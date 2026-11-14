"""Distinguish a generated preview, browser exposure and an accepted user action."""
from backend.observations import interaction_summary
from backend.trace import Trace


def test_exposure_is_not_confirmation_or_understanding(tmp_path):
    trace = Trace(tmp_path)
    card = {'id': 'p1', 'status': 'pending'}
    trace.record('revision_proposed', proposal=card, actor='model')
    trace.record('revision_card_visible', client_ms=100,
                 details={'proposal_id': 'p1', 'display_id': 'page1-summary-1', 'surface': 'summary', 'proposal_status': 'pending'})
    trace.record('revision_card_opened', client_ms=200, details={'proposal_id': 'p1'})
    trace.record('revision_card_visible', client_ms=200,
                 details={'proposal_id': 'p1', 'display_id': 'page1-detail-1', 'surface': 'detail', 'proposal_status': 'pending'})
    trace.record('revision_card_hidden', client_ms=600,
                 details={'proposal_id': 'p1', 'display_id': 'page1-summary-1', 'surface': 'summary'})
    trace.record('revision_confirmation_clicked', client_ms=650, details={'proposal_id': 'p1'})
    # A click alone can be superseded before application; no successful confirmation yet.
    summary = interaction_summary(trace.events)
    result = summary['revision_cards']['proposals'][0]
    assert result['closed_visible_ms_by_surface'] == {'summary': 500, 'detail': 0}
    assert result['open_visible_interval_count'] == 1
    assert result['displayed'] and result['detail_opened']
    assert not result['user_confirmed'] and not result['model_applied']
    assert summary['human_attention_review'] == 'pending'
    card.update(status='committed', committed_revision=7)
    trace.record('revision_applied', proposal=card, actor='model')
    updated = interaction_summary(trace.events)['revision_cards']
    assert updated['model_applied_count'] == 1 and updated['user_confirmed_count'] == 0
    assert trace.events[0]['proposal']['status'] == 'pending'  # append-only event payload


def test_generation_without_browser_exposure_is_not_viewed(tmp_path):
    trace = Trace(tmp_path)
    trace.record('revision_proposed', proposal={'id': 'p1'}, actor='user')
    trace.record('revision_applied', proposal={'id': 'p1', 'committed_revision': 1}, actor='user')
    trace.record('revision_confirmed', proposal_id='p1', committed_revision=1, channel='apply_button')
    summary = interaction_summary(trace.events)['revision_cards']
    assert summary['generated_count'] == summary['user_confirmed_count'] == 1
    assert summary['displayed_count'] == summary['detail_opened_count'] == summary['model_applied_count'] == 0


def test_original_reload_record_does_not_invent_missing_exposure(tmp_path):
    trace = Trace(tmp_path)
    trace.record('revision_proposed', proposal={'id': 'p1'}, actor='model')
    trace.record('revision_card_hidden', client_ms=1200,
                 details={'proposal_id': 'p1', 'display_id': 'lost-before-connect', 'surface': 'summary', 'duration_ms': 400})
    cards = interaction_summary(trace.events)['revision_cards']
    assert cards['displayed_count'] == 0
    assert cards['unmatched_hidden_events'][0]['visible_ms'] is None
