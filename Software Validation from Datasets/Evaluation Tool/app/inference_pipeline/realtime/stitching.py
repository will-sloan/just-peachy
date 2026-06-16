"""Overlap-aware transcript stitching for realtime ASR windows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Mapping, Sequence


UNKNOWN_SPEAKER = "Unknown"
_TOKEN_RE = re.compile(r"\b[\w']+\b", re.ASCII)


@dataclass(frozen=True)
class RealtimeWord:
    """One stitched transcript token with stream-absolute timing."""

    text: str
    normalized: str
    start_sec: float | None = None
    end_sec: float | None = None
    source_window_index: int = 0
    speaker_label: str = UNKNOWN_SPEAKER
    speaker_label_status: str = "unknown"

    def to_jsonable(self) -> dict[str, object]:
        return {
            "text": self.text,
            "normalized": self.normalized,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "source_window_index": self.source_window_index,
            "speaker_label": self.speaker_label,
            "speaker_label_status": self.speaker_label_status,
        }


@dataclass(frozen=True)
class StitcherUpdate:
    """State snapshot after one ASR window is merged."""

    raw_asr_text: str
    normalized_asr_text: str
    overlap_removed_tokens: int
    committed_text: str
    provisional_text: str
    newly_committed_text: str
    provisional_delta_text: str
    emitted_prediction_text: str
    using_word_timestamps: bool
    committed_words: tuple[RealtimeWord, ...]
    provisional_words: tuple[RealtimeWord, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "raw_asr_text": self.raw_asr_text,
            "normalized_asr_text": self.normalized_asr_text,
            "overlap_removed_tokens": self.overlap_removed_tokens,
            "committed_text": self.committed_text,
            "provisional_text": self.provisional_text,
            "newly_committed_text": self.newly_committed_text,
            "provisional_delta_text": self.provisional_delta_text,
            "emitted_prediction_text": self.emitted_prediction_text,
            "using_word_timestamps": self.using_word_timestamps,
            "committed_words": [word.to_jsonable() for word in self.committed_words],
            "provisional_words": [word.to_jsonable() for word in self.provisional_words],
        }


class RealtimeTranscriptStitcher:
    """Merge overlapping ASR windows into committed and provisional text."""

    def __init__(
        self,
        *,
        stability_delay_sec: float = 1.0,
        unknown_speaker_label: str = UNKNOWN_SPEAKER,
    ) -> None:
        if stability_delay_sec < 0:
            raise ValueError("stability_delay_sec must be >= 0")
        if not unknown_speaker_label.strip():
            raise ValueError("unknown_speaker_label must be non-empty")
        self.stability_delay_sec = float(stability_delay_sec)
        self.unknown_speaker_label = unknown_speaker_label
        self._committed: list[RealtimeWord] = []
        self._provisional: list[RealtimeWord] = []
        self._last_update: StitcherUpdate | None = None

    @property
    def committed_words(self) -> tuple[RealtimeWord, ...]:
        return tuple(self._committed)

    @property
    def provisional_words(self) -> tuple[RealtimeWord, ...]:
        return tuple(self._provisional)

    @property
    def all_words(self) -> tuple[RealtimeWord, ...]:
        return (*self.committed_words, *self.provisional_words)

    @property
    def last_update(self) -> StitcherUpdate | None:
        return self._last_update

    def update(
        self,
        *,
        raw_text: str,
        window_start_sec: float,
        window_end_sec: float,
        window_index: int,
        words: Sequence[object] = (),
        speaker_label: str | None = None,
        speaker_label_status: str = "unknown",
    ) -> StitcherUpdate:
        """Merge one ASR window and advance stable committed text."""

        active_label = _clean_speaker_label(speaker_label, self.unknown_speaker_label)
        incoming, using_word_timestamps = _window_words(
            raw_text=raw_text,
            words=words,
            window_start_sec=float(window_start_sec),
            window_end_sec=float(window_end_sec),
            window_index=int(window_index),
            speaker_label=active_label,
            speaker_label_status=speaker_label_status,
        )
        existing_tokens = [word.normalized for word in self.all_words]
        incoming_tokens = [word.normalized for word in incoming]
        overlap = _suffix_prefix_overlap(existing_tokens, incoming_tokens)
        appended = list(incoming[overlap:])
        self._provisional.extend(appended)

        stable_before = float(window_end_sec) - self.stability_delay_sec
        newly_committed = self._commit_stable_words(stable_before)
        provisional_ids = {id(word) for word in self._provisional}
        appended_still_provisional = [
            word for word in appended if id(word) in provisional_ids
        ]
        update = StitcherUpdate(
            raw_asr_text=raw_text,
            normalized_asr_text=" ".join(incoming_tokens).strip(),
            overlap_removed_tokens=overlap,
            committed_text=_words_text(self._committed),
            provisional_text=_words_text(self._provisional),
            newly_committed_text=_words_text(newly_committed),
            provisional_delta_text=_words_text(appended_still_provisional),
            emitted_prediction_text=(
                _words_text(newly_committed) or _words_text(appended_still_provisional)
            ),
            using_word_timestamps=using_word_timestamps,
            committed_words=tuple(self._committed),
            provisional_words=tuple(self._provisional),
        )
        self._last_update = update
        return update

    def apply_speaker_state(
        self,
        *,
        speaker_label: str | None,
        speaker_label_status: str,
        stream_time_sec: float,
        correction_window_sec: float,
    ) -> bool:
        """Apply delayed speaker evidence to recent transcript words."""

        if correction_window_sec < 0:
            raise ValueError("correction_window_sec must be >= 0")
        label = _clean_speaker_label(speaker_label, self.unknown_speaker_label)
        cutoff = float(stream_time_sec) - float(correction_window_sec)
        changed = False
        updated: list[RealtimeWord] = []
        for word in [*self._committed, *self._provisional]:
            word_end = word.end_sec if word.end_sec is not None else stream_time_sec
            if word_end >= cutoff and (
                word.speaker_label != label
                or word.speaker_label_status != speaker_label_status
            ):
                changed = True
                updated.append(
                    RealtimeWord(
                        text=word.text,
                        normalized=word.normalized,
                        start_sec=word.start_sec,
                        end_sec=word.end_sec,
                        source_window_index=word.source_window_index,
                        speaker_label=label,
                        speaker_label_status=speaker_label_status,
                    )
                )
            else:
                updated.append(word)

        committed_len = len(self._committed)
        self._committed = updated[:committed_len]
        self._provisional = updated[committed_len:]
        return changed

    def _commit_stable_words(self, stable_before_sec: float) -> list[RealtimeWord]:
        newly_committed: list[RealtimeWord] = []
        while self._provisional:
            word = self._provisional[0]
            if word.end_sec is not None and word.end_sec > stable_before_sec:
                break
            newly_committed.append(self._provisional.pop(0))
        self._committed.extend(newly_committed)
        return newly_committed


def _window_words(
    *,
    raw_text: str,
    words: Sequence[object],
    window_start_sec: float,
    window_end_sec: float,
    window_index: int,
    speaker_label: str,
    speaker_label_status: str,
) -> tuple[tuple[RealtimeWord, ...], bool]:
    timed_words = [
        _coerce_word(
            value,
            window_start_sec=window_start_sec,
            window_index=window_index,
            speaker_label=speaker_label,
            speaker_label_status=speaker_label_status,
        )
        for value in words
    ]
    timed_words = [word for word in timed_words if word is not None]
    if timed_words and all(word.start_sec is not None and word.end_sec is not None for word in timed_words):
        return tuple(timed_words), True

    tokens = _display_tokens(raw_text)
    if not tokens:
        return (), False
    duration = max(0.0, window_end_sec - window_start_sec)
    step = duration / len(tokens) if tokens else 0.0
    fallback_words = []
    for index, token in enumerate(tokens):
        fallback_words.append(
            RealtimeWord(
                text=token,
                normalized=normalize_token(token),
                start_sec=round(window_start_sec + index * step, 6),
                end_sec=round(window_start_sec + (index + 1) * step, 6),
                source_window_index=window_index,
                speaker_label=speaker_label,
                speaker_label_status=speaker_label_status,
            )
        )
    return tuple(fallback_words), False


def _coerce_word(
    value: object,
    *,
    window_start_sec: float,
    window_index: int,
    speaker_label: str,
    speaker_label_status: str,
) -> RealtimeWord | None:
    text = _word_field(value, "word")
    if text is None:
        text = _word_field(value, "text")
    if text is None or not str(text).strip():
        return None
    normalized = normalize_token(str(text))
    if not normalized:
        return None
    start = _optional_float(_word_field(value, "start_sec"))
    end = _optional_float(_word_field(value, "end_sec"))
    if start is None:
        start = _optional_float(_word_field(value, "start"))
    if end is None:
        end = _optional_float(_word_field(value, "end"))
    return RealtimeWord(
        text=str(text).strip(),
        normalized=normalized,
        start_sec=round(window_start_sec + start, 6) if start is not None else None,
        end_sec=round(window_start_sec + end, 6) if end is not None else None,
        source_window_index=window_index,
        speaker_label=speaker_label,
        speaker_label_status=speaker_label_status,
    )


def _word_field(value: object, field_name: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(field_name)
    return getattr(value, field_name, None)


def _optional_float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_tokens(text: str) -> list[str]:
    return [match.group(0) for match in _TOKEN_RE.finditer(text)]


def normalize_token(token: str) -> str:
    text = token.strip().casefold()
    text = re.sub(r"[^a-z0-9']+", "", text)
    return text


def normalize_text_for_stitching(text: str) -> str:
    return " ".join(
        token for token in (normalize_token(raw) for raw in _display_tokens(text)) if token
    )


def _suffix_prefix_overlap(existing: Sequence[str], incoming: Sequence[str]) -> int:
    if not existing or not incoming:
        return 0
    max_size = min(len(existing), len(incoming))
    for size in range(max_size, 0, -1):
        if _tokens_match(existing[-size:], incoming[:size]):
            return size
    return 0


def _tokens_match(left: Sequence[str], right: Sequence[str]) -> bool:
    if len(left) != len(right):
        return False
    return all(_token_similar(a, b) for a, b in zip(left, right, strict=True))


def _token_similar(left: str, right: str) -> bool:
    if left == right:
        return True
    if not left or not right:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.86


def _words_text(words: Sequence[RealtimeWord]) -> str:
    return " ".join(word.text for word in words if word.text).strip()


def _clean_speaker_label(value: str | None, unknown_label: str) -> str:
    if value is None:
        return unknown_label
    text = str(value).strip()
    return text or unknown_label
