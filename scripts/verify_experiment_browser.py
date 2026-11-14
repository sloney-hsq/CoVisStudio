"""Real browser, Olist and assigned-task lifecycle against a local disabled-key service."""
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
    parser.add_argument('--base', default='http://127.0.0.1:8062')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    assert args.base.startswith('http://127.0.0.1:')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    out = args.output_dir or ROOT / 'traces' / 'experiment-build-20261113' / 'browser' / stamp
    out.mkdir(parents=True, exist_ok=True)
    checks, errors, requests = [], [], []
    participant_id = 'local-browser-' + stamp
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

        def note(label, data=None):
            checks.append({'label': label, 'data': data})

        def close_panel():
            page.get_by_role('button', name='Close panel', exact=True).click()
            expect(page.get_by_role('dialog')).to_have_count(0)

        def select(numbers):
            clear = page.get_by_role('button', name='Clear selection', exact=True)
            if clear.count():
                clear.click()
            for number in numbers:
                page.get_by_role('button', name=f'Select chart {number}', exact=True).click()

        def historical_reference(save=False):
            page.locator('.journey-node').filter(has=page.locator('.node-version', has_text=re.compile('^v3$'))).click()
            expect(page.locator('.history-title')).to_contain_text('Version 3')
            if save:
                page.get_by_role('button', name='Save set from chart 1 version 3', exact=True).click()
                page.get_by_label('Set name', exact=True).fill('Historical service cohort')
                page.get_by_role('button', name='Save category set', exact=True).click()
                expect(page.locator('.saved-set-card')).to_have_count(1)
                close_panel()
            else:
                page.get_by_role('button', name='Use chart 1 version 3 as evidence', exact=True).click()
                expect(page.get_by_role('dialog')).to_have_count(0)

        def save_response():
            page.get_by_role('button', name='View task', exact=True).click()
            page.get_by_label('Conclusion', exact=True).fill('Authored browser check: service interpretation requires human review.')
            page.get_by_label('Evidence and rationale', exact=True).fill('The selected views use Olist results. This fixture does not establish a business recommendation.')
            page.get_by_label('Where did the compared categories come from?', exact=True).fill('Selected according to the public task requirement; see the saved chart history and tool receipt.')
            page.get_by_label('Which region, dates and measure produced the displayed values?', exact=True).fill('The current source scope and metric are recorded in the final chart state.')
            page.get_by_role('button', name='Save response', exact=True).click()
            expect(page.get_by_role('button', name='Response saved', exact=True)).to_be_visible()
            close_panel()

        def perform(trial):
            family = trial['task_id'].split('_')[1]
            if trial['condition'] == 'direct':
                if family in ('01', '03'):
                    historical_reference(save=True)
                    select([2, 3])
                    page.get_by_role('button', name=re.compile('^Saved sets')).click()
                    page.get_by_role('button', name='Apply Historical service cohort to selected charts', exact=True).click()
                elif family == '02':
                    select([1, 2, 3])
                    page.get_by_role('button', name='Edit selection', exact=True).click()
                    page.get_by_role('button', name='Dynamic ranking', exact=True).click()
                    page.get_by_label('Number of groups', exact=True).fill('3')
                    page.get_by_label('Rank by', exact=True).select_option('orders')
                    page.get_by_role('button', name='Apply changes', exact=True).click()
                else:
                    select([1])
                    page.get_by_role('button', name='Edit selection', exact=True).click()
                    page.get_by_label('Measure', exact=True).select_option('revenue')
                    page.get_by_role('button', name='Apply changes', exact=True).click()
            else:
                if family in ('01', '03'):
                    historical_reference()
                select([2, 3] if family in ('01', '03') else [1, 2, 3] if family == '02' else [1])
                page.get_by_role('button', name='Plan a revision', exact=True).click()
                if family == '02':
                    page.get_by_role('radio', name=re.compile('Choose a new ranking')).check()
                if family == '04':
                    page.get_by_label('Revision measure', exact=True).select_option('revenue')
                page.get_by_role('button', name='Preview revision', exact=True).click()
                expect(page.locator('.proposal-state')).to_contain_text('Review the proposed change')
                page.get_by_role('button', name='Apply revision', exact=True).click()
                expect(page.locator('.proposal-state')).to_contain_text('Applied to the canvas')
                close_panel()
            expect(page.get_by_role('dialog')).to_have_count(0)
            save_response()

        attach()
        try:
            initial = snapshot()
            assert not initial['settings']['configured']
            assert len(initial['experiment_tasks']) == 8
            if initial['session'].get('assignment') and initial['session']['trial_status'] != 'finished':
                # A separate rerun archives the previous local attempt, never overwrites it.
                context.request.post(args.base + '/api/finish', data={'reason': 'abandoned'})
            page.goto(args.base)
            page.get_by_role('button', name='Experiment', exact=True).click()
            page.get_by_label('Experiment participant', exact=True).fill(participant_id)
            page.get_by_label('Allocation slot', exact=True).fill('1')
            page.get_by_role('button', name='Load assignment', exact=True).click()
            expect(page.locator('.assignment-list > button')).to_have_count(4)
            plan = context.request.get(args.base + '/api/experiment/plan?slot=1').json()
            assert [trial['condition'] for trial in plan['trials']].count('direct') == 2
            assert len({trial['family_id'] for trial in plan['trials']}) == 4
            page.locator('.matched-library summary').click()
            expect(page.locator('.matched-task-row')).to_have_count(8)
            page.screenshot(path=str(out / 'assignment.png'), full_page=False)
            page.get_by_role('button', name='Prepare assigned task 1', exact=True).click()
            note('Four-task allocation has four distinct families, two tasks per condition and eight available matched versions')
            for index, trial in enumerate(plan['trials']):
                expect(page.get_by_role('button', name='Begin task', exact=True)).to_be_visible()
                ready = snapshot()
                assert ready['session']['trial_status'] == 'ready'
                assert ready['session']['assignment']['trial_index'] == index + 1
                assert not ready['session'].get('trial_started_at')
                assert page.locator('main.main-layout').get_attribute('inert') is not None
                assert not any(event['name'] == 'trial_started' for event in export()['events'])
                page.get_by_role('button', name='Begin task', exact=True).click()
                expect(page.locator('.trial-curtain')).to_have_count(0)
                expect(page.locator('.task-clock')).to_be_visible()
                assert snapshot()['session']['trial_status'] == 'running'
                perform(trial)
                page.get_by_role('button', name='Finish task', exact=True).click()
                expect(page.locator('.trial-review')).to_be_visible()
                record = export()
                (out / f'trial-{index+1}.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
                report = record['report']['trial_report']
                assert report['outcome']['technical_completed']
                assert report['outcome']['review_status'] == 'pending'
                assert report['outcome']['understanding_correct'] is None
                assert report['identity']['condition'] == trial['condition']
                assert report['timing']['elapsed_seconds'] is not None
                assert report['human_review']['repair_turns'] is None
                if trial['condition'] == 'direct' and trial['task_id'].startswith('exp_01'):
                    assert report['process']['interaction']['category_sets']['application_count'] == 1
                    assert report['process']['interaction']['revision_cards']['generated_count'] == 0
                if trial['condition'] == 'bound_revision':
                    assert report['process']['interaction']['revision_cards']['user_confirmed_count'] == 1
                    assert report['process']['tools']['started']['preview_revision'] == 1
                page.screenshot(path=str(out / f'trial-{index+1}-report.png'), full_page=False)
                note(f"Assigned task {index+1}: {trial['task_id']} / {trial['condition']} completes actual UI/Olist path with pending interpretation")
                if index < 3:
                    page.get_by_role('button', name='Prepare next task', exact=True).last.click()
                else:
                    close_panel()
            page.get_by_role('button', name='Experiment', exact=True).click()
            page.get_by_role('button', name='Refresh records', exact=True).click()
            expect(page.locator('.experiment-summary')).to_be_visible()
            aggregate = context.request.get(args.base + '/api/experiment/report').json()
            (out / 'aggregate-complete.json').write_text(json.dumps(aggregate, indent=2), encoding='utf-8')
            participant = next(item for item in aggregate['participants'] if item['participant_id'] == participant_id)
            assert all(item['observed'] == 2 and item['missing'] == 0 and item['technical_correct'] == 2 for item in participant['conditions'].values())
            for format in ('json', 'csv'):
                with page.expect_download() as pending:
                    page.get_by_role('link', name=format.upper(), exact=True).click()
                pending.value.save_as(str(out / f'experiment.{format}'))
            page.get_by_label('Experiment participant', exact=True).fill(participant_id + '-unfinished')
            page.get_by_label('Allocation slot', exact=True).fill('5')
            page.get_by_role('button', name='Load assignment', exact=True).click()
            page.get_by_role('button', name='Assigned task 1', exact=True).click()
            page.get_by_role('button', name='Prepare assigned task 1', exact=True).click()
            page.get_by_role('button', name='Begin task', exact=True).click()
            page.get_by_role('button', name='End unfinished', exact=True).click()
            expect(page.locator('.trial-review')).to_contain_text('Abandoned')
            unfinished = export()
            assert unfinished['report']['trial_report']['outcome']['terminal_reason'] == 'abandoned'
            assert unfinished['report']['trial_report']['timing']['time_censored']
            (out / 'unfinished.json').write_text(json.dumps(unfinished, indent=2), encoding='utf-8')
            note('Unified JSON/CSV retains successful and unfinished records, separate evidence kinds and pending human coding')
            close_panel()
            for width, height, scale in [(1920,1080,2),(2560,1440,1.5),(3840,2160,1)]:
                if page.viewport_size != {'width':width,'height':height} or scale != 2:
                    page.close(); context.close()
                    context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=scale)
                    page=context.new_page(); attach(); page.goto(args.base)
                expect(page.locator('.trial-finished-controls')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(out / f'finished-{width}.png'),full_page=False)
                page.get_by_role('button',name='Experiment',exact=True).click()
                expect(page.locator('.assignment-list>button')).to_have_count(4)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(out / f'assignment-{width}.png'),full_page=False)
                close_panel()
                page.get_by_role('button',name='Review task',exact=True).click()
                expect(page.locator('.trial-review')).to_be_visible()
                page.screenshot(path=str(out / f'review-{width}.png'),full_page=False)
                close_panel()
                note(f'{width}x{height} CSS at {scale}: assignment, locked task and unified report render without overflow')
            assert not errors, errors
            note('No JavaScript errors; no model connection or paid API request')
            result={'status':'passed','checks':checks,'errors':errors,'paid_api_calls':0,
                    'boundary':'Authored browser workflow with real Olist. No model or participant result. Human review pending.'}
            (out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        except Exception:
            page.screenshot(path=str(out/'failure.png'),full_page=False)
            (out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
            (out/'report.json').write_text(json.dumps({'status':'failed','checks':checks,'errors':errors},indent=2),encoding='utf-8')
            raise
        finally:
            (out/'requests.json').write_text(json.dumps(requests,indent=2),encoding='utf-8')
            browser.close()
    print(json.dumps({'passed':len(checks),'output':str(out)}))


if __name__ == '__main__':
    main()
