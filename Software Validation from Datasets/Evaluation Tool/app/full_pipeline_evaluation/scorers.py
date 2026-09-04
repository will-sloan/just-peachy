"""Scientifically explicit scorers for the frozen full-pipeline V1 views.

These functions are intentionally pure and model-free.  They consume bounded
JSON-like records, never infer unavailable ground truth, and always return a
complete :class:`~app.full_pipeline_evaluation.metrics.MetricReport` whose
unsupported values explain the missing prerequisite.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.full_pipeline_evaluation.metrics import (
    MetricReport,
    MetricValue,
    build_metric_report,
    computed_metric,
    undefined_metric,
    unsupported_metric,
)


JsonRecord = Mapping[str, object]

CPWER_NORMALIZATION_ID = "lowercase_whitespace.v1"
CPWER_PERMUTATION_SCOPE_ID = "per_recording"


@dataclass(frozen=True)
class AsrUtterance:
    """One attempted ASR utterance; ``None`` means no hypothesis was produced."""

    reference_text: str
    hypothesis_text: str | None
    output_failed: bool = False
    utterance_id: str | None = None


@dataclass(frozen=True)
class DiarizationSegment:
    """A half-open ``[start_sec, end_sec)`` speaker interval."""

    start_sec: float
    end_sec: float
    speaker_id: str


@dataclass(frozen=True)
class ReentryEpisode:
    """One protocol-annotated return of the same reference speaker."""

    episode_id: str
    reference_speaker_id: str
    before_hypothesis_speaker_id: str | None
    after_hypothesis_speaker_id: str | None


@dataclass(frozen=True)
class LongStreamCase:
    """One declared long-stream completion/failure outcome."""

    case_id: str
    expected_duration_sec: float
    final_emitted: bool
    reset_count: int = 0
    stall_count: int = 0
    failure_count: int = 0


@dataclass(frozen=True)
class AttributionInterval:
    """One constant-reference/constant-decision attribution interval.

    ``reference_is_known`` is deliberately explicit: a persistent ground-truth
    stranger ID is not an enrolled identity.  ``decision_state`` is one of
    confirmed_known, tentative_known, generic_known, unknown, or uncovered.
    """

    start_sec: float
    end_sec: float
    reference_speaker_id: str
    reference_is_known: bool
    predicted_speaker_id: str | None = None
    decision_state: str = "unknown"
    predicted_unknown_label: str | None = None
    episode_id: str | None = None
    temperature: str | None = None
    stable_name_latency_sec: float | None = None
    identity_revision_count: int | None = None

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True)
class SpeakerTranscriptPrerequisites:
    """Evidence gate for cpWER and identity-bound speaker-attributed WER."""

    reference_streams_complete: bool
    hypothesis_streams_complete: bool
    normalization_id: str | None
    permutation_scope: str | None
    identities_comparable: bool = False
    identity_mapping_id: str | None = None
    word_alignment_id: str | None = None


@dataclass(frozen=True)
class WordAlignment:
    """One externally aligned reference/hypothesis word pair.

    Either word may be ``None`` for a deletion/insertion.  The scorer does not
    manufacture word alignment from time spans because that requires a frozen
    alignment policy.
    """

    reference_word: str | None
    hypothesis_word: str | None
    reference_speaker_id: str | None
    hypothesis_speaker_id: str | None
    reference_duration_sec: float | None = None


def score_asr(
    utterances: Sequence[AsrUtterance | JsonRecord] | None,
) -> MetricReport:
    """Score corpus-micro WER/CER and output failure rate.

    A failed or missing hypothesis is treated as empty for error counts while
    also contributing to ``output_failure_rate``.  This prevents failed output
    from disappearing from accuracy denominators.
    """

    if utterances is None:
        return build_metric_report("asr", (), missing_reason="ASR attempts absent")
    rows = tuple(_asr_utterance(value) for value in utterances)
    word_counts = [0, 0, 0, 0]  # errors, substitutions, deletions, insertions
    reference_words = 0
    character_errors = 0
    reference_characters = 0
    failures = 0
    for row in rows:
        reference = _normalize_text(row.reference_text)
        hypothesis = _normalize_text(
            "" if row.output_failed else (row.hypothesis_text or "")
        )
        counts = _word_edit_counts(reference.split(), hypothesis.split())
        word_counts = [left + right for left, right in zip(word_counts, counts)]
        reference_words += len(reference.split())
        ref_chars = reference.replace(" ", "")
        hyp_chars = hypothesis.replace(" ", "")
        character_errors += _edit_distance(tuple(ref_chars), tuple(hyp_chars))
        reference_characters += len(ref_chars)
        failures += int(row.output_failed or row.hypothesis_text is None)

    values: list[MetricValue] = [
        computed_metric("substitutions", word_counts[1]),
        computed_metric("deletions", word_counts[2]),
        computed_metric("insertions", word_counts[3]),
        computed_metric("output_failure_count", failures),
    ]
    if reference_words:
        values.append(
            computed_metric(
                "wer",
                word_counts[0] / reference_words,
                numerator=word_counts[0],
                denominator=reference_words,
                details={"normalization_id": "lowercase_whitespace.v1"},
            )
        )
    else:
        values.append(
            undefined_metric(
                "wer",
                "no reference words in the scored corpus",
                numerator=word_counts[0],
                denominator=0,
            )
        )
    if reference_characters:
        values.append(
            computed_metric(
                "cer",
                character_errors / reference_characters,
                numerator=character_errors,
                denominator=reference_characters,
                details={"normalization_id": "lowercase_whitespace_no_spaces.v1"},
            )
        )
    else:
        values.append(
            undefined_metric(
                "cer",
                "no reference characters in the scored corpus",
                numerator=character_errors,
                denominator=0,
            )
        )
    if rows:
        values.append(
            computed_metric(
                "output_failure_rate",
                failures / len(rows),
                numerator=failures,
                denominator=len(rows),
            )
        )
    else:
        values.append(
            undefined_metric(
                "output_failure_rate",
                "no attempted utterances",
                numerator=0,
                denominator=0,
            )
        )
    return build_metric_report("asr", values)


def score_streaming(
    events: Sequence[JsonRecord] | None,
    *,
    reference_text_by_hypothesis: Mapping[str, str] | None = None,
    readable_min_words: int = 2,
    stream_start_monotonic_ns: int | None = None,
    long_stream_cases: Sequence[LongStreamCase | JsonRecord] | None = None,
) -> MetricReport:
    """Score ordered native/public streaming-ASR event records."""

    if readable_min_words < 1:
        raise ValueError("readable_min_words must be >= 1")
    if events is None:
        return build_metric_report(
            "streaming", (), missing_reason="streaming ASR events absent"
        )
    timing_baseline_ns = _resolve_stream_start_monotonic_ns(
        events, explicit=stream_start_monotonic_ns
    )
    ordered = tuple(sorted(events, key=_event_sort_key))
    partials = tuple(row for row in ordered if _is_partial(row))
    finals = tuple(row for row in ordered if _is_final(row))
    values: list[MetricValue] = []

    nonempty = [row for row in partials if _event_text(row)]
    readable = [
        row
        for row in partials
        if len(_normalize_text(_event_text(row)).split()) >= readable_min_words
    ]
    values.append(
        _minimum_elapsed_metric(
            "first_nonempty_partial_latency_sec",
            nonempty,
            "no non-empty partial hypothesis was emitted",
            stream_start_monotonic_ns=timing_baseline_ns,
        )
    )
    readable_value = _minimum_elapsed_metric(
        "first_readable_partial_latency_sec",
        readable,
        f"no partial reached readable_min_words={readable_min_words}",
        stream_start_monotonic_ns=timing_baseline_ns,
    )
    if readable_value.status == "computed":
        readable_value = computed_metric(
            "first_readable_partial_latency_sec",
            float(readable_value.value),
            details={"readable_min_words": readable_min_words},
        )
    values.append(readable_value)
    stable = [
        row
        for row in ordered
        if _optional_int(row.get("stable_prefix_token_count"), 0) > 0
    ]
    values.append(
        _minimum_elapsed_metric(
            "stable_prefix_latency_sec",
            stable,
            "stable-prefix token telemetry absent or never non-empty",
            stream_start_monotonic_ns=timing_baseline_ns,
        )
    )

    finalization_seconds = [
        value for row in finals if (value := _finalization_latency_sec(row)) is not None
    ]
    if finalization_seconds:
        values.append(
            computed_metric(
                "endpoint_to_final_latency_sec",
                _mean(finalization_seconds),
                numerator=sum(finalization_seconds),
                denominator=len(finalization_seconds),
                details={"paired_final_count": len(finalization_seconds)},
            )
        )
    else:
        values.append(
            unsupported_metric(
                "endpoint_to_final_latency_sec",
                "no endpoint/final pair or backend finalization interval",
            )
        )

    grouped = _group_hypotheses(partials)
    revision_count = 0
    churn_errors = 0
    churn_denominator = 0
    word_transition_count = 0
    token_churn_errors = 0
    token_churn_denominator = 0
    token_transition_count = 0
    missing_token_transition = False
    for rows in grouped.values():
        previous: tuple[str, ...] | None = None
        previous_tokens: tuple[str, ...] | None = None
        for row in rows:
            current = _event_words(row)
            if previous is not None:
                word_transition_count += 1
                revision_count += int(current != previous)
                churn_errors += _edit_distance(previous, current)
                churn_denominator += max(1, len(previous))
            raw_tokens = row.get("tokens")
            current_tokens = (
                tuple(str(value) for value in raw_tokens)
                if isinstance(raw_tokens, Sequence)
                and not isinstance(raw_tokens, (str, bytes, bytearray))
                else None
            )
            if previous is not None:
                if previous_tokens is None or current_tokens is None:
                    missing_token_transition = True
                else:
                    token_transition_count += 1
                    token_churn_errors += _edit_distance(
                        previous_tokens, current_tokens
                    )
                    token_churn_denominator += max(1, len(previous_tokens))
            previous = current
            previous_tokens = current_tokens
    audio_duration = _stream_audio_duration(ordered)
    if audio_duration is None or audio_duration <= 0:
        values.append(
            unsupported_metric(
                "partial_revision_rate_per_minute",
                "consumed audio duration unavailable",
            )
        )
    else:
        values.append(
            computed_metric(
                "partial_revision_rate_per_minute",
                revision_count / (audio_duration / 60.0),
                numerator=revision_count,
                denominator=audio_duration / 60.0,
            )
        )
    if word_transition_count:
        values.append(
            computed_metric(
                "word_churn_rate",
                churn_errors / churn_denominator,
                numerator=churn_errors,
                denominator=churn_denominator,
            )
        )
    else:
        values.append(
            unsupported_metric(
                "word_churn_rate",
                "no consecutive partial hypotheses within one hypothesis stream",
            )
        )
    if missing_token_transition:
        values.append(
            unsupported_metric(
                "token_churn_rate",
                "one or more partial transitions lack backend-emitted token arrays",
            )
        )
    elif token_transition_count:
        values.append(
            computed_metric(
                "token_churn_rate",
                token_churn_errors / token_churn_denominator,
                numerator=token_churn_errors,
                denominator=token_churn_denominator,
            )
        )
    else:
        values.append(
            unsupported_metric(
                "token_churn_rate", "no consecutive partials with emitted token arrays"
            )
        )

    if reference_text_by_hypothesis is None:
        values.append(
            unsupported_metric(
                "final_wer", "matching final reference transcripts absent"
            )
        )
    else:
        final_by_id = {_hypothesis_key(row): row for row in finals}
        asr_rows = [
            AsrUtterance(reference, _event_text(final_by_id[key]))
            for key, reference in reference_text_by_hypothesis.items()
            if key in final_by_id
        ]
        if len(asr_rows) != len(reference_text_by_hypothesis):
            values.append(
                unsupported_metric(
                    "final_wer",
                    "one or more reference hypotheses have no final event",
                )
            )
        else:
            asr = score_asr(asr_rows)["wer"]
            values.append(
                computed_metric(
                    "final_wer",
                    float(asr.value),
                    numerator=asr.numerator,
                    denominator=asr.denominator,
                )
                if asr.status == "computed"
                else undefined_metric(
                    "final_wer",
                    asr.reason or "final WER denominator is zero",
                    numerator=asr.numerator,
                    denominator=asr.denominator,
                )
            )

    declared_long_cases = (
        tuple(_long_stream_case(value) for value in long_stream_cases)
        if long_stream_cases is not None
        else ()
    )
    if declared_long_cases:
        stable_count = sum(
            row.final_emitted
            and row.reset_count == 0
            and row.stall_count == 0
            and row.failure_count == 0
            for row in declared_long_cases
        )
        values.append(
            computed_metric(
                "long_stream_stability_rate",
                stable_count / len(declared_long_cases),
                numerator=stable_count,
                denominator=len(declared_long_cases),
                details={
                    "case_ids": [row.case_id for row in declared_long_cases],
                    "minimum_expected_duration_sec": min(
                        row.expected_duration_sec for row in declared_long_cases
                    ),
                },
            )
        )
    else:
        long_cases = [row for row in ordered if row.get("is_long_stream") is True]
    if not declared_long_cases and long_cases:
        case_states: dict[str, dict[str, bool]] = {}
        for row in long_cases:
            key = str(row.get("case_id") or row.get("stream_id") or "default")
            failed = bool(row.get("failed")) or str(row.get("status")) in {
                "failed",
                "stalled",
            }
            completed = bool(row.get("completed")) or _is_final(row)
            state = case_states.setdefault(key, {"completed": False, "failed": False})
            state["completed"] = state["completed"] or completed
            state["failed"] = state["failed"] or failed
        completed_count = sum(
            state["completed"] and not state["failed"] for state in case_states.values()
        )
        values.append(
            computed_metric(
                "long_stream_stability_rate",
                completed_count / len(case_states),
                numerator=completed_count,
                denominator=len(case_states),
            )
        )
    elif not declared_long_cases:
        values.append(
            unsupported_metric(
                "long_stream_stability_rate", "no protocol-declared long-stream cases"
            )
        )
    return build_metric_report("streaming", values)


def score_anonymous_diarization(
    reference_segments: Sequence[DiarizationSegment | JsonRecord] | None,
    hypothesis_segments: Sequence[DiarizationSegment | JsonRecord] | None,
    *,
    uem: Sequence[tuple[float, float]] | None = None,
    collar_sec: float = 0.0,
    score_overlap: bool = True,
    short_turn_max_duration_sec: float | None = None,
    score_standard_short_turn_bins: bool = False,
    reentry_episodes: Sequence[ReentryEpisode | JsonRecord] | None = None,
) -> MetricReport:
    """Score anonymous diarization with exact atomic-interval accounting.

    The one-to-one speaker mapping maximizes overlap for DER and maximizes
    Jaccard similarity for JER.  A collar excludes time within ``collar_sec``
    of every reference segment boundary.  When ``score_overlap`` is false,
    atomic regions containing more than one reference speaker are excluded.
    """

    if reference_segments is None or hypothesis_segments is None:
        return build_metric_report(
            "diarization",
            (),
            missing_reason="reference and hypothesis diarization segments required",
        )
    if collar_sec < 0:
        raise ValueError("collar_sec must be >= 0")
    references = tuple(_diarization_segment(value) for value in reference_segments)
    hypotheses = tuple(_diarization_segment(value) for value in hypothesis_segments)
    _validate_segments(references, "reference")
    _validate_segments(hypotheses, "hypothesis")
    atoms = _diarization_atoms(
        references,
        hypotheses,
        uem=uem,
        collar_sec=collar_sec,
        score_overlap=score_overlap,
    )
    ref_speakers = sorted({speaker for _, ref, _ in atoms for speaker in ref})
    hyp_speakers = sorted({speaker for _, _, hyp in atoms for speaker in hyp})
    overlap = _speaker_overlap_matrix(atoms, ref_speakers, hyp_speakers)
    mapping = _maximum_matrix_mapping(overlap, ref_speakers, hyp_speakers)

    miss = false_alarm = confusion = denominator = 0.0
    for duration, ref_active, hyp_active in atoms:
        denominator += duration * len(ref_active)
        miss += duration * max(0, len(ref_active) - len(hyp_active))
        false_alarm += duration * max(0, len(hyp_active) - len(ref_active))
        matched_correct = sum(
            1 for hyp_speaker in hyp_active if mapping.get(hyp_speaker) in ref_active
        )
        confusion += duration * (
            min(len(ref_active), len(hyp_active)) - matched_correct
        )
    policy = {
        "collar_sec": collar_sec,
        "score_overlap": score_overlap,
        "uem_provided": uem is not None,
        "speaker_mapping": mapping,
        "scored_reference_speaker_time_sec": denominator,
    }
    values: list[MetricValue] = []
    if denominator > 0:
        for metric_id, numerator in (
            ("miss_rate", miss),
            ("false_alarm_rate", false_alarm),
            ("speaker_confusion_rate", confusion),
            ("der", miss + false_alarm + confusion),
        ):
            values.append(
                computed_metric(
                    metric_id,
                    numerator / denominator,
                    numerator=numerator,
                    denominator=denominator,
                    details=policy,
                )
            )
    else:
        for metric_id in (
            "miss_rate",
            "false_alarm_rate",
            "speaker_confusion_rate",
            "der",
        ):
            values.append(
                undefined_metric(
                    metric_id,
                    "scored reference speaker-time is zero",
                    numerator=0.0,
                    denominator=0.0,
                )
            )

    values.append(_jer_metric(atoms, ref_speakers, hyp_speakers))
    values.append(
        computed_metric(
            "speaker_count_error",
            len(hyp_speakers) - len(ref_speakers),
            details={
                "reference_speaker_count": len(ref_speakers),
                "hypothesis_speaker_count": len(hyp_speakers),
            },
        )
    )
    values.append(
        _boundary_delay_metric(
            references,
            hypotheses,
            mapping,
            atoms,
            uem=uem,
            collar_sec=collar_sec,
        )
    )
    fragment_counts = [
        max(
            0,
            sum(
                overlap[ref_index, hyp_index] > 0
                for hyp_index in range(len(hyp_speakers))
            )
            - 1,
        )
        for ref_index in range(len(ref_speakers))
    ]
    if ref_speakers:
        values.append(
            computed_metric(
                "fragmentation_per_reference_speaker",
                sum(fragment_counts) / len(fragment_counts),
                numerator=sum(fragment_counts),
                denominator=len(fragment_counts),
            )
        )
    else:
        values.append(
            undefined_metric(
                "fragmentation_per_reference_speaker",
                "no scored reference speakers",
                numerator=0,
                denominator=0,
            )
        )
    total_overlap = float(overlap.sum())
    contamination = sum(
        float(overlap[:, index].sum() - overlap[:, index].max(initial=0.0))
        for index in range(len(hyp_speakers))
    )
    if total_overlap > 0:
        values.append(
            computed_metric(
                "merge_contamination_rate",
                contamination / total_overlap,
                numerator=contamination,
                denominator=total_overlap,
            )
        )
    else:
        values.append(
            undefined_metric(
                "merge_contamination_rate",
                "reference/hypothesis speaker overlap is zero",
                numerator=0.0,
                denominator=0.0,
            )
        )
    if short_turn_max_duration_sec is None:
        values.append(
            unsupported_metric(
                "short_turn_der",
                "no frozen short-turn maximum duration supplied",
            )
        )
    elif short_turn_max_duration_sec <= 0:
        raise ValueError("short_turn_max_duration_sec must be > 0")
    else:
        short_regions = [
            (segment.start_sec, segment.end_sec)
            for segment in references
            if segment.end_sec - segment.start_sec <= short_turn_max_duration_sec
        ]
        short_regions = _intersect_regions(short_regions, uem)
        if not short_regions:
            values.append(
                undefined_metric(
                    "short_turn_der",
                    "no reference turns satisfy the frozen short-turn threshold",
                    numerator=0.0,
                    denominator=0.0,
                )
            )
        else:
            short_report = score_anonymous_diarization(
                references,
                hypotheses,
                uem=short_regions,
                collar_sec=collar_sec,
                score_overlap=score_overlap,
            )
            short_der = short_report["der"]
            if short_der.status == "computed":
                values.append(
                    computed_metric(
                        "short_turn_der",
                        float(short_der.value),
                        numerator=short_der.numerator,
                        denominator=short_der.denominator,
                        details={
                            "short_turn_max_duration_sec": short_turn_max_duration_sec,
                            "short_turn_region_count": len(short_regions),
                        },
                    )
                )
            else:
                values.append(
                    undefined_metric(
                        "short_turn_der",
                        short_der.reason or "short-turn DER is undefined",
                        numerator=short_der.numerator,
                        denominator=short_der.denominator,
                    )
                )
    if score_standard_short_turn_bins:
        values.extend(
            _standard_short_turn_der_metrics(
                references,
                hypotheses,
                uem=uem,
                collar_sec=collar_sec,
                score_overlap=score_overlap,
            )
        )
    if reentry_episodes is None:
        values.append(
            unsupported_metric(
                "reentry_accuracy", "no protocol re-entry episode annotations supplied"
            )
        )
    else:
        episodes = tuple(_reentry_episode(value) for value in reentry_episodes)
        if not episodes:
            values.append(
                undefined_metric(
                    "reentry_accuracy",
                    "the supplied re-entry annotation set is empty",
                    numerator=0,
                    denominator=0,
                )
            )
        else:
            if len({row.episode_id for row in episodes}) != len(episodes):
                raise ValueError("re-entry episode IDs must be unique")
            correct_reentries = sum(
                row.before_hypothesis_speaker_id is not None
                and row.before_hypothesis_speaker_id == row.after_hypothesis_speaker_id
                and mapping.get(row.before_hypothesis_speaker_id)
                == row.reference_speaker_id
                for row in episodes
            )
            values.append(
                computed_metric(
                    "reentry_accuracy",
                    correct_reentries / len(episodes),
                    numerator=correct_reentries,
                    denominator=len(episodes),
                )
            )
    return build_metric_report("diarization", values)


def _standard_short_turn_der_metrics(
    references: Sequence[DiarizationSegment],
    hypotheses: Sequence[DiarizationSegment],
    *,
    uem: Sequence[tuple[float, float]] | None,
    collar_sec: float,
    score_overlap: bool,
) -> tuple[MetricValue, ...]:
    """Return the three predeclared H2 short-turn duration-bin DERs."""

    definitions = (
        ("short_turn_der_lt_0_5_sec", 0.0, 0.5, False),
        ("short_turn_der_0_5_to_1_0_sec", 0.5, 1.0, False),
        ("short_turn_der_1_0_to_2_0_sec", 1.0, 2.0, True),
    )
    values: list[MetricValue] = []
    for metric_id, lower_sec, upper_sec, include_upper in definitions:
        selected = [
            segment
            for segment in references
            if segment.end_sec - segment.start_sec >= lower_sec
            and (
                segment.end_sec - segment.start_sec <= upper_sec
                if include_upper
                else segment.end_sec - segment.start_sec < upper_sec
            )
        ]
        regions = _intersect_regions(
            [(segment.start_sec, segment.end_sec) for segment in selected],
            uem,
        )
        details = {
            "duration_lower_sec_inclusive": lower_sec,
            "duration_upper_sec": upper_sec,
            "duration_upper_inclusive": include_upper,
            "short_turn_region_count": len(regions),
        }
        if not regions:
            values.append(
                undefined_metric(
                    metric_id,
                    "no reference turns satisfy the frozen duration bin",
                    numerator=0.0,
                    denominator=0.0,
                    details=details,
                )
            )
            continue
        report = score_anonymous_diarization(
            references,
            hypotheses,
            uem=regions,
            collar_sec=collar_sec,
            score_overlap=score_overlap,
        )
        der = report["der"]
        if der.status == "computed":
            values.append(
                computed_metric(
                    metric_id,
                    float(der.value),
                    numerator=der.numerator,
                    denominator=der.denominator,
                    details=details,
                )
            )
        else:
            values.append(
                undefined_metric(
                    metric_id,
                    der.reason or "duration-bin DER is undefined",
                    numerator=der.numerator,
                    denominator=der.denominator,
                    details=details,
                )
            )
    return tuple(values)


def attribution_intervals_from_prompt1_events(
    identity_events: Sequence[JsonRecord],
    reference_intervals: Sequence[JsonRecord],
) -> tuple[AttributionInterval, ...]:
    """Join Prompt-1 identity transitions to time-aligned reference intervals.

    Every reference interval must declare ``anonymous_speaker_id``, timing,
    ``reference_speaker_id``, and the explicit ``reference_is_known`` flag.
    Prompt-1 states (confirmed/tentative/unknown) and nested speaker-label
    contracts are normalized without treating raw similarity as probability.
    Before the first transition for a track, the decision is conservatively
    Unknown.  A transition at time ``t`` applies from ``t`` onward.
    """

    events_by_speaker: dict[str, list[tuple[float, int, JsonRecord]]] = defaultdict(
        list
    )
    for event in identity_events:
        if str(event.get("event_type")) not in {"identity_label", ""}:
            continue
        speaker = _optional_text(event.get("anonymous_speaker_id"))
        source_time = _identity_event_source_time(event)
        if speaker is None or source_time is None:
            raise ValueError(
                "Prompt-1 identity events require anonymous_speaker_id and "
                "capture_timestamps.audio_end_sec"
            )
        events_by_speaker[speaker].append(
            (source_time, _optional_int(event.get("event_sequence"), 0), event)
        )
    for rows in events_by_speaker.values():
        rows.sort(key=lambda value: (value[0], value[1]))

    output: list[AttributionInterval] = []
    for reference in reference_intervals:
        start = _optional_float(reference.get("start_sec"))
        end = _optional_float(reference.get("end_sec"))
        anonymous_speaker_id = _optional_text(reference.get("anonymous_speaker_id"))
        reference_speaker_id = _optional_text(reference.get("reference_speaker_id"))
        if (
            start is None
            or end is None
            or end <= start
            or anonymous_speaker_id is None
            or reference_speaker_id is None
            or "reference_is_known" not in reference
            or not isinstance(reference.get("reference_is_known"), bool)
        ):
            raise ValueError(
                "reference intervals require valid timing, anonymous_speaker_id, "
                "reference_speaker_id, and reference_is_known"
            )
        transitions = events_by_speaker.get(anonymous_speaker_id, [])
        change_times = sorted(
            {time for time, _, _ in transitions if start < time < end}
        )
        boundaries = (start, *change_times, end)
        for interval_start, interval_end in zip(boundaries, boundaries[1:]):
            active = [
                (time, sequence, event)
                for time, sequence, event in transitions
                if time <= interval_start
            ]
            event = max(active, default=None, key=lambda value: (value[0], value[1]))
            state, predicted_id, unknown_label = (
                _prompt1_identity_decision(event[2])
                if event is not None
                else ("unknown", None, None)
            )
            output.append(
                AttributionInterval(
                    start_sec=interval_start,
                    end_sec=interval_end,
                    reference_speaker_id=reference_speaker_id,
                    reference_is_known=bool(reference["reference_is_known"]),
                    predicted_speaker_id=predicted_id,
                    decision_state=state,
                    predicted_unknown_label=unknown_label,
                    episode_id=_optional_text(
                        reference.get("episode_id") or reference.get("probe_id")
                    ),
                    temperature=_optional_text(reference.get("temperature")),
                )
            )
    return tuple(sorted(output, key=lambda row: (row.start_sec, row.end_sec)))


def score_known_unknown_attribution(
    intervals: Sequence[AttributionInterval | JsonRecord] | None,
    *,
    identity_events: Sequence[JsonRecord] | None = None,
) -> MetricReport:
    """Score duration-weighted open-set known/unknown attribution."""

    if intervals is None:
        return build_metric_report(
            "identity", (), missing_reason="attribution decision intervals absent"
        )
    rows = tuple(_attribution_interval(value) for value in intervals)
    if any(row.duration_sec < 0 for row in rows):
        raise ValueError("attribution intervals must have end_sec >= start_sec")
    known_time = sum(row.duration_sec for row in rows if row.reference_is_known)
    correct = sum(
        row.duration_sec
        for row in rows
        if row.reference_is_known
        and row.decision_state == "confirmed_known"
        and row.predicted_speaker_id == row.reference_speaker_id
    )
    wrong = sum(
        row.duration_sec
        for row in rows
        if row.reference_is_known
        and row.predicted_speaker_id is not None
        and row.predicted_speaker_id != row.reference_speaker_id
    )
    stranger_false_known = sum(
        row.duration_sec
        for row in rows
        if not row.reference_is_known and row.predicted_speaker_id is not None
    )
    generic = sum(
        row.duration_sec for row in rows if row.decision_state == "generic_known"
    )
    uncovered = sum(
        row.duration_sec
        for row in rows
        if row.reference_is_known and row.decision_state in {"unknown", "uncovered"}
    )
    values: list[MetricValue] = [
        computed_metric("correctly_named_known_time_sec", correct),
        computed_metric("wrong_known_time_sec", wrong),
        computed_metric("stranger_false_known_time_sec", stranger_false_known),
        computed_metric("generic_known_time_sec", generic),
        computed_metric("uncovered_known_time_sec", uncovered),
    ]
    if known_time > 0:
        values.extend(
            (
                computed_metric(
                    "correctly_named_known_rate",
                    correct / known_time,
                    numerator=correct,
                    denominator=known_time,
                ),
            )
        )
    else:
        values.extend(
            (
                undefined_metric(
                    "correctly_named_known_rate",
                    "known-reference duration is zero",
                    numerator=0.0,
                    denominator=0.0,
                ),
            )
        )
    if rows and all(row.episode_id for row in rows):
        episodes: dict[str, list[AttributionInterval]] = defaultdict(list)
        for row in rows:
            episodes[str(row.episode_id)].append(row)
        final_rows: list[AttributionInterval] = []
        consistent = True
        for episode_rows in episodes.values():
            consistent = (
                consistent
                and len(
                    {
                        (row.reference_speaker_id, row.reference_is_known)
                        for row in episode_rows
                    }
                )
                == 1
            )
            final_rows.append(
                max(episode_rows, key=lambda row: (row.end_sec, row.start_sec))
            )
        if not consistent:
            values.extend(
                (
                    unsupported_metric(
                        "fpir", "reference identity changed within an episode"
                    ),
                    unsupported_metric(
                        "fnir", "reference identity changed within an episode"
                    ),
                )
            )
        else:
            unknown_episodes = [row for row in final_rows if not row.reference_is_known]
            known_episodes = [row for row in final_rows if row.reference_is_known]
            if unknown_episodes:
                false_positive = sum(
                    row.predicted_speaker_id is not None for row in unknown_episodes
                )
                values.append(
                    computed_metric(
                        "fpir",
                        false_positive / len(unknown_episodes),
                        numerator=false_positive,
                        denominator=len(unknown_episodes),
                        details={"decision": "last_interval_by_end_time"},
                    )
                )
            else:
                values.append(
                    undefined_metric(
                        "fpir",
                        "no non-mated episodes",
                        numerator=0,
                        denominator=0,
                    )
                )
            if known_episodes:
                failures = sum(
                    row.decision_state != "confirmed_known"
                    or row.predicted_speaker_id != row.reference_speaker_id
                    for row in known_episodes
                )
                values.append(
                    computed_metric(
                        "fnir",
                        failures / len(known_episodes),
                        numerator=failures,
                        denominator=len(known_episodes),
                        details={"decision": "last_interval_by_end_time"},
                    )
                )
            else:
                values.append(
                    undefined_metric(
                        "fnir",
                        "no mated episodes",
                        numerator=0,
                        denominator=0,
                    )
                )
    else:
        reason = "episode_id is required for standard open-set identification rates"
        values.extend(
            (unsupported_metric("fpir", reason), unsupported_metric("fnir", reason))
        )

    unknown_state_rows = [
        row
        for row in rows
        if not row.reference_is_known and row.decision_state == "unknown"
    ]
    # The catalog definition deliberately conditions this metric on duration
    # that actually carries a session-local anonymous label.  Early generic
    # Unknown time before the first Speaker_N/Unknown_N assignment is a UX
    # latency outcome; it must not make consistency unscorable once labelled
    # stranger duration exists.
    unknown_label_rows = [
        row for row in unknown_state_rows if row.predicted_unknown_label
    ]
    if unknown_label_rows and all(
        row.reference_speaker_id for row in unknown_label_rows
    ):
        by_reference: dict[str, Counter[str]] = defaultdict(Counter)
        for row in unknown_label_rows:
            by_reference[row.reference_speaker_id][
                str(row.predicted_unknown_label)
            ] += row.duration_sec
        modal = sum(max(counts.values()) for counts in by_reference.values())
        labelled = sum(sum(counts.values()) for counts in by_reference.values())
        unlabelled = sum(
            row.duration_sec
            for row in unknown_state_rows
            if not row.predicted_unknown_label
        )
        values.append(
            computed_metric(
                "unknown_n_consistency",
                modal / labelled,
                numerator=modal,
                denominator=labelled,
                details={
                    "scope": "unknown_decision_intervals_with_session_label",
                    "unlabelled_unknown_duration_sec": unlabelled,
                },
            )
        )
    else:
        values.append(
            unsupported_metric(
                "unknown_n_consistency",
                "persistent stranger IDs and Unknown_N labels are both required",
            )
        )

    reference_outputs: dict[str, set[str]] = defaultdict(set)
    output_references: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        output = row.predicted_speaker_id or row.predicted_unknown_label
        if not output:
            continue
        reference_outputs[row.reference_speaker_id].add(output)
        output_references[output].add(row.reference_speaker_id)
    split_count = sum(
        max(0, len(outputs) - 1) for outputs in reference_outputs.values()
    )
    merge_count = sum(max(0, len(refs) - 1) for refs in output_references.values())
    values.extend(
        (
            computed_metric("identity_split_count", split_count),
            computed_metric("identity_merge_count", merge_count),
        )
    )
    for temperature, metric_id in (
        ("cold", "cold_identity_accuracy"),
        ("warm", "warm_identity_accuracy"),
    ):
        subset = [
            row
            for row in rows
            if row.reference_is_known and row.temperature == temperature
        ]
        duration = sum(row.duration_sec for row in subset)
        if duration > 0:
            subset_correct = sum(
                row.duration_sec
                for row in subset
                if row.decision_state == "confirmed_known"
                and row.predicted_speaker_id == row.reference_speaker_id
            )
            values.append(
                computed_metric(
                    metric_id,
                    subset_correct / duration,
                    numerator=subset_correct,
                    denominator=duration,
                )
            )
        else:
            values.append(
                unsupported_metric(
                    metric_id, f"no protocol-marked {temperature} intervals"
                )
            )
    latency_rows = [row for row in rows if row.stable_name_latency_sec is not None]
    if latency_rows and all(row.episode_id for row in latency_rows):
        latency_by_episode: dict[str, set[float]] = defaultdict(set)
        for row in latency_rows:
            latency = float(row.stable_name_latency_sec)
            if not math.isfinite(latency) or latency < 0:
                raise ValueError("stable-name latency must be finite and non-negative")
            latency_by_episode[str(row.episode_id)].add(latency)
        inconsistent = sorted(
            episode_id
            for episode_id, episode_latencies in latency_by_episode.items()
            if len(episode_latencies) != 1
        )
        if inconsistent:
            values.append(
                unsupported_metric(
                    "stable_name_latency_sec",
                    "inconsistent stable-name latency within episode(s): "
                    + ", ".join(inconsistent),
                )
            )
        else:
            episode_latencies = [
                next(iter(latency_by_episode[episode_id]))
                for episode_id in sorted(latency_by_episode)
            ]
            values.append(
                computed_metric(
                    "stable_name_latency_sec",
                    _mean(episode_latencies),
                    numerator=sum(episode_latencies),
                    denominator=len(episode_latencies),
                    details={
                        "aggregation": "one_value_per_episode",
                        "episode_count": len(episode_latencies),
                    },
                )
            )
    elif latency_rows:
        values.append(
            unsupported_metric(
                "stable_name_latency_sec",
                "episode_id is required to aggregate stable-name latency once per episode",
            )
        )
    else:
        known_rows = [row for row in rows if row.reference_is_known]
        if not known_rows:
            values.append(
                unsupported_metric(
                    "stable_name_latency_sec", "no known-speaker episodes"
                )
            )
        elif not all(row.episode_id for row in known_rows):
            values.append(
                unsupported_metric(
                    "stable_name_latency_sec",
                    "episode_id is required to derive stable-name latency from "
                    "decision intervals",
                )
            )
        else:
            rows_by_episode: dict[str, list[AttributionInterval]] = defaultdict(list)
            for row in known_rows:
                rows_by_episode[str(row.episode_id)].append(row)
            derived_latencies: list[float] = []
            for episode_id in sorted(rows_by_episode):
                episode = sorted(
                    rows_by_episode[episode_id],
                    key=lambda row: (row.start_sec, row.end_sec),
                )
                episode_start = min(row.start_sec for row in episode)
                for index, row in enumerate(episode):
                    correct_confirmed = (
                        row.decision_state == "confirmed_known"
                        and row.predicted_speaker_id == row.reference_speaker_id
                    )
                    if not correct_confirmed:
                        continue
                    if all(
                        later.decision_state == "confirmed_known"
                        and later.predicted_speaker_id == later.reference_speaker_id
                        for later in episode[index:]
                    ):
                        derived_latencies.append(row.start_sec - episode_start)
                        break
            if derived_latencies:
                values.append(
                    computed_metric(
                        "stable_name_latency_sec",
                        _mean(derived_latencies),
                        numerator=sum(derived_latencies),
                        denominator=len(derived_latencies),
                        details={
                            "aggregation": "derived_from_complete_decision_intervals",
                            "episode_count": len(derived_latencies),
                            "eligible_episode_count": len(rows_by_episode),
                            "censored_episode_count": len(rows_by_episode)
                            - len(derived_latencies),
                        },
                    )
                )
            else:
                values.append(
                    undefined_metric(
                        "stable_name_latency_sec",
                        "no known-speaker episode reached a correct confirmed "
                        "name that remained stable",
                        numerator=0,
                        denominator=0,
                    )
                )
    identity_rows = [
        row for row in (identity_events or ()) if _identity_state_label(row) is not None
    ]
    if identity_rows:
        if all(
            _optional_text(row.get("anonymous_speaker_id")) for row in identity_rows
        ):
            values.append(
                computed_metric(
                    "identity_revision_count",
                    _identity_revision_count(identity_rows),
                )
            )
        else:
            values.append(
                unsupported_metric(
                    "identity_revision_count",
                    "anonymous_speaker_id is required to separate identity tracks",
                )
            )
    else:
        values.append(
            unsupported_metric(
                "identity_revision_count", "ordered identity revision timeline absent"
            )
        )
    return build_metric_report("identity", values)


def score_speaker_attributed_transcription(
    reference_speaker_texts: Mapping[str, str] | None,
    hypothesis_speaker_texts: Mapping[str, str] | None,
    *,
    prerequisites: SpeakerTranscriptPrerequisites | JsonRecord | None = None,
    identity_reference_speaker_texts: Mapping[str, str] | None = None,
    identity_hypothesis_speaker_texts: Mapping[str, str] | None = None,
    word_alignments: Sequence[WordAlignment | JsonRecord] | None = None,
    revision_events: Sequence[JsonRecord] | None = None,
) -> MetricReport:
    """Score cpWER and word-attribution metrics without inventing alignment.

    cpWER is gated even when two dictionaries are supplied: callers must attest
    that both contain complete per-speaker streams, name a normalization ID,
    and name the permutation scope.  Time-labelled diarization snippets alone
    do not satisfy those prerequisites.
    """

    gate = _speaker_prerequisites(prerequisites)
    values: list[MetricValue] = []
    streams_available = (
        reference_speaker_texts is not None and hypothesis_speaker_texts is not None
    )
    cpwer_ready = (
        streams_available
        and gate is not None
        and gate.reference_streams_complete
        and gate.hypothesis_streams_complete
        and gate.normalization_id == CPWER_NORMALIZATION_ID
        and gate.permutation_scope == CPWER_PERMUTATION_SCOPE_ID
    )
    if cpwer_ready:
        errors, reference_words, assignment = _cpwer_counts(
            reference_speaker_texts or {}, hypothesis_speaker_texts or {}
        )
        if reference_words:
            values.append(
                computed_metric(
                    "cpwer",
                    errors / reference_words,
                    numerator=errors,
                    denominator=reference_words,
                    details={
                        "normalization_id": gate.normalization_id,
                        "permutation_scope": gate.permutation_scope,
                        "speaker_assignment": assignment,
                    },
                )
            )
        else:
            values.append(
                undefined_metric(
                    "cpwer",
                    "complete reference streams contain zero words",
                    numerator=errors,
                    denominator=0,
                )
            )
    else:
        missing = []
        if not streams_available:
            missing.append("complete per-speaker text mappings")
        if gate is None or not gate.reference_streams_complete:
            missing.append("reference_streams_complete attestation")
        if gate is None or not gate.hypothesis_streams_complete:
            missing.append("hypothesis_streams_complete attestation")
        if gate is None or gate.normalization_id != CPWER_NORMALIZATION_ID:
            missing.append(f"normalization_id={CPWER_NORMALIZATION_ID!r}")
        if gate is None or gate.permutation_scope != CPWER_PERMUTATION_SCOPE_ID:
            missing.append(f"permutation_scope={CPWER_PERMUTATION_SCOPE_ID!r}")
        values.append(
            unsupported_metric(
                "cpwer", "missing cpWER prerequisites: " + ", ".join(missing)
            )
        )

    identity_references = (
        identity_reference_speaker_texts
        if identity_reference_speaker_texts is not None
        else reference_speaker_texts
    )
    identity_hypotheses = (
        identity_hypothesis_speaker_texts
        if identity_hypothesis_speaker_texts is not None
        else hypothesis_speaker_texts
    )
    identity_streams_available = (
        identity_references is not None and identity_hypotheses is not None
    )
    if identity_streams_available and gate is not None and gate.identities_comparable:
        errors = 0
        reference_words = 0
        speakers = sorted(
            set(identity_references or {}) | set(identity_hypotheses or {})
        )
        for speaker in speakers:
            ref = tuple(
                _normalize_text((identity_references or {}).get(speaker, "")).split()
            )
            hyp = tuple(
                _normalize_text((identity_hypotheses or {}).get(speaker, "")).split()
            )
            errors += _edit_distance(ref, hyp)
            reference_words += len(ref)
        if reference_words:
            values.append(
                computed_metric(
                    "speaker_attributed_wer",
                    errors / reference_words,
                    numerator=errors,
                    denominator=reference_words,
                    details={
                        "identity_mapping": (
                            gate.identity_mapping_id or "exact_speaker_id"
                        )
                    },
                )
            )
        else:
            values.append(
                undefined_metric(
                    "speaker_attributed_wer",
                    "comparable reference streams contain zero words",
                    numerator=errors,
                    denominator=0,
                )
            )
    else:
        values.append(
            unsupported_metric(
                "speaker_attributed_wer",
                "reference/hypothesis speaker identities are not attested comparable",
            )
        )

    if word_alignments is None:
        for metric_id in (
            "word_speaker_label_accuracy",
            "correct_transcribed_attributed_word_rate",
            "wrong_speaker_word_count",
            "wrong_speaker_word_time_sec",
            "unlabeled_generic_word_rate",
        ):
            values.append(
                unsupported_metric(metric_id, "frozen word alignment was not supplied")
            )
    else:
        alignments = tuple(_word_alignment(value) for value in word_alignments)
        word_alignment_details = {
            "word_alignment_id": (
                gate.word_alignment_id
                if gate is not None and gate.word_alignment_id
                else "caller_supplied_unspecified"
            )
        }
        reference_rows = [row for row in alignments if row.reference_word is not None]
        paired_rows = [row for row in reference_rows if row.hypothesis_word is not None]
        reference_labels_complete = all(
            row.reference_speaker_id is not None for row in reference_rows
        )
        if not reference_labels_complete:
            reason = "one or more aligned reference words lack a speaker label"
            for metric_id in (
                "word_speaker_label_accuracy",
                "correct_transcribed_attributed_word_rate",
                "wrong_speaker_word_count",
                "wrong_speaker_word_time_sec",
            ):
                values.append(unsupported_metric(metric_id, reason))
        elif paired_rows:
            label_correct = sum(
                row.hypothesis_speaker_id == row.reference_speaker_id
                for row in paired_rows
            )
            values.append(
                computed_metric(
                    "word_speaker_label_accuracy",
                    label_correct / len(paired_rows),
                    numerator=label_correct,
                    denominator=len(paired_rows),
                    details=word_alignment_details,
                )
            )
        else:
            values.append(
                undefined_metric(
                    "word_speaker_label_accuracy",
                    "alignment contains no paired reference/hypothesis words",
                    numerator=0,
                    denominator=0,
                )
            )
        both_correct = sum(
            _normalize_text(row.reference_word or "")
            == _normalize_text(row.hypothesis_word or "")
            and row.hypothesis_speaker_id == row.reference_speaker_id
            for row in reference_rows
        )
        if reference_labels_complete and reference_rows:
            values.append(
                computed_metric(
                    "correct_transcribed_attributed_word_rate",
                    both_correct / len(reference_rows),
                    numerator=both_correct,
                    denominator=len(reference_rows),
                    details=word_alignment_details,
                )
            )
        elif reference_labels_complete:
            values.append(
                undefined_metric(
                    "correct_transcribed_attributed_word_rate",
                    "alignment contains no reference words",
                    numerator=0,
                    denominator=0,
                )
            )
        wrong_speaker = (
            [
                row
                for row in paired_rows
                if _specific_speaker(row.hypothesis_speaker_id)
                and row.hypothesis_speaker_id != row.reference_speaker_id
            ]
            if reference_labels_complete
            else []
        )
        if reference_labels_complete:
            values.append(
                computed_metric(
                    "wrong_speaker_word_count",
                    len(wrong_speaker),
                    details=word_alignment_details,
                )
            )
            if all(row.reference_duration_sec is not None for row in reference_rows):
                values.append(
                    computed_metric(
                        "wrong_speaker_word_time_sec",
                        sum(
                            float(row.reference_duration_sec or 0.0)
                            for row in wrong_speaker
                        ),
                        details=word_alignment_details,
                    )
                )
            else:
                values.append(
                    unsupported_metric(
                        "wrong_speaker_word_time_sec",
                        "one or more reference word durations are absent",
                    )
                )
        hypothesis_rows = [row for row in alignments if row.hypothesis_word is not None]
        unlabelled = sum(
            not _specific_speaker(row.hypothesis_speaker_id) for row in hypothesis_rows
        )
        if hypothesis_rows:
            values.append(
                computed_metric(
                    "unlabeled_generic_word_rate",
                    unlabelled / len(hypothesis_rows),
                    numerator=unlabelled,
                    denominator=len(hypothesis_rows),
                    details=word_alignment_details,
                )
            )
        else:
            values.append(
                undefined_metric(
                    "unlabeled_generic_word_rate",
                    "alignment contains no hypothesis words",
                    numerator=0,
                    denominator=0,
                )
            )
    if revision_events is None:
        values.append(
            unsupported_metric(
                "retroactive_correction_count", "transcript revision events absent"
            )
        )
    else:
        corrections = sum(_is_retroactive_correction(row) for row in revision_events)
        values.append(computed_metric("retroactive_correction_count", corrections))
    return build_metric_report("speaker_transcription", values)


def score_ux(
    events: Sequence[JsonRecord] | None,
    *,
    stream_start_monotonic_ns: int | None = None,
    attribution_intervals: Sequence[AttributionInterval | JsonRecord] | None = None,
) -> MetricReport:
    """Score user-visible event latency/revision metrics from a complete timeline."""

    if events is None:
        return build_metric_report("ux", (), missing_reason="UX event timeline absent")
    timing_baseline_ns = _resolve_stream_start_monotonic_ns(
        events, explicit=stream_start_monotonic_ns
    )
    ordered = tuple(sorted(events, key=_event_sort_key))
    values: list[MetricValue] = []
    text_events = [row for row in ordered if _display_text(row)]
    values.append(
        _minimum_elapsed_metric(
            "time_to_first_text_sec",
            text_events,
            "no non-empty visible text event",
            stream_start_monotonic_ns=timing_baseline_ns,
        )
    )
    anonymous = [
        row
        for row in ordered
        if str(row.get("event_type")) == "anonymous_speaker"
        and (row.get("anonymous_speaker_id") or row.get("display_label"))
    ]
    values.append(
        _minimum_elapsed_metric(
            "time_to_first_anonymous_label_sec",
            anonymous,
            "no anonymous speaker label event",
            stream_start_monotonic_ns=timing_baseline_ns,
        )
    )
    tentative = [row for row in ordered if _tentative_known(row)]
    values.append(
        _minimum_elapsed_metric(
            "time_to_tentative_known_name_sec",
            tentative,
            "no tentative-known identity event",
            stream_start_monotonic_ns=timing_baseline_ns,
        )
    )
    confirmed = [row for row in ordered if _confirmed_known(row)]
    values.append(
        _minimum_elapsed_metric(
            "time_to_confirmed_known_name_sec",
            confirmed,
            "no confirmed-known identity event",
            stream_start_monotonic_ns=timing_baseline_ns,
        )
    )

    transcript_events = [row for row in ordered if _display_text(row)]
    transcript_states = [
        _normalize_text(_display_text(row)) for row in transcript_events
    ]
    transcript_changes = sum(
        current != previous
        for previous, current in zip(transcript_states, transcript_states[1:])
    )
    if transcript_events:
        values.append(computed_metric("transcript_revision_count", transcript_changes))
    else:
        values.append(
            unsupported_metric("transcript_revision_count", "no transcript states")
        )
    final_timeline = bool(transcript_events) and (
        str(transcript_events[-1].get("transcript_state")) == "final"
        or bool(transcript_events[-1].get("is_final"))
        or str(transcript_events[-1].get("event_type")) == "asr_final"
    )
    if final_timeline:
        final_text = transcript_states[-1]
        stable_candidates = [
            row
            for index, row in enumerate(transcript_events)
            if transcript_states[index] == final_text
            and all(value == final_text for value in transcript_states[index:])
        ]
        values.append(
            _minimum_elapsed_metric(
                "time_to_stable_text_sec",
                stable_candidates,
                "final transcript never appeared as a stable displayed state",
                stream_start_monotonic_ns=timing_baseline_ns,
            )
        )
    else:
        values.append(
            unsupported_metric(
                "time_to_stable_text_sec", "timeline has no attested final transcript"
            )
        )

    identity_events = [row for row in ordered if _identity_state_label(row) is not None]
    if identity_events:
        if all(
            _optional_text(row.get("anonymous_speaker_id")) for row in identity_events
        ):
            values.append(
                computed_metric(
                    "ux_identity_revision_count",
                    _identity_revision_count(identity_events),
                )
            )
        else:
            values.append(
                unsupported_metric(
                    "ux_identity_revision_count",
                    "anonymous_speaker_id is required to separate identity tracks",
                )
            )
    else:
        values.append(
            unsupported_metric(
                "ux_identity_revision_count", "no displayed identity states"
            )
        )

    annotated_identity_intervals = [
        row for row in ordered if "ui_identity_is_correct" in row
    ]
    wrong_dwell = [
        _interval_duration(row)
        for row in annotated_identity_intervals
        if row.get("ui_identity_is_correct") is False
        and _specific_speaker(_optional_text(row.get("displayed_speaker_id")))
        and _interval_duration(row) is not None
    ]
    if annotated_identity_intervals and all(
        _interval_duration(row) is not None for row in annotated_identity_intervals
    ):
        values.append(computed_metric("wrong_name_dwell_sec", sum(wrong_dwell)))
    elif attribution_intervals is not None:
        aligned = tuple(_attribution_interval(row) for row in attribution_intervals)
        aligned_wrong_dwell = sum(
            row.duration_sec
            for row in aligned
            if row.decision_state in {"tentative_known", "confirmed_known"}
            and row.predicted_speaker_id is not None
            and (
                not row.reference_is_known
                or row.predicted_speaker_id != row.reference_speaker_id
            )
        )
        values.append(
            computed_metric(
                "wrong_name_dwell_sec",
                aligned_wrong_dwell,
                details={
                    "source": "time_aligned_attribution_decision_intervals",
                    "tentative_names_are_user_visible": True,
                },
            )
        )
    else:
        values.append(
            unsupported_metric(
                "wrong_name_dwell_sec",
                "time-aligned UI/reference label intervals absent",
            )
        )
    ui_lags = [value for row in ordered if (value := _ui_lag_sec(row)) is not None]
    if ui_lags:
        values.append(
            computed_metric(
                "ui_event_lag_sec",
                _mean(ui_lags),
                numerator=sum(ui_lags),
                denominator=len(ui_lags),
            )
        )
    else:
        values.append(
            unsupported_metric("ui_event_lag_sec", "paired UI/event timestamps absent")
        )
    values.append(_dropped_audio_metric(ordered))
    stall_rows = [row for row in ordered if "stall_duration_sec" in row]
    stall_seconds = [
        value
        for row in ordered
        if (value := _optional_float(row.get("stall_duration_sec"))) is not None
    ]
    if stall_rows and len(stall_seconds) == len(stall_rows):
        values.append(computed_metric("stall_time_sec", sum(stall_seconds)))
    else:
        values.append(
            unsupported_metric(
                "stall_time_sec", "protocol-defined stall intervals absent"
            )
        )
    return build_metric_report("ux", values)


def score_resources(
    samples: Sequence[JsonRecord] | None,
    *,
    audio_duration_sec: float | None = None,
    wall_time_sec: float | None = None,
    startup_sec: float | None = None,
    model_bytes: int | None = None,
    cache_bytes: int | None = None,
    maximum_queue_depth: int | None = None,
    failure_count: int | None = None,
    retry_count: int | None = None,
) -> MetricReport:
    """Score serial/matched resource samples; concurrency policy is provenance."""

    rows = tuple(samples or ())
    values: list[MetricValue] = []
    if (
        audio_duration_sec is not None
        and audio_duration_sec > 0
        and wall_time_sec is not None
    ):
        values.extend(
            (
                computed_metric(
                    "total_rtf",
                    wall_time_sec / audio_duration_sec,
                    numerator=wall_time_sec,
                    denominator=audio_duration_sec,
                ),
                (
                    computed_metric(
                        "audio_throughput",
                        (
                            audio_duration_sec / wall_time_sec
                            if wall_time_sec > 0
                            else math.inf
                        ),
                        numerator=audio_duration_sec,
                        denominator=wall_time_sec,
                    )
                    if wall_time_sec > 0
                    else undefined_metric(
                        "audio_throughput",
                        "wall time is zero",
                        numerator=audio_duration_sec,
                        denominator=0.0,
                    )
                ),
            )
        )
    else:
        reason = "positive audio duration and measured end-to-end wall time required"
        values.extend(
            (
                unsupported_metric("total_rtf", reason),
                unsupported_metric("audio_throughput", reason),
            )
        )

    component_totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        component = _optional_text(row.get("component") or row.get("active_component"))
        processing = _optional_float(row.get("processing_sec"))
        audio = _optional_float(row.get("audio_duration_sec"))
        if component and processing is not None and audio is not None:
            component_totals[component][0] += processing
            component_totals[component][1] += audio
    component_rtfs = {
        component: processing / audio
        for component, (processing, audio) in sorted(component_totals.items())
        if audio > 0
    }
    if component_rtfs:
        values.append(
            computed_metric(
                "component_rtf",
                max(component_rtfs.values()),
                details={"component_rtfs": component_rtfs, "summary_value": "maximum"},
            )
        )
    else:
        values.append(
            unsupported_metric(
                "component_rtf", "component processing/audio duration pairs absent"
            )
        )
    cpu = [
        value
        for row in rows
        if (value := _optional_float(row.get("process_cpu_percent"))) is not None
    ]
    if cpu:
        values.extend(
            (
                computed_metric("process_cpu_mean_percent", _mean(cpu)),
                computed_metric("process_cpu_p95_percent", _percentile(cpu, 95.0)),
            )
        )
    else:
        values.extend(
            (
                unsupported_metric("process_cpu_mean_percent", "CPU samples absent"),
                unsupported_metric("process_cpu_p95_percent", "CPU samples absent"),
            )
        )
    rss = [
        value
        for row in rows
        if (value := _optional_float(row.get("process_rss_bytes"))) is not None
    ]
    values.append(
        computed_metric("peak_rss_bytes", max(rss))
        if rss
        else unsupported_metric("peak_rss_bytes", "RSS samples absent")
    )
    gpu_utilization = [
        value
        for row in rows
        if (value := _optional_float(row.get("gpu_utilization_percent"))) is not None
    ]
    values.append(
        computed_metric("gpu_peak_utilization_percent", max(gpu_utilization))
        if gpu_utilization
        else unsupported_metric(
            "gpu_peak_utilization_percent", "GPU utilization telemetry unavailable"
        )
    )
    gpu_memory = [
        value
        for row in rows
        for key in (
            "gpu_memory_bytes",
            "gpu_process_memory_bytes",
            "gpu_peak_memory_bytes",
        )
        if (value := _optional_float(row.get(key))) is not None
    ]
    values.append(
        computed_metric("gpu_peak_memory_bytes", max(gpu_memory))
        if gpu_memory
        else unsupported_metric(
            "gpu_peak_memory_bytes", "GPU memory telemetry unavailable"
        )
    )
    for metric_id, value, reason in (
        ("model_startup_sec", startup_sec, "model lifecycle timestamps absent"),
        ("model_bytes", model_bytes, "model asset byte manifest absent"),
        ("cache_bytes", cache_bytes, "cache byte manifest absent"),
        ("maximum_queue_depth", maximum_queue_depth, "queue depth telemetry absent"),
        ("failure_count", failure_count, "attempt failure states absent"),
        ("retry_count", retry_count, "attempt identities absent"),
    ):
        values.append(
            computed_metric(metric_id, value)
            if value is not None
            else unsupported_metric(metric_id, reason)
        )
    return build_metric_report("resources", values)


def score_full_pipeline(
    *,
    asr_utterances: Sequence[AsrUtterance | JsonRecord] | None = None,
    streaming_events: Sequence[JsonRecord] | None = None,
    streaming_references: Mapping[str, str] | None = None,
    stream_start_monotonic_ns: int | None = None,
    long_stream_cases: Sequence[LongStreamCase | JsonRecord] | None = None,
    diarization_references: Sequence[DiarizationSegment | JsonRecord] | None = None,
    diarization_hypotheses: Sequence[DiarizationSegment | JsonRecord] | None = None,
    diarization_uem: Sequence[tuple[float, float]] | None = None,
    diarization_collar_sec: float = 0.0,
    short_turn_max_duration_sec: float | None = None,
    reentry_episodes: Sequence[ReentryEpisode | JsonRecord] | None = None,
    attribution_intervals: Sequence[AttributionInterval | JsonRecord] | None = None,
    identity_events: Sequence[JsonRecord] | None = None,
    reference_speaker_texts: Mapping[str, str] | None = None,
    hypothesis_speaker_texts: Mapping[str, str] | None = None,
    speaker_transcript_prerequisites: (
        SpeakerTranscriptPrerequisites | JsonRecord | None
    ) = None,
    word_alignments: Sequence[WordAlignment | JsonRecord] | None = None,
    transcript_revision_events: Sequence[JsonRecord] | None = None,
    ux_events: Sequence[JsonRecord] | None = None,
    resource_samples: Sequence[JsonRecord] | None = None,
    resource_kwargs: Mapping[str, object] | None = None,
) -> Mapping[str, MetricReport]:
    """Return all seven equivalent evaluation views for one pipeline result."""

    return {
        "asr": score_asr(asr_utterances),
        "streaming": score_streaming(
            streaming_events,
            reference_text_by_hypothesis=streaming_references,
            stream_start_monotonic_ns=stream_start_monotonic_ns,
            long_stream_cases=long_stream_cases,
        ),
        "diarization": score_anonymous_diarization(
            diarization_references,
            diarization_hypotheses,
            uem=diarization_uem,
            collar_sec=diarization_collar_sec,
            short_turn_max_duration_sec=short_turn_max_duration_sec,
            reentry_episodes=reentry_episodes,
        ),
        "identity": score_known_unknown_attribution(
            attribution_intervals,
            identity_events=identity_events,
        ),
        "speaker_transcription": score_speaker_attributed_transcription(
            reference_speaker_texts,
            hypothesis_speaker_texts,
            prerequisites=speaker_transcript_prerequisites,
            word_alignments=word_alignments,
            revision_events=transcript_revision_events,
        ),
        "ux": score_ux(
            ux_events,
            stream_start_monotonic_ns=stream_start_monotonic_ns,
            attribution_intervals=attribution_intervals,
        ),
        "resources": score_resources(resource_samples, **dict(resource_kwargs or {})),
    }


def fold_reports_for_result_files(
    reports: Mapping[str, MetricReport],
) -> Mapping[str, Mapping[str, MetricReport]]:
    """Fold seven scientific views into the five common result files.

    The common artifact contract has ASR, streaming, diarization, identity, and
    resources metric files.  Speaker-attributed transcription remains a named
    sub-view of ASR, and UX remains a named sub-view of streaming; they are not
    flattened because metric definitions/statuses must remain unambiguous.
    """

    required = {
        "asr",
        "speaker_transcription",
        "streaming",
        "ux",
        "diarization",
        "identity",
        "resources",
    }
    missing = sorted(required - set(reports))
    if missing:
        raise ValueError(f"cannot fold incomplete metric reports: {missing}")
    return {
        "asr": {
            "asr": reports["asr"],
            "speaker_transcription": reports["speaker_transcription"],
        },
        "streaming": {
            "streaming": reports["streaming"],
            "ux": reports["ux"],
        },
        "diarization": {"diarization": reports["diarization"]},
        "identity": {"identity": reports["identity"]},
        "resources": {"resources": reports["resources"]},
    }


# ---------------------------------------------------------------------------
# Input coercion and exact low-level algorithms.


def _asr_utterance(value: AsrUtterance | JsonRecord) -> AsrUtterance:
    if isinstance(value, AsrUtterance):
        return value
    hypothesis_present = "hypothesis_text" in value or "text" in value
    raw_hypothesis = (
        value.get("hypothesis_text")
        if "hypothesis_text" in value
        else value.get("text")
    )
    return AsrUtterance(
        reference_text=str(value.get("reference_text") or ""),
        hypothesis_text=(
            str(raw_hypothesis)
            if hypothesis_present and raw_hypothesis is not None
            else None
        ),
        output_failed=bool(value.get("output_failed") or value.get("failed")),
        utterance_id=_optional_text(value.get("utterance_id") or value.get("utt_id")),
    )


def _diarization_segment(
    value: DiarizationSegment | JsonRecord,
) -> DiarizationSegment:
    if isinstance(value, DiarizationSegment):
        return value
    start = _optional_float(value.get("start_sec"))
    end = _optional_float(value.get("end_sec"))
    if end is None:
        duration = _optional_float(value.get("duration_sec"))
        end = start + duration if start is not None and duration is not None else None
    speaker = _optional_text(
        value.get("speaker_id")
        or value.get("speaker")
        or value.get("anonymous_speaker_id")
    )
    if start is None or end is None or speaker is None:
        raise ValueError(
            "diarization segment requires start_sec, end/duration, speaker_id"
        )
    return DiarizationSegment(start, end, speaker)


def _reentry_episode(value: ReentryEpisode | JsonRecord) -> ReentryEpisode:
    if isinstance(value, ReentryEpisode):
        result = value
    else:
        episode_id = _optional_text(value.get("episode_id"))
        reference_speaker_id = _optional_text(value.get("reference_speaker_id"))
        if episode_id is None or reference_speaker_id is None:
            raise ValueError(
                "re-entry annotations require episode_id and reference_speaker_id"
            )
        result = ReentryEpisode(
            episode_id=episode_id,
            reference_speaker_id=reference_speaker_id,
            before_hypothesis_speaker_id=_optional_text(
                value.get("before_hypothesis_speaker_id")
            ),
            after_hypothesis_speaker_id=_optional_text(
                value.get("after_hypothesis_speaker_id")
            ),
        )
    if not result.episode_id.strip() or not result.reference_speaker_id.strip():
        raise ValueError("re-entry episode identities must be non-empty")
    return result


def _long_stream_case(value: LongStreamCase | JsonRecord) -> LongStreamCase:
    if isinstance(value, LongStreamCase):
        result = value
    else:
        case_id = _optional_text(value.get("case_id"))
        duration = _optional_float(value.get("expected_duration_sec"))
        if case_id is None or duration is None or "final_emitted" not in value:
            raise ValueError(
                "long-stream cases require case_id, expected_duration_sec, and final_emitted"
            )
        result = LongStreamCase(
            case_id=case_id,
            expected_duration_sec=duration,
            final_emitted=bool(value.get("final_emitted")),
            reset_count=_optional_int(value.get("reset_count"), 0),
            stall_count=_optional_int(value.get("stall_count"), 0),
            failure_count=_optional_int(value.get("failure_count"), 0),
        )
    if result.expected_duration_sec <= 0:
        raise ValueError("long-stream expected duration must be > 0")
    if min(result.reset_count, result.stall_count, result.failure_count) < 0:
        raise ValueError("long-stream failure counters must be >= 0")
    return result


def _attribution_interval(
    value: AttributionInterval | JsonRecord,
) -> AttributionInterval:
    if isinstance(value, AttributionInterval):
        return value
    capture = value.get("capture_timestamps")
    start = _optional_float(value.get("start_sec"))
    end = _optional_float(value.get("end_sec"))
    if isinstance(capture, Mapping):
        if start is None:
            start = _optional_float(capture.get("audio_start_sec"))
        if end is None:
            end = _optional_float(capture.get("audio_end_sec"))
    if start is None:
        start = 0.0
    if end is None:
        duration = _optional_float(value.get("duration_sec"))
        end = start + duration if duration is not None else None
    reference = _optional_text(value.get("reference_speaker_id"))
    if end is None or reference is None or "reference_is_known" not in value:
        raise ValueError(
            "attribution interval requires timing, reference_speaker_id, and "
            "explicit reference_is_known"
        )
    if not isinstance(value.get("reference_is_known"), bool):
        raise ValueError("reference_is_known must be a JSON boolean")
    nested_predicted, nested_unknown = _speaker_label_fields(value.get("speaker_label"))
    decision_state = _normalized_decision_state(
        value.get("decision_state") or value.get("identity_state")
    )
    predicted_speaker_id = (
        _optional_text(value.get("predicted_speaker_id")) or nested_predicted
    )
    predicted_unknown_label = (
        _optional_text(value.get("predicted_unknown_label")) or nested_unknown
    )
    if decision_state not in {"confirmed_known", "tentative_known"}:
        predicted_speaker_id = None
    if decision_state != "unknown":
        predicted_unknown_label = None
    return AttributionInterval(
        start_sec=start,
        end_sec=end,
        reference_speaker_id=reference,
        reference_is_known=bool(value["reference_is_known"]),
        predicted_speaker_id=predicted_speaker_id,
        decision_state=decision_state,
        predicted_unknown_label=predicted_unknown_label,
        episode_id=_optional_text(value.get("episode_id") or value.get("probe_id")),
        temperature=_optional_text(value.get("temperature")),
        stable_name_latency_sec=_optional_float(value.get("stable_name_latency_sec")),
        identity_revision_count=_optional_int_or_none(
            value.get("identity_revision_count")
        ),
    )


def _normalized_decision_state(value: object) -> str:
    state = str(value or "unknown").strip().lower()
    aliases = {
        "confirmed": "confirmed_known",
        "confirmed_known": "confirmed_known",
        "tentative": "tentative_known",
        "tentative_known": "tentative_known",
        "generic": "generic_known",
        "generic_known": "generic_known",
        "unknown": "unknown",
        "released": "unknown",
        "uncovered": "uncovered",
    }
    try:
        return aliases[state]
    except KeyError as exc:
        raise ValueError(f"unsupported identity decision state: {state!r}") from exc


def _speaker_label_fields(value: object) -> tuple[str | None, str | None]:
    if not isinstance(value, Mapping):
        return None, None
    label_kind = _optional_text(value.get("label_kind"))
    if label_kind == "known":
        return _optional_text(value.get("enrolled_speaker_id")), None
    if label_kind == "unknown":
        return None, _optional_text(value.get("display_label"))
    return None, None


def _prompt1_identity_decision(
    event: JsonRecord,
) -> tuple[str, str | None, str | None]:
    state = _normalized_decision_state(event.get("identity_state"))
    predicted_id, unknown_label = _speaker_label_fields(event.get("speaker_label"))
    if state not in {"confirmed_known", "tentative_known"}:
        predicted_id = None
    if state != "unknown":
        unknown_label = None
    return state, predicted_id, unknown_label


def _identity_event_source_time(event: JsonRecord) -> float | None:
    capture = event.get("capture_timestamps")
    if isinstance(capture, Mapping):
        value = _optional_float(capture.get("audio_end_sec"))
        if value is not None:
            return value
    return _optional_float(event.get("source_time_sec") or event.get("end_sec"))


def _intersect_regions(
    regions: Sequence[tuple[float, float]],
    limiter: Sequence[tuple[float, float]] | None,
) -> list[tuple[float, float]]:
    if limiter is None:
        return list(regions)
    intersections = [
        (max(start, limit_start), min(end, limit_end))
        for start, end in regions
        for limit_start, limit_end in limiter
        if max(start, limit_start) < min(end, limit_end)
    ]
    return sorted(set(intersections))


def _speaker_prerequisites(
    value: SpeakerTranscriptPrerequisites | JsonRecord | None,
) -> SpeakerTranscriptPrerequisites | None:
    if value is None or isinstance(value, SpeakerTranscriptPrerequisites):
        return value
    return SpeakerTranscriptPrerequisites(
        reference_streams_complete=bool(value.get("reference_streams_complete")),
        hypothesis_streams_complete=bool(value.get("hypothesis_streams_complete")),
        normalization_id=_optional_text(value.get("normalization_id")),
        permutation_scope=_optional_text(value.get("permutation_scope")),
        identities_comparable=bool(value.get("identities_comparable")),
        identity_mapping_id=_optional_text(value.get("identity_mapping_id")),
        word_alignment_id=_optional_text(value.get("word_alignment_id")),
    )


def _word_alignment(value: WordAlignment | JsonRecord) -> WordAlignment:
    if isinstance(value, WordAlignment):
        return value
    return WordAlignment(
        reference_word=_optional_text(value.get("reference_word")),
        hypothesis_word=_optional_text(value.get("hypothesis_word")),
        reference_speaker_id=_optional_text(value.get("reference_speaker_id")),
        hypothesis_speaker_id=_optional_text(value.get("hypothesis_speaker_id")),
        reference_duration_sec=_optional_float(value.get("reference_duration_sec")),
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _word_edit_counts(
    reference: Sequence[str], hypothesis: Sequence[str]
) -> tuple[int, int, int, int]:
    """Return errors, substitutions, deletions, insertions with stable ties."""

    rows = len(reference)
    columns = len(hypothesis)
    table: list[list[tuple[int, int, int, int]]] = [
        [(0, 0, 0, 0) for _ in range(columns + 1)] for _ in range(rows + 1)
    ]
    for row in range(1, rows + 1):
        table[row][0] = (row, 0, row, 0)
    for column in range(1, columns + 1):
        table[0][column] = (column, 0, 0, column)
    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            if reference[row - 1] == hypothesis[column - 1]:
                table[row][column] = table[row - 1][column - 1]
                continue
            diagonal = table[row - 1][column - 1]
            above = table[row - 1][column]
            left = table[row][column - 1]
            candidates = (
                (diagonal[0] + 1, diagonal[1] + 1, diagonal[2], diagonal[3]),
                (above[0] + 1, above[1], above[2] + 1, above[3]),
                (left[0] + 1, left[1], left[2], left[3] + 1),
            )
            table[row][column] = min(candidates)
    return table[-1][-1]


def _edit_distance(reference: Sequence[object], hypothesis: Sequence[object]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, reference_value in enumerate(reference, start=1):
        current = [row]
        for column, hypothesis_value in enumerate(hypothesis, start=1):
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (reference_value != hypothesis_value),
                )
            )
        previous = current
    return previous[-1]


def _event_sort_key(row: JsonRecord) -> tuple[float, int]:
    elapsed = _event_elapsed_sec(row)
    emitted_ns = _event_emitted_monotonic_ns(row)
    sequence = _optional_int(row.get("event_sequence"), 0)
    primary = (
        elapsed
        if elapsed is not None
        else (emitted_ns / 1e9 if emitted_ns is not None else math.inf)
    )
    return (primary, sequence)


def _event_elapsed_sec(
    row: JsonRecord,
    *,
    stream_start_monotonic_ns: int | None = None,
) -> float | None:
    for key in ("emitted_elapsed_sec", "stream_elapsed_sec", "elapsed_sec"):
        value = _optional_float(row.get(key))
        if value is not None:
            return value
    emitted_ns = _event_emitted_monotonic_ns(row)
    if stream_start_monotonic_ns is not None and emitted_ns is not None:
        if emitted_ns < stream_start_monotonic_ns:
            return None
        return (emitted_ns - stream_start_monotonic_ns) / 1e9
    return None


def _event_emitted_monotonic_ns(row: JsonRecord) -> int | None:
    processing = row.get("processing_timestamps")
    if not isinstance(processing, Mapping):
        return None
    return _optional_int_or_none(processing.get("emitted_monotonic_ns"))


def _resolve_stream_start_monotonic_ns(
    rows: Sequence[JsonRecord],
    *,
    explicit: int | None,
) -> int | None:
    """Resolve a real capture baseline; never substitute first output emission."""

    if explicit is not None:
        if explicit < 0:
            raise ValueError("stream_start_monotonic_ns must be >= 0")
        return explicit
    candidates: list[int] = []
    for row in rows:
        source_clock = row.get("source_clock")
        if isinstance(source_clock, Mapping):
            for key in ("stream_start_monotonic_ns", "source_start_monotonic_ns"):
                value = _optional_int_or_none(source_clock.get(key))
                if value is not None:
                    candidates.append(value)
        if str(row.get("event_type")) != "audio_frame":
            continue
        capture = row.get("capture_timestamps")
        if isinstance(capture, Mapping):
            value = _optional_int_or_none(capture.get("capture_start_monotonic_ns"))
            if value is not None:
                candidates.append(value)
    return min(candidates) if candidates else None


def _event_text(row: JsonRecord) -> str:
    return str(row.get("normalized_text") or row.get("text") or "")


def _event_words(row: JsonRecord) -> tuple[str, ...]:
    raw_words = row.get("words")
    if isinstance(raw_words, Sequence) and not isinstance(
        raw_words, (str, bytes, bytearray)
    ):
        return tuple(str(value) for value in raw_words)
    return tuple(_normalize_text(_event_text(row)).split())


def _display_text(row: JsonRecord) -> str:
    displayed = _optional_text(row.get("displayed_text"))
    if displayed is not None:
        return displayed
    committed = _optional_text(row.get("committed_text"))
    provisional = _optional_text(row.get("provisional_text"))
    if committed is not None or provisional is not None:
        return " ".join(value for value in (committed, provisional) if value).strip()
    return str(row.get("text") or "").strip()


def _is_partial(row: JsonRecord) -> bool:
    return str(row.get("adapter_event_type") or row.get("event_type")) == "asr_partial"


def _is_final(row: JsonRecord) -> bool:
    return (
        bool(row.get("is_final"))
        or str(row.get("adapter_event_type") or row.get("event_type")) == "asr_final"
    )


def _hypothesis_key(row: JsonRecord) -> str:
    return str(
        row.get("hypothesis_id")
        or row.get("utterance_id")
        or row.get("utterance_index")
        or row.get("line_id")
        or "default"
    )


def _group_hypotheses(events: Sequence[JsonRecord]) -> Mapping[str, list[JsonRecord]]:
    grouped: dict[str, list[JsonRecord]] = defaultdict(list)
    for row in events:
        grouped[_hypothesis_key(row)].append(row)
    return grouped


def _minimum_elapsed_metric(
    metric_id: str,
    rows: Sequence[JsonRecord],
    empty_reason: str,
    *,
    stream_start_monotonic_ns: int | None = None,
) -> MetricValue:
    if not rows:
        return unsupported_metric(metric_id, empty_reason)
    elapsed = [
        value
        for row in rows
        if (
            value := _event_elapsed_sec(
                row, stream_start_monotonic_ns=stream_start_monotonic_ns
            )
        )
        is not None
    ]
    if not elapsed:
        return unsupported_metric(metric_id, "stream-relative event time absent")
    return computed_metric(metric_id, min(elapsed))


def _finalization_latency_sec(row: JsonRecord) -> float | None:
    milliseconds = _optional_float(row.get("finalization_latency_ms"))
    if milliseconds is not None:
        return milliseconds / 1000.0
    seconds = _optional_float(row.get("endpoint_to_final_sec"))
    if seconds is not None:
        return seconds
    endpoint = _optional_float(row.get("endpoint_elapsed_sec"))
    emitted = _event_elapsed_sec(row)
    if endpoint is not None and emitted is not None and emitted >= endpoint:
        return emitted - endpoint
    return None


def _stream_audio_duration(rows: Sequence[JsonRecord]) -> float | None:
    ends: list[float] = []
    starts: list[float] = []
    for row in rows:
        consumed = _optional_float(row.get("audio_consumed_through_sec"))
        if consumed is not None:
            ends.append(consumed)
        interval = row.get("accepted_audio_interval")
        capture = row.get("capture_timestamps")
        for source in (interval, capture):
            if isinstance(source, Mapping):
                start = _optional_float(source.get("audio_start_sec"))
                end = _optional_float(source.get("audio_end_sec"))
                if start is not None:
                    starts.append(start)
                if end is not None:
                    ends.append(end)
    if not ends:
        return None
    return max(ends) - (min(starts) if starts else 0.0)


def _validate_segments(segments: Sequence[DiarizationSegment], name: str) -> None:
    for segment in segments:
        if not math.isfinite(segment.start_sec) or not math.isfinite(segment.end_sec):
            raise ValueError(f"{name} segment timing must be finite")
        if segment.start_sec < 0 or segment.end_sec <= segment.start_sec:
            raise ValueError(f"{name} segments require 0 <= start_sec < end_sec")


def _diarization_atoms(
    references: Sequence[DiarizationSegment],
    hypotheses: Sequence[DiarizationSegment],
    *,
    uem: Sequence[tuple[float, float]] | None,
    collar_sec: float,
    score_overlap: bool,
) -> tuple[tuple[float, frozenset[str], frozenset[str]], ...]:
    all_segments = tuple(references) + tuple(hypotheses)
    if not all_segments and not uem:
        return ()
    regions = tuple(
        uem
        or (
            (
                min(value.start_sec for value in all_segments),
                max(value.end_sec for value in all_segments),
            ),
        )
    )
    if any(start < 0 or end <= start for start, end in regions):
        raise ValueError("UEM regions require 0 <= start < end")
    reference_boundaries = tuple(
        boundary
        for segment in references
        for boundary in (segment.start_sec, segment.end_sec)
    )
    boundaries = {
        boundary
        for segment in all_segments
        for boundary in (segment.start_sec, segment.end_sec)
    }
    for start, end in regions:
        boundaries.update((start, end))
    if collar_sec:
        for boundary in reference_boundaries:
            boundaries.update((max(0.0, boundary - collar_sec), boundary + collar_sec))
    ordered = sorted(boundaries)
    atoms: list[tuple[float, frozenset[str], frozenset[str]]] = []
    for start, end in zip(ordered, ordered[1:]):
        midpoint = (start + end) / 2.0
        if not any(
            region_start <= midpoint < region_end
            for region_start, region_end in regions
        ):
            continue
        if collar_sec and any(
            abs(midpoint - boundary) < collar_sec for boundary in reference_boundaries
        ):
            continue
        ref_active = frozenset(
            segment.speaker_id
            for segment in references
            if segment.start_sec <= midpoint < segment.end_sec
        )
        if not score_overlap and len(ref_active) > 1:
            continue
        hyp_active = frozenset(
            segment.speaker_id
            for segment in hypotheses
            if segment.start_sec <= midpoint < segment.end_sec
        )
        atoms.append((end - start, ref_active, hyp_active))
    return tuple(atoms)


def _speaker_overlap_matrix(
    atoms: Sequence[tuple[float, frozenset[str], frozenset[str]]],
    ref_speakers: Sequence[str],
    hyp_speakers: Sequence[str],
) -> np.ndarray:
    matrix = np.zeros((len(ref_speakers), len(hyp_speakers)), dtype=np.float64)
    ref_index = {speaker: index for index, speaker in enumerate(ref_speakers)}
    hyp_index = {speaker: index for index, speaker in enumerate(hyp_speakers)}
    for duration, ref_active, hyp_active in atoms:
        for ref_speaker in ref_active:
            for hyp_speaker in hyp_active:
                matrix[ref_index[ref_speaker], hyp_index[hyp_speaker]] += duration
    return matrix


def _maximum_matrix_mapping(
    matrix: np.ndarray,
    ref_speakers: Sequence[str],
    hyp_speakers: Sequence[str],
) -> dict[str, str]:
    if not ref_speakers or not hyp_speakers:
        return {}
    row_indices, column_indices = linear_sum_assignment(matrix, maximize=True)
    return {
        hyp_speakers[column]: ref_speakers[row]
        for row, column in zip(row_indices, column_indices)
    }


def _jer_metric(
    atoms: Sequence[tuple[float, frozenset[str], frozenset[str]]],
    ref_speakers: Sequence[str],
    hyp_speakers: Sequence[str],
) -> MetricValue:
    if not ref_speakers:
        return undefined_metric("jer", "no scored reference speakers", denominator=0)
    overlap = _speaker_overlap_matrix(atoms, ref_speakers, hyp_speakers)
    ref_duration = np.array(
        [
            sum(duration for duration, ref, _ in atoms if speaker in ref)
            for speaker in ref_speakers
        ]
    )
    hyp_duration = np.array(
        [
            sum(duration for duration, _, hyp in atoms if speaker in hyp)
            for speaker in hyp_speakers
        ]
    )
    similarities = np.zeros_like(overlap)
    for row in range(len(ref_speakers)):
        for column in range(len(hyp_speakers)):
            union = ref_duration[row] + hyp_duration[column] - overlap[row, column]
            similarities[row, column] = (
                overlap[row, column] / union if union > 0 else 0.0
            )
    assigned_similarity = np.zeros(len(ref_speakers), dtype=np.float64)
    if hyp_speakers:
        rows, columns = linear_sum_assignment(similarities, maximize=True)
        assigned_similarity[rows] = similarities[rows, columns]
    errors = 1.0 - assigned_similarity
    return computed_metric(
        "jer",
        float(errors.mean()),
        numerator=float(errors.sum()),
        denominator=len(ref_speakers),
    )


def _boundary_delay_metric(
    references: Sequence[DiarizationSegment],
    hypotheses: Sequence[DiarizationSegment],
    hyp_to_ref: Mapping[str, str],
    atoms: Sequence[tuple[float, frozenset[str], frozenset[str]]],
    *,
    uem: Sequence[tuple[float, float]] | None,
    collar_sec: float,
) -> MetricValue:
    scored_speakers = {speaker for _, active, _ in atoms for speaker in active}

    def inside_uem(point: float) -> bool:
        return uem is None or any(start <= point <= end for start, end in uem)

    delays: list[float] = []
    for ref_speaker in sorted(scored_speakers):
        mapped_hypotheses = [
            hyp for hyp, ref in hyp_to_ref.items() if ref == ref_speaker
        ]
        hypothesis_boundaries = [
            boundary
            for segment in hypotheses
            if segment.speaker_id in mapped_hypotheses
            for boundary in (segment.start_sec, segment.end_sec)
            if inside_uem(boundary)
        ]
        if not hypothesis_boundaries:
            continue
        for segment in references:
            if segment.speaker_id != ref_speaker:
                continue
            for boundary in (segment.start_sec, segment.end_sec):
                if not inside_uem(boundary):
                    continue
                raw_error = min(
                    abs(boundary - value) for value in hypothesis_boundaries
                )
                delays.append(max(0.0, raw_error - collar_sec))
    if not delays:
        return unsupported_metric(
            "boundary_delay_sec", "no mapped scored reference/hypothesis boundaries"
        )
    return computed_metric(
        "boundary_delay_sec",
        _mean(delays),
        numerator=sum(delays),
        denominator=len(delays),
        details={
            "collar_sec": collar_sec,
            "uem_provided": uem is not None,
            "boundary_count": len(delays),
            "collar_application": "max(0, absolute_error-collar_sec)",
        },
    )


def _cpwer_counts(
    references: Mapping[str, str], hypotheses: Mapping[str, str]
) -> tuple[int, int, Mapping[str, str | None]]:
    ref_ids = sorted(references)
    hyp_ids = sorted(hypotheses)
    size = max(len(ref_ids), len(hyp_ids))
    if size == 0:
        return 0, 0, {}
    ref_words = [tuple(_normalize_text(references[key]).split()) for key in ref_ids]
    hyp_words = [tuple(_normalize_text(hypotheses[key]).split()) for key in hyp_ids]
    matrix = np.zeros((size, size), dtype=np.int64)
    for row in range(size):
        reference = ref_words[row] if row < len(ref_words) else ()
        for column in range(size):
            hypothesis = hyp_words[column] if column < len(hyp_words) else ()
            matrix[row, column] = _edit_distance(reference, hypothesis)
    rows, columns = linear_sum_assignment(matrix)
    assignment = {
        ref_ids[row]: (hyp_ids[column] if column < len(hyp_ids) else None)
        for row, column in zip(rows, columns)
        if row < len(ref_ids)
    }
    return int(matrix[rows, columns].sum()), sum(map(len, ref_words)), assignment


def _specific_speaker(value: str | None) -> bool:
    return bool(value) and value not in {"generic_known", "unknown", "uncovered"}


def _is_retroactive_correction(row: JsonRecord) -> bool:
    if str(row.get("event_type")) != "transcript_revision":
        return False
    operation = str(row.get("operation") or "")
    return operation in {"replace", "speaker_relabel"}


def _confirmed_known(row: JsonRecord) -> bool:
    state = str(row.get("identity_state") or row.get("public_state") or "")
    label = row.get("speaker_label")
    if isinstance(label, Mapping):
        return state == "confirmed" and label.get("label_kind") == "known"
    return state in {"confirmed", "confirmed_known"} and bool(
        row.get("speaker_id") or row.get("predicted_speaker_id") or label
    )


def _tentative_known(row: JsonRecord) -> bool:
    """Return true only for an explicitly user-visible tentative known label."""

    state = str(row.get("identity_state") or row.get("public_state") or "")
    label = row.get("speaker_label")
    if isinstance(label, Mapping):
        return state in {"tentative", "tentative_known"} and (
            label.get("label_kind") == "known"
        )
    return state in {"tentative", "tentative_known"} and bool(
        row.get("speaker_id") or row.get("predicted_speaker_id") or label
    )


def _identity_state_label(row: JsonRecord) -> tuple[str, str] | None:
    state = _optional_text(row.get("identity_state") or row.get("public_state"))
    label = row.get("speaker_label")
    if isinstance(label, Mapping):
        label = label.get("display_label")
    label_text = _optional_text(
        label or row.get("display_label") or row.get("predicted_speaker_id")
    )
    if state is None and label_text is None:
        return None
    return state or "unspecified", label_text or "unlabelled"


def _identity_revision_count(rows: Sequence[JsonRecord]) -> int:
    by_speaker: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        speaker = _optional_text(row.get("anonymous_speaker_id"))
        state = _identity_state_label(row)
        if speaker is not None and state is not None:
            by_speaker[speaker].append(state)
    return sum(
        current != previous
        for states in by_speaker.values()
        for previous, current in zip(states, states[1:])
    )


def _interval_duration(row: JsonRecord) -> float | None:
    duration = _optional_float(row.get("duration_sec"))
    if duration is not None:
        return duration
    start = _optional_float(row.get("start_sec"))
    end = _optional_float(row.get("end_sec"))
    if start is not None and end is not None and end >= start:
        return end - start
    return None


def _ui_lag_sec(row: JsonRecord) -> float | None:
    milliseconds = _optional_float(row.get("ui_lag_ms"))
    if milliseconds is not None:
        return milliseconds / 1000.0
    rendered = _optional_float(row.get("ui_rendered_elapsed_sec"))
    emitted = _optional_float(row.get("event_emitted_elapsed_sec"))
    if rendered is not None and emitted is not None and rendered >= emitted:
        return rendered - emitted
    return None


def _dropped_audio_metric(rows: Sequence[JsonRecord]) -> MetricValue:
    audio_frames = [row for row in rows if str(row.get("event_type")) == "audio_frame"]
    if audio_frames:
        seconds: list[float] = []
        for row in audio_frames:
            capture = row.get("capture_timestamps")
            dropped = (
                _optional_float(capture.get("dropped_sample_count_before"))
                if isinstance(capture, Mapping)
                else None
            )
            sample_rate = _optional_float(row.get("sample_rate_hz"))
            if dropped is None or sample_rate is None or sample_rate <= 0:
                return unsupported_metric(
                    "dropped_audio_sec",
                    "audio-frame drop deltas require capture count and sample rate",
                )
            seconds.append(dropped / sample_rate)
        return computed_metric(
            "dropped_audio_sec",
            sum(seconds),
            details={
                "source": "audio_frame.capture_timestamps.dropped_sample_count_before",
                "deduplication": "audio_frame_only",
                "frame_count": len(audio_frames),
            },
        )

    explicit_rows = [
        row
        for row in rows
        if any(
            key in row
            for key in (
                "dropped_sample_count_delta",
                "dropped_samples_delta",
                "dropped_audio_sec",
            )
        )
    ]
    if explicit_rows:
        seconds = [_dropped_audio_sec(row) for row in explicit_rows]
        if all(value is not None for value in seconds):
            return computed_metric(
                "dropped_audio_sec",
                sum(float(value) for value in seconds if value is not None),
                details={"source": "explicit_delta_rows"},
            )
    return unsupported_metric("dropped_audio_sec", "dropped-sample deltas absent")


def _dropped_audio_sec(row: JsonRecord) -> float | None:
    raw_dropped = (
        row.get("dropped_sample_count_delta")
        if "dropped_sample_count_delta" in row
        else row.get("dropped_samples_delta")
    )
    dropped = _optional_float(raw_dropped)
    sample_rate = _optional_float(row.get("sample_rate_hz"))
    if dropped is not None and sample_rate is not None and sample_rate > 0:
        return dropped / sample_rate
    return _optional_float(row.get("dropped_audio_sec"))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _percentile(values: Sequence[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _optional_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
