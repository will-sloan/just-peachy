"""Native finite runtime census/export; README_FIELD_RUNTIME_EXPORT_V1.md."""
import os
import sys
import resource
import signal
import fcntl
import hashlib
import json
import re
import struct
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime,timezone

HARD_DEADLINE='2026-10-02T14:14:20+00:00'


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
    hello=json.dumps(dict(type='HELLO',owner=owner),separators=(',',':')).encode()
    sys.stdout.buffer.write(struct.pack('!I',len(hello))+hello);sys.stdout.buffer.flush()
    if type(request) is not dict or set(request)!={'admission','policy','manifest','expected_index_sha256'}:
        raise ValueError('Exact runtime exporter request')
    a=request['admission']
    fields={'schema','phase','issued_utc','expires_utc','unit','policy_sha256','manifest_sha256',
            'lifecycle','lifecycle_sha256','module_sha256','external_owners','closed_owners','mirror_maximum_bytes'}
    if type(a) is not dict or set(a)!=fields or a['schema']!='just-peachy.runtime-export-admission.v1':
        raise ValueError('Fresh exact read-only admission')
    now=datetime.now(timezone.utc);start=datetime.fromisoformat(a['issued_utc']);end=datetime.fromisoformat(a['expires_utc'])
    if (start.tzinfo is None or end.tzinfo is None or start.utcoffset().total_seconds()!=0
            or end.utcoffset().total_seconds()!=0 or not start<=now<end<=datetime.fromisoformat(HARD_DEADLINE)
            or not 90<=(end-now).total_seconds() or (end-start).total_seconds()>600):
        raise ValueError('Finite current UTC admission with closure/backup reserve before user deadline')
    if a['phase'] not in ('census','export') or not re.fullmatch('jp-runtime-'+a['phase']+r'-v[1-9][0-9]*[.]service',a['unit']):
        raise ValueError('Exact phase/service')
    if type(modules) is not dict or not 1<=len(modules)<=64:
        raise ValueError('Original auxiliary module count')
    if any(type(s) is not str or not 0<len(s.encode())<=131072 for s in modules.values()):
        raise ValueError('Original auxiliary member bound')
    if sum(len(s.encode()) for s in modules.values())>2097152:
        raise ValueError('Original auxiliary aggregate')
    for name in modules:
        if name not in sys.modules or sys.modules[name].__file__!='<manager-export-injected:'+name+'>':
            raise ValueError('Exact injected module origin')
    if {n:hashlib.sha256(s.encode()).hexdigest() for n,s in modules.items()}!=a['module_sha256']:
        raise ValueError('Exact complete injected graph')
    from field_runtime_policy_v3 import validate,encoded,digest,identity,pin,timestamp
    from field_runtime_preservation_io_v1 import census,send_census,export_files,read_frame,frame,limits
    from field_owner_binding_v1 import decode as prior_owners
    from field_local_manager_owners_v1 import key
    from field_operator_broker_streamed_mirror_v1 import ancestors
    needed={'field_runtime_policy_v3','field_runtime_preservation_io_v1','field_owner_binding_v1',
            'field_local_manager_owners_v1','field_operator_broker_streamed_mirror_v1'}
    if not needed<=set(modules):raise ValueError('All direct project imports pinned')
    policy=validate(request['policy']);manifest=request['manifest']
    if digest(policy)!=a['policy_sha256'] or digest(manifest)!=a['manifest_sha256'] or a['manifest_sha256']!=policy['runtime_manifest_sha256']:
        raise ValueError('Immutable runtime policy/manifest pins')
    root=Path(policy['manager_root']);campaign=root.parent
    life=a['lifecycle']
    keys={'observed_utc','boot_id','baseline_states','install_sha256','live_config_sha256','display_config_sha256','settings_sha256','display_transform'}
    if type(life) is not dict or set(life)!=keys or digest(life)!=a['lifecycle_sha256']:
        raise ValueError('Exact fresh lifecycle snapshot')
    observed=timestamp(life['observed_utc'])
    if not 0<=(now-observed).total_seconds()<=120 or life['boot_id']!=boot:
        raise ValueError('Fresh current boot observation')
    if type(life['display_transform']) is not int or life['display_transform']!=270:
        raise ValueError('Preserve display270')
    baseline=life['baseline_states']
    if type(baseline) is not list or len(baseline)!=2:
        raise ValueError('Two actual baseline identities with explicit lifecycle states')
    seen=set()
    for row in baseline:
        if type(row) is not dict or set(row)!={'owner','alive'} or type(row['alive']) is not bool:
            raise ValueError('Explicit baseline state')
        who=identity(row['owner'])
        if who['boot_id']!=boot or key(who) in seen or (ticks(who['pid'])==who['start_ticks'])!=row['alive']:
            raise ValueError('Current actual baseline identity/state differs')
        seen.add(key(who))
    config_pins={'JustPeachy/install/current.json':'install_sha256','JustPeachy/data/live_config.json':'live_config_sha256',
                 '.config/kanshi/config':'display_config_sha256','JustPeachy/data/settings.json':'settings_sha256'}
    for relative,name in config_pins.items():
        path=Path.home()/relative;pin(life[name])
        if path.is_symlink() or not path.is_file() or path.stat().st_size>65536 or hashlib.sha256(path.read_bytes()).hexdigest()!=life[name]:
            raise ValueError('Actual baseline/display/settings bytes changed')
    if os.uname().machine!='aarch64' or 'Compute Module 5' not in Path('/proc/device-tree/model').read_text():
        raise ValueError('Actual CM5/aarch64 required')
    if int(Path('/sys/class/block/mmcblk0/size').read_text())*512!=31268536320:
        raise ValueError('Actual32GB device required')
    total=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:'))
    if not 1500000000<total<2200000000:raise ValueError('Actual2GB target')
    def guard(initial=False):
        if time.monotonic()>=deadline or datetime.now(timezone.utc)>=end:raise TimeoutError('Native export deadline')
        ram=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
        if ram<(850 if initial else 192)*1024**2 or shutil.disk_usage(campaign).free<5*1024**3:
            raise RuntimeError('Available memory or free-space floor')
        for path in Path('/proc/asound').glob('card*/pcm*c/sub*/status'):
            if path.read_text().strip()!='closed':raise RuntimeError('Capture remains active')
    guard(True)
    names=['CPUQuotaPerSecUSec','AllowedCPUs','TasksMax','LimitAS','LimitASSoft','LimitSTACK','LimitSTACKSoft',
           'LimitFSIZE','LimitFSIZESoft','RuntimeMaxUSec','TimeoutStopUSec','MainPID','ActiveState']
    cmd=['systemctl','--user','show',a['unit']]
    for name in names:cmd+=['-p',name]
    properties=subprocess.check_output(cmd,text=True,timeout=5)
    values=dict(row.split('=',1) for row in properties.splitlines())
    expected={'CPUQuotaPerSecUSec':'2s','AllowedCPUs':'2-3','TasksMax':'64','LimitAS':'134217728','LimitASSoft':'134217728',
              'LimitSTACK':'1048576','LimitSTACKSoft':'1048576','LimitFSIZE':'0','LimitFSIZESoft':'0',
              'RuntimeMaxUSec':'1min 30s','TimeoutStopUSec':'10s','MainPID':str(owner['pid']),'ActiveState':'active'}
    if values!=expected:raise ValueError('Actual bounded native service properties')
    external=a['external_owners']
    if type(external) is not list or not 1<=len(external)<=16 or len({key(w) for w in external})!=len(external):
        raise ValueError('Actual independently registered runtime owners')
    previous=prior_owners(a['closed_owners'])
    def dead(rows):
        for who in rows:
            identity(who)
            if who['boot_id']==boot and ticks(who['pid'])==who['start_ticks']:
                raise RuntimeError('Recorded runtime owner is still alive')
    dead(external+previous)
    bound=limits(policy)
    if type(a['mirror_maximum_bytes']) is not int or a['mirror_maximum_bytes']!=bound['maximum_bytes']:
        raise ValueError('Full independent manager plus all local copies reserved')
    if a['phase']=='census':
        if request['expected_index_sha256'] is not None:raise ValueError('Independent census has no supplied success digest')
    else:pin(request['expected_index_sha256'])
    with (campaign/'B05_PREVIEW_DISPATCH.lock').open('r+b') as research,(Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hardware:
        for handle in (research,hardware):fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating',
              '--plain','--full','--no-pager','--no-legend','jp-*'],text=True,timeout=5)
        if [row.split()[0] for row in units.splitlines() if row.strip()]!=[a['unit']]:
            raise RuntimeError('Unexpected active project service')
        if not root.exists():
            if a['phase']!='census':raise ValueError('Absent runtime root is census-only')
            frame(sys.stdout.buffer,dict(type='NO_TARGET_ROOT',owner=owner,source=str(root),
                  properties=properties,physical_closure_claimed=False),guard)
            return
        ancestors(root)
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
            value=census(root,policy,manifest,guard)
            dead(value['ownership']['identities'])
            if not {key(row['owner']) for row in value['ownership']['launches']}<={key(w) for w in external}:
                raise ValueError('Journal launches need actual external owner registration')
            if a['phase']=='export' and value['plan']['global_manifest_sha256']!=request['expected_index_sha256']:
                raise ValueError('Complete independently pinned earlier census differs')
            frame(sys.stdout.buffer,dict(type='READY',phase=a['phase'],owner=owner,properties=properties,
                  source=str(root),physical_closure_claimed=False),guard)
            if read_frame(sys.stdin.buffer,guard)!=dict(ack=owner):
                raise ValueError('Actual owner ACK')
            send_census(sys.stdout.buffer,value,guard)
            if a['phase']=='export':
                export_files(sys.stdout.buffer,root,value,policy,guard)
            dead(external+value['ownership']['identities'])
            guard()
        finally:os.close(fd)

