"""Segmentation interfaces and shared helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.contracts import AudioSegment, EvaluationRecord, SpeechRegion
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject


@dataclass(frozen=True)
class SegmenterParameters:
    """Common chunking policy parameters."""

    min_chunk_sec: float = 0.2
    max_chunk_sec: float = 30.0
    merge_gap_sec: float = 0.2
    left_pad_sec: float = 0.0
    right_pad_sec: float = 0.0
    clip_to_record_bounds: bool = True
    target: str = "asr"

    def __post_init__(self) -> None:
        for field_name in (
            "min_chunk_sec",
            "merge_gap_sec",
            "left_pad_sec",
            "right_pad_sec",
        ):
            if getattr(self, field_name) < 0:
                raise ContractValidationError(f"{field_name} must be >= 0")
        if self.max_chunk_sec <= 0:
            raise ContractValidationError("max_chunk_sec must be > 0")
        if not self.target.strip():
            raise ContractValidationError("target must be non-empty")

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, object] | None = None,
    ) -> "SegmenterParameters":
        data = dict(mapping or {})
        return cls(
            min_chunk_sec=_float_value(data.get("min_chunk_sec", 0.2), "min_chunk_sec"),
            max_chunk_sec=_float_value(data.get("max_chunk_sec", 30.0), "max_chunk_sec"),
            merge_gap_sec=_float_value(data.get("merge_gap_sec", 0.2), "merge_gap_sec"),
            left_pad_sec=_float_value(data.get("left_pad_sec", 0.0), "left_pad_sec"),
            right_pad_sec=_float_value(data.get("right_pad_sec", 0.0), "right_pad_sec"),
            clip_to_record_bounds=_bool_value(
                data.get("clip_to_record_bounds", True),
                "clip_to_record_bounds",
            ),
            target=str(data.get("target", "asr")),
        )

    def to_jsonable(self) -> JsonObject:
        return {
            "min_chunk_sec": self.min_chunk_sec,
            "max_chunk_sec": self.max_chunk_sec,
            "merge_gap_sec": self.merge_gap_sec,
            "left_pad_sec": self.left_pad_sec,
            "right_pad_sec": self.right_pad_sec,
            "clip_to_record_bounds": self.clip_to_record_bounds,
            "target": self.target,
        }


@dataclass(frozen=True)
class SegmentTrace:
    """Trace metadata linking an AudioSegment back to one Evaluation Tool row."""

    recording_id: str
    utt_id: str
    segment_index: int
    audio_path: Path
    start_sec: float | None
    end_sec: float | None
    target: str = "asr"

    def to_jsonable(self) -> JsonObject:
        return {
            "recording_id": self.recording_id,
            "utt_id": self.utt_id,
            "segment_index": self.segment_index,
            "audio_path": str(self.audio_path),
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "target": self.target,
        }


class SegmenterBase(ABC):
    """Backend-swappable segmenter interface."""

    name = "segmenter_base"

    def __init__(
        self,
        params: SegmenterParameters | Mapping[str, object] | None = None,
    ) -> None:
        self.params = (
            params
            if isinstance(params, SegmenterParameters)
            else SegmenterParameters.from_mapping(params)
        )

    @abstractmethod
    def segment(
        self,
        record: EvaluationRecord,
        speech_regions: Sequence[SpeechRegion],
        audio: object | None = None,
    ) -> list[AudioSegment]:
        """Return model-friendly audio segments for one Evaluation Tool row."""


class NoOpSegmenter(SegmenterBase):
    """Disabled segmenter that emits no chunks."""

    name = "no_op_segmentation"

    def segment(
        self,
        record: EvaluationRecord,
        speech_regions: Sequence[SpeechRegion],
        audio: object | None = None,
    ) -> list[AudioSegment]:
        _ = (record, speech_regions, audio)
        return []


class FixedSegmenter(SegmenterBase):
    """Deterministic segmenter for focused tests."""

    name = "fixed_segmentation"

    def __init__(self, segments: Sequence[AudioSegment]) -> None:
        super().__init__()
        self.segments = tuple(segments)

    def segment(
        self,
        record: EvaluationRecord,
        speech_regions: Sequence[SpeechRegion],
        audio: object | None = None,
    ) -> list[AudioSegment]:
        _ = (record, speech_regions, audio)
        return list(self.segments)


def build_segmenter_from_config(config: object) -> SegmenterBase | None:
    """Instantiate the configured segmenter without loading unrelated models."""

    component = _segmentation_component(config)
    if component is None or not _component_enabled(component):
        return None

    name = _component_name(component)
    params = _component_params(component)
    if name == "no_op_segmentation":
        return NoOpSegmenter(params)
    if name == "vad_chunks":
        from app.inference_pipeline.segmentation.vad_chunker import VADChunker

        return VADChunker(params)
    raise ContractValidationError(f"unknown segmentation component {name!r}")


def trace_segments(
    record: EvaluationRecord,
    segments: Sequence[AudioSegment],
    *,
    target: str = "asr",
) -> list[SegmentTrace]:
    """Return JSON-safe trace rows without changing AudioSegment."""

    return [
        SegmentTrace(
            recording_id=record.recording_id,
            utt_id=record.utt_id,
            segment_index=index,
            audio_path=segment.audio_path,
            start_sec=segment.start_sec,
            end_sec=segment.end_sec,
            target=target,
        )
        for index, segment in enumerate(segments)
    ]


def write_segments_jsonable(segments: Sequence[AudioSegment]) -> list[JsonObject]:
    """Return JSON-safe AudioSegment rows."""

    return [segment.to_jsonable() for segment in segments]


def component_report_path(reports_root: Path, run_id: str) -> Path:
    """Return the required segmentation component report path."""

    return reports_root / "component_reports" / "segmentation" / f"segmentation_report_{run_id}.md"


def _segmentation_component(config: object) -> object | None:
    components = getattr(config, "components", None)
    if isinstance(components, Mapping):
        return components.get("segmentation")
    if isinstance(config, Mapping):
        raw_components = config.get("components")
        if isinstance(raw_components, Mapping):
            return raw_components.get("segmentation")
        return config.get("segmentation")
    return None


def _component_name(component: object) -> str:
    if isinstance(component, Mapping):
        return str(component.get("name") or "")
    return str(getattr(component, "name", ""))


def _component_enabled(component: object) -> bool:
    if isinstance(component, Mapping):
        return bool(component.get("enabled", True))
    return bool(getattr(component, "enabled", True))


def _component_params(component: object) -> Mapping[str, object]:
    if isinstance(component, Mapping):
        value = component.get("params") or {}
    else:
        value = getattr(component, "params", {}) or {}
    if not isinstance(value, Mapping):
        raise ContractValidationError("segmentation params must be a mapping")
    return value


def _float_value(value: object, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc


def _bool_value(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    raise ContractValidationError(f"{field_name} must be boolean")
