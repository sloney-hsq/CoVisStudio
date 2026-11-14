"""Run four assigned business tasks in an isolated current-build browser service.

No environment credentials or existing workspace are used. All human scores
remain pending. Reuses the normal assignment, UI and report acceptance flow.
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import create_app


async def main():
    output = ROOT / 'traces' / 'release-browser' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    app = create_app({'api_key': '', 'text_model': 'disabled', 'realtime_model': 'disabled', 'voice': 'Maia',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'frontend_dir': ROOT / 'frontend/dist',
        'trace_dir': output / 'sessions'})
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8068, log_level='error'))
    running = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(.05)
        with (output / 'browser.log').open('w', encoding='utf-8') as log:
            process = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'scripts/verify_experiment_browser.py'),
                '--base', 'http://127.0.0.1:8068', '--output-dir', str(output), stdout=log, stderr=log)
            code = await process.wait()
        print((output / 'browser.log').read_text(encoding='utf-8'))
        if code:
            raise SystemExit(code)
    finally:
        server.should_exit = True
        await running


if __name__ == '__main__':
    asyncio.run(main())
