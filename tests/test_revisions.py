"""Historical evidence selects members; current conditions remain authoritative."""

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from backend.charts import ChartStore
from backend.data import OlistData
from backend.revisions import prepare_revision
from backend.study import starter_operations


@pytest.fixture(scope="module")
def real_data():
    data = OlistData(Path("C:/VerbalVis/datasets/olist/data"))
    yield data
    data.close()


def regional_workspace(data):
    store = ChartStore(data)
    for name, args in starter_operations(data):
        store.commit(store.prepare(name, args))
    historical = store.snapshot()
    store.commit(store.prepare("edit_charts", {
        "view_ids": ["v1", "v2", "v3"],
        "patch": {"source": {"region": "MG", "categories": None, "top_n": 3, "rank_by": "orders"}},
    }))
    return store, {historical["revision"]: historical, store.state["revision"]: store.snapshot()}, historical


def payload(historical, **overrides):
    return {
        "evidence": {"revision": historical["revision"], "view_id": "v1"},
        "view_ids": ["v1", "v2", "v3"], "source_patch": {},
        "member_action": "use_evidence", **overrides,
    }


def test_old_sp_members_are_applied_to_current_mg_without_restore(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    before = store.snapshot()
    saved = deepcopy(snapshots)
    old_members = historical["views"][0]["data"]["selection"]["members"]
    assert old_members != before["views"][0]["data"]["selection"]["members"]

    result = prepare_revision(store, snapshots, payload(historical))
    assert store.snapshot() == before
    assert snapshots == saved
    assert result["card"]["binding_applied"] is True
    assert result["card"]["evidence"]["source"]["region"] == "SP"
    assert result["card"]["base_revision"] == before["revision"]
    after = store.commit(result["prepared"])["state"]
    for old, view, change in zip(before["views"], after["views"], result["card"]["changes"]):
        assert view["source"]["region"] == "MG"
        assert view["source"]["categories"] == old_members
        assert view["source"]["top_n"] is None
        for field in ("metric", "dimension", "region", "start", "end", "status", "rank_by"):
            assert view["source"][field] == old["source"][field]
            assert field in change["kept_fields"]
        assert change["after_members"] == old_members
        assert set(change["changed_fields"]) == {"categories", "top_n"}
        expected = real_data.query(view["source"])
        assert view["data"]["selection"] == expected["selection"]
        for actual_row, expected_row in zip(view["data"]["rows"], expected["rows"]):
            assert actual_row == pytest.approx(expected_row)


def test_metric_edit_keeps_evidence_members_and_current_period(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    store.commit(store.prepare("edit_charts", {
        "view_ids": ["v1"], "patch": {"source": {"start": "2017-04-01", "end": "2017-07-01"}},
    }))
    result = prepare_revision(store, snapshots, payload(historical, view_ids=["v1"], source_patch={"metric": "low_review_rate"}))
    view = store.commit(result["prepared"])["state"]["views"][0]
    assert (view["source"]["metric"], view["source"]["region"]) == ("low_review_rate", "MG")
    assert (view["source"]["start"], view["source"]["end"]) == ("2017-04-01", "2017-07-01")
    assert view["source"]["categories"] == historical["views"][0]["data"]["selection"]["members"]
    assert view["data"]["rows"][0]["value"] == pytest.approx(
        view["data"]["rows"][0]["low_review_count"] / view["data"]["rows"][0]["reviewed_orders"]
    )


def test_reference_subset_only_changes_requested_chart(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    before = store.snapshot()
    members = historical["views"][0]["data"]["selection"]["members"][1:]
    result = prepare_revision(store, snapshots, payload(historical, view_ids=["v2"], evidence={
        "revision": historical["revision"], "view_id": "v1", "members": members,
    }))
    after = store.commit(result["prepared"])["state"]
    assert after["views"][0] == before["views"][0]
    assert after["views"][2] == before["views"][2]
    assert after["views"][1]["source"]["categories"] == members
    assert result["card"]["view_ids"] == ["v2"]


def test_rerank_explicitly_releases_fixed_members(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    store.commit(prepare_revision(store, snapshots, payload(historical))["prepared"])
    result = prepare_revision(store, snapshots, {
        "view_ids": ["v1"], "source_patch": {"top_n": 3, "rank_by": "orders"},
        "member_action": "rerank",
    })
    view = store.commit(result["prepared"])["state"]["views"][0]
    assert view["source"]["categories"] is None
    assert view["source"]["top_n"] == 3
    assert view["data"]["selection"]["members"] != historical["views"][0]["data"]["selection"]["members"]
    assert result["card"]["binding_applied"] is False


def test_keep_current_does_not_freeze_a_ranking(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    result = prepare_revision(store, snapshots, {
        "view_ids": ["v1"], "source_patch": {"metric": "revenue"}, "member_action": "keep_current",
    })
    source = result["prepared"]["candidate"]["views"][0]["source"]
    assert source["categories"] is None
    assert source["top_n"] == 3
    assert source["rank_by"] == "orders"


def test_confirmation_is_preview_and_stale_candidate_is_not_rebased(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    result = prepare_revision(store, snapshots, payload(historical, needs_confirmation=True, question="Use the SP categories in MG?"))
    assert result["card"]["needs_confirmation"] is True
    assert result["card"]["question"] == "Use the SP categories in MG?"
    store.commit(store.prepare("edit_charts", {"view_ids": ["v1"], "patch": {"source": {"region": "RJ"}}}))
    before = store.snapshot()
    with pytest.raises(ValueError, match="changed while"):
        store.commit(result["prepared"])
    assert store.snapshot() == before


def test_evidence_members_must_come_from_the_referenced_chart(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    before = store.snapshot()
    invalid = payload(historical, evidence={"revision": historical["revision"], "view_id": "v1", "members": ["not_a_displayed_category"]})
    with pytest.raises(ValueError, match="actually displayed"):
        prepare_revision(store, snapshots, invalid)
    with pytest.raises(ValueError, match="conflict"):
        prepare_revision(store, snapshots, payload(historical, source_patch={"categories": ["not_a_displayed_category"], "top_n": None}))
    assert store.snapshot() == before


def test_rerank_requires_an_explicit_rule_and_cannot_overwrite_values(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    with pytest.raises(ValueError, match="explicit top_n"):
        prepare_revision(store, snapshots, {"view_ids": ["v1"], "source_patch": {}, "member_action": "rerank"})
    with pytest.raises(ValidationError):
        prepare_revision(store, snapshots, payload(historical, source_patch={"values": [999]}))


def test_direct_and_bound_compile_identical_actual_state(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    from backend.evidence_candidates import build_candidates, resolve_candidate
    candidates = build_candidates(snapshots, [])
    chosen = resolve_candidate(f"chart:{historical['revision']}:v1", candidates)
    args = {"candidate_id": chosen["candidate_id"], "view_ids": ["v2", "v3"],
            "source_patch": {"start": "2017-04-01", "end": "2017-07-01"}, "member_action": "use_evidence"}
    direct = prepare_revision(store, snapshots, args, "direct", chosen)
    bound = prepare_revision(store, snapshots, args, "bound_revision", chosen)
    for first, second in zip(direct["prepared"]["candidate"]["views"], bound["prepared"]["candidate"]["views"]):
        assert first["source"] == second["source"]
        assert first["data"]["selection"] == second["data"]["selection"]
        for row, other in zip(first["data"]["rows"], second["data"]["rows"]):
            assert row == pytest.approx(other)
    after = store.commit(direct["prepared"])["state"]
    assert after["views"][0] == snapshots[max(snapshots)]["views"][0]
    for view in after["views"][1:]:
        assert view["source"]["region"] == "MG"
        assert view["source"]["categories"] == chosen["members"]
        expected = real_data.query(view["source"])
        assert view["data"]["selection"] == expected["selection"]
        for row, expected_row in zip(view["data"]["rows"], expected["rows"]):
            assert row == pytest.approx(expected_row)


def test_saved_candidate_reuse_region_patch_and_explicit_release(real_data):
    from backend.category_sets import CategorySets
    from backend.evidence_candidates import build_candidates, resolve_candidate, prepare_candidate_apply
    store, snapshots, historical = regional_workspace(real_data)
    library = CategorySets()
    saved = library.save(snapshots, {"name": "SP cohort", "revision": historical["revision"], "view_id": "v1"})
    candidates = build_candidates(snapshots, library.list())
    chosen = resolve_candidate(f"set:{saved['id']}", candidates)
    before = store.snapshot()
    chosen["members"].append("local_copy_only")
    chosen = resolve_candidate(f"set:{saved['id']}", candidates)
    assert chosen["members"] == saved["members"]
    with pytest.raises(ValueError, match="Unknown evidence"):
        resolve_candidate("set:invented", candidates)
    with pytest.raises(ValueError, match="conflict"):
        prepare_candidate_apply(store, chosen, {"candidate_id": chosen["candidate_id"], "view_ids": ["v2"],
                                               "source_patch": {"categories": ["invented"]}})
    prepared = prepare_candidate_apply(store, chosen, {"candidate_id": chosen["candidate_id"], "view_ids": ["v2"],
                                                      "source_patch": {"region": "RJ"}})
    after = store.commit(prepared)["state"]
    assert after["views"][0] == before["views"][0]
    assert after["views"][2] == before["views"][2]
    source = after["views"][1]["source"]
    assert source["region"] == "RJ" and source["categories"] == saved["members"]
    for field in ("start", "end", "metric", "status", "dimension", "rank_by"):
        assert source[field] == before["views"][1]["source"][field]
    released = prepare_revision(store, snapshots, {"view_ids": ["v2"], "member_action": "rerank",
                                                "source_patch": {"top_n": 3, "rank_by": "orders"}}, "direct")
    assert released["card"]["changes"][0]["released_fields"] == ["categories"]
    result = store.commit(released["prepared"])["state"]
    assert result["views"][1]["source"]["categories"] is None
    expected = real_data.query(result["views"][1]["source"])
    for row, expected_row in zip(result["views"][1]["data"]["rows"], expected["rows"]):
        assert row == pytest.approx(expected_row)


@pytest.mark.parametrize("condition", ["direct", "bound_revision"])
def test_historical_reuse_then_partial_rerank_keeps_current_scope_and_distinct_cohorts(real_data, condition):
    store, snapshots, historical = regional_workspace(real_data)
    store.commit(store.prepare("edit_charts", {
        "view_ids": ["v2", "v3"],
        "patch": {"source": {"start": "2017-01-01", "end": "2017-07-01"}},
    }))
    initial = store.snapshot()
    reused = prepare_revision(store, snapshots, payload(historical, view_ids=["v2", "v3"]), condition)
    reused_state = store.commit(reused["prepared"])["state"]
    assert reused_state["views"][0] == initial["views"][0]
    historical_members = historical["views"][0]["data"]["selection"]["members"]
    for change in reused["card"]["changes"]:
        assert change["after_membership"] == {
            "mode": "fixed", "dimension": "category", "categories": historical_members,
            "top_n": None, "rank_by": None,
        }
    assert reused["card"]["source_patch"] == {"categories": historical_members, "top_n": None}

    released = prepare_revision(store, snapshots, {
        "view_ids": ["v2"], "source_patch": {"top_n": 3, "rank_by": "orders"},
        "member_action": "rerank",
    }, condition)
    card = deepcopy(released["card"])
    final = store.commit(released["prepared"])["state"]
    assert final["views"][0] == initial["views"][0]
    assert final["views"][2] == reused_state["views"][2]
    target = final["views"][1]
    assert target["source"]["categories"] is None
    assert target["source"]["region"] == "MG"
    assert (target["source"]["start"], target["source"]["end"]) == ("2017-01-01", "2017-07-01")
    assert target["source"]["metric"] == reused_state["views"][1]["source"]["metric"]
    assert target["data"]["selection"]["members"] != historical_members
    assert final["views"][2]["source"]["categories"] == historical_members
    assert card["changed_view_ids"] == ["v2"]
    assert card["kept_view_ids"] == ["v1", "v3"]
    assert [view["view_id"] for view in card["untouched_views"]] == ["v1", "v3"]
    change = card["changes"][0]
    assert change["released_fields"] == ["categories"]
    assert change["before_membership"]["mode"] == "fixed"
    assert change["after_membership"] == {
        "mode": "ranked", "dimension": "category", "categories": None,
        "top_n": 3, "rank_by": "orders",
    }
    assert change["after_members"] == target["data"]["selection"]["members"]
    for untouched in card["untouched_views"]:
        actual = next(view for view in final["views"] if view["id"] == untouched["view_id"])
        assert untouched["source"] == actual["source"]
        assert untouched["members"] == actual["data"]["selection"]["members"]
    # A later edit must not rewrite what this earlier interpretation actually preserved.
    store.commit(store.prepare("edit_charts", {"view_ids": ["v3"], "patch": {"source": {"region": "RJ"}}}))
    assert released["card"] == card


def test_fixed_category_scope_is_distinct_from_displayed_month_members(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    result = prepare_revision(store, snapshots, payload(historical, view_ids=["v2"], source_patch={"dimension": "month"}))
    change = result["card"]["changes"][0]
    assert change["after_membership"]["mode"] == "fixed"
    assert change["after_membership"]["categories"] == result["card"]["evidence"]["members"]
    assert change["after_membership"]["dimension"] == "month"
    assert change["after_members"] != change["after_membership"]["categories"]
    assert all(label.startswith("2017-") for label in change["after_members"])


def test_noop_targets_are_kept_and_patch_does_not_copy_distinct_metrics(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    before = store.snapshot()
    assert before["views"][1]["source"]["metric"] != before["views"][2]["source"]["metric"]
    result = prepare_revision(store, snapshots, {
        "view_ids": ["v2", "v3"], "source_patch": {}, "member_action": "keep_current",
    })
    assert result["card"]["source_patch"] == {}
    assert result["card"]["changed_view_ids"] == []
    assert result["card"]["kept_view_ids"] == ["v1", "v2", "v3"]
    assert result["prepared"]["candidate"] == before
