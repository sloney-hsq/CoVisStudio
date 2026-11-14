"""Protocol verification against local peers, never a remote model result."""

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from websockets.asyncio.server import serve

from backend.providers import QwenRealtime, QwenText


TOOLS = [{"type": "function", "function": {
    "name": "edit_charts", "description": "Edit selected charts.",
    "parameters": {"type": "object", "properties": {"view_ids": {"type": "array", "items": {"type": "string"}}}},
}}]


def settings(**changes):
    return {"api_key": "local-only-secret", "text_model": "local-text-peer", "realtime_model": "local-voice-peer",
            "voice": "Tina", **changes}


class Peer:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.events = []
        self.ws = None

    async def handler(self, ws):
        self.ws = ws
        async for message in ws:
            event = json.loads(message)
            self.events.append(event)
            if event["type"] == "session.update":
                await self.send({"type": "session.updated", "session": event["session"]})
            else:
                await self.incoming.put(event)
            if event["type"] == "conversation.item.create":
                await self.send({"type": "conversation.item.created", "item": event["item"]})

    async def send(self, event):
        await self.ws.send(json.dumps(event))

    async def next(self, kind):
        async with asyncio.timeout(3):
            while True:
                event = await self.incoming.get()
                if event["type"] == kind:
                    return event


@pytest.mark.parametrize("valid_arguments", [True, False])
def test_text_stream_tools_receipts_and_followup(valid_arguments):
    requests, emitted, executed, wire_requests = [], [], [], []
    argument_tail = 'ids":["v1"]}' if valid_arguments else 'ids":["v1"]'
    answer = "The selected chart is now a line chart." if valid_arguments else "I could not apply this edit because its tool arguments were incomplete."

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            wire_requests.append(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(json.loads(wire_requests[-1]))
            if len(requests) == 1:
                chunks = [
                    {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call1", "function": {"name": "edit_charts", "arguments": '{"view_'}}]}}]},
                    {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": argument_tail}}]}}]},
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                    {"choices": [], "usage": {"input_tokens": 12, "output_tokens": 8}},
                ]
            else:
                chunks = [{"choices": [{"delta": {"content": answer}, "finish_reason": "stop"}]}]
            encoded = ("".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def run():
        async def emit(event):
            emitted.append(event)
            if event['type'] == 'response_prepare':
                return {'instructions': f'Frozen evidence package {len(requests) + 1}'}

        async def execute(name, arguments):
            executed.append((name, arguments))
            return {"status": "committed", "revision": 2, "changed": ["v1"]}

        model = QwenText(settings(text_url=f"http://127.0.0.1:{server.server_port}/chat"))
        return await model.run([{'role': 'system', 'content': 'Initial instructions'},
                                {"role": "user", "content": "Change this chart to a line."}], TOOLS, emit, execute)

    try:
        result = asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    receipt = json.loads((requests[1]["messages"][-1] if valid_arguments else result["messages"][-1])["content"])
    failures = [event for event in emitted if event["type"] == "tool_failed"]
    if valid_arguments:
        assert executed == [("edit_charts", {"view_ids": ["v1"]})]
        assert receipt["revision"] == 2
        assert failures == []
    else:
        assert executed == []
        assert receipt["status"] == "error"
        assert len(failures) == 1
        assert failures[0]["tool"] == "edit_charts"
        assert failures[0]["arguments"] == '{"view_ids":["v1"]'
        assert failures[0]["message"] == receipt["message"]
    assert result["messages"][-2 if valid_arguments else -1]["tool_call_id"] == "call1"
    assert len(requests) == (2 if valid_arguments else 1)
    assert requests[0]['messages'][0]['content'] == 'Frozen evidence package 1'
    if valid_arguments:
        assert requests[1]['messages'][0]['content'] == 'Frozen evidence package 2'
    if valid_arguments:
        assert [message['role'] for message in requests[1]['messages']] == ['system', 'user', 'assistant', 'tool']
    assert result["text"] == (answer if valid_arguments else "")
    settled = [event for event in emitted if event["type"] == "request_settled"]
    assert len(settled) == 1
    assert settled[0]["status"] == ("completed" if valid_arguments else "failed")
    assert any(event["type"] == "usage" for event in emitted)
    assert "local-only-secret" not in json.dumps(emitted)
    audits = [event for event in emitted if event['type'] == 'provider_input']
    assert [event['status'] for event in audits] == ['attempted', 'sent'] * (2 if valid_arguments else 1)
    assert [event['wire_text'].encode('utf-8') for event in audits if event['status'] == 'sent'] == wire_requests


def test_manual_voice_audio_image_tools_and_single_followup():
    async def run():
        peer, events, executed = Peer(), [], []

        async def emit(event):
            events.append(event)

        async def execute(name, arguments):
            executed.append((name, arguments))
            return {"status": "committed", "revision": len(executed)}

        async with serve(peer.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f"ws://127.0.0.1:{port}"), "push_to_talk", TOOLS, emit, execute)
            await client.connect("Use the selected visible chart. Respond in English.")
            assert peer.events[0]["session"]["turn_detection"] is None
            assert peer.events[0]["session"]["tools"] == TOOLS
            await client.image("jpeg-frame")
            await client.audio("AQACAA==")
            await peer.next("input_image_buffer.append")
            assert [item["type"] for item in peer.events][1:3] == ["input_audio_buffer.append", "input_image_buffer.append"]
            assert sum(event["type"] == "speech_start" for event in events) == 1
            await client.commit()
            await peer.next("input_audio_buffer.commit")
            await peer.send({"type": "input_audio_buffer.committed", "item_id": "u1"})
            await peer.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "u1", "transcript": "Change both charts."})
            await peer.next("response.create")
            await peer.send({"type": "response.created", "response": {"id": "r1"}})
            calls = [
                {"type": "function_call", "call_id": "a", "name": "edit_charts", "arguments": '{"view_ids":["v1"]}'},
                {"type": "function_call", "call_id": "b", "name": "edit_charts", "arguments": '{"view_ids":["v2"]}'},
            ]
            await peer.send({"type": "response.function_call_arguments.done", "response_id": "r1", **calls[0], "type": "response.function_call_arguments.done"})
            await peer.send({"type": "response.done", "response": {"id": "r1", "status": "completed", "output": calls, "usage": {"total_tokens": 20}}})
            await peer.next("response.create")
            assert not any(event["type"] == "request_settled" for event in events)
            assert len(executed) == 2
            assert len([event for event in peer.events if event["type"] == "response.create"]) == 2
            assert len([event for event in peer.events if event["type"] == "conversation.item.create"]) == 2
            await peer.send({"type": "response.created", "response": {"id": "r2"}})
            await peer.send({"type": "response.audio_transcript.delta", "response_id": "r2", "delta": "Both updated."})
            await peer.send({"type": "response.audio.delta", "response_id": "r2", "delta": "AQACAA=="})
            await peer.send({"type": "response.audio_transcript.done", "response_id": "r2", "transcript": "Both updated."})
            await peer.send({"type": "response.done", "response": {"id": "r2", "status": "completed", "output": []}})
            async with asyncio.timeout(3):
                while not any(event["type"] == "response_end" and event["response_id"] == "r2" for event in events):
                    await asyncio.sleep(0.005)
            assert [event for event in events if event["type"] == "request_settled"] == [
                {"type": "request_settled", "response_id": "r2", "status": "completed"}]
            assert any(event["type"] == "audio" and event["data"] == "AQACAA==" for event in events)
            await client.close()
            assert client.receiver.done()
            assert "local-only-secret" not in json.dumps(events)

    asyncio.run(run())


@pytest.mark.parametrize('failure', ['failed', 'error', 'malformed_arguments'])
def test_voice_failed_receipt_stops_batch_without_automatic_continuation(failure):
    async def run():
        peer, events, executed = Peer(), [], []

        async def emit(event):
            events.append(event)

        async def execute(name, arguments):
            executed.append(arguments['view_ids'][0])
            if arguments['view_ids'] == ['v1']:
                return {'status': 'completed', 'committed': True, 'revision': 1}
            return {'status': failure, 'committed': False, 'message': 'Invalid evidence type.'}

        async with serve(peer.handler, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f'ws://127.0.0.1:{port}'),
                                  'push_to_talk', TOOLS, emit, execute)
            await client.connect('Edit the selected charts.')
            try:
                await client.audio('AQACAA==')
                await client.commit()
                await peer.send({'type': 'input_audio_buffer.committed', 'item_id': 'u1'})
                await peer.send({'type': 'conversation.item.input_audio_transcription.completed',
                                 'item_id': 'u1', 'transcript': 'Edit the charts.'})
                await peer.next('response.create')
                await peer.send({'type': 'response.created', 'response': {'id': 'r1'}})
                calls = [{'type': 'function_call', 'call_id': view_id, 'name': 'edit_charts',
                          'arguments': json.dumps({'view_ids': [view_id]})}
                         for view_id in ('v1', 'v2', 'v3')]
                if failure == 'malformed_arguments':
                    calls[1]['arguments'] = '{'
                await peer.send({'type': 'response.done', 'response': {
                    'id': 'r1', 'status': 'completed', 'output': calls}})
                receipts = [(await peer.next('conversation.item.create'))['item'] for _ in range(2)]
                async with asyncio.timeout(3):
                    while client.jobs:
                        await asyncio.sleep(.005)
                assert executed == (['v1'] if failure == 'malformed_arguments' else ['v1', 'v2'])
                assert [item['call_id'] for item in receipts] == ['v1', 'v2']
                assert json.loads(receipts[0]['output'])['committed'] is True
                assert json.loads(receipts[1]['output'])['status'] == ('error' if failure == 'malformed_arguments' else failure)
                assert not client.tool_receipts  # Both outputs were acknowledged.
                assert sum(event['type'] == 'response.create' for event in peer.events) == 1
                assert client.wanted is None and not client.requested
                assert [event for event in events if event["type"] == "request_settled"] == [
                    {"type": "request_settled", "response_id": "r1", "status": "failed"}]
            finally:
                await client.close()

    asyncio.run(run())


