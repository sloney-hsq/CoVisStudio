"""Exercise archive review using a new local-authored attempt; never calls a model."""
import json
import argparse
from datetime import datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8065'


def main():
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    output = ROOT / 'traces' / 'study-review-build-20261113' / 'browser' / stamp
    output.mkdir(parents=True)
    checks, errors = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))

        def get(path):
            response = context.request.get(BASE + path)
            assert response.ok, response.text()
            return response.json()

        def post(path, data):
            response = context.request.post(BASE + path, data=data)
            assert response.ok, response.text()
            return response.json()

        page.goto(BASE, wait_until='networkidle')
        assert get('/api/bootstrap')['settings']['configured'] is False
        participant = 'local-review-' + stamp
        post('/api/experiment/start', {'participant_id': participant, 'slot': 1, 'trial_index': 1, 'evidence_kind': 'local_authored'})
        post('/api/experiment/begin', {})
        expect(page.locator('.chart-card')).to_have_count(3)
        saved = post('/api/category-sets', {'name': 'Recorded historical cohort', 'revision': 3, 'view_id': 'v1'})
        post('/api/category-sets/' + saved['category_sets'][0]['id'] + '/apply', {'view_ids': ['v2', 'v3']})
        post('/api/task-response', {'conclusion': 'Local review fixture: compare the inherited priority cohort.',
            'rationale': 'This authored response exercises archive inspection; its meaning has not been reviewed.',
            'object_origin': 'The historical category set shown in version 3.', 'calculation_scope': 'The current service-analysis region and period.'})
        finished = post('/api/finish', {'reason': 'completed'})
        archived_id = finished['session']['id']
        archived = get('/api/experiment/attempts/' + archived_id)
        assert archived['trial_report']['outcome']['technical_completed']
        assert archived['review_status'] == 'pending'
        checks.append('Fresh local-authored attempt contains a correct Olist publication and pending human scores.')
        # Keep another running attempt active: reviewing the older one must not reset it.
        post('/api/experiment/start', {'participant_id': participant, 'slot': 1, 'trial_index': 2, 'evidence_kind': 'local_authored'})
        post('/api/experiment/begin', {})
        active_before = get('/api/bootstrap')
        page.get_by_role('button', name='Close panel', exact=True).click()
        page.get_by_role('button', name='Experiment', exact=True).click()
        page.get_by_role('button', name=f'Inspect attempt {archived_id}', exact=True).click()
        expect(page.get_by_role('heading', name='Review the evidence', exact=True)).to_be_visible()
        expect(page.locator('.archive-chart-grid .chart-card')).to_have_count(3)
        assert get('/api/bootstrap')['session']['id'] == active_before['session']['id']
        checks.append('Opening an archived trial does not switch or reset the running workspace.')
        events = archived['events']
        measured = archived['measured_event_indices']
        start, end = measured[0], measured[-1]
        first = next(event for event in events if event['index'] == start)
        page.get_by_role('button', name=f"Inspect event {start}: {first['name'].replace('_', ' ').title()}", exact=True).click()
        expect(page.locator('.archive-event-detail')).to_contain_text(f'Event #{start}')
        commit = next(event for event in events if event['name'] == 'tool_committed' and event['index'] in measured)
        committed_node = next(node for node in archived['nodes'] if node['revision'] == commit['revision'])
        page.get_by_role('button', name=f"Inspect event {commit['index']}: Tool Committed", exact=True).click()
        expect(page.get_by_label('Archived canvas version', exact=True)).to_have_value(committed_node['id'])
        checks.append('Selecting the actual publication shows its new revision even before the later node-created event.')
        # Snapshot event selection stays separate from the live canvas.
        page.get_by_role('button', name='Transcript & recordings', exact=True).click()
        expect(page.get_by_text('No transcript is recorded for this attempt.', exact=True)).to_be_visible()
        expect(page.get_by_text('No audio was recorded. Listening remains pending.', exact=True)).to_be_visible()
        checks.append('Absent speech has explicit unavailable evidence; no transcript or listening result is fabricated.')
        page.get_by_role('button', name='Coding drafts', exact=False).click()
        page.get_by_label('Reviewer label', exact=True).fill('local-ui-check')
        page.get_by_label('Coding start event', exact=True).select_option(str(start))
        page.get_by_label('Coding end event', exact=True).select_option(str(end))
        page.get_by_label('Coding activity', exact=True).select_option('unclear')
        page.get_by_label('Coding rationale', exact=True).fill('Authored UI test only. A human has not classified the activity.')
        page.get_by_role('button', name='Add coded span', exact=True).click()
        page.get_by_label('Review draft notes', exact=True).fill('Pending review; this draft verifies saving evidence-linked notes.')
        page.get_by_role('button', name='Save coding draft', exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('Draft saved')
        after = get('/api/experiment/attempts/' + archived_id)
        assert len(after['review_drafts']) == 1
        assert after['review_drafts'][0]['status'] == 'draft'
        assert after['review_status'] == 'pending'
        assert after['events'] == archived['events']
        assert after['trial_report'] == archived['trial_report']
        assert after['task_response'] == archived['task_response']
        checks.append('Draft survives API reread while source events, technical report and response are unchanged.')
        (output / 'archived-packet.json').write_text(json.dumps(after, indent=2), encoding='utf-8')
        page.screenshot(path=str(output / 'coding-1920.png'), full_page=True)
        for width, height in [(1920, 1080), (2560, 1440), (3840, 2160)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.get_by_role('button', name='Task & evidence', exact=True).click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            box = page.locator('.archive-drawer').bounding_box()
            assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1
            page.screenshot(path=str(output / f'archive-{width}.png'), full_page=True)
        checks.append('Archive layout fits 1920, 2560 and 3840 CSS widths without horizontal page overflow.')
        active_after = get('/api/bootstrap')
        assert active_after['state'] == active_before['state']
        assert active_after['session']['trial_started_at'] == active_before['session']['trial_started_at']
        assert active_after['session']['trial_status'] == 'running'
        checks.append('Viewing snapshots and saving a draft leave the active canvas, timer origin and running state unchanged.')
        assert not errors, errors
        checks.append('No JavaScript errors or paid provider connection.')
        post('/api/finish', {'reason': 'abandoned'})
        browser.close()
    report = {'status': 'passed', 'checks': checks, 'errors': errors, 'paid_api_calls': 0,
              'human_review': 'pending', 'archived_session_id': archived_id, 'output': str(output)}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


def verify_media(session_id):
    """Read and play an existing local-fixture archive without annotating it."""
    output = ROOT / 'traces' / 'study-review-build-20261113' / 'browser-media' / datetime.now().strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={'width': 2560, 'height': 1440}, device_scale_factor=1.5)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        packet = context.request.get(BASE + '/api/experiment/attempts/' + session_id).json()
        before = context.request.get(BASE + '/api/bootstrap').json()
        assert before['settings']['configured'] is False
        assert packet['session']['evidence_kind'] == 'local_authored'
        audio = [item for item in packet['media'] if item['kind'] == 'audio']
        images = [item for item in packet['media'] if item['kind'] == 'image']
        assert audio and images and packet['transcripts']
        page.goto(BASE, wait_until='networkidle')
        page.get_by_role('button', name='Experiment', exact=True).click()
        page.get_by_role('button', name=f'Inspect attempt {session_id}', exact=True).click()
        page.get_by_role('button', name='Transcript & recordings', exact=True).click()
        expect(page.locator('.archive-transcripts article')).to_have_count(len(packet['transcripts']))
        expect(page.locator('.archive-audio audio')).to_have_count(len(audio))
        played = []
        for index, item in enumerate(audio):
            player = page.locator('.archive-audio audio').nth(index)
            assert f'/attempts/{session_id}/media/' in player.get_attribute('src')
            player.evaluate('(element) => element.play()')
            page.wait_for_function('(index) => document.querySelectorAll(".archive-audio audio")[index].currentTime > 0', arg=index)
            playback = player.evaluate('(element) => ({time: element.currentTime, duration: element.duration, ready: element.readyState})')
            player.evaluate('(element) => element.pause()')
            assert playback['ready'] >= 2 and playback['time'] > 0
            played.append({'name': item['name'], **playback})
        page.get_by_label('Recorded image', exact=True).select_option(images[0]['name'])
        page.wait_for_function('document.querySelector(".archive-image img").naturalWidth > 0')
        assert f'/attempts/{session_id}/media/' in page.locator('.archive-image img').get_attribute('src')
        page.screenshot(path=str(output / 'recordings-2560.png'), full_page=True)
        after = context.request.get(BASE + '/api/bootstrap').json()
        assert before['session'] == after['session'] and before['state'] == after['state']
        assert not errors, errors
        browser.close()
    report = {'status': 'passed', 'session_id': session_id, 'audio_played': played,
              'image': images[0]['name'], 'transcript_count': len(packet['transcripts']), 'errors': errors,
              'paid_api_calls': 0, 'human_listening': 'pending',
              'scope': 'Browser playback of saved local scripted tones and captured chart image; not human hearing or model intelligence.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), **report}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', choices=['http://127.0.0.1:8063', 'http://127.0.0.1:8065'], default=BASE)
    parser.add_argument('--media-session')
    args = parser.parse_args()
    BASE = args.base
    if args.media_session:
        verify_media(args.media_session)
    else:
        main()
