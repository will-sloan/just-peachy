"""Guarded evaluator-only semantic regression suite. README_SEMANTIC_FAMILY_V7.md."""
import argparse
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, pin
from paced_panel_plan_v3 import application_qualification
from paced_panel_plan_guarded_v2 import admit_plan
from reservation_budget_v1 import require
import guarded_execution_v1 as resource
import semantic_family_v7 as family
from review_application_semantics_v7 import load_reference_context
import test_application_semantics_v7 as semantics
import test_semantic_panel_v7 as names
import test_application_content_panel_v7 as content
import test_semantic_family_v7 as cross


def suite(cls, output):
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    path = output/(cls.__name__+'.txt'); path.write_text(stream.getvalue(), encoding='utf-8')
    require(result.wasSuccessful() and not result.skipped, 'Semantic family check failed: '+cls.__name__)
    return dict(suite=cls.__name__, tests=result.testsRun, log=bind(path))


def isolated_imports(output, context, archive_cases):
    root = output/'import-path'; root.mkdir()
    module = bind(family.HERE.parent/'n3/gui_a1.py')
    helper = bind(family.HERE.parent/'n2/io_utils.py')
    source = load(context['source_receipt']['path'])
    freeze(root/'INPUTS.json', dict(prototype=source['prototype'], archive_module=module, io_helper=helper,
        bound_modules=[module, helper, bind(family.HERE/'application_closure.py')],
        archive_cases=[dict(archive=c['archive'], frames=c['audio']['frames']) for c in archive_cases]))
    results = []
    for label in ('negative', 'positive'):
        environment = dict(os.environ); environment.pop('PYTHONPATH', None)
        if label == 'positive': environment['PYTHONPATH'] = str(family.HERE.parents[3])
        argv = [sys.executable, '-B', str(family.HERE/'application_import_path_v1.py'),
                '--input', str(root/'INPUTS.json'), '--output', str(root/(label+'.json'))]
        if label == 'negative': argv.append('--expect-missing')
        completed = subprocess.run(argv, cwd=family.HERE, env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        (root/(label+'.stdout.txt')).write_bytes(completed.stdout)
        (root/(label+'.stderr.txt')).write_bytes(completed.stderr)
        require(completed.returncode == 0, 'Isolated import path regression failed: '+label)
        receipt = bind(root/(label+'.json')); value = load(receipt['path'])
        require(value['pythonpath'] == environment.get('PYTHONPATH') and value['application_started'] is False,
                'Isolated import environment differs')
        require(value['archive_receipts_checked'] == (0 if label == 'negative' else 9), 'Archive regression denominator differs')
        results.append(receipt)
    return dict(inputs=bind(root/'INPUTS.json'), results=results, tests_passed=2,
                repaired_environment=dict(PYTHONPATH=str(family.HERE.parents[3])), application_started=False)


def run(output, plan_path):
    pin(); sys.path.insert(0, str(family.HERE.parents[3])); code = family.code_bindings(); pb = bind(plan_path)
    g = family.start_output(output, pb, 'probe', code,
        dict(actual_application_or_model_started=False, evaluator_only=True,
             fixture_scope='Synthetic V7 process/source/widget facts; saved evaluator references; actual qualified plan reconstruction'))
    snapshots = []; checks = []; guards = []; last = [0.]
    def checkpoint():
        if time.monotonic()-last[0] >= 1:
            g.fast_check(); last[0] = time.monotonic()
    try:
        with g:
            guards.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            admitted, plan = admit_plan(plan_path); require(admitted == pb, 'Actual plan changed')
            ab, app, context = application_qualification()
            closure = load(family.HERE/'APPLICATION_CLOSURE_CHECK_V2.json'); verify(closure['private_receipt'])
            previous = load(closure['private_receipt']['path']); verify(previous['admission'])
            old = load(previous['admission']['path']); require(exact_process(old['owner']) is None, 'Historical helper active')
            case = old['cases'][0]
            for name in ('finalization', 'consumer', 'archive'): verify(case[name])
            import_checks = isolated_imports(output, context, old['cases'])
            wq = load(family.HERE/'NATIVE_WIDGET_REVIEW_CHECK_V1.json')
            require(wq['application_source'] == context['source_receipt'], 'Native/widget source differs')
            for b in wq['native_pure_modules']: verify(b)
            nq = load(family.HERE/'NAMING_REFERENCE_CHECK_V1.json')
            cellq = load(family.HERE/'APPLICATION_FAMILY_CHECK_V7.json'); verify(cellq['private_receipt'])
            joined = load(cellq['private_receipt']['path'])['synthetic_join_review']; verify(joined)
            for name in family.OWN:
                path = output/'source'/name; path.parent.mkdir(exist_ok=True)
                path.write_bytes((family.HERE/name).read_bytes()); snapshots.append(bind(path))
            freeze(output/'FIXTURE_INPUTS.json', dict(application_qualification=ab, application_context=app['application_context'],
                application_source=context['source_receipt'], native_pure_modules=wq['native_pure_modules'],
                historical_closure_admission=previous['admission'], prior_reference_inputs=nq['reference_inputs'],
                synthetic_cell=joined, actual_plan=pb, actual_plan_required=plan['required']))
            references = load_reference_context(checkpoint=checkpoint)
            freeze(output/'REFERENCE_INPUTS.json', dict(inputs=references['inputs'], population=references['population'],
                NEVER_PASS_TO_RUNTIME=True, models_loaded=0, audio_loaded=False))
            semantics.CONTEXT.update(output=output/'semantics', case=case, source=context['source_receipt'],
                catalog=context['catalog'], galleries=context['gallery_preparation'], runtimes=context['runtimes'],
                references=references, old_reference_context=nq['reference_inputs']['application_context'])
            semantics.CONTEXT['output'].mkdir(); checks.append(suite(semantics.SemanticTests, output)); checkpoint()
            positive = semantics.CONTEXT['output']/'test_full_semantic_chain_and_reference_join_stay_development_only'
            observed = bind(positive/'SYNTHETIC_SEMANTIC_REVIEW.json'); score = bind(positive/'SYNTHETIC_NAME_SCORE.json')
            value = load(observed['path']); body = value['observed']['content']
            payloads = [b for b in body['cell']['transport']['evidence'] if Path(b['path']).name == 'INPUT.json']
            require(len(payloads) == 1, 'One semantic input required'); verify(payloads[0])
            freeze(output/'SYNTHETIC_CONTENT_REVIEW.json', body); cb = bind(output/'SYNTHETIC_CONTENT_REVIEW.json')
            for label, module in (('names', names), ('content', content)):
                root = output/label; root.mkdir()
                module.CONTEXT.update(output=root, checkpoint=checkpoint, synthetic_observed=observed,
                    synthetic_score=score, references=references, payload=payloads[0], synthetic_content=cb)
                module.prior.CONTEXT.update(output=root, synthetic_join=joined)
                checkpoint(); checks.append(suite(module.SemanticPanelTests if label == 'names' else module.ContentPanelTests, output))
            cross.CONTEXT.update(output=output/'cross', content=cb, payload=payloads[0]); cross.CONTEXT['output'].mkdir()
            checkpoint(); checks.append(suite(cross.FamilyTests, output))
            require(sum(r['tests'] for r in checks) == 66, 'Complete semantic regression denominator differs')
            for b in code+snapshots+wq['native_pure_modules']+references['evidence']+[ab, app['application_context'], observed, score, cb, pb]: verify(b)
            require('torch' not in sys.modules, 'Model runtime imported by development probe')
            guards.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            freeze(output/'RESULT.json', dict(status='PASS_V7_SEMANTIC_FAMILY_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=g.admission, execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=guards,
                source_snapshots=snapshots, checks=checks, tests_passed=66, code_records=len(code),
                reference_inputs=bind(output/'REFERENCE_INPUTS.json'), synthetic_semantic_review=observed,
                synthetic_name_score=score, synthetic_content_review=cb,
                synthetic_compact_names=bind(output/'names/SYNTHETIC_COMPACT_NAME_SCORE.json'),
                synthetic_compact_content=bind(output/'content/SYNTHETIC_COMPACT_CONTENT.json'),
                semantic_output_budget=bind(output/'names/OUTPUT_BUDGET_FIXTURE.json'),
                content_output_budget=bind(output/'cross/test_maximum_content_panel_fits_with_registry_and_failure_reserve/CONTENT_BUDGET.json'),
                actual_plan=pb, actual_plan_required=plan['required'], positive_production_plan_gate_executed=True,
                isolated_import_path_repair_verified=True, import_path_checks=import_checks,
                actual_readers_composed=True, development_population_sizes=[40,240], semantic_calculations_unchanged=True,
                raw_delivery_summary_preserved_in_bound_envelope=True, exact_utf8_and_platform_newline_output_bound_tested=True,
                evaluator_truth_loaded=True, reference_never_passed_to_runtime=True,
                actual_panel_reviewed=False, actual_application_or_model_started=False, actual_continuity_test=False,
                naming_accuracy_qualified=False, source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
                integrated_N4_cells=0, N4_accepted=False, N5_complete=False))
    except BaseException as exc:
        freeze(output/'FAILED.json', dict(status='FAILED_V7_SEMANTIC_FAMILY_PROBE_PRESERVED', admission=g.admission,
            execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=guards,
            error_type=type(exc).__name__, reason=str(exc)[:2000], checks_completed=checks,
            source_snapshots=snapshots, N4_accepted=False, N5_complete=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args(); run(args.output, args.plan)
