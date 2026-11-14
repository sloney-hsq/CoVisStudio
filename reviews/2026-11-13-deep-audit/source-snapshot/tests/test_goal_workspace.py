"""Offline execution/outcome/shutdown checks; real Olist, no model connections."""
import asyncio
from copy import deepcopy
from pathlib import Path

import pytest

from backend.app import Workspace
from backend.oracle import category_rows, numeric_rows_equal


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    ws = Workspace({"api_key": "", "text_model": "offline", "realtime_model": "offline",
                    "voice": "Maia", "text_url": "http://127.0.0.1:9/disabled",
                    "realtime_url": "ws://127.0.0.1:9/disabled",
                    "data_dir": Path("C:/VerbalVis/datasets/olist/data"),
                    "trace_dir": tmp_path_factory.mktemp("goal-workspace")})
    yield ws
    ws.data.close()


async def accepted(ws, rid, text="Apply the requested analytical change."):
    await ws.revoke()
    ws.accept(text, ws.reference)
    return await ws.provider_event({"type": "response_start", "response_id": rid})


def assert_oracle(ws, state):
    for view in state["views"]:
        assert numeric_rows_equal(view["data"]["rows"], category_rows(ws.data, view["source"]))


def test_single_call_historical_reuse_and_q1_revision_match_both_conditions(workspace):
    async def run():
        finals = []
        ws = workspace
        for condition in ("direct", "bound_revision"):
            ws.reset("live_voice", "starter", "", condition)
            historical = ws.store.snapshot()
            await ws.execute("edit_charts", {"view_ids": ["v2", "v3"],
                "patch": {"source": {"region": "MG", "categories": None, "top_n": 3}}}, actor="user")
            before = ws.store.snapshot()
            context = await accepted(ws, "reuse")
            result = await ws.execute("revise_analysis", {
                "candidate_id": f"chart:{historical['revision']}:v1", "view_ids": ["v2", "v3"],
                "member_action": "use_evidence", "start": "2017-01-01", "end": "2017-07-01"}, call_context=context)
            assert result["committed"] is True
            first = ws.store.snapshot()
            assert first["revision"] == before["revision"] + 1
            assert first["views"][0] == before["views"][0]
            members = [row["label"] for row in historical["views"][0]["data"]["rows"]]
            for old, view in zip(before["views"][1:], first["views"][1:]):
                assert view["source"] == {**old["source"], "categories": members,
                    "top_n": None, "start": "2017-01-01", "end": "2017-07-01"}
            assert_oracle(ws, first)
            context = await accepted(ws, "q1", "Actually use Q1; keep those categories.")
            revised = await ws.execute("revise_analysis", {"view_ids": ["v2", "v3"],
                "member_action": "keep_current", "end": "2017-04-01"}, call_context=context)
            assert revised["committed"] is True
            final = ws.store.snapshot()
            assert final["views"][0] == before["views"][0]
            for old, view in zip(first["views"][1:], final["views"][1:]):
                assert view["source"] == {**old["source"], "end": "2017-04-01"}
            assert_oracle(ws, final)
            await ws.provider_event({"type": "request_settled", "response_id": "q1", "status": "completed"})
            assert ws.trace.events[-1]["status"] == "committed"
            assert ws.trace.events[-1]["view_numbers"] == [2, 3]
            finals.append(final)
        assert finals[0]["revision"] == finals[1]["revision"]
        for direct, bound in zip(finals[0]["views"], finals[1]["views"]):
            assert direct["source"] == bound["source"]
            assert direct["data"]["selection"] == bound["data"]["selection"]
            assert numeric_rows_equal(direct["data"]["rows"], bound["data"]["rows"])
    asyncio.run(run())


def test_explicit_confirmation_does_not_publish(workspace):
    async def run():
        ws = workspace
        ws.reset("text", "starter", "")
        before = ws.store.snapshot()
        context = await accepted(ws, "confirm")
        result = await ws.execute("revise_analysis", {"view_ids": ["v2"],
            "member_action": "keep_current", "end": "2017-04-01",
            "needs_confirmation": True, "question": "Apply this date range?"}, call_context=context)
        assert result["status"] == "awaiting_confirmation"
        assert not result["committed"]
        assert ws.store.snapshot() == before
        await ws.provider_event({"type": "request_settled", "response_id": "confirm", "status": "completed"})
        assert ws.trace.events[-1]["status"] == "awaiting_confirmation"
        assert not ws.trace.events[-1]["committed"]
    asyncio.run(run())


def test_promise_outcome_excludes_previous_request_commit_and_stale_settlement(workspace):
    async def run():
        ws = workspace
        ws.reset("text", "starter", "")
        context = await accepted(ws, "previous")
        await ws.execute("revise_analysis", {"view_ids": ["v2"], "member_action": "keep_current",
            "end": "2017-07-01"}, call_context=context)
        before = ws.store.snapshot()
        await accepted(ws, "promise", "Actually use Q1.")
        await ws.provider_event({"type": "assistant_done", "response_id": "promise", "text": "I will change it to Q1."})
        await ws.provider_event({"type": "request_settled", "response_id": "promise", "status": "completed"})
        outcome = ws.trace.events[-1]
        assert outcome["name"] == "request_outcome"
        assert outcome["status"] == "no_changes" and not outcome["committed"]
        assert outcome["view_numbers"] == []
        assert ws.store.snapshot() == before
        count = len(ws.trace.events)
        await ws.provider_event({"type": "request_settled", "response_id": "previous", "status": "completed"})
        assert len(ws.trace.events) == count
    asyncio.run(run())


def test_failed_settlement_reports_failure(workspace):
    async def run():
        ws = workspace
        ws.reset("text", "starter", "")
        context = await accepted(ws, "failed")
        result = await ws.execute("revise_analysis", {"view_ids": ["missing"],
            "member_action": "keep_current", "end": "2017-04-01"}, call_context=context)
        assert result["status"] == "failed"
        await ws.provider_event({"type": "request_settled", "response_id": "failed", "status": "failed"})
        outcome = ws.trace.events[-1]
        assert outcome["status"] == "failed" and not outcome["committed"]
        assert outcome["message"]
    asyncio.run(run())


@pytest.mark.parametrize("cancel_first", [False, True])
def test_concurrent_workspace_close_waits_and_emits_once(workspace, cancel_first):
    async def run():
        ws = workspace
        ws.reset("live_voice", "starter", "")
        entered, release = asyncio.Event(), asyncio.Event()
        sent = []
        class Voice:
            calls = 0
            async def close(self):
                self.calls += 1
                entered.set()
                await release.wait()
        async def send(event):
            sent.append(deepcopy(event))
        original_send = ws.send
        ws.send = send
        voice = ws.voice = Voice()
        try:
            first = asyncio.create_task(ws.close_voice())
            await entered.wait()
            second = asyncio.create_task(ws.close_voice())
            await asyncio.sleep(0)
            assert not second.done()
            if cancel_first:
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
            release.set()
            await asyncio.wait_for(second, 1)
            if not cancel_first:
                await first
            assert voice.calls == 1
            assert ws.voice is None and ws.voice_closing is None
            assert sum(event["type"] == "voice_closed" for event in sent) == 1
            assert sum(event["name"] == "voice_closed" for event in ws.trace.events) == 1
        finally:
            ws.send = original_send
    asyncio.run(run())
