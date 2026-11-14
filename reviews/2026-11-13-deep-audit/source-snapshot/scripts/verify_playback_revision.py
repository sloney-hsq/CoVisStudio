"""One actual browser interruption and revision with a local scripted voice peer.

This checks transport, selection, Olist commits and playback, not recognition or
model reasoning. Test-tone input/output and authored transcripts are explicit.
No credentials are loaded; the isolated server exits after preserving records.
"""
import asyncio
import argparse
import base64
import hashlib
from datetime import datetime, timezone
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
    args = parser.parse_args()
    output = args.output_dir or ROOT / 'traces' / 'playback-revision' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    microphone = output / 'fixture-input.wav'
    write_wav(microphone, tone(16000, 3, 330), 16000)
    report = {'status': 'running', 'paid_api_calls': 0, 'evidence_kind': 'local_scripted',
              'human_listening': 'pending', 'not_established': ['Real recognition', 'Model reasoning', 'Method benefit']}
    peer_socket = None
    calls = 0
    proposal_id = None
    images = input_bytes = 0
    first_utterance = False
    records, errors, received_wire = [], [], []
    server = running = browser = workspace = None

    async def send(event):
        await peer_socket.send(json.dumps(event))

    async def utterance(item, text):
        await send({'type': 'input_audio_buffer.speech_started', 'item_id': item})
        await send({'type': 'input_audio_buffer.speech_stopped', 'item_id': item})
        await send({'type': 'input_audio_buffer.committed', 'item_id': item})
        await send({'type': 'conversation.item.input_audio_transcription.completed', 'item_id': item, 'transcript': text})

    async def peer(socket):
        nonlocal peer_socket, calls, proposal_id, images, input_bytes, first_utterance
        peer_socket = socket
        async for raw in socket:
            received_wire.append(raw.encode('utf-8'))
            event = json.loads(raw)
            kind = event['type']
            records.append(kind)
            if kind == 'session.update':
                await send({'type': 'session.updated', 'session': event['session']})
            elif kind == 'input_audio_buffer.append':
                input_bytes += len(base64.b64decode(event['audio']))
            elif kind == 'input_image_buffer.append':
                images += 1
            elif kind == 'conversation.item.create':
                item = event['item']
                result = json.loads(item['output'])
                if item['call_id'].startswith('preview'):
                    proposal_id = result['proposal']['id']
                await send({'type': 'conversation.item.created', 'item': item})
            elif kind == 'response.create':
                calls += 1
                rid = f'local-revision-{calls}'
                await send({'type': 'response.created', 'response': {'id': rid}})
                if calls in (1, 4):
                    payload = {'view_ids': ['v2', 'v3'], 'source_patch': {'end': '2017-07-01' if calls == 1 else '2017-04-01'},
                               'member_action': 'use_evidence' if calls == 1 else 'keep_current'}
                    items = [{'type': 'function_call', 'call_id': f'preview-{calls}', 'name': 'preview_revision', 'arguments': json.dumps(payload)}]
                elif calls in (2, 5):
                    items = [{'type': 'function_call', 'call_id': f'apply-{calls}', 'name': 'apply_revision', 'arguments': json.dumps({'proposal_id': proposal_id})}]
                else:
                    assert calls in (3, 6)
                    items = []
                    text = ('The two service charts now use the historical categories for the first half of 2017.' if calls == 3 else
                            'The service charts now show the first quarter. MG, the historical category set and both measures are retained. The orders chart is unchanged.')
                    await send({'type': 'response.audio_transcript.delta', 'response_id': rid, 'delta': text})
                    pcm = tone(24000, 4 if calls == 3 else .6, 440)
                    # Deliver ahead of playback, as normal streaming output can do.
                    for offset in range(0, len(pcm), 12000):
                        await send({'type': 'response.audio.delta', 'response_id': rid,
                                    'delta': base64.b64encode(pcm[offset:offset + 12000]).decode()})
                    await send({'type': 'response.audio_transcript.done', 'response_id': rid, 'transcript': text})
                    await send({'type': 'response.audio.done', 'response_id': rid})
                await send({'type': 'response.done', 'response': {'id': rid, 'status': 'completed', 'output': items}})
            if input_bytes >= 6400 and images and not first_utterance:
                first_utterance = True
                await utterance('first-request', 'Use the historical categories for service charts two and three. Show the first half of 2017 and keep the current region and measures.')

    try:
        async with serve(peer, '127.0.0.1', 0) as local_provider:
            app = create_app({'api_key': 'local-scripted-only', 'text_model': 'local', 'realtime_model': 'local', 'voice': 'Maia',
                'text_url': 'http://127.0.0.1:9/disabled',
                'realtime_url': f'ws://127.0.0.1:{local_provider.sockets[0].getsockname()[1]}',
                'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'frontend_dir': ROOT / 'frontend/dist', 'trace_dir': output / 'sessions'})
            server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8069, log_level='error'))
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
                await context.request.post('http://127.0.0.1:8069/api/session', data={'mode': 'live_voice', 'condition': 'bound_revision', 'task_id': 'exp_01_a'})
                await page.goto('http://127.0.0.1:8069/', wait_until='networkidle')
                await until(lambda: any(e['name'] == 'clock_calibrated' for e in workspace.trace.events))
                await page.get_by_role('button', name='Select chart 2', exact=True).click()
                await page.get_by_role('button', name='Select chart 3', exact=True).click()
                await context.request.post('http://127.0.0.1:8069/api/evidence', data={'revision': 3, 'view_id': 'v1'})
                await until(lambda: workspace.reference['view_ids'] == ['v2', 'v3'] and bool(workspace.image))
                initial = workspace.store.snapshot()
                await page.get_by_role('button', name='Start speaking', exact=True).click()
                await until(lambda: any(e['name'] == 'playback_start' and e['details']['response_id'] == 'local-revision-3' for e in workspace.trace.events))
                playback_start = next(e['index'] for e in workspace.trace.events if e['name'] == 'playback_start' and e['details']['response_id'] == 'local-revision-3')
                await until(lambda: any(e['name'] == 'audio_sent' and e['index'] > playback_start for e in workspace.trace.events))
                # The revision is injected only after actual playback, never response.done.
                first_end = [e for e in workspace.trace.events if e['name'] == 'playback_end' and e['details']['response_id'] == 'local-revision-3']
                assert not first_end, 'No overlap: do not relabel a completed reply as an interruption.'
                workspace.trace.record('local_fixture_intervention', label='authored revision during actual playback')
                await utterance('revision-request', 'Actually, use the first quarter instead. Keep those categories and the other conditions.')
                await until(lambda: any(e['name'] == 'playback_end' and e['details']['response_id'] == 'local-revision-6' for e in workspace.trace.events))
                final = workspace.store.snapshot()
                await until(lambda: {e['details']['view_id'] for e in workspace.trace.events if e['name'] == 'chart_rendered' and e['details']['revision'] == final['revision']} == {'v1', 'v2', 'v3'})
                await expect(page.get_by_role('status', name='Actual chart action')).to_contain_text(f'Charts 2, 3 · Version {final["revision"]}')
                # Real controls cover the main plots and create a distinct expanded surface.
                await until(lambda: any(e['name'] == 'chart_visible' and e['details']['revision'] == final['revision']
                    and e['details']['view_id'] == 'v1' for e in workspace.trace.events))
                main_surface = next(e['details']['surface_id'] for e in reversed(workspace.trace.events)
                    if e['name'] == 'chart_visible' and e['details']['view_id'] == 'v1')
                expansion_index = len(workspace.trace.events)
                await page.locator('.chart-card[data-view-id="v1"]').get_by_role('button', name='Expand chart', exact=True).click()
                await until(lambda: any(e['name'] == 'chart_visible' and e['details']['surface_id'] != main_surface
                    and e['details']['view_id'] == 'v1' and e['index'] >= expansion_index for e in workspace.trace.events))
                expanded_surface = next(e['details']['surface_id'] for e in workspace.trace.events
                    if e['name'] == 'chart_visible' and e['details']['surface_id'] != main_surface
                    and e['details']['view_id'] == 'v1' and e['index'] >= expansion_index)
                await page.get_by_role('button', name='Close expanded chart', exact=True).click()
                await until(lambda: any(e['name'] == 'chart_visible' and e['details']['surface_id'] == main_surface
                    and e['index'] >= expansion_index for e in workspace.trace.events))
                await until(lambda: any(e['name'] == 'chart_hidden' and e['details']['surface_id'] == expanded_surface
                    and e['details']['visibility_reason'] == 'unmounted' for e in workspace.trace.events))
                await page.get_by_role('button', name='End voice session', exact=True).click()
                await until(lambda: workspace.voice is None)
                await page.screenshot(path=str(output / 'revised-canvas.png'))
                await page.get_by_role('button', name='Review & export', exact=True).click()
                delivery_review = page.get_by_role('region', name='Execution and delivery', exact=True)
                await expect(delivery_review).to_be_visible()
                await expect(delivery_review).to_contain_text('AudioWorklet receipt')
                await expect(delivery_review).to_contain_text('Word alignment unknown')
                await delivery_review.scroll_into_view_if_needed()
                await page.screenshot(path=str(output / 'delivery-review.png'))
                events = workspace.trace.events
                ends = {e['details']['response_id']: e['details'] for e in events if e['name'] == 'playback_end'}
                commits = [e for e in events if e['name'] == 'tool_committed']
                intervention = next(e['index'] for e in events if e['name'] == 'local_fixture_intervention')
                speech = [e for e in events if e['name'] == 'speech_start']
                interrupted, completed = ends['local-revision-3'], ends['local-revision-6']
                visible = [e for e in events if e['name'] == 'chart_visible']
                rendered_events = [e for e in events if e['name'] == 'chart_rendered']
                def render_precedes(exposure):
                    identity = exposure['details']
                    return any(e['name'] == 'chart_rendered' and e['index'] < exposure['index'] and
                        all(e['details'].get(key) == identity.get(key) for key in
                            ('view_id', 'revision', 'render_generation', 'surface_id')) for e in events)
                aligned = [e for e in events if e['name'] in ('playback_start', 'playback_end', 'chart_visible')
                           and e.get('client_ms') is not None and e['index'] > next(
                               e['index'] for e in events if e['name'] == 'clock_calibrated')]
                old_end_event = next(e for e in events if e['name'] == 'playback_end' and e['details']['response_id'] == 'local-revision-3')
                members = [row['label'] for row in workspace.snapshots[3]['views'][0]['data']['rows']]
                checks = {'original_audio_interrupted': ends['local-revision-3']['interrupted'],
                    'delivery_review_actual_drawer': await delivery_review.is_visible(),
                    'revised_audio_finished': not ends['local-revision-6']['interrupted'],
                    'untargeted_orders_unchanged': initial['views'][0] == final['views'][0],
                    'actual_image_input': images > 0,
                    'actual_pcm_during_reply': any(e['name'] == 'audio_sent' and playback_start < e['index'] < intervention for e in events),
                    'first_half_commit_preceded_revision': commits[0]['index'] < intervention < commits[1]['index'],
                    'two_commits_only': len(commits) == 2, 'no_browser_errors': not errors,
                    'input_below_ten_seconds': input_bytes / 32000 < 10}
                checks.update({
                    'actual_worklet_cursor_receipts': all(end.get('timing_basis') == 'audio_worklet_source_cursor'
                        and isinstance(end.get('generation_epoch'), int) for end in (interrupted, completed)),
                    'generation_changes_after_interruption': completed.get('generation_epoch', -1) > interrupted.get('generation_epoch', -1),
                    'clock_calibrated': any(e['name'] == 'clock_calibrated' for e in events),
                    'client_events_calibrated': bool(aligned) and all(e.get('aligned_server_ms') is not None and
                        e.get('calibration_id') and e.get('uncertainty_ms') is not None for e in aligned),
                    'one_speech_start_per_authored_utterance': len(speech) == 2 and
                        [e['event']['item_id'] for e in speech] == ['first-request', 'revision-request'],
                    'interruption_clips_received_audio': 0 < interrupted['played_samples'] < interrupted['received_samples'],
                    'interrupted_old_request_provenance': len(speech) == 2 and old_end_event['index'] > speech[1]['index'] and
                        interrupted['request_id'] == speech[0]['request_id'] and interrupted['epoch'] == speech[0]['epoch'] and
                        interrupted['response_id'] == 'local-revision-3' and old_end_event['request_id'] == speech[0]['request_id'],
                    'completed_new_request_provenance': len(speech) == 2 and completed['request_id'] == speech[1]['request_id'] and
                        completed['epoch'] == speech[1]['epoch'] and completed['response_id'] == 'local-revision-6',
                    'final_audio_fully_played_and_empty': completed['queue_empty'] and completed['pending_chunks'] == 0 and
                        completed['played_samples'] == completed['received_samples'] > 0,
                    'visible_only_after_matching_actual_render': bool(visible) and all(render_precedes(e) for e in visible),
                    'render_completion_timestamp_retained': bool(rendered_events) and all(
                        e['details'].get('notification_kind') in ('render_completed', 'existing_render') and
                        e['details'].get('render_completed_client_ms') == e.get('client_ms') for e in rendered_events),
                    'existing_render_replay_identified': any(e['details'].get('notification_kind') == 'existing_render'
                        for e in rendered_events),
                    'main_surface_covered_and_reshown': any(e['name'] == 'chart_hidden' and e['index'] >= expansion_index and
                        e['details']['surface_id'] == main_surface and e['details']['visibility_reason'] == 'surface_disabled' for e in events) and
                        any(e['name'] == 'chart_visible' and e['index'] >= expansion_index and e['details']['surface_id'] == main_surface for e in events),
                    'expanded_surface_closed': any(e['name'] == 'chart_hidden' and e['index'] >= expansion_index and
                        e['details']['view_id'] == 'v1' and e['details']['surface_id'] != main_surface and
                        e['details']['visibility_reason'] == 'unmounted' for e in events),
                })
                model_inputs = [e for e in events if e['name'] == 'model_input' and e['status'] == 'sent']
                archived_wire = [(workspace.trace.directory / e['file']).read_bytes() for e in model_inputs]
                checks['exact_native_model_input_files'] = bool(model_inputs) and archived_wire == received_wire and all(
                    len(wire) == event['bytes'] and hashlib.sha256(wire).hexdigest() == event['sha256']
                    for event, wire in zip(model_inputs, archived_wire))
                native = [json.loads(wire) for wire in archived_wire]
                checks['native_pcm_jpeg_tools_instructions_archived'] = all(any(
                    event['type'] == kind for event in native) for kind in (
                        'input_audio_buffer.append', 'input_image_buffer.append', 'conversation.item.create')) and any(
                    event['type'] == 'session.update' and event['session'].get('tools') and event['session'].get('instructions') for event in native)
                packages = [json.loads((workspace.trace.directory / event['file']).read_text(encoding='utf-8'))
                    for event in events if event['name'] == 'evidence_package']
                checks['evidence_dual_cutoff'] = bool(packages) and all(
                    item['available_at'] <= package['cutoff'] and item['captured_at'] + item['clock_uncertainty'] <= package['cutoff']
                    for package in packages for item in package['items'])
                checks['frozen_image_frame_hashes'] = any(item['kind'] == 'image' for package in packages for item in package['items']) and all(
                    hashlib.sha256((workspace.trace.directory / item['content']['file']).read_bytes()).hexdigest() == item['content']['sha256']
                    for package in packages for item in package['items'] if item['kind'] == 'image' and item['content'].get('file'))
                for view in final['views'][1:]:
                    expected = {**initial['views'][view['number'] - 1]['source'], 'categories': members, 'top_n': None, 'end': '2017-04-01'}
                    checks[f'chart_{view["number"]}_scope_and_members'] = view['source'] == expected
                    checks[f'chart_{view["number"]}_independent_sql'] = numeric_rows_equal(view['data']['rows'], category_rows(workspace.data, expected))
                report.update(status='passed' if all(checks.values()) else 'failed', checks=checks,
                    initial_revision=initial['revision'], final_revision=final['revision'], input_seconds=input_bytes / 32000,
                    playback_ends=ends, errors=errors, provider_event_types=records, session_directory=str(workspace.trace.directory))
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
