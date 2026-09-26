"""Bounded FileSource delivery observation; see README_SOURCE_DELIVERY.md.

This utility is not an application admission gate. Install only in a separately
admitted fresh application session, before its unchanged FileSource starts.
"""
from __future__ import annotations

import math
from pathlib import Path
import struct
import threading
import time

from common import audio_only, fingerprint

RATE = 16000
CHUNK = 320
MAX_FRAMES = RATE * 3600
RECORD = struct.Struct('<IIIddB')
FORMAT = dict(struct='<IIIddB', bytes=RECORD.size, fields=[
    'start_sample', 'sample_count', 'committed_after',
    'append_entry_perf_counter', 'append_return_perf_counter', 'raised'])
TAG = '_n4_source_delivery_observer'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def distribution(values):
    """Nearest-rank quantiles, including signed early observations unchanged."""
    if not values:
        return dict(count=0, minimum=None, p50=None, p95=None, p99=None, maximum=None)
    ordered = sorted(values)
    return dict(count=len(ordered), minimum=ordered[0], maximum=ordered[-1],
                **{f'p{p}': ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)] for p in (50, 95, 99)})


def summarize(raw, *, origin, frames, sent, committed):
    """Independently parse every attempted append. Failures cannot become success."""
    check(type(frames) is int and 0 < frames <= MAX_FRAMES, 'Invalid planned source length')
    check(type(sent) is int and type(committed) is int and 0 <= sent <= committed <= frames,
          'Invalid terminal source counters')
    check(finite(origin) and origin > 0, 'Missing finite source origin')
    check(len(raw) % RECORD.size == 0 and len(raw) <= math.ceil(frames / CHUNK) * RECORD.size,
          'Truncated or oversized delivery trace')
    entry_delays = []; return_delays = []; call_times = []; gaps = []
    success = 0; attempted = 0; failures = 0; previous_return = origin; previous_entry = None
    for start, count, after, entered, returned, raised in RECORD.iter_unpack(raw):
        check(not failures and raised in (0, 1), 'Records follow a failed append or have invalid outcome')
        check(start == success and count == min(CHUNK, frames - start) and count > 0,
              'Missing, duplicated or noncanonical source chunk')
        check(finite(entered) and finite(returned) and previous_return <= entered <= returned,
              'Delivery clocks are nonfinite or reversed')
        check(after == start + count if not raised else start <= after <= start + count,
              'Journal committed count disagrees with append')
        deadline = origin + (start + count) / RATE
        entry_delays.append((entered - deadline) * 1000)
        return_delays.append((returned - deadline) * 1000)
        call_times.append((returned - entered) * 1000)
        if previous_entry is not None:
            gaps.append((entered - previous_entry) * 1000)
        previous_entry = entered; previous_return = returned
        attempted += count
        if raised:
            failures += 1
        else:
            success += count
        last_committed = after
    check(success == sent and (last_committed if raw else 0) == committed,
          'Trace does not cover terminal source/journal counts')
    return dict(records=len(raw) // RECORD.size, successful_samples=success,
        attempted_samples=attempted, failed_appends=failures, complete_source=success == frames and not failures,
        planned_duration_seconds=frames / RATE, delivered_duration_seconds=success / RATE,
        last_append_return_after_origin_seconds=previous_return - origin if raw else None,
        append_entry_lateness_ms=distribution(entry_delays), append_return_lateness_ms=distribution(return_delays),
        append_call_ms=distribution(call_times), inter_append_entry_gap_ms=distribution(gaps),
        append_call_total_ms=sum(call_times),
        early_entry_count=sum(v < -1e-6 for v in entry_delays),
        entry_over_5ms=sum(v > 5 for v in entry_delays), entry_over_20ms=sum(v > 20 for v in entry_delays),
        return_over_5ms=sum(v > 5 for v in return_delays), return_over_20ms=sum(v > 20 for v in return_delays),
        thresholds_are_diagnostics_not_acceptance=True)


