"""Versioned spatial-evidence interface and an intentionally inert XVF stub."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import math
from typing import Mapping, Protocol, Sequence, runtime_checkable

from .contracts import (
    SPATIAL_EVIDENCE_INTERFACE_VERSION,
    XVF_NO_EFFECT_PLACEHOLDER_ID,
)


@dataclass(frozen=True)
class SpatialEvidence:
    """Future timestamp-aligned XVF evidence with legacy v1 aliases.

    The current H2 campaign records this contract only. No field in this
    structure is connected to audio, segmentation, clustering, identity, or
    transcript decisions.
    """

    timestamp_sec: float
    source_clock: str = "normalized_audio_sample_clock"
    aoa_deg: float | None = None
    aoa_confidence: float | None = None
    speech_energy: float | None = None
    speech_activity: bool | None = None
    direction_change_deg: float | None = None
    beamformer_state: Mapping[str, object] | None = None
    channel_state: Mapping[str, object] | None = None
    available: bool = False
    quality_flags: Sequence[str] = ()
    # Deprecated v1 constructor aliases. They are accepted so existing callers
    # keep working, but canonical v2 serialization uses the fields above.
    energy: float | None = None
    angle_of_arrival_deg: float | None = None
    angle_confidence: float | None = None
    direction_change: bool | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.timestamp_sec) or self.timestamp_sec < 0:
            raise ValueError("timestamp_sec must be finite and non-negative")
        if not isinstance(self.source_clock, str) or not self.source_clock.strip():
            raise ValueError("source_clock must be a non-empty string")
        if not isinstance(self.available, bool):
            raise ValueError("available must be boolean")
        if self.speech_activity is not None and not isinstance(
            self.speech_activity, bool
        ):
            raise ValueError("speech_activity must be boolean when supplied")
        if self.direction_change is not None and not isinstance(
            self.direction_change, bool
        ):
            raise ValueError("direction_change must be boolean when supplied")

        self._merge_legacy_alias("speech_energy", "energy")
        self._merge_legacy_alias("aoa_deg", "angle_of_arrival_deg")
        self._merge_legacy_alias("aoa_confidence", "angle_confidence")
        for name in (
            "speech_energy",
            "aoa_deg",
            "aoa_confidence",
            "direction_change_deg",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite when supplied")
        if self.aoa_confidence is not None and not 0 <= self.aoa_confidence <= 1:
            raise ValueError("aoa_confidence must be in [0, 1]")

        for name in ("beamformer_state", "channel_state"):
            value = getattr(self, name)
            if value is not None:
                if not isinstance(value, Mapping) or not all(
                    isinstance(key, str) for key in value
                ):
                    raise ValueError(f"{name} must be a string-keyed mapping")
                copied = deepcopy(dict(value))
                try:
                    json.dumps(copied, allow_nan=False)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{name} must be finite JSON data") from exc
                object.__setattr__(self, name, copied)

        if isinstance(self.quality_flags, (str, bytes)):
            raise ValueError("quality_flags must be a sequence of flag strings")
        flags = tuple(self.quality_flags)
        if any(not isinstance(flag, str) or not flag.strip() for flag in flags):
            raise ValueError("quality_flags must contain non-empty strings")
        object.__setattr__(self, "quality_flags", tuple(sorted(set(flags))))

    def _merge_legacy_alias(self, canonical_name: str, legacy_name: str) -> None:
        canonical = getattr(self, canonical_name)
        legacy = getattr(self, legacy_name)
        if canonical is not None and legacy is not None and canonical != legacy:
            raise ValueError(
                f"{canonical_name} and deprecated {legacy_name} disagree"
            )
        if canonical is None and legacy is not None:
            object.__setattr__(self, canonical_name, legacy)

    def to_jsonable(self) -> dict[str, object]:
        """Return only the canonical v2 frame fields."""

        return {
            "timestamp_sec": self.timestamp_sec,
            "source_clock": self.source_clock,
            "aoa_deg": self.aoa_deg,
            "aoa_confidence": self.aoa_confidence,
            "speech_energy": self.speech_energy,
            "speech_activity": self.speech_activity,
            "direction_change_deg": self.direction_change_deg,
            "beamformer_state": deepcopy(self.beamformer_state),
            "channel_state": deepcopy(self.channel_state),
            "available": self.available,
            "quality_flags": list(self.quality_flags),
        }


@dataclass(frozen=True)
class SpatialEvidenceReceipt:
    """Provenance receipt proving that the placeholder applied no policy effect."""

    interface_version: str
    implementation_id: str
    status: str
    evidence_present: bool
    evidence_available: bool = False
    source_clock: str | None = None
    evidence_values_affect_results: bool = False
    missing_or_default_evidence_affects_results: bool = False
    applied_to_audio: bool = False
    applied_to_segmentation: bool = False
    applied_to_clustering: bool = False
    applied_to_identity: bool = False
    applied_to_transcript: bool = False

    def to_jsonable(self) -> dict[str, object]:
        return asdict(self)


@runtime_checkable
class SpatialEvidenceInterface(Protocol):
    """Future additive interface; v2 consumers must remain independently gated."""

    interface_version: str
    implementation_id: str

    def observe(self, evidence: SpatialEvidence | None) -> SpatialEvidenceReceipt:
        """Record availability without affecting the audio-only decision path."""

    def pass_through_event(
        self,
        event: Mapping[str, object],
        evidence: SpatialEvidence | None = None,
    ) -> dict[str, object]:
        """Return an equivalent event document without adding spatial fields."""


class NoEffectXVFPlaceholder:
    """Disabled XVF integration point that is provably event-preserving."""

    interface_version = SPATIAL_EVIDENCE_INTERFACE_VERSION
    implementation_id = XVF_NO_EFFECT_PLACEHOLDER_ID

    def observe(self, evidence: SpatialEvidence | None) -> SpatialEvidenceReceipt:
        return SpatialEvidenceReceipt(
            interface_version=self.interface_version,
            implementation_id=self.implementation_id,
            status="DISABLED_NO_EFFECT_PLACEHOLDER",
            evidence_present=evidence is not None,
            evidence_available=bool(evidence is not None and evidence.available),
            source_clock=evidence.source_clock if evidence is not None else None,
        )

    def pass_through_event(
        self,
        event: Mapping[str, object],
        evidence: SpatialEvidence | None = None,
    ) -> dict[str, object]:
        del evidence
        return deepcopy(dict(event))
