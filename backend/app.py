"""Single-workspace service: tools, public commits, model transport and evidence."""
import asyncio
import base64
import hashlib
import json
import wave
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from jsonschema import ValidationError

from .charts import ChartStore, TOOL_DEFINITIONS
from .model_contract import model_tool_definitions, compile_model_arguments
from .data import OlistData
from .settings import ROOT, load_settings
from .study import tasks, diagnostic_tasks, experiment_tasks, task_brief, setup_operations, evaluate
from .experiment import allocation_for, allocation_table, build_trial_report, aggregate_reports, report_csv
from .experiment import (formal_allocation_for, formal_allocation_table, formal_manifest,
                         formal_primary_attempts, formal_assignment_csv)
from .formal_tasks import FORMAL_PROTOCOL, formal_tasks
from .intent_scoring import (create_episode, lock_intent, score_episode, write_new, episode_index,
                             review_understanding, attach_formal_scores, designate_primary_episode)
from .revisions import prepare_revision, normalize_revise_analysis, evidence_source, REVISION_TOOL_DEFINITIONS, CONDITIONS
from .category_sets import CategorySets, CATEGORY_SET_TOOL_DEFINITIONS
from .observations import interaction_summary
from .trace import Trace
from .evidence import EvidenceStore
from .delivery import summarize_delivery
from .evidence_candidates import (build_candidates, resolve_candidate, prepare_candidate_apply,
                                  EVIDENCE_CANDIDATE_TOOL_DEFINITIONS)
from .review_packets import build_review_packet, save_review_draft, read_trial_archives, attach_review_drafts


INSTRUCTIONS = """You are CoVis, an analytical collaborator. Speak and write concise English.
Use the provided tools to make real chart edits. A spoken promise is not execution.
Create a new chart with create_chart, including the first chart on an empty canvas.
To change an existing chart's query, call revise_analysis before speaking: name the current view_ids,
member_action, and only the flat fields the user changed. That call computes and commits the edit.
For a date-only correction, use member_action="keep_current" and change only the requested date fields.
Dates are start-inclusive and end-exclusive. Derive the year and exact target IDs from the current analysis and user selection.
For historical reuse, follow revise_analysis's candidate_id selection rule. Never serialize evidence into a string.
If a choice is unresolved, set needs_confirmation=true and question; do not invent an answer.
Read saved charts before making numerical claims. Only claim an edit after its committed receipt.
Keep every source condition not explicitly changed. Fixed category IDs and dynamic top-N are different:
'keep these categories' means the exact visible IDs, not a new ranking. Rates are within-group rates;
never sum or renormalize review rates or delivery means. Exclude freight from revenue.
Historical evidence supplies category identities; calculate their values under the current target chart's
region, dates, order conditions and metric unless the user explicitly changes those fields.
A later explicit request to re-rank or release fixed categories replaces the earlier membership choice.
Preserve still-valid conditions and untargeted charts; different charts may intentionally compare different categories.
Reference context records the chart version and selection associated with the request; it does not prove attention.
The current public state may be newer. Do not equate a generated explanation with words already played.
Use the explicit reference when the user says 'these' or 'this chart'. Ask one short question if scope is ambiguous.
The same tools are available in every interaction mode. Do not automatically synchronize other charts;
apply shared edits only when requested. Reply briefly and distinguish changed, unchanged and unexecuted work.
You may discuss an observation without editing. Never invent measurements, study scores or user intentions.
execution_state is the runtime's account of actual commits, not an assistant interpretation.
If it records no commit for a request, that request did not change the charts, regardless of prior speech.
Cancelled, unexecuted calls changed nothing. If their work still applies, issue a new tool call under
the current request. For any follow-up revision, do not assume that earlier promised work ran:
read current_dashboard and the recorded outcomes, then resolve the still-requested changes.
"""

CONDITION_OPTIONS = [
    {'id': 'direct', 'label': 'Direct editing', 'description': 'Complete evidence and shared chart tools; the model resolves references.'},
    {'id': 'bound_revision', 'label': 'Evidence-linked revision', 'description': 'Use a historical object set in the current analysis with an explicit revision card.'},
    {'id': 'unbound_preview', 'label': 'Preview without binding', 'description': 'The same revision card; categories must be explicitly supplied rather than bound from evidence.'},
]
HISTORY_TOOL = {'type': 'function', 'function': {
    'name': 'read_history',
    'description': 'Read the same committed evidence available in every study condition. Omit revision for a version index; give revision to read its complete chart state. Reading never restores a version.',
    'parameters': {'type': 'object', 'properties': {'revision': {'type': 'integer', 'minimum': 0}}, 'additionalProperties': False},
}}
MODEL_TOOLS = model_tool_definitions([
    *TOOL_DEFINITIONS, HISTORY_TOOL, *REVISION_TOOL_DEFINITIONS,
    *CATEGORY_SET_TOOL_DEFINITIONS, *EVIDENCE_CANDIDATE_TOOL_DEFINITIONS])


