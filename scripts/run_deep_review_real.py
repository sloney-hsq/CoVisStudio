"""Run only the two authorized review diagnostics; default performs no API calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'traces/real-study-20261113-224313'
TRIALS = [('02', 'direct'), ('03', 'bound_revision')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Explicitly permit exactly two real voice attempts, without retries.')
    parser.add_argument('--env-file', type=Path, help='Explicit credential file, required only with --execute.')
    parser.add_argument('--output-dir', type=Path, required=True, help='New evidence directory; must not already exist.')
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend/dist')
    parser.add_argument('--port', type=int, default=8076)
    args = parser.parse_args()
    if args.execute and args.env_file is None:
        parser.error('--execute requires --env-file')
    # Verify every original recording before allowing either model connection.
    audio = {}
    for case, condition in TRIALS:
        original = json.loads((SOURCE / f'{case}-{condition}/report.json').read_text(encoding='utf-8'))
        for name, expected in original['audio'].items():
            path = SOURCE / 'audio' / f'{name}.wav'
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == expected['sha256'], f'Original recording changed: {name}'
            with wave.open(str(path), 'rb') as recording:
                assert recording.getparams()[:3] == (1, 2, 16000)
                seconds = recording.getnframes() / recording.getframerate()
            assert 0 < seconds < 10, f'Complete recording exceeds input cap: {name}'
            audio[name] = {'path': str(path), 'sha256': digest, 'seconds': seconds}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    summary = {'created_at': datetime.now(timezone.utc).isoformat(), 'execute': args.execute,
               'maximum_voice_attempts': 2 if args.execute else 0, 'automatic_retries': 0,
               'tts_calls': 0, 'source_archive': str(SOURCE), 'audio': audio, 'trials': []}
    destination = args.output_dir / 'wrapper-report.json'
    for case, condition in TRIALS:
        directory = args.output_dir / f'{case}-{condition}'
        command = [sys.executable, str(ROOT / 'scripts/verify_real_study_matrix.py'),
                   '--case', case, '--condition', condition, '--audio-dir', str(SOURCE / 'audio'),
                   '--output-dir', str(directory), '--frontend-dir', str(args.frontend_dir), '--port', str(args.port)]
        if args.execute:
            command += ['--run-real', '--env-file', str(args.env_file)]
        entry = {'case': case, 'condition': condition, 'command': command, 'status': 'started'}
        summary['trials'].append(entry)
        destination.write_text(json.dumps(summary, indent=2), encoding='utf-8')
        # Each child invokes the original driver exactly once and preserves its own
        # budget stop, first-tool-failure stop, awaited cleanup and original score.
        with (args.output_dir / f'{case}-{condition}.stdout.txt').open('w', encoding='utf-8') as stdout, \
             (args.output_dir / f'{case}-{condition}.stderr.txt').open('w', encoding='utf-8') as stderr:
            completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
        entry.update(status='finished', exit_code=completed.returncode, report=str(directory / 'report.json'))
        destination.write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(entry), flush=True)
    if any(trial['exit_code'] for trial in summary['trials']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
