"""Offline, independently coded revision episodes. Never used in model context.

Coders see the pre-outcome packet. An adjudicator locks their interpretation
before this module reads publications. Unreviewed and unresolved intent stays
unknown; SQL verifies data, not the participant's intention.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .oracle import category_rows, numeric_rows_equal

SCHEMA = 'covis-intent-episode-1'
SOURCE_FIELDS = {'metric', 'dimension', 'region', 'start', 'end', 'status',
                 'categories', 'top_n', 'rank_by'}
UNDERSTANDING_FIELDS = ('object_origin', 'target_views', 'calculation_scope', 'kept_released')
REFERENCE_INTERVAL_FIELDS = {'start_ms', 'end_ms', 'basis', 'uncertainty_ms', 'note'}
REFERENCE_BASES = ('sample_locked', 'coarse')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def write_new(path, content):
    """Review locks and results are new artifacts, never replacements of evidence."""
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(content, stream, indent=2, ensure_ascii=False)


def coding_template(packet):
    return {'schema': SCHEMA, 'packet_id': packet['packet_id'], 'reviewer_id': '',
            'status': 'pending', 'kind': packet.get('kind', 'episode'),
            'reference_interval': 'unknown', 'intent': {
                'status': 'unknown', 'disposition': 'revise', 'target_view_ids': [],
                'source_patch': {}, 'members': {'mode': 'keep_current'},
                'source_requirement': {'mode': 'none', 'candidate_id': None, 'reason': ''},
                'retained_fields': [], 'released_fields': [], 'view_overrides': {},
                'reason': '', 'evidence_indices': []},
            'speech_verification': 'pending'}


def packet_event_indices(packet):
    """Event indices a coder may cite, including terminal carry-forward obligations."""
    if packet.get('kind') == 'terminal':
        indices = {segment['index'] for segment in packet['input_segments']}
        for lock in packet.get('episode_locks', []):
            indices.update(lock['intent']['evidence_indices'])
    else:
        indices = {event['index'] for event in packet['prior_context'] + packet['participant_input']}
    indices.add(packet['boundary']['onset']['index'])
    return indices


def validate_reference_interval(value):
    """A spoken reference is either unknown or a bounded sample-clock interval."""
    if value == 'unknown':
        return value
    if not isinstance(value, dict) or set(value) != REFERENCE_INTERVAL_FIELDS:
        raise ValueError('Reference interval is unknown or has start_ms, end_ms, basis, uncertainty_ms and note.')
    if type(value['start_ms']) is not int or type(value['end_ms']) is not int:
        raise ValueError('Reference interval bounds are integer milliseconds.')
    if value['start_ms'] < 0 or value['start_ms'] > value['end_ms']:
        raise ValueError('Reference interval bounds are nonnegative and ordered.')
    if type(value['uncertainty_ms']) is not int or value['uncertainty_ms'] < 0:
        raise ValueError('Reference interval uncertainty is nonnegative integer milliseconds.')
    if value['basis'] not in REFERENCE_BASES:
        raise ValueError('Reference interval basis must be sample_locked or coarse.')
    if not isinstance(value['note'], str):
        raise ValueError('Reference interval note is text.')
    return value


def lock_intent(packet, coder_a, coder_b, adjudication, level=None):
    """Validate an explicit two-coder handoff; never manufacture a human label."""
    if level is None:
        level = 'terminal' if packet.get('kind') == 'terminal' else 'episode'
    for coder in (coder_a, coder_b):
        if coder['packet_id'] != packet['packet_id'] or coder['status'] != 'completed':
            raise ValueError('Both completed independent codings must identify this packet.')
        if not coder['reviewer_id'].strip():
            raise ValueError('Identify each independent coder.')
    if coder_a['reviewer_id'] == coder_b['reviewer_id']:
        raise ValueError('Use two independent coder identifiers.')
    if not adjudication['reviewer_id'].strip() or not adjudication['reason'].strip():
        raise ValueError('Record who resolved the coding and why.')
    intent = deepcopy(adjudication['intent'])
    reference_interval = validate_reference_interval(
        adjudication.get('reference_interval', intent.get('reference_interval', 'unknown')))
    intent.pop('reference_interval', None)
    if intent['status'] not in ('resolved', 'unknown'):
        raise ValueError('Intent is resolved or unknown.')
    available = packet_event_indices(packet)
    if not intent['reason'].strip() or not intent['evidence_indices'] or not set(intent['evidence_indices']) <= available:
        raise ValueError('Cite source events in the blinded packet and explain the interpretation.')
    if intent['status'] == 'resolved':
        validate_resolved_intent(intent, level=level)
        for view_id, override in intent.get('view_overrides', {}).items():
            if view_id not in intent['target_view_ids']:
                raise ValueError('Per-view overrides must identify an intended target view.')
            if set(override) - {'source_patch', 'members', 'source_requirement', 'retained_fields', 'released_fields'}:
                raise ValueError('Per-view overrides use the existing analytical intent fields.')
            validate_resolved_intent({**intent, **override, 'target_view_ids': [view_id]}, level='episode')
    record = {'schema': SCHEMA, 'packet_id': packet['packet_id'], 'packet_hash': digest(packet),
              'status': 'locked', 'locked_at': datetime.now(timezone.utc).isoformat(),
              'coder_a': deepcopy(coder_a), 'coder_b': deepcopy(coder_b),
              'coders_agree': coder_a['intent'] == coder_b['intent'],
              'adjudication': deepcopy(adjudication), 'intent': intent,
              'reference_interval': reference_interval, 'human_listening': 'pending'}
    record['lock_hash'] = digest(record)
    return record



def validate_resolved_intent(intent, level='episode'):
    disposition = intent.get('disposition', 'revise')
    if disposition not in ('revise', 'no_change', 'retain_all'):
        raise ValueError('Code the disposition as revise, no_change or retain_all.')
    if level == 'episode' and disposition == 'retain_all':
        raise ValueError('retain_all is a terminal-level disposition.')
    if level == 'terminal' and disposition == 'no_change':
        raise ValueError('no_change is an episode-level disposition.')
    if disposition in ('no_change', 'retain_all'):
        if intent['target_view_ids']:
            raise ValueError(f'{disposition} targets no views; leave target_view_ids empty.')
        return
    if not intent['target_view_ids']:
        raise ValueError('Specify the intended current views.')
    if not set(intent['source_patch']) <= SOURCE_FIELDS:
        raise ValueError('Use the declared analytical source fields.')
    mode = intent['members']['mode']
    if mode not in ('keep_current', 'fixed', 'rank'):
        raise ValueError('Specify preserved, fixed or dynamically ranked members.')
    if mode == 'fixed' and not intent['members']['values']:
        raise ValueError('A fixed set needs independently identified category members.')
    if mode == 'fixed' and (not isinstance(intent['members']['values'], list)
            or any(not isinstance(value, str) or not value for value in intent['members']['values'])):
        raise ValueError('Fixed members are category identifiers in a nonempty list.')
    if mode == 'rank' and (type(intent['members']['top_n']) is not int or intent['members']['top_n'] < 1):
        raise ValueError('Ranking needs a positive integer count.')
    if mode == 'rank' and intent['members'].get('rank_by') not in ('orders', 'revenue', 'low_review_rate', 'avg_delivery_days'):
        raise ValueError('Ranking needs an explicit supported rank_by measure.')
    if {'categories', 'top_n', 'rank_by'} & set(intent['source_patch']):
        raise ValueError('Describe membership in members, separately from scope changes.')
    retained, released = set(intent['retained_fields']), set(intent['released_fields'])
    changed = set(intent['source_patch']) | ({'categories', 'top_n', 'rank_by'} if mode == 'rank'
                                           else {'categories', 'top_n'} if mode == 'fixed' else set())
    if not (retained | released) <= SOURCE_FIELDS or retained & (changed | released):
        raise ValueError('Retained fields cannot also be changed or released.')
    if not released <= changed:
        raise ValueError('Released fields need an explicit replacement; unresolved choices must stay unknown.')
    requirement = intent.get('source_requirement', {'mode': 'unknown'})
    if requirement['mode'] not in ('exact', 'members_only', 'none', 'unknown'):
        raise ValueError('Code whether source identity is exact, members-only, not required, or unknown.')
    if requirement['mode'] in ('exact', 'members_only') and not requirement.get('reason', '').strip():
        raise ValueError('Explain the source requirement using the cited participant evidence.')
    if requirement['mode'] == 'exact' and not requirement.get('candidate_id'):
        raise ValueError('An exact source requirement needs an independently coded candidate ID.')


def state_at(archive, index):
    """Last actual publication by an event boundary, including Undo/Restore."""
    states = {state['revision']: state for state in archive['states'].values()}
    states[archive['initial']['revision']] = archive['initial']
    states[archive['final']['revision']] = archive['final']
    publications = []
    for event in archive['events']:
        if event['index'] > index:
            break
        if event['name'] in ('tool_committed', 'undo', 'restore'):
            publications.append(event['revision'])
        elif event['name'] == 'node_created':
            publications.append(event['node']['revision'])
    return deepcopy(states[publications[-1]]) if publications else deepcopy(archive['initial'])


def expected_sources(base, intent):
    """Independent interpretation of coded scope; no runtime revision compiler."""
    sources = {view['id']: deepcopy(view['source']) for view in base['views']}
    for view_id in intent['target_view_ids']:
        source = sources[view_id]
        scoped = {**intent, **intent.get('view_overrides', {}).get(view_id, {})}
        source.update(scoped['source_patch'])
        membership = scoped['members']
        if membership['mode'] == 'fixed':
            source.update(categories=list(membership['values']), top_n=None)
        elif membership['mode'] == 'rank':
            source.update(categories=None, top_n=membership['top_n'], rank_by=membership['rank_by'])
    return sources


def compare_state(base, observed, intent, data):
    expected = expected_sources(base, intent)
    original = {view['id']: view for view in base['views']}
    actual = {view['id']: view for view in observed['views']}
    checks = [{'name': 'view_membership', 'passed': actual.keys() == expected.keys()}]
    for view_id, source in expected.items():
        view = actual.get(view_id)
        if view is None:
            checks.append({'name': f'{view_id}:present', 'passed': False})
            continue
        for field, value in source.items():
            got = view['source'].get(field)
            equal = set(got or []) == set(value) if field == 'categories' and value is not None else got == value
            checks.append({'name': f'{view_id}:source.{field}', 'passed': equal,
                           'expected': value, 'actual': got})
        if source['dimension'] != 'category':
            checks.append({'name': f'{view_id}:independent_numbers', 'passed': None,
                           'reason': 'The independent SQL oracle covers category aggregates.'})
        else:
            checks.append({'name': f'{view_id}:independent_numbers',
                           'passed': numeric_rows_equal(view['data']['rows'], category_rows(data, source))})
        if view_id in intent['target_view_ids']:
            scoped = {**intent, **intent.get('view_overrides', {}).get(view_id, {})}
            requirement = scoped.get('source_requirement', {'mode': 'unknown'})
            actual_origin = view.get('membership_origin')
            if requirement['mode'] == 'exact':
                if actual_origin:
                    lineage = actual_origin.get(
                        'lineage_id', f"chart:{actual_origin['revision']}:{actual_origin['view_id']}")
                    passed = (actual_origin['candidate_id'] == requirement['candidate_id']
                              or lineage == requirement['candidate_id'])
                else:
                    passed = None
            else:
                passed = None if requirement['mode'] == 'unknown' else True
            checks.append({'name': f'{view_id}:provenance', 'passed': passed,
                           'requirement': requirement, 'actual': actual_origin})
        else:
            checks.append({'name': f'{view_id}:preserved_origin',
                           'passed': view.get('membership_origin') == original[view_id].get('membership_origin')})
    values = [check['passed'] for check in checks]
    correctness = False if False in values else None if None in values else True
    provenance = [c['passed'] for c in checks if c['name'].endswith(':provenance')]
    numeric = [c['passed'] for c in checks if c['name'].endswith(':independent_numbers')]
    analytical = [c['passed'] for c in checks if not c['name'].endswith((':provenance', ':independent_numbers'))]
    combine = lambda values: False if False in values else None if None in values else True
    return {'correct': correctness, 'checks': checks,
            'analytical_correct': combine(analytical), 'numeric_correct': combine(numeric),
            'provenance_correct': combine(provenance)}


def score_episode(archive, packet, lock, end_event_index, data):
    """An episode spans the declared boundary, possibly multiple repair requests."""
    onset = packet['boundary']['onset']['index']
    utterance_end = packet['boundary']['utterance_arrival_end']['index']
    by_index = {event['index']: event for event in archive['events']}
    if end_event_index < utterance_end or end_event_index not in by_index:
        raise ValueError('Choose an existing episode end after the recorded user input.')
    result = {'schema': SCHEMA, 'packet_id': packet['packet_id'],
              'session_id': archive['session']['id'], 'onset_index': onset,
              'end_event_index': end_event_index, 'intent_status': 'pending',
              'first_publication_consistent': None, 'final_correct': None,
              'understanding': {field: None for field in UNDERSTANDING_FIELDS},
              'human_listening': 'pending', 'repair_cost': None,
              'archive_hash': digest(archive), 'packet_hash': digest(packet),
              'request_ids': sorted({event['request_id'] for event in archive['events']
                  if onset <= event['index'] <= end_event_index and event.get('request_id')}),
              'limits': 'Analytical objects, scopes, independently required source identity and SQL values. Playback, understanding and repair need separate human assessment. Selection is not intent ground truth.'}
    if lock is None:
        return result
    if lock['status'] != 'locked' or lock['packet_hash'] != digest(packet) or lock['lock_hash'] != digest({k: v for k, v in lock.items() if k != 'lock_hash'}):
        raise ValueError('Score the original locked coding against its original packet.')
    result.update(intent_status=lock['intent']['status'], lock_hash=lock['lock_hash'])
    if lock['intent']['status'] == 'unknown':
        return result
    base = state_at(archive, onset - 1)
    final = state_at(archive, end_event_index)
    final_score = compare_state(base, final, lock['intent'], data)
    publications = [e for e in archive['events'] if onset <= e['index'] <= end_event_index
                    and e['name'] in ('tool_committed', 'undo', 'restore')]
    result.update(base_revision=base['revision'], final_revision=final['revision'],
                  final_correct=final_score['correct'], final_checks=final_score['checks'],
                  final_components={key: final_score[key] for key in
                      ('analytical_correct', 'numeric_correct', 'provenance_correct')},
                  publication_indices=[e['index'] for e in publications])
    if publications:
        first = compare_state(base, state_at(archive, publications[0]['index']), lock['intent'], data)
        result['first_publication_consistent'] = first['correct']
    return result


def terminal_packet(archive, episode_locks):
    """Blinded terminal-intent material: trial-start state and every participant
    input segment with its pre-input state. Strictly excludes the final state,
    post-final-input model output, and the task_response submission."""
    input_names = ('user_transcript', 'request_accepted', 'user_input', 'manual_edit_requested')
    events = archive['events']
    trial_started = next((event for event in events if event['name'] == 'trial_started'),
                         events[0] if events else {'index': 0, 'name': 'trial_started'})
    segments = []
    for event in events:
        if event['name'] not in input_names:
            continue
        segments.append({
            'index': event['index'], 'name': event['name'],
            'text': event.get('text', event.get('details', {}).get('text', '')),
            'pre_input_state': state_at(archive, event['index'] - 1),
        })
    last_input = segments[-1]['index'] if segments else trial_started['index']
    return {'schema': 'covis-terminal-packet-1', 'kind': 'terminal', 'packet_id': 'terminal',
            'session_id': archive['session']['id'],
            'boundary': {'onset': {'index': trial_started['index'], 'name': trial_started.get('name', 'trial_started')},
                         'utterance_arrival_end': {'index': last_input, 'name': 'terminal_input'}},
            'trial_start': deepcopy(archive['initial']),
            'input_segments': segments,
            'episode_locks': deepcopy(episode_locks)}


def terminal_coverage(episode_locks, terminal_packet, input_dispositions):
    """Every participant input segment is classified; episode locks carry forward."""
    segments = terminal_packet['input_segments']
    covered = set(input_dispositions)
    uncovered = [segment['index'] for segment in segments if segment['index'] not in covered]
    return {'covered': not uncovered, 'uncovered_segments': uncovered,
            'carry_forward_episodes': [lock['packet_id'] for lock in episode_locks]}


def score_terminal(archive, terminal_intent, data):
    """Terminal intent-consistency: cumulative active intent versus terminal state,
    scored against the trial-start state, reusing compare_state unchanged."""
    result = {'schema': SCHEMA, 'packet_id': 'terminal', 'session_id': archive['session']['id'],
              'intent_status': terminal_intent.get('status', 'resolved'), 'final_correct': None,
              'final_checks': [], 'final_components': None,
              'base_revision': archive['initial']['revision'],
              'final_revision': archive['final']['revision'],
              'archive_hash': digest(archive), 'human_listening': 'pending',
              'limits': 'Terminal analytical objects, scopes, independently required source identity and SQL values. '
                        'Playback, understanding and repair need separate human assessment.'}
    if terminal_intent.get('status') == 'unknown':
        return result
    score = compare_state(archive['initial'], archive['final'], terminal_intent, data)
    result.update(final_correct=score['correct'], final_checks=score['checks'],
                  final_components={key: score[key] for key in
                      ('analytical_correct', 'numeric_correct', 'provenance_correct')})
    return result


def interpretation_key(archive):
    """Execution-grounded answer key from actual committed state, never from intent."""
    initial = {view['id']: view for view in archive['initial']['views']}
    final = archive['final']
    changed = [view['id'] for view in final['views']
               if view['id'] not in initial or initial[view['id']]['source'] != view['source']]
    origin = {view['id']: view.get('membership_origin') for view in final['views']}
    scope = {view['id']: {k: view['source'][k] for k in ('region', 'start', 'end', 'metric', 'status')
                          if k in view['source']} for view in final['views'] if view['id'] in changed}
    kept_released = {}
    for view in final['views']:
        if view['id'] not in initial:
            continue
        before, after = initial[view['id']]['source'], view['source']
        kept_released[view['id']] = {
            'released_fields': [field for field in before if before[field] is not None and after.get(field) is None],
            'kept_fields': [field for field in after if field in before and after[field] == before[field]],
        }
    key = {'object_origin': origin, 'target_views': changed,
           'calculation_scope': scope, 'kept_released': kept_released}
    return {'schema': 'covis-interpretation-key-1', 'final_revision': final['revision'],
            'key': key, 'key_hash': digest(key)}


def lock_understanding(key, response, review_a, review_b, adjudication):
    """Lock the understanding review: two distinct reviewers, a matching key hash,
    and key-field plus response-span citations."""
    for reviewer in (review_a, review_b):
        if not reviewer.get('reviewer_id', '').strip():
            raise ValueError('Identify each understanding reviewer.')
        if reviewer.get('key_hash') != key['key_hash']:
            raise ValueError('Understanding reviews must cite the matching interpretation key.')
        if not set(reviewer.get('key_fields', [])) <= set(UNDERSTANDING_FIELDS):
            raise ValueError('Cite the interpretation key fields used.')
        if not reviewer.get('response_span'):
            raise ValueError('Cite the response span the judgment is based on.')
    if review_a['reviewer_id'] == review_b['reviewer_id']:
        raise ValueError('Use two distinct understanding reviewers.')
    if response.get('revision') != key['final_revision']:
        raise ValueError('The response must correspond to the final chart revision.')
    if not adjudication.get('reviewer_id', '').strip() or not adjudication.get('reason', '').strip():
        raise ValueError('Record who adjudicated and why.')
    labels = {field: adjudication.get('labels', {}).get(field) for field in UNDERSTANDING_FIELDS}
    return {'schema': SCHEMA, 'status': 'locked', 'key_hash': key['key_hash'],
            'final_revision': key['final_revision'],
            'reviewer_a': deepcopy(review_a), 'reviewer_b': deepcopy(review_b),
            'adjudication': deepcopy(adjudication), 'labels': labels,
            'response': deepcopy(response),
            'locked_at': datetime.now(timezone.utc).isoformat()}


def outcome_summary(values):
    """Every assigned value counts, including missing and unreviewed outcomes."""
    count = len(values)
    success, failure, unknown = values.count(True), values.count(False), values.count(None)
    return {'assigned': count, 'success': success, 'failure': failure, 'unknown': unknown,
            'success_lower': success / count if count else None,
            'success_upper': (success + unknown) / count if count else None}


def paired_bounds(participants):
    """Manski-style bounds on the participant-level paired B2-minus-B0 difference.

    Each participant is {'direct': outcome, 'bound_revision': outcome} with outcome
    in {True, False, None}. Unknown contributes as failure in the lower bound and
    as success in the upper bound."""
    lower_total, upper_total, count = 0.0, 0.0, 0
    for participant in participants:
        b2, b0 = participant['bound_revision'], participant['direct']
        lower_total += (1 if b2 is True else 0) - (0 if b0 is False else 1)
        upper_total += (0 if b2 is False else 1) - (1 if b0 is True else 0)
        count += 1
    if not count:
        return {'participants': 0, 'lower_bound': None, 'upper_bound': None}
    return {'participants': count, 'lower_bound': lower_total / count,
            'upper_bound': upper_total / count}


def participant_bootstrap(participants, seed=0, samples=2000):
    """Seeded participant-level bootstrap of the paired difference, using a
    symmetric midpoint for unknown outcomes. Deterministic."""
    import random
    rng = random.Random(seed)
    n = len(participants)
    if not n:
        return {'samples': samples, 'mean': None, 'ci_lower': None, 'ci_upper': None}

    def estimate(outcome):
        return 0.5 if outcome is None else float(bool(outcome))

    observed = [estimate(p['bound_revision']) - estimate(p['direct']) for p in participants]
    means = [sum(observed[rng.randrange(n)] for _ in range(n)) / n for _ in range(samples)]
    means.sort()
    return {'samples': samples, 'mean': sum(observed) / n,
            'ci_lower': means[int(0.025 * samples)], 'ci_upper': means[int(0.975 * samples) - 1]}


def create_episode(directory, onset_index, utterance_end_index, end_event_index, evidence_kind):
    from scripts.prepare_intent_review import prepare_packet
    directory = Path(directory)
    packet, private = prepare_packet(directory, onset_index, utterance_end_index, evidence_kind)
    archive = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
    if (end_event_index < utterance_end_index
            or end_event_index not in {event['index'] for event in archive['events']}):
        raise ValueError('Choose an existing episode end after the recorded user input.')
    destination = directory / 'intent-episodes' / packet['packet_id']
    destination.mkdir(parents=True)
    write_new(destination / 'packet.json', packet)
    write_new(destination / 'private.json', {**private, 'end_event_index': end_event_index,
                                           'archive_hash': digest(archive)})
    for coder in ('a', 'b'):
        write_new(destination / f'coder-{coder}.json', coding_template(packet))
    write_new(destination / 'adjudication.json', {'reviewer_id': '', 'reason': '',
                                                 'intent': coding_template(packet)['intent']})
    return {'packet_id': packet['packet_id'], 'directory': str(destination),
            'status': 'pending', 'final_correct': None}


def episode_index(directory):
    result = []
    selection_file = Path(directory) / 'intent-episodes' / 'primary.json'
    primary = json.loads(selection_file.read_text(encoding='utf-8'))['packet_id'] if selection_file.exists() else None
    for path in sorted((Path(directory) / 'intent-episodes').glob('*/packet.json')):
        packet = json.loads(path.read_text(encoding='utf-8'))
        if packet.get('kind') == 'terminal':
            continue
        boundary = json.loads((path.parent / 'private.json').read_text(encoding='utf-8'))
        record = {'packet_id': path.parent.name, 'intent_status': 'pending', 'final_correct': None,
                  'onset_index': packet['boundary']['onset']['index'],
                  'utterance_end_index': packet['boundary']['utterance_arrival_end']['index'],
                  'end_event_index': boundary['end_event_index'],
                  'locked': (path.parent / 'locked.json').exists(),
                  'scored': (path.parent / 'score.json').exists(), 'primary': primary == path.parent.name}
        scored = path.parent / 'score.json'
        if scored.exists():
            record.update(json.loads(scored.read_text(encoding='utf-8')))
            if 'first_publication_consistent' not in record and 'first_commit_correct' in record:
                record['first_publication_consistent'] = record.pop('first_commit_correct')
        elif (path.parent / 'locked.json').exists():
            record['intent_status'] = 'locked_unscored'
        assessment = path.parent / 'understanding.json'
        if assessment.exists():
            record['understanding_review'] = json.loads(assessment.read_text(encoding='utf-8'))
        result.append(record)
    return result


def review_understanding(archive, body):
    """Explicit researcher labels on verbatim answers, separate from intent/SQL."""
    if not body['reviewer_id'].strip() or not body['reason'].strip():
        raise ValueError('Identify the reviewer and evidence for the understanding assessment.')
    labels = {field: body['labels'][field] for field in UNDERSTANDING_FIELDS}
    if any(value is not None and type(value) is not bool for value in labels.values()):
        raise ValueError('Understanding labels are true, false or null (unresolved).')
    response = archive.get('task_response')
    if any(value is not None for value in labels.values()) and not response:
        raise ValueError('Understanding needs an actual participant response.')
    if response and response['revision'] != archive['final']['revision']:
        raise ValueError('The response predates the final chart; retain it as stale and ungraded.')
    return {'status': 'reviewed', 'reviewer_id': body['reviewer_id'], 'reason': body['reason'],
            'at': datetime.now(timezone.utc).isoformat(), 'labels': labels,
            'response': deepcopy(response), 'human_listening': 'pending'}


def attach_formal_scores(report, records, data=None, plan=None):
    """Attach offline outcomes without replacing the first assigned attempt."""
    indexed = {session_id: episode_index(record['directory']) for session_id, record in records.items()}
    report['intent_episodes'] = indexed
    # A trial endpoint is designated explicitly after intent coding, not selected by score.
    for row in report['assigned_rows'] + report['attempt_rows']:
        session_id = row.get('primary_session_id', row.get('session_id'))
        if session_id is None:
            continue
        directory = Path(records[session_id]['directory'])
        terminal_directory = directory / 'intent-episodes' / 'terminal'
        terminal_score_path = terminal_directory / 'score.json'
        terminal_lock_path = terminal_directory / 'locked.json'
        if terminal_score_path.exists():
            score = json.loads(terminal_score_path.read_text(encoding='utf-8'))
            lock = (json.loads(terminal_lock_path.read_text(encoding='utf-8'))
                    if terminal_lock_path.exists() else {})
            row.update(intent_packet_id='terminal', revision_correct=score.get('final_correct'),
                       intent_status=(lock.get('intent') or {}).get('status', 'resolved'))
        elif (terminal_directory / 'packet.json').exists() or terminal_lock_path.exists():
            lock = (json.loads(terminal_lock_path.read_text(encoding='utf-8'))
                    if terminal_lock_path.exists() else {})
            row.update(intent_packet_id='terminal', revision_correct=None,
                       intent_status=(lock.get('intent') or {}).get('status', 'pending'))
        else:
            selection_path = directory / 'intent-episodes' / 'primary.json'
            if selection_path.exists():
                selection = json.loads(selection_path.read_text(encoding='utf-8'))
                episode = next(e for e in indexed[session_id] if e['packet_id'] == selection['packet_id'])
                if any(other['onset_index'] > episode['onset_index'] for other in indexed[session_id]):
                    row.update(intent_status='superseded_endpoint', revision_correct=None,
                               understanding_correct=None)
                else:
                    row.update(intent_packet_id=episode['packet_id'],
                               revision_correct=episode['final_correct'],
                               intent_status=episode['intent_status'])
                    reviewed = episode.get('understanding_review')
                    if reviewed:
                        values = list(reviewed['labels'].values())
                        row['understanding_correct'] = (False if False in values else
                                                        None if None in values else True)
        understanding_path = directory / 'understanding-locked.json'
        if understanding_path.exists():
            labels = json.loads(understanding_path.read_text(encoding='utf-8')).get('labels', {})
            values = list(labels.values())
            row['understanding_correct'] = (False if False in values else
                                            None if None in values else True)
    grouped = defaultdict(lambda: {'direct': [], 'bound_revision': []})
    for row in report['assigned_rows']:
        condition = row.get('condition')
        if condition in grouped[(row.get('participant_id'), row.get('participant_slot'))]:
            grouped[(row.get('participant_id'), row.get('participant_slot'))][condition].append(
                row.get('revision_correct'))
    participants = []
    for key in sorted(grouped, key=str):
        outcomes = grouped[key]
        if not outcomes['direct'] and not outcomes['bound_revision']:
            continue
        participants.append({
            'direct': (False if False in outcomes['direct'] else
                       None if None in outcomes['direct'] or not outcomes['direct'] else True),
            'bound_revision': (False if False in outcomes['bound_revision'] else
                               None if None in outcomes['bound_revision'] or not outcomes['bound_revision'] else True),
        })
    bootstrap = (plan or {}).get('bootstrap', {})
    report['primary'] = {
        'outcome': 'terminal_intent_consistency', 'row_key': 'revision_correct',
        'conditions': [{'condition': condition, **outcome_summary(
            [row.get('revision_correct') for row in report['assigned_rows']
             if row.get('condition') == condition])}
            for condition in ('direct', 'bound_revision')],
        'paired': paired_bounds(participants),
        'bootstrap': participant_bootstrap(participants, **bootstrap),
    }
    report['secondary'] = {'interpretation': {
        'outcome': 'interface_assisted_interpretation', 'row_key': 'understanding_correct',
        'conditions': [{'condition': condition, **outcome_summary(
            [row.get('understanding_correct') for row in report['assigned_rows']
             if row.get('condition') == condition])}
            for condition in ('direct', 'bound_revision')],
    }}
    report['interpretation'] = (
        'Primary outcome: terminal intent-consistency for every assigned first attempt. '
        'Unknown, incomplete and missing outcomes stay in the denominator. The paired B2 minus B0 '
        'estimate is participant-level, with unknown-outcome bounds and a participant-cluster bootstrap. '
        'There is a single primary outcome, so no multiplicity adjustment applies. Interface-assisted '
        'interpretation, repair and interaction cost are secondary and descriptive.')
    return report


def designate_primary_episode(directory, packet_id, reviewer_id, reason):
    """Declare the final task revision before outcome scoring; never choose a best result."""
    directory = Path(directory)
    episode = directory / 'intent-episodes' / packet_id
    if not (episode / 'locked.json').exists() or (episode / 'score.json').exists():
        raise ValueError('Designate the final task revision after intent lock and before scoring.')
    if not reviewer_id.strip() or not reason.strip():
        raise ValueError('Record the endpoint reviewer and boundary rationale.')
    archive = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
    terminal = next(event for event in archive['events'] if event['name'] == 'trial_finished')
    boundary = json.loads((episode / 'private.json').read_text(encoding='utf-8'))
    if boundary['end_event_index'] != terminal['index']:
        raise ValueError('The primary task endpoint must include the final trial state, not an earlier successful edit.')
    packet = json.loads((episode / 'packet.json').read_text(encoding='utf-8'))
    onset = packet['boundary']['onset']['index']
    later = [item for item in (json.loads(path.read_text(encoding='utf-8'))
             for path in (directory / 'intent-episodes').glob('*/packet.json'))
             if item.get('kind') != 'terminal']
    if any(onset < item['boundary']['onset']['index'] <= terminal['index'] for item in later):
        raise ValueError('Designate the latest independently annotated intent, including unresolved intent; earlier superseded goals are not terminal requirements.')
    selection = {'packet_id': packet_id, 'reviewer_id': reviewer_id, 'reason': reason,
                 'at': datetime.now(timezone.utc).isoformat()}
    write_new(directory / 'intent-episodes' / 'primary.json', selection)
    return selection
