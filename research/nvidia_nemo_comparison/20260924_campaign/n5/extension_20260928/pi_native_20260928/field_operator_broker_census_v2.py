"""Native broker qualification component; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V1.md."""
import os
import resource
import signal
from pathlib import Path
import hashlib
import json
import fcntl
import stat
import time

def collect(root,expected_policy,policy_sha256,additional_owners,partial_binding=None):
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    signal.alarm(30);deadline=time.monotonic()+28
    def ticks(pid):
        try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
        except FileNotFoundError:return None
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
    print(json.dumps(dict(utility_owner=owner)),flush=True)
    root=Path(root)
    if str(root)!=expected_policy['root'] or root.parent!=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928'):
        raise ValueError('Exact admitted root')
    if boot!=expected_policy['boot_id'] or ticks(1013)!=569 or ticks(1130)!=607:raise ValueError('Baseline drift')
    if Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()!='closed':raise RuntimeError('Capture remains active')
    with (root.parent/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hw:
            fcntl.flock(hw,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(hw,fcntl.LOCK_UN)
        owners=list(additional_owners)
        slots=expected_policy['allocation']['slot_names']
        if partial_binding is not None:
            if partial_binding['source_root']!=str(root) or partial_binding['policy_sha256']!=policy_sha256 or additional_owners!=[partial_binding['initializer_owner']]:raise ValueError('Exact failed initializer binding')
        for relative in ([] if partial_binding is not None else ['broker/STAGE_OWNER.json','broker/GATE_OWNER.json','broker/OWNER.json']+[
            'recordings/'+s+'/'+r for s in slots for r in ('control/OWNER.json','parent_control/OWNER.json','source/CHILD_OWNER.json')]):
            p=root/relative
            if p.exists():
                if p.is_symlink() or p.stat().st_size>16384:raise ValueError('Owner file')
                owners.append(json.loads(p.read_bytes()))
        unique={}
        for o in owners:
            if set(o)!={'pid','start_ticks','boot_id'} or type(o['pid']) is not int or type(o['start_ticks']) is not int:
                raise ValueError('Exact owner identity')
            if o['boot_id']==boot and ticks(o['pid'])==o['start_ticks']:raise RuntimeError('Owned process still active')
            unique[(o['boot_id'],o['pid'],o['start_ticks'])]=o
        if not root.exists():
            return dict(status='NO_TARGET_ROOT',files={},directories=[],owners=list(unique.values()),utility_owner=owner,capture_closed=True)
        release=root/'RELEASE.json';status='PARTIAL_INITIALIZATION'
        if release.exists() and partial_binding is None:
            raw=release.read_bytes()
            if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=policy_sha256 or json.loads(raw)!=expected_policy:
                raise ValueError('Root policy drift')
            status='CLOSED_TREE_WITH_RELEASE'
        if partial_binding is not None:status='CLOSED_PARTIAL_INITIALIZER_TREE'
        files={};dirs=[];identities={}
        for base,names,members in os.walk(root,followlinks=False):
            if time.monotonic()>=deadline:raise TimeoutError('Closed census deadline')
            d=Path(base)
            if d.is_symlink():raise ValueError('Linked directory')
            dirs.append('' if d==root else d.relative_to(root).as_posix())
            for name in members:
                p=d/name;s=p.lstat();relative=p.relative_to(root).as_posix()
                if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>33554432:raise ValueError('Closed file type/size')
                with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
                after=p.stat()
                identity=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
                if identity!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('Closed file changed')
                files[relative]=dict(bytes=s.st_size,sha256=h);identities[relative]=identity
            if len(files)>1162 or len(dirs)>264:raise ValueError('Whole tree cardinality')
        if partial_binding is not None:
            if not set(dirs).issubset({'','code','broker'}):raise ValueError('No runtime subtree in initializer failure')
            if any(n not in partial_binding['members'] or v['bytes']>partial_binding['members'][n] for n,v in files.items()):raise ValueError('Initializer exact member ceilings')
        full=expected_policy['allocation']['target_maximum_bytes']
        if sum(v['bytes'] for v in files.values())+len(dirs)*65536>full:raise ValueError('Whole target allocation')
        for slot in slots:
            prefix='recordings/'+slot
            rows=[v for n,v in files.items() if n.startswith(prefix+'/')]
            directory_count=sum(d==prefix or d.startswith(prefix+'/') for d in dirs)
            if len(rows)>256 or directory_count>64 or sum(v['bytes'] for v in rows)+directory_count*65536>146919980:
                raise ValueError('Independent recording allocation')
        result=dict(status=status,files=files,directories=sorted(dirs),owners=list(unique.values()),
            utility_owner=owner,policy_sha256=policy_sha256,capture_closed=True,partial_initializer=partial_binding,
            observed_release_sha256=files.get('RELEASE.json',{}).get('sha256'))
        for label,relative in (('gate','broker/GATE_RESULT.json'),('broker','broker/RESULT.json')):
            p=root/relative
            if p.exists():
                if p.stat().st_size>65536:raise ValueError('Closed result cap')
                result[label]=json.loads(p.read_bytes())
        if len(json.dumps(result).encode())>262144:raise ValueError('Closed census output slot')
        return result
