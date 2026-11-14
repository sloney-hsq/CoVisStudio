"""Actual-browser revision correction with real local Olist and disabled providers."""
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
from backend.oracle import numeric_rows_equal
from scripts.verify_browser_voice import until


async def main():
    output = ROOT / 'traces/revision-support-final-20261113' / ('browser-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    output.mkdir(parents=True)
    report = {'status': 'running', 'evidence_kind': 'local_authored', 'paid_api_calls': 0, 'checks': {}}
    app = create_app({'api_key': '', 'text_model': 'qwen3.8-omni-flash', 'realtime_model': 'qwen3.8-omni-flash-realtime', 'voice': 'Maia',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'frontend_dir': ROOT / 'frontend/dist', 'trace_dir': output / 'sessions'})
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8078, log_level='error'))
    running = asyncio.create_task(server.serve())
    errors, requests, finals = [], [], []
    page = None
    try:
        await until(lambda: server.started)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda req: requests.append({'url': req.url, 'method': req.method, 'body': req.post_data}) if '/api/' in req.url else None)
            base = 'http://127.0.0.1:8078'

            async def post(path, payload):
                response = await context.request.post(base + path, data=payload)
                assert response.ok, (path, response.status, await response.text())
                return await response.json()

            async def snapshot():
                return await (await context.request.get(base + '/api/bootstrap')).json()

            async def rendered(revision):
                await until(lambda: {event['details']['view_id'] for event in app.state.workspace.trace.events
                    if event['name'] == 'chart_rendered' and event['details']['revision'] == revision} == {'v1', 'v2', 'v3'})

            async def apply_ui():
                await page.get_by_role('button', name='Apply revision', exact=True).last.click()
                await expect(page.get_by_role('dialog')).to_have_count(0)
                await expect(page.locator('.revision-support')).to_contain_text('Revision committed')
                data = await snapshot()
                assert data['proposal']['status'] == 'committed'
                await rendered(data['state']['revision'])
                return data

            for condition in ('direct', 'bound_revision'):
                await post('/api/session', {'mode': 'text', 'condition': condition, 'task_id': 'exp_01_a'})
                await page.goto(base, wait_until='networkidle')
                initial = (await snapshot())['state']
                await rendered(initial['revision'])
                assert len({v['source']['metric'] for v in initial['views']}) == 3
                candidates = (await post('/api/tools', {'name': 'list_evidence_candidates', 'arguments': {}}))['result']['candidates']
                chosen = next(item for item in candidates if item['candidate_id'] == 'chart:3:v1')
                await post('/api/evidence', {'revision': 3, 'view_id': 'v1'})
                saved = (await post('/api/tools', {'name': 'save_category_set', 'arguments': {
                    'name': 'MG comparison', 'revision': 6, 'view_id': 'v1'}}))['result']['category_set']
                overridden = await post('/api/tools', {'name': 'revise_analysis', 'arguments': {
                    'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence', 'candidate_id': 'chart:1:v1'}})
                await rendered(overridden['state']['revision'])
                provenance = overridden['result']['revision_card']['execution_provenance']
                assert provenance['overrides_selection'] and provenance['members_equal']
                if condition == 'bound_revision':
                    await expect(page.locator('.revision-brief .provenance-notice')).to_contain_text('Selected Chart 1 · version 3; used Chart 1 · version 1')
                    await page.screenshot(path=str(output / 'source-version-mismatch.png'), full_page=True)
                report['checks'][condition + '_equal_members_distinct_sources'] = True
                receipt = await post('/api/tools', {'name': 'revise_analysis', 'arguments': {
                    'view_ids': ['v2', 'v3'], 'member_action': 'use_evidence', 'candidate_id': chosen['candidate_id'],
                    'question': 'Use the historical group in charts 2 and 3; keep the current MG scope and measures.'}})
                reused = receipt['state']
                await expect(page.locator('.revision-support')).to_contain_text('Revision committed')
                await rendered(reused['revision'])
                assert reused['views'][0] == initial['views'][0]
                for old, new in zip(initial['views'][1:], reused['views'][1:]):
                    assert new['source'] == {**old['source'], 'categories': chosen['members'], 'top_n': None}
                report['checks'][condition + '_historical_members_current_scope'] = True
                if condition == 'bound_revision':
                    summary = page.locator('.revision-brief')
                    await expect(page.locator('.revision-support')).to_contain_text('System interpretation')
                    for text in ('Object origin', 'Current computation', 'Fixed categories (3)', 'MG', 'Charts 1 stay unchanged'):
                        await expect(summary).to_contain_text(text)
                    await page.get_by_role('button', name='Details', exact=True).click()
                    await expect(page.locator('.revision-sections')).to_contain_text('Current computation & changes')
                    await page.get_by_role('button', name='Summary', exact=True).click()
                    summary_box = await page.locator('.revision-support [data-revision-surface="summary"]').first.bounding_box()
                    footer_box = await page.locator('.revision-support-footer').first.bounding_box()
                    assert footer_box['y'] >= summary_box['y'] + summary_box['height'] - 1
                    report['checks']['revision_actions_do_not_cover_summary'] = True
                    report['checks']['b2_explicit_origin_scope_membership_untouched'] = True
                else:
                    await expect(page.locator('.revision-brief')).to_have_count(0)
                    report['checks']['b0_no_structured_card'] = True
                await page.screenshot(path=str(output / (condition + '-historical-reuse.png')), full_page=True)

                # A different visible selection must not change the card's correction targets.
                await page.get_by_role('button', name='Select chart 1', exact=True).click()
                await expect(page.get_by_role('button', name='Deselect chart 1', exact=True)).to_have_text('01')
                report['checks'][condition + '_selected_chart_number_visible'] = True
                await page.get_by_role('button', name='Correct interpretation', exact=True).click()
                await expect(page.locator('.revision-body')).to_be_visible()
                targets = page.locator('.revision-targets button')
                assert await targets.evaluate_all('(buttons) => buttons.filter(b => b.getAttribute("aria-pressed") === "true").map(b => b.querySelector(".target-number").textContent)') == ['02', '03']
                for label in ('Revision measure', 'Revision region', 'Revision start date', 'Revision end date'):
                    assert await page.get_by_label(label, exact=True).input_value() == ''
                if condition == 'bound_revision':
                    await page.get_by_label('Revision category source', exact=True).select_option('set:' + saved['id'])
                    reference = page.locator('.revision-reference-block').first
                    await expect(reference).to_contain_text('Saved set: MG comparison · MG · Chart 1 · v6')
                    assert await reference.locator('.member-tags span').count() == len(saved['members'])
                    await page.get_by_label('Revision category source', exact=True).select_option('chart:3:v1')
                    await expect(reference).to_contain_text('RJ · Chart 1 · v3')
                    report['checks']['saved_set_metadata_follows_selected_set'] = True
                await page.get_by_label('Revision end date', exact=True).fill('2017-04-01')
                async with page.expect_request(lambda req: req.url.endswith('/api/revisions/preview')) as pending:
                    await page.get_by_role('button', name='Preview revision', exact=True).click()
                sent = (await pending.value).post_data_json
                assert sent['view_ids'] == ['v2', 'v3'] and sent['source_patch'] == {'end': '2017-04-01'}, sent
                await expect(page.get_by_role('button', name='Apply revision', exact=True).last).to_be_visible()
                corrected = (await apply_ui())['state']
                assert corrected['views'][0] == reused['views'][0]
                for old, new in zip(reused['views'][1:], corrected['views'][1:]):
                    assert new['source'] == {**old['source'], 'end': '2017-04-01'}
                report['checks'][condition + '_correction_targets_patch_metrics_rendered'] = True
                event_names = {event['name'] for event in app.state.workspace.trace.events}
                assert {'revision_card_revision_requested', 'revision_confirmation_clicked', 'revision_confirmed'} <= event_names
                if condition == 'bound_revision':
                    assert {'revision_card_visible', 'revision_card_opened'} <= event_names
                report['checks'][condition + '_actual_correction_confirmation_observations'] = True
                finals.append(corrected)
                await page.screenshot(path=str(output / (condition + '-corrected.png')), full_page=True)

                if condition == 'bound_revision':
                    await page.get_by_role('button', name='Correct interpretation', exact=True).click()
                    await page.locator('.revision-targets button').nth(2).click()
                    await page.get_by_role('radio', name='Choose a new ranking').check()
                    await page.get_by_role('button', name='Preview revision', exact=True).click()
                    await expect(page.get_by_role('button', name='Apply revision', exact=True).last).to_be_visible()
                    reranked = (await apply_ui())['state']
                    assert reranked['views'][0] == corrected['views'][0]
                    assert reranked['views'][2] == corrected['views'][2]
                    assert reranked['views'][1]['source'] == {**corrected['views'][1]['source'], 'categories': None, 'top_n': 3, 'rank_by': 'orders'}
                    await expect(page.locator('.revision-brief')).to_contain_text('Dynamic top 3 by')
                    await expect(page.locator('.revision-brief')).to_contain_text('Charts 1, 3 stay unchanged')
                    await expect(page.locator('.revision-brief .provenance-notice')).to_contain_text('Selected, not used for this edit')
                    assert (await snapshot())['proposal']['card']['evidence'] is None
                    report['checks']['rerank_one_view_release_others_fixed_rendered'] = True
                    for width, height in ((1920, 1080), (2560, 1440), (3840, 2160)):
                        await page.set_viewport_size({'width': width, 'height': height})
                        await page.locator('.revision-support').scroll_into_view_if_needed()
                        assert not await page.evaluate('document.documentElement.scrollWidth > innerWidth')
                        assert not await page.locator('.collaboration-panel').evaluate('(el) => el.scrollWidth > el.clientWidth')
                        await page.screenshot(path=str(output / f'workspace-{width}.png'), full_page=True)
                        report['checks'][f'layout_{width}_no_overflow'] = True
                    await page.get_by_role('button', name='Correct interpretation', exact=True).click()
                    for width, height in ((1920, 1080), (2560, 1440), (3840, 2160)):
                        await page.set_viewport_size({'width': width, 'height': height})
                        assert not await page.locator('.drawer').evaluate('(el) => el.scrollWidth > el.clientWidth')
                        button = await page.get_by_role('button', name='Preview revision', exact=True).bounding_box()
                        assert button['y'] >= 0 and button['y'] + button['height'] <= height
                        assert await page.locator('.drawer-backdrop').evaluate('(el) => getComputedStyle(el).backdropFilter') == 'none'
                        report['checks'][f'correction_{width}_preview_visible_canvas_unblurred'] = True
                        await page.screenshot(path=str(output / f'correction-{width}.png'), full_page=True)
                    await page.get_by_role('button', name='Close panel', exact=True).click()
            (output / 'corrected-states.json').write_text(json.dumps(finals, indent=2), encoding='utf-8')
            assert all(finals[0][key] == finals[1][key] for key in finals[0] if key != 'views')
            for left, right in zip(finals[0]['views'], finals[1]['views']):
                assert {key: value for key, value in left.items() if key != 'data'} == {key: value for key, value in right.items() if key != 'data'}
                assert {key: value for key, value in left['data'].items() if key != 'rows'} == {key: value for key, value in right['data'].items() if key != 'rows'}
                assert numeric_rows_equal(left['data']['rows'], right['data']['rows'])
            report['checks']['b0_b2_identical_corrected_state'] = True
            report['checks']['no_browser_errors'] = not errors
            assert not errors, errors
            report['status'] = 'passed'
            await context.close()
            await browser.close()
    except BaseException as error:
        report.update(status='failed', error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        server.should_exit = True
        await running
        report.update(errors=errors, service_closed=True)
        (output / 'requests.json').write_text(json.dumps(requests, indent=2), encoding='utf-8')
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'status': report['status'], 'report': str(output / 'report.json')}))


if __name__ == '__main__':
    asyncio.run(main())
