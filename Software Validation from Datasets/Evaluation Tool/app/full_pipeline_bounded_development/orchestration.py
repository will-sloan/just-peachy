"""Restart-safe controller for amended, bounded Prompt 4.

This package is additive.  It consumes the stopped v5 Prompt-4 workspace as
immutable policy/qualification provenance, prepares a new 180-case all-18
development campaign, and never merges the partial v5 result set into the new
bounded result set.
"""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Mapping, Sequence
import zipfile

import yaml

from app.full_pipeline.factory import DEFAULT_CACHE_ROOT
from app.full_pipeline_development import orchestration as legacy_orchestration
from app.full_pipeline_development.evidence import (
    combine_development_evidence,
    freeze_development_outputs,
)
from app.full_pipeline_development.policies import (
    validate_development_policy_registry,
)
from app.full_pipeline_development.qualification import (
    require_valid_qualification_bundle,
)
from app.full_pipeline_development.reporting import publish_development_report
from app.full_pipeline_evaluation import controller as evaluation_controller
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    read_json,
    sha256_bytes,
    sha256_file,
    write_bytes_atomic,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import (
    DEFAULT_RESULTS_ROOT,
    DEFAULT_SUMMARY_ROOT,
    EVALUATION_ROOT,
    matrix,
)
from app.full_pipeline_evaluation.protocol import load_cases

from .selection import (
    COMPLETION_MARKER,
    ORIGINAL_FULL_SCOPE_COMPLETE,
    SCOPE_CLASS,
    SCOPE_ID,
    SELECTION_SEED,
    build_selection_manifest,
    selected_rows,
    write_selection_manifest,
)


ORCHESTRATION_SCHEMA_VERSION = "full-pipeline-prompt4-reduced-orchestration.v1"
COMPLETION_SCHEMA_VERSION = "full-pipeline-eight-day-stage-completion.v1"
ACCURACY_STAGE = "prompt4_reduced_8day_all18_development_accuracy"
RESOURCES_STAGE = "prompt4_reduced_8day_all18_serial_resources"
MINIMUM_FREE_GIB = 35
MAXIMUM_STAGE_HOURS = 48
EXPECTED_PIPELINES = 18
EXPECTED_SELECTED_CASES = 180
PARTIAL_MARKER = "SUPERSEDED_PARTIAL_FULL_SCOPE"
AMENDMENT_PATH = EVALUATION_ROOT / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
PROGRAM_STATE_PATH = EVALUATION_ROOT / "runs/full_pipeline_program/PROGRAM_STATE.json"
DEFAULT_SOURCE_EVIDENCE_ROOT = EVALUATION_ROOT / (
    "automated_runs/full_pipeline_development_v1_prompt4_execution_recovery_"
    "v5_restart_contract_fix"
)
DEFAULT_ROOT = EVALUATION_ROOT / (
    "automated_runs/full_pipeline_development_prompt4_reduced_8day_v1"
)
DEFAULT_OUTPUT_ROOT = EVALUATION_ROOT / (
    "JustPeachyResearchSummaries/full_pipeline/development/"
    "full_pipeline_prompt4_reduced_8day_v1"
)


class BoundedOrchestrationError(RuntimeError):
    """A bounded Prompt-4 gate or immutable binding failed."""


class StorageReserveError(BoundedOrchestrationError):
    """C: does not satisfy the amendment's 35-GiB reserve."""


def layout(workspace_root: Path = DEFAULT_ROOT) -> dict[str, Path]:
    root = _require_c_path(workspace_root, "workspace root")
    return {
        "root": root,
        "selection": root / "bounded_selection.json",
        "input_binding": root / "input_binding.json",
        "plan": root / "orchestration_plan.json",
        "registry": root / "decision_policy_registry.json",
        "accuracy": root / "development_accuracy",
        "resources": root / "resource_spots",
        "combined": root / "combined_evidence",
        "frozen_configs": root / "frozen_pipeline_configs",
        "freeze_result": root / "freeze_result.json",
        "scope_binding": root / "bounded_scope_binding.json",
        "completion": root / "completion_marker.json",
        "artifact_manifest": root / "artifact_manifest.json",
        "gates": root / "gates",
    }


def plan(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    source_evidence_root: Path = DEFAULT_SOURCE_EVIDENCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, object]:
    """Freeze the metadata panel and bind stopped v5 policy/qualification evidence."""

    paths = layout(workspace_root)
    output = _require_c_path(output_root, "output root")
    source = _require_c_path(source_evidence_root, "source evidence root")
    material = _material_paths(paths["root"], source, output)
    storage = _storage_preflight(material, fail_below_reserve=True)
    _validated_amendment()
    rows = _development_rows()
    selection = build_selection_manifest(rows)
    if selection["selected_case_count"] != EXPECTED_SELECTED_CASES:
        raise BoundedOrchestrationError("bounded panel is not exactly 180 cases")
    source_binding = _source_evidence_binding(source)
    paths["root"].mkdir(parents=True, exist_ok=True)
    write_selection_manifest(paths["selection"], selection)
    _copy_or_verify(
        source / "frozen/decision_policy_registry.json", paths["registry"]
    )
    binding_core: dict[str, object] = {
        "schema_version": "full-pipeline-prompt4-reduced-input-binding.v1",
        **_scope_fields(),
        "amendment_path": str(AMENDMENT_PATH.resolve()),
        "amendment_sha256": sha256_file(AMENDMENT_PATH),
        "source_evidence": source_binding,
        "selection_path": str(paths["selection"]),
        "selection_sha256": sha256_file(paths["selection"]),
        "decision_policy_registry_path": str(paths["registry"]),
        "decision_policy_registry_sha256": sha256_file(paths["registry"]),
        "all_material_paths_c_only": True,
        "material_paths": [str(path) for path in material],
        "partial_original_results_merged": False,
        "development_only": True,
        "evaluation_material_inspected": False,
    }
    input_binding = {
        **binding_core,
        "binding_identity_sha256": sha256_bytes(canonical_json_bytes(binding_core)),
    }
    _write_or_verify(paths["input_binding"], input_binding)
    selected = selected_rows(rows, selection)
    plan_core: dict[str, object] = {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "PASS",
        **_scope_fields(),
        "completion_marker_on_success": COMPLETION_MARKER,
        "workspace_root": str(paths["root"]),
        "output_root": str(output),
        "input_binding_sha256": sha256_file(paths["input_binding"]),
        "selection_identity_sha256": selection["selection_identity_sha256"],
        "case_manifest_sha256": selection["case_manifest_sha256"],
        "reference_sha256": selection["reference_sha256"],
        "selection_seed": SELECTION_SEED,
        "pipeline_count": len(matrix().pipeline_ids),
        "pipeline_ids": list(matrix().pipeline_ids),
        "accuracy": {
            "campaign_stage": ACCURACY_STAGE,
            "workspace_root": str(paths["accuracy"]),
            "case_count": len(selected),
            "logical_pipeline_case_count": len(selected) * EXPECTED_PIPELINES,
            "duration_sec": round(sum(float(row["duration_sec"]) for row in selected), 9),
            "parallel_jobs": 2,
            "measurement_mode": "accuracy",
        },
        "resources": {
            "campaign_stage": RESOURCES_STAGE,
            "workspace_root": str(paths["resources"]),
            "case_count": len(_resource_cases(selected)),
            "logical_pipeline_case_count": len(_resource_cases(selected)) * EXPECTED_PIPELINES,
            "parallel_jobs": 1,
            "measurement_mode": "resources",
            "isolated_component_cache_per_attempt": True,
        },
        "budget": {
            "maximum_stage_hours": MAXIMUM_STAGE_HOURS,
            "measured_v5_logical_cases": source_binding["partial_original_run"]["completed_cases"],
            "measured_v5_elapsed_hours": source_binding["partial_original_run"]["elapsed_sec"] / 3600.0,
            "projected_accuracy_hours_at_measured_case_rate": round(
                (len(selected) * EXPECTED_PIPELINES)
                / (
                    source_binding["partial_original_run"]["completed_cases"]
                    / (source_binding["partial_original_run"]["elapsed_sec"] / 3600.0)
                ),
                3,
            ),
            "projection_is_runtime_only_not_result_dependent": True,
            "shared_cache_reused": str(DEFAULT_CACHE_ROOT.resolve()),
        },
        "storage_policy": {
            "allowed_drive": "C:\\",
            "minimum_free_space_reserve_gib": MINIMUM_FREE_GIB,
            "validated_paths": storage["validated_paths"],
            "other_drives_used": False,
            "preflight_required_before_every_stage": True,
        },
        "qualification_and_policy_reused_without_retuning": True,
        "partial_original_results_merged": False,
        "held_out_evaluation_allowed": False,
        "held_out_evaluation_started": False,
        "evaluation_material_inspected": False,
        "model_inference_performed": False,
    }
    _write_or_verify(paths["plan"], plan_core)
    return {**plan_core, "current_storage_preflight": storage}


