"""Shared audio and segment helpers for optional diarization backends."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Any, Iterable, Iterator

import numpy as np
import soundfile as sf

from app.inference_pipeline.audio_io.resample import resample_audio
from app.inference_pipeline.errors import ContractValidationError


def audio_path(audio: object) -> Path:
    value = getattr(audio, "audio_path", None)
    if value is None:
        value = getattr(audio, "path", None)
    if value is None or not str(value).strip():
        raise ContractValidationError("diarization audio object must expose audio_path")
    path = Path(str(value))
    if not path.is_file():
        raise FileNotFoundError(f"diarization audio path does not exist: {path}")
    return path


def mono_samples(audio: object, *, target_sample_rate: int) -> np.ndarray:
    """Return model-ready mono float32 samples, preferring loaded/cropped audio."""

    if int(target_sample_rate) < 1:
        raise ContractValidationError("diarization target_sample_rate must be >= 1")
    waveform = getattr(audio, "waveform", None)
    source_rate = getattr(audio, "sample_rate", None)
    if waveform is not None and source_rate is not None:
        array = waveform.detach().cpu().float().numpy()
        if array.ndim == 1:
            samples = array
        elif array.ndim == 2:
            samples = array.mean(axis=0)
        else:
            raise ContractValidationError(
                "diarization waveform must have shape [samples] or [channels, samples]"
            )
        source_rate = int(source_rate)
    else:
        samples, source_rate = sf.read(
            audio_path(audio),
            dtype="float32",
            always_2d=True,
        )
        samples = samples.mean(axis=1, dtype=np.float32)
        source_rate = int(source_rate)
    samples = np.ascontiguousarray(samples, dtype=np.float32)
    if samples.size < 1:
        raise ContractValidationError("diarization audio must be non-empty")
    if source_rate != target_sample_rate:
        samples = resample_audio(
            samples[:, None], source_rate, target_sample_rate
        )[:, 0]
    return np.ascontiguousarray(samples, dtype=np.float32)


@contextmanager
def materialized_audio_path(
    audio: object,
    *,
    prefix: str = "diarization-audio-",
) -> Iterator[Path]:
    """Yield a WAV containing exactly the model-ready record audio.

    Evaluation records may select only part of a longer source recording.  A
    filepath-only backend must not be handed that original path because doing
    so silently diarizes audio outside ``start_sec``/``end_sec`` and produces
    timestamps in a different coordinate system from the in-memory backends.
    When a loaded waveform is available, materialize that already-cropped,
    channel-processed waveform.  Otherwise, crop the source path using segment
    metadata.  Whole-file path-only inputs can be used directly.
    """

    waveform = getattr(audio, "waveform", None)
    sample_rate = getattr(audio, "sample_rate", None)
    if waveform is not None and sample_rate is not None:
        samples = _waveform_for_soundfile(waveform)
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            path = Path(directory) / "record_audio.wav"
            sf.write(path, samples, int(sample_rate), subtype="PCM_16")
            yield path
        return

    source_path = audio_path(audio)
    start_sec = _optional_nonnegative_float(
        getattr(audio, "segment_start_sec", None),
        "segment_start_sec",
    )
    end_sec = _optional_nonnegative_float(
        getattr(audio, "segment_end_sec", None),
        "segment_end_sec",
    )
    if start_sec is None and end_sec is None:
        yield source_path
        return

    info = sf.info(source_path)
    source_rate = int(info.samplerate)
    start_frame = int(round((start_sec or 0.0) * source_rate))
    end_frame = (
        int(round(end_sec * source_rate))
        if end_sec is not None
        else int(info.frames)
    )
    if start_frame < 0 or end_frame > int(info.frames) or end_frame <= start_frame:
        raise ContractValidationError(
            "diarization record bounds must select a non-empty interval inside the source audio"
        )
    samples, _ = sf.read(
        source_path,
        start=start_frame,
        frames=end_frame - start_frame,
        dtype="float32",
        always_2d=True,
    )
    with tempfile.TemporaryDirectory(prefix=prefix) as directory:
        path = Path(directory) / "record_audio.wav"
        sf.write(path, samples, source_rate, subtype="PCM_16")
        yield path


def _waveform_for_soundfile(waveform: object) -> np.ndarray:
    value = waveform
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "float"):
        value = value.float()
    if hasattr(value, "numpy"):
        value = value.numpy()
    samples = np.asarray(value, dtype=np.float32)
    if samples.ndim == 1:
        samples = samples[:, None]
    elif samples.ndim == 2:
        # LoadedAudio is channel-first while soundfile is sample-first.
        samples = samples.T
    else:
        raise ContractValidationError(
            "diarization waveform must have shape [samples] or [channels, samples]"
        )
    if samples.shape[0] < 1 or samples.shape[1] < 1:
        raise ContractValidationError("diarization waveform must be non-empty")
    return np.ascontiguousarray(samples, dtype=np.float32)


def _optional_nonnegative_float(value: object, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc
    if parsed < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    return parsed


def anonymous_speaker_label(value: object) -> str:
    try:
        return f"speaker_{int(value):02d}"
    except (TypeError, ValueError):
        text = str(value).strip()
        return text if text.startswith("speaker_") else f"speaker_{text}"


def sorted_segments(value: object) -> Iterable[Any]:
    if hasattr(value, "sort_by_start_time"):
        return value.sort_by_start_time()
    if isinstance(value, Iterable):
        return value
    raise ContractValidationError("diarization backend returned a non-iterable result")
