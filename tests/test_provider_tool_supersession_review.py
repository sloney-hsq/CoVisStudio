"""Local native-turn ordering regressions, without a model connection."""
import asyncio
import json

import pytest

from backend.providers import QwenRealtime


@pytest.mark.parametrize('call_count', [1, 2])
@pytest.mark.parametrize('old_status', ['superseded', 'committed'])
def test_new_input_waits_for_inflight_tool_receipt_and_quarantines_old_result(call_count, old_status):
    async def run():
        entered, release, receipt_sent, ack = (asyncio.Event() for _ in range(4))
        wire, events, executed = [], [], []

        async def emit(event):
            events.append(event)

        async def execute(*args, **kwargs):
            executed.append(args)
            entered.set()
            await release.wait()
            return {'status': old_status, 'committed': old_status == 'committed',
                    'revision': 99, 'secret_old_rows': [99]}

        client = QwenRealtime({}, 'live_voice', [], emit, execute)

        class Socket:
            async def send(self, text):
                event = json.loads(text)
                wire.append(event)
                if event['type'] == 'conversation.item.create':
                    receipt_sent.set()
                    await ack.wait()
                    await client._handle({'type': 'conversation.item.created', 'item': event['item']})

        client.ws = Socket()
        client.active = 'old'
        client.response_epochs['old'] = client.epoch
        call = {'type': 'function_call', 'name': 'edit_charts', 'arguments': '{}', 'call_id': 'c1'}
        await client._handle({'type': 'response.done', 'response': {
            'id': 'old', 'status': 'completed', 'output': [dict(call, call_id=f'c{i}') for i in range(call_count)]}})
        await entered.wait()
        await client._speech_started('new')
        await client._handle({'type': 'conversation.item.input_audio_transcription.completed',
                              'item_id': 'new', 'transcript': 'Use MG instead.'})
        assert not any(e['type'] == 'response.create' for e in wire), 'New response dispatched before old tool receipt'
        release.set()
        await asyncio.wait_for(receipt_sent.wait(), 1)
        output = json.loads(wire[-1]['item']['output'])
        assert output['status'] == 'superseded'
        assert 'secret_old_rows' not in output
        assert output['committed'] == (old_status == 'committed')
        if old_status == 'committed':
            assert output['revision'] == 99
            assert 'Already committed' in output['message']
        else:
            assert 'revision' not in output
        assert not any(e['type'] == 'response.create' for e in wire)
        ack.set()
        await asyncio.gather(*client.jobs)
        assert [e['type'] for e in wire] == ['conversation.item.create'] * call_count + ['response.create']
        assert len(executed) == 1
        if call_count == 2:
            remaining = json.loads(wire[1]['item']['output'])
            assert remaining['committed'] is False
            assert 'Not executed' in remaining['message']
        assert not client.draining

    asyncio.run(run())
