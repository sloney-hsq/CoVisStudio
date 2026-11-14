"""Offline observations of technical completion and user-facing delivery.

This is a read model, never publication authority or a semantic success score.
"""
from copy import deepcopy


def _receipt(event):
    return {key: deepcopy(event[key]) for key in (
        'event_id', 'index', 'server_ms', 'client_ms', 'client_clock_id',
        'aligned_server_ms', 'calibration_id', 'uncertainty_ms') if key in event}


def summarize_delivery(events):
    requests, responses, surfaces, controls = {}, {}, {}, []
    for event in events:
        name = event['name']
        payload = {**event.get('event', {}), **event.get('details', {})}
        rid = event.get('request_id', payload.get('request_id'))
        response_id = event.get('response_id', payload.get('response_id'))
        request = None
        if rid is not None:
            request = requests.setdefault(rid, {'request_id': rid, 'epoch': event.get('epoch', payload.get('epoch')),
                'accepted': None, 'commits': [], 'response_ids': [], 'control_observations': []})
        if name == 'request_accepted':
            if request is None:
                request = requests.setdefault('__unattributed__', {'request_id': None, 'epoch': None,
                    'accepted': None, 'commits': [], 'response_ids': [], 'control_observations': []})
            request['accepted'] = {**_receipt(event), 'text': event.get('text'),
                'reference': deepcopy(event.get('reference'))}
        if name in ('tool_committed', 'undo', 'restore'):
            result = event.get('result', {})
            commit = {**_receipt(event), 'request_id': rid, 'response_id': response_id,
                'revision': event['revision'], 'tool': event.get('tool', name),
                'view_ids': result.get('changed_view_ids', [v['id'] for v in result.get('views', event.get('state', {}).get('views', []))]),
                'status': 'committed', 'independent_numeric_audit': 'not_checked',
                'views': [{k: deepcopy(v[k]) for k in ('id', 'number', 'chart_type', 'source') if k in v}
                          for v in result.get('views', [])]}
            if request is not None:
                request['commits'].append(commit)
            else:
                requests.setdefault('__unattributed__', {'request_id': None, 'epoch': None, 'accepted': None,
                    'commits': [], 'response_ids': [], 'control_observations': []})['commits'].append(commit)
        if name in ('speech_start', 'cancel_requested', 'stop_speaking', 'request_cancelled', 'request_failed'):
            control = {**_receipt(event), 'name': name, 'request_id': rid, 'response_id': response_id,
                       'reason': event.get('reason', payload.get('reason'))}
            controls.append(control)
            if request is not None:
                request['control_observations'].append(control)
        if response_id is not None:
            response = responses.setdefault(response_id, {'response_id': response_id, 'request_id': rid,
                'epoch': event.get('epoch', payload.get('epoch')), 'provider_status': 'pending',
                'generated_text': '', 'generated_text_status': 'pending', 'received_audio_samples': 0,
                'playback_status': 'unknown', 'playback': None, 'playback_observations': [],
                'human_semantic_consistency': 'pending', 'human_listening': 'pending',
                'partial_text_word_alignment': 'unknown'})
            if response['request_id'] is None and rid is not None:
                response['request_id'] = rid
                response['epoch'] = event.get('epoch', payload.get('epoch'))
            if request is not None and response_id not in request['response_ids']:
                request['response_ids'].append(response_id)
            if name == 'assistant_done':
                response['generated_text'] = payload.get('text', '')
                response['generated_text_status'] = 'complete_received'
            elif name == 'assistant_delta' and response['generated_text_status'] != 'complete_received':
                response['generated_text'] += payload.get('text', payload.get('delta', ''))
                response['generated_text_status'] = 'partial_received'
            elif name == 'response_end':
                response['provider_status'] = payload.get('status', 'unknown')
            elif name == 'audio_received':
                response['received_audio_samples'] += event['sample_end'] - event['sample_start']
            elif name.startswith('playback_'):
                observation = {**_receipt(event), 'name': name, **deepcopy(payload)}
                basis = payload.get('timing_basis')
                observation['measurement'] = ('source_cursor' if basis == 'audio_worklet_source_cursor'
                                              else 'estimate' if basis == 'browser_audio_clock' else 'unknown')
                response['playback_observations'].append(observation)
                response['playback'] = observation
                response['playback_status'] = 'pending'
                if name == 'playback_stopped' or payload.get('interrupted'):
                    response['playback_status'] = 'interrupted'
                elif name == 'playback_end' and payload.get('queue_empty') and payload.get('received_samples', 0) > 0 and payload.get('played_samples') == payload.get('received_samples'):
                    response['playback_status'] = 'complete'
                elif name == 'playback_end' and not payload.get('started') and not payload.get('played_samples'):
                    response['playback_status'] = 'not_started'
        if name in ('chart_rendered', 'chart_visible', 'chart_hidden'):
            key = tuple(payload.get(k) for k in ('revision', 'view_id', 'surface_id', 'render_generation'))
            surface = surfaces.setdefault(key, {k: payload.get(k) for k in ('revision', 'view_id', 'surface_id', 'render_generation')})
            surface.setdefault('renders', [])
            surface.setdefault('exposures', [])
            observed = {**_receipt(event), **deepcopy(payload)}
            if name == 'chart_rendered':
                if not any(r.get('render_completed_client_ms') == payload.get('render_completed_client_ms') for r in surface['renders']):
                    surface['renders'].append(observed)
            elif name == 'chart_visible':
                surface['exposures'].append({'start': observed, 'end': None})
            else:
                for exposure in reversed(surface['exposures']):
                    if exposure['start'].get('display_id') == payload.get('display_id') and exposure['end'] is None:
                        exposure['end'] = observed
                        break
    return {'schema': 'covis-delivery-1', 'requests': list(requests.values()),
        'responses': list(responses.values()), 'chart_surfaces': list(surfaces.values()),
        'control_observations': controls, 'human_semantic_consistency': 'pending', 'human_listening': 'pending',
        'partial_text_word_alignment': 'unknown',
        'interpretation': 'Commit, render, exposure, generated text and playback are independent observations. '
                          'Playback is not acoustic listening or comprehension. Control events do not grade semantic mismatch. '
                          'Earlier legitimate commits remain recorded after later revocation.'}
