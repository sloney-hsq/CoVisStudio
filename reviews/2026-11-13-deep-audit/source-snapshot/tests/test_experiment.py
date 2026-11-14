"""Allocation balance, timed evidence and complete attempt accounting."""
import csv
from io import StringIO

import pytest

from backend.experiment import allocation_for, allocation_table, build_trial_report, aggregate_reports, report_csv


def event(index, name, clock, **details):
    return {'index': index, 'name': name, 'server_ms': clock,
            'at': f'2026-11-13T12:00:{index:02d}+00:00', **details}


def trial_report(slot=1, trial_index=1, attempt='attempt-1', correct=True,
                 reason='completed', kind='local_authored', minute=0, response_current=False):
    assignment = allocation_for(slot)['trials'][trial_index - 1]
    session = {'id': attempt, 'participant_id': 'person-A', 'assignment': assignment,
               'evidence_kind': kind, 'mode': 'text', 'used_modes': ['text'],
               'started_at': f'2026-11-13T12:{minute:02d}:00+00:00'}
    events = [event(0, 'session_started', 0), event(1, 'tool_started', 900, tool='setup'),
              event(2, 'trial_started', 3000), event(3, 'request_accepted', 3500),
              event(4, 'tool_started', 4000, tool='edit_charts'),
              event(5, 'tool_committed', 5000, tool='edit_charts', result={}, actor='user', revision=7)]
    events[2]['at'] = f'2026-11-13T12:{minute:02d}:03+00:00'
    if reason:
        events += [event(6, 'trial_finished', 9000, reason=reason),
                   event(7, 'playback_end', 10000)]
    base = {'technical_completed': correct, 'first_commit_correct': True,
            'all_revision_commits_correct': correct, 'incorrect_commit_count': 0 if correct else 1,
            'commit_assessments': [{'revision': 7, 'server_ms': 5000, 'event_index': 5,
                                    'correct': True, 'full_correct': correct}],
            'checks': [{'name': 'Actual source', 'passed': correct}],
            'task_response_status': 'current' if response_current else 'none', 'task_response_current': response_current}
    return build_trial_report(session, base, events)


def test_sixteen_slots_jointly_balance_family_order_condition_and_variant():
    result = allocation_table(16)
    assert result['balance']['exact_full_balance']
    assert {cell['count'] for cell in result['balance']['cells']} == {1}
    for plan in result['allocations']:
        trials = plan['trials']
        assert {trial['family_id'] for trial in trials} == {'01', '02', '03', '04'}
        assert sum(trial['condition'] == 'direct' for trial in trials) == 2
        assert sum(trial['variant_id'] == 'a' for trial in trials) == 2
        assert len({trial['task_id'] for trial in trials}) == 4
    assert allocation_for(17)['trials'][0]['task_id'] == allocation_for(1)['trials'][0]['task_id']
    assert allocation_for(17)['trials'][0]['trial_id'] != allocation_for(1)['trials'][0]['trial_id']


def test_thirty_slot_plan_reports_partial_balance_without_inventing_participants():
    result = allocation_table()
    assert result['participant_count'] == 30
    assert not result['balance']['exact_full_balance']
    assert result['balance']['condition_counts'] == {'direct': 60, 'bound_revision': 60}
    assert result['balance']['partial_block_slots'] == 14
    assert result['balance']['cell_min'] == 1 and result['balance']['cell_max'] == 2


def test_trial_duration_and_counts_exclude_setup_and_post_finish_review():
    report = trial_report()
    assert report['timing']['elapsed_seconds'] == 6
    assert report['timing']['first_full_correct_seconds'] == 2
    assert report['process']['counts']['tool_started'] == 1
    assert report['process']['counts']['playback_end'] == 0
    assert report['process']['publication']['first_full_correct_revision'] == 7
    assert report['outcome']['submitted_correct']
    assert report['outcome']['business_conclusion_correct'] is None
    assert report['human_review']['repair_turns'] is None


def test_chart_success_without_current_response_is_not_complete_business_delivery():
    missing = trial_report(correct=True)
    current = trial_report(correct=True, response_current=True)
    assert missing['outcome']['technical_completed'] and missing['outcome']['submitted_correct']
    assert missing['outcome']['status'] == 'submitted_incomplete'
    assert not missing['outcome']['response_complete_current']
    assert not missing['outcome']['submitted_deliverables_complete']
    assert current['outcome']['status'] == 'completed'
    assert current['outcome']['submitted_deliverables_complete']
    assert current['outcome']['business_conclusion_correct'] is None
    assert missing['timing']['time_analysis_status'] == 'observed_chart_submission'


@pytest.mark.parametrize('reason,status,censored', [
    ('completed', 'submitted_incomplete', True), ('timeout', 'timeout', True),
    ('abandoned', 'abandoned', True), (None, 'running', True),
])
def test_incomplete_and_interrupted_attempts_remain_distinct(reason, status, censored):
    report = trial_report(correct=False, reason=reason)
    assert report['outcome']['status'] == status
    assert report['outcome']['submitted_correct'] is False
    assert report['timing']['time_censored'] is censored
    assert report['timing']['elapsed_seconds'] == (None if reason is None else 6)
    assert report['process']['publication']['first_commit_correct'] is True
    assert report['process']['publication']['first_full_correct_revision'] is None


def test_latest_failed_attempt_does_not_disappear_behind_earlier_success():
    good = trial_report(attempt='earlier-success', minute=0)
    failed = trial_report(attempt='later-failure', minute=1, correct=False, reason='timeout')
    aggregate = aggregate_reports([good, failed])
    assert aggregate['attempt_count'] == 2 and aggregate['assigned_trial_count'] == 4
    assert aggregate['latest_attempts'][0]['identity']['session_id'] == 'later-failure'
    assert len(aggregate['missing_trials']) == 3
    assert aggregate['participants'][0]['paired']['technical_correct_rate_difference'] is None
    rows = list(csv.DictReader(StringIO(report_csv(aggregate))))
    assert len(rows) == 2
    assert rows[0]['selected_latest'] == 'False' and rows[1]['selected_latest'] == 'True'
    assert rows[1]['status'] == 'timeout' and rows[0]['submitted_correct'] == 'True'
    assert all(row['human_review'] == 'pending' and row['repair_seconds'] == '' for row in rows)


def test_local_authored_records_never_merge_with_participant_evidence():
    reports = [trial_report(trial_index=i, attempt=f'authored-{i}') for i in range(1, 5)]
    reports += [trial_report(trial_index=1, attempt='participant-1', kind='participant', correct=False)]
    aggregate = aggregate_reports(reports)
    assert aggregate['assigned_trial_count'] == 8
    assert len(aggregate['participants']) == 2
    authored = next(row for row in aggregate['participants'] if row['evidence_kind'] == 'local_authored')
    participant = next(row for row in aggregate['participants'] if row['evidence_kind'] == 'participant')
    assert authored['paired']['complete_pair'] and authored['paired']['technical_correct_rate_difference'] == 0
    assert not participant['paired']['complete_pair']
    assert len(aggregate['missing_trials']) == 3


def test_registered_but_unstarted_participant_has_four_missing_trials():
    aggregate = aggregate_reports([], [{'participant_id': 'not-started', 'participant_slot': 3,
                                       'evidence_kind': 'participant'}])
    assert aggregate['attempt_count'] == 0 and aggregate['assigned_trial_count'] == 4
    assert len(aggregate['missing_trials']) == 4
    assert aggregate['participants'][0]['paired']['elapsed_seconds_difference'] is None