def test_live_speech_interrupts_inflight_tool_without_obsolete_result_or_audio():
    async def run():
        peer, events = Peer(), []
        started, release, interrupted = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def emit(event):
            events.append(event)
            if event["type"] == "speech_start" and event["item_id"] == "u2":
                interrupted.set()

        async def execute(name, arguments):
            started.set()
            await release.wait()
            return {"status": "committed", "revision": 1}

        async with serve(peer.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f"ws://127.0.0.1:{port}"), "live_voice", TOOLS, emit, execute)
            await client.connect("English dashboard collaboration.")
            assert peer.events[0]["session"]["turn_detection"]["create_response"] is False
            await client.audio("AQACAA==")
            await peer.send({"type": "input_audio_buffer.speech_started", "item_id": "u1"})
            await peer.send({"type": "input_audio_buffer.committed", "item_id": "u1"})
            await peer.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "u1", "transcript": "Change the date."})
            await peer.next("response.create")
            await peer.send({"type": "response.created", "response": {"id": "r1"}})
            await peer.send({"type": "response.done", "response": {"id": "r1", "status": "completed", "output": [
                {"type": "function_call", "call_id": "a", "name": "edit_charts", "arguments": '{"view_ids":["v1"]}'},
            ]}})
            await asyncio.wait_for(started.wait(), 3)
            await peer.send({"type": "input_audio_buffer.speech_started", "item_id": "u2"})
            await asyncio.wait_for(interrupted.wait(), 3)
            await peer.send({"type": "response.audio.delta", "response_id": "r1", "delta": "obsolete"})
            release.set()
            await asyncio.gather(*client.jobs)
            await peer.send({"type": "input_audio_buffer.committed", "item_id": "u2"})
            await peer.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "u2", "transcript": "Actually keep the first quarter."})
            await peer.next("response.create")
            receipts = [event['item'] for event in peer.events if event['type'] == 'conversation.item.create']
            assert len(receipts) == 1
            assert json.loads(receipts[0]['output'])['status'] == 'superseded'
            assert 'revision' not in json.loads(receipts[0]['output'])
            assert not any(event["type"] == "audio" for event in events)
            assert len([event for event in peer.events if event["type"] == "response.create"]) == 2
            await client.close()

    asyncio.run(run())


