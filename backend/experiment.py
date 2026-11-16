"""Balanced assignments and observable trial reports for the local study apparatus."""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
from io import StringIO

from .observations import interaction_summary
from .formal_tasks import (FORMAL_PROTOCOL, FORMAL_MATERIALS_PROTOCOL, VOICE_BUDGET_SECONDS,
                           content_sha256, formal_task_brief, formal_materials_manifest)


PROTOCOL = 'covis-experiment-0.1'
MATERIALS_PROTOCOL = 'covis-matched-0.1'
ORDER_ROWS = ((1, 2, 4, 3), (2, 3, 1, 4), (3, 4, 2, 1), (4, 1, 3, 2))
CONDITIONS = ('direct', 'bound_revision')
TIME_LIMIT_SECONDS = 480


def allocation_for(slot):
    """One slot receives each family once, two tasks per condition, mixed variants."""
    if not isinstance(slot, int) or slot < 1:
        raise ValueError('Participant slot must be a positive integer.')
    position = (slot - 1) % 16
    order_row = position % 4
    condition_flip = (position // 4) % 2
    variant_flip = position // 8
    trials = []
    for index, family in enumerate(ORDER_ROWS[order_row]):
        variant = ('a', 'b')[(index + variant_flip) % 2]
        trials.append({
            'protocol': PROTOCOL, 'materials_protocol': MATERIALS_PROTOCOL, 'participant_slot': slot,
            'trial_id': f's{slot:03d}-t{index + 1}', 'trial_index': index + 1,
            'family_id': f'{family:02d}', 'variant_id': variant,
            'task_id': f'exp_{family:02d}_{variant}',
            'condition': CONDITIONS[((index // 2) + condition_flip) % 2],
            'time_limit_seconds': TIME_LIMIT_SECONDS,
        })
    return {'protocol': PROTOCOL, 'participant_slot': slot, 'block': (slot - 1) // 16 + 1,
            'order_row': order_row + 1, 'condition_order': ['direct', 'bound_revision'][condition_flip:] + ['direct', 'bound_revision'][:condition_flip],
            'variant_pattern': ''.join(trial['variant_id'].upper() for trial in trials), 'trials': trials}


def allocation_table(count=30):
    if count < 1:
        raise ValueError('Choose at least one participant slot.')
    allocations = [allocation_for(slot) for slot in range(1, count + 1)]
    frequencies = Counter((trial['family_id'], trial['trial_index'], trial['condition'], trial['variant_id'])
                          for plan in allocations for trial in plan['trials'])
    cells = [{'family_id': f'{family:02d}', 'trial_index': order, 'condition': condition,
              'variant_id': variant, 'count': frequencies[(f'{family:02d}', order, condition, variant)]}
             for family in range(1, 5) for order in range(1, 5)
             for condition in CONDITIONS for variant in ('a', 'b')]
    values = [cell['count'] for cell in cells]
    return {'protocol': PROTOCOL, 'participant_count': count, 'block_size': 16,
            'allocations': allocations, 'balance': {
                'cells': cells, 'exact_full_balance': len(set(values)) == 1,
                'cell_min': min(values), 'cell_max': max(values),
                'complete_blocks': count // 16, 'partial_block_slots': count % 16,
                'condition_counts': dict(Counter(trial['condition'] for plan in allocations for trial in plan['trials'])),
                'meaning': 'Joint family × position × condition × variant balance holds for complete 16-slot blocks. A partial block is reported as allocated, not called perfectly balanced.',
            }}


def build_trial_report(session, base_report, events, task_response=None):
    """No inferred repairs, reading, speech meaning or fabricated completion times."""
    assignment = session['assignment']
    starts = [event for event in events if event['name'] == 'trial_started']
    ends = [event for event in events if event['name'] == 'trial_finished']
    start = starts[0] if starts else None
    end = ends[0] if ends else None
    window = [event for event in events if start is not None and event['index'] >= start['index']
              and (end is None or event['index'] <= end['index'])]
    reason = end['reason'] if end else None
    correct = bool(base_report.get('technical_completed', base_report.get('completed', False)))
    response_complete_current = base_report.get('task_response_current', False)
    deliverables_complete = correct and response_complete_current
    submitted_deliverables_complete = reason == 'completed' and deliverables_complete
    status = ('completed' if submitted_deliverables_complete else 'submitted_incomplete') if reason == 'completed' else reason or ('running' if start else 'ready')
    elapsed = round((end['server_ms'] - start['server_ms']) / 1000, 3) if start and end else None
    counts = Counter(event['name'] for event in window)
    count_names = ('request_accepted', 'tool_started', 'tool_committed', 'tool_failed', 'tool_superseded',
                   'evidence_selected', 'category_set_saved', 'undo', 'restore', 'revision_proposed',
                   'revision_applied', 'revision_confirmed', 'revision_card_opened', 'revision_confirmation_clicked',
                   'playback_start', 'playback_end', 'audio_sent', 'audio_received', 'user_transcript',
                   'speech_start', 'image_captured', 'chart_rendered', 'task_response_submitted',
                   'history_open', 'selection', 'inspector_open', 'recording_start', 'recording_end',
                   'text_submit', 'text_focus', 'text_blur', 'revision_panel_open', 'revision_card_revision_requested')
    tools = {phase: dict(Counter(event['tool'] for event in window if event['name'] == f'tool_{phase}'))
             for phase in ('started', 'committed')}
    commits = deepcopy(base_report.get('commit_assessments', []))
    first_full = next((commit for commit in commits if commit.get('full_correct')), None)
    submitted_correct = reason == 'completed' and correct
    sent_frames = [event for event in window if event['name'] == 'image_delivery' and event['status'] == 'sent']
    return {
        'protocol': assignment.get('protocol', PROTOCOL),
        'identity': {'session_id': session['id'], 'participant_id': session['participant_id'],
                     **{key: assignment[key] for key in ('participant_slot', 'trial_id', 'trial_index', 'family_id', 'variant_id', 'task_id', 'condition')},
                     'evidence_kind': session['evidence_kind'], 'materials_protocol': assignment.get('materials_protocol', MATERIALS_PROTOCOL)},
        'started_at': start['at'] if start else session['started_at'],
        'outcome': {'status': status, 'terminal_reason': reason, 'technical_completed': correct,
                    'submitted_correct': submitted_correct, 'chart_submitted_correct': submitted_correct,
                    'response_complete_current': response_complete_current,
                    'deliverables_complete': deliverables_complete,
                    'submitted_deliverables_complete': submitted_deliverables_complete,
                    'submission_basis': base_report.get('completion_basis', 'Public chart requirements only; completed response fields still await human interpretation.'),
                    'review_status': 'pending',
                    'business_conclusion_correct': None, 'understanding_correct': None},
        'timing': {'start_server_ms': start['server_ms'] if start else None,
                   'end_server_ms': end['server_ms'] if end else None,
                   'elapsed_seconds': elapsed, 'time_limit_seconds': assignment['time_limit_seconds'],
                   'correct_completion_observed': submitted_correct,
                   'time_censored': bool(start and not submitted_correct),
                   'time_analysis_status': 'not_started' if start is None else 'ongoing' if end is None else 'observed_chart_submission' if submitted_correct else 'censored',
                   'first_full_correct_seconds': round((first_full['server_ms'] - start['server_ms']) / 1000, 3)
                       if first_full and start else None},
        'process': {
            'counts': {name: counts[name] for name in count_names}, 'tools': tools,
            'visual_input': {
                'captured_frames': counts['image_captured'],
                'queued_frames': sum(event['name'] == 'image_delivery' and event['status'] == 'queued' for event in window),
                'sent_frames': len(sent_frames),
                'sent_frame_ids': [event['frame_id'] for event in sent_frames],
                'interpretation': 'Sent means an image was appended to the native provider input buffer. It does not establish consumption or visual understanding.',
            },
            'audio': {
                'input_seconds': round(sum(event['bytes'] / (2 * event['sample_rate']) for event in window if event['name'] == 'audio_sent'), 3),
                'received_output_seconds': round(sum(event['bytes'] / (2 * event['sample_rate']) for event in window if event['name'] == 'audio_received'), 3),
                'interpretation': 'PCM duration is recorded transport volume, not connection time, human listening or billed cost.',
            },
            'publication': {
                'first_commit_correct': base_report.get('first_commit_correct'),
                'first_full_correct_revision': first_full['revision'] if first_full else None,
                'all_revision_commits_correct': base_report.get('all_revision_commits_correct'),
                'incorrect_commit_count': base_report.get('incorrect_commit_count', 0),
                'commit_assessments': commits,
            },
            'interaction': interaction_summary(window),
        },
        'transport': {'mode_at_report': session['mode'], 'used_modes': deepcopy(session.get('used_modes', []))},
        'task_response': deepcopy(task_response),
        'response_status': base_report.get('task_response_status', 'none'),
        'response_current': base_report.get('task_response_current', False),
        'checks': deepcopy(base_report.get('checks', [])),
        'human_review': {'status': 'pending', 'repair_turns': None, 'repair_seconds': None,
                         'spoken_consistency': None, 'business_interpretation': None},
        'boundaries': [
            'Timing covers explicit Begin through Finish/Timeout/Abandon, excluding setup. Browser clocks are not subtracted from server clocks.',
            'All unfinished, timed-out and abandoned trials are retained. Correct chart state is separate from successful submission and human interpretation.',
            'First correct partial publication is not first full task correctness; full_correct is evaluated on the complete published state.',
            'Observed counts are events, not inferred repair effort or user attention. The 60-second voice budget is unchanged.',
        ],
    }


def _attempt_row(report):
    identity, outcome = report['identity'], report['outcome']
    process, timing = report['process'], report['timing']
    card = process['interaction']['revision_cards']
    return {
        **identity, 'started_at': report['started_at'], 'status': outcome['status'],
        'terminal_reason': outcome['terminal_reason'], 'technical_completed': outcome['technical_completed'],
        'submitted_correct': outcome['submitted_correct'], 'elapsed_seconds': timing['elapsed_seconds'],
        'response_complete_current': outcome['response_complete_current'],
        'deliverables_complete': outcome['deliverables_complete'],
        'submitted_deliverables_complete': outcome['submitted_deliverables_complete'],
        'time_censored': timing['time_censored'],
        'first_full_correct_seconds': timing['first_full_correct_seconds'],
        'incorrect_commit_count': process['publication']['incorrect_commit_count'],
        'tool_calls': process['counts']['tool_started'], 'tool_failures': process['counts']['tool_failed'],
        'evidence_selections': process['counts']['evidence_selected'],
        'history_opens': process['counts']['history_open'],
        'recording_starts': process['counts']['recording_start'],
        'recording_ends': process['counts']['recording_end'],
        'saved_set_applications': process['interaction']['category_sets']['application_count'],
        'cards_generated': card['generated_count'], 'cards_displayed': card['displayed_count'],
        'cards_opened': card['detail_opened_count'], 'user_confirmed': card['user_confirmed_count'],
        'model_applied': card['model_applied_count'], 'task_response_status': report['response_status'],
        'human_review': 'pending', 'repair_turns': None, 'repair_seconds': None,
    }


def aggregate_reports(reports, participant_slots=None):
    """Each session is an attempt; the latest start is selected without outcome filtering."""
    all_attempts = sorted(deepcopy(reports), key=lambda report: (report['started_at'], report['identity']['session_id']))
    registrations = {(r['identity']['evidence_kind'], r['identity']['participant_id'], r['identity']['participant_slot'])
                     for r in all_attempts}
    for item in participant_slots or []:
        registrations.add((item['evidence_kind'], item['participant_id'], item['participant_slot']))
    grouped = defaultdict(list)
    for report in all_attempts:
        identity = report['identity']
        grouped[(identity['evidence_kind'], identity['participant_id'], identity['participant_slot'], identity['trial_id'])].append(report)
    selected = {key: attempts[-1] for key, attempts in grouped.items()}
    latest = list(selected.values())
    missing, participants = [], []
    condition_totals = defaultdict(lambda: {'assigned': 0, 'observed': 0, 'missing': 0,
                                           'technical_correct': 0, 'submitted_correct': 0,
                                           'response_complete_current': 0, 'submitted_deliverables_complete': 0,
                                           'timeout': 0, 'abandoned': 0, 'unfinished': 0,
                                           'elapsed_seconds_total': 0, 'elapsed_seconds_observed': 0})
    for kind, participant_id, slot in sorted(registrations):
        condition_summary = {}
        for condition in CONDITIONS:
            expected = [trial for trial in allocation_for(slot)['trials'] if trial['condition'] == condition]
            observed = [selected[(kind, participant_id, slot, trial['trial_id'])] for trial in expected
                        if (kind, participant_id, slot, trial['trial_id']) in selected]
            summary = {'assigned': len(expected), 'observed': len(observed), 'missing': len(expected) - len(observed),
                       'technical_correct': sum(r['outcome']['technical_completed'] for r in observed),
                       'submitted_correct': sum(r['outcome']['submitted_correct'] for r in observed),
                       'response_complete_current': sum(r['outcome']['response_complete_current'] for r in observed),
                       'submitted_deliverables_complete': sum(r['outcome']['submitted_deliverables_complete'] for r in observed),
                       'timeout': sum(r['outcome']['terminal_reason'] == 'timeout' for r in observed),
                       'abandoned': sum(r['outcome']['terminal_reason'] == 'abandoned' for r in observed),
                       'unfinished': sum(r['outcome']['terminal_reason'] is None for r in observed),
                       'elapsed_seconds_total': round(sum(r['timing']['elapsed_seconds'] for r in observed
                                                        if r['timing']['elapsed_seconds'] is not None), 3),
                       'elapsed_seconds_observed': sum(r['timing']['elapsed_seconds'] is not None for r in observed)}
            condition_summary[condition] = summary
            for key, value in summary.items():
                condition_totals[(kind, condition)][key] += value
            for trial in expected:
                if (kind, participant_id, slot, trial['trial_id']) not in selected:
                    missing.append({'participant_id': participant_id, 'evidence_kind': kind, **trial})
        direct, bound = (condition_summary[name] for name in CONDITIONS)
        complete_pair = direct['observed'] == bound['observed'] == 2 and not direct['unfinished'] and not bound['unfinished']
        participants.append({'participant_id': participant_id, 'participant_slot': slot, 'evidence_kind': kind,
                             'conditions': condition_summary,
                             'paired': {'complete_pair': complete_pair,
                                        'technical_correct_rate_difference': (bound['technical_correct'] - direct['technical_correct']) / 2 if complete_pair else None,
                                        'submitted_correct_rate_difference': (bound['submitted_correct'] - direct['submitted_correct']) / 2 if complete_pair else None,
                                        'submitted_deliverables_rate_difference': (bound['submitted_deliverables_complete'] - direct['submitted_deliverables_complete']) / 2 if complete_pair else None,
                                        'elapsed_seconds_difference': round(bound['elapsed_seconds_total'] - direct['elapsed_seconds_total'], 3)
                                            if complete_pair and direct['elapsed_seconds_observed'] == bound['elapsed_seconds_observed'] == 2 else None}})
    attempt_rows = []
    for report in all_attempts:
        row = _attempt_row(report)
        key = (row['evidence_kind'], row['participant_id'], row['participant_slot'], row['trial_id'])
        row.update(attempt_index=grouped[key].index(report) + 1, attempt_count=len(grouped[key]),
                   selected_latest=report['identity']['session_id'] == selected[key]['identity']['session_id'])
        attempt_rows.append(row)
    return {'protocol': PROTOCOL, 'attempt_count': len(all_attempts), 'assigned_trial_count': len(registrations) * 4,
            'all_attempts': all_attempts, 'latest_attempts': latest, 'attempt_rows': attempt_rows,
            'participants': participants, 'missing_trials': missing,
            'conditions': [{'evidence_kind': kind, 'condition': condition, **values}
                           for (kind, condition), values in sorted(condition_totals.items())],
            'selection_rule': 'Latest started attempt per participant/slot/assigned trial, including failures and unfinished attempts; never best score. All attempts remain exported.',
            'human_review': 'pending',
            'interpretation': 'Descriptive paired summaries only. Missing tasks remain explicit; local authored records and participant records are separate. Pair differences are not inferential statistics or evidence of method benefit.'}


def report_csv(report):
    """One row per actual attempt, including superseded attempts and failures."""
    output = StringIO(newline='')
    rows = report['attempt_rows']
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue()


def formal_allocation_for(slot):
    """Retain the existing counterbalance, with a distinct locked study contract."""
    plan = allocation_for(slot)
    plan['protocol'] = FORMAL_PROTOCOL
    for trial in plan['trials']:
        trial.update(protocol=FORMAL_PROTOCOL, materials_protocol=FORMAL_MATERIALS_PROTOCOL,
                     trial_id=f"study-{trial['trial_id']}",
                     task_id=f"study_{trial['family_id']}_{trial['variant_id']}",
                     mode='live_voice', voice_budget_seconds=VOICE_BUDGET_SECONDS,
                     voice_windows_per_trial=1, condition_locked=True)
        trial['material_sha256'] = content_sha256(formal_task_brief(trial['task_id']))
        trial['assignment_sha256'] = content_sha256(trial)
    return plan


def formal_allocation_table(count=30):
    table = allocation_table(count)
    table.update(protocol=FORMAL_PROTOCOL,
                 allocations=[formal_allocation_for(slot) for slot in range(1, count + 1)])
    table['assignment_sha256'] = content_sha256(table['allocations'])
    return table


def validate_formal_assignment(assignment, *, condition=None, mode=None):
    """Check the assignment at a runtime boundary without accepting relabeling."""
    expected = formal_allocation_for(assignment['participant_slot'])['trials'][assignment['trial_index'] - 1]
    if assignment != expected:
        raise ValueError('The formal trial assignment is fixed; prepare the assigned trial again.')
    if condition is not None and condition != expected['condition']:
        raise ValueError('The condition is locked for this formal trial.')
    if mode is not None and mode != 'live_voice':
        raise ValueError('Formal trials use the shared live_voice transport.')
    return deepcopy(expected)


def formal_manifest():
    """A reviewable candidate snapshot, never a software-generated approval."""
    manifest = formal_materials_manifest()
    manifest.update(
        allocation=formal_allocation_table(),
        conditions=list(CONDITIONS), mode='live_voice', time_limit_seconds=TIME_LIMIT_SECONDS,
        voice_window={
            'maximum_seconds': VOICE_BUDGET_SECONDS, 'maximum_connections': 1,
            'placement': 'After Begin and initial inspection, before Finish; participant starts explicitly.',
            'remaining_task_time': 'Offline inspection, manual chart operations and the written response; no second model window.',
            'interruption_required': False,
        },
        shared_capabilities={
            'voice_model': 'qwen3.8-omni-flash-realtime',
            'saved_sets': ['save_category_set', 'list_category_sets', 'apply_category_set'],
            'execution': 'Shared evidence-candidate resolution and revision compiler.',
            'history': 'Retained native history with exact outgoing archives; no claim of frozen native context.',
        },
        treatment='Visible, correctable evidence origin, current edit scope, and retained/released conditions.',
        primary_attempt_rule='First actually begun participant attempt per registered assigned trial; keep repeats and failures.',
        collection_status='pending_human_review',
        required_reviews={
            'materials_and_difficulty': 'pending', 'voice_window_feasibility_and_listening': 'pending',
            'intent_and_understanding_rubrics': 'pending',
            'meaningful_effect_and_precision_thresholds': 'pending',
            'consent_and_analysis_plan': 'pending',
        },
        analysis_plan={
            'primary_outcomes': ['terminal_intent_consistency'],
            'secondary_outcomes': ['interface_assisted_interpretation', 'repair_funnel',
                                   'interaction_cost_time', 'public_constraint_completion'],
            'descriptive_only': ['overlap_incidence', 'reference_dependence',
                                 'first_publication_consistent', 'window_expiry'],
            'estimand': 'Participant-level paired difference (bound_revision minus direct), two tasks per condition.',
            'uncertainty': 'Cluster bootstrap over participants with Manski-style lower/upper bounds for unknown outcomes.',
            'multiple_testing': 'Single primary outcome; no Holm adjustment.',
        },
    )
    manifest['manifest_sha256'] = content_sha256(manifest)
    return manifest


def formal_primary_attempts(records, registrations):
    """Join raw archives to the actual roster, including unscored and missing trials.

    `registrations` is an actual assignment roster, not thirty fabricated people.
    Only formal participant records with a real Begin can become primary. This
    table deliberately does not turn technical checks into intent/human scores.
    """
    roster = {(item['participant_id'], item['participant_slot']) for item in registrations}
    grouped = defaultdict(list)
    non_primary_records = []
    for record in records:
        session = record['session']
        assignment = session.get('assignment') or {}
        if (assignment.get('protocol') != FORMAL_PROTOCOL
                or session.get('evidence_kind') != 'participant'):
            non_primary_records.append(deepcopy(record))
            continue
        validate_formal_assignment(assignment, condition=session.get('condition'), mode=session['mode'])
        registration = (session['participant_id'], assignment['participant_slot'])
        if registration not in roster:
            raise ValueError('Formal participant records require an actual assignment-roster entry.')
        start = next((event for event in record.get('events', []) if event['name'] == 'trial_started'), None)
        end = next((event for event in record.get('events', []) if event['name'] == 'trial_finished'), None)
        grouped[(*registration, assignment['trial_id'])].append({
            'session_id': session['id'], 'participant_id': session['participant_id'],
            **deepcopy(assignment), 'evidence_kind': 'participant',
            'prepared_at': session['started_at'], 'began_at': start['at'] if start else None,
            'begin_event_index': start['index'] if start else None,
            'terminal_reason': end['reason'] if end else None,
            'status': end['reason'] if end else 'running' if start else 'ready',
            'report_available': record.get('report') is not None,
            'repeat_reason': session.get('repeat_reason'),
            'human_review': 'pending', 'revision_correct': None, 'understanding_correct': None,
        })
    assigned_rows, attempt_rows = [], []
    for participant_id, slot in sorted(roster):
        for assignment in formal_allocation_for(slot)['trials']:
            key = (participant_id, slot, assignment['trial_id'])
            attempts = sorted(grouped[key], key=lambda row: (row['began_at'] is None,
                              row['began_at'] or row['prepared_at'], row['session_id']))
            begun = [row for row in attempts if row['began_at'] is not None]
            primary = begun[0] if begun else None
            for row in attempts:
                number = begun.index(row) + 1 if row['began_at'] is not None else None
                row.update(attempt_index=number, selected_primary=row is primary,
                           attempt_role='primary' if row is primary else 'repeat' if number else 'prepared')
                attempt_rows.append(row)
            assigned_rows.append({
                'participant_id': participant_id, **deepcopy(assignment),
                'evidence_kind': 'participant',
                'primary_session_id': primary['session_id'] if primary else None,
                'primary_began_at': primary['began_at'] if primary else None,
                'primary_status': primary['status'] if primary else 'missing',
                'primary_report_available': primary['report_available'] if primary else False,
                'attempt_count': len(attempts), 'begun_attempt_count': len(begun),
                'repeat_session_ids': [row['session_id'] for row in begun[1:]],
                'missing_reason': None if primary else 'no_actual_begin' if attempts else 'no_archive',
                'human_review': 'pending', 'revision_correct': None, 'understanding_correct': None,
            })
    return {
        'protocol': FORMAL_PROTOCOL, 'registered_participant_count': len(roster),
        'assigned_trial_count': len(assigned_rows), 'attempt_count': len(attempt_rows),
        'assigned_rows': assigned_rows, 'attempt_rows': attempt_rows,
        'primary_attempts': [row for row in attempt_rows if row['selected_primary']],
        'missing_trials': [row for row in assigned_rows if row['primary_session_id'] is None],
        'all_records': deepcopy(records), 'non_primary_records': non_primary_records,
        'selection_rule': 'First actual trial_started in a formal participant archive per roster assignment; not latest, best, preparation time or local_authored.',
        'human_review': 'pending',
        'interpretation': 'An accounting table only. Missing, unscored, failed, unfinished and repeated attempts remain explicit; no research outcome is inferred.',
    }


def formal_assignment_csv(report):
    """One row per roster assignment, including assignments with no attempt."""
    output = StringIO(newline='')
    rows = report['assigned_rows']
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({**row, 'repeat_session_ids': '|'.join(row['repeat_session_ids'])} for row in rows)
    return output.getvalue()
