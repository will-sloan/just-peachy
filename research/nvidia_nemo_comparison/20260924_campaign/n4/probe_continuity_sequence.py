"""Qualify whole-session continuity input preparation. README_CONTINUITY_SEQUENCE.md."""
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
import continuity_sequence as sequence
import test_continuity_sequence as regression


def run(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,720);inventory=shared_allowance(local);code=sequence.code_bindings()
        preparation,bindings,docs=sequence.inputs()
        active=load(local/'n4/asr-full-bank-v1/RESULT.json')
        require(active['status']=='RUNNING' and exact_process(active['child']) is not None and
            exact_process(active['child']).cpu_affinity()==[4],'Re-observe numerical owner')
        (output/'source').mkdir(parents=True);snapshots=[]
        for b in code:
            path=output/'source'/Path(b['path']).name
            with path.open('xb') as stream:stream.write(Path(b['path']).read_bytes())
            require(bind(path)['sha256']==b['sha256'],'Source snapshot differs');snapshots.append(bind(path))
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
            preparation=preparation,inputs=bindings,ASR_snapshot=active,new_model_source_or_GUI_execution=False))
        regression.CONTEXT.update(output=output,docs=docs,bindings=bindings)
        try:
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(regression.SequenceTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==10 and not tests.skipped,'Continuity sequence checks failed')
            plan=regression.CONTEXT['plan'];truth=regression.CONTEXT['truth']
            freeze(output/'METADATA_PLAN.json',plan);freeze(output/'EVALUATOR_TRUTH.json',truth)
            for b in code+list(bindings.values()):verify(b)
            guard(output,local,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_CONTINUITY_SEQUENCE_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                metadata_plan=bind(output/'METADATA_PLAN.json'),evaluator_truth=bind(output/'EVALUATOR_TRUTH.json'),
                selected_sessions=plan['original_sessions'],seconds=plan['actual_seconds'],actors=plan['distinct_actor_count'],
                reference_classes=plan['reference_classes'],actual_audio_assembled=False,synthetic_pcm_byte_copy_checked=True,
                actual_application_spawned=False,model_inference_started=False,actual_source_execution=False,
                actual_continuity_test=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 10 continuity preparation checks; 27 whole sessions selected, no application run',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_CONTINUITY_SEQUENCE_PROBE_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
