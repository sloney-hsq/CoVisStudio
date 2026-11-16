"""Offline scoring uses coded intent, never the authored task answer or model text."""
from copy import deepcopy
from pathlib import Path
import pytest

from backend.charts import ChartStore
from backend.data import OlistData
from backend.intent_scoring import (coding_template, lock_intent, score_episode,
                                   outcome_summary, review_understanding, digest,
                                   designate_primary_episode, write_new, attach_formal_scores,
                                   terminal_packet, terminal_coverage, score_terminal,
                                   interpretation_key, lock_understanding)
from backend.study import starter_operations


@pytest.fixture(scope='module')
def data():
    db = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    yield db
    db.close()


def fixture(data):
    store = ChartStore(data)
    for name, args in starter_operations(data):
        store.commit(store.prepare(name, args))
    before = store.snapshot()
    packet = {'packet_id': 'test-packet',
              'boundary': {'onset': {'index': 1}, 'utterance_arrival_end': {'index': 2}},
              'prior_context': [], 'participant_input': [{'index': 2, 'text': 'Use RJ; keep the selected group.'}]}
    coder = coding_template(packet)
    coder['intent']['source_requirement'] = {'mode': 'none', 'candidate_id': None, 'reason': 'Authored fixture requests scope changes without a new historical source.'}
    coder.update(status='completed', reviewer_id='fixture-a')
    coder['intent'].update(status='resolved', target_view_ids=['v2', 'v3'],
                           source_patch={'region': 'RJ'}, retained_fields=['categories', 'start', 'end', 'metric'],
                           reason='Authored local unit fixture, not human review.', evidence_indices=[2])
    other = {**deepcopy(coder), 'reviewer_id': 'fixture-b'}
    adjudication = {'reviewer_id': 'fixture-adjudicator', 'reason': 'Local unit fixture.', 'intent': coder['intent']}
    lock = lock_intent(packet, coder, other, adjudication)
    return store, before, packet, lock


def archive(before, after, events):
    return {'session': {'id': 'offline-fixture'}, 'initial': before, 'final': after,
            'states': {'before': before, 'after': after}, 'events': events}


def test_correct_followup_after_wrong_commit_is_not_first_commit_success(data):
    store, before, packet, lock = fixture(data)
    wrong = store.commit(store.prepare('edit_charts', {'view_ids': ['v2', 'v3'],
                 'patch': {'source': {'region': 'MG'}}}))['state']
    right = store.commit(store.prepare('edit_charts', {'view_ids': ['v2', 'v3'],
                 'patch': {'source': {'region': 'RJ'}}}))['state']
    events = [{'index': 1, 'name': 'speech_start', 'request_id': 'q1'},
              {'index': 2, 'name': 'request_accepted', 'request_id': 'q1'},
              {'index': 3, 'name': 'tool_committed', 'revision': wrong['revision'], 'request_id': 'q1'},
              {'index': 4, 'name': 'request_accepted', 'request_id': 'q2'},
              {'index': 5, 'name': 'tool_committed', 'revision': right['revision'], 'request_id': 'q2'}]
    saved = archive(before, right, events)
    saved['states']['wrong'] = wrong
    result = score_episode(saved, packet, lock, 5, data)
    assert result['first_publication_consistent'] is False
    assert result['final_correct'] is True
    assert result['request_ids'] == ['q1', 'q2']
    assert result['repair_cost'] is None and result['human_listening'] == 'pending'
    assert all(value is None for value in result['understanding'].values())


def test_wrong_cohort_or_untargeted_edit_fails_even_when_numbers_are_correct(data):
    store, before, packet, lock = fixture(data)
    after = store.commit(store.prepare('edit_charts', {'view_ids': ['v1', 'v2', 'v3'],
                 'patch': {'source': {'region': 'RJ', 'categories': None, 'top_n': 3}}}))['state']
    saved = archive(before, after, [{'index': 2, 'name': 'request_accepted'},
                      {'index': 3, 'name': 'tool_committed', 'revision': after['revision']}])
    assert score_episode(saved, packet, lock, 3, data)['final_correct'] is False


def test_unreviewed_unresolved_and_tampered_locks(data):
    _, before, packet, lock = fixture(data)
    saved = archive(before, before, [{'index': 2, 'name': 'request_accepted'}])
    assert score_episode(saved, packet, None, 2, data)['final_correct'] is None
    lock['intent']['status'] = 'unknown'
    with pytest.raises(ValueError, match='original locked'):
        score_episode(saved, packet, lock, 2, data)
    lock['lock_hash'] = digest({k: v for k, v in lock.items() if k != 'lock_hash'})
    assert score_episode(saved, packet, lock, 2, data)['final_correct'] is None
    assert outcome_summary([True, False, None, None]) == {
        'assigned': 4, 'success': 1, 'failure': 1, 'unknown': 2,
        'success_lower': .25, 'success_upper': .75}


