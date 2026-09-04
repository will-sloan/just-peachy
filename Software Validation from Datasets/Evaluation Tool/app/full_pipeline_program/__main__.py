"""Command-line entry point for the full-pipeline program lock."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .validator import ProgramLockValidationError, validate_program_lock


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.full_pipeline_program",
        description="Validate the read-only Just-Peachy full-pipeline program lock.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser(
        "validate", help="Validate matrix, contracts, provenance anchors, and state."
    )
    validate.add_argument(
        "--evaluation-root",
        type=Path,
        default=None,
        help="Evaluation Tool root; defaults to the root containing this package.",
    )
    validate.add_argument(
        "--verify-assets",
        action="store_true",
        help="Also hash the locked local model files and trees; never loads a model.",
    )
    validate.add_argument(
        "--json", action="store_true", help="Print the validation summary as JSON."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "validate":  # pragma: no cover - argparse owns this guard.
        raise AssertionError(args.command)
    try:
        summary = validate_program_lock(
            evaluation_root=args.evaluation_root,
            verify_assets=bool(args.verify_assets),
        )
    except ProgramLockValidationError as exc:
        payload = {"status": "FAIL", "errors": exc.errors}
        print(json.dumps(payload, indent=2) if args.json else exc)
        return 1
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "PASS full pipeline program lock: "
            f"{summary['matrix_count']} pipelines, "
            f"{summary['contract_count']} public contracts, "
            f"{summary['source_hashes_checked']} source hashes checked, "
            f"assets={'verified' if summary['assets_verified'] else 'not requested'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

