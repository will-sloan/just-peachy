"""Continuously capture microphone audio while completed windows run inference."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import queue
import sys
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence, TextIO

import numpy as np


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
DEFAULT_CONFIG_PATH = TOOL_ROOT / "configs" / "inference" / "live_mic_realtime_whisper_tiny.yaml"
DEFAULT_OUTPUT_ROOT = TOOL_ROOT / "runs" / "live_mic_realtime"
DEFAULT_REPORT_DIR = TOOL_ROOT / "reports" / "component_reports" / "live_mic_realtime"
REQUIRED_PREDICTION_FIELDS = (
    "recording_id",
    "utt_id",
    "start_sec",
    "end_sec",
    "speaker_label",
    "text",
)
DROP_POLICIES = ("drop_oldest", "drop_newest", "block")

if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.inference_pipeline.audio_io.resample import resample_audio  # noqa: E402
from app.inference_pipeline.config import PipelineConfig  # noqa: E402
from app.inference_pipeline.realtime import (  # noqa: E402
    SPEAKER_STATUS_CONFIRMED,
    SpeakerEvidenceAccumulator,
    RealtimeTranscriptStitcher,
)
from app.utils.json_utils import write_json  # noqa: E402

import live_mic_smoke  # noqa: E402


DropPolicy = Literal["drop_oldest", "drop_newest", "block"]
FrameCallback = Callable[[np.ndarray, float, float], None]


class LiveMicRealtimeError(RuntimeError):
    """Raised when realtime microphone validation cannot continue."""


class MicrophoneUnavailableError(LiveMicRealtimeError):
    """Raised when optional microphone capture support is unavailable."""


class FrameSource(Protocol):
    """Protocol for realtime microphone or synthetic frame sources."""

    def capture(
        self,
        *,
        on_frames: FrameCallback,
        duration_sec: float,
        sample_rate: int,
        stop_event: threading.Event,
    ) -> None:
        """Continuously call on_frames until duration elapses or stop_event is set."""


@dataclass(frozen=True)
class FrameBatch:
    """Captured audio frames plus monotonic capture timing."""

    audio: np.ndarray
    capture_start_monotonic: float
    capture_end_monotonic: float


@dataclass(frozen=True)
class WindowAudio:
    """A completed inference window assembled from continuous frames."""

    window_index: int
    audio: np.ndarray
    window_start_sec: float
    window_end_sec: float
    capture_start_monotonic: float
    capture_end_monotonic: float


@dataclass(frozen=True)
class InferenceWindow:
    """A completed window ready for the background inference worker."""

    window_index: int
    audio: np.ndarray
    audio_path: Path
    sample_rate: int
    window_start_sec: float
    window_end_sec: float
    capture_start_monotonic: float
    capture_end_monotonic: float
    purpose: Literal["asr", "speaker"] = "asr"

    @property
    def duration_sec(self) -> float:
        return _round_seconds(self.window_end_sec - self.window_start_sec)


@dataclass(frozen=True)
class QueuedWindow:
    """Inference window with enqueue metadata."""

    window: InferenceWindow
    enqueue_monotonic: float
    queue_depth_at_enqueue: int
    dropped_window_count_at_enqueue: int
    enqueue_blocked_sec: float = 0.0


@dataclass(frozen=True)
class QueuePutResult:
    """Result of adding a window to the bounded inference queue."""

    enqueued: QueuedWindow | None
    dropped: InferenceWindow | None
    queue_depth_at_enqueue: int
    dropped_window_count: int
    enqueue_blocked_sec: float
    drop_reason: str | None = None
    closed: bool = False


@dataclass(frozen=True)
class QueueGetResult:
    """Result of taking a window from the inference queue."""

    queued_window: QueuedWindow
    dequeue_monotonic: float
    queue_depth_at_dequeue: int
    queue_depth_after_dequeue: int


@dataclass(frozen=True)
class LiveMicRealtimeResult:
    """Summary of one realtime live microphone run."""

    run_id: str
    run_dir: Path
    predictions_path: Path
    diagnostics_path: Path
    summary_path: Path
    component_report_path: Path | None
    dry_run: bool
    asr_mode: str
    microphone_capture_tested: bool
    audio_retained: bool
    window_count: int
    prediction_count: int
    dropped_window_count: int
    max_queue_depth: int
    config_path: Path
    availability: dict[str, object]

    def to_jsonable(self) -> dict[str, object]:
        """Return a JSON-safe run summary."""

        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "predictions_path": str(self.predictions_path),
            "diagnostics_path": str(self.diagnostics_path),
            "summary_path": str(self.summary_path),
            "component_report_path": (
                str(self.component_report_path) if self.component_report_path is not None else None
            ),
            "dry_run": self.dry_run,
            "asr_mode": self.asr_mode,
            "microphone_capture_tested": self.microphone_capture_tested,
            "audio_retained": self.audio_retained,
            "window_count": self.window_count,
            "prediction_count": self.prediction_count,
            "dropped_window_count": self.dropped_window_count,
            "max_queue_depth": self.max_queue_depth,
            "config_path": str(self.config_path),
            "availability": self.availability,
        }


@dataclass
class _RunState:
    """Thread-shared counters and rows."""

    prediction_rows: list[dict[str, object]] = field(default_factory=list)
    diagnostics_rows: list[dict[str, object]] = field(default_factory=list)
    audio_paths: list[Path] = field(default_factory=list)
    worker_errors: list[str] = field(default_factory=list)
    windows_completed: int = 0
    windows_enqueued: int = 0
    windows_dropped: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def increment(self, key: str, value: int = 1) -> None:
        with self.lock:
            setattr(self, key, int(getattr(self, key)) + value)

    def add_audio_path(self, path: Path) -> None:
        with self.lock:
            self.audio_paths.append(path)

    def add_worker_error(self, message: str) -> None:
        with self.lock:
            self.worker_errors.append(message)


class WindowWorkQueue:
    """Bounded queue with deterministic drop policies for inference windows."""

    def __init__(self, max_size: int) -> None:
        if max_size < 1:
            raise LiveMicRealtimeError("--max-queue must be >= 1")
        self.max_size = max_size
        self._items: deque[QueuedWindow] = deque()
        self._condition = threading.Condition()
        self._closed = False
        self._dropped_count = 0
        self._max_depth = 0

    def enqueue(self, window: InferenceWindow, *, drop_policy: DropPolicy) -> QueuePutResult:
        """Add a window, dropping or blocking deterministically when the queue is full."""

        if drop_policy not in DROP_POLICIES:
            raise LiveMicRealtimeError(f"unknown drop policy: {drop_policy}")

        blocked_started_at = time.monotonic()
        dropped: InferenceWindow | None = None
        drop_reason: str | None = None
        with self._condition:
            if self._closed:
                return QueuePutResult(
                    enqueued=None,
                    dropped=None,
                    queue_depth_at_enqueue=len(self._items),
                    dropped_window_count=self._dropped_count,
                    enqueue_blocked_sec=0.0,
                    closed=True,
                )

            if len(self._items) >= self.max_size:
                if drop_policy == "drop_newest":
                    self._dropped_count += 1
                    return QueuePutResult(
                        enqueued=None,
                        dropped=window,
                        queue_depth_at_enqueue=len(self._items),
                        dropped_window_count=self._dropped_count,
                        enqueue_blocked_sec=0.0,
                        drop_reason="drop_newest",
                    )
                if drop_policy == "drop_oldest":
                    dropped = self._items.popleft().window
                    self._dropped_count += 1
                    drop_reason = "drop_oldest"
                    self._condition.notify_all()
                else:
                    while len(self._items) >= self.max_size and not self._closed:
                        self._condition.wait(timeout=0.05)

            if self._closed:
                return QueuePutResult(
                    enqueued=None,
                    dropped=dropped,
                    queue_depth_at_enqueue=len(self._items),
                    dropped_window_count=self._dropped_count,
                    enqueue_blocked_sec=time.monotonic() - blocked_started_at,
                    drop_reason=drop_reason,
                    closed=True,
                )

            queue_depth = len(self._items) + 1
            queued = QueuedWindow(
                window=window,
                enqueue_monotonic=time.monotonic(),
                queue_depth_at_enqueue=queue_depth,
                dropped_window_count_at_enqueue=self._dropped_count,
                enqueue_blocked_sec=(
                    time.monotonic() - blocked_started_at if drop_policy == "block" else 0.0
                ),
            )
            self._items.append(queued)
            self._max_depth = max(self._max_depth, len(self._items))
            self._condition.notify_all()
            return QueuePutResult(
                enqueued=queued,
                dropped=dropped,
                queue_depth_at_enqueue=len(self._items),
                dropped_window_count=self._dropped_count,
                enqueue_blocked_sec=queued.enqueue_blocked_sec,
                drop_reason=drop_reason,
            )

    def get(self) -> QueueGetResult | None:
        """Return the next queued window, or None after the queue is closed and drained."""

        with self._condition:
            while not self._items:
                if self._closed:
                    return None
                self._condition.wait(timeout=0.05)
            depth_before = len(self._items)
            queued = self._items.popleft()
            depth_after = len(self._items)
            self._condition.notify_all()
            return QueueGetResult(
                queued_window=queued,
                dequeue_monotonic=time.monotonic(),
                queue_depth_at_dequeue=depth_before,
                queue_depth_after_dequeue=depth_after,
            )

    def close(self) -> None:
        """Wake waiters and prevent future enqueues."""

        with self._condition:
            self._closed = True
            self._condition.notify_all()

    @property
    def dropped_count(self) -> int:
        with self._condition:
            return self._dropped_count

    @property
    def max_depth(self) -> int:
        with self._condition:
            return self._max_depth


@dataclass(frozen=True)
class _BatchSpan:
    start_sample: int
    end_sample: int
    capture_start_monotonic: float
    capture_end_monotonic: float


class WindowAssembler:
    """Assemble fixed windows and overlapping hops from a continuous frame stream."""

    def __init__(self, *, sample_rate: int, window_sec: float, hop_sec: float) -> None:
        self.sample_rate = sample_rate
        self.window_frames = max(1, int(round(window_sec * sample_rate)))
        self.hop_frames = max(1, int(round(hop_sec * sample_rate)))
        self._buffer = np.zeros(0, dtype=np.float32)
        self._buffer_start_sample = 0
        self._total_samples = 0
        self._next_window_start_sample = 0
        self._window_index = 0
        self._spans: deque[_BatchSpan] = deque()

    def add_frames(
        self,
        frames: np.ndarray,
        *,
        capture_start_monotonic: float,
        capture_end_monotonic: float,
    ) -> list[WindowAudio]:
        """Add one frame batch and return any completed inference windows."""

        audio = _mono_float32(frames)
        if audio.size == 0:
            return []

        batch_start_sample = self._total_samples
        batch_end_sample = batch_start_sample + int(audio.size)
        self._total_samples = batch_end_sample
        self._spans.append(
            _BatchSpan(
                start_sample=batch_start_sample,
                end_sample=batch_end_sample,
                capture_start_monotonic=capture_start_monotonic,
                capture_end_monotonic=capture_end_monotonic,
            )
        )
        self._buffer = np.concatenate((self._buffer, audio))

        windows: list[WindowAudio] = []
        while self._next_window_start_sample + self.window_frames <= (
            self._buffer_start_sample + int(self._buffer.size)
        ):
            start_sample = self._next_window_start_sample
            end_sample = start_sample + self.window_frames
            relative_start = start_sample - self._buffer_start_sample
            relative_end = relative_start + self.window_frames
            self._window_index += 1
            window_audio = np.array(self._buffer[relative_start:relative_end], copy=True)
            windows.append(
                WindowAudio(
                    window_index=self._window_index,
                    audio=window_audio,
                    window_start_sec=_round_seconds(start_sample / self.sample_rate),
                    window_end_sec=_round_seconds(end_sample / self.sample_rate),
                    capture_start_monotonic=self._time_for_sample(start_sample),
                    capture_end_monotonic=self._time_for_sample(end_sample),
                )
            )
            self._next_window_start_sample += self.hop_frames

        self._drop_consumed_samples()
        return windows

    def _drop_consumed_samples(self) -> None:
        drop_before = self._next_window_start_sample
        if drop_before <= self._buffer_start_sample:
            return
        drop_count = min(drop_before - self._buffer_start_sample, int(self._buffer.size))
        if drop_count <= 0:
            return
        self._buffer = self._buffer[drop_count:]
        self._buffer_start_sample += drop_count
        self._trim_spans_before(self._buffer_start_sample)

    def _time_for_sample(self, sample_index: int) -> float:
        if not self._spans:
            return time.monotonic()
        clamped_index = min(max(sample_index, self._spans[0].start_sample), self._spans[-1].end_sample)
        for span in self._spans:
            if span.start_sample <= clamped_index <= span.end_sample:
                if span.end_sample <= span.start_sample:
                    return span.capture_end_monotonic
                fraction = (clamped_index - span.start_sample) / (span.end_sample - span.start_sample)
                return span.capture_start_monotonic + fraction * (
                    span.capture_end_monotonic - span.capture_start_monotonic
                )
        return self._spans[-1].capture_end_monotonic

    def _trim_spans_before(self, sample_index: int) -> None:
        while self._spans and self._spans[0].end_sample <= sample_index:
            self._spans.popleft()
        if not self._spans or self._spans[0].start_sample >= sample_index:
            return
        first = self._spans.popleft()
        adjusted = _BatchSpan(
            start_sample=sample_index,
            end_sample=first.end_sample,
            capture_start_monotonic=self._interpolate_span_time(first, sample_index),
            capture_end_monotonic=first.capture_end_monotonic,
        )
        self._spans.appendleft(adjusted)

    @staticmethod
    def _interpolate_span_time(span: _BatchSpan, sample_index: int) -> float:
        if span.end_sample <= span.start_sample:
            return span.capture_end_monotonic
        fraction = (sample_index - span.start_sample) / (span.end_sample - span.start_sample)
        return span.capture_start_monotonic + fraction * (
            span.capture_end_monotonic - span.capture_start_monotonic
        )


class SoundDeviceFrameSource:
    """sounddevice.InputStream-backed realtime microphone frame source."""

    is_microphone = True

    def __init__(
        self,
        *,
        device: str | int | None = None,
        channels: int = 1,
        dtype: str = "float32",
        block_sec: float = 0.05,
        module_importer: Callable[[str], Any] | None = None,
    ) -> None:
        self.device = device
        self.channels = channels
        self.dtype = dtype
        self.block_sec = block_sec
        self._module_importer = module_importer or importlib.import_module
        self.status_messages: list[str] = []

    def capture(
        self,
        *,
        on_frames: FrameCallback,
        duration_sec: float,
        sample_rate: int,
        stop_event: threading.Event,
    ) -> None:
        sd = self._import_sounddevice()
        blocksize = max(1, int(round(self.block_sec * sample_rate)))
        callback_errors: list[BaseException] = []

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            _ = time_info
            if status:
                self.status_messages.append(str(status))
            capture_end = time.monotonic()
            capture_start = capture_end - (frames / sample_rate)
            try:
                on_frames(np.array(indata, dtype=np.float32, copy=True), capture_start, capture_end)
            except BaseException as exc:  # pragma: no cover - callback safety boundary
                callback_errors.append(exc)
                stop_event.set()

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.device,
                blocksize=blocksize,
                callback=callback,
            ):
                end_at = time.monotonic() + duration_sec
                while time.monotonic() < end_at and not stop_event.is_set():
                    time.sleep(min(0.1, max(0.0, end_at - time.monotonic())))
        except Exception as exc:  # pragma: no cover - hardware boundary
            raise MicrophoneUnavailableError(
                "Microphone capture failed. Check OS microphone permission, the selected "
                f"input device, and sample rate {sample_rate}: {exc}"
            ) from exc
        if callback_errors:
            raise MicrophoneUnavailableError(
                f"Microphone callback failed: {callback_errors[0]}"
            ) from callback_errors[0]

    def _import_sounddevice(self) -> Any:
        try:
            return self._module_importer("sounddevice")
        except ModuleNotFoundError as exc:
            raise MicrophoneUnavailableError(
                "Missing optional microphone dependency 'sounddevice'. Install it in the "
                "repository .venv for real microphone capture, or rerun with --dry-run."
            ) from exc


class DryRunFrameSource:
    """Synthetic realtime frame source used by --dry-run."""

    is_microphone = False

    def __init__(self, *, frame_sec: float = 0.05, real_time: bool = True) -> None:
        self.frame_sec = frame_sec
        self.real_time = real_time

    def capture(
        self,
        *,
        on_frames: FrameCallback,
        duration_sec: float,
        sample_rate: int,
        stop_event: threading.Event,
    ) -> None:
        frames_per_batch = max(1, int(round(self.frame_sec * sample_rate)))
        total_frames = max(1, int(round(duration_sec * sample_rate)))
        emitted = 0
        phase = 0.0
        while emitted < total_frames and not stop_event.is_set():
            batch_frames = min(frames_per_batch, total_frames - emitted)
            if self.real_time:
                capture_start = time.monotonic()
                time.sleep(batch_frames / sample_rate)
                capture_end = time.monotonic()
            else:
                capture_start = time.monotonic()
                capture_end = capture_start
            t = (np.arange(batch_frames, dtype=np.float32) + phase) / sample_rate
            audio = (0.02 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)
            phase += batch_frames
            emitted += batch_frames
            on_frames(audio, capture_start, capture_end)


class WavFileFrameSource:
    """Stream a WAV file at wall-clock speed into the realtime frame path."""

    is_microphone = False

    def __init__(
        self,
        path: Path | str,
        *,
        frame_sec: float = 0.05,
        real_time: bool = True,
        module_importer: Callable[[str], Any] | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.frame_sec = frame_sec
        self.real_time = real_time
        self._module_importer = module_importer or importlib.import_module

    def capture(
        self,
        *,
        on_frames: FrameCallback,
        duration_sec: float,
        sample_rate: int,
        stop_event: threading.Event,
    ) -> None:
        if not self.path.is_file():
            raise LiveMicRealtimeError(f"--input-wav does not exist: {self.path}")
        sf = self._import_soundfile()
        try:
            audio, source_sample_rate = sf.read(
                self.path,
                dtype="float32",
                always_2d=True,
            )
        except Exception as exc:
            raise LiveMicRealtimeError(f"Failed to read --input-wav {self.path}: {exc}") from exc

        if int(source_sample_rate) != int(sample_rate):
            audio = resample_audio(audio, int(source_sample_rate), int(sample_rate))
        mono = _mono_float32(audio)
        total_frames = min(int(mono.size), max(1, int(round(duration_sec * sample_rate))))
        frames_per_batch = max(1, int(round(self.frame_sec * sample_rate)))
        started_at = time.monotonic()
        emitted = 0
        while emitted < total_frames and not stop_event.is_set():
            batch_frames = min(frames_per_batch, total_frames - emitted)
            frame_start_sec = emitted / sample_rate
            frame_end_sec = (emitted + batch_frames) / sample_rate
            if self.real_time:
                delay = (started_at + frame_end_sec) - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            capture_start = started_at + frame_start_sec
            capture_end = max(time.monotonic(), started_at + frame_end_sec)
            on_frames(mono[emitted : emitted + batch_frames], capture_start, capture_end)
            emitted += batch_frames

    def _import_soundfile(self) -> Any:
        try:
            return self._module_importer("soundfile")
        except ModuleNotFoundError as exc:
            raise LiveMicRealtimeError(
                "Missing audio reader dependency 'soundfile'; cannot stream --input-wav."
            ) from exc


def run_live_mic_realtime(
    *,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    run_id: str | None = None,
    duration_sec: float = 10.0,
    window_sec: float = 3.0,
    hop_sec: float = 1.5,
    sample_rate: int = 16000,
    speaker_label: str | None = None,
    recording_id: str = "live_mic_realtime",
    device: str | int | None = None,
    input_wav: Path | str | None = None,
    output_dir: Path | str | None = None,
    keep_audio: bool = False,
    dry_run: bool = False,
    max_queue: int = 4,
    drop_policy: DropPolicy = "drop_oldest",
    frame_source: FrameSource | None = None,
    pipeline_runner: Any | None = None,
    report_dir: Path | str | None = None,
    write_report: bool = True,
    verbose: bool = False,
    stitch_transcript: bool = False,
    stability_delay_sec: float = 1.0,
    speaker_window_sec: float | None = None,
    speaker_hop_sec: float | None = None,
    speaker_confirmation_windows: int = 3,
    speaker_confirmation_threshold: int = 2,
    speaker_score_threshold: float = 0.5,
    speaker_correction_window_sec: float = 6.0,
    stdout: TextIO | None = None,
    command: Sequence[str] = (),
) -> LiveMicRealtimeResult:
    """Run continuous capture and background inference through PipelineRunner."""

    _validate_realtime_args(
        duration_sec=duration_sec,
        window_sec=window_sec,
        hop_sec=hop_sec,
        sample_rate=sample_rate,
        recording_id=recording_id,
        max_queue=max_queue,
        drop_policy=drop_policy,
        stitch_transcript=stitch_transcript,
        stability_delay_sec=stability_delay_sec,
        speaker_window_sec=speaker_window_sec,
        speaker_hop_sec=speaker_hop_sec,
        speaker_confirmation_windows=speaker_confirmation_windows,
        speaker_confirmation_threshold=speaker_confirmation_threshold,
        speaker_score_threshold=speaker_score_threshold,
        speaker_correction_window_sec=speaker_correction_window_sec,
    )
    output = stdout or sys.stdout
    resolved_config_path = live_mic_smoke.resolve_config_path(config_path)
    config = PipelineConfig.from_yaml_path(resolved_config_path)
    availability = live_mic_smoke.inspect_runtime_availability(
        config,
        config_path=resolved_config_path,
    )
    availability["mic_device"] = device
    availability["input_wav_path"] = str(Path(input_wav).expanduser()) if input_wav else None
    availability["realtime_capture"] = (
        "wav_file_realtime" if input_wav else "sounddevice.InputStream callback"
    )
    resolved_speaker_window_sec = (
        max(window_sec, 4.0) if stitch_transcript and speaker_window_sec is None else speaker_window_sec
    )
    resolved_speaker_hop_sec = (
        max(hop_sec, 1.0) if stitch_transcript and speaker_hop_sec is None else speaker_hop_sec
    )
    speaker_evidence_enabled = (
        stitch_transcript
        and resolved_speaker_window_sec is not None
        and resolved_speaker_hop_sec is not None
    )

    try:
        pipeline, asr_mode = live_mic_smoke._select_pipeline(
            config,
            availability,
            dry_run=dry_run,
            pipeline_runner=pipeline_runner,
        )
    except live_mic_smoke.LiveMicSmokeError as exc:
        raise LiveMicRealtimeError(str(exc)) from exc

    selected_run_id = live_mic_smoke._safe_run_id(run_id or _default_run_id())
    output_root = resolve_output_root(output_dir)
    run_dir = output_root / selected_run_id
    audio_dir = run_dir / "audio"
    predictions_dir = run_dir / "predictions"
    predictions_path = predictions_dir / "utterances.jsonl"
    diagnostics_path = predictions_dir / "diagnostics.jsonl"
    summary_path = run_dir / "summary.json"

    predictions_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    predictions_path.write_text("", encoding="utf-8")
    diagnostics_path.write_text("", encoding="utf-8")

    run_config = _run_config(
        config=config,
        config_path=resolved_config_path,
        run_id=selected_run_id,
        run_dir=run_dir,
        duration_sec=duration_sec,
        window_sec=window_sec,
        hop_sec=hop_sec,
        sample_rate=sample_rate,
        speaker_label=speaker_label,
        recording_id=recording_id,
        device=device,
        input_wav=input_wav,
        dry_run=dry_run,
        max_queue=max_queue,
        drop_policy=drop_policy,
        command=command,
        availability=availability,
        stitch_transcript=stitch_transcript,
        stability_delay_sec=stability_delay_sec,
        speaker_window_sec=resolved_speaker_window_sec,
        speaker_hop_sec=resolved_speaker_hop_sec,
        speaker_confirmation_windows=speaker_confirmation_windows,
        speaker_confirmation_threshold=speaker_confirmation_threshold,
        speaker_score_threshold=speaker_score_threshold,
        speaker_correction_window_sec=speaker_correction_window_sec,
    )

    selected_frame_source = frame_source
    if selected_frame_source is None:
        if input_wav is not None:
            selected_frame_source = WavFileFrameSource(input_wav)
        elif dry_run:
            selected_frame_source = DryRunFrameSource()
        else:
            selected_frame_source = SoundDeviceFrameSource(device=device)
    microphone_capture_tested = bool(getattr(selected_frame_source, "is_microphone", False)) and not dry_run

    state = _RunState()
    stop_event = threading.Event()
    frame_queue: queue.Queue[FrameBatch | None] = queue.Queue()
    work_queue = WindowWorkQueue(max_queue)
    writer_lock = threading.Lock()
    stitcher = (
        RealtimeTranscriptStitcher(stability_delay_sec=stability_delay_sec)
        if stitch_transcript
        else None
    )
    speaker_state = (
        SpeakerEvidenceAccumulator(
            confirmation_windows=speaker_confirmation_windows,
            confirmation_threshold=speaker_confirmation_threshold,
            score_threshold=speaker_score_threshold,
        )
        if stitch_transcript
        else None
    )

    producer_thread = threading.Thread(
        target=_window_producer_loop,
        name="live-mic-realtime-window-producer",
        kwargs={
            "frame_queue": frame_queue,
            "work_queue": work_queue,
            "audio_dir": audio_dir,
            "sample_rate": sample_rate,
            "window_sec": window_sec,
            "hop_sec": hop_sec,
            "speaker_window_sec": resolved_speaker_window_sec,
            "speaker_hop_sec": resolved_speaker_hop_sec,
            "speaker_evidence_enabled": speaker_evidence_enabled,
            "drop_policy": drop_policy,
            "dry_run": dry_run,
            "diagnostics_path": diagnostics_path,
            "writer_lock": writer_lock,
            "state": state,
            "stop_event": stop_event,
        },
        daemon=True,
    )
    worker_thread = threading.Thread(
        target=_inference_worker_loop,
        name="live-mic-realtime-inference-worker",
        kwargs={
            "work_queue": work_queue,
            "pipeline": pipeline,
            "run_config": run_config,
            "predictions_path": predictions_path,
            "diagnostics_path": diagnostics_path,
            "writer_lock": writer_lock,
            "state": state,
            "stop_event": stop_event,
            "speaker_label": speaker_label,
            "recording_id": recording_id,
            "hop_sec": hop_sec,
            "dry_run": dry_run,
            "drop_policy": drop_policy,
            "stdout": output,
            "run_id": selected_run_id,
            "verbose": verbose,
            "stitcher": stitcher,
            "speaker_state": speaker_state,
            "stitch_transcript": stitch_transcript,
            "speaker_evidence_enabled": speaker_evidence_enabled,
            "speaker_correction_window_sec": speaker_correction_window_sec,
        },
        daemon=True,
    )

    producer_thread.start()
    worker_thread.start()

    def on_frames(frames: np.ndarray, capture_start: float, capture_end: float) -> None:
        frame_queue.put(
            FrameBatch(
                audio=np.array(frames, dtype=np.float32, copy=True),
                capture_start_monotonic=capture_start,
                capture_end_monotonic=capture_end,
            )
        )

    source_error: LiveMicRealtimeError | None = None
    try:
        selected_frame_source.capture(
            on_frames=on_frames,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            stop_event=stop_event,
        )
    except LiveMicRealtimeError as exc:
        source_error = exc
        stop_event.set()
    except Exception as exc:  # pragma: no cover - defensive boundary
        source_error = LiveMicRealtimeError(f"Realtime capture failed: {exc}")
        stop_event.set()
    finally:
        frame_queue.put(None)

    producer_thread.join()
    work_queue.close()
    worker_thread.join()

    if not keep_audio:
        with state.lock:
            audio_paths = list(state.audio_paths)
        live_mic_smoke._remove_audio_files(audio_paths, audio_dir)

    with state.lock:
        prediction_rows = list(state.prediction_rows)
        diagnostics_rows = list(state.diagnostics_rows)
        worker_errors = list(state.worker_errors)
        window_count = state.windows_completed
        dropped_count = state.windows_dropped

    component_report_path = (
        resolve_report_dir(report_dir) / f"live_mic_realtime_{selected_run_id}.md"
        if write_report
        else None
    )
    result = LiveMicRealtimeResult(
        run_id=selected_run_id,
        run_dir=run_dir,
        predictions_path=predictions_path,
        diagnostics_path=diagnostics_path,
        summary_path=summary_path,
        component_report_path=component_report_path,
        dry_run=dry_run,
        asr_mode=asr_mode,
        microphone_capture_tested=microphone_capture_tested,
        audio_retained=keep_audio,
        window_count=window_count,
        prediction_count=len(prediction_rows),
        dropped_window_count=dropped_count,
        max_queue_depth=work_queue.max_depth,
        config_path=resolved_config_path,
        availability=availability,
    )
    summary = _summary_json(
        result=result,
        recording_id=recording_id,
        speaker_label=speaker_label,
        duration_sec=duration_sec,
        window_sec=window_sec,
        hop_sec=hop_sec,
        sample_rate=sample_rate,
        device=device,
        input_wav=input_wav,
        max_queue=max_queue,
        drop_policy=drop_policy,
        prediction_rows=prediction_rows,
        diagnostics_rows=diagnostics_rows,
        worker_errors=worker_errors,
        stitch_transcript=stitch_transcript,
        stability_delay_sec=stability_delay_sec,
        speaker_window_sec=resolved_speaker_window_sec,
        speaker_hop_sec=resolved_speaker_hop_sec,
        speaker_confirmation_windows=speaker_confirmation_windows,
        speaker_confirmation_threshold=speaker_confirmation_threshold,
        speaker_score_threshold=speaker_score_threshold,
        speaker_correction_window_sec=speaker_correction_window_sec,
    )
    write_json(summary_path, summary)
    if component_report_path is not None:
        write_component_report(
            result,
            summary=summary,
            speaker_label=speaker_label,
            command=command,
        )

    if source_error is not None:
        raise source_error
    if worker_errors:
        raise LiveMicRealtimeError(worker_errors[0])
    return result


def build_realtime_record(
    *,
    recording_id: str,
    window: InferenceWindow,
    speaker_label: str | None,
    hop_sec: float,
    dry_run: bool,
) -> dict[str, object]:
    """Create one Evaluation Tool record for a realtime inference-window WAV."""

    duration_sec = _round_seconds(window.duration_sec)
    return {
        "recording_id": recording_id,
        "utt_id": f"{recording_id}_window_{window.window_index:04d}",
        "inference_audio_path": str(window.audio_path),
        "audio_path_resolved": str(window.audio_path),
        "start_sec": 0.0,
        "end_sec": duration_sec,
        "duration_sec": duration_sec,
        "sample_rate_hz": window.sample_rate,
        "channel_count": 1,
        "speaker_label": speaker_label,
        "source_recording_id": recording_id,
        "window_index": window.window_index,
        "window_purpose": window.purpose,
        "window_start_sec": _round_seconds(window.window_start_sec),
        "window_end_sec": _round_seconds(window.window_end_sec),
        "window_duration_sec": duration_sec,
        "window_hop_sec": _round_seconds(hop_sec),
        "capture_source": (
            "synthetic_realtime_dry_run" if dry_run else "live_microphone_realtime"
        ),
    }


def write_pcm16_wav(path: Path, audio: np.ndarray, *, sample_rate: int) -> Path:
    """Write mono float audio as PCM16 WAV."""

    mono = np.clip(_mono_float32(audio), -1.0, 1.0)
    pcm = (mono * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return path


def write_component_report(
    result: LiveMicRealtimeResult,
    *,
    summary: Mapping[str, object],
    speaker_label: str | None,
    command: Sequence[str],
) -> Path:
    """Write the per-run realtime live microphone component report."""

    if result.component_report_path is None:
        raise ValueError("component_report_path is required")
    result.component_report_path.parent.mkdir(parents=True, exist_ok=True)
    command_text = " ".join(command) if command else "not captured"
    availability = result.availability
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), Mapping) else {}
    latency = metrics.get("latency_sec") if isinstance(metrics, Mapping) else {}
    asr_rtf = metrics.get("asr_realtime_factor") if isinstance(metrics, Mapping) else {}
    queue_metrics = metrics.get("queue") if isinstance(metrics, Mapping) else {}
    stitching_enabled = bool(summary.get("stitch_transcript"))
    stitching_summary = (
        "- Transcript stitching: enabled.\n"
        f"- Stability delay seconds: `{summary.get('stability_delay_sec')}`.\n"
        f"- Speaker evidence window/hop seconds: "
        f"`{summary.get('speaker_window_sec')}` / `{summary.get('speaker_hop_sec')}`.\n"
        f"- Speaker confirmation: `{summary.get('speaker_confirmation_threshold')}` of "
        f"`{summary.get('speaker_confirmation_windows')}` windows above score "
        f"`{summary.get('speaker_score_threshold')}`."
        if stitching_enabled
        else "- Transcript stitching: disabled; one prediction row is emitted per ASR window."
    )
    microphone_status = (
        "actual microphone capture was attempted with sounddevice.InputStream"
        if result.microphone_capture_tested
        else "not tested; dry-run or injected frames were used"
    )
    asr_status = (
        "dry-run no-op ASR; transcripts are contract placeholders, not real ASR"
        if result.dry_run
        else f"configured ASR mode: {result.asr_mode}"
    )
    remaining = (
        "- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, "
        "Whisper package, and local model assets are available."
        if result.dry_run or not result.microphone_capture_tested
        else "- No incomplete work was identified by this realtime run."
    )
    text = f"""# Realtime Live Microphone Report

