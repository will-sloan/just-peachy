"""Command-line interface for Stage 12 campaign analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import analyze_campaign
from .index import build_analysis_manifest, validate_analysis_manifest
from .release import evaluate_release_gates, qualify_synthetic_release
from .statistics import paired_comparison
from .contracts import load_registries
from app.utils.paths import find_project_root


def add_analysis_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("analysis", help="Index, compare, plot, report, and qualify completed campaigns")
    commands = parser.add_subparsers(dest="analysis_command", required=True)

    index = commands.add_parser("index", help="Reconcile planned and observed scenario results")
    _campaign(index)
    index.set_defaults(func=command_index)

    validate = commands.add_parser("validate", help="Validate a standalone analysis manifest")
    _campaign(validate)
    validate.set_defaults(func=command_validate)

    run = commands.add_parser("run", help="Build the complete Stage 12 analysis without inference")
    _campaign(run)
    run.add_argument("--comparison", action="append", default=[], help="baseline,candidate,metric[,item_field]")
    run.add_argument("--prerequisite-evidence", type=Path, default=None)
    run.set_defaults(func=command_run)

    compare = commands.add_parser("compare", help="Run one paired item-level comparison")
    compare.add_argument("--baseline-item-metrics", required=True, type=Path)
    compare.add_argument("--candidate-item-metrics", required=True, type=Path)
    compare.add_argument("--baseline-scenario-id", required=True)
    compare.add_argument("--candidate-scenario-id", required=True)
    compare.add_argument("--metric", required=True)
    compare.set_defaults(func=command_compare)

    coverage = commands.add_parser("coverage", help="Print the current coverage reconciliation")
    _campaign(coverage)
    coverage.set_defaults(func=command_coverage)

    release = commands.add_parser("release-status", help="Print preregistered release-gate status")
    _campaign(release)
    release.add_argument("--prerequisite-evidence", type=Path, default=None)
    release.set_defaults(func=command_release_status)

    qualify = commands.add_parser("qualify-synthetic", help="Run the model-free two-machine workflow qualification")
    qualify.add_argument("--project-root", type=Path, default=None)
    qualify.add_argument("--output-root", required=True, type=Path)
    qualify.set_defaults(func=command_qualify_synthetic)


def command_index(args: argparse.Namespace) -> None:
    print(json.dumps(build_analysis_manifest(args.campaign_root), indent=2))


def command_validate(args: argparse.Namespace) -> None:
    path = args.campaign_root.resolve() / "analysis" / "analysis_manifest.json"
    value = validate_analysis_manifest(path, campaign_root=args.campaign_root)
    print(json.dumps({"valid": True, "analysis_manifest_id": value["analysis_manifest_id"]}, indent=2))


def command_run(args: argparse.Namespace) -> None:
    declarations = [_parse_comparison(value) for value in args.comparison]
    print(json.dumps(analyze_campaign(args.campaign_root, comparisons=declarations, prerequisite_evidence_path=args.prerequisite_evidence), indent=2))


def command_compare(args: argparse.Namespace) -> None:
    print(json.dumps(paired_comparison(args.baseline_item_metrics, args.candidate_item_metrics, metric=args.metric, baseline_scenario_id=args.baseline_scenario_id, candidate_scenario_id=args.candidate_scenario_id), indent=2))


def command_coverage(args: argparse.Namespace) -> None:
    path = args.campaign_root.resolve() / "analysis" / "coverage_matrix.json"
    print(path.read_text(encoding="utf-8"))


def command_release_status(args: argparse.Namespace) -> None:
    root = args.campaign_root.resolve()
    manifest = json.loads((root / "analysis" / "analysis_manifest.json").read_text(encoding="utf-8"))
    coverage = json.loads((root / "analysis" / "coverage_matrix.json").read_text(encoding="utf-8"))
    evidence = json.loads(args.prerequisite_evidence.read_text(encoding="utf-8")) if args.prerequisite_evidence else None
    policy = load_registries().decision_policy
    print(json.dumps(evaluate_release_gates(manifest, coverage, policy, prerequisite_evidence=evidence), indent=2))


def command_qualify_synthetic(args: argparse.Namespace) -> None:
    project_root = find_project_root(args.project_root) if args.project_root else find_project_root()
    print(json.dumps(qualify_synthetic_release(project_root, args.output_root), indent=2))


def _campaign(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign-root", required=True, type=Path)


def _parse_comparison(value: str) -> dict[str, str]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) not in {3, 4} or not all(parts):
        raise argparse.ArgumentTypeError("comparison must be baseline,candidate,metric[,item_field]")
    result = {"baseline_scenario_id": parts[0], "candidate_scenario_id": parts[1], "metric": parts[2]}
    if len(parts) == 4:
        result["item_field"] = parts[3]
    return result
