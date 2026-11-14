"""Archived review reads the selected attempt and never alters trial evidence."""
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import wave

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    directory = tmp_path_factory.mktemp('review-api')
    settings = {'api_key': '', 'text_model': 'local', 'realtime_model': 'local', 'voice': 'Maia',
                'text_url': 'http://127.0.0.1:9/unused', 'realtime_url': 'ws://127.0.0.1:9/unused',
                'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'trace_dir': directory}
    with TestClient(create_app(settings)) as client:
        yield client


def prepare(client, index=1):
    return client.post('/api/experiment/start', json={'slot': 1, 'trial_index': index,
        'participant_id': 'review-local', 'evidence_kind': 'local_authored'}).json()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_archived_review_media_and_drafts_preserve_original_evidence(client):
    prepared = prepare(client)
    client.post('/api/experiment/begin')
    saved = client.post('/api/category-sets', json={'name': 'Original cohort', 'revision': 3, 'view_id': 'v1'}).json()['category_sets'][0]
    assert client.post(f"/api/category-sets/{saved['id']}/apply", json={'view_ids': ['v2', 'v3']}).status_code == 200
    client.post('/api/finish', json={'reason': 'completed'})
    directory = client.app.state.workspace.trace.directory
    # Local test recording belongs to this attempt, never the later active session.
    with wave.open(str(directory / 'input-review-fixture.wav'), 'wb') as audio:
        audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        audio.writeframes(bytes(3200))
    (directory / 'image-review-fixture.jpg').write_bytes(b'local-test-image')
    original = {name: digest(directory / name) for name in ('session.json', 'events.jsonl')}
    prepare(client, 2)
    active_id = client.get('/api/bootstrap').json()['session']['id']
    identity = prepared['session']['id']
    url = f'/api/experiment/attempts/{identity}'
    packet = client.get(url).json()
    assert packet['session']['id'] == identity != active_id
    assert packet['task']['id'] == 'exp_01_a'
    assert packet['review_status'] == 'pending' and packet['review_drafts'] == []
    assert packet['trial_report']['outcome']['business_conclusion_correct'] is None
    assert packet['node_states']
    audio = next(item for item in packet['media'] if item['kind'] == 'audio')
    assert client.get(audio['url']).content == (directory / audio['name']).read_bytes()
    image = next(item for item in packet['media'] if item['kind'] == 'image')
    assert client.get(image['url']).content == b'local-test-image'
    events = packet['events']
    start = next(e['index'] for e in events if e['name'] == 'trial_started')
    end = next(e['index'] for e in events if e['name'] == 'trial_finished')
    body = {'reviewer_id': 'local-verifier', 'notes': 'Authored test of draft storage, not human judgement.',
            'interpretation': 'pending', 'spoken_consistency': 'not_available',
            'segments': [{'start_event_index': start, 'end_event_index': end,
                          'kind': 'unclear', 'reason': 'No participant performed this local test.'}]}
    saved = client.post(url + '/review-drafts', json=body)
    assert saved.status_code == 200, saved.text
    assert len(saved.json()['review_drafts']) == 1 and saved.json()['review_status'] == 'pending'
    assert {name: digest(directory / name) for name in original} == original
    assert client.get('/api/bootstrap').json()['session']['id'] == active_id
    aggregate = client.get('/api/experiment/report').json()
    row = next(row for row in aggregate['attempt_rows'] if row['session_id'] == identity)
    assert row['review_draft_count'] == 1 and row['human_review'] == 'pending'
    assert row['repair_turns'] is None and row['repair_seconds'] is None
    assert len(aggregate['review_drafts']) == 1
    csv_rows = list(csv.DictReader(StringIO(client.get('/api/experiment/export?format=csv').text)))
    assert next(row for row in csv_rows if row['session_id'] == identity)['review_draft_count'] == '1'
    assert json.loads((directory / 'session.json').read_text())['task']['id'] == 'exp_01_a'


def test_review_window_and_phase_are_not_fabricated(client):
    current = client.get('/api/bootstrap').json()
    identity = current['session']['id']
    body = {'reviewer_id': 'local-verifier', 'notes': 'Pending', 'interpretation': 'pending',
            'spoken_consistency': 'pending', 'segments': []}
    assert client.post(f'/api/experiment/attempts/{identity}/review-drafts', json=body).status_code == 409
    client.post('/api/finish', json={'reason': 'abandoned'})
    packet = client.get(f'/api/experiment/attempts/{identity}').json()
    # There is no timed work in an unstarted abandoned attempt.
    body['segments'] = [{'start_event_index': 0, 'end_event_index': 1, 'kind': 'repair', 'reason': 'Invalid setup interval'}]
    response = client.post(f'/api/experiment/attempts/{identity}/review-drafts', json=body)
    assert response.status_code == 400
    assert client.get(f'/api/experiment/attempts/{identity}').json()['review_drafts'] == []
    assert packet['trial_report']['human_review']['repair_turns'] is None
