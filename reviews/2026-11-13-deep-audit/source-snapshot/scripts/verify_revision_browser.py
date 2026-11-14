"""Exercise the revision UI using real local Olist tools, with no model calls."""
import argparse
import json
import re
import traceback
from datetime import datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8060')
    args = parser.parse_args()
    out = ROOT / 'traces' / 'revision-build-20261113' / 'browser' / datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    checks, errors, requests = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append({'method': request.method, 'url': request.url, 'body': request.post_data if '/api/' in request.url else None}))

        def snapshot():
            return context.request.get(args.base + '/api/bootstrap').json()

        initial = snapshot()
        assert initial['settings']['configured'] is False, 'Run against the disabled-key review server.'
        task_titles = {task['id']: task['title'] for task in initial['tasks']}

        def note(label, data=None):
            checks.append({'label': label, 'data': data})

        def start(task, condition='bound_revision'):
            page.get_by_role('button', name='New session', exact=True).click()
            page.locator('.study-configuration summary').click()
            page.get_by_label('Study condition').select_option(condition)
            page.locator('.task-card').filter(has=page.get_by_role('heading', name=task_titles[task], exact=True)).click()
            page.get_by_role('button', name='Start session', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)
            expect(page.locator('.chart-grid .chart-card')).to_have_count(3)
            data = snapshot()
            assert data['session']['task_id'] == task
            assert data['session']['condition'] == condition
            return data['state']

        def evidence(indices=None):
            before = snapshot()['state']
            page.locator('.journey-node').filter(has=page.locator('.node-version', has_text=re.compile('^v3$'))).click()
            expect(page.get_by_role('dialog')).to_be_visible()
            expect(page.locator('.history-title')).to_contain_text('Version 3')
            if indices is not None:
                members = page.locator('.history-member-selection').first.get_by_role('button')
                for index in range(members.count()):
                    if index not in indices:
                        members.nth(index).click()
                page.screenshot(path=str(out / 'historical-subset-selection.png'), full_page=True)
            page.get_by_role('button', name='Use chart 1 version 3 as evidence', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)
            expect(page.locator('.evidence-strip')).to_contain_text('SP')
            data = snapshot()
            assert data['state'] == before, 'Selecting historical evidence must not restore an older canvas.'
            assert data['evidence']['source']['region'] == 'SP'
            return data['evidence']

        def select(numbers):
            for number in numbers:
                page.get_by_role('button', name=f'Select chart {number}', exact=True).click()

        def open_revision():
            page.get_by_role('button', name='Plan a revision', exact=True).click()
            expect(page.locator('.revision-body')).to_be_visible()

        def preview():
            before = snapshot()['state']
            page.get_by_role('button', name='Preview revision', exact=True).click()
            expect(page.get_by_role('button', name='Apply revision', exact=True)).to_be_visible()
            data = snapshot()
            assert data['state'] == before, 'Preview must not publish charts.'
            return data['proposal']

        def apply():
            page.get_by_role('button', name='Apply revision', exact=True).click()
            expect(page.locator('.proposal-state')).to_contain_text('Applied to the canvas')
            data = snapshot()
            assert data['proposal']['status'] == 'committed'
            return data['state']

        def close_panel():
            page.get_by_role('button', name='Close panel', exact=True).click()

        try:
            page.goto(args.base)
            expect(page.get_by_role('button', name='New session', exact=True)).to_be_visible()
            before = start('rev_dev_01')
            old = evidence()
            select([1, 2, 3])
            open_revision()
            expect(page.locator('.revision-reference-block').first).to_contain_text('SP')
            expect(page.locator('.current-reference')).to_contain_text('MG')
            card = preview()['card']
            assert card['binding_applied'] is True
            assert card['evidence']['members'] == old['members']
            page.screenshot(path=str(out / 'bound-preview-1920.png'), full_page=True)
            after = apply()
            for previous, current in zip(before['views'], after['views']):
                assert current['source']['categories'] == old['members']
                for field in ['region', 'start', 'end', 'status', 'metric']:
                    assert current['source'][field] == previous['source'][field]
            note('Historical SP evidence is applied to current MG views without restoring old filters', {'before_revision': before['revision'], 'after_revision': after['revision'], 'members': old['members']})
            close_panel()
            page.get_by_role('button', name='Review & export', exact=True).click()
            expect(page.locator('.pending-label')).to_have_text('Pending')
            expect(page.locator('.report-checks strong').filter(has_text='Not met')).to_have_count(0)
            page.screenshot(path=str(out / 'bound-review-pending.png'), full_page=True)
            with page.expect_download() as download:
                page.get_by_role('link', name='Export session', exact=True).click()
            download.value.save_as(str(out / 'bound-session.json'))
            exported = json.loads((out / 'bound-session.json').read_text(encoding='utf-8'))
            assert exported['report']['review_status'] == 'pending'
            assert exported['report']['completed'] is True
            assert exported['report']['first_commit_correct'] is True
            assert exported['report']['counts']['evidence_selected'] == 1
            assert exported['report']['counts']['revision_applied'] == 1
            note('Outcome passes while human review remains pending; session downloaded through the UI')
            close_panel()

            page.get_by_role('button', name='Undo last change', exact=True).click()
            expect(page.locator('.version-label')).to_have_text('v8')
            undone = snapshot()['state']
            assert undone['views'] == before['views'] and undone['revision'] > after['revision']
            page.locator('.journey-node').filter(has=page.locator('.node-version', has_text=re.compile('^v7$'))).click()
            expect(page.locator('.history-reference-note').first).to_contain_text('Evidence from version 3')
            page.get_by_role('button', name='Restore this canvas', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)
            restored = snapshot()['state']
            assert restored['views'] == after['views'] and restored['revision'] > undone['revision']
            note('Undo and Restore remain separate from evidence selection, and Journey retains source/target provenance')

            before = start('rev_dev_02')
            old = evidence()
            select([2])
            open_revision()
            page.get_by_label('Revision measure', exact=True).select_option('revenue')
            preview()
            after = apply()
            assert after['views'][0] == before['views'][0]
            assert after['views'][2] == before['views'][2]
            assert after['views'][1]['source']['metric'] == 'revenue'
            assert after['views'][1]['source']['categories'] == old['members']
            assert after['views'][1]['source']['region'] == 'MG'
            note('Local revision changes chart 2 only, including its metric; charts 1 and 3 are byte-equivalent')
            close_panel()

            start('rev_hold_02')
            old = evidence([0, 2])
            assert len(old['members']) == 2
            select([1, 2, 3])
            open_revision()
            preview()
            after = apply()
            assert all(view['source']['categories'] == old['members'] and view['source']['region'] == 'MG' for view in after['views'])
            note('Historical evidence supports an explicitly selected first/third category subset without restoring old scope')
            close_panel()

            before = start('rev_dev_03')
            select([1, 2, 3])
            open_revision()
            page.get_by_role('radio', name='Choose a new ranking').check()
            preview()
            after = apply()
            for previous, current in zip(before['views'], after['views']):
                assert current['source']['categories'] is None
                assert current['source']['top_n'] == 3
                assert current['source']['rank_by'] == 'orders'
                assert current['source']['region'] == previous['source']['region'] == 'MG'
                assert current['source']['metric'] == previous['source']['metric']
            note('Reranking releases the fixed member set and calculates the current MG top 3')
            close_panel()

            start('rev_dev_01', 'unbound_preview')
            old = evidence()
            select([1, 2, 3])
            open_revision()
            expect(page.get_by_role('button', name='Preview revision', exact=True)).to_be_disabled()
            assert page.get_by_label('Explicit categories to apply').evaluate('(el) => [...el.selectedOptions].length') == 0
            page.get_by_label('Explicit categories to apply').select_option(old['members'])
            proposal = preview()
            assert proposal['card']['binding_applied'] is False
            after = apply()
            assert all(view['source']['categories'] == old['members'] for view in after['views'])
            note('Unbound preview starts with no implicit member values and uses the explicit manual selection')
            close_panel()

            before = start('rev_dev_01', 'direct')
            old = evidence()
            select([1, 2, 3])
            expect(page.get_by_role('button', name='Plan a revision', exact=True)).to_have_count(0)
            expect(page.get_by_role('button', name='Use in a revision')).to_have_count(0)
            page.get_by_role('button', name='Edit selection', exact=True).click()
            page.get_by_role('button', name='Fixed categories', exact=True).click()
            page.locator('.category-select').select_option(old['members'])
            page.get_by_role('button', name='Apply changes', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)
            after = snapshot()['state']
            assert all(set(view['source']['categories']) == set(old['members']) and view['source']['region'] == 'MG' for view in after['views'])
            assert snapshot()['proposal'] is None
            note('Direct editing has the same readable historical evidence and current target controls, without revision cards')

            assert not errors, errors
            context.close()
            for width, height, scale in [(1920, 1080, 2), (2560, 1440, 1.5), (3840, 2160, 1)]:
                context = browser.new_context(viewport={'width': width, 'height': height}, device_scale_factor=scale)
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(args.base)
                # Each browser connection owns its pending work. Prepare within this connection.
                start('rev_dev_01')
                evidence()
                select([1, 2, 3])
                open_revision()
                preview()
                close_panel()
                expect(page.locator('.chart-grid .chart-card')).to_have_count(3)
                page.wait_for_function("document.querySelectorAll('.chart-grid .chart-plot canvas').length === 3")
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                page.screenshot(path=str(out / f'workspace-{width}-scale{scale}.png'), full_page=True)
                page.locator('.proposal-summary').click()
                expect(page.locator('.revision-change-card')).to_have_count(3)
                expect(page.get_by_role('button', name='Apply revision', exact=True)).to_be_visible()
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                assert not page.locator('.drawer').evaluate('(el) => el.scrollWidth > el.clientWidth')
                page.screenshot(path=str(out / f'revision-{width}-scale{scale}.png'), full_page=True)
                note(f'{width}x{height} CSS at {scale} scale: workspace and revision card have no horizontal overflow')
                context.close()
            assert not errors, errors
            note('No browser JavaScript errors')
            report = {'status': 'passed', 'checks': checks, 'errors': errors, 'paid_api_calls': 0, 'boundary': 'Actual browser and local Olist tools only; no model or human-study result.'}
            (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        except Exception:
            page.screenshot(path=str(out / 'first-failure.png'), full_page=True)
            (out / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            (out / 'report.json').write_text(json.dumps({'status': 'failed', 'checks': checks, 'errors': errors}, indent=2), encoding='utf-8')
            raise
        finally:
            (out / 'requests.json').write_text(json.dumps(requests, indent=2), encoding='utf-8')
            browser.close()
    print(json.dumps({'passed': len(checks), 'output': str(out)}))


if __name__ == '__main__':
    main()
