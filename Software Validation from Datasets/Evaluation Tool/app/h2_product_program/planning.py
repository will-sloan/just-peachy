"""Checksum-bound protocol and staged job planning for the H2 program."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix

from .contracts import H2Job, H2ProgramError, H2_PROTOCOL_SCHEMA_VERSION, ProgramPaths
from .io import canonical_sha256, read_jsonl, read_yaml, sha256_file
from .selection import (
    SAFETY_PRIORITY_CONTRACT_ID,
    SAFETY_PRIORITY_ORDERED_RISK_FAMILIES,
    build_panel_manifest,
)


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = EVALUATION_ROOT.parents[1]
DEFAULT_CONFIG_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/h2_product_program.v17.yaml"
)
MATRIX_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
)
RUNTIME_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
)
HISTORICAL_EVIDENCE_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/h2_historical_evidence.v1.yaml"
)
PREPARED_PROTOCOL_ROOT = (
    EVALUATION_ROOT / "benchmarks/full_pipeline/full_speech_pipeline_v1"
)
DEFAULT_WORKSPACE = EVALUATION_ROOT / "automated_runs/h2_complete_product_pipeline_v17"
DEFAULT_RESULTS_ROOT = (
    EVALUATION_ROOT / "JustPeachyResults/full_pipeline/h2_complete_product_pipeline_v17"
)
DEFAULT_SUMMARY_ROOT = (
    EVALUATION_ROOT / "JustPeachyResearchSummaries/h2_complete_product_pipeline_v17"
)


def default_paths(
    *,
    workspace: Path | None = None,
    results_root: Path | None = None,
    summary_root: Path | None = None,
    config_path: Path | None = None,
) -> ProgramPaths:
    return ProgramPaths(
        evaluation_root=EVALUATION_ROOT,
        workspace=(workspace or DEFAULT_WORKSPACE).resolve(),
        results_root=(results_root or DEFAULT_RESULTS_ROOT).resolve(),
        summary_root=(summary_root or DEFAULT_SUMMARY_ROOT).resolve(),
        config_path=(config_path or DEFAULT_CONFIG_PATH).resolve(),
    )


def load_and_validate_spec(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    spec = read_yaml(path)
    if spec.get("schema_version") != "just-peachy-h2-product-program.v1":
        raise H2ProgramError("unexpected H2 program schema")
    architecture = _mapping(spec, "fixed_architecture")
    exact = {
        "primary_pipeline_id": "fullpipe_v1_ag_dr_ir",
        "fallback_pipeline_id": "fullpipe_v1_ao_dr_ir",
        "hybrid_label": "H2",
        "anonymous_embedding": "redimnet2_b2_speaker_embedding",
        "identity_embedding": "redimnet2_b2_speaker_embedding",
        "segmentation": "pyannote_segmentation_3_0",
    }
    for key, expected in exact.items():
        if architecture.get(key) != expected:
            raise H2ProgramError(f"fixed H2 architecture changed at {key}")
    excluded = set(map(str, architecture.get("excluded_hybrids") or ()))
    if not {"H4", "H5"}.issubset(excluded):
        raise H2ProgramError("H4/H5 must be excluded by the H2 steering override")
    modes = _mapping(spec, "product_modes")
    expected_modes = {
        "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_ENHANCED",
    }
    if set(modes) != expected_modes:
        raise H2ProgramError("H2 product mode set differs")
    execution = _mapping(spec, "execution")
    if int(execution.get("accuracy_parallel_jobs_max") or 0) > 2:
        raise H2ProgramError("accuracy parallelism exceeds two")
    if int(execution.get("resource_parallel_jobs") or 0) != 1:
        raise H2ProgramError("resource work must be serial")
    if (
        execution.get("target_is_advisory_only") is not True
        or execution.get("no_automatic_time_limit") is not True
    ):
        raise H2ProgramError("the eight-day target must remain advisory")
    # Archived v1-v13 manifests remain readable for forensic validation.  The
    # corrected v14+ protocol is fail-closed unless both the machine contract
    # and the matching top-level prose declaration are present.
    protocol_match = re.fullmatch(
        r"h2_product_protocol\.v(?P<version>\d+)", str(spec.get("protocol_version"))
    )
    if protocol_match and int(protocol_match.group("version")) >= 14:
        scientific_scoring = _mapping(spec, "scientific_scoring")
        if (
            scientific_scoring.get("safety_priority_contract_id")
            != SAFETY_PRIORITY_CONTRACT_ID
        ):
            raise H2ProgramError("scientific safety-priority contract differs")
        if tuple(scientific_scoring.get("ordered_safety_risk_families") or ()) != (
            SAFETY_PRIORITY_ORDERED_RISK_FAMILIES
        ):
            raise H2ProgramError("scientific safety-risk family order differs")
        selection_priorities = _mapping(spec, "selection_priorities")
        declared = tuple(map(str, selection_priorities.get("ordered") or ()))
        if declared[:2] != (
            "minimize_wrong_known_speaker_time",
            "minimize_stranger_false_known_time",
        ):
            raise H2ProgramError("top-level selection safety order differs")
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    for pipeline_id in exact["primary_pipeline_id"], exact["fallback_pipeline_id"]:
        selection = matrix.resolve(pipeline_id)
        if (
            selection.hybrid_label != "H2"
            or selection.diarization_alias != "DR"
            or selection.identity_alias != "IR"
        ):
            raise H2ProgramError(f"matrix row is not H2: {pipeline_id}")
    return spec


def build_protocol_manifest(paths: ProgramPaths) -> dict[str, object]:
    spec = load_and_validate_spec(paths.config_path)
    development = read_jsonl(PREPARED_PROTOCOL_ROOT / "development/case_manifest.jsonl")
    evaluation = read_jsonl(PREPARED_PROTOCOL_ROOT / "evaluation/case_manifest.jsonl")
    panels = build_panel_manifest(
        development,
        evaluation,
        tool_root=EVALUATION_ROOT,
        seed=int(spec["seed"]),
    )
    source_protocol_summary = PREPARED_PROTOCOL_ROOT / "protocol_summary.json"
    core = {
        "schema_version": H2_PROTOCOL_SCHEMA_VERSION,
        "program_id": spec["program_id"],
        "protocol_version": spec["protocol_version"],
        "seed": int(spec["seed"]),
        "scope": "H2_ONLY_FIXED_ARCHITECTURE",
        "config_path": str(paths.config_path),
        "config_sha256": sha256_file(paths.config_path),
        "matrix_path": str(MATRIX_PATH),
        "matrix_sha256": sha256_file(MATRIX_PATH),
        "runtime_path": str(RUNTIME_PATH),
        "runtime_sha256": sha256_file(RUNTIME_PATH),
        "historical_evidence_path": str(HISTORICAL_EVIDENCE_PATH),
        "historical_evidence_sha256": sha256_file(HISTORICAL_EVIDENCE_PATH),
        "prepared_protocol_root": str(PREPARED_PROTOCOL_ROOT),
        "prepared_protocol_summary_sha256": sha256_file(source_protocol_summary),
        "fixed_architecture": deepcopy(spec["fixed_architecture"]),
        "product_modes": deepcopy(spec["product_modes"]),
        "historical_baseline": deepcopy(spec["historical_baseline"]),
        "development_search": deepcopy(spec["development_search"]),
        "panels": panels,
        "firewall": {
            "development_calibration_only": True,
            "evaluation_execution_requires_freeze": True,
            "evaluation_recalibration_allowed": False,
            "heldout_membership_selected_from_metadata_only": True,
            "heldout_reference_content_used_by_selection": False,
            "heldout_source_rows_may_contain_reference_fields": True,
            "failed_and_partial_attempts_retained": True,
        },
        "stop_semantics": "finish_current_atomic_case_then_stop",
        "parallelism": {"accuracy_max": 2, "resources": 1},
        "target_wall_hours": float(_mapping(spec, "execution")["target_wall_hours"]),
        "target_is_advisory_only": True,
    }
    identity = canonical_sha256(core)
    protocol_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", str(spec["protocol_version"])).strip(
        "_"
    )
    return {
        **core,
        "protocol_id": f"{protocol_slug}_{identity[:12]}",
        "protocol_sha256": identity,
    }


def build_job_manifest(protocol: Mapping[str, object]) -> dict[str, object]:
    panels = _mapping(protocol, "panels")
    development = _mapping(panels, "development")
    evaluation = _mapping(panels, "evaluation")
    dev_small = _mapping(development, "small")
    dev_medium = _mapping(development, "medium")
    dev_core = _mapping(development, "core")
    dev_integration = _mapping(development, "integration_eligible")
    dev_long = _mapping(development, "long_session")
    eval_core = _mapping(evaluation, "core")
    eval_reduced = _mapping(evaluation, "reduced_paired")
    eval_long = _mapping(evaluation, "long_session")
    diagnostics = _mapping(evaluation, "diagnostics")
    baseline = _baseline_tuning(protocol)
    jobs: list[H2Job] = []

    jobs.extend(
        [
            _job(
                0,
                "AUDIT_BASELINE",
                "evidence_audit",
                "none",
                "NOT_APPLICABLE",
                "H2_BASELINE_EVIDENCE_AUDIT",
                "NOT_APPLICABLE",
                {},
                None,
                1.0,
            ),
            _runtime_job(
                0,
                "AUDIT_BASELINE",
                "development",
                "fullpipe_v1_ag_dr_ir",
                "H2_BASELINE_REFERENCE",
                "H2_SESSION_ANONYMOUS",
                dev_core,
                baseline,
                4.0,
            ),
            _job(
                0,
                "AUDIT_BASELINE",
                "runtime_qualification",
                "development",
                "fullpipe_v1_ag_dr_ir",
                "H2_TRUE_STREAMING_QUALIFICATION",
                "H2_SESSION_MEMORY_ENHANCED",
                baseline,
                dev_small,
                2.0,
            ),
        ]
    )

    segmentation = _segmentation_candidates(baseline)
    for candidate_id, tuning in segmentation.items():
        for tier, panel, hours in (
            ("small", dev_small, 0.8),
            ("medium", dev_medium, 1.5),
            ("full", dev_core, 3.4),
        ):
            stage_tuning = deepcopy(tuning)
            jobs.append(
                _runtime_job(
                    1,
                    "SEGMENTATION_FRONTIER",
                    "development",
                    "fullpipe_v1_ag_dr_ir",
                    f"{candidate_id}_{tier.upper()}",
                    "H2_SESSION_MEMORY_ENHANCED",
                    panel,
                    stage_tuning,
                    hours,
                    job_kind="successive_halving_runtime",
                    optional=tier != "small",
                )
            )

    for correction_ms in (0, 250, 500, 750, 1000):
        tuning = deepcopy(baseline)
        tuning["boundary_correction_ms"] = correction_ms
        jobs.append(
            _runtime_job(
                1,
                "SEGMENTATION_FRONTIER",
                "development",
                "fullpipe_v1_ag_dr_ir",
                f"BOUNDARY_CORRECTION_{correction_ms:04d}MS",
                "H2_SESSION_MEMORY_ENHANCED",
                dev_medium,
                tuning,
                1.8,
            )
        )
    for overlap_policy in (
        "INCLUDE_PREDICTED_OVERLAP",
        "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
    ):
        tuning = deepcopy(baseline)
        tuning["overlap_policy"] = overlap_policy
        jobs.append(
            _runtime_job(
                1,
                "SEGMENTATION_FRONTIER",
                "development",
                "fullpipe_v1_ag_dr_ir",
                overlap_policy,
                "H2_SESSION_MEMORY_ENHANCED",
                dev_medium,
                tuning,
                1.8,
            )
        )

    redim = {
        **_redim_candidates(baseline),
        **_clustering_attach_candidates(
            baseline,
            _mapping(
                _mapping(protocol, "development_search"),
                "embedding_frontier",
            ),
        ),
    }
    _require_unique_candidate_tunings(redim)

    # R1 and R2 are accuracy-equivalent execution architectures, not two
    # independent accuracy-frontier cells.  Keep one matched small-panel R1
    # reference outside successive halving, while every promoted candidate
    # uses R2.  The separately scheduled serial resource pair decides whether
    # sharing delivers the expected engineering benefit.  This prevents the
    # equal R1/R2 accuracy vectors from consuming both full-tier slots.
    r1_accuracy_tuning = deepcopy(baseline)
    r1_accuracy_tuning["redim_execution_strategy"] = "R1_TWO_INDEPENDENT_MODELS"
    jobs.append(
        _runtime_job(
            2,
            "REDIM_EXECUTION_FRONTIER",
            "development",
            "fullpipe_v1_ag_dr_ir",
            "R1_TWO_INDEPENDENT_MODELS_SMALL",
            "H2_SESSION_MEMORY_ENHANCED",
            dev_small,
            r1_accuracy_tuning,
            0.7,
            job_kind="runtime_accuracy",
        )
    )
    for candidate_id, tuning in redim.items():
        for tier, panel, hours in (
            ("small", dev_small, 0.7),
            ("medium", dev_medium, 1.4),
            ("full", dev_core, 3.2),
        ):
            stage_tuning = deepcopy(tuning)
            jobs.append(
                _runtime_job(
                    2,
                    "REDIM_EXECUTION_FRONTIER",
                    "development",
                    "fullpipe_v1_ag_dr_ir",
                    f"{candidate_id}_{tier.upper()}",
                    "H2_SESSION_MEMORY_ENHANCED",
                    panel,
                    stage_tuning,
                    hours,
                    job_kind="successive_halving_runtime",
                    optional=tier != "small",
                )
            )

    for strategy in (
        "R1_TWO_INDEPENDENT_MODELS",
        "R2_ONE_SHARED_MODEL",
    ):
        tuning = deepcopy(baseline)
        tuning["redim_execution_strategy"] = strategy
        jobs.append(
            _runtime_job(
                2,
                "REDIM_EXECUTION_FRONTIER",
                "development",
                "fullpipe_v1_ag_dr_ir",
                f"{strategy}_MATCHED_SERIAL_RESOURCE",
                "H2_SESSION_MEMORY_ENHANCED",
                dev_small,
                tuning,
                1.0,
                job_kind="resource_runtime",
                serial=True,
            )
        )

    # R3/R4 use the real common runtime only inside their dedicated paired
    # executor.  Ordinary campaign jobs remain on R2 until that gate produces
    # measured, checksum-valid development parity and engineering evidence.
    r3_parity = _job(
        2,
        "REDIM_EXECUTION_FRONTIER",
        "embedding_reuse_parity",
        "development",
        "fullpipe_v1_ag_dr_ir",
        "R3_EXACT_WINDOW_EMBEDDING_REUSE",
        "H2_SESSION_MEMORY_ENHANCED",
        baseline,
        dev_small,
        2.0,
    )
    r4_parity = _job(
        2,
        "REDIM_EXECUTION_FRONTIER",
        "embedding_reuse_parity",
        "development",
        "fullpipe_v1_ag_dr_ir",
        "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
        "H2_SESSION_MEMORY_ENHANCED",
        baseline,
        dev_small,
        2.0,
        dependencies=(r3_parity.job_id,),
    )
    jobs.extend((r3_parity, r4_parity))

    # This logical slot has immutable development case membership but receives
    # a new checksum-bound execution identity only after phase-1/phase-2 and
    # boundary/overlap promotion decisions exist.  The controller must never
    # execute its baseline placeholder tuning.
    jobs.append(
        _job(
            2,
            "REDIM_EXECUTION_FRONTIER",
            "post_promotion_integration",
            "development",
            "fullpipe_v1_ag_dr_ir",
            "H2_POST_PROMOTION_INTEGRATION",
            "H2_SESSION_MEMORY_ENHANCED",
            baseline,
            dev_integration,
            10.0,
        )
    )

    jobs.append(
        _job(
            3,
            "IDENTITY_POLICY_FRONTIER",
            "policy_replay",
            "development",
            "fullpipe_v1_ag_dr_ir",
            "H2_IDENTITY_POLICY_GRID",
            "H2_SESSION_MEMORY_ENHANCED",
            baseline,
            dev_core,
            4.0,
        )
    )
    jobs.append(
        _job(
            3,
            "IDENTITY_POLICY_FRONTIER",
            "integrated_enrollment",
            "development",
            "fullpipe_v1_ag_dr_ir",
            "H2_INTEGRATED_ENROLLMENT_CONFIRMATION",
            "H2_SESSION_MEMORY_ENHANCED",
            baseline,
            dev_medium,
            5.0,
        )
    )
    jobs.append(
        _job(
            4,
            "HYSTERESIS_SESSION_MEMORY",
            "memory_policy_replay",
            "development",
            "fullpipe_v1_ag_dr_ir",
            "H2_HYSTERESIS_MEMORY_GRID",
            "H2_SESSION_MEMORY_ENHANCED",
            baseline,
            dev_core,
            5.0,
        )
    )
    jobs.append(
        _job(
            4,
            "HYSTERESIS_SESSION_MEMORY",
            "short_turn_replay",
            "development",
            "fullpipe_v1_ag_dr_ir",
            "H2_SHORT_TURN_REENTRY_EXPIRY",
            "H2_SESSION_MEMORY_ENHANCED",
            baseline,
            dev_core,
            4.0,
        )
    )
    for paragraph_policy in (
        "T1_ASR_ENDPOINT_PUNCTUATION",
        "T2_PAUSE_ASR_ENDPOINT",
        "T3_PAUSE_ASR_SPEAKER_CHANGE",
        "T4_SPEAKER_CHANGE_DOMINANT",
    ):
        tuning = deepcopy(baseline)
        tuning["paragraph_policy"] = paragraph_policy
        jobs.append(
            _runtime_job(
                5,
                "TRANSCRIPT_UI",
                "development",
                "fullpipe_v1_ag_dr_ir",
                paragraph_policy,
                "H2_SESSION_MEMORY_ENHANCED",
                dev_medium,
                tuning,
                1.5,
                job_kind="post_selection_paragraph_validation",
            )
        )
    jobs.append(
        _job(
            5,
            "TRANSCRIPT_UI",
            "transcript_policy_replay",
            "development",
            "fullpipe_v1_ag_dr_ir",
            "H2_BOUNDARY_OVERLAP_PARAGRAPH_GRID",
            "H2_SESSION_MEMORY_ENHANCED",
            baseline,
            dev_core,
            5.0,
        )
    )
    for mode in ("H2_KNOWN_ONLY", "H2_SESSION_ANONYMOUS", "H2_SESSION_MEMORY_ENHANCED"):
        tuning = deepcopy(baseline)
        tuning["product_mode"] = mode
        jobs.append(
            _runtime_job(
                5,
                "TRANSCRIPT_UI",
                "development",
                "fullpipe_v1_ag_dr_ir",
                f"{mode}_DEVELOPMENT",
                mode,
                dev_medium,
                tuning,
                1.6,
                job_kind="post_selection_mode_validation",
            )
        )

    jobs.extend(
        [
            _job(
                6,
                "PORTABILITY_RESOURCE",
                "app_validation",
                "none",
                "NOT_APPLICABLE",
                "H2_CURRENT_COMMON_APP_TARGETED_VALIDATION",
                "NOT_APPLICABLE",
                {},
                None,
                0.25,
                serial=True,
            ),
            _job(
                6,
                "PORTABILITY_RESOURCE",
                "onnx_export",
                "none",
                "NOT_APPLICABLE",
                "H2_PORTABLE_ONNX_FP32_EXPORT",
                "NOT_APPLICABLE",
                {},
                None,
                2.0,
                serial=True,
            ),
            # Portability parity is a separately frozen two-case same-input
            # native-vs-ONNX fixture protocol. It must not claim to execute the
            # 36-case development panel carried by ordinary runtime jobs.
            _job(
                6,
                "PORTABILITY_RESOURCE",
                "onnx_parity",
                "none",
                "NOT_APPLICABLE",
                "H2_PORTABLE_ONNX_FP32_FROZEN_FIXTURE_PARITY",
                "NOT_APPLICABLE",
                {},
                {
                    "case_ids": (
                        "h2_onnx_enrolled_same_input_10s",
                        "h2_onnx_empty_enrollment_same_input_10s",
                    ),
                    "audio_duration_sec": 20.0,
                },
                3.0,
                serial=True,
            ),
            _job(
                6,
                "PORTABILITY_RESOURCE",
                "linux_portability",
                "none",
                "NOT_APPLICABLE",
                "H2_LINUX_ARM64_PACKAGE",
                "NOT_APPLICABLE",
                {},
                None,
                1.0,
                serial=True,
            ),
            _job(
                6,
                "PORTABILITY_RESOURCE",
                "long_session",
                "development",
                "fullpipe_v1_ag_dr_ir",
                "H2_LONG_SESSION_REFERENCE",
                "H2_SESSION_MEMORY_ENHANCED",
                baseline,
                _long_session_execution_panel(dev_long),
                8.0,
                serial=True,
            ),
            _job(
                6,
                "PORTABILITY_RESOURCE",
                "reliability",
                "development",
                "fullpipe_v1_ag_dr_ir",
                "H2_RELIABILITY",
                "H2_SESSION_MEMORY_ENHANCED",
                baseline,
                dev_long,
                3.0,
                serial=True,
            ),
        ]
    )
    for mode in ("H2_KNOWN_ONLY", "H2_SESSION_ANONYMOUS", "H2_SESSION_MEMORY_ENHANCED"):
        tuning = deepcopy(baseline)
        tuning["product_mode"] = mode
        jobs.append(
            _runtime_job(
                6,
                "PORTABILITY_RESOURCE",
                "development",
                "fullpipe_v1_ag_dr_ir",
                f"{mode}_SERIAL_RESOURCE",
                mode,
                dev_small,
                tuning,
                2.0,
                job_kind="post_selection_resource_runtime",
                serial=True,
            )
        )

    freeze_dependencies = tuple(
        job.job_id
        for job in jobs
        if job.phase_index in range(1, 7) and not job.optional
    )
    jobs.append(
        _job(
            7,
            "FREEZE_HELDOUT",
            "freeze",
            "none",
            "NOT_APPLICABLE",
            "H2_DEVELOPMENT_POLICY_FREEZE",
            "NOT_APPLICABLE",
            {},
            None,
            1.0,
            dependencies=freeze_dependencies,
        )
    )
    freeze_id = jobs[-1].job_id
    for mode in ("H2_KNOWN_ONLY", "H2_SESSION_ANONYMOUS", "H2_SESSION_MEMORY_ENHANCED"):
        tuning = deepcopy(baseline)
        tuning["product_mode"] = mode
        jobs.append(
            _runtime_job(
                7,
                "FREEZE_HELDOUT",
                "evaluation",
                "fullpipe_v1_ag_dr_ir",
                f"{mode}_HELDOUT",
                mode,
                eval_core,
                tuning,
                4.0,
                development_only=False,
                dependencies=(freeze_id,),
            )
        )
    fallback = deepcopy(baseline)
    jobs.append(
        _runtime_job(
            7,
            "FREEZE_HELDOUT",
            "evaluation",
            "fullpipe_v1_ao_dr_ir",
            "H2_ORIGINAL_SHERPA_REDUCED_REGRESSION",
            "H2_SESSION_MEMORY_ENHANCED",
            eval_reduced,
            fallback,
            2.0,
            development_only=False,
            dependencies=(freeze_id,),
        )
    )
    diagnostic_ids: list[str] = []
    for name, panel in diagnostics.items():
        job = _runtime_job(
            7,
            "FREEZE_HELDOUT",
            "evaluation",
            "fullpipe_v1_ag_dr_ir",
            f"H2_{name.upper()}",
            "H2_SESSION_MEMORY_ENHANCED",
            _mapping(diagnostics, name),
            baseline,
            2.0,
            job_kind="diagnostic_runtime",
            development_only=False,
            dependencies=(freeze_id,),
        )
        jobs.append(job)
        diagnostic_ids.append(job.job_id)
    heldout_long = _job(
        7,
        "FREEZE_HELDOUT",
        "long_session_evaluation",
        "evaluation",
        "fullpipe_v1_ag_dr_ir",
        "H2_LONG_SESSION_HELDOUT_8SOURCE_30M_60M",
        "H2_SESSION_MEMORY_ENHANCED",
        baseline,
        _long_session_execution_panel(eval_long),
        12.0,
        serial=True,
        development_only=False,
        dependencies=(freeze_id,),
    )
    jobs.append(heldout_long)
    jobs.extend(
        [
            _job(
                7,
                "FREEZE_HELDOUT",
                "bootstrap",
                "none",
                "NOT_APPLICABLE",
                "H2_SPEAKER_HIERARCHICAL_BOOTSTRAP",
                "NOT_APPLICABLE",
                {},
                None,
                3.0,
                development_only=False,
                dependencies=tuple(
                    job.job_id
                    for job in jobs
                    if job.phase_index == 7
                    and job.job_kind in {"runtime_accuracy", "diagnostic_runtime"}
                ),
            ),
            _job(
                7,
                "FREEZE_HELDOUT",
                "analysis",
                "none",
                "NOT_APPLICABLE",
                "H2_FINAL_ANALYSIS",
                "NOT_APPLICABLE",
                {},
                None,
                2.0,
                development_only=False,
                dependencies=(heldout_long.job_id,),
            ),
            _job(
                7,
                "FREEZE_HELDOUT",
                "collection",
                "none",
                "NOT_APPLICABLE",
                "H2_FINAL_COLLECTION",
                "NOT_APPLICABLE",
                {},
                None,
                1.0,
                development_only=False,
            ),
        ]
    )

    _validate_jobs(jobs)
    core = {
        "schema_version": "h2-product-job-manifest.v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol["protocol_sha256"],
        "job_count": len(jobs),
        "accuracy_parallelism_max": 2,
        "resource_parallelism": 1,
        "successive_halving": {
            "phase_1": {
                "small_candidates": len(segmentation),
                "medium_max": 4,
                "full_max": 2,
            },
            "phase_2": {
                "small_candidates": len(redim),
                "medium_max": 4,
                "full_max": 2,
                "fixed_execution_strategy": "R2_ONE_SHARED_MODEL",
                "duplicate_executable_tunings_allowed": False,
                "r1_accuracy_reference_outside_promotion": True,
            },
            "promotion_uses_development_only": True,
        },
        "heldout_job_count": sum(job.split == "evaluation" for job in jobs),
        "estimated_wall_hours_before_measured_smoke": sum(
            job.estimated_wall_hours for job in jobs if not job.optional
        )
        + 4 * 1.5
        + 2 * 3.3
        + 4 * 1.4
        + 2 * 3.1,
        "jobs": [job.to_jsonable() for job in jobs],
    }
    return {**core, "job_manifest_sha256": canonical_sha256(core)}


def _baseline_tuning(protocol: Mapping[str, object]) -> dict[str, object]:
    baseline = deepcopy(_mapping(protocol, "historical_baseline"))
    segmentation = _mapping(baseline, "segmentation")
    embedding = _mapping(baseline, "embedding")
    clustering = _mapping(baseline, "clustering")
    identity = _mapping(baseline, "identity")
    return {
        "schema_version": "h2-runtime-tuning.v1",
        "product_mode": "H2_SESSION_ANONYMOUS",
        "segmentation_hop_sec": float(segmentation["hop_duration_sec"]),
        "segmentation_onset": float(segmentation["onset"]),
        "segmentation_offset": float(segmentation["offset"]),
        "segmentation_min_speech_sec": 0.0,
        "segmentation_min_silence_sec": 0.0,
        "embedding_window_sec": float(embedding["window_duration_sec"]),
        "embedding_hop_sec": float(embedding["hop_duration_sec"]),
        "minimum_embedding_sec": float(embedding["minimum_duration_sec"]),
        "clustering_threshold": float(clustering["cosine_threshold"]),
        "short_turn_attach_gap_sec": float(clustering["short_turn_attach_gap_sec"]),
        "redim_execution_strategy": str(embedding["sharing_strategy"]),
        "overlap_policy": baseline["overlap_policy"],
        "boundary_correction_ms": int(baseline["boundary_correction_ms"]),
        "paragraph_policy": str(baseline["paragraph_policy"]),
        "identity_accumulation": "accumulated_window",
        "score_threshold": float(identity["score_threshold"]),
        "margin_threshold": float(identity["margin_threshold"]),
        "minimum_evidence_sec": float(identity["minimum_evidence_sec"]),
        "minimum_embedding_consistency": float(identity["minimum_consistency"]),
        "consecutive_passes_to_confirm": 2,
        "hysteresis": 0.02,
        "identity_expiry_sec": float(identity["expiry_sec"]),
    }


def _segmentation_candidates(
    baseline: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    values: dict[str, dict[str, object]] = {}
    candidates = {
        "S0_HISTORICAL": {},
        "S1_COVERAGE": {
            "onset": 0.42,
            "offset": 0.40,
            "minimum_speech_sec": 0.10,
            "minimum_silence_sec": 0.10,
            "speech_padding_sec": 0.10,
            "short_gap_merge_sec": 0.25,
        },
        "S2_BALANCED": {
            "onset": 0.46,
            "offset": 0.45,
            "minimum_speech_sec": 0.10,
            "minimum_silence_sec": 0.20,
            "speech_padding_sec": 0.10,
            "short_gap_merge_sec": 0.25,
        },
        "S3_PRECISION": {
            "onset": 0.58,
            "offset": 0.55,
            "minimum_speech_sec": 0.20,
            "minimum_silence_sec": 0.20,
            "speech_padding_sec": 0.0,
            "short_gap_merge_sec": 0.10,
        },
        "S4_SHORT_TURN": {
            "onset": 0.42,
            "offset": 0.40,
            "minimum_speech_sec": 0.05,
            "minimum_silence_sec": 0.05,
            "speech_padding_sec": 0.10,
            "short_gap_merge_sec": 0.10,
        },
        "S5_HOP_025": {"hop_duration_sec": 0.25},
        "S6_HOP_050": {"hop_duration_sec": 0.50},
        "S7_HOP_100": {"hop_duration_sec": 1.0},
    }
    for candidate_id, updates in candidates.items():
        tuning = deepcopy(dict(baseline))
        translated = {
            {
                "hop_duration_sec": "segmentation_hop_sec",
                "onset": "segmentation_onset",
                "offset": "segmentation_offset",
                "minimum_speech_sec": "segmentation_min_speech_sec",
                "minimum_silence_sec": "segmentation_min_silence_sec",
            }[key]: value
            for key, value in updates.items()
            if key
            in {
                "hop_duration_sec",
                "onset",
                "offset",
                "minimum_speech_sec",
                "minimum_silence_sec",
            }
        }
        tuning.update(translated)
        values[candidate_id] = tuning
    return values


def _redim_candidates(baseline: Mapping[str, object]) -> dict[str, dict[str, object]]:
    values: dict[str, dict[str, object]] = {}
    # R2 is the single execution-strategy baseline in the accuracy frontier.
    # R1 receives its own matched small-panel accuracy and serial-resource jobs
    # in build_job_manifest; it must not compete as an equal-output promotion
    # candidate.
    shared = deepcopy(dict(baseline))
    shared["redim_execution_strategy"] = "R2_ONE_SHARED_MODEL"
    values["R2_ONE_SHARED_MODEL"] = shared
    for name, duration, hop in (
        ("W050_H025", 0.50, 0.25),
        ("W075_H025", 0.75, 0.25),
        ("W100_H050", 1.0, 0.50),
        ("W200_H100", 2.0, 1.0),
        ("W300_H100", 3.0, 1.0),
    ):
        tuning = deepcopy(dict(baseline))
        tuning["embedding_window_sec"] = duration
        tuning["embedding_hop_sec"] = hop
        tuning["minimum_embedding_sec"] = min(
            float(tuning["minimum_embedding_sec"]), duration
        )
        values[name] = tuning
    return values


def _clustering_attach_candidates(
    baseline: Mapping[str, object],
    declaration: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Bounded one-axis frontier; deliberately not a Cartesian expansion."""

    thresholds = tuple(
        float(value) for value in declaration.get("clustering_threshold", ())
    )
    attach_gaps = tuple(
        float(value) for value in declaration.get("short_turn_attach_gap_sec", ())
    )
    if thresholds != (0.25, 0.35, 0.45):
        raise H2ProgramError("predeclared clustering threshold frontier differs")
    if attach_gaps != (0.25, 0.50, 0.75):
        raise H2ProgramError("predeclared short-turn attach-gap frontier differs")
    candidates = {
        "C1_CLUSTER_THRESHOLD_025": {"clustering_threshold": 0.25},
        "C2_CLUSTER_THRESHOLD_045": {"clustering_threshold": 0.45},
        "C3_SHORT_ATTACH_GAP_025": {"short_turn_attach_gap_sec": 0.25},
        "C4_SHORT_ATTACH_GAP_075": {"short_turn_attach_gap_sec": 0.75},
    }
    return {
        candidate_id: {**deepcopy(dict(baseline)), **updates}
        for candidate_id, updates in candidates.items()
    }


