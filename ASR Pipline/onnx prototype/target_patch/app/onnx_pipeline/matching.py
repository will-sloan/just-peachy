from __future__ import annotations

from typing import Iterable

import numpy as np

from .contracts import SpeakerMatch


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def aggregate_scores(query: np.ndarray, exemplars: Iterable[np.ndarray]) -> float:
    scores = [cosine_similarity(query, ex) for ex in exemplars]
    if not scores:
        return 0.0
    return float(np.mean(scores))


def choose_speaker(
    query: np.ndarray,
    gallery: dict[str, list[np.ndarray]],
    accept_threshold: float,
    margin_threshold: float,
) -> SpeakerMatch:
    if not gallery:
        return SpeakerMatch(
            label=None,
            best_score=None,
            second_best_score=None,
            accepted=False,
            reason="empty_gallery",
        )

    scored = sorted(
        ((label, aggregate_scores(query, exemplars)) for label, exemplars in gallery.items()),
        key=lambda item: item[1],
        reverse=True,
    )

    best_label, best_score = scored[0]
    second_best_score = scored[1][1] if len(scored) > 1 else None

    if best_score < accept_threshold:
        return SpeakerMatch(
            label=None,
            best_score=best_score,
            second_best_score=second_best_score,
            accepted=False,
            reason="below_accept_threshold",
        )

    if second_best_score is not None and (best_score - second_best_score) < margin_threshold:
        return SpeakerMatch(
            label=None,
            best_score=best_score,
            second_best_score=second_best_score,
            accepted=False,
            reason="insufficient_margin",
        )

    return SpeakerMatch(
        label=best_label,
        best_score=best_score,
        second_best_score=second_best_score,
        accepted=True,
        reason="accepted",
    )
