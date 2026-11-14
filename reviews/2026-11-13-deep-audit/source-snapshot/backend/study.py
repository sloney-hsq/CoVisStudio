"""Public task briefs and private outcome checks; no model judge or hidden repair."""
from copy import deepcopy

from .business_tasks import (BUSINESS_PROTOCOL, EXPERIMENT_PROTOCOL, business_case,
                             business_tasks, experiment_case, experiment_tasks)

METRICS = ['orders', 'low_review_rate', 'avg_delivery_days']
LABELS = ['Order volume', 'Low review rate', 'Delivery time']
BASE_SOURCE = {'metric': 'orders', 'dimension': 'category', 'region': 'SP',
               'start': '2017-01-01', 'end': '2018-01-01', 'status': 'delivered',
               'categories': None, 'top_n': 3, 'rank_by': 'orders'}

FAMILIES = [
    ('region', 'A new regional perspective', 'Move the charts to {regions}. Keep the original three categories, metrics and 2017 dates.'),
    ('rerank', 'Choose a new comparison set', 'Move the charts to {regions}. Select the three categories with most delivered orders in each target region, then use those categories for its measures. Keep the 2017 dates.'),
    ('quarter', 'A closer look at the quarter', 'Use {periods}. Keep the original categories, SP region and metrics.'),
    ('quarter_rank', 'Reconsider the leading categories', 'Use {periods} and select the three categories with most delivered orders in each target period. Keep SP and the existing metrics.'),
    ('metric', 'Change the analytical lens', 'Change chart 1 to revenue, chart 2 to delivery time and chart 3 to low review rate. Use {regions}; preserve the original categories and dates.'),
    ('scope', 'Refine the comparison', 'Move the charts to {regions} and use {periods}. Preserve the original three categories and metrics.'),
]


def legacy_tasks():
    entries = [{'id': 'starter', 'title': 'Service quality', 'kind': 'explore',
                'description': 'Explore order volume, customer reviews and delivery time.',
                'goal': 'Build a dashboard that helps an operations team compare service quality. Choose what to investigate next.',
                'initial': 'SP · 2017 · Delivered orders · Same three categories'}]
    for key, title, brief in FAMILIES:
        for kind in ('independent', 'linked'):
            region = 'MG in all three charts' if kind == 'linked' else 'MG in chart 1, RJ in chart 2 and PR in chart 3'
            period = 'January–March 2017 in all three charts' if kind == 'linked' else 'January–March in chart 1, April–June in chart 2 and July–September 2017 in chart 3'
            entries.append({'id': f'{key}_{kind}', 'title': title, 'kind': kind,
                            'description': 'Shared analytical scope' if kind == 'linked' else 'Separate analytical scopes',
                            'goal': brief.format(regions=region, periods=period),
                            'initial': 'SP · 2017 · Delivered orders · Same three categories'})
    return entries


def starter_operations(data):
    members = [row['label'] for row in data.query(BASE_SOURCE)['rows']]
    colors = ['#247c70', '#c78c52', '#596db2']
    return [
        ('create_chart', {'title': LABELS[i], 'chart_type': 'bar',
                          'source': {**BASE_SOURCE, 'metric': metric, 'categories': members, 'top_n': None},
                          'style': {'color': colors[i], 'show_labels': True, 'sort': 'source'}})
        for i, metric in enumerate(METRICS)
    ]


def expected_sources(task_id, initial, data):
    family, kind = task_id.rsplit('_', 1)
    result = [deepcopy(v['source']) for v in initial['views']]
    regions = ['MG'] * 3 if kind == 'linked' else ['MG', 'RJ', 'PR']
    periods = [('2017-01-01', '2017-04-01')] * 3 if kind == 'linked' else [
        ('2017-01-01', '2017-04-01'), ('2017-04-01', '2017-07-01'), ('2017-07-01', '2017-10-01')]
    for i, source in enumerate(result):
        if family in ('region', 'rerank', 'metric', 'scope'):
            source['region'] = regions[i]
        if family in ('quarter', 'quarter_rank', 'scope'):
            source['start'], source['end'] = periods[i]
        if family == 'metric':
            source['metric'] = ['revenue', 'avg_delivery_days', 'low_review_rate'][i]
        if family in ('rerank', 'quarter_rank'):
            source['categories'] = None
            source['top_n'] = 3
            source['rank_by'] = 'orders'
    return result


