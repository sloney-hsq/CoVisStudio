"""Scenario file integrity, setup through real chart operations, cumulative truth and scoring.

Uses a deterministic stand-in query so these logic checks run without the Olist CSVs;
they say nothing about real-data values or model behaviour.
"""
from copy import deepcopy
import itertools

import pytest

from backend.charts import ChartStore
from backend.data import SOURCE_SCHEMA
from backend.scenarios import (apply_setup, compare_view, expected_turn_sources, load_scenarios,
                               missing_critical_words, scenario_index, score_scenario)

CATEGORIES = ["bed_bath_table", "health_beauty", "sports_leisure", "furniture_decor",
              "computers_accessories", "housewares", "watches_gifts", "telephony"]


class StandInData:
    """Rank depends on region and dates so different scopes yield different leaders."""

    def query(self, source):
        seed = sum(map(ord, f"{source['region']}{source['start']}{source['end']}{source['status']}"))
        ranked = sorted(CATEGORIES, key=lambda name: (sum(map(ord, name)) * seed) % 997)
        if source["categories"] is not None and source["dimension"] == "category":
            labels = list(source["categories"])
        elif source["top_n"] is not None:
            labels = ranked[:source["top_n"]]
        else:
            labels = ranked
        rows = [{"label": label, "value": float(index + 1)} for index, label in enumerate(labels)]
        return {"rows": rows, "columns": [], "definition": "",
                "selection": {"mode": "fixed" if source["categories"] else "ranked",
                              "members": labels}}


@pytest.fixture(scope="module")
def scenarios():
    return load_scenarios()


def commit_into(store, log):
    def commit(name, args):
        receipt = store.commit(store.prepare(name, args))
        log.append((name, deepcopy(args)))
        return receipt
    return commit


def members_for_source(source):
    return [row["label"] for row in StandInData().query(source)["rows"]]


def test_sixteen_scenarios_five_to_nine_turns_and_valid_fields(scenarios):
    assert sorted(scenarios) == [f"S{n:02d}" for n in range(1, 17)]
    metrics = set(SOURCE_SCHEMA["properties"]["metric"]["enum"])
    for scenario in scenarios.values():
        assert 5 <= len(scenario["turns"]) <= 9
        for turn in scenario["turns"]:
            if turn["speaker"] != "user":
                continue
            assert (turn["expect"]["action"] == "edit") == bool(turn["expect"]["changed_views"])
            for spec in turn["expect"]["state_after"].values():
                assert spec["metric"] in metrics
    listing = scenario_index(scenarios)
    assert all("goal" not in item and "expect" not in str(item) for item in listing)


@pytest.mark.parametrize("scenario_id", [f"S{n:02d}" for n in range(1, 17)])
def test_setup_builds_labelled_snapshots_matching_the_spec(scenarios, scenario_id):
    scenario = scenarios[scenario_id]
    store, log = ChartStore(StandInData()), []
    labels, states = apply_setup(scenario, commit_into(store, log))
    assert set(labels) == {*scenario["setup"]["history"], "current"}
    current = states[labels["current"]]
    assert [view["id"] for view in current["views"]] == ["v1", "v2", "v3"]
    for view in current["views"]:
        spec = scenario["setup"]["current"][view["id"]]
        assert view["source"]["region"] == spec["region"]
        assert (view["source"]["start"], view["source"]["end"]) == (spec["start"], spec["end"])
        rule = spec["membership"]
        if rule["rule"] == "ranked":
            assert view["source"]["top_n"] == rule["top_n"] and view["source"]["categories"] is None
        else:
            label, source_view = rule["from"].split(":")
            historical = next(v for v in states[labels[label]]["views"] if v["id"] == source_view)
            assert view["source"]["categories"] == [row["label"] for row in historical["data"]["rows"]]
    assert all(name in ("create_chart", "edit_charts") for name, _ in log)


def test_after_turn_membership_resolves_from_expected_not_observed_state(scenarios):
    scenario = scenarios["S14"]
    store = ChartStore(StandInData())
    labels, states = apply_setup(scenario, commit_into(store, []))
    expected = expected_turn_sources(scenario, labels, states, members_for_source)
    v1_after_t5 = expected[5]["v1"]
    assert v1_after_t5["region"] == "RJ" and v1_after_t5["top_n"] == 5
    assert expected[7]["v2"]["categories"] == members_for_source(v1_after_t5)
    assert expected[7]["v2"]["region"] == "MG" and expected[7]["v2"]["top_n"] is None


