"""Paths, identities, and small I/O helpers for the deployment study."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Mapping

import yaml

from app.utils.paths import repository_root


TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = TOOL_ROOT / "configs" / "automated_evaluation" / "speaker_embedding_deployment.v1.yaml"


class SpeakerDeploymentError(ValueError):
    """Raised when deployment evidence is missing or inconsistent."""


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "speaker-embedding-deployment-policy.v1":
        raise SpeakerDeploymentError(f"invalid deployment policy: {path}")
    return value


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def study_identity(config: Mapping[str, object]) -> str:
    identity = {
        key: config[key]
        for key in (
            "schema_version", "study_id", "implementation_version", "selection_seed", "backends", "datasets",
            "gallery_sizes", "gallery_repetitions", "enrollment_counts",
            "enrollment_repetitions", "aggregation_methods", "fpir_targets",
            "known_wrong_name_rate_cap", "margin_grid", "primary_fpir_target",
            "bootstrap_repetitions", "confidence_level", "session_turns", "product_policy",
        )
    }
    return f"{config['study_id']}_{canonical_sha256(identity)[:12].lower()}"


def default_result_root(config: Mapping[str, object]) -> Path:
    return TOOL_ROOT / "JustPeachyResults" / "speaker_embedding_deployment" / study_identity(config)


def default_collection_root(config: Mapping[str, object]) -> Path:
    return TOOL_ROOT / "JustPeachyResearchSummaries" / study_identity(config)


def resolve_tool_path(value: str) -> Path:
    return (TOOL_ROOT / value).resolve()


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True, default=_json_scalar) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        deadline = time.monotonic() + 10.0
        while True:
            try:
                os.replace(temporary, path)
                return
            except OSError as exc:
                if not (isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32}):
                    raise
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def _json_scalar(value: object) -> object:
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def git_sha() -> str:
    import subprocess

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository_root().path,
        check=False, capture_output=True, text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"
