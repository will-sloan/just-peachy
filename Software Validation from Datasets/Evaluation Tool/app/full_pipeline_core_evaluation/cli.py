"""Command-line interface for the bounded Prompt-5 core evaluation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_ROOT,
)
from . import controller
from .io import CoreEvaluationError


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        value = _dispatch(args)
        print(json.dumps(value, indent=2, sort_keys=True, default=str))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "STOP_REQUESTED_BY_OPERATOR"}, indent=2))
        return 130
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="C:-only bounded Prompt-5 all-18 held-out core evaluation"
    )
    parser.add_argument(
        "action",
        choices=(
            "validate-freeze",
            "prepare-reduced",
            "run-accuracy",
            "validate-accuracy",
            "prepare-resources",
            "run-resources",
            "validate-resources",
            "analyze",
            "collect",
            "update-program-state",
            "run-all",
            "validate-completion",
            "status",
            "stop",
        ),
    )
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--prompt4-marker", type=Path)
    parser.add_argument("--amendment-path", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--program-state-path", type=Path, default=DEFAULT_PROGRAM_STATE
    )
    parser.add_argument(
        "--pi-deployment-steering-path",
        type=Path,
        default=DEFAULT_PI_DEPLOYMENT_STEERING,
    )
    parser.add_argument("--parallel-jobs", type=int, choices=(1, 2), default=2)
    parser.add_argument("--predecessor-record", type=Path)
    parser.add_argument("--adapter-id")
    parser.add_argument("--adapter-contract-sha256")
    return parser


def _dispatch(args: argparse.Namespace) -> MappingResult:
    action = args.action
    common = {
        "workspace_root": args.workspace_root,
        "prompt4_marker": _require_prompt4_marker(args),
        "amendment_path": args.amendment_path,
        "program_state_path": args.program_state_path,
        "pi_deployment_steering_path": args.pi_deployment_steering_path,
    }
    if action == "validate-freeze":
        return controller.validate_freeze(**common)
    if action == "prepare-reduced":
        return controller.prepare_reduced(**common)
    if action == "run-accuracy":
        return controller.run_accuracy(**common, parallel_jobs=args.parallel_jobs)
    if action == "validate-accuracy":
        return controller.validate_accuracy(**common)
    if action == "prepare-resources":
        return controller.prepare_resources(**common)
    if action == "run-resources":
        return controller.run_resources(**common)
    if action == "validate-resources":
        return controller.validate_resources(args.workspace_root)
    if action in {"analyze", "collect", "update-program-state"}:
        # Revalidate the immutable predecessor and selection before opening or
        # packaging result bytes. The program state remains at Prompt 4 until
        # the final update action succeeds.
        controller._require_prepared(  # noqa: SLF001
            args.workspace_root,
            prompt4_marker=common["prompt4_marker"],
            amendment_path=args.amendment_path,
            program_state_path=args.program_state_path,
            pi_deployment_steering_path=args.pi_deployment_steering_path,
        )
        if action == "analyze":
            # Import result reconstruction only after an explicit Analyze
            # request.  It reaches the scientific scorer stack and should not
            # delay Help, Status, or Stop.
            from .analysis import analyze

            return analyze(workspace_root=args.workspace_root)
        if action == "collect":
            from .reporting import collect

            return collect(workspace_root=args.workspace_root)
        predecessor = (
            args.predecessor_record
            or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
            or _env_path("JP8_PREDECESSOR_RECORD_PATH")
        )
        if predecessor is None:
            predecessor = common["prompt4_marker"]
        adapter_id = args.adapter_id or os.environ.get("JP8_ADAPTER_ID")
        adapter_sha = args.adapter_contract_sha256 or os.environ.get(
            "JP8_ADAPTER_CONTRACT_SHA256"
        )
        if not adapter_id or not adapter_sha:
            raise CoreEvaluationError(
                "UpdateProgramState requires adapter ID and contract SHA-256 "
                "arguments or JP8_ADAPTER_* environment variables"
            )
        from .reporting import update_program_state

        return update_program_state(
            workspace_root=args.workspace_root,
            predecessor_record_path=predecessor,
            adapter_id=adapter_id,
            adapter_contract_sha256=adapter_sha,
            program_state_path=args.program_state_path,
            completion_record_path=_env_path("JP8_COMPLETION_RECORD"),
        )
    if action == "run-all":
        from .analysis import analyze
        from .progress import ProgressBridge
        from .reporting import collect, update_program_state

        adapter_id = args.adapter_id or os.environ.get("JP8_ADAPTER_ID")
        adapter_sha = args.adapter_contract_sha256 or os.environ.get(
            "JP8_ADAPTER_CONTRACT_SHA256"
        )
        predecessor = (
            args.predecessor_record
            or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
            or common["prompt4_marker"]
        )
        if not adapter_id or not adapter_sha:
            raise CoreEvaluationError(
                "RunAll requires JP8_ADAPTER_ID and JP8_ADAPTER_CONTRACT_SHA256"
            )
        bridge = ProgressBridge(args.workspace_root)
        bridge.start()
        try:
            controller.validate_freeze(**common)
            controller.prepare_reduced(**common)
            controller.run_accuracy(**common, parallel_jobs=args.parallel_jobs)
            controller.validate_accuracy(**common)
            controller.prepare_resources(**common)
            controller.run_resources(**common)
            controller.validate_resources(args.workspace_root)
            analyze(workspace_root=args.workspace_root)
            collect(workspace_root=args.workspace_root)
            result = update_program_state(
                workspace_root=args.workspace_root,
                predecessor_record_path=predecessor,
                adapter_id=adapter_id,
                adapter_contract_sha256=adapter_sha,
                program_state_path=args.program_state_path,
                completion_record_path=_env_path("JP8_COMPLETION_RECORD"),
            )
        except BaseException:
            bridge.stop(phase_hint="blocked_or_interrupted")
            raise
        bridge.stop(phase_hint="complete")
        return result
    if action == "validate-completion":
        from .reporting import validate_completion

        completion_path = (
            _env_path("JP8_COMPLETION_RECORD")
            or controller.layout(args.workspace_root).completion_marker
        )
        return validate_completion(
            workspace_root=args.workspace_root,
            completion_record_path=completion_path,
            expected_adapter_id=args.adapter_id or os.environ.get("JP8_ADAPTER_ID"),
            expected_adapter_contract_sha256=(
                args.adapter_contract_sha256
                or os.environ.get("JP8_ADAPTER_CONTRACT_SHA256")
            ),
            program_state_path=args.program_state_path,
        )
    if action == "status":
        from .progress import publish_program_progress

        value = controller.status(workspace_root=args.workspace_root)
        value["program_progress"] = publish_program_progress(
            controller.layout(args.workspace_root)
        )
        return value
    if action == "stop":
        return controller.stop(workspace_root=args.workspace_root)
    raise AssertionError(action)


def _require_prompt4_marker(args: argparse.Namespace) -> Path:
    if args.action in {
        "status",
        "stop",
        "validate-resources",
        "validate-completion",
    }:
        return args.prompt4_marker or Path("C:/unused-prompt4-marker")
    value = (
        args.prompt4_marker
        or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
        or _env_path("JP8_PREDECESSOR_RECORD_PATH")
    )
    if value is None:
        raise CoreEvaluationError(
            f"{args.action} requires --prompt4-marker or JP8_PREDECESSOR_RECORD_PATH"
        )
    return value


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


MappingResult = dict[str, object]
