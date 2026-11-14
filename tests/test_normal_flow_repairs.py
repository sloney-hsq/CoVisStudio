"""Reproduced normal-flow races and provenance; no remote model connection."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.app import Workspace
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


@pytest.mark.parametrize('failed_item', ['first', 'second'])
@pytest.mark.parametrize('failure_first', [False, True])
def test_fragment_group_failure_never_accepts_partial_request_and_next_utterance_works(failed_item, failure_first):
    async def run():
        events = []
        async def emit(event):
            events.append(event)
        client = QwenRealtime({}, 'live_voice', [], emit, None)
        client.ws = Wire(client)
        await client._speech_started('first')
        await client._speech_started('second')
        failed = {'type': 'conversation.item.input_audio_transcription.failed', 'item_id': failed_item}
        succeeded = {'type': 'conversation.item.input_audio_transcription.completed',
                     'item_id': 'second' if failed_item == 'first' else 'first', 'transcript': 'Keep other conditions.'}
        for event in ([failed, succeeded] if failure_first else [succeeded, failed]):
            await client._handle(event)
        assert not any(event['type'] == 'user_transcript' for event in events)
        assert not client.ws.events
        assert client.wanted is None and not client.speech_items and not client.item_epochs
        errors = [event for event in events if event['type'] == 'error']
        assert len(errors) == 1 and errors[0]['item_ids'] == ['first', 'second']
        await client._speech_started('next')
        await client._handle({'type': 'conversation.item.input_audio_transcription.completed',
                             'item_id': 'next', 'transcript': 'Show category orders.'})
        assert [event['text'] for event in events if event['type'] == 'user_transcript'] == ['Show category orders.']
        assert [event['type'] for event in client.ws.events] == ['response.create']
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['failed', 'malformed'])
def test_failed_tool_batch_closes_remaining_calls_without_execution_or_followup(failure):
    async def run():
        events, executed = [], []
        async def emit(event):
            events.append(event)
        async def execute(name, args):
            executed.append(name)
            return {'status': 'failed' if name == 'b' else 'completed', 'committed': name == 'a'}
        client = QwenRealtime({}, 'live_voice', [], emit, execute)
        client.ws = Wire(client)
        client.response_epochs['response'] = client.epoch
        client.draining.add('response')
        calls = [{'name': name, 'call_id': name, 'arguments': '{' if name == 'b' and failure == 'malformed' else '{}'}
                 for name in ('a', 'b', 'c')]
        await client._run_tools('response', calls)
        receipts = [event['item'] for event in client.ws.events]
        assert [item['call_id'] for item in receipts] == ['a', 'b', 'c']
        assert executed == (['a'] if failure == 'malformed' else ['a', 'b'])
        assert json.loads(receipts[-1]['output'])['status'] == 'not_executed'
        assert not client.tool_receipts and not client.draining and not client.requested
        assert [event for event in events if event['type'] == 'request_settled'] == [
            {'type': 'request_settled', 'response_id': 'response', 'status': 'failed'}]
    asyncio.run(run())


@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    ws = Workspace({'api_key': '', 'text_model': 'offline', 'realtime_model': 'offline', 'voice': 'Maia',
                    'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
                    'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
                    'trace_dir': tmp_path_factory.mktemp('normal-flow-repairs')})
    yield ws
    ws.data.close()


def test_user_apply_rechecks_permission_after_waiting_for_voice_cancel(workspace):
    async def run():
        ws = workspace
        ws.reset('live_voice', 'starter', '')
        before = ws.store.snapshot()
        preview = await ws.preview_revision({'view_ids': ['v2', 'v3'], 'source_patch': {'region': 'MG'},
                                            'member_action': 'keep_current'}, actor='user')
        entered, release = asyncio.Event(), asyncio.Event()
        class Voice:
            async def cancel(self):
                entered.set()
                await release.wait()
        ws.voice = Voice()
        try:
            apply = asyncio.create_task(ws.apply_revision(preview['proposal']['id'], actor='user'))
            await entered.wait()
            await ws.provider_event({'type': 'speech_start', 'item_id': 'new-question'})
            release.set()
            result = await asyncio.wait_for(apply, 1)
            assert result == {'status': 'superseded', 'committed': False}
            assert ws.store.snapshot() == before
            assert ws.proposal['status'] == 'superseded' and ws.prepared_revision is None
        finally:
            ws.voice = None
    asyncio.run(run())


def test_concurrent_close_waits_during_pending_proposal_notification(workspace):
    async def run():
        ws = workspace
        ws.reset('live_voice', 'starter', '')
        await ws.preview_revision({'view_ids': ['v2'], 'source_patch': {'region': 'MG'},
                                   'member_action': 'keep_current'}, actor='user')
        notice_entered, release_notice, close_entered, release_close = (asyncio.Event() for _ in range(4))
        class Voice:
            closes = 0
            async def close(self):
                self.closes += 1
                close_entered.set()
                await release_close.wait()
        voice = ws.voice = Voice()
        original_send = ws.send
        async def send(event):
            if event['type'] == 'proposal':
                notice_entered.set()
                await release_notice.wait()
        ws.send = send
        try:
            first = asyncio.create_task(ws.close_voice())
            await notice_entered.wait()
            second = asyncio.create_task(ws.close_voice())
            await asyncio.sleep(0)
            assert ws.voice is None and ws.voice_closing is not None
            assert not second.done()
            release_notice.set()
            await close_entered.wait()
            third = asyncio.create_task(ws.close_voice())
            await asyncio.sleep(0)
            assert not any(task.done() for task in (first, second, third))
            release_close.set()
            await asyncio.wait_for(asyncio.gather(first, second, third), 1)
            assert voice.closes == 1 and ws.voice_closing is None
            assert len([event for event in ws.trace.events if event['name'] == 'voice_closed']) == 1
        finally:
            ws.send = original_send
    asyncio.run(run())


@pytest.mark.parametrize('mode', ['push_to_talk', 'live_voice'])
def test_input_audio_belongs_to_ptt_onset_or_unassigned_live_stream(workspace, mode):
    async def run():
        ws = workspace
        ws.reset(mode, None, '')
        ws.epoch += 1
        ws.accept('Earlier request.', ws.reference)
        old_request = ws.trace.current['request_id']
        client = QwenRealtime({}, mode, [], ws.provider_event, ws.execute)
        client.ws = Wire(client)
        await client.audio('AQACAA==')
        block = next(event for event in ws.trace.events if event['name'] == 'audio_sent')
        assert block['stream_id'] == ws.session['id']
        if mode == 'push_to_talk':
            onset = next(event for event in ws.trace.events if event['name'] == 'speech_start')
            assert onset['index'] < block['index']
            assert block['request_id'] == onset['request_id'] != old_request
        else:
            assert 'request_id' not in block
    asyncio.run(run())


def test_delayed_render_records_commit_owner_and_current_observer_separately(workspace):
    async def run():
        ws = workspace
        ws.reset('text', 'starter', '')
        await ws.revoke()
        ws.accept('Change the title.', ws.reference)
        origin = await ws.provider_event({'type': 'response_start', 'response_id': 'old'})
        result = await ws.execute('set_dashboard', {'title': 'Updated title'}, call_context=origin)
        await ws.revoke()
        ws.accept('A newer question.', ws.reference)
        newer = ws.trace.current['request_id']
        event = ws.record_browser_event({'name': 'chart_rendered', 'client_ms': 123,
            'details': {'revision': result['state']['revision'], 'view_id': 'v1'}})
        assert event['request_id'] == origin['request_id'] != newer
        assert event['observation_request_id'] == newer and event['client_ms'] == 123
        evidence = ws.evidence_store._items[-1]
        assert evidence['source_request_id'] == origin['request_id']
    asyncio.run(run())


def test_superseded_native_receipts_and_cancel_keep_original_request(workspace):
    async def run():
        ws = workspace
        ws.reset('live_voice', None, '')
        await ws.provider_event({'type': 'speech_start', 'item_id': 'old-input'})
        origin = await ws.provider_event({'type': 'response_start', 'response_id': 'old-response'})
        client = QwenRealtime({}, 'live_voice', [], ws.provider_event, ws.execute)
        client.ws = Wire(client)
        client.response_contexts['old-response'] = origin
        await ws.provider_event({'type': 'speech_start', 'item_id': 'new-input'})
        await client._send({'type': 'response.cancel', 'response_id': 'old-response'})
        await client._finish_stale_turn('old-response', [{'call_id': 'old-call'}])
        records = [event for event in ws.trace.events if event['name'] == 'model_input']
        assert len(records) == 4
        assert all(event['request_id'] == origin['request_id'] for event in records)
        assert all(event['call_id'] == 'old-call' for event in records[-2:])
        raw_receipt = [event for event in ws.trace.events if event['name'] == 'provider_event'][-1]
        assert raw_receipt['request_id'] == origin['request_id'] and raw_receipt['call_id'] == 'old-call'
    asyncio.run(run())


def test_late_created_response_receipt_keeps_context_captured_before_new_speech(workspace):
    async def run():
        ws = workspace
        ws.reset('live_voice', None, '')
        client = QwenRealtime({}, 'live_voice', [], ws.provider_event, ws.execute)
        client.ws = Wire(client)
        await client._speech_started('first')
        await client._handle({'type': 'conversation.item.input_audio_transcription.completed',
                             'item_id': 'first', 'transcript': 'Show the orders.'})
        original = deepcopy(ws.trace.current)
        await client._speech_started('second')
        await client._handle({'type': 'conversation.item.input_audio_transcription.completed',
                             'item_id': 'second', 'transcript': 'Use the first quarter.'})
        await client._handle({'type': 'response.created', 'response': {'id': 'late'}})
        await client._handle({'type': 'response.done', 'response': {'id': 'late', 'status': 'completed',
            'output': [{'type': 'function_call', 'name': 'set_dashboard', 'call_id': 'late-call',
                        'arguments': '{"title":"Old"}'}]}})
        await asyncio.gather(*client.jobs)
        receipts = [event for event in ws.trace.events if event['name'] == 'model_input' and event.get('call_id') == 'late-call']
        assert len(receipts) == 2
        assert all(event['request_id'] == original['request_id'] != ws.trace.current['request_id'] for event in receipts)
        assert ws.store.state['revision'] == 0
        assert [event['type'] for event in client.ws.events] == [
            'response.create', 'conversation.item.create', 'response.create']
    asyncio.run(run())


def test_journey_uses_applied_candidate_evidence_instead_of_selected_evidence(workspace):
    async def run():
        ws = workspace
        ws.reset('text', 'starter', '')
        await ws.choose_evidence({'revision': ws.store.state['revision'], 'view_id': 'v1'})
        ws.bound_evidence = deepcopy(ws.evidence)
        result = await ws.execute('revise_analysis', {'view_ids': ['v2'], 'member_action': 'use_evidence',
            'candidate_id': f"chart:{ws.store.state['revision']}:v3"})
        assert result['committed']
        assert result['node']['evidence'] == result['node']['revision_card']['evidence']
        assert result['node']['evidence']['view_id'] == 'v3'
        assert ws.bound_evidence['view_id'] == 'v1'
    asyncio.run(run())


def test_voice_context_retains_recent_received_discussion(workspace):
    ws = workspace
    ws.reset('text', None, '')
    ws.history = [{'role': 'user' if index % 2 == 0 else 'assistant', 'content': f'Option {index}'}
                  for index in range(16)]
    context = json.loads(ws.context())
    assert context['recent_conversation'] == ws.history[-12:]
    assert context['conversation_evidence'] == 'received_text_not_proof_of_listening'
