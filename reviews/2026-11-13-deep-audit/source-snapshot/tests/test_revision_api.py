"""Historical evidence, current-state edits and local protocol boundaries."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import Workspace, create_app


def settings(path):
    return {'api_key': '', 'text_model': 'local-only', 'realtime_model': 'local-only',
            'text_url': 'http://127.0.0.1:9/not-used', 'realtime_url': 'ws://127.0.0.1:9/not-used',
            'voice': 'Maia', 'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'trace_dir': path}


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    with TestClient(create_app(settings(tmp_path_factory.mktemp('revision-api')))) as client:
        yield client


def setup(client, condition='bound_revision'):
    start = client.post('/api/session', json={'mode': 'live_voice', 'task_id': 'starter', 'condition': condition}).json()
    old = start['state']
    current = client.post('/api/tools', json={'name': 'edit_charts', 'arguments': {
        'view_ids': [v['id'] for v in old['views']],
        'patch': {'source': {'region': 'MG', 'categories': None, 'top_n': 3, 'rank_by': 'orders'}}}}).json()['state']
    assert {r['label'] for r in old['views'][0]['data']['rows']} != {r['label'] for r in current['views'][0]['data']['rows']}
    return old, current


def preview(client, **extra):
    response = client.post('/api/revisions/preview', json={
        'view_ids': ['v1', 'v2', 'v3'], 'source_patch': {}, 'member_action': 'use_evidence', **extra})
    assert response.status_code == 200, response.text
    return response.json()['proposal']


def test_history_selection_and_preview_do_not_restore_or_commit(client):
    old, current = setup(client)
    members = old['views'][0]['source']['categories']
    response = client.post('/api/evidence', json={'revision': old['revision'], 'view_id': 'v1'})
    assert response.status_code == 200
    assert response.json()['state'] == current
    assert response.json()['evidence']['members'] == members
    proposal = preview(client)
    assert client.get('/api/bootstrap').json()['state'] == current
    assert proposal['card']['evidence']['source']['region'] == 'SP'
    assert all(change['after_source']['region'] == 'MG' for change in proposal['card']['changes'])
    assert all(change['after_source']['categories'] == members for change in proposal['card']['changes'])
    receipt = client.post(f"/api/revisions/{proposal['id']}/apply").json()
    assert receipt['proposal']['status'] == 'committed'
    for before, after in zip(current['views'], receipt['state']['views']):
        assert after['source']['region'] == 'MG'
        assert after['source']['categories'] == members
        assert after['source']['metric'] == before['source']['metric']
        assert after['source']['start'] == before['source']['start']
    assert client.app.state.workspace.voice is None
    exported = client.get('/api/export').json()
    assert exported['session']['condition'] == 'bound_revision'
    assert any(event['name'] == 'revision_applied' for event in exported['events'])
    assert any(event['name'] == 'request_accepted' for event in exported['events'])


@pytest.mark.parametrize('condition', ['direct', 'unbound_preview'])
def test_direct_shares_binding_and_unbound_preview_leaves_supplied_patch(client, condition):
    old, current = setup(client, condition)
    client.post('/api/evidence', json={'revision': old['revision'], 'view_id': 'v1'})
    proposal = preview(client)
    assert proposal['card']['binding_applied'] is (condition == 'direct')
    expected = old['views'][0]['source']['categories'] if condition == 'direct' else [r['label'] for r in current['views'][0]['data']['rows']]
    assert proposal['card']['changes'][0]['after_members'] == expected
    assert proposal['card']['evidence']['members'] == old['views'][0]['source']['categories']
    assert client.get('/api/bootstrap').json()['state'] == current


def test_only_selected_current_view_changes_and_undo_keeps_history(client):
    old, current = setup(client)
    client.post('/api/evidence', json={'revision': old['revision'], 'view_id': 'v1'})
    proposal = preview(client, view_ids=['v2'], source_patch={'metric': 'revenue'})
    result = client.post(f"/api/revisions/{proposal['id']}/apply").json()
    assert result['state']['views'][0] == current['views'][0]
    assert result['state']['views'][2] == current['views'][2]
    assert result['state']['views'][1]['source']['metric'] == 'revenue'
    assert result['state']['views'][1]['source']['region'] == 'MG'
    undone = client.post('/api/undo').json()['state']
    assert undone['views'] == current['views']
    assert undone['revision'] > result['state']['revision']


def test_new_edit_supersedes_old_preview_without_undoing_the_edit(client):
    old, _ = setup(client)
    client.post('/api/evidence', json={'revision': old['revision'], 'view_id': 'v1'})
    proposal = preview(client)
    latest = client.post('/api/tools', json={'name': 'edit_charts', 'arguments': {
        'view_ids': ['v3'], 'patch': {'style': {'color': '#cc6633'}}}}).json()['state']
    assert client.post(f"/api/revisions/{proposal['id']}/apply").status_code == 409
    assert client.get('/api/bootstrap').json()['state'] == latest
    assert client.get('/api/bootstrap').json()['proposal']['status'] == 'superseded'


def test_same_raw_historical_context_for_all_conditions_and_no_private_answer(client):
    for condition in ['direct', 'bound_revision', 'unbound_preview']:
        old, current = setup(client, condition)
        client.post('/api/evidence', json={'revision': old['revision'], 'view_id': 'v1'})
        workspace = client.app.state.workspace
        workspace.bound_evidence = deepcopy(workspace.evidence)
        context = json.loads(workspace.context())
        assert context['history_index'][old['revision']]['views'][0]['source']['region'] == 'SP'
        assert context['current_dashboard'] == current
        assert context['evidence']['members'] == old['views'][0]['source']['categories']
        assert not {'expected', 'oracle', 'answer', 'resolution'} & context.keys()


def test_model_cannot_apply_unresolved_proposal_and_speech_replaces_it(tmp_path):
    async def run():
        ws = Workspace(settings(tmp_path))
        ws.reset('live_voice', 'starter', '')
        before = ws.store.snapshot()
        result = await ws.execute('preview_revision', {'view_ids': ['v1'], 'source_patch': {'region': 'MG'},
                                 'member_action': 'keep_current', 'needs_confirmation': True,
                                 'question': 'Apply this change only to chart one?'})
        proposal_id = result['proposal']['id']
        denied = await ws.execute('apply_revision', {'proposal_id': proposal_id})
        assert denied['status'] == 'awaiting_confirmation'
        assert ws.store.snapshot() == before
        await ws.provider_event({'type': 'speech_start', 'item_id': 'new-intent'})
        stale = await ws.execute('apply_revision', {'proposal_id': proposal_id})
        assert stale['status'] == 'failed'
        assert ws.store.snapshot() == before
        ws.data.close()
    asyncio.run(run())

