"""Sample-rate conversion helpers for audio tensors."""

from __future__ import annotations

import math

import numpy as np
from scipy import signal

from app.inference_pipeline.errors import ContractValidationError


def resample_audio(
    audio: np.ndarray,
    source_sample_rate: int,
    target_sample_rate: int,
) -> np.ndarray:
    """Resample ``audio`` with shape ``(samples, channels)`` to target rate."""

    validate_sample_rate(source_sample_rate, "source_sample_rate")
    validate_sample_rate(target_sample_rate, "target_sample_rate")
    if audio.ndim != 2:
        raise ContractValidationError("audio must have shape (samples, channels)")
    if source_sample_rate == target_sample_rate:
        return audio.astype(np.float32, copy=False)

    divisor = math.gcd(source_sample_rate, target_sample_rate)
    up = target_sample_rate // divisor
    down = source_sample_rate // divisor
    return signal.resample_poly(audio, up, down, axis=0).astype(np.float32)


def validate_sample_rate(value: int, field_name: str) -> None:
    """Validate a positive integer sample rate."""

    if int(value) < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
