"""Fresh native broker initialization; README_FIELD_OPERATOR_BROKER_NATIVE_V1.md."""
import base64
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import types
sys.dont_write_bytecode=True

def stage(request):
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024,)*2)
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(25)
    if type(request) is not dict or set(request)!={'policy','manifest','files'}:
        raise ValueError('Exact native initializer request')
    decoded={}
    for name,raw in request['files'].items():
        if not isinstance(name,str) or Path(name).is_absolute() or len(Path(name).parts)!=2:
            raise ValueError('Exact initialized capsule path')
        folder,member=Path(name).parts
        if folder=='code':
            if not member.replace('_','').replace('-','').replace('.','').isalnum():raise ValueError('Code basename')
        elif folder!='broker' or member not in ('CONFIG.json','TEMPLATE.json'):
            raise ValueError('Immutable initializer member')
        data=base64.b64decode(raw,validate=True)
        if not 0<len(data)<=128*1024:raise ValueError('Initializer file slot')
        decoded[name]=data
    code=[n for n in decoded if n.startswith('code/')]
    if not 1<=len(code)<=64 or sum(len(decoded[n]) for n in code)>2*1024**2:
        raise ValueError('Original compact code guard')
    manifest=request['manifest']
    if set(manifest)!={'schema','files'} or manifest['schema']!='just-peachy.broker-capsule.v1':
        raise ValueError('Exact immutable capsule manifest')
    pins={row['path']:row for row in manifest['files']}
    if len(pins)!=len(manifest['files']) or set(pins)!=set(decoded):raise ValueError('Complete unique manifest')
    for name,data in decoded.items():
        if pins[name]!=dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()):
            raise ValueError('Initializer source pin')
    for name in ('field_operator_session_plan_v1','field_operator_broker_layout_v2',
                 'field_operator_session_plan_v3','field_live_layout_v2','field_live_layout_v3',
                 'field_operator_broker_files_v2','field_operator_session_ledger_v4',
                 'field_operator_broker_common_v1','field_owner_binding_v1'):
        module=types.ModuleType(name);module.__file__='<admitted-initializer:'+name+'>'
        sys.modules[name]=module
        exec(compile(decoded['code/'+name+'.py'],module.__file__,'exec'),module.__dict__)
    from field_operator_session_plan_v3 import validate_policy,encoded
    from field_operator_session_ledger_v4 import identity,ticks
    from field_operator_broker_common_v1 import physical,bundle
    from field_owner_binding_v1 import decode
    policy=validate_policy(request['policy']);root=Path(policy['root']);owner=identity()
    if root.parent!=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928'):
        raise ValueError('Exact parent')
    for p in (root.parent,*root.parent.parents):
        if p.is_symlink() or not p.is_dir():raise ValueError('Real initialized ancestors')
    if root.exists() or root.is_symlink():raise FileExistsError('Preserve attempted root; no retry')
    raw_policy=encoded(policy);raw_manifest=encoded(manifest)
    if len(raw_policy)>65536 or len(raw_manifest)>128*1024 or hashlib.sha256(raw_manifest).hexdigest()!=policy['release_manifest_sha256']:
        raise ValueError('Immutable policy/manifest binding')
    if not 575<=(datetime.fromisoformat(policy['expires_utc'])-datetime.now(timezone.utc)).total_seconds()<=600:
        raise RuntimeError('Whole initialization/gate/backup deadline')
    config=json.loads(decoded['broker/CONFIG.json']);physical(config)
    if policy['boot_id']!=owner['boot_id']:raise ValueError('Exact boot')
    for old in decode(config['preflight_pi_owners']):
        if old['boot_id']==owner['boot_id'] and ticks(old['pid'])==old['start_ticks']:
            raise RuntimeError('Prior exact research owner still active')
    def publish(path,data,cap):
        if len(data)>cap:raise ValueError('Initializer physical slot')
        with path.open('xb') as f:
            for offset in range(0,len(data),16384):
                block=data[offset:offset+16384]
                if f.write(block)!=len(block):raise IOError('Initializer short write')
            f.flush();os.fsync(f.fileno())
        if path.read_bytes()!=data:raise IOError('Initializer readback')
    with (root.parent/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','--plain','jp-*'],text=True,timeout=5).strip():
            raise RuntimeError('Healthy research unit remains')
        with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hw:
            fcntl.flock(hw,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(hw,fcntl.LOCK_UN)
        total=int(subprocess.check_output(['du','-sb',str(root.parent)],text=True,timeout=10).split()[0])
        request_bytes=policy['allocation']['combined_request_bytes']
        if policy['host_window_bytes']+total+request_bytes>policy['combined_output_cap_bytes'] or policy['payload_before_bytes']+max(0,total-policy['target_before_bytes'])+request_bytes>policy['total_payload_cap_bytes']:
            raise ValueError('Fresh target-inclusive allocation')
        import shutil
        if shutil.disk_usage(root.parent).free<5*1024**3+policy['allocation']['target_maximum_bytes']:
            raise ValueError('Full independent target reserve')
        ram=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        if ram<850*1024**2:raise ValueError('Initial RAM')
        root.mkdir();(root/'code').mkdir();(root/'broker').mkdir()
        publish(root/'broker/STAGE_OWNER.json',encoded(owner),16384)
        publish(root/'RELEASE.json',raw_policy,65536)
        publish(root/'broker/MANIFEST.json',raw_manifest,128*1024)
        for name,data in decoded.items():publish(root/name,data,65536 if name=='broker/CONFIG.json' else 128*1024)
        for p in (root/'code',root/'broker',root,root.parent):
            fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
        bundle(root)
    return dict(root=str(root),owner=owner,policy_sha256=hashlib.sha256(raw_policy).hexdigest(),
                files=len(decoded),bytes=sum(map(len,decoded.values())),readback_exact=True)

if __name__=='__main__':
    # The host pins this bootstrap and records this identity before sending data.
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(1024**2,)*2)
    signal.alarm(30)
    pid=os.getpid();ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    owner=dict(pid=pid,start_ticks=ticks,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    print(json.dumps(dict(owner=owner)),flush=True)
    raw=sys.stdin.buffer.readline(4*1024**2+1)
    if len(raw)>4*1024**2 or not raw.endswith(b'\n'):raise ValueError('Bounded one-line request')
    print(json.dumps(stage(json.loads(raw))),flush=True)
