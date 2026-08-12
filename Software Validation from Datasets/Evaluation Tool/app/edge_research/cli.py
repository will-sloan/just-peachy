"""Command line interface for edge research planning and preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.edge_research.plan import (
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_OUTPUT_ROOT,
    build_edge_research_plan,
    verify_edge_research_plan,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    plan.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    verify = commands.add_parser("verify")
    verify.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    verify.add_argument("--automated-runs-root", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = build_edge_research_plan(args.benchmark_root, args.output_root)
        output = {
            "plan_id": result["plan_id"],
            "catalog_count": len(result["catalogs"]),
            "scenario_count": sum(int(row["scenario_count"]) for row in result["catalogs"]),
            "long_campaign_started": False,
        }
    else:
        result = verify_edge_research_plan(
            args.output_root,
            automated_runs_root=args.automated_runs_root,
        )
        output = result
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
