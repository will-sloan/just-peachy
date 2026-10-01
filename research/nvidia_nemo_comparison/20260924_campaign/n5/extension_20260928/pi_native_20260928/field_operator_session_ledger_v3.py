"""Native immutable session ledger; README_FIELD_OPERATOR_BROKER_V1.md."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import stat
import time
from field_operator_session_plan_v2 import allocation, encoded, digest, validate_policy, state, next_slot, RECORDS
from field_live_layout_v3 import finite_json

def read(path, cap=65536):
    path=Path(path);s=path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>cap:
        raise ValueError('Real bounded unique file required')
    raw=path.read_bytes()
    if len(raw)!=s.st_size:raise RuntimeError('File changed during read')
    return finite_json(raw)


def file_pin(path):
    path=Path(path);before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>33554432:
        raise ValueError('Bounded real receipt required')
    with path.open('rb') as f:value=hashlib.file_digest(f,'sha256').hexdigest()
    after=path.lstat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise RuntimeError('Closed receipt changed')
    return dict(bytes=after.st_size,sha256=value)


def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def identity():
    return dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def validate_open_policy(policy, *, readonly, now=None):
    if type(readonly) is not bool:raise ValueError('Explicit inspection mode')
    now=datetime.now(timezone.utc) if now is None else now
    issued=datetime.fromisoformat(policy['issued_utc'])
    if issued.tzinfo is None or now<issued:raise ValueError('Future policy is not historical evidence')
    # Historical inspection retains the original finite policy, but grants no writes.
    return validate_policy(policy, now=issued if readonly else now)


class Ledger:
    """One native broker owns this object and the nonblocking lifetime flock.

    An injected storage adapter is deliberately unsupported. Host checks exercise
    the pure contract separately and cannot claim native filesystem durability.
    """
    def __init__(self, root, policy_sha256, release_sha256, *, create=False):
        import fcntl
        self.root=Path(root).absolute();self.lock_fd=None;self.failed=False;self.readonly=not create
        if os.uname().machine!='aarch64':raise ValueError('Native aarch64 broker only')
        for p in (self.root,*self.root.parents):
            if p.is_symlink() or not p.is_dir():raise ValueError('Existing real broker root')
        policy=read(self.root/'RELEASE.json')
        if file_pin(self.root/'RELEASE.json')['sha256']!=policy_sha256:
            raise ValueError('Immutable measured policy digest')
        self.policy=validate_open_policy(policy,readonly=self.readonly)
        if policy['root']!=str(self.root) or policy['release_manifest_sha256']!=release_sha256:
            raise ValueError('Root/release manifest binding')
        if policy['boot_id']!=identity()['boot_id']:raise ValueError('Boot changed')
        self.plan=allocation(policy['allocation']['count'])
        # Restarted ledgers are inspection-only; no prior failure is cleared.
        self.lock_fd=os.open(self.root/'.lease',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            s=os.fstat(self.lock_fd)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size:
                raise ValueError('Empty broker lease required')
            fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if create:
                if set(p.name for p in self.root.iterdir())!={'RELEASE.json','.lease','broker','code'}:
                    raise ValueError('Fresh broker root contents')
                (self.root/'recordings').mkdir()
                for name in self.plan['slot_names']:(self.root/name).mkdir()
                self._sync_directory(self.root)
            self.records()
        except BaseException:
            os.close(self.lock_fd);self.lock_fd=None
            raise

    @staticmethod
    def _sync_directory(path):
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)

    def close(self):
        if self.lock_fd is not None:os.close(self.lock_fd);self.lock_fd=None

    def _live(self):
        if self.lock_fd is None or self.failed or self.readonly:raise RuntimeError('Closed or failed broker')
        validate_policy(self.policy)
        if identity()['boot_id']!=self.policy['boot_id']:raise RuntimeError('Boot changed')

    def records(self):
        if self.lock_fd is None:raise RuntimeError('Broker lease is not held')
        allowed={'RELEASE.json','.lease','recordings','broker','code',*self.plan['slot_names']}
        from field_operator_broker_files_v1 import inspect
        inspect(self.root)
        if set(p.name for p in self.root.iterdir())!=allowed:raise ValueError('Broker root membership')
        result={};total=(self.root/'RELEASE.json').stat().st_size
        for name in self.plan['slot_names']:
            directory=self.root/name
            if directory.is_symlink() or not directory.is_dir():raise ValueError('Slot directory type')
            docs={}
            for p in directory.iterdir():
                if p.name.endswith('.pending'):raise RuntimeError('Preserved pending session record; no retry')
                if p.name not in {k+'.json' for k in RECORDS}:raise ValueError('Unallocated slot file')
                doc=read(p,16384);total+=p.stat().st_size
                if doc.get('slot')!=name or doc.get('policy_sha256')!=file_pin(self.root/'RELEASE.json')['sha256']:
                    raise ValueError('Session record root/policy binding')
                docs[p.stem]=doc
            state(docs);result[name]=docs
        if total>self.plan['metadata_maximum_bytes']:raise RuntimeError('Metadata reservation exceeded')
        recording_dir=self.root/'recordings'
        if recording_dir.is_symlink() or not recording_dir.is_dir():raise ValueError('Real recordings parent')
        recording_roots={p.name for p in recording_dir.iterdir()}
        if recording_roots-set(result):raise ValueError('Unallocated recording root')
        for name in recording_roots:
            p=self.root/'recordings'/name
            if p.is_symlink() or not p.is_dir() or not result[name]:
                raise ValueError('Unreserved recording root')
        return result

    def _publish(self, name, kind, value):
        self._live()
        if name not in self.plan['slot_names'] or kind not in RECORDS:raise ValueError('Record slot')
        records=self.records()
        if kind in records[name]:raise FileExistsError('Immutable session record')
        record=dict(slot=name,policy_sha256=file_pin(self.root/'RELEASE.json')['sha256'],
                    utc=datetime.now(timezone.utc).isoformat(),**value)
        trial={**records[name],kind:record};state(trial)
        raw=encoded(record)
        if len(raw)>16384:raise ValueError('Session metadata slot exhausted')
        if shutil.disk_usage(self.root).free<5*1024**3+len(raw):raise RuntimeError('Pi free floor')
        directory=self.root/name;pending=directory/(kind+'.json.pending');final=directory/(kind+'.json')
        self.failed=True  # Any write/fsync/rename fault permanently fences this instance.
        with pending.open('xb') as f:
            view=memoryview(raw)
            while view:
                count=f.write(view)
                if not count:raise OSError('Session short write')
                view=view[count:]
            f.flush();os.fsync(f.fileno())
        # Unique names, held lifetime lease, no replacement is allowed.
        if final.exists():raise FileExistsError('Session primary appeared')
        os.link(pending,final,follow_symlinks=False)
        self._sync_directory(directory)
        pending.unlink()
        self._sync_directory(directory)
        if final.read_bytes()!=raw:raise IOError('Session metadata readback')
        self.failed=False
        return record

    def reserve(self):
        self._live();records=self.records();name=next_slot(self.plan,records)
        import subprocess
        target=self.root.parent
        total=int(subprocess.check_output(['du','-sb',str(target)],text=True,timeout=10).split()[0])
        own=int(subprocess.check_output(['du','-sb',str(self.root)],text=True,timeout=10).split()[0])
        if own>self.plan['target_maximum_bytes']:raise RuntimeError('Session root aggregate budget')
        outside=total-own;p=self.policy;request=self.plan['combined_request_bytes']
        if p['host_window_bytes']+outside+request>p['combined_output_cap_bytes']:
            raise RuntimeError('Fresh target-inclusive output census')
        if p['payload_before_bytes']+max(0,outside-p['target_before_bytes'])+request>p['total_payload_cap_bytes']:
            raise RuntimeError('Fresh target-inclusive payload census')
        if shutil.disk_usage(self.root).free<5*1024**3+self.plan['target_per_session']:
            raise RuntimeError('Full next recording reservation unavailable')
        root=self.root/'recordings'/name
        if root.exists():raise FileExistsError('Recording root already exists')
        self._publish(name,'RESERVED',dict(root=str(root),mode='delayed',
            target_maximum_bytes=self.plan['target_per_session'],
            host_maximum_bytes=self.plan['host_per_session'],broker_owner=identity()))
        return root

    def staged(self, name):
        self._live();records=self.records()
        if state(records[name])!='ACTIVE' or set(records[name])!={'RESERVED'}:
            raise RuntimeError('Stage requires a single unconsumed reservation')
        root=self.root/'recordings'/name;a=read(root/'control/ADMISSION.json')
        if a['output_root']!=str(root) or a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION':
            raise ValueError('Exact actual recording admission')
        if a['target_maximum_bytes']!=self.plan['target_per_session'] or a['host_maximum_bytes']!=self.plan['host_per_session']:
            raise ValueError('Per-recording envelope changed')
        if not datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])<=datetime.fromisoformat(self.policy['expires_utc']):
            raise ValueError('Recording admission extends broker policy')
        pins={n:file_pin(root/n) for n in ('control/ADMISSION.json','control/MANIFEST.json','config/CONFIG.json')}
        return self._publish(name,'STAGED',dict(pins=pins))

    def started(self, name, owner):
        self._live();records=self.records()
        if set(records[name])!={'RESERVED','STAGED'}:raise RuntimeError('Start sequence')
        if type(owner) is not dict or set(owner)!={'pid','start_ticks','boot_id'} or any(type(owner[k]) is not int or owner[k]<=0 for k in ('pid','start_ticks')) or owner['boot_id']!=self.policy['boot_id'] or ticks(owner['pid'])!=owner['start_ticks']:
            raise ValueError('Exact live recording-parent owner')
        if read(self.root/'recordings'/name/'control/OWNER.json')!=owner:
            raise ValueError('Actual staged parent owner differs')
        return self._publish(name,'STARTED',dict(owner=owner))

    def complete(self, name):
        self._live();records=self.records()
        if set(records[name])!={'RESERVED','STAGED','STARTED'}:raise RuntimeError('Completion sequence')
        root=self.root/'recordings'/name
        parent=read(root/'parent_control/RESULT.json');app=read(root/'receipts/APPLICATION_CLOSURE.json')
        result=read(root/'receipts/RESULT.json');launcher=read(root/'closure/launcher.json')
        owners=[records[name]['STARTED']['owner'],parent['child_owner']]
        if parent['owner']!=records[name]['STARTED']['owner'] or launcher['owner']!=parent['owner']:
            raise RuntimeError('Recording parent identity drift')
        if any(o['boot_id']==self.policy['boot_id'] and ticks(o['pid'])==o['start_ticks'] for o in owners):
            raise RuntimeError('Exact application owner remains alive')
        if (parent['status']!='PASS_PARENT_RETURN_ONLY' or not parent['child_reaped']
            or parent['watcher'].get('terminate_sent') or parent['watcher'].get('kill_sent')
            or result['status']!='INTERACTIVE_RETURN_REQUESTED'
            or not app['controller_closed'] or not app['worker_joined'] or app['pending_commands']
            or app['physical']['open_writable_descriptors'] or app['physical']['failures']
            or not launcher['child_reaped'] or not launcher['watcher_joined']
            or not launcher['capture_closed'] or not app['capture_closed']
            or Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()!='closed'):
            raise RuntimeError('Actual full closure not established')
        if result.get('actual_capture_started'):
            source=read(root/'source/CHILD_OWNER.json')
            if source['boot_id']==self.policy['boot_id'] and ticks(source['pid'])==source['start_ticks']:
                raise RuntimeError('Source remains alive')
            stop=read(root/'receipts/GUI_STOP.json');model=read(root/'receipts/MODEL_CLOSURE.json')
            if (not stop['source_thread_joined'] or not stop['archive_thread_joined']
                or not model['closed'] or not model['finish_observed']
                or model['samples']!=result['source_samples']):
                raise RuntimeError('Source/model/archive closure incomplete')
        names=['parent_control/RESULT.json','receipts/APPLICATION_CLOSURE.json',
               'receipts/RESULT.json','closure/launcher.json']
        if result.get('actual_capture_started'):
            names+=['source/CHILD_OWNER.json','receipts/GUI_STOP.json','receipts/MODEL_CLOSURE.json']
        pins={n:file_pin(root/n) for n in names}
        return self._publish(name,'CLOSED',dict(pins=pins,owners=owners,
            source_samples=result.get('source_samples',0),capture_closed=True))

    def fail(self, name, request_stop, reason):
        # Caller must Stop before diagnostic publication. No record is erased.
        request_stop()
        return self._publish(name,'FAILED',dict(reason=str(reason)[:1024]))

    def history(self):
        """Read-only saved-recording descriptors; no constructor or mutation."""
        rows=[]
        for name,records in self.records().items():
            if state(records)!='CLOSED':continue
            root=self.root/'recordings'/name
            for relative,pin in records['CLOSED']['pins'].items():
                if file_pin(root/relative)!=pin:raise RuntimeError('Closed session receipt drift')
            folders=list((root/'data/conversations').iterdir())
            if len(folders)>1:raise ValueError('One recording per independent session')
            for folder in folders:
                if folder.is_symlink() or not folder.is_dir():raise ValueError('History link')
                document=read(folder/'conversation.json')
                if document.get('state')=='SAVED' and document.get('pinned') is True:
                    rows.append(dict(slot=name,root=str(root),conversation_id=folder.name,
                        metadata_pin=file_pin(folder/'conversation.json')))
        return rows
