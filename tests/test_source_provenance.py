"""Actual Olist source identity, shared execution and offline intent scoring. No API."""
import asyncio
from copy import deepcopy
import json

import pytest

from backend.app import Workspace
from backend.providers import QwenRealtime
from backend.intent_scoring import compare_state, validate_resolved_intent
from test_workspace import local_settings


@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    ws = Workspace(local_settings(tmp_path_factory.mktemp('provenance')))
    ws.data.connection.execute('SET threads=1')
    yield ws
    ws.data.close()


async def setup(ws, condition='bound_revision'):
    ws.reset('live_voice', 'exp_01_a', '', condition)
    await ws.choose_evidence({'revision': 3, 'view_id': 'v1'})
    await ws.provider_event({'type': 'speech_start', 'item_id': 'start'})
    return ws.store.snapshot()


@pytest.mark.parametrize('candidate_id,basis', [(None, 'selection'), ('chart:3:v1', 'explicit_match'),
                                               ('chart:1:v1', 'explicit_override')])
def test_source_identity_and_parity_without_replacing_explicit_choice(workspace, candidate_id, basis):
    async def run():
        records = []
        for condition in ('direct', 'bound_revision'):
            before = await setup(workspace, condition)
            args = {'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence'}
            if candidate_id:
                args['candidate_id'] = candidate_id
            context = json.loads(workspace.context())
            assert context['selected_evidence_source']['candidate_id'] == 'chart:3:v1'
            receipt = await workspace.execute('revise_analysis', args)
            assert receipt['committed'] is True
            card = receipt['result']['revision_card']
            provenance = card['execution_provenance']
            assert provenance['selected_source_at_onset']['candidate_id'] == 'chart:3:v1'
            assert provenance['executed_source']['candidate_id'] == (candidate_id or 'chart:3:v1')
            assert provenance['source_basis'] == basis
            assert provenance['members_equal'] is True
            assert provenance['lineage_equal'] == (candidate_id != 'chart:1:v1')
            assert provenance['candidate_ids_equal'] == (candidate_id != 'chart:1:v1')
            assert provenance['overrides_selection'] == (candidate_id == 'chart:1:v1')
            assert receipt['state']['views'][0] == before['views'][0]
            for old, new in zip(before['views'][1:], receipt['state']['views'][1:]):
                assert new['membership_origin'] == provenance['executed_source']
                assert all(new['source'][key] == old['source'][key] for key in ('region', 'metric', 'start', 'end', 'status'))
            records.append((receipt['state'], card, workspace.instructions()))
        assert records[0] == records[1]
    asyncio.run(run())


def test_saved_set_lineage_is_not_an_override(workspace):
    async def run():
        for condition in ('direct', 'bound_revision'):
            await setup(workspace, condition)
            three = (await workspace.execute('save_category_set', {
                'name': 'Set from version 3', 'revision': 3, 'view_id': 'v1'}, actor='user'))['result']['category_set']
            one = (await workspace.execute('save_category_set', {
                'name': 'Set from version 1', 'revision': 1, 'view_id': 'v1'}, actor='user'))['result']['category_set']
            receipt = await workspace.execute('revise_analysis', {
                'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence',
                'candidate_id': f"set:{three['id']}"})
            assert receipt['committed'] is True
            provenance = receipt['result']['revision_card']['execution_provenance']
            assert provenance['executed_source']['candidate_id'] == f"set:{three['id']}"
            assert provenance['executed_source']['lineage_id'] == provenance['selected_source_at_onset']['lineage_id'] == 'chart:3:v1'
            assert (provenance['lineage_equal'], provenance['candidate_ids_equal'],
                    provenance['overrides_selection'], provenance['members_equal']) == (True, False, False, True)
            assert provenance['source_basis'] == 'explicit_match'
            assert [view['membership_origin']['candidate_id'] for view in receipt['state']['views'][1:]] == [f"set:{three['id']}", f"set:{three['id']}"]
            other = await workspace.execute('revise_analysis', {
                'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence',
                'candidate_id': f"set:{one['id']}"})
            overridden = other['result']['revision_card']['execution_provenance']
            assert overridden['overrides_selection'] is True
            assert overridden['lineage_equal'] is False
    asyncio.run(run())


