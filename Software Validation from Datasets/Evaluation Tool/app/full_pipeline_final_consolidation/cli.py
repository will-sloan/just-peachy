"""CLI for bounded Prompt-8 final consolidation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_ADAPTER_REGISTRY,
    DEFAULT_EXECUTION_POLICY_ADDENDUM,
    DEFAULT_LICENSE_DOCUMENT,
    DEFAULT_MATRIX,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_ROOT,
    DEFAULT_RUNTIME,
    DEFAULT_ZIP,
)
from . import controller
from .io import blocked_status


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        value = _dispatch(args)
        print(json.dumps(value, indent=2, sort_keys=True, default=str))
        if (
            args.action in {"run-all", "validate-completion"}
            and value.get("status") == "PASS"
        ):
            print()
            print("UPLOAD THIS FILE TO CHATGPT:")
            print(value["compact_zip_path"])
            print()
            print("SHA-256:")
            print(value["compact_zip_sha256"])
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "STOP_REQUESTED_BY_OPERATOR"}, indent=2))
        return 130
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": blocked_status(exc),
                    "error": f"{type(exc).__name__}: {exc}",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="C:-only bounded Prompt-8 ranking/reproducibility finalizer"
    )
    parser.add_argument(
        "action", choices=("run-all", "stop", "status", "validate-completion")
    )
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--zip-path", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--prompt7-marker", type=Path)
    parser.add_argument("--amendment-path", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--execution-policy-path", type=Path, default=DEFAULT_EXECUTION_POLICY_ADDENDUM
    )
    parser.add_argument(
        "--adapter-registry-path", type=Path, default=DEFAULT_ADAPTER_REGISTRY
    )
    parser.add_argument(
        "--pi-deployment-steering-path",
        type=Path,
        default=DEFAULT_PI_DEPLOYMENT_STEERING,
    )
    parser.add_argument(
        "--program-state-path", type=Path, default=DEFAULT_PROGRAM_STATE
    )
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--runtime-path", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument(
        "--license-document-path", type=Path, default=DEFAULT_LICENSE_DOCUMENT
    )
    parser.add_argument("--completion-record", type=Path)
    parser.add_argument("--progress-record", type=Path)
    parser.add_argument("--adapter-id")
    parser.add_argument("--adapter-contract-sha256")
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.adapter_id:
        os.environ["JP8_ADAPTER_ID"] = args.adapter_id
    if args.adapter_contract_sha256:
        os.environ["JP8_ADAPTER_CONTRACT_SHA256"] = args.adapter_contract_sha256
    if args.action == "stop":
        return controller.request_stop(workspace_root=args.workspace_root)
    if args.action == "status":
        return controller.status(
            workspace_root=args.workspace_root,
            output_root=args.output_root,
            zip_path=args.zip_path,
            completion_record=args.completion_record,
            progress_record=args.progress_record,
        )
    marker = args.prompt7_marker or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
    if args.action == "validate-completion":
        return controller.validate_final_completion(
            workspace_root=args.workspace_root,
            output_root=args.output_root,
            zip_path=args.zip_path,
            completion_record=args.completion_record,
            prompt7_marker=marker,
            program_state_path=args.program_state_path,
            adapter_registry_path=args.adapter_registry_path,
            pi_deployment_steering_path=args.pi_deployment_steering_path,
            expected_adapter_id=args.adapter_id or os.environ.get("JP8_ADAPTER_ID"),
            expected_adapter_contract_sha256=(
                args.adapter_contract_sha256
                or os.environ.get("JP8_ADAPTER_CONTRACT_SHA256")
            ),
        )
    return controller.run_all(
        workspace_root=args.workspace_root,
        output_root=args.output_root,
        zip_path=args.zip_path,
        prompt7_marker=marker,
        amendment_path=args.amendment_path,
        execution_policy_path=args.execution_policy_path,
        adapter_registry_path=args.adapter_registry_path,
        pi_deployment_steering_path=args.pi_deployment_steering_path,
        program_state_path=args.program_state_path,
        matrix_path=args.matrix_path,
        runtime_path=args.runtime_path,
        license_document_path=args.license_document_path,
        completion_record=args.completion_record,
        progress_record=args.progress_record,
    )


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


__all__ = ["main"]
