"""Prepared native manager census/export; README_FIELD_LOCAL_EXPORT_V1.md."""
import os,sys,json,hashlib,resource,signal,fcntl,time,subprocess,shutil,re
from pathlib import Path
from datetime import datetime,timezone

def run(request,modules):
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    signal.alarm(80);deadline=time.monotonic()+75
    def ticks(pid):
        try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
        except FileNotFoundError:return None
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
    def frame(value):
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>262144:raise ValueError('Bounded output frame')
        sys.stdout.buffer.write(str(len(raw)).encode()+b'\n'+raw);sys.stdout.buffer.flush()
    frame(dict(type='HELLO',owner=owner))
    if type(request) is not dict or set(request)!={'admission','files'}:raise ValueError('Exact export request')
    a=request['admission']
    fields={'schema','phase','issued_utc','expires_utc','unit','manager_binding','lifecycle','lifecycle_sha256','module_sha256','external_owners','closed_owners','mirror_maximum_bytes'}
    if type(a) is not dict or set(a)!=fields or a['schema']!='just-peachy.manager-export-admission.v1':
        raise ValueError('Exact fresh read-only admission')
    now=datetime.now(timezone.utc);start=datetime.fromisoformat(a['issued_utc']);end=datetime.fromisoformat(a['expires_utc'])
    if start.tzinfo is None or end.tzinfo is None or not start<=now<end<=datetime.fromisoformat('2026-10-01T17:42:44+00:00'):
        raise ValueError('Current operation and hard deadline')
    if not 90<=(end-now).total_seconds() or (end-start).total_seconds()>600:
        raise ValueError('Finite operation with closure/backup reserve')
    if a['phase'] not in ('census','export') or not re.fullmatch('jp-field-manager-'+a['phase']+r'-v[1-9][0-9]*[.]service',a['unit']):
        raise ValueError('Exact admitted phase/unit')
    if type(modules) is not dict or not 1<=len(modules)<=64 or sum(len(v.encode()) for v in modules.values())>2097152:
        raise ValueError('Original auxiliary capsule limits')
    for name,source in modules.items():
        if not re.fullmatch('[a-zA-Z0-9_]+',name) or type(source) is not str or not 0<len(source.encode())<=131072:
            raise ValueError('Bounded source member')
        if name not in sys.modules or sys.modules[name].__file__!='<manager-export-injected:'+name+'>':
            raise ValueError('Exact injected module origin')
    if {n:hashlib.sha256(v.encode()).hexdigest() for n,v in modules.items()}!=a['module_sha256']:
        raise ValueError('Exact admitted module bytes')
    required={'field_local_manager_owners_v1','field_local_manager_tree_v1','field_operator_broker_streamed_mirror_v1','field_host_budget_v1','field_local_manager_ssh_mirror_v1','field_owner_binding_v1'}
    if not required<=set(modules):raise ValueError('Every directly imported project module must be pinned')
    from field_local_manager_owners_v1 import lifecycle,identity,key,decode,encoded
    from field_local_manager_tree_v1 import validate,inventory,plan
    from field_operator_broker_streamed_mirror_v1 import ancestors,identity as file_identity
    from field_host_budget_v1 import real
    from field_local_manager_ssh_mirror_v1 import receive_json
    from field_owner_binding_v1 import decode as old_owners
    b=validate(a['manager_binding']);root=Path(b['root']);campaign=root.parent
    life=lifecycle(a['lifecycle'],a['lifecycle_sha256'])
    if boot!=life['boot_id']:raise ValueError('Fresh actual boot differs')
    for row in life['baseline_owners']:
        if ticks(row['pid'])!=row['start_ticks']:raise ValueError('Fresh baseline identity differs')
    if os.uname().machine!='aarch64' or 'Compute Module 5' not in Path('/proc/device-tree/model').read_text():
        raise ValueError('Actual CM5/aarch64')
    if int(Path('/sys/class/block/mmcblk0/size').read_text())*512!=31268536320:raise ValueError('Physical32GB device')
    memory=Path('/proc/meminfo').read_text()
    total=next(int(x.split()[1])*1024 for x in memory.splitlines() if x.startswith('MemTotal:'))
    if not 1500000000<total<2200000000:raise ValueError('Actual2GB target')
    pins={'JustPeachy/install/current.json':'install_sha256','JustPeachy/data/live_config.json':'live_config_sha256','.config/kanshi/config':'display_config_sha256'}
    for rel,k in pins.items():
        p=Path.home()/rel
        if p.stat().st_size>65536 or hashlib.sha256(p.read_bytes()).hexdigest()!=life[k]:
            raise ValueError('Observed baseline config drift')
    def guard(initial=False):
        if time.monotonic()>=deadline or datetime.now(timezone.utc)>=end:raise TimeoutError('Export deadline')
        ram=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
        if ram<(850 if initial else 192)*1024**2 or shutil.disk_usage(campaign).free<5*1024**3:
            raise RuntimeError('RAM or storage floor')
        if Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()!='closed':
            raise RuntimeError('Capture is active')
    guard(True)
    names=['CPUQuotaPerSecUSec','AllowedCPUs','TasksMax','LimitAS','LimitASSoft','LimitSTACK','LimitSTACKSoft','LimitFSIZE','LimitFSIZESoft','RuntimeMaxUSec','TimeoutStopUSec','MainPID','ActiveState']
    cmd=['systemctl','--user','show',a['unit']]
    for n in names:cmd+=['-p',n]
    properties=subprocess.check_output(cmd,text=True,timeout=5)
    values=dict(x.split('=',1) for x in properties.splitlines())
    expected={'CPUQuotaPerSecUSec':'2s','AllowedCPUs':'2-3','TasksMax':'64','LimitAS':'134217728','LimitASSoft':'134217728','LimitSTACK':'1048576','LimitSTACKSoft':'1048576','LimitFSIZE':'0','LimitFSIZESoft':'0','RuntimeMaxUSec':'1min 30s','TimeoutStopUSec':'10s','MainPID':str(owner['pid']),'ActiveState':'active'}
    if values!=expected:raise ValueError('Exact actual export service properties')
    external=a['external_owners']
    if type(external) is not list or not 1<=len(external)<=8 or len({key(o) for o in external})!=len(external):
        raise ValueError('Exact registered phase owners')
    prior=old_owners(a['closed_owners'])
    def dead(rows):
        for o in rows:
            identity(o)
            if o['boot_id']==boot and ticks(o['pid'])==o['start_ticks']:
                raise RuntimeError('Recorded owner remains alive')
    dead(external+prior)
    allocation=b['allocation'];maximum=allocation['metadata_maximum_bytes']+allocation['local_backup_per_recording']
    if type(a['mirror_maximum_bytes']) is not int or a['mirror_maximum_bytes']!=maximum:
        raise ValueError('Full independent manager-tree backup reservation')
    with (campaign/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease,(Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hardware:
        for f in (lease,hardware):fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--plain','--full','--no-pager','--no-legend','jp-*'],text=True,timeout=5)
        if [x.split()[0] for x in units.splitlines() if x.strip()]!=[a['unit']]:
            raise RuntimeError('Unexpected active research unit')
        if not root.exists():
            if a['phase']!='census' or request['files'] is not None:raise ValueError('Absent root is census-only')
            frame(dict(type='NO_TARGET_ROOT',owner=owner,properties=properties,source=str(root),physical_closure_claimed=False));return
        ancestors(root)
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
            before,dirs=inventory(root,deadline,a['manager_binding'])
            pins={};records={}
            for name,ident in sorted(before.items()):
                guard();p=root/name;h=hashlib.sha256()
                with p.open('rb',buffering=0) as stream:
                    left=ident[2]
                    while left:
                        guard();block=stream.read(min(16384,left))
                        if not block:raise EOFError('Source truncated')
                        h.update(block);left-=len(block)
                    if stream.read(1):raise RuntimeError('Source grew')
                if file_identity(real(p))!=ident:raise RuntimeError('Source identity changed')
                pins[name]=dict(bytes=ident[2],sha256=h.hexdigest())
                if 'owner' in p.name.lower() and p.name.endswith('.json'):
                    if ident[2]>16384:raise ValueError('Owner envelope limit')
                    raw=p.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=pins[name]['sha256']:raise RuntimeError('Owner bytes changed')
                    records[name]=raw
            observed=decode(records,a['manager_binding']['policy_sha256'])
            dead(observed['identities'])
            launch_keys={key(r['owner']) for r in observed['records'] if r['path'].startswith('launches/')}
            if not launch_keys<={key(o) for o in external}:raise ValueError('Journal owners must match registered actual phase owners')
            value=plan(root,pins,deadline,a['manager_binding'])
            if value['source_identities']!=before or set(value['directories'])!=dirs:raise RuntimeError('Tree changed after census')
            if a['phase']=='census':
                if request['files'] is not None:raise ValueError('Census has no supplied file success facts')
                frame(dict(type='CENSUS',owner=owner,source=str(root),properties=properties,files=pins,directories=sorted(dirs),ownership=observed,external_owners=external,physical_closure_claimed=False,recording_success_claimed=False))
                return
            if encoded(request['files'])!=encoded(pins):raise ValueError('Exact independently pinned whole census')
            frame(dict(type='READY',owner=owner,properties=properties,source=str(root),ownership=observed,external_owners=external))
            if receive_json(sys.stdin.buffer,deadline)!=dict(ack=owner):raise ValueError('Exact owner ACK')
            public={k:v for k,v in value.items() if k!='source_identities'};frame(public)
            for name,row in sorted(pins.items()):
                guard();p=root/name;ancestors(p.parent)
                if file_identity(real(p))!=before[name]:raise RuntimeError('Changed pre-send identity')
                frame(dict(file=name,bytes=row['bytes']));h=hashlib.sha256();left=row['bytes']
                with p.open('rb',buffering=0) as stream:
                    while left:
                        guard();block=stream.read(min(16384,left))
                        if not block:raise EOFError('Truncated send')
                        sys.stdout.buffer.write(block);sys.stdout.buffer.flush();h.update(block);left-=len(block)
                    if stream.read(1):raise RuntimeError('Source grew during send')
                if h.hexdigest()!=row['sha256'] or file_identity(real(p))!=before[name]:raise RuntimeError('Changed sent source')
            after,dirs_after=inventory(root,deadline,a['manager_binding']);dead(external+observed['identities'])
            if after!=before or dirs_after!=dirs:raise RuntimeError('Final whole source changed')
            frame(dict(status='SOURCE_TREE_UNCHANGED',files=len(pins),bytes=value['bytes']))
        finally:os.close(fd)
