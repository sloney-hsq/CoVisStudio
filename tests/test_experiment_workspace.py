"""Assigned-task lifecycle, actual commits, deadline and full-attempt exports."""
import csv
from io import StringIO
import json
from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    settings = {'api_key': '', 'text_model': 'local', 'realtime_model': 'local', 'voice': 'Maia',
                'text_url': 'http://127.0.0.1:9/unused', 'realtime_url': 'ws://127.0.0.1:9/unused',
                'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
                'trace_dir': tmp_path_factory.mktemp('experiment-api')}
    with TestClient(create_app(settings)) as client:
        yield client


def prepare(client, slot=1, trial_index=1, participant='local-check'):
    response = client.post('/api/experiment/start', json={'slot': slot, 'trial_index': trial_index,
        'participant_id': participant, 'evidence_kind': 'local_authored', 'condition': 'direct'})
    assert response.status_code == 200, response.text
    return response.json()


def save_response(client):
    return client.post('/api/task-response', json={
        'conclusion': 'Investigate the selected cohort, subject to service evidence.',
        'rationale': 'Authored interface check; business meaning remains pending.',
        'object_origin': 'The first complete historical comparison.',
        'calculation_scope': 'The current region, delivered orders, current dates.',
    }).json()


def test_public_plan_and_timing_gate_do_not_supply_private_answers(client):
    plan = client.get('/api/experiment/plan?slot=1').json()
    assert [trial['condition'] for trial in plan['trials']] == ['direct', 'direct', 'bound_revision', 'bound_revision']
    assert {trial['family_id'] for trial in plan['trials']} == {'01', '02', '03', '04'}
    assert all(not {'targets', 'evidence_phase', 'resolution', 'patch'} & trial['task'].keys() for trial in plan['trials'])
    assert client.get('/api/experiment/allocations?count=16').json()['balance']['exact_full_balance']
    assert not client.get('/api/experiment/allocations?count=30').json()['balance']['exact_full_balance']
    prepared = prepare(client)
    assert prepared['session']['condition'] == 'direct'  # supplied condition cannot change assignment
    assert prepared['session']['trial_status'] == 'ready'
    assert len(prepared['experiment_tasks']) == 8
    blocked = client.post('/api/tools', json={'name': 'edit_charts', 'arguments': {'view_ids': ['v1'], 'patch': {'source': {'metric': 'revenue'}}}})
    assert blocked.status_code == 409
    assert client.get('/api/bootstrap').json()['state'] == prepared['state']
    with client.websocket_connect('/ws') as socket:
        socket.receive_json()
        socket.send_json({'type': 'voice_start', 'mode': 'live_voice'})
        assert socket.receive_json()['type'] == 'error'
    context = json.loads(client.app.state.workspace.context())
    assert context['task']['id'] == 'exp_01_a'
    assert client.app.state.workspace.voice is None


@pytest.mark.parametrize('slot,condition', [(1, 'direct'), (5, 'bound_revision')])
def test_assigned_paths_share_numeric_score_and_complete_process_records(client, slot, condition):
    prepared = prepare(client, slot, participant=f'complete-{slot}')
    started = client.post('/api/experiment/begin').json()
    assert started['session']['trial_status'] == 'running' and started['session']['trial_started_at']
    if condition == 'direct':
        saved = client.post('/api/category-sets', json={'name': 'Earlier priorities', 'revision': 3, 'view_id': 'v1'}).json()['category_sets'][0]
        receipt = client.post(f"/api/category-sets/{saved['id']}/apply", json={'view_ids': ['v2', 'v3']}).json()
    else:
        client.post('/api/evidence', json={'revision': 3, 'view_id': 'v1'})
        proposal = client.post('/api/revisions/preview', json={'view_ids': ['v2', 'v3'],
            'source_patch': {}, 'member_action': 'use_evidence'}).json()['proposal']
        receipt = client.post(f"/api/revisions/{proposal['id']}/apply").json()
    assert receipt['committed'] and receipt['state']['views'][0] == prepared['state']['views'][0]
    save_response(client)
    finished = client.post('/api/finish', json={'reason': 'completed'}).json()
    report = finished['report']['trial_report']
    assert report['outcome']['technical_completed'] and report['outcome']['status'] == 'completed'
    assert report['outcome']['business_conclusion_correct'] is None
    assert report['process']['publication']['first_full_correct_revision'] == receipt['state']['revision']
    assert report['timing']['elapsed_seconds'] > 0 and report['timing']['first_full_correct_seconds'] >= 0
    assert report['process']['counts']['tool_started'] == 2
    assert report['process']['counts']['tool_committed'] == 1
    assert report['identity']['condition'] == condition
    assert finished['session']['trial_status'] == 'finished'
    assert client.post('/api/task-response', json={}).status_code == 409
    assert client.post('/api/finish').json()['report'] == finished['report']
    assert client.get('/api/bootstrap').json()['report'] == finished['report']
    events = client.get('/api/export').json()['events']
    assert sum(event['name'] == 'trial_started' for event in events) == 1
    assert sum(event['name'] == 'trial_finished' for event in events) == 1


