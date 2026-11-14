"""Author-scripted real Olist task paths and errors; no model or participant run."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.business_tasks import BUSINESS_PROTOCOL, business_tasks
from backend.charts import ChartStore
from backend.data import OlistData
from backend.study import evaluate, revision_case, revision_targets, setup_operations, task_brief
from backend.trace import Trace


def start(task_id, data, directory):
    store, trace = ChartStore(data), Trace(directory)
    snapshots = {0: store.snapshot()}
    trace.record('session_started', kind='authored-business-task-path', task_id=task_id,
                 paid_api_calls=0, human_review='pending')
    for name, arguments in setup_operations(task_id, data):
        receipt = store.commit(store.prepare(name, arguments))
        trace.record('tool_committed', tool=name, arguments=arguments, actor='starter',
                     revision=receipt['state']['revision'], result=receipt['result'])
        snapshots[receipt['state']['revision']] = receipt['state']
    initial = store.snapshot()
    trace.save('starting-history.json', snapshots)
    trace.save('initial.json', initial)
    trace.save('public-brief.json', task_brief(task_id))
    trace.record('request_accepted', text=task_brief(task_id)['goal'], actor='authored-script', epoch=1)
    return store, initial, trace


def publish(store, trace, ids, patch):
    arguments = {'view_ids': ids, 'patch': {'source': patch}}
    receipt = store.commit(store.prepare('edit_charts', arguments))
    trace.record('tool_committed', tool='edit_charts', arguments=arguments,
                 actor='authored-script', revision=receipt['state']['revision'], result=receipt['result'])


def solve(task_id, store, initial, trace, data):
    targets = revision_targets(task_id, initial, data)
    for number in revision_case(task_id)['targets']:
        publish(store, trace, [f'v{number}'], targets[f'v{number}'])


def finish(task_id, store, initial, trace, data):
    report = evaluate(task_id, initial, store.snapshot(), trace.events, data, [])
    trace.save('final.json', store.snapshot())
    trace.save('report.json', report)
    return report


def main():
    output = ROOT / 'traces' / 'business-task-runs' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=True)
    data = OlistData(Path('C:/VerbalVis/datasets/olist/data'))
    paths, counterexamples = [], []
    try:
        for task in business_tasks():
            task_id = task['id']
            store, initial, trace = start(task_id, data, output / task_id)
            solve(task_id, store, initial, trace, data)
            report = finish(task_id, store, initial, trace, data)
            paths.append({'task_id': task_id, 'technical_completed': report['technical_completed'],
                          'all_revision_commits_correct': report['all_revision_commits_correct'],
                          'interpretation_status': report['interpretation_status'],
                          'task_response_submitted': report['task_response_submitted']})

        cases = [
            ('current_cohort', 'biz_01_sp_priorities_mg'),
            ('wrong_region', 'biz_01_sp_priorities_mg'),
            ('scope_expansion', 'biz_01_sp_priorities_mg'),
            ('failed_release', 'biz_02_mg_local_priorities'),
            ('fixed_new_members_instead_of_ranking', 'biz_02_mg_local_priorities'),
            ('wrong_seasonal_cohort', 'biz_03_seasonal_same_cohort'),
            ('wrong_seasonal_period', 'biz_03_seasonal_same_cohort'),
            ('wrong_local_scope', 'biz_04_stable_metric_control'),
        ]
        for error, task_id in cases:
            store, initial, trace = start(task_id, data, output / f'counterexample-{error}')
            targets = revision_targets(task_id, initial, data)
            if error in ('current_cohort', 'wrong_seasonal_cohort'):
                publish(store, trace, ['v2', 'v3'], {'categories': initial['views'][0]['source']['categories'], 'top_n': None})
            elif error == 'wrong_region':
                solve(task_id, store, initial, trace, data)
                publish(store, trace, ['v2', 'v3'], {'region': 'SP'})
            elif error == 'scope_expansion':
                solve(task_id, store, initial, trace, data)
                publish(store, trace, ['v1'], {'categories': targets['v2']['categories'], 'top_n': None})
            elif error == 'failed_release':
                publish(store, trace, ['v1', 'v2', 'v3'], {'categories': initial['views'][0]['source']['categories'], 'top_n': None})
            elif error == 'fixed_new_members_instead_of_ranking':
                selected = [row['label'] for row in data.query(targets['v1'])['rows']]
                publish(store, trace, ['v1', 'v2', 'v3'], {'categories': selected, 'top_n': None})
            elif error == 'wrong_seasonal_period':
                solve(task_id, store, initial, trace, data)
                publish(store, trace, ['v2', 'v3'], {'start': '2017-01-01', 'end': '2017-04-01'})
            elif error == 'wrong_local_scope':
                solve(task_id, store, initial, trace, data)
                publish(store, trace, ['v2'], {'metric': 'revenue'})
            report = finish(task_id, store, initial, trace, data)
            counterexamples.append({'kind': error, 'detected': not report['technical_completed'],
                                    'failed_checks': [check['name'] for check in report['checks'] if not check['passed']]})
    finally:
        data.close()
    summary = {
        'protocol': BUSINESS_PROTOCOL, 'kind': 'authored-real-Olist-business-task-feasibility',
        'evidence_directory': str(output), 'paid_api_calls': 0,
        'reference_paths': paths, 'reference_passes': sum(path['technical_completed'] for path in paths),
        'reference_count': len(paths), 'counterexamples': counterexamples,
        'counterexamples_detected': sum(case['detected'] for case in counterexamples),
        'counterexample_count': len(counterexamples),
        'human_interpretation': 'pending', 'model_performance': None, 'participant_results': None,
        'limits': 'Author-scripted tools establish feasible chart outcomes and error detection. No model, voice, participant decision or human understanding is tested.',
    }
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in summary.items() if key not in ('reference_paths', 'counterexamples')}, indent=2))
    assert summary['reference_passes'] == 4
    assert summary['counterexamples_detected'] == len(counterexamples)


if __name__ == '__main__':
    main()
