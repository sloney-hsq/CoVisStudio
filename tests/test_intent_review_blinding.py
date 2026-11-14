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


def test_preceding_text_and_saved_subset_are_available_but_focus_outcome_is_not(tmp_path):
    events = [
        {'index': 0, 'name': 'request_accepted', 'text': 'Save only alpha and gamma.'},
        {'index': 1, 'name': 'category_set_saved', 'category_set': {'id': 'set1', 'members': ['alpha', 'gamma']}},
        {'index': 2, 'name': 'request_accepted', 'text': 'Use my saved group in the service charts.'},
        {'index': 3, 'name': 'tool_committed', 'result': {'secret': 'OUTCOME'}}]
    (tmp_path / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events), encoding='utf8')
    packet, _ = prepare_packet(tmp_path, 2, 2)
    assert packet['prior_context'][0]['text'] == events[0]['text']
    assert packet['prior_context'][1]['category_set']['members'] == ['alpha', 'gamma']
    assert 'OUTCOME' not in json.dumps(packet)


def test_public_task_and_direct_edit_are_inputs_not_inferred_outcomes(tmp_path):
    event = {'index': 0, 'name': 'manual_edit_requested', 'text': 'Direct chart edit',
             'tool': 'edit_charts', 'arguments': {'view_ids': ['v2'], 'patch': {'source': {'region': 'RJ'}}}}
    (tmp_path / 'events.jsonl').write_text(json.dumps(event), encoding='utf8')
    (tmp_path / 'session.json').write_text(json.dumps({'task': {'title': 'Service investigation',
        'goal': 'Choose categories to examine.', 'expected_sources': 'SECRET', 'condition': 'SECRET'}}), encoding='utf8')
    packet, _ = prepare_packet(tmp_path, 0, 0)
    assert packet['public_task']['goal'] == 'Choose categories to examine.'
    assert packet['participant_input'][0]['arguments'] == event['arguments']
    assert 'SECRET' not in json.dumps(packet)
