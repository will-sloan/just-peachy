"""Deterministic causal anonymous-speaker clustering.

This is an additive online policy, not the frozen batch average-link result.
It keeps monotonic session cluster IDs, compares each normalized embedding with
normalized cluster centroids, and never uses future embeddings.  The frozen
diarization threshold (0.35) remains configurable, but this causal policy needs
its own runtime identity and later scientific qualification.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from typing import Mapping, Sequence

import numpy as np


ONLINE_CLUSTER_POLICY_ID = "full_pipeline_online_centroid_cosine.v1"


class OnlineClusteringError(ValueError):
    """Raised when an online clustering observation violates the contract."""


@dataclass(frozen=True)
class OnlineClusterConfig:
    threshold: float = 0.35
    minimum_embedding_duration_sec: float = 0.75
    short_turn_attach_gap_sec: float = 0.50
    maximum_clusters: int = 128
    maximum_embeddings_per_cluster: int = 256
    cluster_prefix: str = "anon"
    policy_id: str = ONLINE_CLUSTER_POLICY_ID
    reconciliation_enabled: bool = False
    reconciliation_threshold: float | None = None
    reconciliation_max_gap_sec: float = 120.0
    reconciliation_min_embeddings: int = 2

    def __post_init__(self) -> None:
        if not -1.0 <= self.threshold <= 1.0:
            raise OnlineClusteringError("threshold must be in [-1, 1]")
        if self.minimum_embedding_duration_sec <= 0:
            raise OnlineClusteringError("minimum_embedding_duration_sec must be > 0")
        if self.short_turn_attach_gap_sec < 0:
            raise OnlineClusteringError("short_turn_attach_gap_sec must be >= 0")
        if self.maximum_clusters < 1 or self.maximum_embeddings_per_cluster < 1:
            raise OnlineClusteringError("online clustering bounds must be >= 1")
        if self.reconciliation_threshold is not None and not (
            -1.0 <= self.reconciliation_threshold <= 1.0
        ):
            raise OnlineClusteringError("reconciliation_threshold must be in [-1, 1]")
        if self.reconciliation_max_gap_sec <= 0 or not math.isfinite(
            self.reconciliation_max_gap_sec
        ):
            raise OnlineClusteringError(
                "reconciliation_max_gap_sec must be finite and > 0"
            )
        if self.reconciliation_min_embeddings < 2:
            raise OnlineClusteringError("reconciliation_min_embeddings must be >= 2")
        if self.reconciliation_enabled and self.reconciliation_threshold is None:
            raise OnlineClusteringError(
                "reconciliation_enabled requires a calibrated threshold"
            )
        if not self.cluster_prefix.strip() or not self.policy_id.strip():
            raise OnlineClusteringError(
                "cluster_prefix and policy_id must be non-empty"
            )

    def to_jsonable(self) -> dict[str, object]:
        value: dict[str, object] = {
            "policy_id": self.policy_id,
            "family": "online_normalized_centroid_cosine",
            "threshold": self.threshold,
            "minimum_embedding_duration_sec": self.minimum_embedding_duration_sec,
            "short_turn_attach_gap_sec": self.short_turn_attach_gap_sec,
            "maximum_clusters": self.maximum_clusters,
            "maximum_embeddings_per_cluster": self.maximum_embeddings_per_cluster,
            "stable_cluster_ids": True,
            "future_evidence_used": False,
        }
        if self.reconciliation_enabled:
            value["causal_reconciliation"] = {
                "enabled": True,
                "voice_similarity_threshold": self.reconciliation_threshold,
                "maximum_gap_sec": self.reconciliation_max_gap_sec,
                "minimum_source_embeddings": self.reconciliation_min_embeddings,
                "timing_requires_nonoverlap": True,
                "future_spatial_hook_available": False,
                "future_spatial_hook_result_effect": False,
            }
        return value


@dataclass(frozen=True)
class ClusterAssignment:
    window_id: str
    cluster_id: str
    start_sec: float
    end_sec: float
    score: float | None
    provisional: bool
    short_turn: bool
    reentry: bool
    evidence_duration_sec: float

    def to_jsonable(self) -> dict[str, object]:
        return {
            "window_id": self.window_id,
            "cluster_id": self.cluster_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "score": self.score,
            "provisional": self.provisional,
            "short_turn": self.short_turn,
            "reentry": self.reentry,
            "evidence_duration_sec": self.evidence_duration_sec,
        }


@dataclass(frozen=True)
class ClusterRevision:
    window_id: str
    previous_cluster_id: str
    cluster_id: str
    reason: str

    def to_jsonable(self) -> dict[str, str]:
        return {
            "window_id": self.window_id,
            "previous_cluster_id": self.previous_cluster_id,
            "cluster_id": self.cluster_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OnlineClusterUpdate:
    assignment: ClusterAssignment
    revisions: tuple[ClusterRevision, ...]
    active_cluster_count: int
    reconciliation: "ClusterReconciliation | None" = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "assignment": self.assignment.to_jsonable(),
            "revisions": [row.to_jsonable() for row in self.revisions],
            "active_cluster_count": self.active_cluster_count,
            "reconciliation": (
                self.reconciliation.to_jsonable()
                if self.reconciliation is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ClusterReconciliation:
    """One whole-cluster causal merge justified by voice and past timing."""

    source_cluster_id: str
    survivor_cluster_id: str
    voice_similarity: float
    source_gap_sec: float
    revisions: tuple[ClusterRevision, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "source_cluster_id": self.source_cluster_id,
            "survivor_cluster_id": self.survivor_cluster_id,
            "voice_similarity": self.voice_similarity,
            "source_gap_sec": self.source_gap_sec,
            "revisions": [row.to_jsonable() for row in self.revisions],
            "future_evidence_used": False,
            "spatial_evidence_available": False,
            "spatial_evidence_result_effect": False,
        }


@dataclass
class _Cluster:
    cluster_id: str
    vectors: dict[str, np.ndarray] = field(default_factory=dict)
    windows: set[str] = field(default_factory=set)
    first_start_sec: float = math.inf
    last_end_sec: float = 0.0
    released: bool = False

    @property
    def centroid(self) -> np.ndarray | None:
        if not self.vectors:
            return None
        mean = np.mean(np.stack(list(self.vectors.values())), axis=0)
        norm = float(np.linalg.norm(mean))
        if not math.isfinite(norm) or norm <= 0:
            return None
        return mean / norm


class OnlineClusterManager:
    """Assign an append-only stream while allowing explicit evidence revisions."""

    def __init__(self, config: OnlineClusterConfig | None = None) -> None:
        self.config = config or OnlineClusterConfig()
        self._clusters: dict[str, _Cluster] = {}
        self._assignments: dict[str, ClusterAssignment] = {}
        self._window_vectors: dict[str, np.ndarray | None] = {}
        self._cluster_revisions: dict[str, int] = {}
        self._reconciliation_history: list[ClusterReconciliation] = []
        self._counter = 0

    @property
    def assignments(self) -> Mapping[str, ClusterAssignment]:
        return dict(self._assignments)

    def observe(
        self,
        *,
        window_id: str,
        start_sec: float,
        end_sec: float,
        embedding: Sequence[float] | None,
        evidence_duration_sec: float | None = None,
    ) -> OnlineClusterUpdate:
        """Assign or revise one window using only evidence available now."""

        if not window_id.strip():
            raise OnlineClusteringError("window_id must be non-empty")
        if (
            not math.isfinite(start_sec)
            or not math.isfinite(end_sec)
            or end_sec <= start_sec
        ):
            raise OnlineClusteringError(
                "window timestamps must be finite and increasing"
            )
        duration = float(
            evidence_duration_sec
            if evidence_duration_sec is not None
            else end_sec - start_sec
        )
        if not math.isfinite(duration) or duration <= 0:
            raise OnlineClusteringError(
                "evidence_duration_sec must be finite and positive"
            )
        vector = _normalized(embedding) if embedding is not None else None
        short_turn = (
            duration < self.config.minimum_embedding_duration_sec or vector is None
        )
        if short_turn:
            vector = None

        previous = self._assignments.get(window_id)
        previous_cluster_id = previous.cluster_id if previous else None
        previous_cluster = self._clusters.get(previous_cluster_id or "")
        if previous_cluster is not None:
            previous_cluster.windows.discard(window_id)
            previous_cluster.vectors.pop(window_id, None)

        score: float | None = None
        if vector is None:
            cluster = self._short_turn_cluster(start_sec, previous_cluster)
            provisional = True
        else:
            cluster, score = self._best_cluster(vector)
            if cluster is None or score is None or score < self.config.threshold:
                cluster = (
                    previous_cluster
                    if previous_cluster and not previous_cluster.released
                    else None
                )
                if cluster is None:
                    cluster = self._new_cluster()
                score = None
            provisional = False

        prior_end = cluster.last_end_sec
        reentry = bool(
            cluster.windows
            and start_sec > prior_end + self.config.short_turn_attach_gap_sec
        )
        cluster.windows.add(window_id)
        cluster.first_start_sec = min(cluster.first_start_sec, start_sec)
        cluster.last_end_sec = max(cluster.last_end_sec, end_sec)
        if vector is not None:
            cluster.vectors[window_id] = vector
        self._window_vectors[window_id] = vector

        assignment = ClusterAssignment(
            window_id=window_id,
            cluster_id=cluster.cluster_id,
            start_sec=float(start_sec),
            end_sec=float(end_sec),
            score=score,
            provisional=provisional,
            short_turn=short_turn,
            reentry=reentry,
            evidence_duration_sec=duration,
        )
        self._assignments[window_id] = assignment
        self._prune_cluster_history(cluster)
        revisions: tuple[ClusterRevision, ...] = ()
        if (
            previous_cluster_id is not None
            and previous_cluster_id != cluster.cluster_id
        ):
            revisions = (
                ClusterRevision(
                    window_id=window_id,
                    previous_cluster_id=previous_cluster_id,
                    cluster_id=cluster.cluster_id,
                    reason="stronger_embedding_evidence",
                ),
            )
        self._discard_empty(previous_cluster)
        reconciliation = None
        if self.config.reconciliation_enabled:
            reconciliation = self.reconcile_cluster(
                cluster.cluster_id, source_time_sec=end_sec
            )
            if reconciliation is not None:
                revisions = (*revisions, *reconciliation.revisions)
                assignment = self._assignments[window_id]
        return OnlineClusterUpdate(
            assignment=assignment,
            revisions=revisions,
            active_cluster_count=sum(
                not item.released for item in self._clusters.values()
            ),
            reconciliation=reconciliation,
        )

    def reconcile_cluster(
        self, cluster_id: str, *, source_time_sec: float
    ) -> ClusterReconciliation | None:
        """Merge a causal fragment into one earlier non-overlapping cluster.

        Only centroids already observed at ``source_time_sec`` participate.
        The method never uses reference truth, future audio, or the inactive
        spatial hook.
        """

        if not self.config.reconciliation_enabled:
            return None
        if not math.isfinite(source_time_sec) or source_time_sec < 0:
            raise OnlineClusteringError("source_time_sec must be finite and >= 0")
        source = self._clusters.get(cluster_id)
        if source is None or source.released:
            raise OnlineClusteringError(f"unknown active cluster_id: {cluster_id}")
        if len(source.vectors) < self.config.reconciliation_min_embeddings:
            return None
        source_centroid = source.centroid
        if source_centroid is None:
            return None
        assert self.config.reconciliation_threshold is not None
        candidates: list[tuple[float, float, str, _Cluster]] = []
        for target in self._clusters.values():
            if target.cluster_id == source.cluster_id or target.released:
                continue
            if not target.vectors or not target.windows:
                continue
            gap = source.first_start_sec - target.last_end_sec
            if gap < 0.0 or gap > self.config.reconciliation_max_gap_sec:
                continue
            target_centroid = target.centroid
            if target_centroid is None:
                continue
            score = float(np.dot(source_centroid, target_centroid))
            if score >= self.config.reconciliation_threshold:
                candidates.append((score, gap, target.cluster_id, target))
        if not candidates:
            return None
        score, gap, _target_id, target = min(
            candidates, key=lambda row: (-row[0], row[1], row[2])
        )
        revisions = tuple(
            ClusterRevision(
                window_id=window_id,
                previous_cluster_id=source.cluster_id,
                cluster_id=target.cluster_id,
                reason="causal_fragment_reconciliation_voice_timing",
            )
            for window_id in sorted(source.windows)
        )
        for revision in revisions:
            assignment = self._assignments[revision.window_id]
            self._assignments[revision.window_id] = replace(
                assignment, cluster_id=target.cluster_id, reentry=True
            )
        target.windows.update(source.windows)
        target.vectors.update(source.vectors)
        target.first_start_sec = min(target.first_start_sec, source.first_start_sec)
        target.last_end_sec = max(target.last_end_sec, source.last_end_sec)
        self._clusters.pop(source.cluster_id, None)
        self._cluster_revisions.pop(source.cluster_id, None)
        self._prune_cluster_history(target)
        result = ClusterReconciliation(
            source_cluster_id=source.cluster_id,
            survivor_cluster_id=target.cluster_id,
            voice_similarity=score,
            source_gap_sec=gap,
            revisions=revisions,
        )
        self._reconciliation_history.append(result)
        overflow = len(self._reconciliation_history) - self.config.maximum_clusters
        if overflow > 0:
            del self._reconciliation_history[:overflow]
        return result

    def release(self, cluster_id: str) -> None:
        """Prevent future re-entry into a cluster without reusing its ID."""

        try:
            self._clusters[cluster_id].released = True
        except KeyError as exc:
            raise OnlineClusteringError(f"unknown cluster_id: {cluster_id}") from exc

    def update(self, embedding: object, window: object) -> object:
        """Implement the common runtime protocol using full-pipeline model types."""

        from app.full_pipeline.models import AnonymousClusterUpdate

        existing_ids = set(self._clusters)
        result = self.observe(
            window_id=str(getattr(window, "window_id")),
            start_sec=float(getattr(window, "start_sec")),
            end_sec=float(getattr(window, "end_sec")),
            embedding=getattr(embedding, "vector"),
            evidence_duration_sec=float(getattr(embedding, "duration_sec")),
        )
        assignment = result.assignment
        cluster = self._clusters[assignment.cluster_id]
        revision = self._cluster_revisions.get(assignment.cluster_id, 0) + 1
        self._cluster_revisions[assignment.cluster_id] = revision
        return AnonymousClusterUpdate(
            anonymous_speaker_id=assignment.cluster_id,
            cluster_revision=revision,
            start_sec=assignment.start_sec,
            end_sec=assignment.end_sec,
            state="PROVISIONAL" if assignment.provisional else "ACTIVE",
            similarity=assignment.score,
            created=assignment.cluster_id not in existing_ids,
            reentry=assignment.reentry,
            boundary=assignment.cluster_id not in existing_ids
            or bool(result.revisions),
            evidence_duration_sec=sum(
                self._assignments[key].evidence_duration_sec for key in cluster.windows
            ),
            evidence_window_count=len(cluster.vectors),
            source_window_ids=tuple(sorted(cluster.windows)),
        )

    def finalize(self) -> tuple[object, ...]:
        """Emit one final state per live cluster; no assignments are changed."""

        from app.full_pipeline.models import AnonymousClusterUpdate

        updates = []
        for cluster in sorted(self._clusters.values(), key=lambda row: row.cluster_id):
            if cluster.released or not cluster.windows:
                continue
            assignments = [self._assignments[key] for key in cluster.windows]
            revision = self._cluster_revisions.get(cluster.cluster_id, 0) + 1
            self._cluster_revisions[cluster.cluster_id] = revision
            updates.append(
                AnonymousClusterUpdate(
                    anonymous_speaker_id=cluster.cluster_id,
                    cluster_revision=revision,
                    start_sec=min(row.start_sec for row in assignments),
                    end_sec=max(row.end_sec for row in assignments),
                    state="FINAL",
                    similarity=None,
                    created=False,
                    reentry=False,
                    boundary=False,
                    evidence_duration_sec=sum(
                        row.evidence_duration_sec for row in assignments
                    ),
                    evidence_window_count=len(cluster.vectors),
                    source_window_ids=tuple(sorted(cluster.windows)),
                )
            )
        return tuple(updates)

    def reset(self) -> None:
        self._clusters.clear()
        self._assignments.clear()
        self._window_vectors.clear()
        self._cluster_revisions.clear()
        self._reconciliation_history.clear()
        self._counter = 0

    def snapshot(self) -> dict[str, object]:
        return {
            "schema_version": "full-pipeline-online-cluster-state.v1",
            "policy": self.config.to_jsonable(),
            "next_cluster_number": self._counter + 1,
            "clusters": [
                {
                    "cluster_id": cluster.cluster_id,
                    "member_window_ids": sorted(cluster.windows),
                    "embedding_member_count": len(cluster.vectors),
                    "first_start_sec": cluster.first_start_sec,
                    "last_end_sec": cluster.last_end_sec,
                    "released": cluster.released,
                }
                for cluster in sorted(
                    self._clusters.values(), key=lambda row: row.cluster_id
                )
            ],
            "assignments": [
                self._assignments[key].to_jsonable()
                for key in sorted(self._assignments)
            ],
            "reconciliation_history": [
                row.to_jsonable() for row in self._reconciliation_history
            ],
        }

    def _new_cluster(self) -> _Cluster:
        if len(self._clusters) >= self.config.maximum_clusters:
            self._evict_oldest_cluster()
        self._counter += 1
        cluster_id = f"{self.config.cluster_prefix}_{self._counter:04d}"
        cluster = _Cluster(cluster_id=cluster_id)
        self._clusters[cluster_id] = cluster
        return cluster

    def _prune_cluster_history(self, cluster: _Cluster) -> None:
        """Keep centroids/session state bounded while event logs remain append-only."""

        overflow = len(cluster.vectors) - self.config.maximum_embeddings_per_cluster
        if overflow > 0:
            oldest = sorted(
                cluster.vectors,
                key=lambda key: (
                    self._assignments[key].end_sec
                    if key in self._assignments
                    else -1.0,
                    key,
                ),
            )[:overflow]
            for window_id in oldest:
                cluster.vectors.pop(window_id, None)
                cluster.windows.discard(window_id)
                self._assignments.pop(window_id, None)
                self._window_vectors.pop(window_id, None)
        # Short turns have no vector, so the vector limit alone would leave an
        # unbounded assignment history. Apply the same explicit ceiling to all
        # active windows in a cluster.
        window_overflow = (
            len(cluster.windows) - self.config.maximum_embeddings_per_cluster
        )
        if window_overflow <= 0:
            return
        oldest_windows = sorted(
            cluster.windows,
            key=lambda key: (
                self._assignments[key].end_sec
                if key in self._assignments
                else -1.0,
                key,
            ),
        )[:window_overflow]
        for window_id in oldest_windows:
            cluster.windows.discard(window_id)
            cluster.vectors.pop(window_id, None)
            self._assignments.pop(window_id, None)
            self._window_vectors.pop(window_id, None)

    def _evict_oldest_cluster(self) -> None:
        if not self._clusters:
            return
        cluster = min(
            self._clusters.values(),
            key=lambda value: (
                not value.released,
                value.last_end_sec,
                value.cluster_id,
            ),
        )
        for window_id in tuple(cluster.windows):
            self._assignments.pop(window_id, None)
            self._window_vectors.pop(window_id, None)
        self._cluster_revisions.pop(cluster.cluster_id, None)
        self._clusters.pop(cluster.cluster_id, None)

    def _best_cluster(self, vector: np.ndarray) -> tuple[_Cluster | None, float | None]:
        candidates: list[tuple[float, str, _Cluster]] = []
        for cluster in self._clusters.values():
            if cluster.released:
                continue
            centroid = cluster.centroid
            if centroid is None:
                continue
            candidates.append(
                (float(np.dot(vector, centroid)), cluster.cluster_id, cluster)
            )
        if not candidates:
            return None, None
        score, _cluster_id, cluster = min(candidates, key=lambda row: (-row[0], row[1]))
        return cluster, score

    def _short_turn_cluster(
        self, start_sec: float, previous_cluster: _Cluster | None
    ) -> _Cluster:
        if previous_cluster is not None and not previous_cluster.released:
            return previous_cluster
        candidates = [
            cluster
            for cluster in self._clusters.values()
            if not cluster.released
            and cluster.windows
            and 0.0
            <= start_sec - cluster.last_end_sec
            <= self.config.short_turn_attach_gap_sec
        ]
        if candidates:
            return min(candidates, key=lambda row: (-row.last_end_sec, row.cluster_id))
        return self._new_cluster()

    def _discard_empty(self, cluster: _Cluster | None) -> None:
        if cluster is None or cluster.windows or cluster.released:
            return
        self._clusters.pop(cluster.cluster_id, None)


def _normalized(values: Sequence[float]) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
        raise OnlineClusteringError("embedding must be a non-empty finite vector")
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 0:
        raise OnlineClusteringError("embedding must have a positive finite norm")
    return vector / norm
