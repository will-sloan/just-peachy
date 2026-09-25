"""Reviewed-score admission and fixed actual-application panels. README_PACED_PANEL_PLAN.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
import time

from common import audio_only, bind, fingerprint, freeze, load, verify
from integrated_bank_plan import exact_jobs, exact_panel
from metric_process import exact_process, identity, pin
from mode_galleries import backend_contract
from review_scoring_bank import (code_bindings as reviewer_code, guard, owners_closed, require,
                                 shared_allowance, validate_terminal)
from scoring_bank import admit, verify_bindings, writer_lock

HERE = Path(__file__).resolve().parent
MAIN_MODE = 'open_with_names'
COMPOSITIONS = {'_'.join(c) for c in product(('A0', 'A1', 'A2', 'A3'), ('D0', 'D1'), ('E0', 'E1'))}
BASELINE = 'A0_D0_E0'
ANCHORS = {'N2_'+scene+'_'+tap for scene in ('S45_08_07', 'S45_03_03', 'S45_06_07', 'S45_12_15') for tap in ('O0', 'O1')}
OBJECTIVES = {'baseline', 'smallest_useful', 'diarization_identity', 'text_tradeoff', 'higher_memory', 'independent_architecture'}
EXECUTION_POLICY = dict(cpu_affinity=[4], math_threads=1, gpu=False, source_paced=True,
    recipe='balanced', mode=MAIN_MODE, adaptation=False, text_assistance=False, private_desktop_required=True,
    reset_between_cells=True, fresh_application_process_per_cell=True, cells_concurrent=1,
    controlled_resource_measurements=True, cold_scope='fresh process and model load; OS file cache is not flushed')


def composition_catalog(catalog):
    result = {}
    for row in catalog['backends']:
        if not row['implemented']: continue
        contract = backend_contract(catalog, row['key'], MAIN_MODE)
        composition = '_'.join(contract[k] for k in ('variant', 'diarization', 'encoder'))
        require(composition not in result, 'Duplicate composition catalog route')
        result[composition] = contract
    require(set(result) == COMPOSITIONS and result[BASELINE]['backend_key'] == 'baseline', 'Exact 16-composition catalog required')
    return result


def validate_selection(selection, reviews):
    require(set(selection) == {'schema', 'status', 'reviews', 'selected', 'excluded', 'limitations'}, 'Selection schema differs')
    require(selection['schema'] == 'n4-paced-selection-v1' and selection['status'] == 'PROPOSED_PACED_EVALUATION_ONLY'
            and selection['reviews'] == reviews, 'Selection must bind these exact passed score reviews')
    rows = selection['selected']; selected = []
    require(isinstance(rows, list) and 1 <= len(rows) <= 6, 'Baseline plus at most five alternatives')
    for row in rows:
        require(set(row) == {'composition', 'objective', 'rationale', 'limitations'}, 'Selected row schema differs')
        require(row['composition'] in COMPOSITIONS and row['composition'] not in selected, 'Duplicate or foreign candidate')
        require(row['objective'] in OBJECTIVES and (row['objective'] == 'baseline') == (row['composition'] == BASELINE), 'Candidate role differs')
        require(all(isinstance(row[k], str) and 1 <= len(row[k].strip()) <= 4000 for k in ('rationale', 'limitations')), 'Explicit bounded rationale/limitations required')
        selected.append(row['composition'])
    require(selected[0] == BASELINE, 'Exact baseline must lead the paired panel')
    excluded = selection['excluded']
    require(isinstance(excluded, list) and len(excluded) == len(COMPOSITIONS)-len(selected), 'Every omitted composition needs a reason')
    found = set()
    for row in excluded:
        require(set(row) == {'composition', 'reason'} and row['composition'] in COMPOSITIONS-set(selected)
                and row['composition'] not in found and isinstance(row['reason'], str)
                and 1 <= len(row['reason'].strip()) <= 4000, 'Invalid exclusion rationale')
        found.add(row['composition'])
    require(found | set(selected) == COMPOSITIONS, 'Selection drops a composition silently')
    require(isinstance(selection['limitations'], str) and 1 <= len(selection['limitations'].strip()) <= 8000, 'Selection limitations required')
    return selected


def validate_review_pair(main, modes):
    require(main['scope'] == 'main' and main['required'] == 7680 and modes['scope'] == 'modes-panel'
            and modes['required'] == 1536, 'Both full reviewed comparison populations required')
    require(main['context'] == modes['context'] and main['jobs'] == modes['jobs'], 'Main/mode source or component parents differ')


def build_plan(selection, reviews, jobs, panel, regression, catalog, context):
    """Pure planning only. Does not authorize a source or manufacture acceptance."""
    selected = validate_selection(selection, reviews); by_job = exact_jobs(jobs)
    panel_ids = exact_panel(panel, by_job)
    require(len(regression) == 8 and {r['job_id'] for r in regression} == ANCHORS, 'Frozen eight timing regressions required')
    for job in regression:
        audio_only(job)
        require(job == by_job[job['job_id']] and job['job_id'] in panel_ids, 'Regression is not the identical admitted panel file')
    contracts = composition_catalog(catalog); rows = []
    # Block by file and repetition, then alternate candidates. Every cell starts
    # a fresh process; no previous-scene state or candidate-specific scene order.
    for kind, repeat, population in [('panel', 0, panel), ('timing_repeat', 1, regression), ('timing_repeat', 2, regression)]:
        for job in population:
            for composition in selected:
                contract = contracts[composition]
                key = dict(job=job, contract=contract, execution=EXECUTION_POLICY, kind=kind, repeat=repeat,
                           context_sha256=fingerprint(context))
                rows.append(dict(cell_id=f'{kind}_{repeat}_{job["job_id"]}_{composition}', composition=composition,
                    job=deepcopy(job), contract=deepcopy(contract), kind=kind, repeat=repeat,
                    cache_key=fingerprint(key), collection_credit=0))
    required = len(selected)*40
    require(len(rows) == required and len({r['cell_id'] for r in rows}) == required, 'Paired panel census differs')
    return dict(schema='n4-paced-panel-plan-v1', status='PREPARED_PANELS_AND_REPEATS_ONLY',
        reviews=deepcopy(reviews), selection=deepcopy(selection), context=deepcopy(context), rows=rows,
        required=required, candidates=selected, panel_cases_per_candidate=24, additional_repeats_per_candidate=16,
        occurrences_per_regression_per_candidate=3, execution=deepcopy(EXECUTION_POLICY),
        source_seconds_per_candidate=sum(j['frames']/16000 for j in panel)+2*sum(j['frames']/16000 for j in regression),
        mode_scope='Open conversation plus names; other modes have separate modeled and later release checks',
        continuity_required_per_release_candidate_seconds=1200, continuity_included=False,
        model_slot_admitted=False, inference_started=False, integrated_N4_cells=0, N4_accepted=False)


def execution_payload(plan, index):
    """Allowlist for the future child; references/reports/selection never copied."""
    require(plan['schema'] == 'n4-paced-panel-plan-v1' and plan['status'] == 'PREPARED_PANELS_AND_REPEATS_ONLY'
            and plan['execution'] == EXECUTION_POLICY and type(index) is int and 0 <= index < len(plan['rows']), 'Invalid panel execution request')
    row = plan['rows'][index]; context = plan['context']; audio_only(row['job'])
    key = dict(job=row['job'], contract=row['contract'], execution=plan['execution'], kind=row['kind'], repeat=row['repeat'],
               context_sha256=fingerprint(context))
    require(row['cache_key'] == fingerprint(key), 'Changed panel row or source context')
    require(set(context['runtimes']) == {'n2_runtime.json', 'n3_runtime.json'}, 'Both exact application runtimes required')
    return dict(schema='n4-paced-cell-input-v1', cell_id=row['cell_id'], job=deepcopy(row['job']),
        contract=deepcopy(row['contract']), execution=deepcopy(plan['execution']),
        source_receipt=deepcopy(context['source_receipt']), catalog=deepcopy(context['catalog']),
        runtimes=[deepcopy(context['runtimes'][name]) for name in sorted(context['runtimes'])], gallery_preparation=deepcopy(context['gallery_preparation']),
        models_root=context['models_root'], assets=deepcopy(context['assets']),
        source_execution_authorized=False,
        remaining_gate='Exact supervised exclusive-slot owner, frozen launcher and live resource/deadline admission required')


def read_review(path):
    """Recheck passed immutable full-score receipt; do not load evaluator truth."""
    binding = bind(path); review = load(path)
    require(review.get('status') == 'PASS_REVIEWED_MODELED_SCORING_ONLY'
            and review.get('all_metric_inputs_and_report_totals_verified') is True and review.get('N4_accepted') is False
            and review.get('integrated_N4_cells') == 0, 'Passed complete modeled-score review required')
    for key in ('admission', 'scoring_result', 'plan', 'method_review', 'report'): verify(review[key])
    admission = load(review['admission']['path'])
    require(exact_process(admission['owner']) is None, 'Exact score reviewer is still active')
    qualifier = bind(HERE/'SCORING_REVIEW_IMPLEMENTATION_V1.json')
    require(admission['qualification'] == qualifier and admission['code'] == reviewer_code(), 'Unqualified or changed score reviewer')
    for b in admission['code']: verify(b)
    require(load(qualifier['path'])['status'] == 'PASS_SCORING_REVIEW_DEVELOPMENT_ONLY', 'Review implementation qualification failed')
    scored = load(review['scoring_result']['path']); verify(scored['admission']); scoring_admission = load(scored['admission']['path'])
    plan = load(review['plan']['path']); validate_terminal(scored, plan); owners_closed(scored['workers'], plan['required'])
    require(exact_process(scoring_admission['owner']) is None, 'Exact scoring driver is still active')
    require(review['reviewed'] == review['required'] == plan['required'] and review['scope'] == plan['scope']
            and scored['report'] == review['report'] and scoring_admission['plan'] == review['plan']
            and scoring_admission['review'] == review['method_review'] and admission['result'] == review['scoring_result']
            and admission['scoring_admission'] == scored['admission'], 'Review/score/plan join differs')
    verify_bindings(scoring_admission)
    bundle = admit(Path(scoring_admission['terminal']['path']).parent, Path(review['method_review']['path']))
    require(bundle['terminal_binding'] == scoring_admission['terminal'] and bundle['plan'] == plan, 'Method bank source differs')
    for b in scored['scores']: verify(b)
    report = load(review['report']['path'])
    require(fingerprint(report) == review['report_content_sha256'] and report['required_cells'] == plan['required'], 'Reviewed report content differs')
    verify(binding)
    return binding, plan


def code_bindings():
    return [bind(HERE/n) for n in ('paced_panel_plan.py', 'test_paced_panel_plan.py', 'probe_paced_panel_plan.py',
            'README_PACED_PANEL_PLAN.md', 'integrated_bank_plan.py', 'mode_galleries.py', 'common.py')] + reviewer_code()


def prepare(args):
    process = pin(); started = time.monotonic()
    prep_binding = load(HERE/'PREPARATION_V2_CHECK.json')['preparation']; verify(prep_binding); prep = load(prep_binding['path'])
    local = Path(prep_binding['path']).parents[2]
    require(not args.output.exists() and args.output.resolve().is_relative_to((local/'n4').resolve()), 'Fresh private N4 plan output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(args.output, local, started, 720)
        qualification = load(HERE/'PACED_PANEL_PLAN_CHECK_V1.json'); code = code_bindings()
        require(qualification['status'] == 'PASS_PACED_PANEL_PLAN_DEVELOPMENT_ONLY' and qualification['code'] == code, 'Planner code not qualified')
        inventory = shared_allowance(local)
        mb, main = read_review(args.main_review); xb, modes = read_review(args.modes_review); validate_review_pair(main, modes)
        reviews = {'main': mb, 'modes-panel': xb}; selection_binding = bind(args.selection); selection = load(args.selection)
        validate_selection(selection, reviews)
        outputs = {Path(b['path']).name: b for b in prep['outputs']}
        manifest, panel, regression = [outputs[n] for n in ('AUDIO_ONLY_480.json', 'PACED_AUDIO_ONLY_24.json', 'REGRESSION_AUDIO_ONLY_8.json')]
        for b in (manifest, panel, regression): verify(b)
        ctx = main['context']
        require(ctx['manifest'] == manifest and ctx['panel'] == panel, 'Frozen panel/preparation differs')
        app_binding = bind(HERE/'PACED_APPLICATION_CELL_CHECK_V1.json'); app = load(app_binding['path'])
        require(app['status'] == 'PASS_PRIVATE_TK_AND_APPLICATION_PRESTART_ONLY' and app['source_receipt'] == ctx['source_receipt']
                and app['gallery_preparation'] == ctx['gallery_preparation'], 'Application prestart/source qualification differs')
        for b in app['code']+[app['private_receipt']]: verify(b)
        private_app = load(app['private_receipt']['path']); verify(private_app['admission']); app_admission = load(private_app['admission']['path'])
        require({Path(b['path']).name: b for b in app_admission['runtimes']} == ctx['runtimes']
                and app_admission['catalog'] == ctx['catalog'], 'Application runtime/catalog differs from scored banks')
        assets = {}; models_root = None
        for kind in ('ASR', 'D1'):
            r = load(ctx['reviews'][kind]['path']); verify(r['admission']); a = load(r['admission']['path'])
            require(a['component_contract']['source_receipt'] == ctx['source_receipt'], 'Asset/source component differs')
            if models_root is None: models_root = a['models_root']
            require(models_root == a['models_root'], 'Component model roots differ')
            for b in a['component_contract']['assets']:
                require(b['path'] not in assets or assets[b['path']] == b, 'Conflicting model/runtime asset')
                assets[b['path']] = b
        require(bool(assets), 'Actual bound assets required')
        for b in assets.values(): verify(b)
        jobs = load(manifest['path'])['jobs']; panel_jobs = load(panel['path'])['jobs']; regression_jobs = load(regression['path'])['jobs']
        for job in panel_jobs:
            require(bind(job['audio_path'])['sha256'] == job['audio_sha256'], 'Saved panel waveform changed')
        context = dict(source_receipt=ctx['source_receipt'], catalog=ctx['catalog'], runtimes=ctx['runtimes'],
            gallery_preparation=ctx['gallery_preparation'], manifest=manifest, panel=panel, regression=regression,
            models_root=models_root, assets=list(assets.values()), application_qualification=app_binding,
            planner_qualification=bind(HERE/'PACED_PANEL_PLAN_CHECK_V1.json'), code=code)
        plan = build_plan(selection, reviews, jobs, panel_jobs, regression_jobs, load(ctx['catalog']['path']), context)
        # This is coordinator metadata. A future worker receives only the allowlist above.
        for b in code+[mb, xb, selection_binding, prep_binding]: verify(b)
        guard(args.output, local, started, 720)
        freeze(args.output/'ADMISSION.json', dict(owner=identity(process), code=code, selection=selection_binding, reviews=reviews,
            preparation=prep_binding, inventory=inventory, inference_started=False, model_slot_admitted=False))
        freeze(args.output/'PLAN.json', plan)
        freeze(args.output/'RESULT.json', dict(status='PREPARED_PANELS_AND_REPEATS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
            admission=bind(args.output/'ADMISSION.json'), plan=bind(args.output/'PLAN.json'), required=plan['required'],
            candidates=len(plan['candidates']), source_execution_authorized=False, continuity_included=False, integrated_N4_cells=0))
        print('Prepared '+str(plan['required'])+' source-paced panel/repeat cells; no launch', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('main-review', 'modes-review', 'selection', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    prepare(parser.parse_args())
