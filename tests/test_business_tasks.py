"""Real-data checks for participant outcomes, without a gold business decision."""
import json
from pathlib import Path

import pytest

from backend.business_tasks import BUSINESS_PROTOCOL, business_tasks
from backend.charts import ChartStore
from backend.data import OlistData
from backend.study import (diagnostic_tasks, evaluate, evidence_for_case, revision_case,
                           revision_targets, setup_operations, task_brief, tasks)


@pytest.fixture(scope='module')
def data():
    source = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    yield source
    source.close()


def prepare(task_id, data):
    store = ChartStore(data)
    for name, arguments in setup_operations(task_id, data):
        store.commit(store.prepare(name, arguments))
    return store, store.snapshot()


def publish(store, ids, source):
    receipt = store.commit(store.prepare('edit_charts', {'view_ids': ids, 'patch': {'source': source}}))
    return {'name': 'tool_committed', 'actor': 'authored-script', 'server_ms': 1,
            'revision': receipt['state']['revision'], 'result': receipt['result']}


def solve(task_id, store, initial, data):
    targets = revision_targets(task_id, initial, data)
    return [{'name': 'request_accepted', 'text': task_brief(task_id)['goal'], 'server_ms': 0}] + [
        publish(store, [f'v{number}'], targets[f'v{number}']) for number in revision_case(task_id)['targets']]


def test_primary_tasks_and_diagnostic_ids_are_separate():
    assert len(tasks()) == 5
    assert tasks()[0]['id'] == 'starter'
    assert len(diagnostic_tasks()) == 18
    assert {task['id'] for task in tasks()[1:]} == {task['id'] for task in business_tasks()}
    for task in tasks() + diagnostic_tasks():
        assert task_brief(task['id']) == task
        assert not {'patch', 'targets', 'resolution', 'evidence_phase', 'phases'} & task.keys()
    assert task_brief('region_linked')['kind'] == 'linked'


@pytest.mark.parametrize('task_id', [task['id'] for task in business_tasks()])
def test_authored_business_outcomes_use_independent_oracle(task_id, data, monkeypatch):
    store, initial = prepare(task_id, data)
    events = solve(task_id, store, initial, data)

    def forbidden(_):
        pytest.fail('The evaluator must not reuse the runtime query.')

    monkeypatch.setattr(data, 'query', forbidden)
    report = evaluate(task_id, initial, store.snapshot(), events, data, [])
    assert report['technical_completed'] and report['completed']
    assert report['all_revision_commits_correct']
    assert report['protocol'] == BUSINESS_PROTOCOL
    assert report['interpretation_status'] == report['review_status'] == 'pending'
    assert report['business_conclusion_correct'] is report['understanding_correct'] is None
    assert report['task_response'] is None and not report['task_response_submitted']
    assert report['task_response_status'] == 'none' and not report['task_response_current']
    assert report['task_response_recorded_revision'] is report['task_response_revision_mismatch'] is None
    assert report['task_response_final_revision'] == store.snapshot()['revision']


def test_participant_response_is_recorded_without_grading_or_inferred_intent(data):
    task_id = 'biz_01_sp_priorities_mg'
    store, initial = prepare(task_id, data)
    events = solve(task_id, store, initial, data)
    response = {'conclusion': 'I need more evidence.', 'rationale': 'These charts do not establish causes.',
                'object_origin': 'My own claim about origin.', 'calculation_scope': 'My own claim about scope.',
                'revision': store.snapshot()['revision']}
    report = evaluate(task_id, initial, store.snapshot(), events, data, [], response)
    assert report['task_response'] == response and report['task_response_submitted']
    assert report['task_response_status'] == 'current' and report['task_response_current']
    assert report['task_response_revision_mismatch'] is False
    assert report['interpretation_status'] == 'pending'
    assert report['business_conclusion_correct'] is report['understanding_correct'] is None
    assert report['technical_completed']


