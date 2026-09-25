"""Reviewed full-bank ASR collection. See README_ASR_FULL_BANK.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import gzip
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''

from common import audio_only, bind, verify, freeze, load, fingerprint
from asr_bank_components import verify_admission as verify_smoke_admission, component_key, require_owner
from review_asr_components import scan_events
from d0_bank_components import event_digest
from d0_calibration_windows import supervisor, ROOT
from asr_lane_components import capture_type

HERE=Path(__file__).resolve().parent
ALLOCATION=2*1024**3
CELL_LIMIT=32*1024**2
CODE_NAMES=('asr_full_bank.py','test_asr_full_bank.py','README_ASR_FULL_BANK.md',
    'review_asr_full_bank.py','test_review_asr_full_bank.py')


class BoundedTextWriter:
    def __init__(self, stream, limit=CELL_LIMIT):
        self.stream, self.limit, self.written = stream, limit, 0
    def write(self, text):
        size=len(text.encode('utf-8'))
        if self.written+size>self.limit:raise RuntimeError('ASR per-cell expanded event limit exceeded; preserve failed cell')
        answer=self.stream.write(text);self.written+=size;return answer


def payload_inventory(root):
    """Read logical bytes without following symlinks/junctions; no dedup credit."""
    total=files=0;reparse=[];pending=[Path(root)]
    while pending:
        directory=pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                info=entry.stat(follow_symlinks=False)
                if entry.is_symlink() or getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    reparse.append(entry.path);total+=info.st_size;continue
                if entry.is_dir(follow_symlinks=False):pending.append(Path(entry.path))
                else:total+=info.st_size;files+=1
    return dict(checked_utc=supervisor.now(),root=str(Path(root).resolve()),total_logical_bytes=total,
        files=files,reparse_not_traversed=reparse,errors=[],scope='All private campaign files; no deduplication credit; original shared models/audio excluded')


def resource_guard(root,state):
    policy=load(state/'campaign.json')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    _,low=supervisor.disk_reserves(policy)
    if low:raise RuntimeError('Disk reserve breached: '+str(low))
    size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if size+CELL_LIMIT+2*1024**2>ALLOCATION:raise RuntimeError('Full ASR allocation exhausted')


def check_bank(jobs):
    if len(jobs)!=480 or len({j['job_id'] for j in jobs})!=480:
        raise ValueError('Exactly 480 distinct full-bank jobs required')
    for j in jobs:audio_only(j)
    if sum(j['tap']=='O0' for j in jobs)!=240 or sum(j['tap']=='O1' for j in jobs)!=240:
        raise ValueError('Both complete tap populations required')
    return jobs


def verify_smoke_review(path, *, scan=False):
    receipt=load(path)
    if (receipt['schema']!='n4-asr-smoke-review-v1' or receipt['status']!='PASS_ASR_COMPONENT_SMOKE'
            or receipt['component_cells']!=8 or receipt['per_variant']!=2 or len(receipt['cells'])!=8
            or receipt['integrated_N4_cells']!=0 or receipt['Controller_or_widget_parity_qualified'] is not False):
        raise ValueError('Passed eight-cell ASR smoke review required')
    for binding in [receipt['admission'],receipt['final_result'],*receipt['code']]:verify(binding)
    parent=verify_smoke_admission(receipt['admission']['path'])
    if (parent['scope']!='SMOKE_EIGHT_COMPONENT_CELLS' or parent['total']!=8 or len(parent['jobs'])!=2
            or receipt['component_contract_sha256']!=fingerprint(parent['component_contract'])):
        raise ValueError('Smoke review component contract differs')
    final=load(receipt['final_result']['path'])
    if (final['status']!='SMOKE_COLLECTED_REQUIRES_REVIEW' or final['completed']!=8 or final['total']!=8
            or final['admission']!=receipt['admission'] or final['child'] is not None):
        raise ValueError('Smoke terminal census differs')
    expected=[(v,j) for v in parent['variants'] for j in parent['jobs']]
    for row,(variant,job) in zip(receipt['cells'],expected):
        verify(row['result']);cell=load(row['result']['path']);profile=parent['profiles'][job['tap']]
        if (row['variant']!=variant or cell['job']!=job or cell['variant']!=variant or cell['status']!='COMPLETE'
                or cell['admission_sha256']!=receipt['admission']['sha256']
                or cell['cache_key']!=component_key(parent,job,variant,profile)):
            raise ValueError('Smoke cell identity/cache differs')
        verify(cell['events'])
        if scan and scan_events(cell,round(profile['asr']['journal_read_ms']*16))!=row['scan']:
            raise ValueError('Smoke full event scan differs')
    return parent


def prepare(args):
    import soundfile as sf
    if args.output.exists():raise ValueError('Fresh full-bank output required')
    parent=verify_smoke_review(args.smoke_review,scan=True)
    jobs=check_bank(load(parent['manifest']['path'])['jobs'])
    for job in jobs:
        info=sf.info(job['audio_path'])
        if (bind(job['audio_path'])['sha256']!=job['audio_sha256'] or info.frames!=job['frames']
                or info.samplerate!=16000 or info.channels!=1 or info.subtype!='PCM_16'):
            raise ValueError('Full-bank waveform binding/header differs')
    inventory=payload_inventory(ROOT.parent/'local')
    # Additional reservations, beyond every byte already in the new inventory:
    # full ASR 2 GiB, pending D1 smoke <=2 GiB, future D1 bank 2 GiB, contingency 1 GiB.
    reservations=7*1024**3
    policy=load(args.state/'campaign.json')
    limit=min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3
    if inventory['total_logical_bytes']+reservations>limit:
        raise ValueError('Remaining shared payload allowance cannot admit full ASR plus downstream reservations')
    component=deepcopy(parent['component_contract'])
    component['code'] += [bind(HERE/n) for n in CODE_NAMES]
    component['dependencies'] += [bind(HERE/'review_asr_components.py')]
    contract=dict(schema='n4-asr-full-bank-v1',scope='FULL_1920_COMPONENT_CELLS',component_contract=component,
        parent_component_contract_sha256=fingerprint(parent['component_contract']),
        smoke_review=bind(args.smoke_review),source=parent['source'],models_root=parent['models_root'],
        manifest=parent['manifest'],preparation=parent['preparation'],profiles=parent['profiles'],
        jobs=jobs,variants=['A0','A1','A2','A3'],total=1920,
        output=str(args.output.resolve()),state=str(args.state.resolve()),allocation_bytes=ALLOCATION,
        per_cell_expanded_limit_bytes=CELL_LIMIT,other_pending_reservations_bytes=5*1024**3,
        payload_inventory=inventory,integrated_N4_cells=0,gui_or_paced_qualification=False,
        notes=['Fresh state per scene; actual unchanged application ASR loops and frozen CPU1 owners',
            'No reuse of smoke cell timing; all 480 files are recollected per variant',
            'Actual final-only formatting calls in separate modeled FIFO, not GUI timing',
            'Reference-free predictor; one numerical owner; no devices, downloads or Pi'])
    args.output.mkdir(parents=True);resource_guard(args.output,args.state)
    freeze(args.output/'ADMISSION.json',contract)
    freeze(args.output/'worker.json',dict(argv=[sys.executable,'-B',str(Path(__file__).resolve()),'run',
        '--admission',str(args.output.resolve()/'ADMISSION.json')],cwd=str(ROOT)))
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',admission=bind(args.output/'ADMISSION.json'),total=1920,
        allocated_plus_existing_gib=(inventory['total_logical_bytes']+reservations)/1024**3)))


def verify_admission(path):
    contract=load(path)
    if (contract['schema']!='n4-asr-full-bank-v1' or contract['scope']!='FULL_1920_COMPONENT_CELLS'
            or contract['total']!=1920 or contract['variants']!=['A0','A1','A2','A3']
            or contract['allocation_bytes']!=ALLOCATION or contract['per_cell_expanded_limit_bytes']!=CELL_LIMIT):
        raise ValueError('Wrong full-bank ASR scope/census/budget')
    verify(contract['smoke_review']);parent=verify_smoke_review(contract['smoke_review']['path'])
    expected=deepcopy(parent['component_contract'])
    expected['code'] += [bind(HERE/n) for n in CODE_NAMES]
    expected['dependencies'] += [bind(HERE/'review_asr_components.py')]
    if (contract['component_contract']!=expected or contract['parent_component_contract_sha256']!=fingerprint(parent['component_contract'])
            or contract['integrated_N4_cells']!=0 or contract['gui_or_paced_qualification'] is not False):
        raise ValueError('Full-bank executable contract changed')
    for key in ('source','models_root','manifest','preparation','profiles'):
        if contract[key]!=parent[key]:raise ValueError('Full-bank upstream binding differs: '+key)
    jobs=check_bank(load(contract['manifest']['path'])['jobs'])
    if contract['jobs']!=jobs:raise ValueError('Full-bank job list was changed/subsampled')
    if Path(path).resolve()!=Path(contract['output']).resolve()/'ADMISSION.json':
        raise ValueError('Full-bank admission moved to another output')
    return contract


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
                with gzip.open(cell/'ASR_EVENTS.jsonl.gz','xt',encoding='utf-8',newline='\n',compresslevel=3) as compressed:
                    log=BoundedTextWriter(compressed)
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
            supervisor.atomic(state/'panel_progress.json',dict(stage='N4_ASR_FULL_BANK_COMPONENTS',variant=args.variant,
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
            result.update(status='FULL_BANK_COLLECTED_REQUIRES_REVIEW',child=None,
                variants=[bind(root/v/'RESULT.json') for v in contract['variants']],finished_utc=supervisor.now())
        except BaseException as exc:
            result.update(status='FAILED_PRESERVED',error=repr(exc),finished_utc=supervisor.now());raise
        finally:supervisor.atomic(root/'RESULT.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('smoke-review','output','state'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('run','extract','check'):
        p=sub.add_parser(name);p.add_argument('--admission',type=Path,required=True)
        if name=='extract':p.add_argument('--variant',choices=['A0','A1','A2','A3'],required=True)
    args=parser.parse_args()
    import psutil
    psutil.Process().cpu_affinity([4] if args.command=='extract' else [14])
    if args.command=='check':
        contract=verify_admission(args.admission);print(json.dumps(dict(status='VERIFIED',total=contract['total'])))
    else:{'prepare':prepare,'run':run,'extract':extract}[args.command](args)