def prepare(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    source_evidence_root: Path = DEFAULT_SOURCE_EVIDENCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, object]:
    value = plan(
        workspace_root=workspace_root,
        source_evidence_root=source_evidence_root,
        output_root=output_root,
    )
    paths = layout(workspace_root)
    _storage_preflight(_material_paths(paths["root"], source_evidence_root, output_root))
    cases = _selected_cases(paths)
    result = evaluation_controller.prepare(
        workspace_root=paths["accuracy"],
        seed=SELECTION_SEED,
        case_ids=tuple(_case_id(row) for row in cases),
        pipeline_ids=matrix().pipeline_ids,
        measurement_modes=("accuracy",),
        campaign_stage=ACCURACY_STAGE,
        decision_policy_registry_path=paths["registry"],
    )
    _require_campaign(paths["accuracy"], ACCURACY_STAGE, cases, "accuracy", paths["registry"])
    return _result("Prepare", result, plan=value)


def run(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    _validate_existing_bindings(paths)
    _storage_preflight(_material_paths_from_plan(paths))
    cases = _selected_cases(paths)
    _require_campaign(paths["accuracy"], ACCURACY_STAGE, cases, "accuracy", paths["registry"])
    result = _run_with_storage_monitor(
        workspace=paths["accuracy"],
        material_paths=_material_paths_from_plan(paths),
        operation=lambda: evaluation_controller.run_development(
            workspace_root=paths["accuracy"],
            measurement_mode="accuracy",
            pipeline_ids=matrix().pipeline_ids,
            parallel_jobs=2,
        ),
    )
    return _result("Run", result)


def prepare_resources(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    source_evidence_root: Path = DEFAULT_SOURCE_EVIDENCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, object]:
    plan(
        workspace_root=workspace_root,
        source_evidence_root=source_evidence_root,
        output_root=output_root,
    )
    paths = layout(workspace_root)
    _storage_preflight(_material_paths_from_plan(paths))
    cases = _resource_cases(_selected_cases(paths))
    result = evaluation_controller.prepare(
        workspace_root=paths["resources"],
        seed=SELECTION_SEED,
        case_ids=tuple(_case_id(row) for row in cases),
        pipeline_ids=matrix().pipeline_ids,
        measurement_modes=("resources",),
        campaign_stage=RESOURCES_STAGE,
        decision_policy_registry_path=paths["registry"],
    )
    _require_campaign(paths["resources"], RESOURCES_STAGE, cases, "resources", paths["registry"])
    return _result("PrepareResources", result)


def run_resources(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    _validate_existing_bindings(paths)
    _storage_preflight(_material_paths_from_plan(paths))
    cases = _resource_cases(_selected_cases(paths))
    _require_campaign(paths["resources"], RESOURCES_STAGE, cases, "resources", paths["registry"])
    isolated = legacy_orchestration._isolated_job_executor(  # noqa: SLF001
        paths["resources"] / "decision_policy_registry.json",
        measurement_mode="resources",
    )
    result = _run_with_storage_monitor(
        workspace=paths["resources"],
        material_paths=_material_paths_from_plan(paths),
        operation=lambda: evaluation_controller.run_development(
            workspace_root=paths["resources"],
            measurement_mode="resources",
            pipeline_ids=matrix().pipeline_ids,
            parallel_jobs=1,
            job_executor=isolated,
        ),
    )
    return _result("RunResources", result)


def analyze(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    """Checksum-validate both complete campaigns and combine without inference."""

    paths = layout(workspace_root)
    _validate_existing_bindings(paths)
    _storage_preflight(_material_paths_from_plan(paths))
    accuracy = evaluation_controller.analyze(workspace_root=paths["accuracy"])
    resources = evaluation_controller.analyze(workspace_root=paths["resources"])
    combined = combine_development_evidence(
        output_workspace_root=paths["combined"],
        accuracy_workspace_root=paths["accuracy"],
        resource_workspace_root=paths["resources"],
        accuracy_analysis=accuracy,
        resource_analysis=resources,
    )
    binding = {
        "schema_version": "full-pipeline-prompt4-reduced-evidence-binding.v1",
        "status": "PASS",
        **_scope_fields(),
        "selection_identity_sha256": read_json(paths["selection"])[
            "selection_identity_sha256"
        ],
        "combined_campaign_identity_sha256": combined[
            "campaign_identity_sha256"
        ],
        "development_result_set_sha256": combined["development_result_set_sha256"],
        "partial_original_results_merged": False,
        "evaluation_material_inspected": False,
    }
    _write_or_verify(paths["scope_binding"], binding)
    return _result("Analyze", combined)


def freeze(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    """Freeze exact all-18 configurations from bounded development evidence."""

    paths = layout(workspace_root)
    _validate_existing_bindings(paths)
    if not (paths["combined"] / "campaign_manifest.json").is_file():
        raise BoundedOrchestrationError("combined evidence is missing; run Analyze")
    if paths["freeze_result"].is_file():
        _validate_frozen_configs(paths["frozen_configs"])
        return read_json(paths["freeze_result"])
    source = Path(read_json(paths["input_binding"])["source_evidence"]["root"])
    result = freeze_development_outputs(
        combined_workspace_root=paths["combined"],
        policy_registry=paths["registry"],
        runtime_anchor_qualification=read_json(
            source / "qualification/anchor_runtime_qualification.json"
        ),
        frozen_config_root=paths["frozen_configs"],
    )
    _validate_frozen_configs(paths["frozen_configs"])
    document = {
        "schema_version": "full-pipeline-prompt4-reduced-freeze-result.v1",
        "status": "PASS",
        **_scope_fields(),
        "scientific_freeze": result,
        "pipeline_count": EXPECTED_PIPELINES,
        "frozen_pipeline_configs": str(paths["frozen_configs"]),
        "checksums_sha256": sha256_file(paths["frozen_configs"] / "checksums.json"),
        "evaluation_material_inspected": False,
    }
    _write_or_verify(paths["freeze_result"], document)
    return document


def collect(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, object]:
    """Publish the scoped report/package and atomically emit Prompt-5's gate."""

    paths = layout(workspace_root)
    output = _require_c_path(output_root, "output root")
    _validate_existing_bindings(paths)
    _storage_preflight(_material_paths_from_plan(paths) + (output,))
    _validate_frozen_configs(paths["frozen_configs"])
    source = Path(read_json(paths["input_binding"])["source_evidence"]["root"])
    scientific_root = output / "scientific_report"
    publish_development_report(
        analysis_index=paths["combined"] / "analysis/analysis.json",
        campaign_manifest=paths["combined"] / "campaign_manifest.json",
        qualification_bundle=source / "qualification/qualification.json",
        qualification_plan=source / "qualification/qualification_plan.json",
        qualification_evidence_root=source / "qualification",
        frozen_config_root=paths["frozen_configs"],
        output_root=scientific_root,
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_scoped_summary(
        scientific_root / "development_summary.csv",
        output / "development_summary.csv",
    )
    _write_scoped_extended_set(
        scientific_root / "extended_set.yaml",
        output / "extended_set.yaml",
    )
    _copy_or_verify(paths["selection"], output / "bounded_selection.json")
    _copy_or_verify(AMENDMENT_PATH, output / "EIGHT_DAY_SCOPE_AMENDMENT.json")
    _copy_or_verify(paths["input_binding"], output / "input_binding.json")
    _copy_or_verify(paths["scope_binding"], output / "bounded_scope_binding.json")
    report = _bounded_report(paths, scientific_root)
    write_bytes_atomic(output / "development_report.md", report.encode("utf-8"))
    scope_manifest = {
        "schema_version": "full-pipeline-prompt4-reduced-report-scope.v1",
        "status": "PASS",
        **_scope_fields(),
        "scientific_report_root": str(scientific_root.resolve()),
        "scientific_report_checksums_sha256": sha256_file(
            scientific_root / "checksums.json"
        ),
        "selection_identity_sha256": read_json(paths["selection"])[
            "selection_identity_sha256"
        ],
        "partial_original_results_merged": False,
        "evaluation_material_inspected": False,
    }
    _write_or_verify(output / "scope_manifest.json", scope_manifest)
    _write_report_checksums(output)
    zip_path = output / "full_pipeline_prompt4_reduced_8day_compact.zip"
    _write_deterministic_zip(output, zip_path)

    gates = _write_stage_gates(paths, output)
    artifact_manifest = _write_artifact_manifest(paths, output, zip_path, gates)
    completion = _completion_document(
        paths, output, zip_path, gates, artifact_manifest
    )
    _write_or_verify(paths["completion"], completion)
    _advance_program_state(paths["completion"])
    return completion


def status(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    stages: dict[str, object] = {}
    for name in ("accuracy", "resources"):
        root = paths[name]
        stages[name] = (
            evaluation_controller.status(workspace_root=root)
            if (root / "campaign_manifest.json").is_file()
            else {"status": "NOT_PREPARED", "workspace_root": str(root)}
        )
    material = _material_paths_from_plan(paths) if paths["plan"].is_file() else (paths["root"],)
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "PASS",
        **_scope_fields(),
        "completion_marker": (
            read_json(paths["completion"])["completion_marker"]
            if paths["completion"].is_file()
            else None
        ),
        "workspace_root": str(paths["root"]),
        "selection": "FROZEN" if paths["selection"].is_file() else "NOT_PLANNED",
        "input_binding": "FROZEN" if paths["input_binding"].is_file() else "NOT_PLANNED",
        "frozen_pipeline_configs": (
            "FROZEN" if (paths["frozen_configs"] / "checksums.json").is_file() else "PENDING"
        ),
        "storage": _storage_preflight(material, fail_below_reserve=False),
        "stages": stages,
        "held_out_evaluation_started": False,
        "evaluation_material_inspected": False,
    }


def stop(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    stages: dict[str, object] = {}
    for name in ("accuracy", "resources"):
        root = paths[name]
        if (root / "campaign_manifest.json").is_file():
            stages[name] = evaluation_controller.stop(workspace_root=root)
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": "STOP_REQUESTED",
        **_scope_fields(),
        "stages": stages,
        "held_out_evaluation_started": False,
        "evaluation_material_inspected": False,
    }


def execute(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    source_evidence_root: Path = DEFAULT_SOURCE_EVIDENCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, object]:
    """Run/resume the complete bounded Prompt-4 sequence, stopping on any gate."""

    completed: list[str] = []
    steps = (
        (
            "Prepare",
            lambda: prepare(
                workspace_root=workspace_root,
                source_evidence_root=source_evidence_root,
                output_root=output_root,
            ),
        ),
        ("Run", lambda: run(workspace_root=workspace_root)),
        (
            "PrepareResources",
            lambda: prepare_resources(
                workspace_root=workspace_root,
                source_evidence_root=source_evidence_root,
                output_root=output_root,
            ),
        ),
        ("RunResources", lambda: run_resources(workspace_root=workspace_root)),
        ("Analyze", lambda: analyze(workspace_root=workspace_root)),
        ("Freeze", lambda: freeze(workspace_root=workspace_root)),
        (
            "Collect",
            lambda: collect(workspace_root=workspace_root, output_root=output_root),
        ),
    )
    latest: dict[str, object] = {}
    for name, operation in steps:
        latest = operation()
        stage_status = str(latest.get("status") or "").upper()
        if stage_status not in {"PASS", "COMPLETE"}:
            return {
                "schema_version": ORCHESTRATION_SCHEMA_VERSION,
                "status": stage_status or "INCOMPLETE",
                **_scope_fields(),
                "action": "Execute",
                "completed_actions": completed,
                "stopped_at_action": name,
                "latest_result": latest,
                "held_out_evaluation_started": False,
                "evaluation_material_inspected": False,
            }
        completed.append(name)
    return latest


def validate(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    """Fail-closed validation of Prompt-4 completion and the universal envelope."""

    paths = layout(workspace_root)
    errors: list[str] = []
    try:
        _validate_existing_bindings(paths)
    except Exception as exc:  # validation inventory must retain every failure
        errors.append(f"input_binding: {type(exc).__name__}: {exc}")
    for name in ("accuracy", "resources"):
        try:
            result = evaluation_controller.validate(
                workspace_root=paths[name], verify_audio=False
            )
            if result.get("valid") is not True:
                errors.append(f"{name}: controller validation failed: {result.get('errors')}")
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    try:
        _validate_frozen_configs(paths["frozen_configs"])
    except Exception as exc:
        errors.append(f"frozen_configs: {type(exc).__name__}: {exc}")
    completion: dict[str, object] | None = None
    if not paths["completion"].is_file():
        errors.append("completion_marker.json is missing")
    else:
        try:
            completion = read_json(paths["completion"])
            _validate_completion_envelope(completion)
        except Exception as exc:
            errors.append(f"completion: {type(exc).__name__}: {exc}")
    if completion is not None:
        try:
            _validate_program_state_binding(paths["completion"])
        except Exception as exc:
            errors.append(f"program_state: {type(exc).__name__}: {exc}")
    return {
        "schema_version": "full-pipeline-prompt4-reduced-validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        **_scope_fields(),
        "completion_marker": (
            completion.get("completion_marker") if completion is not None else None
        ),
        "errors": errors,
        "held_out_evaluation_started": False,
        "evaluation_material_inspected": False,
    }


def _validate_completion_envelope(completion: Mapping[str, object]) -> None:
    if completion.get("schema_version") != COMPLETION_SCHEMA_VERSION:
        raise BoundedOrchestrationError("completion schema differs")
    if completion.get("status") != "COMPLETE":
        raise BoundedOrchestrationError("completion status is not COMPLETE")
    if completion.get("completion_marker") != COMPLETION_MARKER:
        raise BoundedOrchestrationError("completion marker differs")
    if completion.get("prompt_index") != 4 or completion.get("predecessor") is not None:
        raise BoundedOrchestrationError("completion prompt/predecessor differs")
    if (
        completion.get("scope_id") != SCOPE_ID
        or completion.get("scope_class") != SCOPE_CLASS
        or completion.get("original_full_scope_complete") is not False
    ):
        raise BoundedOrchestrationError("completion scope differs")
    if (
        completion.get("development_only") is not True
        or completion.get("evaluation_material_inspected") is not False
        or completion.get("held_out_evaluation_started") is not False
    ):
        raise BoundedOrchestrationError("completion firewall attestation differs")
    unsigned = dict(completion)
    expected_identity = unsigned.pop("completion_identity_sha256", None)
    if expected_identity != sha256_bytes(canonical_json_bytes(unsigned)):
        raise BoundedOrchestrationError("completion identity differs")
    env_adapter_id = os.environ.get("JP8_ADAPTER_ID", "").strip()
    env_adapter_sha = os.environ.get("JP8_ADAPTER_CONTRACT_SHA256", "").strip().lower()
    if env_adapter_id or env_adapter_sha:
        adapter_id, adapter_sha = _adapter_identity()
        if completion.get("adapter_id") != adapter_id or completion.get(
            "adapter_contract_sha256"
        ) != adapter_sha:
            raise BoundedOrchestrationError("completion adapter binding differs")
    elif (
        not str(completion.get("adapter_id") or "")
        or len(str(completion.get("adapter_contract_sha256") or "")) != 64
    ):
        raise BoundedOrchestrationError("completion adapter binding is invalid")
    manifest_ref = completion.get("artifact_manifest")
    if not isinstance(manifest_ref, Mapping):
        raise BoundedOrchestrationError("artifact manifest reference is absent")
    manifest_path = _verified_reference(manifest_ref, "artifact manifest")
    manifest = read_json(manifest_path)
    if (
        manifest.get("schema_version")
        != "full-pipeline-eight-day-artifact-manifest.v1"
        or manifest.get("prompt_index") != 4
        or manifest.get("scope_id") != SCOPE_ID
        or manifest.get("scope_class") != SCOPE_CLASS
        or manifest.get("original_full_scope_complete") is not False
    ):
        raise BoundedOrchestrationError("artifact manifest contract differs")
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise BoundedOrchestrationError("artifact manifest inventory is empty")
    manifest_artifact_paths: set[str] = set()
    for raw in raw_artifacts:
        if not isinstance(raw, Mapping) or raw.get("required") is not True:
            raise BoundedOrchestrationError("artifact manifest entry is invalid")
        manifest_artifact_paths.add(str(_verified_reference(raw, "required artifact")))
    gate_records = completion.get("gate_records")
    expected_gates = {
        "hash_validation",
        "firewall_validation",
        "prerequisite_validation",
    }
    if not isinstance(gate_records, Mapping) or set(gate_records) != expected_gates:
        raise BoundedOrchestrationError("completion gate inventory differs")
    for gate, raw in gate_records.items():
        if not isinstance(raw, Mapping):
            raise BoundedOrchestrationError(f"{gate} gate reference is invalid")
        gate_path = _verified_reference(raw, f"{gate} gate")
        if str(gate_path) not in manifest_artifact_paths:
            raise BoundedOrchestrationError(f"{gate} gate is absent from artifact manifest")
        document = read_json(gate_path)
        if (
            document.get("schema_version") != "full-pipeline-eight-day-gate.v1"
            or document.get("gate") != gate
            or document.get("status") != "PASS"
            or document.get("prompt_index") != 4
            or document.get("scope_id") != SCOPE_ID
        ):
            raise BoundedOrchestrationError(f"{gate} gate contract differs")
    native_artifacts = completion.get("artifacts")
    if not isinstance(native_artifacts, Mapping) or set(native_artifacts) != {
        "frozen_pipeline_configs",
        "decision_policy_registry",
        "extended_set",
        "development_summary",
    }:
        raise BoundedOrchestrationError("Prompt-5 native artifact inventory differs")
    for name, raw in native_artifacts.items():
        if not isinstance(raw, Mapping):
            raise BoundedOrchestrationError(f"native artifact {name} is invalid")
        if name == "frozen_pipeline_configs":
            root = _require_c_path(Path(str(raw.get("path") or "")), name)
            if not root.is_dir():
                raise BoundedOrchestrationError("frozen pipeline config root is missing")
            _validate_frozen_configs(root)
            checksums = root / "checksums.json"
            if raw.get("sha256") != sha256_file(checksums):
                raise BoundedOrchestrationError("frozen config identity differs")
        else:
            _verified_reference(raw, f"native artifact {name}")


def _verified_reference(reference: Mapping[str, object], label: str) -> Path:
    path = _require_c_path(Path(str(reference.get("path") or "")), label)
    if not path.is_file():
        raise BoundedOrchestrationError(f"{label} is missing: {path}")
    expected = str(reference.get("sha256") or "")
    if sha256_file(path) != expected:
        raise BoundedOrchestrationError(f"{label} checksum differs")
    return path


def _advance_program_state(completion_path: Path) -> dict[str, object]:
    """Atomically advance the canonical program gate after Prompt 4 completes.

    The operation is idempotent for the same checksum-bound completion record
    and fails closed if another stage has already advanced the program.
    """

    state_path = _require_c_path(PROGRAM_STATE_PATH, "program state")
    completion = read_json(completion_path)
    _validate_completion_envelope(completion)
    state = read_json(state_path)
    completion_sha = sha256_file(completion_path)
    if (
        state.get("status") == COMPLETION_MARKER
        and int(state.get("current_prompt_index") or -1) == 4
    ):
        _validate_program_state_binding(completion_path)
        return state
    if int(state.get("current_prompt_index") or -1) != 3:
        raise BoundedOrchestrationError(
            "PROGRAM_STATE is neither the Prompt-3 prerequisite nor this exact "
            "completed Prompt-4 stage"
        )
    completion_state = dict(state.get("completion_state") or {})
    if completion_state.get("prompt_3") != "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE":
        raise BoundedOrchestrationError(
            "PROGRAM_STATE lacks the completed Prompt-3 prerequisite"
        )
    completion_state.update(
        {
            "prompt_4": COMPLETION_MARKER,
            "prompt_4_scope_id": SCOPE_ID,
            "prompt_4_original_full_scope_complete": False,
        }
    )
    updated = {
        **state,
        "status": COMPLETION_MARKER,
        "current_prompt_index": 4,
        "remaining_prompt_indices": [5, 6, 7, 8],
        "remaining_prompt_status": "PENDING_AUTOMATIC",
        "completion_state": completion_state,
        "prompt_4_completion_record": str(completion_path.resolve()),
        "prompt_4_completion_record_sha256": completion_sha,
        **_scope_fields(),
    }
    write_json_atomic(state_path, updated)
    _validate_program_state_binding(completion_path)
    return updated


def _validate_program_state_binding(completion_path: Path) -> None:
    state_path = _require_c_path(PROGRAM_STATE_PATH, "program state")
    state = read_json(state_path)
    if (
        state.get("status") != COMPLETION_MARKER
        or int(state.get("current_prompt_index") or -1) != 4
        or state.get("remaining_prompt_indices") != [5, 6, 7, 8]
    ):
        raise BoundedOrchestrationError(
            "PROGRAM_STATE has not reached bounded Prompt 4"
        )
    completion_state = state.get("completion_state")
    if not isinstance(completion_state, Mapping) or completion_state.get(
        "prompt_4"
    ) != COMPLETION_MARKER:
        raise BoundedOrchestrationError(
            "PROGRAM_STATE completion_state.prompt_4 differs"
        )
    if (
        state.get("scope_id") != SCOPE_ID
        or state.get("scope_class") != SCOPE_CLASS
        or state.get("original_full_scope_complete") is not False
    ):
        raise BoundedOrchestrationError("PROGRAM_STATE bounded scope differs")
    resolved_completion = completion_path.resolve()
    if state.get("prompt_4_completion_record") != str(resolved_completion):
        raise BoundedOrchestrationError("PROGRAM_STATE Prompt-4 record path differs")
    if state.get("prompt_4_completion_record_sha256") != sha256_file(
        resolved_completion
    ):
        raise BoundedOrchestrationError("PROGRAM_STATE Prompt-4 record hash differs")


def _development_rows() -> tuple[dict[str, object], ...]:
    rows = tuple(
        dict(row)
        for row in load_cases()
        if str(row.get("split") or row.get("partition") or "") == "development"
        and str(row.get("source_key") or "") in {"controlled_v1", "product_v2"}
    )
    if len(rows) != 807:
        raise BoundedOrchestrationError(
            f"development protocol inventory changed: expected=807, observed={len(rows)}"
        )
    if any(
        str(row.get("split") or row.get("partition") or "") != "development"
        for row in rows
    ):
        raise BoundedOrchestrationError("held-out case reached Prompt-4 selector")
    return tuple(sorted(rows, key=_case_id))


def _selected_cases(paths: Mapping[str, Path]) -> tuple[dict[str, object], ...]:
    if not paths["selection"].is_file():
        raise BoundedOrchestrationError("bounded selection is absent; run Plan")
    return selected_rows(_development_rows(), read_json(paths["selection"]))


def _resource_cases(cases: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    selected: list[dict[str, object]] = []
    for source in ("controlled_v1", "product_v2"):
        candidates = [
            dict(row)
            for row in cases
            if str(row.get("source_key") or "") == source
            and str(row.get("overlay_id") or "") == "MIXED_KNOWN_UNKNOWN"
            and int(row.get("known_speaker_count") or 0) > 0
            and int(row.get("unknown_speaker_count") or 0) > 0
        ]
        if not candidates:
            raise BoundedOrchestrationError(f"no mixed resource spot for {source}")
        selected.append(min(candidates, key=lambda row: (float(row["duration_sec"]), _case_id(row))))
    return tuple(sorted(selected, key=lambda row: str(row["source_key"])))


def _require_campaign(
    workspace: Path,
    stage: str,
    cases: Sequence[Mapping[str, object]],
    mode: str,
    registry: Path,
) -> Mapping[str, object]:
    return legacy_orchestration._require_stage_manifest(  # noqa: SLF001
        workspace,
        stage=stage,
        cases=cases,
        pipeline_ids=matrix().pipeline_ids,
        measurement_modes=(mode,),
        registry_path=registry,
    )


def _validated_amendment() -> dict[str, object]:
    if not AMENDMENT_PATH.is_file():
        raise BoundedOrchestrationError(f"scope amendment is missing: {AMENDMENT_PATH}")
    value = read_json(AMENDMENT_PATH)
    labels = value.get("required_artifact_labels")
    markers = value.get("completion_markers")
    storage = value.get("storage_policy")
    if value.get("amendment_id") != SCOPE_ID:
        raise BoundedOrchestrationError("scope amendment identity differs")
    if not isinstance(labels, Mapping) or (
        labels.get("scope_id") != SCOPE_ID
        or labels.get("scope_class") != SCOPE_CLASS
        or labels.get("original_full_scope_complete") is not False
    ):
        raise BoundedOrchestrationError("scope amendment labels differ")
    if not isinstance(markers, Mapping) or markers.get("prompt_4") != COMPLETION_MARKER:
        raise BoundedOrchestrationError("Prompt-4 amended completion marker differs")
    if not isinstance(storage, Mapping) or (
        storage.get("allowed_drive") != "C:\\"
        or int(storage.get("minimum_free_space_reserve_gib", -1)) != MINIMUM_FREE_GIB
    ):
        raise BoundedOrchestrationError("C:-only storage amendment differs")
    return value


def _source_evidence_binding(root: Path) -> dict[str, object]:
    immutable_files = {
        "decision_policy_registry": root / "frozen/decision_policy_registry.json",
        "calibration_freeze": root / "frozen/calibration_freeze.json",
        "qualification": root / "qualification/qualification.json",
        "qualification_plan": root / "qualification/qualification_plan.json",
        "anchor_runtime_qualification": root / "qualification/anchor_runtime_qualification.json",
        "partial_campaign_manifest": root / "development_accuracy/campaign_manifest.json",
        "partial_campaign_database": root / "development_accuracy/campaign.sqlite3",
    }
    snapshot_files = {
        "partial_controller_state": root / "development_accuracy/controller_state.json",
        "partial_progress": root / "development_accuracy/campaign_progress.json",
    }
    files = {**immutable_files, **snapshot_files}
    missing = [name for name, path in files.items() if not path.is_file()]
    if missing:
        raise BoundedOrchestrationError("source v5 evidence missing: " + ", ".join(missing))
    registry = read_json(files["decision_policy_registry"])
    validate_development_policy_registry(registry)
    qualification = require_valid_qualification_bundle(
        files["qualification"],
        plan=files["qualification_plan"],
        evidence_root=root / "qualification",
        verify_evidence_files=True,
    )
    if qualification.get("status") != "PASS" and qualification.get("valid") is not True:
        raise BoundedOrchestrationError("source v5 qualification is not PASS")
    controller_state = read_json(files["partial_controller_state"])
    progress = read_json(files["partial_progress"])
    if controller_state.get("status") != "STOPPED" or progress.get("status") != "STOPPED":
        raise BoundedOrchestrationError("source full-scope campaign is not cleanly stopped")
    if int(progress.get("failures") or 0) != 0 or int(progress.get("failed_jobs") or 0) != 0:
        raise BoundedOrchestrationError("source partial campaign contains failed jobs")
    entries = {
        name: {"path": str(path.resolve()), "sha256": sha256_file(path)}
        for name, path in immutable_files.items()
    }
    return {
        "root": str(root.resolve()),
        "marker": PARTIAL_MARKER,
        "immutable_entries": entries,
        "stopped_status_snapshot_paths": {
            name: str(path.resolve()) for name, path in snapshot_files.items()
        },
        "policy_registry_identity_sha256": registry["registry_identity_sha256"],
        "qualification_result_sha256": read_json(files["qualification"])[
            "qualification_result_sha256"
        ],
        "partial_original_run": {
            "status": "STOPPED",
            "completed_jobs": int(progress.get("complete_jobs") or 0),
            "stopped_jobs": sum(
                1 for row in progress.get("jobs", []) if row.get("state") == "stopped"
            ),
            "failed_jobs": int(progress.get("failed_jobs") or 0),
            "completed_cases": int(progress.get("completed_cases") or 0),
            "elapsed_sec": float(progress.get("elapsed_sec") or 0.0),
            "results_merged_into_bounded_campaign": False,
        },
        "evaluation_material_inspected": False,
    }


def _validate_existing_bindings(paths: Mapping[str, Path]) -> None:
    for name in ("selection", "input_binding", "plan", "registry"):
        if not paths[name].is_file():
            raise BoundedOrchestrationError(f"{name} binding is missing; run Plan")
    binding = read_json(paths["input_binding"])
    if binding.get("scope_id") != SCOPE_ID or binding.get("scope_class") != SCOPE_CLASS:
        raise BoundedOrchestrationError("input binding scope differs")
    if binding.get("selection_sha256") != sha256_file(paths["selection"]):
        raise BoundedOrchestrationError("bounded selection changed after planning")
    if binding.get("decision_policy_registry_sha256") != sha256_file(paths["registry"]):
        raise BoundedOrchestrationError("decision-policy registry changed after planning")
    if binding.get("amendment_sha256") != sha256_file(AMENDMENT_PATH):
        raise BoundedOrchestrationError("scope amendment changed after planning")
    source = binding.get("source_evidence")
    if not isinstance(source, Mapping):
        raise BoundedOrchestrationError("source evidence binding is absent")
    entries = source.get("immutable_entries")
    if not isinstance(entries, Mapping):
        raise BoundedOrchestrationError("source evidence checksums are absent")
    for name, raw in entries.items():
        if not isinstance(raw, Mapping):
            raise BoundedOrchestrationError(f"source evidence entry {name} is invalid")
        path = _require_c_path(Path(str(raw["path"])), f"source evidence {name}")
        if not path.is_file() or sha256_file(path) != raw.get("sha256"):
            raise BoundedOrchestrationError(f"source evidence {name} changed")
    selected_rows(_development_rows(), read_json(paths["selection"]))


def _validate_frozen_configs(root: Path) -> None:
    expected = {f"{pipeline_id}.yaml" for pipeline_id in matrix().pipeline_ids}
    names = {path.name for path in root.glob("*.yaml")}
    if names != expected:
        raise BoundedOrchestrationError("frozen config inventory is not exact all-18")
    checksums_path = root / "checksums.json"
    if not checksums_path.is_file():
        raise BoundedOrchestrationError("frozen config checksums are missing")
    document = read_json(checksums_path)
    if document.get("pipeline_count") != EXPECTED_PIPELINES:
        raise BoundedOrchestrationError("frozen config pipeline count differs")
    if document.get("entries") != checksum_map(root, exclude=("checksums.json",)):
        raise BoundedOrchestrationError("frozen config checksum inventory differs")


def _completion_document(
    paths: Mapping[str, Path],
    output: Path,
    zip_path: Path,
    gates: Mapping[str, Mapping[str, object]],
    artifact_manifest: Mapping[str, object],
) -> dict[str, object]:
    frozen_checksums = paths["frozen_configs"] / "checksums.json"
    registry = paths["registry"]
    extended = output / "extended_set.yaml"
    summary = output / "development_summary.csv"
    artifacts = {
        "frozen_pipeline_configs": {
            "path": str(paths["frozen_configs"].resolve()),
            "sha256": sha256_file(frozen_checksums),
            "pipeline_count": EXPECTED_PIPELINES,
            "checksums_path": str(frozen_checksums.resolve()),
            "checksums_sha256": sha256_file(frozen_checksums),
        },
        "decision_policy_registry": {
            "path": str(registry.resolve()),
            "sha256": sha256_file(registry),
        },
        "extended_set": {
            "path": str(extended.resolve()),
            "sha256": sha256_file(extended),
        },
        "development_summary": {
            "path": str(summary.resolve()),
            "sha256": sha256_file(summary),
        },
    }
    core = {
        "schema_version": COMPLETION_SCHEMA_VERSION,
        "status": "COMPLETE",
        "completion_marker": COMPLETION_MARKER,
        "prompt_index": 4,
        **_scope_fields(),
        "adapter_id": _adapter_identity()[0],
        "adapter_contract_sha256": _adapter_identity()[1],
        "predecessor": None,
        "artifact_manifest": dict(artifact_manifest),
        "gate_records": {key: dict(value) for key, value in gates.items()},
        "development_only": True,
        "evaluation_material_inspected": False,
        "held_out_evaluation_started": False,
        "partial_original_results_merged": False,
        "pipeline_count": EXPECTED_PIPELINES,
        "selected_case_count_per_pipeline": EXPECTED_SELECTED_CASES,
        "selection_identity_sha256": read_json(paths["selection"])[
            "selection_identity_sha256"
        ],
        "input_binding_sha256": sha256_file(paths["input_binding"]),
        "artifacts": artifacts,
        "compact_zip": {"path": str(zip_path.resolve()), "sha256": sha256_file(zip_path)},
        "all_resolved_paths_c_only": True,
        "original_full_scope_completion_marker_emitted": False,
    }
    for artifact in [*artifacts.values(), core["compact_zip"]]:
        _require_c_path(Path(str(artifact["path"])), "completion artifact")
    return {**core, "completion_identity_sha256": sha256_bytes(canonical_json_bytes(core))}


def _write_stage_gates(
    paths: Mapping[str, Path], output: Path
) -> dict[str, dict[str, object]]:
    paths["gates"].mkdir(parents=True, exist_ok=True)
    selection = read_json(paths["selection"])
    binding = read_json(paths["input_binding"])
    gate_evidence = {
        "hash_validation": {
            "selection_sha256": sha256_file(paths["selection"]),
            "input_binding_sha256": sha256_file(paths["input_binding"]),
            "frozen_config_checksums_sha256": sha256_file(
                paths["frozen_configs"] / "checksums.json"
            ),
            "report_checksums_sha256": sha256_file(output / "checksums.json"),
        },
        "firewall_validation": {
            "development_only": True,
            "held_out_evaluation_started": False,
            "evaluation_material_inspected": False,
            "selected_case_count": selection["selected_case_count"],
            "all_selected_splits": ["development"],
        },
        "prerequisite_validation": {
            "source_partial_marker": binding["source_evidence"]["marker"],
            "source_policy_registry_identity_sha256": binding["source_evidence"][
                "policy_registry_identity_sha256"
            ],
            "source_qualification_result_sha256": binding["source_evidence"][
                "qualification_result_sha256"
            ],
            "amendment_sha256": binding["amendment_sha256"],
            "partial_original_results_merged": False,
        },
    }
    result: dict[str, dict[str, object]] = {}
    for gate, evidence in gate_evidence.items():
        document = {
            "schema_version": "full-pipeline-eight-day-gate.v1",
            "gate": gate,
            "status": "PASS",
            "prompt_index": 4,
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "evidence": evidence,
        }
        destination = paths["gates"] / f"{gate}.json"
        _write_or_verify(destination, document)
        result[gate] = {
            "path": str(destination.resolve()),
            "sha256": sha256_file(destination),
        }
    return result


def _write_artifact_manifest(
    paths: Mapping[str, Path],
    output: Path,
    zip_path: Path,
    gates: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    artifact_paths = [
        paths["selection"],
        paths["input_binding"],
        paths["scope_binding"],
        paths["registry"],
        paths["frozen_configs"] / "checksums.json",
        output / "development_summary.csv",
        output / "extended_set.yaml",
        output / "checksums.json",
        zip_path,
        AMENDMENT_PATH,
        *(Path(str(value["path"])) for value in gates.values()),
    ]
    artifacts: list[dict[str, object]] = []
    for path in artifact_paths:
        resolved = _require_c_path(path, "artifact manifest entry")
        if not resolved.is_file():
            raise BoundedOrchestrationError(f"required artifact is missing: {resolved}")
        artifacts.append(
            {"path": str(resolved), "sha256": sha256_file(resolved), "required": True}
        )
    document = {
        "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
        "status": "PASS",
        "prompt_index": 4,
        **_scope_fields(),
        "artifacts": artifacts,
    }
    _write_or_verify(paths["artifact_manifest"], document)
    return {
        "path": str(paths["artifact_manifest"].resolve()),
        "sha256": sha256_file(paths["artifact_manifest"]),
    }


def _adapter_identity() -> tuple[str, str]:
    adapter_id = os.environ.get(
        "JP8_ADAPTER_ID", "full_pipeline_prompt4_reduced_native.v1"
    ).strip()
    supplied_sha = os.environ.get("JP8_ADAPTER_CONTRACT_SHA256", "").strip().lower()
    if not adapter_id:
        raise BoundedOrchestrationError("JP8_ADAPTER_ID must be nonempty")
    if supplied_sha:
        if len(supplied_sha) != 64 or any(char not in "0123456789abcdef" for char in supplied_sha):
            raise BoundedOrchestrationError(
                "JP8_ADAPTER_CONTRACT_SHA256 must be a lowercase SHA-256"
            )
        return adapter_id, supplied_sha
    native_contract = {
        "schema_version": COMPLETION_SCHEMA_VERSION,
        "adapter_id": adapter_id,
        "prompt_index": 4,
        "completion_marker": COMPLETION_MARKER,
        "required_gate_keys": [
            "hash_validation",
            "firewall_validation",
            "prerequisite_validation",
        ],
    }
    return adapter_id, sha256_bytes(canonical_json_bytes(native_contract))


def _write_scoped_summary(source: Path, destination: Path) -> None:
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    scoped_fields = ["scope_id", "scope_class", "original_full_scope_complete", *fields]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=scoped_fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "scope_id": SCOPE_ID,
                "scope_class": SCOPE_CLASS,
                "original_full_scope_complete": "false",
                **row,
            }
        )
    write_bytes_atomic(destination, buffer.getvalue().encode("utf-8"))


def _write_scoped_extended_set(source: Path, destination: Path) -> None:
    value = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise BoundedOrchestrationError("standard extended_set.yaml is invalid")
    document = {
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "completion_marker": COMPLETION_MARKER,
        **dict(value),
    }
    write_bytes_atomic(
        destination,
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True).encode("utf-8"),
    )


def _bounded_report(paths: Mapping[str, Path], scientific_root: Path) -> str:
    selection = read_json(paths["selection"])
    coverage = selection["achieved_coverage"]
    return f"""# Bounded Prompt-4 Development Report

- scope_id: `{SCOPE_ID}`
- scope_class: `{SCOPE_CLASS}`
- original_full_scope_complete: `false`
- completion marker on success: `{COMPLETION_MARKER}`

This is the user-authorized eight-day reduced panel, not the original 807-case
Prompt-4 campaign.  It evaluates all 18 pipelines on the same deterministic
180-case development panel (72 controlled-v1 and 108 Product-v2 cases).  The
stopped v5 full-scope evidence remains preserved as `{PARTIAL_MARKER}` and was
not merged into these results.

Achieved coverage: {coverage['case_count']} cases, {coverage['duration_sec']:.3f}
seconds, {coverage['speaker_count']} referenced speakers, and
{coverage['enrolled_identity_count']} enrolled identities.  The complete
selected and excluded inventories, seed, strata, case hash, and reference hash
are in `bounded_selection.json`.

The standard checksum-validated scientific report is retained under
`scientific_report/` at `{scientific_root.resolve()}`.  Scope-labelled comparison
artifacts are at the report root.
"""


def _write_report_checksums(root: Path) -> None:
    entries = checksum_map(
        root,
        exclude=("checksums.json", "full_pipeline_prompt4_reduced_8day_compact.zip"),
    )
    write_json_atomic(
        root / "checksums.json",
        {
            "schema_version": "full-pipeline-prompt4-reduced-report-checksums.v1",
            **_scope_fields(),
            "hash_algorithm": "sha256",
            "entries": entries,
        },
    )


def _write_deterministic_zip(root: Path, destination: Path) -> None:
    files = [
        path
        for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix())
        if path.is_file() and path.resolve() != destination.resolve()
    ]
    temp = destination.with_suffix(destination.suffix + ".tmp")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    temp.replace(destination)


def _copy_or_verify(source: Path, destination: Path) -> None:
    source = _require_c_path(source, "copy source")
    destination = _require_c_path(destination, "copy destination")
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if sha256_file(destination) != sha256_file(source):
            raise BoundedOrchestrationError(f"immutable copy differs: {destination}")
        return
    shutil.copy2(source, destination)


def _write_or_verify(path: Path, value: Mapping[str, object]) -> None:
    destination = Path(path).resolve()
    if destination.is_file():
        if canonical_json_bytes(read_json(destination)) != canonical_json_bytes(dict(value)):
            raise BoundedOrchestrationError(f"immutable artifact differs: {destination}")
        return
    write_json_atomic(destination, dict(value))


def _scope_fields() -> dict[str, object]:
    return {
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": ORIGINAL_FULL_SCOPE_COMPLETE,
    }


def _result(action: str, result: Mapping[str, object], **extra: object) -> dict[str, object]:
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "status": result.get("status", "PASS"),
        **_scope_fields(),
        "action": action,
        "result": dict(result),
        **extra,
        "held_out_evaluation_started": False,
        "evaluation_material_inspected": False,
    }


def _material_paths(root: Path, source: Path, output: Path) -> tuple[Path, ...]:
    return tuple(
        _require_c_path(path, "material path")
        for path in (
            root,
            source,
            output,
            EVALUATION_ROOT,
            AMENDMENT_PATH,
            DEFAULT_RESULTS_ROOT,
            DEFAULT_SUMMARY_ROOT,
            DEFAULT_CACHE_ROOT,
            Path(tempfile.gettempdir()),
        )
    )


def _material_paths_from_plan(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    plan_value = read_json(paths["plan"])
    return tuple(
        _require_c_path(Path(str(value)), "bound material path")
        for value in plan_value["storage_policy"]["validated_paths"]
    )


def _storage_preflight(
    paths: Sequence[Path], *, fail_below_reserve: bool = True
) -> dict[str, object]:
    validated = sorted({str(_require_c_path(path, "storage preflight path")) for path in paths})
    usage = shutil.disk_usage("C:\\")
    reserve = MINIMUM_FREE_GIB * 1024**3
    passed = usage.free >= reserve
    value = {
        "status": "PASS" if passed else "BLOCKED_C_DRIVE_RESERVE_35_GIB",
        "drive": "C:\\",
        "free_bytes": usage.free,
        "minimum_free_bytes": reserve,
        "minimum_free_space_reserve_gib": MINIMUM_FREE_GIB,
        "validated_paths": validated,
        "other_drives_used": False,
    }
    if not passed and fail_below_reserve:
        raise StorageReserveError(json.dumps(value, sort_keys=True))
    return value


def _run_with_storage_monitor(
    *,
    workspace: Path,
    material_paths: Sequence[Path],
    operation: object,
) -> dict[str, object]:
    """Run a controller action while polling the C: reserve every 30 seconds."""

    if not callable(operation):
        raise TypeError("operation must be callable")
    finished = threading.Event()
    breach: list[dict[str, object]] = []

    def monitor() -> None:
        while not finished.wait(30.0):
            snapshot = _storage_preflight(
                material_paths, fail_below_reserve=False
            )
            if snapshot["status"] == "PASS":
                continue
            document = {
                "schema_version": "full-pipeline-eight-day-storage-pause.v1",
                "status": "BLOCKED_C_DRIVE_RESERVE_35_GIB",
                "prompt_index": 4,
                **_scope_fields(),
                "storage": snapshot,
                "authoritative_evidence_deleted": False,
                "other_drive_used": False,
            }
            write_json_atomic(Path(workspace) / "storage_reserve_pause.json", document)
            breach.append(document)
            evaluation_controller.stop(workspace_root=Path(workspace))
            return

    worker = threading.Thread(
        target=monitor,
        name="prompt4-c-drive-reserve-monitor",
        daemon=True,
    )
    worker.start()
    try:
        result = operation()
    finally:
        finished.set()
        worker.join(timeout=5.0)
    if breach:
        return {
            "schema_version": ORCHESTRATION_SCHEMA_VERSION,
            "status": "BLOCKED_C_DRIVE_RESERVE_35_GIB",
            **_scope_fields(),
            "storage_pause": breach[0],
            "underlying_controller_result": result,
            "restartable": True,
        }
    if not isinstance(result, Mapping):
        raise BoundedOrchestrationError("controller operation returned a non-mapping")
    return dict(result)


def _require_c_path(path: Path, label: str) -> Path:
    resolved = Path(path).resolve()
    if resolved.drive.upper() != "C:":
        raise BoundedOrchestrationError(f"{label} must resolve on C:, got {resolved}")
    return resolved


def _case_id(row: Mapping[str, object]) -> str:
    value = str(row.get("protocol_case_id") or row.get("case_id") or "")
    if not value:
        raise BoundedOrchestrationError("case ID is missing")
    return value


__all__ = [
    "ACCURACY_STAGE",
    "BoundedOrchestrationError",
    "COMPLETION_SCHEMA_VERSION",
    "DEFAULT_OUTPUT_ROOT",
    "DEFAULT_ROOT",
    "DEFAULT_SOURCE_EVIDENCE_ROOT",
    "MINIMUM_FREE_GIB",
    "RESOURCES_STAGE",
    "StorageReserveError",
    "analyze",
    "collect",
    "execute",
    "freeze",
    "layout",
    "plan",
    "prepare",
    "prepare_resources",
    "run",
    "run_resources",
    "status",
    "stop",
    "validate",
]
