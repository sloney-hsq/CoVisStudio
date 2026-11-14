"""Full local application/provider loops. Scripted peers are not model results."""

import asyncio
import base64
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import socket
from threading import Event, Thread

import httpx
from PIL import Image, ImageDraw
import uvicorn
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from backend.app import create_app


EVIDENCE = Path(__file__).resolve().parents[1] / "traces" / "provider-integration"
PCM = base64.b64encode(bytes(3200)).decode()
TOOL_ARGUMENTS = {"view_ids": ["v1"], "patch": {"source": {"end": "2017-04-01"}}}


def configuration(name, text_url="http://127.0.0.1:1/not-used", realtime_url="ws://127.0.0.1:1/not-used"):
    return {"data_dir": Path("C:/VerbalVis/datasets/olist/data"), "trace_dir": EVIDENCE / name,
            "api_key": "local-integration-only", "text_model": "scripted-local-text", "realtime_model": "scripted-local-voice",
            "text_url": text_url, "realtime_url": realtime_url, "voice": "Tina"}


@asynccontextmanager
async def application(settings):
    app = create_app(settings)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    running = asyncio.create_task(server.serve(sockets=[listener]))
    async with asyncio.timeout(10):
        while not server.started:
            await asyncio.sleep(0.01)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", trust_env=False) as http:
            yield app, http, f"ws://127.0.0.1:{port}/ws"
    finally:
        server.should_exit = True
        await running


async def receive_until(browser, kind, predicate=lambda _: True):
    async with asyncio.timeout(10):
        while True:
            event = json.loads(await browser.recv())
            assert event["type"] != "error", event
            if event["type"] == kind and predicate(event):
                return event


async def seed(http):
    result = await http.post("/api/tools", json={"name": "create_chart", "arguments": {
        "title": "SP monthly orders", "chart_type": "line", "source": {
            "metric": "orders", "dimension": "month", "region": "SP", "start": "2017-01-01",
            "end": "2018-01-01", "status": "delivered", "top_n": None,
        }}})
    result.raise_for_status()
    return result.json()["state"]


def picture(state):
    """A real data-derived chart JPEG, not a captured browser-render claim."""
    image = Image.new("RGB", (640, 360), "#faf9f5")
    draw = ImageDraw.Draw(image)
    draw.text((24, 20), "SP monthly orders / Olist", fill="#172d32")
    rows = state["views"][0]["data"]["rows"]
    maximum = max(row["value"] for row in rows)
    for index, row in enumerate(rows):
        x = 26 + index * 48
        height = row["value"] / maximum * 230
        draw.rectangle((x, 300 - height, x + 30, 300), fill="#238579")
        draw.text((x, 310), row["label"][-2:], fill="#172d32")
    stream = BytesIO()
    image.save(stream, format="JPEG")
    return base64.b64encode(stream.getvalue()).decode()


def reference(state):
    return {"revision": state["revision"], "view_ids": ["v1"], "entities": {}}


def synthetic_capture_clock(app):
    """Explicit clock fixture for locally authored JPEGs; not a browser calibration measurement."""
    trace = app.state.workspace.trace
    trace.calibrations['synthetic-image-fixture'] = {
        'offset_ms': 0, 'uncertainty_ms': 0, 'calibration_id': 'synthetic-image-fixture'}
    return {'captured_client_ms': trace.now_ms(), 'client_clock_id': 'synthetic-image-fixture'}


async def acknowledge_fixture_render(browser, state, app, *, image=None, reference_snapshot=None):
    """Model the browser's render->capture reply; this is a local JPEG fixture."""
    for view in state['views']:
        await browser.send(json.dumps({'type': 'event', 'name': 'chart_rendered',
            'client_ms': app.state.workspace.trace.now_ms(), 'client_clock_id': 'synthetic-image-fixture',
            'details': {'view_id': view['id'], 'revision': state['revision'], 'fixture': True}}))
    await browser.send(json.dumps({'type': 'context', 'reference': reference(state) if reference_snapshot is None else reference_snapshot,
                                   'image': picture(state) if image is None else image, **synthetic_capture_clock(app)}))


def save_report(name, workspace, assertions):
    workspace.trace.finalize_audio()
    workspace.trace.save("integration-report.json", {
        "case": name, "validation": "local application and scripted provider protocol",
        "paid_api_calls": 0, "real_model_result": False, "human_listening": "pending",
        "assertions": assertions, "final_revision": workspace.store.state["revision"],
    })


