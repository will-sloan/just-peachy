"""CLI for the scientific enrollment and live-identification duration study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.speaker_enrollment.analysis import analyze_results
from app.speaker_enrollment.collection import collect_results
from app.speaker_enrollment.evaluation import evaluate_configurations, validate_configuration_result
from app.speaker_enrollment.extraction import validate_embedding_cache
from app.speaker_enrollment.protocol import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_SOURCE_PROTOCOL_ROOT,
    audit_source_protocol,
    prepare_protocol,
    protocol_plan,
    required_slice_ids,
    resolve_phase_configurations,
    validate_protocol,
)
from app.speaker_protocol.contracts import eligible_embedding_backends
from app.utils.paths import repository_root


PHASES = ("EnrollmentCount", "EnrollmentDuration", "Aggregation", "ProbeDuration", "JointFrontier")


def add_speaker_enrollment_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "speaker-enrollment", help="Operate the frozen enrollment and live-duration study"
    )
    commands = parser.add_subparsers(dest="speaker_enrollment_command", required=True)

    audit = commands.add_parser("audit", help="Measure source feasibility without inference")
    _source_args(audit)
    audit.set_defaults(func=_audit)

    prepare = commands.add_parser("prepare", help="Freeze the paired cohort and slice manifests")
    _protocol_args(prepare)
    prepare.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    prepare.set_defaults(func=_prepare)

    plan = commands.add_parser("plan", help="Print phase-specific workload without inference")
    _protocol_args(plan)
    plan.add_argument("--phase", choices=("All", *PHASES), default="All")
    plan.add_argument("--backend", action="append", default=[])
    plan.set_defaults(func=_plan)

    validate = commands.add_parser("validate", help="Validate protocol, source paths, and backend eligibility")
    _protocol_args(validate)
    validate.add_argument("--backend", action="append", default=[])
    validate.set_defaults(func=_validate)

    runtime = commands.add_parser("backend-runtime", help="Resolve a qualified backend environment")
    runtime.add_argument("--backend", required=True)
    runtime.set_defaults(func=_backend_runtime)

    slices = commands.add_parser("required-slices", help="Write exact slice IDs for one phase")
    _protocol_args(slices)
    _phase_args(slices)
    slices.add_argument("--output", required=True, type=Path)
    slices.set_defaults(func=_required_slices)

    cache = commands.add_parser("validate-cache", help="Validate the per-slice embedding cache")
    _protocol_args(cache)
    _phase_args(cache)
    cache.add_argument("--backend", required=True)
    cache.add_argument("--cache-root", required=True, type=Path)
    cache.set_defaults(func=_validate_cache)

    evaluate = commands.add_parser("evaluate", help="Calibrate and evaluate one phase")
    _protocol_args(evaluate)
    _phase_args(evaluate)
    evaluate.add_argument("--backend", required=True)
    evaluate.add_argument("--cache-root", required=True, type=Path)
    evaluate.add_argument("--result-root", required=True, type=Path)
    evaluate.set_defaults(func=_evaluate)

    result = commands.add_parser("validate-result", help="Validate one configuration result")
    result.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    result.add_argument("--result-root", required=True, type=Path)
    result.set_defaults(func=_validate_result)

    status = commands.add_parser("status", help="Summarize completed and partial phase results")
    status.add_argument("--result-base", required=True, type=Path)
    status.add_argument("--backend", action="append", default=[])
    status.set_defaults(func=_status)

    analyze = commands.add_parser("analyze", help="Build scientific tables, intervals, and plots")
    analyze.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    analyze.add_argument("--result-base", required=True, type=Path)
    analyze.add_argument("--output-root", required=True, type=Path)
    analyze.add_argument("--backend", action="append", default=[])
    analyze.add_argument("--bootstrap-repetitions", type=int, default=None)
    analyze.set_defaults(func=_analyze)

    collect = commands.add_parser("collect", help="Collect compact evidence for ChatGPT analysis")
    _protocol_args(collect)
    collect.add_argument("--result-base", required=True, type=Path)
    collect.add_argument("--analysis-root", required=True, type=Path)
    collect.add_argument("--output-root", required=True, type=Path)
    collect.add_argument("--backend", action="append", default=[])
    collect.set_defaults(func=_collect)

    smoke = commands.add_parser("smoke", help="Run a bounded NON-SCIENTIFIC synthetic contract smoke")
    smoke.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    smoke.add_argument("--output-root", required=True, type=Path)
    smoke.set_defaults(func=_smoke)


def _protocol_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    parser.add_argument("--source-protocol-root", type=Path, default=DEFAULT_SOURCE_PROTOCOL_ROOT)


def _source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-protocol-root", type=Path, default=DEFAULT_SOURCE_PROTOCOL_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)


def _phase_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--reference-enrollment-configuration-id", default="")
    parser.add_argument("--decision-gate", type=Path, default=None)


def _audit(args: argparse.Namespace) -> None:
    print(json.dumps(audit_source_protocol(args.source_protocol_root, config_path=args.config), indent=2))


def _prepare(args: argparse.Namespace) -> None:
    print(json.dumps(prepare_protocol(args.protocol_root, source_protocol_root=args.source_protocol_root, config_path=args.config), indent=2))


def _plan(args: argparse.Namespace) -> None:
    print(json.dumps(protocol_plan(args.protocol_root, source_protocol_root=args.source_protocol_root, backends=args.backend, phase=args.phase), indent=2))


def _validate(args: argparse.Namespace) -> None:
    result = validate_protocol(args.protocol_root, source_protocol_root=args.source_protocol_root)
    eligible = eligible_embedding_backends(backend_ids=set(args.backend)) if args.backend else {}
    missing = sorted(set(args.backend) - set(eligible))
    if missing:
        raise ValueError(f"backends are not qualified and locally available: {missing}")
    result["backend_eligibility"] = {key: value["qualification_status"] for key, value in eligible.items()}
    print(json.dumps(result, indent=2))


def _backend_runtime(args: argparse.Namespace) -> None:
    values = eligible_embedding_backends(backend_ids={args.backend})
    if args.backend not in values:
        raise ValueError(f"backend is not currently qualified and locally available: {args.backend}")
    row = values[args.backend]
    profile = str(row["environment_profile"])
    repository = repository_root().path
    interpreter = repository / ".venv" / "Scripts" / "python.exe" if profile == "core-cpu" else repository / ".stage8-envs" / profile / "Scripts" / "python.exe"
    if not interpreter.is_file():
        raise FileNotFoundError(f"qualified environment interpreter is missing: {interpreter}")
    print(json.dumps({"backend": args.backend, "environment_profile": profile, "python": str(interpreter), "qualification_status": row["qualification_status"]}))


def _resolve(args: argparse.Namespace) -> list[dict[str, object]]:
    return resolve_phase_configurations(
        args.protocol_root,
        args.phase,
        reference_enrollment_configuration_id=args.reference_enrollment_configuration_id,
        decision_gate=args.decision_gate,
    )


def _required_slices(args: argparse.Namespace) -> None:
    configurations = _resolve(args)
    values = sorted(required_slice_ids(args.protocol_root, configurations))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(values) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"phase": args.phase, "configurations": len(configurations), "unique_slices": len(values), "output": str(args.output)}, indent=2))


def _validate_cache(args: argparse.Namespace) -> None:
    configurations = _resolve(args)
    print(json.dumps(validate_embedding_cache(args.protocol_root, args.backend, args.cache_root, required_slice_ids(args.protocol_root, configurations)), indent=2))


def _evaluate(args: argparse.Namespace) -> None:
    configurations = _resolve(args)
    if args.phase in {"ProbeDuration", "JointFrontier"}:
        references = {str(row.get("reference_configuration_id", "")) for row in configurations}
        completed = {path.parent.name for path in args.result_root.glob("phase_*/*/configuration_result.json")}
        missing = sorted(references - completed)
        if missing:
            raise ValueError(f"selected reference configurations have not completed for this backend: {missing}")
    print(json.dumps(evaluate_configurations(args.protocol_root, configurations, args.backend, args.cache_root, args.result_root), indent=2))


def _validate_result(args: argparse.Namespace) -> None:
    print(json.dumps(validate_configuration_result(args.result_root, protocol_root=args.protocol_root), indent=2))


def _status(args: argparse.Namespace) -> None:
    rows = []
    for backend in args.backend:
        root = args.result_base / backend
        for phase_dir in ("phase_a_enrollment_count", "phase_b_enrollment_duration", "phase_c_aggregation", "phase_d_probe_duration", "phase_e_joint_frontier"):
            phase_root = root / phase_dir
            completed = len(list(phase_root.glob("*/configuration_result.json"))) if phase_root.is_dir() else 0
            partial = len([path for path in phase_root.glob("*") if path.is_dir()]) - completed if phase_root.is_dir() else 0
            rows.append({"backend": backend, "phase": phase_dir, "completed": completed, "partial": max(0, partial)})
    print(json.dumps({"schema_version": "speaker-enrollment-status.v1", "rows": rows}, indent=2))


def _analyze(args: argparse.Namespace) -> None:
    if not args.backend:
        raise ValueError("Analyze requires one or more --backend values")
    print(json.dumps(analyze_results(args.protocol_root, args.result_base, args.output_root, args.backend, bootstrap_repetitions=args.bootstrap_repetitions), indent=2))


def _collect(args: argparse.Namespace) -> None:
    if not args.backend:
        raise ValueError("Collect requires one or more --backend values")
    print(json.dumps(collect_results(args.protocol_root, args.source_protocol_root, args.result_base, args.analysis_root, args.output_root, args.backend), indent=2))


def _smoke(args: argparse.Namespace) -> None:
    from app.speaker_enrollment.smoke import run_smoke

    print(json.dumps(run_smoke(args.protocol_root, args.output_root), indent=2))
