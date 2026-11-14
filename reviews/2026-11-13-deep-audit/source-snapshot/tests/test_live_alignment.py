"""Normal frontend/backend image and voice lifecycle agreement; local only."""
import asyncio
import base64
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
import pytest

from backend.app import Workspace
from backend.settings import load_settings


class Browser:
    def __init__(self):
        self.events = []

    async def send_json(self, event):
        self.events.append(deepcopy(event))


@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    ws = Workspace({'api_key': '', 'voice': 'Maia', 'text_model': 'local', 'realtime_model': 'local',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
        'trace_dir': tmp_path_factory.mktemp('live-alignment')})
    yield ws
    ws.data.connection.close()


@pytest.mark.parametrize('key_name', ['QWEN_API_KEY', 'DASHSCOPE_API_KEY'])
def test_explicit_env_file_is_loaded_without_exposing_its_key(tmp_path, monkeypatch, key_name):
    path = tmp_path / 'study.env'
    path.write_text(f'{key_name}=local-test-value\nQWEN_VOICE=Maia\n', encoding='utf-8')
    monkeypatch.setenv('QWEN_API_KEY', 'unrelated-process-value')
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'old-process-value')
    settings = load_settings(path)
    assert settings['api_key'] == 'local-test-value'
    assert settings['credential_file'] == str(path.resolve())


def test_blank_local_key_does_not_connect_with_an_unrelated_process_key(tmp_path, monkeypatch):
    path = tmp_path / 'blank.env'
    path.write_text('QWEN_API_KEY=\n', encoding='utf-8')
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'old-process-value')
    assert load_settings(path)['api_key'] == ''


def test_bootstrap_distinguishes_disabled_and_unconfigured(workspace):
    workspace.settings['api_key'] = ''
    assert workspace.bootstrap()['settings']['connection_mode'] == 'disabled'
    workspace.settings['realtime_url'] = 'ws://127.0.0.1:9/not-called'
    assert workspace.bootstrap()['settings']['connection_mode'] == 'unconfigured'
    workspace.settings['api_key'] = 'local-test-value'
    public = workspace.bootstrap()['settings']
    assert public['connection_mode'] == 'configured'
    assert public['configured'] is True
    assert 'local-test-value' not in json.dumps(public)
    workspace.settings['api_key'] = ''


def test_visual_delivery_keeps_the_actual_frame_reference_and_empty_clears_it(workspace):
    async def run():
        workspace.reset('text', None, 'local-check')
        browser = Browser()
        workspace.socket = browser
        image = BytesIO()
        Image.new('RGB', (12, 12), 'white').save(image, 'JPEG')
        reference = {'revision': 0, 'view_ids': ['selected-chart'], 'entities': {'selected-chart': ['original-member']}}
        await workspace.set_context({'reference': reference, 'image': base64.b64encode(image.getvalue()).decode()})
        frame = workspace.image_frame
        assert browser.events[-1]['status'] == 'captured'
        # Selection may have changed by the time the provider sends the earlier frame.
        workspace.reference = {'revision': 0, 'view_ids': [], 'entities': {}}
        await workspace.provider_event({'type': 'image_delivery', 'status': 'queued', 'frame_id': frame})
        await workspace.provider_event({'type': 'image_delivery', 'status': 'sent', 'frame_id': frame})
        assert browser.events[-1]['reference'] == reference
        assert browser.events[-1]['status'] == 'sent'
        assert [e['status'] for e in workspace.trace.events if e['name'] == 'image_delivery'] == ['queued', 'sent']
        await workspace.set_context({'reference': workspace.reference, 'image': ''})
        assert workspace.image == '' and workspace.image_frame is None
        assert browser.events[-1]['status'] == 'empty'
        workspace.socket = None
    asyncio.run(run())


def test_closed_transport_releases_workspace_timer_and_browser_microphone(workspace):
    class AlreadyClosed:
        closed = True
        close_waits = 0

        async def close(self):
            # The provider's idempotent close also awaits an existing cleanup task.
            self.close_waits += 1

    async def run():
        browser = Browser()
        workspace.socket = browser
        voice = AlreadyClosed()
        workspace.voice = voice
        timer = asyncio.create_task(asyncio.sleep(60))
        workspace.voice_timer = timer
        await workspace.provider_event({'type': 'transport_closed', 'reason': 'error'})
        await asyncio.gather(timer, return_exceptions=True)
        assert timer.cancelled()
        assert workspace.voice is None and workspace.voice_timer is None
        assert voice.close_waits == 1
        assert [event['type'] for event in browser.events] == ['stop_audio', 'voice_closed']
        assert sum(e['name'] == 'voice_closed' for e in workspace.trace.events) == 1
        workspace.socket = None
    asyncio.run(run())


def test_handshake_failure_does_not_leave_a_connected_ui(workspace, monkeypatch):
    class FailedHandshake:
        closed = False
        async def connect(self, _):
            raise RuntimeError('Local handshake fixture rejection')
        async def close(self):
            self.closed = True

    async def run():
        voice = FailedHandshake()
        monkeypatch.setattr('backend.providers.QwenRealtime', lambda *args: voice)
        workspace.settings['api_key'] = 'local-test-value'
        workspace.socket = Browser()
        with pytest.raises(RuntimeError, match='fixture rejection'):
            await workspace.start_voice({'mode': 'push_to_talk', 'image': '',
                'reference': {'revision': 0, 'view_ids': [], 'entities': {}}})
        assert voice.closed and workspace.voice is None and workspace.voice_timer is None
        assert workspace.socket.events[-1]['type'] == 'voice_closed'
        workspace.settings['api_key'] = ''
        workspace.socket = None
    asyncio.run(run())


def test_tool_feedback_names_actual_commits_previews_and_failed_edits(workspace):
    async def run():
        workspace.reset('text', 'exp_01_a', 'local-check')
        browser = Browser()
        workspace.socket = browser
        revision = workspace.store.state['revision']
        result = await workspace.execute('preview_revision', {
            'view_ids': ['v2', 'v3'], 'evidence': {'revision': 3, 'view_id': 'v1'},
            'source_patch': {}, 'member_action': 'use_evidence', 'needs_confirmation': True,
            'question': 'Keep this comparison set?'})
        assert browser.events[-1]['tool'] == 'preview_revision'
        assert browser.events[-1]['committed'] is False
        proposal_id = result['proposal']['id']
        await workspace.execute('apply_revision', {'proposal_id': proposal_id})
        assert browser.events[-1]['status'] == 'awaiting_confirmation'
        assert workspace.store.state['revision'] == revision
        await workspace.execute('apply_revision', {'proposal_id': proposal_id}, actor='user')
        assert browser.events[-1]['view_numbers'] == [2, 3]
        assert browser.events[-1]['revision'] == revision + 1
        assert browser.events[-1]['committed'] is True
        await workspace.execute('edit_charts', {'view_ids': ['v2'], 'patch': {'source': {'metric': 'invented'}}})
        assert browser.events[-1]['status'] == 'failed'
        assert browser.events[-1]['committed'] is False
        assert workspace.store.state['revision'] == revision + 1
        await workspace.execute('remove_charts', {'view_ids': ['v2']}, actor='user')
        assert browser.events[-1]['view_numbers'] == [2]
        assert browser.events[-1]['committed'] is True
        workspace.socket = None
    asyncio.run(run())