def evaluate_legacy(task_id, initial, final, events, data, reviews):
    checks = []
    if task_id and task_id != 'starter':
        expected = expected_sources(task_id, initial, data)
        actual = {v['id']: v for v in final['views']}
        for start_view, target in zip(initial['views'], expected):
            chart = actual.get(start_view['id'])
            checks.append({'name': f"Chart {start_view['number']} retained", 'passed': chart is not None})
            if chart is None:
                continue
            for field in ('metric', 'dimension', 'region', 'start', 'end', 'status'):
                checks.append({'name': f"Chart {chart['number']} · {field}",
                               'passed': chart['source'][field] == target[field],
                               'expected': target[field], 'actual': chart['source'][field]})
            required = data.query(target)['rows']
            expected_rows = {r['label']: r['value'] for r in required}
            actual_rows = {r['label']: r['value'] for r in chart['data']['rows']}
            correct = expected_rows.keys() == actual_rows.keys() and all(
                actual_rows[k] == value if value is None else actual_rows[k] is not None and abs(actual_rows[k] - value) < 1e-7
                for k, value in expected_rows.items())
            checks.append({'name': f"Chart {chart['number']} · comparison members and values", 'passed': correct,
                           'expected': expected_rows, 'actual': actual_rows})
    counts = {name: sum(e['name'] == name for e in events) for name in
              ['request_accepted', 'tool_started', 'tool_committed', 'tool_failed', 'tool_superseded', 'undo', 'text_focus', 'text_blur', 'playback_start', 'playback_end']}
    return {'task_id': task_id, 'revision': final['revision'], 'completed': all(c['passed'] for c in checks) if checks else None,
            'checks': checks, 'counts': counts,
            'elapsed_seconds': round(events[-1]['server_ms'] / 1000, 2) if events else 0,
            'review_status': 'pending', 'reviews': reviews,
            'limitations': ['Outcome checks use task constraints and database recomputation; they do not grade spoken semantics.',
                           'Human intent, misunderstanding, exploratory edits and rework require review.',
                           'Exported clocks are separate; overlapping activities are not summed.',
                           'An unfinished task remains in the report. No model performance claim follows from a local test.']}


# The case specification and expected sources are evaluator-side material.
# Only tasks()/task_brief() are exposed to the workspace and provider context.
REVISION_PROTOCOL = 'covis-revision-0.1'


def _case(case_id, title, instruction, *, family, split='development',
          phases=None, targets=(1, 2, 3), action='use_evidence', patch=None,
          evidence_phase=0, evidence_indices=None, resolution=None):
    return {'id': case_id, 'title': title, 'instruction': instruction, 'family': family,
            'split': split, 'phases': phases or [{'region': 'SP'}, {'region': 'MG'}],
            'targets': list(targets), 'action': action, 'patch': patch or {},
            'evidence_phase': evidence_phase, 'evidence_indices': evidence_indices,
            'resolution': resolution}


