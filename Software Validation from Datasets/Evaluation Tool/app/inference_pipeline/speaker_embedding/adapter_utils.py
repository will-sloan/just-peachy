"""Shared audio and result helpers for optional speaker-embedding adapters."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import soundfile as sf

from app.inference_pipeline.audio_io.resample import resample_audio
from app.inference_pipeline.audio_io.segments import resolve_segment_frames
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.speaker_embedding.base import (
    EMBEDDING_STATUS_OK,
    SpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
    SpeakerEmbeddingRuntimeStats,
    embedding_id,
    normalize_vector,
    peak_gpu_memory_mb,
    process_memory_mb,
)
from app.utils.paths import model_root, resolve_model_path_from_logical


@dataclass(frozen=True)
class SegmentSamples:
    samples: np.ndarray
    sample_rate: int

    @property
    def duration_sec(self) -> float:
        return len(self.samples) / self.sample_rate


def load_segment_samples(
    segment: AudioSegment,
    *,
    target_sample_rate: int,
) -> SegmentSamples:
    """Load, crop, downmix/select, and resample one segment as mono float32."""

    if not segment.audio_path.is_file():
        raise FileNotFoundError(
            f"speaker embedding audio path does not exist: {segment.audio_path}"
        )
    info = sf.info(segment.audio_path)
    source_rate = int(info.samplerate)
    frame_range = resolve_segment_frames(
        segment.start_sec,
        segment.end_sec,
        source_rate,
        int(info.frames),
    )
    audio, _ = sf.read(
        segment.audio_path,
        start=frame_range.start_frame,
        frames=frame_range.frame_count,
        dtype="float32",
        always_2d=True,
    )
    if segment.channel_index is None:
        mono = audio.mean(axis=1, keepdims=True, dtype=np.float32)
    else:
        index = int(segment.channel_index)
        if index < 0 or index >= audio.shape[1]:
            raise ContractValidationError(
                "channel_index out of range for speaker embedding audio"
            )
        mono = audio[:, index : index + 1]
    resampled = resample_audio(mono, source_rate, target_sample_rate)
    return SegmentSamples(
        samples=np.ascontiguousarray(resampled[:, 0], dtype=np.float32),
        sample_rate=target_sample_rate,
    )


def successful_embedding(
    adapter: SpeakerEmbeddingBase,
    segment: AudioSegment,
    context: SpeakerEmbeddingContext,
    vector: Sequence[float] | np.ndarray,
    *,
    started_at: float,
    duration_sec: float,
    sample_rate: int,
    device: str,
    load_sec: float | None,
    metadata: Mapping[str, object] | None = None,
) -> SpeakerEmbedding:
    """Normalize and package a backend vector using the shared contract."""

    runtime = SpeakerEmbeddingRuntimeStats.from_timings(
        model_name=adapter.model_name,
        load_sec=load_sec,
        inference_sec=time.perf_counter() - started_at,
        audio_duration_sec=duration_sec,
        device=device,
        dtype=adapter.dtype,
        peak_gpu_memory_mb=peak_gpu_memory_mb(device),
        cpu_memory_mb=process_memory_mb(),
    )
    result = SpeakerEmbedding(
        embedding_id=embedding_id(context),
        vector=normalize_vector(vector),
        model_name=adapter.model_name,
        segment_duration_sec=duration_sec,
        device=device,
        runtime=runtime,
        status=EMBEDDING_STATUS_OK,
        reliable=True,
        recording_id=context.recording_id,
        utt_id=context.utt_id,
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
        sample_rate_hz=sample_rate,
        metadata=dict(metadata or {}),
    )
    adapter.last_embedding = result
    adapter.last_runtime_stats = runtime
    return result


def resolve_embedding_model_path(
    value: object,
    context: SpeakerEmbeddingContext,
) -> Path:
    """Resolve a local embedding model using Evaluation Tool path conventions."""

    if value is None or not str(value).strip():
        raise ContractValidationError("speaker embedding model path must be non-empty")
    configured = Path(str(value)).expanduser()
    if configured.is_absolute():
        candidates = [configured]
    else:
        candidates = [resolve_model_path_from_logical(configured)]
        if model_root().source != "environment override" and isinstance(context.run_config, Mapping):
            project_value = context.run_config.get("project_root")
            if project_value is not None:
                project_root = Path(str(project_value)).expanduser()
                candidates.extend(
                    (
                        project_root / "Evaluation Tool" / configured,
                        project_root / configured,
                        project_root.parent / configured,
                    )
                )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(
        "speaker embedding model does not exist; searched: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed


def non_negative_float(value: object, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc
    if parsed < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    return parsed
