"""Offline reference_context reconstructs browser-visible and audible state. No API."""
from backend.delivery import reference_context


def test_commit_before_reference_render_after():
    events = [
        {'index': 0, 'name': 'chart_rendered', 'server_ms': 5000, 'revision': 1},
        {'index': 1, 'name': 'tool_committed', 'server_ms': 10000, 'revision': 2},
        {'index': 2, 'name': 'chart_rendered', 'server_ms': 11300, 'revision': 2},
    ]
    context = reference_context(events, {1: {}, 2: {}},
                                {'start_ms': 10500, 'end_ms': 11100, 'basis': 'sample_locked'})
    assert context['visible_chart_versions']['at_start'] == 1
    assert context['visible_chart_versions']['at_end'] == 1
    assert context['committed_not_yet_rendered'] == [2]
    assert context['timing_precision'] == 'sample_locked'
    assert context['ordering_ambiguities'] is False


def test_full_audio_received_prefix_played():
    events = [
        {'index': 0, 'name': 'playback_start', 'server_ms': 0, 'received_samples': 144000,
         'played_samples': 0, 'sample_start': 0, 'sample_end': 144000},
        {'index': 1, 'name': 'playback_stopped', 'server_ms': 2300, 'received_samples': 144000,
         'played_samples': 55200, 'sample_start': 0, 'sample_end': 144000},
    ]
    context = reference_context(events, {}, {'start_ms': 2000, 'end_ms': 3000, 'basis': 'sample_locked'})
    prefix = context['played_audio_prefix']
    assert prefix and prefix[-1]['played_samples'] == 55200
    unplayed = context['received_unplayed']
    assert unplayed and unplayed[-1]['received_samples'] == 144000
    assert unplayed[-1]['received_samples'] > unplayed[-1]['played_samples']


def test_selection_change_between_vad_fragments():
    events = [
        {'index': 0, 'name': 'speech_start', 'server_ms': 5000, 'event': {'continuation': False}},
        {'index': 1, 'name': 'selection', 'server_ms': 5400, 'reference': {'revision': 2, 'view_ids': ['v1']}},
        {'index': 2, 'name': 'speech_start', 'server_ms': 5600, 'event': {'continuation': True}},
    ]
    context = reference_context(events, {}, {'start_ms': 5000, 'end_ms': 6000, 'basis': 'sample_locked'})
    assert context['online_binding']['index'] == 0
    assert len(context['active_ui_selection_at_anchor']) == 1
    assert context['active_ui_selection_at_anchor'][0]['server_ms'] == 5400


def test_timing_uncertainty_unknown_ordering():
    events = [
        {'index': 0, 'name': 'chart_rendered', 'server_ms': 8200, 'revision': 2, 'uncertainty_ms': 600},
    ]
    context = reference_context(events, {}, {'start_ms': 8000, 'end_ms': 8500,
                                             'basis': 'sample_locked', 'uncertainty_ms': 600})
    assert context['timing_precision'] == 'unresolved'
    assert context['ordering_ambiguities'] is True


def test_unknown_anchor_interval_is_unresolved():
    context = reference_context([], {}, 'unknown')
    assert context['timing_precision'] == 'unresolved'
    assert context['ordering_ambiguities'] is True
