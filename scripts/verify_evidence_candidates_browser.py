"""Local real-Olist candidate parity and browser receipt check; no provider connection."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback

import uvicorn
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import create_app
from backend.oracle import category_rows, numeric_rows_equal
from scripts.verify_browser_voice import until


async def main():
    output = ROOT / 'traces/jarvis-adaptation-20261113-210751/integration' / ('candidates-' + datetime.now(timezone.utc).strftime('%H%M%S-%f'))
    output.mkdir(parents=True)
    report = {'status': 'running', 'paid_api_calls': 0, 'evidence_kind': 'local_authored', 'checks': {}}
    app = create_app({'api_key': '', 'text_model': 'disabled', 'realtime_model': 'disabled', 'voice': 'Maia',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'frontend_dir': ROOT / 'frontend/dist', 'trace_dir': output / 'sessions'})
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8069, log_level='error'))
    running = asyncio.create_task(server.serve())
    errors, results = [], []
    try:
        await until(lambda: server.started)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            async with await browser.new_context(viewport={'width': 2560, 'height': 1440}) as context:
                page = await context.new_page()
                page.on('pageerror', lambda error: errors.append(error.stack))
                for condition in ('direct', 'bound_revision'):
                    await context.request.post('http://127.0.0.1:8069/api/session', data={'mode': 'text', 'condition': condition, 'task_id': 'exp_01_a'})
                    await page.goto('http://127.0.0.1:8069/', wait_until='networkidle')
                    initial = app.state.workspace.store.snapshot()
                    response = await context.request.post('http://127.0.0.1:8069/api/tools', data={'name': 'list_evidence_candidates', 'arguments': {}})
                    candidates = (await response.json())['result']['candidates']
                    chosen = next(candidate for candidate in candidates if candidate['candidate_id'] == 'chart:3:v1')
                    response = await context.request.post('http://127.0.0.1:8069/api/tools', data={'name': 'apply_evidence_candidate',
                        'arguments': {'candidate_id': chosen['candidate_id'], 'view_ids': ['v2', 'v3'], 'source_patch': {'end': '2017-04-01'}}})
                    receipt = await response.json()
                    final = receipt['state']
                    await expect(page.get_by_role('status', name='Actual chart action')).to_contain_text(f'Charts 2, 3 · Version {final["revision"]}')
                    await until(lambda: {e['details']['view_id'] for e in app.state.workspace.trace.events if e['name'] == 'chart_rendered' and e['details']['revision'] == final['revision']} == {'v1', 'v2', 'v3'})
                    checks = report['checks']
                    checks[condition + '_committed'] = receipt['result']['committed']
                    checks[condition + '_untargeted_unchanged'] = initial['views'][0] == final['views'][0]
                    checks[condition + '_exact_members_current_scope_sql'] = all(
                        view['source'] == {**initial['views'][view['number'] - 1]['source'], 'categories': chosen['members'], 'top_n': None, 'end': '2017-04-01'}
                        and numeric_rows_equal(view['data']['rows'], category_rows(app.state.workspace.data, view['source'])) for view in final['views'][1:])
                    results.append(final)
                    await page.screenshot(path=str(output / (condition + '.png')))
                report['checks']['identical_candidate_semantics'] = all(
                    {key: value for key, value in left.items() if key != 'data'} ==
                    {key: value for key, value in right.items() if key != 'data'} and
                    {key: value for key, value in left['data'].items() if key != 'rows'} ==
                    {key: value for key, value in right['data'].items() if key != 'rows'} and
                    numeric_rows_equal(left['data']['rows'], right['data']['rows'])
                    for left, right in zip(results[0]['views'], results[1]['views'])) and all(
                    results[0][key] == results[1][key] for key in results[0] if key != 'views')
                report['checks']['no_browser_errors'] = not errors
                report.update(status='passed' if all(report['checks'].values()) else 'failed', errors=errors)
                assert all(report['checks'].values()), report
            await browser.close()
    except BaseException as error:
        report.update(status='failed', error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        server.should_exit = True
        await running
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'status': report['status'], 'report': str(output / 'report.json')}))


if __name__ == '__main__':
    asyncio.run(main())
