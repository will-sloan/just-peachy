"""Separate exact historical B36 pacing; see README_S6C_PACED_B36_V1.md."""
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
CONTROLS=('B36',)
RESOURCE_LIMITS=dict(c_free_min_bytes=50*2**30,g_free_min_bytes=75*2**30,
    host_available_min_bytes=4*2**30,new_output_cap_bytes=120*2**30,pending_cell_reserve_bytes=512*2**20)
GLOBAL_DEADLINE=datetime.strptime(E.RUN,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)+timedelta(hours=71)

SOURCE_PLAN_SHA='22033c693b7009eec2c86e1c0b2235826984bbfb8cacc914730216204893de86'
SOURCE_COORDINATOR_SHA='abacc5db48137a808a9417c26e44b921be817dda4e6271efe7a9fb7dfd7bf6a9'
SCHEMA='s6c-historical-paced-b36.v1'


def source_authority(path):
    b=E.bind(path)
    if b['sha256']!=SOURCE_PLAN_SHA:raise ValueError('Exact preserved80-cell B00/B01 source plan required')
    source=SCRIPTS/'s6c_paced_controls.py'
    if E.bind(source)['sha256']!=SOURCE_COORDINATOR_SHA:raise ValueError('Preserved historical coordinator source changed')
    original=load_module(source,'s6c_b36_original_control_authority')
    base=original.admit_manifest(Path(path))
    if len(base['jobs'])!=80 or base['profiles']!=['B00','B01'] or len(base['cases'])!=16:raise ValueError('Exact original80-cell scope differs')
    spec=verified(base['historical_epoch']);registry=verified(spec['effective_profile_registry'])
    entry=next(r for r in registry['profiles'] if r['profile_id']=='B36')
    profile=entry['profile']
    if entry['recipe_id']!='R0' or profile['profile_id']!='B36' or profile['schema_version']!='edge-research-profile.v2' or profile['tracker']['mode']!='original_common':raise ValueError('Exact B36 original common tracker required')
    if profile['tracker']['max_tracks']!=256 or profile['xvf']['mode']!='none' or profile['tracker']['cues_enabled'] or profile['input']!={'tap':'mono','gain':1.0,'already_gained':True}:raise ValueError('Historical B36 tracker/cue/gain semantics changed')
    E.verify(entry['file_binding'])
    if E.read(entry['file_binding']['path'])!=profile:raise ValueError('B36 native profile file differs from sealed registry')
    return b,base,spec,entry


def converted_jobs(base,entry):
    from copy import deepcopy
    jobs=[]
    for original in base['jobs']:
        if original['profile_id']!='B01':continue
        job=deepcopy(original);job.update(profile_id='B36',recipe_id=entry['recipe_id'],profile=deepcopy(entry['profile']),
            epoch='s6c_historical_b36_v1',mode='EXACT_ORIGINAL_S6B_B36_PROFILE')
        job['job_id']=f"B36_{job['case_id']}_{job['stream']}_R{job['repetition']}"
        job.pop('job_key');job['job_key']=digest(job);jobs.append(job)
    if len(jobs)!=40:raise ValueError('B36 needs exactly40 matched physical cells')
    return jobs


def validate_b36_plan(plan,base,entry):
    validate_plan_structure(plan)
    if plan['schema']!=SCHEMA or plan['jobs']!=converted_jobs(base,entry):raise ValueError('B36 jobs differ from exact historical profile and matched source metadata')
    for name in ('cases','streams','repetitions','repeat_case_sets','selection','panel','runtime_versions','historical_epoch','source_sealed_index','historical_baseline_authority','resource_limits','deadline_utc','max_wall_sec','timeout_sec'):
        if plan[name]!=base[name]:raise ValueError('Matched historical plan metadata differs: '+name)
    if plan['b36_registry_entry']!=entry:raise ValueError('Exact B36 sealed registry entry differs')


def prepare(args):
    source,base,spec,entry=source_authority(args.source_plan);driver,observer,dep=dependencies();driver.check_runtime_versions(base['runtime_versions'])
    output=safe_namespace(args.namespace)
    if output.exists():raise ValueError('Fresh B36 namespace required')
    if dt(base['deadline_utc'])<=datetime.now(timezone.utc):raise ValueError('Source research deadline expired')
    plan=dict(base);plan.pop('manifest_key');jobs=converted_jobs(base,entry)
    additions=[source,E.bind(__file__),E.bind(Path(__file__).with_name('README_S6C_PACED_B36_V1.md')),entry['file_binding']]
    plan.update(schema=SCHEMA,created_utc=E.utc(),coordinator=E.bind(__file__),profiles=['B36'],jobs=jobs,source_controls_plan=source,
        dependencies=list({b['path']:b for b in base['dependencies']+additions}.values()),output_root=str(output),
        total_audio_sec=sum(j['duration_sec'] for j in jobs),b36_registry_entry=entry,
        method_order='B36 only; exact source case/tap order, same16 first-pass and4 second-pass cases as preserved B00/B01 plan',
        scope='Additional40 newly paced B36 native sessions when authorized; original80 B00/B01 jobs/admission unchanged. No historical run result is reused as current paced evidence.',
        defaults='Exact sealed S6B epoch2 B36 original_common tracker/common scheduler profile and original1-thread research pools; all original numeric fields preserved.')
    validate_b36_plan(plan,base,entry);plan['manifest_key']=digest(plan);output.mkdir(parents=True)
    E.save(output/'MANIFEST.json',plan)
    result=dict(status='PREPARED_NO_MODELS_STARTED',manifest=E.bind(output/'MANIFEST.json'),source_controls_plan=source,jobs=40,
        base_cases=16,repeat_cases=4,streams=['O0','O1'],source_minutes=plan['total_audio_sec']/60,b36_profile=entry['file_binding'],
        historical_epoch=base['historical_epoch'],native_driver=plan['driver'],source_before_after_exact=E.bind(args.source_plan)==source)
    E.save(E.REPORT/'paced_controls'/args.namespace/'PREPARATION.json',result);return result


