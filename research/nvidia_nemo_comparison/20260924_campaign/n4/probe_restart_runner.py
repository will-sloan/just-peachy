"""Guarded model-free restart coordinator qualification. README_RESTART_RUNNER.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import restart_application_runner as subject
import test_restart_runner as tests

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private coordinator probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,720)
        check();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in subject.OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Attempt snapshot differs');snapshots.append(bind(target))
        try:
            code,child,executable,script=subject.qualified_manifests();qualifications=[]
            for name in subject.QUALIFICATIONS:
                qb=bind(HERE/name);q=load(qb['path']);verify(q['private_receipt'])
                r=load(q['private_receipt']['path']);verify(r['admission']);a=load(r['admission']['path'])
                require(exact_process(a['owner']) is None,'Prerequisite probe is active');qualifications.append(qb)
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,child_code=child,executable=executable,
                child_script=script,qualifications=qualifications,source_snapshots=snapshots,inventory=inventory,D1_snapshot=active,
                actual_private_process_created=False,actual_application_or_model_started=False))
            tests.OUTPUT=output/'tests';tests.OUTPUT.mkdir();stream=io.StringIO()
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartRunnerTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun==24 and not result.skipped,'Restart coordinator checks failed')
            for b in code+snapshots+[executable,script]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 ownership changed')
            check()
            freeze(output/'RESULT.json',dict(status='PASS_RESTART_RUNNER_WIRING_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=result.testsRun,D1_after=after,
                parent_code_records=len(code),child_code_records=len(child),mocked_private_process_slot_lease_and_leaf_reviews=True,
                mocked_plan_admission_and_supervision=True,actual_private_process_created=False,actual_GUI_or_model_started=False,
                production_plan_admitted=False,successful_supervised_application_admission=False,
                actual_restart_qualified=False,independent_complete_transport_reviewed=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 24 restart coordinator checks; no actual child, application or model launched',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_RUNNER_PROBE_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
