"""High-level audio loader for Evaluation Tool inference records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import soundfile as sf
import torch

from app.inference_pipeline.audio_io.multichannel import apply_channel_policy
from app.inference_pipeline.audio_io.resample import resample_audio, validate_sample_rate
from app.inference_pipeline.audio_io.segments import SegmentFrames, resolve_segment_frames
from app.inference_pipeline.errors import ContractValidationError, MissingRequiredFieldError
from app.inference_pipeline.typing import JsonObject


DEFAULT_SAMPLE_RATE_HZ = 16000
DEFAULT_CHANNEL_POLICY = "mono"


@dataclass(frozen=True)
class LoadedAudio:
    """Model-ready audio and metadata for one Evaluation Tool record."""

    waveform: torch.Tensor
    sample_rate: int
    duration_sec: float
    num_channels: int
    channel_policy: JsonObject
    source_sample_rate: int
    source_num_channels: int
    source_duration_sec: float
    segment_start_sec: float | None
    segment_end_sec: float | None
    audio_path: Path


def load_audio(record: Mapping[str, object], config: object | None = None) -> LoadedAudio:
    """Load ``record["inference_audio_path"]`` as a channel-first torch tensor."""

    audio_path = _inference_audio_path(record)
    if not audio_path.is_file():
        raise FileNotFoundError(f"inference_audio_path does not exist: {audio_path}")

    target_sample_rate = _target_sample_rate(config)
    channel_policy = _channel_policy(config)
    channel_index = _channel_index(record, config)

    info = sf.info(audio_path)
    source_sample_rate = int(info.samplerate)
    source_channels = int(info.channels)
    source_frames = int(info.frames)
    validate_sample_rate(source_sample_rate, "source_sample_rate")
    segment = resolve_segment_frames(
        record.get("start_sec"),
        record.get("end_sec"),
        source_sample_rate,
        source_frames,
    )

    source_audio = _read_source_segment(audio_path, segment)
    policy_audio, policy_metadata = apply_channel_policy(
        source_audio,
        channel_policy,
        channel_index,
    )
    resampled = resample_audio(policy_audio, source_sample_rate, target_sample_rate)
    waveform = torch.from_numpy(np.ascontiguousarray(resampled.T))

    return LoadedAudio(
        waveform=waveform,
        sample_rate=target_sample_rate,
        duration_sec=waveform.shape[1] / target_sample_rate,
        num_channels=int(waveform.shape[0]),
        channel_policy=policy_metadata,
        source_sample_rate=source_sample_rate,
        source_num_channels=source_channels,
        source_duration_sec=source_frames / source_sample_rate,
        segment_start_sec=segment.start_sec,
        segment_end_sec=segment.end_sec,
        audio_path=audio_path,
    )


def _read_source_segment(audio_path: Path, segment: SegmentFrames) -> np.ndarray:
    audio, _sample_rate = sf.read(
        audio_path,
        start=segment.start_frame,
        frames=segment.frame_count,
        dtype="float32",
        always_2d=True,
    )
    return audio.astype(np.float32, copy=False)


def _inference_audio_path(record: Mapping[str, object]) -> Path:
    if "inference_audio_path" not in record:
        raise MissingRequiredFieldError("missing required field 'inference_audio_path'")
    value = record["inference_audio_path"]
    if value is None or str(value).strip() == "":
        raise MissingRequiredFieldError("missing required field 'inference_audio_path'")
    return Path(str(value))


def _target_sample_rate(config: object | None) -> int:
    audio_config = _mapping_child(config, "audio")
    for key in ("target_sample_rate_hz", "sample_rate_hz", "target_sample_rate"):
        value = _mapping_get(audio_config, key)
        if value is not None:
            return _positive_int(value, key)

    runtime = getattr(config, "runtime", None)
    runtime_value = getattr(runtime, "sample_rate_hz", None)
    if runtime_value is not None:
        return _positive_int(runtime_value, "sample_rate_hz")

    runtime_config = _mapping_child(config, "runtime")
    runtime_mapping_value = _mapping_get(runtime_config, "sample_rate_hz")
    if runtime_mapping_value is not None:
        return _positive_int(runtime_mapping_value, "sample_rate_hz")

    top_level_value = _mapping_get(config, "sample_rate_hz")
    if top_level_value is not None:
        return _positive_int(top_level_value, "sample_rate_hz")

    return DEFAULT_SAMPLE_RATE_HZ


def _channel_policy(config: object | None) -> str:
    audio_config = _mapping_child(config, "audio")
    return str(
        _mapping_get(audio_config, "channel_policy")
        or _mapping_get(config, "channel_policy")
        or DEFAULT_CHANNEL_POLICY
    )


def _channel_index(record: Mapping[str, object], config: object | None) -> int | None:
    audio_config = _mapping_child(config, "audio")
    value = (
        _mapping_get(audio_config, "channel_index")
        if _mapping_get(audio_config, "channel_index") is not None
        else _mapping_get(config, "channel_index")
    )
    if value is None:
        value = record.get("channel_index")
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("channel_index must be an integer") from exc


def _mapping_child(config: object | None, key: str) -> Mapping[str, object] | None:
    value = _mapping_get(config, key)
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value
    raise ContractValidationError(f"{key} config must be a mapping")


def _mapping_get(config: object | None, key: str) -> object | None:
    if isinstance(config, Mapping):
        return config.get(key)
    return None


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    validate_sample_rate(parsed, field_name)
    return parsed
