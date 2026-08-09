"""CLI integration for persistent Stage 4 campaigns."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from app.artifact_contracts.completion import validate_scenario_completion
from app.artifact_contracts.registry import (
    LATEST_ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
)
from app.campaign_exchange import (
    create_worker_assignment,
    current_git_commit,
    export_worker_results,
    merge_worker_results,
    prepare_worker_campaign_copy,
    run_worker_assignment,
    validate_assignment_set,
    validate_merged_results,
    validate_worker_assignment,
    validate_worker_transfer,
)
from app.campaign_executor.executor import CampaignExecutor
from app.campaign_executor.planner import (
    parse_scenario_range,
    plan_campaign,
    validate_campaign,
)
from app.campaign_executor.state import CampaignStateStore
from app.inference_pipeline.resolver import parse_assignments
from app.utils.paths import find_project_root, tool_root


def add_campaign_parser(subparsers: argparse._SubParsersAction) -> None:
    campaign = subparsers.add_parser(
        "campaign",
        help="Plan, run, resume, inspect, and stop persistent benchmark campaigns",
    )
    actions = campaign.add_subparsers(dest="campaign_action", required=True)

    plan = actions.add_parser("plan", help="Create a deterministic campaign queue")
    _add_project_root(plan)
    plan.add_argument("--catalog", type=Path, default=None)
    plan.add_argument("--automated-runs-root", type=Path, default=None)
    plan.add_argument("--campaign-id", default=None)
    plan.add_argument("--scenario-id", action="append", default=[])
    plan.add_argument("--scenario-range", default=None, metavar="START:END")
    plan.add_argument("--panel", action="append", default=[])
    plan.add_argument("--tier", action="append", default=[])
    plan.add_argument("--component", action="append", default=[])
    plan.add_argument("--default-max-retries", type=int, default=0)
    plan.add_argument("--dry-run", action="store_true")
    plan.set_defaults(func=command_campaign_plan)

    validate = actions.add_parser("validate", help="Validate campaign identity and state")
    validate.add_argument("--campaign-root", required=True, type=Path)
    validate.set_defaults(func=command_campaign_validate)

    listing = actions.add_parser("list", help="List scenarios in deterministic order")
    listing.add_argument("--campaign-root", required=True, type=Path)
    listing.add_argument("--state", action="append", default=[])
    listing.set_defaults(func=command_campaign_list)

    for name, help_text in (
        ("run", "Execute queued scenarios"),
        ("resume", "Recover stale work and resume queued scenarios"),
    ):
        run = actions.add_parser(name, help=help_text)
        _add_project_root(run)
        run.add_argument("--campaign-root", required=True, type=Path)
        run.add_argument("--worker-id", required=True)
        run.add_argument("--scenario-id", action="append", default=[])
        run.add_argument("--scenario-range", default=None, metavar="START:END")
        run.add_argument("--max-scenarios", type=int, default=None)
        run.add_argument("--lease-seconds", type=float, default=120.0)
        run.add_argument("--heartbeat-seconds", type=float, default=10.0)
        run.add_argument("--minimum-free-disk-gb", type=float, default=5.0)
        run.add_argument(
            "--telemetry",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="Collect Stage 5 process/component telemetry (default: enabled)",
        )
        run.add_argument("--telemetry-interval-sec", type=float, default=1.0)
        run.add_argument("--dry-run", action="store_true")
        run.set_defaults(func=command_campaign_run)

    status = actions.add_parser("status", help="Show queue and terminal-state counts")
    status.add_argument("--campaign-root", required=True, type=Path)
    status.set_defaults(func=command_campaign_status)

    stop = actions.add_parser("stop", help="Request a campaign or scenario stop")
    stop.add_argument("--campaign-root", required=True, type=Path)
    stop.add_argument("--scenario-id", default=None)
    stop.add_argument("--reason", default="operator request")
    stop.set_defaults(func=command_campaign_stop)

    retry = actions.add_parser("retry", help="Queue eligible failed scenarios")
    retry.add_argument("--campaign-root", required=True, type=Path)
    retry.add_argument("--scenario-id", action="append", default=[])
    retry.set_defaults(func=command_campaign_retry)

    artifacts = actions.add_parser(
        "validate-artifacts",
        help="Validate completed scenario artifacts without executing work",
    )
    artifacts.add_argument("--campaign-root", required=True, type=Path)
    artifacts.add_argument("--scenario-id", action="append", default=[])
    artifacts.set_defaults(func=command_campaign_validate_artifacts)

    assign = actions.add_parser(
        "assign", help="Create a deterministic non-overlapping worker assignment"
    )
    _add_project_root(assign)
    assign.add_argument("--campaign-root", required=True, type=Path)
    assign.add_argument("--worker-id", required=True)
    assign.add_argument("--expected-git-commit", default=None)
    assign.add_argument("--environment-profile", required=True)
    assign.add_argument("--scenario-id", action="append", default=[])
    assign.add_argument("--scenario-range", default=None, metavar="START:END")
    assign.add_argument("--component", action="append", default=[])
    assign.add_argument("--dataset", action="append", default=[])
    assign.add_argument("--panel", action="append", default=[])
    assign.add_argument("--partition-index", type=int, default=None)
    assign.add_argument("--partition-count", type=int, default=None)
    assign.add_argument("--maximum-scenario-count", type=int, default=None)
    assign.add_argument("--allow-overlap", action="store_true")
    assign.add_argument("--notes", default=None)
    assign.add_argument("--output", type=Path, default=None)
    assign.set_defaults(func=command_campaign_assign)

    assignment_validation = actions.add_parser(
        "validate-assignments", help="Validate assignment identity, coverage, and overlap"
    )
    assignment_validation.add_argument("--campaign-root", required=True, type=Path)
    assignment_validation.add_argument("--assignment", action="append", type=Path, default=[])
    assignment_validation.set_defaults(func=command_campaign_validate_assignments)

    assignment_run = actions.add_parser(
        "run-assignment", help="Execute only scenarios in one validated assignment"
    )
    _add_project_root(assignment_run)
    assignment_run.add_argument("--campaign-root", required=True, type=Path)
    assignment_run.add_argument("--assignment", required=True, type=Path)
    assignment_run.add_argument("--environment-profile", required=True)
    assignment_run.add_argument("--max-scenarios", type=int, default=None)
    assignment_run.add_argument("--lease-seconds", type=float, default=120.0)
    assignment_run.add_argument("--heartbeat-seconds", type=float, default=10.0)
    assignment_run.add_argument("--minimum-free-disk-gb", type=float, default=5.0)
    assignment_run.add_argument(
        "--telemetry", action=argparse.BooleanOptionalAction, default=True
    )
    assignment_run.add_argument("--telemetry-interval-sec", type=float, default=1.0)
    assignment_run.add_argument("--dry-run", action="store_true")
    assignment_run.set_defaults(func=command_campaign_run_assignment)

    worker_copy = actions.add_parser(
        "prepare-worker-copy",
        help="Create a one-time independent local copy of a pending campaign",
    )
    worker_copy.add_argument("--campaign-root", required=True, type=Path)
    worker_copy.add_argument("--assignment", required=True, type=Path)
    worker_copy.add_argument("--destination", required=True, type=Path)
    worker_copy.set_defaults(func=command_campaign_prepare_worker_copy)

    export = actions.add_parser(
        "export-results", help="Create a checksummed worker result transfer package"
    )
    _add_project_root(export)
    export.add_argument("--campaign-root", required=True, type=Path)
    export.add_argument("--assignment", required=True, type=Path)
    export.add_argument("--destination", required=True, type=Path)
    export.add_argument("--environment-profile", required=True)
    export.set_defaults(func=command_campaign_export_results)

    transfer_validation = actions.add_parser(
        "validate-transfer", help="Validate a copied worker result package"
    )
    transfer_validation.add_argument("--campaign-root", required=True, type=Path)
    transfer_validation.add_argument("--transfer-root", required=True, type=Path)
    transfer_validation.set_defaults(func=command_campaign_validate_transfer)

    merge = actions.add_parser(
        "merge-results", help="Validate and merge independent worker result packages"
    )
    merge.add_argument("--campaign-root", required=True, type=Path)
    merge.add_argument("--transfer-root", action="append", required=True, type=Path)
    merge.set_defaults(func=command_campaign_merge_results)

    merged_validation = actions.add_parser(
        "validate-merged", help="Revalidate the merged result and analysis indexes"
    )
    merged_validation.add_argument("--campaign-root", required=True, type=Path)
    merged_validation.set_defaults(func=command_campaign_validate_merged)


def command_campaign_plan(args: argparse.Namespace) -> None:
    project_root = find_project_root(args.project_root.resolve() if args.project_root else None)
    evaluation_root = tool_root(project_root)
    catalog = (args.catalog or evaluation_root / "benchmarks" / "v1" / "resolved_scenarios.jsonl").resolve()
    runs_root = (args.automated_runs_root or evaluation_root / "automated_runs").resolve()
    components = parse_assignments(args.component, label="--component")
    component_filters = {str(key): str(value) for key, value in components.items()}
    plan = plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=runs_root,
        campaign_id=args.campaign_id,
        scenario_ids=args.scenario_id,
        scenario_range=parse_scenario_range(args.scenario_range),
        panels=args.panel,
        tiers=args.tier,
        component_filters=component_filters,
        default_max_retries=args.default_max_retries,
        dry_run=args.dry_run,
        registry=ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION),
    )
    print(json.dumps(plan.to_jsonable(), indent=2))


def command_campaign_validate(args: argparse.Namespace) -> None:
    print(json.dumps(validate_campaign(args.campaign_root.resolve()), indent=2))


def command_campaign_list(args: argparse.Namespace) -> None:
    root, campaign_id, state = _campaign_state(args.campaign_root)
    _ = root
    rows = state.scenarios(campaign_id, states=args.state or None)
    print(
        json.dumps(
            {
                "schema_version": "campaign-scenario-list.v1",
                "campaign_id": campaign_id,
                "scenarios": [asdict(row) for row in rows],
            },
            indent=2,
        )
    )


def command_campaign_run(args: argparse.Namespace) -> None:
    project_root = find_project_root(args.project_root.resolve() if args.project_root else None)
    selected = _selected_campaign_ids(
        args.campaign_root.resolve(),
        args.scenario_id,
        parse_scenario_range(args.scenario_range),
    )
    executor = CampaignExecutor(
        args.campaign_root.resolve(),
        project_root=project_root,
        worker_id=args.worker_id,
        lease_seconds=args.lease_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        minimum_free_disk_bytes=int(args.minimum_free_disk_gb * 1024**3),
        telemetry_enabled=args.telemetry,
        telemetry_interval_sec=args.telemetry_interval_sec,
    )
    executor.run(
        scenario_ids=selected or None,
        max_scenarios=args.max_scenarios,
        dry_run=args.dry_run,
    )


def command_campaign_status(args: argparse.Namespace) -> None:
    _root, campaign_id, state = _campaign_state(args.campaign_root)
    print(json.dumps(state.summary(campaign_id), indent=2))


def command_campaign_stop(args: argparse.Namespace) -> None:
    _root, campaign_id, state = _campaign_state(args.campaign_root)
    state.request_stop(
        campaign_id,
        scenario_id=args.scenario_id,
        reason=args.reason,
    )
    print(
        json.dumps(
            {
                "campaign_id": campaign_id,
                "scenario_id": args.scenario_id,
                "stop_requested": True,
            },
            indent=2,
        )
    )


def command_campaign_retry(args: argparse.Namespace) -> None:
    _root, campaign_id, state = _campaign_state(args.campaign_root)
    queued = state.reset_retry_eligible(
        campaign_id,
        scenario_ids=args.scenario_id or None,
    )
    print(json.dumps({"campaign_id": campaign_id, "queued": list(queued)}, indent=2))


def command_campaign_validate_artifacts(args: argparse.Namespace) -> None:
    root, campaign_id, state = _campaign_state(args.campaign_root)
    selected = set(args.scenario_id or ())
    reports = []
    for scenario in state.scenarios(campaign_id):
        if selected and scenario.scenario_id not in selected:
            continue
        reports.append(
            validate_scenario_completion(
                root / "scenarios" / scenario.scenario_id
            ).to_jsonable()
        )
    missing = selected - {str(item["scenario_id"]) for item in reports}
    if missing:
        raise ValueError(f"unknown scenario IDs: {sorted(missing)}")
    print(json.dumps({"campaign_id": campaign_id, "reports": reports}, indent=2))


def command_campaign_assign(args: argparse.Namespace) -> None:
    project_root = find_project_root(args.project_root.resolve() if args.project_root else None)
    components = parse_assignments(args.component, label="--component")
    assignment = create_worker_assignment(
        args.campaign_root.resolve(),
        worker_id=args.worker_id,
        expected_git_commit=args.expected_git_commit or current_git_commit(project_root),
        expected_environment_profile=args.environment_profile,
        scenario_ids=args.scenario_id,
        scenario_range=parse_scenario_range(args.scenario_range),
        component_filters={str(key): str(value) for key, value in components.items()},
        datasets=args.dataset,
        panels=args.panel,
        partition_index=args.partition_index,
        partition_count=args.partition_count,
        maximum_scenario_count=args.maximum_scenario_count,
        allow_overlap=args.allow_overlap,
        notes=args.notes,
        output_path=args.output.resolve() if args.output else None,
    )
    print(json.dumps(assignment, indent=2))


def command_campaign_validate_assignments(args: argparse.Namespace) -> None:
    report = validate_assignment_set(
        args.campaign_root.resolve(),
        [path.resolve() for path in args.assignment] or None,
    )
    print(json.dumps(report, indent=2))


def command_campaign_run_assignment(args: argparse.Namespace) -> None:
    project_root = find_project_root(args.project_root.resolve() if args.project_root else None)
    run_worker_assignment(
        args.campaign_root.resolve(),
        args.assignment.resolve(),
        project_root=project_root,
        environment_profile=args.environment_profile,
        max_scenarios=args.max_scenarios,
        dry_run=args.dry_run,
        lease_seconds=args.lease_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        minimum_free_disk_bytes=int(args.minimum_free_disk_gb * 1024**3),
        telemetry_enabled=args.telemetry,
        telemetry_interval_sec=args.telemetry_interval_sec,
    )


def command_campaign_prepare_worker_copy(args: argparse.Namespace) -> None:
    report = prepare_worker_campaign_copy(
        args.campaign_root.resolve(),
        args.assignment.resolve(),
        args.destination.resolve(),
    )
    print(json.dumps(report, indent=2))


def command_campaign_export_results(args: argparse.Namespace) -> None:
    project_root = find_project_root(args.project_root.resolve() if args.project_root else None)
    assignment = args.assignment.resolve()
    validate_worker_assignment(
        args.campaign_root.resolve(),
        assignment,
        actual_git_commit=current_git_commit(project_root),
        actual_environment_profile=args.environment_profile,
    )
    manifest = export_worker_results(
        args.campaign_root.resolve(),
        assignment,
        args.destination.resolve(),
        repository_root=project_root,
        actual_git_commit=current_git_commit(project_root),
        actual_environment_profile=args.environment_profile,
    )
    print(json.dumps(manifest, indent=2))


def command_campaign_validate_transfer(args: argparse.Namespace) -> None:
    report = validate_worker_transfer(
        args.transfer_root.resolve(), campaign_root=args.campaign_root.resolve()
    )
    print(json.dumps(report, indent=2))


def command_campaign_merge_results(args: argparse.Namespace) -> None:
    report = merge_worker_results(
        args.campaign_root.resolve(),
        [path.resolve() for path in args.transfer_root],
    )
    print(json.dumps(report, indent=2))


def command_campaign_validate_merged(args: argparse.Namespace) -> None:
    print(json.dumps(validate_merged_results(args.campaign_root.resolve()), indent=2))


def _campaign_state(path: Path) -> tuple[Path, str, CampaignStateStore]:
    root = path.resolve()
    manifest = json.loads((root / "campaign_manifest.json").read_text(encoding="utf-8"))
    campaign_id = str(manifest["campaign_id"])
    return root, campaign_id, CampaignStateStore(root / "database" / "campaign.sqlite")


def _selected_campaign_ids(
    campaign_root: Path,
    explicit: list[str],
    scenario_range: tuple[str, str] | None,
) -> tuple[str, ...]:
    _root, campaign_id, state = _campaign_state(campaign_root)
    known = [item.scenario_id for item in state.scenarios(campaign_id)]
    requested = set(explicit)
    if requested - set(known):
        raise ValueError(f"unknown scenario IDs: {sorted(requested - set(known))}")
    selected = tuple(
        scenario_id
        for scenario_id in known
        if (not requested or scenario_id in requested)
        and (
            scenario_range is None
            or scenario_range[0] <= scenario_id <= scenario_range[1]
        )
    )
    if (requested or scenario_range is not None) and not selected:
        raise ValueError("scenario selection matched no campaign work")
    return selected


def _add_project_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Software Validation from Datasets root containing normalized/raw datasets",
    )
