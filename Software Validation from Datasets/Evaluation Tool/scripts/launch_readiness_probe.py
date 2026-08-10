"""Capture machine readiness or preflight every scenario in a worker assignment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.campaign_exchange.common import atomic_write_json  # noqa: E402
from app.launch_readiness import (  # noqa: E402
    LaunchReadinessError,
    collect_machine_profile,
    credential_readiness,
    preflight_worker_assignment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    machine = subparsers.add_parser(
        "machine", help="capture a privacy-safe machine profile"
    )
    _common(machine)
    machine.add_argument("--credential-name", action="append", default=[])
    machine.add_argument("--output", required=True, type=Path)

    credentials = subparsers.add_parser(
        "credentials",
        help="report only READY/MISSING for credential-gated backends",
    )
    credentials.add_argument("--output", type=Path)

    assignment = subparsers.add_parser(
        "assignment", help="preflight every scenario in one frozen worker assignment"
    )
    _common(assignment)
    assignment.add_argument("--campaign-root", required=True, type=Path)
    assignment.add_argument("--assignment", required=True, type=Path)
    assignment.add_argument("--machine-profile", type=Path)
    assignment.add_argument("--output", required=True, type=Path)
    assignment.add_argument("--estimated-rtf", type=float, default=0.235)
    assignment.add_argument("--estimated-rtf-low", type=float, default=0.20)
    assignment.add_argument("--estimated-rtf-high", type=float, default=0.35)
    assignment.add_argument("--minimum-free-disk-gb", type=float, default=5.0)
    assignment.add_argument(
        "--existence-only",
        action="store_true",
        help="skip audio-header decoding; diagnostic only and never use for final launch approval",
    )
    return parser


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--environment-profile", required=True)
    parser.add_argument("--output-root", required=True, type=Path)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "credentials":
            report = credential_readiness()
            if args.output:
                atomic_write_json(args.output.resolve(), report)
            for backend, status in report.items():
                print(f"{backend}: {status}")
            return 0 if all(value == "READY" for value in report.values()) else 2

        if args.action == "machine":
            profile = collect_machine_profile(
                machine_id=args.machine_id,
                repository_root=args.repository_root,
                project_root=args.project_root,
                environment_profile=args.environment_profile,
                output_root=args.output_root,
                credential_names=args.credential_name,
            )
            atomic_write_json(args.output.resolve(), profile)
            print(json.dumps(profile, indent=2))
            return 0

        profile = (
            json.loads(args.machine_profile.read_text(encoding="utf-8"))
            if args.machine_profile
            else collect_machine_profile(
                machine_id=args.machine_id,
                repository_root=args.repository_root,
                project_root=args.project_root,
                environment_profile=args.environment_profile,
                output_root=args.output_root,
            )
        )
        report = preflight_worker_assignment(
            campaign_root=args.campaign_root,
            assignment_path=args.assignment,
            repository_root=args.repository_root,
            project_root=args.project_root,
            machine_profile=profile,
            expected_environment_profile=args.environment_profile,
            estimated_rtf=args.estimated_rtf,
            estimated_rtf_low=args.estimated_rtf_low,
            estimated_rtf_high=args.estimated_rtf_high,
            minimum_free_disk_reserve_bytes=int(args.minimum_free_disk_gb * 1024**3),
            inspect_audio_headers=not args.existence_only,
        )
        atomic_write_json(args.output.resolve(), report)
        print(json.dumps(report, indent=2))
        return 0 if report["verdict"] == "READY_TO_LAUNCH" else 2
    except (LaunchReadinessError, FileNotFoundError, ValueError, KeyError) as exc:
        print(f"launch preflight error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
