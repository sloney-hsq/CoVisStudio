"""Exercise the real English UI against the local app. Never starts a provider."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'traces' / 'browser-verification'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8050'


def main():
    checks = []
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, timezone_id='Asia/Shanghai')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        context.request.post(BASE + '/api/session', data={'mode': 'text'})
        page.goto(BASE)
        page.get_by_role('button', name='Start with Olist').click()
        expect(page.locator('.chart-card')).to_have_count(3)
        initial = context.request.get(BASE + '/api/bootstrap').json()['state']
        for number in range(1, 4):
            page.get_by_role('button', name=f'Select chart {number}', exact=True).click()
        page.get_by_role('button', name='Edit selection').click()
        page.locator('label.field').filter(has=page.get_by_text('Region', exact=True)).locator('select').select_option('MG')
        page.get_by_role('button', name='Apply changes', exact=True).click()
        expect(page.get_by_role('dialog')).to_have_count(0)
        changed = context.request.get(BASE + '/api/bootstrap').json()['state']
        assert all(v['source']['region'] == 'MG' for v in changed['views'])
        assert [v['source']['categories'] for v in changed['views']] == [v['source']['categories'] for v in initial['views']]
        checks.append('Multi-selection changes all three regions and retains exact categories')
        page.screenshot(path=str(OUT / 'selected-1920.png'), full_page=True)

        page.locator('.journey-node').last.click()
        expect(page.get_by_role('dialog')).to_be_visible()
        expect(page.locator('.node-changes')).to_contain_text('Region')
        expect(page.locator('.node-changes')).to_contain_text('SP')
        expect(page.locator('.node-changes')).to_contain_text('MG')
        page.screenshot(path=str(OUT / 'version-details-1920.png'), full_page=True)
        page.get_by_role('button', name='Close panel').click()
        page.get_by_role('button', name='Undo last change').click()
        page.wait_for_function("document.querySelector('.scope-chips').textContent.includes('SP region')")
        restored = context.request.get(BASE + '/api/bootstrap').json()['state']
        assert restored['views'] == initial['views'] and restored['revision'] > changed['revision']
        checks.append('Journey shows before/after and Undo publishes the original charts in a new version')

        page.get_by_role('button', name='2 column layout').click()
        page.wait_for_function("getComputedStyle(document.querySelector('.chart-grid')).gridTemplateColumns.split(' ').length === 2")
        page.get_by_role('button', name='3 column layout').click()
        page.wait_for_function("getComputedStyle(document.querySelector('.chart-grid')).gridTemplateColumns.split(' ').length === 3")
        checks.append('Two and three column layout controls update the actual grid')

        page.get_by_role('button', name='New session', exact=True).click()
        candidates = page.locator('.task-card').filter(has_text='A new regional perspective').filter(has_text='MG in all three charts')
        candidates.click()
        page.get_by_role('button', name='Start session', exact=True).click()
        expect(page.get_by_role('dialog')).to_have_count(0)
        for number in range(1, 4):
            page.get_by_role('button', name=f'Select chart {number}', exact=True).click()
        page.get_by_role('button', name='Edit selection').click()
        page.locator('label.field').filter(has=page.get_by_text('Region', exact=True)).locator('select').select_option('MG')
        page.get_by_role('button', name='Apply changes', exact=True).click()
        expect(page.get_by_role('dialog')).to_have_count(0)
        page.get_by_role('button', name='Review & export').click()
        expect(page.locator('.report-checks strong').filter(has_text='Not met')).to_have_count(0)
        expect(page.locator('.pending-label')).to_have_text('Pending')
        page.get_by_label('Review notes').fill('Local UI verification only. No participant or model semantics were reviewed.')
        page.get_by_role('button', name='Save review notes').click()
        expect(page.get_by_role('button', name='Notes saved')).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role('link', name='Export session').click()
        download.value.save_as(str(OUT / 'ui-session.json'))
        archive = json.loads((OUT / 'ui-session.json').read_text(encoding='utf-8'))
        assert archive['report']['completed'] is True
        assert archive['report']['review_status'] == 'pending'
        assert archive['reviews'][-1]['classification'] == 'pending'
        assert any(e['name'] == 'image_captured' for e in archive['events'])
        assert any(e['name'] == 'chart_rendered' for e in archive['events'])
        checks.append('Task, automatic outcome, pending human review, notes and full download work through the UI')
        page.screenshot(path=str(OUT / 'review-1920.png'), full_page=True)
        page.get_by_role('button', name='Saved audio', exact=True).click()
        expect(page.get_by_text('No audio was recorded in this session.')).to_be_visible()
        page.get_by_role('button', name='Close panel').click()

        for width, height, scale in [(1920, 1080, 2), (2560, 1440, 1.5), (3840, 2160, 1)]:
            display = browser.new_context(viewport={'width': width, 'height': height}, device_scale_factor=scale, timezone_id='Asia/Shanghai')
            view = display.new_page()
            view.on('pageerror', lambda error: errors.append(str(error)))
            view.goto(BASE)
            expect(view.locator('.chart-card')).to_have_count(3)
            view.wait_for_function("document.querySelectorAll('.chart-plot canvas').length === 3")
            view.wait_for_timeout(200)
            assert not view.evaluate('document.documentElement.scrollWidth > innerWidth')
            view.screenshot(path=str(OUT / f'workspace-{width}-scale{scale}.png'), full_page=True)
            checks.append(f'{width} × {height} CSS, scale {scale}: charts and collaboration panel; no horizontal overflow')
            display.close()
        assert not errors, errors
        checks.append('No browser JavaScript errors')
        (OUT / 'report.json').write_text(json.dumps({'checks': checks, 'errors': errors, 'paid_api_calls': 0,
            'boundary': 'Real browser/manual-tool validation, not model or participant evidence.'}, indent=2), encoding='utf-8')
        browser.close()
    print(json.dumps({'passed': len(checks), 'report': str(OUT / 'report.json')}))


if __name__ == '__main__':
    main()
