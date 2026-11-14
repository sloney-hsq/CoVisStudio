"""Exact observed VAD/cancellation ordering; local protocol checks only."""
import asyncio
import json

import pytest

from backend.providers import QwenRealtime


class Wire:
    def __init__(self, client):
        self.client = client
        self.events = []

    async def send(self, text):
        event = json.loads(text)
        self.events.append(event)
        if event['type'] == 'conversation.item.create':
            await self.client._handle({'type': 'conversation.item.created', 'item': event['item']})


def provider():
    events = []

    async def emit(event):
        events.append(event)

    async def execute(*args, **kwargs):
        raise AssertionError('No obsolete tool may execute')

    client = QwenRealtime({}, 'live_voice', [], emit, execute)
    client.ws = Wire(client)
    return client, events


async def onset(client, item):
    await client._handle({'type': 'input_audio_buffer.speech_started', 'item_id': item})


async def transcript(client, item, text):
    await client._handle({'type': 'conversation.item.input_audio_transcription.completed',
                          'item_id': item, 'transcript': text})


@pytest.mark.parametrize('tail_first', [False, True])
def test_late_first_fragment_preserved_under_latest_permission(tail_first):
    async def run():
        client, events = provider()
        await onset(client, 'first')
        first_epoch = client.epoch
        await onset(client, 'second')
        prefix = 'Use the current local top three categories by order volume in all charts.'
        tail = 'These fixed categories keep other conditions.'
        if tail_first:
            await transcript(client, 'second', tail)
            assert not client.ws.events
        await transcript(client, 'first', prefix)
        if not tail_first:
            assert not client.ws.events  # Prefix alone never requests old execution.
        if not tail_first:
            await transcript(client, 'second', tail)
        accepted = [e for e in events if e['type'] == 'user_transcript']
        assert len(accepted) == 1
        assert accepted[0]['text'] == prefix + ' ' + tail
        assert accepted[0]['item_ids'] == ['first', 'second']
        assert list(client.requested) == [client.epoch]
        assert first_epoch != client.epoch
        assert [e['type'] for e in client.ws.events] == ['response.create']
        assert len([e for e in events if e['type'] == 'speech_start']) == 2
    asyncio.run(run())


def test_late_created_tool_response_drains_before_one_current_response():
    async def run():
        client, events = provider()
        await onset(client, 'prefix')
        await transcript(client, 'prefix', 'Use the selected historical categories for charts two and three.')
        await onset(client, 'tail')
        await transcript(client, 'tail', 'Keep the current region, dates, and metrics.')
        # Actual 03-bound: newer input is committed before old response.created.
        await client._handle({'type': 'input_audio_buffer.committed', 'item_id': 'tail'})
        await client._handle({'type': 'response.created', 'response': {'id': 'late'}})
        assert 'late' in client.draining
        await client._handle({'type': 'response.audio.delta', 'response_id': 'late', 'delta': 'obsolete'})
        await client._handle({'type': 'response.audio_transcript.done', 'response_id': 'late', 'transcript': 'Obsolete success'})
        # A further natural fragment still revokes immediately, without cancelling
        # the remote turn being drained or losing the previous actual transcript.
        await onset(client, 'third')
        await transcript(client, 'third', 'Preserve the other chart.')
        call = {'type': 'function_call', 'id': 'item_G7SVZT3D9qfQjKjIE4pGz',
                'call_id': 'call_a47e868e0301478b872151e5', 'name': 'revise_analysis',
                'arguments': '{"view_ids":["v2","v3"]}'}
        await client._handle({'type': 'response.done', 'response': {'id': 'late', 'status': 'completed', 'output': [call]}})
        await asyncio.gather(*client.jobs)
        wire = client.ws.events
        assert [e['type'] for e in wire] == ['response.create', 'conversation.item.create', 'response.create']
        output = wire[1]['item']
        assert output['call_id'] == call['call_id']
        assert json.loads(output['output']) == {'status': 'superseded', 'committed': False,
            'message': 'Not executed: newer user speech superseded this response.'}
        assert list(client.requested) == [client.epoch]
        assert not client.draining
        assert not any(e['type'] in ('audio', 'assistant_done', 'response_start') for e in events)
        assert len([e for e in events if e['type'] == 'speech_start']) == 3
        assert [e for e in events if e['type'] == 'user_transcript'][-1]['text'].endswith(
            'Keep the current region, dates, and metrics. Preserve the other chart.')
    asyncio.run(run())


def test_existing_active_response_still_cancelled_at_onset():
    async def run():
        client, events = provider()
        await onset(client, 'initial')
        await transcript(client, 'initial', 'Explain the selected charts.')
        await client._handle({'type': 'response.created', 'response': {'id': 'active'}})
        await onset(client, 'revision')
        assert client.ws.events[-1]['type'] == 'response.cancel'
        assert client.ws.events[-1]['response_id'] == 'active'
        assert events[-2]['type'] == 'provider_input'  # Outbound cancellation audit.
        assert any(e['type'] == 'speech_start' and e['item_id'] == 'revision' for e in events)
        assert list(client.speech_items) == ['revision']
    asyncio.run(run())

def test_workspace_attaches_actual_fragments_to_current_request(tmp_path):
    from pathlib import Path
    from backend.app import Workspace

    async def run():
        ws = Workspace({'api_key': '', 'voice': 'Maia', 'text_model': 'local', 'realtime_model': 'local',
            'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
            'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'trace_dir': tmp_path})
        try:
            await ws.provider_event({'type': 'speech_start', 'item_id': 'prefix'})
            old_epoch = ws.epoch
            await ws.provider_event({'type': 'speech_start', 'item_id': 'tail'})
            await ws.provider_event({'type': 'user_transcript_fragment', 'item_id': 'prefix',
                                     'text': 'Use the current local top three categories.', 'provider_epoch': 1})
            await ws.provider_event({'type': 'user_transcript', 'item_id': 'tail',
                'item_ids': ['prefix', 'tail'],
                'text': 'Use the current local top three categories. Keep other conditions.'})
            assert ws.epoch > old_epoch
            assert ws.current_intent == 'Use the current local top three categories. Keep other conditions.'
            assert ws.history[-1]['content'] == ws.current_intent
            assert ws.trace.items['prefix']['request_id'] == ws.trace.current['request_id']
            assert ws.trace.items['tail']['request_id'] == ws.trace.current['request_id']
            fragment = [e for e in ws.trace.events if e['name'] == 'user_transcript_fragment'][-1]
            assert fragment['epoch'] == old_epoch  # Preserve its observed origin too.
        finally:
            ws.data.connection.close()
    asyncio.run(run())
