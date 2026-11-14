"""Evaluator-only authored trial specifications; never include in model context."""
from copy import deepcopy

from backend.oracle import category_rows, numeric_rows_equal


NEW_TTS_CLIPS = {
    'explain': 'Explain the selected charts and their current region, dates, and categories.',
    '02_revision': 'Use the current local top three categories by order volume in all charts. Release fixed categories; keep other conditions.',
    '04_revision': 'Change chart one to product revenue. Keep these categories, the current filters, and the other charts.',
}

CASES = {
    '01': {'task_id': 'exp_01_a', 'targets': ['v2', 'v3'],
           'evidence': {'revision': 3, 'view_id': 'v1'},
           'initial_clip': '01_initial', 'revision_clip': '01_revision',
           'initial_requires_commit': True},
    '02': {'task_id': 'exp_02_a', 'targets': ['v1', 'v2', 'v3'],
           'evidence': None, 'initial_clip': 'explain', 'revision_clip': '02_revision',
           'initial_requires_commit': False},
    '03': {'task_id': 'exp_03_a', 'targets': ['v2', 'v3'],
           'evidence': {'revision': 3, 'view_id': 'v1'},
           'initial_clip': 'explain', 'revision_clip': '03_revision',
           'initial_requires_commit': False},
    '04': {'task_id': 'exp_04_a', 'targets': ['v1'],
           'evidence': None, 'initial_clip': 'explain', 'revision_clip': '04_revision',
           'initial_requires_commit': False},
}


def expected_sources(initial, snapshots, case_id):
    """Derive explicit authored final intent from setup, not observed model edits."""
    sources = {view['id']: deepcopy(view['source']) for view in initial['views']}
    case = CASES[case_id]
    if case_id in ('01', '03'):
        evidence = case['evidence']
        historical = snapshots[evidence['revision']]
        view = next(view for view in historical['views'] if view['id'] == evidence['view_id'])
        members = [row['label'] for row in view['data']['rows']]
        for target in case['targets']:
            sources[target].update(categories=deepcopy(members), top_n=None)
        if case_id == '01':
            for target in case['targets']:
                sources[target].update(start='2017-01-01', end='2017-04-01')
    elif case_id == '02':
        for target in case['targets']:
            sources[target].update(categories=None, top_n=3, rank_by='orders')
    elif case_id == '04':
        sources['v1']['metric'] = 'revenue'
    return sources


def score_final(data, initial, final, snapshots, case_id):
    """Source identity, untargeted preservation and independent real Olist values."""
    expected = expected_sources(initial, snapshots, case_id)
    old = {view['id']: view for view in initial['views']}
    observed = {view['id']: view for view in final['views']}
    checks = {'exact_view_ids': set(observed) == set(expected)}
    for view_id, source in expected.items():
        view = observed.get(view_id)
        checks[f'{view_id}_source'] = view is not None and view['source'] == source
        checks[f'{view_id}_independent_sql'] = view is not None and numeric_rows_equal(
            view['data']['rows'], category_rows(data, source))
        if view_id not in CASES[case_id]['targets']:
            checks[f'{view_id}_unchanged'] = view == old[view_id]
    return {'passed': all(checks.values()), 'checks': checks, 'expected_sources': expected}
