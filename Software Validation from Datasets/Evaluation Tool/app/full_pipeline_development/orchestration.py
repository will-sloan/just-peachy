"""Restart-safe, development-only orchestration for Prompt 4.

The scientific work is deliberately split into immutable campaign roots:

* challenger calibration (56 cases, 12 non-anchor pipelines);
* one-case all-18 cold/shared integrated qualification;
* the complete 807-case all-18 development campaign; and
* a serial, two-source resource spot panel.

This module delegates execution to :mod:`app.full_pipeline_evaluation.controller`.
It never exposes a held-out/evaluation action and verifies every prepared
manifest again before allowing a run.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Mapping, Sequence

from app.full_pipeline_evaluation import controller as evaluation_controller
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import (
    DEFAULT_RESULTS_ROOT,
    DEFAULT_SEED,
    EVALUATION_ROOT,
    matrix,
)
from app.full_pipeline_evaluation.protocol import load_cases
from app.full_pipeline_evaluation.store import EvaluationJobSpec, EvaluationStateStore

from .policies import (
    build_development_policy_registry,
    challenger_pipeline_ids,
    select_development_calibration_cases,
    validate_development_policy_registry,
    write_development_policy_registry,
)
from .qualification_execution import (
    finalize_qualification as seal_qualification,
    qualify_component_restarts,
)
from .evidence import (
    combine_development_evidence,
    freeze_development_outputs,
)


ORCHESTRATION_SCHEMA_VERSION = "full-pipeline-development-orchestration.v1"
CALIBRATION_STAGE = "prompt4_challenger_calibration"
QUALIFICATION_SHARED_STAGE = "prompt4_qualification_shared"
QUALIFICATION_COLD_STAGE = "prompt4_qualification_cold"
DEVELOPMENT_STAGE = "prompt4_all18_development_accuracy"
RESOURCES_STAGE = "prompt4_resource_spots"
EXPECTED_DEVELOPMENT_CASES = 807
EXPECTED_CALIBRATION_CASES = 56
DEFAULT_ROOT = EVALUATION_ROOT / "automated_runs/full_pipeline_development_v1"


@dataclass(frozen=True)
class DevelopmentRunLayout:
    """Physical roots for the five immutable Prompt-4 campaigns."""

    root: Path
    calibration: Path
    qualification_shared: Path
    qualification_cold: Path
    development: Path
    resources: Path
    frozen: Path
    policy_registry: Path
    qualification: Path
    qualification_plan: Path
    qualification_bundle: Path
    qualification_evidence: Path
    qualification_restart_manifest: Path
    combined_evidence: Path
    frozen_pipeline_configs: Path
    orchestration_plan: Path
    qualification_execution_plan: Path


def layout(root: Path = DEFAULT_ROOT) -> DevelopmentRunLayout:
    base = Path(root).resolve()
    frozen = base / "frozen"
    qualification = base / "qualification"
    return DevelopmentRunLayout(
        root=base,
        calibration=base / "calibration",
        qualification_shared=base / "qualification_shared",
        qualification_cold=base / "qualification_cold",
        development=base / "development_accuracy",
        resources=base / "resource_spots",
        frozen=frozen,
        policy_registry=frozen / "decision_policy_registry.json",
        qualification=qualification,
        qualification_plan=qualification / "qualification_plan.json",
        qualification_bundle=qualification / "qualification.json",
        qualification_evidence=qualification / "evidence",
        qualification_restart_manifest=(
            qualification / "evidence/restarts/restart_manifest.json"
        ),
        combined_evidence=base / "combined_evidence",
        frozen_pipeline_configs=base / "frozen_pipeline_configs",
        orchestration_plan=base / "orchestration_plan.json",
        qualification_execution_plan=base / "qualification_execution_plan.json",
    )


def plan(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    """Write the exact model-free Prompt-4 stage plan."""

    paths = layout(workspace_root)
    development = _development_cases()
    calibration = _calibration_cases(development)
    qualification = _qualification_cases(development)
    resources = _resource_spot_cases(development)
    challengers = challenger_pipeline_ids()
    all_pipelines = matrix().pipeline_ids
    value: dict[str, object] = {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "PASS",
        "workspace_root": str(paths.root),
        "development_only": True,
        "held_out_evaluation_allowed": False,
        "production_winner_selected": False,
        "seed": DEFAULT_SEED,
        "stages": {
            "calibration": {
                "campaign_stage": CALIBRATION_STAGE,
                "workspace_root": str(paths.calibration),
                "case_count": len(calibration),
                "case_ids": [_case_id(row) for row in calibration],
                "pipeline_count": len(challengers),
                "pipeline_ids": list(challengers),
                "measurement_modes": ["accuracy"],
                "parallel_jobs": 2,
                "purpose": "raw_unknown_scores_for_challenger_policy_freeze",
            },
            "qualification": {
                "shared_campaign_stage": QUALIFICATION_SHARED_STAGE,
                "cold_campaign_stage": QUALIFICATION_COLD_STAGE,
                "shared_workspace_root": str(paths.qualification_shared),
                "cold_workspace_root": str(paths.qualification_cold),
                "case_count": len(qualification),
                "case_ids": [_case_id(row) for row in qualification],
                "pipeline_count": len(all_pipelines),
                "pipeline_ids": list(all_pipelines),
                "measurement_modes": ["accuracy"],
                "shared_parallel_jobs": 2,
                "cold_parallel_jobs": 1,
                "cold_vs_shared_equivalence_required": True,
            },
            "development": {
                "campaign_stage": DEVELOPMENT_STAGE,
                "workspace_root": str(paths.development),
                "case_count": len(development),
                "case_ids": [_case_id(row) for row in development],
                "pipeline_count": len(all_pipelines),
                "pipeline_ids": list(all_pipelines),
                "measurement_modes": ["accuracy"],
                "parallel_jobs": 2,
            },
            "resources": {
                "campaign_stage": RESOURCES_STAGE,
                "workspace_root": str(paths.resources),
                "case_count": len(resources),
                "case_ids": [_case_id(row) for row in resources],
                "source_keys": [str(row["source_key"]) for row in resources],
                "pipeline_count": len(all_pipelines),
                "pipeline_ids": list(all_pipelines),
                "measurement_modes": ["resources"],
                "parallel_jobs": 1,
                "isolated_component_cache_per_attempt": True,
            },
        },
        "postprocessing": {
            "qualification_bundle": str(paths.qualification_bundle),
            "combined_manifest": str(
                paths.combined_evidence / "campaign_manifest.json"
            ),
            "combined_analysis": str(
                paths.combined_evidence / "analysis/analysis.json"
            ),
            "frozen_pipeline_configs": str(paths.frozen_pipeline_configs),
            "model_inference_performed": False,
        },
    }
    _write_or_verify(paths.orchestration_plan, value)
    return value


def prepare_calibration(
    *, workspace_root: Path = DEFAULT_ROOT, seed: int = DEFAULT_SEED
) -> dict[str, object]:
    paths = layout(workspace_root)
    cases = _calibration_cases(_development_cases())
    result = evaluation_controller.prepare(
        workspace_root=paths.calibration,
        seed=seed,
        case_ids=tuple(_case_id(row) for row in cases),
        pipeline_ids=challenger_pipeline_ids(),
        measurement_modes=("accuracy",),
        campaign_stage=CALIBRATION_STAGE,
    )
    _require_stage_manifest(
        paths.calibration,
        stage=CALIBRATION_STAGE,
        cases=cases,
        pipeline_ids=challenger_pipeline_ids(),
        measurement_modes=("accuracy",),
        registry_path=None,
    )
    return _stage_result("PrepareCalibration", result)


def run_calibration(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    cases = _calibration_cases(_development_cases())
    pipelines = challenger_pipeline_ids()
    _require_stage_manifest(
        paths.calibration,
        stage=CALIBRATION_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        registry_path=None,
    )
    return _stage_result(
        "RunCalibration",
        evaluation_controller.run_development(
            workspace_root=paths.calibration,
            measurement_mode="accuracy",
            pipeline_ids=pipelines,
            parallel_jobs=2,
        ),
    )


def freeze_policies(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    policy_registry_path: Path | None = None,
) -> dict[str, object]:
    """Freeze challenger policies from complete calibration diagnostics only."""

    paths = layout(workspace_root)
    cases = _calibration_cases(_development_cases())
    pipelines = challenger_pipeline_ids()
    manifest = _require_stage_manifest(
        paths.calibration,
        stage=CALIBRATION_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        registry_path=None,
    )
    checked = evaluation_controller.validate(workspace_root=paths.calibration)
    if checked.get("valid") is not True:
        raise RuntimeError("calibration campaign validation failed")
    observations, evidence = _calibration_observations(paths.calibration, manifest)
    registry = build_development_policy_registry(
        observations,
        protocol_id=str(manifest["full_protocol_id"]),
        development_identity_sha256=str(manifest["development_identity"]),
        expected_pipeline_ids=pipelines,
    )
    target = Path(policy_registry_path or paths.policy_registry).resolve()
    if target.is_file():
        existing = read_json(target)
        if canonical_json_bytes(existing) != canonical_json_bytes(registry):
            raise RuntimeError("immutable development policy registry differs")
        validate_development_policy_registry(existing)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        write_development_policy_registry(target, registry)
    freeze_record = {
        "schema_version": "full-pipeline-development-policy-freeze-evidence.v1",
        "status": "PASS",
        "campaign_id": manifest["campaign_id"],
        "campaign_stage": CALIBRATION_STAGE,
        "calibration_partition": "development",
        "calibration_case_count": len(cases),
        "challenger_pipeline_count": len(pipelines),
        "observation_count": len(observations),
        "diagnostic_files": evidence,
        "policy_registry_path": str(target),
        "policy_registry_file_sha256": sha256_file(target),
        "policy_registry_identity_sha256": registry["registry_identity_sha256"],
        "evaluation_material_inspected": False,
    }
    _write_or_verify(paths.frozen / "calibration_freeze.json", freeze_record)
    return freeze_record


def prepare_qualification(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    policy_registry_path: Path | None = None,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    paths = layout(workspace_root)
    registry = _require_policy_registry(policy_registry_path or paths.policy_registry)
    cases = _qualification_cases(_development_cases())
    pipelines = matrix().pipeline_ids
    shared = evaluation_controller.prepare(
        workspace_root=paths.qualification_shared,
        seed=seed,
        case_ids=tuple(_case_id(row) for row in cases),
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        campaign_stage=QUALIFICATION_SHARED_STAGE,
        decision_policy_registry_path=registry,
    )
    cold = evaluation_controller.prepare(
        workspace_root=paths.qualification_cold,
        seed=seed,
        case_ids=tuple(_case_id(row) for row in cases),
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        campaign_stage=QUALIFICATION_COLD_STAGE,
        decision_policy_registry_path=registry,
    )
    for campaign_root, stage in (
        (paths.qualification_shared, QUALIFICATION_SHARED_STAGE),
        (paths.qualification_cold, QUALIFICATION_COLD_STAGE),
    ):
        _require_stage_manifest(
            campaign_root,
            stage=stage,
            cases=cases,
            pipeline_ids=pipelines,
            measurement_modes=("accuracy",),
            registry_path=registry,
        )
    execution_plan = {
        "schema_version": "full-pipeline-development-qualification-execution.v1",
        "status": "PREPARED",
        "split": "development",
        "case_id": _case_id(cases[0]),
        "pipeline_ids": list(pipelines),
        "cold": {
            "workspace_root": str(paths.qualification_cold),
            "execution_origin": "primary_computed",
            "persistent_worker_reuse": False,
            "asr_stream_trace_replay": False,
            "component_cache": "attempt_local_empty_namespace",
            "parallel_jobs": 1,
        },
        "shared": {
            "workspace_root": str(paths.qualification_shared),
            "allowed_execution_origins": ["primary_computed", "accuracy_replayed"],
            "persistent_worker_reuse": True,
            "asr_stream_trace_replay": True,
            "parallel_jobs": 2,
        },
        "required_equivalence": [
            "labelled_transcript_semantic_sha256",
            "event_sequence_semantic_sha256",
            "known_unknown_decisions",
            "clean_shutdown",
            "restart",
        ],
        "evaluation_material_inspected": False,
    }
    _write_or_verify(paths.qualification_execution_plan, execution_plan)
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "PASS",
        "action": "PrepareQualification",
        "shared": shared,
        "cold": cold,
        "execution_plan": execution_plan,
    }


def run_qualification(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    policy_registry_path: Path | None = None,
) -> dict[str, object]:
    """Run one cold and one shared integrated development smoke per pipeline."""

    paths = layout(workspace_root)
    cold_registry = _require_policy_registry(
        policy_registry_path
        or paths.qualification_cold / "decision_policy_registry.json"
    )
    shared_registry = _require_policy_registry(
        policy_registry_path
        or paths.qualification_shared / "decision_policy_registry.json"
    )
    cases = _qualification_cases(_development_cases())
    pipelines = matrix().pipeline_ids
    _require_stage_manifest(
        paths.qualification_cold,
        stage=QUALIFICATION_COLD_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        registry_path=cold_registry,
    )
    _require_stage_manifest(
        paths.qualification_shared,
        stage=QUALIFICATION_SHARED_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        registry_path=shared_registry,
    )
    cold = evaluation_controller.run_development(
        workspace_root=paths.qualification_cold,
        measurement_mode="accuracy",
        pipeline_ids=pipelines,
        parallel_jobs=1,
        job_executor=_isolated_job_executor(
            cold_registry, measurement_mode="accuracy"
        ),
    )
    if str(cold.get("status") or "").upper() not in {"PASS", "COMPLETE"}:
        return _stage_result("RunQualificationCold", cold)
    shared = evaluation_controller.run_development(
        workspace_root=paths.qualification_shared,
        measurement_mode="accuracy",
        pipeline_ids=pipelines,
        parallel_jobs=2,
    )
    if str(shared.get("status") or "").upper() not in {"PASS", "COMPLETE"}:
        return _stage_result("RunQualificationShared", shared)
    restarts = qualify_restarts(workspace_root=paths.root)
    finalized = finalize_qualification(workspace_root=paths.root)
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "PASS",
        "action": "RunQualification",
        "cold": cold,
        "shared": shared,
        "component_restarts": restarts,
        "qualification": finalized,
        "cold_vs_shared_comparison_pending": False,
    }


def qualify_restarts(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    """Exercise actual restart/identity/clean-shutdown for six unique workers."""

    paths = layout(workspace_root)
    return qualify_component_restarts(paths.qualification)


def finalize_qualification(
    *, workspace_root: Path = DEFAULT_ROOT
) -> dict[str, object]:
    """Seal complete cold/shared runs into the exact 15-check qualification bundle."""

    paths = layout(workspace_root)
    cases = _qualification_cases(_development_cases())
    return seal_qualification(
        cold_workspace=paths.qualification_cold,
        shared_workspace=paths.qualification_shared,
        qualification_root=paths.qualification,
        case=cases[0],
    )


def prepare_development(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    policy_registry_path: Path | None = None,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    paths = layout(workspace_root)
    registry = _require_policy_registry(policy_registry_path or paths.policy_registry)
    cases = _development_cases()
    pipelines = matrix().pipeline_ids
    result = evaluation_controller.prepare(
        workspace_root=paths.development,
        seed=seed,
        case_ids=tuple(_case_id(row) for row in cases),
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        campaign_stage=DEVELOPMENT_STAGE,
        decision_policy_registry_path=registry,
    )
    _require_stage_manifest(
        paths.development,
        stage=DEVELOPMENT_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        registry_path=registry,
    )
    return _stage_result("PrepareDevelopment", result)


def run_development(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    registry = _require_policy_registry(
        paths.development / "decision_policy_registry.json"
    )
    cases = _development_cases()
    pipelines = matrix().pipeline_ids
    _require_stage_manifest(
        paths.development,
        stage=DEVELOPMENT_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("accuracy",),
        registry_path=registry,
    )
    return _stage_result(
        "RunDevelopment",
        evaluation_controller.run_development(
            workspace_root=paths.development,
            measurement_mode="accuracy",
            pipeline_ids=pipelines,
            parallel_jobs=2,
        ),
    )


def prepare_resources(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    policy_registry_path: Path | None = None,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    paths = layout(workspace_root)
    registry = _require_policy_registry(policy_registry_path or paths.policy_registry)
    cases = _resource_spot_cases(_development_cases())
    pipelines = matrix().pipeline_ids
    result = evaluation_controller.prepare(
        workspace_root=paths.resources,
        seed=seed,
        case_ids=tuple(_case_id(row) for row in cases),
        pipeline_ids=pipelines,
        measurement_modes=("resources",),
        campaign_stage=RESOURCES_STAGE,
        decision_policy_registry_path=registry,
    )
    _require_stage_manifest(
        paths.resources,
        stage=RESOURCES_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("resources",),
        registry_path=registry,
    )
    return _stage_result("PrepareResources", result)


def run_resources(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    registry = _require_policy_registry(
        paths.resources / "decision_policy_registry.json"
    )
    cases = _resource_spot_cases(_development_cases())
    pipelines = matrix().pipeline_ids
    _require_stage_manifest(
        paths.resources,
        stage=RESOURCES_STAGE,
        cases=cases,
        pipeline_ids=pipelines,
        measurement_modes=("resources",),
        registry_path=registry,
    )
    return _stage_result(
        "RunResources",
        evaluation_controller.run_development(
            workspace_root=paths.resources,
            measurement_mode="resources",
            pipeline_ids=pipelines,
            parallel_jobs=1,
            job_executor=_isolated_job_executor(registry, measurement_mode="resources"),
        ),
    )


def combine_evidence(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    """Combine complete accuracy and serial-resource campaigns without inference."""

    paths = layout(workspace_root)
    return combine_development_evidence(
        output_workspace_root=paths.combined_evidence,
        accuracy_workspace_root=paths.development,
        resource_workspace_root=paths.resources,
    )


def freeze_development(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    """Freeze exact all-18 configurations after combined evidence/qualification."""

    paths = layout(workspace_root)
    anchor_path = paths.qualification / "anchor_runtime_qualification.json"
    if not anchor_path.is_file():
        raise RuntimeError("finalized runtime-anchor qualification is missing")
    if not (paths.combined_evidence / "campaign_manifest.json").is_file():
        raise RuntimeError("combined development evidence is missing")
    registry = _require_policy_registry(paths.policy_registry)
    return freeze_development_outputs(
        combined_workspace_root=paths.combined_evidence,
        policy_registry=registry,
        runtime_anchor_qualification=read_json(anchor_path),
        frozen_config_root=paths.frozen_pipeline_configs,
    )


def status(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    stage_roots = {
        "calibration": paths.calibration,
        "qualification_cold": paths.qualification_cold,
        "qualification_shared": paths.qualification_shared,
        "development": paths.development,
        "resources": paths.resources,
    }
    stages: dict[str, object] = {}
    for name, root in stage_roots.items():
        if not (root / "campaign_manifest.json").is_file():
            stages[name] = {"status": "NOT_PREPARED", "workspace_root": str(root)}
            continue
        stages[name] = evaluation_controller.status(workspace_root=root)
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "PASS",
        "workspace_root": str(paths.root),
        "policy_registry": {
            "status": "FROZEN" if paths.policy_registry.is_file() else "NOT_FROZEN",
            "path": str(paths.policy_registry),
            "sha256": sha256_file(paths.policy_registry)
            if paths.policy_registry.is_file()
            else None,
        },
        "qualification": {
            "status": "PASS" if paths.qualification_bundle.is_file() else "PENDING",
            "path": str(paths.qualification_bundle),
        },
        "combined_evidence": {
            "status": "PASS"
            if (paths.combined_evidence / "campaign_manifest.json").is_file()
            else "PENDING",
            "workspace_root": str(paths.combined_evidence),
        },
        "frozen_pipeline_configs": {
            "status": "FROZEN"
            if (paths.frozen_pipeline_configs / "checksums.json").is_file()
            else "PENDING",
            "path": str(paths.frozen_pipeline_configs),
        },
        "stages": stages,
        "held_out_evaluation_started": False,
    }


def stop(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    stopped: dict[str, object] = {}
    for name, root in (
        ("calibration", paths.calibration),
        ("qualification_cold", paths.qualification_cold),
        ("qualification_shared", paths.qualification_shared),
        ("development", paths.development),
        ("resources", paths.resources),
    ):
        if (root / "campaign_manifest.json").is_file():
            stopped[name] = evaluation_controller.stop(workspace_root=root)
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "STOP_REQUESTED",
        "stages": stopped,
    }


def _development_cases() -> tuple[dict[str, object], ...]:
    cases = tuple(
        dict(row)
        for row in load_cases()
        if str(row.get("split") or row.get("partition") or "") == "development"
    )
    _assert_development_only(cases)
    if len(cases) != EXPECTED_DEVELOPMENT_CASES:
        raise RuntimeError(
            "Prompt-4 requires the exact 807-case development protocol; "
            f"observed={len(cases)}"
        )
    return tuple(sorted(cases, key=lambda row: _case_id(row)))


def _calibration_cases(
    development: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    cases = select_development_calibration_cases(development)
    if len(cases) != EXPECTED_CALIBRATION_CASES:
        raise RuntimeError(
            "Prompt-4 challenger calibration requires exactly 56 cases; "
            f"observed={len(cases)}"
        )
    _assert_development_only(cases)
    return cases


def _qualification_cases(
    development: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    candidates = [
        dict(row)
        for row in development
        if str(row.get("source_key") or "") == "product_v2"
        and str(row.get("overlay_id") or "") == "MIXED_KNOWN_UNKNOWN"
        and int(row.get("known_speaker_count") or 0) > 0
        and int(row.get("unknown_speaker_count") or 0) > 0
        and str(row.get("gallery_requested_size") or "") == "10"
        and float(row.get("duration_sec") or 0.0) >= 2.0
    ]
    if not candidates:
        raise RuntimeError("no short mixed development qualification case exists")
    selected = min(
        candidates,
        key=lambda row: (float(row["duration_sec"]), _case_id(row)),
    )
    _assert_development_only((selected,))
    return (selected,)


def _resource_spot_cases(
    development: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    selected: list[dict[str, object]] = []
    for source_key in ("controlled_v1", "product_v2"):
        candidates = [
            dict(row)
            for row in development
            if str(row.get("source_key") or "") == source_key
            and str(row.get("overlay_id") or "") == "MIXED_KNOWN_UNKNOWN"
            and int(row.get("known_speaker_count") or 0) > 0
            and int(row.get("unknown_speaker_count") or 0) > 0
            and (
                source_key != "product_v2"
                or str(row.get("gallery_requested_size") or "") == "10"
            )
        ]
        if not candidates:
            raise RuntimeError(f"no mixed resource spot exists for {source_key}")
        selected.append(
            min(
                candidates,
                key=lambda row: (float(row["duration_sec"]), _case_id(row)),
            )
        )
    rows = tuple(sorted(selected, key=lambda row: str(row["source_key"])))
    _assert_development_only(rows)
    return rows


def _assert_development_only(cases: Sequence[Mapping[str, object]]) -> None:
    invalid = [
        _case_id(row)
        for row in cases
        if str(row.get("split") or row.get("partition") or "") != "development"
    ]
    if invalid:
        raise RuntimeError(
            "held-out/evaluation cases are forbidden in Prompt 4: "
            + ", ".join(sorted(invalid)[:5])
        )


def _require_stage_manifest(
    workspace: Path,
    *,
    stage: str,
    cases: Sequence[Mapping[str, object]],
    pipeline_ids: Sequence[str],
    measurement_modes: Sequence[str],
    registry_path: Path | None,
) -> dict[str, object]:
    _assert_development_only(cases)
    path = Path(workspace).resolve() / "campaign_manifest.json"
    if not path.is_file():
        raise RuntimeError(f"campaign is not prepared: {path.parent}")
    manifest = read_json(path)
    if str(manifest.get("campaign_stage") or "") != stage:
        raise RuntimeError(f"campaign stage differs: expected {stage}")
    selected_cases = tuple(str(value) for value in manifest.get("selected_case_ids", ()))
    expected_cases = tuple(_case_id(row) for row in cases)
    if len(selected_cases) != len(expected_cases) or set(selected_cases) != set(
        expected_cases
    ):
        raise RuntimeError("campaign exact case selection differs")
    case_index = manifest.get("case_index")
    if not isinstance(case_index, Mapping):
        raise RuntimeError("campaign case index is missing")
    indexed = [case_index.get(case_id) for case_id in selected_cases]
    if any(not isinstance(row, Mapping) for row in indexed):
        raise RuntimeError("campaign case index is incomplete")
    _assert_development_only([row for row in indexed if isinstance(row, Mapping)])
    if set(str(value) for value in manifest.get("selected_pipeline_ids", ())) != set(
        pipeline_ids
    ):
        raise RuntimeError("campaign exact pipeline selection differs")
    if tuple(str(value) for value in manifest.get("measurement_modes", ())) != tuple(
        measurement_modes
    ):
        raise RuntimeError("campaign measurement modes differ")
    registry_ref = manifest.get("decision_policy_registry")
    if registry_path is None:
        if registry_ref is not None:
            raise RuntimeError("raw calibration must not load a decision registry")
    else:
        registry = Path(registry_path).resolve()
        if not registry.is_file():
            raise FileNotFoundError(registry)
        if not isinstance(registry_ref, Mapping) or str(
            registry_ref.get("sha256") or ""
        ) != sha256_file(registry):
            raise RuntimeError("campaign decision-policy registry differs")
    return manifest


def _calibration_observations(
    workspace: Path, manifest: Mapping[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    store = EvaluationStateStore(Path(workspace) / "campaign.sqlite3")
    rows = store.list_jobs(split="development", measurement_mode="accuracy")
    if not rows or any(row.state != "complete" for row in rows):
        remaining = sum(row.state != "complete" for row in rows)
        raise RuntimeError(
            "cannot freeze challenger policies before calibration completes; "
            f"remaining={remaining}"
        )
    campaign_id = str(manifest["campaign_id"])
    results_root = (DEFAULT_RESULTS_ROOT / campaign_id).resolve()
    observations: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    for state in sorted(rows, key=lambda value: value.spec.job_id):
        diagnostic = (
            results_root
            / state.spec.result_relative_path
            / "diagnostics/challenger_identity_scores.jsonl"
        ).resolve()
        try:
            diagnostic.relative_to(results_root)
        except ValueError as error:
            raise RuntimeError("calibration diagnostic escapes result root") from error
        if not diagnostic.is_file():
            raise RuntimeError(f"calibration diagnostic is missing: {diagnostic}")
        local_rows = _jsonl(diagnostic)
        observations.extend(local_rows)
        evidence.append(
            {
                "job_id": state.spec.job_id,
                "pipeline_id": state.spec.pipeline_id,
                "result_relative_path": state.spec.result_relative_path,
                "diagnostic_logical_path": "diagnostics/challenger_identity_scores.jsonl",
                "row_count": len(local_rows),
                "sha256": sha256_file(diagnostic),
            }
        )
    if not observations:
        raise RuntimeError("calibration produced no challenger score observations")
    return observations, evidence


def _isolated_job_executor(
    registry_path: Path,
    *,
    measurement_mode: str,
) -> Callable[..., Mapping[str, object]]:
    """Return an attempt-local-cache executor for cold/resource measurements."""

    registry = Path(registry_path).resolve()

    def execute(
        job: EvaluationJobSpec,
        cases: Sequence[Mapping[str, object]],
        output_root: Path,
        progress: Callable[..., None],
        stop_requested: Callable[[], bool],
    ) -> Mapping[str, object]:
        from app.full_pipeline.factory import build_file_runtime
        from app.full_pipeline_evaluation.worker import execute_evaluation_job

        attempt_cache = Path(output_root).resolve().parent / "isolated_component_cache"

        def isolated_runtime(**kwargs: object) -> object:
            kwargs["cache_root"] = attempt_cache
            kwargs["worker_pool"] = None
            kwargs["lazy_worker_start"] = False
            kwargs["asr_stream_trace_root"] = None
            kwargs["asr_stream_trace_enabled"] = False
            kwargs["evaluation_measurement_mode"] = measurement_mode
            return build_file_runtime(**kwargs)  # type: ignore[arg-type]

        return execute_evaluation_job(
            job,
            cases,
            output_root,
            progress,
            stop_requested,
            runtime_builder=isolated_runtime,
            decision_policy_registry_path=registry,
        )

    return execute


def _require_policy_registry(path: Path) -> Path:
    target = Path(path).resolve()
    if not target.is_file():
        raise RuntimeError(
            "challenger decision policies are not frozen; run FreezePolicies first"
        )
    value = read_json(target)
    validate_development_policy_registry(value)
    return target


def _write_or_verify(path: Path, value: Mapping[str, object]) -> None:
    target = Path(path)
    if target.is_file():
        if canonical_json_bytes(read_json(target)) != canonical_json_bytes(value):
            raise RuntimeError(f"immutable Prompt-4 artifact differs: {target}")
        return
    write_json_atomic(target, dict(value))


def _jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row is not an object: {path}:{line_number}")
        rows.append(value)
    return rows


def _case_id(row: Mapping[str, object]) -> str:
    value = (
        row.get("case_id")
        or row.get("protocol_case_id")
        or row.get("recording_id")
        or row.get("utt_id")
    )
    if value is None or not str(value).strip():
        raise ValueError("full-pipeline case lacks an ID")
    return str(value)


def _stage_result(action: str, value: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "action": action,
        **dict(value),
        "held_out_evaluation_started": False,
    }


__all__ = [
    "DEFAULT_ROOT",
    "combine_evidence",
    "DevelopmentRunLayout",
    "freeze_policies",
    "freeze_development",
    "finalize_qualification",
    "layout",
    "plan",
    "prepare_calibration",
    "prepare_development",
    "prepare_qualification",
    "prepare_resources",
    "qualify_restarts",
    "run_calibration",
    "run_development",
    "run_qualification",
    "run_resources",
    "status",
    "stop",
]
