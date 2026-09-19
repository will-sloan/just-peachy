"""Exact historical B36 continuous session; README_S6C_LONG_B36_V1.md."""
from __future__ import annotations
import argparse, ast, hashlib, importlib, json, math, os, re, shutil, subprocess, sys, tempfile, time, traceback, uuid, wave
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import psutil

HERE=Path(__file__).resolve().parent;SIM=HERE.parent;RUN='20260910T123540Z'
REPORT=SIM/'reports/S6C'/RUN;STAGING=SIM/'staging/s6c'/RUN;PAYLOAD=Path('G:/Just_Peachy_S6C')/RUN
EDGE=SIM.parents[2]/'.edge-speech-env/python.exe'
SCHEMA='s6c-exact-historical-b36-continuous.v1'
RESULT_SCHEMA='s6c-exact-historical-b36-continuous-result.v1'
KIND='S6C_EXACT_HISTORICAL_B36_CONTINUOUS'
COMPOSITION=REPORT/'long_session/v1/COMPOSITION.json'
COMPOSITION_SHA='bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3'
OLD=SIM/'reports/S6B/20260909T230840Z'
EPOCH_SHA='ea0d57f0af68c2b7fd8ac4298154d3d460c804e0a6650887383a804709864673'
SEALED_SHA='2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e'
PINS={'s6c_long_native_epoch4.py':'9c15795253b17722af6b56e8bc3eb524ce68665bfa2d5de2d95ef940f690ea9b',
      's6c_paced_controls.py':'abacc5db48137a808a9417c26e44b921be817dda4e6271efe7a9fb7dfd7bf6a9',
      's6b_paced.py':'e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9'}
for name,wanted in PINS.items():
    if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=wanted:raise ValueError('Held source changed: '+name)
import s6c_long_native_epoch4 as L
import s6c_paced_controls as C
if Path(L.__file__).resolve()!=HERE/'s6c_long_native_epoch4.py' or Path(C.__file__).resolve()!=HERE/'s6c_paced_controls.py':raise ValueError('Wrong dependency import')
LIMITS=dict(c_free_min_bytes=50*2**30,g_free_min_bytes=75*2**30,host_available_min_bytes=12*2**30,new_output_cap_bytes=120*2**30,pending_cell_reserve_bytes=4*2**30)
DURATION=1827.426625;FRAMES=29238826;TIMEOUT=DURATION+120.;CLEANUP_MAX_SEC=25.
DEADLINE=L.DEADLINE
LIMIT_NOTES=dict(native_lane_drain_timeout_sec=30,native_final_join_sec=65,scheduler_max_pending_events=20000,scheduler_max_events=1000000,scheduler_max_utterances=4096,tracker_max_tracks=256,
    scope='Original historical limits unchanged. Native observer stores display/events in memory and scans session bytes; saturation/timeout is an outcome, not repaired by this wrapper. The outer source+120 s execution deadline has up to25 s additional owned cleanup, reported separately.')

def require(value,message):
    if not value:raise ValueError(message)

def read_bound(path,b=None):return L.read_bound(path,b)
def bind(path):return L.bind(path)
def digest(value):return L.digest(value)
def utc():return L.utc()
def small(b):return {k:b[k] for k in ('path','bytes','sha256')}

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    require(not path.exists(),'Preserve existing artifact: '+str(path))
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    temp.rename(path)
    return bind(path)

