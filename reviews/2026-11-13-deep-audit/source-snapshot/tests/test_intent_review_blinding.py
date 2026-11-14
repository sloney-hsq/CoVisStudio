import json
from scripts.prepare_intent_review import prepare_packet


def test_blinded_boundary_keeps_words_not_answers(tmp_path):
    def event(i, name, **kw):
        return {"index": i, "event_id": f"s:{i}", "name": name, "server_ms": i * 10, **kw}
    events = [event(0, "chart_rendered", details={"revision": 1, "view_id": "v1"}),
        event(1, "assistant_done", event={"text": "Previous legitimate discussion"}),
        event(2, "playback_progress", details={"received_samples": 500, "played_samples": 100}),
        event(3, "speech_start", reference={"revision": 1, "view_ids": ["v1"]}),
        event(4, "provider_event", event={"type": "provider_event", "event": {"type": "conversation.item.input_audio_transcription.completed", "transcript": "Dropped original prefix", "item_id": "old"}}),
        event(5, "request_accepted", text="Keep region"),
        event(6, "assistant_done", event={"text": "SECRET POST ANSWER"}),
        event(7, "revision_proposed", proposal={"members": ["SECRET PROPOSAL"]}),
        event(8, "user_transcript", event={"text": "Actual final user fragment"})]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf8")
    (tmp_path / "state-r1.json").write_text(json.dumps({"revision": 1, "views": [{"id": "v1", "source": {"region": "MG"}}, {"id": "v2", "source": {"region": "UNSEEN"}}], "expected_sources": "SECRET EXPECTED"}), encoding="utf8")
    (tmp_path / "state-r2.json").write_text('{"final":"SECRET FINAL"}', encoding="utf8")
    packet, secret = prepare_packet(tmp_path, 3, 8, "authored_diagnostic")
    text = json.dumps(packet)
    assert "SECRET" not in text and "UNSEEN" not in text
    assert "Previous legitimate discussion" in text and "Dropped original prefix" in text
    assert "Actual final user fragment" in text
    assert packet["coding"]["members"] is None and packet["coding"]["status"] == "pending"
    assert packet["participant_input"][0]["raw_provider_fragment"]
    assert packet["prior_context"][1]["delivery_interpretation"].startswith("Generated text only")
    assert packet["prior_context"][2]["details"]["played_samples"] == 100
    assert "s:6" in secret["outcome_event_ids"] and "session_dir" not in packet
