"""One released session in a future same-Controller restart; README_RESTART_SESSION.md.

This internal primitive requires an independently admitted application child.
It preserves the full input job and records a stopped prefix separately.
"""
from pathlib import Path
import threading
import time

from application_delivery import SourceLaunchCapture
from common import audio_only, bind, fingerprint, freeze
from source_delivery import CHUNK, FORMAT, RECORD, check, finite, summarize

INTENTS = ('mid_file_stop', 'completed_release')
POLICY = dict(schema='n4-restart-session-delivery-policy-v1',
    source='unchanged FileSource', observation='source_delivery.SourceDelivery',
    command='Controller.stop once after source start',
    writes='after session release with Controller and command worker retained',
    planned_frames_unchanged=True, timing_correction=False)
JOIN_KEYS = {'same_engine', 'same_source', 'same_journal', 'same_worker', 'same_models',
             'controller_open', 'worker_alive', 'consumer_exited', 'engine_released',
             'consumer_released', 'commands_drained', 'stopped_without_error',
             'source_kind_cleared', 'same_epoch', 'offset_equals_delivered'}


def validate_request(request, job, intent, sent):
    audio_only(job); check(intent in INTENTS, 'Wrong release intent')
    check(isinstance(request, dict) and request.get('intent') == intent, 'Missing explicit stop request')
    check(request.get('returned') is True and request.get('error') is None, 'Stop command did not return')
    check(type(request.get('epoch')) is int and request['epoch'] > 0, 'Missing session epoch')
    count = request.get('source_sent_before')
    check(type(count) is int and type(sent) is int, 'Missing source counts')
    if intent == 'mid_file_stop':
        check(0 < count <= sent < job['frames'], 'Mid-file stop must preserve a positive incomplete prefix')
        check(request.get('state_before') == 'RUNNING' and request.get('source_stop_set_before') is False,
              'Mid-file command was not requested on an active source')
    else:
        check(count == sent == job['frames'] and request.get('state_before') == 'STOPPED',
              'Completed release requires the full source first')
    before, after = request.get('requested_monotonic_sec'), request.get('returned_monotonic_sec')
    check(finite(before) and finite(after) and 0 < before <= after, 'Invalid stop command clocks')


