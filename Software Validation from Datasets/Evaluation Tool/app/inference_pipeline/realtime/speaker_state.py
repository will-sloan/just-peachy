"""Delayed speaker-label state for realtime transcript spans."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Mapping


UNKNOWN_LABEL = "Unknown"
SPEAKER_STATUS_UNKNOWN = "unknown"
SPEAKER_STATUS_TENTATIVE = "tentative"
SPEAKER_STATUS_CONFIRMED = "confirmed"


@dataclass(frozen=True)
class SpeakerStateUpdate:
    """Speaker-label state after one evidence window."""

    speaker_label: str
    status: str
    scores: dict[str, float]
    best_label: str | None
    best_score: float | None
    evidence_window_count: int
    agreement_count: int
    corrected_prior_span: bool = False

    def to_jsonable(self) -> dict[str, object]:
        return {
            "speaker_label": self.speaker_label,
            "status": self.status,
            "scores": dict(self.scores),
            "best_label": self.best_label,
            "best_score": self.best_score,
            "evidence_window_count": self.evidence_window_count,
            "agreement_count": self.agreement_count,
            "corrected_prior_span": self.corrected_prior_span,
        }


class SpeakerEvidenceAccumulator:
    """Accumulate recent speaker evidence into unknown/tentative/confirmed states."""

    def __init__(
        self,
        *,
        confirmation_windows: int = 3,
        confirmation_threshold: int = 2,
        score_threshold: float = 0.5,
        unknown_label: str = UNKNOWN_LABEL,
    ) -> None:
        if confirmation_windows < 1:
            raise ValueError("confirmation_windows must be >= 1")
        if confirmation_threshold < 1:
            raise ValueError("confirmation_threshold must be >= 1")
        if confirmation_threshold > confirmation_windows:
            raise ValueError("confirmation_threshold must be <= confirmation_windows")
        if not unknown_label.strip():
            raise ValueError("unknown_label must be non-empty")
        self.confirmation_windows = int(confirmation_windows)
        self.confirmation_threshold = int(confirmation_threshold)
        self.score_threshold = float(score_threshold)
        self.unknown_label = unknown_label
        self._recent: deque[str] = deque(maxlen=self.confirmation_windows)
        self._current_label = unknown_label
        self._current_status = SPEAKER_STATUS_UNKNOWN
        self._current_scores: dict[str, float] = {}

    @property
    def current_label(self) -> str:
        return self._current_label

    @property
    def current_status(self) -> str:
        return self._current_status

    @property
    def current_scores(self) -> dict[str, float]:
        return dict(self._current_scores)

    def add_evidence(
        self,
        scores: Mapping[str, object] | None,
    ) -> SpeakerStateUpdate:
        """Add one evidence window of label scores."""

        clean_scores = _clean_scores(scores or {}, self.unknown_label)
        self._current_scores = clean_scores
        best_label, best_score = _best_score(clean_scores, self.unknown_label)
        if best_label is None or best_score is None or best_score < self.score_threshold:
            self._recent.append(self.unknown_label)
            update = self._set_state(
                speaker_label=self.unknown_label,
                status=SPEAKER_STATUS_UNKNOWN,
                best_label=best_label,
                best_score=best_score,
                scores=clean_scores,
                agreement_count=0,
            )
            return update

        self._recent.append(best_label)
        counts = Counter(label for label in self._recent if label != self.unknown_label)
        agreed_label, agreement_count = counts.most_common(1)[0] if counts else (None, 0)
        if agreed_label == best_label and agreement_count >= self.confirmation_threshold:
            return self._set_state(
                speaker_label=best_label,
                status=SPEAKER_STATUS_CONFIRMED,
                best_label=best_label,
                best_score=best_score,
                scores=clean_scores,
                agreement_count=agreement_count,
            )

        return self._set_state(
            speaker_label=best_label,
            status=SPEAKER_STATUS_TENTATIVE,
            best_label=best_label,
            best_score=best_score,
            scores=clean_scores,
            agreement_count=agreement_count if agreed_label == best_label else 1,
        )

    def _set_state(
        self,
        *,
        speaker_label: str,
        status: str,
        best_label: str | None,
        best_score: float | None,
        scores: dict[str, float],
        agreement_count: int,
    ) -> SpeakerStateUpdate:
        previous_label = self._current_label
        previous_status = self._current_status
        self._current_label = speaker_label
        self._current_status = status
        corrected = (
            status == SPEAKER_STATUS_CONFIRMED
            and (previous_label != speaker_label or previous_status != SPEAKER_STATUS_CONFIRMED)
        )
        return SpeakerStateUpdate(
            speaker_label=speaker_label,
            status=status,
            scores=dict(scores),
            best_label=best_label,
            best_score=best_score,
            evidence_window_count=len(self._recent),
            agreement_count=agreement_count,
            corrected_prior_span=corrected,
        )


def _clean_scores(scores: Mapping[str, object], unknown_label: str) -> dict[str, float]:
    clean: dict[str, float] = {}
    for label, value in scores.items():
        text = str(label).strip()
        if not text or text == unknown_label:
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        clean[text] = score
    return clean


def _best_score(
    scores: Mapping[str, float],
    unknown_label: str,
) -> tuple[str | None, float | None]:
    if not scores:
        return None, None
    label, score = max(scores.items(), key=lambda item: item[1])
    if label == unknown_label:
        return None, None
    return label, score
