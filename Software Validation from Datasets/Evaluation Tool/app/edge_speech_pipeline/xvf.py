"""Inactive XVF3800 provider boundary for future controlled fusion studies."""

from __future__ import annotations

from typing import Protocol

from .contracts import SpatialEvidence


class SpatialEvidenceProvider(Protocol):
    """Adapters must align metadata to the audio sample clock before returning it."""

    provider_id: str

    def evidence(self, source_start_sec: float, source_end_sec: float) -> SpatialEvidence:
        ...


class NoSpatialEvidence:
    """Frozen audio-only control. It cannot affect segmentation or identity."""

    provider_id = "none"

    def evidence(self, source_start_sec: float, source_end_sec: float) -> SpatialEvidence:
        return SpatialEvidence(
            source_start_sec=source_start_sec,
            source_end_sec=source_end_sec,
            provider=self.provider_id,
        )


__all__ = ["NoSpatialEvidence", "SpatialEvidenceProvider"]

