"""Archived evidence stays immutable and human coding stays explicitly provisional."""
from copy import deepcopy
import json
import wave

import pytest

from backend.review_packets import (attach_review_drafts, build_review_packet, load_review_drafts,
                                    read_trial_archives, save_review_draft)


@pytest.fixture
def evidence(tmp_path):
    events = [
        {'index': 0, 'name': 'node_created', 'server_ms': 0, 'at': '2026-11-13T01:00:00+00:00'},
        {'index': 1, 'name': 'trial_started', 'server_ms': 10, 'at': '2026-11-13T01:00:01+00:00'},
        {'index': 2, 'name': 'user_transcript', 'server_ms': 20, 'at': '2026-11-13T01:00:02+00:00',
         'event': {'type': 'user_transcript', 'text': 'Keep the original categories.', 'item_id': 'input-1'}},
        {'index': 3, 'name': 'audio_sent', 'server_ms': 30, 'file': 'input-user.pcm', 'offset_bytes': 0, 'bytes': 320},
        {'index': 4, 'name': 'assistant_done', 'server_ms': 40,
         'event': {'type': 'assistant_done', 'text': 'The historical categories are retained.', 'response_id': 'r1'}},
        {'index': 5, 'name': 'image_captured', 'server_ms': 50, 'file': 'image-00005-r7.jpg', 'reference': {'revision': 7}},
        {'index': 6, 'name': 'chart_rendered', 'server_ms': 60, 'client_ms': 501, 'details': {'revision': 7}},
        {'index': 7, 'name': 'trial_finished', 'server_ms': 70, 'reason': 'completed'},
        {'index': 8, 'name': 'history_open', 'server_ms': 80, 'client_ms': 601, 'details': {'revision': 3}},
    ]
    archive = {'version': 4,
        'session': {'id': 'review-fixture', 'task_id': 'exp_01_a', 'evidence_kind': 'local_authored',
                    'assignment': {'task_id': 'exp_01_a'}, 'trial_status': 'finished'},
        'task': {'id': 'exp_01_a', 'title': 'The exact archived brief', 'business_goal': 'Compare the historical cohort.'},
        'initial': {'revision': 6, 'views': []}, 'final': {'revision': 7, 'views': []},
        'events': events, 'nodes': [{'id': 'n1', 'revision': 7, 'event_index': 6}],
        'states': {'n1': {'revision': 7, 'views': []}},
        'task_response': {'conclusion': 'Investigate service.', 'revision': 7},
        'report': {'trial_report': {'outcome': {'technical_completed': True, 'business_conclusion_correct': None},
                                   'human_review': {'status': 'pending', 'repair_turns': None}}}}
    (tmp_path / 'session.json').write_text(json.dumps(archive), encoding='utf-8')
    (tmp_path / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
    (tmp_path / 'image-00005-r7.jpg').write_bytes(b'fixture-image')
    with wave.open(str(tmp_path / 'input-user.wav'), 'wb') as audio:
        audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        audio.writeframes(bytes(320))
    return archive, tmp_path


def draft(**changes):
    return {'reviewer_id': 'R01', 'notes': 'No final human judgement; local interface check.',
            'interpretation': 'pending', 'spoken_consistency': 'pending',
            'segments': [{'start_event_index': 2, 'end_event_index': 6, 'kind': 'unclear',
                          'reason': 'Need the full interaction to establish why this changed.'}], **changes}


def test_packet_preserves_archived_brief_response_scores_and_clock_domains(evidence):
    archive, directory = evidence
    before = deepcopy(archive)
    packet = build_review_packet(archive, directory)
    assert packet['task'] == archive['task'] and packet['task_source'] == 'archive'
    assert packet['task_response'] == archive['task_response']
    assert packet['events'] == archive['events']
    assert packet['node_states'] == archive['states']
    assert packet['measured_event_indices'] == list(range(1, 8))
    assert packet['events'][6]['server_ms'] == 60 and packet['events'][6]['client_ms'] == 501
    assert packet['review_status'] == 'pending' and packet['review_drafts'] == []
    assert packet['trial_report'] == archive['report']['trial_report']
    packet['events'][2]['event']['text'] = 'Altered packet copy'
    packet['node_states']['n1']['revision'] = 999
    assert archive == before


def test_media_and_transcripts_link_actual_recorded_events(evidence):
    archive, directory = evidence
    packet = build_review_packet(archive, directory)
    audio = next(item for item in packet['media'] if item['kind'] == 'audio')
    assert audio == {'name': 'input-user.wav', 'url': '/api/experiment/attempts/review-fixture/media/input-user.wav',
                     'kind': 'audio', 'event_indices': [3], 'sample_rate': 16000, 'duration_seconds': .01}
    assert next(item for item in packet['media'] if item['kind'] == 'image')['event_indices'] == [5]
    assert [item['role'] for item in packet['transcripts']] == ['user', 'assistant']
    assert [item['text'] for item in packet['transcripts']] == [
        'Keep the original categories.', 'The historical categories are retained.']
    assert packet['transcripts'][0]['item_id'] == 'input-1'
    assert packet['transcripts'][1]['response_id'] == 'r1'


def test_existing_frozen_material_is_labeled_as_lookup(evidence):
    archive, directory = evidence
    del archive['task']
    packet = build_review_packet(archive, directory)
    assert packet['task']['id'] == 'exp_01_a'
    assert packet['task_source'] == 'materials_lookup'
    assert 'targets' not in packet['task'] and 'resolution' not in packet['task']


def test_appended_drafts_do_not_rewrite_evidence_or_promote_review(evidence):
    archive, directory = evidence
    original = {name: (directory / name).read_bytes() for name in ('session.json', 'events.jsonl')}
    first = save_review_draft(archive, directory, draft())
    first_bytes = (directory / 'review-drafts.jsonl').read_bytes()
    second = save_review_draft(archive, directory, draft(reviewer_id='R02', interpretation='supported'))
    assert (directory / 'review-drafts.jsonl').read_bytes().startswith(first_bytes)
    assert first['id'] != second['id'] and first['status'] == second['status'] == 'draft'
    assert load_review_drafts(directory) == [first, second]
    assert all((directory / name).read_bytes() == value for name, value in original.items())
    packet = build_review_packet(archive, directory)
    assert packet['review_status'] == 'pending'
    assert packet['trial_report']['human_review'] == {'status': 'pending', 'repair_turns': None}
    assert packet['trial_report']['outcome']['business_conclusion_correct'] is None


@pytest.mark.parametrize('start,end', [(0, 2), (2, 8), (6, 2), (2, 99)])
def test_segment_requires_ordered_actual_events_inside_task(evidence, start, end):
    archive, directory = evidence
    body = draft(segments=[{'start_event_index': start, 'end_event_index': end,
                            'kind': 'repair', 'reason': 'Recorded correction.'}])
    with pytest.raises(ValueError, match='measured task interval'):
        save_review_draft(archive, directory, body)
    assert not (directory / 'review-drafts.jsonl').exists()


@pytest.mark.parametrize('changes,message', [
    ({'reviewer_id': ' '}, 'reviewer label'),
    ({'interpretation': 'approved'}, 'listed review labels'),
    ({'spoken_consistency': 'pass'}, 'listed review labels'),
    ({'interpretation': 'supported', 'notes': ' '}, 'review notes'),
    ({'notes': '', 'segments': []}, 'review notes or'),
    ({'segments': [{'start_event_index': 2, 'end_event_index': 6, 'kind': 'repair', 'reason': ' '}]}, 'evidence'),
    ({'segments': [{'start_event_index': 2, 'end_event_index': 6, 'kind': 'automatic_error', 'reason': 'Unknown category.'}]}, 'repair, exploration'),
])
def test_draft_requires_attribution_and_reasoned_declared_labels(evidence, changes, message):
    archive, directory = evidence
    with pytest.raises(ValueError, match=message):
        save_review_draft(archive, directory, draft(**changes))


def test_unstarted_attempt_can_have_notes_but_no_measured_segment(evidence):
    archive, directory = evidence
    archive['events'] = [archive['events'][0]]
    assert build_review_packet(archive, directory)['measured_event_indices'] == []
    saved = save_review_draft(archive, directory, draft(segments=[], notes='Prepared, then abandoned before Begin.'))
    assert saved['status'] == 'draft' and saved['segments'] == []
    with pytest.raises(ValueError, match='measured task interval'):
        save_review_draft(archive, directory, draft())


def test_archive_registry_retains_all_attempts_and_prefers_current_copy(evidence):
    archive, directory = evidence
    older, current = directory / 'older', directory / 'current'
    for root in (older, current):
        (root / 'review-fixture').mkdir(parents=True)
        (root / 'review-fixture' / 'session.json').write_text(json.dumps(archive), encoding='utf-8')
    old_attempt = deepcopy(archive)
    old_attempt['session']['id'] = 'earlier-attempt'
    (older / 'earlier-attempt').mkdir()
    (older / 'earlier-attempt' / 'session.json').write_text(json.dumps(old_attempt), encoding='utf-8')
    ad_hoc = deepcopy(archive)
    ad_hoc['session'].pop('assignment')
    (current / 'adhoc').mkdir()
    (current / 'adhoc' / 'session.json').write_text(json.dumps(ad_hoc), encoding='utf-8')
    ready = deepcopy(archive)
    ready['session']['id'] = 'unscored'
    ready['report'] = None
    (current / 'unscored').mkdir()
    (current / 'unscored' / 'session.json').write_text(json.dumps(ready), encoding='utf-8')
    records = read_trial_archives([older, current])
    assert set(records) == {'review-fixture', 'earlier-attempt', 'unscored'}
    assert records['unscored']['archive']['report'] is None
    assert records['review-fixture']['directory'] == current / 'review-fixture'
    assert records['earlier-attempt']['directory'] == older / 'earlier-attempt'
    assert records['review-fixture']['archive'] == archive


def test_draft_export_keeps_manual_scores_pending_and_all_reviewers(evidence):
    archive, directory = evidence
    first = save_review_draft(archive, directory, draft())
    second = save_review_draft(archive, directory, draft(reviewer_id='R02', interpretation='supported'))
    aggregate = {'human_review': 'pending', 'attempt_rows': [
        {'session_id': 'review-fixture', 'repair_turns': None, 'repair_seconds': None, 'human_review': 'pending'}],
        'all_attempts': [deepcopy(archive['report']['trial_report'])]}
    result = attach_review_drafts(aggregate, {'review-fixture': {'archive': archive, 'directory': directory}})
    assert result is aggregate
    assert result['review_drafts'] == [first, second]
    assert result['attempt_rows'][0] == {'session_id': 'review-fixture', 'repair_turns': None,
        'repair_seconds': None, 'human_review': 'pending', 'review_draft_count': 2, 'last_draft_at': second['at']}
    assert result['all_attempts'] == [archive['report']['trial_report']]
    assert result['human_review'] == 'pending'
