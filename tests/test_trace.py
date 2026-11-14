import base64

from backend.trace import Trace


def test_clock_alignment_keeps_raw_values_and_selects_min_rtt(tmp_path):
    trace = Trace(tmp_path / 'session')
    event = {'name': 'playback_end', 'client_ms': 105, 'client_clock_id': 'browser',
             'client_event_id': 'e1', 'details': {}}
    assert trace.record_client(event)['aligned_server_ms'] is None
    samples = [dict(sync_id='slow', client_send_ms=0, client_receive_ms=40,
                    server_receive_ms=110, server_send_ms=112),
               dict(sync_id='fast', client_send_ms=100, client_receive_ms=112,
                    server_receive_ms=205, server_send_ms=207),
               dict(sync_id='third', client_send_ms=200, client_receive_ms=220,
                    server_receive_ms=306, server_send_ms=308)]
    calibration = trace.calibrate_clock('browser', 'session', samples)
    assert calibration['offset_ms'] == 100
    assert calibration['uncertainty_ms'] == 5
    logged = trace.events[-1]
    assert logged['samples'] == samples
    assert logged['selected_sync_id'] == 'fast'
    aligned = trace.record_client(event)
    assert aligned['client_ms'] == 105
    assert aligned['aligned_server_ms'] == 205
    assert aligned['client_event_id'] == 'e1'
    assert aligned['calibration_id'] == calibration['calibration_id']
    assert trace.calibrate_clock('browser', 'old-session', samples) is None
    assert Trace(tmp_path / 'new-session').record_client(event)['calibration_id'] is None


def test_old_playback_retains_origin_and_unknown_does_not_guess(tmp_path):
    trace = Trace(tmp_path)
    trace.responses['r1'] = {'request_id': 'q1', 'epoch': 1, 'response_id': 'r1'}
    trace.current = {'request_id': 'q2', 'epoch': 2}
    event = trace.record_client({'name': 'playback_end', 'client_ms': 10,
                                'details': {'response_id': 'r1'}})
    assert event['request_id'] == 'q1'
    unknown = trace.record_client({'name': 'playback_end', 'client_ms': 10,
                                  'details': {'response_id': 'unknown'}})
    assert 'request_id' not in unknown
    assert unknown['response_id'] == 'unknown'
    assert event['schema'] == 'covis-event-1'
    assert event['event_id'] != unknown['event_id']


def test_audio_chunk_ranges_are_per_response(tmp_path):
    trace = Trace(tmp_path)
    pcm = base64.b64encode(bytes(8)).decode()
    first = trace.audio(pcm, 'output', 'r1')
    second = trace.audio(pcm, 'output', 'r1')
    other = trace.audio(pcm, 'output', 'r2')
    assert (first['sample_start'], first['sample_end']) == (0, 4)
    assert (second['sample_start'], second['sample_end']) == (4, 8)
    assert other['sample_start'] == 0
    assert len({first['chunk_id'], second['chunk_id'], other['chunk_id']}) == 3


def test_previous_session_event_is_retained_without_current_attribution(tmp_path):
    trace = Trace(tmp_path / 'current')
    trace.current = {'request_id': 'current-question', 'epoch': 2}
    message = {'name': 'playback_end', 'session_id': 'previous', 'client_ms': 10,
               'client_clock_id': 'browser', 'details': {'response_id': 'old-response'}}
    event = trace.record_client(message)
    assert event['name'] == 'client_event_session_mismatch'
    assert event['client_event'] == message
    assert event['client_session_id'] == 'previous'
    assert 'request_id' not in event
    assert 'aligned_server_ms' not in event
