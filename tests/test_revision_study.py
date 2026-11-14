"""Independent task/scorer checks. Authored operations never stand in for a model."""
from copy import deepcopy
from pathlib import Path

import pytest

from backend.charts import ChartStore
from backend.data import OlistData
from backend.oracle import category_rows
from backend.study import (REVISION_CASES, evidence_for_case, evaluate_revision,
                           revision_targets, setup_operations, tasks, diagnostic_tasks)


@pytest.fixture(scope='module')
def data():
    source = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    yield source
    source.close()


def prepare(task_id, data):
    store = ChartStore(data)
    for name, args in setup_operations(task_id, data):
        store.commit(store.prepare(name, args))
    return store, store.snapshot()


def event(store, ids, source, index=1):
    receipt = store.commit(store.prepare('edit_charts', {'view_ids': ids, 'patch': {'source': source}}))
    return {'name': 'tool_committed', 'actor': 'author', 'index': index, 'server_ms': index,
            'revision': receipt['state']['revision'], 'result': receipt['result']}


def request():
    return {'name': 'request_accepted', 'text': 'Authored revision', 'server_ms': 0}


def correct(task_id, store, initial, data):
    target = revision_targets(task_id, initial, data)
    return [event(store, [view_id], source, i + 1) for i, (view_id, source) in enumerate(target.items())
            if source != next(v['source'] for v in initial['views'] if v['id'] == view_id)]


def test_public_task_briefs_do_not_include_private_answers():
    assert len(tasks()) == 5
    assert len(diagnostic_tasks()) == 18
    assert sum(case['split'] == 'development' for case in REVISION_CASES) == 6
    assert sum(case['split'] == 'heldout' for case in REVISION_CASES) == 12
    for task in tasks() + diagnostic_tasks():
        assert not {'resolution', 'evidence_phase', 'evidence_indices', 'patch', 'targets'} & task.keys()


@pytest.mark.parametrize('task_id', [case['id'] for case in REVISION_CASES])
def test_reference_targets_pass_independent_raw_sql(task_id, data):
    store, initial = prepare(task_id, data)
    events = [request(), {'name': 'evidence_selected', 'evidence': evidence_for_case(task_id, data), 'server_ms': 0}]
    events.extend(correct(task_id, store, initial, data))
    report = evaluate_revision(task_id, initial, store.snapshot(), events, data, [])
    assert report['completed'], [c for c in report['checks'] if not c['passed']]
    assert report['review_status'] == 'pending'
    assert report['spoken_consistency'] is None and report['repair_turns'] is None


def test_oracle_does_not_call_runtime_query(data, monkeypatch):
    store, initial = prepare('rev_dev_01', data)
    events = [request()] + correct('rev_dev_01', store, initial, data)
    def forbidden(_):
        pytest.fail('Scorer reused runtime query implementation')
    monkeypatch.setattr(data, 'query', forbidden)
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), events, data, [])
    assert report['completed'] is True


def test_wrong_first_commit_is_not_erased_by_recovery(data):
    store, initial = prepare('rev_dev_01', data)
    events = [request(), event(store, ['v1'], {'region': 'SP'})]
    events += correct('rev_dev_01', store, initial, data)
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), events, data, [])
    assert report['completed'] is True
    assert report['first_commit_correct'] is False
    assert report['recovered_after_error'] is True


def test_correct_first_commit_and_wrong_final_are_reported_separately(data):
    store, initial = prepare('rev_dev_01', data)
    events = [request()] + correct('rev_dev_01', store, initial, data)
    events.append(event(store, ['v1'], {'region': 'SP'}, len(events)))
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), events, data, [])
    assert report['first_commit_correct'] is True
    assert report['completed'] is False
    assert report['all_revision_commits_correct'] is False


def test_pre_revision_publication_is_not_retroactively_wrong(data):
    store, initial = prepare('rev_dev_01', data)
    events = [event(store, ['v1'], {'region': 'SP'}), request()]
    events += correct('rev_dev_01', store, initial, data)
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), events, data, [])
    assert report['completed'] is True
    assert report['first_commit_correct'] is True
    assert report['pre_revision_commits_not_scored'] == 1


def test_final_success_without_recorded_publication_does_not_invent_first_success(data):
    store, initial = prepare('rev_dev_01', data)
    correct('rev_dev_01', store, initial, data)
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), [], data, [])
    assert report['completed'] is True
    assert report['first_commit_correct'] is None


def test_reference_resolution_must_precede_publication(data):
    store, initial = prepare('rev_dev_05', data)
    events = [request()] + correct('rev_dev_05', store, initial, data)
    unresolved = evaluate_revision('rev_dev_05', initial, store.snapshot(), events, data, [])
    assert unresolved['completed'] is False
    events += [{'name': 'evidence_selected', 'evidence': None, 'server_ms': 2},
               {'name': 'evidence_selected', 'evidence': evidence_for_case('rev_dev_05', data), 'server_ms': 3}]
    resolved = evaluate_revision('rev_dev_05', initial, store.snapshot(), events, data, [])
    assert resolved['completed'] is True and resolved['first_commit_correct'] is False


def test_rate_denominator_corruption_is_detected(data):
    store, initial = prepare('rev_dev_01', data)
    events = [request()] + correct('rev_dev_01', store, initial, data)
    final = deepcopy(store.snapshot())
    final['views'][1]['data']['rows'][0]['reviewed_orders'] += 10
    report = evaluate_revision('rev_dev_01', initial, final, events, data, [])
    assert report['completed'] is False


