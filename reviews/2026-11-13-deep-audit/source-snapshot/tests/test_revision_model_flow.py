"""Local voice transport with scripted decisions; no paid model or listening claim."""

import asyncio
import base64
from io import BytesIO
import json
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from backend.app import media_summary
from test_model_flow import application, receive_until, synthetic_capture_clock, acknowledge_fixture_render


EVIDENCE = Path(__file__).resolve().parents[1] / "traces" / "revision-model-20261113"
REQUEST = "Use the three categories from the selected SP version in chart 2. Keep MG and its current metric and dates."
REPLY = "Chart 2 now uses the selected SP categories, calculated for MG. The low review rate and 2017 dates are retained; charts 1 and 3 are unchanged."
CANCEL_REPLY = "The earlier proposal is no longer current. No chart has changed."


def tone(rate):
    """200 ms protocol audio fixture, deliberately not represented as speech."""
    pcm = b"".join(struct.pack("<h", int(1200 * math.sin(2 * math.pi * 440 * t / rate))) for t in range(rate // 5))
    return base64.b64encode(pcm).decode()


INPUT_PCM, OUTPUT_PCM = tone(16000), tone(24000)


def configuration(case, url):
    return {"data_dir": Path("C:/VerbalVis/datasets/olist/data"), "trace_dir": EVIDENCE / case,
            "api_key": "local-scripted-peer-only", "text_model": "scripted-local-text",
            "realtime_model": "scripted-local-voice", "text_url": "http://127.0.0.1:1/not-used",
            "realtime_url": url, "voice": "Tina"}


def chart_image(state):
    """Render actual current Olist values; this is not a browser screenshot."""
    view = state["views"][1]
    image = Image.new("RGB", (900, 440), "#f6f5f0")
    draw = ImageDraw.Draw(image)
    draw.text((28, 25), f"Chart 2 | {view['source']['region']} | Low review rate | 2017", fill="#173531")
    maximum = max(row["value"] for row in view["data"]["rows"])
    for index, row in enumerate(view["data"]["rows"]):
        y = 100 + 95 * index
        draw.text((28, y), row["label"], fill="#173531")
        draw.rectangle((260, y, 260 + row["value"] / maximum * 500, y + 38), fill="#267d70")
        draw.text((770, y + 10), f"{row['value']:.1%}", fill="#173531")
    output = BytesIO()
    image.save(output, format="JPEG")
    return base64.b64encode(output.getvalue()).decode()


async def seed_history(http):
    initial = await http.post("/api/session", json={"mode": "live_voice", "task_id": "starter", "condition": "bound_revision"})
    initial.raise_for_status()
    historical = initial.json()["state"]
    response = await http.post("/api/tools", json={"name": "edit_charts", "arguments": {
        "view_ids": ["v1", "v2", "v3"], "patch": {"source": {
            "region": "MG", "categories": None, "top_n": 3, "rank_by": "orders"}}}})
    response.raise_for_status()
    current = response.json()["state"]
    selection = {"revision": historical["revision"], "view_id": "v1"}
    chosen = await http.post("/api/evidence", json=selection)
    chosen.raise_for_status()
    assert chosen.json()["evidence"]["source"]["region"] == "SP"
    assert historical["views"][0]["data"]["selection"]["members"] != current["views"][0]["data"]["selection"]["members"]
    return historical, current


class RevisionVoicePeer:
    """One deterministic response script through the production WS provider."""

    def __init__(self, case):
        self.case = case
        self.events, self.sent, self.receipts = [], [], []
        self.count = 0
        self.proposal_id = None
        self.waiting = asyncio.Event()
        self.history_revision = None
        self.ws = None

    async def send(self, event):
        self.sent.append(event)
        await self.ws.send(json.dumps(event))

    async def utterance(self, item, text):
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
            elif kind == "conversation.item.create":
                receipt = json.loads(event["item"]["output"])
                self.receipts.append(receipt)
                if receipt.get("proposal"):
                    self.proposal_id = receipt["proposal"]["id"]
                await self.send({"type": "conversation.item.created", "item": event["item"]})
            elif kind == "response.cancel":
                await self.send({"type": "response.done", "response": {
                    "id": event["response_id"], "status": "cancelled", "output": []}})
            elif kind == "response.create":
                self.count += 1
                rid = f"revision-voice-{self.count}"
                await self.send({"type": "response.created", "response": {"id": rid}})
                if self.count == 1:
                    name, arguments = "read_history", {"revision": self.history_revision}
                elif self.count == 2 or self.case == "spoken_confirmation" and self.count == 5:
                    # Evidence is inherited from the user's selection at speech start.
                    name, arguments = "preview_revision", {
                        "view_ids": ["v2"], "source_patch": {}, "member_action": "use_evidence",
                        "needs_confirmation": self.case in ("confirmation", "spoken_confirmation") and self.count == 2,
                    }
                    if arguments["needs_confirmation"]:
                        arguments["question"] = "Use the earlier SP categories in chart 2, keeping MG?"
                elif self.case == "superseded" and self.count == 3:
                    self.waiting.set()
                    continue
                elif self.count == 3 or self.case == "superseded" and self.count == 4 or self.case == "spoken_confirmation" and self.count == 6:
                    name, arguments = "apply_revision", {"proposal_id": self.proposal_id}
                else:
                    reply = "Please confirm which comparison set to use. No chart has changed." if self.case in ("confirmation", "spoken_confirmation") and self.count == 4 else REPLY
                    if self.case == "superseded":
                        reply = CANCEL_REPLY
                    await self.send({"type": "response.audio_transcript.delta", "response_id": rid, "delta": reply})
                    await self.send({"type": "response.audio.delta", "response_id": rid, "delta": OUTPUT_PCM})
                    await self.send({"type": "response.audio_transcript.done", "response_id": rid, "transcript": reply})
                    await self.send({"type": "response.audio.done", "response_id": rid})
                    await self.send({"type": "response.done", "response": {"id": rid, "status": "completed", "output": []}})
                    continue
                await self.send({"type": "response.done", "response": {"id": rid, "status": "completed", "output": [{
                    "type": "function_call", "call_id": f"revision-call-{self.count}",
                    "name": name, "arguments": json.dumps(arguments),
                }]}})


def verify_committed_data(workspace, historical, before):
    after = workspace.store.snapshot()
    members = historical["views"][0]["data"]["selection"]["members"]
    assert after["revision"] == before["revision"] + 1
    assert after["views"][0] == before["views"][0]
    assert after["views"][2] == before["views"][2]
    source = after["views"][1]["source"]
    assert source == {**before["views"][1]["source"], "categories": members, "top_n": None}
    assert source["region"] == "MG"
    # Independent aggregate: distinct order/category pairs prevent item joins multiplying reviews.
    for row in after["views"][1]["data"]["rows"]:
        reviewed, low = workspace.data.connection.execute("""
            SELECT count(o.review_score), count(*) FILTER (WHERE o.review_score <= 2)
            FROM orders o JOIN (SELECT DISTINCT order_id FROM items WHERE category = ?) i USING(order_id)
            WHERE o.region = 'MG' AND o.order_status = 'delivered'
              AND o.purchased_at >= DATE '2017-01-01' AND o.purchased_at < DATE '2018-01-01'
        """, [row["label"]]).fetchone()
        assert row["reviewed_orders"] == reviewed
        assert row["low_review_count"] == low
        assert row["value"] == pytest.approx(low / reviewed)


@pytest.mark.parametrize("case", ["complete", "confirmation", "spoken_confirmation", "superseded"])
def test_revision_voice_protocol(case):
    async def run():
        peer = RevisionVoicePeer(case)
        async with serve(peer.handler, "127.0.0.1", 0) as provider:
            port = provider.sockets[0].getsockname()[1]
            async with application(configuration(case, f"ws://127.0.0.1:{port}")) as (app, http, url):
                historical, before = await seed_history(http)
                peer.history_revision = historical["revision"]
                workspace = app.state.workspace
                jpeg, completed = chart_image(before), False
                try:
                    async with connect(url, proxy=None) as browser:
                        await receive_until(browser, "bootstrap")
                        await browser.send(json.dumps({"type": "voice_start", "mode": "live_voice", "image": jpeg, **synthetic_capture_clock(app),
                            "reference": {"revision": before["revision"], "view_ids": ["v2"], "entities": {}}}))
                        await receive_until(browser, "voice_ready")
                        await browser.send(json.dumps({"type": "audio", "data": INPUT_PCM}))
                        await peer.utterance("initial", REQUEST)
                        proposal_event = await receive_until(browser, "proposal", lambda e: e["proposal"]["status"] == "pending")
                        card = proposal_event["proposal"]["card"]
                        assert card["evidence"]["revision"] == historical["revision"]
                        assert card["evidence"]["source"]["region"] == "SP"
                        assert card["base_revision"] == before["revision"]
                        assert card["binding_applied"] is True
                        assert card["view_ids"] == ["v2"]

                        if case == "superseded":
                            async with asyncio.timeout(10):
                                await peer.waiting.wait()
                            old_proposal = peer.proposal_id
                            old_epoch = workspace.epoch
                            assert workspace.store.snapshot() == before
                            await browser.send(json.dumps({"type": "audio", "data": INPUT_PCM}))
                            await peer.utterance("revised", "Cancel that change. Keep the current MG comparison set.")
                            await receive_until(browser, "proposal", lambda e: e["proposal"]["status"] == "superseded")
                            await receive_until(browser, "user_transcript", lambda e: "Cancel" in e["text"])
                            stale_execution = await workspace.apply_revision(old_proposal, expected_epoch=old_epoch)
                            assert stale_execution == {"status": "superseded", "committed": False}
                            await receive_until(browser, "response_end", lambda e: e["response_id"] == "revision-voice-4")
                            async with asyncio.timeout(10):
                                while workspace.voice.jobs:
                                    await asyncio.sleep(0.01)
                            outcome = await receive_until(browser, "request_outcome", lambda e: e["response_id"] == "revision-voice-4")
                            assert outcome["status"] == "failed" and outcome["committed"] is False
                            assert outcome["view_numbers"] == []
                            rejected = await http.post(f"/api/revisions/{old_proposal}/apply")
                            assert rejected.status_code == 409
                            assert workspace.store.snapshot() == before
                            assert workspace.proposal["status"] == "superseded"
                            assert len(peer.receipts) == 3
                            assert peer.receipts[-1]["status"] == "failed"
                            assert peer.receipts[-1]["committed"] is False
                            assert "new preview" in peer.receipts[-1]["message"]
                            # The acknowledged failure ends this request, without asking the model to continue.
                            assert peer.count == 4
                            assert sum(e["type"] == "response.create" for e in peer.events) == 4
                            assert not any(e["type"] == "response.audio.delta" for e in peer.sent)
                            assert not any(e["type"] == "response.audio_transcript.done" for e in peer.sent)
                        else:
                            if case == "complete":
                                committed = await receive_until(browser, "state")
                                await acknowledge_fixture_render(browser, committed['state'], app,
                                    image=chart_image(committed['state']), reference_snapshot={
                                        'revision': committed['state']['revision'], 'view_ids': ['v2'], 'entities': {}})
                            audio = await receive_until(browser, "audio")
                            answer = await receive_until(browser, "assistant_done", lambda e: bool(e.get("text")))
                            assert audio["data"] == OUTPUT_PCM
                            assert len(peer.receipts) == 3
                            if case == "complete":
                                verify_committed_data(workspace, historical, before)
                                assert peer.receipts[-1]["committed"] is True
                                assert answer["text"] == REPLY
                            elif case == "confirmation":
                                assert workspace.store.snapshot() == before
                                assert peer.receipts[-1]["status"] == "awaiting_confirmation"
                                assert workspace.proposal["status"] == "pending"
                                confirmed = await http.post(f"/api/revisions/{peer.proposal_id}/apply")
                                confirmed.raise_for_status()
                                verify_committed_data(workspace, historical, before)
                                assert workspace.proposal["status"] == "committed"
                            else:
                                assert workspace.store.snapshot() == before
                                assert peer.receipts[-1]["status"] == "awaiting_confirmation"
                                old_id = peer.proposal_id
                                await browser.send(json.dumps({"type": "audio", "data": INPUT_PCM}))
                                await peer.send({"type": "input_audio_buffer.speech_started", "item_id": "yes"})
                                await receive_until(browser, "proposal", lambda e: e["proposal"]["status"] == "superseded")
                                rejected = await http.post(f"/api/revisions/{old_id}/apply")
                                assert rejected.status_code == 409
                                assert workspace.store.snapshot() == before
                                # The new turn receives the old question/card as context, not execution permission.
                                context = json.loads(workspace.context())
                                assert context["last_proposal"]["id"] == old_id
                                assert context["last_proposal"]["status"] == "superseded"
                                assert context["last_proposal"]["card"] == card
                                await peer.send({"type": "input_audio_buffer.speech_stopped", "item_id": "yes"})
                                await peer.send({"type": "input_audio_buffer.committed", "item_id": "yes"})
                                await peer.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "yes",
                                                 "transcript": "Yes, use those earlier SP categories. Keep MG and apply it only to chart 2."})
                                second = await receive_until(browser, "proposal", lambda e: e["proposal"]["status"] == "pending")
                                assert second["proposal"]["id"] != old_id
                                assert second["proposal"]["card"]["needs_confirmation"] is False
                                committed = await receive_until(browser, "state")
                                await acknowledge_fixture_render(browser, committed['state'], app,
                                    image=chart_image(committed['state']), reference_snapshot={
                                        'revision': committed['state']['revision'], 'view_ids': ['v2'], 'entities': {}})
                                await receive_until(browser, "audio")
                                await receive_until(browser, "assistant_done", lambda e: e.get("text") == REPLY)
                                verify_committed_data(workspace, historical, before)
                                assert len(peer.receipts) == 5
                                assert peer.receipts[-1]["committed"] is True
                                contexts = [json.loads(e["session"]["instructions"].splitlines()[-1])
                                            for e in peer.events if e["type"] == "session.update" and "last_proposal" in e["session"].get("instructions", "")]
                                assert any(c["last_proposal"] and c["last_proposal"]["id"] == old_id
                                           and c["last_proposal"]["status"] == "superseded" for c in contexts)

                        await browser.send(json.dumps({"type": "voice_stop"}))
                        await receive_until(browser, "voice_closed")
                        kinds = [event["type"] for event in peer.events]
                        assert kinds.index("input_audio_buffer.append") < kinds.index("input_image_buffer.append")
                        assert next(e["image"] for e in peer.events if e["type"] == "input_image_buffer.append") == jpeg
                        tool_names = {t["function"]["name"] for t in peer.events[0]["session"]["tools"]}
                        assert {"read_history", "preview_revision", "apply_revision"} <= tool_names
                        assert peer.receipts[0]["result"] == historical
                        assert workspace.voice is None
                        assert list(workspace.trace.directory.glob("input-*.wav"))
                        if case != "superseded":
                            assert list(workspace.trace.directory.glob("output-*.wav"))
                        completed = True
                finally:
                    workspace.trace.finalize_audio()
                    workspace.trace.save("peer-protocol.json", media_summary({"received": peer.events, "sent": peer.sent}))
                    workspace.trace.save("session.json", workspace.export())
                    workspace.trace.save("integration-report.json", {
                        "case": case, "completed": completed, "paid_api_calls": 0, "real_model_result": False,
                        "input_audio": "200 ms synthetic tone; transcription explicitly scripted",
                        "output_audio": "200 ms synthetic tone; assistant text explicitly scripted",
                        "image": "actual Olist chart values rendered as JPEG, not browser capture",
                        "actual_browser_playback": False, "human_listening": "pending",
                        "initial_revision": before["revision"], "final_revision": workspace.store.state["revision"],
                        "historical_evidence_revision": historical["revision"],
                        "checks_passed": (["historical SP evidence read through model tool", "PCM and JPEG delivered",
                                           "current source and target scope retained", "public revision lifecycle checked"]
                                          if completed else []),
                    })
    asyncio.run(run())
