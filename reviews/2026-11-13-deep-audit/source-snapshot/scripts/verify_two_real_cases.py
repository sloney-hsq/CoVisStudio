"""Two explicitly authorized real browser voice attempts; never retries.

Default is audio/driver preflight only: no settings or credentials are loaded.
Provide existing neural speech WAVs, mono PCM16 16kHz, each under ten seconds.
"""
import argparse
import asyncio
import base64
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
from scripts.verify_live_browser import wait_until
from backend.oracle import category_rows, numeric_rows_equal


def microphone_script(paths):
    clips = {name: base64.b64encode(path.read_bytes()).decode() for name, path in paths.items()}
    return """(() => {
      const clips = __CLIPS__;
      navigator.mediaDevices.getUserMedia = async () => {
        const context = new AudioContext({sampleRate:16000});
        const destination = context.createMediaStreamDestination();
        const buffers = {};
        for (const [name, encoded] of Object.entries(clips)) {
          const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
          buffers[name] = await context.decodeAudioData(bytes.buffer);
        }
        window.__spokenInput = {
          segments: [],
          start: async name => {
            await context.resume();
            const source = context.createBufferSource(); source.buffer = buffers[name];
            source.connect(destination);
            const segment = {name, started_client_ms: performance.now(), duration:source.buffer.duration};
            window.__spokenInput.segments.push(segment);
            return await new Promise(resolve => {
              source.onended = () => {segment.ended_client_ms = performance.now(); resolve(segment)};
              source.start();
            });
          },
          close: async () => {destination.stream.getTracks().forEach(t => t.stop()); await context.close()}
        };
        return destination.stream;
      };
    })();""".replace('__CLIPS__', json.dumps(clips))


