"""Inspect archived trial evidence and append human coding drafts separately."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
import wave

from .study import task_brief


INTERPRETATIONS = ('pending', 'supported', 'unsupported', 'unclear')
SPOKEN_CONSISTENCY = ('pending', 'consistent', 'inconsistent', 'not_available', 'unclear')
SEGMENT_KINDS = ('repair', 'exploration', 'intent_change', 'unclear')


def read_trial_archives(directories):
    """Read assigned archives; a later directory supplies the current copy."""
    records = {}
    for directory in directories:
        for path in sorted(directory.glob('*/session.json')):
            archive = json.loads(path.read_text(encoding='utf-8'))
            if archive['session'].get('assignment'):
                records[archive['session']['id']] = {'archive': archive, 'directory': path.parent}
    return records


def load_review_drafts(directory: Path):
    path = directory / 'review-drafts.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def attach_review_drafts(aggregate, records):
    """Attach provisional notes without merging them into scored outcomes."""
    drafts = {session_id: load_review_drafts(record['directory']) for session_id, record in records.items()}
    aggregate['review_drafts'] = [draft for history in drafts.values() for draft in history]
    for row in aggregate['attempt_rows']:
        history = drafts[row['session_id']]
        row.update(review_draft_count=len(history), last_draft_at=history[-1]['at'] if history else None)
    return aggregate


def _measured_event_indices(events):
    start = next((event['index'] for event in events if event['name'] == 'trial_started'), None)
    end = next((event['index'] for event in events if event['name'] == 'trial_finished'), None)
    return [event['index'] for event in events if start is not None and event['index'] >= start
            and (end is None or event['index'] <= end)]


def build_review_packet(archive, directory: Path):
    """Keep event indices, clock domains and archived scores exactly as recorded."""
    session = archive['session']
    events = archive['events']
    media = []
    for path in sorted(directory.iterdir()):
        if path.suffix not in ('.wav', '.jpg'):
            continue
        event_file = path.with_suffix('.pcm').name if path.suffix == '.wav' else path.name
        item = {'name': path.name,
                'url': f"/api/experiment/attempts/{session['id']}/media/{path.name}",
                'kind': 'audio' if path.suffix == '.wav' else 'image',
                'event_indices': [event['index'] for event in events if event.get('file') == event_file]}
        if path.suffix == '.wav':
            with wave.open(str(path), 'rb') as audio:
                item.update(sample_rate=audio.getframerate(),
                            duration_seconds=audio.getnframes() / audio.getframerate())
        media.append(item)
    transcripts = [
        {'event_index': event['index'],
         'role': 'user' if event['name'] == 'user_transcript' else 'assistant',
         'text': event['event']['text'],
         'response_id': event['event'].get('response_id'),
         'item_id': event['event'].get('item_id')}
        for event in events if event['name'] in ('user_transcript', 'assistant_done')
    ]
    return deepcopy({
        'session': session,
        'task': archive['task'] if 'task' in archive else task_brief(session['task_id']),
        'task_source': 'archive' if 'task' in archive else 'materials_lookup',
        'trial_report': (archive['report'] or {}).get('trial_report'),
        'task_response': archive['task_response'],
        'initial': archive['initial'], 'final': archive['final'],
        'events': events, 'measured_event_indices': _measured_event_indices(events),
        'nodes': archive['nodes'], 'node_states': archive['states'],
        'transcripts': transcripts, 'media': media,
        'review_drafts': load_review_drafts(directory), 'review_status': 'pending',
    })


def save_review_draft(archive, directory: Path, body):
    """Store a reviewer's proposed labels; never alter trial evidence or scores."""
    reviewer = body['reviewer_id'].strip()
    notes = body['notes'].strip()
    if not reviewer:
        raise ValueError('Enter a reviewer label.')
    if body['interpretation'] not in INTERPRETATIONS or body['spoken_consistency'] not in SPOKEN_CONSISTENCY:
        raise ValueError('Choose one of the listed review labels.')
    if (body['interpretation'] != 'pending' or body['spoken_consistency'] != 'pending') and not notes:
        raise ValueError('Explain the proposed interpretation or speech label in review notes.')
    measured = set(_measured_event_indices(archive['events']))
    segments = []
    for segment in body['segments']:
        start, end = segment['start_event_index'], segment['end_event_index']
        if start not in measured or end not in measured or start > end:
            raise ValueError('Select an ordered event range inside the measured task interval.')
        if segment['kind'] not in SEGMENT_KINDS:
            raise ValueError('Choose repair, exploration, intent change or unclear.')
        if not segment['reason'].strip():
            raise ValueError('Explain the evidence for each proposed event label.')
        segments.append({'start_event_index': start, 'end_event_index': end,
                         'kind': segment['kind'], 'reason': segment['reason'].strip()})
    if not notes and not segments:
        raise ValueError('Add review notes or an evidence-linked segment.')
    draft = {'id': uuid4().hex, 'at': datetime.now(timezone.utc).isoformat(),
             'session_id': archive['session']['id'], 'reviewer_id': reviewer, 'status': 'draft',
             'notes': notes, 'interpretation': body['interpretation'],
             'spoken_consistency': body['spoken_consistency'], 'segments': segments}
    with (directory / 'review-drafts.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(draft, ensure_ascii=False) + '\n')
    return draft
 