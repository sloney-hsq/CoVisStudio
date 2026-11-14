"""Actual local browser checks for saved sets, observation intervals and task responses.

Run only against the separate disabled-key 8061 review service. This script does
not start, restart or connect a model. Every run preserves its own artifacts.
"""
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
    parser.add_argument('--base', default='http://127.0.0.1:8061')
    args = parser.parse_args()
    assert args.base == 'http://127.0.0.1:8061', 'Use the isolated 8061 review service.'
    out = ROOT / 'traces' / 'business-build-20261113' / 'browser' / datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    checks, errors, requests = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
        page = context.new_page()

        def attach():
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append({'method': request.method, 'url': request.url,
                'body': request.post_data if '/api/' in request.url else None}))

        def snapshot():
            return context.request.get(args.base + '/api/bootstrap').json()

        def export():
            return context.request.get(args.base + '/api/export').json()

        def events(name, surface=None, proposal_id=None):
            found = [event for event in export()['events'] if event['name'] == name]
            if surface:
                found = [event for event in found if event.get('details', {}).get('surface') == surface]
            if proposal_id:
                found = [event for event in found if event.get('details', {}).get('proposal_id') == proposal_id]
            return found

        def note(label, data=None):
            checks.append({'label': label, 'data': data})

        def close_panel():
            page.get_by_role('button', name='Close panel', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)

        def start(task_id='biz_01_sp_priorities_mg', condition='direct'):
            page.get_by_role('button', name='New session', exact=True).click()
            page.locator('.study-configuration summary').click()
            page.get_by_label('Study condition').select_option(condition)
            page.locator('.task-card').filter(has=page.get_by_role('heading', name=task_titles[task_id], exact=True)).click()
            page.get_by_role('button', name='Start session', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)
            expect(page.locator('.chart-grid .chart-card')).to_have_count(3)
            result = snapshot()
            assert result['session']['task_id'] == task_id
            assert result['session']['condition'] == condition
            assert not result['category_sets'], 'Saved sets are session scoped.'
            return result['state']

        def select(numbers):
            clear = page.get_by_role('button', name='Clear selection', exact=True)
            if clear.count():
                clear.click()
            for number in numbers:
                page.get_by_role('button', name=f'Select chart {number}', exact=True).click()

        def open_sets():
            page.get_by_role('button', name=re.compile(r'^Saved sets')).click()
            expect(page.locator('.saved-sets-body')).to_be_visible()

        def save(name):
            before = snapshot()['state']
            page.get_by_label('Set name', exact=True).fill(name)
            page.get_by_role('button', name='Save category set', exact=True).click()
            expect(page.locator('.saved-set-card').filter(has=page.get_by_role('heading', name=name, exact=True))).to_be_visible()
            saved = next(item for item in snapshot()['category_sets'] if item['name'] == name)
            assert snapshot()['state'] == before, 'Saving members is not a chart edit.'
            return saved

        def history(subset=None):
            before = snapshot()['state']
            page.locator('.journey-node').filter(has=page.locator('.node-version', has_text=re.compile('^v3$'))).click()
            expect(page.locator('.history-title')).to_contain_text('Version 3')
            if subset is not None:
                buttons = page.locator('.history-member-selection').first.get_by_role('button')
                for index in range(buttons.count()):
                    if index not in subset:
                        buttons.nth(index).click()
            assert snapshot()['state'] == before

        def apply_set(name):
            page.get_by_role('button', name=f'Apply {name} to selected charts', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)
            return snapshot()['state']

        def assert_scope(before, after, indices, members):
            for index, (old, current) in enumerate(zip(before['views'], after['views'])):
                if index not in indices:
                    assert current == old, 'A view outside the selected target set changed.'
                else:
                    assert current['source']['categories'] == members
                    assert current['source']['top_n'] is None
                    for field in ['region', 'start', 'end', 'status', 'metric']:
                        assert current['source'][field] == old['source'][field], field

        def preview():
            before = snapshot()['state']
            page.get_by_role('button', name='Preview revision', exact=True).click()
            expect(page.locator('.proposal-state')).to_contain_text('Review the proposed change')
            result = snapshot()
            assert result['state'] == before
            return result['proposal']

        def download(filename):
            with page.expect_download() as pending:
                page.get_by_role('link', name='Export session', exact=True).click()
            pending.value.save_as(str(out / filename))
            return json.loads((out / filename).read_text(encoding='utf-8'))

        attach()
        try:
            initial = snapshot()
            assert initial['settings']['configured'] is False
            task_titles = {task['id']: task['title'] for task in initial['tasks']}
            assert len([key for key in task_titles if key.startswith('biz_')]) == 4
            page.goto(args.base)
            expect(page.get_by_role('button', name='New session', exact=True)).to_be_visible()
            before = start()
            select([1])
            open_sets()
            expect(page.locator('.set-session-note')).to_contain_text('Saved in this session')
            current = save('Current MG comparison')
            assert current['members'] == [row['label'] for row in before['views'][0]['data']['rows']]
            assert current['evidence']['revision'] == before['revision']
            close_panel()
            note('Current selected category chart saves its actual members and provenance without editing the canvas')

            history([0, 2])
            page.get_by_role('button', name='Save set from chart 1 version 3', exact=True).click()
            subset = save('Earlier SP subset')
            assert len(subset['members']) == 2
            assert subset['evidence']['revision'] == 3 and subset['evidence']['source']['region'] == 'SP'
            page.screenshot(path=str(out / 'saved-historical-subset.png'), full_page=False)
            close_panel()
            select([2])
            open_sets()
            expect(page.locator('.set-targets')).to_contain_text('Charts 2')
            after = apply_set('Earlier SP subset')
            assert_scope(before, after, [1], subset['members'])
            assert snapshot()['proposal'] is None
            assert not events('revision_card_visible')
            note('Direct condition applies a named historical subset to chart 2 only, retaining MG and other current conditions, without a revision card')

            history()
            page.get_by_role('button', name='Save set from chart 1 version 3', exact=True).click()
            full = save('SP service priorities')
            close_panel()
            select([2, 3])
            open_sets()
            before = snapshot()['state']
            after = apply_set('SP service priorities')
            assert_scope(before, after, [1, 2], full['members'])
            page.get_by_role('button', name='View task', exact=True).click()
            expect(page.locator('.analysis-brief')).to_contain_text('Required outcomes')
            response = {'conclusion': 'Local UI verification response; a recommendation requires human review.',
                'rationale': 'The current MG low-review and delivery charts compare the saved SP categories; the unchanged MG order-volume chart supplies local context.',
                'object_origin': 'The categories came from chart 1 in Journey version 3, originally computed for SP.',
                'calculation_scope': 'Current MG, 2017-01-01 inclusive to 2018-01-01 exclusive, delivered orders; each chart keeps its own measure and denominator.'}
            page.get_by_label('Conclusion', exact=True).fill(response['conclusion'])
            page.get_by_label('Evidence and rationale', exact=True).fill(response['rationale'])
            page.get_by_label('Where did the compared categories come from?', exact=True).fill(response['object_origin'])
            page.get_by_label('Which region, dates and measure produced the displayed values?', exact=True).fill(response['calculation_scope'])
            page.get_by_role('button', name='Save response', exact=True).click()
            expect(page.get_by_role('button', name='Response saved', exact=True)).to_be_visible()
            expect(page.locator('.task-response-status .pending-label')).to_have_text('Pending')
            page.screenshot(path=str(out / 'business-response-pending.png'), full_page=False)
            for field, value in response.items():
                assert snapshot()['task_response'][field] == value
            close_panel()
            page.get_by_role('button', name='Review & export', exact=True).click()
            expect(page.locator('.pending-label')).to_have_text('Pending')
            direct_export = download('direct-business-session.json')
            assert direct_export['report']['review_status'] == 'pending'
            assert direct_export['report']['technical_completed'] is True
            assert direct_export['report']['understanding_correct'] is None
            assert len(direct_export['category_sets']) == 3
            assert direct_export['task_response']['conclusion'] == response['conclusion']
            close_panel()
            note('Business brief, conclusion/rationale and object/scope understanding response save and export; human interpretation stays pending')

            page.get_by_role('button', name='Undo last change', exact=True).click()
            expect(page.locator('.version-label')).to_have_text(f"v{after['revision'] + 1}")
            page.get_by_role('button', name='View task', exact=True).click()
            expect(page.locator('.response-stale')).to_contain_text('Charts changed')
            expect(page.get_by_label('Conclusion', exact=True)).to_have_value(response['conclusion'])
            expect(page.get_by_role('button', name='Save response', exact=True)).to_be_visible()
            close_panel()
            page.get_by_role('button', name='Review & export', exact=True).click()
            expect(page.locator('.task-response-review .response-stale')).to_contain_text('Charts changed')
            stale_export = download('direct-business-stale-response.json')
            assert stale_export['report']['task_response_status'] == 'stale'
            assert stale_export['report']['task_response_current'] is False
            assert stale_export['task_response']['conclusion'] == response['conclusion']
            close_panel()
            page.get_by_role('button', name='View task', exact=True).click()
            page.get_by_role('button', name='Save response', exact=True).click()
            expect(page.get_by_role('button', name='Response saved', exact=True)).to_be_visible()
            expect(page.locator('.response-stale')).to_have_count(0)
            assert snapshot()['task_response']['revision'] == snapshot()['state']['revision']
            close_panel()
            note('A later chart revision marks the saved response stale, preserves its text, and requires explicit resave for the current version')

            before = start(condition='bound_revision')
            select([1])
            open_sets()
            method_set = save('Method current members')
            close_panel()
            select([2])
            open_sets()
            after = apply_set('Method current members')
            assert_scope(before, after, [1], method_set['members'])
            note('The same saved-set operations are available in the method condition')

            history()
            page.get_by_role('button', name='Use chart 1 version 3 as evidence', exact=True).click()
            select([2, 3])
            page.get_by_role('button', name='Plan a revision', exact=True).click()
            proposed = preview()
            pid = proposed['id']
            # Automatic detail display after preview counts as displayed, not a user-open action.
            expect(page.locator('[data-revision-surface="detail"]')).to_be_visible()
            page.wait_for_function("document.querySelector('[data-revision-surface=detail]').getBoundingClientRect().top < innerHeight")
            assert not events('revision_card_visible', 'summary', pid), 'The drawer covers the summary.'
            close_panel()
            page.locator('.proposal-summary').scroll_into_view_if_needed()
            expect(page.locator('.proposal-summary')).to_be_in_viewport()
            # An API round trip follows browser rendering and drains the WS observations.
            page.wait_for_timeout(80)
            assert events('revision_card_visible', 'summary', pid)
            assert events('revision_card_hidden', 'detail', pid)
            page.locator('.proposal-summary').click()
            expect(page.locator('.revision-change-card')).to_have_count(2)
            page.wait_for_timeout(80)
            assert events('revision_card_opened', proposal_id=pid)
            assert events('revision_card_hidden', 'summary', pid)
            assert events('revision_card_visible', 'detail', pid)
            page.screenshot(path=str(out / 'method-detail-observed.png'), full_page=False)
            page.get_by_role('button', name='Revise proposal', exact=True).click()
            expect(page.get_by_role('button', name='Preview revision', exact=True)).to_be_visible()
            assert events('revision_card_revision_requested', proposal_id=pid)
            proposed = preview()
            applied_id = proposed['id']
            page.get_by_role('button', name='Apply revision', exact=True).click()
            expect(page.locator('.proposal-state')).to_contain_text('Applied to the canvas')
            assert events('revision_confirmation_clicked', proposal_id=applied_id)
            close_panel()
            page.get_by_role('button', name='Review & export', exact=True).click()
            method_export = download('method-observations-session.json')
            assert method_export['report']['technical_completed'] is True
            assert method_export['report']['understanding_correct'] is None
            expect(page.locator('.review-observations')).to_contain_text('Cards generated')
            expect(page.locator('.review-observations')).to_contain_text('User confirmed')
            visible = [event for event in method_export['events'] if event['name'] == 'revision_card_visible']
            hidden = [event for event in method_export['events'] if event['name'] == 'revision_card_hidden']
            by_id = {event['details']['display_id']: event for event in visible}
            assert len(by_id) == len(visible)
            assert {event['details']['surface'] for event in visible} == {'summary', 'detail'}
            for event in hidden:
                opened = by_id[event['details']['display_id']]
                assert event['client_ms'] >= opened['client_ms']
                assert abs(event['details']['duration_ms'] - (event['client_ms'] - opened['client_ms'])) < .01
            assert set(by_id) == {event['details']['display_id'] for event in hidden}
            note('Actual summary/detail DOM exposure intervals close on covering/unmount; explicit open, revise and confirmation clicks remain distinct',
                {'visible_intervals': len(visible), 'closed_intervals': len(hidden)})
            context.close()

            for width, height, scale in [(1920, 1080, 2), (2560, 1440, 1.5), (3840, 2160, 1)]:
                context = browser.new_context(viewport={'width': width, 'height': height}, device_scale_factor=scale)
                page = context.new_page(); attach(); page.goto(args.base)
                start(condition='bound_revision')
                select([2, 3])
                open_sets(); save('Viewport categories')
                assert not page.locator('.drawer').evaluate('(el) => el.scrollWidth > el.clientWidth')
                page.screenshot(path=str(out / f'sets-{width}-scale{scale}.png'), full_page=False)
                close_panel()
                history()
                page.get_by_role('button', name='Use chart 1 version 3 as evidence', exact=True).click()
                page.get_by_role('button', name='Plan a revision', exact=True).click()
                preview(); close_panel()
                expect(page.locator('.chart-grid .chart-card')).to_have_count(3)
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                page.screenshot(path=str(out / f'workspace-{width}-scale{scale}.png'), full_page=False)
                page.locator('.proposal-summary').click()
                expect(page.locator('.revision-change-card')).to_have_count(2)
                assert not page.locator('.drawer').evaluate('(el) => el.scrollWidth > el.clientWidth')
                page.screenshot(path=str(out / f'revision-{width}-scale{scale}.png'), full_page=False)
                close_panel()
                page.get_by_role('button', name='View task', exact=True).click()
                expect(page.get_by_label('Conclusion', exact=True)).to_be_visible()
                assert not page.locator('.drawer').evaluate('(el) => el.scrollWidth > el.clientWidth')
                page.screenshot(path=str(out / f'task-{width}-scale{scale}.png'), full_page=False)
                note(f'{width}x{height} CSS at {scale} scale: canvas, sets, revision details and task response have no horizontal overflow')
                context.close()
            assert not errors, errors
            note('No browser JavaScript errors')
            result = {'status': 'passed', 'checks': checks, 'errors': errors, 'paid_api_calls': 0,
                'boundary': 'Actual browser and real local Olist only. Observation is display exposure, not reading or understanding. No model or participant result.'}
            (out / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        except Exception:
            if not page.is_closed():
                page.screenshot(path=str(out / 'first-failure.png'), full_page=False)
            (out / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            (out / 'report.json').write_text(json.dumps({'status': 'failed', 'checks': checks, 'errors': errors}, indent=2), encoding='utf-8')
            raise
        finally:
            (out / 'requests.json').write_text(json.dumps(requests, indent=2), encoding='utf-8')
            browser.close()
    print(json.dumps({'passed': len(checks), 'output': str(out)}))


if __name__ == '__main__':
    main()