def _require_unique_candidate_tunings(
    candidates: Mapping[str, Mapping[str, object]],
) -> None:
    """Fail preparation if two promotion labels execute identical tuning."""

    by_identity: dict[str, str] = {}
    duplicates: list[str] = []
    for candidate_id, tuning in candidates.items():
        identity = canonical_sha256(dict(tuning))
        previous = by_identity.setdefault(identity, candidate_id)
        if previous != candidate_id:
            duplicates.append(f"{previous} == {candidate_id}")
    if duplicates:
        raise H2ProgramError(
            "phase-2 promotion candidates contain duplicate executable tuning: "
            + "; ".join(duplicates)
        )


def _long_session_execution_panel(
    panel: Mapping[str, object],
) -> dict[str, object]:
    source_count = int(panel.get("source_count") or 0)
    if source_count not in {4, 8}:
        raise H2ProgramError("long-session panel must contain four or eight sources")
    target_audio_sec = source_count * (30.0 + 60.0) * 60.0
    return {
        **deepcopy(dict(panel)),
        "audio_duration_sec": target_audio_sec,
        "stream_count": source_count * 2,
        "target_durations_sec": [1800.0, 3600.0],
        "source_hours": target_audio_sec / 3600.0,
    }


def _runtime_job(
    phase: int,
    phase_name: str,
    split: str,
    pipeline_id: str,
    config_id: str,
    mode: str,
    panel: Mapping[str, object],
    tuning: Mapping[str, object],
    hours: float,
    *,
    job_kind: str = "runtime_accuracy",
    optional: bool = False,
    serial: bool = False,
    development_only: bool = True,
    dependencies: Sequence[str] = (),
) -> H2Job:
    executable_tuning = deepcopy(dict(tuning))
    if mode in {
        "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_ENHANCED",
    }:
        executable_tuning["product_mode"] = mode
    return _job(
        phase,
        phase_name,
        job_kind,
        split,
        pipeline_id,
        config_id,
        mode,
        executable_tuning,
        panel,
        hours,
        optional=optional,
        serial=serial,
        development_only=development_only,
        dependencies=dependencies,
    )


