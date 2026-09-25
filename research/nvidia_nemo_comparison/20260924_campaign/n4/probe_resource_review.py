"""Qualify resource replay against saved samples; no new measurement."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest
from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
from review_resource_evidence import review
import test_resource_review as regression


def run(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local');here=Path(__file__).resolve().parent
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,720);inventory=shared_allowance(local)
        qualification=load(here/'APPLICATION_RESOURCES_CHECK_V1.json')
        require(qualification['status']=='PASS_MODEL_FREE_RESOURCE_COLLECTOR_ONLY','Original collector qualification required')
        verify(qualification['private_receipt']);original=load(qualification['private_receipt']['path'])
        regression.SAVED=original['actual_tree']['result'];verify(regression.SAVED)
        require(exact_process(original['actual_tree']['child']) is None,'Original fixture child still active')
        names=('review_resource_evidence.py','test_resource_review.py','probe_resource_review.py','README_RESOURCE_REVIEW.md',
            'test_application_resources.py','application_resources.py','resources.py','common.py','metric_process.py',
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
            collector_qualification=bind(here/'APPLICATION_RESOURCES_CHECK_V1.json'),original_observation=regression.SAVED,
            ASR_snapshot=active,new_model_or_resource_measurement=False))
        try:
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(regression.ResourceReviewTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==9 and not tests.skipped,'Resource review checks failed')
            reviewed=review(regression.SAVED,require_all_phases=True);freeze(output/'SAVED_RESOURCE_REVIEW.json',reviewed)
            for b in code:verify(b)
            guard(output,local,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_RESOURCE_REVIEW_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                saved_observation_review=bind(output/'SAVED_RESOURCE_REVIEW.json'),new_resource_measurement=False,
                actual_application_spawned=False,model_inference_started=False,controlled_whole_stack_qualified=False,
                target_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 9 resource review checks and saved actual resource-tree replay; no new measurement',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESOURCE_REVIEW_PROBE_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
