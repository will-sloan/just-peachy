"""Shared audio and model-path helpers for optional ASR backends."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, Mapping

import numpy as np
import soundfile as sf

from app.inference_pipeline.asr.base import ASRContext
from app.inference_pipeline.audio_io.resample import resample_audio
from app.inference_pipeline.audio_io.segments import resolve_segment_frames
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.errors import ContractValidationError


@dataclass(frozen=True)
class ASRAudio:
    """Mono float32 audio prepared for an ASR backend."""

    samples: np.ndarray
    sample_rate: int

    @property
    def duration_sec(self) -> float:
        return len(self.samples) / self.sample_rate


def load_segment_audio(
    audio_segment: AudioSegment,
    *,
    target_sample_rate: int | None = None,
) -> ASRAudio:
    """Read, crop, select/downmix, and optionally resample one segment."""

    path = audio_segment.audio_path
    if not path.is_file():
        raise FileNotFoundError(f"ASR audio path does not exist: {path}")

    info = sf.info(path)
    source_sample_rate = int(info.samplerate)
    frame_range = resolve_segment_frames(
        audio_segment.start_sec,
        audio_segment.end_sec,
        source_sample_rate,
        int(info.frames),
    )
    audio, _ = sf.read(
        path,
        start=frame_range.start_frame,
        frames=frame_range.frame_count,
        dtype="float32",
        always_2d=True,
    )
    if audio_segment.channel_index is not None:
        channel_index = int(audio_segment.channel_index)
        if channel_index < 0 or channel_index >= audio.shape[1]:
            raise ContractValidationError(
                f"channel_index {channel_index} is out of range for {audio.shape[1]} channels"
            )
        mono = audio[:, channel_index : channel_index + 1]
    else:
        mono = np.mean(audio, axis=1, keepdims=True, dtype=np.float32)

    sample_rate = source_sample_rate
    if target_sample_rate is not None:
        sample_rate = _positive_int(target_sample_rate, "target_sample_rate")
        mono = resample_audio(mono, source_sample_rate, sample_rate)
    samples = np.ascontiguousarray(mono[:, 0], dtype=np.float32)
    return ASRAudio(samples=samples, sample_rate=sample_rate)


def resolve_model_path(value: object, context: ASRContext | None = None) -> Path:
    """Resolve a configured local asset path using the project's path conventions."""

    if value is None or not str(value).strip():
        raise ContractValidationError("model asset path must be a non-empty string")
    configured = Path(str(value)).expanduser()
    candidates = [configured] if configured.is_absolute() else _relative_candidates(
        configured,
        context,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"model asset does not exist; searched: {searched}")


@contextmanager
def temporary_pcm16_wav(audio: ASRAudio, *, prefix: str) -> Iterator[Path]:
    """Write backend-compatible mono PCM16 audio and remove it afterwards."""

    with TemporaryDirectory(prefix=prefix) as directory:
        path = Path(directory) / "segment.wav"
        sf.write(path, audio.samples, audio.sample_rate, subtype="PCM_16")
        yield path


def _relative_candidates(path: Path, context: ASRContext | None) -> list[Path]:
    tool_root = Path(__file__).resolve().parents[3]
    candidates = [
        Path.cwd() / path,
        tool_root / path,
        tool_root.parent / path,
        tool_root.parent.parent / path,
    ]
    project_root = _project_root(context)
    if project_root is not None:
        candidates.extend(
            (
                project_root / "Evaluation Tool" / path,
                project_root / path,
                project_root.parent / path,
            )
        )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _project_root(context: ASRContext | None) -> Path | None:
    if context is None or not isinstance(context.run_config, Mapping):
        return None
    value = context.run_config.get("project_root")
    if value is None or not str(value).strip():
        return None
    return Path(str(value)).expanduser()


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed
