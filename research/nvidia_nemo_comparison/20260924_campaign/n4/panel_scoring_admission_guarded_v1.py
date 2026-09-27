"""Read closed main V3 and guarded modes scores. README_PANEL_SCORING_GUARDED_V1.md."""
from pathlib import Path

from common import bind, fingerprint, load, verify
from metric_process import exact_process
from reservation_budget_v1 import require
import guarded_execution_v1 as guarded
import panel_scoring_admission_v3 as previous
import review_scoring_bank_v3 as reviewer
from scoring_bank_v3 import verify_bindings

HERE = Path(__file__).resolve().parent
OWN = ('panel_scoring_admission_guarded_v1.py',
       'test_panel_scoring_admission_guarded_v1.py', 'probe_panel_scoring_guarded_v1.py',
       'README_PANEL_SCORING_GUARDED_V1.md')
POLICY = dict(schema='n4-panel-scoring-admission-guarded-v1',
    main='ACCEPTED_MAIN_V3_REVIEW', modes='CLOSED_GUARDED_V1_SCORE_REVIEW',
    required_main=7680, required_modes_panel=1536,
    context_difference='Verified main-only reuse_review; other context and audio identical',
    evaluator_truth_in_child=False, modeled_scores_confer_application_acceptance=False)


def code_bindings():
    """Bind the entire qualified parent reader and guarded family, including tests."""
    import paced_panel_plan_v4 as planner
    values = planner.code_bindings() + guarded.code_bindings()
    values += [bind(HERE/n) for n in OWN]
    values += [bind(HERE/n) for n in ('PACED_PANEL_PLAN_CHECK_V4.json',
        'GUARDED_BANK_CHECK_V1.json', 'MAIN_MODELED_SCORING_ACCEPTANCE_V1.json')]
    unique = {}
    for b in values:
        require(b['path'] not in unique or unique[b['path']] == b, 'Conflicting reader source')
        unique[b['path']] = b
    return [b for _, b in sorted(unique.items())]


def validate_guarded_chain(binding, reviewed, scored, plan):
    """Pure joins after both resource execution envelopes have been checked."""
    r, a = reviewed['result'], reviewed['admission']
    result, sa = scored['result'], scored['admission']
    require(plan.get('scope') == 'modes-panel' and type(plan.get('required')) is int
        and plan['required'] == 1536, 'Complete modes panel required')
    require(r.get('status') == 'PASS_REVIEWED_MODELED_SCORING_ONLY'
        and r.get('all_metric_inputs_and_report_totals_verified') is True
        and r.get('N4_accepted') is False and type(r.get('integrated_N4_cells')) is int
        and r['integrated_N4_cells'] == 0, 'Complete modeled score review required')
    require(all(type(r.get(k)) is int and r[k] == plan['required'] for k in ('required', 'reviewed'))
        and r.get('scope') == plan['scope'], 'Review population differs')
    require(all(type(result.get(k)) is int for k in ('required', 'prediction_completed')),
        'Invalid scoring population type')
    reviewer.validate_terminal(result, plan)
    require(binding == reviewed['terminal'] and r['scoring_result'] == scored['terminal']
        and a['reviewed_terminal'] == scored['terminal']
        and a['plan'] == r['plan'] == sa['plan'] == result['plan']
        and r['method_review'] == sa['review'] and r['report'] == result['report'],
        'Guarded review/score/plan join differs')
    root = Path(scored['terminal']['path']).parent
    require(Path(binding['path']).name == 'RESULT.json'
        and Path(r['admission']['path']) == Path(binding['path']).parent/'ADMISSION.json'
        and Path(scored['terminal']['path']) == root/'RESULT.json'
        and Path(result['admission']['path']) == root/'ADMISSION.json'
        and Path(result['report']['path']) == root/'REPORT.json'
        and Path(result['evaluator']['path']) == root/'EVALUATOR.json', 'Foreign guarded evidence path')
    require(all(Path(b['path']) == root/'cells'/f'{i:05d}.json'
        for i, b in enumerate(result['scores'])), 'Score population order/path differs')
    require(r['execution_plan'] == reviewed['execution_plan']
        and result['execution_plan'] == scored['execution_plan'], 'Review/score execution identity differs')


