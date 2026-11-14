"""Offline reproduction only: no socket, provider credentials or real API."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.providers import QwenRealtime


class Wire:
    def __init__(self):
        self.events = []

    async def send(self, text):
        self.events.append(json.loads(text))


async def run(tail_first):
    observed = []

    async def emit(event):
        observed.append(event)

    async def execute(*args, **kwargs):
        raise AssertionError('No execution expected')

    client = QwenRealtime({}, 'live_voice', [], emit, execute)
    client.ws = Wire()
    for item in ('first', 'second'):
        await client._handle({'type': 'input_audio_buffer.speech_started', 'item_id': item})
    failed = {'type': 'conversation.item.input_audio_transcription.failed', 'item_id': 'first',
              'error': {'message': 'offline diagnostic failure'}}
    completed = {'type': 'conversation.item.input_audio_transcription.completed',
                 'item_id': 'second', 'transcript': 'Keep other conditions.'}
    for event in ((completed, failed) if tail_first else (failed, completed)):
        await client._handle(event)
    return {'tail_first': tail_first,
            'accepted': [e for e in observed if e['type'] == 'user_transcript'],
            'errors': [e for e in observed if e['type'] == 'error'],
            'response_create_count': sum(e['type'] == 'response.create' for e in client.ws.events)}


async def main():
    print(json.dumps([await run(False), await run(True)], indent=2))


asyncio.run(main())
