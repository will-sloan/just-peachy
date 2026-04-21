"""Audio DSP primitives used by on-the-fly augmentation."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal


PEAK_LIMIT = 0.98
EPSILON = 1e-12


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    """Read WAV/FLAC audio as float32 with shape ``(samples, channels)``."""

    audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    return audio, int(sample_rate)


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    """Write float audio to a WAV file with peak protection."""

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, peak_protect(audio), sample_rate, subtype="PCM_16")


def load_rir(path: Path, target_sample_rate: int) -> np.ndarray:
    """Load, mono-convert, resample, and normalize a room impulse response."""

    rir, rir_sample_rate = read_audio(path)
    rir_mono = mono(rir)
    if rir_sample_rate != target_sample_rate:
        rir_mono = resample_audio(rir_mono[:, None], rir_sample_rate, target_sample_rate)[:, 0]
    peak = float(np.max(np.abs(rir_mono))) if rir_mono.size else 0.0
    if peak > EPSILON:
        rir_mono = rir_mono / peak
    return rir_mono.astype(np.float32)


def resample_audio(audio: np.ndarray, source_sample_rate: int, target_sample_rate: int) -> np.ndarray:
    """Resample audio with polyphase filtering."""

    if source_sample_rate == target_sample_rate:
        return audio.astype(np.float32, copy=False)
    divisor = math.gcd(source_sample_rate, target_sample_rate)
    up = target_sample_rate // divisor
    down = source_sample_rate // divisor
    return signal.resample_poly(audio, up, down, axis=0).astype(np.float32)


def convolve_with_rir(audio: np.ndarray, rir: np.ndarray) -> np.ndarray:
    """Convolve each source channel with a mono RIR."""

    if not rir.size:
        return audio
    channels = []
    for channel_index in range(audio.shape[1]):
        convolved = signal.fftconvolve(audio[:, channel_index], rir, mode="full")
        channels.append(convolved.astype(np.float32))
    return np.stack(channels, axis=1)


def add_noise_at_snr(
    audio: np.ndarray,
    noise_type: str,
    snr_db: float,
    seed_text: str,
) -> np.ndarray:
    """Add deterministic white or pink noise at a target SNR in dB."""

    rng = np.random.default_rng(stable_seed(seed_text))
    if noise_type == "white":
        noise = rng.standard_normal(audio.shape).astype(np.float32)
    elif noise_type == "pink":
        noise = np.stack(
            [pink_noise(audio.shape[0], rng) for _ in range(audio.shape[1])],
            axis=1,
        )
    else:
        raise ValueError(f"Unsupported noise type {noise_type!r}")

    signal_rms = rms(audio)
    noise_rms = rms(noise)
    if noise_rms <= EPSILON:
        return audio
    target_noise_rms = signal_rms / (10 ** (snr_db / 20.0))
    return audio + noise * (target_noise_rms / noise_rms)


def pink_noise(length: int, rng: np.random.Generator) -> np.ndarray:
    """Generate approximate pink noise using frequency-domain shaping."""

    if length <= 0:
        return np.zeros(0, dtype=np.float32)
    white = rng.standard_normal(length)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(length)
    scale = np.ones_like(freqs)
    scale[1:] = 1.0 / np.sqrt(freqs[1:])
    spectrum *= scale
    pink = np.fft.irfft(spectrum, n=length)
    pink = pink - np.mean(pink)
    std = np.std(pink)
    if std > EPSILON:
        pink = pink / std
    return pink.astype(np.float32)


def peak_protect(audio: np.ndarray, limit: float = PEAK_LIMIT) -> np.ndarray:
    """Scale audio to avoid clipping while preserving relative levels."""

    if audio.size == 0:
        return audio.astype(np.float32, copy=False)
    max_abs = float(np.max(np.abs(audio)))
    if max_abs > limit:
        audio = audio * (limit / max_abs)
    return audio.astype(np.float32, copy=False)


def mono(audio: np.ndarray) -> np.ndarray:
    """Convert audio to mono while preserving sample count."""

    if audio.ndim == 1:
        return audio.astype(np.float32, copy=False)
    return np.mean(audio, axis=1).astype(np.float32)


def rms(audio: np.ndarray) -> float:
    """Return root mean square amplitude."""

    return float(np.sqrt(np.mean(np.square(audio), dtype=np.float64) + EPSILON))


def stable_seed(text: str) -> int:
    """Create a deterministic 32-bit seed from text."""

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="little", signed=False)

