from backend.delivery import summarize_delivery
from scripts.audit_delivery import audit_session
import json


def event(name, **fields):
    return {'name': name, 'request_id': 'q1', 'response_id': 'r1', **fields}


def test_provider_completed_and_received_are_not_playback():
    report = summarize_delivery([event('request_accepted', text='Change region'),
        event('assistant_done', event={'text': 'Updated'}),
        event('audio_received', sample_start=0, sample_end=2400),
        event('response_end', event={'status': 'completed'})])
    response = report['responses'][0]
    assert response['provider_status'] == 'completed'
    assert response['generated_text_status'] == 'complete_received'
    assert response['playback_status'] == 'unknown'
    assert response['human_semantic_consistency'] == 'pending'
    assert response['human_listening'] == 'pending'
    assert response['partial_text_word_alignment'] == 'unknown'


def test_playback_complete_and_interrupted_are_independent_from_commit():
    source = {'region': 'MG', 'dimension': 'category', 'metric': 'orders'}
    report = summarize_delivery([event('tool_committed', revision=7,
        result={'changed_view_ids': ['v2'], 'views': [{'id': 'v2', 'source': source}]}),
        event('stop_speaking'), event('playback_end', details={'interrupted': True,
        'timing_basis': 'browser_audio_clock', 'received_samples': 96000, 'played_samples': 1816, 'queue_empty': True}),
        event('playback_end', response_id='r2', details={'timing_basis': 'audio_worklet_source_cursor',
            'generation_epoch': 2, 'received_samples': 14400, 'played_samples': 14400, 'queue_empty': True})])
    stopped, complete = report['responses']
    assert stopped['playback_status'] == 'interrupted'
    assert stopped['playback']['measurement'] == 'estimate'
    assert complete['playback_status'] == 'complete'
    assert complete['playback']['generation_epoch'] == 2
    assert report['requests'][0]['commits'][0]['views'][0]['source'] == source
    assert report['requests'][0]['commits'][0]['status'] == 'committed'
    assert report['control_observations'][0]['name'] == 'stop_speaking'


def test_render_surface_identity_and_open_exposure():
    identity = {'revision': 7, 'view_id': 'v2', 'surface_id': 'expanded', 'render_generation': 3}
    rendered = event('chart_rendered', details={**identity, 'render_completed_client_ms': 10})
    report = summarize_delivery([rendered, rendered, event('chart_visible', details={**identity, 'display_id': 'd'})])
    surface = report['chart_surfaces'][0]
    assert len(surface['renders']) == 1
    assert surface['exposures'][0]['end'] is None


def test_offline_archive_audit_retains_sources_and_hashes(tmp_path):
    (tmp_path / 'events.jsonl').write_text(json.dumps(event('request_accepted', text='Check values')) + '\n')
    state = {'revision': 1, 'views': [{'id': 'v1', 'chart_type': 'line', 'source': {'dimension': 'month'}}]}
    (tmp_path / 'state-r1.json').write_text(json.dumps(state))
    result = audit_session(tmp_path)
    assert result['numeric_audit'][0]['status'] == 'not_checked'
    assert result['numeric_audit'][0]['source']['dimension'] == 'month'
    assert len(result['input_fingerprints']['state-r1.json']) == 64


def test_later_normalized_response_fills_unknown_origin():
    report = summarize_delivery([
        {'name': 'provider_event', 'response_id': 'r1', 'event': {'type': 'response.created'}},
        event('response_start', epoch=4),
        event('response_end', epoch=4, event={'status': 'completed'})])
    assert report['responses'][0]['request_id'] == 'q1'
    assert report['responses'][0]['epoch'] == 4
    assert report['requests'][0]['response_ids'] == ['r1']


def test_legacy_acceptance_without_request_identity_is_retained():
    report = summarize_delivery([{'name': 'request_accepted', 'text': 'Show orders', 'epoch': 2}])
    assert report['requests'][0]['request_id'] is None
    assert report['requests'][0]['accepted']['text'] == 'Show orders'
