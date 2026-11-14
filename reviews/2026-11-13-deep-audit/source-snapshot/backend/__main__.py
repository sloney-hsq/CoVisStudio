"""Launch the current source and frontend build; opening the app calls no model."""
import argparse
from pathlib import Path

import uvicorn

from .app import create_app
from .settings import ROOT, load_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8066)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    settings = load_settings(args.env_file)
    settings.update(
        frontend_dir=ROOT / 'frontend' / 'dist',
        trace_dir=ROOT / 'traces' / 'studio',
        review_archive_dirs=[ROOT / 'traces' / 'experiment-review-final-20261113',
                             ROOT / 'traces' / 'study-review-20261113',
                             ROOT / 'traces' / 'studio-live-20261113',
                             *sorted((ROOT / 'traces' / 'assigned-voice').glob('*/sessions')),
                             *sorted((ROOT / 'traces' / 'live-browser').glob('*/sessions'))],
    )
    uvicorn.run(create_app(settings), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
