"""Assigned direct/bound trials through real browser I/O and a local native peer.

The provider decisions, transcript and tones are authored fixtures, not model or
participant evidence. The actual adapters, Olist tools, rendering and playback
are exercised. This script never reads credentials or contacts a hosted API.
"""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import uvicorn
from playwright.async_api import async_playwright, expect
from websockets.asyncio.server import serve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import create_app
from backend.experiment import aggregate_reports
from scripts.verify_browser_voice import tone, until, write_wav


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend' / 'dist')
    parser.add_argument('--port', type=int, default=8064)
    args = parser.parse_args()
    output = ROOT / 'traces' / 'assigned-voice' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    report = {'status': 'running', 'paid_api_calls': 0, 'cases': [],
              'scope': 'Actual assigned browser task, native realtime adapter, local scripted provider and real Olist.',
              'not_established': ['Real recognition or model reasoning', 'Human listening or interpretation',
                                  'Method effectiveness', 'Natural participant behavior',
                                  'Visual inspection of the updated chart before the spoken reply']}
    microphone_file = output / 'fixture-microphone.wav'
    write_wav(microphone_file, tone(16000, 3, 330), 16000)
    output_pcm = tone(24000, .8, 440)
    write_wav(output / 'fixture-assistant.wav', output_pcm, 24000)
    peer_records, console_errors = [], []
    active_condition = 'direct'
    workspace = None
    server = running = browser = page = None

    async def peer(socket):
        condition = active_condition
        record = {'condition': condition, 'events': [], 'receipts': [], 'images': []}
        peer_records.append(record)
        connection_start = time.monotonic()
        response_count = input_bytes = 0
        utterance_started = False
        history = saved_set = proposal = None

        async def send(event):
            await socket.send(json.dumps(event))

        try:
            async for raw in socket:
                event = json.loads(raw)
                kind = event['type']
                logged = json.loads(raw)
                if kind == 'input_audio_buffer.append':
                    pcm = base64.b64decode(event['audio'])
                    input_bytes += len(pcm)
                    logged['audio'] = {'bytes': len(pcm), 'sha256': hashlib.sha256(pcm).hexdigest()}
                elif kind == 'input_image_buffer.append':
                    jpeg = base64.b64decode(event['image'])
                    filename = f'{condition}-provider-frame-{len(record["images"]) + 1:02d}.jpg'
                    (output / filename).write_bytes(jpeg)
                    record['images'].append(filename)
                    logged['image'] = {'file': filename, 'bytes': len(jpeg), 'sha256': hashlib.sha256(jpeg).hexdigest()}
                record['events'].append(logged)
                if kind == 'session.update':
                    await send({'type': 'session.updated', 'session': event['session']})
                elif kind == 'conversation.item.create':
                    item = event['item']
                    if item['type'] == 'function_call_output':
                        receipt = json.loads(item['output'])
                        record['receipts'].append(receipt)
                        assert receipt['status'] == 'completed', receipt
                        if item['call_id'] == 'read-history':
                            history = receipt['result']
                        elif item['call_id'] == 'prepare':
                            if condition == 'direct':
                                saved_set = receipt['result']['category_set']
                            else:
                                proposal = receipt['proposal']
                    await send({'type': 'conversation.item.created', 'item': item})
                elif kind == 'response.create':
                    response_count += 1
                    rid = f'{condition}-response-{response_count}'
                    await send({'type': 'response.created', 'response': {'id': rid}})
                    if response_count == 1:
                        name, payload, call_id = 'read_history', {'revision': 3}, 'read-history'
                    elif response_count == 2:
                        # The complete historical chart is obtained through the public tool.
                        source = next(view for view in history['views'] if view['number'] == 1)
                        evidence = {'revision': history['revision'], 'view_id': source['id']}
                        if condition == 'direct':
                            name, payload = 'save_category_set', {'name': 'Original RJ priorities', **evidence}
                        else:
                            name, payload = 'preview_revision', {'evidence': evidence, 'view_ids': ['v2', 'v3'],
                                'source_patch': {}, 'member_action': 'use_evidence', 'needs_confirmation': False}
                        call_id = 'prepare'
                    elif response_count == 3:
                        if condition == 'direct':
                            name, payload = 'apply_category_set', {'set_id': saved_set['id'], 'view_ids': ['v2', 'v3']}
                        else:
                            name, payload = 'apply_revision', {'proposal_id': proposal['id']}
                        call_id = 'apply'
                    else:
                        assert response_count == 4
                        text = 'The two service charts now use the original RJ categories, with current MG values. The orders chart is unchanged.'
                        await send({'type': 'response.audio_transcript.delta', 'response_id': rid, 'delta': text})
                        for index in range(0, len(output_pcm), 4800):
                            await send({'type': 'response.audio.delta', 'response_id': rid,
                                        'delta': base64.b64encode(output_pcm[index:index + 4800]).decode()})
                            await asyncio.sleep(.035)
                        await send({'type': 'response.audio_transcript.done', 'response_id': rid, 'transcript': text})
                        await send({'type': 'response.audio.done', 'response_id': rid})
                    calls = [] if response_count == 4 else [{'type': 'function_call', 'name': name,
                            'arguments': json.dumps(payload), 'call_id': call_id}]
                    await send({'type': 'response.done', 'response': {'id': rid, 'status': 'completed', 'output': calls}})
                if record['images'] and input_bytes >= 6400 and not utterance_started:
                    utterance_started = True
                    item_id = f'{condition}-user-1'
                    await send({'type': 'input_audio_buffer.speech_started', 'item_id': item_id})
                    await send({'type': 'input_audio_buffer.speech_stopped', 'item_id': item_id})
                    await send({'type': 'input_audio_buffer.committed', 'item_id': item_id})
                    await send({'type': 'conversation.item.input_audio_transcription.completed', 'item_id': item_id,
                                'transcript': 'Use the original RJ priorities in these two service charts. Keep the current MG scope and leave orders unchanged.'})
        finally:
            record.update(connection_seconds=round(time.monotonic() - connection_start, 3),
                          input_audio_seconds=round(input_bytes / 32000, 3), response_count=response_count)

    async def close_panel():
        await page.get_by_role('button', name='Close panel', exact=True).click()
        await expect(page.get_by_role('dialog')).to_have_count(0)

    try:
        assert (args.frontend_dir / 'index.html').exists()
        async with serve(peer, '127.0.0.1', 0) as provider:
            provider_port = provider.sockets[0].getsockname()[1]
            app = create_app({'frontend_dir': args.frontend_dir, 'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
                'trace_dir': output / 'sessions', 'api_key': 'local-scripted-peer-only',
                'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': f'ws://127.0.0.1:{provider_port}',
                'text_model': 'local-scripted-text', 'realtime_model': 'local-scripted-voice', 'voice': 'Maia'})
            server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='error'))
            running = asyncio.create_task(server.serve())
            await until(lambda: server.started)
            workspace = app.state.workspace
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True, args=[
                    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
                    '--use-file-for-fake-audio-capture=' + str(microphone_file),
                    '--autoplay-policy=no-user-gesture-required'])
                context = await browser.new_context(viewport={'width': 2560, 'height': 1440}, device_scale_factor=1.5,
                    permissions=['microphone'], record_video_dir=str(output / 'video'))
                page = await context.new_page()
                page.on('pageerror', lambda error: console_errors.append(str(error)))
                await page.goto(f'http://127.0.0.1:{args.port}/', wait_until='networkidle')
                for condition, slot in [('direct', 1), ('bound_revision', 5)]:
                    active_condition = condition
                    await page.get_by_role('button', name='Experiment', exact=True).click()
                    await page.get_by_label('Experiment participant', exact=True).fill(f'fixture-voice-{condition}')
                    await page.get_by_label('Allocation slot', exact=True).fill(str(slot))
                    await page.get_by_role('button', name='Load assignment', exact=True).click()
                    await page.get_by_role('button', name='Assigned task 1', exact=True).click()
                    await page.get_by_role('button', name='Prepare assigned task 1', exact=True).click()
                    await expect(page.get_by_role('button', name='Begin task', exact=True)).to_be_visible()
                    assert workspace.session['assignment']['condition'] == condition
                    assert workspace.session['assignment']['task_id'] == 'exp_01_a'
                    assert workspace.voice is None
                    await page.get_by_role('button', name='Begin task', exact=True).click()
                    await expect(page.locator('.trial-curtain')).to_have_count(0)
                    await page.get_by_role('button', name='Select chart 2', exact=True).click()
                    await page.get_by_role('button', name='Select chart 3', exact=True).click()
                    await until(lambda: workspace.reference['view_ids'] == ['v2', 'v3'] and bool(workspace.image))
                    initial = workspace.store.snapshot()
                    await page.screenshot(path=str(output / f'{condition}-before.png'))
                    await page.get_by_role('button', name='Start speaking', exact=True).click()
                    await until(lambda: any(event['name'] == 'playback_end' for event in workspace.trace.events))
                    await until(lambda: any(event['name'] == 'chart_rendered' and
                        event.get('details', {}).get('revision') == initial['revision'] + 1 for event in workspace.trace.events))
                    await page.get_by_role('button', name='End voice session', exact=True).click()
                    await until(lambda: workspace.voice is None)
                    await until(lambda: 'connection_seconds' in peer_records[-1])
                    final = workspace.store.snapshot()
                    assert final['views'][0] == initial['views'][0]
                    historical_members = {row['label'] for row in workspace.snapshots[3]['views'][0]['data']['rows']}
                    for index in (1, 2):
                        assert set(final['views'][index]['source']['categories']) == historical_members
                        assert final['views'][index]['source']['top_n'] is None
                        for key in ('region', 'start', 'end', 'status', 'metric'):
                            assert final['views'][index]['source'][key] == initial['views'][index]['source'][key]
                    await page.screenshot(path=str(output / f'{condition}-after.png'))
                    await page.get_by_role('button', name='View task', exact=True).click()
                    for label, value in {
                        'Conclusion': 'Authored protocol verification; business recommendation is pending human review.',
                        'Evidence and rationale': 'Real Olist service measures are retained. A scripted voice peer selected the historical cohort.',
                        'Where did the compared categories come from?': 'The original RJ order-volume chart in version 3.',
                        'Which region, dates and measure produced the displayed values?': 'Current MG delivered orders in 2017; low-review rate and mean delivery time.'}.items():
                        await page.get_by_label(label, exact=True).fill(value)
                    await page.get_by_role('button', name='Save response', exact=True).click()
                    await expect(page.get_by_role('button', name='Response saved', exact=True)).to_be_visible()
                    await close_panel()
                    await page.get_by_role('button', name='Finish task', exact=True).click()
                    await expect(page.locator('.trial-review')).to_be_visible()
                    trial = workspace.report['trial_report']
                    assert trial['outcome']['status'] == 'completed'
                    assert trial['outcome']['technical_completed']
                    assert trial['human_review']['status'] == 'pending'
                    assert trial['human_review']['repair_turns'] is None
                    assert trial['outcome']['business_conclusion_correct'] is None
                    events = workspace.trace.events
                    accepted = [event for event in events if event['name'] == 'request_accepted']
                    assert accepted[-1]['reference']['view_ids'] == ['v2', 'v3']
                    starts = [event for event in events if event['name'] == 'playback_start']
                    ends = [event for event in events if event['name'] == 'playback_end']
                    assert len(starts) == len(ends) == 1
                    assert ends[0]['client_ms'] > starts[0]['client_ms']
                    assert not ends[0]['details']['interrupted']
                    incoming = next(workspace.trace.directory.glob('input-*.pcm')).read_bytes()
                    outgoing = next(workspace.trace.directory.glob('output-*.pcm')).read_bytes()
                    assert any(incoming) and outgoing == output_pcm
                    record = peer_records[-1]
                    assert record['images'] and record['response_count'] == 4
                    types = [event['type'] for event in record['events']]
                    assert types.index('input_audio_buffer.append') < types.index('input_image_buffer.append')
                    assert record['input_audio_seconds'] <= 10
                    assert record['connection_seconds'] < 60
                    assert len(record['receipts']) == 3
                    tools = trial['process']['tools']['started']
                    assert tools['read_history'] == 1
                    assert tools['save_category_set' if condition == 'direct' else 'preview_revision'] == 1
                    assert tools['apply_category_set' if condition == 'direct' else 'apply_revision'] == 1
                    if condition == 'bound_revision':
                        cards = trial['process']['interaction']['revision_cards']
                        assert cards['model_applied_count'] == 1 and cards['user_confirmed_count'] == 0
                    assert trial['process']['counts']['audio_sent'] > 0 and trial['process']['counts']['image_captured'] > 0
                    assert trial['process']['counts']['playback_start'] == trial['process']['counts']['playback_end'] == 1
                    assert trial['process']['publication']['first_full_correct_revision'] == final['revision']
                    workspace.trace.finalize_audio()
                    workspace.trace.save('session.json', workspace.export())
                    (output / f'{condition}-trial.json').write_text(json.dumps(trial, indent=2), encoding='utf-8')
                    await page.screenshot(path=str(output / f'{condition}-report.png'))
                    report['cases'].append({'condition': condition, 'task_id': 'exp_01_a', 'slot': slot,
                        'status': 'passed', 'session_directory': str(workspace.trace.directory),
                        'initial_revision': initial['revision'], 'final_revision': final['revision'],
                        'selected_view_ids': accepted[-1]['reference']['view_ids'], 'tools': tools,
                        'input_audio_seconds': record['input_audio_seconds'], 'connection_seconds': record['connection_seconds'],
                        'playback_client_ms': round(ends[0]['client_ms'] - starts[0]['client_ms'], 3),
                        'technical_completed': True, 'human_review': 'pending'})
                    await close_panel()
                assert not console_errors, console_errors
                aggregate = aggregate_reports([json.loads((output / f'{condition}-trial.json').read_text())
                                               for condition in ('direct', 'bound_revision')])
                (output / 'unified-report.json').write_text(json.dumps(aggregate, indent=2), encoding='utf-8')
                report.update(status='passed', assertions=['Both assigned mechanisms use the same task and exact view selection',
                    'Actual PCM precedes browser JPEG delivery', 'Public history informs registered tool calls',
                    'Actual tool receipts precede the scripted assistant reply', 'Real Olist commit and canvas render agree',
                    'Actual WebAudio start/end recorded', 'Unified report keeps human judgments pending',
                    'Every voice input below ten seconds; connections below sixty seconds', 'No browser errors'])
                await context.close()
                await browser.close()
                browser = None
    except BaseException as error:
        report.update(status='failed', error=str(error), traceback=traceback.format_exc())
        if page is not None and not page.is_closed():
            await page.screenshot(path=str(output / 'failure.png'))
        raise
    finally:
        if browser is not None:
            await browser.close()
        if server is not None:
            server.should_exit = True
        if running is not None:
            await running
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (output / 'provider-events.json').write_text(json.dumps(peer_records, indent=2), encoding='utf-8')
        (output / 'console-errors.json').write_text(json.dumps(console_errors, indent=2), encoding='utf-8')
        print(json.dumps({'status': report['status'], 'report': str(output / 'report.json'), 'paid_api_calls': 0}))


if __name__ == '__main__':
    asyncio.run(main())
