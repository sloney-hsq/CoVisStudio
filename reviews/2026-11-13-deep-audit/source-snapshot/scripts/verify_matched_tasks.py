"""Matched-task audit and authored tool paths, never participant/model results."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.business_tasks import EXPERIMENT_PROTOCOL, experiment_tasks
from backend.category_sets import CategorySets
from backend.charts import ChartStore
from backend.data import OlistData
from backend.oracle import category_rows
from backend.revisions import prepare_revision
from backend.study import (evaluate, phase_source, revision_case, revision_targets,
                           setup_operations, task_brief)
from backend.trace import Trace


def setup(task_id, data, directory):
    store, trace = ChartStore(data), Trace(directory)
    snapshots = {0: store.snapshot()}
    trace.record('session_started', task_id=task_id, kind='authored-matched-task-path', real_api_calls=0)
    for name, args in setup_operations(task_id, data):
        receipt = store.commit(store.prepare(name, args))
        trace.record('tool_committed', tool=name, arguments=args, actor='starter',
                     revision=receipt['state']['revision'], result=receipt['result'])
        snapshots[receipt['state']['revision']] = receipt['state']
    trace.save('starting-history.json', snapshots)
    trace.save('public-brief.json', task_brief(task_id))
    trace.record('request_accepted', text=task_brief(task_id)['goal'], actor='authored-script')
    return store, store.snapshot(), snapshots, trace


def commit(store, prepared, trace, tool, arguments):
    receipt = store.commit(prepared)
    trace.record('tool_committed', tool=tool, arguments=arguments, actor='authored-script',
                 revision=receipt['state']['revision'], result=receipt['result'])
    return receipt


def solve(task_id, store, snapshots, trace, condition):
    case = revision_case(task_id)
    ids = [f'v{number}' for number in case['targets']]
    source = dict(case['patch'])
    if condition == 'bound_revision':
        args = {'evidence': {'revision': 3, 'view_id': 'v1'}, 'view_ids': ids,
                'source_patch': source, 'member_action': case['action']}
        preview = prepare_revision(store, snapshots, args, condition)
        return commit(store, preview['prepared'], trace, 'apply_revision', args)
    if case['action'] == 'use_evidence':
        sets = CategorySets()
        saved = sets.save(snapshots, {'name': 'Earlier priority cohort', 'revision': 3, 'view_id': 'v1'})
        trace.record('category_set_saved', category_set=saved, actor='authored-script')
        args = {'set_id': saved['id'], 'view_ids': ids}
        return commit(store, sets.prepare_apply(store, args), trace, 'apply_category_set', args)
    if case['action'] == 'rerank':
        source['categories'] = None
    args = {'view_ids': ids, 'patch': {'source': source}}
    return commit(store, store.prepare('edit_charts', args), trace, 'edit_charts', args)


def finish(task_id, store, initial, trace, data):
    report = evaluate(task_id, initial, store.snapshot(), trace.events, data, [])
    trace.save('initial.json', initial)
    trace.save('final.json', store.snapshot())
    trace.save('report.json', report)
    return report


def matching_audit(data):
    """Evaluator-only structural and data checks; no human equivalence claim."""
    variants = []
    for brief in experiment_tasks():
        case = revision_case(brief['id'])
        old_source = phase_source(case, 0)
        current_source = phase_source(case, len(case['phases']) - 1)
        old_rows, current_rows = category_rows(data, old_source), category_rows(data, current_source)
        old_members = [row['label'] for row in old_rows]
        current_members = [row['label'] for row in current_rows]
        evaluation_rows = category_rows(data, {**current_source, 'categories': old_members, 'top_n': None})
        fields = ['metric'] if case['action'] == 'keep_current' else ['categories', 'top_n']
        variants.append({
            'task_id': brief['id'], 'family_id': brief['family_id'], 'variant_id': brief['variant_id'],
            'structural': {'view_count': 3, 'history_phase_count': len(case['phases']),
                           'initial_commit_count': len(case['phases']) * 3, 'member_count': 3,
                           'target_view_count': len(case['targets']), 'target_view_numbers': case['targets'],
                           'requested_source_fields': fields, 'selection_operation': case['action'],
                           'minimum_chart_commits': 1, 'response_field_count': 4,
                           'reference_period_days': (datetime.fromisoformat(old_source['end']) - datetime.fromisoformat(old_source['start'])).days,
                           'current_period_days': (datetime.fromisoformat(current_source['end']) - datetime.fromisoformat(current_source['start'])).days,
                           'goal_word_count': len(brief['goal'].split())},
            'data': {'reference_region': old_source['region'], 'current_region': current_source['region'],
                     'reference_members': old_members, 'current_ranked_members': current_members,
                     'cohort_overlap_count': len(set(old_members) & set(current_members)),
                     'reference_rows': old_rows, 'current_ranked_rows': current_rows,
                     'reference_members_in_current_scope': evaluation_rows,
                     'minimum_review_denominator': min(row['reviewed_orders'] for row in old_rows + current_rows + evaluation_rows),
                     'minimum_delivery_denominator': min(row['delivery_order_count'] for row in old_rows + current_rows + evaluation_rows)},
        })
    pairs = []
    for family in ('01', '02', '03', '04'):
        a, b = [entry for entry in variants if entry['family_id'] == family]
        differences = [key for key in a['structural'] if a['structural'][key] != b['structural'][key]]
        scope_counts = [sum(row['orders'] for row in entry['data']['reference_members_in_current_scope']) for entry in (a, b)]
        overlap_equal = a['data']['cohort_overlap_count'] == b['data']['cohort_overlap_count']
        valid_denominators = all(entry['data'][key] > 0 for entry in (a, b)
                                 for key in ('minimum_review_denominator', 'minimum_delivery_denominator'))
        pairs.append({'family_id': family, 'structural_match': not differences,
                      'different_structural_fields': differences, 'cohort_overlap_matched': overlap_equal,
                      'positive_denominators': valid_denominators,
                      'current_cohort_order_count_ratio': round(max(scope_counts) / min(scope_counts), 4),
                      'passed': not differences and overlap_equal and valid_denominators})
    return {'protocol': EXPERIMENT_PROTOCOL, 'variants': variants, 'pairs': pairs,
            'all_pairs_passed': all(pair['passed'] for pair in pairs),
            'human_difficulty_equivalence': 'not_established',
            'boundary': 'Structure, prompt length, cohort overlap and data support are matched; human difficulty and business interpretations require participant evidence. Raw order counts are group counts and may overlap across categories.'}


def main():
    output = ROOT / 'traces' / 'matched-task-runs' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    data = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    paths, errors = [], []
    try:
        for brief in experiment_tasks():
            task_id = brief['id']
            for condition in ('direct', 'bound_revision'):
                store, initial, snapshots, trace = setup(task_id, data, output / task_id / condition)
                solve(task_id, store, snapshots, trace, condition)
                report = finish(task_id, store, initial, trace, data)
                paths.append({'task_id': task_id, 'condition': condition,
                              'technical_completed': report['technical_completed'],
                              'all_revision_commits_correct': report['all_revision_commits_correct'],
                              'interpretation_status': report['interpretation_status']})
            for error in ('unchanged_or_wrong_cohort', 'scope_or_period_error'):
                store, initial, snapshots, trace = setup(task_id, data, output / task_id / error)
                if error == 'unchanged_or_wrong_cohort':
                    if brief['family_id'] in ('01', '03'):
                        source, ids = {'categories': None, 'top_n': 3, 'rank_by': 'orders'}, ['v2', 'v3']
                    elif brief['family_id'] == '02':
                        source = {'categories': list(initial['views'][0]['source']['categories']), 'top_n': None}
                        ids = ['v1', 'v2', 'v3']
                    else:
                        source, ids = {'metric': 'low_review_rate'}, ['v1']
                    args = {'view_ids': ids, 'patch': {'source': source}}
                    commit(store, store.prepare('edit_charts', args), trace, 'edit_charts', args)
                else:
                    solve(task_id, store, snapshots, trace, 'direct')
                    case = revision_case(task_id)
                    if brief['family_id'] == '02':
                        # Correct visible new members with the wrong fixed selection rule.
                        source = {'categories': [row['label'] for row in store.state['views'][0]['data']['rows']], 'top_n': None}
                        ids = ['v1', 'v2', 'v3']
                    elif brief['family_id'] == '03':
                        source, ids = {'start': '2017-01-01', 'end': '2017-04-01'}, ['v2', 'v3']
                    else:
                        source, ids = {'metric': 'revenue'}, ['v3'] if brief['family_id'] == '04' else ['v1']
                    args = {'view_ids': ids, 'patch': {'source': source}}
                    commit(store, store.prepare('edit_charts', args), trace, 'edit_charts', args)
                report = finish(task_id, store, initial, trace, data)
                errors.append({'task_id': task_id, 'error': error, 'detected': not report['technical_completed']})
        audit = matching_audit(data)
        summary = {'protocol': EXPERIMENT_PROTOCOL, 'real_api_calls': 0, 'paths': paths,
                   'counterexamples': errors, 'matching': audit, 'human_review': 'pending',
                   'all_passed': all(path['technical_completed'] and path['all_revision_commits_correct'] for path in paths)
                                 and all(error['detected'] for error in errors) and audit['all_pairs_passed']}
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        (output / 'matching-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
        assert summary['all_passed'], output
        print(json.dumps({'paths_passed': len(paths), 'errors_detected': len(errors), 'matched_pairs': len(audit['pairs']), 'output': str(output)}))
    finally:
        data.close()


if __name__ == '__main__':
    main()
