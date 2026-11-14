"""Participant briefs and private mappings into the existing revision scorer.

Only business_tasks() is public. Cases describe authored starting histories and
required data outcomes, not a gold business recommendation or a model answer.
"""
from copy import deepcopy
import re

BUSINESS_PROTOCOL = 'covis-business-0.1'
EXPERIMENT_PROTOCOL = 'covis-matched-0.1'

_BRIEFS = [
    {
        'id': 'biz_01_sp_priorities_mg',
        'title': 'Assess SP priority categories in MG',
        'kind': 'regional_service_review',
        'business_goal': (
            'Headquarters identified its three priority categories by delivered-order volume in SP in 2017. '
            'The MG team needs to assess service quality for those same categories before supporting the rollout. '
            'The current dashboard instead describes MG\'s own leading categories. Recommend one service issue '
            'to investigate in MG, or explain why the evidence does not justify a clear priority.'),
        'mandatory_outcomes': [
            'Use the categories from the earliest complete SP comparison for the current low-review-rate and delivery-time views.',
            'Calculate both service measures using MG delivered orders in calendar year 2017; keep their existing measures.',
            'Keep the current MG order-volume view unchanged as the local business context.',
            'Explain your recommendation with evidence, including the limits of comparing review rates and mean delivery time.',
        ],
        'initial': 'Historical SP priorities; current MG leaders; 2017 delivered orders',
        'response_prompt': 'What should the MG team investigate, and why? State where the category set came from and where and when the service measures were calculated.',
    },
    {
        'id': 'biz_02_mg_local_priorities',
        'title': 'Set MG local operating priorities',
        'kind': 'release_and_rerank',
        'business_goal': (
            'The dashboard currently monitors MG using a fixed set of headquarters\' SP priority categories. '
            'The next planning meeting is about MG\'s own workload, so the comparison should now follow MG\'s '
            'three highest-volume categories rather than the inherited set. Recommend where the local team '
            'should investigate service performance among those categories.'),
        'mandatory_outcomes': [
            'Release the fixed SP category set in all three current views and use a dynamic top-three ranking by MG delivered-order volume.',
            'Use the same MG 2017 ranking rule for volume, low-review rate and delivery time, preserving each measure and the delivered-order scope.',
            'Explain how the local planning objective changes the appropriate category selection and support a recommendation with the resulting evidence.',
        ],
        'initial': 'Historical SP priorities; current MG measures still using that fixed SP set',
        'response_prompt': 'What local service priority would you recommend, and why? Explain why the old set was released, how the new categories were selected, and the region and period behind the values.',
    },
    {
        'id': 'biz_03_seasonal_same_cohort',
        'title': 'Compare service for a stable seasonal cohort',
        'kind': 'seasonal_same_cohort',
        'business_goal': (
            'An SP service manager wants to know whether the categories leading order volume in January–March 2017 '
            'show different service outcomes in October–December. The current dashboard follows the fourth quarter\'s '
            'leaders, which may mix changing category selection with changing service performance. Use a stable '
            'first-quarter cohort to support a seasonal service observation and identify a useful follow-up.'),
        'mandatory_outcomes': [
            'Use the earliest complete January–March SP comparison as the category cohort for the current low-review-rate and delivery-time views.',
            'Calculate those two current views for SP delivered orders in October–December 2017, keeping the service measures.',
            'Keep the fourth-quarter order-volume view unchanged; compare current service results with the saved first-quarter service evidence.',
            'Describe an observed change or lack of clear change and a follow-up question; do not treat a quarter-to-quarter association as a proven seasonal cause.',
        ],
        'initial': 'Historical January–March SP leaders; current October–December SP leaders',
        'response_prompt': 'What service change is supported for the same categories, and what would you investigate next? Identify the category-selection period and both measurement periods.',
    },
    {
        'id': 'biz_04_stable_metric_control',
        'title': 'Add the revenue perspective without changing the cohort',
        'kind': 'stable_local_metric',
        'business_goal': (
            'An SP manager already has an agreed 2017 category cohort and service comparison. For the budget discussion, '
            'they need the financial scale of those same categories instead of their order counts. Show revenue in the '
            'volume view while retaining the service evidence, then discuss whether revenue changes your operating priority.'),
        'mandatory_outcomes': [
            'Change only the order-volume view to item revenue excluding freight, using its current fixed categories.',
            'Keep SP, calendar year 2017 and delivered orders; leave the low-review-rate and delivery-time views unchanged.',
            'Support your business conclusion using revenue and service evidence; distinguish revenue from profit and from order volume.',
        ],
        'initial': 'One agreed SP 2017 cohort; order volume, low-review rate and delivery time',
        'response_prompt': 'Does the revenue perspective change your operating priority, and why? Identify the category origin and the region, dates and metric used in the revised view.',
    },
]


