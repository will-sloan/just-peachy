"""Small deterministic I/O and C:-only storage guards for Prompt 5."""

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

from . import (
    MINIMUM_FREE_SPACE_BYTES,
    ORIGINAL_FULL_SCOPE_COMPLETE,
    SCOPE_CLASS,
    SCOPE_ID,
)


class CoreEvaluationError(RuntimeError):
    """A Prompt-5 admission, integrity, or evidence-contract failure."""


def scope_fields() -> dict[str, object]:
    return {
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": ORIGINAL_FULL_SCOPE_COMPLETE,
    }


def ensure_c_drive(path: Path | str, *, label: str, must_exist: bool = False) -> Path:
    """Resolve a path and reject anything whose physical target is not on C:."""

    raw = Path(path).expanduser()
    if must_exist and not raw.exists():
        raise CoreEvaluationError(f"{label} is missing: {raw}")
    resolved = raw.resolve(strict=must_exist)
    if os.name == "nt" and resolved.drive.casefold() != "c:":
        raise CoreEvaluationError(f"{label} violates the C:-only amendment: {resolved}")
    return resolved


def storage_preflight(
    workspace_root: Path | str,
    *,
    reserve_bytes: int = MINIMUM_FREE_SPACE_BYTES,
    write_record: bool = True,
) -> dict[str, object]:
    root = ensure_c_drive(workspace_root, label="Prompt-5 workspace")
    usage = shutil.disk_usage(Path("C:/") if os.name == "nt" else root.anchor or root)
    passed = usage.free >= reserve_bytes
    value = {
        "schema_version": "full-pipeline-core-storage-preflight.v1",
        **scope_fields(),
        "status": "PASS" if passed else "BLOCKED_C_DRIVE_RESERVE_35_GIB",
        "workspace_root": str(root),
        "allowed_drive": "C:\\",
        "other_drives_allowed": False,
        "minimum_free_space_reserve_bytes": reserve_bytes,
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
    }
    if write_record:
        root.mkdir(parents=True, exist_ok=True)
        write_json_atomic(root / "storage_preflight.json", value)
    if not passed:
        raise CoreEvaluationError(
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
                raise CoreEvaluationError(
                    f"JSONL row {line_number} is not an object: {path}"
                )
            rows.append(value)
    return rows


def write_jsonl_once(path: Path, rows: Iterable[Mapping[str, object]]) -> Path:
    payload = b"".join(canonical_json_bytes(dict(row)) + b"\n" for row in rows)
    return write_bytes_once(path, payload)


def write_bytes_once(path: Path, payload: bytes) -> Path:
    target = Path(path)
    if target.is_file():
        if target.read_bytes() != payload:
            raise CoreEvaluationError(f"immutable artifact differs: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, target)
    return target


def write_json_once(path: Path, value: Mapping[str, object]) -> Path:
    return write_bytes_once(path, canonical_json_bytes(dict(value)) + b"\n")


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> Path:
    keys: list[str] = []
    observed: set[str] = set()
    for row in rows:
        for key in row:
            if key not in observed:
                observed.add(key)
                keys.append(str(key))
    if not keys:
        keys = ["scope_id", "scope_class", "original_full_scope_complete"]
        rows = [scope_fields()]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in keys})
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


def exact_checksum_manifest(
    root: Path, *, exclude: Sequence[str] = ()
) -> dict[str, str]:
    return checksum_map(Path(root), exclude=tuple(exclude))


def hash_lines(values: Sequence[str]) -> str:
    payload = ("\n".join(values) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_checksum_document(root: Path, path: Path) -> dict[str, str]:
    value = read_json(path)
    entries = value.get("entries") or value.get("files")
    if not isinstance(entries, Mapping):
        raise CoreEvaluationError(f"checksum document has no entries/files map: {path}")
    normalized = {str(key): str(item).casefold() for key, item in entries.items()}
    for relative, expected in normalized.items():
        target = (root / relative).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise CoreEvaluationError(
                f"checksum entry escapes root: {relative}"
            ) from exc
        if not target.is_file():
            raise CoreEvaluationError(f"checksum-bound file is missing: {target}")
        if sha256_file(target).casefold() != expected:
            raise CoreEvaluationError(f"checksum differs: {target}")
    return normalized
