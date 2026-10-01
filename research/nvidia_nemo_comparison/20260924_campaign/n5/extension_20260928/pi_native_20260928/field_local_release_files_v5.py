"""Native bounded release metadata journal; README_FIELD_LOCAL_CAPSULE_V1.md."""
from datetime import datetime,timezone
import os
from pathlib import Path
import shutil
import stat
import time
from field_local_release_plan_v2 import (CONTROL_RECORDS,LAUNCH_RECORDS,RECORDING_RECORDS,
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

def validate_started_observation(owner, gate, current, values):
    """Validate observed roles; caller separately verifies actual process ticks."""
    for item in (owner,gate,current):
        if type(item) is not dict or set(item)!={'pid','boot_id','start_ticks'}:
            raise ValueError('Exact native identity')
        if type(item['pid']) is not int or item['pid']<=0 or type(item['start_ticks']) is not int or item['start_ticks']<=0:
            raise ValueError('Positive native PID and start ticks')
        if type(item['boot_id']) is not str or len(item['boot_id'])!=36:
            raise ValueError('Recorded boot identity')
    if owner['boot_id']!=current['boot_id'] or gate['boot_id']!=current['boot_id']:
        raise RuntimeError('Current same-boot source identities')
    if owner['pid']==gate['pid']:
        raise RuntimeError('Independent broker and gate processes')
    if type(values) is not dict or set(values)!={'MainPID','ActiveState'}:
        raise ValueError('Exact service observation')
    if values['ActiveState']!='active' or values['MainPID']!=str(owner['pid']):
        raise RuntimeError('Service MainPID must be actual broker, not external gate')
    return True

class Journal:
    """Prepared native primitive, not an activated manager or recovery authority.

    Creation is an install boundary. Every open needs a fresh bounded operation.
    Reopening never clears pending files, failure records, or consumed slots.
    """
    def __init__(self,root,release_sha256,operation,*,create=False):
        import fcntl
        self.root=Path(root).absolute();self.failed=False;self.fd=None
        self._fact_token=False;self._copying_slot=None
        self.operation=validate_research_operation(operation)
        import resource
        if resource.getrlimit(resource.RLIMIT_AS)!=(134217728,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1048576,)*2:
            raise ValueError('Native journal128MiB hardAS and1MiB stack')
        if resource.getrlimit(resource.RLIMIT_FSIZE)!=(33554432,)*2:
            raise ValueError('Native outer32MiB file envelope')
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

    def _capsule(self):
        import hashlib
        policy_path=self.root/'control/RELEASE.json'
        read(policy_path,65536)
        if hashlib.sha256(policy_path.read_bytes()).hexdigest()!=self.policy_sha:
            raise ValueError('Immutable policy drift')
        path=self.root/'control/MANIFEST.json'
        manifest=read(path,131072)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=self.release['release_manifest_sha256']:
            raise ValueError('Immutable local capsule manifest digest')
        if type(manifest) is not dict or set(manifest)!={'schema','files'} or manifest['schema']!='just-peachy.local-release-manifest.v1' or type(manifest['files']) is not list:
            raise ValueError('Local capsule manifest shape')
        from field_operator_session_ledger_v4 import file_pin
        expected=set()
        for row in manifest['files']:
            if type(row) is not dict or set(row)!={'path','bytes','sha256'}:raise ValueError('Exact code pin')
            rel=row['path']
            if type(rel) is not str or not rel.startswith('code/') or len(Path(rel).parts)!=2 or Path(rel).name in ('.','..') or rel in expected:
                raise ValueError('Canonical unique code basename')
            if type(row['bytes']) is not int or not 0<row['bytes']<=self.plan['code_member_bytes']:
                raise ValueError('Code member bound')
            if file_pin(self.root/rel)!=dict(bytes=row['bytes'],sha256=row['sha256']):raise ValueError('Actual pinned code bytes')
            expected.add(rel)
        if expected!={'code/'+p.name for p in (self.root/'code').iterdir()}:
            raise ValueError('Exact local code membership')

    def inspect(self):
        self._live();self._capsule()
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
        self._backups(out)
        if total+size>self.plan['metadata_maximum_bytes']:raise RuntimeError('Metadata aggregate allocation')
        return out

    def publish(self,slot,kind,value):
        if slot=='control' and kind in ('ACTIVATION','ROLLBACK'):
            raise RuntimeError('Activation and rollback adapter not implemented')
        if slot.startswith('recordings/') and not self._fact_token:
            raise RuntimeError('Recording facts require actual lifecycle verification')
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

    def _deadline(self, seconds=90):
        left=(datetime.fromisoformat(self.operation['expires_utc'])-datetime.now(timezone.utc)).total_seconds()
        if left<=5:raise TimeoutError('No bounded verification lifetime')
        return time.monotonic()+min(seconds,left-2)

    def _binding(self, slot):
        from field_local_backup_contract_v2 import source_binding
        from field_operator_session_ledger_v4 import file_pin
        if slot not in self.plan['recording_slots']:raise ValueError('Exact recording slot')
        source=Path(self.release['recording_roots'][self.plan['recording_slots'].index(slot)])
        return source_binding(self.release,slot,read(source/'RELEASE.json',65536),
                              file_pin(source/'RELEASE.json')['sha256'])

    def _closed_source(self, slot):
        import fcntl
        from field_operator_session_ledger_v4 import file_pin
        from field_operator_health_v1 import _inspect
        from field_local_broker_backup_v1 import unit_closed
        b=self._binding(slot);source=Path(b['source'])
        for p in (source,*source.parents):
            if p.is_symlink() or not p.is_dir():raise ValueError('Canonical real source ancestors')
        fd=os.open(source/'broker',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
            health=_inspect(source,read(source/'RELEASE.json',65536),b['policy_sha256'])
            if health['status']!='CLOSED_HISTORY_AVAILABLE' or not health['minimum_free_floor_met']:
                raise RuntimeError('Actual closure incomplete; preserve the source')
            gate=read(source/'broker/GATE_RESULT.json',16384)
            if not all(gate[k] is True for k in ('logical_success','capture_closed','worker_exact_dead','pipe_closed')) or gate['returncode']!=0:
                raise RuntimeError('Actual successful gate closure required')
            unit=unit_closed(b['source_unit'])
            names=['RELEASE.json','broker/GATE_RESULT.json','broker/OWNER.json',
                'broker/GATE_OWNER.json','slot-01/STARTED.json','slot-01/CLOSED.json']
            pins={name:file_pin(source/name) for name in names}
            return dict(binding=b,owners=health['owners'],source_pins=pins,unit=unit,
                        successful=True,capture_closed=True)
        finally:os.close(fd)

    def _verify_copy(self, slot, receipt, deadline):
        from field_local_backup_contract_v2 import copy_binding
        from field_operator_broker_streamed_mirror_v1 import inventory,_readback,plan
        b=self._binding(slot);copy_binding(receipt,b)
        source=Path(b['source']);destination=Path(b['destination'])
        value=plan(source,receipt['files'],deadline,b['maximum_bytes'])
        if value['directories']!=receipt['directories'] or value['bytes']!=receipt['bytes'] or value['reserved_bytes']!=receipt['reserved_bytes']:
            raise ValueError('Actual source inventory differs from complete receipt')
        before,dirs=inventory(destination,deadline)
        if set(before)!=set(receipt['files']) or dirs!=set(receipt['directories']):
            raise ValueError('Exact independent local backup membership')
        for name,pin in receipt['files'].items():
            self._live();_readback(source/name,pin,deadline);_readback(destination/name,pin,deadline)
        after,afterdirs=inventory(destination,deadline)
        current,currentdirs=inventory(source,deadline)
        if after!=before or afterdirs!=dirs or current!=value['source_identities'] or currentdirs!=set(value['directories']):
            raise ValueError('Source/backup changed during verification')

    def _backups(self, observed):
        from field_operator_broker_streamed_mirror_v1 import _inventory
        backup=self.root/'backups'
        if backup.is_symlink() or not backup.is_dir():raise ValueError('Real local backup directory')
        present={p.name for p in backup.iterdir()}
        if not present<=set(self.plan['recording_slots']):raise ValueError('Unknown local backup slot')
        for slot in self.plan['recording_slots']:
            records=observed['recordings/'+slot];record=records.get('BACKUP')
            if record is not None:
                if slot not in present:raise RuntimeError('Certified backup is missing')
                if set(record)!={'policy_sha256','slot','utc','copy'}:raise ValueError('Exact journal backup envelope')
                self._verify_copy(slot,record['copy'],self._deadline())
                fact=self._closed_source(slot)
                closed=records.get('CLOSED',{})
                if any(closed.get(k)!=fact[k] for k in ('binding','source_pins','owners')) or record['copy']['owners']!=fact['owners']:
                    raise RuntimeError('Certified copy requires the actual matching closure')
            elif slot in present:
                # Only the current once-only in-process copy may be in flight.
                # Any subsequent constructor has no token and fences this tree.
                if self._copying_slot!=slot:raise RuntimeError('Uncertified local backup preserved; no retry')
                files,dirs=_inventory(backup/slot,self._deadline())
                if sum(v[2] for v in files.values())+len(dirs)*65536>self.plan['local_backup_per_recording']:
                    raise ValueError('Partial mirror retains full independent allocation')

    def _fact(self, slot, kind, value):
        if self._fact_token:raise RuntimeError('No nested verified publication')
        self._fact_token=True
        try:return self.publish('recordings/'+slot,kind,value)
        finally:self._fact_token=False

    def reserve_recording(self):
        from field_local_release_plan_v2 import next_recording
        self._live();observed=self.inspect()
        records={n:observed['recordings/'+n] for n in self.plan['recording_slots']}
        # Existing completed slots need fresh actual physical checks as well as
        # full backup readback performed by inspect; no supplied booleans suffice.
        for slot,rows in records.items():
            if rows:
                fact=self._closed_source(slot)
                if any(rows.get('CLOSED',{}).get(k)!=fact[k] for k in ('binding','source_pins','owners')):
                    raise RuntimeError('Prior actual closure differs from journal')
        slot=next_recording(self.plan,records)
        source=Path(self.release['recording_roots'][self.plan['recording_slots'].index(slot)])
        if source.exists() or source.is_symlink():raise FileExistsError('Fresh broker root required')
        self._fact(slot,'RESERVED',dict(source_root=str(source),source_unit='jp-'+source.name+'.service'))
        return dict(slot=slot,source_root=str(source))

    def recording_started(self, slot):
        from field_operator_session_ledger_v4 import identity,ticks
        from field_operator_session_plan_v3 import validate_policy
        import subprocess
        b=self._binding(slot);source=Path(b['source'])
        rows=self.inspect()['recordings/'+slot]
        if set(rows)!={'RESERVED'} or rows['RESERVED']['source_root']!=str(source):
            raise ValueError('Exact prior unused reservation')
        validate_policy(read(source/'RELEASE.json',65536))
        owner=read(source/'broker/OWNER.json',16384);gate=read(source/'broker/GATE_OWNER.json',16384)
        now=identity()
        for o in (owner,gate):
            if set(o)!={'pid','boot_id','start_ticks'} or o['boot_id']!=now['boot_id'] or ticks(o['pid'])!=o['start_ticks']:
                raise RuntimeError('Actual current broker and gate owners')
        proc=subprocess.run(['systemctl','--user','show',b['source_unit'],'-p','MainPID','-p','ActiveState'],capture_output=True,text=True,timeout=5)
        if len(proc.stdout)>4096 or len(proc.stderr)>4096:raise ValueError('Bounded service observation')
        values=dict(line.split('=',1) for line in proc.stdout.splitlines())
        if proc.returncode:raise RuntimeError('Actual admitted source service observation failed')
        validate_started_observation(owner,gate,now,values)
        return self._fact(slot,'STARTED',dict(binding=b,owner=owner,gate_owner=gate,unit=values))

    def recording_closed(self, slot):
        from field_operator_session_ledger_v4 import file_pin
        rows=self.inspect()['recordings/'+slot]
        if set(rows)!={'RESERVED','STARTED'}:raise ValueError('Once-only started recording closure')
        fact=self._closed_source(slot)
        if rows['STARTED']['binding']!=fact['binding']:raise ValueError('Source policy changed after actual Start')
        source=Path(fact['binding']['source'])
        if read(source/'broker/OWNER.json',16384)!=rows['STARTED']['owner'] or read(source/'broker/GATE_OWNER.json',16384)!=rows['STARTED']['gate_owner']:
            raise ValueError('Recorded actual source owners changed')
        return self._fact(slot,'CLOSED',fact)

    def backup_recording(self, slot):
        from field_local_broker_backup_v1 import copy_closed
        from field_operator_broker_streamed_mirror_v1 import inventory
        from field_operator_session_ledger_v4 import file_pin
        rows=self.inspect()['recordings/'+slot]
        if set(rows)!={'RESERVED','STARTED','CLOSED'}:raise ValueError('Once-only closed recording backup')
        fact=self._closed_source(slot)
        if fact['binding']!=rows['CLOSED']['binding'] or fact['source_pins']!=rows['CLOSED']['source_pins']:
            raise ValueError('Actual closure receipts changed')
        b=fact['binding'];source=Path(b['source']);destination=Path(b['destination'])
        if destination.exists() or destination.is_symlink():raise FileExistsError('Consumed local mirror')
        deadline=self._deadline(100)
        files,dirs=inventory(source,deadline)
        pins={name:file_pin(source/name) for name in files}
        self._copying_slot=slot
        try:
            receipt=copy_closed(source,destination,b['policy_sha256'],b['source_unit'],pins,
                operation=self.operation,deadline=deadline,maximum_bytes=b['maximum_bytes'])
            self._verify_copy(slot,receipt,deadline)
            # Final actual closure observation after copy and before certification.
            after=self._closed_source(slot)
            if after['binding']!=fact['binding'] or after['source_pins']!=fact['source_pins']:
                raise RuntimeError('Source closure changed during local backup')
            return self._fact(slot,'BACKUP',dict(copy=receipt))
        except BaseException:
            self.failed=True
            raise
        finally:self._copying_slot=None

    def recording_failed(self, slot, reason):
        if type(reason) is not str or not 1<=len(reason)<=512:raise ValueError('Bounded failure reason')
        rows=self.inspect()['recordings/'+slot]
        if 'RESERVED' not in rows or any(k in rows for k in ('FAILED','CLOSED','BACKUP')):
            raise ValueError('Once-only active failure')
        return self._fact(slot,'FAILED',dict(reason=reason,physical_closure_verified=False))
