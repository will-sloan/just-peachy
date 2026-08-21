"""CLI surface for the Common Voice 60+ ASR campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import analyze
from .collection import collect, validate_collection
from .contracts import (
    DEFAULT_PROTOCOL_ROOT,
    MODEL_COMPONENT_IDS,
    campaign_identity,
    default_collection_root,
    default_result_root,
    default_smoke_collection_root,
    default_smoke_result_root,
    resolve_models,
)
from .protocol import audit_source, prepare_protocol, protocol_plan, validate_protocol
from .runner import run_backend, status, validate_backend


def add_asr_commonvoice_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "asr-commonvoice", help="Common Voice 60+ three-ASR generalization campaign"
    )
    actions = parser.add_subparsers(dest="asr_commonvoice_action", required=True)
    for name in ("audit", "prepare", "plan", "validate", "paths", "status", "analyze", "collect"):
        child = actions.add_parser(name)
        _common(child)
        child.set_defaults(func=_COMMANDS[name])
    backend = actions.add_parser("run-backend")
    _common(backend)
    backend.add_argument("--component-id", required=True, choices=MODEL_COMPONENT_IDS)
    backend.add_argument("--parallel-models", type=int, choices=(1, 2, 3), default=1)
    backend.set_defaults(func=_command_run_backend)


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    parser.add_argument("--result-root", type=Path, default=None)
    parser.add_argument("--collection-root", type=Path, default=None)
    parser.add_argument("--verify-audio-hashes", action="store_true")
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Use isolated NON-SCIENTIFIC SMOKE roots")


def _paths(args: argparse.Namespace) -> tuple[dict[str, object], Path, Path]:
    protocol = validate_protocol(args.protocol_root)
    smoke = bool(getattr(args, "smoke", False))
    result = args.result_root.resolve() if args.result_root else (default_smoke_result_root(protocol) if smoke else default_result_root(protocol))
    collection = args.collection_root.resolve() if args.collection_root else (default_smoke_collection_root(protocol) if smoke else default_collection_root(protocol))
    return protocol, result, collection


def _command_audit(args: argparse.Namespace) -> None:
    value = audit_source(verify_audio_hashes=args.verify_audio_hashes)
    value.pop("eligible_rows", None)
    value.pop("exclusions", None)
    value["models"] = resolve_models()
    value["all_model_assets_ready"] = all(row["asset_ready"] for row in value["models"])
    value["all_model_environments_ready"] = all(row["environment_ready"] for row in value["models"])
    _print(value)


def _command_prepare(args: argparse.Namespace) -> None:
    _print(prepare_protocol(args.protocol_root, verify_audio_hashes=args.verify_audio_hashes))


def _command_plan(args: argparse.Namespace) -> None:
    protocol, result, collection = _paths(args)
    plan = protocol_plan(args.protocol_root)
    reuse = []
    for component in MODEL_COMPONENT_IDS:
        root = result / component
        if (root / "backend_identity.json").is_file():
            try:
                valid = bool(validate_backend(root, args.protocol_root)["valid"])
            except (OSError, ValueError):
                valid = False
        else:
            valid = False
        reuse.append({"component_id": component, "complete_valid_result_reusable": valid})
    _print({
        "schema_version": "asr-commonvoice-campaign-plan.v1",
        "campaign_id": campaign_identity(protocol),
        "protocol": plan,
        "models": resolve_models(),
        "execution_order": list(MODEL_COMPONENT_IDS),
        "planned_inference_units": int(plan["clips"]["total"]) * len(MODEL_COMPONENT_IDS),
        "existing_results": reuse,
        "result_root": str(result),
        "collection_root": str(collection),
        "restart_unit": "one item JSON per backend",
        "sequential": True,
        "model_inference_performed": False,
    })


def _command_validate(args: argparse.Namespace) -> None:
    protocol, result, collection = _paths(args)
    value: dict[str, object] = {
        "protocol": validate_protocol(args.protocol_root, verify_audio_hashes=args.verify_audio_hashes),
        "source": {key: item for key, item in audit_source(verify_audio_hashes=args.verify_audio_hashes).items() if key not in {"eligible_rows", "exclusions"}},
        "models": resolve_models(),
    }
    existing = []
    for component in MODEL_COMPONENT_IDS:
        if (result / component / "backend_identity.json").is_file():
            existing.append(validate_backend(result / component, args.protocol_root))
    value["existing_backends"] = existing
    if (collection / "collection_manifest.json").is_file():
        value["collection"] = validate_collection(collection)
    value["valid"] = all(row["asset_ready"] and row["environment_ready"] for row in value["models"])
    _print(value)


def _command_paths(args: argparse.Namespace) -> None:
    protocol, result, collection = _paths(args)
    _print({"campaign_id": campaign_identity(protocol), "result_root": str(result), "collection_root": str(collection), "protocol_root": str(args.protocol_root.resolve())})


def _command_run_backend(args: argparse.Namespace) -> None:
    _protocol, result, _collection = _paths(args)
    _print(
        run_backend(
            args.component_id,
            result,
            args.protocol_root,
            smoke=args.smoke,
            concurrent_model_limit=args.parallel_models,
        )
    )


def _command_status(args: argparse.Namespace) -> None:
    _protocol, result, _collection = _paths(args)
    _print(status(result, args.protocol_root))


def _command_analyze(args: argparse.Namespace) -> None:
    _protocol, result, _collection = _paths(args)
    _print(analyze(result, args.protocol_root))


def _command_collect(args: argparse.Namespace) -> None:
    _protocol, result, collection = _paths(args)
    _print(collect(result, args.protocol_root, collection, create_zip=not args.no_zip))


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str))


_COMMANDS = {
    "audit": _command_audit,
    "prepare": _command_prepare,
    "plan": _command_plan,
    "validate": _command_validate,
    "paths": _command_paths,
    "status": _command_status,
    "analyze": _command_analyze,
    "collect": _command_collect,
}
