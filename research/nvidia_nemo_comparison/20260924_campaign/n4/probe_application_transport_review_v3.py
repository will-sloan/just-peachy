"""Qualify stopped transport review without any new application/process launch."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_slot import observe_owner, validate_supervision
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_application_transport_review_v3 as regression
from paced_panel_plan_v3 import application_qualification

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('review_application_transport_v3.py','test_application_transport_review_v3.py','probe_application_transport_review_v3.py',
     'README_APPLICATION_TRANSPORT_REVIEW_V3.md','delivery_review_fixtures.py')


def code_bindings():
    names = OWN+('common.py','metric_process.py','paced_child_admission.py','paced_slot.py',
        'paced_panel_plan.py','review_scoring_bank.py','scoring_bank.py','asr_full_bank.py','test_paced_child_admission.py')
    code = [bind(HERE/name) for name in names]
    for name in ('PACED_RUNNER_CHECK_V3.json','PRIVATE_PROCESS_CHECK_V3.json','NATIVE_JOURNAL_REVIEW_CHECK_V1.json'):
        q=load(HERE/name);verify(q['private_receipt'])
        code += [bind(HERE/name),*q['code']]
    return list({b['path']:b for b in code}.values())


from probe_application_transport_review import active_d1


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private N4 output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720);inventory=shared_allowance(LOCAL);numerical=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(parents=True);snapshots=[]
        # Dependencies remain bound in-place; snapshot this attempt's new files.
        for name in OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Attempt snapshot changed');snapshots.append(bind(target))
        try:
            code=code_bindings()
            for b in code:verify(b)
            qualification=load(HERE/'PRIVATE_PROCESS_CHECK_V3.json')
            require(qualification['status']=='PASS_PRIVATE_PROCESS_LIFETIME_DEVELOPMENT_ONLY','Native fixture qualification differs')
            original=load(qualification['private_receipt']['path']);regression.SAVED=original['fixture_lifetimes']
            for binding in regression.SAVED:
                verify(binding);require(exact_process(load(binding['path'])['owner']) is None,'Saved native fixture owner remains')
            ab,app,source=application_qualification();regression.SOURCE=source['source_receipt']
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=numerical,native_fixture_receipt=qualification['private_receipt'],application_qualification=ab,
                source_receipt=source['source_receipt'],new_application_or_model_started=False,
                fixture_scope='Fabricated append times, source/owner facts and inert transport bytes; never production admission'))
            regression.OUTPUT=output/'tests';regression.OUTPUT.mkdir()
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.TransportReviewTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==18 and not tests.skipped,'Transport review checks failed')
            for b in code:verify(b)
            guard(output,LOCAL,started,720);after=active_d1()
            require(after['result']['owner']==numerical['result']['owner'] and after['result']['child']==numerical['result']['child']
                and after['run_id']==numerical['run_id'],'Numerical ownership changed during probe; re-observe')
            freeze(output/'RESULT.json',dict(status='PASS_APPLICATION_TRANSPORT_V3_REVIEW_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                saved_lifetimes_reviewed=len(regression.SAVED),saved_classifications=bind(output/'tests/test_saved_actual_native_closure_and_failure_classification/SAVED_CLASSIFICATIONS.json'),
                synthetic_join_review=bind(output/'tests/test_join_preserves_all_acceptance_and_history_limits/SYNTHETIC_REVIEW.json'),
                D1_after=after,new_application_or_model_started=False,actual_panel_reviewed=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 18 V3 transport/delivery/native review tests; seven saved lifetimes; no new application or model',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_TRANSPORT_V3_REVIEW_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
