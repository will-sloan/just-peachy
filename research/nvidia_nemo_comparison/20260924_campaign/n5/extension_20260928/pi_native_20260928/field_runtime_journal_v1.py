"""Native persistent user-release journal; README_FIELD_RUNTIME_JOURNAL_V1.md."""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import time

from field_runtime_policy_v1 import (validate, issue_operation, validate_operation,
    digest, identity as validate_identity)
from field_local_release_plan_v2 import CONTROL_RECORDS, LAUNCH_RECORDS, RECORDING_RECORDS, encoded
from field_operator_session_ledger_v4 import read, file_pin, identity, ticks


def sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class RuntimeJournal:
    """One real native manager owns the lifetime lock; no caller-supplied closure flags."""
    def __init__(self, root, policy_sha256, *, create=False):
        import fcntl
        import resource
        self.root=Path(root).absolute(); self.fd=None; self.failed=False
        self.owner=validate_identity(identity()); self.launch_slot=None
        self.started=time.monotonic()
        if type(create) is not bool or os.uname().machine!='aarch64' or os.sched_getaffinity(0)!={3}:
            raise ValueError('Native CPU3 manager required')
        for kind, value in ((resource.RLIMIT_AS,134217728), (resource.RLIMIT_STACK,1048576),
                            (resource.RLIMIT_FSIZE,33554432)):
            if resource.getrlimit(kind)!=(value,value):
                raise ValueError('Actual metadata AS/stack/file envelope required')
        for path in (self.root,*self.root.parents):
            if path.is_symlink() or not path.is_dir():
                raise ValueError('Existing canonical real installation required')
        self.fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            policy_path=self.root/'control/RELEASE.json'
            if file_pin(policy_path)['sha256']!=policy_sha256:
                raise ValueError('Immutable runtime policy bytes required')
            self.policy=validate(read(policy_path,65536)); self.policy_sha=policy_sha256
            self.plan=self.policy['allocation']
            if self.policy['manager_root']!=str(self.root):
                raise ValueError('Exact installed manager root')
            self._capsule()
            if create:
                if {p.name for p in self.root.iterdir()}!={'code','control'}:
                    raise ValueError('Fresh installation only')
                if {p.name for p in (self.root/'control').iterdir()}!={'RELEASE.json','MANIFEST.json'}:
                    raise ValueError('Fresh exact installation controls')
                self.failed=True
                for parent,slots in (('recordings',self.plan['recording_slots']),
                                     ('launches',self.plan['launch_slots']),('backups',[])):
                    directory=self.root/parent;directory.mkdir()
                    for slot in slots:(directory/slot).mkdir()
                    sync(directory)
                sync(self.root);self.failed=False
            self.inspect()
        except BaseException:
            self.close();raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd);self.fd=None

    def _live(self):
        if self.fd is None or self.failed:
            raise RuntimeError('Closed or fault-latched runtime journal')
        if identity()!=self.owner:
            raise RuntimeError('Actual manager process identity changed')
        if time.monotonic()-self.started>=self.policy['limits']['idle_launch_seconds']:
            raise TimeoutError('Finite idle launch exhausted')
        if file_pin(self.root/'control/RELEASE.json')['sha256']!=self.policy_sha:
            raise ValueError('Immutable runtime policy changed')

    def _capsule(self):
        manifest=read(self.root/'control/MANIFEST.json',131072)
        if file_pin(self.root/'control/MANIFEST.json')['sha256']!=self.policy['runtime_manifest_sha256']:
            raise ValueError('Exact installed runtime manifest required')
        if type(manifest) is not dict or set(manifest)!={'schema','files'} or manifest['schema']!='just-peachy.local-release-manifest.v1':
            raise ValueError('Exact runtime code manifest')
        rows=manifest['files'];seen=set();aliases=set();total=0
        if type(rows) is not list or not 1<=len(rows)<=self.plan['code_files']:
            raise ValueError('Original manager code cardinality')
        for row in rows:
            if type(row) is not dict or set(row)!={'path','bytes','sha256'}:
                raise ValueError('Exact code pin')
            name=row['path'];path=Path(name)
            if type(name) is not str or path.parts[:1]!=('code',) or len(path.parts)!=2 or path.name in ('.','..') or path.as_posix()!=name:
                raise ValueError('Canonical code member')
            if name.casefold() in aliases or type(row['bytes']) is not int or not 0<row['bytes']<=self.plan['code_member_bytes']:
                raise ValueError('Unique bounded code member')
            if file_pin(self.root/name)!=dict(bytes=row['bytes'],sha256=row['sha256']):
                raise ValueError('Installed code differs from pinned release')
            total+=row['bytes'];seen.add(path.name);aliases.add(name.casefold())
        if total>self.plan['code_bytes'] or seen!={p.name for p in (self.root/'code').iterdir()}:
            raise ValueError('Exact complete runtime capsule')

    def _caps(self):
        caps={'control':CONTROL_RECORDS}
        caps.update({'launches/'+s:LAUNCH_RECORDS for s in self.plan['launch_slots']})
        caps.update({'recordings/'+s:RECORDING_RECORDS for s in self.plan['recording_slots']})
        return caps

    def inspect(self):
        self._live();self._capsule()
        if {p.name for p in self.root.iterdir()}!={'control','code','recordings','launches','backups'}:
            raise ValueError('Exact runtime root membership')
        for parent,slots in (('recordings',self.plan['recording_slots']),('launches',self.plan['launch_slots'])):
            directory=self.root/parent
            if directory.is_symlink() or not directory.is_dir() or {p.name for p in directory.iterdir()}!=set(slots):
                raise ValueError('Complete immutable slot membership')
        result={};total=0
        for relative,caps in self._caps().items():
            directory=self.root/relative;rows={}
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError('Real metadata directories')
            for path in directory.iterdir():
                if path.name.endswith('.pending'):
                    raise RuntimeError('Preserved incomplete publication; recovery required')
                if path.suffix!='.json' or path.stem not in caps:
                    raise ValueError('Unallocated metadata path')
                row=read(path,caps[path.stem]);total+=path.stat().st_size
                if relative!='control' and (row.get('policy_sha256')!=self.policy_sha or row.get('slot')!=relative):
                    raise ValueError('Exact record policy and slot binding')
                rows[path.stem]=row
            result[relative]=rows
        if total+sum(p.stat().st_size for p in (self.root/'code').iterdir())>self.plan['metadata_maximum_bytes']:
            raise RuntimeError('Original complete metadata allocation exceeded')
        backups=self.root/'backups'
        if backups.is_symlink() or not backups.is_dir() or {p.name for p in backups.iterdir()}-set(self.plan['recording_slots']):
            raise ValueError('Independent allocated backup directory')
        return result

    def _publish(self,slot,kind,value):
        self._live();self.inspect()
        cap=self._caps().get(slot,{}).get(kind)
        if cap is None or slot=='control':
            raise ValueError('Allocated journal slot required; activation is separate')
        if type(value) is not dict or set(value)&{'policy_sha256','slot','utc'}:
            raise ValueError('Reserved journal envelope fields')
        path=self.root/slot/(kind+'.json');pending=path.with_name(path.name+'.pending')
        if path.exists() or pending.exists():
            raise FileExistsError('Consumed record cannot be overwritten or retried')
        raw=encoded(dict(policy_sha256=self.policy_sha,slot=slot,
            utc=datetime.now(timezone.utc).isoformat(),**value))
        if len(raw)>cap or shutil.disk_usage(self.root).free<5*1024**3+len(raw):
            raise RuntimeError('Independent member or physical free allocation')
        self.failed=True
        fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            for offset in range(0,len(raw),16384):
                block=memoryview(raw[offset:offset+16384])
                while block:
                    count=os.write(fd,block)
                    if count<=0:raise OSError('Incomplete publication')
                    block=block[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.link(pending,path,follow_symlinks=False);sync(path.parent)
        pending.unlink();sync(path.parent)
        if path.read_bytes()!=raw:raise IOError('Independent exact record readback')
        self.failed=False
        return read(path,cap)

    def begin_launch(self):
        if self.launch_slot is not None:
            raise RuntimeError('Manager has already consumed a launch')
        self._physical_idle()
        records=self.inspect();used=[]
        for index,slot in enumerate(self.plan['launch_slots']):
            rows=records['launches/'+slot]
            if not rows:continue
            used.append(index)
            if 'OWNER' not in rows or 'EXIT' not in rows:
                raise RuntimeError('Prior unfinished launch requires actual recovery')
            old=validate_identity(rows['OWNER']['owner'])
            if old['boot_id']==self.owner['boot_id'] and ticks(old['pid'])==old['start_ticks']:
                raise RuntimeError('Prior exact manager is still alive')
        if used!=list(range(len(used))) or len(used)==len(self.plan['launch_slots']):
            raise RuntimeError('Finite launch allocation exhausted or has a gap')
        slot=self.plan['launch_slots'][len(used)]
        self._publish('launches/'+slot,'OWNER',dict(owner=self.owner,purpose='USER_RUNTIME_MANAGER'))
        self.launch_slot=slot
        return slot

    def end_launch(self):
        if self.launch_slot is None:raise RuntimeError('No owned launch')
        self._physical_idle()
        rows=self.inspect()
        for slot in self.plan['recording_slots']:
            record=rows['recordings/'+slot]
            if record and set(record)!={'RESERVED','STARTED','CLOSED','BACKUP'}:
                raise RuntimeError('Active or unresolved recording remains fenced')
            if record:self.verify_closed_backup(slot,record)
        # This is intent while the manager lives; next launch verifies actual death.
        return self._publish('launches/'+self.launch_slot,'EXIT',
            dict(owner=self.owner,status='IDLE_CAPTURE_OFF',exit_is_intent=True))

    def reserve_recording(self,profile):
        if self.launch_slot is None:raise RuntimeError('Early registered manager launch required')
        self._physical_idle()
        available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                       if line.startswith('MemAvailable:'))
        if available<self.policy['limits']['initial_available_bytes']:
            raise RuntimeError('Initial available RAM below admission floor')
        observed=self.inspect();used=[]
        for index,slot in enumerate(self.plan['recording_slots']):
            rows=observed['recordings/'+slot]
            if not rows:continue
            used.append(index)
            if set(rows)!={'RESERVED','STARTED','CLOSED','BACKUP'}:
                raise RuntimeError('Prior recording requires actual closure and independent local copy')
            # The full native closure/copy verifier is deliberately mandatory.
            self.verify_closed_backup(slot,rows)
        if used!=list(range(len(used))) or len(used)==len(self.plan['recording_slots']):
            raise RuntimeError('Finite recording allocation exhausted or has a gap')
        slot=self.plan['recording_slots'][len(used)]
        operation=issue_operation(self.policy,slot=slot,profile=profile,owner=self.owner,
                                  now=datetime.now(timezone.utc))
        source=Path(operation['root'])
        if source.exists() or source.is_symlink():raise FileExistsError('Never reuse a source root')
        if shutil.disk_usage(self.root).free<5*1024**3+2*self.plan['broker_allocation']['target_maximum_bytes']:
            raise RuntimeError('Full source and independent local copy free reserve')
        self._publish('recordings/'+slot,'RESERVED',dict(operation=operation))
        return operation

    def verify_closed_backup(self,slot,rows):
        if set(rows)!={'RESERVED','STARTED','CLOSED','BACKUP'}:
            raise ValueError('Complete immutable recording records required')
        fact=self._closed_source(slot)
        closed=rows['CLOSED']
        for key in ('binding','owners','source_pins'):
            if closed.get(key)!=fact[key]:
                raise RuntimeError('Actual physical source facts changed')
        self._verify_copy(slot,rows['BACKUP']['copy'],fact)
        return fact

    @staticmethod
    def _physical_idle():
        import fcntl
        if Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()!='closed':
            raise RuntimeError('Microphone capture remains active')
        base=Path.home()/'JustPeachy'
        for path in (base/'research/nemotron-20260928/B05_PREVIEW_DISPATCH.lock',base/'data/xvf-hardware.lock'):
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            finally:
                os.close(fd)

    @staticmethod
    def _unit(unit, *, active=False):
        import subprocess
        proc=subprocess.run(['systemctl','--user','show',unit,'-p','LoadState','-p','ActiveState',
                             '-p','SubState','-p','MainPID'],capture_output=True,timeout=5)
        if len(proc.stdout)>4096 or len(proc.stderr)>4096:
            raise ValueError('Bounded service observation required')
        rows=dict(line.split('=',1) for line in proc.stdout.decode().splitlines())
        if set(rows)!={'LoadState','ActiveState','SubState','MainPID'}:
            raise ValueError('Exact service properties')
        if active:
            if proc.returncode or rows['LoadState']!='loaded' or rows['ActiveState']!='active':
                raise RuntimeError('Actual source service is not active')
        elif (proc.returncode not in (0,1) or rows['LoadState'] not in ('loaded','not-found')
              or rows['MainPID']!='0' or rows['ActiveState'] not in ('inactive','failed')
              or rows['SubState'] not in ('dead','failed')):
            raise RuntimeError('Source service is not physically closed')
        return rows

    def _source_binding(self,slot):
        if slot not in self.plan['recording_slots']:raise ValueError('Allocated slot required')
        reserved=read(self.root/'recordings'/slot/'RESERVED.json',16384)
        operation=reserved['operation']
        # Historical validation permits inspection only, never refreshes an operation.
        validate_operation(operation,self.policy,now=datetime.fromisoformat(operation['issued_utc']))
        if operation['slot']!=slot or reserved['policy_sha256']!=self.policy_sha:
            raise ValueError('Immutable reservation binding')
        source=Path(operation['root'])
        for path in (source,*source.parents):
            if path.is_symlink() or not path.is_dir():raise ValueError('Real existing source ancestors')
        policy=read(source/'RELEASE.json',65536)
        if (policy.get('schema')!='just-peachy.offline-broker-policy.v1' or policy.get('root')!=str(source)
            or policy.get('runtime_policy_sha256')!=self.policy_sha
            or policy.get('runtime_operation_sha256')!=digest(operation)
            or policy.get('issued_utc')!=operation['issued_utc']
            or policy.get('expires_utc')!=operation['expires_utc']
            or policy.get('boot_id')!=operation['owner']['boot_id']
            or encoded(policy.get('allocation'))!=encoded(self.plan['broker_allocation'])):
            raise ValueError('Actual independently allocated production source policy')
        return dict(source=str(source),destination=str(self.root/'backups'/slot),
            policy_sha256=file_pin(source/'RELEASE.json')['sha256'],
            source_unit='jp-'+source.name+'.service',maximum_bytes=self.plan['local_backup_per_recording'])

    def recording_started(self,slot):
        rows=self.inspect()['recordings/'+slot]
        if set(rows)!={'RESERVED'}:raise ValueError('Once-only reserved source Start')
        validate_operation(rows['RESERVED']['operation'],self.policy,now=datetime.now(timezone.utc))
        binding=self._source_binding(slot);source=Path(binding['source'])
        broker=validate_identity(read(source/'broker/OWNER.json',16384))
        gate=validate_identity(read(source/'broker/GATE_OWNER.json',16384))
        if broker==gate:raise ValueError('Independent broker and gate identities')
        for owner in (broker,gate):
            if owner['boot_id']!=self.owner['boot_id'] or ticks(owner['pid'])!=owner['start_ticks']:
                raise RuntimeError('Actual source owner is not alive')
        service=self._unit(binding['source_unit'],active=True)
        if service['MainPID']!=str(broker['pid']):raise RuntimeError('Actual service MainPID is not broker')
        return self._publish('recordings/'+slot,'STARTED',
            dict(binding=binding,owner=broker,gate_owner=gate,unit=service))

    def _closed_source(self,slot):
        import fcntl
        from field_operator_health_v1 import _inspect
        binding=self._source_binding(slot);source=Path(binding['source'])
        fd=os.open(source/'broker',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
            health=_inspect(source,read(source/'RELEASE.json',65536),binding['policy_sha256'])
            if health['status']!='CLOSED_HISTORY_AVAILABLE' or not health['minimum_free_floor_met']:
                raise RuntimeError('Actual source owners/capture/archive closure incomplete')
            gate=read(source/'broker/GATE_RESULT.json',16384)
            if any(gate.get(k) is not True for k in ('logical_success','capture_closed','worker_exact_dead','pipe_closed')) or gate.get('returncode')!=0:
                raise RuntimeError('Source did not close successfully and naturally')
            unit=self._unit(binding['source_unit'])
            names=('RELEASE.json','broker/GATE_RESULT.json','broker/OWNER.json',
                   'broker/GATE_OWNER.json','slot-01/STARTED.json','slot-01/CLOSED.json')
            pins={name:file_pin(source/name) for name in names}
            return dict(binding=binding,owners=health['owners'],source_pins=pins,unit=unit,
                        successful=True,capture_closed=True)
        finally:
            os.close(fd)

    def recording_closed(self,slot):
        rows=self.inspect()['recordings/'+slot]
        if set(rows)!={'RESERVED','STARTED'}:raise ValueError('Once-only started recording closure')
        validate_operation(rows['RESERVED']['operation'],self.policy,now=datetime.now(timezone.utc))
        fact=self._closed_source(slot);source=Path(fact['binding']['source'])
        if fact['binding']!=rows['STARTED']['binding']:
            raise ValueError('Source binding changed since Start')
        if (read(source/'broker/OWNER.json',16384)!=rows['STARTED']['owner'] or
            read(source/'broker/GATE_OWNER.json',16384)!=rows['STARTED']['gate_owner']):
            raise ValueError('Actual Start identities changed')
        return self._publish('recordings/'+slot,'CLOSED',fact)

    def _verify_copy(self,slot,receipt,fact,deadline=None):
        from field_local_backup_contract_v2 import copy_binding
        from field_operator_broker_streamed_mirror_v1 import inventory,plan,_readback
        binding=fact['binding'];copy_binding(receipt,binding)
        if receipt['owners']!=fact['owners']:raise ValueError('Copy owner observations differ')
        source=Path(binding['source']);destination=Path(binding['destination'])
        deadline=time.monotonic()+90 if deadline is None else deadline
        value=plan(source,receipt['files'],deadline,binding['maximum_bytes'])
        if (value['directories']!=receipt['directories'] or value['bytes']!=receipt['bytes']
            or value['reserved_bytes']!=receipt['reserved_bytes']):
            raise ValueError('Copy receipt differs from complete actual source')
        before,dirs=inventory(destination,deadline)
        if set(before)!=set(receipt['files']) or dirs!=set(receipt['directories']):
            raise ValueError('Complete independent local backup membership required')
        for name,pin in receipt['files'].items():
            self._live();_readback(source/name,pin,deadline);_readback(destination/name,pin,deadline)
        after,afterdirs=inventory(destination,deadline);current,currentdirs=inventory(source,deadline)
        if (after!=before or afterdirs!=dirs or current!=value['source_identities']
            or currentdirs!=set(value['directories'])):
            raise RuntimeError('Source or copy changed during independent verification')
        after_fact=self._closed_source(slot)
        for key in ('binding','owners','source_pins'):
            if after_fact[key]!=fact[key]:raise RuntimeError('Source changed before backup certification')

    def accept_local_backup(self,slot,receipt):
        rows=self.inspect()['recordings/'+slot]
        if set(rows)!={'RESERVED','STARTED','CLOSED'}:raise ValueError('Once-only closed-source copy')
        operation=rows['RESERVED']['operation']
        validate_operation(operation,self.policy,now=datetime.now(timezone.utc))
        left=(datetime.fromisoformat(operation['expires_utc'])-datetime.now(timezone.utc)).total_seconds()
        if left<=2:raise TimeoutError('Insufficient bounded backup verification reserve')
        fact=self._closed_source(slot)
        for key in ('binding','owners','source_pins'):
            if rows['CLOSED'].get(key)!=fact[key]:raise RuntimeError('Actual source closure drift')
        self._verify_copy(slot,receipt,fact,time.monotonic()+min(90,left-2))
        validate_operation(operation,self.policy,now=datetime.now(timezone.utc))
        return self._publish('recordings/'+slot,'BACKUP',dict(copy=receipt))

    def recording_failed(self,slot,reason):
        if type(reason) is not str or not 1<=len(reason)<=512:raise ValueError('Bounded failure reason')
        rows=self.inspect()['recordings/'+slot]
        if 'RESERVED' not in rows or any(k in rows for k in ('CLOSED','BACKUP','FAILED')):
            raise ValueError('Once-only active failure record')
        return self._publish('recordings/'+slot,'FAILED',dict(reason=reason,physical_closure_verified=False))
