"""Actual-capture ordering contract; local authored frame fixtures only."""
import asyncio
import base64
from pathlib import Path

import pytest

from backend.app import Workspace
from backend.providers import QwenRealtime


@pytest.mark.parametrize('finish', ['capture', 'onset', 'revoke', 'close'])
def test_committed_voice_tool_waits_for_its_capture_without_blocking_new_input(tmp_path, finish):
    async def run():
        ws = Workspace({'api_key': '', 'text_model': 'local', 'realtime_model': 'local',
                        'voice': 'Maia', 'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
                        'trace_dir': tmp_path})
        committed = asyncio.Event()
        messages = []

        class Browser:
            async def send_json(self, event):
                messages.append(event)
                if event['type'] == 'state':
                    committed.set()

        class Voice:
            async def cancel(self):
                pass

            async def close(self):
                pass

            async def context(self, text):
                pass

            async def image(self, image, frame_id=None):
                assert frame_id.endswith('-r1.jpg')

        def capture(revision):
            return {'reference': {'revision': revision, 'view_ids': [], 'entities': {}},
                    'image': base64.b64encode(f'local-frame-{revision}'.encode()).decode(),
                    'captured_client_ms': ws.trace.now_ms(), 'client_clock_id': 'fixture'}

        ws.trace.calibrations['fixture'] = {'offset_ms': 0, 'uncertainty_ms': 0, 'calibration_id': 'fixture'}
        ws.socket = Browser()
        await ws.set_context(capture(0))
        ws.voice = Voice()
        task = asyncio.create_task(ws.execute('set_dashboard', {'title': 'Committed title'}))
        try:
            await asyncio.wait_for(committed.wait(), 2)
            assert ws.store.state['revision'] == 1
            assert not task.done(), 'Native receipt escaped before the committed render capture'
            assert not ws.tool_lock.locked()
            if finish == 'capture':
                await ws.set_context(capture(0))
                await asyncio.sleep(0)
                assert not task.done(), 'An old-revision capture released the new receipt'
                await ws.set_context(capture(1))
            elif finish == 'onset':
                await ws.provider_event({'type': 'speech_start', 'item_id': 'new'})
            elif finish == 'revoke':
                await ws.revoke()
            else:
                await ws.close_voice()
            result = await asyncio.wait_for(task, 2)
            assert ws.store.state['revision'] == 1
            assert ws.store.state['title'] == 'Committed title'
            if finish == 'capture':
                assert result['committed'] is True
                await ws.provider_event({'type': 'response_prepare', 'transport': 'websocket'})
                assert ws.decision_image()['file'].endswith('-r1.jpg')
            else:
                assert result['status'] == 'superseded'
                assert result['committed'] is True and result['revision'] == 1
                assert set(result) == {'status', 'committed', 'revision', 'message'}
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            ws.data.connection.close()

    asyncio.run(run())


def test_provider_does_not_upload_the_same_archived_frame_twice():
    async def run():
        wire = []

        async def emit(event):
            pass

        class Socket:
            async def send(self, text):
                wire.append(text)

        voice = QwenRealtime({}, 'live_voice', [], emit, None)
        voice.ws = Socket()
        voice.audio_open = True
        await voice.image('same-jpeg', 'frame-r1.jpg')
        await voice.image('same-jpeg', 'frame-r1.jpg')
        assert len(wire) == 1
        await voice.image('next-jpeg', 'frame-r2.jpg')
        assert len(wire) == 2

    asyncio.run(run())


@pytest.mark.parametrize('operation', ['remove_last', 'create_first'])
def test_empty_canvas_capture_for_first_create_and_last_remove(tmp_path, operation):
    async def run():
        ws = Workspace({'api_key': '', 'text_model': 'local', 'realtime_model': 'local',
                        'voice': 'Maia', 'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
                        'trace_dir': tmp_path})
        published = asyncio.Event()

        class Browser:
            async def send_json(self, event):
                if event['type'] == 'state':
                    published.set()

        try:
            create_arguments = {'title': 'Orders', 'chart_type': 'bar', 'source': {
                'metric': 'orders', 'dimension': 'category', 'region': 'SP', 'start': '2017-01-01',
                'end': '2018-01-01', 'status': 'delivered', 'top_n': 3}}
            if operation == 'remove_last':
                await ws.execute('create_chart', create_arguments, actor='user')
            ws.trace.calibrations['fixture'] = {'offset_ms': 0, 'uncertainty_ms': 0, 'calibration_id': 'fixture'}
            def context(revision, image):
                return {'reference': {'revision': revision, 'view_ids': [], 'entities': {}}, 'image': image,
                        'captured_client_ms': ws.trace.now_ms(), 'client_clock_id': 'fixture'}
            old_revision = ws.store.state['revision']
            frame = base64.b64encode(b'local-frame').decode()
            await ws.set_context(context(old_revision, frame if operation == 'remove_last' else ''))
            ws.socket = Browser()
            ws.voice = object()  # No transport calls are needed for this ordering test.
            task = asyncio.create_task(ws.execute('remove_charts', {'view_ids': ['v1']}) if operation == 'remove_last'
                                       else ws.execute('create_chart', create_arguments))
            await asyncio.wait_for(published.wait(), 2)
            assert not task.done()
            assert bool(ws.store.state['views']) == (operation == 'create_first')
            await ws.set_context(context(old_revision + 1, '' if operation == 'remove_last' else frame))
            result = await asyncio.wait_for(task, 2)
            assert result['committed'] is True and result['state']['revision'] == old_revision + 1
            ws.freeze_evidence()
            assert (ws.decision_image() is None) == (operation == 'remove_last')
        finally:
            ws.data.connection.close()

    asyncio.run(run())
