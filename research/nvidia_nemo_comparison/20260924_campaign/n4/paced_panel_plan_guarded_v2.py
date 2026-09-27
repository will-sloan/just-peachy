"""Actual selected plan preparation; README_PACED_PANEL_PLAN_GUARDED_V2.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from reservation_budget_v1 import require
import guarded_execution_v1 as resource
import guarded_metadata_probe_v1 as metadata
import paced_panel_plan_guarded_v1 as adapter
import paced_panel_plan as original

HERE = Path(__file__).resolve().parent
LOCAL = adapter.previous.LOCAL
SCHEMA = 'n4-paced-panel-plan-guarded-v2'
ENVELOPE = 'n4-guarded-plan-preparation-v1'
QUALIFICATION = 'PACED_PANEL_PLAN_GUARDED_V2_CHECK.json'
STATUS = 'PASS_ACTUAL_GUARDED_PLAN_PREPARATION_ONLY'
CAP, SECONDS, TESTS = 16*1024**2, 2400, 12
OWN = ('paced_panel_plan_guarded_v2.py', 'test_paced_panel_plan_guarded_v2.py',
       'README_PACED_PANEL_PLAN_GUARDED_V2.md')
APPLICATION_POLICY = adapter.previous.APPLICATION_POLICY
PREPARATION_POLICY = dict(schema=ENVELOPE, complete_review_pair=True,
    actual_component_assets=True, saved_panel_hashes=True,
    complete_resource_census=True, application_execution_authorized=False)


def parents():
    """Require the actual reader and adapter checks, never a fixture-only claim."""
    rb = bind(HERE/'PANEL_SCORING_GUARDED_CHECK_V2.json'); rq = load(rb['path'])
    pb = bind(HERE/'PANEL_PLANNER_GUARDED_CHECK_V2.json'); pq = load(pb['path'])
    require(rq['status'] == 'PASS_REAL_CLOSED_SCORE_PAIR_READER_ONLY'
        and pq['status'] == 'PASS_GUARDED_PANEL_ADAPTER_DIAGNOSTIC_ONLY'
        and pq['planner_code'] == adapter.code_bindings()
        and pq['real_reviews'] == rq['real_review_pair']['reviews']
        and pq['fixture_payloads'] == 1240 and pq['child_payloads_equal_to_V4'] is True,
        'Actual reviewed-pair adapter qualification required')
    for q, role, count, base in ((rq, 'reader', 11, adapter.scores.code_bindings()),
                                (pq, 'planner', 10, adapter.code_bindings())):
        require(q['code'] == metadata.code_bindings(base, role)
            and q['tests_passed'] == count and q['manifest_tests_passed'] == 7
            and q['exact_probe_owner_exited'] is True and q['exact_supervisor_owner_exited'] is True
            and q['N4_accepted'] is False and q['N5_complete'] is False,
            'Changed diagnostic code, scope or test census')
        r = load(q['private_result']['path']); a = load(r['admission']['path'])
        require(a['code'] == q['code'] and a['owner'] == q['probe_owner']
            and r['status'] == q['status'] and r['tests_passed'] == count
            and r['manifest_tests_passed'] == 7
            and exact_process(q['probe_owner']) is None
            and exact_process(q['supervisor_owner']) is None, 'Diagnostic owner or result differs')
        for b in q['code'] + q['source_snapshots'] + q['guard_checks'] + [
            q['private_result'], r['admission'], r['metadata_execution_plan'],
            q['tests'], q['manifest_tests']]: verify(b)
    return rb, pb, rq, pq


def code_bindings():
    rb, pb, rq, pq = parents()
    values = rq['code'] + pq['code'] + [rb, pb] + [bind(HERE/n) for n in OWN]
    unique = {}
    for b in values:
        require(b['path'] not in unique or unique[b['path']] == b, 'Conflicting producer dependency')
        unique[b['path']] = b
    code = [b for _, b in sorted(unique.items())]
    metadata.validate_manifest(code, resource.code_bindings(), bind(HERE/OWN[0]))
    for b in code: verify(b)
    return code


def component_assets(scored, admissions):
    """Join actual component asset manifests; reject mixed roots or source parents."""
    require(set(admissions) == {'ASR', 'D1'}, 'Both actual asset component admissions required')
    assets = {}; root = None
    for kind in ('ASR', 'D1'):
        a = admissions[kind]
        require(a['component_contract']['source_receipt'] == scored['source_receipt'],
                'Asset component/source parent differs')
        candidate = a['models_root']
        require(isinstance(candidate, str) and Path(candidate).is_absolute(), 'Absolute actual model root required')
        if root is None: root = candidate
        require(candidate == root, 'Component model root differs')
        require(bool(a['component_contract']['assets']), 'Empty component asset manifest')
        for b in a['component_contract']['assets']:
            require(set(b) == {'path', 'sha256', 'bytes'} and Path(b['path']).is_absolute()
                and type(b['bytes']) is int and b['bytes'] > 0, 'Invalid model asset binding')
            require(b['path'] not in assets or assets[b['path']] == b, 'Conflicting actual assets')
            assets[b['path']] = deepcopy(b)
    return root, [b for _, b in sorted(assets.items())]


def build_plan(selection, reviews, jobs, panel, anchors, catalog, context):
    require(context.get('preparation_policy') == PREPARATION_POLICY, 'Explicit production preparation policy required')
    plan = adapter.build_plan(selection, reviews, jobs, panel, anchors, catalog, context)
    plan['schema'] = SCHEMA
    return plan


def execution_payload(plan, index):
    require(plan.get('schema') == SCHEMA and plan.get('context', {}).get('preparation_policy') == PREPARATION_POLICY,
            'Wrong actual guarded application plan')
    return adapter.execution_payload(dict(plan, schema=adapter.SCHEMA), index)


def reconstruct(selection_binding, reviews, preparation_binding, code, *, boundary=lambda: None):
    """Rebuild from complete original reviews, actual assets and qualified source."""
    rb, pb, rq, pq = parents()
    require(reviews == pq['real_reviews'], 'Exact qualified review pair required')
    actual, main, modes = adapter.scores.read_pair(Path(reviews['main']['path']), Path(reviews['modes-panel']['path']))
    require(actual == reviews, 'Review binding differs')
    boundary(); verify(selection_binding); selected = load(selection_binding['path'])
    original.validate_selection(selected, reviews)
    require(preparation_binding == pq['preparation'], 'Exact frozen preparation required')
    verify(preparation_binding); prepared = load(preparation_binding['path'])
    outputs = {Path(b['path']).name: b for b in prepared['outputs']}
    manifest, panel, anchors = [outputs[n] for n in ('AUDIO_ONLY_480.json', 'PACED_AUDIO_ONLY_24.json', 'REGRESSION_AUDIO_ONLY_8.json')]
    for b in (manifest, panel, anchors): verify(b)
    ab, app, source = adapter.previous.application_qualification(); scored = main['context']
    admissions = {}
    for kind in ('ASR', 'D1'):
        verify(scored['reviews'][kind]); review = load(scored['reviews'][kind]['path'])
        verify(review['admission']); admissions[kind] = load(review['admission']['path'])
        terminal_binding = review['final_result'] if kind == 'ASR' else review['terminal']
        verify(terminal_binding); terminal = load(terminal_binding['path'])
        require(terminal['admission'] == review['admission'] and exact_process(terminal['owner']) is None,
                'Component asset producer remains active or terminal differs')
    root, assets = component_assets(scored, admissions)
    require(Path(root).is_dir(), 'Actual model root missing')
    for b in assets: boundary(); verify(b)
    common = dict(manifest=manifest, panel=panel, regression=anchors, models_root=root,
        assets=assets, planner_qualification=pb, code=code)
    context = adapter.application_context(scored, source, app['application_context'], ab, common)
    context['preparation_policy'] = deepcopy(PREPARATION_POLICY)
    context['reader_qualification'] = rb
    jobs, panel_jobs, anchor_jobs = [load(b['path'])['jobs'] for b in (manifest, panel, anchors)]
    for job in panel_jobs:
        boundary(); require(bind(job['audio_path'])['sha256'] == job['audio_sha256'], 'Saved panel waveform differs')
    plan = build_plan(selected, reviews, jobs, panel_jobs, anchor_jobs, load(source['catalog']['path']), context)
    for i in range(plan['required']):
        payload = execution_payload(plan, i)
        require(len(payload) == 13 and payload['source_execution_authorized'] is False, 'Inference firewall differs')
    for b in code + [rb, pb, ab, selection_binding, preparation_binding, *reviews.values()]: verify(b)
    boundary(); return plan


def envelope(plan, code):
    return dict(schema=ENVELOPE, kind='plan-preparation', original_plan=plan, code=code,
        entry_script=bind(HERE/OWN[0]), resource_code=resource.code_bindings(),
        resource_qualification=resource.qualification(), allocation_bytes=CAP, maximum_seconds=SECONDS,
        preparation_policy=deepcopy(PREPARATION_POLICY), application_execution_authorized=False)


def validate_provenance(result, admission, execution, ab, eb, pb, code, expected_envelope, *, owner_closed):
    """Pure gate for exact joins, budgets, test census and non-execution scope."""
    require(result.get('status') == STATUS and result.get('admission') == ab
        and result.get('execution_plan') == admission.get('execution_plan') == eb
        and result.get('plan') == pb and admission.get('code') == code
        and execution == expected_envelope and owner_closed is True,
        'Preparation terminal, producer, envelope or exact closure differs')
    require(admission.get('allocation_bytes') == CAP and admission.get('maximum_seconds') == SECONDS
        and result.get('tests_passed') == TESTS and type(result.get('tests_passed')) is int
        and type(result.get('tests_skipped')) is int and result.get('tests_skipped') == 0
        and result.get('model_assets_verified') is True,
        'Preparation limits or test/asset evidence differs')
    require(all(result.get(k) is False for k in ('actual_application_or_model_started', 'source_execution_authorized',
        'N4_accepted', 'N5_complete')) and type(result.get('integrated_N4_cells')) is int
        and result.get('integrated_N4_cells') == 0,
        'Plan preparation cannot grant application acceptance')


def admit_plan(path):
    """Downstream admission requires published closed proof AND reconstruction."""
    path = Path(path).resolve(strict=True); require(path.is_relative_to(LOCAL/'n4') and path.name == 'PLAN.json', 'Foreign plan')
    run = path.parent; pb = bind(path); plan = load(path); rb = bind(run/'RESULT.json'); result = load(rb['path'])
    ab = bind(run/'ADMISSION.json'); a = load(ab['path']); eb = bind(run/'EXECUTION_PLAN.json'); code = code_bindings()
    q = load(HERE/QUALIFICATION)
    require(q['status'] == STATUS and q['code'] == code and q['private_result'] == rb
        and q['plan'] == pb and q['exact_preparer_owner_exited'] is True
        and q['N4_accepted'] is False, 'Exact production preparation qualification required')
    validate_provenance(result, a, load(eb['path']), ab, eb, pb, code, envelope(a['original_plan'], code),
        owner_closed=exact_process(a['owner']) is None)
    require(len(result['guard_checks']) == 2, 'Initial and final complete resource proofs required')
    for b, name in zip(result['guard_checks'], ('GUARD_INITIAL.json', 'GUARD_FINAL.json')):
        verify(b); v = load(b['path'])['projection']
        require(Path(b['path']) == run/name and v['own_admission'] == ab
            and v['production_scope_checked'] is True and v['own_allocation_counted_once'] is True
            and v['other_allocation_count'] == 0, 'Plan producer resource proof differs')
    verify(result['tests']); log = Path(result['tests']['path']).read_text()
    require(f'Ran {TESTS} tests' in log and log.strip().endswith('OK') and 'skipped' not in log, 'Preparation tests incomplete')
    rebuilt = reconstruct(a['selection'], a['reviews'], a['preparation'], code)
    require(rebuilt == plan and result['required'] == plan['required']
        and result['candidates'] == plan['candidates'], 'Actual plan reconstruction differs')
    for b in (rb, ab, eb, pb): verify(b)
    return pb, plan


def prepare(args):
    process = pin(); code = code_bindings(); _, _, _, pq = parents()
    original_plan = bind(args.plan); require(original_plan == pq['original_modes_plan'], 'Original modes plan differs')
    reviews = {'main': bind(args.main_review), 'modes-panel': bind(args.modes_review)}
    require(reviews == pq['real_reviews'], 'Exact accepted review pair required')
    selection = bind(args.selection); original.validate_selection(load(selection['path']), reviews)
    output = args.output.resolve(); require(not output.exists() and output.is_relative_to(LOCAL/'n4') and output != LOCAL/'n4', 'Fresh private preparation required')
    require(Path(sys.argv[0]).resolve() == HERE/OWN[0], 'Different preparer entry')
    freeze(output/'EXECUTION_PLAN.json', envelope(original_plan, code)); eb = bind(output/'EXECUTION_PLAN.json')
    freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, plan=original_plan,
        original_plan=original_plan, execution_plan=eb, selection=selection, reviews=reviews,
        preparation=pq['preparation'], allocation_bytes=CAP, maximum_seconds=SECONDS,
        cpu_affinity=process.cpu_affinity(), models_loaded=0, integrated_N4_cells=0))
    checks = []
    g = resource.Guard(LOCAL, output, code, load(LOCAL/'n4/integrated-main-v3/RESULT.json')['plan'], SECONDS, production=True)
    try:
        with g:
            checks.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            import test_paced_panel_plan_guarded_v2 as tests
            with (output/'tests.txt').open('x', encoding='utf-8') as stream:
                tested = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            require(tested.wasSuccessful() and tested.testsRun == TESTS and not tested.skipped, 'Production preparation regression failed')
            for n in OWN:
                dest = output/'source'/n; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes((HERE/n).read_bytes())
            plan = reconstruct(selection, reviews, pq['preparation'], code, boundary=g.fast_check)
            require('torch' not in sys.modules, 'Plan preparation loaded a model runtime')
            freeze(output/'PLAN.json', plan)
            checks.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            freeze(output/'RESULT.json', dict(status=STATUS, utc=datetime.now(timezone.utc).isoformat(),
                admission=g.admission, execution_plan=eb, plan=bind(output/'PLAN.json'), required=plan['required'],
                candidates=plan['candidates'], tests=bind(output/'tests.txt'), tests_passed=tested.testsRun,
                tests_skipped=0, model_assets_verified=True, source_snapshots=[bind(output/'source'/n) for n in OWN],
                guard_checks=checks, actual_application_or_model_started=False, source_execution_authorized=False,
                integrated_N4_cells=0, N4_accepted=False, N5_complete=False))
    except BaseException as exc:
        freeze(output/'FAILED.json', dict(status='FAILED_PLAN_PREPARATION_PRESERVED', admission=g.admission,
            execution_plan=eb, reason=str(exc), error_type=type(exc).__name__, guard_checks=checks,
            actual_application_or_model_started=False, N4_accepted=False, N5_complete=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'main-review', 'modes-review', 'selection', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    prepare(parser.parse_args())
