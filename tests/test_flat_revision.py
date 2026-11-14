"""Flat model edits reuse the existing real-query revision compiler."""

from copy import deepcopy

import pytest
from jsonschema import ValidationError, validate

from backend.evidence_candidates import build_candidates, resolve_candidate
from backend.revisions import (
    REVISION_SCHEMA, REVISION_TOOL_DEFINITIONS, normalize_revise_analysis, prepare_revision,
)
from test_revisions import real_data, regional_workspace


@pytest.mark.parametrize("extra", [
    {"source_patch": '{"start":"2017-01-01"}'},
    {"source_patch": {"start": "2017-01-01"}},
    {"evidence": '{"revision":1,"view_id":"v1"}'},
    {"evidence": {"revision": 1, "view_id": "v1"}},
    {"categories": '["bed_bath_table"]'}, {"view_ids": '["v1"]'},
    {"top_n": "3"}, {"needs_confirmation": "false"}, {"candidate_id": 1},
    {"region": {"state": "MG"}},
])
def test_flat_contract_rejects_nested_and_wrong_types(extra):
    with pytest.raises(ValidationError):
        normalize_revise_analysis({"view_ids": ["v1"], "member_action": "keep_current", **extra})


def test_preview_model_schema_excludes_evidence_but_internal_calls_retain_it():
    preview = next(t["function"] for t in REVISION_TOOL_DEFINITIONS
                   if t["function"]["name"] == "preview_revision")
    payload = {"view_ids": ["v1"], "member_action": "use_evidence", "source_patch": {},
               "evidence": {"revision": 1, "view_id": "v1"}}
    validate(payload, REVISION_SCHEMA)
    with pytest.raises(ValidationError):
        validate(payload, preview["parameters"])


def test_minimal_date_edit_preserves_current_rule_and_other_views(real_data):
    store, snapshots, _ = regional_workspace(real_data)
    before = store.snapshot()
    args = {"view_ids": ["v2", "v3"], "member_action": "keep_current",
            "start": "2017-01-01", "end": "2017-04-01"}
    original = deepcopy(args)
    payload = normalize_revise_analysis(args)
    assert payload["source_patch"] == {"start": "2017-01-01", "end": "2017-04-01"}
    result = prepare_revision(store, snapshots, payload)
    assert args == original and store.snapshot() == before
    after = store.commit(result["prepared"])["state"]
    assert after["views"][0] == before["views"][0]
    for old, new in zip(before["views"][1:], after["views"][1:]):
        assert new["source"] == {**old["source"], **payload["source_patch"]}


@pytest.mark.parametrize("condition", ["direct", "bound_revision"])
@pytest.mark.parametrize("explicit_candidate", [False, True])
def test_evidence_reuse_and_rerank_preserve_current_scope(real_data, condition, explicit_candidate):
    store, snapshots, historical = regional_workspace(real_data)
    store.commit(store.prepare("edit_charts", {"view_ids": ["v2"], "patch": {"source": {
        "start": "2017-04-01", "end": "2017-07-01", "metric": "revenue"}}}))
    before = store.snapshot()
    reference = {"revision": historical["revision"], "view_id": "v1"}
    chosen = resolve_candidate(f"chart:{historical['revision']}:v1", build_candidates(snapshots, []))
    args = {"view_ids": ["v2"], "member_action": "use_evidence"}
    if explicit_candidate:
        args["candidate_id"] = chosen["candidate_id"]
    payload = normalize_revise_analysis(args)
    if not explicit_candidate:
        payload["evidence"] = reference  # Application-bound selection, never model arguments.
    prepared = prepare_revision(store, snapshots, payload, condition, chosen if explicit_candidate else None)
    after = store.commit(prepared["prepared"])["state"]
    expected = {**before["views"][1]["source"], "categories": chosen["members"], "top_n": None}
    assert after["views"][1]["source"] == expected
    assert after["views"][0] == before["views"][0]
    assert after["views"][2] == before["views"][2]
    rerank = normalize_revise_analysis({"view_ids": ["v2"], "member_action": "rerank",
                                         "top_n": 3, "rank_by": "orders"})
    released = prepare_revision(store, snapshots, rerank, condition)
    result = store.commit(released["prepared"])["state"]["views"][1]
    assert result["source"] == {**expected, "categories": None, "top_n": 3, "rank_by": "orders"}
    expected_data = real_data.query(result["source"])
    assert result["data"]["selection"] == expected_data["selection"]
    for row, expected_row in zip(result["data"]["rows"], expected_data["rows"]):
        assert row == pytest.approx(expected_row)
