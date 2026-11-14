"""Read archived playback metadata only; preserve every original result."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
results = []
for path in sorted((root / 'traces/real-study-20261113-224313').glob('0*/report.json')):
    report = json.loads(path.read_text(encoding='utf-8'))
    start = report['browser_input_segments'][-1]['started_client_ms']
    response_ids = report['overlap_response_ids']
    observations = [e for e in report['events'] if e['name'].startswith('playback_')
                    and e.get('details', {}).get('response_id') in response_ids
                    and e.get('client_ms') is not None]
    before = [e for e in observations if e['client_ms'] <= start]
    after = [e for e in observations if e['client_ms'] > start
             and e['name'] in ('playback_progress', 'playback_chunk_ended', 'playback_end')]
    left = max(before, key=lambda e: e['client_ms']) if before else None
    right = min(after, key=lambda e: e['client_ms']) if after else None
    def compact(e):
        if e is None:
            return None
        return {'name': e['name'], 'client_ms': e['client_ms'],
                **{k: e['details'].get(k) for k in ('queue_empty', 'pending_chunks',
                    'played_samples', 'queued_samples', 'interrupted', 'audio_context_time')}}
    results.append({'trial': path.parent.name, 'source_input_start_client_ms': start,
                    'last_prior_observation': compact(left), 'first_later_progress': compact(right),
                    'original_overlap_valid': report['overlap_valid'],
                    'original_result_unchanged': True})
output = {'scope': 'Local source start bracketed by archived browser playback receipts; '
                   'not acoustic measurement, not a reclassification of original API results.',
          'trials': results}
target = Path(__file__).with_name('archived-overlap-recheck.json')
target.write_text(json.dumps(output, indent=2), encoding='utf-8')
for row in results:
    left, right = row['last_prior_observation'], row['first_later_progress']
    print(row['trial'], 'prior_empty=', left and left['queue_empty'],
          'prior_queued=', left and left['queued_samples'],
          'subsequent_played=', right and right['played_samples'])
