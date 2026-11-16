"""Actual session APIs, saved-set baseline and report boundaries; no external model."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    settings = {'api_key': '', 'text_model': 'local-test', 'realtime_model': 'local-test', 'voice': 'Maia',
                'text_url': 'http://127.0.0.1:9/unused', 'realtime_url': 'ws://127.0.0.1:9/unused',
                'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
                'trace_dir': tmp_path_factory.mktemp('business-workspace')}
    with TestClient(create_app(settings)) as client:
        yield client


def start(client, condition='direct'):
    return client.post('/api/session', json={'mode': 'text', 'condition': condition,
                       'task_id': 'biz_01_sp_priorities_mg'}).json()


@pytest.mark.parametrize('condition', ['direct', 'bound_revision'])
def test_named_set_baseline_reuses_history_without_changing_scope(client, condition):
    initial = start(client, condition)
    saved = client.post('/api/category-sets', json={'name': 'SP priorities', 'revision': 3, 'view_id': 'v1'}).json()
    assert saved['state'] == initial['state']
    assert saved['category_sets'][0]['evidence']['source']['region'] == 'SP'
    set_id = saved['category_sets'][0]['id']
    receipt = client.post(f'/api/category-sets/{set_id}/apply', json={'view_ids': ['v2', 'v3']}).json()
    assert receipt['committed']
    assert receipt['state']['views'][0] == initial['state']['views'][0]
    for old, new in zip(initial['state']['views'][1:], receipt['state']['views'][1:]):
        assert new['source'] == {**old['source'], 'categories': saved['category_sets'][0]['members'], 'top_n': None}
    report = client.post('/api/finish').json()['report']
    assert report['technical_completed'] and report['all_revision_commits_correct']
    assert report['interpretation_status'] == 'pending' and report['business_conclusion_correct'] is None
    assert not report['task_response_submitted']
    assert report['interaction']['category_sets']['application_count'] == 1
    assert report['interaction']['revision_cards']['generated_count'] == 0
    exported = client.get('/api/export').json()
    assert exported['category_sets'] == saved['category_sets']
    assert exported['interaction'] == report['interaction']
    context = json.loads(client.app.state.workspace.context())
    assert context['task']['business_goal'] == initial['tasks'][1]['business_goal']
    assert context['category_sets'] == saved['category_sets']
    assert not {'expected', 'resolution', 'evidence_phase', 'targets'} & context['task'].keys()


def test_recorded_response_is_not_a_graded_business_conclusion(client):
    start(client)
    answers = {'conclusion': 'I would investigate delivery.', 'rationale': 'Draft reasoning for human review.',
               'object_origin': 'SP priority chart, version 3.', 'calculation_scope': 'MG, delivered orders in 2017.'}
    response = client.post('/api/task-response', json=answers).json()['response']
    assert all(response[key] == value for key, value in answers.items())
    report = client.post('/api/finish').json()['report']
    assert report['task_response_submitted']
    assert report['technical_completed'] is False
    assert report['business_conclusion_correct'] is None and report['understanding_correct'] is None
    assert client.get('/api/export').json()['task_response'] == response
    fresh = start(client)
    assert fresh['task_response'] is None and fresh['category_sets'] == []


def test_selected_set_in_route_is_the_set_applied(client):
    initial = start(client)
    for name, revision in [('Historical priorities', 3), ('Current priorities', initial['state']['revision'])]:
        saved = client.post('/api/category-sets', json={
            'name': name, 'revision': revision, 'view_id': 'v1'}).json()['category_sets']
    historical, current = saved
    assert historical['members'] != current['members']
    receipt = client.post(f"/api/category-sets/{historical['id']}/apply", json={
        'view_ids': ['v2', 'v3'], 'set_id': current['id']}).json()
    assert receipt['committed']
    assert receipt['result']['category_set']['id'] == historical['id']
    assert receipt['state']['views'][0] == initial['state']['views'][0]
    for view in receipt['state']['views'][1:]:
        assert view['source']['categories'] == historical['members']


def test_manual_apply_and_actual_browser_telemetry_are_separate(client):
    start(client, 'bound_revision')
    proposal = client.post('/api/revisions/preview', json={'evidence': {'revision': 3, 'view_id': 'v1'},
        'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence', 'source_patch': {}}).json()['proposal']
    with client.websocket_connect('/ws') as socket:
        assert socket.receive_json()['type'] == 'bootstrap'
        for name, clock, extra in [
            ('revision_card_opened', 100, {}),
            ('revision_card_visible', 120, {'surface': 'detail', 'display_id': 'pageA-1', 'proposal_status': 'pending'}),
            ('revision_card_hidden', 1020, {'surface': 'detail', 'display_id': 'pageA-1'}),
            ('revision_confirmation_clicked', 1100, {}),
        ]:
            socket.send_json({'type': 'event', 'name': name, 'client_ms': clock,
                              'details': {'proposal_id': proposal['id'], **extra}})
        # Same WebSocket roundtrip establishes the telemetry has reached the server.
        socket.send_json({'type': 'stop_speaking'})
        assert socket.receive_json()['type'] == 'stop_audio'
        result = client.post(f"/api/revisions/{proposal['id']}/apply").json()
        assert result['committed']
        report = client.post('/api/finish').json()['report']
        observed = report['interaction']['revision_cards']
        assert observed['displayed_count'] == observed['detail_opened_count'] == observed['user_confirmed_count'] == 1
        assert observed['model_applied_count'] == 0
        assert observed['proposals'][0]['closed_visible_ms_by_surface']['detail'] == 900
        assert report['review_status'] == 'pending'
