"""Offline control checks for the authored voice driver; no model connection."""
from scripts.verify_complete_revision_flow import stage_wait_result


def event(name, request_id='r1', **fields):
    return dict(name=name, request_id=request_id, **fields)


def test_commit_finishes_edit_wait():
    assert stage_wait_result([event('tool_committed')], 'r1') == 'committed'


def test_pending_keeps_waiting():
    assert stage_wait_result([event('assistant_done')], 'r1') == 'pending'


def test_no_changes_stops_edit_wait():
    assert stage_wait_result([event('request_outcome', status='no_changes')], 'r1') == 'not_committed'


def test_wrong_request_outcome_does_not_stop():
    assert stage_wait_result([event('request_outcome', 'r2', status='no_changes')], 'r1') == 'pending'


def test_initial_explanation_no_changes_is_expected():
    assert stage_wait_result([event('request_outcome', status='no_changes')], 'r1', editing=False) == 'pending'


def test_failure_and_confirmation_are_uncommitted():
    for status in ('failed', 'awaiting_confirmation'):
        assert stage_wait_result([event('request_outcome', status=status)], 'r1') == 'not_committed'
