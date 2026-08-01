"""Optional diarization interfaces, metrics, and reporting helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.contracts import SpeechRegion
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.inference_pipeline.typing import JsonObject


class DiarizationUnavailableError(InferencePipelineError):
    """Raised when an optional diarization backend cannot run locally."""


@dataclass(frozen=True)
class SpeakerTurnRegion:
    """Anonymous diarization speaker-turn region.

    The label is a backend-local turn label such as ``speaker_00``. It must not
    be treated as a named product speaker label.
    """

    start_sec: float
    end_sec: float
    speaker_turn_label: str
    confidence: float | None = None
    channel_index: int | None = None
    is_overlap: bool = False
    source: str | None = None

    def __post_init__(self) -> None:
        try:
            start_sec = float(self.start_sec)
            end_sec = float(self.end_sec)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                "SpeakerTurnRegion times must be numeric"
            ) from exc
        _validate_time_range(start_sec, end_sec, "SpeakerTurnRegion")
        label = str(self.speaker_turn_label).strip()
        if not label:
            raise ContractValidationError("speaker_turn_label must be non-empty")
        if any(character.isspace() for character in label):
            raise ContractValidationError("speaker_turn_label must not contain whitespace")
        try:
            confidence = None if self.confidence is None else float(self.confidence)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                "SpeakerTurnRegion confidence must be numeric"
            ) from exc
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ContractValidationError("SpeakerTurnRegion confidence must be in [0, 1]")
        try:
            channel_index = None if self.channel_index is None else int(self.channel_index)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                "SpeakerTurnRegion channel_index must be an integer"
            ) from exc
        if channel_index is not None and channel_index < 0:
            raise ContractValidationError("SpeakerTurnRegion channel_index must be >= 0")
        object.__setattr__(self, "start_sec", start_sec)
        object.__setattr__(self, "end_sec", end_sec)
        object.__setattr__(self, "speaker_turn_label", label)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "channel_index", channel_index)

    def to_speech_region(self) -> SpeechRegion:
        """Return a segmentation-compatible region without naming a speaker."""

        return SpeechRegion(
            start_sec=self.start_sec,
            end_sec=self.end_sec,
            confidence=self.confidence,
            channel_index=self.channel_index,
            label=f"diarization:{self.speaker_turn_label}",
        )

    def to_jsonable(self) -> JsonObject:
        return {
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "speaker_turn_label": self.speaker_turn_label,
            "confidence": self.confidence,
            "channel_index": self.channel_index,
            "is_overlap": self.is_overlap,
            "source": self.source,
        }


@dataclass(frozen=True)
class DiarizationParameters:
    """Common options for optional diarization backends."""

    model_source: str = "pyannote/speaker-diarization-community-1"
    min_turn_sec: float = 0.05
    min_speakers: int | None = None
    max_speakers: int | None = None
    collar_sec: float = 0.0
    auth_token_env: str = "PYANNOTE_AUTH_TOKEN"
    cache_dir: str | None = None
    allow_model_downloads: bool = False

    def __post_init__(self) -> None:
        if not self.model_source.strip():
            raise ContractValidationError("diarization model_source must be non-empty")
        if self.min_turn_sec < 0:
            raise ContractValidationError("diarization min_turn_sec must be >= 0")
        if self.collar_sec < 0:
            raise ContractValidationError("diarization collar_sec must be >= 0")
        for field_name in ("min_speakers", "max_speakers"):
            value = getattr(self, field_name)
            if value is not None and value < 1:
                raise ContractValidationError(f"{field_name} must be >= 1")
        if (
            self.min_speakers is not None
            and self.max_speakers is not None
            and self.min_speakers > self.max_speakers
        ):
            raise ContractValidationError("min_speakers must be <= max_speakers")

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, object] | None = None,
    ) -> "DiarizationParameters":
        data = dict(mapping or {})
        return cls(
            model_source=str(
                data.get("model_source")
                or data.get("model_name")
                or "pyannote/speaker-diarization-community-1"
            ),
            min_turn_sec=_float_value(data.get("min_turn_sec", 0.05), "min_turn_sec"),
            min_speakers=_optional_int(data.get("min_speakers"), "min_speakers"),
            max_speakers=_optional_int(data.get("max_speakers"), "max_speakers"),
            collar_sec=_float_value(data.get("collar_sec", 0.0), "collar_sec"),
            auth_token_env=str(data.get("auth_token_env") or "PYANNOTE_AUTH_TOKEN"),
            cache_dir=_optional_string(data.get("cache_dir")),
            allow_model_downloads=_bool_value(
                data.get("allow_model_downloads", False),
                "allow_model_downloads",
            ),
        )

    def to_jsonable(self) -> JsonObject:
        return {
            "model_source": self.model_source,
            "min_turn_sec": self.min_turn_sec,
            "min_speakers": self.min_speakers,
            "max_speakers": self.max_speakers,
            "collar_sec": self.collar_sec,
            "auth_token_env": self.auth_token_env,
            "cache_dir": self.cache_dir,
            "allow_model_downloads": self.allow_model_downloads,
        }


class DiarizationBase(ABC):
    """Backend-swappable optional diarizer interface."""

    name = "diarization_base"
    model_name = "diarization_base"

    def __init__(
        self,
        params: DiarizationParameters | Mapping[str, object] | None = None,
    ) -> None:
        self.params = (
            params
            if isinstance(params, DiarizationParameters)
            else DiarizationParameters.from_mapping(params)
        )
        self.model_name = self.params.model_source

    @abstractmethod
    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        """Return anonymous speaker turns for model-ready audio."""


class NoOpDiarizer(DiarizationBase):
    """Disabled diarizer that emits no turns."""

    name = "no_op_diarization"
    model_name = "no_op_diarization"

    def __init__(
        self,
        params: DiarizationParameters | Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(params)
        self.model_name = self.name

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        _ = audio
        return []


class FixedDiarizer(DiarizationBase):
    """Deterministic adapter for tests and smoke reports."""

    name = "fixed_diarization"
    model_name = "fixed_diarization"

    def __init__(self, turns: Sequence[SpeakerTurnRegion]) -> None:
        super().__init__({"model_source": self.model_name})
        self.turns = tuple(turns)

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        _ = audio
        return list(self.turns)


@dataclass(frozen=True)
class DiarizationMetrics:
    """Baseline comparison metrics for optional diarization."""

    predicted_turn_count: int
    reference_turn_count: int
    predicted_speaker_count: int
    reference_speaker_count: int
    diarization_segment_count: int | None = None
    vad_only_segment_count: int | None = None
    der: float | None = None
    jer: float | None = None
    speaker_attributed_wer: float | None = None
    named_speaker_false_assignment_rate_before: float | None = None
    named_speaker_false_assignment_rate_after: float | None = None
    overlap_segment_detection_rate: float | None = None
    overlap_predicted_turn_count: int = 0
    runtime_sec: float | None = None
    memory_overhead_mb: float | None = None

    def to_jsonable(self) -> JsonObject:
        return {
            "predicted_turn_count": self.predicted_turn_count,
            "reference_turn_count": self.reference_turn_count,
            "predicted_speaker_count": self.predicted_speaker_count,
            "reference_speaker_count": self.reference_speaker_count,
            "diarization_segment_count": self.diarization_segment_count,
            "vad_only_segment_count": self.vad_only_segment_count,
            "der": self.der,
            "jer": self.jer,
            "speaker_attributed_wer": self.speaker_attributed_wer,
            "named_speaker_false_assignment_rate_before": (
                self.named_speaker_false_assignment_rate_before
            ),
            "named_speaker_false_assignment_rate_after": (
                self.named_speaker_false_assignment_rate_after
            ),
            "overlap_segment_detection_rate": self.overlap_segment_detection_rate,
            "overlap_predicted_turn_count": self.overlap_predicted_turn_count,
            "runtime_sec": self.runtime_sec,
            "memory_overhead_mb": self.memory_overhead_mb,
        }

    def to_markdown_rows(self) -> list[str]:
        return [
            f"- Predicted turn count: `{self.predicted_turn_count}`",
            f"- Reference turn count: `{self.reference_turn_count}`",
            f"- Predicted anonymous speaker count: `{self.predicted_speaker_count}`",
            f"- Reference speaker count: `{self.reference_speaker_count}`",
            f"- VAD-only segment count: `{_format_metric(self.vad_only_segment_count)}`",
            f"- Diarization-assisted segment count: `{_format_metric(self.diarization_segment_count)}`",
            f"- DER: `{_format_metric(self.der)}`",
            f"- JER: `{_format_metric(self.jer)}`",
            f"- Speaker-attributed WER: `{_format_metric(self.speaker_attributed_wer)}`",
            "- Named-speaker false assignment rate before: "
            f"`{_format_metric(self.named_speaker_false_assignment_rate_before)}`",
            "- Named-speaker false assignment rate after: "
            f"`{_format_metric(self.named_speaker_false_assignment_rate_after)}`",
            "- Overlap segment detection rate: "
            f"`{_format_metric(self.overlap_segment_detection_rate)}`",
            f"- Predicted overlap turn count: `{self.overlap_predicted_turn_count}`",
            f"- Diarization runtime sec: `{_format_metric(self.runtime_sec)}`",
            f"- Memory overhead MB: `{_format_metric(self.memory_overhead_mb)}`",
        ]


def build_diarizer_from_config(config: object) -> DiarizationBase | None:
    """Instantiate the configured optional diarizer without eager model loads."""

    component = _diarization_component(config)
    if component is None or not _component_enabled(component):
        return None

    name = _component_name(component)
    params = _component_params(component)
    if name == "no_op_diarization":
        return NoOpDiarizer(params)
    if name == "pyannote_community":
        from app.inference_pipeline.diarization.pyannote_adapter import (
            PyannoteCommunityDiarizer,
        )

        return PyannoteCommunityDiarizer(params)
    if name == "sherpa_onnx_diarization":
        from app.inference_pipeline.diarization.sherpa_onnx_adapter import (
            SherpaOnnxDiarizer,
        )

        return SherpaOnnxDiarizer(params)
    if name == "picovoice_falcon":
        from app.inference_pipeline.diarization.falcon_adapter import (
            PicovoiceFalconDiarizer,
        )

        return PicovoiceFalconDiarizer(params)
    if name == "nemo_diarization":
        from app.inference_pipeline.diarization.nemo_adapter import NemoDiarizer

        return NemoDiarizer(params)
    raise ContractValidationError(f"unknown diarization component {name!r}")


def speaker_turns_to_speech_regions(
    turns: Sequence[SpeakerTurnRegion],
) -> list[SpeechRegion]:
    """Convert anonymous turns into segmentation regions."""

    return [turn.to_speech_region() for turn in turns]


def write_turns_jsonable(turns: Sequence[SpeakerTurnRegion]) -> list[JsonObject]:
    """Return JSON-safe diarization turn rows."""

    return [turn.to_jsonable() for turn in turns]


def speaker_turns_to_rttm_lines(
    recording_id: str,
    turns: Sequence[SpeakerTurnRegion],
    *,
    time_offset_sec: float = 0.0,
) -> list[str]:
    """Serialize anonymous turns as standards-compatible RTTM SPEAKER rows.

    Backend timestamps are relative to the model-ready record audio.  The
    optional offset maps them back to source-recording coordinates before the
    Evaluation Tool writes ``predictions/segments.rttm``.
    """

    file_id = str(recording_id).strip()
    if not file_id or any(character.isspace() for character in file_id):
        raise ContractValidationError(
            "RTTM recording_id must be non-empty and contain no whitespace"
        )
    try:
        offset = float(time_offset_sec)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("RTTM time_offset_sec must be numeric") from exc
    if not math.isfinite(offset) or offset < 0:
        raise ContractValidationError("RTTM time_offset_sec must be finite and >= 0")

    lines: list[str] = []
    for turn in sorted(
        turns,
        key=lambda item: (item.start_sec, item.end_sec, item.speaker_turn_label),
    ):
        start = offset + turn.start_sec
        duration = turn.end_sec - turn.start_sec
        channel = (turn.channel_index + 1) if turn.channel_index is not None else 1
        lines.append(
            f"SPEAKER {file_id} {channel} {start:.6f} {duration:.6f} "
            f"<NA> <NA> {turn.speaker_turn_label} <NA> <NA>"
        )
    return lines


def mark_overlapping_turns(
    turns: Sequence[SpeakerTurnRegion],
) -> list[SpeakerTurnRegion]:
    """Return turns with ``is_overlap`` set when another speaker overlaps."""

    output: list[SpeakerTurnRegion] = []
    for index, turn in enumerate(turns):
        is_overlap = any(
            index != other_index
            and turn.speaker_turn_label != other.speaker_turn_label
            and _overlap_seconds(turn, other) > 0
            for other_index, other in enumerate(turns)
        )
        output.append(
            SpeakerTurnRegion(
                start_sec=turn.start_sec,
                end_sec=turn.end_sec,
                speaker_turn_label=turn.speaker_turn_label,
                confidence=turn.confidence,
                channel_index=turn.channel_index,
                is_overlap=is_overlap,
                source=turn.source,
            )
        )
    return output


def summarize_diarization_baseline(
    predicted_turns: Sequence[SpeakerTurnRegion],
    *,
    reference_turns: Sequence[SpeakerTurnRegion] | None = None,
    diarization_segment_count: int | None = None,
    vad_only_segment_count: int | None = None,
    speaker_attributed_wer: float | None = None,
    named_speaker_false_assignment_rate_before: float | None = None,
    named_speaker_false_assignment_rate_after: float | None = None,
    runtime_sec: float | None = None,
    memory_overhead_mb: float | None = None,
) -> DiarizationMetrics:
    """Summarize VAD-only versus diarization-assisted baseline signals."""

    predicted = tuple(mark_overlapping_turns(predicted_turns))
    reference = tuple(mark_overlapping_turns(reference_turns or ()))
    der = diarization_error_rate(predicted, reference) if reference else None
    jer = jaccard_error_rate(predicted, reference) if reference else None
    overlap_detection = (
        overlap_segment_detection_rate(predicted, reference) if reference else None
    )
    return DiarizationMetrics(
        predicted_turn_count=len(predicted),
        reference_turn_count=len(reference),
        predicted_speaker_count=len(_speaker_labels(predicted)),
        reference_speaker_count=len(_speaker_labels(reference)),
        diarization_segment_count=diarization_segment_count,
        vad_only_segment_count=vad_only_segment_count,
        der=der,
        jer=jer,
        speaker_attributed_wer=speaker_attributed_wer,
        named_speaker_false_assignment_rate_before=(
            named_speaker_false_assignment_rate_before
        ),
        named_speaker_false_assignment_rate_after=(
            named_speaker_false_assignment_rate_after
        ),
        overlap_segment_detection_rate=overlap_detection,
        overlap_predicted_turn_count=sum(1 for turn in predicted if turn.is_overlap),
        runtime_sec=runtime_sec,
        memory_overhead_mb=memory_overhead_mb,
    )


def diarization_error_rate(
    predicted_turns: Sequence[SpeakerTurnRegion],
    reference_turns: Sequence[SpeakerTurnRegion],
) -> float | None:
    """Compute a deterministic approximate DER over atomic time intervals."""

    predicted = tuple(predicted_turns)
    reference = tuple(reference_turns)
    reference_time = _active_speaker_time(reference)
    if reference_time <= 0:
        return None
    label_map = _greedy_label_map(predicted, reference)
    missed = 0.0
    false_alarm = 0.0
    confusion = 0.0
    for start_sec, end_sec in _atomic_intervals(predicted, reference):
        duration = end_sec - start_sec
        ref_labels = _active_labels(reference, start_sec, end_sec)
        pred_labels = _active_labels(predicted, start_sec, end_sec)
        mapped_pred = {
            label_map.get(label, label)
            for label in pred_labels
        }
        matched_count = len(ref_labels & mapped_pred)
        if not ref_labels and pred_labels:
            false_alarm += len(pred_labels) * duration
            continue
        if ref_labels and not pred_labels:
            missed += len(ref_labels) * duration
            continue
        if ref_labels and pred_labels:
            shared_capacity = min(len(ref_labels), len(pred_labels))
            confusion += max(0, shared_capacity - matched_count) * duration
            missed += max(0, len(ref_labels) - shared_capacity) * duration
            false_alarm += max(0, len(pred_labels) - shared_capacity) * duration
    return (missed + false_alarm + confusion) / reference_time


def jaccard_error_rate(
    predicted_turns: Sequence[SpeakerTurnRegion],
    reference_turns: Sequence[SpeakerTurnRegion],
) -> float | None:
    """Compute an approximate JER after anonymous-label mapping."""

    predicted = tuple(predicted_turns)
    reference = tuple(reference_turns)
    reference_labels = sorted(_speaker_labels(reference))
    if not reference_labels:
        return None
    label_map = _greedy_label_map(predicted, reference)
    inverse: dict[str, str] = {}
    for pred_label, ref_label in label_map.items():
        inverse.setdefault(ref_label, pred_label)

    errors: list[float] = []
    for ref_label in reference_labels:
        pred_label = inverse.get(ref_label)
        ref_intervals = _label_intervals(reference, ref_label)
        pred_intervals = _label_intervals(predicted, pred_label) if pred_label else []
        intersection = _interval_overlap_duration(ref_intervals, pred_intervals)
        union = _interval_union_duration([*ref_intervals, *pred_intervals])
        jaccard = intersection / union if union else 0.0
        errors.append(1.0 - jaccard)
    return sum(errors) / len(errors) if errors else None


def overlap_segment_detection_rate(
    predicted_turns: Sequence[SpeakerTurnRegion],
    reference_turns: Sequence[SpeakerTurnRegion],
) -> float | None:
    """Return reference-overlap duration covered by predicted overlap duration."""

    reference_overlap = _overlap_intervals(reference_turns)
    reference_duration = _interval_union_duration(reference_overlap)
    if reference_duration <= 0:
        return None
    predicted_overlap = _overlap_intervals(predicted_turns)
    return _interval_overlap_duration(reference_overlap, predicted_overlap) / reference_duration


def named_speaker_false_assignment_rate(
    predicted_labels: Sequence[str | None],
    reference_labels: Sequence[str | None],
    *,
    unknown_label: str = "Unknown",
) -> float | None:
    """Return false named-speaker rate for existing speaker-attribution outputs."""

    scored = 0
    false_named = 0
    for predicted, reference in zip(predicted_labels, reference_labels, strict=False):
        reference_text = _optional_string(reference)
        if not reference_text:
            continue
        scored += 1
        predicted_text = _optional_string(predicted)
        if (
            predicted_text
            and predicted_text != unknown_label
            and predicted_text != reference_text
        ):
            false_named += 1
    return false_named / scored if scored else None


def component_report_path(reports_root: Path, run_id: str) -> Path:
    """Return the required M17 diarization component report path."""

    return (
        reports_root
        / "component_reports"
        / "diarization"
        / f"diarization_baseline_{run_id}.md"
    )


def write_diarization_report(
    path: Path,
    *,
    run_id: str,
    backend_name: str,
    metrics: DiarizationMetrics | None,
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_checks: Sequence[str],
    pyannote_status: str,
    runner_contract: str,
    enabled_disabled_status: str,
    recommendation: str,
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the M17 optional diarization baseline report artifact."""

    lines = [
        "# Diarization Baseline Report",
        "",
        "## Milestone",
        "",
        "M17 - Optional Diarization and Overlap Baseline",
        "",
        f"- Run id: `{run_id}`",
        f"- Selected diarization backend: `{backend_name}`",
        f"- Pyannote status: {pyannote_status}",
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Summary",
        "",
        "M17 adds an optional diarization interface that returns anonymous speaker-turn regions.",
        "Diarization-assisted segmentation is used only when the helper is enabled and available.",
        "",
        "## Runner Contract Preservation",
        "",
        runner_contract,
        "",
        "## Commands",
        "",
        *[f"- `{command}`" for command in test_commands],
        "",
        "## Smoke Checks",
        "",
        *[f"- `{check}`" for check in smoke_checks],
        "",
        "## Diarization Metrics",
        "",
    ]
    if metrics is None:
        lines.append("Metrics were not produced because required comparison assets were unavailable.")
    else:
        lines.extend(metrics.to_markdown_rows())
    lines.extend(
        [
            "",
            "## Enabled Disabled Status",
            "",
            enabled_disabled_status,
            "",
            "## Recommendation",
            "",
            recommendation,
            "",
            "## Blockers",
            "",
        ]
    )
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- None known.")
    lines.extend(["", "## Incomplete", ""])
    if incomplete:
        lines.extend(f"- {item}" for item in incomplete)
    else:
        lines.append("- None known.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _diarization_component(config: object) -> object | None:
    components = getattr(config, "components", None)
    if isinstance(components, Mapping):
        return components.get("diarization")
    if isinstance(config, Mapping):
        raw_components = config.get("components")
        if isinstance(raw_components, Mapping):
            return raw_components.get("diarization")
        return config.get("diarization")
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
        raise ContractValidationError("diarization params must be a mapping")
    return value


def _validate_time_range(start_sec: float, end_sec: float, label: str) -> None:
    if not math.isfinite(float(start_sec)) or not math.isfinite(float(end_sec)):
        raise ContractValidationError(f"{label} times must be finite")
    if start_sec < 0:
        raise ContractValidationError(f"{label} start_sec must be >= 0")
    if end_sec <= start_sec:
        raise ContractValidationError(f"{label} end_sec must be > start_sec")


def _float_value(value: object, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc


def _optional_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bool_value(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ContractValidationError(f"{field_name} must be a boolean")


def _format_metric(value: object) -> str:
    if value is None:
        return "not_calculable"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _speaker_labels(turns: Sequence[SpeakerTurnRegion]) -> set[str]:
    return {turn.speaker_turn_label for turn in turns}


def _overlap_seconds(left: SpeakerTurnRegion, right: SpeakerTurnRegion) -> float:
    return max(0.0, min(left.end_sec, right.end_sec) - max(left.start_sec, right.start_sec))


def _active_speaker_time(turns: Sequence[SpeakerTurnRegion]) -> float:
    return sum(max(0.0, turn.end_sec - turn.start_sec) for turn in turns)


def _atomic_intervals(
    predicted: Sequence[SpeakerTurnRegion],
    reference: Sequence[SpeakerTurnRegion],
) -> list[tuple[float, float]]:
    boundaries = sorted(
        {
            boundary
            for turn in (*predicted, *reference)
            for boundary in (turn.start_sec, turn.end_sec)
        }
    )
    return [
        (start_sec, end_sec)
        for start_sec, end_sec in zip(boundaries, boundaries[1:], strict=False)
        if end_sec > start_sec
    ]


def _active_labels(
    turns: Sequence[SpeakerTurnRegion],
    start_sec: float,
    end_sec: float,
) -> set[str]:
    midpoint = (start_sec + end_sec) / 2.0
    return {
        turn.speaker_turn_label
        for turn in turns
        if turn.start_sec <= midpoint < turn.end_sec
    }


def _greedy_label_map(
    predicted: Sequence[SpeakerTurnRegion],
    reference: Sequence[SpeakerTurnRegion],
) -> dict[str, str]:
    overlaps: list[tuple[float, str, str]] = []
    for pred_label in _speaker_labels(predicted):
        pred_intervals = _label_intervals(predicted, pred_label)
        for ref_label in _speaker_labels(reference):
            ref_intervals = _label_intervals(reference, ref_label)
            overlaps.append(
                (
                    _interval_overlap_duration(pred_intervals, ref_intervals),
                    pred_label,
                    ref_label,
                )
            )
    used_pred: set[str] = set()
    used_ref: set[str] = set()
    label_map: dict[str, str] = {}
    for overlap, pred_label, ref_label in sorted(overlaps, reverse=True):
        if overlap <= 0 or pred_label in used_pred or ref_label in used_ref:
            continue
        label_map[pred_label] = ref_label
        used_pred.add(pred_label)
        used_ref.add(ref_label)
    return label_map


def _label_intervals(
    turns: Sequence[SpeakerTurnRegion],
    label: str | None,
) -> list[tuple[float, float]]:
    if label is None:
        return []
    return [
        (turn.start_sec, turn.end_sec)
        for turn in turns
        if turn.speaker_turn_label == label and turn.end_sec > turn.start_sec
    ]


def _overlap_intervals(
    turns: Sequence[SpeakerTurnRegion],
) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    for index, turn in enumerate(turns):
        for other_index, other in enumerate(turns):
            if index >= other_index or turn.speaker_turn_label == other.speaker_turn_label:
                continue
            start_sec = max(turn.start_sec, other.start_sec)
            end_sec = min(turn.end_sec, other.end_sec)
            if end_sec > start_sec:
                intervals.append((start_sec, end_sec))
    return _merge_intervals(intervals)


def _interval_overlap_duration(
    left_intervals: Sequence[tuple[float, float]],
    right_intervals: Sequence[tuple[float, float]],
) -> float:
    total = 0.0
    for left_start, left_end in _merge_intervals(left_intervals):
        for right_start, right_end in _merge_intervals(right_intervals):
            total += max(0.0, min(left_end, right_end) - max(left_start, right_start))
    return total


def _interval_union_duration(intervals: Sequence[tuple[float, float]]) -> float:
    return sum(end_sec - start_sec for start_sec, end_sec in _merge_intervals(intervals))


def _merge_intervals(intervals: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start_sec, end_sec in sorted(intervals):
        if end_sec <= start_sec:
            continue
        if not merged or start_sec > merged[-1][1]:
            merged.append((start_sec, end_sec))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], end_sec))
    return merged
