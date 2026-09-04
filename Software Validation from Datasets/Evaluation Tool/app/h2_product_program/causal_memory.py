"""Checksum-bound causal H2 session-memory evidence.

This module deliberately does not create counterfactual ``live_projection``
objects.  One evidence cell represents one completed development execution of
the runtime (or of the exact :class:`SessionIdentityManager` primitive) under
one declared policy.  Runtime decisions are recorded before reference fields
are joined for scoring and are bound to the source events, cases, partition,
configuration, implementation, and shared neural-cache identities.

The long-running controller may call :func:`write_exact_runtime_cell` after an
atomic case/cell completes.  The immutable artifact is safe to reuse after a
restart only when every binding and its payload checksum still validate.
Missing cells remain explicit unsupported outcomes; this module never
substitutes another cell or invents a metric.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import gzip
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline.identity import (
    ClusterCreation,
    IdentityEvidence,
    IdentityPolicy,
    IdentityState,
    SessionIdentityManager,
)

from .contracts import H2ProgramError
from .io import canonical_sha256, read_json, write_once_or_verify


CAUSAL_MEMORY_SCHEMA_VERSION = "h2-causal-memory-runtime-evidence.v2"
CAUSAL_MEMORY_BINDING_SCHEMA_VERSION = "h2-causal-memory-source-binding.v2"
CAUSAL_MEMORY_OUTCOME_SCHEMA_VERSION = "h2-causal-memory-runtime-outcome.v2"

MEMORY_LEVELS = (
    "M0_STATELESS",
    "M1_CLUSTER",
    "M2_CONFIRMED_NAME",
    "M3_SHORT_TURN",
    "M4_ACTIVE_ROSTER_DECAY",
    "M5_CLUSTER_RECONCILIATION",
)
EXECUTABLE_MEMORY_LEVELS = MEMORY_LEVELS
EXPIRY_CELLS: tuple[float | str, ...] = (
    15.0,
    30.0,
    60.0,
    120.0,
    "END_SESSION",
)
SHORT_TURN_POLICIES = (
    "A_FRESH_EMBEDDING",
    "B_ANONYMOUS_CLUSTER_INHERITANCE",
    "C_CONFIRMED_NAME_INHERITANCE",
    "D_INHERITANCE_WITH_CONTRADICTION_CHECKS",
    "E_GENERIC_UNTIL_LATER_CORRECTION",
)
SHORT_TURN_BINS = ("LT_0P5", "GE_0P5_LT_1P0", "GE_1P0_LE_2P0")
CAUSAL_EXECUTORS = {
    "PipelineCoordinator",
    "SessionIdentityManager",
}
DEVELOPMENT_ROLES = {"calibration", "selection"}
CONFIDENCE_DECAY_HALF_LIFE_SEC = 30.0
CONFIDENCE_DECAY_RELEASE_FLOOR = 0.25
RECONCILIATION_MAX_GAP_SEC = 120.0
RECONCILIATION_MIN_EMBEDDINGS = 2
RECONCILIATION_TARGET_FALSE_MERGE_RATE = 0.01


def _is_sha256(value: object) -> bool:
    text = str(value or "").casefold()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _require_sha256(value: object, field: str) -> str:
    if not _is_sha256(value):
        raise H2ProgramError(f"{field} must be a SHA-256 digest")
    return str(value).casefold()


def _finite(value: object, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise H2ProgramError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise H2ProgramError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise H2ProgramError(f"{field} is outside its finite range")
    return number


def expiry_identity(value: float | str) -> tuple[float, str, str]:
    """Return executable seconds, expiry mode, and stable public cell label."""

    if isinstance(value, str):
        if value.casefold() not in {"end_session", "end_of_session", "session_end"}:
            raise H2ProgramError(f"unsupported expiry cell: {value}")
        return 120.0, "end_session", "END_SESSION"
    seconds = _finite(value, "identity_expiry_sec", minimum=0.0)
    if seconds <= 0 or seconds not in {15.0, 30.0, 60.0, 120.0}:
        raise H2ProgramError("expiry must be 15, 30, 60, 120, or END_SESSION")
    return seconds, "source_clock", f"{seconds:g}S"


@dataclass(frozen=True)
class CausalCellSpec:
    """One declared causal execution cell."""

    memory_level: str
    expiry: float | str
    short_turn_policy: str | None = None

    def __post_init__(self) -> None:
        if self.memory_level not in MEMORY_LEVELS:
            raise H2ProgramError(f"unsupported memory level: {self.memory_level}")
        expiry_identity(self.expiry)
        if (
            self.short_turn_policy is not None
            and self.short_turn_policy not in SHORT_TURN_POLICIES
        ):
            raise H2ProgramError(
                f"unsupported short-turn policy: {self.short_turn_policy}"
            )

    @property
    def cell_id(self) -> str:
        _seconds, _mode, expiry_label = expiry_identity(self.expiry)
        parts = [self.memory_level, expiry_label]
        if self.short_turn_policy is not None:
            parts.append(self.short_turn_policy)
        return "__".join(parts)

    @property
    def executable(self) -> bool:
        return self.memory_level in EXECUTABLE_MEMORY_LEVELS

    def to_jsonable(self) -> dict[str, object]:
        seconds, mode, label = expiry_identity(self.expiry)
        return {
            "cell_id": self.cell_id,
            "memory_level": self.memory_level,
            "identity_expiry_sec": seconds,
            "identity_expiry_mode": mode,
            "expiry_cell": label,
            "short_turn_policy": self.short_turn_policy,
            "runtime_execution_required": self.executable,
        }


def declared_memory_cells() -> tuple[CausalCellSpec, ...]:
    return tuple(
        CausalCellSpec(level, expiry)
        for level in MEMORY_LEVELS
        for expiry in EXPIRY_CELLS
    )


def declared_short_turn_cells(
    *,
    memory_level: str = "M3_SHORT_TURN",
    expiry: float | str = 60.0,
) -> tuple[CausalCellSpec, ...]:
    return tuple(
        CausalCellSpec(memory_level, expiry, policy)
        for policy in SHORT_TURN_POLICIES
    )


class UnsupportedCausalCapability(H2ProgramError):
    """Raised when an exact source lacks evidence required by one policy."""


def read_ordered_runtime_events(path: Path) -> tuple[dict[str, object], ...]:
    """Read the checksum-bound aggregate runtime JSONL or JSONL.GZ stream."""

    source = Path(path)
    opener = gzip.open if source.suffix.casefold() == ".gz" else source.open
    rows: list[dict[str, object]] = []
    with opener(source, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise H2ProgramError(
                    f"runtime event row {line_number} is not an object"
                )
            rows.append(value)
    if not rows:
        raise H2ProgramError("development runtime event stream is empty")
    return tuple(rows)


def _event_case_id(row: Mapping[str, object]) -> str:
    return str(row.get("evaluation_case_id") or row.get("case_id") or "")


def _event_source_time(row: Mapping[str, object]) -> float:
    capture = row.get("capture_timestamps")
    if isinstance(capture, Mapping):
        for key in ("audio_end_sec", "audio_start_sec"):
            if capture.get(key) is not None:
                return _finite(capture[key], f"capture_timestamps.{key}", minimum=0.0)
    for key in ("source_time_sec", "end_sec", "start_sec"):
        if row.get(key) is not None:
            return _finite(row[key], key, minimum=0.0)
    raise H2ProgramError("causal runtime event lacks source/audio time")


def _turn_key(row: Mapping[str, object]) -> str:
    values = row.get("source_turn_ids")
    source_turn = str(values[0]) if isinstance(values, list) and values else ""
    if not source_turn:
        return str(row.get("event_id") or "turn")
    for marker in ("_window_", "_short"):
        if marker in source_turn:
            return source_turn.split(marker, 1)[0]
    return source_turn


def _speaker_reference_by_cluster(
    observations: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    references: dict[tuple[str, str], dict[str, object]] = {}
    for row in observations:
        if str(row.get("split")) != "development" or bool(
            row.get("evaluation_material_inspected")
        ):
            raise H2ProgramError("causal source observation crossed held-out firewall")
        if str(row.get("status")) != "VALID":
            continue
        case_id = str(row.get("case_id") or "")
        cluster_id = str(row.get("anonymous_speaker_id") or "")
        role = str(
            row.get("effective_calibration_role")
            or row.get("h2_calibration_role")
            or ""
        )
        if not case_id or not cluster_id or role not in DEVELOPMENT_ROLES:
            raise H2ProgramError("causal source observation lacks case/cluster role")
        gallery_ids = tuple(
            sorted(map(str, row.get("gallery_enrolled_ids") or ()))
        )
        scores = row.get("candidate_raw_cosine_scores")
        if not gallery_ids or not isinstance(scores, Mapping) or set(map(str, scores)) != set(
            gallery_ids
        ):
            raise H2ProgramError("causal source observation is not full-gallery")
        reference = {
            "case_id": case_id,
            "anonymous_speaker_id": cluster_id,
            "effective_calibration_role": role,
            "reference_truth_state": str(row.get("truth_state") or ""),
            "reference_enrolled_id": row.get("reference_enrolled_id"),
            "reference_global_speaker_id": str(
                row.get("reference_global_speaker_id") or ""
            ),
            "full_gallery_enrolled_ids": list(gallery_ids),
        }
        key = (case_id, cluster_id)
        previous = references.get(key)
        if previous is not None and previous != reference:
            raise H2ProgramError(
                f"runtime cluster has conflicting joined references: {case_id}/{cluster_id}"
            )
        references[key] = reference
    if not references:
        raise H2ProgramError("causal source has no valid full-gallery references")
    return references


def _score_signature_similarity(
    left: Mapping[str, float], right: Mapping[str, float]
) -> float:
    """Centered cosine over full-gallery score signatures."""

    keys = tuple(sorted(left))
    if len(keys) < 2 or keys != tuple(sorted(right)):
        raise UnsupportedCausalCapability(
            "M5 reconciliation requires matching full-gallery score signatures "
            "with at least two enrolled identities"
        )
    left_mean = sum(float(left[key]) for key in keys) / len(keys)
    right_mean = sum(float(right[key]) for key in keys) / len(keys)
    left_centered = [float(left[key]) - left_mean for key in keys]
    right_centered = [float(right[key]) - right_mean for key in keys]
    left_norm = math.sqrt(sum(value * value for value in left_centered))
    right_norm = math.sqrt(sum(value * value for value in right_centered))
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return -1.0
    return sum(
        a * b for a, b in zip(left_centered, right_centered)
    ) / (left_norm * right_norm)


def calibrate_reconciliation_policy(
    *,
    runtime_events: Sequence[Mapping[str, object]],
    observations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Select the M5 threshold using calibration identities only.

    Candidate signatures are averages of actual full-gallery identity scores.
    Reference truth is used only here, before the selection cohort is executed.
    """

    references = _speaker_reference_by_cluster(observations)
    anonymous_by_event: dict[str, tuple[str, str, float, float]] = {}
    score_rows: dict[tuple[str, str], list[dict[str, float]]] = defaultdict(list)
    bounds: dict[tuple[str, str], tuple[float, float]] = {}
    for raw in runtime_events:
        row = dict(raw)
        case_id = _event_case_id(row)
        if str(row.get("event_type")) == "anonymous_speaker":
            cluster_id = str(row.get("anonymous_speaker_id") or "")
            if (case_id, cluster_id) not in references:
                continue
            start = _finite(row.get("start_sec"), "turn_start_sec", minimum=0.0)
            end = _finite(row.get("end_sec"), "turn_end_sec", minimum=0.0)
            anonymous_by_event[str(row.get("event_id") or "")] = (
                case_id,
                cluster_id,
                start,
                end,
            )
            prior = bounds.get((case_id, cluster_id))
            bounds[(case_id, cluster_id)] = (
                min(start, prior[0]) if prior is not None else start,
                max(end, prior[1]) if prior is not None else end,
            )
        elif str(row.get("event_type")) == "identity_evidence":
            anchor = anonymous_by_event.get(str(row.get("causation_event_id") or ""))
            if anchor is None:
                continue
            candidates = row.get("candidate_scores")
            if not isinstance(candidates, list):
                continue
            signature = {
                str(value["candidate_speaker_id"]): float(value["raw_score"])
                for value in candidates
                if isinstance(value, Mapping)
            }
            expected = set(
                map(str, references[(anchor[0], anchor[1])]["full_gallery_enrolled_ids"])
            )
            if set(signature) != expected:
                raise H2ProgramError(
                    "M5 calibration encountered a narrowed score signature"
                )
            score_rows[(anchor[0], anchor[1])].append(signature)

    signatures: dict[tuple[str, str], dict[str, float]] = {}
    for key, rows in score_rows.items():
        if len(rows) < RECONCILIATION_MIN_EMBEDDINGS:
            continue
        gallery = tuple(sorted(rows[0]))
        signatures[key] = {
            speaker_id: sum(row[speaker_id] for row in rows) / len(rows)
            for speaker_id in gallery
        }
    positives: list[float] = []
    negatives: list[float] = []
    case_ids = sorted({case_id for case_id, _cluster in signatures})
    for case_id in case_ids:
        clusters = sorted(
            cluster_id
            for candidate_case, cluster_id in signatures
            if candidate_case == case_id
            and references[(candidate_case, cluster_id)][
                "effective_calibration_role"
            ]
            == "calibration"
        )
        for index, left_cluster in enumerate(clusters):
            for right_cluster in clusters[index + 1 :]:
                left_bounds = bounds[(case_id, left_cluster)]
                right_bounds = bounds[(case_id, right_cluster)]
                if left_bounds[0] <= right_bounds[0]:
                    gap = right_bounds[0] - left_bounds[1]
                else:
                    gap = left_bounds[0] - right_bounds[1]
                if gap < 0 or gap > RECONCILIATION_MAX_GAP_SEC:
                    continue
                similarity = _score_signature_similarity(
                    signatures[(case_id, left_cluster)],
                    signatures[(case_id, right_cluster)],
                )
                same_speaker = (
                    references[(case_id, left_cluster)][
                        "reference_global_speaker_id"
                    ]
                    == references[(case_id, right_cluster)][
                        "reference_global_speaker_id"
                    ]
                )
                (positives if same_speaker else negatives).append(similarity)
    if not positives:
        raise UnsupportedCausalCapability(
            "M5 calibration cohort contains no causal fragmented-speaker pair"
        )
    candidates = sorted(
        {
            -1.0,
            0.80,
            0.85,
            0.90,
            0.925,
            0.95,
            0.975,
            0.99,
            0.995,
            1.0,
            *positives,
            *negatives,
        }
    )
    eligible: list[tuple[float, float, float]] = []
    for threshold in candidates:
        false_merge_rate = (
            sum(score >= threshold for score in negatives) / len(negatives)
            if negatives
            else 0.0
        )
        recall = sum(score >= threshold for score in positives) / len(positives)
        if false_merge_rate <= RECONCILIATION_TARGET_FALSE_MERGE_RATE:
            eligible.append((recall, threshold, false_merge_rate))
    if not eligible:
        threshold = 1.0
        recall = 0.0
        false_merge_rate = 0.0
    else:
        recall, threshold, false_merge_rate = min(
            eligible, key=lambda row: (-row[0], -row[1], row[2])
        )
    contract = {
        "schema_version": "h2-m5-reconciliation-calibration.v1",
        "calibration_role": "calibration",
        "evaluation_role_used": False,
        "similarity": "centered_cosine_full_gallery_score_signature",
        "threshold": threshold,
        "maximum_gap_sec": RECONCILIATION_MAX_GAP_SEC,
        "minimum_embeddings_per_cluster": RECONCILIATION_MIN_EMBEDDINGS,
        "target_false_merge_rate": RECONCILIATION_TARGET_FALSE_MERGE_RATE,
        "calibration_positive_pair_count": len(positives),
        "calibration_negative_pair_count": len(negatives),
        "calibration_fragment_recall": recall,
        "calibration_false_merge_rate": false_merge_rate,
        "full_gallery_required": True,
        "future_spatial_hook_available": False,
        "future_spatial_hook_result_effect": False,
    }
    return {**contract, "policy_sha256": canonical_sha256(contract)}