def test_explicit_different_members_and_rerank_preserve_untouched_provenance(workspace):
    async def run():
        await setup(workspace)
        # Current MG categories differ from the selected historical RJ set.
        receipt = await workspace.execute('revise_analysis', {'view_ids': ['v2', 'v3'],
            'member_action': 'use_evidence', 'candidate_id': 'chart:6:v1'})
        provenance = receipt['result']['revision_card']['execution_provenance']
        assert provenance['overrides_selection'] is True and provenance['members_equal'] is False
        prior = deepcopy(receipt['state'])
        corrected = await workspace.execute('revise_analysis', {'view_ids': ['v3'],
            'member_action': 'keep_current', 'end': '2017-07-01'})
        assert corrected['state']['views'][2]['membership_origin'] == prior['views'][2]['membership_origin']
        before = corrected['state']
        reranked = await workspace.execute('revise_analysis', {'view_ids': ['v2'],
            'member_action': 'rerank', 'top_n': 3, 'rank_by': 'orders'})
        card = reranked['result']['revision_card']
        assert card['evidence'] is None and card['origin'] is None
        assert card['execution_provenance']['executed_source'] is None
        assert card['execution_provenance']['selected_source_at_onset']['candidate_id'] == 'chart:3:v1'
        assert 'membership_origin' not in reranked['state']['views'][1]
        assert reranked['state']['views'][0] == before['views'][0]
        assert reranked['state']['views'][2] == before['views'][2]
        assert prior['views'][1]['membership_origin']['candidate_id'] == 'chart:6:v1'
        assert any(e['name'] == 'tool_committed' and e['result'].get('revision_card', {}).get('execution_provenance', {}).get('executed_source')
                   for e in workspace.trace.events)
    asyncio.run(run())


def test_fragments_revoke_each_time_but_bind_once_then_next_utterance_uses_new_click(workspace):
    async def run():
        await setup(workspace)
        provider = QwenRealtime({}, 'live_voice', [], workspace.provider_event, workspace.execute)
        await provider._speech_started('part1')
        bound = deepcopy(workspace.bound_reference)
        epoch = workspace.epoch
        await workspace.choose_evidence({'revision': 1, 'view_id': 'v1'})
        workspace.reference = {**workspace.reference, 'view_ids': ['v2']}
        await provider._speech_started('part2')
        assert workspace.epoch == epoch + 1
        assert workspace.bound_reference == bound
        assert workspace.bound_evidence['revision'] == 3
        starts = [e for e in workspace.trace.events if e['name'] == 'speech_start']
        assert starts[-1]['event']['continuation'] is True
        assert starts[-1]['event']['speech_group_id'] == 'part1'
        provider.response_started_since_speech = True
        await provider._speech_started('next')
        assert workspace.bound_evidence['revision'] == 1
        assert workspace.bound_reference['view_ids'] == ['v2']
    asyncio.run(run())


def test_independent_source_requirement_not_ui_selection_or_sql(workspace):
    async def run():
        base = await setup(workspace)
        receipt = await workspace.execute('revise_analysis', {'view_ids': ['v2', 'v3'],
            'member_action': 'use_evidence', 'candidate_id': 'chart:1:v1'})
        observed = receipt['state']
        intent = {'target_view_ids': ['v2', 'v3'], 'source_patch': {},
            'members': {'mode': 'fixed', 'values': workspace.bound_evidence['members']},
            'retained_fields': ['region', 'start', 'end', 'metric'], 'released_fields': [],
            'source_requirement': {'mode': 'exact', 'candidate_id': 'chart:3:v1',
                                   'reason': 'Fixture explicitly says use the selected version.'}}
        validate_resolved_intent(intent)
        result = compare_state(base, observed, intent, workspace.data)
        assert result['analytical_correct'] and result['numeric_correct']
        assert result['provenance_correct'] is False and result['correct'] is False
        intent['source_requirement']['mode'] = 'members_only'
        assert compare_state(base, observed, intent, workspace.data)['correct'] is True
        unrecorded = deepcopy(observed)
        for view in unrecorded['views'][1:]:
            view.pop('membership_origin')
        intent['source_requirement']['mode'] = 'exact'
        assert compare_state(base, unrecorded, intent, workspace.data)['correct'] is None
        intent['source_requirement'].update(mode='exact', candidate_id='chart:1:v1',
                                            reason='Fixture explicitly overrides the selected version.')
        assert compare_state(base, observed, intent, workspace.data)['correct'] is True
        intent['source_requirement']['mode'] = 'unknown'
        assert compare_state(base, observed, intent, workspace.data)['correct'] is None
        saved = (await workspace.execute('save_category_set', {
            'name': 'Selected version', 'revision': 3, 'view_id': 'v1'}, actor='user'))['result']['category_set']
        set_receipt = await workspace.execute('revise_analysis', {
            'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence',
            'candidate_id': f"set:{saved['id']}"})
        set_observed = set_receipt['state']
        intent['source_requirement'] = {'mode': 'exact', 'candidate_id': 'chart:3:v1',
                                        'reason': 'Fixture requires the selected chart version.'}
        assert compare_state(base, set_observed, intent, workspace.data)['correct'] is True
        intent['source_requirement']['candidate_id'] = 'chart:1:v1'
        assert compare_state(base, set_observed, intent, workspace.data)['correct'] is False
        intent['source_patch'] = {'region': 'SP'}
        assert compare_state(base, observed, intent, workspace.data)['correct'] is False
    asyncio.run(run())
