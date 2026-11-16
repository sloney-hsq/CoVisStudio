"""Shared metric definitions reach every tool that exposes a metric field."""
from backend.app import MODEL_TOOLS


TOOLS = {tool['function']['name']: tool['function']['parameters'] for tool in MODEL_TOOLS}


def metric_descriptions(node):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == 'metric' and isinstance(value, dict) and isinstance(value.get('description'), str):
                found.append(value['description'])
            found.extend(metric_descriptions(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(metric_descriptions(item))
    return found


def test_metric_rules_reach_every_tool_that_exposes_metric():
    expected = ('create_chart', 'edit_charts', 'revise_analysis', 'preview_revision',
                'apply_evidence_candidate', 'apply_category_set')
    descriptions = set()
    for name in expected:
        found = metric_descriptions(TOOLS[name])
        assert len(found) == 1, name
        assert 'excluding freight' in found[0], name
        assert 'within-group' in found[0], name
        descriptions.add(found[0])
    assert len(descriptions) == 1
