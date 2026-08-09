"""Deterministic Stage 7 metrics with explicit support boundaries."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from statistics import fmean
from typing import Iterable, Mapping, Sequence

from app.inference_pipeline.asr.base import normalize_text
from app.inference_pipeline.asr.metrics import (
    consecutive_duplicate_token_rate,
    repeated_ngram_rate,
    repeated_word_rate,
)
from app.scoring.wer import compute_wer


ASR_METRICS_SCHEMA_VERSION = "core-asr-screening-metrics.v1"
VAD_METRICS_SCHEMA_VERSION = "core-vad-screening-metrics.v1"
EMBEDDING_METRICS_SCHEMA_VERSION = "core-embedding-qualification-metrics.v1"
RELIABILITY_METRICS_SCHEMA_VERSION = "core-reliability-metrics.v1"

STAGE10_ONLY_METRICS = (
    "eer",
    "far",
    "frr",
    "top_1_identification",
    "top_k_identification",
    "unknown_rejection",
)


def analyze_asr_items(
    expected_items: Sequence[Mapping[str, object]],
    prediction_rows: Sequence[object],
    *,
    failure_rows: Sequence[Mapping[str, object]] = (),
    diagnostic_rows: Sequence[Mapping[str, object]] = (),
    component_spans: Sequence[Mapping[str, object]] = (),
    resource_summary: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Score all expected items while retaining failed/missing items in denominators.

    Missing, failed, and attributable malformed outputs use an empty hypothesis for
    the primary WER/CER. This makes the coverage penalty explicit rather than
    silently reducing the evaluation set. Duplicate rows use the first valid row.
    """

    expected = [_expected_item(row) for row in expected_items]
    expected_keys = {_item_key(row) for row in expected}
    if len(expected_keys) != len(expected):
        raise ValueError(
            "expected ASR items contain duplicate recording_id/utt_id keys"
        )

    predictions: dict[tuple[str, str], Mapping[str, object]] = {}
    malformed = 0
    duplicates = 0
    unexpected = 0
    for raw in prediction_rows:
        if not isinstance(raw, Mapping):
            malformed += 1
            continue
        key = _optional_item_key(raw)
        if key is None or not isinstance(raw.get("text"), str):
            malformed += 1
            continue
        if key not in expected_keys:
            unexpected += 1
            continue
        if key in predictions:
            duplicates += 1
            continue
        predictions[key] = raw

    failure_keys = {
        key
        for row in failure_rows
        if (key := _optional_item_key(row)) is not None and key in expected_keys
    }
    diagnostics = {
        key: row
        for row in diagnostic_rows
        if (key := _optional_item_key(row)) is not None and key in expected_keys
    }

    word_errors = substitutions = deletions = insertions = 0
    reference_words = hypothesis_words = 0
    character_errors = character_reference_count = character_hypothesis_count = 0
    item_wer: list[float] = []
    item_cer: list[float] = []
    outputs: list[str] = []
    missing = empty = failed = valid = 0
    timings: list[float] = []
    rtfs: list[float] = []
    durations: list[float] = []

    for item in expected:
        key = _item_key(item)
        prediction = predictions.get(key)
        hypothesis = str(prediction["text"]) if prediction is not None else ""
        outputs.append(hypothesis)
        if prediction is None:
            missing += 1
        else:
            valid += 1
            if not normalize_text(hypothesis):
                empty += 1
        if key in failure_keys:
            failed += 1

        reference = str(item["reference_text"])
        word = compute_wer(normalize_text(reference), normalize_text(hypothesis))
        word_errors += word.errors
        substitutions += word.substitutions
        deletions += word.deletions
        insertions += word.insertions
        reference_words += word.reference_words
        hypothesis_words += word.hypothesis_words
        item_wer.append(word.wer)

        ref_chars = _cer_characters(reference)
        hyp_chars = _cer_characters(hypothesis)
        char_errors = _edit_distance(ref_chars, hyp_chars)
        character_errors += char_errors
        character_reference_count += len(ref_chars)
        character_hypothesis_count += len(hyp_chars)
        item_cer.append(_error_rate(char_errors, len(ref_chars)))

        duration = _optional_number(item.get("duration_sec"))
        diagnostic = diagnostics.get(key)
        runtime = diagnostic.get("runtime_stats") if diagnostic else None
        if isinstance(runtime, Mapping):
            total = _optional_number(runtime.get("total_sec"))
            rtf = _optional_number(runtime.get("realtime_factor"))
            if total is not None:
                timings.append(total)
                if duration is not None and duration > 0:
                    durations.append(duration)
            if rtf is not None:
                rtfs.append(rtf)

    denominator = len(expected)
    supported = [
        "micro_wer",
        "macro_wer",
        "micro_cer",
        "macro_cer",
        "substitutions",
        "insertions",
        "deletions",
        "reference_words",
        "hypothesis_words",
        "empty_predictions",
        "missing_predictions",
        "malformed_predictions",
        "duplicate_predictions",
        "unexpected_predictions",
        "repetition_diagnostics",
    ]
    metrics: dict[str, object] = {
        "schema_version": ASR_METRICS_SCHEMA_VERSION,
        "denominator_policy": {
            "expected_items": denominator,
            "missing_or_failed_hypothesis": "empty_string",
            "duplicate_policy": "first_valid_prediction",
            "cer_units": "normalized_characters_excluding_whitespace",
        },
        "expected_items": denominator,
        "valid_predictions": valid,
        "valid_output_rate": _rate(valid, denominator),
        "missing_predictions": missing,
        "missing_prediction_rate": _rate(missing, denominator),
        "failed_items": failed,
        "failure_rate": _rate(failed, denominator),
        "empty_predictions": empty,
        "empty_prediction_rate": _rate(empty, denominator),
        "malformed_predictions": malformed,
        "duplicate_predictions": duplicates,
        "unexpected_predictions": unexpected,
        "word_errors": word_errors,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "reference_words": reference_words,
        "hypothesis_words": hypothesis_words,
        "micro_wer": _error_rate(word_errors, reference_words),
        "macro_wer": _mean(item_wer),
        "character_errors": character_errors,
        "reference_characters": character_reference_count,
        "hypothesis_characters": character_hypothesis_count,
        "micro_cer": _error_rate(character_errors, character_reference_count),
        "macro_cer": _mean(item_cer),
        "repetition_diagnostics": {
            "mean_repeated_word_rate": _mean(
                [repeated_word_rate(text) for text in outputs]
            ),
            "mean_repeated_bigram_rate": _mean(
                [repeated_ngram_rate(text, n=2) for text in outputs]
            ),
            "mean_consecutive_duplicate_token_rate": _mean(
                [consecutive_duplicate_token_rate(text) for text in outputs]
            ),
        },
    }

    silence_flags = [item.get("is_silence") for item in expected]
    if silence_flags and all(isinstance(value, bool) for value in silence_flags):
        silent_outputs = [
            outputs[index] for index, value in enumerate(silence_flags) if bool(value)
        ]
        metrics["hallucinated_silent_outputs"] = sum(
            1 for value in silent_outputs if normalize_text(value)
        )
        metrics["hallucinated_silent_output_rate"] = _rate(
            int(metrics["hallucinated_silent_outputs"]), len(silent_outputs)
        )
        supported.append("hallucinated_silent_output_rate")
    else:
        metrics["unsupported_metrics"] = [
            {
                "metric": "hallucinated_silent_output_rate",
                "reason": "the benchmark items do not provide explicit silence references",
            }
        ]

    if timings:
        supported.extend(["latency_mean_sec", "latency_p50_sec", "latency_p95_sec"])
        metrics["latency_mean_sec"] = _mean(timings)
        metrics["latency_p50_sec"] = _percentile(timings, 50)
        metrics["latency_p95_sec"] = _percentile(timings, 95)
        metrics["inference_time_sec"] = sum(timings)
    if rtfs:
        supported.extend(["mean_rtf", "p95_rtf"])
        metrics["mean_rtf"] = _mean(rtfs)
        metrics["p95_rtf"] = _percentile(rtfs, 95)
    if durations and timings:
        total_audio = sum(durations)
        total_time = sum(timings)
        metrics["throughput_audio_sec_per_wall_sec"] = (
            total_audio / total_time if total_time > 0 else None
        )
        supported.append("throughput_audio_sec_per_wall_sec")

    load_spans = [
        _span_duration(row)
        for row in component_spans
        if str(row.get("component") or row.get("name") or "") == "asr_model_load"
    ]
    load_spans = [value for value in load_spans if value is not None]
    if load_spans:
        metrics["initialization_time_sec"] = sum(load_spans)
        supported.append("initialization_time_sec")
    if resource_summary is not None:
        metrics["resource_usage"] = _screening_resource_fields(resource_summary)
        supported.append("resource_usage")
    metrics["supported_metrics"] = sorted(set(supported))
    metrics.setdefault("unsupported_metrics", [])
    return metrics


