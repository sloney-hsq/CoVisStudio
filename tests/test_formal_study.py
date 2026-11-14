"""Formal choices, locked assignment and first-Begin accounting; no model calls."""
from copy import deepcopy
import csv
from io import StringIO
from pathlib import Path

import pytest

from backend.charts import ChartStore
from backend.data import OlistData
from backend.experiment import (allocation_for, formal_allocation_for, formal_allocation_table,
                                validate_formal_assignment, formal_manifest,
                                formal_primary_attempts, formal_assignment_csv)
from backend.formal_tasks import (FORMAL_PROTOCOL, formal_tasks, formal_task_brief,
                                  formal_setup_operations, content_sha256)


def archive(session_id, *, minute=0, begin=True, reason=None, kind='participant', report=None):
    assignment = formal_allocation_for(1)['trials'][0]
    at = f'2026-11-13T12:{minute:02d}:00+00:00'
    events = [{'name': 'trial_started', 'index': 1, 'at': at, 'server_ms': minute * 60000}] if begin else []
    if reason:
        events.append({'name': 'trial_finished', 'index': 2, 'at': at,
                       'server_ms': minute * 60000 + 10000, 'reason': reason})
    return {'session': {'id': session_id, 'participant_id': 'P01', 'started_at': at,
                        'assignment': assignment, 'condition': assignment['condition'],
                        'mode': 'live_voice', 'evidence_kind': kind},
            'events': events, 'report': report}


ROSTER = [{'participant_id': 'P01', 'participant_slot': 1}]


def test_formal_materials_leave_member_and_ranking_decisions_open():
    tasks = formal_tasks()
    assert len(tasks) == 8
    assert {task['id'] for task in tasks} == {f'study_{family:02d}_{variant}'
                                             for family in range(1, 5) for variant in ('a', 'b')}
    for task in tasks:
        assert task['participant_choices'] and task['hard_constraints']
        assert task['material_review'] == 'pending'
        assert not {'expected_sources', 'resolution', 'evidence_phase', 'action', 'targets'} & task.keys()
        for constraint in task['hard_constraints']:
            assert not {'categories', 'top_n', 'rank_by'} & constraint.get('required', {}).keys()
    # Pair matching describes structure, not equivalence of human evidence interpretation.
    for family in range(1, 5):
        first, second = tasks[(family - 1) * 2:family * 2]
        assert [c['kind'] for c in first['hard_constraints']] == [c['kind'] for c in second['hard_constraints']]
        assert first['difficulty_equivalence'] == second['difficulty_equivalence'] == 'not_established'


def test_new_assignments_keep_balance_and_old_assignments_unchanged():
    old = deepcopy(allocation_for(1))
    table = formal_allocation_table()
    assert table['participant_count'] == 30
    assert table['balance']['condition_counts'] == {'direct': 60, 'bound_revision': 60}
    assert (table['balance']['cell_min'], table['balance']['cell_max']) == (1, 2)
    assert not table['balance']['exact_full_balance']
    trials = [trial for plan in table['allocations'] for trial in plan['trials']]
    assert len({trial['trial_id'] for trial in trials}) == 120
    for plan in table['allocations']:
        assert {trial['family_id'] for trial in plan['trials']} == {'01', '02', '03', '04'}
        assert sum(trial['condition'] == 'direct' for trial in plan['trials']) == 2
    for trial in trials:
        assert trial['mode'] == 'live_voice'
        assert trial['time_limit_seconds'] == 480 and trial['voice_budget_seconds'] == 60
        assert trial['voice_windows_per_trial'] == 1
        assert trial['material_sha256'] == content_sha256(formal_task_brief(trial['task_id']))
    assert allocation_for(1) == old
    assert old['trials'][0]['task_id'].startswith('exp_')


def test_formal_assignment_rejects_changed_condition_transport_and_material():
    assignment = formal_allocation_for(1)['trials'][0]
    assert validate_formal_assignment(assignment, condition='direct', mode='live_voice') == assignment
    with pytest.raises(ValueError, match='condition is locked'):
        validate_formal_assignment(assignment, condition='bound_revision')
    with pytest.raises(ValueError, match='live_voice'):
        validate_formal_assignment(assignment, mode='text')
    edited = {**assignment, 'task_id': 'study_01_b'}
    with pytest.raises(ValueError, match='assignment is fixed'):
        validate_formal_assignment(edited)


