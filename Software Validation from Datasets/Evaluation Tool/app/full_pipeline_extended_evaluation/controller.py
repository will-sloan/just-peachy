"""Restart-safe bounded Prompt-6 controller and durable job scheduler."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import socket
import threading
from typing import Mapping
import uuid

from app.full_pipeline_evaluation.io import canonical_json_bytes, sha256_bytes
from app.full_pipeline_evaluation.protocol import load_cases
from app.full_pipeline_evaluation.store import EvaluationStateStore

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_ENROLLMENT_REGISTRY,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_ROOT,
    DEFAULT_SHARED_CACHE,
    MAXIMUM_ACCURACY_JOBS,
    NOMINAL_STAGE_TARGET_HOURS,
    PI_DEPLOYMENT_STEERING_SHA256,
    RESOURCE_CONCURRENCY,
    TOOL_ROOT,
    scope_fields,
)
from .execution import execute_custom, execute_scored, materialize_hardening_inputs
from .gate import (
    _validate_frozen_configs,
    validate_prompt5_predecessor,
    validate_saved_authorization,
)
from .io import (
    ExtendedEvaluationError,
    ensure_c_drive,
    read_json,
    read_jsonl,
    sha256_file,
    storage_preflight,
    write_json_atomic,
    write_json_once,
    write_jsonl_once,
)
from .progress import publish_program_progress
from .protocol import (
    build_bounded_plan,
    _execution_contract_binding,
    plan_specs,
    selection_exclusions,
    validate_plan,
)


@dataclass(frozen=True)
class Layout:
    root: Path
    authorization: Path
    input_binding: Path
    plan: Path
    selection_manifest: Path
    excluded_cases: Path
    database: Path
    attempts: Path
    results: Path
    logs: Path
    temp: Path
    report: Path
    program_progress: Path
    controller_state: Path
    controller_log: Path
    stop_record: Path
    completion: Path
    artifact_manifest: Path
    gates: Path
    hardening_manifest: Path
    deployment_evidence: Path


def layout(workspace_root: Path | str = DEFAULT_ROOT) -> Layout:
    root = ensure_c_drive(workspace_root, label="Prompt-6 workspace")
    return Layout(
        root=root,
        authorization=root / "prompt6_authorization.json",
        input_binding=root / "input_binding.json",
        plan=root / "bounded_plan.json",
        selection_manifest=root / "selection_manifest.json",
        excluded_cases=root / "excluded_cases.jsonl",
        database=root / "campaign.sqlite3",
        attempts=root / "attempts",
        results=root / "results",
        logs=root / "logs",
        temp=root / "temp",
        report=root / "report",
        program_progress=root / "program_progress.json",
        controller_state=root / "controller_state.json",
        controller_log=root / "logs/controller.log",
        stop_record=root / "stop_request.json",
        completion=root / "completion_marker.json",
        artifact_manifest=root / "artifact_manifest.json",
        gates=root / "gate_records",
        hardening_manifest=root / "hardening_input_manifest.json",
        deployment_evidence=root / "report/extended_deployment_evidence.json",
    )


def validate_prerequisite(
    *,
    predecessor_path: Path,
    predecessor_sha256: str | None = None,
    program_state_path: Path = DEFAULT_PROGRAM_STATE,
    amendment_path: Path = DEFAULT_AMENDMENT,
    deployment_steering_path: Path = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> dict[str, object]:
    return validate_prompt5_predecessor(
        predecessor_path,
        expected_sha256=predecessor_sha256,
        program_state_path=program_state_path,
        amendment_path=amendment_path,
        deployment_steering_path=deployment_steering_path,
        deployment_steering_sha256=deployment_steering_sha256,
    )


def prepare(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    predecessor_path: Path,
    predecessor_sha256: str | None = None,
    program_state_path: Path = DEFAULT_PROGRAM_STATE,
    amendment_path: Path = DEFAULT_AMENDMENT,
    deployment_steering_path: Path = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> dict[str, object]:
    paths = layout(workspace_root)
    if paths.completion.is_file():
        raise ExtendedEvaluationError(
            "Prompt 6 is already complete; use ValidateCompletion"
        )
    paths.root.mkdir(parents=True, exist_ok=True)
    for path in (paths.attempts, paths.results, paths.logs, paths.temp, paths.report):
        path.mkdir(parents=True, exist_ok=True)
    storage = storage_preflight(paths.root)
    authorization = validate_prerequisite(
        predecessor_path=predecessor_path,
        predecessor_sha256=predecessor_sha256,
        program_state_path=program_state_path,
        amendment_path=amendment_path,
        deployment_steering_path=deployment_steering_path,
        deployment_steering_sha256=deployment_steering_sha256,
    )
    write_json_once(paths.authorization, authorization)
    cases = load_cases(DEFAULT_PROTOCOL_ROOT, split="evaluation")
    protocol_summary = read_json(DEFAULT_PROTOCOL_ROOT / "protocol_summary.json")
    enrollment_rows = read_jsonl(DEFAULT_ENROLLMENT_REGISTRY)
    extended = authorization["extended_set"]
    if not isinstance(extended, Mapping):
        raise ExtendedEvaluationError("authorization extended set is invalid")
    registry = authorization["decision_policy_registry"]
    if not isinstance(registry, Mapping):
        raise ExtendedEvaluationError("authorization decision registry is invalid")
    plan = build_bounded_plan(
        cases,
        protocol_summary=protocol_summary,
        extended_pipeline_ids=tuple(
            str(item)
            for item in extended["extended_pipeline_ids"]  # type: ignore[index]
        ),
        workspace_root=paths.root,
        decision_policy_registry_sha256=str(registry["sha256"]),
        enrollment_rows=enrollment_rows,
        frozen_execution_contract=(
            authorization["frozen_pipeline_configs"]
            if isinstance(authorization.get("frozen_pipeline_configs"), Mapping)
            else {}
        ),
        deployment_context={
            "raspberry_pi_deployment_steering": authorization[
                "raspberry_pi_deployment_steering"
            ],
            "prompt5_deployment_evidence": authorization["prompt5_deployment_evidence"],
            "prompt4_extended_set": authorization["extended_set"],
            "predeclared_membership_unchanged_after_heldout": True,
            "deployment_evidence_used_as_filter": False,
        },
    )
    write_json_once(paths.plan, plan)
    write_json_once(
        paths.selection_manifest,
        {
            "schema_version": "full-pipeline-extended-selection-manifest.v1",
            **scope_fields(),
            "selection_seed": plan["selection_seed"],
            "selection_inputs": ["metadata", "references"],
            "outcome_dependent_selection": False,
            "prompt5_scientific_outcome_tables_opened_for_selection": False,
            "prompt5_deployment_evidence_opened_for_reporting": True,
            "deployment_evidence_used_as_filter": False,
            "pipeline_membership_changed_after_heldout": False,
            "inventory": plan["selection_inventory"],
            "plan_identity_sha256": plan["plan_identity_sha256"],
        },
    )
    write_jsonl_once(paths.excluded_cases, selection_exclusions(cases, plan))
    hardening = materialize_hardening_inputs(plan, workspace_root=paths.root)
    material_paths = _material_inventory(paths, authorization, predecessor_path)
    binding_core = {
        "schema_version": "full-pipeline-extended-input-binding.v1",
        **scope_fields(),
        "predecessor_completion_input": {
            "path": str(Path(predecessor_path).resolve()),
            "sha256": sha256_file(Path(predecessor_path).resolve()),
        },
        "prompt6_authorization_path": str(paths.authorization),
        "prompt6_authorization_sha256": sha256_file(paths.authorization),
        "bounded_plan_path": str(paths.plan),
        "bounded_plan_sha256": sha256_file(paths.plan),
        "hardening_input_manifest_path": str(paths.hardening_manifest),
        "hardening_input_manifest_sha256": sha256_file(paths.hardening_manifest),
        "material_paths": material_paths,
        "all_paths_c_only": True,
        "raspberry_pi_deployment_steering": authorization[
            "raspberry_pi_deployment_steering"
        ],
        "prompt5_deployment_evidence": authorization["prompt5_deployment_evidence"],
        "prompt5_scientific_outcome_tables_opened_for_selection": False,
        "prompt5_deployment_evidence_opened_for_reporting": True,
        "outcome_dependent_selection": False,
        "deployment_evidence_used_as_filter": False,
        "pipeline_membership_changed_after_heldout": False,
    }
    binding = {
        **binding_core,
        "binding_identity_sha256": sha256_bytes(canonical_json_bytes(binding_core)),
    }
    write_json_once(paths.input_binding, binding)
    specs = plan_specs(plan)
    store = EvaluationStateStore(paths.database)
    store.prepare(
        specs,
        campaign_id=f"prompt6_reduced_{str(plan['plan_identity_sha256'])[:12]}",
        manifest_sha256=sha256_file(paths.plan),
    )
    _write_controller_state(
        paths,
        status="PREPARED",
        action="Prepare",
        detail="Bounded panel and hardening inputs frozen; inference not started",
        stage_started_at_utc=None,
    )
    progress = publish_program_progress(paths)
    return {
        "schema_version": "full-pipeline-extended-preparation.v1",
        **scope_fields(),
        "status": "PASS",
        "workspace_root": str(paths.root),
        "pipeline_count": plan["pipeline_count"],
        "job_count": len(specs),
        "storage": storage,
        "hardening_input_count": len(hardening["inputs"]),
        "progress": progress,
        "inference_started": False,
    }


def run_accuracy(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    predecessor_path: Path,
    predecessor_sha256: str | None = None,
    program_state_path: Path = DEFAULT_PROGRAM_STATE,
    amendment_path: Path = DEFAULT_AMENDMENT,
    deployment_steering_path: Path = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
    parallel_jobs: int = MAXIMUM_ACCURACY_JOBS,
) -> dict[str, object]:
    if not 1 <= parallel_jobs <= MAXIMUM_ACCURACY_JOBS:
        raise ExtendedEvaluationError("accuracy parallelism must be 1 or 2")
    paths, plan, authorization = _require_prepared(
        workspace_root,
        predecessor_path=predecessor_path,
        predecessor_sha256=predecessor_sha256,
        program_state_path=program_state_path,
        amendment_path=amendment_path,
        deployment_steering_path=deployment_steering_path,
        deployment_steering_sha256=deployment_steering_sha256,
    )
    return _run_jobs(
        paths,
        plan,
        authorization,
        measurement_mode="accuracy",
        parallel_jobs=parallel_jobs,
    )


def run_resources(
    *,
    workspace_root: Path = DEFAULT_ROOT,
    predecessor_path: Path,
    predecessor_sha256: str | None = None,
    program_state_path: Path = DEFAULT_PROGRAM_STATE,
    amendment_path: Path = DEFAULT_AMENDMENT,
    deployment_steering_path: Path = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> dict[str, object]:
    paths, plan, authorization = _require_prepared(
        workspace_root,
        predecessor_path=predecessor_path,
        predecessor_sha256=predecessor_sha256,
        program_state_path=program_state_path,
        amendment_path=amendment_path,
        deployment_steering_path=deployment_steering_path,
        deployment_steering_sha256=deployment_steering_sha256,
    )
    return _run_jobs(
        paths,
        plan,
        authorization,
        measurement_mode="resources",
        parallel_jobs=RESOURCE_CONCURRENCY,
    )


def status(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    progress = publish_program_progress(paths)
    storage = storage_preflight(paths.root, fail=False)
    return {
        "schema_version": "full-pipeline-extended-status.v1",
        **scope_fields(),
        "status": "PASS",
        "workspace_root": str(paths.root),
        "completion_marker": (
            read_json(paths.completion).get("completion_marker")
            if paths.completion.is_file()
            else None
        ),
        "progress": progress,
        "storage": storage,
    }


def stop(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    if not paths.database.is_file():
        return {
            "schema_version": "full-pipeline-extended-stop.v1",
            **scope_fields(),
            "status": "STOP_REQUESTED",
            "queued_jobs_stopped": 0,
        }
    store = EvaluationStateStore(paths.database)
    store.request_stop()
    stopped = store.stop_not_running()
    write_json_atomic(
        paths.stop_record,
        {
            "schema_version": "full-pipeline-extended-stop-request.v1",
            **scope_fields(),
            "status": "STOP_REQUESTED",
            "requested_at_utc": _utc_now(),
            "queued_jobs_stopped": stopped,
        },
    )
    _write_controller_state(
        paths,
        status="STOP_REQUESTED",
        action="Stop",
        detail="Graceful restart-safe stop requested",
    )
    return {
        "schema_version": "full-pipeline-extended-stop.v1",
        **scope_fields(),
        "status": "STOP_REQUESTED",
        "queued_jobs_stopped": stopped,
        "progress": publish_program_progress(paths),
    }


def validate_terminal(*, workspace_root: Path = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    plan = read_json(paths.plan)
    validate_plan(plan)
    store = EvaluationStateStore(paths.database)
    states = store.list_jobs()
    expected = {spec.job_id for spec in plan_specs(plan)}
    observed = {row.spec.job_id for row in states}
    errors: list[str] = []
    if observed != expected:
        errors.append("durable job inventory differs from bounded plan")
    nonterminal = [
        row.spec.job_id for row in states if row.state not in {"complete", "failed"}
    ]
    if nonterminal:
        errors.append(f"{len(nonterminal)} jobs are not terminal complete/failed")
    for row in states:
        result_root = paths.results / row.spec.job_id
        if row.state == "complete" and not (result_root / "checksums.json").is_file():
            errors.append(f"complete job lacks checksums: {row.spec.job_id}")
        if row.state == "failed" and not row.last_error:
            errors.append(f"failed job lacks explicit error: {row.spec.job_id}")
    return {
        "schema_version": "full-pipeline-extended-terminal-validation.v1",
        **scope_fields(),
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        "job_count": len(states),
        "complete_count": sum(row.state == "complete" for row in states),
        "failed_count": sum(row.state == "failed" for row in states),
        "errors": errors,
    }


def _require_prepared(
    workspace_root: Path,
    *,
    predecessor_path: Path,
    predecessor_sha256: str | None,
    program_state_path: Path,
    amendment_path: Path,
    deployment_steering_path: Path = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> tuple[Layout, dict[str, object], dict[str, object]]:
    paths = layout(workspace_root)
    for required in (
        paths.authorization,
        paths.input_binding,
        paths.plan,
        paths.database,
        paths.hardening_manifest,
    ):
        if not required.exists():
            raise ExtendedEvaluationError(f"Prepare output is missing: {required}")
    storage_preflight(paths.root)
    authorization = validate_saved_authorization(
        read_json(paths.authorization),
        predecessor_path=predecessor_path,
        expected_sha256=predecessor_sha256,
        program_state_path=program_state_path,
        amendment_path=amendment_path,
        deployment_steering_path=deployment_steering_path,
        deployment_steering_sha256=deployment_steering_sha256,
    )
    plan = read_json(paths.plan)
    validate_plan(plan)
    binding = read_json(paths.input_binding)
    unsigned_binding = dict(binding)
    claimed_binding_identity = unsigned_binding.pop("binding_identity_sha256", None)
    if claimed_binding_identity != sha256_bytes(canonical_json_bytes(unsigned_binding)):
        raise ExtendedEvaluationError("Prompt-6 input binding identity differs")
    if binding.get("bounded_plan_sha256") != sha256_file(paths.plan):
        raise ExtendedEvaluationError("Prompt-6 input binding plan hash differs")
    if binding.get("prompt6_authorization_sha256") != sha256_file(paths.authorization):
        raise ExtendedEvaluationError(
            "Prompt-6 input binding authorization hash differs"
        )
    if binding.get("raspberry_pi_deployment_steering") != authorization.get(
        "raspberry_pi_deployment_steering"
    ):
        raise ExtendedEvaluationError("deployment steering input binding differs")
    if binding.get("prompt5_deployment_evidence") != authorization.get(
        "prompt5_deployment_evidence"
    ):
        raise ExtendedEvaluationError("Prompt-5 deployment evidence binding differs")
    if binding.get("hardening_input_manifest_sha256") != sha256_file(
        paths.hardening_manifest
    ):
        raise ExtendedEvaluationError("hardening input binding differs")
    predecessor_binding = binding.get("predecessor_completion_input")
    if (
        not isinstance(predecessor_binding, Mapping)
        or predecessor_binding.get("path") != str(Path(predecessor_path).resolve())
        or predecessor_binding.get("sha256")
        != sha256_file(Path(predecessor_path).resolve())
    ):
        raise ExtendedEvaluationError("predecessor completion input binding differs")
    return paths, plan, authorization


def _run_jobs(
    paths: Layout,
    plan: Mapping[str, object],
    authorization: Mapping[str, object],
    *,
    measurement_mode: str,
    parallel_jobs: int,
) -> dict[str, object]:
    store = EvaluationStateStore(paths.database)
    store.assert_integrity()
    store.reclaim_expired_leases()
    store.clear_stop()
    if paths.stop_record.is_file():
        paths.stop_record.unlink()
    started = _stage_started(paths)
    _write_controller_state(
        paths,
        status="RUNNING",
        action=f"Run{measurement_mode.title()}",
        detail=f"Running bounded {measurement_mode} jobs",
        stage_started_at_utc=started,
    )
    raw_jobs = plan.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ExtendedEvaluationError("Prompt-6 plan job records are missing")
    records = {
        str(row["job_id"]): row
        for row in raw_jobs
        if isinstance(row, Mapping) and row.get("measurement_class") == measurement_mode
    }
    registry = authorization.get("decision_policy_registry")
    if not isinstance(registry, Mapping):
        raise ExtendedEvaluationError("decision registry authorization is missing")
    registry_path = Path(str(registry["path"]))
    eligible = [
        row
        for row in store.list_jobs(measurement_mode=measurement_mode)
        if row.state in {"pending", "partial", "stopped"}
    ]
    if not eligible:
        value = _run_result(paths, measurement_mode)
        _write_controller_state(
            paths,
            status=str(value["status"]),
            action=f"Run{measurement_mode.title()}",
            detail="No restart-eligible jobs remain",
        )
        return value

    monitor_stop = threading.Event()
    monitor = threading.Thread(
        target=_monitor_run,
        args=(paths, store, monitor_stop, started),
        daemon=True,
        name="prompt6-storage-progress-monitor",
    )
    monitor.start()
    futures: set[Future[None]] = set()
    iterator = iter(eligible)
    try:
        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            while True:
                while len(futures) < parallel_jobs and not store.stop_requested():
                    try:
                        state = next(iterator)
                    except StopIteration:
                        break
                    record = records.get(state.spec.job_id)
                    if record is None:
                        raise ExtendedEvaluationError(
                            f"plan record missing for {state.spec.job_id}"
                        )
                    futures.add(
                        executor.submit(
                            _run_one,
                            paths,
                            store,
                            record,
                            registry_path,
                            authorization,
                            plan,
                        )
                    )
                if not futures:
                    break
                done, futures = wait(futures, timeout=5.0, return_when=FIRST_COMPLETED)
                for future in done:
                    future.result()
                publish_program_progress(paths)
                if store.stop_requested() and not futures:
                    break
    finally:
        monitor_stop.set()
        monitor.join(timeout=10.0)
    if store.stop_requested():
        store.stop_not_running()
    result = _run_result(paths, measurement_mode)
    _write_controller_state(
        paths,
        status=str(result["status"]),
        action=f"Run{measurement_mode.title()}",
        detail=f"Bounded {measurement_mode} scheduler returned",
    )
    publish_program_progress(paths)
    return result


def _run_one(
    paths: Layout,
    store: EvaluationStateStore,
    record: Mapping[str, object],
    registry_path: Path,
    authorization: Mapping[str, object],
    plan: Mapping[str, object],
) -> None:
    # This check is intentionally inside the worker boundary: every job proves
    # that all 18 frozen YAMLs still match the exact live matrix/runtime/code
    # contract before it claims durable work.
    _revalidate_live_execution_proof(authorization, plan)
    job_id = str(record["job_id"])
    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    claimed = store.claim(job_id, owner=owner, lease_seconds=120)
    if claimed is None:
        return
    attempt = claimed.attempt_count
    attempt_root = paths.attempts / job_id / f"attempt_{attempt:03d}"
    work_result = attempt_root / "result"
    attempt_root.mkdir(parents=True, exist_ok=True)
    started = _utc_now()
    latest: dict[str, object] = {
        "completed_cases": 0,
        "completed_audio_sec": 0.0,
        "current_case_id": None,
        "latest_activity": "attempt claimed",
    }
    latest_lock = threading.Lock()
    heartbeat_stop = threading.Event()

    def heartbeat(**values: object) -> None:
        with latest_lock:
            latest.update(values)
            snapshot = dict(latest)
        store.heartbeat(job_id, owner=owner, **_heartbeat_values(snapshot))
        publish_program_progress(paths)

    def keepalive() -> None:
        while not heartbeat_stop.wait(20.0):
            try:
                with latest_lock:
                    snapshot = dict(latest)
                store.heartbeat(job_id, owner=owner, **_heartbeat_values(snapshot))
                publish_program_progress(paths)
            except Exception:
                return

    keepalive_thread = threading.Thread(target=keepalive, daemon=True)
    keepalive_thread.start()
    state = "failed"
    error: str | None = None
    result_sha: str | None = None
    completed_cases = 0
    completed_audio = 0.0
    try:
        if record.get("engine") == "scored_runtime":
            outcome = execute_scored(
                record,
                output_root=work_result,
                progress=heartbeat,
                stop_requested=store.stop_requested,
                decision_policy_registry_path=registry_path,
            )
        else:
            outcome = execute_custom(
                record,
                output_root=work_result,
                workspace_root=paths.root,
                progress=heartbeat,
                stop_requested=store.stop_requested,
                decision_policy_registry_path=registry_path,
            )
        state = str(outcome.get("state") or "failed")
        completed_cases = int(outcome.get("completed_cases") or 0)
        completed_audio = float(outcome.get("completed_audio_sec") or 0.0)
        error = str(outcome.get("error") or "") or None
        if work_result.exists():
            destination = paths.results / job_id
            _publish_result(work_result, destination)
            if (destination / "checksums.json").is_file():
                result_sha = sha256_file(destination / "checksums.json")
        if store.stop_requested() and state not in {"complete", "failed"}:
            state = "stopped"
        if state not in {"complete", "failed", "stopped", "partial"}:
            state = "failed"
            error = error or "executor returned an invalid terminal state"
    except Exception as exc:
        state = "stopped" if store.stop_requested() else "failed"
        error = f"{type(exc).__name__}: {exc}"
        write_json_atomic(
            attempt_root / "failure.json",
            {
                "schema_version": "full-pipeline-extended-attempt-failure.v1",
                **scope_fields(),
                "job_id": job_id,
                "error": error,
                "state": state,
            },
        )
    finally:
        heartbeat_stop.set()
        keepalive_thread.join(timeout=5.0)
    store.finish(
        job_id,
        owner=owner,
        state=state,
        completed_cases=completed_cases,
        completed_audio_sec=completed_audio,
        latest_activity=error or f"{state} result finalized",
        result_sha256=result_sha,
        last_error=error,
    )
    store.record_attempt(
        job_id=job_id,
        attempt_number=attempt,
        state=state,
        attempt_path=attempt_root,
        started_at_utc=started,
        ended_at_utc=_utc_now(),
        error=error,
    )


def _revalidate_live_execution_proof(
    authorization: Mapping[str, object],
    plan: Mapping[str, object],
) -> dict[str, object]:
    frozen = authorization.get("frozen_pipeline_configs")
    registry = authorization.get("decision_policy_registry")
    bound = plan.get("frozen_execution_contract")
    if not all(isinstance(item, Mapping) for item in (frozen, registry, bound)):
        raise ExtendedEvaluationError("Prompt-6 live execution proof is absent")
    assert isinstance(frozen, Mapping)
    assert isinstance(registry, Mapping)
    assert isinstance(bound, Mapping)
    registry_path = Path(str(registry.get("path") or ""))
    if (
        not registry_path.is_file()
        or sha256_file(registry_path) != str(registry.get("sha256") or "").casefold()
    ):
        raise ExtendedEvaluationError("decision-policy registry changed before job")
    current = _validate_frozen_configs(
        frozen,
        policy_registry=read_json(registry_path),
    )
    current_binding = _execution_contract_binding(current)
    if current_binding != dict(bound):
        raise ExtendedEvaluationError(
            "frozen/live execution proof changed before Prompt-6 job"
        )
    return current_binding


def _publish_result(source: Path, destination: Path) -> None:
    if destination.exists():
        current = destination / "checksums.json"
        candidate = source / "checksums.json"
        if (
            current.is_file()
            and candidate.is_file()
            and sha256_file(current) == sha256_file(candidate)
        ):
            shutil.rmtree(source)
            return
        raise ExtendedEvaluationError(f"immutable result differs: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)


def _monitor_run(
    paths: Layout,
    store: EvaluationStateStore,
    stop_event: threading.Event,
    started_at_utc: str,
) -> None:
    while not stop_event.wait(10.0):
        publish_program_progress(paths)
        storage = storage_preflight(paths.root, fail=False)
        if storage.get("status") != "PASS":
            reason = "BLOCKED_C_DRIVE_RESERVE_35_GIB"
            write_json_atomic(
                paths.root / "graceful_pause.json",
                {
                    "schema_version": "full-pipeline-extended-graceful-pause.v1",
                    **scope_fields(),
                    "status": reason,
                    "storage": storage,
                    "stage_elapsed_hours": _hours_since(started_at_utc),
                    "nominal_planning_target_hours": NOMINAL_STAGE_TARGET_HOURS,
                    "elapsed_time_stop_enabled": False,
                },
            )
            store.request_stop()
            store.stop_not_running()
            return


def _run_result(paths: Layout, measurement_mode: str) -> dict[str, object]:
    rows = EvaluationStateStore(paths.database).list_jobs(
        measurement_mode=measurement_mode
    )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.state] = counts.get(row.state, 0) + 1
    interrupted = any(
        state in counts for state in ("pending", "running", "partial", "stopped")
    )
    return {
        "schema_version": "full-pipeline-extended-run-result.v1",
        **scope_fields(),
        "status": "STOPPED" if interrupted else "COMPLETE",
        "measurement_mode": measurement_mode,
        "job_count": len(rows),
        "state_counts": counts,
        "explicit_failures_retained": counts.get("failed", 0),
    }


def _heartbeat_values(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "completed_cases": int(value.get("completed_cases") or 0),
        "completed_audio_sec": float(value.get("completed_audio_sec") or 0.0),
        "current_case_id": (
            str(value["current_case_id"]) if value.get("current_case_id") else None
        ),
        "latest_activity": str(value.get("latest_activity") or "running"),
        "rolling_rtf": _optional_float(value.get("rolling_rtf")),
        "cpu_percent": _optional_float(value.get("cpu_percent")),
        "rss_mb": _optional_float(value.get("rss_mb")),
        "queue_depth": _optional_int(value.get("queue_depth")),
        "cache_hits": _optional_int(value.get("cache_hits")),
    }


def _material_inventory(
    paths: Layout,
    authorization: Mapping[str, object],
    predecessor_path: Path,
) -> dict[str, list[str]]:
    frozen = authorization["frozen_pipeline_configs"]
    registry = authorization["decision_policy_registry"]
    extended = authorization["extended_set"]
    steering = authorization["raspberry_pi_deployment_steering"]
    prompt5_deployment = authorization["prompt5_deployment_evidence"]
    if not all(
        isinstance(item, Mapping)
        for item in (frozen, registry, extended, steering, prompt5_deployment)
    ):
        raise ExtendedEvaluationError("authorization material paths are invalid")
    inventory = {
        "inputs": [
            str(Path(predecessor_path).resolve()),
            str(DEFAULT_PROTOCOL_ROOT.resolve()),
            str(DEFAULT_ENROLLMENT_REGISTRY.resolve()),
            str(Path(str(extended["path"])).resolve()),  # type: ignore[index]
            str(Path(str(registry["path"])).resolve()),  # type: ignore[index]
            str(Path(str(frozen["path"])).resolve()),  # type: ignore[index]
            str(DEFAULT_AMENDMENT.resolve()),
            str(DEFAULT_PROGRAM_STATE.resolve()),
            str(Path(str(steering["path"])).resolve()),  # type: ignore[index]
            str(Path(str(prompt5_deployment["path"])).resolve()),  # type: ignore[index]
        ],
        "workspaces": [str(paths.root)],
        "caches": [str(DEFAULT_SHARED_CACHE.resolve())],
        "temporary": [str(paths.temp)],
        "logs": [str(paths.logs)],
        "results": [str(paths.results)],
        "reports": [str(DEFAULT_REPORT_ROOT.resolve()), str(paths.report)],
        "packages": [
            str(DEFAULT_REPORT_ROOT.parent.resolve()),
            str(paths.artifact_manifest),
            str(paths.gates),
        ],
        "checkpoints": [str(TOOL_ROOT.parents[1] / "models")],
    }
    if set(inventory) != {
        "inputs",
        "workspaces",
        "caches",
        "temporary",
        "logs",
        "results",
        "reports",
        "packages",
        "checkpoints",
    }:
        raise ExtendedEvaluationError("material inventory classes differ")
    for values in inventory.values():
        for value in values:
            ensure_c_drive(value, label="material path")
    return inventory


def _stage_started(paths: Layout) -> str:
    if paths.controller_state.is_file():
        value = read_json(paths.controller_state).get("stage_started_at_utc")
        if isinstance(value, str) and value:
            return value
    return _utc_now()


def _write_controller_state(
    paths: Layout,
    *,
    status: str,
    action: str,
    detail: str,
    stage_started_at_utc: str | None = None,
) -> None:
    existing = (
        read_json(paths.controller_state) if paths.controller_state.is_file() else {}
    )
    started = stage_started_at_utc
    if started is None:
        raw = existing.get("stage_started_at_utc")
        started = str(raw) if raw else None
    value = {
        "schema_version": "full-pipeline-extended-controller-state.v1",
        **scope_fields(),
        "status": status,
        "action": action,
        "detail": detail,
        "stage_started_at_utc": started,
        "updated_at_utc": _utc_now(),
    }
    write_json_atomic(paths.controller_state, value)
    paths.controller_log.parent.mkdir(parents=True, exist_ok=True)
    with paths.controller_log.open("ab") as stream:
        stream.write(canonical_json_bytes(value) + b"\n")


def _hours_since(value: str) -> float:
    started = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - started).total_seconds() / 3600.0)


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "Layout",
    "layout",
    "prepare",
    "run_accuracy",
    "run_resources",
    "status",
    "stop",
    "validate_prerequisite",
    "validate_terminal",
]
