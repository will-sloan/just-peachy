"""Single desktop entry: profile/source selector and persistent history. See README.md."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from profiles import RuntimeSelection, SessionPolicy, catalog
from runtime_support import Lease, publish, strict, digest, current_owner, encoded, owner_status, kill_owned_unit
from storage import SessionStore, StoragePolicy
from storage_support import error_facts


def selection_control_states(diarizer, attribution, optional=False, provisional=False):
    return dict(geometry='readonly' if diarizer=='nemotron' else 'disabled',
                revision='normal' if attribution=='single_d1_late_labels' or optional or provisional else 'disabled')


class Manager:
    """One owned worker at a time; recording count is never an admission input."""
    def __init__(self, binding_path, data_root, unit, *, process_factory=subprocess.Popen,
                 unit_ownership=None, owner_probe=owner_status, unit_killer=kill_owned_unit,
                 session_authorizer=None, service_room_check=None):
        self.binding_path = Path(binding_path).resolve()
        self.binding = strict(self.binding_path.read_bytes())
        self.data_root = Path(data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.launches = self.data_root/'launches'
        self.launches.mkdir(exist_ok=True)
        self.lease = Lease(self.data_root/'launcher.lock')
        try:
            self.store = SessionStore(self.data_root/'recordings', StoragePolicy(**self.binding.get('storage_policy', {})))
        except BaseException as error:
            try:
                self.lease.close()
            except BaseException as secondary:
                error.add_note('Launcher initialization lease close failed: '+repr(secondary))
            finally:
                if not self.lease.file.closed:
                    try:
                        self.lease.file.close()
                    except BaseException as secondary:
                        error.add_note('Launcher initialization handle close failed: '+repr(secondary))
            raise
        self.unit = unit
        self.unit_ownership = Path(unit_ownership) if unit_ownership else None
        self.owner_probe = owner_probe
        self.unit_killer = unit_killer
        self.session_authorizer = session_authorizer
        self.service_room_check = service_room_check
        self.watchdog_requested = False
        self.process_factory = process_factory
        self.process = None
        self.owner_dir = self.run_dir = None
        self.reader = None
        self.reader_error = None
        self.closed = False
        self.last = None
        self.stop_requested = None
        self.request = None
        self.latest_health = self.latest_diagnostic = None
        self.started = None
        self.spatial_visible = False
        self.latest_spatial = None
        self.export_task = None
        self.last_export = None
        self._readiness_thread = None
        self._readiness_done = threading.Event()
        self._readiness_cancel = threading.Event()
        self._readiness_result = self._readiness_error = None
        self._readiness_origin = self._start_context = None
        self._continuation_used = self._resuming_start = False
        self.readiness_notice = ''

    @property
    def readiness_pending(self):
        """The helper remains owned until poll joins it; Stop stays available."""
        return self._readiness_thread is not None

    def start(self, selection, policy, saved_path=None, *, saved_session_id=None, saved_store_root=None,
              repeat_input_seconds=None, application=None):
        self.poll()
        if self.export_task is not None:
            raise RuntimeError('Wait for the selected recording export to close before Start')
        if self.closed or self.process is not None or self.readiness_pending:
            raise RuntimeError('Close the previous owned worker before another Start')
        selection.validate(); policy.validate()
        from application_contract import validate, default
        application = validate(application or default(selection.embedding), selection)
        from developer_replay import validate_repeat, pin_repeat_input
        validate_repeat(selection,policy,saved_path,saved_session_id,repeat_input_seconds)
        repeat_input_sha256=pin_repeat_input(saved_path,policy) if repeat_input_seconds is not None else None
        if selection.provisional_correction:
            raise RuntimeError('Provisional correction is disabled pending native admission')
        self._check_previous_launch()
        if selection.input_source == 'saved':
            if bool(saved_path) == bool(saved_session_id):
                raise ValueError('Choose one complete kept recording or one processed replay WAV')
            if saved_session_id:
                source_root = Path(saved_store_root).absolute() if saved_store_root else self.store.root
                if source_root != self.store.root:
                    raise ValueError('History replay must use this owned recording store')
                metadata = self.store.read(saved_session_id)
                if metadata['status'] != 'kept' or not 0 < metadata['processed_samples'] <= policy.maximum_samples():
                    raise ValueError('Choose a kept recording that fits the explicit duration policy')
                saved_store_root = str(source_root)
        elif saved_path or saved_session_id or saved_store_root:
            raise ValueError('Saved input cannot be attached to a live source')
        if self.binding.get('native_launch_enabled') is not True:
            raise RuntimeError('Candidate native installation/admission is pending; retained runtime remains available')
        from release_authorization import authorize_session, require_service_room
        authorization = (self.session_authorizer or authorize_session)(self.binding, selection, policy)
        if self.unit_ownership is not None:
            (self.service_room_check or require_service_room)(self.unit_ownership, policy)
        from optional_refiner_dispatch import request_receipt
        optional_admission=request_receipt(self.binding,selection,policy)
        if not self._resuming_start:
            self.stop_requested = None
            self.watchdog_requested = False
            self.reader_error = None
            self.latest_health = self.latest_diagnostic = self.latest_spatial = None
            self._readiness_cancel.clear()
            self._continuation_used = False
            self._start_context = strict(encoded(dict(selection=selection.validate(), policy=policy.validate(),
                saved_path=str(saved_path) if saved_path else None, saved_session_id=saved_session_id,
                saved_store_root=str(saved_store_root) if saved_store_root else None,
                repeat_input_seconds=repeat_input_seconds, application=application)))
            if selection.input_source == 'live':
                previous = self._previous_readiness_fault()
                if previous is not None:
                    self._begin_readiness(previous)
                    return
        self.run_dir = self.launches/uuid.uuid4().hex
        self.run_dir.mkdir()
        self.owner_dir = self.run_dir/'worker'
        publish(self.data_root/'CURRENT_LAUNCH.json', dict(launch_id=self.run_dir.name), replace=True)
        request = dict(binding=str(self.binding_path), binding_sha256=digest(self.binding_path),
            data_root=str(self.data_root/'recordings'), unit=self.unit,
            authorization=authorization,
            selection=selection.validate(), policy=policy.validate(), application=application,
            storage_policy=self.binding.get('storage_policy', {}), saved_path=str(saved_path) if saved_path else None,
            saved_session_id=saved_session_id, saved_store_root=saved_store_root,
            repeat_input_seconds=repeat_input_seconds,repeat_input_sha256=repeat_input_sha256,
            optional_refiner_admission=optional_admission)
        request_path = self.run_dir/'REQUEST.json'
        publish(request_path, request)
        self.request = request
        self.latest_spatial = None
        self.latest_health = self.latest_diagnostic = None
        self.reader_error = None
        self.stop_requested = None
        self.watchdog_requested = False
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
                   OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
                   MALLOC_ARENA_MAX='1',MALLOC_MMAP_THRESHOLD_='131072',MALLOC_TRIM_THRESHOLD_='131072')
        try:
            self.process = self.process_factory([self.binding['python'], str(Path(__file__).with_name('worker.py')),
                '--request', str(request_path), '--owner-directory', str(self.owner_dir)],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        except BaseException as exc:
            publish(self.run_dir/'START_FAILURE.json', dict(error=repr(exc), child_started=False))
            raise
        self.started = time.monotonic()
        proc = self.process
        def collect():
            count = 0
            try:
                with (self.run_dir/'WORKER.log').open('xb') as stream:
                    from runtime_ui_channel import StreamDecoder
                    def diagnostic(raw):
                        nonlocal count
                        remaining=max(0,512*1024-count)
                        if remaining:stream.write(raw[:remaining])
                        count+=len(raw)
                        if count>512*1024:
                            self.reader_error='Worker output exceeded512KiB; original prefix retained'
                            self.stop()
                    def spatial(row):self.latest_spatial=row
                    def status(row):
                        if row['kind']=='health':self.latest_health=row
                        else:self.latest_diagnostic=row
                    decoder=StreamDecoder(spatial,diagnostic,status)
                    while True:
                        raw = getattr(proc.stdout,'read1',proc.stdout.read)(4096)
                        if not raw:
                            break
                        decoder.feed(raw)
                    decoder.finish()
                    stream.flush(); os.fsync(stream.fileno())
            except BaseException as exc:
                self.reader_error = repr(exc)
            finally:
                proc.stdout.close()
        self.reader = threading.Thread(target=collect, name='v29-worker-output', daemon=True)
        self.reader.start()
        self.last = None
        child_owner = None
        if isinstance(self.process, subprocess.Popen):
            try:
                if os.name == 'nt':
                    import psutil
                    child_owner = dict(pid=self.process.pid, create_time=psutil.Process(self.process.pid).create_time())
                else:
                    child_owner = dict(pid=self.process.pid,
                        start_ticks=int(Path('/proc', str(self.process.pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]),
                        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
            except (FileNotFoundError, ProcessLookupError):
                pass
        publish(self.run_dir/'CHILD_LAUNCH.json', dict(pid=self.process.pid, manager=current_owner(),
            child_owner=child_owner, request_sha256=digest(request_path)))

    def _readiness_fault(self, closure):
        """Only an exact naturally closed, empty physical AEC255 source qualifies."""
        from xvf_readiness import qualifying_fault
        if type(closure) is not dict or closure.get('direct_child_reaped') is not True:
            return False
        nested = closure.get('nested_source')
        if (type(nested) is not dict or nested.get('closed') is not True
                or closure.get('stdout_reader_joined') is not True or closure.get('receipt_errors')
                or closure.get('output_error') or type(closure.get('returncode')) is not int
                or closure['returncode'] < 0):
            return False
        physical = nested.get('physical_receipt')
        if type(physical) is not dict or not qualifying_fault(physical):
            return False
        owners = (closure.get('registered_owner'), physical.get('owner'))
        for owner in owners:
            if (type(owner) is not dict or set(owner) != {'pid', 'start_ticks', 'boot_id'}
                    or type(owner['pid']) is not int or owner['pid'] <= 0
                    or type(owner['start_ticks']) is not int or owner['start_ticks'] <= 0
                    or type(owner['boot_id']) is not str):
                return False
            try:
                if str(uuid.UUID(owner['boot_id'])) != owner['boot_id']:
                    return False
            except ValueError:
                return False
        result = closure.get('result')
        facts = result.get('source_facts') if type(result) is dict else None
        if (type(facts) is not dict or facts.get('input_source') != 'live'
                or facts.get('owner') != owners[1] or facts.get('source_thread_joined') is not True
                or type(facts.get('child_returncode')) is not int or facts['child_returncode'] < 0
                or type(facts.get('processed_samples')) is not int or facts['processed_samples'] != 0):
            return False
        if os.name == 'posix' and any(type(owner) is not dict or
                owner.get('boot_id') != current_owner()['boot_id'] for owner in owners):
            return False
        return all(type(state) is dict and state.get('closed') is True
                   for state in (self.owner_probe(owner) for owner in owners))

    def _previous_readiness_fault(self):
        pointer = self.data_root/'CURRENT_LAUNCH.json'
        if not pointer.exists():
            return None
        identifier = strict(pointer.read_bytes()).get('launch_id')
        if type(identifier) is not str or len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
            raise RuntimeError('Previous microphone launch identifier is invalid')
        path = self.launches/identifier/'HOST_CLOSURE.json'
        if not path.exists():
            return None
        if path.is_symlink() or path.stat().st_size > 262144:
            raise RuntimeError('Previous microphone closure must be a bounded real receipt')
        closure = strict(path.read_bytes())
        if not self._readiness_fault(closure):
            return None
        from xvf_readiness import preserved_unsent_manual_failure
        if preserved_unsent_manual_failure(self, closure):
            # Preserve the old failed/no-send recovery. A fresh ordinary source
            # produces new ownership/fault evidence before any fixed helper.
            return None
        return closure

    def _begin_readiness(self, closure):
        """Use at most one helper/continuation for the unchanged user Start."""
        if (self._continuation_used or self.readiness_pending or self._readiness_cancel.is_set()
                or self.closed or self.process is not None or not self._readiness_fault(closure)):
            raise RuntimeError('Microphone recovery continuation is not admitted')
        pointer = strict((self.data_root/'CURRENT_LAUNCH.json').read_bytes())
        origin = self.launches/pointer['launch_id']
        if strict((origin/'HOST_CLOSURE.json').read_bytes()) != closure:
            raise RuntimeError('Microphone continuation must bind the current closed failure')
        self._continuation_used = True
        self._readiness_origin = (origin, closure)
        self._readiness_result = self._readiness_error = None
        self._readiness_done.clear()
        self.stop_requested = None
        self.readiness_notice = 'Preparing microphone after its closed startup fault; Stop cancels this Start.'
        publish(origin/('SOURCE_RESTART_INTENT_'+uuid.uuid4().hex+'.json'),
                dict(schema='just-peachy.same-start-readiness.v1', maximum_continuations=1,
                     original_request_sha256=digest(origin/'REQUEST.json'),
                     original_source_sha256=digest(self.store._artifact_path(
                         strict((origin/'worker/SESSION.json').read_bytes())['session_id'],
                         'work/source/SOURCE_CLOSE.json')),
                     requested_selection=self._start_context['selection'], closure_claimed=False))
        def recover():
            try:
                if self._readiness_cancel.is_set():
                    return
                from xvf_readiness import recover_previous_source
                self._readiness_result = recover_previous_source(self)
                if self._readiness_result is None:
                    raise RuntimeError('Exact closed microphone fault no longer qualifies; Start was not repeated')
            except BaseException as exc:
                self._readiness_error = type(exc).__name__+': '+str(exc)
            finally:
                self._readiness_done.set()
        self._readiness_thread = threading.Thread(target=recover, name='xvf-start-readiness', daemon=True)
        try:
            self._readiness_thread.start()
        except BaseException:
            self._readiness_thread = None
            self._readiness_done.set()
            raise

    def _poll_readiness(self):
        if not self._readiness_done.is_set():
            return None
        self._readiness_thread.join()
        self._readiness_thread = None
        origin, closure = self._readiness_origin
        cancelled = self._readiness_cancel.is_set() or self.closed
        decision = dict(schema='just-peachy.same-start-readiness.v1',
                        cancelled=cancelled, result=self._readiness_result,
                        error=self._readiness_error, helper_thread_joined=True,
                        fresh_worker_requested=not cancelled and self._readiness_error is None)
        publish(origin/('SOURCE_RESTART_RESULT_'+uuid.uuid4().hex+'.json'), decision)
        if cancelled or self._readiness_error is not None:
            self.readiness_notice = ('Microphone Start cancelled; recovery evidence retained.' if cancelled else
                                    'Microphone recovery stopped safely: '+self._readiness_error)
            self.last = dict(closure, readiness_continuation=decision)
            return self.last
        context = self._start_context
        self.readiness_notice = 'Microphone ready; loading the selected backend.'
        self._resuming_start = True
        try:
            self.start(RuntimeSelection(**context['selection']), SessionPolicy(**context['policy']),
                       context['saved_path'], saved_session_id=context['saved_session_id'],
                       saved_store_root=context['saved_store_root'],
                       repeat_input_seconds=context['repeat_input_seconds'], application=context['application'])
        except BaseException as exc:
            self.readiness_notice = 'Recovered microphone Start refused: '+str(exc)
            self.last = dict(closure, readiness_continuation=dict(decision, restart_error=repr(exc)))
            return self.last
        finally:
            self._resuming_start = False
        return None

    def _nested_source(self, owner_dir):
        result_path = owner_dir/'RESULT.json'
        result_unreadable = False
        try:
            if result_path.exists() and (result_path.is_symlink() or result_path.stat().st_size > 262144):
                raise ValueError('Bounded real worker result receipt required')
            result = strict(result_path.read_bytes()) if result_path.exists() else {}
            if type(result) is not dict:
                raise ValueError('Worker result must be an object')
            facts = result.get('source_facts', {})
            if type(facts) is not dict:
                raise ValueError('Source facts must be an object')
            samples = facts.get('processed_samples', 0)
            if type(samples) is not int or samples < 0 or any(
                    key in facts and type(facts[key]) is not bool for key in
                    ('source_start_observed', 'physical_start_packet_observed')):
                raise ValueError('Exact nonnegative samples and boolean source observations required')
        except (OSError, ValueError):
            result, facts, samples, result_unreadable = {}, {}, 0, True
        saved = self._saved_source(owner_dir, result, facts, result_unreadable)
        if saved is not None:
            return saved
        observed = facts.get('source_start_observed') is True or facts.get('physical_start_packet_observed') is True
        observed = observed or (type(samples) is int and samples > 0)
        def missing_source():
            # No directory is not evidence that a microphone never opened.
            # Positive worker observations require an exact source identity.
            return dict(closed=not observed and not result_unreadable,
                        state='SOURCE_OWNER_RECEIPT_MISSING' if observed else 'SOURCE_START_UNVERIFIABLE' if result_unreadable else 'SOURCE_START_UNOBSERVED',
                        source_start_observed=observed)
        session_path = owner_dir/'SESSION.json'
        if not session_path.exists():
            return missing_source()
        session_id = strict(session_path.read_bytes())['session_id']
        path = self.store._artifact_path(session_id, 'work/source/REGISTERED_OWNER.json')
        if not path.parent.exists():
            return missing_source()
        if not path.exists():
            return dict(closed=False, state='SOURCE_OWNER_RECEIPT_MISSING')
        registration = strict(path.read_bytes())
        owner = registration.get('owner')
        status = self.owner_probe(owner)
        closure_path = path.with_name('SOURCE_CLOSE.json')
        physical = strict(closure_path.read_bytes()) if closure_path.exists() else None
        if physical and physical.get('owner') != owner:
            return dict(closed=False, state='SOURCE_CLOSURE_OWNER_MISMATCH', owner=owner)
        if result_unreadable:
            return dict(closed=False, state='SOURCE_RESULT_UNVERIFIABLE',
                owner=owner, owner_status=status, physical_receipt=physical)
        return dict(status, owner=owner, physical_receipt=physical)

    def _saved_source(self, owner_dir, result, facts, result_unreadable):
        """A Saved reader is a worker thread, never a microphone subprocess."""
        def read(path):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 262144:
                raise ValueError('Bounded real Saved closure receipt required')
            value = strict(path.read_bytes())
            if type(value) is not dict:
                raise ValueError('Saved closure receipt must be an object')
            return value
        request_path = owner_dir.parent/'REQUEST.json'
        indicated = facts.get('input_source') == 'saved'
        try:
            request = read(request_path)
        except (OSError, ValueError):
            if not indicated:
                return None
            return dict(closed=False, state='SAVED_REQUEST_UNVERIFIABLE')
        selection = request.get('selection')
        if type(selection) is not dict or selection.get('input_source') != 'saved':
            return dict(closed=False, state='SAVED_REQUEST_SOURCE_MISMATCH') if indicated else None
        try:
            if result_unreadable or not result:
                raise ValueError('Saved worker result is missing or unreadable')
            owner = read(owner_dir/'REGISTERED_OWNER.json')
            child = read(owner_dir.parent/'CHILD_LAUNCH.json')
            envelope = read(owner_dir/'ENVELOPE.json')
            session = read(owner_dir/'SESSION.json')
            sid = session.get('session_id')
            if (type(sid) is not str or len(sid) != 32 or any(c not in '0123456789abcdef' for c in sid)
                    or result.get('session_id') != sid or session.get('worker') != owner
                    or child.get('child_owner') != owner or type(child.get('pid')) is not int
                    or child['pid'] != owner.get('pid') or type(owner.get('pid')) is not int
                    or child.get('request_sha256') != digest(request_path)
                    or envelope.get('owner') != owner or type(request.get('policy')) is not dict
                    or encoded(envelope.get('policy')) != encoded(request['policy'])):
                raise ValueError('Exact Saved request, worker, envelope and session binding required')
            pin = request.get('binding_sha256')
            if type(pin) is not str or len(pin) != 64 or any(c not in '0123456789abcdef' for c in pin):
                raise ValueError('Exact deployment binding pin required')
            kept, wav = request.get('saved_session_id'), request.get('saved_path')
            if bool(kept) == bool(wav):
                raise ValueError('Exactly one kept recording or replay WAV required')
            if kept is not None and (type(kept) is not str or len(kept) != 32
                    or any(c not in '0123456789abcdef' for c in kept)
                    or request.get('saved_store_root') != request.get('data_root')):
                raise ValueError('Kept source must belong to the requested recording store')
            if wav is not None and (type(wav) is not str or not wav or request.get('saved_store_root') is not None):
                raise ValueError('Replay WAV must not claim kept spatial evidence')
            for name in ('REGISTERED_OWNER.json', 'SOURCE_CLOSE.json'):
                if self.store._artifact_path(sid, 'work/source/'+name).exists():
                    raise ValueError('Saved replay unexpectedly has a physical source receipt')
            failure = result.get('failure')
            if failure is not None and (type(failure) is not str or not failure):
                raise ValueError('Exact Saved failure value required')
            engine = result.get('result')
            cleanup = result.get('cleanup')
            if type(result.get('logical_cleanup_complete')) is not bool:
                raise ValueError('Saved logical cleanup must remain explicit')
            samples = facts.get('processed_samples', 0)
            if type(samples) is not int or samples < 0:
                raise ValueError('Exact Saved processed sample count required')
            if facts:
                if (facts.get('input_source') != 'saved' or facts.get('owner') is not None
                        or facts.get('child_returncode') is not None
                        or facts.get('physical_start_packet_observed') is not False
                        or type(facts.get('source_thread_joined')) is not bool
                        or type(facts.get('source_start_observed')) is not bool
                        or facts.get('physical_process_closed') is not False):
                    raise ValueError('Saved source facts must describe an in-process reader only')
            elif failure is None or engine is not None:
                raise ValueError('Saved reader facts are missing')
            if engine is not None:
                if (type(engine) is not dict or encoded(engine.get('selection')) != encoded(selection)
                        or encoded(engine.get('source_policy')) != encoded(request['policy'])
                        or type(engine.get('source_samples')) is not int or engine['source_samples'] != samples):
                    raise ValueError('Saved engine selection, policy or source count differs from request')
            elif failure is None:
                raise ValueError('Saved success lacks an engine result')
            spatial = None if engine is None else engine.get('saved_spatial')
            application = request.get('application')
            if type(application) is not dict:
                raise ValueError('Saved application intent is missing')
            spatial_required = application.get('mode') in (
                'spatial_assisted', 'strongly_spatial_assisted', 'spatial_selected',
                'strongly_spatial_selected', 'assigned_direction', 'assigned_hybrid')
            if failure is None:
                if (engine.get('status') != 'FUNCTIONAL_SESSION_COMPLETED'
                        or facts.get('source_thread_joined') is not True or facts.get('source_error') is not None
                        or result['logical_cleanup_complete'] is not True or result.get('cleanup_attempted') is not True
                        or result.get('cleanup_error') is not None or type(cleanup) is not dict
                        or cleanup.get('attempted') is not True or cleanup.get('model_lanes_owned') is not False
                        or cleanup.get('logical_cleanup_complete') is not True or cleanup.get('errors') != []
                        or type(cleanup.get('completed')) is not list or 'source_stop_join' not in cleanup['completed']):
                    raise ValueError('Successful Saved replay requires actual reader join and cleanup')
                if spatial_required or spatial is not None:
                    if (kept is None or type(spatial) is not dict or spatial.get('session_id') != kept
                            or spatial.get('schema') != 'just-peachy.saved-spatial-replay.v1'
                            or spatial.get('source_verified_after_drain') is not True
                            or spatial.get('source_shared_lease_closed') is not True
                            or spatial.get('current_motion_used') is not False
                            or type(spatial.get('metadata_sha256')) is not str
                            or len(spatial['metadata_sha256']) != 64
                            or any(c not in '0123456789abcdef' for c in spatial['metadata_sha256'])
                            or 'saved_spatial_lease' not in cleanup['completed']):
                        raise ValueError('Saved spatial replay lacks verified historical source closure')
            status = self.owner_probe(owner)
            if type(status) is not dict or status.get('closed') is not True:
                return dict(closed=False, state='SAVED_WORKER_STILL_OWNED', worker_status=status)
            return dict(closed=True, state='SAVED_INPROCESS_SOURCE_CLOSED', input_source='saved',
                session_id=sid, processed_samples=samples, worker=owner, worker_status=status,
                physical_inprocess_closure=True, physical_microphone=False,
                source_thread_joined=facts.get('source_thread_joined'),
                logical_cleanup_complete=result['logical_cleanup_complete'], failure=failure,
                saved_spatial=spatial, request_sha256=child['request_sha256'],
                scope='Exact worker OS absence closes in-process replay threads; logical failure is preserved')
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return dict(closed=False, state='SAVED_SOURCE_CLOSURE_UNVERIFIABLE', error=str(exc))

    def _check_previous_launch(self):
        pointer = self.data_root/'CURRENT_LAUNCH.json'
        if not pointer.exists():
            return
        launch_id = strict(pointer.read_bytes()).get('launch_id')
        if not isinstance(launch_id, str) or len(launch_id) != 32 or any(c not in '0123456789abcdef' for c in launch_id):
            raise RuntimeError('Invalid previous launch identity')
        previous = self.launches/launch_id
        if (previous/'HOST_CLOSURE.json').exists() or (previous/'START_FAILURE.json').exists():
            return
        child_path = previous/'CHILD_LAUNCH.json'
        registration = previous/'worker'/'REGISTERED_OWNER.json'
        if registration.exists():
            owner = strict(registration.read_bytes())
        elif child_path.exists():
            owner = strict(child_path.read_bytes()).get('child_owner')
        else:
            raise RuntimeError('Previous launch lacks child closure evidence')
        state = self.owner_probe(owner)
        source = self._nested_source(previous/'worker')
        if not state['closed'] or not source['closed']:
            raise RuntimeError('Previous worker/source owner is still live or unverifiable')
        publish(previous/'RECOVERED_CLOSURE.json', dict(worker=state, source=source), replace=True)

    def stop(self):
        self._readiness_cancel.set()
        if self.readiness_pending:
            self.stop_requested = self.stop_requested or time.monotonic()
            self.readiness_notice = 'Cancelling microphone Start; waiting for the owned recovery helper to close.'
        if self.process is None:
            return
        self.stop_requested = self.stop_requested or time.monotonic()
        if self.owner_dir.exists() and not (self.owner_dir/'STOP').exists():
            # Marker is idempotent control, never a mutation of a closed receipt.
            try:
                (self.owner_dir/'STOP').touch(exist_ok=False)
            except FileExistsError:
                pass

    def show_spatial(self,visible):
        self.spatial_visible=bool(visible)
        if self.process is None or self.owner_dir is None or not self.owner_dir.is_dir():return
        marker=self.owner_dir/'GUI_SPATIAL_ON'
        if self.spatial_visible:marker.touch(exist_ok=True)
        else:marker.unlink(missing_ok=True)

    def poll(self):
        if self.readiness_pending:
            return self._poll_readiness()
        if self.process is None:
            return self.last
        if self.spatial_visible and self.owner_dir.is_dir() and not (self.owner_dir/'GUI_SPATIAL_ON').exists():
            self.show_spatial(True)
        if self.stop_requested is not None:
            self.stop()  # Persist a Stop requested before early owner registration.
        if (self.run_dir/'STOP_REQUEST').exists():
            self.stop()
        policy = SessionPolicy(**self.request['policy'])
        overdue = time.monotonic()-self.started > policy.total_deadline_seconds
        if self.stop_requested is not None:
            overdue = overdue or time.monotonic()-self.stop_requested > policy.max_drain_seconds + policy.cleanup_seconds
        if overdue:
            self.stop()
            self.reader_error = self.reader_error or 'Worker exceeded explicit process deadline'
            if self.unit_ownership is not None and not self.watchdog_requested:
                self.watchdog_requested = True
                publish(self.run_dir/'WATCHDOG_REQUEST.json', dict(unit=self.unit,
                    ownership_path=str(self.unit_ownership), reason=self.reader_error,
                    closure_claimed=False))
                self.unit_killer(self.unit, self.unit_ownership)
        status = self.process.poll()
        if status is None:
            return None
        self.process.wait()
        self.reader.join(5)
        if self.reader.is_alive():
            raise RuntimeError('Child reaped but output reader remains owned')
        nested = self._nested_source(self.owner_dir)
        if not nested['closed']:
            publish(self.run_dir/'NESTED_CLOSURE_PENDING.json', nested, replace=True)
            return None
        result_path = self.owner_dir/'RESULT.json'
        result = None
        receipt_errors = []
        try:
            result = strict(result_path.read_bytes()) if result_path.exists() else None
        except (OSError, ValueError) as exc:
            receipt_errors.append('result: ' + repr(exc))
        identity_path = self.owner_dir/'REGISTERED_OWNER.json'
        identity = None
        try:
            identity = strict(identity_path.read_bytes()) if identity_path.exists() else None
        except (OSError, ValueError) as exc:
            receipt_errors.append('owner: ' + repr(exc))
        # Popen.wait is direct-child closure; identity is retained separately.
        closure = dict(returncode=status, direct_child_reaped=True, registered_owner=identity,
                       stdout_reader_joined=True, output_error=self.reader_error, result=result,
                       receipt_errors=receipt_errors, nested_source=nested)
        publish(self.run_dir/'HOST_CLOSURE.json', closure)
        self.last = closure
        self.process = None
        if (self._start_context is not None and self._start_context['selection']['input_source'] == 'live'
                and not self._continuation_used and not self._readiness_cancel.is_set()
                and self.stop_requested is None and not self.watchdog_requested and not self.closed
                and self._readiness_fault(closure)):
            self._begin_readiness(closure)
            return None
        return closure

    def active_session_id(self):
        if self.owner_dir is None:
            return None
        path = self.owner_dir/'SESSION.json'
        return strict(path.read_bytes())['session_id'] if path.exists() else None

    def export_recordings(self, session_ids, destination):
        if self.process is not None or self.export_task is not None or self.closed or self.readiness_pending:
            raise RuntimeError('Stop the active session and close any prior export first')
        from owned_export import ExportTask
        deadline = None
        if self.unit_ownership is not None:
            deadline = strict(self.unit_ownership.read_bytes())['deadline_monotonic']
        self.export_task = ExportTask(self.store, session_ids, destination, self.data_root/'exports',
            python=self.binding['python'], deadline_monotonic=deadline)
        return self.export_task

    def poll_export(self):
        if self.export_task is None:
            return None
        result = self.export_task.poll()
        if self.export_task.finished:
            self.last_export = result; self.export_task = None
            return result
        return None

    def close(self):
        self._readiness_cancel.set()
        errors = []
        for operation in (self.poll, self.poll_export):
            try:
                operation()
            except BaseException as error:
                errors.append(error)
        if self.export_task is not None:
            self.export_task.cancel()
            raise RuntimeError('Closing the owned export. Exit remains pending until it is reaped.')
        if self.process is not None:
            self.stop()
            raise RuntimeError('Stopping and draining. Exit remains pending until the worker closes.')
        if self.readiness_pending:
            self.readiness_notice = 'Closing microphone recovery before Exit.'
            raise RuntimeError('Microphone recovery is closing. Exit remains pending until the helper is reaped.')
        # Database publication is independent of releasing the launcher lease.
        for operation in (self.store.close, self.lease.close):
            try:
                operation()
            except BaseException as error:
                errors.append(error)
        try:
            if not self.lease.file.closed:
                self.lease.file.close()
        except BaseException as error:
            errors.append(error)
        spool = getattr(self.store, '_spool', None)
        self.closed = self.lease.file.closed and (spool is None or spool.closed)
        if errors:
            for secondary in errors[1:]:
                errors[0].add_note('Independent launcher cleanup also failed: '+repr(secondary))
            raise errors[0]


class CaptionView:
    """Bounded newest-caption view, refreshed only when a revision changes."""
    def __init__(self, store, limit=40):
        self.store, self.limit = store, limit
        self.session_id = self.revision = None
        self.rows = []

    def refresh(self, session_id):
        if session_id != self.session_id:
            self.session_id, self.revision = session_id, None
        page = self.store.latest_captions(session_id, self.limit, self.revision)
        if page['changed']:
            self.rows = page['items']
            self.revision = page['revision_cursor']
        return page['changed']


def request_current_stop(data_root):
    """Headless control targets only the one indexed owned launch."""
    root = Path(data_root)
    launch_id = strict((root/'CURRENT_LAUNCH.json').read_bytes()).get('launch_id')
    if not isinstance(launch_id, str) or len(launch_id) != 32 or any(c not in '0123456789abcdef' for c in launch_id):
        raise RuntimeError('Invalid current launch identity')
    directory = root/'launches'/launch_id
    if any(path.is_symlink() for path in (directory, *directory.parents)) or not (directory/'REQUEST.json').is_file():
        raise RuntimeError('Owned current launch required')
    (directory/'STOP_REQUEST').touch(exist_ok=True)
    return launch_id


def run_headless(manager, selection, policy, *, saved_path=None, saved_session_id=None, saved_store_root=None,
                 stop_after_seconds=None, keep_processed=False, poll_interval=.1, repeat_input_seconds=None):
    """Finite explicit capture/replay; keep only after nested physical closure."""
    if stop_after_seconds is not None and not 0 < stop_after_seconds <= policy.maximum_session_seconds:
        raise ValueError('Stop interval must fit the allocated session duration')
    manager.start(selection, policy, saved_path, saved_session_id=saved_session_id, saved_store_root=saved_store_root,
                  repeat_input_seconds=repeat_input_seconds)
    began = time.monotonic()
    while True:
        if stop_after_seconds is not None and time.monotonic()-began >= stop_after_seconds:
            manager.stop()
        closure = manager.poll()
        if closure is not None:
            break
        time.sleep(poll_interval)
    result = closure.get('result') or {}
    if keep_processed and closure['returncode'] == 0 and not result.get('failure'):
        session_id = result.get('session_id') or manager.active_session_id()
        manager.store.keep(session_id, include_raw=False)
    manager.close()
    return closure


def gui_session_policy(binding, selection):
    """Use one exact reviewed optional policy; ordinary GUI defaults stay fixed."""
    chosen = selection.validate()
    if not selection.optional_d1_refiner:
        return SessionPolicy()
    from release_authorization import authorization
    from optional_refiner_dispatch import validate_references, reviewed_options
    _, receipt = authorization(binding)
    matches = [row for row in validate_references(receipt.get('optional_refiner_admissions', []))
               if row['selection'] == chosen]
    if len(matches) != 1:
        raise ValueError('Choose the exact reviewed optional selection/window; one policy is required')
    policy = SessionPolicy(**matches[0]['policy'])
    policy.validate()
    if policy.developer_soak or policy.maximum_session_seconds > 300:
        raise ValueError('Optional GUI requires a reviewed ordinary policy of at most 300 seconds')
    reviewed_options(binding, selection, policy)
    return policy


def gui_policy_summary(policy):
    policy.validate()
    return ('Source %d s; load %d s; drain %d s; backlog %d s; cleanup %d s.'
            % (policy.maximum_session_seconds, policy.model_load_seconds,
               policy.max_drain_seconds, policy.max_backlog_seconds, policy.cleanup_seconds))


def laboratory_show(manager):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from runtime_ui import ScrollPage, SpatialPanel, history_label
    root = tk.Tk()
    root.title('Just Peachy - runtime v29 candidate')
    root.geometry('480x800+0+0')
    fullscreen_requested = False
    def mapped(event):
        nonlocal fullscreen_requested
        if event.widget is root and not fullscreen_requested:
            fullscreen_requested = True
            # Request fullscreen after the window manager has mapped the
            # client; this avoids the retained desktop top-bar clipping.
            root.after_idle(lambda: root.attributes('-fullscreen', True))
    root.bind('<Map>', mapped, add='+')
    root.configure(bg='#142029')
    state = dict(history_cursor=None, pending_exit=False, last_render=None, current_id=None,
                 idle_since=time.monotonic())
    idle_timeout = 300
    if manager.unit_ownership is not None:
        idle_timeout = strict(manager.unit_ownership.read_bytes()).get('idle_timeout_seconds', 300)
        if type(idle_timeout) not in (int, float) or not 1 <= idle_timeout <= 1800:
            raise ValueError('Finite desktop idle timeout required')
    def desktop_activity(event):
        state['idle_since'] = time.monotonic()
    root.bind_all('<ButtonPress>', desktop_activity, add='+')
    root.bind_all('<KeyPress>', desktop_activity, add='+')
    caption_view = CaptionView(manager.store)
    header = ttk.Frame(root, padding=12); header.pack(fill='x')
    ttk.Label(header, text='Just Peachy', font=('Sans', 21, 'bold')).pack(side='left')
    def exit_desktop():
        try:
            manager.close()
        except RuntimeError as exc:
            state['pending_exit'] = True; status.set(str(exc)); return
        root.destroy()
    ttk.Button(header, text='Exit to desktop', command=exit_desktop).pack(side='right')
    notebook = ttk.Notebook(root); notebook.pack(fill='both', expand=True, padx=8, pady=8)
    launch_page=ScrollPage(notebook);notebook.add(launch_page.frame,text='Launch');control=launch_page.body
    history = ttk.Frame(notebook, padding=8); notebook.add(history, text='Recordings')
    developer_page=ScrollPage(notebook);notebook.add(developer_page.frame,text='Developer');advanced=developer_page.body
    diarizer = tk.StringVar(value='pyannote')
    encoder = tk.StringVar(value='redimnet')
    source = tk.StringVar(value='live')
    geometry = tk.StringVar(value='current_delayed')
    experimental = tk.BooleanVar(value=False)
    provisional = tk.BooleanVar(value=False)
    optional_refiner = tk.BooleanVar(value=False)
    embedding_schedule = tk.StringVar(value='continuous')
    embedding_refresh = tk.StringVar(value='2.0')
    speaker_attribution = tk.StringVar(value='retained')
    revision_window = tk.StringVar(value='30')
    policy_summary = tk.StringVar(value=gui_policy_summary(SessionPolicy()))
    saved = tk.StringVar()
    saved_session = tk.StringVar()
    selection_widgets={}
    for label, variable, values in (
        ('Diarizer', diarizer, ('pyannote', 'nemotron')),
        ('Speaker embedding', encoder, ('redimnet', 'titanet', 'anonymous')),
        ('Input', source, ('live', 'saved')),
        ('Nemotron preset', geometry, tuple(r['id'] for r in catalog()))):
        ttk.Label(control, text=label).pack(anchor='w')
        widget=ttk.Combobox(control, textvariable=variable, values=values, state='readonly', height=12)
        widget.pack(fill='x', pady=(0, 7));selection_widgets[label]=widget
    ttk.Checkbutton(control, text='Enable experimental configurations', variable=experimental).pack(anchor='w')
    ttk.Label(control, text='Microphone off until Start. Maximum 5 minutes.\nChoose whether to keep audio after Stop.', wraplength=430).pack(anchor='w', pady=8)
    ttk.Label(control, textvariable=policy_summary, wraplength=430).pack(anchor='w')
    def choose_wav():
        path = filedialog.askopenfilename(filetypes=[('Processed replay WAV', '*.wav')])
        if path:
            saved.set(path); saved_session.set(''); source.set('saved')
    ttk.Button(control, text='Choose saved WAV...', command=choose_wav).pack(fill='x')
    ttk.Label(control, textvariable=saved, wraplength=420).pack(fill='x')
    buttons = ttk.Frame(control); buttons.pack(fill='x', pady=8)
    status = tk.StringVar(value='Idle. Native qualification pending for the new iteration.')
    def start():
        if source.get() == 'live' and not messagebox.askokcancel('Temporary audio', 'Capture audio to temporary storage for this test? After Stop you can save or discard it.'):
            return
        try:
            selection = RuntimeSelection(diarizer.get(), encoder.get(), source.get(),
                geometry.get() if diarizer.get() == 'nemotron' else None, experimental.get(), provisional.get(),
                embedding_schedule=embedding_schedule.get(), embedding_refresh_seconds=float(embedding_refresh.get()),
                speaker_attribution=speaker_attribution.get(), revision_window_seconds=int(revision_window.get()),
                optional_d1_refiner=optional_refiner.get())
            policy = gui_session_policy(manager.binding, selection)
            policy_summary.set(gui_policy_summary(policy))
            manager.start(selection, policy, saved.get() if source.get()=='saved' and not saved_session.get() else None,
                          saved_session_id=(saved_session.get() or None) if source.get()=='saved' else None)
            state['last_render'] = None; state['current_id'] = None
            status.set('Starting selected models. Capture begins after initialization.')
        except Exception as exc:
            messagebox.showerror('Unable to start', str(exc))
    ttk.Button(buttons, text='Start', command=start).pack(side='left', expand=True, fill='x')
    ttk.Button(buttons, text='Stop', command=manager.stop).pack(side='left', expand=True, fill='x')
    ttk.Label(control, textvariable=status, wraplength=425).pack(fill='x', pady=6)
    captions = tk.Text(control, height=7, wrap='word', font=('Sans', 14), state='disabled')
    captions.pack(fill='both', expand=True)
    retain = ttk.Frame(control); retain.pack(fill='x', pady=8)
    def disposition(keep, include_raw=False):
        identifier = state['current_id']
        try:
            if manager.process is not None or not identifier:
                raise RuntimeError('Wait for Stop, drain and process closure')
            if keep:
                manager.store.keep(identifier, include_raw=include_raw)
            else:
                manager.store.discard(identifier)
            status.set(('Raw and processed audio saved.' if include_raw else 'Processed audio saved.') if keep else 'Temporary audio discarded.')
            refresh_history()
        except Exception as exc:
            messagebox.showerror('Recording', str(exc))
    ttk.Button(retain, text='Save processed', command=lambda: disposition(True)).pack(side='left', expand=True, fill='x')
    save_raw = ttk.Button(retain, text='Save raw + processed', state='disabled', command=lambda: disposition(True, True))
    save_raw.pack(side='left', expand=True, fill='x')
    ttk.Button(retain, text='Discard audio', command=lambda: disposition(False)).pack(side='left', expand=True, fill='x')
    raw_status = tk.StringVar(value='Raw is unavailable until this adapter passes native qualification.')
    ttk.Label(control, textvariable=raw_status, wraplength=425).pack(anchor='w')
    spatial_panel=SpatialPanel(control,manager)
    history_rows=ttk.Frame(history);history_rows.pack(fill='both',expand=True)
    tree = ttk.Treeview(history_rows, columns=('date', 'state'), show='headings', selectmode='extended', height=14)
    tree.heading('date', text='Recording'); tree.heading('state', text='State')
    tree.column('date', width=275); tree.column('state', width=120)
    history_scroll = ttk.Scrollbar(history_rows, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=history_scroll.set)
    history_scroll.pack(side='right', fill='y')
    tree.pack(side='left',fill='both',expand=True)
    def refresh_history(next_page=False):
        if not next_page:
            state['history_cursor'] = None
        page = manager.store.history(limit=25, before=state['history_cursor'])
        tree.delete(*tree.get_children())
        for row in page['items']:
            identifier = row.get('session_id') or row.get('id')
            tree.insert('', 'end', iid=identifier, values=(history_label(row), row.get('status')))
        state['history_cursor'] = page['next_cursor']
    def selected_one():
        items = tree.selection()
        if len(items) != 1:
            raise ValueError('Select one recording')
        return items[0]
    def history_action(action):
        try:
            identifier = selected_one() if action != 'export' else None
            if action == 'open':
                state['current_id'] = identifier
                caption_view.refresh(identifier)
                rows = caption_view.rows
                captions.configure(state='normal'); captions.delete('1.0', 'end')
                captions.insert('end', '\n'.join(str(r.get('speaker') or 'Unknown')+': '+r['text'] for r in rows))
                captions.configure(state='disabled'); notebook.select(launch_page.frame)
            elif action == 'replay':
                saved_session.set(identifier); saved.set('Complete recording: '+identifier)
                source.set('saved'); notebook.select(launch_page.frame); start()
            elif action == 'delete':
                if manager.export_task is not None:
                    raise RuntimeError('Wait for the selected recording export to close before deletion')
                if messagebox.askyesno('Delete recording', 'Permanently delete only the selected recording?'):
                    manager.store.delete(identifier, confirm=True); refresh_history()
            elif action == 'export':
                destination = filedialog.asksaveasfilename(defaultextension='.zip', filetypes=[('Recording export', '*.zip')])
                if destination:
                    manager.export_recordings(list(tree.selection()), Path(destination))
                    status.set('Exporting selected recordings. The original recordings are retained.')
        except Exception as exc:
            messagebox.showerror('Recordings', str(exc))
    for text, command in [('Refresh', refresh_history), ('Older', lambda: refresh_history(True)),
                          ('Open', lambda: history_action('open')), ('Export', lambda: history_action('export')),
                          ('Replay recording', lambda: history_action('replay')),
                          ('Delete selected', lambda: history_action('delete'))]:
        ttk.Button(history, text=text, command=command).pack(fill='x', pady=2)
    ttk.Checkbutton(advanced, text='Provisional/correction: native admission pending', variable=provisional, state='disabled').pack(anchor='w')
    optional_button=ttk.Checkbutton(advanced, text='Optional anonymous CurrentDelayed refiner:\ncombined native admission pending',
                    variable=optional_refiner,state='disabled')
    optional_button.pack(anchor='w')
    optional_status=tk.StringVar(value='Combined native admission pending')
    ttk.Label(advanced,textvariable=optional_status,wraplength=410).pack(anchor='w')
    ttk.Label(advanced, text='Named speaker embedding schedule (experimental Nemotron only)',wraplength=410).pack(anchor='w')
    ttk.Combobox(advanced, textvariable=embedding_schedule, values=('continuous', 'sparse_clean_turn'), state='readonly').pack(fill='x')
    ttk.Label(advanced, text='Sparse refresh interval in seconds (0.5-120)').pack(anchor='w')
    ttk.Entry(advanced, textvariable=embedding_refresh).pack(fill='x')
    ttk.Label(advanced, text='Speaker attribution (late labels: experimental Nemotron)',wraplength=410).pack(anchor='w')
    ttk.Combobox(advanced, textvariable=speaker_attribution, values=('retained', 'single_d1_late_labels'), state='readonly').pack(fill='x')
    ttk.Label(advanced, text='Label revision window in seconds (1-300)').pack(anchor='w')
    revision_entry=ttk.Entry(advanced, textvariable=revision_window)
    revision_entry.pack(fill='x')
    ttk.Label(advanced, text='For optional Pyannote, enter the exact reviewed revision window before checking the refiner. The accepted source/drain/backlog policy is shown explicitly.', wraplength=410).pack(anchor='w')
    updating_controls=[False]
    def update_selection_controls(*unused):
        if updating_controls[0]:return
        updating_controls[0]=True
        try:
            selected=RuntimeSelection(diarizer.get(),encoder.get(),source.get(),
                geometry.get() if diarizer.get()=='nemotron' else None,experimental.get(),provisional.get(),
                embedding_schedule=embedding_schedule.get(),embedding_refresh_seconds=float(embedding_refresh.get()),
                speaker_attribution=speaker_attribution.get(),revision_window_seconds=int(revision_window.get()),
                optional_d1_refiner=True)
            optional_policy=gui_session_policy(manager.binding,selected)
            eligible,reason=True,'Reviewed optional policy: '+gui_policy_summary(optional_policy)
        except (ValueError,TypeError,PermissionError,OSError,KeyError) as error:
            eligible,reason=False,'Optional unavailable: '+str(error)[:180]
        optional_button.configure(state='normal' if eligible else 'disabled')
        optional_button.configure(text='Optional anonymous CurrentDelayed refiner:\n'+('reviewed combined admission available' if eligible else 'combined native admission pending'))
        optional_status.set(reason)
        if not eligible:optional_refiner.set(False)
        policy_summary.set(gui_policy_summary(optional_policy if eligible and optional_refiner.get() else SessionPolicy()))
        states=selection_control_states(diarizer.get(),speaker_attribution.get(),optional_refiner.get(),provisional.get())
        selection_widgets['Nemotron preset'].configure(state=states['geometry'])
        if states['geometry']=='disabled':geometry.set('')
        elif not geometry.get():geometry.set('current_delayed')
        if diarizer.get()=='pyannote' and experimental.get():
            states['revision']='normal'
        revision_entry.configure(state=states['revision'])
        updating_controls[0]=False
    for variable in (diarizer,encoder,source,experimental,speaker_attribution,optional_refiner,provisional,embedding_schedule,embedding_refresh,revision_window):
        variable.trace_add('write',update_selection_controls)
    update_selection_controls()
    ttk.Label(advanced, text='A second diarizer is not admitted without measured CPU/RAM headroom. The fast path remains available; refinement state is reported explicitly.\n\nThe 60+ minute soak uses the command-line developer policy and a finite storage reservation.', wraplength=420).pack(anchor='w', pady=10)
    diagnostic = tk.Text(advanced, height=18, wrap='word', state='disabled'); diagnostic.pack(fill='both', expand=True)
    last_live_render=[None]
    def tick():
        try:
            result = manager.poll()
            export_result = manager.poll_export()
            if export_result:
                status.set('Selected recordings exported and verified.' if export_result['status'] == 'EXPORTED'
                           else str(export_result.get('error', 'Selected recording export failed.')))
            if manager.export_task is not None:
                state['idle_since'] = time.monotonic()
            if manager.process is not None:
                live=dict(health=manager.latest_health,last_diagnostic=manager.latest_diagnostic)
                text=encoded(live).decode()
                if text!=last_live_render[0]:
                    diagnostic.configure(state='normal');diagnostic.delete('1.0','end')
                    diagnostic.insert('end',text);diagnostic.configure(state='disabled')
                    last_live_render[0]=text
            if manager.process is not None or result and state['last_render'] != result:
                state['idle_since'] = time.monotonic()
            elif time.monotonic()-state['idle_since'] >= idle_timeout:
                exit_desktop(); return
            identifier = manager.active_session_id()
            if identifier and manager.process is not None:
                state['current_id'] = identifier
            if result and state['last_render'] != result:
                state['last_render'] = result
                if identifier:
                    state['current_id'] = identifier
                status.set('Stopped. Choose Save processed or Discard audio.' if result['returncode'] == 0 else 'Session failed; evidence preserved. See Developer diagnostics.')
                diagnostic.configure(state='normal'); diagnostic.delete('1.0', 'end')
                diagnostic.insert('end', encoded(result).decode()); diagnostic.configure(state='disabled')
                refresh_history()
            display_id = identifier if manager.process else state['current_id']
            if display_id:
                recording = manager.store.read(display_id)
                raw_available = recording['spec']['mode'] == 'raw_processed' and recording['spec']['raw']['qualification'].get('qualified') is True
                save_raw.configure(state='normal' if raw_available and manager.process is None and recording['status'] in ('stopped', 'kept') else 'disabled')
                raw_status.set('Qualified 4-microphone PCM32 at 16 kHz is temporarily spooled.' if raw_available else 'Raw unavailable for this recording; processed audio only.')
            if display_id and caption_view.refresh(display_id):
                rows = caption_view.rows
                captions.configure(state='normal'); captions.delete('1.0', 'end')
                captions.insert('end', '\n'.join(str(r.get('speaker') or 'Unknown')+': '+r['text'] for r in rows))
                captions.configure(state='disabled')
            if state['pending_exit'] and manager.process is None:
                exit_desktop(); return
        except Exception as exc:
            status.set(str(exc))
        root.after(500, tick)
    root.protocol('WM_DELETE_WINDOW', exit_desktop)
    def spatial_tick():
        visible=notebook.select()==str(launch_page.frame) and spatial_panel.visible()
        manager.show_spatial(visible)
        spatial_panel.update(manager.latest_spatial if visible else None,
                             live=manager.process is not None and manager.request['selection']['input_source']=='live')
        root.after(200,spatial_tick)
    spatial_tick()
    refresh_history(); tick(); root.mainloop()


def show(manager):
    from classic_frontend import show as portrait_show
    return portrait_show(manager)


def startup_recovery_dialog(error, retry_factory):
    """Keep startup failures visible with capture disabled and explicit Retry/Exit.

    No SQLite, recording, gallery, or diagnostic-file writes occur in this UI.
    A retry constructs the normal Manager in a thread; models/capture remain off.
    """
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('Just Peachy · storage recovery')
    root.geometry('480x800')
    frame = ttk.Frame(root,padding=20)
    frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Just Peachy needs recovery',font=('Arial',18,'bold'),wraplength=430).pack(anchor='w',pady=(0,16))
    ttk.Label(frame,text='Capture is disabled. Existing recordings and enrollments are preserved.',wraplength=430).pack(anchor='w',pady=(0,16))
    status = tk.StringVar()
    ttk.Label(frame,textvariable=status,wraplength=430,justify='left').pack(anchor='w',fill='x',pady=(0,20))
    state = dict(thread=None,result=None,error=error,exit=False)

    def display(failure):
        facts = getattr(failure,'storage_diagnostic',None) or error_facts(failure,operation='launcher initialization')
        print(encoded(dict(startup_recovery=True,capture_enabled=False,error=facts)).decode(),file=sys.stderr,flush=True)
        code = getattr(failure,'sqlite_errorcode',None)
        name = getattr(failure,'sqlite_errorname',None)
        detail = type(failure).__name__+': '+str(failure)[:700]
        if code is not None or name is not None:
            detail += '\nSQLite code: %s (%s)' % (code,name)
        if facts.get('database'):
            detail += '\nDatabase: '+facts['database']
        detail += '\n\nCheck storage, permissions and the owned service log, then choose Retry. An interrupted explicit Discard will resume safely.'
        status.set(detail)

    def finish_retry():
        thread = state['thread']
        if thread is not None and thread.is_alive():
            root.after(50,finish_retry)
            return
        if thread is not None:
            thread.join()
            state['thread'] = None
        if state['exit']:
            if state['result'] is not None:
                try:
                    state['result'].close()
                except Exception as failure:
                    print(encoded(error_facts(failure,operation='recovery Exit cleanup')).decode(),file=sys.stderr,flush=True)
                state['result'] = None
            root.quit()
        elif state['result'] is not None:
            root.quit()
        else:
            display(state['error'])
            retry.configure(state='normal')

    def retry_start():
        if state['thread'] is not None:
            return
        retry.configure(state='disabled')
        status.set('Checking storage and completing explicitly requested cleanup. Capture remains disabled.')
        def attempt():
            try:
                state['result'] = retry_factory()
            except Exception as failure:
                state['error'] = failure
        state['thread'] = threading.Thread(target=attempt,name='storage-startup-retry',daemon=False)
        state['thread'].start()
        root.after(50,finish_retry)

    def exit_recovery():
        state['exit'] = True
        retry.configure(state='disabled')
        if state['thread'] is not None:
            status.set('Closing the owned storage check before Exit. Capture remains disabled.')
        else:
            root.quit()

    retry = ttk.Button(frame,text='Retry',command=retry_start)
    retry.pack(fill='x',pady=8,ipady=10)
    ttk.Button(frame,text='Exit',command=exit_recovery).pack(fill='x',pady=8,ipady=10)
    root.protocol('WM_DELETE_WINDOW',exit_recovery)
    display(error)
    try:
        root.mainloop()
    finally:
        root.destroy()
    return state['result']


def initialize_manager(args):
    def create():
        return Manager(args.binding,args.data_root,args.unit,unit_ownership=args.unit_ownership)
    try:
        return create()
    except Exception as error:
        if args.headless:
            print(encoded(error_facts(error,operation='headless launcher initialization')).decode(),file=sys.stderr,flush=True)
            raise
        try:
            return startup_recovery_dialog(error,create)
        except Exception as display_error:
            error.add_note('Startup recovery display also failed: '+repr(display_error))
            print(encoded(error_facts(error,operation='launcher recovery display')).decode(),file=sys.stderr,flush=True)
            raise error


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binding', type=Path, required=True)
    ap.add_argument('--data-root', type=Path, required=True)
    ap.add_argument('--unit', required=True)
    ap.add_argument('--unit-ownership', type=Path)
    ap.add_argument('--list-profiles', action='store_true')
    ap.add_argument('--headless', action='store_true')
    ap.add_argument('--request-stop', action='store_true')
    ap.add_argument('--input-source', choices=('live', 'saved'), default='live')
    ap.add_argument('--saved-path', type=Path)
    ap.add_argument('--saved-session-id')
    ap.add_argument('--saved-store-root', type=Path)
    ap.add_argument('--diarizer', choices=('pyannote', 'nemotron'), default='pyannote')
    ap.add_argument('--embedding', choices=('redimnet', 'titanet', 'anonymous'), default='redimnet')
    ap.add_argument('--nemotron-profile')
    ap.add_argument('--allow-experimental', action='store_true')
    ap.add_argument('--maximum-session-seconds', type=int, default=300)
    ap.add_argument('--developer-soak', action='store_true')
    ap.add_argument('--repeat-input-seconds',type=int,help='Explicit developer saved-WAV repetition; must equal >=3600s policy')
    ap.add_argument('--max-drain-seconds', type=int, default=120)
    ap.add_argument('--max-backlog-seconds', type=int, default=120)
    ap.add_argument('--stop-after-seconds', type=float)
    ap.add_argument('--keep-processed', action='store_true')
    ap.add_argument('--embedding-schedule', choices=('continuous', 'sparse_clean_turn'), default='continuous')
    ap.add_argument('--embedding-refresh-seconds', type=float, default=2.0)
    ap.add_argument('--speaker-attribution', choices=('retained', 'single_d1_late_labels'), default='retained')
    ap.add_argument('--revision-window-seconds', type=int, default=30)
    ap.add_argument('--optional-d1-refiner',action='store_true',help='Requires exact reviewed combined admission; never enables a first trial')
    args = ap.parse_args()
    if args.list_profiles:
        print(encoded(catalog()).decode()); return
    if sys.platform != 'linux':
        raise RuntimeError('Launch the tablet UI on the Pi; host tests never take over the PC display')
    os.sched_setaffinity(0, {3})
    if args.request_stop:
        print(encoded(dict(stop_requested=request_current_stop(args.data_root))).decode())
        return
    if args.unit_ownership is None:
        raise RuntimeError('Use the owned native scope wrapper; --unit-ownership is required')
    manager = initialize_manager(args)
    if manager is None:
        return 1  # User exited a visible recovery screen; no capture occurred.
    if args.headless:
        selection = RuntimeSelection(args.diarizer, args.embedding, args.input_source,
            args.nemotron_profile if args.diarizer == 'nemotron' else None, args.allow_experimental,
            embedding_schedule=args.embedding_schedule, embedding_refresh_seconds=args.embedding_refresh_seconds,
            speaker_attribution=args.speaker_attribution, revision_window_seconds=args.revision_window_seconds,
            optional_d1_refiner=args.optional_d1_refiner)
        policy = SessionPolicy(args.maximum_session_seconds, args.developer_soak,
            max_drain_seconds=args.max_drain_seconds, max_backlog_seconds=args.max_backlog_seconds)
        closure = run_headless(manager, selection, policy, saved_path=args.saved_path,
            saved_session_id=args.saved_session_id, saved_store_root=args.saved_store_root,
            stop_after_seconds=args.stop_after_seconds, keep_processed=args.keep_processed,
            repeat_input_seconds=args.repeat_input_seconds)
        print(encoded(closure).decode())
        return 0 if closure['returncode'] == 0 and not (closure.get('result') or {}).get('failure') else 1
    if args.repeat_input_seconds is not None or args.optional_d1_refiner:
        raise ValueError('CLI repeat/optional selections are headless only; use the actual GUI controls otherwise')
    show(manager)


if __name__ == '__main__':
    raise SystemExit(main())