def execute_causal_primitive_cell(
    *,
    cell: CausalCellSpec,
    policy: IdentityPolicy,
    runtime_config_sha256: str,
    runtime_events: Sequence[Mapping[str, object]],
    observations: Sequence[Mapping[str, object]],
    case_sha256_by_id: Mapping[str, str],
    reconciliation_policy: Mapping[str, object] | None = None,
) -> tuple[dict[str, object], ...]:
    """Drive the live identity state machine over real causal runtime events.

    Neural outputs, anonymous-cluster assignments, overlap flags, source times,
    and galleries come from the completed development runtime.  Only the
    declared memory/expiry state transition changes between cells.  Therefore
    results are conditional on the observed segmentation/clustering trace and
    do not claim that M0 counterfactually changed neural or clustering output.
    Reference truth is joined in a separate final pass after all decisions.
    """

    if not cell.executable:
        raise UnsupportedCausalCapability(
            f"{cell.memory_level} has no executable causal runtime primitive"
        )
    if cell.memory_level == "M5_CLUSTER_RECONCILIATION":
        if not isinstance(reconciliation_policy, Mapping):
            raise UnsupportedCausalCapability(
                "M5 requires a development-frozen reconciliation policy"
            )
        if reconciliation_policy.get("evaluation_role_used") is not False:
            raise H2ProgramError("M5 reconciliation policy crossed the held-out firewall")
    runtime_config = _require_sha256(runtime_config_sha256, "runtime_config_sha256")
    references = _speaker_reference_by_cluster(observations)
    selected_case_ids = {case_id for case_id, _cluster_id in references}
    events = [
        dict(row)
        for row in runtime_events
        if _event_case_id(row) in selected_case_ids
        and str(row.get("event_type"))
        in {"anonymous_speaker", "identity_evidence", "identity_label"}
    ]
    if not events:
        raise H2ProgramError("actual development runtime has no causal speaker events")
    events.sort(
        key=lambda row: (
            _event_case_id(row),
            int(row.get("event_sequence", -1)),
            str(row.get("event_id") or ""),
        )
    )
    by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in events:
        by_case[_event_case_id(row)].append(row)

    decisions: list[dict[str, object]] = []
    for case_id, case_events in sorted(by_case.items()):
        cell_policy = IdentityPolicy(
            **{
                **policy.__dict__,
                "identity_expiry_sec": expiry_identity(cell.expiry)[0],
                "identity_expiry_mode": expiry_identity(cell.expiry)[1],
                "policy_id": f"h2_causal_runtime_cell.v2:{runtime_config}",
                "decision_policy_sha256": runtime_config,
                "frozen_anchor": False,
            }
        )
        manager = SessionIdentityManager(
            cell_policy,
            maximum_clusters=64,
            maximum_evidence_history_per_cluster=64,
        )
        creation_sequence = 0
        created: set[str] = set()
        anonymous_to_internal: dict[str, str] = {}
        outcome_by_anonymous_event: dict[str, dict[str, object]] = {}
        outcome_internal_id: dict[int, str] = {}
        gallery_by_internal: dict[str, tuple[str, ...]] = {}
        pending_generic_corrections: dict[str, list[dict[str, object]]] = defaultdict(list)
        expired_internal_ids: set[str] = set()
        decayed_internal_ids: set[str] = set()
        score_signatures: dict[str, list[dict[str, float]]] = defaultdict(list)
        cluster_bounds: dict[str, tuple[float, float]] = {}
        reconciliation_aliases: dict[str, str] = {}
        last_time: float | None = None

        for event in case_events:
            event_type = str(event["event_type"])
            now = _event_source_time(event)
            if last_time is not None and now > last_time:
                for transition in manager.advance_time(
                    now,
                    confidence_decay_half_life_sec=(
                        CONFIDENCE_DECAY_HALF_LIFE_SEC
                        if cell.memory_level
                        in {
                            "M4_ACTIVE_ROSTER_DECAY",
                            "M5_CLUSTER_RECONCILIATION",
                        }
                        else None
                    ),
                    confidence_decay_release_floor=CONFIDENCE_DECAY_RELEASE_FLOOR,
                ):
                    expired_internal_ids.add(transition.anonymous_speaker_id)
                    if transition.decision_reason == "identity_confidence_decayed":
                        decayed_internal_ids.add(transition.anonymous_speaker_id)
            last_time = max(last_time or 0.0, now)

            if event_type == "anonymous_speaker":
                external_cluster = str(event.get("anonymous_speaker_id") or "")
                reference = references.get((case_id, external_cluster))
                if reference is None:
                    continue
                turn_key = _turn_key(event)
                internal_cluster = (
                    f"{external_cluster}::stateless::{canonical_sha256(turn_key)[:12]}"
                    if cell.memory_level == "M0_STATELESS"
                    else external_cluster
                )
                anonymous_to_internal[str(event["event_id"])] = internal_cluster
                if internal_cluster not in created:
                    creation_sequence += 1
                    manager.ensure_cluster(
                        ClusterCreation(
                            start_sample_index=int(
                                round(
                                    _finite(
                                        event.get("start_sec", now),
                                        "anonymous.start_sec",
                                        minimum=0.0,
                                    )
                                    * 16000.0
                                )
                            ),
                            creation_event_sequence=creation_sequence,
                            anonymous_speaker_id=internal_cluster,
                        )
                    )
                    created.add(internal_cluster)
                canonical_internal = manager.allocator.canonical_id(internal_cluster)
                prior_bounds = cluster_bounds.get(canonical_internal)
                snapshot = manager.snapshot(internal_cluster)
                start = _finite(event.get("start_sec"), "turn_start_sec", minimum=0.0)
                end = _finite(event.get("end_sec"), "turn_end_sec", minimum=0.0)
                duration = end - start
                if duration <= 0:
                    raise H2ProgramError("anonymous runtime turn has invalid bounds")
                cluster_bounds[canonical_internal] = (
                    min(start, prior_bounds[0]) if prior_bounds is not None else start,
                    max(end, prior_bounds[1]) if prior_bounds is not None else end,
                )
                source_turn_ids = event.get("source_turn_ids")
                source_turn_id = (
                    str(source_turn_ids[0])
                    if isinstance(source_turn_ids, list) and source_turn_ids
                    else str(event["event_id"])
                )
                is_short = source_turn_id.startswith("short:") or "_short" in source_turn_id
                short_policy = cell.short_turn_policy
                if is_short and short_policy is None:
                    short_policy = (
                        "C_CONFIRMED_NAME_INHERITANCE"
                        if cell.memory_level
                        in {
                            "M3_SHORT_TURN",
                            "M4_ACTIVE_ROSTER_DECAY",
                            "M5_CLUSTER_RECONCILIATION",
                        }
                        else "B_ANONYMOUS_CLUSTER_INHERITANCE"
                    )
                transition = None
                contradiction = "NONE"
                predicted_overlap = bool(event.get("overlap", False))
                if is_short and short_policy in {
                    "C_CONFIRMED_NAME_INHERITANCE",
                    "D_INHERITANCE_WITH_CONTRADICTION_CHECKS",
                }:
                    checked = short_policy == "D_INHERITANCE_WITH_CONTRADICTION_CHECKS"
                    strong_mismatch_available = "strong_redim_mismatch" in event
                    strong_mismatch = bool(event.get("strong_redim_mismatch", False))
                    transition = manager.inherit_confirmed_short_turn(
                        internal_cluster,
                        source_time_sec=end,
                        maximum_gap_sec=min(
                            cell_policy.identity_expiry_sec,
                            max(2.0, duration),
                        ),
                        same_cluster=True,
                        predicted_overlap=predicted_overlap if checked else False,
                        strong_contradiction=strong_mismatch if checked else False,
                    )
                    if checked and predicted_overlap:
                        contradiction = "BLOCKED_PREDICTED_OVERLAP"
                    elif checked and strong_mismatch_available and strong_mismatch:
                        contradiction = "BLOCKED_STRONG_REDIM_MISMATCH"
                    elif checked and transition is None:
                        contradiction = "BLOCKED_UNCONFIRMED_OR_EXPIRED_CLUSTER"
                    elif checked:
                        contradiction = "CHECKS_PASSED"
                inherited_id = transition.known_speaker_id if transition is not None else None
                if not is_short and cell.memory_level in {
                    "M2_CONFIRMED_NAME",
                    "M3_SHORT_TURN",
                    "M4_ACTIVE_ROSTER_DECAY",
                    "M5_CLUSTER_RECONCILIATION",
                } and snapshot.state is IdentityState.CONFIRMED_KNOWN:
                    inherited_id = snapshot.known_speaker_id
                inherited_evidence_ids = (
                    list(transition.evidence_event_ids)
                    if transition is not None
                    else (
                        [manager.last_evidence_event_id(internal_cluster)]
                        if inherited_id is not None
                        and manager.last_evidence_event_id(internal_cluster) is not None
                        else []
                    )
                )
                outcome: dict[str, object] = {
                    "schema_version": CAUSAL_MEMORY_OUTCOME_SCHEMA_VERSION,
                    "cell_id": cell.cell_id,
                    "causal_executor": "SessionIdentityManager",
                    "decision_used_reference": False,
                    "runtime_config_sha256": runtime_config,
                    "case_id": case_id,
                    "source_event_ids": [
                        str(event["event_id"]),
                        *map(str, inherited_evidence_ids),
                    ],
                    "identity_decision_attempted": False,
                    "full_gallery_enrolled_ids": list(reference["full_gallery_enrolled_ids"]),
                    "scored_gallery_enrolled_ids": [],
                    "active_roster_narrowed_gallery": False,
                    "active_roster_prior_applied": False,
                    "active_roster_speaker_ids": [],
                    "full_gallery_completed_before_decision": False,
                    "turn_id": source_turn_id,
                    "turn_start_sec": start,
                    "turn_end_sec": end,
                    "turn_duration_sec": duration,
                    "first_name_latency_sec": 0.0 if inherited_id is not None else None,
                    "confirmed_name_latency_sec": 0.0 if inherited_id is not None else None,
                    "last_verified_age_sec": (
                        end - snapshot.last_verified_source_sec
                        if snapshot.last_verified_source_sec is not None
                        else None
                    ),
                    "embedding_compute_sec": 0.0,
                    "compute_saved_sec": None,
                    "embedding_calls": 0,
                    "embedding_calls_avoided": 1 if is_short and short_policy != "A_FRESH_EMBEDDING" else 0,
                    "word_count": int(event.get("word_count") or 0),
                    "bounded_cluster_count": 0,
                    "bounded_identity_history_count": 0,
                    "bounded_roster_count": 0,
                    "returning_turn": False,
                    "short_turn": is_short,
                    "inherited_name": inherited_id is not None,
                    "inherited_from_full_gallery_evidence": inherited_id is not None,
                    "fresh_identity_evidence_used": False,
                    "stale_inheritance": False,
                    "false_inheritance": False,
                    "new_speaker_lockout": False,
                    "fragmented_reference_speaker": False,
                    "reentry_consistent": False,
                    "correction_observed": False,
                    "retraction_observed": False,
                    "expiry_observed": canonical_internal in expired_internal_ids,
                    "confidence_decay_applied": canonical_internal
                    in decayed_internal_ids,
                    "confidence_decay_policy_enabled": cell.memory_level
                    in {
                        "M4_ACTIVE_ROSTER_DECAY",
                        "M5_CLUSTER_RECONCILIATION",
                    },
                    "cluster_reconciliation_applied": False,
                    "cluster_reconciliation_similarity": None,
                    "cluster_reconciliation_survivor": None,
                    "cluster_reconciliation_contaminated": False,
                    "short_turn_policy": short_policy if is_short else None,
                    "duration_bin": short_turn_duration_bin(duration) if is_short else None,
                    "contradiction_outcome": contradiction,
                    "contradiction_signals_available": {
                        "predicted_overlap": True,
                        "anonymous_cluster_identity": True,
                        "strong_redim_mismatch": "strong_redim_mismatch" in event,
                        "xvf_direction_conflict": False,
                    },
                    "display_enrolled_id": inherited_id,
                    "display_label": inherited_id or str(event.get("unknown_label") or "Unknown"),
                    "decision_reason": (
                        transition.decision_reason
                        if transition is not None
                        else "generic_until_fresh_evidence"
                    ),
                }
                outcome_by_anonymous_event[str(event["event_id"])] = outcome
                outcome_internal_id[id(outcome)] = internal_cluster
                decisions.append(outcome)
                if is_short and short_policy == "E_GENERIC_UNTIL_LATER_CORRECTION":
                    pending_generic_corrections[internal_cluster].append(outcome)
                continue

            if event_type != "identity_evidence":
                continue
            anonymous_event_id = str(event.get("causation_event_id") or "")
            outcome = outcome_by_anonymous_event.get(anonymous_event_id)
            if outcome is None:
                continue
            internal_cluster = anonymous_to_internal[anonymous_event_id]
            raw_candidates = event.get("candidate_scores")
            if not isinstance(raw_candidates, list):
                raise H2ProgramError("identity evidence lacks full candidate rows")
            scores = {
                str(row["candidate_speaker_id"]): float(row["raw_score"])
                for row in raw_candidates
                if isinstance(row, Mapping)
            }
            expected_gallery = tuple(sorted(map(str, outcome["full_gallery_enrolled_ids"])))
            if tuple(sorted(scores)) != expected_gallery:
                raise H2ProgramError("identity runtime event narrowed the enrolled gallery")
            active_roster_ids = tuple(
                dict.fromkeys(
                    str(row["known_speaker_id"])
                    for row in sorted(
                        (
                            value
                            for value in manager.session_state()["clusters"]
                            if isinstance(value, Mapping)
                            and value.get("state") == "CONFIRMED_KNOWN"
                            and value.get("known_speaker_id") is not None
                        ),
                        key=lambda value: (
                            -float(value.get("last_verified_source_sec") or 0.0),
                            str(value.get("known_speaker_id") or ""),
                        ),
                    )
                )
            )
            ordered_gallery = tuple(
                speaker_id
                for speaker_id in active_roster_ids
                if speaker_id in expected_gallery
            ) + tuple(
                speaker_id
                for speaker_id in expected_gallery
                if speaker_id not in active_roster_ids
            )
            if set(ordered_gallery) != set(expected_gallery) or len(
                ordered_gallery
            ) != len(expected_gallery):
                raise H2ProgramError("active roster changed full-gallery membership")
            outcome["active_roster_prior_applied"] = bool(
                active_roster_ids
                and cell.memory_level
                in {
                    "M4_ACTIVE_ROSTER_DECAY",
                    "M5_CLUSTER_RECONCILIATION",
                }
            )
            outcome["active_roster_speaker_ids"] = list(active_roster_ids)
            outcome["full_gallery_completed_before_decision"] = True
            gallery_by_internal[internal_cluster] = expected_gallery
            quality = event.get("quality_gate")
            quality_mapping = quality if isinstance(quality, Mapping) else {}
            metrics = quality_mapping.get("metrics")
            metric_mapping = metrics if isinstance(metrics, Mapping) else {}
            transition = manager.observe(
                IdentityEvidence(
                    anonymous_speaker_id=internal_cluster,
                    source_time_sec=now,
                    evidence_duration_sec=_finite(
                        event.get("evidence_duration_sec"),
                        "evidence_duration_sec",
                        minimum=0.0,
                    ),
                    candidate_scores=scores,
                    embedding_consistency=(
                        float(metric_mapping["embedding_consistency"])
                        if metric_mapping.get("embedding_consistency") is not None
                        else None
                    ),
                    evidence_event_id=str(event["event_id"]),
                    usable=str(quality_mapping.get("status") or "accepted") == "accepted",
                )
            )
            manager.bind_latest_evidence_event(internal_cluster, str(event["event_id"]))
            outcome["source_event_ids"] = [
                *list(outcome["source_event_ids"]),
                str(event["event_id"]),
            ]
            outcome["identity_decision_attempted"] = True
            outcome["scored_gallery_enrolled_ids"] = list(expected_gallery)
            outcome["fresh_identity_evidence_used"] = True
            outcome["embedding_calls"] = 1
            processing = event.get("processing_timestamps")
            process_mapping = processing if isinstance(processing, Mapping) else {}
            compute_sec = float(process_mapping.get("backend_latency_ms") or 0.0) / 1000.0
            outcome["embedding_compute_sec"] = compute_sec
            visible_id = (
                transition.speaker_label
                if transition.state in {
                    IdentityState.TENTATIVE_KNOWN,
                    IdentityState.CONFIRMED_KNOWN,
                }
                else None
            )
            if visible_id is not None:
                outcome["display_enrolled_id"] = visible_id
                outcome["display_label"] = visible_id
                outcome["first_name_latency_sec"] = max(
                    0.0, now - float(outcome["turn_start_sec"])
                )
            if transition.state is IdentityState.CONFIRMED_KNOWN:
                outcome["confirmed_name_latency_sec"] = max(
                    0.0, now - float(outcome["turn_start_sec"])
                )
            outcome["decision_reason"] = transition.decision_reason
            canonical_cluster = manager.allocator.canonical_id(internal_cluster)
            score_signatures[canonical_cluster].append(scores)
            if (
                cell.memory_level == "M5_CLUSTER_RECONCILIATION"
                and len(score_signatures[canonical_cluster])
                >= int(reconciliation_policy["minimum_embeddings_per_cluster"])
            ):
                source_rows = score_signatures[canonical_cluster]
                source_signature = {
                    speaker_id: sum(row[speaker_id] for row in source_rows)
                    / len(source_rows)
                    for speaker_id in expected_gallery
                }
                source_bounds = cluster_bounds.get(canonical_cluster)
                candidates_for_merge: list[tuple[float, float, str]] = []
                if source_bounds is not None:
                    for target_cluster, target_rows in score_signatures.items():
                        if target_cluster == canonical_cluster or len(target_rows) < int(
                            reconciliation_policy["minimum_embeddings_per_cluster"]
                        ):
                            continue
                        target_bounds = cluster_bounds.get(target_cluster)
                        if target_bounds is None:
                            continue
                        gap = source_bounds[0] - target_bounds[1]
                        if gap < 0 or gap > float(
                            reconciliation_policy["maximum_gap_sec"]
                        ):
                            continue
                        target_signature = {
                            speaker_id: sum(row[speaker_id] for row in target_rows)
                            / len(target_rows)
                            for speaker_id in expected_gallery
                        }
                        similarity = _score_signature_similarity(
                            source_signature, target_signature
                        )
                        if similarity >= float(reconciliation_policy["threshold"]):
                            candidates_for_merge.append(
                                (similarity, gap, target_cluster)
                            )
                if candidates_for_merge:
                    similarity, _gap, target_cluster = min(
                        candidates_for_merge,
                        key=lambda row: (-row[0], row[1], row[2]),
                    )
                    source_outcomes = [
                        prior
                        for prior in decisions
                        if prior.get("case_id") == case_id
                        and manager.allocator.canonical_id(
                            outcome_internal_id[id(prior)]
                        )
                        == canonical_cluster
                    ]
                    merged = manager.merge_clusters(
                        [target_cluster, canonical_cluster]
                    )
                    survivor = merged.anonymous_speaker_id
                    if survivor != target_cluster:
                        raise H2ProgramError(
                            "M5 reconciliation did not retain the earlier cluster"
                        )
                    score_signatures[target_cluster] = [
                        *score_signatures[target_cluster],
                        *score_signatures.pop(canonical_cluster),
                    ]
                    source_bounds = cluster_bounds.pop(canonical_cluster)
                    target_bounds = cluster_bounds[target_cluster]
                    cluster_bounds[target_cluster] = (
                        min(source_bounds[0], target_bounds[0]),
                        max(source_bounds[1], target_bounds[1]),
                    )
                    anchor_event_id = manager.last_evidence_event_id(target_cluster)
                    for prior in source_outcomes:
                        prior["cluster_reconciliation_applied"] = True
                        prior["cluster_reconciliation_similarity"] = similarity
                        prior["cluster_reconciliation_survivor"] = target_cluster
                        if (
                            merged.state is IdentityState.CONFIRMED_KNOWN
                            and merged.known_speaker_id is not None
                            and float(prior["turn_end_sec"]) >= now - 30.0
                        ):
                            changed_by_merge = (
                                prior.get("display_enrolled_id")
                                != merged.known_speaker_id
                            )
                            if changed_by_merge:
                                prior["correction_observed"] = True
                            prior["display_enrolled_id"] = merged.known_speaker_id
                            prior["display_label"] = merged.known_speaker_id
                            if changed_by_merge:
                                prior["inherited_name"] = True
                                prior["inherited_from_full_gallery_evidence"] = True
                            prior["scored_gallery_enrolled_ids"] = list(
                                expected_gallery
                            )
                            if (
                                anchor_event_id is not None
                                and anchor_event_id not in prior["source_event_ids"]
                            ):
                                prior["source_event_ids"] = [
                                    *list(prior["source_event_ids"]),
                                    anchor_event_id,
                                ]
                    reconciliation_aliases[canonical_cluster] = target_cluster
            for pending in pending_generic_corrections[internal_cluster]:
                if visible_id is None or pending.get("later_correction_enrolled_id") is not None:
                    continue
                pending["later_correction_enrolled_id"] = visible_id
                pending["later_correction_source_sec"] = now
                pending["correction_observed"] = True
                pending["source_event_ids"] = [
                    *list(pending["source_event_ids"]),
                    str(event["event_id"]),
                ]

            state = manager.session_state()
            history_count = sum(
                len(row.get("evidence_history") or ())
                for row in state.get("clusters", ())
                if isinstance(row, Mapping)
            )
            outcome["bounded_cluster_count"] = int(state["cluster_count"])
            outcome["bounded_identity_history_count"] = history_count
            outcome["bounded_roster_count"] = sum(
                isinstance(row, Mapping)
                and row.get("state") == "CONFIRMED_KNOWN"
                for row in state.get("clusters", ())
            )

        # Join truth only after all state-machine decisions are complete.
        case_outcomes = [
            row for row in decisions if row["case_id"] == case_id
        ]
        seen_turns_by_speaker: Counter[str] = Counter()
        prior_clusters_by_speaker: dict[str, set[str]] = defaultdict(set)
        clusters_by_speaker: dict[str, set[str]] = defaultdict(set)
        for outcome in case_outcomes:
            internal_cluster = outcome_internal_id[id(outcome)]
            external_cluster = internal_cluster.split("::stateless::", 1)[0]
            reference = references[(case_id, external_cluster)]
            outcome.update(reference)
            effective_cluster = manager.allocator.canonical_id(internal_cluster)
            outcome["effective_anonymous_speaker_id"] = effective_cluster
            outcome["confidence_decay_applied"] = bool(
                outcome["confidence_decay_applied"]
                or effective_cluster in decayed_internal_ids
            )
            outcome["source_case_sha256"] = _require_sha256(
                case_sha256_by_id[case_id], f"case_sha256_by_id[{case_id}]"
            )
            speaker = str(reference["reference_global_speaker_id"])
            outcome["returning_turn"] = seen_turns_by_speaker[speaker] > 0
            outcome["reentry_consistent"] = (
                not outcome["returning_turn"]
                or effective_cluster in prior_clusters_by_speaker[speaker]
            )
            seen_turns_by_speaker[speaker] += 1
            prior_clusters_by_speaker[speaker].add(effective_cluster)
            clusters_by_speaker[speaker].add(effective_cluster)
            display_id = outcome.get("display_enrolled_id")
            reference_id = reference.get("reference_enrolled_id")
            inherited = bool(outcome["inherited_name"])
            false_inheritance = inherited and (
                reference["reference_truth_state"] == "UNKNOWN"
                or str(display_id) != str(reference_id)
            )
            outcome["false_inheritance"] = false_inheritance
            outcome["new_speaker_lockout"] = false_inheritance
            survivor = outcome.get("cluster_reconciliation_survivor")
            if survivor is not None:
                survivor_external = str(survivor).split("::stateless::", 1)[0]
                survivor_reference = references.get((case_id, survivor_external))
                contaminated = bool(
                    survivor_reference is None
                    or survivor_reference["reference_global_speaker_id"]
                    != reference["reference_global_speaker_id"]
                )
                outcome["cluster_reconciliation_contaminated"] = contaminated
                outcome["new_speaker_lockout"] = bool(
                    outcome["new_speaker_lockout"] or contaminated
                )
            age = outcome.get("last_verified_age_sec")
            outcome["stale_inheritance"] = bool(
                inherited
                and age is not None
                and float(age) >= cell_policy.identity_expiry_sec
            )
            if not outcome["identity_decision_attempted"]:
                # No new match was attempted, but prior inherited evidence was
                # itself full-gallery checked. Generic policies score no gallery.
                if inherited:
                    anchor_gallery = gallery_by_internal.get(internal_cluster)
                    if anchor_gallery is None:
                        raise H2ProgramError(
                            "inherited runtime name lacks prior scored-gallery evidence"
                        )
                    outcome["scored_gallery_enrolled_ids"] = list(anchor_gallery)
                else:
                    outcome["scored_gallery_enrolled_ids"] = []
        for outcome in case_outcomes:
            speaker = str(outcome["reference_global_speaker_id"])
            outcome["fragmented_reference_speaker"] = (
                len(clusters_by_speaker[speaker]) > 1
            )
            if int(outcome["bounded_cluster_count"]) == 0:
                state = manager.session_state()
                outcome["bounded_cluster_count"] = int(state["cluster_count"])
                outcome["bounded_identity_history_count"] = sum(
                    len(row.get("evidence_history") or ())
                    for row in state.get("clusters", ())
                    if isinstance(row, Mapping)
                )

        short_outcomes = [row for row in case_outcomes if row["short_turn"]]
        if cell.short_turn_policy == "A_FRESH_EMBEDDING" and any(
            not row["fresh_identity_evidence_used"] for row in short_outcomes
        ):
            raise UnsupportedCausalCapability(
                "A fresh-embedding policy is unsupported because the live runtime "
                "did not emit a full-gallery identity embedding for every short turn"
            )
    if not decisions:
        raise H2ProgramError("causal primitive execution produced no outcomes")
    return tuple(decisions)