REVISION_CASES = [
    _case('rev_dev_01', 'Carry earlier categories into a new region',
          'Keep the three categories from the first SP chart. Analyze them in the current MG region in all three views. Keep the current dates and delivered-order scope.',
          family='historical_objects'),
    _case('rev_dev_02', 'Change the measure, retain the evidence',
          'In chart 2, use the categories from the first SP chart and show revenue in the current MG region. Leave charts 1 and 3 unchanged.',
          family='metric_revision', targets=(2,), patch={'metric': 'revenue'}),
    _case('rev_dev_03', 'Release the fixed comparison set',
          'Stop keeping the original categories. Re-select the three categories with most orders in the current MG region for all views. Keep dates and measures.',
          family='release_constraint', phases=[{'region': 'SP'}, {'region': 'MG', 'cohort': 'previous'}],
          action='rerank', patch={'top_n': 3, 'rank_by': 'orders'}),
    _case('rev_dev_04', 'Revise one view only',
          'Use the first SP chart\'s categories in chart 2 only. Keep its current MG data scope and leave the other views untouched.',
          family='local_scope', targets=(2,)),
    _case('rev_dev_05', 'Resolve an unspecified historical reference',
          'Keep those three categories and leave MG unchanged. Resolve which visible version is intended before changing all three views.',
          family='reference_clarification', resolution={'phase': 0, 'answer': 'The three from the first SP version.'}),
    _case('rev_dev_06', 'Stable evidence, shorter time range',
          'Use January through March 2017 in all three views. Keep the current SP categories and measures.',
          family='stable_control', phases=[{'region': 'SP'}], action='keep_current',
          patch={'start': '2017-01-01', 'end': '2017-04-01'}),
    _case('rev_hold_01', 'Earlier quarter, current quarter data',
          'Compare the categories selected in the first-quarter SP version using the current second-quarter SP data in all three views.',
          family='historical_objects', split='heldout',
          phases=[{'region': 'SP', 'end': '2017-04-01'}, {'region': 'SP', 'start': '2017-04-01', 'end': '2017-07-01'}]),
    _case('rev_hold_02', 'Reuse a subset of an earlier comparison',
          'From the first SP five-category chart, keep its first and third categories. Use those two in the current MG analysis across all three views.',
          family='historical_objects', split='heldout', evidence_indices=[0, 2],
          phases=[{'region': 'SP', 'top_n': 5}, {'region': 'MG'}]),
    _case('rev_hold_03', 'Reuse a differently ranked historical set',
          'Use the categories from the first SP revenue-ranked version for all current MG views. Keep the current measures, dates and order status.',
          family='historical_objects', split='heldout',
          phases=[{'region': 'SP', 'rank_by': 'revenue'}, {'region': 'MG'}]),
    _case('rev_hold_04', 'Reference the middle version',
          'Use the four categories from the middle PR version, not the first SP or latest MG version. Keep the current MG scope for all views.',
          family='historical_objects', split='heldout', evidence_phase=1,
          phases=[{'region': 'SP'}, {'region': 'PR', 'top_n': 4}, {'region': 'MG'}]),
    _case('rev_hold_05', 'Keep old objects and revise the current period',
          'Retain the first SP chart\'s categories, keep MG, and use July through September 2017 in all views.',
          family='historical_objects', split='heldout',
          patch={'start': '2017-07-01', 'end': '2017-10-01'}),
    _case('rev_hold_06', 'Change one measure on historical objects',
          'Change chart 3 to low-review rate for the first SP version\'s categories. Keep its current MG scope; leave the other two views untouched.',
          family='metric_revision', split='heldout', targets=(3,), patch={'metric': 'low_review_rate'}),
    _case('rev_hold_07', 'Explicitly change the selection rule',
          'Release the fixed categories and select the three leading MG categories by revenue in all three views. Preserve the displayed measures and dates.',
          family='release_constraint', split='heldout', action='rerank',
          phases=[{'region': 'SP'}, {'region': 'MG', 'cohort': 'previous'}],
          patch={'top_n': 3, 'rank_by': 'revenue'}),
    _case('rev_hold_08', 'Expand the selection after releasing it',
          'Do not keep the fixed three. Select the five MG categories with most orders in all views, keeping the current measures and dates.',
          family='release_constraint', split='heldout', action='rerank',
          phases=[{'region': 'SP'}, {'region': 'MG', 'cohort': 'previous'}],
          patch={'top_n': 5, 'rank_by': 'orders'}),
    _case('rev_hold_09', 'Preserve one view as a reference',
          'Leave chart 1 as it is. In charts 2 and 3, compare the first SP version\'s categories using the current MG scope.',
          family='local_scope', split='heldout', targets=(2, 3)),
    _case('rev_hold_10', 'Keep each view\'s own regional scope',
          'Use the first SP version\'s categories in chart 2, keeping chart 2 in RJ. Do not change chart 1 in MG or chart 3 in PR.',
          family='local_scope', split='heldout', targets=(2,),
          phases=[{'region': 'SP'}, {'regions': ['MG', 'RJ', 'PR']}]),
    _case('rev_hold_11', 'Clarify a reference without assuming the older set',
          'Use those three categories and change chart 2 to revenue. Resolve the intended version, keep MG, and leave charts 1 and 3 alone.',
          family='reference_clarification', split='heldout', targets=(2,), evidence_phase=1,
          patch={'metric': 'revenue'}, resolution={'phase': 1, 'answer': 'The three in the current MG version.'}),
    _case('rev_hold_12', 'Stable evidence, explicit measure change',
          'Change chart 1 from orders to revenue. Keep the same SP categories and all other conditions and views.',
          family='stable_control', split='heldout', phases=[{'region': 'SP'}],
          targets=(1,), action='keep_current', patch={'metric': 'revenue'}),
]


