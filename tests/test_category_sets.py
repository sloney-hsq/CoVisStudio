"""Saved sets carry real members into current conditions through ordinary commits."""

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from backend.category_sets import CategorySets
from backend.charts import ChartStore
from backend.data import OlistData
from backend.oracle import category_rows, numeric_rows_equal
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
    return store, {historical["revision"]: historical}, historical


def save_historical(sets, snapshots, historical, **extra):
    return sets.save(snapshots, {
        "name": "SP priority categories", "revision": historical["revision"], "view_id": "v1", **extra,
    })


def test_save_subset_is_immutable_and_does_not_edit_canvas(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    before, old_snapshots = store.snapshot(), deepcopy(snapshots)
    sets = CategorySets()
    members = historical["views"][0]["data"]["selection"]["members"][1:]
    saved = save_historical(sets, snapshots, historical, members=members)
    expected = deepcopy(saved)
    assert saved["members"] == members
    assert saved["evidence"]["source"]["region"] == "SP"
    assert (saved["evidence"]["revision"], saved["evidence"]["view_id"]) == (historical["revision"], "v1")
    assert store.snapshot() == before
    assert snapshots == old_snapshots

    saved["members"].clear()
    saved["evidence"]["source"]["region"] = "RJ"
    listed = sets.list()
    assert listed == [expected]
    listed[0]["members"].append("not_a_category")
    assert sets.list() == [expected]
    second = save_historical(sets, snapshots, historical)
    assert second["id"] != expected["id"]
    assert sets.list()[0] == expected


def test_apply_retains_current_mg_metrics_and_commits_real_values(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    sets = CategorySets()
    saved = save_historical(sets, snapshots, historical)
    before = store.snapshot()
    assert before["views"][0]["data"]["selection"]["members"] != saved["members"]
    prepared = sets.prepare_apply(store, {"set_id": saved["id"], "view_ids": ["v1", "v2", "v3"]})
    assert store.snapshot() == before
    receipt = store.commit(prepared)
    assert receipt["result"]["committed"] is True
    assert receipt["result"]["tool"] == "apply_category_set"
    assert receipt["result"]["category_set"] == saved
    assert receipt["state"]["revision"] == before["revision"] + 1
    for old, view in zip(before["views"], receipt["state"]["views"]):
        assert view["source"] == {**old["source"], "categories": saved["members"], "top_n": None}
        assert view["source"]["region"] == "MG"
        assert view["data"]["selection"]["members"] == saved["members"]
        assert numeric_rows_equal(view["data"]["rows"], category_rows(real_data, view["source"]))


def test_reranking_source_chart_does_not_change_saved_set(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    sets = CategorySets()
    saved = save_historical(sets, snapshots, historical)
    store.commit(store.prepare("edit_charts", {
        "view_ids": ["v1"],
        "patch": {"source": {"categories": None, "top_n": 2, "rank_by": "revenue"}},
    }))
    before = store.snapshot()
    assert before["views"][0]["data"]["selection"]["members"] != saved["members"]
    assert sets.list() == [saved]
    prepared = sets.prepare_apply(store, {"set_id": saved["id"], "view_ids": ["v2"]})
    after = store.commit(prepared)["state"]
    assert after["views"][0] == before["views"][0]
    assert after["views"][2] == before["views"][2]
    assert after["views"][1]["source"] == {
        **before["views"][1]["source"], "categories": saved["members"], "top_n": None,
    }
    assert sets.list() == [saved]


def test_subset_application_changes_only_explicit_target_and_source_patch(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    sets = CategorySets()
    saved = save_historical(sets, snapshots, historical,
                            members=historical["views"][0]["data"]["selection"]["members"][1:])
    store.commit(store.prepare("edit_charts", {
        "view_ids": ["v2"], "patch": {"source": {"start": "2017-04-01", "end": "2017-07-01"}},
    }))
    before = store.snapshot()
    prepared = sets.prepare_apply(store, {
        "set_id": saved["id"], "view_ids": ["v2"],
        "source_patch": {"metric": "revenue", "categories": list(reversed(saved["members"])), "top_n": None},
    })
    after = store.commit(prepared)["state"]
    assert after["views"][0] == before["views"][0]
    assert after["views"][2] == before["views"][2]
    view = after["views"][1]
    assert view["source"] == {
        **before["views"][1]["source"], "metric": "revenue", "categories": saved["members"], "top_n": None,
    }
    assert numeric_rows_equal(view["data"]["rows"], category_rows(real_data, view["source"]))


@pytest.mark.parametrize("change, message", [
    ({"revision": 999}, "not saved"),
    ({"view_id": "v999"}, "not present"),
    ({"members": ["not_a_displayed_category"]}, "actually displayed"),
])
def test_save_requires_real_saved_reference_and_displayed_members(real_data, change, message):
    store, snapshots, historical = regional_workspace(real_data)
    sets = CategorySets()
    before = store.snapshot()
    with pytest.raises(ValueError, match=message):
        save_historical(sets, snapshots, historical, **change)
    assert sets.list() == []
    assert store.snapshot() == before


def test_save_rejects_month_chart_as_category_evidence(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    store.commit(store.prepare("edit_charts", {
        "view_ids": ["v1"], "patch": {"source": {"dimension": "month"}},
    }))
    current = store.snapshot()
    sets = CategorySets()
    with pytest.raises(ValueError, match="grouped by product category"):
        sets.save({current["revision"]: current}, {
            "name": "Months", "revision": current["revision"], "view_id": "v1",
        })
    assert sets.list() == []


@pytest.mark.parametrize("change, error, message", [
    ({"set_id": "cs999"}, ValueError, "Unknown category set"),
    ({"view_ids": ["v999"]}, ValueError, "Unknown chart IDs"),
    ({"source_patch": {"categories": ["not_a_saved_category"]}}, ValueError, "conflict"),
    ({"source_patch": {"categories": None}}, ValueError, "conflict"),
    ({"source_patch": {"top_n": 3}}, ValueError, "ranking"),
    ({"source_patch": {"values": [999]}}, ValidationError, "Additional properties"),
])
def test_apply_rejects_wrong_targets_and_conflicting_member_requests(real_data, change, error, message):
    store, snapshots, historical = regional_workspace(real_data)
    sets = CategorySets()
    saved = save_historical(sets, snapshots, historical)
    before = store.snapshot()
    with pytest.raises(error, match=message):
        sets.prepare_apply(store, {"set_id": saved["id"], "view_ids": ["v1"], **change})
    assert store.snapshot() == before
    assert sets.list() == [saved]


def test_prepared_set_application_uses_normal_stale_commit_check(real_data):
    store, snapshots, historical = regional_workspace(real_data)
    sets = CategorySets()
    saved = save_historical(sets, snapshots, historical)
    prepared = sets.prepare_apply(store, {"set_id": saved["id"], "view_ids": ["v1"]})
    store.commit(store.prepare("edit_charts", {"view_ids": ["v1"], "patch": {"source": {"region": "RJ"}}}))
    before = store.snapshot()
    with pytest.raises(ValueError, match="changed while"):
        store.commit(prepared)
    assert store.snapshot() == before
