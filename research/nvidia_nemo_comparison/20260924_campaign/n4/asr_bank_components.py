"""Prepare and supervise real application ASR components. README_ASR_BANK.md."""
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

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''

from common import audio_only,bind,verify,freeze,load,fingerprint
from d0_bank_components import verify_contract as verify_d0_contract,event_digest
from d0_calibration_windows import supervisor,ROOT
from asr_lane_components import capture_type

HERE=Path(__file__).resolve().parent
ALLOCATION=2*1024**3
CODE_NAMES=('asr_bank_components.py','asr_lane_components.py','test_asr_lane_components.py','README_ASR_BANK.md')


def resource_guard(root,state):
    policy=load(state/'campaign.json')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    _,low=supervisor.disk_reserves(policy)
    if low:raise RuntimeError('Disk reserve breached: '+str(low))
    size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if size+32*1024**2>ALLOCATION:raise RuntimeError('ASR component allocation exhausted')


def component_key(contract,job,variant,profile):
    audio_only(job)
    if variant not in ('A0','A1','A2','A3'):raise ValueError('Unknown ASR variant')
    return fingerprint(dict(component=contract['component_contract'],job=job,variant=variant,profile=profile,
        history='fresh native stream per independent scene; actual application EOU/reset/flush',
        delivery='unchanged application ASR lane reading forward journal chunks',
        punctuation='actual final-only P0 or native P1, separate modeled FIFO after ASR closure'))


