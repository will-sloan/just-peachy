"""Continuity assembly with a dedicated bounded payload guard. README_CONTINUITY_SEQUENCE_V2.md."""
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import shutil
import time
from common import bind, freeze, load, verify
from metric_process import identity, pin
from review_scoring_bank import require
from scoring_bank import writer_lock
from asr_full_bank import payload_inventory
from continuity_sequence import inputs, build, materialize, code_bindings as original_code

HERE=Path(__file__).resolve().parent
GIB=1024**3
MAX_OUTPUT=64*1024**2
PACKAGING=datetime(2026,9,28,2,48,19,tzinfo=timezone.utc)


def guard(output,local,started,seconds=720):
    require(time.monotonic()-started<seconds,'Continuity preparation time budget reached')
    policy=load(local/'supervision/campaign.json')
    cutoff=min(PACKAGING,datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12))
    require(datetime.now(timezone.utc)<cutoff,'Packaging reserve reached')
    for drive,floor in (('C:/',50),('G:/',75)):
        require(shutil.disk_usage(drive).free>=floor*GIB+MAX_OUTPUT,'Continuity drive floor unavailable')
    if output.exists():
        require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<MAX_OUTPUT,'Continuity output bound reached')


def allowance(local):
    inventory=payload_inventory(local);policy=load(local/'supervision/campaign.json')
    require(not inventory['errors'] and inventory['total_logical_bytes']+6*GIB+MAX_OUTPUT<=
        min(50,policy['resource_policy']['new_payload_allowance_gib'])*GIB,'Shared continuity allowance unavailable')
    return inventory


def code_bindings():
    return [bind(HERE/n) for n in ('continuity_sequence_v2.py','test_continuity_sequence_v2.py',
        'probe_continuity_sequence_v2.py','README_CONTINUITY_SEQUENCE_V2.md')]+original_code()


def prepare(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started);inventory=allowance(local);code=code_bindings()
        qualification=load(HERE/'CONTINUITY_SEQUENCE_CHECK_V2.json')
        require(qualification['status']=='PASS_CONTINUITY_SEQUENCE_V2_DEVELOPMENT_ONLY' and qualification['code']==code,'Qualified V2 preparation required')
        for b in code+[qualification['private_receipt'],qualification['private_admission'],qualification['tests']]:verify(b)
        preparation,bindings,docs=inputs();plan,truth=build(docs,bindings)
        require(2*plan['frames']+4*1024**2<MAX_OUTPUT,'PCM plus metadata margin exceeds dedicated allocation')
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,preparation=preparation,inputs=bindings,inventory=inventory,
            qualification=bind(HERE/'CONTINUITY_SEQUENCE_CHECK_V2.json'),maximum_output_bytes=MAX_OUTPUT,
            source_execution_authorized=False))
        freeze(output/'PLAN.json',plan)
        try:
            job,copied=materialize(plan,output/'CONTINUITY_O0.wav',checkpoint=lambda:guard(output,local,started))
            freeze(output/'INFERENCE_AUDIO_ONLY.json',dict(schema='n4-audio-only-v1',jobs=[job]))
            freeze(output/'EVALUATOR_TRUTH.json',dict(schema='n4-evaluator-truth-v1',NEVER_PASS_TO_RUNTIME=True,cells=[truth]))
            freeze(output/'COPY_RECEIPT.json',copied)
            for b in code+list(bindings.values()):verify(b)
            guard(output,local,started)
            freeze(output/'RESULT.json',dict(status='PREPARED_LOSSLESS_CONTINUITY_INPUT_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),plan=bind(output/'PLAN.json'),audio_only=bind(output/'INFERENCE_AUDIO_ONLY.json'),
                evaluator_truth=bind(output/'EVALUATOR_TRUTH.json'),copy_receipt=bind(output/'COPY_RECEIPT.json'),
                sessions=plan['original_sessions'],seconds=plan['actual_seconds'],distinct_actor_count=plan['distinct_actor_count'],
                actual_application_spawned=False,actual_source_execution=False,actual_continuity_test=False,integrated_N4_cells=0,N4_accepted=False))
            print('Prepared 27 exact saved PCM sessions (20:06.78); no application run or playback',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_SEQUENCE_PREPARATION_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args().output)
