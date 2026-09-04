"""CLI integration for Stage 10 speaker protocol operations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from app.speaker_protocol.evaluation import (
    evaluate_protocol,
    observations_from_npz,
    validate_protocol_results,
)
from app.speaker_protocol.contracts import DEFAULT_POLICY_PATH
from app.speaker_protocol.extraction import (
    extract_clean_protocol_embeddings,
    load_backend_identity,
)
from app.speaker_protocol.manifests import (
    build_protocol_manifests,
    validate_protocol_manifest_set,
)
from app.speaker_protocol.smoke import build_real_speaker_smoke
from app.speaker_protocol.progress import EvaluationProgress


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
    evaluate.add_argument("--workers", type=int, default=1)
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
    progress = EvaluationProgress(args.output_root, backend=identity.backend_id, workers=args.workers)
    try:
        progress.update("LOADING_OBSERVATIONS", force=True)
        observations = observations_from_npz(args.observation_bundle, identity)
        metrics = evaluate_protocol(
            args.manifest_root,
            observations,
            identity,
            args.output_root,
            allow_overwrite=args.allow_overwrite,
            workers=args.workers,
            progress=progress,
            execution_provenance={
                "evaluation_git_sha": _git_sha(),
                "evaluation_git_dirty": _git_dirty(),
                "observation_bundle_path": str(args.observation_bundle.resolve()),
                "observation_bundle_sha256": _file_sha256(args.observation_bundle),
                "backend_identity_path": str(args.backend_identity.resolve()),
                "scientific_policy_path": str(DEFAULT_POLICY_PATH.resolve()),
                "scientific_policy_sha256": _file_sha256(DEFAULT_POLICY_PATH),
            },
        )
    except Exception as exc:
        progress.fail(str(exc))
        raise
    print(json.dumps(metrics, indent=2))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _git_dirty() -> bool | None:
    completed = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    return bool(completed.stdout.strip()) if completed.returncode == 0 else None


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
