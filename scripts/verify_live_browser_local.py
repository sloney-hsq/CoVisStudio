"""Exercise the one-shot real-test harness against a local scripted peer only."""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import json
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

from websockets.asyncio.server import serve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_live_browser import prepare_speech, run
from scripts.verify_browser_voice import tone


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend/dist')
    parser.add_argument('--port', type=int, default=8067)
    parser.add_argument('--reject-handshake', action='store_true')
    options = parser.parse_args()
    output = ROOT / 'traces/live-harness-local' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    speech, duration = prepare_speech(output)
    received, responses = [], 0
    proposal_id = None

    async def peer(socket):
        nonlocal responses, proposal_id

        async def send(event):
            await socket.send(json.dumps(event))

        async for raw in socket:
            event = json.loads(raw)
            received.append(event['type'])
            if event['type'] == 'session.update':
                await send({'type': 'session.updated', 'session': event['session']})
            elif event['type'] == 'input_audio_buffer.commit':
                await send({'type': 'input_audio_buffer.committed', 'item_id': 'local-input'})
                await send({'type': 'conversation.item.input_audio_transcription.completed', 'item_id': 'local-input',
                            'transcript': 'Apply the selected historical categories to charts two and three.'})
            elif event['type'] == 'conversation.item.create':
                item = event['item']
                if item['type'] == 'function_call_output' and item['call_id'] == 'preview':
                    proposal_id = json.loads(item['output'])['proposal']['id']
                await send({'type': 'conversation.item.created', 'item': item})
            elif event['type'] == 'response.create':
                responses += 1
                rid = f'local-reply-{responses}'
                await send({'type': 'response.created', 'response': {'id': rid}})
                if responses == 1:
                    calls = [{'type': 'function_call', 'call_id': 'preview', 'name': 'preview_revision',
                              'arguments': json.dumps({'view_ids': ['v2', 'v3'], 'source_patch': {},
                                                       'member_action': 'use_evidence'})}]
                elif responses == 2:
                    calls = [{'type': 'function_call', 'call_id': 'apply', 'name': 'apply_revision',
                              'arguments': json.dumps({'proposal_id': proposal_id})}]
                else:
                    assert responses == 3
                    calls = []
                    transcript = 'The service charts now use the historical categories with current MG values.'
                    await send({'type': 'response.audio_transcript.delta', 'response_id': rid, 'delta': transcript})
                    await send({'type': 'response.audio.delta', 'response_id': rid,
                                'delta': base64.b64encode(tone(24000, .35, 440)).decode()})
                    await send({'type': 'response.audio_transcript.done', 'response_id': rid, 'transcript': transcript})
                    await send({'type': 'response.audio.done', 'response_id': rid})
                await send({'type': 'response.done', 'response': {'id': rid, 'status': 'completed', 'output': calls}})

    def reject(connection, request):
        return connection.respond(HTTPStatus.UNAUTHORIZED, 'Local verification rejection')

    async with serve(peer, '127.0.0.1', 0, process_request=reject if options.reject_handshake else None) as server:
        settings = {'api_key': 'local-only-test-value', 'text_model': 'local-scripted',
                    'realtime_model': 'local-scripted', 'voice': 'Maia',
                    'text_url': 'http://127.0.0.1:9/disabled',
                    'realtime_url': f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}',
                    'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'trace_dir': output / 'sessions'}
        result = {'status': 'running', 'api_attempted': False, 'paid_api_calls': 0, 'offline_speech_seconds': duration,
                  'evidence_kind': 'local_scripted_harness_check',
                  'scope': 'Same browser driver with offline TTS input and a scripted local provider; not real recognition.'}
        with patch('backend.settings.load_settings', return_value=settings):
            await run(SimpleNamespace(env_file=None, frontend_dir=options.frontend_dir, port=options.port),
                      output, speech, result)
        result['local_connection_attempted'] = result.pop('api_attempted')
        result['provider_event_types'] = received
        result['scripted_responses'] = responses
        if options.reject_handshake:
            result['expected_failure'] = 'HTTP 401 before any audio or image input'
        (output / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'status': result['status'], 'paid_api_calls': 0, 'report': str(output / 'report.json')}))
        if options.reject_handshake:
            assert result['status'] == 'failed' and 'HTTP 401' in result['error']
            assert result['provider_connected'] is False and result['input_seconds'] == 0
            assert result['attempt_wall_seconds'] < 10
        else:
            assert result['status'] == 'passed', result.get('error', result.get('checks'))


if __name__ == '__main__':
    asyncio.run(main())
