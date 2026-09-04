"""Fail-closed validation of Prompt 4-7 evidence and immutable policies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_core_evaluation.controller import layout as prompt5_layout
from app.full_pipeline_core_evaluation.reporting import (
    _validate_terminal_jobs as validate_prompt5_terminal_jobs,
    _verify_collection as validate_prompt5_collection,
)
from app.full_pipeline_development import validate_development_policy_registry
from app.full_pipeline_deployment_evidence import (
    DeploymentEvidenceError,
    load_deployment_steering,
)
from app.full_pipeline_eight_day_program.contracts import load_adapter_configuration
from app.full_pipeline_eight_day_program.storage import ProgramContractError
from app.full_pipeline_extended_evaluation.execution import (
    _validate_hardening_manifest as validate_prompt6_hardening_manifest,
)
from app.full_pipeline_production_hardening.reporting import (
    validate_completion as validate_prompt7_completion,
)

from . import (
    COMPLETION_MARKERS,
    DEFAULT_ADAPTER_REGISTRY,
    DEFAULT_AMENDMENT,
    DEFAULT_EXECUTION_POLICY_ADDENDUM,
    DEFAULT_LICENSE_DOCUMENT,
    DEFAULT_MATRIX,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_RUNTIME,
    MANDATORY_EXTENDED_ANCHORS,
    REQUIRED_STAGE_BASENAMES,
    SCOPE_CLASS,
    SCOPE_ID,
    scope_fields,
)
from .io import (
    FinalConsolidationError,
    ProductionCandidateError,
    canonical_json_bytes,
    ensure_c,
    read_csv,
    read_json,
    sha256_bytes,
    sha256_file,
)


STAGE_SCHEMA = "full-pipeline-eight-day-stage-completion.v1"
MANIFEST_SCHEMA = "full-pipeline-eight-day-artifact-manifest.v1"
GATE_SCHEMA = "full-pipeline-eight-day-gate.v1"
GATES = ("hash_validation", "firewall_validation", "prerequisite_validation")


@dataclass(frozen=True)
class ArtifactEvidence:
    prompt_index: int
    path: Path
    sha256: str
    binding: str
    binding_path: Path


@dataclass(frozen=True)
class CompletionEvidence:
    prompt_index: int
    marker: str
    path: Path
    sha256: str
    record: Mapping[str, Any]
    manifest_path: Path
    manifest_sha256: str
    artifacts: tuple[ArtifactEvidence, ...]

    def matches(self, basename: str) -> tuple[ArtifactEvidence, ...]:
        return tuple(item for item in self.artifacts if item.path.name == basename)

    def one(self, basename: str) -> Path:
        matches = self.matches(basename)
        direct = tuple(
            item for item in matches if item.binding == "universal_artifact_manifest"
        )
        authoritative = direct or matches
        if len(authoritative) != 1:
            raise FinalConsolidationError(
                f"Prompt {self.prompt_index} needs one authoritative {basename}; "
                f"found {len(authoritative)}"
            )
        return authoritative[0].path


@dataclass(frozen=True)
class EvidenceBundle:
    completions: Mapping[int, CompletionEvidence]
    program_state_path: Path
    program_state_sha256: str
    amendment_path: Path
    amendment_sha256: str
    execution_policy_path: Path
    execution_policy_sha256: str
    execution_policy: Mapping[str, object]
    adapter_registry_path: Path
    adapter_registry_sha256: str
    pi_deployment_steering_path: Path
    pi_deployment_steering_sha256: str
    pi_deployment_steering: Mapping[str, object]
    program_state_snapshot: Mapping[str, object]
    matrix_path: Path
    matrix_sha256: str
    runtime_path: Path
    runtime_sha256: str
    license_document_path: Path
    license_document_sha256: str
    pipeline_ids: tuple[str, ...]
    frozen_policy_refs: Mapping[str, Mapping[str, object]]


def validate_completion(
    path: Path | str,
    *,
    prompt_index: int,
    marker: str,
    required_basenames: Sequence[str] = (),
) -> CompletionEvidence:
    completion_path = ensure_c(
        path, label=f"Prompt-{prompt_index} completion", must_exist=True
    )
    record = read_json(completion_path)
    expected = {
        "schema_version": STAGE_SCHEMA,
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "prompt_index": prompt_index,
        "status": "COMPLETE",
        "completion_marker": marker,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} completion {key} differs: {record.get(key)!r}"
            )
    if not str(record.get("adapter_id") or "").strip():
        raise FinalConsolidationError(f"Prompt-{prompt_index} adapter_id is absent")
    _require_sha(record.get("adapter_contract_sha256"), "adapter contract SHA-256")

    manifest_ref = record.get("artifact_manifest")
    if not isinstance(manifest_ref, Mapping):
        raise FinalConsolidationError(
            f"Prompt-{prompt_index} artifact manifest reference is absent"
        )
    manifest_path = _verified_ref(manifest_ref, "artifact manifest")
    manifest = read_json(manifest_path)
    for key, value in {
        "schema_version": MANIFEST_SCHEMA,
        **scope_fields(),
        "prompt_index": prompt_index,
    }.items():
        if manifest.get(key) != value:
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} artifact manifest {key} differs"
            )
    if manifest.get("status") not in {None, "PASS"}:
        raise FinalConsolidationError(
            f"Prompt-{prompt_index} artifact manifest status is not PASS"
        )
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise FinalConsolidationError(
            f"Prompt-{prompt_index} artifact manifest is empty"
        )
    direct: list[ArtifactEvidence] = []
    for index, raw in enumerate(raw_artifacts):
        if not isinstance(raw, Mapping) or raw.get("required") is not True:
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} artifact {index} is not required"
            )
        artifact = _verified_ref(raw, f"Prompt-{prompt_index} artifact {index}")
        direct.append(
            ArtifactEvidence(
                prompt_index=prompt_index,
                path=artifact,
                sha256=sha256_file(artifact),
                binding="universal_artifact_manifest",
                binding_path=manifest_path,
            )
        )
    direct_paths_list = [item.path for item in direct]
    if len(direct_paths_list) != len(set(direct_paths_list)):
        raise FinalConsolidationError(
            f"Prompt-{prompt_index} artifact manifest contains duplicate paths"
        )

    gate_refs = record.get("gate_records")
    if not isinstance(gate_refs, Mapping) or set(gate_refs) != set(GATES):
        raise FinalConsolidationError(
            f"Prompt-{prompt_index} exact universal gate set differs"
        )
    direct_paths = {item.path for item in direct}
    for gate_name in GATES:
        raw = gate_refs[gate_name]
        if not isinstance(raw, Mapping):
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} {gate_name} reference is invalid"
            )
        gate_path = _verified_ref(raw, f"Prompt-{prompt_index} {gate_name}")
        if gate_path not in direct_paths:
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} {gate_name} is absent from its artifact manifest"
            )
        gate = read_json(gate_path)
        for key, value in {
            "schema_version": GATE_SCHEMA,
            **scope_fields(),
            "prompt_index": prompt_index,
            "gate": gate_name,
            "status": "PASS",
        }.items():
            if gate.get(key) != value:
                raise FinalConsolidationError(
                    f"Prompt-{prompt_index} {gate_name} gate {key} differs"
                )

    expanded = _expand_checksum_inventories(prompt_index, direct)
    all_artifacts = tuple(_dedupe_artifacts([*direct, *expanded]))
    for basename in required_basenames:
        matches = tuple(item for item in all_artifacts if item.path.name == basename)
        direct_matches = tuple(
            item for item in matches if item.binding == "universal_artifact_manifest"
        )
        authoritative = direct_matches or matches
        if len(authoritative) != 1:
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} needs exactly one authoritative {basename}; "
                f"found {len(authoritative)}"
            )
    return CompletionEvidence(
        prompt_index=prompt_index,
        marker=marker,
        path=completion_path,
        sha256=sha256_file(completion_path),
        record=record,
        manifest_path=manifest_path,
        manifest_sha256=sha256_file(manifest_path),
        artifacts=all_artifacts,
    )


def validate_prerequisites(
    *,
    prompt7_marker: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    execution_policy_path: Path | str = DEFAULT_EXECUTION_POLICY_ADDENDUM,
    adapter_registry_path: Path | str = DEFAULT_ADAPTER_REGISTRY,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    matrix_path: Path | str = DEFAULT_MATRIX,
    runtime_path: Path | str = DEFAULT_RUNTIME,
    license_document_path: Path | str = DEFAULT_LICENSE_DOCUMENT,
    expected_prompt8_adapter_id: str | None = None,
    expected_prompt8_adapter_contract_sha256: str | None = None,
) -> EvidenceBundle:
    """Validate the exact P4->P7 chain without reading scientific outcomes first."""

    raw_paths: dict[int, Path] = {
        7: ensure_c(prompt7_marker, label="Prompt-7 completion", must_exist=True)
    }
    raw_records: dict[int, dict[str, Any]] = {7: read_json(raw_paths[7])}
    for prompt in (7, 6, 5):
        predecessor = raw_records[prompt].get("predecessor")
        if not isinstance(predecessor, Mapping):
            raise FinalConsolidationError(
                f"Prompt-{prompt} completion lacks a predecessor binding"
            )
        expected_prompt = prompt - 1
        if (
            predecessor.get("prompt_index") != expected_prompt
            or predecessor.get("completion_marker")
            != COMPLETION_MARKERS[expected_prompt]
        ):
            raise FinalConsolidationError(
                f"Prompt-{prompt} predecessor marker/index differs"
            )
        path = ensure_c(
            str(predecessor.get("completion_record_path") or ""),
            label=f"Prompt-{expected_prompt} predecessor completion",
            must_exist=True,
        )
        if str(
            predecessor.get("completion_record_sha256") or ""
        ).casefold() != sha256_file(path):
            raise FinalConsolidationError(
                f"Prompt-{prompt} predecessor completion hash differs"
            )
        raw_paths[expected_prompt] = path
        raw_records[expected_prompt] = read_json(path)
    if raw_records[4].get("predecessor") is not None:
        raise FinalConsolidationError("Prompt-4 predecessor must be null")

    completions = {
        prompt: validate_completion(
            raw_paths[prompt],
            prompt_index=prompt,
            marker=COMPLETION_MARKERS[prompt],
            required_basenames=REQUIRED_STAGE_BASENAMES[prompt],
        )
        for prompt in (4, 5, 6, 7)
    }
    _validate_chain(completions)

    amendment = ensure_c(amendment_path, label="eight-day amendment", must_exist=True)
    _validate_amendment(read_json(amendment))
    execution_policy_file = ensure_c(
        execution_policy_path, label="execution-policy addendum", must_exist=True
    )
    execution_policy = read_json(execution_policy_file)
    _validate_execution_policy(
        execution_policy,
        amendment_path=amendment,
    )
    adapter_registry = ensure_c(
        adapter_registry_path, label="eight-day adapter registry", must_exist=True
    )
    pi_deployment_steering_file = ensure_c(
        pi_deployment_steering_path,
        label="Raspberry Pi deployment steering",
        must_exist=True,
    )
    try:
        pi_deployment_steering = load_deployment_steering(
            pi_deployment_steering_file,
            expected_prompt_index=8,
        )
    except DeploymentEvidenceError as exc:
        raise FinalConsolidationError(
            f"Raspberry Pi deployment steering validation failed: {exc}"
        ) from exc
    state_path = ensure_c(
        program_state_path, label="full-pipeline PROGRAM_STATE", must_exist=True
    )
    state_snapshot = read_json(state_path)
    _validate_program_state(state_snapshot, completions)
    matrix_file = ensure_c(matrix_path, label="pipeline matrix", must_exist=True)
    runtime_file = ensure_c(runtime_path, label="runtime config", must_exist=True)
    matrix = FullPipelineMatrix(matrix_file, runtime_file)
    pipeline_ids = tuple(matrix.pipeline_ids)
    if len(pipeline_ids) != 18 or len(set(pipeline_ids)) != 18:
        raise FinalConsolidationError("authoritative matrix is not exact all-18")
    license_file = ensure_c(
        license_document_path, label="license/asset manifest", must_exist=True
    )
    if not license_file.is_file():
        raise FinalConsolidationError("license/asset manifest is not a file")
    _validate_adapter_bindings(
        adapter_registry,
        completions=completions,
        amendment_path=amendment,
        execution_policy_path=execution_policy_file,
        pi_deployment_steering_path=pi_deployment_steering_file,
        program_state_path=state_path,
        matrix_path=matrix_file,
        runtime_path=runtime_file,
        license_document_path=license_file,
        expected_prompt8_adapter_id=expected_prompt8_adapter_id,
        expected_prompt8_adapter_contract_sha256=(
            expected_prompt8_adapter_contract_sha256
        ),
    )

    frozen = _validate_frozen_policies(
        completions[4],
        pipeline_ids,
        matrix_path=matrix_file,
        runtime_path=runtime_file,
    )
    _validate_stage_tables(completions, pipeline_ids, frozen)
    _validate_prompt5_live_evidence(completions[5])
    selected_ids = _validate_catalog(
        completions[7].one("production_candidate_catalog.yaml"),
        pipeline_ids=pipeline_ids,
    )
    extended_ids = _extended_ids(frozen, pipeline_ids)
    _validate_licensing_record(
        completions[6].one("licensing_provenance.json"),
        6,
        expected_pipeline_ids=extended_ids,
        license_document=license_file,
        matrix_path=matrix_file,
    )
    _validate_licensing_record(
        completions[7].one("licensing_provenance.json"),
        7,
        expected_pipeline_ids=selected_ids,
        license_document=license_file,
        matrix_path=matrix_file,
    )
    try:
        validate_prompt7_completion(
            workspace_root=completions[7].path.parent,
            completion_record_path=completions[7].path,
            program_state_path=state_path,
            expected_adapter_id=str(completions[7].record["adapter_id"]),
            expected_adapter_contract_sha256=str(
                completions[7].record["adapter_contract_sha256"]
            ),
        )
    except Exception as exc:
        raise ProductionCandidateError(
            f"established Prompt-7 completion validation failed: {exc}"
        ) from exc
    return EvidenceBundle(
        completions=completions,
        program_state_path=state_path,
        program_state_sha256=sha256_file(state_path),
        amendment_path=amendment,
        amendment_sha256=sha256_file(amendment),
        execution_policy_path=execution_policy_file,
        execution_policy_sha256=sha256_file(execution_policy_file),
        execution_policy=execution_policy,
        adapter_registry_path=adapter_registry,
        adapter_registry_sha256=sha256_file(adapter_registry),
        pi_deployment_steering_path=pi_deployment_steering_file,
        pi_deployment_steering_sha256=sha256_file(pi_deployment_steering_file),
        pi_deployment_steering=pi_deployment_steering,
        program_state_snapshot=state_snapshot,
        matrix_path=matrix_file,
        matrix_sha256=sha256_file(matrix_file),
        runtime_path=runtime_file,
        runtime_sha256=sha256_file(runtime_file),
        license_document_path=license_file,
        license_document_sha256=sha256_file(license_file),
        pipeline_ids=pipeline_ids,
        frozen_policy_refs=frozen,
    )


def _expand_checksum_inventories(
    prompt_index: int, direct: Sequence[ArtifactEvidence]
) -> list[ArtifactEvidence]:
    expanded: list[ArtifactEvidence] = []
    for item in direct:
        if item.path.name != "checksums.json":
            continue
        document = read_json(item.path)
        entries = document.get("entries")
        if not isinstance(entries, Mapping) or not entries:
            raise FinalConsolidationError(
                f"checksum inventory has no nonempty entries mapping: {item.path}"
            )
        root = item.path.parent.resolve(strict=True)
        for relative, expected in entries.items():
            relative_path = Path(str(relative))
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise FinalConsolidationError(
                    f"unsafe relative path in checksum inventory {item.path}: {relative}"
                )
            path = ensure_c(
                root / relative_path,
                label=f"Prompt-{prompt_index} checksummed artifact",
                must_exist=True,
            )
            if not path.is_file() or not path.is_relative_to(root):
                raise FinalConsolidationError(
                    f"checksum inventory entry escapes/is not a file: {path}"
                )
            actual = sha256_file(path)
            if str(expected).casefold() != actual:
                raise FinalConsolidationError(
                    f"checksum inventory mismatch: {item.path} -> {relative}"
                )
            expanded.append(
                ArtifactEvidence(
                    prompt_index=prompt_index,
                    path=path,
                    sha256=actual,
                    binding="checksums.json",
                    binding_path=item.path,
                )
            )
    return expanded


def _dedupe_artifacts(values: Sequence[ArtifactEvidence]) -> list[ArtifactEvidence]:
    result: list[ArtifactEvidence] = []
    seen: set[tuple[Path, str]] = set()
    for value in values:
        key = (value.path, value.sha256)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _validate_chain(completions: Mapping[int, CompletionEvidence]) -> None:
    for prompt in (5, 6, 7):
        predecessor = completions[prompt].record.get("predecessor")
        assert isinstance(predecessor, Mapping)
        previous = completions[prompt - 1]
        expected = {
            "prompt_index": prompt - 1,
            "completion_marker": previous.marker,
            "completion_record_sha256": previous.sha256,
        }
        for key, value in expected.items():
            if predecessor.get(key) != value:
                raise FinalConsolidationError(
                    f"Prompt-{prompt} predecessor {key} differs"
                )
        bound = ensure_c(
            str(predecessor.get("completion_record_path") or ""),
            label=f"Prompt-{prompt} predecessor path",
            must_exist=True,
        )
        if bound != previous.path:
            raise FinalConsolidationError(
                f"Prompt-{prompt} predecessor path differs after resolution"
            )


def _validate_amendment(value: Mapping[str, object]) -> None:
    if value.get("amendment_id") != SCOPE_ID:
        raise FinalConsolidationError("eight-day amendment ID differs")
    scope = value.get("scope")
    storage = value.get("storage_policy")
    markers = value.get("completion_markers")
    labels = value.get("required_artifact_labels")
    if not all(isinstance(item, Mapping) for item in (scope, storage, markers, labels)):
        raise FinalConsolidationError("eight-day amendment sections are absent")
    assert isinstance(scope, Mapping)
    assert isinstance(storage, Mapping)
    assert isinstance(markers, Mapping)
    assert isinstance(labels, Mapping)
    budgets = scope.get("stage_budget_hours")
    if (
        scope.get("scope_class") != SCOPE_CLASS
        or int(scope.get("total_wall_target_hours") or 0) != 192
        or not isinstance(budgets, Mapping)
        or float(budgets.get("prompt_8") or 0) != 4.0
    ):
        raise FinalConsolidationError("Prompt-8 amended scope/budget differs")
    if (
        storage.get("allowed_drive") != "C:\\"
        or storage.get("other_drives_allowed") is not False
        or int(storage.get("minimum_free_space_reserve_gib") or 0) != 35
    ):
        raise FinalConsolidationError("amendment C:-only/35-GiB policy differs")
    for prompt, marker in COMPLETION_MARKERS.items():
        if markers.get(f"prompt_{prompt}") != marker:
            raise FinalConsolidationError(
                f"amendment Prompt-{prompt} completion marker differs"
            )
    if (
        labels.get("scope_id") != SCOPE_ID
        or labels.get("original_full_scope_complete") is not False
    ):
        raise FinalConsolidationError("amendment bounded output labels differ")


def _validate_execution_policy(
    value: Mapping[str, object], *, amendment_path: Path
) -> None:
    expected_top = {
        "schema_version": "full-pipeline-execution-policy-addendum.v1",
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "scientific_scope_or_firewall_changed": False,
        "panel_membership_changed": False,
        "frozen_policy_changed": False,
        "storage_boundary_changed": False,
        "worker_health_timeouts_retained": True,
        "allowed_drive": "C:\\",
        "minimum_free_space_reserve_gib": 35,
        "original_amendment_sha256": sha256_file(amendment_path),
    }
    for key, expected in expected_top.items():
        if value.get(key) != expected:
            raise FinalConsolidationError(
                f"execution-policy addendum {key} differs: {value.get(key)!r}"
            )
    if (
        value.get("authorized_by") != "user"
        or not str(value.get("authorized_at_utc") or "").strip()
        or not str(value.get("reason") or "").strip()
        or set(str(item) for item in value.get("supersedes_only", []))
        != {"elapsed_time_termination", "elapsed_time_admission_denial"}
    ):
        raise FinalConsolidationError(
            "execution-policy authorization/supersession contract differs"
        )
    if list(value.get("applies_to_prompt_indices") or []) != [4, 5, 6, 7, 8]:
        raise FinalConsolidationError("execution-policy prompt coverage differs")
    planning = value.get("planning_target")
    policy = value.get("execution_policy")
    if not isinstance(planning, Mapping) or not isinstance(policy, Mapping):
        raise FinalConsolidationError(
            "execution-policy planning/policy sections are absent"
        )
    expected_hours = {
        "prompt_4": 48,
        "prompt_5": 60,
        "prompt_6": 30,
        "prompt_7": 12,
        "prompt_8": 4,
    }
    stage_hours = planning.get("stage_hours")
    if (
        int(planning.get("total_hours") or 0) != 192
        or not isinstance(stage_hours, Mapping)
        or dict(stage_hours) != expected_hours
        or int(planning.get("shared_contingency_hours") or -1) != 38
        or planning.get("interpretation") != "ADVISORY_ETA_TARGET_ONLY"
    ):
        raise FinalConsolidationError(
            "execution-policy advisory planning targets differ"
        )
    if (
        policy.get("policy_id") != "ADVISORY_ONLY_NO_AUTOMATIC_STOP"
        or policy.get("elapsed_time_kill_switch_enabled") is not False
        or policy.get("elapsed_time_admission_gate_enabled") is not False
        or policy.get("continue_healthy_execution_after_target") is not True
        or policy.get("automatic_transition_after_valid_completion") is not True
    ):
        raise FinalConsolidationError("execution-policy advisory semantics differ")
    retained = set(
        str(item) for item in value.get("stop_or_pause_conditions_retained", [])
    )
    required_retained = {
        "explicit_operator_stop",
        "c_drive_free_space_reserve_breach",
        "genuine_stage_failure",
        "invalid_prerequisite_or_scientific_hash_gate",
    }
    if retained != required_retained:
        raise FinalConsolidationError(
            "execution-policy retained stop conditions differ"
        )


def _validate_adapter_bindings(
    path: Path,
    *,
    completions: Mapping[int, CompletionEvidence],
    amendment_path: Path,
    execution_policy_path: Path,
    pi_deployment_steering_path: Path,
    program_state_path: Path,
    matrix_path: Path,
    runtime_path: Path,
    license_document_path: Path,
    expected_prompt8_adapter_id: str | None,
    expected_prompt8_adapter_contract_sha256: str | None,
) -> None:
    try:
        configuration = load_adapter_configuration(path)
    except ProgramContractError as exc:
        raise FinalConsolidationError(
            f"invalid eight-day adapter registry: {exc}"
        ) from exc
    for prompt in (4, 5, 6, 7):
        adapter = configuration.stages[prompt]
        completion = completions[prompt]
        if adapter.readiness != "READY":
            raise FinalConsolidationError(f"Prompt-{prompt} adapter is not READY")
        if completion.record.get("adapter_id") != adapter.adapter_id:
            raise FinalConsolidationError(
                f"Prompt-{prompt} adapter ID differs from registry"
            )
        if completion.record.get("adapter_contract_sha256") != adapter.contract_sha256:
            raise FinalConsolidationError(
                f"Prompt-{prompt} adapter contract differs from registry"
            )
    prompt8 = configuration.stages[8]
    if prompt8.readiness != "READY":
        raise FinalConsolidationError("Prompt-8 adapter is not READY")
    if (
        expected_prompt8_adapter_id
        and prompt8.adapter_id != expected_prompt8_adapter_id
    ):
        raise FinalConsolidationError("Prompt-8 adapter ID differs from registry")
    if (
        expected_prompt8_adapter_contract_sha256
        and prompt8.contract_sha256
        != expected_prompt8_adapter_contract_sha256.casefold()
    ):
        raise FinalConsolidationError("Prompt-8 adapter contract differs from registry")
    expected_inputs = {
        *(completion.path for completion in completions.values()),
        amendment_path,
        execution_policy_path,
        pi_deployment_steering_path,
        path,
        program_state_path,
        matrix_path,
        runtime_path,
        license_document_path,
    }
    observed_inputs = set(prompt8.material_paths.get("inputs", ()))
    if observed_inputs != expected_inputs:
        raise FinalConsolidationError(
            "Prompt-8 adapter inputs are not the exact narrow authority set"
        )
    if (
        prompt8.stage_workspace is None
        or prompt8.completion_record is None
        or prompt8.progress_record is None
        or prompt8.controller_log is None
        or set(prompt8.material_paths.get("workspaces", ()))
        != {prompt8.stage_workspace}
        or set(prompt8.material_paths.get("temporary", ()))
        != {prompt8.stage_workspace / "temp"}
        or set(prompt8.material_paths.get("logs", ()))
        != {prompt8.controller_log, prompt8.progress_record}
        or prompt8.material_paths.get("caches")
        or prompt8.material_paths.get("results")
        or prompt8.material_paths.get("checkpoints")
    ):
        raise FinalConsolidationError(
            "Prompt-8 adapter workspace/cache/model material paths differ"
        )
    declared = {item for values in prompt8.material_paths.values() for item in values}
    if configuration.evaluation_tool_root in declared:
        raise FinalConsolidationError(
            "Prompt-8 adapter broadly declares the entire evaluation tool root"
        )
    if (
        prompt8.completion_record not in set(prompt8.material_paths.get("packages", ()))
        or not prompt8.material_paths.get("reports")
        or not prompt8.material_paths.get("packages")
    ):
        raise FinalConsolidationError(
            "Prompt-8 adapter report/package material paths are incomplete"
        )


def _validate_program_state(
    value: Mapping[str, object], completions: Mapping[int, CompletionEvidence]
) -> None:
    if (
        value.get("schema_version") != "just-peachy-full-pipeline-program-state.v1"
        or value.get("status") != COMPLETION_MARKERS[7]
        or value.get("scope_id") != SCOPE_ID
        or value.get("scope_class") != SCOPE_CLASS
        or value.get("original_full_scope_complete") is not False
        or value.get("remaining_prompt_status") != "PENDING_AUTOMATIC"
    ):
        raise FinalConsolidationError("PROGRAM_STATE has not reached bounded Prompt 7")
    if int(value.get("current_prompt_index") or -1) != 7:
        raise FinalConsolidationError("PROGRAM_STATE current_prompt_index is not 7")
    if [int(item) for item in value.get("remaining_prompt_indices", [])] != [8]:
        raise FinalConsolidationError("PROGRAM_STATE remaining prompts are not [8]")
    completion_state = value.get("completion_state")
    if not isinstance(completion_state, Mapping):
        raise FinalConsolidationError("PROGRAM_STATE completion_state is absent")
    for prompt in (4, 5, 6, 7):
        expected = {
            f"prompt_{prompt}": COMPLETION_MARKERS[prompt],
            f"prompt_{prompt}_scope_id": SCOPE_ID,
            f"prompt_{prompt}_original_full_scope_complete": False,
        }
        for key, item in expected.items():
            if completion_state.get(key) != item:
                raise FinalConsolidationError(f"PROGRAM_STATE {key} differs")
        completion = completions[prompt]
        if value.get(f"prompt_{prompt}_completion_record") != str(completion.path):
            raise FinalConsolidationError(
                f"PROGRAM_STATE Prompt-{prompt} completion path differs"
            )
        if value.get(f"prompt_{prompt}_completion_record_sha256") != completion.sha256:
            raise FinalConsolidationError(
                f"PROGRAM_STATE Prompt-{prompt} completion hash differs"
            )


def _validate_frozen_policies(
    prompt4: CompletionEvidence,
    pipeline_ids: Sequence[str],
    *,
    matrix_path: Path,
    runtime_path: Path,
) -> dict[str, Mapping[str, object]]:
    raw = prompt4.record.get("artifacts")
    if not isinstance(raw, Mapping):
        raise FinalConsolidationError("Prompt-4 native frozen artifacts are absent")
    required = {
        "frozen_pipeline_configs",
        "decision_policy_registry",
        "extended_set",
        "development_summary",
    }
    if not required.issubset(raw):
        raise FinalConsolidationError(
            "Prompt-4 native frozen artifacts are incomplete: "
            + ", ".join(sorted(required - set(raw)))
        )
    result: dict[str, Mapping[str, object]] = {}
    for key in sorted(required - {"frozen_pipeline_configs"}):
        ref = raw[key]
        if not isinstance(ref, Mapping):
            raise FinalConsolidationError(f"Prompt-4 {key} reference is invalid")
        path = _verified_ref(ref, f"Prompt-4 {key}")
        result[key] = {"path": str(path), "sha256": sha256_file(path)}
    registry_path = Path(str(result["decision_policy_registry"]["path"]))
    registry_document = read_json(registry_path)
    try:
        validate_development_policy_registry(registry_document)
    except Exception as exc:
        raise FinalConsolidationError(
            f"Prompt-4 decision-policy registry is invalid: {exc}"
        ) from exc
    extended_document = load_yaml(Path(str(result["extended_set"]["path"])))
    extended_ids = [
        str(item) for item in extended_document.get("extended_pipeline_ids", [])
    ]
    if (
        len(extended_ids) != len(set(extended_ids))
        or not 6 <= len(extended_ids) <= 8
        or not set(MANDATORY_EXTENDED_ANCHORS).issubset(extended_ids)
        or set(extended_ids) - set(pipeline_ids)
    ):
        raise FinalConsolidationError(
            "frozen extended set is outside the mandatory six-plus-two contract"
        )
    frozen = raw["frozen_pipeline_configs"]
    if not isinstance(frozen, Mapping):
        raise FinalConsolidationError("Prompt-4 frozen config reference is invalid")
    root = ensure_c(
        str(frozen.get("path") or ""), label="frozen pipeline configs", must_exist=True
    )
    checksums = ensure_c(
        str(frozen.get("checksums_path") or ""),
        label="frozen pipeline checksums",
        must_exist=True,
    )
    if not root.is_dir() or checksums.parent != root:
        raise FinalConsolidationError("frozen pipeline config layout differs")
    checksum_sha = sha256_file(checksums)
    if (
        frozen.get("checksums_sha256") != checksum_sha
        or frozen.get("sha256") != checksum_sha
    ):
        raise FinalConsolidationError("frozen pipeline checksum document differs")
    configs = sorted(root.glob("*.yaml"))
    if len(configs) != 18 or {path.stem for path in configs} != set(pipeline_ids):
        raise FinalConsolidationError("frozen pipeline configs are not exact all-18")
    checksum_doc = read_json(checksums)
    entries = checksum_doc.get("entries")
    if not isinstance(entries, Mapping):
        raise FinalConsolidationError("frozen pipeline checksum inventory is absent")
    matrix = FullPipelineMatrix(matrix_path, runtime_path)
    freeze_ids: dict[str, str] = {}
    for config in configs:
        relative = config.relative_to(root).as_posix()
        if entries.get(relative) != sha256_file(config):
            raise FinalConsolidationError(f"frozen config hash differs: {config.name}")
        value = load_yaml(config)
        unsigned = dict(value)
        freeze_identity = str(unsigned.pop("freeze_identity_sha256", "")).casefold()
        if freeze_identity != sha256_bytes(canonical_json_bytes(unsigned)):
            raise FinalConsolidationError(
                f"frozen config identity differs: {config.name}"
            )
        selection = matrix.resolve(config.stem)
        expected_fields = {
            "schema_version": "full-pipeline-development-config-freeze.v1",
            "status": "IMMUTABLE_DEVELOPMENT_FREEZE",
            "pipeline_id": config.stem,
            "pipeline_config_sha256_before_development_freeze": (
                selection.pipeline_config_sha256
            ),
            "evaluation_material_inspected": False,
            "evaluation_retuning_allowed": False,
            "production_winner_selected": False,
        }
        for key, expected in expected_fields.items():
            if value.get(key) != expected:
                raise FinalConsolidationError(
                    f"frozen config {config.name} {key} differs"
                )
        source_hashes = value.get("source_hashes")
        if not isinstance(source_hashes, Mapping) or (
            source_hashes.get("matrix_sha256") != sha256_file(matrix_path)
            or source_hashes.get("runtime_config_sha256") != sha256_file(runtime_path)
            or source_hashes.get("development_policy_registry_sha256")
            != registry_document.get("registry_identity_sha256")
        ):
            raise FinalConsolidationError(
                f"frozen config {config.name} source hashes differ"
            )
        for section in ("identity_policy", "model_assets", "result_affecting_code"):
            if not isinstance(value.get(section), Mapping) or not value.get(section):
                raise FinalConsolidationError(
                    f"frozen config {config.name} lacks {section} identity"
                )
        freeze_ids[config.stem] = freeze_identity
    result["frozen_pipeline_configs"] = {
        "path": str(root),
        "checksums_path": str(checksums),
        "checksums_sha256": checksum_sha,
        "pipeline_count": 18,
        "pipeline_freeze_identity_sha256s": dict(sorted(freeze_ids.items())),
    }
    return result


def _validate_stage_tables(
    completions: Mapping[int, CompletionEvidence],
    pipeline_ids: Sequence[str],
    frozen: Mapping[str, Mapping[str, object]],
) -> None:
    expected = tuple(sorted(str(item) for item in pipeline_ids))
    for name in ("development_matrix.csv", "development_summary.csv"):
        _validate_pipeline_table(
            completions[4].one(name), expected, label=f"Prompt-4 {name}", exact_one=True
        )

    p5_exact = (
        "all18_finalist_summary.csv",
        "all18_asr.csv",
        "all18_diarization.csv",
        "all18_identity.csv",
        "all18_speaker_attributed_transcript.csv",
        "all18_streaming.csv",
        "all18_resources.csv",
    )
    for name in p5_exact:
        _validate_pipeline_table(
            completions[5].one(name), expected, label=f"Prompt-5 {name}", exact_one=True
        )
    for name in ("all18_failures.csv", "bootstrap_intervals.csv"):
        _validate_pipeline_table(
            completions[5].one(name),
            expected,
            label=f"Prompt-5 {name}",
            exact_one=False,
        )
    if not read_csv(completions[5].one("paired_comparisons.csv")):
        raise FinalConsolidationError("Prompt-5 paired comparisons are empty")
    _validate_prompt5_authorization(completions, frozen)

    extended = _extended_ids(frozen, pipeline_ids)
    _validate_pipeline_table(
        completions[6].one("extended_summary.csv"),
        extended,
        label="Prompt-6 extended_summary.csv",
        exact_one=True,
    )
    for name in (
        "true_streaming_asr.csv",
        "online_diarization.csv",
        "online_identity.csv",
        "ux_latency.csv",
        "label_revision.csv",
        "long_session_results.csv",
        "reliability_results.csv",
        "serial_resources.csv",
    ):
        _validate_pipeline_table(
            completions[6].one(name),
            extended,
            label=f"Prompt-6 {name}",
            exact_one=False,
        )
    _validate_pipeline_table(
        completions[6].one("native_results.csv"),
        extended,
        label="Prompt-6 native_results.csv",
        exact_one=False,
        allow_partial=True,
    )
    analysis = read_json(completions[6].one("analysis.json"))
    _require_scope(analysis, label="Prompt-6 analysis")
    if analysis.get("status") != "PASS":
        raise FinalConsolidationError("Prompt-6 analysis status is not PASS")
    try:
        validate_prompt6_hardening_manifest(
            read_json(completions[6].one("hardening_input_manifest.json"))
        )
    except Exception as exc:
        raise FinalConsolidationError(
            f"Prompt-6 hardening-input validation failed: {exc}"
        ) from exc


def _validate_prompt5_live_evidence(completion: CompletionEvidence) -> None:
    """Reuse Prompt-5's established terminal/collection gates after state advanced."""

    paths = prompt5_layout(completion.path.parent)
    try:
        validate_prompt5_terminal_jobs(paths.accuracy, expected_job_count=126)
        validate_prompt5_terminal_jobs(paths.resources, expected_job_count=18)
        collection = read_json(paths.root / "collection.json")
        package_root = ensure_c(
            str(collection.get("destination") or ""),
            label="canonical Prompt-5 report",
            must_exist=True,
        )
        validate_prompt5_collection(package_root, collection)
    except Exception as exc:
        raise FinalConsolidationError(
            f"established Prompt-5 live-evidence validation failed: {exc}"
        ) from exc


