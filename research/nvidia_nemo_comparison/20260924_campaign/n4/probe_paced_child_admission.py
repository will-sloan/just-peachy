"""Model-free child admission checks. README_PACED_CHILD_ADMISSION.md."""
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
from test_paced_child_admission import ChildAdmissionTests


def run(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()),'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,720);inventory=shared_allowance(local)
        here=Path(__file__).resolve().parent
        names=('paced_child_admission.py','test_paced_child_admission.py','probe_paced_child_admission.py','README_PACED_CHILD_ADMISSION.md',
            'paced_slot.py','paced_panel_plan.py','mode_galleries.py','common.py','metric_process.py','scoring_bank.py','review_scoring_bank.py','asr_full_bank.py')
        code=[bind(here/name) for name in names]
        active=load(local/'n4/asr-full-bank-v1/RESULT.json')
        require(active['status']=='RUNNING' and exact_process(active['child']) is not None and
            exact_process(active['child']).cpu_affinity()==[4],'Re-observe current numerical owner')
        (output/'source').mkdir(parents=True);snapshots=[]
        for entry in code:
            snapshot=output/'source'/Path(entry['path']).name
            with snapshot.open('xb') as stream:stream.write(Path(entry['path']).read_bytes())
            require(bind(snapshot)['sha256']==entry['sha256'],'Source snapshot mismatch');snapshots.append(bind(snapshot))
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
            ASR_snapshot=active,actual_application_spawned=False,model_inference_started=False))
        try:
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ChildAdmissionTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==9 and not tests.skipped,'Child admission checks failed')
            for entry in code:verify(entry)
            guard(output,local,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_CHILD_ADMISSION_REJECTION_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                actual_CPU14_helper_rejected=True,foreign_lease_writer_rejected=True,production_permit_created=False,
                successful_supervised_child_admission=False,model_source_priming_executed=False,
                application_spawned=False,model_inference_started=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 9 child admission checks; no child, model or source started',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_CHILD_ADMISSION_PROBE_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
