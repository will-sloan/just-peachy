"""Threshold calibration helpers for speaker matching."""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


TOOL_ROOT = Path(__file__).resolve().parents[3]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.enrollment import load_enrollment_db
from app.inference_pipeline.enrollment.schema import EnrollmentDatabase
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.speaker_matching.base import (
    UNKNOWN_LABEL,
    SpeakerDecision,
)
from app.inference_pipeline.speaker_matching.cosine_matcher import (
    CosineThresholdSpeakerMatcher,
)
from app.utils.json_utils import read_jsonl


DEFAULT_FIXED_FAR_TARGETS = (0.01, 0.05, 0.10)


@dataclass(frozen=True)
class CalibrationSample:
    """One labeled query embedding for threshold calibration."""

    sample_id: str
    true_label: str
    embedding: tuple[float, ...]
    model_id: str | None = None


@dataclass(frozen=True)
class ThresholdMetrics:
    """Open-set speaker matching metrics for one threshold."""

    threshold: float
    sample_count: int
    known_sample_count: int
    unknown_sample_count: int
    known_speaker_accuracy: float | None
    false_known_rate: float | None
    unknown_rate: float | None
    unknown_rejection_rate: float | None
    false_known_count: int
    unknown_count: int
    accepted_count: int
    margin_mean: float | None
    margin_min: float | None
    margin_max: float | None


@dataclass(frozen=True)
class VerificationMetrics:
    """Verification-style metrics from query-vs-speaker score pairs."""

    positive_pair_count: int
    negative_pair_count: int
    equal_error_rate: float | None
    equal_error_threshold: float | None
    tar_at_far: tuple[tuple[float, float | None], ...]


@dataclass(frozen=True)
class ThresholdCalibrationResult:
    """Complete threshold sweep result."""

    run_id: str
    metrics: tuple[ThresholdMetrics, ...]
    recommended_threshold: float | None
    recommended_metrics: ThresholdMetrics | None
    verification: VerificationMetrics
    fixed_far_targets: tuple[float, ...]
    conservative_max_false_known_rate: float
    min_margin: float
    scoring_mode: str
    unknown_label: str


def threshold_calibration_report_path(reports_root: Path, run_id: str) -> Path:
    """Return the required M11 threshold calibration report path."""

    return (
        reports_root
        / "component_reports"
        / "speaker_matching"
        / f"threshold_calibration_{run_id}.md"
    )


def load_calibration_samples(path: Path) -> tuple[CalibrationSample, ...]:
    """Load calibration samples from JSONL rows with embeddings and labels."""

    samples: list[CalibrationSample] = []
    for index, row in enumerate(read_jsonl(path), start=1):
        label = row.get("true_label") or row.get("speaker_label") or row.get("label")
        vector = row.get("embedding") or row.get("vector")
        if not label:
            raise ContractValidationError(f"calibration sample {index} missing label")
        if not isinstance(vector, Sequence) or isinstance(vector, str | bytes | bytearray):
            raise ContractValidationError(f"calibration sample {index} missing embedding vector")
        sample_id = row.get("sample_id") or row.get("embedding_id") or row.get("utt_id") or f"sample-{index}"
        samples.append(
            CalibrationSample(
                sample_id=str(sample_id),
                true_label=str(label),
                embedding=tuple(float(value) for value in vector),
                model_id=_optional_string(row.get("model_id") or row.get("model_name")),
            )
        )
    return tuple(samples)


def default_threshold_grid(
    *,
    threshold_min: float = 0.0,
    threshold_max: float = 1.0,
    threshold_step: float = 0.05,
) -> tuple[float, ...]:
    """Return an inclusive threshold sweep grid."""

    if threshold_step <= 0:
        raise ContractValidationError("threshold_step must be > 0")
    if threshold_max < threshold_min:
        raise ContractValidationError("threshold_max must be >= threshold_min")
    values: list[float] = []
    current = float(threshold_min)
    while current <= threshold_max + threshold_step / 10.0:
        values.append(round(current, 6))
        current += threshold_step
    return tuple(values)