def _validate_pipeline_table(
    path: Path,
    expected_pipeline_ids: Sequence[str],
    *,
    label: str,
    exact_one: bool,
    allow_partial: bool = False,
) -> None:
    rows = read_csv(path)
    if not rows:
        raise FinalConsolidationError(f"{label} is empty")
    expected = set(expected_pipeline_ids)
    observed_values = [
        str(row.get("pipeline_id") or row.get("preset_id") or "") for row in rows
    ]
    observed = {value for value in observed_values if value}
    if (
        not observed
        or observed - expected
        or (not allow_partial and observed != expected)
    ):
        raise FinalConsolidationError(
            f"{label} pipeline coverage differs: expected={sorted(expected)}, "
            f"observed={sorted(observed)}"
        )
    if exact_one and (
        len(rows) != len(expected) or len(observed_values) != len(observed)
    ):
        raise FinalConsolidationError(f"{label} is not exactly one row per pipeline")
    for row in rows:
        _require_scope(row, label=label)


def _extended_ids(
    frozen: Mapping[str, Mapping[str, object]], pipeline_ids: Sequence[str]
) -> tuple[str, ...]:
    document = load_yaml(Path(str(frozen["extended_set"]["path"])))
    values = tuple(str(item) for item in document.get("extended_pipeline_ids", []))
    if (
        len(values) != len(set(values))
        or not 6 <= len(values) <= 8
        or not set(MANDATORY_EXTENDED_ANCHORS).issubset(values)
        or set(values) - set(pipeline_ids)
    ):
        raise FinalConsolidationError("frozen extended set differs")
    return tuple(sorted(values))


