"""Export assigned-session evidence locally; never connects to a model."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.experiment import aggregate_reports, allocation_table, report_csv
from backend.review_packets import read_trial_archives, attach_review_drafts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trace-dir', type=Path, required=True, help='Directory whose child session folders contain session.json.')
    parser.add_argument('--plan-count', type=int, default=30)
    parser.add_argument('--archive-dir', type=Path, action='append', default=[], help='Additional archived experiment directory to include.')
    args = parser.parse_args()
    records = read_trial_archives([*args.archive_dir, args.trace_dir])
    reports = [record['archive']['report']['trial_report'] for record in records.values()]
    aggregate = attach_review_drafts(aggregate_reports(reports), records)
    output = ROOT / 'traces' / 'experiment-exports' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    (output / 'report.json').write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'attempts.csv').write_text(report_csv(aggregate), encoding='utf-8-sig')
    (output / 'allocation.json').write_text(json.dumps(allocation_table(args.plan_count), indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'attempts': aggregate['attempt_count'],
                      'missing_trials': len(aggregate['missing_trials']), 'human_review': 'pending'}))


if __name__ == '__main__':
    main()
