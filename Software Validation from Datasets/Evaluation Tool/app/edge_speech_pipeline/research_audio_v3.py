"""S6C paired file producer. See README_RESEARCH_S6C.md for invocation."""
from __future__ import annotations

from pathlib import Path
import threading
import time

import numpy as np

from .audio import AudioJournal


class PairedJournal:
    """Publish each common sample boundary only after both journals are written."""

    def __init__(self, asr: AudioJournal, identity: AudioJournal):
        self.journals = (asr, identity)
        self.condition = threading.Condition()
        self.committed_samples = 0
        self.finished = False
        self.fatal_error = None

    def append(self, left, right):
        if len(left) != len(right):
            raise ValueError("paired block lengths differ")
        with self.condition:
            if self.finished:
                raise RuntimeError("paired journals are closed")
            try:
                self.journals[0].append(left)
                self.journals[1].append(right)
            except Exception as exc:
                self.finish(str(exc))
                raise
            self.committed_samples += len(left)
            self.condition.notify_all()

    def finish(self, error=None):
        with self.condition:
            if not self.finished:
                self.fatal_error = error
                for journal in self.journals:
                    journal.finish(error)
                self.finished = True
                self.condition.notify_all()

    def view(self, index):
        return _JournalView(self, index)


class _JournalView:
    def __init__(self, pair, index):
        self.pair, self.index = pair, index
        self.path = pair.journals[index].path
        self.sample_rate = pair.journals[index].sample_rate

    @property
    def committed_samples(self):
        return self.pair.committed_samples

    @property
    def duration_sec(self):
        return self.committed_samples / self.sample_rate

    @property
    def finished(self):
        return self.pair.finished

    @property
    def fatal_error(self):
        return self.pair.fatal_error

    def read(self, cursor, maximum_samples, *, wait_sec=.25):
        with self.pair.condition:
            if cursor >= self.committed_samples and not self.finished:
                self.pair.condition.wait(timeout=wait_sec)
            count = min(maximum_samples, max(0, self.committed_samples - cursor))
        if not count:
            return np.empty(0, dtype=np.float32)
        return self.pair.journals[self.index].read(cursor, count, wait_sec=0)

    def finish(self, error=None):
        self.pair.finish(error)


class PairedWavSource:
    """Incrementally consume already-gained, aligned mono16k files; no playback."""

    def __init__(self, pair, asr_path, identity_path, *, realtime=True,
                 accelerated_factor=4., status_callback=None, source_block_ms=100):
        import soundfile as sf
        self.pair = pair
        self.paths = tuple(Path(p).resolve() for p in (asr_path, identity_path))
        infos = [sf.info(p) for p in self.paths]
        if any(i.samplerate != 16000 or i.channels != 1 for i in infos):
            raise ValueError("S6C paired files must both be mono16kHz; no implicit resampling/downmix")
        if infos[0].frames != infos[1].frames:
            raise ValueError("paired files must have identical complete sample counts")
        if source_block_ms not in {20, 50, 100, 200}:
            raise ValueError("unsupported paired source block")
        self.expected_samples = infos[0].frames
        self.realtime, self.accelerated_factor = realtime, accelerated_factor
        self.block_samples = source_block_ms * 16
        self.status_callback = status_callback or (lambda *_: None)
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, name="s6c-paired-wav", daemon=True)
        self.thread.start()

    def _run(self):
        import soundfile as sf
        try:
            with sf.SoundFile(self.paths[0]) as left, sf.SoundFile(self.paths[1]) as right:
                self.status_callback("source_started", {"mode": "paired_wav", "asr_path": str(self.paths[0]),
                    "identity_path": str(self.paths[1]), "native_sample_rate": 16000, "pipeline_sample_rate": 16000,
                    "channels": 1, "expected_samples": self.expected_samples,
                    "common_origin": "paired_capture_sample_zero", "gain_in_producer": 1.,
                    "publication_policy": "both journals written then common block committed before sleep"})
                while not self.stop_event.is_set():
                    while self.pause_event.is_set() and not self.stop_event.is_set():
                        time.sleep(.05)
                    if self.stop_event.is_set():
                        break
                    a = left.read(self.block_samples, dtype="float32", always_2d=False)
                    b = right.read(self.block_samples, dtype="float32", always_2d=False)
                    if len(a) != len(b):
                        raise RuntimeError("paired input changed or ended asynchronously")
                    if not len(a):
                        break
                    self.pair.append(a, b)
                    delay = len(a) / 16000
                    if self.realtime:
                        time.sleep(delay)
                    elif self.accelerated_factor > 0:
                        time.sleep(delay / self.accelerated_factor)
                if not self.stop_event.is_set() and self.pair.committed_samples != self.expected_samples:
                    raise RuntimeError("paired input did not deliver admitted full length")
            self.pair.finish()
        except Exception as exc:
            self.pair.finish(str(exc))
            self.status_callback("fatal", {"reason": "PAIRED_WAV_SOURCE_FAILED", "detail": str(exc)})

    def pause(self):
        self.pause_event.set()

    def resume(self):
        self.pause_event.clear()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=3.)
        self.pair.finish()
