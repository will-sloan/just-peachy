"""Model-free open-set identity state and stable session speaker labels.

The scientific embedding workers produce raw candidate scores.  This module owns
only the causal decision state.  In particular, cosine scores are never treated
as probabilities and wall-clock/compute time is never used for identity expiry.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import math
from typing import Iterable, Mapping, Sequence


class IdentityState(str, Enum):
    """Internal session identity lifecycle required by the streaming runtime."""

    GENERIC = "GENERIC"
    TENTATIVE_KNOWN = "TENTATIVE_KNOWN"
    CONFIRMED_KNOWN = "CONFIRMED_KNOWN"
    UNKNOWN_INSTANCE = "UNKNOWN_INSTANCE"
    RELEASED = "RELEASED"


@dataclass(frozen=True)
class IdentityPolicy:
    """One open-set decision policy, including its calibration status."""

    hybrid_label: str
    policy_id: str
    score_threshold: float | None
    margin_threshold: float | None
    minimum_evidence_sec: float = 2.0
    minimum_embedding_consistency: float = 0.35
    consecutive_passes_to_confirm: int = 2
    hysteresis: float = 0.02
    identity_expiry_sec: float = 120.0
    tentative_visible: bool = True
    calibration_identity: str | None = None
    decision_policy_sha256: str | None = None
    calibration_protocol_id: str | None = None
    calibration_result_sha256: str | None = None
    target_fpir: float | None = None
    consistency_method: str = "frozen_mean_cosine_to_aggregate"
    hysteresis_score_mode: str = "frozen_top1"
    frozen_anchor: bool = False
    # Existing frozen policy hashes predate named H1 and historically used two
    # confirmations but one failed decision to release.  Keep that behavior
    # under an explicit legacy identity; corrected H1 is selected only through
    # checksum-bound h2-runtime-tuning.v2.
    hysteresis_policy: str = "LEGACY_TWO_CONFIRM_ONE_RELEASE"
    consecutive_failures_to_release: int = 2
    adaptive_early_max_evidence_sec: float = 1.5
    adaptive_standard_evidence_sec: float = 3.0
    adaptive_early_score_delta: float = 0.05
    adaptive_early_margin_delta: float = 0.02
    adaptive_medium_score_delta: float = 0.02
    adaptive_medium_margin_delta: float = 0.01
    identity_expiry_mode: str = "source_clock"

    def __post_init__(self) -> None:
        if not self.hybrid_label.strip() or not self.policy_id.strip():
            raise ValueError("hybrid_label and policy_id must be non-empty")
        if (self.score_threshold is None) != (self.margin_threshold is None):
            raise ValueError("score and margin thresholds must be resolved together")
        if self.score_threshold is not None and not math.isfinite(self.score_threshold):
            raise ValueError("score_threshold must be finite")
        if self.margin_threshold is not None and (
            not math.isfinite(self.margin_threshold) or self.margin_threshold < 0
        ):
            raise ValueError("margin_threshold must be finite and >= 0")
        if self.minimum_evidence_sec <= 0:
            raise ValueError("minimum_evidence_sec must be > 0")
        if not -1.0 <= self.minimum_embedding_consistency <= 1.0:
            raise ValueError("minimum_embedding_consistency must be in [-1, 1]")
        if self.consecutive_passes_to_confirm < 1:
            raise ValueError("consecutive_passes_to_confirm must be >= 1")
        if self.consecutive_failures_to_release < 1:
            raise ValueError("consecutive_failures_to_release must be >= 1")
        if self.hysteresis < 0 or self.identity_expiry_sec <= 0:
            raise ValueError(
                "hysteresis must be >= 0 and identity_expiry_sec must be > 0"
            )
        for name in ("decision_policy_sha256", "calibration_result_sha256"):
            value = getattr(self, name)
            if value is not None and (
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value.lower())
            ):
                raise ValueError(f"{name} must be a SHA-256 hex digest when present")
        if self.target_fpir is not None and not 0.0 <= self.target_fpir <= 1.0:
            raise ValueError("target_fpir must be in [0, 1] when present")
        if self.consistency_method != "frozen_mean_cosine_to_aggregate":
            raise ValueError("unsupported identity consistency method")
        if self.hysteresis_score_mode not in {"frozen_top1", "current_identity"}:
            raise ValueError("unsupported hysteresis score mode")
        if self.hysteresis_policy not in {
            "LEGACY_TWO_CONFIRM_ONE_RELEASE",
            "H0_ONE_PASS_DIAGNOSTIC",
            "H1_TWO_CONFIRM_TWO_RELEASE",
            "H2A_ADAPTIVE_EARLY",
            "H3_THREE_CONFIRM_SAFE",
            "H4_DURATION_DEPENDENT",
        }:
            raise ValueError("unsupported named hysteresis policy")
        if self.identity_expiry_mode not in {"source_clock", "end_session"}:
            raise ValueError("identity_expiry_mode must be source_clock or end_session")
        if not (
            0 < self.adaptive_early_max_evidence_sec
            < self.adaptive_standard_evidence_sec
        ):
            raise ValueError(
                "adaptive evidence boundaries must be positive and increasing"
            )
        for name in (
            "adaptive_early_score_delta",
            "adaptive_early_margin_delta",
            "adaptive_medium_score_delta",
            "adaptive_medium_margin_delta",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")

    @property
    def calibrated(self) -> bool:
        """Whether this policy may emit a known-speaker decision."""

        return self.score_threshold is not None and self.margin_threshold is not None

    @property
    def release_threshold(self) -> float | None:
        if self.score_threshold is None:
            return None
        return self.score_threshold - self.hysteresis

    def effective_gate(self, evidence_duration_sec: float) -> tuple[float | None, float | None, int]:
        """Return the causal score, margin, and confirmation gate for this pass.

        The method depends only on evidence available at the current source
        time.  It intentionally has no reference/truth input so the exact same
        method can be used by live execution and policy replay.
        """

        score = self.score_threshold
        margin = self.margin_threshold
        confirmations = self.consecutive_passes_to_confirm
        if self.hysteresis_policy == "H0_ONE_PASS_DIAGNOSTIC":
            confirmations = 1
        elif self.hysteresis_policy == "H3_THREE_CONFIRM_SAFE":
            confirmations = max(3, confirmations)
        elif self.hysteresis_policy in {
            "H2A_ADAPTIVE_EARLY",
            "H4_DURATION_DEPENDENT",
        }:
            if evidence_duration_sec <= self.adaptive_early_max_evidence_sec:
                if score is not None:
                    score += self.adaptive_early_score_delta
                if margin is not None:
                    margin += self.adaptive_early_margin_delta
                if self.hysteresis_policy == "H4_DURATION_DEPENDENT":
                    confirmations = max(3, confirmations)
            elif evidence_duration_sec <= self.adaptive_standard_evidence_sec:
                if score is not None:
                    score += self.adaptive_medium_score_delta
                if margin is not None:
                    margin += self.adaptive_medium_margin_delta
        return score, margin, confirmations

    @property
    def required_release_passes(self) -> int:
        if self.hysteresis_policy in {
            "LEGACY_TWO_CONFIRM_ONE_RELEASE",
            "H0_ONE_PASS_DIAGNOSTIC",
        }:
            return 1
        return self.consecutive_failures_to_release


FROZEN_IDENTITY_POLICIES: dict[str, IdentityPolicy] = {
    "H2": IdentityPolicy(
        hybrid_label="H2",
        policy_id="full_pipeline_open_set_decision.v1:H2",
        score_threshold=0.5265351286789879,
        margin_threshold=0.03,
        calibration_identity="frozen_hybrid_product_v2_selection:H2",
        decision_policy_sha256="2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a",
        calibration_protocol_id="hybrid_speaker_attribution_product_v2_a68cc1ac26aa",
        calibration_result_sha256="2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a",
        target_fpir=0.01,
        frozen_anchor=True,
    ),
    "H4": IdentityPolicy(
        hybrid_label="H4",
        policy_id="full_pipeline_open_set_decision.v1:H4",
        score_threshold=0.5331755752703802,
        margin_threshold=0.03,
        calibration_identity="frozen_hybrid_product_v2_selection:H4",
        decision_policy_sha256="2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a",
        calibration_protocol_id="hybrid_speaker_attribution_product_v2_a68cc1ac26aa",
        calibration_result_sha256="2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a",
        target_fpir=0.01,
        frozen_anchor=True,
    ),
    "H5": IdentityPolicy(
        hybrid_label="H5",
        policy_id="full_pipeline_open_set_decision.v1:H5",
        score_threshold=0.4572960706169966,
        margin_threshold=0.03,
        calibration_identity="frozen_hybrid_product_v2_selection:H5",
        decision_policy_sha256="2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a",
        calibration_protocol_id="hybrid_speaker_attribution_product_v2_a68cc1ac26aa",
        calibration_result_sha256="2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a",
        target_fpir=0.01,
        frozen_anchor=True,
    ),
}


def challenger_policy(
    hybrid_label: str,
    *,
    score_threshold: float | None = None,
    margin_threshold: float | None = None,
    calibration_identity: str | None = None,
    decision_policy_sha256: str | None = None,
    calibration_protocol_id: str | None = None,
    calibration_result_sha256: str | None = None,
    target_fpir: float | None = None,
) -> IdentityPolicy:
    """Create a challenger hook without inventing a scientific threshold.

    Supplying thresholds requires a named development-calibration artifact.  An
    unresolved challenger remains useful for raw-score/event smokes but refuses
    to emit a known identity.
    """

    if hybrid_label in FROZEN_IDENTITY_POLICIES:
        raise ValueError(f"{hybrid_label} is frozen; use FROZEN_IDENTITY_POLICIES")
    if score_threshold is not None and not (calibration_identity or "").strip():
        raise ValueError("resolved challenger thresholds require calibration_identity")
    return IdentityPolicy(
        hybrid_label=hybrid_label,
        policy_id=f"full_pipeline_open_set_decision.v1:{hybrid_label}",
        score_threshold=score_threshold,
        margin_threshold=margin_threshold,
        calibration_identity=calibration_identity,
        decision_policy_sha256=decision_policy_sha256,
        calibration_protocol_id=calibration_protocol_id,
        calibration_result_sha256=calibration_result_sha256,
        target_fpir=target_fpir,
        frozen_anchor=False,
    )


@dataclass(frozen=True, order=True)
class ClusterCreation:
    """Deterministic creation key for one causal anonymous cluster."""

    start_sample_index: int
    creation_event_sequence: int
    anonymous_speaker_id: str = field(compare=True)

    def __post_init__(self) -> None:
        if self.start_sample_index < 0 or self.creation_event_sequence < 0:
            raise ValueError("cluster creation indices must be >= 0")
        if not self.anonymous_speaker_id.strip():
            raise ValueError("anonymous_speaker_id must be non-empty")


@dataclass(frozen=True)
class UnknownAllocation:
    anonymous_speaker_id: str
    unknown_label: str
    unknown_ordinal: int
    creation: ClusterCreation


@dataclass(frozen=True)
class ClusterSplitResult:
    parent_id: str
    retained_child_id: str
    child_labels: Mapping[str, str]


class UnknownLabelAllocator:
    """Own persistent session-local ``Unknown_N`` allocation.

    Ordinals are monotonic and never reused.  Aliases created by merges and
    splits continue resolving to the surviving label.
    """

    def __init__(self) -> None:
        self._allocations: dict[str, UnknownAllocation] = {}
        self._aliases: dict[str, str] = {}
        self._next_ordinal = 1

    def allocate(self, creation: ClusterCreation) -> UnknownAllocation:
        if self.contains(creation.anonymous_speaker_id):
            return self.allocation_for(creation.anonymous_speaker_id)
        return self._allocate_new(creation)

    def allocate_many(
        self, creations: Iterable[ClusterCreation]
    ) -> tuple[UnknownAllocation, ...]:
        """Allocate a causal batch with deterministic same-time tie-breaking."""

        ordered = sorted(creations)
        ids = [item.anonymous_speaker_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("cluster creation batch contains duplicate IDs")
        return tuple(self.allocate(item) for item in ordered)

    def contains(self, anonymous_speaker_id: str) -> bool:
        return (
            anonymous_speaker_id in self._allocations
            or anonymous_speaker_id in self._aliases
        )

    def canonical_id(self, anonymous_speaker_id: str) -> str:
        if not self.contains(anonymous_speaker_id):
            raise KeyError(f"unknown anonymous speaker: {anonymous_speaker_id}")
        current = anonymous_speaker_id
        visited: set[str] = set()
        while current in self._aliases:
            if current in visited:  # defensive; public operations never create cycles
                raise RuntimeError("anonymous-speaker alias cycle")
            visited.add(current)
            current = self._aliases[current]
        return current

    def allocation_for(self, anonymous_speaker_id: str) -> UnknownAllocation:
        return self._allocations[self.canonical_id(anonymous_speaker_id)]

    def label_for(self, anonymous_speaker_id: str) -> str:
        return self.allocation_for(anonymous_speaker_id).unknown_label

    def merge(self, anonymous_speaker_ids: Sequence[str]) -> UnknownAllocation:
        """Merge clusters, retaining the earliest-created canonical label."""

        if not anonymous_speaker_ids:
            raise ValueError("merge requires at least one anonymous speaker")
        canonical_ids = sorted(
            {self.canonical_id(value) for value in anonymous_speaker_ids}
        )
        survivor = min(
            canonical_ids,
            key=lambda value: self._allocations[value].creation,
        )
        for losing in canonical_ids:
            if losing == survivor:
                continue
            del self._allocations[losing]
            self._aliases[losing] = survivor
        return self._allocations[survivor]

    def split(
        self,
        parent_id: str,
        children: Sequence[ClusterCreation],
    ) -> ClusterSplitResult:
        """Split a cluster; earliest child inherits, others receive fresh labels."""

        if not children:
            raise ValueError("split requires at least one child")
        ordered = sorted(children)
        child_ids = [item.anonymous_speaker_id for item in ordered]
        if len(child_ids) != len(set(child_ids)):
            raise ValueError("split children contain duplicate IDs")
        canonical_parent = self.canonical_id(parent_id)
        parent_allocation = self._allocations[canonical_parent]
        retained = ordered[0]
        if retained.anonymous_speaker_id != canonical_parent:
            if self.contains(retained.anonymous_speaker_id):
                raise ValueError("retained split child already exists")
            del self._allocations[canonical_parent]
            inherited = replace(
                parent_allocation,
                anonymous_speaker_id=retained.anonymous_speaker_id,
            )
            self._allocations[retained.anonymous_speaker_id] = inherited
            self._aliases[canonical_parent] = retained.anonymous_speaker_id
        for child in ordered[1:]:
            if self.contains(child.anonymous_speaker_id):
                raise ValueError(
                    f"split child already exists: {child.anonymous_speaker_id}"
                )
            self._allocate_new(child)
        labels = {
            child.anonymous_speaker_id: self.label_for(child.anonymous_speaker_id)
            for child in ordered
        }
        return ClusterSplitResult(
            parent_id=parent_id,
            retained_child_id=retained.anonymous_speaker_id,
            child_labels=labels,
        )

    def snapshot(self) -> tuple[UnknownAllocation, ...]:
        return tuple(
            sorted(self._allocations.values(), key=lambda value: value.unknown_ordinal)
        )

    def discard(self, anonymous_speaker_id: str) -> None:
        """Forget one allocation without reusing its privacy-local ordinal."""

        canonical = self.canonical_id(anonymous_speaker_id)
        self._allocations.pop(canonical, None)
        self._aliases = {
            alias: target
            for alias, target in self._aliases.items()
            if alias != anonymous_speaker_id and target != canonical
        }

    def reset(self) -> None:
        self._allocations.clear()
        self._aliases.clear()
        self._next_ordinal = 1

    def _allocate_new(self, creation: ClusterCreation) -> UnknownAllocation:
        ordinal = self._next_ordinal
        self._next_ordinal += 1
        allocation = UnknownAllocation(
            anonymous_speaker_id=creation.anonymous_speaker_id,
            unknown_label=f"Unknown_{ordinal}",
            unknown_ordinal=ordinal,
            creation=creation,
        )
        self._allocations[creation.anonymous_speaker_id] = allocation
        return allocation


@dataclass(frozen=True)
class IdentityEvidence:
    """One cumulative, causal open-set score observation for a cluster."""

    anonymous_speaker_id: str
    source_time_sec: float
    evidence_duration_sec: float
    candidate_scores: Mapping[str, float]
    embedding_consistency: float | None
    evidence_event_id: str
    usable: bool = True

    def __post_init__(self) -> None:
        if not self.anonymous_speaker_id.strip() or not self.evidence_event_id.strip():
            raise ValueError(
                "anonymous_speaker_id and evidence_event_id must be non-empty"
            )
        if self.source_time_sec < 0 or self.evidence_duration_sec < 0:
            raise ValueError("source time and evidence duration must be >= 0")
        if not math.isfinite(self.source_time_sec) or not math.isfinite(
            self.evidence_duration_sec
        ):
            raise ValueError("source time and evidence duration must be finite")
        if self.embedding_consistency is not None and not math.isfinite(
            self.embedding_consistency
        ):
            raise ValueError("embedding_consistency must be finite when present")
        scores: dict[str, float] = {}
        for candidate_id, value in self.candidate_scores.items():
            candidate = str(candidate_id).strip()
            score = float(value)
            if not candidate or not math.isfinite(score):
                raise ValueError("candidate IDs must be non-empty and scores finite")
            scores[candidate] = score
        object.__setattr__(self, "candidate_scores", dict(sorted(scores.items())))


@dataclass(frozen=True)
class IdentitySnapshot:
    anonymous_speaker_id: str
    state: IdentityState
    unknown_label: str
    speaker_label: str
    known_speaker_id: str | None
    tentative_candidate_id: str | None
    confirmation_count: int
    release_count: int
    last_usable_source_sec: float | None
    last_verified_source_sec: float | None
    revision_number: int


@dataclass(frozen=True)
class IdentityTransition:
    """Decision result suitable for adaptation to Prompt-0 identity events."""

    anonymous_speaker_id: str
    source_time_sec: float
    prior_state: IdentityState
    state: IdentityState
    prior_speaker_label: str
    speaker_label: str
    unknown_label: str
    known_speaker_id: str | None
    top1_candidate_id: str | None
    top1_score: float | None
    top2_candidate_id: str | None
    top2_score: float | None
    margin: float | None
    confirmation_count: int
    required_confirmation_count: int
    evidence_event_ids: tuple[str, ...]
    decision_reason: str
    hysteresis_applied: bool
    policy_id: str
    calibration_resolved: bool
    revision_number: int
    changed: bool
    release_count: int = 0
    required_release_count: int = 1
    effective_score_threshold: float | None = None
    effective_margin_threshold: float | None = None
    confidence_strength: float | None = None


@dataclass
class _ClusterIdentityRecord:
    anonymous_speaker_id: str
    unknown_label: str
    state: IdentityState = IdentityState.GENERIC
    known_speaker_id: str | None = None
    tentative_candidate_id: str | None = None
    confirmation_count: int = 0
    release_count: int = 0
    last_usable_source_sec: float | None = None
    last_verified_source_sec: float | None = None
    last_source_time_sec: float | None = None
    last_evidence_event_id: str | None = None
    revision_number: int = 0
    evidence_history: list[dict[str, object]] = field(default_factory=list)


class SessionIdentityManager:
    """Causal per-cluster identity policy with session-owned anonymous labels."""

    def __init__(
        self,
        policy: IdentityPolicy,
        *,
        allocator: UnknownLabelAllocator | None = None,
        maximum_clusters: int = 128,
        maximum_evidence_history_per_cluster: int = 64,
    ) -> None:
        if maximum_clusters < 1 or maximum_evidence_history_per_cluster < 1:
            raise ValueError("session identity bounds must be >= 1")
        self.policy = policy
        self.allocator = allocator or UnknownLabelAllocator()
        self.maximum_clusters = int(maximum_clusters)
        self.maximum_evidence_history_per_cluster = int(
            maximum_evidence_history_per_cluster
        )
        self._records: dict[str, _ClusterIdentityRecord] = {}

    def ensure_cluster(self, creation: ClusterCreation) -> IdentitySnapshot:
        if (
            not self.allocator.contains(creation.anonymous_speaker_id)
            and len(self._records) >= self.maximum_clusters
        ):
            self._evict_one_cluster()
        allocation = self.allocator.allocate(creation)
        canonical = self.allocator.canonical_id(creation.anonymous_speaker_id)
        if canonical not in self._records:
            self._records[canonical] = _ClusterIdentityRecord(
                anonymous_speaker_id=canonical,
                unknown_label=allocation.unknown_label,
            )
        return self.snapshot(creation.anonymous_speaker_id)

    def snapshot(self, anonymous_speaker_id: str) -> IdentitySnapshot:
        canonical = self.allocator.canonical_id(anonymous_speaker_id)
        record = self._records[canonical]
        return IdentitySnapshot(
            anonymous_speaker_id=canonical,
            state=record.state,
            unknown_label=record.unknown_label,
            speaker_label=self._speaker_label(record),
            known_speaker_id=record.known_speaker_id,
            tentative_candidate_id=record.tentative_candidate_id,
            confirmation_count=record.confirmation_count,
            release_count=record.release_count,
            last_usable_source_sec=record.last_usable_source_sec,
            last_verified_source_sec=record.last_verified_source_sec,
            revision_number=record.revision_number,
        )

    def observe(self, evidence: IdentityEvidence) -> IdentityTransition:
        canonical = self.allocator.canonical_id(evidence.anonymous_speaker_id)
        record = self._records[canonical]
        self._validate_source_time(record, evidence.source_time_sec)
        record.last_source_time_sec = evidence.source_time_sec
        prior_state = record.state
        prior_label = self._speaker_label(record)
        ranked = sorted(
            evidence.candidate_scores.items(), key=lambda item: (-item[1], item[0])
        )
        top1_id, top1_score = ranked[0] if ranked else (None, None)
        top2_id, top2_score = ranked[1] if len(ranked) > 1 else (None, None)
        margin = (
            top1_score - top2_score
            if top1_score is not None and top2_score is not None
            else None
        )
        quality_passed = (
            evidence.usable
            and evidence.embedding_consistency is not None
            and evidence.embedding_consistency
            >= self.policy.minimum_embedding_consistency
        )
        if quality_passed:
            record.last_usable_source_sec = evidence.source_time_sec

        reason = "insufficient_evidence"
        hysteresis_applied = False
        (
            effective_score_threshold,
            effective_margin_threshold,
            required_confirmation_count,
        ) = self.policy.effective_gate(evidence.evidence_duration_sec)
        enough_evidence = (
            evidence.evidence_duration_sec >= self.policy.minimum_evidence_sec
        )
        if not evidence.usable:
            reason = "unusable_evidence"
        elif not enough_evidence:
            reason = "insufficient_evidence"
        elif not quality_passed:
            reason = "quality_rejected"
            self._reject_or_hold(record)
        elif not self.policy.calibrated:
            reason = "challenger_calibration_unresolved"
            self._set_unknown(record)
        elif top1_id is None or top1_score is None:
            reason = "no_candidate_scores"
            reason = self._release_or_reject(record, reason)
        else:
            assert effective_score_threshold is not None
            assert effective_margin_threshold is not None
            margin_passed = (
                margin is None or margin >= effective_margin_threshold
            )
            base_passed = top1_score >= effective_score_threshold and margin_passed
            if base_passed:
                reason = self._accept_candidate(
                    record,
                    top1_id,
                    required_confirmation_count=required_confirmation_count,
                )
                if (
                    record.state is IdentityState.CONFIRMED_KNOWN
                    and record.known_speaker_id == top1_id
                ):
                    record.last_verified_source_sec = evidence.source_time_sec
            else:
                hysteresis_score = (
                    top1_score
                    if self.policy.hysteresis_score_mode == "frozen_top1"
                    else (
                        evidence.candidate_scores.get(record.known_speaker_id)
                        if record.known_speaker_id is not None
                        else None
                    )
                )
                release_threshold = effective_score_threshold - self.policy.hysteresis
                if (
                    record.state is IdentityState.CONFIRMED_KNOWN
                    and hysteresis_score is not None
                    and release_threshold is not None
                    and hysteresis_score >= release_threshold
                ):
                    record.tentative_candidate_id = None
                    record.confirmation_count = 0
                    record.release_count = 0
                    reason = "current_identity_hysteresis_hold"
                    hysteresis_applied = True
                else:
                    rejection_reason = (
                        "below_score_threshold"
                        if top1_score < effective_score_threshold
                        else "below_margin_threshold"
                    )
                    reason = self._release_or_reject(record, rejection_reason)

        new_label = self._speaker_label(record)
        changed = prior_state is not record.state or prior_label != new_label
        if changed:
            record.revision_number += 1
        transition = IdentityTransition(
            anonymous_speaker_id=canonical,
            source_time_sec=evidence.source_time_sec,
            prior_state=prior_state,
            state=record.state,
            prior_speaker_label=prior_label,
            speaker_label=new_label,
            unknown_label=record.unknown_label,
            known_speaker_id=record.known_speaker_id,
            top1_candidate_id=top1_id,
            top1_score=top1_score,
            top2_candidate_id=top2_id,
            top2_score=top2_score,
            margin=margin,
            confirmation_count=record.confirmation_count,
            required_confirmation_count=required_confirmation_count,
            evidence_event_ids=(evidence.evidence_event_id,),
            decision_reason=reason,
            hysteresis_applied=hysteresis_applied,
            policy_id=self.policy.policy_id,
            calibration_resolved=self.policy.calibrated,
            revision_number=record.revision_number,
            changed=changed,
            release_count=record.release_count,
            required_release_count=self.policy.required_release_passes,
            effective_score_threshold=effective_score_threshold,
            effective_margin_threshold=effective_margin_threshold,
            confidence_strength=(
                1.0
                if record.last_verified_source_sec == evidence.source_time_sec
                and record.state is IdentityState.CONFIRMED_KNOWN
                else None
            ),
        )
        record.last_evidence_event_id = evidence.evidence_event_id
        self._append_history(record, transition)
        return transition

    def bind_latest_evidence_event(
        self, anonymous_speaker_id: str, evidence_event_id: str
    ) -> None:
        """Replace a coordinator reservation ID with its emitted event ID.

        The identity decision is computed before the common event factory owns
        the final deterministic ID.  Binding keeps later inheritance/expiry
        causality attached to a real IdentityEvidenceEvent.
        """

        if not evidence_event_id.strip():
            raise ValueError("evidence_event_id must be non-empty")
        canonical = self.allocator.canonical_id(anonymous_speaker_id)
        record = self._records[canonical]
        record.last_evidence_event_id = evidence_event_id
        if record.evidence_history:
            record.evidence_history[-1]["evidence_event_ids"] = [evidence_event_id]

    def inherit_confirmed_short_turn(
        self,
        anonymous_speaker_id: str,
        *,
        source_time_sec: float,
        maximum_gap_sec: float,
        same_cluster: bool = True,
        predicted_overlap: bool = False,
        strong_contradiction: bool = False,
    ) -> IdentityTransition | None:
        """Provisionally carry a confirmed name without fabricating evidence.

        The method never refreshes ``last_usable_source_sec``.  Repeated short
        turns therefore cannot keep a stale name alive beyond source-clock
        expiry, and the prior real evidence event remains the causal anchor.
        """

        if maximum_gap_sec < 0 or not math.isfinite(maximum_gap_sec):
            raise ValueError("maximum_gap_sec must be finite and >= 0")
        canonical = self.allocator.canonical_id(anonymous_speaker_id)
        record = self._records[canonical]
        self._validate_source_time(record, source_time_sec)
        record.last_source_time_sec = source_time_sec
        if not same_cluster or predicted_overlap or strong_contradiction:
            return None
        if (
            record.state is not IdentityState.CONFIRMED_KNOWN
            or record.known_speaker_id is None
            or record.last_usable_source_sec is None
            or record.last_evidence_event_id is None
        ):
            return None
        age = source_time_sec - record.last_usable_source_sec
        if age > maximum_gap_sec or age >= self.policy.identity_expiry_sec:
            return None
        label = self._speaker_label(record)
        transition = IdentityTransition(
            anonymous_speaker_id=canonical,
            source_time_sec=source_time_sec,
            prior_state=record.state,
            state=record.state,
            prior_speaker_label=label,
            speaker_label=label,
            unknown_label=record.unknown_label,
            known_speaker_id=record.known_speaker_id,
            top1_candidate_id=None,
            top1_score=None,
            top2_candidate_id=None,
            top2_score=None,
            margin=None,
            confirmation_count=record.confirmation_count,
            required_confirmation_count=self.policy.consecutive_passes_to_confirm,
            evidence_event_ids=(record.last_evidence_event_id,),
            decision_reason="confirmed_name_inherited_short_turn",
            hysteresis_applied=True,
            policy_id=self.policy.policy_id,
            calibration_resolved=self.policy.calibrated,
            revision_number=record.revision_number,
            changed=False,
            release_count=record.release_count,
            required_release_count=self.policy.required_release_passes,
        )
        self._append_history(record, transition)
        return transition

    def advance_time(
        self,
        source_time_sec: float,
        *,
        confidence_decay_half_life_sec: float | None = None,
        confidence_decay_release_floor: float = 0.25,
    ) -> tuple[IdentityTransition, ...]:
        """Release stale identity state using source/audio time only.

        Hard expiry remains the fail-safe.  M4/M5 may additionally request an
        exponential confidence decay; it releases a name but never creates or
        strengthens one.
        """

        if source_time_sec < 0 or not math.isfinite(source_time_sec):
            raise ValueError("source_time_sec must be finite and >= 0")
        if confidence_decay_half_life_sec is not None and (
            not math.isfinite(confidence_decay_half_life_sec)
            or confidence_decay_half_life_sec <= 0
        ):
            raise ValueError("confidence decay half-life must be finite and > 0")
        if (
            not math.isfinite(confidence_decay_release_floor)
            or not 0.0 < confidence_decay_release_floor < 1.0
        ):
            raise ValueError("confidence decay release floor must be in (0, 1)")
        if (
            self.policy.identity_expiry_mode == "end_session"
            and confidence_decay_half_life_sec is None
        ):
            for record in self._records.values():
                self._validate_source_time(record, source_time_sec)
                record.last_source_time_sec = source_time_sec
            return ()
        transitions: list[IdentityTransition] = []
        for canonical in sorted(self._records):
            record = self._records[canonical]
            self._validate_source_time(record, source_time_sec)
            record.last_source_time_sec = source_time_sec
            if record.state is IdentityState.RELEASED:
                continue
            decay_strength: float | None = None
            decay_due = False
            if (
                confidence_decay_half_life_sec is not None
                and record.state is IdentityState.CONFIRMED_KNOWN
                and record.last_verified_source_sec is not None
            ):
                decay_age = max(
                    0.0, source_time_sec - record.last_verified_source_sec
                )
                decay_strength = math.pow(
                    0.5, decay_age / confidence_decay_half_life_sec
                )
                decay_due = decay_strength <= confidence_decay_release_floor
            hard_expiry_due = (
                self.policy.identity_expiry_mode != "end_session"
                and record.last_usable_source_sec is not None
                and source_time_sec - record.last_usable_source_sec
                >= self.policy.identity_expiry_sec
            )
            if not decay_due and not hard_expiry_due:
                continue
            prior_state = record.state
            prior_label = self._speaker_label(record)
            record.state = IdentityState.RELEASED
            record.known_speaker_id = None
            record.tentative_candidate_id = None
            record.confirmation_count = 0
            record.release_count = 0
            record.revision_number += 1
            transitions.append(
                IdentityTransition(
                    anonymous_speaker_id=canonical,
                    source_time_sec=source_time_sec,
                    prior_state=prior_state,
                    state=record.state,
                    prior_speaker_label=prior_label,
                    speaker_label=record.unknown_label,
                    unknown_label=record.unknown_label,
                    known_speaker_id=None,
                    top1_candidate_id=None,
                    top1_score=None,
                    top2_candidate_id=None,
                    top2_score=None,
                    margin=None,
                    confirmation_count=0,
                    required_confirmation_count=self.policy.consecutive_passes_to_confirm,
                    evidence_event_ids=(),
                    decision_reason=(
                        "identity_confidence_decayed"
                        if decay_due
                        else "identity_evidence_expired"
                    ),
                    hysteresis_applied=False,
                    policy_id=self.policy.policy_id,
                    calibration_resolved=self.policy.calibrated,
                    revision_number=record.revision_number,
                    changed=True,
                    release_count=0,
                    required_release_count=self.policy.required_release_passes,
                    confidence_strength=decay_strength,
                )
            )
            self._append_history(record, transitions[-1])
        return tuple(transitions)

    def end_session(
        self, source_time_sec: float
    ) -> tuple[IdentityTransition, ...]:
        """Release and delete all volatile identity state at session end.

        Permanent enrollment profiles are owned by a separate store and are
        therefore never touched by this method.
        """

        if source_time_sec < 0 or not math.isfinite(source_time_sec):
            raise ValueError("source_time_sec must be finite and >= 0")
        transitions: list[IdentityTransition] = []
        for canonical in sorted(self._records):
            record = self._records[canonical]
            self._validate_source_time(record, source_time_sec)
            prior_state = record.state
            prior_label = self._speaker_label(record)
            if prior_state is IdentityState.RELEASED:
                continue
            record.state = IdentityState.RELEASED
            record.known_speaker_id = None
            record.tentative_candidate_id = None
            record.confirmation_count = 0
            record.release_count = 0
            record.revision_number += 1
            transitions.append(
                IdentityTransition(
                    anonymous_speaker_id=canonical,
                    source_time_sec=source_time_sec,
                    prior_state=prior_state,
                    state=IdentityState.RELEASED,
                    prior_speaker_label=prior_label,
                    speaker_label=record.unknown_label,
                    unknown_label=record.unknown_label,
                    known_speaker_id=None,
                    top1_candidate_id=None,
                    top1_score=None,
                    top2_candidate_id=None,
                    top2_score=None,
                    margin=None,
                    confirmation_count=0,
                    required_confirmation_count=(
                        self.policy.consecutive_passes_to_confirm
                    ),
                    evidence_event_ids=(),
                    decision_reason="session_ended",
                    hysteresis_applied=False,
                    policy_id=self.policy.policy_id,
                    calibration_resolved=self.policy.calibrated,
                    revision_number=record.revision_number,
                    changed=True,
                    release_count=0,
                    required_release_count=self.policy.required_release_passes,
                    confidence_strength=0.0,
                )
            )
        self.reset()
        return tuple(transitions)

    def merge_clusters(self, anonymous_speaker_ids: Sequence[str]) -> IdentitySnapshot:
        canonical_before = [
            self.allocator.canonical_id(value) for value in anonymous_speaker_ids
        ]
        records = [self._records[value] for value in dict.fromkeys(canonical_before)]
        allocation = self.allocator.merge(anonymous_speaker_ids)
        survivor = self.allocator.canonical_id(allocation.anonymous_speaker_id)
        survivor_record = next(
            (value for value in records if value.anonymous_speaker_id == survivor),
            records[0],
        )
        known_ids = {
            value.known_speaker_id for value in records if value.known_speaker_id
        }
        if len(known_ids) > 1:
            survivor_record.state = IdentityState.UNKNOWN_INSTANCE
            survivor_record.known_speaker_id = None
            survivor_record.tentative_candidate_id = None
            survivor_record.confirmation_count = 0
            survivor_record.release_count = 0
            survivor_record.revision_number += 1
        else:
            strongest = max(records, key=lambda value: _state_strength(value.state))
            survivor_record.state = strongest.state
            survivor_record.known_speaker_id = strongest.known_speaker_id
            survivor_record.tentative_candidate_id = strongest.tentative_candidate_id
            survivor_record.confirmation_count = strongest.confirmation_count
            survivor_record.release_count = strongest.release_count
            survivor_record.last_evidence_event_id = strongest.last_evidence_event_id
        survivor_record.anonymous_speaker_id = survivor
        survivor_record.unknown_label = allocation.unknown_label
        usable_times = [
            value.last_usable_source_sec
            for value in records
            if value.last_usable_source_sec is not None
        ]
        survivor_record.last_usable_source_sec = (
            max(usable_times) if usable_times else None
        )
        verified_times = [
            value.last_verified_source_sec
            for value in records
            if value.last_verified_source_sec is not None
        ]
        survivor_record.last_verified_source_sec = (
            max(verified_times) if verified_times else None
        )
        source_times = [
            value.last_source_time_sec
            for value in records
            if value.last_source_time_sec is not None
        ]
        survivor_record.last_source_time_sec = max(source_times) if source_times else None
        combined_history = sorted(
            (
                dict(item)
                for value in records
                for item in value.evidence_history
            ),
            key=lambda item: (
                float(item.get("source_time_sec") or 0.0),
                str(item.get("decision_reason") or ""),
            ),
        )
        survivor_record.evidence_history = combined_history[
            -self.maximum_evidence_history_per_cluster :
        ]
        for canonical in set(canonical_before):
            self._records.pop(canonical, None)
        self._records[survivor] = survivor_record
        return self.snapshot(survivor)

    def split_cluster(
        self,
        parent_id: str,
        children: Sequence[ClusterCreation],
    ) -> ClusterSplitResult:
        canonical_parent = self.allocator.canonical_id(parent_id)
        parent_record = self._records[canonical_parent]
        result = self.allocator.split(parent_id, children)
        retained = self.allocator.canonical_id(result.retained_child_id)
        self._records.pop(canonical_parent, None)
        parent_record.anonymous_speaker_id = retained
        parent_record.unknown_label = self.allocator.label_for(retained)
        self._records[retained] = parent_record
        for child in sorted(children):
            canonical = self.allocator.canonical_id(child.anonymous_speaker_id)
            if canonical not in self._records:
                self._records[canonical] = _ClusterIdentityRecord(
                    anonymous_speaker_id=canonical,
                    unknown_label=self.allocator.label_for(canonical),
                )
        return result

    def reset(self) -> None:
        self.allocator.reset()
        self._records.clear()

    def clear_anonymous_memory(self) -> None:
        """Delete all volatile identity mappings; enrollment lives elsewhere."""

        self.reset()

    def last_evidence_event_id(self, anonymous_speaker_id: str) -> str | None:
        canonical = self.allocator.canonical_id(anonymous_speaker_id)
        return self._records[canonical].last_evidence_event_id

    def session_state(self) -> dict[str, object]:
        """Return bounded, JSON-safe identity state for research/UX inspection."""

        rows = []
        for canonical in sorted(self._records):
            record = self._records[canonical]
            snapshot = self.snapshot(canonical)
            rows.append(
                {
                    "anonymous_speaker_id": canonical,
                    "unknown_label": record.unknown_label,
                    "state": snapshot.state.value,
                    "speaker_label": snapshot.speaker_label,
                    "known_speaker_id": snapshot.known_speaker_id,
                    "last_usable_source_sec": record.last_usable_source_sec,
                    "last_verified_source_sec": record.last_verified_source_sec,
                    "last_source_time_sec": record.last_source_time_sec,
                    "last_evidence_event_id": record.last_evidence_event_id,
                    "release_count": record.release_count,
                    "evidence_history": [dict(value) for value in record.evidence_history],
                }
            )
        return {
            "maximum_clusters": self.maximum_clusters,
            "maximum_evidence_history_per_cluster": (
                self.maximum_evidence_history_per_cluster
            ),
            "cluster_count": len(rows),
            "clusters": rows,
        }

    def _append_history(
        self, record: _ClusterIdentityRecord, transition: IdentityTransition
    ) -> None:
        record.evidence_history.append(
            {
                "source_time_sec": transition.source_time_sec,
                "state": transition.state.value,
                "speaker_label": transition.speaker_label,
                "known_speaker_id": transition.known_speaker_id,
                "top1_candidate_id": transition.top1_candidate_id,
                "top1_score": transition.top1_score,
                "top2_candidate_id": transition.top2_candidate_id,
                "top2_score": transition.top2_score,
                "margin": transition.margin,
                "decision_reason": transition.decision_reason,
                "evidence_event_ids": list(transition.evidence_event_ids),
                "confirmation_count": transition.confirmation_count,
                "required_confirmation_count": transition.required_confirmation_count,
                "release_count": transition.release_count,
                "required_release_count": transition.required_release_count,
                "effective_score_threshold": transition.effective_score_threshold,
                "effective_margin_threshold": transition.effective_margin_threshold,
                "confidence_strength": transition.confidence_strength,
            }
        )
        overflow = (
            len(record.evidence_history)
            - self.maximum_evidence_history_per_cluster
        )
        if overflow > 0:
            del record.evidence_history[:overflow]

    def _evict_one_cluster(self) -> None:
        candidates = sorted(
            self._records.values(),
            key=lambda value: (
                value.state not in {
                    IdentityState.RELEASED,
                    IdentityState.UNKNOWN_INSTANCE,
                    IdentityState.GENERIC,
                },
                value.last_source_time_sec
                if value.last_source_time_sec is not None
                else -1.0,
                value.anonymous_speaker_id,
            ),
        )
        if not candidates or candidates[0].state in {
            IdentityState.TENTATIVE_KNOWN,
            IdentityState.CONFIRMED_KNOWN,
        }:
            raise RuntimeError(
                "maximum_session_speakers reached with no safely evictable cluster"
            )
        evicted = candidates[0].anonymous_speaker_id
        self._records.pop(evicted, None)
        self.allocator.discard(evicted)

    def _accept_candidate(
        self,
        record: _ClusterIdentityRecord,
        candidate_id: str,
        *,
        required_confirmation_count: int,
    ) -> str:
        record.release_count = 0
        if record.state is IdentityState.CONFIRMED_KNOWN:
            if record.known_speaker_id == candidate_id:
                record.tentative_candidate_id = None
                record.confirmation_count = 0
                return "confirmed_identity_pass"
            if record.tentative_candidate_id == candidate_id:
                record.confirmation_count += 1
            else:
                record.tentative_candidate_id = candidate_id
                record.confirmation_count = 1
            if record.confirmation_count < required_confirmation_count:
                return "challenger_confirmation_pending"
            record.known_speaker_id = candidate_id
            record.tentative_candidate_id = None
            record.confirmation_count = required_confirmation_count
            return "challenger_confirmed"

        if record.tentative_candidate_id == candidate_id:
            record.confirmation_count += 1
        else:
            record.tentative_candidate_id = candidate_id
            record.confirmation_count = 1
        if record.confirmation_count >= required_confirmation_count:
            record.state = IdentityState.CONFIRMED_KNOWN
            record.known_speaker_id = candidate_id
            record.tentative_candidate_id = None
            return "known_identity_confirmed"
        record.state = IdentityState.TENTATIVE_KNOWN
        record.known_speaker_id = None
        return "known_identity_tentative"

    def _reject_or_hold(self, record: _ClusterIdentityRecord) -> None:
        if record.state is IdentityState.CONFIRMED_KNOWN:
            record.release_count = 0
        elif record.state is not IdentityState.RELEASED:
            self._set_unknown(record)

    def _release_or_reject(
        self, record: _ClusterIdentityRecord, rejection_reason: str
    ) -> str:
        """Apply consecutive release passes to an already-confirmed name."""

        if record.state is not IdentityState.CONFIRMED_KNOWN:
            self._set_unknown(record)
            return rejection_reason
        record.tentative_candidate_id = None
        record.confirmation_count = 0
        record.release_count += 1
        if record.release_count < self.policy.required_release_passes:
            return "release_confirmation_pending"
        self._set_unknown(record)
        return "known_identity_released_after_failures"

    @staticmethod
    def _set_unknown(record: _ClusterIdentityRecord) -> None:
        record.state = IdentityState.UNKNOWN_INSTANCE
        record.known_speaker_id = None
        record.tentative_candidate_id = None
        record.confirmation_count = 0
        record.release_count = 0

    def _speaker_label(self, record: _ClusterIdentityRecord) -> str:
        if record.state is IdentityState.CONFIRMED_KNOWN and record.known_speaker_id:
            return record.known_speaker_id
        if (
            record.state is IdentityState.TENTATIVE_KNOWN
            and self.policy.tentative_visible
            and record.tentative_candidate_id
        ):
            return record.tentative_candidate_id
        return record.unknown_label

    @staticmethod
    def _validate_source_time(
        record: _ClusterIdentityRecord, source_time_sec: float
    ) -> None:
        if source_time_sec < 0 or not math.isfinite(source_time_sec):
            raise ValueError("source_time_sec must be finite and >= 0")
        if (
            record.last_source_time_sec is not None
            and source_time_sec < record.last_source_time_sec
        ):
            raise ValueError("source time must be monotonic for each anonymous speaker")


def _state_strength(state: IdentityState) -> int:
    return {
        IdentityState.RELEASED: 0,
        IdentityState.GENERIC: 1,
        IdentityState.UNKNOWN_INSTANCE: 2,
        IdentityState.TENTATIVE_KNOWN: 3,
        IdentityState.CONFIRMED_KNOWN: 4,
    }[state]
