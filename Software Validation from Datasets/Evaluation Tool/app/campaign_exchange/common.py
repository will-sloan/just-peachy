"""Shared deterministic and atomic helpers for Stage 6 result exchange."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
from typing import Mapping
import uuid

import yaml

from app.artifact_contracts.atomic import (
    best_effort_unlink,
    file_sha256,
    replace_file_with_retry,
)
from app.benchmark_contracts.canonical import canonical_sha256


SHA256_PATTERN = re.compile(r"^[0-9A-F]{64}$")
GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
WORKER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
SENSITIVE_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|auth[_-]?token|access[_-]?key|password|secret)"
)


class CampaignExchangeError(RuntimeError):
    """Raised when an assignment or result exchange is unsafe or incompatible."""


def utc_timestamp(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise CampaignExchangeError("exchange timestamps must be timezone-aware")
    return timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def read_json_mapping(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignExchangeError(f"cannot read JSON mapping {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CampaignExchangeError(f"JSON artifact must be a mapping: {path}")
    return value


def read_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CampaignExchangeError(f"cannot read YAML mapping {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CampaignExchangeError(f"YAML artifact must be a mapping: {path}")
    return value


def atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    atomic_write_bytes(path, encoded)


def atomic_write_yaml(path: Path, value: Mapping[str, object]) -> None:
    encoded = yaml.safe_dump(
        dict(value),
        allow_unicode=True,
        sort_keys=True,
        default_flow_style=False,
    ).encode("utf-8")
    atomic_write_bytes(path, encoded)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex}")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        replace_file_with_retry(temporary, target)
        _fsync_directory(target.parent)
    finally:
        best_effort_unlink(temporary)


def atomic_copy_tree(source: Path, destination: Path) -> None:
    """Copy a new directory and publish it by a same-parent atomic rename."""

    source_root = source.resolve()
    destination_root = destination.resolve()
    if not source_root.is_dir():
        raise CampaignExchangeError(f"source directory is missing: {source_root}")
    if destination_root.exists():
        raise CampaignExchangeError(f"refusing to overwrite directory: {destination_root}")
    destination_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination_root.with_name(
        f".{destination_root.name}.tmp-{uuid.uuid4().hex}"
    )
    try:
        shutil.copytree(source_root, temporary, copy_function=shutil.copy2)
        # Windows indexing, antivirus, and Explorer can briefly retain a
        # handle after copytree closes its files.  Directory publication uses
        # the same bounded sharing-violation retry policy as atomic files so a
        # transient WinError 5/32/33 cannot strand an otherwise valid export.
        replace_file_with_retry(temporary, destination_root)
        _fsync_directory(destination_root.parent)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def directory_inventory(root: Path) -> list[dict[str, object]]:
    """Return a stable complete file inventory for transfer-integrity checks."""

    resolved = root.resolve()
    if not resolved.is_dir():
        raise CampaignExchangeError(f"directory is missing: {resolved}")
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in resolved.rglob("*") if item.is_file()):
        relative = path.relative_to(resolved).as_posix()
        require_portable_path(relative)
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return rows


def directory_sha256(root: Path) -> str:
    return canonical_sha256(directory_inventory(root))


def require_inventory(root: Path, expected: object) -> list[dict[str, object]]:
    if not isinstance(expected, list) or any(not isinstance(item, Mapping) for item in expected):
        raise CampaignExchangeError("transfer file inventory must be a mapping list")
    normalized = [dict(item) for item in expected]
    observed = directory_inventory(root)
    if normalized != observed:
        raise CampaignExchangeError(f"incomplete or modified transfer directory: {root}")
    return observed


def require_sha256(value: object, label: str) -> str:
    digest = str(value or "").upper()
    if not SHA256_PATTERN.fullmatch(digest):
        raise CampaignExchangeError(f"{label} must be uppercase SHA-256")
    return digest


def require_git_commit(value: object) -> str:
    commit = str(value or "")
    if not GIT_COMMIT_PATTERN.fullmatch(commit):
        raise CampaignExchangeError("expected Git commit must be a 40- or 64-hex ID")
    return commit.lower()


def require_worker_id(value: object) -> str:
    worker_id = str(value or "")
    if not WORKER_ID_PATTERN.fullmatch(worker_id):
        raise CampaignExchangeError(
            "worker ID must be 2-32 lowercase letters, digits, underscores, or hyphens"
        )
    return worker_id


def require_portable_path(value: object) -> str:
    text = str(value or "")
    windows = PureWindowsPath(text)
    if (
        not text
        or "\\" in text
        or windows.drive
        or windows.root
        or text.startswith("/")
    ):
        raise CampaignExchangeError(f"path must be portable and relative: {value!r}")
    path = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise CampaignExchangeError(f"path is unsafe: {value!r}")
    return path.as_posix()


def require_no_credentials(value: object, label: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if SENSITIVE_PATTERN.search(serialized):
        raise CampaignExchangeError(f"possible credential material in {label}")


def identity_digest(value: object) -> str:
    if not isinstance(value, Mapping):
        raise CampaignExchangeError("identity must be a mapping")
    return canonical_sha256(dict(value))


def content_hash(value: Mapping[str, object], excluded: set[str]) -> str:
    payload = {key: item for key, item in value.items() if key not in excluded}
    return canonical_sha256(payload)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":  # os.open cannot reliably fsync Windows directories.
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
