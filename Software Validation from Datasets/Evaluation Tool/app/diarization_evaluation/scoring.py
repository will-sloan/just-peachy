"""Permutation-aware diarization and speaker-attributed transcript scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.diarization_evaluation.contracts import (
    METRICS_SCHEMA_VERSION,
    DiarizationEvaluationError,
    DiarizationScoringPolicy,
)
from app.diarization_evaluation.formats import RttmTurn, UemRegion
from app.scoring.wer import compute_wer


@dataclass(frozen=True)
class TimebaseValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    expected_recording_ids: tuple[str, ...]
    reference_recording_ids: tuple[str, ...]
    hypothesis_recording_ids: tuple[str, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": "diarization-timebase-validation.v1",
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "timebase": "source_recording_absolute_seconds",
            "expected_recording_ids": list(self.expected_recording_ids),
            "reference_recording_ids": list(self.reference_recording_ids),
            "hypothesis_recording_ids": list(self.hypothesis_recording_ids),
        }


def validate_timebase(
    reference: Sequence[RttmTurn],
    hypothesis: Sequence[RttmTurn],
    uem: Sequence[UemRegion],
    *,
    label_semantics: str = "anonymous_diarization",
) -> TimebaseValidation:
    """Validate IDs, source-coordinate bounds, and anonymous-label semantics."""

    errors: list[str] = []
    warnings: list[str] = []
    expected_keys = {(region.recording_id, region.channel) for region in uem}
    expected = {recording_id for recording_id, _channel in expected_keys}
    ref_ids = {turn.recording_id for turn in reference}
    hyp_ids = {turn.recording_id for turn in hypothesis}
    ref_keys = {(turn.recording_id, turn.channel) for turn in reference}
    hyp_keys = {(turn.recording_id, turn.channel) for turn in hypothesis}
    if not expected:
        errors.append("no UEM/scored region was supplied")
    if ref_keys - expected_keys:
        errors.append("reference RTTM contains recording/channel pairs absent from UEM")
    if hyp_keys - expected_keys:
        errors.append("hypothesis RTTM contains recording/channel pairs absent from UEM")
    if reference and expected - ref_ids:
        warnings.append("some UEM recording IDs contain no reference speech")
    if hypothesis and expected - hyp_ids:
        warnings.append("some UEM recording IDs contain no predicted speech")
    if not hypothesis:
        warnings.append("hypothesis RTTM is empty; missing-speech errors remain scoreable")

    regions = _regions_by_key(uem)
    for label, turns in (("reference", reference), ("hypothesis", hypothesis)):
        for turn in turns:
            matching_regions = regions.get((turn.recording_id, turn.channel), ())
            if not _overlaps_any(turn, matching_regions):
                errors.append(f"{label} RTTM turn lies entirely outside its UEM region")
                break
            if not _contained_by_any(turn, matching_regions):
                warnings.append(f"{label} RTTM turn extends outside its UEM and will be clipped")
                break
    if label_semantics == "anonymous_diarization":
        reference_labels = {turn.speaker_label for turn in reference}
        if any(turn.speaker_label in reference_labels for turn in hypothesis):
            errors.append("anonymous hypothesis labels reuse reference speaker identities")
        if any(not turn.speaker_label.startswith("speaker_") for turn in hypothesis):
            errors.append("anonymous diarization labels must use the speaker_ namespace")
    elif label_semantics not in {"known_speaker", "speaker_change", "full_diarization"}:
        errors.append(f"unsupported speaker-label semantics: {label_semantics}")
    return TimebaseValidation(
        valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
        expected_recording_ids=tuple(sorted(expected)),
        reference_recording_ids=tuple(sorted(ref_ids)),
        hypothesis_recording_ids=tuple(sorted(hyp_ids)),
    )


def score_diarization(
    reference: Sequence[RttmTurn],
    hypothesis: Sequence[RttmTurn],
    uem: Sequence[UemRegion],
    *,
    policy: DiarizationScoringPolicy | None = None,
    reference_compatible: bool = True,
    incompatibility_reason: str | None = None,
    label_semantics: str = "anonymous_diarization",
) -> dict[str, object]:
    """Score exact atomic intervals or suppress metrics when contracts are invalid."""

    active_policy = policy or DiarizationScoringPolicy()
    alignment = validate_timebase(
        reference,
        hypothesis,
        uem,
        label_semantics=label_semantics,
    )
    result: dict[str, object] = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "scoring_policy": active_policy.to_jsonable(),
        "label_semantics": label_semantics,
        "timebase_validation": alignment.to_jsonable(),
        "reference_compatible": reference_compatible,
        "metrics_emitted": False,
        "predicted_turn_count": len(hypothesis),
        "reference_turn_count": len(reference),
        "predicted_speaker_count": len({turn.speaker_label for turn in hypothesis}),
        "reference_speaker_count": len({turn.speaker_label for turn in reference}),
        "speaker_count_mode": active_policy.speaker_count_mode,
        "speaker_count_error": (
            len({turn.speaker_label for turn in hypothesis})
            - len({turn.speaker_label for turn in reference})
            if reference_compatible and reference
            else None
        ),
    }
    if not reference_compatible:
        result["suppression_reasons"] = [
            incompatibility_reason or "reference/output pair is not compatible"
        ]
        return result
    if not alignment.valid:
        result["suppression_reasons"] = list(alignment.errors)
        return result
    if not reference:
        result["suppression_reasons"] = ["reference RTTM contains no speech turns"]
        return result

    mode_results: dict[str, object] = {}
    for mode in active_policy.overlap_modes:
        scored = _score_mode(
            reference,
            hypothesis,
            uem,
            collar_sec=active_policy.collar_sec,
            overlap_excluded=mode == "overlap_excluded",
        )
        mode_results[mode] = scored
    result["modes"] = mode_results
    primary = mode_results.get("overlap_aware")
    if isinstance(primary, Mapping) and primary.get("valid"):
        result.update(
            {
                "metrics_emitted": True,
                "der": primary["der"],
                "jer": primary["jer"],
                "missed_speech_sec": primary["missed_speech_sec"],
                "false_alarm_sec": primary["false_alarm_sec"],
                "speaker_confusion_sec": primary["speaker_confusion_sec"],
                "reference_speaker_time_sec": primary["reference_speaker_time_sec"],
                "anonymous_label_consistency": primary["anonymous_label_consistency"],
                "permutation_aware": True,
                "scoring_mapping_pair_count": primary["scoring_mapping_pair_count"],
            }
        )
    else:
        reasons = []
        for value in mode_results.values():
            if isinstance(value, Mapping) and value.get("reason"):
                reasons.append(str(value["reason"]))
        result["suppression_reasons"] = reasons or ["no reference speaker-time remains"]
    return result


def score_speaker_attributed_transcripts(
    reference_by_speaker: Mapping[str, str],
    hypothesis_by_speaker: Mapping[str, str],
) -> dict[str, object]:
    """Compute cpWER without changing anonymous labels in stored predictions."""

    references = sorted((str(key), str(value)) for key, value in reference_by_speaker.items())
    hypotheses = sorted((str(key), str(value)) for key, value in hypothesis_by_speaker.items())
    if not references:
        raise DiarizationEvaluationError("cpWER requires at least one reference speaker")
    ref_count, hyp_count = len(references), len(hypotheses)
    size = ref_count + hyp_count
    large = 10**12
    costs = [[large for _ in range(size)] for _ in range(size)]
    for ref_index, (_ref_label, ref_text) in enumerate(references):
        for hyp_index, (_hyp_label, hyp_text) in enumerate(hypotheses):
            costs[ref_index][hyp_index] = compute_wer(ref_text, hyp_text).errors
        for dummy in range(ref_count):
            costs[ref_index][hyp_count + dummy] = (
                len(ref_text.split()) if dummy == ref_index else large
            )
    for hyp_dummy in range(hyp_count):
        row_index = ref_count + hyp_dummy
        for hyp_index, (_hyp_label, hyp_text) in enumerate(hypotheses):
            costs[row_index][hyp_index] = (
                len(hyp_text.split()) if hyp_index == hyp_dummy else large
            )
        for dummy in range(ref_count):
            costs[row_index][hyp_count + dummy] = 0
    assignments = _minimum_assignment(costs)
    errors = int(sum(costs[row][column] for row, column in assignments))
    reference_words = sum(len(text.split()) for _label, text in references)
    return {
        "schema_version": "speaker-attributed-wer.v1",
        "metric": "cpWER",
        "cpwer": errors / reference_words if reference_words else (0.0 if errors == 0 else 1.0),
        "errors": errors,
        "reference_words": reference_words,
        "reference_speakers": ref_count,
        "hypothesis_speakers": hyp_count,
        "permutation_aware": True,
        "stored_labels_rewritten": False,
    }


def _score_mode(
    reference: Sequence[RttmTurn],
    hypothesis: Sequence[RttmTurn],
    uem: Sequence[UemRegion],
    *,
    collar_sec: float,
    overlap_excluded: bool,
) -> dict[str, object]:
    atoms = _atomic_scored_intervals(
        reference,
        hypothesis,
        uem,
        collar_sec=collar_sec,
        overlap_excluded=overlap_excluded,
    )
    denominator = sum(len(ref_labels) * duration for duration, ref_labels, _ in atoms)
    if denominator <= 0:
        return {
            "valid": False,
            "reason": "no reference speaker-time remains after UEM, collar, and overlap policy",
        }
    ref_labels = sorted({label for _duration, labels, _hyp in atoms for label in labels})
    hyp_labels = sorted({label for _duration, _ref, labels in atoms for label in labels})
    overlap_matrix = [
        [
            sum(
                duration
                for duration, active_ref, active_hyp in atoms
                if ref_label in active_ref and hyp_label in active_hyp
            )
            for hyp_label in hyp_labels
        ]
        for ref_label in ref_labels
    ]
    mapping = _maximum_overlap_mapping(ref_labels, hyp_labels, overlap_matrix)
    missed = false_alarm = confusion = 0.0
    for duration, active_ref, active_hyp in atoms:
        mapped_hyp = {mapping[label] for label in active_hyp if label in mapping}
        correct = len(active_ref & mapped_hyp)
        shared = min(len(active_ref), len(active_hyp))
        confusion += max(0, shared - correct) * duration
        missed += max(0, len(active_ref) - shared) * duration
        false_alarm += max(0, len(active_hyp) - shared) * duration
    jer = _jaccard_error(ref_labels, hyp_labels, atoms, mapping)
    consistency = _anonymous_consistency(ref_labels, hyp_labels, overlap_matrix, atoms)
    return {
        "valid": True,
        "der": (missed + false_alarm + confusion) / denominator,
        "jer": jer,
        "missed_speech_sec": missed,
        "false_alarm_sec": false_alarm,
        "speaker_confusion_sec": confusion,
        "reference_speaker_time_sec": denominator,
        "anonymous_label_consistency": consistency,
        "reference_speaker_count": len(ref_labels),
        "hypothesis_speaker_count": len(hyp_labels),
        "scoring_mapping_pair_count": len(mapping),
        "evaluated_atomic_interval_count": len(atoms),
        "overlap_policy": "excluded" if overlap_excluded else "aware",
    }


def _atomic_scored_intervals(
    reference: Sequence[RttmTurn],
    hypothesis: Sequence[RttmTurn],
    uem: Sequence[UemRegion],
    *,
    collar_sec: float,
    overlap_excluded: bool,
) -> list[tuple[float, set[str], set[str]]]:
    output: list[tuple[float, set[str], set[str]]] = []
    recording_channels = sorted({(region.recording_id, region.channel) for region in uem})
    for recording_id, channel in recording_channels:
        ref = [
            turn
            for turn in reference
            if turn.recording_id == recording_id and turn.channel == channel
        ]
        hyp = [
            turn
            for turn in hypothesis
            if turn.recording_id == recording_id and turn.channel == channel
        ]
        regions = [
            region
            for region in uem
            if region.recording_id == recording_id and region.channel == channel
        ]
        collar_intervals = [
            (max(0.0, boundary - collar_sec), boundary + collar_sec)
            for turn in ref
            for boundary in (turn.start_sec, turn.end_sec)
            if collar_sec > 0
        ]
        boundaries = {
            boundary
            for region in regions
            for boundary in (region.start_sec, region.end_sec)
        }
        boundaries.update(
            boundary for turn in (*ref, *hyp) for boundary in (turn.start_sec, turn.end_sec)
        )
        boundaries.update(boundary for interval in collar_intervals for boundary in interval)
        ordered = sorted(boundaries)
        for start, end in zip(ordered, ordered[1:], strict=False):
            if end <= start:
                continue
            midpoint = (start + end) / 2.0
            if not any(region.start_sec <= midpoint < region.end_sec for region in regions):
                continue
            if any(left <= midpoint < right for left, right in collar_intervals):
                continue
            active_ref = {
                turn.speaker_label for turn in ref if turn.start_sec <= midpoint < turn.end_sec
            }
            if overlap_excluded and len(active_ref) > 1:
                continue
            active_hyp = {
                turn.speaker_label for turn in hyp if turn.start_sec <= midpoint < turn.end_sec
            }
            output.append((end - start, active_ref, active_hyp))
    return output


def _maximum_overlap_mapping(
    ref_labels: Sequence[str],
    hyp_labels: Sequence[str],
    overlap_matrix: Sequence[Sequence[float]],
) -> dict[str, str]:
    if not ref_labels or not hyp_labels:
        return {}
    size = max(len(ref_labels), len(hyp_labels))
    maximum = max((value for row in overlap_matrix for value in row), default=0.0)
    costs = [[maximum for _ in range(size)] for _ in range(size)]
    for ref_index, row in enumerate(overlap_matrix):
        for hyp_index, value in enumerate(row):
            costs[ref_index][hyp_index] = maximum - value
    assignments = _minimum_assignment(costs)
    mapping: dict[str, str] = {}
    for ref_index, hyp_index in assignments:
        if ref_index >= len(ref_labels) or hyp_index >= len(hyp_labels):
            continue
        if overlap_matrix[ref_index][hyp_index] > 0:
            mapping[hyp_labels[hyp_index]] = ref_labels[ref_index]
    return mapping


def _minimum_assignment(costs: Sequence[Sequence[float]]) -> list[tuple[int, int]]:
    if not costs:
        return []
    row_count, column_count = len(costs), len(costs[0])
    if any(len(row) != column_count for row in costs) or row_count != column_count:
        raise DiarizationEvaluationError("assignment cost matrix must be square")
    try:
        from scipy.optimize import linear_sum_assignment

        rows, columns = linear_sum_assignment(costs)
        return [(int(row), int(column)) for row, column in zip(rows, columns, strict=True)]
    except ImportError:
        if row_count > 12:
            raise DiarizationEvaluationError(
                "SciPy is required to align more than 12 diarization speakers"
            )
        states: dict[int, tuple[float, tuple[int, ...]]] = {0: (0.0, ())}
        for row_index in range(row_count):
            updated: dict[int, tuple[float, tuple[int, ...]]] = {}
            for mask, (total, columns) in states.items():
                for column in range(column_count):
                    if mask & (1 << column):
                        continue
                    next_mask = mask | (1 << column)
                    candidate = (total + float(costs[row_index][column]), columns + (column,))
                    existing = updated.get(next_mask)
                    if existing is None or candidate < existing:
                        updated[next_mask] = candidate
            states = updated
        _cost, columns = min(states.values())
        return list(enumerate(columns))


def _jaccard_error(
    ref_labels: Sequence[str],
    hyp_labels: Sequence[str],
    atoms: Sequence[tuple[float, set[str], set[str]]],
    mapping: Mapping[str, str],
) -> float:
    inverse = {ref: hyp for hyp, ref in mapping.items()}
    errors: list[float] = []
    for ref_label in ref_labels:
        hyp_label = inverse.get(ref_label)
        intersection = sum(
            duration
            for duration, active_ref, active_hyp in atoms
            if ref_label in active_ref and hyp_label is not None and hyp_label in active_hyp
        )
        union = sum(
            duration
            for duration, active_ref, active_hyp in atoms
            if ref_label in active_ref or (hyp_label is not None and hyp_label in active_hyp)
        )
        errors.append(1.0 - intersection / union if union > 0 else 1.0)
    return sum(errors) / len(errors)


def _anonymous_consistency(
    ref_labels: Sequence[str],
    hyp_labels: Sequence[str],
    overlap_matrix: Sequence[Sequence[float]],
    atoms: Sequence[tuple[float, set[str], set[str]]],
) -> float:
    total = sum(len(active_ref) * duration for duration, active_ref, _hyp in atoms)
    if total <= 0:
        return 0.0
    stable = 0.0
    for ref_index, ref_label in enumerate(ref_labels):
        ref_time = sum(duration for duration, active_ref, _ in atoms if ref_label in active_ref)
        best = max(overlap_matrix[ref_index], default=0.0) if hyp_labels else 0.0
        stable += min(ref_time, best)
    return stable / total


def _regions_by_key(
    uem: Sequence[UemRegion],
) -> dict[tuple[str, str], list[UemRegion]]:
    output: dict[tuple[str, str], list[UemRegion]] = {}
    for region in uem:
        output.setdefault((region.recording_id, region.channel), []).append(region)
    return output


def _overlaps_any(turn: RttmTurn, regions: Iterable[UemRegion]) -> bool:
    return any(min(turn.end_sec, region.end_sec) > max(turn.start_sec, region.start_sec) for region in regions)


def _contained_by_any(turn: RttmTurn, regions: Iterable[UemRegion]) -> bool:
    return any(
        region.start_sec <= turn.start_sec and turn.end_sec <= region.end_sec
        for region in regions
    )