def test_response_saved_before_chart_revision_stays_stale_until_resaved(data):
    task_id = 'biz_01_sp_priorities_mg'
    store, initial = prepare(task_id, data)
    assert initial['revision'] == 6
    response = {'conclusion': 'Investigate service in this comparison.',
                'rationale': 'Draft evidence to reconsider after the edit.',
                'object_origin': 'SP categories.', 'calculation_scope': 'MG in 2017.',
                'revision': 6, 'submitted_at': '2026-11-13T04:00:00+00:00'}
    before = evaluate(task_id, initial, store.snapshot(), [], data, [], response)
    assert before['task_response_status'] == 'current'
    assert before['technical_completed'] is False
    members = evidence_for_case(task_id, data)['members']
    events = [{'name': 'request_accepted', 'text': 'Use the SP set for MG service.', 'server_ms': 0},
              publish(store, ['v2', 'v3'], {'categories': members, 'top_n': None})]
    assert store.snapshot()['revision'] == 7
    finished = evaluate(task_id, initial, store.snapshot(), events, data, [], response)
    assert finished['technical_completed'] and finished['task_response_submitted']
    assert finished['task_response_status'] == 'stale' and not finished['task_response_current']
    assert finished['task_response_recorded_revision'] == 6
    assert finished['task_response_final_revision'] == 7
    assert finished['task_response_revision_mismatch'] is True
    assert finished['task_response'] == response
    assert finished['interpretation_status'] == 'pending'
    assert finished['business_conclusion_correct'] is finished['understanding_correct'] is None

    resaved = {**response, 'revision': 7, 'submitted_at': '2026-11-13T04:01:00+00:00'}
    reviewed = evaluate(task_id, initial, store.snapshot(), events, data, [], resaved)
    assert reviewed['task_response_status'] == 'current' and reviewed['task_response_current']
    assert reviewed['task_response_submitted'] and not reviewed['task_response_revision_mismatch']
    assert reviewed['task_response'] == resaved
    assert reviewed['interpretation_status'] == 'pending'
    assert reviewed['business_conclusion_correct'] is reviewed['understanding_correct'] is None


def test_partial_response_at_current_revision_remains_incomplete(data):
    task_id = 'biz_04_stable_metric_control'
    store, initial = prepare(task_id, data)
    response = {'conclusion': 'Review financial scale.', 'rationale': '   ',
                'object_origin': '', 'calculation_scope': '', 'revision': initial['revision']}
    report = evaluate(task_id, initial, store.snapshot(), [], data, [], response)
    assert report['task_response_status'] == 'incomplete'
    assert not report['task_response_submitted'] and not report['task_response_current']
    assert report['task_response_revision_mismatch'] is False
    assert report['task_response'] == response


@pytest.mark.parametrize('task_id', ['biz_01_sp_priorities_mg', 'biz_03_seasonal_same_cohort'])
def test_history_cohort_is_distinct_from_current_and_not_hidden_in_brief(task_id, data):
    _, initial = prepare(task_id, data)
    historical = evidence_for_case(task_id, data)['members']
    current = initial['views'][0]['source']['categories']
    assert set(historical) != set(current)
    serialized = json.dumps(task_brief(task_id))
    assert all(member not in serialized for member in historical)


def test_keeping_current_mg_cohort_does_not_complete_sp_priority_task(data):
    task_id = 'biz_01_sp_priorities_mg'
    store, initial = prepare(task_id, data)
    report = evaluate(task_id, initial, store.snapshot(), [], data, [])
    assert not report['technical_completed']


def test_service_edit_cannot_change_local_volume_reference(data):
    task_id = 'biz_01_sp_priorities_mg'
    store, initial = prepare(task_id, data)
    events = solve(task_id, store, initial, data)
    events.append(publish(store, ['v1'], {'categories': evidence_for_case(task_id, data)['members'], 'top_n': None}))
    report = evaluate(task_id, initial, store.snapshot(), events, data, [])
    assert not report['technical_completed']
    assert {'name': 'v1 untouched', 'passed': False} in report['checks']


def test_release_requires_dynamic_rule_even_if_fixed_members_match(data):
    task_id = 'biz_02_mg_local_priorities'
    store, initial = prepare(task_id, data)
    target = revision_targets(task_id, initial, data)['v1']
    selected = [row['label'] for row in data.query(target)['rows']]
    events = [publish(store, ['v1', 'v2', 'v3'], {'categories': selected, 'top_n': None})]
    report = evaluate(task_id, initial, store.snapshot(), events, data, [])
    assert not report['technical_completed']
    assert any(check['name'] == 'v1 source.categories' and not check['passed'] for check in report['checks'])


def test_seasonal_task_preserves_q4_values_instead_of_restoring_q1(data):
    task_id = 'biz_03_seasonal_same_cohort'
    store, initial = prepare(task_id, data)
    events = solve(task_id, store, initial, data)
    events.append(publish(store, ['v2', 'v3'], {'start': '2017-01-01', 'end': '2017-04-01'}))
    report = evaluate(task_id, initial, store.snapshot(), events, data, [])
    assert not report['technical_completed']
    assert any(check['name'] == 'v2 source.start' and not check['passed'] for check in report['checks'])


def test_business_target_presentation_is_free_but_untouched_service_views_are_not(data):
    task_id = 'biz_04_stable_metric_control'
    store, initial = prepare(task_id, data)
    events = solve(task_id, store, initial, data)
    store.commit(store.prepare('edit_charts', {'view_ids': ['v1'], 'patch': {'style': {'color': '#336699'}}}))
    assert evaluate(task_id, initial, store.snapshot(), events, data, [])['technical_completed']
    store.commit(store.prepare('edit_charts', {'view_ids': ['v2'], 'patch': {'style': {'color': '#336699'}}}))
    assert not evaluate(task_id, initial, store.snapshot(), events, data, [])['technical_completed']
