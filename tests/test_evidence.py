import asyncio
import hashlib
import json

import pytest

from backend.evidence import EvidenceStore
from backend.providers import QwenRealtime
from backend.trace import Trace


def test_cutoff_availability_uncertainty_and_immutable_archive(tmp_path):
    trace = Trace(tmp_path)
    store = EvidenceStore(trace)
    content = {'source': {'region': 'RJ'}, 'members': ['a']}
    first = store.add('chart', content, captured_at=10, available_at=20, source_request_id='old', chart_revision=1)
    content['members'].append('b')
    first['content']['members'].append('c')
    store.add('saved_set', {'members': ['a'], 'source_revision': 1}, captured_at=10, available_at=60)
    store.add('frame', {}, captured_at=None, available_at=20)
    store.add('frame', {}, captured_at=49, clock_uncertainty=2, available_at=49)
    package = store.package(50, request_id='request')
    assert len(package['items']) == 1
    assert package['items'][0]['content']['members'] == ['a']
    assert package['items'][0]['source_request_id'] == 'old'
    assert {x['reason'] for x in package['excluded']} == {'not_available', 'unknown_capture', 'clock_uncertain'}
    archived = (tmp_path / package['file']).read_bytes()
    store.add('chart', {}, captured_at=5, available_at=5)
    package['items'].clear()
    assert (tmp_path / 'evidence-package-00001.json').read_bytes() == archived
    assert len(json.loads(archived)['items']) == 1


def test_client_stamp_requires_calibration(tmp_path):
    trace = Trace(tmp_path)
    assert trace.client_stamp(15, 'browser')['captured_at'] is None
    trace.calibrations['browser'] = {'offset_ms': 10, 'uncertainty_ms': 2, 'calibration_id': 'cal1'}
    stamp = trace.client_stamp(15, 'browser')
    assert stamp == {'captured_at': 25, 'clock_uncertainty': 2, 'calibration_id': 'cal1',
                     'raw_clock': {'client_ms': 15, 'client_clock_id': 'browser'}}


@pytest.mark.parametrize('failed', [False, True])
def test_wire_audit_attempt_and_send_preserves_native_history(tmp_path, failed):
    async def run():
        trace = Trace(tmp_path)
        events, sent = [], []
        async def on_event(event):
            events.append(event)
            if event['type'] == 'provider_input':
                trace.record_model_input(event)
        class Socket:
            async def send(self, wire):
                if failed:
                    raise OSError('local send failure')
                sent.append(wire)
        provider = QwenRealtime({}, 'live_voice', [], on_event, None)
        provider.ws = Socket()
        if failed:
            with pytest.raises(OSError):
                await provider.context('new package')
        else:
            await provider.context('old instructions')
            await provider.context('new package')
            # Updating instructions is audited but does not delete native conversation items.
            assert [json.loads(x)['type'] for x in sent] == ['session.update', 'session.update']
        audits = [x for x in events if x['type'] == 'provider_input']
        assert [x['status'] for x in audits] == (['attempted'] if failed else ['attempted', 'sent'] * 2)
        for event in trace.events:
            wire = (tmp_path / event['file']).read_bytes()
            assert hashlib.sha256(wire).hexdigest() == event['sha256']
        if sent:
            assert (tmp_path / trace.events[-1]['file']).read_text('utf-8') == sent[-1]
    asyncio.run(run())


def test_response_prepare_revocation_prevents_old_response_create():
    async def run():
        events, sent = [], []
        async def emit(event):
            events.append(event)
            if event['type'] == 'response_prepare':
                await provider.cancel()
        class Socket:
            async def send(self, wire):
                sent.append(json.loads(wire))
        provider = QwenRealtime({}, 'live_voice', [], emit, None)
        provider.ws = Socket()
        await provider._request_response(provider.epoch)
        assert events == [{'type': 'response_prepare', 'transport': 'websocket', 'provider_epoch': 0}]
        assert sent == []
        assert list(provider.requested) == []
    asyncio.run(run())
