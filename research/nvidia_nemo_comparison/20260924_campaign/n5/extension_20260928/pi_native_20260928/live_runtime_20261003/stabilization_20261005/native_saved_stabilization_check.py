"""Bounded actual kept-recording replay. See README_NATIVE_SAVED_STABILIZATION_CHECK.md.

Injected test instrumentation only; this file is not installed into a runtime.
The existing package's owner envelope, worker and disposition API remain in use.
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

CAMPAIGN = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
RUNTIME_DATA = Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
MIB = 1024**2


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate classic-check field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def put(path, value):
    raw = encoded(value)
    if len(raw) > 262144:
        raise ValueError('Classic-check receipt bound')
    with Path(path).open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short classic-check receipt')
        stream.flush(); os.fsync(stream.fileno())
    if Path(path).read_bytes() != raw:
        raise OSError('Classic-check receipt readback differs')
    descriptor = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def members(root):
    pending, result = [root], []
    while pending:
        widget = pending.pop(0)
        result.append(widget)
        if len(result) > 512:
            raise ValueError('Actual classic widget inventory exceeds512')
        pending.extend(widget.winfo_children())
    return result


def named(root, label, classes=('Button', 'TButton')):
    found = [widget for widget in members(root)
        if widget.winfo_class() in classes and str(widget.cget('text')) == label]
    if len(found) != 1:
        raise ValueError('Exactly one actual widget required: '+label)
    return found[0]


class ClassicDriver:
    """After-hooks invoke actual retained widgets; no fake source/controller."""
    def __init__(self, settings, scope):
        self.settings, self.scope = settings, scope
        self.output = Path(settings['output'])
        self.actions, self.failure = [], None
        self.manager = self.ui = self.root = None
        self.stage = 'chooser'
        self.deadline = time.monotonic()+settings['driver_seconds']
        self.geometry_count = 0
        self.started = self.stopped = self.kept = self.exited = False
        self.session_id, self.capture_samples = None, 0
        self.worker_closure = None
        self.source_lease = None
        self.source_files = None

    def record(self, action, **values):
        row = dict(action=action, monotonic_sec=time.monotonic(), programmatic=True,
            physical_touch=False, **values)
        if len(self.actions) >= 128 or len(encoded(row)) > 65536:
            raise ValueError('Classic actual-action receipt bound')
        self.actions.append(row)
        put(self.output/('ACTION_%03d.json' % len(self.actions)), row)

    def invoke(self, widget, action):
        if str(widget.cget('state')) == 'disabled':
            raise RuntimeError('Actual UI control is disabled: '+action)
        self.record(action, widget=str(widget), widget_class=widget.winfo_class(),
            label=str(widget.cget('text')))
        widget.invoke()

    def geometry(self, root):
        observed = dict(width=root.winfo_width(), height=root.winfo_height(),
            x=root.winfo_rootx(), y=root.winfo_rooty(),
            viewable=bool(root.winfo_viewable()), fullscreen=bool(root.attributes('-fullscreen')))
        exact = observed == dict(width=480, height=800, x=0, y=0, viewable=True, fullscreen=True)
        self.geometry_count = self.geometry_count+1 if exact else 0
        if self.geometry_count == 10:
            self.record('portrait-geometry', observations=10, interval_ms=100, actual=observed)
        return self.geometry_count >= 10

    def chooser_tick(self, root):
        try:
            if time.monotonic() >= self.deadline:
                raise TimeoutError('Actual chooser did not map within the finite driver deadline')
            if not self.geometry(root):
                root.after(100, lambda: self.chooser_tick(root)); return
            from operator_profiles import catalog, selection_for
            rows = catalog()
            radios = [widget for widget in members(root) if widget.winfo_class() == 'Radiobutton']
            backends = [widget for widget in radios if str(widget.cget('value')) not in ('live', 'saved')]
            actual = {str(widget.cget('value')): str(widget.cget('text')) for widget in backends}
            if (len(rows) != 6 or len(backends) != 6 or
                    actual != {row['id']: row['label'] for row in rows}):
                raise ValueError('Actual six pinned backend radio controls required')
            matches = [widget for widget in backends if str(widget.cget('text')) == self.settings['chooser_label']]
            if len(matches) != 1:
                raise ValueError('Pinned backend label missing or ambiguous')
            selected = matches[0]
            identifier = str(selected.cget('value'))
            if selection_for(identifier, 'saved').validate() != self.settings['selection']:
                raise ValueError('Actual operator radio value differs from pinned selection')
            self.invoke(selected, 'chooser-backend-radio')
            source = named(root, 'Saved WAV', classes=('Radiobutton',))
            if str(source.cget('value')) != 'saved':
                raise ValueError('Actual saved source radio value required')
            self.invoke(source, 'chooser-saved-source-radio')
            if (str(root.getvar(str(selected.cget('variable')))) != identifier or
                    str(root.getvar(str(source.cget('variable')))) != 'saved'):
                raise ValueError('Actual selected backend/source variables did not change')
            self.record('choose-backend', label=self.settings['chooser_label'], operator_id=identifier,
                visible_backends=actual, input_source='saved', manager_idle=True, capture_started=False)
            self.invoke(named(root, 'Open Application'), 'chooser-open-application')
        except BaseException as exc:
            self.failure = repr(exc)
            self.record('failure', error=self.failure)
            root.quit()

    def attach(self, ui):
        self.ui, self.root, self.manager = ui, ui.root, ui.controller.manager
        if self.manager.process is not None or ui.controller.selection.validate() != self.settings['selection']:
            raise ValueError('Opening the actual pinned rich application must be idle')
        self.stage, self.geometry_count = 'portrait', 0
        self.record('retained-portrait-created', class_name=type(ui).__name__,
            retained_base=type(ui).__mro__[2].__name__, page=ui.page,
            source='saved', capture_started=False)
        self.root.report_callback_exception = lambda kind, value, traceback: self.abort(str(kind)+': '+str(value))
        self.root.after(100, self.tick)

    def source_snapshot(self):
        """Pin only the explicitly selected kept source; never the whole history."""
        folder = self.manager.store._session_dir(self.settings['saved_session_id'])
        files, total, visited = [], 0, 0
        pending = [folder]
        paths = []
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 768 or entry.is_symlink():
                        raise ValueError('Bounded regular saved source membership required')
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    else:
                        paths.append(Path(entry.path))
        for path in sorted(paths):
            if path.is_symlink():
                raise ValueError('Saved source must not contain symlinks')
            if path.is_dir():
                continue
            if not path.is_file() or len(files) >= 512:
                raise ValueError('Bounded regular saved source tree required')
            before = path.stat()
            if before.st_size > 32*MIB:
                raise ValueError('Saved source individual file cap32MiB')
            digest = sha(path)
            after = path.stat()
            identity = [before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns]
            if identity != [after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns]:
                raise ValueError('Saved source changed during readback')
            total += before.st_size
            if total > 96*MIB:
                raise ValueError('Selected short saved source exceeds finite readback bound')
            files.append(dict(path=path.relative_to(folder).as_posix(),bytes=before.st_size,
                sha256=digest,identity=identity))
        if not files:
            raise ValueError('Complete kept source required')
        return dict(files=files,bytes=total,sha256=hashlib.sha256(encoded(files)).hexdigest())

    def capture_home(self):
        grim = shutil.which('grim')
        if not grim:
            self.record('private-image-unavailable', reason='Existing grim executable is absent')
            return
        path = self.output/'PORTRAIT_HOME.png'
        result = subprocess.run([grim, '-t', 'png', str(path)], capture_output=True, timeout=8)
        if len(result.stdout)+len(result.stderr) > 16384:
            raise ValueError('Bounded compositor image diagnostics required')
        if result.returncode:
            self.record('private-image-unavailable', returncode=result.returncode,
                stderr=result.stderr.decode(errors='replace')[:4096]); return
        if path.is_symlink() or not 24 <= path.stat().st_size <= 2*MIB:
            raise ValueError('Bounded private actual compositor image required')
        import struct
        with path.open('rb') as stream:
            header = stream.read(24)
        if header[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('!II', header[16:24]) != (480, 800):
            raise ValueError('Actual portrait image must be480x800')
        self.record('private-portrait-image', path=str(path), bytes=path.stat().st_size, sha256=sha(path),
            media_private=True, display_transform=270)

    def abort(self, error):
        if self.failure is None:
            self.failure = str(error)[:4096]
            self.record('failure', error=self.failure)
        self.stage = 'aborting'
        if self.manager is not None:
            self.manager.stop()
        if self.root is not None:
            self.root.after(100, self.tick)

    def processing_evidence(self, closure):
        """Count committed text and actual engine calls; preserve quiet/no-event gaps."""
        outer = closure.get('result') or {}
        result = outer.get('result') or {}
        costs = result.get('costs') or {}
        calls = {}
        if type(costs) is not dict or len(costs) > 64:
            raise ValueError('Bounded actual engine component costs required')
        for key, value in costs.items():
            if type(key) is not str or type(value) is not dict or type(value.get('calls')) is not int or value['calls'] < 0:
                raise ValueError('Actual component call counts required')
            calls[key] = value['calls']
        with self.manager.store._db() as db:
            counts = db.execute('SELECT COUNT(*), COALESCE(SUM(CASE WHEN LENGTH(TRIM(text))>0 THEN 1 ELSE 0 END),0) '
                'FROM captions WHERE session_id=?', (self.session_id,)).fetchone()
        snapshot = self.ui.controller.snapshot()
        rows = snapshot.get('rows') or []
        if type(rows) is not list or len(rows) > 256:
            raise ValueError('Bounded actual current caption view required')
        current_text = sum(bool(str(row.get('text') or row.get('raw_asr_text') or row.get('display_text') or '').strip())
            for row in rows)
        self.processing = dict(session_id=self.session_id, selection=self.settings['selection'],
            application_mode=self.settings['application_mode'], indexed_caption_rows=int(counts[0]),
            indexed_nonempty_text_rows=int(counts[1]), current_view_rows=len(rows),
            current_view_nonempty_text_rows=current_text, current_caption_text_exists=current_text > 0,
            component_calls_by_actual_key=calls, engine_result_status=result.get('status'),
            engine_result_selection=result.get('selection'), transcript_content_retained_private=True,
            no_events_do_not_qualify_embedding=True, quiet_function_pass_is_not_speech_success=True,
            quality_evaluated=False, sustained_realtime_qualified=False)
        self.record('actual-processing-evidence', **self.processing)

    def tick(self):
        try:
            if self.stage != 'aborting' and time.monotonic() >= self.deadline:
                raise TimeoutError('Finite saved workflow deadline; normal Stop requested')
            closure = self.manager.poll()
            if self.stage == 'aborting':
                if self.manager.process is None:
                    self.ui.close(); return
            elif self.stage == 'portrait':
                if not self.geometry(self.root):
                    self.root.after(100, self.tick); return
                self.capture_home()
                source_id = self.settings['saved_session_id']
                row = self.manager.store.read(source_id)
                source_path = self.manager.store._session_dir(source_id)/'session.json'
                if (row['status'] != 'kept' or row['spec']['sample_rate'] != 16000 or
                        sha(source_path) != self.settings['saved_metadata_sha256'] or
                        type(row['processed_samples']) is not int or
                        not 0 < row['processed_samples'] <= self.settings['policy']['maximum_session_seconds']*16000):
                    raise ValueError('Exact complete kept short source must fit finite replay policy')
                self.source_frames = row['processed_samples']
                self.source_metadata = row
                self.canonical_metadata_sha256 = hashlib.sha256(encoded(row)).hexdigest()
                self.source_lease = self.manager.store._session_lease(source_id, shared=True)
                self.source_files = self.source_snapshot()
                put(self.output/'SAVED_SOURCE_MANIFEST.json', self.source_files)
                self.record('selected-kept-source', source_session_id=source_id,
                    raw_metadata_sha256=self.settings['saved_metadata_sha256'],
                    canonical_metadata_sha256=self.canonical_metadata_sha256,
                    processed_samples=self.source_frames, complete_tree_sha256=self.source_files['sha256'],
                    file_count=len(self.source_files['files']), bytes=self.source_files['bytes'],
                    physical_microphone=False, current_motion_used=False)
                self.invoke(self.ui.actions['mode'], 'mode-tab')
                if self.ui.page != 'modes':
                    raise RuntimeError('Retained Mode page required')
                mode = self.settings['application_mode']
                self.invoke(self.ui.actions['mode_'+mode], 'actual-recorded-application-mode')
                if mode in ('assigned_direction','assigned_hybrid'):
                    if self.ui.page != 'seats':
                        raise RuntimeError('Retained assigned-seat editor required')
                    layout = self.settings['seating']
                    self.ui._seat_draft = json.loads(json.dumps(layout['rows'], allow_nan=False))
                    self.ui._seat_strength = layout['strength']
                    self.ui._seat_ack = layout['acknowledged']
                    self.ui._draw_seat_page()
                    self.record('programmatic-recorded-seat-draft', rows_sha256=hashlib.sha256(encoded(layout['rows'])).hexdigest(),
                        participants=len(layout['rows']), physical_touch=False, person_created=False,
                        reference='selected recording original array; not current sensor',
                        direction_names_are_assumptions=True)
                    self.invoke(self.ui.actions['seat_apply'], 'actual-recorded-seat-apply')
                if self.ui.controller.mode != mode or self.ui.controller.intent['mode'] != mode:
                    raise RuntimeError('Actual retained replay Mode must be applied')
                self.invoke(self.ui.actions['settings'], 'settings-tab')
                if self.ui.page != 'settings':
                    raise RuntimeError('Retained Settings page required')
                self.invoke(self.ui.actions['sessions'], 'actual-recording-history')
                if self.ui.page != 'sessions':
                    raise RuntimeError('Retained recording History required')
                page = self.ui.controller.history_page
                matches = [value for value in page['items'] if value['session_id'] == source_id]
                if len(matches) != 1 or matches[0] != row:
                    raise ValueError('Explicit pinned kept UUID must be in current bounded History page')
                # Exactly reproduce the retained page's label; a UUID prefix
                # alone cannot select one of two colliding history rows.
                title = row.get('spec',{}).get('title') or time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(row['created']))
                label = '%s\n%s · %.1fs · %s' % (title,row['status'],row['duration_seconds'],source_id[:8])
                self.invoke(named(self.root,label), 'actual-selected-history-row')
                if self.ui.page != 'session_detail':
                    raise RuntimeError('Actual selected History detail page required')
                self.invoke(named(self.root,'Replay with selected backend'), 'actual-kept-recording-replay')
                if self.manager.process is None:
                    raise RuntimeError('Actual Replay did not create its worker: '+str(self.ui._notice))
                request = self.manager.request
                if (request['selection'] != self.settings['selection'] or request['policy'] != self.settings['policy'] or
                        request.get('saved_session_id') != source_id or request.get('saved_path') is not None or
                        request['application']['mode'] != mode or request.get('saved_store_root') != str(self.manager.store.root)):
                    raise ValueError('Actual replay request differs from pinned source/backend/Mode')
                self.started = True; self.stage = 'replaying'
                self.record('actual-replay-worker-started',launch_root=str(self.manager.run_dir),
                    request_sha256=sha(self.manager.run_dir/'REQUEST.json'),policy=request['policy'],
                    physical_microphone=False,current_motion_used=False)
            elif self.stage == 'replaying':
                identifier = self.manager.active_session_id()
                if identifier:
                    if identifier == self.settings['saved_session_id']:
                        raise ValueError('Replay must create a fresh output recording')
                    self.session_id = identifier
                    self.capture_samples = self.manager.store.read(identifier)['processed_samples']
                    if self.capture_samples > self.source_frames:
                        raise ValueError('Saved replay exceeded its authoritative source timeline')
                if self.manager.process is None and closure is not None:
                    from native_gui_driver import require_closed
                    identifier = require_closed(closure)
                    if identifier != self.session_id:
                        raise RuntimeError('Closed replay worker must match only its new output')
                    row = self.manager.store.read(identifier)
                    if row['status'] != 'stopped' or row['processed_samples'] != self.source_frames:
                        raise RuntimeError('Natural saved EOF/drain must commit the entire source timeline')
                    self.stopped = True; self.worker_closure = closure
                    self.record('worker-source-closed',session_id=identifier,closure=closure,
                        actual_processed_samples=row['processed_samples'],natural_saved_eof=True,
                        injected_stop_calls=0,physical_microphone=False)
                    self.processing_evidence(closure)
                    spatial = ((closure.get('result') or {}).get('result') or {}).get('saved_spatial')
                    needed = self.settings['application_mode'] != 'enrolled_names'
                    if needed:
                        if (type(spatial) is not dict or spatial.get('metadata_sha256') != self.canonical_metadata_sha256 or
                                spatial.get('session_id') != self.settings['saved_session_id'] or
                                spatial.get('processed_samples') != self.source_frames or spatial.get('current_motion_used') is not False or
                                spatial.get('source_verified_after_drain') is not True or spatial.get('source_shared_lease_closed') is not True or
                                type(spatial.get('replayed_anchors')) is not int or spatial['replayed_anchors'] <= 0 or
                                type(spatial.get('replayed_beams')) is not int or spatial['replayed_beams'] <= 0):
                            raise RuntimeError('Saved spatial Mode must prove original recorded beam/pose/sample binding and closure')
                    elif spatial is not None:
                        raise RuntimeError('Named replay must not silently enable spatial inference')
                    self.record('saved-spatial-evidence',required=needed,recorded_provider=spatial,
                        current_motion_used=False,dsp_acoustic_synchronization_claimed=False,
                        actual_direction_accuracy_qualified=False)
                    if self.manager.store.read(self.settings['saved_session_id']) != self.source_metadata or self.source_snapshot() != self.source_files:
                        raise ValueError('Original kept source changed during backend replay')
                    self.source_lease.close(); self.source_lease = None
                    self.record('original-kept-source-unchanged',complete_tree_sha256=self.source_files['sha256'],
                        source_session_id=self.settings['saved_session_id'],shared_source_lease_closed=True)
                    self.stage = 'post-stop'; self.post_at = time.monotonic()+.75
            elif self.stage == 'post-stop' and time.monotonic() >= self.post_at:
                if self.ui.page != 'save_session' or 'save_session' not in self.ui.actions:
                    raise RuntimeError('Actual replay EOF Save session prompt required')
                if self.settings.get('discard_session'):
                    self.invoke(self.ui.actions['discard_session'],'post-replay-discard-dialog')
                    self.invoke(self.ui.actions['confirm'],'actual-new-replay-discard')
                    if (self.manager.store.root/'sessions'/self.session_id).exists():
                        raise RuntimeError('Discard must remove only its new replay output')
                    self.kept=True
                else:
                    self.invoke(self.ui.actions['save_session'],'post-replay-save-session')
                    row=self.manager.store.read(self.session_id)
                    if row['status']!='kept' or row['include_raw']:
                        raise RuntimeError('Saved replay disposition must preserve processed input only')
                    files=[]
                    segments=self.manager.store._segments(self.session_id,'processed')
                    for segment in segments:
                        for key in ('data_name','replay_name'):
                            if segment.get(key):
                                path=self.manager.store._audio_path(self.session_id,segment[key])
                                if len(files)>=128 or path.stat().st_size>32*MIB:
                                    raise ValueError('Bounded new replay audio readback required')
                                files.append(dict(name=segment[key],bytes=path.stat().st_size,sha256=sha(path)))
                    if not files or sum(segment['samples'] for segment in self.manager.store._segments(self.session_id,'processed'))!=self.source_frames:
                        raise RuntimeError('Complete new processed replay timeline required')
                    self.kept=True
                    self.record('processed-audio-readback',session_id=self.session_id,processed_samples=row['processed_samples'],
                        include_raw=False,files=files,audio_private=True)
                self.invoke(self.ui.actions['settings'],'final-settings')
                self.invoke(named(self.root,'Exit to desktop'),'actual-exit-desktop')
                if not self.ui.controller.closing:
                    raise RuntimeError('Actual Exit must close after replay worker/drain')
                self.exited=True;self.stage='exiting'
            if self.stage!='exiting' and self.root.winfo_exists():
                self.root.after(100,self.tick)
        except BaseException as exc:
            self.abort(repr(exc))

def inside(settings):
    """Run exact native_scope.inside, with a narrowly scoped actual-Tk driver."""
    output, package = Path(settings['output']), Path(settings['package'])
    scope = load(package/'native_scope.py', 'classic_check_native_scope')
    identity = scope.identity()
    if strict((output/'OWNER.json').read_bytes()) != identity:
        raise ValueError('Wrapper early identity required before any project imports')
    scope.verified_inventory(package, settings['package_manifest_sha256'])
    ownership = strict((output/'UNIT_OWNERSHIP.json').read_bytes())
    actual = scope.properties(settings['unit'])
    if (ownership['owner'] != identity or actual['MainPID'] != str(identity['pid'])
        or actual['InvocationID'] != ownership['invocation_id']):
        raise ValueError('Actual owned-unit ACK required before GUI imports')
    sys.path.insert(0, str(package))
    import tkinter as tk
    from tkinter import messagebox
    import classic_frontend
    import launcher
    import xvf_readiness
    from profiles import SessionPolicy
    driver = ClassicDriver(settings, scope)
    tk_original, type_original = tk.Tk, classic_frontend.frontend_type
    policy_original, consent_original = launcher.gui_session_policy, messagebox.askokcancel
    import application_controller
    application_type_original = application_controller.controller_type
    recovery_original = xvf_readiness.recover_previous_source
    bootstrap_original = scope.bootstrap
    def inherited_bootstrap(directory, *, inside_service=False):
        # An independent production service can select its finite hard FSIZE.
        # This test inherits an already stricter wrapper hard cap. Honour it;
        # Linux correctly refuses increasing an inherited unprivileged hard cap.
        import resource
        setter = resource.setrlimit
        prior = resource.getrlimit(resource.RLIMIT_FSIZE)
        def stricter(kind, limits):
            if kind == resource.RLIMIT_FSIZE and prior[1] != resource.RLIM_INFINITY:
                limits = (min(limits[0], prior[1]), min(limits[1], prior[1]))
            return setter(kind, limits)
        resource.setrlimit = stricter
        try:
            owner = bootstrap_original(directory, inside_service=inside_service)
        finally:
            resource.setrlimit = setter
        driver.record('stricter-inherited-file-cap', original_wrapper_limit=list(prior),
            actual=list(resource.getrlimit(resource.RLIMIT_FSIZE)), native_scope_owner=owner,
            weaker_guard=False, test_only=True)
        return owner
    scope.bootstrap = inherited_bootstrap
    import classic_check_lease_handoff as handoff
    import fcntl
    if (handoff.owner != identity or handoff.path != settings['research_lock'] or len(handoff.leases) != 1
        or handoff.leases[0] is not handoff.stream):
        raise ValueError('Exact original wrapper research lease required for bounded handoff')
    def readiness(manager):
        # Only this already authorized, idle Start may transfer the retained
        # same-inode research lease to the actual recovery helper. New worker
        # construction remains after successful reacquisition.
        if manager.process is not None or driver.stage != 'portrait' or manager.closed:
            raise ValueError('Readiness lease handoff is limited to this one pre-worker Start')
        path = Path(handoff.path)
        before = os.fstat(handoff.stream.fileno())
        current = path.stat()
        if path.is_symlink() or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('Retained research lease identity changed before handoff')
        driver.record('research-lease-handoff-begin', owner=identity, path=str(path),
            device=before.st_dev, inode=before.st_ino, new_worker_started=False)
        fcntl.flock(handoff.stream, fcntl.LOCK_UN)
        try:
            return recovery_original(manager)
        finally:
            after = path.stat()
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise RuntimeError('Research lease inode changed during recovery; new worker refused')
            fcntl.flock(handoff.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            driver.record('research-lease-handoff-closed', owner=identity, path=str(path),
                device=after.st_dev, inode=after.st_ino, reacquired=True, new_worker_started=False)
    xvf_readiness.recover_previous_source = readiness
    policy = SessionPolicy(**settings['policy']); policy.validate()
    launcher.gui_session_policy = lambda binding, selection: policy
    def qualification_type(base):
        restored = application_type_original(base)
        class FiniteQualification(restored):
            def _policy(self): return policy
        return FiniteQualification
    application_controller.controller_type = qualification_type
    driver.record('finite-test-policy', production_manual_stop_qualified=False, policy=policy.validate())
    def consent(title, message, **values):
        if title != 'Experimental backend' or not settings['selection']['allow_experimental']:
            raise ValueError('Unexpected native check dialog')
        driver.record('experimental-opt-in', title=title, answer=True)
        return True
    messagebox.askokcancel = consent
    class ActualTk(tk_original):
        def mainloop(self, *args, **values):
            if self.title() == 'Just Peachy · choose backend':
                self.after(100, lambda: driver.chooser_tick(self))
            return super().mainloop(*args, **values)
    def observed_type(prototype):
        retained = type_original(prototype)
        class ObservedPortrait(retained):
            def __init__(self, *args, **values):
                super().__init__(*args, **values)
                driver.attach(self)
        return ObservedPortrait
    tk.Tk, classic_frontend.frontend_type = ActualTk, observed_type
    from types import SimpleNamespace
    args = SimpleNamespace(inside=str(output), binding=str(package/'BINDING.json'),
        manifest_sha256=settings['package_manifest_sha256'], unit=settings['unit'],
        data_root=settings['data_root'], entrypoint='launcher.py', developer_soak=False,
        maximum_session_seconds=policy.maximum_session_seconds,
        max_drain_seconds=policy.max_drain_seconds, max_backlog_seconds=policy.max_backlog_seconds)
    code, failure = 1, None
    try:
        code = scope.inside(args, [])
        if driver.failure:
            raise RuntimeError(driver.failure)
        if not (driver.started and driver.stopped and driver.kept and driver.exited and driver.manager.closed
            and driver.manager.process is None and driver.ui.controller.closed and driver.worker_closure):
            raise RuntimeError('Every actual classic workflow stage must complete before proof')
        put(output/'COMPLETE.json', dict(status='FUNCTION_PASS_AWAITING_UNIT_CLOSURE',
            package_manifest_sha256=settings['package_manifest_sha256'], boot_id=identity['boot_id'],
            actual_portrait_ui=True, capture_function_passed=False, saved_replay_function_passed=True,
            physical_microphone=False, current_motion_used=False, workers_closed=True,
            session_id=driver.session_id, worker_closure=driver.worker_closure,
            source_session_id=settings['saved_session_id'], source_metadata_sha256=settings['saved_metadata_sha256'],
            original_source_tree_sha256=driver.source_files['sha256'], original_source_unchanged=True,
            source_shared_lease_closed=driver.source_lease is None, application_mode=settings['application_mode'],
            processed_save_passed=not settings.get('discard_session',False),
            complete_session_discard_passed=settings.get('discard_session',False),
            enrollment_models_prepared=getattr(driver,'gallery_prepared',False),
            actual_processing_evidence=driver.processing,
            settings_exit_passed=True, policy=settings['policy'],
            short_functional_qualification=not settings.get('manual_stop_test',False), ordinary_300s_qualified=False,
            manual_stop_beyond_300s_test=settings.get('manual_stop_test',False),
            production_gui_lifetime_qualified=False,
            sustained_realtime_qualified=False, physical_touch=False, screenshots_private=True,
            actions=len(driver.actions), owner=identity))
        return code
    except BaseException as exc:
        failure = repr(exc)
        raise
    finally:
        if driver.source_lease is not None:
            driver.source_lease.close()
            driver.source_lease = None
        tk.Tk, classic_frontend.frontend_type = tk_original, type_original
        launcher.gui_session_policy, messagebox.askokcancel = policy_original, consent_original
        application_controller.controller_type = application_type_original
        xvf_readiness.recover_previous_source = recovery_original
        scope.bootstrap = bootstrap_original
        put(output/'DRIVER_EXIT.json', dict(owner=identity, failure=failure, code=code,
            worker_still_owned=driver.manager is not None and driver.manager.process is not None,
            physical_closure_claimed=False))


def launch(payload, baseline):
    """Return a normal asynchronous JOB; the existing collector closes it."""
    p = dict(payload)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != p['boot_id'] or not time.time() < p['expires_unix'] <= time.time()+600:
        raise ValueError('Fresh bounded current-boot admission required')
    if baseline.get('current_project_processes') or baseline.get('active_recorded_owners') or baseline.get('live_manager_owners'):
        raise ValueError('Full prior-owner inspection must be clear')
    package = Path(p['package'])
    if package.parent != CAMPAIGN or not re.fullmatch(r'field-runtime-v29-build-\d{2}', package.name):
        raise ValueError('Explicit immutable runtime build required')
    if not re.fullmatch(r'classic-ui-check-\d{2}', p['label']):
        raise ValueError('Fresh named classic workflow required')
    helper = base64.b64decode(p['helper_source_b64'], validate=True)
    if not 0 < len(helper) <= 65536 or hashlib.sha256(helper).hexdigest() != p['helper_source_sha256']:
        raise ValueError('Exact backed test helper source required')
    compile(helper, '<backed-classic-check>', 'exec')
    # Verify the manifest before loading the retained guard/wrapper implementation.
    manifest_raw = (package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(manifest_raw) > 262144 or hashlib.sha256(manifest_raw).hexdigest() != p['package_manifest_sha256']:
        raise ValueError('Pinned package manifest required')
    manifest = strict(manifest_raw)
    row = next(value for value in manifest['files'] if value['path'] == 'launch_raw_qualification_action.py')
    raw_path = package/'launch_raw_qualification_action.py'
    if raw_path.is_symlink() or raw_path.stat().st_size != row['bytes'] or sha(raw_path) != row['sha256']:
        raise ValueError('Pinned existing qualification wrapper required')
    guard = load(raw_path, 'classic_check_existing_wrapper')
    guard.inventory(package, p['package_manifest_sha256'])
    binding = strict((package/'BINDING.json').read_bytes())
    profiles, storage = guard.load_pure(package, 'profiles'), guard.load_pure(package, 'storage')
    selection = profiles.RuntimeSelection(**p['selection']).validate()
    long_test = p.get('manual_stop_test', False)
    if type(long_test) is not bool:
        raise ValueError('Explicit manual-stop qualification flag required')
    if long_test:
        raise ValueError('This focused stabilization check accepts only the short finite speech window')
    for flag in ('prepare_gallery', 'discard_session'):
        if type(p.get(flag, False)) is not bool:
            raise ValueError('Typed changed gallery/disposition qualification flag required')
    if p.get('prepare_gallery'):
        raise ValueError('Saved replay does not perform separate enrollment preparation')
    policy = profiles.SessionPolicy(maximum_session_seconds=30)
    if (selection['input_source'] != 'saved' or selection['embedding'] not in ('redimnet','titanet') or
            selection['provisional_correction'] or selection['optional_d1_refiner']):
        raise ValueError('One named ordinary single-worker saved backend required')
    saved_id = p.get('saved_session_id')
    source_pin = p.get('saved_metadata_sha256')
    if (type(saved_id) is not str or not re.fullmatch(r'[0-9a-f]{32}', saved_id) or
            type(source_pin) is not str or not re.fullmatch(r'[0-9a-f]{64}', source_pin)):
        raise ValueError('Explicit canonical kept UUID and session.json byte SHA required')
    mode = p.get('application_mode', 'enrolled_names')
    if mode not in ('enrolled_names','spatial_assisted','strongly_spatial_assisted','assigned_direction','assigned_hybrid'):
        raise ValueError('Explicit supported named/recorded-spatial application Mode required')
    seating = p.get('seating')
    if mode in ('assigned_direction','assigned_hybrid'):
        if (type(seating) is not dict or set(seating) != {'rows','strength','acknowledged'} or
                type(seating['rows']) is not list or not 1 <= len(seating['rows']) <= 256 or
                seating['strength'] not in ('soft','strong') or type(seating['acknowledged']) is not bool or
                mode == 'assigned_direction' and seating['strength'] != 'soft'):
            raise ValueError('Explicit bounded actual-person recorded-seat draft required')
    elif seating is not None:
        raise ValueError('Seat draft belongs only to assigned-seat Modes')
    data = Path(p['data_root'])
    if data != RUNTIME_DATA or data.is_symlink() or data.resolve(strict=True) != data:
        raise ValueError('Actual canonical owned runtime data root required')
    source_path = data/'recordings'/'sessions'/saved_id/'session.json'
    for parent in source_path.parents:
        if parent == data:
            break
        if parent.is_symlink():
            raise ValueError('Actual canonical saved source path required')
    if source_path.is_symlink() or not source_path.is_file() or source_path.stat().st_size > 65536 or sha(source_path) != source_pin:
        raise ValueError('Pinned existing kept session.json bytes required')
    source_meta = strict(source_path.read_bytes())
    source_frames = source_meta.get('processed_samples')
    if (source_meta.get('status') != 'kept' or source_meta.get('session_id') != saved_id or
            source_meta.get('spec',{}).get('sample_rate') != 16000 or
            type(source_frames) is not int or not 0 < source_frames <= 30*16000):
        raise ValueError('Complete kept <=30second source must fit finite saved replay policy')
    unit = 'jp-v29-'+p['label']+'.service'
    old = subprocess.run(['systemctl', '--user', 'show', unit, '--property=LoadState'],
        capture_output=True, text=True, timeout=5)
    if old.stdout.strip() != 'LoadState=not-found':
        raise ValueError('Fresh unused test unit required')
    shown = subprocess.run(['systemctl', '--user', 'show-environment'],
        capture_output=True, text=True, timeout=5, check=True)
    if len(shown.stdout) > 65536: raise ValueError('Bounded display environment required')
    environment = dict(line.split('=', 1) for line in shown.stdout.splitlines() if '=' in line)
    display = {key:environment[key] for key in ('DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS') if key in environment}
    if any(not display.get(key) for key in ('DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR')) or any(len(value)>512 or '\n' in value or '\r' in value for value in display.values()):
        raise ValueError('Exact current desktop environment required')
    seconds = policy.maximum_session_seconds
    spec = dict(sample_rate=16000, mode='processed', duration_seconds=seconds,
        metadata_reserve_bytes=16*MIB+seconds*256*1024)
    # Replaying the authoritative processed float timeline does not recapture
    # the original raw microphones or open any physical source route.
    measured_plan = storage.StoragePolicy(**binding.get('storage_policy', {})).estimate_bytes(spec)+32*MIB
    full = 96*MIB
    if (type(p.get('maximum_output_bytes')) is not int or p['maximum_output_bytes'] != full
        or type(p.get('independent_pc_copy_bytes')) is not int or p['independent_pc_copy_bytes'] != full
        or measured_plan > full):
        raise ValueError('Exact independent96MiB native and PC reservations must cover the complete measured plan')
    if shutil.disk_usage(CAMPAIGN).free < 5*1024**3+full:
        raise OSError('Independent complete test reserve must preserve5GiB')
    parent = CAMPAIGN/'live-runtime-tests-20261003'
    if parent.is_symlink(): raise ValueError('Real native trial parent required')
    parent.mkdir(exist_ok=True)
    output = parent/p['label']; output.mkdir()
    budget = dict(maximum_output_bytes=full, runtime_seconds=600 if long_test else 540, stop_seconds=30,
        file_limit_bytes=full, maximum_files=512)
    settings = dict(output=str(output), package=str(package), data_root=str(data), unit=unit, boot_id=boot,
        expires_unix=p['expires_unix'], package_manifest_sha256=p['package_manifest_sha256'],
        scope_sha256=sha(package/'native_scope.py'), research_lock=str(CAMPAIGN/'B05_PREVIEW_DISPATCH.lock'),
        budget=budget, kind='gui', template=None, template_sha256=None,
        chooser_label=p['chooser_label'], selection=selection, policy=policy.validate(),
        driver_seconds=180, stop_after_seconds=source_frames/16000, manual_stop_test=long_test,
        saved_session_id=saved_id, saved_metadata_sha256=source_pin, application_mode=mode, seating=seating,
        prepare_gallery=p.get('prepare_gallery',False), discard_session=p.get('discard_session',False))
    driver_source = helper+b'\nif __name__ == "__main__":\n    settings = strict(Path(sys.argv[1]).read_bytes())\n    raise SystemExit(inside(settings))\n'
    driver_path = output/'classic_driver.py'
    with driver_path.open('xb') as stream:
        if stream.write(driver_source) != len(driver_source): raise OSError('Short native helper write')
        stream.flush(); os.fsync(stream.fileno())
    settings['argv'] = [str(driver_path), str(output/'DRIVER_SETTINGS.json')]
    put(output/'DRIVER_SETTINGS.json', settings)
    wrapper = guard.wrapper_source(settings)
    anchor = ' watcher.start();sys.argv=argv\n'
    if wrapper.count(anchor) != 1:
        raise ValueError('Exact original guarded runpy boundary required')
    export = (" import types\n handoff=types.ModuleType('classic_check_lease_handoff')\n"
        " handoff.stream=lock;handoff.leases=leases;handoff.owner=owner;handoff.path=SETTINGS['research_lock']\n"
        " sys.modules[handoff.__name__]=handoff\n")
    wrapper = wrapper.replace(anchor, anchor+export)
    compile(wrapper, '<guarded-classic-check-with-exact-lease-handoff>', 'exec')
    with (output/'wrapper.py').open('xb') as stream:
        source = wrapper.encode()
        if stream.write(source) != len(source): raise OSError('Short guarded wrapper write')
        stream.flush(); os.fsync(stream.fileno())
    put(output/'ADMISSION.json', dict(payload={key:value for key,value in p.items() if key!='helper_source_b64'},
        budget=budget, policy=policy.validate(), complete_measured_plan_bytes=measured_plan, target_reservation_bytes=full,
        independent_host_reservation_bytes=full, existing_runtime_store=str(data),
        new_session_only=True, earlier_recordings_mutated=False, capture_authorized=False,
        saved_replay_authorized=True, saved_session_id=saved_id, source_metadata_sha256=source_pin,
        source_samples=source_frames, application_mode=mode, current_motion_used=False,
        helper_sha256=p['helper_source_sha256'], wrapper_sha256=hashlib.sha256(source).hexdigest(),
        ordinary_300s_qualification=False, physical_touch=False))
    command = ['systemd-run','--user','--unit='+unit,'--description=JustPeachyClassicUiCheck',
        '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64',
        '--property=RuntimeMaxSec='+str(budget['runtime_seconds']),'--property=TimeoutStopSec=30','--property=KillMode=control-group']
    values = dict(display, ALSA_CONFIG_PATH=binding['alsa_config'], PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', MALLOC_ARENA_MAX='1',
        MALLOC_MMAP_THRESHOLD_='131072', MALLOC_TRIM_THRESHOLD_='131072')
    command.extend('--setenv='+key+'='+value for key,value in values.items())
    command.extend([binding['python'], '-B', str(output/'wrapper.py')])
    start = subprocess.run(command, capture_output=True, text=True, timeout=10)
    put(output/'SYSTEMD_RUN.json', dict(returncode=start.returncode, stdout=start.stdout[:4096], stderr=start.stderr[:4096]))
    if start.returncode: raise RuntimeError('Owned classic-check service rejected; evidence retained')
    limit = time.monotonic()+5
    while not (output/'OWNER.json').exists() and time.monotonic()<limit: time.sleep(.05)
    owner = strict((output/'OWNER.json').read_bytes()) if (output/'OWNER.json').exists() else None
    shown = subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],
        capture_output=True, text=True, timeout=5, check=True)
    properties = dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    job = dict(schema='just-peachy.native-component-job.v1', boot_id=boot, unit=unit,
        invocation_id=properties.get('InvocationID'), control_group=properties.get('ControlGroup'), owner=owner,
        output_root=str(output), maximum_output_bytes=full, package_manifest_sha256=p['package_manifest_sha256'],
        issued_unix=time.time(), deadline_unix=time.time()+580, properties=properties,
        native_check_path=str(output/'NATIVE_CHECK.json'), helper_source_sha256=p['helper_source_sha256'])
    put(output/'JOB.json', job)
    return job


def finalize(payload, baseline):
    """Independent exact native unit closure precedes publishing status PASS."""
    output = Path(payload['output_root'])
    if output.parent != CAMPAIGN/'live-runtime-tests-20261003' or not re.fullmatch(r'classic-ui-check-\d{2}', output.name):
        raise ValueError('Exact fresh classic-check root required')
    job = strict((output/'JOB.json').read_bytes())
    package = Path(payload['package'])
    if job['package_manifest_sha256'] != payload['package_manifest_sha256'] or sha(package/'PACKAGE_MANIFEST.json') != job['package_manifest_sha256']:
        raise ValueError('Exact checked package changed')
    scope = load(package/'native_scope.py', 'classic_finalize_scope')
    scope.verified_inventory(package, job['package_manifest_sha256'])
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != job['boot_id'] or job.get('owner') is None or scope.alive(job['owner']):
        raise RuntimeError('Same-boot exact main identity must be closed')
    properties = scope.properties(job['unit'])
    if not scope.cgroup_empty(job['control_group']):
        raise RuntimeError('Exact owned service cgroup must be recursively empty')
    if properties.get('InvocationID') not in ('', job['invocation_id']) or properties.get('ActiveState') in ('active','activating','deactivating'):
        raise RuntimeError('Exact test service must be inactive without an invocation replacement')
    complete = strict((output/'COMPLETE.json').read_bytes())
    service, wrapper = strict((output/'SERVICE_EXIT.json').read_bytes()), strict((output/'JOB_EXIT.json').read_bytes())
    if (complete['status'] != 'FUNCTION_PASS_AWAITING_UNIT_CLOSURE' or service['exit_code'] != 0 or service['error'] is not None
        or wrapper['natural_returncode'] != 0 or wrapper['error'] is not None or wrapper['output_budget_failure'] is not None
        or complete['owner'] != job['owner'] or service['owner'] != job['owner']):
        raise RuntimeError('Actual full workflow and natural service exit required')
    from_path = package/'native_gui_driver.py'
    checker = load(from_path, 'classic_finalize_ui_checks')
    checker.require_closed(complete['worker_closure'])
    for source in scope.source_owners(Path(payload['data_root']), job['issued_unix']-10):
        if not source['exact_owner_gone'] or scope.alive(source['owner']):
            raise RuntimeError('Actual registered source owner still live')
    proof = dict(complete, status='PASS', main_exact_owner_gone=True, unit_recursively_empty=True,
        native_unit_properties=properties, unit=job['unit'], invocation_id=job['invocation_id'],
        control_group=job['control_group'], worker_source_closure_before_save=True,
        independent_native_finalize=True, full_private_pc_copy_required=True)
    put(output/'NATIVE_CHECK_V2.json', proof)
    return dict(native_check_path=str(output/'NATIVE_CHECK_V2.json'), proof=proof)


if 'PAYLOAD' in globals():
    RESULT = finalize(PAYLOAD, BASELINE) if PAYLOAD.get('operation') == 'finalize' else launch(PAYLOAD, BASELINE)
