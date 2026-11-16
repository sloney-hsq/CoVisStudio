"""Real local HTTP lifecycle and SQL; no provider connection or human claims."""
from pathlib import Path
from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.intent_scoring import coding_template


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    settings = {'api_key': '', 'text_model': 'local', 'realtime_model': 'local', 'voice': 'Maia',
                'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
                'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
                'trace_dir': tmp_path_factory.mktemp('formal-api')}
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def prepare(client):
    result = client.post('/api/experiment/start', json={'protocol': 'formal', 'slot': 1, 'trial_index': 1,
                         'participant_id': 'authored-integration', 'evidence_kind': 'local_authored'})
    assert result.status_code == 200, result.text
    client.post('/api/experiment/begin')
    return result.json()


def test_formal_plan_live_lock_and_unknown_are_not_authored_answers(client):
    plan = client.get('/api/experiment/plan?protocol=formal&slot=1').json()
    assert len(plan['trials']) == 4
    assert all(item['task_id'].startswith('study_') for item in plan['trials'])
    assert 'expected_sources' not in json.dumps(plan)
    prepared = prepare(client)
    assert prepared['session']['mode'] == 'live_voice'
    with client.websocket_connect('/ws') as socket:
        socket.receive_json()
        socket.send_json({'type': 'text', 'text': 'Try a bypass'})
        assert 'one live voice window' in socket.receive_json()['message']
        socket.send_json({'type': 'voice_start', 'mode': 'push_to_talk'})
        assert 'one Realtime voice window' in socket.receive_json()['message']
        socket.send_json({'type': 'event', 'name': 'mode_selected', 'client_ms': 2,
                         'details': {'mode': 'text'}})
    assert client.get('/api/bootstrap').json()['session']['mode'] == 'live_voice'
    finished = client.post('/api/finish').json()
    assert finished['report']['intent_correct'] is None
    assert finished['report']['trial_report']['protocol'] == 'covis-formal-study-0.1'
    assert finished['report']['understanding_correct'] is None
    summary = client.get('/api/experiment/report?protocol=formal').json()
    assert summary['registered_participant_count'] == 0
    assert summary['non_primary_records']  # authored local check is not a participant


def test_independent_intent_handoff_from_http_to_locked_sql_and_archive(client):
    prepared = prepare(client)
    session_id = prepared['session']['id']
    # Explicit user source selection precedes the focus revision; the packet keeps it.
    evidence = client.post('/api/evidence', json={'revision': 3, 'view_id': 'v1'}).json()['evidence']
    proposal = client.post('/api/revisions/preview', json={'view_ids': ['v2', 'v3'],
               'source_patch': {}, 'member_action': 'use_evidence',
               'label': 'Use the selected historical group in both service charts. Keep the current region and dates.'}).json()['proposal']
    assert client.post(f"/api/revisions/{proposal['id']}/apply").status_code == 200
    response = {key: 'Synthetic API acceptance answer; not participant evidence.' for key in
                ('conclusion', 'rationale', 'object_origin', 'calculation_scope', 'target_views', 'kept_released')}
    assert client.post('/api/task-response', json=response).status_code == 200
    client.post('/api/finish')
    original = client.get('/api/export').json()
    events = original['events']
    onset = next(e['index'] for e in events if e['name'] == 'request_accepted')
    end = next(e['index'] for e in events if e['name'] == 'trial_finished')
    prefix = f'/api/experiment/attempts/{session_id}/intent-episodes'
    prepared_packet = client.post(prefix, json={'onset_index': onset, 'utterance_end_index': onset, 'end_event_index': end})
    assert prepared_packet.status_code == 200, prepared_packet.text
    episode_url = prefix + '/' + prepared_packet.json()['packet_id']
    packet = client.get(episode_url).json()
    assert 'final' not in packet and 'expected_sources' not in json.dumps(packet)
    assert client.post(episode_url + '/score').status_code == 409
    coder = coding_template(packet)
    coder['intent']['source_requirement'] = {'mode': 'none', 'candidate_id': None, 'reason': 'Authored fixture requests scope changes without a new historical source.'}
    coder.update(status='completed', reviewer_id='local-fixture-a')
    coder['intent'].update(status='resolved', target_view_ids=['v2', 'v3'], source_patch={},
        members={'mode': 'fixed', 'values': evidence['members'], 'origin': {'revision': 3, 'view_id': 'v1'}},
        retained_fields=['region', 'start', 'end', 'metric'], released_fields=['top_n'],
        reason='Authored integration coding; no human review performed.', evidence_indices=[onset])
    body = {'coder_a': coder, 'coder_b': {**deepcopy(coder), 'reviewer_id': 'local-fixture-b'},
            'adjudication': {'reviewer_id': 'local-fixture', 'reason': 'Authored test.', 'intent': coder['intent']}}
    assert client.post(episode_url + '/lock', json=body).status_code == 200
    assert client.post(episode_url + '/primary', json={'reviewer_id': 'local-fixture', 'reason': 'Only task revision in this authored check.'}).status_code == 200
    result = client.post(episode_url + '/score')
    assert result.status_code == 200, result.text
    assert result.json()['final_correct'] is True
    assert result.json()['human_listening'] == 'pending'
    archived = client.get(f'/api/experiment/attempts/{session_id}').json()
    assert archived['intent_episodes'][0]['final_correct'] is True
    assert archived['intent_episodes'][0]['understanding']['object_origin'] is None
    assert client.get('/api/export').json() == original  # sidecars never rewrite the original
    assert 'local-fixture-a' not in client.app.state.workspace.context()


