"""Bounded disk audio reader for the existing pipeline journal interface.

See README_AUDIO_JOURNAL.md. The caller registers its owner before importing
project modules and supplies a session policy, a SessionSpool and a fault sink.
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Mapping

import numpy as np


class AudioGap(RuntimeError):
    """An append/read could not preserve the admitted sample sequence."""


class DiskAudioJournal:
    """Append once to SessionSpool; read bounded slices at absolute offsets.

    The spool owns files, fsync, storage accounting and its closure. This
    adapter owns no audio queue, native source, archive, or background worker.
    Observer failures preserve accepted-source accounting: append returns
    after setting fatal_error, finishing, publishing a fault and requesting
    Stop. A failed disk append instead raises without publishing its samples.
    """

    def __init__(self, spool, *, policy: Mapping, fault_receipt,
                 observer=None, request_stop=None, max_read_samples=None):
        if not isinstance(policy, Mapping):
            raise TypeError('An explicit session policy mapping is required')
        duration = policy.get('duration_seconds')
        rate = policy.get('sample_rate')
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError('Positive finite duration_seconds is required')
        if type(rate) is not int or rate != 16000:
            raise ValueError('Journal requires the selected mono 16 kHz source')
        if not callable(fault_receipt):
            raise TypeError('A fault_receipt callback is required')
        if not callable(getattr(spool, 'append_processed', None)) or not callable(getattr(spool, 'read_processed', None)):
            raise TypeError('Spool must supply append_processed and read_processed')
        if any(spool.spec.get(key) != policy[key] for key in ('duration_seconds', 'sample_rate')):
            raise ValueError('Journal policy differs from the actual spool session')
        if spool.processed_samples != 0:
            raise ValueError('A fresh audio journal requires a fresh processed cursor')
        limit = getattr(getattr(getattr(spool, 'store', None), 'policy', None), 'max_append_bytes', None)
        if limit is None:
            limit = getattr(getattr(spool, 'policy', None), 'max_append_bytes', None)
        if limit is None:
            limit = getattr(spool, 'max_append_bytes', None)
        if type(limit) is not int or limit < 4:
            raise ValueError('Spool must expose its positive max_append_bytes bound')
        available = limit // 4
        if max_read_samples is None:
            max_read_samples = min(rate * 10, available)
        if type(max_read_samples) is not int or not 0 < max_read_samples <= available:
            raise ValueError('Read allocation must fit the spool I/O bound')
        self.spool = spool
        # This is the logical journal root. Physical audio is segmented and
        # must be accessed with SessionSpool.read_processed, not one f32 file.
        self.path = getattr(spool, 'directory', None)
        self.sample_rate = rate
        self.maximum_samples = math.floor(duration * rate)
        self.max_read_samples = max_read_samples
        self.max_append_samples = available
        self.observer = observer
        self.request_stop = request_stop
        self.fault_receipt = fault_receipt
        self.committed_samples = 0
        self.finished = False
        self.fatal_error = None
        self.max_append_ms = 0.0
        self.overrun_reads = 0
        self.fault = None
        self.fault_receipt_error = None
        self._condition = threading.Condition(threading.RLock())
        self._append_lock = threading.Lock()

    @property
    def duration_sec(self):
        return self.committed_samples / self.sample_rate

    def _fail(self, stage, error, start, offered, accepted):
        with self._condition:
            if self.fatal_error is None:
                self.fatal_error = error
            self.finished = True
            if self.fault is not None:
                self._condition.notify_all()
                return
            self.fault = dict(schema='just-peachy.audio-journal-fault.v1',
                stage=stage, error_type=type(error).__name__, reason=str(error)[:1024],
                start_sample=start, offered_samples=offered, accepted_samples=accepted,
                committed_samples=self.committed_samples,
                spool_committed_samples=self.spool.processed_samples,
                source_samples_silently_dropped=False, retry_allowed=False)
            receipt = dict(self.fault)
            self._condition.notify_all()
        # Stop is requested before diagnostic I/O, preserving physical closure
        # ownership in the caller. Neither hook may alter accepted sample counts.
        if self.request_stop is not None:
            try:
                self.request_stop('AUDIO_JOURNAL_' + stage.upper())
            except BaseException as stop_error:
                receipt['stop_callback_error'] = repr(stop_error)[:1024]
        try:
            self.fault_receipt(receipt)
        except BaseException as receipt_error:
            # Preserve a visible in-memory receipt even when its durable sink
            # itself fails (for example ENOSPC); never claim publication success.
            self.fault_receipt_error = receipt_error
            receipt['receipt_publication_error'] = repr(receipt_error)[:1024]
        self.fault = receipt

    def append(self, samples):
        started = time.perf_counter()
        with self._append_lock:
            start = self.committed_samples
            with self._condition:
                if self.finished:
                    error = AudioGap('Audio arrived after journal closure')
                    self._fail('closed_append', error, start, 0, 0)
                    raise error
            offered = 0
            try:
                # Inspect shape/length before dtype conversion or byte copying.
                offered = len(samples)
                if offered > self.max_append_samples:
                    raise AudioGap('Audio block exceeds the bounded append allocation')
                array = np.asarray(samples)
                if array.ndim != 1:
                    raise AudioGap('Expected a mono one-dimensional audio block')
                if start + offered > self.maximum_samples:
                    raise AudioGap('Session recording sample allowance exhausted')
                array = np.ascontiguousarray(array, dtype='<f4')
                if not np.isfinite(array).all():
                    raise AudioGap('Nonfinite audio block')
                if offered == 0:
                    return
                # SessionSpool fsyncs before advancing its published cursor.
                self.spool.append_processed(start, array.tobytes())
                if self.spool.processed_samples != start + offered:
                    raise AudioGap('Spool did not publish the exact accepted cursor')
            except BaseException as error:
                self._fail('append', error, start, offered, 0)
                raise
            with self._condition:
                self.committed_samples = start + offered
                self._condition.notify_all()
            if self.observer is not None:
                try:
                    self.observer(start, array)
                except BaseException as error:
                    self._fail('observer', error, start, offered, offered)
            self.max_append_ms = max(self.max_append_ms, (time.perf_counter() - started) * 1000)

    def read(self, cursor, maximum_samples, *, wait_sec=0.25):
        if type(cursor) is not int or cursor < 0:
            raise ValueError('Nonnegative absolute sample cursor required')
        if type(maximum_samples) is not int or maximum_samples < 0:
            raise ValueError('Nonnegative integer read bound required')
        if type(wait_sec) not in (int, float) or not math.isfinite(wait_sec) or not 0 <= wait_sec <= 1:
            raise ValueError('Read wait must be finite and between zero and one second')
        with self._condition:
            if cursor >= self.committed_samples and not self.finished and maximum_samples:
                self._condition.wait(wait_sec)
            count = min(maximum_samples, self.max_read_samples,
                        max(0, self.committed_samples - cursor))
        if not count:
            return np.empty(0, dtype=np.float32)
        try:
            raw = self.spool.read_processed(cursor, count)
            if len(raw) != count * 4:
                raise AudioGap('Committed disk audio is truncated')
            return np.frombuffer(raw, dtype='<f4').copy()
        except BaseException as error:
            self._fail('read', error, cursor, count, 0)
            raise

    def finish(self, error=None):
        # Join any in-progress append before publishing EOF; a concurrent
        # reader can drain the complete committed prefix after this returns.
        with self._append_lock:
            if error is not None:
                self._fail('source', error, self.committed_samples, 0, 0)
            else:
                with self._condition:
                    self.finished = True
                    self._condition.notify_all()

    def close(self):
        """Close this view; the session owner remains responsible for the spool."""
        self.finish()

    def snapshot(self):
        with self._condition:
            return dict(committed_samples=self.committed_samples, finished=self.finished,
                maximum_samples=self.maximum_samples, max_read_samples=self.max_read_samples,
                audio_ram_cache_bytes=0, fatal_error=str(self.fatal_error) if self.fatal_error else None,
                fault=dict(self.fault) if self.fault else None,
                fault_receipt_error=str(self.fault_receipt_error) if self.fault_receipt_error else None)