def _job(
    phase: int,
    phase_name: str,
    job_kind: str,
    split: str,
    pipeline_id: str,
    config_id: str,
    mode: str,
    tuning: Mapping[str, object],
    panel: Mapping[str, object] | None,
    hours: float,
    *,
    optional: bool = False,
    serial: bool = False,
    development_only: bool = True,
    dependencies: Sequence[str] = (),
) -> H2Job:
    bound_tuning = deepcopy(dict(tuning))
    if (
        mode
        in {
            "H2_KNOWN_ONLY",
            "H2_SESSION_ANONYMOUS",
            "H2_SESSION_MEMORY_ENHANCED",
        }
        and bound_tuning
    ):
        bound_tuning["product_mode"] = mode
    case_ids = tuple(str(value) for value in (panel or {}).get("case_ids", ()))
    digest = canonical_sha256(
        {
            "phase": phase,
            "kind": job_kind,
            "pipeline": pipeline_id,
            "config": config_id,
            "mode": mode,
            "cases": case_ids,
            "tuning": bound_tuning,
        }
    )
    return H2Job(
        job_id=f"h2p{phase}_{_portable(config_id)}_{digest[:10]}",
        phase_index=phase,
        phase_name=phase_name,
        job_kind=job_kind,
        split=split,
        pipeline_id=pipeline_id,
        configuration_id=config_id,
        mode=mode,
        case_ids=case_ids,
        audio_duration_sec=float((panel or {}).get("audio_duration_sec") or 0.0),
        runtime_tuning=bound_tuning,
        dependencies=tuple(dependencies),
        serial=serial,
        development_only=development_only,
        optional=optional,
        estimated_wall_hours=hours,
    )