def _validate_prompt5_authorization(
    completions: Mapping[int, CompletionEvidence],
    frozen: Mapping[str, Mapping[str, object]],
) -> None:
    path = completions[5].one("prompt5_authorization.json")
    value = read_json(path)
    _require_scope(value, label="Prompt-5 authorization")
    if (
        value.get("schema_version") != "full-pipeline-core-evaluation-authorization.v1"
        or value.get("status") != "AUTHORIZED_NOT_STARTED"
        or int(value.get("pipeline_count") or 0) != 18
        or value.get("held_out_predictions_inspected") is not False
        or value.get("held_out_inference_started") is not False
        or value.get("retuning_allowed") is not False
    ):
        raise FinalConsolidationError("Prompt-5 authorization contract differs")
    unsigned = dict(value)
    identity = str(unsigned.pop("authorization_identity_sha256", "")).casefold()
    if identity != sha256_bytes(canonical_json_bytes(unsigned)):
        raise FinalConsolidationError("Prompt-5 authorization identity differs")
    p4 = completions[4]
    if (
        value.get("prompt4_marker_path") != str(p4.path)
        or value.get("prompt4_marker_sha256") != p4.sha256
    ):
        raise FinalConsolidationError("Prompt-5 authorization Prompt-4 binding differs")
    frozen_auth = value.get("frozen_pipeline_configs")
    expected_frozen = frozen["frozen_pipeline_configs"]
    if not isinstance(frozen_auth, Mapping) or (
        frozen_auth.get("checksums_sha256") != expected_frozen["checksums_sha256"]
        or frozen_auth.get("pipeline_count") != 18
        or frozen_auth.get("pipeline_freeze_identity_sha256s")
        != expected_frozen["pipeline_freeze_identity_sha256s"]
        or frozen_auth.get("execution_contract_validation") != "EXACT_LIVE_MATCH"
    ):
        raise FinalConsolidationError("Prompt-5 frozen execution attestation differs")
    registry = value.get("decision_policy_registry")
    expected_registry = frozen["decision_policy_registry"]
    if not isinstance(registry, Mapping) or (
        registry.get("path") != expected_registry["path"]
        or registry.get("sha256") != expected_registry["sha256"]
    ):
        raise FinalConsolidationError("Prompt-5 decision registry binding differs")