def test_cancel_pending_response_rejects_its_late_creation_and_output():
    async def run():
        peer, events = Peer(), []

        async def emit(event):
            events.append(event)

        async def execute(*_):
            raise AssertionError("Cancelled response must not execute a tool")

        async with serve(peer.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f"ws://127.0.0.1:{port}"), "push_to_talk", TOOLS, emit, execute)
            await client.connect("English.")
            await client.audio("AQACAA==")
            await client.commit()
            await peer.send({"type": "input_audio_buffer.committed", "item_id": "u1"})
            await peer.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "u1", "transcript": "Change the color."})
            await peer.next("response.create")
            await client.cancel()
            await peer.send({"type": "response.created", "response": {"id": "old"}})
            cancel = await peer.next("response.cancel")
            assert cancel["response_id"] == "old"
            await peer.send({"type": "response.audio.delta", "response_id": "old", "delta": "obsolete"})
            await peer.send({"type": "response.done", "response": {"id": "old", "status": "cancelled", "output": []}})
            await client.context("The public chart remains unchanged.")
            await asyncio.sleep(0.01)
            assert not any(event["type"] in ("audio", "response_start") for event in events)
            await client.close()

    asyncio.run(run())


def test_manual_response_contract_must_be_acknowledged():
    async def run():
        async def wrong_ack(ws):
            await ws.recv()
            await ws.send(json.dumps({"type": "session.updated", "session": {"turn_detection": {"type": "server_vad"}}}))
            await ws.wait_closed()

        async def emit(_):
            pass

        async def execute(*_):
            pass

        async with serve(wrong_ack, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f"ws://127.0.0.1:{port}"), "live_voice", TOOLS, emit, execute)
            try:
                await client.connect("English.")
            except RuntimeError as error:
                assert "acknowledge" in str(error)
            else:
                raise AssertionError("An uncontrolled response session was accepted")
            assert client.receiver is None

    asyncio.run(run())


