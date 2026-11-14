"""Qwen transports. The application owns chart state and commit permission.

No connection is opened at import time. Tests use local HTTP/WebSocket peers.
"""

import asyncio
from collections import deque
from copy import deepcopy
import json
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from websockets.asyncio.client import connect


class QwenText:
    def __init__(self, settings):
        self.settings = settings

    async def run(self, messages, tools, on_event, execute_tool):
        """Stream a text turn and its tool continuations; cancellation closes HTTP."""
        history = deepcopy(messages)
        async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
            for _ in range(8):
                prepared = await on_event({'type': 'response_prepare', 'transport': 'http'})
                if isinstance(prepared, dict) and 'instructions' in prepared:
                    system_message = next(message for message in history if message['role'] == 'system')
                    system_message['content'] = prepared['instructions']
                body = {
                    "model": self.settings["text_model"], "messages": history,
                    "tools": tools, "stream": True,
                    "stream_options": {"include_usage": True},
                }
                wire_text = json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
                audit = {'type': 'provider_input', 'transport': 'http', 'input_id': uuid4().hex,
                         'wire_text': wire_text, 'payload': deepcopy(body)}
                await on_event({**audit, 'status': 'attempted'})
                await on_event({"type": "provider_event", "direction": "sent", "event": body})
                content, calls, finish_reason = "", {}, None
                rid = "text-" + uuid4().hex
                call_context = await on_event({"type": "response_start", "response_id": rid})
                async with client.stream(
                    "POST", self.settings["text_url"], content=wire_text.encode('utf-8'),
                    headers={"Authorization": "Bearer " + self.settings["api_key"], "Content-Type": "application/json"},
                ) as response:
                    await on_event({**audit, 'status': 'sent'})
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        await on_event({"type": "provider_event", "direction": "received", "event": chunk})
                        if chunk.get("usage"):
                            await on_event({"type": "usage", "usage": chunk["usage"], "response_id": rid})
                        if not chunk.get("choices"):
                            continue
                        choice = chunk["choices"][0]
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        delta = choice["delta"]
                        if delta.get("content"):
                            content += delta["content"]
                            await on_event({"type": "assistant_delta", "text": delta["content"], "response_id": rid})
                        for item in delta.get("tool_calls", []):
                            call = calls.setdefault(item["index"], {
                                "id": "", "type": "function", "function": {"name": "", "arguments": ""},
                            })
                            if item.get("id"):
                                call["id"] = item["id"]
                            for field in ("name", "arguments"):
                                call["function"][field] += item.get("function", {}).get(field, "")
                await on_event({"type": "assistant_done", "text": content, "response_id": rid})
                status = "completed" if finish_reason in ("stop", "tool_calls") else "incomplete"
                await on_event({"type": "response_end", "response_id": rid, "status": status})
                if status == "incomplete":
                    await on_event({"type": "request_settled", "response_id": rid, "status": "failed"})
                    raise RuntimeError("Qwen ended this response before completion.")
                if not calls:
                    await on_event({"type": "request_settled", "response_id": rid, "status": "completed"})
                    return {"text": content, "messages": history + [{"role": "assistant", "content": content}]}
                ordered_calls = [calls[i] for i in sorted(calls)]
                history.append({"role": "assistant", "content": content or None, "tool_calls": ordered_calls})
                for index, call in enumerate(ordered_calls):
                    function = call["function"]
                    result = await _execute(execute_tool, function["name"], function["arguments"], on_event,
                                            {**call_context, "call_id": call["id"]} if call_context is not None else None)
                    if result.get("status") == "superseded":
                        return {"text": content, "messages": history, "status": "superseded"}
                    history.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
                    if result.get("status") in ("failed", "error"):
                        for remaining in ordered_calls[index + 1:]:
                            history.append({"role": "tool", "tool_call_id": remaining["id"],
                                "content": json.dumps({"status": "not_executed", "committed": False,
                                    "message": "Not executed: an earlier tool in this batch failed."})})
                        await on_event({"type": "request_settled", "response_id": rid, "status": "failed"})
                        return {"text": content, "messages": history, "status": "failed"}
            raise RuntimeError("The assistant reached the eight-round tool limit.")


