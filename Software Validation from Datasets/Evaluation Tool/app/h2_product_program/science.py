"""Development-only H2 policy replay and scientific summaries.

Most handlers consume completed development observations without neural
inference.  R3/R4 embedding reuse delegates to a bounded paired runtime
protocol, while the session-memory and short-turn handlers execute the exact
``SessionIdentityManager`` primitive over checksum-bound development runtime
events.  Evaluation observations are rejected at the input boundary.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
from itertools import product
import math
from pathlib import Path
import random
import statistics
from typing import Iterable, Mapping, Sequence

from app.full_pipeline_evaluation.results import validate_result_tree
from app.full_pipeline.identity import (
    ClusterCreation,
    IdentityEvidence,
    IdentityPolicy,
    IdentityState,
    SessionIdentityManager,
)

from .causal_memory import (
    CAUSAL_MEMORY_BINDING_SCHEMA_VERSION,
    SHORT_TURN_POLICIES as CAUSAL_SHORT_TURN_POLICIES,
    CausalCellSpec,
    UnsupportedCausalCapability,
    calibrate_reconciliation_policy,
    declared_memory_cells,
    declared_short_turn_cells,
    exact_evidence_coverage,
    exact_short_turn_coverage,
    execute_causal_primitive_cell,
    read_ordered_runtime_events,
    score_runtime_outcomes,
    write_exact_runtime_cell,
)
from .contracts import H2Job, H2ProgramError, ProgramPaths
from .io import (
    canonical_sha256,
    read_json,
    read_jsonl,
    read_yaml,
    sha256_file,
    write_csv_atomic,
    write_json_atomic,
    write_jsonl_atomic,
)
from .selection import (
    SAFETY_PRIORITY_CONTRACT_ID,
    SAFETY_PRIORITY_ORDERED_RISK_FAMILIES,
)


OBSERVATION_SCHEMA_VERSION = "full-pipeline-challenger-score-observation.v1"
POLICY_REPLAY_SCHEMA_VERSION = "h2-open-set-policy-replay.v1"
TARGET_FPIRS = (0.001, 0.005, 0.01, 0.02, 0.05)
MARGINS = (0.01, 0.02, 0.03, 0.04, 0.05)
EVIDENCE_DURATIONS = (1.0, 1.5, 2.0, 2.5, 3.0)
CONSISTENCY_THRESHOLDS = (0.30, 0.35, 0.40)
POST_PROMOTION_CONFIGURATION = "H2_POST_PROMOTION_INTEGRATION"
POST_PROMOTION_JOB_KIND = "post_promotion_integration"
SCIENCE_JOB_KINDS = frozenset(
    {
        "embedding_reuse_parity",
        "policy_replay",
        "integrated_enrollment",
        "memory_policy_replay",
        "short_turn_replay",
        "transcript_policy_replay",
        "bootstrap",
    }
)
HISTORICAL_EVIDENCE_RELATIVE_PATH = Path(
    "configs/automated_evaluation/h2_historical_evidence.v1.yaml"
)
BOOTSTRAP_REPETITIONS = 2000
BOOTSTRAP_SEED = 3800
TRANSCRIPT_POLICY_PRIORITY = (
    ("wrong_known_time_sec", "min"),
    ("stranger_false_known_time_sec", "min"),
    ("transcript_revision_count", "min"),
    ("speaker_attributed_wer", "min"),
    ("correct_transcribed_attributed_word_rate", "max"),
    ("stable_prefix_latency_sec", "min"),
    ("endpoint_to_final_latency_sec", "min"),
)

NAMED_HYSTERESIS_POLICIES = (
    "H0_ONE_PASS_DIAGNOSTIC",
    "H1_TWO_CONFIRM_TWO_RELEASE",
    "H2A_ADAPTIVE_EARLY",
    "H3_THREE_CONFIRM_SAFE",
    "H4_DURATION_DEPENDENT",
)
MEMORY_LEVELS = (
    "M0_STATELESS",
    "M1_CLUSTER",
    "M2_CONFIRMED_NAME",
    "M3_SHORT_TURN",
    "M4_ACTIVE_ROSTER_DECAY",
    "M5_CLUSTER_RECONCILIATION",
)
EXPIRY_CELLS: tuple[float | str, ...] = (
    15.0,
    30.0,
    60.0,
    120.0,
    "end_of_session",
)
SHORT_TURN_DURATION_BINS = ("LT_0P5", "GE_0P5_LT_1P0", "GE_1P0_LE_2P0")
SHORT_TURN_POLICIES = (
    "FRESH_EMBEDDING_REQUIRED",
    "ANONYMOUS_CLUSTER_INHERITANCE",
    "CONFIRMED_NAME_INHERITANCE",
    "INHERITANCE_WITH_CONTRADICTION_CHECKS",
    "GENERIC_UNTIL_LATER_CORRECTION",
)
ENROLLMENT_MATRIX_AXES: Mapping[str, tuple[object, ...]] = {
    "utterances": (3, 5),
    "total_duration_sec": (10.0, 20.0),
    "sessions": ("single", "varied"),
    "aggregation": ("normalized_mean", "frozen_redim_multi_template"),
    "quality_filter": ("blind_accept", "quality_filtered"),
}


@dataclass(frozen=True)
class OpenSetPolicy:
    """One development-selected maximum-gallery open-set decision policy."""

    gallery_requested_size: str
    target_fpir: float
    score_threshold: float
    margin_threshold: float
    minimum_evidence_sec: float
    minimum_embedding_consistency: float

    def to_jsonable(self) -> dict[str, object]:
        return {
            "gallery_requested_size": self.gallery_requested_size,
            "target_fpir": self.target_fpir,
            "score_threshold": self.score_threshold,
            "margin_threshold": self.margin_threshold,
            "minimum_evidence_sec": self.minimum_evidence_sec,
            "minimum_embedding_consistency": self.minimum_embedding_consistency,
            "calibration_method": "maximum_gallery_score_plus_top1_top2_margin",
        }


def unsupported_capability_row(
    *,
    study_id: str,
    cell_id: str,
    reason: str,
    axes: Mapping[str, object],
    source_bindings: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Create an explicit, checksum-bound outcome without synthetic metrics."""

    if not study_id.strip() or not cell_id.strip() or not reason.strip():
        raise ValueError("unsupported capability rows require study/cell/reason")
    bindings = [dict(row) for row in source_bindings]
    core = {
        "schema_version": "h2-study-capability-outcome.v1",
        "study_id": study_id,
        "cell_id": cell_id,
        "status": "UNSUPPORTED_CAPABILITY",
        "reason": reason,
        **dict(axes),
        "source_bindings": bindings,
        "metrics_computed": False,
        "synthetic_metrics_emitted": False,
        "promotion_eligible": False,
        "development_only": True,
        "evaluation_material_inspected": False,
    }
    return {**core, "outcome_sha256": canonical_sha256(core)}