def validate_source_binding(binding: Mapping[str, object]) -> dict[str, object]:
    """Validate development-only, speaker-disjoint causal source provenance."""

    value = dict(binding)
    if value.get("schema_version") != CAUSAL_MEMORY_BINDING_SCHEMA_VERSION:
        raise H2ProgramError("unexpected causal-memory source-binding schema")
    if value.get("split") != "development" or bool(
        value.get("evaluation_material_inspected")
    ):
        raise H2ProgramError("causal-memory evidence crossed the held-out firewall")
    for field in (
        "assignment_sha256",
        "source_result_sha256",
        "runtime_config_sha256",
        "runtime_implementation_sha256",
        "runtime_event_log_sha256",
        "neural_cache_manifest_sha256",
        "reference_manifest_sha256",
    ):
        value[field] = _require_sha256(value.get(field), field)
    case_hashes = value.get("case_sha256_by_id")
    if not isinstance(case_hashes, Mapping) or not case_hashes:
        raise H2ProgramError("causal-memory binding has no case identities")
    value["case_sha256_by_id"] = {
        str(case_id): _require_sha256(digest, f"case_sha256_by_id[{case_id}]")
        for case_id, digest in sorted(case_hashes.items())
    }
    roles = value.get("case_role_by_id")
    if not isinstance(roles, Mapping) or set(map(str, roles)) != set(
        value["case_sha256_by_id"]
    ):
        raise H2ProgramError("case roles do not exactly cover bound cases")
    normalised_roles = {str(key): str(role) for key, role in roles.items()}
    if set(normalised_roles.values()) - DEVELOPMENT_ROLES:
        raise H2ProgramError("causal-memory case has a non-development role")
    value["case_role_by_id"] = dict(sorted(normalised_roles.items()))
    speaker_roles = value.get("speaker_ids_by_role")
    if not isinstance(speaker_roles, Mapping):
        raise H2ProgramError("speaker-disjoint partition metadata is missing")
    calibration = tuple(sorted(map(str, speaker_roles.get("calibration") or ())))
    selection = tuple(sorted(map(str, speaker_roles.get("selection") or ())))
    if not calibration or not selection or set(calibration) & set(selection):
        raise H2ProgramError("development speaker roles are empty or overlap")
    value["speaker_ids_by_role"] = {
        "calibration": list(calibration),
        "selection": list(selection),
    }
    if bool(value.get("active_roster_narrowed_gallery")):
        raise H2ProgramError("active roster narrowed the open-set gallery")
    if value.get("full_gallery_safety_enforced") is not True:
        raise H2ProgramError("full-gallery open-set safety was not enforced")
    if value.get("shared_neural_cache_reuse") is not True:
        raise H2ProgramError("causal cells are not bound to the shared neural cache")
    unsigned = dict(value)
    supplied = unsigned.pop("binding_sha256", None)
    expected = canonical_sha256(unsigned)
    if supplied is not None and str(supplied).casefold() != expected:
        raise H2ProgramError("causal-memory source binding checksum differs")
    return {**value, "binding_sha256": expected}