def _validate_licensing_record(
    path: Path,
    prompt_index: int,
    *,
    expected_pipeline_ids: Sequence[str],
    license_document: Path,
    matrix_path: Path,
) -> None:
    value = read_json(path)
    _require_scope(value, label=f"Prompt-{prompt_index} licensing provenance")
    expected_ids = set(expected_pipeline_ids)
    if prompt_index == 6:
        if (
            value.get("schema_version")
            != "full-pipeline-extended-licensing-provenance.v1"
            or value.get("status")
            != "BOUND_EXISTING_DECLARATIONS_NO_NEW_LEGAL_CONCLUSION"
            or value.get("source_manifest_path") != str(license_document)
            or value.get("source_manifest_sha256") != sha256_file(license_document)
            or value.get("matrix_path") != str(matrix_path)
            or value.get("matrix_sha256") != sha256_file(matrix_path)
        ):
            raise FinalConsolidationError(
                "Prompt-6 licensing authority binding differs"
            )
        rows = value.get("pipelines")
    else:
        if (
            value.get("schema_version")
            != "full-pipeline-production-licensing-provenance.v1"
        ):
            raise FinalConsolidationError("Prompt-7 licensing schema differs")
        license_ref = value.get("license_document")
        if not isinstance(license_ref, Mapping) or (
            license_ref.get("path") != str(license_document)
            or license_ref.get("sha256") != sha256_file(license_document)
            or value.get("technical_ranking_used_as_legal_conclusion") is not False
            or not str(value.get("repository_redistribution_status") or "").strip()
        ):
            raise FinalConsolidationError(
                "Prompt-7 licensing authority binding differs"
            )
        rows = value.get("candidates")
    if not isinstance(rows, list):
        raise FinalConsolidationError(
            f"Prompt-{prompt_index} licensing rows are absent"
        )
    observed: list[str] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} licensing row is invalid"
            )
        pipeline_id = str(raw.get("pipeline_id") or raw.get("technical_id") or "")
        observed.append(pipeline_id)
        if prompt_index == 6:
            required_statuses = (
                raw.get("asr_license_deployment_status"),
                raw.get("diarization_embedding_license_deployment_status"),
                raw.get("identity_license_deployment_status"),
            )
        else:
            required_statuses = (
                raw.get("license_status"),
                raw.get("repository_redistribution_status"),
            )
        if any(not str(item or "").strip() for item in required_statuses):
            raise FinalConsolidationError(
                f"Prompt-{prompt_index} licensing status is incomplete: {pipeline_id}"
            )
    if len(observed) != len(set(observed)) or set(observed) != expected_ids:
        raise FinalConsolidationError(
            f"Prompt-{prompt_index} licensing pipeline coverage differs"
        )


