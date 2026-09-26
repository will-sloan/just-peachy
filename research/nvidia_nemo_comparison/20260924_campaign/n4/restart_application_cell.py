"""Bounded same-Controller two-session lifecycle; README_RESTART_APPLICATION.md."""
from pathlib import Path
import time

from common import bind, freeze, load
from paced_application_cell_v2 import ApplicationCell as PreparedCell
from restart_source_capture import RestartSourceCapture, validate_delivery
from restart_session_closure import capture_engine
from restart_archive import capture_archive, validate_complete
from source_delivery import CHUNK, check

POLICY = dict(schema='n4-restart-application-policy-v1', sessions=2,
    first='positive mid-file stop and complete delivered-prefix drain',
    second='same full saved file from sample zero through EOF and release',
    same_controller_ui_worker_models=True, old_caption_history='retained; partition by native session',
    maximum_source_seconds=120, maximum_pair_seconds=900,
    source_schedule_unchanged=True, timing_correction=False)


class RestartApplicationCell(PreparedCell):
    """Internal application primitive; requires the exclusive admitted launcher.

    PreparedCell supplies the identical source/runtime/roster/private-Tk setup.
    Two sessions retain its Controller/UI/model store and resource observer.
    Actual observers are fresh per epoch; all persisted input jobs stay full.
    The inherited single-source run method is disabled for this variant.
    """
    def __init__(self, output, job, contract):
        super().__init__(output, job, contract)
        self.source_root = None; self.shared = None; self.sessions = []; self.retained = []
        self.session_folder = None; self.viewport_path = None
        self.admission_check = None; self.next_guard = 0.; self.deadline = None
        self.initial_epoch = None; self.pair_proof = None

    def prepare(self, **kwargs):
        super().prepare(**kwargs)
        check(self.job['frames'] <= 16000*POLICY['maximum_source_seconds'], 'Use a bounded saved-file restart job')
        self.source_root = Path(kwargs['source']); self.initial_epoch = self.c.epoch
        self.shared = (self.c, self.ui, self.root, self.c.worker, self.c.models)
        self._arm(0)
        freeze(self.output/'RESTART_PREPARED.json', dict(status='PREPARED_RESTART_PAIR_NO_SOURCE_STARTED',
            policy=POLICY, job=self.job, contract=self.contract, initial_epoch=self.initial_epoch,
            inherited_preparation=bind(self.output/'PREPARED.json'), resources_owner=self.resources.owner,
            actual_restart_qualified=False, integrated_N4_cells=0))

    def _arm(self, index):
        check(index == len(self.sessions) and index in (0, 1), 'Exactly two ordered sessions required')
        self._shared_check()
        check(self.c.engine is None and self.c.consumer is None and self.c.commands.unfinished_tasks == 0,
              'Previous session owners must be released before arming')
        self.session_folder = self.output/'sessions'/f'{index+1:02d}'
        self.session_folder.mkdir(parents=True, exist_ok=False)
        if index:
            from paced_adapters_v3 import ConsumerSourceClock
            from paced_viewport import PacedViewport
            check(not self.clock.installed and self.viewport.closed, 'Prior observers must be closed')
            self.clock = ConsumerSourceClock(self.job).install(self.c)
            self.viewport = PacedViewport(self.ui, self.clock, self.session_folder/'viewport')
        self.viewport_path = self.output/'viewport' if index == 0 else self.session_folder/'viewport'
        self.delivery = RestartSourceCapture(self.c, self.job, self.contract, self.source_root,
            intent='mid_file_stop' if index == 0 else 'completed_release')
        self.engine = self.consumer = None

    def _shared_check(self):
        check(self.shared is not None, 'Restart cell is not prepared')
        c, ui, root, worker, models = self.shared
        check(self.c is c and self.ui is ui and self.root is root and c.worker is worker and c.models is models,
              'Controller/UI/worker/model store changed between sessions')
        check(ui.controller is c and ui.root is root and ui._closed is False, 'UI no longer owns the admitted Controller/root')
        check(not c.closed and worker.is_alive() and c.saved_audio_only and not c.collect_references
              and not c.use_references and c.tap == self.job['tap'] and c.mode == self.contract['mode'],
              'Shared Controller is no longer admitted')

    def _gate(self, force=False):
        self._shared_check(); self.check()
        now = time.perf_counter()
        check(self.deadline is not None and now < self.deadline, 'Restart pair deadline reached')
        if force or now >= self.next_guard:
            self.admission_check(self.job, self.contract); self.next_guard = now+1.

    def _pump(self):
        self._gate(); self.root.update(); self.check(); time.sleep(.01)

    def _wait(self, predicate, seconds):
        end = min(self.deadline, time.perf_counter()+seconds)
        while not predicate():
            check(time.perf_counter() < end, 'Restart lifecycle transition timed out')
            self._pump()
        self._gate()

    def _start_session(self, index):
        self._gate(True); self.delivery.install()
        try:
            self.c.start_file(self.job['audio_path'])
            self._wait(lambda:self.c.commands.unfinished_tasks == 0, 180)
        finally:
            self.engine = self.c.engine or self.delivery.engine
            self.consumer = self.c.consumer
        check(self.engine is not None and self.consumer is not None, 'Actual session owners missing')
        check(self.c.epoch == self.initial_epoch+index+1 and self.c.file_offset == 0,
              'Restart did not create the next epoch at sample zero')
        source = self.engine._source
        check(source.start_sample == 0 and self.delivery.engine is self.engine, 'Restart source owner/offset differs')
        if self.retained:
            old = self.retained[0]
            check(self.engine is not old['engine'] and source is not old['source']
                  and source.journal is not old['journal'] and self.consumer is not old['consumer']
                  and self.clock is not old['clock'] and self.viewport is not old['viewport'],
                  'Restart reused prior session state')
            check(str(self.engine.session_dir) != old['session'], 'Restart reused the native session path')
        (self.engine.session_dir/'PINNED').touch(exist_ok=False)
        if index == 0:self.resources.mark('running')

    def _release_session(self, index):
        self._gate(True); self.delivery.request_stop()
        self._wait(lambda:self.c.commands.unfinished_tasks == 0, 180)
        check(self.c.engine is None and self.c.consumer is None and self.c.state == 'STOPPED',
              'Controller retained previous session owners')
        settle = time.perf_counter()+1.4
        while time.perf_counter() < settle:self._pump()
        self.ui.poll(); self.root.update(); self._gate()
        folder = self.session_folder; native = str(self.engine.session_dir)
        capture = self.delivery.finish(folder/'delivery', engine=self.engine)
        captured = load(capture['path']); value = load(captured['observation']['path'])
        raw = Path(captured['trace']['path']).read_bytes()
        delivery_join = validate_delivery(value, raw, captured, self.job, self.contract)
        observed = capture_engine(self.engine, self.consumer, self.clock, self.job, self.delivery, capture)
        freeze(folder/'ENGINE_CLOSURE.json', observed)
        archive = capture_archive(self.c, self.engine); freeze(folder/'ARCHIVE_INTEGRITY.json', archive)
        closure = validate_complete(observed, archive)
        freeze(folder/'CONTROLLER_SNAPSHOT.json', self.c.snapshot())
        freeze(folder/'SOURCE_CLOCK.json', self.clock.snapshot())
        viewport = self.viewport.close(); check(viewport['failure'] is None, 'Viewport observer failed')
        self.clock.detach()
        scope = dict(schema='n4-restart-viewport-session-scope-v1', native_session=native,
            publication_session=Path(native).name, controller_epoch=self.c.epoch,
            prior_native_sessions=[r['native_session'] for r in self.sessions],
            prior_caption_history_retained=True,
            all_rows_have_current_source_clock=False, source_to_widget_latency_qualified=False,
            instruction='Match caption keys/publication sessions before interpreting each row; old history is not new-session output')
        freeze(folder/'VIEWPORT_SCOPE.json', scope)
        row = dict(status='COLLECTED_RESTART_SESSION_REQUIRES_REVIEW', index=index, intent=self.delivery.intent,
            native_session=native, controller_epoch=self.c.epoch, job=self.job,
            delivery_capture=capture, delivery_join=delivery_join,
            engine_closure=bind(folder/'ENGINE_CLOSURE.json'), archive=bind(folder/'ARCHIVE_INTEGRITY.json'), closure=closure,
            source_clock=bind(folder/'SOURCE_CLOCK.json'), viewport=bind(self.viewport_path/'RESULT.json'),
            viewport_scope=bind(folder/'VIEWPORT_SCOPE.json'), controller_snapshot=bind(folder/'CONTROLLER_SNAPSHOT.json'),
            completed_monotonic_sec=time.perf_counter(), actual_restart_qualified=False, integrated_N4_cells=0)
        freeze(folder/'RESULT.json', row)
        self.retained.append(dict(engine=self.engine, source=self.engine._source, journal=self.engine._source.journal,
            consumer=self.consumer, clock=self.clock, viewport=self.viewport, session=native, capture=self.delivery))
        self.sessions.append(dict(row, receipt=bind(folder/'RESULT.json')))

    def run_source(self, **kwargs):
        raise ValueError('Use the explicitly admitted run_pair with a planned stop threshold')

    def run_pair(self, *, admission_check, stop_after_samples):
        check(self.c is not None and self.shared is not None and not self.started and not self.closed, 'Fresh prepared pair required')
        check(type(stop_after_samples) is int and stop_after_samples % CHUNK == 0
              and CHUNK <= stop_after_samples <= self.job['frames']-2*CHUNK, 'Bounded pre-EOF stop threshold required')
        self.admission_check = admission_check
        self.deadline = self.began+POLICY['maximum_pair_seconds']; self.next_guard = 0.
        self._gate(True); self.resources.mark('starting'); self.started = True
        try:
            self._start_session(0)
            self._wait(lambda:self.engine._source.sent >= stop_after_samples, 180)
            self._release_session(0)
            self._arm(1); self._start_session(1)
            self._wait(lambda:self.c.state == 'STOPPED' and not self.consumer.is_alive(),
                       min(700,self.job['frames']/16000*25+180))
            self.resources.mark('draining'); self._release_session(1)
            self._shared_check()
            first, second = self.sessions
            origin = second['delivery_join']['source_origin_perf_counter']
            check(origin > first['completed_monotonic_sec'], 'Restart origin precedes first session closure')
            check(first['delivery_join']['delivered_frames'] < self.job['frames']
                  and second['delivery_join']['delivered_frames'] == self.job['frames'], 'Wrong restart source coverage')
            self.pair_proof = dict(schema='n4-same-controller-restart-observation-v1',
                same_controller=True, same_ui=True, same_tk_root=True, same_command_worker=True, same_model_store=True,
                distinct_engines_sources_journals_consumers_clocks_viewports=True,
                consecutive_epochs=[r['controller_epoch'] for r in self.sessions],
                source_start_samples=[0,0], native_sessions=[r['native_session'] for r in self.sessions],
                source_jobs_unchanged=True, second_origin_after_first_release=True,
                initial_epoch=self.initial_epoch, planned_stop_after_samples=stop_after_samples,
                process_owner=self.resources.owner, session_receipts=[r['receipt'] for r in self.sessions],
                controller_still_open=True, actual_restart_qualified=False, integrated_N4_cells=0)
            freeze(self.output/'PAIR_OBSERVATION.json', self.pair_proof)
            self.run_completed = True
        except BaseException as exc:
            self.run_error = repr(exc); raise
        finally:
            if self.delivery is not None:self.delivery.restore_start()

    def close(self):
        if self.closed:return self.result
        errors = []; failure_capture = None
        if self.run_error:errors.append('Restart pair: '+self.run_error)
        if self.started and not self.run_completed:errors.append('Restart pair did not complete')
        if self.errors:errors.append('Tk callback failed')
        if self.c is not None:
            if self.c.error:errors.append('Controller: '+str(self.c.error))
            self.engine = self.engine or self.c.engine; self.consumer = self.consumer or self.c.consumer
            try:
                self.c.close(); self.wait_commands(130,check=False); self.c.worker.join(10)
                check(self.c.closed and not self.c.worker.is_alive(), 'Controller failed to close')
                if self.run_completed:self.resources.mark('closed')
            except Exception as exc:errors.append('Controller cleanup: '+repr(exc))
        if self.delivery is not None:
            try:
                self.delivery.restore_start()
                if isinstance(self.delivery,RestartSourceCapture) and not self.delivery.finished and self.delivery.ever_installed:
                    failure_capture = self.delivery.finish(self.session_folder/'failed-delivery',engine=self.engine)
            except Exception as exc:errors.append('Failed source evidence: '+repr(exc))
        if self.viewport is not None and not self.viewport.closed:
            try:
                viewport=self.viewport.close()
                if viewport['failure'] is not None:errors.append('Viewport: '+str(viewport['failure']))
            except Exception as exc:errors.append('Viewport cleanup: '+repr(exc))
        if self.clock is not None and self.clock.installed:
            try:
                freeze(self.output/'FAILED_OR_PREPARED_SOURCE_CLOCK.json',self.clock.snapshot());self.clock.detach()
            except Exception as exc:errors.append('Clock cleanup: '+repr(exc))
        if self.ui is not None:self.ui._closed=True
        if self.root is not None:
            try:self.root.destroy()
            except Exception as exc:errors.append('Tk cleanup: '+repr(exc))
        resources=self.resources.close()
        if resources['status']!='OBSERVED_HOST_RESOURCES':errors.append('Resources: '+str(resources['error']))
        self.closed=True
        self.result=dict(schema='n4-restart-application-cell-v1',policy=POLICY,
            status='COLLECTED_RESTART_PAIR_CLOSED_REQUIRES_REVIEW' if self.run_completed and len(self.sessions)==2 and not errors else
                   'PREPARED_RESTART_PAIR_ONLY_CLOSED' if not self.started and not errors else 'FAILED_RESTART_PAIR_PRESERVED',
            source_start_requested=self.started,completed_sessions=len(self.sessions),errors=errors,callback_errors=self.errors,
            sessions=[r['receipt'] for r in self.sessions],pair_observation=bind(self.output/'PAIR_OBSERVATION.json') if self.pair_proof else None,
            failure_delivery_capture=failure_capture,resources=bind(self.output/'resources/RESULT.json'),
            controller_closed=self.c.closed if self.c is not None else None,
            controller_worker_exited=not self.c.worker.is_alive() if self.c is not None else None,
            actual_restart_qualified=False,source_to_widget_latency_qualified=False,complete_N4_acceptance=False,integrated_N4_cells=0)
        freeze(self.output/'RESULT.json',self.result);return self.result
