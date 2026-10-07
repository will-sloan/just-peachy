"""Bounded saved-input append timing. See README_SAVED_SOURCE_METRICS.md."""
import time

DEFAULT_APPEND_BATCH_SAMPLES = 1600


def validate_batch_samples(value):
    """An explicit source-only batch of 20, 40, 60, 80 or 100 ms."""
    if type(value) is not int or not 320 <= value <= 1600 or value % 320:
        raise ValueError('Saved append batch must be 320..1600 samples, in 320-sample steps')
    return value


class SavedSourceMetrics:
    """Constant-memory totals; no hardware polling, sample retention or model work."""
    def __init__(self, origin, callback, batch_samples, *, clock=time.perf_counter):
        self.origin, self.callback, self.clock = origin, callback, clock
        self.batch_samples = validate_batch_samples(batch_samples)
        self.calls = self.failures = self.samples = 0
        self.seconds = self.maximum_seconds = 0.0
        self.maximum_wall_lag_seconds = 0.0
        self.last_progress = origin

    def append(self, journal, audio, end_sample):
        count = len(audio)
        if not 0 < count <= self.batch_samples or end_sample != self.samples + count:
            raise ValueError('Saved append extent/cursor differs')
        started = self.clock()
        self.calls += 1
        try:
            journal.append(audio)
        except BaseException:
            self.failures += 1
            raise
        else:
            self.samples = end_sample
        finally:
            now = self.clock()
            elapsed = max(0.0, now-started)
            self.seconds += elapsed
            self.maximum_seconds = max(self.maximum_seconds, elapsed)
            self.maximum_wall_lag_seconds = max(self.maximum_wall_lag_seconds,
                max(0.0, now-self.origin-self.samples/16000))

    def progress(self):
        now = self.clock()
        if now-self.last_progress >= 1.0:
            self.last_progress = now
            self.callback('saved_source_progress', self.snapshot(now=now))

    def snapshot(self, *, now=None):
        now = self.clock() if now is None else now
        elapsed = max(0.0, now-self.origin)
        lag = max(0.0, elapsed-self.samples/16000)
        return dict(schema='saved-source-metrics.v1', append_batch_samples=self.batch_samples,
            committed_source_samples=self.samples, source_seconds=self.samples/16000,
            source_wall_seconds=elapsed, source_wall_lag_seconds=lag,
            maximum_source_wall_lag_seconds=max(lag,self.maximum_wall_lag_seconds),
            append_calls=self.calls, append_failures=self.failures,
            append_seconds=self.seconds, maximum_append_seconds=self.maximum_seconds,
            append_timing_scope='journal.append wall time including lock, durability and observer; not isolated storage CPU')