def media_summary(value):
    if isinstance(value, list):
        return [media_summary(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if isinstance(item, str) and (key in ('audio', 'image') or key == 'delta' and value.get('type', '') == 'response.audio.delta' or key == 'url' and item.startswith('data:image/')):
                encoded = item.split(',', 1)[1] if item.startswith('data:') else item
                result[key] = {'encoded_characters': len(encoded), 'sha256': hashlib.sha256(base64.b64decode(encoded)).hexdigest()}
            else:
                result[key] = media_summary(item)
        return result
    return value


class Workspace:
    def __init__(self, settings):
        self.settings = settings
        self.data = OlistData(settings['data_dir'])
        self.socket = None
        self.send_lock = asyncio.Lock()
        self.tool_lock = asyncio.Lock()
        self.epoch = 0
        self.text_task = None
        self.voice = None
        self.voice_closing = None
        self.voice_timer = None
        self.trial_timer = None
        self.reset('text', None, '')

    def reset(self, mode, task_id, participant_id, condition='bound_revision'):
        self.store = ChartStore(self.data)
        self.session = {'id': uuid4().hex[:12], 'mode': mode, 'task_id': task_id,
                        'participant_id': participant_id, 'started_at': datetime.now(timezone.utc).isoformat(),
                        'models': {'text': self.settings['text_model'], 'voice': self.settings['realtime_model']},
                        'used_modes': [], 'condition': condition}
        self.session['instructions_sha256'] = hashlib.sha256(self.instructions().encode('utf-8')).hexdigest()
        self.trace = Trace(self.settings['trace_dir'] / self.session['id'])
        self.evidence_store = EvidenceStore(self.trace)
        self.evidence_package = None
        self.nodes = []
        self.snapshots = {0: self.store.snapshot()}
        self.revision_origins = {0: {}}
        self.node_states = {}
        self.undo_stack = []
        self.history = []
        self.reviews = []
        self.report = None
        self.category_sets = CategorySets()
        self.task_response = None
        self.reference = {'revision': 0, 'view_ids': [], 'entities': {}}
        self.bound_reference = deepcopy(self.reference)
        self.evidence = None
        self.bound_evidence = None
        self.proposal = None
        self.prepared_revision = None
        self.image = None
        self.image_frame = None
        self.image_revision = None
        self.capture_changed = asyncio.Event()
        self.current_intent = ''
        self.response_epochs = {}
        self.current_response = None
        self.muted_responses = set()
        self.trace.record('session_started', session=self.session)
        self.evidence_store.add('chart_state', self.snapshots[0], captured_at=self.trace.now_ms(), chart_revision=0)
        if task_id:
            title = task_brief(task_id)['title']
            self.store.state['title'] = title
            for name, args in setup_operations(task_id, self.data):
                before = self.store.snapshot()
                receipt = self.store.commit(self.store.prepare(name, args))
                self.add_node('Starter chart', 'starter', receipt, 'starter', before)
        self.initial = self.store.snapshot()
        self.snapshots[self.initial['revision']] = self.initial
        self.trace.save('initial.json', self.initial)

    def bootstrap(self):
        return {'state': self.store.snapshot(), 'catalog': self.data.catalog(), 'tasks': tasks(),
                'experiment_tasks': experiment_tasks(), 'formal_tasks': formal_tasks(), 'report': self.report,
                'diagnostic_tasks': diagnostic_tasks(), 'category_sets': self.category_sets.list(),
                'task_response': self.task_response,
                'settings': {'configured': bool(self.settings['api_key']),
                             'connection_mode': 'disabled' if self.settings['realtime_url'].endswith('/disabled')
                                else 'configured' if self.settings['api_key'] else 'unconfigured',
                             'credential_file': self.settings.get('credential_file', str(ROOT / '.env.local')),
                             'text_model': self.settings['text_model'], 'realtime_model': self.settings['realtime_model']},
                'session': self.session, 'nodes': self.nodes,
                'condition': self.session['condition'], 'conditions': CONDITION_OPTIONS,
                'evidence': self.evidence, 'proposal': self.proposal}

    def score(self):
        report = evaluate(self.session['task_id'], self.initial, self.store.snapshot(), self.trace.events,
                          self.data, self.reviews, task_response=self.task_response)
        report['interaction'] = interaction_summary(self.trace.events)
        report['delivery'] = summarize_delivery(self.trace.events)
        if self.session.get('assignment'):
            report['trial_report'] = build_trial_report(self.session, report, self.trace.events, self.task_response)
        return report

    async def finish(self, reason='completed'):
        if self.session.get('assignment'):
            if self.session['trial_status'] == 'finished':
                return {'report': self.report, 'session': self.session, 'export_url': '/api/export'}
            self.session['trial_status'] = 'finished'
            self.trace.record('trial_finished', reason=reason, revision=self.store.state['revision'])
        if self.trial_timer and self.trial_timer != asyncio.current_task():
            self.trial_timer.cancel()
        self.trial_timer = None
        await self.revoke()
        await self.close_voice()
        self.trace.record('task_finished')
        self.report = self.score()
        self.trace.finalize_audio()
        self.trace.save('report.json', self.report)
        self.trace.save('session.json', self.export())
        result = {'report': self.report, 'session': self.session, 'export_url': '/api/export'}
        if self.session.get('assignment'):
            await self.send({'type': 'trial_finished', **result})
        return result

    async def archive(self):
        if self.session.get('assignment') and self.session['trial_status'] != 'finished':
            await self.finish('abandoned')
        else:
            await self.revoke()
            await self.close_voice()
            self.trace.finalize_audio()
            if self.session.get('trial_status') != 'finished':
                self.trace.save('session.json', self.export())

    def instructions(self):
        common = (INSTRUCTIONS + '\nHistorical evidence is distinct from the current execution state. '
                  'read_history provides prior chart states in every condition. Do not treat citing an old chart as Undo. '
                  'All conditions support save_category_set, list_category_sets and apply_category_set. '
                  'Save exact members from a public chart version and reuse its set ID on explicit current targets; no manual copying of category names is required. '
                  'Saved sets retain object identities, not historical filters or metrics. Never invent a saved set ID. '
                  'list_evidence_candidates returns real chart groups and saved sets with exact candidate IDs. '
                  'Choose the intended candidate; apply_evidence_candidate and preview_revision resolve the same exact members in direct and bound_revision. '
                  'Separate object origin, current targets and scope, and retained or released conditions. '
                  'Only describe a chart change after a successful committed tool receipt. Give one short sentence of at most 25 words naming the affected charts and result; do not enumerate values unless asked, and do not read raw JSON aloud. '
                  'Generated assistant text is not proof that it was played or understood. Playback progress is partial when interrupted; specific words are not aligned. '
                  'Never select an evidence version using an evaluator answer. '
                  'A revision preview has not changed any chart. A proposal awaiting clarification requires a user answer; do not apply it yourself. '
                  'A new utterance supersedes the previous proposal. When the user answers a clarification, use the last_proposal card as conversation context and call revise_analysis with the resolved change; do not reuse the old proposal ID.\n')
        if self.session['condition'] in ('direct', 'bound_revision'):
            return common + ('Use revise_analysis for explicit changes to existing chart queries; it computes and commits in one call. '
                             'member_action=use_evidence binds members from the selected historical candidate, keeping current scope except for explicit flat fields. '
                             'Use apply_evidence_candidate or apply_category_set for deterministic object reuse on explicit current views. '
                             'For a new ranking, use member_action="rerank", top_n="3" and rank_by="orders" when the user asks for three by orders; the model tool contract requires top_n as a positive decimal string, or null to clear ranking. '
                             'preview_revision is available when the user asks for a preview, followed by apply_revision for explicit approval. '
                             'Use needs_confirmation only for a genuine unresolved choice and ask the concrete question. '
                             'Direct presentation-only edits can use edit_charts.')
        return common + ('This is the historical preview-without-binding diagnostic. '
                         'In direct editing, save_category_set then apply_category_set provides deterministic reuse of historical members without a preview. '
                         'Supply exact categories and top_n=null to retain a historical set. '
                         'The application does not copy members from evidence in this condition. '
                         'Use edit_charts directly in direct editing, or preview_revision then apply_revision in preview-without-binding. '
                         'You may ask a short clarification when the user has not determined a choice.')

    def history_index(self, snapshots=None):
        return [{'revision': revision, 'views': [
            {'id': view['id'], 'number': view['number'], 'title': view['title'],
             'source': view['source'], 'members': [row['label'] for row in view['data']['rows']]}
            for view in state['views']]} for revision, state in (self.snapshots if snapshots is None else snapshots).items()]

    def decision_material(self, actor='model'):
        if actor != 'model' or self.evidence_package is None:
            return self.snapshots, self.category_sets.list()
        items = self.evidence_package['items']
        snapshots = {item['chart_revision']: deepcopy(item['content']) for item in items if item['kind'] == 'chart_state'}
        sets = [deepcopy(item['content']) for item in items if item['kind'] == 'category_set']
        return snapshots, sets

    def candidates(self, actor='model'):
        snapshots, sets = self.decision_material(actor)
        return build_candidates(snapshots, sets)

    def freeze_evidence(self):
        self.evidence_package = self.evidence_store.package(self.trace.now_ms(),
            request_id=self.trace.current.get('request_id'))
        return self.evidence_package

    def decision_image(self):
        frames = [item for item in self.evidence_package['items'] if item['kind'] == 'image']
        if not frames:
            return None
        content = frames[-1]['content']
        if content['file'] is None:
            return None
        return {'file': content['file'], 'image': base64.b64encode(
            (self.trace.directory / content['file']).read_bytes()).decode('ascii')}

    def record_browser_event(self, message):
        details = message.get('details', {})
        origin = (self.revision_origins.get(details.get('revision'), {})
                  if message['name'] in ('chart_rendered', 'chart_visible', 'chart_hidden') else None)
        event = self.trace.record_client(message, origin=origin)
        if event['name'] in ('chart_rendered', 'chart_visible', 'chart_hidden',
                              'playback_start', 'playback_progress', 'playback_stopped', 'playback_end'):
            details = message['details']
            self.evidence_store.add(event['name'], details,
                available_at=event['server_ms'], source_request_id=event.get('request_id'),
                chart_revision=details.get('revision'), response_id=details.get('response_id'),
                **self.trace.client_stamp(message['client_ms'], message.get('client_clock_id')))
        return event

    async def choose_evidence(self, payload):
        if payload.get('clear'):
            self.evidence = None
        else:
            state = self.snapshots[payload['revision']]
            view = next(view for view in state['views'] if view['id'] == payload['view_id'])
            if view['source']['dimension'] != 'category':
                raise ValueError('Choose a category chart to reference a comparison set.')
            available = [row['label'] for row in view['data']['rows']]
            members = payload.get('members', available)
            if not members or not set(members) <= set(available):
                raise ValueError('Choose members displayed in this historical chart.')
            self.evidence = {'revision': state['revision'], 'view_id': view['id'], 'number': view['number'],
                             'title': view['title'], 'source': deepcopy(view['source']), 'members': list(members)}
        self.trace.record('evidence_selected', evidence=self.evidence)
        await self.send({'type': 'evidence', 'evidence': self.evidence})
        return self.bootstrap()

    async def send(self, event):
        if self.socket:
            async with self.send_lock:
                await self.socket.send_json(event)

    def add_node(self, title, kind, receipt, actor, before):
        self.report = None
        state = receipt['state']
        changes = []
        previous = {v['id']: v for v in before['views']}
        for view in state['views']:
            old = previous.get(view['id'])
            fields = [f for f in ('title', 'chart_type', 'source', 'style', 'data') if old is None or old[f] != view[f]]
            if fields:
                details = []
                if old:
                    for field in ('title', 'chart_type'):
                        if old[field] != view[field]:
                            details.append({'field': field, 'before': old[field], 'after': view[field]})
                    for field in ('source', 'style'):
                        for key, value in view[field].items():
                            if old[field].get(key) != value:
                                details.append({'field': key, 'before': old[field].get(key), 'after': value})
                changes.append({'view_id': view['id'], 'number': view['number'], 'fields': fields, 'details': details})
        changes += [{'view_id': v['id'], 'number': v['number'], 'fields': ['removed']} for v in before['views'] if v['id'] not in {c['id'] for c in state['views']}]
        node = {'id': uuid4().hex[:10], 'revision': state['revision'], 'title': title,
                'kind': kind, 'actor': actor, 'created_at': datetime.now(timezone.utc).isoformat(),
                'summary': receipt['result']['summary'], 'view_ids': receipt['result'].get('changed_view_ids', []),
                'changes': changes, 'intent': self.current_intent,
                'dashboard_changes': [field for field in ('title', 'layout') if before.get(field) != state.get(field)] +
                    (['view_order'] if [v['id'] for v in before['views']] != [v['id'] for v in state['views']] else []),
                'reference': deepcopy(self.bound_reference),
                'evidence': deepcopy(receipt['result'].get('revision_card', {}).get('evidence')),
                'revision_card': deepcopy(receipt['result'].get('revision_card')),
                'event_start': self.nodes[-1]['event_index'] + 1 if self.nodes else 0,
                'event_index': len(self.trace.events), 'parent_id': self.nodes[-1]['id'] if self.nodes else None}
        self.nodes.append(node)
        self.node_states[node['id']] = deepcopy(state)
        self.snapshots[state['revision']] = deepcopy(state)
        created = self.trace.record('node_created', node=node)
        self.revision_origins[state['revision']] = {
            key: created[key] for key in ('request_id', 'epoch', 'response_id', 'item_id', 'call_id') if key in created}
        self.evidence_store.add('chart_state', state, captured_at=created['server_ms'],
            chart_revision=state['revision'], source_request_id=created.get('request_id'))
        self.trace.save(f"state-r{state['revision']}.json", state)
        return node

    async def revoke(self, preserve_proposal=False):
        self.epoch += 1
        self.capture_changed.set()
        if self.proposal and self.proposal['status'] == 'pending' and not preserve_proposal:
            self.proposal['status'] = 'superseded'
            self.prepared_revision = None
            self.trace.record('revision_superseded', proposal_id=self.proposal['id'], epoch=self.epoch)
            await self.send({'type': 'proposal', 'proposal': self.proposal})
        if self.text_task and not self.text_task.done() and self.text_task != asyncio.current_task():
            self.text_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.text_task
        await self.send({'type': 'stop_audio'})
        if self.voice:
            await self.voice.cancel()

    async def execute_model(self, name, arguments, expected_epoch=None, *, call_context=None):
        return await self.execute(name, arguments, expected_epoch=expected_epoch,
                                  call_context=call_context, model_wire=True)

    async def execute(self, name, arguments, actor='model', expected_epoch=None, *, call_context=None, model_wire=False):
        context = deepcopy(call_context) if call_context is not None else (self.trace.origin() if actor == 'model' else {'epoch': self.epoch})
        if call_context is not None and expected_epoch is None and 'epoch' in context:
            expected_epoch = context['epoch']
        with self.trace.scope(context):
            return await self._execute_with_feedback(name, arguments, actor, expected_epoch, model_wire=model_wire)

    async def _execute_with_feedback(self, name, arguments, actor='model', expected_epoch=None, *, model_wire=False):
        epoch = self.epoch if expected_epoch is None else expected_epoch
        numbers = {view['id']: view['number'] for view in self.store.state['views']}
        if model_wire:
            try:
                compiled = compile_model_arguments(name, arguments, MODEL_TOOLS)
            except ValidationError as error:
                self.trace.record('tool_failed', tool=name, arguments=arguments, message=error.message, actor=actor)
                result = {'status': 'failed', 'committed': False, 'message': error.message}
            else:
                self.trace.record('model_arguments_compiled', tool=name, arguments=arguments,
                                  compiled_arguments=compiled, contract='decimal-top-n-v1')
                result = await self._execute(name, compiled, actor, epoch)
        else:
            result = await self._execute(name, arguments, actor, epoch)
        if result['status'] != 'superseded' and (actor == 'user' or epoch == self.epoch):
            state = result.get('state', self.store.state)
            changed = result.get('result', {}).get('changed_view_ids', [])
            numbers.update({view['id']: view['number'] for view in state['views']})
            feedback = {'tool': name, 'status': result['status'], 'committed': result.get('committed', False),
                        'revision': state['revision'], 'view_numbers': [numbers[view_id] for view_id in changed],
                        'summary': result.get('result', {}).get('summary', ''),
                        'message': result.get('message'), 'proposal_id': result.get('proposal', {}).get('id')}
            self.trace.record('tool_feedback', **feedback)
            await self.send({'type': 'tool_result', **feedback, **(self.trace.call_context.get() or {})})
        if actor == 'model' and result.get('committed') and self.voice is not None and self.image_revision is not None:
            revision = result['state']['revision']
            if self.image_revision != revision:
                self.trace.record('commit_capture_wait', revision=revision)
            # This runs in the tool job, outside the transaction lock. Native
            # input and browser context continue to arrive while it waits.
            while epoch == self.epoch and self.voice is not None and self.image_revision != revision:
                self.capture_changed.clear()
                await self.capture_changed.wait()
            if epoch != self.epoch or self.voice is None:
                return {'status': 'superseded', 'committed': True, 'revision': revision,
                        'message': 'Committed before supersession; obsolete chart data withheld.'}
        return result

    async def _execute(self, name, arguments, actor='model', expected_epoch=None):
        epoch = self.epoch if expected_epoch is None else expected_epoch
        if name == 'revise_analysis':
            try:
                payload = normalize_revise_analysis(arguments)
            except ValidationError as error:
                self.trace.record('tool_failed', tool=name, message=error.message, actor=actor)
                return {'status': 'failed', 'committed': False, 'message': error.message}
            preview = await self.preview_revision(payload, actor, epoch)
            if preview['status'] != 'completed':
                return preview
            if preview['proposal']['card']['needs_confirmation']:
                return {**preview, 'status': 'awaiting_confirmation'}
            return await self.apply_revision(preview['proposal']['id'], actor, epoch)
        if name == 'preview_revision':
            return await self.preview_revision(arguments, actor, epoch)
        if name == 'apply_revision':
            return await self.apply_revision(arguments['proposal_id'], actor, epoch)
        async with self.tool_lock:
            if epoch != self.epoch:
                return {'status': 'superseded', 'committed': False}
            before = self.store.snapshot()
            self.trace.record('tool_started', tool=name, arguments=arguments, actor=actor, epoch=epoch,
                              reference=self.bound_reference)
            await self.send({'type': 'status', 'status': 'working'})
            try:
                if name == 'read_history':
                    snapshots, _ = self.decision_material(actor)
                    result = snapshots[arguments['revision']] if 'revision' in arguments else {'versions': self.history_index(snapshots)}
                    self.trace.record('tool_read', tool=name, result=result)
                    await self.send({'type': 'status', 'status': 'ready'})
                    return {'status': 'completed', 'committed': False, 'result': deepcopy(result)}
                if name in ('list_evidence_candidates', 'read_dashboard'):
                    snapshots, _ = self.decision_material(actor)
                    result = ({'candidates': self.candidates(actor)} if name == 'list_evidence_candidates'
                              else {'tool': name, 'summary': 'Read decision dashboard', **snapshots[max(snapshots)]})
                    self.trace.record('tool_read', tool=name, result=result)
                    await self.send({'type': 'status', 'status': 'ready'})
                    return {'status': 'completed', 'committed': False, 'result': deepcopy(result)}
                if name in ('save_category_set', 'list_category_sets'):
                    if epoch != self.epoch:
                        return {'status': 'superseded', 'committed': False}
                    if name == 'save_category_set':
                        snapshots, _ = self.decision_material(actor)
                        saved = self.category_sets.save(snapshots, arguments)
                        created = self.trace.record('category_set_saved', category_set=saved, actor=actor)
                        self.evidence_store.add('category_set', saved, captured_at=created['server_ms'],
                            source_request_id=created.get('request_id'), chart_revision=saved['evidence']['revision'])
                        self.trace.save('category-sets.json', self.category_sets.list())
                        self.report = None
                        await self.send({'type': 'category_sets', 'category_sets': self.category_sets.list()})
                        result = {'category_set': saved}
                    else:
                        _, sets = self.decision_material(actor)
                        result = {'category_sets': sets}
                        self.trace.record('tool_read', tool=name, result=result, actor=actor)
                    await self.send({'type': 'status', 'status': 'ready'})
                    return {'status': 'completed', 'committed': False, 'result': result}
                if name == 'apply_category_set':
                    _, sets = self.decision_material(actor)
                    resolve_candidate('set:' + arguments['set_id'], build_candidates({}, sets))
                    prepared = await asyncio.to_thread(self.category_sets.prepare_apply, self.store, arguments,
                        self.bound_evidence if actor == 'model' else self.evidence)
                elif name == 'apply_evidence_candidate':
                    candidate = resolve_candidate(arguments['candidate_id'], self.candidates(actor))
                    prepared = await asyncio.to_thread(prepare_candidate_apply, self.store, candidate, arguments,
                        self.bound_evidence if actor == 'model' else self.evidence)
                else:
                    prepared = await asyncio.to_thread(self.store.prepare, name, arguments, self.bound_reference)
                if epoch != self.epoch:
                    self.trace.record('tool_superseded', tool=name, epoch=epoch)
                    return {'status': 'superseded', 'committed': False}
                # Permission check and commit have no await between them.
                receipt = self.store.commit(prepared)
            except (ValueError, KeyError, ValidationError) as error:
                message = error.message if isinstance(error, ValidationError) else str(error)
                self.trace.record('tool_failed', tool=name, message=message, actor=actor)
                await self.send({'type': 'status', 'status': 'ready'})
                return {'status': 'failed', 'committed': False, 'message': message}
            node = None
            if receipt['result']['committed']:
                self.undo_stack.append(before)
                self.trace.record('tool_committed', tool=name, revision=receipt['state']['revision'], result=receipt['result'], actor=actor)
                node = self.add_node(self.current_intent or receipt['result']['summary'], 'edit', receipt, actor, before)
                await self.send({'type': 'state', 'state': receipt['state'], 'node': node})
            else:
                self.trace.record('tool_read', tool=name, revision=receipt['state']['revision'], result=receipt['result'])
            await self.send({'type': 'status', 'status': 'ready'})
            return {**receipt, 'status': 'completed', 'node': node, 'committed': receipt['result']['committed']}

    async def preview_revision(self, arguments, actor='model', expected_epoch=None):
        epoch = self.epoch if expected_epoch is None else expected_epoch
        async with self.tool_lock:
            if epoch != self.epoch:
                return {'status': 'superseded', 'committed': False}
            payload = deepcopy(arguments)
            chosen = self.bound_evidence if actor == 'model' else self.evidence
            self.trace.record('tool_started', tool='preview_revision', arguments=payload, actor=actor, epoch=epoch)
            try:
                snapshots, _ = self.decision_material(actor)
                candidate = resolve_candidate(payload['candidate_id'], self.candidates(actor)) if 'candidate_id' in payload else None
                preview = await asyncio.to_thread(prepare_revision, self.store, snapshots, payload,
                    self.session['condition'], resolved_candidate=candidate, selected_evidence=deepcopy(chosen))
            except (ValueError, KeyError, ValidationError) as error:
                message = error.message if isinstance(error, ValidationError) else str(error)
                self.trace.record('tool_failed', tool='preview_revision', message=message, actor=actor)
                return {'status': 'failed', 'committed': False, 'message': message}
            if epoch != self.epoch:
                self.trace.record('tool_superseded', tool='preview_revision', epoch=epoch)
                return {'status': 'superseded', 'committed': False}
            self.prepared_revision = preview['prepared']
            self.proposal = {'id': uuid4().hex[:10], 'epoch': epoch, 'card': preview['card'], 'status': 'pending'}
            self.trace.record('revision_proposed', proposal=self.proposal, actor=actor)
            await self.send({'type': 'proposal', 'proposal': self.proposal})
            return {'status': 'completed', 'committed': False, 'proposal': deepcopy(self.proposal)}

    async def apply_revision(self, proposal_id, actor='model', expected_epoch=None):
        epoch = self.epoch if expected_epoch is None else expected_epoch
        async with self.tool_lock:
            proposal = self.proposal
            if epoch != self.epoch:
                return {'status': 'superseded', 'committed': False}
            self.trace.record('tool_started', tool='apply_revision', arguments={'proposal_id': proposal_id}, actor=actor, epoch=epoch)
            if not proposal or proposal['id'] != proposal_id or proposal['status'] != 'pending' or proposal['epoch'] != self.epoch:
                message = 'This proposal is no longer current. Prepare a new preview using the latest request and current chart state.'
                self.trace.record('tool_failed', tool='apply_revision', proposal_id=proposal_id, message=message, actor=actor)
                return {'status': 'failed', 'committed': False, 'message': message}
            if actor == 'model' and proposal['card']['needs_confirmation']:
                return {'status': 'awaiting_confirmation', 'committed': False, 'proposal': deepcopy(proposal)}
            if actor == 'user':
                confirmation_epoch = self.epoch + 1
                prepared = self.prepared_revision
                await self.revoke(preserve_proposal=True)
                if (self.epoch != confirmation_epoch or self.proposal is not proposal
                        or proposal['status'] != 'pending' or self.prepared_revision is not prepared):
                    return {'status': 'superseded', 'committed': False}
                proposal['epoch'] = self.epoch
            before = self.store.snapshot()
            try:
                receipt = self.store.commit(self.prepared_revision)
            except ValueError as error:
                proposal['status'] = 'superseded'
                self.prepared_revision = None
                self.trace.record('revision_superseded', proposal_id=proposal_id, message=str(error))
                await self.send({'type': 'proposal', 'proposal': proposal})
                return {'status': 'failed', 'committed': False, 'message': str(error)}
            self.prepared_revision = None
            proposal['status'] = 'committed'
            proposal['committed_revision'] = receipt['state']['revision']
            self.undo_stack.append(before)
            receipt['result']['revision_card'] = deepcopy(proposal['card'])
            self.trace.record('tool_committed', tool='apply_revision', revision=receipt['state']['revision'], result=receipt['result'], actor=actor)
            self.trace.record('revision_applied', proposal=proposal, actor=actor)
            if actor == 'user':
                self.trace.record('revision_confirmed', proposal_id=proposal_id,
                                  committed_revision=receipt['state']['revision'], channel='apply_button')
            node = self.add_node(self.current_intent or 'Revise current analysis', 'revision', receipt, actor, before)
            await self.send({'type': 'state', 'state': receipt['state'], 'node': node})
            await self.send({'type': 'proposal', 'proposal': proposal})
            await self.send({'type': 'status', 'status': 'ready'})
            return {**receipt, 'status': 'completed', 'committed': True, 'node': node, 'proposal': deepcopy(proposal)}

    def execution_state(self, request_id=None):
        """Execution facts from public state and the existing request ledger."""
        request_id = request_id or self.trace.current.get('request_id')
        commits = [event for event in self.trace.events
                   if request_id is not None and event['name'] == 'tool_committed' and event.get('request_id') == request_id]
        outcomes = [event for event in self.trace.events if event['name'] == 'request_outcome']
        return {'request_id': request_id, 'public_revision': self.store.state['revision'],
                'request_committed': bool(commits),
                'request_commit_revisions': [event['revision'] for event in commits],
                'recent_request_outcomes': [{key: event.get(key) for key in
                    ('request_id', 'status', 'committed', 'revision', 'view_numbers')}
                    for event in outcomes[-6:]]}

    def context(self):
        snapshots, sets = self.decision_material()
        revision = self.bound_reference['revision']
        visible = snapshots.get(revision)
        playback = {}
        if self.evidence_package:
            for item in self.evidence_package['items']:
                if item['kind'].startswith('playback_'):
                    details = item['content']
                    playback[item['response_id']] = {key: details[key] for key in
                        ('response_id', 'played_samples', 'received_samples', 'interrupted', 'timing_basis') if key in details}
        return json.dumps({'execution_state': self.execution_state(),
                           'evidence_revision': max(snapshots),
                           'reference': self.bound_reference, 'visible_dashboard': visible,
                           'current_dashboard': snapshots[max(snapshots)], 'evidence': self.bound_evidence,
                           'selected_evidence_source': evidence_source(self.bound_evidence),
                           'history_index': self.history_index(snapshots),
                           'category_sets': sets, 'evidence_candidates': self.candidates(),
                           'evidence_package_id': self.evidence_package['package_id'] if self.evidence_package else None,
                           'playback_observations': list(playback.values()), 'spoken_words_alignment': 'unknown',
                           'recent_conversation': deepcopy(self.history[-12:]),
                           'conversation_evidence': 'received_text_not_proof_of_listening',
                           'task': task_brief(self.session['task_id']) if self.session['task_id'] else None,
                           'last_proposal': deepcopy(self.proposal)}, ensure_ascii=False)

    def begin_request(self, item_id=None):
        self.trace.current = {'request_id': f"{self.session['id']}:request:{self.epoch}", 'epoch': self.epoch}
        if item_id is not None:
            self.trace.current['item_id'] = item_id
            self.trace.items[item_id] = deepcopy(self.trace.current)
        self.trace.requests[self.epoch] = deepcopy(self.trace.current)

    def accept(self, text, reference):
        if self.trace.current.get('epoch') != self.epoch:
            self.begin_request()
        self.current_intent = text
        self.bound_reference = deepcopy(reference)
        self.trace.record('request_accepted', text=text, reference=self.bound_reference, evidence=self.bound_evidence, epoch=self.epoch)
        self.history.append({'role': 'user', 'content': text})

    async def request_outcome(self, response_id, settled_status):
        """Report execution for this request; a spoken answer is not a chart commit."""
        origin = self.trace.origin(response_id)
        if not origin or origin['epoch'] != self.epoch:
            return
        events = [event for event in self.trace.events if event.get('request_id') == origin['request_id']]
        commits = [event for event in events if event['name'] == 'tool_committed']
        failures = [event for event in events if event['name'] == 'tool_failed']
        pending = self.proposal if self.proposal and self.proposal['epoch'] == self.epoch and self.proposal['status'] == 'pending' else None
        status = ('failed' if settled_status == 'failed' or failures else
                  'awaiting_confirmation' if pending else 'committed' if commits else 'no_changes')
        changed_ids = {view_id for event in commits for view_id in event['result'].get('changed_view_ids', [])}
        outcome = {'status': status, 'committed': bool(commits),
                   'revision': commits[-1]['revision'] if commits else self.store.state['revision'],
                   'view_numbers': [view['number'] for view in self.store.state['views'] if view['id'] in changed_ids],
                   'proposal_id': pending['id'] if pending else None,
                   'message': failures[-1]['message'] if failures else None}
        with self.trace.scope(origin):
            self.trace.record('request_outcome', **outcome)
        await self.send({'type': 'request_outcome', **origin, **outcome})

    async def set_context(self, message):
        available_at = self.trace.now_ms()
        self.reference = deepcopy(message.get('reference', self.reference))
        if 'image' in message:
            self.image = message['image']
            self.image_frame = None
            self.image_revision = None
        if message.get('image'):
            filename = self.trace.image(self.image, self.reference['revision'])
            self.image_frame = filename
            self.image_revision = self.reference['revision']
            content = {'file': filename, 'reference': deepcopy(self.reference),
                       'sha256': hashlib.sha256(base64.b64decode(self.image)).hexdigest()}
            stamp = self.trace.client_stamp(message.get('captured_client_ms'), message.get('client_clock_id'))
            item = self.evidence_store.add('image', content, available_at=available_at,
                source_request_id=self.trace.current.get('request_id'), chart_revision=self.reference['revision'], **stamp)
            self.trace.record('image_captured', **content, evidence_id=item['evidence_id'],
                              captured_at=item['captured_at'], available_at=available_at,
                              clock_uncertainty=item['clock_uncertainty'])
            await self.send({'type': 'visual_context', 'reference': deepcopy(self.reference),
                             'status': 'captured', 'frame_id': filename})
        elif 'image' in message:
            self.image_revision = self.reference['revision']
            self.evidence_store.add('image', {'file': None, 'reference': deepcopy(self.reference)},
                available_at=available_at, chart_revision=self.reference['revision'],
                **self.trace.client_stamp(message.get('captured_client_ms'), message.get('client_clock_id')))
            await self.send({'type': 'visual_context', 'reference': deepcopy(self.reference),
                             'status': 'empty', 'frame_id': None})
        # Capture and arrival are observations. Upload only from a decision package.
        self.capture_changed.set()

    async def provider_event(self, event, expected_epoch=None):
        kind = event['type']
        if kind == 'superseded_receipt':
            origin = event['context']
            attempted = event['execution_attempted']
            commits = [entry for entry in self.trace.events if entry['name'] == 'tool_committed'
                       and origin.get('call_id') is not None and entry.get('call_id') == origin['call_id']
                       and entry.get('request_id') == origin.get('request_id')
                       and entry.get('response_id') == origin.get('response_id')]
            receipt = {'status': 'superseded', 'committed': bool(commits),
                       'execution_attempted': attempted,
                       'public_revision': self.store.state['revision'],
                       'message': ('Already committed before supersession; obsolete chart data withheld.' if commits else
                                  ('Not committed: execution was attempted before supersession. ' if attempted else
                                   'Not executed: newer user speech superseded this response. ') +
                                  'This call changed no public charts. Issue a new call under the current '
                                  'request if this work is still required.')}
            if commits:
                receipt['revision'] = commits[-1]['revision']
            with self.trace.scope(origin):
                self.trace.record('superseded_receipt', receipt=receipt)
            return receipt
        if kind == 'audio_input':
            origin = self.trace.origin() if event['mode'] == 'push_to_talk' else {}
            with self.trace.scope(origin):
                info = self.trace.audio(event['data'], 'input', self.session['id'])
                self.trace.record('audio_sent', stream_id=self.session['id'], **info)
            return
        if kind == 'provider_input':
            origin = event.get('context', self.trace.requests.get(expected_epoch, {})
                               if expected_epoch is not None else self.trace.origin())
            with self.trace.scope(origin):
                record = self.trace.record_model_input(event)
                self.trace.record('model_input_package', input_id=event['input_id'], status=event['status'],
                    model_input_event_id=record['event_id'], package_id=self.evidence_package['package_id'] if self.evidence_package else None,
                    scope='application_evidence_only', native_conversation_frozen=False)
            return
        if kind == 'response_prepare':
            self.freeze_evidence()
            instructions = self.instructions() + '\n' + self.context()
            if event.get('transport') == 'websocket' and self.voice:
                await self.voice.context(instructions)
                image = self.decision_image()
                if image:
                    await self.voice.image(image['image'], frame_id=image['file'])
            return {'instructions': instructions, **self.trace.current}
        if kind == 'image_delivery':
            frame = next(item for item in reversed(self.trace.events)
                         if item['name'] == 'image_captured' and item['file'] == event['frame_id'])
            self.trace.record('image_delivery', frame_id=event['frame_id'], status=event['status'],
                              reference=frame['reference'])
            await self.send({'type': 'visual_context', 'frame_id': event['frame_id'],
                             'status': event['status'], 'reference': deepcopy(frame['reference'])})
            return
        if kind == 'transport_closed':
            self.trace.record('transport_closed', reason=event['reason'])
            await self.close_voice()
            return
        if kind == 'provider_event':
            raw = event['event']
            response_id = raw.get('response_id', raw.get('response', {}).get('id'))
            item_id = raw.get('item_id', raw.get('item', {}).get('id'))
            call_id = raw.get('call_id', raw.get('item', {}).get('call_id'))
            correlation = {key: value for key, value in (('item_id', item_id), ('call_id', call_id)) if value is not None}
            if response_id is not None:
                correlation['response_id'] = response_id
            with self.trace.scope(event.get('context', self.trace.origin(response_id, item_id))):
                self.trace.record('provider_event', event=media_summary(event), **correlation)
            return
        if kind == 'speech_start':
            self.epoch += 1
            self.capture_changed.set()
            self.begin_request(event.get('item_id'))
            if not event.get('continuation', False):
                self.bound_reference = deepcopy(self.reference)
                self.bound_evidence = deepcopy(self.evidence)
            if self.proposal and self.proposal['status'] == 'pending':
                self.proposal['status'] = 'superseded'
                self.prepared_revision = None
                self.trace.record('revision_superseded', proposal_id=self.proposal['id'], epoch=self.epoch)
                await self.send({'type': 'proposal', 'proposal': self.proposal})
            self.trace.record('speech_start', event=event, reference=self.bound_reference, epoch=self.epoch)
            await self.send({'type': 'stop_audio'})
            await self.send({**event, **self.trace.current})
            return deepcopy(self.trace.current)
        elif kind == 'user_transcript_fragment':
            with self.trace.scope(self.trace.origin(item_id=event['item_id'])):
                self.trace.record('user_transcript_fragment', event=event, item_id=event['item_id'])
            return
        elif kind == 'user_transcript':
            item_id = event.get('item_id')
            if item_id is not None:
                self.trace.current['item_id'] = item_id
                self.trace.items[item_id] = deepcopy(self.trace.current)
                self.trace.requests[self.epoch] = deepcopy(self.trace.current)
            for fragment_id in event.get('item_ids', []):
                self.trace.items[fragment_id] = {**self.trace.current, 'item_id': fragment_id}
            self.accept(event['text'], self.bound_reference)
            await self.send({'type': 'request_accepted', **self.trace.current, 'text': event['text']})
        elif kind == 'response_start':
            self.current_response = event['response_id']
            response_epoch = self.epoch if expected_epoch is None else expected_epoch
            self.response_epochs[self.current_response] = response_epoch
            origin = self.trace.requests.get(response_epoch, {})
            self.trace.responses[self.current_response] = {**origin, 'response_id': self.current_response}
        response_id = event.get('response_id')
        epoch = expected_epoch if expected_epoch is not None else self.response_epochs.get(response_id, self.epoch)
        if kind == 'request_settled':
            await self.request_outcome(response_id, event['status'])
            return
        if kind in ('audio', 'assistant_delta', 'assistant_done') and epoch != self.epoch:
            self.trace.record('output_suppressed', response_id=response_id, output_type=kind)
            return
        if kind == 'audio':
            record = self.trace.audio(event['data'], 'output', response_id or 'unknown')
            self.trace.record('audio_received', response_id=response_id,
                              **{key: event[key] for key in ('item_id', 'content_index') if event.get(key) is not None}, **record)
            event = {**event, **record}
            if response_id in self.muted_responses:
                return
        else:
            with self.trace.scope(self.trace.origin(response_id, event.get('item_id'))):
                self.trace.record(kind, event=event, **{key: event[key] for key in ('response_id', 'item_id', 'call_id') if event.get(key) is not None})
        if kind == 'assistant_done' and event.get('text'):
            self.history.append({'role': 'assistant', 'content': event['text']})
            self.evidence_store.add('assistant_text_received', {'text': event['text'], 'status': 'received_not_aligned'},
                captured_at=self.trace.now_ms(), response_id=response_id,
                source_request_id=self.trace.origin(response_id).get('request_id'))
        origin = self.trace.origin(response_id, event.get('item_id'))
        await self.send({**origin, **event})
        return origin

    async def text(self, message):
        if self.session.get('assignment', {}).get('protocol') == FORMAL_PROTOCOL:
            await self.send({'type': 'error', 'message': 'This study task uses one live voice window. Use chart controls and the written response outside that window.'})
            return
        await self.revoke()
        await self.close_voice()
        await self.set_context(message)
        self.bound_evidence = deepcopy(self.evidence)
        self.session['mode'] = 'text'
        if 'text' not in self.session['used_modes']:
            self.session['used_modes'].append('text')
        self.accept(message['text'], message.get('reference', self.reference))
        await self.send({'type': 'request_accepted', **self.trace.current, 'text': message['text']})
        self.freeze_evidence()
        if not self.settings['api_key']:
            await self.send({'type': 'error', 'message': 'Add your Qwen key to C:\\CoVisStudio\\.env.local and restart the server to chat. You can edit charts locally now.'})
            return
        epoch = self.epoch
        from .providers import QwenText
        content = [{'type': 'text', 'text': message['text'] + '\nVisible reference:\n' + self.context()}]
        image = self.decision_image()
        if image:
            content.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + image['image']}})
        messages = [{'role': 'system', 'content': self.instructions()}, *deepcopy(self.history[:-1]), {'role': 'user', 'content': content}]

        async def run():
            await self.send({'type': 'status', 'status': 'thinking'})
            try:
                await QwenText(self.settings).run(messages, MODEL_TOOLS,
                    lambda event: self.provider_event(event, epoch),
                    lambda name, args, **kwargs: self.execute_model(name, args, expected_epoch=epoch, **kwargs))
            except asyncio.CancelledError:
                self.trace.record('request_cancelled', epoch=epoch)
                raise
            except Exception as error:
                self.trace.record('request_failed', message=str(error))
                await self.send({'type': 'error', 'message': str(error)})
            finally:
                if epoch == self.epoch:
                    await self.send({'type': 'status', 'status': 'ready'})
        self.text_task = asyncio.create_task(run())

    async def start_voice(self, message):
        formal = self.session.get('assignment', {}).get('protocol') == FORMAL_PROTOCOL
        if formal and (message['mode'] != 'live_voice' or self.session.get('voice_window_used')):
            await self.send({'type': 'error', 'message': 'This study task has one Realtime voice window. Continue with chart controls after it ends.'})
            return
        if not self.settings['api_key']:
            await self.send({'type': 'error', 'message': 'Add your Qwen key to C:\\CoVisStudio\\.env.local and restart the server. No model connection was opened.'})
            return
        await self.close_voice()
        await self.revoke()
        await self.set_context(message)
        self.bound_reference = deepcopy(self.reference)
        self.bound_evidence = deepcopy(self.evidence)
        from .providers import QwenRealtime
        self.freeze_evidence()
        self.session['mode'] = message['mode']
        if message['mode'] not in self.session['used_modes']:
            self.session['used_modes'].append(message['mode'])
        self.voice = QwenRealtime(self.settings, message['mode'], MODEL_TOOLS, self.provider_event, self.execute_model)
        if formal:
            self.session['voice_window_used'] = True
            self.trace.record('voice_window_started', maximum_seconds=60, maximum_connections=1)
        try:
            await self.voice.connect(self.instructions() + '\n' + self.context())
        except Exception:
            await self.close_voice()
            raise
        image = self.decision_image()
        if image:
            await self.voice.image(image['image'], frame_id=image['file'])
        self.trace.record('voice_connected', mode=message['mode'])
        await self.send({'type': 'voice_ready', 'voice_window_used': self.session.get('voice_window_used', False)})
        self.voice_timer = asyncio.create_task(self.voice_budget())

    async def voice_budget(self):
        await asyncio.sleep(60)
        self.trace.record('voice_budget_reached', seconds=60)
        await self.close_voice()

    async def close_voice(self):
        if self.voice_closing is not None:
            await asyncio.shield(self.voice_closing)
            return
        if self.voice_timer and self.voice_timer != asyncio.current_task():
            self.voice_timer.cancel()
        self.voice_timer = None
        if self.voice:
            self.epoch += 1
            self.capture_changed.set()
            proposal = None
            if self.proposal and self.proposal['status'] == 'pending':
                self.proposal['status'] = 'superseded'
                self.prepared_revision = None
                self.trace.record('revision_superseded', proposal_id=self.proposal['id'], epoch=self.epoch)
                proposal = deepcopy(self.proposal)
            voice, self.voice = self.voice, None
            self.voice_closing = asyncio.create_task(self._close_voice(voice, proposal))
            await asyncio.shield(self.voice_closing)

    async def _close_voice(self, voice, proposal):
        try:
            if proposal is not None:
                await self.send({'type': 'proposal', 'proposal': proposal})
            await voice.close()
            self.trace.record('voice_closed')
            self.trace.finalize_audio()
            await self.send({'type': 'stop_audio'})
            await self.send({'type': 'voice_closed', 'voice_window_used': self.session.get('voice_window_used', False)})
        finally:
            self.voice_closing = None

    async def restore(self, snapshot, kind):
        await self.revoke()
        before = self.store.snapshot()
        receipt = self.store.restore(snapshot)
        self.trace.record(kind, revision=receipt['state']['revision'], state=receipt['state'])
        node = self.add_node('Undo last change' if kind == 'undo' else 'Restore this version', kind, receipt, 'user', before)
        await self.send({'type': 'state', 'state': receipt['state'], 'node': node})
        return {**receipt, 'node': node}

    def export(self):
        return {'version': 4, 'session': self.session, 'initial': self.initial,
                'task': task_brief(self.session['task_id']) if self.session.get('task_id') else None,
                'final': self.store.snapshot(), 'nodes': self.nodes, 'states': self.node_states,
                'evidence': self.evidence, 'proposal': self.proposal,
                'category_sets': self.category_sets.list(), 'task_response': self.task_response,
                'interaction': interaction_summary(self.trace.events),
                'delivery': summarize_delivery(self.trace.events),
                'latest_evidence_package': self.evidence_package['package_id'] if self.evidence_package else None,
                'events': self.trace.events, 'report': self.report, 'reviews': self.reviews,
                'evidence_directory': str(self.trace.directory)}