def test_no_automatic_or_single_coder_lock(data):
    _, _, packet, lock = fixture(data)
    with pytest.raises(ValueError, match='two independent'):
        lock_intent(packet, lock['coder_a'], lock['coder_a'], lock['adjudication'])
    pending = coding_template(packet)
    with pytest.raises(ValueError, match='completed independent'):
        lock_intent(packet, pending, lock['coder_b'], lock['adjudication'])


def test_missing_playback_and_understanding_never_become_passes(data):
    _, before, _, _ = fixture(data)
    saved = archive(before, before, [])
    with pytest.raises(ValueError, match='actual participant response'):
        review_understanding(saved, {'reviewer_id': 'fixture', 'reason': 'Synthetic test',
             'labels': dict.fromkeys(('object_origin', 'target_views', 'calculation_scope', 'kept_released'), True)})


@pytest.mark.parametrize('mutation,message', [
    ({'retained_fields': ['region']}, 'Retained fields'),
    ({'released_fields': ['categories'], 'retained_fields': []}, 'Released fields'),
    ({'members': {'mode': 'rank', 'top_n': 3}}, 'rank_by'),
    ({'members': {'mode': 'fixed', 'values': 'alpha'}}, 'category identifiers'),
])
def test_coding_must_express_one_consistent_intention(data, mutation, message):
    _, _, packet, locked = fixture(data)
    adjudication = deepcopy(locked['adjudication'])
    adjudication['intent'].update(mutation)
    with pytest.raises(ValueError, match=message):
        lock_intent(packet, locked['coder_a'], locked['coder_b'], adjudication)


def test_primary_must_include_terminal_not_earlier_success(tmp_path):
    folder = tmp_path / 'intent-episodes' / 'early'
    folder.mkdir(parents=True)
    write_new(folder / 'locked.json', {'status': 'locked'})
    write_new(folder / 'private.json', {'end_event_index': 3})
    write_new(tmp_path / 'session.json', {'events': [{'index': 5, 'name': 'trial_finished'}]})
    with pytest.raises(ValueError, match='final trial state'):
        designate_primary_episode(tmp_path, 'early', 'fixture', 'A success occurred earlier.')
    assert not (tmp_path / 'intent-episodes' / 'primary.json').exists()


def test_known_incorrect_understanding_is_not_replaced_by_unknown(tmp_path):
    folder = tmp_path / 'intent-episodes' / 'episode'
    folder.mkdir(parents=True)
    write_new(folder / 'packet.json', {'boundary': {'onset': {'index': 1}, 'utterance_arrival_end': {'index': 2}}})
    write_new(folder / 'private.json', {'end_event_index': 5})
    write_new(folder / 'score.json', {'packet_id': 'episode', 'intent_status': 'resolved', 'final_correct': True})
    write_new(folder / 'understanding.json', {'labels': {'object_origin': False, 'target_views': None,
                                                        'calculation_scope': True, 'kept_released': True}})
    write_new(folder.parent / 'primary.json', {'packet_id': 'episode'})
    report = {'assigned_rows': [{'primary_session_id': 's', 'condition': 'direct',
                                 'revision_correct': None, 'understanding_correct': None}], 'attempt_rows': []}
    result = attach_formal_scores(report, {'s': {'directory': tmp_path}})
    assert result['assigned_rows'][0]['understanding_correct'] is False
    assert result['conditions'][0]['understanding']['success_upper'] == 0