def revision_case(task_id):
    if task_id.startswith('exp_'):
        return experiment_case(task_id)
    if task_id.startswith('biz_'):
        return business_case(task_id)
    return deepcopy(next(case for case in REVISION_CASES if case['id'] == task_id))


def tasks():
    return [legacy_tasks()[0]] + business_tasks()


def diagnostic_tasks():
    return [
        {'id': case['id'], 'title': case['title'], 'kind': case['family'],
         'split': case['split'], 'description': case['instruction'], 'goal': case['instruction'],
         'initial': 'Real Olist chart history, followed by the current comparison',
         'protocol': REVISION_PROTOCOL}
        for case in REVISION_CASES
    ]


def task_brief(task_id):
    return next(task for task in tasks() + experiment_tasks() + diagnostic_tasks() + legacy_tasks() if task['id'] == task_id)


def phase_source(case, phase_index, view_index=0):
    phase = case['phases'][phase_index]
    source = {**BASE_SOURCE, **{key: value for key, value in phase.items() if key not in ('cohort', 'regions')}}
    if 'regions' in phase:
        source['region'] = phase['regions'][view_index]
    return source


def setup_operations(task_id, data):
    """Authored starting history, never a claimed model-generated trajectory."""
    if not task_id.startswith(('rev_', 'biz_', 'exp_')):
        return starter_operations(data)
    case = revision_case(task_id)
    operations, previous = [], None
    for phase_index, phase in enumerate(case['phases']):
        phase_members = []
        for view_index in range(3):
            source = phase_source(case, phase_index, view_index)
            selected = previous[view_index] if phase.get('cohort') == 'previous' else [r['label'] for r in data.query(source)['rows']]
            phase_members.append(selected)
            scope = {key: source[key] for key in ('region', 'start', 'end', 'status', 'rank_by')}
            scope.update(categories=selected, top_n=None)
            if phase_index == 0:
                operations.append(('create_chart', {'title': LABELS[view_index], 'chart_type': 'bar',
                    'source': {**source, **scope, 'metric': METRICS[view_index]},
                    'style': {'color': ['#247c70', '#c78c52', '#596db2'][view_index], 'show_labels': True}}))
            else:
                operations.append(('edit_charts', {'view_ids': [f'v{view_index + 1}'], 'patch': {'source': scope}}))
        previous = phase_members
    return operations


def evidence_for_case(task_id, data):
    """Evaluator reference, not added to public briefs or model context."""
    from .oracle import members
    case = revision_case(task_id)
    phase = case['evidence_phase']
    selected = members(data, phase_source(case, phase))
    if case['evidence_indices'] is not None:
        selected = [selected[i] for i in case['evidence_indices']]
    return {'revision': (phase + 1) * 3, 'view_id': 'v1', 'members': selected}


def revision_targets(task_id, initial, data):
    """Build private target source specifications without the runtime query code."""
    case = revision_case(task_id)
    evidence = evidence_for_case(task_id, data)
    sources = {view['id']: deepcopy(view['source']) for view in initial['views']}
    for number in case['targets']:
        source = sources[f'v{number}']
        source.update(case['patch'])
        if case['action'] == 'use_evidence':
            source.update(categories=evidence['members'], top_n=None)
        elif case['action'] == 'rerank':
            source.update(categories=None, top_n=case['patch']['top_n'], rank_by=case['patch']['rank_by'])
    return sources


