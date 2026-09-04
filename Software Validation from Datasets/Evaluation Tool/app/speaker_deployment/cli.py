"""CLI surface for the deployment-policy embedding study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import analyze
from .collection import collect
from .contracts import DEFAULT_CONFIG, default_collection_root, default_result_root, load_config, resolve_tool_path, study_identity
from .replay import _dataset_paths, run_backend


def add_speaker_deployment_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("speaker-deployment", help="Evaluate deployment policies over frozen speaker embeddings")
    commands = parser.add_subparsers(dest="speaker_deployment_command", required=True)
    for name in ("plan", "validate", "status", "analyze", "collect"):
        command = commands.add_parser(name)
        _common(command)
        command.set_defaults(func=globals()[f"_{name}"])
    run = commands.add_parser("run-backend")
    _common(run)
    run.add_argument("--backend", required=True)
    run.set_defaults(func=_run_backend)


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--result-root", type=Path, default=None)
    parser.add_argument("--analysis-root", type=Path, default=None)
    parser.add_argument("--collection-root", type=Path, default=None)
    parser.add_argument("--no-zip", action="store_true")


def _paths(args):
    config = load_config(args.config)
    result = args.result_root.resolve() if args.result_root else default_result_root(config)
    analysis_root = args.analysis_root.resolve() if args.analysis_root else result / "analysis"
    collection_root = args.collection_root.resolve() if args.collection_root else default_collection_root(config)
    return config, result, analysis_root, collection_root


def _plan(args):
    config, result, analysis_root, collection_root = _paths(args)
    _print({"study_id": study_identity(config), "backends": config["backends"], "datasets": list(config["datasets"]), "gallery_sizes": config["gallery_sizes"], "fpir_targets": config["fpir_targets"], "result_root": str(result), "analysis_root": str(analysis_root), "collection_root": str(collection_root), "model_inference_required_for_replay": False})


def _validate(args):
    config, result, analysis_root, collection_root = _paths(args)
    evidence = []
    for backend in config["backends"]:
        for dataset in config["datasets"]:
            protocol, bundle = _dataset_paths(config, str(backend), str(dataset))
            missing = [str(path) for path in (protocol, bundle) if not path.exists()]
            evidence.append({"backend": backend, "dataset": dataset, "protocol_root": str(protocol), "observation_bundle": str(bundle), "valid": not missing, "missing": missing})
    _print({"valid": all(row["valid"] for row in evidence), "evidence": evidence, "result_root": str(result)})


def _run_backend(args):
    _config, result, _analysis, _collection = _paths(args)
    value = run_backend(args.backend, result, args.config)
    _print({
        "backend": value["backend"], "status": value["status"],
        "elapsed_sec": value.get("elapsed_sec"), "reused": value.get("reused", False),
    })


def _status(args):
    config, result, _analysis, collection = _paths(args)
    rows = []
    for backend in config["backends"]:
        path = result / str(backend) / "progress.json"
        value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"status": "PENDING", "phase": "not_started"}
        rows.append({"backend": backend, **value})
    _print({"study_id": study_identity(config), "result_root": str(result), "collection_root": str(collection), "backends": rows})


def _analyze(args):
    _config, result, analysis_root, _collection = _paths(args)
    _print(analyze(result, analysis_root, args.config))


def _collect(args):
    _config, result, analysis_root, collection_root = _paths(args)
    _print(collect(result, analysis_root, collection_root, args.config, create_zip=not args.no_zip))


def _print(value):
    print(json.dumps(value, indent=2, sort_keys=True))