def analyze_vad_segments(
    items: Sequence[Mapping[str, object]],
    *,
    collar_sec: float = 0.25,
    boundary_tolerance_sec: float = 0.25,
    too_short_sec: float = 0.2,
) -> dict[str, object]:
    """Measure VAD/segment outputs and conditionally score referenced regions."""

    if collar_sec < 0 or boundary_tolerance_sec < 0 or too_short_sec < 0:
        raise ValueError("VAD collar, tolerance, and too-short thresholds must be >= 0")
    segment_durations: list[float] = []
    segment_count = empty_segments = too_short_segments = 0
    total_audio_sec = 0.0
    referenced_items = 0
    total_reference = total_prediction = total_overlap = 0.0
    item_ious: list[float] = []
    boundary_deviations: list[float] = []
    within_tolerance = boundary_count = 0
    fragmented = merged = reference_region_count = predicted_region_count = 0

    for item in items:
        duration = max(0.0, float(item.get("duration_sec") or 0.0))
        total_audio_sec += duration
        predictions = _intervals(item.get("predicted_regions"), duration)
        segments = _intervals(item.get("segments"), duration)
        predicted_region_count += len(predictions)
        segment_count += len(segments)
        if not segments:
            empty_segments += 1
        for start, end in segments:
            value = end - start
            segment_durations.append(value)
            if value < too_short_sec:
                too_short_segments += 1

        if "reference_regions" not in item or item.get("reference_regions") is None:
            continue
        references = _intervals(item.get("reference_regions"), duration)
        referenced_items += 1
        reference_region_count += len(references)
        total_reference += _union_duration(references)
        total_prediction += _union_duration(predictions)
        total_overlap += _intersection_duration(references, predictions)
        union = _union_duration([*references, *predictions])
        item_ious.append(
            _intersection_duration(references, predictions) / union if union else 1.0
        )

        for reference in references:
            overlaps = [
                candidate
                for candidate in predictions
                if _overlap(reference, candidate) > 0
            ]
            if len(overlaps) > 1:
                fragmented += 1
        for prediction in predictions:
            overlaps = [
                candidate
                for candidate in references
                if _overlap(prediction, candidate) > 0
            ]
            if len(overlaps) > 1:
                merged += 1
        for reference, prediction in _greedy_interval_matches(references, predictions):
            for ref_boundary, pred_boundary in zip(reference, prediction, strict=True):
                deviation = abs(ref_boundary - pred_boundary)
                boundary_deviations.append(deviation)
                boundary_count += 1
                if deviation <= boundary_tolerance_sec + collar_sec:
                    within_tolerance += 1

    metrics: dict[str, object] = {
        "schema_version": VAD_METRICS_SCHEMA_VERSION,
        "policy": {
            "collar_sec": collar_sec,
            "boundary_tolerance_sec": boundary_tolerance_sec,
            "effective_boundary_tolerance_sec": collar_sec + boundary_tolerance_sec,
            "duration_overlap_uses_collar": False,
            "too_short_sec": too_short_sec,
        },
        "evaluated_items": len(items),
        "total_audio_sec": total_audio_sec,
        "segment_count": segment_count,
        "segments_per_minute": segment_count / (total_audio_sec / 60.0)
        if total_audio_sec
        else 0.0,
        "empty_segment_items": empty_segments,
        "too_short_segments": too_short_segments,
        "segment_duration_sec": _distribution_summary(segment_durations),
        "supported_metrics": [
            "segment_count",
            "segments_per_minute",
            "segment_duration_sec",
            "empty_segment_items",
            "too_short_segments",
        ],
        "unsupported_metrics": [],
    }
    if referenced_items:
        precision = total_overlap / total_prediction if total_prediction else 0.0
        recall = total_overlap / total_reference if total_reference else 0.0
        metrics.update(
            {
                "referenced_items": referenced_items,
                "speech_precision": precision,
                "speech_recall": recall,
                "speech_f1": _f1(precision, recall),
                "missed_speech_duration_sec": max(0.0, total_reference - total_overlap),
                "false_alarm_duration_sec": max(0.0, total_prediction - total_overlap),
                "mean_region_iou": _mean(item_ious),
                "mean_boundary_deviation_sec": _mean(boundary_deviations),
                "boundary_within_tolerance_rate": _rate(
                    within_tolerance, boundary_count
                ),
                "fragmented_reference_regions": fragmented,
                "fragmentation_rate": _rate(fragmented, reference_region_count),
                "merged_prediction_regions": merged,
                "merge_rate": _rate(merged, predicted_region_count),
            }
        )
        metrics["supported_metrics"] = sorted(
            [
                *metrics["supported_metrics"],
                "speech_precision",
                "speech_recall",
                "speech_f1",
                "missed_speech_duration_sec",
                "false_alarm_duration_sec",
                "mean_region_iou",
                "mean_boundary_deviation_sec",
                "boundary_within_tolerance_rate",
                "fragmentation_rate",
                "merge_rate",
            ]
        )
    else:
        metrics["unsupported_metrics"] = [
            {
                "metric": name,
                "reason": "no VAD reference regions are present for these items",
            }
            for name in (
                "speech_precision",
                "speech_recall",
                "speech_f1",
                "missed_speech_duration_sec",
                "false_alarm_duration_sec",
                "mean_region_iou",
                "mean_boundary_deviation_sec",
                "fragmentation_rate",
                "merge_rate",
            )
        ]
    return metrics