def validate_runtime_outcome(
    row: Mapping[str, object],
    *,
    cell: CausalCellSpec,
    binding: Mapping[str, object],
    source_event_ids: set[str],
) -> dict[str, object]:
    """Validate one decision produced by an exact live runtime primitive."""

    value = dict(row)
    if value.get("schema_version") != CAUSAL_MEMORY_OUTCOME_SCHEMA_VERSION:
        raise H2ProgramError("unexpected causal-memory outcome schema")
    if "live_projection" in value:
        raise H2ProgramError("fabricated live_projection is forbidden")
    if value.get("cell_id") != cell.cell_id:
        raise H2ProgramError("outcome cell identity differs")
    executor = str(value.get("causal_executor") or "")
    if executor not in CAUSAL_EXECUTORS:
        raise H2ProgramError("outcome was not emitted by a live runtime primitive")
    if value.get("decision_used_reference") is not False:
        raise H2ProgramError("runtime decision may not use reference truth")
    if str(value.get("runtime_config_sha256") or "").casefold() != str(
        binding["runtime_config_sha256"]
    ):
        raise H2ProgramError("outcome runtime configuration differs")
    case_id = str(value.get("case_id") or "")
    if case_id not in dict(binding["case_sha256_by_id"]):
        raise H2ProgramError("outcome case is absent from the source binding")
    if str(value.get("effective_calibration_role") or "") != dict(
        binding["case_role_by_id"]
    )[case_id]:
        raise H2ProgramError("outcome development role differs from frozen partition")
    linked = tuple(map(str, value.get("source_event_ids") or ()))
    if not linked or not set(linked) <= source_event_ids:
        raise H2ProgramError("outcome is not fully linked to actual runtime events")
    if str(value.get("source_case_sha256") or "").casefold() != dict(
        binding["case_sha256_by_id"]
    )[case_id]:
        raise H2ProgramError("outcome source-case checksum differs")
    gallery = tuple(sorted(map(str, value.get("full_gallery_enrolled_ids") or ())))
    scored = tuple(sorted(map(str, value.get("scored_gallery_enrolled_ids") or ())))
    if not isinstance(value.get("identity_decision_attempted"), bool):
        raise H2ProgramError("outcome lacks identity-decision execution status")
    if value["identity_decision_attempted"] and gallery != scored:
        raise H2ProgramError("outcome did not score the complete enrolled gallery")
    if not value["identity_decision_attempted"] and scored and gallery != scored:
        raise H2ProgramError("inherited decision anchor did not use the full gallery")
    inherited = value.get("inherited_name") is True
    if inherited:
        if value.get("inherited_from_full_gallery_evidence") is not True:
            raise H2ProgramError("inherited name lacks a prior full-gallery anchor")
        if gallery != scored or value.get("display_enrolled_id") is None or len(linked) < 2:
            raise H2ProgramError("inherited name lacks full-gallery causal provenance")
    elif not value["identity_decision_attempted"]:
        if scored or value.get("display_enrolled_id") is not None:
            raise H2ProgramError("generic no-decision turn claims an enrolled match")
    if value.get("active_roster_narrowed_gallery") is not False:
        raise H2ProgramError("outcome used active roster to narrow the gallery")

    start = _finite(value.get("turn_start_sec"), "turn_start_sec", minimum=0.0)
    end = _finite(value.get("turn_end_sec"), "turn_end_sec", minimum=0.0)
    if end <= start:
        raise H2ProgramError("outcome turn bounds are not increasing")
    duration = _finite(value.get("turn_duration_sec"), "turn_duration_sec", minimum=0.0)
    if abs(duration - (end - start)) > 1e-6:
        raise H2ProgramError("turn duration differs from exact turn bounds")
    for field in (
        "first_name_latency_sec",
        "confirmed_name_latency_sec",
        "last_verified_age_sec",
        "embedding_compute_sec",
        "compute_saved_sec",
    ):
        if value.get(field) is not None:
            value[field] = _finite(value[field], field, minimum=0.0)
    for field in (
        "embedding_calls",
        "embedding_calls_avoided",
        "word_count",
        "bounded_cluster_count",
        "bounded_identity_history_count",
        "bounded_roster_count",
    ):
        number = value.get(field)
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise H2ProgramError(f"{field} must be an integer >= 0")
    required_booleans = (
        "returning_turn",
        "short_turn",
        "inherited_name",
        "inherited_from_full_gallery_evidence",
        "fresh_identity_evidence_used",
        "stale_inheritance",
        "false_inheritance",
        "new_speaker_lockout",
        "fragmented_reference_speaker",
        "reentry_consistent",
        "correction_observed",
        "retraction_observed",
        "expiry_observed",
        "confidence_decay_applied",
        "confidence_decay_policy_enabled",
        "active_roster_prior_applied",
        "full_gallery_completed_before_decision",
        "cluster_reconciliation_applied",
        "cluster_reconciliation_contaminated",
    )
    if any(not isinstance(value.get(field), bool) for field in required_booleans):
        raise H2ProgramError("outcome lacks exact boolean causal measurements")
    if value["short_turn"]:
        declared_policy = str(value.get("short_turn_policy") or "")
        if declared_policy not in SHORT_TURN_POLICIES:
            raise H2ProgramError("short-turn outcome lacks a declared A-E policy")
        if cell.short_turn_policy is not None and declared_policy != cell.short_turn_policy:
            raise H2ProgramError("short-turn outcome policy differs from cell")
        if value.get("duration_bin") != short_turn_duration_bin(duration):
            raise H2ProgramError("short-turn duration bin differs from exact bounds")
    advanced = cell.memory_level in {
        "M4_ACTIVE_ROSTER_DECAY",
        "M5_CLUSTER_RECONCILIATION",
    }
    if value["confidence_decay_policy_enabled"] is not advanced:
        raise H2ProgramError("confidence-decay execution differs from memory level")
    if value["confidence_decay_applied"] and not advanced:
        raise H2ProgramError("non-M4/M5 outcome claims confidence decay")
    if value["identity_decision_attempted"] and not value[
        "full_gallery_completed_before_decision"
    ]:
        raise H2ProgramError("identity decision preceded full-gallery completion")
    if value["active_roster_prior_applied"] and not advanced:
        raise H2ProgramError("non-M4/M5 outcome claims an active-roster prior")
    if value["cluster_reconciliation_applied"]:
        if cell.memory_level != "M5_CLUSTER_RECONCILIATION":
            raise H2ProgramError("non-M5 outcome claims cluster reconciliation")
        value["cluster_reconciliation_similarity"] = _finite(
            value.get("cluster_reconciliation_similarity"),
            "cluster_reconciliation_similarity",
        )
    if value.get("reference_truth_state") not in {"KNOWN", "UNKNOWN"}:
        raise H2ProgramError("outcome lacks a scorable reference truth state")
    if value["reference_truth_state"] == "KNOWN" and not value.get(
        "reference_enrolled_id"
    ):
        raise H2ProgramError("known reference turn lacks enrolled identity")
    if not str(value.get("reference_global_speaker_id") or "").strip():
        raise H2ProgramError("outcome lacks a reference global speaker")
    return value


