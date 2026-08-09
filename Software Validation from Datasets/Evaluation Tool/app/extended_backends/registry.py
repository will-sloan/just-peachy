"""Runtime readers and identity inspection for Stage 8 registries."""

from __future__ import annotations

import hashlib
import importlib.util
from importlib import metadata
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import yaml

from app.extended_backends.contracts import (
    validate_environment_profiles,
    validate_model_asset_registry,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parent.parent
AUTOMATION_CONFIG_ROOT = TOOL_ROOT / "configs" / "automated_evaluation"


def load_environment_profiles(path: Path | None = None) -> dict[str, object]:
    payload = _read_yaml(
        path or AUTOMATION_CONFIG_ROOT / "environment_profiles.stage8.v1.yaml"
    )
    validate_environment_profiles(payload)
    return payload


def load_model_asset_registry(path: Path | None = None) -> dict[str, object]:
    payload = _read_yaml(path or AUTOMATION_CONFIG_ROOT / "model_asset_registry.v1.yaml")
    validate_model_asset_registry(payload)
    return payload


def load_backend_catalog(path: Path | None = None) -> dict[str, object]:
    payload = _read_yaml(path or AUTOMATION_CONFIG_ROOT / "extended_backends.v1.yaml")
    if payload.get("schema_version") != "extended-backend-catalog.v1":
        raise ValueError("extended backend catalog schema_version must be v1")
    backends = payload.get("backends")
    if not isinstance(backends, list) or not backends:
        raise ValueError("extended backend catalog must contain backends")
    identifiers = [str(item.get("id")) for item in backends if isinstance(item, Mapping)]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("extended backend identifiers must be unique")
    return payload


def package_version(distribution: str) -> str | None:
    """Return one installed distribution version without importing the backend."""

    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def package_available(distribution: str) -> bool:
    return package_version(distribution) is not None


def inspect_asset(asset_id: str, registry: Mapping[str, object] | None = None) -> dict[str, object]:
    """Return a portable, content-addressed asset observation."""

    source = dict(registry or load_model_asset_registry())
    assets = source.get("assets")
    if not isinstance(assets, Mapping) or asset_id not in assets:
        raise KeyError(f"unknown model asset {asset_id!r}")
    definition = assets[asset_id]
    if not isinstance(definition, Mapping):
        raise ValueError(f"invalid model asset definition {asset_id!r}")

    resolved = _resolve_asset_path(asset_id, definition)
    required_files = tuple(str(item) for item in definition.get("required_files", ()))
    present = _asset_is_complete(resolved, required_files)
    missing_required_files = [
        relative
        for relative in required_files
        if resolved is None
        or not resolved.is_dir()
        or not (resolved / relative).is_file()
        or (resolved / relative).stat().st_size == 0
    ]
    files = _file_inventory(resolved) if present else []
    total_bytes = sum(int(item["bytes"]) for item in files)
    identity = _tree_identity(files) if files else None
    acquisition_date = (
        datetime.fromtimestamp(
            max(_file_mtime(resolved, str(item["path"])) for item in files),
            tz=timezone.utc,
        ).isoformat()
        if files and resolved is not None
        else None
    )
    return {
        "asset_id": asset_id,
        "component": definition["component"],
        "backend": definition["backend"],
        "model_name": definition["model_name"],
        "model_version": str(definition["model_version"]),
        "source": definition["source"],
        "licence": definition["licence"],
        "artifact_filename": definition["artifact_filename"],
        "storage_path": str(definition["storage_path"]).replace("\\", "/"),
        "environment_profile": definition["environment_profile"],
        "credential_required": definition.get("credential_requirement") is not None,
        "acquisition_method": definition["acquisition_method"],
        "acquisition_date": acquisition_date,
        "present": present,
        "missing_required_files": missing_required_files,
        "size_bytes": total_bytes if present else None,
        "sha256": identity,
        "files": files,
        "verification_status": "verified" if present else "missing",
    }


def inspect_all_assets() -> list[dict[str, object]]:
    registry = load_model_asset_registry()
    assets = registry["assets"]
    assert isinstance(assets, Mapping)
    return [inspect_asset(str(asset_id), registry) for asset_id in sorted(assets)]


def _read_yaml(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return {str(key): value for key, value in payload.items()}


def _resolve_asset_path(asset_id: str, definition: Mapping[str, object]) -> Path | None:
    storage = str(definition["storage_path"])
    if storage.startswith("environment/"):
        if asset_id == "resemblyzer_packaged":
            spec = importlib.util.find_spec("resemblyzer")
            if spec is not None and spec.origin:
                return Path(spec.origin).resolve().parent / "pretrained.pt"
        return None
    return REPOSITORY_ROOT / Path(storage)


def _asset_is_complete(path: Path | None, required_files: tuple[str, ...]) -> bool:
    if path is None or not path.exists():
        return False
    if path.is_file():
        return path.stat().st_size > 0
    if not required_files:
        return any(candidate.is_file() for candidate in path.rglob("*"))
    return all((path / relative).is_file() and (path / relative).stat().st_size > 0 for relative in required_files)


def _file_inventory(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return []
    candidates = [path] if path.is_file() else sorted(
        (item for item in path.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(path).as_posix(),
    )
    rows: list[dict[str, object]] = []
    for item in candidates:
        relative = item.name if path.is_file() else item.relative_to(path).as_posix()
        rows.append(
            {
                "path": relative,
                "bytes": item.stat().st_size,
                "sha256": _sha256(item),
            }
        )
    return rows


def _file_mtime(root: Path, relative: str) -> float:
    candidate = root if root.is_file() else root / Path(relative)
    return candidate.stat().st_mtime


def _tree_identity(files: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(str(item["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(item["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