def roots(namespace):
    require(isinstance(namespace,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,60}',namespace),'Simple fresh namespace required')
    return REPORT/'long_b36'/namespace,PAYLOAD/'long_b36'/namespace

def source_bindings():return [bind(HERE/name) for name in ('s6c_long_b36_v1.py','README_S6C_LONG_B36_V1.md',*PINS)]

def load_driver():
    driver,observer,deps=C.dependencies()
    require(Path(driver.__file__).resolve()==HERE/'s6b_paced.py' and bind(driver.__file__)['sha256']==PINS['s6b_paced.py'],'Original driver required')
    tree=ast.parse(Path(driver.__file__).read_bytes());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
    return driver,observer,deps,hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()

def authorities():
    sealed,sb=read_bound(OLD/'LOCAL_ARTIFACT_INDEX.json');require(sb['sha256']==SEALED_SHA,'Sealed S6B authority changed')
    ep=OLD/'EPOCH2_EXECUTION_MANIFEST.json';matches=[small(r) for r in sealed['artifacts'] if Path(r['path']).resolve()==ep.resolve()]
    require(len(matches)==1 and matches[0]['sha256']==EPOCH_SHA,'Exact sealed S6B epoch2 required')
    spec,eb=read_bound(ep,matches[0]);registry,rb=read_bound(spec['effective_profile_registry']['path'],spec['effective_profile_registry'])
    entries=[r for r in registry['profiles'] if r['profile_id']=='B36'];require(len(entries)==1,'Exact B36 registry entry required');entry=entries[0]
    profile,pb=read_bound(entry['file_binding']['path'],entry['file_binding']);require(profile==entry['profile'],'Original B36 profile file differs')
    require(entry['recipe_id']=='R0' and profile['schema_version']=='edge-research-profile.v2' and profile['tracker']['mode']=='original_common' and profile['tracker']['max_tracks']==256,'Original B36 semantics differ')
    require(profile['xvf']['mode']=='none' and profile['tracker']['cues_enabled'] is False and profile['input']==dict(tap='mono',gain=1.,already_gained=True),'Original B36 input/cue settings differ')
    composition,cb=read_bound(COMPOSITION);require(cb['sha256']==COMPOSITION_SHA,'Exact existing composition required')
    require(composition['duration_sec']==DURATION and composition['duration_samples']==FRAMES and composition['source_count']==38 and composition['no_new_gain'] is True and composition['epoch']['sha256']=='1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb','Exact source lineage/whole duration differs')
    return dict(spec=spec,epoch=eb,sealed=sb,registry=rb,entry=entry,profile_file=pb,composition=composition,composition_binding=cb)

def make_job(a,tap):
    require(tap in ('O0','O1'),'One admitted mono source tap required')
    m=a['composition'];return dict(job_id='B36_CONTINUOUS_'+tap+'_R1',profile_id='B36',recipe_id='R0',case_id=None,source_kind='EXISTING_CONTINUOUS_COMPOSITION',stream=tap,repetition=1,
        input=m['audio'][tap],input_pcm_sha256=m['pcm_sha256'][tap],duration_sec=DURATION,source_sample_rate=16000,realtime=True,telemetry=None,profile=deepcopy(a['entry']['profile']),app_path=str(Path(a['spec']['root'])/'app'),assets=a['spec']['assets'],
        mode='EXACT_ORIGINAL_S6B_B36_CONTINUOUS',epoch='S6B_epoch2',gain_context='Existing once-gained concatenation with unchanged within-capture timing and declared2s between-capture silence; adapter unity.',clip_policy='Entire existing1827.426625-second mono composition; no copying, trim, inserted silence or regeneration by this wrapper')

def asset_bindings(spec):
    result=[]
    for asset in spec['assets']:
        b=asset['binding'];require(b['path']==asset['path'] and b['sha256']==asset['sha256'] and isinstance(b['bytes'],int) and not isinstance(b['bytes'],bool) and b['bytes']>0,'Nested historical asset binding differs')
        require(set(b)=={'path','bytes','sha256'} and re.fullmatch('[a-f0-9]{64}',b['sha256']),'Complete asset binding required');result.append(b)
    require(result and len({b['path'] for b in result})==len(result),'Distinct fixed model assets required')
    return result

def validate_plan(plan,a):
    require(plan['schema']==SCHEMA and plan['status']=='PREPARED_NO_MODELS_STARTED','Exact continuous schema/status required')
    r,p=roots(plan['namespace']);require(plan['report_root']==str(r) and plan['output_root']==str(p) and plan['payload_root']==str(p),'Separate continuous namespace differs')
    require(plan['actual_execution_epoch']=='S6B_epoch2' and plan['source_composition_epoch']=='S6C_epoch2' and plan['source_kind']=='EXISTING_CONTINUOUS_COMPOSITION','Historical execution/source lineage differs')
    for k,v in dict(historical_epoch=a['epoch'],source_sealed_index=a['sealed'],b36_registry_entry=a['entry'],composition=a['composition_binding'],runtime_versions=a['spec']['runtime_versions'],resource_limits=LIMITS,timeout_sec=TIMEOUT,cleanup_max_sec=CLEANUP_MAX_SEC,original_limits=LIMIT_NOTES,worker_limit=1,inner_threads=1).items():require(plan[k]==v,'Plan admission differs: '+k)
    require(plan['deadline_utc']==L.dt(plan['deadline_utc']).isoformat() and L.dt(plan['deadline_utc'])<=DEADLINE,'Declared study deadline differs')
    require(len(plan['jobs'])==1,'Exactly one continuous worker job required');job=plan['jobs'][0];expected=make_job(a,job['stream']);expected['job_key']=digest(expected);require(job==expected,'Exact historical profile/source/job differs')
    require(plan['driver']['sha256']==PINS['s6b_paced.py'] and Path(plan['driver']['path']).resolve()==HERE/'s6b_paced.py','Original worker driver changed')
    copied=dict(plan);key=copied.pop('manifest_key');require(key==digest(copied),'Manifest digest differs')

def verify_native_dependencies(plan,a,audio=True):
    app=Path(a['spec']['root'])/'app'
    files=[small(b) for b in a['spec']['execution_files'] if app in Path(b['path']).parents]
    require({str(p.resolve()) for p in app.rglob('*.py')}=={str(Path(b['path']).resolve()) for b in files},'Historical APP inventory differs')
    for b in files:L.verify(b)
    for b in asset_bindings(a['spec']):L.verify(b)
    if audio:
        job=plan['jobs'][0];L.verify(job['input']);h=hashlib.sha256()
        with wave.open(job['input']['path'],'rb') as f:
            require((f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getcomptype(),f.getnframes())==(1,2,16000,'NONE',FRAMES),'Exact whole continuous PCM16 required')
            for raw in iter(lambda:f.readframes(65536),b''):h.update(raw)
        require(h.hexdigest()==job['input_pcm_sha256'],'Existing composition PCM body differs')
    return files

def admit(path,full=False):
    plan,pb=read_bound(path);a=authorities();validate_plan(plan,a);r,_=roots(plan['namespace']);require(Path(pb['path'])==r/'MANIFEST.json','Manifest path differs')
    require(plan['sources']==source_bindings(),'Held wrapper/dependencies changed')
    driver,observer,deps,worker_ast=load_driver();require(plan['original_worker_ast_sha256']==worker_ast and plan['driver']==bind(driver.__file__) and plan['observer_dependencies']==deps,'Exact original worker/observer differs')
    require(Path(sys.executable).resolve()==EDGE.resolve(),'Exact EDGE interpreter required');driver.check_runtime_versions(plan['runtime_versions'])
    if full:verify_native_dependencies(plan,a)
    return plan,pb,a,driver,observer

def prepare(args):
    a=authorities();driver,observer,deps,worker_ast=load_driver();r,p=roots(args.namespace)
    require(not r.exists() and not p.exists(),'Fresh continuous namespace required')
    require(Path(sys.executable).resolve()==EDGE.resolve(),'Exact EDGE interpreter required');driver.check_runtime_versions(a['spec']['runtime_versions'])
    deadline=L.dt(args.deadline_utc);require(datetime.now(timezone.utc)+timedelta(seconds=TIMEOUT+CLEANUP_MAX_SEC+60)<deadline<=DEADLINE,'Full bounded continuous session must fit the deadline')
    job=make_job(a,args.tap);job['job_key']=digest(job)
    plan=dict(schema=SCHEMA,status='PREPARED_NO_MODELS_STARTED',created_utc=utc(),namespace=args.namespace,report_root=str(r),output_root=str(p),payload_root=str(p),
        actual_execution_epoch='S6B_epoch2',source_composition_epoch='S6C_epoch2',source_kind='EXISTING_CONTINUOUS_COMPOSITION',historical_epoch=a['epoch'],source_sealed_index=a['sealed'],b36_registry_entry=a['entry'],composition=a['composition_binding'],
        runtime_versions=a['spec']['runtime_versions'],sources=source_bindings(),driver=bind(driver.__file__),observer_dependencies=deps,original_worker_ast_sha256=worker_ast,
        jobs=[job],resource_limits=LIMITS,timeout_sec=TIMEOUT,cleanup_max_sec=CLEANUP_MAX_SEC,original_limits=LIMIT_NOTES,worker_limit=1,inner_threads=1,deadline_utc=deadline.isoformat(),
        scope='One newly executed exact historical B36 host session, if separately authorized. Original worker function and all APP/profile settings unchanged. Existing S6C composition supplies one mono tap; no naming gallery/cues, source rewrite, simulated long result, physical capture or CM5 inference.')
    plan['manifest_key']=digest(plan);validate_plan(plan,a);verify_native_dependencies(plan,a);r.mkdir(parents=True);p.mkdir(parents=True)
    return save(r/'MANIFEST.json',plan)

def owner_state(pid,created):
    require(isinstance(pid,int) and not isinstance(pid,bool) and pid>0 and isinstance(created,(int,float)) and not isinstance(created,bool) and math.isfinite(created) and created>0,'Finite process identity required')
    try:return dict(alive=abs(psutil.Process(pid).create_time()-created)<.001,error=None)
    except psutil.NoSuchProcess:return dict(alive=False,error=None)
    except psutil.Error as exc:return dict(alive=None,error=repr(exc))

def states(owned):return [dict(pid=p,creation_time=c,**owner_state(p,c)) for p,c in owned.items()]

def quiet(excluded=()):
    skip={os.getpid(),*excluded};found=[]
    for p in psutil.process_iter(['pid','cmdline','create_time']):
        if p.pid in skip:continue
        argv=p.info['cmdline'] or [];names={Path(v).name.lower() for v in argv}
        active=L.worker_command(argv) or (any(n.startswith(('s6c_paced_','s6c_long_')) and n.endswith('.py') for n in names) and any(v in argv for v in ('run','worker')))
        if active:
            s=owner_state(p.pid,p.info['create_time']);require(s['alive'] is False,'Other study worker/owner active or unverified: '+str(p.pid));found.append(s)
    for path in REPORT.glob('epoch*/workers/*.json'):
        row,_=read_bound(path)
        if row['pid'] not in skip:require(owner_state(row['pid'],row['creation_time'])['alive'] is False,'Other registered model worker active or unknown')
    return found

def resources(plan,excluded=(),reserve=False):
    quiet(excluded)
    value=dict(c_free_bytes=shutil.disk_usage('C:/').free,g_free_bytes=shutil.disk_usage('G:/').free,available_ram_bytes=psutil.virtual_memory().available,
        new_S6C_output_bytes=C.strict_bytes(PAYLOAD)+C.strict_bytes(REPORT)+C.strict_bytes(STAGING))
    C.validate_resource_sample(value,plan['resource_limits'],reserve);return value

def validate_worker_result(result,job,native_owner,out):
    require(result['status']=='COMPLETE' and result['job_key']==job['job_key'],'Actual worker completion/key required')
    require((result['pid'],result['creation_time'])==(native_owner['pid'],native_owner['creation_time']),'Actual native owner differs')
    require(result['source_duration_sec']==DURATION and result['complete_pcm_samples']==FRAMES and result['native_pcm_exact'] is True and result['asr_cursor_complete'] is True,'Complete whole source/ASR required')
    require(result['journal']['sha256']==job['input_pcm_sha256'] and result['journal']['bytes']==FRAMES*2,'Native full journal differs')
    require(result['empty_gallery'] is True and result['hardware_calls']==0 and result['truth_passed_to_predictor'] is False,'Native context differs')
    require(all(result['numeric_pools'][k]=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'Inner numeric pools differ')
    root=Path(out).resolve();session=Path(result['session_dir']).resolve();require(root/'sessions' in session.parents,'Native session outside owned namespace')
    for key,name in (('events','events.jsonl'),('journal','audio_spool.pcm16'),('summary_binding','session_summary.json')):require(Path(result[key]['path']).resolve()==session/name,'Native artifact path differs')
    require(Path(result['display_events']['path']).resolve()==root/'DISPLAY_EVENTS.json','Native display path differs')
    t=result['summary']['telemetry'];require(t['asr_cursor_sec']==DURATION and t['source_duration_sec']==DURATION,'Summary source cursor differs')
    require(all(t.get(k,0)==0 for k in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures')),'Native loss counter differs')
    delivery=result['native_dispatch_delivery'];require(delivery is not None and all(delivery[k] is True for k in ('no_gaps_or_duplicates','starts_at_zero','ends_at_full_duration','exact_samples')),'Original B36 dispatch proof required')
    require(result['baseline_dispatch_instrumentation_unavailable'] is False,'B36 dispatch instrumented route differs')

def worker(args):
    plan,pb,a,driver,observer=admit(args.manifest,full=True);job=plan['jobs'][0];root=Path(plan['output_root'])/'jobs'/job['job_id']
    lease,lb=read_bound(args.owner_lease);require(Path(args.owner_lease).resolve()==REPORT/'PACED_QUIET_OWNER.json' and lease['kind']==KIND and lease['manifest']==pb and owner_state(lease['pid'],lease['creation_time'])['alive'] is True,'Exact live parent quiet lease required')
    me=psutil.Process();o=dict(pid=me.pid,creation_time=me.create_time(),argv=me.cmdline());quiet((lease['pid'],))
    require(all(os.environ.get(k)=='1' for k in driver.NUMERIC_KEYS),'Explicit inner pools1 required before original worker')
    require(not (root/'WORKER_IDENTITY.json').exists(),'Prior native attempt must remain preserved')
    save(root/'CONTINUOUS_ADMISSION.json',dict(schema=SCHEMA,status='STARTED',owner=o,manifest=pb,job=job,quiet_lease=lb,actual_execution_epoch='S6B_epoch2',historical_epoch=plan['historical_epoch'],source_composition_epoch='S6C_epoch2',composition=plan['composition'],driver=plan['driver']))
    L.verify(pb);fn=driver.worker;started=time.monotonic();error=None;nb=None;status='FAILED';initial_ast=plan['original_worker_ast_sha256']
    try:
        driver.worker(argparse.Namespace(manifest=Path(pb['path']),job_id=job['job_id'],timeout=TIMEOUT))
        native,nb=read_bound(root/'WORKER_RESULT.json');validate_worker_result(native,job,o,root)
        require(driver.worker is fn and load_driver()[3]==initial_ast,'Original native worker changed')
        status='NATIVE_COMPLETE'
    except BaseException:error=traceback.format_exc();raise
    finally:
        save(root/'CONTINUOUS_OUTCOME.json',dict(schema=RESULT_SCHEMA,status=status,created_utc=utc(),owner=o,manifest=pb,job_key=job['job_key'],native_result=nb,error=error,original_worker_function_unchanged=driver.worker is fn,elapsed_sec=time.monotonic()-started,
            actual_execution_epoch='S6B_epoch2',historical_epoch=plan['historical_epoch'],source_composition_epoch='S6C_epoch2',composition=plan['composition'],process_scope='This native child can still be exiting; coordinator completion requires observed closure.'))

def expected_argv(manifest,lock):return [str(EDGE),str(Path(__file__).resolve()),'worker','--manifest',str(Path(manifest).resolve()),'--owner-lease',str(lock)]

def terminate_owned(owned,deadline=None,started=None):
    started=time.monotonic() if started is None else started;deadline=started+CLEANUP_MAX_SEC if deadline is None else deadline;errors=[]
    for action,wait in (('terminate',10.),('kill',10.)):
        for pid,created in reversed(list(owned.items())):
            if time.monotonic()>=deadline:break
            s=owner_state(pid,created)
            if s['alive'] is True:
                try:getattr(psutil.Process(pid),action)()
                except psutil.Error as exc:errors.append(dict(pid=pid,action=action,error=repr(exc)))
            elif s['alive'] is None:errors.append(dict(pid=pid,action='unverified_identity_not_signaled',error=s['error']))
        until=min(deadline,time.monotonic()+wait)
        while time.monotonic()<until and any(s['alive'] is True for s in states(owned)):time.sleep(.1)
    return dict(elapsed_sec=time.monotonic()-started,owners=states(owned),errors=errors)

def release(lock,target,lb,owned_states):
    if any(s['alive'] is not False for s in owned_states):return dict(status='RETAINED_OWNED_CLOSURE_UNVERIFIED',released=False,error=None,owners=owned_states)
    return L.release_lease(lock,target,lb)

def close_unregistered_child(child,owned,deadline=None):
    """A Popen handle is owned even if subsequent PID/creation lookup failed."""
    if child is None or child.pid in owned:return None
    deadline=time.monotonic()+CLEANUP_MAX_SEC if deadline is None else deadline
    result=dict(pid=child.pid,creation_time=None,process_handle_exited=None,identity_and_descendants_unverified=True,error=None)
    try:
        if child.poll() is None and time.monotonic()<deadline:
            child.terminate()
            remaining=deadline-time.monotonic()
            try:
                if remaining>0:child.wait(timeout=min(5.,remaining))
            except subprocess.TimeoutExpired:
                if time.monotonic()<deadline:
                    child.kill();remaining=deadline-time.monotonic()
                    if remaining>0:child.wait(timeout=min(5.,remaining))
        result['process_handle_exited']=child.poll() is not None
    except Exception:result['error']=traceback.format_exc()
    return result

def cleanup_attempt(child,owned):
    started=time.monotonic();deadline=started+CLEANUP_MAX_SEC
    unregistered=close_unregistered_child(child,owned,deadline)
    result=terminate_owned(owned,deadline,started);result['unregistered_child_handle']=unregistered
    remaining=deadline-time.monotonic()
    if child is not None and remaining>0:
        try:child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:pass
        except Exception:result['final_reap_error']=traceback.format_exc()
    result['elapsed_sec']=time.monotonic()-started
    result['shared_deadline_sec']=CLEANUP_MAX_SEC
    result['deadline_scope']='One shared between-operation deadline; blocking OS operations cannot be preempted. No new wait starts after remaining budget is exhausted.'
    return result

def final_owner_states(owned,child):
    result=states(owned)
    if child is not None and child.pid not in owned:
        result.append(dict(pid=child.pid,creation_time=None,alive=None,error='Successful Popen lacked admitted PID/creation and descendant accounting; quiet lease retained.',process_handle_exited=child.poll() is not None))
    return result

def trajectory_counts(periodic):
    require(isinstance(periodic,int) and not isinstance(periodic,bool) and periodic>=0,'Nonnegative periodic count required')
    return dict(periodic_process_samples=periodic,terminal_process_samples=1,process_samples=periodic+1)

def run(args):
    plan,pb,a,driver,observer=admit(args.manifest,full=True);r=Path(plan['report_root']);p=Path(plan['output_root']);job=plan['jobs'][0];out=p/'jobs'/job['job_id']
    q,qb=read_bound(args.quiet_admission);require(q['status']=='AUTHORIZED_FOR_QUIET_LONG_B36' and q['manifest']==pb and q['all_other_model_hil_work_stopped'] is True and q['all_heavy_analysis_stopped'] is True,'Explicit exact quiet admission required')
    deadline=min(L.dt(q['expires_utc']),L.dt(plan['deadline_utc']));require(datetime.now(timezone.utc)+timedelta(seconds=TIMEOUT+CLEANUP_MAX_SEC+60)<deadline,'Insufficient reserved quiet interval')
    require(not out.exists(),'No overwrite/retry of prior native attempt; use separately reviewed fresh namespace')
    initial=resources(plan,reserve=True);lock=REPORT/'PACED_QUIET_OWNER.json';require(not lock.exists(),'Existing quiet lease requires explicit resolution')
    me=psutil.Process();owner=dict(pid=me.pid,creation_time=me.create_time(),argv=me.cmdline());inv=r/'invocations'/uuid.uuid4().hex;inv.mkdir(parents=True)
    lb=save(lock,dict(kind=KIND,**owner,manifest=pb,quiet_admission=qb,created_utc=utc()));owned={};child=None;error=None;status='FAILED';nb=None;result_binding=None;cleanup=None;started=time.monotonic();samples=0
    try:
        save(inv/'ADMISSION.json',dict(status='STARTED',owner=owner,manifest=pb,quiet_admission=qb,quiet_lease=lb,initial_resources=initial,created_utc=utc(),original_limits=LIMIT_NOTES))
        with (inv/'OBSERVER_EVENTS.jsonl').open('x',encoding='utf-8') as events:
            def emit(value):events.write(json.dumps(value,allow_nan=False)+'\n');events.flush();os.fsync(events.fileno())
            reader=observer.OptionalLiveReader(driver.read,[out/'LIVE.json'],inv/'rejected_snapshots',emit)
            argv=expected_argv(args.manifest,lock);env=dict(os.environ);env.update({k:'1' for k in driver.NUMERIC_KEYS});env['PYTHONDONTWRITEBYTECODE']='1'
            out.mkdir(parents=True);L.verify(pb);L.verify(qb);L.verify(lb);t0=time.monotonic();lastbeat=-20.
            with (out/'stdout.log').open('x',encoding='utf-8') as stdout,(out/'PROCESS_SAMPLES.jsonl').open('x',encoding='utf-8') as trajectory:
                child=subprocess.Popen(argv,env=env,stdout=stdout,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                save(inv/'CHILD_SPAWN.json',dict(status='POPEN_SUCCEEDED_IDENTITY_PENDING',pid=child.pid,creation_time=None,argv=argv,manifest=pb,job_key=job['job_key'],created_utc=utc(),scope='A physical launch occurred; PID creation/descendant identity is not yet established.'))
                process=psutil.Process(child.pid);owned[child.pid]=process.create_time()
                native_owner=dict(pid=child.pid,creation_time=owned[child.pid]);launch=save(out/'LAUNCH.json',dict(**native_owner,argv=argv,manifest=pb,job_key=job['job_key'],created_utc=utc()))
                print(json.dumps(dict(phase='B36_CONTINUOUS_LAUNCH',**native_owner,source_sec=DURATION,timeout_sec=TIMEOUT)),flush=True)
                while child.poll() is None:
                    tree=C.sample_tree(process,driver)
                    for member in tree['processes']:
                        require(member['pid'] not in owned or owned[member['pid']]==member['creation_time'],'Observed PID was reused; retain prior ownership')
                        owned[member['pid']]=member['creation_time']
                    live=reader(out/'LIVE.json') if (out/'LIVE.json').exists() else None;elapsed=time.monotonic()-t0
                    value=dict(phase='periodic',created_utc=utc(),elapsed_sec=elapsed,tree=tree,live=live,coordinator_rss_bytes=me.memory_info().rss)
                    trajectory.write(json.dumps(value,allow_nan=False)+'\n');trajectory.flush();samples+=1
                    if elapsed-lastbeat>=20:
                        current=resources(plan,owned);driver.save(r/'HEARTBEAT.json',dict(phase='B36_CONTINUOUS',created_utc=utc(),owner=owner,native_owner=native_owner,elapsed_sec=elapsed,source_duration_sec=DURATION,source_cursor=(live or {}).get('telemetry',{}),resources=current,samples=samples,eta_scope='No prior continuous throughput; nominal remaining source is not a measured completion ETA.'));lastbeat=elapsed
                        print(json.dumps(dict(phase='B36_CONTINUOUS',elapsed_sec=elapsed,samples=samples)),flush=True)
                    if elapsed>TIMEOUT or datetime.now(timezone.utc)>=deadline or any((root/name).exists() for root in (r,REPORT) for name in ('STOP_REQUEST','STOP_NOW','STOP_REQUEST.json')):raise InterruptedError('Owned continuous time/stop boundary')
                    time.sleep(.5)
                trajectory.write(json.dumps(dict(phase='terminal_after_child_exit',created_utc=utc(),elapsed_sec=time.monotonic()-t0,child_returncode=child.returncode,owned_processes=states(owned),live=None,live_scope='Terminal process-closure record; no interpolated LIVE sample'),allow_nan=False)+'\n');trajectory.flush();os.fsync(trajectory.fileno())
            require(child.returncode==0,'Original continuous native worker failed; preserve all artifacts')
            native,nb=read_bound(out/'WORKER_RESULT.json');validate_worker_result(native,job,native_owner,out)
            outcome,ob=read_bound(out/'CONTINUOUS_OUTCOME.json');require(outcome['schema']==RESULT_SCHEMA and outcome['status']=='NATIVE_COMPLETE' and outcome['manifest']==pb and outcome['native_result']==nb and outcome['job_key']==job['job_key'] and outcome['error'] is None and outcome['original_worker_function_unchanged'] is True,'Strict original native outcome differs')
            require(outcome['owner']['pid']==native_owner['pid'] and outcome['owner']['creation_time']==native_owner['creation_time'] and outcome['owner']['argv']==argv,'Original child command/identity differs')
            closed=states(owned);require(all(s['alive'] is False for s in closed),'Owned process survives or closure unavailable')
            admission,ab=read_bound(out/'CONTINUOUS_ADMISSION.json');require(admission['owner']==outcome['owner'] and admission['manifest']==pb and admission['job']==job and admission['quiet_lease']==lb,'Native admission chain differs')
            final_resources=resources(plan);artifacts=[nb,ob,ab,launch,bind(out/'PROCESS_SAMPLES.jsonl'),native['events'],native['journal'],native['display_events'],native['summary_binding']]
            for b in artifacts:L.verify(b)
            result_binding=save(r/'RESULT.json',dict(schema=RESULT_SCHEMA,status='COMPLETE_NATIVE_AND_OWNED_CHILD_CLOSED',created_utc=utc(),manifest=pb,owner=owner,native_owner=native_owner,job=job,
                actual_execution_epoch='S6B_epoch2',historical_epoch=plan['historical_epoch'],source_composition_epoch='S6C_epoch2',composition=plan['composition'],source_kind=plan['source_kind'],native_result=nb,native_outcome=ob,
                artifacts=artifacts,owned_processes=closed,all_owned_processes_closed=True,observer_stats=reader.snapshot(),**trajectory_counts(samples),source_duration_sec=DURATION,source_duration_samples=FRAMES,total_observed_child_sec=time.monotonic()-t0,
                final_resources=final_resources,original_worker_unchanged=True,original_limits=LIMIT_NOTES,scope='One physical native attempt and one successful continuous session. RSS/USS/commit/threads/CPU/IO/queues are observations at stored sampling times, not continuous maxima. Quiet lease release is independently recorded by CLOSURE.'))
            status='NATIVE_COMPLETE'
    except BaseException:
        error=traceback.format_exc();cleanup=cleanup_attempt(child,owned)
        raise
    finally:
        owned_final=final_owner_states(owned,child);pre=save(inv/'NATIVE_OUTCOME.json',dict(schema=SCHEMA,status=status,created_utc=utc(),manifest=pb,owner=owner,native_result=nb,continuous_result=result_binding,error=error,cleanup=cleanup,owned_processes=owned_final,total_invocation_sec=time.monotonic()-started))
        released=release(lock,inv/'QUIET_LEASE_RELEASED.json',lb,owned_final)
        closure=save(inv/'CLOSURE.json',dict(schema=SCHEMA,status='NATIVE_COMPLETE_QUIET_RELEASED' if status=='NATIVE_COMPLETE' and released['status']=='RELEASED' else 'FAILED_OR_RELEASE_UNVERIFIED',created_utc=utc(),manifest=pb,owner=owner,pre_release_outcome=pre,continuous_result=result_binding,error=error,owned_processes=owned_final,lease_release=released,coordinator_scope='This coordinator can still be exiting; inventory must observe its PID+creation separately.'))
        if released['status']!='RELEASED':raise RuntimeError('Quiet lease retained/release unverified; see durable closure')
    return dict(status=status,result=result_binding,closure=closure)

def checks():
    checks=[]
    def good(name,fn):fn();checks.append(dict(name=name,status='PASS'))
    def bad(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError,RuntimeError):checks.append(dict(name=name,status='PASS_REJECTED'));return
        raise AssertionError(name+' unexpectedly passed')
    good('simple_namespace',lambda:roots('check_v1'))
    for name in ('../escape','a/b','',r'a\b'):bad('namespace_'+repr(name),lambda name=name:roots(name))
    for pid,ct in ((True,1.),(1,float('nan')),(1,False),(0,1.),(1,float('inf'))):bad('finite_owner_'+repr((pid,ct)),lambda pid=pid,ct=ct:owner_state(pid,ct))
    with patch.object(psutil,'Process',side_effect=psutil.NoSuchProcess(100)):good('missing_owner_is_closed',lambda:require(owner_state(100,1.)['alive'] is False,'closed'))
    with patch.object(psutil,'Process',side_effect=psutil.AccessDenied(100)):good('denied_owner_is_unknown',lambda:require(owner_state(100,1.)['alive'] is None,'unknown'))
    for alive in (True,None):good('retain_lease_'+str(alive),lambda alive=alive:require(release(Path('x'),Path('y'),{},[dict(alive=alive)])['status']=='RETAINED_OWNED_CLOSURE_UNVERIFIED','retain'))
    class FakeChild:
        pid=123
        def __init__(self):self.done=False;self.terminated=0
        def poll(self):return 0 if self.done else None
        def terminate(self):self.terminated+=1;self.done=True
        def kill(self):self.done=True
        def wait(self,timeout):return self.poll()
    child=FakeChild()
    with patch.object(psutil,'Process',side_effect=psutil.AccessDenied(123)):
        bad('injected_successful_popen_identity_denied',lambda:require(owner_state(123,1.)['alive'] is True,'identity unavailable'))
        good('unregistered_child_owned_handle_reaped',lambda:require(close_unregistered_child(child,{})['process_handle_exited'] is True and child.terminated==1,'handle not closed'))
    unknown=final_owner_states({},child);good('unregistered_child_lease_retained_after_handle_exit',lambda:require(release(Path('x'),Path('y'),{},unknown)['status']=='RETAINED_OWNED_CLOSURE_UNVERIFIED' and unknown[0]['creation_time'] is None,'unknown closure'))
    class TimeoutChild(FakeChild):
        def __init__(self,clock):self.clock=clock;self.waits=[];self.terminated=0
        def poll(self):return None
        def terminate(self):self.terminated+=1
        def kill(self):pass
        def wait(self,timeout):self.waits.append(timeout);self.clock[0]+=timeout;raise subprocess.TimeoutExpired('fixture',timeout)
    clock=[0.];stuck=TimeoutChild(clock)
    with patch.object(time,'monotonic',side_effect=lambda:clock[0]):
        cleaned=cleanup_attempt(stuck,{})
    good('shared_cleanup_budget_after_both_handle_timeouts',lambda:require(stuck.waits==[5.,5.,15.] and cleaned['elapsed_sec']==25. and clock[0]==25. and cleaned['unregistered_child_handle']['error'] is not None,'separate cleanup budgets'))
    good('trajectory_periodic_terminal_total',lambda:require(trajectory_counts(9)==dict(periodic_process_samples=9,terminal_process_samples=1,process_samples=10),'sample counts'))
    for n in (True,-1,1.5):bad('invalid_trajectory_count_'+str(n),lambda n=n:trajectory_counts(n))
    asset=dict(path='x.onnx',sha256='a'*64,binding=dict(path='x.onnx',bytes=5,sha256='a'*64));good('nested_asset_positive',lambda:require(asset_bindings(dict(assets=[asset]))==[asset['binding']],'asset'))
    for name,value in [('path','other'),('sha256','b'*64),('bytes',False),('bytes',0)]:
        changed=deepcopy(asset);changed['binding'][name]=value;bad('nested_asset_'+name+'_'+str(value),lambda changed=changed:asset_bindings(dict(assets=[changed])))
    sample=dict(c_free_bytes=60*2**30,g_free_bytes=85*2**30,available_ram_bytes=13*2**30,new_S6C_output_bytes=10*2**30)
    good('resource_positive',lambda:C.validate_resource_sample(sample,LIMITS,True))
    for key,value in [('c_free_bytes',49*2**30),('g_free_bytes',74*2**30),('available_ram_bytes',11*2**30),('new_S6C_output_bytes',119*2**30)]:bad('resource_'+key,lambda key=key,value=value:C.validate_resource_sample({**sample,key:value},LIMITS,True))
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'x.json';b=save(p,dict(x=1));good('exact_buffer_read',lambda:require(read_bound(p,b)[0]==dict(x=1),'read'));bad('no_overwrite',lambda:save(p,dict(x=2)))
        p.write_text('{"x":2}',encoding='utf-8');bad('changed_buffer',lambda:read_bound(p,b))
        lock=Path(d)/'lock';lb=save(lock,dict(owner='fixture'));good('actual_lease_release',lambda:require(release(lock,Path(d)/'archive',lb,[dict(alive=False)])['status']=='RELEASED','release'))
        lock=Path(d)/'lock2';lb=save(lock,dict(owner='fixture'))
        with patch.object(Path,'rename',side_effect=PermissionError('fixture denial')):
            good('lease_rename_failure_retained',lambda:require(release(lock,Path(d)/'archive2',lb,[dict(alive=False)])['status']=='RELEASE_FAILED' and lock.exists(),'retain'))
        out=Path(d)/'worker';session=out/'sessions/session1';job=dict(job_key='j',input_pcm_sha256='a'*64);native_owner=dict(pid=123,creation_time=1.)
        b=lambda name:dict(path=str(session/name),bytes=1,sha256='b'*64)
        native=dict(status='COMPLETE',job_key='j',pid=123,creation_time=1.,source_duration_sec=DURATION,complete_pcm_samples=FRAMES,native_pcm_exact=True,asr_cursor_complete=True,
            journal=dict(path=str(session/'audio_spool.pcm16'),sha256='a'*64,bytes=FRAMES*2),empty_gallery=True,hardware_calls=0,truth_passed_to_predictor=False,
            numeric_pools={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},session_dir=str(session),events=b('events.jsonl'),summary_binding=b('session_summary.json'),display_events=dict(path=str(out/'DISPLAY_EVENTS.json')),
            summary=dict(telemetry=dict(asr_cursor_sec=DURATION,source_duration_sec=DURATION,audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0)),
            native_dispatch_delivery=dict(no_gaps_or_duplicates=True,starts_at_zero=True,ends_at_full_duration=True,exact_samples=True),baseline_dispatch_instrumentation_unavailable=False)
        good('complete_original_native_metadata',lambda:validate_worker_result(native,job,native_owner,out))
        for name,path,value in [('status',['status'],'FAILED'),('key',['job_key'],'other'),('pid',['pid'],124),('creation',['creation_time'],2.),('duration',['source_duration_sec'],45.),('samples',['complete_pcm_samples'],FRAMES-1),('pcm',['native_pcm_exact'],False),('asr',['asr_cursor_complete'],False),('hash',['journal','sha256'],'c'*64),('bytes',['journal','bytes'],3),('cursor',['summary','telemetry','asr_cursor_sec'],0.),('drop',['summary','telemetry','audio_frames_dropped'],1),('gallery',['empty_gallery'],False),('hardware',['hardware_calls'],1),('truth',['truth_passed_to_predictor'],True),('pool',['numeric_pools','OMP_NUM_THREADS'],'2'),('dispatch',['native_dispatch_delivery','exact_samples'],False),('event_path',['events','path'],str(Path(d)/'elsewhere.jsonl'))]:
            changed=deepcopy(native);target=changed
            for k in path[:-1]:target=target[k]
            target[path[-1]]=value;bad('native_'+name,lambda changed=changed:validate_worker_result(changed,job,native_owner,out))
    return checks

def source_checks(args):
    a=authorities();driver,observer,deps,worker_ast=load_driver();require(Path(sys.executable).resolve()==EDGE.resolve(),'Exact EDGE required');driver.check_runtime_versions(a['spec']['runtime_versions']);results=checks();assets=asset_bindings(a['spec']);results.append(dict(name='actual_nested_asset_metadata',status='PASS',assets=len(assets)))
    job=make_job(a,'O0');job['job_key']=digest(job)
    for tap in ('O0','O1'):
        value=make_job(a,tap);require(value['input']==a['composition']['audio'][tap] and value['input_pcm_sha256']==a['composition']['pcm_sha256'][tap],'Source selection');results.append(dict(name='actual_metadata_source_'+tap,status='PASS'))
    require(job['profile']==a['entry']['profile'] and job['telemetry'] is None and job['profile']['runtime']['asr_threads']==job['profile']['runtime']['speaker_threads']==job['profile']['runtime']['punctuation_threads']==1,'Historical profile equality')
    r,p=roots('source_fixture_only');plan=dict(schema=SCHEMA,status='PREPARED_NO_MODELS_STARTED',namespace='source_fixture_only',report_root=str(r),output_root=str(p),payload_root=str(p),actual_execution_epoch='S6B_epoch2',source_composition_epoch='S6C_epoch2',source_kind='EXISTING_CONTINUOUS_COMPOSITION',
        historical_epoch=a['epoch'],source_sealed_index=a['sealed'],b36_registry_entry=a['entry'],composition=a['composition_binding'],runtime_versions=a['spec']['runtime_versions'],resource_limits=LIMITS,timeout_sec=TIMEOUT,cleanup_max_sec=CLEANUP_MAX_SEC,original_limits=LIMIT_NOTES,worker_limit=1,inner_threads=1,deadline_utc=DEADLINE.isoformat(),jobs=[job],driver=bind(driver.__file__))
    plan['manifest_key']=digest(plan);validate_plan(plan,a);results.append(dict(name='actual_metadata_prospective_plan',status='PASS'))
    for name,path,value in [('profile',['jobs',0,'profile','tracker','max_tracks'],16),('cue',['jobs',0,'telemetry'],dict(path='other')),('tap_audio',['jobs',0,'input'],a['composition']['audio']['O1']),('audio_hash',['jobs',0,'input_pcm_sha256'],'0'*64),('short_duration',['jobs',0,'duration_sec'],45.),('gain',['jobs',0,'profile','input','gain'],2.),('app',['jobs',0,'app_path'],'current/app'),('assets',['jobs',0,'assets'],[]),('epoch',['actual_execution_epoch'],'epoch4'),('source_epoch',['source_composition_epoch'],'S6B_epoch2'),('workers',['worker_limit'],2),('timeout',['timeout_sec'],600.),('ram',['resource_limits','host_available_min_bytes'],4*2**30),('state_caps',['original_limits','native_lane_drain_timeout_sec'],120),('schema',['schema'],'s6c-canonical-paired-paced.v1'),('namespace',['namespace'],'../escape')]:
        changed=deepcopy(plan);target=changed
        for k in path[:-1]:target=target[k]
        target[path[-1]]=value
        for j in changed['jobs']:
            copied=dict(j);copied.pop('job_key');j['job_key']=digest(copied)
        changed.pop('manifest_key');changed['manifest_key']=digest(changed)
        try:validate_plan(changed,a)
        except (ValueError,KeyError,TypeError):results.append(dict(name='actual_rekeyed_plan_'+name,status='PASS_REJECTED'))
        else:raise AssertionError('Prospective plan mutation accepted: '+name)
    tree=ast.parse(Path(driver.__file__).read_bytes());entry=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker');require(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='start_file' for n in ast.walk(entry)),'Original continuous entry point')
    preserved=STAGING/'long_b36/draft_source_checks_v1'
    prior,priorb=read_bound(preserved/'SOURCE_CHECKS_DRAFT_V1.json')
    resolver=[]
    for b in prior['source_bindings']:
        old=preserved/Path(b['path']).name
        if old.exists():
            actual=bind(old);require(actual['sha256']==b['sha256'] and actual['bytes']==b['bytes'],'Preserved draft source differs');resolver.append(dict(original=b,preserved=actual))
    held=STAGING/'long_b36/before_asset_binding_repair_v1';old,oldb=read_bound(held/'SOURCE_CHECKS_V1.json');oldresolver=[]
    for b in old['source_bindings']:
        path=held/Path(b['path']).name
        if path.exists():
            actual=bind(path);require(actual['sha256']==b['sha256'] and actual['bytes']==b['bytes'],'Preserved V1 source differs');oldresolver.append(dict(original=b,preserved=actual))
    held2=STAGING/'long_b36/before_cleanup_deadline_repair_v2';old2,old2b=read_bound(held2/'SOURCE_CHECKS_V2.json');resolver2=[]
    for b in old2['source_bindings']:
        path=held2/Path(b['path']).name
        if path.exists():
            actual=bind(path);require(actual['sha256']==b['sha256'] and actual['bytes']==b['bytes'],'Preserved V2 source differs');resolver2.append(dict(original=b,preserved=actual))
    return save(args.output,dict(schema=SCHEMA,status='PASS_MODEL_FREE_SOURCE_CHECKS',created_utc=utc(),checks=results,check_count=len(results),source_bindings=source_bindings(),historical_epoch=a['epoch'],sealed_authority=a['sealed'],composition=a['composition_binding'],profile_file=a['profile_file'],original_worker_ast_sha256=worker_ast,observer_dependencies=deps,original_limits=LIMIT_NOTES,model_calls=0,native_sessions=0,new_audio_files=0,prior_draft_checks=priorb,preserved_draft_sources=resolver,prior_v1_checks=oldb,preserved_v1_sources=oldresolver,prior_v2_checks=old2b,preserved_v2_sources=resolver2,
        scope='Metadata-only historical/profile/composition admission and bounded synthetic guards. Actual native success, source PCM and model asset current-byte admission are not asserted; prepare/run rehash them. No real manifest or quiet lease created.'))

def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('checks','prepare','worker','run'));p.add_argument('--output',type=Path);p.add_argument('--namespace');p.add_argument('--tap',choices=('O0','O1'),default='O0');p.add_argument('--deadline-utc');p.add_argument('--manifest',type=Path);p.add_argument('--owner-lease',type=Path);p.add_argument('--quiet-admission',type=Path);a=p.parse_args()
    if a.action=='checks':require(a.output is not None,'checks requires fresh --output');return source_checks(a)
    if a.action=='prepare':require(a.namespace and a.deadline_utc,'prepare requires namespace/deadline');return prepare(a)
    require(a.manifest is not None,'Exact manifest required')
    if a.action=='worker':require(a.owner_lease is not None,'worker requires live parent lease');return worker(a)
    require(a.quiet_admission is not None,'run requires root quiet admission');return run(a)

if __name__=='__main__':print(json.dumps(main(),allow_nan=False))
