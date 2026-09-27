"""Guarded V10 setup diagnostics and open-path repair. README_APPLICATION_SETUP_V1.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import unittest

from common import bind, freeze, load, verify
from metric_process import pin
from reservation_budget_v1 import require
import application_family_v10 as family
import guarded_execution_v1 as resource
from paced_panel_plan_guarded_v2 import admit_plan
from paced_application_runner_v10 import qualified_interpreter
import test_application_outcomes_v1 as outcomes
import test_application_setup_v1 as setup
import test_paced_child_admission_v7 as child


def run(output, plan_path):
    pin(); code=family.code_bindings(); pb=bind(plan_path)
    g=family.start_output(output,pb,'probe',code,16*1024**2,2400,
        dict(actual_application_or_model_started=False,fixture_scope='Concurrent Windows open/rename and unchanged refusal gates'))
    guards=[]; snapshots=[]
    try:
        with g:
            guards.append(resource.save_check(g,'GUARD_INITIAL.json'))
            admitted,plan=admit_plan(plan_path)
            require(admitted==pb and plan['required']==240,'Actual production plan differs')
            qualified_interpreter()
            outcomes.CONTEXT['failed_cell']=family.LOCAL/'n4/paced-application-v8/cells/panel_0_N2_S45_01_01_O0_A0_D1_E0'
            setup.CONTEXT['fixture_root']=output
            for name in family.OWN:
                path=output/'source'/name; path.parent.mkdir(exist_ok=True)
                path.write_bytes((family.HERE/name).read_bytes()); snapshots.append(bind(path))
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(t)
                for t in (child.ChildAdmissionTests,setup.SetupTests,outcomes.OutcomeTests))
            stream=io.StringIO(); result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            log=output/'tests.txt';log.write_text(stream.getvalue(),encoding='utf-8')
            require(result.testsRun==45 and result.wasSuccessful() and not result.skipped,'Setup qualification tests failed')
            freeze(output/'CONCURRENT_OPEN.json',setup.CONTEXT['concurrent_open'])
            freeze(output/'ACTUAL_FAILURE_REVIEW.json',outcomes.CONTEXT['actual_review'])
            for b in code+snapshots+[pb]:verify(b)
            guards.append(resource.save_check(g,'GUARD_FINAL.json'));g.fast_check()
            freeze(output/'RESULT.json',dict(status='PASS_V10_APPLICATION_FAMILY_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=g.admission,execution_plan=bind(output/'EXECUTION_PLAN.json'),
                guard_checks=guards,tests_passed=45,tests=bind(log),source_snapshots=snapshots,code_records=len(code),
                inherited_qualification=bind(family.HERE/'APPLICATION_FAMILY_CHECK_V9.json'),
                actual_failure_review=bind(output/'ACTUAL_FAILURE_REVIEW.json'),concurrent_open=bind(output/'CONCURRENT_OPEN.json'),
                positive_production_plan_gate_executed=True,actual_plan_required=240,
                actual_application_or_model_started=False,integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
    except BaseException as exc:
        freeze(output/'FAILED.json',dict(status='FAILED_SETUP_PROBE_PRESERVED',admission=g.admission,
            execution_plan=bind(output/'EXECUTION_PLAN.json'),guard_checks=guards,source_snapshots=snapshots,
            error=type(exc).__name__+': '+str(exc),N4_accepted=False,N5_complete=False))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.output,a.plan)