def write_exact_runtime_cell(
    path: Path,
    *,
    cell: CausalCellSpec,
    source_binding: Mapping[str, object],
    runtime_events: Sequence[Mapping[str, object]],
    outcomes: Sequence[Mapping[str, object]],
    execution_metadata: Mapping[str, object],
) -> dict[str, object]:
    """Write or exactly reuse one immutable, restart-safe causal cell.

    ``runtime_events`` must be the actual ordered event rows for this cell.
    Reference-enriched ``outcomes`` may be constructed only after those events
    have been emitted.  The raw event payload is not copied into the compact
    evidence file, but its canonical digest and every cited event ID are bound.
    """

    if not cell.executable:
        raise H2ProgramError(
            f"{cell.memory_level} is unsupported and may not produce measured evidence"
        )
    binding = validate_source_binding(source_binding)
    events = tuple(dict(row) for row in runtime_events)
    if not events:
        raise H2ProgramError("exact causal cell has no runtime events")
    if any("live_projection" in row for row in events):
        raise H2ProgramError("runtime event stream contains forbidden live_projection")
    event_ids = [str(row.get("event_id") or "") for row in events]
    if any(not event_id for event_id in event_ids) or len(event_ids) != len(set(event_ids)):
        raise H2ProgramError("runtime event IDs are empty or duplicated")
    event_sequence_keys = [
        (_event_case_id(row), int(row.get("event_sequence", -1))) for row in events
    ]
    if len(event_sequence_keys) != len(set(event_sequence_keys)) or any(
        sequence < 0 for _case_id, sequence in event_sequence_keys
    ):
        raise H2ProgramError("runtime event sequence is duplicated or negative")
    by_case_sequences: dict[str, list[int]] = defaultdict(list)
    for case_id, sequence in event_sequence_keys:
        by_case_sequences[case_id].append(sequence)
    if any(values != sorted(values) for values in by_case_sequences.values()):
        raise H2ProgramError("runtime event sequence is not ordered within a case")
    actual_event_sha = canonical_sha256(events)
    if actual_event_sha != binding["runtime_event_log_sha256"]:
        raise H2ProgramError("runtime event payload differs from its bound checksum")
    metadata = dict(execution_metadata)
    if metadata.get("completion_state") != "complete":
        raise H2ProgramError("partial runtime cell may not be scored")
    if metadata.get("runtime_tuning_sha256") != binding["runtime_config_sha256"]:
        raise H2ProgramError("execution metadata runtime configuration differs")
    if metadata.get("memory_level") != cell.memory_level:
        raise H2ProgramError("execution metadata memory level differs")
    seconds, mode, _label = expiry_identity(cell.expiry)
    if float(metadata.get("identity_expiry_sec") or -1.0) != seconds or str(
        metadata.get("identity_expiry_mode")
    ) != mode:
        raise H2ProgramError("execution metadata expiry differs")
    if metadata.get("short_turn_policy") != cell.short_turn_policy:
        raise H2ProgramError("execution metadata short-turn policy differs")
    validated = tuple(
        validate_runtime_outcome(
            row,
            cell=cell,
            binding=binding,
            source_event_ids=set(event_ids),
        )
        for row in outcomes
    )
    if not validated:
        raise H2ProgramError("exact causal cell has no scorable runtime outcomes")
    payload: dict[str, object] = {
        "schema_version": CAUSAL_MEMORY_SCHEMA_VERSION,
        "status": "MEASURED",
        "cell": cell.to_jsonable(),
        "source_binding": binding,
        "runtime_event_count": len(events),
        "runtime_event_payload_sha256": actual_event_sha,
        "runtime_event_ids_sha256": canonical_sha256(event_ids),
        "execution_metadata": metadata,
        "outcomes": list(validated),
        "metrics": score_runtime_outcomes(validated),
        "metrics_by_development_role": {
            role: score_runtime_outcomes(
                [
                    row
                    for row in validated
                    if row["effective_calibration_role"] == role
                ]
            )
            for role in sorted(DEVELOPMENT_ROLES)
            if any(row["effective_calibration_role"] == role for row in validated)
        },
        "metric_scope": "END_TO_END_ON_EXACT_RUNTIME_TURNS",
        "conditional_metrics_scope": "CONDITIONAL_ON_OBSERVED_SEGMENTATION_AND_CLUSTER_ASSIGNMENTS",
        "truth_used_only_after_runtime_decisions": True,
        "evaluation_material_inspected": False,
        "active_roster_narrowed_gallery": False,
        "confidence_decay_measured": cell.memory_level
        in {"M4_ACTIVE_ROSTER_DECAY", "M5_CLUSTER_RECONCILIATION"},
        "active_roster_prior_measured": cell.memory_level
        in {"M4_ACTIVE_ROSTER_DECAY", "M5_CLUSTER_RECONCILIATION"},
        "cluster_reconciliation_measured": cell.memory_level
        == "M5_CLUSTER_RECONCILIATION",
    }
    payload["evidence_sha256"] = canonical_sha256(payload)
    destination = Path(path)
    existed = destination.is_file()
    write_once_or_verify(destination, payload)
    return {**payload, "write_disposition": "REUSED" if existed else "CREATED"}


