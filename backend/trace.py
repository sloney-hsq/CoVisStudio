"""Append-only evidence with raw clocks and explicitly calibrated alignment."""
import base64
import hashlib
import json
import time
import wave
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


class Trace:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.started = time.perf_counter()
        self.events = []
        self.session_id = directory.name
        self.current = {}
        self.responses = {}
        self.requests = {}
        self.items = {}
        self.calibrations = {}
        self.call_context = ContextVar('trace_call_context', default=None)
        self.chunk_index = 0

    def now_ms(self):
        return round((time.perf_counter() - self.started) * 1000, 3)

    @contextmanager
    def scope(self, context):
        token = self.call_context.set(deepcopy(context))
        try:
            yield
        finally:
            self.call_context.reset(token)

    def origin(self, response_id=None, item_id=None):
        if response_id is not None:
            return deepcopy(self.responses.get(response_id, {}))
        if item_id is not None:
            return deepcopy(self.items.get(item_id, {}))
        return deepcopy(self.current)

    def calibrate_clock(self, client_clock_id, session_id, samples):
        if session_id != self.session_id:
            return None
        measured = []
        for sample in samples:
            c1, c4 = sample['client_send_ms'], sample['client_receive_ms']
            s2, s3 = sample['server_receive_ms'], sample['server_send_ms']
            measured.append(((c4-c1)-(s3-s2), ((s2-c1)+(s3-c4))/2, sample))
        rtt, offset, selected = min(measured, key=lambda entry: entry[0])
        calibration = {'calibration_id': f'{self.session_id}:clock:{len(self.events)}',
                       'offset_ms': offset, 'uncertainty_ms': rtt/2}
        self.calibrations[client_clock_id] = calibration
        self.record('clock_calibrated', client_clock_id=client_clock_id,
                    samples=samples, selected_sync_id=selected['sync_id'], **calibration)
        return calibration

    def record_client(self, message, origin=None):
        client_session_id = message.get('session_id')
        if client_session_id is not None and client_session_id != self.session_id:
            with self.scope({}):
                return self.record('client_event_session_mismatch', client_session_id=client_session_id,
                                   client_event=message)
        calibration = self.calibrations.get(message.get('client_clock_id'))
        details = message.get('details', {})
        if origin is None:
            if details.get('request_id') is not None:
                origin = next((request for request in self.requests.values()
                               if request['request_id'] == details['request_id']), {})
            else:
                origin = self.origin(details.get('response_id'), details.get('item_id'))
        correlation = {key: details[key] for key in ('response_id', 'item_id', 'call_id') if details.get(key) is not None}
        with self.scope(origin):
            return self.record(message['name'], **{**origin, **correlation},
            observation_request_id=self.current.get('request_id'),
            client_session_id=client_session_id,
            client_ms=message['client_ms'], client_clock_id=message.get('client_clock_id'),
            client_event_id=message.get('client_event_id'), details=details,
            aligned_server_ms=message['client_ms'] + calibration['offset_ms'] if calibration else None,
            calibration_id=calibration['calibration_id'] if calibration else None,
            uncertainty_ms=calibration['uncertainty_ms'] if calibration else None)

    def client_stamp(self, client_ms, clock_id):
        calibration = self.calibrations.get(clock_id)
        return {'captured_at': client_ms + calibration['offset_ms'] if calibration and client_ms is not None else None,
                'clock_uncertainty': calibration['uncertainty_ms'] if calibration else None,
                'calibration_id': calibration['calibration_id'] if calibration else None,
                'raw_clock': {'client_ms': client_ms, 'client_clock_id': clock_id}}

    def record_model_input(self, event):
        """Archive exact application wire bytes, never HTTP/authentication headers."""
        wire = event['wire_text'].encode('utf-8')
        filename = f"model-input-{event['input_id']}-{event['status']}.json"
        (self.directory / filename).write_bytes(wire)
        return self.record('model_input', input_id=event['input_id'], transport=event['transport'],
                           status=event['status'], file=filename, bytes=len(wire),
                           sha256=hashlib.sha256(wire).hexdigest())

    def record(self, name, **details):
        origin = self.call_context.get()
        if origin is None:
            origin = self.origin(details.get('response_id'), details.get('item_id'))
        event = {**origin, 'schema': 'covis-event-1', 'session_id': self.session_id,
                 'event_id': f'{self.session_id}:{len(self.events)}',
                 'index': len(self.events), 'name': name,
                 'at': datetime.now(timezone.utc).isoformat(),
                 'server_ms': self.now_ms(),
                 **deepcopy(details)}
        self.events.append(event)
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        return event

    def image(self, encoded, revision):
        path = self.directory / f'image-{len(self.events):05d}-r{revision}.jpg'
        path.write_bytes(base64.b64decode(encoded))
        return path.name

    def audio(self, encoded, direction, response_id='input'):
        # Provider IDs are not used as filesystem paths.
        token = ''.join(c for c in response_id if c.isalnum() or c in '-_')
        path = self.directory / f'{direction}-{token}.pcm'
        block = base64.b64decode(encoded)
        offset = path.stat().st_size if path.exists() else 0
        with path.open('ab') as stream:
            stream.write(block)
        self.chunk_index += 1
        return {'chunk_id': f'{self.session_id}:audio:{self.chunk_index}',
                'sample_start': offset // 2, 'sample_end': (offset + len(block)) // 2,
                'file': path.name, 'offset_bytes': offset, 'bytes': len(block), 'sample_rate': 16000 if direction == 'input' else 24000}

    def finalize_audio(self):
        for path in self.directory.glob('*.pcm'):
            with wave.open(str(path.with_suffix('.wav')), 'wb') as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000 if path.name.startswith('input-') else 24000)
                stream.writeframes(path.read_bytes())

    def save(self, name, data):
        (self.directory / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
