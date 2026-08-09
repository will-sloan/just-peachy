from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys
import threading
import time

import pytest

from app.artifact_contracts.atomic import file_sha256
from app.artifact_contracts.completion import validate_scenario_completion
from app.benchmark_contracts.scenario import finalize_scenario
from app.cli.main import build_parser
from app.campaign_executor.executor import CampaignExecutor
from app.campaign_executor.planner import plan_campaign, validate_campaign
from app.campaign_executor.state import (
    CampaignStateError,
    CampaignStateStore,
    ExecutionLease,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = TOOL_ROOT.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage2"


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


def _scenario(
    *,
    repetition: int = 1,
    max_retries: int = 0,
    timeout_seconds: float = 30.0,
    oom_retry: bool = False,
) -> dict[str, object]:
    value = json.loads(
        (FIXTURES / "golden_scenario_source.json").read_text(encoding="utf-8")
    )
    identity = json.loads(
        (FIXTURES / "golden_manifest_identity.json").read_text(encoding="utf-8")
    )
    value["benchmark_manifest"] = {**identity, "path": "golden_manifest.parquet"}
    value["repetition"] = repetition
    value["timeout_policy"] = {
        "timeout_seconds": timeout_seconds,
        "on_timeout": "fail_scenario",
    }
    value["failure_policy"] = {
        **value["failure_policy"],
        "max_scenario_retries": max_retries,
    }
    if oom_retry:
        value["failure_policy"]["oom_retry"] = {
            "enabled": True,
            "safe_retry_action": "restart_process",
        }
    result = finalize_scenario(value)
    result["artifact_contract"] = {
        "schema_version": "scenario-artifact-requirements.v1",
        "scenario_type": "synthetic_executor",
        "capabilities": [],
    }
    return result


def _plan(
    tmp_path: Path,
    scenarios: list[dict[str, object]],
    *,
    campaign_id: str = "campaign_stage4test",
) -> tuple[Path, CampaignStateStore]:
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir(parents=True)
    shutil.copy2(
        FIXTURES / "golden_manifest.parquet",
        catalog_root / "golden_manifest.parquet",
    )
    catalog = catalog_root / "resolved_scenarios.jsonl"
    catalog.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in scenarios),
        encoding="utf-8",
    )
    plan = plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=tmp_path / "automated_runs",
        campaign_id=campaign_id,
    )
    state = CampaignStateStore(plan.campaign_root / "database" / "campaign.sqlite")
    return plan.campaign_root, state


def _builder(behaviors: dict[str, list[str]]):
    def build(lease: ExecutionLease, scenario_root: Path) -> list[str]:
        choices = behaviors[lease.scenario_id]
        behavior = choices[min(lease.attempt_number - 1, len(choices) - 1)]
        command = [
            sys.executable,
            "-u",
            "-m",
            "app.campaign_executor.synthetic_worker",
            "--scenario-root",
            str(scenario_root),
            "--behavior",
            behavior,
        ]
        if behavior == "sleep":
            command.extend(["--sleep-seconds", "30"])
        return command

    return build


def _executor(
    campaign_root: Path,
    behaviors: dict[str, list[str]],
    *,
    worker_id: str = "worker-test",
    minimum_free_disk_bytes: int = 0,
) -> CampaignExecutor:
    return CampaignExecutor(
        campaign_root,
        project_root=PROJECT_ROOT,
        worker_id=worker_id,
        command_builder=_builder(behaviors),
        lease_seconds=2.0,
        heartbeat_seconds=0.2,
        stop_poll_seconds=0.02,
        terminate_grace_seconds=0.2,
        minimum_free_disk_bytes=minimum_free_disk_bytes,
    )


def _wait_for_state(
    state: CampaignStateStore,
    campaign_id: str,
    scenario_id: str,
    expected: str,
    timeout: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if state.scenario(campaign_id, scenario_id).state == expected:
            return
        time.sleep(0.02)
    raise AssertionError(
        f"scenario did not reach {expected}: {state.scenario(campaign_id, scenario_id)}"
    )


def test_plan_is_deterministic_and_dry_run_writes_nothing(tmp_path: Path) -> None:
    scenarios = [_scenario(repetition=2), _scenario(repetition=1)]
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir()
    shutil.copy2(FIXTURES / "golden_manifest.parquet", catalog_root / "golden_manifest.parquet")
    catalog = catalog_root / "resolved_scenarios.jsonl"
    catalog.write_text(
        "".join(json.dumps(item) + "\n" for item in reversed(scenarios)),
        encoding="utf-8",
    )
    plan = plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=tmp_path / "automated_runs",
        dry_run=True,
    )
    assert plan.scenario_ids == tuple(sorted(item["scenario_id"] for item in scenarios))
    assert not plan.campaign_root.exists()


