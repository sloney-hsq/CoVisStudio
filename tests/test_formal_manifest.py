"""Amendment A1 analysis plan and first-attempt primary accounting. No API."""
from backend.experiment import formal_manifest, formal_primary_attempts, formal_allocation_for
from backend.formal_tasks import FORMAL_PROTOCOL
from backend.intent_scoring import paired_bounds, participant_bootstrap


def test_paired_bounds_treat_unknown_as_both_extremes():
    participants = [
        {'direct': True, 'bound_revision': True},
        {'direct': False, 'bound_revision': True},
        {'direct': None, 'bound_revision': True},
        {'direct': True, 'bound_revision': None},
    ]
    bounds = paired_bounds(participants)
    assert bounds['participants'] == 4
    # Lower: unknown-as-failure for B2, unknown-as-success for B0; upper reversed.
    assert bounds['lower_bound'] <= bounds['upper_bound']
    # All-known case is exact.
    assert paired_bounds([{'direct': True, 'bound_revision': True},
                          {'direct': False, 'bound_revision': True}])['lower_bound'] == 0.5


def test_participant_bootstrap_is_deterministic():
    participants = [{'direct': True, 'bound_revision': True},
                    {'direct': False, 'bound_revision': True},
                    {'direct': None, 'bound_revision': False}]
    first = participant_bootstrap(participants, seed=7)
    second = participant_bootstrap(participants, seed=7)
    assert first == second
    assert first['ci_lower'] <= first['ci_upper']


def test_manifest_declares_single_primary_outcome():
    manifest = formal_manifest()
    assert manifest['protocol'] == 'covis-formal-study-0.1'
    plan = manifest['analysis_plan']
    assert plan['primary_outcomes'] == ['terminal_intent_consistency']
    assert 'interface_assisted_interpretation' in plan['secondary_outcomes']
    assert 'repair_funnel' in plan['secondary_outcomes']
    assert 'first_publication_consistent' in plan['descriptive_only']
    assert 'window_expiry' in plan['descriptive_only']
    assert 'no Holm adjustment' in plan['multiple_testing']
    assert 'bound_revision minus direct' in plan['estimand']


def _archive(session_id, *, minute=0, begin=True, reason=None):
    assignment = formal_allocation_for(1)['trials'][0]
    at = f'2026-11-13T12:{minute:02d}:00+00:00'
    events = [{'name': 'trial_started', 'index': 1, 'at': at, 'server_ms': minute * 60000}] if begin else []
    if reason:
        events.append({'name': 'trial_finished', 'index': 2, 'at': at,
                       'server_ms': minute * 60000 + 10000, 'reason': reason})
    return {'session': {'id': session_id, 'participant_id': 'P01', 'started_at': at,
                        'assignment': assignment, 'condition': assignment['condition'],
                        'mode': 'live_voice', 'evidence_kind': 'participant'},
            'events': events, 'report': None}


def test_repeat_does_not_replace_failed_first_attempt():
    roster = [{'participant_id': 'P01', 'participant_slot': 1}]
    failed = _archive('first-failed', minute=0, reason='timeout')
    repeat = _archive('repeat-success', minute=1, reason='completed')
    repeat['session']['repeat_reason'] = 'Participant requested an additional attempt.'
    result = formal_primary_attempts([repeat, failed], roster)
    primary = result['primary_attempts'][0]
    assert primary['session_id'] == 'first-failed'
    assert primary['status'] == 'timeout'
    assert result['assigned_rows'][0]['repeat_session_ids'] == ['repeat-success']
    assert result['protocol'] == FORMAL_PROTOCOL
