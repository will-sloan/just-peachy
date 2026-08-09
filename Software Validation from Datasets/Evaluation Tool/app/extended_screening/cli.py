"""CLI registration for Stage 9 extended-backend screening."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.extended_screening.analysis import analyze_extended_screening_campaign
from app.extended_screening.plan import (
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_OUTPUT_ROOT,
    build_extended_screening_plan,
)
from app.extended_screening.smoke import build_real_smoke_matrix


def add_extended_screening_parser(
    subparsers: argparse._SubParsersAction,
) -> None:
    parser = subparsers.add_parser(
        "extended-screening",
        help="Plan, smoke, and analyze Stage 9 qualified extended backends",
    )
    actions = parser.add_subparsers(dest="extended_screening_action", required=True)

    plan = actions.add_parser("plan", help="Build deterministic Stage 9 scenarios")
    plan.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    plan.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    plan.add_argument("--asr-shortlist", action="append", default=[])
    plan.add_argument("--vad-shortlist", action="append", default=[])
    plan.add_argument("--embedding-shortlist", action="append", default=[])
    plan.add_argument("--finalist", action="append", default=[])
    plan.set_defaults(func=command_extended_screening_plan)

    smoke = actions.add_parser(
        "smoke", help="Run or validate every eligible backend on one real item"
    )
    smoke.add_argument("--output-root", type=Path)
    smoke.add_argument("--audio", type=Path)
    smoke.add_argument("--rerun", action="store_true")
    smoke.set_defaults(func=command_extended_screening_smoke)

    analyze = actions.add_parser(
        "analyze", help="Analyze a validated Stage 9 campaign result index"
    )
    analyze.add_argument("--plan", type=Path, required=True)
    analyze.add_argument("--analysis-index", type=Path, required=True)
    analyze.add_argument("--embedding-results", type=Path)
    analyze.add_argument("--output-dir", type=Path)
    analyze.set_defaults(func=command_extended_screening_analyze)


def command_extended_screening_plan(args: argparse.Namespace) -> None:
    payload = build_extended_screening_plan(
        args.benchmark_dir,
        args.output_dir,
        asr_shortlist=args.asr_shortlist,
        vad_shortlist=args.vad_shortlist,
        embedding_shortlist=args.embedding_shortlist,
        finalists=args.finalist,
    )
    print(
        json.dumps(
            {
                "plan_id": payload["plan_id"],
                "candidate_count": len(payload["candidate_definitions"]),
                "scenario_count": payload["scenario_catalog"]["scenario_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def command_extended_screening_smoke(args: argparse.Namespace) -> None:
    keywords = {"rerun": args.rerun}
    if args.output_root is not None:
        keywords["output_root"] = args.output_root
    if args.audio is not None:
        keywords["audio_path"] = args.audio
    payload = build_real_smoke_matrix(**keywords)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


def command_extended_screening_analyze(args: argparse.Namespace) -> None:
    payload = analyze_extended_screening_campaign(
        args.plan,
        args.analysis_index,
        embedding_results_path=args.embedding_results,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "analysis_id": payload["analysis_id"],
                "stage_count": len(payload["stages"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
