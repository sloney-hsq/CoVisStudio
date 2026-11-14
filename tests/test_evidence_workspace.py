"""Application evidence decisions using real Olist and local synthetic clocks only."""
import asyncio
import base64
import json

import pytest

from backend.app import Workspace
from test_revision_api import settings


@pytest.fixture
def workspace(tmp_path):
    ws = Workspace(settings(tmp_path))
    ws.reset('live_voice', 'starter', '')
    yield ws
    ws.data.close()


def test_committed_states_and_saved_sets_enter_immutable_evidence(workspace):
    async def run():
        ws = workspace
        state = ws.store.snapshot()
        saved = await ws.execute('save_category_set', {'name': 'Original cohort', 'revision': state['revision'], 'view_id': 'v1'}, actor='user')
        package = ws.freeze_evidence()
        states = [i for i in package['items'] if i['kind'] == 'chart_state']
        sets = [i for i in package['items'] if i['kind'] == 'category_set']
        assert states[-1]['content'] == state
        assert sets[0]['content'] == saved['result']['category_set']
        state['views'][0]['source']['region'] = 'CHANGED'
        assert states[-1]['content']['views'][0]['source']['region'] == 'SP'
    asyncio.run(run())


def test_image_requires_both_capture_and_arrival_before_cutoff(workspace, monkeypatch):
    async def run():
        ws = workspace
        clock = [100]
        monkeypatch.setattr(ws.trace, 'now_ms', lambda: clock[0])
        # Explicit synthetic browser calibration: local protocol fixture, not measured browser timing.
        ws.trace.calibrations['fixture-browser'] = {'offset_ms': 10, 'uncertainty_ms': 2, 'calibration_id': 'synthetic-fixture'}
        image = base64.b64encode(b'local fixture JPEG bytes').decode()
        await ws.set_context({'image': image, 'captured_client_ms': 80, 'client_clock_id': 'fixture-browser'})
        early = ws.evidence_store.package(99)
        assert not any(i['kind'] == 'image' for i in early['items'])
        assert 'not_available' in {i['reason'] for i in early['excluded']}
        ws.freeze_evidence()
        assert ws.decision_image()['image'] == image
        clock[0] = 110
        await ws.set_context({'image': image, 'captured_client_ms': 101, 'client_clock_id': 'fixture-browser'})
        await ws.set_context({'image': image})
        package = ws.freeze_evidence()
        assert len([i for i in package['items'] if i['kind'] == 'image']) == 1
        assert {'clock_uncertain', 'unknown_capture'} <= {i['reason'] for i in package['excluded']}
    asyncio.run(run())


def test_frozen_model_reads_exclude_new_states_sets_candidates_but_edit_current_scope(workspace):
    async def run():
        ws = workspace
        old = ws.store.snapshot()
        ws.freeze_evidence()
        current = await ws.execute('edit_charts', {'view_ids': ['v2'], 'patch': {'source': {'region': 'MG', 'end': '2017-04-01'}}}, actor='user')
        revision = current['state']['revision']
        await ws.execute('save_category_set', {'name': 'Future set', 'revision': revision, 'view_id': 'v2'}, actor='user')
        history = await ws.execute('read_history', {})
        assert max(v['revision'] for v in history['result']['versions']) == old['revision']
        assert (await ws.execute('read_history', {'revision': revision}))['status'] == 'failed'
        assert (await ws.execute('list_category_sets', {}))['result']['category_sets'] == []
        candidates = (await ws.execute('list_evidence_candidates', {}))['result']['candidates']
        assert all(c['origin'] == 'chart' and c['revision'] <= old['revision'] for c in candidates)
        candidate = f"chart:{old['revision']}:v1"
        applied = await ws.execute('apply_evidence_candidate', {'candidate_id': candidate, 'view_ids': ['v2']})
        assert applied['committed']
        after = applied['state']
        assert after['views'][0] == current['state']['views'][0]
        assert after['views'][2] == current['state']['views'][2]
        assert after['views'][1]['source']['region'] == 'MG'
        assert after['views'][1]['source']['end'] == '2017-04-01'
        assert after['views'][1]['source']['metric'] == 'low_review_rate'
        assert after['views'][1]['source']['categories'] == old['views'][0]['source']['categories']
    asyncio.run(run())


def test_direct_and_bound_apply_identical_candidates(workspace):
    async def run():
        results = []
        for condition in ('direct', 'bound_revision'):
            workspace.reset('text', 'starter', '', condition)
            old = workspace.store.snapshot()
            await workspace.execute('edit_charts', {'view_ids': ['v2'], 'patch': {'source': {'region': 'MG'}}}, actor='user')
            workspace.freeze_evidence()
            result = await workspace.execute('apply_evidence_candidate', {'candidate_id': f"chart:{old['revision']}:v1", 'view_ids': ['v2']})
            assert result['committed']
            results.append(result['state'])
        # DuckDB parallel floating aggregates may differ at machine precision.
        for left, right in zip(results[0]['views'], results[1]['views']):
            ldata, rdata = left.pop('data'), right.pop('data')
            assert left == right
            lrows, rrows = ldata.pop('rows'), rdata.pop('rows')
            assert ldata == rdata
            assert len(lrows) == len(rrows)
            for lrow, rrow in zip(lrows, rrows):
                assert lrow == pytest.approx(rrow, rel=1e-12, abs=1e-12)
        assert results[0] == results[1]
    asyncio.run(run())


def test_context_capture_uploads_only_at_response_prepare_and_omits_private_answers(workspace):
    async def run():
        ws = workspace
        calls = []
        class Voice:
            async def context(self, value):
                calls.append(('context', value))
            async def image(self, value, frame_id=None):
                calls.append(('image', value))
        ws.voice = Voice()
        ws.trace.calibrations['fixture'] = {'offset_ms': 0, 'uncertainty_ms': 0, 'calibration_id': 'synthetic-fixture'}
        image = base64.b64encode(b'fixture bytes').decode()
        await ws.set_context({'image': image, 'captured_client_ms': 0, 'client_clock_id': 'fixture'})
        assert calls == []
        await ws.provider_event({'type': 'response_prepare', 'transport': 'websocket'})
        assert [kind for kind, _ in calls] == ['context', 'image']
        assert calls[-1][1] == image
        context = json.loads(ws.context())
        assert not {'expected', 'oracle', 'answer', 'resolution', 'target_sources'} & context.keys()
        assert all('preferred' not in c and 'correct' not in c for c in context['evidence_candidates'])
        ws.voice = None
    asyncio.run(run())
