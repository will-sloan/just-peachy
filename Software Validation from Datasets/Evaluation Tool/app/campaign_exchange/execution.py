"""Run only the globally identified scenarios in one validated worker assignment."""

from __future__ import annotations

from pathlib import Path

from app.campaign_executor.executor import CampaignExecutor, ExecutorResult
from app.campaign_executor.planner import validate_campaign
from app.campaign_executor.state import CampaignStateStore

from .assignments import current_git_commit, validate_worker_assignment
from .common import CampaignExchangeError, atomic_copy_tree, read_json_mapping, read_yaml_mapping


def prepare_worker_campaign_copy(
    campaign_root: Path,
    assignment_path: Path,
    destination: Path,
) -> dict[str, object]:
    """Make a one-time independent local copy of an entirely pending campaign."""

    source = campaign_root.resolve()
    target = destination.resolve()
    validate_campaign(source)
    assignment = read_yaml_mapping(assignment_path.resolve())
    validation = validate_worker_assignment(source, assignment)
    manifest = read_json_mapping(source / "campaign_manifest.json")
    state = CampaignStateStore(source / "database" / "campaign.sqlite")
    summary = state.summary(str(manifest["campaign_id"]))
    if summary["state_counts"] != {"pending": len(manifest["scenario_ids"])}:
        raise CampaignExchangeError(
            "worker campaign copies must be created before any scenario is assigned or run"
        )
    atomic_copy_tree(source, target)
    validate_campaign(target)
    copied_assignment = target / "worker_assignments" / assignment_path.name
    validate_worker_assignment(target, copied_assignment)
    return {
        "schema_version": "worker-campaign-copy.v1",
        "campaign_id": manifest["campaign_id"],
        "worker_id": validation["worker_id"],
        "scenario_ids": validation["scenario_ids"],
        "destination": str(target),
        "database_mode": "independent_local_copy",
        "valid": True,
    }


def run_worker_assignment(
    campaign_root: Path,
    assignment_path: Path,
    *,
    project_root: Path,
    environment_profile: str,
    max_scenarios: int | None = None,
    dry_run: bool = False,
    lease_seconds: float = 120.0,
    heartbeat_seconds: float = 10.0,
    minimum_free_disk_bytes: int = 5 * 1024**3,
    telemetry_enabled: bool = True,
    telemetry_interval_sec: float = 1.0,
    resume_stopped: bool = False,
) -> ExecutorResult:
    """Validate local identity, then delegate unchanged execution to Stage 4."""

    campaign = campaign_root.resolve()
    assignment = read_yaml_mapping(assignment_path.resolve())
    validation = validate_worker_assignment(
        campaign,
        assignment,
        actual_git_commit=current_git_commit(project_root.resolve()),
        actual_environment_profile=environment_profile,
    )
    scenario_ids = tuple(str(item) for item in validation["scenario_ids"])
    if resume_stopped and not dry_run:
        manifest = read_json_mapping(campaign / "campaign_manifest.json")
        state = CampaignStateStore(campaign / "database" / "campaign.sqlite")
        state.resume_stopped(
            str(manifest["campaign_id"]),
            scenario_ids=scenario_ids,
        )
    executor = CampaignExecutor(
        campaign,
        project_root=project_root.resolve(),
        worker_id=str(validation["worker_id"]),
        lease_seconds=lease_seconds,
        heartbeat_seconds=heartbeat_seconds,
        minimum_free_disk_bytes=minimum_free_disk_bytes,
        telemetry_enabled=telemetry_enabled,
        telemetry_interval_sec=telemetry_interval_sec,
    )
    return executor.run(
        scenario_ids=scenario_ids,
        max_scenarios=max_scenarios,
        dry_run=dry_run,
    )


__all__ = ["prepare_worker_campaign_copy", "run_worker_assignment"]
