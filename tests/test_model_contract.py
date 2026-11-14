"""Native count strings are an explicit contract, separate from strict domain sources."""

from copy import deepcopy
import asyncio
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from backend.category_sets import CATEGORY_SET_TOOL_DEFINITIONS
from backend.charts import TOOL_DEFINITIONS
from backend.data import SOURCE_SCHEMA
from backend.evidence_candidates import EVIDENCE_CANDIDATE_TOOL_DEFINITIONS
from backend.model_contract import TOP_N_PATHS, compile_model_arguments, model_tool_definitions
from backend.revisions import REVISION_TOOL_DEFINITIONS, normalize_revise_analysis, prepare_revision
from test_revisions import real_data, regional_workspace


DOMAIN_TOOLS = [*TOOL_DEFINITIONS, *REVISION_TOOL_DEFINITIONS,
                *CATEGORY_SET_TOOL_DEFINITIONS, *EVIDENCE_CANDIDATE_TOOL_DEFINITIONS]
MODEL_TOOLS = model_tool_definitions(DOMAIN_TOOLS)


@pytest.mark.parametrize("name,args", [
    ("revise_analysis", {"view_ids": ["v2"], "member_action": "rerank", "top_n": "3", "rank_by": "orders"}),
    ("preview_revision", {"view_ids": ["v2"], "member_action": "rerank", "source_patch": {"top_n": "3", "rank_by": "orders"}}),
    ("create_chart", {"title": "Orders", "chart_type": "bar", "source": {"top_n": "3"}}),
    ("edit_charts", {"view_ids": ["v2"], "patch": {"source": {"top_n": "3"}}}),
    ("apply_category_set", {"set_id": "cs1", "view_ids": ["v2"], "source_patch": {"top_n": "3"}}),
    ("apply_evidence_candidate", {"candidate_id": "set:cs1", "view_ids": ["v2"], "source_patch": {"top_n": "3"}}),
])
def test_all_source_tools_compile_same_explicit_wire_count(name, args):
    original = deepcopy(args)
    compiled = compile_model_arguments(name, args, MODEL_TOOLS)
    value = compiled
    for field in TOP_N_PATHS[name]:
        value = value[field]
    assert value == 3 and type(value) is int
    assert args == original
    domain_schema = next(tool["function"]["parameters"] for tool in DOMAIN_TOOLS
                         if tool["function"]["name"] == name)
    validate(compiled, domain_schema)
    with pytest.raises(ValidationError):
        validate(args, domain_schema)


@pytest.mark.parametrize("value", [3, 3.0, True, "0", "03", "-3", "3.0", " 3", "3 ", "3\n", {}, [], "three"])
def test_malformed_or_wrong_wire_types_rejected(value):
    with pytest.raises(ValidationError):
        compile_model_arguments("revise_analysis", {
            "view_ids": ["v2"], "member_action": "rerank", "top_n": value,
            "rank_by": "orders"}, MODEL_TOOLS)


def test_null_omission_and_manual_domain_remain_distinct():
    base = {"view_ids": ["v2"], "member_action": "keep_current"}
    assert compile_model_arguments("revise_analysis", base, MODEL_TOOLS) == base
    assert compile_model_arguments("revise_analysis", {**base, "top_n": None}, MODEL_TOOLS)["top_n"] is None
    validate({"top_n": 3}, SOURCE_SCHEMA)
    with pytest.raises(ValidationError):
        validate({"top_n": "3"}, SOURCE_SCHEMA)
    assert SOURCE_SCHEMA["properties"]["top_n"]["type"] == ["integer", "null"]


@pytest.mark.parametrize("condition", ["direct", "bound_revision"])
def test_wire_rerank_uses_real_olist_and_preserves_scope(real_data, condition):
    store, snapshots, _ = regional_workspace(real_data)
    # A prior fixed set must be released while current MG/date/metric scope survives.
    members = snapshots[min(snapshots)]["views"][0]["data"]["selection"]["members"]
    store.commit(store.prepare("edit_charts", {"view_ids": ["v2"], "patch": {"source": {
        "categories": members, "top_n": None, "metric": "revenue",
        "start": "2017-04-01", "end": "2017-07-01"}}}))
    before = store.snapshot()
    raw = {"view_ids": ["v2"], "member_action": "rerank", "top_n": "3", "rank_by": "orders"}
    compiled = compile_model_arguments("revise_analysis", raw, MODEL_TOOLS)
    prepared = prepare_revision(store, snapshots, normalize_revise_analysis(compiled), condition)
    after = store.commit(prepared["prepared"])["state"]
    assert raw["top_n"] == "3"
    assert after["views"][0] == before["views"][0]
    assert after["views"][2] == before["views"][2]
    target = after["views"][1]
    assert target["source"] == {**before["views"][1]["source"], "categories": None,
                                "top_n": 3, "rank_by": "orders"}
    expected = real_data.query(target["source"])
    assert target["data"]["selection"] == expected["selection"]
    assert len(expected["selection"]["members"]) == 3
    for row, expected_row in zip(target["data"]["rows"], expected["rows"]):
        assert row == pytest.approx(expected_row)


