"""Idempotent Prompt-8 controller: validate, analyze, package, and complete."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Mapping

from app.full_pipeline_eight_day_program.storage import ControllerLock
from app.full_pipeline_eight_day_program.contracts import load_adapter_configuration
from app.full_pipeline_eight_day_program.storage import ProgramContractError

from . import (
    COMPLETION_MARKERS,
    DEFAULT_ADAPTER_REGISTRY,
    DEFAULT_AMENDMENT,
    DEFAULT_EXECUTION_POLICY_ADDENDUM,
    DEFAULT_LICENSE_DOCUMENT,
    DEFAULT_MATRIX,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_ROOT,
    DEFAULT_RUNTIME,
    DEFAULT_ZIP,
    FINAL_OUTPUTS,
    RESERVED_ORIGINAL_MARKER,
    SCOPE_ID,
    scope_fields,
)
from .analysis import analyze_failures, result_inventory
from .evidence import (
    CompletionEvidence,
    EvidenceBundle,
    validate_completion,
    validate_prerequisites,
)
from .io import (
    FinalConsolidationError,
    IncompleteEvidenceError,
    ProductionCandidateError,
    artifact_ref,
    blocked_status,
    canonical_json_bytes,
    deterministic_zip,
    ensure_c,
    read_json,
    read_csv,
    sha256_bytes,
    sha256_file,
    storage_guard,
    validate_zip,
    write_csv_atomic,
    write_json_atomic,
)
from .pi_handoff import build_pi_handoff, validate_pi_handoff
from .ranking import MATRIX_PRIORITY_CONTRACT, build_rankings
from .reports import write_markdown_reports, write_reproducibility_manifest


@dataclass(frozen=True)
class Layout:
    root: Path
    output_root: Path
    zip_path: Path
    progress: Path
    stop_request: Path
    stop_acknowledged: Path
    lock: Path
    input_binding: Path
    gates: Path
    artifact_manifest: Path
    completion: Path
    failure: Path
    superseded_failure: Path
    pre_state_snapshot: Path


def layout(
    root: Path | str = DEFAULT_ROOT,
    *,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    zip_path: Path | str = DEFAULT_ZIP,
    completion_record: Path | str | None = None,
    progress_record: Path | str | None = None,
) -> Layout:
    base = ensure_c(root, label="Prompt-8 workspace")
    output = ensure_c(output_root, label="Prompt-8 final report root")
    package = ensure_c(zip_path, label="Prompt-8 final ZIP")
    completion_raw = (
        completion_record
        or os.environ.get("JP8_COMPLETION_RECORD")
        or base / "completion_marker.json"
    )
    progress_raw = (
        progress_record
        or os.environ.get("JP8_PROGRESS_RECORD")
        or base / "program_progress.json"
    )
    return Layout(
        root=base,
        output_root=output,
        zip_path=package,
        progress=ensure_c(progress_raw, label="Prompt-8 progress"),
        stop_request=base / "stop_requested.json",
        stop_acknowledged=base / "stop_acknowledged.json",
        lock=base / "prompt8_controller.lock",
        input_binding=base / "input_binding.json",
        gates=base / "gate_records",
        artifact_manifest=base / "artifact_manifest.json",
        completion=ensure_c(completion_raw, label="Prompt-8 completion record"),
        failure=base / "failure.json",
        superseded_failure=base / "failure_superseded_by_completion.json",
        pre_state_snapshot=base / "program_state_before_prompt8.json",
    )


def run_all(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    zip_path: Path | str = DEFAULT_ZIP,
    prompt7_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    execution_policy_path: Path | str = DEFAULT_EXECUTION_POLICY_ADDENDUM,
    adapter_registry_path: Path | str = DEFAULT_ADAPTER_REGISTRY,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    matrix_path: Path | str = DEFAULT_MATRIX,
    runtime_path: Path | str = DEFAULT_RUNTIME,
    license_document_path: Path | str = DEFAULT_LICENSE_DOCUMENT,
    completion_record: Path | str | None = None,
    progress_record: Path | str | None = None,
) -> dict[str, object]:
    paths = layout(
        workspace_root,
        output_root=output_root,
        zip_path=zip_path,
        completion_record=completion_record,
        progress_record=progress_record,
    )
    paths.root.mkdir(parents=True, exist_ok=True)
    marker = prompt7_marker or os.environ.get("JP8_PREDECESSOR_COMPLETION_PATH")
    if not marker:
        raise FinalConsolidationError(
            "Prompt-7 completion is required via -Prompt7Marker or "
            "JP8_PREDECESSOR_COMPLETION_PATH"
        )
    marker_path = ensure_c(marker, label="Prompt-7 completion", must_exist=True)

    lock = ControllerLock(paths.lock, state_path=paths.progress)
    lock.acquire()
    try:
        # Recover the narrow crash window where completion was durable but
        # PROGRAM_STATE/progress cleanup had not yet advanced. Recovery is kept under
        # the same controller lock as a fresh run.
        if paths.completion.is_file():
            _validate_runtime_material_layout(adapter_registry_path, paths)
            adapter_id, adapter_sha = _adapter_identity(adapter_registry_path)
            validated = validate_final_completion(
                workspace_root=paths.root,
                output_root=paths.output_root,
                zip_path=paths.zip_path,
                completion_record=paths.completion,
                prompt7_marker=marker_path,
                program_state_path=program_state_path,
                adapter_registry_path=adapter_registry_path,
                pi_deployment_steering_path=pi_deployment_steering_path,
                require_program_state=False,
            )
            _update_program_state(
                ensure_c(program_state_path, label="PROGRAM_STATE", must_exist=True),
                completion_path=paths.completion,
                completion=read_json(paths.completion),
                expected_pre_state_sha256=_bound_pre_state_sha256(paths.input_binding),
            )
            final = validate_final_completion(
                workspace_root=paths.root,
                output_root=paths.output_root,
                zip_path=paths.zip_path,
                completion_record=paths.completion,
                prompt7_marker=marker_path,
                program_state_path=program_state_path,
                adapter_registry_path=adapter_registry_path,
                pi_deployment_steering_path=pi_deployment_steering_path,
                expected_adapter_id=adapter_id,
                expected_adapter_contract_sha256=adapter_sha,
            )
            _supersede_failure(paths)
            _acknowledge_stop(paths, disposition="ALREADY_COMPLETE")
            _progress(
                paths,
                100.0,
                "COMPLETE",
                COMPLETION_MARKERS[8],
                0,
                status="COMPLETE",
            )
            return final | {
                "recovered_or_reused": True,
                "prior_validation": validated,
            }

        _check_stop(paths)
        storage = storage_guard(paths.root)
        write_json_atomic(paths.root / "storage_status.json", storage)
        _progress(paths, 2.0, "PREFLIGHT", "C:-only 35-GiB storage guard passed", 900)
        _check_stop(paths)

        _validate_runtime_material_layout(adapter_registry_path, paths)
        adapter_id, adapter_sha = _adapter_identity(adapter_registry_path)
        try:
            bundle = validate_prerequisites(
                prompt7_marker=marker_path,
                amendment_path=amendment_path,
                execution_policy_path=execution_policy_path,
                adapter_registry_path=adapter_registry_path,
                pi_deployment_steering_path=pi_deployment_steering_path,
                program_state_path=program_state_path,
                matrix_path=matrix_path,
                runtime_path=runtime_path,
                license_document_path=license_document_path,
                expected_prompt8_adapter_id=adapter_id,
                expected_prompt8_adapter_contract_sha256=adapter_sha,
            )
        except ProductionCandidateError:
            raise
        except Exception as exc:
            raise IncompleteEvidenceError(
                f"Prompt 4-7 prerequisite evidence failed: {exc}"
            ) from exc
        _write_immutable_snapshot(
            paths.pre_state_snapshot, bundle.program_state_snapshot
        )
        binding = _input_binding(bundle, snapshot_path=paths.pre_state_snapshot)
        write_json_atomic(paths.input_binding, binding)
        _progress(
            paths,
            20.0,
            "VALIDATE_EVIDENCE",
            "P4-P7 chain, policies, inventories, failures, and licensing validated",
            720,
        )
        lock.heartbeat()
        _check_stop(paths)

        inventory = result_inventory(
            bundle,
            authority_paths=(
                (bundle.amendment_path, "amendment_authority"),
                (bundle.execution_policy_path, "execution_policy_authority"),
                (bundle.adapter_registry_path, "adapter_registry_authority"),
                (
                    bundle.pi_deployment_steering_path,
                    "raspberry_pi_deployment_steering_authority",
                ),
                (bundle.matrix_path, "matrix_authority"),
                (bundle.runtime_path, "runtime_authority"),
                (bundle.license_document_path, "licensing_authority"),
                (paths.pre_state_snapshot, "immutable_pre_prompt8_state"),
            ),
        )
        write_csv_atomic(paths.output_root / "RESULT_FILE_INVENTORY.csv", inventory)
        _progress(
            paths,
            35.0,
            "INVENTORY",
            f"{len(inventory)} source artifacts inventoried",
            540,
        )
        _check_stop(paths)

        rankings = build_rankings(bundle)
        write_csv_atomic(
            paths.output_root / "FINAL_PIPELINE_RANKING.csv", rankings.rows
        )
        write_csv_atomic(
            paths.output_root / "PIPELINE_PARETO_FRONTIER.csv", rankings.pareto_rows
        )
        _progress(
            paths, 55.0, "RANK", "separate rankings and Pareto frontier complete", 420
        )
        lock.heartbeat()
        _check_stop(paths)

        failures = analyze_failures(bundle, rankings)
        pi_handoff = build_pi_handoff(bundle, rankings)
        write_json_atomic(
            paths.output_root / "RASPBERRY_PI_DEPLOYMENT_HANDOFF.json", pi_handoff
        )
        write_markdown_reports(
            output_root=paths.output_root,
            workspace_root=paths.root,
            bundle=bundle,
            rankings=rankings,
            failures=failures,
            inventory_rows=inventory,
            pi_handoff=pi_handoff,
        )
        _progress(
            paths,
            73.0,
            "ANALYZE",
            "failure, fine-tuning, XVF, and final reports written",
            300,
        )
        _check_stop(paths)

        write_reproducibility_manifest(
            output_root=paths.output_root,
            bundle=bundle,
            rankings=rankings,
            inventory_rows=inventory,
            pre_state_snapshot_path=paths.pre_state_snapshot,
        )
        _validate_final_outputs(paths.output_root)
        deterministic_zip(paths.zip_path, root=paths.output_root, members=FINAL_OUTPUTS)
        validate_zip(
            paths.zip_path, expected_members=FINAL_OUTPUTS, root=paths.output_root
        )
        _progress(paths, 88.0, "PACKAGE", "compact allowlisted ZIP validated", 120)
        _check_stop(paths)

        gates = _write_gates(
            paths=paths,
            bundle=bundle,
            rankings=rankings,
            failures=failures,
        )
        manifest_ref = _write_artifact_manifest(paths, bundle, gates)
        completion = _completion_document(
            paths=paths,
            bundle=bundle,
            rankings=rankings,
            failures=failures,
            artifact_manifest=manifest_ref,
            gates=gates,
        )
        write_json_atomic(paths.completion, completion)
        _update_program_state(
            ensure_c(program_state_path, label="PROGRAM_STATE", must_exist=True),
            completion_path=paths.completion,
            completion=completion,
            expected_pre_state_sha256=bundle.program_state_sha256,
        )
        validated = validate_final_completion(
            workspace_root=paths.root,
            output_root=paths.output_root,
            zip_path=paths.zip_path,
            completion_record=paths.completion,
            prompt7_marker=marker_path,
            program_state_path=program_state_path,
            adapter_registry_path=adapter_registry_path,
            pi_deployment_steering_path=pi_deployment_steering_path,
            expected_adapter_id=_adapter_identity(adapter_registry_path)[0],
            expected_adapter_contract_sha256=_adapter_identity(adapter_registry_path)[
                1
            ],
        )
        _progress(
            paths,
            100.0,
            "COMPLETE",
            COMPLETION_MARKERS[8],
            0,
            status="COMPLETE",
        )
        _supersede_failure(paths)
        _acknowledge_stop(paths, disposition="COMPLETED")
        return validated
    except StopRequested as exc:
        _acknowledge_stop(paths, disposition="STOPPED_BEFORE_COMPLETION")
        _progress(paths, 0.0, "STOPPED", str(exc), None, status="STOPPED")
        return {
            "schema_version": "full-pipeline-final-consolidation-result.v1",
            **scope_fields(),
            "status": "STOPPED",
            "completion_marker_emitted": False,
        }
    except Exception as exc:
        terminal_status = blocked_status(exc)
        write_json_atomic(
            paths.failure,
            {
                "schema_version": "full-pipeline-final-consolidation-failure.v1",
                **scope_fields(),
                "status": terminal_status,
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "completion_marker_emitted": False,
            },
        )
        _progress(
            paths,
            0.0,
            terminal_status,
            str(exc),
            None,
            status=terminal_status,
        )
        raise
    finally:
        lock.release()


def request_stop(*, workspace_root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    paths.root.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": "full-pipeline-final-consolidation-stop-request.v1",
        **scope_fields(),
        "status": "STOP_REQUESTED",
        "requested_at_utc": _utc_now(),
    }
    write_json_atomic(paths.stop_request, value)
    return value


def status(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    zip_path: Path | str = DEFAULT_ZIP,
    completion_record: Path | str | None = None,
    progress_record: Path | str | None = None,
) -> dict[str, object]:
    paths = layout(
        workspace_root,
        output_root=output_root,
        zip_path=zip_path,
        completion_record=completion_record,
        progress_record=progress_record,
    )
    if paths.progress.is_file():
        return read_json(paths.progress)
    return {
        "schema_version": "full-pipeline-final-consolidation-progress.v1",
        **scope_fields(),
        "status": "NOT_STARTED",
        "overall_percentage": 0.0,
        "eta_seconds": None,
        "phase": "NOT_STARTED",
        "detail": "Prompt 8 has not started",
        "completion_record": str(paths.completion),
    }


def validate_final_completion(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    zip_path: Path | str = DEFAULT_ZIP,
    completion_record: Path | str | None = None,
    prompt7_marker: Path | str | None = None,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    adapter_registry_path: Path | str = DEFAULT_ADAPTER_REGISTRY,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    expected_adapter_id: str | None = None,
    expected_adapter_contract_sha256: str | None = None,
    require_program_state: bool = True,
) -> dict[str, object]:
    paths = layout(
        workspace_root,
        output_root=output_root,
        zip_path=zip_path,
        completion_record=completion_record,
    )
    evidence = validate_completion(
        paths.completion,
        prompt_index=8,
        marker=COMPLETION_MARKERS[8],
        required_basenames=FINAL_OUTPUTS,
    )
    record = evidence.record
    _validate_input_binding(
        evidence=evidence,
        paths=paths,
        program_state_path=program_state_path,
        adapter_registry_path=adapter_registry_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    _validate_prompt8_gates(record, paths)
    _validate_runtime_material_layout(adapter_registry_path, paths)
    unsigned_completion = dict(record)
    completion_identity = str(
        unsigned_completion.pop("completion_identity_sha256", "")
    ).casefold()
    if completion_identity != sha256_bytes(canonical_json_bytes(unsigned_completion)):
        raise FinalConsolidationError("Prompt-8 completion identity differs")
    registered_id, registered_sha = _adapter_identity(adapter_registry_path)
    expected_adapter_id = expected_adapter_id or registered_id
    expected_adapter_contract_sha256 = (
        expected_adapter_contract_sha256 or registered_sha
    )
    if record.get("completion_marker") == RESERVED_ORIGINAL_MARKER:
        raise FinalConsolidationError("reserved original full-scope marker was emitted")
    if (
        expected_adapter_id is not None
        and record.get("adapter_id") != expected_adapter_id
    ):
        raise FinalConsolidationError("Prompt-8 adapter ID differs")
    if (
        expected_adapter_contract_sha256 is not None
        and record.get("adapter_contract_sha256")
        != expected_adapter_contract_sha256.casefold()
    ):
        raise FinalConsolidationError("Prompt-8 adapter contract hash differs")
    predecessor = record.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise FinalConsolidationError("Prompt-8 predecessor binding is absent")
    p7_raw = prompt7_marker or predecessor.get("completion_record_path")
    p7 = ensure_c(p7_raw, label="Prompt-7 predecessor", must_exist=True)
    if (
        predecessor.get("prompt_index") != 7
        or predecessor.get("completion_marker") != COMPLETION_MARKERS[7]
        or predecessor.get("completion_record_sha256") != sha256_file(p7)
        or ensure_c(
            str(predecessor.get("completion_record_path") or ""),
            label="bound Prompt-7 predecessor",
            must_exist=True,
        )
        != p7
    ):
        raise FinalConsolidationError("Prompt-8 predecessor binding differs")
    _validate_final_outputs(paths.output_root)
    validate_zip(paths.zip_path, expected_members=FINAL_OUTPUTS, root=paths.output_root)
    native = record.get("native_completion")
    if not isinstance(native, Mapping):
        raise FinalConsolidationError("Prompt-8 native_completion is absent")
    if (
        native.get("compact_zip_path") != str(paths.zip_path)
        or native.get("compact_zip_sha256") != sha256_file(paths.zip_path)
        or native.get("pipeline_count") != 18
        or native.get("weighted_composite_score_used") is not False
        or native.get("time_target_policy") != "ADVISORY_ONLY_NO_AUTOMATIC_STOP"
        or native.get("elapsed_time_kill_switch_enabled") is not False
        or native.get("raw_datasets_included") is not False
        or native.get("model_weights_included") is not False
        or native.get("credentials_included") is not False
        or native.get("large_caches_included") is not False
        or native.get("fine_tuning_decision")
        not in {
            "NO_FINE_TUNING_CURRENTLY_JUSTIFIED",
            "ASR_TARGET_ADAPTATION_CANDIDATE",
            "SPEAKER_EMBEDDING_SHORT_DURATION_CANDIDATE",
            "SEGMENTATION_REAL_DEVICE_DATA_REQUIRED",
            "POLICY_CHANGE_ONLY",
        }
    ):
        raise FinalConsolidationError("Prompt-8 native completion summary differs")
    if require_program_state:
        state = read_json(
            ensure_c(program_state_path, label="PROGRAM_STATE", must_exist=True)
        )
        _validate_final_state(state, paths.completion)
    return {
        "schema_version": "full-pipeline-final-consolidation-validation.v1",
        **scope_fields(),
        "status": "PASS",
        "completion_marker": COMPLETION_MARKERS[8],
        "completion_record": str(paths.completion),
        "completion_record_sha256": sha256_file(paths.completion),
        "compact_zip_path": str(paths.zip_path),
        "compact_zip_sha256": sha256_file(paths.zip_path),
        "primary": native.get("primary"),
        "fallback": native.get("fallback"),
        "alternative": native.get("alternative"),
        "not_worth_continuing": native.get("not_worth_continuing"),
        "major_failure": native.get("major_failure"),
        "fine_tuning_decision": native.get("fine_tuning_decision"),
        "remaining_xvf_work": "IMPLEMENT_ADAPTER_CAPTURE_REAL_DEVICE_DATA_RUN_FROZEN_ABLATIONS",
    }


def _input_binding(bundle: EvidenceBundle, *, snapshot_path: Path) -> dict[str, object]:
    core = {
        "schema_version": "full-pipeline-final-consolidation-input-binding.v1",
        **scope_fields(),
        "status": "PASS",
        "completion_chain": [
            {
                "prompt_index": prompt,
                "completion_marker": completion.marker,
                "path": str(completion.path),
                "sha256": completion.sha256,
                "artifact_manifest_path": str(completion.manifest_path),
                "artifact_manifest_sha256": completion.manifest_sha256,
                "artifact_count": len(completion.artifacts),
            }
            for prompt, completion in sorted(bundle.completions.items())
        ],
        "program_state_before_prompt8": {
            "path": str(bundle.program_state_path),
            "sha256": bundle.program_state_sha256,
            "snapshot": artifact_ref(snapshot_path),
            "embedded_document": dict(bundle.program_state_snapshot),
            "embedded_canonical_sha256": sha256_bytes(
                canonical_json_bytes(bundle.program_state_snapshot)
            ),
        },
        "amendment": artifact_ref(bundle.amendment_path),
        "execution_policy_addendum": {
            **artifact_ref(bundle.execution_policy_path),
            "embedded_document": dict(bundle.execution_policy),
            "embedded_canonical_sha256": sha256_bytes(
                canonical_json_bytes(bundle.execution_policy)
            ),
        },
        "adapter_registry": artifact_ref(bundle.adapter_registry_path),
        "raspberry_pi_deployment_steering": {
            **artifact_ref(bundle.pi_deployment_steering_path),
            "embedded_document": dict(bundle.pi_deployment_steering),
            "embedded_canonical_sha256": sha256_bytes(
                canonical_json_bytes(bundle.pi_deployment_steering)
            ),
        },
        "matrix": artifact_ref(bundle.matrix_path),
        "runtime": artifact_ref(bundle.runtime_path),
        "license_document": artifact_ref(bundle.license_document_path),
        "frozen_policy_refs": bundle.frozen_policy_refs,
        "pipeline_count": len(bundle.pipeline_ids),
        "scientific_outcomes_changed": False,
        "prompt7_roles_reselected": False,
    }
    return {**core, "binding_identity_sha256": sha256_bytes(canonical_json_bytes(core))}


def _validate_input_binding(
    *,
    evidence: CompletionEvidence,
    paths: Layout,
    program_state_path: Path | str,
    adapter_registry_path: Path | str,
    pi_deployment_steering_path: Path | str,
) -> None:
    matches = evidence.matches("input_binding.json")
    if len(matches) != 1 or matches[0].path != paths.input_binding:
        raise FinalConsolidationError(
            "Prompt-8 completion does not bind exactly one canonical input binding"
        )
    value = read_json(paths.input_binding)
    unsigned = dict(value)
    identity = str(unsigned.pop("binding_identity_sha256", "")).casefold()
    if identity != sha256_bytes(canonical_json_bytes(unsigned)):
        raise FinalConsolidationError("Prompt-8 input binding identity differs")
    _require_final_scope(value, label="Prompt-8 input binding")
    if (
        value.get("schema_version")
        != "full-pipeline-final-consolidation-input-binding.v1"
        or value.get("status") != "PASS"
        or int(value.get("pipeline_count") or 0) != 18
        or value.get("scientific_outcomes_changed") is not False
        or value.get("prompt7_roles_reselected") is not False
        or not isinstance(value.get("frozen_policy_refs"), Mapping)
        or not value.get("frozen_policy_refs")
    ):
        raise FinalConsolidationError("Prompt-8 input binding contract differs")
    chain = value.get("completion_chain")
    if not isinstance(chain, list) or len(chain) != 4:
        raise FinalConsolidationError("Prompt-8 input completion chain differs")
    observed_prompts: set[int] = set()
    for raw in chain:
        if not isinstance(raw, Mapping):
            raise FinalConsolidationError("Prompt-8 input completion row is invalid")
        prompt = int(raw.get("prompt_index") or -1)
        observed_prompts.add(prompt)
        completion_path = ensure_c(
            str(raw.get("path") or ""),
            label=f"Prompt-{prompt} bound completion",
            must_exist=True,
        )
        manifest_path = ensure_c(
            str(raw.get("artifact_manifest_path") or ""),
            label=f"Prompt-{prompt} bound artifact manifest",
            must_exist=True,
        )
        if (
            raw.get("completion_marker") != COMPLETION_MARKERS.get(prompt)
            or str(raw.get("sha256") or "").casefold() != sha256_file(completion_path)
            or str(raw.get("artifact_manifest_sha256") or "").casefold()
            != sha256_file(manifest_path)
            or int(raw.get("artifact_count") or 0) <= 0
        ):
            raise FinalConsolidationError(
                f"Prompt-{prompt} input completion binding differs"
            )
    if observed_prompts != {4, 5, 6, 7}:
        raise FinalConsolidationError("Prompt-8 input completion prompts differ")

    state = value.get("program_state_before_prompt8")
    if not isinstance(state, Mapping):
        raise FinalConsolidationError("Prompt-8 pre-state input binding is absent")
    source_state_path = ensure_c(
        str(state.get("path") or ""),
        label="Prompt-8 bound PROGRAM_STATE",
        must_exist=True,
    )
    expected_state_path = ensure_c(
        program_state_path, label="PROGRAM_STATE", must_exist=True
    )
    digest = str(state.get("sha256") or "").casefold()
    snapshot_path = _validate_artifact_ref(
        state.get("snapshot"), label="immutable pre-Prompt-8 state snapshot"
    )
    embedded_state = state.get("embedded_document")
    if (
        source_state_path != expected_state_path
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or snapshot_path != paths.pre_state_snapshot
        or not isinstance(embedded_state, Mapping)
        or read_json(snapshot_path) != embedded_state
        or str(state.get("embedded_canonical_sha256") or "").casefold()
        != sha256_bytes(canonical_json_bytes(embedded_state))
        or embedded_state.get("status") != COMPLETION_MARKERS[7]
    ):
        raise FinalConsolidationError("Prompt-8 immutable pre-state binding differs")

    _validate_artifact_ref(value.get("amendment"), label="Prompt-8 amendment")
    _validate_embedded_authority(
        value.get("execution_policy_addendum"),
        label="execution-policy addendum",
    )
    adapter = _validate_artifact_ref(
        value.get("adapter_registry"), label="Prompt-8 adapter registry"
    )
    if adapter != ensure_c(
        adapter_registry_path, label="eight-day adapter registry", must_exist=True
    ):
        raise FinalConsolidationError("Prompt-8 adapter registry path differs")
    steering = _validate_embedded_authority(
        value.get("raspberry_pi_deployment_steering"),
        label="Raspberry Pi deployment steering",
    )
    if steering != ensure_c(
        pi_deployment_steering_path,
        label="Raspberry Pi deployment steering",
        must_exist=True,
    ):
        raise FinalConsolidationError(
            "Prompt-8 Raspberry Pi deployment steering path differs"
        )
    for key, label in (
        ("matrix", "Prompt-8 matrix"),
        ("runtime", "Prompt-8 runtime config"),
        ("license_document", "Prompt-8 license document"),
    ):
        _validate_artifact_ref(value.get(key), label=label)


def _validate_prompt8_gates(record: Mapping[str, object], paths: Layout) -> None:
    raw_refs = record.get("gate_records")
    if not isinstance(raw_refs, Mapping):
        raise FinalConsolidationError("Prompt-8 gate references are absent")
    gates: dict[str, Mapping[str, object]] = {}
    for name in ("hash_validation", "firewall_validation", "prerequisite_validation"):
        ref = raw_refs.get(name)
        path = _validate_artifact_ref(ref, label=f"Prompt-8 {name} gate")
        value = read_json(path)
        evidence = value.get("evidence")
        if not isinstance(evidence, Mapping):
            raise FinalConsolidationError(f"Prompt-8 {name} gate evidence is absent")
        gates[name] = evidence

    hashes = gates["hash_validation"]
    outputs = hashes.get("final_output_sha256s")
    if (
        hashes.get("p4_p7_completion_chain_validated") is not True
        or int(hashes.get("source_artifact_count") or 0) <= 0
        or not isinstance(outputs, Mapping)
        or set(outputs) != set(FINAL_OUTPUTS)
        or hashes.get("compact_zip_path") != str(paths.zip_path)
        or hashes.get("compact_zip_sha256") != sha256_file(paths.zip_path)
    ):
        raise FinalConsolidationError("Prompt-8 hash gate semantics differ")
    for name in FINAL_OUTPUTS:
        if str(outputs[name]).casefold() != sha256_file(paths.output_root / name):
            raise FinalConsolidationError(f"Prompt-8 hash gate output differs: {name}")

    firewall = gates["firewall_validation"]
    expected_firewall = {
        "bounded_reduced_scope": True,
        "original_full_scope_complete": False,
        "new_campaign_launched": False,
        "held_out_retuning_performed": False,
        "fine_tuning_performed": False,
        "xvf_implemented": False,
        "prompt7_roles_reselected": False,
        "weighted_composite_score_used": False,
    }
    if any(
        firewall.get(key) is not expected for key, expected in expected_firewall.items()
    ):
        raise FinalConsolidationError("Prompt-8 firewall gate semantics differ")

    prerequisite = gates["prerequisite_validation"]
    chain = prerequisite.get("completion_chain")
    if (
        not isinstance(chain, list)
        or len(chain) != 4
        or {
            int(row.get("prompt_index") or -1)
            for row in chain
            if isinstance(row, Mapping)
        }
        != {4, 5, 6, 7}
        or int(prerequisite.get("pipeline_count") or 0) != 18
        or int(prerequisite.get("failure_source_row_count") or -1) < 0
        or prerequisite.get("input_binding_path") != str(paths.input_binding)
        or prerequisite.get("input_binding_sha256") != sha256_file(paths.input_binding)
    ):
        raise FinalConsolidationError("Prompt-8 prerequisite gate semantics differ")
    for raw in chain:
        assert isinstance(raw, Mapping)
        prompt = int(raw["prompt_index"])
        path = ensure_c(
            str(raw.get("path") or ""),
            label=f"Prompt-{prompt} prerequisite completion",
            must_exist=True,
        )
        if raw.get("completion_marker") != COMPLETION_MARKERS[prompt] or raw.get(
            "sha256"
        ) != sha256_file(path):
            raise FinalConsolidationError(
                f"Prompt-{prompt} prerequisite gate binding differs"
            )


def _write_gates(
    *, paths: Layout, bundle, rankings, failures
) -> dict[str, dict[str, str]]:
    paths.gates.mkdir(parents=True, exist_ok=True)
    data = {
        "hash_validation": {
            "p4_p7_completion_chain_validated": True,
            "source_artifact_count": sum(
                len(value.artifacts) for value in bundle.completions.values()
            ),
            "final_output_sha256s": {
                name: sha256_file(paths.output_root / name) for name in FINAL_OUTPUTS
            },
            "compact_zip_path": str(paths.zip_path),
            "compact_zip_sha256": sha256_file(paths.zip_path),
        },
        "firewall_validation": {
            "bounded_reduced_scope": True,
            "original_full_scope_complete": False,
            "new_campaign_launched": False,
            "held_out_retuning_performed": False,
            "fine_tuning_performed": False,
            "xvf_implemented": False,
            "prompt7_roles_reselected": False,
            "weighted_composite_score_used": False,
        },
        "prerequisite_validation": {
            "completion_chain": [
                {
                    "prompt_index": prompt,
                    "completion_marker": value.marker,
                    "path": str(value.path),
                    "sha256": value.sha256,
                }
                for prompt, value in sorted(bundle.completions.items())
            ],
            "input_binding_path": str(paths.input_binding),
            "input_binding_sha256": sha256_file(paths.input_binding),
            "pipeline_count": len(rankings.rows),
            "failure_source_row_count": failures.source_row_count,
        },
    }
    result: dict[str, dict[str, str]] = {}
    for gate, evidence in data.items():
        path = paths.gates / f"{gate}.json"
        write_json_atomic(
            path,
            {
                "schema_version": "full-pipeline-eight-day-gate.v1",
                **scope_fields(),
                "prompt_index": 8,
                "gate": gate,
                "status": "PASS",
                "evidence": evidence,
            },
        )
        result[gate] = artifact_ref(path)
    return result


def _write_artifact_manifest(
    paths: Layout,
    bundle: EvidenceBundle,
    gates: Mapping[str, Mapping[str, str]],
) -> dict[str, str]:
    artifact_paths = [
        *(paths.output_root / name for name in FINAL_OUTPUTS),
        paths.zip_path,
        paths.input_binding,
        paths.pre_state_snapshot,
        bundle.amendment_path,
        bundle.execution_policy_path,
        bundle.adapter_registry_path,
        bundle.pi_deployment_steering_path,
        bundle.matrix_path,
        bundle.runtime_path,
        bundle.license_document_path,
        *(value.path for value in bundle.completions.values()),
        *(Path(value["path"]) for value in gates.values()),
    ]
    manifest = {
        "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
        **scope_fields(),
        "prompt_index": 8,
        "status": "PASS",
        "artifacts": [
            {**artifact_ref(path), "required": True}
            for path in _unique_paths(artifact_paths)
        ],
    }
    write_json_atomic(paths.artifact_manifest, manifest)
    return artifact_ref(paths.artifact_manifest)


def _completion_document(
    *, paths, bundle, rankings, failures, artifact_manifest, gates
):
    adapter_id, adapter_sha = _adapter_identity(bundle.adapter_registry_path)
    p7 = bundle.completions[7]
    core = {
        "schema_version": "full-pipeline-eight-day-stage-completion.v1",
        **scope_fields(),
        "prompt_index": 8,
        "status": "COMPLETE",
        "completion_marker": COMPLETION_MARKERS[8],
        "completed_at_utc": _utc_now(),
        "adapter_id": adapter_id,
        "adapter_contract_sha256": adapter_sha,
        "predecessor": {
            "prompt_index": 7,
            "completion_marker": p7.marker,
            "completion_record_path": str(p7.path),
            "completion_record_sha256": p7.sha256,
        },
        "artifact_manifest": dict(artifact_manifest),
        "gate_records": {key: dict(value) for key, value in gates.items()},
        "native_completion": {
            "pipeline_count": 18,
            "primary": rankings.primary,
            "fallback": rankings.fallback,
            "alternative": rankings.alternative,
            "not_worth_continuing": rankings.not_worth_continuing,
            "major_failure": failures.major_failure,
            "fine_tuning_decision": failures.fine_tuning_decision,
            "remaining_xvf_work": "IMPLEMENT_ADAPTER_CAPTURE_REAL_DEVICE_DATA_RUN_FROZEN_ABLATIONS",
            "compact_zip_path": str(paths.zip_path),
            "compact_zip_sha256": sha256_file(paths.zip_path),
            "weighted_composite_score_used": False,
            "time_target_policy": "ADVISORY_ONLY_NO_AUTOMATIC_STOP",
            "elapsed_time_kill_switch_enabled": False,
            "raw_datasets_included": False,
            "model_weights_included": False,
            "credentials_included": False,
            "large_caches_included": False,
        },
        "bounded_limitations": {
            "original_full_scope_complete": False,
            "real_beaker_xvf_performance_claimed": False,
            "commercial_license_clearance_claimed": False,
            "exhaustive_native_coverage_claimed": False,
        },
        "original_full_scope_completion_marker_emitted": False,
    }
    return {
        **core,
        "completion_identity_sha256": sha256_bytes(canonical_json_bytes(core)),
    }


def _update_program_state(
    path: Path,
    *,
    completion_path: Path,
    completion: Mapping[str, object],
    expected_pre_state_sha256: str,
) -> None:
    state = read_json(path)
    if state.get("status") == COMPLETION_MARKERS[8]:
        _validate_final_state(state, completion_path)
        return
    if sha256_file(path) != expected_pre_state_sha256:
        raise FinalConsolidationError(
            "PROGRAM_STATE changed after the immutable pre-Prompt-8 snapshot"
        )
    if state.get("status") != COMPLETION_MARKERS[7]:
        raise FinalConsolidationError("PROGRAM_STATE moved away from bounded Prompt 7")
    completion_state = dict(state.get("completion_state") or {})
    completion_state.update(
        {
            "prompt_8": COMPLETION_MARKERS[8],
            "prompt_8_scope_id": SCOPE_ID,
            "prompt_8_original_full_scope_complete": False,
        }
    )
    state.update(
        {
            "status": COMPLETION_MARKERS[8],
            "current_prompt_index": 8,
            "remaining_prompt_indices": [],
            "remaining_prompt_status": "COMPLETE_BOUNDED_REDUCED",
            "completion_state": completion_state,
            "prompt_8_completion_record": str(completion_path),
            "prompt_8_completion_record_sha256": sha256_file(completion_path),
            **scope_fields(),
            "original_full_scope_completion_marker_emitted": False,
            "final_compact_zip_path": completion["native_completion"][
                "compact_zip_path"
            ],
            "final_compact_zip_sha256": completion["native_completion"][
                "compact_zip_sha256"
            ],
        }
    )
    write_json_atomic(path, state)


def _write_immutable_snapshot(path: Path, document: Mapping[str, object]) -> None:
    expected = sha256_bytes(canonical_json_bytes(document))
    if path.is_file():
        existing = read_json(path)
        if sha256_bytes(canonical_json_bytes(existing)) != expected:
            raise FinalConsolidationError(
                "immutable pre-Prompt-8 PROGRAM_STATE snapshot differs"
            )
        return
    write_json_atomic(path, document)


def _bound_pre_state_sha256(path: Path) -> str:
    binding = read_json(path)
    raw = binding.get("program_state_before_prompt8")
    if not isinstance(raw, Mapping):
        raise FinalConsolidationError("Prompt-8 input binding lacks pre-state evidence")
    digest = str(raw.get("sha256") or "").casefold()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise FinalConsolidationError(
            "Prompt-8 input binding pre-state SHA-256 is invalid"
        )
    return digest


def _validate_final_state(value: Mapping[str, object], completion_path: Path) -> None:
    completion_document = read_json(completion_path)
    native = completion_document.get("native_completion")
    if not isinstance(native, Mapping):
        raise FinalConsolidationError("Prompt-8 completion native summary is absent")
    if (
        value.get("schema_version") != "just-peachy-full-pipeline-program-state.v1"
        or value.get("status") != COMPLETION_MARKERS[8]
        or int(value.get("current_prompt_index") or -1) != 8
        or list(value.get("remaining_prompt_indices") or []) != []
        or value.get("remaining_prompt_status") != "COMPLETE_BOUNDED_REDUCED"
        or value.get("scope_id") != SCOPE_ID
        or value.get("scope_class") != "BOUNDED_REDUCED"
        or value.get("original_full_scope_complete") is not False
        or value.get("original_full_scope_completion_marker_emitted") is not False
        or value.get("prompt_8_completion_record") != str(completion_path)
        or value.get("prompt_8_completion_record_sha256")
        != sha256_file(completion_path)
        or value.get("final_compact_zip_path") != native.get("compact_zip_path")
        or value.get("final_compact_zip_sha256") != native.get("compact_zip_sha256")
    ):
        raise FinalConsolidationError("PROGRAM_STATE bounded Prompt-8 binding differs")
    completion_state = value.get("completion_state")
    if not isinstance(completion_state, Mapping):
        raise FinalConsolidationError("PROGRAM_STATE completion_state is absent")
    for prompt in (4, 5, 6, 7, 8):
        expected = {
            f"prompt_{prompt}": COMPLETION_MARKERS[prompt],
            f"prompt_{prompt}_scope_id": SCOPE_ID,
            f"prompt_{prompt}_original_full_scope_complete": False,
        }
        for key, item in expected.items():
            if completion_state.get(key) != item:
                raise FinalConsolidationError(
                    f"PROGRAM_STATE completion_state {key} differs"
                )


def _validate_final_outputs(root: Path) -> None:
    root = ensure_c(root, label="final report root", must_exist=True)
    for name in FINAL_OUTPUTS:
        path = ensure_c(root / name, label=f"final output {name}", must_exist=True)
        if not path.is_file() or path.stat().st_size == 0:
            raise FinalConsolidationError(f"final output is missing/empty: {path}")
    observed_files = {path.name for path in root.iterdir() if path.is_file()}
    if observed_files != set(FINAL_OUTPUTS):
        raise FinalConsolidationError(
            "final report root must contain exactly the ten allowlisted outputs"
        )

    ranking_rows = read_csv(root / "FINAL_PIPELINE_RANKING.csv")
    pipeline_ids = {str(row.get("pipeline_id") or "") for row in ranking_rows}
    if len(ranking_rows) != 18 or len(pipeline_ids) != 18 or "" in pipeline_ids:
        raise FinalConsolidationError("FINAL_PIPELINE_RANKING.csv is not exact all-18")
    rank_fields = (
        "technical_performance_rank",
        "user_experience_safety_rank",
        "resource_efficiency_rank",
        "deployment_licensing_readiness_rank",
    )
    for field in rank_fields:
        try:
            observed = {int(str(row.get(field) or "")) for row in ranking_rows}
        except ValueError as exc:
            raise FinalConsolidationError(f"final ranking {field} is invalid") from exc
        if observed != set(range(1, 19)):
            raise FinalConsolidationError(
                f"final ranking {field} is not an exact 1..18 permutation"
            )
    selected_roles: dict[str, str] = {}
    for row in ranking_rows:
        _require_final_scope(row, label="final ranking row")
        if (
            row.get("schema_version") != "full-pipeline-final-ranking.v1"
            or str(row.get("weighted_composite_score") or "").strip()
            or row.get("p5_core_evidence") != "EXACT_ALL18_HELDOUT"
            or _csv_truth(row.get("p6_extended_metrics_used_in_all18_rank"))
            or row.get("technical_rank_method") != "ORDERED_LEXICOGRAPHIC_NO_COMPOSITE"
            or row.get("ux_rank_method") != "ORDERED_SAFETY_LEXICOGRAPHIC_NO_COMPOSITE"
            or row.get("resource_rank_method")
            != "ORDERED_SERIAL_RESOURCES_NO_COMPOSITE"
        ):
            raise FinalConsolidationError("final ranking policy semantics differ")
        license_evidence = _json_csv_mapping(
            row.get("component_license_evidence"),
            label="component license evidence",
        )
        license_values = [
            str(value).upper()
            for values in license_evidence.values()
            for value in (values if isinstance(values, list) else [values])
        ]
        try:
            review_count = int(str(row.get("component_license_review_count") or "0"))
        except ValueError as exc:
            raise FinalConsolidationError(
                "final ranking license review count is invalid"
            ) from exc
        review_required = _csv_truth(row.get("component_license_review_required"))
        if (
            "diarization_embedding" not in license_evidence
            or not license_evidence["diarization_embedding"]
            or review_required != (review_count > 0)
            or (
                any(
                    token in value
                    for value in license_values
                    for token in ("MISSING", "UNSUPPORTED")
                )
                and review_count <= 0
            )
        ):
            raise FinalConsolidationError(
                "final ranking licensing evidence/review semantics differ"
            )
        role = str(row.get("selected_role") or "").strip()
        if role:
            if (
                role not in {"PRIMARY", "FALLBACK", "ALTERNATIVE"}
                or role in selected_roles
            ):
                raise FinalConsolidationError("final ranking selected roles differ")
            if not _csv_truth(row.get("software_ready")):
                raise FinalConsolidationError(
                    "final ranking selected role is not software-ready"
                )
            selected_roles[role] = str(row["pipeline_id"])
    if "PRIMARY" not in selected_roles or not 1 <= len(selected_roles) <= 3:
        raise FinalConsolidationError("final ranking lacks a valid Prompt-7 role set")

    pareto_rows = read_csv(root / "PIPELINE_PARETO_FRONTIER.csv")
    pareto_ids = {str(row.get("pipeline_id") or "") for row in pareto_rows}
    if (
        len(pareto_rows) != 18
        or pareto_ids != pipeline_ids
        or not any(_csv_truth(row.get("on_frontier")) for row in pareto_rows)
    ):
        raise FinalConsolidationError("PIPELINE_PARETO_FRONTIER.csv semantics differ")
    for row in pareto_rows:
        _require_final_scope(row, label="Pareto row")
        if (
            row.get("schema_version") != "full-pipeline-final-pareto-frontier.v1"
            or _csv_truth(row.get("weighted_composite_score_used"))
            or not str(row.get("definition") or "").strip()
        ):
            raise FinalConsolidationError("Pareto row contract differs")

    final_report = (root / "FINAL_PIPELINE_REPORT.md").read_text(encoding="utf-8")
    for heading in (
        "### A. Technical performance",
        "### B. User-experience safety",
        "### C. Resource efficiency",
        "### D. Deployment/licensing review readiness",
        "### E. Overall recommendation",
    ):
        if heading not in final_report:
            raise FinalConsolidationError(
                f"FINAL_PIPELINE_REPORT.md lacks ranking view: {heading}"
            )
    if (
        "not a fifth composite rank" not in final_report
        or "P5 exact all-18" not in final_report
        or "P6 predeclared-extended" not in final_report
        or "## A. Desktop / software scientific ranking" not in final_report
        or "## B. Raspberry Pi / approximately 2-GB ARM candidate shortlist"
        not in final_report
        or "names no final Pi winner" not in final_report
        or "do not predict optimized ARM performance" not in final_report
    ):
        raise FinalConsolidationError("final report evidence/ranking boundary differs")

    pi_handoff = read_json(root / "RASPBERRY_PI_DEPLOYMENT_HANDOFF.json")
    steering_ref = pi_handoff.get("steering_authority")
    if not isinstance(steering_ref, Mapping):
        raise FinalConsolidationError("Pi handoff steering authority is absent")
    steering_path = _validate_artifact_ref(
        steering_ref, label="Pi handoff deployment steering"
    )
    validate_pi_handoff(pi_handoff, read_json(steering_path))

    failure_report = (root / "PIPELINE_FAILURE_ANALYSIS.md").read_text(encoding="utf-8")
    for heading in (
        "## Component propagation map",
        "## Measured error exposure",
        "## Terminal status inventory",
        "## Failed/missing records",
        "## Major failure",
    ):
        if heading not in failure_report:
            raise FinalConsolidationError(
                f"failure analysis lacks required section: {heading}"
            )

    fine_tuning = (root / "FINE_TUNING_CANDIDATES.md").read_text(encoding="utf-8")
    allowed_decisions = (
        "NO_FINE_TUNING_CURRENTLY_JUSTIFIED",
        "ASR_TARGET_ADAPTATION_CANDIDATE",
        "SPEAKER_EMBEDDING_SHORT_DURATION_CANDIDATE",
        "SEGMENTATION_REAL_DEVICE_DATA_REQUIRED",
        "POLICY_CHANGE_ONLY",
    )
    if sum(f"Decision: `{item}`" in fine_tuning for item in allowed_decisions) != 1:
        raise FinalConsolidationError("fine-tuning decision is absent or ambiguous")

    xvf = (root / "XVF3800_INTEGRATION_HANDOFF.md").read_text(encoding="utf-8")
    required_ablations = (
        "audio only",
        "audio + energy",
        "audio + AoA",
        "audio + energy + AoA",
        "processed XVF audio + metadata",
    )
    if any(item not in xvf for item in required_ablations):
        raise FinalConsolidationError("XVF handoff lacks a required frozen ablation")

    inventory_rows = read_csv(root / "RESULT_FILE_INVENTORY.csv")
    if not inventory_rows:
        raise FinalConsolidationError("RESULT_FILE_INVENTORY.csv is empty")
    authority_bindings = {
        "amendment_authority",
        "execution_policy_authority",
        "adapter_registry_authority",
        "raspberry_pi_deployment_steering_authority",
        "matrix_authority",
        "runtime_authority",
        "licensing_authority",
        "immutable_pre_prompt8_state",
    }
    observed_bindings = {str(row.get("binding") or "") for row in inventory_rows}
    if not authority_bindings.issubset(observed_bindings):
        raise FinalConsolidationError("result inventory lacks a Prompt-8 authority")
    for row in inventory_rows:
        _require_final_scope(row, label="result inventory row")
        path = ensure_c(
            str(row.get("path") or ""),
            label="result inventory artifact",
            must_exist=True,
        )
        if (
            row.get("schema_version") != "full-pipeline-final-result-file-inventory.v1"
            or not path.is_file()
            or str(row.get("sha256") or "").casefold() != sha256_file(path)
            or not _csv_truth(row.get("required"))
            or not _csv_truth(row.get("exists"))
            or not _csv_truth(row.get("hash_validated"))
            or _csv_truth(row.get("raw_payload_packaged"))
        ):
            raise FinalConsolidationError("result inventory row contract differs")

    manifest = read_json(root / "REPRODUCIBILITY_MANIFEST.json")
    _require_final_scope(manifest, label="reproducibility manifest")
    if (
        manifest.get("schema_version")
        != "full-pipeline-final-reproducibility-manifest.v1"
        or manifest.get("status") != "PASS"
        or manifest.get("completion_marker_on_success") != COMPLETION_MARKERS[8]
        or manifest.get("original_full_scope_marker_emitted") is not False
        or int(manifest.get("pipeline_count") or 0) != 18
        or set(manifest.get("pipeline_ids") or []) != pipeline_ids
        or manifest.get("source_inventory_all_hash_validated") is not True
    ):
        raise FinalConsolidationError("reproducibility manifest core contract differs")
    package = manifest.get("package_policy")
    scientific = manifest.get("scientific_actions")
    time_policy = manifest.get("execution_time_policy")
    selection_policy = manifest.get("selection_policy")
    priority_mapping = (
        selection_policy.get("technical_priority_metric_mapping")
        if isinstance(selection_policy, Mapping)
        else None
    )
    if (
        not isinstance(package, Mapping)
        or package.get("member_allowlist") != sorted(FINAL_OUTPUTS)
        or any(
            package.get(key) is not False
            for key in (
                "raw_datasets_included",
                "model_weights_included",
                "credentials_included",
                "large_caches_included",
                "biometric_vectors_included",
            )
        )
        or not isinstance(scientific, Mapping)
        or any(value is not False for value in scientific.values())
        or not isinstance(time_policy, Mapping)
        or time_policy.get("policy_id") != "ADVISORY_ONLY_NO_AUTOMATIC_STOP"
        or int(time_policy.get("total_planning_target_hours") or 0) != 192
        or int(time_policy.get("prompt8_planning_target_hours") or 0) != 4
        or time_policy.get("elapsed_time_kill_switch_enabled") is not False
        or time_policy.get("elapsed_time_admission_gate_enabled") is not False
        or not isinstance(selection_policy, Mapping)
        or selection_policy.get("weighted_score_used") is not False
        or selection_policy.get("p5_p6_p7_evidence_kept_separate") is not True
        or selection_policy.get(
            "production_roles_consumed_from_prompt7_without_reselection"
        )
        is not True
        or not isinstance(priority_mapping, list)
        or len(priority_mapping) != 12
        or tuple(
            (
                int(row.get("rank") or -1),
                str(row.get("matrix_metric") or ""),
                str(row.get("direction") or ""),
            )
            for row in priority_mapping
            if isinstance(row, Mapping)
        )
        != MATRIX_PRIORITY_CONTRACT
    ):
        raise FinalConsolidationError("reproducibility policy semantics differ")
    generated = manifest.get("generated_output_sha256s")
    prior_names = set(FINAL_OUTPUTS) - {"REPRODUCIBILITY_MANIFEST.json"}
    if not isinstance(generated, Mapping) or set(generated) != prior_names:
        raise FinalConsolidationError("reproducibility output hash inventory differs")
    for name in prior_names:
        if str(generated[name]).casefold() != sha256_file(root / name):
            raise FinalConsolidationError(
                f"reproducibility output hash differs: {name}"
            )
    authorities = manifest.get("authorities")
    if not isinstance(authorities, Mapping):
        raise FinalConsolidationError("reproducibility authorities are absent")
    for name in (
        "amendment",
        "adapter_registry",
        "matrix",
        "runtime",
        "license_and_asset_manifest",
    ):
        _validate_artifact_ref(authorities.get(name), label=f"manifest {name}")
    _validate_embedded_authority(
        authorities.get("raspberry_pi_deployment_steering"),
        label="Raspberry Pi deployment steering",
    )
    _validate_embedded_authority(
        authorities.get("execution_policy_addendum"),
        label="execution-policy addendum",
    )
    _validate_embedded_authority(
        authorities.get("program_state_before_prompt8"),
        label="pre-Prompt-8 state",
        ref_key="immutable_snapshot",
    )

    runbook = (root / "FINAL_RUNBOOK.md").read_text(encoding="utf-8")
    if (
        "advisory planning estimates only" not in runbook
        or "neither is an elapsed-time stop or admission gate" not in runbook
    ):
        raise FinalConsolidationError(
            "final runbook misstates the advisory time policy"
        )


def _require_final_scope(value: Mapping[str, object], *, label: str) -> None:
    if (
        value.get("scope_id") != SCOPE_ID
        or value.get("scope_class") != "BOUNDED_REDUCED"
        or not _csv_false(value.get("original_full_scope_complete"))
    ):
        raise FinalConsolidationError(f"{label} bounded scope differs")


def _csv_truth(value: object) -> bool:
    return value is True or str(value or "").strip().casefold() in {"true", "1", "yes"}


def _csv_false(value: object) -> bool:
    return value is False or str(value or "").strip().casefold() == "false"


def _json_csv_mapping(value: object, *, label: str) -> Mapping[str, object]:
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError as exc:
        raise FinalConsolidationError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise FinalConsolidationError(f"{label} is not a JSON object")
    return parsed


def _validate_artifact_ref(value: object, *, label: str) -> Path:
    if not isinstance(value, Mapping):
        raise FinalConsolidationError(f"{label} reference is absent")
    path = ensure_c(str(value.get("path") or ""), label=label, must_exist=True)
    if not path.is_file() or str(value.get("sha256") or "").casefold() != sha256_file(
        path
    ):
        raise FinalConsolidationError(f"{label} reference differs")
    return path


def _validate_embedded_authority(
    value: object,
    *,
    label: str,
    ref_key: str | None = None,
) -> Path:
    if not isinstance(value, Mapping):
        raise FinalConsolidationError(f"{label} authority is absent")
    if ref_key is None:
        path = _validate_artifact_ref(value, label=label)
    else:
        path = _validate_artifact_ref(value.get(ref_key), label=label)
    embedded = value.get("embedded_document")
    if not isinstance(embedded, Mapping) or read_json(path) != embedded:
        raise FinalConsolidationError(f"{label} embedded document differs")
    canonical_sha = sha256_bytes(canonical_json_bytes(embedded))
    if str(value.get("embedded_canonical_sha256") or "").casefold() != canonical_sha:
        raise FinalConsolidationError(f"{label} embedded canonical hash differs")
    if label == "execution-policy addendum":
        policy = embedded.get("execution_policy")
        planning = embedded.get("planning_target")
        stage_hours = (
            planning.get("stage_hours") if isinstance(planning, Mapping) else None
        )
        if (
            not isinstance(policy, Mapping)
            or policy.get("policy_id") != "ADVISORY_ONLY_NO_AUTOMATIC_STOP"
            or policy.get("elapsed_time_kill_switch_enabled") is not False
            or policy.get("elapsed_time_admission_gate_enabled") is not False
            or policy.get("continue_healthy_execution_after_target") is not True
            or not isinstance(planning, Mapping)
            or int(planning.get("total_hours") or 0) != 192
            or not isinstance(stage_hours, Mapping)
            or dict(stage_hours).get("prompt_8") != 4
        ):
            raise FinalConsolidationError(
                "execution-policy addendum advisory semantics differ"
            )
    return path


def _adapter_identity(
    adapter_registry_path: Path | str = DEFAULT_ADAPTER_REGISTRY,
) -> tuple[str, str]:
    try:
        configuration = load_adapter_configuration(
            ensure_c(
                adapter_registry_path,
                label="eight-day adapter registry",
                must_exist=True,
            )
        )
    except ProgramContractError as exc:
        raise FinalConsolidationError(
            f"invalid eight-day adapter registry: {exc}"
        ) from exc
    registered = configuration.stages[8]
    supplied_id = os.environ.get("JP8_ADAPTER_ID", "").strip()
    supplied_sha = os.environ.get("JP8_ADAPTER_CONTRACT_SHA256", "").strip().casefold()
    if supplied_id and supplied_id != registered.adapter_id:
        raise FinalConsolidationError(
            "JP8_ADAPTER_ID differs from registered Prompt-8 adapter"
        )
    if supplied_sha and supplied_sha != registered.contract_sha256:
        raise FinalConsolidationError(
            "JP8_ADAPTER_CONTRACT_SHA256 differs from registered Prompt-8 adapter"
        )
    return registered.adapter_id, registered.contract_sha256


def _validate_runtime_material_layout(
    adapter_registry_path: Path | str, paths: Layout
) -> None:
    try:
        configuration = load_adapter_configuration(
            ensure_c(
                adapter_registry_path,
                label="eight-day adapter registry",
                must_exist=True,
            )
        )
    except ProgramContractError as exc:
        raise FinalConsolidationError(
            f"invalid eight-day adapter registry: {exc}"
        ) from exc
    adapter = configuration.stages[8]
    _validate_runtime_input_layout(
        adapter.material_paths.get("inputs", ()),
        adapter_registry_path=adapter_registry_path,
    )
    expected = {
        "workspaces": {paths.root},
        "temporary": {paths.root / "temp"},
        "logs": {paths.root / "controller.log", paths.progress},
        "results": set(),
        "reports": {paths.output_root},
        "packages": {
            paths.zip_path,
            paths.completion,
            paths.artifact_manifest,
            paths.input_binding,
            paths.pre_state_snapshot,
            paths.gates,
        },
        "caches": set(),
        "checkpoints": set(),
    }
    if adapter.readiness != "READY" or any(
        set(adapter.material_paths.get(path_class, ())) != declared
        for path_class, declared in expected.items()
    ):
        raise FinalConsolidationError(
            "Prompt-8 runtime paths differ from the exact adapter material layout"
        )
    if (
        adapter.stage_workspace != paths.root
        or adapter.completion_record != paths.completion
        or adapter.progress_record != paths.progress
        or adapter.controller_log != paths.root / "controller.log"
    ):
        raise FinalConsolidationError(
            "Prompt-8 runtime controller paths differ from the adapter"
        )


def _validate_runtime_input_layout(
    declared_paths, *, adapter_registry_path: Path | str
) -> None:
    raw_paths = tuple(declared_paths)
    declared = {
        ensure_c(path, label="Prompt-8 material input", must_exist=True)
        for path in raw_paths
    }
    fixed = {
        ensure_c(DEFAULT_AMENDMENT, label="scope amendment", must_exist=True),
        ensure_c(
            DEFAULT_EXECUTION_POLICY_ADDENDUM,
            label="execution policy addendum",
            must_exist=True,
        ),
        ensure_c(
            adapter_registry_path, label="eight-day adapter registry", must_exist=True
        ),
        ensure_c(DEFAULT_PROGRAM_STATE, label="PROGRAM_STATE", must_exist=True),
        ensure_c(DEFAULT_MATRIX, label="pipeline matrix", must_exist=True),
        ensure_c(DEFAULT_RUNTIME, label="pipeline runtime", must_exist=True),
        ensure_c(
            DEFAULT_LICENSE_DOCUMENT,
            label="license and asset manifest",
            must_exist=True,
        ),
        ensure_c(
            DEFAULT_PI_DEPLOYMENT_STEERING,
            label="Raspberry Pi deployment steering",
            must_exist=True,
        ),
    }
    chain_paths = declared - fixed
    if (
        len(raw_paths) != len(declared)
        or not fixed.issubset(declared)
        or len(declared) != len(fixed) + 4
    ):
        raise FinalConsolidationError(
            "Prompt-8 adapter inputs must be the exact authorities plus four "
            "P4-P7 completion records"
        )
    observed: dict[int, Path] = {}
    for path in chain_paths:
        if not path.is_file() or path.name != "completion_marker.json":
            raise FinalConsolidationError(
                "Prompt-8 adapter input is not an exact completion record"
            )
        value = read_json(path)
        prompt = int(value.get("prompt_index") or -1)
        if (
            prompt not in {4, 5, 6, 7}
            or prompt in observed
            or value.get("schema_version")
            != "full-pipeline-eight-day-stage-completion.v1"
            or value.get("completion_marker") != COMPLETION_MARKERS[prompt]
            or value.get("scope_id") != SCOPE_ID
            or value.get("scope_class") != "BOUNDED_REDUCED"
            or value.get("original_full_scope_complete") is not False
        ):
            raise FinalConsolidationError(
                "Prompt-8 adapter completion-input identity differs"
            )
        observed[prompt] = path
    if set(observed) != {4, 5, 6, 7}:
        raise FinalConsolidationError(
            "Prompt-8 adapter inputs do not cover exact P4-P7 completions"
        )


def _progress(
    paths: Layout,
    percentage: float,
    phase: str,
    detail: str,
    eta_seconds: int | None,
    *,
    status: str = "RUNNING",
) -> None:
    write_json_atomic(
        paths.progress,
        {
            "schema_version": "full-pipeline-final-consolidation-progress.v1",
            **scope_fields(),
            "status": status,
            "overall_percentage": percentage,
            "eta_seconds": eta_seconds,
            "phase": phase,
            "detail": detail,
            "updated_at_utc": _utc_now(),
            "completion_record": str(paths.completion),
            "compact_zip_path": str(paths.zip_path),
        },
    )


def _check_stop(paths: Layout) -> None:
    if paths.stop_request.is_file():
        raise StopRequested("graceful stop requested; no completion marker was emitted")


def _acknowledge_stop(paths: Layout, *, disposition: str) -> None:
    if not paths.stop_request.is_file():
        return
    request = read_json(paths.stop_request)
    write_json_atomic(
        paths.stop_acknowledged,
        {
            **request,
            "acknowledged_at_utc": _utc_now(),
            "disposition": disposition,
            "completion_marker_emitted": paths.completion.is_file(),
        },
    )
    paths.stop_request.unlink()


def _supersede_failure(paths: Layout) -> None:
    if not paths.failure.is_file():
        return
    failure = read_json(paths.failure)
    write_json_atomic(
        paths.superseded_failure,
        {
            **failure,
            "status": "SUPERSEDED_BY_VALIDATED_COMPLETION",
            "superseded_at_utc": _utc_now(),
            "completion_record": str(paths.completion),
            "completion_record_sha256": sha256_file(paths.completion),
        },
    )
    paths.failure.unlink()


def _unique_paths(paths) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = ensure_c(raw, label="Prompt-8 artifact", must_exist=True)
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StopRequested(RuntimeError):
    """A durable graceful stop was observed between Prompt-8 phases."""


__all__ = [
    "Layout",
    "layout",
    "request_stop",
    "run_all",
    "status",
    "validate_final_completion",
]
