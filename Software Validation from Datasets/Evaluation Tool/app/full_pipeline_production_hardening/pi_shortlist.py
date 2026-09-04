"""Additive Prompt-7 Raspberry Pi candidate-shortlist handoff.

This module consumes frozen Prompt-5/6 evidence and the existing Prompt-7
desktop selection.  It does not retune, rerank, or change a desktop role.  Its
only decision is which two to four already-predeclared extended-set pipelines
remain worth measuring on Linux ARM64 hardware.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from app.full_pipeline.matrix import FullPipelineMatrix, PipelineSelection
from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES,
    FUTURE_LINUX_ARM64_VALIDATION,
    FUTURE_TARGET_HARDWARE_TESTS,
    RASPBERRY_PI_CANDIDATE_FIELDS,
    DeploymentEvidenceError,
    evidence,
    load_deployment_steering,
    steering_ref,
    unknown_evidence,
    validate_deployment_evidence_document,
    validate_evidence,
)

from . import (
    MATRIX_PATH,
    PI_DEPLOYMENT_STEERING_SHA256,
    PI_SHORTLIST_SCHEMA,
    RUNTIME_PATH,
    scope_fields,
)
from .io import HardeningError, artifact_ref, ensure_c, read_csv, read_json, sha256_file


_P5_SCHEMA = "full-pipeline-all18-deployment-evidence.v1"
_P6_SCHEMA = "full-pipeline-extended-deployment-evidence.v1"
_P5_MERGE_ORDER = (
    "all18_finalist_summary.csv",
    "all18_asr.csv",
    "all18_diarization.csv",
    "all18_identity.csv",
    "all18_speaker_attributed_transcript.csv",
    "all18_streaming.csv",
    "all18_resources.csv",
)
_METRICS = {
    "wer": (("wer", "word_error_rate"), "ratio"),
    "der": (("der", "diarization_error_rate"), "ratio"),
    "wrong_known": (
        ("wrong_known_time_sec", "wrong_known_speaker_time_sec"),
        "seconds",
    ),
    "stranger_false_known": (
        ("stranger_false_known_time_sec", "stranger_false_known_sec"),
        "seconds",
    ),
    "rtf": (("total_rtf", "realtime_factor", "rtf"), "ratio"),
}
_LATENCY_METRICS = {
    "first_readable_partial": (
        ("first_readable_partial_latency_sec", "first_readable_text_latency_sec"),
        "seconds",
    ),
    "stable_transcript": (
        ("stable_prefix_latency_sec", "stable_transcript_latency_sec"),
        "seconds",
    ),
    "stable_correct_name": (
        (
            "stable_name_latency_sec",
            "time_to_confirmed_known_name_sec",
            "stable_correct_name_latency_sec",
        ),
        "seconds",
    ),
}
_FAILURE_ALIASES = (
    "explicit_failed_job_count",
    "failure_count",
    "output_failure_count",
)


def build_pi_shortlist(
    *,
    authorization: Mapping[str, object],
    desktop_selection: Mapping[str, object],
    evidence_files: Mapping[str, Path],
    desktop_roles_source: Path | str,
) -> dict[str, object]:
    """Build and immediately revalidate the exact Prompt-7 shortlist."""

    inputs = _validated_inputs(authorization)
    pool = _candidate_pool(authorization, desktop_selection)
    merged, sources = _merge_prompt5_rows(evidence_files)
    if tuple(merged) != tuple(
        FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH).pipeline_ids
    ):
        raise HardeningError(
            "Prompt-5 metric evidence is not exact all-18 matrix order"
        )
    selection_rows = _selection_rows(desktop_selection, pool)
    credible = [
        pipeline_id
        for pipeline_id in pool
        if _scientifically_credible(selection_rows[pipeline_id], merged[pipeline_id])
    ]
    roles = _desktop_roles(desktop_selection)
    primary = roles["PRIMARY"]
    if primary not in credible:
        raise HardeningError(
            "desktop PRIMARY lacks complete safety/reliability evidence for Pi handoff"
        )
    if len(credible) < 2:
        raise HardeningError(
            "fewer than two scientifically credible predeclared Pi candidates"
        )

    p6_rows = _deployment_rows(inputs["prompt6_document"], pool, "Prompt-6")
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    selected_ids, reasons, policy_audit = _choose_candidates(
        pool=pool,
        credible=credible,
        primary=primary,
        selection_rows=selection_rows,
        merged=merged,
        p6_rows=p6_rows,
        matrix=matrix,
    )
    candidates = [
        _candidate(
            pipeline_id,
            matrix=matrix,
            desktop_roles=roles,
            selection_row=selection_rows[pipeline_id],
            merged_row=merged[pipeline_id],
            field_sources=sources[pipeline_id],
            p6_row=p6_rows[pipeline_id],
            reasons=reasons[pipeline_id],
        )
        for pipeline_id in selected_ids
    ]
    document = {
        "schema_version": PI_SHORTLIST_SCHEMA,
        **scope_fields(),
        "prompt_index": 7,
        "status": "PASS",
        "steering_authority": inputs["steering_reference"],
        "prompt5_deployment_evidence": inputs["prompt5_reference"],
        "prompt6_deployment_evidence": inputs["prompt6_reference"],
        "desktop_roles": roles,
        "desktop_roles_source": artifact_ref(desktop_roles_source),
        "candidate_pool_source": inputs["candidate_pool_reference"],
        "desktop_roles_changed_for_pi": False,
        "candidate_pool_pipeline_ids": list(pool),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "deployment_attributes_by_pipeline": {
            pipeline_id: p6_rows[pipeline_id]["deployment_attributes"]
            for pipeline_id in selected_ids
        },
        "two_gib_classification_evidence_by_pipeline": {
            pipeline_id: p6_rows[pipeline_id]["two_gib_feasibility"]
            for pipeline_id in selected_ids
        },
        "selection_policy": {
            "policy_id": "prompt7_pi_categorical_preservation_no_composite.v1",
            "weighted_composite_used": False,
            "universal_within_one_percent_equivalence_rule_used": False,
            "deployment_evidence_used_to_rewrite_scientific_ranks": False,
            "two_gib_used_as_hard_filter": False,
            "final_pi_winner_selected": False,
            "candidate_order": "FROZEN_PROMPT4_EXTENDED_SET_ORDER",
            "safety_nondominated_efficiency_candidate_supported": policy_audit[
                "safety_nondominated_efficiency_candidate_supported"
            ],
            "safety_nondominated_efficiency_pipeline_id": policy_audit[
                "safety_nondominated_efficiency_pipeline_id"
            ],
        },
        "architecture_tradeoff_audit": _tradeoff_audit(
            matrix=matrix,
            pool=pool,
            credible=credible,
            selected_ids=selected_ids,
        ),
        "future_target_hardware_tests": list(FUTURE_TARGET_HARDWARE_TESTS),
        "future_linux_arm64_validation": list(FUTURE_LINUX_ARM64_VALIDATION),
        "final_raspberry_pi_winner": None,
        "final_raspberry_pi_winner_claimed": False,
        "desktop_software_ready_requirement_applied_to_pi_only_candidates": False,
        "pi_only_candidate_bundles_or_acceptance_tasks_created": False,
        "scientific_firewall": {
            "scientific_methodology_changed": False,
            "frozen_thresholds_changed": False,
            "heldout_reselection_or_retuning_performed": False,
            "desktop_roles_changed": False,
            "predeclared_extended_membership_expanded": False,
            "deployment_evidence_used_as_scientific_hard_filter": False,
        },
    }
    return validate_pi_shortlist(
        document,
        authorization=authorization,
        desktop_selection=desktop_selection,
        evidence_files=evidence_files,
        desktop_roles_source=desktop_roles_source,
    )


def validate_pi_shortlist(
    document: Mapping[str, object],
    *,
    authorization: Mapping[str, object],
    desktop_selection: Mapping[str, object],
    evidence_files: Mapping[str, Path],
    desktop_roles_source: Path | str,
) -> dict[str, object]:
    """Rehash and semantically validate a Prompt-7 shortlist document."""

    inputs = _validated_inputs(authorization)
    pool = _candidate_pool(authorization, desktop_selection)
    roles = _desktop_roles(desktop_selection)
    desktop_source = artifact_ref(desktop_roles_source)
    candidate_pool_source = inputs["candidate_pool_reference"]
    expected_core = {
        "schema_version": PI_SHORTLIST_SCHEMA,
        **scope_fields(),
        "prompt_index": 7,
        "status": "PASS",
        "steering_authority": inputs["steering_reference"],
        "prompt5_deployment_evidence": inputs["prompt5_reference"],
        "prompt6_deployment_evidence": inputs["prompt6_reference"],
        "desktop_roles": roles,
        "desktop_roles_source": desktop_source,
        "candidate_pool_source": candidate_pool_source,
        "desktop_roles_changed_for_pi": False,
        "candidate_pool_pipeline_ids": list(pool),
    }
    for key, expected in expected_core.items():
        if document.get(key) != expected:
            raise HardeningError(f"Prompt-7 Pi shortlist {key} differs")
    _validate_desktop_role_source(desktop_source, roles)
    if (
        document.get("final_raspberry_pi_winner") is not None
        or document.get("final_raspberry_pi_winner_claimed") is not False
    ):
        raise HardeningError("Prompt-7 may not claim a final Raspberry Pi winner")
    if document.get("future_target_hardware_tests") != list(
        FUTURE_TARGET_HARDWARE_TESTS
    ) or document.get("future_linux_arm64_validation") != list(
        FUTURE_LINUX_ARM64_VALIDATION
    ):
        raise HardeningError("Prompt-7 exact future ARM validation lists differ")
    policy = _mapping(document, "selection_policy")
    for key in (
        "weighted_composite_used",
        "universal_within_one_percent_equivalence_rule_used",
        "deployment_evidence_used_to_rewrite_scientific_ranks",
        "two_gib_used_as_hard_filter",
        "final_pi_winner_selected",
    ):
        if policy.get(key) is not False:
            raise HardeningError(f"Prompt-7 Pi selection policy {key} differs")
    architecture = _mapping(document, "architecture_tradeoff_audit")
    if architecture.get("final_arm_preference_claimed") is not False:
        raise HardeningError("Prompt-7 architecture audit claims an ARM preference")
    firewall = _mapping(document, "scientific_firewall")
    if any(value is not False for value in firewall.values()):
        raise HardeningError("Prompt-7 Pi scientific firewall differs")
    if (
        document.get("desktop_software_ready_requirement_applied_to_pi_only_candidates")
        is not False
        or document.get("pi_only_candidate_bundles_or_acceptance_tasks_created")
        is not False
    ):
        raise HardeningError("Prompt-7 Pi-only candidates changed desktop hardening")

    raw_candidates = document.get("candidates")
    if not isinstance(raw_candidates, list) or not 2 <= len(raw_candidates) <= 4:
        raise HardeningError(
            "Prompt-7 Pi shortlist must contain exactly 2-4 candidates"
        )
    if int(document.get("candidate_count") or -1) != len(raw_candidates):
        raise HardeningError("Prompt-7 Pi candidate count differs")
    selected_ids = tuple(
        str(raw.get("pipeline_id") or "")
        for raw in raw_candidates
        if isinstance(raw, Mapping)
    )
    if len(selected_ids) != len(raw_candidates) or len(set(selected_ids)) != len(
        selected_ids
    ):
        raise HardeningError("Prompt-7 Pi candidate IDs are absent or duplicated")
    if tuple(item for item in pool if item in set(selected_ids)) != selected_ids:
        raise HardeningError(
            "Prompt-7 Pi candidates do not preserve extended-set order"
        )
    if roles["PRIMARY"] not in selected_ids:
        raise HardeningError("Prompt-7 Pi shortlist omits the desktop PRIMARY")

    merged, sources = _merge_prompt5_rows(evidence_files)
    selection_rows = _selection_rows(desktop_selection, pool)
    credible = [
        pipeline_id
        for pipeline_id in pool
        if _scientifically_credible(selection_rows[pipeline_id], merged[pipeline_id])
    ]
    p6_rows = _deployment_rows(inputs["prompt6_document"], pool, "Prompt-6")
    expected_ids, expected_reasons, audit = _choose_candidates(
        pool=pool,
        credible=credible,
        primary=roles["PRIMARY"],
        selection_rows=selection_rows,
        merged=merged,
        p6_rows=p6_rows,
        matrix=FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH),
    )
    if selected_ids != expected_ids:
        raise HardeningError("Prompt-7 Pi shortlist membership is not reproducible")
    if policy.get("safety_nondominated_efficiency_candidate_supported") != audit.get(
        "safety_nondominated_efficiency_candidate_supported"
    ) or policy.get("safety_nondominated_efficiency_pipeline_id") != audit.get(
        "safety_nondominated_efficiency_pipeline_id"
    ):
        raise HardeningError("Prompt-7 Pi efficiency audit differs")

    attributes = _mapping(document, "deployment_attributes_by_pipeline")
    feasibility = _mapping(document, "two_gib_classification_evidence_by_pipeline")
    if set(attributes) != set(selected_ids) or set(feasibility) != set(selected_ids):
        raise HardeningError("Prompt-7 Pi deployment evidence coverage differs")
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    for raw, pipeline_id in zip(raw_candidates, selected_ids, strict=True):
        assert isinstance(raw, Mapping)
        if set(raw) != set(RASPBERRY_PI_CANDIDATE_FIELDS):
            raise HardeningError(
                f"Prompt-7 exact 26 candidate fields differ: {pipeline_id}"
            )
        p6_row = p6_rows[pipeline_id]
        if attributes[pipeline_id] != p6_row.get("deployment_attributes"):
            raise HardeningError(f"Prompt-7/P6 attributes differ: {pipeline_id}")
        if feasibility[pipeline_id] != p6_row.get("two_gib_feasibility"):
            raise HardeningError(f"Prompt-7/P6 2-GiB evidence differs: {pipeline_id}")
        for name in DEPLOYMENT_ATTRIBUTE_NAMES:
            try:
                validate_evidence(attributes[pipeline_id][name])
            except (DeploymentEvidenceError, KeyError, TypeError) as exc:
                raise HardeningError(
                    f"Prompt-7 deployment evidence is invalid: {pipeline_id} {name}: {exc}"
                ) from exc
        expected_candidate = _candidate(
            pipeline_id,
            matrix=matrix,
            desktop_roles=roles,
            selection_row=selection_rows[pipeline_id],
            merged_row=merged[pipeline_id],
            field_sources=sources[pipeline_id],
            p6_row=p6_row,
            reasons=expected_reasons[pipeline_id],
        )
        if dict(raw) != expected_candidate:
            raise HardeningError(
                f"Prompt-7 Pi candidate binding differs: {pipeline_id}"
            )
    expected_architecture = _tradeoff_audit(
        matrix=matrix,
        pool=pool,
        credible=credible,
        selected_ids=selected_ids,
    )
    if architecture != expected_architecture:
        raise HardeningError("Prompt-7 architecture tradeoff audit differs")
    return dict(document)


def _validated_inputs(authorization: Mapping[str, object]) -> dict[str, object]:
    authority = _mapping(authorization, "deployment_steering")
    steering_path = ensure_c(
        str(authority.get("path") or ""),
        label="Prompt-7 deployment steering",
        must_exist=True,
    )
    steering = load_deployment_steering(
        steering_path,
        expected_prompt_index=7,
        expected_sha256=PI_DEPLOYMENT_STEERING_SHA256,
    )
    reference = steering_ref(steering_path, steering)
    if authority != reference:
        raise HardeningError("Prompt-7 deployment steering authorization differs")
    p5_ref = _exact_ref(authorization, "prompt5_deployment_evidence")
    p6_ref = _exact_ref(authorization, "prompt6_deployment_evidence")
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    pool = tuple(
        str(item) for item in authorization.get("predeclared_extended_pipeline_ids", [])
    )
    try:
        p5 = validate_deployment_evidence_document(
            read_json(p5_ref["path"]),
            schema_version=_P5_SCHEMA,
            prompt_index=5,
            expected_pipeline_ids=matrix.pipeline_ids,
            steering=steering,
        )
        p6 = validate_deployment_evidence_document(
            read_json(p6_ref["path"]),
            schema_version=_P6_SCHEMA,
            prompt_index=6,
            expected_pipeline_ids=pool,
            steering=steering,
        )
    except DeploymentEvidenceError as exc:
        raise HardeningError(f"upstream deployment evidence is invalid: {exc}") from exc
    if (
        p5.get("steering_authority") != reference
        or p6.get("steering_authority") != reference
    ):
        raise HardeningError("upstream deployment steering binding differs")
    if p6.get("prompt5_deployment_evidence") != p5_ref:
        raise HardeningError("Prompt-6 deployment evidence does not bind Prompt 5")
    return {
        "steering": steering,
        "steering_reference": reference,
        "prompt5_reference": p5_ref,
        "prompt6_reference": p6_ref,
        "prompt5_document": p5,
        "prompt6_document": p6,
        "candidate_pool_reference": _exact_ref(
            authorization, "predeclared_extended_set"
        ),
    }


def _exact_ref(authorization: Mapping[str, object], key: str) -> dict[str, str]:
    raw = _mapping(authorization, key)
    path = ensure_c(str(raw.get("path") or ""), label=key, must_exist=True)
    expected = artifact_ref(path)
    if raw != expected:
        raise HardeningError(f"Prompt-7 authorization {key} differs")
    return expected


def _validate_desktop_role_source(
    reference: Mapping[str, object], roles: Mapping[str, str | None]
) -> None:
    path = ensure_c(
        str(reference.get("path") or ""),
        label="Prompt-7 desktop roles source",
        must_exist=True,
    )
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, Mapping):
        raise HardeningError("Prompt-7 desktop role catalog is invalid")
    if value.get("schema_version") != "full-pipeline-production-candidate-catalog.v1":
        raise HardeningError("Prompt-7 desktop role catalog schema differs")
    if value.get("roles") != roles:
        raise HardeningError("Prompt-7 desktop role catalog roles differ")


def _candidate_pool(
    authorization: Mapping[str, object], desktop_selection: Mapping[str, object]
) -> tuple[str, ...]:
    values = tuple(
        str(item) for item in authorization.get("predeclared_extended_pipeline_ids", [])
    )
    if not 6 <= len(values) <= 8 or len(values) != len(set(values)):
        raise HardeningError("Prompt-7 predeclared extended candidate pool differs")
    if desktop_selection.get("candidate_pool") != list(values):
        raise HardeningError("desktop selection changed the predeclared candidate pool")
    return values


def _desktop_roles(value: Mapping[str, object]) -> dict[str, str | None]:
    raw = _mapping(value, "roles")
    roles = {
        role: (str(raw[role]) if raw.get(role) is not None else None)
        for role in ("PRIMARY", "FALLBACK", "ALTERNATIVE")
    }
    if not roles["PRIMARY"]:
        raise HardeningError("desktop PRIMARY is absent")
    return roles


def _selection_rows(
    value: Mapping[str, object], pool: Sequence[str]
) -> dict[str, Mapping[str, object]]:
    raw = value.get("candidates")
    if not isinstance(raw, list):
        raise HardeningError("desktop candidate attestations are absent")
    rows = {
        str(item.get("pipeline_id") or ""): item
        for item in raw
        if isinstance(item, Mapping)
    }
    if tuple(pipeline_id for pipeline_id in pool if pipeline_id in rows) != tuple(pool):
        raise HardeningError("desktop candidate attestations do not cover extended set")
    return rows


def _merge_prompt5_rows(
    evidence_files: Mapping[str, Path],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, tuple[Path, str]]]]:
    matrix_ids = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH).pipeline_ids
    merged = {pipeline_id: {} for pipeline_id in matrix_ids}
    sources: dict[str, dict[str, tuple[Path, str]]] = {
        pipeline_id: {} for pipeline_id in matrix_ids
    }
    for name in _P5_MERGE_ORDER:
        path = evidence_files.get(name)
        if path is None:
            raise HardeningError(f"Prompt-5 evidence file is absent: {name}")
        source = ensure_c(path, label=name, must_exist=True)
        rows = read_csv(source)
        observed: set[str] = set()
        for row in rows:
            pipeline_id = str(row.get("pipeline_id") or "")
            if pipeline_id not in merged or pipeline_id in observed:
                raise HardeningError(
                    f"{name} contains duplicate/unknown {pipeline_id!r}"
                )
            observed.add(pipeline_id)
            for key, value in row.items():
                if value not in (None, "") or key not in merged[pipeline_id]:
                    merged[pipeline_id][key] = value
                    sources[pipeline_id][key] = (source, key)
        if observed != set(matrix_ids):
            raise HardeningError(f"{name} is not exact all-18")
    return merged, sources


def _deployment_rows(
    document: Mapping[str, object], expected_ids: Sequence[str], label: str
) -> dict[str, Mapping[str, object]]:
    raw = document.get("pipelines")
    if not isinstance(raw, list):
        raise HardeningError(f"{label} deployment rows are absent")
    rows = {
        str(item.get("pipeline_id") or ""): item
        for item in raw
        if isinstance(item, Mapping)
    }
    if tuple(item for item in expected_ids if item in rows) != tuple(
        expected_ids
    ) or len(rows) != len(raw):
        raise HardeningError(f"{label} deployment rows differ")
    return rows


def _scientifically_credible(
    selection_row: Mapping[str, object], merged_row: Mapping[str, object]
) -> bool:
    rtf = _first_number(merged_row, _METRICS["rtf"][0])
    return bool(
        selection_row.get("reliability_eligible") is True
        and _first_number(merged_row, _METRICS["wrong_known"][0]) is not None
        and _first_number(merged_row, _METRICS["stranger_false_known"][0]) is not None
        and _first_number(merged_row, _FAILURE_ALIASES) == 0.0
        and rtf is not None
        and rtf <= 1.0
    )


def _choose_candidates(
    *,
    pool: Sequence[str],
    credible: Sequence[str],
    primary: str,
    selection_rows: Mapping[str, Mapping[str, object]],
    merged: Mapping[str, Mapping[str, object]],
    p6_rows: Mapping[str, Mapping[str, object]],
    matrix: FullPipelineMatrix,
) -> tuple[tuple[str, ...], dict[str, list[str]], dict[str, object]]:
    credible_set = set(credible)
    if primary not in credible_set or len(credible_set) < 2:
        raise HardeningError("Pi shortlist does not have a credible primary plus peer")
    reasons: dict[str, list[str]] = {primary: ["DESKTOP_PRIMARY_ACCURACY_REFERENCE"]}
    chosen = {primary}
    safety_frontier = {
        pipeline_id
        for pipeline_id in credible
        if not any(
            other != pipeline_id
            and _safety_dominates(merged[other], merged[pipeline_id])
            for other in credible
        )
    }
    supported_efficiency = [
        pipeline_id
        for pipeline_id in credible
        if pipeline_id != primary and pipeline_id in safety_frontier
    ]
    if supported_efficiency:
        efficiency = min(
            supported_efficiency,
            key=lambda pipeline_id: _resource_key(
                pipeline_id, merged=merged, p6_rows=p6_rows
            ),
        )
        reasons[efficiency] = ["SAFETY_NONDOMINATED_EFFICIENCY_LOW_MEMORY_REFERENCE"]
        efficiency_supported = True
    else:
        efficiency = min(
            (pipeline_id for pipeline_id in credible if pipeline_id != primary),
            key=lambda pipeline_id: _resource_key(
                pipeline_id, merged=merged, p6_rows=p6_rows
            ),
        )
        reasons[efficiency] = [
            "EFFICIENCY_REFERENCE_SAFETY_TRADEOFF_REQUIRES_TARGET_VALIDATION"
        ]
        efficiency_supported = False
    chosen.add(efficiency)

    categories = {
        pipeline_id: _categories(matrix.resolve(pipeline_id))
        for pipeline_id in credible
    }
    desired = {"H2", "H5", "WESPEAKER", "ASR_AO", "ASR_AG"}
    while len(chosen) < min(4, len(credible_set)):
        covered = set().union(*(categories[pipeline_id] for pipeline_id in chosen))
        remaining = [
            pipeline_id for pipeline_id in credible if pipeline_id not in chosen
        ]
        if not remaining:
            break
        best = min(
            remaining,
            key=lambda pipeline_id: (
                -len((categories[pipeline_id] - covered) & desired),
                int(selection_rows[pipeline_id].get("technical_rank") or 10**9),
                pool.index(pipeline_id),
            ),
        )
        new_categories = sorted((categories[best] - covered) & desired)
        if not new_categories:
            break
        chosen.add(best)
        reasons[best] = [
            f"CATEGORICAL_ARCHITECTURE_DIVERSITY_{category}"
            for category in new_categories
        ]
    selected = tuple(pipeline_id for pipeline_id in pool if pipeline_id in chosen)
    return (
        selected,
        reasons,
        {
            "safety_nondominated_efficiency_candidate_supported": efficiency_supported,
            "safety_nondominated_efficiency_pipeline_id": (
                efficiency if efficiency_supported else None
            ),
        },
    )


def _candidate(
    pipeline_id: str,
    *,
    matrix: FullPipelineMatrix,
    desktop_roles: Mapping[str, str | None],
    selection_row: Mapping[str, object],
    merged_row: Mapping[str, object],
    field_sources: Mapping[str, tuple[Path, str]],
    p6_row: Mapping[str, object],
    reasons: Sequence[str],
) -> dict[str, object]:
    resolved = matrix.resolve(pipeline_id)
    attributes = _mapping(p6_row, "deployment_attributes")
    feasibility = _mapping(p6_row, "two_gib_feasibility")
    portability = _mapping(p6_row, "linux_arm64_portability")
    candidate = {
        "pipeline_id": pipeline_id,
        "asr": {
            "alias": resolved.asr_alias,
            "component_id": resolved.asr.get("component_id"),
            "registry_id": resolved.asr.get("registry_id"),
            "environment_profile": resolved.asr.get("environment_profile"),
        },
        "segmentation": {
            "segmentation_id": resolved.diarization.get("segmentation_id"),
        },
        "diarization_embedding": {
            "alias": resolved.diarization_alias,
            "backend_id": resolved.diarization_embedding.get("backend_id"),
            "model_id": resolved.diarization_embedding.get("model_id"),
            "embedding_dimension": resolved.diarization_embedding.get(
                "embedding_dimension"
            ),
            "environment_profile": resolved.diarization_embedding.get(
                "environment_profile"
            ),
        },
        "identity_embedding": {
            "alias": resolved.identity_alias,
            "backend_id": resolved.identity.get("backend_id"),
            "model_id": resolved.identity.get("model_id"),
            "embedding_dimension": resolved.identity.get("embedding_dimension"),
            "environment_profile": resolved.identity.get("environment_profile"),
        },
        "enrollment_policy": {
            "policy_id": resolved.enrollment_policy.get("policy_id"),
            "path": resolved.enrollment_policy.get("path"),
            "sha256": resolved.enrollment_policy.get("sha256"),
        },
        "current_desktop_accuracy": {
            "status": "PROMPT5_UNTOUCHED_HELDOUT_DESKTOP",
            "selected_desktop_role": next(
                (role for role, value in desktop_roles.items() if value == pipeline_id),
                None,
            ),
            "technical_rank": selection_row.get("technical_rank"),
            "pareto_frontier": selection_row.get("pareto_frontier"),
            "software_ready_required_for_pi_shortlist": False,
        },
        **{
            name: _metric_cell(
                merged_row,
                field_sources,
                aliases=aliases,
                unit=unit,
                metric_id=name,
            )
            for name, (aliases, unit) in _METRICS.items()
        },
        "latency": {
            name: _metric_cell(
                merged_row,
                field_sources,
                aliases=aliases,
                unit=unit,
                metric_id=name,
            )
            for name, (aliases, unit) in _LATENCY_METRICS.items()
        },
        "peak_ram": attributes["total_pipeline_peak_rss_bytes"],
        "model_footprint": attributes["model_file_size_bytes"],
        "resident_model_count": attributes[
            "simultaneously_resident_neural_model_count"
        ],
        "export_path": {
            "status": "UNKNOWN_REQUIRES_LINUX_ARM64_EXPORT_AND_PARITY",
            "current_export_status": attributes["export_status"],
            "onnx_runtime_export_feasibility": attributes[
                "onnx_runtime_export_feasibility"
            ],
            "executorch_feasibility": attributes["executorch_feasibility"],
            "arm_measurement": False,
        },
        "quantization_opportunities": _quantization_opportunities(resolved),
        "model_sharing_opportunities": _sharing_opportunities(resolved),
        "arm_runtime_risks": _arm_risks(resolved, attributes),
        "reason_retained": list(reasons),
        "two_gib_feasibility_class": feasibility.get("class"),
        "linux_arm64_portability_class": portability.get("class"),
        "windows_specific_assumptions": p6_row.get("windows_specific_assumptions"),
        "linux_arm64_dependency_status": p6_row.get("linux_arm64_dependency_status"),
        "required_platform_replacements": p6_row.get("required_platform_replacements"),
    }
    if set(candidate) != set(RASPBERRY_PI_CANDIDATE_FIELDS):
        raise HardeningError(
            f"internal exact candidate field set differs: {pipeline_id}"
        )
    for key in (
        "wer",
        "der",
        "wrong_known",
        "stranger_false_known",
        "rtf",
        "peak_ram",
        "model_footprint",
        "resident_model_count",
        "windows_specific_assumptions",
        "linux_arm64_dependency_status",
        "required_platform_replacements",
    ):
        try:
            validate_evidence(candidate[key])
        except DeploymentEvidenceError as exc:
            raise HardeningError(
                f"Prompt-7 candidate evidence is invalid: {pipeline_id} {key}: {exc}"
            ) from exc
    for key, cell in candidate["latency"].items():
        try:
            validate_evidence(cell)
        except DeploymentEvidenceError as exc:
            raise HardeningError(
                f"Prompt-7 candidate latency evidence is invalid: {pipeline_id} {key}: {exc}"
            ) from exc
    return candidate


def _metric_cell(
    row: Mapping[str, object],
    sources: Mapping[str, tuple[Path, str]],
    *,
    aliases: Sequence[str],
    unit: str,
    metric_id: str,
) -> dict[str, object]:
    for alias in aliases:
        number = _number(row.get(alias))
        if number is None:
            continue
        source = sources.get(alias)
        if source is None:
            raise HardeningError(f"source is absent for Prompt-5 metric {alias}")
        path, field = source
        return evidence(
            number,
            unit=unit,
            evidence_status="MEASURED",
            reason_code="PROMPT5_UNTOUCHED_HELDOUT_DESKTOP_METRIC",
            measurement_context="WINDOWS_X86_64_DESKTOP",
            source_path=path,
            source_sha256=sha256_file(path),
            source_field=field,
            desktop_measurement=True,
            details={"candidate_field": metric_id, "arm_target_measurement": False},
        )
    return unknown_evidence(
        unit=unit,
        reason_code="PROMPT5_METRIC_UNAVAILABLE",
        details={"candidate_field": metric_id, "aliases": list(aliases)},
    )


def _safety_dominates(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    left_values = (
        _first_number(left, _METRICS["wrong_known"][0]),
        _first_number(left, _METRICS["stranger_false_known"][0]),
    )
    right_values = (
        _first_number(right, _METRICS["wrong_known"][0]),
        _first_number(right, _METRICS["stranger_false_known"][0]),
    )
    if None in left_values or None in right_values:
        return False
    return all(a <= b for a, b in zip(left_values, right_values, strict=True)) and any(
        a < b for a, b in zip(left_values, right_values, strict=True)
    )


def _resource_key(
    pipeline_id: str,
    *,
    merged: Mapping[str, Mapping[str, object]],
    p6_rows: Mapping[str, Mapping[str, object]],
) -> tuple[float, float, float, str]:
    attributes = _mapping(p6_rows[pipeline_id], "deployment_attributes")
    rtf = _first_number(merged[pipeline_id], _METRICS["rtf"][0])
    return (
        _evidence_number(attributes["total_pipeline_peak_rss_bytes"]),
        _evidence_number(attributes["model_file_size_bytes"]),
        rtf if rtf is not None else math.inf,
        pipeline_id,
    )


def _evidence_number(value: object) -> float:
    if not isinstance(value, Mapping):
        return math.inf
    number = _number(value.get("value"))
    return number if number is not None else math.inf


def _categories(value: PipelineSelection) -> set[str]:
    result = {value.hybrid_label, f"ASR_{value.asr_alias}"}
    if value.diarization_alias == "DW" or value.identity_alias == "IW":
        result.add("WESPEAKER")
    return result


def _tradeoff_audit(
    *,
    matrix: FullPipelineMatrix,
    pool: Sequence[str],
    credible: Sequence[str],
    selected_ids: Sequence[str],
) -> dict[str, object]:
    resolved = {pipeline_id: matrix.resolve(pipeline_id) for pipeline_id in pool}
    credible_set = set(credible)
    selected_set = set(selected_ids)

    def audit(predicate) -> dict[str, object]:
        supported = [
            pipeline_id
            for pipeline_id in pool
            if pipeline_id in credible_set and predicate(resolved[pipeline_id])
        ]
        shortlisted = [
            pipeline_id for pipeline_id in supported if pipeline_id in selected_set
        ]
        return {
            "credible_pipeline_ids": supported,
            "shortlisted_pipeline_ids": shortlisted,
            "status": (
                "SHORTLIST_REPRESENTED"
                if shortlisted
                else "NOT_SHORTLISTED_WITHIN_FOUR_CANDIDATE_CAP"
                if supported
                else "UNSUPPORTED_NO_CREDIBLE_PIPELINE"
            ),
        }

    return {
        "H2_same_model": {
            **audit(lambda row: row.hybrid_label == "H2"),
            "sharing_claim": "POTENTIAL_ONLY_NOT_IMPLEMENTED_OR_MEASURED",
        },
        "H5_dual_embedding": {
            **audit(lambda row: row.hybrid_label == "H5"),
            "tradeoff": "SAFETY_VERSUS_TWO_EMBEDDING_ARCHITECTURES_REQUIRES_ARM_TEST",
        },
        "wespeaker_paths": {
            **audit(
                lambda row: row.diarization_alias == "DW" or row.identity_alias == "IW"
            ),
            "tradeoff": "DESKTOP_ACCURACY_AND_RESOURCES_DO_NOT_PREDICT_ARM",
        },
        "asr_original_sherpa_AO": audit(lambda row: row.asr_alias == "AO"),
        "asr_sherpa_giga_AG": audit(lambda row: row.asr_alias == "AG"),
        "both_asrs_preserved_in_all18_desktop_ranking": True,
        "shortlist_asr_aliases": sorted(
            {resolved[pipeline_id].asr_alias for pipeline_id in selected_ids}
        ),
        "final_arm_preference_claimed": False,
    }


def _quantization_opportunities(value: PipelineSelection) -> list[str]:
    output = [
        "ASR_CURRENT_ONNX_INT8_ASSETS_REVIEW_WHERE_PRESENT",
        "SPEAKER_MODELS_REQUIRE_EXPORT_PARITY_AND_SAFETY_REGRESSION_TESTS",
        "NO_QUANTIZED_ARM_RESULT_CLAIMED",
    ]
    if value.hybrid_label == "H5":
        output.append("H5_BOTH_EMBEDDING_ARCHITECTURES_REQUIRE_SEPARATE_VALIDATION")
    return output


def _sharing_opportunities(value: PipelineSelection) -> list[str]:
    same = str(value.diarization_embedding.get("backend_id") or "") == str(
        value.identity.get("backend_id") or ""
    )
    return [
        (
            "SAME_BACKEND_INSTANCE_OR_EMBEDDING_REUSE_POTENTIAL_ONLY"
            if same
            else "DISTINCT_EMBEDDING_ARCHITECTURES_NO_INSTANCE_SHARING_ASSUMED"
        ),
        "FEATURE_EXTRACTION_DUPLICATION_CURRENTLY_UNKNOWN",
    ]


def _arm_risks(value: PipelineSelection, attributes: Mapping[str, object]) -> list[str]:
    output = [
        "NO_NATIVE_LINUX_ARM64_RTF_RAM_LATENCY_OR_THERMAL_MEASUREMENT",
        "FULL_PIPELINE_EXPORT_AND_NUMERICAL_PARITY_UNPROVEN",
        "TWO_GIB_MUST_INCLUDE_OS_UI_QUEUES_AND_SESSION_STATE",
        "WINDOWS_MULTIPROCESSING_AUDIO_AND_SERVICE_ASSUMPTIONS_REQUIRE_AUDIT",
    ]
    if value.hybrid_label == "H2":
        output.append("H2_MODEL_SHARING_BENEFIT_NOT_IMPLEMENTED_OR_MEASURED")
    if value.hybrid_label == "H5":
        output.append("H5_RETAINS_TWO_DISTINCT_SPEAKER_EMBEDDING_ARCHITECTURES")
    if value.diarization_alias == "DW" or value.identity_alias == "IW":
        output.append("WESPEAKER_LINUX_ARM64_EXPORT_RUNTIME_UNVALIDATED")
    if _evidence_number(attributes["total_pipeline_peak_rss_bytes"]) == math.inf:
        output.append("DESKTOP_TOTAL_PIPELINE_PEAK_RSS_UNKNOWN")
    return output


def _first_number(row: Mapping[str, object], aliases: Sequence[str]) -> float | None:
    for alias in aliases:
        value = _number(row.get(alias))
        if value is not None:
            return value
    return None


def _number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mapping(value: Mapping[str, object], key: str) -> dict[str, object]:
    raw = value.get(key)
    if not isinstance(raw, Mapping):
        raise HardeningError(f"Prompt-7 {key} is absent")
    return dict(raw)


__all__ = ["build_pi_shortlist", "validate_pi_shortlist"]