class SourceDelivery:
    """Observe one unchanged, fresh mono FileSource and its actual input journal.

    Private test seams allow isolated source-class tests without importing the
    application/model graph. Any use is stamped and is never production evidence.
    All runtime observer failures invalidate its evidence but still forward the
    original block/callback exactly once. Original exceptions are re-raised.
    No disk writes, waveform copies, pacer changes or source stop requests occur.
    """
    def __init__(self, source, job, *, _types=None, _clock=None):
        audio_only(job)
        check(job['frames'] <= MAX_FRAMES, 'Delivery observation is limited to one hour')
        test_seams = _types is not None or _clock is not None
        if _types is None:
            from app.pipeline import FileSource
            from app.buffers import MemoryJournal
        else:
            FileSource, MemoryJournal = _types
        journal = source.journal
        check(type(source) is FileSource and type(journal) is MemoryJournal, 'Exact source/journal types required')
        check(source.thread is None and source.sent == 0 and source.start_sample == 0
              and not source.stop_event.is_set(), 'Install only before a fresh source starts')
        check(Path(source.path).resolve() == Path(job['audio_path']).resolve(), 'Source/job path mismatch')
        check(journal.sample_rate == RATE and journal.committed_samples == 0 and not journal.finished
              and journal.fatal_error is None, 'Fresh 16 kHz journal required')
        check(TAG not in vars(source) and 'append' not in vars(journal), 'Source or append already instrumented')
        check(getattr(journal.append, '__func__', None) is MemoryJournal.append
              and callable(source.callback), 'Unexpected source callback or append method')
        self.source = source; self.journal = journal; self.job = dict(job)
        self.clock = _clock or time.perf_counter; self.test_seams = test_seams
        self.original_callback = source.callback; self.original_append = journal.append
        self.data = bytearray(); self.max_bytes = math.ceil(job['frames'] / CHUNK) * RECORD.size
        self.errors = {}; self.origin = None; self.starts = 0; self.producer = None
        self.in_append = False; self.closed = False; self.source_fatal_seen = False
        self.attempts = 0; self.observed_callbacks = 0; self.previous_end = 0; self.previous_return = None
        self.installed = self.clock()
        check(finite(self.installed) and self.installed > 0, 'Invalid installation clock')
        # Keep identical callable objects for exact own-hook restoration checks.
        self.callback_hook = self._callback; self.append_hook = self._append
        source.callback = self.callback_hook; journal.append = self.append_hook
        setattr(source, TAG, self)

    def _error(self, kind):
        # Fixed internal reason vocabulary; no exception messages or unbounded strings.
        if kind in self.errors or len(self.errors) < 24:
            self.errors[kind] = self.errors.get(kind, 0) + 1

    def _callback(self, kind, payload):
        self.observed_callbacks += 1
        try:
            if kind == 'source_started':
                self.starts += 1
                check(self.starts == 1 and self.attempts == 0, 'Duplicate or late start')
                origin = payload['source_epoch_monotonic_sec']; now = self.clock()
                check(finite(origin) and finite(now) and self.installed <= origin <= now, 'Wrong source epoch')
                check(payload['mode'] == 'file' and payload['start_sample'] == 0 and payload['gain'] == 1
                      and payload['pacing'] == 'absolute' and Path(payload['path']).resolve() == Path(self.job['audio_path']).resolve(),
                      'Wrong start contract')
                self.origin = origin; self.producer = threading.get_ident(); self.previous_return = origin
            elif kind == 'fatal':
                self.source_fatal_seen = True; self._error('source_fatal')
        except Exception:
            self._error('invalid_source_event')
        try:
            return self.original_callback(kind, payload)
        except BaseException:
            self._error('original_callback_raised')
            raise

    def _append(self, block):
        if self.in_append:
            self._error('concurrent_or_reentrant_append')
            return self.original_append(block)
        self.in_append = True; self.attempts += 1; before = None; raised = 0
        try:
            try:
                start = self.source.sent; count = len(block); committed = self.journal.committed_samples
                check(self.starts == 1 and self.origin is not None and threading.get_ident() == self.producer,
                      'Append outside sole source producer')
                check(self.source.journal is self.journal and self.source.callback is self.callback_hook
                      and self.journal.append is self.append_hook and getattr(self.source, TAG, None) is self,
                      'Observer hooks changed')
                check(type(start) is int and start == self.previous_end == committed
                      and count == min(CHUNK, self.job['frames'] - start) and count > 0, 'Noncanonical source chunk')
                check(len(self.data) + RECORD.size <= self.max_bytes, 'Observation capacity exhausted')
                entered = self.clock()
                check(finite(entered) and self.previous_return <= entered, 'Invalid append entry clock')
                before = (start, count, entered)
            except Exception:
                self._error('invalid_append_entry')
            try:
                return self.original_append(block)
            except BaseException:
                raised = 1; self._error('original_append_raised')
                raise
            finally:
                try:
                    returned = self.clock(); after = self.journal.committed_samples
                    if before is not None:
                        start, count, entered = before
                        check(finite(returned) and returned >= entered and type(after) is int
                              and start <= after <= start + count, 'Invalid append return')
                        check(raised or after == start + count, 'Append did not commit whole block')
                        self.data.extend(RECORD.pack(start, count, after, entered, returned, raised))
                        self.previous_return = returned
                        if not raised:
                            self.previous_end = start + count
                except Exception:
                    self._error('invalid_append_return')
        finally:
            self.in_append = False

    def close(self):
        """Restore only owned hooks after producer exit; return metadata and bytes.

        Does not stop or join the application. Caller must persist both outputs in
        its admitted private directory and bind them in the final cell receipt.
        """
        check(not self.closed, 'Observer already closed')
        check(not self.in_append and (self.source.thread is None or not self.source.thread.is_alive()),
              'Source must exit before observation closure')
        self.closed = True
        for obj, name, own in ((self.source, 'callback', self.callback_hook), (self.journal, 'append', self.append_hook)):
            if getattr(obj, name, None) is own:
                if name == 'append':
                    delattr(obj, name)
                else:
                    setattr(obj, name, self.original_callback)
            else:
                self._error('foreign_hook_at_closure')
        if getattr(self.source, TAG, None) is self:
            delattr(self.source, TAG)
        else:
            self._error('foreign_owner_at_closure')
        if self.source.journal is not self.journal:
            self._error('source_journal_changed')
        if self.starts != 1 or self.source.thread is None:
            self._error('missing_source_start_or_thread')
        if not self.journal.finished or self.journal.fatal_error is not None:
            self._error('journal_not_cleanly_finished')
        raw = bytes(self.data); summary = None
        try:
            summary = summarize(raw, origin=self.origin, frames=self.job['frames'],
                                sent=self.source.sent, committed=self.journal.committed_samples)
            check(summary['records'] == self.attempts, 'Missing append attempts')
        except Exception:
            self._error('trace_counter_or_clock_mismatch')
        status = 'FAILED_SOURCE_DELIVERY_OBSERVATION'
        if not self.errors:
            status = ('OBSERVED_FULL_SOURCE_DELIVERY_REQUIRES_REVIEW' if summary['complete_source']
                      else 'OBSERVED_PARTIAL_SOURCE_DELIVERY_REQUIRES_REVIEW')
        receipt = dict(schema='n4-source-delivery-v1', status=status, job_fingerprint=fingerprint(self.job),
            sample_rate_hz=RATE, chunk_samples=CHUNK, expected_frames=self.job['frames'],
            source_sent=self.source.sent, journal_committed=self.journal.committed_samples,
            journal_finished=self.journal.finished, journal_had_fatal_error=self.journal.fatal_error is not None,
            source_stop_requested=self.source.stop_event.is_set(), source_thread_exited=True,
            source_start_events=self.starts, source_fatal_seen=self.source_fatal_seen,
            installation_perf_counter=self.installed, source_origin_perf_counter=self.origin,
            append_attempts=self.attempts, observed_callbacks=self.observed_callbacks,
            trace_format=FORMAT, trace_bytes=len(raw), trace_capacity_bytes=self.max_bytes,
            errors=dict(self.errors), summary=summary, test_seams_used=self.test_seams,
            audio_copied_or_transformed=False, source_pacer_changed=False, source_stop_requested_by_observer=False,
            observer_cost_not_subtracted=True, metric_scope='FileSource input-journal append timing; not a device callback or GUI paint clock',
            actual_application_integration_qualified=False, timing_or_continuity_accepted=False)
        return receipt, raw
