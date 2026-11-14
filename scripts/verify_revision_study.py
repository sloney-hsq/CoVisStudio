"""Real-Olist reference trajectories and scorer counterexamples; no model calls."""
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.charts import ChartStore
from backend.data import OlistData
from backend.study import (REVISION_CASES, REVISION_PROTOCOL, evidence_for_case,
                           evaluate_revision, revision_case, revision_targets,
                           setup_operations)
from backend.trace import Trace


def start_case(task_id, data, directory):
    store, trace = ChartStore(data), Trace(directory)
    snapshots = {0: store.snapshot()}
    trace.record('session_started', kind='authored-local-reference', task_id=task_id,
                 paid_api_calls=0, human_review='pending')
    for name, args in setup_operations(task_id, data):
        receipt = store.commit(store.prepare(name, args))
        trace.record('tool_committed', tool=name, arguments=args, actor='starter',
                     revision=receipt['state']['revision'], result=receipt['result'])
        snapshots[receipt['state']['revision']] = receipt['state']
    initial = store.snapshot()
    trace.save('starting-history.json', snapshots)
    trace.save('initial.json', initial)
    trace.record('request_accepted', text=revision_case(task_id)['instruction'], epoch=1)
    return store, initial, trace


def publish(store, trace, view_ids, source):
    args = {'view_ids': view_ids, 'patch': {'source': source}}
    receipt = store.commit(store.prepare('edit_charts', args))
    trace.record('tool_committed', tool='edit_charts', arguments=args,
                 actor='authored-reference', revision=receipt['state']['revision'], result=receipt['result'])
    return receipt


def correct_edits(task_id, store, initial, trace, data):
    case = revision_case(task_id)
    if case['resolution']:
        trace.record('evidence_selected', evidence=evidence_for_case(task_id, data),
                     actor='authored-reference', note='Scripted choice, not a human answer.')
    targets = revision_targets(task_id, initial, data)
    for number in case['targets']:
        publish(store, trace, [f'v{number}'], targets[f'v{number}'])


def finish(task_id, store, initial, trace, data):
    report = evaluate_revision(task_id, initial, store.snapshot(), trace.events, data, [])
    trace.save('final.json', store.snapshot())
    trace.save('report.json', report)
    return report


def main():
    output = ROOT / 'traces' / 'revision-study-runs' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=True)
    data = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    results, failures = [], []
    try:
        for case in REVISION_CASES:
            store, initial, trace = start_case(case['id'], data, output / case['id'])
            correct_edits(case['id'], store, initial, trace, data)
            report = finish(case['id'], store, initial, trace, data)
            results.append({'task_id': case['id'], 'split': case['split'], 'family': case['family'],
                            'completed': report['completed'], 'first_commit_correct': report['first_commit_correct'],
                            'reference': evidence_for_case(case['id'], data),
                            'current_members': initial['views'][0]['data']['selection']['members'],
                            'review_status': report['review_status']})

        # These are deliberately wrong publications, not observed model failures.
        for label, task_id in [('current_members', 'rev_dev_01'), ('region_rollback', 'rev_dev_01'),
                               ('locked_old_rule', 'rev_dev_03'), ('scope_expansion', 'rev_dev_04'),
                               ('wrong_values', 'rev_dev_01'), ('wrong_then_recovered', 'rev_dev_01')]:
            store, initial, trace = start_case(task_id, data, output / f'counterexample-{label}')
            target = revision_targets(task_id, initial, data)['v1']
            if label in ('current_members', 'wrong_then_recovered'):
                publish(store, trace, ['v1', 'v2', 'v3'], {'categories': initial['views'][0]['source']['categories'], 'top_n': None})
            elif label == 'region_rollback':
                publish(store, trace, ['v1', 'v2', 'v3'], {'categories': target['categories'], 'top_n': None, 'region': 'SP'})
            elif label == 'locked_old_rule':
                publish(store, trace, ['v1', 'v2', 'v3'], {'categories': initial['views'][0]['source']['categories'], 'top_n': None})
            elif label == 'scope_expansion':
                members = evidence_for_case(task_id, data)['members']
                publish(store, trace, ['v1', 'v2', 'v3'], {'categories': members, 'top_n': None})
            elif label == 'wrong_values':
                correct_edits(task_id, store, initial, trace, data)
                # Corrupt an observed artifact only; production tools cannot set values.
                store.state['views'][0]['data']['rows'][0]['value'] += 1
                trace.record('injected_artifact_corruption', field='views[0].data.rows[0].value', delta=1,
                             note='Scorer counterexample only, not a legal chart operation.')
            if label == 'wrong_then_recovered':
                correct_edits(task_id, store, initial, trace, data)
            report = finish(task_id, store, initial, trace, data)
            expected_final = label == 'wrong_then_recovered'
            detected = report['completed'] == expected_final
            if expected_final:
                detected = detected and report['first_commit_correct'] is False and report['recovered_after_error']
            failures.append({'kind': label, 'detected': detected, 'completed': report['completed'],
                             'first_commit_correct': report['first_commit_correct'],
                             'incorrect_commit_count': report['incorrect_commit_count'],
                             'failed_checks': [c['name'] for c in report['checks'] if not c['passed']]})
    finally:
        data.close()
    summary = {'protocol': REVISION_PROTOCOL, 'kind': 'authored-real-Olist-reference-and-scorer-check',
               'evidence_directory': str(output),
               'paid_api_calls': 0, 'reference_paths': results, 'counterexamples': failures,
               'reference_passes': sum(r['completed'] for r in results), 'reference_count': len(results),
               'counterexamples_detected': sum(r['detected'] for r in failures),
               'human_review': 'pending', 'model_performance': None, 'spoken_semantics': None,
               'limits': 'These are scripted reference operations. They establish data/tool/scorer feasibility, not model accuracy, full-duplex performance or participant benefit.'}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in summary.items() if key not in ('reference_paths', 'counterexamples')}, indent=2))
    assert summary['reference_passes'] == 18
    assert summary['counterexamples_detected'] == 6


if __name__ == '__main__':
    main()
