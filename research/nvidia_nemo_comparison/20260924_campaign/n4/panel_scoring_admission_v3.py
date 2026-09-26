"""Closed V3 scoring evidence for selected panels. README_PACED_PANEL_PLAN_V4.md."""
from copy import deepcopy
from pathlib import Path

from common import bind, fingerprint, load, verify
from metric_process import exact_process
import paced_panel_plan as original
import scoring_bank_v3 as scoring
import review_scoring_bank_v3 as reviewer
from review_scoring_bank import require

HERE = Path(__file__).resolve().parent
QUALIFICATION_STATUS = 'PASS_SCORING_HISTORY_DERIVATIVE_DEVELOPMENT_ONLY'
POLICY = dict(schema='n4-panel-scoring-admission-v3', scorer='scoring_bank_v3',
    reviewer='review_scoring_bank_v3', qualification='SCORING_HISTORY_CHECK_V3.json',
    required_main=7680, required_modes_panel=1536,
    context_difference='Verified main-only reuse_review; all other context and audio identical',
    evaluator_truth_in_child=False, modeled_scores_confer_application_acceptance=False)


def qualification():
    qb = scoring.qualification(); q = load(qb['path'])
    require(q['status'] == QUALIFICATION_STATUS and q['review_code'] == reviewer.code_bindings()
        and q['scoring_code'] == scoring.code_bindings(), 'Exact V3 scoring/reviewer qualification required')
    scoring.verify_bindings(q)
    tested = load(q['private_receipt']['path']); verify(tested['admission'])
    a = load(tested['admission']['path'])
    require(tested['admission'] == q['private_admission'] and q['all_probe_and_metric_owners_exited'] is True
        and exact_process(a['owner']) is None, 'V3 scoring qualification probe is not closed')
    verify(qb)
    return qb, q


def validate_chain(binding, review, admission, scored, scoring_admission, plan, qb, q):
    """Pure provenance/denominator gate; callers also verify bytes and stopped owners."""
    require(review.get('status') == 'PASS_REVIEWED_MODELED_SCORING_ONLY'
        and review.get('all_metric_inputs_and_report_totals_verified') is True
        and review.get('N4_accepted') is False and type(review.get('integrated_N4_cells')) is int
        and review['integrated_N4_cells'] == 0, 'Passed complete modeled-score review required')
    require(q.get('status') == QUALIFICATION_STATUS
        and admission['qualification'] == scoring_admission['qualification'] == qb
        and admission['code'] == q['review_code'] and scoring_admission['code'] == q['scoring_code'],
        'Changed or unqualified V3 scorer/reviewer')
    required = {'main':7680, 'modes-panel':1536}.get(plan['scope'])
    require(required is not None and type(plan['required']) is int and plan['required'] == required,
        'Full main or modes population required')
    reviewer.validate_terminal(scored, plan)
    require(type(review['reviewed']) is int and type(review['required']) is int
        and review['reviewed'] == review['required'] == required and review['scope'] == plan['scope']
        and scored['report'] == review['report'] and scoring_admission['plan'] == review['plan']
        and scoring_admission['review'] == review['method_review'] and admission['result'] == review['scoring_result']
        and admission['scoring_admission'] == scored['admission'], 'Review/score/plan join differs')
    root = Path(review['scoring_result']['path']).parent
    require(Path(review['admission']['path']) == Path(binding['path']).parent/'ADMISSION.json'
        and Path(review['scoring_result']['path']) == root/'RESULT.json'
        and Path(scored['admission']['path']) == root/'ADMISSION.json'
        and Path(review['report']['path']) == root/'REPORT.json', 'Foreign review/scoring evidence path')
    require(all(Path(b['path']) == root/'cells'/f'{i:05d}.json' for i,b in enumerate(scored['scores'])),
        'Changed full scoring population order or path')


def read_review(path):
    """Read reviewed scores only; no evaluator reference contents or models are loaded."""
    binding = bind(path); review = load(path)
    require(review.get('status') == 'PASS_REVIEWED_MODELED_SCORING_ONLY'
        and review.get('all_metric_inputs_and_report_totals_verified') is True
        and review.get('N4_accepted') is False and review.get('integrated_N4_cells') == 0,
        'Passed complete modeled-score review required')
    for key in ('admission','scoring_result','plan','method_review','report'): verify(review[key])
    admission = load(review['admission']['path'])
    require(exact_process(admission['owner']) is None, 'Exact score reviewer remains active')
    qb, q = qualification()
    scored = load(review['scoring_result']['path']); verify(scored['admission'])
    scoring_admission = load(scored['admission']['path']); plan = load(review['plan']['path'])
    validate_chain(binding, review, admission, scored, scoring_admission, plan, qb, q)
    reviewer.owners_closed(scored['workers'], plan['required'])
    require(exact_process(scoring_admission['owner']) is None, 'Exact scoring driver remains active')
    scoring.verify_bindings(scoring_admission)
    bundle = scoring.admit(Path(scoring_admission['terminal']['path']).parent, Path(review['method_review']['path']))
    require(bundle['terminal_binding'] == scoring_admission['terminal'] and bundle['plan'] == plan
        and bundle['terminal']['plan'] == review['plan']
        and bundle['terminal']['status'] == 'COLLECTED_METHOD_BANK_REQUIRES_REVIEW', 'Method bank source differs')
    for b in scored['scores']: verify(b)
    report = load(review['report']['path'])
    require(fingerprint(report) == review['report_content_sha256']
        and report['required_cells'] == plan['required'], 'Reviewed report content differs')
    # Close the read interval over each admitted parent and both exact owners.
    scoring.verify_bindings(admission); scoring.verify_bindings(scoring_admission)
    for b in (binding, qb, review['plan'], review['scoring_result'], review['method_review'], review['report']): verify(b)
    require(all(exact_process(o) is None for o in (admission['owner'],scoring_admission['owner'])),
        'A scoring or review owner reappeared')
    reviewer.owners_closed(scored['workers'], plan['required'])
    return binding, plan


def validate_contexts(main, modes):
    """Only main reuse provenance may differ; it is admitted separately below."""
    require('reuse_review' not in modes['context'], 'Mode panel must not reuse a main-mode prefix')
    left = deepcopy(main['context']); right = modes['context']
    if 'reuse_review' in left:
        require(isinstance(left['reuse_review'],dict) and set(left['reuse_review']) == {'path','sha256','bytes'},
            'Malformed main reuse provenance')
        del left['reuse_review']
    original.validate_review_pair(dict(main, context=left), modes)
    return left


def validate_review_pair(main, modes):
    common = validate_contexts(main, modes)
    qb = bind(HERE/'INTEGRATED_HISTORY_CHECK_V3.json'); q = load(qb['path'])
    for plan in (main, modes):
        scoring.validate_implementation(plan['context'], q, qb)
        scoring.verify_bindings(plan['context'])
    reused = scoring.admit_reuse(main)
    require(scoring.admit_reuse(modes) is None, 'Unexpected mode-panel prefix')
    require(('reuse_review' in main['context']) == (reused is not None), 'Missing qualified main prefix')
    verify(qb)
    return common