def create_app(settings=None):
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.workspace = Workspace(settings)
        yield
        workspace = app.state.workspace
        workspace.socket = None
        await workspace.archive()
        workspace.data.connection.close()

    app = FastAPI(title='CoVis Studio', lifespan=lifespan)

    @app.middleware('http')
    async def trial_phase(request: Request, call_next):
        ws = app.state.workspace
        task_actions = ('/api/tools', '/api/evidence', '/api/category-sets', '/api/task-response',
                        '/api/revisions', '/api/undo', '/api/nodes')
        if (ws.session.get('assignment') and ws.session['trial_status'] != 'running'
                and request.method == 'POST' and request.url.path.startswith(task_actions)):
            return JSONResponse({'detail': 'Begin the assigned task before editing. Finished tasks remain read-only.'}, status_code=409)
        return await call_next(request)

    @app.get('/api/experiment/plan')
    def experiment_plan(slot: int = 1, protocol: str = 'authored'):
        plan = formal_allocation_for(slot) if protocol == 'formal' else allocation_for(slot)
        return {**plan, 'slot': slot,
                'trials': [{**trial, 'task': task_brief(trial['task_id'])} for trial in plan['trials']]}

    @app.get('/api/experiment/allocations')
    def experiment_allocations(count: int = 30, protocol: str = 'authored'):
        return formal_allocation_table(count) if protocol == 'formal' else allocation_table(count)

    @app.get('/api/experiment/formal-manifest')
    def experiment_formal_manifest():
        return formal_manifest()

    def registered_participants():
        path = settings['trace_dir'] / 'formal-registrations.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []

    @app.post('/api/experiment/register')
    def experiment_register(body: dict):
        participant = body['participant_id'].strip()
        if not participant:
            raise HTTPException(400, 'Enter a pseudonymous participant ID.')
        formal_allocation_for(body['participant_slot'])
        registrations = registered_participants()
        item = {'participant_id': participant, 'participant_slot': body['participant_slot']}
        if item not in registrations:
            registrations.append(item)
            path = settings['trace_dir'] / 'formal-registrations.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(registrations, indent=2), encoding='utf-8')
        return {'registrations': registrations}

    @app.post('/api/experiment/start')
    async def experiment_start(body: dict):
        ws = app.state.workspace
        if not body['participant_id'].strip():
            raise HTTPException(400, 'Enter a pseudonymous participant ID.')
        if body['evidence_kind'] not in ('local_authored', 'participant'):
            raise HTTPException(400, 'Choose local authored verification or participant collection.')
        formal = body.get('protocol') == 'formal'
        plan = formal_allocation_for(body['slot']) if formal else allocation_for(body['slot'])
        trial = next(item for item in plan['trials'] if item['trial_index'] == body['trial_index'])
        if formal and body['evidence_kind'] == 'participant':
            experiment_register({'participant_id': body['participant_id'], 'participant_slot': body['slot']})
        await ws.archive()
        ws.reset('live_voice', trial['task_id'], body['participant_id'].strip(), trial['condition'])
        ws.session.update(assignment=trial, evidence_kind=body['evidence_kind'], trial_status='ready', trial_started_at=None)
        if formal:
            ws.session.update(voice_window_used=False, repeat_reason=body.get('repeat_reason'),
                              material_review='pending', human_review='pending')
        ws.trace.record('trial_assigned', assignment=trial, evidence_kind=body['evidence_kind'])
        ws.trace.save('session.json', ws.export())
        await ws.send({'type': 'bootstrap', **ws.bootstrap()})
        return ws.bootstrap()

    @app.post('/api/experiment/begin')
    async def experiment_begin():
        ws = app.state.workspace
        if ws.session.get('trial_status') != 'ready':
            raise HTTPException(409, 'Prepare an assigned task before beginning it.')
        ws.session.update(trial_status='running', trial_started_at=datetime.now(timezone.utc).isoformat())
        ws.trace.record('trial_started', assignment=ws.session['assignment'], revision=ws.store.state['revision'])

        async def deadline():
            await asyncio.sleep(ws.session['assignment']['time_limit_seconds'])
            await ws.finish('timeout')

        ws.trial_timer = asyncio.create_task(deadline())
        await ws.send({'type': 'bootstrap', **ws.bootstrap()})
        return ws.bootstrap()

    def experiment_archives():
        ws = app.state.workspace
        records = read_trial_archives([*settings.get('review_archive_dirs', []), settings['trace_dir']])
        if ws.session.get('assignment') and ws.session.get('trial_status') != 'finished':
            saved = ws.export()
            saved['report'] = ws.report or ws.score()
            records[ws.session['id']] = {'archive': saved, 'directory': ws.trace.directory}
        return records

    def experiment_summary(protocol='authored'):
        records = experiment_archives()
        if protocol == 'formal':
            report = formal_primary_attempts([r['archive'] for r in records.values()], registered_participants())
            return attach_formal_scores(report, records, app.state.workspace.data)
        legacy = [record for record in records.values()
                  if record['archive']['session']['assignment'].get('protocol') != FORMAL_PROTOCOL]
        report = aggregate_reports([record['archive']['report']['trial_report'] for record in legacy
                                    if (record['archive'].get('report') or {}).get('trial_report')])
        report['unscored_attempts'] = [record['archive']['session'] for record in legacy if not record['archive'].get('report')]
        return attach_review_drafts(report, records)

    def attempt_record(session_id):
        records = experiment_archives()
        if session_id not in records:
            raise HTTPException(404, 'This assigned attempt is not in the experiment archive.')
        return records[session_id]

    @app.get('/api/experiment/attempts/{session_id}')
    def experiment_attempt(session_id: str):
        record = attempt_record(session_id)
        return {**build_review_packet(record['archive'], record['directory']),
                'intent_episodes': episode_index(record['directory'])}

    @app.post('/api/experiment/attempts/{session_id}/intent-episodes')
    def prepare_intent_episode(session_id: str, body: dict):
        record = attempt_record(session_id)
        if record['archive']['session']['trial_status'] != 'finished':
            raise HTTPException(409, 'Finish the attempt before preparing blinded intent coding.')
        return create_episode(record['directory'], body['onset_index'], body['utterance_end_index'],
                              body['end_event_index'], record['archive']['session']['evidence_kind'])

    def intent_files(session_id, packet_id):
        record = attempt_record(session_id)
        episodes = {p.parent.name: p.parent for p in (record['directory'] / 'intent-episodes').glob('*/packet.json')}
        if packet_id not in episodes:
            raise HTTPException(404, 'Choose a prepared intent episode.')
        return record, episodes[packet_id]

    @app.get('/api/experiment/attempts/{session_id}/intent-episodes/{packet_id}')
    def intent_packet(session_id: str, packet_id: str):
        _, directory = intent_files(session_id, packet_id)
        return json.loads((directory / 'packet.json').read_text(encoding='utf-8'))

    @app.post('/api/experiment/attempts/{session_id}/intent-episodes/{packet_id}/lock')
    def intent_lock(session_id: str, packet_id: str, body: dict):
        _, directory = intent_files(session_id, packet_id)
        packet = json.loads((directory / 'packet.json').read_text(encoding='utf-8'))
        try:
            locked = lock_intent(packet, body['coder_a'], body['coder_b'], body['adjudication'])
            write_new(directory / 'locked.json', locked)
        except (ValueError, FileExistsError) as error:
            raise HTTPException(400, str(error)) from error
        return locked

    @app.post('/api/experiment/attempts/{session_id}/intent-episodes/{packet_id}/primary')
    def intent_primary(session_id: str, packet_id: str, body: dict):
        record, _ = intent_files(session_id, packet_id)
        return designate_primary_episode(record['directory'], packet_id, body['reviewer_id'], body['reason'])

    @app.post('/api/experiment/attempts/{session_id}/intent-episodes/{packet_id}/score')
    def intent_score(session_id: str, packet_id: str):
        record, directory = intent_files(session_id, packet_id)
        if not (directory / 'locked.json').exists():
            raise HTTPException(409, 'Two independent codings must be locked before scoring.')
        read = lambda name: json.loads((directory / name).read_text(encoding='utf-8'))
        result = score_episode(record['archive'], read('packet.json'), read('locked.json'),
                               read('private.json')['end_event_index'], app.state.workspace.data)
        write_new(directory / 'score.json', result)
        return result

    @app.post('/api/experiment/attempts/{session_id}/intent-episodes/{packet_id}/understanding')
    def intent_understanding(session_id: str, packet_id: str, body: dict):
        record, directory = intent_files(session_id, packet_id)
        result = review_understanding(record['archive'], body)
        write_new(directory / 'understanding.json', result)
        return result

    @app.post('/api/experiment/attempts/{session_id}/review-drafts')
    def experiment_review_draft(session_id: str, body: dict):
        record = attempt_record(session_id)
        if record['archive']['session']['trial_status'] != 'finished':
            raise HTTPException(409, 'Finish the attempt before coding its record.')
        try:
            save_review_draft(record['archive'], record['directory'], body)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        return build_review_packet(record['archive'], record['directory'])

    @app.get('/api/experiment/attempts/{session_id}/media/{filename}')
    def experiment_attempt_media(session_id: str, filename: str):
        record = attempt_record(session_id)
        files = {path.name: path for path in record['directory'].iterdir() if path.suffix in ('.wav', '.jpg')}
        if filename not in files:
            raise HTTPException(404, 'This recording is not in the selected attempt.')
        return FileResponse(files[filename])

    @app.get('/api/experiment/report')
    def experiment_report(protocol: str = 'authored'):
        return experiment_summary(protocol)

    @app.get('/api/experiment/export')
    def experiment_export(format: str = 'json', protocol: str = 'authored'):
        report = experiment_summary(protocol)
        if format == 'csv':
            return Response(formal_assignment_csv(report) if protocol == 'formal' else report_csv(report), media_type='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="covis-experiment-attempts.csv"'})
        return JSONResponse(report, headers={'Content-Disposition': 'attachment; filename="covis-experiment.json"'})

    @app.get('/api/bootstrap')
    def bootstrap():
        return app.state.workspace.bootstrap()

    @app.post('/api/session')
    async def session(body: dict):
        ws = app.state.workspace
        if body['mode'] not in ('text', 'push_to_talk', 'live_voice'):
            raise HTTPException(400, 'Choose Text, Push to talk or Live voice.')
        task_id = body.get('task_id')
        if task_id:
            try:
                task_brief(task_id)
            except KeyError:
                raise HTTPException(400, 'Unknown task.')
        condition = body.get('condition', 'bound_revision')
        if condition not in CONDITIONS:
            raise HTTPException(400, 'Choose a supported revision configuration.')
        await ws.archive()
        ws.reset(body['mode'], task_id, body.get('participant_id', ''), condition)
        await ws.send({'type': 'bootstrap', **ws.bootstrap()})
        return ws.bootstrap()

    @app.post('/api/evidence')
    async def evidence(body: dict):
        try:
            return await app.state.workspace.choose_evidence(body)
        except (ValueError, KeyError, StopIteration) as error:
            raise HTTPException(400, str(error))

    @app.get('/api/category-sets')
    def category_sets():
        return {'category_sets': app.state.workspace.category_sets.list()}

    @app.post('/api/category-sets')
    async def save_category_set(body: dict):
        ws = app.state.workspace
        result = await ws.execute('save_category_set', body, actor='user')
        if result['status'] == 'failed':
            raise HTTPException(400, result['message'])
        return ws.bootstrap()

    @app.post('/api/category-sets/{set_id}/apply')
    async def apply_category_set(set_id: str, body: dict):
        ws = app.state.workspace
        await ws.revoke()
        ws.bound_evidence = deepcopy(ws.evidence)
        ws.accept('Apply saved category set', ws.reference)
        result = await ws.execute('apply_category_set', {**body, 'set_id': set_id}, actor='user')
        if result['status'] == 'failed':
            raise HTTPException(400, result['message'])
        return result

    @app.post('/api/task-response')
    def task_response(body: dict):
        ws = app.state.workspace
        ws.task_response = {field: body[field] for field in
                            ('conclusion', 'rationale', 'object_origin', 'calculation_scope')}
        if ws.session.get('assignment', {}).get('protocol') == FORMAL_PROTOCOL:
            ws.task_response.update({field: body[field] for field in ('target_views', 'kept_released')})
        ws.task_response.update(revision=ws.store.state['revision'], submitted_at=datetime.now(timezone.utc).isoformat())
        ws.report = None
        ws.trace.record('task_response_submitted', response=ws.task_response)
        ws.trace.save('task-response.json', ws.task_response)
        return {'response': ws.task_response, 'report': None}

    @app.post('/api/revisions/preview')
    async def preview_revision(body: dict):
        ws = app.state.workspace
        await ws.revoke()
        ws.bound_evidence = deepcopy(ws.evidence)
        label = body.pop('label', 'Revise the selected analysis')
        ws.accept(label, ws.reference)
        ws.trace.record('manual_revision_request', arguments=body)
        result = await ws.execute('preview_revision', body, actor='user')
        if result['status'] == 'failed':
            raise HTTPException(400, result['message'])
        return result

    @app.post('/api/revisions/{proposal_id}/apply')
    async def apply_revision(proposal_id: str):
        result = await app.state.workspace.execute('apply_revision', {'proposal_id': proposal_id}, actor='user')
        if result['status'] in ('failed', 'superseded'):
            raise HTTPException(409, result.get('message', 'This revision has been superseded. Prepare a new revision from the current canvas.'))
        return result

    @app.post('/api/revisions/{proposal_id}/dismiss')
    async def dismiss_revision(proposal_id: str):
        ws = app.state.workspace
        if ws.proposal and ws.proposal['id'] == proposal_id:
            await ws.revoke()
            ws.trace.record('revision_dismissed', proposal_id=proposal_id)
            ws.proposal = None
            ws.prepared_revision = None
            await ws.send({'type': 'proposal', 'proposal': None})
        return {'proposal': ws.proposal}

    @app.post('/api/tools')
    async def tool(body: dict):
        ws = app.state.workspace
        await ws.revoke()
        ws.accept(body.get('label', 'Direct chart edit'), body.get('reference', ws.reference))
        ws.trace.record('manual_edit_requested', text=ws.current_intent, tool=body['name'],
                        arguments=body['arguments'], reference=ws.bound_reference)
        result = await ws.execute(body['name'], body['arguments'], actor='user')
        if result['status'] == 'failed':
            raise HTTPException(400, result['message'])
        return result

    @app.post('/api/undo')
    async def undo():
        ws = app.state.workspace
        if not ws.undo_stack:
            raise HTTPException(400, 'There is no edit to undo.')
        return await ws.restore(ws.undo_stack.pop(), 'undo')

    @app.get('/api/history')
    def history():
        return {'nodes': app.state.workspace.nodes}

    @app.get('/api/nodes/{node_id}')
    def node(node_id: str):
        ws = app.state.workspace
        selected = next(n for n in ws.nodes if n['id'] == node_id)
        return {'node': selected, 'state': ws.node_states[node_id],
                'events': [e for e in ws.trace.events if selected['event_start'] <= e['index'] <= selected['event_index']]}

    @app.post('/api/nodes/{node_id}/restore')
    async def restore(node_id: str):
        ws = app.state.workspace
        ws.undo_stack.append(ws.store.snapshot())
        return await ws.restore(ws.node_states[node_id], 'restore')

    @app.post('/api/finish')
    async def finish(body: dict | None = None):
        reason = (body or {}).get('reason', 'completed')
        if reason not in ('completed', 'timeout', 'abandoned'):
            raise HTTPException(400, 'Choose completion, time limit or unfinished exit.')
        return await app.state.workspace.finish(reason)

    @app.post('/api/review')
    def review(body: dict):
        ws = app.state.workspace
        ws.reviews.append({**body, 'at': datetime.now(timezone.utc).isoformat()})
        ws.trace.record('human_note', **body)
        return {'review_status': 'pending', 'reviews': ws.reviews}

    @app.get('/api/export')
    def export():
        ws = app.state.workspace
        ws.trace.finalize_audio()
        if ws.session.get('trial_status') != 'finished':
            ws.trace.save('session.json', ws.export())
        return FileResponse(ws.trace.directory / 'session.json', filename=f"covis-{ws.session['id']}.json")

    @app.get('/api/media')
    def media():
        ws = app.state.workspace
        ws.trace.finalize_audio()
        items = []
        for path in sorted(ws.trace.directory.iterdir()):
            if path.suffix == '.wav':
                with wave.open(str(path), 'rb') as audio:
                    items.append({'name': path.name, 'url': f'/api/media/{path.name}', 'kind': 'audio',
                                  'sample_rate': audio.getframerate(), 'duration_seconds': audio.getnframes() / audio.getframerate()})
            elif path.suffix == '.jpg':
                items.append({'name': path.name, 'url': f'/api/media/{path.name}', 'kind': 'image'})
        return {'items': items}

    @app.get('/api/media/{filename}')
    def media_file(filename: str):
        directory = app.state.workspace.trace.directory
        files = {p.name: p for p in directory.iterdir() if p.suffix in ('.wav', '.jpg')}
        if filename not in files:
            raise HTTPException(404, 'This recording is not available in the current session.')
        return FileResponse(files[filename])

    @app.get('/api/sessions')
    def sessions():
        records = []
        for path in sorted(settings['trace_dir'].glob('*/session.json'), reverse=True):
            archive = json.loads(path.read_text(encoding='utf-8'))
            records.append({'session': archive['session'], 'report': archive['report'], 'url': f'/api/sessions/{path.parent.name}'})
        return {'items': records}

    @app.get('/api/sessions/{session_id}')
    def archive(session_id: str):
        files = {p.parent.name: p for p in settings['trace_dir'].glob('*/session.json')}
        if session_id not in files:
            raise HTTPException(404, 'This session has not been saved.')
        return FileResponse(files[session_id], filename=f'covis-{session_id}.json')

    @app.websocket('/ws')
    async def socket(websocket: WebSocket):
        ws = app.state.workspace
        await websocket.accept()
        ws.socket = websocket
        await ws.send({'type': 'bootstrap', **ws.bootstrap()})
        try:
            while True:
                message = await websocket.receive_json()
                kind = message['type']
                if (ws.session.get('assignment') and ws.session['trial_status'] != 'running'
                        and kind in ('text', 'voice_start')):
                    await ws.send({'type': 'error', 'message': 'Begin the assigned task before making a request.'})
                    continue
                if kind == 'text':
                    await ws.text(message)
                elif kind == 'voice_start':
                    await ws.start_voice(message)
                elif kind == 'audio':
                    if ws.voice:
                        await ws.voice.audio(message['data'])
                elif kind == 'voice_commit':
                    await ws.voice.commit()
                elif kind == 'voice_stop':
                    await ws.close_voice()
                elif kind == 'context':
                    await ws.set_context(message)
                elif kind == 'cancel':
                    await ws.revoke()
                    ws.trace.record('cancel_requested')
                    await ws.send({'type': 'status', 'status': 'ready'})
                elif kind == 'stop_speaking':
                    ws.muted_responses.add(ws.current_response)
                    ws.trace.record('stop_speaking', response_id=ws.current_response)
                    await ws.send({'type': 'stop_audio'})
                elif kind == 'clock_ping':
                    received = ws.trace.now_ms()
                    await ws.send({'type': 'clock_pong', 'sync_id': message['sync_id'],
                                   'client_clock_id': message['client_clock_id'],
                                   'client_send_ms': message['client_send_ms'], 'session_id': ws.session['id'],
                                   'server_receive_ms': received, 'server_send_ms': ws.trace.now_ms()})
                elif kind == 'clock_sample':
                    ws.trace.calibrate_clock(message['client_clock_id'], message['session_id'], message['samples'])
                elif kind == 'event':
                    if message['name'] == 'mode_selected':
                        if ws.session.get('assignment', {}).get('protocol') != FORMAL_PROTOCOL:
                            ws.session['mode'] = message['details']['mode']
                    ws.record_browser_event(message)
        except WebSocketDisconnect:
            pass
        except Exception as error:
            ws.trace.record('session_error', message=str(error))
            await ws.send({'type': 'error', 'message': str(error)})
        finally:
            ws.socket = None
            await ws.revoke()
            await ws.close_voice()
            ws.trace.finalize_audio()
            if ws.session.get('trial_status') != 'finished':
                ws.trace.save('session.json', ws.export())

    frontend_dir = settings.get('frontend_dir', ROOT / 'frontend' / 'dist')
    if frontend_dir.exists():
        app.mount('/', StaticFiles(directory=frontend_dir, html=True), name='frontend')
    return app
