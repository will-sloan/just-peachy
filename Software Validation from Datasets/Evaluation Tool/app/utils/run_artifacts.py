"""Run folder creation and artifact helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

import yaml


ARTIFACT_SUBDIRS = ("predictions", "metrics", "plots", "logs", "report", "preview_audio")


def make_run_id(dataset_key: str, command_name: str, run_name: str | None = None) -> str:
    """Create a stable, sortable run identifier."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts = [timestamp, dataset_key, command_name]
    if run_name:
        parts.append(_slugify_run_name(run_name))
    return "_".join(part for part in parts if part)


def create_run_dir(
    runs_root: Path,
    dataset_key: str,
    command_name: str,
    run_name: str | None = None,
) -> Path:
    """Create a timestamped run folder with the required artifact subfolders."""

    run_dir = runs_root / make_run_id(dataset_key, command_name, run_name)
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ARTIFACT_SUBDIRS:
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    return run_dir


def _slugify_run_name(run_name: str) -> str:
    """Return a filesystem-friendly run-name suffix."""

    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", run_name.strip())
    slug = slug.strip("._-")
    return slug[:80] or "run"


def ensure_run_subdirs(run_dir: Path) -> None:
    """Ensure all required run artifact subdirectories exist."""

    for name in ARTIFACT_SUBDIRS:
        (run_dir / name).mkdir(parents=True, exist_ok=True)


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a YAML file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=False)


def read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file and return a dictionary."""

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data