class RestartSourceCapture(SourceLaunchCapture):
    """Retain exact owners, enqueue one public stop, then observe release.

    Neither request_stop nor finish waits, stops a source directly, closes the
    Controller, or restarts it. The caller must pump its admitted private GUI and
    drain the command queue before finish. Exceptions and evidence are preserved.
    """
    def __init__(self, controller, job, contract, source_root, *, intent, **test_seams):
        check(intent in INTENTS, 'Wrong release intent')
        super().__init__(controller, job, contract, source_root, **test_seams)
        self.intent = intent; self.request = None; self.consumer = None
        self.worker = controller.worker; self.models = controller.models
        self.caller = threading.current_thread(); self.epoch = None

    def request_stop(self):
        c = self.controller; engine = self.engine; source = getattr(engine, '_source', None)
        check(threading.current_thread() is self.caller and c.worker is self.worker,
              'Stop must use the admitted caller and command worker')
        check(self.request is None and not self.finished and self.starts == 1 and self.observer is not None,
              'Exactly one stop request after launch required')
        check(c.engine is engine and c.models is self.models and not c.closed and c.worker.is_alive()
              and c.error is None and c.commands.unfinished_tasks == 0, 'Controller is not ready for stop')
        consumer = c.consumer
        check(consumer is not None and c.source_kind == 'file' and c.file_offset == 0,
              'Original source/consumer owner required')
        request = dict(intent=self.intent, epoch=c.epoch, state_before=c.state,
            source_sent_before=source.sent, source_stop_set_before=source.stop_event.is_set(),
            requested_monotonic_sec=time.perf_counter(), returned_monotonic_sec=None,
            returned=False, error=None)
        # Admission uses a separate copy; no successful command is fabricated in evidence.
        validate_request(dict(request, returned=True, returned_monotonic_sec=request['requested_monotonic_sec']),
                         self.job, self.intent, source.sent)
        if self.intent == 'mid_file_stop':
            check(source.thread is not None and source.thread.is_alive() and consumer.is_alive(),
                  'Active producer and consumer required before mid-file stop')
        else:
            check(engine.state == 'COMPLETED' and not source.thread.is_alive() and not consumer.is_alive(),
                  'Completed session owners have not drained')
        self.request = request; self.consumer = consumer; self.epoch = c.epoch
        try:
            c.stop(); self.request['returned'] = True
        except BaseException as exc:
            self.request['error'] = type(exc).__name__; self._error('stop_command_raised'); raise
        finally:
            self.request['returned_monotonic_sec'] = time.perf_counter()

    def finish(self, output, *, engine):
        check(not self.finished, 'Restart capture already finished')
        self.restore_start(); self.finished = True
        c = self.controller; output = Path(output)
        check(not output.exists(), 'Fresh restart-session evidence required')
        if self.ever_installed and self.types[0].__dict__['start'] is not self.original_start:
            self._error('foreign_start_hook_preserved')
        observer = self.observer; source = getattr(engine, '_source', None)
        joined = dict(same_engine=engine is not None and engine is self.engine,
            same_source=observer is not None and source is observer.source,
            same_journal=observer is not None and getattr(engine, '_input_journal', None) is observer.journal,
            same_worker=c.worker is self.worker, same_models=c.models is self.models,
            controller_open=c.closed is False, worker_alive=c.worker.is_alive(),
            consumer_exited=self.consumer is not None and not self.consumer.is_alive(),
            engine_released=c.engine is None, consumer_released=c.consumer is None,
            commands_drained=c.commands.unfinished_tasks == 0,
            stopped_without_error=c.state == 'STOPPED' and c.error is None,
            source_kind_cleared=c.source_kind is None, same_epoch=c.epoch == self.epoch,
            offset_equals_delivered=source is not None and c.file_offset == source.sent)
        if set(joined) != JOIN_KEYS or not all(joined.values()): self._error('session_owner_release_failed')
        observation = trace = None
        if observer is not None:
            try:
                value, raw = observer.close(); output.mkdir(parents=True, exist_ok=False)
                with (output/'TRACE.bin').open('xb') as stream: stream.write(raw)
                freeze(output/'OBSERVATION.json', value)
                observation = bind(output/'OBSERVATION.json'); trace = bind(output/'TRACE.bin')
                validate_request(self.request, self.job, self.intent, value['source_sent'])
                wanted = 'PARTIAL' if self.intent == 'mid_file_stop' else 'FULL'
                check(value['status'] == 'OBSERVED_'+wanted+'_SOURCE_DELIVERY_REQUIRES_REVIEW'
                      and value['source_stop_requested'] is True, 'Wrong stopped source disposition')
            except BaseException:
                self._error('released_source_observation_failed')
        else: self._error('missing_source_observer')
        if self.starts != 1 or not self.ever_installed or not self.restored or self.original_start_raised:
            self._error('launch_not_clean')
        receipt = dict(schema='n4-released-session-delivery-v1', policy=POLICY,
            status='FAILED_RELEASED_SESSION_DELIVERY_PRESERVED' if self.errors else 'COLLECTED_RELEASED_SESSION_DELIVERY_REQUIRES_REVIEW',
            intent=self.intent, job_fingerprint=fingerprint(self.job), contract_fingerprint=fingerprint(self.contract),
            source_files=self.source_files, launch_attempts=self.starts, installed=self.ever_installed,
            launch_hook_restored=self.restored, original_start_raised=self.original_start_raised,
            request=self.request, owner_join=joined, errors=list(self.errors), test_seams_used=self.test_seams,
            observation=observation, trace=trace, controller_closed=c.closed is True,
            same_controller_restart_qualified=False, integrated_N4_cells=0)
        freeze(output/'CAPTURE.json', receipt); return bind(output/'CAPTURE.json')