async def _execute(callback, name, arguments, on_event=None, call_context=None):
    """Malformed model arguments are one failed tool receipt, not a transport failure."""
    try:
        values = json.loads(arguments)
    except json.JSONDecodeError as error:
        message = "Tool arguments are not valid JSON: " + error.msg
        if on_event is not None:
            await on_event({"type": "tool_failed", "tool": name, "arguments": arguments, "message": message, **(call_context or {})})
        return {"status": "error", "message": message}
    if call_context is not None:
        return await callback(name, values, call_context=call_context)
    return await callback(name, values)


class QwenRealtime:
    def __init__(self, settings, mode, tools, on_event, execute_tool):
        self.settings, self.mode, self.tools = settings, mode, tools
        self.on_event, self.execute_tool = on_event, execute_tool
        self.ws = None
        self.receiver = None
        self.closed = False
        self.epoch = 0
        self.active = None
        self.draining = set()
        self.requested = deque()
        self.wanted = None
        self.response_epochs = {}
        self.response_contexts = {}
        self.request_contexts = {}
        self.item_epochs = {}
        self.speech_items = {}
        self.speech_failed = False
        self.response_started_since_speech = False
        self.transcript_epoch = None
        self.calls = {}
        self.jobs = set()
        self.audio_open = False
        self.pending_image = None
        self.sent_image_frame = None
        self.instructions = ""
        self.tool_receipts = {}
        self.call_contexts = {}
        self.manual_commits = deque()
        self.close_task = None

    async def connect(self, context):
        self.instructions = context
        url = self.settings["realtime_url"]
        separator = "&" if "?" in url else "?"
        self.ws = await connect(
            url + separator + urlencode({"model": self.settings["realtime_model"]}),
            additional_headers={"Authorization": "Bearer " + self.settings["api_key"]},
            open_timeout=15, close_timeout=2, max_size=None, proxy=None,
        )
        turn_detection = None if self.mode == "push_to_talk" else {
            "type": "server_vad", "threshold": 0.55, "silence_duration_ms": 600,
            "create_response": False, "interrupt_response": False,
        }
        await self._send({"type": "session.update", "session": {
            "modalities": ["text", "audio"], "instructions": context,
            "audio": {
                "input": {"format": {"type": "pcm", "sample_rate": 16000}},
                "output": {"format": {"type": "pcm", "sample_rate": 24000}, "voice": self.settings["voice"]},
            },
            "input_audio_transcription": {"model": "qwen3-asr-flash-realtime"},
            "turn_detection": turn_detection, "tools": self.tools,
        }})
        try:
            async with asyncio.timeout(15):
                while True:
                    event = await self._read()
                    if event["type"] == "session.updated":
                        acknowledged = event["session"].get("turn_detection")
                        if self.mode == "live_voice" and (
                            acknowledged is None or acknowledged.get("create_response") is not False
                            or acknowledged.get("interrupt_response") is not False
                        ):
                            raise RuntimeError("Qwen did not acknowledge application-controlled voice responses.")
                        if self.mode == "push_to_talk" and acknowledged is not None:
                            raise RuntimeError("Qwen did not acknowledge manual voice submission.")
                        break
        except BaseException:
            await self.ws.close()
            raise
        self.receiver = asyncio.create_task(self._receive())

    async def _send(self, event, context=None):
        if context is None and event.get('response_id') is not None:
            rid = event['response_id']
            context = {**(self.response_contexts.get(rid) or {}), 'response_id': rid}
        event = {"event_id": uuid4().hex, **event}
        wire_text = json.dumps(event)
        audit = {'type': 'provider_input', 'transport': 'websocket', 'input_id': event['event_id'],
                 'wire_text': wire_text, 'payload': deepcopy(event),
                 **({'context': deepcopy(context)} if context is not None else {})}
        await self.on_event({**audit, 'status': 'attempted'})
        await self.ws.send(wire_text)
        await self.on_event({**audit, 'status': 'sent'})
        await self.on_event({"type": "provider_event", "direction": "sent", "event": event,
                             **({'context': context} if context is not None else {})})

    async def _read(self):
        event = json.loads(await self.ws.recv())
        context = self.call_contexts.get(event.get('call_id', event.get('item', {}).get('call_id')))
        await self.on_event({"type": "provider_event", "direction": "received", "event": event,
                             **({'context': context} if context is not None else {})})
        if event["type"] == "error":
            raise RuntimeError("Qwen: " + event["error"]["message"])
        return event

    async def audio(self, pcm_b64):
        if not self.audio_open and self.mode == "push_to_talk":
            await self._speech_started(None)
        self.audio_open = True
        await self.on_event({'type': 'audio_input', 'data': pcm_b64, 'mode': self.mode})
        await self._send({"type": "input_audio_buffer.append", "audio": pcm_b64},
                         context={} if self.mode == 'live_voice' else None)
        if self.pending_image is not None:
            frame, self.pending_image = self.pending_image, None
            await self._send_image(*frame)

    async def _send_image(self, jpeg_b64, frame_id):
        if frame_id is not None and frame_id == self.sent_image_frame:
            return
        await self._send({"type": "input_image_buffer.append", "image": jpeg_b64})
        self.sent_image_frame = frame_id
        await self.on_event({"type": "image_delivery", "status": "sent", "frame_id": frame_id})

    async def image(self, jpeg_b64, frame_id=None):
        # Delivery to the buffer is not evidence of model consumption or inspection.
        if frame_id is not None and frame_id == self.sent_image_frame:
            return
        if self.audio_open:
            await self._send_image(jpeg_b64, frame_id)
        else:
            self.pending_image = (jpeg_b64, frame_id)
            await self.on_event({"type": "image_delivery", "status": "queued", "frame_id": frame_id})

    async def commit(self):
        if self.mode != "push_to_talk":
            raise ValueError("Live voice uses provider VAD; manual commit belongs to push-to-talk.")
        await self.on_event({"type": "speech_end", "item_id": None})
        self.manual_commits.append(self.epoch)
        await self._send({"type": "input_audio_buffer.commit"})
        self.audio_open = False

    async def context(self, text):
        self.instructions = text
        await self._send({"type": "session.update", "session": {"instructions": text}})

    async def cancel(self):
        """Revoke pending tool/voice delivery; already committed chart state stays."""
        self.epoch += 1
        self.wanted = None
        self.speech_items.clear()
        self.speech_failed = False
        if self.active is not None:
            await self._send({"type": "response.cancel", "response_id": self.active})

    async def _speech_started(self, item_id, **offsets):
        # VAD fragments before assistant delivery remain one continuing utterance.
        if self.response_started_since_speech:
            self.speech_items.clear()
            self.speech_failed = False
        self.response_started_since_speech = False
        self.transcript_epoch = None
        if item_id is not None:
            self.speech_items[item_id] = None
        self.epoch += 1
        self.wanted = None
        if item_id is not None:
            self.item_epochs[item_id] = self.epoch
        # Revoke Workspace permissions and stop local playback before network I/O.
        await self.on_event({"type": "speech_start", "item_id": item_id, **offsets})
        if self.active is not None and self.active not in self.draining:
            await self._send({"type": "response.cancel", "response_id": self.active})

    async def _request_response(self, epoch):
        if not self.closed and epoch == self.epoch:
            self.wanted = epoch
            await self._dispatch()

    async def _dispatch(self):
        if self.wanted is None or self.active is not None or self.requested or self.draining or self.closed:
            return
        epoch, self.wanted = self.wanted, None
        prepared = await self.on_event({'type': 'response_prepare', 'transport': 'websocket', 'provider_epoch': epoch})
        if self.closed or epoch != self.epoch:
            return
        self.requested.append(epoch)
        context = {key: value for key, value in (prepared or {}).items()
                   if key in ('request_id', 'epoch', 'item_id')}
        self.request_contexts[epoch] = context
        await self._send({"type": "response.create"}, context=context)

    async def _finish_transcription(self):
        if self.transcript_epoch != self.epoch or any(text is None for text in self.speech_items.values()):
            return
        item_ids = list(self.speech_items)
        if self.speech_failed:
            self.speech_items.clear()
            self.speech_failed = False
            await self.on_event({'type': 'error', 'item_id': item_ids[-1], 'item_ids': item_ids,
                'message': 'Qwen could not transcribe this utterance. No response was requested.'})
            return
        text = ' '.join(text.strip() for text in self.speech_items.values() if text.strip())
        await self.on_event({'type': 'user_transcript', 'text': text, 'item_id': item_ids[-1], 'item_ids': item_ids})
        if text:
            await self._request_response(self.epoch)

    def _current(self, rid):
        return not self.closed and self.response_epochs.get(rid) == self.epoch

    async def _receive(self):
        try:
            while not self.closed:
                await self._handle(await self._read())
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self.closed:
                await self.on_event({"type": "error", "message": str(error)})
                await self.close()
                await self.on_event({"type": "transport_closed", "reason": "error"})

    async def _handle(self, event):
        kind = event["type"]
        if kind == "input_audio_buffer.speech_started":
            await self._speech_started(event["item_id"], audio_start_ms=event.get("audio_start_ms"))
        elif kind == "input_audio_buffer.speech_stopped":
            await self.on_event({"type": "speech_end", "item_id": event["item_id"], "audio_end_ms": event.get("audio_end_ms")})
        elif kind == "input_audio_buffer.committed":
            if self.mode == "push_to_talk":
                self.item_epochs[event["item_id"]] = self.manual_commits.popleft()
            else:
                self.audio_open = False
        elif kind == "conversation.item.input_audio_transcription.completed":
            item_id = event["item_id"]
            epoch = self.item_epochs.pop(item_id, self.epoch)
            if self.mode == "live_voice" and item_id in self.speech_items:
                self.speech_items[item_id] = event["transcript"]
                await self.on_event({"type": "user_transcript_fragment", "text": event["transcript"],
                                     "item_id": item_id, "provider_epoch": epoch})
                # An earlier ASR may arrive after the next onset. Keep it as input,
                # but only the latest fragment can authorize the current response.
                if epoch == self.epoch:
                    self.transcript_epoch = epoch
                await self._finish_transcription()
            elif epoch == self.epoch:
                await self.on_event({"type": "user_transcript", "text": event["transcript"], "item_id": item_id})
                if event["transcript"].strip():
                    await self._request_response(epoch)
        elif kind == "conversation.item.input_audio_transcription.failed":
            item_id = event['item_id']
            epoch = self.item_epochs.pop(item_id, None)
            if self.mode == 'live_voice' and item_id in self.speech_items:
                self.speech_items[item_id] = ''
                self.speech_failed = True
                self.wanted = None
                if epoch == self.epoch:
                    self.transcript_epoch = epoch
                await self._finish_transcription()
            elif epoch == self.epoch:
                await self.on_event({'type': 'error', 'item_id': item_id,
                    'message': 'Qwen could not transcribe this utterance. No response was requested.'})
        elif kind == "conversation.item.created" and event["item"]["type"] == "function_call_output":
            future = self.tool_receipts.pop(event["item"]["call_id"], None)
            self.call_contexts.pop(event['item']['call_id'], None)
            if future is not None:
                future.set_result(None)
        elif kind == "response.created":
            rid = event["response"]["id"]
            self.active = rid
            self.response_epochs[rid] = self.requested.popleft()
            self.response_contexts[rid] = self.request_contexts.pop(self.response_epochs[rid], {})
            if self._current(rid):
                self.response_started_since_speech = True
                self.response_contexts[rid] = await self.on_event({"type": "response_start", "response_id": rid})
            elif self.speech_items:
                # New native audio may already be committed. Cancelling this late
                # creation would strand a tool turn after that real new input.
                self.draining.add(rid)
                await self.on_event({"type": "stale_response_draining", "response_id": rid})
            else:
                await self._send({"type": "response.cancel", "response_id": rid})
        elif kind == "response.done":
            response = event["response"]
            rid = response["id"]
            if self.active == rid:
                self.active = None
            if response.get("usage"):
                await self.on_event({"type": "usage", "usage": response["usage"], "response_id": rid})
            calls = self.calls.pop(rid, {})
            for item in response.get("output", []):
                if item["type"] == "function_call":
                    calls[item["call_id"]] = item
            if rid in self.draining:
                job = asyncio.create_task(self._finish_stale_turn(rid, list(calls.values())))
                self.jobs.add(job)
                job.add_done_callback(self.jobs.discard)
            if self._current(rid):
                if calls and response["status"] == "completed":
                    # The native turn remains open until its tool receipts land.
                    self.draining.add(rid)
                await self.on_event({"type": "response_end", "response_id": rid, "status": response["status"]})
                if calls and response["status"] == "completed":
                    job = asyncio.create_task(self._run_tools(rid, list(calls.values())))
                    self.jobs.add(job)
                    job.add_done_callback(self.jobs.discard)
                elif not self.wanted and not self.requested:
                    await self.on_event({"type": "request_settled", "response_id": rid,
                                         "status": "completed" if response["status"] == "completed" else "failed"})
            await self._dispatch()
        elif kind.startswith("response."):
            rid = event.get("response_id")
            if not self._current(rid):
                return
            if kind in ("response.text.delta", "response.audio_transcript.delta"):
                await self.on_event({"type": "assistant_delta", "text": event["delta"], "response_id": rid})
            elif kind in ("response.text.done", "response.audio_transcript.done"):
                await self.on_event({"type": "assistant_done", "text": event.get("text", event.get("transcript", "")), "response_id": rid})
            elif kind == "response.audio.delta":
                await self.on_event({"type": "audio", "data": event["delta"], "response_id": rid, "sample_rate": 24000,
                                     "item_id": event.get("item_id"), "content_index": event.get("content_index")})
            elif kind == "response.audio.done":
                await self.on_event({"type": "audio_end", "response_id": rid,
                                     "item_id": event.get("item_id"), "content_index": event.get("content_index")})
            elif kind == "response.function_call_arguments.done":
                self.calls.setdefault(rid, {})[event["call_id"]] = event

    async def _send_tool_receipt(self, rid, call, result):
        future = asyncio.get_running_loop().create_future()
        self.tool_receipts[call['call_id']] = future
        context = {**(self.response_contexts.get(rid) or {}), 'response_id': rid, 'call_id': call['call_id']}
        self.call_contexts[call['call_id']] = context
        await self._send({'type': 'conversation.item.create', 'item': {
            'type': 'function_call_output', 'call_id': call['call_id'], 'output': json.dumps(result),
        }}, context=context)
        await future

    async def _finish_stale_turn(self, rid, calls, message="Not executed: newer user speech superseded this response.", first_receipt=None, first_attempted=False):
        """Close native calls without executing or returning obsolete chart data."""
        for index, call in enumerate(calls):
            context = {**(self.response_contexts.get(rid) or {}),
                       'response_id': rid, 'call_id': call['call_id']}
            receipt = await self.on_event({'type': 'superseded_receipt', 'context': context,
                                          'execution_attempted': first_attempted and index == 0})
            if receipt is None:  # Standalone transport consumers may only observe events.
                receipt = first_receipt if index == 0 and first_receipt is not None else {
                    'status': 'superseded', 'committed': False, 'message': message}
            await self._send_tool_receipt(rid, call, receipt)
        self.draining.discard(rid)
        await self._dispatch()

    async def _run_tools(self, rid, calls):
        try:
            for index, call in enumerate(calls):
                if not self._current(rid):
                    await self._finish_stale_turn(rid, calls[index:])
                    return
                context = self.response_contexts.get(rid)
                result = await _execute(self.execute_tool, call["name"], call["arguments"], self.on_event,
                                        {**context, "call_id": call["call_id"], **({"item_id": call["item_id"]} if call.get("item_id") else {})} if context is not None else None)
                if not self._current(rid) or result.get("status") == "superseded":
                    committed_receipt = None
                    if result.get('committed'):
                        committed_receipt = {'status': 'superseded', 'committed': True,
                            'revision': result.get('revision', result.get('state', {}).get('revision')),
                            'message': 'Already committed before supersession; obsolete chart data withheld.'}
                    await self._finish_stale_turn(rid, calls[index:],
                        first_receipt=committed_receipt, first_attempted=True)
                    return
                await self._send_tool_receipt(rid, call, result)
                if result.get("status") in ("failed", "error"):
                    for remaining in calls[index + 1:]:
                        await self._send_tool_receipt(rid, remaining, {'status': 'not_executed', 'committed': False,
                            'message': 'Not executed: an earlier tool in this batch failed.'})
                    if self._current(rid):
                        await self.on_event({"type": "request_settled", "response_id": rid, "status": "failed"})
                    return
            if self._current(rid):
                await self._request_response(self.response_epochs[rid])
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if self._current(rid):
                await self.on_event({"type": "error", "message": str(error)})
                if self._current(rid):
                    await self.on_event({"type": "request_settled", "response_id": rid, "status": "failed"})
        finally:
            self.draining.discard(rid)
            await self._dispatch()

    async def close(self):
        if self.close_task is None:
            self.closed = True
            self.epoch += 1
            self.close_task = asyncio.create_task(self._close(asyncio.current_task()))
        await asyncio.shield(self.close_task)

    async def _close(self, caller):
        tasks = [task for task in self.jobs if task is not caller]
        if self.receiver is not None and self.receiver is not caller:
            tasks.append(self.receiver)
        for task in tasks:
            task.cancel()
        if self.ws is not None:
            await self.ws.close()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tool_receipts.clear()
        self.call_contexts.clear()