def _state_checks(case, initial, observed, targets, data, view_ids=None, previous=None):
    from .oracle import category_rows, numeric_rows_equal
    checks = []
    actual = {v['id']: v for v in observed['views']}
    old = {v['id']: v for v in initial['views']}
    prior = {v['id']: v for v in previous['views']} if previous is not None else None
    selected = set(view_ids) if view_ids is not None else set(old)
    if view_ids is None:
        checks.append({'name': 'Stable chart membership', 'passed': actual.keys() == old.keys()})
    intended = {f'v{number}' for number in case['targets']}
    for view_id in sorted(selected):
        view = actual.get(view_id)
        checks.append({'name': f'{view_id} retained', 'passed': view is not None})
        if view_id not in old:
            checks.append({'name': f'{view_id} belongs to the requested workspace', 'passed': False})
            continue
        if view is None:
            continue
        if view_id not in intended:
            checks.append({'name': f'{view_id} untouched', 'passed': view == old[view_id]})
            continue
        source = targets[view_id]
        for field, value in source.items():
            observed_value = view['source'].get(field)
            if prior is not None and view_id in prior and observed_value == prior[view_id]['source'].get(field):
                continue
            # These tasks require the same category members, not a specific display order.
            matches = (set(observed_value or []) == set(value)
                       if field == 'categories' and value is not None else observed_value == value)
            checks.append({'name': f'{view_id} source.{field}', 'passed': matches,
                           'expected': value, 'actual': observed_value})
        checks.append({'name': f'{view_id} members, values and denominators',
                       'passed': numeric_rows_equal(view['data']['rows'], category_rows(data, view['source'] if prior is not None else source))})
        if case.get('preserve_presentation', True):
            for field in ('style', 'chart_type'):
                checks.append({'name': f'{view_id} {field} retained', 'passed': view[field] == old[view_id][field]})
    return checks


def _reference_resolved(case, events):
    if case['resolution'] is None:
        return True
    revision = (case['resolution']['phase'] + 1) * 3
    selected = None
    for event in events:
        if event['name'] == 'evidence_selected':
            selected = event.get('evidence')
        if event['name'] in ('clarification_answer', 'reference_resolved') and event.get('revision') == revision:
            return True
    return (selected or {}).get('revision') == revision


def evaluate_revision(task_id, initial, final, events, data, reviews):
    case = revision_case(task_id)
    targets = revision_targets(task_id, initial, data)
    checks = _state_checks(case, initial, final, targets, data)
    resolved = _reference_resolved(case, events)
    if case['resolution']:
        checks.append({'name': 'Reference choice documented', 'passed': resolved})
    requests = [i for i, e in enumerate(events)
                if e['name'] in ('request_accepted', 'revision_request_accepted')
                or task_id.startswith('exp_') and e['name'] == 'trial_started']
    start = requests[0] if requests else len(events)
    replay = deepcopy(initial)
    commits, before_request, unchanged_restores = [], 0, 0
    for index, event in enumerate(events):
        if event['name'] not in ('tool_committed', 'undo', 'restore') or event.get('actor') == 'starter' or event['revision'] <= initial['revision']:
            continue
        if index < start:
            before_request += 1
        previous = deepcopy(replay)
        views = {view['id']: view for view in replay['views']}
        if event['name'] in ('undo', 'restore'):
            restored = {view['id']: view for view in event['state']['views']}
            ids = [view_id for view_id in views.keys() | restored.keys() if views.get(view_id) != restored.get(view_id)]
            replay = deepcopy(event['state'])
            if not ids:
                unchanged_restores += 1
                continue
        else:
            result = event['result']
            ids = result.get('changed_view_ids', [])
            for view in result.get('views', []):
                views[view['id']] = deepcopy(view)
            if result.get('tool') == 'remove_charts':
                for view_id in ids:
                    views.pop(view_id, None)
            replay['views'] = list(views.values())
            replay['revision'] = event['revision']
        if index >= start:
            commit_checks = _state_checks(case, initial, replay, targets, data, ids, previous)
            # A clarification must precede a publication, not be supplied retroactively.
            known_reference = _reference_resolved(case, events[:index + 1])
            full_correct = all(check['passed'] for check in _state_checks(case, initial, replay, targets, data)) and known_reference
            commits.append({'revision': event['revision'], 'event_index': event.get('index', index), 'event': event['name'],
                            'server_ms': event['server_ms'], 'full_correct': full_correct,
                            'changed_view_ids': ids,
                            'correct': bool(ids) and all(c['passed'] for c in commit_checks) and known_reference,
                            'failed_checks': [c['name'] for c in commit_checks if not c['passed']]})
    completed = all(check['passed'] for check in checks)
    wrong = [commit for commit in commits if not commit['correct']]
    first_full = next((commit for commit in commits if commit['full_correct']), None)
    counts = {name: sum(event['name'] == name for event in events) for name in (
        'request_accepted', 'tool_started', 'tool_committed', 'tool_failed', 'tool_superseded',
        'revision_proposed', 'revision_applied', 'evidence_selected', 'undo', 'restore', 'playback_start', 'playback_end')}
    return {'task_id': task_id, 'protocol': REVISION_PROTOCOL, 'split': case['split'], 'family': case['family'],
            'revision': final['revision'], 'completed': completed, 'checks': checks,
            'first_commit_correct': commits[0]['correct'] if commits else None,
            'first_full_correct_revision': first_full['revision'] if first_full else None,
            'first_full_correct_event_index': first_full['event_index'] if first_full else None,
            'all_revision_commits_correct': not wrong if commits else None,
            'recovered_after_error': completed and bool(wrong), 'commit_assessments': commits,
            'incorrect_commit_count': len(wrong), 'pre_revision_commits_not_scored': before_request,
            'unchanged_restores_not_scored': unchanged_restores,
            'counts': counts, 'elapsed_seconds': round(events[-1]['server_ms'] / 1000, 2) if events else 0,
            'review_status': 'pending', 'spoken_consistency': None, 'repair_turns': None, 'repair_seconds': None,
            'reviews': reviews, 'oracle': 'Independent SQL over raw Olist CSV tables; no runtime query reuse.',
            'limitations': [
                'Authored fixtures verify execution and scoring, not model understanding or user benefit.',
                'Commit scoring assumes one specified revision episode; accepted earlier goals need separate episode boundaries.',
                'Partial updates check changed source fields and actual-source numbers; final completeness is checked separately.',
                'Publications before the revision request are not retroactively marked wrong.',
                'Reference clarification is documented by an explicit selection or coded answer, never inferred from the final chart.',
                'Speech semantics, error blocking, repair effort and human interpretation remain pending review.',
            ]}