def test_manifest_is_reproducible_and_does_not_approve_human_freeze_items():
    first, second = formal_manifest(), formal_manifest()
    assert first == second
    assert first['conditions'] == ['direct', 'bound_revision']
    assert first['approved_by'] is first['approved_at'] is None
    assert first['collection_status'] == 'pending_human_review'
    assert set(first['required_reviews'].values()) == {'pending'}
    assert not first['voice_window']['interruption_required']


def test_primary_is_first_actual_participant_begin_including_unscored_failure():
    authored = archive('authored', minute=0, reason='completed', kind='local_authored', report={'pass': True})
    prepared = archive('prepared', minute=1, begin=False)
    original = archive('original-unscored', minute=2, reason='timeout')
    repeat = archive('later-success', minute=3, reason='completed', report={'pass': True})
    repeat['session']['repeat_reason'] = 'Participant requested an additional practice attempt.'
    records = [repeat, prepared, original, authored]
    before = deepcopy(records)
    result = formal_primary_attempts(records, ROSTER)
    assert records == before
    assert result['assigned_trial_count'] == 4 and result['attempt_count'] == 3
    assert result['primary_attempts'][0]['session_id'] == 'original-unscored'
    row = result['assigned_rows'][0]
    assert row['primary_status'] == 'timeout' and not row['primary_report_available']
    assert row['repeat_session_ids'] == ['later-success']
    by_id = {attempt['session_id']: attempt for attempt in result['attempt_rows']}
    assert by_id['prepared']['attempt_role'] == 'prepared'
    assert by_id['prepared']['attempt_index'] is None
    assert by_id['later-success']['attempt_role'] == 'repeat'
    assert by_id['later-success']['repeat_reason']
    assert len(result['non_primary_records']) == 1
    assert len(result['all_records']) == 4
    assert row['revision_correct'] is row['understanding_correct'] is None
    assert len(result['missing_trials']) == 3


def test_preparation_does_not_win_over_earlier_actual_begin():
    earlier_preparation = archive('prepared-first', minute=0)
    earlier_preparation['events'][0]['at'] = '2026-11-13T12:04:00+00:00'
    earlier_begin = archive('begun-first', minute=2)
    result = formal_primary_attempts([earlier_preparation, earlier_begin], ROSTER)
    assert result['primary_attempts'][0]['session_id'] == 'begun-first'
    assert result['primary_attempts'][0]['status'] == 'running'


def test_actual_roster_keeps_missing_and_prepared_assignments_in_csv():
    records = [archive('prepared', begin=False)]
    result = formal_primary_attempts(records, ROSTER + [{'participant_id': 'P02', 'participant_slot': 2}])
    assert result['registered_participant_count'] == 2 and len(result['missing_trials']) == 8
    rows = list(csv.DictReader(StringIO(formal_assignment_csv(result))))
    assert len(rows) == 8
    assert rows[0]['missing_reason'] == 'no_actual_begin'
    assert all(row['primary_session_id'] == '' for row in rows)
    assert rows[4]['missing_reason'] == 'no_archive'
    assert formal_primary_attempts([], [])['assigned_trial_count'] == 0


def test_formal_archive_requires_roster_and_cannot_be_relabelled():
    with pytest.raises(ValueError, match='roster'):
        formal_primary_attempts([archive('unregistered')], [])
    changed = archive('changed-condition')
    changed['session']['condition'] = 'bound_revision'
    with pytest.raises(ValueError, match='condition is locked'):
        formal_primary_attempts([changed], ROSTER)


def test_all_formal_materials_seed_real_charts_without_reading_evaluator_answers(monkeypatch):
    from backend import study

    def forbidden(*args, **kwargs):
        pytest.fail('Formal setup must not read fixed diagnostic answers.')

    monkeypatch.setattr(study, 'expected_sources', forbidden)
    monkeypatch.setattr(study, 'revision_targets', forbidden)
    data = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    try:
        for task in formal_tasks():
            store = ChartStore(data)
            for name, arguments in formal_setup_operations(task['id'], data):
                store.commit(store.prepare(name, arguments))
            assert [view['number'] for view in store.state['views']] == [1, 2, 3]
            assert all(view['data']['rows'] for view in store.state['views'])
            assert [view['source']['metric'] for view in store.state['views']] == [
                'orders', 'low_review_rate', 'avg_delivery_days']
    finally:
        data.close()