def test_campaign_plan_and_database_validate(tmp_path: Path) -> None:
    root, state = _plan(tmp_path, [_scenario()])
    validation = validate_campaign(root)
    assert validation["valid"] is True
    assert validation["scenario_count"] == 1
    assert state.summary("campaign_stage4test")["state_counts"] == {"pending": 1}
    assert (root / "campaign_manifest.sha256").is_file()


def test_competing_workers_cannot_acquire_the_same_lease(tmp_path: Path) -> None:
    root, _state = _plan(tmp_path, [_scenario()])
    first = CampaignStateStore(root / "database" / "campaign.sqlite")
    second = CampaignStateStore(root / "database" / "campaign.sqlite")
    lease = first.acquire_next(
        "campaign_stage4test",
        worker_id="worker-a",
        hostname="host-a",
        lease_seconds=10,
    )
    assert lease is not None
    assert (
        second.acquire_next(
            "campaign_stage4test",
            worker_id="worker-b",
            hostname="host-b",
            lease_seconds=10,
        )
        is None
    )


def test_heartbeat_extends_lease_and_stale_lease_recovers(tmp_path: Path) -> None:
    root, _state = _plan(tmp_path, [_scenario()])
    clock = MutableClock()
    state = CampaignStateStore(root / "database" / "campaign.sqlite", clock=clock)
    lease = state.acquire_next(
        "campaign_stage4test",
        worker_id="worker-a",
        hostname="host-a",
        lease_seconds=1,
    )
    assert lease is not None
    state.mark_running(lease)
    clock.advance(0.75)
    state.heartbeat(lease, lease_seconds=2)
    clock.advance(1)
    assert state.recover_stale_leases("campaign_stage4test") == ()
    clock.advance(2)
    assert state.recover_stale_leases("campaign_stage4test") == (lease.scenario_id,)
    recovered = state.scenario("campaign_stage4test", lease.scenario_id)
    assert recovered.state == "interrupted"
    assert recovered.retry_eligible is True


def test_invalid_lease_owner_cannot_transition_state(tmp_path: Path) -> None:
    root, state = _plan(tmp_path, [_scenario()])
    lease = state.acquire_next(
        "campaign_stage4test",
        worker_id="worker-a",
        hostname="host-a",
        lease_seconds=10,
    )
    assert lease is not None
    forged = ExecutionLease(**{**lease.__dict__, "owner": "other@host"})
    with pytest.raises(CampaignStateError, match="no longer owned"):
        state.mark_running(forged)