def prepare(args):
    import soundfile as sf
    base=verify_d0_contract(args.d0_admission)
    acceptance=load(HERE.parent/'n3/N3_ACCEPTANCE.json')
    if acceptance['status']!='ACCEPTED_N3_OFFLINE_COMPONENT_SCOPE':raise ValueError('N3 is not accepted')
    accepted_path=HERE.parent/'n3/N3_ACCEPTED_CONFIGS.json';accepted=load(accepted_path)
    expected=acceptance['analysis_files']['N3_ACCEPTED_CONFIGS.json'];actual=bind(accepted_path)
    if any(actual[k]!=expected[k] for k in ('sha256','bytes')):raise ValueError('Accepted N3 configuration changed')
    if load(base['source_receipt']['path'])['parent']!=accepted['source_receipt']:
        raise ValueError('N4 is not derived from the accepted N3 source')
    catalog_check=load(HERE/'ACCEPTED_SOURCE_CATALOG_CHECK.json')
    if bind(args.n3_runtime) not in catalog_check['inputs']:raise ValueError('Runtime differs from accepted 16-entry catalog check')
    runtime=load(args.n3_runtime)
    if runtime['schema']!='just-peachy.n3.runtime.v1' or set(runtime['variants'])!={'A1','A2','A3'}:
        raise ValueError('All three accepted N3 bindings required')
    source=Path(base['source']);sys.path[:0]=[str(source),str(source/'vendor')]
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    from edge_speech_pipeline.n3_a1_adapter import validate_binding as a1_binding
    from edge_speech_pipeline.n3_asr_native import validate_binding as native_binding
    paths={}
    def add(path):
        row=bind(path);paths[row['path']]=row;return row
    for row in load(source/'config/assets.json'):
        if row['component_id'].startswith('sherpa_'):
            b=add(Path(base['models_root'])/row['sha256']/row['filename'])
            if b['sha256']!=row['sha256'] or b['bytes']!=row['bytes']:raise ValueError('Frozen baseline asset differs')
    for variant,binding in runtime['variants'].items():
        if binding['gpu']!=-1:raise ValueError('CPU-only numerical binding required')
        if variant=='A1':
            bundle=a1_binding(binding);add(bundle/'BUNDLE.json')
            for row in load(bundle/'BUNDLE.json')['files']:
                b=add(bundle/row['name'])
                if b['sha256']!=row['sha256'] or b['bytes']!=row['bytes']:raise ValueError('A1 bundle file differs')
        else:
            native_binding(binding);add(binding['model_path'])
            for row in binding['runtime_files']:verify(row);add(row['path'])
    jobs=load(base['manifest']['path'])['jobs']
    if len(jobs)!=480 or len({j['job_id'] for j in jobs})!=480:raise ValueError('Complete bank manifest required')
    # An initial two-file smoke must precede a separately admitted full-bank run.
    if args.scope!='smoke':raise ValueError('Full-bank dispatch requires a reviewed smoke and a fresh admission; not yet enabled')
    selected=jobs[:2]
    for job in selected:
        audio_only(job);info=sf.info(job['audio_path'])
        if (bind(job['audio_path'])['sha256']!=job['audio_sha256'] or info.frames!=job['frames']
                or info.samplerate!=16000 or info.channels!=1 or info.subtype!='PCM_16'):
            raise ValueError('Prepared waveform binding/header changed')
    inventory=load(args.payload_inventory)
    # Charge the full 4-GiB D0 reservation even while it is only partly consumed.
    if inventory['errors'] or inventory['total_logical_bytes']+4*1024**3+ALLOCATION+1024**3>50*1024**3:
        raise ValueError('Conservative shared payload reservation exceeds 50 GiB')
    if args.output.exists():raise ValueError('Fresh ASR run required; preserve earlier evidence')
    profiles={tap:effective_profile('balanced','anonymous_conversation',tap) for tap in ('O0','O1')}
    for profile in profiles.values():
        config=profile.apply(pipeline_config(args.output/'unused-private-root',Path(base['models_root'])))
        if config.input_gain!=1 or config.asr_threads!=1 or config.punctuation_threads!=1:
            raise ValueError('Unexpected actual application configuration')
    args.output.mkdir(parents=True);resource_guard(args.output,args.state)
    code=[bind(HERE/name) for name in CODE_NAMES]
    dependencies=[bind(HERE/name) for name in ('common.py','d0_bank_components.py','d0_calibration_windows.py')]+[
        bind(HERE.parent/'supervision/supervisor.py')]
    component=dict(source_receipt=base['source_receipt'],n3_runtime=bind(args.n3_runtime),
        assets=list(paths.values()),code=code,dependencies=dependencies,
        versions={k:importlib.metadata.version(k) for k in ('numpy','scipy','onnxruntime','sherpa-onnx','soundfile','psutil')},
        python=sys.version,cpu_affinity=[4],threads=1,gpu=False)
    contract=dict(schema='n4-asr-components-v1',scope='SMOKE_EIGHT_COMPONENT_CELLS',
        component_contract=component,source=base['source'],models_root=base['models_root'],
        manifest=base['manifest'],preparation=base['preparation'],d0_admission=bind(args.d0_admission),
        N3_acceptance=bind(HERE.parent/'n3/N3_ACCEPTANCE.json'),accepted_configs=actual,
        jobs=selected,variants=['A0','A1','A2','A3'],total=8,profiles={k:v.to_dict() for k,v in profiles.items()},
        output=str(args.output.resolve()),state=str(args.state.resolve()),allocation_bytes=ALLOCATION,
        payload_inventory=bind(args.payload_inventory),existing_D0_reservation_bytes=4*1024**3,
        remaining_contingency_bytes=1024**3,integrated_N4_cells=0,gui_or_paced_qualification=False,
        notes=['Unchanged frozen application ASR loops; no speaker/tracker/gallery dependencies',
            'Actual P0/native P1 formatting calls after ASR closure; modeled availability only',
            'Read size comes from actual profile, not N3 screen chunk selection',
            'No GPU, microphone, playback, UI, Pi or new model download'])
    freeze(args.output/'ADMISSION.json',contract)
    freeze(args.output/'worker.json',dict(argv=[sys.executable,'-B',str(Path(__file__).resolve()),'run',
        '--admission',str(args.output.resolve()/'ADMISSION.json')],cwd=str(ROOT)))
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',admission=bind(args.output/'ADMISSION.json'),total=8)))