def evaluate(task_id, initial, final, events, data, reviews, task_response=None):
    if task_id and task_id.startswith(('biz_', 'exp_')):
        report = evaluate_revision(task_id, initial, final, events, data, reviews)
        response = deepcopy(task_response) if task_response is not None else None
        submitted = bool(response and all(response.get(field, '').strip() for field in
                         ('conclusion', 'rationale', 'object_origin', 'calculation_scope')))
        recorded_revision = response.get('revision') if response is not None else None
        revision_mismatch = recorded_revision != final['revision'] if response is not None else None
        response_status = ('none' if response is None else 'incomplete' if not submitted
                           else 'stale' if revision_mismatch else 'current')
        report.update(protocol=EXPERIMENT_PROTOCOL if task_id.startswith('exp_') else BUSINESS_PROTOCOL,
                      technical_completed=report['completed'],
                      completion_basis='Required chart/source/numeric outcomes only; business interpretation requires human review.',
                      interpretation_status='pending', business_conclusion_correct=None,
                      understanding_correct=None, task_response=response,
                      task_response_submitted=submitted, task_response_status=response_status,
                      task_response_current=response_status == 'current',
                      task_response_recorded_revision=recorded_revision,
                      task_response_final_revision=final['revision'],
                      task_response_revision_mismatch=revision_mismatch)
        if task_id.startswith('exp_'):
            brief = task_brief(task_id)
            report.update(family_id=brief['family_id'], variant_id=brief['variant_id'])
        report['limitations'].extend([
            'completed is a technical-completion alias; it does not approve the participant conclusion or rationale.',
            'Participant statements about object origin and calculation scope are recorded verbatim, not inferred from charts.',
            'A populated response remains submitted after edits, but is current only when its recorded revision matches the evaluated chart revision.',
            'Business recommendations have no single gold decision; human interpretation and evidence use remain pending.',
            'Eight minutes is the planned task limit; the separate sixty-second voice connection cap remains a development budget.',
        ])
        return report
    if task_id and task_id.startswith('rev_'):
        return evaluate_revision(task_id, initial, final, events, data, reviews)
    return evaluate_legacy(task_id, initial, final, events, data, reviews)
