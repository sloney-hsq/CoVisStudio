"""Scripted local text transport exercises reusable sets; never a model result."""

import asyncio
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest
from websockets.asyncio.client import connect

from backend.app import MODEL_TOOLS
from backend.oracle import category_rows, numeric_rows_equal
from test_model_flow import application, receive_until


EVIDENCE = (Path(__file__).resolve().parents[1] / "traces" / "business-model-flow" /
            datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
REQUEST = (
    "Reuse the saved SP priority categories in current charts 2 and 3. Keep MG, each chart's "
    "current metric, dates and status, and leave chart 1 unchanged."
)


class CategorySetTextPeer:
    """Decisions are authored; all versions, set IDs and data come from real receipts."""

    def __init__(self):
        self.requests, self.responses, self.receipts = [], [], []
        self.context = None
        self.saved = None
        self.reply = None

    def respond(self, body):
        self.requests.append(body)
        step = len(self.requests)
        if step > 1:
            self.receipts.append(json.loads(body["messages"][-1]["content"]))
        if step == 1:
            text = body["messages"][-1]["content"][0]["text"]
            self.context = json.loads(text.split("\nVisible reference:\n", 1)[1])
            name, args = "list_evidence_candidates", {}
        elif step == 2:
            sets = [candidate for candidate in self.receipts[-1]["result"]["candidates"]
                    if candidate["origin"] == "saved_set"]
            assert len(sets) == 1
            self.saved = sets[0]
            targets = [view["id"] for view in self.context["current_dashboard"]["views"]
                       if view["number"] in (2, 3)]
            name, args = "revise_analysis", {"view_ids": targets, "member_action": "use_evidence",
                                             "candidate_id": self.saved["candidate_id"]}
        elif step == 3:
            assert self.receipts[-1]["committed"] is True
            name, args = "read_dashboard", {}
        else:
            assert step == 4
            views = self.receipts[-1]["result"]["views"]
            second, third = (next(view for view in views if view["number"] == number) for number in (2, 3))
            assert second["source"]["region"] == third["source"]["region"]
            self.reply = (f"Charts 2 and 3 now use {self.saved['label']} in "
                          f"{second['source']['region']}. Their metrics remain "
                          f"{second['source']['metric']} and {third['source']['metric']}. "
                          "This is a scripted local protocol response.")
            return self.chunk({"content": self.reply}, "stop")
        delta = {"tool_calls": [{"index": 0, "id": f"set-call-{step}", "function": {
            "name": name, "arguments": json.dumps(args),
        }}]}
        return self.chunk(delta, "tool_calls")

    def chunk(self, delta, reason):
        chunk = {"id": f"local-set-{len(self.requests)}",
                 "choices": [{"delta": delta, "finish_reason": reason}]}
        self.responses.append(chunk)
        return ("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode()


@pytest.mark.parametrize("condition", ["direct", "bound_revision"])
def test_saved_sets_through_local_text_provider_in_every_condition(condition):
    scripted = CategorySetTextPeer()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            encoded = scripted.respond(body)
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
        settings = {
            "data_dir": Path("C:/VerbalVis/datasets/olist/data"), "trace_dir": EVIDENCE / condition,
            "api_key": "local-scripted-category-set-peer-only", "text_model": "scripted-local-text",
            "realtime_model": "unused-local-voice", "text_url": f"http://127.0.0.1:{peer.server_port}/chat",
            "realtime_url": "ws://127.0.0.1:1/not-used", "voice": "Tina",
        }
        async with application(settings) as (app, http, url):
            seeded = await http.post("/api/session", json={
                "mode": "text", "task_id": "starter", "condition": condition,
            })
            seeded.raise_for_status()
            historical = seeded.json()["state"]
            saved = await http.post("/api/category-sets", json={
                "name": "SP priority categories", "revision": historical["revision"], "view_id": "v1",
            })
            saved.raise_for_status()
            current = await http.post("/api/tools", json={"name": "edit_charts", "arguments": {
                "view_ids": ["v1", "v2", "v3"], "patch": {"source": {
                    "region": "MG", "categories": None, "top_n": 3, "rank_by": "orders",
                }},
            }})
            current.raise_for_status()
            before = current.json()["state"]
            historical_members = historical["views"][0]["data"]["selection"]["members"]
            assert historical_members != before["views"][0]["data"]["selection"]["members"]
            workspace, completed = app.state.workspace, False
            try:
                async with connect(url, proxy=None) as browser:
                    await receive_until(browser, "bootstrap")
                    await browser.send(json.dumps({"type": "text", "text": REQUEST, "reference": {
                        "revision": before["revision"], "view_ids": ["v2", "v3"], "entities": {},
                    }}))
                    commit = await receive_until(browser, "state")
                    answer = await receive_until(browser, "assistant_done", lambda event: bool(event.get("text")))
                    assert answer["text"] == scripted.reply
                    assert len(scripted.requests) == 4
                    assert len(scripted.receipts) == 3
                    assert all(request["tools"] == MODEL_TOOLS for request in scripted.requests)
                    assert "condition" not in scripted.context
                    assert workspace.session["condition"] == condition
                    assert scripted.saved["members"] == historical_members
                    assert scripted.saved["evidence"]["revision"] == historical["revision"]
                    assert scripted.saved["evidence"]["source"]["region"] == "SP"
                    assert [receipt["committed"] for receipt in scripted.receipts] == [False, True, False]

                    after = workspace.store.snapshot()
                    assert after == commit["state"]
                    assert after == scripted.receipts[1]["state"]
                    assert after["revision"] == before["revision"] + 1
                    assert after["views"][0] == before["views"][0]
                    assert scripted.receipts[2]["result"]["views"] == after["views"]
                    for old, view in zip(before["views"][1:], after["views"][1:]):
                        assert view["source"] == {**old["source"], "categories": historical_members, "top_n": None}
                        assert view["data"]["selection"]["members"] == historical_members
                        assert numeric_rows_equal(view["data"]["rows"], category_rows(workspace.data, view["source"]))
                    calls = [event for event in workspace.trace.events if event["name"] == "tool_started" and event["actor"] == "model"]
                    assert [event["tool"] for event in calls] == [
                        "list_evidence_candidates", "preview_revision", "apply_revision", "read_dashboard",
                    ]
                    assert calls[1]["arguments"]["candidate_id"] == scripted.saved["candidate_id"]
                    publications = [event for event in workspace.trace.events if event["name"] == "tool_committed" and event["actor"] == "model"]
                    assert len(publications) == 1 and publications[0]["tool"] == "apply_revision"
                    assert workspace.proposal["status"] == "committed"
                    assert workspace.voice is None
                    completed = True
            finally:
                workspace.trace.save("peer-protocol.json", {
                    "requests": scripted.requests, "responses": scripted.responses, "receipts": scripted.receipts,
                })
                workspace.trace.save("session.json", workspace.export())
                workspace.trace.save("integration-report.json", {
                    "condition": condition, "completed": completed, "paid_api_calls": 0, "real_model_result": False,
                    "transport": "production QwenText against a local HTTP SSE scripted peer",
                    "actual_browser_rendering": False, "human_listening": "not tested",
                    "initial_revision": before["revision"], "final_revision": workspace.store.state["revision"],
                    "historical_evidence_revision": historical["revision"],
                    "checks_passed": (["same six tools in every condition", "interface-saved set listed as a candidate",
                                       "candidate ID applied without category transcription", "only v2/v3 edited",
                                       "current MG and each metric/date/status retained", "independent raw-table values checked",
                                       "actual committed receipt returned to peer", "read_dashboard before fixture response",
                                       "single revise_analysis call committed"] if completed else []),
                })

    try:
        asyncio.run(run())
    finally:
        peer.shutdown()
        peer.server_close()
        thread.join()
