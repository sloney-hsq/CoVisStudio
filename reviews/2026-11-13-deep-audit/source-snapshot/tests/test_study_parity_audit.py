"""Same model-facing analytical contract and deterministic execution across main paths."""
import asyncio
from pathlib import Path

from scripts.audit_study_parity import controlled


def test_direct_bound_application_contract_and_execution_are_equal(tmp_path):
    result = asyncio.run(controlled(tmp_path, Path('C:/VerbalVis/datasets/olist/data')))
    for field in ('context_differences', 'read_differences', 'result_differences',
                  'post_edit_context_differences', 'receipt_card_differences'):
        assert result[field] == [], (field, result[field])
    for field in ('instruction_equal', 'tools_equal', 'commit_equal', 'clarification_equal'):
        assert result[field], field
    for condition, run in result['runs'].items():
        assert run['commit'] == {'status': 'completed', 'committed': True}, condition
        assert run['clarification'] == {'status': 'awaiting_confirmation', 'committed': False}, condition
        assert run['private_key_hits'] == [], condition