def _validate_catalog(path: Path, *, pipeline_ids: Sequence[str]) -> tuple[str, ...]:
    value = load_yaml(path)
    _require_scope(value, label="Prompt-7 production catalog")
    if (
        value.get("schema_version") != "full-pipeline-production-candidate-catalog.v1"
        or value.get("status") != "PASS"
        or value.get("technical_and_licensing_rankings_separate") is not True
        or value.get("weighted_score_used") is not False
        or value.get("final_beaker_hardware_readiness_claimed") is not False
    ):
        raise ProductionCandidateError("Prompt-7 production catalog contract differs")
    roles = value.get("roles")
    candidates = value.get("candidates")
    if not isinstance(roles, Mapping) or not isinstance(candidates, list):
        raise ProductionCandidateError("Prompt-7 catalog roles/candidates are absent")
    selected = tuple(str(item) for item in roles.values() if item)
    if (
        not 1 <= len(selected) <= 3
        or len(selected) != len(set(selected))
        or set(selected) - set(pipeline_ids)
        or roles.get("PRIMARY") is None
    ):
        raise ProductionCandidateError("Prompt-7 selected role set differs")
    rows: dict[str, Mapping[str, object]] = {}
    for raw in candidates:
        if not isinstance(raw, Mapping):
            raise ProductionCandidateError("Prompt-7 candidate row is invalid")
        pipeline_id = str(raw.get("pipeline_id") or raw.get("technical_id") or "")
        if not pipeline_id or pipeline_id in rows:
            raise ProductionCandidateError(
                "Prompt-7 candidate IDs are absent/duplicated"
            )
        rows[pipeline_id] = raw
    if set(rows) != set(selected) or int(value.get("candidate_count") or -1) != len(
        selected
    ):
        raise ProductionCandidateError("Prompt-7 catalog candidate coverage differs")
    for pipeline_id, row in rows.items():
        if (
            row.get("software_ready") is not True
            or row.get("production_role_eligible") is not True
            or row.get("runtime_binding_status") != "BOUND_FROZEN_ANCHOR"
            or row.get("unknown_only_policy_executed") is not False
            or not str(row.get("license_status") or "").strip()
            or not str(row.get("repository_redistribution_status") or "").strip()
        ):
            raise ProductionCandidateError(
                f"Prompt-7 candidate is not software-ready/fail-closed: {pipeline_id}"
            )
        bundle = ensure_c(
            str(row.get("bundle_path") or ""),
            label=f"Prompt-7 candidate bundle {pipeline_id}",
            must_exist=True,
        )
        checksum = bundle / "checksums.json"
        if (
            not bundle.is_dir()
            or not checksum.is_file()
            or row.get("bundle_checksums_sha256") != sha256_file(checksum)
        ):
            raise ProductionCandidateError(
                f"Prompt-7 candidate bundle binding differs: {pipeline_id}"
            )
    return tuple(sorted(selected))


