"""Offline narrated replay from recorded input and actual output sample receipts.

This is a derived replay, not a new system-audio recording. Video alignment uses
the first traced screencast frame; timing is limited by frame/receipt precision.
"""
import argparse
from array import array
import audioop
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import wave
import zipfile

import imageio_ffmpeg

RATE = 24000


def played_chunks(events, video_server_ms):
    """Keep only observed played samples, with gaps and interruption preserved."""
    bases, chunks = {}, {}
    for event in events:
        if not event['name'].startswith('playback_'):
            continue
        detail = event.get('details', {})
        rid = detail.get('response_id')
        if event['name'] == 'playback_start':
            bases[rid] = ((event['aligned_server_ms'] - video_server_ms) / 1000
                          - detail['audio_context_time'])
        if rid not in bases:
            continue
        for chunk in detail.get('chunks', []):
            count = chunk['played_samples_in_chunk']
            key = (rid, chunk['chunk_id'])
            if count <= chunks.get(key, {}).get('samples', 0):
                continue
            rate = detail['sample_rate']
            chunks[key] = dict(kind='assistant', response_id=rid,
                chunk_id=chunk['chunk_id'], source_start=chunk['sample_start'],
                samples=count, rate=rate,
                start=bases[rid] + detail['audio_context_time'] - count / rate)
    return list(chunks.values())


def read_pcm(path, start=0, count=None):
    with wave.open(str(path), 'rb') as source:
        assert source.getnchannels() == 1 and source.getsampwidth() == 2
        source.setpos(start)
        pcm = source.readframes(count if count is not None else source.getnframes())
        rate = source.getframerate()
    if rate != RATE:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, RATE, None)
    return array('h', pcm)


def render(run):
    run = Path(run).resolve()
    report = json.loads((run / 'report.json').read_text(encoding='utf-8'))
    events = report['events']
    session = Path(report['session_directory'])
    if not session.is_absolute():
        session = Path(__file__).resolve().parents[1] / session
    with zipfile.ZipFile(run / 'browser-trace.zip') as archive:
        trace = [json.loads(line) for line in archive.read('trace.trace').splitlines()]
    first_frame = next(item for item in trace if item['type'] == 'screencast-frame')
    anchor = events[0]
    server_origin = datetime.fromisoformat(anchor['at']).timestamp() * 1000 - anchor['server_ms']
    video_server_ms = first_frame['frameSwapWallTime'] - server_origin
    calibration = next(event for event in events if event['name'] == 'clock_calibrated')
    chunks = played_chunks(events, video_server_ms)
    inputs = []
    for segment in report['browser_input_segments']:
        inputs.append(dict(kind='user', name=segment['name'],
            start=(segment['started_client_ms'] + calibration['offset_ms'] - video_server_ms) / 1000,
            seconds=segment['duration']))
    original = next((run / 'video').glob('*.webm'))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    metadata = subprocess.run([ffmpeg, '-hide_banner', '-i', str(original)], capture_output=True, text=True).stderr
    match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', metadata)
    duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    mix = array('i', [0]) * (round(duration * RATE) + 1)
    for clip in inputs + chunks:
        if clip['kind'] == 'user':
            pcm = read_pcm(run / f"{clip['name']}.wav")
        else:
            pcm = read_pcm(session / f"output-{clip['response_id']}.wav", clip['source_start'], clip['samples'])
        offset = round(clip['start'] * RATE)
        assert offset >= 0 and offset + len(pcm) <= len(mix), 'Audio interval must fit the original video'
        for index, value in enumerate(pcm, offset):
            mix[index] += value
    peak = max(abs(value) for value in mix)
    gain = min(1.0, 32000 / max(1, peak))
    output = array('h', (round(value * gain) for value in mix))
    mixed = run / 'video' / 'replay-audio.wav'
    with wave.open(str(mixed), 'wb') as target:
        target.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        target.writeframes(output.tobytes())
    destination = run / 'video' / 'recording-with-audio.mp4'
    subprocess.run([ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
        '-i', str(original), '-i', str(mixed), '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', str(destination)], check=True)
    audit = dict(video=str(destination), original_video=str(original), duration_seconds=duration,
        alignment='First traced screencast frame and calibrated browser clock; frame/receipt precision, not sample-exact video sync',
        audio_kind='Derived replay: complete injected input clips and only played assistant samples',
        mix_gain=gain, inputs=inputs, assistant_chunks=chunks,
        assistant_played_samples=sum(clip['samples'] for clip in chunks),
        paid_api_calls=0)
    (run / 'video' / 'audio-alignment.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    print(render(parser.parse_args().run))
