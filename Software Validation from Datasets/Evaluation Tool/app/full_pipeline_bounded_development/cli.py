"""Command-line interface for the bounded Prompt-4 controller."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from . import orchestration


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="C:-only eight-day reduced Prompt-4 all-18 controller"
    )
    parser.add_argument(
        "action",
        choices=(
            "plan",
            "prepare",
            "run",
            "prepare-resources",
            "run-resources",
            "analyze",
            "freeze",
            "collect",
            "execute",
            "validate",
            "status",
            "stop",
        ),
    )
    parser.add_argument("--workspace-root", type=Path, default=orchestration.DEFAULT_ROOT)
    parser.add_argument(
        "--source-evidence-root",
        type=Path,
        default=orchestration.DEFAULT_SOURCE_EVIDENCE_ROOT,
    )
    parser.add_argument("--output-root", type=Path, default=orchestration.DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        value = _dispatch(args)
        print(json.dumps(value, indent=2, sort_keys=True, default=str))
        return 0 if str(value.get("status") or "").upper() in {
            "PASS",
            "COMPLETE",
            "STOP_REQUESTED",
        } else 1
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    common = {
        "workspace_root": args.workspace_root,
        "source_evidence_root": args.source_evidence_root,
        "output_root": args.output_root,
    }
    if args.action == "plan":
        return orchestration.plan(**common)
    if args.action == "prepare":
        return orchestration.prepare(**common)
    if args.action == "run":
        return orchestration.run(workspace_root=args.workspace_root)
    if args.action == "prepare-resources":
        return orchestration.prepare_resources(**common)
    if args.action == "run-resources":
        return orchestration.run_resources(workspace_root=args.workspace_root)
    if args.action == "analyze":
        return orchestration.analyze(workspace_root=args.workspace_root)
    if args.action == "freeze":
        return orchestration.freeze(workspace_root=args.workspace_root)
    if args.action == "collect":
        return orchestration.collect(
            workspace_root=args.workspace_root, output_root=args.output_root
        )
    if args.action == "execute":
        return orchestration.execute(**common)
    if args.action == "validate":
        return orchestration.validate(workspace_root=args.workspace_root)
    if args.action == "status":
        return orchestration.status(workspace_root=args.workspace_root)
    if args.action == "stop":
        return orchestration.stop(workspace_root=args.workspace_root)
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
