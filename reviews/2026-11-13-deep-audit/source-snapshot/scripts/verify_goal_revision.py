"""Local scripted voice/browser revision check; no real model or credentials.

Uses the production browser, loopback native voice transport and real Olist.
Authored transcripts and test tones do not establish recognition or semantics.
"""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback

import uvicorn
from playwright.async_api import async_playwright, expect
from websockets.asyncio.server import serve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import create_app
from backend.oracle import category_rows, numeric_rows_equal
from scripts.verify_browser_voice import tone, until, write_wav


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend/dist')
    args = parser.parse_args()
    output = args.output_dir or ROOT / 'traces/goal-optimization' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    microphone = output / 'fixture-input.wav'
    write_wav(microphone, tone(16000, 3, 330), 16000)
    report = {'status': 'running', 'paid_api_calls': 0, 'evidence_kind': 'local_scripted',
              'not_established': ['Real recognition', 'Model semantics', 'Human listening', 'Method benefit']}
    socket = None
    calls = images = input_bytes = 0
    first_started = False
    wire, tools, receipts, errors = [], [], [], []
    server = running = browser = workspace = None

    async def send(event):
        await socket.send(json.dumps(event))

    async def utterance(item, text):
        for event in (
            {'type': 'input_audio_buffer.speech_started', 'item_id': item},
            {'type': 'input_audio_buffer.speech_stopped', 'item_id': item},
            {'type': 'input_audio_buffer.committed', 'item_id': item},
            {'type': 'conversation.item.input_audio_transcription.completed', 'item_id': item, 'transcript': text},
        ):
            await send(event)

    async def peer(connection):
        nonlocal socket, calls, images, input_bytes, first_started
        socket = connection
        async for raw in connection:
            wire.append(raw.encode('utf-8'))
            event = json.loads(raw)
            kind = event['type']
            if kind == 'session.update':
                await send({'type': 'session.updated', 'session': event['session']})
            elif kind == 'input_audio_buffer.append':
                input_bytes += len(base64.b64decode(event['audio']))
            elif kind == 'input_image_buffer.append':
                images += 1
            elif kind == 'conversation.item.create':
                receipts.append(json.loads(event['item']['output']))
                await send({'type': 'conversation.item.created', 'item': event['item']})
            elif kind == 'response.create':
                calls += 1
                rid = f'local-goal-{calls}'
                await send({'type': 'response.created', 'response': {'id': rid}})
                items = []
                if calls in (1, 3):
                    payload = {'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence' if calls == 1 else 'keep_current',
                               'start': '2017-01-01', 'end': '2017-07-01' if calls == 1 else '2017-04-01'}
                    tools.append({'name': 'revise_analysis', 'arguments': payload})
                    items = [{'type': 'function_call', 'call_id': f'revise-{calls}', 'name': 'revise_analysis',
                              'arguments': json.dumps(payload)}]
                else:
                    assert calls in (2, 4, 5), calls
                    text = {2: 'The service charts now use the historical categories for the first half of 2017.',
                            4: 'The service charts now show the first quarter. MG and the historical category set are retained.',
                            5: 'I will change the service charts to the second quarter now.'}[calls]
                    await send({'type': 'response.audio_transcript.delta', 'response_id': rid, 'delta': text})
                    pcm = tone(24000, 4 if calls == 2 else .6, 440)
                    for offset in range(0, len(pcm), 12000):
                        await send({'type': 'response.audio.delta', 'response_id': rid,
                                    'delta': base64.b64encode(pcm[offset:offset + 12000]).decode()})
                    await send({'type': 'response.audio_transcript.done', 'response_id': rid, 'transcript': text})
                    await send({'type': 'response.audio.done', 'response_id': rid})
                await send({'type': 'response.done', 'response': {'id': rid, 'status': 'completed', 'output': items}})
            if input_bytes >= 6400 and images and not first_started:
                first_started = True
                await utterance('first-request', 'Use the historical categories for service charts two and three. Show the first half of 2017 and keep the current region and measures.')

    try:
        async with serve(peer, '127.0.0.1', 0) as provider:
            app = create_app({'api_key': 'local-scripted-only', 'text_model': 'local', 'realtime_model': 'local', 'voice': 'Maia',
                'text_url': 'http://127.0.0.1:9/disabled',
                'realtime_url': f'ws://127.0.0.1:{provider.sockets[0].getsockname()[1]}',
                'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'frontend_dir': args.frontend_dir,
                'trace_dir': output / 'sessions'})
            server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8074, log_level='error'))
            running = asyncio.create_task(server.serve())
            await until(lambda: server.started)
            workspace = app.state.workspace
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True, args=['--use-fake-ui-for-media-stream',
                    '--use-fake-device-for-media-stream', '--use-file-for-fake-audio-capture=' + str(microphone),
                    '--autoplay-policy=no-user-gesture-required'])
                context = await browser.new_context(viewport={'width': 2560, 'height': 1440}, device_scale_factor=1.5, permissions=['microphone'])
                page = await context.new_page()
                page.on('pageerror', lambda error: errors.append(error.stack))
                await context.request.post('http://127.0.0.1:8074/api/session', data={'mode': 'live_voice', 'condition': 'bound_revision', 'task_id': 'exp_01_a'})
                await page.goto('http://127.0.0.1:8074/', wait_until='networkidle')
                await until(lambda: any(e['name'] == 'clock_calibrated' for e in workspace.trace.events))
                for number in (2, 3):
                    await page.get_by_role('button', name=f'Select chart {number}', exact=True).click()
                await context.request.post('http://127.0.0.1:8074/api/evidence', data={'revision': 3, 'view_id': 'v1'})
                await until(lambda: workspace.reference['view_ids'] == ['v2', 'v3'] and bool(workspace.image))
                initial = workspace.store.snapshot()
                await page.get_by_role('button', name='Start speaking', exact=True).click()
                await until(lambda: any(e['name'] == 'playback_start' and e['details']['response_id'] == 'local-goal-2' for e in workspace.trace.events))
                half = workspace.store.snapshot()
                playback_start = next(e['index'] for e in workspace.trace.events if e['name'] == 'playback_start' and e['details']['response_id'] == 'local-goal-2')
                await until(lambda: any(e['name'] == 'audio_sent' and e['index'] > playback_start for e in workspace.trace.events))
                assert not any(e['name'] == 'playback_end' and e['details']['response_id'] == 'local-goal-2' for e in workspace.trace.events), 'No actual overlap'
                workspace.trace.record('local_fixture_intervention', label='Q1 revision during actual playback')
                await utterance('revision-request', 'Actually, use the first quarter instead. Keep those categories and the other conditions.')
                await until(lambda: any(e['name'] == 'playback_end' and e['details']['response_id'] == 'local-goal-4' for e in workspace.trace.events))
                quarter = workspace.store.snapshot()
                await until(lambda: {e['details']['view_id'] for e in workspace.trace.events if e['name'] == 'chart_rendered' and e['details']['revision'] == quarter['revision']} == {'v1', 'v2', 'v3'})
                await utterance('promise-only-request', 'Now use the second quarter for service charts two and three.')
                await until(lambda: any(e['name'] == 'request_outcome' and e['status'] == 'no_changes' for e in workspace.trace.events))
                await until(lambda: any(e['name'] == 'playback_end' and e['details']['response_id'] == 'local-goal-5' for e in workspace.trace.events))
                await expect(page.locator('.message.assistant').last).to_contain_text('No chart changes')
                await expect(page.locator('.message.assistant').last).not_to_contain_text('Charts updated')
                turn_receipts = await page.locator('.message .turn-receipt').all_text_contents()
                await page.get_by_role('button', name='End voice session', exact=True).click()
                await until(lambda: workspace.voice is None)
                await page.screenshot(path=str(output / 'canvas-2560-css-150percent.png'))
                await page.set_viewport_size({'width': 3840, 'height': 2160})
                await page.screenshot(path=str(output / 'canvas-3840-css.png'), scale='css')
                events = workspace.trace.events
                final = workspace.store.snapshot()
                commits = [e for e in events if e['name'] == 'tool_committed']
                outcomes = [e for e in events if e['name'] == 'request_outcome']
                speech = [e for e in events if e['name'] == 'speech_start']
                ends = {e['details']['response_id']: e['details'] for e in events if e['name'] == 'playback_end'}
                members = [row['label'] for row in workspace.snapshots[3]['views'][0]['data']['rows']]
                checks = {'single_call_edits': len(tools) == 2 and all(t['name'] == 'revise_analysis' for t in tools),
                          'two_commits_only': len(commits) == 2, 'promise_did_not_commit': final == quarter,
                          'promise_no_changes_same_request': any(e['status'] == 'no_changes' and e['request_id'] == speech[2]['request_id'] and not e['committed'] for e in outcomes),
                          'old_receipts_stay_in_old_turns': len(turn_receipts) == 3 and all('Charts 2, 3' in text for text in turn_receipts[:2]) and 'No chart changes' in turn_receipts[2],
                          'actual_overlap_stopped_audio': ends['local-goal-2']['interrupted'] and 0 < ends['local-goal-2']['played_samples'] < ends['local-goal-2']['received_samples'],
                          'worklet_cursor_evidence': all(e['timing_basis'] == 'audio_worklet_source_cursor' for e in ends.values()),
                          'current_reply_finished': not ends['local-goal-5']['interrupted'] and ends['local-goal-5']['queue_empty'],
                          'pcm_during_reply': any(e['name'] == 'audio_sent' and playback_start < e['index'] < speech[1]['index'] for e in events),
                          'actual_jpeg_input': images > 0, 'unchanged_orders_chart': initial['views'][0] == final['views'][0],
                          'no_browser_errors': not errors, 'voice_closed_recorded': any(e['name'] == 'voice_closed' for e in events)}
                for number in (2, 3):
                    for label, state, end in [('half', half, '2017-07-01'), ('quarter', quarter, '2017-04-01')]:
                        view = state['views'][number - 1]
                        expected = {**initial['views'][number - 1]['source'], 'categories': members, 'top_n': None, 'start': '2017-01-01', 'end': end}
                        checks[f'{label}_chart_{number}_source'] = view['source'] == expected
                        checks[f'{label}_chart_{number}_independent_sql'] = numeric_rows_equal(view['data']['rows'], category_rows(workspace.data, expected))
                    checks[f'chart_{number}_actual_render'] = any(e['name'] == 'chart_rendered' and e['details']['view_id'] == f'v{number}' and e['details']['revision'] == final['revision'] for e in events)
                archived = [e for e in events if e['name'] == 'model_input' and e['status'] == 'sent']
                archived_wire = [(workspace.trace.directory / e['file']).read_bytes() for e in archived]
                checks['exact_outbound_archive'] = archived_wire == wire and all(hashlib.sha256(raw).hexdigest() == e['sha256'] for raw, e in zip(archived_wire, archived))
                report.update(status='passed' if all(checks.values()) else 'failed', checks=checks, errors=errors,
                              revisions=[initial['revision'], half['revision'], quarter['revision'], final['revision']],
                              tools=tools, receipts=receipts, turn_receipts=turn_receipts, playback_ends=ends,
                              outcomes=outcomes, session_directory=str(workspace.trace.directory), input_seconds=input_bytes / 32000)
                (output / 'states.json').write_text(json.dumps({'initial': initial, 'half': half, 'quarter': quarter, 'final': final}, indent=2), encoding='utf-8')
                assert all(checks.values()), checks
                await context.close()
                await browser.close()
                browser = None
    except BaseException as error:
        report.update(status='failed', error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        if browser is not None:
            await browser.close()
        if running is not None:
            server.should_exit = True
            await running
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'status': report['status'], 'report': str(output / 'report.json'), 'paid_api_calls': 0}))


if __name__ == '__main__':
    asyncio.run(main())

