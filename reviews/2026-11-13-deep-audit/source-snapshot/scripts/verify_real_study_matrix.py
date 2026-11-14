"""One explicitly selected real-browser diagnostic; default is credential-free preflight."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import wave

import uvicorn
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_two_real_cases import microphone_script
from scripts.verify_live_browser import wait_until
from scripts.api_trial_specs import CASES, score_final

TARGETS = CASES


def save(output, report):
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def preflight(args):
    assert (args.frontend_dir / 'index.html').exists(), 'Build frontend first.'
    names = [CASES[args.case]['initial_clip'], CASES[args.case]['revision_clip']]
    records = {}
    for name in names:
        path = args.audio_dir / f'{name}.wav'
        with wave.open(str(path), 'rb') as audio:
            assert audio.getparams()[:3] == (1, 2, 16000), f'{name}: expected mono PCM16 16kHz'
            seconds = audio.getnframes() / audio.getframerate()
            assert 0 < seconds <= 10, f'{name}: complete input must be <=10 seconds'
        shutil.copy2(path, args.output_dir / path.name)
        records[name] = {'path': str(path.resolve()), 'duration_seconds': seconds,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return names, records


def request_events(events, request_id):
    return [event for event in events if event.get('request_id') == request_id]


def unfinished_playback(events, request_id):
    own = request_events(events, request_id)
    ended = {e['details'].get('response_id') for e in own if e['name'] == 'playback_end'}
    return [e for e in own if e['name'] == 'playback_start' and e['details'].get('response_id') not in ended]


def settled_and_drained(events, request_id):
    own = request_events(events, request_id)
    if not any(e['name'] == 'request_outcome' for e in own):
        return False
    responses = {e.get('response_id') for e in own if e['name'] == 'audio_received'}
    ends = {e['details'].get('response_id') for e in own if e['name'] == 'playback_end'
            and e['details'].get('queue_empty') and e['details'].get('pending_chunks') == 0}
    return responses <= ends


def natural_playback_completed(events, request_id):
    own = request_events(events, request_id)
    responses = {e.get('response_id') for e in own if e['name'] == 'audio_received'}
    ends = {e['details'].get('response_id') for e in own if e['name'] == 'playback_end'
            and not e['details'].get('interrupted') and e['details'].get('queue_empty')
            and e['details'].get('pending_chunks') == 0
            and e['details'].get('played_samples') == e['details'].get('received_samples')}
    return bool(responses) and responses <= ends


def revision_complete(events, report):
    """Follow the latest fragment; an older fragment's settlement cannot finish it."""
    after = [e for e in events if e['index'] >= report['revision_trigger_event_index']]
    accepted = [e for e in after if e['name'] == 'request_accepted']
    if not accepted:
        return False
    latest = accepted[-1]['request_id']
    report['revision_request_id'] = latest
    onsets = [e for e in after if e['name'] == 'speech_start']
    if onsets and onsets[-1].get('request_id') != latest:
        return False
    return bool(report.get('revision_input_complete')) and settled_and_drained(events, latest)


def finish_reason(report, events):
    if report.get('stopped_after_first_tool_failure'):
        return 'tool_failure'
    if any(e['name'] in ('error', 'session_error') or
           (e['name'] == 'transport_closed' and e.get('reason') == 'error') for e in events):
        return 'transport_error'
    if report.get('timed_out') or report.get('watchdog_fired'):
        return 'timeout'
    if report.get('invalid_reason'):
        return 'invalid_overlap'
    return 'error' if report.get('error') else 'completed'


async def close_after_watchdog(workspace, watchdog):
    watchdog.cancel()
    await asyncio.gather(watchdog, return_exceptions=True)
    await workspace.close_voice()


