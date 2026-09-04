"""Command line for the additive bounded Prompt-6 controller."""

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
    PROMPT6_COMPLETION_MARKER,
    PI_DEPLOYMENT_STEERING_SHA256,
)
from . import controller
from .io import ExtendedEvaluationError, read_json, sha256_file


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
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
                {"status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="C:-only bounded Prompt-6 extended full-pipeline evaluation"
    )
    parser.add_argument(
        "action",
        choices=(
            "validate-prerequisite",
            "prepare",
            "run-accuracy",
            "run-resources",
            "validate-terminal",
            "analyze",
            "collect",
            "finalize",
            "run-all",
            "validate-completion",
            "status",
            "stop",
        ),
    )
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--predecessor-record", type=Path)
    parser.add_argument("--predecessor-sha256")
    parser.add_argument(
        "--program-state-path", type=Path, default=DEFAULT_PROGRAM_STATE
    )
    parser.add_argument("--amendment-path", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--pi-deployment-steering-path",
        type=Path,
        default=(
            _env_path("JP8_PI_DEPLOYMENT_STEERING_PATH")
            or DEFAULT_PI_DEPLOYMENT_STEERING
        ),
    )
    parser.add_argument(
        "--pi-deployment-steering-sha256",
        default=(
            os.environ.get("JP8_PI_DEPLOYMENT_STEERING_SHA256")
            or PI_DEPLOYMENT_STEERING_SHA256
        ),
    )
    parser.add_argument("--parallel-jobs", type=int, choices=(1, 2), default=2)
    parser.add_argument("--adapter-id")
    parser.add_argument("--adapter-contract-sha256")
    parser.add_argument("--completion-record", type=Path)
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    action = args.action
    if action == "status":
        return controller.status(workspace_root=args.workspace_root)
    if action == "stop":
        return controller.stop(workspace_root=args.workspace_root)
    if action == "validate-terminal":
        return controller.validate_terminal(workspace_root=args.workspace_root)
    if action == "validate-completion":
        from .reporting import validate_completion

        return validate_completion(
            workspace_root=args.workspace_root,
            completion_record_path=(
                args.completion_record
                or _env_path("JP8_COMPLETION_RECORD")
                or controller.layout(args.workspace_root).completion
            ),
            expected_adapter_id=args.adapter_id or os.environ.get("JP8_ADAPTER_ID"),
            expected_adapter_contract_sha256=(
                args.adapter_contract_sha256
                or os.environ.get("JP8_ADAPTER_CONTRACT_SHA256")
            ),
            program_state_path=args.program_state_path,
            deployment_steering_path=args.pi_deployment_steering_path,
            deployment_steering_sha256=args.pi_deployment_steering_sha256,
        )

    predecessor, predecessor_sha = _predecessor(args)
    common = {
        "workspace_root": args.workspace_root,
        "predecessor_path": predecessor,
        "predecessor_sha256": predecessor_sha,
        "program_state_path": args.program_state_path,
        "amendment_path": args.amendment_path,
        "deployment_steering_path": args.pi_deployment_steering_path,
        "deployment_steering_sha256": args.pi_deployment_steering_sha256,
    }
    if action == "validate-prerequisite":
        return controller.validate_prerequisite(
            predecessor_path=predecessor,
            predecessor_sha256=predecessor_sha,
            program_state_path=args.program_state_path,
            amendment_path=args.amendment_path,
            deployment_steering_path=args.pi_deployment_steering_path,
            deployment_steering_sha256=args.pi_deployment_steering_sha256,
        )
    if action == "prepare":
        return controller.prepare(**common)
    if action == "run-accuracy":
        return controller.run_accuracy(**common, parallel_jobs=args.parallel_jobs)
    if action == "run-resources":
        return controller.run_resources(**common)
    if action in {"analyze", "collect", "finalize"}:
        controller._require_prepared(  # noqa: SLF001 - command admission boundary
            args.workspace_root,
            predecessor_path=predecessor,
            predecessor_sha256=predecessor_sha,
            program_state_path=args.program_state_path,
            amendment_path=args.amendment_path,
            deployment_steering_path=args.pi_deployment_steering_path,
            deployment_steering_sha256=args.pi_deployment_steering_sha256,
        )
        if action == "analyze":
            from .analysis import analyze

            return analyze(workspace_root=args.workspace_root)
        if action == "collect":
            from .reporting import collect

            return collect(workspace_root=args.workspace_root)
        return _finalize(args, predecessor, predecessor_sha)
    if action == "run-all":
        return _run_all(args, common, predecessor, predecessor_sha)
    raise AssertionError(action)


