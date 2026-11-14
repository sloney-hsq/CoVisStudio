"""Actual-browser offline research handoff. Explicit fixture coding, no API/model."""
import asyncio
from copy import deepcopy
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
from backend.intent_scoring import coding_template


async def main():
    output = ROOT / 'traces/route-delivery' / datetime.now(timezone.utc).strftime('review-browser-%H%M%S')
    output.mkdir(parents=True)
    report = {'evidence': 'Local authored UI and SQL verification; imported codings are fixtures, not human judgments.',
              'paid_api_calls': 0, 'checks': [], 'human_listening': 'pending'}
    def checked(name, value):
        report['checks'].append({'name': name, 'passed': bool(value)})
        assert value, name
    app = create_app({'api_key': '', 'text_model': 'disabled', 'realtime_model': 'disabled', 'voice': 'Maia',
        'text_url': 'http://127.0.0.1:9/disabled', 'realtime_url': 'ws://127.0.0.1:9/disabled',
        'data_dir': Path('C:/VerbalVis/datasets/olist/data'), 'frontend_dir': ROOT / 'frontend/dist',
        'trace_dir': output / 'sessions'})
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8087, log_level='error'))
    running = asyncio.create_task(server.serve())
    browser = None
    try:
        while not server.started:
            await asyncio.sleep(.05)
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto('http://127.0.0.1:8087')
            async def post(path, body):
                response = await page.request.post('http://127.0.0.1:8087' + path, data=body)
                assert response.ok, await response.text()
                return await response.json()
            prepared = await post('/api/experiment/start', {'protocol': 'formal', 'slot': 1, 'trial_index': 1,
                                  'participant_id': 'LOCAL-REVIEW-FIXTURE', 'evidence_kind': 'local_authored'})
            await post('/api/experiment/begin', {})
            evidence = (await post('/api/evidence', {'revision': 3, 'view_id': 'v1'}))['evidence']
            proposal = (await post('/api/revisions/preview', {'view_ids': ['v2', 'v3'], 'source_patch': {},
                        'member_action': 'use_evidence',
                        'label': 'Use the selected historical group in both service charts; retain current scope.'}))['proposal']
            await post(f"/api/revisions/{proposal['id']}/apply", {})
            await post('/api/task-response', {field: 'Authored verification response. Human interpretation pending.' for field in
                       ('conclusion', 'rationale', 'object_origin', 'calculation_scope', 'target_views', 'kept_released')})
            await post('/api/finish', {})
            session_id = prepared['session']['id']
            original = (output / 'sessions' / session_id / 'session.json').read_bytes()
            events = app.state.workspace.trace.events
            onset = next(e['index'] for e in events if e['name'] == 'request_accepted')
            terminal = next(e['index'] for e in events if e['name'] == 'trial_finished')
            await page.get_by_label('Close panel', exact=True).click()
            await page.get_by_role('button', name='Experiment', exact=True).click()
            await expect(page.get_by_label(f'Inspect attempt {session_id}')).to_be_visible()
            await page.get_by_label(f'Inspect attempt {session_id}').click()
            await page.get_by_role('button', name='Independent intent review', exact=True).click()
            await page.get_by_label('Intent onset event').select_option(str(onset))
            await page.get_by_label('Intent input end event').fill(str(onset))
            checked('primary episode defaults to task terminal', await page.get_by_label('Intent episode end event').input_value() == str(terminal))
            await page.get_by_role('button', name='Prepare blinded packet', exact=True).click()
            await expect(page.get_by_role('button', name='Download blinded packet', exact=True)).to_be_visible()
            async with page.expect_download() as download:
                await page.get_by_role('button', name='Download blinded packet', exact=True).click()
            destination = output / 'downloaded-blinded-packet.json'
            await (await download.value).save_as(destination)
            packet = json.loads(destination.read_text(encoding='utf-8'))
            checked('blind export contains public brief and input, no outcome or condition',
                    bool(packet['public_task']) and bool(packet['participant_input'])
                    and not {'final', 'report', 'condition', 'expected_sources'} & packet.keys())
            checked('cannot score before independent coding lock', await page.get_by_role('button', name='Score against locked intent', exact=True).is_disabled())
            coder = coding_template(packet)
            coder['intent']['source_requirement'] = {'mode': 'none', 'candidate_id': None, 'reason': 'Authored fixture requests scope changes without a new historical source.'}
            coder.update(reviewer_id='FIXTURE-A', status='completed')
            coder['intent'].update(status='resolved', target_view_ids=['v2', 'v3'], source_patch={},
                 members={'mode': 'fixed', 'values': evidence['members'], 'origin': {'revision': 3, 'view_id': 'v1'}},
                 retained_fields=['region', 'start', 'end', 'metric'], released_fields=['top_n'],
                 reason='Authored fixture from explicit selected evidence; not human annotation.', evidence_indices=[onset])
            imports = {'Coder A': coder, 'Coder B': {**deepcopy(coder), 'reviewer_id': 'FIXTURE-B'},
                       'Adjudication': {'reviewer_id': 'FIXTURE', 'reason': 'Authored UI verification.', 'intent': coder['intent']}}
            for label, value in imports.items():
                await page.get_by_label(label + ' JSON file').set_input_files({'name': label + '.json',
                     'mimeType': 'application/json', 'buffer': json.dumps(value).encode()})
            await page.get_by_role('button', name='Lock imported coding', exact=True).click()
            await expect(page.get_by_role('button', name='Independent coding locked', exact=True)).to_be_visible()
            await page.get_by_label('Endpoint reviewer', exact=True).fill('FIXTURE')
            await page.get_by_label('Endpoint rationale', exact=True).fill('Only final task revision, ending at trial terminal.')
            await page.get_by_role('button', name='Designate final task endpoint', exact=True).click()
            await expect(page.get_by_text('This is the designated final task endpoint.', exact=True)).to_be_visible()
            await page.get_by_role('button', name='Score against locked intent', exact=True).click()
            await expect(page.get_by_text('Score recorded', exact=True)).to_be_visible()
            response = await page.request.get(f'http://127.0.0.1:8087/api/experiment/attempts/{session_id}')
            episode = (await response.json())['intent_episodes'][0]
            checked('SQL result and locked terminal exposed in archive', episode['final_correct'] is True and episode['primary'] and episode['locked'])
            checked('human understanding and listening remain pending', all(v is None for v in episode['understanding'].values()) and episode['human_listening'] == 'pending')
            checked('original attempt preserved', (output / 'sessions' / session_id / 'session.json').read_bytes() == original)
            checked('no private coding in online context', 'FIXTURE-A' not in app.state.workspace.context())
            await page.screenshot(path=str(output / 'intent-review-1920.png'), full_page=True)
            checked('no horizontal overflow', await page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            checked('no page errors', not errors)
            report.update(status='passed', page_errors=errors, session_id=session_id)
            await browser.close()
            browser = None
    except Exception:
        report.update(status='failed', traceback=traceback.format_exc())
        raise
    finally:
        if browser:
            await browser.close()
        server.should_exit = True
        await running
        if report.get('status') == 'passed':
            checked('original attempt survives browser and server shutdown',
                    (output / 'sessions' / report['session_id'] / 'session.json').read_bytes() == original)
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(output)


if __name__ == '__main__':
    asyncio.run(main())
