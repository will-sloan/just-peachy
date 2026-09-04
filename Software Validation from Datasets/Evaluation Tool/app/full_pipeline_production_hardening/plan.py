"""Immutable bounded acceptance plan for each selected production candidate."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from . import scope_fields
from .io import HardeningError


FAULTS = (
    "no_enrolled_speakers",
    "invalid_profile_binding",
    "operator_stop_during_inference",
    "worker_process_failure_and_restart",
    "slow_consumer_queue_pressure",
    "unsupported_input_format",
)


def build_acceptance_plan(
    *,
    workspace_root: Path,
    selection: Mapping[str, object],
    hardening_inputs: Mapping[str, object],
) -> dict[str, object]:
    roles = selection.get("roles")
    if not isinstance(roles, Mapping):
        raise HardeningError("selection roles are missing")
    candidates = [
        (str(role), str(pipeline))
        for role, pipeline in roles.items()
        if pipeline is not None
    ]
    if not 1 <= len(candidates) <= 3:
        raise HardeningError("selection must contain one to three roles")
    raw_candidates = selection.get("candidates")
    if not isinstance(raw_candidates, list):
        raise HardeningError("selection candidate attestations are missing")
    candidate_rows = {
        str(row.get("pipeline_id")): row
        for row in raw_candidates
        if isinstance(row, Mapping)
    }
    inputs = hardening_inputs.get("inputs")
    if not isinstance(inputs, list):
        raise HardeningError("hardening input rows are missing")
    by_role: dict[str, list[Mapping[str, object]]] = {}
    for raw in inputs:
        if not isinstance(raw, Mapping):
            continue
        for input_role in raw.get("roles", []):
            by_role.setdefault(str(input_role), []).append(raw)
    tasks: list[dict[str, object]] = []
    for role, pipeline in candidates:
        candidate = candidate_rows.get(pipeline)
        binding = (
            candidate.get("runtime_binding") if isinstance(candidate, Mapping) else None
        )
        if (
            not isinstance(binding, Mapping)
            or candidate.get("production_role_eligible") is not True
            or binding.get("binding_status") != "BOUND_FROZEN_ANCHOR"
            or binding.get("frozen_anchor") is not True
            or binding.get("unknown_only_fallback_allowed") is not False
        ):
            raise HardeningError(
                f"selected role lacks an exact runnable frozen-anchor binding: {pipeline}"
            )
        first_task_index = len(tasks)
        prefix = f"{role.casefold()}_{pipeline}"
        replay = _input(by_role, "deterministic_replay", 300)
        repeated = _input(by_role, "repeated_session", 120)
        loopback = _input(by_role, "controlled_loopback", 600)
        soak = _input(by_role, "soak", 3600)
        enrollment = sorted(
            by_role.get("enrollment_sample", []),
            key=lambda row: str(row.get("input_id")),
        )[:3]
        if len(enrollment) != 3:
            raise HardeningError("three enrollment samples are required")
        for index in (1, 2):
            tasks.append(
                _session_task(
                    task_id=f"{prefix}_deterministic_replay_{index}",
                    pipeline_id=pipeline,
                    role=role,
                    kind="deterministic_replay",
                    source=replay,
                    duration_sec=300,
                    pace=0.0,
                    source_mode="file_simulation_unpaced",
                )
            )
        tasks.append(
            _session_task(
                task_id=f"{prefix}_controlled_loopback",
                pipeline_id=pipeline,
                role=role,
                kind="controlled_loopback",
                source=loopback,
                duration_sec=600,
                pace=1.0,
                source_mode="controlled_virtual_loopback",
                extra={
                    "physical_microphone_claimed": False,
                    "os_loopback_device_claimed": False,
                    "live_api_required": "DemoSessionManager.start_microphone",
                    "capture_method": loopback.get("capture_method"),
                    "loopback_input_device": loopback.get("loopback_input_device"),
                    "playback_output_device": loopback.get("playback_output_device"),
                },
            )
        )
        tasks.append(
            {
                "task_id": f"{prefix}_enrollment_profile",
                "pipeline_id": pipeline,
                "candidate_role": role,
                "kind": "enrollment_profile",
                "source_mode": "labelled_wav_import",
                "enrollment_inputs": [dict(row) for row in enrollment],
                "expected_outcome": "profile_created_and_backend_bound",
            }
        )
        for index in range(1, 6):
            tasks.append(
                _session_task(
                    task_id=f"{prefix}_repeat_{index}",
                    pipeline_id=pipeline,
                    role=role,
                    kind="repeated_session",
                    source=repeated,
                    duration_sec=120,
                    pace=0.0,
                    source_mode="file_simulation_unpaced",
                )
            )
        tasks.append(
            _session_task(
                task_id=f"{prefix}_soak_60min",
                pipeline_id=pipeline,
                role=role,
                kind="soak",
                source=soak,
                duration_sec=3600,
                pace=1.0,
                source_mode="file_simulation_realtime_1x",
            )
        )
        for fault in FAULTS:
            task = {
                "task_id": f"{prefix}_fault_{fault}",
                "pipeline_id": pipeline,
                "candidate_role": role,
                "kind": "recovery_fault",
                "source_mode": "controlled_fault_injection",
                "fault_id": fault,
                "input": dict(repeated),
                "duration_sec": 30.0
                if fault != "operator_stop_during_inference"
                else 120.0,
                "expected_outcome": "fault_detected_and_recovery_contract_passed",
            }
            tasks.append(task)
        tasks.append(
            {
                "task_id": f"{prefix}_startup_self_test",
                "pipeline_id": pipeline,
                "candidate_role": role,
                "kind": "startup_self_test",
                "source_mode": "file_simulation_unpaced_preflight",
                "input": dict(repeated),
                "duration_sec": 10.0,
                "expected_outcome": "all_assets_and_workers_healthy",
            }
        )
        binding_attestation = {
            key: binding.get(key)
            for key in (
                "binding_status",
                "frozen_anchor",
                "frozen_config_path",
                "frozen_config_sha256",
                "freeze_identity_sha256",
                "pipeline_config_sha256",
                "runtime_config_sha256",
                "decision_policy_sha256",
                "model_assets",
                "runtime_component_identities",
                "external_assets",
                "environment_interpreters",
                "unknown_only_fallback_allowed",
            )
        }
        for task in tasks[first_task_index:]:
            task["runtime_binding"] = binding_attestation
            task["offline_no_download_required"] = True
    return {
        "schema_version": "full-pipeline-production-hardening-plan.v1",
        **scope_fields(),
        "status": "PREPARED_NOT_RUN",
        "workspace_root": str(workspace_root.resolve()),
        "candidate_count": len(candidates),
        "candidate_roles": {role: pipeline for role, pipeline in candidates},
        "task_count": len(tasks),
        "tasks": tasks,
        "acceptance_per_candidate": {
            "deterministic_replay_5min_count": 2,
            "controlled_loopback_10min_count": 1,
            "enrollment_profile_count": 1,
            "repeated_session_2min_count": 5,
            "soak_60min_count": 1,
            "recovery_fault_count": 6,
            "startup_self_test_count": 1,
        },
        "deterministic_replay_comparison_required": True,
        "session_export_required": True,
        "profile_backend_checkpoint_invalidation_required": True,
        "threshold_changes_allowed": False,
        "xvf_hooks_enabled": False,
        "fine_tuning_hooks_enabled": False,
        "parallel_candidate_runs": 1,
    }


def _session_task(
    *,
    task_id: str,
    pipeline_id: str,
    role: str,
    kind: str,
    source: Mapping[str, object],
    duration_sec: float,
    pace: float,
    source_mode: str,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "pipeline_id": pipeline_id,
        "candidate_role": role,
        "kind": kind,
        "input": dict(source),
        "duration_sec": float(duration_sec),
        "pace": float(pace),
        "source_mode": source_mode,
        "expected_outcome": "complete_exported_session",
        **dict(extra or {}),
    }


def _input(
    by_role: Mapping[str, Sequence[Mapping[str, object]]],
    role: str,
    minimum_duration: float,
) -> Mapping[str, object]:
    candidates = [
        row
        for row in by_role.get(role, ())
        if float(row.get("duration_sec") or 0.0) >= minimum_duration
    ]
    if not candidates:
        raise HardeningError(f"no hardening input satisfies {role}")
    return min(candidates, key=lambda row: str(row.get("input_id")))


__all__ = ["FAULTS", "build_acceptance_plan"]
