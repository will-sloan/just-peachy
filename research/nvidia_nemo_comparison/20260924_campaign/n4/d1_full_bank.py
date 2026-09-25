"""Admit full-bank D1 after passed smoke. See README_D1_FULL_BANK.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from common import audio_only, bind, verify, freeze, load, fingerprint
from asr_bank_components import require_owner
from asr_full_bank import payload_inventory, check_bank, verify_admission as verify_asr_full, component_key as asr_key
from d0_bank_components import event_digest
from d0_calibration_windows import supervisor, ROOT
from d1_bank_components import component_key, verify_admission as verify_smoke_admission
from d1_lane_components import capture_type
from review_d1_components import scan_events

HERE=Path(__file__).resolve().parent
ALLOCATION=2*1024**3
CELL_LIMIT=32*1024**2
CODE_NAMES=('d1_full_bank.py','test_d1_full_bank.py','review_d1_full_bank.py',
            'test_review_d1_full_bank.py','README_D1_FULL_BANK.md')
DEPENDENCIES=('asr_full_bank.py','review_asr_components.py','review_d1_components.py')


class BoundedTextWriter:
    def __init__(self, stream, limit=CELL_LIMIT):self.stream,self.limit,self.written=stream,limit,0
    def write(self, text):
        size=len(text.encode('utf-8'))
        if self.written+size>self.limit:raise RuntimeError('D1 per-cell expanded event limit exceeded; preserve failed cell')
        result=self.stream.write(text);self.written+=size;return result


def resource_guard(root,state):
    policy=load(state/'campaign.json')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    _,low=supervisor.disk_reserves(policy)
    if low:raise RuntimeError('Disk reserve breached: '+str(low))
    size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    # Up to 32 MiB event text plus a 4 MiB summary/index margin per cell.
    if size+CELL_LIMIT+4*1024**2>ALLOCATION:raise RuntimeError('Full D1 allocation exhausted')


def verify_smoke_review(path, *, scan=False):
    receipt=load(path)
    if (receipt['status']!='PASS_D1_COMPONENT_SMOKE' or receipt['component_cells']!=4
            or receipt['paired_files']!=2 or len(receipt['rows'])!=4 or receipt['integrated_N4_cells']!=0
            or receipt['Controller_widget_parity'] is not False):
        raise ValueError('Passed four-cell D1 smoke review required')
    for binding in [receipt['admission'],receipt['terminal'],receipt['reviewer']]:verify(binding)
    if receipt['reviewer']!=bind(HERE/'review_d1_components.py'):raise ValueError('Unexpected D1 reviewer')
    parent=verify_smoke_admission(receipt['admission']['path'])
    terminal=load(receipt['terminal']['path'])
    if (terminal['status']!='SMOKE_COLLECTED_REQUIRES_REVIEW' or terminal['completed']!=4
            or terminal['total']!=4 or terminal['child'] is not None or terminal['admission']!=receipt['admission']
            or parent['total']!=4 or len(parent['jobs'])!=2 or parent['encoders']!=['E0','E1']):
        raise ValueError('D1 smoke terminal/admission census differs')
    if scan:
        import soundfile as sf
        source=Path(parent['source']);sys.path[:0]=[str(source),str(source/'vendor')]
        from app.n2_pipeline import ActivityTimeline
    pairs={}
    for row,(encoder,job) in zip(receipt['rows'],[(e,j) for e in parent['encoders'] for j in parent['jobs']]):
        verify(row['result']);cell=load(row['result']['path'])
        if (row['encoder']!=encoder or row['job_id']!=job['job_id'] or cell['job']!=job
                or cell['encoder']!=encoder or cell['status']!='COMPLETE'
                or cell['admission_sha256']!=receipt['admission']['sha256']
                or cell['cache_key']!=component_key(parent,job,encoder,parent['profiles'][job['tap']])):
            raise ValueError('D1 smoke identity/cache differs')
        verify(cell['events'])
        scan_record={k:row[k] for k in ['native_frames','embeddings','short_runs','semantic_frames_sha256','query_geometry_sha256']}
        if pairs.setdefault(job['job_id'],scan_record)!=scan_record:raise ValueError('D1 paired smoke geometry differs')
        if scan:
            if event_digest(cell['events']['path'])!=cell['events_expanded']:raise ValueError('D1 expanded bytes changed')
            if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('D1 smoke audio changed')
            wave,rate=sf.read(job['audio_path'],dtype='float32')
            if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames']:raise ValueError('D1 smoke waveform differs')
            with gzip.open(cell['events']['path'],'rt',encoding='utf-8') as stream:events=[json.loads(s) for s in stream]
            if scan_events(events,wave,cell['summary'],cell['namespace'],ActivityTimeline)!=scan_record:
                raise ValueError('D1 smoke event scan differs')
    return parent


def require_predecessor(contract):
    """Require the closed, reviewed ASR bank before any D1 model is loaded."""
    path=Path(contract['predecessor_review_path'])
    if not path.is_file():raise ValueError('ASR full-bank terminal review is not available; D1 remains prepared')
    receipt=load(path)
    if (receipt['schema']!='n4-asr-full-bank-review-v1' or receipt['status']!='PASS_ASR_FULL_BANK_COMPONENTS_ONLY'
            or receipt['component_cells']!=1920 or receipt['per_variant']!=480 or len(receipt['cells'])!=1920
            or receipt['admission']!=contract['asr_full_admission'] or receipt['integrated_N4_cells']!=0):
        raise ValueError('Passed complete ASR predecessor review required')
    parent=verify_asr_full(contract['asr_full_admission']['path'])
    if receipt['component_contract_sha256']!=fingerprint(parent['component_contract']):
        raise ValueError('ASR predecessor component contract differs')
    for row in [receipt['admission'],receipt['final_result'],*receipt['code']]:verify(row)
    expected_code=[bind(HERE/n) for n in ['review_asr_full_bank.py','test_review_asr_full_bank.py','README_ASR_FULL_BANK.md']]
    if receipt['code']!=expected_code:raise ValueError('ASR predecessor reviewer differs')
    terminal=load(receipt['final_result']['path'])
    if (terminal['status']!='FULL_BANK_COLLECTED_REQUIRES_REVIEW' or terminal['completed']!=1920
            or terminal['total']!=1920 or terminal['child'] is not None or supervisor.same_process(terminal['owner'])
            or terminal['admission']!=contract['asr_full_admission']
            or Path(receipt['final_result']['path']).resolve()!=Path(parent['output'])/'RESULT.json'):
        raise ValueError('ASR predecessor not terminal or exact owner remains active')
    expected=[(v,j) for v in parent['variants'] for j in parent['jobs']]
    for row,(variant,job) in zip(receipt['cells'],expected):
        verify(row['result']);cell=load(row['result']['path'])
        expected_path=Path(parent['output'])/variant/job['job_id']/'RESULT.json'
        if (row['variant']!=variant or cell['variant']!=variant or cell['job']!=job or cell['status']!='COMPLETE'
                or Path(row['result']['path']).resolve()!=expected_path
                or cell['admission_sha256']!=contract['asr_full_admission']['sha256']
                or cell['cache_key']!=asr_key(parent,job,variant,parent['profiles'][job['tap']])
                or Path(cell['events']['path']).resolve()!=expected_path.parent/'ASR_EVENTS.jsonl.gz'):
            raise ValueError('ASR predecessor cell census differs')
        verify(cell['events'])
    return bind(path)


def prepare(args):
    import soundfile as sf
    if args.output.exists():raise ValueError('Fresh D1 full-bank output required')
    parent=verify_smoke_review(args.smoke_review,scan=True)
    asr=verify_asr_full(args.asr_full_admission)
    if (asr['manifest']!=parent['manifest'] or asr['component_contract']['source_receipt']!=parent['component_contract']['source_receipt']
            or asr['state']!=str(args.state.resolve())):raise ValueError('Different ASR/D1 source, bank or supervisor')
    jobs=check_bank(load(parent['manifest']['path'])['jobs'])
    for job in jobs:
        info=sf.info(job['audio_path'])
        if (bind(job['audio_path'])['sha256']!=job['audio_sha256'] or info.frames!=job['frames']
                or info.samplerate!=16000 or info.channels!=1 or info.subtype!='PCM_16' or info.frames>120*16000):
            raise ValueError('Full D1 waveform binding/header/length differs')
    inventory=payload_inventory(ROOT.parent/'local');policy=load(args.state/'campaign.json')
    # Count existing bytes plus this 2GiB, active ASR's full 2GiB and 1GiB contingency.
    reserved=5*1024**3
    limit=min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3
    if inventory['total_logical_bytes']+reserved>limit:raise ValueError('Full D1 reservation exceeds shared allowance')
    component=deepcopy(parent['component_contract'])
    component['code'] += [bind(HERE/n) for n in CODE_NAMES]
    component['dependencies'] += [bind(HERE/n) for n in DEPENDENCIES]
    contract=dict(schema='n4-d1-full-bank-v1',scope='FULL_960_COMPONENT_CELLS',component_contract=component,
        parent_component_contract_sha256=fingerprint(parent['component_contract']),smoke_review=bind(args.smoke_review),
        asr_full_admission=bind(args.asr_full_admission),predecessor_review_path=str(args.asr_full_review.resolve()),
        source=parent['source'],models_root=parent['models_root'],manifest=parent['manifest'],preparation=parent['preparation'],
        profiles=parent['profiles'],jobs=jobs,encoders=['E0','E1'],total=960,output=str(args.output.resolve()),
        state=str(args.state.resolve()),allocation_bytes=ALLOCATION,per_cell_expanded_limit_bytes=CELL_LIMIT,
        other_pending_reservations_bytes=3*1024**3,payload_inventory=inventory,integrated_N4_cells=0,
        gui_or_paced_qualification=False,inference_started=False,
        notes=['Exact frozen N2Engine speaker loop and ActivityTimeline; native CPU1 low_latency D1',
            'One resident D1/encoder owner, independent-scene stream reset, actual 100ms source reads and one finish',
            'All native frames and contiguous query vectors retained; clocks explicitly modeled',
            'Existing ASR must finish and pass its strict review before this sole supervisor can launch D1',
            'No ASR, Pyannote, roster/gallery, device, Pi, capture, playback or download in D1 worker'])
    args.output.mkdir(parents=True);resource_guard(args.output,args.state)
    freeze(args.output/'ADMISSION.json',contract)
    freeze(args.output/'worker.json',dict(argv=[sys.executable,'-B',str(Path(__file__).resolve()),'run',
        '--admission',str(args.output.resolve()/'ADMISSION.json')],cwd=str(ROOT)))
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',admission=bind(args.output/'ADMISSION.json'),total=960,
        conservative_inventory_and_reservations_gib=(inventory['total_logical_bytes']+reserved)/1024**3)))


def verify_admission(path):
    contract=load(path)
    if (contract['schema']!='n4-d1-full-bank-v1' or contract['scope']!='FULL_960_COMPONENT_CELLS'
            or contract['total']!=960 or contract['encoders']!=['E0','E1'] or contract['allocation_bytes']!=ALLOCATION
            or contract['per_cell_expanded_limit_bytes']!=CELL_LIMIT):raise ValueError('Wrong full D1 scope/census/budget')
    verify(contract['smoke_review']);parent=verify_smoke_review(contract['smoke_review']['path'])
    verify(contract['asr_full_admission'])
    expected=deepcopy(parent['component_contract'])
    expected['code'] += [bind(HERE/n) for n in CODE_NAMES]
    expected['dependencies'] += [bind(HERE/n) for n in DEPENDENCIES]
    if (contract['component_contract']!=expected or contract['parent_component_contract_sha256']!=fingerprint(parent['component_contract'])
            or contract['integrated_N4_cells']!=0 or contract['gui_or_paced_qualification'] is not False):
        raise ValueError('Full D1 executable contract changed')
    for key in ('source','models_root','manifest','preparation','profiles'):
        if contract[key]!=parent[key]:raise ValueError('Full D1 upstream binding differs: '+key)
    if contract['jobs']!=check_bank(load(contract['manifest']['path'])['jobs']):raise ValueError('Full D1 bank changed/subsampled')
    if Path(path).resolve()!=Path(contract['output']).resolve()/'ADMISSION.json':raise ValueError('D1 admission moved')
    return contract


def extract(args):
    import psutil
    import soundfile as sf
    import numpy as np
    process = psutil.Process()
    process.cpu_affinity([4])
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract = verify_admission(args.admission)
    root, state = Path(contract['output']), Path(contract['state'])
    predecessor=require_predecessor(contract)
    parent = process.parent()
    require_owner(state, parent)
    if load(root/'RESULT.json')['owner'] != dict(pid=parent.pid, create_time=parent.create_time()):
        raise RuntimeError('Wrong numerical parent')
    if load(root/'RESULT.json')['predecessor_review']!=predecessor:raise ValueError('D1 predecessor receipt changed after launch')
    source = Path(contract['source'])
    sys.path[:0] = [str(source), str(source/'vendor')]
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    from app.n2_models import N2ResidentModels, N2SpeakerModels, load_runtime
    from app.n2_pipeline import N2Engine, ActivityTimeline
    from app.n2_identity import N2NameMap
    runtime = load_runtime(Path(contract['component_contract']['runtime']['path']).parent)
    Capture = capture_type(N2Engine, ActivityTimeline, N2NameMap)
    destination = root/args.encoder
    destination.mkdir(exist_ok=False)
    cells = {}
    owner = N2ResidentModels('D1', args.encoder, runtime)
    try:
        resource_guard(root, state)
        profile = effective_profile('balanced', 'anonymous_conversation', 'O0')
        config = profile.apply(pipeline_config(root/'unused-private-root', Path(contract['models_root'])))
        start = time.perf_counter()
        encoder = N2SpeakerModels(config, args.encoder, runtime, pyannote=False)
        embedding_load_sec = time.perf_counter()-start
        for job in contract['jobs']:
            require_owner(state, parent)
            resource_guard(root, state)
            audio_only(job)
            if bind(job['audio_path'])['sha256'] != job['audio_sha256']:
                raise ValueError('Actual audio changed')
            wave, rate = sf.read(job['audio_path'], dtype='float32')
            if rate != 16000 or wave.ndim != 1 or len(wave) != job['frames'] or not np.isfinite(wave).all():
                raise ValueError('Invalid actual audio')
            profile = effective_profile('balanced', 'anonymous_conversation', job['tap'])
            if profile.to_dict() != contract['profiles'][job['tap']]:
                raise ValueError('Profile changed')
            cell = destination/job['job_id']
            cell.mkdir()
            start = time.perf_counter()
            try:
                with gzip.open(cell/'D1_EVENTS.jsonl.gz', 'xt', encoding='utf-8', newline='\n', compresslevel=3) as compressed:
                    log=BoundedTextWriter(compressed)
                    capture = Capture(wave, log, owner, job['job_id'])
                    summary = capture.run_capture(encoder)
                result = dict(schema='n4-d1-component-cell-v1', status='COMPLETE', job=job,
                    encoder=args.encoder, admission_sha256=bind(args.admission)['sha256'],
                    cache_key=component_key(contract, job, args.encoder, profile.to_dict()),
                    profile_sha256=fingerprint(profile.to_dict()), namespace=encoder.namespace, summary=summary,
                    events=bind(cell/'D1_EVENTS.jsonl.gz'), events_expanded=event_digest(cell/'D1_EVENTS.jsonl.gz'),
                    elapsed_seconds=time.perf_counter()-start, process_rss_bytes=process.memory_info().rss,
                    embedding_load_sec=embedding_load_sec if not cells else None,
                    first_scene_includes_native_load=not bool(cells), actual_neural_inference=True,
                    cpu_affinity=process.cpu_affinity(), integrated_N4_cells=0)
                if len(json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8'))>2*1024**2:
                    raise RuntimeError('D1 per-cell summary limit exceeded; preserve failed cell')
                freeze(cell/'RESULT.json', result)
            except BaseException as exc:
                freeze(cell/'FAILED.json', dict(status='FAILED_PRESERVED', error=repr(exc), job=job))
                raise
            cells[job['job_id']] = bind(cell/'RESULT.json')
            supervisor.atomic(destination/'RESULT_INDEX.json', dict(cells=cells, completed=len(cells), total=len(contract['jobs'])))
            supervisor.atomic(state/'panel_progress.json', dict(stage='N4_D1_FULL_BANK_COMPONENTS', encoder=args.encoder,
                completed=contract['encoders'].index(args.encoder)*len(contract['jobs'])+len(cells), total=contract['total']))
        freeze(destination/'RESULT.json', dict(status='COMPLETE', encoder=args.encoder,
            completed=len(cells), total=len(contract['jobs']), cells=cells, cpu_affinity=process.cpu_affinity()))
    finally:
        owner.close()


def run(args):
    import psutil
    process = psutil.Process()
    process.cpu_affinity([14])
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract = verify_admission(args.admission)
    root, state = Path(contract['output']), Path(contract['state'])
    predecessor=require_predecessor(contract)
    require_owner(state, process)
    with supervisor.lock(root/'owner.lock'):
        if (root/'RESULT.json').exists():
            raise ValueError('Preserve prior D1 attempt')
        result = dict(status='RUNNING', owner=dict(pid=process.pid, create_time=process.create_time()),
            child=None, admission=bind(args.admission), predecessor_review=predecessor, completed=0, total=contract['total'], integrated_N4_cells=0)
        supervisor.atomic(root/'RESULT.json', result)
        try:
            for encoder in contract['encoders']:
                resource_guard(root, state)
                require_owner(state, process)
                with (root/(encoder+'.log')).open('x', encoding='utf-8') as log:
                    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                        'extract', '--admission', str(args.admission), '--encoder', encoder], cwd=str(ROOT),
                        stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
                    result.update(encoder=encoder, child=dict(pid=child.pid, create_time=psutil.Process(child.pid).create_time()))
                    supervisor.atomic(root/'RESULT.json', result)
                    code = child.wait()
                if code:
                    raise RuntimeError(encoder+' D1 collection exit '+str(code))
                terminal = load(root/encoder/'RESULT.json')
                if terminal['status'] != 'COMPLETE' or terminal['completed'] != len(contract['jobs']):
                    raise ValueError('Incomplete D1 census')
                result['completed'] += len(contract['jobs'])
            result.update(status='FULL_BANK_COLLECTED_REQUIRES_REVIEW', child=None,
                encoders=[bind(root/e/'RESULT.json') for e in contract['encoders']], finished_utc=supervisor.now())
        except BaseException as exc:
            result.update(status='FAILED_PRESERVED', error=repr(exc), finished_utc=supervisor.now())
            raise
        finally:
            supervisor.atomic(root/'RESULT.json', result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('smoke-review','asr-full-admission','asr-full-review','output','state'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('check','run','extract'):
        p=sub.add_parser(name);p.add_argument('--admission',type=Path,required=True)
        if name=='extract':p.add_argument('--encoder',choices=['E0','E1'],required=True)
    args=parser.parse_args()
    import psutil
    psutil.Process().cpu_affinity([4] if args.command=='extract' else [14])
    if args.command=='check':
        contract=verify_admission(args.admission)
        print(json.dumps(dict(status='VERIFIED_PREPARATION_ONLY',total=contract['total'],predecessor_review_exists=Path(contract['predecessor_review_path']).is_file())))
    else:{'prepare':prepare,'run':run,'extract':extract}[args.command](args)
