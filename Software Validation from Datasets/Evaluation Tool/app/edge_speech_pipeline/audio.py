"""Lossless source-clock audio journal and live/file producers."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import queue
import threading
import time
from typing import Callable

import numpy as np
from scipy.signal import resample_poly


class AudioJournal:
    """Append-only PCM16 spool with independent cursors for every consumer.

    Capture never waits for ASR or speaker inference. Consumers can lag and read
    the exact committed samples from disk. A session therefore cannot silently
    discard old frames to make room for new ones.
    """

    def __init__(self, path: Path, sample_rate: int = 16_000) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate
        self._writer = self.path.open("wb", buffering=0)
        self._condition = threading.Condition()
        self.committed_samples = 0
        self.finished = False
        self.fatal_error: str | None = None

    def append(self, samples: np.ndarray) -> None:
        values = np.asarray(samples, dtype=np.float32).reshape(-1)
        if not values.size:
            return
        encoded = np.round(np.clip(values, -1.0, 0.999969) * 32768.0).astype("<i2")
        with self._condition:
            if self.finished:
                raise RuntimeError("cannot append after the journal is finished")
            self._writer.write(encoded.tobytes())
            self.committed_samples += int(encoded.size)
            self._condition.notify_all()

    def read(
        self, cursor: int, maximum_samples: int, *, wait_sec: float = 0.25
    ) -> np.ndarray:
        with self._condition:
            if cursor >= self.committed_samples and not self.finished:
                self._condition.wait(timeout=wait_sec)
            available = self.committed_samples - cursor
            count = min(maximum_samples, max(0, available))
        if count <= 0:
            return np.empty(0, dtype=np.float32)
        with self.path.open("rb", buffering=0) as handle:
            handle.seek(cursor * 2)
            payload = handle.read(count * 2)
        return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0

    def finish(self, error: str | None = None) -> None:
        with self._condition:
            if self.finished:
                return
            self.fatal_error = error
            self.finished = True
            self._writer.close()
            self._condition.notify_all()

    @property
    def duration_sec(self) -> float:
        return self.committed_samples / self.sample_rate


class _StreamingResampler:
    """Low-latency block resampler with a short overlap for filter continuity."""

    def __init__(self, source_rate: int, target_rate: int) -> None:
        from math import gcd

        common = gcd(source_rate, target_rate)
        self.up = target_rate // common
        self.down = source_rate // common
        self.source_rate = source_rate
        self.target_rate = target_rate
        self._carry = np.empty(0, dtype=np.float32)
        self._carry_samples = min(256, max(32, source_rate // 100))

    def convert(self, samples: np.ndarray) -> np.ndarray:
        values = np.asarray(samples, dtype=np.float32).reshape(-1)
        if self.source_rate == self.target_rate:
            return values
        combined = np.concatenate((self._carry, values))
        converted = resample_poly(combined, self.up, self.down).astype(np.float32)
        discard = round(self._carry.size * self.target_rate / self.source_rate)
        output = converted[discard:]
        self._carry = combined[-self._carry_samples :].copy()
        return output


class MicrophoneSource:
    """A fast callback plus independent normalization thread.

    The callback performs no inference and has a two-minute raw reserve. Any
    actual PortAudio overflow or reserve exhaustion becomes an explicit fatal
    session event instead of a drop-oldest warning.
    """

    def __init__(
        self,
        journal: AudioJournal,
        *,
        device: int | None,
        target_rate: int,
        block_ms: int,
        reserve_sec: int,
        status_callback: Callable[[str, dict[str, object]], None] | None = None,
    ) -> None:
        self.journal = journal
        self.device = device
        self.target_rate = target_rate
        self.block_ms = block_ms
        self.reserve_sec = reserve_sec
        self.status_callback = status_callback or (lambda _kind, _data: None)
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.raw_queue: queue.Queue[np.ndarray] | None = None
        self.stream = None
        self.thread: threading.Thread | None = None
        self.native_rate = target_rate
        self.input_overflow_events = 0
        self.raw_reserve_failures = 0
        self.intentional_pause_samples = 0

    def start(self) -> None:
        import sounddevice as sd

        info = sd.query_devices(self.device, "input")
        if int(info["max_input_channels"]) < 1:
            raise RuntimeError("selected device has no input channel")
        default_rate = int(round(float(info["default_samplerate"])))
        try:
            sd.check_input_settings(
                device=self.device,
                channels=1,
                dtype="float32",
                samplerate=self.target_rate,
            )
            self.native_rate = self.target_rate
        except Exception:
            self.native_rate = default_rate
        blocksize = max(1, round(self.native_rate * self.block_ms / 1000))
        reserve_blocks = max(100, round(self.reserve_sec * 1000 / self.block_ms))
        self.raw_queue = queue.Queue(maxsize=reserve_blocks)

        def callback(indata, frames, _time_info, status) -> None:
            if status:
                text = str(status)
                if "overflow" in text.lower():
                    self.input_overflow_events += 1
                    self.stop_event.set()
                    self.status_callback("fatal", {"reason": "PORTAUDIO_INPUT_OVERFLOW", "detail": text})
                    return
            if self.pause_event.is_set():
                self.intentional_pause_samples += int(frames)
                return
            try:
                assert self.raw_queue is not None
                self.raw_queue.put_nowait(np.asarray(indata[:, 0], np.float32).copy())
            except queue.Full:
                self.raw_reserve_failures += 1
                self.stop_event.set()
                self.status_callback("fatal", {"reason": "RAW_CAPTURE_RESERVE_EXHAUSTED"})

        self.stream = sd.InputStream(
            device=self.device,
            samplerate=self.native_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            callback=callback,
        )
        self.thread = threading.Thread(target=self._normalize, name="audio-normalizer", daemon=True)
        self.thread.start()
        self.stream.start()
        self.status_callback(
            "source_started",
            {
                "mode": "microphone",
                "device": int(self.device) if self.device is not None else None,
                "native_sample_rate": self.native_rate,
                "pipeline_sample_rate": self.target_rate,
                "channels": 1,
            },
        )

    def _normalize(self) -> None:
        assert self.raw_queue is not None
        converter = _StreamingResampler(self.native_rate, self.target_rate)
        try:
            while not self.stop_event.is_set() or not self.raw_queue.empty():
                try:
                    raw = self.raw_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                self.journal.append(converter.convert(raw))
        except Exception as exc:
            self.journal.finish(f"audio normalizer failed: {exc}")
            self.status_callback("fatal", {"reason": "AUDIO_NORMALIZER_FAILED", "detail": str(exc)})
            return
        self.journal.finish()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    def stop(self) -> None:
        self.stop_event.set()
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        if self.thread is not None:
            self.thread.join(timeout=3.0)
        if not self.journal.finished:
            self.journal.finish()


class WavSource:
    def __init__(
        self,
        journal: AudioJournal,
        path: Path,
        *,
        target_rate: int,
        realtime: bool,
        accelerated_factor: float = 4.0,
        status_callback: Callable[[str, dict[str, object]], None] | None = None,
    ) -> None:
        self.journal = journal
        self.path = Path(path).resolve()
        self.target_rate = target_rate
        self.realtime = realtime
        self.accelerated_factor = accelerated_factor
        self.status_callback = status_callback or (lambda _kind, _data: None)
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self.thread = threading.Thread(target=self._run, name="wav-source", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        import soundfile as sf

        try:
            with sf.SoundFile(self.path) as handle:
                source_rate = int(handle.samplerate)
                converter = _StreamingResampler(source_rate, self.target_rate)
                source_block = max(1, round(source_rate * 0.1))
                self.status_callback("source_started", {"mode": "wav", "path": str(self.path), "native_sample_rate": source_rate, "pipeline_sample_rate": self.target_rate, "channels": int(handle.channels)})
                while not self.stop_event.is_set():
                    while self.pause_event.is_set() and not self.stop_event.is_set():
                        time.sleep(0.05)
                    data = handle.read(source_block, dtype="float32", always_2d=True)
                    if not data.size:
                        break
                    mono = np.mean(data, axis=1, dtype=np.float32)
                    converted = converter.convert(mono)
                    self.journal.append(converted)
                    delay = len(converted) / self.target_rate
                    if self.realtime:
                        time.sleep(delay)
                    elif self.accelerated_factor > 0:
                        time.sleep(delay / self.accelerated_factor)
            self.journal.finish()
        except Exception as exc:
            self.journal.finish(f"WAV source failed: {exc}")
            self.status_callback("fatal", {"reason": "WAV_SOURCE_FAILED", "detail": str(exc)})

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=3.0)
        if not self.journal.finished:
            self.journal.finish()


def input_devices() -> list[dict[str, object]]:
    import sounddevice as sd

    rows = []
    for index, item in enumerate(sd.query_devices()):
        if int(item["max_input_channels"]) > 0:
            rows.append(
                {
                    "index": index,
                    "name": str(item["name"]),
                    "channels": int(item["max_input_channels"]),
                    "default_sample_rate": int(round(float(item["default_samplerate"]))),
                }
            )
    return rows

