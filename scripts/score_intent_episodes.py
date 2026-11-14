"""Offline intent handoff: prepare -> two human codings -> lock -> SQL score."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.intent_scoring import create_episode, lock_intent, score_episode, write_new


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'lock', 'score'))
    parser.add_argument('--session-dir', required=True, type=Path)
    parser.add_argument('--episode', help='Packet ID returned by prepare.')
    parser.add_argument('--onset', type=int)
    parser.add_argument('--utterance-end', type=int)
    parser.add_argument('--episode-end', type=int)
    parser.add_argument('--data-dir', type=Path, default=Path('C:/VerbalVis/datasets/olist/data'))
    args = parser.parse_args()
    archive = read(args.session_dir / 'session.json')
    if args.action == 'prepare':
        print(json.dumps(create_episode(args.session_dir, args.onset, args.utterance_end,
                        args.episode_end, archive['session'].get('evidence_kind', 'unspecified')), indent=2))
        return
    directory = args.session_dir / 'intent-episodes' / args.episode
    packet = read(directory / 'packet.json')
    if args.action == 'lock':
        result = lock_intent(packet, read(directory / 'coder-a.json'), read(directory / 'coder-b.json'),
                             read(directory / 'adjudication.json'))
        output = directory / 'locked.json'
    else:
        from backend.data import OlistData
        data = OlistData(args.data_dir)
        try:
            result = score_episode(archive, packet, read(directory / 'locked.json'),
                                   read(directory / 'private.json')['end_event_index'], data)
        finally:
            data.close()
        output = directory / 'score.json'
    write_new(output, result)
    print(output)


if __name__ == '__main__':
    main()
