"""Offline aggregation of the frozen eight authored real-model trials; no API access."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_events(report, directory):
    events = report.get('events')
    if events is not None:
        return events
    trace = directory / 'trace.json'
    if trace.exists():
        payload = read_json(trace)
        return payload if isinstance(payload, list) else payload.get('events', [])
    session = report.get('session_directory')
    candidates = [Path(session) / 'events.jsonl'] if session else []
    candidates += list(directory.glob('sessions/*/events.jsonl'))
    for path in candidates:
        if path.exists():
            return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    return []


def compact(event):
    fields = ('index', 'name', 'request_id', 'response_id', 'at', 'tool', 'arguments',
              'status', 'committed', 'revision', 'message', 'error', 'actor')
    result = {key: event[key] for key in fields if key in event}
    payload = event.get('event', {})
    for key in ('text', 'message', 'error', 'status', 'usage'):
        if key in payload:
            result[key] = payload[key]
    if event['name'] == 'tool_failed':
        result['failure_details'] = {key: event[key] for key in ('result', 'reason') if key in event}
    return result


def sum_numbers(value, result, prefix=''):
    for key, item in value.items():
        path = f'{prefix}.{key}' if prefix else key
        if isinstance(item, dict):
            sum_numbers(item, result, path)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            result[path] += item


def summarize(directory, case, condition):
    path = directory / 'report.json'
    base = {'case': case, 'condition': condition, 'report_path': str(path)}
    if not path.exists():
        return {**base, 'status': 'not_attempted', 'api_attempted': False,
                'modelgoal': None, 'overall_pipeline_pass': None}
    report = read_json(path)
    events = load_events(report, directory)
    named = lambda name: [event for event in events if event['name'] == name]
    status = report.get('status', 'incomplete')
    checks = report.get('evaluation', {}).get('checks', {})
    goal_checks = {key: value for key, value in checks.items()
                   if key == 'exact_view_ids' or key.endswith(('_source', '_independent_sql', '_unchanged'))}
    goal = all(goal_checks.values()) if goal_checks else None
    requests = {phase: report.get(f'{phase}_request_id') for phase in ('initial', 'revision')}
    trigger = report.get('revision_trigger_event_index')
    post_trigger = [event for event in events if trigger is not None and event.get('index', -1) >= trigger]
    post_accepted = [event for event in post_trigger if event['name'] == 'request_accepted']
    latest_revision_id = post_accepted[-1].get('request_id') if post_accepted else requests['revision']
    turns = {}
    for phase, request_id in requests.items():
        own = [event for event in events if request_id and event.get('request_id') == request_id]
        turns[phase] = {
            'request_id': request_id,
            'user_transcripts': [compact(e) for e in own if e['name'] == 'user_transcript'],
            'assistant_transcripts': [compact(e) for e in own if e['name'] == 'assistant_done'],
            'tool_calls': [compact(e) for e in own if e['name'] == 'tool_started'],
            'tool_errors': [compact(e) for e in own if e['name'] == 'tool_failed'],
            'commits': [compact(e) for e in own if e['name'] == 'tool_committed'],
            'outcomes': [compact(e) for e in own if e['name'] == 'request_outcome'],
        }
    # Playback progress is cumulative. Keep the last receipt per response/generation,
    # rather than adding successive progress samples and overcounting output.
    playback = {}
    for event in events:
        if event['name'] in ('playback_progress', 'playback_end'):
            details = event.get('details', {})
            key = (details.get('response_id', event.get('response_id')), details.get('generation_epoch'))
            playback[key] = {key: details.get(key) for key in (
                'response_id', 'generation_epoch', 'sample_rate', 'received_samples', 'played_samples',
                'interrupted', 'started', 'queue_empty', 'pending_chunks')}
            playback[key]['last_event_name'] = event['name']
    revision_id = latest_revision_id
    revision_received = Counter()
    for event in named('audio_received'):
        if revision_id and event.get('request_id') == revision_id:
            revision_received[event.get('response_id')] += event.get('bytes', 0) // 2
    natural_ends = {}
    for event in named('playback_end'):
        if revision_id and event.get('request_id') == revision_id:
            detail = event.get('details', {})
            natural_ends[detail.get('response_id', event.get('response_id'))] = detail
    natural_per_response = {
        response_id: (response_id in natural_ends
                      and natural_ends[response_id].get('interrupted') is False
                      and natural_ends[response_id].get('started') is True
                      and natural_ends[response_id].get('played_samples') == samples
                      and natural_ends[response_id].get('received_samples') == samples)
        for response_id, samples in revision_received.items()
    }
    natural_completion = bool(natural_per_response) and all(natural_per_response.values())
    last_revision_end = next((e for e in reversed(events) if e['name'] == 'playback_end'
                              and revision_id and e.get('request_id') == revision_id), None)
    natural_end_elapsed = None
    if natural_completion and last_revision_end and report.get('started_at'):
        natural_end_elapsed = (datetime.fromisoformat(last_revision_end['at'])
                               - datetime.fromisoformat(report['started_at'])).total_seconds()
    connected, closed = named('voice_connected'), named('voice_closed')
    interval = None
    if connected and closed:
        interval = (datetime.fromisoformat(closed[-1]['at']) - datetime.fromisoformat(connected[0]['at'])).total_seconds()
    usage = Counter()
    for event in named('usage'):
        sum_numbers(event.get('event', {}).get('usage', event.get('usage', {})), usage)
    sent_seconds = sum(e.get('bytes', 0) / 2 / e.get('sample_rate', 16000) for e in named('audio_sent'))
    output_seconds = sum(e.get('bytes', 0) / 2 / e.get('sample_rate', 24000) for e in named('audio_received'))
    segments = report.get('browser_input_segments', [])
    utterances = sum(segment.get('duration', 0) for segment in segments)
    failures = []
    for name in ('tool_failed', 'session_error', 'error', 'transport_closed'):
        failures += [compact(e) for e in named(name)]
    if report.get('invalid_reason'):
        failures.append({'name': 'invalid_timing_or_input', 'message': report['invalid_reason']})
    if report.get('error') or report.get('error_type'):
        failures.append({'name': 'driver_error', 'message': report.get('error', report.get('error_type'))})
    if report.get('timed_out') or report.get('watchdog_fired'):
        failures.append({'name': 'time_budget_reached'})
    transport_errors = [event for event in events if event['name'] in ('error', 'session_error')]
    if turns['revision']['request_id'] and not turns['revision']['commits'] and not transport_errors:
        failures.append({'name': 'accepted_revision_without_commit',
                         'assistant_reply_present': bool(turns['revision']['assistant_transcripts'])})
    if goal is False:
        failures.append({'name': 'final_goal_mismatch', 'failed_checks': [k for k, v in goal_checks.items() if not v]})
    failed_pipeline = [key for key, value in checks.items() if not value and key not in goal_checks]
    if failed_pipeline:
        failures.append({'name': 'pipeline_check_failure', 'failed_checks': failed_pipeline})
    if transport_errors:
        audited_terminal = 'transport_or_session_failure'
    elif named('tool_failed'):
        audited_terminal = 'tool_failure'
    elif report.get('timed_out') or report.get('watchdog_fired'):
        audited_terminal = 'budget_stop_after_natural_completion' if natural_completion else 'budget_stop'
    elif status in ('running', 'preflight', 'prepared'):
        audited_terminal = status
    elif report.get('invalid_reason'):
        audited_terminal = 'invalid_timing_or_input'
    else:
        audited_terminal = report.get('finish_reason', status)
    sources = lambda state: {v['id']: v['source'] for v in state.get('views', [])}
    return {**base, 'status': status, 'api_attempted': report.get('api_attempted', False),
            'finish_reason': report.get('finish_reason'), 'modelgoal': goal,
            'raw_driver_status': status, 'raw_driver_finish_reason': report.get('finish_reason'),
            'raw_driver_watchdog_fired': report.get('watchdog_fired', False),
            'raw_driver_timed_out': report.get('timed_out', False),
            'audited_terminal_classification': audited_terminal,
            'raw_tracked_revision_request_id': requests['revision'],
            'latest_accepted_revision_request_id': latest_revision_id,
            'revision_request_tracking_mismatch': latest_revision_id != requests['revision'],
            'post_trigger_accepted_requests': [compact(e) for e in post_accepted],
            'post_trigger_transcripts': [compact(e) for e in post_trigger
                                        if e['name'] in ('user_transcript', 'assistant_done')],
            'post_trigger_errors': [compact(e) for e in post_trigger
                                   if e['name'] in ('error', 'session_error', 'tool_failed', 'transport_closed')],
            'post_trigger_response_ids': sorted({e['response_id'] for e in post_trigger if e.get('response_id')}),
            'post_trigger_records': post_trigger,
            'pipeline_checks_pass': all(checks.values()) if checks else None,
            'overall_pipeline_pass': (status == 'passed' and all(checks.values())) if checks else None,
            'delivery': {'final_output_audio': report.get('final_output_audio'),
                         'final_settled_and_queue_empty': report.get('final_settled_and_drained'),
                         'revision_audio_natural_completion': natural_completion,
                         'natural_completion_request_id': revision_id,
                         'revision_natural_completion_elapsed_seconds': natural_end_elapsed,
                         'revision_response_natural_completion': natural_per_response,
                         'revision_received_samples_by_response': dict(revision_received),
                         'final_views_rendered': checks.get('final_views_rendered'),
                         'actual_image_sent': checks.get('actual_image_sent')},
            'goal_checks': goal_checks, 'pipeline_checks': checks, 'turns': turns,
            'all_tool_errors': [compact(e) for e in named('tool_failed')],
            'model_tool_call_count': sum(e.get('actor') == 'model' for e in named('tool_started')),
            'model_commit_count': sum(e.get('actor') == 'model' for e in named('tool_committed')),
            'initial_sources': sources(report.get('initial_state', {})),
            'final_sources': sources(report.get('final_state', {})),
            'expected_sources': report.get('evaluation', {}).get('expected_sources'),
            'actual_overlap': checks.get('actual_revision_speech_during_playback'),
            'driver_overlap_flag': report.get('overlap_valid'), 'playback': list(playback.values()),
            'received_output_seconds': output_seconds,
            'played_output_seconds': sum((p.get('played_samples') or 0) / (p.get('sample_rate') or 24000) for p in playback.values()),
            'jpg_sent_count': sum(e.get('status') == 'sent' for e in named('image_delivery')),
            'voice_connected_at': connected[0]['at'] if connected else None,
            'voice_closed_at': closed[-1]['at'] if closed else None,
            'connected_to_closed_seconds': interval,
            'driver_connection_wall_seconds': report.get('connection_wall_seconds'),
            'streamed_pcm_seconds': sent_seconds,
            'source_utterance_seconds': utterances if segments else None,
            'browser_input_segments': segments, 'usage_event_count': len(named('usage')),
            'provider_usage_numeric_totals': dict(usage), 'usage_is_money': False,
            'failure_types': failures, 'human_listening': 'pending', 'spoken_semantic_review': 'pending'}


def aggregate(root):
    plan = read_json(root / 'matrix-plan.json')
    trials = [summarize(root / f'{case}-{condition}', case, condition) for case, condition in plan['order']]
    totals = Counter()
    for trial in trials:
        totals.update(trial.get('provider_usage_numeric_totals', {}))
    return {'kind': 'authored_real_model_diagnostic_not_participant_study',
            'expected_trials': 8, 'status_counts': dict(Counter(t['status'] for t in trials)),
            'attempted_trials': sum(t['api_attempted'] for t in trials),
            'modelgoal_pass_count': sum(t['modelgoal'] is True for t in trials),
            'overall_pipeline_pass_count': sum(t['overall_pipeline_pass'] is True for t in trials),
            'usage_event_count': sum(t.get('usage_event_count', 0) for t in trials),
            'provider_usage_numeric_totals': dict(totals), 'usage_is_money': False,
            'human_listening': 'pending', 'participant_results': 'not_collected', 'trials': trials}


def markdown(summary):
    lines = ['# Eight authored real-model diagnostics', '',
             'These are model trials, not participant results. Human listening and spoken semantic review remain pending. No inferential statistics or billing estimates are produced.', '',
             f"Attempted: {summary['attempted_trials']}/8. Final source/SQL goal passes: {summary['modelgoal_pass_count']}/8. Complete pipeline passes: {summary['overall_pipeline_pass_count']}/8.", '',
             '| Family | Condition | Raw driver | Model goal | All checks | Overall pipeline | Actual overlap | Provider connection s |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for trial in summary['trials']:
        lines.append('| ' + ' | '.join(str(trial.get(key)) for key in (
            'case', 'condition', 'status', 'modelgoal', 'pipeline_checks_pass', 'overall_pipeline_pass', 'actual_overlap', 'connected_to_closed_seconds')) + ' |')
    lines += ['', 'Raw driver status is preserved separately from final model-goal, delivery and check results. A watchdog timeout remains a driver failure even if every recorded check passes; overall pipeline requires both a passed driver and all checks. Provider connection duration uses voice_connected to voice_closed timestamps; the driver wall interval also includes setup/cleanup around the connection. Queue-empty after an interrupted budget stop is not natural playback completion: natural completion additionally requires every revision response to have a non-interrupted playback end and played samples equal to all received samples. A watchdog can fire during awaited shutdown after natural playback already ended; the separate natural-completion timestamp makes that distinction inspectable.', '', 'Provider usage is the sum of recorded numeric usage fields across response events, including partial/interrupted responses. Nested token detail fields overlap parent totals and must not be added together. Usage is not a monetary charge.', '']
    for trial in summary['trials']:
        lines += [f"## {trial['case']} {trial['condition']}", '', f"Report: `{trial['report_path']}`", '']
        lines += [f"Audited terminal: {trial.get('audited_terminal_classification')}; raw finish: {trial.get('raw_driver_finish_reason')}. Tracked/latest revision request: {trial.get('raw_tracked_revision_request_id')} / {trial.get('latest_accepted_revision_request_id')}.", '']
        for phase, turn in trial.get('turns', {}).items():
            lines.append(f"{phase.capitalize()} user: " + ' / '.join(e.get('text', '') for e in turn['user_transcripts']))
            lines.append(f"{phase.capitalize()} assistant: " + ' / '.join(e.get('text', '') for e in turn['assistant_transcripts']))
        lines += ['', 'Concrete failures/checks: `' + json.dumps(trial.get('failure_types', []), ensure_ascii=False) + '`', '',
                  'All post-trigger transcripts: `' + json.dumps(trial.get('post_trigger_transcripts', []), ensure_ascii=False) + '`', '',
                  'All post-trigger errors: `' + json.dumps(trial.get('post_trigger_errors', []), ensure_ascii=False) + '`', '',
                  'Delivery: `' + json.dumps(trial.get('delivery', {}), ensure_ascii=False) + '`', '',
                  f"Streamed PCM: {trial.get('streamed_pcm_seconds')} s; source utterances: {trial.get('source_utterance_seconds')} s; output received/played: {trial.get('received_output_seconds')}/{trial.get('played_output_seconds')} s; JPEG deliveries: {trial.get('jpg_sent_count')}; usage events: {trial.get('usage_event_count')}.", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Frozen matrix output directory')
    args = parser.parse_args()
    result = aggregate(args.root)
    (args.root / 'aggregate.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.root / 'RESULTS.md').write_text(markdown(result), encoding='utf-8')
    print(json.dumps({'attempted': result['attempted_trials'], 'statuses': result['status_counts']}))


if __name__ == '__main__':
    main()