def calibrate_thresholds(
    samples: Sequence[CalibrationSample],
    enrollment_db: EnrollmentDatabase,
    *,
    run_id: str,
    thresholds: Sequence[float] | None = None,
    min_margin: float = 0.05,
    scoring_mode: str = "centroid",
    runtime_model_id: str | None = None,
    unknown_label: str = UNKNOWN_LABEL,
    conservative_max_false_known_rate: float = 0.0,
    fixed_far_targets: Sequence[float] = DEFAULT_FIXED_FAR_TARGETS,
) -> ThresholdCalibrationResult:
    """Sweep thresholds and recommend a conservative operating point."""

    sample_rows = tuple(samples)
    if not sample_rows:
        raise ContractValidationError("threshold calibration requires at least one sample")
    threshold_values = tuple(thresholds or default_threshold_grid())
    known_labels = {speaker.display_name for speaker in enrollment_db.speakers}

    metrics: list[ThresholdMetrics] = []
    for threshold in threshold_values:
        matcher = CosineThresholdSpeakerMatcher(
            threshold=float(threshold),
            min_margin=min_margin,
            unknown_label=unknown_label,
            scoring_mode=scoring_mode,
            runtime_model_id=runtime_model_id,
        )
        decisions = tuple(
            matcher.match(_embedding_payload(sample), enrollment_db)
            for sample in sample_rows
        )
        metrics.append(
            _threshold_metrics(
                float(threshold),
                sample_rows,
                decisions,
                known_labels,
                unknown_label=unknown_label,
            )
        )

    verification = _verification_metrics(
        sample_rows,
        enrollment_db,
        min_margin=min_margin,
        scoring_mode=scoring_mode,
        runtime_model_id=runtime_model_id,
        unknown_label=unknown_label,
        fixed_far_targets=tuple(float(value) for value in fixed_far_targets),
    )
    recommended = _recommend_threshold(
        metrics,
        conservative_max_false_known_rate=conservative_max_false_known_rate,
    )
    return ThresholdCalibrationResult(
        run_id=run_id,
        metrics=tuple(metrics),
        recommended_threshold=(
            recommended.threshold
            if recommended is not None
            else None
        ),
        recommended_metrics=recommended,
        verification=verification,
        fixed_far_targets=tuple(float(value) for value in fixed_far_targets),
        conservative_max_false_known_rate=float(conservative_max_false_known_rate),
        min_margin=float(min_margin),
        scoring_mode=scoring_mode,
        unknown_label=unknown_label,
    )