def test_superseded_goal_is_not_terminal_requirement_and_prior_commit_survives(data):
    store, before, old_packet, old_lock = fixture(data)
    first = store.commit(store.prepare('edit_charts', {'view_ids': ['v2', 'v3'],
                 'patch': {'source': {'region': 'RJ'}}}))['state']
    packet = deepcopy(old_packet)
    packet.update(packet_id='latest-goal')
    packet['boundary'] = {'onset': {'index': 4}, 'utterance_arrival_end': {'index': 5}}
    packet['participant_input'] = [{'index': 5, 'text': 'Instead use MG, release the fixed cohort and rank the top three by revenue.'}]
    coder = coding_template(packet)
    coder['intent']['source_requirement'] = {'mode': 'none', 'candidate_id': None, 'reason': 'Authored fixture requests scope changes without a new historical source.'}
    coder.update(status='completed', reviewer_id='a')
    coder['intent'].update(status='resolved', target_view_ids=['v2', 'v3'],
        source_patch={'region': 'MG'}, members={'mode': 'rank', 'top_n': 3, 'rank_by': 'revenue'},
        retained_fields=['metric', 'start', 'end', 'status'], released_fields=['categories'],
        reason='Authored goal change, not an error correction.', evidence_indices=[5])
    lock = lock_intent(packet, coder, {**deepcopy(coder), 'reviewer_id': 'b'},
        {'reviewer_id': 'c', 'reason': 'Authored test.', 'intent': coder['intent']})
    final = store.commit(store.prepare('edit_charts', {'view_ids': ['v2', 'v3'],
        'patch': {'source': {'region': 'MG', 'categories': None, 'top_n': 3, 'rank_by': 'revenue'}}}))['state']
    events = [{'index': 1, 'name': 'speech_start'}, {'index': 2, 'name': 'request_accepted'},
        {'index': 3, 'name': 'tool_committed', 'revision': first['revision']},
        {'index': 4, 'name': 'speech_start'}, {'index': 5, 'name': 'request_accepted'},
        {'index': 6, 'name': 'tool_committed', 'revision': final['revision']},
        {'index': 7, 'name': 'trial_finished'}]
    saved = archive(before, final, events)
    saved['states']['first'] = first
    result = score_episode(saved, packet, lock, 7, data)
    assert result['base_revision'] == first['revision']
    assert result['final_correct'] is True
    assert score_episode(saved, old_packet, old_lock, 3, data)['final_correct'] is True
    assert score_episode(saved, old_packet, old_lock, 7, data)['final_correct'] is False
    assert result['repair_cost'] is None


def test_primary_cannot_select_superseded_intent_even_if_later_intent_unknown(tmp_path):
    for name, onset in [('old', 1), ('latest', 4)]:
        folder = tmp_path / 'intent-episodes' / name
        folder.mkdir(parents=True)
        write_new(folder / 'packet.json', {'boundary': {'onset': {'index': onset}}})
        write_new(folder / 'locked.json', {'status': 'locked', 'intent': {'status': 'unknown'}})
        write_new(folder / 'private.json', {'end_event_index': 7})
    write_new(tmp_path / 'session.json', {'events': [{'index': 7, 'name': 'trial_finished'}]})
    with pytest.raises(ValueError, match='latest independently annotated intent'):
        designate_primary_episode(tmp_path, 'old', 'reviewer', 'Earlier successful goal.')
    assert designate_primary_episode(tmp_path, 'latest', 'reviewer', 'Latest intent remains unknown.')['packet_id'] == 'latest'


def test_later_annotation_invalidates_earlier_primary_attachment(tmp_path):
    for name, onset in [('old', 1), ('new', 4)]:
        folder = tmp_path / 'intent-episodes' / name
        folder.mkdir(parents=True)
        write_new(folder / 'packet.json', {'boundary': {'onset': {'index': onset}, 'utterance_arrival_end': {'index': onset + 1}}})
        write_new(folder / 'private.json', {'end_event_index': 7})
    write_new(tmp_path / 'intent-episodes' / 'old' / 'score.json', {'final_correct': True, 'intent_status': 'resolved'})
    write_new(tmp_path / 'intent-episodes' / 'primary.json', {'packet_id': 'old'})
    report = {'assigned_rows': [{'primary_session_id': 's', 'condition': 'direct',
        'revision_correct': None, 'understanding_correct': None}], 'attempt_rows': []}
    result = attach_formal_scores(report, {'s': {'directory': tmp_path}})
    assert result['assigned_rows'][0]['intent_status'] == 'superseded_endpoint'
    assert result['conditions'][0]['revision']['unknown'] == 1


