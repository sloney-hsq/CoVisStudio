import base64
import hashlib
import json

from scripts.audit_rerank_real import image_sequences


def fixture_events(tmp_path):
    jpg = b'actual captured jpeg bytes'
    (tmp_path / 'frame.jpg').write_bytes(jpg)
    (tmp_path / 'state-r7.json').write_text(json.dumps({'views': [{'id': 'v1'}]}))
    events = [
        {'index': 1, 'name': 'tool_committed', 'revision': 7, 'call_id': 'call1'},
        {'index': 2, 'name': 'chart_rendered', 'details': {'revision': 7, 'view_id': 'v1'}},
        {'index': 3, 'name': 'image_captured', 'reference': {'revision': 7}, 'file': 'frame.jpg',
         'sha256': hashlib.sha256(jpg).hexdigest()},
    ]
    for index, wire in ((4, {'type': 'conversation.item.create', 'item': {'call_id': 'call1'}}),
                        (5, {'type': 'input_image_buffer.append', 'image': base64.b64encode(jpg).decode()}),
                        (7, {'type': 'response.create'})):
        raw = json.dumps(wire).encode()
        name = f'wire{index}.json'
        (tmp_path / name).write_bytes(raw)
        events.append({'index': index, 'name': 'model_input', 'status': 'sent', 'file': name,
                       'sha256': hashlib.sha256(raw).hexdigest()})
    events.append({'index': 6, 'name': 'image_delivery', 'status': 'sent', 'frame_id': 'frame.jpg'})
    return sorted(events, key=lambda e: e['index'])


def test_exact_jpeg_order_passes(tmp_path):
    assert image_sequences(fixture_events(tmp_path), tmp_path)[0]['passed']


def test_missing_or_late_capture_cannot_certify_followup(tmp_path):
    events = fixture_events(tmp_path)
    events[2]['index'] = 8
    assert not image_sequences(events, tmp_path)[0]['passed']


def test_wire_hash_corruption_and_different_frame_fail(tmp_path):
    events = fixture_events(tmp_path)
    events[4]['sha256'] = 'wrong'
    assert not image_sequences(events, tmp_path)[0]['passed']
    events = fixture_events(tmp_path)
    (tmp_path / 'frame.jpg').write_bytes(b'different frame')
    assert not image_sequences(events, tmp_path)[0]['passed']
