"""Single-scenario-at-a-time persistent campaign process executor."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any

from app.artifact_contracts.atomic import ScenarioArtifactStore
from app.artifact_contracts.completion import CompletionReport, validate_scenario_completion
from app.artifact_contracts.registry import (
    ARTIFACT_REGISTRY_VERSION,
    LATEST_ARTIFACT_REGISTRY_VERSION,
    registry_for_campaign,
    registry_for_scenario,
)
from app.benchmark_contracts.scenario import validate_scenario
from app.campaign_executor.planner import validate_campaign
from app.campaign_executor.state import (
    ExecutionLease,
    SUCCESS_STATES,
    CampaignStateStore,
)
from app.resource_telemetry.context import (
    ACTIVE_PATH_ENV,
    CONTEXT_ENV,
    CUDA_TIMING_ENV,
    REGISTRY_ENV,
    SPAN_PATH_ENV,
)
from app.resource_telemetry.providers import GpuTelemetryProvider, SystemTelemetryProvider
from app.resource_telemetry.session import (
    ScenarioTelemetrySession,
    migrate_scenario_registry,
)


CommandBuilder = Callable[[ExecutionLease, Path], Sequence[str]]

OOM_EXIT_CODE = 88
TRANSIENT_EXIT_CODE = 75
CONFIG_EXIT_CODE = 78


@dataclass(frozen=True)
class ExecutorResult:
    campaign_id: str
    worker_id: str
    attempted: int
    succeeded: int
    failed: int
    stopped: int
    skipped_complete: int
    recovered_stale: int

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": "campaign-executor-result.v1",
            "campaign_id": self.campaign_id,
            "worker_id": self.worker_id,
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "stopped": self.stopped,
            "skipped_complete": self.skipped_complete,
            "recovered_stale": self.recovered_stale,
        }


class CampaignExecutor:
    """Claim leased work, supervise subprocesses, and persist every outcome."""

    def __init__(
        self,
        campaign_root: Path,
        *,
        project_root: Path,
        worker_id: str,
        command_builder: CommandBuilder | None = None,
        hostname: str | None = None,
        lease_seconds: float = 120.0,
        heartbeat_seconds: float = 10.0,
        stop_poll_seconds: float = 0.25,
        terminate_grace_seconds: float = 5.0,
        minimum_free_disk_bytes: int = 5 * 1024**3,
        telemetry_enabled: bool = False,
        telemetry_interval_sec: float = 1.0,
        telemetry_system_provider: SystemTelemetryProvider | None = None,
        telemetry_gpu_provider: GpuTelemetryProvider | None = None,
    ) -> None:
        if heartbeat_seconds <= 0 or lease_seconds <= heartbeat_seconds:
            raise ValueError("lease_seconds must exceed the positive heartbeat interval")
        self.campaign_root = campaign_root.resolve()
        self.project_root = project_root.resolve()
        self.evaluation_root = Path(__file__).resolve().parents[2]
        self.worker_id = worker_id
        self.hostname = hostname or socket.gethostname()
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.stop_poll_seconds = stop_poll_seconds
        self.terminate_grace_seconds = terminate_grace_seconds
        self.minimum_free_disk_bytes = int(minimum_free_disk_bytes)
        if telemetry_interval_sec <= 0:
            raise ValueError("telemetry_interval_sec must be positive")
        self.telemetry_enabled = bool(telemetry_enabled)
        self.telemetry_interval_sec = float(telemetry_interval_sec)
        self.telemetry_system_provider = telemetry_system_provider
        self.telemetry_gpu_provider = telemetry_gpu_provider
        self.command_builder = command_builder or self._default_command
        self.state = CampaignStateStore(
            self.campaign_root / "database" / "campaign.sqlite"
        )
        manifest = json.loads(
            (self.campaign_root / "campaign_manifest.json").read_text(encoding="utf-8")
        )
        self.registry = registry_for_campaign(self.campaign_root)
        self.campaign_id = str(manifest["campaign_id"])
        self._interrupt_requested = threading.Event()

    def request_interrupt(self) -> None:
        """Request the same safe child termination path used by Ctrl+C."""

        self._interrupt_requested.set()

    def run(
        self,
        *,
        scenario_ids: Sequence[str] | None = None,
        max_scenarios: int | None = None,
        dry_run: bool = False,
    ) -> ExecutorResult:
        validate_campaign(self.campaign_root)
        selected = tuple(scenario_ids) if scenario_ids else None
        if selected:
            known = {item.scenario_id for item in self.state.scenarios(self.campaign_id)}
            missing = set(selected) - known
            if missing:
                raise ValueError(f"unknown scenario IDs: {sorted(missing)}")
        if dry_run:
            queue = [
                item.scenario_id
                for item in self.state.scenarios(self.campaign_id)
                if (selected is None or item.scenario_id in selected)
                and item.state not in SUCCESS_STATES
            ]
            print(json.dumps({"dry_run": True, "queue": queue}, indent=2))
            return ExecutorResult(
                self.campaign_id,
                self.worker_id,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        stale = self.state.recover_stale_leases(self.campaign_id)
        for scenario_id in stale:
            self._event(scenario_id, "stale_lease_recovered", {})
        skipped = self._audit_existing_successes(selected)

        attempted = succeeded = failed = stopped = 0
        try:
            while max_scenarios is None or attempted < max_scenarios:
                lease = self.state.acquire_next(
                    self.campaign_id,
                    worker_id=self.worker_id,
                    hostname=self.hostname,
                    lease_seconds=self.lease_seconds,
                    scenario_ids=selected,
                )
                if lease is None:
                    break
                attempted += 1
                outcome = self._execute_lease(lease)
                if outcome in SUCCESS_STATES:
                    succeeded += 1
                elif outcome == "stopped":
                    stopped += 1
                else:
                    failed += 1
                print(
                    f"[{attempted}] {lease.scenario_id} -> {outcome} "
                    f"(attempt {lease.attempt_number}/{lease.max_attempts})",
                    flush=True,
                )
                if self._interrupt_requested.is_set():
                    break
        except KeyboardInterrupt:
            self._interrupt_requested.set()
            print("Interrupt received; current scenario was preserved for resume.", flush=True)
        result = ExecutorResult(
            self.campaign_id,
            self.worker_id,
            attempted,
            succeeded,
            failed,
            stopped,
            skipped,
            len(stale),
        )
        print(json.dumps(result.to_jsonable(), indent=2), flush=True)
        return result

    def _execute_lease(self, lease: ExecutionLease) -> str:
        scenario_root = self.campaign_root / "scenarios" / lease.scenario_id
        try:
            scenario = _read_scenario(scenario_root)
        except Exception as exc:
            self.state.mark_running(lease)
            message = f"resolved scenario validation failed: {type(exc).__name__}: {exc}"
            self._error(lease.scenario_id, "scenario_identity", message)
            self.state.finalize(
                lease,
                state="invalid",
                exit_code=None,
                exception_category="scenario_identity",
                concise_error=message,
                output_completeness="incompatible",
                retry_eligible=False,
            )
            return "invalid"
        if scenario["scenario_hash"] != lease.scenario_hash:
            self.state.mark_running(lease)
            self.state.finalize(
                lease,
                state="invalid",
                exit_code=None,
                exception_category="scenario_identity",
                concise_error="resolved scenario hash differs from leased hash",
                output_completeness="incompatible",
                retry_eligible=False,
            )
            return "invalid"
        self.state.mark_running(lease)
        try:
            self._event(
                lease.scenario_id,
                "attempt_started",
                {"attempt": lease.attempt_number, "worker_id": self.worker_id},
            )
            if lease.attempt_number > 1:
                self._archive_partial_outputs(lease)
            if self.telemetry_enabled:
                migrate_scenario_registry(scenario_root, lease.scenario_id)
            timeout_seconds = _timeout_seconds(scenario)
            command = [str(item) for item in self.command_builder(lease, scenario_root)]
            if not command:
                raise ValueError("scenario command builder returned no command")
        except Exception as exc:
            message = f"deterministic execution setup failed: {type(exc).__name__}: {exc}"
            self._error(lease.scenario_id, "execution_setup", message)
            self.state.finalize(
                lease,
                state="failed_terminal",
                exit_code=None,
                exception_category="execution_setup",
                concise_error=message,
                output_completeness=_completion_state(scenario_root),
                retry_eligible=False,
            )
            return "failed_terminal"
        free_bytes = shutil.disk_usage(self.campaign_root).free
        required_free = max(
            self.minimum_free_disk_bytes,
            int(_resource_policy(scenario).get("minimum_free_disk_bytes", 0)),
        )
        if free_bytes < required_free:
            retry = lease.attempt_number < lease.max_attempts
            state = "failed_retryable" if retry else "failed_terminal"
            message = f"free disk {free_bytes} bytes is below required {required_free} bytes"
            self._error(lease.scenario_id, "disk_space", message)
            self.state.finalize(
                lease,
                state=state,
                exit_code=None,
                exception_category="disk_space",
                concise_error=message,
                output_completeness="incomplete",
                retry_eligible=retry,
            )
            return state

        runner_log = scenario_root / "logs" / "runner.log"
        runner_log.parent.mkdir(parents=True, exist_ok=True)
        process: subprocess.Popen[Any] | None = None
        telemetry_session: ScenarioTelemetrySession | None = None
        telemetry_failure: str | None = None
        telemetry_staging = (
            self.campaign_root
            / "audit"
            / "telemetry_raw"
            / lease.scenario_id
            / f"attempt_{lease.attempt_number:04d}"
        )
        started = time.monotonic()
        stop_reason: str | None = None
        timed_out = False
        interrupted = False
        try:
            with runner_log.open("a", encoding="utf-8", newline="\n") as log_handle:
                log_handle.write(
                    f"\n=== attempt {lease.attempt_number} started {_utc_now()} ===\n"
                )
                log_handle.flush()
                creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                child_environment = None
                if self.telemetry_enabled:
                    child_environment = dict(os.environ)
                    child_environment.update(
                        _telemetry_child_environment(
                            telemetry_staging,
                            campaign_id=self.campaign_id,
                            scenario_id=lease.scenario_id,
                            attempt=lease.attempt_number,
                            worker_id=self.worker_id,
                            host=self.hostname,
                            cuda_timing=_scenario_uses_cuda(scenario),
                        )
                    )
                elif self.registry.schema_version != ARTIFACT_REGISTRY_VERSION:
                    child_environment = dict(os.environ)
                    child_environment[REGISTRY_ENV] = self.registry.schema_version
                process = subprocess.Popen(
                    command,
                    cwd=self.evaluation_root,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    shell=False,
                    creationflags=creation_flags,
                    env=child_environment,
                )
                self.state.mark_running_process(lease, process.pid)
                if self.telemetry_enabled:
                    telemetry_session = ScenarioTelemetrySession(
                        campaign_id=self.campaign_id,
                        scenario_id=lease.scenario_id,
                        scenario_hash=lease.scenario_hash,
                        attempt=lease.attempt_number,
                        worker_id=self.worker_id,
                        host=self.hostname,
                        root_pid=process.pid,
                        disk_path=self.campaign_root,
                        staging_root=telemetry_staging,
                        gpu_index=_scenario_gpu_index(scenario),
                        interval_sec=self.telemetry_interval_sec,
                        system_provider=self.telemetry_system_provider,
                        gpu_provider=self.telemetry_gpu_provider,
                    )
                    try:
                        telemetry_session.start()
                    except Exception as exc:
                        _terminate_process(process, self.terminate_grace_seconds)
                        raise OSError(
                            f"telemetry sampler could not start: {type(exc).__name__}"
                        ) from exc
                next_heartbeat = time.monotonic() + self.heartbeat_seconds
                while process.poll() is None:
                    now = time.monotonic()
                    requested, reason = self.state.stop_requested(
                        self.campaign_id, lease.scenario_id
                    )
                    if requested:
                        stop_reason = reason
                        _terminate_process(process, self.terminate_grace_seconds)
                        break
                    if self._interrupt_requested.is_set():
                        interrupted = True
                        _terminate_process(process, self.terminate_grace_seconds)
                        break
                    if timeout_seconds is not None and now - started >= timeout_seconds:
                        timed_out = True
                        _terminate_process(process, self.terminate_grace_seconds)
                        break
                    if now >= next_heartbeat:
                        self.state.heartbeat(lease, lease_seconds=self.lease_seconds)
                        next_heartbeat = now + self.heartbeat_seconds
                    time.sleep(self.stop_poll_seconds)
                exit_code = process.wait()
                log_handle.write(
                    f"=== attempt {lease.attempt_number} ended {_utc_now()} exit={exit_code} ===\n"
                )
                log_handle.flush()
                os.fsync(log_handle.fileno())
        except KeyboardInterrupt:
            interrupted = True
            self._interrupt_requested.set()
            if process is not None:
                _terminate_process(process, self.terminate_grace_seconds)
            exit_code = process.wait() if process is not None else None
        except OSError as exc:
            if process is not None and process.poll() is None:
                _terminate_process(process, self.terminate_grace_seconds)
            exit_code = None
            message = f"process launch or I/O failure: {type(exc).__name__}: {exc}"
            retry = lease.attempt_number < lease.max_attempts
            state = "failed_retryable" if retry else "failed_terminal"
            self._error(lease.scenario_id, "process_io", message)
            self.state.finalize(
                lease,
                state=state,
                exit_code=exit_code,
                exception_category="process_io",
                concise_error=message,
                output_completeness=_completion_state(scenario_root),
                retry_eligible=retry,
            )
            return state
        finally:
            if telemetry_session is not None:
                try:
                    telemetry_session.publish(scenario_root)
                except Exception as exc:  # telemetry must not destroy inference artifacts
                    telemetry_failure = (
                        f"telemetry publication failed: {type(exc).__name__}: {exc}"
                    )
                    self._error(lease.scenario_id, "telemetry", telemetry_failure)

        if stop_reason is not None:
            self._event(
                lease.scenario_id,
                "scenario_stopped",
                {"attempt": lease.attempt_number, "reason": stop_reason},
            )
            self.state.finalize(
                lease,
                state="stopped",
                exit_code=exit_code,
                exception_category="stop_request",
                concise_error=stop_reason,
                output_completeness=_completion_state(scenario_root),
                retry_eligible=False,
            )
            return "stopped"
        if interrupted:
            self._event(
                lease.scenario_id,
                "scenario_interrupted",
                {"attempt": lease.attempt_number},
            )
            self.state.finalize(
                lease,
                state="interrupted",
                exit_code=exit_code,
                exception_category="interrupt",
                concise_error="execution interrupted; partial outputs preserved",
                output_completeness=_completion_state(scenario_root),
                retry_eligible=True,
            )
            return "interrupted"
        if timed_out:
            retry = lease.attempt_number < lease.max_attempts
            self._error(lease.scenario_id, "timeout", "scenario exceeded timeout policy")
            self.state.finalize(
                lease,
                state="timeout",
                exit_code=exit_code,
                exception_category="timeout",
                concise_error=f"scenario exceeded {timeout_seconds:g} second timeout",
                output_completeness=_completion_state(scenario_root),
                retry_eligible=retry,
            )
            return "timeout"

        if telemetry_failure is not None and exit_code == 0:
            self.state.finalize(
                lease,
                state="failed_terminal",
                exit_code=0,
                exception_category="telemetry",
                concise_error=_safe_message(telemetry_failure),
                output_completeness=_completion_state(scenario_root),
                retry_eligible=False,
            )
            return "failed_terminal"

        if exit_code == 0:
            self._event(
                lease.scenario_id,
                "subprocess_completed",
                {"attempt": lease.attempt_number, "exit_code": 0},
            )
            report = self._reconcile_and_validate(scenario_root, lease)
            if report.complete:
                warnings = _has_warnings(scenario_root)
                final_state = "succeeded_with_warnings" if warnings else "succeeded"
                self._event(
                    lease.scenario_id,
                    "scenario_completed",
                    {"attempt": lease.attempt_number, "state": final_state},
                )
                report = self._reconcile_and_validate(scenario_root, lease)
                if not report.complete:
                    return self._finalize_invalid(lease, report)
                self.state.finalize(
                    lease,
                    state=final_state,
                    exit_code=0,
                    exception_category=None,
                    concise_error=None,
                    output_completeness="complete",
                    retry_eligible=False,
                )
                return final_state
            return self._finalize_invalid(lease, report)

        tail = _tail_text(runner_log)
        state, category, retry = _classify_failure(
            exit_code,
            tail,
            scenario,
            attempts_remaining=lease.attempt_number < lease.max_attempts,
        )
        message = _failure_message(category, tail)
        self._error(lease.scenario_id, category, message)
        self._event(
            lease.scenario_id,
            "attempt_failed",
            {
                "attempt": lease.attempt_number,
                "state": state,
                "exit_code": exit_code,
                "category": category,
                "retry_eligible": retry,
            },
        )
        self.state.finalize(
            lease,
            state=state,
            exit_code=exit_code,
            exception_category=category,
            concise_error=message,
            output_completeness=_completion_state(scenario_root),
            retry_eligible=retry,
        )
        return state

    def _finalize_invalid(
        self,
        lease: ExecutionLease,
        report: CompletionReport,
    ) -> str:
        message = "; ".join(issue.code for issue in report.issues[:8]) or report.state
        self._error(lease.scenario_id, "artifact_validation", message)
        self.state.finalize(
            lease,
            state="invalid",
            exit_code=0,
            exception_category="artifact_validation",
            concise_error=f"successful process produced {report.state} artifacts: {message}",
            output_completeness=report.state,
            retry_eligible=False,
        )
        return "invalid"

    def _audit_existing_successes(self, selected: Sequence[str] | None) -> int:
        selected_set = set(selected or ())
        skipped = 0
        for record in self.state.scenarios(self.campaign_id):
            if selected_set and record.scenario_id not in selected_set:
                continue
            root = self.campaign_root / "scenarios" / record.scenario_id
            recoverable_states = {"pending", "assigned", "running", "interrupted"}
            should_validate = record.state in SUCCESS_STATES or (
                record.state in recoverable_states and (root / "checksums.json").is_file()
            )
            if not should_validate:
                continue
            report = validate_scenario_completion(root)
            if report.complete:
                self.state.mark_recovered_success(
                    self.campaign_id,
                    record.scenario_id,
                    warnings=_has_warnings(root),
                )
                skipped += 1
            elif record.state in SUCCESS_STATES:
                self.state.invalidate_success(
                    self.campaign_id,
                    record.scenario_id,
                    completeness=report.state,
                    concise_error="; ".join(issue.code for issue in report.issues[:8]),
                )
        return skipped

    def _archive_partial_outputs(self, lease: ExecutionLease) -> None:
        scenario_root = self.campaign_root / "scenarios" / lease.scenario_id
        archive = (
            self.campaign_root
            / "audit"
            / "partial_results"
            / lease.scenario_id
            / f"attempt_{lease.attempt_number - 1:04d}"
        )
        if archive.exists():
            raise RuntimeError(f"partial-result archive already exists: {archive}")
        moved = False
        for relative in (
            "predictions",
            "metrics",
            "resource_logs",
            "report",
            "status.json",
            "checksums.json",
        ):
            source = scenario_root / relative
            if not source.exists():
                continue
            if source.is_dir() and not any(source.iterdir()):
                continue
            target = archive / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            moved = True
        for relative in ("predictions", "metrics", "resource_logs", "report"):
            (scenario_root / relative).mkdir(parents=True, exist_ok=True)
        if moved:
            self._event(
                lease.scenario_id,
                "partial_results_archived",
                {
                    "previous_attempt": lease.attempt_number - 1,
                    "archive": (
                        Path("audit")
                        / "partial_results"
                        / lease.scenario_id
                        / f"attempt_{lease.attempt_number - 1:04d}"
                    ).as_posix(),
                },
            )

    def _reconcile_and_validate(
        self,
        scenario_root: Path,
        lease: ExecutionLease,
    ) -> CompletionReport:
        registry = registry_for_scenario(scenario_root)
        store = ScenarioArtifactStore(
            scenario_root,
            lease.scenario_id,
            registry=registry,
        )
        try:
            store.reconcile_checksum_manifest()
        except Exception:
            return validate_scenario_completion(scenario_root, registry=registry)
        return validate_scenario_completion(scenario_root, registry=registry)

    def _event(
        self,
        scenario_id: str,
        event_type: str,
        payload: Mapping[str, object],
    ) -> None:
        self.state.record_event(self.campaign_id, scenario_id, event_type, payload)
        path = self.campaign_root / "scenarios" / scenario_id / "logs" / "events.jsonl"
        row = {
            "schema_version": "scenario-events.v1",
            "scenario_id": scenario_id,
            "timestamp_utc": _utc_now(),
            "event_type": event_type,
            **dict(payload),
        }
        _append_jsonl(path, row)

    def _error(self, scenario_id: str, error_type: str, message: str) -> None:
        path = self.campaign_root / "scenarios" / scenario_id / "logs" / "errors.jsonl"
        _append_jsonl(
            path,
            {
                "schema_version": "scenario-errors.v1",
                "scenario_id": scenario_id,
                "timestamp_utc": _utc_now(),
                "error_type": error_type,
                "message": _safe_message(message),
            },
        )

    def _default_command(self, lease: ExecutionLease, scenario_root: Path) -> Sequence[str]:
        return (
            sys.executable,
            "-m",
            "app.campaign_executor.runtime",
            "--campaign-root",
            str(self.campaign_root),
            "--scenario-id",
            lease.scenario_id,
            "--project-root",
            str(self.project_root),
            "--attempt",
            str(lease.attempt_number),
        )


def _read_scenario(root: Path) -> dict[str, object]:
    value = json.loads((root / "resolved_scenario.json").read_text(encoding="utf-8"))
    validate_scenario(value)
    return value


def _timeout_seconds(scenario: Mapping[str, object]) -> float | None:
    policy = scenario.get("timeout_policy")
    value = policy.get("timeout_seconds") if isinstance(policy, Mapping) else None
    if value is None:
        return None
    numeric = float(value)
    if numeric <= 0:
        raise ValueError("scenario timeout_seconds must be positive")
    return numeric


def _resource_policy(scenario: Mapping[str, object]) -> Mapping[str, object]:
    value = scenario.get("resource_policy")
    return value if isinstance(value, Mapping) else {}


def _telemetry_child_environment(
    staging_root: Path,
    *,
    campaign_id: str,
    scenario_id: str,
    attempt: int,
    worker_id: str,
    host: str,
    cuda_timing: bool,
) -> dict[str, str]:
    staging_root.mkdir(parents=True, exist_ok=True)
    return {
        SPAN_PATH_ENV: str(staging_root / "component_spans.raw.jsonl"),
        ACTIVE_PATH_ENV: str(staging_root / "active_component.json"),
        CONTEXT_ENV: json.dumps(
            {
                "campaign_id": campaign_id,
                "scenario_id": scenario_id,
                "attempt": int(attempt),
                "worker_id": worker_id,
                "host": host,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        CUDA_TIMING_ENV: "1" if cuda_timing else "0",
        REGISTRY_ENV: LATEST_ARTIFACT_REGISTRY_VERSION,
    }


def _scenario_uses_cuda(scenario: Mapping[str, object]) -> bool:
    device = scenario.get("device")
    if isinstance(device, Mapping):
        return str(device.get("type") or device.get("device") or "").casefold() == "cuda"
    return str(device or "").casefold().startswith("cuda")


def _scenario_gpu_index(scenario: Mapping[str, object]) -> str | None:
    if not _scenario_uses_cuda(scenario):
        return None
    device = scenario.get("device")
    if isinstance(device, Mapping):
        value = device.get("index")
        return "0" if value is None else str(value)
    text = str(device)
    return text.split(":", 1)[1] if ":" in text else "0"


def _classify_failure(
    exit_code: int,
    log_tail: str,
    scenario: Mapping[str, object],
    *,
    attempts_remaining: bool,
) -> tuple[str, str, bool]:
    normalized = log_tail.casefold()
    oom = exit_code == OOM_EXIT_CODE or any(
        token in normalized
        for token in ("cuda out of memory", "outofmemoryerror", "out of memory", "cublas_status_alloc_failed")
    )
    if oom:
        retry = attempts_remaining and _oom_retry_allowed(scenario)
        return "out_of_memory", "out_of_memory", retry
    deterministic = exit_code == CONFIG_EXIT_CODE or any(
        token in normalized
        for token in (
            "schema validation",
            "scenario hash",
            "reference mismatch",
            "configuration error",
            "incompatible config",
        )
    )
    if deterministic:
        return "failed_terminal", "deterministic_configuration", False
    transient = exit_code == TRANSIENT_EXIT_CODE or any(
        token in normalized
        for token in (
            "temporarily unavailable",
            "connection reset",
            "timed out while reading",
            "transient i/o",
            "resource busy",
        )
    )
    if transient and attempts_remaining:
        return "failed_retryable", "transient_process", True
    return "failed_terminal", "process_failure", False


def _oom_retry_allowed(scenario: Mapping[str, object]) -> bool:
    policy = scenario.get("failure_policy")
    if not isinstance(policy, Mapping):
        return False
    value = policy.get("oom_retry")
    if not isinstance(value, Mapping) or value.get("enabled") is not True:
        return False
    action = value.get("safe_retry_action")
    return action in {
        "restart_process",
        "release_cuda_cache_then_restart",
        "clear_allocator_cache_then_restart",
    }


def _completion_state(scenario_root: Path) -> str:
    try:
        return validate_scenario_completion(scenario_root).state
    except Exception:
        return "incompatible"


def _has_warnings(scenario_root: Path) -> bool:
    path = scenario_root / "status.json"
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    warnings = value.get("warnings") if isinstance(value, Mapping) else None
    return isinstance(warnings, list) and bool(warnings)


def _terminate_process(process: subprocess.Popen[Any], grace_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=max(grace_seconds, 1.0))


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(row), sort_keys=True, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _tail_text(path: Path, limit: int = 16_384) -> str:
    if not path.is_file():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - limit))
        return handle.read().decode("utf-8", errors="replace")


def _failure_message(category: str, tail: str) -> str:
    lines = [line.strip() for line in tail.splitlines() if line.strip()]
    detail = lines[-1] if lines else "subprocess exited without diagnostic output"
    return _safe_message(f"{category}: {detail}")


def _safe_message(value: str, limit: int = 1000) -> str:
    text = " ".join(str(value).split())
    text = re.sub(
        r"(?i)(api[_-]?key|auth[_-]?token|access[_-]?key|password)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        text,
    )
    return text[:limit]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )
