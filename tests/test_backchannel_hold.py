"""Short acknowledgements over audible speech keep the assistant's floor; requests still revoke.

Provider-level checks with a recording on_event peer; no model, data or browser.
"""
import asyncio
import json

import pytest

from backend.backchannel import is_backchannel
from backend.providers import QwenRealtime


class Wire:
    def __init__(self):
        self.events = []

    async def send(self, text):
        self.events.append(json.loads(text))


class Peer:
    """Stands in for Workspace.provider_event; grants a hold only while 'audible'."""

    def __init__(self, audible=True):
        self.audible, self.events = audible, []

    async def __call__(self, event):
        self.events.append(event)
        if event['type'] == 'speech_hold':
            return {'hold': self.audible}
        if event['type'] == 'response_prepare':
            return {'request_id': 'r'}
        return None

    def kinds(self):
        return [event['type'] for event in self.events if event['type'] not in ('provider_input', 'provider_event')]


def client(peer):
    voice = QwenRealtime({}, 'live_voice', [], peer, None)
    voice.ws = Wire()
    return voice


async def transcript(voice, item, text):
    await voice._handle({'type': 'conversation.item.input_audio_transcription.completed',
                         'item_id': item, 'transcript': text})


@pytest.mark.parametrize('text,expected', [
    ('Mm-hm.', True), ('Okay, right.', True), ('Got it.', True), ('uh huh', True),
    ('Yes.', False), ('No.', False), ('Wait.', False), ('Stop.', False),
    ('Okay, do it.', False), ('Got it. Narrow all three to the top three.', False), ('', False),
])
def test_classifier_is_turn_taking_only(text, expected):
    assert is_backchannel(text) is expected


def test_acknowledgement_keeps_epoch_response_and_requests_nothing():
    async def run():
        peer = Peer(audible=True)
        voice = client(peer)
        voice.active = 'answer'
        await voice._speech_started('ack')
        assert voice.epoch == 0 and voice.hold is not None
        assert 'speech_start' not in peer.kinds()
        await transcript(voice, 'ack', 'Mm-hm.')
        assert voice.epoch == 0 and voice.hold is None
        assert peer.kinds()[-1] == 'backchannel'
        assert 'speech_start' not in peer.kinds() and 'user_transcript' not in peer.kinds()
        assert not [e for e in voice.ws.events if e['type'] in ('response.cancel', 'response.create')]
        assert voice.speech_items == {}
    asyncio.run(run())


def test_request_over_audible_speech_revokes_at_transcript_with_onset_identity():
    async def run():
        peer = Peer(audible=True)
        voice = client(peer)
        voice.active = 'answer'
        await voice._speech_started('req', audio_start_ms=1200)
        await transcript(voice, 'req', 'Use the Rio categories in charts two and three.')
        starts = [e for e in peer.events if e['type'] == 'speech_start']
        assert len(starts) == 1 and starts[0]['held'] is True
        assert starts[0]['item_id'] == 'req' and starts[0]['audio_start_ms'] == 1200
        assert voice.epoch == 1
        assert [e['type'] for e in voice.ws.events][:1] == ['response.cancel']
        assert peer.kinds().index('speech_start') < peer.kinds().index('user_transcript')
        assert voice.wanted == 1 or 'response_prepare' in peer.kinds()
    asyncio.run(run())


def test_fragmented_request_during_hold_stays_one_group():
    async def run():
        peer = Peer(audible=True)
        voice = client(peer)
        await voice._speech_started('a')
        await voice._speech_started('b')
        assert [e['type'] for e in peer.events].count('speech_hold') == 1
        await transcript(voice, 'a', 'For charts two and three')
        assert 'user_transcript' not in peer.kinds()
        await transcript(voice, 'b', 'use the Sao Paulo categories.')
        accepted = [e for e in peer.events if e['type'] == 'user_transcript']
        assert accepted and accepted[0]['item_ids'] == ['a', 'b']
        assert accepted[0]['text'] == 'For charts two and three use the Sao Paulo categories.'
    asyncio.run(run())


def test_no_hold_when_assistant_silent_preserves_immediate_revocation():
    async def run():
        peer = Peer(audible=False)
        voice = client(peer)
        await voice._speech_started('now')
        assert voice.epoch == 1 and voice.hold is None
        start = next(e for e in peer.events if e['type'] == 'speech_start')
        assert 'held' not in start
    asyncio.run(run())


def test_failed_transcription_during_hold_revokes_rather_than_resuming():
    async def run():
        peer = Peer(audible=True)
        voice = client(peer)
        await voice._speech_started('x')
        await voice._handle({'type': 'conversation.item.input_audio_transcription.failed', 'item_id': 'x'})
        assert 'backchannel' not in peer.kinds()
        assert any(e['type'] == 'speech_start' and e.get('held') for e in peer.events)
        assert peer.kinds()[-1] == 'error'
    asyncio.run(run())


def test_cancel_clears_hold():
    async def run():
        voice = client(Peer(audible=True))
        await voice._speech_started('x')
        await voice.cancel()
        assert voice.hold is None
    asyncio.run(run())