def analyze_embedding_results(
    rows: Sequence[Mapping[str, object]],
    *,
    min_duration_sec: float = 0.75,
) -> dict[str, object]:
    """Qualify fixed-segment embeddings without Stage 10 recognition metrics."""

    norms: list[float] = []
    dimensions: Counter[int] = Counter()
    valid_vectors: dict[tuple[str, str, int], tuple[float, ...]] = {}
    statuses: Counter[str] = Counter()
    invalid_vectors = 0
    minimum_duration_cases = minimum_duration_rejections = 0

    for index, row in enumerate(rows):
        status = str(row.get("status") or "failed")
        statuses[status] += 1
        duration = _optional_number(row.get("duration_sec"))
        if duration is not None and duration < min_duration_sec:
            minimum_duration_cases += 1
            if status == "too_short":
                minimum_duration_rejections += 1
        vector = _finite_vector(row.get("vector"))
        if status != "ok":
            continue
        if vector is None:
            invalid_vectors += 1
            continue
        dimension = len(vector)
        dimensions[dimension] += 1
        norm = math.sqrt(sum(value * value for value in vector))
        norms.append(norm)
        segment_id = str(row.get("segment_id") or row.get("embedding_id") or index)
        condition = str(row.get("condition") or "clean")
        repetition = int(row.get("repetition") or 1)
        valid_vectors[(segment_id, condition, repetition)] = vector

    repeatability: list[float] = []
    grouped: dict[tuple[str, str], list[tuple[int, tuple[float, ...]]]] = defaultdict(
        list
    )
    for (segment_id, condition, repetition), vector in valid_vectors.items():
        grouped[(segment_id, condition)].append((repetition, vector))
    for values in grouped.values():
        ordered = [vector for _rep, vector in sorted(values)]
        if len(ordered) < 2:
            continue
        anchor = ordered[0]
        repeatability.extend(_cosine(anchor, candidate) for candidate in ordered[1:])

    paired_drift: list[float] = []
    pair_groups: dict[tuple[str, int], dict[str, tuple[float, ...]]] = defaultdict(dict)
    row_lookup = {
        (
            str(row.get("segment_id") or row.get("embedding_id") or index),
            str(row.get("condition") or "clean"),
            int(row.get("repetition") or 1),
        ): row
        for index, row in enumerate(rows)
    }
    for key, vector in valid_vectors.items():
        row = row_lookup.get(key, {})
        pair_id = str(row.get("pair_id") or key[0])
        pair_groups[(pair_id, key[2])][key[1]] = vector
    for conditions in pair_groups.values():
        clean = conditions.get("clean")
        for name, degraded in conditions.items():
            if clean is not None and name != "clean" and len(clean) == len(degraded):
                paired_drift.append(1.0 - _cosine(clean, degraded))

    successful = sum(dimensions.values())
    metrics: dict[str, object] = {
        "schema_version": EMBEDDING_METRICS_SCHEMA_VERSION,
        "expected_extractions": len(rows),
        "successful_extractions": successful,
        "extraction_success_rate": _rate(successful, len(rows)),
        "statuses": dict(sorted(statuses.items())),
        "dimensions": {str(key): value for key, value in sorted(dimensions.items())},
        "invalid_or_nonfinite_vectors": invalid_vectors,
        "l2_norm": _distribution_summary(norms),
        "repeatability_cosine": _distribution_summary(repeatability),
        "minimum_duration_cases": minimum_duration_cases,
        "minimum_duration_rejections": minimum_duration_rejections,
        "minimum_duration_rejection_rate": _rate(
            minimum_duration_rejections, minimum_duration_cases
        ),
        "clean_to_degraded_cosine_drift": _distribution_summary(paired_drift),
        "supported_metrics": [
            "extraction_success_rate",
            "dimensions",
            "invalid_or_nonfinite_vectors",
            "l2_norm",
            "repeatability_cosine",
            "minimum_duration_rejection_rate",
            "clean_to_degraded_cosine_drift",
        ],
        "unsupported_metrics": [
            {
                "metric": metric,
                "reason": "speaker recognition metrics belong to Stage 10",
            }
            for metric in STAGE10_ONLY_METRICS
        ],
    }
    return metrics


