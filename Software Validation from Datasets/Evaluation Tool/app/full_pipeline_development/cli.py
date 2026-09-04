"""CLI for model-free Prompt-4 qualification and development reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from . import orchestration
from .qualification import (
    build_qualification_plan,
    validate_qualification_bundle,
    write_qualification_plan,
)
from .reporting import collect_development_report, publish_development_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        value = _dispatch(args)
        print(json.dumps(value, indent=2, sort_keys=True, default=str))
        return 0 if value.get("status") != "FAIL" and value.get("valid") is not False else 1
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Just-Peachy all-18 development qualification/reporting"
    )
    parser.add_argument(
        "action",
        choices=(
            "plan",
            "prepare-calibration",
            "run-calibration",
            "freeze-policies",
            "prepare-qualification",
            "run-qualification",
            "qualify-restarts",
            "finalize-qualification",
            "prepare-development",
            "run-development",
            "prepare-resources",
            "run-resources",
            "combine-evidence",
            "freeze-development",
            "status",
            "stop",
            "plan-qualification",
            "validate-qualification",
            "analyze",
            "collect",
        ),
    )
    parser.add_argument("--workspace-root", type=Path, default=orchestration.DEFAULT_ROOT)
    parser.add_argument("--policy-registry-path", type=Path)
    parser.add_argument("--seed", type=int, default=5107)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--plan-path", type=Path)
    parser.add_argument("--qualification-path", type=Path)
    parser.add_argument("--qualification-evidence-root", type=Path)
    parser.add_argument("--analysis-path", type=Path)
    parser.add_argument("--campaign-manifest", type=Path)
    parser.add_argument("--frozen-config-root", type=Path)
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.action == "plan":
        return orchestration.plan(workspace_root=args.workspace_root)
    if args.action == "prepare-calibration":
        return orchestration.prepare_calibration(
            workspace_root=args.workspace_root, seed=args.seed
        )
    if args.action == "run-calibration":
        return orchestration.run_calibration(workspace_root=args.workspace_root)
    if args.action == "freeze-policies":
        return orchestration.freeze_policies(
            workspace_root=args.workspace_root,
            policy_registry_path=args.policy_registry_path,
        )
    if args.action == "prepare-qualification":
        return orchestration.prepare_qualification(
            workspace_root=args.workspace_root,
            policy_registry_path=args.policy_registry_path,
            seed=args.seed,
        )
    if args.action == "run-qualification":
        return orchestration.run_qualification(
            workspace_root=args.workspace_root,
            policy_registry_path=args.policy_registry_path,
        )
    if args.action == "qualify-restarts":
        return orchestration.qualify_restarts(workspace_root=args.workspace_root)
    if args.action == "finalize-qualification":
        return orchestration.finalize_qualification(
            workspace_root=args.workspace_root
        )
    if args.action == "prepare-development":
        return orchestration.prepare_development(
            workspace_root=args.workspace_root,
            policy_registry_path=args.policy_registry_path,
            seed=args.seed,
        )
    if args.action == "run-development":
        return orchestration.run_development(workspace_root=args.workspace_root)
    if args.action == "prepare-resources":
        return orchestration.prepare_resources(
            workspace_root=args.workspace_root,
            policy_registry_path=args.policy_registry_path,
            seed=args.seed,
        )
    if args.action == "run-resources":
        return orchestration.run_resources(workspace_root=args.workspace_root)
    if args.action == "combine-evidence":
        return orchestration.combine_evidence(workspace_root=args.workspace_root)
    if args.action == "freeze-development":
        return orchestration.freeze_development(
            workspace_root=args.workspace_root
        )
    if args.action == "status":
        return orchestration.status(workspace_root=args.workspace_root)
    if args.action == "stop":
        return orchestration.stop(workspace_root=args.workspace_root)
    if args.action == "plan-qualification":
        plan = build_qualification_plan()
        if args.plan_path is not None:
            write_qualification_plan(args.plan_path, plan)
        return plan
    if args.action == "validate-qualification":
        _require(args.qualification_path, "--qualification-path")
        return validate_qualification_bundle(
            args.qualification_path,
            plan=args.plan_path,
            evidence_root=args.qualification_evidence_root,
            verify_evidence_files=True,
        )
    if args.action == "analyze":
        for value, name in (
            (args.analysis_path, "--analysis-path"),
            (args.campaign_manifest, "--campaign-manifest"),
            (args.qualification_path, "--qualification-path"),
            (args.frozen_config_root, "--frozen-config-root"),
            (args.output_root, "--output-root"),
        ):
            _require(value, name)
        return publish_development_report(
            analysis_index=args.analysis_path,
            campaign_manifest=args.campaign_manifest,
            qualification_bundle=args.qualification_path,
            qualification_plan=args.plan_path,
            qualification_evidence_root=args.qualification_evidence_root,
            frozen_config_root=args.frozen_config_root,
            output_root=args.output_root,
        )
    if args.action == "collect":
        _require(args.output_root, "--output-root")
        return collect_development_report(args.output_root)
    raise AssertionError(args.action)


def _require(value: object, name: str) -> None:
    if value is None:
        raise ValueError(f"{name} is required for this action")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
