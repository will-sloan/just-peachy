"""CLI for preparing and operating the Common Voice breadth experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.speaker_breadth.collection import collect_results
from app.speaker_breadth.commonvoice import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROTOCOL_ROOT,
    prepare_protocol,
    protocol_plan,
    validate_extraction_bundle,
    validate_protocol,
)
from app.speaker_protocol.contracts import eligible_embedding_backends
from app.utils.paths import repository_root


def add_speaker_breadth_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "speaker-breadth", help="Prepare and operate the Common Voice 60+ breadth protocol"
    )
    commands = parser.add_subparsers(dest="speaker_breadth_command", required=True)

    prepare = commands.add_parser("prepare", help="Audit and freeze the source protocol")
    prepare.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    prepare.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    prepare.add_argument("--skip-deep-audio", action="store_true")
    prepare.set_defaults(func=_prepare)

    plan = commands.add_parser("plan", help="Print a no-inference experiment plan")
    plan.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    plan.add_argument("--backend", action="append", default=[])
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=_plan)

    validate = commands.add_parser("validate", help="Validate the frozen protocol")
    validate.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    validate.add_argument("--verify-audio-hashes", action="store_true")
    validate.set_defaults(func=_validate)

    runtime = commands.add_parser("backend-runtime", help="Resolve one backend environment")
    runtime.add_argument("--backend", required=True)
    runtime.set_defaults(func=_backend_runtime)

    extraction = commands.add_parser(
        "validate-extraction", help="Validate a restartable extraction bundle"
    )
    extraction.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    extraction.add_argument("--extraction-root", type=Path, required=True)
    extraction.add_argument("--backend", required=True)
    extraction.set_defaults(func=_validate_extraction)

    collect = commands.add_parser("collect", help="Collect compact finalist evidence")
    collect.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    collect.add_argument("--result-base", type=Path, required=True)
    collect.add_argument("--output-root", type=Path, required=True)
    collect.add_argument("--backend", action="append", default=[])
    collect.set_defaults(func=_collect)


def _prepare(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            prepare_protocol(
                args.protocol_root,
                config_path=args.config,
                validate_audio=not args.skip_deep_audio,
            ),
            indent=2,
        )
    )


def _plan(args: argparse.Namespace) -> None:
    value = protocol_plan(args.protocol_root, args.backend)
    if args.json:
        print(json.dumps(value, indent=2))
        return
    print(f"Protocol: {value['protocol_name']}")
    print(f"Protocol ID: {value['protocol_id']}")
    print(f"Eligible 60+ speakers: {value['eligible_60plus_speakers']}")
    print(f"Known speakers: {value['known_speakers']}")
    print(f"Calibration Unknown speakers: {value['calibration_unknown_speakers']}")
    print(f"Evaluation Unknown speakers: {value['evaluation_unknown_speakers']}")
    print(f"Enrollment clips: {value['enrollment_clips']}")
    print(f"Calibration probe clips: {value['calibration_probe_clips']}")
    print(f"Evaluation probe clips: {value['evaluation_probe_clips']}")
    print(f"Total selected clips: {value['total_selected_clips']}")
    print(f"Total audio: {float(value['total_audio_hours']):.3f} hours")
    print("Age categories:")
    for age, counts in value["age_categories"].items():
        print(f"  {age}: {counts['total']} speakers")
    print("Selected backends: " + (", ".join(value["selected_backends"]) or "none supplied"))
    print(f"Estimated Stage 10 extraction jobs: {value['estimated_extraction_jobs']}")
    print("Model inference performed: NO")


def _validate(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            validate_protocol(
                args.protocol_root, verify_audio_hashes=args.verify_audio_hashes
            ),
            indent=2,
        )
    )


def _backend_runtime(args: argparse.Namespace) -> None:
    values = eligible_embedding_backends(backend_ids={args.backend})
    if args.backend not in values:
        raise ValueError(f"backend is not currently qualified and locally available: {args.backend}")
    row = values[args.backend]
    profile = str(row["environment_profile"])
    repository = repository_root().path
    interpreter = (
        repository / ".venv" / "Scripts" / "python.exe"
        if profile == "core-cpu"
        else repository / ".stage8-envs" / profile / "Scripts" / "python.exe"
    )
    if not interpreter.is_file():
        raise FileNotFoundError(f"qualified environment interpreter is missing: {interpreter}")
    print(
        json.dumps(
            {
                "backend": args.backend,
                "environment_profile": profile,
                "python": str(interpreter),
                "qualification_status": row["qualification_status"],
            }
        )
    )


def _validate_extraction(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            validate_extraction_bundle(
                args.protocol_root, args.extraction_root, args.backend
            ),
            indent=2,
        )
    )


def _collect(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            collect_results(
                args.protocol_root,
                args.result_base,
                args.output_root,
                args.backend,
            ),
            indent=2,
        )
    )