def verify_admission(path):
    contract=load(path);component=contract['component_contract']
    if contract['schema']!='n4-asr-components-v1':raise ValueError('Unknown ASR admission')
    for row in [component['source_receipt'],component['n3_runtime'],contract['manifest'],contract['preparation'],
                contract['d0_admission'],contract['N3_acceptance'],contract['accepted_configs'],
                *component['assets'],*component['code'],*component['dependencies']]:verify(row)
    for rel,row in load(component['source_receipt']['path'])['files'].items():
        actual=bind(Path(contract['source'])/rel)
        if any(actual[k]!=row[k] for k in ('sha256','bytes')):raise ValueError('Frozen source changed')
    if component['python']!=sys.version or component['versions']!={k:importlib.metadata.version(k) for k in component['versions']}:
        raise ValueError('ASR numerical runtime changed')
    return contract


def require_owner(state,coordinator):
    """Only the exact active supervised coordinator may launch a model child."""
    worker=load(state/'worker.json')
    if (worker.get('child_pid')!=coordinator.pid or worker.get('child_create_time')!=coordinator.create_time()
            or not supervisor.same_process(worker)):
        raise RuntimeError('ASR coordinator is not the sole exact supervised child')


def extract(args):
    import psutil
    import soundfile as sf
    import numpy as np
    process=psutil.Process();process.cpu_affinity([4]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract=verify_admission(args.admission);root=Path(contract['output']);state=Path(contract['state'])
    coordinator=process.parent();require_owner(state,coordinator)
    run=load(root/'RESULT.json')
    if run['owner']!=dict(pid=coordinator.pid,create_time=coordinator.create_time()):raise RuntimeError('Wrong model parent')
    source=Path(contract['source']);sys.path[:0]=[str(source),str(source/'vendor')]
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    from app.n3_pipeline import StreamingASRLane
    from edge_speech_pipeline.runtime import PipelineEngine
    from edge_speech_pipeline.models import SherpaStream
    from edge_speech_pipeline.n3_a1_adapter import A1Recognizer
    from edge_speech_pipeline.n3_asr_native import NativeRecognizer
    Capture=capture_type(PipelineEngine);runtime=load(contract['component_contract']['n3_runtime']['path'])
    profile=effective_profile('balanced','anonymous_conversation','O0')
    config=profile.apply(pipeline_config(root/'unused-private-root',Path(contract['models_root'])))
    destination=root/args.variant;destination.mkdir(exist_ok=False)
    resource_guard(root,state);started=time.perf_counter();owner=None;cells={}
    try:
        owner=(SherpaStream(config) if args.variant=='A0' else A1Recognizer(runtime['variants']['A1'],config)
               if args.variant=='A1' else NativeRecognizer(runtime['variants'][args.variant]))
        load_seconds=time.perf_counter()-started
        for job in contract['jobs']:
            require_owner(state,coordinator);resource_guard(root,state);audio_only(job)
            if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Actual audio changed')
            wave,rate=sf.read(job['audio_path'],dtype='float32')
            if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames'] or not np.isfinite(wave).all():raise ValueError('Invalid audio')
            profile=effective_profile('balanced','anonymous_conversation',job['tap'])
            if profile.to_dict()!=contract['profiles'][job['tap']]:raise ValueError('Application profile changed')
            config=profile.apply(pipeline_config(root/'unused-private-root',Path(contract['models_root'])))
            cell=destination/job['job_id'];cell.mkdir();began=time.perf_counter();stream=None
            try:
                stream=SherpaStream(config,resident=owner) if args.variant=='A0' else owner.stream()
                with gzip.open(cell/'ASR_EVENTS.jsonl.gz','xt',encoding='utf-8',newline='\n',compresslevel=3) as log:
                    capture=Capture(profile,config,wave,log,runtime['variants'].get(args.variant))
                    (PipelineEngine._asr_loop if args.variant=='A0' else StreamingASRLane._asr_loop)(capture,stream)
                    summary=capture.finish_capture()
                result=dict(schema='n4-asr-component-cell-v1',status='COMPLETE',variant=args.variant,job=job,
                    admission_sha256=bind(args.admission)['sha256'],cache_key=component_key(contract,job,args.variant,profile.to_dict()),
                    profile_sha256=fingerprint(profile.to_dict()),summary=summary,
                    events=bind(cell/'ASR_EVENTS.jsonl.gz'),events_expanded=event_digest(cell/'ASR_EVENTS.jsonl.gz'),
                    elapsed_seconds=time.perf_counter()-began,process_rss_bytes=process.memory_info().rss,
                    model_load_seconds=load_seconds if not cells else None,actual_neural_inference=True,
                    cpu_affinity=process.cpu_affinity(),integrated_N4_cells=0)
                freeze(cell/'RESULT.json',result)
            except BaseException as exc:
                freeze(cell/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),job=job))
                raise
            finally:
                if stream is not None and hasattr(stream,'close'):stream.close()
            cells[job['job_id']]=bind(cell/'RESULT.json')
            supervisor.atomic(destination/'RESULT_INDEX.json',dict(cells=cells,completed=len(cells),total=len(contract['jobs'])))
            supervisor.atomic(state/'panel_progress.json',dict(stage='N4_ASR_COMPONENT_SMOKE',variant=args.variant,
                completed=contract['variants'].index(args.variant)*len(contract['jobs'])+len(cells),total=contract['total']))
        freeze(destination/'RESULT.json',dict(status='COMPLETE',variant=args.variant,completed=len(cells),
            total=len(contract['jobs']),cells=cells,cpu_affinity=process.cpu_affinity()))
    finally:
        if owner is not None and hasattr(owner,'close'):owner.close()


