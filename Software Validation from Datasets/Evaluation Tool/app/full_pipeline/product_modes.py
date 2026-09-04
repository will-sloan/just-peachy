"""H2 product-mode and result-affecting runtime tuning contracts.

The original 18-pipeline runtime predates the H2 product pivot.  This module is
additive: callers that do not select a product mode keep the legacy behaviour,
while H2 callers receive an explicit, JSON-serializable and hash-bound tuning
identity.  Only knobs that are connected to executable runtime behaviour are
accepted here.  Unimplemented research axes remain visible through
``capability_contract`` instead of being silently recorded as if they ran.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import asdict, dataclass, replace
from enum import Enum
import hashlib
import json
import math
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for typing only
    from .identity import IdentityPolicy, IdentityTransition


H2_RUNTIME_TUNING_SCHEMA_VERSION = "h2-runtime-tuning.v4"
H2_RUNTIME_TUNING_V3_SCHEMA_VERSION = "h2-runtime-tuning.v3"
H2_RUNTIME_TUNING_V2_SCHEMA_VERSION = "h2-runtime-tuning.v2"
H2_RUNTIME_TUNING_LEGACY_SCHEMA_VERSION = "h2-runtime-tuning.v1"
H2_SESSION_MEMORY_SCHEMA_VERSION = "h2-session-memory.v2"


class H2ProductMode(str, Enum):
    """Selectable H2 user-visible behavior over the same model stack."""

    KNOWN_ONLY = "H2_KNOWN_ONLY"
    SESSION_ANONYMOUS = "H2_SESSION_ANONYMOUS"
    SESSION_MEMORY_ENHANCED = "H2_SESSION_MEMORY_ENHANCED"


@dataclass(frozen=True)
class H2ModeBehavior:
    mode: H2ProductMode
    public_unknown_style: str
    anonymous_profiles_across_turns: bool
    confirmed_name_inheritance: bool
    short_turn_inheritance: bool
    active_roster: bool
    delete_anonymous_state_on_end: bool = True

    def public_unknown_label(self, internal_label: str) -> str:
        """Translate the private ``Unknown_N`` allocator label for the UI."""

        if self.public_unknown_style == "generic":
            return "Unknown"
        ordinal = internal_label.rsplit("_", 1)[-1]
        return f"Speaker_{ordinal}" if ordinal.isdigit() else "Speaker"


MODE_BEHAVIORS: Mapping[H2ProductMode, H2ModeBehavior] = {
    H2ProductMode.KNOWN_ONLY: H2ModeBehavior(
        mode=H2ProductMode.KNOWN_ONLY,
        public_unknown_style="generic",
        anonymous_profiles_across_turns=False,
        confirmed_name_inheritance=True,
        short_turn_inheritance=False,
        active_roster=False,
    ),
    H2ProductMode.SESSION_ANONYMOUS: H2ModeBehavior(
        mode=H2ProductMode.SESSION_ANONYMOUS,
        public_unknown_style="session_speaker",
        anonymous_profiles_across_turns=True,
        confirmed_name_inheritance=False,
        short_turn_inheritance=False,
        active_roster=False,
    ),
    H2ProductMode.SESSION_MEMORY_ENHANCED: H2ModeBehavior(
        mode=H2ProductMode.SESSION_MEMORY_ENHANCED,
        public_unknown_style="session_speaker",
        anonymous_profiles_across_turns=True,
        confirmed_name_inheritance=True,
        short_turn_inheritance=True,
        active_roster=True,
    ),
}


@dataclass(frozen=True)
class H2RuntimeTuning:
    """Executable H2 tuning with a stable scientific identity.

    The defaults reproduce the currently implemented H2 baseline mechanics.
    They do not claim that the configuration is selected or frozen; the H2
    controller owns that scientific lifecycle.
    """

    product_mode: H2ProductMode = H2ProductMode.SESSION_MEMORY_ENHANCED

    # Truthful Pyannote rolling-frontier controls.  The installed bidirectional
    # checkpoint remains fixed to 10 s input and 5 s lookahead.
    segmentation_hop_sec: float = 0.75
    segmentation_onset: float = 0.50
    segmentation_offset: float = 0.50
    segmentation_min_speech_sec: float = 0.0
    segmentation_min_silence_sec: float = 0.0

    # Causal ReDim windowing and online clustering.
    embedding_window_sec: float = 1.50
    embedding_hop_sec: float = 0.75
    minimum_embedding_sec: float = 0.75
    clustering_threshold: float = 0.35
    short_turn_attach_gap_sec: float = 0.50
    redim_execution_strategy: str = "R2_ONE_SHARED_MODEL"
    embedding_reuse_qualification_sha256: str | None = None
    overlap_policy: str = "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY"
    identity_accumulation: str = "accumulated_window"
    boundary_correction_ms: int = 0
    paragraph_policy: str = "T3_PAUSE_ASR_SPEAKER_CHANGE"
    paragraph_pause_sec: float = 0.80
    paragraph_max_words: int = 80

    # Open-set policy controls.  ``None`` means retain the base calibrated H2
    # value rather than inventing a new threshold.
    score_threshold: float | None = None
    margin_threshold: float | None = None
    minimum_evidence_sec: float | None = None
    minimum_embedding_consistency: float | None = None
    consecutive_passes_to_confirm: int | None = None
    consecutive_failures_to_release: int | None = None
    hysteresis: float | None = None
    identity_expiry_sec: float | None = None
    identity_expiry_mode: str = "source_clock"
    hysteresis_policy: str | None = None
    adaptive_early_max_evidence_sec: float = 1.5
    adaptive_standard_evidence_sec: float = 3.0
    adaptive_early_score_delta: float = 0.05
    adaptive_early_margin_delta: float = 0.02
    adaptive_medium_score_delta: float = 0.02
    adaptive_medium_margin_delta: float = 0.01
    memory_level: str | None = None

    # M4/M5 are explicit development policies.  ``None`` keeps historical
    # M0-M3 identities byte-for-byte stable and prevents an uncalibrated decay
    # or reconciliation policy from silently becoming result affecting.
    confidence_decay_half_life_sec: float | None = None
    confidence_decay_release_floor: float = 0.25
    cluster_reconciliation_threshold: float | None = None
    cluster_reconciliation_max_gap_sec: float = 120.0
    cluster_reconciliation_min_embeddings: int = 2

    # Bounded product state.  These limits are part of result identity because
    # eviction can affect long-session output.
    unmatched_embedding_retention_sec: float = 3.0
    identity_observation_retention_sec: float = 120.0
    maximum_identity_observations_per_cluster: int = 32
    maximum_cluster_embeddings: int = 128
    maximum_session_speakers: int = 64
    maximum_identity_history_per_cluster: int = 64
    maximum_roster_entries: int = 64
    maximum_session_event_history: int = 512
    retroactive_correction_sec: float = 30.0
    short_turn_inheritance_max_sec: float = 0.75

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_mode", H2ProductMode(self.product_mode))
        positive = (
            "segmentation_hop_sec",
            "embedding_window_sec",
            "embedding_hop_sec",
            "minimum_embedding_sec",
            "unmatched_embedding_retention_sec",
            "identity_observation_retention_sec",
            "retroactive_correction_sec",
            "short_turn_inheritance_max_sec",
            "paragraph_pause_sec",
            "adaptive_early_max_evidence_sec",
            "adaptive_standard_evidence_sec",
        )
        for name in positive:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
        if self.embedding_hop_sec > self.embedding_window_sec:
            raise ValueError("embedding_hop_sec must not exceed embedding_window_sec")
        if self.minimum_embedding_sec > self.embedding_window_sec:
            raise ValueError("minimum_embedding_sec must not exceed embedding_window_sec")
        for name in ("segmentation_onset", "segmentation_offset"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        for name in ("segmentation_min_speech_sec", "segmentation_min_silence_sec"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        if not -1.0 <= self.clustering_threshold <= 1.0:
            raise ValueError("clustering_threshold must be in [-1, 1]")
        if self.short_turn_attach_gap_sec < 0:
            raise ValueError("short_turn_attach_gap_sec must be >= 0")
        if self.redim_execution_strategy not in {
            "R1_TWO_INDEPENDENT_MODELS",
            "R2_ONE_SHARED_MODEL",
            "R3_EXACT_WINDOW_EMBEDDING_REUSE",
            "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
        }:
            raise ValueError("unsupported ReDim execution strategy")
        qualification = self.embedding_reuse_qualification_sha256
        if qualification is not None and (
            len(qualification) != 64
            or any(
                character not in "0123456789abcdef"
                for character in qualification.lower()
            )
        ):
            raise ValueError(
                "embedding_reuse_qualification_sha256 must be a SHA-256 digest"
            )
        if self.redim_execution_strategy in {
            "R1_TWO_INDEPENDENT_MODELS",
            "R2_ONE_SHARED_MODEL",
        } and qualification is not None:
            raise ValueError("R1/R2 must not carry an embedding-reuse qualification")
        if self.overlap_policy not in {
            "INCLUDE_PREDICTED_OVERLAP",
            "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
        }:
            raise ValueError(
                "runtime currently implements only INCLUDE_PREDICTED_OVERLAP and "
                "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY"
            )
        if self.identity_accumulation not in {
            "recent_window",
            "accumulated_window",
        }:
            raise ValueError("unsupported identity_accumulation")
        if self.boundary_correction_ms not in {0, 250, 500, 750, 1000}:
            raise ValueError(
                "boundary_correction_ms must be one of 0, 250, 500, 750, 1000"
            )
        if self.paragraph_policy not in {
            "T1_ASR_ENDPOINT_PUNCTUATION",
            "T2_PAUSE_ASR_ENDPOINT",
            "T3_PAUSE_ASR_SPEAKER_CHANGE",
            "T4_SPEAKER_CHANGE_DOMINANT",
        }:
            raise ValueError("unsupported paragraph_policy")
        if self.paragraph_max_words < 1:
            raise ValueError("paragraph_max_words must be >= 1")
        for name in (
            "maximum_identity_observations_per_cluster",
            "maximum_cluster_embeddings",
            "maximum_session_speakers",
            "maximum_identity_history_per_cluster",
            "maximum_roster_entries",
            "maximum_session_event_history",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")
        for name in (
            "score_threshold",
            "margin_threshold",
            "minimum_evidence_sec",
            "minimum_embedding_consistency",
            "hysteresis",
            "identity_expiry_sec",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite when supplied")
        if self.margin_threshold is not None and self.margin_threshold < 0:
            raise ValueError("margin_threshold must be >= 0")
        if self.minimum_evidence_sec is not None and self.minimum_evidence_sec <= 0:
            raise ValueError("minimum_evidence_sec must be > 0")
        if self.minimum_embedding_consistency is not None and not (
            -1.0 <= self.minimum_embedding_consistency <= 1.0
        ):
            raise ValueError("minimum_embedding_consistency must be in [-1, 1]")
        if self.consecutive_passes_to_confirm is not None and (
            self.consecutive_passes_to_confirm < 1
        ):
            raise ValueError("consecutive_passes_to_confirm must be >= 1")
        if self.consecutive_failures_to_release is not None and (
            self.consecutive_failures_to_release < 1
        ):
            raise ValueError("consecutive_failures_to_release must be >= 1")
        if self.hysteresis is not None and self.hysteresis < 0:
            raise ValueError("hysteresis must be >= 0")
        if self.identity_expiry_sec is not None and self.identity_expiry_sec <= 0:
            raise ValueError("identity_expiry_sec must be > 0")
        if self.identity_expiry_mode not in {"source_clock", "end_session"}:
            raise ValueError("identity_expiry_mode must be source_clock or end_session")
        if self.hysteresis_policy is not None and self.hysteresis_policy not in {
            "H0_ONE_PASS_DIAGNOSTIC",
            "H1_TWO_CONFIRM_TWO_RELEASE",
            "H2A_ADAPTIVE_EARLY",
            "H3_THREE_CONFIRM_SAFE",
            "H4_DURATION_DEPENDENT",
        }:
            raise ValueError("unsupported named hysteresis policy")
        if self.adaptive_early_max_evidence_sec >= self.adaptive_standard_evidence_sec:
            raise ValueError("adaptive evidence boundaries must be increasing")
        for name in (
            "adaptive_early_score_delta",
            "adaptive_early_margin_delta",
            "adaptive_medium_score_delta",
            "adaptive_medium_margin_delta",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        if self.memory_level not in {
            None,
            "M0_STATELESS",
            "M1_CLUSTER",
            "M2_CONFIRMED_NAME",
            "M3_SHORT_TURN",
            "M4_ACTIVE_ROSTER_DECAY",
            "M5_CLUSTER_RECONCILIATION",
        }:
            raise ValueError("unsupported session-memory level")
        if self.confidence_decay_half_life_sec is not None and (
            not math.isfinite(self.confidence_decay_half_life_sec)
            or self.confidence_decay_half_life_sec <= 0
        ):
            raise ValueError("confidence_decay_half_life_sec must be finite and > 0")
        if (
            not math.isfinite(self.confidence_decay_release_floor)
            or not 0.0 < self.confidence_decay_release_floor < 1.0
        ):
            raise ValueError("confidence_decay_release_floor must be in (0, 1)")
        if self.cluster_reconciliation_threshold is not None and (
            not math.isfinite(self.cluster_reconciliation_threshold)
            or not -1.0 <= self.cluster_reconciliation_threshold <= 1.0
        ):
            raise ValueError("cluster_reconciliation_threshold must be in [-1, 1]")
        if (
            not math.isfinite(self.cluster_reconciliation_max_gap_sec)
            or self.cluster_reconciliation_max_gap_sec <= 0
        ):
            raise ValueError(
                "cluster_reconciliation_max_gap_sec must be finite and > 0"
            )
        if self.cluster_reconciliation_min_embeddings < 2:
            raise ValueError("cluster_reconciliation_min_embeddings must be >= 2")
        if self.memory_level in {
            "M4_ACTIVE_ROSTER_DECAY",
            "M5_CLUSTER_RECONCILIATION",
        } and self.confidence_decay_half_life_sec is None:
            raise ValueError(
                "M4/M5 require a development-calibrated confidence decay half-life"
            )
        if (
            self.memory_level == "M5_CLUSTER_RECONCILIATION"
            and self.cluster_reconciliation_threshold is None
        ):
            raise ValueError(
                "M5 requires a development-calibrated reconciliation threshold"
            )
        if self.memory_level not in {
            "M4_ACTIVE_ROSTER_DECAY",
            "M5_CLUSTER_RECONCILIATION",
        } and self.confidence_decay_half_life_sec is not None:
            raise ValueError("confidence decay is result affecting only for M4/M5")
        if (
            self.memory_level != "M5_CLUSTER_RECONCILIATION"
            and self.cluster_reconciliation_threshold is not None
        ):
            raise ValueError("cluster reconciliation is result affecting only for M5")

    @property
    def behavior(self) -> H2ModeBehavior:
        base = MODE_BEHAVIORS[self.product_mode]
        if (
            self.product_mode is not H2ProductMode.SESSION_MEMORY_ENHANCED
            or self.memory_level is None
        ):
            return base
        overrides = {
            "M0_STATELESS": (False, False, False, False),
            "M1_CLUSTER": (True, False, False, False),
            "M2_CONFIRMED_NAME": (True, True, False, False),
            "M3_SHORT_TURN": (True, True, True, False),
            "M4_ACTIVE_ROSTER_DECAY": (True, True, True, True),
            "M5_CLUSTER_RECONCILIATION": (True, True, True, True),
        }
        anonymous, confirmed, short_turn, roster = overrides[self.memory_level]
        return replace(
            base,
            anonymous_profiles_across_turns=anonymous,
            confirmed_name_inheritance=confirmed,
            short_turn_inheritance=short_turn,
            active_roster=roster,
        )

    def to_jsonable(self) -> dict[str, object]:
        value = asdict(self)
        value["product_mode"] = self.product_mode.value
        advanced_memory = self.memory_level in {
            "M4_ACTIVE_ROSTER_DECAY",
            "M5_CLUSTER_RECONCILIATION",
        }
        historical = not advanced_memory and self.redim_execution_strategy in {
            "R1_TWO_INDEPENDENT_MODELS",
            "R2_ONE_SHARED_MODEL",
        }
        if historical:
            # Preserve pre-v3 R1/R2 identities exactly; the new field did not
            # exist and None must not become result affecting retroactively.
            value.pop("embedding_reuse_qualification_sha256")
        if not advanced_memory:
            for name in (
                "confidence_decay_half_life_sec",
                "confidence_decay_release_floor",
                "cluster_reconciliation_threshold",
                "cluster_reconciliation_max_gap_sec",
                "cluster_reconciliation_min_embeddings",
            ):
                value.pop(name)
        return {
            "schema_version": (
                H2_RUNTIME_TUNING_V2_SCHEMA_VERSION
                if historical
                else (
                    H2_RUNTIME_TUNING_SCHEMA_VERSION
                    if advanced_memory
                    else H2_RUNTIME_TUNING_V3_SCHEMA_VERSION
                )
            ),
            **value,
            "scientific_capabilities": (
                _legacy_v2_capability_contract()
                if historical
                else (
                    self.capability_contract()
                    if advanced_memory
                    else _legacy_v3_capability_contract()
                )
            ),
        }

    @property
    def identity_sha256(self) -> str:
        payload = json.dumps(
            self.to_jsonable(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def __hash__(self) -> int:
        return int(self.identity_sha256[:16], 16)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "H2RuntimeTuning":
        payload = dict(value)
        schema_version = payload.pop("schema_version", None)
        if schema_version not in {
            None,
            H2_RUNTIME_TUNING_SCHEMA_VERSION,
            H2_RUNTIME_TUNING_V3_SCHEMA_VERSION,
            H2_RUNTIME_TUNING_V2_SCHEMA_VERSION,
            H2_RUNTIME_TUNING_LEGACY_SCHEMA_VERSION,
        }:
            raise ValueError(f"unsupported runtime tuning schema: {schema_version}")
        payload.pop("scientific_capabilities", None)
        supplied_identity = payload.pop("identity_sha256", None)
        v2_only_fields = {
            "consecutive_failures_to_release",
            "identity_expiry_mode",
            "hysteresis_policy",
            "adaptive_early_max_evidence_sec",
            "adaptive_standard_evidence_sec",
            "adaptive_early_score_delta",
            "adaptive_early_margin_delta",
            "adaptive_medium_score_delta",
            "adaptive_medium_margin_delta",
            "memory_level",
        }
        v3_only_fields = {"embedding_reuse_qualification_sha256"}
        v4_only_fields = {
            "confidence_decay_half_life_sec",
            "confidence_decay_release_floor",
            "cluster_reconciliation_threshold",
            "cluster_reconciliation_max_gap_sec",
            "cluster_reconciliation_min_embeddings",
        }
        if schema_version == H2_RUNTIME_TUNING_LEGACY_SCHEMA_VERSION:
            unexpected_v2 = sorted(
                set(payload) & (v2_only_fields | v3_only_fields | v4_only_fields)
            )
            if unexpected_v2:
                raise ValueError(
                    "legacy v1 runtime tuning contains unbound v2 fields: "
                    + ", ".join(unexpected_v2)
                )
        if schema_version == H2_RUNTIME_TUNING_V2_SCHEMA_VERSION:
            unexpected_v3 = sorted(set(payload) & (v3_only_fields | v4_only_fields))
            if unexpected_v3:
                raise ValueError(
                    "legacy v2 runtime tuning contains unbound v3 fields: "
                    + ", ".join(unexpected_v3)
                )
        if schema_version == H2_RUNTIME_TUNING_V3_SCHEMA_VERSION:
            unexpected_v4 = sorted(set(payload) & v4_only_fields)
            if unexpected_v4:
                raise ValueError(
                    "legacy v3 runtime tuning contains unbound v4 fields: "
                    + ", ".join(unexpected_v4)
                )
        if "mode" in payload:
            if "product_mode" in payload:
                raise ValueError("runtime tuning may not contain both mode and product_mode")
            payload["product_mode"] = payload.pop("mode")
        known = set(cls.__dataclass_fields__)
        unknown = sorted(set(payload) - known)
        if unknown:
            raise ValueError(f"unsupported runtime tuning keys: {', '.join(unknown)}")
        tuning = cls(**payload)  # type: ignore[arg-type]
        if schema_version in {
            H2_RUNTIME_TUNING_LEGACY_SCHEMA_VERSION,
            H2_RUNTIME_TUNING_V2_SCHEMA_VERSION,
        } and tuning.redim_execution_strategy.startswith(("R3_", "R4_")):
            raise ValueError("legacy runtime tuning cannot identify R3/R4 behavior")
        if supplied_identity is not None:
            if schema_version == H2_RUNTIME_TUNING_LEGACY_SCHEMA_VERSION:
                expected = tuning._legacy_v1_identity_sha256()
            elif schema_version == H2_RUNTIME_TUNING_V2_SCHEMA_VERSION:
                expected = tuning._legacy_v2_identity_sha256()
            else:
                expected = tuning.identity_sha256
            if str(supplied_identity) != expected:
                raise ValueError("runtime tuning identity_sha256 mismatch")
        return tuning

    @classmethod
    def coerce(
        cls,
        value: "H2RuntimeTuning | Mapping[str, object] | None",
        *,
        product_mode: H2ProductMode | str | None = None,
    ) -> "H2RuntimeTuning | None":
        if value is None and product_mode is None:
            return None
        tuning = value if isinstance(value, cls) else cls.from_mapping(value or {})
        if product_mode is None:
            return tuning
        mode = H2ProductMode(product_mode)
        mapping_declared_mode = isinstance(value, Mapping) and (
            "mode" in value or "product_mode" in value
        )
        if tuning.product_mode is not mode and (
            isinstance(value, cls) or mapping_declared_mode
        ):
            raise ValueError("product_mode conflicts with runtime_tuning.product_mode")
        return replace(tuning, product_mode=mode)

    def apply_identity_policy(self, base: "IdentityPolicy") -> "IdentityPolicy":
        """Bind executable identity overrides without losing calibration provenance."""

        updates: dict[str, object] = {
            "policy_id": (
                "h2_product_runtime.v4:"
                if self.memory_level in {
                    "M4_ACTIVE_ROSTER_DECAY",
                    "M5_CLUSTER_RECONCILIATION",
                }
                else (
                    "h2_product_runtime.v3:"
                    if self.redim_execution_strategy.startswith(("R3_", "R4_"))
                    else "h2_product_runtime.v2:"
                )
            )
            + self.identity_sha256,
            "decision_policy_sha256": self.identity_sha256,
            "frozen_anchor": False,
        }
        for tuning_name, policy_name in (
            ("score_threshold", "score_threshold"),
            ("margin_threshold", "margin_threshold"),
            ("minimum_evidence_sec", "minimum_evidence_sec"),
            ("minimum_embedding_consistency", "minimum_embedding_consistency"),
            ("consecutive_passes_to_confirm", "consecutive_passes_to_confirm"),
            ("consecutive_failures_to_release", "consecutive_failures_to_release"),
            ("hysteresis", "hysteresis"),
            ("identity_expiry_sec", "identity_expiry_sec"),
            ("hysteresis_policy", "hysteresis_policy"),
        ):
            value = getattr(self, tuning_name)
            if value is not None:
                updates[policy_name] = value
        updates.update(
            {
                "identity_expiry_mode": self.identity_expiry_mode,
                "adaptive_early_max_evidence_sec": (
                    self.adaptive_early_max_evidence_sec
                ),
                "adaptive_standard_evidence_sec": (
                    self.adaptive_standard_evidence_sec
                ),
                "adaptive_early_score_delta": self.adaptive_early_score_delta,
                "adaptive_early_margin_delta": self.adaptive_early_margin_delta,
                "adaptive_medium_score_delta": self.adaptive_medium_score_delta,
                "adaptive_medium_margin_delta": self.adaptive_medium_margin_delta,
            }
        )
        return replace(base, **updates)

    def _legacy_v1_identity_sha256(self) -> str:
        """Reproduce the pre-v2 hash for strict loading of saved v1 tunings."""

        value = asdict(self)
        for name in (
            "consecutive_failures_to_release",
            "identity_expiry_mode",
            "hysteresis_policy",
            "adaptive_early_max_evidence_sec",
            "adaptive_standard_evidence_sec",
            "adaptive_early_score_delta",
            "adaptive_early_margin_delta",
            "adaptive_medium_score_delta",
            "adaptive_medium_margin_delta",
            "memory_level",
            "embedding_reuse_qualification_sha256",
            "confidence_decay_half_life_sec",
            "confidence_decay_release_floor",
            "cluster_reconciliation_threshold",
            "cluster_reconciliation_max_gap_sec",
            "cluster_reconciliation_min_embeddings",
        ):
            value.pop(name)
        value["product_mode"] = self.product_mode.value
        payload = {
            "schema_version": H2_RUNTIME_TUNING_LEGACY_SCHEMA_VERSION,
            **value,
            "scientific_capabilities": _legacy_v1_capability_contract(),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _legacy_v2_identity_sha256(self) -> str:
        """Reproduce pre-v3 R1/R2 hashes for strict saved-tuning loading."""

        value = asdict(self)
        for name in (
            "embedding_reuse_qualification_sha256",
            "confidence_decay_half_life_sec",
            "confidence_decay_release_floor",
            "cluster_reconciliation_threshold",
            "cluster_reconciliation_max_gap_sec",
            "cluster_reconciliation_min_embeddings",
        ):
            value.pop(name)
        value["product_mode"] = self.product_mode.value
        payload = {
            "schema_version": H2_RUNTIME_TUNING_V2_SCHEMA_VERSION,
            **value,
            "scientific_capabilities": _legacy_v2_capability_contract(),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def capability_contract() -> dict[str, object]:
        return {
            "implemented": [
                "three_product_label_and_memory_modes",
                "segmentation_hop_onset_offset_min_on_min_off",
                "embedding_window_hop_minimum_duration",
                "online_clustering_threshold_and_short_turn_gap",
                "redim_R1_through_R4_with_checksum_strict_reuse",
                "overlap_include_and_exclude",
                "bounded_boundary_correction_0_to_1000ms",
                "paragraph_policies_T1_through_T4",
                "recent_or_accumulated_identity_windows",
                "open_set_threshold_margin_evidence_consistency",
                "confirmation_hysteresis_and_source_clock_expiry",
                "named_hysteresis_H0_H1_H2A_H3_H4",
                "consecutive_release_passes",
                "duration_dependent_and_adaptive_early_identity_gates",
                "end_session_identity_expiry",
                "memory_levels_M0_through_M5",
                "M4_active_roster_full_gallery_search_order_and_source_time_decay",
                "M5_causal_voice_timing_cluster_reconciliation",
                "bounded_roster_embedding_identity_and_correction_history",
            ],
            "not_implemented_do_not_schedule": [
                "zero_or_short_pyannote_lookahead_with_current_checkpoint",
                "defer_identity_until_non_overlap",
                "display_overlapping_speakers_when_ambiguous",
                "spatial_or_XVF_result_effects",
            ],
        }


def _legacy_v2_capability_contract() -> dict[str, object]:
    """Exact capability payload used by pre-v3 R1/R2 tuning identities."""

    return {
        "implemented": [
            "three_product_label_and_memory_modes",
            "segmentation_hop_onset_offset_min_on_min_off",
            "embedding_window_hop_minimum_duration",
            "online_clustering_threshold_and_short_turn_gap",
            "redim_R1_and_R2",
            "overlap_include_and_exclude",
            "bounded_boundary_correction_0_to_1000ms",
            "paragraph_policies_T1_through_T4",
            "recent_or_accumulated_identity_windows",
            "open_set_threshold_margin_evidence_consistency",
            "confirmation_hysteresis_and_source_clock_expiry",
            "named_hysteresis_H0_H1_H2A_H3_H4",
            "consecutive_release_passes",
            "duration_dependent_and_adaptive_early_identity_gates",
            "end_session_identity_expiry",
            "memory_levels_M0_through_M3",
            "bounded_roster_embedding_identity_and_correction_history",
        ],
        "not_implemented_do_not_schedule": [
            "zero_or_short_pyannote_lookahead_with_current_checkpoint",
            "R3_exact_embedding_reuse",
            "R4_hybrid_reuse_with_identity_aggregation",
            "defer_identity_until_non_overlap",
            "display_overlapping_speakers_when_ambiguous",
            "M4_active_roster_as_calibrated_search_prior",
            "M5_fragmented_cluster_reconciliation",
            "spatial_or_XVF_result_effects",
        ],
    }


def _legacy_v3_capability_contract() -> dict[str, object]:
    """Exact capability payload used by pre-v4 R3/R4 tuning identities."""

    return {
        "implemented": [
            "three_product_label_and_memory_modes",
            "segmentation_hop_onset_offset_min_on_min_off",
            "embedding_window_hop_minimum_duration",
            "online_clustering_threshold_and_short_turn_gap",
            "redim_R1_through_R4_with_checksum_strict_reuse",
            "overlap_include_and_exclude",
            "bounded_boundary_correction_0_to_1000ms",
            "paragraph_policies_T1_through_T4",
            "recent_or_accumulated_identity_windows",
            "open_set_threshold_margin_evidence_consistency",
            "confirmation_hysteresis_and_source_clock_expiry",
            "named_hysteresis_H0_H1_H2A_H3_H4",
            "consecutive_release_passes",
            "duration_dependent_and_adaptive_early_identity_gates",
            "end_session_identity_expiry",
            "memory_levels_M0_through_M3",
            "bounded_roster_embedding_identity_and_correction_history",
        ],
        "not_implemented_do_not_schedule": [
            "zero_or_short_pyannote_lookahead_with_current_checkpoint",
            "defer_identity_until_non_overlap",
            "display_overlapping_speakers_when_ambiguous",
            "M4_active_roster_as_calibrated_search_prior",
            "M5_fragmented_cluster_reconciliation",
            "spatial_or_XVF_result_effects",
        ],
    }


def _legacy_v1_capability_contract() -> dict[str, object]:
    return {
        "implemented": [
            "three_product_label_and_memory_modes",
            "segmentation_hop_onset_offset_min_on_min_off",
            "embedding_window_hop_minimum_duration",
            "online_clustering_threshold_and_short_turn_gap",
            "redim_R1_and_R2",
            "overlap_include_and_exclude",
            "bounded_boundary_correction_0_to_1000ms",
            "paragraph_policies_T1_through_T4",
            "recent_or_accumulated_identity_windows",
            "open_set_threshold_margin_evidence_consistency",
            "confirmation_hysteresis_and_source_clock_expiry",
            "bounded_roster_embedding_identity_and_correction_history",
        ],
        "not_implemented_do_not_schedule": [
            "zero_or_short_pyannote_lookahead_with_current_checkpoint",
            "R3_exact_embedding_reuse",
            "R4_hybrid_reuse_with_identity_aggregation",
            "defer_identity_until_non_overlap",
            "display_overlapping_speakers_when_ambiguous",
            "spatial_or_XVF_result_effects",
        ],
    }


@dataclass
class _RosterEntry:
    anonymous_speaker_id: str
    public_label: str
    known_speaker_id: str | None
    identity_state: str
    first_seen_sec: float
    last_seen_sec: float
    last_verified_sec: float | None = None
    evidence_count: int = 0
    contradiction_count: int = 0
    expired: bool = False
    confidence_strength: float | None = None
    confidence_state: str = "unverified"

    def to_jsonable(self) -> dict[str, object]:
        return {
            **asdict(self),
            "spatial_evidence": {
                "available": False,
                "seat_or_direction": None,
                "result_effect": False,
            },
        }


class BoundedSessionMemory:
    """Bounded roster, source-time decay, and full-gallery search scheduling.

    The roster may change evaluation *order* for M4/M5, but never the scores,
    thresholds, margins, or gallery membership.  That distinction is enforced
    by :meth:`full_gallery_search_order` and recorded in every snapshot.
    """

    def __init__(self, tuning: H2RuntimeTuning) -> None:
        self.tuning = tuning
        self._roster: "OrderedDict[str, _RosterEntry]" = OrderedDict()
        self._history: deque[dict[str, object]] = deque(
            maxlen=tuning.maximum_session_event_history
        )

    def observe_cluster(
        self,
        *,
        anonymous_speaker_id: str,
        public_label: str,
        source_time_sec: float,
    ) -> None:
        entry = self._roster.get(anonymous_speaker_id)
        if entry is None:
            self._make_room()
            entry = _RosterEntry(
                anonymous_speaker_id=anonymous_speaker_id,
                public_label=public_label,
                known_speaker_id=None,
                identity_state="unknown",
                first_seen_sec=source_time_sec,
                last_seen_sec=source_time_sec,
            )
            self._roster[anonymous_speaker_id] = entry
        else:
            entry.public_label = public_label
            entry.last_seen_sec = source_time_sec
            entry.expired = False
            self._roster.move_to_end(anonymous_speaker_id)
        self._record("cluster_observed", anonymous_speaker_id, source_time_sec)

    def observe_identity(self, transition: "IdentityTransition") -> None:
        entry = self._roster.get(transition.anonymous_speaker_id)
        if entry is None:
            self.observe_cluster(
                anonymous_speaker_id=transition.anonymous_speaker_id,
                public_label=transition.speaker_label,
                source_time_sec=transition.source_time_sec,
            )
            entry = self._roster[transition.anonymous_speaker_id]
        entry.public_label = transition.speaker_label
        entry.known_speaker_id = transition.known_speaker_id
        entry.identity_state = transition.state.value
        entry.last_seen_sec = transition.source_time_sec
        entry.evidence_count += len(transition.evidence_event_ids)
        entry.expired = transition.state.value == "RELEASED"
        if (
            transition.known_speaker_id is not None
            and transition.confidence_strength is not None
        ):
            entry.last_verified_sec = transition.source_time_sec
            entry.confidence_strength = transition.confidence_strength
            entry.confidence_state = "fresh"
        elif entry.expired:
            entry.confidence_strength = 0.0
            entry.confidence_state = (
                "decayed"
                if transition.decision_reason == "identity_confidence_decayed"
                else "expired"
            )
        if transition.decision_reason in {
            "below_score_threshold",
            "below_margin_threshold",
            "challenger_confirmation_pending",
        }:
            entry.contradiction_count += 1
        self._roster.move_to_end(transition.anonymous_speaker_id)
        self._record(
            transition.decision_reason,
            transition.anonymous_speaker_id,
            transition.source_time_sec,
        )

    def advance_time(self, source_time_sec: float) -> None:
        """Update roster confidence from the source clock, never wall time."""

        if not math.isfinite(source_time_sec) or source_time_sec < 0:
            raise ValueError("source_time_sec must be finite and >= 0")
        half_life = self.tuning.confidence_decay_half_life_sec
        if half_life is None:
            return
        floor = self.tuning.confidence_decay_release_floor
        for entry in self._roster.values():
            if entry.last_verified_sec is None or entry.expired:
                continue
            age = max(0.0, source_time_sec - entry.last_verified_sec)
            strength = math.pow(0.5, age / half_life)
            entry.confidence_strength = strength
            if strength <= floor:
                entry.confidence_state = "decayed"
            elif strength < 1.0:
                entry.confidence_state = "decaying"
            else:
                entry.confidence_state = "fresh"

    def full_gallery_search_order(
        self,
        enrolled_speaker_ids: tuple[str, ...] | list[str],
        *,
        source_time_sec: float,
    ) -> tuple[str, ...]:
        """Return active-known IDs first while retaining every gallery member."""

        gallery = tuple(map(str, enrolled_speaker_ids))
        if len(gallery) != len(set(gallery)):
            raise ValueError("enrolled gallery contains duplicate speaker IDs")
        gallery_set = set(gallery)
        active = list(
            self.active_known_speaker_ids(
                gallery, source_time_sec=source_time_sec
            )
        )
        ordered = tuple(active + sorted(gallery_set - set(active)))
        if len(ordered) != len(gallery) or set(ordered) != gallery_set:
            raise RuntimeError("active-roster scheduling changed gallery membership")
        return ordered

    def active_known_speaker_ids(
        self,
        enrolled_speaker_ids: tuple[str, ...] | list[str],
        *,
        source_time_sec: float,
    ) -> tuple[str, ...]:
        """Return most-recently active enrolled identities in roster order."""

        self.advance_time(source_time_sec)
        gallery_set = set(map(str, enrolled_speaker_ids))
        active: list[str] = []
        for entry in reversed(tuple(self._roster.values())):
            known_id = entry.known_speaker_id
            if (
                known_id is not None
                and known_id in gallery_set
                and not entry.expired
                and entry.confidence_state != "decayed"
                and known_id not in active
            ):
                active.append(known_id)
        return tuple(active)

    def merge_clusters(
        self,
        *,
        survivor_cluster_id: str,
        source_cluster_id: str,
        source_time_sec: float,
    ) -> None:
        """Reconcile two roster rows without inventing identity evidence."""

        if survivor_cluster_id == source_cluster_id:
            raise ValueError("roster merge requires two distinct clusters")
        source = self._roster.pop(source_cluster_id, None)
        survivor = self._roster.get(survivor_cluster_id)
        if source is None:
            return
        if survivor is None:
            source.anonymous_speaker_id = survivor_cluster_id
            survivor = source
            self._roster[survivor_cluster_id] = survivor
        else:
            survivor.first_seen_sec = min(
                survivor.first_seen_sec, source.first_seen_sec
            )
            survivor.last_seen_sec = max(survivor.last_seen_sec, source.last_seen_sec)
            survivor.evidence_count += source.evidence_count
            survivor.contradiction_count += source.contradiction_count
            verified = [
                value
                for value in (survivor.last_verified_sec, source.last_verified_sec)
                if value is not None
            ]
            survivor.last_verified_sec = max(verified) if verified else None
            if (
                survivor.known_speaker_id is not None
                and source.known_speaker_id is not None
                and survivor.known_speaker_id != source.known_speaker_id
            ):
                survivor.known_speaker_id = None
                survivor.identity_state = "UNKNOWN_INSTANCE"
                survivor.public_label = "Unknown"
                survivor.confidence_strength = 0.0
                survivor.confidence_state = "identity_conflict"
            elif survivor.known_speaker_id is None:
                survivor.known_speaker_id = source.known_speaker_id
                survivor.identity_state = source.identity_state
                survivor.public_label = source.public_label
                survivor.confidence_strength = source.confidence_strength
                survivor.confidence_state = source.confidence_state
            survivor.expired = survivor.expired and source.expired
        survivor.last_seen_sec = max(survivor.last_seen_sec, source_time_sec)
        self._roster.move_to_end(survivor_cluster_id)
        self._record("cluster_reconciled", survivor_cluster_id, source_time_sec)

    def clear(self) -> None:
        self._roster.clear()
        self._history.clear()

    def snapshot(self) -> dict[str, object]:
        search_order_enabled = self.tuning.memory_level in {
            "M4_ACTIVE_ROSTER_DECAY",
            "M5_CLUSTER_RECONCILIATION",
        }
        return {
            "schema_version": H2_SESSION_MEMORY_SCHEMA_VERSION,
            "mode": self.tuning.product_mode.value,
            "scoring_effect": "search_order_only" if search_order_enabled else False,
            "search_order_enabled": search_order_enabled,
            "gallery_membership_effect": False,
            "full_gallery_safety_check_required": True,
            "roster_bound": self.tuning.maximum_roster_entries,
            "history_bound": self.tuning.maximum_session_event_history,
            "roster_count": len(self._roster),
            "history_count": len(self._history),
            "roster": [entry.to_jsonable() for entry in self._roster.values()],
            "history": list(self._history),
        }

    def _make_room(self) -> None:
        if len(self._roster) < self.tuning.maximum_roster_entries:
            return
        expired = next(
            (key for key, value in self._roster.items() if value.expired), None
        )
        self._roster.pop(expired if expired is not None else next(iter(self._roster)))

    def _record(self, kind: str, speaker_id: str, source_time_sec: float) -> None:
        self._history.append(
            {
                "event": kind,
                "anonymous_speaker_id": speaker_id,
                "source_time_sec": source_time_sec,
            }
        )


__all__ = [
    "BoundedSessionMemory",
    "H2ModeBehavior",
    "H2ProductMode",
    "H2RuntimeTuning",
    "H2_RUNTIME_TUNING_SCHEMA_VERSION",
    "H2_RUNTIME_TUNING_V3_SCHEMA_VERSION",
    "H2_RUNTIME_TUNING_V2_SCHEMA_VERSION",
    "H2_SESSION_MEMORY_SCHEMA_VERSION",
    "MODE_BEHAVIORS",
]