def _run_all(
    args: argparse.Namespace,
    common: dict[str, object],
    predecessor: Path,
    predecessor_sha: str,
) -> dict[str, object]:
    paths = controller.layout(args.workspace_root)
    if paths.completion.is_file():
        state = read_json(args.program_state_path)
        if state.get("status") == PROMPT6_COMPLETION_MARKER:
            from .reporting import validate_completion

            return validate_completion(
                workspace_root=args.workspace_root,
                completion_record_path=paths.completion,
                expected_adapter_id=args.adapter_id or os.environ.get("JP8_ADAPTER_ID"),
                expected_adapter_contract_sha256=(
                    args.adapter_contract_sha256
                    or os.environ.get("JP8_ADAPTER_CONTRACT_SHA256")
                ),
                program_state_path=args.program_state_path,
                deployment_steering_path=args.pi_deployment_steering_path,
                deployment_steering_sha256=args.pi_deployment_steering_sha256,
            )
        # A crash may occur after the immutable completion envelope is written
        # but before PROGRAM_STATE is advanced. Finalize is safe to replay.
        return _finalize(args, predecessor, predecessor_sha)

    controller.validate_prerequisite(
        predecessor_path=predecessor,
        predecessor_sha256=predecessor_sha,
        program_state_path=args.program_state_path,
        amendment_path=args.amendment_path,
        deployment_steering_path=args.pi_deployment_steering_path,
        deployment_steering_sha256=args.pi_deployment_steering_sha256,
    )
    controller.prepare(**common)
    accuracy = controller.run_accuracy(**common, parallel_jobs=args.parallel_jobs)
    if accuracy.get("status") != "COMPLETE":
        return accuracy
    resources = controller.run_resources(**common)
    if resources.get("status") != "COMPLETE":
        return resources
    terminal = controller.validate_terminal(workspace_root=args.workspace_root)
    if terminal.get("status") != "PASS":
        return terminal
    from .analysis import analyze
    from .reporting import collect

    analyze(workspace_root=args.workspace_root)
    collect(workspace_root=args.workspace_root)
    return _finalize(args, predecessor, predecessor_sha)


def _finalize(
    args: argparse.Namespace, predecessor: Path, predecessor_sha: str
) -> dict[str, object]:
    adapter_id = args.adapter_id or os.environ.get("JP8_ADAPTER_ID")
    adapter_sha = args.adapter_contract_sha256 or os.environ.get(
        "JP8_ADAPTER_CONTRACT_SHA256"
    )
    if not adapter_id or not adapter_sha:
        raise ExtendedEvaluationError(
            "Finalize requires JP8_ADAPTER_ID and JP8_ADAPTER_CONTRACT_SHA256"
        )
    from .reporting import finalize

    return finalize(
        workspace_root=args.workspace_root,
        predecessor_record_path=predecessor,
        predecessor_record_sha256=predecessor_sha,
        adapter_id=adapter_id,
        adapter_contract_sha256=adapter_sha,
        program_state_path=args.program_state_path,
        completion_record_path=(
            args.completion_record or _env_path("JP8_COMPLETION_RECORD")
        ),
        deployment_steering_path=args.pi_deployment_steering_path,
        deployment_steering_sha256=args.pi_deployment_steering_sha256,
    )


def _predecessor(args: argparse.Namespace) -> tuple[Path, str]:
    path = (
        args.predecessor_record
        or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
        or _env_path("JP8_PREDECESSOR_RECORD_PATH")
    )
    if path is None:
        raise ExtendedEvaluationError(
            f"{args.action} requires the orchestrator-supplied Prompt-5 predecessor path"
        )
    claimed = (
        args.predecessor_sha256
        or os.environ.get("JP8_PREDECESSOR_COMPLETION_SHA256")
        or os.environ.get("JP8_PREDECESSOR_RECORD_SHA256")
    )
    if not claimed:
        raise ExtendedEvaluationError(
            f"{args.action} requires the orchestrator-supplied Prompt-5 predecessor SHA-256"
        )
    # Do not silently substitute a locally discovered hash: exact path/hash
    # binding is the automatic stage-chain contract.
    if path.is_file() and sha256_file(path) != claimed.casefold():
        raise ExtendedEvaluationError("supplied Prompt-5 predecessor hash differs")
    return path, claimed.casefold()


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