def test_terminal_routes_roundtrip(client):
    prepared = prepare(client)
    session_id = prepared['session']['id']
    response = {key: 'Synthetic terminal route fixture; not participant evidence.' for key in
                ('conclusion', 'rationale', 'object_origin', 'calculation_scope', 'target_views', 'kept_released')}
    assert client.post('/api/task-response', json=response).status_code == 200
    client.post('/api/finish')
    prefix = f'/api/experiment/attempts/{session_id}'
    created = client.post(prefix + '/intent-episodes/terminal', json={})
    assert created.status_code == 200, created.text
    assert created.json()['packet_id'] == 'terminal'
    assert client.post(prefix + '/intent-episodes/terminal', json={}).status_code == 400
    packet = client.get(prefix + '/intent-episodes/terminal').json()
    assert packet['kind'] == 'terminal'
    onset = packet['boundary']['onset']['index']
    coder = coding_template(packet)
    assert coder['kind'] == 'terminal'
    coder.update(status='completed', reviewer_id='terminal-fixture-a')
    coder['intent'].update(status='resolved', disposition='retain_all', target_view_ids=[],
                           reason='Authored terminal fixture; no human review.',
                           evidence_indices=[onset])
    body = {'coder_a': coder, 'coder_b': {**deepcopy(coder), 'reviewer_id': 'terminal-fixture-b'},
            'adjudication': {'reviewer_id': 'terminal-fixture', 'reason': 'Authored test.',
                             'intent': coder['intent']}}
    locked = client.post(prefix + '/intent-episodes/terminal/lock', json=body)
    assert locked.status_code == 200, locked.text
    scored = client.post(prefix + '/intent-episodes/terminal/score')
    assert scored.status_code == 200, scored.text
    assert scored.json()['final_correct'] is True
    attempt = client.get(prefix).json()
    assert attempt['terminal_intent']['scored'] is True
    assert attempt['terminal_intent']['final_correct'] is True
    key = client.get(prefix + '/interpretation-key').json()
    assert key['key_hash'] and key['key']['target_views'] == []
    review = {'reviewer_id': 'understanding-a', 'key_hash': key['key_hash'],
              'key_fields': ['target_views'], 'response_span': [0, 1]}
    understanding = client.post(prefix + '/understanding-lock', json={
        'review_a': review, 'review_b': {**review, 'reviewer_id': 'understanding-b'},
        'adjudication': {'reviewer_id': 'understanding-c', 'reason': 'Authored test.',
                         'labels': {'target_views': True}}})
    assert understanding.status_code == 200, understanding.text
    assert understanding.json()['labels']['target_views'] is True


def test_registration_retains_four_missing_assigned_rows(client):
    # This pseudonymous fixture is only in pytest's temporary directory.
    response = client.post('/api/experiment/register', json={'participant_id': 'fixture-roster-only', 'participant_slot': 2})
    assert response.status_code == 200
    report = client.get('/api/experiment/report?protocol=formal').json()
    assert len(report['assigned_rows']) == 4 and len(report['missing_trials']) == 4
    assert all(row['revision_correct'] is None for row in report['assigned_rows'])
    assert all(row['unknown'] == 2 for row in report['primary']['conditions'])
    exported = client.get('/api/experiment/export?protocol=formal&format=csv').text
    assert len(exported.splitlines()) == 5
