"""Status-only speech readiness for an owned classic job. See README_SPEECH_READY.md."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time

ROOT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'
CHUNK = 16384
MAX_FILES = 256
MAX_OUTPUT = 256*1024**2
SEGMENT = 1024**2


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def emit(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(raw.encode())>65536: raise ValueError('Native protocol line cap')
    sys.stdout.write(raw+'\n');sys.stdout.flush()


def identity(pid):
    try:
        ticks=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:
        return None
    return dict(pid=pid,start_ticks=ticks,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def valid_owner(owner):
    if (type(owner) is not dict or set(owner)!={'pid','start_ticks','boot_id'}
        or type(owner['pid']) is not int or owner['pid']<=0
        or type(owner['start_ticks']) is not int or owner['start_ticks']<=0
        or not re.fullmatch(r'[0-9a-f-]{36}',owner['boot_id'])):
        raise ValueError('Exact actual owner identity required')
    return owner


def read_json(path,maximum=16384):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>maximum:
        raise ValueError('Bounded single-link regular receipt required')
    return strict(path.read_bytes())


def utility(argv):
    child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    owner=identity(child.pid)
    forced=False
    try:
        out,err=child.communicate(timeout=4)
    except subprocess.TimeoutExpired:
        forced=True;child.kill();out,err=child.communicate(timeout=2)
    if len(out)>16384 or len(err)>4096 or owner is None:
        raise ValueError('Bounded directly owned systemctl utility required')
    receipt=dict(owner=owner,returncode=child.returncode,reaped=True,forced=forced,
        exact_owner_gone=identity(owner['pid'])!=owner)
    emit(dict(kind='UTILITY',receipt=receipt))
    if forced or not receipt['exact_owner_gone']:
        raise RuntimeError('Systemctl utility did not close naturally')
    return child.returncode,out.decode('utf-8','strict'),err.decode('utf-8','replace')


def cgroup_empty(group):
    if not isinstance(group,str) or not group.startswith('/user.slice/') or '..' in group.split('/') or '\\' in group:
        raise ValueError('Original owned user cgroup is required')
    path=Path('/sys/fs/cgroup'+group)/'cgroup.events'
    try: raw=path.read_text()
    except FileNotFoundError: return True
    if len(raw)>4096: raise ValueError('Cgroup events cap')
    return dict(row.split() for row in raw.splitlines()).get('populated')=='0'


def source_identity(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
        raise ValueError('Only owned single-link regular output files may be copied')
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns)


def bounded_text(path,maximum=16384):
    with path.open('r') as stream:raw=stream.read(maximum+1)
    if len(raw)>maximum:raise ValueError('Memory sample pseudo-file bound')
    return raw


def memory_members(group):
    if not isinstance(group,str) or not group.startswith('/user.slice/') or '..' in group.split('/') or '\\' in group:
        raise ValueError('Exact owned cgroup required for memory sample')
    root=Path('/sys/fs/cgroup'+group);stack=[root];seen=0;pids=set()
    while stack:
        path=stack.pop();seen+=1
        if seen>64:raise ValueError('Owned cgroup directory bound')
        try:
            rows=bounded_text(path/'cgroup.procs',4096).split()
            for row in rows:
                pid=int(row)
                if pid<=0:raise ValueError('Positive cgroup PID')
                pids.add(pid)
            if len(pids)>64:raise ValueError('Owned cgroup process bound')
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_symlink():raise ValueError('Cgroup link refused')
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                        if len(stack)+seen>64:raise ValueError('Owned cgroup traversal bound')
        except FileNotFoundError:
            continue
    return pids


def job_limits(job):
    optional=re.fullmatch(re.escape(ROOT)+r'(optional-followup-[0-9]{2})',job.get('output_root',''))
    if optional:
        plan=job.get('output_plan',{});mode=plan.get('mode')
        metadata=16*1024**2+300*256*1024
        audio=4800000*6+30*(44+3*4096)+1024**2+metadata
        if mode=='raw_processed':audio+=4800000*4*4+30*2*4096
        primary=metadata+1024**2+10*1024**2
        complete=audio+primary+4*1024**2+16*1024**2
        maximum=max(256*1024**2,complete)
        expected=dict(schema='just-peachy.optional-output-plan.v1',stage='followup_policy',
            source_kind='live',session_seconds=300,mode=mode,audio_and_metadata_bytes=audio,
            additional_primary_allocation_bytes=primary,optional_output_bytes=4*1024**2,
            outer_unit_trace_bytes=16*1024**2,computed_output_bytes=complete,
            native_maximum_output_bytes=maximum,maximum_files=256)
        if (mode not in ('processed','raw_processed')
                or json.dumps(plan,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False)
                or job.get('unit')!='jp-v29-'+optional[1]+'.service'
                or job.get('workflow')!='optional-followup-live-policy'
                or type(job.get('duration_seconds')) is not int or job['duration_seconds']!=300
                or type(job.get('runtime_seconds')) is not int or job['runtime_seconds']!=840
                or job.get('maximum_output_files')!=256 or job.get('maximum_output_bytes')!=maximum
                or job.get('independent_pc_copy_bytes')!=maximum
                or not 0<job['deadline_unix']-job['issued_unix']<=885):
            raise ValueError('Exact computed optional live300 output and lifetime scope required')
        return 512*1024**2,256
    hour=re.fullmatch(re.escape(ROOT)+r'(full-app-hour-[0-9]+)',job.get('output_root',''))
    if hour:
        if (job.get('unit')!='jp-v29-'+hour[1]+'.service'
                or job.get('workflow')!='continuous-full-application-repeated-wav'
                or job.get('duration_seconds')!=3600 or job.get('repeat_input_seconds')!=3600
                or job.get('maximum_output_files')!=2048
                or not 0<job['deadline_unix']-job['issued_unix']<=4725):
            raise ValueError('Exact finite full-application hour scope required')
        return 3*1024**3,2048
    match=re.fullmatch(re.escape(ROOT)+r'(gui-qualification-[0-9]+)',job.get('output_root',''))
    if match:
        if job.get('unit')!='jp-v29-'+match[1]+'.service':
            raise ValueError('Exact GUI output/unit pair required')
        if not 0<job['deadline_unix']-job['issued_unix']<=1545:
            raise ValueError('Finite two-session GUI lifetime required')
        return 1024**3,1024
    return MAX_OUTPUT,MAX_FILES


def inspect(job):
    if job.get('schema')!='just-peachy.native-component-job.v1': raise ValueError('Job schema')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if job['boot_id']!=boot: raise ValueError('Job boot changed')
    unit=job['unit']
    if not re.fullmatch(r'jp-v29-[a-z0-9-]+\.service',unit): raise ValueError('Exact unique job unit')
    root=Path(job['output_root'])
    if not str(root).startswith(ROOT) or '/' in str(root)[len(ROOT):] or not re.fullmatch(r'[a-z0-9-]+',root.name):
        raise ValueError('Exact current-iteration output root required')
    if root.resolve(strict=True)!=root or root.is_symlink(): raise ValueError('Real output root required')
    metadata=root.stat()
    root_identity=dict(device=metadata.st_dev,inode=metadata.st_ino)
    if job.get('output_identity') is not None and job['output_identity']!=root_identity:
        raise ValueError('Output root identity changed')
    _,raw,_=utility(['systemctl','--user','show',unit,
        '--property=ActiveState,SubState,InvocationID,ControlGroup,MainPID,Result,ExecMainStatus'])
    state=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    active=state.get('ActiveState') in ('active','activating','deactivating')
    current_invocation=state.get('InvocationID')
    expected_invocation=job.get('invocation_id')
    if current_invocation and expected_invocation and current_invocation!=expected_invocation:
        raise ValueError('Owned systemd invocation changed')
    group=job.get('control_group') or state.get('ControlGroup')
    if job.get('control_group') and state.get('ControlGroup') and group!=state['ControlGroup']:
        raise ValueError('Owned systemd cgroup changed')
    owner=job.get('owner')
    recaptured=False
    if (root/'OWNER.json').exists():
        actual=valid_owner(read_json(root/'OWNER.json'))
        if owner is not None and valid_owner(owner)!=actual: raise ValueError('Early job owner differs')
        owner=actual;recaptured=True
    if owner is not None:
        valid_owner(owner)
        if owner['boot_id']!=boot: raise ValueError('Owner boot differs')
        if active and state.get('MainPID') not in ('0',str(owner['pid'])):
            raise ValueError('Active service MainPID differs from actual job owner')
    observed=identity(owner['pid']) if owner is not None else None
    owner_gone=owner is not None and observed!=owner
    empty=cgroup_empty(group) if group else False
    exit_receipt=read_json(root/'JOB_EXIT.json') if (root/'JOB_EXIT.json').exists() else None
    if exit_receipt:
        for key,expected in (('owner',owner),('unit',unit),('invocation_id',expected_invocation)):
            if key in exit_receipt and expected is not None and exit_receipt[key]!=expected:
                raise ValueError('Durable job exit identity differs')
    if active:
        _,running,_=utility(['systemctl','--user','list-units','--type=service','--state=running',
            '--plain','--no-legend','jp-v29-*','jp-field-*'])
        other=[line.split()[0] for line in running.splitlines() if line.split() and line.split()[0]!=unit]
        if other: raise ValueError('Another project unit is active: '+','.join(other))
    result=dict(kind='STATUS',unit=unit,owner=owner,owner_recaptured=recaptured,
        observed_owner=observed,exact_owner_gone=owner_gone,cgroup_empty=empty,
        output_identity=root_identity,invocation_id=expected_invocation or current_invocation,
        control_group=group,state=state,job_exit=exit_receipt,
        closed=bool(owner_gone and empty and not active),utility_read_only=True)
    return root,result


def speech_ready(root, status, job):
    """Only the already-owned classic job/session; no model or capture calls."""
    import sqlite3
    import zlib
    if not re.fullmatch(r'classic-ui-check-[0-9]+', root.name):
        raise ValueError('Speech readiness is restricted to an owned classic UI check')
    result = dict(schema='just-peachy.owned-live-speech-ready.v1', ready=False,
        state='WAITING_FOR_ACTUAL_WORKER', sampled_unix=time.time(),
        capture_start_requested=False, model_snapshot_requested=False)
    settings = read_json(root/'DRIVER_SETTINGS.json', 65536)
    if settings['output'] != str(root) or settings['unit'] != status['unit'] or settings['boot_id'] != job['boot_id']:
        raise ValueError('Owned classic settings changed')
    data = Path(settings['data_root'])
    if data != Path('/home/peachyprototype/JustPeachy/data/runtime-v29') or data.resolve(strict=True) != data:
        raise ValueError('Exact canonical existing runtime data root required')
    if settings['selection'].get('input_source') != 'live':
        raise ValueError('Speech READY cannot label a saved replay as a live microphone')
    with os.scandir(root) as entries:
        names = sorted(entry.name for entry in entries if re.fullmatch(r'ACTION_[0-9]{3}\.json', entry.name))
    if len(names) > 128:
        raise ValueError('Classic action membership bound')
    started = []; read_bytes = 0
    for name in names:
        path = root/name; read_bytes += source_identity(path)['bytes']
        if read_bytes > 262144:
            raise ValueError('Status-only action read allocation')
        row = read_json(path,65536)
        if row.get('action') == 'actual-worker-started':
            started.append(row)
    if len(started) > 1:
        raise ValueError('Single owned classic worker is required')
    if not started:
        return result
    launch = Path(started[0]['launch_root'])
    if launch.parent != data/'launches' or not re.fullmatch('[0-9a-f]{32}', launch.name) or launch.resolve(strict=True)!=launch:
        raise ValueError('Actual action must bind one canonical runtime launch')
    request_path=launch/'REQUEST.json'
    if source_identity(request_path)['bytes']>65536:
        raise ValueError('Bounded worker request required')
    with request_path.open('rb') as stream:
        request_raw=stream.read(65537)
    if len(request_raw)>65536 or hashlib.sha256(request_raw).hexdigest()!=started[0]['request_sha256']:
        raise ValueError('Actual classic worker request pin differs')
    request=strict(request_raw)
    if request['selection'] != settings['selection'] or request['policy'] != settings['policy'] or request['unit'] != status['unit']:
        raise ValueError('Owned worker selection/policy/unit differs')
    store = data/'recordings'
    if request['data_root']!=str(store) or store.resolve(strict=True)!=store:
        raise ValueError('Exact owned recording store required')
    session_path=launch/'worker'/'SESSION.json'
    if not session_path.exists():
        return dict(result,state='WORKER_STARTING_NO_SESSION',launch_id=launch.name)
    session=read_json(session_path); worker=valid_owner(session['worker']); session_id=session['session_id']
    if not re.fullmatch('[0-9a-f]{32}',session_id):
        raise ValueError('Exact persistent recording UUID required')
    session_root=store/'sessions'/session_id
    if session_root.resolve(strict=True)!=session_root:
        raise ValueError('Canonical session root required')
    owner_path=session_root/'work'/'source'/'REGISTERED_OWNER.json'
    result.update(launch_id=launch.name,session_id=session_id,worker=worker,worker_alive=identity(worker['pid'])==worker)
    if not owner_path.exists():
        return dict(result,state='SOURCE_NOT_YET_REGISTERED')
    registration=read_json(owner_path)
    if registration.get('schema')!='just-peachy.source-owner.v1':
        raise ValueError('Actual isolated source registration required')
    source=valid_owner(registration['owner'])
    if source['boot_id']!=job['boot_id'] or worker['boot_id']!=job['boot_id']:
        raise ValueError('Current source/worker boot differs')
    group=status['control_group']; members=memory_members(group)
    source_alive=identity(source['pid'])==source
    result.update(source_owner=source,source_alive=source_alive,
        source_in_owned_cgroup=source['pid'] in members,worker_in_owned_cgroup=worker['pid'] in members)
    db_path=store/'history.sqlite3'; db_identity=source_identity(db_path)
    if db_identity['bytes']>128*1024**2:
        raise ValueError('Bounded existing recording metadata database required')
    for suffix in ('-wal','-shm'):
        sidecar=Path(str(db_path)+suffix)
        if sidecar.exists() and source_identity(sidecar)['bytes']>128*1024**2:
            raise ValueError('Bounded real metadata database sidecar required')
    db=sqlite3.connect(db_path.as_uri()+'?mode=ro&cache=private',uri=True,timeout=1)
    try:
        db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-128')
        operations=[0]
        def bound():
            operations[0]+=1
            return int(operations[0]>128)
        db.set_progress_handler(bound,1000)
        db.execute('BEGIN')
        row=db.execute('SELECT status,processed_samples,updated FROM sessions WHERE id=?',(session_id,)).fetchone()
        if row is None or type(row[1]) is not int or row[1]<0:
            raise ValueError('Exact indexed session/count required')
        events=db.execute("SELECT seq,created,payload_encoding,payload_bytes,payload_sha256,CASE WHEN LENGTH(payload)<=65536 THEN payload ELSE NULL END FROM events WHERE session_id=? AND event_type='source_started_physical' ORDER BY seq DESC LIMIT 2",(session_id,)).fetchall()
        if len(events)>1:
            raise ValueError('One physical source start per session required')
        result.update(session_status=row[0],processed_samples=row[1],processed_seconds=row[1]/16000,
            last_audio_commit_unix=row[2],last_audio_commit_age_seconds=max(0,time.time()-row[2]),
            physical_source_started=False)
        if events:
            seq,created,encoding,length,expected,payload=events[0]
            if type(length) is not int or not 0<length<=65536 or payload is None:
                raise ValueError('Bounded physical source start event required')
            if encoding=='json' and isinstance(payload,str):
                raw=payload.encode()
            elif encoding=='zlib-json-v1' and isinstance(payload,bytes):
                decoder=zlib.decompressobj();raw=decoder.decompress(payload,length+1)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError('Physical source event compression/trailing data')
            else:
                raise ValueError('Known bounded source start encoding required')
            if len(raw)!=length or hashlib.sha256(raw).hexdigest()!=expected:
                raise ValueError('Physical source start event pin differs')
            physical=strict(raw)
            if physical.get('kind')!='STARTED' or not isinstance(physical.get('metadata'),dict):
                raise ValueError('Actual physical source STARTED packet required')
            result.update(physical_source_started=True,physical_start_seq=seq,
                physical_start_created_unix=created,physical_start_payload_sha256=expected)
    finally:
        db.close()
    after=source_identity(db_path)
    if (after['device'],after['inode'])!=(db_identity['device'],db_identity['inode']):
        raise ValueError('Recording database identity changed')
    result['source_alive']=identity(source['pid'])==source
    result['worker_alive']=identity(worker['pid'])==worker
    active=(not status['closed'] and status['state'].get('ActiveState')=='active' and
        result['source_alive'] and result['worker_alive'] and result['source_in_owned_cgroup'] and
        result['worker_in_owned_cgroup'] and result['physical_source_started'] and row[0]=='active' and
        row[1]>0 and result['last_audio_commit_age_seconds']<=5 and row[2]<=time.time()+1)
    result.update(ready=bool(active),state='READY_ACCEPTING_LIVE_AUDIO' if active else
        'SOURCE_REGISTERED_AWAITING_RECENT_AUDIO' if result['source_alive'] else 'SOURCE_CLOSED_OR_FAILED',
        interpreted_as='actual owned source start plus recently committed processed audio; not ASR/identity/accuracy proof')
    return result


def main():
    import resource
    import signal
    os.sched_setaffinity(0,{3})
    for kind,value in ((resource.RLIMIT_AS,128*1024**2),(resource.RLIMIT_STACK,1024**2),
                       (resource.RLIMIT_FSIZE,0),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(value,value))
    signal.alarm(15)
    emit(dict(kind='OWNER',owner=identity(os.getpid()),cpu=3,address_space_bytes=128*1024**2,
              stack_bytes=1024**2,file_size_limit=0,alarm_seconds=15))
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536: raise ValueError('Job request cap')
    request=strict(raw);job=request['job']
    if request.get('mode')!='status' or set(request)!={'mode','job'}:
        raise ValueError('Speech helper is exact status-only; no memory/model/transfer mode')
    maximum=job['maximum_output_bytes']
    output_limit,maximum_files=job_limits(job)
    if type(maximum) is not int or not 1<=maximum<=output_limit:
        raise ValueError('Finite full-output reservation required')
    root,status=inspect(job)
    status['speech_ready']=speech_ready(root,status,job)
    emit(status)


if __name__=='__main__': main()