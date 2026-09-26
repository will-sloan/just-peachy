"""Explicit application/source timing integration; README_APPLICATION_DELIVERY.md."""
from pathlib import Path
import threading

from common import audio_only, bind, fingerprint, freeze, load, verify
from application_closure_v2 import validate_clock_join
from paced_child_admission import assert_plain_path
from source_delivery import SourceDelivery, FORMAT, CHUNK, RECORD, check, summarize

TAG = '_n4_source_launch_capture'
POLICY = dict(schema='n4-application-delivery-policy-v1', source='unchanged FileSource',
    observation='source_delivery.SourceDelivery', schedule='unchanged absolute 16 kHz / 320 samples',
    writes='after source and Controller closure, before resource observer closure',
    maximum_seconds=3600, trace_format=FORMAT, timing_correction=False)


class SourceLaunchCapture:
    """One class-level start seam in an isolated, single-cell application child.

    Runtime patching is confined to that child; original source files stay bound
    and unchanged. A wrong or second start is rejected before launching a source.
    Once the one admitted start passes, the original method is called once.
    """
    def __init__(self, controller, job, contract, source_root, *, _types=None, _observer_factory=None):
        audio_only(job); self.controller = controller; self.job = dict(job); self.contract = dict(contract)
        self.test_seams = _types is not None or _observer_factory is not None
        if _types is None:
            from app.pipeline import FileSource
            from app.buffers import MemoryJournal
            self.types = (FileSource, MemoryJournal)
        else:
            self.types = _types
        self.source_root = Path(source_root).resolve()
        self.source_files = [bind(self.source_root/name) for name in ('app/pipeline.py', 'app/buffers.py')]
        for cls, binding in zip(self.types, self.source_files):
            check(Path(cls.__init__.__code__.co_filename).resolve() == Path(binding['path']), 'Loaded source type has different origin')
        self.original_start = self.types[0].__dict__['start']
        check(Path(self.original_start.__code__.co_filename).resolve() == self.source_root/'app/pipeline.py',
              'Loaded FileSource.start has different origin')
        self.factory = _observer_factory or SourceDelivery
        self.observer = None; self.engine = None; self.starts = 0; self.installed = False
        self.ever_installed = False; self.restored = False; self.finished = False; self.errors = []
        self.original_start_raised = False
        def start(source): return self._start(source)
        self.hook = start

    def _error(self, kind):
        if kind not in self.errors and len(self.errors) < 16: self.errors.append(kind)

    def check(self):
        check(not self.errors, 'Application source delivery capture failed: '+','.join(self.errors))
        if self.observer is not None:
            check(not self.observer.errors, 'Source delivery observer failed')

    def install(self):
        cls = self.types[0]; c = self.controller
        check(not self.ever_installed and not self.finished and c.engine is None and not c.closed,
              'Install once on a fresh prepared Controller')
        check(cls.__dict__['start'] is self.original_start and TAG not in vars(cls), 'FileSource.start already changed')
        cls.start = self.hook; setattr(cls, TAG, self)
        self.installed = self.ever_installed = True

    def _start(self, source):
        self.starts += 1
        try:
            c = self.controller; engine = c.engine; cls, journal_cls = self.types
            check(self.installed and not self.finished and self.starts == 1 and self.observer is None,
                  'Unexpected duplicate source start')
            check(cls.__dict__['start'] is self.hook and getattr(cls, TAG, None) is self, 'Launch hook changed')
            check(threading.current_thread() is c.worker and c.saved_audio_only is True and not c.closed
                  and c.state == 'STARTING' and c.source_kind == 'file' and c.file_offset == 0,
                  'Source start is outside the admitted Controller command')
            check(c.tap == self.job['tap'] and c.mode == self.contract['mode']
                  and Path(c.file_path).resolve() == Path(self.job['audio_path']).resolve()
                  and not c.collect_references and not c.use_references, 'Controller source/mode/adaptation differs')
            check(type(source) is cls and type(engine).__name__ == self.contract['engine']
                  and engine._source is source and getattr(source.callback, '__self__', None) is engine,
                  'Source callback or engine owner differs')
            check(engine.enhancement_route == 'bypass' and engine.enhancement_router is None
                  and type(source.journal) is journal_cls
                  and all(getattr(engine, name) is source.journal for name in ('_input_journal', '_journal', '_identity_journal')),
                  'Actual bypass source journal differs')
            self.engine = engine; self.observer = self.factory(source, self.job)
        except BaseException:
            self._error('source_start_admission_failed'); raise
        try:
            return self.original_start(source)
        except BaseException:
            self.original_start_raised = True; self._error('original_source_start_raised'); raise

    def restore_start(self):
        if self.restored or not self.ever_installed: return
        cls = self.types[0]
        if cls.__dict__['start'] is self.hook:
            cls.start = self.original_start
        else:
            self._error('foreign_start_hook_preserved')
        if getattr(cls, TAG, None) is self:
            delattr(cls, TAG)
        else:
            self._error('foreign_start_owner_preserved')
        self.installed = False; self.restored = True

    def finish(self, output, *, engine):
        """Called after normal Controller/source cleanup. Preserve failed evidence."""
        check(not self.finished, 'Launch capture already finished'); self.restore_start()
        if self.ever_installed and self.types[0].__dict__['start'] is not self.original_start:
            self._error('foreign_start_hook_preserved')
        output = Path(output); check(not output.exists(), 'Fresh source-delivery output required')
        observation = None; trace = None; self.finished = True
        joined = dict(same_retained_engine=engine is not None and engine is self.engine,
            same_source=self.observer is not None and getattr(engine, '_source', None) is self.observer.source,
            same_journal=self.observer is not None and getattr(engine, '_input_journal', None) is self.observer.journal,
            controller_closed=self.controller.closed is True,
            controller_worker_exited=not self.controller.worker.is_alive())
        if self.observer is not None:
            try:
                value, raw = self.observer.close()
                output.mkdir(parents=True, exist_ok=False)
                with (output/'TRACE.bin').open('xb') as stream: stream.write(raw)
                freeze(output/'OBSERVATION.json', value)
                observation = bind(output/'OBSERVATION.json'); trace = bind(output/'TRACE.bin')
                if value['status'] != 'OBSERVED_FULL_SOURCE_DELIVERY_REQUIRES_REVIEW': self._error('source_observation_not_full')
            except BaseException:
                self._error('source_observation_close_failed')
        elif self.ever_installed:
            self._error('no_source_observer_created')
        if not joined['controller_closed'] or not joined['controller_worker_exited']:
            self._error('controller_not_closed')
        if self.ever_installed and not all(joined.values()): self._error('source_owner_join_failed')
        if self.ever_installed and self.starts != 1: self._error('source_start_count_differs')
        status = ('FAILED_APPLICATION_DELIVERY_PRESERVED' if self.errors else
                  'COLLECTED_APPLICATION_DELIVERY_REQUIRES_REVIEW' if self.ever_installed else 'PREPARED_WITHOUT_SOURCE_DELIVERY')
        result = dict(schema='n4-application-delivery-capture-v1', status=status, policy=POLICY,
            job_fingerprint=fingerprint(self.job), contract_fingerprint=fingerprint(self.contract), source_files=self.source_files,
            launch_attempts=self.starts, installed=self.ever_installed, launch_hook_restored=self.restored,
            original_start_raised=self.original_start_raised, owner_join=joined, errors=list(self.errors),
            test_seams_used=self.test_seams, observation=observation, trace=trace,
            model_accuracy_qualified=False, deadline_or_continuity_accepted=False, integrated_N4_cells=0)
        freeze(output/'CAPTURE.json', result)
        return bind(output/'CAPTURE.json')