def test_failed_repeat_unstarted_exit_and_missing_tasks_remain_in_report(client):
    prepare(client, 1, participant='complete-1')
    finished = client.post('/api/finish', json={'reason': 'abandoned'}).json()['report']['trial_report']
    assert finished['outcome']['terminal_reason'] == 'abandoned'
    assert finished['timing']['elapsed_seconds'] is None
    report = client.get('/api/experiment/report').json()
    repeats = [row for row in report['attempt_rows'] if row['participant_id'] == 'complete-1' and row['trial_id'] == 's001-t1']
    assert len(repeats) == 2
    assert next(row for row in repeats if row['selected_latest'])['terminal_reason'] == 'abandoned'
    assert sum(row['technical_completed'] for row in repeats) == 1  # earlier success retained, not selected as best
    assert len([trial for trial in report['missing_trials'] if trial['participant_id'] == 'complete-1']) == 3
    csv_rows = list(csv.DictReader(StringIO(client.get('/api/experiment/export?format=csv').text)))
    assert len(csv_rows) == report['attempt_count']
    assert client.get('/api/experiment/export').json()['attempt_count'] == report['attempt_count']


def test_server_deadline_ends_work_and_closes_the_assigned_attempt(client):
    prepare(client, 9, participant='deadline-local')
    # Exercise the actual server timer quickly; formal assignments always specify 480 seconds.
    client.app.state.workspace.session['assignment']['time_limit_seconds'] = 0.02
    client.post('/api/experiment/begin')
    time.sleep(0.15)
    result = client.get('/api/bootstrap').json()
    assert result['session']['trial_status'] == 'finished'
    trial = result['report']['trial_report']
    assert trial['outcome']['terminal_reason'] == 'timeout'
    # Windows GetTickCount64/asyncio timers can wake one monotonic tick early.
    # The report must preserve that measured interval, not fabricate the requested duration.
    events = client.app.state.workspace.trace.events
    started = next(event for event in events if event['name'] == 'trial_started')
    finished = next(event for event in events if event['name'] == 'trial_finished')
    elapsed = round((finished['server_ms'] - started['server_ms']) / 1000, 3)
    tolerance = time.get_clock_info('monotonic').resolution + 0.0005
    assert trial['timing']['elapsed_seconds'] == elapsed
    assert elapsed >= 0.02 - tolerance
    assert trial['timing']['time_censored']
    assert client.app.state.workspace.voice is None


def test_switching_tasks_retains_the_unfinished_attempt(client):
    old = prepare(client, 13, participant='switch-local')
    client.post('/api/experiment/begin')
    prepare(client, 13, 2, participant='switch-local')
    report = client.get('/api/experiment/report').json()
    previous = next(attempt for attempt in report['all_attempts'] if attempt['identity']['session_id'] == old['session']['id'])
    assert previous['outcome']['terminal_reason'] == 'abandoned'
    assert previous['timing']['elapsed_seconds'] is not None
    assert sum(attempt['identity']['participant_id'] == 'switch-local' for attempt in report['all_attempts']) == 2