def admit_manifest(path):
    plan=E.read(path);output=ensure_output(plan['output_root'])
    if Path(path).resolve()!=output/'MANIFEST.json':raise ValueError('B36 manifest/output location mismatch')
    copy=dict(plan);key=copy.pop('manifest_key')
    if digest(copy)!=key:raise ValueError('B36 manifest digest mismatch')
    for b in plan['dependencies']:E.verify(b)
    if plan['coordinator']!=E.bind(__file__):raise ValueError('B36 coordinator differs')
    source,base,spec,entry=source_authority(plan['source_controls_plan']['path'])
    if source!=plan['source_controls_plan']:raise ValueError('Source80-cell plan binding differs')
    validate_b36_plan(plan,base,entry)
    driver,observer,dep=dependencies();driver.check_runtime_versions(plan['runtime_versions'])
    if plan['driver']!=E.bind(SCRIPTS/'s6b_paced.py'):raise ValueError('Original native driver differs')
    for job in plan['jobs']:E.verify(job['input'])
    return plan

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


def stop_requested(output):
    return any((root/name).exists() for root in (Path(output),E.REPORT) for name in ('STOP_REQUEST','STOP_REQUEST.json'))


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


def checks(args):
    import ast
    from copy import deepcopy
    source,base,spec,entry=source_authority(args.source_plan)
    old=ast.parse((SCRIPTS/'s6c_paced_controls.py').read_text());new=ast.parse(Path(__file__).read_text())
    def functions(tree):return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
    left,right=functions(old),functions(new)
    names=('verified','digest','dt','load_module','dependencies','strict_bytes','alive','safe_namespace','ensure_output','stop_requested',
        'validate_plan_structure','quiet_processes','validate_resource_sample','resources','sample_tree','run')
    for name in names:
        if left[name]!=right[name]:raise AssertionError('Original runtime/guard function changed: '+name)
    result_checks=['16 exact original coordinator/resource/observer/ownership function ASTs',
        'sealed historical epoch2 B36 registry/file full profile equal','original80 source manifest admitted and untouched']
    jobs=converted_jobs(base,entry)
    expected={(cid,tap,rep) for rep,ids in ((1,base['cases']),(2,base['repeat_case_sets'][1]['case_ids'])) for cid in ids for tap in ('O0','O1')}
    assert {(j['case_id'],j['stream'],j['repetition']) for j in jobs}==expected and len(jobs)==40
    result_checks.append('exact16 plus4 both-tap40-cell matched grid')
    plan=dict(base,schema=SCHEMA,profiles=['B36'],jobs=jobs,b36_registry_entry=entry,total_audio_sec=sum(j['duration_sec'] for j in jobs))
    validate_b36_plan(plan,base,entry)
    for field,value in [('profile',{}),('app_path','wrong'),('assets',[]),('telemetry',{}),('input',{}),('input_pcm_sha256','wrong'),
        ('gain_context','wrong'),('realtime',False),('source_sample_rate',48000),('duration_sec',1),('recipe_id','R1')]:
        bad=deepcopy(plan);bad['jobs'][0][field]=value
        try:validate_b36_plan(bad,base,entry)
        except ValueError:result_checks.append('rejected changed B36 '+field)
        else:raise AssertionError('Substitution accepted: '+field)
    for field,value in [('worker_limit',2),('jobs',jobs[:-1]),('streams',['O0']),('profiles',['B01']),('cases',base['cases'][:-1]),
        ('resource_limits',{}),('b36_registry_entry',{}),('deadline_utc',GLOBAL_DEADLINE.isoformat()+'changed')]:
        bad=dict(plan);bad[field]=value
        try:validate_b36_plan(bad,base,entry)
        except (ValueError,KeyError):result_checks.append('rejected altered plan '+field)
        else:raise AssertionError('Plan substituted: '+field)
    driver,observer,dependencies_rows=dependencies();driver.check_runtime_versions(base['runtime_versions'])
    assert E.bind(args.source_plan)==source
    out=dict(status='PASS',checks=len(result_checks),details=result_checks,native_calls=0,source_controls_plan=source,
        source=E.bind(__file__),readme=E.bind(Path(__file__).with_name('README_S6C_PACED_B36_V1.md')),
        original_functions=names,dependencies=dependencies_rows,b36_profile=entry['file_binding'],historical_epoch=base['historical_epoch'],
        scope='Original native driver imported only; no engine/model/worker/run called.16 unchanged function ASTs and source/profile/grid fault guards.')
    target=E.REPORT/'paced_controls/B36_ADAPTER_CHECKS_V1.json'
    if target.exists():raise ValueError('Preserve prior fixture output')
    E.save(target,out);return E.bind(target)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('prepare','run','checks'))
    p.add_argument('--source-plan',type=Path,default=PAYLOAD/'paced_controls/controls_v1/MANIFEST.json');p.add_argument('--namespace',default='b36_v1')
    p.add_argument('--manifest',type=Path);p.add_argument('--quiet-admission',type=Path);args=p.parse_args()
    if args.action=='run' and (args.manifest is None or args.quiet_admission is None):p.error('run requires manifest and quiet-admission')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
    print(json.dumps({'prepare':prepare,'run':run,'checks':checks}[args.action](args),indent=2))

