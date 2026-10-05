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
import json,sys,time
from pathlib import Path
out=Path(sys.argv[1]);package=Path(sys.argv[2]);session_id=sys.argv[3];data=Path(sys.argv[4]);maximum=int(sys.argv[6])
sys.path.insert(0,str(out))
from owned_export import ExportTask,put,memory,identity,plan_export
put(out/'EXPORT_PARENT_MEMORY.json',dict(scope='shared_wrapper_before_storage_import',owner=identity(__import__('os').getpid()),memory=memory()))
sys.path.insert(0,str(package))
from storage import SessionStore,StoragePolicy
binding=json.loads((package/'BINDING.json').read_bytes())
store=SessionStore(data,StoragePolicy(**binding.get('storage_policy',{})),read_only=True)
try:
 plan=plan_export(store,[session_id],out/'selected-recording.zip')
 if plan['maximum_bytes']+16*1024**2>maximum:raise ValueError('Selected ZIP plus independent metadata exceeds admitted reservation')
 task=ExportTask(store,[session_id],out/'selected-recording.zip',out/'exports',python=sys.executable)
 while not task.finished:task.poll();time.sleep(.05)
 if task.result['status']!='EXPORTED':raise RuntimeError(task.result.get('error','Selected export failed'))
 put(out/'EXPORT.json',dict(task.result,session_id=session_id,child_receipt_directory=str(task.directory)))
