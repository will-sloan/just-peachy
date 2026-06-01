"""Assemble segment-level ASR and speaker outputs into one utterance."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.asr.base import normalize_text
from app.inference_pipeline.contracts import (
    ASRTranscript,
    AudioSegment,
    EvaluationRecord,
    TranscriptItem,
    WordTiming,
)
from app.inference_pipeline.typing import JsonObject, JsonValue


@dataclass(frozen=True)
class SegmentPrediction:
    """ASR, speaker, and embedding outputs for one pipeline segment."""

    segment_index: int
    segment: AudioSegment
    transcript: ASRTranscript
    raw_text: str | None = None
    normalized_text: str | None = None
    speaker_decision: object | None = None
    embedding: object | None = None

    @property
    def speaker_label(self) -> str | None:
        value = getattr(self.speaker_decision, "speaker_label", None)
        if value is None and isinstance(self.speaker_decision, Mapping):
            value = self.speaker_decision.get("speaker_label")
        return str(value) if value not in (None, "") else None

    def to_jsonable(self) -> JsonObject:
        return {
            "segment_index": self.segment_index,
            "segment": self.segment.to_jsonable(),
            "transcript": self.transcript.to_jsonable(),
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "speaker_decision": _jsonable(self.speaker_decision),
            "embedding": _jsonable(self.embedding),
        }


@dataclass(frozen=True)
class AssembledTranscript:
    """Utterance-level transcript plus assembly diagnostics."""

    transcript: ASRTranscript
    transcript_items: tuple[TranscriptItem, ...]
    speaker_label: str | None
    raw_text: str
    chronological_ordering_violations: int = 0
    duplicate_text_tokens_removed: int = 0
    warnings: tuple[str, ...] = ()


class TranscriptAssembler:
    """Merge chunk transcripts while preserving output identity and timing."""

    def assemble(
        self,
        record: EvaluationRecord,
        segment_predictions: Sequence[SegmentPrediction],
    ) -> AssembledTranscript:
        sorted_predictions = _chronological(segment_predictions)
        chronological_violations = _chronological_violation_count(segment_predictions)

        merged_tokens: list[str] = []
        transcript_items: list[TranscriptItem] = []
        all_words: list[WordTiming] = []
        duplicate_tokens_removed = 0
        raw_text_parts: list[str] = []

        for prediction in sorted_predictions:
            raw_text = prediction.raw_text if prediction.raw_text is not None else prediction.transcript.text
            normalized_text = prediction.normalized_text
            if normalized_text is None:
                normalized_text = prediction.transcript.text
            normalized_text = normalize_text(normalized_text)
            raw_text_parts.append(str(raw_text or ""))

            item_text, removed = _dedupe_against_tail(merged_tokens, normalized_text.split())
            duplicate_tokens_removed += removed
            merged_tokens.extend(item_text.split())
            all_words.extend(prediction.transcript.words)
            transcript_items.append(
                TranscriptItem(
                    text=item_text,
                    start_sec=prediction.segment.start_sec,
                    end_sec=prediction.segment.end_sec,
                    speaker_label=prediction.speaker_label,
                    confidence=prediction.transcript.confidence,
                    words=prediction.transcript.words,
                )
            )

        text = " ".join(merged_tokens).strip()
        transcript = ASRTranscript(
            text=text,
            words=tuple(all_words),
            language=_first_language(sorted_predictions),
            confidence=_mean_confidence(sorted_predictions),
            start_sec=record.start_sec,
            end_sec=record.end_sec,
        )
        warnings = ()
        if chronological_violations:
            warnings = (f"reordered {chronological_violations} non-chronological segment(s)",)
        return AssembledTranscript(
            transcript=transcript,
            transcript_items=tuple(transcript_items),
            speaker_label=_speaker_label(sorted_predictions),
            raw_text=" ".join(part for part in raw_text_parts if part).strip(),
            chronological_ordering_violations=chronological_violations,
            duplicate_text_tokens_removed=duplicate_tokens_removed,
            warnings=warnings,
        )


def _chronological(
    predictions: Sequence[SegmentPrediction],
) -> tuple[SegmentPrediction, ...]:
    return tuple(
        sorted(
            predictions,
            key=lambda item: (
                item.segment.start_sec is None,
                item.segment.start_sec if item.segment.start_sec is not None else 0.0,
                item.segment.end_sec is None,
                item.segment.end_sec if item.segment.end_sec is not None else 0.0,
                item.segment_index,
            ),
        )
    )


def _chronological_violation_count(predictions: Sequence[SegmentPrediction]) -> int:
    violations = 0
    previous_start: float | None = None
    for prediction in predictions:
        start = prediction.segment.start_sec
        if start is not None and previous_start is not None and start < previous_start:
            violations += 1
        if start is not None:
            previous_start = start
    return violations


def _dedupe_against_tail(existing_tokens: Sequence[str], new_tokens: Sequence[str]) -> tuple[str, int]:
    if not new_tokens:
        return "", 0
    max_overlap = min(len(existing_tokens), len(new_tokens))
    overlap = 0
    for size in range(max_overlap, 0, -1):
        if list(existing_tokens[-size:]) == list(new_tokens[:size]):
            overlap = size
            break
    return " ".join(new_tokens[overlap:]).strip(), overlap


def _speaker_label(predictions: Sequence[SegmentPrediction]) -> str | None:
    labels: dict[str, tuple[int, float, int]] = {}
    for order, prediction in enumerate(predictions):
        label = prediction.speaker_label
        if not label:
            continue
        confidence = _decision_confidence(prediction.speaker_decision)
        count, total_confidence, first_order = labels.get(label, (0, 0.0, order))
        labels[label] = (count + 1, total_confidence + confidence, first_order)
    if not labels:
        return None
    return sorted(
        labels.items(),
        key=lambda item: (-item[1][0], -item[1][1], item[1][2], item[0]),
    )[0][0]


def _decision_confidence(decision: object | None) -> float:
    if decision is None:
        return 0.0
    value = getattr(decision, "confidence", None)
    if value is None and isinstance(decision, Mapping):
        value = decision.get("confidence")
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _first_language(predictions: Sequence[SegmentPrediction]) -> str | None:
    for prediction in predictions:
        if prediction.transcript.language:
            return prediction.transcript.language
    return None


def _mean_confidence(predictions: Sequence[SegmentPrediction]) -> float | None:
    values = [
        prediction.transcript.confidence
        for prediction in predictions
        if prediction.transcript.confidence is not None
    ]
    return sum(values) / len(values) if values else None


def _jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_jsonable"):
        return value.to_jsonable()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    return str(value)