def validate_delivery(value, raw, launch, observed, clock, job, contract):
    """Only the delivery/clock join; engine/archive acceptance remains separate."""
    audio_only(job); validate_clock_join(observed)
    check(launch['schema'] == 'n4-application-delivery-capture-v1'
          and launch['status'] == 'COLLECTED_APPLICATION_DELIVERY_REQUIRES_REVIEW' and launch['policy'] == POLICY,
          'Capture schema/status/policy differs')
    check(launch['job_fingerprint'] == fingerprint(job) and launch['contract_fingerprint'] == fingerprint(contract)
          and launch['test_seams_used'] is False, 'Capture job/contract or production scope differs')
    check(launch['launch_attempts'] == 1 and launch['installed'] is True and launch['launch_hook_restored'] is True
          and launch['original_start_raised'] is False and launch['errors'] == [], 'Source launch failed or ambiguous')
    check(launch['owner_join'] == dict(same_retained_engine=True, same_source=True, same_journal=True,
          controller_closed=True, controller_worker_exited=True), 'Source launch owner join differs')
    check(value['schema'] == 'n4-source-delivery-v1' and value['status'] == 'OBSERVED_FULL_SOURCE_DELIVERY_REQUIRES_REVIEW'
          and value['test_seams_used'] is False and value['errors'] == {}, 'Observation is failed, partial or a fixture')
    check(value['job_fingerprint'] == fingerprint(job) and value['expected_frames'] == job['frames']
          and value['sample_rate_hz'] == 16000 and value['chunk_samples'] == CHUNK, 'Observed source job differs')
    check(value['trace_format'] == FORMAT and value['trace_bytes'] == len(raw)
          and value['trace_capacity_bytes'] == ((job['frames']+CHUNK-1)//CHUNK)*RECORD.size,
          'Trace encoding/size/capacity differs')
    source = observed['source']; origin = value['source_origin_perf_counter']
    check(observed['job'] == job and observed['engine_class'] == contract['engine']
          and observed['controller_clock'] == clock and origin == clock['source_epoch_monotonic_sec'],
          'Source/consumer origin, job or engine differs')
    check(source['actual_FileSource'] is True and source['start_sample'] == 0
          and Path(source['path']).resolve() == Path(job['audio_path']).resolve()
          and source['thread']['present'] is True and source['thread']['started'] is True and source['thread']['alive'] is False,
          'Retained actual source is absent or unclosed')
    check(source['sent'] == value['source_sent'] == value['journal_committed'] == job['frames']
          and source['journal']['committed_samples'] == job['frames'], 'Source/trace/journal census differs')
    check(value['source_thread_exited'] is True and value['journal_finished'] is True
          and value['journal_had_fatal_error'] is False and value['source_fatal_seen'] is False
          and value['source_start_events'] == 1, 'Source did not close cleanly')
    for key in ('audio_copied_or_transformed', 'source_pacer_changed', 'source_stop_requested_by_observer',
                'actual_application_integration_qualified', 'timing_or_continuity_accepted'):
        check(value[key] is False, 'Unexpected observer behavior or acceptance claim')
    check(value['observer_cost_not_subtracted'] is True, 'Observer overhead correction is not admitted')
    summary = summarize(raw, origin=origin, frames=job['frames'], sent=value['source_sent'], committed=value['journal_committed'])
    check(value['summary'] == summary and value['append_attempts'] == summary['records']
          and summary['complete_source'] is True and summary['failed_appends'] == 0, 'Trace summary or full census differs')
    return dict(status='PASS_APPLICATION_DELIVERY_SOURCE_CLOCK_JOIN_ONLY', source_samples=job['frames'],
        source_origin_perf_counter=origin, summary=summary, independent_trace_parsed=True,
        engine_archive_closure_must_pass_separately=True, model_accuracy_qualified=False,
        source_to_widget_latency_qualified=False, deadline_or_continuity_accepted=False, integrated_N4_cells=0)


def review_files(output, job, contract, source_files):
    """Read only the fixed files within one private application output directory."""
    output = assert_plain_path(output, Path('G:/Just_Peachy_N1/20260924_campaign/local/n4'))
    folder = output/'delivery'
    def bounded(path, limit):
        path = assert_plain_path(path, output)
        check(path.is_file() and path.stat().st_size <= limit, 'Delivery evidence exceeds file bound')
        return bind(path)
    capture = bounded(folder/'CAPTURE.json', 128*1024); launch = load(capture['path'])
    check(launch['source_files'] == source_files and len(source_files) == 2,
          'Capture source files differ from caller-bound application source')
    expected = [bounded(folder/'OBSERVATION.json', 128*1024), bounded(folder/'TRACE.bin', 5220000)]
    check([launch['observation'], launch['trace']] == expected, 'Capture points outside this cell')
    check(expected[1]['bytes'] <= 5220000 and expected[0]['bytes'] < 128*1024, 'Delivery files exceed bounds')
    closures = [bounded(output/'ENGINE_CLOSURE.json', 1024**2), bounded(output/'SOURCE_CLOCK.json', 1024**2)]
    inputs = [capture, *expected, *closures, *launch['source_files']]
    for b in inputs: verify(b)
    result = validate_delivery(load(expected[0]['path']), Path(expected[1]['path']).read_bytes(), launch,
                               load(closures[0]['path']), load(closures[1]['path']), job, contract)
    for b in inputs: verify(b)
    return dict(result, evidence=inputs)
