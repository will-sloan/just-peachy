"""Local-only WAV or microphone enrollment with quality checks."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import re
import threading
import time
from typing import Sequence

import numpy as np
from scipy.signal import resample_poly

from .config import PipelineConfig
from .models import SpeakerModels


class EnrollmentRecorder:
    """Unlimited, disk-backed microphone recording with a fast callback."""

    def __init__(
        self,
        output_path: Path,
        *,
        device: int | None,
        preferred_rate: int = 16_000,
        block_ms: int = 20,
        reserve_sec: int = 120,
    ) -> None:
        self.output_path = Path(output_path).resolve()
        self.device = device
        self.preferred_rate = preferred_rate
        self.block_ms = block_ms
        self.reserve_sec = reserve_sec
        self.sample_rate = preferred_rate
        self.written_frames = 0
        self.started_monotonic = 0.0
        self.error: str | None = None
        self.input_overflow_events = 0
        self.reserve_failures = 0
        self._queue: queue.Queue[np.ndarray] | None = None
        self._stop_event = threading.Event()
        self._writer_thread: threading.Thread | None = None
        self._stream = None
        self._started = False

    def start(self) -> dict[str, object]:
        import sounddevice as sd

        if self._started:
            raise RuntimeError("enrollment recording is already active")
        info = sd.query_devices(self.device, "input")
        if int(info["max_input_channels"]) < 1:
            raise RuntimeError("selected device has no input channel")
        default_rate = int(round(float(info["default_samplerate"])))
        try:
            sd.check_input_settings(
                device=self.device,
                channels=1,
                dtype="float32",
                samplerate=self.preferred_rate,
            )
            self.sample_rate = self.preferred_rate
        except Exception:
            self.sample_rate = default_rate
        blocksize = max(1, round(self.sample_rate * self.block_ms / 1000))
        reserve_blocks = max(100, round(self.reserve_sec * 1000 / self.block_ms))
        self._queue = queue.Queue(maxsize=reserve_blocks)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()

        def callback(indata, _frames, _time_info, status) -> None:
            if status and "overflow" in str(status).lower():
                self.input_overflow_events += 1
                self.error = f"PORTAUDIO_INPUT_OVERFLOW: {status}"
                self._stop_event.set()
                raise sd.CallbackAbort
            try:
                assert self._queue is not None
                self._queue.put_nowait(
                    np.asarray(indata[:, 0], dtype=np.float32).copy()
                )
            except queue.Full:
                self.reserve_failures += 1
                self.error = "ENROLLMENT_CAPTURE_RESERVE_EXHAUSTED"
                self._stop_event.set()
                raise sd.CallbackAbort

        self._writer_thread = threading.Thread(
            target=self._write_loop,
            name="enrollment-wav-writer",
            daemon=True,
        )
        self._writer_thread.start()
        self._stream = sd.InputStream(
            device=self.device,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            callback=callback,
        )
        try:
            self._stream.start()
        except Exception:
            self._stop_event.set()
            if self._writer_thread is not None:
                self._writer_thread.join(timeout=3.0)
            raise
        self.started_monotonic = time.perf_counter()
        self._started = True
        return self.status()

    def _write_loop(self) -> None:
        import soundfile as sf

        assert self._queue is not None
        try:
            with sf.SoundFile(
                self.output_path,
                mode="w",
                samplerate=self.sample_rate,
                channels=1,
                subtype="PCM_16",
                format="WAV",
            ) as handle:
                while not self._stop_event.is_set() or not self._queue.empty():
                    try:
                        block = self._queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    handle.write(block)
                    self.written_frames += int(block.size)
        except Exception as exc:
            self.error = f"ENROLLMENT_WAV_WRITE_FAILED: {exc}"
            self._stop_event.set()

    def stop(self) -> Path:
        if not self._started:
            raise RuntimeError("enrollment recording has not started")
        self._stop_event.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        if self._writer_thread is not None:
            self._writer_thread.join(timeout=10.0)
            if self._writer_thread.is_alive():
                raise RuntimeError("enrollment WAV writer did not stop cleanly")
        self._started = False
        if self.error:
            raise RuntimeError(self.error)
        return self.output_path

    def cancel(self) -> None:
        try:
            self.stop()
        except Exception:
            pass

    def status(self) -> dict[str, object]:
        return {
            "active": self._started and not self._stop_event.is_set(),
            "duration_sec": self.written_frames / self.sample_rate,
            "wall_elapsed_sec": (
                time.perf_counter() - self.started_monotonic
                if self.started_monotonic
                else 0.0
            ),
            "sample_rate": self.sample_rate,
            "written_frames": self.written_frames,
            "output_path": str(self.output_path),
            "error": self.error,
            "input_overflow_events": self.input_overflow_events,
            "reserve_failures": self.reserve_failures,
        }


def enrollment_recording_path(profile_root: Path, display_name: str) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", display_name.strip()).strip("_")
    if not slug:
        slug = "speaker"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(profile_root) / "recordings" / f"{slug}_{stamp}.wav"


def _mono_16k(path: Path) -> np.ndarray:
    import soundfile as sf

    samples, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(samples, axis=1, dtype=np.float32)
    if int(rate) != 16_000:
        from math import gcd

        common = gcd(int(rate), 16_000)
        mono = resample_poly(mono, 16_000 // common, int(rate) // common).astype(np.float32)
    return mono


def enroll_wavs(
    display_name: str,
    wav_paths: Sequence[Path],
    *,
    models: SpeakerModels,
    config: PipelineConfig,
) -> dict[str, object]:
    name = display_name.strip()
    if not name:
        raise ValueError("display name is required")
    if not wav_paths:
        raise ValueError("at least one WAV is required")
    vectors = []
    quality_rows = []
    for path in wav_paths:
        waveform = _mono_16k(Path(path))
        duration = waveform.size / 16_000
        rms = float(np.sqrt(np.mean(np.square(waveform), dtype=np.float64))) if waveform.size else 0.0
        peak = float(np.max(np.abs(waveform))) if waveform.size else 0.0
        clipping = float(np.mean(np.abs(waveform) >= 0.999)) if waveform.size else 0.0
        if duration < 0.5:
            raise ValueError(f"enrollment audio is shorter than 0.5 seconds: {path}")
        if rms < config.minimum_rms:
            raise ValueError(f"enrollment audio level is too low: {path}")
        for left in range(0, max(1, waveform.size - 8_000 + 1), 16_000):
            window = waveform[left : left + 32_000]
            if window.size >= 8_000:
                vectors.append(models.embed(window))
        quality_rows.append({"path": str(Path(path).resolve()), "duration_sec": duration, "rms": rms, "peak": peak, "clipping_fraction": clipping})
    matrix = np.stack(vectors)
    centroid = np.mean(matrix, axis=0)
    centroid = (centroid / np.linalg.norm(centroid)).astype(np.float32)
    consistency = float(np.min(matrix @ centroid))
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "speaker"
    identity = hashlib.sha256((name + datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:12]
    profile_id = f"{slug}_{identity}"
    config.profile_root.mkdir(parents=True, exist_ok=True)
    vector_path = config.profile_root / f"{profile_id}.npy"
    metadata_path = config.profile_root / f"{profile_id}.json"
    np.save(vector_path, centroid, allow_pickle=False)
    metadata = {
        "schema_version": "edge-speaker-profile.v1",
        "profile_id": profile_id,
        "display_name": name,
        "backend_id": "redimnet2_b2_fp32",
        "backend_sha256": config.asset("redimnet2_b2_fp32").sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_files": quality_rows,
        "embedding_count": int(matrix.shape[0]),
        "within_enrollment_consistency": consistency,
        "quality_status": "PASS" if consistency >= 0.3 else "REVIEW_LOW_CONSISTENCY",
        "vector_path": str(vector_path),
        "local_only": True,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def record_microphone_wav(
    output_path: Path,
    *,
    device: int | None,
    duration_sec: float = 6.0,
) -> Path:
    import sounddevice as sd
    import soundfile as sf

    info = sd.query_devices(device, "input")
    rate = int(round(float(info["default_samplerate"])))
    recording = sd.rec(
        round(duration_sec * rate),
        samplerate=rate,
        channels=1,
        dtype="float32",
        device=device,
        blocking=True,
    )
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, recording[:, 0], rate, subtype="PCM_16")
    return output
