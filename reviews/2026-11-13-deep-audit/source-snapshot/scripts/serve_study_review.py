"""Local study records and coding drafts; no credentials or remote provider."""
from pathlib import Path
import argparse
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import create_app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8065)
    args = parser.parse_args()
    uvicorn.run(create_app({
        'api_key': '', 'text_model': 'qwen3.8-omni-flash', 'realtime_model': 'qwen3.8-omni-flash-realtime',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'voice': 'Maia', 'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
        'trace_dir': ROOT / 'traces' / 'study-review-20261113',
        'review_archive_dirs': [ROOT / 'traces' / 'experiment-review-final-20261113',
                                *sorted((ROOT / 'traces' / 'assigned-voice').glob('*/sessions'))],
        'frontend_dir': ROOT / 'traces' / 'study-review-build-20261113' / 'frontend-dist',
    }), host='127.0.0.1', port=args.port)
