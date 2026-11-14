"""One four-input cumulative revision diagnostic; default is credential-free preflight."""
import argparse
from copy import deepcopy
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



def save(output, report):
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def preflight(args):
    assert (args.frontend_dir / 'index.html').exists(), 'Build frontend first.'
    names = ['00_explain', '01_reuse', '02_correct', '03_rerank']
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



def stage_wait_result(events, request_id, *, editing=True):
    """A spoken completion is not a chart commit; inspect this request only."""
    if not editing:
        return 'pending'
    own = request_events(events, request_id)
    if any(e['name'] == 'tool_committed' for e in own):
        return 'committed'
    if any(e['name'] == 'request_outcome' and e.get('status') in
           ('no_changes', 'failed', 'awaiting_confirmation') for e in own):
        return 'not_committed'
    return 'pending'


def finish_reason(report, events):
    if report.get('edit_not_committed'):
        return 'edit_not_committed'
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
                                                                      'task_id': 'exp_01_a'})
            await page.goto(base, wait_until='networkidle')
            await wait_until(lambda: any(e['name'] == 'clock_calibrated' for e in workspace.trace.events))
            for view_id in ['v2', 'v3']:
                number = next(v['number'] for v in workspace.store.state['views'] if v['id'] == view_id)
                await page.get_by_role('button', name=f'Select chart {number}', exact=True).click()
            await context.request.post(base + '/api/evidence', data={'revision':3, 'view_id':'v1'})
            await wait_until(lambda: workspace.reference['view_ids'] == ['v2', 'v3'] and bool(workspace.image))
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
                    report['stages'] = []
                    for index, name in enumerate(names):
                        stage = {'name': name, 'input_start_event_index': len(workspace.trace.events)}
                        report['stages'].append(stage)
                        if index:
                            previous = report['stages'][-2]['request_id']
                            def ready():
                                own = request_events(workspace.trace.events, previous)
                                committed = [e for e in own if e['name'] == 'tool_committed']
                                if index == 1:
                                    return bool(unfinished_playback(workspace.trace.events, previous))
                                if not committed:
                                    return False
                                commit_index = committed[-1]['index']
                                captures = [e for e in workspace.trace.events if e['name']=='image_captured'
                                    and e['index']>commit_index and e['reference']['revision']==committed[-1]['revision']]
                                deliveries = [e for e in own if e['name']=='image_delivery' and e.get('status')=='sent'
                                    and any(e.get('frame_id')==capture['file'] for capture in captures)]
                                if not deliveries:
                                    return False
                                delivery_index = deliveries[-1]['index']
                                output_after_image = any(e['name']=='audio_received' and e['index']>delivery_index for e in own)
                                if not output_after_image:
                                    return False
                                revision = workspace.store.state['revision']
                                rendered = {e['details'].get('view_id') for e in workspace.trace.events
                                    if e['name'] == 'chart_rendered' and e['details'].get('revision') == revision}
                                return rendered == {'v1', 'v2', 'v3'} and (
                                    any(e['index']>delivery_index for e in unfinished_playback(workspace.trace.events, previous))
                                    or settled_and_drained(workspace.trace.events, previous))
                            await wait_until(lambda: ready() or workspace.voice is None, 40)
                            if workspace.voice is None or not ready():
                                report['invalid_reason'] = f'No qualifying prior playback/commit before {name}'
                                break
                            stage.update(trigger_event_index=len(workspace.trace.events),
                                overlap_response_ids=[e['details']['response_id'] for e in unfinished_playback(workspace.trace.events, previous)],
                                prior_completed=settled_and_drained(workspace.trace.events, previous))
                            if index == 3:
                                await page.get_by_role('button', name='Select chart 3', exact=True).click()
                                await wait_until(lambda: workspace.reference['view_ids'] == ['v2'])
                        clip_seconds = report['audio'][name]['duration_seconds']
                        if time.monotonic()-started+clip_seconds+.5 >= 55:
                            report['invalid_reason'] = f'Insufficient budget for complete input: {name}'
                            stage['not_reached'] = True
                            report['budget_exhausted_before_input'] = name
                            break
                        stage['input_start_event_index'] = len(workspace.trace.events)
                        await page.evaluate('(name) => window.__spokenInput.start(name)', name)
                        stage['input_complete'] = True
                        await wait_until(lambda: any(e['name'] == 'request_accepted' and e['index'] >= stage['input_start_event_index']
                            for e in workspace.trace.events) or workspace.voice is None, 15)
                        accepted = [e for e in workspace.trace.events if e['name'] == 'request_accepted'
                            and e['index'] >= stage['input_start_event_index']]
                        if not accepted:
                            report['invalid_reason'] = f'Input not accepted: {name}'
                            break
                        stage['request_id'] = accepted[-1]['request_id']
                        if index:
                            await wait_until(lambda: stage_wait_result(workspace.trace.events, stage['request_id']) != 'pending'
                                or workspace.voice is None, 35)
                            if stage_wait_result(workspace.trace.events, stage['request_id']) != 'committed':
                                stage['not_committed'] = True
                                stage['terminal_events'] = request_events(workspace.trace.events, stage['request_id'])
                                report['edit_not_committed'] = name
                                save(args.output_dir, report)
                                break
                            committed_revision = workspace.store.state['revision']
                            await wait_until(lambda: {e['details'].get('view_id') for e in workspace.trace.events
                                if e['name']=='chart_rendered' and e['details'].get('revision')==committed_revision} == {'v1','v2','v3'}
                                or workspace.voice is None, 10)
                            stage['state_after_commit'] = workspace.store.snapshot()
                            stage['proposal'] = deepcopy(workspace.proposal)
                            stage['own_events_at_capture'] = request_events(workspace.trace.events, stage['request_id'])
                            await page.screenshot(path=str(args.output_dir / f'stage-{index}.png'))
                        save(args.output_dir, report)
                    if len(report['stages']) == 4 and report['stages'][-1].get('request_id'):
                        final_id = report['stages'][-1]['request_id']
                        report['revision_request_id'] = final_id
                        await wait_until(lambda: settled_and_drained(workspace.trace.events, final_id)
                            or workspace.voice is None, 45)
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
            request_id = report.get('revision_request_id')
            own = request_events(events, request_id) if request_id else []
            report['stopped_after_first_tool_failure'] = next((e for e in events if e['name'] == 'tool_failed'), report.get('stopped_after_first_tool_failure'))
            report['final_output_audio'] = any(e['name'] == 'audio_received' for e in own)
            report['final_settled_and_drained'] = bool(request_id) and settled_and_drained(events, request_id)
            report['final_natural_playback_completed'] = bool(request_id) and natural_playback_completed(events, request_id)
            report['finish_reason'] = finish_reason(report, events)
            save(args.output_dir, report)
            if initial:
                from backend.oracle import category_rows, numeric_rows_equal
                expected = {v['id']: deepcopy(v['source']) for v in initial['views']}
                members = [r['label'] for r in workspace.snapshots[3]['views'][0]['data']['rows']]
                for target in ('v2', 'v3'):
                    expected[target].update(categories=members, top_n=None, start='2017-01-01', end='2017-04-01')
                expected['v2'].update(categories=None, top_n=3, rank_by='orders')
                final = report['final_state']
                checks = {'connection_under_60_seconds': report.get('connection_wall_seconds',61) <= 60,
                    'four_complete_inputs': len(report.get('stages', [])) == 4 and all(s.get('input_complete') for s in report.get('stages', [])),
                    'final_natural_playback_completed': report['final_natural_playback_completed'],
                    'no_browser_errors': not errors,
                    'chart1_unchanged': final['views'][0] == initial['views'][0],
                    'final_views_rendered': {e['details'].get('view_id') for e in events if e['name']=='chart_rendered'
                        and e['details'].get('revision')==final['revision']} == {'v1','v2','v3'},
                    'actual_image_sent': any(e['name']=='image_delivery' and e.get('status')=='sent' for e in events)}
                for view in final['views']:
                    source = expected[view['id']]
                    checks[view['id']+'_source'] = view['source'] == source
                    checks[view['id']+'_sql'] = numeric_rows_equal(view['data']['rows'], category_rows(workspace.data, source))
                for i, stage in enumerate(report.get('stages', [])):
                    own = request_events(events, stage.get('request_id'))
                    stage['events'] = own
                    next_stage = report['stages'][i+1] if i+1 < len(report['stages']) else None
                    end_index = next_stage['input_start_event_index'] if next_stage else len(events)
                    if i:
                        checks[f'stage_{i}_commit'] = any(e['name']=='tool_committed' for e in own)
                        stage_expected = deepcopy(expected)
                        if i < 3:
                            stage_expected['v2'].update(categories=members, top_n=None)
                        if i == 1:
                            for target in ('v2','v3'):
                                stage_expected[target].update(start=initial['views'][1]['source']['start'], end=initial['views'][1]['source']['end'])
                        snapshot = stage.get('state_after_commit', {})
                        checks[f'stage_{i}_sources'] = bool(snapshot) and all(v['source']==stage_expected[v['id']] for v in snapshot.get('views', []))
                        stage['card_events'] = [e for e in events if e['name'].startswith('revision_card_') and stage['input_start_event_index']<=e['index']<end_index]
                    if i == 1:
                        trigger = stage['input_start_event_index']
                        checks['reuse_speech_during_actual_playback'] = any(e['name']=='speech_start' and e['index']>=trigger
                            and any(end['name']=='playback_end' and end['details'].get('response_id') in stage.get('overlap_response_ids', [])
                                and end['index']>e['index'] for end in events) for e in events)
                report['overlap_valid'] = checks.get('reuse_speech_during_actual_playback', False)
                report['evaluation'] = {'checks': checks, 'passed': all(checks.values()), 'expected_sources': expected}
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
    parser.add_argument('--case', default='01', choices=['01'])
    parser.add_argument('--condition', choices=['direct', 'bound_revision'], default='bound_revision')
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
