"""Exploratory arrival sentinel; see README_S6C_PACED_ARRIVAL_SENTINEL_FAST_V2.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
import wave
import psutil

_helper=Path(__file__).with_name('s6c_long_native_epoch4_fast_v2.py')
if hashlib.sha256(_helper.read_bytes()).hexdigest()!='079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67':raise ValueError('Reviewed long admission utilities changed')
import s6c_long_native_epoch4_fast_v2 as L
if Path(L.__file__).resolve()!=_helper.resolve():raise ValueError('Wrong long utility import')
REPORT=L.REPORT;PAYLOAD=L.PAYLOAD
PANEL=REPORT/'design/PACED_ARRIVAL_SENTINEL_SELECTION_V1.json'
PANEL_SHA='13490a4773b5be366b6a7d7e47013f8cd3ab9a8d34a3f9d99f33c539a24f2d4b'
SCHEMA='s6c-paced-arrival-sentinel.v1'
HELD=Path(__file__).with_name('s6c_paced_epoch4_fast_v2.py')
if hashlib.sha256(HELD.read_bytes()).hexdigest()!='a8776724003fa2a642575892327b7c3e88eaddf29606881b302b05157c12b270':raise ValueError('Held canonical adapter changed')
CELL_RESERVE=512*2**20
MAX_RUN_SEC=8*3600
GATE_CASES=['S45_02_10','S45_03_03','S45_04_07','S45_05_05','S45_06_19','S45_12_11']


def source_bindings():
    names=('s6c_paced_arrival_sentinel_fast_v2.py','README_S6C_PACED_ARRIVAL_SENTINEL_FAST_V2.md','s6c_paced_epoch4_fast_v2.py','README_S6C_PACED_EPOCH4_FAST_V2.md','s6c_long_native_epoch4_fast_v2.py','README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md','s6c_long_session.py','README_S6C_LONG_SESSION.md','s6c_native_prefix.py','s6c_historical_fast_observer_v1.py','README_S6C_HISTORICAL_FAST_OBSERVER_V1.md')
    return [L.bind(Path(__file__).with_name(n)) for n in names]


def load_native():
    for name,sha in L.PINS.items():
        if L.bind(Path(__file__).with_name(name))['sha256']!=sha:raise ValueError('Pinned native dependency changed: '+name)
    overlay=importlib.import_module('s6c_orchestrator_scan_v3');eb,spec,common,execution=overlay.load_native('epoch4')
    driver=importlib.import_module('s6c_long_session');prefix=importlib.import_module('s6c_native_prefix')
    if Path(driver.__file__).resolve()!=Path(__file__).with_name('s6c_long_session.py').resolve() or Path(prefix.__file__).resolve()!=Path(__file__).with_name('s6c_native_prefix.py').resolve():raise ValueError('Wrong original native/prefix helper')
    if driver.bind is not common.bind or prefix.bind is not common.bind or driver.load_epoch is not prefix.load_epoch:raise ValueError('Native/prefix did not use the exact frozen common module')
    L.validate_protected_driver(driver)
    L.install_observer_scanner(common)
    return driver,common,spec,eb


def namespace_roots(namespace):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',namespace) or not namespace.endswith('_fast_v2'):raise ValueError('Simple fresh sentinel namespace required')
    return REPORT/'paced_arrival_sentinel'/namespace,PAYLOAD/'paced_arrival_sentinel'/namespace


def panel():
    value,b=L.read_bound(PANEL)
    if b['sha256']!=PANEL_SHA:raise ValueError('Exact exploratory sentinel selection required')
    selected_panel(value,'arrival_sentinel',value['candidates'])
    return value,b


def selected_panel(value,mode,candidates):
    if mode!='arrival_sentinel' or candidates!=['C088','C105'] or value['candidates']!=candidates:raise ValueError('Exact C088/C105 sentinel pair required')
    if value['schema']!='s6c-paced-arrival-sentinel-selection.v1' or value['case_ids']!=['S45_08_07'] or value['streams']!=['O0','O1'] or value['repetitions']!=[1,2,3] or value['expected_cells']!=12:raise ValueError('Exact one-case/two-tap/three-repeat sentinel selection required')
    if value['gallery_condition']!='FIXED_ROTATION_A' or value['enrollment_tier']!=15 or value['cue_conditions']!={'C088':'CUES_OFF','C105':'REAL_ALIGNED_CUES'}:raise ValueError('Sentinel roster/tier/cue condition differs')
    if value['all_repetitions_retained'] is not True or value['main16_plus4_and_gate6_unchanged'] is not True:raise ValueError('Sentinel retention/scope differs')
    return dict(case_ids=['S45_08_07'],repeated_case_ids=['S45_08_07'])


def validate_source_rows(pair):
    if set(pair)!= {'O0','O1'}:raise ValueError('Complete canonical pair required')
    first=pair['O0'];frames=round(first['duration_sec']*16000)
    if frames<=0 or frames/16000!=first['duration_sec']:raise ValueError('Exact integer source frames required')
    for tap,row in pair.items():
        if row['stream']!=tap or row['case_id']!=first['case_id'] or row['duration_sec']!=first['duration_sec'] or row['input_gain']!=1. or row['already_gained'] is not True:raise ValueError('Canonical pair identity/duration/unity adapter differs')
        gain=1.4125375446227544 if tap=='O0' else 1.
        if row['historical_gain_applied_once']!=gain:raise ValueError('Frozen gain history changed')
    if pair['O0']['telemetry']!=pair['O1']['telemetry']:raise ValueError('Paired source-clock telemetry differs')
    return frames


def verify_pcm(row):
    L.verify(row['audio']);h=hashlib.sha256()
    with wave.open(row['audio']['path'],'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getcomptype())!=(1,2,16000,'NONE') or f.getnframes()/16000!=row['duration_sec']:raise ValueError('Exact full native PCM16 view required')
        for raw in iter(lambda:f.readframes(65536),b''):h.update(raw)
    if h.hexdigest()!=row['audio_pcm_sha256']:raise ValueError('Canonical complete PCM differs')


def source_record(pair,input_binding):
    frames=validate_source_rows(pair)
    return dict(schema='s6c-canonical-single-scene-pair.v1',source_kind='CANONICAL_SINGLE_SCENE_PAIR',case_id=pair['O0']['case_id'],input_index=input_binding,
        audio={k:v['audio'] for k,v in pair.items()},pcm_sha256={k:v['audio_pcm_sha256'] for k,v in pair.items()},telemetry=pair['O0']['telemetry'],
        duration_sec=frames/16000,duration_samples=frames,source_offset_samples=0,inserted_gap_samples=0,no_new_gain=True,adapter_gain=1.,
        historical_gain={k:v['historical_gain_applied_once'] for k,v in pair.items()},
        scope='One complete unchanged processed capture pair at original sample zero; no new silence, trim, shift, gain, concatenation or audio copy. This is not the long-session composition.')


def candidate_routes(spec,candidates):
    if not candidates or len(candidates)!=len(set(candidates)):raise ValueError('Explicit distinct selected candidate IDs required')
    result={}
    for candidate in candidates:
        for tap in ('O0','O1'):
            rows=[r for r in spec['profiles'] if r['candidate_id']==candidate and r['asr_tap']==tap]
            if len(rows)!=1 or rows[0]['identity_tap'] not in ('O0','O1'):raise ValueError('Exactly one registered route per candidate and ASR tap required')
            if rows[0]['gallery_condition'] not in ('NONE','FIXED_ROTATION_A','FIXED_ROTATION_B') or rows[0]['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):raise ValueError('Paced adapter supports exact fixed A/B/empty and real/off cues only')
            result[candidate,tap]=rows[0]
    if candidates!=['C088','C105']:raise ValueError('No substitute sentinel candidate')
    for tap in ('O0','O1'):
        off,on=result['C088',tap],result['C105',tap]
        for row,cue in ((off,'CUES_OFF'),(on,'REAL_ALIGNED_CUES')):
            if row['gallery_condition']!='FIXED_ROTATION_A' or row['enrollment_tier']!=15 or row['cue_condition']!=cue or row['identity_tap']!=tap:raise ValueError('Exact same-tap fixedA15 cue pair required')
        left,right=deepcopy(off['profile']),deepcopy(on['profile'])
        if left['tracker']['cues_enabled'] is not False or right['tracker']['cues_enabled'] is not True or left['xvf']['mode']!='none' or right['xvf']['mode']!='tracking_only':raise ValueError('Only off-to-tracking-only routing admitted')
        for value in (left,right):
            value.pop('profile_id');value['tracker']['cues_enabled']=None;value['xvf']['mode']=None
        if left!=right:raise ValueError('Unexpected actual profile difference beyond the three declared fields')
    return result



def grid(selected,p):
    if selected!=['C088','C105'] or p!={'case_ids':['S45_08_07'],'repeated_case_ids':['S45_08_07']}:raise ValueError('Exact sentinel grid required')
    return [(candidate,'S45_08_07',tap,rep) for rep in (1,2,3) for tap in ('O0','O1') for candidate in (selected if rep%2 else list(reversed(selected)))]


@L.observer_entry
def prepare(args):
    driver,common,spec,eb=load_native();p,pb=panel();root,payload=namespace_roots(args.namespace)
    if root.exists() or payload.exists():raise ValueError('Fresh paced namespace required')
    candidates=args.candidates.split(',');p=selected_panel(p,args.panel_mode,candidates);routes=candidate_routes(spec,candidates)
    index,ib=L.read_bound(spec['input_index']['path'],spec['input_index']);lookup={(r['case_id'],r['stream']):r for r in index['rows']};sources={}
    deadline=L.dt(args.deadline_utc)
    if deadline> L.DEADLINE or deadline<=datetime.now(timezone.utc):raise ValueError('Bounded future deadline with closure reserve required')
    for case in p['case_ids']:
        pair={tap:lookup[case,tap] for tap in ('O0','O1')}
        for row in pair.values():verify_pcm(row)
        L.verify(pair['O0']['telemetry']);sources[case]=source_record(pair,ib)
    galleries={key:L.select_gallery(driver,spec,row) for key,row in routes.items()}
    for tap in ('O0','O1'):
        if galleries['C088',tap]!=galleries['C105',tap]:raise ValueError('Actual sentinel galleries differ')
    # Only JSON metadata is materialized. Native waveforms/cues remain at their
    # canonical indexed paths, including the actual non-45-second view length.
    source_map={case:common.save(root/'sources'/(case+'.json'),value,immutable=True) for case,value in sources.items()}
    jobs=[]
    for candidate,case,tap,rep in grid(candidates,p):
        row=routes[candidate,tap];gallery,gr=galleries[candidate,tap];job_id=f'{candidate}_{case}_{tap}_{row["identity_tap"]}_r{rep}'
        job=dict(job_id=job_id,candidate_id=candidate,case_id=case,asr_tap=tap,identity_tap=row['identity_tap'],repetition=rep,profile_row=row,profile_sha256=L.digest(row),
            source=source_map[case],gallery=gallery,gallery_row=gr,report_root=str(root/'jobs'/job_id),payload_root=str(payload/'jobs'/job_id),
            timeout_sec=max(720.,sources[case]['duration_sec']*1.75+row['profile']['runtime']['lane_drain_timeout_sec']+120.))
        job['job_key']=L.digest(job);jobs.append(job)
    plan=dict(schema=SCHEMA,status='PREPARED_NO_MODELS_STARTED',created_utc=L.utc(),namespace=args.namespace,observer_policy=L.observer_policy(),protected_guard_policy=L.protected_guard_policy(),execution_manifest=eb,input_index=ib,panel=pb,panel_mode=args.panel_mode,candidates=candidates,
        jobs=jobs,requested=len(jobs),source_case_ids=p['case_ids'],repeat_case_ids=p['repeated_case_ids'],report_root=str(root),payload_root=str(payload),
        sources=source_bindings(),deadline_utc=deadline.isoformat(),worker_limit=1,inner_threads=1,pending_cell_bytes=CELL_RESERVE,max_run_sec=MAX_RUN_SEC,
        original_native_function=L.protected_identities(driver)['native']['code_sha256'],
        total_source_sec=sum(sources[j['case_id']]['duration_sec'] for j in jobs),
        scope='Exploratory S45_08_07 C088/C105 fixedA15 matched cue-off/real, both taps, three repeats. Selected after arrival-boundary discrepancy; all12 cells retained. Does not replace main16+4 or gate6 and does not imply finalist status.',
        original_result_scope_note='The unchanged generic long native body retains its fixed concatenation wording. CELL_RESULT and the canonical source manifest supply the actual single-scene input semantics; no long composition or epoch2 source is asserted.')
    plan['manifest_key']=L.digest(plan);return common.save(root/'MANIFEST.json',plan,immutable=True)


def admit(path):
    plan,pb=L.read_bound(path);copy=dict(plan);wanted=copy.pop('manifest_key')
    if plan.get('observer_policy')!=L.observer_policy():raise ValueError('Exact fast observer policy required')
    if plan.get('protected_guard_policy')!=L.protected_guard_policy():raise ValueError('Exact structural native guard policy required')
    if plan['schema']!=SCHEMA or L.digest(copy)!=wanted:raise ValueError('Prepared manifest digest/schema differs')
    root,payload=namespace_roots(plan['namespace'])
    if Path(path).resolve()!=root/'MANIFEST.json' or plan['report_root']!=str(root) or plan['payload_root']!=str(payload):raise ValueError('Paced namespace differs')
    if plan['sources']!=source_bindings() or plan['worker_limit']!=1 or plan['inner_threads']!=1 or plan['pending_cell_bytes']!=CELL_RESERVE or plan['max_run_sec']!=MAX_RUN_SEC:raise ValueError('Held source/limits differ')
    driver,common,spec,eb=load_native();p,panel_binding=panel()
    if plan['execution_manifest']!=eb or plan['panel']!=panel_binding or plan['input_index']!=spec['input_index'] or L.dt(plan['deadline_utc'])>L.DEADLINE:raise ValueError('Pinned epoch/panel/deadline differs')
    if plan['original_native_function']!=L.protected_identities(driver)['native']['code_sha256']:raise ValueError('Original native function changed')
    p=selected_panel(p,plan['panel_mode'],plan['candidates'])
    routes=candidate_routes(spec,plan['candidates']);wanted_grid=grid(plan['candidates'],p)
    actual=[(j['candidate_id'],j['case_id'],j['asr_tap'],j['repetition']) for j in plan['jobs']]
    if actual!=wanted_grid or plan['requested']!=len(actual) or plan['source_case_ids']!=p['case_ids'] or plan['repeat_case_ids']!=p['repeated_case_ids']:raise ValueError('Exact selected panel/two-tap grid differs')
    index,ib=L.read_bound(spec['input_index']['path'],spec['input_index']);lookup={(r['case_id'],r['stream']):r for r in index['rows']}
    for job in plan['jobs']:
        copy=dict(job);key=copy.pop('job_key')
        if L.digest(copy)!=key:raise ValueError('Cell digest differs')
        row=routes[job['candidate_id'],job['asr_tap']];gallery,gr=L.select_gallery(driver,spec,row)
        expected_id=f'{job["candidate_id"]}_{job["case_id"]}_{job["asr_tap"]}_{row["identity_tap"]}_r{job["repetition"]}'
        if job['job_id']!=expected_id:raise ValueError('Canonical cell ID differs')
        if row!=job['profile_row'] or L.digest(row)!=job['profile_sha256'] or row['identity_tap']!=job['identity_tap'] or gallery!=job['gallery'] or gr!=job['gallery_row']:raise ValueError('Exact registered cell profile/gallery differs')
        if job['report_root']!=str(root/'jobs'/job['job_id']) or job['payload_root']!=str(payload/'jobs'/job['job_id']):raise ValueError('Cell output namespace differs')
        source,sb=L.read_bound(job['source']['path'],job['source']);expected=source_record({tap:lookup[job['case_id'],tap] for tap in ('O0','O1')},ib)
        if source!=expected or Path(sb['path'])!=root/'sources'/(job['case_id']+'.json'):raise ValueError('Canonical per-case source/offset/gap differs')
        if job['timeout_sec']!=max(720.,source['duration_sec']*1.75+row['profile']['runtime']['lane_drain_timeout_sec']+120.):raise ValueError('Bounded native timeout changed')
    if plan['total_source_sec']!=sum(lookup[j['case_id'],j['asr_tap']]['duration_sec'] for j in plan['jobs']):raise ValueError('Actual source-time denominator differs')
    return plan,pb,driver,common,spec


def quiet(excluded=()):
    skip={os.getpid(),*excluded};found=[]
    for p in psutil.process_iter(['pid','cmdline','create_time']):
        if p.pid in skip:continue
        argv=p.info['cmdline'] or [];names={Path(a).name.lower() for a in argv}
        if L.worker_command(argv) or (bool({'s6c_paced_epoch4.py','s6c_paced_arrival_sentinel_v1.py','s6c_paced_cross_routes_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_paced_arrival_sentinel_fast_v1.py','s6c_paced_cross_routes_fast_v1.py','s6c_paced_epoch4_fast_v2.py','s6c_paced_arrival_sentinel_fast_v2.py','s6c_paced_cross_routes_fast_v2.py'}&names) and any(v in argv for v in ('run','worker'))):
            if L.state(p.pid,p.info['create_time']):found.append(dict(pid=p.pid,creation_time=p.info['create_time']))
    for path in REPORT.glob('epoch*/workers/*.json'):
        row,_=L.read_bound(path)
        if row['pid'] not in skip and L.state(row['pid'],row['creation_time']):found.append(dict(pid=row['pid'],creation_time=row['creation_time']))
    if found:raise RuntimeError('Other study workers remain active: '+json.dumps(found))


@L.observer_entry
def worker(args):
    plan,pb,driver,common,spec=admit(args.manifest);jobs=[j for j in plan['jobs'] if j['job_id']==args.job_id]
    if len(jobs)!=1:raise ValueError('One exact cell required')
    job=jobs[0];root=Path(job['report_root']);source,sb=L.read_bound(job['source']['path'],job['source']);lease,lb=L.read_bound(args.owner_lease)
    if Path(args.owner_lease).resolve()!=REPORT/'PACED_QUIET_OWNER.json' or lease['manifest']!=pb or lease['kind']!='S6C_PACED_ARRIVAL_SENTINEL' or not L.state(lease['pid'],lease['creation_time']):raise ValueError('Live parent-owned quiet lease required')
    process=psutil.Process();owner=dict(pid=process.pid,creation_time=process.create_time(),argv=process.cmdline());quiet((lease['pid'],));L.check_headroom(common.admit_work(full=True),CELL_RESERVE)
    for tap in ('O0','O1'):L.verify(source['audio'][tap])
    L.verify(source['telemetry']);L.verify(pb)
    if (root/'CELL_ADMISSION.json').exists():raise ValueError('Prior cell attempt requires a separate diagnosed namespace')
    common.save(root/'CELL_ADMISSION.json',dict(status='STARTED',created_utc=L.utc(),owner=owner,manifest=pb,job=job,source=sb,source_kind='CANONICAL_SINGLE_SCENE_PAIR',actual_execution_epoch='epoch4',execution_manifest=plan['execution_manifest'],quiet_lease=lb),immutable=True)
    effective={**source,'report_root':str(root),'payload_root':job['payload_root']};original_sample=driver.process_sample;start=time.monotonic();result=None;error=None
    def guard():
        if time.monotonic()-start>job['timeout_sec'] or datetime.now(timezone.utc)>=L.dt(plan['deadline_utc']):raise TimeoutError('Paced cell time bound')
        L.check_headroom(common.admit_work(full=False))
    def load_override(unused,assets=False):
        if assets is not True:raise ValueError('Native asset admission required')
        return deepcopy(effective),spec,sb
    def sampled(p):guard();return original_sample(p)
    replacements=dict(load_composition=load_override,admit_work=lambda full=False:common.admit_work(full=full),process_sample=sampled)
    native_args=argparse.Namespace(version=job['job_id'],epoch='epoch4',candidate=job['candidate_id'],asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],gallery=Path(job['gallery']['path']) if job['gallery'] else None)
    before=L.protected_identities(driver)
    try:
        with L.protected_override(driver,replacements):result=driver.native(native_args)
        actual,result=L.read_bound(result['path'],result)
        if actual['status']!='COMPLETE' or actual['composition']!=sb or actual['profile']!=job['profile_row'] or actual['long_session_gallery_condition']!=job['gallery_row'] or actual['owner']!=owner or actual['source_duration_sec']!=source['duration_sec']:raise ValueError('Actual canonical paced result differs')
        guard()
        return common.save(root/'CELL_RESULT.json',dict(schema='s6c-paced-arrival-sentinel-cell-result.v1',status='COMPLETE',created_utc=L.utc(),owner=owner,manifest=pb,job=job,source=sb,
            source_kind='CANONICAL_SINGLE_SCENE_PAIR',actual_execution_epoch='epoch4',execution_manifest=plan['execution_manifest'],native_result=result,source_offset_samples=0,inserted_gap_samples=0,
            original_native_function_unchanged=L.protected_identities(driver)==before,process_exit_not_yet_claimed=True,
            interpretation='Actual single canonical scene, not concatenated or long. The original generic native RESULT scope wording is retained as source provenance; this exact per-case receipt defines input semantics.'),immutable=True)
    except BaseException:
        error=traceback.format_exc();raise
    finally:
        common.save(root/'CELL_OUTCOME.json',dict(status='NATIVE_RETURNED' if error is None else 'FAILED',owner=owner,manifest=pb,job_key=job['job_key'],native_result=result,error=error,protected_functions_restored=L.protected_identities(driver)==before),immutable=True)


def terminate_owned(owned):
    for pid,created in reversed(list(owned.items())):
        try:
            if L.state(pid,created):psutil.Process(pid).terminate()
        except psutil.NoSuchProcess:pass
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and any(L.state(p,c) for p,c in owned.items()):time.sleep(.1)
    for pid,created in reversed(list(owned.items())):
        try:
            if L.state(pid,created):psutil.Process(pid).kill()
        except psutil.NoSuchProcess:pass


def owned_states(owned,state=None):
    state=state or L.state;rows=[]
    for pid,created in owned.items():
        try:alive=state(pid,created);error=None
        except Exception as exc:alive=None;error=type(exc).__name__+': '+str(exc)
        if alive not in (True,False) or type(alive) is not bool:alive=None
        rows.append(dict(pid=pid,creation_time=created,alive=alive,inspection_error=error))
    return rows


def release_after_closure(lock,target,expected,states,release=None):
    if any(row['alive'] is not False for row in states):
        return dict(status='RETAINED_OWNED_CLOSURE_UNVERIFIED',released=False,error='At least one recorded owned process is live or cannot be inspected; lease retained.',archived_binding=None)
    return (release or L.release_lease)(lock,target,expected)


def native_folder(job):
    row=job['gallery_row'];condition=row['gallery_condition']+'_tier'+str(row['enrollment_tier']) if row else 'NONE'
    return Path(job['report_root'])/'native'/job['candidate_id']/(job['asr_tap']+'_'+job['identity_tap'])/condition


def valid_owner(owner):
    if type(owner['pid']) is not int or owner['pid']<=0 or type(owner['creation_time']) not in (int,float) or not math.isfinite(owner['creation_time']) or owner['creation_time']<=0:raise ValueError('Exact finite owned process identity required')


def validate_native_identity(native,job,source,spec,owner):
    valid_owner(owner)
    if native['schema']!='s6c_continuous_paced_native.v1' or native['status']!='COMPLETE' or native['composition']!=job['source'] or native['profile']!=job['profile_row'] or native['owner']!=owner:raise ValueError('Native result source/profile/owner identity differs')
    if native['source_duration_sec']!=source['duration_sec'] or native['long_session_gallery_condition']!=job['gallery_row'] or native['gallery_index']!=spec.get('gallery_index'):raise ValueError('Native duration/gallery differs')
    if native['resident_bundle_loads']!=1 or native['resident_sessions_created']!=1 or native['live_owned_lanes'] or native['hardware_invocations']!=0 or native['final_telemetry']['asr_cursor_sec']!=source['duration_sec']:raise ValueError('Native full-tail/session/closure differs')
    for key in ('model_load_sec','native_elapsed_sec','total_observed_worker_sec'):
        if type(native[key]) not in (int,float) or not math.isfinite(native[key]) or native[key]<0:raise ValueError('Invalid native measured time')
    expected={'audio_spool.pcm16':job['asr_tap'],'identity_audio_spool.pcm16':job['identity_tap']}
    if set(native['native_journals'])!=set(expected):raise ValueError('Exact paired journals required')
    for name,tap in expected.items():
        b=native['native_journals'][name]
        if b['sha256']!=source['pcm_sha256'][tap] or b['bytes']!=source['duration_samples']*2 or Path(b['path']).name!=name or b not in native['native_artifacts']:raise ValueError('Exact paired full journal binding differs')
    if Path(native['process_samples']['path']).resolve()!=native_folder(job)/'PROCESS_SAMPLES.jsonl':raise ValueError('Native process trajectory namespace differs')
    parents={Path(b['path']).resolve().parent for b in native['native_artifacts']}
    if len(parents)!=1:raise ValueError('Exactly one native session artifact directory required')
    session=next(iter(parents));suffix=native_folder(job).relative_to(Path(job['report_root']))
    if session.parent!=Path(job['payload_root'])/suffix/'sessions':raise ValueError('Native session payload namespace differs')


def read_cell_chain(job,plan,pb,spec):
    folder=Path(job['report_root']);source,sb=L.read_bound(job['source']['path'],job['source'])
    cell,cb=L.read_bound(folder/'CELL_RESULT.json');valid_owner(cell['owner'])
    if cell['schema']!='s6c-paced-arrival-sentinel-cell-result.v1' or cell['status']!='COMPLETE' or cell['manifest']!=pb or cell['job']!=job or cell['source']!=sb:raise ValueError('Canonical cell receipt identity differs')
    if cell['source_kind']!='CANONICAL_SINGLE_SCENE_PAIR' or cell['actual_execution_epoch']!='epoch4' or cell['execution_manifest']!=plan['execution_manifest'] or cell['source_offset_samples']!=0 or cell['inserted_gap_samples']!=0 or cell['original_native_function_unchanged'] is not True:raise ValueError('Canonical cell source/epoch/native boundary differs')
    native,nb=L.read_bound(cell['native_result']['path'],cell['native_result'])
    if Path(nb['path']).resolve()!=native_folder(job)/'RESULT.json':raise ValueError('Native result output namespace differs')
    validate_native_identity(native,job,source,spec,cell['owner'])
    admission,ab=L.read_bound(folder/'CELL_ADMISSION.json');launch,lb=L.read_bound(folder/'LAUNCH.json');outcome,ob=L.read_bound(folder/'CELL_OUTCOME.json')
    if admission['status']!='STARTED' or admission['owner']!=cell['owner'] or admission['manifest']!=pb or admission['job']!=job or admission['source']!=sb or admission['source_kind']!='CANONICAL_SINGLE_SCENE_PAIR' or admission['actual_execution_epoch']!='epoch4' or admission['execution_manifest']!=plan['execution_manifest']:raise ValueError('Original cell admission differs')
    if launch['job_key']!=job['job_key'] or launch['manifest']!=pb or (launch['pid'],launch['creation_time'])!=(cell['owner']['pid'],cell['owner']['creation_time']) or launch['argv']!=cell['owner']['argv']:raise ValueError('Original child launch differs')
    if outcome['status']!='NATIVE_RETURNED' or outcome['owner']!=cell['owner'] or outcome['manifest']!=pb or outcome['job_key']!=job['job_key'] or outcome['native_result']!=nb or outcome['error'] is not None or outcome['protected_functions_restored'] is not True:raise ValueError('Native child outcome differs')
    artifacts=[cb,nb,L.bind(folder/'PROCESS_TREE_SAMPLES.jsonl'),ob,ab,lb]+native['native_artifacts']+[native['process_samples']]
    if len({str(Path(b['path']).resolve()) for b in artifacts})!=len(artifacts):raise ValueError('Duplicate required artifact path')
    for b in artifacts:L.verify(b)
    final=[b for b in native['native_artifacts'] if Path(b['path']).name=='session_finalization_v3.json']
    if len(final)!=1:raise ValueError('One exact session finalization required')
    closure,_=L.read_bound(final[0]['path'],final[0])
    if closure['state']!='COMPLETED' or closure['live_lanes_at_finalization'] or closure['resident_bundle_lease_retained'] or closure['event_and_transcript_handles_closed'] is not True:raise ValueError('Native finalization differs')
    return cell,cb,native,nb,artifacts


def validate_complete(old,job,plan,pb,spec,state=None):
    if old['status']!='COMPLETE' or old['job_key']!=job['job_key'] or old['job_id']!=job['job_id'] or old['all_owned_processes_closed'] is not True or old['source_kind']!='CANONICAL_SINGLE_SCENE_PAIR':raise ValueError('Prior cell completion differs')
    cell,cb,native,nb,artifacts=read_cell_chain(job,plan,pb,spec)
    if old['cell_result']!=cb or old['native_result']!=nb or old['artifacts']!=artifacts:raise ValueError('Completion must bind the exact original cell/native artifact chain')
    identities={}
    for row in old['owned_processes']:
        valid_owner(row)
        if row['pid'] in identities:raise ValueError('Duplicate recorded owned PID')
        identities[row['pid']]=row['creation_time']
    if identities.get(cell['owner']['pid'])!=cell['owner']['creation_time'] or any(r['alive'] is not False for r in owned_states(identities,state)):raise ValueError('Prior completed owners are not confirmed closed')
    external_binding=next(b for b in artifacts if Path(b['path']).name=='PROCESS_TREE_SAMPLES.jsonl')
    raw=Path(external_binding['path']).read_bytes()
    if len(raw)!=external_binding['bytes'] or hashlib.sha256(raw).hexdigest()!=external_binding['sha256']:raise ValueError('Exact external process sample buffer differs')
    external=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    if old['external_process_samples']!=len(external):raise ValueError('External sample denominator differs')
    for sample in external:
        for row in sample['process']['processes']:
            if identities.get(row['pid'])!=row['creation_time']:raise ValueError('Sampled owned process missing from closure')
    # Coordinator wall is an original bound measurement, not reconstructible
    # from nested native clocks. Recompute every deterministic measurement.
    measured=completed_measurement(job,native,old['measurement']['completed_cell_wall_sec'])
    if old['measurement']!=measured:raise ValueError('Completion measurement differs from exact native evidence')
    return measured


def phase_observations(samples,duration):
    previous=None;previous_nonfull=None;first_full=None;terminal=None;gaps=[]
    for sample in samples:
        instant=sample['elapsed_from_native_launch_sec']
        if type(instant) not in (int,float) or not math.isfinite(instant) or instant<0 or (previous is not None and instant<previous):raise ValueError('Invalid sampled phase clock')
        if previous is not None:gaps.append(instant-previous)
        previous=instant;cursor=sample.get('telemetry',{}).get('source_duration_sec')
        if cursor is not None and (type(cursor) not in (int,float) or not math.isfinite(cursor) or cursor<0):raise ValueError('Invalid observed source cursor')
        if cursor is not None and cursor>=duration and first_full is None:first_full=instant
        elif first_full is None and cursor is not None:previous_nonfull=instant
        if sample.get('phase')=='terminal_after_finalization':terminal=instant
    lower=terminal-first_full if terminal is not None and first_full is not None else None
    upper=terminal-previous_nonfull if terminal is not None and previous_nonfull is not None and first_full is not None else None
    if terminal is not None and terminal!=previous:raise ValueError('Terminal phase must be last')
    return dict(process_samples=len(samples),first_full_source_cursor_observed_sec=first_full,terminal_after_finalization_observed_sec=terminal,
        full_cursor_to_terminal_interval_sec=None if lower is None else [lower,upper],max_sample_gap_sec=max(gaps) if gaps else None,exact_eof_drain_sec=None,
        scope='Interval-censored full-source-cursor publication to terminal observation, including final source pacing and closure; native source EOF is not timestamped. This is not exact decoder drain or phonetic latency.')


def completed_measurement(job,native,cell_wall):
    if type(cell_wall) not in (int,float) or not math.isfinite(cell_wall) or cell_wall<=0:raise ValueError('Original measured positive finite coordinator cell wall required')
    b=native['process_samples'];raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('Closed native process sample binding differs')
    phases=phase_observations([json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()],native['source_duration_sec'])
    if len([line for line in raw.decode('utf-8-sig').splitlines() if line.strip()])!=native['process_sample_count']:raise ValueError('Native process sample denominator differs')
    return dict(job_id=job['job_id'],candidate_id=job['candidate_id'],case_id=job['case_id'],asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],repetition=job['repetition'],
        source_sec=native['source_duration_sec'],completed_cell_wall_sec=cell_wall,model_startup_sec=native['model_load_sec'],native_elapsed_sec=native['native_elapsed_sec'],
        original_observed_worker_sec=native['total_observed_worker_sec'],phase_observations=phases,
        scope='Completed cell wall includes fresh child launch/admission/model/file/drain/closure and parent validation. Startup/native/phase intervals are nested observations, never added to that wall time.')


def progress(jobs,completed,current,elapsed,active_id=None,active_elapsed=0.):
    done={r['job_id'] for r in completed};remaining=[j for j in jobs if j['job_id'] not in done]
    if len(done)!=len(completed):raise ValueError('Duplicate completion progress observation')
    if not done<={j['job_id'] for j in jobs} or len({r['job_id'] for r in current})!=len(current) or any(r not in completed for r in current):raise ValueError('Progress observations differ from admitted/current cells')
    for row in completed:
        if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) or row[k]<0 for k in ('source_sec','completed_cell_wall_sec','model_startup_sec','native_elapsed_sec')):raise ValueError('Invalid measured completion progress')
    def mean(field):
        values=[r[field] for r in completed if r.get(field) is not None]
        return sum(values)/len(values) if values else None
    seconds=sum(r['source_sec'] for r in current);wall=sum(r['completed_cell_wall_sec'] for r in current)
    prediction=None
    if completed:
        prediction=0.
        for job in remaining:
            local=[r['completed_cell_wall_sec'] for r in completed if (r['candidate_id'],r['asr_tap'],r['identity_tap'])==(job['candidate_id'],job['asr_tap'],job['identity_tap'])]
            estimates=local or [r['completed_cell_wall_sec'] for r in completed];cost=sum(estimates)/len(estimates)
            prediction+=max(cost*.1,cost-active_elapsed) if job['job_id']==active_id else cost
    return dict(completed_cells=len(completed),requested_cells=len(jobs),completed_source_sec=sum(r['source_sec'] for r in completed),new_completed_cells_this_invocation=len(current),new_source_sec_this_invocation=seconds,
        completed_cell_source_seconds_per_wall_second=seconds/wall if wall>0 else None,invocation_source_seconds_per_elapsed_second=seconds/elapsed if elapsed>0 and current else None,
        mean_completed_cell_wall_sec=mean('completed_cell_wall_sec'),mean_nested_model_startup_sec=mean('model_startup_sec'),mean_nested_native_elapsed_sec=mean('native_elapsed_sec'),
        exact_eof_drain_sec=None,observed_phase_rows=sum(r.get('phase_observations',{}).get('first_full_source_cursor_observed_sec') is not None for r in completed),
        heuristic_remaining_wall_sec=prediction,heuristic_eta_range_sec=None if prediction is None else [prediction*.75,prediction*1.5],
        basis='Completed actual fresh-cell wall observations, matched candidate/tap when available, otherwise pooled completed cells; partial active time is subtracted with a 10% observed-cell-cost residual floor while active. Reused completions may inform ETA but never current-invocation throughput. Heuristic range, not a confidence interval, latency qualification or model/replay equivalence.')


@L.observer_entry
def run(args):
    plan,pb,driver,common,spec=admit(args.manifest);admission,ab=L.read_bound(args.quiet_admission)
    if admission.get('status')!='AUTHORIZED_FOR_QUIET_PACED' or admission.get('manifest_sha256')!=pb['sha256'] or admission.get('all_other_model_hil_work_stopped') is not True or admission.get('all_heavy_analysis_stopped') is not True:raise ValueError('Exact coordinator quiet admission required')
    deadline=min(L.dt(plan['deadline_utc']),L.dt(admission['expires_utc']),L.DEADLINE)
    if deadline<=datetime.now(timezone.utc):raise ValueError('Quiet admission expired')
    quiet();L.check_headroom(common.admit_work(full=True),CELL_RESERVE);root=Path(plan['report_root']);inv=root/'invocations'/uuid.uuid4().hex;inv.mkdir(parents=True)
    me=psutil.Process();owner=dict(pid=me.pid,creation_time=me.create_time(),argv=me.cmdline());lock=REPORT/'PACED_QUIET_OWNER.json'
    if lock.exists():raise ValueError('Existing quiet lease requires explicit closure/resolution')
    launch=common.save(inv/'LAUNCH.json',dict(status='STARTED',created_utc=L.utc(),owner=owner,manifest=pb,quiet_admission=ab,sources=source_bindings()),immutable=True)
    with lock.open('x',encoding='utf-8') as f:json.dump(dict(**owner,manifest=pb,kind='S6C_PACED_ARRIVAL_SENTINEL',launch=launch),f);f.flush();os.fsync(f.fileno())
    lease_binding=L.bind(lock);started=time.monotonic();complete=[];measurements=[];current_measurements=[];error=None;cleanup_errors=[];owned={};child=None
    try:
        for job in plan['jobs']:
            folder=Path(job['report_root']);done=folder/'COMPLETE.json'
            if done.exists():
                old,db=L.read_bound(done)
                measurement=validate_complete(old,job,plan,pb,spec);L.verify(db)
                measurements.append(measurement);complete.append(dict(job_id=job['job_id'],status='COMPLETE_REUSED',completion=db));continue
            if (folder/'CELL_ADMISSION.json').exists():raise ValueError('Prior failed/incomplete cell requires a diagnosed new namespace')
            if datetime.now(timezone.utc).timestamp()+job['timeout_sec']>=deadline.timestamp() or time.monotonic()-started+job['timeout_sec']>MAX_RUN_SEC:raise TimeoutError('No bounded cell time remains in quiet interval')
            quiet();L.check_headroom(common.admit_work(full=True),CELL_RESERVE);L.verify(pb);L.verify(ab);folder.mkdir(parents=True,exist_ok=True)
            argv=[sys.executable,str(Path(__file__).resolve()),'worker','--manifest',str(args.manifest),'--job-id',job['job_id'],'--owner-lease',str(lock)]
            owned={};cell_started=time.monotonic();sample_count=0;last_full=-1.
            with (folder/'WORKER_LOG.txt').open('x',encoding='utf-8') as log,(folder/'PROCESS_TREE_SAMPLES.jsonl').open('x',encoding='utf-8') as trajectory:
                child=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));process=psutil.Process(child.pid);owned[child.pid]=process.create_time()
                common.save(folder/'LAUNCH.json',dict(job_key=job['job_key'],pid=child.pid,creation_time=owned[child.pid],argv=argv,manifest=pb,created_utc=L.utc()),immutable=True)
                while child.poll() is None:
                    elapsed=time.monotonic()-cell_started
                    if elapsed>job['timeout_sec'] or datetime.now(timezone.utc)>=deadline or (REPORT/'STOP_REQUEST.json').exists():raise TimeoutError('Owned paced cell time/stop guard')
                    sample=driver.process_sample(process)
                    for row in sample['processes']:owned[row['pid']]=row['creation_time']
                    trajectory.write(json.dumps(dict(utc=L.utc(),elapsed_sec=elapsed,process=sample,coordinator_rss_bytes=me.memory_info().rss),allow_nan=False)+'\n');trajectory.flush();sample_count+=1
                    L.check_headroom(common.admit_work(full=False))
                    if elapsed-last_full>=20:
                        quiet(owned);resources=common.admit_work(full=True);L.check_headroom(resources);last_full=time.monotonic()-cell_started
                        common.save(root/'HEARTBEAT.json',dict(status='RUNNING',job_id=job['job_id'],completed=len(complete),requested=len(plan['jobs']),owner=owner,worker=dict(pid=child.pid,creation_time=owned[child.pid]),elapsed_sec=time.monotonic()-started,resources=resources,
                            measured_progress=progress(plan['jobs'],measurements,current_measurements,time.monotonic()-started,job['job_id'],elapsed)))
                    time.sleep(.5)
                os.fsync(trajectory.fileno())
            if child.returncode!=0:raise RuntimeError('Original paced native child failed; preserve cell artifacts')
            value,rb,native,nb,artifacts=read_cell_chain(job,plan,pb,spec)
            if value['owner']['pid']!=child.pid or value['owner']['creation_time']!=owned[child.pid]:raise ValueError('Paced child result owner differs')
            if any(r['alive'] is not False for r in owned_states(owned)):raise ValueError('Owned native process remains live or unverified')
            L.check_headroom(common.admit_work(full=True));measurement=completed_measurement(job,native,time.monotonic()-cell_started)
            db=common.save(done,dict(status='COMPLETE',created_utc=L.utc(),job_key=job['job_key'],job_id=job['job_id'],cell_result=rb,native_result=nb,artifacts=artifacts,measurement=measurement,
                all_owned_processes_closed=True,owned_processes=[dict(pid=p,creation_time=c) for p,c in owned.items()],external_process_samples=sample_count,source_kind='CANONICAL_SINGLE_SCENE_PAIR'),immutable=True)
            measurements.append(measurement);current_measurements.append(measurement);complete.append(dict(job_id=job['job_id'],status='COMPLETE',completion=db));child=None;owned={}
        result=common.save(root/'PACED_INDEX.json',dict(schema=SCHEMA,status='COMPLETE',manifest=pb,requested=len(plan['jobs']),completed=len(complete),rows=complete,created_utc=L.utc(),measured_progress=progress(plan['jobs'],measurements,current_measurements,time.monotonic()-started),measurements=measurements),immutable=True)
        return result
    except BaseException:
        error=traceback.format_exc()
        try:
            if owned:terminate_owned(owned)
        except Exception:cleanup_errors.append(traceback.format_exc())
        try:
            if child is not None:child.wait(timeout=10)
        except Exception:cleanup_errors.append(traceback.format_exc())
        raise
    finally:
        remaining=owned_states(owned)
        outcome=common.save(inv/'OUTCOME.json',dict(status='COMPLETE' if error is None else 'PARTIAL',owner=owner,manifest=pb,completed=len(complete),requested=len(plan['jobs']),rows=complete,error=error,
            remaining_owned=remaining,cleanup_errors=cleanup_errors,elapsed_sec=time.monotonic()-started,measured_progress=progress(plan['jobs'],measurements,current_measurements,time.monotonic()-started),measurements=measurements),immutable=True)
        release=release_after_closure(lock,inv/'QUIET_LEASE_RELEASED.json',lease_binding,remaining)
        common.save(inv/'CLOSURE.json',dict(status='QUIET_LEASE_RELEASED' if release['status']=='RELEASED' else 'LEASE_RETAINED_OWNED_CLOSURE_UNVERIFIED' if release['status']=='RETAINED_OWNED_CLOSURE_UNVERIFIED' else 'LEASE_RELEASE_FAILED_OR_UNVERIFIED',owner=owner,manifest=pb,outcome=outcome,lease_release=release,
            scope='Only recorded owned children are closed. Current coordinator process exit needs external PID/creation inspection. Resource values are observed samples, not continuous maxima.'),immutable=True)
        if release['status']!='RELEASED':raise RuntimeError('Quiet lease release failed or unverified')


def checks():
    import ast
    import s6c_paced_epoch4_fast_v2 as baseline
    if Path(baseline.__file__).resolve()!=Path(__file__).with_name('s6c_paced_epoch4_fast_v2.py').resolve():raise ValueError('Wrong held adapter import')
    original=baseline.checks();passed=[]
    def ok(name,value):
        if not value:raise AssertionError(name)
        passed.append(name)
    def reject(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):passed.append(name);return
        raise AssertionError(name)
    proposal=dict(schema='s6c-paced-arrival-sentinel-selection.v1',candidates=['C088','C105'],case_ids=['S45_08_07'],streams=['O0','O1'],repetitions=[1,2,3],expected_cells=12,gallery_condition='FIXED_ROTATION_A',enrollment_tier=15,cue_conditions={'C088':'CUES_OFF','C105':'REAL_ALIGNED_CUES'},all_repetitions_retained=True,main16_plus4_and_gate6_unchanged=True)
    panel=selected_panel(proposal,'arrival_sentinel',['C088','C105']);cells=grid(['C088','C105'],panel)
    ok('twelve_unique_cells',len(cells)==len(set(cells))==12)
    ok('exact_repeats',sorted({x[3] for x in cells})==[1,2,3])
    ok('counterbalanced_second_repeat',cells[4][0]=='C105' and cells[8][0]=='C088')
    for field,value in [('case_ids',['S45_08_14']),('repetitions',[1,2]),('streams',['O0']),('expected_cells',8),('gallery_condition','FIXED_ROTATION_B'),('enrollment_tier',30),('all_repetitions_retained',False),('main16_plus4_and_gate6_unchanged',False)]:
        p=deepcopy(proposal);p[field]=value;reject('reject_selection_'+field,lambda p=p:selected_panel(p,'arrival_sentinel',['C088','C105']))
    reject('reject_full_panel',lambda:selected_panel(proposal,'full16_plus4',['C088','C105']))
    reject('reject_candidate_order',lambda:selected_panel(proposal,'arrival_sentinel',['C105','C088']))
    reject('reject_repeated_grid',lambda:grid(['C088','C105'],dict(case_ids=['S45_08_07'],repeated_case_ids=[])))
    off=dict(profile_id='C088',tracker=dict(cues_enabled=False),xvf=dict(mode='none'),identity=dict(mode='post_association'),embedding=dict(window_sec=1.5))
    on=deepcopy(off);on.update(profile_id='C105');on['tracker']['cues_enabled']=True;on['xvf']['mode']='tracking_only'
    spec=dict(profiles=[dict(candidate_id=c,asr_tap=t,identity_tap=t,gallery_condition='FIXED_ROTATION_A',enrollment_tier=15,cue_condition='CUES_OFF' if c=='C088' else 'REAL_ALIGNED_CUES',profile=deepcopy(off if c=='C088' else on)) for c in ('C088','C105') for t in ('O0','O1')])
    ok('matched_profiles_admitted',len(candidate_routes(spec,['C088','C105']))==4)
    for field,value in [('gallery_condition','FIXED_ROTATION_B'),('enrollment_tier',5),('identity_tap','O1'),('cue_condition','CUES_OFF')]:
        altered=deepcopy(spec);altered['profiles'][2][field]=value;reject('reject_route_'+field,lambda s=altered:candidate_routes(s,['C088','C105']))
    altered=deepcopy(spec);altered['profiles'][2]['profile']['embedding']['window_sec']=2.;reject('reject_other_profile_change',lambda:candidate_routes(altered,['C088','C105']))
    altered=deepcopy(spec);altered['profiles'][2]['profile']['xvf']['mode']='both';reject('reject_endpoint_advice',lambda:candidate_routes(altered,['C088','C105']))
    held=ast.parse(Path(baseline.__file__).read_text());current=ast.parse(Path(__file__).read_text());lookup=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)};a,b=lookup(held),lookup(current)
    unchanged=['load_native','validate_source_rows','verify_pcm','source_record','admit','terminate_owned','owned_states','release_after_closure','native_folder','valid_owner','validate_native_identity','validate_complete','phase_observations','completed_measurement','progress']
    for name in unchanged:ok('unchanged_AST_'+name,ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False))
    class NormalizeSentinelConstants(ast.NodeTransformer):
        def visit_Constant(self,node):
            if node.value=='S6C_PACED_ARRIVAL_SENTINEL':return ast.copy_location(ast.Constant('S6C_CANONICAL_PACED_EPOCH4'),node)
            if node.value=='s6c-paced-arrival-sentinel-cell-result.v1':return ast.copy_location(ast.Constant('s6c-canonical-paced-cell-result.v1'),node)
            return node
    for name in ('worker','read_cell_chain','run'):
        normalized=NormalizeSentinelConstants().visit(deepcopy(b[name]));ok('only_sentinel_schema_constants_'+name,ast.dump(a[name],include_attributes=False)==ast.dump(normalized,include_attributes=False))
    return dict(status='PASS_MODEL_FREE',sentinel_checks=len(passed),checks=passed,inherited_original_guard_checks=original,models=0,native_calls=0)





@L.observer_entry
def source_checks():
    tests=checks();driver,common,spec,eb=load_native();proposal,pb=panel();routes=candidate_routes(spec,['C088','C105']);index,ib=L.read_bound(spec['input_index']['path'],spec['input_index']);lookup={(r['case_id'],r['stream']):r for r in index['rows']}
    pair={tap:lookup['S45_08_07',tap] for tap in ('O0','O1')};source=source_record(pair,ib)
    for row in pair.values():verify_pcm(row)
    L.verify(source['telemetry']);galleries={key:L.select_gallery(driver,spec,row) for key,row in routes.items()}
    for tap in ('O0','O1'):
        if galleries['C088',tap]!=galleries['C105',tap]:raise ValueError('Actual gallery binding differs across sentinel pair')
    if abs(source['duration_sec']*12-536.34525)>1e-9:raise ValueError('Unexpected source duration')
    prior,pb0=L.read_bound(REPORT/'paced_candidates/SOURCE_CHECKS_V3.json');review,review_b=L.read_bound(REPORT/'independent_review/PACED_COMPONENT_REVIEW_V3.json')
    for name in ('s6c_paced_epoch4.py','README_S6C_PACED_EPOCH4.md'):
        expected=next(b for b in prior['sources'] if Path(b['path']).name==name);L.verify(expected)
    result=dict(schema=SCHEMA,status='PASS_MODEL_FREE_SOURCE_ADMISSION',created_utc=L.utc(),checks=tests,execution_manifest=eb,panel=pb,input_index=ib,sources=source_bindings(),held_original_source_checks=pb0,held_original_independent_review=review_b,verified_canonical_sources=[source],verified_views=2,requested_cells=12,total_source_sec=source['duration_sec']*12,matched_profile_rows=list(routes.values()),same_gallery=True,original_native_function=L.protected_identities(driver)['native'],new_audio_files=0,model_calls=0,native_calls=0,scope='Exploratory one-case arrival-boundary diagnostic selected after an observed discrepancy. Source/guard admission only; no native session, finalist selection, broad accuracy claim or change to main16+4/gate6.')
    return common.save(REPORT/'paced_arrival_sentinel/observer_fast_v2/SOURCE_CHECKS_V1.json',result,immutable=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('checks','source-checks','prepare','run','worker'));p.add_argument('--namespace');p.add_argument('--candidates');p.add_argument('--panel-mode',choices=('arrival_sentinel',),default='arrival_sentinel');p.add_argument('--deadline-utc');p.add_argument('--manifest',type=Path);p.add_argument('--quiet-admission',type=Path);p.add_argument('--job-id');p.add_argument('--owner-lease',type=Path);a=p.parse_args()
    required={'prepare':('namespace','candidates','deadline_utc'),'run':('manifest','quiet_admission'),'worker':('manifest','job_id','owner_lease')}
    if any(getattr(a,k) is None for k in required.get(a.action,())):p.error('Missing explicit arguments for '+a.action)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    sys.dont_write_bytecode=True
    print(json.dumps({'checks':checks,'source-checks':source_checks,'prepare':lambda:prepare(a),'run':lambda:run(a),'worker':lambda:worker(a)}[a.action](),indent=2))
