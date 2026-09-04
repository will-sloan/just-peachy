"""Development-only open-set calibration and immutable policy registries.

This module deliberately contains no inference.  It consumes raw maximum-gallery
score observations emitted by the full-pipeline runtime, reproduces the frozen
Hybrid Product V2 score-plus-margin calibration method, and produces a registry
that a later runtime/replay pass can load.  Evaluation observations are rejected
at the input boundary.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml

from app.full_pipeline.identity import FROZEN_IDENTITY_POLICIES

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import (
    EVALUATION_ROOT,
    MATRIX_PATH,
    RUNTIME_CONFIG_PATH,
    matrix,
)


POLICY_REGISTRY_SCHEMA_VERSION = "full-pipeline-development-policy-registry.v1"
OBSERVATION_SCHEMA_VERSION = "full-pipeline-challenger-score-observation.v1"
CALIBRATION_METHOD = "maximum_gallery_score_with_top1_top2_margin"
ACTIVE_OPERATING_MODE = "BALANCED"
OPERATING_MODES: dict[str, dict[str, float]] = {
    "STRICT": {"target_fpir": 0.005, "margin_threshold": 0.04},
    "BALANCED": {"target_fpir": 0.01, "margin_threshold": 0.03},
    "RESPONSIVE": {"target_fpir": 0.02, "margin_threshold": 0.01},
    "DIAGNOSTIC_5PCT": {"target_fpir": 0.05, "margin_threshold": 0.0},
}
FROZEN_ANCHOR_LABELS = frozenset({"H2", "H4", "H5"})
FROZEN_HYBRID_PROTOCOL_ID = "hybrid_speaker_attribution_product_v2_a68cc1ac26aa"
FROZEN_HYBRID_SELECTION_SHA256 = (
    "2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a"
)


class DevelopmentPolicyError(RuntimeError):
    """A scientific calibration/freeze invariant was violated."""


def development_role(case_id: str) -> str:
    """Reproduce Product V2's frozen deterministic 20% calibration assignment."""

    value = str(case_id).strip()
    if not value:
        raise ValueError("case_id must be non-empty")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return "calibration" if int(digest[:8], 16) % 5 == 0 else "selection"


def challenger_pipeline_ids() -> tuple[str, ...]:
    """Return the exact twelve non-anchor AO/AG pipelines."""

    resolved = matrix()
    return tuple(
        pipeline_id
        for pipeline_id in resolved.pipeline_ids
        if resolved.resolve(pipeline_id).hybrid_label not in FROZEN_ANCHOR_LABELS
    )


