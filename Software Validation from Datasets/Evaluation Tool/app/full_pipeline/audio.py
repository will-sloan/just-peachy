"""Incremental file/microphone capture, normalization, and bounded queues."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, is_dataclass, replace
import hashlib
from pathlib import Path
import queue
import threading
import time
from typing import Any, Callable, Literal
import uuid

import numpy as np
import soundfile as sf

from app.inference_pipeline.audio_io.multichannel import apply_channel_policy
from app.inference_pipeline.audio_io.resample import resample_audio

from .cache import ContentAddressedCache, make_cache_key
from .models import NormalizedAudioFrame, RawAudioFrame, utc_now_text


DropPolicy = Literal["block", "drop_oldest", "drop_newest"]


class AudioReadTimeout(TimeoutError):
    """A live source had no frame yet; this is not end-of-stream."""


@dataclass(frozen=True)
class QueuePutResult:
    accepted: bool
    dropped: RawAudioFrame | NormalizedAudioFrame | None
    queue_depth: int
    dropped_frame_count: int
    blocked_sec: float
    reason: str | None
    closed: bool = False


class BoundedFrameQueue:
    """Condition-backed bounded queue with deterministic overflow semantics."""

    def __init__(self, max_frames: int, *, drop_policy: DropPolicy = "block") -> None:
        if max_frames < 1:
            raise ValueError("max_frames must be >= 1")
        if drop_policy not in {"block", "drop_oldest", "drop_newest"}:
            raise ValueError(f"unsupported drop policy: {drop_policy}")
        self.max_frames = int(max_frames)
        self.drop_policy = drop_policy
        self._items: deque[Any] = deque()
        self._condition = threading.Condition()
        self._closed = False
        self._dropped = 0
        self._max_depth = 0
        self._pending_dropped_samples = 0
        self._pending_discontinuity = False

    def put(self, item: Any) -> QueuePutResult:
        started = time.monotonic()
        dropped = None
        reason = None
        with self._condition:
            while len(self._items) >= self.max_frames and not self._closed:
                if self.drop_policy == "drop_newest":
                    self._dropped += 1
                    self._pending_dropped_samples += _frame_sample_count(item) + int(
                        getattr(item, "dropped_source_samples_before", 0)
                    )
                    self._pending_discontinuity = True
                    return QueuePutResult(
                        False,
                        item,
                        len(self._items),
                        self._dropped,
                        0.0,
                        "drop_newest",
                    )
                if self.drop_policy == "drop_oldest":
                    dropped = self._items.popleft()
                    self._dropped += 1
                    gap_samples = _frame_sample_count(dropped) + int(
                        getattr(dropped, "dropped_source_samples_before", 0)
                    )
                    if self._items:
                        self._items[0] = _with_discontinuity(
                            self._items[0], gap_samples
                        )
                    else:
                        self._pending_dropped_samples += gap_samples
                        self._pending_discontinuity = True
                    reason = "drop_oldest"
                    break
                self._condition.wait()
            if self._closed:
                return QueuePutResult(
                    False,
                    None,
                    len(self._items),
                    self._dropped,
                    time.monotonic() - started,
                    "queue_closed",
                    True,
                )
            if self._pending_discontinuity:
                item = _with_discontinuity(item, self._pending_dropped_samples)
                self._pending_dropped_samples = 0
                self._pending_discontinuity = False
            self._items.append(item)
            self._max_depth = max(self._max_depth, len(self._items))
            self._condition.notify_all()
            return QueuePutResult(
                True,
                dropped,
                len(self._items),
                self._dropped,
                time.monotonic() - started,
                reason,
            )

    def get(self, timeout_sec: float | None = None) -> Any | None:
        deadline = None if timeout_sec is None else time.monotonic() + timeout_sec
        with self._condition:
            while not self._items and not self._closed:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return None
                self._condition.wait(remaining)
            if not self._items:
                return None
            value = self._items.popleft()
            self._condition.notify_all()
            return value

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    @property
    def closed(self) -> bool:
        with self._condition:
            return self._closed

    @property
    def depth(self) -> int:
        with self._condition:
            return len(self._items)

    @property
    def dropped_count(self) -> int:
        with self._condition:
            return self._dropped

    @property
    def max_depth(self) -> int:
        with self._condition:
            return self._max_depth


def _frame_sample_count(value: object) -> int:
    samples = getattr(value, "samples", None)
    if samples is None:
        return 0
    try:
        return int(np.asarray(samples).shape[0])
    except (TypeError, ValueError, IndexError):
        return 0


def _with_discontinuity(value: Any, dropped_samples: int) -> Any:
    if not is_dataclass(value):
        return value
    fields = getattr(value, "__dataclass_fields__", {})
    if not {
        "discontinuity_before",
        "dropped_source_samples_before",
    }.issubset(fields):
        return value
    return replace(
        value,
        discontinuity_before=True,
        dropped_source_samples_before=(
            int(getattr(value, "dropped_source_samples_before", 0))
            + int(dropped_samples)
        ),
    )


class StreamingAudioNormalizer:
    """Downmix and framewise polyphase-resample source audio to mono 16 kHz.

    The normalization provenance calls out framewise operation explicitly; it is
    never represented as source-native audio.  Cumulative output indexing keeps
    media time monotonic even when frame length ratios do not divide exactly.
    """

    def __init__(
        self,
        target_sample_rate_hz: int = 16000,
        *,
        cache: ContentAddressedCache | None = None,
    ) -> None:
        if target_sample_rate_hz != 16000:
            raise ValueError(
                "the full-pipeline internal sample rate is fixed at 16000 Hz"
            )
        self.target_sample_rate_hz = target_sample_rate_hz
        self.cache = cache
        self._next_sample = 0

    def normalize(self, frame: RawAudioFrame) -> NormalizedAudioFrame:
        raw = np.ascontiguousarray(frame.samples, dtype=np.float32)
        source_digest = hashlib.sha256(raw.tobytes()).hexdigest()
        key = make_cache_key(
            artifact_kind="decoded_resampled_audio",
            role="normalized_runtime_audio",
            source_audio_sha256=source_digest,
            source_start_sample=frame.source_sample_start,
            source_end_sample=frame.source_sample_end,
            sample_rate_hz=frame.sample_rate_hz,
            window_identity={
                "source_channel_count": frame.channel_count,
                "source_shape": list(raw.shape),
            },
            preprocessing_identity={
                "channel_policy": "mono_mean",
                "resampler": "scipy.signal.resample_poly_framewise",
                "target_sample_rate_hz": self.target_sample_rate_hz,
            },
            model_identity={"decoder": "source_float32_frame.v1"},
            configuration_identity={
                "normalization_policy_id": "full_pipeline_audio_normalization.v1"
            },
        )
        cached = self.cache.load(key) if self.cache is not None else None
        if cached is None:
            mono, channel_metadata = apply_channel_policy(raw, "mono")
            converted = resample_audio(
                mono,
                frame.sample_rate_hz,
                self.target_sample_rate_hz,
            )[:, 0]
            if self.cache is not None:
                self.cache.publish(
                    key,
                    {
                        "samples": converted.tolist(),
                        "channel_metadata": dict(channel_metadata),
                    },
                )
        else:
            payload = dict(cached)
            converted = np.asarray(payload["samples"], dtype=np.float32)
            channel_metadata = dict(payload["channel_metadata"])
        mapped_dropped_samples = round(
            frame.dropped_source_samples_before
            * self.target_sample_rate_hz
            / frame.sample_rate_hz
        )
        if frame.discontinuity_before and mapped_dropped_samples:
            self._next_sample += mapped_dropped_samples
        start = self._next_sample
        end = start + int(converted.size)
        self._next_sample = end
        return NormalizedAudioFrame(
            frame_id=frame.frame_id,
            sequence=frame.sequence,
            samples=converted,
            sample_rate_hz=self.target_sample_rate_hz,
            sample_start=start,
            sample_end=end,
            audio_start_sec=start / self.target_sample_rate_hz,
            audio_end_sec=end / self.target_sample_rate_hz,
            source_sample_rate_hz=frame.sample_rate_hz,
            source_channel_count=frame.channel_count,
            source_sample_start=frame.source_sample_start,
            source_sample_end=frame.source_sample_end,
            source_audio_start_sec=frame.audio_start_sec,
            source_audio_end_sec=frame.audio_end_sec,
            capture_start_monotonic_ns=frame.capture_start_monotonic_ns,
            capture_end_monotonic_ns=frame.capture_end_monotonic_ns,
            capture_start_utc=frame.capture_start_utc,
            capture_end_utc=frame.capture_end_utc,
            source_clock_id=frame.source_clock_id,
            source_clock_type=frame.source_clock_type,
            discontinuity_before=frame.discontinuity_before,
            dropped_source_samples_before=mapped_dropped_samples,
            provenance={
                "normalization_policy_id": "full_pipeline_audio_normalization.v1",
                "channel_policy": dict(channel_metadata),
                "resampler": "scipy.signal.resample_poly_framewise",
                "source_sample_rate_hz": frame.sample_rate_hz,
                "target_sample_rate_hz": self.target_sample_rate_hz,
                "source_channel_count": frame.channel_count,
                "target_channel_count": 1,
                "dropped_source_samples_before": frame.dropped_source_samples_before,
                "mapped_dropped_internal_samples_before": mapped_dropped_samples,
                "decoded_resampled_audio_cache_key": key.digest,
                "decoded_resampled_audio_cache_hit": cached is not None,
            },
        )

    def reset(self) -> None:
        self._next_sample = 0


class FileAudioSource:
    """Incrementally read a file at realtime or accelerated engineering cadence."""

    def __init__(
        self,
        path: Path,
        *,
        frame_duration_ms: int = 100,
        pace: float = 0.0,
        recording_id: str | None = None,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
        utc_clock: Callable[[], str] = utc_now_text,
    ) -> None:
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        if frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be positive")
        if pace < 0:
            raise ValueError("pace must be >= 0; 0 means accelerated")
        self.frame_duration_ms = int(frame_duration_ms)
        self.pace = float(pace)
        self.recording_id = recording_id or self.path.stem
        self.clock_ns = clock_ns
        self.utc_clock = utc_clock
        self._file: sf.SoundFile | None = None
        self._file_lock = threading.RLock()
        self._sequence = 0
        self._sample = 0
        self._started_ns: int | None = None
        self._stop = threading.Event()
        self._control = threading.Condition()
        self._paused = False
        self._pause_effective_ns: int | None = None

    def start(self) -> None:
        with self._file_lock:
            if self._file is not None:
                raise RuntimeError("file source is already started")
            self._file = sf.SoundFile(self.path, mode="r")
            self._sequence = 0
            self._sample = 0
            self._started_ns = self.clock_ns()
            self._stop.clear()
        with self._control:
            self._paused = False
            self._pause_effective_ns = None
            self._control.notify_all()

    def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
        del timeout_sec
        if self._stop.is_set():
            return None
        if not self._wait_until_resumed():
            return None
        # A coordinator stop and the producer's ``finally`` may race.  Keep a
        # read and its SoundFile close mutually exclusive so libsndfile never
        # sees a close while it is reading or a second close of the same handle.
        with self._file_lock:
            if self._stop.is_set():
                return None
            stream = self._file
            if stream is None:
                raise RuntimeError("file source is not started")
            sample_rate = int(stream.samplerate)
            channel_count = int(stream.channels)
            count = max(1, round(sample_rate * self.frame_duration_ms / 1000))
            start = self._sample
            audio = stream.read(count, dtype="float32", always_2d=True)
            if audio.size == 0:
                return None
            end = start + int(audio.shape[0])
            if self.pace > 0 and self._started_ns is not None:
                target = self._started_ns + int(
                    (end / sample_rate) * 1e9 / self.pace
                )
                remaining = (target - self.clock_ns()) / 1e9
                if remaining > 0:
                    self._stop.wait(remaining)
            if self._stop.is_set():
                return None
            self._sequence += 1
            self._sample = end
            now_ns = self.clock_ns()
            utc = self.utc_clock()
            return RawAudioFrame(
                frame_id=f"frame_{self._sequence:09d}",
                sequence=self._sequence,
                samples=audio,
                sample_rate_hz=sample_rate,
                channel_count=channel_count,
                source_sample_start=start,
                source_sample_end=end,
                audio_start_sec=start / sample_rate,
                audio_end_sec=end / sample_rate,
                capture_start_monotonic_ns=now_ns,
                capture_end_monotonic_ns=now_ns,
                capture_start_utc=utc,
                capture_end_utc=utc,
                source_clock_id=f"external_media:{self.recording_id}",
                source_clock_type="external_media",
            )

    def stop(self) -> None:
        # Signal first so a paced read can leave its wait while this caller is
        # waiting to acquire the file lock.
        self._stop.set()
        with self._control:
            self._paused = False
            self._pause_effective_ns = None
            self._control.notify_all()
        with self._file_lock:
            stream, self._file = self._file, None
            if stream is not None:
                stream.close()

    def pause(self) -> None:
        """Pause before the next frame is read from the file."""

        with self._control:
            if not self._stop.is_set():
                self._paused = True

    def resume(self) -> None:
        """Resume without letting realtime pacing catch up after the pause."""

        with self._control:
            if not self._paused:
                return
            if self._pause_effective_ns is not None and self._started_ns is not None:
                self._started_ns += max(0, self.clock_ns() - self._pause_effective_ns)
            self._paused = False
            self._pause_effective_ns = None
            self._control.notify_all()

    def _wait_until_resumed(self) -> bool:
        with self._control:
            while self._paused and not self._stop.is_set():
                if self._pause_effective_ns is None:
                    self._pause_effective_ns = self.clock_ns()
                self._control.wait(timeout=0.25)
            return not self._stop.is_set()

    def reset(self) -> None:
        self.stop()
        self.start()

    def status(self) -> dict[str, object]:
        with self._control:
            paused = self._paused
        with self._file_lock:
            running = self._file is not None and not self._stop.is_set()
        return {
            "source_mode": "file_realtime" if self.pace == 1 else "file_accelerated",
            "path": str(self.path),
            "pace": self.pace,
            "frame_duration_ms": self.frame_duration_ms,
            "sequence": self._sequence,
            "source_sample_index": self._sample,
            "running": running,
            "paused": paused,
        }


class MicrophoneAudioSource:
    """SoundDevice callback source preserving the device-native rate/channels."""

    def __init__(
        self,
        *,
        device: int | str | None = None,
        source_sample_rate_hz: int | None = None,
        source_channels: int | None = None,
        frame_duration_ms: int = 100,
        max_callback_frames: int = 16,
        module_importer: Callable[[str], Any] = __import__,
    ) -> None:
        self.device = device
        self.source_sample_rate_hz = source_sample_rate_hz
        self.source_channels = source_channels
        self.frame_duration_ms = int(frame_duration_ms)
        self.max_callback_frames = int(max_callback_frames)
        self.module_importer = module_importer
        self._queue: queue.Queue[tuple[np.ndarray, int, str, bool, int] | None] = (
            queue.Queue(maxsize=max_callback_frames)
        )
        self._stream: Any | None = None
        self._sequence = 0
        self._sample = 0
        self._dropped_samples = 0
        self._dropped_samples_total = 0
        self._paused_dropped_samples_total = 0
        self._clock_id = f"microphone:{uuid.uuid4().hex[:12]}"
        self._control = threading.RLock()
        self._paused = False

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("microphone source is already started")
        with self._control:
            self._paused = False
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
        try:
            sd = self.module_importer("sounddevice")
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                "sounddevice is required for microphone capture; use file smoke when unavailable"
            ) from exc
        info = sd.query_devices(self.device, "input")
        rate = int(
            self.source_sample_rate_hz or round(float(info["default_samplerate"]))
        )
        available_channels = int(info["max_input_channels"])
        channels = int(self.source_channels or min(2, available_channels))
        if rate <= 0 or channels <= 0 or channels > available_channels:
            raise RuntimeError("invalid microphone source format")
        blocksize = max(1, round(rate * self.frame_duration_ms / 1000))
        self.source_sample_rate_hz = rate
        self.source_channels = channels

        def callback(
            indata: np.ndarray, frames: int, _time_info: Any, status: Any
        ) -> None:
            now_ns = time.perf_counter_ns()
            utc = utc_now_text()
            with self._control:
                if self._paused:
                    self._dropped_samples += int(frames)
                    self._dropped_samples_total += int(frames)
                    self._paused_dropped_samples_total += int(frames)
                    return
                dropped_before = self._dropped_samples
                discontinuity = bool(status) or dropped_before > 0
                row = (
                    np.array(indata[:frames], dtype=np.float32, copy=True),
                    now_ns,
                    utc,
                    discontinuity,
                    dropped_before,
                )
                try:
                    self._queue.put_nowait(row)
                    self._dropped_samples = 0
                except queue.Full:
                    self._dropped_samples += int(frames)
                    self._dropped_samples_total += int(frames)

        self._stream = sd.InputStream(
            device=self.device,
            samplerate=rate,
            channels=channels,
            dtype="float32",
            blocksize=blocksize,
            callback=callback,
        )
        self._stream.start()

    def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
        if self._stream is None:
            raise RuntimeError("microphone source is not started")
        try:
            row = self._queue.get(timeout=timeout_sec)
        except queue.Empty as exc:
            raise AudioReadTimeout("microphone frame wait timed out") from exc
        if row is None:
            return None
        audio, capture_ns, utc, discontinuity, dropped = row
        start = self._sample + int(dropped)
        end = start + int(audio.shape[0])
        self._sample = end
        self._sequence += 1
        rate = int(self.source_sample_rate_hz or 0)
        channels = int(self.source_channels or 0)
        return RawAudioFrame(
            frame_id=f"frame_{self._sequence:09d}",
            sequence=self._sequence,
            samples=audio,
            sample_rate_hz=rate,
            channel_count=channels,
            source_sample_start=start,
            source_sample_end=end,
            audio_start_sec=start / rate,
            audio_end_sec=end / rate,
            capture_start_monotonic_ns=capture_ns,
            capture_end_monotonic_ns=capture_ns,
            capture_start_utc=utc,
            capture_end_utc=utc,
            source_clock_id=self._clock_id,
            source_clock_type="audio_sample",
            discontinuity_before=discontinuity,
            dropped_source_samples_before=dropped,
        )

    def stop(self) -> None:
        with self._control:
            self._paused = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

    def pause(self) -> None:
        """Drop live samples after the current source frame boundary."""

        with self._control:
            if self._stream is None or self._paused:
                return
            self._paused = True
            while True:
                try:
                    row = self._queue.get_nowait()
                except queue.Empty:
                    break
                if row is None:
                    continue
                audio, _capture_ns, _utc, _discontinuity, dropped = row
                skipped = int(audio.shape[0]) + int(dropped)
                self._dropped_samples += skipped
                self._dropped_samples_total += skipped
                self._paused_dropped_samples_total += skipped

    def resume(self) -> None:
        with self._control:
            self._paused = False

    def reset(self) -> None:
        self.stop()
        self._sequence = 0
        self._sample = 0
        self._dropped_samples = 0
        self._dropped_samples_total = 0
        self._paused_dropped_samples_total = 0
        self.start()

    def status(self) -> dict[str, object]:
        with self._control:
            paused = self._paused
            dropped_pending = self._dropped_samples
            dropped_total = self._dropped_samples_total
            paused_dropped_total = self._paused_dropped_samples_total
        return {
            "source_mode": "microphone",
            "device": self.device,
            "source_sample_rate_hz": self.source_sample_rate_hz,
            "source_channels": self.source_channels,
            "frame_duration_ms": self.frame_duration_ms,
            "callback_queue_depth": self._queue.qsize(),
            "dropped_source_samples_pending": dropped_pending,
            "dropped_source_samples_total": dropped_total,
            "paused_dropped_source_samples_total": paused_dropped_total,
            "running": self._stream is not None,
            "paused": paused,
        }


class PlaybackAudioSource:
    """Synchronously play every exact source frame while forwarding it downstream."""

    def __init__(
        self,
        source: Any,
        *,
        device: int | str | None = None,
        module_importer: Callable[[str], Any] = __import__,
    ) -> None:
        self.source = source
        self.device = device
        self.module_importer = module_importer
        self._stream: Any | None = None
        self._format: tuple[int, int] | None = None

    def start(self) -> None:
        self._close_output()
        self.source.start()

    def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
        frame = self.source.read(timeout_sec=timeout_sec)
        if frame is None:
            return None
        self._ensure_output(frame)
        assert self._stream is not None
        self._stream.write(np.ascontiguousarray(frame.samples, dtype=np.float32))
        return frame

    def _ensure_output(self, frame: RawAudioFrame) -> None:
        source_format = (int(frame.sample_rate_hz), int(frame.channel_count))
        if self._stream is not None:
            if source_format != self._format:
                raise RuntimeError("playback source format changed during the session")
            return
        try:
            sd = self.module_importer("sounddevice")
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                "sounddevice is required when file playback is enabled"
            ) from exc
        stream = sd.OutputStream(
            device=self.device,
            samplerate=source_format[0],
            channels=source_format[1],
            dtype="float32",
        )
        try:
            stream.start()
        except BaseException:
            stream.close()
            raise
        self._stream = stream
        self._format = source_format

    def pause(self) -> None:
        if hasattr(self.source, "pause"):
            self.source.pause()

    def resume(self) -> None:
        if hasattr(self.source, "resume"):
            self.source.resume()

    def stop(self) -> None:
        output_error: BaseException | None = None
        try:
            self._close_output()
        except BaseException as exc:
            output_error = exc
        try:
            self.source.stop()
        finally:
            if output_error is not None:
                raise output_error

    def _close_output(self) -> None:
        stream, self._stream = self._stream, None
        self._format = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    def reset(self) -> None:
        self.stop()
        self.source.reset()

    def status(self) -> dict[str, object]:
        return {
            **dict(self.source.status()),
            "playback_enabled": True,
            "playback_running": self._stream is not None,
            "playback_device": self.device,
        }


class RecordingAudioSource:
    """Write exact source frames to a user-authorized local WAV while forwarding.

    The wrapper is deliberately source-neutral and contains no inference.  It
    opens the WAV after the first frame reveals the device format, rejects a
    mid-session format change, and never overwrites an existing recording.
    """

    def __init__(self, source: Any, path: Path) -> None:
        self.source = source
        self.path = Path(path).resolve()
        self._file: sf.SoundFile | None = None
        self._format: tuple[int, int] | None = None
        self._frames_written = 0

    def start(self) -> None:
        if self.path.exists():
            raise FileExistsError(f"refusing to overwrite recorded input: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._frames_written = 0
        self._format = None
        self.source.start()

    def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
        frame = self.source.read(timeout_sec=timeout_sec)
        if frame is None:
            return None
        source_format = (int(frame.sample_rate_hz), int(frame.channel_count))
        if self._file is None:
            self._file = sf.SoundFile(
                self.path,
                mode="x",
                samplerate=source_format[0],
                channels=source_format[1],
                format="WAV",
                subtype="FLOAT",
            )
            self._format = source_format
        elif source_format != self._format:
            raise RuntimeError("recorded input format changed during the session")
        samples = np.asarray(frame.samples, dtype=np.float32)
        if samples.ndim == 1:
            samples = samples[:, None]
        self._file.write(np.ascontiguousarray(samples))
        self._file.flush()
        self._frames_written += int(samples.shape[0])
        return frame

    def stop(self) -> None:
        recording_error: BaseException | None = None
        file, self._file = self._file, None
        if file is not None:
            try:
                file.flush()
                file.close()
            except BaseException as exc:
                recording_error = exc
        try:
            self.source.stop()
        finally:
            if recording_error is not None:
                raise recording_error

    def pause(self) -> None:
        if hasattr(self.source, "pause"):
            self.source.pause()

    def resume(self) -> None:
        if hasattr(self.source, "resume"):
            self.source.resume()

    def reset(self) -> None:
        raise RuntimeError("a local input recording cannot be reset in place")

    def status(self) -> dict[str, object]:
        return {
            **dict(self.source.status()),
            "input_recording_enabled": True,
            "input_recording_path": str(self.path),
            "input_recording_frames_written": self._frames_written,
            "input_recording_open": self._file is not None,
            "input_recording_upload_performed": False,
        }


class DurationLimitedAudioSource:
    """Stop any source after a bounded amount of source media time."""

    def __init__(self, source: Any, duration_sec: float) -> None:
        if duration_sec <= 0:
            raise ValueError("duration_sec must be positive")
        self.source = source
        self.duration_sec = float(duration_sec)
        self._done = False

    def start(self) -> None:
        self._done = False
        self.source.start()

    def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
        if self._done:
            return None
        frame = self.source.read(timeout_sec=timeout_sec)
        if frame is None:
            return None
        if frame.audio_start_sec >= self.duration_sec:
            self._done = True
            self.source.stop()
            return None
        if frame.audio_end_sec >= self.duration_sec:
            keep = max(
                0,
                min(
                    frame.samples.shape[0],
                    round(
                        (self.duration_sec - frame.audio_start_sec)
                        * frame.sample_rate_hz
                    ),
                ),
            )
            frame = replace(
                frame,
                samples=frame.samples[:keep],
                source_sample_end=frame.source_sample_start + keep,
                audio_end_sec=frame.audio_start_sec + keep / frame.sample_rate_hz,
            )
            self._done = True
        return frame

    def stop(self) -> None:
        self._done = True
        self.source.stop()

    def pause(self) -> None:
        if hasattr(self.source, "pause"):
            self.source.pause()

    def resume(self) -> None:
        if hasattr(self.source, "resume"):
            self.source.resume()

    def reset(self) -> None:
        self._done = False
        self.source.reset()

    def status(self) -> dict[str, object]:
        return {**dict(self.source.status()), "duration_limit_sec": self.duration_sec}