## Report Metadata
- Run id: `{result.run_id}`
- Date: `{datetime.now(timezone.utc).isoformat()}`
- Config path: `{result.config_path}`
- Run directory: `{result.run_dir}`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.
- Added opt-in overlap-aware ASR stitching and delayed speaker-state handling for realtime validation runs.

## Difference From M17_VAL
- M17_VAL recorded one full chunk, paused capture while ASR ran, then recorded the next chunk.
- This prototype keeps capture and window assembly running while previous windows are processed by the worker, and records latency, backlog, and dropped-window diagnostics.

## How To Run
```bash
python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id {result.run_id} --duration-sec {summary.get("duration_sec")} --window-sec {summary.get("window_sec")} --hop-sec {summary.get("hop_sec")} --speaker-label {speaker_label or "Unknown"} --keep-audio
```

## Execution Mode
- Microphone capture: {microphone_status}.
- ASR mode: {asr_status}.
- Dry-run: `{result.dry_run}`.
- Whisper package available: `{availability.get("whisper_package_available")}`.
- Whisper model asset: `{availability.get("whisper_model_asset_path")}`.
- Model downloads allowed: `{availability.get("allow_model_downloads")}`.
- Config/runtime blocker: `{availability.get("blocker") or "none for completed run"}`.

## Realtime Stitching And Speaker Evidence
{stitching_summary}
- Duplicate removal uses suffix/prefix token matching over normalized ASR tokens, with word timestamps converted from window-relative to stream-absolute time when ASR provides them.
- Provisional text remains mutable until the stability delay elapses; finalized text is committed without re-adding overlap tokens from later windows.
- Speaker evidence is accumulated over recent longer windows, with labels reported as `unknown`, `tentative`, or `confirmed`; recent transcript spans can be corrected when stronger evidence arrives.

