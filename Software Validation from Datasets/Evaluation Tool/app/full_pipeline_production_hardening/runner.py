"""Restart-safe serial executor for the immutable Prompt-7 acceptance plan."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time
from typing import Mapping, Sequence

import psutil

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)

from . import TOOL_ROOT, scope_fields
from .io import HardeningError, ensure_c, storage_guard


REPO_PYTHON = TOOL_ROOT.parents[1] / ".venv/Scripts/python.exe"


def run_plan(*, workspace_root: Path, plan: Mapping[str, object]) -> dict[str, object]:
    root = ensure_c(workspace_root, label="Prompt-7 workspace")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise HardeningError("acceptance plan has no tasks")
    control = root / "control/stop_request.json"
    control.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(control, {"requested": False, "updated_at_utc": _utc()})
    _run_budget(root)
    plan_identity = sha256_bytes(canonical_json_bytes(dict(plan)))
    results: list[dict[str, object]] = []
    for index, raw in enumerate(tasks, start=1):
        if not isinstance(raw, Mapping):
            raise HardeningError(f"acceptance task {index} is invalid")
        if _stop_requested(control):
            return _summary(plan, results, status="STOPPED")
        storage_guard(root)
        task_id = str(raw.get("task_id") or "")
        task_root = root / "evidence" / task_id
        task = dict(raw)
        task_identity = sha256_bytes(canonical_json_bytes(task))
        existing = _latest_pass(
            task_root,
            task=task,
            task_identity=task_identity,
            plan_identity=plan_identity,
        )
        if existing is not None:
            results.append(existing)
            continue
        attempt = _next_attempt(task_root)
        result = _execute_task(
            task,
            attempt_root=attempt,
            workspace_root=root,
            stop_path=control,
            task_identity=task_identity,
            plan_identity=plan_identity,
        )
        result_path = attempt / "task_result.json"
        write_json_atomic(result_path, result)
        write_json_atomic(
            task_root / "latest.json",
            {
                "task_id": task_id,
                "attempt_path": str(attempt),
                "result_path": str(result_path),
                "result_sha256": sha256_file(result_path),
                "status": result["status"],
                "task_identity_sha256": task_identity,
                "plan_identity_sha256": plan_identity,
            },
        )
        results.append(result)
        storage_guard(root)
        if result.get("status") == "STOPPED":
            return _summary(plan, results, status="STOPPED")
    status = "PASS" if all(row.get("status") == "PASS" for row in results) else "FAIL"
    value = _summary(plan, results, status=status)
    write_json_atomic(root / "acceptance_execution.json", value)
    return value


def request_stop(workspace_root: Path) -> dict[str, object]:
    root = ensure_c(workspace_root, label="Prompt-7 workspace")
    path = root / "control/stop_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"requested": True, "requested_at_utc": _utc()}
    write_json_atomic(path, value)
    return {
        "schema_version": "full-pipeline-production-hardening-stop.v1",
        **scope_fields(),
        "status": "STOP_REQUESTED",
        "path": str(path),
    }


def _execute_task(
    task: dict[str, object],
    *,
    attempt_root: Path,
    workspace_root: Path,
    stop_path: Path,
    task_identity: str,
    plan_identity: str,
) -> dict[str, object]:
    attempt_root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    kind = str(task["kind"])
    command, expected_nonzero, interrupt_after = _command(
        task, attempt_root=attempt_root, workspace_root=workspace_root
    )
    command_record = {
        "schema_version": "full-pipeline-production-hardening-command.v1",
        **scope_fields(),
        "task": task,
        "argv": command,
        "shell": False,
        "expected_nonzero": expected_nonzero,
        "interrupt_after_sec": interrupt_after,
    }
    write_json_atomic(attempt_root / "command.json", command_record)
    stdout_path = attempt_root / "stdout.log"
    stderr_path = attempt_root / "stderr.log"
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    temporary_root = workspace_root / "temp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    offline_environment = {
        "TEMP": str(temporary_root),
        "TMP": str(temporary_root),
        "TMPDIR": str(temporary_root),
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "JP_OFFLINE_NO_DOWNLOAD": "1",
    }
    with (
        stdout_path.open("w", encoding="utf-8") as stdout,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        process = subprocess.Popen(
            command,
            cwd=TOOL_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            text=True,
            shell=False,
            creationflags=flags,
            env={**os.environ, **offline_environment},
        )
        write_json_atomic(
            attempt_root / "process.json",
            {"pid": process.pid, "started_at_utc": _utc(), "task_id": task["task_id"]},
        )
        interrupted = False
        external_stop = False
        observed_descendants: dict[int, float] = {}
        while process.poll() is None:
            elapsed = time.monotonic() - started
            _record_descendants(process.pid, observed_descendants)
            if _stop_requested(stop_path):
                external_stop = True
                interrupted = True
                _interrupt(process)
            elif interrupt_after is not None and elapsed >= interrupt_after:
                interrupted = True
                _interrupt(process)
            if int(elapsed) % 30 < 2:
                try:
                    storage_guard(workspace_root)
                except HardeningError:
                    _interrupt(process)
                    raise
            time.sleep(1.0)
        exit_code = int(process.returncode or 0)
    orphan_audit = _audit_and_cleanup_orphans(observed_descendants)
    payload = _last_json(stdout_path) or _last_json(stderr_path)
    passed = (exit_code != 0) if expected_nonzero else exit_code == 0
    if (
        kind == "recovery_fault"
        and task.get("fault_id") == "operator_stop_during_inference"
    ):
        passed = interrupted and exit_code != 0
    if external_stop:
        passed = False
    if int(orphan_audit["orphan_process_count_before_cleanup"]) != 0:
        passed = False
    artifacts = _artifact_inventory(attempt_root)
    if kind == "enrollment_profile":
        enrollment_root = (
            workspace_root
            / "candidate_runtime"
            / str(task["pipeline_id"])
            / "enrollment"
        )
        artifacts.extend(_artifact_inventory(enrollment_root))
    return {
        "schema_version": "full-pipeline-production-hardening-task-result.v1",
        **scope_fields(),
        "task_id": task["task_id"],
        "pipeline_id": task["pipeline_id"],
        "candidate_role": task["candidate_role"],
        "kind": kind,
        "fault_id": task.get("fault_id"),
        "status": ("STOPPED" if external_stop else "PASS" if passed else "FAIL"),
        "exit_code": exit_code,
        "expected_nonzero": expected_nonzero,
        "interrupted_as_planned": interrupted and not external_stop,
        "operator_stop_request_observed": external_stop,
        "elapsed_sec": time.monotonic() - started,
        "source_mode": task.get("source_mode"),
        "runtime_binding": task.get("runtime_binding"),
        "task_identity_sha256": task_identity,
        "plan_identity_sha256": plan_identity,
        "command_payload": payload,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "artifacts": artifacts,
        "offline_environment": offline_environment,
        "implicit_downloads_allowed": False,
        "graceful_shutdown_observed": (
            int(orphan_audit["orphan_process_count_before_cleanup"]) == 0
        ),
        **orphan_audit,
        "thresholds_changed": False,
    }


def _command(
    task: Mapping[str, object], *, attempt_root: Path, workspace_root: Path
) -> tuple[list[str], bool, float | None]:
    if not REPO_PYTHON.is_file():
        raise HardeningError(f"repository Python is missing: {REPO_PYTHON}")
    pipeline = str(task["pipeline_id"])
    kind = str(task["kind"])
    candidate_root = workspace_root / "candidate_runtime" / pipeline
    enrollment_root = candidate_root / "enrollment"
    if kind == "controlled_loopback":
        raw_input = task.get("input")
        if not isinstance(raw_input, Mapping):
            raise HardeningError("controlled virtual loopback input is absent")
        return (
            [
                str(REPO_PYTHON),
                "-m",
                "app.full_pipeline_production_hardening.acceptance_worker",
                "controlled-virtual-loopback",
                "--pipeline-id",
                pipeline,
                "--input",
                str(raw_input["path"]),
                "--duration-sec",
                str(float(task.get("duration_sec") or 0.0)),
                "--session-id",
                str(task["task_id"]),
                "--results-root",
                str(attempt_root / "runs"),
                "--runtime-root",
                str(attempt_root / "runtime"),
                "--export-root",
                str(attempt_root / "export"),
                "--enrollment-root",
                str(enrollment_root),
                "--output",
                str(attempt_root / "controlled_virtual_loopback.json"),
            ],
            False,
            None,
        )
    if kind == "enrollment_profile":
        inputs = task.get("enrollment_inputs")
        if not isinstance(inputs, list) or len(inputs) != 3:
            raise HardeningError("enrollment task does not contain three samples")
        command = [
            str(REPO_PYTHON),
            "-m",
            "app.full_pipeline_demo",
            "enroll-import",
            "--pipeline-id",
            pipeline,
            "--display-name",
            f"Prompt7 {task['candidate_role']}",
            "--speaker-id",
            f"prompt7_{str(task['candidate_role']).casefold()}_speaker",
            "--enrollment-root",
            str(enrollment_root),
        ]
        for index, raw in enumerate(inputs, start=1):
            assert isinstance(raw, Mapping)
            command.extend(["--wav", f"prompt_{index}={raw['path']}"])
        return command, False, None
    if kind == "recovery_fault":
        fault = str(task.get("fault_id") or "")
        if fault in {
            "worker_process_failure_and_restart",
            "slow_consumer_queue_pressure",
        }:
            action = (
                "worker-recovery" if fault.startswith("worker") else "slow-consumer"
            )
            return (
                [
                    str(REPO_PYTHON),
                    "-m",
                    "app.full_pipeline_production_hardening.acceptance_worker",
                    action,
                    "--pipeline-id",
                    pipeline,
                    "--output",
                    str(attempt_root / "recovery.json"),
                ],
                False,
                None,
            )
        if fault == "unsupported_input_format":
            invalid = attempt_root / "unsupported.txt"
            invalid.write_text("not audio\n", encoding="utf-8")
            source = invalid
        else:
            source = Path(str(dict(task["input"])["path"]))
        fault_enrollment = enrollment_root
        if fault == "no_enrolled_speakers":
            fault_enrollment = attempt_root / "empty_enrollment"
            fault_enrollment.mkdir(parents=True)
        elif fault == "invalid_profile_binding":
            fault_enrollment = attempt_root / "invalid_enrollment"
            if not enrollment_root.is_dir():
                raise HardeningError(
                    "invalid-profile fault requires the completed enrollment task"
                )
            shutil.copytree(enrollment_root, fault_enrollment)
            profiles = sorted((fault_enrollment / "profiles").glob("*.json"))
            if not profiles:
                raise HardeningError("invalid-profile fault found no active profile")
            profile = json.loads(profiles[0].read_text(encoding="utf-8"))
            profile["backend_config_sha256"] = "0" * 64
            unsigned = {
                key: value for key, value in profile.items() if key != "profile_sha256"
            }
            profile["profile_sha256"] = hashlib.sha256(
                json.dumps(
                    unsigned,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            profiles[0].write_text(
                json.dumps(profile, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        command = _file_command(
            task,
            source=source,
            attempt_root=attempt_root,
            enrollment_root=fault_enrollment,
            duration_sec=float(task.get("duration_sec") or 30.0),
            pace=1.0 if fault == "operator_stop_during_inference" else 0.0,
        )
        expected_nonzero = fault in {
            "unsupported_input_format",
            "invalid_profile_binding",
            "operator_stop_during_inference",
        }
        return (
            command,
            expected_nonzero,
            10.0 if fault == "operator_stop_during_inference" else None,
        )
    raw_input = task.get("input")
    if not isinstance(raw_input, Mapping):
        raise HardeningError(f"{kind} task input is absent")
    return (
        _file_command(
            task,
            source=Path(str(raw_input["path"])),
            attempt_root=attempt_root,
            enrollment_root=enrollment_root,
            duration_sec=float(task.get("duration_sec") or 0.0),
            pace=float(task.get("pace") or 0.0),
        ),
        False,
        None,
    )


def _file_command(
    task: Mapping[str, object],
    *,
    source: Path,
    attempt_root: Path,
    enrollment_root: Path,
    duration_sec: float,
    pace: float,
) -> list[str]:
    return [
        str(REPO_PYTHON),
        "-m",
        "app.full_pipeline_demo",
        "file",
        "--pipeline-id",
        str(task["pipeline_id"]),
        "--input",
        str(source),
        "--pace",
        str(pace),
        "--duration-sec",
        str(duration_sec),
        "--session-id",
        str(task["task_id"]),
        "--results-root",
        str(attempt_root / "runs"),
        "--output-root",
        str(attempt_root / "runtime"),
        "--export-root",
        str(attempt_root / "export"),
        "--enrollment-root",
        str(enrollment_root),
    ]


def _next_attempt(task_root: Path) -> Path:
    attempts = task_root / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    existing = [path for path in attempts.iterdir() if path.is_dir()]
    return attempts / f"attempt_{len(existing) + 1:03d}"


def _latest_pass(
    task_root: Path,
    *,
    task: Mapping[str, object],
    task_identity: str,
    plan_identity: str,
) -> dict[str, object] | None:
    latest = task_root / "latest.json"
    if latest.is_file():
        ref = read_json(latest)
        path = _contained_result_path(task_root, ref.get("result_path"))
        if not path.is_file() or ref.get("result_sha256") != sha256_file(path):
            raise HardeningError(f"task latest result binding differs: {task_root}")
        result = read_json(path)
        _validate_reusable_result(
            result,
            task=task,
            task_identity=task_identity,
            plan_identity=plan_identity,
        )
        return result if result.get("status") == "PASS" else None
    attempts = task_root / "attempts"
    if not attempts.is_dir():
        return None
    for path in sorted(attempts.glob("attempt_*/task_result.json"), reverse=True):
        _contained_result_path(task_root, path)
        result = read_json(path)
        try:
            _validate_reusable_result(
                result,
                task=task,
                task_identity=task_identity,
                plan_identity=plan_identity,
            )
        except HardeningError:
            continue
        if result.get("status") != "PASS":
            continue
        write_json_atomic(
            latest,
            {
                "task_id": task["task_id"],
                "attempt_path": str(path.parent),
                "result_path": str(path),
                "result_sha256": sha256_file(path),
                "status": "PASS",
                "task_identity_sha256": task_identity,
                "plan_identity_sha256": plan_identity,
                "recovered_after_pointer_write_interruption": True,
            },
        )
        return result
    return None


def _contained_result_path(task_root: Path, raw: object) -> Path:
    path = Path(str(raw or "")).resolve()
    try:
        path.relative_to(task_root.resolve())
    except ValueError as exc:
        raise HardeningError(f"task result escaped its task root: {path}") from exc
    return path


def _validate_reusable_result(
    result: Mapping[str, object],
    *,
    task: Mapping[str, object],
    task_identity: str,
    plan_identity: str,
) -> None:
    expected = {
        "task_id": task.get("task_id"),
        "pipeline_id": task.get("pipeline_id"),
        "candidate_role": task.get("candidate_role"),
        "kind": task.get("kind"),
        "source_mode": task.get("source_mode"),
        "task_identity_sha256": task_identity,
        "plan_identity_sha256": plan_identity,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise HardeningError(f"reusable task result {key} differs")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        raise HardeningError("reusable task result lacks artifacts")
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise HardeningError("reusable task artifact is invalid")
        path = ensure_c(
            str(artifact.get("path") or ""),
            label="reusable task artifact",
            must_exist=True,
        )
        if artifact.get("sha256") != sha256_file(path):
            raise HardeningError(f"reusable task artifact differs: {path}")


def _artifact_inventory(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        if path.name in {"task_result.json", "process.json"}:
            continue
        rows.append(
            {
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
                "byte_count": path.stat().st_size,
            }
        )
    return rows


def _last_json(path: Path) -> Mapping[str, object] | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, Mapping):
        return value
    # Operational CLIs may write progress before their final JSON result. Decode
    # every possible object start and retain the last complete mapping.
    decoder = json.JSONDecoder()
    found: Mapping[str, object] | None = None
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, Mapping):
            found = candidate
    return found


def _stop_requested(path: Path) -> bool:
    return path.is_file() and read_json(path).get("requested") is True


def _interrupt(process: subprocess.Popen[object]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGINT)
        process.wait(timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _record_descendants(pid: int, observed: dict[int, float]) -> None:
    try:
        root = psutil.Process(pid)
        for child in root.children(recursive=True):
            observed.setdefault(child.pid, child.create_time())
    except (psutil.Error, OSError):
        return


def _audit_and_cleanup_orphans(observed: Mapping[int, float]) -> dict[str, object]:
    deadline = time.monotonic() + 5.0
    alive: list[psutil.Process] = []
    while True:
        alive = []
        for pid, created in observed.items():
            try:
                process = psutil.Process(pid)
                if abs(process.create_time() - created) < 0.01 and process.is_running():
                    alive.append(process)
            except (psutil.Error, OSError):
                continue
        if not alive or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    before = sorted(process.pid for process in alive)
    for process in alive:
        try:
            process.terminate()
        except psutil.Error:
            pass
    _, remaining = psutil.wait_procs(alive, timeout=3.0)
    for process in remaining:
        try:
            process.kill()
        except psutil.Error:
            pass
    _, remaining = psutil.wait_procs(remaining, timeout=2.0)
    return {
        "observed_descendant_process_count": len(observed),
        "orphan_process_count_before_cleanup": len(before),
        "orphan_process_ids_before_cleanup": before,
        "orphan_process_count_after_cleanup": len(remaining),
        "orphan_process_ids_after_cleanup": sorted(
            process.pid for process in remaining
        ),
    }


def _summary(
    plan: Mapping[str, object],
    results: Sequence[Mapping[str, object]],
    *,
    status: str,
) -> dict[str, object]:
    return {
        "schema_version": "full-pipeline-production-hardening-execution.v1",
        **scope_fields(),
        "status": status,
        "planned_task_count": plan.get("task_count"),
        "terminal_task_count": len(results),
        "passed_task_count": sum(row.get("status") == "PASS" for row in results),
        "failed_task_count": sum(
            row.get("status") not in {"PASS", "STOPPED"} for row in results
        ),
        "results": [dict(row) for row in results],
    }


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_budget(root: Path) -> dict[str, object]:
    path = root / "run_budget.json"
    if path.is_file():
        value = read_json(path)
        if (
            value.get("schema_version")
            != "full-pipeline-production-hardening-run-budget.v1"
            or int(value.get("nominal_planning_seconds") or 0) != 12 * 3600
            or float(value.get("nominal_planning_hours") or 0) != 12.0
            or value.get("elapsed_time_kill_switch_enabled") is not False
            or value.get("completion_policy") != "run_to_terminal_or_operator_stop"
            or value.get("scope_id") != scope_fields()["scope_id"]
            or value.get("scope_class") != scope_fields()["scope_class"]
            or value.get("original_full_scope_complete") is not False
            or "deadline_at_utc" in value
            or "budget_seconds" in value
        ):
            raise HardeningError("immutable Prompt-7 planning budget differs")
        started = datetime.fromisoformat(
            str(value.get("started_at_utc") or "").replace("Z", "+00:00")
        )
        if started > datetime.now(timezone.utc) + timedelta(minutes=1):
            raise HardeningError("immutable Prompt-7 planning start differs")
        return value
    started = datetime.now(timezone.utc)
    value = {
        "schema_version": "full-pipeline-production-hardening-run-budget.v1",
        **scope_fields(),
        "nominal_planning_seconds": 12 * 3600,
        "nominal_planning_hours": 12,
        "elapsed_time_kill_switch_enabled": False,
        "completion_policy": "run_to_terminal_or_operator_stop",
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "restart_policy": "RERUN_IDEMPOTENT_NO_ELAPSED_DEADLINE",
    }
    write_json_atomic(path, value)
    return value


__all__ = ["request_stop", "run_plan"]
