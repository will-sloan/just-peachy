"""Retest sequence logic and dedicated assembly allocation. README_CONTINUITY_SEQUENCE_V2.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest
from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from review_scoring_bank import require
from scoring_bank import writer_lock
import continuity_sequence_v2 as sequence
import test_continuity_sequence as original
import test_continuity_sequence_v2 as regression


def run(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        sequence.guard(output,local,started);inventory=sequence.allowance(local);code=sequence.code_bindings()
        preparation,bindings,docs=sequence.inputs();failed=bind(local/'n4/continuity-sequence-v1/FAILED.json')
        failure=load(failed['path']);verify(failure['admission']);require(exact_process(load(failure['admission']['path'])['owner']) is None,'Failed V1 helper remains active')
        active=load(local/'n4/asr-full-bank-v1/RESULT.json')
        require(active['status']=='RUNNING' and exact_process(active['child']) is not None and exact_process(active['child']).cpu_affinity()==[4],'Re-observe numerical owner')
        (output/'source').mkdir(parents=True);snapshots=[]
        for b in code:
            path=output/'source'/Path(b['path']).name
            with path.open('xb') as stream:stream.write(Path(b['path']).read_bytes())
            require(bind(path)['sha256']==b['sha256'],'Source snapshot differs');snapshots.append(bind(path))
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
            preparation=preparation,inputs=bindings,preserved_failed_preparation=failed,ASR_snapshot=active,new_model_source_or_GUI_execution=False))
        original.CONTEXT.update(output=output,docs=docs,bindings=bindings)
        try:
            suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(original.SequenceTests),unittest.defaultTestLoader.loadTestsFromTestCase(regression.GuardTests)])
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==14 and not tests.skipped,'V2 sequence checks failed')
            plan=original.CONTEXT['plan'];freeze(output/'METADATA_PLAN.json',plan)
            for b in code+list(bindings.values())+[failed]:verify(b)
            sequence.guard(output,local,started)
            freeze(output/'RESULT.json',dict(status='PASS_CONTINUITY_SEQUENCE_V2_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,metadata_plan=bind(output/'METADATA_PLAN.json'),
                selected_sessions=plan['original_sessions'],seconds=plan['actual_seconds'],actors=plan['distinct_actor_count'],
                reference_classes=plan['reference_classes'],actual_audio_assembled=False,synthetic_pcm_byte_copy_checked=True,
                actual_application_spawned=False,model_inference_started=False,actual_source_execution=False,actual_continuity_test=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 14 continuity selection, PCM and bounded-allocation checks',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_CONTINUITY_SEQUENCE_V2_PROBE_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
