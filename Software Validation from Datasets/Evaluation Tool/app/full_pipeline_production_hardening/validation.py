"""Acceptance evidence validation and software-readiness classification."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline_evaluation.io import read_json, sha256_file, write_json_atomic

from . import scope_fields
from .io import HardeningError, ensure_c, write_csv
from .plan import FAULTS


def validate_acceptance(
    *, workspace_root: Path, plan: Mapping[str, object]
) -> dict[str, object]:
    root = ensure_c(workspace_root, label="Prompt-7 workspace")
    raw_tasks = plan.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise HardeningError("acceptance plan tasks are absent")
    task_results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    by_pipeline: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw in raw_tasks:
        if not isinstance(raw, Mapping):
            raise HardeningError("acceptance plan task is invalid")
        task_id = str(raw["task_id"])
        latest_path = root / "evidence" / task_id / "latest.json"
        if not latest_path.is_file():
            result = {
                "task_id": task_id,
                "pipeline_id": raw["pipeline_id"],
                "candidate_role": raw["candidate_role"],
                "kind": raw["kind"],
                "status": "MISSING",
                "reason": "task_not_run",
            }
        else:
            latest = read_json(latest_path)
            result_path = ensure_c(
                str(latest.get("result_path") or ""),
                label=f"{task_id} result",
                must_exist=True,
            )
            if latest.get("result_sha256") != sha256_file(result_path):
                raise HardeningError(f"acceptance result binding differs: {task_id}")
            result = read_json(result_path)
            _validate_result_against_task(result, raw)
            _validate_result_artifacts(result)
            result["result_path"] = str(result_path)
            result["result_sha256"] = sha256_file(result_path)
        task_results.append(result)
        pipeline = str(result["pipeline_id"])
        by_pipeline[pipeline].append(result)
        if result.get("status") != "PASS":
            failures.append(
                {
                    **scope_fields(),
                    "pipeline_id": pipeline,
                    "candidate_role": result.get("candidate_role"),
                    "task_id": task_id,
                    "kind": result.get("kind"),
                    "fault_id": result.get("fault_id"),
                    "status": result.get("status"),
                    "reason": result.get("reason") or result.get("command_payload"),
                    "result_path": result.get("result_path"),
                }
            )

    deterministic: list[dict[str, object]] = []
    no_enrollment: list[dict[str, object]] = []
    invalidation: list[dict[str, object]] = []
    enrollment_profiles: list[dict[str, object]] = []
    live_source: list[dict[str, object]] = []
    session_contracts: list[dict[str, object]] = []
    runtime_bindings: list[dict[str, object]] = []
    recovery_faults: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for pipeline, results in sorted(by_pipeline.items()):
        role = str(results[0].get("candidate_role") or "")
        replay = sorted(
            (row for row in results if row.get("kind") == "deterministic_replay"),
            key=lambda row: str(row["task_id"]),
        )
        deterministic_result = _validate_deterministic_pair(pipeline, replay)
        deterministic.append(deterministic_result)
        no_enrollment_result = _validate_no_enrollment(pipeline, results)
        no_enrollment.append(no_enrollment_result)
        invalidation_result = _validate_profile_invalidation(pipeline, results)
        invalidation.append(invalidation_result)
        enrollment_result = _validate_enrollment_profile(pipeline, results)
        enrollment_profiles.append(enrollment_result)
        live_source_result = _validate_live_source(pipeline, results)
        live_source.append(live_source_result)
        session_result = _validate_session_contracts(pipeline, results)
        session_contracts.append(session_result)
        binding_result = _validate_runtime_binding(pipeline, results)
        runtime_bindings.append(binding_result)
        recovery_result = _validate_recovery_faults(pipeline, results)
        recovery_faults.append(recovery_result)
        task_pass = all(row.get("status") == "PASS" for row in results)
        software_ready = (
            task_pass
            and deterministic_result["status"] == "PASS"
            and no_enrollment_result["status"] == "PASS"
            and invalidation_result["status"] == "PASS"
            and enrollment_result["status"] == "PASS"
            and live_source_result["status"] == "PASS"
            and session_result["status"] == "PASS"
            and binding_result["status"] == "PASS"
            and recovery_result["status"] == "PASS"
        )
        candidates.append(
            {
                **scope_fields(),
                "pipeline_id": pipeline,
                "role": role,
                "software_ready": software_ready,
                "planned_task_count": len(results),
                "passed_task_count": sum(
                    row.get("status") == "PASS" for row in results
                ),
                "failed_or_missing_task_count": sum(
                    row.get("status") != "PASS" for row in results
                ),
                "deterministic_replay": deterministic_result["status"],
                "no_enrollment_safety": no_enrollment_result["status"],
                "profile_invalidation": invalidation_result["status"],
                "enrollment_profile": enrollment_result["status"],
                "controlled_live_source": live_source_result["status"],
                "session_export_and_shutdown": session_result["status"],
                "frozen_runtime_binding": binding_result["status"],
                "recovery_faults": recovery_result["status"],
                "thresholds_changed": False,
                "xvf_hooks_enabled": False,
                "fine_tuning_hooks_enabled": False,
            }
        )
    write_csv(root / "report/acceptance_summary.csv", candidates)
    write_csv(
        root / "report/failure_inventory.csv",
        failures,
        fieldnames=(
            "scope_id",
            "scope_class",
            "original_full_scope_complete",
            "pipeline_id",
            "candidate_role",
            "task_id",
            "kind",
            "fault_id",
            "status",
            "reason",
            "result_path",
        ),
    )
    evidence_index = {
        "schema_version": "full-pipeline-production-hardening-evidence-index.v1",
        **scope_fields(),
        "status": "PASS"
        if all(row["software_ready"] for row in candidates)
        else "FAIL",
        "task_results": task_results,
        "deterministic_replay_comparisons": deterministic,
        "no_enrollment_checks": no_enrollment,
        "profile_invalidation_checks": invalidation,
        "enrollment_profile_checks": enrollment_profiles,
        "controlled_live_source_checks": live_source,
        "session_contract_checks": session_contracts,
        "runtime_binding_checks": runtime_bindings,
        "recovery_fault_checks": recovery_faults,
        "candidates": candidates,
        "failure_count": len(failures),
        "biometric_vectors_in_compact_package": False,
    }
    write_json_atomic(root / "report/evidence_index.json", evidence_index)
    if not all(row["software_ready"] for row in candidates):
        raise HardeningError(
            "BLOCKED_PRODUCTION_CANDIDATE: one or more selected candidates failed acceptance"
        )
    return evidence_index


def _validate_result_artifacts(result: Mapping[str, object]) -> None:
    raw = result.get("artifacts")
    if not isinstance(raw, list):
        raise HardeningError(
            f"task result lacks artifact inventory: {result.get('task_id')}"
        )
    for artifact in raw:
        if not isinstance(artifact, Mapping):
            raise HardeningError("task artifact inventory row is invalid")
        path = ensure_c(
            str(artifact.get("path") or ""), label="task artifact", must_exist=True
        )
        if artifact.get("sha256") != sha256_file(path):
            raise HardeningError(f"task artifact checksum differs: {path}")


def _validate_result_against_task(
    result: Mapping[str, object], task: Mapping[str, object]
) -> None:
    for key in ("task_id", "pipeline_id", "candidate_role", "kind", "source_mode"):
        if result.get(key) != task.get(key):
            raise HardeningError(
                f"acceptance result {key} differs: {task.get('task_id')}"
            )
    binding = task.get("runtime_binding")
    if (
        not isinstance(binding, Mapping)
        or binding.get("binding_status") != "BOUND_FROZEN_ANCHOR"
        or binding.get("frozen_anchor") is not True
        or binding.get("unknown_only_fallback_allowed") is not False
    ):
        raise HardeningError(
            f"acceptance task has an unsafe runtime binding: {task.get('task_id')}"
        )
    if result.get("status") == "PASS":
        environment = result.get("offline_environment")
        if not isinstance(environment, Mapping) or any(
            environment.get(key) != "1"
            for key in (
                "HF_HUB_OFFLINE",
                "HF_DATASETS_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "JP_OFFLINE_NO_DOWNLOAD",
            )
        ):
            raise HardeningError(
                f"acceptance task lacks offline enforcement: {task.get('task_id')}"
            )
        if (
            result.get("implicit_downloads_allowed") is not False
            or result.get("graceful_shutdown_observed") is not True
            or int(result.get("orphan_process_count_before_cleanup") or 0) != 0
            or int(result.get("orphan_process_count_after_cleanup") or 0) != 0
        ):
            raise HardeningError(
                f"acceptance task shutdown/download contract failed: {task.get('task_id')}"
            )


def _validate_deterministic_pair(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    if len(results) != 2 or any(row.get("status") != "PASS" for row in results):
        return {
            "pipeline_id": pipeline,
            "status": "FAIL",
            "reason": "two_passed_replays_required",
        }
    transcript_hashes = [
        _artifact_normalized_hash(row, "transcript/labelled_transcript.jsonl")
        for row in results
    ]
    event_hashes = [
        _artifact_normalized_hash(row, "events/events.jsonl") for row in results
    ]
    passed = len(set(transcript_hashes)) == 1 and len(set(event_hashes)) == 1
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if passed else "FAIL",
        "transcript_normalized_sha256s": transcript_hashes,
        "event_normalized_sha256s": event_hashes,
        "comparison": "volatile_identifiers_and_wall_clock_fields_removed",
    }


def _artifact_normalized_hash(result: Mapping[str, object], suffix: str) -> str:
    artifacts = result.get("artifacts")
    assert isinstance(artifacts, list)
    matches = [
        Path(str(row["path"]))
        for row in artifacts
        if isinstance(row, Mapping)
        and "/export/" in str(row.get("path") or "").replace("\\", "/")
        and str(row.get("path") or "").replace("\\", "/").endswith(suffix)
    ]
    if len(matches) != 1:
        raise HardeningError(f"deterministic replay requires one {suffix}")
    digest = hashlib.sha256()
    with matches[0].open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            value = json.loads(line)
            normalized = _drop_volatile(value)
            digest.update(
                json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
                + b"\n"
            )
    return digest.hexdigest()


def _drop_volatile(value: object) -> object:
    volatile = {
        "event_id",
        "session_id",
        "run_id",
        "created_at_utc",
        "updated_at_utc",
        "wall_time_utc",
        "processing_time_sec",
        "compute_latency_sec",
        "ui_latency_sec",
        "source_event_ids",
        "causal_event_ids",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _drop_volatile(item)
            for key, item in value.items()
            if str(key) not in volatile
        }
    if isinstance(value, list):
        return [_drop_volatile(item) for item in value]
    return value


def _validate_no_enrollment(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    matches = [row for row in results if row.get("fault_id") == "no_enrolled_speakers"]
    if len(matches) != 1 or matches[0].get("status") != "PASS":
        return {
            "pipeline_id": pipeline,
            "status": "FAIL",
            "reason": "fault_task_missing",
        }
    artifacts = matches[0].get("artifacts")
    assert isinstance(artifacts, list)
    paths = [
        Path(str(row["path"]))
        for row in artifacts
        if isinstance(row, Mapping)
        and "/export/" in str(row.get("path") or "").replace("\\", "/")
        and str(row.get("path") or "")
        .replace("\\", "/")
        .endswith("events/events.jsonl")
    ]
    if len(paths) != 1:
        return {
            "pipeline_id": pipeline,
            "status": "FAIL",
            "reason": "event_log_missing",
        }
    known_releases = 0
    with paths[0].open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            event = json.loads(line)
            if str(event.get("contract_type") or "") != "IdentityLabelEvent":
                continue
            state = str(
                event.get("identity_state")
                or event.get("decision_state")
                or event.get("state")
                or ""
            ).casefold()
            known_releases += int(state in {"tentative_known", "confirmed_known"})
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if known_releases == 0 else "FAIL",
        "known_name_release_count_without_profiles": known_releases,
    }


def _validate_profile_invalidation(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    matches = [
        row for row in results if row.get("fault_id") == "invalid_profile_binding"
    ]
    if len(matches) != 1:
        return {
            "pipeline_id": pipeline,
            "status": "FAIL",
            "reason": "fault_task_missing",
        }
    row = matches[0]
    payload = json.dumps(row.get("command_payload") or {}, sort_keys=True).casefold()
    observed = row.get("status") == "PASS" and any(
        text in payload
        for text in ("backend config mismatch", "model identity mismatch")
    )
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if observed else "FAIL",
        "mismatched_backend_or_checkpoint_rejected": observed,
    }


def _validate_enrollment_profile(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    matches = [row for row in results if row.get("kind") == "enrollment_profile"]
    if len(matches) != 1:
        return {
            "pipeline_id": pipeline,
            "status": "FAIL",
            "reason": "one_enrollment_profile_task_required",
        }
    row = matches[0]
    payload = row.get("command_payload")
    binding = row.get("runtime_binding")
    expected_embedding = (
        dict(binding.get("model_assets") or {}).get("identity_embedding")
        if isinstance(binding, Mapping)
        else None
    )
    backend = payload.get("backend") if isinstance(payload, Mapping) else None
    passed = (
        row.get("status") == "PASS"
        and isinstance(payload, Mapping)
        and payload.get("state") == "profile_created"
        and payload.get("pipeline_id") == pipeline
        and bool(payload.get("profile_id"))
        and bool(payload.get("profile_sha256"))
        and payload.get("biometric_vectors_inline") is False
        and payload.get("network_transfer_performed") is False
        and isinstance(backend, Mapping)
        and isinstance(expected_embedding, Mapping)
        and backend.get("backend_id") == expected_embedding.get("backend_id")
        and backend.get("backend_config_sha256")
        == expected_embedding.get("config_sha256")
        and backend.get("model_id") == expected_embedding.get("model_id")
        and backend.get("model_sha256")
        == expected_embedding.get("model_identity_sha256")
    )
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if passed else "FAIL",
        "profile_created": (
            payload.get("state") == "profile_created"
            if isinstance(payload, Mapping)
            else False
        ),
        "backend_checkpoint_binding_validated": passed,
        "network_transfer_performed": False,
        "biometric_vectors_inline": False,
    }


def _validate_live_source(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    matches = [row for row in results if row.get("kind") == "controlled_loopback"]
    if len(matches) != 1:
        return {
            "pipeline_id": pipeline,
            "status": "FAIL",
            "reason": "one_controlled_virtual_loopback_required",
        }
    row = matches[0]
    payload = row.get("command_payload")
    passed = (
        row.get("status") == "PASS"
        and row.get("source_mode") == "controlled_virtual_loopback"
        and isinstance(payload, Mapping)
        and payload.get("source_mode") == "controlled_virtual_loopback"
        and payload.get("common_live_api_exercised")
        == "DemoSessionManager.start_microphone"
        and payload.get("runtime_transport")
        == "deterministic_wav_virtual_microphone_source"
        and payload.get("live_queue_policy") == "drop_oldest"
        and payload.get("physical_microphone_claimed") is False
        and payload.get("os_loopback_device_claimed") is False
        and payload.get("file_simulation_claimed") is False
        and payload.get("graceful_shutdown_observed") is True
    )
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if passed else "FAIL",
        "source_mode": row.get("source_mode"),
        "common_live_api_exercised": (
            payload.get("common_live_api_exercised")
            if isinstance(payload, Mapping)
            else None
        ),
        "physical_microphone_performance_claimed": False,
        "os_loopback_device_claimed": False,
        "scientific_claim": (
            "reproducible virtual live-session lifecycle only; not physical microphone"
        ),
    }


def _validate_session_contracts(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    session_kinds = {
        "deterministic_replay",
        "controlled_loopback",
        "repeated_session",
        "soak",
        "startup_self_test",
    }
    session_rows = [row for row in results if row.get("kind") in session_kinds]
    expected_count = 2 + 1 + 5 + 1 + 1
    failures: list[str] = []
    validated_exports = 0
    for row in session_rows:
        if row.get("status") != "PASS":
            failures.append(f"{row.get('task_id')}:not_passed")
            continue
        try:
            _validate_export(row, pipeline=pipeline)
        except HardeningError as exc:
            failures.append(f"{row.get('task_id')}:{exc}")
        else:
            validated_exports += 1
    if len(session_rows) != expected_count:
        failures.append(
            f"session_task_count:{len(session_rows)}_expected_{expected_count}"
        )
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if not failures else "FAIL",
        "expected_session_export_count": expected_count,
        "validated_session_export_count": validated_exports,
        "all_processes_joined_without_orphans": all(
            row.get("graceful_shutdown_observed") is True
            and int(row.get("orphan_process_count_before_cleanup") or 0) == 0
            for row in session_rows
        ),
        "failures": failures,
    }


def _validate_export(result: Mapping[str, object], *, pipeline: str) -> None:
    artifacts = result.get("artifacts")
    assert isinstance(artifacts, list)
    checksum_paths = [
        Path(str(row.get("path")))
        for row in artifacts
        if isinstance(row, Mapping)
        and str(row.get("path") or "")
        .replace("\\", "/")
        .endswith("/export/checksums.json")
    ]
    if len(checksum_paths) != 1:
        raise HardeningError("exactly one session export checksums.json is required")
    export_root = checksum_paths[0].parent
    checksums = read_json(checksum_paths[0])
    if checksums.get("schema_version") != "full-pipeline-demo-export-checksums.v1":
        raise HardeningError("session export checksum schema differs")
    raw_rows = checksums.get("artifacts")
    if not isinstance(raw_rows, list):
        raise HardeningError("session export checksum rows are absent")
    logical_paths: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise HardeningError("session export checksum row is invalid")
        logical = str(raw.get("logical_path") or "")
        path = (export_root / logical).resolve()
        try:
            path.relative_to(export_root.resolve())
        except ValueError as exc:
            raise HardeningError("session export artifact escapes its root") from exc
        if (
            not path.is_file()
            or raw.get("sha256") != sha256_file(path)
            or int(raw.get("byte_count") or -1) != path.stat().st_size
        ):
            raise HardeningError(f"session export artifact differs: {logical}")
        logical_paths.add(logical)
    required = {
        "transcript/labelled_transcript.jsonl",
        "events/events.jsonl",
        "telemetry/resource_samples.jsonl",
        "manifests/pipeline_identity.json",
        "manifests/component_identities.json",
        "identities/pipeline_models_profiles.json",
        "diagnostics/failures.json",
        "manifest.json",
    }
    if not required.issubset(logical_paths):
        raise HardeningError(
            "session export lacks required artifacts: "
            + ", ".join(sorted(required - logical_paths))
        )
    manifest = read_json(export_root / "manifest.json")
    if (
        manifest.get("pipeline_id") != pipeline
        or manifest.get("source_completion_state") != "completed"
        or manifest.get("local_export_only") is not True
        or manifest.get("contains_biometric_vectors") is not False
        or manifest.get("runtime_work_or_cache_copied") is not False
    ):
        raise HardeningError("session export manifest contract differs")
    failures = read_json(export_root / "diagnostics/failures.json")
    if failures.get("manager_failures") or failures.get("runtime_errors"):
        raise HardeningError("successful session export contains failures")


def _validate_runtime_binding(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    bindings = [row.get("runtime_binding") for row in results]
    valid_bindings = [row for row in bindings if isinstance(row, Mapping)]
    failures: list[str] = []
    if len(valid_bindings) != len(results):
        failures.append("task_runtime_binding_missing")
    elif any(
        row.get("binding_status") != "BOUND_FROZEN_ANCHOR"
        or row.get("frozen_anchor") is not True
        or row.get("unknown_only_fallback_allowed") is not False
        for row in valid_bindings
    ):
        failures.append("unsafe_or_unresolved_runtime_binding")
    elif (
        len(
            {
                json.dumps(dict(row), sort_keys=True, separators=(",", ":"))
                for row in valid_bindings
            }
        )
        != 1
    ):
        failures.append("runtime_binding_changed_between_tasks")
    session_results = [
        row
        for row in results
        if row.get("kind")
        in {
            "deterministic_replay",
            "controlled_loopback",
            "repeated_session",
            "soak",
            "startup_self_test",
        }
        and row.get("status") == "PASS"
    ]
    for result in session_results:
        binding = result.get("runtime_binding")
        assert isinstance(binding, Mapping)
        try:
            _validate_export_runtime_identity(
                result,
                pipeline=pipeline,
                binding=binding,
            )
        except HardeningError as exc:
            failures.append(f"{result.get('task_id')}:{exc}")
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if not failures else "FAIL",
        "frozen_anchor": True,
        "unknown_only_policy_executed": False,
        "validated_session_identity_count": len(session_results),
        "failures": failures,
    }


def _validate_export_runtime_identity(
    result: Mapping[str, object],
    *,
    pipeline: str,
    binding: Mapping[str, object],
) -> None:
    artifacts = result.get("artifacts")
    assert isinstance(artifacts, list)
    matches = [
        Path(str(row.get("path")))
        for row in artifacts
        if isinstance(row, Mapping)
        and str(row.get("path") or "")
        .replace("\\", "/")
        .endswith("/export/manifests/pipeline_identity.json")
    ]
    if len(matches) != 1:
        raise HardeningError("pipeline identity export is absent/duplicate")
    identity = read_json(matches[0])
    manager = identity.get("manager_pipeline_identity")
    if (
        identity.get("pipeline_id") != pipeline
        or identity.get("pipeline_config_sha256")
        != binding.get("pipeline_config_sha256")
        or not isinstance(manager, Mapping)
        or manager.get("pipeline_id") != pipeline
        or manager.get("pipeline_config_sha256")
        != binding.get("pipeline_config_sha256")
    ):
        raise HardeningError("runtime pipeline identity differs from frozen binding")
    component_path = matches[0].with_name("component_identities.json")
    components = read_json(component_path)
    observed_rows = components.get("component_identities")
    expected_raw = binding.get("runtime_component_identities")
    if not isinstance(observed_rows, list) or not isinstance(expected_raw, Mapping):
        raise HardeningError("runtime component identity inventory is absent")
    observed = {
        str(row.get("component_family")): dict(row)
        for row in observed_rows
        if isinstance(row, Mapping)
    }
    expected = {
        str(row.get("component_family")): dict(row)
        for row in expected_raw.values()
        if isinstance(row, Mapping)
    }
    if not expected or observed != expected:
        raise HardeningError("worker/runtime component identities differ from freeze")
    worker_rows = components.get("worker_reported_identities")
    if not isinstance(worker_rows, list) or not worker_rows:
        raise HardeningError("worker-reported runtime identities are absent")
    for row in worker_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("identity"), Mapping):
            raise HardeningError("worker-reported runtime identity is invalid")


def _validate_recovery_faults(
    pipeline: str, results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    matches = {
        str(row.get("fault_id")): row
        for row in results
        if row.get("kind") == "recovery_fault"
    }
    failures: list[str] = []
    if set(matches) != set(FAULTS):
        failures.append("six_exact_fault_ids_required")
    for fault in FAULTS:
        row = matches.get(fault)
        if row is None or row.get("status") != "PASS":
            failures.append(f"{fault}:not_passed")
            continue
        payload = row.get("command_payload")
        if fault == "worker_process_failure_and_restart" and (
            not isinstance(payload, Mapping)
            or payload.get("status") != "PASS"
            or payload.get("initial_worker_exit_observed") is not True
            or int(payload.get("restart_count") or 0) < 1
        ):
            failures.append(f"{fault}:restart_not_proved")
        elif fault == "slow_consumer_queue_pressure" and (
            not isinstance(payload, Mapping)
            or payload.get("status") != "PASS"
            or payload.get("bounded_queue") is not True
            or payload.get("durable_event_resync_requested") is not True
        ):
            failures.append(f"{fault}:bounded_resync_not_proved")
        elif fault == "operator_stop_during_inference" and (
            row.get("interrupted_as_planned") is not True
            or row.get("expected_nonzero") is not True
            or int(row.get("exit_code") or 0) == 0
        ):
            failures.append(f"{fault}:graceful_interrupt_not_proved")
        elif fault in {"unsupported_input_format", "invalid_profile_binding"} and (
            row.get("expected_nonzero") is not True
            or int(row.get("exit_code") or 0) == 0
        ):
            failures.append(f"{fault}:expected_rejection_not_observed")
    return {
        "pipeline_id": pipeline,
        "status": "PASS" if not failures else "FAIL",
        "expected_fault_ids": list(FAULTS),
        "observed_fault_ids": sorted(matches),
        "failures": failures,
    }


__all__ = ["validate_acceptance"]
