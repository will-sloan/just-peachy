"""Read-only owned-job probe/closed-output stream. See README_JOB_MONITOR.md."""
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


def kb_fields(raw):
    result={}
    for line in raw.splitlines():
        if ':' not in line:continue
        key,value=line.split(':',1);parts=value.split()
        if len(parts)==2 and parts[1]=='kB' and parts[0].isdigit():result[key]=int(parts[0])*1024
    return result


def sample_memory(status):
    """One bounded read-only sample of this already verified service only."""
    group=status['control_group'];owner=status['owner'];rows=[];complete=True
    members=memory_members(group)
    if not status['closed'] and (owner is None or identity(owner['pid'])!=owner):complete=False
    for pid in sorted(members):
        try:
            before=identity(pid)
            if before is None:complete=False;continue
            process=Path('/proc',str(pid))
            membership=bounded_text(process/'cgroup',4096).splitlines()
            if not any(line.startswith('0::') and (line[3:]==group or line[3:].startswith(group+'/')) for line in membership):
                complete=False;continue
            fields=kb_fields(bounded_text(process/'status'))
            rollup=kb_fields(bounded_text(process/'smaps_rollup'))
            if identity(pid)!=before:complete=False;continue
            if not {'Rss','Pss'}<=set(rollup) or not {'VmSize','VmPeak','VmSwap'}<=set(fields):
                complete=False;continue
            rows.append(dict(owner=before,rss_bytes=rollup['Rss'],pss_bytes=rollup['Pss'],
                vm_bytes=fields['VmSize'],vm_peak_bytes=fields['VmPeak'],swap_bytes=fields['VmSwap']))
        except (FileNotFoundError,ProcessLookupError,PermissionError):complete=False
    if memory_members(group)!=members:complete=False
    if not status['closed'] and (owner is None or identity(owner['pid'])!=owner):complete=False
    memory=kb_fields(bounded_text(Path('/proc/meminfo'),32768))
    try:temperature=float(bounded_text(Path('/sys/class/thermal/thermal_zone0/temp'),128).strip())/1000
    except (FileNotFoundError,ValueError):temperature=None
    return dict(schema='just-peachy.sampled-owned-unit-memory.v1',sampled_unix=time.time(),
        sample_monotonic=time.monotonic(),unit=status['unit'],invocation_id=status['invocation_id'],
        control_group=group,main_owner=owner,processes=rows,observed_processes=len(members),
        complete_process_sample=complete and len(rows)==len(members),continuous_peak_claimed=False,
        rss_bytes=sum(row['rss_bytes'] for row in rows),pss_bytes=sum(row['pss_bytes'] for row in rows),
        vm_bytes=sum(row['vm_bytes'] for row in rows),swap_bytes=sum(row['swap_bytes'] for row in rows),
        available_bytes=memory.get('MemAvailable'),physical_ram_bytes=memory.get('MemTotal'),
        system_swap_used_bytes=memory.get('SwapTotal',0)-memory.get('SwapFree',0),temperature_c=temperature)


def job_limits(job):
    # Only the already issued build20 manual-Stop job has this larger copy reservation.
    if job.get('output_root') == '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/classic-ui-check-07':
        if (job.get('unit') != 'jp-v29-classic-ui-check-07.service'
                or job.get('package_manifest_sha256') != 'f42216e8169aa2b0be0b40c7fd0d9cf45542e2bf04b0e4405a95cc2189437659'
                or job.get('helper_source_sha256') != '4d0bef169c54d90769d50bb0f9a1becb6ae7ff80d438892e6dc7c57d59754b87'
                or type(job.get('maximum_output_bytes')) is not int
                or job['maximum_output_bytes'] != 512*1024**2
                or not 0 < job['deadline_unix']-job['issued_unix'] <= 581):
            raise ValueError('Exact issued job07 manual-Stop closure/copy contract required')
        return 512*1024**2,256
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


def inventory(root,maximum,maximum_files=MAX_FILES,hash_files=True):
    rows=[];total=0;directory_count=0
    for directory,children,files in os.walk(root,followlinks=False):
        directory_count+=1
        if directory_count>maximum_files: raise ValueError('Bounded output directory traversal required')
        if len(children)+len(files)>maximum_files:
            raise ValueError('Bounded output directory membership required')
        for name in children:
            child=Path(directory)/name
            if child.is_symlink(): raise ValueError('Symlink in output tree')
        for name in files:
            path=Path(directory)/name
            relative=path.relative_to(root).as_posix()
            if len(relative)>512 or path.resolve(strict=True)!=path:
                raise ValueError('Output member path changed')
            before=source_identity(path)
            total+=before['bytes']
            if total>maximum or len(rows)>=maximum_files:
                raise ValueError('Full closed output exceeds its explicit reservation')
            checksum=None
            if hash_files:
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    while raw:=stream.read(CHUNK): digest.update(raw)
                checksum=digest.hexdigest()
            if source_identity(path)!=before: raise ValueError('Output changed while hashing')
            rows.append(dict(path=relative,identity=before,sha256=checksum))
    return sorted(rows,key=lambda row:row['path'])


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