def business_tasks():
    """English goals and constraints; no member IDs or evaluator target sources."""
    return [
        {**deepcopy(brief), 'description': brief['business_goal'],
         'goal': brief['business_goal'] + '\n\nRequired outcomes:\n' + '\n'.join(brief['mandatory_outcomes']),
         'split': 'participant_material', 'protocol': BUSINESS_PROTOCOL,
         'duration_minutes': 8, 'voice_budget_seconds': 60,
         'interpretation_review': 'pending'}
        for brief in _BRIEFS
    ]


def business_case(task_id):
    """Private mapping: share setup, SQL oracle and publication scoring with diagnostics."""
    brief = next(task for task in _BRIEFS if task['id'] == task_id)
    case = {
        'id': task_id, 'title': brief['title'], 'instruction': brief['business_goal'],
        'family': brief['kind'], 'split': 'participant_material',
        'phases': [{'region': 'SP'}, {'region': 'MG'}],
        'targets': [2, 3], 'action': 'use_evidence', 'patch': {},
        'evidence_phase': 0, 'evidence_indices': None, 'resolution': None,
        'preserve_presentation': False,
    }
    if task_id == 'biz_02_mg_local_priorities':
        case.update(phases=[{'region': 'SP'}, {'region': 'MG', 'cohort': 'previous'}],
                    targets=[1, 2, 3], action='rerank', patch={'top_n': 3, 'rank_by': 'orders'})
    elif task_id == 'biz_03_seasonal_same_cohort':
        case['phases'] = [
            {'region': 'SP', 'start': '2017-01-01', 'end': '2017-04-01'},
            {'region': 'SP', 'start': '2017-10-01', 'end': '2018-01-01'},
        ]
    elif task_id == 'biz_04_stable_metric_control':
        case.update(phases=[{'region': 'SP'}], targets=[1], action='keep_current', patch={'metric': 'revenue'})
    return case


def experiment_tasks():
    """Parallel participant briefs; matching facts and answers are evaluator-only."""
    result = []
    for family_index, original in enumerate(business_tasks(), 1):
        for variant in ('a', 'b'):
            source, current = ('RJ', 'MG') if variant == 'a' else ('MG', 'RJ')
            region = 'RJ' if variant == 'a' else 'MG'
            replacements = {'SP': source, 'MG': current} if family_index in (1, 2) else {'SP': region}

            def rewrite(value):
                value = re.sub(r'\b(SP|MG)\b', lambda match: replacements.get(match[0], match[0]), value)
                if family_index == 3:
                    value = value.replace('October–December', 'July–September').replace('fourth', 'third')
                return value

            brief = {key: rewrite(value) if isinstance(value, str) else deepcopy(value)
                     for key, value in original.items()}
            brief['mandatory_outcomes'] = [rewrite(value) for value in original['mandatory_outcomes']]
            brief.update(id=f'exp_{family_index:02d}_{variant}', family_id=f'{family_index:02d}',
                         variant_id=variant, protocol=EXPERIMENT_PROTOCOL, split='matched_participant_material')
            result.append(brief)
    return result


def experiment_case(task_id):
    """Private parallel configurations. One view/source rule is changed per family."""
    _, family, variant = task_id.split('_')
    original = _BRIEFS[int(family) - 1]
    case = business_case(original['id'])
    brief = next(task for task in experiment_tasks() if task['id'] == task_id)
    source, current = ('RJ', 'MG') if variant == 'a' else ('MG', 'RJ')
    region = 'RJ' if variant == 'a' else 'MG'
    case.update(id=task_id, title=brief['title'], instruction=brief['business_goal'],
                family_id=family, variant_id=variant, split='matched_participant_material')
    if family in ('01', '02'):
        case['phases'][0]['region'] = source
        case['phases'][1]['region'] = current
    elif family == '03':
        case['phases'] = [
            {'region': region, 'start': '2017-01-01', 'end': '2017-04-01'},
            {'region': region, 'start': '2017-07-01', 'end': '2017-10-01'},
        ]
    else:
        case['phases'][0]['region'] = region
    return case
