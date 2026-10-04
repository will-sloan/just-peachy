"""Optional bounded background refinement coordinator. See README_PIPELINES.md.

Prepared integration code: the installed native dual-worker route remains disabled
until independently measured admission and a verified worker are provided.
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import math
import re
import threading
import time

try:
    from .correction import CaptionLedger, SampleInterval, SpeakerSpan
    from .profiles import RuntimeSelection, MODEL_SHA256, RUNTIME_REVISION
    from .telemetry import BoundedRefinementQueue
except ImportError:
    from correction import CaptionLedger, SampleInterval, SpeakerSpan
    from profiles import RuntimeSelection, MODEL_SHA256, RUNTIME_REVISION
    from telemetry import BoundedRefinementQueue


def _pin(value):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Exact SHA256 source/admission pin required")
    return value


def validate_native_admission(raw, expected_sha256, selection, source_pin):
    """Check a pinned measured receipt; synthetic results cannot admit native work.

    The caller supplies an independently trusted receipt hash, not a hash derived
    on the fly from an untrusted request. No such CM5 dual-worker receipt is part
    of this change. This function never creates or upgrades a qualification.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= 65536:
        raise ValueError("Pinned bounded native admission receipt required")
    if hashlib.sha256(raw).hexdigest() != _pin(expected_sha256):
        raise ValueError("Native admission receipt bytes changed")
    if not isinstance(selection, RuntimeSelection) or not selection.provisional_correction:
        raise ValueError("Explicit provisional selection required")
    selection.validate(); _pin(source_pin)
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate receipt field")
            value[key] = item
        return value
    def invalid_constant(value):
        raise ValueError("Nonfinite admission value")
    receipt = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    expected = dict(schema="just-peachy.native-dual-refinement-admission.v1",
        status="MEASURED_NATIVE_CM5_DUAL_WORKER_PASS", synthetic=False,
        model_sha256=MODEL_SHA256, runtime_revision=RUNTIME_REVISION,
        fast_profile=selection.nemotron_profile, refinement_profile=selection.refinement_profile,
        source_sha256=source_pin, cpus=[2, 3], maximum_tasks=64)
    if any(type(receipt.get(key)) is not type(value) or receipt.get(key) != value
           for key, value in expected.items()):
        raise ValueError("Measured dual-worker receipt does not cover selected source/profiles/envelope")
    measured = receipt.get("measured")
    if type(measured) is not dict:
        raise ValueError("Actual dual-worker measurements required")
    for key in ("audio_seconds", "peak_memory_bytes", "rolling_rtf", "cpu_headroom_percent"):
        value = measured.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Finite native measurements required")
    if (measured["audio_seconds"] <= 0 or measured["peak_memory_bytes"] > 768 * 1024**2 or
            measured["rolling_rtf"] > 1 or measured["rolling_rtf"] <= 0 or
            not 0 < measured["cpu_headroom_percent"] <= 100 or
            type(measured.get("dropped_samples")) is not int or measured["dropped_samples"] != 0):
        raise ValueError("Native measurements do not admit concurrent real-time refinement")
    _pin(receipt.get("native_measurement_receipt_sha256"))
    return receipt


