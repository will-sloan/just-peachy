"""Bounded guarded runner/reviewer checks; README_APPLICATION_FAMILY_V5.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from common import bind, freeze, load, verify
from metric_process import exact_process, pin
from paced_panel_plan_v3 import application_qualification
from paced_panel_plan_guarded_v2 import admit_plan
from reservation_budget_v1 import require
import guarded_execution_v1 as resource
import application_family_v5 as family
from paced_application_runner_v5 import qualified_interpreter
import test_paced_child_admission_v3 as gate_tests
import test_paced_application_runner_v5 as runner_tests
import test_application_transport_review_v5 as transport_tests
import test_application_cell_review_v5 as cell_tests
import test_application_panel_review_v5 as panel_tests
import test_application_family_v5 as family_tests
import test_paced_slot_guarded_v1 as slot_tests


def suite(cls, output):
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    path = output/(cls.__module__+'.txt'); path.write_text(stream.getvalue(), encoding='utf-8')
    require(result.wasSuccessful() and not result.skipped, 'Family regression failed: '+cls.__module__)
    return dict(suite=cls.__module__, tests=result.testsRun, log=bind(path))


def run(output, plan_path):
    pin(); sys.path.insert(0, str(family.HERE.parents[3])); code = family.code_bindings(); pb = bind(plan_path)
    g = family.start_output(output, pb, 'probe', code, 16*1024**2, 2400,
        dict(actual_application_or_model_started=False, fixture_scope='Mocked child/slot lifecycles; synthetic recorded facts and saved native lifetimes; actual plan reconstruction'))
    checks = []; guards = []; snapshots = []
    try:
        with g:
            guards.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            admitted, plan = admit_plan(plan_path); require(admitted == pb, 'Actual qualified plan changed')
            exe = qualified_interpreter(); ab, app, source = application_qualification()
            prototype = Path(load(source['source_receipt']['path'])['prototype'])
            native = load(family.HERE/'PRIVATE_PROCESS_CHECK_V3.json'); verify(native['private_receipt'])
            saved = load(native['private_receipt']['path'])['fixture_lifetimes']
            for b in saved:
                verify(b); require(exact_process(load(b['path'])['owner']) is None, 'Saved fixture owner remains active')
            closure = load(family.HERE/'APPLICATION_CLOSURE_CHECK_V2.json'); verify(closure['private_receipt'])
            prior = load(closure['private_receipt']['path']); verify(prior['admission']); old = load(prior['admission']['path'])
            require(exact_process(old['owner']) is None, 'Historical closure helper remains active'); case = old['cases'][0]
            for name in ('finalization', 'consumer', 'archive'): verify(case[name])
            for name in family.OWN:
                path = output/'source'/name; path.parent.mkdir(exist_ok=True); path.write_bytes((family.HERE/name).read_bytes()); snapshots.append(bind(path))
            freeze(output/'FIXTURE_INPUTS.json', dict(application_qualification=ab, application_context=app['application_context'],
                source_receipt=source['source_receipt'], saved_native_lifetimes=saved, historical_closure_admission=prior['admission'],
                actual_plan=pb, actual_plan_required=plan['required'], complete_dependency_count=len(code)))
            fixtures = output/'temporary-fixtures'; fixtures.mkdir()
            runner_root = output/'runner'; runner_root.mkdir()
            runner_tests.CONTEXT.update(output=runner_root, prototype=prototype, checkpoint=g.fast_check)
            runner_tests.delivery_tests.CONTEXT.update(output=runner_root, prototype=prototype, checkpoint=g.fast_check)
            runner_tests.delivery_tests.source_tests.CONTEXT.update(output=runner_root, prototype=prototype, checkpoint=g.fast_check)
            transport_tests.SAVED = saved; transport_tests.SOURCE = source['source_receipt']
            transport_tests.OUTPUT = output/'transport'; transport_tests.OUTPUT.mkdir()
            cell_tests.CONTEXT.update(output=output/'cell', case=case, source=source['source_receipt'],
                catalog=source['catalog'], galleries=source['gallery_preparation'], runtimes=source['runtimes'])
            cell_tests.CONTEXT['output'].mkdir()
            family_tests.CONTEXT.update(code=code, output=output/'family'); family_tests.CONTEXT['output'].mkdir()
            with patch.object(tempfile, 'tempdir', str(fixtures)):
                for cls in (gate_tests.ChildAdmissionTests, runner_tests.RunnerTests,
                            transport_tests.TransportReviewTests, cell_tests.CellReviewTests):
                    g.fast_check(); checks.append(suite(cls, output))
                joined = bind(output/'cell/test_all_real_readers_compose_with_synthetic_facts/SYNTHETIC_COMPLETE_JOIN_REVIEW.json')
                panel_tests.CONTEXT.update(output=output/'panel', synthetic_join=joined); panel_tests.CONTEXT['output'].mkdir()
                for cls in (panel_tests.PanelReviewTests, family_tests.FamilyTests, slot_tests.AllocationSlotTests):
                    g.fast_check(); checks.append(suite(cls, output))
            require(sum(r['tests'] for r in checks) == 84, 'Complete family test denominator differs')
            for b in code+snapshots+[exe, ab, pb]: verify(b)
            require('torch' not in sys.modules, 'Model runtime imported by development check')
            guards.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            freeze(output/'RESULT.json', dict(status='PASS_V5_APPLICATION_FAMILY_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=g.admission, execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=guards,
                checks=checks, tests_passed=84, source_snapshots=snapshots, code_records=len(code),
                synthetic_join_review=joined, saved_lifetimes_reviewed=len(saved), actual_plan=pb,
                expanded_dependency_manifest_tested=512, maximum_permit_bytes=256*1024, lease_seconds=5,
                positive_production_plan_gate_executed=True, actual_plan_required=plan['required'],
                mocked_coordinator_and_child_lifecycle=True, actual_application_or_model_started=False,
                actual_saved_audio_executed=False, successful_supervised_application_admission=False,
                actual_panel_reviewed=False, semantic_content_and_resource_acceptance=False,
                restart_family_rebound=False, integrated_N4_cells=0, N4_accepted=False, N5_complete=False))
    except BaseException as exc:
        freeze(output/'FAILED.json', dict(status='FAILED_APPLICATION_FAMILY_V5_PROBE_PRESERVED', admission=g.admission,
            execution_plan=bind(output/'EXECUTION_PLAN.json'), error_type=type(exc).__name__, reason=str(exc),
            checks_completed=checks, guard_checks=guards, source_snapshots=snapshots,
            actual_application_or_model_started=False, N4_accepted=False, N5_complete=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--plan', type=Path, required=True)
    args = p.parse_args(); run(args.output, args.plan)