def select_development_calibration_cases(
    cases: Iterable[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Select the frozen ALL_UNKNOWN calibration scope without model work.

    The upstream source-case identity is used for the Product V2 20% assignment;
    the generated full-pipeline wrapper ID never repartitions the source data.
    """

    selected: list[dict[str, object]] = []
    for raw in cases:
        row = dict(raw)
        split = str(row.get("split") or row.get("partition") or "")
        if split != "development":
            raise DevelopmentPolicyError(
                "calibration case selector accepts development rows only"
            )
        if not row.get("gallery_enrolled_ids"):
            continue
        overlay = str(row.get("overlay_id") or "")
        if overlay != "ALL_UNKNOWN":
            continue
        source_case_id = str(row.get("source_case_id") or "")
        if not source_case_id:
            raise DevelopmentPolicyError("calibration case lacks source_case_id")
        role = development_role(source_case_id)
        if role != "calibration":
            continue
        gallery_size = int(row.get("gallery_size") or 0)
        if gallery_size != len(row["gallery_enrolled_ids"]):
            raise DevelopmentPolicyError("case gallery size/list mismatch")
        selected.append(
            {
                **row,
                "calibration_role": role,
                "gallery_requested_size": _normalize_gallery_request(
                    row.get("gallery_requested_size") or gallery_size
                ),
            }
        )
    return tuple(
        sorted(
            selected,
            key=lambda row: (
                _gallery_request_sort_key(str(row["gallery_requested_size"])),
                str(row.get("source_key") or ""),
                str(row.get("protocol_case_id") or row.get("case_id") or ""),
            ),
        )
    )


def build_development_policy_registry(
    observations: Iterable[Mapping[str, object]],
    *,
    protocol_id: str,
    development_identity_sha256: str,
    expected_pipeline_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Calibrate exact-pipeline, exact-gallery policies using development only.

    One final valid unknown observation is retained per
    ``pipeline/case/anonymous-cluster/gallery``.  Repeated cumulative checkpoints
    therefore do not inflate the calibration sample count.  Thresholds reproduce
    Hybrid Product V2: for each fixed margin, take the linear
    ``1 - target_fpir`` quantile of unknown Top-1 maximum-gallery scores whose
    Top-1/Top-2 margin passes.  If no row passes the margin, all unknown Top-1
    scores are used, matching the prior study's explicit fallback.
    """

    protocol = str(protocol_id).strip()
    if not protocol:
        raise ValueError("protocol_id must be non-empty")
    development_hash = _sha256(development_identity_sha256, "development identity")
    expected = tuple(expected_pipeline_ids or challenger_pipeline_ids())
    if len(expected) != len(set(expected)):
        raise ValueError("expected_pipeline_ids contains duplicates")
    allowed = set(challenger_pipeline_ids())
    if set(expected) - allowed:
        raise DevelopmentPolicyError(
            "anchor or unknown pipeline supplied for challenger calibration: "
            + ", ".join(sorted(set(expected) - allowed))
        )

    selected = _select_final_unknown_observations(
        observations,
        expected,
        protocol_id=protocol,
        development_identity_sha256=development_hash,
    )
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in selected:
        grouped[
            (str(row["pipeline_id"]), str(row["gallery_requested_size"]))
        ].append(row)

    missing = [pipeline_id for pipeline_id in expected if not any(key[0] == pipeline_id for key in grouped)]
    if missing:
        raise DevelopmentPolicyError(
            "no valid development calibration observations for exact pipeline(s): "
            + ", ".join(missing)
        )

    resolved = matrix()
    entries: list[dict[str, object]] = []
    for pipeline_id in expected:
        selection = resolved.resolve(pipeline_id)
        gallery_rows: list[dict[str, object]] = []
        for (_, gallery_request), rows in sorted(
            (item for item in grouped.items() if item[0][0] == pipeline_id),
            key=lambda item: _gallery_request_sort_key(item[0][1]),
        ):
            mode_rows = [
                _calibrate_mode(rows, mode, settings)
                for mode, settings in OPERATING_MODES.items()
            ]
            gallery_rows.append(
                {
                    "gallery_requested_size": gallery_request,
                    "observed_realized_gallery_sizes": sorted(
                        {int(row["gallery_size"]) for row in rows}
                    ),
                    "calibration_unknown_clusters": len(rows),
                    "smallest_empirical_fpir_step": 1.0 / len(rows),
                    "operating_modes": mode_rows,
                }
            )

        input_rows = [
            row
            for row in selected
            if str(row["pipeline_id"]) == pipeline_id
        ]
        input_identity = sha256_bytes(canonical_json_bytes(input_rows))
        base = {
            "pipeline_id": pipeline_id,
            "hybrid_label": selection.hybrid_label,
            "identity_backend_id": str(selection.identity["backend_id"]),
            "enrollment_policy_id": str(selection.enrollment_policy["policy_id"]),
            "enrollment_policy_path": str(selection.enrollment_policy["path"]),
            "enrollment_policy_sha256": str(selection.enrollment_policy["sha256"]),
            "calibration_partition": "development",
            "calibration_input_sha256": input_identity,
            "calibration_unknown_clusters": len(input_rows),
            "calibration_method": CALIBRATION_METHOD,
            "active_operating_mode": ACTIVE_OPERATING_MODE,
            "thresholds_by_gallery_request": gallery_rows,
            "minimum_evidence_sec": 2.0,
            "minimum_embedding_consistency": 0.35,
            "consecutive_passes_to_confirm": 2,
            "hysteresis": 0.02,
            "identity_expiry_sec": 120.0,
            "overlap_policy": "exclude_predicted_overlap_for_identity_primary_include_diagnostic",
            "cluster_evidence_aggregation": "duration_weighted_normalized_mean",
            "tentative_visible": True,
            "evaluation_material_inspected": False,
            "threshold_shared_with_another_pipeline": False,
        }
        calibration_identity = sha256_bytes(canonical_json_bytes(base))
        entries.append(
            {
                **base,
                "policy_id": (
                    "full_pipeline_open_set_decision.development.v1:"
                    f"{pipeline_id}:{calibration_identity[:12]}"
                ),
                "calibration_identity_sha256": calibration_identity,
            }
        )

    registry_core = {
        "schema_version": POLICY_REGISTRY_SCHEMA_VERSION,
        "status": "FROZEN_DEVELOPMENT_ONLY",
        "protocol_id": protocol,
        "development_identity_sha256": development_hash,
        "matrix_sha256": sha256_file(MATRIX_PATH),
        "runtime_config_sha256": sha256_file(RUNTIME_CONFIG_PATH),
        "calibration_partition": "development",
        "evaluation_material_inspected": False,
        "evaluation_recalibration_allowed": False,
        "calibration_method": CALIBRATION_METHOD,
        "operating_modes": OPERATING_MODES,
        "active_operating_mode": ACTIVE_OPERATING_MODE,
        "pipeline_scope": "exact_pipeline_and_frozen_gallery_request",
        "cross_backend_threshold_sharing": False,
        "entries": entries,
    }
    return {
        **registry_core,
        "registry_identity_sha256": sha256_bytes(canonical_json_bytes(registry_core)),
    }


def write_development_policy_registry(
    path: Path, registry: Mapping[str, object]
) -> Path:
    """Validate and atomically publish one immutable policy registry."""

    validate_development_policy_registry(registry)
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"development policy registry is immutable: {target}")
    return write_json_atomic(target, dict(registry))


def validate_development_policy_registry(
    registry: Mapping[str, object],
) -> None:
    """Reject evaluation leakage, anchor mutation, or cross-pipeline sharing."""

    if registry.get("schema_version") != POLICY_REGISTRY_SCHEMA_VERSION:
        raise DevelopmentPolicyError("unexpected development policy registry schema")
    if registry.get("calibration_partition") != "development":
        raise DevelopmentPolicyError("policy registry is not development-only")
    if registry.get("evaluation_material_inspected") is not False:
        raise DevelopmentPolicyError("evaluation material may not enter calibration")
    if registry.get("evaluation_recalibration_allowed") is not False:
        raise DevelopmentPolicyError("evaluation recalibration must be disabled")
    if registry.get("cross_backend_threshold_sharing") is not False:
        raise DevelopmentPolicyError("cross-backend threshold sharing is forbidden")
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        raise DevelopmentPolicyError("policy registry entries must be non-empty")
    seen: set[str] = set()
    identities: set[str] = set()
    resolved = matrix()
    for raw in entries:
        if not isinstance(raw, Mapping):
            raise DevelopmentPolicyError("policy registry entry must be an object")
        pipeline_id = str(raw.get("pipeline_id") or "")
        if pipeline_id in seen:
            raise DevelopmentPolicyError(f"duplicate policy entry: {pipeline_id}")
        seen.add(pipeline_id)
        selection = resolved.resolve(pipeline_id)
        if selection.hybrid_label in FROZEN_ANCHOR_LABELS:
            raise DevelopmentPolicyError(f"anchor cannot appear as challenger: {pipeline_id}")
        if raw.get("threshold_shared_with_another_pipeline") is not False:
            raise DevelopmentPolicyError(f"shared threshold forbidden: {pipeline_id}")
        identity = _sha256(raw.get("calibration_identity_sha256"), "calibration identity")
        if identity in identities:
            raise DevelopmentPolicyError(
                "calibration identity reused across exact pipelines"
            )
        identities.add(identity)
        if str(raw.get("identity_backend_id")) != str(selection.identity["backend_id"]):
            raise DevelopmentPolicyError(f"backend mismatch: {pipeline_id}")
        if str(raw.get("enrollment_policy_sha256")) != str(
            selection.enrollment_policy["sha256"]
        ):
            raise DevelopmentPolicyError(f"enrollment policy mismatch: {pipeline_id}")
        schedules = raw.get("thresholds_by_gallery_request")
        if not isinstance(schedules, list) or not schedules:
            raise DevelopmentPolicyError(f"threshold schedule missing: {pipeline_id}")
    core = {key: value for key, value in registry.items() if key != "registry_identity_sha256"}
    expected_identity = sha256_bytes(canonical_json_bytes(core))
    if registry.get("registry_identity_sha256") != expected_identity:
        raise DevelopmentPolicyError("registry identity checksum mismatch")


def resolve_decision_policy_contract(
    pipeline_id: str,
    *,
    realized_gallery_size: int,
    gallery_requested_size: str | int | None = None,
    registry: Mapping[str, object] | None = None,
    operating_mode: str = ACTIVE_OPERATING_MODE,
) -> dict[str, object]:
    """Resolve the exact decision artifact the coordinator must publish.

    Frozen anchors deliberately retain the inherited Product V2 BALANCED,
    gallery-size-10 scalar at every realized gallery size. Challengers require
    an exact-pipeline, frozen requested-gallery development registry entry. The returned
    ``decision_policy_sha256`` is never an enrollment-policy hash.
    """

    if realized_gallery_size < 1:
        raise ValueError("realized_gallery_size must be >= 1")
    selection = matrix().resolve(pipeline_id)
    if selection.hybrid_label in FROZEN_ANCHOR_LABELS:
        policy = FROZEN_IDENTITY_POLICIES[selection.hybrid_label]
        return {
            "policy_id": policy.policy_id,
            "decision_policy_sha256": FROZEN_HYBRID_SELECTION_SHA256,
            "calibration_protocol_id": FROZEN_HYBRID_PROTOCOL_ID,
            "calibration_result_sha256": FROZEN_HYBRID_SELECTION_SHA256,
            "calibration_partition": "development",
            "operating_mode": ACTIVE_OPERATING_MODE,
            "target_fpir": 0.01,
            "score_threshold": policy.score_threshold,
            "margin_threshold": policy.margin_threshold,
            "minimum_evidence_sec": policy.minimum_evidence_sec,
            "realized_gallery_size": realized_gallery_size,
            "threshold_scope": (
                "frozen_product_v2_balanced_gallery10_scalar_reused_for_all_galleries"
            ),
            "frozen_anchor": True,
            "evaluation_recalibration_allowed": False,
        }
    if registry is None:
        raise DevelopmentPolicyError(
            f"challenger {pipeline_id} requires a frozen development registry"
        )
    validate_development_policy_registry(registry)
    raw_entries = registry["entries"]
    assert isinstance(raw_entries, list)
    matches = [
        row
        for row in raw_entries
        if isinstance(row, Mapping) and row.get("pipeline_id") == pipeline_id
    ]
    if len(matches) != 1:
        raise DevelopmentPolicyError(
            f"expected exactly one challenger policy for {pipeline_id}"
        )
    entry = matches[0]
    raw_schedules = entry["thresholds_by_gallery_request"]
    assert isinstance(raw_schedules, list)
    requested = _normalize_gallery_request(
        gallery_requested_size
        if gallery_requested_size is not None
        else realized_gallery_size
    )
    schedules = [
        row
        for row in raw_schedules
        if isinstance(row, Mapping)
        and str(row.get("gallery_requested_size")) == requested
    ]
    if len(schedules) != 1:
        raise DevelopmentPolicyError(
            f"no frozen gallery-request {requested} policy for {pipeline_id}"
        )
    modes = schedules[0]["operating_modes"]
    assert isinstance(modes, list)
    mode_rows = [
        row
        for row in modes
        if isinstance(row, Mapping) and row.get("operating_mode") == operating_mode
    ]
    if len(mode_rows) != 1:
        raise DevelopmentPolicyError(
            f"operating mode {operating_mode} unavailable for {pipeline_id}"
        )
    mode = mode_rows[0]
    policy_sha = str(entry["calibration_identity_sha256"])
    return {
        "policy_id": str(entry["policy_id"]),
        "decision_policy_sha256": policy_sha,
        "policy_registry_sha256": str(registry["registry_identity_sha256"]),
        "calibration_protocol_id": str(registry["protocol_id"]),
        "calibration_result_sha256": policy_sha,
        "calibration_partition": "development",
        "operating_mode": operating_mode,
        "target_fpir": float(mode["target_fpir"]),
        "score_threshold": float(mode["score_threshold"]),
        "margin_threshold": float(mode["margin_threshold"]),
        "minimum_evidence_sec": float(entry["minimum_evidence_sec"]),
        "realized_gallery_size": realized_gallery_size,
        "gallery_requested_size": requested,
        "threshold_scope": "exact_pipeline_and_frozen_gallery_request",
        "frozen_anchor": False,
        "evaluation_recalibration_allowed": False,
    }


def audit_frozen_anchor_policies(
    *, evaluation_root: Path = EVALUATION_ROOT
) -> dict[str, object]:
    """Cross-check H2/H4/H5 against their authoritative frozen source."""

    root = Path(evaluation_root).resolve()
    matrix_doc = _yaml(root / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml")
    runtime_doc = _yaml(root / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml")
    source_path = root / str(
        matrix_doc["source_anchors"]["frozen_hybrid_development_selection"]["path"]
    )
    source_expected_sha = str(
        matrix_doc["source_anchors"]["frozen_hybrid_development_selection"]["sha256"]
    )
    source = _yaml(source_path)
    source_by_label = {
        str(row["hybrid_combination_id"]): row
        for row in source.get("selected_finalists", [])
        if isinstance(row, Mapping)
    }
    errors: list[str] = []
    if sha256_file(source_path) != source_expected_sha:
        errors.append("frozen hybrid development selection checksum changed")
    rows = [row for row in matrix_doc.get("pipelines", []) if isinstance(row, Mapping)]
    runtime_thresholds = runtime_doc["identity"]["frozen_thresholds"]
    for label in sorted(FROZEN_ANCHOR_LABELS):
        source_row = source_by_label.get(label)
        code_policy = FROZEN_IDENTITY_POLICIES.get(label)
        if source_row is None or code_policy is None:
            errors.append(f"{label}: frozen source/code policy missing")
            continue
        expected_threshold = float(source_row["score_threshold"])
        expected_common = {
            "margin_threshold": float(source_row["margin_threshold"]),
            "minimum_evidence_sec": float(source_row["minimum_evidence_sec"]),
            "hysteresis": float(source_row["confirmation"]["hysteresis"]),
            "identity_expiry_sec": float(source_row["expiry_session_policy"]["expiry_sec"]),
            "consecutive_passes_to_confirm": int(source_row["confirmation"]["consecutive_passes"]),
            "minimum_embedding_consistency": float(source_row["quality_gate"]["minimum_embedding_consistency"]),
            "tentative_visible": bool(source_row["confirmation"]["tentative_visible"]),
        }
        observed_common = {
            key: getattr(code_policy, key) for key in expected_common
        }
        if float(code_policy.score_threshold or math.nan) != expected_threshold:
            errors.append(f"{label}: code threshold differs from frozen source")
        if observed_common != expected_common:
            errors.append(f"{label}: common identity behavior differs from frozen source")
        if float(runtime_thresholds[label]) != expected_threshold:
            errors.append(f"{label}: runtime threshold differs from frozen source")
        anchor_rows = [row for row in rows if row.get("hybrid_label") == label]
        if len(anchor_rows) != 2:
            errors.append(f"{label}: expected AO and AG matrix rows")
        for row in anchor_rows:
            if row.get("frozen_anchor_derived") is not True:
                errors.append(f"{label}: matrix anchor flag missing")
            if float(row.get("frozen_anchor_score_threshold", math.nan)) != expected_threshold:
                errors.append(f"{label}: matrix threshold differs from frozen source")
        policy_alias = str(source_row["identity_backend_id"])
        enrollment_entries = matrix_doc["policies"]["enrollment"]
        matches = [
            value
            for value in enrollment_entries.values()
            if isinstance(value, Mapping)
            and _yaml(root / str(value["path"])).get("identity_backend_id") == policy_alias
        ]
        if len(matches) != 1:
            errors.append(f"{label}: enrollment policy mapping is ambiguous")
        elif (
            str(matches[0]["sha256"])
            != str(source_row["scientific_enrollment_policy_sha256"])
        ):
            errors.append(f"{label}: enrollment policy hash differs from frozen source")
    return {
        "schema_version": "full-pipeline-frozen-anchor-audit.v1",
        "status": "PASS" if not errors else "FAIL",
        "frozen_source_path": source_path.relative_to(root).as_posix(),
        "frozen_source_sha256": sha256_file(source_path),
        "anchors_checked": sorted(FROZEN_ANCHOR_LABELS),
        "matrix_rows_checked": 6,
        "settings_checked": [
            "enrollment aggregation",
            "score threshold",
            "Top-1/Top-2 margin",
            "minimum evidence",
            "embedding consistency",
            "overlap policy",
            "confirmation count",
            "hysteresis",
            "tentative visibility",
            "identity expiry",
        ],
        "errors": errors,
    }


def _select_final_unknown_observations(
    observations: Iterable[Mapping[str, object]],
    expected: Sequence[str],
    *,
    protocol_id: str,
    development_identity_sha256: str,
) -> list[dict[str, object]]:
    expected_set = set(expected)
    latest: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for raw in observations:
        row = _normalize_observation(
            raw,
            protocol_id=protocol_id,
            development_identity_sha256=development_identity_sha256,
        )
        pipeline_id = str(row["pipeline_id"])
        if pipeline_id not in expected_set:
            continue
        if row["truth_state"] != "UNKNOWN":
            continue
        if row["calibration_role"] != "calibration":
            continue
        if row["status"] != "VALID" or bool(row["predicted_overlap"]):
            continue
        if float(row["evidence_duration_sec"]) < 2.0:
            continue
        if float(row["embedding_consistency"]) < 0.35:
            continue
        key = (
            pipeline_id,
            str(row["case_id"]),
            str(row["anonymous_speaker_id"]),
            str(row["gallery_requested_size"]),
        )
        previous = latest.get(key)
        if previous is None or (
            float(row["source_time_sec"]), str(row["observation_id"])
        ) > (
            float(previous["source_time_sec"]), str(previous["observation_id"])
        ):
            latest[key] = row
    return sorted(
        latest.values(),
        key=lambda row: (
            str(row["pipeline_id"]),
            _gallery_request_sort_key(str(row["gallery_requested_size"])),
            str(row["case_id"]),
            str(row["anonymous_speaker_id"]),
        ),
    )


def _normalize_observation(
    raw: Mapping[str, object],
    *,
    protocol_id: str,
    development_identity_sha256: str,
) -> dict[str, object]:
    row = dict(raw)
    if row.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
        raise DevelopmentPolicyError("unexpected raw challenger score schema")
    if str(row.get("split") or row.get("partition")) != "development":
        raise DevelopmentPolicyError("evaluation/non-development score row rejected")
    if row.get("evaluation_material_inspected") is not False:
        raise DevelopmentPolicyError("score row lacks explicit no-evaluation attestation")
    required_text = (
        "pipeline_id",
        "hybrid_label",
        "identity_backend_id",
        "case_id",
        "anonymous_speaker_id",
        "observation_id",
        "truth_state",
        "calibration_role",
        "status",
        "top1_candidate_id",
        "overlay_condition",
        "gallery_requested_size",
    )
    for key in required_text:
        if not str(row.get(key) or "").strip():
            raise DevelopmentPolicyError(f"score row missing {key}")
    if str(row["truth_state"]) not in {"KNOWN", "UNKNOWN"}:
        raise DevelopmentPolicyError("truth_state must be KNOWN or UNKNOWN")
    if str(row["calibration_role"]) not in {"calibration", "selection"}:
        raise DevelopmentPolicyError("invalid development calibration role")
    if str(row.get("protocol_id")) != protocol_id:
        raise DevelopmentPolicyError("score row protocol identity mismatch")
    if _sha256(
        row.get("development_protocol_sha256"), "row development protocol"
    ) != development_identity_sha256:
        raise DevelopmentPolicyError("score row development identity mismatch")
    _sha256(row.get("gallery_identity_sha256"), "gallery identity")
    selection = matrix().resolve(str(row["pipeline_id"]))
    if str(row["hybrid_label"]) != selection.hybrid_label:
        raise DevelopmentPolicyError("score row hybrid label mismatch")
    if str(row["identity_backend_id"]) != str(selection.identity["backend_id"]):
        raise DevelopmentPolicyError("score row backend mismatch")
    if _sha256(
        row.get("enrollment_policy_sha256"), "enrollment policy"
    ) != str(selection.enrollment_policy["sha256"]):
        raise DevelopmentPolicyError("score row enrollment policy mismatch")
    for key in (
        "source_time_sec",
        "evidence_duration_sec",
        "embedding_consistency",
        "top1_score",
    ):
        value = _finite(row.get(key), key)
        row[key] = value
    top2 = row.get("top2_score")
    row["top2_score"] = -1.0 if top2 is None else _finite(top2, "top2_score")
    gallery_size = int(row.get("gallery_size") or 0)
    if gallery_size < 1:
        raise DevelopmentPolicyError("gallery_size must be >= 1")
    row["gallery_size"] = gallery_size
    row["gallery_requested_size"] = _normalize_gallery_request(
        row["gallery_requested_size"]
    )
    candidate_count = int(row.get("candidate_count") or 0)
    if candidate_count != gallery_size:
        raise DevelopmentPolicyError(
            "maximum-gallery calibration requires one score per gallery identity"
        )
    row["candidate_count"] = candidate_count
    if gallery_size > 1 and raw.get("top2_score") is None:
        raise DevelopmentPolicyError("Top-2 score is required when gallery size > 1")
    if row["calibration_role"] == "calibration" and row["truth_state"] == "UNKNOWN":
        if row["overlay_condition"] != "ALL_UNKNOWN":
            raise DevelopmentPolicyError(
                "frozen calibration methodology requires ALL_UNKNOWN overlays"
            )
    row["predicted_overlap"] = bool(row.get("predicted_overlap"))
    row["top1_top2_margin"] = float(row["top1_score"]) - float(row["top2_score"])
    return row


def _calibrate_mode(
    rows: Sequence[Mapping[str, object]],
    mode: str,
    settings: Mapping[str, float],
) -> dict[str, object]:
    margin = float(settings["margin_threshold"])
    target = float(settings["target_fpir"])
    all_scores = [float(row["top1_score"]) for row in rows]
    eligible = [
        float(row["top1_score"])
        for row in rows
        if float(row["top1_top2_margin"]) >= margin
    ]
    calibration_scores = eligible or all_scores
    threshold = _linear_quantile(calibration_scores, 1.0 - target)
    false_positive_count = sum(
        float(row["top1_score"]) >= threshold
        and float(row["top1_top2_margin"]) >= margin
        for row in rows
    )
    return {
        "operating_mode": mode,
        "target_fpir": target,
        "score_threshold": threshold,
        "margin_threshold": margin,
        "calibration_unknown_clusters": len(rows),
        "margin_eligible_unknown_clusters": len(eligible),
        "margin_empty_fallback_used": not bool(eligible),
        "observed_calibration_fpir": false_positive_count / len(rows),
        "target_empirically_resolvable": len(rows) >= math.ceil(1.0 / target),
    }


def _linear_quantile(values: Sequence[float], q: float) -> float:
    if not values:
        raise DevelopmentPolicyError("cannot calibrate an empty score distribution")
    if not 0.0 <= q <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _normalize_gallery_request(value: object) -> str:
    text = str(value).strip().casefold()
    if text and all(character.isalnum() or character in {"_", "-"} for character in text):
        if not text.isdigit():
            return text
    try:
        number = int(text)
    except ValueError as exc:
        raise DevelopmentPolicyError(
            f"invalid frozen gallery request: {value}"
        ) from exc
    if number < 1:
        raise DevelopmentPolicyError("gallery request must be >= 1")
    return str(number)


def _gallery_request_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise DevelopmentPolicyError(f"YAML root is not an object: {path}")
    return value


def _finite(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DevelopmentPolicyError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise DevelopmentPolicyError(f"{label} must be finite")
    return result


def _sha256(value: object, label: str) -> str:
    text = str(value or "").casefold()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 hex digest")
    return text
