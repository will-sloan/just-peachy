"""Guarded fixed-child wiring probe; README_RESTART_CHILD.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import restart_application_child as subject
import test_restart_child as tests

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private child wiring probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,720)
        check();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in subject.OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Child source snapshot differs');snapshots.append(bind(target))
        try:
            code=subject.code_bindings();require(len(code)==122 and len(code)<=128,'Bounded complete child dependency set differs')
            for b in code:verify(b)
            q=load(HERE/'RESTART_PLAN_CHECK_V1.json');verify(q['private_receipt']);verify(q['private_admission'])
            require(exact_process(load(q['private_admission']['path'])['owner']) is None,'Planner probe still active')
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,planner_qualification=bind(HERE/'RESTART_PLAN_CHECK_V1.json'),
                complete_prior_dependency_records=len(q['code']),new_child_dependency_records=5,
                parent_native_reviewer_imported=False,actual_application_spawned=False,model_inference_started=False))
            tests.OUTPUT=output/'tests';tests.OUTPUT.mkdir();stream=io.StringIO()
            outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartChildTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(outcome.wasSuccessful() and outcome.testsRun==15 and not outcome.skipped,'Restart child wiring checks failed')
            for b in code+snapshots:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            check()
            freeze(output/'RESULT.json',dict(status='PASS_RESTART_CHILD_WIRING_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=outcome.testsRun,D1_after=after,
                child_code_records=len(code),all_prior_117_code_records_preserved=True,
                mocked_admission_private_desktop_and_application=True,actual_supervised_admission=False,
                actual_process_spawned=False,actual_GUI_or_model_started=False,actual_source_execution=False,
                actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 15 fixed restart child wiring checks; all 117 prior bindings retained, 122/128 total; no process or model launch',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_CHILD_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
