"""Guarded failure-aware collection qualification; README_APPLICATION_OUTCOMES_V1.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import unittest

from common import bind, freeze, load, verify
from metric_process import pin
from reservation_budget_v1 import require
import application_family_v9 as family
import guarded_execution_v1 as resource
from paced_panel_plan_guarded_v2 import admit_plan
from paced_application_runner_v9 import qualified_interpreter
import test_application_outcomes_v1 as tests


def run(output, plan_path):
    pin(); code = family.code_bindings(); pb = bind(plan_path)
    g = family.start_output(output,pb,'probe',code,16*1024**2,2400,
        dict(actual_application_or_model_started=False,fixture_scope='Preserved failed V8 cell and rejection mutations'))
    guards = []; snapshots = []
    try:
        with g:
            guards.append(resource.save_check(g,'GUARD_INITIAL.json'))
            admitted, plan = admit_plan(plan_path)
            require(admitted == pb and plan['required'] == 240,'Actual plan differs')
            qualified_interpreter()
            tests.CONTEXT['failed_cell'] = family.LOCAL/'n4/paced-application-v8/cells/panel_0_N2_S45_01_01_O0_A0_D1_E0'
            for name in family.OWN:
                path = output/'source'/name; path.parent.mkdir(exist_ok=True)
                path.write_bytes((family.HERE/name).read_bytes()); snapshots.append(bind(path))
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.OutcomeTests))
            log = output/'tests.txt'; log.write_text(stream.getvalue(),encoding='utf-8')
            require(result.testsRun == 16 and result.wasSuccessful() and not result.skipped,'Outcome regression failed')
            freeze(output/'ACTUAL_FAILURE_REVIEW.json',tests.CONTEXT['actual_review'])
            for b in code+snapshots+[pb]: verify(b)
            guards.append(resource.save_check(g,'GUARD_FINAL.json')); g.fast_check()
            freeze(output/'RESULT.json',dict(status='PASS_V9_APPLICATION_FAMILY_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(), admission=g.admission,
                execution_plan=bind(output/'EXECUTION_PLAN.json'),guard_checks=guards,
                tests_passed=16,tests=bind(log),source_snapshots=snapshots,code_records=len(code),
                inherited_qualification=bind(family.HERE/'APPLICATION_FAMILY_CHECK_V8.json'),
                inherited_97_tests_rerun=False,actual_failure_review=bind(output/'ACTUAL_FAILURE_REVIEW.json'),
                positive_production_plan_gate_executed=True,actual_plan_required=240,
                actual_application_or_model_started=False,integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
    except BaseException as exc:
        freeze(output/'FAILED.json',dict(status='FAILED_OUTCOMES_PROBE_PRESERVED',admission=g.admission,
            execution_plan=bind(output/'EXECUTION_PLAN.json'),guard_checks=guards,source_snapshots=snapshots,
            error=type(exc).__name__+': '+str(exc),N4_accepted=False,N5_complete=False))
        raise


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.output,a.plan)