def validate_delivery(value, raw, capture, job, contract):
    """Review prefix/full-source delivery separately from engine and archive drain."""
    audio_only(job)
    check(capture.get('schema') == 'n4-released-session-delivery-v1' and capture.get('policy') == POLICY
          and capture.get('status') == 'COLLECTED_RELEASED_SESSION_DELIVERY_REQUIRES_REVIEW', 'Wrong release capture')
    check(capture.get('job_fingerprint') == fingerprint(job)
          and capture.get('contract_fingerprint') == fingerprint(contract), 'Source job or contract differs')
    check(capture.get('test_seams_used') is False and value.get('test_seams_used') is False, 'Test seams cannot qualify runtime')
    check(capture.get('installed') is True and capture.get('launch_attempts') == 1
          and capture.get('launch_hook_restored') is True and capture.get('original_start_raised') is False
          and capture.get('errors') == [], 'Launch or stop capture failed')
    check(capture.get('controller_closed') is False and capture.get('same_controller_restart_qualified') is False
          and type(capture.get('integrated_N4_cells')) is int and capture['integrated_N4_cells'] == 0,
          'Release capture has unexpected closure or acceptance claims')
    join = capture.get('owner_join', {})
    check(set(join) == JOIN_KEYS and all(v is True for v in join.values()), 'Session ownership was not released cleanly')
    intent = capture['intent']; sent = value.get('source_sent')
    validate_request(capture.get('request'), job, intent, sent)
    wanted = 'PARTIAL' if intent == 'mid_file_stop' else 'FULL'
    check(value.get('schema') == 'n4-source-delivery-v1'
          and value.get('status') == 'OBSERVED_'+wanted+'_SOURCE_DELIVERY_REQUIRES_REVIEW'
          and value.get('errors') == {}, 'Wrong source observation')
    check(value.get('expected_frames') == job['frames'] and value.get('job_fingerprint') == fingerprint(job)
          and value.get('sample_rate_hz') == 16000 and value.get('chunk_samples') == CHUNK, 'Planned source changed')
    check(value.get('journal_committed') == sent and value.get('journal_finished') is True
          and value.get('journal_had_fatal_error') is False and value.get('source_fatal_seen') is False
          and value.get('source_thread_exited') is True and value.get('source_stop_requested') is True
          and value.get('source_start_events') == 1, 'Source/journal did not finish the delivered prefix')
    check(value.get('trace_format') == FORMAT and value.get('trace_bytes') == len(raw)
          and value.get('trace_capacity_bytes') == ((job['frames']+CHUNK-1)//CHUNK)*RECORD.size,
          'Trace format or capacity differs')
    for key in ('audio_copied_or_transformed','source_pacer_changed','source_stop_requested_by_observer',
                'actual_application_integration_qualified','timing_or_continuity_accepted'):
        check(value.get(key) is False, 'Unexpected source effect/acceptance: '+key)
    check(value.get('observer_cost_not_subtracted') is True, 'Timing correction is forbidden')
    origin = value.get('source_origin_perf_counter'); request = capture['request']
    check(finite(origin) and 0 < origin <= request['requested_monotonic_sec'], 'Source origin does not precede stop request')
    summary = summarize(raw, origin=origin, frames=job['frames'], sent=sent, committed=sent)
    check(summary == value.get('summary') and summary['records'] == value.get('append_attempts')
          and summary['failed_appends'] == 0 and summary['complete_source'] is (intent == 'completed_release'),
          'Independent trace reconstruction differs')
    return dict(status='PASS_RELEASED_SESSION_DELIVERY_ONLY', intent=intent, planned_frames=job['frames'],
        delivered_frames=sent, source_origin_perf_counter=origin, summary=summary,
        engine_archive_closure_must_pass_separately=True, same_controller_restart_qualified=False,
        timing_or_continuity_accepted=False, integrated_N4_cells=0)
