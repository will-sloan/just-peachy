"""Guarded runner wiring checks. README_PACED_APPLICATION_RUNNER.md."""
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
from paced_application_runner import code_bindings,qualified_interpreter
from test_paced_application_runner import RunnerTests


def run(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private probe output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,720);inventory=shared_allowance(local);code=code_bindings();executable=qualified_interpreter()
        require(len(code)<=128,'Child code binding count exceeded')
        active=load(local/'n4/asr-full-bank-v1/RESULT.json')
        require(active['status']=='RUNNING' and exact_process(active['child']) is not None and
            exact_process(active['child']).cpu_affinity()==[4],'Re-observe numerical owner before development probe')
        (output/'source').mkdir(parents=True);snapshots=[]
        for b in code:
            path=output/'source'/Path(b['path']).name
            with path.open('xb') as stream:stream.write(Path(b['path']).read_bytes())
            require(bind(path)['sha256']==b['sha256'],'Snapshot changed');snapshots.append(bind(path))
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,executable=executable,source_snapshots=snapshots,
            inventory=inventory,ASR_snapshot=active,actual_application_spawned=False,model_inference_started=False))
        try:
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RunnerTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==11 and not tests.skipped,'Runner wiring regression failed')
            for b in code:verify(b)
            guard(output,local,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_PACED_RUNNER_WIRING_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                actual_atomic_lease_writes_with_synthetic_permit=True,mocked_coordinator_and_child_lifecycle=True,
                production_plan_admitted=False,successful_supervised_application_admission=False,
                actual_application_spawned=False,model_inference_started=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 11 model-free runner wiring checks; no actual application/model/source launch',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_PACED_RUNNER_PROBE_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
