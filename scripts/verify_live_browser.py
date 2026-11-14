"""One explicitly authorized realtime API attempt using offline spoken input.

Without --run-real this only creates a Windows SAPI recording. The real path
uses the production PTT UI, AudioWorklet, image capture, native adapter and tools.
There is no scripted transcript, forced tool call, retry or physical microphone.
"""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import wave

import uvicorn
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROMPT = ('Use the categories in the selected historical chart for charts two and three. '
          'Keep the current region, dates, and metrics. Apply the revision and explain briefly.')


def prepare_speech(directory):
    """Offline Windows speech synthesis; complete utterance with short silence."""
    raw = directory / 'spoken-request-raw.wav'
    script = r'''
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$english = $speaker.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1
$speaker.SelectVoice($english.VoiceInfo.Name)
$speaker.Rate = 3
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$speaker.SetOutputToWaveFile('__PATH__', $format)
$speaker.Speak('__PROMPT__')
$speaker.Dispose()
'''.replace('__PATH__', str(raw).replace("'", "''")).replace('__PROMPT__', PROMPT.replace("'", "''"))
    (directory / 'synthesize.ps1').write_text(script, encoding='utf-8')
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                    base64.b64encode(script.encode('utf-16le')).decode()],
                   capture_output=True, text=True, check=True)
    with wave.open(str(raw), 'rb') as recording:
        assert recording.getparams()[:3] == (1, 2, 16000)
        pcm = recording.readframes(recording.getnframes())
    pcm = bytes(3200) + pcm + bytes(6400)  # 100 ms lead, 200 ms tail.
    seconds = len(pcm) / 32000
    assert seconds <= 9, f'Offline speech is {seconds:.3f}s; shorten it before any API attempt.'
    path = directory / 'spoken-request.wav'
    with wave.open(str(path), 'wb') as recording:
        recording.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        recording.writeframes(pcm)
    return path, seconds


def browser_microphone_script(path):
    """Start prerecorded speech after voice_ready, so handshake cannot eat it."""
    encoded = base64.b64encode(path.read_bytes()).decode()
    return """(() => {
      navigator.mediaDevices.getUserMedia = async () => {
        const context = new AudioContext({ sampleRate: 16000 });
        const bytes = Uint8Array.from(atob('__WAV__'), char => char.charCodeAt(0));
        const buffer = await context.decodeAudioData(bytes.buffer);
        const destination = context.createMediaStreamDestination();
        const source = context.createBufferSource();
        source.buffer = buffer; source.connect(destination);
        window.__spokenInput = {
          start: async () => {
            await context.resume();
            return await new Promise(resolve => {
              source.onended = () => resolve(buffer.duration);
              source.start();
            });
          },
          close: async () => { destination.stream.getTracks().forEach(t => t.stop()); await context.close(); }
        };
        return destination.stream;
      };
    })();""".replace('__WAV__', encoded)


async def wait_until(predicate, seconds=20):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(.04)


def summarize(workspace, initial, report):
    """Separate actual evidence at each stage; no model self-claim is a pass."""
    events = workspace.trace.events
    sent = [e['event']['event'] for e in events if e['name'] == 'provider_event'
            and e['event']['direction'] == 'sent']
    received = [e for e in events if e['name'] == 'audio_received']
    input_bytes = sum(e['bytes'] for e in events if e['name'] == 'audio_sent')
    commits = [e for e in events if e['name'] == 'tool_committed']
    final = workspace.store.snapshot()
    transcripts = [{'role': 'user' if e['name'] == 'user_transcript' else 'assistant',
                    'text': e['event']['text'], 'event_index': e['index']}
                   for e in events if e['name'] in ('user_transcript', 'assistant_done')]
    playback = [e for e in events if e['name'] in ('playback_start', 'playback_end')]
    rendered = {e['details']['view_id'] for e in events if e['name'] == 'chart_rendered'
                and e['details']['revision'] == final['revision']}
    checks = {
        'recognized_nonempty_input': any(t['role'] == 'user' and t['text'].strip() for t in transcripts),
        'initial_image_sent': any(e['type'] == 'input_image_buffer.append' for e in sent),
        'actual_tool_commit': bool(commits),
        'technical_chart_correct': bool(report['technical_completed']),
        'untargeted_chart_unchanged': final['views'][0] == initial['views'][0],
        'final_views_rendered': rendered == {v['id'] for v in final['views']},
        'output_audio_received': bool(received),
        'output_audio_played_to_end': any(e['name'] == 'playback_end' and not e['details']['interrupted'] for e in playback),
        'input_under_ten_seconds': 0 < input_bytes / 32000 <= 10,
        'accepted_selected_views': any(e['name'] == 'request_accepted'
            and e['reference']['view_ids'] == ['v2', 'v3'] for e in events),
    }
    return {'checks': checks, 'input_seconds': round(input_bytes / 32000, 3),
            'transcripts': transcripts, 'playback_events': playback,
            'tool_commits': commits, 'initial_revision': initial['revision'], 'final_revision': final['revision'],
            'image_events': [e for e in events if e['name'] in ('image_captured', 'visual_context_ready')],
            'usage': [e for e in events if e['name'] == 'usage'],
            'actual_final_state': final, 'technical_report': report,
            'human_listening': 'pending', 'spoken_semantic_consistency': 'pending'}


