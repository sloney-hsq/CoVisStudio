"""Real Olist matching and scoring checks, not participant difficulty claims."""
from pathlib import Path

import pytest

from backend.business_tasks import EXPERIMENT_PROTOCOL, experiment_tasks
from backend.data import OlistData
from backend.study import evaluate, revision_targets, task_brief, tasks, diagnostic_tasks
from scripts.verify_matched_tasks import commit, matching_audit, setup, solve


@pytest.fixture(scope='module')
def data():
    data = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    yield data
    data.close()


def test_public_variants_leave_original_materials_intact():
    assert len(tasks()) == 5 and len(diagnostic_tasks()) == 18
    variants = experiment_tasks()
    assert [entry['id'] for entry in variants] == [f'exp_{family:02d}_{variant}' for family in range(1, 5) for variant in ('a', 'b')]
    for brief in variants:
        assert task_brief(brief['id']) == brief
        assert brief['protocol'] == EXPERIMENT_PROTOCOL
        assert brief['business_goal'] and brief['mandatory_outcomes'] and brief['response_prompt']
        assert not {'resolution', 'phases', 'targets', 'patch', 'evidence_phase', 'members'} & brief.keys()
        assert brief['duration_minutes'] == 8 and brief['voice_budget_seconds'] == 60


def test_matching_is_structural_and_data_supported_not_a_human_claim(data):
    audit = matching_audit(data)
    assert audit['all_pairs_passed']
    assert audit['human_difficulty_equivalence'] == 'not_established'
    assert all(pair['current_cohort_order_count_ratio'] < 2 for pair in audit['pairs'])
    for pair in audit['pairs']:
        assert pair['structural_match'] and pair['cohort_overlap_matched'] and pair['positive_denominators']
    for case in audit['variants']:
        assert case['data']['minimum_review_denominator'] >= 40
        assert case['data']['minimum_delivery_denominator'] >= 40
        assert case['data']['cohort_overlap_count'] == (3 if case['family_id'] == '04' else 2)


@pytest.mark.parametrize('task_id', [entry['id'] for entry in experiment_tasks()])
@pytest.mark.parametrize('condition', ['direct', 'bound_revision'])
def test_both_methods_complete_each_variant_with_independent_sql(task_id, condition, data, tmp_path, monkeypatch):
    store, initial, snapshots, trace = setup(task_id, data, tmp_path)
    solve(task_id, store, snapshots, trace, condition)

    def forbidden(_):
        pytest.fail('Matched scoring reused runtime query implementation')

    monkeypatch.setattr(data, 'query', forbidden)
    report = evaluate(task_id, initial, store.snapshot(), trace.events, data, [])
    assert report['technical_completed'] and report['all_revision_commits_correct']
    assert report['protocol'] == EXPERIMENT_PROTOCOL
    assert report['family_id'] == task_id.split('_')[1]
    assert report['variant_id'] == task_id.split('_')[2]
    assert report['first_full_correct_revision'] == initial['revision'] + 1
    assert report['commit_assessments'][0]['full_correct']
    assert report['interpretation_status'] == report['review_status'] == 'pending'
    assert report['business_conclusion_correct'] is report['understanding_correct'] is None
    assert report['task_response_status'] == 'none'


def test_first_correct_partial_commit_is_not_full_task_completion(data, tmp_path):
    task_id = 'exp_01_a'
    store, initial, snapshots, trace = setup(task_id, data, tmp_path)
    targets = revision_targets(task_id, initial, data)
    for view_id in ('v2', 'v3'):
        args = {'view_ids': [view_id], 'patch': {'source': targets[view_id]}}
        commit(store, store.prepare('edit_charts', args), trace, 'edit_charts', args)
    report = evaluate(task_id, initial, store.snapshot(), trace.events, data, [])
    assert report['first_commit_correct']
    assert [entry['full_correct'] for entry in report['commit_assessments']] == [False, True]
    assert report['first_full_correct_revision'] == initial['revision'] + 2
    assert report['first_full_correct_event_index'] == report['commit_assessments'][1]['event_index']


def test_experiment_response_freshness_is_preserved(data, tmp_path):
    store, initial, snapshots, trace = setup('exp_04_b', data, tmp_path)
    response = {'conclusion': 'A provisional decision.', 'rationale': 'To be reviewed.',
                'object_origin': 'The current fixed cohort.', 'calculation_scope': 'MG in 2017.',
                'revision': initial['revision']}
    solve('exp_04_b', store, snapshots, trace, 'direct')
    report = evaluate('exp_04_b', initial, store.snapshot(), trace.events, data, [], response)
    assert report['technical_completed'] and report['task_response_status'] == 'stale'
    assert report['task_response'] == response and report['task_response_submitted']
    assert report['understanding_correct'] is None


def test_explicit_trial_start_scores_manual_edits_without_invented_request(data, tmp_path):
    task_id = 'exp_04_a'
    store, initial, snapshots, trace = setup(task_id, data, tmp_path)
    solve(task_id, store, snapshots, trace, 'direct')
    events = [{'name': 'trial_started', 'server_ms': 0, 'index': 0}] + [
        event for event in trace.events if event['name'] == 'tool_committed' and event['actor'] != 'starter']
    report = evaluate(task_id, initial, store.snapshot(), events, data, [])
    assert report['technical_completed'] and report['all_revision_commits_correct']
    assert report['counts']['request_accepted'] == 0
    assert report['pre_revision_commits_not_scored'] == 0
    assert report['first_full_correct_revision'] == store.snapshot()['revision']
