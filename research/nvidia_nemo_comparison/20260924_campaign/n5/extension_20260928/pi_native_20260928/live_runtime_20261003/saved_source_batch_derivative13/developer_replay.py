"""Explicit continuous developer replay, one source epoch. See README_DEVELOPER_REPLAY.md."""
from pathlib import Path
import threading
import time
import wave

from runtime_support import digest
from saved_source_metrics import SavedSourceMetrics, validate_batch_samples


def pin_repeat_input(path,policy):
    path=Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Repeated input must be an ordinary pinned WAV')
    if not 44<=path.stat().st_size<=policy.maximum_samples()*2+65536:
        raise ValueError('Repeated WAV container exceeds finite source allocation')
    return digest(path)


def validate_repeat(selection, policy, saved_path, saved_session_id, seconds):
    if seconds is None:
        return None
    if (type(seconds) is not int or seconds < 3600 or not policy.developer_soak
            or seconds != policy.maximum_session_seconds
            or selection.input_source != 'saved' or not saved_path or saved_session_id):
        raise ValueError('Repeat requires explicit >=3600s developer policy and one saved WAV')
    return seconds


class RepeatedSavedSource:
    """Repeat exact PCM bytes without restarting the journal or any model."""
    def __init__(self, journal, path, callback, policy, stop_event, *, repeat_input_seconds,
                 expected_sha256, clock=time.perf_counter, append_batch_samples=1600):
        if (type(repeat_input_seconds) is not int or repeat_input_seconds < 3600
                or repeat_input_seconds != policy.maximum_session_seconds or not policy.developer_soak):
            raise ValueError('Explicit matching developer repeat duration required')
        self.append_batch_samples = validate_batch_samples(append_batch_samples)
        self.journal, self.path, self.callback = journal, Path(path), callback
        self.policy, self.stop_event, self.clock = policy, stop_event, clock
        self.sha256 = pin_repeat_input(self.path,policy)
        if self.sha256 != expected_sha256:
            raise ValueError('Repeated input SHA changed since explicit admission')
        with wave.open(str(self.path), 'rb') as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1,2,16000,'NONE'):
                raise ValueError('Repeated input requires mono PCM16 16 kHz; no conversion')
            self.frames = source.getnframes()
        if not 0 < self.frames <= policy.maximum_samples():
            raise ValueError('Empty or over-policy repeat input')
        self.target = policy.maximum_samples()
        self.sent = 0
        self.error = None
        self.thread = None
        self.done = threading.Event()

    def start(self):
        if self.thread is not None:
            raise RuntimeError('One continuous repeated source per session')
        self.thread = threading.Thread(target=self._run, name='v29-developer-repeated-source', daemon=True)
        self.thread.start()

    def _run(self):
        import numpy as np
        origin = self.clock()
        metrics = SavedSourceMetrics(origin, self.callback, self.append_batch_samples, clock=self.clock)
        cycle = 0
        try:
            self.callback('source_started', dict(mode='developer_repeated_file',
                source_epoch_monotonic_sec=origin, source_sha256=self.sha256,
                source_frames=self.frames, target_samples=self.target,
                physical_microphone=False, motion_applied=False, gain=1.0,
                repeated_input=True, quality_evaluated=False, append_batch_samples=self.append_batch_samples))
            with wave.open(str(self.path), 'rb') as source:
                while self.sent < self.target and not self.stop_event.is_set():
                    raw = source.readframes(min(self.append_batch_samples, self.target-self.sent))
                    if not raw:
                        # Check bytes at every boundary before reusing the file.
                        if pin_repeat_input(self.path,self.policy) != self.sha256:
                            raise RuntimeError('Repeat input changed while in use')
                        cycle += 1
                        self.callback('source_repeat_boundary', dict(repetition=cycle,
                            logical_start_sample=self.sent, input_offset_sample=0,
                            source_frames=self.frames, source_sha256=self.sha256,
                            source_epoch_monotonic_sec=origin, models_reset=False))
                        source.rewind()
                        continue
                    end = self.sent+len(raw)//2
                    if self.stop_event.wait(max(0.,origin+end/16000-self.clock())):
                        break
                    metrics.append(self.journal, np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768., end)
                    self.sent = end
                    metrics.progress()
            if pin_repeat_input(self.path,self.policy) != self.sha256:
                raise RuntimeError('Repeat input changed while in use')
        except BaseException as exc:
            self.error = repr(exc)
            self.callback('fatal',dict(reason=self.error))
        finally:
            try:
                self.journal.finish(self.error)
                self.callback('source_stopped',dict(sent_samples=self.sent,target_samples=self.target,
                    repetitions=cycle, physical_microphone=False,error=self.error,
                    source_sha256=self.sha256,repeated_input=True, saved_source_metrics=metrics.snapshot()))
            finally:
                self.done.set()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(5)
            if self.thread.is_alive():
                raise RuntimeError('Repeated source remains owned')

    def wait(self, timeout=None):
        return self.done.wait(timeout)
