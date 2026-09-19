"""Isolated historical control pacing; see README_S6C_PACED_CONTROLS.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
import uuid
import psutil
import s6c_enrollment as E

SCRIPTS=E.SIM/'scripts'
OLD=E.SIM/'reports/S6B/20260909T230840Z'
PAYLOAD=Path('G:/Just_Peachy_S6C')/E.RUN
STAGING=E.SIM/'staging/s6c'/E.RUN
DRIVER_SHA='e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9'
OBSERVER_SHA='9c5d65dbf21dc2feeaec0352943aa7fe506d5c36cd22e310380feb1511c52beb'
SEALED_SHA='2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e'
CONTROLS=('B00','B01')
RESOURCE_LIMITS=dict(c_free_min_bytes=50*2**30,g_free_min_bytes=75*2**30,
    host_available_min_bytes=4*2**30,new_output_cap_bytes=120*2**30,pending_cell_reserve_bytes=512*2**20)
GLOBAL_DEADLINE=datetime.strptime(E.RUN,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)+timedelta(hours=71)

def verified(b):E.verify(b);return E.read(b['path'])
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def dt(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Explicit timezone required')
    return result.astimezone(timezone.utc)
def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def dependencies():
    path=SCRIPTS/'s6b_paced.py'
    if E.bind(path)['sha256']!=DRIVER_SHA:raise ValueError('Original paced native worker changed')
    observer_path=SCRIPTS/'s6b_paced_optional_live_v3.py'
    if E.bind(observer_path)['sha256']!=OBSERVER_SHA:raise ValueError('Original optional-LIVE observer changed')
    observer=load_module(observer_path,'s6c_controls_optional_observer')
    driver,binding=observer.v2.v1.load_driver(path)
    return driver,observer,[binding,E.bind(observer.__file__),E.bind(observer.v2.__file__),E.bind(observer.v2.v1.__file__)]
def strict_bytes(root):
    return sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file()) if Path(root).exists() else 0
def alive(pid,created):
    try:return pid>0 and abs(psutil.Process(pid).create_time()-created)<.001
    except psutil.NoSuchProcess:return False
def safe_namespace(name):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name):raise ValueError('Simple new S6C namespace required')
    return (PAYLOAD/'paced_controls'/name).resolve()
def ensure_output(path):
    path=Path(path).resolve()
    if path.parent!=(PAYLOAD/'paced_controls').resolve() or safe_namespace(path.name)!=path:raise ValueError('Output outside separate S6C paced-control namespace')
    return path

def historical_baseline_authority(sealed):
    old_paced=Path('G:/Just_Peachy_S6B/20260909T230840Z/paced_finalists_epoch2_v4/MANIFEST.json')
    matches=[r for r in sealed['artifacts'] if Path(r['path']).resolve()==old_paced.resolve()]
    if len(matches)!=1:raise ValueError('Sealed historical paced manifest must resolve once')
    paced_binding={k:matches[0][k] for k in ('path','sha256','bytes')}
    paced=verified(paced_binding)
    contract=E.SIM/'reports/S6A/20260909T202250Z/execution_contract.json'
    rows=[r for r in paced['dependencies'] if Path(r['path']).resolve()==contract.resolve()]
    if len(rows)!=1:raise ValueError('Sealed historical B00 execution contract must resolve once')
    E.verify(rows[0])
    return dict(sealed_paced_manifest=paced_binding,execution_contract=rows[0])


def stop_requested(output):
    return any((root/name).exists() for root in (Path(output),E.REPORT) for name in ('STOP_REQUEST','STOP_REQUEST.json'))


def prepare(args):
    driver,observer,dep=dependencies();output=safe_namespace(args.namespace)
    if output.exists():raise ValueError('Fresh output namespace required; do not replace prior finals')
    panel=E.read(args.panel);cases=panel['case_ids']
    if not 12<=len(cases)<=24 or len(set(cases))!=len(cases):raise ValueError('Explicit12..24 unique balanced cases required')
    if args.repetitions!=2:raise ValueError('One full pass plus the four explicitly selected repeat cases required')
    repeat_cases=panel['repeated_case_ids']
    repeat_sets=[dict(repetition=1,case_ids=cases),dict(repetition=2,case_ids=repeat_cases)]
    deadline=dt(args.deadline_utc)
    if deadline>GLOBAL_DEADLINE or deadline<=datetime.now(timezone.utc):raise ValueError('Deadline must preserve one-hour stage closure reserve')
    sealed=E.bind(OLD/'LOCAL_ARTIFACT_INDEX.json')
    if sealed['sha256']!=SEALED_SHA:raise ValueError('Original S6B sealed index differs')
    index=verified(sealed)
    def old(path):
        match=[r for r in index['artifacts'] if Path(r['path']).resolve()==Path(path).resolve()]
        if len(match)!=1:raise ValueError('Historical authority does not resolve once')
        b={k:match[0][k] for k in ('path','sha256','bytes')};dep.append(b);return verified(b)
    spec=old(OLD/'EPOCH2_EXECUTION_MANIFEST.json');driver.check_runtime_versions(spec['runtime_versions'])
    registry=verified(spec['effective_profile_registry']);dep.append(spec['effective_profile_registry'])
    entries={r['profile_id']:r for r in registry['profiles']}
    if set(CONTROLS)-entries.keys() or entries['B00']['recipe_id']!='HISTORICAL_B0' or entries['B01']['recipe_id']!='R0':raise ValueError('Wrong historical controls')
    profile=entries['B01']['profile']
    if profile['profile_id']!='B01' or profile['schema_version']!='edge-research-profile.v2' or profile['tracker']['mode']!='voice':raise ValueError('B01 substituted')
    if profile['input']['gain']!=1 or not profile['input']['already_gained'] or profile['xvf']['mode']!='none':raise ValueError('B01 gain/cue route changed')
    inputs=verified(spec['input_index']);dep.append(spec['input_index']);scene=verified(spec['scene_manifest']);dep.append(spec['scene_manifest'])
    byinput={(r['case_id'],r['stream']):r for r in inputs['rows']};bycase={r['case_id']:r for r in scene['scenes']}
    if set(cases)-bycase.keys():raise ValueError('Panel has unknown canonical case')
    for b in spec['execution_files']:E.verify(b);dep.append(b)
    for asset in spec['assets']:E.verify(asset['binding']);dep.append(asset['binding'])
    b0_authority=historical_baseline_authority(index);dep.extend(b0_authority.values())
    historical=b0_authority['execution_contract']['path']
    baseline=E.SIM/'staging/s6a/20260909T202250Z/baseline_app'
    rows=[r for r in E.read(historical)['snapshot'] if Path(r['snapshot']).suffix=='.py']
    if {Path(r['snapshot']).resolve() for r in rows}!={p.resolve() for p in (baseline/'edge_speech_pipeline').glob('*.py')}:raise ValueError('Exact historical B00 source inventory differs')
    for r in rows:
        b=E.bind(r['snapshot'])
        if b['sha256']!=r['sha256']:raise ValueError('Historical B00 code/default changed')
        dep.append(b)
    selection=[];jobs=[];pcms={}
    for cid in cases:
        s=bycase[cid];utterances=[r for r in s['segments'] if r['kind']=='utterance']
        seen={};returning=False
        for i,utterance in enumerate(utterances):
            person=utterance['speaker_key']
            if person in seen and i-seen[person]>1:returning=True
            seen[person]=i
        selection.append(dict(case_id=cid,family=s['family'],family_id=s['family_id'],
            source_empty=not utterances,includes_subsecond=any((r['source_stop_sample']-r['source_start_sample'])/16000<1 for r in utterances),
            instrumental_music_control=not utterances and any(x.get('category')=='instrumental_music' for x in s['segments']),includes_return=returning,
            scheduled_overlap=bool(s['overlap_intervals']),metadata_only=True,predictor_receives_selection=False))
    if any(not any(row[k] for row in selection) for k in ('source_empty','instrumental_music_control','includes_subsecond','scheduled_overlap','includes_return')):
        raise ValueError('Panel lacks a required empty/music, short, overlap or returning-speaker stratum')
    for repeat_set in repeat_sets:
        repeat=repeat_set['repetition']
        for cid in repeat_set['case_ids']:
            for tap in ('O0','O1'):
                source=byinput[cid,tap];E.verify(source['audio'])
                if source['audio']['path'] not in pcms:pcms[source['audio']['path']]=driver.pcm16_hash(source['audio']['path'])
                pcm=pcms[source['audio']['path']]
                if pcm['sha256']!=source['audio_pcm_sha256'] or pcm['duration_sec']!=source['duration_sec']:raise ValueError('Once-gained indexed input differs')
                dep.append(source['audio'])
                for pid in CONTROLS if repeat%2 else reversed(CONTROLS):
                    job=dict(profile_id=pid,recipe_id=entries[pid]['recipe_id'],case_id=cid,stream=tap,repetition=repeat,
                        profile=None if pid=='B00' else profile,app_path=str(baseline if pid=='B00' else Path(spec['root'])/'app'),
                        input=source['audio'],input_pcm_sha256=pcm['sha256'],duration_sec=pcm['duration_sec'],telemetry=None,
                        assets=spec['assets'],epoch='s6c_historical_controls_v1',mode='EXACT_IMMUTABLE_B0_DEFAULT' if pid=='B00' else 'EXACT_ORIGINAL_S6B_B01_PROFILE',
                        gain_context=source['historical_gain_applied_once'],source_sample_rate=16000,realtime=True,
                        clip_policy='whole indexed once-gained input, no cropping or regeneration',original_config_threads_retained=True,inner_numeric_pools=1)
                    job['job_id']=f'{pid}_{cid}_{tap}_R{repeat}';job['job_key']=digest(job);jobs.append(job)
    for p in (__file__,Path(__file__).with_name('README_S6C_PACED_CONTROLS.md'),args.panel):dep.append(E.bind(p))
    plan=dict(schema='s6c-historical-paced-controls.v1',created_utc=E.utc(),driver=E.bind(SCRIPTS/'s6b_paced.py'),
        coordinator=E.bind(__file__),dependencies=list({r['path']:r for r in dep}.values()),source_sealed_index=sealed,
        historical_epoch=E.bind(OLD/'EPOCH2_EXECUTION_MANIFEST.json'),historical_baseline_authority=b0_authority,runtime_versions=spec['runtime_versions'],
        profiles=list(CONTROLS),cases=cases,streams=['O0','O1'],repetitions=args.repetitions,repeat_case_sets=repeat_sets,selection=selection,
        panel=E.bind(args.panel),jobs=jobs,worker_limit=1,payload_root=str(PAYLOAD),output_root=str(output),
        total_audio_sec=sum(j['duration_sec'] for j in jobs),deadline_utc=deadline.isoformat(),max_wall_sec=args.max_wall_sec,
        timeout_sec=args.timeout,resource_limits=dict(RESOURCE_LIMITS),method_order='B00/B01 on odd repetitions; B01/B00 on even; same case/tap order',
        scope='New S6C paced native sessions through unchanged historical workers, not reuse of S6B four-case runtime measurements',
        defaults='B00 immutable original config defaults; B01 exact old profile. Native thread settings retained; numeric pools1 as original paced driver.',
        timing='Native event emission and whole-source pacing; no exact phonetic, GUI, DSP or CM5 latency claim',
        resume='Complete own-namespace cells may be verified and skipped; any partial launch requires separate explicit recovery, never historical35-cell resume helper')
    validate_plan_structure(plan)
    plan['manifest_key']=digest(plan);output.mkdir(parents=True);E.save(output/'MANIFEST.json',plan)
    E.save(E.REPORT/'paced_controls'/args.namespace/'PREPARATION.json',dict(status='PREPARED_NO_MODELS_STARTED',manifest=E.bind(output/'MANIFEST.json'),jobs=len(jobs),source_minutes=plan['total_audio_sec']/60))
    return dict(status='PREPARED_NO_MODELS_STARTED',manifest=E.bind(output/'MANIFEST.json'),jobs=len(jobs),source_minutes=plan['total_audio_sec']/60)

def validate_job_semantics(j,source,entries,spec,baseline):
    pid=j['profile_id'];expected_profile=None if pid=='B00' else entries['B01']['profile']
    expected_app=baseline if pid=='B00' else Path(spec['root'])/'app'
    if j['profile']!=expected_profile or j['recipe_id']!=entries[pid]['recipe_id'] or Path(j['app_path']).resolve()!=expected_app.resolve():raise ValueError('Historical control semantics substituted')
    if j['assets']!=spec['assets'] or j['telemetry'] is not None or j['input']!=source['audio'] or j['input_pcm_sha256']!=source['audio_pcm_sha256']:
        raise ValueError('Historical asset/input/cue binding substituted')
    if j['duration_sec']!=source['duration_sec'] or j['gain_context']!=source['historical_gain_applied_once'] or j['source_sample_rate']!=16000 or j['realtime'] is not True:
        raise ValueError('Duration/gain/pacing changed')


def validate_plan_structure(plan):
    if plan['profiles']!=list(CONTROLS) or plan['streams']!=['O0','O1'] or not 12<=len(plan['cases'])<=24 or plan['repetitions']!=2:raise ValueError('Required controls/panel/taps/repeats absent')
    if len(set(plan['cases']))!=len(plan['cases']) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',c) for c in plan['cases']):raise ValueError('Unsafe or duplicate panel case')
    sets=plan['repeat_case_sets']
    if len(sets)!=2 or sets[0]!={'repetition':1,'case_ids':plan['cases']} or sets[1]['repetition']!=2:raise ValueError('Explicit per-repeat panel differs')
    repeated=sets[1]['case_ids']
    if len(repeated)!=4 or len(set(repeated))!=4 or not set(repeated)<=set(plan['cases']):raise ValueError('Exactly four unique panel repeat cases required')
    expected=[(p,c,t,s['repetition']) for s in sets for c in s['case_ids'] for t in ('O0','O1') for p in (CONTROLS if s['repetition']%2 else tuple(reversed(CONTROLS)))]
    actual=[(j['profile_id'],j['case_id'],j['stream'],j['repetition']) for j in plan['jobs']]
    if actual!=expected:raise ValueError('Exact paced control grid/order mismatch')
    if any(j['job_id']!=f"{j['profile_id']}_{j['case_id']}_{j['stream']}_R{j['repetition']}" for j in plan['jobs']):raise ValueError('Unsafe or changed job identity')
    if plan['worker_limit']!=1 or plan['resource_limits']!=RESOURCE_LIMITS or Path(plan['payload_root']).resolve()!=PAYLOAD.resolve():raise ValueError('Fixed quiet/resource budget changed')
    if not 60<=plan['timeout_sec']<=600 or not 600<=plan['max_wall_sec']<=14400 or dt(plan['deadline_utc'])>GLOBAL_DEADLINE:raise ValueError('Manifest time bound changed')
    if plan['total_audio_sec']!=sum(j['duration_sec'] for j in plan['jobs']):raise ValueError('Total source duration differs')


def admit_manifest(path):
    plan=E.read(path);output=ensure_output(plan['output_root'])
    if Path(path).resolve()!=output/'MANIFEST.json':raise ValueError('Manifest/output location mismatch')
    copy=dict(plan);key=copy.pop('manifest_key')
    if digest(copy)!=key or plan['schema']!='s6c-historical-paced-controls.v1':raise ValueError('Manifest digest/schema mismatch')
    validate_plan_structure(plan)
    for b in plan['dependencies']:E.verify(b)
    if plan['coordinator']!=E.bind(__file__):raise ValueError('New coordinator differs from plan')
    if plan['driver']!=E.bind(SCRIPTS/'s6b_paced.py') or plan['driver']['sha256']!=DRIVER_SHA:raise ValueError('Historical worker substituted')
    authority=E.bind(OLD/'LOCAL_ARTIFACT_INDEX.json')
    if authority['sha256']!=SEALED_SHA or plan['source_sealed_index']!=authority:raise ValueError('Historical authority substituted')
    sealed=verified(authority)
    b0_authority=historical_baseline_authority(sealed)
    if plan['historical_baseline_authority']!=b0_authority:raise ValueError('Historical B00 sealed authority changed')
    old_binding=next(r for r in sealed['artifacts'] if Path(r['path']).resolve()==(OLD/'EPOCH2_EXECUTION_MANIFEST.json').resolve())
    E.verify(old_binding);spec=E.read(old_binding['path'])
    if plan['historical_epoch']!=E.bind(old_binding['path']) or plan['runtime_versions']!=spec['runtime_versions']:raise ValueError('Historical epoch/runtime differs')
    registry=verified(spec['effective_profile_registry']);entries={r['profile_id']:r for r in registry['profiles']}
    inputs={(r['case_id'],r['stream']):r for r in verified(spec['input_index'])['rows']}
    panel=verified(plan['panel'])
    if panel['case_ids']!=plan['cases'] or panel['repeated_case_ids']!=plan['repeat_case_sets'][1]['case_ids']:raise ValueError('Panel or explicit repeat cases differ')
    for b in spec['execution_files']:E.verify(b)
    for asset in spec['assets']:E.verify(asset['binding'])
    baseline=E.SIM/'staging/s6a/20260909T202250Z/baseline_app'
    contract=E.SIM/'reports/S6A/20260909T202250Z/execution_contract.json'
    bound_contract=[b for b in plan['dependencies'] if Path(b['path']).resolve()==contract.resolve()]
    if len(bound_contract)!=1:raise ValueError('Historical B00 contract missing')
    snapshot=[r for r in verified(bound_contract[0])['snapshot'] if Path(r['snapshot']).suffix=='.py']
    if {Path(r['snapshot']).resolve() for r in snapshot}!={p.resolve() for p in (baseline/'edge_speech_pipeline').glob('*.py')}:raise ValueError('Historical B00 source inventory changed')
    for row in snapshot:
        if E.bind(row['snapshot'])['sha256']!=row['sha256']:raise ValueError('B00 source/default changed')
    for j in plan['jobs']:
        copy=dict(j);key=copy.pop('job_key')
        if digest(copy)!=key:raise ValueError('Job digest mismatch')
        validate_job_semantics(j,inputs[j['case_id'],j['stream']],entries,spec,baseline)
    return plan

def quiet_processes(excluded=()):
    found={};skip=set(excluded)|{os.getpid()};needle=str(PAYLOAD).lower().replace('/','\\')
    for p in psutil.process_iter(['pid','cmdline','create_time']):
        if p.pid in skip:continue
        command=' '.join(p.info['cmdline'] or []).lower().replace('/','\\')
        if '--mode worker' in command or '--worker' in command:
            if any(x in command for x in ('s6b_','s6c_',needle)):
                found[p.pid]=dict(pid=p.pid,creation_time=p.info['create_time'],source='explicit study worker command')
    for path in E.REPORT.glob('**/workers/*.json'):
        try:row=E.read(path)
        except (OSError,json.JSONDecodeError):raise RuntimeError('Cannot establish quiet worker-registry state')
        pid=row.get('pid',-1);created=row.get('creation_time',-1)
        if pid not in skip and alive(pid,created):found[pid]=dict(pid=pid,creation_time=created,source=str(path))
    return list(found.values())

def validate_resource_sample(sample,limits,pending_cell=False):
    reserve=limits['pending_cell_reserve_bytes'] if pending_cell else 0
    for key,minimum in [('c_free_bytes','c_free_min_bytes'),('g_free_bytes','g_free_min_bytes'),('available_ram_bytes','host_available_min_bytes')]:
        extra=reserve if key!='available_ram_bytes' else 0
        if sample[key]<limits[minimum]+extra:raise RuntimeError('Storage/RAM reserve violated: '+key)
    if pending_cell and 'new_S6C_output_bytes' not in sample:raise ValueError('Pending cell requires global output accounting')
    if 'new_S6C_output_bytes' in sample and sample['new_S6C_output_bytes']+reserve>limits['new_output_cap_bytes']:raise RuntimeError('Global S6C120GiB output cap/headroom exceeded')


def resources(plan,excluded=(),count_payload=False,pending_cell=False):
    live=quiet_processes(excluded)
    if live:raise RuntimeError('Quiet period unavailable; other study workers are live: '+json.dumps(live))
    sample=dict(c_free_bytes=shutil.disk_usage('C:/').free,g_free_bytes=shutil.disk_usage('G:/').free,available_ram_bytes=psutil.virtual_memory().available)
    limits=plan['resource_limits']
    if count_payload:
        sample['new_S6C_output_bytes']=strict_bytes(PAYLOAD)+strict_bytes(E.REPORT)+strict_bytes(STAGING)
    validate_resource_sample(sample,limits,pending_cell)
    sample['pending_cell_reserve_bytes']=limits['pending_cell_reserve_bytes'] if pending_cell else 0
    return sample

def sample_tree(process,driver):
    try:members=[process]+process.children(recursive=True)
    except psutil.Error:
        return dict(processes=[],tree_complete=False,descendant_enumeration_complete=False,unreadable_pids=[process.pid],
            rss_sum_upper_bound_bytes=None,private_resident_uss_sum_bytes=None,windows_private_commit_sum_bytes=None,pss_sum_bytes=None)
    rows=[];unreadable=[]
    for p in members:
        try:
            memory=p.memory_full_info();cpu=p.cpu_times();io=p.io_counters()
            rows.append(dict(pid=p.pid,creation_time=p.create_time(),name=p.name(),rss_bytes=memory.rss,
                private_resident_uss_bytes=getattr(memory,'uss',None),windows_private_commit_bytes=getattr(memory,'private',None),pss_bytes=getattr(memory,'pss',None),
                threads=p.num_threads(),cpu_seconds=cpu.user+cpu.system,io_read_bytes=io.read_bytes,io_write_bytes=io.write_bytes))
        except psutil.Error:unreadable.append(p.pid)
    def total(key):return sum(r[key] for r in rows) if rows and not unreadable and all(r[key] is not None for r in rows) else None
    return dict(processes=rows,unreadable_pids=unreadable,tree_complete=not unreadable,descendant_enumeration_complete=True,
        rss_sum_upper_bound_bytes=total('rss_bytes'),private_resident_uss_sum_bytes=total('private_resident_uss_bytes'),
        windows_private_commit_sum_bytes=total('windows_private_commit_bytes'),pss_sum_bytes=total('pss_bytes'),
        system_available_ram_bytes=psutil.virtual_memory().available,
        enumeration_scope='Stored sampler flags and observed PID tree; not guaranteed full OS process enumeration between samples')

def run(args):
    plan=admit_manifest(args.manifest);driver,observer,_=dependencies();driver.check_runtime_versions(plan['runtime_versions'])
    output=ensure_output(plan['output_root']);admission=E.read(args.quiet_admission)
    if admission.get('status')!='AUTHORIZED_FOR_QUIET_PACED' or admission.get('manifest_sha256')!=E.bind(args.manifest)['sha256'] or admission.get('all_other_model_hil_work_stopped') is not True:
        raise ValueError('Explicit source-bound quiet-period admission required')
    if dt(admission['expires_utc'])<=datetime.now(timezone.utc):raise ValueError('Quiet-period admission expired')
    deadline=min(dt(plan['deadline_utc']),dt(admission['expires_utc']),GLOBAL_DEADLINE)
    resources(plan,count_payload=True)
    lock=E.REPORT/'PACED_QUIET_OWNER.json';me=psutil.Process()
    if lock.exists():
        prior=E.read(lock)
        if alive(prior['pid'],prior['creation_time']):raise ValueError('Another quiet-period owner is active')
        raise ValueError('Preserved quiet owner requires explicit resolution; do not replace')
    with lock.open('x',encoding='utf-8') as f:json.dump(dict(pid=me.pid,creation_time=me.create_time(),manifest=E.bind(args.manifest)),f)
    invocation=output/'invocations'/uuid.uuid4().hex;invocation.mkdir(parents=True)
    started=time.monotonic();status='RUNNING';error=None;complete=[]
    with (invocation/'OBSERVER_EVENTS.jsonl').open('x',encoding='utf-8') as handle:
        def emit(event):handle.write(json.dumps(event,allow_nan=False)+'\n');handle.flush();os.fsync(handle.fileno())
        paths=[output/'jobs'/j['job_id']/'LIVE.json' for j in plan['jobs']]
        reader=observer.OptionalLiveReader(driver.read,paths,invocation/'rejected_snapshots',emit)
        try:
            E.save(invocation/'LAUNCH.json',dict(status='STARTED',pid=me.pid,creation_time=me.create_time(),manifest=E.bind(args.manifest),quiet_admission=E.bind(args.quiet_admission),
                coordinator=E.bind(__file__),observer=E.bind(observer.__file__),native_driver=plan['driver']))
            for job in plan['jobs']:
                if stop_requested(output):status='PARTIAL_STOP_REQUEST';break
                if datetime.now(timezone.utc)+timedelta(seconds=plan['timeout_sec']+75)>=deadline or time.monotonic()-started+plan['timeout_sec']+75>plan['max_wall_sec']:
                    status='PARTIAL_TIME_RESERVE';break
                directory=output/'jobs'/job['job_id'];directory.mkdir(parents=True,exist_ok=True)
                done=directory/'COMPLETE.json'
                if done.exists():
                    old=E.read(done)
                    if old['status']!='COMPLETE' or old['job_key']!=job['job_key'] or not old['all_owned_processes_closed']:raise ValueError('Wrong completed cell')
                    for b in old['artifacts']:E.verify(b)
                    if any(alive(x['pid'],x['creation_time']) for x in old['owned_processes']):raise ValueError('Completed native process is live')
                    complete.append(job['job_id']);continue
                if (directory/'LAUNCH.json').exists():raise ValueError('Partial native launch preserved; separate reviewed recovery required')
                resources(plan,count_payload=True,pending_cell=True);E.verify(plan['driver']);E.verify(job['input'])
                argv=[sys.executable,plan['driver']['path'],'--mode','worker','--manifest',str(args.manifest),'--job-id',job['job_id'],'--timeout',str(plan['timeout_sec'])]
                owned={};child=None;t0=time.monotonic();lastbeat=0.
                try:
                    with (directory/'stdout.log').open('x',encoding='utf-8') as log:
                        child=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                        process=psutil.Process(child.pid);owned[child.pid]=process.create_time()
                        E.save(directory/'LAUNCH.json',dict(pid=child.pid,creation_time=owned[child.pid],argv=argv,job_key=job['job_key'],created_utc=E.utc()))
                        with (directory/'PROCESS_SAMPLES.jsonl').open('x',encoding='utf-8') as trajectory:
                            while child.poll() is None:
                                tree=sample_tree(process,driver)
                                for p in tree['processes']:owned[p['pid']]=p['creation_time']
                                live=reader(directory/'LIVE.json') if (directory/'LIVE.json').exists() else None
                                elapsed=time.monotonic()-t0
                                row=dict(elapsed_sec=elapsed,created_utc=E.utc(),tree=tree,live=live,coordinator_rss_bytes=me.memory_info().rss)
                                trajectory.write(json.dumps(row,allow_nan=False)+'\n');trajectory.flush()
                                if elapsed-lastbeat>=20:
                                    sample=resources(plan,owned,count_payload=True)
                                    driver.save(output/'HEARTBEAT.json',dict(phase='S6C_HISTORICAL_PACED',job_id=job['job_id'],elapsed_sec=elapsed,completed=len(complete),requested=len(plan['jobs']),resources=sample,created_utc=E.utc()))
                                    print(json.dumps(dict(job_id=job['job_id'],completed=len(complete),requested=len(plan['jobs']),elapsed_sec=elapsed)),flush=True);lastbeat=elapsed
                                if (output/'STOP_NOW').exists() or datetime.now(timezone.utc)>=deadline or elapsed>plan['timeout_sec']+75:raise InterruptedError('Owned paced stop/time boundary')
                                time.sleep(.5)
                    if child.returncode!=0:raise RuntimeError('Historical native worker failed; preserve stdout and outputs')
                    result=reader(directory/'WORKER_RESULT.json')
                    if result['status']!='COMPLETE' or result['job_key']!=job['job_key'] or not result['native_pcm_exact'] or not result['asr_cursor_complete']:
                        raise ValueError('Native closure/source cursor failure')
                    if result['journal']['sha256']!=job['input_pcm_sha256'] or result['journal']['bytes']!=round(job['duration_sec']*16000)*2:raise ValueError('Actual full PCM mismatch')
                    if any(alive(p,c) for p,c in owned.items()):raise ValueError('Owned descendant remains live')
                    resources(plan,count_payload=True)
                    artifacts=[E.bind(directory/'WORKER_RESULT.json'),E.bind(directory/'PROCESS_SAMPLES.jsonl'),result['events'],result['journal'],result['display_events'],result['summary_binding']]
                    for b in artifacts:E.verify(b)
                    E.save(done,dict(status='COMPLETE',job_key=job['job_key'],worker=result,artifacts=artifacts,all_owned_processes_closed=True,
                        owned_processes=[dict(pid=p,creation_time=c) for p,c in owned.items()],created_utc=E.utc()))
                    complete.append(job['job_id'])
                except BaseException:
                    driver.stop_owned(owned)
                    if child is not None:child.wait(timeout=15)
                    E.save(directory/'FAILURE.json',dict(status='FAILED',job_key=job['job_key'],traceback=traceback.format_exc(),
                        owned_processes=[dict(pid=p,creation_time=c,alive=alive(p,c)) for p,c in owned.items()]))
                    raise
            else:status='COMPLETE'
        except BaseException:
            status='FAILED';error=traceback.format_exc();raise
        finally:
            handle.flush();os.fsync(handle.fileno())
            E.save(invocation/'COMPLETION.json',dict(status=status,completed=len(complete),requested=len(plan['jobs']),stats=reader.snapshot(),
                error=error,events=E.bind(invocation/'OBSERVER_EVENTS.jsonl'),manifest=E.bind(args.manifest),created_utc=E.utc()))
            lock.rename(invocation/'QUIET_OWNER_CLOSED.json')
    return dict(status=status,completed=len(complete),requested=len(plan['jobs']),invocation=str(invocation))

def checks():
    assert safe_namespace('controls_v1').parent==(PAYLOAD/'paced_controls').resolve()
    for bad in ('../old','a/b','C:',''):
        try:safe_namespace(bad)
        except ValueError:pass
        else:raise AssertionError('Unsafe namespace admitted')
    try:ensure_output(Path('G:/Just_Peachy_S6B/old'))
    except ValueError:pass
    else:raise AssertionError('Old output admitted')
    try:dt('2026-09-10T12:00:00')
    except ValueError:pass
    else:raise AssertionError('Ambiguous timezone admitted')
    driver,observer,bindings=dependencies()
    assert bindings[0]['sha256']==DRIVER_SHA and callable(observer.OptionalLiveReader)
    assert len({(p,c,t,r) for p in CONTROLS for r,cs in ((1,range(16)),(2,range(4))) for c in cs for t in ('O0','O1')})==80
    spec=E.read(OLD/'EPOCH2_EXECUTION_MANIFEST.json');registry=verified(spec['effective_profile_registry']);entries={r['profile_id']:r for r in registry['profiles']}
    source=verified(spec['input_index'])['rows'][0];baseline=E.SIM/'staging/s6a/20260909T202250Z/baseline_app'
    job=dict(profile_id='B00',profile=None,recipe_id=entries['B00']['recipe_id'],app_path=str(baseline),assets=spec['assets'],telemetry=None,
        input=source['audio'],input_pcm_sha256=source['audio_pcm_sha256'],duration_sec=source['duration_sec'],gain_context=source['historical_gain_applied_once'],source_sample_rate=16000,realtime=True)
    validate_job_semantics(job,source,entries,spec,baseline)
    from copy import deepcopy
    failures=0
    for key,value in [('profile',entries['B01']['profile']),('recipe_id','R0'),('app_path',str(Path(spec['root'])/'app')),('telemetry',{}),
                      ('assets',[]),('input',{}),('input_pcm_sha256','changed'),('duration_sec',1),('gain_context',9),('source_sample_rate',48000),('realtime',False)]:
        bad=deepcopy(job);bad[key]=value
        try:validate_job_semantics(bad,source,entries,spec,baseline)
        except ValueError:failures+=1
        else:raise AssertionError('Altered historical dependency admitted: '+key)
    job.update(profile_id='B01',profile=entries['B01']['profile'],recipe_id='R0',app_path=str(Path(spec['root'])/'app'))
    validate_job_semantics(job,source,entries,spec,baseline)
    bad=deepcopy(job);bad['profile']['tracker']['max_tracks']=256
    try:validate_job_semantics(bad,source,entries,spec,baseline)
    except ValueError:failures+=1
    else:raise AssertionError('Changed B01 tracker admitted')
    cases=[f'CASE_{i:02d}' for i in range(12)]
    sets=[dict(repetition=1,case_ids=cases),dict(repetition=2,case_ids=cases[:4])]
    jobs=[dict(profile_id=p,case_id=c,stream=t,repetition=s['repetition'],duration_sec=45,job_id=f"{p}_{c}_{t}_R{s['repetition']}")
        for s in sets for c in s['case_ids'] for t in ('O0','O1') for p in (CONTROLS if s['repetition']%2 else tuple(reversed(CONTROLS)))]
    structure=dict(profiles=list(CONTROLS),streams=['O0','O1'],cases=cases,repetitions=2,jobs=jobs,
        repeat_case_sets=sets,
        worker_limit=1,resource_limits=dict(RESOURCE_LIMITS),payload_root=str(PAYLOAD),timeout_sec=300,max_wall_sec=14400,
        deadline_utc=GLOBAL_DEADLINE.isoformat(),total_audio_sec=2880)
    validate_plan_structure(structure);failures+=1
    mutations=[('worker_limit',2),('payload_root',str(OLD)),('resource_limits',RESOURCE_LIMITS|{'g_free_min_bytes':1}),
        ('total_audio_sec',1),('timeout_sec',601),('max_wall_sec',14401),('cases',cases[:-1]+[cases[0]]),
        ('jobs',jobs[:-1]),('jobs',list(reversed(jobs))),('jobs',[jobs[0]|{'job_id':'../outside'}]+jobs[1:]),
        ('deadline_utc',(GLOBAL_DEADLINE+timedelta(seconds=1)).isoformat()),
        ('repeat_case_sets',[sets[0],dict(repetition=2,case_ids=cases)]),
        ('repeat_case_sets',[sets[0],dict(repetition=2,case_ids=cases[:3]+['outside'])]),
        ('repeat_case_sets',[sets[0],dict(repetition=2,case_ids=cases[:3]+[cases[0]])])]
    for key,value in mutations:
        bad=deepcopy(structure);bad[key]=value
        try:validate_plan_structure(bad)
        except ValueError:failures+=1
        else:raise AssertionError('Changed resource/grid bound admitted: '+key)
    assert callable(shutil.disk_usage)
    import tempfile
    from unittest.mock import patch
    for exception,closed in [(psutil.NoSuchProcess(42),True),(psutil.AccessDenied(42),False)]:
        with patch.object(psutil,'Process',side_effect=exception):
            try:value=alive(42,1)
            except psutil.AccessDenied:
                assert not closed
            else:assert closed and value is False
        failures+=1
    sample=dict(c_free_bytes=51*2**30,g_free_bytes=76*2**30,available_ram_bytes=4*2**30,new_S6C_output_bytes=119*2**30)
    validate_resource_sample(sample,RESOURCE_LIMITS,True);failures+=1
    bad_samples=[sample|{'c_free_bytes':50*2**30},sample|{'g_free_bytes':75*2**30},
        sample|{'new_S6C_output_bytes':120*2**30-1},sample|{'available_ram_bytes':4*2**30-1}]
    for bad in bad_samples:
        try:validate_resource_sample(bad,RESOURCE_LIMITS,True)
        except RuntimeError:failures+=1
        else:raise AssertionError('Pending cell without headroom admitted')
    try:validate_resource_sample(sample|{'new_S6C_output_bytes':120*2**30+1},RESOURCE_LIMITS,False)
    except RuntimeError:failures+=1
    else:raise AssertionError('Post-cell output cap violation admitted')
    with tempfile.TemporaryDirectory(prefix='paced_stop_checks_',dir=STAGING) as temporary:
        temp=Path(temporary).resolve();assert temp.parent==STAGING.resolve()
        output=temp/'output';report=temp/'report';output.mkdir();report.mkdir()
        with patch.object(E,'REPORT',report):
            assert not stop_requested(output);failures+=1
            for directory in (output,report):
                for name in ('STOP_REQUEST','STOP_REQUEST.json'):
                    sentinel=directory/name;sentinel.write_text('{}');assert stop_requested(output);sentinel.unlink();failures+=1
    sealed=E.read(OLD/'LOCAL_ARTIFACT_INDEX.json');authority=historical_baseline_authority(sealed)
    assert authority['execution_contract']['sha256']=='4be1e8cdd342124c36716e7267f5e28ae5f3d0655c1685696af56cab8057148a';failures+=1
    bad=deepcopy(sealed)
    for row in bad['artifacts']:
        if Path(row['path']).resolve()==Path(authority['sealed_paced_manifest']['path']).resolve():row['sha256']='0'*64
    try:historical_baseline_authority(bad)
    except ValueError:failures+=1
    else:raise AssertionError('Changed sealed B00 authority admitted')
    result=dict(status='PASS',checks=12+failures,model_calls=0,native_worker_unchanged=True,bindings=bindings,source=E.bind(__file__),readme=E.bind(Path(__file__).with_name('README_S6C_PACED_CONTROLS.md')))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('prepare','run','checks'))
    p.add_argument('--panel',type=Path);p.add_argument('--namespace');p.add_argument('--deadline-utc');p.add_argument('--repetitions',type=int,default=2)
    p.add_argument('--max-wall-sec',type=float,default=14400);p.add_argument('--timeout',type=float,default=300)
    p.add_argument('--manifest',type=Path);p.add_argument('--quiet-admission',type=Path);a=p.parse_args()
    if not 60<=a.timeout<=600 or not 600<=a.max_wall_sec<=14400:p.error('Bounded timeout60..600 and wall600..14400 required')
    if a.action=='prepare' and any(x is None for x in (a.panel,a.namespace,a.deadline_utc)):p.error('prepare requires panel, namespace and deadline')
    if a.action=='run' and (a.manifest is None or a.quiet_admission is None):p.error('run requires manifest and quiet-admission')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
    print(json.dumps({'prepare':lambda:prepare(a),'run':lambda:run(a),'checks':checks}[a.action](),indent=2))
