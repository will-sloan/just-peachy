"""Native bounded release metadata journal; README_FIELD_LOCAL_RELEASE_V1.md."""
from datetime import datetime,timezone
import os
from pathlib import Path
import shutil
import stat
import time
from field_local_release_plan_v1 import (CONTROL_RECORDS,LAUNCH_RECORDS,RECORDING_RECORDS,
    allocation,encoded,sha,validate_release,validate_research_operation,
    next_recording,next_launch,recording_state)
from field_live_layout_v3 import finite_json

def read(path,cap):
    p=Path(path);s=p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>cap:raise ValueError('Unique bounded metadata file')
    raw=p.read_bytes();t=p.lstat()
    if (s.st_ino,s.st_size,s.st_mtime_ns)!=(t.st_ino,t.st_size,t.st_mtime_ns) or len(raw)!=s.st_size:
        raise RuntimeError('Metadata changed')
    return finite_json(raw)

def sync(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

class Journal:
    """Prepared native primitive, not an activated manager or recovery authority.

    Creation is an install boundary. Every open needs a fresh bounded operation.
    Reopening never clears pending files, failure records, or consumed slots.
    """
    def __init__(self,root,release_sha256,operation,*,create=False):
        import fcntl
        self.root=Path(root).absolute();self.failed=False;self.fd=None
        self.operation=validate_research_operation(operation)
        if type(create) is not bool:raise ValueError('Explicit creation mode')
        if os.uname().machine!='aarch64' or os.sched_getaffinity(0)!={3}:raise ValueError('Native CPU3 journal')
        for p in (self.root,*self.root.parents):
            if not p.is_dir() or p.is_symlink():raise ValueError('Existing canonical real directory')
        self.fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            policy=read(self.root/'control/RELEASE.json',65536)
            raw=(self.root/'control/RELEASE.json').read_bytes()
            import hashlib
            if hashlib.sha256(raw).hexdigest()!=release_sha256:raise ValueError('Exact release policy bytes')
            self.release=validate_release(policy)
            self.policy_sha=release_sha256;self.plan=self.release['allocation']
            if self.release['root']!=str(self.root):raise ValueError('Exact journal root')
            if create:
                if {p.name for p in self.root.iterdir()}!={'control','code'}:raise ValueError('Fresh installed root')
                if {p.name for p in (self.root/'control').iterdir()}!={'RELEASE.json','MANIFEST.json'}:
                    raise ValueError('Fresh immutable install controls')
                self.failed=True
                for name,slots in [('recordings',self.plan['recording_slots']),('launches',self.plan['launch_slots']),('backups',[])]:
                    parent=self.root/name;parent.mkdir()
                    for slot in slots:(parent/slot).mkdir()
                    sync(parent)
                sync(self.root);self.failed=False
            self.inspect()
        except BaseException:
            self.close();raise

    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None

    def _live(self):
        if self.fd is None or self.failed:raise RuntimeError('Closed or fault-latched journal')
        validate_research_operation(self.operation)

    def _slot_caps(self):
        result={'control':CONTROL_RECORDS}
        result.update({'recordings/'+n:RECORDING_RECORDS for n in self.plan['recording_slots']})
        result.update({'launches/'+n:LAUNCH_RECORDS for n in self.plan['launch_slots']})
        return result

    def inspect(self):
        self._live()
        if {p.name for p in self.root.iterdir()}!={'control','code','recordings','launches','backups'}:
            raise ValueError('Exact local release root membership')
        count=0;total=0;out={}
        for parent,names in [('recordings',self.plan['recording_slots']),('launches',self.plan['launch_slots'])]:
            d=self.root/parent
            if d.is_symlink() or not d.is_dir() or {p.name for p in d.iterdir()}!=set(names):
                raise ValueError('Exact metadata directories')
        for relative,caps in self._slot_caps().items():
            d=self.root/relative
            if d.is_symlink() or not d.is_dir():raise ValueError('Real metadata directory')
            rows={}
            for p in d.iterdir():
                if p.name.endswith('.pending'):raise RuntimeError('Preserved incomplete publication; no retry')
                kind=p.stem
                if p.suffix!='.json' or kind not in caps:raise ValueError('Unallocated metadata file')
                value=read(p,caps[kind]);total+=p.stat().st_size;count+=1;rows[kind]=value
                if relative!='control' and (value.get('policy_sha256')!=self.policy_sha or value.get('slot')!=relative):
                    raise ValueError('Record slot/policy drift')
            out[relative]=rows
        code=self.root/'code';size=0;members=0
        if code.is_symlink() or not code.is_dir():raise ValueError('Real code directory')
        for p in code.iterdir():
            s=p.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>self.plan['code_member_bytes']:
                raise ValueError('Bounded unique code member')
            size+=s.st_size;members+=1
        if members>self.plan['code_files'] or size>self.plan['code_bytes']:raise ValueError('Code aggregate/cardinality')
        # Backup publication/copy is intentionally not implemented by this primitive.
        # It cannot claim a full release-tree census from metadata accounting.
        backup=self.root/'backups'
        if backup.is_symlink() or not backup.is_dir() or any(backup.iterdir()):
            raise ValueError('Backup consumer is not wired; no unaccounted payload allowed')
        if total+size>self.plan['metadata_maximum_bytes']:raise RuntimeError('Metadata aggregate allocation')
        return out

    def publish(self,slot,kind,value):
        self._live();observed=self.inspect()
        caps=self._slot_caps().get(slot)
        if caps is None or kind not in caps or kind in ('RELEASE','MANIFEST'):
            raise ValueError('Exact mutable publication slot')
        if type(value) is not dict or set(value)&{'policy_sha256','slot','utc'}:raise ValueError('Reserved binding fields')
        target=self.root/slot/(kind+'.json');pending=target.with_name(target.name+'.pending')
        if target.exists() or pending.exists():raise FileExistsError('Consumed immutable publication')
        if slot.startswith('recordings/'):
            trial={**observed[slot],kind:value};recording_state(trial)
            if kind=='RESERVED':
                records={n:observed['recordings/'+n] for n in self.plan['recording_slots']}
                if slot!='recordings/'+next_recording(self.plan,records):raise ValueError('Next unconsumed recording only')
        if slot.startswith('launches/'):
            from field_operator_session_ledger_v4 import identity,ticks
            if kind=='OWNER':
                records={n:observed['launches/'+n] for n in self.plan['launch_slots']}
                if slot!='launches/'+next_launch(self.plan,records):raise ValueError('Next unconsumed launch only')
                if value.get('owner')!=identity():raise ValueError('Actual current journal owner')
                for rows in records.values():
                    if rows:
                        owner=rows['OWNER']['owner']
                        if owner['boot_id']==identity()['boot_id'] and ticks(owner['pid'])==owner['start_ticks']:
                            raise RuntimeError('Prior journal owner remains alive')
            else:
                if 'OWNER' not in observed[slot]:raise ValueError('Actual owner precedes exit/failure')
                if observed[slot]['OWNER']['owner']!=identity():raise RuntimeError('No recovery impersonation of old owner')
        raw=encoded(dict(policy_sha256=self.policy_sha,slot=slot,utc=datetime.now(timezone.utc).isoformat(),**value))
        if len(raw)>caps[kind]:raise ValueError('Independent primary allocation')
        if shutil.disk_usage(self.root).free<5*1024**3+len(raw):raise RuntimeError('Physical free floor')
        self.failed=True
        fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            for offset in range(0,len(raw),16384):
                block=memoryview(raw[offset:offset+16384])
                while block:
                    n=os.write(fd,block)
                    if not n:raise OSError('Metadata short write')
                    block=block[n:]
            os.fsync(fd)
        finally:os.close(fd)
        os.link(pending,target,follow_symlinks=False);sync(target.parent)
        pending.unlink();sync(target.parent)
        if target.read_bytes()!=raw:raise IOError('Metadata exact readback')
        self.failed=False
        return read(target,caps[kind])
