"""Deterministic H2 transcript paragraph construction.

Paragraph policies consume only already-emitted transcript spans.  They do not
alter ASR words or speaker decisions, which makes policy replay cheap and
scientifically auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class TranscriptParagraph:
    paragraph_id: str
    span_ids: tuple[str, ...]
    text: str
    start_sec: float | None
    end_sec: float | None
    anonymous_speaker_ids: tuple[str, ...]
    speaker_labels: tuple[str, ...]
    mixed_speaker: bool
    break_reason: str

    def to_jsonable(self) -> dict[str, object]:
        return {
            "paragraph_id": self.paragraph_id,
            "span_ids": list(self.span_ids),
            "text": self.text,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "anonymous_speaker_ids": list(self.anonymous_speaker_ids),
            "speaker_labels": list(self.speaker_labels),
            "mixed_speaker": self.mixed_speaker,
            "break_reason": self.break_reason,
        }


def build_paragraphs(
    spans: Iterable[object],
    *,
    policy: str,
    pause_sec: float,
    maximum_words: int,
) -> tuple[TranscriptParagraph, ...]:
    """Build T1–T4 paragraphs without inventing unavailable endpoint fields."""

    ordered = tuple(
        sorted(
            spans,
            key=lambda row: (
                getattr(row, "start_sec") is None,
                getattr(row, "start_sec")
                if getattr(row, "start_sec") is not None
                else float("inf"),
                str(getattr(row, "span_id")),
            ),
        )
    )
    if not ordered:
        return ()
    groups: list[tuple[list[object], str]] = []
    current: list[object] = []
    words = 0
    next_reason = "session_start"
    for span in ordered:
        reason = _break_reason(
            current,
            span,
            policy=policy,
            pause_sec=pause_sec,
            current_word_count=words,
            maximum_words=maximum_words,
        )
        if reason is not None and current:
            groups.append((current, next_reason))
            current = []
            words = 0
            next_reason = reason
        current.append(span)
        words += len(str(getattr(span, "text")).split())
    if current:
        groups.append((current, next_reason))
    return tuple(
        _paragraph(index + 1, rows, reason)
        for index, (rows, reason) in enumerate(groups)
    )


def _break_reason(
    current: Sequence[object],
    candidate: object,
    *,
    policy: str,
    pause_sec: float,
    current_word_count: int,
    maximum_words: int,
) -> str | None:
    if not current:
        return None
    candidate_words = len(str(getattr(candidate, "text")).split())
    if current_word_count + candidate_words > maximum_words:
        return "maximum_words"
    previous = current[-1]
    previous_end = getattr(previous, "end_sec")
    candidate_start = getattr(candidate, "start_sec")
    pause = (
        float(candidate_start) - float(previous_end)
        if previous_end is not None and candidate_start is not None
        else 0.0
    )
    speaker_changed = _speaker_key(previous) != _speaker_key(candidate)
    punctuation = str(getattr(previous, "text")).rstrip().endswith(
        (".", "?", "!")
    )
    endpoint = str(getattr(previous, "state", "")).lower() == "final"
    if policy == "T1_ASR_ENDPOINT_PUNCTUATION":
        return "asr_endpoint_punctuation" if endpoint and punctuation else None
    if policy == "T2_PAUSE_ASR_ENDPOINT":
        if endpoint and pause >= pause_sec:
            return "pause_asr_endpoint"
        return "asr_endpoint_punctuation" if endpoint and punctuation else None
    if policy == "T3_PAUSE_ASR_SPEAKER_CHANGE":
        if speaker_changed:
            return "speaker_change"
        if endpoint and pause >= pause_sec:
            return "pause_asr_endpoint"
        return "asr_endpoint_punctuation" if endpoint and punctuation else None
    if policy == "T4_SPEAKER_CHANGE_DOMINANT":
        if speaker_changed:
            return "speaker_change_dominant"
        return "long_pause" if pause >= pause_sec else None
    raise ValueError(f"unsupported paragraph policy: {policy}")


def _speaker_key(span: object) -> tuple[str | None, str | None]:
    # Anonymous ID is intentionally first: in H2_KNOWN_ONLY two people may both
    # display as "Unknown" but a likely voice change must still start a paragraph.
    return (
        getattr(span, "anonymous_speaker_id", None),
        getattr(span, "speaker_label", None),
    )


def _paragraph(
    ordinal: int, rows: Sequence[object], break_reason: str
) -> TranscriptParagraph:
    starts = [
        float(getattr(row, "start_sec"))
        for row in rows
        if getattr(row, "start_sec") is not None
    ]
    ends = [
        float(getattr(row, "end_sec"))
        for row in rows
        if getattr(row, "end_sec") is not None
    ]
    anonymous = tuple(
        sorted(
            {
                str(getattr(row, "anonymous_speaker_id"))
                for row in rows
                if getattr(row, "anonymous_speaker_id", None) is not None
            }
        )
    )
    labels = tuple(
        sorted(
            {
                str(getattr(row, "speaker_label"))
                for row in rows
                if getattr(row, "speaker_label", None) is not None
            }
        )
    )
    return TranscriptParagraph(
        paragraph_id=f"paragraph_{ordinal:06d}",
        span_ids=tuple(str(getattr(row, "span_id")) for row in rows),
        text=" ".join(str(getattr(row, "text")).strip() for row in rows).strip(),
        start_sec=min(starts) if starts else None,
        end_sec=max(ends) if ends else None,
        anonymous_speaker_ids=anonymous,
        speaker_labels=labels,
        mixed_speaker=len(anonymous) > 1 or len(labels) > 1,
        break_reason=break_reason,
    )


__all__ = ["TranscriptParagraph", "build_paragraphs"]
