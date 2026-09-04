"""Deterministic C:-only I/O helpers for bounded Prompt 7."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Iterable, Mapping, Sequence

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    read_json,
    sha256_file,
    write_json_atomic,
)

from . import MINIMUM_FREE_SPACE_BYTES, scope_fields


class HardeningError(RuntimeError):
    """A Prompt-7 contract, evidence, or execution failure."""


def ensure_c(path: Path | str, *, label: str, must_exist: bool = False) -> Path:
    raw = Path(path).expanduser()
    if must_exist and not raw.exists():
        raise HardeningError(f"{label} is missing: {raw}")
    resolved = raw.resolve(strict=must_exist)
    if os.name == "nt" and resolved.drive.casefold() != "c:":
        raise HardeningError(f"{label} violates the C:-only amendment: {resolved}")
    return resolved


def storage_guard(
    workspace_root: Path | str,
    *,
    write_record: bool = True,
    fail_below_reserve: bool = True,
) -> dict[str, object]:
    root = ensure_c(workspace_root, label="Prompt-7 workspace")
    usage = shutil.disk_usage(Path("C:/") if os.name == "nt" else root.anchor or root)
    passed = usage.free >= MINIMUM_FREE_SPACE_BYTES
    value = {
        "schema_version": "full-pipeline-production-hardening-storage.v1",
        **scope_fields(),
        "status": "PASS" if passed else "BLOCKED_C_DRIVE_RESERVE_35_GIB",
        "allowed_drive": "C:\\",
        "other_drives_allowed": False,
        "minimum_free_space_reserve_bytes": MINIMUM_FREE_SPACE_BYTES,
        "free_bytes": usage.free,
        "used_bytes": usage.used,
        "total_bytes": usage.total,
        "workspace_root": str(root),
    }
    if write_record:
        root.mkdir(parents=True, exist_ok=True)
        write_json_atomic(root / "storage_status.json", value)
    if fail_below_reserve and not passed:
        raise HardeningError(
            "BLOCKED_C_DRIVE_RESERVE_35_GIB: "
            f"free={usage.free} required={MINIMUM_FREE_SPACE_BYTES}"
        )
    return value


def write_bytes_once(path: Path, payload: bytes) -> Path:
    target = ensure_c(path, label="immutable Prompt-7 artifact")
    if target.is_file():
        if target.read_bytes() != payload:
            raise HardeningError(f"immutable artifact differs: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, target)
    return target


def write_json_once(path: Path, value: Mapping[str, object]) -> Path:
    return write_bytes_once(path, canonical_json_bytes(dict(value)) + b"\n")


def write_text_once(path: Path, value: str) -> Path:
    return write_bytes_once(path, value.encode("utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with ensure_c(path, label="CSV evidence", must_exist=True).open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        return list(csv.DictReader(stream))


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> Path:
    fields: list[str] = list(fieldnames or ())
    seen: set[str] = set()
    seen.update(fields)
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(str(key))
                seen.add(str(key))
    if not fields:
        rows = [scope_fields()]
        fields = list(rows[0])
    buffer: list[str] = []
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in fields})
    buffer.append(stream.getvalue())
    return write_bytes_once(path, "".join(buffer).encode("utf-8"))


def _csv_value(value: object) -> object:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return str(value).lower()
    return "" if value is None else value


def artifact_ref(path: Path | str) -> dict[str, str]:
    resolved = ensure_c(path, label="Prompt-7 artifact", must_exist=True)
    if not resolved.is_file():
        raise HardeningError(f"artifact is not a file: {resolved}")
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def source_tree_sha(paths: Iterable[Path]) -> str:
    entries = {
        str(path.resolve()): sha256_file(path)
        for path in sorted((Path(item) for item in paths), key=str)
    }
    return hashlib.sha256(canonical_json_bytes(entries)).hexdigest()


def directory_sha256(root: Path | str) -> str:
    """Hash a locked asset tree with the program-lock algorithm.

    The relative path, byte count, and file digest are all included. Python
    bytecode/cache files are deliberately excluded because they are runtime
    by-products rather than model assets.
    """

    path = ensure_c(root, label="asset tree", must_exist=True)
    if not path.is_dir():
        raise HardeningError(f"asset tree is not a directory: {path}")
    rows: list[tuple[str, int, str]] = []
    for candidate in sorted(
        (
            item
            for item in path.rglob("*")
            if item.is_file()
            and "__pycache__" not in item.parts
            and item.suffix.casefold() not in {".pyc", ".pyo"}
        ),
        key=lambda item: item.relative_to(path).as_posix(),
    ):
        rows.append(
            (
                candidate.relative_to(path).as_posix(),
                candidate.stat().st_size,
                sha256_file(candidate),
            )
        )
    digest = hashlib.sha256()
    for relative, size, file_hash in rows:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def checksum_document(root: Path, *, exclude: Sequence[str] = ()) -> dict[str, object]:
    return {
        "schema_version": "full-pipeline-production-candidate-checksums.v1",
        **scope_fields(),
        "entries": checksum_map(root, exclude=tuple(exclude)),
    }


__all__ = [
    "HardeningError",
    "artifact_ref",
    "checksum_document",
    "directory_sha256",
    "ensure_c",
    "read_csv",
    "read_json",
    "sha256_file",
    "source_tree_sha",
    "storage_guard",
    "write_csv",
    "write_json_atomic",
    "write_json_once",
    "write_text_once",
]