def load_exact_runtime_cell(
    path: Path,
    *,
    expected_cell: CausalCellSpec | None = None,
    expected_assignment_sha256: str | None = None,
) -> dict[str, object]:
    """Load one completed cell and revalidate every immutable binding."""

    value = read_json(path)
    if value.get("schema_version") != CAUSAL_MEMORY_SCHEMA_VERSION:
        raise H2ProgramError("unexpected exact causal-memory evidence schema")
    unsigned = dict(value)
    supplied = unsigned.pop("evidence_sha256", None)
    if not _is_sha256(supplied) or canonical_sha256(unsigned) != str(supplied):
        raise H2ProgramError("exact causal-memory evidence checksum differs")
    raw_cell = value.get("cell")
    if not isinstance(raw_cell, Mapping):
        raise H2ProgramError("exact causal-memory cell declaration is missing")
    expiry = (
        "END_SESSION"
        if raw_cell.get("identity_expiry_mode") == "end_session"
        else float(raw_cell["identity_expiry_sec"])
    )
    cell = CausalCellSpec(
        str(raw_cell["memory_level"]),
        expiry,
        str(raw_cell["short_turn_policy"])
        if raw_cell.get("short_turn_policy") is not None
        else None,
    )
    if raw_cell.get("cell_id") != cell.cell_id:
        raise H2ProgramError("stored causal cell ID differs from its axes")
    if expected_cell is not None and cell != expected_cell:
        raise H2ProgramError("exact causal-memory evidence is for another cell")
    raw_binding = value.get("source_binding")
    if not isinstance(raw_binding, Mapping):
        raise H2ProgramError("exact causal-memory source binding is missing")
    binding = validate_source_binding(raw_binding)
    if expected_assignment_sha256 is not None and str(
        binding["assignment_sha256"]
    ) != _require_sha256(expected_assignment_sha256, "expected_assignment_sha256"):
        raise H2ProgramError("exact causal-memory assignment differs")
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        raise H2ProgramError("exact causal-memory outcomes are missing")
    event_ids_sha = _require_sha256(
        value.get("runtime_event_ids_sha256"), "runtime_event_ids_sha256"
    )
    # The compact artifact intentionally does not duplicate the potentially
    # sensitive runtime log. Outcome validation still confirms event linkage at
    # write time, and this digest binds the immutable set on reload.
    if value.get("status") != "MEASURED" or event_ids_sha == "0" * 64:
        raise H2ProgramError("exact causal-memory evidence is not measured")
    if value.get("truth_used_only_after_runtime_decisions") is not True:
        raise H2ProgramError("exact causal-memory evidence violates the truth firewall")
    if value.get("evaluation_material_inspected") is not False:
        raise H2ProgramError("exact causal-memory evidence inspected held-out material")
    if value.get("active_roster_narrowed_gallery") is not False:
        raise H2ProgramError("exact causal-memory evidence narrowed the gallery")
    return value