def run(args):
    import psutil
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract=verify_admission(args.admission);root=Path(contract['output']);state=Path(contract['state'])
    require_owner(state,process)
    with supervisor.lock(root/'owner.lock'):
        if (root/'RESULT.json').exists():raise ValueError('Preserve prior run; use fresh admission after failures')
        result=dict(status='RUNNING',owner=dict(pid=process.pid,create_time=process.create_time()),child=None,
            admission=bind(args.admission),completed=0,total=contract['total'],integrated_N4_cells=0)
        supervisor.atomic(root/'RESULT.json',result)
        try:
            for variant in contract['variants']:
                resource_guard(root,state);require_owner(state,process)
                with (root/(variant+'.log')).open('x',encoding='utf-8') as log:
                    child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'extract','--admission',
                        str(args.admission),'--variant',variant],cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    result.update(variant=variant,child=dict(pid=child.pid,create_time=psutil.Process(child.pid).create_time()))
                    supervisor.atomic(root/'RESULT.json',result);code=child.wait()
                if code:raise RuntimeError(variant+' ASR collection exit '+str(code))
                terminal=load(root/variant/'RESULT.json')
                if terminal['status']!='COMPLETE' or terminal['completed']!=len(contract['jobs']):raise ValueError('Incomplete ASR census')
                result['completed']+=len(contract['jobs'])
            result.update(status='SMOKE_COLLECTED_REQUIRES_REVIEW',child=None,
                variants=[bind(root/v/'RESULT.json') for v in contract['variants']],finished_utc=supervisor.now())
        except BaseException as exc:
            result.update(status='FAILED_PRESERVED',error=repr(exc),finished_utc=supervisor.now());raise
        finally:supervisor.atomic(root/'RESULT.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('d0-admission','n3-runtime','payload-inventory','output','state'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--scope',choices=['smoke','full'],default='smoke')
    for name in ('run','extract','check'):
        p=sub.add_parser(name);p.add_argument('--admission',type=Path,required=True)
        if name=='extract':p.add_argument('--variant',choices=['A0','A1','A2','A3'],required=True)
    args=parser.parse_args()
    import psutil
    psutil.Process().cpu_affinity([4] if args.command=='extract' else [14])
    if args.command=='check':
        contract=verify_admission(args.admission);print(json.dumps(dict(status='VERIFIED_NOT_STARTED',total=contract['total'])))
    else:{'prepare':prepare,'run':run,'extract':extract}[args.command](args)