## Latency And Backlog
- Windows completed: `{result.window_count}`.
- Predictions written: `{result.prediction_count}`.
- Dropped windows: `{result.dropped_window_count}`.
- Latency seconds: `{latency}`.
- ASR realtime factor: `{asr_rtf}`.
- Queue metrics: `{queue_metrics}`.

## Commands Run
- `{command_text}`

## Output Artifacts
- Predictions: `{result.predictions_path}`
- Diagnostics: `{result.diagnostics_path}`
- Summary: `{result.summary_path}`
- Audio retained: `{result.audio_retained}`

## Remaining Incomplete Work
{remaining}
"""
    result.component_report_path.write_text(text, encoding="utf-8")
    return result.component_report_path


def resolve_output_root(path: Path | str | None) -> Path:
    if path is None:
        return DEFAULT_OUTPUT_ROOT
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return TOOL_ROOT / candidate


def resolve_report_dir(path: Path | str | None) -> Path:
    if path is None:
        return DEFAULT_REPORT_DIR
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return TOOL_ROOT / candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Continuously capture microphone frames and run completed windows through "
            "Evaluation Tool inference in a background worker."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/inference/live_mic_realtime_whisper_tiny.yaml"),
        help="Inference config path, absolute or Evaluation Tool relative.",
    )
    parser.add_argument("--run-id", default=None, help="Run id. Defaults to a UTC timestamp.")
    parser.add_argument("--duration-sec", type=float, default=10.0, help="Total capture seconds.")
    parser.add_argument("--window-sec", type=float, default=3.0, help="Seconds sent to inference.")
    parser.add_argument("--hop-sec", type=float, default=1.5, help="Seconds between windows.")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Microphone sample rate.")
    parser.add_argument(
        "--speaker-label",
        default="Unknown",
        help="Speaker label placed in each synthetic Evaluation Tool record.",
    )
    parser.add_argument(
        "--recording-id",
        default="live_mic_realtime",
        help="Recording id placed in each synthetic Evaluation Tool record.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Optional sounddevice input device id/name for real microphone capture.",
    )
    parser.add_argument(
        "--input-wav",
        type=Path,
        default=None,
        help=(
            "Stream this WAV file at wall-clock speed instead of using a microphone. "
            "This tests realtime queue/worker behavior without OS microphone input."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/live_mic_realtime"),
        help="Root directory that will contain the run-id folder.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/component_reports/live_mic_realtime"),
        help="Directory for the realtime live mic component report.",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Retain processed window WAV files under the run directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate synthetic frames and use no-op ASR; no microphone or Whisper required.",
    )
    parser.add_argument(
        "--max-queue",
        type=int,
        default=4,
        help="Maximum completed windows waiting for inference.",
    )
    parser.add_argument(
        "--drop-policy",
        choices=DROP_POLICIES,
        default="drop_oldest",
        help="Policy when ASR is slower than capture and the inference queue is full.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed realtime diagnostics and output artifact paths.",
    )
    parser.add_argument(
        "--stitch-transcript",
        action="store_true",
        help="Merge overlapping ASR windows and emit provisional/final transcript updates.",
    )
    parser.add_argument(
        "--stability-delay-sec",
        type=float,
        default=1.0,
        help="Seconds to keep recent stitched words provisional before finalizing.",
    )
    parser.add_argument(
        "--speaker-window-sec",
        type=float,
        default=None,
        help="Longer speaker-evidence window seconds. Defaults to max(window-sec, 4.0) when stitching.",
    )
    parser.add_argument(
        "--speaker-hop-sec",
        type=float,
        default=None,
        help="Seconds between speaker-evidence windows. Defaults to max(hop-sec, 1.0) when stitching.",
    )
    parser.add_argument(
        "--speaker-confirmation-windows",
        type=int,
        default=3,
        help="Recent speaker-evidence windows used for label confirmation.",
    )
    parser.add_argument(
        "--speaker-confirmation-threshold",
        type=int,
        default=2,
        help="Matching recent speaker windows required before a label is confirmed.",
    )
    parser.add_argument(
        "--speaker-score-threshold",
        type=float,
        default=0.5,
        help="Minimum per-window speaker score used as evidence.",
    )
    parser.add_argument(
        "--speaker-correction-window-sec",
        type=float,
        default=6.0,
        help="Recent transcript seconds eligible for delayed speaker-label correction.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = (
        "python",
        "scripts/live_mic_realtime.py",
        *(argv if argv is not None else sys.argv[1:]),
    )
    try:
        result = run_live_mic_realtime(
            config_path=args.config,
            run_id=args.run_id,
            duration_sec=args.duration_sec,
            window_sec=args.window_sec,
            hop_sec=args.hop_sec,
            sample_rate=args.sample_rate,
            speaker_label=args.speaker_label,
            recording_id=args.recording_id,
            device=args.device,
            input_wav=args.input_wav,
            output_dir=args.output_dir,
            keep_audio=args.keep_audio,
            dry_run=args.dry_run,
            max_queue=args.max_queue,
            drop_policy=args.drop_policy,
            report_dir=args.report_dir,
            verbose=args.verbose,
            stitch_transcript=args.stitch_transcript,
            stability_delay_sec=args.stability_delay_sec,
            speaker_window_sec=args.speaker_window_sec,
            speaker_hop_sec=args.speaker_hop_sec,
            speaker_confirmation_windows=args.speaker_confirmation_windows,
            speaker_confirmation_threshold=args.speaker_confirmation_threshold,
            speaker_score_threshold=args.speaker_score_threshold,
            speaker_correction_window_sec=args.speaker_correction_window_sec,
            command=command,
        )
    except LiveMicRealtimeError as exc:
        print(f"live mic realtime blocked: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("live mic realtime interrupted", file=sys.stderr)
        return 130

    if args.verbose:
        print(f"Run directory: {result.run_dir}")
        print(f"Predictions: {result.predictions_path}")
        print(f"Diagnostics: {result.diagnostics_path}")
        print(f"Summary: {result.summary_path}")
        if result.component_report_path is not None:
            print(f"Component report: {result.component_report_path}")
    return 0


def _window_producer_loop(
    *,
    frame_queue: queue.Queue[FrameBatch | None],
    work_queue: WindowWorkQueue,
    audio_dir: Path,
    sample_rate: int,
    window_sec: float,
    hop_sec: float,
    speaker_window_sec: float | None,
    speaker_hop_sec: float | None,
    speaker_evidence_enabled: bool,
    drop_policy: DropPolicy,
    dry_run: bool,
    diagnostics_path: Path,
    writer_lock: threading.Lock,
    state: _RunState,
    stop_event: threading.Event,
) -> None:
    assembler = WindowAssembler(sample_rate=sample_rate, window_sec=window_sec, hop_sec=hop_sec)
    speaker_assembler = (
        WindowAssembler(
            sample_rate=sample_rate,
            window_sec=float(speaker_window_sec),
            hop_sec=float(speaker_hop_sec),
        )
        if speaker_evidence_enabled and speaker_window_sec is not None and speaker_hop_sec is not None
        else None
    )
    while not stop_event.is_set():
        batch = frame_queue.get()
        if batch is None:
            break
        asr_windows = assembler.add_frames(
            batch.audio,
            capture_start_monotonic=batch.capture_start_monotonic,
            capture_end_monotonic=batch.capture_end_monotonic,
        )
        speaker_windows = (
            speaker_assembler.add_frames(
                batch.audio,
                capture_start_monotonic=batch.capture_start_monotonic,
                capture_end_monotonic=batch.capture_end_monotonic,
            )
            if speaker_assembler is not None
            else []
        )
        pending_windows = [
            *_pending_windows(
                asr_windows,
                audio_dir=audio_dir,
                sample_rate=sample_rate,
                purpose="asr",
            ),
            *_pending_windows(
                speaker_windows,
                audio_dir=audio_dir,
                sample_rate=sample_rate,
                purpose="speaker",
            ),
        ]
        pending_windows.sort(key=lambda item: (item.window_end_sec, item.purpose))
        for window in pending_windows:
            if stop_event.is_set():
                break
            state.increment("windows_completed")
            outcome = work_queue.enqueue(window, drop_policy=drop_policy)
            if outcome.enqueued is not None:
                state.increment("windows_enqueued")
            if outcome.dropped is not None:
                state.increment("windows_dropped")
                row = _dropped_diagnostics_row(
                    window=outcome.dropped,
                    dry_run=dry_run,
                    drop_policy=drop_policy,
                    drop_reason=outcome.drop_reason or drop_policy,
                    queue_depth_at_enqueue=outcome.queue_depth_at_enqueue,
                    dropped_window_count=outcome.dropped_window_count,
                )
                _append_diagnostics_row(
                    row,
                    diagnostics_path=diagnostics_path,
                    writer_lock=writer_lock,
                    state=state,
                )


def _inference_worker_loop(
    *,
    work_queue: WindowWorkQueue,
    pipeline: Any,
    run_config: Mapping[str, object],
    predictions_path: Path,
    diagnostics_path: Path,
    writer_lock: threading.Lock,
    state: _RunState,
    stop_event: threading.Event,
    speaker_label: str | None,
    recording_id: str,
    hop_sec: float,
    dry_run: bool,
    drop_policy: DropPolicy,
    stdout: TextIO,
    run_id: str,
    verbose: bool,
    stitcher: RealtimeTranscriptStitcher | None,
    speaker_state: SpeakerEvidenceAccumulator | None,
    stitch_transcript: bool,
    speaker_evidence_enabled: bool,
    speaker_correction_window_sec: float,
) -> None:
    while not stop_event.is_set():
        get_result = work_queue.get()
        if get_result is None:
            return
        queued = get_result.queued_window
        window = queued.window
        inference_start = time.monotonic()
        record = build_realtime_record(
            recording_id=recording_id,
            window=window,
            speaker_label=speaker_label,
            hop_sec=hop_sec,
            dry_run=dry_run,
        )
        try:
            write_pcm16_wav(window.audio_path, window.audio, sample_rate=window.sample_rate)
            state.add_audio_path(window.audio_path)
            pipeline_output = pipeline.predict(record, run_config)
        except Exception as exc:
            inference_end = time.monotonic()
            row = _failed_diagnostics_row(
                record,
                window=window,
                queued=queued,
                get_result=get_result,
                inference_start_monotonic=inference_start,
                inference_end_monotonic=inference_end,
                dry_run=dry_run,
                drop_policy=drop_policy,
                dropped_window_count=work_queue.dropped_count,
                error=exc,
            )
            _append_diagnostics_row(
                row,
                diagnostics_path=diagnostics_path,
                writer_lock=writer_lock,
                state=state,
            )
            message = f"Pipeline prediction failed for window {window.window_index:04d}: {exc}"
            state.add_worker_error(message)
            stop_event.set()
            work_queue.close()
            return

        inference_end = time.monotonic()
        if window.purpose == "speaker":
            speaker_update = (
                speaker_state.add_evidence(_speaker_scores_from_output(pipeline_output))
                if speaker_state is not None
                else None
            )
            corrected = False
            if stitcher is not None and speaker_update is not None:
                corrected = stitcher.apply_speaker_state(
                    speaker_label=speaker_update.speaker_label,
                    speaker_label_status=speaker_update.status,
                    stream_time_sec=window.window_end_sec,
                    correction_window_sec=speaker_correction_window_sec,
                )
            diagnostics_row = _speaker_evidence_diagnostics_row(
                pipeline_output,
                pipeline,
                record,
                window=window,
                queued=queued,
                get_result=get_result,
                inference_start_monotonic=inference_start,
                inference_end_monotonic=inference_end,
                dry_run=dry_run,
                drop_policy=drop_policy,
                dropped_window_count=work_queue.dropped_count,
                speaker_update=speaker_update,
                corrected_prior_span=corrected,
            )
            _append_diagnostics_row(
                diagnostics_row,
                diagnostics_path=diagnostics_path,
                writer_lock=writer_lock,
                state=state,
            )
            if verbose:
                _print_speaker_evidence_line(
                    stdout,
                    run_id=run_id,
                    window_index=window.window_index,
                    diagnostics_row=diagnostics_row,
                    dry_run=dry_run,
                )
            continue

        prediction_row = live_mic_smoke._prediction_row(pipeline_output, record=record)
        speaker_update = None
        corrected_prior_span = False
        if stitch_transcript and speaker_state is not None and not speaker_evidence_enabled:
            speaker_update = speaker_state.add_evidence(_speaker_scores_from_output(pipeline_output))
            if stitcher is not None and speaker_update.corrected_prior_span:
                corrected_prior_span = stitcher.apply_speaker_state(
                    speaker_label=speaker_update.speaker_label,
                    speaker_label_status=speaker_update.status,
                    stream_time_sec=window.window_end_sec,
                    correction_window_sec=speaker_correction_window_sec,
                )
        stitch_update = None
        if stitch_transcript and stitcher is not None:
            speaker_label_for_text = (
                speaker_state.current_label
                if speaker_state is not None
                else str(prediction_row.get("speaker_label") or "Unknown")
            )
            speaker_status_for_text = (
                speaker_state.current_status if speaker_state is not None else SPEAKER_STATUS_CONFIRMED
            )
            stitch_update = stitcher.update(
                raw_text=str(prediction_row.get("text") or ""),
                window_start_sec=window.window_start_sec,
                window_end_sec=window.window_end_sec,
                window_index=window.window_index,
                words=_word_timings_from_output(pipeline_output),
                speaker_label=speaker_label_for_text,
                speaker_label_status=speaker_status_for_text,
            )
            prediction_row = _stitched_prediction_row(
                prediction_row,
                stitch_update=stitch_update,
                speaker_state=speaker_state,
            )
        diagnostics_row = _prediction_diagnostics_row(
            pipeline_output,
            pipeline,
            record,
            window=window,
            queued=queued,
            get_result=get_result,
            inference_start_monotonic=inference_start,
            inference_end_monotonic=inference_end,
            dry_run=dry_run,
            drop_policy=drop_policy,
            dropped_window_count=work_queue.dropped_count,
            stitch_update=stitch_update,
            speaker_state=speaker_state,
            corrected_prior_span=corrected_prior_span,
        )
        _append_prediction_and_diagnostics(
            prediction_row,
            diagnostics_row,
            predictions_path=predictions_path,
            diagnostics_path=diagnostics_path,
            writer_lock=writer_lock,
            state=state,
        )
        _print_transcript_line(
            stdout,
            run_id=run_id,
            window_index=window.window_index,
            prediction_row=prediction_row,
            diagnostics_row=diagnostics_row,
            dry_run=dry_run,
            verbose=verbose,
        )


def _pending_windows(
    windows: Sequence[WindowAudio],
    *,
    audio_dir: Path,
    sample_rate: int,
    purpose: Literal["asr", "speaker"],
) -> list[InferenceWindow]:
    prefix = "speaker_window" if purpose == "speaker" else "window"
    return [
        InferenceWindow(
            window_index=window_audio.window_index,
            audio=window_audio.audio,
            audio_path=audio_dir / f"{prefix}_{window_audio.window_index:04d}.wav",
            sample_rate=sample_rate,
            window_start_sec=window_audio.window_start_sec,
            window_end_sec=window_audio.window_end_sec,
            capture_start_monotonic=window_audio.capture_start_monotonic,
            capture_end_monotonic=window_audio.capture_end_monotonic,
            purpose=purpose,
        )
        for window_audio in windows
    ]


def _stitched_prediction_row(
    prediction_row: Mapping[str, object],
    *,
    stitch_update: Any,
    speaker_state: SpeakerEvidenceAccumulator | None,
) -> dict[str, object]:
    row = dict(prediction_row)
    row["text"] = stitch_update.emitted_prediction_text
    if speaker_state is not None:
        row["speaker_label"] = (
            speaker_state.current_label
            if speaker_state.current_status != "unknown"
            else "Unknown"
        )
    return row


def _word_timings_from_output(output: Any) -> tuple[object, ...]:
    transcript = getattr(output, "transcript", None)
    transcript_words = tuple(getattr(transcript, "words", ()) or ())
    if transcript_words:
        return transcript_words
    words: list[object] = []
    for item in tuple(getattr(output, "transcript_items", ()) or ()):
        words.extend(tuple(getattr(item, "words", ()) or ()))
    if words:
        return tuple(words)
    diagnostics = getattr(output, "diagnostics", None)
    if isinstance(diagnostics, Mapping):
        raw_words = diagnostics.get("words") or diagnostics.get("word_timestamps")
        if isinstance(raw_words, Sequence) and not isinstance(raw_words, str | bytes | bytearray):
            return tuple(raw_words)
    return ()


def _speaker_scores_from_output(output: Any) -> dict[str, float]:
    diagnostics = getattr(output, "diagnostics", None)
    if not isinstance(diagnostics, Mapping):
        diagnostics = {}
    direct_scores = _coerce_speaker_scores(diagnostics.get("speaker_scores"))
    if direct_scores:
        return direct_scores
    for key in ("speaker_state", "speaker_decision", "speaker_matching"):
        value = diagnostics.get(key)
        if isinstance(value, Mapping):
            scores = _coerce_speaker_scores(value.get("scores"))
            if scores:
                return scores
            fallback = _label_score_from_mapping(value)
            if fallback:
                return fallback
    decisions = diagnostics.get("speaker_decisions")
    if isinstance(decisions, Sequence) and not isinstance(decisions, str | bytes | bytearray):
        for decision in decisions:
            if not isinstance(decision, Mapping):
                continue
            scores = _coerce_speaker_scores(decision.get("scores"))
            if scores:
                return scores
            fallback = _label_score_from_mapping(decision)
            if fallback:
                return fallback
    label = str(getattr(output, "speaker_label", "") or "").strip()
    if label and label != "Unknown":
        return {label: 1.0}
    return {}


def _coerce_speaker_scores(value: object) -> dict[str, float]:
    if isinstance(value, Mapping):
        return _clean_score_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        scores: dict[str, float] = {}
        for item in value:
            if not isinstance(item, Mapping):
                continue
            label = item.get("speaker_label") or item.get("label") or item.get("best_label")
            score = item.get("score")
            if score is None:
                score = item.get("confidence")
            if label is None or score is None:
                continue
            try:
                scores[str(label)] = float(score)
            except (TypeError, ValueError):
                continue
        return _clean_score_mapping(scores)
    return {}


def _label_score_from_mapping(value: Mapping[str, object]) -> dict[str, float]:
    label = value.get("speaker_label") or value.get("best_label") or value.get("label")
    score = value.get("confidence")
    if score is None:
        score = value.get("score")
    if label is None or score is None:
        return {}
    return _clean_score_mapping({str(label): score})


def _clean_score_mapping(value: Mapping[str, object]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for label, score in value.items():
        text = str(label).strip()
        if not text or text == "Unknown":
            continue
        try:
            scores[text] = float(score)
        except (TypeError, ValueError):
            continue
    return scores


def _speaker_state_json(
    speaker_state: SpeakerEvidenceAccumulator | None,
) -> dict[str, object]:
    if speaker_state is None:
        return {
            "speaker_label": "Unknown",
            "status": SPEAKER_STATUS_CONFIRMED,
            "scores": {},
        }
    return {
        "speaker_label": speaker_state.current_label,
        "status": speaker_state.current_status,
        "scores": speaker_state.current_scores,
    }


def _raw_asr_text(output: Any) -> str:
    diagnostics = getattr(output, "diagnostics", None)
    if isinstance(diagnostics, Mapping):
        value = diagnostics.get("raw_asr_text")
        if value is not None:
            return _diagnostic_text(value)
    return str(getattr(output, "text", "") or "")


def _normalized_asr_text(output: Any, *, fallback: str) -> str:
    diagnostics = getattr(output, "diagnostics", None)
    if isinstance(diagnostics, Mapping):
        for key in ("normalized_asr_text", "normalized_text", "assembled_text"):
            value = diagnostics.get(key)
            if value is not None:
                return _diagnostic_text(value)
    return fallback


def _diagnostic_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return " ".join(str(item) for item in value if item is not None).strip()
    return str(value)


def _speaker_evidence_diagnostics_row(
    output: Any,
    pipeline: Any,
    record: Mapping[str, object],
    *,
    window: InferenceWindow,
    queued: QueuedWindow,
    get_result: QueueGetResult,
    inference_start_monotonic: float,
    inference_end_monotonic: float,
    dry_run: bool,
    drop_policy: DropPolicy,
    dropped_window_count: int,
    speaker_update: Any | None,
    corrected_prior_span: bool,
) -> dict[str, object]:
    pipeline_diagnostics = getattr(output, "diagnostics", None)
    if pipeline_diagnostics is None:
        pipeline_diagnostics = getattr(pipeline, "last_diagnostics", None)
    scores = speaker_update.scores if speaker_update is not None else {}
    status = speaker_update.status if speaker_update is not None else "unknown"
    label = speaker_update.speaker_label if speaker_update is not None else "Unknown"
    return {
        "status": "speaker_evidence",
        "window_index": window.window_index,
        "recording_id": getattr(output, "recording_id"),
        "utt_id": getattr(output, "utt_id"),
        "start_sec": getattr(output, "start_sec"),
        "end_sec": getattr(output, "end_sec"),
        "speaker_label": label,
        "window_start_sec": window.window_start_sec,
        "window_end_sec": window.window_end_sec,
        "window_duration_sec": window.duration_sec,
        "capture_start_monotonic": window.capture_start_monotonic,
        "capture_end_monotonic": window.capture_end_monotonic,
        "enqueue_monotonic": queued.enqueue_monotonic,
        "dequeue_monotonic": get_result.dequeue_monotonic,
        "inference_start_monotonic": inference_start_monotonic,
        "inference_end_monotonic": inference_end_monotonic,
        "capture_to_prediction_latency_sec": _round_seconds(
            inference_end_monotonic - window.capture_end_monotonic
        ),
        "inference_runtime_sec": _round_seconds(inference_end_monotonic - inference_start_monotonic),
        "asr_realtime_factor": _asr_realtime_factor(
            pipeline=pipeline,
            output=output,
            audio_duration_sec=window.duration_sec,
        ),
        "queue_depth_at_enqueue": queued.queue_depth_at_enqueue,
        "queue_depth_at_dequeue": get_result.queue_depth_at_dequeue,
        "queue_depth_after_dequeue": get_result.queue_depth_after_dequeue,
        "enqueue_blocked_sec": _round_seconds(queued.enqueue_blocked_sec),
        "dropped_window_count": dropped_window_count,
        "drop_policy": drop_policy,
        "inference_audio_path": str(record["inference_audio_path"]),
        "dry_run": dry_run,
        "raw_asr_text": _raw_asr_text(output),
        "normalized_asr_text": _normalized_asr_text(output, fallback=_raw_asr_text(output)),
        "overlap_removed_tokens": 0,
        "committed_text": "",
        "provisional_text": "",
        "newly_committed_text": "",
        "provisional_delta_text": "",
        "speaker_state": speaker_update.to_jsonable() if speaker_update is not None else {},
        "speaker_scores": dict(scores),
        "speaker_label_status": status,
        "corrected_prior_span": corrected_prior_span,
        "stitching_enabled": True,
        "diagnostics": pipeline_diagnostics or {},
        "warnings": list(getattr(output, "warnings", ()) or ()),
        "errors": list(getattr(output, "errors", ()) or ()),
    }


def _run_config(
    *,
    config: PipelineConfig,
    config_path: Path,
    run_id: str,
    run_dir: Path,
    duration_sec: float,
    window_sec: float,
    hop_sec: float,
    sample_rate: int,
    speaker_label: str | None,
    recording_id: str,
    device: str | int | None,
    input_wav: Path | str | None,
    dry_run: bool,
    max_queue: int,
    drop_policy: DropPolicy,
    command: Sequence[str],
    availability: Mapping[str, object],
    stitch_transcript: bool,
    stability_delay_sec: float,
    speaker_window_sec: float | None,
    speaker_hop_sec: float | None,
    speaker_confirmation_windows: int,
    speaker_confirmation_threshold: int,
    speaker_score_threshold: float,
    speaker_correction_window_sec: float,
) -> dict[str, object]:
    return {
        "command": "live_mic_realtime",
        "command_argv": list(command),
        "project_root": str(PROJECT_ROOT),
        "run_dir": str(run_dir),
        "config_path": str(config_path),
        "runtime": config.runtime.to_jsonable(),
        "components": {
            slot: component.to_jsonable()
            for slot, component in config.components.items()
        },
        "live_mic_realtime": {
            "run_id": run_id,
            "recording_id": recording_id,
            "speaker_label": speaker_label,
            "duration_sec": duration_sec,
            "window_sec": window_sec,
            "hop_sec": hop_sec,
            "sample_rate": sample_rate,
            "device": device,
            "input_wav_path": str(Path(input_wav).expanduser()) if input_wav else None,
            "dry_run": dry_run,
            "max_queue": max_queue,
            "drop_policy": drop_policy,
            "stitch_transcript": stitch_transcript,
            "stability_delay_sec": stability_delay_sec,
            "speaker_window_sec": speaker_window_sec,
            "speaker_hop_sec": speaker_hop_sec,
            "speaker_confirmation_windows": speaker_confirmation_windows,
            "speaker_confirmation_threshold": speaker_confirmation_threshold,
            "speaker_score_threshold": speaker_score_threshold,
            "speaker_correction_window_sec": speaker_correction_window_sec,
            "pipeline_contract": {
                "input": "one selected metadata row per completed window",
                "audio_field": "inference_audio_path",
                "prediction_fields": list(REQUIRED_PREDICTION_FIELDS),
            },
        },
        "availability": dict(availability),
    }


def _prediction_diagnostics_row(
    output: Any,
    pipeline: Any,
    record: Mapping[str, object],
    *,
    window: InferenceWindow,
    queued: QueuedWindow,
    get_result: QueueGetResult,
    inference_start_monotonic: float,
    inference_end_monotonic: float,
    dry_run: bool,
    drop_policy: DropPolicy,
    dropped_window_count: int,
    stitch_update: Any | None = None,
    speaker_state: SpeakerEvidenceAccumulator | None = None,
    corrected_prior_span: bool = False,
) -> dict[str, object]:
    pipeline_diagnostics = getattr(output, "diagnostics", None)
    if pipeline_diagnostics is None:
        pipeline_diagnostics = getattr(pipeline, "last_diagnostics", None)
    asr_realtime_factor = _asr_realtime_factor(
        pipeline=pipeline,
        output=output,
        audio_duration_sec=window.duration_sec,
    )
    raw_asr_text = _raw_asr_text(output)
    normalized_asr_text = _normalized_asr_text(output, fallback=raw_asr_text)
    row = {
        "status": "predicted",
        "window_index": window.window_index,
        "recording_id": getattr(output, "recording_id"),
        "utt_id": getattr(output, "utt_id"),
        "start_sec": getattr(output, "start_sec"),
        "end_sec": getattr(output, "end_sec"),
        "speaker_label": getattr(output, "speaker_label") or record.get("speaker_label"),
        "window_start_sec": window.window_start_sec,
        "window_end_sec": window.window_end_sec,
        "window_duration_sec": window.duration_sec,
        "capture_start_monotonic": window.capture_start_monotonic,
        "capture_end_monotonic": window.capture_end_monotonic,
        "enqueue_monotonic": queued.enqueue_monotonic,
        "dequeue_monotonic": get_result.dequeue_monotonic,
        "inference_start_monotonic": inference_start_monotonic,
        "inference_end_monotonic": inference_end_monotonic,
        "capture_to_prediction_latency_sec": _round_seconds(
            inference_end_monotonic - window.capture_end_monotonic
        ),
        "inference_runtime_sec": _round_seconds(inference_end_monotonic - inference_start_monotonic),
        "asr_realtime_factor": asr_realtime_factor,
        "queue_depth_at_enqueue": queued.queue_depth_at_enqueue,
        "queue_depth_at_dequeue": get_result.queue_depth_at_dequeue,
        "queue_depth_after_dequeue": get_result.queue_depth_after_dequeue,
        "enqueue_blocked_sec": _round_seconds(queued.enqueue_blocked_sec),
        "dropped_window_count": dropped_window_count,
        "drop_policy": drop_policy,
        "inference_audio_path": str(record["inference_audio_path"]),
        "dry_run": dry_run,
        "raw_asr_text": raw_asr_text,
        "normalized_asr_text": normalized_asr_text,
        "overlap_removed_tokens": 0,
        "committed_text": "",
        "provisional_text": "",
        "newly_committed_text": "",
        "provisional_delta_text": "",
        "speaker_state": _speaker_state_json(speaker_state),
        "speaker_scores": speaker_state.current_scores if speaker_state is not None else {},
        "speaker_label_status": (
            speaker_state.current_status if speaker_state is not None else SPEAKER_STATUS_CONFIRMED
        ),
        "corrected_prior_span": corrected_prior_span,
        "stitching_enabled": stitch_update is not None,
        "diagnostics": pipeline_diagnostics or {},
        "warnings": list(getattr(output, "warnings", ()) or ()),
        "errors": list(getattr(output, "errors", ()) or ()),
    }
    if stitch_update is not None:
        row.update(
            {
                "raw_asr_text": stitch_update.raw_asr_text,
                "normalized_asr_text": stitch_update.normalized_asr_text,
                "overlap_removed_tokens": stitch_update.overlap_removed_tokens,
                "committed_text": stitch_update.committed_text,
                "provisional_text": stitch_update.provisional_text,
                "newly_committed_text": stitch_update.newly_committed_text,
                "provisional_delta_text": stitch_update.provisional_delta_text,
                "stitching": stitch_update.to_jsonable(),
            }
        )
    return row


def _dropped_diagnostics_row(
    *,
    window: InferenceWindow,
    dry_run: bool,
    drop_policy: DropPolicy,
    drop_reason: str,
    queue_depth_at_enqueue: int,
    dropped_window_count: int,
) -> dict[str, object]:
    now = time.monotonic()
    return {
        "status": "dropped",
        "window_index": window.window_index,
        "recording_id": None,
        "utt_id": None,
        "start_sec": 0.0,
        "end_sec": window.duration_sec,
        "speaker_label": None,
        "window_start_sec": window.window_start_sec,
        "window_end_sec": window.window_end_sec,
        "window_duration_sec": window.duration_sec,
        "capture_start_monotonic": window.capture_start_monotonic,
        "capture_end_monotonic": window.capture_end_monotonic,
        "enqueue_monotonic": None,
        "dequeue_monotonic": None,
        "inference_start_monotonic": None,
        "inference_end_monotonic": None,
        "capture_to_prediction_latency_sec": None,
        "inference_runtime_sec": None,
        "asr_realtime_factor": None,
        "queue_depth_at_enqueue": queue_depth_at_enqueue,
        "queue_depth_at_dequeue": None,
        "queue_depth_after_dequeue": None,
        "enqueue_blocked_sec": 0.0,
        "dropped_window_count": dropped_window_count,
        "drop_policy": drop_policy,
        "drop_reason": drop_reason,
        "drop_monotonic": now,
        "inference_audio_path": str(window.audio_path),
        "dry_run": dry_run,
        "diagnostics": {},
        "warnings": ["window dropped before inference because backlog exceeded --max-queue"],
        "errors": [],
    }


def _failed_diagnostics_row(
    record: Mapping[str, object],
    *,
    window: InferenceWindow,
    queued: QueuedWindow,
    get_result: QueueGetResult,
    inference_start_monotonic: float,
    inference_end_monotonic: float,
    dry_run: bool,
    drop_policy: DropPolicy,
    dropped_window_count: int,
    error: Exception,
) -> dict[str, object]:
    return {
        "status": "failed",
        "window_index": window.window_index,
        "recording_id": record.get("recording_id"),
        "utt_id": record.get("utt_id"),
        "start_sec": record.get("start_sec"),
        "end_sec": record.get("end_sec"),
        "speaker_label": record.get("speaker_label"),
        "window_start_sec": window.window_start_sec,
        "window_end_sec": window.window_end_sec,
        "window_duration_sec": window.duration_sec,
        "capture_start_monotonic": window.capture_start_monotonic,
        "capture_end_monotonic": window.capture_end_monotonic,
        "enqueue_monotonic": queued.enqueue_monotonic,
        "dequeue_monotonic": get_result.dequeue_monotonic,
        "inference_start_monotonic": inference_start_monotonic,
        "inference_end_monotonic": inference_end_monotonic,
        "capture_to_prediction_latency_sec": _round_seconds(
            inference_end_monotonic - window.capture_end_monotonic
        ),
        "inference_runtime_sec": _round_seconds(inference_end_monotonic - inference_start_monotonic),
        "asr_realtime_factor": None,
        "queue_depth_at_enqueue": queued.queue_depth_at_enqueue,
        "queue_depth_at_dequeue": get_result.queue_depth_at_dequeue,
        "queue_depth_after_dequeue": get_result.queue_depth_after_dequeue,
        "enqueue_blocked_sec": _round_seconds(queued.enqueue_blocked_sec),
        "dropped_window_count": dropped_window_count,
        "drop_policy": drop_policy,
        "inference_audio_path": str(record.get("inference_audio_path")),
        "dry_run": dry_run,
        "diagnostics": {},
        "warnings": [],
        "errors": [f"{type(error).__name__}: {error}"],
    }


def _append_prediction_and_diagnostics(
    prediction_row: Mapping[str, object],
    diagnostics_row: Mapping[str, object],
    *,
    predictions_path: Path,
    diagnostics_path: Path,
    writer_lock: threading.Lock,
    state: _RunState,
) -> None:
    with writer_lock:
        live_mic_smoke._append_jsonl(predictions_path, prediction_row)
        live_mic_smoke._append_jsonl(diagnostics_path, diagnostics_row)
        with state.lock:
            state.prediction_rows.append(dict(prediction_row))
            state.diagnostics_rows.append(dict(diagnostics_row))


def _append_diagnostics_row(
    row: Mapping[str, object],
    *,
    diagnostics_path: Path,
    writer_lock: threading.Lock,
    state: _RunState,
) -> None:
    with writer_lock:
        live_mic_smoke._append_jsonl(diagnostics_path, row)
        with state.lock:
            state.diagnostics_rows.append(dict(row))


def _print_transcript_line(
    output: TextIO,
    *,
    run_id: str,
    window_index: int,
    prediction_row: Mapping[str, object],
    diagnostics_row: Mapping[str, object],
    dry_run: bool,
    verbose: bool,
) -> None:
    mode = "DRY-RUN/NO-OP" if dry_run else "LIVE"
    speaker = prediction_row.get("speaker_label") or "Unknown"
    text = str(prediction_row.get("text") or "").strip() or "(empty transcript)"
    if diagnostics_row.get("stitching_enabled"):
        final_text = str(diagnostics_row.get("newly_committed_text") or "").strip()
        provisional_text = str(diagnostics_row.get("provisional_delta_text") or "").strip()
        status = str(diagnostics_row.get("speaker_label_status") or "unknown")
        if not verbose:
            if final_text:
                print(f"{_speaker_display(speaker, status, provisional=False)}: {final_text}", file=output)
            if provisional_text and provisional_text != final_text:
                print(
                    f"{_speaker_display(speaker, status, provisional=True)}: {provisional_text}",
                    file=output,
                )
            return
        overlap = diagnostics_row.get("overlap_removed_tokens")
        committed = diagnostics_row.get("committed_text")
        provisional = diagnostics_row.get("provisional_text")
        print(
            f"[{mode} {run_id}] window {window_index:04d} "
            f"overlap_removed={overlap} "
            f"speaker_status={status} "
            f"committed={committed!r} provisional={provisional!r}",
            file=output,
        )
        return
    if not verbose:
        print(f"{speaker}: {text}", file=output)
        return
    latency = diagnostics_row.get("capture_to_prediction_latency_sec")
    backlog = diagnostics_row.get("queue_depth_after_dequeue")
    dropped = diagnostics_row.get("dropped_window_count")
    print(
        f"[{mode} {run_id}] window {window_index:04d} "
        f"latency={latency}s backlog={backlog} dropped={dropped} {speaker}: {text}",
        file=output,
    )


def _print_speaker_evidence_line(
    output: TextIO,
    *,
    run_id: str,
    window_index: int,
    diagnostics_row: Mapping[str, object],
    dry_run: bool,
) -> None:
    mode = "DRY-RUN/NO-OP" if dry_run else "LIVE"
    speaker = diagnostics_row.get("speaker_label") or "Unknown"
    status = diagnostics_row.get("speaker_label_status")
    scores = diagnostics_row.get("speaker_scores")
    corrected = diagnostics_row.get("corrected_prior_span")
    print(
        f"[{mode} {run_id}] speaker-window {window_index:04d} "
        f"{speaker} status={status} corrected_prior_span={corrected} scores={scores}",
        file=output,
    )


def _speaker_display(speaker: object, status: str, *, provisional: bool) -> str:
    text = str(speaker or "Unknown").strip() or "Unknown"
    if text != "Unknown" and (provisional or status != SPEAKER_STATUS_CONFIRMED):
        return f"{text}?"
    return text


def _summary_json(
    *,
    result: LiveMicRealtimeResult,
    recording_id: str,
    speaker_label: str | None,
    duration_sec: float,
    window_sec: float,
    hop_sec: float,
    sample_rate: int,
    device: str | int | None,
    input_wav: Path | str | None,
    max_queue: int,
    drop_policy: DropPolicy,
    prediction_rows: Sequence[Mapping[str, object]],
    diagnostics_rows: Sequence[Mapping[str, object]],
    worker_errors: Sequence[str],
    stitch_transcript: bool,
    stability_delay_sec: float,
    speaker_window_sec: float | None,
    speaker_hop_sec: float | None,
    speaker_confirmation_windows: int,
    speaker_confirmation_threshold: int,
    speaker_score_threshold: float,
    speaker_correction_window_sec: float,
) -> dict[str, object]:
    predicted_rows = [row for row in diagnostics_rows if row.get("status") == "predicted"]
    dropped_rows = [row for row in diagnostics_rows if row.get("status") == "dropped"]
    latencies = [_optional_float(row.get("capture_to_prediction_latency_sec")) for row in predicted_rows]
    rtfs = [_optional_float(row.get("asr_realtime_factor")) for row in predicted_rows]
    queue_depths = [
        _optional_float(row.get("queue_depth_at_enqueue"))
        for row in diagnostics_rows
        if row.get("queue_depth_at_enqueue") is not None
    ]
    return {
        **result.to_jsonable(),
        "recording_id": recording_id,
        "speaker_label": speaker_label,
        "duration_sec": duration_sec,
        "window_sec": window_sec,
        "hop_sec": hop_sec,
        "sample_rate": sample_rate,
        "device": device,
        "input_wav_path": str(Path(input_wav).expanduser()) if input_wav else None,
        "max_queue": max_queue,
        "drop_policy": drop_policy,
        "stitch_transcript": stitch_transcript,
        "stability_delay_sec": stability_delay_sec,
        "speaker_window_sec": speaker_window_sec,
        "speaker_hop_sec": speaker_hop_sec,
        "speaker_confirmation_windows": speaker_confirmation_windows,
        "speaker_confirmation_threshold": speaker_confirmation_threshold,
        "speaker_score_threshold": speaker_score_threshold,
        "speaker_correction_window_sec": speaker_correction_window_sec,
        "real_asr_used": not result.dry_run and result.asr_mode not in {"dry_run_no_op_asr"},
        "prediction_required_fields": list(REQUIRED_PREDICTION_FIELDS),
        "metrics": {
            "latency_sec": _numeric_summary(latencies),
            "asr_realtime_factor": _numeric_summary(rtfs),
            "queue": {
                "max_depth_observed": result.max_queue_depth,
                "max_depth_recorded": max(queue_depths) if queue_depths else 0,
                "dropped_window_count": result.dropped_window_count,
                "dropped_window_indices": [row.get("window_index") for row in dropped_rows],
            },
        },
        "prediction_rows": [dict(row) for row in prediction_rows],
        "diagnostics_rows": [dict(row) for row in diagnostics_rows],
        "worker_errors": list(worker_errors),
    }


def _asr_realtime_factor(
    *,
    pipeline: Any,
    output: Any,
    audio_duration_sec: float,
) -> float | None:
    asr = getattr(pipeline, "asr", None)
    asr_stats = getattr(asr, "last_runtime_stats", None)
    value = getattr(asr_stats, "realtime_factor", None)
    if value is not None:
        return _round_seconds(float(value))
    runtime_stats = getattr(output, "runtime_stats", None)
    asr_sec = getattr(runtime_stats, "asr_sec", None)
    if asr_sec is not None and audio_duration_sec > 0:
        return _round_seconds(float(asr_sec) / audio_duration_sec)
    return None


def _numeric_summary(values: Sequence[float | None]) -> dict[str, float | int | None]:
    numeric = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not numeric:
        return {"count": 0, "min": None, "mean": None, "max": None}
    return {
        "count": len(numeric),
        "min": _round_seconds(min(numeric)),
        "mean": _round_seconds(sum(numeric) / len(numeric)),
        "max": _round_seconds(max(numeric)),
    }


def _validate_realtime_args(
    *,
    duration_sec: float,
    window_sec: float,
    hop_sec: float,
    sample_rate: int,
    recording_id: str,
    max_queue: int,
    drop_policy: str,
    stitch_transcript: bool,
    stability_delay_sec: float,
    speaker_window_sec: float | None,
    speaker_hop_sec: float | None,
    speaker_confirmation_windows: int,
    speaker_confirmation_threshold: int,
    speaker_score_threshold: float,
    speaker_correction_window_sec: float,
) -> None:
    if duration_sec <= 0:
        raise LiveMicRealtimeError("--duration-sec must be > 0")
    if window_sec <= 0:
        raise LiveMicRealtimeError("--window-sec must be > 0")
    if hop_sec <= 0:
        raise LiveMicRealtimeError("--hop-sec must be > 0")
    if sample_rate < 1:
        raise LiveMicRealtimeError("--sample-rate must be >= 1")
    if max_queue < 1:
        raise LiveMicRealtimeError("--max-queue must be >= 1")
    if drop_policy not in DROP_POLICIES:
        raise LiveMicRealtimeError(f"--drop-policy must be one of {DROP_POLICIES}")
    if not str(recording_id).strip():
        raise LiveMicRealtimeError("--recording-id must be non-empty")
    if stability_delay_sec < 0:
        raise LiveMicRealtimeError("--stability-delay-sec must be >= 0")
    if speaker_window_sec is not None and speaker_window_sec <= 0:
        raise LiveMicRealtimeError("--speaker-window-sec must be > 0")
    if speaker_hop_sec is not None and speaker_hop_sec <= 0:
        raise LiveMicRealtimeError("--speaker-hop-sec must be > 0")
    if speaker_confirmation_windows < 1:
        raise LiveMicRealtimeError("--speaker-confirmation-windows must be >= 1")
    if speaker_confirmation_threshold < 1:
        raise LiveMicRealtimeError("--speaker-confirmation-threshold must be >= 1")
    if speaker_confirmation_threshold > speaker_confirmation_windows:
        raise LiveMicRealtimeError(
            "--speaker-confirmation-threshold must be <= --speaker-confirmation-windows"
        )
    if speaker_correction_window_sec < 0:
        raise LiveMicRealtimeError("--speaker-correction-window-sec must be >= 0")
    if stitch_transcript and speaker_score_threshold < 0:
        raise LiveMicRealtimeError("--speaker-score-threshold must be >= 0")


def _mono_float32(frames: np.ndarray) -> np.ndarray:
    audio = np.asarray(frames, dtype=np.float32)
    if audio.ndim == 0:
        return audio.reshape(1)
    if audio.ndim == 1:
        return audio
    if audio.shape[1] == 1:
        return audio[:, 0]
    return np.mean(audio, axis=1, dtype=np.float32)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_seconds(value: float) -> float:
    return round(float(value), 6)


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_live_mic_realtime")


if __name__ == "__main__":
    raise SystemExit(main())