def test_scenario_id_cannot_be_rebound_to_changed_hash(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    _ = root
    with pytest.raises(CampaignStateError, match="another hash"):
        state.register_scenarios(
            "campaign_stage4test",
            [
                {
                    "scenario_id": scenario["scenario_id"],
                    "scenario_hash": "F" * 64,
                    "max_attempts": 1,
                    "expected_artifacts": [],
                }
            ],
        )


def test_changed_result_parameter_with_old_identity_is_rejected(tmp_path: Path) -> None:
    scenario = _scenario()
    changed = deepcopy(scenario)
    changed["repetition"] = 2
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir()
    shutil.copy2(FIXTURES / "golden_manifest.parquet", catalog_root / "golden_manifest.parquet")
    catalog = catalog_root / "resolved_scenarios.jsonl"
    catalog.write_text(json.dumps(changed) + "\n", encoding="utf-8")
    with pytest.raises(Exception, match="scenario ID/hash"):
        plan_campaign(
            scenario_catalog=catalog,
            automated_runs_root=tmp_path / "automated_runs",
            campaign_id="campaign_changedhash",
        )


def test_success_is_validated_and_skipped_without_overwrite(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    executor = _executor(root, {scenario["scenario_id"]: ["success"]})
    first = executor.run()
    assert first.succeeded == 1
    scenario_root = root / "scenarios" / str(scenario["scenario_id"])
    assert validate_scenario_completion(scenario_root).complete
    checksum = file_sha256(scenario_root / "predictions" / "diagnostics.jsonl")
    attempts = state.scenario("campaign_stage4test", str(scenario["scenario_id"])).attempt_count

    second = executor.run()
    assert second.attempted == 0
    assert second.skipped_complete == 1
    assert file_sha256(scenario_root / "predictions" / "diagnostics.jsonl") == checksum
    assert state.scenario("campaign_stage4test", str(scenario["scenario_id"])).attempt_count == attempts


@pytest.mark.parametrize("behavior,expected", [("corrupt", "corrupt"), ("incomplete", "incomplete")])
def test_zero_exit_with_bad_artifacts_is_invalid(
    tmp_path: Path,
    behavior: str,
    expected: str,
) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    result = _executor(root, {scenario["scenario_id"]: [behavior]}).run()
    record = state.scenario("campaign_stage4test", str(scenario["scenario_id"]))
    assert result.failed == 1
    assert record.state == "invalid"
    assert record.output_completeness == expected


def test_corrupted_previous_success_does_not_skip_or_overwrite(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    executor = _executor(root, {scenario["scenario_id"]: ["success"]})
    executor.run()
    scenario_root = root / "scenarios" / str(scenario["scenario_id"])
    summary = scenario_root / "metrics" / "summary.json"
    summary.write_text("{corrupt", encoding="utf-8")
    result = executor.run()
    record = state.scenario("campaign_stage4test", str(scenario["scenario_id"]))
    assert result.attempted == 0
    assert record.state == "invalid"
    assert summary.read_text(encoding="utf-8") == "{corrupt"


def test_transient_failure_retries_and_preserves_partial_results(tmp_path: Path) -> None:
    scenario = _scenario(max_retries=1)
    root, state = _plan(tmp_path, [scenario])
    result = _executor(
        root,
        {scenario["scenario_id"]: ["partial-transient", "success"]},
    ).run()
    record = state.scenario("campaign_stage4test", str(scenario["scenario_id"]))
    archive = (
        root
        / "audit"
        / "partial_results"
        / str(scenario["scenario_id"])
        / "attempt_0001"
        / "metrics"
        / "summary.json"
    )
    assert result.attempted == 2
    assert result.succeeded == 1
    assert record.state == "succeeded"
    assert record.attempt_count == 2
    assert archive.is_file()


def test_terminal_failure_does_not_stop_unrelated_scenario(tmp_path: Path) -> None:
    first = _scenario(repetition=1)
    second = _scenario(repetition=2)
    root, state = _plan(tmp_path, [first, second])
    ordered = sorted((first["scenario_id"], second["scenario_id"]))
    behaviors = {ordered[0]: ["terminal"], ordered[1]: ["success"]}
    result = _executor(root, behaviors).run()
    states = {item.scenario_id: item.state for item in state.scenarios("campaign_stage4test")}
    assert result.attempted == 2
    assert states[ordered[0]] == "failed_terminal"
    assert states[ordered[1]] == "succeeded"


def test_oom_retries_only_with_explicit_safe_action(tmp_path: Path) -> None:
    blocked = _scenario(repetition=1, max_retries=1, oom_retry=False)
    safe = _scenario(repetition=2, max_retries=1, oom_retry=True)
    root, state = _plan(tmp_path, [blocked, safe])
    result = _executor(
        root,
        {
            blocked["scenario_id"]: ["oom", "success"],
            safe["scenario_id"]: ["oom", "success"],
        },
    ).run()
    blocked_state = state.scenario("campaign_stage4test", str(blocked["scenario_id"]))
    safe_state = state.scenario("campaign_stage4test", str(safe["scenario_id"]))
    assert result.attempted == 3
    assert blocked_state.state == "out_of_memory"
    assert blocked_state.retry_eligible is False
    assert blocked_state.attempt_count == 1
    assert safe_state.state == "succeeded"
    assert safe_state.attempt_count == 2


def test_timeout_terminates_subprocess(tmp_path: Path) -> None:
    scenario = _scenario(timeout_seconds=0.2)
    root, state = _plan(tmp_path, [scenario])
    result = _executor(root, {scenario["scenario_id"]: ["sleep"]}).run()
    record = state.scenario("campaign_stage4test", str(scenario["scenario_id"]))
    assert result.failed == 1
    assert record.state == "timeout"
    assert record.exception_category == "timeout"


def test_stop_request_terminates_only_selected_scenario(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    executor = _executor(root, {scenario["scenario_id"]: ["sleep"]})
    thread = threading.Thread(target=executor.run, daemon=True)
    thread.start()
    _wait_for_state(
        state,
        "campaign_stage4test",
        str(scenario["scenario_id"]),
        "running",
    )
    state.request_stop(
        "campaign_stage4test",
        scenario_id=str(scenario["scenario_id"]),
        reason="test stop",
    )
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert state.scenario("campaign_stage4test", str(scenario["scenario_id"])).state == "stopped"


def test_interruption_is_restart_safe_and_resumable(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    first = _executor(root, {scenario["scenario_id"]: ["sleep"]}, worker_id="worker-a")
    thread = threading.Thread(target=first.run, daemon=True)
    thread.start()
    _wait_for_state(
        state,
        "campaign_stage4test",
        str(scenario["scenario_id"]),
        "running",
    )
    first.request_interrupt()
    thread.join(timeout=5)
    interrupted = state.scenario("campaign_stage4test", str(scenario["scenario_id"]))
    assert interrupted.state == "interrupted"
    assert interrupted.retry_eligible is True

    resumed = _executor(
        root,
        {scenario["scenario_id"]: ["success"]},
        worker_id="worker-b",
    ).run()
    final = state.scenario("campaign_stage4test", str(scenario["scenario_id"]))
    assert resumed.succeeded == 1
    assert final.state == "succeeded"
    assert final.attempt_count == 2


def test_process_restart_recovers_expired_running_lease(tmp_path: Path) -> None:
    scenario = _scenario()
    root, _state = _plan(tmp_path, [scenario])
    old_clock = MutableClock()
    old_clock.value = datetime(2020, 1, 1, tzinfo=timezone.utc)
    crashed = CampaignStateStore(root / "database" / "campaign.sqlite", clock=old_clock)
    lease = crashed.acquire_next(
        "campaign_stage4test",
        worker_id="crashed",
        hostname="old-host",
        lease_seconds=1,
    )
    assert lease is not None
    crashed.mark_running(lease)

    resumed = _executor(root, {scenario["scenario_id"]: ["success"]}).run()
    final = CampaignStateStore(root / "database" / "campaign.sqlite").scenario(
        "campaign_stage4test", str(scenario["scenario_id"])
    )
    assert resumed.recovered_stale == 1
    assert resumed.succeeded == 1
    assert final.state == "succeeded"


def test_disk_space_refusal_does_not_launch_child(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    executor = _executor(
        root,
        {scenario["scenario_id"]: ["success"]},
        minimum_free_disk_bytes=2**63 - 1,
    )
    result = executor.run()
    record = state.scenario("campaign_stage4test", str(scenario["scenario_id"]))
    assert result.failed == 1
    assert record.state == "failed_terminal"
    assert record.exception_category == "disk_space"
    assert not (root / "scenarios" / str(scenario["scenario_id"]) / "predictions" / "diagnostics.jsonl").exists()


def test_machine_readable_events_and_attempt_history_persist(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    _executor(root, {scenario["scenario_id"]: ["success"]}).run()
    events = state.events(
        "campaign_stage4test", scenario_id=str(scenario["scenario_id"])
    )
    event_types = {str(item["event_type"]) for item in events}
    assert {"lease_acquired", "scenario_started", "scenario_finalized"}.issubset(event_types)
    event_log = root / "scenarios" / str(scenario["scenario_id"]) / "logs" / "events.jsonl"
    rows = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert all(row["scenario_id"] == scenario["scenario_id"] for row in rows)
    assert validate_scenario_completion(
        root / "scenarios" / str(scenario["scenario_id"])
    ).complete


def test_campaign_stop_request_prevents_new_leases(tmp_path: Path) -> None:
    scenario = _scenario()
    root, state = _plan(tmp_path, [scenario])
    _ = root
    state.request_stop("campaign_stage4test", reason="campaign maintenance")
    assert (
        state.acquire_next(
            "campaign_stage4test",
            worker_id="worker-a",
            hostname="host-a",
            lease_seconds=10,
        )
        is None
    )
    summary = state.summary("campaign_stage4test")
    assert summary["stop_requested"] is True
    assert summary["stop_reason"] == "campaign maintenance"


def test_campaign_cli_exposes_all_stage4_actions_without_changing_existing_run() -> None:
    parser = build_parser()
    action_names = (
        "plan",
        "validate",
        "list",
        "run",
        "resume",
        "status",
        "stop",
        "retry",
        "validate-artifacts",
    )
    for action in action_names:
        required = ["campaign", action]
        if action == "plan":
            required.append("--dry-run")
        elif action in {"validate", "list", "status", "stop", "retry", "validate-artifacts"}:
            required.extend(["--campaign-root", "campaign_fixture"])
        else:
            required.extend(
                [
                    "--campaign-root",
                    "campaign_fixture",
                    "--worker-id",
                    "worker-a",
                ]
            )
        parsed = parser.parse_args(required)
        assert parsed.campaign_action == action
        assert callable(parsed.func)

    ordinary = parser.parse_args(["run", "--dataset", "cmu_arctic"])
    assert ordinary.command == "run"
    assert ordinary.runner == "simulation"
