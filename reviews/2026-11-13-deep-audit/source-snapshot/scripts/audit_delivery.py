"""Audit an archived session without importing or resetting a live Workspace."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.delivery import summarize_delivery


def audit_session(session_dir, data_dir=None):
    session_dir = Path(session_dir)
    event_file = session_dir / 'events.jsonl'
    states = sorted(session_dir.glob('state-r*.json'))
    inputs = [event_file, *states]
    report = {'schema': 'covis-delivery-audit-1', 'session_dir': str(session_dir.resolve()),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'input_fingerprints': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'source_fingerprints': {str(p.relative_to(Path(__file__).resolve().parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), Path(__file__).resolve().parents[1] / 'backend/delivery.py', Path(__file__).resolve().parents[1] / 'backend/oracle.py']},
        'delivery_ledger': summarize_delivery([json.loads(line) for line in event_file.read_text(encoding='utf-8').splitlines() if line.strip()]),
        'numeric_audit': []}
    data = None
    if data_dir is not None:
        from backend.data import OlistData
        data = OlistData(Path(data_dir))
        report['data_fingerprints'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(data_dir).glob('*.csv'))}
    try:
        from backend.oracle import category_rows, numeric_rows_equal
        for path in states:
            state = json.loads(path.read_text(encoding='utf-8'))
            for view in state['views']:
                row = {'revision': state['revision'], 'view_id': view['id'], 'source': view['source'],
                       'chart_type': view['chart_type'], 'status': 'not_checked'}
                if data is None:
                    row['reason'] = 'Independent SQL audit not requested.'
                elif view['chart_type'] not in ('bar', 'line', 'area', 'pie', 'scatter', 'heatmap') or view['source'].get('dimension') != 'category':
                    row['reason'] = 'Independent oracle supports category aggregates only for the six supported chart forms.'
                else:
                    expected = category_rows(data, view['source'])
                    row.update(status='passed' if numeric_rows_equal(view['data']['rows'], expected) else 'failed',
                               oracle='backend.oracle.category_rows', checked_rows=len(expected))
                report['numeric_audit'].append(row)
    finally:
        if data is not None:
            data.connection.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-dir', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--data-dir', type=Path, help='Enable independent SQL audit using this Olist CSV directory.')
    args = parser.parse_args()
    report = audit_session(args.session_dir, args.data_dir)
    output = args.output or args.session_dir / ('delivery-audit-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(output)


if __name__ == '__main__':
    main()
