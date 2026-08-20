"""Deterministic cosine clustering for modular diarization pipelines."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.inference_pipeline.errors import ContractValidationError


def agglomerative_cosine_labels(
    embeddings: Sequence[Sequence[float]],
    *,
    threshold: float,
    min_clusters: int = 1,
    max_clusters: int | None = None,
) -> list[int]:
    """Cluster normalized embeddings with deterministic average linkage.

    ``threshold`` belongs only to the calling diarization configuration.  It is
    intentionally unrelated to any named-speaker recognition threshold.
    """

    matrix = np.asarray(embeddings, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 1 or matrix.shape[1] < 1:
        raise ContractValidationError(
            "diarization embeddings must be a non-empty two-dimensional matrix"
        )
    if not np.isfinite(matrix).all():
        raise ContractValidationError("diarization embeddings must be finite")
    try:
        threshold_value = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(
            "diarization clustering threshold must be numeric"
        ) from exc
    if not -1.0 <= threshold_value <= 1.0:
        raise ContractValidationError(
            "diarization clustering threshold must be in [-1, 1]"
        )
    if min_clusters < 1 or min_clusters > matrix.shape[0]:
        raise ContractValidationError(
            "diarization min_clusters must be between 1 and the embedding count"
        )
    if max_clusters is not None:
        if max_clusters < min_clusters:
            raise ContractValidationError(
                "diarization max_clusters must be at least min_clusters"
            )
        max_clusters = min(max_clusters, matrix.shape[0])

    norms = np.linalg.norm(matrix, axis=1)
    if np.any(norms <= 0.0):
        raise ContractValidationError("diarization embeddings must be non-zero")
    normalized = matrix / norms[:, None]
    similarity = np.clip(normalized @ normalized.T, -1.0, 1.0)
    clusters: list[tuple[int, ...]] = [(index,) for index in range(matrix.shape[0])]

    while len(clusters) > min_clusters:
        candidates = [
            (
                _average_link_similarity(similarity, left, right),
                left[0],
                right[0],
                left_index,
                right_index,
            )
            for left_index, left in enumerate(clusters)
            for right_index, right in enumerate(clusters[left_index + 1 :], left_index + 1)
        ]
        if not candidates:
            break
        # Highest similarity wins; earliest original indices break exact ties.
        best = min(candidates, key=lambda item: (-item[0], item[1], item[2]))
        force_merge = max_clusters is not None and len(clusters) > max_clusters
        if not force_merge and best[0] < threshold_value:
            break
        left_index, right_index = best[3], best[4]
        merged = tuple(sorted((*clusters[left_index], *clusters[right_index])))
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in {left_index, right_index}
        ]
        clusters.append(merged)
        clusters.sort(key=lambda cluster: cluster[0])

    labels = [0] * matrix.shape[0]
    for label, cluster in enumerate(sorted(clusters, key=lambda item: item[0])):
        for index in cluster:
            labels[index] = label
    return labels


def _average_link_similarity(
    similarity: np.ndarray,
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> float:
    values = similarity[np.ix_(np.asarray(left), np.asarray(right))]
    return float(np.mean(values))