def test_latest_cumulative_intent_keeps_other_view_obligation(data):
    store, before, packet, old_lock = fixture(data)
    coder = deepcopy(old_lock['coder_a'])
    coder['intent'].update(target_view_ids=['v2', 'v3'], source_patch={'region': 'MG'},
        members={'mode': 'rank', 'top_n': 3, 'rank_by': 'revenue'},
        retained_fields=['metric', 'start', 'end'], released_fields=['categories'],
        view_overrides={'v3': {'source_patch': {'region': 'RJ'},
            'members': {'mode': 'keep_current'}, 'retained_fields': ['categories', 'metric'],
            'released_fields': []}})
    lock = lock_intent(packet, coder, {**deepcopy(coder), 'reviewer_id': 'b'},
        {'reviewer_id': 'c', 'reason': 'Latest goal changes v2 only; prior unfulfilled v3 goal stays active.',
         'intent': coder['intent']})
    only_latest = store.commit(store.prepare('edit_charts', {'view_ids': ['v2'],
        'patch': {'source': {'region': 'MG', 'categories': None, 'top_n': 3, 'rank_by': 'revenue'}}}))['state']
    final = store.commit(store.prepare('edit_charts', {'view_ids': ['v3'],
        'patch': {'source': {'region': 'RJ'}}}))['state']
    events = [{'index': 2, 'name': 'request_accepted'},
        {'index': 3, 'name': 'tool_committed', 'revision': only_latest['revision']},
        {'index': 4, 'name': 'tool_committed', 'revision': final['revision']}]
    saved = archive(before, final, events)
    saved['states']['only-latest'] = only_latest
    result = score_episode(saved, packet, lock, 4, data)
    assert result['first_publication_consistent'] is False
    assert result['final_correct'] is True
    assert final['views'][2]['source']['categories'] == before['views'][2]['source']['categories']
    assert final['views'][1]['source']['categories'] is None


def test_wrong_execution_and_correct_interpretation_are_separate(data):
    store, before, packet, lock = fixture(data)
    wrong = store.commit(store.prepare('edit_charts', {'view_ids': ['v2'],
        'patch': {'source': {'region': 'MG'}}}))['state']
    saved = archive(before, wrong, [{'index': 1, 'name': 'trial_started'},
        {'index': 2, 'name': 'tool_committed', 'revision': wrong['revision']}])
    score = score_terminal(saved, lock['intent'], data)
    assert score['intent_status'] == 'resolved'
    assert score['correct'] is False  # revision incorrect: v2 wrong region, v3 unfulfilled
    key = interpretation_key(saved)
    assert key['key']['target_views'] == ['v2']  # ground truth from actual state, not intent
    assert key['key']['calculation_scope']['v2']['region'] == 'MG'


def test_terminal_packet_coverage_and_scoring(data):
    store, before, packet, lock = fixture(data)
    final = store.commit(store.prepare('edit_charts', {'view_ids': ['v2'],
        'patch': {'source': {'region': 'RJ'}}}))['state']
    events = [{'index': 0, 'name': 'trial_started'},
        {'index': 1, 'name': 'request_accepted', 'text': 'Use RJ on the service charts.'},
        {'index': 2, 'name': 'tool_committed', 'revision': final['revision']},
        {'index': 3, 'name': 'request_accepted', 'text': 'Now also Q1.'}]
    saved = archive(before, final, events)
    packet = terminal_packet(saved, [lock])
    assert [segment['index'] for segment in packet['input_segments']] == [1, 3]
    assert packet['trial_start']['revision'] == before['revision']
    partial = terminal_coverage([lock], packet, {1: 'revise'})
    assert partial['covered'] is False and partial['uncovered_segments'] == [3]
    full = terminal_coverage([lock], packet, {1: 'revise', 3: 'revise'})
    assert full['covered'] is True and full['carry_forward_episodes'] == ['test-packet']


def test_lock_understanding_enforces_two_reviewers_and_key_hash(data):
    store, before, packet, lock = fixture(data)
    final = store.commit(store.prepare('edit_charts', {'view_ids': ['v2'],
        'patch': {'source': {'region': 'RJ'}}}))['state']
    saved = archive(before, final, [])
    key = interpretation_key(saved)
    response = {'revision': final['revision']}
    review = {'reviewer_id': 'a', 'key_hash': key['key_hash'], 'key_fields': ['target_views'],
              'response_span': [0, 1]}
    with pytest.raises(ValueError, match='two distinct'):
        lock_understanding(key, response, review, {**review}, {'reviewer_id': 'c', 'reason': 'x'})
    with pytest.raises(ValueError, match='matching interpretation key'):
        lock_understanding(key, response, review, {**review, 'reviewer_id': 'b', 'key_hash': 'bad'},
                           {'reviewer_id': 'c', 'reason': 'x'})
    with pytest.raises(ValueError, match='final chart revision'):
        lock_understanding(key, {'revision': before['revision']}, review,
                           {**review, 'reviewer_id': 'b'}, {'reviewer_id': 'c', 'reason': 'x'})
    locked = lock_understanding(key, response, review, {**review, 'reviewer_id': 'b'},
                                {'reviewer_id': 'c', 'reason': 'x', 'labels': {'target_views': True}})
    assert locked['status'] == 'locked' and locked['labels']['target_views'] is True
