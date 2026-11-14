"""Prepare three complete modern Qwen TTS inputs; paid calls require --run-real.

API/voice references (verified 2026-11-13; English docs updated 2026-11-12):
https://www.alibabacloud.com/help/en/model-studio/non-realtime-tts-user-guide
https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-voice-list
Uses the explicitly selected Beijing workspace, never a fallback endpoint/model.
"""
import argparse
import audioop
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import wave

import httpx
from dotenv import dotenv_values


ENDPOINT = ('https://llm-ynielphi7sx0d0wc.cn-beijing.maas.aliyuncs.com'
            '/api/v1/services/audio/tts/SpeechSynthesizer')
MODEL = 'qwen-audio-3.1-tts-flash'
VOICE = 'Abby_v3.1'
INSTRUCTION = ('Speak in natural American English, like a person discussing charts with a colleague. '
               'Use a brisk conversational pace, around 210 words per minute, with short natural '
               'pauses and clear pronunciation. Sound engaged and matter-of-fact, not like a narrator.')
CLIPS = {
    '01_reuse': 'Use the selected historical categories for charts two and three. Keep the current region, dates, and metrics.',
    '02_initial': 'For charts two and three, use the selected historical categories, January through June. Keep the current region and metrics. Explain the result.',
    '03_revision': 'Wait, only January through March for those two charts. Keep the same categories, region, and metrics.',
}


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def convert_wav(raw, destination):
    """Resample the entire recording; never crop or accelerate generated audio."""
    with wave.open(io.BytesIO(raw), 'rb') as recording:
        channels, width, rate, frames, compression, _ = recording.getparams()
        assert compression == 'NONE' and channels in (1, 2), 'Expected mono/stereo PCM WAV'
        pcm = recording.readframes(frames)
        source_seconds = len(pcm) / (channels * width * rate)
    if channels == 2:
        pcm = audioop.tomono(pcm, width, .5, .5)
    if width != 2:
        if width == 1:
            pcm = audioop.bias(pcm, 1, -128)
        pcm = audioop.lin2lin(pcm, width, 2)
    if rate != 16000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    with wave.open(str(destination), 'wb') as recording:
        recording.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        recording.writeframes(pcm)
    seconds = len(pcm) / 32000
    return {'seconds': seconds, 'source_seconds': source_seconds,
            'source_rate': rate, 'source_channels': channels,
            'sample_rate': 16000, 'channels': 1, 'sample_width': 2,
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'under_ten_seconds': seconds < 10}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path(r'C:\DuplexVisEval\.env.local'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--run-real', action='store_true')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {'model': MODEL, 'voice': VOICE, 'endpoint': ENDPOINT,
                'instruction': INSTRUCTION, 'run_real': args.run_real, 'clips': []}
    for name, text in CLIPS.items():
        manifest['clips'].append({'id': name, 'text': text, 'words': len(text.split())})
    # Dry preparation never reads credentials or contacts a provider.
    manifest_path = args.output_dir / 'speech-manifest.json'
    assert not manifest_path.exists(), 'Use a new output directory; preserve earlier attempts'
    save_json(manifest_path, manifest)
    if not args.run_real:
        print(f'Prepared text/settings only: {manifest_path}')
        return
    values = dotenv_values(args.env_file)
    key = values.get('DASHSCOPE_API_KEY') or values.get('QWEN_API_KEY')
    assert key, 'Explicit env file must contain a nonempty API key'
    with httpx.Client(timeout=60) as client:
        for clip in manifest['clips']:
            directory = args.output_dir / clip['id']
            directory.mkdir()
            request = {'model': MODEL, 'input': {'text': clip['text'], 'voice': VOICE,
                       'format': 'wav', 'sample_rate': 24000, 'instruction': INSTRUCTION}}
            save_json(directory / 'request.json', request)
            attempt = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'started'}
            save_json(directory / 'attempt.json', attempt)
            try:
                response = client.post(ENDPOINT, headers={'Authorization': f'Bearer {key}'}, json=request)
                attempt['http_status'] = response.status_code
                # Preserve the response body while never writing the credential.
                (directory / 'response.txt').write_text(response.text.replace(key, '[REDACTED]'), encoding='utf-8')
                response.raise_for_status()
                payload = response.json()
                audio_response = client.get(payload['output']['audio']['url'])
                attempt['download_http_status'] = audio_response.status_code
                audio_response.raise_for_status()
                raw = audio_response.content
                (directory / 'original.wav').write_bytes(raw)
                audio = convert_wav(raw, directory / 'input-16k.wav')
                clip.update(audio)
                clip['path'] = str(directory / 'input-16k.wav')
                attempt.update(audio)
                assert audio['under_ten_seconds'], f"Complete {clip['id']} audio exceeds the 10-second input cap"
                attempt['status'] = 'complete'
            except Exception as error:
                # No retries or fallback. Save the failed attempt and stop the run.
                attempt.update(status='failed', error_type=type(error).__name__)
                raise RuntimeError(f"TTS {clip['id']} failed; inspect {directory / 'attempt.json'}") from None
            finally:
                attempt['finished_at'] = datetime.now(timezone.utc).isoformat()
                save_json(directory / 'attempt.json', attempt)
                save_json(manifest_path, manifest)
            print(f"{clip['id']}: {clip['seconds']:.3f}s, complete mono 16 kHz WAV")


if __name__ == '__main__':
    main()
