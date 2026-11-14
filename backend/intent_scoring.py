"""Offline, independently coded revision episodes. Never used in model context.

Coders see the pre-outcome packet. An adjudicator locks their interpretation
before this module reads publications. Unreviewed and unresolved intent stays
unknown; SQL verifies data, not the participant's intention.
"""
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


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def write_new(path, content):
    """Review locks and results are new artifacts, never replacements of evidence."""
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(content, stream, indent=2, ensure_ascii=False)


def coding_template(packet):
    return {'schema': SCHEMA, 'packet_id': packet['packet_id'], 'reviewer_id': '',
            'status': 'pending', 'intent': {
                'status': 'unknown', 'target_view_ids': [], 'source_patch': {},
                'members': {'mode': 'keep_current'},
                'retained_fields': [], 'released_fields': [], 'view_overrides': {},
                'reason': '', 'evidence_indices': []},
            'speech_verification': 'pending'}


def lock_intent(packet, coder_a, coder_b, adjudication):
    """Validate an explicit two-coder handoff; never manufacture a human label."""
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
    if intent['status'] not in ('resolved', 'unknown'):
        raise ValueError('Intent is resolved or unknown.')
    available = {event['index'] for event in packet['prior_context'] + packet['participant_input']}
    available.add(packet['boundary']['onset']['index'])
    if not intent['reason'].strip() or not intent['evidence_indices'] or not set(intent['evidence_indices']) <= available:
        raise ValueError('Cite source events in the blinded packet and explain the interpretation.')
    if intent['status'] == 'resolved':
        validate_resolved_intent(intent)
        for view_id, override in intent.get('view_overrides', {}).items():
            if view_id not in intent['target_view_ids']:
                raise ValueError('Per-view overrides must identify an intended target view.')
            if set(override) - {'source_patch', 'members', 'retained_fields', 'released_fields'}:
                raise ValueError('Per-view overrides use the existing analytical intent fields.')
            validate_resolved_intent({**intent, **override, 'target_view_ids': [view_id]})
    record = {'schema': SCHEMA, 'packet_id': packet['packet_id'], 'packet_hash': digest(packet),
              'status': 'locked', 'locked_at': datetime.now(timezone.utc).isoformat(),
              'coder_a': deepcopy(coder_a), 'coder_b': deepcopy(coder_b),
              'coders_agree': coder_a['intent'] == coder_b['intent'],
              'adjudication': deepcopy(adjudication), 'intent': intent,
              'human_listening': 'pending'}
    record['lock_hash'] = digest(record)
    return record



def validate_resolved_intent(intent):
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
    values = [check['passed'] for check in checks]
    correctness = False if False in values else None if None in values else True
    return {'correct': correctness, 'checks': checks}


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
              'first_commit_correct': None, 'final_correct': None,
              'understanding': {field: None for field in UNDERSTANDING_FIELDS},
              'human_listening': 'pending', 'repair_cost': None,
              'archive_hash': digest(archive), 'packet_hash': digest(packet),
              'request_ids': sorted({event['request_id'] for event in archive['events']
                  if onset <= event['index'] <= end_event_index and event.get('request_id')}),
              'limits': 'Analytical objects, scopes and SQL values only. Playback, understanding and repair are independent human assessments. Intermediate differences are not automatically errors.'}
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
                  publication_indices=[e['index'] for e in publications])
    if publications:
        first = compare_state(base, state_at(archive, publications[0]['index']), lock['intent'], data)
        result['first_commit_correct'] = first['correct']
    return result


def outcome_summary(values):
    """Every assigned value counts, including missing and unreviewed outcomes."""
    count = len(values)
    success, failure, unknown = values.count(True), values.count(False), values.count(None)
    return {'assigned': count, 'success': success, 'failure': failure, 'unknown': unknown,
            'success_lower': success / count if count else None,
            'success_upper': (success + unknown) / count if count else None}


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


def attach_formal_scores(report, records):
    """Attach offline outcomes without replacing the first assigned attempt."""
    indexed = {session_id: episode_index(record['directory']) for session_id, record in records.items()}
    report['intent_episodes'] = indexed
    # A trial endpoint is designated explicitly after intent coding, not selected by score.
    for row in report['assigned_rows'] + report['attempt_rows']:
        session_id = row.get('primary_session_id', row.get('session_id'))
        if session_id is None:
            continue
        selection_path = records[session_id]['directory'] / 'intent-episodes' / 'primary.json'
        if not selection_path.exists():
            continue
        selection = json.loads(selection_path.read_text(encoding='utf-8'))
        episode = next(e for e in indexed[session_id] if e['packet_id'] == selection['packet_id'])
        if any(other['onset_index'] > episode['onset_index'] for other in indexed[session_id]):
            row.update(intent_status='superseded_endpoint', revision_correct=None,
                       understanding_correct=None)
            continue
        row.update(intent_packet_id=episode['packet_id'], revision_correct=episode['final_correct'],
                   intent_status=episode['intent_status'])
        reviewed = episode.get('understanding_review')
        if reviewed:
            values = list(reviewed['labels'].values())
            row['understanding_correct'] = False if False in values else None if None in values else True
    report['conditions'] = [{
        'condition': condition,
        'revision': outcome_summary([row['revision_correct'] for row in report['assigned_rows'] if row['condition'] == condition]),
        'understanding': outcome_summary([row['understanding_correct'] for row in report['assigned_rows'] if row['condition'] == condition]),
    } for condition in ('direct', 'bound_revision')]
    report['interpretation'] = ('First assigned participant attempts only. Intent must be independently locked before SQL scoring. '
        'Unknown, incomplete and missing outcomes remain in the denominator. These are descriptive counts and bounds, not a treatment-effect test.')
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
    later = [json.loads(path.read_text(encoding='utf-8'))
             for path in (directory / 'intent-episodes').glob('*/packet.json')]
    if any(onset < item['boundary']['onset']['index'] <= terminal['index'] for item in later):
        raise ValueError('Designate the latest independently annotated intent, including unresolved intent; earlier superseded goals are not terminal requirements.')
    selection = {'packet_id': packet_id, 'reviewer_id': reviewer_id, 'reason': reason,
                 'at': datetime.now(timezone.utc).isoformat()}
    write_new(directory / 'intent-episodes' / 'primary.json', selection)
    return selection
