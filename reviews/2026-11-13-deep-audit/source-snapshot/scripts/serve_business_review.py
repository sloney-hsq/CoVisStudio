"""Isolated local review; existing services and credentials are untouched."""
from pathlib import Path
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import create_app


if __name__ == '__main__':
    uvicorn.run(create_app({
        'api_key': '', 'text_model': 'qwen3.8-omni-flash', 'realtime_model': 'qwen3.8-omni-flash-realtime',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'voice': 'Maia', 'data_dir': Path('C:/VerbalVis/datasets/olist/data'),
        'trace_dir': ROOT / 'traces' / 'business-review-20261113',
        'frontend_dir': ROOT / 'traces' / 'business-build-20261113' / 'frontend-dist',
    }), host='127.0.0.1', port=8061)
