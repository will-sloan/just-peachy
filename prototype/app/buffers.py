"""Bounded RAM audio and rotating UTF-8 field journals. No ambient audio archive."""
from pathlib import Path
import threading
import time
import queue
import numpy as np


class AudioGap(RuntimeError):
    pass


class MemoryJournal:
    """Shared 120-second audio ring. A late reader fails explicitly, never skips."""
    def __init__(self, path=None, sample_rate=16000, reserve_sec=120, observer=None):
        self.path = Path(path) if path else None
        self.sample_rate = sample_rate
        self.capacity = round(sample_rate*reserve_sec)
        self._ring = np.zeros(self.capacity, dtype=np.float32)
        self._condition = threading.Condition()
        self.committed_samples = 0
        self.finished = False
        self.fatal_error = None
        self.max_append_ms = 0.
        self.overrun_reads = 0
        self.observer = observer

    def append(self, samples):
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        if len(samples) > self.capacity or not np.isfinite(samples).all():
            raise AudioGap('Invalid block or block exceeds audio reserve')
        started = time.perf_counter()
        start_sample = self.committed_samples
        with self._condition:
            if self.finished:
                raise AudioGap('Audio arrived after source closure')
            offset = self.committed_samples % self.capacity
            first = min(len(samples), self.capacity-offset)
            self._ring[offset:offset+first] = samples[:first]
            self._ring[:len(samples)-first] = samples[first:]
            self.committed_samples += len(samples)
            self._condition.notify_all()
        self.max_append_ms = max(self.max_append_ms, (time.perf_counter()-started)*1000)
        # Prototype source-consumer hook, never the native audio callback.
        # The observer owns its bounded nonthrowing archival failure policy.
        if self.observer is not None:self.observer(start_sample,samples)

    def read(self, cursor, maximum_samples, *, wait_sec=.25):
        with self._condition:
            if cursor >= self.committed_samples and not self.finished:
                self._condition.wait(wait_sec)
            if cursor < max(0, self.committed_samples-self.capacity):
                self.overrun_reads += 1
                raise AudioGap('Consumer exceeded bounded 120-second reserve; start a fresh session')
            n = min(maximum_samples, max(0, self.committed_samples-cursor))
            at = cursor % self.capacity
            first = min(n, self.capacity-at)
            out = np.empty(n, dtype=np.float32)
            out[:first] = self._ring[at:at+first]
            out[first:] = self._ring[:n-first]
            return out

    def finish(self, error=None):
        with self._condition:
            self.finished = True
            if self.fatal_error is None:
                self.fatal_error = error
            self._condition.notify_all()

    @property
    def duration_sec(self):
        return self.committed_samples/self.sample_rate


class RotatingText:
    """Used only by journal/finalization workers, never by capture callbacks."""
    def __init__(self, path, max_bytes=1048576, backups=2, delay_sec=0):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes, self.backups, self.delay_sec = max_bytes, backups, delay_sec
        self.closed = False
        self._lock = threading.Lock()
        self._handle = self.path.open('a', encoding='utf-8', newline='\n', buffering=1)
        self._bytes = self.path.stat().st_size
        self.rotations = 0

    def write(self, value):
        if self.delay_sec:
            time.sleep(self.delay_sec)
        encoded = len(value.encode('utf-8'))
        with self._lock:
            if self.closed:
                raise ValueError('Journal is closed')
            if self._bytes+encoded > self.max_bytes and self._bytes:
                self._handle.close()
                for n in range(self.backups, 0, -1):
                    old = self.path.with_name(self.path.name+f'.{n}')
                    if n == self.backups:
                        old.unlink(missing_ok=True)
                    else:
                        if old.exists(): old.replace(self.path.with_name(self.path.name+f'.{n+1}'))
                self.path.replace(self.path.with_name(self.path.name+'.1'))
                self._handle = self.path.open('w', encoding='utf-8', newline='\n', buffering=1)
                self._bytes = 0
                self.rotations += 1
            self._handle.write(value)
            self._bytes += encoded
        return len(value)

    def flush(self):
        with self._lock:
            if not self.closed: self._handle.flush()

    def close(self):
        with self._lock:
            if not self.closed: self._handle.close()
            self.closed = True


class AsyncText:
    """Nonblocking finite event/text writer; exhaustion is an explicit failure."""
    def __init__(self, path, capacity=4096, delay_once=0):
        self.sink = RotatingText(path)
        self.queue = queue.Queue(capacity)
        self.delay_once = delay_once
        self.error = None
        self.closed = False
        self.accepted = self.completed = self.max_depth = 0
        self.thread = threading.Thread(target=self._run, name='proto-journal', daemon=True)
        self.thread.start()

    def write(self, text):
        if self.closed or self.error: raise RuntimeError('Journal unavailable: '+str(self.error))
        if len(text.encode('utf-8'))>1024*1024: raise RuntimeError('Single journal record exceeds1MiB')
        try: self.queue.put_nowait(text)
        except queue.Full as exc: raise RuntimeError('Journal queue exhausted; capture must stop explicitly') from exc
        self.accepted+=1;self.max_depth=max(self.max_depth,self.queue.qsize())
        return len(text)

    def _run(self):
        while True:
            text=self.queue.get()
            try:
                if text is None: return
                if self.delay_once:
                    time.sleep(self.delay_once);self.delay_once=0
                self.sink.write(text);self.completed+=1
            except Exception as exc:
                self.error=repr(exc)
            finally: self.queue.task_done()

    def flush(self):
        if self.error: raise RuntimeError(self.error)

    def close(self):
        if self.closed: return
        self.closed=True
        self.queue.put(None,timeout=30)
        self.thread.join(30)
        if self.thread.is_alive(): raise TimeoutError('Bounded journal did not drain')
        self.sink.close()
        if self.error or self.accepted!=self.completed: raise RuntimeError('Journal failed: '+str(self.error))