def short_turn_duration_bin(duration_sec: float) -> str:
    duration = _finite(duration_sec, "duration_sec", minimum=0.0)
    if duration < 0.5:
        return "LT_0P5"
    if duration < 1.0:
        return "GE_0P5_LT_1P0"
    if duration <= 2.0:
        return "GE_1P0_LE_2P0"
    return "GT_2P0"


def score_runtime_outcomes(
    outcomes: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Score exact decisions; no transition is simulated in this function."""

    rows = [dict(row) for row in outcomes]
    if not rows:
        raise H2ProgramError("cannot score an empty exact runtime cell")
    known = [row for row in rows if row["reference_truth_state"] == "KNOWN"]
    unknown = [row for row in rows if row["reference_truth_state"] == "UNKNOWN"]
    returning = [row for row in known if bool(row["returning_turn"])]
    first = [row for row in known if not bool(row["returning_turn"])]
    short = [row for row in rows if bool(row["short_turn"])]

    def correct(row: Mapping[str, object]) -> bool:
        label = row.get("display_enrolled_id")
        return label is not None and str(label) == str(row.get("reference_enrolled_id"))

    def wrong_known(row: Mapping[str, object]) -> bool:
        label = row.get("display_enrolled_id")
        return label is not None and not correct(row)

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    first_latencies = [
        float(row["first_name_latency_sec"])
        for row in first
        if correct(row) and row.get("first_name_latency_sec") is not None
    ]
    returning_latencies = [
        float(row["first_name_latency_sec"])
        for row in returning
        if correct(row) and row.get("first_name_latency_sec") is not None
    ]
    confirmed_latencies = [
        float(row["confirmed_name_latency_sec"])
        for row in known
        if correct(row) and row.get("confirmed_name_latency_sec") is not None
    ]
    clusters_by_speaker: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        clusters_by_speaker[str(row["reference_global_speaker_id"])].add(
            str(
                row.get("effective_anonymous_speaker_id")
                or row["anonymous_speaker_id"]
            )
        )
    short_by_bin = Counter(str(row.get("duration_bin")) for row in short)
    short_correct_by_bin = Counter(
        str(row.get("duration_bin")) for row in short if correct(row)
    )
    contradiction_rows = [
        row for row in short if str(row.get("contradiction_outcome") or "NONE") != "NONE"
    ]
    return {
        "turn_count": len(rows),
        "known_turn_count": len(known),
        "unknown_turn_count": len(unknown),
        "correct_known_turn_rate": ratio(sum(correct(row) for row in known), len(known)),
        "wrong_known_turn_rate": ratio(sum(wrong_known(row) for row in known), len(known)),
        "stranger_false_known_turn_rate": ratio(
            sum(row.get("display_enrolled_id") is not None for row in unknown),
            len(unknown),
        ),
        "warm_reacquisition_rate": ratio(
            sum(correct(row) and bool(row["inherited_name"]) for row in returning),
            len(returning),
        ),
        "first_turn_name_latency_sec_mean": (
            sum(first_latencies) / len(first_latencies) if first_latencies else None
        ),
        "returning_turn_name_latency_sec_mean": (
            sum(returning_latencies) / len(returning_latencies)
            if returning_latencies
            else None
        ),
        "confirmed_name_latency_sec_mean": (
            sum(confirmed_latencies) / len(confirmed_latencies)
            if confirmed_latencies
            else None
        ),
        "short_turn_count": len(short),
        "short_turn_correct_name_rate": ratio(
            sum(correct(row) for row in short), len(short)
        ),
        "short_turn_correct_rate_by_duration": {
            duration_bin: ratio(
                short_correct_by_bin[duration_bin], short_by_bin[duration_bin]
            )
            for duration_bin in SHORT_TURN_BINS
        },
        "stale_inheritance_rate": ratio(
            sum(bool(row["stale_inheritance"]) for row in short), len(short)
        ),
        "false_inheritance_rate": ratio(
            sum(bool(row["false_inheritance"]) for row in short), len(short)
        ),
        "new_speaker_lockout_rate": ratio(
            sum(bool(row["new_speaker_lockout"]) for row in rows), len(rows)
        ),
        "fragmentation_reference_speaker_rate": ratio(
            sum(len(clusters) > 1 for clusters in clusters_by_speaker.values()),
            len(clusters_by_speaker),
        ),
        "reentry_consistency_rate": ratio(
            sum(bool(row["reentry_consistent"]) for row in returning),
            len(returning),
        ),
        "embedding_calls": sum(int(row["embedding_calls"]) for row in rows),
        "embedding_calls_avoided": sum(
            int(row["embedding_calls_avoided"]) for row in rows
        ),
        "embedding_compute_sec": sum(
            float(row.get("embedding_compute_sec") or 0.0) for row in rows
        ),
        "compute_saved_sec": (
            sum(
                float(row["compute_saved_sec"])
                for row in rows
                if row.get("compute_saved_sec") is not None
            )
            if any(row.get("compute_saved_sec") is not None for row in rows)
            else None
        ),
        "compute_saved_sec_status": (
            "MEASURED"
            if any(row.get("compute_saved_sec") is not None for row in rows)
            else "UNSUPPORTED_CAPABILITY_NO_PAIRED_FRESH_RUNTIME_COST"
        ),
        "correction_rate": ratio(
            sum(bool(row["correction_observed"]) for row in rows), len(rows)
        ),
        "retraction_rate": ratio(
            sum(bool(row["retraction_observed"]) for row in rows), len(rows)
        ),
        "expiry_observed_count": sum(bool(row["expiry_observed"]) for row in rows),
        "contradiction_event_count": len(contradiction_rows),
        "contradiction_outcomes": dict(
            sorted(
                Counter(
                    str(row.get("contradiction_outcome"))
                    for row in contradiction_rows
                ).items()
            )
        ),
        "maximum_bounded_cluster_count": max(
            int(row["bounded_cluster_count"]) for row in rows
        ),
        "maximum_bounded_identity_history_count": max(
            int(row["bounded_identity_history_count"]) for row in rows
        ),
        "maximum_bounded_roster_count": max(
            int(row["bounded_roster_count"]) for row in rows
        ),
        "confidence_decay_status": (
            "MEASURED_CAUSAL_SOURCE_CLOCK"
            if any(bool(row["confidence_decay_policy_enabled"]) for row in rows)
            else "NOT_ENABLED_FOR_CELL"
        ),
        "confidence_decay_release_count": sum(
            bool(row["confidence_decay_applied"]) for row in rows
        ),
        "active_roster_prior_status": (
            "MEASURED_FULL_GALLERY_SEARCH_ORDER"
            if any(bool(row["confidence_decay_policy_enabled"]) for row in rows)
            else "NOT_ENABLED_FOR_CELL"
        ),
        "active_roster_prior_application_count": sum(
            bool(row["active_roster_prior_applied"]) for row in rows
        ),
        "full_gallery_completion_rate": ratio(
            sum(
                bool(row["full_gallery_completed_before_decision"])
                for row in rows
                if bool(row["identity_decision_attempted"])
            ),
            sum(bool(row["identity_decision_attempted"]) for row in rows),
        ),
        "cluster_reconciliation_application_count": sum(
            bool(row["cluster_reconciliation_applied"]) for row in rows
        ),
        "cluster_reconciliation_contamination_rate": ratio(
            sum(bool(row["cluster_reconciliation_contaminated"]) for row in rows),
            sum(bool(row["cluster_reconciliation_applied"]) for row in rows),
        ),
        "metric_scope": "END_TO_END_ON_EXACT_RUNTIME_TURNS",
        "conditional_scope": "OBSERVED_SEGMENTATION_AND_CLUSTER_ASSIGNMENTS",
    }


def unsupported_cell(cell: CausalCellSpec, *, reason: str) -> dict[str, object]:
    row = {
        "schema_version": "h2-causal-memory-capability-row.v1",
        "status": "UNSUPPORTED_CAPABILITY",
        **cell.to_jsonable(),
        "reason": reason,
        "metrics": None,
        "promotion_eligible": False,
    }
    row["outcome_sha256"] = canonical_sha256(row)
    return row


def exact_evidence_coverage(
    evidence_by_cell: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Return complete M0-M5 x expiry coverage without substituting evidence."""

    rows: list[dict[str, object]] = []
    for cell in declared_memory_cells():
        evidence = evidence_by_cell.get(cell.cell_id)
        if evidence is None:
            rows.append(
                unsupported_cell(
                    cell,
                    reason=(
                        "no checksum-valid exact development runtime execution exists "
                        "for this memory/expiry cell"
                    ),
                )
            )
            continue
        if evidence.get("schema_version") != CAUSAL_MEMORY_SCHEMA_VERSION or evidence.get(
            "status"
        ) != "MEASURED":
            raise H2ProgramError(f"invalid exact evidence for {cell.cell_id}")
        metadata = evidence.get("execution_metadata")
        execution = dict(metadata) if isinstance(metadata, Mapping) else {}
        raw_decay = execution.get("confidence_decay")
        decay_policy = dict(raw_decay) if isinstance(raw_decay, Mapping) else {}
        raw_reconciliation = execution.get("reconciliation_policy")
        reconciliation_policy = (
            dict(raw_reconciliation)
            if isinstance(raw_reconciliation, Mapping)
            else {}
        )
        row = {
            "schema_version": "h2-causal-memory-capability-row.v1",
            "status": "MEASURED",
            **cell.to_jsonable(),
            "confidence_decay_half_life_sec": decay_policy.get("half_life_sec"),
            "confidence_decay_release_floor": decay_policy.get("release_floor"),
            "cluster_reconciliation_threshold": reconciliation_policy.get(
                "threshold"
            ),
            "cluster_reconciliation_max_gap_sec": reconciliation_policy.get(
                "maximum_gap_sec"
            ),
            "cluster_reconciliation_min_embeddings": reconciliation_policy.get(
                "minimum_embeddings_per_cluster"
            ),
            "evidence_sha256": evidence.get("evidence_sha256"),
            "metrics": dict(evidence.get("metrics") or {}),
            "promotion_eligible": True,
        }
        row["outcome_sha256"] = canonical_sha256(row)
        rows.append(row)
    decay_source_id = CausalCellSpec(
        "M4_ACTIVE_ROSTER_DECAY", "END_SESSION"
    ).cell_id
    decay_evidence = evidence_by_cell.get(decay_source_id)
    if decay_evidence is None:
        decay = {
            "schema_version": "h2-causal-memory-capability-row.v1",
            "status": "UNSUPPORTED_CAPABILITY",
            "cell_id": "CONFIDENCE_BASED_DECAY",
            "evidence_cell_id": decay_source_id,
            "memory_level": "NOT_APPLICABLE",
            "identity_expiry_sec": None,
            "identity_expiry_mode": "confidence_based",
            "expiry_cell": "CONFIDENCE_BASED_DECAY",
            "short_turn_policy": None,
            "runtime_execution_required": True,
            "reason": "no checksum-valid M4 end-session decay execution exists",
            "metrics": None,
            "promotion_eligible": False,
        }
    else:
        decay_metadata = decay_evidence.get("execution_metadata")
        decay_execution = (
            dict(decay_metadata) if isinstance(decay_metadata, Mapping) else {}
        )
        raw_decay_policy = decay_execution.get("confidence_decay")
        decay_policy = (
            dict(raw_decay_policy)
            if isinstance(raw_decay_policy, Mapping)
            else {}
        )
        decay = {
            "schema_version": "h2-causal-memory-capability-row.v1",
            "status": "MEASURED",
            "cell_id": "CONFIDENCE_BASED_DECAY",
            "evidence_cell_id": decay_source_id,
            "memory_level": "NOT_APPLICABLE",
            "identity_expiry_sec": None,
            "identity_expiry_mode": "confidence_based",
            "expiry_cell": "CONFIDENCE_BASED_DECAY",
            "short_turn_policy": None,
            "runtime_execution_required": True,
            "confidence_decay_half_life_sec": decay_policy.get("half_life_sec"),
            "confidence_decay_release_floor": decay_policy.get("release_floor"),
            "evidence_sha256": decay_evidence.get("evidence_sha256"),
            "metrics": dict(decay_evidence.get("metrics") or {}),
            "promotion_eligible": True,
        }
    decay["outcome_sha256"] = canonical_sha256(decay)
    rows.append(decay)
    return tuple(rows)


def load_exact_evidence_directory(
    root: Path,
    *,
    expected_assignment_sha256: str,
) -> dict[str, dict[str, object]]:
    """Load all immutable cells below ``root`` and reject duplicates.

    A stopped campaign may leave only a subset of cells.  The subset is valid;
    coverage builders turn missing declarations into precise unsupported rows.
    A corrupt existing cell is not treated as missing and fails closed.
    """

    directory = Path(root)
    if not directory.is_dir():
        return {}
    cells: dict[str, dict[str, object]] = {}
    for path in sorted(directory.rglob("evidence.json")):
        evidence = load_exact_runtime_cell(
            path, expected_assignment_sha256=expected_assignment_sha256
        )
        raw_cell = evidence.get("cell")
        if not isinstance(raw_cell, Mapping):  # guarded by loader
            raise H2ProgramError("exact causal-memory cell declaration is missing")
        cell_id = str(raw_cell["cell_id"])
        if cell_id in cells:
            raise H2ProgramError(f"duplicate exact causal-memory cell: {cell_id}")
        cells[cell_id] = evidence
    return cells


def exact_short_turn_coverage(
    evidence_by_cell: Mapping[str, Mapping[str, object]],
    *,
    memory_level: str = "M3_SHORT_TURN",
    expiry: float | str = 60.0,
    role: str = "selection",
    unsupported_reasons: Mapping[str, str] | None = None,
) -> tuple[dict[str, object], ...]:
    """Account for A-E by exact duration bin using only runtime outcomes."""

    if role not in DEVELOPMENT_ROLES:
        raise H2ProgramError("short-turn scoring role must be development-only")
    rows: list[dict[str, object]] = []
    for cell in declared_short_turn_cells(memory_level=memory_level, expiry=expiry):
        evidence = evidence_by_cell.get(cell.cell_id)
        for duration_bin in SHORT_TURN_BINS:
            axes = {
                **cell.to_jsonable(),
                "duration_bin": duration_bin,
                "effective_calibration_role": role,
            }
            if evidence is None:
                row = {
                    "schema_version": "h2-causal-short-turn-capability-row.v1",
                    "status": "UNSUPPORTED_CAPABILITY",
                    **axes,
                    "reason": (
                        str((unsupported_reasons or {}).get(cell.cell_id))
                        if (unsupported_reasons or {}).get(cell.cell_id)
                        else "no checksum-valid exact development runtime execution exists "
                        "for this short-turn policy"
                    ),
                    "metrics": None,
                    "promotion_eligible": False,
                }
            else:
                outcomes = [
                    dict(value)
                    for value in evidence.get("outcomes", ())
                    if isinstance(value, Mapping)
                    and value.get("effective_calibration_role") == role
                    and value.get("short_turn") is True
                    and value.get("duration_bin") == duration_bin
                ]
                if not outcomes:
                    row = {
                        "schema_version": "h2-causal-short-turn-capability-row.v1",
                        "status": "UNSUPPORTED_CAPABILITY",
                        **axes,
                        "reason": (
                            "exact runtime evidence contains no development turn in "
                            "this duration bin"
                        ),
                        "metrics": None,
                        "promotion_eligible": False,
                    }
                else:
                    row = {
                        "schema_version": "h2-causal-short-turn-capability-row.v1",
                        "status": "MEASURED",
                        **axes,
                        "evidence_sha256": evidence.get("evidence_sha256"),
                        "metrics": score_runtime_outcomes(outcomes),
                        "promotion_eligible": True,
                    }
            row["outcome_sha256"] = canonical_sha256(row)
            rows.append(row)
    return tuple(rows)


__all__ = [
    "CAUSAL_MEMORY_BINDING_SCHEMA_VERSION",
    "CAUSAL_MEMORY_OUTCOME_SCHEMA_VERSION",
    "CAUSAL_MEMORY_SCHEMA_VERSION",
    "CausalCellSpec",
    "EXECUTABLE_MEMORY_LEVELS",
    "EXPIRY_CELLS",
    "MEMORY_LEVELS",
    "SHORT_TURN_BINS",
    "SHORT_TURN_POLICIES",
    "declared_memory_cells",
    "declared_short_turn_cells",
    "exact_evidence_coverage",
    "exact_short_turn_coverage",
    "expiry_identity",
    "load_exact_runtime_cell",
    "load_exact_evidence_directory",
    "score_runtime_outcomes",
    "short_turn_duration_bin",
    "unsupported_cell",
    "validate_runtime_outcome",
    "validate_source_binding",
    "write_exact_runtime_cell",
]
