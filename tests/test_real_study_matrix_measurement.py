"""Local regressions for observed real-matrix measurement failures; no provider calls."""
import asyncio

from scripts.verify_real_study_matrix import (
    close_after_watchdog, finish_reason, natural_playback_completed,
    revision_complete, settled_and_drained,
)


def event(index, name, request='r4', **fields):
    return {'index': index, 'name': name, 'request_id': request, **fields}


def test_normal_shutdown_cancels_watchdog_before_slow_provider_close():
    async def scenario():
        report = {}
        closing = asyncio.Event()
        class Workspace:
            async def close_voice(self):
                closing.set()
                await asyncio.sleep(.03)
        async def watchdog():
            await closing.wait()
            report['watchdog_fired'] = True
        task = asyncio.create_task(watchdog())
        await asyncio.sleep(0)
        await close_after_watchdog(Workspace(), task)
        assert not report.get('watchdog_fired')
        assert finish_reason(report, []) == 'completed'
    asyncio.run(scenario())


def test_latest_fragment_must_be_accepted_and_settled_after_full_clip():
    report = {'revision_trigger_event_index': 10}
    events = [event(10, 'speech_start'), event(11, 'request_accepted'), event(12, 'request_outcome')]
    assert not revision_complete(events, report)  # Source WAV is still playing.
    report['revision_input_complete'] = True
    events.append(event(13, 'speech_start', 'r5'))
    assert not revision_complete(events, report)  # Older fragment settled, next ASR pending.
    events.append(event(14, 'request_accepted', 'r5'))
    assert not revision_complete(events, report)
    assert report['revision_request_id'] == 'r5'
    events.append(event(15, 'request_outcome', 'r5'))
    assert revision_complete(events, report)


def test_cancelled_tool_turn_is_transport_error_even_without_python_exception():
    events = [event(20, 'error', event={'message': 'Cannot continue a cancelled tool turn; submit new input'}),
              event(21, 'session_error'), event(22, 'transport_closed', reason='error')]
    assert finish_reason({}, events) == 'transport_error'


def test_interrupted_empty_queue_is_drained_but_not_naturally_completed():
    events = [event(1, 'request_outcome'), event(2, 'audio_received', response_id='resp'),
              event(3, 'playback_end', details={'response_id': 'resp', 'queue_empty': True,
                    'pending_chunks': 0, 'interrupted': True, 'received_samples': 100, 'played_samples': 80})]
    assert settled_and_drained(events, 'r4')
    assert not natural_playback_completed(events, 'r4')
    events[-1]['details'].update(interrupted=False, played_samples=100)
    assert natural_playback_completed(events, 'r4')
