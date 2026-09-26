"""Guarded independent restart review checks. README_RESTART_REVIEW.md."""
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
import review_restart_run as subject
import test_restart_transport as transport
import test_restart_run_review as population

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private review probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,720)
        check();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in subject.OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Source snapshot differs');snapshots.append(bind(target))
        try:
            code=subject.code_bindings();q=load(HERE/'PRIVATE_PROCESS_CHECK_V3.json')
            require(q['status']=='PASS_PRIVATE_PROCESS_LIFETIME_DEVELOPMENT_ONLY','Native fixture qualification differs')
            verify(q['private_receipt']);native=load(q['private_receipt']['path']);saved=native['fixture_lifetimes']
            require(len(saved)==7,'Seven saved native lifetime cases required')
            for b in saved:
                verify(b);require(exact_process(load(b['path'])['owner']) is None,'Saved native owner still active')
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,native_fixture_receipt=q['private_receipt'],saved_lifetimes=saved,
                actual_application_or_model_started=False))
            tests=output/'tests';tests.mkdir();transport.OUTPUT=tests;transport.SAVED=saved;population.OUTPUT=tests
            stream=io.StringIO();suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(transport.RestartTransportTests),
                unittest.defaultTestLoader.loadTestsFromTestCase(population.RestartPopulationTests)])
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun==29 and not result.skipped,'Independent restart review checks failed')
            for b in code+snapshots+saved:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            check()
            freeze(output/'RESULT.json',dict(status='PASS_RESTART_REVIEW_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=result.testsRun,D1_after=after,
                code_records=len(code),saved_native_lifetimes_reviewed=7,synthetic_transport_and_population=True,
                mocked_pair_leaf_review_and_production_plan_admission=True,actual_private_process_created=False,
                actual_application_or_model_started=False,actual_complete_production_run_reviewed=False,
                actual_restart_qualified=False,viewport_rows_reviewed=False,resource_samples_reviewed=False,
                integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 29 independent restart review checks; seven saved native lifetimes; no new process or model run',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_REVIEW_PROBE_PRESERVED',owner=identity(process),error_type=type(exc).__name__,
                source_snapshots=snapshots,admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
