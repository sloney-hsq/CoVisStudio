"""Offline direct/bound audit. Never loads credentials or instantiates a provider."""
import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import Workspace, MODEL_TOOLS

# Authoritative private study fields, not public task 'goal' prose.
PRIVATE_KEYS = {'expected_sources', 'target_sources', 'resolution', 'evidence_phase',
                'evidence_indices', 'target_ids', 'expected_members', 'reference_trajectory',
                'source_requirement'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def differences(a, b, path='$'):
    if type(a) is not type(b):
        return [{'path': path, 'left': a, 'right': b}]
    if isinstance(a, dict):
        result = []
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                result.append({'path': f'{path}.{key}', 'left': a.get(key), 'right': b.get(key)})
            else:
                result.extend(differences(a[key], b[key], f'{path}.{key}'))
        return result
    if isinstance(a, list):
        if len(a) != len(b):
            return [{'path': path, 'left_length': len(a), 'right_length': len(b)}]
        return [item for i, (x, y) in enumerate(zip(a, b)) for item in differences(x, y, f'{path}[{i}]')]
    if a != b:
        item = {'path': path, 'left': a, 'right': b}
        if isinstance(a, float) and isinstance(b, float):
            item['machine_precision_only'] = math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
        return [item]
    return []


def private_hits(value, path='$'):
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in PRIVATE_KEYS:
                result.append(f'{path}.{key}')
            result.extend(private_hits(item, f'{path}.{key}'))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            result.extend(private_hits(item, f'{path}[{i}]'))
    elif isinstance(value, str) and value.lstrip().startswith(('{', '[')):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return result
        result.extend(private_hits(decoded, path + '<json>'))
    return result


async def controlled(out, data_dir):
    settings = {'api_key': '', 'text_model': 'qwen3.8-omni-flash',
                'realtime_model': 'qwen3.8-omni-flash-realtime', 'voice': 'Maia',
                'text_url': 'http://127.0.0.1:9/disabled',
                'realtime_url': 'ws://127.0.0.1:9/disabled',
                'trace_dir': out / 'workspaces', 'data_dir': data_dir}
    runs = {}
    for condition in ('direct', 'bound_revision'):
        ws = Workspace(settings)
        try:
            # Identical measured data and deterministic SQL reduction order.
            ws.data.connection.execute('SET threads=1')
            ws.reset('live_voice', 'starter', '', condition)
            old = ws.store.snapshot()
            await ws.execute('save_category_set', {'name': 'Historical cohort',
                'revision': old['revision'], 'view_id': 'v1'}, actor='user')
            await ws.execute('edit_charts', {'view_ids': ['v2', 'v3'],
                'patch': {'source': {'region': 'MG'}}}, actor='user')
            ws.accept('Use the historical cohort in charts 2 and 3, keeping current scope.',
                      {'revision': ws.store.state['revision'], 'view_ids': ['v2', 'v3'], 'entities': {}})
            package = ws.freeze_evidence()
            context = json.loads(ws.context())
            reads = {}
            for tool in ('read_history', 'list_category_sets', 'list_evidence_candidates'):
                reads[tool] = (await ws.execute(tool, {}))['result']
            edit = await ws.execute('revise_analysis', {'view_ids': ['v2', 'v3'],
                'member_action': 'use_evidence', 'candidate_id': f"chart:{old['revision']}:v1"})
            post_context = json.loads(ws.context())
            # Normalize only the random session prefix, retaining request numbers
            # and every execution fact in the B0/B2 comparison.
            for payload in (context, post_context):
                execution = payload['execution_state']
                for item in [execution, *execution['recent_request_outcomes']]:
                    item['request_id'] = '<session>:' + item['request_id'].removeprefix(ws.session['id'] + ':')
            # A local proposal UUID is transport identity; card.condition remains visible.
            if post_context['last_proposal']:
                post_context['last_proposal']['id'] = '<local-proposal-id>'
            post_context['evidence_package_id'] = '<local-package-id>'
            card = edit.get('proposal', {}).get('card')
            confirmation = await ws.execute('revise_analysis', {'view_ids': ['v2'],
                'member_action': 'keep_current', 'needs_confirmation': True,
                'question': 'Which date range?'})
            runs[condition] = {'instructions': ws.instructions(), 'context': context,
                'reads': reads, 'final_state': edit.get('state'),
                'post_edit_context': post_context, 'receipt_card': card,
                'commit': {'status': edit['status'], 'committed': edit['committed']},
                'clarification': {'status': confirmation['status'], 'committed': confirmation['committed']},
                'package_id': package['package_id'], 'tool_schema_sha256': digest(MODEL_TOOLS),
                'private_key_hits': private_hits({'context': context, 'reads': reads})}
        finally:
            ws.data.close()
    left, right = runs.values()
    # The package ID names a different local archive; no semantic condition field is removed.
    for run in runs.values():
        run['context']['evidence_package_id'] = '<local-package-id>'
    return {'runs': runs, 'context_differences': differences(left['context'], right['context']),
            'read_differences': differences(left['reads'], right['reads']),
            'result_differences': differences(left['final_state'], right['final_state']),
            'post_edit_context_differences': differences(left['post_edit_context'], right['post_edit_context']),
            'receipt_card_differences': differences(left['receipt_card'], right['receipt_card']),
            'instruction_equal': left['instructions'] == right['instructions'],
            'tools_equal': left['tool_schema_sha256'] == right['tool_schema_sha256'],
            'commit_equal': left['commit'] == right['commit'],
            'clarification_equal': left['clarification'] == right['clarification']}


def archived(root):
    rows = []
    for trial in sorted(root.glob('[0-9][0-9]-*')):
        if not trial.is_dir():
            continue
        report = json.loads((trial / 'report.json').read_text(encoding='utf-8'))
        counts, hits, instructions, tools = {}, [], set(), set()
        files = list((trial / 'sessions').glob('*/model-input-*-sent.json'))
        for file in files:
            payload = json.loads(file.read_text(encoding='utf-8'))
            kind = payload['type']
            counts[kind] = counts.get(kind, 0) + 1
            # PCM/image payloads cannot contain JSON study fields.
            if kind in ('input_audio_buffer.append', 'input_image_buffer.append'):
                continue
            hits.extend({'file': str(file.relative_to(ROOT)), 'path': p} for p in private_hits(payload))
            if kind == 'session.update':
                instructions.add(digest(payload['session'].get('instructions')))
                if 'tools' in payload['session']:
                    tools.add(digest(payload['session']['tools']))
        rows.append({'trial': trial.name, 'status': report['status'],
            'condition': report['condition'], 'study_parity': report.get('study_parity'),
            'sent_file_count': len(files), 'input_types': counts,
            'instruction_hashes': sorted(instructions), 'tool_hashes': sorted(tools),
            'private_key_hits': hits})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'traces/research-acceleration/parity')
    parser.add_argument('--archive', type=Path, default=ROOT / 'traces/real-study-20261113-224313')
    parser.add_argument('--data-dir', type=Path, default=Path('C:/VerbalVis/datasets/olist/data'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'scope': 'offline controlled application parity + archived outbound known-field scan',
        'native_history_frozen': False, 'semantic_leak_absence_proven': False,
        'known_private_fields': sorted(PRIVATE_KEYS),
        'controlled': asyncio.run(controlled(args.output, args.data_dir)),
        'archived': archived(args.archive)}
    destination = args.output / 'audit.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(destination), 'archived_trials': len(result['archived']),
        'context_difference_paths': [x['path'] for x in result['controlled']['context_differences']],
        'read_difference_count': len(result['controlled']['read_differences']),
        'result_difference_count': len(result['controlled']['result_differences'])}))


if __name__ == '__main__':
    main()