def test_cancel_before_manual_commit_ack_does_not_revive_cancelled_utterance():
    async def run():
        peer, events = Peer(), []

        async def emit(event):
            events.append(event)

        async def execute(*_):
            raise AssertionError("Cancelled input must not request tools")

        async with serve(peer.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f"ws://127.0.0.1:{port}"), "push_to_talk", TOOLS, emit, execute)
            await client.connect("English.")
            await client.audio("AQACAA==")
            await client.commit()
            await peer.next("input_audio_buffer.commit")
            await client.cancel()
            await peer.send({"type": "input_audio_buffer.committed", "item_id": "cancelled"})
            await peer.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "cancelled", "transcript": "Wrong earlier request."})
            await client.audio("AQACAA==")
            await client.commit()
            await peer.next("input_audio_buffer.commit")
            await peer.send({"type": "input_audio_buffer.committed", "item_id": "current"})
            await peer.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "current", "transcript": "Keep the first quarter."})
            await peer.next("response.create")
            transcripts = [event["text"] for event in events if event["type"] == "user_transcript"]
            assert transcripts == ["Keep the first quarter."]
            assert len([event for event in peer.events if event["type"] == "response.create"]) == 1
            await client.close()

    asyncio.run(run())


def test_image_delivery_records_actual_send_and_waits_for_next_manual_audio():
    async def run():
        peer, events = Peer(), []

        async def emit(event):
            events.append(event)

        async def execute(*_):
            raise AssertionError('This test sends visual context only.')

        async with serve(peer.handler, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f'ws://127.0.0.1:{port}'),
                                  'push_to_talk', TOOLS, emit, execute)
            await client.connect('Read the visible chart.')
            await client.image('initial-jpeg', 'image-r6')
            assert [event for event in events if event['type'] == 'image_delivery'] == [
                {'type': 'image_delivery', 'status': 'queued', 'frame_id': 'image-r6'}]
            assert not any(event['type'] == 'input_image_buffer.append' for event in peer.events)
            await client.audio('AQACAA==')
            assert (await peer.next('input_image_buffer.append'))['image'] == 'initial-jpeg'
            await client.commit()
            await peer.next('input_audio_buffer.commit')
            await client.image('updated-jpeg', 'image-r7')
            # A post-commit screenshot has not been sent, much less inspected.
            deliveries = [event for event in events if event['type'] == 'image_delivery']
            assert [(event['status'], event['frame_id']) for event in deliveries] == [
                ('queued', 'image-r6'), ('sent', 'image-r6'), ('queued', 'image-r7')]
            assert sum(event['type'] == 'input_image_buffer.append' for event in peer.events) == 1
            await client.audio('AwAEAA==')
            assert (await peer.next('input_image_buffer.append'))['image'] == 'updated-jpeg'
            deliveries = [event for event in events if event['type'] == 'image_delivery']
            assert deliveries[-1] == {'type': 'image_delivery', 'status': 'sent', 'frame_id': 'image-r7'}
            assert sum(event['type'] == 'input_audio_buffer.append' for event in peer.events) == 2
            assert not any(event['type'] == 'response.create' for event in peer.events)
            assert all('image' not in event for event in deliveries)
            await client.close()

    asyncio.run(run())


