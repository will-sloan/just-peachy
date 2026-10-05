"""One bounded actual classic-UI workflow. See README.md in full_application_20261004.

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
            boxes = [widget for widget in members(root) if widget.winfo_class() == 'Listbox']
            sources = [widget for widget in members(root) if widget.winfo_class() == 'TCombobox']
            if len(boxes) != 1 or len(sources) != 1:
                raise ValueError('Actual single backend/source chooser required')
            labels = boxes[0].get(0, 'end')
            matches = [index for index, label in enumerate(labels) if label == self.settings['chooser_label']]
            if len(matches) != 1:
                raise ValueError('Pinned backend label missing or ambiguous')
            boxes[0].selection_clear(0, 'end')
            boxes[0].selection_set(matches[0]); boxes[0].see(matches[0])
            sources[0].set('live')
            self.record('choose-backend', label=labels[matches[0]], input_source='live',
                manager_idle=True, capture_started=False)
            self.invoke(named(root, 'OK · open application'), 'chooser-ok')
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
            source='live', capture_started=False)
        self.root.report_callback_exception = lambda kind, value, traceback: self.abort(str(kind)+': '+str(value))
        self.root.after(100, self.tick)

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

    def tick(self):
        try:
            if self.stage != 'aborting' and time.monotonic() >= self.deadline:
                raise TimeoutError('Finite classic workflow deadline; normal Stop requested')
            closure = self.manager.poll()
            if self.stage == 'gallery_prepare':
                snapshot = self.ui.controller.snapshot()
                enrollment = snapshot['enrollment']
                if enrollment.get('error'):
                    raise RuntimeError('Actual enrollment preparation failed: '+str(enrollment['error']))
                if enrollment.get('models_prepared'):
                    service = self.ui.controller.gallery_service
                    self.record('actual-enrollment-models-prepared',
                        embedding=enrollment['embedding'], directory=str(service.directory),
                        owner=strict((service.directory/'REGISTERED_OWNER.json').read_bytes()),
                        microphone_started=enrollment['microphone_started'], person_created=False)
                    service.close(); self.stage = 'gallery_close'
                self.root.after(100, self.tick); return
            if self.stage == 'gallery_close':
                self.ui.controller.snapshot()
                if self.ui.controller.gallery_service is None:
                    self.gallery_prepared = True; self.stage = 'portrait'
                    self.record('actual-enrollment-helper-closed', capture_started=False)
                self.root.after(100, self.tick); return
            if self.stage == 'aborting':
                if self.manager.process is None:
                    self.ui.close(); return
            elif self.stage == 'portrait':
                if not self.geometry(self.root):
                    self.root.after(100, self.tick); return
                self.capture_home()
                self.invoke(self.ui.actions['mode'], 'mode-tab')
                if self.ui.page != 'modes': raise RuntimeError('Mode tab callback did not open its retained page')
                self.invoke(self.ui.actions['people'], 'people-tab')
                if self.ui.page != 'people': raise RuntimeError('People tab callback did not open its retained page')
                if self.settings['selection']['embedding'] != 'anonymous':
                    self.invoke(self.ui.actions['add_person'], 'add-person-form')
                    if self.ui.page != 'keyboard': raise RuntimeError('Original touch name keyboard required')
                    self.ui.keyboard_value.insert('1.0', 'UI prompt check only')
                    self.invoke(self.ui.actions['keyboard_done'], 'enrollment-name-done')
                    if self.ui.page != 'enrollment' or len(self.ui._paragraph) < 100:
                        raise RuntimeError('Original paragraph enrollment form required')
                    if str(self.ui.actions['enrollment_start'].cget('state')) != 'disabled':
                        raise RuntimeError('Enrollment must require its independent explicit consent')
                    self.record('original-enrollment-prompt', paragraph_sha256=hashlib.sha256(self.ui._paragraph.encode()).hexdigest(),
                        recording_started=False, named_person_created=False)
                else:
                    self.record('anonymous-people-page', enrollment_recording_started=False)
                    if str(self.ui.actions['add_person'].cget('state')) != 'disabled':
                        raise RuntimeError('Anonymous gallery mutation must be disabled')
                if self.settings.get('prepare_gallery') and not getattr(self, 'gallery_prepared', False):
                    self.ui.controller._gallery('enrollment_prepare')
                    self.stage = 'gallery_prepare'
                    self.root.after(100, self.tick); return
                self.invoke(self.ui.actions['settings'], 'settings-tab')
                if self.ui.page != 'settings': raise RuntimeError('Settings tab callback did not open its retained page')
                self.invoke(self.ui.actions['back'], 'return-to-transcript')
                if self.ui.page != 'captions': raise RuntimeError('Transcript page must be retained')
                self.ui._mic_consented = False  # Ephemeral: force the real consent control for this test.
                self.invoke(self.ui.actions['start_stop'], 'actual-start')
                if self.ui.page != 'consent': raise RuntimeError('Explicit actual microphone consent page required')
                self.invoke(self.ui.actions['confirm'], 'actual-consent')
                if self.manager.process is None:
                    raise RuntimeError('Actual Start/consent did not create a worker: '+str(self.ui._notice))
                if self.manager.request['selection'] != self.settings['selection'] or self.manager.request['policy'] != self.settings['policy']:
                    raise ValueError('Actual worker request differs from pinned short qualification policy')
                self.started = True; self.stage = 'capturing'
                self.record('actual-worker-started', launch_root=str(self.manager.run_dir),
                    request_sha256=sha(self.manager.run_dir/'REQUEST.json'), policy=self.manager.request['policy'])
            elif self.stage == 'capturing':
                identifier = self.manager.active_session_id()
                if identifier and self.manager.process is not None:
                    self.session_id = identifier
                    row = self.manager.store.read(identifier)
                    self.capture_samples = row['processed_samples']
                    if self.capture_samples >= int(self.settings['stop_after_seconds']*16000):
                        self.ui.snapshot = self.ui.controller.snapshot()
                        self.invoke(self.ui.actions['start_stop'], 'actual-stop')
                        if self.manager.stop_requested is None:
                            raise RuntimeError('Actual Stop callback did not request capture closure')
                        self.stopped = True; self.stage = 'draining'
                        self.record('source-boundary', session_id=identifier, processed_samples=self.capture_samples)
                if closure is not None and self.manager.process is None and not self.stopped:
                    raise RuntimeError('Source ended before the planned actual Stop: '+repr(closure.get('result')))
            elif self.stage == 'draining' and self.manager.process is None and closure is not None:
                from native_gui_driver import require_closed
                identifier = require_closed(closure)
                if identifier != self.session_id:
                    raise RuntimeError('Closed worker must match only this new session')
                self.worker_closure = closure
                row = self.manager.store.read(identifier)
                if row['status'] != 'stopped' or row['processed_samples'] < int(self.settings['stop_after_seconds']*16000):
                    raise RuntimeError('Committed processed audio and actual Stop/drain are required')
                self.record('worker-source-closed', session_id=identifier, closure=closure,
                    actual_processed_samples=row['processed_samples'])
                self.stage = 'post-stop'; self.post_at = time.monotonic()+.75
            elif self.stage == 'post-stop' and time.monotonic() >= self.post_at:
                if self.ui.page != 'save_session' or 'save_session' not in self.ui.actions:
                    raise RuntimeError('Actual post-Stop Save session prompt required')
                if self.settings.get('discard_session'):
                    self.invoke(self.ui.actions['discard_session'], 'post-stop-discard-dialog')
                    self.invoke(self.ui.actions['confirm'], 'actual-discard-confirmation')
                    if (self.manager.store.root/self.session_id).exists():
                        raise RuntimeError('Discard must remove the complete owned temporary session')
                    self.kept = True
                    self.record('temporary-session-discarded', session_id=self.session_id,
                        unrelated_recordings_changed=False)
                    self.invoke(self.ui.actions['settings'], 'final-settings')
                    self.invoke(named(self.root, 'Exit to desktop'), 'actual-exit-desktop')
                    self.exited = True; self.stage = 'exiting'
                    return
                self.invoke(self.ui.actions['save_session'], 'post-stop-save-session')
                row = self.manager.store.read(self.session_id)
                if row['status'] != 'kept' or row['include_raw'] != (row['spec']['mode'] == 'raw_processed'):
                    raise RuntimeError('Actual post-Stop processed-save disposition failed')
                files = []
                for segment in self.manager.store._segments(self.session_id, 'processed'):
                    for key in ('data_name', 'replay_name'):
                        if segment.get(key):
                            path = self.manager.store._audio_path(self.session_id, segment[key])
                            if len(files) >= 128 or path.stat().st_size > 32*MIB:
                                raise ValueError('Bounded own-session audio readback required')
                            files.append(dict(name=segment[key], bytes=path.stat().st_size, sha256=sha(path)))
                if not files or sum(segment['samples'] for segment in self.manager.store._segments(self.session_id, 'processed')) != row['processed_samples']:
                    raise RuntimeError('Exact complete processed replay timeline required')
                self.kept = True
                self.record('processed-audio-readback', session_id=self.session_id, processed_samples=row['processed_samples'],
                    include_raw=row['include_raw'], files=files, audio_private=True)
                self.invoke(self.ui.actions['settings'], 'final-settings')
                self.invoke(named(self.root, 'Exit to desktop'), 'actual-exit-desktop')
                if not self.ui.controller.closing:
                    raise RuntimeError('Actual Exit must close the facade after worker closure')
                self.exited = True; self.stage = 'exiting'
            if self.stage not in ('exiting',) and self.root.winfo_exists():
                self.root.after(100, self.tick)
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
            if self.title() == 'Just Peachy · choose combination':
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
            actual_portrait_ui=True, capture_function_passed=True, workers_closed=True,
            session_id=driver.session_id, worker_closure=driver.worker_closure,
            processed_save_passed=not settings.get('discard_session',False),
            complete_session_discard_passed=settings.get('discard_session',False),
            enrollment_models_prepared=getattr(driver,'gallery_prepared',False),
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
    for flag in ('prepare_gallery', 'discard_session'):
        if type(p.get(flag, False)) is not bool:
            raise ValueError('Typed changed gallery/disposition qualification flag required')
    if p.get('prepare_gallery') and selection['embedding'] == 'anonymous':
        raise ValueError('Anonymous has no enrollment encoder')
    policy = (profiles.SessionPolicy(maximum_session_seconds=330, manual_stop=True,
        model_load_seconds=30, max_drain_seconds=30, cleanup_seconds=30, max_backlog_seconds=60)
        if long_test else profiles.SessionPolicy(maximum_session_seconds=10))
    if selection['input_source'] != 'live' or selection['provisional_correction'] or selection['optional_d1_refiner']:
        raise ValueError('One ordinary single-worker live backend required')
    stop = p.get('stop_after_seconds', 3)
    if type(stop) not in (int, float) or not ((305 <= stop <= 315) if long_test else (3 <= stop <= 5)):
        raise ValueError('Explicit three-to-five or305-to315-second processed-audio test required')
    data = Path(p['data_root'])
    if data != RUNTIME_DATA or data.is_symlink() or data.resolve(strict=True) != data:
        raise ValueError('Actual canonical owned runtime data root required')
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
    if binding.get('raw_adapter_enabled') is True:
        spec.update(mode='raw_processed', raw=dict(sample_rate=16000, channels=4, sample_width_bytes=4,
            encoding='PCM_S32LE', qualification=dict(qualified=True,
                evidence='allocation only; actual worker verifies independently qualified physical raw route')))
    measured_plan = storage.StoragePolicy(**binding.get('storage_policy', {})).estimate_bytes(spec)+32*MIB
    full = (512 if long_test else 64)*MIB
    if (type(p.get('maximum_output_bytes')) is not int or p['maximum_output_bytes'] != full
        or type(p.get('independent_pc_copy_bytes')) is not int or p['independent_pc_copy_bytes'] != full
        or measured_plan > full):
        raise ValueError('Exact independent64/512MiB native and PC reservations must cover the complete measured plan')
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
        driver_seconds=540 if long_test else 480, stop_after_seconds=stop, manual_stop_test=long_test,
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
        new_session_only=True, earlier_recordings_mutated=False, capture_authorized=True,
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
