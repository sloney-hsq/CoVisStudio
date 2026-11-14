"""Offline post-commit JPEG/wire audit for the two explicit real diagnostics."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_delivery import audit_session


def image_sequences(events, session):
    """Missing evidence fails a sequence; never infer visual reasoning from delivery."""
    sent = []
    for event in events:
        if event['name'] == 'model_input' and event.get('status') == 'sent':
            raw = (session / event['file']).read_bytes()
            wire = json.loads(raw)
            if wire.get('type') in ('input_image_buffer.append', 'response.create', 'conversation.item.create'):
                sent.append((event, wire, hashlib.sha256(raw).hexdigest() == event['sha256']))
    sequences = []
    for commit in (e for e in events if e['name'] == 'tool_committed'):
        revision = commit['revision']
        result = {'revision': revision, 'commit_index': commit['index'], 'passed': False}
        capture = next((e for e in events if e['name'] == 'image_captured'
                        and e['index'] > commit['index'] and e['reference']['revision'] == revision), None)
        if capture:
            jpg = (session / capture['file']).read_bytes()
            digest = hashlib.sha256(jpg).hexdigest()
            image = next(((e, w, valid) for e, w, valid in sent
                          if e['index'] > capture['index'] and w['type'] == 'input_image_buffer.append'
                          and base64.b64decode(w['image']) == jpg), None)
            receipt = next(((e, w, valid) for e, w, valid in sent
                            if e['index'] > commit['index'] and w['type'] == 'conversation.item.create'
                            and w['item'].get('call_id') == commit.get('call_id')), None)
            response = next(((e, w, valid) for e, w, valid in sent
                             if image and e['index'] > image[0]['index'] and w['type'] == 'response.create'), None)
            delivery = next((e for e in events if e['name'] == 'image_delivery'
                             and e.get('status') == 'sent' and e.get('frame_id') == capture['file']), None)
            state = json.loads((session / f'state-r{revision}.json').read_text(encoding='utf-8'))
            rendered = [e for e in events if e['name'] == 'chart_rendered'
                        and e['details']['revision'] == revision
                        and commit['index'] < e['index'] < capture['index']]
            render_complete = {e['details']['view_id'] for e in rendered} == {v['id'] for v in state['views']}
            result.update(capture_index=capture['index'], image_file=capture['file'], jpeg_sha256=digest,
                          captured_hash_matches=digest == capture.get('sha256'), all_views_rendered=render_complete,
                          native_image_index=image[0]['index'] if image else None,
                          receipt_index=receipt[0]['index'] if receipt else None,
                          next_response_index=response[0]['index'] if response else None,
                          delivery_index=delivery['index'] if delivery else None)
            result['passed'] = bool(image and receipt and response and delivery and render_complete
                and digest == capture.get('sha256') and all(x[2] for x in (image, receipt, response))
                and capture['index'] < receipt[0]['index'] < image[0]['index']
                < delivery['index'] < response[0]['index'])
        sequences.append(result)
    return sequences


def audit_run(run, data_dir):
    report = json.loads((run / 'report.json').read_text(encoding='utf-8'))
    session = Path(report['session_directory'])
    if not session.is_absolute():
        session = ROOT / session
    delivery = audit_session(session, data_dir)
    ordering = image_sequences(report['events'], session)
    checks = dict(report['evaluation']['checks'])
    checks['every_commit_fresh_native_jpeg_before_followup'] = bool(ordering) and all(x['passed'] for x in ordering)
    checks['all_archived_states_independent_sql'] = bool(delivery['numeric_audit']) and all(
        x['status'] == 'passed' for x in delivery['numeric_audit'])
    return {'original_driver_status': report['status'], 'checks': checks, 'passed': all(checks.values()),
            'post_commit_sequences': ordering, 'independent_delivery': delivery,
            'boundary': 'Native JPEG bytes were delivered before follow-up; model visual inspection and human listening remain unverified.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit_run(args.run_dir, args.data_dir)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'passed': result['passed'], 'failed_checks': [k for k, v in result['checks'].items() if not v]}))


if __name__ == '__main__':
    main()
