"""Restart-safe state machine for the amended Prompt 4–8 program."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from . import (
    COMPLETION_MARKERS,
    MINIMUM_FREE_GIB,
    PROMPTS,
    SCOPE_CLASS,
    SCOPE_ID,
    STAGE_BUDGET_HOURS,
    STATE_SCHEMA,
    TIME_TARGET_POLICY,
    TOTAL_BUDGET_HOURS,
)
from .contracts import (
    StageAdapter,
    ValidatedCompletion,
    adapter_environment,
    load_adapter_configuration,
    materialize_command,
    validate_amendment,
    validate_stage_completion,
)
from .storage import (
    ControllerLock,
    DurableNotifications,
    ProgramContractError,
    atomic_write_json,
    c_drive_free_bytes,
    file_sha256,
    load_json,
    parse_utc,
    pid_is_alive,
    resolve_c_only_path,
    utc_now,
)


GIB = 1024**3


class ProgramStopped(RuntimeError):
    """Internal signal for an intentional graceful stop."""


class ProgramNotReady(RuntimeError):
    """Internal signal for a missing bounded-stage command adapter."""


class ProgramController:
    """Drive one validated stage at a time and transition only on durable gates."""

    def __init__(
        self,
        config_path: Path,
        *,
        free_bytes_provider: Callable[[Path], int] = c_drive_free_bytes,
        pid_alive: Callable[[int], bool] = pid_is_alive,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = load_adapter_configuration(config_path)
        self.amendment = validate_amendment(self.config.amendment_path)
        self.free_bytes_provider = free_bytes_provider
        self.pid_alive = pid_alive
        self.monotonic = monotonic
        self.sleeper = sleeper
        self.workspace = self.config.program_workspace
        self.state_path = self.workspace / "program_state.json"
        self.notification_path = self.workspace / "milestones.jsonl"
        self.stop_request_path = self.workspace / "stop_request.json"
        self.preflight_root = self.workspace / "preflights"
        self.lock = ControllerLock(
            self.workspace / "controller.lock",
            state_path=self.state_path,
            pid_alive=pid_alive,
        )
        self.notifications: DurableNotifications | None = None

    def validate_configuration(self) -> dict[str, Any]:
        return {
            "status": "PASS",
            "scope_id": SCOPE_ID,
            "adapter_config": str(self.config.path),
            "adapter_config_sha256": self.config.raw_sha256,
            "amendment": str(self.config.amendment_path),
            "amendment_sha256": file_sha256(self.config.amendment_path),
            "program_workspace": str(self.workspace),
            "minimum_free_space_reserve_gib": MINIMUM_FREE_GIB,
            "time_target_policy": TIME_TARGET_POLICY,
            "stages": {
                str(prompt): {
                    "adapter_id": adapter.adapter_id,
                    "readiness": adapter.readiness,
                    "not_ready_reason": adapter.not_ready_reason,
                    "adapter_contract_sha256": adapter.contract_sha256,
                    "expected_duration_hours": adapter.expected_duration_hours,
                    "completion_marker": COMPLETION_MARKERS[prompt],
                }
                for prompt, adapter in self.config.stages.items()
            },
        }

    def run(self) -> str:
        self.workspace.mkdir(parents=True, exist_ok=True)
        stale = self.lock.acquire()
        self.notifications = DurableNotifications(self.notification_path)
        try:
            state = self._load_or_initialize_state()
            if stale is not None:
                self._notify(
                    state,
                    event_id=f"lock-recovered:{stale['previous'].get('token', 'unknown')}",
                    event_type="CONTROLLER_LOCK_RECOVERED",
                    previous_lock=stale,
                )
            self._bind_configuration(state)
            self._write_state(state)
            completions = self._revalidate_completed_prefix(state)
            first_incomplete = self._first_incomplete(state)
            if first_incomplete is None:
                self._finish_program(state, completions[8])
                return "COMPLETE"

            prompt = first_incomplete
            while prompt in PROMPTS:
                predecessor = completions.get(prompt - 1)
                if prompt > 4 and predecessor is None:
                    return self._block(
                        state,
                        marker="BLOCKED_UNMET_PREDECESSOR",
                        detail=f"Prompt {prompt - 1} has no validated completion.",
                        prompt=prompt,
                    )
                self._reload_configuration_at_boundary(state)
                adapter = self.config.stages[prompt]
                if adapter.readiness != "READY":
                    self._mark_not_ready(state, adapter)
                    raise ProgramNotReady(
                        f"Prompt {prompt} adapter is NOT_READY: {adapter.not_ready_reason}"
                    )
                self._admit_stage(state, adapter, predecessor)

                # An adapter may have finished between controller restarts. It is adopted
                # only after the same validator command and exact internal gates pass.
                recorded_child_pid = int(
                    state["stages"][str(prompt)].get("child_pid", 0) or 0
                )
                child_still_active = bool(
                    recorded_child_pid and self.pid_alive(recorded_child_pid)
                )
                if (
                    adapter.completion_record
                    and adapter.completion_record.exists()
                    and not child_still_active
                ):
                    try:
                        completion = self._validate_existing_completion(
                            state, adapter, predecessor
                        )
                    except ProgramContractError as exc:
                        # A stage may atomically emit its universal envelope just before
                        # a final native state/index update. If the controller or machine
                        # dies in that narrow window, use the declared restart-safe action
                        # once; never adopt the envelope until validation then passes.
                        stage_status = state["stages"][str(prompt)].get("status")
                        if stage_status == "COMPLETE":
                            raise
                        self._notify(
                            state,
                            event_id=(
                                f"prompt-{prompt}-incomplete-terminal-recovery:"
                                f"{adapter.contract_sha256}"
                            ),
                            event_type="INCOMPLETE_TERMINAL_STATE_RECOVERY",
                            prompt_index=prompt,
                            validation_error=str(exc),
                        )
                        completion = self._execute_or_recover_stage(
                            state, adapter, predecessor
                        )
                else:
                    completion = self._execute_or_recover_stage(
                        state, adapter, predecessor
                    )
                completions[prompt] = completion
                self._record_stage_completion(state, adapter, completion)
                if prompt == 8:
                    self._finish_program(state, completion)
                    return "COMPLETE"
                next_prompt = prompt + 1
                self._notify(
                    state,
                    event_id=(
                        f"transition:{prompt}:{completion.sha256}:to:{next_prompt}"
                    ),
                    event_type="AUTOMATIC_TRANSITION_ADMITTED",
                    completed_prompt=prompt,
                    next_prompt=next_prompt,
                    predecessor_completion_sha256=completion.sha256,
                )
                state["current_prompt_index"] = next_prompt
                state["status"] = "TRANSITIONING"
                self._write_state(state)
                prompt = next_prompt
        except ProgramNotReady:
            return "NOT_READY"
        except ProgramStopped:
            return "STOPPED"
        except ProgramContractError as exc:
            state = self._safe_load_state()
            if state is not None:
                detail = str(exc)
                marker = "BLOCKED_CONTRACT_VALIDATION"
                if "BLOCKED_C_DRIVE_RESERVE_35_GIB" in detail:
                    marker = "BLOCKED_C_DRIVE_RESERVE_35_GIB"
                self._block(
                    state,
                    marker=marker,
                    detail=detail,
                    prompt=state.get("current_prompt_index"),
                )
            raise
        finally:
            self.lock.release()

    def request_stop(self, *, reason: str) -> dict[str, Any]:
        self.workspace.mkdir(parents=True, exist_ok=True)
        existing = load_json(self.stop_request_path) if self.stop_request_path.exists() else None
        state = self._safe_load_state()
        processed_id = state.get("processed_stop_request_id") if state else None
        if existing and existing.get("request_id") != processed_id:
            return existing
        request = {
            "schema_version": "full-pipeline-eight-day-stop-request.v1",
            "request_id": uuid4().hex,
            "requested_at_utc": utc_now(),
            "reason": reason,
            "requested_by_pid": os.getpid(),
        }
        atomic_write_json(self.stop_request_path, request)
        return request

    def status(self) -> dict[str, Any]:
        state = self._safe_load_state()
        free = self.free_bytes_provider(self.config.evaluation_tool_root)
        if state is None:
            state = self._new_state()
            persisted = False
        else:
            persisted = True
        stage_views: list[dict[str, Any]] = []
        completed_weight = 0.0
        current_weight = 0.0
        current_eta = 0.0
        for prompt in PROMPTS:
            adapter = self.config.stages[prompt]
            stage = state["stages"][str(prompt)]
            status = str(stage.get("status", "PENDING"))
            percentage = 100.0 if status == "COMPLETE" else 0.0
            eta_seconds: float | None = None
            detail = stage.get("detail")
            if status in {"RUNNING", "STOPPING", "VALIDATING", "ADMITTED"}:
                percentage, eta_seconds, progress_detail = self._adapter_progress(adapter, stage)
                detail = progress_detail or detail
            if status == "COMPLETE":
                completed_weight += STAGE_BUDGET_HOURS[prompt]
            elif prompt == state.get("current_prompt_index"):
                current_weight = STAGE_BUDGET_HOURS[prompt] * percentage / 100.0
                current_eta = eta_seconds or (
                    adapter.expected_duration_hours * 3600 * (1.0 - percentage / 100.0)
                )
            stage_views.append(
                {
                    "prompt_index": prompt,
                    "status": status,
                    "readiness": adapter.readiness,
                    "percentage": round(percentage, 3),
                    "eta_seconds": eta_seconds,
                    "detail": detail,
                    "completion_marker": COMPLETION_MARKERS[prompt],
                    "adapter_id": adapter.adapter_id,
                }
            )
        nominal_total = sum(STAGE_BUDGET_HOURS.values())
        overall = 100.0 * (completed_weight + current_weight) / nominal_total
        remaining_future = sum(
            self.config.stages[prompt].expected_duration_hours * 3600
            for prompt in PROMPTS
            if state["stages"][str(prompt)].get("status") != "COMPLETE"
            and prompt != state.get("current_prompt_index")
        )
        elapsed = self._program_elapsed_seconds(state)
        target_delta = TOTAL_BUDGET_HOURS * 3600 - elapsed
        return {
            "schema_version": "full-pipeline-eight-day-monitor.v1",
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "persisted": persisted,
            "status": state.get("status"),
            "current_prompt_index": state.get("current_prompt_index"),
            "overall_percentage": round(min(100.0, overall), 3),
            "elapsed_seconds": round(elapsed, 3),
            # Kept for monitor/backward compatibility. This is an advisory target,
            # never an execution deadline.
            "remaining_envelope_seconds": round(max(0.0, target_delta), 3),
            "target_remaining_seconds": round(max(0.0, target_delta), 3),
            "target_overrun_seconds": round(max(0.0, -target_delta), 3),
            "time_target_policy": TIME_TARGET_POLICY,
            "eta_seconds": round(current_eta + remaining_future, 3),
            "c_drive_free_bytes": free,
            "c_drive_free_gib": round(free / GIB, 3),
            "minimum_free_space_reserve_gib": MINIMUM_FREE_GIB,
            "storage_status": "PASS" if free >= MINIMUM_FREE_GIB * GIB else "BLOCKED",
            "program_state": str(self.state_path),
            "milestone_notifications": str(self.notification_path),
            "stages": stage_views,
            "updated_at_utc": utc_now(),
        }

    def validate_completed_prefix(self) -> dict[str, Any]:
        state = self._safe_load_state()
        if state is None:
            return {"status": "PASS", "validated_prompts": [], "next_prompt": 4}
        completions = self._revalidate_completed_prefix(state)
        next_prompt = self._first_incomplete(state)
        return {
            "status": "PASS",
            "validated_prompts": sorted(completions),
            "completion_hashes": {
                str(prompt): completion.sha256
                for prompt, completion in completions.items()
            },
            "next_prompt": next_prompt,
        }

    def _new_state(self) -> dict[str, Any]:
        started = str(self.amendment.get("recorded_at_utc", utc_now()))
        return {
            "schema_version": STATE_SCHEMA,
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "status": "READY",
            "program_started_at_utc": started,
            "current_prompt_index": 4,
            "adapter_config_path": str(self.config.path),
            "adapter_config_sha256": self.config.raw_sha256,
            "amendment_path": str(self.config.amendment_path),
            "amendment_sha256": file_sha256(self.config.amendment_path),
            "minimum_free_space_reserve_gib": MINIMUM_FREE_GIB,
            "total_budget_hours": TOTAL_BUDGET_HOURS,
            "time_target_policy": TIME_TARGET_POLICY,
            "processed_stop_request_id": None,
            "stages": {
                str(prompt): {
                    "prompt_index": prompt,
                    "status": "PENDING",
                    "nominal_budget_hours": STAGE_BUDGET_HOURS[prompt],
                    "attempts": 0,
                }
                for prompt in PROMPTS
            },
            "updated_at_utc": utc_now(),
        }

    def _load_or_initialize_state(self) -> dict[str, Any]:
        state = self._safe_load_state()
        if state is None:
            state = self._new_state()
            self._notify(
                state,
                event_id=f"program-initialized:{file_sha256(self.config.amendment_path)}",
                event_type="PROGRAM_INITIALIZED",
                program_started_at_utc=state["program_started_at_utc"],
                total_budget_hours=TOTAL_BUDGET_HOURS,
                time_target_policy=TIME_TARGET_POLICY,
            )
            self._write_state(state)
            return state
        if state.get("schema_version") != STATE_SCHEMA:
            raise ProgramContractError("Program state schema is invalid")
        if state.get("scope_id") != SCOPE_ID or state.get("scope_class") != SCOPE_CLASS:
            raise ProgramContractError("Program state is bound to a different scope")
        if state.get("original_full_scope_complete") is not False:
            raise ProgramContractError("Program state violates bounded-scope labeling")
        if state.get("amendment_sha256") != file_sha256(self.config.amendment_path):
            raise ProgramContractError("The authoritative amendment changed after initialization")
        # This is an execution-policy migration only. It does not change the
        # scientific scope, stage inputs, frozen policies, or amendment hash.
        state["time_target_policy"] = TIME_TARGET_POLICY
        return state

    def _safe_load_state(self) -> dict[str, Any] | None:
        return load_json(self.state_path) if self.state_path.exists() else None

    def _bind_configuration(self, state: dict[str, Any]) -> None:
        for prompt in PROMPTS:
            stage_state = state["stages"][str(prompt)]
            bound = stage_state.get("adapter_contract_sha256")
            current = self.config.stages[prompt].contract_sha256
            if bound and stage_state.get("status") in {
                "ADMITTED",
                "RUNNING",
                "STOPPING",
                "VALIDATING",
                "COMPLETE",
            } and bound != current:
                raise ProgramContractError(
                    f"Prompt {prompt} adapter changed after admission: {bound} != {current}"
                )
        if state.get("adapter_config_sha256") != self.config.raw_sha256:
            old_hash = state.get("adapter_config_sha256")
            state["adapter_config_sha256"] = self.config.raw_sha256
            state["adapter_config_path"] = str(self.config.path)
            self._notify(
                state,
                event_id=f"adapter-config:{self.config.raw_sha256}",
                event_type="ADAPTER_CONFIGURATION_UPDATED",
                previous_sha256=old_hash,
                adapter_config_sha256=self.config.raw_sha256,
            )

    def _reload_configuration_at_boundary(self, state: dict[str, Any]) -> None:
        fresh = load_adapter_configuration(self.config.path)
        if fresh.program_workspace != self.workspace:
            raise ProgramContractError(
                "program_workspace cannot change after controller initialization"
            )
        if fresh.amendment_path != self.config.amendment_path:
            raise ProgramContractError(
                "amendment_path cannot change after controller initialization"
            )
        if fresh.evaluation_tool_root != self.config.evaluation_tool_root:
            raise ProgramContractError(
                "evaluation_tool_root cannot change after controller initialization"
            )
        self.config = fresh
        self._bind_configuration(state)

    def _revalidate_completed_prefix(
        self, state: dict[str, Any]
    ) -> dict[int, ValidatedCompletion]:
        completions: dict[int, ValidatedCompletion] = {}
        for prompt in PROMPTS:
            stage = state["stages"][str(prompt)]
            if stage.get("status") != "COMPLETE":
                break
            adapter = self.config.stages[prompt]
            predecessor = completions.get(prompt - 1)
            completion = validate_stage_completion(
                adapter=adapter, predecessor=predecessor
            )
            if stage.get("completion_record_sha256") != completion.sha256:
                raise ProgramContractError(
                    f"Prompt {prompt} completion changed after it was recorded"
                )
            completions[prompt] = completion
        return completions

    def _first_incomplete(self, state: Mapping[str, Any]) -> int | None:
        for prompt in PROMPTS:
            if state["stages"][str(prompt)].get("status") != "COMPLETE":
                return prompt
        return None

    def _admit_stage(
        self,
        state: dict[str, Any],
        adapter: StageAdapter,
        predecessor: ValidatedCompletion | None,
    ) -> None:
        prompt = adapter.prompt_index
        self._storage_preflight(state, adapter, predecessor)
        elapsed = self._program_elapsed_seconds(state)
        remaining = max(0.0, TOTAL_BUDGET_HOURS * 3600 - elapsed)
        overrun = max(0.0, elapsed - TOTAL_BUDGET_HOURS * 3600)
        stage = state["stages"][str(prompt)]
        if stage.get("status") not in {"RUNNING", "STOPPING", "VALIDATING"}:
            stage["status"] = "ADMITTED"
        stage["adapter_id"] = adapter.adapter_id
        stage["adapter_contract_sha256"] = adapter.contract_sha256
        stage["expected_duration_hours"] = adapter.expected_duration_hours
        stage["admitted_at_utc"] = stage.get("admitted_at_utc") or utc_now()
        stage["detail"] = (
            "C:-only storage and predecessor gates passed; elapsed-time targets are advisory"
        )
        state["current_prompt_index"] = prompt
        state["status"] = "RUNNING"
        self._notify(
            state,
            event_id=f"prompt-{prompt}-admitted:{adapter.contract_sha256}",
            event_type="STAGE_ADMITTED",
            prompt_index=prompt,
            adapter_id=adapter.adapter_id,
            adapter_contract_sha256=adapter.contract_sha256,
            advisory_target_remaining_hours=round(remaining / 3600, 6),
            advisory_target_overrun_hours=round(overrun / 3600, 6),
            time_target_policy=TIME_TARGET_POLICY,
        )
        self._write_state(state)

    def _storage_preflight(
        self,
        state: dict[str, Any],
        adapter: StageAdapter,
        predecessor: ValidatedCompletion | None,
    ) -> None:
        free = self.free_bytes_provider(self.config.evaluation_tool_root)
        rows: list[dict[str, Any]] = [
            {
                "class": "controller_input",
                "declared_path": str(path),
                "resolved_path": str(
                    resolve_c_only_path(path, must_exist=True, label=label)
                ),
                "exists": True,
                "sha256": file_sha256(path),
            }
            for path, label in (
                (self.config.path, "adapter configuration"),
                (self.config.amendment_path, "scope amendment"),
            )
        ]
        if predecessor is not None:
            resolved_predecessor = resolve_c_only_path(
                predecessor.path,
                must_exist=True,
                label=f"Prompt {adapter.prompt_index} predecessor completion",
            )
            predecessor_hash = file_sha256(resolved_predecessor)
            if predecessor_hash != predecessor.sha256:
                raise ProgramContractError(
                    f"Prompt {adapter.prompt_index} predecessor changed before admission"
                )
            rows.append(
                {
                    "class": "predecessor_completion_input",
                    "declared_path": str(predecessor.path),
                    "resolved_path": str(resolved_predecessor),
                    "exists": True,
                    "sha256": predecessor_hash,
                    "completion_marker": predecessor.marker,
                }
            )
        for path_class, paths in adapter.material_paths.items():
            for path in paths:
                resolved = resolve_c_only_path(
                    path,
                    must_exist=path_class == "inputs",
                    label=f"Prompt {adapter.prompt_index} {path_class}",
                )
                rows.append(
                    {
                        "class": path_class,
                        "declared_path": str(path),
                        "resolved_path": str(resolved),
                        "exists": resolved.exists(),
                    }
                )
        preflight = {
            "schema_version": "full-pipeline-eight-day-preflight.v1",
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "prompt_index": adapter.prompt_index,
            "status": "PASS" if free >= MINIMUM_FREE_GIB * GIB else "FAIL",
            "checked_at_utc": utc_now(),
            "allowed_drive": "C:\\",
            "free_bytes": free,
            "free_gib": free / GIB,
            "minimum_reserve_gib": MINIMUM_FREE_GIB,
            "material_paths": rows,
        }
        preflight_path = self.preflight_root / (
            f"prompt_{adapter.prompt_index}_{utc_now().replace(':', '').replace('-', '')}.json"
        )
        atomic_write_json(preflight_path, preflight)
        state["stages"][str(adapter.prompt_index)]["latest_preflight"] = str(preflight_path)
        if preflight["status"] != "PASS":
            raise ProgramContractError(
                f"BLOCKED_C_DRIVE_RESERVE_35_GIB: C: has {free / GIB:.2f} GiB free"
            )

    def _validate_existing_completion(
        self,
        state: dict[str, Any],
        adapter: StageAdapter,
        predecessor: ValidatedCompletion | None,
    ) -> ValidatedCompletion:
        stage = state["stages"][str(adapter.prompt_index)]
        stage["status"] = "VALIDATING"
        stage["detail"] = "Validating an existing exact completion record"
        self._write_state(state)
        exit_code = self._run_command(
            adapter.validate_command,
            adapter=adapter,
            predecessor=predecessor,
            log_prefix="validate-existing",
        )
        if exit_code != 0:
            raise ProgramContractError(
                f"Prompt {adapter.prompt_index} validator exited {exit_code}"
            )
        return validate_stage_completion(adapter=adapter, predecessor=predecessor)

    def _execute_or_recover_stage(
        self,
        state: dict[str, Any],
        adapter: StageAdapter,
        predecessor: ValidatedCompletion | None,
    ) -> ValidatedCompletion:
        stage = state["stages"][str(adapter.prompt_index)]
        child_pid = int(stage.get("child_pid", 0) or 0)
        stop_request = self._unprocessed_stop_request(state)
        if not child_pid and stop_request is not None:
            stage["status"] = "STOPPED"
            stage["detail"] = "Stop request honored before an adapter process started"
            state["status"] = "STOPPED"
            state["processed_stop_request_id"] = stop_request.get("request_id")
            self._notify(
                state,
                event_id=f"stop-result:{stop_request.get('request_id')}:PRESTART",
                event_type="GRACEFUL_STOP_RESULT",
                prompt_index=adapter.prompt_index,
                status="STOPPED_BEFORE_START",
                reason=stop_request.get("reason"),
            )
            self._write_state(state)
            raise ProgramStopped(str(stop_request.get("reason")))
        recovered = int(stage.get("attempts", 0)) > 0 or stage.get("status") in {
            "RUNNING",
            "STOPPING",
            "STOP_TIMEOUT",
            "STOPPED",
        }
        process: subprocess.Popen[bytes] | None = None
        if recovered and child_pid and self.pid_alive(child_pid):
            stage["detail"] = f"Recovered monitoring of live adapter PID {child_pid}"
            self._notify(
                state,
                event_id=f"prompt-{adapter.prompt_index}-reattached:{child_pid}",
                event_type="STAGE_PROCESS_REATTACHED",
                prompt_index=adapter.prompt_index,
                child_pid=child_pid,
            )
            self._write_state(state)
        else:
            if recovered:
                command = (
                    adapter.resume_command
                    if adapter.restart_policy == "RESUME_COMMAND"
                    else adapter.start_command
                )
            else:
                command = adapter.start_command
            process = self._spawn_command(
                command, adapter=adapter, predecessor=predecessor
            )
            child_pid = process.pid
            stage["attempts"] = int(stage.get("attempts", 0)) + 1
            stage["status"] = "RUNNING"
            stage["child_pid"] = child_pid
            stage["started_at_utc"] = stage.get("started_at_utc") or utc_now()
            stage["attempt_started_at_utc"] = utc_now()
            stage["detail"] = f"Adapter PID {child_pid} is running"
            self._notify(
                state,
                event_id=(
                    f"prompt-{adapter.prompt_index}-started:"
                    f"{adapter.contract_sha256}:attempt-{stage['attempts']}"
                ),
                event_type="STAGE_STARTED",
                prompt_index=adapter.prompt_index,
                child_pid=child_pid,
                attempt=stage["attempts"],
            )
            self._write_state(state)

        last_console = 0.0
        while True:
            alive = process.poll() is None if process is not None else self.pid_alive(child_pid)
            if not alive:
                break
            self.lock.heartbeat(child_pid=child_pid)
            stop_request = self._unprocessed_stop_request(state)
            if stop_request is not None:
                self._graceful_stop(
                    state, adapter, predecessor, child_pid, process, stop_request
                )
                raise ProgramStopped(stop_request.get("reason", "stop requested"))
            free = self.free_bytes_provider(self.config.evaluation_tool_root)
            if free < MINIMUM_FREE_GIB * GIB:
                synthetic_stop = {
                    "request_id": f"storage-{uuid4().hex}",
                    "reason": "BLOCKED_C_DRIVE_RESERVE_35_GIB",
                }
                self._graceful_stop(
                    state, adapter, predecessor, child_pid, process, synthetic_stop
                )
                self._block(
                    state,
                    marker="BLOCKED_C_DRIVE_RESERVE_35_GIB",
                    detail=f"C: free space fell to {free / GIB:.2f} GiB",
                    prompt=adapter.prompt_index,
                )
                raise ProgramStopped("storage reserve")
            now = self.monotonic()
            if now - last_console >= max(10.0, self.config.poll_interval_seconds):
                percentage, eta, detail = self._adapter_progress(adapter, stage)
                stage["last_observed_percentage"] = percentage
                stage["last_observed_eta_seconds"] = eta
                if detail:
                    stage["detail"] = detail
                self._write_state(state)
                print(
                    f"Prompt {adapter.prompt_index} {_bar(percentage)} "
                    f"ETA {_duration(eta)} C-free {free / GIB:.1f} GiB",
                    flush=True,
                )
                last_console = now
            self.sleeper(self.config.poll_interval_seconds)

        exit_code = process.returncode if process is not None else None
        stage["child_pid"] = None
        stage["adapter_exit_code"] = exit_code
        if exit_code not in (None, 0):
            stage["status"] = "FAILED"
            stage["detail"] = f"Adapter process exited {exit_code}"
            self._write_state(state)
            raise ProgramContractError(stage["detail"])

        stage["status"] = "VALIDATING"
        stage["detail"] = "Adapter ended; running independent completion validator"
        self._write_state(state)
        validator_exit = self._run_command(
            adapter.validate_command,
            adapter=adapter,
            predecessor=predecessor,
            log_prefix="validate",
        )
        stage["validator_exit_code"] = validator_exit
        if validator_exit != 0:
            stage["status"] = "FAILED"
            stage["detail"] = f"Validator exited {validator_exit}"
            self._write_state(state)
            raise ProgramContractError(stage["detail"])
        return validate_stage_completion(adapter=adapter, predecessor=predecessor)

    def _spawn_command(
        self,
        command: tuple[str, ...],
        *,
        adapter: StageAdapter,
        predecessor: ValidatedCompletion | None,
    ) -> subprocess.Popen[bytes]:
        assert adapter.cwd is not None and adapter.controller_log is not None
        adapter.cwd.mkdir(parents=True, exist_ok=True)
        adapter.controller_log.parent.mkdir(parents=True, exist_ok=True)
        environment = adapter_environment(
            config=self.config, adapter=adapter, predecessor=predecessor
        )
        command = materialize_command(
            command=command, adapter=adapter, predecessor=predecessor
        )
        log_handle = adapter.controller_log.open("ab")
        try:
            process = subprocess.Popen(
                list(command),
                cwd=str(adapter.cwd),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
            )
        except Exception:
            log_handle.close()
            raise
        # Popen duplicates the OS handle. Closing the parent copy prevents a long-lived
        # controller descriptor leak while preserving child logging.
        log_handle.close()
        return process

    def _run_command(
        self,
        command: tuple[str, ...],
        *,
        adapter: StageAdapter,
        predecessor: ValidatedCompletion | None,
        log_prefix: str,
        timeout: float | None = None,
    ) -> int:
        assert adapter.cwd is not None and adapter.controller_log is not None
        environment = adapter_environment(
            config=self.config, adapter=adapter, predecessor=predecessor
        )
        command = materialize_command(
            command=command, adapter=adapter, predecessor=predecessor
        )
        adapter.controller_log.parent.mkdir(parents=True, exist_ok=True)
        with adapter.controller_log.open("ab") as log_handle:
            log_handle.write(
                f"\n[{utc_now()}] {log_prefix}: {json.dumps(command)}\n".encode("utf-8")
            )
            log_handle.flush()
            completed = subprocess.run(
                list(command),
                cwd=str(adapter.cwd),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
                timeout=timeout,
                check=False,
            )
        return int(completed.returncode)

    def _graceful_stop(
        self,
        state: dict[str, Any],
        adapter: StageAdapter,
        predecessor: ValidatedCompletion | None,
        child_pid: int,
        process: subprocess.Popen[bytes] | None,
        request: Mapping[str, Any],
    ) -> None:
        stage = state["stages"][str(adapter.prompt_index)]
        stage["status"] = "STOPPING"
        stage["detail"] = f"Graceful stop requested: {request.get('reason')}"
        state["status"] = "STOPPING"
        self._write_state(state)
        self._notify(
            state,
            event_id=f"stop:{request.get('request_id')}",
            event_type="GRACEFUL_STOP_REQUESTED",
            prompt_index=adapter.prompt_index,
            reason=request.get("reason"),
            child_pid=child_pid,
        )
        try:
            stop_exit = self._run_command(
                adapter.stop_command,
                adapter=adapter,
                predecessor=predecessor,
                log_prefix="stop",
                timeout=float(adapter.stop_grace_seconds),
            )
        except subprocess.TimeoutExpired:
            stop_exit = 124
        deadline = self.monotonic() + adapter.stop_grace_seconds
        while self.monotonic() < deadline:
            alive = process.poll() is None if process is not None else self.pid_alive(child_pid)
            if not alive:
                break
            self.lock.heartbeat(child_pid=child_pid)
            self.sleeper(min(self.config.poll_interval_seconds, 2.0))
        alive = process.poll() is None if process is not None else self.pid_alive(child_pid)
        stage["stop_command_exit_code"] = stop_exit
        stage["child_pid"] = child_pid if alive else None
        stage["status"] = "STOP_TIMEOUT" if alive else "STOPPED"
        stage["detail"] = (
            f"Adapter PID {child_pid} did not stop inside {adapter.stop_grace_seconds}s; "
            "no forced termination was performed"
            if alive
            else "Adapter stopped gracefully; results and restart state were preserved"
        )
        state["processed_stop_request_id"] = request.get("request_id")
        state["status"] = stage["status"]
        self._write_state(state)
        self._notify(
            state,
            event_id=f"stop-result:{request.get('request_id')}:{stage['status']}",
            event_type="GRACEFUL_STOP_RESULT",
            prompt_index=adapter.prompt_index,
            status=stage["status"],
            child_pid=stage["child_pid"],
            stop_command_exit_code=stop_exit,
        )

    def _unprocessed_stop_request(
        self, state: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        if not self.stop_request_path.exists():
            return None
        request = load_json(self.stop_request_path)
        if request.get("request_id") == state.get("processed_stop_request_id"):
            return None
        return request

    def _record_stage_completion(
        self,
        state: dict[str, Any],
        adapter: StageAdapter,
        completion: ValidatedCompletion,
    ) -> None:
        prompt = adapter.prompt_index
        # The completion notification is fsync'd before the state permits transition.
        self._notify(
            state,
            event_id=f"prompt-{prompt}-complete:{completion.sha256}",
            event_type="STAGE_COMPLETED_AND_VALIDATED",
            prompt_index=prompt,
            completion_marker=completion.marker,
            completion_record_path=str(completion.path),
            completion_record_sha256=completion.sha256,
            artifact_manifest_path=str(completion.artifact_manifest_path),
            artifact_manifest_sha256=completion.artifact_manifest_sha256,
            artifact_count=completion.artifact_count,
            hash_validation="PASS",
            firewall_validation="PASS",
            prerequisite_validation="PASS",
        )
        stage = state["stages"][str(prompt)]
        completed_at = utc_now()
        start_raw = stage.get("started_at_utc") or stage.get("admitted_at_utc")
        elapsed_seconds = None
        if start_raw:
            elapsed_seconds = max(
                0.0,
                (parse_utc(completed_at) - parse_utc(str(start_raw))).total_seconds(),
            )
        nominal_seconds = STAGE_BUDGET_HOURS[prompt] * 3600
        contingency_seconds = (
            max(0.0, elapsed_seconds - nominal_seconds)
            if elapsed_seconds is not None
            else None
        )
        stage.update(
            {
                "status": "COMPLETE",
                "detail": "Exact amended completion and all independent gates validated",
                "completed_at_utc": completed_at,
                "elapsed_seconds": elapsed_seconds,
                "nominal_budget_consumed_seconds": (
                    min(elapsed_seconds, nominal_seconds)
                    if elapsed_seconds is not None
                    else None
                ),
                "contingency_consumed_seconds": contingency_seconds,
                "child_pid": None,
                "completion_marker": completion.marker,
                "completion_record_path": str(completion.path),
                "completion_record_sha256": completion.sha256,
                "artifact_manifest_sha256": completion.artifact_manifest_sha256,
            }
        )
        state["status"] = "STAGE_COMPLETE"
        self._write_state(state)

    def _finish_program(
        self, state: dict[str, Any], completion: ValidatedCompletion
    ) -> None:
        state["status"] = COMPLETION_MARKERS[8]
        state["current_prompt_index"] = None
        state["completed_at_utc"] = utc_now()
        self._notify(
            state,
            event_id=f"program-complete:{completion.sha256}",
            event_type="PROGRAM_COMPLETED_AND_VALIDATED",
            prompt_index=8,
            completion_marker=COMPLETION_MARKERS[8],
            completion_record_sha256=completion.sha256,
            elapsed_hours=round(self._program_elapsed_seconds(state) / 3600, 6),
        )
        self._write_state(state)

    def _mark_not_ready(self, state: dict[str, Any], adapter: StageAdapter) -> None:
        prompt = adapter.prompt_index
        stage = state["stages"][str(prompt)]
        stage["status"] = "NOT_READY"
        stage["detail"] = adapter.not_ready_reason
        state["status"] = "NOT_READY"
        state["current_prompt_index"] = prompt
        self._notify(
            state,
            event_id=f"prompt-{prompt}-not-ready:{adapter.contract_sha256}",
            event_type="STAGE_NOT_READY",
            prompt_index=prompt,
            adapter_id=adapter.adapter_id,
            reason=adapter.not_ready_reason,
        )
        self._write_state(state)

    def _block(
        self,
        state: dict[str, Any],
        *,
        marker: str,
        detail: str,
        prompt: object,
    ) -> str:
        state["status"] = marker
        state["blocked_detail"] = detail
        if isinstance(prompt, int) and str(prompt) in state.get("stages", {}):
            state["stages"][str(prompt)]["status"] = marker
            state["stages"][str(prompt)]["detail"] = detail
        self._notify(
            state,
            event_id=f"blocked:{marker}:{prompt}:{file_sha256(self.config.amendment_path)}",
            event_type="PROGRAM_BLOCKED",
            prompt_index=prompt,
            marker=marker,
            detail=detail,
        )
        self._write_state(state)
        return marker

    def _write_state(self, state: dict[str, Any]) -> None:
        state["updated_at_utc"] = utc_now()
        atomic_write_json(self.state_path, state)

    def _notify(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        event_type: str,
        **fields: Any,
    ) -> None:
        if self.notifications is None:
            self.notifications = DurableNotifications(self.notification_path)
        self.notifications.write(
            event_id=event_id,
            event_type=event_type,
            fields={
                "scope_id": SCOPE_ID,
                "scope_class": SCOPE_CLASS,
                "original_full_scope_complete": False,
                "program_status": state.get("status"),
                **fields,
            },
        )

    def _program_elapsed_seconds(self, state: Mapping[str, Any]) -> float:
        started = parse_utc(str(state["program_started_at_utc"]))
        return max(0.0, (datetime.now(timezone.utc) - started).total_seconds())

    def _adapter_progress(
        self, adapter: StageAdapter, stage: Mapping[str, Any]
    ) -> tuple[float, float | None, str | None]:
        if adapter.progress_record and adapter.progress_record.exists():
            try:
                progress = load_json(adapter.progress_record)
                percentage = float(
                    progress.get("overall_percentage", progress.get("percentage", 0.0))
                )
                eta_raw = progress.get("eta_seconds", progress.get("eta_sec"))
                eta = float(eta_raw) if eta_raw is not None else None
                detail = progress.get("detail") or progress.get("latest_activity")
                return max(0.0, min(100.0, percentage)), eta, str(detail) if detail else None
            except (ProgramContractError, TypeError, ValueError):
                pass
        started_raw = stage.get("started_at_utc")
        if started_raw:
            elapsed = max(
                0.0,
                (datetime.now(timezone.utc) - parse_utc(str(started_raw))).total_seconds(),
            )
            planned = adapter.expected_duration_hours * 3600
            percentage = min(99.0, 100.0 * elapsed / planned)
            return percentage, max(0.0, planned - elapsed), None
        return 0.0, adapter.expected_duration_hours * 3600, None


def _bar(percentage: float, width: int = 24) -> str:
    bounded = max(0.0, min(100.0, percentage))
    filled = round(width * bounded / 100.0)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {bounded:5.1f}%"


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "calculating"
    total = max(0, int(seconds))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
