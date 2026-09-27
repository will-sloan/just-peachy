"""Guarded restart development and actual-plan probe; README_RESTART_FAMILY_V3.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from common import bind, freeze, load, verify
from reservation_budget_v1 import require
from paced_panel_plan_v4 import application_qualification
from probe_restart_plan import actual_anchors
from probe_restart_family_v2 import suite
import guarded_execution_v1 as resource
import restart_family_v3 as family
import restart_application_plan_v3 as planner
import restart_application_runner_v3 as runner
import test_paced_panel_plan_v3 as panel_fixture
import test_restart_plan_v2 as plan_tests
import test_restart_runner_v2 as runner_tests
import test_restart_run_review_v2 as stopped_tests
import test_restart_content_run_v2 as content_tests
import test_restart_family_v2 as family_tests
import test_restart_guarded_v3 as guarded_tests


def run(output, plan_path):
    output = Path(output).resolve(); pb = bind(plan_path)
    code, child, exe, script = runner.qualified_manifests()
    g = family.start_output(output, pb, 'probe', code, dict(child_code=child, executable=exe, child_script=script))
    boundaries = []; checks = []; snapshots = []
    try:
        with g:
            boundaries.append(resource.save_check(g, 'GUARD_INITIAL.json')); checkpoint = g.fast_check
            for name in family.OWN:
                path = output/'source'/name; path.parent.mkdir(exist_ok=True)
                path.write_bytes((family.HERE/name).read_bytes()); snapshots.append(bind(path))
            admitted, panel = planner.panels.admit_plan(plan_path)
            require(admitted == pb and panel['required'] == 240, 'Actual full qualified panel required')
            lifecycle, _ = planner.lifecycle_qualification()
            value = planner.build_plan(pb, panel, lifecycle)
            require(value['required'] == 12 and value['required_sessions'] == 24, 'Complete paired restart population required')
            for i in range(value['required']):
                payload = planner.execution_payload(value, i)
                runner.control(payload); require(len(payload) == 13, 'Changed child input firewall')
            freeze(output/'RECONSTRUCTED_RESTART_PLAN.json', value)
            ab, app, context = application_qualification(); anchors = actual_anchors()
            asset_metadata = panel['context']['assets']; models_root = panel['context']['models_root']
            freeze(output/'FIXTURE_INPUTS.json', dict(application_qualification=ab,
                application_context=app['application_context'], source_receipt=context['source_receipt'],
                actual_anchors=anchors, lifecycle_qualification=lifecycle, actual_panel=pb,
                model_assets_verified_by_actual_panel_admission=True, model_runtime_loaded=False))
            panel_fixture.CONTEXT.update(source=context,source_binding=app['application_context'],app_binding=ab)
            plan_tests.CONTEXT.update(qualification=lifecycle,actual_jobs=anchors['jobs'],assets=asset_metadata,models_root=models_root)
            for module,name in ((plan_tests,'plans'),(runner_tests,'runner'),(stopped_tests,'stopped')):
                module.OUTPUT=output/'tests'/name;module.OUTPUT.mkdir(parents=True)
            # This fixture is never a production qualification and cannot pass family.qualification.
            freeze(output/'QUALIFICATION_FIXTURE.json',dict(synthetic=True,production_qualification=False))
            stopped_tests.CONTEXT['qualification_fixture']=bind(output/'QUALIFICATION_FIXTURE.json')
            content_tests.CONTEXT.update(context,output=output/'tests/content');content_tests.CONTEXT['output'].mkdir()
            family_tests.CONTEXT.update(output=output/'tests/family');family_tests.CONTEXT['output'].mkdir()
            for cls in (plan_tests.RestartPlanTests,runner_tests.RestartRunnerTests,stopped_tests.RestartPopulationTests,
                        content_tests.ContentCellTests,content_tests.ContentPopulationTests,family_tests.FamilyTests):
                checkpoint();checks.append(suite(cls,output))
            guarded_tests.ACTUAL.update(panel_binding=pb, panel=panel, lifecycle=lifecycle)
            checks.append(suite(guarded_tests.GuardedRestartTests, output))
            require(checks[-1]['tests'] == 20, 'Guarded restart test census changed')
            for b in code+child+snapshots+[exe, script, pb, ab, app['application_context']]: verify(b)
            require('torch' not in sys.modules, 'Development probe loaded a model runtime')
            boundaries.append(resource.save_check(g, 'GUARD_FINAL.json')); checkpoint()
            freeze(output/'RESULT.json', dict(status='PASS_V3_GUARDED_RESTART_FAMILY_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(), admission=g.admission,
                execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=boundaries,
                checks=checks, tests_passed=sum(r['tests'] for r in checks), tests_skipped=0,
                source_snapshots=snapshots, code_records=len(code), child_code_records=len(child),
                actual_panel=pb, reconstructed_plan=bind(output/'RECONSTRUCTED_RESTART_PLAN.json'),
                positive_production_plan_gate_executed=True, actual_restart_payloads_checked=12,
                actual_application_or_model_started=False, actual_production_restart_run_reviewed=False,
                actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False, N5_complete=False))
            print('PASS: guarded restart development plus actual plan; no application launch', flush=True)
    except BaseException as exc:
        freeze(output/'FAILED.json',dict(status='FAILED_GUARDED_RESTART_PROBE_PRESERVED',
            admission=g.admission, error_type=type(exc).__name__, error=str(exc)[:2000],
            checks_completed=checks, guard_checks=boundaries, N4_accepted=False))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); run(args.output,args.plan)