def test_text_image_tool_commit_and_reply_through_application():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            if len(requests) == 1:
                delta = {"tool_calls": [{"index": 0, "id": "q1", "function": {
                    "name": "edit_charts", "arguments": json.dumps(TOOL_ARGUMENTS),
                }}]}
                reason = "tool_calls"
            else:
                delta, reason = {"content": "The selected chart now shows the first quarter; SP and delivered orders are unchanged."}, "stop"
            chunk = {"id": f"local-{len(requests)}", "choices": [{"delta": delta, "finish_reason": reason}]}
            encoded = ("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_):
            pass

    peer = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=peer.serve_forever, daemon=True)
    thread.start()

    async def run():
        settings = configuration("text", text_url=f"http://127.0.0.1:{peer.server_port}/chat")
        async with application(settings) as (app, http, url):
            initial = await seed(http)
            jpeg = picture(initial)
            async with connect(url, proxy=None) as browser:
                await receive_until(browser, "bootstrap")
                await browser.send(json.dumps({"type": "text", "text": "Show only the first quarter, keeping the other conditions.",
                                               "reference": reference(initial), "image": jpeg, **synthetic_capture_clock(app)}))
                commit = await receive_until(browser, "state")
                answer = await receive_until(browser, "assistant_done", lambda e: bool(e.get("text")))
                view = commit["state"]["views"][0]
                assert view["source"]["end"] == "2017-04-01"
                assert view["source"]["region"] == "SP"
                assert view["source"]["status"] == "delivered"
                assert len(view["data"]["rows"]) == 3
                assert "first quarter" in answer["text"]
                assert requests[0]["messages"][-1]["content"][-1]["image_url"]["url"].endswith(jpeg)
                returned = json.loads(requests[1]["messages"][-1]["content"])
                assert returned["committed"] is True
                assert returned["state"]["revision"] == commit["state"]["revision"]
                assert len(requests) == 2
                workspace = app.state.workspace
                assert any(e["name"] == "image_captured" for e in workspace.trace.events)
                assert any(e["name"] == "tool_committed" and e["actor"] == "model" for e in workspace.trace.events)
                assert "local-integration-only" not in json.dumps(workspace.export())
                save_report("text", workspace, ["JPEG delivered", "actual Olist query committed", "source conditions preserved", "tool receipt returned", "assistant reply delivered"])

    try:
        asyncio.run(run())
    finally:
        peer.shutdown()
        peer.server_close()
        thread.join()


class VoicePeer:
    def __init__(self, first_arguments=None):
        self.events = []
        self.ws = None
        self.count = 0
        self.first_arguments = first_arguments

    async def send(self, event):
        await self.ws.send(json.dumps(event))

    async def utterance(self, item, text, live=False):
        if live:
            await self.send({"type": "input_audio_buffer.speech_started", "item_id": item})
            await self.send({"type": "input_audio_buffer.speech_stopped", "item_id": item})
        await self.send({"type": "input_audio_buffer.committed", "item_id": item})
        await self.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": item, "transcript": text})

    async def handler(self, ws):
        self.ws = ws
        async for raw in ws:
            event = json.loads(raw)
            self.events.append(event)
            kind = event["type"]
            if kind == "session.update":
                await self.send({"type": "session.updated", "session": event["session"]})
            elif kind == "input_audio_buffer.commit":
                await self.utterance("manual-1", "Show the first quarter and retain SP.")
            elif kind == "response.create":
                self.count += 1
                rid = f"voice-{self.count}"
                await self.send({"type": "response.created", "response": {"id": rid}})
                tool_response = self.count <= (2 if self.first_arguments else 1)
                if tool_response:
                    args = self.first_arguments if self.count == 1 and self.first_arguments else TOOL_ARGUMENTS
                    output = [{"type": "function_call", "call_id": f"call-{self.count}", "name": "edit_charts", "arguments": json.dumps(args)}]
                else:
                    output = []
                    await self.send({"type": "response.audio_transcript.delta", "response_id": rid, "delta": "The first quarter is displayed."})
                    await self.send({"type": "response.audio.delta", "response_id": rid, "delta": PCM})
                    await self.send({"type": "response.audio_transcript.done", "response_id": rid, "transcript": "The first quarter is displayed."})
                    await self.send({"type": "response.audio.done", "response_id": rid})
                await self.send({"type": "response.done", "response": {"id": rid, "status": "completed", "output": output}})
            elif kind == "conversation.item.create":
                await self.send({"type": "conversation.item.created", "item": event["item"]})


