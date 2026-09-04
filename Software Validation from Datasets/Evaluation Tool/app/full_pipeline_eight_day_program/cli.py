"""Command-line interface for the C:-only automatic program controller."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Sequence

from .contracts import template_configuration
from .controller import ProgramController
from .monitor import render_status
from .storage import ProgramContractError, atomic_write_json, resolve_c_only_path


def _default_tool_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_config() -> Path:
    return (
        _default_tool_root()
        / "runs/full_pipeline_program/EIGHT_DAY_ADAPTERS.json"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.full_pipeline_eight_day_program",
        description=(
            "Validate, run, stop, or monitor the bounded Prompt 4–8 C:-only program."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    template = subparsers.add_parser(
        "write-template", help="Write a safe all-NOT_READY adapter template."
    )
    template.add_argument("--output", type=Path, default=_default_config())
    template.add_argument("--evaluation-tool-root", type=Path, default=_default_tool_root())

    for name, help_text in (
        ("validate-config", "Validate amendment, adapters, paths, and fixed budgets."),
        ("run", "Run/recover one controller and transition automatically after gates."),
        ("status", "Print one read-only status snapshot."),
        ("monitor", "Continuously render percentage, ETA, storage, and stages."),
        ("stop", "Write a durable graceful-stop request."),
        ("validate-completions", "Revalidate the recorded completed-stage prefix."),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("--adapter-config", type=Path, default=_default_config())
        if name in {"validate-config", "status", "validate-completions"}:
            subparser.add_argument("--json", action="store_true")
        if name == "monitor":
            subparser.add_argument("--follow", action="store_true")
            subparser.add_argument("--interval-seconds", type=float, default=30.0)
            subparser.add_argument("--json", action="store_true")
        if name == "stop":
            subparser.add_argument(
                "--reason", default="user_requested_graceful_stop", help="Audit reason."
            )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "write-template":
            root = resolve_c_only_path(
                args.evaluation_tool_root,
                must_exist=True,
                label="evaluation tool root",
            )
            output = resolve_c_only_path(args.output, base=Path.cwd(), label="template output")
            if output.exists():
                raise ProgramContractError(
                    f"Refusing to overwrite an existing adapter configuration: {output}"
                )
            atomic_write_json(output, template_configuration(evaluation_tool_root=root))
            print(json.dumps({"status": "CREATED_NOT_READY_TEMPLATE", "path": str(output)}, indent=2))
            return 0

        controller = ProgramController(args.adapter_config)
        if args.command == "validate-config":
            payload = controller.validate_configuration()
            _print(payload, as_json=args.json)
            return 0
        if args.command == "run":
            status = controller.run()
            print(status)
            return {"COMPLETE": 0, "NOT_READY": 3, "STOPPED": 4}.get(status, 2)
        if args.command == "status":
            payload = controller.status()
            _print(payload, as_json=args.json)
            return 0
        if args.command == "validate-completions":
            payload = controller.validate_completed_prefix()
            _print(payload, as_json=args.json)
            return 0
        if args.command == "stop":
            payload = controller.request_stop(reason=args.reason)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "monitor":
            if not 2.0 <= args.interval_seconds <= 3600.0:
                raise ProgramContractError("interval-seconds must be between 2 and 3600")
            while True:
                payload = controller.status()
                if args.json:
                    print(json.dumps(payload, sort_keys=True), flush=True)
                else:
                    if args.follow:
                        os.system("cls" if os.name == "nt" else "clear")
                    print(render_status(payload), flush=True)
                if not args.follow or payload.get("status") in {
                    "COMPLETE_FULL_PIPELINE_PROGRAM_REDUCED_8DAY_V1",
                    "BLOCKED_CONTRACT_VALIDATION",
                    "BLOCKED_C_DRIVE_RESERVE_35_GIB",
                    "STOPPED",
                    "STOP_TIMEOUT",
                    "NOT_READY",
                }:
                    return 0
                time.sleep(args.interval_seconds)
        raise AssertionError(args.command)
    except ProgramContractError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Monitor/controller interrupted; use the Stop action for a graceful stage stop.")
        return 130


def _print(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_status(payload) if "overall_percentage" in payload else payload)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