@pytest.mark.parametrize('failure', ['provider_error', 'connection_closed'])
def test_voice_transport_failure_notifies_workspace_after_resources_close(failure):
    async def run():
        peer, events = Peer(), []
        closed = asyncio.Event()

        async def emit(event):
            events.append(event)
            if event['type'] == 'transport_closed':
                assert client.closed
                assert not client.jobs
                closed.set()

        async def execute(*_):
            raise AssertionError('No tool is expected.')

        async with serve(peer.handler, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = QwenRealtime(settings(realtime_url=f'ws://127.0.0.1:{port}'),
                                  'live_voice', TOOLS, emit, execute)
            await client.connect('Read the visible chart.')
            if failure == 'provider_error':
                await peer.send({'type': 'error', 'error': {'message': 'Authored provider rejection.'}})
            else:
                await peer.ws.close()
            await asyncio.wait_for(closed.wait(), 3)
            await client.receiver
            assert sum(event['type'] == 'error' for event in events) == 1
            assert sum(event['type'] == 'transport_closed' for event in events) == 1
            assert events[-1] == {'type': 'transport_closed', 'reason': 'error'}
            assert client.receiver.done()

    asyncio.run(run())


@pytest.mark.parametrize('from_receiver', [False, True])
def test_concurrent_close_waits_for_one_complete_cleanup(from_receiver):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class Socket:
            count = 0
            async def close(self):
                self.count += 1
                entered.set()
                await release.wait()
        async def emit(_):
            pass
        client = QwenRealtime({}, 'live_voice', [], emit, None)
        client.ws = Socket()
        first = asyncio.create_task(client.close())
        if from_receiver:
            client.receiver = first
        await entered.wait()
        second = asyncio.create_task(client.close())
        await asyncio.sleep(0)
        assert not first.done() and not second.done()
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert client.ws.count == 1
        assert not first.cancelled()
    asyncio.run(run())


def test_plain_voice_promise_settles_without_implying_tool_execution():
    async def run():
        events = []
        async def emit(event):
            events.append(event)
        client = QwenRealtime({}, 'live_voice', [], emit, None)
        client.response_epochs['promise'] = client.epoch
        client.active = 'promise'
        await client._handle({'type': 'response.done', 'response': {
            'id': 'promise', 'status': 'completed', 'output': []}})
        assert events == [
            {'type': 'response_end', 'response_id': 'promise', 'status': 'completed'},
            {'type': 'request_settled', 'response_id': 'promise', 'status': 'completed'}]
        await client.cancel()
        await client._handle({'type': 'response.done', 'response': {
            'id': 'promise', 'status': 'completed', 'output': []}})
        assert len(events) == 2
    asyncio.run(run())



def test_tool_execution_exception_settles_failed_without_followup():
    async def run():
        events = []
        async def emit(event):
            events.append(event)
        async def execute(*_):
            raise RuntimeError('Local execution failed.')
        client = QwenRealtime({}, 'live_voice', [], emit, execute)
        client.response_epochs['tool'] = client.epoch
        await client._run_tools('tool', [{'name': 'edit_charts', 'arguments': '{}', 'call_id': 'a'}])
        assert events == [
            {'type': 'error', 'message': 'Local execution failed.'},
            {'type': 'request_settled', 'response_id': 'tool', 'status': 'failed'}]
        assert client.wanted is None and not client.requested
    asyncio.run(run())
