"""Pure guarded-score panel adapter. README_PACED_PANEL_PLAN_GUARDED_V1.md."""
from copy import deepcopy
from pathlib import Path

from common import bind
from reservation_budget_v1 import require
import paced_panel_plan_v3 as previous
import panel_scoring_admission_guarded_v1 as scores

HERE = Path(__file__).resolve().parent
SCHEMA = 'n4-paced-panel-plan-guarded-v1'
SCORING_RELATIONSHIP = 'Accepted main V3 and independently reviewed guarded V1 modes; exact original contexts'
OWN = ('paced_panel_plan_guarded_v1.py', 'test_paced_panel_plan_guarded_v1.py',
       'probe_paced_panel_plan_guarded_v1.py', 'README_PACED_PANEL_PLAN_GUARDED_V1.md')


def code_bindings():
    entries = scores.code_bindings()+[bind(HERE/name) for name in OWN]
    unique = {}
    for b in entries:
        require(b['path'] not in unique or unique[b['path']] == b, 'Conflicting planner source')
        unique[b['path']] = b
    return [b for _, b in sorted(unique.items())]


def application_context(scored, source, source_binding, app_binding, common):
    """Preserve the qualified application derivative and its component parent."""
    context = previous.application_context(scored, source, source_binding, app_binding, common)
    context['scoring_review_policy'] = deepcopy(scores.POLICY)
    return context


def build_plan(selection, reviews, jobs, panel, regression, catalog, context):
    """Pure dictionary transformation; callers still need actual review admission."""
    require(context.get('scoring_review_policy') == scores.POLICY,
            'Exact guarded score-review policy required')
    plan = previous.build_plan(selection, reviews, jobs, panel, regression, catalog, context)
    plan['schema'] = SCHEMA
    plan['scoring_relationship'] = SCORING_RELATIONSHIP
    return plan


def execution_payload(plan, index):
    """Preserve the 13-field inference allowlist with execution permission false."""
    require(plan.get('schema') == SCHEMA and plan.get('scoring_relationship') == SCORING_RELATIONSHIP
            and plan.get('context', {}).get('scoring_review_policy') == scores.POLICY,
            'Wrong guarded-score application plan')
    return previous.execution_payload(dict(plan, schema=previous.SCHEMA), index)


# Deliberately no prepare/admit_plan/launch API: production reconstruction,
# producer resource provenance and matching consumers require their own qualified
# derivative. Changing this schema to a previous one is not an admission route.
