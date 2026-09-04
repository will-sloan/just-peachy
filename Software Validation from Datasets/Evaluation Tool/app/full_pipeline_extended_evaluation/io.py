"""Deterministic I/O, hashing, packaging, and C:-only storage guards."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
from typing import Iterable, Mapping, Sequence
import zipfile

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_file,
    write_json_atomic,
)

from . import MINIMUM_FREE_SPACE_BYTES, scope_fields


class ExtendedEvaluationError(RuntimeError):
    """A Prompt-6 admission, integrity, execution, or report failure."""


class StorageReserveError(ExtendedEvaluationError):
    """C: has reached the user-mandated 35-GiB reserve."""


def ensure_c_drive(path: Path | str, *, label: str, must_exist: bool = False) -> Path:
    raw = Path(path).expanduser()
    if must_exist and not raw.exists():
        raise ExtendedEvaluationError(f"{label} is missing: {raw}")
    resolved = raw.resolve(strict=must_exist)
    if os.name == "nt" and resolved.drive.casefold() != "c:":
        raise ExtendedEvaluationError(
            f"{label} violates the C:-only amendment: {resolved}"
        )
    return resolved


def storage_preflight(
    workspace_root: Path | str,
    *,
    reserve_bytes: int = MINIMUM_FREE_SPACE_BYTES,
    fail: bool = True,
) -> dict[str, object]:
    root = ensure_c_drive(workspace_root, label="Prompt-6 workspace")
    usage = shutil.disk_usage("C:\\" if os.name == "nt" else root.anchor or root)
    passed = usage.free >= reserve_bytes
    value = {
        "schema_version": "full-pipeline-extended-storage-preflight.v1",
        **scope_fields(),
        "status": "PASS" if passed else "BLOCKED_C_DRIVE_RESERVE_35_GIB",
        "allowed_drive": "C:\\",
        "other_drives_allowed": False,
        "minimum_free_space_reserve_bytes": reserve_bytes,
        "free_bytes": usage.free,
        "used_bytes": usage.used,
        "total_bytes": usage.total,
        "workspace_root": str(root),
    }
    root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(root / "storage_preflight.json", value)
    if fail and not passed:
        raise StorageReserveError(
            "BLOCKED_C_DRIVE_RESERVE_35_GIB: "
            f"free={usage.free} required={reserve_bytes}"
        )
    return value


def read_jsonl(path: Path | str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ExtendedEvaluationError(
                    f"JSONL row {line_number} is not an object: {path}"
                )
            rows.append(value)
    return rows


def write_json_once(path: Path, value: Mapping[str, object]) -> Path:
    return write_bytes_once(path, canonical_json_bytes(dict(value)) + b"\n")


def write_jsonl_once(path: Path, rows: Iterable[Mapping[str, object]]) -> Path:
    return write_bytes_once(
        path,
        b"".join(canonical_json_bytes(dict(row)) + b"\n" for row in rows),
    )


def write_bytes_once(path: Path, payload: bytes) -> Path:
    target = Path(path)
    if target.is_file():
        if target.read_bytes() != payload:
            raise ExtendedEvaluationError(f"immutable artifact differs: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, target)
    return target


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> Path:
    values = list(rows) or [{**scope_fields(), "status": "NO_ROWS"}]
    fields: list[str] = []
    observed: set[str] = set()
    for row in values:
        for key in row:
            text = str(key)
            if text not in observed:
                observed.add(text)
                fields.append(text)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in values:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})
    os.replace(temporary, target)
    return target


def _csv_value(value: object) -> object:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return value


def deterministic_zip(source: Path, destination: Path) -> Path:
    source = ensure_c_drive(source, label="package source", must_exist=True)
    destination = ensure_c_drive(destination, label="package ZIP")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            if path.resolve() == destination.resolve():
                continue
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    os.replace(temporary, destination)
    return destination


def artifact_ref(path: Path | str) -> dict[str, str]:
    resolved = ensure_c_drive(path, label="artifact", must_exist=True)
    if not resolved.is_file():
        raise ExtendedEvaluationError(f"artifact is not a file: {resolved}")
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def verify_ref(raw: Mapping[str, object], *, label: str) -> Path:
    path = ensure_c_drive(str(raw.get("path") or ""), label=label, must_exist=True)
    if not path.is_file():
        raise ExtendedEvaluationError(f"{label} is not a file: {path}")
    if str(raw.get("sha256") or "").casefold() != sha256_file(path):
        raise ExtendedEvaluationError(f"{label} SHA-256 differs: {path}")
    return path


__all__ = [
    "ExtendedEvaluationError",
    "StorageReserveError",
    "artifact_ref",
    "deterministic_zip",
    "ensure_c_drive",
    "read_json",
    "read_jsonl",
    "sha256_file",
    "storage_preflight",
    "verify_ref",
    "write_csv",
    "write_json_atomic",
    "write_json_once",
    "write_jsonl_once",
]
