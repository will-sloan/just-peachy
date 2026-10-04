"""External finite selected export from an unchanged package. README_NATIVE_EXPORT.md."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

DRIVER = r'''
import json,os,resource,sys,time
from pathlib import Path
out=Path(sys.argv[1]);package=Path(sys.argv[2]);selected=sys.argv[3];source=Path(sys.argv[4]);maximum=int(sys.argv[6])
resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,768*1024**2))
soft,hard=resource.getrlimit(resource.RLIMIT_FSIZE);resource.setrlimit(resource.RLIMIT_FSIZE,(32*1024**2,hard))
sys.path.insert(0,str(package))
from owned_export import put,memory,digest,plan_export
from storage import SessionStore,StoragePolicy
from launcher import Manager,show
from native_gui_driver import widgets,named_widget,display_state
import tkinter as tk
from tkinter import filedialog,messagebox
ui=out/'gui';ui.mkdir()
unit=json.loads((out/'UNIT_OWNERSHIP.json').read_bytes())
before_display=display_state(ui,'DISPLAY_BEFORE.json',put)
manager=Manager(package/'BINDING.json',out/'ui-data',unit['unit'],unit_ownership=out/'UNIT_OWNERSHIP.json')
manager.store.close()
manager.store=SessionStore(source,StoragePolicy(**manager.binding.get('storage_policy',{})),read_only=True)
before=manager.store.read(selected);before_db=digest(manager.store.db_path)
if before['status']!='kept':raise ValueError('Exact existing kept recording required')
plan=plan_export(manager.store,[selected],out/'selected-recording.zip')
if plan['maximum_bytes']+16*1024**2>maximum:raise ValueError('Reviewed GUI export reservation too small')
put(ui/'ENVELOPE.json',dict(memory=memory(),address_space=list(resource.getrlimit(resource.RLIMIT_AS)),file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)),models_loaded=False,capture=False))
state=dict(root=None,geometry=[],failure=None,export_invoked=0,exit_invoked=0,stage='geometry',deadline=time.monotonic()+155,task_directory=None)
original_tk=tk.Tk;original_dialog=filedialog.asksaveasfilename;original_error=messagebox.showerror

def fail(exc):
 if state['failure'] is None:state['failure']=dict(type=type(exc).__name__,message=str(exc)[:2048])
 close()

def close():
 try:
  named_widget(state['root'],'Exit to desktop').invoke();state['exit_invoked']+=1
  if not manager.closed:state['root'].after(100,close)
 except tk.TclError:
  if not manager.closed:raise

def tick():
 try:
  root=state['root']
  if state['failure']:close();return
  if time.monotonic()>state['deadline']:raise TimeoutError('Finite actual History Export UI deadline')
  if state['stage']=='geometry':
   extent=(root.winfo_width(),root.winfo_height(),root.winfo_rootx(),root.winfo_rooty())
   full=bool(root.attributes('-fullscreen'))
   if extent==(480,800,0,0) and full:state['geometry'].append(dict(extent=extent,fullscreen=full))
   else:state['geometry']=[]
   if len(state['geometry'])==10:
    books=[w for w in widgets(root) if w.winfo_class()=='TNotebook']
    if len(books)!=1:raise ValueError('Exact actual notebook required')
    tabs=[tab for tab in books[0].tabs() if books[0].tab(tab,'text')=='Recordings']
    if len(tabs)!=1:raise ValueError('Actual Recordings tab required')
    books[0].select(tabs[0]);root.update_idletasks()
    trees=[w for w in widgets(root) if w.winfo_class()=='Treeview']
    if len(trees)!=1 or not trees[0].exists(selected):raise ValueError('Exact kept recording must appear in real History')
    trees[0].selection_set(selected);trees[0].see(selected)
    button=named_widget(root,'Export');button.invoke();state['export_invoked']+=1
    if manager.export_task is None:raise RuntimeError('Real History Export callback did not create an owned task')
    state['task_directory']=str(manager.export_task.directory);state['stage']='export'
  elif state['stage']=='export' and manager.last_export is not None:
   if manager.export_task is not None or manager.last_export.get('status')!='EXPORTED':raise RuntimeError('Owned History Export failed: '+str(manager.last_export))
   if manager.store.read(selected)!=before or digest(manager.store.db_path)!=before_db:raise RuntimeError('Original source metadata changed')
   put(out/'EXPORT.json',dict(manager.last_export,session_id=selected,child_receipt_directory=state['task_directory']))
   state['stage']='complete';close();return
  root.after(100,tick)
 except BaseException as exc:fail(exc)

def tracked(*args,**kwargs):
 root=original_tk(*args,**kwargs);state['root']=root;root.after(150,tick);return root

def choose_destination(*args,**kwargs):return str(out/'selected-recording.zip')
def error_dialog(title,message,*args,**kwargs):
 state['failure']=dict(type='ActualHistoryDialogError',message=str(message)[:2048]);return None

tk.Tk=tracked;filedialog.asksaveasfilename=choose_destination;messagebox.showerror=error_dialog
try:show(manager)
finally:
 tk.Tk=original_tk;filedialog.asksaveasfilename=original_dialog;messagebox.showerror=original_error
 if not manager.closed:manager.close()
after_display=display_state(ui,'DISPLAY_AFTER.json',put)
passed=state['stage']=='complete' and not state['failure'] and manager.closed and state['export_invoked']==1 and state['exit_invoked']>=1
put(ui/'GUI_EXPORT_RESULT.json',dict(schema='just-peachy.history-export-ui.v1',functional_success=passed,
 actual_tk=True,geometry_samples=state['geometry'],history_export_invocations=state['export_invoked'],exit_invocations=state['exit_invoked'],
 file_dialog_destination_injected=True,selected_session_id=selected,source_store_opened_read_only=True,
 original_metadata_sha256=before_db,original_metadata_preserved=digest(manager.store.db_path)==before_db,
 desktop_orientation_270_before_after=True,capture_started=False,models_loaded=False,physical_touch_qualified=False,
 screenshot_quality_qualified=False,failure=state['failure']))
if not passed:raise RuntimeError('Actual History Export UI check failed')
'''
EXPORT_HELPER = r'''"""Fresh, bounded selected-recording export child. See README_OWNED_EXPORT.md."""
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
'''


def export_wrapper(shared,settings):
    """Only add the exact Store ZIP transaction; retained pending rule is unchanged."""
    source=shared(settings)
    anchor="def bounded_output():\n total=count=0\n"
    if source.count(anchor)!=1:raise ValueError('Exact10 guard definition boundary')
    source=source.replace(anchor,anchor+" archive_inodes=set()\n")
    anchor="   if info.st_nlink!=1:\n"
    if source.count(anchor)!=1:raise ValueError('Exact10 guard link boundary')
    source=source.replace(anchor,"   archive=path.parent==out and (name=='selected-recording.zip' or name.startswith('selected-recording.zip.part-') and len(name)==60 and all(c in '0123456789abcdef' for c in name[-32:]))\n"+anchor)
    anchor="    peer=path.with_name(name[:-8]) if name.endswith('.pending') and len(name)>8 else path.with_name(name+'.pending')\n"
    replacement=r'''    if archive:
     if name!='selected-recording.zip':peer=out/'selected-recording.zip'
     else:
      peers=[];scanned=0
      for candidate in out.iterdir():
       scanned+=1
       if scanned>256:fail('archive_peer_membership',path,info)
       if candidate.name.startswith('selected-recording.zip.part-') and len(candidate.name)==60 and all(c in '0123456789abcdef' for c in candidate.name[-32:]):
        try:other_candidate=candidate.lstat()
        except FileNotFoundError:continue
        if (other_candidate.st_dev,other_candidate.st_ino)==(info.st_dev,info.st_ino):peers.append(candidate)
      peer=peers[0] if len(peers)==1 else out/'selected-recording.zip.no-valid-peer'
    else:
     peer=path.with_name(name[:-8]) if name.endswith('.pending') and len(name)>8 else path.with_name(name+'.pending')
'''
    if source.count(anchor)!=1:raise ValueError('Exact10 retained pending peer boundary')
    source=source.replace(anchor,replacement)
    anchor='   total+=info.st_size\n'
    replacement="   if archive:\n    key=(info.st_dev,info.st_ino)\n    if key in archive_inodes:continue\n    archive_inodes.add(key)\n"+anchor
    if source.count(anchor)!=1:raise ValueError('Exact10 output charge boundary')
    source=source.replace(anchor,replacement)
    compile(source,'<exact10-history-export-guard>','exec');return source

def dispatch(p, baseline):
    if baseline.get('current_project_processes') or baseline.get('active_recorded_owners') or baseline.get('live_manager_owners'):
        raise ValueError('Fresh full existing source/owner closure required')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if p['boot_id']!=boot or not time.time()<p['expires_unix']<=time.time()+600:
        raise ValueError('Fresh exact boot admission required')
    package=Path(p['package'])
    campaign=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
    if package.parent!=campaign or re.fullmatch(r'field-runtime-v29-build-\d{2}',package.name) is None:
        raise ValueError('Explicit immutable source package required')
    raw=(package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=p['package_manifest_sha256']:
        raise ValueError('Pinned complete package required')
    manifest=json.loads(raw)
    entry=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
    helper_path=package/entry['path'];source=helper_path.read_bytes()
    if (helper_path.resolve(strict=True)!=helper_path or len(source)!=entry['bytes'] or
        hashlib.sha256(source).hexdigest()!=entry['sha256'] or len(source)>131072):
        raise ValueError('Exact immutable shared wrapper required')
    namespace=dict(__name__='verified_export_helper',__file__=str(helper_path))
    exec(compile(source,str(helper_path),'exec'),namespace)
    namespace['inventory'](package,p['package_manifest_sha256'])
    binding=json.loads((package/'BINDING.json').read_bytes())
    if binding['target']!=str(package):raise ValueError('Exact export package target required')
    label=p['label']
    if re.fullmatch(r'recording-export-\d{2}',label) is None or re.fullmatch(r'[0-9a-f]{32}',p['session_id']) is None:
        raise ValueError('Fresh export label and exact selected session ID required')
    if type(p['maximum_output_bytes']) is not int or not 16*1024**2<=p['maximum_output_bytes']<=256*1024**2:
        raise ValueError('Explicit full ZIP plus16MiB overhead reservation required, maximum256MiB')
    old_job=p['source_job'];source_root=Path(old_job['output_root'])
    if (re.fullmatch(r'gui-qualification-\d{2}',source_root.name) is None or
        old_job['unit']!='jp-v29-'+source_root.name+'.service' or
        old_job['package_manifest_sha256']!=p['source_package_manifest_sha256'] or
        Path(p['recordings_root'])!=source_root/'data/recordings'):
        raise ValueError('Exact closed GUI job recording root/package required')
    # Use the existing independently owned systemd helper, retaining its utility
    # receipts inside this action result instead of printing protocol frames.
    probe=namespace['load_pure'](package,'native_job_probe');utilities=[];probe.emit=utilities.append
    _,closed=probe.inspect(old_job)
    if not all(closed.get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty')):
        raise ValueError('Selected source job has not actually closed')
    if shutil.disk_usage(campaign).free<5*1024**3+p['maximum_output_bytes']:
        raise OSError('Native floor plus independent exported ZIP allocation unavailable')
    unit='jp-v29-'+label+'.service';out=campaign/'live-runtime-tests-20261003'/label
    old=subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'],capture_output=True,text=True,timeout=5)
    if old.stdout.strip()!='LoadState=not-found':raise ValueError('Fresh unique export unit required')
    if out.parent.resolve(strict=True)!=out.parent:raise ValueError('Canonical existing output parent required')
    out.mkdir()
    put=namespace['put'];sha=namespace['sha']
    settings=dict(output=str(out),package=str(package),unit=unit,boot_id=boot,expires_unix=p['expires_unix'],
        package_manifest_sha256=p['package_manifest_sha256'],scope_sha256=sha(package/'native_scope.py'),
        research_lock=str(campaign/'B05_PREVIEW_DISPATCH.lock'),kind='selected_export',template=None,
        budget=dict(maximum_output_bytes=p['maximum_output_bytes'],runtime_seconds=180,stop_seconds=30,
            file_limit_bytes=p['maximum_output_bytes']-8*1024**2),
        argv=[str(out/'export_driver.py'),str(out),str(package),p['session_id'],p['recordings_root'],p['package_manifest_sha256'],str(p['maximum_output_bytes'])])
    wrapper=export_wrapper(namespace['wrapper_source'],settings).encode()
    observed_env=subprocess.run(['systemctl','--user','show-environment'],capture_output=True,text=True,timeout=5,check=True)
    if len(observed_env.stdout)>65536:raise ValueError('Finite desktop environment required')
    desktop_env=dict(line.split('=',1) for line in observed_env.stdout.splitlines() if '=' in line)
    if not desktop_env.get('DISPLAY') or not desktop_env.get('XDG_RUNTIME_DIR'):raise ValueError('Existing actual desktop environment required')
    for name,data in (('export_driver.py',DRIVER.encode()),('owned_export.py',EXPORT_HELPER.encode()),('wrapper.py',wrapper)):
        with (out/name).open('xb') as stream:
            if stream.write(data)!=len(data):raise OSError('Short export preparation write')
            stream.flush();os.fsync(stream.fileno())
        if (out/name).read_bytes()!=data:raise OSError('Export preparation readback')
    put(out/'ADMISSION.json',dict(payload=p,closed_source=closed,source_probe_utilities=utilities,
        export_driver_sha256=hashlib.sha256(DRIVER.encode()).hexdigest(),export_helper_sha256=hashlib.sha256(EXPORT_HELPER.encode()).hexdigest(),wrapper_sha256=hashlib.sha256(wrapper).hexdigest(),
        native_reservation_bytes=p['maximum_output_bytes'],independent_host_reservation_bytes=p['maximum_output_bytes'],
        capture=False,models_loaded=False,source_package_modified=False))
    args=['systemd-run','--user','--unit='+unit,'--description=JustPeachySelectedExport',
        '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64',
        '--property=RuntimeMaxSec=180','--property=TimeoutStopSec=30','--property=KillMode=control-group',
        '--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=MALLOC_ARENA_MAX=1','--setenv=MALLOC_MMAP_THRESHOLD_=131072','--setenv=MALLOC_TRIM_THRESHOLD_=131072',binding['python'],'-B',str(out/'wrapper.py')]
    args[-3:-3]=['--setenv='+key+'='+desktop_env[key] for key in ('DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS') if desktop_env.get(key)]
    started=subprocess.run(args,capture_output=True,text=True,timeout=10)
    put(out/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode:raise RuntimeError('Selected export unit failed to launch')
    end=time.monotonic()+5
    while not (out/'OWNER.json').exists() and time.monotonic()<end:time.sleep(.05)
    owner=json.loads((out/'OWNER.json').read_bytes()) if (out/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],
        capture_output=True,text=True,timeout=5,check=True)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    job=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,owner=owner,
        invocation_id=props.get('InvocationID'),control_group=props.get('ControlGroup'),properties=props,
        output_root=str(out),maximum_output_bytes=p['maximum_output_bytes'],
        package_manifest_sha256=p['package_manifest_sha256'],issued_unix=time.time(),deadline_unix=time.time()+225)
    put(out/'JOB.json',job);return job


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