class RefinementCoordinator:
    """One optional worker, bounded pending/results, main-thread caption ownership.

    ``worker`` receives a serialized-source-reference job as a dict and returns
    SpeakerSpan objects on exactly that source's clock. It is called only from
    the worker thread. ``emit_primary`` never calls, waits for, or joins it.
    ``native=False`` is exclusively for synthetic/injected component use.
    """
    def __init__(self, ledger, selection, worker, *, source_pin, native=False,
                 admission_raw=None, admission_sha256=None, maximum_jobs=2,
                 clock=time.monotonic):
        if not isinstance(ledger, CaptionLedger) or not isinstance(selection, RuntimeSelection):
            raise ValueError("Explicit ledger and selection required")
        selection.validate()
        if not selection.provisional_correction or not callable(worker) or not callable(clock):
            raise ValueError("Explicit optional correction and injected worker required")
        if type(native) is not bool:
            raise ValueError("Exact native flag required")
        _pin(source_pin)
        self.admission = None
        if native:
            self.admission = validate_native_admission(admission_raw, admission_sha256,
                                                       selection, source_pin)
        self.ledger, self.selection, self.worker = ledger, selection, worker
        self.source_pin, self.native, self.clock = source_pin, native, clock
        self.queue = BoundedRefinementQueue(maximum_jobs=maximum_jobs, maximum_job_bytes=4096)
        self.results = deque(maxlen=maximum_jobs + 1)
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.thread = None
        self.serial = 0
        self.coalesced = self.result_overflow = self.late_results = self.worker_failures = 0

    def start(self):
        if self.thread is not None or self.stop_event.is_set():
            raise RuntimeError("Refinement coordinator is single-use")
        self.thread = threading.Thread(target=self._run, name="optional-speaker-refinement", daemon=True)
        self.thread.start()

    def emit_primary(self, sequence, interval, text):
        """Main-thread call: immediate text event regardless of worker state."""
        return self.ledger.add_caption(sequence, interval, text)

    def offer(self, interval, *, now, deadline, refinement_admissible=True):
        self.ledger._check(interval)
        if interval.end_sample > self.ledger.watermark:
            raise ValueError("Cannot refine audio beyond the received sample watermark")
        if interval.end_sample - interval.start_sample > self.ledger.window_samples:
            raise ValueError("Refinement job exceeds bounded revision window")
        if self.stop_event.is_set():
            return False
        if self.thread is None:
            raise RuntimeError("Start optional worker before offering jobs")
        self.serial += 1
        job = dict(pass_id=f"refinement-{self.serial}", interval=vars(interval),
                   source_sha256=self.source_pin, fast_profile=self.selection.nemotron_profile,
                   refinement_profile=self.selection.refinement_profile)
        payload = json.dumps(job, sort_keys=True, separators=(",", ":")).encode()
        with self.lock:
            if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
                raise ValueError("Finite monotonic admission time required")
            # The worker may advance the queue clock before this lock is held.
            now = max(now, self.queue.last_time)
            # A newer overlapping window supersedes queued work. An in-flight
            # job keeps its identity and is checked for lateness on completion.
            retained = deque()
            for old_deadline, old_payload in self.queue.jobs:
                old = json.loads(old_payload)["interval"]
                if max(old["start_sample"], interval.start_sample) < min(old["end_sample"], interval.end_sample):
                    self.coalesced += 1
                else:
                    retained.append((old_deadline, old_payload))
            self.queue.jobs = retained
            accepted = self.queue.offer(payload, deadline=deadline, now=now,
                                        refinement_admissible=refinement_admissible)
        if accepted:
            self.wake.set()
        return accepted

    def _run(self):
        while not self.stop_event.is_set():
            with self.lock:
                item = self.queue.take(self.clock())
            if item is None:
                self.wake.wait(.05)
                self.wake.clear()
                continue
            deadline, payload = item
            job = json.loads(payload)
            try:
                spans = self.worker(job)
                if type(spans) not in (list, tuple) or len(spans) > self.ledger.maximum_spans:
                    raise ValueError("Injected worker returned an unbounded span batch")
                requested = SampleInterval(**job["interval"])
                for span in spans:
                    if not isinstance(span, SpeakerSpan):
                        raise ValueError("Exact worker speaker spans required")
                    span.validate()
                    self.ledger._check(span.interval)
                    if not requested.start_sample <= span.interval.start_sample < span.interval.end_sample <= requested.end_sample:
                        raise ValueError("Refinement evidence escapes the submitted audio interval")
                result = (deadline, job["pass_id"], tuple(spans), None)
            except Exception as exc:
                result = (deadline, job["pass_id"], (), type(exc).__name__ + ": " + str(exc)[:512])
            with self.lock:
                if len(self.results) == self.results.maxlen:
                    self.result_overflow += 1
                self.results.append(result)

    def poll(self, *, now):
        """Main-thread call: nonblocking result drain and bounded revisions."""
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError("Finite monotonic time required")
        with self.lock:
            ready = list(self.results)
            self.results.clear()
        events = []
        for deadline, pass_id, spans, error in ready:
            if deadline <= now:
                self.late_results += 1
                continue
            if error:
                self.worker_failures += 1
                events.append(dict(event="refinement_failed", pass_id=pass_id, error=error,
                                   primary_text_unchanged=True))
                continue
            try:
                events.extend(self.ledger.apply_refinement(pass_id, list(spans)))
            except ValueError as exc:
                self.worker_failures += 1
                events.append(dict(event="refinement_failed", pass_id=pass_id, error=str(exc)[:512],
                                   primary_text_unchanged=True))
        return events

    def close(self, timeout=1):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= 60:
            raise ValueError("Finite bounded worker join required")
        self.stop_event.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(timeout)
            if self.thread.is_alive():
                raise RuntimeError("Optional worker remains owned; no cleanup success")

