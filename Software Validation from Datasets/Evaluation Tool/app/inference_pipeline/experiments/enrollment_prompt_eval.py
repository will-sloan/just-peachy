"""Enrollment prompt comparison experiment for speaker recognition."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from app.inference_pipeline.enrollment.schema import (
    ENROLLMENT_SCHEMA_VERSION,
    EnrollmentDatabase,
    EnrollmentExemplar,
    EnrollmentSpeaker,
)
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.speaker_embedding import normalize_vector
from app.inference_pipeline.speaker_matching import CosineThresholdSpeakerMatcher
from app.inference_pipeline.speaker_matching.thresholds import (
    DEFAULT_FIXED_FAR_TARGETS,
    CalibrationSample,
    ThresholdCalibrationResult,
    calibrate_thresholds,
)
from app.inference_pipeline.typing import JsonObject, JsonValue
from app.utils.json_utils import read_json, read_jsonl


TOOL_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPT_SETS_PATH = TOOL_ROOT / "app" / "inference_pipeline" / "enrollment" / "prompt_sets.yaml"
DEFAULT_SWEEP_CONFIG_PATH = TOOL_ROOT / "configs" / "sweeps" / "enrollment_prompts.yaml"
DEFAULT_SYNTHETIC_SAMPLES_PATH = TOOL_ROOT / "artifacts" / "enrollment_prompt_eval" / "synthetic_prompt_samples.jsonl"


@dataclass(frozen=True)
class PromptItem:
    """One phrase or text block inside a prompt set."""

    prompt_id: str
    text: str

    def __post_init__(self) -> None:
        _validate_required_string("prompt_id", self.prompt_id)
        _validate_required_string("text", self.text)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "PromptItem":
        return cls(
            prompt_id=_required_string(mapping, "prompt_id"),
            text=_required_string(mapping, "text"),
        )

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class PromptSet:
    """Candidate enrollment prompt strategy."""

    prompt_set_id: str
    title: str
    strategy: str
    prompts: tuple[PromptItem, ...]
    target_duration_sec: float
    minimum_duration_sec: float
    notes: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        _validate_required_string("prompt_set_id", self.prompt_set_id)
        _validate_required_string("title", self.title)
        _validate_required_string("strategy", self.strategy)
        prompts = tuple(self.prompts)
        if not prompts:
            raise ContractValidationError("prompt set must contain at least one prompt")
        if self.target_duration_sec <= 0:
            raise ContractValidationError("target_duration_sec must be > 0")
        if self.minimum_duration_sec <= 0:
            raise ContractValidationError("minimum_duration_sec must be > 0")
        object.__setattr__(self, "prompts", prompts)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "PromptSet":
        raw_prompts = mapping.get("prompts") or ()
        if not isinstance(raw_prompts, Sequence) or isinstance(raw_prompts, str | bytes | bytearray):
            raise ContractValidationError("prompt set prompts must be a list")
        return cls(
            prompt_set_id=_required_string(mapping, "prompt_set_id"),
            title=_required_string(mapping, "title"),
            strategy=_required_string(mapping, "strategy"),
            prompts=tuple(PromptItem.from_mapping(_mapping_value(item, "prompt")) for item in raw_prompts),
            target_duration_sec=_float_value(mapping.get("target_duration_sec"), "target_duration_sec"),
            minimum_duration_sec=_float_value(mapping.get("minimum_duration_sec"), "minimum_duration_sec"),
            notes=_optional_string(mapping.get("notes")),
            enabled=_optional_bool(mapping.get("enabled"), default=True),
        )

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class EnrollmentPromptSample:
    """One enrollment prompt evaluation sample with embedding metadata."""

    sample_id: str
    speaker_id: str
    display_name: str
    prompt_id: str
    prompt_set_id: str
    recording_condition: str
    embedding_model: str
    duration_sec: float
    embedding: tuple[float, ...] | None = None
    embedding_path: str | None = None
    audio_path: str | None = None
    metadata: JsonObject | None = None

    def __post_init__(self) -> None:
        _validate_required_string("sample_id", self.sample_id)
        _validate_required_string("speaker_id", self.speaker_id)
        _validate_required_string("display_name", self.display_name)
        _validate_required_string("prompt_id", self.prompt_id)
        _validate_required_string("prompt_set_id", self.prompt_set_id)
        _validate_required_string("recording_condition", self.recording_condition)
        _validate_required_string("embedding_model", self.embedding_model)
        if self.duration_sec <= 0:
            raise ContractValidationError("duration_sec must be > 0")
        embedding = None if self.embedding is None else tuple(float(value) for value in self.embedding)
        if embedding is None and self.embedding_path is None:
            raise ContractValidationError("sample must include embedding or embedding_path")
        if embedding is not None:
            if not embedding:
                raise ContractValidationError("embedding must be non-empty")
            if any(not math.isfinite(value) for value in embedding):
                raise ContractValidationError("embedding values must be finite")
        object.__setattr__(self, "embedding", embedding)
        object.__setattr__(self, "embedding_path", _optional_string(self.embedding_path))
        object.__setattr__(self, "audio_path", _optional_string(self.audio_path))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, object],
        *,
        base_dir: Path | None = None,
    ) -> "EnrollmentPromptSample":
        embedding_value = mapping.get("embedding") or mapping.get("vector")
        embedding_path = _optional_string(mapping.get("embedding_path"))
        embedding = (
            _sequence_float_tuple(embedding_value, "embedding")
            if embedding_value is not None
            else _load_embedding_path(embedding_path, base_dir=base_dir)
        )
        metadata = mapping.get("metadata")
        return cls(
            sample_id=_required_string(mapping, "sample_id"),
            speaker_id=_required_string(mapping, "speaker_id"),
            display_name=_required_string(mapping, "display_name"),
            prompt_id=_required_string(mapping, "prompt_id"),
            prompt_set_id=_required_string(mapping, "prompt_set_id"),
            recording_condition=_required_string(mapping, "recording_condition"),
            embedding_model=_required_string(mapping, "embedding_model"),
            duration_sec=_float_value(mapping.get("duration_sec"), "duration_sec"),
            embedding=embedding,
            embedding_path=embedding_path,
            audio_path=_optional_string(mapping.get("audio_path")),
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
        )

    def normalized_embedding(self) -> tuple[float, ...]:
        if self.embedding is None:
            raise ContractValidationError(f"sample {self.sample_id!r} has no loaded embedding")
        return normalize_vector(self.embedding)

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class PromptSetMetrics:
    """Metrics for one enrollment prompt strategy."""

    prompt_set_id: str
    title: str
    strategy: str
    prompt_ids: tuple[str, ...]
    enrollment_sample_count: int
    test_sample_count: int
    cross_prompt_test_count: int
    natural_speech_test_count: int
    known_speaker_accuracy: float | None
    false_known_rate: float | None
    unknown_rejection_rate: float | None
    equal_error_rate: float | None
    equal_error_threshold: float | None
    tar_at_far: tuple[tuple[float, float | None], ...]
    score_margin_mean: float | None
    score_margin_min: float | None
    score_margin_max: float | None
    stability_mean: float | None
    stability_min: float | None
    total_enrollment_duration_sec: float
    mean_enrollment_duration_per_speaker_sec: float | None
    min_enrollment_duration_per_speaker_sec: float | None
    recommended_threshold: float | None

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class EnrollmentPromptEvalResult:
    """Complete M12 experiment result."""

    run_id: str
    metrics: tuple[PromptSetMetrics, ...]
    recommended_prompt_set_id: str | None
    recommended_prompt_title: str | None
    recommended_min_duration_sec: float | None
    assumptions: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    incomplete: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "assumptions", tuple(str(item) for item in self.assumptions))
        object.__setattr__(self, "blockers", tuple(str(item) for item in self.blockers))
        object.__setattr__(self, "incomplete", tuple(str(item) for item in self.incomplete))

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


def prompt_comparison_report_path(reports_root: Path, run_id: str) -> Path:
    return (
        reports_root
        / "component_reports"
        / "enrollment_prompts"
        / f"prompt_comparison_{run_id}.md"
    )


def load_prompt_sets(path: Path | str = DEFAULT_PROMPT_SETS_PATH) -> tuple[PromptSet, ...]:
    data = _load_yaml_mapping(Path(path))
    raw_sets = data.get("prompt_sets") or ()
    if not isinstance(raw_sets, Sequence) or isinstance(raw_sets, str | bytes | bytearray):
        raise ContractValidationError("prompt_sets must be a list")
    prompt_sets = tuple(PromptSet.from_mapping(_mapping_value(item, "prompt_set")) for item in raw_sets)
    prompt_ids = [prompt_set.prompt_set_id for prompt_set in prompt_sets]
    if len(prompt_ids) != len(set(prompt_ids)):
        raise ContractValidationError("prompt_set_id values must be unique")
    return prompt_sets


def load_prompt_eval_config(path: Path | str = DEFAULT_SWEEP_CONFIG_PATH) -> JsonObject:
    return dict(_load_yaml_mapping(Path(path)))


def load_prompt_samples(path: Path | str) -> tuple[EnrollmentPromptSample, ...]:
    sample_path = Path(path)
    return tuple(
        EnrollmentPromptSample.from_mapping(row, base_dir=sample_path.parent)
        for row in read_jsonl(sample_path)
    )


def evaluate_enrollment_prompts(
    *,
    run_id: str,
    prompt_sets: Sequence[PromptSet],
    samples: Sequence[EnrollmentPromptSample],
    thresholds: Sequence[float],
    min_margin: float = 0.05,
    scoring_mode: str = "centroid",
    unknown_label: str = "Unknown",
    conservative_max_false_known_rate: float = 0.0,
    fixed_far_targets: Sequence[float] = DEFAULT_FIXED_FAR_TARGETS,
    assumptions: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> EnrollmentPromptEvalResult:
    """Compare prompt strategies by enrolling on each prompt set and testing others."""

    sample_rows = tuple(samples)
    candidate_sets = tuple(prompt_set for prompt_set in prompt_sets if prompt_set.enabled)
    if len(candidate_sets) < 3:
        raise ContractValidationError("M12 requires at least three enabled prompt strategies")
    if not sample_rows:
        raise ContractValidationError("enrollment prompt evaluation requires samples")

    metrics = tuple(
        _evaluate_prompt_set(
            prompt_set,
            samples=sample_rows,
            thresholds=thresholds,
            min_margin=min_margin,
            scoring_mode=scoring_mode,
            unknown_label=unknown_label,
            conservative_max_false_known_rate=conservative_max_false_known_rate,
            fixed_far_targets=fixed_far_targets,
        )
        for prompt_set in candidate_sets
    )
    ranked = rank_prompt_sets(metrics)
    recommended = ranked[0] if ranked else None
    return EnrollmentPromptEvalResult(
        run_id=run_id,
        metrics=ranked,
        recommended_prompt_set_id=recommended.prompt_set_id if recommended is not None else None,
        recommended_prompt_title=recommended.title if recommended is not None else None,
        recommended_min_duration_sec=(
            recommended.mean_enrollment_duration_per_speaker_sec
            if recommended is not None
            else None
        ),
        assumptions=tuple(assumptions),
        blockers=(),
        incomplete=tuple(incomplete),
    )


def run_enrollment_prompt_eval(
    *,
    run_id: str,
    prompt_sets_path: Path,
    samples_jsonl: Path,
    sweep_config_path: Path | None = None,
    report_path: Path | None = None,
    test_commands: Sequence[str] = (),
    smoke_commands: Sequence[str] = (),
) -> tuple[EnrollmentPromptEvalResult, Path]:
    """Load config and inputs, run the experiment, and write the report."""

    config = load_prompt_eval_config(sweep_config_path or DEFAULT_SWEEP_CONFIG_PATH)
    matcher_config = _mapping_value(config.get("matcher") or {}, "matcher")
    prompt_sets = load_prompt_sets(prompt_sets_path)
    samples = load_prompt_samples(samples_jsonl)
    thresholds = _thresholds_from_config(matcher_config)
    result = evaluate_enrollment_prompts(
        run_id=run_id,
        prompt_sets=prompt_sets,
        samples=samples,
        thresholds=thresholds,
        min_margin=_float_value(matcher_config.get("min_margin", 0.05), "min_margin"),
        scoring_mode=str(matcher_config.get("scoring_mode") or "centroid"),
        unknown_label=str(matcher_config.get("unknown_label") or "Unknown"),
        conservative_max_false_known_rate=_float_value(
            matcher_config.get("conservative_max_false_known_rate", 0.0),
            "conservative_max_false_known_rate",
        ),
        fixed_far_targets=tuple(
            float(value)
            for value in matcher_config.get("fixed_far_targets", DEFAULT_FIXED_FAR_TARGETS)
        ),
        assumptions=[
            f"Prompt sets loaded from {prompt_sets_path}",
            f"Samples loaded from {samples_jsonl}",
            "Synthetic fixtures validate experiment behavior but not product speaker quality.",
        ],
        incomplete=tuple(str(item) for item in config.get("incomplete", ())),
    )
    output_path = report_path or prompt_comparison_report_path(TOOL_ROOT / "reports", run_id)
    write_prompt_comparison_report(
        output_path,
        result,
        prompt_sets=prompt_sets,
        samples=samples,
        files_changed=[
            "app/inference_pipeline/enrollment/prompt_sets.yaml",
            "app/inference_pipeline/experiments/__init__.py",
            "app/inference_pipeline/experiments/enrollment_prompt_eval.py",
            "scripts/run_enrollment_prompt_eval.py",
            "configs/sweeps/enrollment_prompts.yaml",
            "artifacts/enrollment_prompt_eval/README.md",
            "artifacts/enrollment_prompt_eval/synthetic_prompt_samples.jsonl",
            "tests/inference_pipeline/test_enrollment_prompt_eval.py",
            "tests/run_all_tests.py",
            "tests/run_smoke_tests.py",
        ],
        test_commands=test_commands,
        smoke_commands=smoke_commands,
        runner_contract=(
            "Enrollment prompt evaluation reads prompt/sample artifacts and embeddings only. "
            "It does not modify app/model_runner/external_stub.py, record['inference_audio_path'], "
            "predictions/utterances.jsonl, or scoring identity fields."
        ),
    )
    return result, output_path


def rank_prompt_sets(metrics: Sequence[PromptSetMetrics]) -> tuple[PromptSetMetrics, ...]:
    return tuple(
        sorted(
            metrics,
            key=lambda item: (
                _none_high(item.false_known_rate),
                -_none_low(item.known_speaker_accuracy),
                _none_high(item.equal_error_rate),
                _none_high(item.mean_enrollment_duration_per_speaker_sec),
                -_none_low(item.score_margin_mean),
                -_none_low(item.stability_mean),
            ),
        )
    )


def write_prompt_comparison_report(
    path: Path,
    result: EnrollmentPromptEvalResult,
    *,
    prompt_sets: Sequence[PromptSet],
    samples: Sequence[EnrollmentPromptSample],
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_commands: Sequence[str],
    runner_contract: str,
) -> Path:
    """Write the required M12 prompt recommendation report."""

    lines = [
        "# Enrollment Prompt Comparison Report",
        "",
        "## Milestone",
        "",
        "M12 - Enrollment Prompt Testing Framework",
        "",
        f"- Run id: `{result.run_id}`",
        f"- Prompt strategies compared: `{len(prompt_sets)}`",
        f"- Samples evaluated: `{len(samples)}`",
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Prompt Strategies",
        "",
    ]
    for prompt_set in prompt_sets:
        prompt_ids = ", ".join(prompt.prompt_id for prompt in prompt_set.prompts)
        lines.append(
            f"- `{prompt_set.prompt_set_id}` ({prompt_set.strategy}): "
            f"{prompt_set.title}; prompt_ids={prompt_ids}; "
            f"target={prompt_set.target_duration_sec:.1f}s"
        )
    lines.extend(
        [
            "",
            "## Experiment Inputs And Assumptions",
            "",
            *[f"- {item}" for item in result.assumptions],
            "",
            "## Runner Contract Preservation",
            "",
            runner_contract,
            "",
            "## Commands",
            "",
            *[f"- `{command}`" for command in test_commands],
            *[f"- `{command}`" for command in smoke_commands],
            "",
            "## Recommendation",
            "",
        ]
    )
    if result.recommended_prompt_set_id is None:
        lines.append("- No prompt recommendation was available.")
    else:
        lines.extend(
            [
                f"- Recommended prompt set: `{result.recommended_prompt_set_id}`",
                f"- Recommended prompt title: `{result.recommended_prompt_title}`",
                (
                    "- Recommended minimum enrollment duration: "
                    f"`{_format_metric(result.recommended_min_duration_sec)}s`"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Metrics By Prompt Set",
            "",
            "| rank | prompt set | known accuracy | false-known rate | EER | margin mean | stability mean | per-speaker duration sec | threshold |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for rank, metrics in enumerate(result.metrics, start=1):
        lines.append(
            "| "
            f"{rank} | "
            f"{metrics.prompt_set_id} | "
            f"{_format_metric(metrics.known_speaker_accuracy)} | "
            f"{_format_metric(metrics.false_known_rate)} | "
            f"{_format_metric(metrics.equal_error_rate)} | "
            f"{_format_metric(metrics.score_margin_mean)} | "
            f"{_format_metric(metrics.stability_mean)} | "
            f"{_format_metric(metrics.mean_enrollment_duration_per_speaker_sec)} | "
            f"{_format_metric(metrics.recommended_threshold)} |"
        )
    lines.extend(["", "## Cross-Prompt Generalization", ""])
    lines.extend(
        (
            f"- `{metrics.prompt_set_id}`: known_accuracy="
            f"`{_format_metric(metrics.known_speaker_accuracy)}`, "
            f"cross_prompt_tests=`{metrics.cross_prompt_test_count}`, "
            f"natural_speech_tests=`{metrics.natural_speech_test_count}`"
        )
        for metrics in result.metrics
    )
    lines.extend(["", "## Stability Across Repeated Recordings", ""])
    lines.extend(
        (
            f"- `{metrics.prompt_set_id}`: stability_mean="
            f"`{_format_metric(metrics.stability_mean)}`, "
            f"stability_min=`{_format_metric(metrics.stability_min)}`"
        )
        for metrics in result.metrics
    )
    lines.extend(["", "## EER And TAR@FAR", ""])
    for metrics in result.metrics:
        tar_text = ", ".join(
            f"FAR {far:.2f}: {_format_metric(tar)}"
            for far, tar in metrics.tar_at_far
        )
        lines.append(
            f"- `{metrics.prompt_set_id}`: EER=`{_format_metric(metrics.equal_error_rate)}`, "
            f"TAR@FAR={tar_text or 'n/a'}"
        )
    lines.extend(["", "## False Known-Speaker Rate By Prompt Set", ""])
    lines.extend(
        f"- `{metrics.prompt_set_id}`: `{_format_metric(metrics.false_known_rate)}`"
        for metrics in result.metrics
    )
    lines.extend(["", "## Duration Vs Performance", ""])
    lines.extend(
        (
            f"- `{metrics.prompt_set_id}`: per-speaker duration="
            f"`{_format_metric(metrics.mean_enrollment_duration_per_speaker_sec)}s`, "
            f"known_accuracy=`{_format_metric(metrics.known_speaker_accuracy)}`, "
            f"false_known_rate=`{_format_metric(metrics.false_known_rate)}`"
        )
        for metrics in result.metrics
    )
    lines.extend(["", "## Blockers", ""])
    if result.blockers:
        lines.extend(f"- {item}" for item in result.blockers)
    else:
        lines.append("- None known.")
    lines.extend(["", "## Incomplete", ""])
    if result.incomplete:
        lines.extend(f"- {item}" for item in result.incomplete)
    else:
        lines.append("- None known.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _evaluate_prompt_set(
    prompt_set: PromptSet,
    *,
    samples: Sequence[EnrollmentPromptSample],
    thresholds: Sequence[float],
    min_margin: float,
    scoring_mode: str,
    unknown_label: str,
    conservative_max_false_known_rate: float,
    fixed_far_targets: Sequence[float],
) -> PromptSetMetrics:
    enrollment_samples = tuple(
        sample
        for sample in samples
        if sample.prompt_set_id == prompt_set.prompt_set_id
    )
    if not enrollment_samples:
        raise ContractValidationError(f"no enrollment samples for prompt set {prompt_set.prompt_set_id!r}")
    enrollment_db = enrollment_database_from_samples(enrollment_samples)
    enrolled_speaker_ids = {sample.speaker_id for sample in enrollment_samples}
    test_samples = tuple(
        sample
        for sample in samples
        if sample.prompt_set_id != prompt_set.prompt_set_id
    )
    calibration_samples = tuple(_calibration_sample(sample) for sample in test_samples)
    calibration = calibrate_thresholds(
        calibration_samples,
        enrollment_db,
        run_id=f"m12_{prompt_set.prompt_set_id}",
        thresholds=thresholds,
        min_margin=min_margin,
        scoring_mode=scoring_mode,
        runtime_model_id=_single_embedding_model(enrollment_samples),
        unknown_label=unknown_label,
        conservative_max_false_known_rate=conservative_max_false_known_rate,
        fixed_far_targets=fixed_far_targets,
    )
    threshold = calibration.recommended_threshold
    matcher = CosineThresholdSpeakerMatcher(
        threshold=threshold if threshold is not None else 1.0,
        min_margin=min_margin,
        unknown_label=unknown_label,
        scoring_mode=scoring_mode,
        runtime_model_id=_single_embedding_model(enrollment_samples),
    )
    decisions = tuple(
        matcher.match(
            {
                "embedding_id": sample.sample_id,
                "vector": sample.normalized_embedding(),
                "model_id": sample.embedding_model,
            },
            enrollment_db,
        )
        for sample in test_samples
    )
    known_tests = tuple(sample for sample in test_samples if sample.speaker_id in enrolled_speaker_ids)
    unknown_tests = tuple(sample for sample in test_samples if sample.speaker_id not in enrolled_speaker_ids)
    known_correct = sum(
        1
        for sample, decision in zip(test_samples, decisions, strict=True)
        if sample.speaker_id in enrolled_speaker_ids
        and decision.speaker_label == sample.display_name
    )
    false_known_count = sum(
        1
        for sample, decision in zip(test_samples, decisions, strict=True)
        if decision.speaker_label != unknown_label
        and decision.speaker_label != sample.display_name
    )
    unknown_rejections = sum(
        1
        for sample, decision in zip(test_samples, decisions, strict=True)
        if sample.speaker_id not in enrolled_speaker_ids
        and decision.speaker_label == unknown_label
    )
    duration_by_speaker = _duration_by_speaker(enrollment_samples)
    stability_scores = _stability_scores(enrollment_samples)
    recommended_metrics = calibration.recommended_metrics
    return PromptSetMetrics(
        prompt_set_id=prompt_set.prompt_set_id,
        title=prompt_set.title,
        strategy=prompt_set.strategy,
        prompt_ids=tuple(prompt.prompt_id for prompt in prompt_set.prompts),
        enrollment_sample_count=len(enrollment_samples),
        test_sample_count=len(test_samples),
        cross_prompt_test_count=len(known_tests),
        natural_speech_test_count=sum(1 for sample in test_samples if sample.prompt_set_id == "natural_speech"),
        known_speaker_accuracy=_safe_rate(known_correct, len(known_tests)),
        false_known_rate=_safe_rate(false_known_count, len(test_samples)),
        unknown_rejection_rate=_safe_rate(unknown_rejections, len(unknown_tests)),
        equal_error_rate=calibration.verification.equal_error_rate,
        equal_error_threshold=calibration.verification.equal_error_threshold,
        tar_at_far=calibration.verification.tar_at_far,
        score_margin_mean=(
            recommended_metrics.margin_mean
            if recommended_metrics is not None
            else None
        ),
        score_margin_min=(
            recommended_metrics.margin_min
            if recommended_metrics is not None
            else None
        ),
        score_margin_max=(
            recommended_metrics.margin_max
            if recommended_metrics is not None
            else None
        ),
        stability_mean=_mean(stability_scores),
        stability_min=min(stability_scores) if stability_scores else None,
        total_enrollment_duration_sec=sum(duration_by_speaker.values()),
        mean_enrollment_duration_per_speaker_sec=_mean(tuple(duration_by_speaker.values())),
        min_enrollment_duration_per_speaker_sec=(
            min(duration_by_speaker.values()) if duration_by_speaker else None
        ),
        recommended_threshold=threshold,
    )


def enrollment_database_from_samples(
    samples: Sequence[EnrollmentPromptSample],
) -> EnrollmentDatabase:
    speakers: list[EnrollmentSpeaker] = []
    for speaker_id in sorted({sample.speaker_id for sample in samples}):
        speaker_samples = tuple(sample for sample in samples if sample.speaker_id == speaker_id)
        display_names = {sample.display_name for sample in speaker_samples}
        if len(display_names) != 1:
            raise ContractValidationError(f"speaker_id {speaker_id!r} has multiple display_name values")
        exemplars = tuple(
            EnrollmentExemplar(
                speaker_id=sample.speaker_id,
                display_name=sample.display_name,
                prompt_id=sample.prompt_id,
                audio_path=sample.audio_path or sample.embedding_path or f"{sample.sample_id}.wav",
                embedding=sample.normalized_embedding(),
                model_id=sample.embedding_model,
                created_at="2026-05-28T00:00:00Z",
                duration_sec=sample.duration_sec,
                embedding_id=sample.sample_id,
                metadata={
                    "prompt_set_id": sample.prompt_set_id,
                    "recording_condition": sample.recording_condition,
                    "sample_id": sample.sample_id,
                },
            )
            for sample in speaker_samples
        )
        speakers.append(
            EnrollmentSpeaker(
                speaker_id=speaker_id,
                display_name=speaker_samples[0].display_name,
                exemplars=exemplars,
            )
        )
    return EnrollmentDatabase(
        schema_version=ENROLLMENT_SCHEMA_VERSION,
        speakers=tuple(speakers),
        created_at="2026-05-28T00:00:00Z",
        updated_at="2026-05-28T00:00:00Z",
        notes="M12 enrollment prompt evaluation DB",
    )


def _calibration_sample(sample: EnrollmentPromptSample) -> CalibrationSample:
    return CalibrationSample(
        sample_id=sample.sample_id,
        true_label=sample.display_name,
        embedding=sample.normalized_embedding(),
        model_id=sample.embedding_model,
    )


def _stability_scores(samples: Sequence[EnrollmentPromptSample]) -> tuple[float, ...]:
    scores: list[float] = []
    for speaker_id in sorted({sample.speaker_id for sample in samples}):
        vectors = [
            sample.normalized_embedding()
            for sample in samples
            if sample.speaker_id == speaker_id
        ]
        for left_index, left in enumerate(vectors):
            for right in vectors[left_index + 1 :]:
                scores.append(_cosine(left, right))
    return tuple(scores)


def _duration_by_speaker(samples: Sequence[EnrollmentPromptSample]) -> dict[str, float]:
    durations: dict[str, float] = {}
    for sample in samples:
        durations[sample.speaker_id] = durations.get(sample.speaker_id, 0.0) + sample.duration_sec
    return durations


def _single_embedding_model(samples: Sequence[EnrollmentPromptSample]) -> str | None:
    models = {sample.embedding_model for sample in samples}
    return next(iter(models)) if len(models) == 1 else None


def _thresholds_from_config(mapping: Mapping[str, object]) -> tuple[float, ...]:
    raw = mapping.get("thresholds") or ()
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes | bytearray):
        raise ContractValidationError("matcher.thresholds must be a list")
    values = tuple(float(value) for value in raw)
    if not values:
        raise ContractValidationError("matcher.thresholds must not be empty")
    return values


def _load_embedding_path(
    embedding_path: str | None,
    *,
    base_dir: Path | None,
) -> tuple[float, ...] | None:
    if embedding_path is None:
        return None
    path = Path(embedding_path)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    data = read_json(path)
    if isinstance(data, Mapping):
        value = data.get("embedding") or data.get("vector")
    else:
        value = data
    return _sequence_float_tuple(value, "embedding_path")


def _load_yaml_mapping(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return _mapping_value(data, str(path))


def _mapping_value(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field_name} must be a mapping")
    return value


def _required_string(mapping: Mapping[str, object], field_name: str) -> str:
    value = mapping.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
    return value


def _validate_required_string(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _float_value(value: object, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc


def _sequence_float_tuple(value: object, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ContractValidationError(f"{field_name} must be a sequence")
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must contain only numbers") from exc


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _none_high(value: float | None) -> float:
    return value if value is not None else float("inf")


def _none_low(value: float | None) -> float:
    return value if value is not None else float("-inf")


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _dataclass_jsonable(value: object) -> JsonObject:
    return {
        field.name: _jsonable(getattr(value, field.name))
        for field in fields(value)
    }


def _jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _dataclass_jsonable(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    return str(value)