def measured_capability_row(
    *,
    study_id: str,
    cell_id: str,
    axes: Mapping[str, object],
    source_bindings: Sequence[Mapping[str, object]],
    metrics: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create a measured cell whose evidence identity is explicit."""

    if not source_bindings:
        raise ValueError("measured capability rows require source bindings")
    core = {
        "schema_version": "h2-study-capability-outcome.v1",
        "study_id": study_id,
        "cell_id": cell_id,
        "status": "MEASURED",
        "reason": None,
        **dict(axes),
        "source_bindings": [dict(row) for row in source_bindings],
        "metrics_computed": metrics is not None,
        "metrics": dict(metrics or {}),
        "synthetic_metrics_emitted": False,
        "promotion_eligible": True,
        "development_only": True,
        "evaluation_material_inspected": False,
    }
    return {**core, "outcome_sha256": canonical_sha256(core)}


def load_development_observations(
    result_roots: Iterable[Path],
) -> tuple[dict[str, object], ...]:
    """Load score observations from exact result trees and reject evaluation.

    Duplicate observations can appear when scientifically identical runtime
    configurations share a result.  Byte-equivalent duplicates are collapsed
    by ``observation_id``; conflicting duplicates fail closed.
    """

    by_id: dict[str, dict[str, object]] = {}
    for raw_root in result_roots:
        path = Path(raw_root) / "diagnostics/challenger_identity_scores.jsonl"
        if not path.is_file():
            continue
        for raw in read_jsonl(path):
            row = normalize_observation(raw)
            observation_id = str(row["observation_id"])
            previous = by_id.get(observation_id)
            if previous is not None and previous != row:
                raise H2ProgramError(
                    f"conflicting development observation: {observation_id}"
                )
            by_id[observation_id] = row
    observations = tuple(
        sorted(
            by_id.values(),
            key=lambda row: (
                str(row["pipeline_id"]),
                _gallery_sort_key(str(row["gallery_requested_size"])),
                str(row["case_id"]),
                str(row["anonymous_speaker_id"]),
                float(row["source_time_sec"]),
                str(row["observation_id"]),
            ),
        )
    )
    assignment_ids = {
        str(row["h2_calibration_assignment_sha256"])
        for row in observations
        if row.get("h2_calibration_assignment_sha256")
    }
    if len(assignment_ids) > 1:
        raise H2ProgramError(
            "mixed H2 calibration assignment identities entered one replay"
        )
    return observations


def normalize_observation(raw: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize one development score-vector observation."""

    row = dict(raw)
    if row.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
        raise H2ProgramError("unexpected open-set observation schema")
    if str(row.get("split")) != "development":
        raise H2ProgramError("open-set policy replay accepts development rows only")
    if bool(row.get("evaluation_material_inspected")):
        raise H2ProgramError("evaluation-inspected row entered development replay")
    effective_role = row.get("h2_calibration_role") or row.get("calibration_role")
    if str(effective_role) not in {"calibration", "selection"}:
        raise H2ProgramError("development row lacks a frozen calibration role")
    row["effective_calibration_role"] = str(effective_role)
    if str(row.get("truth_state")) not in {"KNOWN", "UNKNOWN"}:
        raise H2ProgramError("development row has an invalid truth state")
    if str(row.get("status")) not in {"VALID", "INVALID"}:
        raise H2ProgramError("development row has an invalid observation status")
    scores = row.get("candidate_raw_cosine_scores")
    if not isinstance(scores, Mapping):
        raise H2ProgramError("development row lacks a candidate score vector")
    normalized_scores = {
        str(key): _finite(value, "candidate score") for key, value in scores.items()
    }
    ranked = sorted(normalized_scores.items(), key=lambda item: (-item[1], item[0]))
    if not ranked and str(row.get("status")) == "VALID":
        raise H2ProgramError("development row has an empty candidate score vector")
    expected_count = int(row.get("gallery_size") or 0)
    if str(row.get("status")) == "VALID" and expected_count != len(ranked):
        raise H2ProgramError("valid score row has an incomplete gallery vector")
    row["candidate_raw_cosine_scores"] = dict(sorted(normalized_scores.items()))
    row["top1_candidate_id"] = ranked[0][0] if ranked else None
    row["top1_score"] = ranked[0][1] if ranked else None
    row["top2_candidate_id"] = ranked[1][0] if len(ranked) > 1 else None
    row["top2_score"] = ranked[1][1] if len(ranked) > 1 else -1.0
    row["top1_top2_margin"] = (
        float(row["top1_score"]) - float(row["top2_score"]) if ranked else None
    )
    row["source_time_sec"] = _finite(row.get("source_time_sec"), "source time")
    row["evidence_duration_sec"] = _finite(
        row.get("evidence_duration_sec"), "evidence duration"
    )
    row["embedding_consistency"] = _finite(
        row.get("embedding_consistency"), "embedding consistency"
    )
    if row["source_time_sec"] < 0 or row["evidence_duration_sec"] < 0:
        raise H2ProgramError("development row has a negative duration")
    return row


def build_policy_frontier(
    observations: Sequence[Mapping[str, object]],
    *,
    target_fpirs: Sequence[float] = TARGET_FPIRS,
    margins: Sequence[float] = MARGINS,
    evidence_durations: Sequence[float] = EVIDENCE_DURATIONS,
    consistency_thresholds: Sequence[float] = CONSISTENCY_THRESHOLDS,
) -> tuple[dict[str, object], ...]:
    """Calibrate and evaluate the complete development-only open-set grid.

    Thresholds use calibration-role UNKNOWN clusters only.  One final valid
    observation is retained per case/anonymous-cluster/gallery for each quality
    gate, preventing long recordings from contributing repeated correlated
    checkpoints.  The independent development selection cohort reports TPIR,
    FPIR, wrong-known, FNIR, and Unknown rejection.
    """

    normalized = tuple(normalize_observation(row) for row in observations)
    galleries = sorted(
        {str(row["gallery_requested_size"]) for row in normalized},
        key=_gallery_sort_key,
    )
    rows: list[dict[str, object]] = []
    for gallery in galleries:
        gallery_rows = [
            row
            for row in normalized
            if str(row["gallery_requested_size"]) == gallery
            and str(row["status"]) == "VALID"
            and not bool(row.get("predicted_overlap"))
        ]
        final = _last_per_cluster(gallery_rows)
        for evidence in evidence_durations:
            for consistency in consistency_thresholds:
                calibration_unknown = [
                    row
                    for row in final
                    if row["effective_calibration_role"] == "calibration"
                    and row["truth_state"] == "UNKNOWN"
                ]
                selection = [
                    row
                    for row in final
                    if row["effective_calibration_role"] == "selection"
                ]
                for margin in margins:
                    for target in target_fpirs:
                        if not calibration_unknown:
                            rows.append(
                                _unsupported_frontier_row(
                                    gallery, target, margin, evidence, consistency
                                )
                            )
                            continue
                        threshold, accepted_units, unit_count = (
                            _speaker_conservative_threshold(
                                calibration_unknown,
                                target_fpir=float(target),
                                margin=float(margin),
                                evidence=float(evidence),
                                consistency=float(consistency),
                            )
                        )
                        eligible_calibration_clusters = [
                            row
                            for row in calibration_unknown
                            if _quality_and_margin_passes(
                                row,
                                margin=float(margin),
                                evidence=float(evidence),
                                consistency=float(consistency),
                            )
                        ]
                        eligible_calibration_speakers = sum(
                            any(
                                _quality_and_margin_passes(
                                    row,
                                    margin=float(margin),
                                    evidence=float(evidence),
                                    consistency=float(consistency),
                                )
                                for row in speaker_rows
                            )
                            for speaker_rows in _unknown_speaker_groups(
                                calibration_unknown
                            ).values()
                        )
                        calibration_fpir = _accepted_fraction(
                            calibration_unknown,
                            threshold=threshold,
                            margin=float(margin),
                            evidence=float(evidence),
                            consistency=float(consistency),
                            group_unknown_speakers=True,
                        )
                        empirical_resolution = 1.0 / unit_count
                        target_resolvable = (
                            float(target) + 1.0e-15 >= empirical_resolution
                        )
                        zero_false_id_upper_95 = (
                            _zero_false_id_binomial_upper_95(unit_count)
                            if accepted_units == 0
                            else None
                        )
                        target_observed = (
                            calibration_fpir is not None
                            and calibration_fpir <= float(target) + 1.0e-15
                        )
                        target_demonstrated = bool(
                            target_resolvable
                            and target_observed
                            and (
                                zero_false_id_upper_95 is None
                                or zero_false_id_upper_95 <= float(target) + 1.0e-15
                            )
                        )
                        if not target_resolvable:
                            target_claim = "NOT_DEMONSTRATED_BELOW_EMPIRICAL_RESOLUTION"
                        elif (
                            zero_false_id_upper_95 is not None
                            and zero_false_id_upper_95 > float(target) + 1.0e-15
                        ):
                            target_claim = (
                                "NOT_DEMONSTRATED_ZERO_ERROR_UPPER_BOUND_EXCEEDS_TARGET"
                            )
                        elif target_demonstrated:
                            target_claim = "DEMONSTRATED_ON_CALIBRATION_COHORT"
                        else:
                            target_claim = (
                                "NOT_DEMONSTRATED_OBSERVED_FPIR_EXCEEDS_TARGET"
                            )
                        metrics = _decision_metrics(
                            selection,
                            threshold=threshold,
                            margin=float(margin),
                            evidence=float(evidence),
                            consistency=float(consistency),
                        )
                        rows.append(
                            {
                                "schema_version": POLICY_REPLAY_SCHEMA_VERSION,
                                "status": "COMPUTED",
                                "gallery_requested_size": gallery,
                                "target_fpir": float(target),
                                "score_threshold": threshold,
                                "margin_threshold": float(margin),
                                "minimum_evidence_sec": float(evidence),
                                "minimum_embedding_consistency": float(consistency),
                                "calibration_unknown_clusters": len(
                                    calibration_unknown
                                ),
                                "calibration_unknown_speakers": unit_count,
                                "margin_eligible_calibration_unknown_clusters": len(
                                    eligible_calibration_clusters
                                ),
                                "eligible_calibration_unknown_clusters": len(
                                    eligible_calibration_clusters
                                ),
                                "eligible_calibration_unknown_speakers": (
                                    eligible_calibration_speakers
                                ),
                                "accepted_calibration_unknown_speakers": accepted_units,
                                "margin_empty_fallback_used": not bool(
                                    eligible_calibration_clusters
                                ),
                                "calibration_unit": "reference_unknown_speaker_max_over_fragments",
                                "smallest_empirical_fpir_step": empirical_resolution,
                                "empirical_fpir_resolution": empirical_resolution,
                                "target_below_empirical_resolution": not target_resolvable,
                                "target_empirically_resolvable": target_resolvable,
                                "target_fpir_observed_at_or_below_target": target_observed,
                                "zero_false_id_binomial_upper_95": (
                                    zero_false_id_upper_95
                                ),
                                "target_fpir_demonstrated": target_demonstrated,
                                "target_fpir_claim": target_claim,
                                "observed_calibration_fpir": calibration_fpir,
                                "selection_rows": len(selection),
                                **metrics,
                                "development_only_selection": True,
                                "evaluation_material_inspected": False,
                            }
                        )
    return tuple(rows)


def select_balanced_policy(
    frontier: Sequence[Mapping[str, object]],
    *,
    preferred_target_fpir: float = 0.01,
    preferred_gallery: str = "full",
) -> tuple[OpenSetPolicy, dict[str, object]]:
    """Select one policy using the declared lexicographic safety priorities."""

    computed = [
        dict(row)
        for row in frontier
        if row.get("status") == "COMPUTED"
        and float(row.get("target_fpir") or -1.0) == preferred_target_fpir
        and int(row.get("selection_rows") or 0) > 0
    ]
    if not computed:
        raise H2ProgramError("no computed 1% development policy frontier rows")
    galleries = {str(row["gallery_requested_size"]) for row in computed}
    if preferred_gallery in galleries:
        selected_gallery = preferred_gallery
    elif preferred_gallery == "full" and "source_full" in galleries:
        selected_gallery = "source_full"
    else:
        selected_gallery = max(galleries, key=_gallery_sort_key)
    candidates = [
        row
        for row in computed
        if str(row["gallery_requested_size"]) == selected_gallery
    ]
    resolvable = [row for row in candidates if row["target_empirically_resolvable"]]
    pool = resolvable or candidates
    # No unexplained composite score: safety exposure is minimized first,
    # followed by correct-known yield and then lower latency/quality burden.
    selected = min(pool, key=_open_set_policy_selection_key)
    policy = OpenSetPolicy(
        gallery_requested_size=str(selected["gallery_requested_size"]),
        target_fpir=float(selected["target_fpir"]),
        score_threshold=float(selected["score_threshold"]),
        margin_threshold=float(selected["margin_threshold"]),
        minimum_evidence_sec=float(selected["minimum_evidence_sec"]),
        minimum_embedding_consistency=float(selected["minimum_embedding_consistency"]),
    )
    rationale = {
        "schema_version": "h2-open-set-policy-selection.v1",
        "selection_method": "predeclared_lexicographic_safety_then_yield",
        "safety_priority_contract_id": SAFETY_PRIORITY_CONTRACT_ID,
        "ordered_safety_risk_families": list(SAFETY_PRIORITY_ORDERED_RISK_FAMILIES),
        "ordered_priorities": [
            "minimize_selection_wrong_known_rate",
            "minimize_selection_unknown_speaker_fpir",
            "minimize_selection_stranger_fpir",
            "maximize_selection_tpir",
            "minimize_selection_fnir",
            "minimize_evidence_latency",
        ],
        "weighted_composite_used": False,
        "preferred_target_fpir": preferred_target_fpir,
        "preferred_gallery": preferred_gallery,
        "selected_gallery": selected_gallery,
        "selected_row": selected,
        "development_only_selection": True,
        "evaluation_material_inspected": False,
    }
    return policy, rationale


def _open_set_policy_selection_key(row: Mapping[str, object]) -> tuple[object, ...]:
    """Wrong-known risk must dominate every stranger exposure tie-break."""

    return (
        _metric_or_inf(row, "selection_wrong_known_rate"),
        _metric_or_inf(row, "selection_unknown_speaker_fpir"),
        _metric_or_inf(row, "selection_stranger_fpir"),
        -_metric_or_neg_inf(row, "selection_tpir"),
        _metric_or_inf(row, "selection_fnir"),
        float(row["minimum_evidence_sec"]),
        float(row["minimum_embedding_consistency"]),
        -float(row["margin_threshold"]),
        -float(row["score_threshold"]),
    )


def hubness_rows(
    observations: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Report which enrollment identities attract Unknown nearest matches."""

    normalized = [
        normalize_observation(row)
        for row in observations
        if str(row.get("status")) == "VALID"
        and str(row.get("truth_state")) == "UNKNOWN"
        and not bool(row.get("predicted_overlap"))
    ]
    final = _last_per_cluster(normalized)
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    score_max: dict[tuple[str, str, str], float] = {}
    margin_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in final:
        key = (
            str(row["gallery_requested_size"]),
            str(row["effective_calibration_role"]),
        )
        identity = str(row["top1_candidate_id"])
        grouped[key][identity] += 1
        identity_key = (*key, identity)
        score_max[identity_key] = max(
            score_max.get(identity_key, -math.inf), float(row["top1_score"])
        )
        margin_values[identity_key].append(float(row["top1_top2_margin"]))
    output: list[dict[str, object]] = []
    for key, counts in sorted(
        grouped.items(), key=lambda item: (_gallery_sort_key(item[0][0]), item[0][1])
    ):
        total = sum(counts.values())
        maximum_share = max(counts.values()) / total if total else None
        for identity, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        ):
            identity_key = (*key, identity)
            output.append(
                {
                    "schema_version": "h2-identity-hubness.v1",
                    "gallery_requested_size": key[0],
                    "development_role": key[1],
                    "enrolled_id": identity,
                    "unknown_top1_count": count,
                    "unknown_top1_share": count / total if total else None,
                    "gallery_maximum_hub_share": maximum_share,
                    "maximum_impostor_score": score_max[identity_key],
                    "mean_top1_top2_margin": sum(margin_values[identity_key])
                    / len(margin_values[identity_key]),
                    "development_only": True,
                    "evaluation_material_inspected": False,
                }
            )
    return tuple(output)


def selected_runtime_payload(
    policy: OpenSetPolicy, *, source_result_sha256: str | None = None
) -> dict[str, object]:
    """Return the controller hook for immutable development freeze merging."""

    return {
        "schema_version": "h2-science-handler-result.v1",
        "status": "COMPLETE",
        "selected_runtime_tuning": {
            "score_threshold": policy.score_threshold,
            "margin_threshold": policy.margin_threshold,
            "minimum_evidence_sec": policy.minimum_evidence_sec,
            "minimum_embedding_consistency": policy.minimum_embedding_consistency,
        },
        "selected_runtime_axes": [
            "score_threshold",
            "margin_threshold",
            "minimum_evidence_sec",
            "minimum_embedding_consistency",
        ],
        "source_result_sha256": source_result_sha256,
        "development_only_selection": True,
        "evaluation_material_inspected": False,
        "weighted_composite_used": False,
    }


def apply_frozen_integration_assignment(
    observations: Sequence[Mapping[str, object]],
    assignment: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    """Apply the frozen development partition without weakening its firewall.

    The worker's legacy role remains in each raw observation for provenance,
    but H2 policy science uses only the protocol role.  V2 additionally
    requires the worker-emitted role/checksum, rejects cross-cohort cases, and
    verifies that observed reference speakers do not cross roles.  V1 remains
    accepted only for isolated legacy evidence/tests.
    """

    schema = str(assignment.get("schema_version") or "")
    if schema not in {
        "h2-development-integration-partition.v1",
        "h2-development-integration-partition.v2",
    }:
        raise H2ProgramError("H2 integration calibration assignment is missing")
    if assignment.get("outcomes_used") is not False:
        raise H2ProgramError("H2 calibration assignment used outcomes")
    if schema == "h2-development-integration-partition.v1":
        if assignment.get("reference_content_used") is not False:
            raise H2ProgramError("H2 calibration assignment used reference content")
    else:
        if assignment.get("prediction_or_metric_inputs_used") is not False:
            raise H2ProgramError(
                "H2 calibration assignment used predictions or metrics"
            )
        if assignment.get("reference_transcript_or_audio_content_used") is not False:
            raise H2ProgramError(
                "H2 calibration assignment used transcript or audio content"
            )
        if assignment.get("reference_speaker_identity_metadata_used") is not True:
            raise H2ProgramError(
                "H2 v2 assignment does not declare its speaker-metadata input"
            )
    if assignment.get("evaluation_material_used") is not False:
        raise H2ProgramError("H2 calibration assignment used held-out material")
    assignment_sha = str(assignment.get("assignment_sha256") or "")
    unsigned = dict(assignment)
    unsigned.pop("assignment_sha256", None)
    if assignment_sha != canonical_sha256(unsigned):
        raise H2ProgramError("H2 integration assignment identity differs")
    calibration = set(map(str, assignment.get("calibration_case_ids") or ()))
    selection = set(map(str, assignment.get("selection_case_ids") or ()))
    excluded = (
        set(map(str, assignment.get("excluded_cross_cohort_case_ids") or ()))
        if schema == "h2-development-integration-partition.v2"
        else set()
    )
    if (
        not calibration
        or not selection
        or calibration & selection
        or calibration & excluded
        or selection & excluded
    ):
        raise H2ProgramError("H2 integration assignment is empty or overlapping")
    calibration_speakers: set[str] = set()
    selection_speakers: set[str] = set()
    if schema == "h2-development-integration-partition.v2":
        calibration_speakers = set(
            map(str, assignment.get("calibration_speaker_ids") or ())
        )
        selection_speakers = set(
            map(str, assignment.get("selection_speaker_ids") or ())
        )
        if not calibration_speakers or not selection_speakers:
            raise H2ProgramError("H2 v2 integration speaker roles are empty")
        if calibration_speakers & selection_speakers:
            raise H2ProgramError("H2 v2 integration speaker roles overlap")
        if int(assignment.get("speaker_overlap_count") or 0) != 0:
            raise H2ProgramError("H2 v2 assignment declares speaker overlap")
        if (
            assignment.get("excluded_cases_used_for_calibration_or_selection")
            is not False
        ):
            raise H2ProgramError("H2 v2 assignment reused excluded cases")
        expected_counts = {
            "calibration_case_count": len(calibration),
            "selection_case_count": len(selection),
            "excluded_cross_cohort_case_count": len(excluded),
            "calibration_speaker_count": len(calibration_speakers),
            "selection_speaker_count": len(selection_speakers),
        }
        for field, expected in expected_counts.items():
            if int(assignment.get(field) or -1) != expected:
                raise H2ProgramError(f"H2 v2 assignment {field} differs")
    output: list[dict[str, object]] = []
    observed_speakers: dict[str, set[str]] = {
        "calibration": set(),
        "selection": set(),
    }
    for raw in observations:
        row = dict(raw)
        case_id = str(row["case_id"])
        if case_id in excluded:
            raise H2ProgramError(
                f"excluded cross-cohort observation entered policy science: {case_id}"
            )
        in_calibration = case_id in calibration
        in_selection = case_id in selection
        if in_calibration == in_selection:
            raise H2ProgramError(
                f"integration observation is not assigned exactly once: {case_id}"
            )
        expected_role = "calibration" if in_calibration else "selection"
        if schema == "h2-development-integration-partition.v2":
            worker_role = str(row.get("h2_calibration_role") or "")
            worker_sha = str(row.get("h2_calibration_assignment_sha256") or "")
            if worker_role != expected_role:
                raise H2ProgramError(
                    f"worker H2 role differs from v2 assignment: {case_id}"
                )
            if worker_sha != assignment_sha:
                raise H2ProgramError(
                    f"worker H2 assignment checksum differs: {case_id}"
                )
            speaker_id = str(row.get("reference_global_speaker_id") or "")
            if speaker_id:
                observed_speakers[expected_role].add(speaker_id)
        row["legacy_calibration_role"] = row.get("calibration_role")
        row["h2_calibration_role"] = expected_role
        row["effective_calibration_role"] = row["h2_calibration_role"]
        row["h2_calibration_assignment_sha256"] = assignment_sha
        row["h2_assignment_schema_version"] = schema
        row["h2_excluded_cross_cohort_absent"] = True
        output.append(row)
    if schema == "h2-development-integration-partition.v2":
        if observed_speakers["calibration"] - calibration_speakers:
            raise H2ProgramError(
                "observed calibration speaker is outside its frozen cohort"
            )
        if observed_speakers["selection"] - selection_speakers:
            raise H2ProgramError(
                "observed selection speaker is outside its frozen cohort"
            )
        if observed_speakers["calibration"] & observed_speakers["selection"]:
            raise H2ProgramError(
                "observed integration speakers cross calibration/selection"
            )
        for row in output:
            row["h2_observed_speaker_firewall_validated"] = True
    return tuple(output)


def execute_science_job(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    """Execute one bounded H2 science job.

    Every handler writes a checksum-bound primary result and supporting tables.
    A missing prerequisite is a failed job, never an empty or fabricated
    success.  No handler opens evaluation material except the post-freeze
    bootstrap job, whose inputs are the already-completed held-out result trees.
    Handlers are replay-only except the two explicitly scheduled, bounded
    development-only R3/R4 paired neural qualifications delegated to
    :mod:`app.h2_product_program.reuse`.
    """

    handlers = {
        "policy_replay": _execute_policy_replay,
        "integrated_enrollment": _execute_integrated_enrollment,
        "memory_policy_replay": _execute_memory_policy_replay,
        "short_turn_replay": _execute_short_turn_replay,
        "transcript_policy_replay": _execute_transcript_policy_replay,
        "embedding_reuse_parity": _execute_embedding_reuse_parity,
        "bootstrap": _execute_hierarchical_bootstrap,
    }
    if job.job_kind not in SCIENCE_JOB_KINDS:
        raise H2ProgramError(f"unsupported science job kind: {job.job_kind}")
    try:
        payload, tables = handlers[job.job_kind](paths, job, state, jobs)
    except (H2ProgramError, OSError, ValueError, KeyError) as exc:
        payload = {
            "schema_version": "h2-science-handler-result.v1",
            "status": "FAILED_PREREQUISITE_OR_INVALID_EVIDENCE",
            "job_id": job.job_id,
            "job_kind": job.job_kind,
            "error": f"{type(exc).__name__}: {exc}",
            "marked_complete": False,
            "evaluation_material_inspected": job.job_kind == "bootstrap",
        }
        return _publish_science_result(paths, job, payload, {})
    return _publish_science_result(paths, job, payload, tables)


def _execute_policy_replay(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    source_job, source_root, source_identity = _integration_source(paths, state, jobs)
    observations, assignment = _integration_observations(paths, source_root)
    frontier = build_policy_frontier(observations)
    policy, rationale = select_balanced_policy(frontier)
    hubness = hubness_rows(observations)
    embedding_coverage = build_embedding_clustering_coverage(
        paths, state=state, jobs=jobs
    )
    assignment_sha = str(assignment["assignment_sha256"])
    role_counts = Counter(
        str(row["effective_calibration_role"]) for row in observations
    )
    invalid_count = sum(str(row["status"]) != "VALID" for row in observations)
    payload = {
        **selected_runtime_payload(policy, source_result_sha256=source_identity),
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "promotion_eligible": True,
        "source_runtime_job_id": source_job.job_id,
        "source_runtime_configuration_id": source_job.configuration_id,
        "source_runtime_result_root": str(source_root),
        "source_runtime_result_sha256": source_identity,
        "source_observation_count": len(observations),
        "invalid_observation_count": invalid_count,
        "effective_role_counts": dict(sorted(role_counts.items())),
        "integration_assignment_sha256": assignment_sha,
        "integration_independent_source_count": assignment.get(
            "independent_source_count"
        ),
        "calibration_source_count": assignment.get("calibration_source_count"),
        "selection_source_count": assignment.get("selection_source_count"),
        "selected_policy": policy.to_jsonable(),
        "selection_rationale": rationale,
        "gallery_labels_preserved_verbatim": True,
        "commonvoice_prior_pooled": False,
        "commonvoice_role": "external_diagnostic_prior_only",
        "speaker_fragment_independence_assumed": False,
        "calibration_unit": "reference_unknown_speaker_max_over_fragments",
        "neural_inference_performed": False,
        "embedding_clustering_declared_cell_count": len(embedding_coverage),
        "embedding_clustering_all_cells_accounted_for": all(
            row["status"] in {"MEASURED", "UNSUPPORTED_CAPABILITY"}
            for row in embedding_coverage
        ),
    }
    return payload, {
        "open_set_policy_frontier.csv": frontier,
        "identity_hubness.csv": hubness,
        "embedding_clustering_coverage.csv": embedding_coverage,
    }


def build_embedding_clustering_coverage(
    paths: ProgramPaths,
    *,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], ...]:
    """Account for every declared embedding/clustering development cell.

    A completed ordinary runtime result is accuracy evidence only.  It is
    never relabelled as matched-resource evidence.  R1/R2 resource evidence
    and R3/R4 paired-parity evidence are attached only when their own
    checksum-bound jobs have completed with the required contract fields.
    """

    declarations = _embedding_clustering_declarations(paths, jobs)
    output: list[dict[str, object]] = []
    for declaration in declarations:
        axis = str(declaration["axis"])
        value = declaration["value"]
        cell_id = f"{axis}={_coverage_cell_token(value)}"
        common = {
            "axis": axis,
            "cell_id": cell_id,
            "value": value,
            "selected": False,
            "selection_basis": "coverage_contract_is_not_a_selection_decision",
            "evidence_class": "accuracy_development",
            "matched_resource_evidence": False,
            "isolated_one_axis_comparison": False,
            "runtime_field": declaration.get("runtime_field"),
        }

        if axis == "redim_execution_strategy" and str(value).startswith(("R3_", "R4_")):
            parity = _reuse_parity_coverage_binding(state, jobs, strategy=str(value))
            parity_binding = parity.get("binding")
            bindings = (
                (dict(parity_binding),) if isinstance(parity_binding, Mapping) else ()
            )
            if parity.get("measured") is True:
                axes = {
                    **common,
                    "source_job_id": parity_binding["source_job_id"],
                    "source_result_sha256": parity_binding["source_result_sha256"],
                    "evidence_class": "paired_runtime_parity",
                }
                output.append(
                    measured_capability_row(
                        study_id="embedding_clustering_coverage",
                        cell_id=cell_id,
                        axes=axes,
                        source_bindings=bindings,
                    )
                )
            else:
                axes = {
                    **common,
                    "source_job_id": (
                        parity_binding.get("source_job_id")
                        if isinstance(parity_binding, Mapping)
                        else None
                    ),
                    "source_result_sha256": (
                        parity_binding.get("source_result_sha256")
                        if isinstance(parity_binding, Mapping)
                        else None
                    ),
                    "evidence_class": "paired_runtime_parity",
                }
                output.append(
                    unsupported_capability_row(
                        study_id="embedding_clustering_coverage",
                        cell_id=cell_id,
                        reason=str(parity["reason"]),
                        axes=axes,
                        source_bindings=bindings,
                    )
                )
            continue

        runtime_field = declaration.get("runtime_field")
        if runtime_field is None:
            output.append(
                unsupported_capability_row(
                    study_id="embedding_clustering_coverage",
                    cell_id=cell_id,
                    reason=str(declaration["unsupported_reason"]),
                    axes={
                        **common,
                        "source_job_id": None,
                        "source_result_sha256": None,
                    },
                )
            )
            continue

        accuracy = _completed_axis_runtime_binding(
            state,
            jobs,
            runtime_field=str(runtime_field),
            value=value,
        )
        if accuracy is None:
            output.append(
                unsupported_capability_row(
                    study_id="embedding_clustering_coverage",
                    cell_id=cell_id,
                    reason=(
                        "no checksum-valid completed declared development runtime "
                        "job measures this exact axis value"
                    ),
                    axes={
                        **common,
                        "source_job_id": None,
                        "source_result_sha256": None,
                    },
                )
            )
            continue

        bindings = [accuracy]
        matched_resource = None
        if axis == "redim_execution_strategy" and str(value) in {
            "R1_TWO_INDEPENDENT_MODELS",
            "R2_ONE_SHARED_MODEL",
        }:
            matched_resource = _completed_resource_binding(
                state, jobs, strategy=str(value)
            )
            if matched_resource is not None:
                bindings.append(matched_resource)
        axes = {
            **common,
            "source_job_id": accuracy["source_job_id"],
            "source_result_sha256": accuracy["source_result_sha256"],
            "matched_resource_evidence": matched_resource is not None,
            "matched_resource_source_job_id": (
                matched_resource["source_job_id"]
                if matched_resource is not None
                else None
            ),
            "matched_resource_source_result_sha256": (
                matched_resource["source_result_sha256"]
                if matched_resource is not None
                else None
            ),
        }
        measured = measured_capability_row(
            study_id="embedding_clustering_coverage",
            cell_id=cell_id,
            axes=axes,
            source_bindings=bindings,
        )
        if axis == "redim_execution_strategy" and matched_resource is None:
            measured["promotion_eligible"] = False
            measured["promotion_block_reason"] = (
                "accuracy evidence is not matched-resource evidence"
            )
            unsigned = dict(measured)
            unsigned.pop("outcome_sha256", None)
            measured["outcome_sha256"] = canonical_sha256(unsigned)
        output.append(measured)
    return tuple(output)


def _embedding_clustering_declarations(
    paths: ProgramPaths, jobs: Sequence[H2Job]
) -> tuple[dict[str, object], ...]:
    specification = read_yaml(paths.config_path)
    search = specification.get("development_search")
    baseline = specification.get("historical_baseline")
    if not isinstance(search, Mapping) or not isinstance(baseline, Mapping):
        raise H2ProgramError("H2 configuration lacks development search/baseline")
    embedding = search.get("embedding_frontier")
    redim = search.get("redim_execution")
    baseline_clustering = baseline.get("clustering")
    if (
        not isinstance(embedding, Mapping)
        or not isinstance(redim, Sequence)
        or isinstance(redim, (str, bytes))
        or not isinstance(baseline_clustering, Mapping)
    ):
        raise H2ProgramError("H2 embedding/clustering declarations are invalid")

    specs: tuple[tuple[str, str, str | None, str | None], ...] = (
        ("embedding_window_sec", "window_sec", "embedding_window_sec", None),
        ("embedding_hop_sec", "hop_sec", "embedding_hop_sec", None),
        (
            "minimum_voiced_proportion",
            "minimum_voiced_proportion",
            None,
            "runtime does not expose a voiced-proportion evidence gate",
        ),
        (
            "minimum_non_overlap_sec",
            "minimum_non_overlap_sec",
            None,
            "runtime does not expose a minimum non-overlap evidence-duration gate",
        ),
        ("identity_accumulation", "accumulation", "identity_accumulation", None),
        (
            "embedding_aggregation",
            "aggregation",
            None,
            "runtime does not expose the declared embedding aggregation methods",
        ),
        (
            "outlier_rejection",
            "outlier_rejection",
            None,
            "runtime does not expose the declared embedding outlier-rejection policy",
        ),
    )
    declarations: list[dict[str, object]] = []
    for axis, config_key, runtime_field, reason in specs:
        values = embedding.get(config_key)
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise H2ProgramError(
                f"embedding frontier lacks declared axis: {config_key}"
            )
        for value in values:
            declarations.append(
                {
                    "axis": axis,
                    "value": value,
                    "runtime_field": runtime_field,
                    "unsupported_reason": reason,
                }
            )
    for value in redim:
        declarations.append(
            {
                "axis": "redim_execution_strategy",
                "value": value,
                "runtime_field": "redim_execution_strategy",
                "unsupported_reason": None,
            }
        )

    clustering_values = _declared_runtime_axis_values(
        jobs,
        runtime_field="clustering_threshold",
        baseline_value=baseline_clustering.get("cosine_threshold"),
    )
    attach_values = _declared_runtime_axis_values(
        jobs,
        runtime_field="short_turn_attach_gap_sec",
        baseline_value=baseline_clustering.get("short_turn_attach_gap_sec"),
    )
    for axis, values in (
        ("clustering_threshold", clustering_values),
        ("short_turn_attach_gap_sec", attach_values),
    ):
        for value in values:
            declarations.append(
                {
                    "axis": axis,
                    "value": value,
                    "runtime_field": axis,
                    "unsupported_reason": None,
                }
            )
    return tuple(declarations)


def _declared_runtime_axis_values(
    jobs: Sequence[H2Job], *, runtime_field: str, baseline_value: object
) -> tuple[object, ...]:
    if baseline_value is None:
        raise H2ProgramError(f"baseline lacks declared axis: {runtime_field}")
    values = [baseline_value]
    values.extend(
        job.runtime_tuning[runtime_field]
        for job in jobs
        if job.phase_index == 2
        and job.split == "development"
        and runtime_field in job.runtime_tuning
    )
    unique: dict[str, object] = {}
    for value in values:
        unique.setdefault(canonical_sha256({"value": value}), value)
    return tuple(sorted(unique.values(), key=_coverage_value_sort_key))


def _completed_axis_runtime_binding(
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    runtime_field: str,
    value: object,
) -> dict[str, object] | None:
    candidates = [
        job
        for job in jobs
        if job.phase_index == 2
        and job.split == "development"
        and job.job_kind in {"successive_halving_runtime", "runtime_accuracy"}
        and runtime_field in job.runtime_tuning
        and _coverage_values_equal(job.runtime_tuning[runtime_field], value)
        and _state_job_if_present(state, job.job_id).get("state") == "COMPLETE"
    ]
    if not candidates:
        return None
    job = sorted(candidates, key=_coverage_runtime_job_sort_key)[0]
    root, identity = _completed_result_root(state, job)
    _require_valid_result_tree(root)
    return {
        "source_kind": "development_runtime_accuracy",
        "source_job_id": job.job_id,
        "source_result_sha256": identity,
        "source_result_root": str(root),
        "configuration_id": job.configuration_id,
        "development_case_count": len(job.case_ids),
        "serial_execution": bool(job.serial),
        "matched_resource_evidence": False,
    }


def _completed_resource_binding(
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    strategy: str,
) -> dict[str, object] | None:
    candidates = [
        job
        for job in jobs
        if job.phase_index == 2
        and job.split == "development"
        and job.job_kind == "resource_runtime"
        and job.runtime_tuning.get("redim_execution_strategy") == strategy
        and _state_job_if_present(state, job.job_id).get("state") == "COMPLETE"
    ]
    if not candidates:
        return None
    job = sorted(candidates, key=lambda candidate: candidate.job_id)[0]
    root, identity = _completed_result_root(state, job)
    _require_valid_result_tree(root)
    return {
        "source_kind": "matched_serial_resource_runtime",
        "source_job_id": job.job_id,
        "source_result_sha256": identity,
        "source_result_root": str(root),
        "configuration_id": job.configuration_id,
        "development_case_count": len(job.case_ids),
        "serial_execution": bool(job.serial),
        "matched_resource_evidence": True,
    }


def _reuse_parity_coverage_binding(
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    strategy: str,
) -> dict[str, object]:
    candidates = [
        job
        for job in jobs
        if job.job_kind == "embedding_reuse_parity" and job.configuration_id == strategy
    ]
    if len(candidates) != 1:
        return {
            "measured": False,
            "reason": "exactly one declared paired-parity job is required",
        }
    job = candidates[0]
    state_row = _state_job_if_present(state, job.job_id)
    if state_row.get("state") != "COMPLETE":
        return {
            "measured": False,
            "reason": "declared paired-parity job is not complete",
        }
    result_path = Path(str(state_row.get("result_path") or ""))
    result_sha = str(state_row.get("result_sha256") or "")
    if not result_path.is_file() or not result_sha:
        raise H2ProgramError(f"paired-parity result is missing: {job.job_id}")
    if sha256_file(result_path) != result_sha:
        raise H2ProgramError(f"paired-parity result checksum differs: {job.job_id}")
    result = read_json(result_path)
    scientific_outcome = result.get("scientific_outcome")
    outcome_reason = (
        scientific_outcome.get("reason")
        if isinstance(scientific_outcome, Mapping)
        else None
    )
    binding = {
        "source_kind": "paired_runtime_parity",
        "source_job_id": job.job_id,
        "source_result_sha256": result_sha,
        "source_result_path": str(result_path),
        "strategy": strategy,
    }
    terminal_status = str(result.get("status") or "") in {
        "COMPLETE",
        "GATED_NOT_PROMOTED",
    }
    measured = (
        terminal_status
        and result.get("bounded_exact_parity_executed") is True
        and result.get("required_parity_outputs_measured") is True
        and result.get("evaluation_material_inspected") is False
    )
    qualified = (
        measured
        and result.get("parity_passed") is True
        and result.get("candidate_qualified") is True
    )
    return {
        "measured": measured,
        "qualified": qualified,
        "reason": (
            "paired runtime parity completed and candidate qualified"
            if qualified
            else "paired runtime parity completed; candidate not promoted"
            if measured
            else str(
                result.get("reason")
                or outcome_reason
                or "paired-parity contract did not qualify the candidate"
            )
        ),
        "binding": binding,
    }


def _state_job_if_present(
    state: Mapping[str, object], job_id: str
) -> Mapping[str, object]:
    rows = state.get("jobs")
    if not isinstance(rows, Mapping):
        return {}
    row = rows.get(job_id)
    return row if isinstance(row, Mapping) else {}


def _coverage_values_equal(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)
    return left == right


def _coverage_runtime_job_sort_key(job: H2Job) -> tuple[int, str]:
    tier = 0 if job.configuration_id.endswith("_FULL") else 1
    tier = 2 if job.configuration_id.endswith("_MEDIUM") else tier
    tier = 3 if job.configuration_id.endswith("_SMALL") else tier
    return tier, job.job_id


def _coverage_value_sort_key(value: object) -> tuple[int, object]:
    if isinstance(value, bool):
        return 2, str(value)
    if isinstance(value, (int, float)):
        return 0, float(value)
    return 1, str(value)


def _coverage_cell_token(value: object) -> str:
    if isinstance(value, bool):
        return str(value).casefold()
    if isinstance(value, float):
        return format(value, "g")
    return str(value)


def _execute_embedding_reuse_parity(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    from .reuse import execute_embedding_reuse_parity

    return execute_embedding_reuse_parity(paths, job, state, jobs)


def _execute_integrated_enrollment(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    historical, historical_rows = _historical_enrollment_evidence(paths)
    configuration_rows, configuration_binding = (
        _historical_enrollment_configuration_rows(historical)
    )
    # This job owns a sealed, speaker/session-disjoint train-clean-100 panel.
    # It deliberately does not depend on the general H2 integration output or
    # inspect held-out outcomes.  Real ReDim extraction occurs only in the
    # already-qualified isolated environment and is restart-safe.
    from .integrated_enrollment import execute_integrated_enrollment

    return execute_integrated_enrollment(
        paths,
        job,
        historical_summary=historical,
        historical_evidence_rows=historical_rows,
        historical_configuration_rows=configuration_rows,
        historical_source_bindings=(configuration_binding,),
    )


def _execute_memory_policy_replay(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    source_job, source_root, source_identity = _integration_source(paths, state, jobs)
    observations, assignment = _integration_observations(paths, source_root)
    policy_result = _completed_science_result(state, jobs, "policy_replay")
    selected_policy = policy_result.get("selected_policy")
    if not isinstance(selected_policy, Mapping):
        raise H2ProgramError("policy replay result lacks selected policy")
    if policy_result.get("integration_assignment_sha256") != assignment.get(
        "assignment_sha256"
    ):
        raise H2ProgramError("memory replay assignment differs from policy replay")
    gallery = str(selected_policy["gallery_requested_size"])
    policy_tuning = {
        "score_threshold": float(selected_policy["score_threshold"]),
        "margin_threshold": float(selected_policy["margin_threshold"]),
        "minimum_evidence_sec": float(selected_policy["minimum_evidence_sec"]),
        "minimum_embedding_consistency": float(
            selected_policy["minimum_embedding_consistency"]
        ),
    }
    source_rows = _replay_rows(observations, gallery=gallery)
    frontier: list[dict[str, object]] = []
    source_binding = {
        "source_job_id": source_job.job_id,
        "source_result_sha256": source_identity,
        "integration_assignment_sha256": assignment["assignment_sha256"],
    }
    # Preserve the legacy scalar grid as a diagnostic, but never use it to
    # stand in for the five named algorithms below.
    for confirmations in (1, 2, 3):
        for hysteresis in (0.0, 0.01, 0.02, 0.03, 0.05):
            for expiry in (15.0, 30.0, 60.0, 120.0):
                tuning = {
                    **policy_tuning,
                    "consecutive_passes_to_confirm": confirmations,
                    "hysteresis": hysteresis,
                    "identity_expiry_sec": expiry,
                }
                decisions = _replay_identity_sequences(source_rows, tuning)
                calibration = _sequence_decision_metrics(decisions, role="calibration")
                selection = _sequence_decision_metrics(decisions, role="selection")
                metrics = {
                    **{
                        f"calibration_{key}": value
                        for key, value in calibration.items()
                    },
                    **{f"selection_{key}": value for key, value in selection.items()},
                }
                diagnostic = measured_capability_row(
                    study_id="h2_legacy_scalar_hysteresis_diagnostic",
                    cell_id=(f"C{confirmations}__H{hysteresis:g}__E{expiry:g}"),
                    axes={
                        "cell_type": "legacy_scalar_diagnostic",
                        "hysteresis_policy": "CUSTOM_SCALAR_DIAGNOSTIC",
                        "consecutive_passes_to_confirm": confirmations,
                        "consecutive_failures_to_release": 2,
                        "hysteresis": hysteresis,
                        "identity_expiry_sec": expiry,
                        "development_only_selection": True,
                        "evaluation_material_inspected": False,
                    },
                    source_bindings=(source_binding,),
                    metrics=metrics,
                )
                diagnostic.update(metrics)
                diagnostic["promotion_eligible"] = False
                diagnostic["promotion_block_reason"] = (
                    "custom scalar diagnostic is not a declared named policy"
                )
                unsigned = dict(diagnostic)
                unsigned.pop("outcome_sha256", None)
                diagnostic["outcome_sha256"] = canonical_sha256(unsigned)
                frontier.append(diagnostic)
    named_rows: list[dict[str, object]] = []
    for policy_id in NAMED_HYSTERESIS_POLICIES:
        for expiry_cell in EXPIRY_CELLS:
            tuning = _named_hysteresis_tuning(
                policy_tuning,
                policy_id=policy_id,
                expiry_cell=expiry_cell,
            )
            decisions = _replay_identity_sequences(source_rows, tuning)
            calibration = _sequence_decision_metrics(decisions, role="calibration")
            selection = _sequence_decision_metrics(decisions, role="selection")
            row = measured_capability_row(
                study_id="h2_named_hysteresis",
                cell_id=f"{policy_id}__{str(expiry_cell).upper()}",
                axes={
                    "cell_type": "named_hysteresis",
                    "hysteresis_policy": policy_id,
                    "identity_expiry_sec": expiry_cell,
                    "identity_expiry_mode": tuning["identity_expiry_mode"],
                    "consecutive_passes_to_confirm": tuning[
                        "consecutive_passes_to_confirm"
                    ],
                    "consecutive_failures_to_release": tuning[
                        "consecutive_failures_to_release"
                    ],
                    "hysteresis": tuning["hysteresis"],
                },
                source_bindings=(source_binding,),
                metrics={
                    **{
                        f"calibration_{key}": value
                        for key, value in calibration.items()
                    },
                    **{f"selection_{key}": value for key, value in selection.items()},
                },
            )
            # Keep metrics flat for the existing result/report consumers.
            row.update(
                {f"calibration_{key}": value for key, value in calibration.items()}
            )
            row.update({f"selection_{key}": value for key, value in selection.items()})
            named_rows.append(row)
    h0_latency = {
        row["identity_expiry_sec"]: row.get("selection_confirmed_name_latency_sec")
        for row in named_rows
        if row["hysteresis_policy"] == "H0_ONE_PASS_DIAGNOSTIC"
    }
    for row in named_rows:
        baseline_latency = h0_latency.get(row["identity_expiry_sec"])
        latency = row.get("selection_confirmed_name_latency_sec")
        row["selection_added_latency_vs_h0_sec"] = (
            float(latency) - float(baseline_latency)
            if latency is not None and baseline_latency is not None
            else None
        )
        rebound = dict(row)
        rebound.pop("outcome_sha256", None)
        row["outcome_sha256"] = canonical_sha256(rebound)
    frontier.extend(named_rows)

    if not named_rows:
        raise H2ProgramError("named hysteresis replay frontier is empty")
    selected = min(
        [
            row
            for row in named_rows
            if row["hysteresis_policy"] != "H0_ONE_PASS_DIAGNOSTIC"
        ],
        key=_hysteresis_selection_key,
    )
    selected_expiry = selected["identity_expiry_sec"]
    axes = (
        "hysteresis_policy",
        "consecutive_passes_to_confirm",
        "consecutive_failures_to_release",
        "hysteresis",
        "identity_expiry_sec",
        "identity_expiry_mode",
    )
    selected_tuning = {axis: selected[axis] for axis in axes}
    if isinstance(selected_expiry, str):
        selected_tuning["identity_expiry_sec"] = 120.0
        selected_tuning["identity_expiry_mode"] = "end_session"
    exact_evidence, exact_unsupported = _execute_exact_memory_cells(
        paths=paths,
        job=job,
        source_root=source_root,
        source_result_sha256=source_identity,
        observations=observations,
        assignment=assignment,
        policy_tuning={**policy_tuning, **selected_tuning},
    )
    memory_rows = list(
        build_memory_level_coverage(
            source_binding,
            evidence_by_cell=exact_evidence,
        )
    )
    frontier.extend(memory_rows)
    measured_memory = [
        row
        for row in memory_rows
        if row["status"] == "MEASURED" and row["memory_level"] in set(MEMORY_LEVELS)
    ]
    complete_exact_memory_grid = len(measured_memory) == 30
    selected_memory = (
        min(measured_memory, key=_memory_selection_key)
        if complete_exact_memory_grid
        else None
    )
    if selected_memory is not None:
        selected_tuning.update(
            {
                "memory_level": selected_memory["memory_level"],
                "identity_expiry_sec": selected_memory["identity_expiry_sec"],
                "identity_expiry_mode": selected_memory["identity_expiry_mode"],
            }
        )
        if selected_memory["memory_level"] in {
            "M4_ACTIVE_ROSTER_DECAY",
            "M5_CLUSTER_RECONCILIATION",
        }:
            selected_tuning.update(
                {
                    "confidence_decay_half_life_sec": 30.0,
                    "confidence_decay_release_floor": 0.25,
                }
            )
        if selected_memory["memory_level"] == "M5_CLUSTER_RECONCILIATION":
            selected_evidence = exact_evidence[str(selected_memory["cell_id"])]
            selected_metadata = dict(selected_evidence["execution_metadata"])
            selected_reconciliation = dict(selected_metadata["reconciliation_policy"])
            selected_tuning.update(
                {
                    "cluster_reconciliation_threshold": selected_reconciliation[
                        "threshold"
                    ],
                    "cluster_reconciliation_max_gap_sec": selected_reconciliation[
                        "maximum_gap_sec"
                    ],
                    "cluster_reconciliation_min_embeddings": selected_reconciliation[
                        "minimum_embeddings_per_cluster"
                    ],
                }
            )
        axes = (
            *axes[:-2],
            "memory_level",
            "identity_expiry_sec",
            "identity_expiry_mode",
        )
        if selected_memory["memory_level"] in {
            "M4_ACTIVE_ROSTER_DECAY",
            "M5_CLUSTER_RECONCILIATION",
        }:
            axes = (
                *axes,
                "confidence_decay_half_life_sec",
                "confidence_decay_release_floor",
            )
        if selected_memory["memory_level"] == "M5_CLUSTER_RECONCILIATION":
            axes = (
                *axes,
                "cluster_reconciliation_threshold",
                "cluster_reconciliation_max_gap_sec",
                "cluster_reconciliation_min_embeddings",
            )
    payload = {
        "schema_version": "h2-science-handler-result.v1",
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "promotion_eligible": selected_memory is not None,
        "source_runtime_job_id": source_job.job_id,
        "source_runtime_result_sha256": source_identity,
        "integration_assignment_sha256": assignment["assignment_sha256"],
        "source_policy_result_sha256": _completed_science_result_sha(
            state, jobs, "policy_replay"
        ),
        "gallery_requested_size": gallery,
        "selected_runtime_tuning": selected_tuning,
        "selected_runtime_axes": list(axes),
        "selected_frontier_row": selected,
        "selected_memory_frontier_row": selected_memory,
        "declared_named_hysteresis_cell_count": len(NAMED_HYSTERESIS_POLICIES)
        * len(EXPIRY_CELLS),
        "measured_named_hysteresis_cell_count": len(named_rows),
        "declared_memory_cell_count": len(MEMORY_LEVELS) * len(EXPIRY_CELLS),
        "declared_confidence_decay_cell_count": 1,
        "declared_session_memory_outcome_count": (
            len(MEMORY_LEVELS) * len(EXPIRY_CELLS) + 1
        ),
        "measured_memory_cell_count": len(measured_memory),
        "unsupported_memory_cell_count": sum(
            row["status"] == "UNSUPPORTED_CAPABILITY" for row in memory_rows
        ),
        "memory_level_selected": selected_memory is not None,
        "memory_level_selection_reason": (
            "complete checksum-bound M0-M5 development grid selected with "
            "lexicographic safety/latency criteria"
            if selected_memory is not None
            else "exact M0-M5 x expiry development grid is incomplete; no memory policy frozen"
        ),
        "all_declared_cells_accounted_for": (
            len(named_rows) == len(NAMED_HYSTERESIS_POLICIES) * len(EXPIRY_CELLS)
            and len(memory_rows) == len(MEMORY_LEVELS) * len(EXPIRY_CELLS) + 1
        ),
        "selection_method": "declared_lexicographic_safety_yield_latency_revisions",
        "safety_priority_contract_id": SAFETY_PRIORITY_CONTRACT_ID,
        "ordered_safety_risk_families": list(SAFETY_PRIORITY_ORDERED_RISK_FAMILIES),
        "hysteresis_ordered_priorities": [
            "minimize_wrong_known_dwell_rate",
            "minimize_wrong_known_rate",
            "minimize_premature_wrong_name_events",
            "minimize_harmful_known_to_known_switches",
            "minimize_unknown_speaker_fpir",
            "minimize_stranger_false_known_dwell_rate",
            "minimize_identity_oscillation_and_revision",
            "minimize_never_identified_rate",
            "maximize_correct_known_rate",
            "minimize_first_correct_latency",
        ],
        "memory_ordered_priorities": [
            "minimize_wrong_known_turn_rate",
            "minimize_false_inheritance_rate",
            "minimize_stale_inheritance_rate",
            "minimize_stranger_false_known_turn_rate",
            "minimize_new_speaker_lockout_rate",
            "maximize_correct_known_turn_rate",
            "minimize_returning_turn_name_latency",
            "maximize_reentry_consistency_rate",
        ],
        "weighted_composite_used": False,
        "transition_algorithm_used_truth": False,
        "truth_used_only_after_replay_for_scoring": True,
        "truth_used_only_after_runtime_decisions_for_memory_scoring": True,
        "checkpoint_independence_assumed": False,
        "runtime_transition_implementation": (
            "app.full_pipeline.identity.SessionIdentityManager"
        ),
        "memory_execution_kind": "EXACT_SHARED_RUNTIME_PRIMITIVE",
        "memory_runtime_evidence_schema": "h2-causal-memory-runtime-evidence.v1",
        "memory_unsupported_runtime_cells": exact_unsupported,
        "memory_metric_scope": "END_TO_END_ON_EXACT_RUNTIME_TURNS",
        "memory_conditional_scope": "OBSERVED_SEGMENTATION_AND_CLUSTER_ASSIGNMENTS",
        "development_only_selection": True,
        "evaluation_material_inspected": False,
        "neural_inference_performed": False,
    }
    return payload, {"memory_policy_frontier.csv": frontier}


def _hysteresis_selection_key(row: Mapping[str, object]) -> tuple[object, ...]:
    """Order named hysteresis cells by the frozen safety contract."""

    return (
        _metric_or_inf(row, "selection_wrong_known_dwell_rate"),
        _metric_or_inf(row, "selection_wrong_known_rate"),
        _metric_or_inf(row, "selection_premature_wrong_name_event_count"),
        _metric_or_inf(row, "selection_harmful_known_to_known_switch_count"),
        _metric_or_inf(row, "selection_unknown_speaker_fpir"),
        _metric_or_inf(row, "selection_stranger_false_known_dwell_rate"),
        _metric_or_inf(row, "selection_identity_oscillation_count"),
        _metric_or_inf(row, "selection_identity_revision_rate"),
        _metric_or_inf(row, "selection_never_identified_rate"),
        -_metric_or_neg_inf(row, "selection_correct_known_rate"),
        _metric_or_inf(row, "selection_first_correct_latency_sec"),
        _expiry_sort_key(row["identity_expiry_sec"]),
        NAMED_HYSTERESIS_POLICIES.index(str(row["hysteresis_policy"])),
    )


def _memory_selection_key(row: Mapping[str, object]) -> tuple[object, ...]:
    """Order exact memory cells without allowing stranger risk to mask wrong names."""

    return (
        _metric_or_inf(row, "selection_wrong_known_turn_rate"),
        _metric_or_inf(row, "selection_false_inheritance_rate"),
        _metric_or_inf(row, "selection_stale_inheritance_rate"),
        _metric_or_inf(row, "selection_stranger_false_known_turn_rate"),
        _metric_or_inf(row, "selection_new_speaker_lockout_rate"),
        -_metric_or_neg_inf(row, "selection_correct_known_turn_rate"),
        _metric_or_inf(row, "selection_returning_turn_name_latency_sec_mean"),
        -_metric_or_neg_inf(row, "selection_reentry_consistency_rate"),
        _expiry_sort_key(row["identity_expiry_sec"]),
        MEMORY_LEVELS.index(str(row["memory_level"])),
    )


def _execute_exact_memory_cells(
    *,
    paths: ProgramPaths,
    job: H2Job,
    source_root: Path,
    source_result_sha256: str,
    observations: Sequence[Mapping[str, object]],
    assignment: Mapping[str, object],
    policy_tuning: Mapping[str, object],
    cell_specs: Sequence[CausalCellSpec] | None = None,
    artifact_family: str = "causal_memory_runtime_evidence",
) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    """Execute the complete supported M0-M5 x expiry grid restart-safely."""

    event_path = next(
        (
            path
            for path in (
                source_root / "events/events.jsonl.gz",
                source_root / "events/events.jsonl",
            )
            if path.is_file()
        ),
        None,
    )
    cache_regime_path = source_root / "diagnostics/cache_regime.json"
    if event_path is None or not cache_regime_path.is_file():
        return {}, {"SOURCE": "runtime event stream or cache regime is absent"}
    cache_regime = read_json(cache_regime_path)
    if (
        cache_regime.get("measurement_mode") != "accuracy"
        or cache_regime.get("runtime_cache_scope") != "shared_cross_job_accuracy"
    ):
        return {}, {
            "SOURCE": "source runtime is not shared-cache development accuracy evidence"
        }
    assigned_cases = {
        str(row["case_id"]) for row in observations if str(row.get("status")) == "VALID"
    }
    runtime_events = tuple(
        row
        for row in read_ordered_runtime_events(event_path)
        if str(row.get("evaluation_case_id") or row.get("case_id") or "")
        in assigned_cases
        and str(row.get("event_type"))
        in {"anonymous_speaker", "identity_evidence", "identity_label"}
    )
    if not runtime_events:
        return {}, {"SOURCE": "source runtime has no causal speaker events"}
    observations_by_case: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    case_role_by_id: dict[str, str] = {}
    speakers_by_role: dict[str, set[str]] = {
        "calibration": set(),
        "selection": set(),
    }
    for row in observations:
        if str(row.get("status")) != "VALID":
            continue
        case_id = str(row["case_id"])
        role = str(row.get("effective_calibration_role") or "")
        speaker = str(row.get("reference_global_speaker_id") or "")
        if role not in speakers_by_role or not speaker:
            raise H2ProgramError("exact memory source lacks development speaker role")
        prior_role = case_role_by_id.setdefault(case_id, role)
        if prior_role != role:
            raise H2ProgramError("exact memory case crosses development roles")
        speakers_by_role[role].add(speaker)
        observations_by_case[case_id].append(row)
    if (
        not speakers_by_role["calibration"]
        or not speakers_by_role["selection"]
        or speakers_by_role["calibration"] & speakers_by_role["selection"]
    ):
        return {}, {
            "SOURCE": "source partition is not speaker-disjoint calibration/selection"
        }
    case_sha256_by_id = {
        case_id: canonical_sha256(
            sorted(
                (dict(row) for row in rows),
                key=lambda value: (
                    str(value.get("anonymous_speaker_id")),
                    float(value.get("source_time_sec") or 0.0),
                    str(value.get("observation_id") or ""),
                ),
            )
        )
        for case_id, rows in sorted(observations_by_case.items())
    }
    assignment_sha = str(assignment.get("assignment_sha256") or "")
    implementation_sha = canonical_sha256(
        {
            "causal_memory.py": sha256_file(
                Path(__file__).with_name("causal_memory.py")
            ),
            "identity.py": sha256_file(
                paths.evaluation_root / "app/full_pipeline/identity.py"
            ),
            "executor": "SessionIdentityManager",
        }
    )
    event_payload_sha = canonical_sha256(runtime_events)
    reference_manifest_sha = canonical_sha256(observations)
    evidence: dict[str, dict[str, object]] = {}
    root = paths.results_root / "jobs" / job.job_id / "artifacts" / artifact_family
    unsupported: dict[str, str] = {}
    try:
        reconciliation_policy = calibrate_reconciliation_policy(
            runtime_events=runtime_events,
            observations=observations,
        )
        reconciliation_error = None
    except UnsupportedCausalCapability as exc:
        reconciliation_policy = None
        reconciliation_error = str(exc)
    for cell in cell_specs or declared_memory_cells():
        if not cell.executable:
            continue
        cell_tuning = {
            **dict(policy_tuning),
            "memory_level": cell.memory_level,
            "identity_expiry_sec": cell.to_jsonable()["identity_expiry_sec"],
            "identity_expiry_mode": cell.to_jsonable()["identity_expiry_mode"],
        }
        policy = _identity_policy_from_tuning(cell_tuning)
        runtime_config_sha = canonical_sha256(
            {
                "schema_version": "h2-causal-runtime-cell-config.v2",
                "cell": cell.to_jsonable(),
                "identity_policy": policy.__dict__,
                "confidence_decay": (
                    {
                        "half_life_sec": 30.0,
                        "release_floor": 0.25,
                        "source_clock_only": True,
                    }
                    if cell.memory_level
                    in {
                        "M4_ACTIVE_ROSTER_DECAY",
                        "M5_CLUSTER_RECONCILIATION",
                    }
                    else None
                ),
                "reconciliation_policy": (
                    reconciliation_policy
                    if cell.memory_level == "M5_CLUSTER_RECONCILIATION"
                    else None
                ),
                "source_result_sha256": source_result_sha256,
                "assignment_sha256": assignment_sha,
                "runtime_implementation_sha256": implementation_sha,
            }
        )
        if (
            cell.memory_level == "M5_CLUSTER_RECONCILIATION"
            and reconciliation_policy is None
        ):
            unsupported[cell.cell_id] = str(reconciliation_error)
            continue
        try:
            outcomes = execute_causal_primitive_cell(
                cell=cell,
                policy=policy,
                runtime_config_sha256=runtime_config_sha,
                runtime_events=runtime_events,
                observations=observations,
                case_sha256_by_id=case_sha256_by_id,
                reconciliation_policy=(
                    reconciliation_policy
                    if cell.memory_level == "M5_CLUSTER_RECONCILIATION"
                    else None
                ),
            )
        except UnsupportedCausalCapability as exc:
            unsupported[cell.cell_id] = str(exc)
            continue
        binding_core = {
            "schema_version": CAUSAL_MEMORY_BINDING_SCHEMA_VERSION,
            "split": "development",
            "evaluation_material_inspected": False,
            "assignment_sha256": assignment_sha,
            "source_result_sha256": source_result_sha256,
            "runtime_config_sha256": runtime_config_sha,
            "runtime_implementation_sha256": implementation_sha,
            "runtime_event_log_sha256": event_payload_sha,
            "neural_cache_manifest_sha256": sha256_file(cache_regime_path),
            "reference_manifest_sha256": reference_manifest_sha,
            "case_sha256_by_id": case_sha256_by_id,
            "case_role_by_id": dict(sorted(case_role_by_id.items())),
            "speaker_ids_by_role": {
                role: sorted(values) for role, values in speakers_by_role.items()
            },
            "active_roster_narrowed_gallery": False,
            "full_gallery_safety_enforced": True,
            "shared_neural_cache_reuse": True,
        }
        source_binding = {
            **binding_core,
            "binding_sha256": canonical_sha256(binding_core),
        }
        artifact = write_exact_runtime_cell(
            root / cell.cell_id / runtime_config_sha / "evidence.json",
            cell=cell,
            source_binding=source_binding,
            runtime_events=runtime_events,
            outcomes=outcomes,
            execution_metadata={
                "completion_state": "complete",
                "runtime_tuning_sha256": runtime_config_sha,
                "memory_level": cell.memory_level,
                "identity_expiry_sec": cell.to_jsonable()["identity_expiry_sec"],
                "identity_expiry_mode": cell.to_jsonable()["identity_expiry_mode"],
                "short_turn_policy": None,
                "hysteresis_policy": policy.hysteresis_policy,
                "source_event_kind": "completed_development_runtime",
                "neural_execution": "REUSED_CHECKSUM_BOUND_SHARED_CACHE_OUTPUTS",
                "confidence_decay": (
                    {
                        "half_life_sec": 30.0,
                        "release_floor": 0.25,
                        "source_clock_only": True,
                    }
                    if cell.memory_level
                    in {
                        "M4_ACTIVE_ROSTER_DECAY",
                        "M5_CLUSTER_RECONCILIATION",
                    }
                    else None
                ),
                "reconciliation_policy": (
                    reconciliation_policy
                    if cell.memory_level == "M5_CLUSTER_RECONCILIATION"
                    else None
                ),
            },
        )
        artifact.pop("write_disposition", None)
        evidence[cell.cell_id] = artifact
    return evidence, unsupported


def build_memory_level_coverage(
    source_binding: Mapping[str, object],
    *,
    evidence_by_cell: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[dict[str, object], ...]:
    """Return explicit outcomes for the complete M0-M5 by expiry contract."""

    if evidence_by_cell is not None:
        rows: list[dict[str, object]] = []
        for exact in exact_evidence_coverage(evidence_by_cell):
            axes = {
                "cell_type": "memory_level",
                "memory_level": exact["memory_level"],
                "identity_expiry_sec": exact["identity_expiry_sec"],
                "identity_expiry_mode": exact["identity_expiry_mode"],
                "confidence_decay_behavior": (
                    "MEASURED_CAUSAL_SOURCE_CLOCK"
                    if exact["memory_level"]
                    in {
                        "M4_ACTIVE_ROSTER_DECAY",
                        "M5_CLUSTER_RECONCILIATION",
                    }
                    else "NOT_ENABLED_FOR_CELL"
                ),
            }
            if exact["cell_id"] == "CONFIDENCE_BASED_DECAY":
                axes.update(
                    {
                        "cell_type": "confidence_based_decay",
                        "confidence_decay_behavior": "MEASURED_CAUSAL_SOURCE_CLOCK",
                    }
                )
            if exact["status"] != "MEASURED":
                rows.append(
                    unsupported_capability_row(
                        study_id="h2_session_memory_levels",
                        cell_id=str(exact["cell_id"]),
                        reason=str(exact["reason"]),
                        axes=axes,
                        source_bindings=(source_binding,),
                    )
                )
                continue
            evidence = evidence_by_cell[
                str(exact.get("evidence_cell_id") or exact["cell_id"])
            ]
            role_metrics = evidence.get("metrics_by_development_role")
            role_mapping = role_metrics if isinstance(role_metrics, Mapping) else {}
            metrics: dict[str, object] = {}
            for role in ("calibration", "selection"):
                values = role_mapping.get(role)
                if isinstance(values, Mapping):
                    metrics.update(
                        {f"{role}_{key}": value for key, value in values.items()}
                    )
            row = measured_capability_row(
                study_id="h2_session_memory_levels",
                cell_id=str(exact["cell_id"]),
                axes=axes,
                source_bindings=(
                    source_binding,
                    {
                        "evidence_sha256": evidence["evidence_sha256"],
                        "runtime_config_sha256": dict(evidence["source_binding"])[
                            "runtime_config_sha256"
                        ],
                    },
                ),
                metrics=metrics,
            )
            row.update(metrics)
            rows.append(row)
        return tuple(rows)

    rows: list[dict[str, object]] = []
    for memory_level in MEMORY_LEVELS:
        for expiry_cell in EXPIRY_CELLS:
            reason = (
                "no checksum-valid exact development execution was supplied for "
                "this memory/expiry cell"
            )
            rows.append(
                unsupported_capability_row(
                    study_id="h2_session_memory_levels",
                    cell_id=f"{memory_level}__{str(expiry_cell).upper()}",
                    reason=reason,
                    axes={
                        "cell_type": "memory_level",
                        "memory_level": memory_level,
                        "identity_expiry_sec": expiry_cell,
                        "identity_expiry_mode": (
                            "end_session"
                            if isinstance(expiry_cell, str)
                            else "source_clock"
                        ),
                        "confidence_decay_behavior": ("DECLARED_BUT_UNMEASURED"),
                    },
                    source_bindings=(source_binding,),
                )
            )
    rows.append(
        unsupported_capability_row(
            study_id="h2_session_memory_levels",
            cell_id="CONFIDENCE_BASED_DECAY",
            reason=(
                "no checksum-valid M4 end-session confidence-decay execution was supplied"
            ),
            axes={
                "cell_type": "confidence_based_decay",
                "memory_level": "NOT_APPLICABLE",
                "identity_expiry_sec": None,
                "identity_expiry_mode": "confidence_based",
                "confidence_decay_behavior": "UNSUPPORTED_CAPABILITY",
            },
            source_bindings=(source_binding,),
        )
    )
    return tuple(rows)


def _named_hysteresis_tuning(
    policy_tuning: Mapping[str, object],
    *,
    policy_id: str,
    expiry_cell: float | str,
) -> dict[str, object]:
    if policy_id not in NAMED_HYSTERESIS_POLICIES:
        raise ValueError(f"unsupported named hysteresis policy: {policy_id}")
    values = {
        "H0_ONE_PASS_DIAGNOSTIC": (1, 1, 0.0),
        "H1_TWO_CONFIRM_TWO_RELEASE": (2, 2, 0.02),
        "H2A_ADAPTIVE_EARLY": (2, 2, 0.02),
        "H3_THREE_CONFIRM_SAFE": (3, 2, 0.02),
        "H4_DURATION_DEPENDENT": (2, 2, 0.02),
    }
    confirmations, releases, hysteresis = values[policy_id]
    end_session = isinstance(expiry_cell, str)
    return {
        **dict(policy_tuning),
        "hysteresis_policy": policy_id,
        "consecutive_passes_to_confirm": confirmations,
        "consecutive_failures_to_release": releases,
        "hysteresis": hysteresis,
        "identity_expiry_sec": 120.0 if end_session else float(expiry_cell),
        "identity_expiry_mode": "end_session" if end_session else "source_clock",
        "adaptive_early_max_evidence_sec": 1.5,
        "adaptive_standard_evidence_sec": 3.0,
        "adaptive_early_score_delta": 0.05,
        "adaptive_early_margin_delta": 0.02,
        "adaptive_medium_score_delta": 0.02,
        "adaptive_medium_margin_delta": 0.01,
    }


def _expiry_sort_key(value: object) -> tuple[int, float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    return (1, math.inf)


def _execute_short_turn_replay(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    """Execute A-E through the live identity primitive on real runtime events."""

    source_job, source_root, source_identity = _integration_source(paths, state, jobs)
    observations, assignment = _integration_observations(paths, source_root)
    policy_result = _completed_science_result(state, jobs, "policy_replay")
    memory_result = _completed_science_result(state, jobs, "memory_policy_replay")
    if policy_result.get("integration_assignment_sha256") != assignment.get(
        "assignment_sha256"
    ) or memory_result.get("integration_assignment_sha256") != assignment.get(
        "assignment_sha256"
    ):
        raise H2ProgramError("short-turn replay assignment differs")
    selected_policy = policy_result.get("selected_policy")
    if not isinstance(selected_policy, Mapping):
        raise H2ProgramError("short-turn replay lacks selected open-set policy")
    memory_tuning = memory_result.get("selected_runtime_tuning")
    if not isinstance(memory_tuning, Mapping):
        raise H2ProgramError("short-turn runtime execution lacks memory policy")
    policy_tuning = {
        "score_threshold": float(selected_policy["score_threshold"]),
        "margin_threshold": float(selected_policy["margin_threshold"]),
        "minimum_evidence_sec": float(selected_policy["minimum_evidence_sec"]),
        "minimum_embedding_consistency": float(
            selected_policy["minimum_embedding_consistency"]
        ),
        "consecutive_passes_to_confirm": int(
            memory_tuning["consecutive_passes_to_confirm"]
        ),
        "hysteresis": float(memory_tuning["hysteresis"]),
        "identity_expiry_sec": float(memory_tuning["identity_expiry_sec"]),
        "identity_expiry_mode": str(
            memory_tuning.get("identity_expiry_mode") or "source_clock"
        ),
        "hysteresis_policy": str(
            memory_tuning.get("hysteresis_policy") or "H1_TWO_CONFIRM_TWO_RELEASE"
        ),
        "consecutive_failures_to_release": int(
            memory_tuning.get("consecutive_failures_to_release") or 2
        ),
    }
    expiry: float | str = (
        "END_SESSION"
        if str(memory_tuning.get("identity_expiry_mode")) == "end_session"
        else float(memory_tuning["identity_expiry_sec"])
    )
    cell_specs = declared_short_turn_cells(memory_level="M3_SHORT_TURN", expiry=expiry)
    evidence, unsupported = _execute_exact_memory_cells(
        paths=paths,
        job=job,
        source_root=source_root,
        source_result_sha256=source_identity,
        observations=observations,
        assignment=assignment,
        policy_tuning=policy_tuning,
        cell_specs=cell_specs,
        artifact_family="causal_short_turn_runtime_evidence",
    )
    frontier = list(
        exact_short_turn_coverage(
            evidence,
            memory_level="M3_SHORT_TURN",
            expiry=expiry,
            role="selection",
            unsupported_reasons=unsupported,
        )
    )
    complete_policies = []
    for cell in cell_specs:
        rows = [
            row
            for row in frontier
            if row["short_turn_policy"] == cell.short_turn_policy
            and row["status"] == "MEASURED"
        ]
        if len(rows) != len(SHORT_TURN_DURATION_BINS):
            continue
        document = evidence[cell.cell_id]
        selection_outcomes = [
            row
            for row in document.get("outcomes", ())
            if isinstance(row, Mapping)
            and row.get("effective_calibration_role") == "selection"
            and row.get("short_turn") is True
        ]
        if selection_outcomes:
            complete_policies.append(
                {
                    "cell": cell,
                    "metrics": score_runtime_outcomes(selection_outcomes),
                    "evidence_sha256": document["evidence_sha256"],
                }
            )
    selected = (
        min(complete_policies, key=_short_turn_selection_key)
        if complete_policies
        else None
    )
    selected_policy_id = (
        str(selected["cell"].short_turn_policy) if selected is not None else None
    )
    payload = {
        "schema_version": "h2-science-handler-result.v1",
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        # A-E are scientifically comparable through the exact primitive, but
        # the production coordinator currently exposes only policy C.  Keep
        # this study advisory rather than freezing a non-executable axis.
        "promotion_eligible": False,
        "source_runtime_job_id": source_job.job_id,
        "source_runtime_result_sha256": source_identity,
        "integration_assignment_sha256": assignment["assignment_sha256"],
        "selected_runtime_tuning": {},
        "selected_runtime_axes": [],
        "advisory_selected_short_turn_policy": selected_policy_id,
        "safety_priority_contract_id": SAFETY_PRIORITY_CONTRACT_ID,
        "ordered_safety_risk_families": list(SAFETY_PRIORITY_ORDERED_RISK_FAMILIES),
        "short_turn_ordered_priorities": [
            "minimize_wrong_known_turn_rate",
            "minimize_false_inheritance_rate",
            "minimize_stale_inheritance_rate",
            "minimize_stranger_false_known_turn_rate",
            "minimize_new_speaker_lockout_rate",
            "maximize_short_turn_correct_name_rate",
        ],
        "promotion_block_reason": (
            "production coordinator does not expose a checksum-bound A-E policy axis; "
            "current executable behavior corresponds to policy C only"
        ),
        "selected_frontier_row": (
            {
                "cell": selected["cell"].to_jsonable(),
                "metrics": selected["metrics"],
                "evidence_sha256": selected["evidence_sha256"],
            }
            if selected is not None
            else None
        ),
        "short_turn_attach_gap_sec_selected": False,
        "short_turn_attach_gap_reason": "causal trace contains materialized cluster IDs but not counterfactual diarization embeddings needed to vary attach-gap",
        "declared_policy_count": len(CAUSAL_SHORT_TURN_POLICIES),
        "declared_duration_bin_count": len(SHORT_TURN_DURATION_BINS),
        "all_declared_cells_accounted_for": all(
            row["status"] in {"MEASURED", "UNSUPPORTED_CAPABILITY"} for row in frontier
        ),
        "causal_runtime_evidence_available": bool(evidence),
        "causal_runtime_evidence_schema": "h2-causal-memory-runtime-evidence.v1",
        "unsupported_runtime_cells": unsupported,
        "transition_algorithm_used_truth": False,
        "truth_used_only_after_runtime_decisions_for_scoring": True,
        "synthetic_live_projection_used": False,
        "actual_runtime_event_source_used": bool(evidence),
        "runtime_executor": "app.full_pipeline.identity.SessionIdentityManager",
        "metric_scope": "END_TO_END_ON_EXACT_RUNTIME_TURNS",
        "conditional_scope": "OBSERVED_SEGMENTATION_AND_CLUSTER_ASSIGNMENTS",
        "weighted_composite_used": False,
        "development_only_selection": True,
        "evaluation_material_inspected": False,
        "neural_inference_performed": False,
        "shared_neural_cache_outputs_reused": bool(evidence),
    }
    return payload, {"short_turn_replay_frontier.csv": frontier}


def _short_turn_selection_key(row: Mapping[str, object]) -> tuple[object, ...]:
    """Order advisory short-turn policies using the same safety contract."""

    metrics = row["metrics"]
    if not isinstance(metrics, Mapping):
        raise H2ProgramError("short-turn selection row lacks metrics")
    cell = row["cell"]
    return (
        _metric_or_inf(metrics, "wrong_known_turn_rate"),
        _metric_or_inf(metrics, "false_inheritance_rate"),
        _metric_or_inf(metrics, "stale_inheritance_rate"),
        _metric_or_inf(metrics, "stranger_false_known_turn_rate"),
        _metric_or_inf(metrics, "new_speaker_lockout_rate"),
        -_metric_or_neg_inf(metrics, "short_turn_correct_name_rate"),
        CAUSAL_SHORT_TURN_POLICIES.index(str(cell.short_turn_policy)),
    )


def _replay_rows(
    observations: Sequence[Mapping[str, object]], *, gallery: str
) -> tuple[dict[str, object], ...]:
    rows = [
        normalize_observation(row)
        for row in observations
        if str(row.get("status")) == "VALID"
        and str(row.get("gallery_requested_size")) == gallery
        and not bool(row.get("predicted_overlap"))
    ]
    if not rows:
        raise H2ProgramError(f"no valid integration observations for gallery {gallery}")
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                str(row["case_id"]),
                str(row["anonymous_speaker_id"]),
                float(row["source_time_sec"]),
                str(row["observation_id"]),
            ),
        )
    )


def _identity_policy_from_tuning(tuning: Mapping[str, object]) -> IdentityPolicy:
    expiry_value = tuning.get("identity_expiry_sec", 120.0)
    expiry_mode = str(tuning.get("identity_expiry_mode") or "source_clock")
    if isinstance(expiry_value, str):
        if expiry_value.casefold() not in {"end_of_session", "session_end"}:
            raise H2ProgramError(f"unsupported identity expiry cell: {expiry_value}")
        expiry_mode = "end_session"
        expiry_sec = 120.0
    else:
        expiry_sec = float(expiry_value)
    identity_fields = {
        key: tuning[key]
        for key in (
            "score_threshold",
            "margin_threshold",
            "minimum_evidence_sec",
            "minimum_embedding_consistency",
            "consecutive_passes_to_confirm",
            "consecutive_failures_to_release",
            "hysteresis",
            "hysteresis_policy",
            "adaptive_early_max_evidence_sec",
            "adaptive_standard_evidence_sec",
            "adaptive_early_score_delta",
            "adaptive_early_margin_delta",
            "adaptive_medium_score_delta",
            "adaptive_medium_margin_delta",
        )
        if key in tuning and tuning[key] is not None
    }
    identity = canonical_sha256(
        {
            **identity_fields,
            "identity_expiry_sec": expiry_sec,
            "identity_expiry_mode": expiry_mode,
        }
    )
    return IdentityPolicy(
        hybrid_label="H2",
        policy_id=f"h2_science_exact_replay.v2:{identity}",
        score_threshold=float(identity_fields["score_threshold"]),
        margin_threshold=float(identity_fields["margin_threshold"]),
        minimum_evidence_sec=float(identity_fields["minimum_evidence_sec"]),
        minimum_embedding_consistency=float(
            identity_fields["minimum_embedding_consistency"]
        ),
        consecutive_passes_to_confirm=int(
            identity_fields.get("consecutive_passes_to_confirm", 2)
        ),
        consecutive_failures_to_release=int(
            identity_fields.get("consecutive_failures_to_release", 2)
        ),
        hysteresis=float(identity_fields.get("hysteresis", 0.02)),
        identity_expiry_sec=expiry_sec,
        hysteresis_policy=str(
            identity_fields.get("hysteresis_policy", "LEGACY_TWO_CONFIRM_ONE_RELEASE")
        ),
        adaptive_early_max_evidence_sec=float(
            identity_fields.get("adaptive_early_max_evidence_sec", 1.5)
        ),
        adaptive_standard_evidence_sec=float(
            identity_fields.get("adaptive_standard_evidence_sec", 3.0)
        ),
        adaptive_early_score_delta=float(
            identity_fields.get("adaptive_early_score_delta", 0.05)
        ),
        adaptive_early_margin_delta=float(
            identity_fields.get("adaptive_early_margin_delta", 0.02)
        ),
        adaptive_medium_score_delta=float(
            identity_fields.get("adaptive_medium_score_delta", 0.02)
        ),
        adaptive_medium_margin_delta=float(
            identity_fields.get("adaptive_medium_margin_delta", 0.01)
        ),
        identity_expiry_mode=expiry_mode,
        tentative_visible=True,
    )


def _observation_start_sec(row: Mapping[str, object]) -> float:
    for key in ("turn_start_sec", "cluster_start_sec", "region_start_sec"):
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value))
    return max(
        0.0,
        float(row["source_time_sec"]) - float(row["evidence_duration_sec"]),
    )


def _transition_replay_row(
    *,
    case_id: str,
    transition: object,
    row: Mapping[str, object],
    sequence_index: int,
    cluster_start_sec: float,
    cluster_end_sec: float,
    prior_display: str | None,
    passes_open_set_gate: bool,
    event_kind: str,
) -> dict[str, object]:
    known_id = getattr(transition, "known_speaker_id")
    state = getattr(transition, "state")
    speaker_label = str(getattr(transition, "speaker_label"))
    visible_enrolled_id = (
        speaker_label
        if state in {IdentityState.TENTATIVE_KNOWN, IdentityState.CONFIRMED_KNOWN}
        else None
    )
    reason = str(getattr(transition, "decision_reason"))
    transition_name = {
        "known_identity_tentative": "ACCUMULATING",
        "known_identity_confirmed": "CONFIRMED",
        "confirmed_identity_pass": "CONFIRMED_PASS",
        "current_identity_hysteresis_hold": "RETAINED_HYSTERESIS",
        "release_confirmation_pending": "RELEASE_PENDING",
        "known_identity_released_after_failures": "RELEASED",
        "challenger_confirmation_pending": "CHALLENGER_PENDING",
        "challenger_confirmed": "CORRECTED_TO_CHALLENGER",
        "identity_evidence_expired": "EXPIRED",
        "session_ended": "SESSION_ENDED",
    }.get(reason, "REJECTED" if known_id is None else "HELD")
    top1_score = getattr(transition, "top1_score")
    margin = getattr(transition, "margin")
    return {
        "case_id": case_id,
        "anonymous_speaker_id": str(getattr(transition, "anonymous_speaker_id")),
        "sequence_index": sequence_index,
        "event_kind": event_kind,
        "source_time_sec": float(getattr(transition, "source_time_sec")),
        "cluster_start_sec": cluster_start_sec,
        "cluster_end_sec": cluster_end_sec,
        "cluster_bounds_observed": any(
            row.get(key) is not None
            for key in ("turn_start_sec", "cluster_start_sec", "region_start_sec")
        ),
        "display_enrolled_id": visible_enrolled_id,
        "confirmed_enrolled_id": known_id,
        "speaker_label": speaker_label,
        "identity_state": (
            state.value if isinstance(state, IdentityState) else str(state)
        ),
        "display_changed": visible_enrolled_id != prior_display,
        "transition": transition_name,
        "decision_reason": reason,
        "top1_candidate_id": getattr(transition, "top1_candidate_id"),
        "top1_score": float(top1_score) if top1_score is not None else None,
        "top1_top2_margin": float(margin) if margin is not None else None,
        "passes_open_set_gate": passes_open_set_gate,
        "gallery_candidate_count": len(
            dict(row.get("candidate_raw_cosine_scores") or {})
        ),
        "active_roster_narrowed_gallery": False,
        "confirmation_count": int(getattr(transition, "confirmation_count")),
        "required_confirmation_count": int(
            getattr(transition, "required_confirmation_count")
        ),
        "release_count": int(getattr(transition, "release_count")),
        "required_release_count": int(getattr(transition, "required_release_count")),
        "effective_score_threshold": getattr(transition, "effective_score_threshold"),
        "effective_margin_threshold": getattr(transition, "effective_margin_threshold"),
        "transition_algorithm_used_truth": False,
        # These reference fields are copied only after the live state-machine
        # transition above and are consumed solely by scoring helpers.
        "truth_state": row["truth_state"],
        "reference_enrolled_id": row.get("reference_enrolled_id"),
        "reference_global_speaker_id": row.get("reference_global_speaker_id"),
        "effective_calibration_role": row["effective_calibration_role"],
    }


def _replay_identity_sequences(
    rows: Sequence[Mapping[str, object]], tuning: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    """Replay with the exact live ``SessionIdentityManager`` transition code.

    Events are ordered globally within a case by their emitted checkpoint
    sequence.  The coordinator processes every event emitted in one source
    frame and only then advances the source clock, so replay groups equal-time
    observations before expiry.  Reference fields are attached only after each
    transition has completed.
    """

    policy = _identity_policy_from_tuning(tuning)
    by_case: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        by_case[str(row["case_id"])].append(row)
    output: list[dict[str, object]] = []
    for case_id, raw_case_rows in sorted(by_case.items()):
        manager = SessionIdentityManager(policy)
        sequence_counts: Counter[str] = Counter()
        latest_reference: dict[str, Mapping[str, object]] = {}
        prior_display: dict[str, str | None] = {}
        cluster_bounds: dict[str, tuple[float, float]] = {}
        created_clusters: set[str] = set()
        creation_sequence = 0
        ordered = sorted(
            raw_case_rows,
            key=lambda row: (
                float(row["source_time_sec"]),
                int(row.get("raw_checkpoint_index") or 0),
                str(row["observation_id"]),
            ),
        )
        cursor = 0
        while cursor < len(ordered):
            now = float(ordered[cursor]["source_time_sec"])
            frame_rows: list[Mapping[str, object]] = []
            while (
                cursor < len(ordered)
                and float(ordered[cursor]["source_time_sec"]) == now
            ):
                frame_rows.append(ordered[cursor])
                cursor += 1
            for row in frame_rows:
                cluster_id = str(row["anonymous_speaker_id"])
                if cluster_id not in created_clusters:
                    creation_sequence += 1
                    start = _observation_start_sec(row)
                    manager.ensure_cluster(
                        ClusterCreation(
                            start_sample_index=int(round(start * 16000.0)),
                            creation_event_sequence=creation_sequence,
                            anonymous_speaker_id=cluster_id,
                        )
                    )
                    created_clusters.add(cluster_id)
                    cluster_bounds[cluster_id] = (start, now)
                    prior_display[cluster_id] = None
                else:
                    start, end = cluster_bounds[cluster_id]
                    cluster_bounds[cluster_id] = (
                        min(start, _observation_start_sec(row)),
                        max(end, now),
                    )
                evidence = IdentityEvidence(
                    anonymous_speaker_id=cluster_id,
                    source_time_sec=now,
                    evidence_duration_sec=float(row["evidence_duration_sec"]),
                    candidate_scores={
                        str(key): float(value)
                        for key, value in dict(
                            row["candidate_raw_cosine_scores"]
                        ).items()
                    },
                    embedding_consistency=float(row["embedding_consistency"]),
                    evidence_event_id=str(row["observation_id"]),
                    usable=str(row.get("status")) == "VALID",
                )
                transition = manager.observe(evidence)
                effective_score = transition.effective_score_threshold
                effective_margin = transition.effective_margin_threshold
                passes = bool(
                    effective_score is not None
                    and effective_margin is not None
                    and _accepts(
                        row,
                        threshold=effective_score,
                        margin=effective_margin,
                        evidence=policy.minimum_evidence_sec,
                        consistency=policy.minimum_embedding_consistency,
                    )
                )
                bounds = cluster_bounds[cluster_id]
                output.append(
                    _transition_replay_row(
                        case_id=case_id,
                        transition=transition,
                        row=row,
                        sequence_index=sequence_counts[cluster_id],
                        cluster_start_sec=bounds[0],
                        cluster_end_sec=bounds[1],
                        prior_display=prior_display.get(cluster_id),
                        passes_open_set_gate=passes,
                        event_kind="identity_evidence",
                    )
                )
                sequence_counts[cluster_id] += 1
                latest_reference[cluster_id] = row
                prior_display[cluster_id] = output[-1]["display_enrolled_id"]
            for expired in manager.advance_time(now):
                reference = latest_reference[expired.anonymous_speaker_id]
                cluster_id = expired.anonymous_speaker_id
                bounds = cluster_bounds[cluster_id]
                output.append(
                    _transition_replay_row(
                        case_id=case_id,
                        transition=expired,
                        row=reference,
                        sequence_index=sequence_counts[cluster_id],
                        cluster_start_sec=bounds[0],
                        cluster_end_sec=max(bounds[1], now),
                        prior_display=prior_display.get(cluster_id),
                        passes_open_set_gate=False,
                        event_kind="source_clock_expiry",
                    )
                )
                sequence_counts[cluster_id] += 1
                prior_display[cluster_id] = None
    return tuple(output)


def simulate_short_turn_events(
    events: Sequence[Mapping[str, object]],
    tuning: Mapping[str, object],
    *,
    short_turn_policy: str,
    maximum_turn_duration_sec: float,
    maximum_real_evidence_age_sec: float,
) -> tuple[dict[str, object], ...]:
    """Run a causal short-turn trace through the live identity manager.

    The trace must contain the coordinator's already-causal anonymous cluster
    identity.  No reclustering or reference truth is inferred here.  Duration
    uses the current turn, inheritance age uses the same cluster's last real
    usable evidence, and expiry uses source time.
    """

    if short_turn_policy not in SHORT_TURN_POLICIES:
        raise ValueError(f"unsupported short-turn policy: {short_turn_policy}")
    if maximum_turn_duration_sec <= 0 or maximum_real_evidence_age_sec < 0:
        raise ValueError("short-turn duration must be > 0 and age must be >= 0")
    policy = _identity_policy_from_tuning(tuning)
    output: list[dict[str, object]] = []
    by_case: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for event in events:
        by_case[str(event["case_id"])].append(event)
    for case_id, case_events in sorted(by_case.items()):
        manager = SessionIdentityManager(policy)
        created: set[str] = set()
        creation_sequence = 0
        ordered = [
            row
            for _index, row in sorted(
                enumerate(case_events),
                key=lambda item: (
                    float(item[1]["source_time_sec"]),
                    int(item[1].get("event_sequence", item[0])),
                    str(item[1].get("event_id") or ""),
                ),
            )
        ]
        for event_index, event in enumerate(ordered):
            event_type = str(event["event_type"])
            now = float(event["source_time_sec"])
            frame_ends_after_event = (
                event_index + 1 == len(ordered)
                or float(ordered[event_index + 1]["source_time_sec"]) != now
            )
            if event_type == "end_session":
                manager.end_session(now)
                created.clear()
                continue
            cluster_id = str(event["anonymous_speaker_id"])
            same_cluster = cluster_id in created
            if not same_cluster:
                creation_sequence += 1
                manager.ensure_cluster(
                    ClusterCreation(
                        start_sample_index=int(
                            round(float(event.get("turn_start_sec") or now) * 16000)
                        ),
                        creation_event_sequence=creation_sequence,
                        anonymous_speaker_id=cluster_id,
                    )
                )
                created.add(cluster_id)
            if event_type == "identity_evidence":
                scores = event.get("candidate_raw_cosine_scores") or event.get(
                    "candidate_scores"
                )
                if not isinstance(scores, Mapping):
                    raise ValueError("identity_evidence event lacks candidate scores")
                manager.observe(
                    IdentityEvidence(
                        anonymous_speaker_id=cluster_id,
                        source_time_sec=now,
                        evidence_duration_sec=float(event["evidence_duration_sec"]),
                        candidate_scores={
                            str(key): float(value) for key, value in scores.items()
                        },
                        embedding_consistency=float(event["embedding_consistency"]),
                        evidence_event_id=str(event["event_id"]),
                        usable=bool(event.get("usable", True)),
                    )
                )
                if frame_ends_after_event:
                    manager.advance_time(now)
                continue
            if event_type != "short_turn":
                raise ValueError(f"unsupported causal short-turn event: {event_type}")
            start = float(event["turn_start_sec"])
            end = float(event["turn_end_sec"])
            if end <= start or abs(end - now) > 1e-6:
                raise ValueError("short turn must end at its source-time decision")
            duration = end - start
            snapshot = manager.snapshot(cluster_id)
            last_real = snapshot.last_usable_source_sec
            age = now - last_real if last_real is not None else None
            within_duration_gate = duration < maximum_turn_duration_sec
            predicted_overlap = bool(event.get("predicted_overlap", False))
            strong_contradiction = bool(event.get("strong_contradiction", False))
            transition = None
            reason = "generic_by_policy"
            if short_turn_policy == "FRESH_EMBEDDING_REQUIRED":
                scores = event.get("candidate_raw_cosine_scores") or event.get(
                    "candidate_scores"
                )
                if within_duration_gate and isinstance(scores, Mapping):
                    transition = manager.observe(
                        IdentityEvidence(
                            anonymous_speaker_id=cluster_id,
                            source_time_sec=now,
                            evidence_duration_sec=float(
                                event.get("evidence_duration_sec") or duration
                            ),
                            candidate_scores={
                                str(key): float(value) for key, value in scores.items()
                            },
                            embedding_consistency=float(event["embedding_consistency"]),
                            evidence_event_id=str(event["event_id"]),
                            usable=bool(event.get("usable", True)),
                        )
                    )
                    reason = transition.decision_reason
                else:
                    reason = "fresh_embedding_unavailable"
            elif short_turn_policy == "ANONYMOUS_CLUSTER_INHERITANCE":
                reason = (
                    "anonymous_cluster_inherited"
                    if same_cluster and within_duration_gate
                    else "anonymous_cluster_not_inherited"
                )
            elif short_turn_policy == "CONFIRMED_NAME_INHERITANCE":
                if within_duration_gate:
                    transition = manager.inherit_confirmed_short_turn(
                        cluster_id,
                        source_time_sec=now,
                        maximum_gap_sec=maximum_real_evidence_age_sec,
                    )
                reason = (
                    transition.decision_reason
                    if transition is not None
                    else "confirmed_name_inheritance_rejected"
                )
            elif short_turn_policy == "INHERITANCE_WITH_CONTRADICTION_CHECKS":
                if within_duration_gate:
                    transition = manager.inherit_confirmed_short_turn(
                        cluster_id,
                        source_time_sec=now,
                        maximum_gap_sec=maximum_real_evidence_age_sec,
                        same_cluster=same_cluster,
                        predicted_overlap=predicted_overlap,
                        strong_contradiction=strong_contradiction,
                    )
                reason = (
                    transition.decision_reason
                    if transition is not None
                    else "contradiction_checked_inheritance_rejected"
                )
            snapshot_after = manager.snapshot(cluster_id)
            inherited_known = (
                transition.known_speaker_id if transition is not None else None
            )
            public_label = (
                inherited_known
                if inherited_known is not None
                else snapshot_after.unknown_label
            )
            result = {
                "schema_version": "h2-short-turn-causal-simulation.v2",
                "case_id": case_id,
                "event_id": str(event["event_id"]),
                "short_turn_policy": short_turn_policy,
                "maximum_turn_duration_sec": maximum_turn_duration_sec,
                "maximum_real_evidence_age_sec": (maximum_real_evidence_age_sec),
                "short_turn_inheritance_max_sec": (
                    maximum_turn_duration_sec
                    if maximum_turn_duration_sec == maximum_real_evidence_age_sec
                    else None
                ),
                "source_time_sec": now,
                "turn_start_sec": start,
                "turn_end_sec": end,
                "turn_duration_sec": duration,
                "duration_bin": _short_turn_duration_bin(duration),
                "within_current_turn_duration_gate": within_duration_gate,
                "anonymous_speaker_id": cluster_id,
                "same_cluster_as_prior_real_evidence": same_cluster
                and last_real is not None,
                "last_real_evidence_source_sec": last_real,
                "same_cluster_last_real_evidence_age_sec": age,
                "predicted_overlap": predicted_overlap,
                "strong_contradiction": strong_contradiction,
                "display_enrolled_id": inherited_known,
                "speaker_label": public_label,
                "decision_reason": reason,
                "source_evidence_event_ids": (
                    list(transition.evidence_event_ids)
                    if transition is not None
                    else []
                ),
                "source_clock_expiry_mode": policy.identity_expiry_mode,
                "transition_algorithm_used_truth": False,
            }
            # Truth is copied after the decision and never read above.
            for key in (
                "truth_state",
                "reference_enrolled_id",
                "reference_global_speaker_id",
                "effective_calibration_role",
                "word_count",
                "fresh_embedding_compute_ms",
                "later_correction_enrolled_id",
                "later_correction_source_sec",
                "retracted",
            ):
                result[key] = event.get(key)
            output.append(result)
            if frame_ends_after_event:
                manager.advance_time(now)
    return tuple(output)


def _short_turn_duration_bin(duration_sec: float) -> str:
    if duration_sec < 0 or not math.isfinite(duration_sec):
        raise ValueError("short-turn duration must be finite and >= 0")
    if duration_sec < 0.5:
        return "LT_0P5"
    if duration_sec < 1.0:
        return "GE_0P5_LT_1P0"
    if duration_sec <= 2.0:
        return "GE_1P0_LE_2P0"
    return "GT_2P0"


def _validate_short_turn_trace(
    rows: Sequence[Mapping[str, object]],
    *,
    assignment: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    if not rows:
        raise H2ProgramError("causal short-turn trace is empty")
    expected_assignment = str(assignment["assignment_sha256"])
    output: list[dict[str, object]] = []
    for raw in rows:
        row = dict(raw)
        if row.get("schema_version") != "h2-short-turn-causal-event.v1":
            raise H2ProgramError("unexpected causal short-turn trace schema")
        if str(row.get("split")) != "development" or bool(
            row.get("evaluation_material_inspected")
        ):
            raise H2ProgramError("causal short-turn trace crossed the firewall")
        if str(row.get("h2_calibration_assignment_sha256")) != expected_assignment:
            raise H2ProgramError("causal short-turn trace assignment differs")
        if str(row.get("effective_calibration_role")) not in {
            "calibration",
            "selection",
        }:
            raise H2ProgramError("causal short-turn event lacks development role")
        if any(
            key in row
            for key in (
                "embedding",
                "embedding_vector",
                "raw_embedding",
                "template_vectors",
            )
        ):
            raise H2ProgramError("raw biometric vector entered short-turn trace")
        event_type = str(row.get("event_type"))
        required = {"case_id", "event_id", "event_sequence", "source_time_sec"}
        if event_type != "end_session":
            required.add("anonymous_speaker_id")
        if event_type == "identity_evidence":
            required.update(
                {
                    "evidence_duration_sec",
                    "candidate_raw_cosine_scores",
                    "embedding_consistency",
                }
            )
        elif event_type == "short_turn":
            if "live_projection" in row:
                raise H2ProgramError("fabricated live_projection is forbidden")
            required.update(
                {
                    "turn_start_sec",
                    "turn_end_sec",
                    "predicted_overlap",
                    "strong_contradiction",
                    "word_count",
                    "fresh_embedding_compute_ms",
                }
            )
        elif event_type != "end_session":
            raise H2ProgramError(f"unknown causal trace event: {event_type}")
        missing = sorted(key for key in required if row.get(key) is None)
        if missing:
            raise H2ProgramError(
                f"causal short-turn event lacks fields: {', '.join(missing)}"
            )
        sequence = int(row["event_sequence"])
        if sequence < 0:
            raise H2ProgramError("causal short-turn event sequence must be >= 0")
        row["event_sequence"] = sequence
        output.append(row)
    sequence_keys = [
        (str(row["case_id"]), int(row["event_sequence"])) for row in output
    ]
    if len(sequence_keys) != len(set(sequence_keys)):
        raise H2ProgramError("causal short-turn trace has duplicate event sequences")
    if not any(row["event_type"] == "short_turn" for row in output):
        raise H2ProgramError("causal trace has no short-turn event")
    return tuple(output)


def _score_short_turn_simulation(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    correct = wrong = generic = corrections = retractions = 0
    stranger_false_known = 0
    words = compute_avoided = 0
    time_saved = 0.0
    for row in rows:
        label = row.get("display_enrolled_id")
        truth = str(row.get("truth_state"))
        reference = row.get("reference_enrolled_id")
        if label is None:
            generic += 1
        elif truth == "KNOWN" and str(label) == str(reference):
            correct += 1
        else:
            wrong += 1
            if truth == "UNKNOWN":
                stranger_false_known += 1
        if row.get("later_correction_enrolled_id") is not None:
            corrections += 1
        if bool(row.get("retracted")):
            retractions += 1
        words += int(row.get("word_count") or 0)
        if row["short_turn_policy"] != "FRESH_EMBEDDING_REQUIRED":
            compute_avoided += 1
            time_saved += float(row.get("fresh_embedding_compute_ms") or 0.0) / 1000.0
    return {
        "turn_count": len(rows),
        "correct_inherited_name_count": correct,
        "wrong_inherited_name_count": wrong,
        "generic_label_count": generic,
        "correct_inherited_name_rate": _ratio(correct, len(rows)),
        "wrong_inherited_name_rate": _ratio(wrong, len(rows)),
        "generic_label_rate": _ratio(generic, len(rows)),
        "stranger_false_known_count": stranger_false_known,
        "correction_count": corrections,
        "retraction_count": retractions,
        "words_labelled": words,
        "embedding_calls_avoided": compute_avoided,
        "compute_time_saved_sec": time_saved,
    }


def _sequence_decision_metrics(
    decisions: Sequence[Mapping[str, object]], *, role: str
) -> dict[str, object]:
    selected = [
        row for row in decisions if str(row["effective_calibration_role"]) == role
    ]
    groups: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in selected:
        groups[(str(row["case_id"]), str(row["anonymous_speaker_id"]))].append(row)
    final = [
        max(
            values,
            key=lambda row: (float(row["source_time_sec"]), int(row["sequence_index"])),
        )
        for values in groups.values()
    ]
    known = [row for row in final if row["truth_state"] == "KNOWN"]
    unknown = [row for row in final if row["truth_state"] == "UNKNOWN"]
    correct = sum(
        row.get("display_enrolled_id") is not None
        and str(row["display_enrolled_id"]) == str(row.get("reference_enrolled_id"))
        for row in known
    )
    wrong = sum(
        row.get("display_enrolled_id") is not None
        and str(row["display_enrolled_id"]) != str(row.get("reference_enrolled_id"))
        for row in known
    )
    unknown_speakers: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in selected:
        if row["truth_state"] != "UNKNOWN":
            continue
        speaker = str(
            row.get("reference_global_speaker_id")
            or f"case-cluster::{row['case_id']}::{row['anonymous_speaker_id']}"
        )
        unknown_speakers[speaker].append(row)
    false_speakers = sum(
        any(row.get("display_enrolled_id") is not None for row in values)
        for values in unknown_speakers.values()
    )
    revisions = sum(bool(row["display_changed"]) for row in selected)
    latencies: list[float] = []
    tentative_latencies: list[float] = []
    confirmed_latencies: list[float] = []
    stable_latencies: list[float] = []
    eligible_sequences = 0
    wrong_known_dwell = 0.0
    stranger_false_known_dwell = 0.0
    known_observed_dwell = 0.0
    unknown_observed_dwell = 0.0
    oscillations = 0
    known_to_known_switches = 0
    known_to_generic_regressions = 0
    corrections = 0
    beneficial_generic_to_correct = 0
    premature_wrong_names = 0
    release_pending = 0
    for values in groups.values():
        sequence = sorted(
            values,
            key=lambda row: (float(row["source_time_sec"]), int(row["sequence_index"])),
        )
        previous_label: str | None = None
        previous_correct: bool | None = None
        previous_seen = False
        for index, row in enumerate(sequence):
            start = float(row["source_time_sec"])
            end = (
                float(sequence[index + 1]["source_time_sec"])
                if index + 1 < len(sequence)
                else max(start, float(row["cluster_end_sec"]))
            )
            dwell = max(0.0, end - start)
            label = (
                str(row["display_enrolled_id"])
                if row.get("display_enrolled_id") is not None
                else None
            )
            correct_label = bool(
                label is not None
                and row["truth_state"] == "KNOWN"
                and label == str(row.get("reference_enrolled_id"))
            )
            if row["truth_state"] == "KNOWN":
                known_observed_dwell += dwell
                if label is not None and not correct_label:
                    wrong_known_dwell += dwell
                    premature_wrong_names += 1
            else:
                unknown_observed_dwell += dwell
                if label is not None:
                    stranger_false_known_dwell += dwell
            if previous_label is not None and label != previous_label:
                oscillations += 1
                if label is not None:
                    known_to_known_switches += 1
                else:
                    known_to_generic_regressions += 1
            if previous_correct is False and correct_label:
                corrections += 1
            if previous_seen and previous_label is None and correct_label:
                beneficial_generic_to_correct += 1
            if str(row.get("transition")) == "RELEASE_PENDING":
                release_pending += 1
            previous_label = label
            previous_correct = correct_label if label is not None else None
            previous_seen = True
        if sequence[0]["truth_state"] != "KNOWN":
            continue
        eligible_sequences += 1
        tentative_times = [
            float(row["source_time_sec"])
            for row in sequence
            if row.get("identity_state") == IdentityState.TENTATIVE_KNOWN.value
        ]
        if tentative_times:
            tentative_latencies.append(
                min(tentative_times) - float(sequence[0]["cluster_start_sec"])
            )
        correct_times = [
            float(row["source_time_sec"])
            for row in sequence
            if row.get("display_enrolled_id") is not None
            and str(row["display_enrolled_id"]) == str(row.get("reference_enrolled_id"))
        ]
        if correct_times:
            latencies.append(
                min(correct_times) - float(sequence[0]["cluster_start_sec"])
            )
            confirmed_times = [
                float(row["source_time_sec"])
                for row in sequence
                if row.get("identity_state") == IdentityState.CONFIRMED_KNOWN.value
                and row.get("display_enrolled_id") is not None
                and str(row["display_enrolled_id"])
                == str(row.get("reference_enrolled_id"))
            ]
            if confirmed_times:
                confirmed_latencies.append(
                    min(confirmed_times) - float(sequence[0]["cluster_start_sec"])
                )
            for index, row in enumerate(sequence):
                if row.get("display_enrolled_id") is None or str(
                    row["display_enrolled_id"]
                ) != str(row.get("reference_enrolled_id")):
                    continue
                if all(
                    later.get("display_enrolled_id") is not None
                    and str(later["display_enrolled_id"])
                    == str(later.get("reference_enrolled_id"))
                    for later in sequence[index:]
                ):
                    stable_latencies.append(
                        float(row["source_time_sec"])
                        - float(sequence[0]["cluster_start_sec"])
                    )
                    break
    return {
        "known_cluster_count": len(known),
        "unknown_cluster_count": len(unknown),
        "correct_known_rate": _ratio(correct, len(known)),
        "wrong_known_rate": _ratio(wrong, len(known)),
        "unknown_speaker_count": len(unknown_speakers),
        "false_known_speaker_count": false_speakers,
        "unknown_speaker_fpir": _ratio(false_speakers, len(unknown_speakers)),
        "first_correct_latency_sec": (
            statistics.fmean(latencies) if latencies else None
        ),
        "first_correct_censored_count": eligible_sequences - len(latencies),
        "tentative_name_latency_sec": (
            statistics.fmean(tentative_latencies) if tentative_latencies else None
        ),
        "confirmed_name_latency_sec": (
            statistics.fmean(confirmed_latencies) if confirmed_latencies else None
        ),
        "confirmed_name_censored_count": (
            eligible_sequences - len(confirmed_latencies)
        ),
        "stable_name_latency_sec": (
            statistics.fmean(stable_latencies) if stable_latencies else None
        ),
        "stable_name_censored_count": eligible_sequences - len(stable_latencies),
        "never_identified_rate": _ratio(
            eligible_sequences - len(latencies), eligible_sequences
        ),
        "wrong_known_dwell_sec": wrong_known_dwell,
        "known_observed_dwell_sec": known_observed_dwell,
        "wrong_known_dwell_rate": _ratio(wrong_known_dwell, known_observed_dwell),
        "stranger_false_known_dwell_sec": stranger_false_known_dwell,
        "unknown_observed_dwell_sec": unknown_observed_dwell,
        "stranger_false_known_dwell_rate": _ratio(
            stranger_false_known_dwell, unknown_observed_dwell
        ),
        "dwell_scope": "between_causal_checkpoints_only",
        "final_checkpoint_dwell_right_censored": True,
        "identity_oscillation_count": oscillations,
        "harmful_known_to_known_switch_count": known_to_known_switches,
        "known_to_generic_regression_count": known_to_generic_regressions,
        "correction_count": corrections,
        "beneficial_generic_to_correct_count": beneficial_generic_to_correct,
        "premature_wrong_name_event_count": premature_wrong_names,
        "release_confirmation_pending_count": release_pending,
        "identity_revision_count": revisions,
        "identity_revision_rate": _ratio(revisions, len(selected)),
        "observation_count": len(selected),
        "full_gallery_preserved": not any(
            bool(row.get("active_roster_narrowed_gallery")) for row in selected
        ),
    }


def _short_turn_metrics(
    decisions: Sequence[Mapping[str, object]],
    *,
    role: str,
    inheritance_max_sec: float,
    retroactive_correction_sec: float,
    tuning: Mapping[str, object],
) -> dict[str, object]:
    groups: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in decisions:
        if str(row["effective_calibration_role"]) == role:
            groups[(str(row["case_id"]), str(row["anonymous_speaker_id"]))].append(row)
    by_case: dict[str, list[list[Mapping[str, object]]]] = defaultdict(list)
    for (case_id, _cluster_id), values in groups.items():
        by_case[case_id].append(
            sorted(values, key=lambda row: float(row["source_time_sec"]))
        )
    inherited: list[tuple[Mapping[str, object], str]] = []
    corrected_known = 0.0
    corrected_wrong = 0.0
    all_unknown_speakers: set[str] = set()
    for sequences in by_case.values():
        sequences.sort(key=lambda rows: float(rows[0]["cluster_start_sec"]))
        prior_confirmed: str | None = None
        prior_end: float | None = None
        for sequence in sequences:
            first = sequence[0]
            if first["truth_state"] == "UNKNOWN":
                all_unknown_speakers.add(
                    str(
                        first.get("reference_global_speaker_id")
                        or f"case-cluster::{first['case_id']}::{first['anonymous_speaker_id']}"
                    )
                )
            start = float(first["cluster_start_sec"])
            first_confirmed = next(
                (row for row in sequence if row.get("display_enrolled_id") is not None),
                None,
            )
            contradiction = bool(
                first["passes_open_set_gate"]
                and prior_confirmed is not None
                and str(first["top1_candidate_id"]) != prior_confirmed
            )
            if (
                prior_confirmed is not None
                and prior_end is not None
                and 0.0 <= start - prior_end <= inheritance_max_sec
                and not contradiction
            ):
                inherited.append((first, prior_confirmed))
            if first_confirmed is not None:
                label = str(first_confirmed["display_enrolled_id"])
                duration = min(
                    retroactive_correction_sec,
                    max(0.0, float(first_confirmed["source_time_sec"]) - start),
                )
                if first["truth_state"] == "KNOWN" and label == str(
                    first.get("reference_enrolled_id")
                ):
                    corrected_known += duration
                else:
                    corrected_wrong += duration
            final_label = sequence[-1].get("display_enrolled_id")
            if final_label is not None:
                prior_confirmed = str(final_label)
                prior_end = float(sequence[-1]["cluster_end_sec"])
            elif prior_end is not None and start - prior_end > float(
                tuning["identity_expiry_sec"]
            ):
                prior_confirmed = None
                prior_end = None
    correct = wrong = 0
    false_unknown_speakers: set[str] = set()
    for row, inherited_label in inherited:
        if row["truth_state"] == "KNOWN" and inherited_label == str(
            row.get("reference_enrolled_id")
        ):
            correct += 1
        else:
            wrong += 1
        if row["truth_state"] == "UNKNOWN":
            speaker = str(
                row.get("reference_global_speaker_id")
                or f"case-cluster::{row['case_id']}::{row['anonymous_speaker_id']}"
            )
            false_unknown_speakers.add(speaker)
    return {
        "inheritance_count": len(inherited),
        "correct_inheritance_count": correct,
        "wrong_inheritance_count": wrong,
        "correct_inheritance_rate": _ratio(correct, len(inherited)),
        "wrong_inheritance_rate": _ratio(wrong, len(inherited)),
        "unknown_speaker_count": len(all_unknown_speakers),
        "false_known_unknown_speaker_count": len(false_unknown_speakers),
        "unknown_speaker_fpir": _ratio(
            len(false_unknown_speakers), len(all_unknown_speakers)
        ),
        "corrected_known_time_sec": corrected_known,
        "wrong_corrected_time_sec": corrected_wrong,
    }


def _execute_transcript_policy_replay(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    policies = {
        "T1_ASR_ENDPOINT_PUNCTUATION",
        "T2_PAUSE_ASR_ENDPOINT",
        "T3_PAUSE_ASR_SPEAKER_CHANGE",
        "T4_SPEAKER_CHANGE_DOMINANT",
    }
    candidates = [
        candidate
        for candidate in jobs
        if candidate.configuration_id in policies
        and candidate.job_kind == "post_selection_paragraph_validation"
    ]
    if {candidate.configuration_id for candidate in candidates} != policies:
        raise H2ProgramError("four post-selection paragraph validations are required")
    priority = TRANSCRIPT_POLICY_PRIORITY
    rows: list[dict[str, object]] = []
    result_roots: dict[str, Path] = {}
    for candidate in sorted(candidates, key=lambda value: value.configuration_id):
        root, identity = _completed_result_root(state, candidate)
        _require_valid_result_tree(root)
        values = _result_metric_values(root)
        result_roots[candidate.configuration_id] = root
        rows.append(
            {
                "schema_version": "h2-transcript-policy-replay.v1",
                "paragraph_policy": candidate.configuration_id,
                "source_job_id": candidate.job_id,
                "source_result_root": str(root),
                "source_result_sha256": identity,
                **{metric: values.get(metric) for metric, _direction in priority},
                "actual_runtime_result": True,
                "development_only_selection": True,
                "evaluation_material_inspected": False,
            }
        )
    common = [
        (metric, direction)
        for metric, direction in priority
        if all(row.get(metric) is not None for row in rows)
    ]
    if not common:
        raise H2ProgramError(
            "paragraph runtime results share no declared computed selection metric"
        )
    selected = min(
        rows,
        key=lambda row: tuple(
            float(row[metric]) if direction == "min" else -float(row[metric])
            for metric, direction in common
        )
        + (str(row["paragraph_policy"]),),
    )
    integration_job, integration_root, integration_identity = _integration_source(
        paths, state, jobs
    )
    integration_pipeline = read_json(integration_root / "pipeline_identity.json")
    integration_tuning = integration_pipeline.get("runtime_tuning")
    if not isinstance(integration_tuning, Mapping):
        raise H2ProgramError("integration result lacks strict runtime tuning")
    axis_evidence = _phase1_axis_evidence(
        state, jobs, integration_tuning=integration_tuning
    )
    payload = {
        "schema_version": "h2-science-handler-result.v1",
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "promotion_eligible": True,
        "selected_runtime_tuning": {"paragraph_policy": selected["paragraph_policy"]},
        "selected_runtime_axes": ["paragraph_policy"],
        "selected_frontier_row": selected,
        "common_metric_priority": [metric for metric, _direction in common],
        "safety_priority_contract_id": SAFETY_PRIORITY_CONTRACT_ID,
        "ordered_safety_risk_families": list(SAFETY_PRIORITY_ORDERED_RISK_FAMILIES),
        "selection_method": "actual_runtime_results_declared_lexicographic_priority",
        "weighted_composite_used": False,
        "integration_runtime_job_id": integration_job.job_id,
        "integration_runtime_result_sha256": integration_identity,
        "boundary_correction_ms_already_materialized": integration_tuning.get(
            "boundary_correction_ms"
        ),
        "overlap_policy_already_materialized": integration_tuning.get("overlap_policy"),
        "boundary_or_overlap_reselected": False,
        "paragraph_pause_sec_reselected": False,
        "paragraph_max_words_reselected": False,
        "development_only_selection": True,
        "evaluation_material_inspected": False,
        "neural_inference_performed_by_handler": False,
    }
    return payload, {
        "transcript_policy_frontier.csv": rows,
        "boundary_overlap_selection_evidence.csv": axis_evidence,
    }


def _execute_hierarchical_bootstrap(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    del paths
    evaluation_jobs = [
        candidate
        for candidate in jobs
        if candidate.split == "evaluation"
        and candidate.job_kind in {"runtime_accuracy", "diagnostic_runtime"}
    ]
    if not evaluation_jobs:
        raise H2ProgramError("bootstrap has no predeclared held-out runtime jobs")
    per_case: list[dict[str, object]] = []
    source_results: list[dict[str, object]] = []
    for candidate in evaluation_jobs:
        root, identity = _completed_result_root(state, candidate)
        _require_valid_result_tree(root)
        path = root / "diagnostics/per_case_metrics.jsonl"
        if not path.is_file():
            raise H2ProgramError(
                f"held-out result lacks per-case metrics: {candidate.job_id}"
            )
        source_results.append(
            {
                "job_id": candidate.job_id,
                "pipeline_id": candidate.pipeline_id,
                "mode": candidate.mode,
                "result_root": str(root),
                "result_sha256": identity,
            }
        )
        for raw in read_jsonl(path):
            per_case.extend(_flatten_per_case_metrics(candidate, raw))
    intervals = hierarchical_speaker_case_bootstrap(
        per_case,
        repetitions=BOOTSTRAP_REPETITIONS,
        seed=BOOTSTRAP_SEED,
    )
    if not intervals:
        raise H2ProgramError("no computed held-out per-case metrics for bootstrap")
    payload = {
        "schema_version": "h2-speaker-case-hierarchical-bootstrap.v2",
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "source_results": source_results,
        "source_result_count": len(source_results),
        "per_case_metric_row_count": len(per_case),
        "interval_count": len(intervals),
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "resampling_design": (
            "whole_reference_speaker_clusters_all_probes_fractional_"
            "multi_speaker_cases_with_case_fallback"
        ),
        "checkpoint_or_clip_independence_assumed": False,
        "evaluation_policy_retuned": False,
        "evaluation_material_inspected": True,
        "selected_runtime_tuning": {},
        "selected_runtime_axes": [],
        "neural_inference_performed": False,
    }
    return payload, {
        "bootstrap_intervals.csv": intervals,
        "bootstrap_source_results.csv": source_results,
    }


def hierarchical_speaker_case_bootstrap(
    rows: Sequence[Mapping[str, object]],
    *,
    repetitions: int = BOOTSTRAP_REPETITIONS,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[dict[str, object], ...]:
    """Bootstrap whole speaker clusters while preserving every probe/case.

    A row containing ``K`` reference speakers contributes ``1/K`` to each of
    those speakers.  Consequently the full, unsampled point estimate counts
    every row exactly once, while a bootstrap draw includes *all* rows attached
    to each sampled speaker.  Rows without speaker identity are explicit
    case-level fallback clusters rather than invented speakers.
    """

    if repetitions < 1:
        raise ValueError("bootstrap repetitions must be positive")
    scopes: dict[tuple[str, str, str, str, str], list[Mapping[str, object]]] = (
        defaultdict(list)
    )
    for row in rows:
        if row.get("status") != "computed":
            continue
        key = (
            str(row["job_id"]),
            str(row["pipeline_id"]),
            str(row["mode"]),
            str(row["category"]),
            str(row["metric_id"]),
        )
        scopes[key].append(row)
    output: list[dict[str, object]] = []
    for key, values in sorted(scopes.items()):
        estimator = _bootstrap_estimator(values)
        clusters: dict[str, list[tuple[Mapping[str, object], float]]] = defaultdict(
            list
        )
        reference_speaker_keys: set[str] = set()
        fallback_case_keys: set[str] = set()
        for row in values:
            raw_speakers = row.get("reference_speaker_ids") or ()
            if isinstance(raw_speakers, (str, bytes)):
                raw_speakers = (raw_speakers,)
            speakers = sorted(
                {
                    f"{row.get('source_key')}::{str(speaker).strip()}"
                    for speaker in raw_speakers
                    if speaker is not None and str(speaker).strip()
                }
            )
            if not speakers:
                source_key = str(row.get("source_key") or "UNSPECIFIED_SOURCE")
                fallback_key = f"case::{source_key}::{row['case_id']}"
                fallback_case_keys.add(fallback_key)
                clusters[fallback_key].append((row, 1.0))
                continue
            fraction = 1.0 / len(speakers)
            for speaker in speakers:
                reference_speaker_keys.add(speaker)
                clusters[speaker].append((row, fraction))
        cluster_keys = sorted(clusters)
        if not cluster_keys:
            continue
        rng = random.Random(_derived_seed(seed, "|".join(key)))
        draws: list[float] = []
        for _ in range(repetitions):
            contributions: list[tuple[float, float]] = []
            for _cluster_ordinal in cluster_keys:
                sampled_cluster = rng.choice(cluster_keys)
                contributions.extend(
                    _bootstrap_contribution(
                        row,
                        estimator=estimator,
                        fraction=fraction,
                    )
                    for row, fraction in clusters[sampled_cluster]
                )
            estimate = _estimate_contributions(contributions, estimator)
            if math.isfinite(estimate):
                draws.append(estimate)
        point_contributions = [
            _bootstrap_contribution(
                row,
                estimator=estimator,
                fraction=fraction,
            )
            for cluster_key in cluster_keys
            for row, fraction in clusters[cluster_key]
        ]
        point = _estimate_contributions(point_contributions, estimator)
        cluster_probe_counts = [len(clusters[value]) for value in cluster_keys]
        output.append(
            {
                "schema_version": "h2-speaker-case-bootstrap-interval.v2",
                "job_id": key[0],
                "pipeline_id": key[1],
                "mode": key[2],
                "category": key[3],
                "metric_id": key[4],
                "status": "computed" if draws else "undefined",
                "point_estimate": point,
                "ci_lower_95": _linear_quantile(draws, 0.025) if draws else None,
                "ci_upper_95": _linear_quantile(draws, 0.975) if draws else None,
                "reference_speaker_cluster_count": len(reference_speaker_keys),
                "resampling_cluster_count": len(cluster_keys),
                "case_count": len({str(row["case_id"]) for row in values}),
                "fallback_case_unit_row_count": sum(
                    len(clusters[value]) for value in fallback_case_keys
                ),
                "fallback_case_unit_count": len(fallback_case_keys),
                "speaker_cluster_probe_count_min": min(cluster_probe_counts),
                "speaker_cluster_probe_count_max": max(cluster_probe_counts),
                "bootstrap_repetitions": repetitions,
                "bootstrap_seed": seed,
                "estimator": estimator,
                "resampling_unit": "whole_speaker_cluster_all_probes_with_case_fallback",
                "within_speaker_case_resampling": False,
                "multi_speaker_case_weighting": "fractional_by_reference_speaker_count",
            }
        )
    return tuple(output)


def _integration_source(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[H2Job, Path, str]:
    candidates = [
        job
        for job in jobs
        if job.job_kind == POST_PROMOTION_JOB_KIND
        and job.configuration_id == POST_PROMOTION_CONFIGURATION
        and job.split == "development"
    ]
    if len(candidates) != 1:
        raise H2ProgramError(
            "exactly one predeclared H2 post-promotion integration job is required"
        )
    source = candidates[0]
    root, identity = _completed_result_root(state, source)
    _require_valid_result_tree(root)
    if not (root / "diagnostics/challenger_identity_scores.jsonl").is_file():
        raise H2ProgramError(
            "post-promotion integration lacks development score observations"
        )
    pipeline = read_json(root / "pipeline_identity.json")
    contract = pipeline.get("execution_contract")
    if not isinstance(contract, Mapping):
        raise H2ProgramError("integration result lacks H2 execution contract")
    partition = contract.get("h2_development_integration_partition")
    if not isinstance(partition, Mapping):
        raise H2ProgramError(
            "integration execution contract lacks calibration partition"
        )
    protocol_assignment = _integration_assignment(paths)
    if partition.get("assignment_sha256") != protocol_assignment.get(
        "assignment_sha256"
    ):
        raise H2ProgramError("integration execution assignment differs from protocol")
    return source, root, identity


def _integration_observations(
    paths: ProgramPaths, source_root: Path
) -> tuple[tuple[dict[str, object], ...], dict[str, object]]:
    assignment = _integration_assignment(paths)
    if assignment.get("schema_version") != "h2-development-integration-partition.v2":
        raise H2ProgramError(
            "active H2 integration requires the speaker-disjoint v2 partition"
        )
    observations = load_development_observations((source_root,))
    assigned = apply_frozen_integration_assignment(observations, assignment)
    if not assigned:
        raise H2ProgramError("integration result has no policy observations")
    assignment_ids = {str(row["h2_calibration_assignment_sha256"]) for row in assigned}
    if assignment_ids != {str(assignment["assignment_sha256"])}:
        raise H2ProgramError("integration observations carry a mixed assignment")
    excluded = set(map(str, assignment.get("excluded_cross_cohort_case_ids") or ()))
    if excluded & {str(row["case_id"]) for row in assigned}:
        raise H2ProgramError("excluded cross-cohort cases entered integration replay")
    roles = {str(row["effective_calibration_role"]) for row in assigned}
    if roles != {"calibration", "selection"}:
        raise H2ProgramError("integration observations do not contain both v2 roles")
    observed_speakers = {
        role: {
            str(row["reference_global_speaker_id"])
            for row in assigned
            if str(row["effective_calibration_role"]) == role
            and row.get("reference_global_speaker_id")
        }
        for role in ("calibration", "selection")
    }
    if not observed_speakers["calibration"] or not observed_speakers["selection"]:
        raise H2ProgramError(
            "integration observations cannot demonstrate speaker disjointness"
        )
    if observed_speakers["calibration"] & observed_speakers["selection"]:
        raise H2ProgramError("integration observations cross v2 speaker cohorts")
    return assigned, assignment


def _integration_assignment(paths: ProgramPaths) -> dict[str, object]:
    if not paths.protocol_path.is_file():
        raise H2ProgramError("protocol manifest is required for H2 calibration")
    protocol = read_json(paths.protocol_path)
    panels = protocol.get("panels")
    development = panels.get("development") if isinstance(panels, Mapping) else None
    assignment = (
        development.get("integration_partition")
        if isinstance(development, Mapping)
        else None
    )
    if not isinstance(assignment, Mapping):
        raise H2ProgramError("protocol lacks H2 integration partition")
    return dict(assignment)


def _completed_result_root(state: Mapping[str, object], job: H2Job) -> tuple[Path, str]:
    row = _state_job(state, job.job_id)
    if row.get("state") != "COMPLETE":
        raise H2ProgramError(f"required result is not complete: {job.job_id}")
    raw_path = row.get("result_path")
    identity = str(row.get("result_sha256") or "")
    if not raw_path or not identity:
        raise H2ProgramError(f"required result lacks path/checksum: {job.job_id}")
    root = Path(str(raw_path)).resolve()
    if not root.is_dir():
        raise H2ProgramError(f"required result root is missing: {root}")
    return root, identity


def _require_valid_result_tree(root: Path) -> None:
    report = validate_result_tree(root)
    if not report.reusable:
        reasons = "; ".join(
            f"{issue.code}:{issue.logical_path}" for issue in report.issues[:5]
        )
        raise H2ProgramError(f"result tree is not checksum-reusable: {reasons}")


def _state_job(state: Mapping[str, object], job_id: str) -> Mapping[str, object]:
    values = state.get("jobs")
    if not isinstance(values, Mapping):
        raise H2ProgramError("program state lacks jobs")
    row = values.get(job_id)
    if not isinstance(row, Mapping):
        raise H2ProgramError(f"program state lacks job: {job_id}")
    return row


def _completed_science_result(
    state: Mapping[str, object], jobs: Sequence[H2Job], job_kind: str
) -> dict[str, object]:
    matching = [job for job in jobs if job.job_kind == job_kind]
    if len(matching) != 1:
        raise H2ProgramError(f"expected one prior science job: {job_kind}")
    row = _state_job(state, matching[0].job_id)
    if row.get("state") != "COMPLETE":
        raise H2ProgramError(f"prior science job is incomplete: {job_kind}")
    path = Path(str(row.get("result_path") or ""))
    expected = str(row.get("result_sha256") or "")
    if not path.is_file() or not expected or sha256_file(path) != expected:
        raise H2ProgramError(f"prior science result checksum differs: {job_kind}")
    result = read_json(path)
    if result.get("status") != "COMPLETE":
        raise H2ProgramError(f"prior science result is not complete: {job_kind}")
    if result.get("evaluation_material_inspected") is not False:
        raise H2ProgramError(f"prior science result crossed firewall: {job_kind}")
    return result


def _completed_science_result_sha(
    state: Mapping[str, object], jobs: Sequence[H2Job], job_kind: str
) -> str:
    matching = [job for job in jobs if job.job_kind == job_kind]
    if len(matching) != 1:
        raise H2ProgramError(f"expected one prior science job: {job_kind}")
    return str(_state_job(state, matching[0].job_id).get("result_sha256") or "")


def _publish_science_result(
    paths: ProgramPaths,
    job: H2Job,
    payload: Mapping[str, object],
    tables: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    root = paths.results_root / "jobs" / job.job_id / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, object]] = []
    for filename, rows in sorted(tables.items()):
        values = tuple(dict(row) for row in rows)
        path = root / filename
        if path.suffix.casefold() == ".jsonl":
            write_jsonl_atomic(path, values)
        elif path.suffix.casefold() == ".csv":
            write_csv_atomic(path, values, _table_fields(values))
        else:
            write_json_atomic(path, {"rows": list(values)})
        artifacts.append(
            {
                "path": filename,
                "sha256": sha256_file(path),
                "row_count": len(values),
            }
        )
    complete_statuses = {"COMPLETE", "GATED_NOT_PROMOTED"}
    final_payload = {
        **dict(payload),
        "artifact_manifest": artifacts,
        "handler_code_sha256": sha256_file(Path(__file__)),
    }
    result_path = root / "job_result.json"
    write_json_atomic(result_path, final_payload)
    status = str(payload.get("status"))
    complete = status in complete_statuses
    return {
        "state": (
            "complete" if complete else "stopped" if status == "STOPPED" else "failed"
        ),
        "error": None if complete else payload.get("error"),
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
    }


def _table_fields(rows: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    preferred = (
        "schema_version",
        "job_id",
        "pipeline_id",
        "mode",
        "case_id",
        "metric_id",
        "status",
    )
    keys = {str(key) for row in rows for key in row}
    ordered = [key for key in preferred if key in keys]
    ordered.extend(sorted(keys - set(ordered)))
    return tuple(ordered) or ("status",)


def _historical_enrollment_evidence(
    paths: ProgramPaths,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    manifest_path = paths.evaluation_root / HISTORICAL_EVIDENCE_RELATIVE_PATH
    manifest = read_yaml(manifest_path)
    if manifest.get("schema_version") != "just-peachy-h2-historical-evidence.v1":
        raise H2ProgramError("historical H2 evidence schema differs")
    enrollment = manifest.get("speaker_enrollment_live")
    frozen = manifest.get("frozen_h2")
    if not isinstance(enrollment, Mapping) or not isinstance(frozen, Mapping):
        raise H2ProgramError("historical enrollment evidence is incomplete")
    sources: list[dict[str, object]] = []
    for label, raw in enrollment.items():
        if not isinstance(raw, Mapping) or not raw.get("path") or not raw.get("sha256"):
            raise H2ProgramError(f"historical enrollment source is invalid: {label}")
        path = _evidence_path(paths, str(raw["path"]))
        observed = sha256_file(path)
        if observed.casefold() != str(raw["sha256"]).casefold():
            raise H2ProgramError(f"historical evidence checksum differs: {label}")
        sources.append(
            {
                "source_id": str(label),
                "path": str(path),
                "sha256": observed,
                "size_bytes": path.stat().st_size,
            }
        )
    frozen_policy = frozen.get("enrollment_policy")
    if not isinstance(frozen_policy, Mapping):
        raise H2ProgramError("frozen ReDim enrollment policy is missing")
    policy_path = _evidence_path(paths, str(frozen_policy["path"]))
    policy_sha = sha256_file(policy_path)
    if policy_sha.casefold() != str(frozen_policy["sha256"]).casefold():
        raise H2ProgramError("frozen enrollment policy checksum differs")
    rows: list[dict[str, object]] = []
    for source in sources:
        path = Path(str(source["path"]))
        if path.suffix.casefold() != ".csv":
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for raw in csv.DictReader(stream):
                if str(raw.get("backend") or "") != "redimnet2_b2_speaker_embedding":
                    continue
                rows.append(
                    {
                        "evidence_table": source["source_id"],
                        "source_sha256": source["sha256"],
                        **dict(raw),
                    }
                )
    summary = {
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "sources": sources,
        "frozen_policy_path": str(policy_path),
        "frozen_policy_sha256": policy_sha,
        "historical_row_count": len(rows),
        "commonvoice_threshold_transferred": False,
        "protocols_pooled": False,
    }
    return summary, tuple(rows)


def _historical_enrollment_configuration_rows(
    historical: Mapping[str, object],
) -> tuple[tuple[dict[str, object], ...], dict[str, object]]:
    sources = historical.get("sources")
    if not isinstance(sources, Sequence):
        raise H2ProgramError("historical enrollment source bindings are missing")
    duration_source = next(
        (
            row
            for row in sources
            if isinstance(row, Mapping) and row.get("source_id") == "duration_curve"
        ),
        None,
    )
    if not isinstance(duration_source, Mapping):
        raise H2ProgramError("historical enrollment analysis root is unresolved")
    analysis_root = Path(str(duration_source["path"])).parent
    inventory_path = analysis_root / "RESULT_FILE_INVENTORY.csv"
    configuration_path = analysis_root / "configuration_results.csv"
    manifest_path = analysis_root / "analysis_manifest.json"
    for path in (inventory_path, configuration_path, manifest_path):
        if not path.is_file():
            raise H2ProgramError(f"historical enrollment artifact is missing: {path}")
    with inventory_path.open("r", encoding="utf-8-sig", newline="") as stream:
        inventory = {
            str(row["relative_path"]): dict(row) for row in csv.DictReader(stream)
        }
    expected = inventory.get("configuration_results.csv")
    if (
        not isinstance(expected, Mapping)
        or str(expected.get("sha256") or "").casefold()
        != sha256_file(configuration_path).casefold()
    ):
        raise H2ProgramError("historical enrollment configuration checksum differs")
    with configuration_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = tuple(
            {
                **dict(raw),
                "source_table": "configuration_results.csv",
                "source_sha256": sha256_file(configuration_path),
            }
            for raw in csv.DictReader(stream)
            if str(raw.get("backend")) == "redimnet2_b2_speaker_embedding"
        )
    binding = {
        "source_kind": "completed_redimnet_enrollment_study",
        "protocol_id": "speaker_enrollment_live_v2_5107db9ab304",
        "configuration_results_path": str(configuration_path),
        "configuration_results_sha256": sha256_file(configuration_path),
        "result_inventory_path": str(inventory_path),
        "result_inventory_sha256": sha256_file(inventory_path),
        "analysis_manifest_path": str(manifest_path),
        "analysis_manifest_sha256": sha256_file(manifest_path),
    }
    return rows, binding


def build_integrated_enrollment_matrix(
    evidence_rows: Sequence[Mapping[str, object]],
    *,
    source_bindings: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Account for every declared enrollment cell without cross-protocol pooling."""

    rows: list[dict[str, object]] = []
    axis_names = tuple(ENROLLMENT_MATRIX_AXES)
    for values in product(*(ENROLLMENT_MATRIX_AXES[name] for name in axis_names)):
        axes = dict(zip(axis_names, values, strict=True))
        cell_id = "__".join(f"{key}={axes[key]}" for key in axis_names)
        exact = [
            row
            for row in evidence_rows
            if all(_enrollment_axis_value(row, key) == axes[key] for key in axis_names)
        ]
        if len(exact) != 1:
            reason = (
                "no scientifically identical completed source binds utterance count, "
                "total duration, independent-session condition, aggregation, and "
                "quality-filter policy in one protocol cell"
                if not exact
                else "multiple exact source rows disagree on the declared cell identity"
            )
            rows.append(
                unsupported_capability_row(
                    study_id="h2_integrated_enrollment_confirmation",
                    cell_id=cell_id,
                    reason=reason,
                    axes=axes,
                    source_bindings=source_bindings,
                )
            )
            continue
        source = exact[0]
        source_sha = str(source.get("source_sha256") or "")
        configuration_sha = str(source.get("configuration_identity_hash") or "")
        configuration_outcome = str(
            source.get("configuration_outcome") or "SCORED"
        ).upper()
        if (
            not _valid_sha256(source_sha)
            or not _valid_sha256(configuration_sha)
            or configuration_outcome not in {"SCORED", "COMPLETE"}
        ):
            rows.append(
                unsupported_capability_row(
                    study_id="h2_integrated_enrollment_confirmation",
                    cell_id=cell_id,
                    reason=(
                        "exact source row lacks a checksum-bound completed "
                        "configuration identity"
                    ),
                    axes=axes,
                    source_bindings=source_bindings,
                )
            )
            continue
        metric_names = (
            "fpir",
            "dir_rank1",
            "wrong_known_rate",
            "unknown_rejection",
            "false_known_rate",
            "known_open_set_accuracy",
            "top1_accuracy",
            "valid_rate",
            "mean_actual_enrollment_audio_sec",
            "stored_templates_per_speaker",
            "storage_bytes_per_speaker_float32",
        )
        metrics = {key: _optional_finite(source.get(key)) for key in metric_names}
        evidence_binding = {
            "source_kind": "exact_enrollment_matrix_row",
            "configuration_id": source.get("configuration_id"),
            "configuration_identity_hash": source.get("configuration_identity_hash"),
            "source_table": source.get("source_table"),
            "source_sha256": source.get("source_sha256"),
        }
        measured = measured_capability_row(
            study_id="h2_integrated_enrollment_confirmation",
            cell_id=cell_id,
            axes=axes,
            source_bindings=(*source_bindings, evidence_binding),
            metrics=metrics,
        )
        measured.update(metrics)
        measured["biometric_vectors_written"] = False
        rebound = dict(measured)
        rebound.pop("outcome_sha256", None)
        measured["outcome_sha256"] = canonical_sha256(rebound)
        rows.append(measured)
    return tuple(rows)


def _enrollment_axis_value(row: Mapping[str, object], key: str) -> object:
    aliases = {
        "utterances": ("utterances", "enrollment_utterance_count", "enrollment_count"),
        "total_duration_sec": (
            "total_duration_sec",
            "enrollment_total_duration_sec",
            "enrollment_target_audio_sec",
        ),
        "sessions": ("sessions", "session_condition", "enrollment_sessions"),
        "aggregation": (
            "aggregation",
            "integrated_aggregation",
            "aggregation_method",
        ),
        "quality_filter": ("quality_filter", "enrollment_quality_filter"),
    }
    for alias in aliases[key]:
        value = row.get(alias)
        if value is None or value == "":
            continue
        if key == "utterances":
            return int(float(value))
        if key == "total_duration_sec":
            return float(value)
        if key == "sessions":
            normalized = str(value).strip().casefold()
            return {"single_session": "single", "varied_sessions": "varied"}.get(
                normalized, normalized
            )
        if key == "aggregation":
            normalized = str(value).strip().casefold()
            return {
                "normalized_mean": "normalized_mean",
                "multi_template_max": "frozen_redim_multi_template",
                "frozen_redim_multi_template": "frozen_redim_multi_template",
            }.get(normalized, normalized)
        if key == "quality_filter":
            normalized = str(value).strip().casefold()
            return {
                "none": "blind_accept",
                "blind": "blind_accept",
                "quality_controlled": "quality_filtered",
                "quality_filtering": "quality_filtered",
            }.get(normalized, normalized)
    return None


def _optional_finite(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value.casefold()
    )


def _evidence_path(paths: ProgramPaths, raw: str) -> Path:
    path = Path(raw)
    resolved = (
        path.resolve()
        if path.is_absolute()
        else (paths.evaluation_root / path).resolve()
    )
    if not resolved.is_file():
        raise H2ProgramError(f"historical evidence file is missing: {resolved}")
    return resolved


def _result_metric_values(root: Path) -> dict[str, float]:
    result: dict[str, float] = {}
    for view in ("asr", "diarization", "identity", "streaming", "resources"):
        path = root / "metrics" / f"{view}.json"
        document = read_json(path)
        subviews = document.get("subviews")
        if not isinstance(subviews, Mapping):
            continue
        for subview_id in sorted(map(str, subviews)):
            subview = subviews[subview_id]
            if not isinstance(subview, Mapping):
                continue
            metrics = subview.get("metrics")
            if not isinstance(metrics, Mapping):
                continue
            for metric_id, raw in sorted(metrics.items()):
                if metric_id in result or not isinstance(raw, Mapping):
                    continue
                value = raw.get("value")
                if (
                    raw.get("status") == "computed"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(float(value))
                ):
                    result[str(metric_id)] = float(value)
    return result


def _phase1_axis_evidence(
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    integration_tuning: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    decisions = state.get("axis_selections")
    if not isinstance(decisions, Mapping):
        raise H2ProgramError("phase-1 boundary/overlap selections are missing")
    specs = {
        "boundary_correction": "boundary_correction_ms",
        "overlap_policy": "overlap_policy",
    }
    rows: list[dict[str, object]] = []
    for decision_id, axis in specs.items():
        decision = decisions.get(decision_id)
        if not isinstance(decision, Mapping):
            raise H2ProgramError(f"phase-1 selection is missing: {decision_id}")
        decision_path = Path(str(decision.get("decision_path") or ""))
        expected_sha = str(decision.get("decision_sha256") or "")
        if not decision_path.is_file() or sha256_file(decision_path) != expected_sha:
            raise H2ProgramError(f"phase-1 selection checksum differs: {decision_id}")
        selected = list(map(str, decision.get("selected_candidates") or ()))
        if len(selected) != 1:
            raise H2ProgramError(f"phase-1 selection is not singular: {decision_id}")
        candidate = next(
            (
                item
                for item in jobs
                if item.phase_index == 1 and item.configuration_id == selected[0]
            ),
            None,
        )
        if candidate is None:
            raise H2ProgramError(f"selected phase-1 candidate is absent: {selected[0]}")
        root, identity = _completed_result_root(state, candidate)
        _require_valid_result_tree(root)
        value = candidate.runtime_tuning[axis]
        if integration_tuning.get(axis) != value:
            raise H2ProgramError(f"integration did not materialize selected {axis}")
        rows.append(
            {
                "decision_id": decision_id,
                "axis": axis,
                "selected_candidate": candidate.configuration_id,
                "selected_value": value,
                "source_job_id": candidate.job_id,
                "source_result_sha256": identity,
                "decision_sha256": expected_sha,
                "materialized_in_integration": True,
            }
        )
    return tuple(rows)


def _flatten_per_case_metrics(
    job: H2Job, raw: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    reports = raw.get("reports")
    if not isinstance(reports, Mapping):
        raise H2ProgramError(f"per-case row lacks reports: {job.job_id}")
    rows: list[dict[str, object]] = []
    for category, report in sorted(reports.items()):
        if not isinstance(report, Mapping):
            continue
        metrics = report.get("metrics")
        if not isinstance(metrics, Mapping):
            continue
        for metric_id, metric in sorted(metrics.items()):
            if not isinstance(metric, Mapping):
                continue
            rows.append(
                {
                    "job_id": job.job_id,
                    "pipeline_id": job.pipeline_id,
                    "mode": job.mode,
                    "case_id": str(raw.get("case_id") or ""),
                    "source_key": raw.get("source_key"),
                    "reference_speaker_ids": list(
                        map(str, raw.get("reference_speaker_ids") or ())
                    ),
                    "category": str(category),
                    "metric_id": str(metric_id),
                    "status": metric.get("status"),
                    "value": metric.get("value"),
                    "numerator": metric.get("numerator"),
                    "denominator": metric.get("denominator"),
                }
            )
    return tuple(rows)


_ADDITIVE_BOOTSTRAP_METRICS = frozenset(
    {
        "wrong_known_time_sec",
        "stranger_false_known_time_sec",
        "identity_revision_count",
        "transcript_revision_count",
        "retroactive_correction_count",
    }
)


def _bootstrap_estimator(rows: Sequence[Mapping[str, object]]) -> str:
    if all(
        row.get("numerator") is not None and row.get("denominator") is not None
        for row in rows
    ):
        return "ratio"
    return (
        "sum"
        if str(rows[0].get("metric_id")) in _ADDITIVE_BOOTSTRAP_METRICS
        else "mean"
    )


def _bootstrap_contribution(
    row: Mapping[str, object], *, estimator: str, fraction: float
) -> tuple[float, float]:
    if estimator == "ratio":
        return (
            float(row["numerator"]) * fraction,
            float(row["denominator"]) * fraction,
        )
    if estimator == "sum":
        return float(row["value"]) * fraction, 0.0
    return float(row["value"]) * fraction, fraction


def _estimate_contributions(
    contributions: Sequence[tuple[float, float]], estimator: str
) -> float:
    numerator = sum(value[0] for value in contributions)
    denominator = sum(value[1] for value in contributions)
    if estimator == "sum":
        return numerator
    return numerator / denominator if denominator > 0 else math.nan


def _derived_seed(seed: int, value: str) -> int:
    digest = hashlib.sha256(f"{seed}|{value}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _last_per_cluster(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    latest: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for raw in rows:
        row = dict(raw)
        key = (
            str(row["pipeline_id"]),
            str(row["case_id"]),
            str(row["anonymous_speaker_id"]),
            str(row["gallery_requested_size"]),
        )
        previous = latest.get(key)
        if previous is None or (
            float(row["source_time_sec"]),
            str(row["observation_id"]),
        ) > (float(previous["source_time_sec"]), str(previous["observation_id"])):
            latest[key] = row
    return sorted(
        latest.values(),
        key=lambda row: (
            str(row["pipeline_id"]),
            _gallery_sort_key(str(row["gallery_requested_size"])),
            str(row["case_id"]),
            str(row["anonymous_speaker_id"]),
        ),
    )


def _decision_metrics(
    rows: Sequence[Mapping[str, object]],
    *,
    threshold: float,
    margin: float,
    evidence: float,
    consistency: float,
) -> dict[str, object]:
    known_all = [row for row in rows if row["truth_state"] == "KNOWN"]
    known = [
        row
        for row in known_all
        if str(row.get("reference_enrolled_id")) in row["candidate_raw_cosine_scores"]
    ]
    unknown = [row for row in rows if row["truth_state"] == "UNKNOWN"]
    correct = wrong = rejected_known = 0
    for row in known:
        accepted = _accepts(
            row,
            threshold=threshold,
            margin=margin,
            evidence=evidence,
            consistency=consistency,
        )
        if not accepted:
            rejected_known += 1
        elif str(row["top1_candidate_id"]) == str(row.get("reference_enrolled_id")):
            correct += 1
        else:
            wrong += 1
    false_known = sum(
        _accepts(
            row,
            threshold=threshold,
            margin=margin,
            evidence=evidence,
            consistency=consistency,
        )
        for row in unknown
    )
    unknown_groups = _unknown_speaker_groups(unknown)
    false_known_speakers = sum(
        any(
            _accepts(
                row,
                threshold=threshold,
                margin=margin,
                evidence=evidence,
                consistency=consistency,
            )
            for row in speaker_rows
        )
        for speaker_rows in unknown_groups.values()
    )
    return {
        "selection_known_clusters": len(known),
        "selection_known_clusters_absent_from_gallery": len(known_all) - len(known),
        "selection_unknown_clusters": len(unknown),
        "selection_unknown_speakers": len(unknown_groups),
        "selection_correct_known_clusters": correct,
        "selection_wrong_known_clusters": wrong,
        "selection_rejected_known_clusters": rejected_known,
        "selection_false_known_clusters": false_known,
        "selection_tpir": _ratio(correct, len(known)),
        "selection_dir": _ratio(correct, len(known)),
        "selection_wrong_known_rate": _ratio(wrong, len(known)),
        "selection_fnir": _ratio(rejected_known + wrong, len(known)),
        "selection_stranger_fpir": _ratio(false_known, len(unknown)),
        "selection_false_known_speakers": false_known_speakers,
        "selection_unknown_speaker_fpir": _ratio(
            false_known_speakers, len(unknown_groups)
        ),
        "selection_unknown_rejection": (
            1.0 - false_known / len(unknown) if unknown else None
        ),
    }


def _accepted_fraction(
    rows: Sequence[Mapping[str, object]],
    *,
    threshold: float,
    margin: float,
    evidence: float,
    consistency: float,
    group_unknown_speakers: bool = False,
) -> float | None:
    if not rows:
        return None
    if group_unknown_speakers:
        groups = _unknown_speaker_groups(rows)
        return _ratio(
            sum(
                any(
                    _accepts(
                        row,
                        threshold=threshold,
                        margin=margin,
                        evidence=evidence,
                        consistency=consistency,
                    )
                    for row in values
                )
                for values in groups.values()
            ),
            len(groups),
        )
    return _ratio(
        sum(
            _accepts(
                row,
                threshold=threshold,
                margin=margin,
                evidence=evidence,
                consistency=consistency,
            )
            for row in rows
        ),
        len(rows),
    )


def _accepts(
    row: Mapping[str, object],
    *,
    threshold: float,
    margin: float,
    evidence: float = 0.0,
    consistency: float = -math.inf,
) -> bool:
    return (
        float(row["top1_score"]) >= threshold
        and float(row["top1_top2_margin"]) >= margin
        and float(row["evidence_duration_sec"]) >= evidence
        and float(row["embedding_consistency"]) >= consistency
    )


def _quality_and_margin_passes(
    row: Mapping[str, object], *, margin: float, evidence: float, consistency: float
) -> bool:
    return (
        float(row["top1_top2_margin"]) >= margin
        and float(row["evidence_duration_sec"]) >= evidence
        and float(row["embedding_consistency"]) >= consistency
    )


def _unknown_speaker_groups(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        speaker = str(
            row.get("reference_global_speaker_id")
            or f"case-cluster::{row['case_id']}::{row['anonymous_speaker_id']}"
        )
        groups[speaker].append(row)
    return dict(groups)


def _speaker_conservative_threshold(
    rows: Sequence[Mapping[str, object]],
    *,
    target_fpir: float,
    margin: float,
    evidence: float,
    consistency: float,
) -> tuple[float, int, int]:
    """Choose the least restrictive empirical threshold at/below target FPIR.

    The false-positive unit is a reference stranger speaker.  A fragmented
    stranger counts once and is positive when *any* of their final anonymous
    clusters would be named.  Ties are handled conservatively; targets below
    one empirical speaker step result in zero accepted calibration speakers.
    """

    groups = _unknown_speaker_groups(rows)
    if not groups:
        raise H2ProgramError("speaker-conservative calibration has no strangers")
    eligible_scores = [
        float(row["top1_score"])
        for row in rows
        if _quality_and_margin_passes(
            row, margin=margin, evidence=evidence, consistency=consistency
        )
    ]
    if not eligible_scores:
        all_scores = [float(row["top1_score"]) for row in rows]
        reject_all = math.nextafter(max(all_scores), math.inf)
        if not math.isfinite(reject_all):
            raise H2ProgramError(
                "cannot construct a finite reject-all threshold above calibration scores"
            )
        return reject_all, 0, len(groups)
    candidates = sorted(set(eligible_scores))
    candidates.append(math.nextafter(max(eligible_scores), math.inf))
    allowed = math.floor(float(target_fpir) * len(groups) + 1e-12)
    for threshold in candidates:
        accepted = sum(
            any(
                _accepts(
                    row,
                    threshold=threshold,
                    margin=margin,
                    evidence=evidence,
                    consistency=consistency,
                )
                for row in speaker_rows
            )
            for speaker_rows in groups.values()
        )
        if accepted <= allowed:
            return threshold, accepted, len(groups)
    raise AssertionError("threshold candidate construction failed")


def _zero_false_id_binomial_upper_95(unit_count: int) -> float:
    """One-sided exact 95% binomial upper bound after zero false IDs.

    For ``x=0`` the Clopper-Pearson upper endpoint has the closed form
    ``1 - 0.05 ** (1 / n)``.  It is deliberately reported alongside the
    empirical resolution so a zero observation is never presented as proof of
    a sub-resolution target.
    """

    if unit_count < 1:
        raise ValueError("unit_count must be positive")
    return 1.0 - math.pow(0.05, 1.0 / float(unit_count))


def _unsupported_frontier_row(
    gallery: str,
    target: float,
    margin: float,
    evidence: float,
    consistency: float,
) -> dict[str, object]:
    return {
        "schema_version": POLICY_REPLAY_SCHEMA_VERSION,
        "status": "UNSUPPORTED",
        "reason": "no valid development calibration Unknown clusters after gates",
        "gallery_requested_size": gallery,
        "target_fpir": float(target),
        "score_threshold": None,
        "margin_threshold": float(margin),
        "minimum_evidence_sec": float(evidence),
        "minimum_embedding_consistency": float(consistency),
        "calibration_unknown_clusters": 0,
        "calibration_unknown_speakers": 0,
        "eligible_calibration_unknown_clusters": 0,
        "eligible_calibration_unknown_speakers": 0,
        "accepted_calibration_unknown_speakers": 0,
        "empirical_fpir_resolution": None,
        "target_below_empirical_resolution": None,
        "target_empirically_resolvable": False,
        "target_fpir_observed_at_or_below_target": False,
        "zero_false_id_binomial_upper_95": None,
        "target_fpir_demonstrated": False,
        "target_fpir_claim": "NOT_DEMONSTRATED_NO_CALIBRATION_STRANGERS",
        "selection_rows": 0,
        "development_only_selection": True,
        "evaluation_material_inspected": False,
    }


def _linear_quantile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, float(q))) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _gallery_sort_key(value: str) -> tuple[int, int | str]:
    normalized = str(value).strip().casefold()
    if normalized == "full":
        return (1, math.inf)
    try:
        return (0, int(normalized))
    except ValueError:
        return (2, normalized)


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _finite(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise H2ProgramError(f"{label} is not numeric") from exc
    if not math.isfinite(result):
        raise H2ProgramError(f"{label} is not finite")
    return result


def _metric_or_inf(row: Mapping[str, object], key: str) -> float:
    value = row.get(key)
    return float(value) if value is not None else math.inf


def _metric_or_neg_inf(row: Mapping[str, object], key: str) -> float:
    value = row.get(key)
    return float(value) if value is not None else -math.inf


__all__ = [
    "BOOTSTRAP_REPETITIONS",
    "BOOTSTRAP_SEED",
    "CONSISTENCY_THRESHOLDS",
    "EVIDENCE_DURATIONS",
    "MARGINS",
    "OBSERVATION_SCHEMA_VERSION",
    "OpenSetPolicy",
    "POST_PROMOTION_CONFIGURATION",
    "POST_PROMOTION_JOB_KIND",
    "SCIENCE_JOB_KINDS",
    "TARGET_FPIRS",
    "apply_frozen_integration_assignment",
    "build_embedding_clustering_coverage",
    "build_integrated_enrollment_matrix",
    "build_memory_level_coverage",
    "build_policy_frontier",
    "execute_science_job",
    "hierarchical_speaker_case_bootstrap",
    "hubness_rows",
    "load_development_observations",
    "measured_capability_row",
    "normalize_observation",
    "select_balanced_policy",
    "selected_runtime_payload",
    "simulate_short_turn_events",
    "unsupported_capability_row",
]
