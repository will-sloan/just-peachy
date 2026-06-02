"""Speaker matching and enrollment metric summaries for reusable reports."""

from __future__ import annotations

from typing import Mapping, Sequence


UNKNOWN_LABEL = "Unknown"


def summarize_speaker_decisions(
    decisions: Sequence[Mapping[str, object]],
    *,
    reference_labels: Sequence[str | None] | None = None,
    unknown_label: str = UNKNOWN_LABEL,
) -> dict[str, object]:
    """Summarize speaker decisions without changing scorer semantics."""

    decision_rows = tuple(decisions)
    reference_rows = tuple(reference_labels or ())
    total = len(decision_rows)
    unknown_count = 0
    accepted_count = 0
    correct_count = 0
    false_known_count = 0
    scored_count = 0
    threshold_counts: dict[str, int] = {}

    for index, decision in enumerate(decision_rows):
        label = _optional_string(
            decision.get("speaker_label")
            or decision.get("predicted_speaker_label")
            or decision.get("best_label")
        )
        accepted = _optional_bool(decision.get("accepted"))
        if accepted is None:
            accepted = label is not None and label != unknown_label
        if accepted:
            accepted_count += 1
        if label == unknown_label or label is None:
            unknown_count += 1

        threshold_decision = _optional_string(decision.get("threshold_decision"))
        if threshold_decision:
            threshold_counts[threshold_decision] = threshold_counts.get(threshold_decision, 0) + 1

        if index < len(reference_rows):
            reference = _optional_string(reference_rows[index])
            if reference:
                scored_count += 1
                if label == reference:
                    correct_count += 1
                elif label and label != unknown_label:
                    false_known_count += 1

    return {
        "decision_count": total,
        "accepted_count": accepted_count,
        "unknown_count": unknown_count,
        "unknown_rate": _safe_rate(unknown_count, total),
        "speaker_accuracy": _safe_rate(correct_count, scored_count),
        "speaker_scored_count": scored_count,
        "false_known_count": false_known_count,
        "false_known_rate": _safe_rate(false_known_count, scored_count),
        "threshold_decision_counts": threshold_counts,
    }


def extract_speaker_decisions_from_diagnostics(
    diagnostics_rows: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    """Extract nested speaker decision objects from diagnostics JSONL rows."""

    decisions: list[Mapping[str, object]] = []
    for row in diagnostics_rows:
        diagnostics = row.get("diagnostics")
        if not isinstance(diagnostics, Mapping):
            continue
        nested = diagnostics.get("speaker_decisions")
        if not isinstance(nested, Sequence) or isinstance(nested, str | bytes | bytearray):
            continue
        for decision in nested:
            if isinstance(decision, Mapping):
                decisions.append(decision)
    return tuple(decisions)


def speaker_primary_recommendation(metrics: Mapping[str, object]) -> str:
    """Return a concise speaker-matching recommendation for report indexes."""

    false_known_rate = _optional_float(metrics.get("false_known_rate"))
    unknown_rate = _optional_float(metrics.get("unknown_rate"))
    accuracy = _optional_float(
        metrics.get("speaker_accuracy")
        or metrics.get("speaker_label_accuracy")
    )
    if false_known_rate is not None and false_known_rate > 0:
        return "Tighten speaker matching thresholds before accepting named-speaker output."
    if accuracy is not None and accuracy >= 0.90:
        return "Speaker matching is ready for broader dataset comparison."
    if unknown_rate is not None and unknown_rate >= 0.50:
        return "Improve enrollment coverage or thresholds; most decisions are Unknown."
    if accuracy is None:
        return "Add labeled speaker references before ranking speaker matching quality."
    return "Continue calibration before treating speaker labels as deployment-ready."


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