def test_voice_input_image_actual_edit_and_output_recording():
    async def run():
        peer = VoicePeer()
        async with serve(peer.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with application(configuration("voice", realtime_url=f"ws://127.0.0.1:{port}")) as (app, http, url):
                initial = await seed(http)
                async with connect(url, proxy=None) as browser:
                    await receive_until(browser, "bootstrap")
                    await browser.send(json.dumps({"type": "voice_start", "mode": "push_to_talk", "reference": reference(initial), "image": picture(initial), **synthetic_capture_clock(app)}))
                    await receive_until(browser, "voice_ready")
                    await browser.send(json.dumps({"type": "audio", "data": PCM}))
                    await browser.send(json.dumps({"type": "voice_commit"}))
                    commit = await receive_until(browser, "state")
                    await acknowledge_fixture_render(browser, commit['state'], app)
                    audio = await receive_until(browser, "audio")
                    assert audio["data"] == PCM
                    await receive_until(browser, "assistant_done", lambda event: "first quarter" in event.get("text", ""))
                    await browser.send(json.dumps({"type": "event", "name": "playback_start", "client_ms": 1200, "details": {"response_id": audio["response_id"], "fixture": True}}))
                    await browser.send(json.dumps({"type": "event", "name": "playback_end", "client_ms": 1266.7, "details": {"response_id": audio["response_id"], "fixture": True}}))
                    await browser.send(json.dumps({"type": "voice_stop"}))
                    await receive_until(browser, "voice_closed")
                    kinds = [e["type"] for e in peer.events]
                    assert kinds.index("input_audio_buffer.append") < kinds.index("input_image_buffer.append")
                    assert kinds.count("response.create") == 2
                    assert commit["state"]["views"][0]["source"]["end"] == "2017-04-01"
                    workspace = app.state.workspace
                    assert workspace.voice is None
                    assert list(workspace.trace.directory.glob("input-*.wav"))
                    assert list(workspace.trace.directory.glob("output-*.wav"))
                    assert any(e["name"] == "playback_end" and e["details"]["fixture"] for e in workspace.trace.events)
                    save_report("voice", workspace, ["PCM before JPEG", "ASR delivered", "actual edit committed", "tool receipt acknowledged", "output PCM/WAV saved", "provider closed", "playback events are scripted, not human listening"])

    asyncio.run(run())


def test_live_revision_during_query_prevents_obsolete_half_year_commit():
    async def run():
        half_year = {"view_ids": ["v1"], "patch": {"source": {"end": "2017-07-01"}}}
        peer, entered, release = VoicePeer(half_year), Event(), Event()
        async with serve(peer.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with application(configuration("interruption", realtime_url=f"ws://127.0.0.1:{port}")) as (app, http, url):
                initial = await seed(http)
                workspace = app.state.workspace
                original = workspace.store.prepare

                def blocked_prepare(name, args, reference=None):
                    candidate = original(name, args, reference)
                    if name == "edit_charts" and args == half_year:
                        entered.set()
                        release.wait(10)
                    return candidate

                workspace.store.prepare = blocked_prepare
                async with connect(url, proxy=None) as browser:
                    await receive_until(browser, "bootstrap")
                    await browser.send(json.dumps({"type": "voice_start", "mode": "live_voice", "reference": reference(initial), "image": picture(initial), **synthetic_capture_clock(app)}))
                    await receive_until(browser, "voice_ready")
                    await browser.send(json.dumps({"type": "audio", "data": PCM}))
                    await peer.utterance("first", "Show the first half of the year.", live=True)
                    async with asyncio.timeout(10):
                        while not entered.is_set():
                            await asyncio.sleep(0.01)
                    assert workspace.store.state["revision"] == initial["revision"]
                    await browser.send(json.dumps({"type": "audio", "data": PCM}))
                    await peer.utterance("revision", "Cancel the half year; show only the first quarter.", live=True)
                    await receive_until(browser, "user_transcript", lambda event: "Cancel" in event["text"])
                    release.set()
                    committed = await receive_until(browser, "state")
                    await acknowledge_fixture_render(browser, committed['state'], app)
                    await receive_until(browser, "audio")
                    assert committed["state"]["revision"] == initial["revision"] + 1
                    assert committed["state"]["views"][0]["source"]["end"] == "2017-04-01"
                    assert any(e["name"] == "tool_superseded" for e in workspace.trace.events)
                    model_nodes = [node for node in workspace.nodes if node["actor"] == "model"]
                    assert len(model_nodes) == 1
                    assert "first quarter" in model_nodes[0]["intent"]
                    assert all(state["views"][0]["source"]["end"] != "2017-07-01" for state in workspace.node_states.values())
                    outputs = [json.loads(e["item"]["output"]) for e in peer.events
                               if e["type"] == "conversation.item.create"]
                    assert len(outputs) == 2
                    assert outputs[0]["status"] == "superseded" and not outputs[0]["committed"]
                    assert set(outputs[0]) == {"status", "committed", "message"}
                    assert outputs[1]["committed"]
                    assert outputs[1]["state"]["views"][0]["source"]["end"] == "2017-04-01"
                    await browser.send(json.dumps({"type": "voice_stop"}))
                    await receive_until(browser, "voice_closed")
                    save_report("interruption", workspace, ["old candidate computed but not committed", "new ASR received while tool blocked", "only quarter revision published", "obsolete data suppressed; native call closed with superseded receipt", "controlled window, not natural model latency"])
                release.set()

    asyncio.run(run())