def validate_score_cell(value, row, method_binding, execution_binding):
    """No reference contents: verify ordered scored cells and their method lineage."""
    require(value.get('execution_plan') == execution_binding
        and value.get('method_result') == method_binding
        and all(value.get(k) == row[k] for k in ('cell_id', 'job_id', 'composition'))
        and value.get('mode') == row['contract']['mode'], 'Score cell lineage differs')
    require(value.get('score', {}).get('metric_status') == 'SCORED'
        and type(value.get('integrated_N4_cells')) is int and value['integrated_N4_cells'] == 0,
        'Missing metric or invented application acceptance')


def read_guarded_review(path):
    """Read-only modes admission; does not load evaluator truth or run inference."""
    path = Path(path).resolve(strict=True)
    require(path.name == 'RESULT.json', 'Canonical guarded review result required')
    binding = bind(path)
    reviewed = guarded.validate_execution(path.parent, kind='score-review')
    r = reviewed['result']
    # Do not follow arbitrary score paths until the stopped review envelope verifies.
    verify(r['scoring_result'])
    scored = guarded.validate_execution(Path(r['scoring_result']['path']).parent, kind='scoring')
    result, a = scored['result'], scored['admission']
    verify(a['plan']); plan = load(a['plan']['path'])
    validate_guarded_chain(binding, reviewed, scored, plan)
    reviewer.owners_closed(result['workers'], plan['required'])
    for b in (a['terminal'], a['review'], result['report'], result['evaluator']): verify(b)
    bundle = guarded.admit_method(Path(a['terminal']['path']).parent, Path(a['review']['path']))
    require(bundle['terminal_binding'] == a['terminal'] and bundle['review'] == a['review']
        and bundle['plan'] == plan and bundle['terminal']['plan'] == a['plan'],
        'Guarded method parent differs')
    for i, b in enumerate(result['scores']):
        verify(b)
        validate_score_cell(load(b['path']), plan['rows'][i], bundle['terminal']['cells'][i],
            scored['execution_plan'])
    report = load(result['report']['path'])
    require(fingerprint(report) == r['report_content_sha256']
        and type(report.get('required_cells')) is int and report['required_cells'] == 1536,
        'Reviewed report digest or population differs')
    # EVALUATOR is only hashed. No evaluator reference contents enter this reader.
    for b in (binding, reviewed['terminal'], scored['terminal'], result['report'], result['evaluator'],
              a['terminal'], a['review'], a['plan'], reviewed['execution_plan'], scored['execution_plan']): verify(b)
    for v in (reviewed, scored):
        verify_bindings(v['admission'])
        require(exact_process(v['admission']['owner']) is None, 'Scorer/reviewer owner reappeared')
    reviewer.owners_closed(result['workers'], plan['required'])
    return binding, plan


def read_review(path, *, expected_scope):
    """Explicit role prevents inferring authority from a user-controlled status field."""
    require(expected_scope in ('main', 'modes-panel'), 'Explicit main or modes scope required')
    if expected_scope == 'modes-panel':
        return read_guarded_review(path)
    ab = bind(HERE/'MAIN_MODELED_SCORING_ACCEPTANCE_V1.json'); accepted = load(ab['path'])
    require(accepted.get('status') == 'ACCEPTED_REVIEWED_MAIN_MODELED_SCORING_ONLY'
        and accepted.get('main_modeled_scoring_accepted') is True
        and accepted.get('N4_accepted') is False and accepted['review'] == bind(path),
        'Exact accepted main review required')
    binding, plan = previous.read_review(Path(path))
    require(plan['scope'] == 'main' and plan['required'] == 7680, 'Main scope differs')
    verify(ab); verify(binding)
    return binding, plan


def read_pair(main_review, modes_review):
    """Return only original plans/bindings; never manufacture a V4 runnable plan."""
    mb, main = read_review(main_review, expected_scope='main')
    xb, modes = read_review(modes_review, expected_scope='modes-panel')
    previous.validate_review_pair(main, modes)
    verify(mb); verify(xb)
    return {'main': mb, 'modes-panel': xb}, main, modes
