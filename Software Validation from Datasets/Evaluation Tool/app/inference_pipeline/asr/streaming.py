"""Typed diagnostics for deterministic file-to-stream ASR replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np

from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject


STREAMING_DIAGNOSTICS_SCHEMA_VERSION = "streaming-diagnostics.v1"


@dataclass(frozen=True)
class StreamingReplayConfig:
    """Result-affecting settings for deterministic source-audio replay."""

    chunk_duration_ms: int = 100
    update_interval_ms: int = 500
    reset_policy: str = "per_segment"
    endpoint_policy: str = "backend_default"
    real_time_pacing: bool = False

    def __post_init__(self) -> None:
        if self.chunk_duration_ms < 1:
            raise ContractValidationError("streaming chunk_duration_ms must be >= 1")
        if self.update_interval_ms < 1:
            raise ContractValidationError("streaming update_interval_ms must be >= 1")
        if self.reset_policy not in {"per_segment", "per_record"}:
            raise ContractValidationError(
                "streaming reset_policy must be 'per_segment' or 'per_record'"
            )
        if not self.endpoint_policy.strip():
            raise ContractValidationError("streaming endpoint_policy must not be empty")
        if self.real_time_pacing:
            raise ContractValidationError(
                "campaign streaming replay must not sleep in real time; "
                "real_time_pacing must remain false"
            )

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, object] | None = None
    ) -> "StreamingReplayConfig":
        data = dict(value or {})
        return cls(
            chunk_duration_ms=_positive_int(
                data.get("chunk_duration_ms", 100), "chunk_duration_ms"
            ),
            update_interval_ms=_positive_int(
                data.get("update_interval_ms", 500), "update_interval_ms"
            ),
            reset_policy=str(data.get("reset_policy") or "per_segment"),
            endpoint_policy=str(data.get("endpoint_policy") or "backend_default"),
            real_time_pacing=bool(data.get("real_time_pacing", False)),
        )

    def to_jsonable(self) -> JsonObject:
        return {
            "chunk_duration_ms": self.chunk_duration_ms,
            "update_interval_ms": self.update_interval_ms,
            "reset_policy": self.reset_policy,
            "endpoint_policy": self.endpoint_policy,
            "real_time_pacing": self.real_time_pacing,
        }


@dataclass(frozen=True)
class StreamingUpdate:
    """One observable partial or final hypothesis during replay."""

    sequence: int
    audio_end_sec: float
    wall_time_sec: float
    text: str
    is_final: bool
    backend_latency_ms: float | None = None
    line_id: int | None = None
    event_type: str = "hypothesis"

    def to_jsonable(self) -> JsonObject:
        return {
            "schema_version": "streaming-update.v1",
            "sequence": self.sequence,
            "audio_end_sec": self.audio_end_sec,
            "wall_time_sec": self.wall_time_sec,
            "text": self.text,
            "is_final": self.is_final,
            "backend_latency_ms": self.backend_latency_ms,
            "line_id": self.line_id,
            "event_type": self.event_type,
        }


def iter_audio_chunks(
    samples: np.ndarray,
    *,
    sample_rate: int,
    chunk_duration_ms: int,
) -> Iterable[tuple[np.ndarray, float]]:
    """Yield contiguous deterministic chunks and cumulative audio seconds."""

    if sample_rate < 1:
        raise ContractValidationError("streaming sample_rate must be >= 1")
    if chunk_duration_ms < 1:
        raise ContractValidationError("streaming chunk_duration_ms must be >= 1")
    mono = np.ascontiguousarray(samples, dtype=np.float32).reshape(-1)
    chunk_samples = max(1, int(round(sample_rate * chunk_duration_ms / 1000.0)))
    for start in range(0, len(mono), chunk_samples):
        end = min(len(mono), start + chunk_samples)
        yield mono[start:end], end / sample_rate


def build_streaming_diagnostics(
    *,
    backend_id: str,
    replay: StreamingReplayConfig,
    updates: Sequence[StreamingUpdate],
    audio_duration_sec: float,
    processing_sec: float,
    initialization_sec: float | None,
    end_of_input_wall_sec: float,
    final_emitted_wall_sec: float | None,
    chunk_count: int,
    dropped_chunk_count: int = 0,
    invalid_chunk_count: int = 0,
    reset_count: int = 0,
    partial_hypotheses_supported: bool = True,
) -> JsonObject:
    """Build analysis-ready streaming metrics without inventing unsupported values."""

    ordered = tuple(sorted(updates, key=lambda item: item.sequence))
    nonempty = [item for item in ordered if item.text.strip()]
    partials = [item for item in ordered if not item.is_final and item.text.strip()]
    finals = [item for item in ordered if item.is_final]
    final_text = finals[-1].text if finals else (nonempty[-1].text if nonempty else "")
    first_partial = partials[0] if partials else None
    first_nonempty = nonempty[0] if nonempty else None
    finalization_latency = (
        max(0.0, final_emitted_wall_sec - end_of_input_wall_sec)
        if final_emitted_wall_sec is not None
        else None
    )
    partial_churn = _partial_churn(partials)
    final_stability = _final_prefix_stability(partials, final_text)
    duration = audio_duration_sec if audio_duration_sec > 0 else None
    streaming_rtf = processing_sec / duration if duration else None
    throughput = duration / processing_sec if duration and processing_sec > 0 else None
    partial_reason = (
        None
        if partial_hypotheses_supported
        else "backend does not expose observable partial hypotheses"
    )
    return {
        "schema_version": STREAMING_DIAGNOSTICS_SCHEMA_VERSION,
        "backend_id": backend_id,
        "capability": "native_streaming",
        "replay": replay.to_jsonable(),
        "updates": [item.to_jsonable() for item in ordered],
        "metrics": {
            "time_to_first_partial_sec": (
                first_partial.wall_time_sec if first_partial is not None else None
            ),
            "audio_to_first_partial_sec": (
                first_partial.audio_end_sec if first_partial is not None else None
            ),
            "time_to_first_nonempty_sec": (
                first_nonempty.wall_time_sec if first_nonempty is not None else None
            ),
            "audio_to_first_nonempty_sec": (
                first_nonempty.audio_end_sec if first_nonempty is not None else None
            ),
            "end_of_input_to_final_sec": finalization_latency,
            "finalization_latency_sec": finalization_latency,
            "partial_update_count": len(partials),
            "hypothesis_update_count": len(ordered),
            "partial_hypothesis_churn_tokens": partial_churn,
            "final_prefix_stability": final_stability,
            "reset_count": reset_count,
            "chunk_count": chunk_count,
            "dropped_chunk_count": dropped_chunk_count,
            "invalid_chunk_count": invalid_chunk_count,
            "streaming_rtf": streaming_rtf,
            "processed_audio_sec_per_wall_sec": throughput,
            "model_initialization_sec": initialization_sec,
            "stream_processing_sec": processing_sec,
            "audio_duration_sec": audio_duration_sec,
        },
        "availability": {
            "partial_hypotheses": {
                "available": partial_hypotheses_supported,
                "reason": partial_reason,
            },
            "backend_partial_latency": {
                "available": any(
                    item.backend_latency_ms is not None for item in ordered
                ),
                "reason": (
                    None
                    if any(item.backend_latency_ms is not None for item in ordered)
                    else "backend did not expose per-update inference latency"
                ),
            },
        },
        "definitions": {
            "partial_hypothesis_churn_tokens": (
                "sum of token edit distances between consecutive non-empty partial hypotheses"
            ),
            "final_prefix_stability": (
                "longest common token prefix between the last partial and final text, "
                "divided by final token count"
            ),
            "time_basis": "monotonic process wall time without real-time replay sleeping",
        },
    }


def _partial_churn(updates: Sequence[StreamingUpdate]) -> int | None:
    if len(updates) < 2:
        return 0 if updates else None
    return sum(
        _edit_distance(left.text.split(), right.text.split())
        for left, right in zip(updates, updates[1:], strict=False)
    )


def _final_prefix_stability(
    partials: Sequence[StreamingUpdate], final_text: str
) -> float | None:
    final_tokens = final_text.split()
    if not partials or not final_tokens:
        return None
    partial_tokens = partials[-1].text.split()
    common = 0
    for left, right in zip(partial_tokens, final_tokens, strict=False):
        if left != right:
            break
        common += 1
    return common / len(final_tokens)


def _edit_distance(left: Sequence[str], right: Sequence[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_item in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_item in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed
