"""Small backend-neutral contracts shared by audio, models, UI, and future XVF."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class SpatialEvidence:
    """Optional XVF-aligned evidence; it has no result effect in this version."""

    source_start_sec: float
    source_end_sec: float
    energy: float | None = None
    angle_deg: float | None = None
    angle_confidence: float | None = None
    direction_change: bool = False
    source_clock: str = "audio_sample_clock"
    provider: str = "none"

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineEvent:
    event_type: str
    source_time_sec: float
    payload: Mapping[str, Any] = field(default_factory=dict)
    wall_time_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = "edge-speech-event.v1"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "source_time_sec": round(float(self.source_time_sec), 6),
            "wall_time_utc": self.wall_time_utc,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class SpeakerDecision:
    anonymous_label: str
    display_label: str
    state: str
    top1_score: float | None
    top2_score: float | None
    margin: float | None
    evidence_sec: float
    cluster_id: int

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)

