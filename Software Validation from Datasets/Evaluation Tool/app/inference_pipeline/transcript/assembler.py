"""Assemble segment-level inference outputs into one utterance prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.inference_pipeline.asr.base import normalize_text
from app.inference_pipeline.contracts import (
    ASRTranscript,
    AudioSegment,
    EvaluationRecord,
    SpeakerDecision,
    TranscriptItem,
    WordTiming,
)
from app.inference_pipeline.typing import JsonObject


@dataclass(frozen=True)
class SegmentPrediction:
    """ASR and speaker output for one model segment."""

    segment_index: int
    segment: AudioSegment
    transcript: ASRTranscript
    speaker_decision: object | None = None
    raw_text: str | None = None
    normalized_text: str | None = None

    def to_jsonable(self) -> JsonObject:
        return {
            "segment_index": self.segment_index,
            "segment": self.segment.to_jsonable(),
            "transcript": self.transcript.to_jsonable(),
            "speaker_decision": _jsonable_decision(self.speaker_decision),
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
        }


@dataclass(frozen=True)
class TranscriptAssembly:
    """Utterance-level transcript plus diagnostics from segment assembly."""

    transcript: ASRTranscript
    speaker_decision: SpeakerDecision
    transcript_items: tuple[TranscriptItem, ...]
    diagnostics: JsonObject
    warnings: tuple[str, ...] = ()


def assemble_transcript(
    record: EvaluationRecord,
    segment_predictions: Sequence[SegmentPrediction],
    *,
    fallback_speaker_label: str | None = None,
) -> TranscriptAssembly:
    """Merge segment predictions chronologically without duplicating text."""

    original_predictions = tuple(segment_predictions)
    ordered = tuple(
        sorted(
            original_predictions,
            key=lambda item: (
                _sort_time(item.segment.start_sec),
                _sort_time(item.transcript.start_sec),
                item.segment_index,
            ),
        )
    )
    ordering_violations = _ordering_violations(original_predictions)
    overlap_violations = _overlap_violations(ordered)

    items: list[TranscriptItem] = []
    merged_tokens: list[str] = []
    raw_texts: list[str] = []
    normalized_texts: list[str] = []
    words: list[WordTiming] = []
    for prediction in ordered:
        raw_text = (
            prediction.raw_text
            if prediction.raw_text is not None
            else prediction.transcript.text
        )
        normalized_text = (
            prediction.normalized_text
            if prediction.normalized_text is not None
            else normalize_text(prediction.transcript.text)
        )
        raw_texts.append(raw_text)
        normalized_texts.append(normalized_text)
        merged_tokens = _append_without_duplicate(merged_tokens, normalized_text.split())
        words.extend(prediction.transcript.words)
        speaker_label = _speaker_label(prediction.speaker_decision)
        items.append(
            TranscriptItem(
                text=normalized_text,
                start_sec=_first_present(prediction.transcript.start_sec, prediction.segment.start_sec),
                end_sec=_first_present(prediction.transcript.end_sec, prediction.segment.end_sec),
                speaker_label=speaker_label,
                confidence=_confidence(prediction.speaker_decision),
                words=prediction.transcript.words,
            )
        )

    text = " ".join(merged_tokens).strip()
    transcript = ASRTranscript(
        text=text,
        words=tuple(words),
        language=_first_language(ordered),
        confidence=None,
        start_sec=record.start_sec,
        end_sec=record.end_sec,
    )
    utterance_speaker = _utterance_speaker_decision(
        ordered,
        fallback_speaker_label=fallback_speaker_label,
    )
    diagnostics: JsonObject = {
        "segments": [prediction.segment.to_jsonable() for prediction in ordered],
        "segment_predictions": [prediction.to_jsonable() for prediction in ordered],
        "speaker_decisions": [
            _jsonable_decision(prediction.speaker_decision)
            for prediction in ordered
            if prediction.speaker_decision is not None
        ],
        "raw_asr_text": raw_texts,
        "normalized_text": normalized_texts,
        "assembled_text": text,
        "chronological_ordering_violations": ordering_violations,
        "segment_overlap_violations": overlap_violations,
    }
    warnings = []
    if ordering_violations:
        warnings.append(f"{ordering_violations} segment ordering violation(s) corrected")
    if overlap_violations:
        warnings.append(f"{overlap_violations} overlapping segment span(s) observed")

    return TranscriptAssembly(
        transcript=transcript,
        speaker_decision=utterance_speaker,
        transcript_items=tuple(items),
        diagnostics=diagnostics,
        warnings=tuple(warnings),
    )


def _append_without_duplicate(existing: list[str], new_tokens: list[str]) -> list[str]:
    if not existing:
        return list(new_tokens)
    if not new_tokens:
        return list(existing)
    max_overlap = min(len(existing), len(new_tokens))
    overlap = 0
    for size in range(max_overlap, 0, -1):
        if existing[-size:] == new_tokens[:size]:
            overlap = size
            break
    return [*existing, *new_tokens[overlap:]]


def _utterance_speaker_decision(
    predictions: Sequence[SegmentPrediction],
    *,
    fallback_speaker_label: str | None,
) -> SpeakerDecision:
    scored: dict[str, tuple[float, float | None, object]] = {}
    for prediction in predictions:
        label = _speaker_label(prediction.speaker_decision)
        if not label:
            continue
        duration = _duration(prediction.segment)
        confidence = _confidence(prediction.speaker_decision)
        current_duration, current_confidence, current_decision = scored.get(
            label,
            (0.0, None, prediction.speaker_decision),
        )
        confidence_for_rank = confidence if confidence is not None else -1.0
        current_confidence_for_rank = (
            current_confidence if current_confidence is not None else -1.0
        )
        better_decision = (
            prediction.speaker_decision
            if confidence_for_rank > current_confidence_for_rank
            else current_decision
        )
        scored[label] = (
            current_duration + duration,
            max(confidence_for_rank, current_confidence_for_rank),
            better_decision,
        )

    if scored:
        label, (_duration_sum, confidence, decision) = max(
            scored.items(),
            # Equivalent decimal segment lengths can differ by a few binary
            # floating-point ulps (for example 0.7 versus 1.6 - 0.9).  Round
            # before ranking so ties remain stable in chronological order.
            key=lambda item: (
                round(item[1][0], 9),
                item[1][1] if item[1][1] is not None else -1.0,
            ),
        )
        return SpeakerDecision(
            speaker_label=label,
            confidence=None if confidence is None or confidence < 0 else confidence,
            method=_optional_string(_decision_value(decision, "method"))
            or "speaker_matching",
            embedding_id=_optional_string(_decision_value(decision, "embedding_id")),
            matched_reference_id=_optional_string(
                _decision_value(decision, "matched_reference_id")
            ),
            notes=_optional_string(_decision_value(decision, "notes")),
        )

    return SpeakerDecision(
        speaker_label=fallback_speaker_label,
        method="fallback" if fallback_speaker_label else "unavailable",
    )


def _ordering_violations(predictions: Sequence[SegmentPrediction]) -> int:
    previous = None
    violations = 0
    for prediction in predictions:
        current = _first_present(prediction.segment.start_sec, prediction.transcript.start_sec)
        if current is not None and previous is not None and current < previous:
            violations += 1
        if current is not None:
            previous = current
    return violations


def _overlap_violations(predictions: Sequence[SegmentPrediction]) -> int:
    previous_end = None
    violations = 0
    for prediction in predictions:
        start = _first_present(prediction.segment.start_sec, prediction.transcript.start_sec)
        end = _first_present(prediction.segment.end_sec, prediction.transcript.end_sec)
        if start is not None and previous_end is not None and start < previous_end:
            violations += 1
        if end is not None:
            previous_end = max(previous_end, end) if previous_end is not None else end
    return violations


def _first_language(predictions: Sequence[SegmentPrediction]) -> str | None:
    for prediction in predictions:
        if prediction.transcript.language:
            return prediction.transcript.language
    return None


def _duration(segment: AudioSegment) -> float:
    if segment.duration_sec is not None:
        return max(0.0, float(segment.duration_sec))
    if segment.start_sec is not None and segment.end_sec is not None:
        return max(0.0, float(segment.end_sec) - float(segment.start_sec))
    return 0.0


def _speaker_label(decision: object | None) -> str | None:
    value = _decision_value(decision, "speaker_label")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _confidence(decision: object | None) -> float | None:
    value = _decision_value(decision, "confidence")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _jsonable_decision(decision: object | None) -> JsonObject | None:
    if decision is None:
        return None
    to_jsonable = getattr(decision, "to_jsonable", None)
    if callable(to_jsonable):
        value = to_jsonable()
        return dict(value) if isinstance(value, Mapping) else {"value": str(value)}
    if isinstance(decision, Mapping):
        return {str(key): _jsonable(value) for key, value in decision.items()}
    return {
        "speaker_label": _speaker_label(decision),
        "confidence": _confidence(decision),
        "method": _optional_string(_decision_value(decision, "method")),
        "embedding_id": _optional_string(_decision_value(decision, "embedding_id")),
        "matched_reference_id": _optional_string(
            _decision_value(decision, "matched_reference_id")
        ),
        "notes": _optional_string(_decision_value(decision, "notes")),
    }


def _decision_value(decision: object | None, key: str) -> object | None:
    if decision is None:
        return None
    if isinstance(decision, Mapping):
        return decision.get(key)
    return getattr(decision, key, None)


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    to_jsonable = getattr(value, "to_jsonable", None)
    if callable(to_jsonable):
        return to_jsonable()
    return str(value)


def _sort_time(value: float | None) -> tuple[int, float]:
    return (1, 0.0) if value is None else (0, float(value))


def _first_present(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