def _require_scope(value: Mapping[str, object], *, label: str) -> None:
    if (
        value.get("scope_id") != SCOPE_ID
        or value.get("scope_class") != SCOPE_CLASS
        or value.get("original_full_scope_complete") is not False
    ):
        raise FinalConsolidationError(f"{label} bounded scope differs")


def load_yaml(path: Path | str) -> Mapping[str, object]:
    resolved = ensure_c(path, label="YAML evidence", must_exist=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(value, Mapping):
        raise FinalConsolidationError(f"YAML root must be an object: {resolved}")
    return value


def _verified_ref(raw: Mapping[str, object], label: str) -> Path:
    path = ensure_c(str(raw.get("path") or ""), label=label, must_exist=True)
    if not path.is_file():
        raise FinalConsolidationError(f"{label} is not a file: {path}")
    if str(raw.get("sha256") or "").casefold() != sha256_file(path):
        raise FinalConsolidationError(f"{label} SHA-256 differs: {path}")
    return path


def _require_sha(value: object, label: str) -> None:
    text = str(value or "").casefold()
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise FinalConsolidationError(f"{label} is not a SHA-256 digest")


__all__ = [
    "ArtifactEvidence",
    "CompletionEvidence",
    "EvidenceBundle",
    "load_yaml",
    "validate_completion",
    "validate_prerequisites",
]