def _validate_jobs(jobs: Iterable[H2Job]) -> None:
    values = tuple(jobs)
    ids = {job.job_id for job in values}
    if len(ids) != len(values):
        raise H2ProgramError("duplicate H2 job IDs")
    for job in values:
        missing = set(job.dependencies) - ids
        if missing:
            raise H2ProgramError(
                f"job {job.job_id} has missing dependencies: {sorted(missing)}"
            )
        if job.pipeline_id not in {
            "fullpipe_v1_ag_dr_ir",
            "fullpipe_v1_ao_dr_ir",
            "NOT_APPLICABLE",
        }:
            raise H2ProgramError(f"non-H2 job escaped planning: {job.job_id}")
    heldout = [job for job in values if job.split == "evaluation"]
    if not heldout or any(job.development_only for job in heldout):
        raise H2ProgramError("held-out jobs are missing or incorrectly marked")


def _mapping(value: Mapping[str, object], key: str) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise H2ProgramError(f"required mapping missing: {key}")
    return dict(item)


def _portable(value: str) -> str:
    return "_".join(
        part
        for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split()
    )


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_RESULTS_ROOT",
    "DEFAULT_SUMMARY_ROOT",
    "DEFAULT_WORKSPACE",
    "EVALUATION_ROOT",
    "HISTORICAL_EVIDENCE_PATH",
    "PREPARED_PROTOCOL_ROOT",
    "build_job_manifest",
    "build_protocol_manifest",
    "default_paths",
    "load_and_validate_spec",
]