def analyze_reliability(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Summarize scenario/item reliability using the full attempted denominator."""

    statuses = Counter(str(row.get("status") or "unknown") for row in rows)
    total = len(rows)
    valid = sum(
        statuses[name]
        for name in (
            "succeeded",
            "succeeded_with_warnings",
            "successful",
            "complete",
            "valid",
        )
    )
    failures = sum(
        count
        for name, count in statuses.items()
        if name in {"failed", "failed_retryable", "failed_terminal", "invalid"}
    )
    return {
        "schema_version": RELIABILITY_METRICS_SCHEMA_VERSION,
        "attempted": total,
        "statuses": dict(sorted(statuses.items())),
        "valid_output_rate": _rate(valid, total),
        "failure_rate": _rate(failures, total),
        "timeout_rate": _rate(statuses["timeout"], total),
        "retry_rate": _rate(
            sum(1 for row in rows if int(row.get("attempt") or 1) > 1), total
        ),
        "oom_rate": _rate(statuses["out_of_memory"], total),
        "scenario_completion_rate": _rate(valid, total),
    }


def _expected_item(row: Mapping[str, object]) -> dict[str, object]:
    result = dict(row)
    if not str(result.get("recording_id") or "").strip():
        raise ValueError("expected item is missing recording_id")
    if not str(result.get("utt_id") or "").strip():
        raise ValueError("expected item is missing utt_id")
    if "reference_text" not in result:
        raise ValueError("expected item is missing reference_text")
    return result


def _item_key(row: Mapping[str, object]) -> tuple[str, str]:
    return str(row["recording_id"]), str(row["utt_id"])


def _optional_item_key(row: Mapping[str, object]) -> tuple[str, str] | None:
    recording = str(row.get("recording_id") or "").strip()
    utterance = str(row.get("utt_id") or "").strip()
    return (recording, utterance) if recording and utterance else None


def _cer_characters(text: str) -> list[str]:
    return [character for character in normalize_text(text) if not character.isspace()]


def _edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for index, reference_value in enumerate(reference, start=1):
        current = [index]
        for column, hypothesis_value in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (reference_value != hypothesis_value),
                )
            )
        previous = current
    return previous[-1]


def _intervals(value: object, duration_sec: float) -> list[tuple[float, float]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError("region/segment values must be a sequence")
    result = []
    for item in value:
        if isinstance(item, Mapping):
            start = float(item.get("start_sec") or 0.0)
            end = float(item.get("end_sec") or 0.0)
        elif isinstance(item, Sequence) and len(item) == 2:
            start, end = float(item[0]), float(item[1])
        else:
            raise ValueError("each interval must provide start_sec/end_sec")
        start = max(0.0, start)
        end = min(duration_sec, end) if duration_sec > 0 else end
        if end > start:
            result.append((start, end))
    return _merge_intervals(result)


def _merge_intervals(
    values: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(values):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _union_duration(values: Sequence[tuple[float, float]]) -> float:
    return sum(end - start for start, end in _merge_intervals(values))


def _intersection_duration(
    first: Sequence[tuple[float, float]], second: Sequence[tuple[float, float]]
) -> float:
    return sum(_overlap(left, right) for left in first for right in second)


def _overlap(first: tuple[float, float], second: tuple[float, float]) -> float:
    return max(0.0, min(first[1], second[1]) - max(first[0], second[0]))


def _greedy_interval_matches(
    references: Sequence[tuple[float, float]],
    predictions: Sequence[tuple[float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    candidates = sorted(
        (
            (_overlap(reference, prediction), reference_index, prediction_index)
            for reference_index, reference in enumerate(references)
            for prediction_index, prediction in enumerate(predictions)
        ),
        reverse=True,
    )
    matched_references: set[int] = set()
    matched_predictions: set[int] = set()
    matches = []
    for overlap, reference_index, prediction_index in candidates:
        if overlap <= 0:
            break
        if (
            reference_index in matched_references
            or prediction_index in matched_predictions
        ):
            continue
        matched_references.add(reference_index)
        matched_predictions.add(prediction_index)
        matches.append((references[reference_index], predictions[prediction_index]))
    return matches


def _finite_vector(value: object) -> tuple[float, ...] | None:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return None
    try:
        vector = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not vector or not all(math.isfinite(item) for item in vector):
        return None
    return vector


def _cosine(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != len(second) or not first:
        return float("nan")
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if not first_norm or not second_norm:
        return float("nan")
    return sum(left * right for left, right in zip(first, second, strict=True)) / (
        first_norm * second_norm
    )


def _screening_resource_fields(summary: Mapping[str, object]) -> dict[str, object]:
    allowed = {
        "scenario_summary_count",
        "sample_count",
        "span_count",
        "sampling_interval_sec",
        "sampling_gap_count",
        "resources",
        "components",
        "phases",
        "availability",
        "process_cpu_percent",
        "system_cpu_percent",
        "process_rss_bytes",
        "system_ram_used_bytes",
        "gpu_utilization_percent",
        "gpu_memory_used_bytes",
        "peak_vram_bytes",
        "disk_read_bytes",
        "disk_write_bytes",
        "warnings",
    }
    return {str(key): value for key, value in summary.items() if key in allowed}


def _span_duration(row: Mapping[str, object]) -> float | None:
    duration_ns = _optional_number(row.get("duration_ns"))
    if duration_ns is not None:
        return duration_ns / 1_000_000_000
    for key in ("duration_sec", "wall_duration_sec"):
        value = _optional_number(row.get(key))
        if value is not None:
            return value
    start = _optional_number(row.get("start_monotonic_ns"))
    end = _optional_number(row.get("end_monotonic_ns"))
    if start is not None and end is not None and end >= start:
        return (end - start) / 1_000_000_000
    return None


def _distribution_summary(values: Iterable[float]) -> dict[str, object]:
    finite = sorted(float(value) for value in values if math.isfinite(float(value)))
    return {
        "count": len(finite),
        "mean": _mean(finite),
        "p50": _percentile(finite, 50),
        "p95": _percentile(finite, 95),
        "min": finite[0] if finite else None,
        "max": finite[-1] if finite else None,
    }


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _mean(values: Sequence[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return fmean(finite) if finite else None


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    finite = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not finite:
        return None
    if len(finite) == 1:
        return finite[0]
    position = (len(finite) - 1) * percentile / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    weight = position - lower
    return finite[lower] * (1.0 - weight) + finite[upper] * weight


def _error_rate(errors: int, reference_count: int) -> float:
    if reference_count == 0:
        return 0.0 if errors == 0 else 1.0
    return errors / reference_count


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return (
        2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    )
