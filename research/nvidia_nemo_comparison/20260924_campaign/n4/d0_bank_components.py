"""Full-bank causal D0 evidence, sequential E0/E1. README_D0_BANK.md."""
import argparse
from datetime import datetime,timezone,timedelta
import gzip
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_name]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import load,bind,verify,freeze,fingerprint,audio_only
from d0_calibration_windows import LaneCapture,supervisor,ROOT

HERE=Path(__file__).resolve().parent
LIMIT=4*1024**3


def resource_guard(output,state):
    policy=load(state/'campaign.json')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    _,low=supervisor.disk_reserves(policy)
    if low:raise RuntimeError('Disk reserve breached: '+str(low))
    size=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    if size+32*1024**2>LIMIT:raise RuntimeError('Full-bank D0 allocation exhausted')


def event_digest(path):
    """Read to EOF so gzip CRC/truncation checks actually run."""
    import hashlib
    digest=hashlib.sha256();size=0
    with gzip.open(path,'rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block);size+=len(block)
    return dict(uncompressed_sha256=digest.hexdigest(),uncompressed_bytes=size)


def cell_key(admission,job,encoder,profile):
    audio_only(job)
    if encoder not in ('E0','E1'):raise ValueError('Unknown embedding encoder')
    return fingerprint(dict(admission_sha256=admission,job=job,encoder=encoder,profile=profile,
        history='reset once per complete scene; no known turn resets',
        execution='unchanged fixed-cadence causal speaker lane; no ASR or tracker feedback'))


def prepare(args):
    previous=load(args.collection_admission)
    for row in [previous['source_receipt'],previous['runtime'],*previous['model_bindings'],*previous['code']]:verify(row)
    source_receipt=load(previous['source_receipt']['path']);source=Path(previous['source'])
    for rel,row in source_receipt['files'].items():
        current=bind(source/rel)
        if current['sha256']!=row['sha256'] or current['bytes']!=row['bytes']:raise ValueError('Changed source')
    manifest=load(args.manifest);jobs=manifest['jobs']
    preparation_path=args.manifest.with_name('PREPARATION_RECEIPT.json')
    preparation=load(preparation_path)
    if bind(args.manifest) not in preparation['outputs'] or preparation['waveform_files_verified']!=480:
        raise ValueError('Accepted full-bank preparation binding differs')
    if len(jobs)!=480 or len({j['job_id'] for j in jobs})!=480:
        raise ValueError('Exactly 480 unique full-bank jobs required')
    import soundfile as sf
    for job in jobs:
        audio_only(job);actual=bind(job['audio_path']);info=sf.info(job['audio_path'])
        if actual['sha256']!=job['audio_sha256'] or info.frames!=job['frames']:
            raise ValueError('Audio binding changed')
        if info.samplerate!=16000 or info.channels!=1 or info.subtype!='PCM_16' or info.frames>120*16000:
            raise ValueError('Bounded mono16k PCM16 scene required')
    if args.output.exists():raise ValueError('Use a fresh run; preserve all previous evidence')
    # Charge the new reservation against a conservative private logical inventory.
    inventory=load(args.payload_inventory)
    if inventory['errors'] or inventory['total_logical_bytes']+LIMIT+1024**3>50*1024**3:
        raise ValueError('Insufficient conservative shared payload allowance')
    args.output.mkdir(parents=True)
    resource_guard(args.output,args.state)
    files=[HERE/name for name in ('d0_bank_components.py','d0_calibration_windows.py','common.py','test_d0_bank.py','README_D0_BANK.md')]
    contract=dict(schema='n4-d0-bank-components-v1',source_receipt=previous['source_receipt'],
        source=str(source),runtime=previous['runtime'],models_root=previous['models_root'],
        model_bindings=previous['model_bindings'],source_collection_contract=bind(args.collection_admission),
        manifest=bind(args.manifest),preparation=bind(preparation_path),code=[bind(p) for p in files],
        versions={k:importlib.metadata.version(k) for k in ('numpy','onnxruntime','soundfile','psutil')},
        python=sys.version,expected_clips_per_encoder=480,total=960,output=str(args.output),state=str(args.state),
        payload_inventory=bind(args.payload_inventory),allocation_bytes=LIMIT,allocation_extra_contingency_bytes=1024**3,
        source_seconds_per_encoder=sum(j['frames'] for j in jobs)/16000,cpu_affinity=[4],threads=1,gpu=False,
        recipe='balanced',mode='anonymous_conversation',tap='from bound job',cadence='fixed without spatial cues',
        components=dict(diarization='D0',embeddings=['E0','E1'],asr=None,tracker=None,names=None),
        storage='Streaming gzip of complete segmentation/admission/embedding events; CRC and expanded SHA-256 verified',
        cache_scope='Exact component evidence only; no reuse after waveform/span/gain/model/source/profile/runtime/state change',
        calibration_status='D0/E1 C affine proposal failed; nominal tracker remains unqualified; tracker-free window collection unaffected',
        execution='Accelerated causal unchanged speaker lane; fixed dispatch blocks; no live latency or full-stack resource claim',
        integrated_N4_cells=0)
    freeze(args.output/'ADMISSION.json',contract)
    freeze(args.output/'worker.json',dict(argv=[sys.executable,'-B',str(Path(__file__)),'run','--admission',str(args.output/'ADMISSION.json')],cwd=str(ROOT)))
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',admission=bind(args.output/'ADMISSION.json'),total=960)))


def verify_contract(path):
    contract=load(path)
    for row in [contract['source_receipt'],contract['runtime'],contract['manifest'],contract['preparation'],
                contract['source_collection_contract'],*contract['model_bindings'],*contract['code']]:verify(row)
    source_receipt=load(contract['source_receipt']['path'])
    for rel,row in source_receipt['files'].items():
        actual=bind(Path(contract['source'])/rel)
        if actual['sha256']!=row['sha256'] or actual['bytes']!=row['bytes']:raise ValueError('Changed source')
    if contract['versions']!={k:importlib.metadata.version(k) for k in contract['versions']} or contract['python']!=sys.version:
        raise ValueError('Bound numerical runtime versions changed')
    return contract


def extract(args):
    import psutil
    import soundfile as sf
    import numpy as np
    process=psutil.Process();process.cpu_affinity([4]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract=verify_contract(args.admission);root=Path(contract['output']);state=Path(contract['state'])
    destination=root/args.encoder;destination.mkdir(exist_ok=False)
    source=Path(contract['source']);sys.path[:0]=[str(source),str(source/'vendor')]
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    from app.n2_models import N2SpeakerModels
    from edge_speech_pipeline.research_evidence_v3 import run_speaker_lane_v3
    profiles={tap:effective_profile('balanced','anonymous_conversation',tap) for tap in ('O0','O1')}
    configs={tap:p.apply(pipeline_config(root/'unused-private-root',Path(contract['models_root']))) for tap,p in profiles.items()}
    if any(c.speaker_threads!=1 for c in configs.values()):raise ValueError('One model thread required')
    resource_guard(root,state);model=N2SpeakerModels(configs['O0'],args.encoder,load(contract['runtime']['path']),pyannote=True)
    admitted=bind(args.admission)['sha256'];index={};jobs=load(contract['manifest']['path'])['jobs']
    for job in jobs:
        resource_guard(root,state);audio_only(job)
        if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Changed full-bank audio')
        wave,rate=sf.read(job['audio_path'],dtype='float32')
        if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames'] or not np.isfinite(wave).all():raise ValueError('Invalid source waveform')
        profile=profiles[job['tap']];cell=destination/job['job_id'];cell.mkdir()
        key=cell_key(admitted,job,args.encoder,profile.to_dict());started=time.monotonic()
        with gzip.open(cell/'LANE_EVENTS.jsonl.gz','xt',encoding='utf-8',newline='\n',compresslevel=3) as stream:
            engine=LaneCapture(profile,configs[job['tap']],wave,stream);run_speaker_lane_v3(engine,model)
        digest=event_digest(cell/'LANE_EVENTS.jsonl.gz')
        complete=engine.error is None and engine._telemetry.get('identity_audio_samples')==len(wave)
        result=dict(schema='n4-d0-component-cell-v1',status='COMPLETE' if complete else 'FAILED',job=job,
            encoder=args.encoder,cache_key=key,admission_sha256=admitted,profile_sha256=fingerprint(profile.to_dict()),
            namespace=model.namespace,vectors=engine.vectors,segmentation_calls=engine.segmentation_calls,
            telemetry=engine._telemetry,error=engine.error,events=bind(cell/'LANE_EVENTS.jsonl.gz'),events_expanded=digest,
            elapsed_seconds=time.monotonic()-started,process_rss_bytes=process.memory_info().rss,
            observed_compute_is_live_latency=False,tracker_name_or_ASR_outputs_present=False)
        freeze(cell/'RESULT.json',result);index[job['job_id']]=bind(cell/'RESULT.json')
        supervisor.atomic(destination/'RESULT_INDEX.json',dict(admission_sha256=admitted,cells=index,total=480,
            completed=len(index) if complete else len(index)-1,failed=0 if complete else 1))
        supervisor.atomic(state/'panel_progress.json',dict(completed=(480 if args.encoder=='E1' else 0)+len(index),total=960,
            elapsed_seconds=time.monotonic()-args.started,stage='N4_D0_FULL_BANK_COMPONENTS',encoder=args.encoder))
        if not complete:raise RuntimeError('Failed native lane; stop and preserve full attempt: '+str(engine.error))
    freeze(destination/'RESULT.json',dict(status='COMPLETE',completed=480,total=480,cells=index,
        profiles={tap:p.to_dict() for tap,p in profiles.items()},namespace=model.namespace,
        cpu_affinity=process.cpu_affinity(),one_native_model_thread=True))


def run(args):
    import psutil
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract=verify_contract(args.admission);root=Path(contract['output']);started=time.monotonic()
    with supervisor.lock(root/'owner.lock'):
        receipt=dict(status='RUNNING',owner=dict(pid=process.pid,create_time=process.create_time()),child=None,
            admission=bind(args.admission),completed=0,total=960,integrated_N4_cells=0,started_utc=supervisor.now())
        supervisor.atomic(root/'RESULT.json',receipt)
        try:
            for encoder in ('E0','E1'):
                resource_guard(root,Path(contract['state']))
                argv=[sys.executable,'-B',str(Path(__file__)),'extract','--admission',str(args.admission),'--encoder',encoder,'--started',str(started)]
                with (root/(encoder+'.log')).open('x',encoding='utf-8') as log:
                    child=subprocess.Popen(argv,cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    receipt.update(child=dict(pid=child.pid,create_time=psutil.Process(child.pid).create_time()),encoder=encoder)
                    supervisor.atomic(root/'RESULT.json',receipt);code=child.wait()
                if code:raise RuntimeError(encoder+' full-bank collection exit '+str(code))
                result=load(root/encoder/'RESULT.json')
                if result['status']!='COMPLETE' or result['completed']!=480:raise ValueError('Incomplete encoder census')
                receipt['completed']+=480
            receipt.update(status='COLLECTED_REQUIRES_REVIEW',child=None,finished_utc=supervisor.now(),
                encoders=[bind(root/e/'RESULT.json') for e in ('E0','E1')])
        except BaseException as exc:
            receipt.update(status='FAILED',error=repr(exc),finished_utc=supervisor.now());raise
        finally:supervisor.atomic(root/'RESULT.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('collection-admission','manifest','payload-inventory','output','state'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('run','extract'):
        p=sub.add_parser(name);p.add_argument('--admission',type=Path,required=True)
        if name=='extract':p.add_argument('--encoder',choices=('E0','E1'),required=True);p.add_argument('--started',type=float,required=True)
    args=parser.parse_args();{'prepare':prepare,'run':run,'extract':extract}[args.command](args)
