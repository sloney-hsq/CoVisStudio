"""Offline control checks for the authored voice driver; no model connection."""
from scripts.verify_complete_revision_flow import stage_wait_result, stage_request_id, expected_sources


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


def test_fragment_supersession_follows_latest_request_until_terminal():
    events = [event('request_accepted', 'old', index=10),
              event('speech_start', 'new', index=11),
              event('request_outcome', 'old', index=12, status='no_changes')]
    assert stage_request_id(events, 10) == 'new'
    assert stage_wait_result(events, stage_request_id(events, 10)) == 'pending'
    events.extend([event('request_accepted', 'new', index=13),
                   event('request_outcome', 'new', index=14, status='no_changes')])
    assert stage_wait_result(events, stage_request_id(events, 10)) == 'not_committed'


def test_reuse_only_keeps_dates_metrics_and_untargeted_chart():
    initial = {'views': [{'id': v, 'source': {'metric': m, 'region': 'MG',
        'start': '2017-01-01', 'end': '2018-01-01', 'categories': None, 'top_n': 3}}
        for v, m in [('v1', 'orders'), ('v2', 'low_review_rate'), ('v3', 'avg_delivery_days')]]}
    result = expected_sources(initial, ['a', 'b', 'c'], 'reuse')
    assert result['v1'] == initial['views'][0]['source']
    for view in initial['views'][1:]:
        assert result[view['id']] == {**view['source'], 'categories': ['a', 'b', 'c'], 'top_n': None}
    complete = expected_sources(initial, ['a', 'b', 'c'], 'complete')
    assert complete['v2']['categories'] is None and complete['v2']['end'] == '2017-04-01'
    assert complete['v3']['categories'] == ['a', 'b', 'c']
