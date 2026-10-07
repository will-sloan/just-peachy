"""Fresh, bounded selected-recording export child. See README_OWNED_EXPORT.md."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

MIB = 1024**2
ALLOCATOR = dict(MALLOC_ARENA_MAX='1', MALLOC_MMAP_THRESHOLD_='131072', MALLOC_TRIM_THRESHOLD_='131072')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def put(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > 65536:
        raise ValueError('Export receipt exceeds 64 KiB')
    with Path(path).open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short export receipt')
        stream.flush(); os.fsync(stream.fileno())
    if Path(path).read_bytes() != raw:
        raise OSError('Export receipt readback differs')
    if os.name != 'nt':
        fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def identity(pid):
    try:
        ticks = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None
    return dict(pid=pid, start_ticks=ticks, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def memory():
    values = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        key, _, value = line.partition(':')
        if key in ('VmSize', 'VmPeak', 'VmRSS', 'VmHWM', 'VmSwap', 'Threads'):
            values[key] = value.strip()
    return values


def plan_export(store, session_ids, destination):
    """Match Store.export's streamed reservation, including decoded event bytes."""
    from storage import _safe
    destination = _safe(Path(destination).absolute())
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError('Export requires a new path in an existing directory')
    selected = list(session_ids)
    if not selected or len(selected) > store.policy.max_export_sessions or len(set(selected)) != len(selected):
        raise ValueError('Select a bounded, nonduplicate set of kept recordings')
    required = 65536; entries = 0; metadata = []
    for sid in selected:
        row = store.read(sid)
        if row['status'] != 'kept':
            raise ValueError('Export accepts only kept recordings')
        metadata.append(hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest())
        required += len(json.dumps(row, sort_keys=True).encode()) + 4096
        entries += 5
        for segment in store._segments(sid):
            for name in (segment['data_name'], segment['replay_name']):
                if name:
                    required += store._audio_path(sid, name).stat().st_size + 1024
                    entries += 1
        with store._db() as db:
            required += db.execute('SELECT COALESCE(SUM(LENGTH(text)*6+LENGTH(provenance)+4096),0) FROM captions WHERE session_id=?', (sid,)).fetchone()[0]
            required += db.execute('SELECT COALESCE(SUM(CASE WHEN payload_bytes>0 THEN payload_bytes ELSE LENGTH(CAST(payload AS BLOB)) END+4096),0) FROM events WHERE session_id=?', (sid,)).fetchone()[0]
        for artifact in store._artifacts(sid):
            path = store._artifact_path(sid, artifact['path'])
            if path.stat().st_size != artifact['bytes']:
                raise ValueError('Kept artifact extent changed')
            required += artifact['bytes'] + 1024; entries += 1
        if entries > store.policy.max_export_entries:
            raise ValueError('Export entry reservation exhausted; select fewer recordings')
    store._capacity(required, destination.parent)
    return dict(session_ids=selected, destination=str(destination), maximum_bytes=required,
                entries=entries, session_metadata_sha256=metadata)


def file_limit(maximum_bytes, inherited_hard):
    import resource
    if type(maximum_bytes) is not int or maximum_bytes < 65536:
        raise ValueError('Explicit finite export allocation required')
    if inherited_hard == resource.RLIM_INFINITY or maximum_bytes > inherited_hard:
        raise ValueError('Export allocation exceeds the inherited finite file ceiling')
    return maximum_bytes


def read_only_export_store(root, policy):
    """Select shared leases for unmodified export on a query-only SQLite store."""
    from storage import SessionStore
    class SharedExportStore(SessionStore):
        def _session_lease(self, session_id, *, shared=False):
            if not self.read_only:
                raise ValueError('Shared export adapter requires a read-only store')
            return super()._session_lease(session_id, shared=True)
    return SharedExportStore(root, policy, read_only=True)


