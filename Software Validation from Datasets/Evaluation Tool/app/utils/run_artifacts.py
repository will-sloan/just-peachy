"""Run folder creation and artifact helpers."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
from typing import Any, Mapping

import yaml


ARTIFACT_SUBDIRS = ("predictions", "metrics", "plots", "logs", "report", "preview_audio")
PROJECT_RELATIVE_FIELD_BY_PATH_FIELD = {
    "audio_path": "audio_path_project_relative",
    "source_audio_path": "source_audio_path_project_relative",
    "clean_source_audio_path": "source_audio_path_project_relative",
    "distant_audio_path": "distant_audio_path_project_relative",
    "inference_audio_path": "inference_audio_project_relative",
}


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


def relative_artifact_config(
    config: Mapping[str, Any],
    *,
    artifact_root: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Return a JSON/YAML-safe config copy with persisted paths made relative."""

    return _relative_artifact_value(
        dict(config),
        artifact_root=artifact_root,
        project_root=project_root,
    )


def relative_artifact_records(
    records: list[dict[str, object]],
    *,
    artifact_root: Path | None = None,
    project_root: Path | None = None,
) -> list[dict[str, object]]:
    """Return selected metadata records without runtime-only absolute path fields."""

    return [
        relative_artifact_record(
            record,
            artifact_root=artifact_root,
            project_root=project_root,
        )
        for record in records
    ]


def relative_artifact_record(
    record: Mapping[str, object],
    *,
    artifact_root: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, object]:
    """Return one metadata/artifact row using relative paths where possible."""

    artifact: dict[str, object] = {}
    for key, value in record.items():
        if key.endswith("_resolved"):
            continue
        relative_field = PROJECT_RELATIVE_FIELD_BY_PATH_FIELD.get(key)
        if relative_field is not None:
            relative_value = record.get(relative_field)
            if relative_value not in (None, ""):
                artifact[key] = _jsonable_value(relative_value)
                continue
        if _is_pathish_key(key):
            artifact[key] = _relative_path_value(
                value,
                key=key,
                artifact_root=artifact_root,
                project_root=project_root,
            )
        else:
            artifact[key] = _jsonable_value(value)
    return artifact


def _relative_artifact_value(
    value: Any,
    *,
    artifact_root: Path,
    project_root: Path | None,
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                _relative_path_value(
                    item,
                    key=str(key),
                    artifact_root=artifact_root,
                    project_root=project_root,
                )
                if _is_pathish_key(str(key))
                else _relative_artifact_value(
                    item,
                    artifact_root=artifact_root,
                    project_root=project_root,
                )
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _relative_artifact_value(
                item,
                artifact_root=artifact_root,
                project_root=project_root,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _relative_artifact_value(
                item,
                artifact_root=artifact_root,
                project_root=project_root,
            )
            for item in value
        ]
    return _jsonable_value(value)


def _relative_path_value(
    value: object,
    *,
    key: str,
    artifact_root: Path | None,
    project_root: Path | None,
) -> object:
    if value is None:
        return None
    if isinstance(value, Path):
        path = value
    else:
        text = str(value)
        if not text:
            return text
        path = Path(text)
    if not path.is_absolute():
        return path.as_posix()
    if artifact_root is not None and _is_artifact_location_key(key):
        return _relative_between(path, artifact_root)
    if artifact_root is not None:
        relative_to_artifact = _relative_if_descendant(path, artifact_root)
        if relative_to_artifact is not None:
            return relative_to_artifact
    if project_root is not None:
        relative_to_project = _relative_if_descendant(path, project_root)
        if relative_to_project is not None:
            return relative_to_project
    return path.as_posix()


def _jsonable_value(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _is_pathish_key(key: str) -> bool:
    return (
        key in {"project_root", "run_dir", "runs_root", "output_root", "report_dir"}
        or key.endswith("_path")
        or key.endswith("_dir")
        or key.endswith("_root")
    )


def _is_artifact_location_key(key: str) -> bool:
    return key in {"project_root", "run_dir", "runs_root", "output_root", "report_dir"}


def _relative_between(path: Path, root: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), root.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _relative_if_descendant(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