finally:store.close()
'''
EXPORT_HELPER = '"""Fresh, bounded selected-recording export child. See README_OWNED_EXPORT.md."""\nfrom __future__ import annotations\nimport argparse\nfrom dataclasses import asdict\nimport hashlib\nimport json\nimport os\nfrom pathlib import Path\nimport subprocess\nimport sys\nimport time\nimport uuid\n\nMIB = 1024**2\nALLOCATOR = dict(MALLOC_ARENA_MAX=\'1\', MALLOC_MMAP_THRESHOLD_=\'131072\', MALLOC_TRIM_THRESHOLD_=\'131072\')\n\n\ndef digest(path):\n    with Path(path).open(\'rb\') as stream:\n        return hashlib.file_digest(stream, \'sha256\').hexdigest()\n\n\ndef put(path, value):\n    raw = json.dumps(value, sort_keys=True, separators=(\',\', \':\'), allow_nan=False).encode()\n    if len(raw) > 65536:\n        raise ValueError(\'Export receipt exceeds 64 KiB\')\n    with Path(path).open(\'xb\') as stream:\n        if stream.write(raw) != len(raw):\n            raise OSError(\'Short export receipt\')\n        stream.flush(); os.fsync(stream.fileno())\n    if Path(path).read_bytes() != raw:\n        raise OSError(\'Export receipt readback differs\')\n    if os.name != \'nt\':\n        fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)\n        try: os.fsync(fd)\n        finally: os.close(fd)\n\n\ndef identity(pid):\n    try:\n        ticks = int(Path(\'/proc\', str(pid), \'stat\').read_text().rsplit(\')\', 1)[1].split()[19])\n    except FileNotFoundError:\n        return None\n    return dict(pid=pid, start_ticks=ticks, boot_id=Path(\'/proc/sys/kernel/random/boot_id\').read_text().strip())\n\n\ndef memory():\n    values = {}\n    for line in Path(\'/proc/self/status\').read_text().splitlines():\n        key, _, value = line.partition(\':\')\n        if key in (\'VmSize\', \'VmPeak\', \'VmRSS\', \'VmHWM\', \'VmSwap\', \'Threads\'):\n            values[key] = value.strip()\n    return values\n\n\ndef plan_export(store, session_ids, destination):\n    """Match Store.export\'s streamed reservation, including decoded event bytes."""\n    from storage import _safe\n    destination = _safe(Path(destination).absolute())\n    if destination.exists() or not destination.parent.is_dir():\n        raise ValueError(\'Export requires a new path in an existing directory\')\n    selected = list(session_ids)\n    if not selected or len(selected) > store.policy.max_export_sessions or len(set(selected)) != len(selected):\n        raise ValueError(\'Select a bounded, nonduplicate set of kept recordings\')\n    required = 65536; entries = 0; metadata = []\n    for sid in selected:\n        row = store.read(sid)\n        if row[\'status\'] != \'kept\':\n            raise ValueError(\'Export accepts only kept recordings\')\n        metadata.append(hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest())\n        required += len(json.dumps(row, sort_keys=True).encode()) + 4096\n        entries += 5\n        for segment in store._segments(sid):\n            for name in (segment[\'data_name\'], segment[\'replay_name\']):\n                if name:\n                    required += store._audio_path(sid, name).stat().st_size + 1024\n                    entries += 1\n        with store._db() as db:\n            required += db.execute(\'SELECT COALESCE(SUM(LENGTH(text)*6+LENGTH(provenance)+4096),0) FROM captions WHERE session_id=?\', (sid,)).fetchone()[0]\n            required += db.execute(\'SELECT COALESCE(SUM(CASE WHEN payload_bytes>0 THEN payload_bytes ELSE LENGTH(CAST(payload AS BLOB)) END+4096),0) FROM events WHERE session_id=?\', (sid,)).fetchone()[0]\n        for artifact in store._artifacts(sid):\n            path = store._artifact_path(sid, artifact[\'path\'])\n            if path.stat().st_size != artifact[\'bytes\']:\n                raise ValueError(\'Kept artifact extent changed\')\n            required += artifact[\'bytes\'] + 1024; entries += 1\n        if entries > store.policy.max_export_entries:\n            raise ValueError(\'Export entry reservation exhausted; select fewer recordings\')\n    store._capacity(required, destination.parent)\n    return dict(session_ids=selected, destination=str(destination), maximum_bytes=required,\n                entries=entries, session_metadata_sha256=metadata)\n\n\ndef file_limit(maximum_bytes, inherited_hard):\n    import resource\n    if type(maximum_bytes) is not int or maximum_bytes < 65536:\n        raise ValueError(\'Explicit finite export allocation required\')\n    if inherited_hard == resource.RLIM_INFINITY or maximum_bytes > inherited_hard:\n        raise ValueError(\'Export allocation exceeds the inherited finite file ceiling\')\n    return maximum_bytes\n\n\ndef read_only_export_store(root, policy):\n    """Select shared leases for unmodified export on a query-only SQLite store."""\n    from storage import SessionStore\n    class SharedExportStore(SessionStore):\n        def _session_lease(self, session_id, *, shared=False):\n            if not self.read_only:\n                raise ValueError(\'Shared export adapter requires a read-only store\')\n            return super()._session_lease(session_id, shared=True)\n    return SharedExportStore(root, policy, read_only=True)\n\n\nclass ExportTask:\n    """Pollable direct child; callers retain ownership until finished or cancelled."""\n    def __init__(self, store, session_ids, destination, work_directory, *, python=sys.executable,\n                 timeout_seconds=130, deadline_monotonic=None):\n        import resource\n        if not 1 <= timeout_seconds <= 300:\n            raise ValueError(\'Finite export deadline required\')\n        if deadline_monotonic is not None and deadline_monotonic-time.monotonic() < timeout_seconds+20:\n            raise ValueError(\'Service has insufficient time to close this export\')\n        plan = plan_export(store, session_ids, destination)\n        # Reserve bounded private control receipts independently of the ZIP.\n        store._capacity(plan[\'maximum_bytes\']+65536, Path(plan[\'destination\']).parent)\n        limit = file_limit(plan[\'maximum_bytes\'], resource.getrlimit(resource.RLIMIT_FSIZE)[1])\n        from storage import _safe\n        base = _safe(Path(work_directory).absolute())\n        store._capacity(65536, base.parent)\n        base.mkdir(parents=True, exist_ok=True)\n        self.directory = base/uuid.uuid4().hex; self.directory.mkdir()\n        self.child_directory = self.directory/\'child\'; self.child_directory.mkdir()\n        module = Path(sys.modules[store.__class__.__module__].__file__).resolve(strict=True)\n        source = Path(__file__).resolve(strict=True)\n        self.request = dict(schema=\'just-peachy.owned-export-request.v1\', plan=plan,\n            store_root=str(store.root), storage_policy=asdict(store.policy), storage_module=str(module),\n            storage_sha256=digest(module), helper_sha256=digest(source), file_limit_bytes=limit)\n        put(self.directory/\'REQUEST.json\', self.request)\n        put(self.directory/\'PARENT_MEMORY.json\', dict(owner=identity(os.getpid()), memory=memory(),\n            inherited_file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)),\n            inherited_address_space=list(resource.getrlimit(resource.RLIMIT_AS)), parent_limits_changed=False))\n        env = dict(os.environ, **ALLOCATOR, PYTHONDONTWRITEBYTECODE=\'1\')\n        self.process = subprocess.Popen([str(python), \'-B\', str(source), \'--child\', str(self.directory),\n            \'--request-sha256\', digest(self.directory/\'REQUEST.json\')], env=env,\n            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)\n        self.owner = None; self.finished = False; self.result = None; self.error = None\n        self.started = time.monotonic(); self.deadline = self.started+timeout_seconds\n        self.cancelled = False; self.terminated = None; self.killed = False\n\n    def cancel(self):\n        self.cancelled = True\n        if self.process.poll() is None and self.terminated is None:\n            # Popen owns this unreaped direct child; never signal a receipt-only PID.\n            self.process.terminate(); self.terminated = time.monotonic()\n\n    def poll(self):\n        if self.finished:\n            return self.result\n        try:\n            owner_path = self.child_directory/\'OWNER.json\'\n            if self.owner is None and owner_path.exists():\n                owner = json.loads(owner_path.read_bytes())\n                if (set(owner) != {\'pid\',\'start_ticks\',\'boot_id\'} or owner != identity(self.process.pid) or\n                    Path(\'/proc\', str(self.process.pid), \'cgroup\').read_bytes() != Path(\'/proc/self/cgroup\').read_bytes()):\n                    raise RuntimeError(\'Export child identity or cgroup differs\')\n                self.owner = owner\n                put(self.child_directory/\'PARENT_ACK.json\', dict(owner=owner, same_cgroup=True))\n            if time.monotonic() > self.deadline or (self.owner is None and time.monotonic()-self.started > 8):\n                self.error = self.error or \'Export deadline or owner handshake expired\'; self.cancel()\n            if self.terminated is not None and self.process.poll() is None and time.monotonic()-self.terminated > 5:\n                if not self.killed: self.process.kill(); self.killed = True\n            code = self.process.poll()\n            if code is None:\n                return None\n            self.process.wait(timeout=0)\n            gone = identity(self.process.pid) != self.owner if self.owner else True\n            if not gone:\n                raise RuntimeError(\'Export child remains active after direct reap\')\n            closure = dict(owner=self.owner, child_pid=self.process.pid, exit_code=code,\n                exact_owner_gone=gone, direct_child_reaped=True, cancelled=self.cancelled, forced_reap=self.terminated is not None)\n            closed_path = self.child_directory/\'CLOSED.json\'\n            closed = json.loads(closed_path.read_bytes()) if closed_path.exists() else None\n            if code or self.owner is None or closed is None or closed.get(\'owner\') != self.owner or closed.get(\'status\') != \'EXPORTED\':\n                self.error = self.error or \'Selected export failed: \'+str((closed or {}).get(\'error\') or code)\n            if self.error is None:\n                self.result = json.loads((self.directory/\'EXPORT.json\').read_bytes())\n            else:\n                self.result = dict(status=\'FAILED\', error=self.error)\n            put(self.directory/\'CHILD_CLOSURE.json\', dict(**closure, error=self.error))\n            self.finished = True\n            return self.result\n        except BaseException as exc:\n            self.error = str(exc)[:2048]; self.cancel()\n            if self.process.poll() is not None:\n                self.process.wait(timeout=0)\n                self.finished = True; self.result = dict(status=\'FAILED\', error=self.error)\n                put(self.directory/\'CHILD_CLOSURE.json\', dict(owner=self.owner, child_pid=self.process.pid,\n                    exit_code=self.process.returncode, exact_owner_gone=identity(self.process.pid) != self.owner,\n                    direct_child_reaped=True, forced_reap=self.terminated is not None, error=self.error))\n            return self.result\n\n\ndef child(directory, request_sha):\n    import resource\n    os.sched_setaffinity(0, {2,3})\n    root = Path(directory); childroot = root/\'child\'\n    owner = identity(os.getpid()); put(childroot/\'OWNER.json\', owner)\n    # Durable actual owner precedes all request/package reads and project imports.\n    error = None; status = \'FAILED\'\n    try:\n        put(childroot/\'BEFORE_LIMIT.json\', dict(owner=owner, memory=memory(),\n            address_space=list(resource.getrlimit(resource.RLIMIT_AS))))\n        resource.setrlimit(resource.RLIMIT_AS, (128*MIB,128*MIB))\n        resource.setrlimit(resource.RLIMIT_STACK, (MIB,MIB)); resource.setrlimit(resource.RLIMIT_CORE, (0,0))\n        request_path = root/\'REQUEST.json\'\n        if request_path.stat().st_size > 65536 or digest(request_path) != request_sha:\n            raise ValueError(\'Pinned bounded export request differs\')\n        request = json.loads(request_path.read_bytes())\n        if request.get(\'schema\') != \'just-peachy.owned-export-request.v1\' or digest(__file__) != request[\'helper_sha256\']:\n            raise ValueError(\'Pinned export worker differs\')\n        limit = file_limit(request[\'file_limit_bytes\'], resource.getrlimit(resource.RLIMIT_FSIZE)[1])\n        resource.setrlimit(resource.RLIMIT_FSIZE, (limit,limit))\n        put(childroot/\'ENVELOPE.json\', dict(owner=owner, memory=memory(),\n            address_space=list(resource.getrlimit(resource.RLIMIT_AS)), file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)),\n            allocator_environment={key:os.environ.get(key) for key in ALLOCATOR}, affinity=sorted(os.sched_getaffinity(0))))\n        if any(os.environ.get(key) != value for key,value in ALLOCATOR.items()):\n            raise ValueError(\'Retained allocator environment must precede export exec\')\n        deadline = time.monotonic()+10\n        while not (childroot/\'PARENT_ACK.json\').exists() and time.monotonic() < deadline: time.sleep(.02)\n        ack = json.loads((childroot/\'PARENT_ACK.json\').read_bytes())\n        if ack != dict(owner=owner, same_cgroup=True):\n            raise ValueError(\'Exact export child parent ACK required\')\n        module = Path(request[\'storage_module\'])\n        if module.name != \'storage.py\' or module.resolve(strict=True) != module or digest(module) != request[\'storage_sha256\']:\n            raise ValueError(\'Pinned storage module differs\')\n        sys.path.insert(0, str(module.parent))\n        from storage import SessionStore, StoragePolicy\n        store = read_only_export_store(request[\'store_root\'], StoragePolicy(**request[\'storage_policy\']))\n        try:\n            wanted = request[\'plan\']\n            if plan_export(store, wanted[\'session_ids\'], wanted[\'destination\']) != wanted or limit != wanted[\'maximum_bytes\']:\n                raise ValueError(\'Selected export allocation or metadata changed\')\n            path = store.export(wanted[\'session_ids\'], wanted[\'destination\'])\n            for sid,expected in zip(wanted[\'session_ids\'],wanted[\'session_metadata_sha256\']):\n                if hashlib.sha256(json.dumps(store.read(sid),sort_keys=True).encode()).hexdigest() != expected:\n                    raise ValueError(\'Original selected recording metadata changed\')\n            put(root/\'EXPORT.json\', dict(schema=\'just-peachy.native-selected-export.v1\', status=\'EXPORTED\',\n                session_ids=wanted[\'session_ids\'], source_root=str(store.root), zip_path=str(path),\n                zip_bytes=path.stat().st_size, zip_sha256=digest(path), original_session_preserved=True,\n                source_deleted=False, capture=False, models_loaded=False, maximum_bytes=wanted[\'maximum_bytes\']))\n            status = \'EXPORTED\'\n        finally: store.close()\n    except BaseException as exc:\n        error = dict(type=type(exc).__name__, message=str(exc)[:2048]); raise\n    finally:\n        put(childroot/\'CLOSED.json\', dict(owner=owner, status=status, error=error, memory=memory()))\n\n\nif __name__ == \'__main__\':\n    parser = argparse.ArgumentParser(); parser.add_argument(\'--child\', required=True)\n    parser.add_argument(\'--request-sha256\', required=True); args = parser.parse_args()\n    child(args.child, args.request_sha256)\n'


def export_wrapper(shared,settings):
    """Retain build21's bound checks and conservatively charge both ZIP names."""
    source=shared(settings)
    boundary="    peer=path.with_name(name[:-8]) if name.endswith('.pending') and len(name)>8 else path.with_name(name+'.pending')"
    changed="""    archive=(path.parent==out and (name=='selected-recording.zip' or
      name.startswith('selected-recording.zip.part-') and len(name)==60 and all(c in '0123456789abcdef' for c in name[-32:])))
    if archive:
     if name!='selected-recording.zip':peer=out/'selected-recording.zip'
     else:
      candidates=[p for p in out.iterdir() if p.name.startswith('selected-recording.zip.part-')
       and len(p.name)==60 and all(c in '0123456789abcdef' for c in p.name[-32:])]
      if len(candidates)>1:fail('ambiguous_selected_zip_peer',path,info)
      peer=candidates[0] if candidates else out/'selected-recording.zip.absent-peer'
    else:
     peer=path.with_name(name[:-8]) if name.endswith('.pending') and len(name)>8 else path.with_name(name+'.pending')"""
    if source.count(boundary)!=1:raise ValueError('Exact build21 publication-peer boundary required')
    source=source.replace(boundary,changed)
    compile(source,'<full-selected-export-wrapper>','exec')
    return source


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
    if (re.fullmatch(r'classic-ui-check-\d{2}',source_root.name) is None or
        old_job['unit']!='jp-v29-'+source_root.name+'.service' or
        old_job['package_manifest_sha256']!=p['package_manifest_sha256'] or
        Path(p['recordings_root'])!=Path('/home/peachyprototype/JustPeachy/data/runtime-v29/recordings')):
        raise ValueError('Exact closed GUI job recording root/package required')
    proof=json.loads((source_root/'NATIVE_CHECK_V2.json').read_bytes())
    if (proof.get('status')!='PASS' or proof.get('session_id')!=p['session_id'] or
        proof.get('processed_save_passed') is not True or proof.get('workers_closed') is not True or
        proof.get('package_manifest_sha256')!=p['package_manifest_sha256'] or proof.get('boot_id')!=boot):
        raise ValueError('Exact actually kept rich session and independently finalized source required')
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