async def run(args, output, microphone_path, report):
    # Configuration and credentials are loaded only after explicit --run-real.
    from backend.app import create_app
    from backend.settings import load_settings
    settings = load_settings(args.env_file) if args.env_file else load_settings()
    if not settings['api_key']:
        raise RuntimeError('The explicitly selected local configuration has no Qwen API key. No API attempt was made.')
    settings.update(frontend_dir=args.frontend_dir, trace_dir=output / 'sessions')
    app = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='error'))
    running = asyncio.create_task(server.serve())
    workspace = browser = context = page = None
    errors = []
    attempt_start = None
    watchdog = None
    initial = None
    budget_ended = asyncio.Event()

    def redact(text):
        return str(text).replace(settings['api_key'], '[REDACTED]')

    async def close_for_budget():
        await asyncio.sleep(55)
        budget_ended.set()
        workspace.trace.record('integration_budget_reached', seconds=55)
        await workspace.close_voice()

    try:
        assert (args.frontend_dir / 'index.html').exists(), 'Build the specified frontend before the API attempt.'
        await wait_until(lambda: server.started)
        workspace = app.state.workspace
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True,
                args=['--autoplay-policy=no-user-gesture-required'])
            context = await browser.new_context(viewport={'width': 2560, 'height': 1440},
                device_scale_factor=1.5, record_video_dir=str(output / 'video'))
            await context.add_init_script(browser_microphone_script(microphone_path))
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(redact(error)))
            await page.goto(f'http://127.0.0.1:{args.port}/', wait_until='networkidle')
            await page.get_by_role('button', name='Experiment', exact=True).click()
            await page.get_by_label('Experiment participant', exact=True).fill('authored-real-api-check')
            await page.get_by_label('Allocation slot', exact=True).fill('5')
            await page.get_by_role('button', name='Load assignment', exact=True).click()
            await page.get_by_role('button', name='Assigned task 1', exact=True).click()
            await page.get_by_role('button', name='Prepare assigned task 1', exact=True).click()
            await page.get_by_role('button', name='Begin task', exact=True).click()
            await expect(page.locator('.trial-curtain')).to_have_count(0)
            assert workspace.session['task_id'] == 'exp_01_a'
            assert workspace.session['condition'] == 'bound_revision'
            await page.locator('.journey-node').filter(has=page.locator('.node-version', has_text=re.compile(r'^v3$'))).click()
            await page.get_by_role('button', name='Use chart 1 version 3 as evidence', exact=True).click()
            await page.get_by_role('button', name='Select chart 2', exact=True).click()
            await page.get_by_role('button', name='Select chart 3', exact=True).click()
            await page.get_by_role('button', name='Push to talk', exact=True).click()
            await wait_until(lambda: workspace.reference['view_ids'] == ['v2', 'v3'] and bool(workspace.image))
            initial = workspace.store.snapshot()
            await page.screenshot(path=str(output / 'before.png'))
            report['api_attempted'] = True
            report['configured_model'] = settings['realtime_model']
            report['attempt_started_at'] = datetime.now(timezone.utc).isoformat()
            attempt_start = time.monotonic()
            watchdog = asyncio.create_task(close_for_budget())
            try:
                async with asyncio.timeout(55):
                    await page.get_by_role('button', name='Start speaking', exact=True).click()
                    await wait_until(lambda: any(e['name'] in ('voice_connected', 'session_error', 'error') for e in workspace.trace.events), 18)
                    failures = [e for e in workspace.trace.events if e['name'] in ('session_error', 'error')]
                    if failures:
                        raise RuntimeError(failures[-1].get('message') or failures[-1]['event']['message'])
                    await expect(page.get_by_role('button', name='Send recording', exact=True)).to_be_visible(timeout=18000)
                    await page.evaluate('window.__spokenInput.start()')
                    await page.get_by_role('button', name='Send recording', exact=True).click()

                    def terminal_reply():
                        events = workspace.trace.events
                        if any(e['name'] in ('error', 'session_error') for e in events):
                            return True
                        voice = workspace.voice
                        if voice is None:
                            return True
                        # Tool responses also end; wait for the actual final spoken response and empty work.
                        ended = any(e['name'] == 'playback_end' for e in events)
                        return ended and voice.active is None and not voice.jobs and not voice.requested and voice.wanted is None

                    await wait_until(terminal_reply, 55)
                    if workspace.voice is not None:
                        await page.get_by_role('button', name='End session', exact=True).click()
                        await wait_until(lambda: workspace.voice is None, 3)
            except TimeoutError:
                report['timed_out'] = True
            finally:
                await workspace.close_voice()
                report['attempt_wall_seconds'] = round(time.monotonic() - attempt_start, 3)
                if watchdog is not None:
                    watchdog.cancel()
                    await asyncio.gather(watchdog, return_exceptions=True)
            await page.evaluate('window.__spokenInput.close()')
            await page.screenshot(path=str(output / 'after.png'))
            # These are authored integration notes, not a participant's business result.
            await page.get_by_role('button', name='View task', exact=True).click()
            responses = {
                'Conclusion': 'Automated integration run; no participant recommendation was submitted.',
                'Evidence and rationale': 'Actual API and tool records were collected. Human interpretation and listening remain pending.',
                'Where did the compared categories come from?': 'Historical chart 1, version 3, was explicitly selected before the request.',
                'Which region, dates and measure produced the displayed values?': 'Inspect the recorded final source for each chart; this authored note does not certify the explanation.',
            }
            for label, value in responses.items():
                await page.get_by_label(label, exact=True).fill(value)
            await page.get_by_role('button', name='Save response', exact=True).click()
            await expect(page.get_by_role('button', name='Response saved', exact=True)).to_be_visible()
            await page.get_by_role('button', name='Close panel', exact=True).click()
            await page.get_by_role('button', name='Finish task', exact=True).click()
            await expect(page.locator('.trial-review')).to_be_visible()
            await page.screenshot(path=str(output / 'report.png'))
            report.update(summarize(workspace, initial, workspace.report))
            report['checks']['one_attempt_within_sixty_seconds'] = report['attempt_wall_seconds'] <= 60
            report['checks']['no_browser_errors'] = not errors
            report['status'] = 'passed' if all(report['checks'].values()) else 'failed'
            report['errors'] = [redact(e['event']['message']) for e in workspace.trace.events if e['name'] == 'error']
            report['errors'] += [redact(e['message']) for e in workspace.trace.events if e['name'] == 'session_error']
            report['session_directory'] = str(workspace.trace.directory)
            await context.close()
            await browser.close()
            browser = None
    except Exception as error:
        report.update(status='failed', error=redact(error))
        if workspace is not None:
            await workspace.close_voice()
        if attempt_start is not None and 'attempt_wall_seconds' not in report:
            report['attempt_wall_seconds'] = round(time.monotonic() - attempt_start, 3)
        # Playwright has closed the browser on leaving its context. Keep the
        # pre-attempt screenshot and original transport error; do not mask it.
    finally:
        if watchdog is not None:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)
        if workspace is not None:
            report['errors'] = [redact(e.get('message') or e['event']['message'])
                                for e in workspace.trace.events if e['name'] in ('session_error', 'error')]
            report['provider_connected'] = any(e['name'] == 'voice_connected' for e in workspace.trace.events)
            if workspace.session.get('assignment') and workspace.session['trial_status'] != 'finished':
                await workspace.finish('timeout' if budget_ended.is_set() else 'abandoned')
            if initial is not None and 'checks' not in report:
                report.update(summarize(workspace, initial, workspace.report))
            report['session_directory'] = str(workspace.trace.directory)
            workspace.trace.finalize_audio()
            workspace.trace.save('session.json', workspace.export())
        if browser is not None:
            await browser.close()
        server.should_exit = True
        await running
        report['browser_errors'] = errors


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-real', action='store_true', help='Explicitly open one real provider connection; never retry.')
    parser.add_argument('--env-file', type=Path, help='Explicit project credential file; read only with --run-real.')
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend/dist')
    parser.add_argument('--port', type=int, default=8067)
    args = parser.parse_args()
    output = ROOT / 'traces/live-browser' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    report = {'status': 'preparing', 'api_attempted': False, 'automatic_retries': 0,
              'input_mode': 'push_to_talk', 'condition': 'bound_revision', 'task_id': 'exp_01_a',
              'scope': 'One authored real realtime API check with offline TTS supplied as a browser microphone MediaStream.',
              'human_listening': 'pending', 'not_established': ['Physical microphone behavior',
                'Overlap or full-duplex interaction benefit', 'Human interpretation or method effectiveness']}
    try:
        path, duration = prepare_speech(output)
        report.update(prompt=PROMPT, offline_speech_seconds=duration,
                      offline_speech_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if args.run_real:
            await run(args, output, path, report)
        else:
            report.update(status='prepared', paid_api_calls=0,
                          next_step='Only --run-real loads credentials and opens a provider connection.')
    except Exception as error:
        report.update(status='failed', error=str(error))
    finally:
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'status': report['status'], 'api_attempted': report['api_attempted'],
                          'report': str(output / 'report.json')}))
    if report['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