@pytest.mark.parametrize("count", ["omitted", None])
def test_omission_retains_and_null_releases_dynamic_rule(real_data, count):
    store, snapshots, _ = regional_workspace(real_data)
    before = store.snapshot()
    raw = {"view_ids": ["v2"], "member_action": "keep_current"}
    if count is None:
        raw["top_n"] = None
    args = compile_model_arguments("revise_analysis", raw, MODEL_TOOLS)
    result = prepare_revision(store, snapshots, normalize_revise_analysis(args))
    target = result["prepared"]["candidate"]["views"][1]
    assert target["source"]["top_n"] == (3 if count == "omitted" else None)
    assert target["source"] == {**before["views"][1]["source"],
                                "top_n": 3 if count == "omitted" else None}
    assert store.snapshot() == before


@pytest.fixture(scope="module")
def gateway_workspace(tmp_path_factory):
    from backend.app import Workspace
    ws = Workspace({"api_key": "", "text_model": "offline", "realtime_model": "offline",
                    "voice": "Maia", "text_url": "http://127.0.0.1:9/disabled",
                    "realtime_url": "ws://127.0.0.1:9/disabled",
                    "data_dir": Path("C:/VerbalVis/datasets/olist/data"),
                    "trace_dir": tmp_path_factory.mktemp("model-contract")})
    yield ws
    ws.data.close()


def test_model_gateway_raw_trace_real_commit_and_b0_b2_parity(gateway_workspace):
    from backend.app import MODEL_TOOLS as advertised_tools
    from backend.oracle import category_rows, numeric_rows_equal

    async def run():
        finals = []
        ws = gateway_workspace
        for condition in ("direct", "bound_revision"):
            ws.reset("text", "starter", "", condition)
            await ws.execute("edit_charts", {"view_ids": ["v2"], "patch": {"source": {
                "region": "MG", "start": "2017-04-01", "end": "2017-07-01",
                "metric": "revenue"}}}, actor="user")
            before = ws.store.snapshot()
            ws.accept("Rerank chart two by the top three order counts.", ws.reference)
            context = await ws.provider_event({"type": "response_start", "response_id": "rank"})
            raw = {"view_ids": ["v2"], "member_action": "rerank", "top_n": "3", "rank_by": "orders"}
            result = await ws.execute_model("revise_analysis", raw, call_context=context)
            assert result["committed"] is True
            after = ws.store.snapshot()
            assert after["revision"] == before["revision"] + 1
            assert after["views"][0] == before["views"][0]
            assert after["views"][2] == before["views"][2]
            target = after["views"][1]
            assert target["source"] == {**before["views"][1]["source"],
                                        "categories": None, "top_n": 3, "rank_by": "orders"}
            assert numeric_rows_equal(target["data"]["rows"], category_rows(ws.data, target["source"]))
            compiled = [event for event in ws.trace.events if event["name"] == "model_arguments_compiled"]
            assert len(compiled) == 1
            assert compiled[0]["arguments"] == raw
            assert compiled[0]["compiled_arguments"] == {**raw, "top_n": 3}
            assert compiled[0]["contract"] == "decimal-top-n-v1"
            assert next(tool for tool in advertised_tools if tool["function"]["name"] == "revise_analysis") == next(
                tool for tool in MODEL_TOOLS if tool["function"]["name"] == "revise_analysis")
            finals.append(after)
        for direct, bound in zip(finals[0]["views"], finals[1]["views"]):
            assert direct["source"] == bound["source"]
            assert direct["data"]["selection"] == bound["data"]["selection"]
            assert numeric_rows_equal(direct["data"]["rows"], bound["data"]["rows"])
    asyncio.run(run())


def test_model_gateway_failure_once_and_internal_manual_integer_unchanged(gateway_workspace):
    async def run():
        ws = gateway_workspace
        ws.reset("text", "starter", "", "direct")
        before = ws.store.snapshot()
        result = await ws.execute_model("revise_analysis", {"view_ids": ["v2"],
            "member_action": "rerank", "top_n": "3.0", "rank_by": "orders"})
        assert result["status"] == "failed" and result["committed"] is False
        assert ws.store.snapshot() == before
        assert len([e for e in ws.trace.events if e["name"] == "tool_failed"]) == 1
        assert len([e for e in ws.trace.events if e["name"] == "tool_feedback"]) == 1
        assert not [e for e in ws.trace.events if e["name"] == "model_arguments_compiled"]
        for actor in ("user", "model"):
            result = await ws.execute("revise_analysis", {"view_ids": ["v2"],
                "member_action": "rerank", "top_n": 3, "rank_by": "orders"}, actor=actor)
            assert result["committed"] is True
            assert ws.store.state["views"][1]["source"]["top_n"] == 3
        assert not [e for e in ws.trace.events if e["name"] == "model_arguments_compiled"]
    asyncio.run(run())

