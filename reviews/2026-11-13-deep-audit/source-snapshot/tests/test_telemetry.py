import asyncio
from threading import Event

from backend.app import Workspace, create_app
from backend.providers import QwenRealtime
from fastapi.testclient import TestClient
from test_workspace import local_settings


def test_single_speech_start_revokes_before_cancel_network_and_keeps_vad(tmp_path):
    async def run():
        workspace = Workspace(local_settings(tmp_path))
        workspace.accept('old question', workspace.reference)
        old_epoch = workspace.epoch
        observed = []
        async def send(event):
            observed.append(event)
        workspace.send = send
        provider = QwenRealtime({}, 'live_voice', [], workspace.provider_event, workspace.execute)
        provider.active = 'old-response'
        async def provider_send(event):
            assert workspace.epoch > old_epoch
            assert any(item['type'] == 'stop_audio' for item in observed)
        provider._send = provider_send
        await provider._handle({'type': 'input_audio_buffer.speech_started',
                                'item_id': 'item1', 'audio_start_ms': 120})
        await provider._handle({'type': 'input_audio_buffer.speech_stopped',
                                'item_id': 'item1', 'audio_end_ms': 360})
        starts = [e for e in workspace.trace.events if e['name'] == 'speech_start']
        assert len(starts) == 1
        assert starts[0]['event']['audio_start_ms'] == 120
        assert starts[0]['item_id'] == 'item1'
        ends = [e for e in workspace.trace.events if e['name'] == 'speech_end']
        assert ends[0]['event']['audio_end_ms'] == 360
        request_id = starts[0]['request_id']
        await workspace.provider_event({'type': 'user_transcript', 'text': 'new question', 'item_id': 'item1'})
        await workspace.provider_event({'type': 'response_start', 'response_id': 'r1'})
        await workspace.provider_event({'type': 'response_start', 'response_id': 'r2'})
        assert workspace.trace.responses['r1']['request_id'] == request_id
        assert workspace.trace.responses['r2']['request_id'] == request_id
    asyncio.run(run())


def test_tool_context_survives_new_utterance_while_query_runs(tmp_path):
    async def run():
        workspace = Workspace(local_settings(tmp_path))
        workspace.accept('old question', workspace.reference)
        origin = await workspace.provider_event({'type': 'response_start', 'response_id': 'r1'})
        origin['call_id'] = 'call1'
        started, finish = Event(), Event()
        prepare = workspace.store.prepare
        def blocked(*args):
            started.set()
            finish.wait(5)
            return prepare(*args)
        workspace.store.prepare = blocked
        task = asyncio.create_task(workspace.execute('set_dashboard', {'title': 'obsolete'}, call_context=origin))
        await asyncio.to_thread(started.wait, 5)
        await workspace.provider_event({'type': 'speech_start', 'item_id': 'new-item'})
        finish.set()
        result = await task
        assert result['status'] == 'superseded'
        assert workspace.store.state['title'] == 'Untitled dashboard'
        events = [event for event in workspace.trace.events if event['name'] in ('tool_started', 'tool_superseded')]
        assert len(events) == 2
        assert all(event['request_id'] == origin['request_id'] and event['call_id'] == 'call1' for event in events)
        current = await workspace.provider_event({'type': 'response_start', 'response_id': 'r2'})
        current['call_id'] = 'call2'
        workspace.store.prepare = prepare
        await workspace.execute('set_dashboard', {'title': 'current'}, call_context=current)
        events = [event for event in workspace.trace.events if event['name'] in ('tool_started', 'tool_committed', 'tool_feedback') and event.get('call_id') == 'call2']
        assert {event['name'] for event in events} == {'tool_started', 'tool_committed', 'tool_feedback'}
        assert all(event['request_id'] == current['request_id'] and event['response_id'] == 'r2' for event in events)
    asyncio.run(run())


def test_websocket_clock_exchange(tmp_path):
    app = create_app(local_settings(tmp_path))
    with TestClient(app) as client, client.websocket_connect('/ws') as socket:
        bootstrap = socket.receive_json()
        session_id = bootstrap['session']['id']
        socket.send_json({'type': 'clock_ping', 'sync_id': 's1', 'client_clock_id': 'c1',
                          'session_id': session_id, 'client_send_ms': 5})
        pong = socket.receive_json()
        assert pong['type'] == 'clock_pong'
        assert pong['session_id'] == session_id
        assert pong['sync_id'] == 's1'
        assert pong['client_send_ms'] == 5
        assert pong['server_send_ms'] >= pong['server_receive_ms']


def test_audio_forwarding_keeps_output_item_and_chunk_positions(tmp_path):
    async def run():
        workspace = Workspace(local_settings(tmp_path))
        workspace.accept('question', workspace.reference)
        sent = []
        async def send(event):
            sent.append(event)
        workspace.send = send
        await workspace.provider_event({'type': 'response_start', 'response_id': 'r1'})
        await workspace.provider_event({'type': 'audio', 'response_id': 'r1', 'data': 'AAAAAA==',
                                        'item_id': 'output-item', 'content_index': 2, 'sample_rate': 24000})
        audio = sent[-1]
        assert audio['item_id'] == 'output-item'
        assert audio['content_index'] == 2
        assert audio['sample_start'] == 0
        assert audio['sample_end'] == 2
        assert audio['chunk_id'] == workspace.trace.events[-1]['chunk_id']
        assert audio['request_id'] == workspace.trace.current['request_id']
    asyncio.run(run())


def test_explicit_revoke_stops_playback_before_provider_cancel(tmp_path):
    async def run():
        workspace = Workspace(local_settings(tmp_path))
        before = workspace.epoch
        sent = []
        async def send(event):
            sent.append(event)
        class Voice:
            async def cancel(self):
                assert workspace.epoch == before + 1
                assert sent[-1]['type'] == 'stop_audio'
        workspace.send = send
        workspace.voice = Voice()
        await workspace.revoke()
    asyncio.run(run())