def write_threshold_calibration_report(
    path: Path,
    result: ThresholdCalibrationResult,
    *,
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_commands: Sequence[str],
    runner_contract: str,
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the required M11 threshold calibration markdown report."""

    lines = [
        "# Speaker Matching Threshold Calibration Report",
        "",
        "## Milestone",
        "",
        "M11 - Speaker Matching, Unknown Fallback, and Threshold Calibration",
        "",
        f"- Run id: `{result.run_id}`",
        f"- Scoring mode: `{result.scoring_mode}`",
        f"- Minimum margin: `{result.min_margin:.4f}`",
        f"- Unknown label: `{result.unknown_label}`",
        (
            "- Conservative max false-known rate: "
            f"`{result.conservative_max_false_known_rate:.4f}`"
        ),
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Summary",
        "",
        "M11 adds cosine speaker matching against the M10 enrollment database,",
        "including configurable thresholds, score margins, model-id checks,",
        "and conservative `Unknown` fallback for unsafe decisions.",
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
        "## Recommended Threshold",
        "",
    ]
    if result.recommended_metrics is None:
        lines.append("- No threshold recommendation was available.")
    else:
        metrics = result.recommended_metrics
        lines.extend(
            [
                f"- Recommended threshold: `{metrics.threshold:.4f}`",
                f"- Known-speaker accuracy: `{_format_metric(metrics.known_speaker_accuracy)}`",
                f"- False-known rate: `{_format_metric(metrics.false_known_rate)}`",
                f"- Unknown rate: `{_format_metric(metrics.unknown_rate)}`",
                f"- Unknown rejection rate: `{_format_metric(metrics.unknown_rejection_rate)}`",
                f"- Accepted / Unknown: `{metrics.accepted_count}` / `{metrics.unknown_count}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Threshold Sweep",
            "",
            "| threshold | known accuracy | false-known rate | unknown rate | unknown rejection | accepted | unknown | margin mean |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for metrics in result.metrics:
        lines.append(
            "| "
            f"{metrics.threshold:.4f} | "
            f"{_format_metric(metrics.known_speaker_accuracy)} | "
            f"{_format_metric(metrics.false_known_rate)} | "
            f"{_format_metric(metrics.unknown_rate)} | "
            f"{_format_metric(metrics.unknown_rejection_rate)} | "
            f"{metrics.accepted_count} | "
            f"{metrics.unknown_count} | "
            f"{_format_metric(metrics.margin_mean)} |"
        )

    lines.extend(["", "## Verification-Style Metrics", ""])
    verification = result.verification
    lines.extend(
        [
            f"- Positive pairs: `{verification.positive_pair_count}`",
            f"- Negative pairs: `{verification.negative_pair_count}`",
            f"- Equal error rate: `{_format_metric(verification.equal_error_rate)}`",
            f"- Equal error threshold: `{_format_metric(verification.equal_error_threshold)}`",
        ]
    )
    if verification.tar_at_far:
        lines.append("- TAR at fixed FAR:")
        lines.extend(
            f"  - FAR `{far:.4f}`: TAR `{_format_metric(tar)}`"
            for far, tar in verification.tar_at_far
        )
    else:
        lines.append("- TAR at fixed FAR: `n/a`")

    lines.extend(["", "## Score Margin Distribution", ""])
    if result.recommended_metrics is None:
        lines.append("- Not available.")
    else:
        metrics = result.recommended_metrics
        lines.extend(
            [
                f"- Margin mean: `{_format_metric(metrics.margin_mean)}`",
                f"- Margin min/max: `{_format_metric(metrics.margin_min)}` / `{_format_metric(metrics.margin_max)}`",
            ]
        )

    lines.extend(["", "## Blockers", ""])
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate speaker matching thresholds.")
    parser.add_argument("--enrollment-db", type=Path, required=True, help="Enrollment DB JSON path.")
    parser.add_argument("--samples-jsonl", type=Path, required=True, help="Labeled query embeddings JSONL.")
    parser.add_argument("--run-id", default=None, help="Run id for the report artifact.")
    parser.add_argument("--report", type=Path, default=None, help="Markdown report output path.")
    parser.add_argument("--threshold-min", type=float, default=0.0)
    parser.add_argument("--threshold-max", type=float, default=1.0)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--min-margin", type=float, default=0.05)
    parser.add_argument("--scoring-mode", choices=["centroid", "exemplar"], default="centroid")
    parser.add_argument("--runtime-model-id", default=None)
    parser.add_argument("--unknown-label", default=UNKNOWN_LABEL)
    parser.add_argument("--max-false-known-rate", type=float, default=0.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.run_id or time.strftime("m11_speaker_matching_%Y%m%d_%H%M%S")
    report_path = args.report or threshold_calibration_report_path(TOOL_ROOT / "reports", run_id)
    db = load_enrollment_db(args.enrollment_db)
    samples = load_calibration_samples(args.samples_jsonl)
    result = calibrate_thresholds(
        samples,
        db,
        run_id=run_id,
        thresholds=default_threshold_grid(
            threshold_min=args.threshold_min,
            threshold_max=args.threshold_max,
            threshold_step=args.threshold_step,
        ),
        min_margin=args.min_margin,
        scoring_mode=args.scoring_mode,
        runtime_model_id=args.runtime_model_id,
        unknown_label=args.unknown_label,
        conservative_max_false_known_rate=args.max_false_known_rate,
    )
    write_threshold_calibration_report(
        report_path,
        result,
        files_changed=[
            "app/inference_pipeline/registry.py",
            "app/inference_pipeline/speaker_matching/__init__.py",
            "app/inference_pipeline/speaker_matching/base.py",
            "app/inference_pipeline/speaker_matching/cosine_matcher.py",
            "app/inference_pipeline/speaker_matching/thresholds.py",
            "configs/inference/components/speaker_matching/cosine_threshold.yaml",
            "tests/run_all_tests.py",
            "tests/run_smoke_tests.py",
            "tests/inference_pipeline/test_speaker_matching.py",
        ],
        test_commands=[],
        smoke_commands=[_command_summary(args, report_path)],
        runner_contract=(
            "Threshold calibration reads enrollment DB and query embedding artifacts only. "
            "It does not modify app/model_runner/external_stub.py, record['inference_audio_path'], "
            "predictions/utterances.jsonl, or scoring identity fields."
        ),
        incomplete=_incomplete_summary(result),
    )
    print(f"Recommended threshold: {result.recommended_threshold}")
    print(f"Report: {report_path}")
    return 0


def _threshold_metrics(
    threshold: float,
    samples: Sequence[CalibrationSample],
    decisions: Sequence[SpeakerDecision],
    known_labels: set[str],
    *,
    unknown_label: str,
) -> ThresholdMetrics:
    sample_count = len(samples)
    known_sample_count = sum(1 for sample in samples if sample.true_label in known_labels)
    unknown_sample_count = sample_count - known_sample_count
    known_correct = sum(
        1
        for sample, decision in zip(samples, decisions, strict=True)
        if sample.true_label in known_labels and decision.speaker_label == sample.true_label
    )
    false_known_count = sum(
        1
        for sample, decision in zip(samples, decisions, strict=True)
        if decision.speaker_label != unknown_label and decision.speaker_label != sample.true_label
    )
    unknown_count = sum(1 for decision in decisions if decision.speaker_label == unknown_label)
    unknown_rejections = sum(
        1
        for sample, decision in zip(samples, decisions, strict=True)
        if sample.true_label not in known_labels and decision.speaker_label == unknown_label
    )
    accepted_count = sample_count - unknown_count
    margins = [
        float(decision.margin)
        for decision in decisions
        if decision.margin is not None and math.isfinite(float(decision.margin))
    ]
    return ThresholdMetrics(
        threshold=threshold,
        sample_count=sample_count,
        known_sample_count=known_sample_count,
        unknown_sample_count=unknown_sample_count,
        known_speaker_accuracy=_safe_rate(known_correct, known_sample_count),
        false_known_rate=_safe_rate(false_known_count, sample_count),
        unknown_rate=_safe_rate(unknown_count, sample_count),
        unknown_rejection_rate=_safe_rate(unknown_rejections, unknown_sample_count),
        false_known_count=false_known_count,
        unknown_count=unknown_count,
        accepted_count=accepted_count,
        margin_mean=_mean(margins),
        margin_min=min(margins) if margins else None,
        margin_max=max(margins) if margins else None,
    )


def _verification_metrics(
    samples: Sequence[CalibrationSample],
    enrollment_db: EnrollmentDatabase,
    *,
    min_margin: float,
    scoring_mode: str,
    runtime_model_id: str | None,
    unknown_label: str,
    fixed_far_targets: Sequence[float],
) -> VerificationMetrics:
    matcher = CosineThresholdSpeakerMatcher(
        threshold=-1.0,
        min_margin=min_margin,
        unknown_label=unknown_label,
        scoring_mode=scoring_mode,
        runtime_model_id=runtime_model_id,
    )
    known_labels = {speaker.display_name for speaker in enrollment_db.speakers}
    positive_scores: list[float] = []
    negative_scores: list[float] = []
    for sample in samples:
        decision = matcher.match(_embedding_payload(sample), enrollment_db)
        for score in decision.scores:
            if sample.true_label in known_labels and score.speaker_label == sample.true_label:
                positive_scores.append(score.score)
            else:
                negative_scores.append(score.score)
    if not positive_scores or not negative_scores:
        return VerificationMetrics(
            positive_pair_count=len(positive_scores),
            negative_pair_count=len(negative_scores),
            equal_error_rate=None,
            equal_error_threshold=None,
            tar_at_far=tuple((float(target), None) for target in fixed_far_targets),
        )

    thresholds = sorted(set(positive_scores + negative_scores))
    best_eer: tuple[float, float] | None = None
    best_eer_diff: float | None = None
    tar_at_far: list[tuple[float, float | None]] = []
    operating_points: list[tuple[float, float, float]] = []
    for threshold in thresholds:
        far = _safe_rate(
            sum(1 for score in negative_scores if score >= threshold),
            len(negative_scores),
        )
        tar = _safe_rate(
            sum(1 for score in positive_scores if score >= threshold),
            len(positive_scores),
        )
        if far is None or tar is None:
            continue
        frr = 1.0 - tar
        operating_points.append((threshold, far, tar))
        diff = abs(far - frr)
        candidate = ((far + frr) / 2.0, threshold)
        if best_eer_diff is None or diff < best_eer_diff:
            best_eer = candidate
            best_eer_diff = diff

    for target in fixed_far_targets:
        candidates = [tar for _threshold, far, tar in operating_points if far <= float(target)]
        tar_at_far.append((float(target), max(candidates) if candidates else None))

    return VerificationMetrics(
        positive_pair_count=len(positive_scores),
        negative_pair_count=len(negative_scores),
        equal_error_rate=best_eer[0] if best_eer is not None else None,
        equal_error_threshold=best_eer[1] if best_eer is not None else None,
        tar_at_far=tuple(tar_at_far),
    )


def _recommend_threshold(
    metrics: Sequence[ThresholdMetrics],
    *,
    conservative_max_false_known_rate: float,
) -> ThresholdMetrics | None:
    if not metrics:
        return None
    candidates = [
        item
        for item in metrics
        if item.false_known_rate is not None
        and item.false_known_rate <= conservative_max_false_known_rate
    ]
    if not candidates:
        candidates = [min(metrics, key=lambda item: item.false_known_rate or 1.0)]
    return sorted(
        candidates,
        key=lambda item: (
            item.false_known_rate if item.false_known_rate is not None else 1.0,
            -(item.known_speaker_accuracy if item.known_speaker_accuracy is not None else -1.0),
            item.unknown_rate if item.unknown_rate is not None else 1.0,
            -item.threshold,
        ),
    )[0]


def _embedding_payload(sample: CalibrationSample) -> dict[str, object]:
    return {
        "embedding_id": sample.sample_id,
        "vector": list(sample.embedding),
        "model_id": sample.model_id,
    }


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _incomplete_summary(result: ThresholdCalibrationResult) -> list[str]:
    items: list[str] = []
    if result.verification.equal_error_rate is None:
        items.append("EER is unavailable because calibration samples did not provide both positive and negative score pairs.")
    if any(tar is None for _far, tar in result.verification.tar_at_far):
        items.append("Some TAR-at-FAR targets are unavailable because no threshold met the requested FAR.")
    return items


def _command_summary(args: argparse.Namespace, report_path: Path) -> str:
    parts = [
        "python",
        "-m",
        "app.inference_pipeline.speaker_matching.thresholds",
        "--enrollment-db",
        str(args.enrollment_db),
        "--samples-jsonl",
        str(args.samples_jsonl),
        "--report",
        str(report_path),
        "--threshold-min",
        str(args.threshold_min),
        "--threshold-max",
        str(args.threshold_max),
        "--threshold-step",
        str(args.threshold_step),
        "--min-margin",
        str(args.min_margin),
        "--scoring-mode",
        str(args.scoring_mode),
        "--unknown-label",
        str(args.unknown_label),
        "--max-false-known-rate",
        str(args.max_false_known_rate),
    ]
    if args.run_id is not None:
        parts.extend(["--run-id", str(args.run_id)])
    if args.runtime_model_id is not None:
        parts.extend(["--runtime-model-id", str(args.runtime_model_id)])
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
