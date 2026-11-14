"""Offline comparison of execution metadata/policy against one archived native input.

Uses only the event prefix preceding that input. Does not replay or call a model.
"""
import argparse
from copy import deepcopy
import difflib
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import Workspace


def compare(run, filename):
    report = json.loads((run / 'report.json').read_text(encoding='utf-8'))
    entry = next(e for e in report['events'] if e['name'] == 'model_input'
                 and e['status'] == 'sent' and e['file'] == filename)
    session = Path(report['session_directory'])
    if not session.is_absolute():
        session = ROOT / session
    original = json.loads((session / filename).read_text(encoding='utf-8'))['session']['instructions']
    old_policy, serialized = original.rsplit('\n', 1)
    old_context = json.loads(serialized)
    # Rebuild only ledger-derived fields; do not fabricate missing native history.
    ws = Workspace.__new__(Workspace)
    ws.session = {'condition': report['condition']}
    ws.trace = SimpleNamespace(events=[e for e in report['events'] if e['index'] < entry['index']],
                               current={'request_id': entry['request_id']})
    ws.store = SimpleNamespace(state=old_context['current_dashboard'])
    new_context = {**deepcopy(old_context), 'execution_state': ws.execution_state(),
                   'evidence_revision': old_context['current_dashboard']['revision']}
    policy = ws.instructions()
    digest = lambda text: hashlib.sha256(text.encode('utf-8')).hexdigest()
    return {'input_file': filename, 'input_event_index': entry['index'],
            'request_id': entry['request_id'], 'paid_api_calls': 0,
            'method': 'Preserve archived context; reconstruct added ledger fields from preceding events only',
            'added_context_fields': {k: v for k, v in new_context.items() if k not in old_context},
            'changed_existing_fields': [k for k in old_context if old_context[k] != new_context[k]],
            'policy_diff': list(difflib.unified_diff(old_policy.splitlines(), policy.splitlines(),
                               fromfile='archived_policy', tofile='current_policy', lineterm='')),
            'archived_instructions_sha256': digest(old_policy),
            'current_instructions_sha256': digest(policy),
            'limitations': ['No native model state reconstructed', 'No outcome predicted',
                           'Current state was already supplied; additional salience is not missing evidence']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('filename')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.run, args.filename)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
