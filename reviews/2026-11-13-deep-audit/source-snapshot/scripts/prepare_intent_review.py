"""Build a blinded, pending intent-coding packet from one archived session."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def stamp(event):
    return {k: event[k] for k in ("event_id", "index", "name", "at", "server_ms", "client_ms", "client_clock_id", "request_id", "item_id", "aligned_server_ms", "calibration_id", "uncertainty_ms") if k in event}


def prepare_packet(session_dir, onset_index, utterance_end_index, evidence_kind="unspecified"):
    session_dir = Path(session_dir)
    event_file = session_dir / "events.jsonl"
    events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_index = {e["index"]: e for e in events}
    onset, end = by_index[onset_index], by_index[utterance_end_index]
    if onset_index > utterance_end_index:
        raise ValueError("Utterance end must follow onset.")
    if onset["name"] not in ("speech_start", "user_input", "request_accepted"):
        raise ValueError("Choose an actual speech onset or explicit text request event.")
    packet_id = hashlib.sha256((event_file.read_bytes() + f"{onset_index}:{utterance_end_index}".encode())).hexdigest()[:20]
    packet = {"schema": "covis-intent-review-1", "packet_id": packet_id,
        "evidence_kind": evidence_kind, "human_review_status": "pending",
        "boundary": {"onset": stamp(onset), "utterance_arrival_end": stamp(end),
                     "rule": "Context strictly before onset; user words through explicit arrival end. Raw clocks retained."},
        "participant_input": [], "prior_context": [], "public_states": [],
        "onset_selection": {k: onset[k] for k in ("reference", "evidence") if k in onset},
        "limitations": ["Provider transcription is not human-verified speech.",
          "Generated assistant words do not establish playback or comprehension.",
          "Visible/rendered telemetry does not prove reading; no semantic audio alignment is inferred.",
          "Condition labels are withheld, but wording or visible content may reveal the interface."],
        "coding": {"reviewer": None, "status": "pending", "member_origin": None, "members": None,
            "targets": None, "change": None, "keep": None, "release": None,
            "unknown": None, "reason": None, "evidence_ids": [], "timestamps": [],
            "speech_verification": "pending"}}
    pre_names = {"user_transcript", "assistant_done", "assistant_delta", "selection", "evidence_selected",
        "speech_reference", "chart_rendered", "chart_visible", "chart_hidden", "playback_start",
        "playback_progress", "playback_stopped", "playback_end"}
    allowed = {"text", "reference", "evidence", "details", "event", "response_id", "epoch", "revision",
        "view_id", "view_ids", "entities", "played_samples", "received_samples", "sample_rate"}
    for e in events:
        i = e["index"]
        if i < onset_index and e["name"] in pre_names:
            entry = {**stamp(e), **{k: e[k] for k in allowed if k in e}}
            if e["name"] in ("assistant_done", "assistant_delta"):
                entry["delivery_interpretation"] = "Generated text only; heard words unknown. Consult separate playback samples."
            packet["prior_context"].append(entry)
        if onset_index <= i <= utterance_end_index:
            nested = e.get("event", {})
            if e["name"] == "provider_event":
                nested = nested.get("event", nested)
            raw_type = nested.get("type", "")
            if e["name"] in ("user_transcript", "request_accepted", "user_input") or (
                e["name"] == "provider_event" and raw_type == "conversation.item.input_audio_transcription.completed"):
                text = e.get("text", nested.get("text", nested.get("transcript")))
                packet["participant_input"].append({**stamp(e), "text": text,
                    "raw_provider_fragment": e["name"] == "provider_event",
                    "item_id": e.get("item_id", nested.get("item_id")),
                    **{k: e[k] for k in ("reference", "evidence") if k in e}})
    # Public snapshots are included only when a pre-onset render explicitly cites them.
    revisions = sorted({e.get("revision", e.get("details", {}).get("revision"))
        for e in packet["prior_context"] if e["name"] == "chart_rendered"} - {None})
    evidence_views = {}
    for e in packet["prior_context"] + packet["participant_input"]:
        ev = e.get("evidence") or {}
        if ev.get("revision") is not None and ev.get("view_id"):
            evidence_views.setdefault(ev["revision"], set()).add(ev["view_id"])
    revisions = sorted(set(revisions) | set(evidence_views))
    fingerprints = {"events.jsonl": hashlib.sha256(event_file.read_bytes()).hexdigest()}
    for revision in revisions:
        path = session_dir / f"state-r{revision}.json"
        if path.exists():
            state = read_json(path)
            permitted = evidence_views.get(revision, set()) | {e.get("view_id", e.get("details", {}).get("view_id")) for e in packet["prior_context"] if e["name"] == "chart_rendered" and e.get("revision", e.get("details", {}).get("revision")) == revision}
            packet["public_states"].append({"revision": state["revision"], "title": state.get("title"),
                "views": [{k: v[k] for k in ("id", "number", "title", "chart_type", "source", "data", "style") if k in v} for v in state["views"] if v["id"] in permitted]})
            fingerprints[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    packet["raw_fragment_review"] = "Compare raw provider fragments with accepted text; dropped prefixes remain evidence, never concatenate automatically."
    # Keep archive identity and outcomes out of the reviewer handout.
    unblinding = {"schema": "covis-intent-unblinding-1", "packet_id": packet_id,
        "session_dir": str(session_dir.resolve()), "input_fingerprints": fingerprints,
        "created_at": datetime.now(timezone.utc).isoformat(), "unlock_rule": "Only after independent intent coding is locked.",
        "outcome_event_ids": [e.get("event_id", e["index"]) for e in events
            if e["index"] >= onset_index and e["name"] in ("revision_proposed", "tool_started", "tool_committed", "tool_failed", "assistant_done", "request_outcome")],
        "outcome_source": "Original archive; no outcome, expected source or score copied into intent handout."}
    return packet, unblinding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", required=True, type=Path)
    parser.add_argument("--onset-index", required=True, type=int)
    parser.add_argument("--utterance-end-index", required=True, type=int)
    parser.add_argument("--evidence-kind", choices=("authored_diagnostic", "participant", "unspecified"), default="unspecified")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    packet, secret = prepare_packet(args.session_dir, args.onset_index, args.utterance_end_index, args.evidence_kind)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in (("intent-packet.json", packet), ("unblinding-private.json", secret)):
        with (args.output_dir / name).open("x", encoding="utf-8") as stream:
            json.dump(content, stream, ensure_ascii=False, indent=2)
    print(args.output_dir / "intent-packet.json")


if __name__ == "__main__":
    main()
