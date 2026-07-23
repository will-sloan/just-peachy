from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def _to_mono(samples: np.ndarray) -> np.ndarray:
    if samples.ndim == 1:
        return samples.astype(np.float32, copy=False)
    if samples.ndim != 2:
        raise ValueError(f"Expected 1D or 2D audio array, got shape={samples.shape}")
    return samples.mean(axis=1, dtype=np.float32)


def _crop(samples: np.ndarray, sample_rate: int, start_sec: float | None, end_sec: float | None) -> np.ndarray:
    start_idx = 0 if start_sec is None else max(0, int(round(start_sec * sample_rate)))
    end_idx = len(samples) if end_sec is None else min(len(samples), int(round(end_sec * sample_rate)))
    if end_idx < start_idx:
        raise ValueError(f"Invalid crop interval: start={start_sec}, end={end_sec}")
    return samples[start_idx:end_idx]


def _resample(samples: np.ndarray, input_sr: int, target_sr: int) -> np.ndarray:
    if input_sr == target_sr:
        return samples.astype(np.float32, copy=False)
    gcd = np.gcd(input_sr, target_sr)
    up = target_sr // gcd
    down = input_sr // gcd
    out = resample_poly(samples, up=up, down=down)
    return np.asarray(out, dtype=np.float32)


def load_audio_mono(
    path: str | Path,
    target_sample_rate: int = 16000,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> tuple[np.ndarray, int]:
    """Load audio, crop in seconds, convert to mono, resample, return float32."""
    path = Path(path)
    samples, input_sr = sf.read(path, dtype="float32", always_2d=True)
    mono = _to_mono(samples)
    cropped = _crop(mono, input_sr, start_sec, end_sec)
    resampled = _resample(cropped, input_sr, target_sample_rate)
    return np.ascontiguousarray(resampled, dtype=np.float32), target_sample_rate


def concatenate_segments(audio: np.ndarray, sample_rate: int, segments_sec: list[tuple[float, float]]) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for start_sec, end_sec in segments_sec:
        start = max(0, int(round(start_sec * sample_rate)))
        end = min(len(audio), int(round(end_sec * sample_rate)))
        if end > start:
            chunks.append(audio[start:end])
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.ascontiguousarray(np.concatenate(chunks), dtype=np.float32)
