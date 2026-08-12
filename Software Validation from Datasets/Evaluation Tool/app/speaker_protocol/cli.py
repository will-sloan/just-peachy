"""CLI integration for Stage 10 speaker protocol operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.speaker_protocol.evaluation import (
    evaluate_protocol,
    observations_from_npz,
    validate_protocol_results,
)
from app.speaker_protocol.extraction import (
    extract_clean_protocol_embeddings,
    load_backend_identity,
)
from app.speaker_protocol.manifests import (
    build_protocol_manifests,
    validate_protocol_manifest_set,
)
from app.speaker_protocol.smoke import build_real_speaker_smoke


def add_speaker_protocol_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "speaker-protocol",
        help="Build and evaluate backend-specific speaker enrollment protocols",
    )
    commands = parser.add_subparsers(dest="speaker_protocol_command", required=True)

    build = commands.add_parser("build-manifests", help="Derive immutable Stage 10 manifests")
    build.add_argument("--tier", choices=("small", "standard", "large"), default="small")
    build.add_argument("--output-root", type=Path, default=None)
    build.set_defaults(func=_build)

    extract = commands.add_parser("extract", help="Extract clean embeddings in this environment")
    extract.add_argument("--manifest-root", required=True, type=Path)
    extract.add_argument("--component", required=True)
    extract.add_argument("--output-root", required=True, type=Path)
    extract.add_argument("--item-id", action="append", default=[])
    extract.set_defaults(func=_extract)

    evaluate = commands.add_parser("evaluate", help="Evaluate an extracted embedding bundle")
    evaluate.add_argument("--manifest-root", required=True, type=Path)
    evaluate.add_argument("--observation-bundle", required=True, type=Path)
    evaluate.add_argument("--backend-identity", required=True, type=Path)
    evaluate.add_argument("--output-root", required=True, type=Path)
    evaluate.add_argument("--allow-overwrite", action="store_true")
    evaluate.set_defaults(func=_evaluate)

    smoke = commands.add_parser("smoke", help="Run every qualified embedding backend")
    smoke.add_argument("--manifest-root", type=Path, default=None)
    smoke.add_argument("--output-root", type=Path, default=None)
    smoke.add_argument("--rerun", action="store_true")
    smoke.add_argument("--backend", action="append", default=[])
    smoke.set_defaults(func=_smoke)

    validate = commands.add_parser("validate", help="Validate manifests or protocol results")
    validate.add_argument("--manifest-root", type=Path, default=None)
    validate.add_argument("--result-root", type=Path, default=None)
    validate.set_defaults(func=_validate)


def _build(args: argparse.Namespace) -> None:
    output = args.output_root or Path("benchmarks") / "stage10" / args.tier
    print(json.dumps(build_protocol_manifests(output, tier=args.tier), indent=2))


def _extract(args: argparse.Namespace) -> None:
    result = extract_clean_protocol_embeddings(
        args.manifest_root,
        args.component,
        args.output_root,
        item_ids=set(args.item_id) or None,
    )
    print(
        json.dumps(
            {
                "backend_id": result["identity"].backend_id,
                "expected_items": result["expected_items"],
                "successful_items": result["successful_items"],
                "output_root": str(args.output_root),
            },
            indent=2,
        )
    )


def _evaluate(args: argparse.Namespace) -> None:
    identity = load_backend_identity(args.backend_identity)
    observations = observations_from_npz(args.observation_bundle, identity)
    metrics = evaluate_protocol(
        args.manifest_root,
        observations,
        identity,
        args.output_root,
        allow_overwrite=args.allow_overwrite,
    )
    print(json.dumps(metrics, indent=2))


def _smoke(args: argparse.Namespace) -> None:
    kwargs = {
        "rerun": args.rerun,
        "backend_ids": set(args.backend) or None,
    }
    if args.manifest_root is not None:
        kwargs["manifest_root"] = args.manifest_root
    if args.output_root is not None:
        kwargs["output_root"] = args.output_root
    payload = build_real_speaker_smoke(**kwargs)
    print(
        json.dumps(
            {
                "expected_backends": payload["expected_backends"],
                "passed": payload["passed"],
                "failed": payload["failed"],
            },
            indent=2,
        )
    )


def _validate(args: argparse.Namespace) -> None:
    if (args.manifest_root is None) == (args.result_root is None):
        raise ValueError("select exactly one of --manifest-root or --result-root")
    result = (
        validate_protocol_manifest_set(args.manifest_root)
        if args.manifest_root is not None
        else validate_protocol_results(args.result_root)
    )
    print(json.dumps(result, indent=2))