def preflight(args, output):
    assert (args.frontend_dir / 'index.html').exists(), 'Build frontend first.'
    records = {}
    for name in ('01_reuse', '02_initial', '03_revision'):
        path = args.audio_dir / f'{name}.wav'
        with wave.open(str(path), 'rb') as audio:
            assert audio.getparams()[:3] == (1, 2, 16000), f'{path}: expected mono PCM16 16kHz'
            seconds = audio.getnframes() / audio.getframerate()
            assert 0 < seconds < 10, f'{path}: each spoken segment must be <10 seconds'
        shutil.copy2(path, output / path.name)
        records[name] = {'path': str(path.resolve()), 'duration_seconds': seconds,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return records


async def case(args, output, number, settings):
    from backend.app import create_app
    app = create_app({**settings, 'frontend_dir': args.frontend_dir, 'trace_dir': output / 'sessions'})
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='error'))
    running = asyncio.create_task(server.serve())
    workspace = context = browser = None
    initial = None
    started = None
    watchdog = None
    report = {'case': number, 'status': 'running', 'api_attempted': False, 'automatic_retries': 0,
              'human_listening': 'pending', 'spoken_semantic_consistency': 'pending',
              'overlap_valid': None if number == 1 else False}
    errors = []
    key = settings['api_key']
    redact = lambda value: str(value).replace(key, '[REDACTED]')
    try:
        await wait_until(lambda: server.started)
        workspace = app.state.workspace
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=['--autoplay-policy=no-user-gesture-required'])
            context = await browser.new_context(viewport={'width':2560, 'height':1440}, device_scale_factor=1.5,
                                                record_video_dir=str(output / 'video'))
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            names = ('01_reuse',) if number == 1 else ('02_initial', '03_revision')
            await context.add_init_script(microphone_script({name: args.audio_dir / f'{name}.wav' for name in names}))
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(redact(error)))
            page.on('console', lambda message: (output / 'browser-console.jsonl').open('a', encoding='utf-8').write(
                json.dumps({'type':message.type, 'text':redact(message.text)}) + '\n'))
            mode = 'push_to_talk' if number == 1 else 'live_voice'
            base = f'http://127.0.0.1:{args.port}'
            await context.request.post(base + '/api/session', data={'mode':mode, 'condition':'bound_revision', 'task_id':'exp_01_a'})
            await page.goto(base, wait_until='networkidle')
            await wait_until(lambda: any(e['name'] == 'clock_calibrated' for e in workspace.trace.events))
            await page.get_by_role('button', name='Select chart 2', exact=True).click()
            await page.get_by_role('button', name='Select chart 3', exact=True).click()
            await context.request.post(base + '/api/evidence', data={'revision':3, 'view_id':'v1'})
            await wait_until(lambda: workspace.reference['view_ids'] == ['v2','v3'] and bool(workspace.image))
            initial = workspace.store.snapshot()
            assert {v['id'] for v in initial['views']} == {'v1','v2','v3'}
            assert all(v['source']['region'] == 'MG' for v in initial['views'] if v['id'] in ('v2','v3'))
            report['initial_state'] = initial
            await page.screenshot(path=str(output / 'before.png'))

            async def budget():
                while time.monotonic() - started < 55:
                    failed = next((e for e in workspace.trace.events if e['name'] == 'tool_failed'), None)
                    if failed:
                        report['stopped_after_first_tool_failure'] = failed
                        break
                    await asyncio.sleep(.04)
                else:
                    report['watchdog_fired'] = True
                outcome = await asyncio.gather(workspace.close_voice(), return_exceptions=True)
                report['watchdog_cleanup_errors'] = [redact(repr(e)) for e in outcome if isinstance(e, BaseException)]

            started = time.monotonic()
            report.update(api_attempted=True, configured_model=settings['realtime_model'],
                          started_at=datetime.now(timezone.utc).isoformat())
            watchdog = asyncio.create_task(budget())
            try:
                async with asyncio.timeout(55):
                    await page.get_by_role('button', name='Start speaking', exact=True).click()
                    await wait_until(lambda: any(e['name'] in ('voice_connected','session_error','error') for e in workspace.trace.events), 18)
                    failures = [e for e in workspace.trace.events if e['name'] in ('session_error','error')]
                    if failures:
                        raise RuntimeError(failures[-1].get('message') or failures[-1].get('event',{}).get('message'))
                    await page.wait_for_function('!!window.__spokenInput')
                    if number == 1:
                        await page.get_by_role('button', name='Send recording', exact=True).wait_for(state='visible')
                        await page.evaluate("window.__spokenInput.start('01_reuse')")
                        await page.get_by_role('button', name='Send recording', exact=True).click()
                    else:
                        await page.get_by_role('button', name='End voice session', exact=True).wait_for(state='visible')
                        await page.evaluate("window.__spokenInput.start('02_initial')")
                        def overlap():
                            events = workspace.trace.events
                            commits = [e for e in events if e['name'] == 'tool_committed']
                            ends = {e['details'].get('response_id') for e in events if e['name'] == 'playback_end'}
                            starts = [e for e in events if e['name'] == 'playback_start' and e['details'].get('response_id') not in ends]
                            return bool(commits and starts)
                        await wait_until(lambda: overlap() or workspace.voice is None, 40)
                        if overlap():
                            report['overlap_valid'] = True
                            report['state_at_revision'] = workspace.store.snapshot()
                            report['revision_trigger_event_index'] = len(workspace.trace.events)
                            report['overlap_response_ids'] = [e['details']['response_id'] for e in workspace.trace.events
                                if e['name'] == 'playback_start' and not any(end['name'] == 'playback_end'
                                and end['details'].get('response_id') == e['details']['response_id'] for end in workspace.trace.events)]
                            await page.evaluate("window.__spokenInput.start('03_revision')")
                        else:
                            report['invalid_reason'] = 'No actual non-ended playback after a tool commit; revision was not forced.'
                    def drained():
                        voice = workspace.voice
                        after = report.get('revision_trigger_event_index', 0)
                        transcripts = [e for e in workspace.trace.events if e['name'] == 'user_transcript' and e['index'] >= after]
                        ended = bool(transcripts) and any(e['name'] == 'playback_end'
                            and not e['details'].get('interrupted') and e['index'] > transcripts[-1]['index']
                            and e.get('request_id') == transcripts[-1].get('request_id')
                            for e in workspace.trace.events)
                        return voice is None or (ended and voice.active is None and not voice.jobs and not voice.requested and voice.wanted is None)
                    await wait_until(drained, 55)
                    if workspace.voice is not None:
                        label = 'End session' if number == 1 else 'End voice session'
                        await page.get_by_role('button', name=label, exact=True).click()
                        await wait_until(lambda: workspace.voice is None, 3)
            except TimeoutError:
                report['timed_out'] = True
            finally:
                outcome = await asyncio.gather(workspace.close_voice(), return_exceptions=True)
                report['voice_cleanup_errors'] = [redact(repr(e)) for e in outcome if isinstance(e, BaseException)]
                report['connection_wall_seconds'] = time.monotonic() - started
                (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                watchdog.cancel()
                await asyncio.gather(watchdog, return_exceptions=True)
            report['browser_input_segments'] = await page.evaluate('window.__spokenInput.segments')
            await page.evaluate('window.__spokenInput.close()')
            await page.screenshot(path=str(output / 'after.png'))
            await context.tracing.stop(path=str(output / 'browser-trace.zip'))
            await context.close()
            context = None
            await browser.close()
            browser = None
    except (Exception, asyncio.CancelledError) as error:
        report.update(status='failed', error=redact(repr(error)))
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if watchdog:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)
        if workspace:
            outcome = await asyncio.gather(workspace.close_voice(), return_exceptions=True)
            report['final_voice_cleanup_errors'] = [redact(repr(e)) for e in outcome if isinstance(e, BaseException)]
            if started and 'connection_wall_seconds' not in report:
                report['connection_wall_seconds'] = time.monotonic() - started
            final = workspace.store.snapshot()
            events = workspace.trace.events
            finish_reason = 'timeout' if report.get('timed_out') or report.get('watchdog_fired') else 'abandoned' if report.get('error') else 'completed'
            report['finish_reason'] = finish_reason
            report['original_task_static_report'] = workspace.score()
            report.update(final_state=final, browser_errors=errors,
                          session_directory=str(workspace.trace.directory),
                          input_pcm_total_seconds=sum(e['bytes'] for e in events if e['name'] == 'audio_sent') / 32000,
                          transcripts=[e for e in events if e['name'] in ('user_transcript','assistant_done')],
                          playback_events=[e for e in events if e['name'] in ('playback_start','playback_progress','playback_end')],
                          tool_commits=[e for e in events if e['name'] == 'tool_committed'])
            final_transcripts = [e for e in events if e['name'] == 'user_transcript'
                and e['index'] >= report.get('revision_trigger_event_index', 0)]
            final_transcript = final_transcripts[-1] if final_transcripts else None
            if initial:
                members = [row['label'] for row in workspace.snapshots[3]['views'][0]['data']['rows']]
                checks = {'untargeted_chart_unchanged': initial['views'][0] == final['views'][0],
                          'connection_under_60_seconds': report.get('connection_wall_seconds',0) <= 60,
                          'actual_commit': bool(report['tool_commits']), 'no_browser_errors': not errors,
                          'actual_transcription': any(e['name'] == 'user_transcript' for e in events),
                          'actual_output_audio': any(e['name'] == 'audio_received' for e in events),
                          'actual_image_sent': any(e['name'] == 'image_delivery' and e.get('status') == 'sent' for e in events),
                          'final_playback_drained': bool(final_transcript) and any(e['name'] == 'playback_end'
                            and e['index'] > final_transcript['index']
                            and e.get('request_id') == final_transcript.get('request_id')
                            and not e['details'].get('interrupted')
                            and e['details'].get('queue_empty') and e['details'].get('pending_chunks') == 0 for e in events),
                          'final_views_rendered': {e['details']['view_id'] for e in events if e['name'] == 'chart_rendered'
                            and e['details']['revision'] == final['revision']} == {'v1','v2','v3'}}
                for view_id in ('v2','v3'):
                    original = next(v for v in initial['views'] if v['id'] == view_id)
                    view = next(v for v in final['views'] if v['id'] == view_id)
                    expected = {**original['source'], 'categories':members, 'top_n':None}
                    if number == 2:
                        expected.update(start='2017-01-01', end='2017-04-01')
                    checks[f'{view_id}_scope'] = view['source'] == expected
                    checks[f'{view_id}_independent_sql'] = numeric_rows_equal(view['data']['rows'], category_rows(workspace.data, expected))
                if number == 2:
                    checks['actual_overlap'] = report['overlap_valid']
                    trigger = report.get('revision_trigger_event_index', len(events))
                    overlap_ids = report.get('overlap_response_ids', [])
                    checks['actual_revision_speech_during_playback'] = any(e['name'] == 'speech_start' and e['index'] >= trigger
                        and any(end['name'] == 'playback_end' and end['details'].get('response_id') in overlap_ids
                        and end['index'] > e['index'] for end in events) for e in events)
                    intermediate = report.get('state_at_revision', {})
                    checks['first_half_before_revision'] = all(v['source']['end'] == '2017-07-01' for v in intermediate.get('views',[]) if v['id'] in ('v2','v3')) and bool(intermediate)
                report['checks'] = checks
                report['status'] = 'passed' if all(checks.values()) and not report.get('timed_out') and not report.get('error') else 'failed'
            workspace.trace.finalize_audio()
            workspace.trace.save('session.json', workspace.export())
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if context:
            await context.close()
        if browser:
            await browser.close()
        server.should_exit = True
        await running
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-real', action='store_true')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--audio-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend/dist')
    parser.add_argument('--port', type=int, default=8072)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {'status':'preflight', 'api_attempted':False, 'automatic_retries':0}
    try:
        report['audio'] = preflight(args, args.output_dir)
        if args.run_real:
            assert args.env_file, '--run-real requires an explicit --env-file'
            from backend.settings import load_settings
            settings = load_settings(args.env_file)
            assert settings['api_key'], 'Selected configuration has no key.'
            assert settings['realtime_model'] == 'qwen3.8-omni-flash-realtime'
            report['cases'] = []
            for number in (1,2):
                output = args.output_dir / f'case-{number}'
                output.mkdir()
                report['api_attempted'] = True
                report['cases_started'] = number
                (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                result = await case(args, output, number, settings)
                report['cases'].append(result)
            report['api_attempted'] = any(r['api_attempted'] for r in report['cases'])
            report['status'] = 'passed' if all(r['status'] == 'passed' for r in report['cases']) else 'failed'
        else:
            report.update(status='prepared', paid_api_calls=0)
    except (Exception, asyncio.CancelledError) as error:
        report.update(status='failed', error=repr(error))
    finally:
        (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'status':report['status'], 'report':str(args.output_dir / 'report.json')}))
    if report['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
