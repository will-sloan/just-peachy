"""CLI integration for Stage 11 diarization evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.diarization_evaluation.analysis import aggregate_native_results
from app.diarization_evaluation.artifacts import write_json_atomic
from app.diarization_evaluation.execution import (
    backend_status_report,
    run_diarization_unit,
    validate_diarization_result,
)
from app.diarization_evaluation.formats import parse_rttm, parse_uem
from app.diarization_evaluation.manifests import (
    build_native_diarization_manifest,
    read_native_manifest,
)
from app.diarization_evaluation.scoring import score_diarization


def add_diarization_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "diarization",
        help="Build, run, score, and validate Stage 11 native diarization",
    )
    commands = parser.add_subparsers(dest="diarization_command", required=True)

    build = commands.add_parser("build-manifest", help="Build an immutable native scoring view")
    build.add_argument("--tier", choices=("small", "standard", "large"), default="small")
    build.add_argument("--output-root", type=Path, default=None)
    build.set_defaults(func=_build_manifest)

    status = commands.add_parser("status", help="Report qualification and current availability")
    status.add_argument("--output", type=Path, default=None)
    status.set_defaults(func=_status)

    run = commands.add_parser("run", help="Run one authorized backend and scoring unit")
    run.add_argument("--manifest-root", required=True, type=Path)
    run.add_argument("--evaluation-unit-id", required=True)
    run.add_argument("--backend", required=True)
    run.add_argument("--output-root", required=True, type=Path)
    run.add_argument("--oracle-speaker-count-diagnostic", action="store_true")
    run.set_defaults(func=_run)

    score = commands.add_parser("score", help="Score compatible RTTM/UEM files")
    score.add_argument("--reference-rttm", required=True, type=Path)
    score.add_argument("--hypothesis-rttm", required=True, type=Path)
    score.add_argument("--uem", required=True, type=Path)
    score.add_argument("--output", required=True, type=Path)
    score.add_argument("--reference-incompatible-reason", default=None)
    score.add_argument(
        "--label-semantics",
        choices=("anonymous_diarization", "known_speaker", "speaker_change", "full_diarization"),
        default="anonymous_diarization",
    )
    score.set_defaults(func=_score)

    aggregate = commands.add_parser("aggregate", help="Build native grouped metrics")
    aggregate.add_argument("--result", action="append", type=Path, default=[])
    aggregate.add_argument("--results-root", type=Path, default=None)
    aggregate.add_argument("--output-root", required=True, type=Path)
    aggregate.set_defaults(func=_aggregate)

    validate = commands.add_parser("validate", help="Validate a Stage 11 manifest or result")
    validate.add_argument("--manifest-root", type=Path, default=None)
    validate.add_argument("--result-root", type=Path, default=None)
    validate.set_defaults(func=_validate)

    smoke = commands.add_parser("smoke", help="Run one native item in the current qualified environment")
    smoke.add_argument("--manifest-root", type=Path, default=None)
    smoke.add_argument("--output-root", type=Path, default=None)
    smoke.set_defaults(func=_smoke)


def _build_manifest(args: argparse.Namespace) -> None:
    output = args.output_root or Path("benchmarks") / "stage11" / args.tier
    print(json.dumps(build_native_diarization_manifest(output, tier=args.tier), indent=2))


def _status(args: argparse.Namespace) -> None:
    result = backend_status_report()
    if args.output is not None:
        write_json_atomic(args.output, result)
    print(json.dumps(result, indent=2))


def _run(args: argparse.Namespace) -> None:
    result = run_diarization_unit(
        args.manifest_root,
        args.evaluation_unit_id,
        args.backend,
        args.output_root,
        oracle_speaker_count_diagnostic=args.oracle_speaker_count_diagnostic,
    )
    print(json.dumps(result, indent=2))


def _score(args: argparse.Namespace) -> None:
    result = score_diarization(
        parse_rttm(args.reference_rttm),
        parse_rttm(args.hypothesis_rttm),
        parse_uem(args.uem),
        reference_compatible=args.reference_incompatible_reason is None,
        incompatibility_reason=args.reference_incompatible_reason,
        label_semantics=args.label_semantics,
    )
    write_json_atomic(args.output, result)
    print(json.dumps(result, indent=2))


def _aggregate(args: argparse.Namespace) -> None:
    roots = list(args.result)
    if args.results_root is not None:
        roots.extend(path.parent for path in args.results_root.rglob("run.json"))
    unique = sorted(set(path.resolve() for path in roots), key=str)
    print(json.dumps(aggregate_native_results(unique, args.output_root), indent=2))


def _validate(args: argparse.Namespace) -> None:
    if (args.manifest_root is None) == (args.result_root is None):
        raise ValueError("select exactly one of --manifest-root or --result-root")
    if args.result_root is not None:
        result = validate_diarization_result(args.result_root)
    else:
        rows = read_native_manifest(args.manifest_root / "native_diarization_manifest.parquet")
        result = {
            "valid": True,
            "evaluation_units": len(rows),
            "der_jer_eligible": sum(int(bool(row["der_jer_eligible"])) for row in rows),
            "voices_metrics_suppressed": all(
                not row["der_jer_eligible"] for row in rows if row["dataset"] == "voices"
            ),
        }
    print(json.dumps(result, indent=2))


def _smoke(args: argparse.Namespace) -> None:
    manifest_root = args.manifest_root or Path("benchmarks") / "stage11" / "small"
    if not (manifest_root / "native_diarization_manifest.parquet").is_file():
        build_native_diarization_manifest(manifest_root, tier="small")
    status = backend_status_report()
    executable = [row for row in status["backends"] if row["execution_allowed"]]
    if not executable:
        raise RuntimeError("no authorized diarization backend is executable in this environment")
    rows = read_native_manifest(manifest_root / "native_diarization_manifest.parquet")
    candidates = [
        row
        for row in rows
        if row["dataset"] == "ami"
        and row["stream_type"] == "array"
        and row["der_jer_eligible"]
        and 4.0 <= float(row["duration_sec"]) <= 12.0
    ]
    if not candidates:
        raise RuntimeError("no compatible AMI array smoke unit exists")
    unit = sorted(candidates, key=lambda row: str(row["evaluation_unit_id"]))[0]
    output = args.output_root or Path("runs") / "diarization_evaluation"
    summaries: list[dict[str, object]] = []
    for backend in executable:
        result_root = output / f"smoke_{backend['backend_id']}_{unit['evaluation_unit_id']}"
        if (result_root / "run.json").is_file():
            validation = validate_diarization_result(result_root)
            summaries.append({"backend_id": backend["backend_id"], "reused": True, **validation})
            continue
        run = run_diarization_unit(
            manifest_root,
            str(unit["evaluation_unit_id"]),
            str(backend["backend_id"]),
            result_root,
        )
        summaries.append(
            {
                "backend_id": backend["backend_id"],
                "reused": False,
                "evaluation_unit_id": run["evaluation_unit_id"],
                "status": run["status"],
            }
        )
    payload = {
        "schema_version": "diarization-real-smoke-summary.v1",
        "manifest_root": manifest_root.as_posix(),
        "evaluation_unit_id": unit["evaluation_unit_id"],
        "results": summaries,
        "unavailable_backends": [
            {
                "backend_id": row["backend_id"],
                "qualification_status": row["qualification_status"],
                "blockers": row["blockers"],
            }
            for row in status["backends"]
            if not row["execution_allowed"]
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output / "smoke_summary.json", payload)
    print(json.dumps(payload, indent=2))
