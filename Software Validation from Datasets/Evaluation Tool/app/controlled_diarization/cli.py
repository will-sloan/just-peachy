"""Public CLI for the controlled Stage 11 diarization benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


def add_controlled_diarization_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "diarization-benchmark",
        help="Build and operate the controlled synthetic-placement diarization benchmark",
    )
    commands = parser.add_subparsers(dest="controlled_diarization_command", required=True)

    audit = commands.add_parser("audit", help="Audit source feasibility without inference")
    _config(audit)
    _source_pool(audit)
    audit.add_argument("--output", type=Path, default=None)
    audit.set_defaults(func=_audit)

    prepare = commands.add_parser("prepare", help="Freeze recipes/references and render audio")
    _common_paths(prepare)
    _source_pool(prepare)
    prepare.set_defaults(func=_prepare)

    validate = commands.add_parser("validate", help="Validate the benchmark or one result")
    _common_paths(validate)
    validate.add_argument("--result-root", type=Path, default=None)
    validate.add_argument("--verify-source-hashes", action="store_true")
    validate.set_defaults(func=_validate)

    plan = commands.add_parser("plan", help="Print an exact model-free execution plan")
    _common_paths(plan)
    _pipelines(plan)
    plan.add_argument("--tier", choices=("smoke", "development", "evaluation"), default="evaluation")
    plan.set_defaults(func=_plan)

    status = commands.add_parser("pipeline-status", help="Report pipeline/environment readiness")
    _config(status)
    status.set_defaults(func=_pipeline_status)

    run_case = commands.add_parser("run-case", help="Run one case in the current isolated environment")
    _common_paths(run_case)
    run_case.add_argument("--tier", choices=("smoke", "development", "evaluation"), required=True)
    run_case.add_argument("--case-id", required=True)
    run_case.add_argument("--pipeline", required=True)
    run_case.add_argument("--output-root", type=Path, required=True)
    run_case.add_argument("--oracle-speaker-count-diagnostic", action="store_true")
    run_case.set_defaults(func=_run_case)

    run = commands.add_parser("run", help="Run/reuse a sequential restart-safe queue")
    _common_paths(run)
    _pipelines(run, required=True)
    run.add_argument("--tier", choices=("smoke", "development", "evaluation"), required=True)
    run.add_argument("--result-root", type=Path, default=None)
    run.add_argument("--frozen-pipeline-config", type=Path, default=None)
    run.add_argument("--max-cases", type=int, default=None)
    run.add_argument("--oracle-speaker-count-diagnostic", action="store_true")
    run.set_defaults(func=_run)

    smoke = commands.add_parser("smoke", help="Run only the non-scientific smoke panel")
    _common_paths(smoke)
    _pipelines(smoke, required=True)
    smoke.add_argument("--result-root", type=Path, default=None)
    smoke.add_argument("--max-cases", type=int, default=None)
    smoke.set_defaults(func=_smoke)

    queue_status = commands.add_parser("status", help="Report valid/missing/partial/failed counts")
    _config(queue_status)
    queue_status.add_argument("--benchmark-root", type=Path, default=None)
    queue_status.add_argument("--result-root", type=Path, default=None)
    _pipelines(queue_status, required=True)
    queue_status.add_argument("--tier", action="append", choices=("smoke", "development", "evaluation"), default=[])
    queue_status.set_defaults(func=_status)

    freeze = commands.add_parser(
        "freeze-pipelines",
        help="Freeze an explicit post-development operator decision for evaluation",
    )
    _config(freeze)
    freeze.add_argument("--benchmark-root", type=Path, default=None)
    freeze.add_argument("--result-root", type=Path, default=None)
    freeze.add_argument("--analysis-root", type=Path, default=None)
    _pipelines(freeze, required=True)
    freeze.add_argument("--decision-note", required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.set_defaults(func=_freeze)

    analyze = commands.add_parser("analyze", help="Build all controlled Stage 11 analysis tables")
    _config(analyze)
    analyze.add_argument("--benchmark-root", type=Path, default=None)
    analyze.add_argument("--result-root", type=Path, default=None)
    analyze.add_argument("--output-root", type=Path, default=None)
    _pipelines(analyze, required=True)
    analyze.add_argument("--tier", action="append", choices=("smoke", "development", "evaluation"), default=[])
    analyze.set_defaults(func=_analyze)

    collect = commands.add_parser("collect", help="Collect compact results without generated audio")
    collect.add_argument("--benchmark-root", type=Path, default=None)
    collect.add_argument("--generated-root", type=Path, default=None)
    collect.add_argument("--result-root", type=Path, default=None)
    collect.add_argument("--analysis-root", type=Path, default=None)
    collect.add_argument("--output-root", type=Path, default=None)
    _pipelines(collect, required=True)
    collect.add_argument("--tier", action="append", choices=("smoke", "development", "evaluation"), default=[])
    collect.set_defaults(func=_collect)

    reconstruct = commands.add_parser("reconstruct", help="Re-render one frozen recipe")
    reconstruct.add_argument("--recipe", type=Path, required=True)
    reconstruct.add_argument("--output", type=Path, required=True)
    reconstruct.set_defaults(func=_reconstruct)


def _config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None)


def _source_pool(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-speaker-pool", type=Path, default=None)


def _common_paths(parser: argparse.ArgumentParser) -> None:
    _config(parser)
    parser.add_argument("--benchmark-root", type=Path, default=None)
    parser.add_argument("--generated-root", type=Path, default=None)


def _pipelines(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    parser.add_argument("--pipeline", action="append", default=[], required=required)


def _paths(args: argparse.Namespace):
    from app.controlled_diarization.contracts import (
        DEFAULT_BENCHMARK_ROOT,
        DEFAULT_CONFIG_PATH,
    )

    return args.config or DEFAULT_CONFIG_PATH, args.benchmark_root or DEFAULT_BENCHMARK_ROOT


def _audit(args: argparse.Namespace) -> None:
    from app.controlled_diarization.benchmark import audit_source_pool
    from app.controlled_diarization.contracts import DEFAULT_CONFIG_PATH
    from app.diarization_evaluation.artifacts import write_json_atomic

    result = audit_source_pool(
        config_path=args.config or DEFAULT_CONFIG_PATH,
        source_pool_manifest=args.source_speaker_pool,
    )
    if args.output:
        write_json_atomic(args.output, result)
    print(json.dumps(result, indent=2))


def _prepare(args: argparse.Namespace) -> None:
    from app.controlled_diarization.benchmark import prepare_benchmark

    config, benchmark = _paths(args)
    result = prepare_benchmark(
        config_path=config,
        benchmark_root=benchmark,
        generated_root=args.generated_root,
        source_pool_manifest=args.source_speaker_pool,
    )
    print(json.dumps(result, indent=2))


def _validate(args: argparse.Namespace) -> None:
    from app.controlled_diarization.benchmark import validate_benchmark
    from app.controlled_diarization.runner import validate_result

    config, benchmark = _paths(args)
    result = (
        validate_result(args.result_root)
        if args.result_root
        else validate_benchmark(
            config_path=config,
            benchmark_root=benchmark,
            generated_root=args.generated_root,
            verify_source_hashes=args.verify_source_hashes,
        )
    )
    print(json.dumps(result, indent=2))
    if not result.get("valid"):
        raise SystemExit(2)


def _plan(args: argparse.Namespace) -> None:
    from app.controlled_diarization.benchmark import benchmark_plan
    from app.controlled_diarization.contracts import TOOL_ROOT

    config, benchmark = _paths(args)
    result = benchmark_plan(
        config_path=config,
        benchmark_root=benchmark,
        generated_root=args.generated_root,
        pipelines=args.pipeline,
        tier=args.tier,
    )
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=TOOL_ROOT, capture_output=True, text=True, check=True
    )
    result["git_sha"] = completed.stdout.strip()
    print(json.dumps(result, indent=2))


def _pipeline_status(args: argparse.Namespace) -> None:
    from app.controlled_diarization.contracts import DEFAULT_CONFIG_PATH
    from app.controlled_diarization.runner import pipeline_status

    print(json.dumps(pipeline_status(config_path=args.config or DEFAULT_CONFIG_PATH), indent=2))


def _run_case(args: argparse.Namespace) -> None:
    from app.controlled_diarization.runner import run_one_case

    config, benchmark = _paths(args)
    result = run_one_case(
        tier=args.tier,
        case_id=args.case_id,
        pipeline_id=args.pipeline,
        output_root=args.output_root,
        config_path=config,
        benchmark_root=benchmark,
        generated_root=args.generated_root,
        oracle_speaker_count_diagnostic=args.oracle_speaker_count_diagnostic,
    )
    print(json.dumps(result, indent=2))


def _run(args: argparse.Namespace) -> None:
    from app.controlled_diarization.runner import execute_queue

    config, benchmark = _paths(args)
    result = execute_queue(
        tier=args.tier,
        pipelines=args.pipeline,
        config_path=config,
        benchmark_root=benchmark,
        generated_root=args.generated_root,
        result_root=args.result_root,
        frozen_pipeline_config=args.frozen_pipeline_config,
        max_cases=args.max_cases,
        oracle_speaker_count_diagnostic=args.oracle_speaker_count_diagnostic,
    )
    print(json.dumps(result, indent=2))
    if result["failed"]:
        raise SystemExit(2)


def _smoke(args: argparse.Namespace) -> None:
    from app.controlled_diarization.runner import execute_queue

    config, benchmark = _paths(args)
    result = execute_queue(
        tier="smoke",
        pipelines=args.pipeline,
        config_path=config,
        benchmark_root=benchmark,
        generated_root=args.generated_root,
        result_root=args.result_root,
        max_cases=args.max_cases,
    )
    result["scientific"] = False
    result["label"] = "SMOKE / NON-SCIENTIFIC"
    print(json.dumps(result, indent=2))
    if result["failed"]:
        raise SystemExit(2)


def _status(args: argparse.Namespace) -> None:
    from app.controlled_diarization.contracts import DEFAULT_BENCHMARK_ROOT, DEFAULT_CONFIG_PATH
    from app.controlled_diarization.runner import queue_status

    tiers = args.tier or ["development", "evaluation"]
    result = queue_status(
        pipelines=args.pipeline,
        tiers=tiers,
        config_path=args.config or DEFAULT_CONFIG_PATH,
        benchmark_root=args.benchmark_root or DEFAULT_BENCHMARK_ROOT,
        result_root=args.result_root,
    )
    print(json.dumps(result, indent=2))


def _freeze(args: argparse.Namespace) -> None:
    from app.controlled_diarization.contracts import (
        DEFAULT_BENCHMARK_ROOT,
        DEFAULT_CONFIG_PATH,
        FROZEN_PIPELINE_SCHEMA_VERSION,
        load_config,
        load_pipeline_registry,
    )
    from app.controlled_diarization.runner import queue_status
    from app.diarization_evaluation.artifacts import write_json_atomic

    config_path = args.config or DEFAULT_CONFIG_PATH
    benchmark = (args.benchmark_root or DEFAULT_BENCHMARK_ROOT).resolve()
    analysis = args.analysis_root or ((args.result_root or Path.home() / "JustPeachyResults" / "diarization" / "controlled_diarization_v1") / "analysis")
    if not (analysis / "analysis_manifest.json").is_file():
        raise ValueError("development analysis_manifest.json is required before freezing")
    status = queue_status(
        pipelines=args.pipeline,
        tiers=("development",),
        config_path=config_path,
        benchmark_root=benchmark,
        result_root=args.result_root,
    )
    if any(row["valid"] != row["planned"] for row in status["rows"]):
        raise ValueError("all selected development cases must validate before freezing")
    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    summary = json.loads((benchmark / "protocol_summary.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": FROZEN_PIPELINE_SCHEMA_VERSION,
        "benchmark_id": summary["benchmark_id"],
        "development_decision_status": "frozen",
        "evaluation_tuning_prohibited": True,
        "decision_note": args.decision_note,
        "analysis_manifest_sha256": __import__("hashlib").sha256((analysis / "analysis_manifest.json").read_bytes()).hexdigest(),
        "pipelines": [
            {
                "pipeline_id": value,
                "configuration_sha256": registry[value].configuration_sha256,
            }
            for value in args.pipeline
        ],
    }
    write_json_atomic(args.output, payload)
    print(json.dumps(payload, indent=2))


def _analyze(args: argparse.Namespace) -> None:
    from app.controlled_diarization.analysis import analyze_results
    from app.controlled_diarization.contracts import DEFAULT_BENCHMARK_ROOT, DEFAULT_CONFIG_PATH

    result = analyze_results(
        pipelines=args.pipeline,
        tiers=args.tier or ["development", "evaluation"],
        config_path=args.config or DEFAULT_CONFIG_PATH,
        benchmark_root=args.benchmark_root or DEFAULT_BENCHMARK_ROOT,
        result_root=args.result_root,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2))


def _collect(args: argparse.Namespace) -> None:
    from app.controlled_diarization.analysis import collect_research_package
    from app.controlled_diarization.contracts import DEFAULT_BENCHMARK_ROOT

    result = collect_research_package(
        pipelines=args.pipeline,
        tiers=args.tier or ["development", "evaluation"],
        benchmark_root=args.benchmark_root or DEFAULT_BENCHMARK_ROOT,
        generated_root=args.generated_root,
        result_root=args.result_root,
        analysis_root=args.analysis_root,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2))


def _reconstruct(args: argparse.Namespace) -> None:
    from app.controlled_diarization.benchmark import reconstruct_recipe

    print(json.dumps(reconstruct_recipe(args.recipe, args.output), indent=2))