def test_first_partial_commit_does_not_claim_whole_task_completion(data):
    store, initial = prepare('rev_dev_01', data)
    target = revision_targets('rev_dev_01', initial, data)
    events = [request(), event(store, ['v1'], target['v1'])]
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), events, data, [])
    assert report['first_commit_correct'] is True
    assert report['all_revision_commits_correct'] is True
    assert report['completed'] is False
    assert 'first_revision_success' not in report


def test_cleared_reference_is_not_an_active_resolution(data):
    store, initial = prepare('rev_dev_05', data)
    events = [request(), {'name': 'evidence_selected', 'evidence': evidence_for_case('rev_dev_05', data), 'server_ms': 0},
              {'name': 'evidence_selected', 'evidence': None, 'server_ms': 1}]
    events += correct('rev_dev_05', store, initial, data)
    report = evaluate_revision('rev_dev_05', initial, store.snapshot(), events, data, [])
    assert report['completed'] is False
    assert report['first_commit_correct'] is False


def test_restoring_old_state_after_correct_edit_is_visible_in_process_score(data):
    store, initial = prepare('rev_dev_01', data)
    events = [request()] + correct('rev_dev_01', store, initial, data)
    state = store.restore(initial)['state']
    events.append({'name': 'restore', 'state': state, 'revision': state['revision'], 'server_ms': 10})
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), events, data, [])
    assert report['completed'] is False
    assert report['first_commit_correct'] is True
    assert report['all_revision_commits_correct'] is False
    assert report['commit_assessments'][-1]['event'] == 'restore'


def test_restoring_unchanged_snapshot_does_not_add_a_false_error(data):
    store, initial = prepare('rev_dev_01', data)
    events = [request()] + correct('rev_dev_01', store, initial, data)
    state = store.restore(store.snapshot())['state']
    events.append({'name': 'undo', 'state': state, 'revision': state['revision'], 'server_ms': 10})
    report = evaluate_revision('rev_dev_01', initial, store.snapshot(), events, data, [])
    assert report['completed'] is True
    assert report['all_revision_commits_correct'] is True
    assert report['unchanged_restores_not_scored'] == 1


def test_initial_and_current_comparison_sets_are_distinguishable(data):
    store, initial = prepare('rev_dev_01', data)
    assert set(evidence_for_case('rev_dev_01', data)['members']) != set(initial['views'][0]['data']['selection']['members'])
    source = revision_targets('rev_dev_01', initial, data)['v1']
    rows = category_rows(data, source)
    assert [row['label'] for row in rows] == evidence_for_case('rev_dev_01', data)['members']
    assert source['region'] == 'MG'


@pytest.mark.parametrize('task_id', ['rev_dev_01', 'rev_dev_04'])
def test_target_category_order_does_not_change_object_correctness(task_id, data):
    store, initial = prepare(task_id, data)
    targets = revision_targets(task_id, initial, data)
    events = [request()]
    for view in initial['views']:
        source = targets[view['id']]
        if source != view['source']:
            source['categories'] = list(reversed(source['categories']))
            events.append(event(store, [view['id']], source, len(events)))
    report = evaluate_revision(task_id, initial, store.snapshot(), events, data, [])
    assert report['completed'] is True
    assert report['first_commit_correct'] is True
    assert report['all_revision_commits_correct'] is True
    numeric_checks = [check for check in report['checks'] if 'members, values and denominators' in check['name']]
    assert numeric_checks and all(check['passed'] for check in numeric_checks)


def test_reordering_categories_outside_requested_scope_is_still_a_change(data):
    store, initial = prepare('rev_dev_04', data)
    events = [request()] + correct('rev_dev_04', store, initial, data)
    categories = initial['views'][0]['source']['categories']
    events.append(event(store, ['v1'], {'categories': list(reversed(categories))}, len(events)))
    report = evaluate_revision('rev_dev_04', initial, store.snapshot(), events, data, [])
    assert report['completed'] is False
    assert report['all_revision_commits_correct'] is False
    assert {'name': 'v1 untouched', 'passed': False} in report['checks']


@pytest.mark.parametrize('metric_first', [True, False])
def test_same_chart_metric_and_members_can_be_revised_in_either_order(data, metric_first):
    store, initial = prepare('rev_dev_02', data)
    target = revision_targets('rev_dev_02', initial, data)['v2']
    metric = {'metric': target['metric']}
    members = {'categories': target['categories'], 'top_n': None}
    patches = [metric, members] if metric_first else [members, metric]
    events = [request(), event(store, ['v2'], patches[0])]
    partial = evaluate_revision('rev_dev_02', initial, store.snapshot(), events, data, [])
    assert partial['completed'] is False
    assert partial['first_commit_correct'] is True
    events.append(event(store, ['v2'], patches[1], 2))
    report = evaluate_revision('rev_dev_02', initial, store.snapshot(), events, data, [])
    assert report['completed'] is True
    assert report['all_revision_commits_correct'] is True
    assert report['incorrect_commit_count'] == 0
    assert report['recovered_after_error'] is False


def test_partial_edit_cannot_change_a_region_that_should_be_retained(data):
    store, initial = prepare('rev_dev_02', data)
    target = revision_targets('rev_dev_02', initial, data)['v2']
    events = [request(), event(store, ['v2'], {'metric': target['metric'], 'region': 'SP'})]
    events.append(event(store, ['v2'], target, 2))
    report = evaluate_revision('rev_dev_02', initial, store.snapshot(), events, data, [])
    assert report['completed'] is True
    assert report['first_commit_correct'] is False
    assert report['recovered_after_error'] is True
    assert 'v2 source.region' in report['commit_assessments'][0]['failed_checks']
