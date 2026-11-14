import json

from scripts.compare_archived_response_context import compare


def test_context_diff_uses_only_events_before_archived_input(tmp_path):
    filename = 'model-input-session-update.json'
    context = {'current_dashboard': {'revision': 6, 'views': []}, 'marker': 'unchanged'}
    original = {'session': {'instructions': 'Archived policy\n' + json.dumps(context)}}
    (tmp_path / filename).write_text(json.dumps(original), encoding='utf-8')
    events = [dict(name='model_input', index=10, status='sent', file=filename, request_id='r5'),
              dict(name='tool_committed', index=11, request_id='r5', revision=7),
              dict(name='request_outcome', index=12, request_id='r5', status='committed', committed=True)]
    report = dict(condition='direct', session_directory=str(tmp_path), events=events)
    (tmp_path / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    result = compare(tmp_path, filename)
    assert result['changed_existing_fields'] == []
    execution = result['added_context_fields']['execution_state']
    assert execution['public_revision'] == 6
    assert execution['request_committed'] is False
    assert execution['recent_request_outcomes'] == []