class ExportTask:
    """Pollable direct child; callers retain ownership until finished or cancelled."""
    def __init__(self, store, session_ids, destination, work_directory, *, python=sys.executable,
                 timeout_seconds=130, deadline_monotonic=None):
        import resource
        if not 1 <= timeout_seconds <= 300:
            raise ValueError('Finite export deadline required')
        if deadline_monotonic is not None and deadline_monotonic-time.monotonic() < timeout_seconds+20:
            raise ValueError('Service has insufficient time to close this export')
        plan = plan_export(store, session_ids, destination)
        # Reserve bounded private control receipts independently of the ZIP.
        store._capacity(plan['maximum_bytes']+65536, Path(plan['destination']).parent)
        limit = file_limit(plan['maximum_bytes'], resource.getrlimit(resource.RLIMIT_FSIZE)[1])
        from storage import _safe
        base = _safe(Path(work_directory).absolute())
        store._capacity(65536, base.parent)
        base.mkdir(parents=True, exist_ok=True)
        self.directory = base/uuid.uuid4().hex; self.directory.mkdir()
        self.child_directory = self.directory/'child'; self.child_directory.mkdir()
        module = Path(sys.modules[store.__class__.__module__].__file__).resolve(strict=True)
        source = Path(__file__).resolve(strict=True)
        self.request = dict(schema='just-peachy.owned-export-request.v1', plan=plan,
            store_root=str(store.root), storage_policy=asdict(store.policy), storage_module=str(module),
            storage_sha256=digest(module), helper_sha256=digest(source), file_limit_bytes=limit)
        put(self.directory/'REQUEST.json', self.request)
        put(self.directory/'PARENT_MEMORY.json', dict(owner=identity(os.getpid()), memory=memory(),
            inherited_file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)),
            inherited_address_space=list(resource.getrlimit(resource.RLIMIT_AS)), parent_limits_changed=False))
        env = dict(os.environ, **ALLOCATOR, PYTHONDONTWRITEBYTECODE='1')
        self.process = subprocess.Popen([str(python), '-B', str(source), '--child', str(self.directory),
            '--request-sha256', digest(self.directory/'REQUEST.json')], env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        self.owner = None; self.finished = False; self.result = None; self.error = None
        self.started = time.monotonic(); self.deadline = self.started+timeout_seconds
        self.cancelled = False; self.terminated = None; self.killed = False

    def cancel(self):
        self.cancelled = True
        if self.process.poll() is None and self.terminated is None:
            # Popen owns this unreaped direct child; never signal a receipt-only PID.
            self.process.terminate(); self.terminated = time.monotonic()

    def poll(self):
        if self.finished:
            return self.result
        try:
            owner_path = self.child_directory/'OWNER.json'
            if self.owner is None and owner_path.exists():
                owner = json.loads(owner_path.read_bytes())
                if (set(owner) != {'pid','start_ticks','boot_id'} or owner != identity(self.process.pid) or
                    Path('/proc', str(self.process.pid), 'cgroup').read_bytes() != Path('/proc/self/cgroup').read_bytes()):
                    raise RuntimeError('Export child identity or cgroup differs')
                self.owner = owner
                put(self.child_directory/'PARENT_ACK.json', dict(owner=owner, same_cgroup=True))
            if time.monotonic() > self.deadline or (self.owner is None and time.monotonic()-self.started > 8):
                self.error = self.error or 'Export deadline or owner handshake expired'; self.cancel()
            if self.terminated is not None and self.process.poll() is None and time.monotonic()-self.terminated > 5:
                if not self.killed: self.process.kill(); self.killed = True
            code = self.process.poll()
            if code is None:
                return None
            self.process.wait(timeout=0)
            gone = identity(self.process.pid) != self.owner if self.owner else True
            if not gone:
                raise RuntimeError('Export child remains active after direct reap')
            closure = dict(owner=self.owner, child_pid=self.process.pid, exit_code=code,
                exact_owner_gone=gone, direct_child_reaped=True, cancelled=self.cancelled, forced_reap=self.terminated is not None)
            closed_path = self.child_directory/'CLOSED.json'
            closed = json.loads(closed_path.read_bytes()) if closed_path.exists() else None
            if code or self.owner is None or closed is None or closed.get('owner') != self.owner or closed.get('status') != 'EXPORTED':
                self.error = self.error or 'Selected export failed: '+str((closed or {}).get('error') or code)
            if self.error is None:
                self.result = json.loads((self.directory/'EXPORT.json').read_bytes())
            else:
                self.result = dict(status='FAILED', error=self.error)
            put(self.directory/'CHILD_CLOSURE.json', dict(**closure, error=self.error))
            self.finished = True
            return self.result
        except BaseException as exc:
            self.error = str(exc)[:2048]; self.cancel()
            if self.process.poll() is not None:
                self.process.wait(timeout=0)
                self.finished = True; self.result = dict(status='FAILED', error=self.error)
                put(self.directory/'CHILD_CLOSURE.json', dict(owner=self.owner, child_pid=self.process.pid,
                    exit_code=self.process.returncode, exact_owner_gone=identity(self.process.pid) != self.owner,
                    direct_child_reaped=True, forced_reap=self.terminated is not None, error=self.error))
            return self.result


def child(directory, request_sha):
    import resource
    os.sched_setaffinity(0, {2,3})
    root = Path(directory); childroot = root/'child'
    owner = identity(os.getpid()); put(childroot/'OWNER.json', owner)
    # Durable actual owner precedes all request/package reads and project imports.
    error = None; status = 'FAILED'
    try:
        put(childroot/'BEFORE_LIMIT.json', dict(owner=owner, memory=memory(),
            address_space=list(resource.getrlimit(resource.RLIMIT_AS))))
        resource.setrlimit(resource.RLIMIT_AS, (128*MIB,128*MIB))
        resource.setrlimit(resource.RLIMIT_STACK, (MIB,MIB)); resource.setrlimit(resource.RLIMIT_CORE, (0,0))
        request_path = root/'REQUEST.json'
        if request_path.stat().st_size > 65536 or digest(request_path) != request_sha:
            raise ValueError('Pinned bounded export request differs')
        request = json.loads(request_path.read_bytes())
        if request.get('schema') != 'just-peachy.owned-export-request.v1' or digest(__file__) != request['helper_sha256']:
            raise ValueError('Pinned export worker differs')
        limit = file_limit(request['file_limit_bytes'], resource.getrlimit(resource.RLIMIT_FSIZE)[1])
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit,limit))
        put(childroot/'ENVELOPE.json', dict(owner=owner, memory=memory(),
            address_space=list(resource.getrlimit(resource.RLIMIT_AS)), file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)),
            allocator_environment={key:os.environ.get(key) for key in ALLOCATOR}, affinity=sorted(os.sched_getaffinity(0))))
        if any(os.environ.get(key) != value for key,value in ALLOCATOR.items()):
            raise ValueError('Retained allocator environment must precede export exec')
        deadline = time.monotonic()+10
        while not (childroot/'PARENT_ACK.json').exists() and time.monotonic() < deadline: time.sleep(.02)
        ack = json.loads((childroot/'PARENT_ACK.json').read_bytes())
        if ack != dict(owner=owner, same_cgroup=True):
            raise ValueError('Exact export child parent ACK required')
        module = Path(request['storage_module'])
        if module.name != 'storage.py' or module.resolve(strict=True) != module or digest(module) != request['storage_sha256']:
            raise ValueError('Pinned storage module differs')
        sys.path.insert(0, str(module.parent))
        from storage import SessionStore, StoragePolicy
        store = read_only_export_store(request['store_root'], StoragePolicy(**request['storage_policy']))
        try:
            wanted = request['plan']
            if plan_export(store, wanted['session_ids'], wanted['destination']) != wanted or limit != wanted['maximum_bytes']:
                raise ValueError('Selected export allocation or metadata changed')
            path = store.export(wanted['session_ids'], wanted['destination'])
            for sid,expected in zip(wanted['session_ids'],wanted['session_metadata_sha256']):
                if hashlib.sha256(json.dumps(store.read(sid),sort_keys=True).encode()).hexdigest() != expected:
                    raise ValueError('Original selected recording metadata changed')
            put(root/'EXPORT.json', dict(schema='just-peachy.native-selected-export.v1', status='EXPORTED',
                session_ids=wanted['session_ids'], source_root=str(store.root), zip_path=str(path),
                zip_bytes=path.stat().st_size, zip_sha256=digest(path), original_session_preserved=True,
                source_deleted=False, capture=False, models_loaded=False, maximum_bytes=wanted['maximum_bytes']))
            status = 'EXPORTED'
        finally: store.close()
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc)[:2048]); raise
    finally:
        put(childroot/'CLOSED.json', dict(owner=owner, status=status, error=error, memory=memory()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--child', required=True)
    parser.add_argument('--request-sha256', required=True); args = parser.parse_args()
    child(args.child, args.request_sha256)
