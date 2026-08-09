"""CLI integration for Stage 7 qualification, planning, and analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core_screening.analysis import analyze_screening_campaign
from app.core_screening.plan import (
    ASR_COMPONENTS,
    SEGMENTATION_COMPONENTS,
    build_screening_plan,
)
from app.core_screening.qualification import qualify_core_components
from app.utils.paths import find_project_root, tool_root


def add_screening_parser(subparsers: argparse._SubParsersAction) -> None:
    screening = subparsers.add_parser(
        "screening",
        help="Plan, qualify, and analyze the Stage 7 core component screen",
    )
    actions = screening.add_subparsers(dest="screening_action", required=True)

    plan = actions.add_parser("plan", help="Build deterministic Stage 7 scenarios")
    _add_project_root(plan)
    plan.add_argument("--benchmark-dir", type=Path, default=None)
    plan.add_argument("--output-dir", type=Path, default=None)
    plan.add_argument(
        "--segmentation-shortlist",
        action="append",
        choices=tuple(SEGMENTATION_COMPONENTS),
        default=[],
        help="Declared Stage C finalist; repeat for at most two candidates.",
    )
    plan.add_argument(
        "--qualified-asr",
        action="append",
        choices=ASR_COMPONENTS,
        default=[],
        help="Qualified ASR for Stage D; omit to use Tiny, Base, and Small.",
    )
    plan.add_argument(
        "--finalist",
        action="append",
        default=[],
        help="Declared Stage D candidate ID for three-repeat final validation.",
    )
    plan.set_defaults(func=command_screening_plan)

    qualify = actions.add_parser(
        "qualify", help="Run repeated real local qualification for Stages A and E"
    )
    _add_project_root(qualify)
    qualify.add_argument("--audio", type=Path, default=None)
    qualify.add_argument("--degraded-audio", type=Path, default=None)
    qualify.add_argument("--repetitions", type=int, default=2)
    qualify.add_argument(
        "--reference-asr",
        choices=ASR_COMPONENTS,
        default="whisper_base",
        help="Reference ASR for VAD/chunker qualification (default: whisper_base).",
    )
    qualify.add_argument("--output", type=Path, default=None)
    qualify.set_defaults(func=command_screening_qualify)

    analyze = actions.add_parser(
        "analyze", help="Analyze a validated Stage 6 merged-result index"
    )
    analyze.add_argument("--plan", required=True, type=Path)
    analyze.add_argument("--analysis-index", required=True, type=Path)
    analyze.add_argument("--qualification", type=Path, default=None)
    analyze.add_argument("--output-dir", type=Path, default=None)
    analyze.set_defaults(func=command_screening_analyze)


def command_screening_plan(args: argparse.Namespace) -> None:
    project_root = find_project_root(
        args.project_root.resolve() if args.project_root else None
    )
    evaluation_root = tool_root(project_root)
    shortlist = list(args.segmentation_shortlist)
    if len(shortlist) > 2:
        raise ValueError("Stage D accepts at most two segmentation finalists")
    plan = build_screening_plan(
        (args.benchmark_dir or evaluation_root / "benchmarks" / "v1").resolve(),
        (args.output_dir or evaluation_root / "benchmarks" / "stage7").resolve(),
        segmentation_shortlist=shortlist,
        qualified_asr=args.qualified_asr or ASR_COMPONENTS,
        finalists=args.finalist,
    )
    print(
        json.dumps(
            {
                "plan_id": plan["plan_id"],
                "scenario_count": plan["scenario_catalog"]["scenario_count"],
                "output_dir": str(
                    (
                        args.output_dir or evaluation_root / "benchmarks" / "stage7"
                    ).resolve()
                ),
            },
            indent=2,
        )
    )


def command_screening_qualify(args: argparse.Namespace) -> None:
    project_root = find_project_root(
        args.project_root.resolve() if args.project_root else None
    )
    evaluation_root = tool_root(project_root)
    audio = (args.audio or _default_audio(project_root)).resolve()
    output = (
        args.output
        or evaluation_root / "runs" / "component_qualification" / "stage7_core_cpu.json"
    ).resolve()
    result = qualify_core_components(
        audio,
        project_root=project_root,
        repetitions=args.repetitions,
        degraded_audio_path=args.degraded_audio,
        reference_asr=args.reference_asr,
        output_path=output,
    )
    print(json.dumps(result["summary"], indent=2))
    print(f"Qualification artifact: {output}")


def command_screening_analyze(args: argparse.Namespace) -> None:
    result = analyze_screening_campaign(
        args.plan,
        args.analysis_index,
        qualification_path=args.qualification,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "analysis_id": result["analysis_id"],
                "stage_count": len(result["stages"]),
            },
            indent=2,
        )
    )


def _default_audio(project_root: Path) -> Path:
    path = (
        project_root
        / "Raw Datasets (Not formatted)"
        / "CMU Arctic"
        / "cmu_us_aew_arctic"
        / "wav"
        / "arctic_b0476.wav"
    )
    if not path.is_file():
        raise FileNotFoundError(
            "pass --audio because the default CMU Arctic smoke file is missing"
        )
    return path


def _add_project_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Software Validation from Datasets root containing datasets and Evaluation Tool",
    )
