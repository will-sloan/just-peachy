"""Online anonymous clustering plus frozen open-set identity decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json

import numpy as np

from .config import PipelineConfig
from .contracts import SpeakerDecision


@dataclass
class _Cluster:
    cluster_id: int
    center: np.ndarray
    count: int
    first_source_sec: float
    last_source_sec: float


class ProfileStore:
    def __init__(
        self, root: Path, *, expected_backend_sha256: str | None = None
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.expected_backend_sha256 = expected_backend_sha256

    def load(self) -> dict[str, np.ndarray]:
        result: dict[str, np.ndarray] = {}
        for metadata_path in self.root.glob("*.json"):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                vector_path = metadata_path.with_suffix(".npy")
                vector = np.load(vector_path, allow_pickle=False).astype(np.float32)
                hash_matches = (
                    self.expected_backend_sha256 is None
                    or metadata.get("backend_sha256")
                    == self.expected_backend_sha256
                )
                if metadata.get("backend_id") == "redimnet2_b2_fp32" and hash_matches and vector.shape == (192,):
                    norm = float(np.linalg.norm(vector))
                    if norm > 0:
                        result[str(metadata["display_name"])] = vector / norm
            except Exception:
                continue
        return result

    def list_metadata(self) -> list[dict[str, object]]:
        rows = []
        for path in sorted(self.root.glob("*.json")):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                rows.append({"profile_path": str(path), "status": "INVALID"})
        return rows

    def remove(self, profile_id: str) -> None:
        safe = "".join(ch for ch in profile_id if ch.isalnum() or ch in "-_" )
        if safe != profile_id:
            raise ValueError("invalid profile id")
        for suffix in (".json", ".npy"):
            path = self.root / f"{safe}{suffix}"
            if path.exists():
                path.unlink()


class SpeakerTracker:
    def __init__(self, config: PipelineConfig, profiles: ProfileStore) -> None:
        self.config = config
        self.profiles = profiles
        self.clusters: list[_Cluster] = []

    def update(self, embedding: np.ndarray, source_end_sec: float) -> SpeakerDecision:
        vector = np.asarray(embedding, np.float32)
        similarities = [float(vector @ cluster.center) for cluster in self.clusters]
        if similarities and max(similarities) >= self.config.clustering_threshold:
            cluster = self.clusters[int(np.argmax(similarities))]
            merged = cluster.center * cluster.count + vector
            cluster.count += 1
            cluster.center = merged / max(float(np.linalg.norm(merged)), 1e-8)
            cluster.last_source_sec = source_end_sec
        else:
            cluster = _Cluster(
                cluster_id=len(self.clusters) + 1,
                center=vector.copy(),
                count=1,
                first_source_sec=max(0.0, source_end_sec - self.config.embedding_window_sec),
                last_source_sec=source_end_sec,
            )
            self.clusters.append(cluster)

        roster = self.profiles.load()
        scored = sorted(
            ((float(cluster.center @ profile), name) for name, profile in roster.items()),
            reverse=True,
        )
        top1 = scored[0][0] if scored else None
        top2 = scored[1][0] if len(scored) > 1 else -1.0 if scored else None
        margin = top1 - top2 if top1 is not None and top2 is not None else None
        evidence = source_end_sec - cluster.first_source_sec
        anonymous = f"Speaker_{cluster.cluster_id}"
        score_pass = top1 is not None and top1 >= self.config.identity_score_threshold
        margin_pass = margin is not None and margin >= self.config.identity_margin_threshold
        if score_pass and margin_pass and evidence >= self.config.identity_minimum_evidence_sec:
            display = scored[0][1]
            state = "confirmed"
        elif score_pass and margin_pass:
            display = f"{scored[0][1]} (tentative)"
            state = "tentative"
        else:
            display = anonymous
            state = "anonymous"
        return SpeakerDecision(
            anonymous_label=anonymous,
            display_label=display,
            state=state,
            top1_score=top1,
            top2_score=top2,
            margin=margin,
            evidence_sec=evidence,
            cluster_id=cluster.cluster_id,
        )