def closed_again(job,status):
    _,closed=inspect(dict(job,owner=status['owner'],output_identity=status['output_identity'],
                         control_group=status['control_group'],invocation_id=status['invocation_id']))
    if not closed['closed']:raise ValueError('Owned job reopened during closed transfer')
    return closed


def segment(root,request,job,status):
    row=request['entry'];name=row['path'];relative=PurePosixPath(name)
    if (relative.is_absolute() or relative.as_posix()!=name or '..' in relative.parts
        or '\\' in name or len(name)>512):raise ValueError('Exact safe segment member')
    path=root/name
    if path.resolve(strict=True)!=path or source_identity(path)!=row['identity']:
        raise ValueError('Pinned closed segment source changed')
    offset=request['offset'];count=request['count'];size=row['identity']['bytes']
    if (type(offset) is not int or type(count) is not int or not 0<=count<=SEGMENT
        or not 0<=offset<=size or offset+count>size or count==0 and size!=0):
        raise ValueError('Bounded exact source segment')
    emit(dict(kind='SEGMENT',entry=row,offset=offset,count=count))
    digest=hashlib.sha256();cursor=offset
    with path.open('rb') as stream:
        stream.seek(offset)
        while cursor<offset+count:
            raw=stream.read(min(CHUNK,offset+count-cursor))
            if not raw:raise ValueError('Closed segment truncated')
            emit(dict(kind='CHUNK',path=name,offset=cursor,data=base64.b64encode(raw).decode()))
            digest.update(raw);cursor+=len(raw)
    if source_identity(path)!=row['identity']:raise ValueError('Closed segment source changed during read')
    closure=closed_again(job,status)
    emit(dict(kind='SEGMENT_END',path=name,offset=offset,bytes=count,sha256=digest.hexdigest(),closure=closure))


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
    # Actual identity is already emitted before reading the job or project files.
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536: raise ValueError('Job request cap')
    request=strict(raw);job=request['job']
    maximum=job['maximum_output_bytes']
    output_limit,maximum_files=job_limits(job)
    if type(maximum) is not int or not 1<=maximum<=output_limit:
        raise ValueError('Finite full-output reservation required')
    root,status=inspect(job)
    if request.get('sample_memory') is True:
        if request['mode']!='status':raise ValueError('Memory sampling is a status-only option')
        status['memory_sample']=sample_memory(status)
    emit(status)
    if request['mode']=='status': return
    if request['mode']=='segment':
        if not status['closed']:raise ValueError('Segment requires exact closure')
        segment(root,request,job,status);return
    if request['mode']=='catalog':
        if not status['closed']:raise ValueError('Catalog requires exact closure')
        # An hour's multi-gigabyte allowance must not require one full-tree
        # content hash inside a15s read-only helper. Every transferred segment
        # supplies its own native hash; identities/membership are checked twice.
        streamed_hashes=maximum_files==2048
        rows=inventory(root,maximum,maximum_files,hash_files=not streamed_hashes)
        emit(dict(kind='MANIFEST',files=len(rows),bytes=sum(row['identity']['bytes'] for row in rows),
            hash_mode='streamed_segments' if streamed_hashes else 'whole_file'))
        for row in rows:emit(dict(kind='MANIFEST_ENTRY',**row))
        closure=closed_again(job,status)
        emit(dict(kind='CATALOG_END',files=len(rows),bytes=sum(row['identity']['bytes'] for row in rows),
            manifest_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            closure=closure,mirror_scope='all_regular_output_files',empty_directories_copied=False))
        return
    if request['mode']!='mirror' or not status['closed'] or maximum_files==2048:
        raise ValueError('Full output mirror requires exact natural closure first')
    before=inventory(root,maximum,maximum_files)
    # Individual MANIFEST_ENTRY frames keep protocol memory and line size finite.
    emit(dict(kind='MANIFEST',files=len(before),bytes=sum(row['identity']['bytes'] for row in before)))
    for row in before: emit(dict(kind='MANIFEST_ENTRY',**row))
    for row in before:
        path=root/row['path']
        if source_identity(path)!=row['identity']: raise ValueError('Closed source identity changed')
        emit(dict(kind='FILE',path=row['path']))
        offset=0
        with path.open('rb') as stream:
            while raw:=stream.read(CHUNK):
                emit(dict(kind='CHUNK',path=row['path'],offset=offset,data=base64.b64encode(raw).decode()))
                offset+=len(raw)
        if source_identity(path)!=row['identity']: raise ValueError('Source changed during transfer')
        emit(dict(kind='FILE_END',path=row['path'],bytes=offset,sha256=row['sha256']))
    after=inventory(root,maximum,maximum_files)
    if after!=before: raise ValueError('Full output membership or bytes changed during transfer')
    _,closed=inspect(dict(job,owner=status['owner'],output_identity=status['output_identity'],
                         control_group=status['control_group'],invocation_id=status['invocation_id']))
    if not closed['closed']: raise ValueError('Owned job reopened during closed transfer')
    emit(dict(kind='COMPLETE',files=len(before),bytes=sum(row['identity']['bytes'] for row in before),
        manifest_sha256=hashlib.sha256(json.dumps(before,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        closure=closed,mirror_scope='all_regular_output_files',empty_directories_copied=False))


if __name__=='__main__': main()