async def run_case(args, names, report, settings):
    from backend.app import create_app
    app = create_app({**settings, 'frontend_dir': args.frontend_dir, 'trace_dir': args.output_dir / 'sessions'})
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='error'))
    running = asyncio.create_task(server.serve())
    workspace = browser = context = page = watchdog = None
    started = None
    initial = None
    errors = []
    redact = lambda value: str(value).replace(settings['api_key'], '[REDACTED]')
    try:
        await wait_until(lambda: server.started)
        workspace = app.state.workspace
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=['--autoplay-policy=no-user-gesture-required'])
            context = await browser.new_context(viewport={'width': 2560, 'height': 1440}, device_scale_factor=1.5,
                                                record_video_dir=str(args.output_dir / 'video'))
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            await context.add_init_script(microphone_script({name: args.audio_dir / f'{name}.wav' for name in names}))
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(redact(error)))
            base = f'http://127.0.0.1:{args.port}'
            await context.request.post(base + '/api/session', data={'mode': 'live_voice', 'condition': args.condition,
                                                                      'task_id': CASES[args.case]['task_id']})
            await page.goto(base, wait_until='networkidle')
            await wait_until(lambda: any(e['name'] == 'clock_calibrated' for e in workspace.trace.events))
            for view_id in CASES[args.case]['targets']:
                number = next(v['number'] for v in workspace.store.state['views'] if v['id'] == view_id)
                await page.get_by_role('button', name=f'Select chart {number}', exact=True).click()
            if CASES[args.case]['evidence']:
                await context.request.post(base + '/api/evidence', data=CASES[args.case]['evidence'])
            await wait_until(lambda: workspace.reference['view_ids'] == CASES[args.case]['targets'] and bool(workspace.image))
            initial = workspace.store.snapshot()
            report['initial_state'] = initial
            await page.screenshot(path=str(args.output_dir / 'before.png'))

            async def budget():
                while time.monotonic() - started < 55:
                    failed = next((e for e in workspace.trace.events if e['name'] == 'tool_failed'), None)
                    if failed:
                        report['stopped_after_first_tool_failure'] = failed
                        break
                    await asyncio.sleep(.04)
                else:
                    report['watchdog_fired'] = True
                await workspace.close_voice()

            started = time.monotonic()
            report.update(api_attempted=True, status='running', started_at=datetime.now(timezone.utc).isoformat(),
                          configured_model=settings['realtime_model'])
            save(args.output_dir, report)
            watchdog = asyncio.create_task(budget())
            try:
                async with asyncio.timeout(55):
                    await page.get_by_role('button', name='Start speaking', exact=True).click()
                    await wait_until(lambda: any(e['name'] in ('voice_connected', 'session_error', 'error') for e in workspace.trace.events), 18)
                    failures = [e for e in workspace.trace.events if e['name'] in ('session_error', 'error')]
                    if failures:
                        raise RuntimeError(failures[-1].get('message') or failures[-1].get('event', {}).get('message'))
                    await page.wait_for_function('!!window.__spokenInput')
                    await page.evaluate('(name) => window.__spokenInput.start(name)', names[0])
                    await wait_until(lambda: any(e['name'] == 'request_accepted' for e in workspace.trace.events) or workspace.voice is None, 15)
                    accepted = [e for e in workspace.trace.events if e['name'] == 'request_accepted']
                    if not accepted:
                        report['invalid_reason'] = 'Initial input was not accepted.'
                    else:
                        initial_request = accepted[-1]['request_id']
                        report['initial_request_id'] = initial_request
                        def ready():
                            own = request_events(workspace.trace.events, initial_request)
                            return bool(unfinished_playback(workspace.trace.events, initial_request)) and (
                                not CASES[args.case]['initial_requires_commit'] or any(e['name'] == 'tool_committed' for e in own))
                        await wait_until(lambda: ready() or settled_and_drained(workspace.trace.events, initial_request)
                                         or workspace.voice is None, 40)
                        if ready() and workspace.voice is not None and not report.get('stopped_after_first_tool_failure'):
                            report.update(overlap_valid=True, state_at_revision=workspace.store.snapshot(),
                                          revision_trigger_event_index=len(workspace.trace.events),
                                          overlap_response_ids=[e['details']['response_id'] for e in unfinished_playback(workspace.trace.events, initial_request)])
                            save(args.output_dir, report)
                            # start() resolves only after the complete source WAV has played.
                            await page.evaluate('(name) => window.__spokenInput.start(name)', names[1])
                            report['revision_input_complete'] = True
                            await wait_until(lambda: any(e['name'] == 'request_accepted' and e['index'] >= report['revision_trigger_event_index']
                                                        for e in workspace.trace.events) or workspace.voice is None, 15)
                            revised = [e for e in workspace.trace.events if e['name'] == 'request_accepted'
                                       and e['index'] >= report['revision_trigger_event_index']]
                            if revised:
                                await wait_until(lambda: revision_complete(workspace.trace.events, report)
                                                 or workspace.voice is None, 45)
                            else:
                                report['invalid_reason'] = 'Revision input was not accepted.'
                        else:
                            report['invalid_reason'] = 'No actual unfinished initial-request playback; revision was not forced.'
            except TimeoutError:
                report['timed_out'] = True
            finally:
                await close_after_watchdog(workspace, watchdog)
                report['connection_wall_seconds'] = time.monotonic() - started
                save(args.output_dir, report)
            report['browser_input_segments'] = await page.evaluate('window.__spokenInput?.segments || []')
            await page.evaluate('window.__spokenInput?.close()')
            await page.screenshot(path=str(args.output_dir / 'after.png'))
            await context.tracing.stop(path=str(args.output_dir / 'browser-trace.zip'))
            await context.close()
            context = None
            await browser.close()
            browser = None
    except (Exception, asyncio.CancelledError) as error:
        report.update(status='failed', error=redact(repr(error)))
    finally:
        if watchdog:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)
        if workspace:
            await workspace.close_voice()
            if started:
                report.setdefault('connection_wall_seconds', time.monotonic() - started)
            events = workspace.trace.events
            report.update(final_state=workspace.store.snapshot(), browser_errors=errors,
                          session_directory=str(workspace.trace.directory), original_task_static_report=workspace.score(),
                          input_pcm_total_seconds=sum(e['bytes'] for e in events if e['name'] == 'audio_sent') / 32000,
                          events=events)
            if 'revision_trigger_event_index' in report:
                revision_complete(events, report)
            request_id = report.get('revision_request_id')
            own = request_events(events, request_id) if request_id else []
            report['stopped_after_first_tool_failure'] = next((e for e in events if e['name'] == 'tool_failed'), report.get('stopped_after_first_tool_failure'))
            report['final_output_audio'] = any(e['name'] == 'audio_received' for e in own)
            report['final_settled_and_drained'] = bool(request_id) and settled_and_drained(events, request_id)
            report['final_natural_playback_completed'] = bool(request_id) and natural_playback_completed(events, request_id)
            report['finish_reason'] = finish_reason(report, events)
            save(args.output_dir, report)
            if initial:
                scored = score_final(workspace.data, initial, report['final_state'], workspace.snapshots, args.case)
                report['evaluation'] = scored
                checks = scored['checks']
                final_revision = report['final_state']['revision']
                overlap_ids = report.get('overlap_response_ids', [])
                trigger = report.get('revision_trigger_event_index', len(events))
                checks.update(connection_under_60_seconds=report.get('connection_wall_seconds', 61) <= 60,
                              actual_overlap=report['overlap_valid'],
                              actual_revision_speech_during_playback=any(e['name'] == 'speech_start' and e['index'] >= trigger
                                  and any(end['name'] == 'playback_end' and end['details'].get('response_id') in overlap_ids
                                          and end['index'] > e['index'] for end in events) for e in events),
                              revision_commit=any(e['name'] == 'tool_committed' for e in own),
                              final_settled_and_drained=report['final_settled_and_drained'],
                              actual_output_audio=report['final_output_audio'],
                              final_natural_playback_completed=report['final_natural_playback_completed'], no_browser_errors=not errors,
                              actual_image_sent=any(e['name'] == 'image_delivery' and e.get('status') == 'sent' for e in events),
                              final_views_rendered={e['details']['view_id'] for e in events if e['name'] == 'chart_rendered'
                                  and e['details']['revision'] == final_revision} == {v['id'] for v in report['final_state']['views']})
                if not CASES[args.case]['initial_requires_commit']:
                    checks['initial_discussion_left_charts_unchanged'] = report.get('state_at_revision') == initial
                if CASES[args.case]['initial_requires_commit']:
                    intermediate = report.get('state_at_revision', {})
                    targets = [v for v in intermediate.get('views', []) if v['id'] in CASES[args.case]['targets']]
                    checks['first_half_before_revision'] = len(targets) == 2 and all(v['source']['start'] == '2017-01-01'
                        and v['source']['end'] == '2017-07-01' for v in targets)
                scored['passed'] = all(checks.values())
            workspace.trace.finalize_audio()
            workspace.trace.save('session.json', workspace.export())
            report['status'] = 'passed' if report['finish_reason'] == 'completed' and report.get('evaluation', {}).get('passed') else 'failed'
        save(args.output_dir, report)
        if context:
            await context.close()
        if browser:
            await browser.close()
        server.should_exit = True
        await running
        save(args.output_dir, report)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=TARGETS, required=True)
    parser.add_argument('--condition', choices=['direct', 'bound_revision'], required=True)
    parser.add_argument('--run-real', action='store_true')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--audio-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend/dist')
    parser.add_argument('--port', type=int, default=8072)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {'case': args.case, 'condition': args.condition, 'status': 'preflight', 'api_attempted': False,
              'automatic_retries': 0, 'overlap_valid': False, 'human_listening': 'pending',
              'spoken_semantic_consistency': 'pending', 'study_parity': 'not_established'}
    try:
        names, report['audio'] = preflight(args)
        save(args.output_dir, report)
        if args.run_real:
            assert args.env_file, '--run-real requires explicit --env-file'
            from backend.settings import load_settings
            settings = load_settings(args.env_file)
            assert settings['api_key'], 'Selected configuration has no key.'
            assert settings['realtime_model'] == 'qwen3.8-omni-flash-realtime'
            await run_case(args, names, report, settings)
        else:
            report.update(status='prepared', paid_api_calls=0)
    except (Exception, asyncio.CancelledError) as error:
        report.update(status='failed', error_type=type(error).__name__)
    finally:
        save(args.output_dir, report)
        print(json.dumps({'status': report['status'], 'report': str(args.output_dir / 'report.json')}))
    if report['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