def test_played_prefix_is_unknown_until_human_coded(scenarios):
    scenario = scenarios["S05"]
    store = ChartStore(StandInData())
    labels, states = apply_setup(scenario, commit_into(store, []))
    assert expected_turn_sources(scenario, labels, states, members_for_source)[3]["v1"] is None
    coded = expected_turn_sources(scenario, labels, states, members_for_source,
                                  {"played:T2": ["bed_bath_table", "telephony"]})
    assert coded[3]["v2"]["categories"] == ["bed_bath_table", "telephony"]


def test_critical_words_fold_accents_hyphens_and_case():
    assert missing_critical_words("Use the Sao Paulo categories, low review rate.",
                                  ["São Paulo", "low-review rate"]) == []
    assert missing_critical_words("These fixed categories", ["Release", "fixed"]) == ["Release"]


def test_compare_view_distinguishes_rule_ranking_and_members():
    base = {"metric": "orders", "dimension": "category", "region": "MG", "start": "2017-01-01",
            "end": "2018-01-01", "status": "delivered"}
    fixed = {**base, "categories": ["a", "b"], "top_n": None, "rank_by": "orders"}
    ranked = {**base, "categories": None, "top_n": 3, "rank_by": "orders"}
    assert compare_view(fixed, {"source": {**fixed, "categories": ["b", "a"]}})["status"] == "match"
    assert compare_view(fixed, {"source": ranked})["fields"] == ["fixed_members"]
    assert compare_view(ranked, {"source": fixed})["fields"] == ["membership_rule"]
    assert compare_view(ranked, {"source": {**ranked, "rank_by": "revenue"}})["fields"] == ["ranking"]
    assert compare_view({**ranked, "region": "RJ"}, {"source": ranked})["fields"] == ["region"]
    assert compare_view(None, {"source": ranked})["status"] == "unknown"


def simulate(scenario, wrong_turn=None):
    """Commit each expected edit as a perfect agent would, optionally restoring old scope once."""
    store = ChartStore(StandInData())
    labels, states = apply_setup(scenario, commit_into(store, []))
    expected = expected_turn_sources(scenario, labels, states, members_for_source,
                                     {"played:T2": CATEGORIES[:3]})
    counter, events, windows = itertools.count(), [], []

    def record(name, **fields):
        events.append({"index": next(counter), "name": name, **fields})

    for turn in scenario["turns"]:
        if turn["speaker"] != "user":
            continue
        windows.append({"turn": turn["turn"], "start_index": len(events)})
        if "BC" in turn["tags"]:
            record("backchannel_ignored", event={"text": turn["text"]})
            continue
        record("request_accepted", text=turn["text"])
        if turn["expect"]["action"] != "edit":
            continue
        for view_id in turn["expect"]["changed_views"]:
            source = deepcopy(expected[turn["turn"]][view_id])
            if turn["turn"] == wrong_turn:
                source["region"] = "SP" if source["region"] != "SP" else "RJ"
            receipt = store.commit(store.prepare("edit_charts", {"view_ids": [view_id], "patch": {"source": source}}))
            states[receipt["state"]["revision"]] = receipt["state"]
            record("tool_committed")
            record("node_created", node={"revision": receipt["state"]["revision"]})
    return labels, states, events, windows


@pytest.mark.parametrize("scenario_id", [f"S{n:02d}" for n in range(1, 17)])
def test_perfect_agent_scores_every_turn_correct(scenarios, scenario_id):
    scenario = scenarios[scenario_id]
    labels, states, events, windows = simulate(scenario)
    score = score_scenario(scenario, events, states, labels, members_for_source,
                           turn_windows=windows, codings={"played:T2": CATEGORIES[:3]})
    assert score["summary"]["correct"] == score["summary"]["user_turns"], score["turns"]
    assert score["summary"]["terminal_state_correct"] in (True, None)


def test_old_scope_restored_is_a_decision_error_with_the_right_field(scenarios):
    scenario = scenarios["S16"]
    labels, states, events, windows = simulate(scenario, wrong_turn=3)
    score = score_scenario(scenario, events, states, labels, members_for_source, turn_windows=windows)
    row = next(row for row in score["turns"] if row["turn"] == 3)
    assert row["first_cause"] == "decision"
    assert row["views"]["v2"]["fields"] == ["region"]
    assert row["views"]["v1"]["status"] == "match"


def test_acknowledgement_that_becomes_a_request_is_a_segmentation_error(scenarios):
    scenario = scenarios["S04"]
    labels, states, events, windows = simulate(scenario)
    for event in events:
        if event["name"] == "backchannel_ignored":
            event.update(name="request_accepted", text=event["event"]["text"])
            break
    score = score_scenario(scenario, events, states, labels, members_for_source, turn_windows=windows)
    assert score["turns"][1]["first_cause"] == "segmentation_timing"
