"""Choice-preserving materials for the prospective two-condition study.

These briefs constrain business scope, not the participant's intended cohort.
The exp_* histories are reused only as labelled starting evidence.
"""
from copy import deepcopy
import hashlib
import json


FORMAL_PROTOCOL = 'covis-formal-study-0.1'
FORMAL_MATERIALS_PROTOCOL = 'covis-formal-materials-0.1'
VOICE_BUDGET_SECONDS = 60
TASK_LIMIT_SECONDS = 480

_RESPONSE_PROMPT = (
    'State your recommendation and its supporting evidence. Identify how you selected the categories, '
    'which views you changed, and the region, dates and measures used. Explain any choice you revised '
    'and which conditions you kept or released; if you did not revise a choice, say so. '
    'An uncertain conclusion is acceptable when the evidence is insufficient.'
)


def _scope(region, start='2017-01-01', end='2018-01-01'):
    return {'region': region, 'start': start, 'end': end, 'status': 'delivered', 'dimension': 'category'}


def _source_constraint(number, source):
    return {'id': f'view_{number}_scope', 'kind': 'source_fields',
            'view_number': number, 'required': source}


def formal_tasks():
    """Four business families × two structural variants; no expected member set."""
    result = []
    for family in range(1, 5):
        for variant in ('a', 'b'):
            historical, current = ('RJ', 'MG') if variant == 'a' else ('MG', 'RJ')
            region = historical
            service_scope = _scope(current if family in (1, 2) else region)
            if family == 3:
                service_scope = _scope(region, '2017-07-01', '2017-10-01')
            constraints = [
                _source_constraint(2, {**service_scope, 'metric': 'low_review_rate'}),
                _source_constraint(3, {**service_scope, 'metric': 'avg_delivery_days'}),
            ]
            if family == 1:
                title = f'Choose a service investigation for {current}'
                goal = (
                    f'The {current} team needs a defensible service investigation for 2017. Earlier {historical} '
                    f'comparisons and the current {current} leaders offer different starting points. '
                    'Choose the categories that best support your investigation, examine review risk and delivery '
                    'time, and recommend a follow-up. You may keep, combine, replace or narrow an earlier choice '
                    'as you inspect the evidence. The order-volume view remains the local context for the meeting.'
                )
                rules = [
                    f'Use {current} delivered orders in calendar year 2017 for service views 2 and 3, retaining their measures.',
                    'Compare the same chosen categories in both service views; leave order-volume view 1 unchanged.',
                ]
                choices = ['Choose historical, current or other categories supported by the data.',
                           'Choose explicit members or a ranking rule, and revise that choice if useful.']
                constraints += [{'id': 'context_unchanged', 'kind': 'unchanged_view', 'view_number': 1},
                                {'id': 'service_cohort', 'kind': 'same_members', 'view_numbers': [2, 3]}]
                initial = f'Authored {historical} history followed by current {current} leaders; 2017 delivered orders'
            elif family == 2:
                title = f'Choose local operating priorities for {current}'
                goal = (
                    f'The {current} team is reconsidering a monitoring dashboard inherited from {historical}. '
                    'Decide which categories deserve local attention and whether a fixed selection or a dynamic '
                    'ranking better serves that decision. Compare workload, review risk and delivery time, then '
                    'recommend an investigation. Keeping the inherited categories is allowed if you justify it; '
                    'you may instead release, narrow or replace them based on the evidence.'
                )
                rules = [
                    f'Use {current} delivered orders in calendar year 2017 in all three views.',
                    'Retain orders in view 1, low-review rate in view 2 and delivery time in view 3; compare the same categories.',
                ]
                choices = ['Retain, narrow or replace the inherited categories.',
                           'Choose a fixed cohort or the ranking measure and count; no ranking rule is prescribed.']
                constraints += [_source_constraint(1, {**service_scope, 'metric': 'orders'}),
                                {'id': 'comparison_cohort', 'kind': 'same_members', 'view_numbers': [1, 2, 3]}]
                initial = f'Authored {historical} history; current {current} measures retain that starting cohort'
            elif family == 3:
                title = f'Investigate service changes in {region}'
                goal = (
                    f'The {region} manager wants to investigate service differences between January–March and '
                    'July–September 2017. The saved and current comparisons have different leading categories. '
                    'Choose a category cohort that makes your comparison useful and examine the two service '
                    'measures. You may keep an earlier selection or change it while exploring. Explain the '
                    'observed difference, uncertainty and a follow-up without treating association as seasonal causation.'
                )
                rules = [
                    f'Final service views 2 and 3 use {region} delivered orders in July–September 2017, retaining their measures.',
                    'Use the same chosen categories in both service views; keep third-quarter order-volume view 1 unchanged.',
                    'Any claim about change must compare the chosen categories over both stated periods; explain unavailable evidence.',
                ]
                choices = ['Choose the comparison cohort from either period or another explicit selection.',
                           'Choose its selection rule, and revise or narrow it if the evidence calls for it.']
                constraints += [{'id': 'context_unchanged', 'kind': 'unchanged_view', 'view_number': 1},
                                {'id': 'service_cohort', 'kind': 'same_members', 'view_numbers': [2, 3]}]
                initial = f'Authored {region} January–March history followed by July–September leaders'
            else:
                title = f'Review financial and service priorities in {region}'
                goal = (
                    f'The {region} manager needs a financial perspective on the 2017 service comparison. '
                    'Choose a defensible category cohort, show its item revenue alongside review risk and delivery '
                    'time, and discuss whether the financial evidence changes your operating recommendation. '
                    'The starting cohort is a candidate, not an agreed answer: you may retain, narrow or replace '
                    'it and revise your selection rule as the discussion develops.'
                )
                rules = [
                    f'Use {region} delivered orders in calendar year 2017 in all three views.',
                    'Show revenue excluding freight in view 1, retain low-review rate in view 2 and delivery time in view 3, using the same chosen categories.',
                    'Distinguish revenue from order volume and profit when explaining the recommendation.',
                ]
                choices = ['Choose whether to retain, narrow or replace the starting cohort.',
                           'Choose fixed members or a common ranking rule for the three-view comparison.']
                constraints += [_source_constraint(1, {**service_scope, 'metric': 'revenue'}),
                                {'id': 'comparison_cohort', 'kind': 'same_members', 'view_numbers': [1, 2, 3]}]
                initial = f'Authored {region} 2017 starting cohort with orders and two service measures'
            result.append({
                'id': f'study_{family:02d}_{variant}', 'family_id': f'{family:02d}', 'variant_id': variant,
                'protocol': FORMAL_MATERIALS_PROTOCOL, 'split': 'formal_study_candidate',
                'title': title, 'kind': ('regional_service_review', 'local_priorities',
                                        'seasonal_comparison', 'financial_service_review')[family - 1],
                'business_goal': goal, 'description': goal,
                'goal': goal + '\n\nBusiness constraints:\n' + '\n'.join(rules)
                        + '\n\nYour choices:\n' + '\n'.join(choices),
                'mandatory_outcomes': rules, 'hard_constraints': constraints,
                'participant_choices': choices, 'initial': initial,
                'response_prompt': _RESPONSE_PROMPT, 'duration_minutes': 8,
                'voice_budget_seconds': VOICE_BUDGET_SECONDS,
                'interpretation_review': 'pending', 'material_review': 'pending',
                'difficulty_equivalence': 'not_established',
            })
    return result


def formal_task_brief(task_id):
    return next(task for task in formal_tasks() if task['id'] == task_id)


def formal_setup_operations(task_id, data):
    """Reuse only authored real-query setup, never an exp_* expected answer."""
    from .study import setup_operations
    task = formal_task_brief(task_id)
    return setup_operations(f"exp_{task['family_id']}_{task['variant_id']}", data)


def content_sha256(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def formal_materials_manifest():
    materials = formal_tasks()
    return {
        'protocol': FORMAL_PROTOCOL, 'materials_protocol': FORMAL_MATERIALS_PROTOCOL,
        'materials': deepcopy(materials), 'materials_sha256': content_sha256(materials),
        'review_status': 'pending', 'approved_by': None, 'approved_at': None,
        'human_difficulty_equivalence': 'not_established',
        'scoring_basis': 'Public hard constraints plus independently annotated participant intent; no fixed expected_sources.',
    }
