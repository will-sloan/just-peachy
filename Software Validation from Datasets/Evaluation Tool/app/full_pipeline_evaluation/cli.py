"""Command-line actions for the full-pipeline evaluation controller."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from . import controller
from .planning import DEFAULT_SEED, DEFAULT_WORKSPACE_ROOT


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        value = _dispatch(args)
        print(json.dumps(value, indent=2, sort_keys=True, default=str))
        status = str(value.get("status") or "").casefold()
        valid = value.get("valid")
        return 1 if status in {"fail", "failed", "blocked"} or valid is False else 0
    except KeyboardInterrupt:
        print("Graceful stop requested by keyboard interrupt.", file=sys.stderr)
        try:
            controller.stop(workspace_root=args.workspace_root)
        except Exception:
            pass
        return 130
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Just-Peachy reproducible full-pipeline evaluation"
    )
    parser.add_argument(
        "action",
        choices=(
            "audit",
            "prepare",
            "validate",
            "plan",
            "smoke",
            "run-development",
            "freeze",
            "run-evaluation",
            "status",
            "stop",
            "analyze",
            "collect",
        ),
    )
    parser.add_argument(
        "--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT
    )
    parser.add_argument("--pipeline-id", action="append", default=[])
    parser.add_argument("--protocol-id", action="append", default=[])
    parser.add_argument(
        "--measurement-mode", choices=("accuracy", "resources"), default=None
    )
    parser.add_argument("--parallel-jobs", type=int, choices=(1, 2), default=2)
    parser.add_argument("--split", choices=("development", "evaluation"))
    parser.add_argument("--verify-audio", action="store_true")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-root", type=Path)
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    workspace = args.workspace_root
    pipelines = tuple(args.pipeline_id)
    protocols = tuple(args.protocol_id)
    if args.action == "audit":
        return controller.audit()
    if args.action == "prepare":
        return controller.prepare(workspace_root=workspace, seed=args.seed)
    if args.action == "validate":
        return controller.validate(
            workspace_root=workspace, verify_audio=args.verify_audio
        )
    if args.action == "plan":
        return controller.plan(
            workspace_root=workspace,
            split=args.split,
            measurement_mode=args.measurement_mode,
            pipeline_ids=pipelines,
            protocol_ids=protocols,
        )
    if args.action == "smoke":
        from .smoke import run_infrastructure_smoke

        return run_infrastructure_smoke(output_root=args.output_root)
    if args.action == "run-development":
        return controller.run_development(
            workspace_root=workspace,
            measurement_mode=args.measurement_mode or "accuracy",
            pipeline_ids=pipelines,
            protocol_ids=protocols,
            parallel_jobs=args.parallel_jobs,
        )
    if args.action == "freeze":
        return controller.freeze(workspace_root=workspace)
    if args.action == "run-evaluation":
        return controller.run_evaluation(
            workspace_root=workspace,
            measurement_mode=args.measurement_mode or "accuracy",
            pipeline_ids=pipelines,
            protocol_ids=protocols,
            parallel_jobs=args.parallel_jobs,
        )
    if args.action == "status":
        return controller.status(workspace_root=workspace)
    if args.action == "stop":
        return controller.stop(workspace_root=workspace)
    if args.action == "analyze":
        return controller.analyze(workspace_root=workspace)
    if args.action == "collect":
        return controller.collect(workspace_root=workspace)
    raise AssertionError(args.action)
