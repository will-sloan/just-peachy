"""Qualify raw viewport review using saved evidence. README_VIEWPORT_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest
from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_viewport_review as regression


def run(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local');here=Path(__file__).resolve().parent
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,720);inventory=shared_allowance(local)
        qualification=load(here/'VIEWPORT_LEDGER_CHECK_V2.json')
        require(qualification['status']=='PASS_BOUNDED_PRIVATE_VIEWPORT_LEDGER_ONLY','Original ledger qualification required')
        verify(qualification['private_receipt']);original=load(qualification['private_receipt']['path'])
        verify(original['admission']);owner=load(original['admission']['path'])['owner']
        require(exact_process(owner) is None,'Original ledger helper remains active')
        verify(original['checks']);checks=load(original['checks']['path'])
        require(len(checks['saved'])==160,'Full saved viewport set required')
        names=('review_viewport_evidence.py','test_viewport_review.py','probe_viewport_review.py','README_VIEWPORT_REVIEW.md',
            'viewport_ledger_v2.py','test_viewport_ledger_v2.py','widget_visibility.py','common.py','metric_process.py',
            'review_scoring_bank.py','scoring_bank.py','asr_full_bank.py')
        code=[bind(here/name) for name in names]
        for b in qualification['code']:verify(b)
        active=load(local/'n4/asr-full-bank-v1/RESULT.json')
        require(active['status']=='RUNNING' and exact_process(active['child']) is not None and
            exact_process(active['child']).cpu_affinity()==[4],'Re-observe numerical owner')
        (output/'source').mkdir(parents=True);snapshots=[]
        for b in code:
            path=output/'source'/Path(b['path']).name
            with path.open('xb') as stream:stream.write(Path(b['path']).read_bytes())
            require(bind(path)['sha256']==b['sha256'],'Source snapshot differs');snapshots.append(bind(path))
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
            ledger_qualification=bind(here/'VIEWPORT_LEDGER_CHECK_V2.json'),saved_checks=original['checks'],
            ASR_snapshot=active,new_model_source_or_GUI_execution=False))
        regression.CONTEXT.update(output=output,saved=checks['saved'],large=checks['large_history'])
        try:
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(regression.ViewportReviewTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==10 and not tests.skipped,'Viewport review checks failed')
            freeze(output/'SAVED_REVIEWS.json',dict(saved=regression.CONTEXT['saved_reviews'],large=regression.CONTEXT['large_review']))
            for b in code:verify(b)
            guard(output,local,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_VIEWPORT_REVIEW_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                saved_reviews=bind(output/'SAVED_REVIEWS.json'),saved_actual_viewport_histories=160,synthetic_large_history_spans=8192,
                actual_application_spawned=False,model_inference_started=False,actual_source_execution=False,
                source_to_widget_latency_qualified=False,actual_continuity_test=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 10 viewport review tests; 160 saved actual histories and an 8192-span synthetic history reconstructed',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_VIEWPORT_REVIEW_PROBE_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
