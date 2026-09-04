"""CLI for the bounded Prompt-7 production-candidate controller."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Mapping, Sequence

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_ROOT,
    LICENSE_DOCUMENT,
    MATRIX_PATH,
    RUNTIME_PATH,
    SELECTION_POLICY_DOCUMENT,
    TOOL_ROOT,
    scope_fields,
)
from . import controller
from .io import HardeningError, ensure_c


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        value = _dispatch(args)
        if value is not None:
            print(json.dumps(value, indent=2, sort_keys=True, default=str))
        if args.action == "health" and value is not None:
            return 0 if value.get("status") == "HEALTHY" else 1
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
        description="C:-only bounded Prompt-7 candidate selection and hardening"
    )
    parser.add_argument(
        "action",
        choices=(
            "validate-prerequisites",
            "select",
            "prepare-hardening",
            "run-hardening",
            "validate-hardening",
            "package",
            "update-program-state",
            "run-all",
            "stop",
            "status",
            "validate-completion",
            "validate-candidate",
            "validate-bundle",
            "health",
            "serve-health",
            "material-paths",
        ),
    )
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--prompt6-marker", type=Path)
    parser.add_argument("--prompt5-marker", type=Path)
    parser.add_argument("--amendment-path", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--program-state-path", type=Path, default=DEFAULT_PROGRAM_STATE
    )
    parser.add_argument(
        "--pi-deployment-steering-path",
        type=Path,
        default=DEFAULT_PI_DEPLOYMENT_STEERING,
    )
    parser.add_argument("--predecessor-record", type=Path)
    parser.add_argument("--completion-record", type=Path)
    parser.add_argument("--adapter-id")
    parser.add_argument("--adapter-contract-sha256")
    parser.add_argument(
        "--candidate-role", choices=("primary", "fallback", "alternative")
    )
    parser.add_argument("--pipeline-id")
    parser.add_argument("--bundle-root", type=Path)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    return parser


def _dispatch(args: argparse.Namespace) -> Mapping[str, object] | None:
    action = str(args.action)
    if action == "status":
        from .progress import publish_progress

        value = controller.status(workspace_root=args.workspace_root)
        value["program_progress"] = publish_progress(args.workspace_root)
        return value
    if action == "stop":
        return controller.stop(workspace_root=args.workspace_root)
    if action == "material-paths":
        return _material_paths(args)
    if action == "validate-candidate":
        from .packaging import validate_candidate_bundle

        if not args.candidate_role:
            raise HardeningError("ValidateCandidate requires --candidate-role")
        bundle = (
            controller.layout(args.workspace_root).root
            / "candidate_bundles"
            / args.candidate_role
        )
        return validate_candidate_bundle(bundle, pipeline_id=args.pipeline_id)
    if action == "validate-bundle":
        from .packaging import validate_candidate_bundle

        if args.bundle_root is None:
            raise HardeningError("validate-bundle requires --bundle-root")
        return validate_candidate_bundle(
            args.bundle_root,
            pipeline_id=args.pipeline_id,
        )
    if action == "health":
        from .health import health

        return health(
            workspace_root=args.workspace_root,
            candidate_role=args.candidate_role,
            pipeline_id=args.pipeline_id,
        )
    if action == "serve-health":
        from .health import serve

        serve(workspace_root=args.workspace_root, bind=args.bind, port=args.port)
        return None
    if action == "validate-completion":
        from .reporting import validate_completion

        return validate_completion(
            workspace_root=args.workspace_root,
            completion_record_path=(
                args.completion_record
                or _env_path("JP8_COMPLETION_RECORD")
                or controller.layout(args.workspace_root).completion
            ),
            program_state_path=args.program_state_path,
            expected_adapter_id=args.adapter_id or os.environ.get("JP8_ADAPTER_ID"),
            expected_adapter_contract_sha256=(
                args.adapter_contract_sha256
                or os.environ.get("JP8_ADAPTER_CONTRACT_SHA256")
            ),
        )
    if action == "update-program-state":
        return _finalize(args)
    if action == "run-all":
        return _run_all(args)

    common = _common(args)
    if action == "validate-prerequisites":
        return controller.validate_prerequisites(**common)
    if action == "select":
        return controller.select(**common)
    if action == "prepare-hardening":
        return controller.prepare_hardening(**common)
    if action == "run-hardening":
        return controller.run_hardening(**common)
    if action == "validate-hardening":
        return controller.validate_hardening(**common)
    if action == "package":
        return controller.package(**common)
    raise AssertionError(action)


def _run_all(args: argparse.Namespace) -> Mapping[str, object]:
    paths = controller.layout(args.workspace_root)
    from .progress import ProgressBridge, log_event
    from .reporting import validate_completion

    if paths.completion.is_file():
        _finalize(args)
        return validate_completion(
            workspace_root=paths.root,
            completion_record_path=paths.completion,
            program_state_path=args.program_state_path,
            expected_adapter_id=args.adapter_id or os.environ.get("JP8_ADAPTER_ID"),
            expected_adapter_contract_sha256=(
                args.adapter_contract_sha256
                or os.environ.get("JP8_ADAPTER_CONTRACT_SHA256")
            ),
        )
    common = _common(args)
    bridge = ProgressBridge(paths.root)
    bridge.start()
    log_event(paths.root, event="run_all_started", detail="RERUN_IDEMPOTENT")
    try:
        controller.validate_prerequisites(**common)
        controller.select(**common)
        controller.prepare_hardening(**common)
        execution = controller.run_hardening(**common)
        if execution.get("status") == "STOPPED":
            log_event(paths.root, event="run_all_stopped", detail=execution)
            bridge.stop(phase_hint="stopped_restartable")
            return execution
        controller.validate_hardening(**common)
        controller.package(**common)
        result = _finalize(args)
        validated = validate_completion(
            workspace_root=paths.root,
            completion_record_path=paths.completion,
            program_state_path=args.program_state_path,
            expected_adapter_id=args.adapter_id or os.environ.get("JP8_ADAPTER_ID"),
            expected_adapter_contract_sha256=(
                args.adapter_contract_sha256
                or os.environ.get("JP8_ADAPTER_CONTRACT_SHA256")
            ),
        )
        result = {**dict(result), "independent_validation": validated}
    except BaseException as exc:
        log_event(
            paths.root,
            event="run_all_blocked_or_interrupted",
            detail=f"{type(exc).__name__}: {exc}",
        )
        bridge.stop(phase_hint="blocked_or_interrupted")
        raise
    bridge.stop(phase_hint="complete")
    log_event(paths.root, event="run_all_complete", detail=paths.completion)
    return result


def _finalize(args: argparse.Namespace) -> Mapping[str, object]:
    from .reporting import finalize

    predecessor = (
        args.predecessor_record
        or args.prompt6_marker
        or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
    )
    if predecessor is None:
        raise HardeningError(
            "UpdateProgramState requires Prompt-6 predecessor path or "
            "JP8_PREDECESSOR_COMPLETION_PATH"
        )
    adapter_id = args.adapter_id or os.environ.get("JP8_ADAPTER_ID")
    adapter_sha = args.adapter_contract_sha256 or os.environ.get(
        "JP8_ADAPTER_CONTRACT_SHA256"
    )
    if not adapter_id or not adapter_sha:
        raise HardeningError(
            "UpdateProgramState requires JP8_ADAPTER_ID and JP8_ADAPTER_CONTRACT_SHA256"
        )
    return finalize(
        workspace_root=args.workspace_root,
        predecessor_record_path=predecessor,
        adapter_id=adapter_id,
        adapter_contract_sha256=adapter_sha,
        program_state_path=args.program_state_path,
        completion_record_path=(
            args.completion_record or _env_path("JP8_COMPLETION_RECORD")
        ),
    )


def _common(args: argparse.Namespace) -> dict[str, object]:
    marker = args.prompt6_marker or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
    if marker is None:
        raise HardeningError(
            "this action requires --prompt6-marker or JP8_PREDECESSOR_COMPLETION_PATH"
        )
    return {
        "workspace_root": args.workspace_root,
        "prompt6_marker": marker,
        "prompt5_marker": args.prompt5_marker,
        "amendment_path": args.amendment_path,
        "program_state_path": args.program_state_path,
        "pi_deployment_steering_path": args.pi_deployment_steering_path,
    }


def _material_paths(args: argparse.Namespace) -> dict[str, object]:
    paths = controller.layout(args.workspace_root)
    p6 = args.prompt6_marker or _env_path("JP8_PREDECESSOR_COMPLETION_PATH")
    discovered_checkpoints: list[Path] = []
    source_packages = (
        TOOL_ROOT / "app/full_pipeline",
        TOOL_ROOT / "app/full_pipeline_demo",
        TOOL_ROOT / "app/full_pipeline_production_hardening",
    )
    inputs = [
        ensure_c(args.program_state_path, label="program state"),
        ensure_c(args.amendment_path, label="amendment"),
        ensure_c(
            getattr(
                args,
                "pi_deployment_steering_path",
                DEFAULT_PI_DEPLOYMENT_STEERING,
            ),
            label="Raspberry Pi deployment steering",
        ),
        MATRIX_PATH.resolve(),
        RUNTIME_PATH.resolve(),
        SELECTION_POLICY_DOCUMENT.resolve(),
        LICENSE_DOCUMENT.resolve(),
        (TOOL_ROOT / "scripts/run_full_pipeline_demo.ps1").resolve(),
        (TOOL_ROOT / "scripts/run_full_pipeline_production_hardening.ps1").resolve(),
        *(
            path.resolve()
            for package in source_packages
            for path in sorted(package.glob("*.py"))
        ),
    ]
    if args.prompt5_marker:
        inputs.append(ensure_c(args.prompt5_marker, label="Prompt-5 completion"))
    if p6:
        p6_path = ensure_c(p6, label="Prompt-6 completion")
        upstream = _universal_inventory(p6_path)
        inputs.extend(upstream)
        from app.full_pipeline_evaluation.io import read_json

        for path in upstream:
            if path.name != "prompt5_authorization.json" or not path.is_file():
                continue
            prompt5_authorization = read_json(path)
            frozen_ref = prompt5_authorization.get("frozen_pipeline_configs")
            if isinstance(frozen_ref, Mapping):
                discovered_checkpoints.extend(
                    ensure_c(str(frozen_ref.get(key)), label=f"frozen {key}")
                    for key in ("path", "checksums_path")
                    if frozen_ref.get(key)
                )
    authorization = {}
    if paths.authorization.is_file():
        from app.full_pipeline_evaluation.io import read_json

        authorization = read_json(paths.authorization)
        for key in ("prompt5_completion", "prompt6_completion"):
            reference = authorization.get(key)
            if isinstance(reference, Mapping):
                inputs.append(
                    ensure_c(str(reference.get("path")), label=f"{key} record")
                )
        for key in (
            "deployment_steering",
            "predeclared_extended_set",
            "prompt5_deployment_evidence",
            "prompt6_deployment_evidence",
        ):
            reference = authorization.get(key)
            if isinstance(reference, Mapping) and reference.get("path"):
                inputs.append(ensure_c(str(reference["path"]), label=f"{key} input"))
        hardening = authorization.get("hardening_inputs")
        if isinstance(hardening, Mapping):
            for row in hardening.get("inputs", []):
                if isinstance(row, Mapping):
                    inputs.append(
                        ensure_c(str(row.get("path")), label="hardening input")
                    )
    frozen = authorization.get("frozen_pipeline_configs")
    if isinstance(frozen, Mapping):
        discovered_checkpoints.extend(
            ensure_c(str(frozen.get(key)), label=f"frozen {key}")
            for key in ("path", "checksums_path")
            if frozen.get(key)
        )
    bindings = authorization.get("runtime_candidate_bindings")
    if isinstance(bindings, Mapping):
        for binding in bindings.values():
            if not isinstance(binding, Mapping):
                continue
            for raw in binding.get("external_assets", []):
                if isinstance(raw, Mapping) and raw.get("path"):
                    discovered_checkpoints.append(
                        ensure_c(str(raw["path"]), label="runtime model asset")
                    )
            for raw in binding.get("environment_interpreters", []):
                if isinstance(raw, Mapping) and raw.get("interpreter_path"):
                    inputs.append(
                        ensure_c(
                            str(raw["interpreter_path"]),
                            label="runtime environment interpreter",
                        )
                    )
    checkpoints = discovered_checkpoints or [
        (TOOL_ROOT.parents[1] / "models/cache").resolve()
    ]
    classes = {
        "inputs": inputs,
        "workspaces": [paths.root],
        "caches": [
            (TOOL_ROOT / "JustPeachyResults/full_pipeline/_shared_cache").resolve()
        ],
        "temporary": [paths.root / "temp"],
        "logs": [paths.controller_log],
        "results": [paths.root / "evidence"],
        "reports": [paths.report],
        "packages": [paths.root / "packages", paths.root / "candidate_bundles"],
        "checkpoints": checkpoints,
    }
    return {
        "schema_version": "full-pipeline-production-hardening-material-paths.v1",
        **scope_fields(),
        "prompt_index": 7,
        "allowed_drive": "C:\\",
        "minimum_free_space_reserve_gib": 35,
        "classes": {
            key: list(dict.fromkeys(str(Path(path).resolve()) for path in values))
            for key, values in classes.items()
        },
    }


def _universal_inventory(completion_path: Path) -> list[Path]:
    """List universal metadata/evidence paths without opening outcome tables."""

    from app.full_pipeline_evaluation.io import read_json

    result = [completion_path]
    if not completion_path.is_file():
        return result
    completion = read_json(completion_path)
    predecessor = completion.get("predecessor")
    if isinstance(predecessor, Mapping):
        raw = predecessor.get("completion_record_path")
        if raw:
            p5 = ensure_c(str(raw), label="universal predecessor")
            result.extend(_universal_inventory(p5))
    manifest_ref = completion.get("artifact_manifest")
    if not isinstance(manifest_ref, Mapping) or not manifest_ref.get("path"):
        return result
    manifest_path = ensure_c(str(manifest_ref["path"]), label="artifact manifest")
    result.append(manifest_path)
    if not manifest_path.is_file():
        return result
    manifest = read_json(manifest_path)
    for raw in manifest.get("artifacts", []):
        if not isinstance(raw, Mapping) or not raw.get("path"):
            continue
        path = ensure_c(str(raw["path"]), label="upstream artifact")
        result.append(path)
        if path.name == "hardening_input_manifest.json" and path.is_file():
            hardening = read_json(path)
            for row in hardening.get("inputs", []):
                if isinstance(row, Mapping) and row.get("path"):
                    result.append(ensure_c(str(row["path"]), label="hardening WAV"))
    return result


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
