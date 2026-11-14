"""Local HTTP/WebSocket and real-data study checks. No model API is used."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient

from backend.app import Workspace, create_app
from backend.study import tasks, legacy_tasks


def local_settings(trace_dir, api_key=""):
    return {"api_key": api_key, "text_model": "local-test-text", "realtime_model": "local-test-voice", "voice": "Maia",
            "text_url": "http://127.0.0.1:9/not-called", "realtime_url": "ws://127.0.0.1:9/not-called",
            "data_dir": Path("C:/VerbalVis/datasets/olist/data"), "trace_dir": trace_dir}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    app = create_app(local_settings(tmp_path_factory.mktemp("workspace-traces")))
    with TestClient(app) as connection:
        yield connection


def begin(client, task_id="starter", mode="text"):
    response = client.post("/api/session", json={"mode": mode, "task_id": task_id, "participant_id": "local-author-check"})
    assert response.status_code == 200
    return response.json()


def edit(client, ids, patch):
    response = client.post("/api/tools", json={"name": "edit_charts", "arguments": {"view_ids": ids, "patch": patch}})
    assert response.status_code == 200, response.text
    return response.json()


def author_edits(task_id, views):
    """Executable author path from the public task; never delivered to a provider."""
    family, kind = task_id.rsplit("_", 1)
    regions = ["MG"] * 3 if kind == "linked" else ["MG", "RJ", "PR"]
    periods = [("2017-01-01", "2017-04-01")] * 3 if kind == "linked" else [
        ("2017-01-01", "2017-04-01"), ("2017-04-01", "2017-07-01"), ("2017-07-01", "2017-10-01")]
    for index, view in enumerate(views):
        source = {}
        if family in ("region", "rerank", "metric", "scope"):
            source["region"] = regions[index]
        if family in ("quarter", "quarter_rank", "scope"):
            source.update(start=periods[index][0], end=periods[index][1])
        if family in ("rerank", "quarter_rank"):
            source.update(categories=None, top_n=3, rank_by="orders")
        if family == "metric":
            source["metric"] = ["revenue", "avg_delivery_days", "low_review_rate"][index]
        yield view["id"], {"source": source}


def test_empty_bootstrap_is_not_a_prefilled_model_result(client):
    response = begin(client, task_id=None)
    assert response["state"]["views"] == []
    assert response["nodes"] == []
    assert response["settings"]["configured"] is False
    assert len(response["tasks"]) == 5
    assert len(response["diagnostic_tasks"]) == 18
    assert "expected" not in json.dumps(response["tasks"])


@pytest.mark.parametrize("mode", ["text", "push_to_talk", "live_voice"])
def test_three_modes_share_explicit_starter_and_actual_data(client, mode):
    response = begin(client, mode=mode)
    views = response["state"]["views"]
    assert response["session"]["mode"] == mode
    assert len(views) == 3
    assert all(node["actor"] == "starter" for node in response["nodes"])
    assert [v["source"]["metric"] for v in views] == ["orders", "low_review_rate", "avg_delivery_days"]
    assert all(v["source"]["categories"] == views[0]["source"]["categories"] for v in views)
    assert views[0]["data"]["rows"][0]["value"] == 1891
    rate = views[1]["data"]["rows"][0]
    assert rate["value"] == pytest.approx(rate["low_review_count"] / rate["reviewed_orders"])
    assert client.app.state.workspace.voice is None


@pytest.mark.parametrize("task_id", [task["id"] for task in legacy_tasks() if task["id"] != "starter"])
def test_all_twelve_tasks_have_a_real_tool_path_and_score(client, task_id):
    initial = begin(client, task_id)["state"]
    for view_id, patch in author_edits(task_id, initial["views"]):
        receipt = edit(client, [view_id], patch)
        assert receipt["committed"] is True
    report = client.post("/api/finish").json()["report"]
    assert report["completed"] is True
    assert len(report["checks"]) == 24
    assert all(check["passed"] for check in report["checks"])
    assert report["review_status"] == "pending"
    assert report["counts"]["tool_committed"] == 3
    assert client.app.state.workspace.voice is None


def test_wrong_final_scope_fails_and_incomplete_tasks_stay_exported(client):
    begin(client, "region_linked")
    edit(client, ["v1"], {"source": {"region": "MG"}})
    report = client.post("/api/finish").json()["report"]
    assert report["completed"] is False
    assert any(c["name"] == "Chart 2 · region" and not c["passed"] for c in report["checks"])
    exported = client.get("/api/export").json()
    assert exported["report"]["completed"] is False
    assert len(exported["final"]["views"]) == 3


def test_fixed_and_reranked_linked_tasks_have_distinct_real_members(client):
    member_sets = {}
    for task_id in ("region_linked", "rerank_linked"):
        initial = begin(client, task_id)["state"]
        for view_id, patch in author_edits(task_id, initial["views"]):
            final = edit(client, [view_id], patch)["state"]
        member_sets[task_id] = {r["label"] for r in final["views"][0]["data"]["rows"]}
        assert all(v["source"]["region"] == "MG" for v in final["views"])
        assert client.post("/api/finish").json()["report"]["completed"] is True
    assert member_sets["region_linked"] == {"bed_bath_table", "sports_leisure", "furniture_decor"}
    assert member_sets["rerank_linked"] == {"bed_bath_table", "sports_leisure", "health_beauty"}
    assert member_sets["region_linked"] != member_sets["rerank_linked"]


def test_edit_undo_restore_and_nodes_preserve_historical_states(client):
    bootstrap = begin(client)
    initial = bootstrap["state"]
    changed = edit(client, ["v1"], {"style": {"color": "#f1733c"}})
    assert changed["state"]["views"][0]["data"] == initial["views"][0]["data"]
    assert changed["state"]["views"][0]["source"] == initial["views"][0]["source"]
    node_id = changed["node"]["id"]
    undo = client.post("/api/undo").json()
    assert undo["state"]["revision"] > changed["state"]["revision"]
    assert undo["state"]["views"] == initial["views"]
    historic = client.get(f"/api/nodes/{node_id}").json()
    assert historic["state"]["views"][0]["style"]["color"] == "#f1733c"
    restored = client.post(f"/api/nodes/{node_id}/restore").json()
    assert restored["state"]["views"][0]["style"]["color"] == "#f1733c"
    assert restored["state"]["revision"] > undo["state"]["revision"]
    assert len(client.get("/api/history").json()["nodes"]) == 6


def test_failure_and_human_notes_are_retained_without_auto_review_pass(client):
    begin(client, "region_linked")
    bad = client.post("/api/tools", json={"name": "edit_charts", "arguments": {"view_ids": ["v1"], "patch": {"data": [{"value": 999}]}}})
    assert bad.status_code == 400
    review = client.post("/api/review", json={"notes": "Local annotation only; audio not heard.", "classification": "needs_review"}).json()
    assert review["review_status"] == "pending"
    report = client.post("/api/finish").json()["report"]
    assert report["counts"]["tool_failed"] == 1
    assert report["review_status"] == "pending"
    exported = client.get("/api/export").json()
    assert any(e["name"] == "tool_failed" for e in exported["events"])
    assert exported["reviews"][0]["classification"] == "needs_review"


def test_node_event_window_contains_its_commit_and_not_future_changes(client):
    begin(client)
    first = edit(client, ["v1"], {"style": {"color": "#f1733c"}})
    second = edit(client, ["v2"], {"source": {"region": "RJ"}})
    node = client.get(f"/api/nodes/{first['node']['id']}").json()
    commits = [e for e in node["events"] if e["name"] == "tool_committed"]
    assert [e["revision"] for e in commits] == [first["state"]["revision"]]
    assert all(e.get("revision") != second["state"]["revision"] for e in node["events"])
    assert node["state"]["views"][1]["source"]["region"] == "SP"


def test_scored_report_is_invalidated_by_edit_undo_and_restore(client):
    initial = begin(client, "region_linked")["state"]
    for view_id, patch in author_edits("region_linked", initial["views"]):
        edit(client, [view_id], patch)
    completed = client.post("/api/finish").json()["report"]
    assert completed["completed"] is True
    assert completed["revision"] == client.get("/api/bootstrap").json()["state"]["revision"]
    changed = edit(client, ["v1"], {"source": {"region": "RJ"}})
    assert client.get("/api/export").json()["report"] is None
    assert client.post("/api/finish").json()["report"]["completed"] is False
    undone = client.post("/api/undo").json()
    assert client.get("/api/export").json()["report"] is None
    assert client.post("/api/finish").json()["report"]["completed"] is True
    detail = client.get(f"/api/nodes/{undone['node']['id']}").json()
    assert any(event["name"] == "undo" for event in detail["events"])
    client.post(f"/api/nodes/{changed['node']['id']}/restore").raise_for_status()
    assert client.get("/api/export").json()["report"] is None


def test_ui_mode_changes_and_text_submission_are_reflected_in_export(client):
    begin(client, mode="live_voice")
    with client.websocket_connect("/ws") as socket:
        bootstrap = socket.receive_json()
        socket.send_json({"type": "event", "name": "mode_selected", "client_ms": 1, "details": {"mode": "push_to_talk"}})
        socket.send_json({"type": "cancel"})
        assert socket.receive_json()["type"] == "stop_audio"
        assert socket.receive_json()["type"] == "status"
        assert client.get("/api/export").json()["session"]["mode"] == "push_to_talk"
        socket.send_json({"type": "text", "text": "Describe these charts.", "reference": {"revision": bootstrap["state"]["revision"], "view_ids": [], "entities": {}}})
        assert socket.receive_json()["type"] == "stop_audio"
        accepted = socket.receive_json()
        assert accepted["type"] == "request_accepted" and accepted["text"] == "Describe these charts."
        assert accepted["request_id"]
        assert socket.receive_json()["type"] == "error"  # Key absent; input recorded but no model called.
        exported = client.get("/api/export").json()
        assert exported["session"]["mode"] == "text"
        assert exported["session"]["used_modes"] == ["text"]


def test_websocket_reference_clock_and_missing_key_never_open_provider(client, monkeypatch):
    from backend import providers
    def forbidden(*args, **kwargs):
        pytest.fail("Missing-key UI must not instantiate a paid provider")
    monkeypatch.setattr(providers, "QwenText", forbidden)
    monkeypatch.setattr(providers, "QwenRealtime", forbidden)
    bootstrap = begin(client)
    reference = {"revision": bootstrap["state"]["revision"], "view_ids": ["v2"], "entities": {"v2": ["bed_bath_table"]}}
    with client.websocket_connect("/ws") as socket:
        assert socket.receive_json()["type"] == "bootstrap"
        socket.send_json({"type": "context", "reference": reference})
        socket.send_json({"type": "event", "name": "rendered", "client_ms": 120.5, "details": {"revision": reference["revision"]}})
        socket.send_json({"type": "text", "text": "Keep these categories and change the region to RJ.", "reference": reference})
        assert socket.receive_json()["type"] == "stop_audio"
        accepted_message = socket.receive_json()
        assert accepted_message["type"] == "request_accepted"
        error = socket.receive_json()
        assert error["type"] == "error" and "key" in error["message"]
        socket.send_json({"type": "voice_start", "mode": "live_voice", "reference": reference})
        assert socket.receive_json()["type"] == "error"
    exported = client.get("/api/export").json()
    accepted = next(e for e in exported["events"] if e["name"] == "request_accepted")
    assert accepted["request_id"] == accepted_message["request_id"]
    assert accepted["reference"] == reference
    rendered = next(e for e in exported["events"] if e["name"] == "rendered")
    assert rendered["client_ms"] == 120.5 and "server_ms" in rendered
    assert not any(e["name"] == "voice_connected" for e in exported["events"])


def test_bootstrap_and_export_do_not_contain_configured_credentials(tmp_path):
    secret = "test-sentinel-never-send-to-client"
    app = create_app(local_settings(tmp_path, api_key=secret))
    with TestClient(app) as connection:
        bootstrap = connection.get("/api/bootstrap")
        assert bootstrap.json()["settings"]["configured"] is True
        assert secret not in bootstrap.text
        assert secret not in connection.get("/api/export").text


def test_new_intent_revokes_prepared_work_before_public_commit(tmp_path):
    async def scenario():
        workspace = Workspace(local_settings(tmp_path))
        entered, release = Event(), Event()
        prepare = workspace.store.prepare
        def held_prepare(*args):
            result = prepare(*args)
            entered.set()
            assert release.wait(5)
            return result
        workspace.store.prepare = held_prepare
        task = asyncio.create_task(workspace.execute("create_chart", {"title": "Obsolete chart", "chart_type": "bar", "source": {}}))
        assert await asyncio.to_thread(entered.wait, 5)
        await workspace.revoke()
        release.set()
        receipt = await task
        assert receipt["status"] == "superseded"
        assert workspace.store.snapshot()["views"] == []
        assert workspace.nodes == []
        assert any(e["name"] == "tool_superseded" for e in workspace.trace.events)
        assert not any(e["name"] == "tool_committed" for e in workspace.trace.events)
        workspace.data.close()
    asyncio.run(scenario())
