"""Summarize recorded actions, without inferring attention or understanding."""
from collections import Counter


def interaction_summary(events):
    proposals = {}
    intervals = {}
    saved = []
    applied_sets = []
    unmatched_hidden_events = []
    committed_tools = Counter()
    for event in events:
        name = event['name']
        if name == 'category_set_saved':
            saved.append({'set_id': event['category_set']['id'], 'actor': event['actor'],
                          'event_index': event['index']})
        elif name == 'tool_committed':
            committed_tools[event['tool']] += 1
            if event['tool'] == 'apply_category_set':
                applied_sets.append({'set_id': event['result']['category_set']['id'],
                                     'view_ids': event['result']['changed_view_ids'],
                                     'revision': event['revision'], 'actor': event['actor'],
                                     'event_index': event['index']})
        elif name == 'revision_proposed':
            proposal_id = event['proposal']['id']
            proposals[proposal_id] = {
                'proposal_id': proposal_id, 'generated_event_index': event['index'],
                'generated_by': event['actor'], 'opened_events': [], 'confirmation_clicks': [],
                'revision_requests': [], 'user_confirmations': [], 'applications': [],
                'visible_intervals': [],
            }
        elif name.startswith('revision_card_') or name == 'revision_confirmation_clicked':
            detail = event['details']
            proposal_id = detail['proposal_id']
            proposal = proposals[proposal_id]
            if name == 'revision_card_visible':
                interval = {'display_id': detail['display_id'], 'surface': detail['surface'],
                            'start_client_ms': event['client_ms'], 'end_client_ms': None,
                            'visible_ms': None, 'start_event_index': event['index'],
                            'status_at_start': detail.get('proposal_status'),
                            'end_event_index': None}
                intervals[detail['display_id']] = interval
                proposal['visible_intervals'].append(interval)
            elif name == 'revision_card_hidden':
                if detail['display_id'] not in intervals:
                    # A recorded reload defect lost the visible event before the WS opened.
                    # Preserve the unmatched close; do not reconstruct exposure from its duration.
                    unmatched_hidden_events.append({'event_index': event['index'],
                                                    'proposal_id': proposal_id,
                                                    'display_id': detail['display_id'],
                                                    'visible_ms': None})
                    continue
                interval = intervals[detail['display_id']]
                interval.update(end_client_ms=event['client_ms'], end_event_index=event['index'],
                                visible_ms=round(event['client_ms'] - interval['start_client_ms'], 3))
            else:
                field = {'revision_card_opened': 'opened_events',
                         'revision_confirmation_clicked': 'confirmation_clicks',
                         'revision_card_revision_requested': 'revision_requests'}[name]
                proposal[field].append({'event_index': event['index'], 'client_ms': event['client_ms']})
        elif name == 'revision_confirmed':
            proposals[event['proposal_id']]['user_confirmations'].append({
                'event_index': event['index'], 'revision': event['committed_revision'], 'channel': event['channel']})
        elif name == 'revision_applied':
            proposals[event['proposal']['id']]['applications'].append({
                'event_index': event['index'], 'actor': event['actor'],
                'revision': event['proposal']['committed_revision']})

    for proposal in proposals.values():
        exposures = proposal['visible_intervals']
        proposal['displayed'] = bool(exposures)
        proposal['detail_opened'] = bool(proposal['opened_events'])
        proposal['user_confirmed'] = bool(proposal['user_confirmations'])
        proposal['model_applied'] = any(item['actor'] == 'model' for item in proposal['applications'])
        proposal['closed_visible_ms_by_surface'] = {
            surface: round(sum(item['visible_ms'] for item in exposures
                               if item['surface'] == surface and item['visible_ms'] is not None), 3)
            for surface in ('summary', 'detail')}
        proposal['open_visible_interval_count'] = sum(item['visible_ms'] is None for item in exposures)

    cards = list(proposals.values())
    return {
        'category_sets': {'saved_count': len(saved), 'application_count': len(applied_sets),
                          'saved': saved, 'applications': applied_sets},
        'revision_cards': {
            'generated_count': len(cards),
            'displayed_count': sum(card['displayed'] for card in cards),
            'detail_opened_count': sum(card['detail_opened'] for card in cards),
            'user_confirmed_count': sum(card['user_confirmed'] for card in cards),
            'model_applied_count': sum(card['model_applied'] for card in cards),
            'unmatched_hidden_events': unmatched_hidden_events,
            'proposals': cards,
        },
        'committed_tool_counts': dict(committed_tools),
        'interpretation': 'Visibility records an on-screen card in a visible page. It does not establish reading, understanding or agreement. A successful Apply action records confirmation; model application is separate.',
        'timing': 'Durations pair visible/hidden events from the same browser display interval. Open intervals stay unknown. Surface durations may overlap and must not be summed as attention time. Server and browser clocks are not subtracted.',
        'human_attention_review': 'pending',
    }
