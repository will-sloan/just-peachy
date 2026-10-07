"""Bounded measured telemetry and refinement admission. See README_PIPELINES.md."""
from collections import deque
import math


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Finite nonnegative measurement required")
    return float(value)


class RollingTelemetry:
    def __init__(self, *, window_seconds=60, maximum_events=512, backlog_limit_seconds=120,
                 refinement_backlog_limit_seconds=120):
        self.window_seconds = _number(window_seconds)
        self.backlog_limit_seconds = None if backlog_limit_seconds is None else _number(backlog_limit_seconds)
        self.refinement_backlog_limit_seconds = _number(refinement_backlog_limit_seconds)
        if (not self.window_seconds or self.backlog_limit_seconds == 0
                or not self.refinement_backlog_limit_seconds):
            raise ValueError("Positive windows required")
        if type(maximum_events) is not int or not 1 <= maximum_events <= 8192:
            raise ValueError("Bounded event capacity required")
        self.events = deque(maxlen=maximum_events)
        self.last_time = 0.0
        self.dropped_samples = self.dropped_refinements = self.evicted_events = 0
        self.backlog_seconds = self.maximum_backlog_seconds = 0.0

    def _clock(self, now):
        now = _number(now)
        if now < self.last_time:
            raise ValueError("Monotonic telemetry clock required")
        self.last_time = now
        while self.events and self.events[0][0] <= now - self.window_seconds:
            self.events.popleft()
        return now

    def observe(self, *, now, audio_seconds, compute_seconds, backlog_seconds,
                dropped_samples=0, dropped_refinements=0):
        audio = _number(audio_seconds)
        compute = _number(compute_seconds)
        backlog = _number(backlog_seconds)
        for value in (dropped_samples, dropped_refinements):
            if type(value) is not int or value < 0:
                raise ValueError("Exact nonnegative drop counters required")
        if compute and not audio:
            raise ValueError("Compute duration needs its measured audio denominator")
        now = self._clock(now)
        if len(self.events) == self.events.maxlen:
            self.evicted_events += 1
        self.events.append((now, audio, compute))
        self.backlog_seconds = backlog
        self.maximum_backlog_seconds = max(self.maximum_backlog_seconds, backlog)
        self.dropped_samples += dropped_samples
        self.dropped_refinements += dropped_refinements

    def snapshot(self, now):
        self._clock(now)
        audio = sum(v[1] for v in self.events)
        compute = sum(v[2] for v in self.events)
        stop = self.backlog_limit_seconds is not None and self.backlog_seconds >= self.backlog_limit_seconds
        refinement_limit = (self.refinement_backlog_limit_seconds if self.backlog_limit_seconds is None
                            else min(self.backlog_limit_seconds, self.refinement_backlog_limit_seconds))
        return dict(rolling_rtf=compute / audio if audio else None,
                    measured_audio_seconds=audio, measured_compute_seconds=compute,
                    backlog_seconds=self.backlog_seconds,
                    maximum_backlog_seconds=self.maximum_backlog_seconds,
                    refinement_admissible=self.backlog_seconds < refinement_limit,
                    refinement_backlog_limit_seconds=refinement_limit,
                    backlog_limit_seconds=self.backlog_limit_seconds,
                    stop_required=stop,
                    stop_reason="FAILED_BACKLOG_LIMIT" if stop else None,
                    dropped_samples=self.dropped_samples,
                    dropped_refinements=self.dropped_refinements,
                    resident_events=len(self.events), evicted_events=self.evicted_events,
                    window_seconds=self.window_seconds, evidence="CALLER_MEASURED_EVENTS",
                    realtime_qualified=False)


class BoundedRefinementQueue:
    """Nonblocking admission; overflow/late work is counted, text never waits."""
    def __init__(self, *, maximum_jobs=4, maximum_job_bytes=65536):
        if type(maximum_jobs) is not int or not 1 <= maximum_jobs <= 64:
            raise ValueError("Bounded job capacity required")
        if type(maximum_job_bytes) is not int or not 1 <= maximum_job_bytes <= 1048576:
            raise ValueError("Bounded job byte capacity required")
        self.maximum_jobs = maximum_jobs
        self.maximum_job_bytes = maximum_job_bytes
        self.jobs = deque()
        self.dropped_full = self.dropped_late = self.dropped_backlog = 0
        self.last_time = 0.0

    def _expire(self, now):
        now = _number(now)
        if now < self.last_time:
            raise ValueError("Monotonic queue clock required")
        self.last_time = now
        retained = deque()
        for deadline, payload in self.jobs:
            if deadline <= now:
                self.dropped_late += 1
            else:
                retained.append((deadline, payload))
        self.jobs = retained
        return now

    def offer(self, payload, *, deadline, now, refinement_admissible=True):
        if type(payload) is not bytes or len(payload) > self.maximum_job_bytes:
            raise ValueError("Bounded serialized job bytes required")
        if type(refinement_admissible) is not bool:
            raise ValueError("Exact admission flag required")
        deadline = _number(deadline)
        now = self._expire(now)
        if deadline <= now:
            self.dropped_late += 1
            return False
        if not refinement_admissible:
            self.dropped_backlog += 1
            return False
        if len(self.jobs) >= self.maximum_jobs:
            self.dropped_full += 1
            return False
        self.jobs.append((deadline, payload))
        return True

    def take(self, now):
        self._expire(now)
        return self.jobs.popleft() if self.jobs else None
