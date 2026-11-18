"""Evaluator-private voice re-planning scenarios: setup, cumulative expected state, scoring.

Nothing here enters model context. Scenario goals, notes and ground truth stay in
researcher routes and score files. Expected category members are resolved from real
snapshots or real queries, never written into the scenario file.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import unicodedata

from .data import METRICS
from .settings import ROOT

SCENARIO_FILE = ROOT / "docs" / "voice_replan_scenarios.json"
SCENARIO_PROTOCOL = "covis-voice-replan-0.1"
FIELDS = ("metric", "dimension", "region", "start", "end", "status")
VIEW_ORDER = ("v1", "v2", "v3")


def load_scenarios(path=SCENARIO_FILE):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["protocol"] == SCENARIO_PROTOCOL, payload["protocol"]
    return {scenario["id"]: scenario for scenario in payload["scenarios"]}


def scenario_index(scenarios):
    """Researcher listing; carries utterances and timing, not goals or ground truth."""
    return [{"id": s["id"], "title": s["title"], "replan": s["replan"],
             "turns": [{"turn": t["turn"], "speaker": t["speaker"], "timing": t.get("timing"),
                        "text": t.get("text"), "pauses": t.get("pauses", []), "tags": t.get("tags", [])}
                       for t in s["turns"]],
             "summary": s["summary"]} for s in scenarios.values()]


# Setup ------------------------------------------------------------------------
def _members(state, view_id):
    view = next(view for view in state["views"] if view["id"] == view_id)
    return [row["label"] for row in view["data"]["rows"]]


def build_source(spec, members_of):
    source = {field: spec[field] for field in FIELDS}
    membership = spec["membership"]
    if membership["rule"] == "ranked":
        source.update(categories=None, top_n=membership["top_n"], rank_by=membership["rank_by"])
    else:
        source.update(categories=members_of(membership["from"]), top_n=None)
    return source


def apply_setup(scenario, commit):
    """Commit history snapshots, then the current canvas, through real chart operations.

    commit(name, args) must prepare+commit and return the receipt. Returns the revision
    of each labelled snapshot and the committed states keyed by revision.
    """
    labels, states = {}, {}

    def members_of(origin):
        label, view_id = origin.split(":")
        return _members(states[labels[label]], view_id)

    snapshots = [*scenario["setup"]["history"].items(), ("current", scenario["setup"]["current"])]
    state = None
    for label, snapshot in snapshots:
        for view_id in VIEW_ORDER:
            source = build_source(snapshot[view_id], members_of)
            if state is None or view_id not in {view["id"] for view in state["views"]}:
                receipt = commit("create_chart", {"title": METRICS[source["metric"]]["label"],
                                                  "chart_type": "bar", "source": source})
            else:
                current = next(view for view in state["views"] if view["id"] == view_id)
                if current["source"] == {**current["source"], **source}:
                    continue
                receipt = commit("edit_charts", {"view_ids": [view_id], "patch": {"source": source}})
            state = receipt["state"]
            states[state["revision"]] = deepcopy(state)
            assert view_id in {view["id"] for view in state["views"]}, (scenario["id"], view_id)
        labels[label] = state["revision"]
    return labels, states


# Expected state ---------------------------------------------------------------
def expected_turn_sources(scenario, labels, snapshots, members_for_source, codings=None):
    """Resolve each user turn's cumulative expected sources.

    members_for_source(source) returns the members a real query displays; it resolves
    after:T#:v# from the expected (not observed) earlier state. played:T# needs a human
    coding in codings[origin]; without it the membership is unknown.
    """
    codings = codings or {}
    resolved = {}

    def members_of(origin):
        kind, _, rest = origin.partition(":")
        if kind == "played":
            return codings.get(origin)
        if kind == "after":
            turn, view_id = rest.split(":")
            source = resolved[int(turn[1:])][view_id]
            return None if source is None else members_for_source(source)
        return _members(snapshots[labels[kind]], rest)

    for turn in scenario["turns"]:
        if turn["speaker"] != "user":
            continue
        views = {}
        for view_id, spec in turn["expect"]["state_after"].items():
            source = {field: spec[field] for field in FIELDS}
            membership = spec["membership"]
            if membership["rule"] == "ranked":
                source.update(categories=None, top_n=membership["top_n"], rank_by=membership["rank_by"])
            else:
                members = members_of(membership["from"])
                source = None if members is None else {**source, "categories": list(members), "top_n": None}
            views[view_id] = source
        resolved[turn["turn"]] = views
    return resolved


# Scoring ----------------------------------------------------------------------
def _fold(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9']+", text.replace("-", " ")))


def missing_critical_words(transcript, critical):
    folded = f" {_fold(transcript)} "
    return [word for word in critical if f" {_fold(word)} " not in folded]


def compare_view(expected, observed):
    if expected is None:
        return {"status": "unknown", "reason": "membership requires human coding"}
    if observed is None:
        return {"status": "mismatch", "fields": ["missing_view"]}
    source = observed["source"]
    wrong = [field for field in FIELDS if source.get(field) != expected[field]]
    if expected["categories"] is None:
        if source.get("categories") is not None:
            wrong.append("membership_rule")
        elif (source.get("top_n"), source.get("rank_by")) != (expected["top_n"], expected["rank_by"]):
            wrong.append("ranking")
    elif source.get("categories") is None or set(source["categories"]) != set(expected["categories"]):
        wrong.append("fixed_members")
    return {"status": "match" if not wrong else "mismatch", "fields": wrong}


def _windows(events, scenario, turn_windows):
    users = [t for t in scenario["turns"] if t["speaker"] == "user"]
    if turn_windows:
        starts = {window["turn"]: window["start_index"] for window in turn_windows}
        bounds = []
        for position, turn in enumerate(users):
            start = starts.get(turn["turn"])
            later = [starts[t["turn"]] for t in users[position + 1:] if t["turn"] in starts]
            bounds.append((turn, start, later[0] if later else None))
        return bounds, "driver_windows"
    # Fallback: map in order to accepted requests and ignored acknowledgements.
    marks = [e["index"] for e in events if e["name"] in ("request_accepted", "backchannel_ignored")]
    if len(marks) != len(users):
        return [(turn, None, None) for turn in users], "unmapped"
    return [(turn, marks[i], marks[i + 1] if i + 1 < len(marks) else None)
            for i, turn in enumerate(users)], "order_mapping"


def _state_before(events, snapshots, initial_revision, boundary):
    revision = initial_revision
    for event in events:
        if boundary is not None and event["index"] >= boundary:
            break
        if event["name"] == "node_created":
            revision = event["node"]["revision"]
    return snapshots.get(revision)


def score_scenario(scenario, events, snapshots, labels, members_for_source, *, turn_windows=None,
                   codings=None, initial_revision=None):
    """Per user turn: action, per-view state, untouched views, ASR, and one first cause.

    Spoken completion claims and whether a clarifying question was asked are left to a
    human coder; no assistant text is classified here.
    """
    expected = expected_turn_sources(scenario, labels, snapshots, members_for_source, codings)
    initial_revision = labels["current"] if initial_revision is None else initial_revision
    bounds, mapping = _windows(events, scenario, turn_windows)
    rows = []
    previous_revision = initial_revision
    users = [turn for turn, _, _ in bounds]
    # A turn superseded by a barge-in during its own tool run is intermediate: its
    # commit may legally land in the next window, so only the later turn is graded.
    intermediate = {users[i]["turn"] for i in range(len(users) - 1)
                    if users[i + 1]["timing"]["type"] == "during_tool"}
    for turn, start, end in bounds:
        row = {"turn": turn["turn"], "tags": turn["tags"], "expected_action": turn["expect"]["action"],
               "mapping": mapping, "claim": "pending_human_coding"}
        if turn["expect"]["action"] == "clarify":
            row["clarifying_question"] = "pending_human_coding"
        if start is None:
            row.update(first_cause="unknown", reason="turn could not be mapped to trace events")
            rows.append(row)
            continue
        window = [e for e in events if e["index"] >= start and (end is None or e["index"] < end)]
        accepted = [e for e in window if e["name"] == "request_accepted"]
        ignored = [e for e in window if e["name"] == "backchannel_ignored"]
        failures = [e for e in window if e["name"] == "tool_failed"]
        commits = [e for e in window if e["name"] == "tool_committed"]
        transcript = " ".join(e["text"] for e in accepted) or " ".join(
            e["event"].get("text", "") for e in ignored)
        state = _state_before(events, snapshots, initial_revision, end)
        observed = {view["id"]: view for view in state["views"]} if state else {}
        views = {view_id: compare_view(source, observed.get(view_id))
                 for view_id, source in expected[turn["turn"]].items()}
        missing = missing_critical_words(transcript, turn["critical_words"])
        acknowledgement = "BC" in turn["tags"]
        segmentation = []
        if acknowledgement and accepted:
            segmentation.append("acknowledgement_became_request")
        if not acknowledgement and ignored:
            segmentation.append("request_classified_as_acknowledgement")
        if len(accepted) > 1:
            segmentation.append(f"{len(accepted)}_requests_for_one_turn")
        if not acknowledgement and not accepted:
            segmentation.append("no_request_accepted")
        revision = state["revision"] if state else None
        action = "commit" if revision is not None and revision != previous_revision else "no_commit"
        action_ok = (action == "commit") == (turn["expect"]["action"] == "edit")
        statuses = {view["status"] for view in views.values()}
        unknown = "unknown" in statuses
        state_ok = False if "mismatch" in statuses else None if unknown else True
        if turn["turn"] in intermediate:
            row.update(transcript=transcript, missing_critical_words=missing, segmentation=segmentation,
                       intermediate=True, first_cause="asr" if missing else None,
                       note="superseded by a barge-in during its tool run; graded through the next turn")
            rows.append(row)
            continue
        if missing:
            cause = "asr"
        elif segmentation:
            cause = "segmentation_timing"
        elif failures and not (action_ok and state_ok):
            cause = "contract_execution"
        elif not action_ok or state_ok is False:
            cause = "decision"
        elif unknown:
            cause = "unknown"
        else:
            cause = None
        row.update(transcript=transcript, missing_critical_words=missing, segmentation=segmentation,
                   observed_action=action, action_correct=action_ok, views=views,
                   state_correct=state_ok,
                   tool_failures=[e.get("message") for e in failures], commits=len(commits),
                   revision_after=revision, first_cause=cause)
        rows.append(row)
        if revision is not None:
            previous_revision = revision
    known = [row for row in rows if row.get("first_cause") != "unknown"]
    return {"protocol": SCENARIO_PROTOCOL, "scenario_id": scenario["id"], "mapping": mapping,
            "turns": rows,
            "summary": {"user_turns": len(rows), "scored": len(known),
                        "correct": sum(row.get("first_cause") is None for row in known),
                        "by_cause": {cause: sum(row.get("first_cause") == cause for row in rows)
                                     for cause in ("asr", "segmentation_timing", "contract_execution",
                                                   "decision", "unknown")},
                        "terminal_state_correct": rows[-1].get("state_correct") if rows else None},
            "human_coding_pending": ["claim", "clarifying_question", "played_prefix_members"]}
