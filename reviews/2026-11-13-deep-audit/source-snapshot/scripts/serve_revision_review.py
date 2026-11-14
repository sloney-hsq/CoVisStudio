"""Serve this build locally with model connections disabled; leave existing sessions alone."""
import argparse
from pathlib import Path
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import create_app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8060)
    args = parser.parse_args()
    settings = {
        'api_key': '', 'text_model': 'qwen3.8-omni-flash', 'realtime_model': 'qwen3.8-omni-flash-realtime',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'voice': 'Maia', 'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
        'trace_dir': ROOT / 'traces' / 'revision-review-20261113',
        'frontend_dir': ROOT / 'traces' / 'revision-build-20261113' / 'frontend-dist',
    }
    uvicorn.run(create_app(settings), host='127.0.0.1', port=args.port)
