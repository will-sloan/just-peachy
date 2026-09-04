"""C:-only, deterministic and restart-safe I/O for Prompt 8."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Iterable, Mapping, Sequence
import zipfile

from . import MINIMUM_FREE_SPACE_BYTES, scope_fields


class FinalConsolidationError(RuntimeError):
    """A Prompt-8 evidence, safety, or output contract failed."""


class IncompleteEvidenceError(FinalConsolidationError):
    """The checksum-bound Prompt 4-7 evidence is incomplete or invalid."""


class ProductionCandidateError(FinalConsolidationError):
    """Prompt-7 production candidates cannot satisfy the final handoff contract."""


def blocked_status(exc: BaseException) -> str:
    if isinstance(exc, IncompleteEvidenceError):
        return "BLOCKED_INCOMPLETE_EVIDENCE"
    if isinstance(exc, ProductionCandidateError):
        return "BLOCKED_PRODUCTION_CANDIDATE"
    return "BLOCKED_OTHER"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def ensure_c(path: Path | str, *, label: str, must_exist: bool = False) -> Path:
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raise FinalConsolidationError(f"{label} must be absolute: {raw}")
    try:
        resolved = raw.resolve(strict=must_exist)
    except OSError as exc:
        raise FinalConsolidationError(f"cannot resolve {label} {raw}: {exc}") from exc
    if os.name == "nt" and resolved.drive.casefold() != "c:":
        raise FinalConsolidationError(f"{label} violates C:-only storage: {resolved}")
    ancestor = raw
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if ancestor.exists():
        linked = ancestor.resolve(strict=True)
        if os.name == "nt" and linked.drive.casefold() != "c:":
            raise FinalConsolidationError(
                f"{label} has an ancestor resolving off C: {ancestor} -> {linked}"
            )
    return resolved


def read_json(path: Path | str) -> dict[str, Any]:
    resolved = ensure_c(path, label="JSON input", must_exist=True)
    try:
        value = json.loads(resolved.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalConsolidationError(f"invalid JSON {resolved}: {exc}") from exc
    if not isinstance(value, dict):
        raise FinalConsolidationError(f"JSON root must be an object: {resolved}")
    return value


def read_csv(path: Path | str) -> list[dict[str, str]]:
    resolved = ensure_c(path, label="CSV input", must_exist=True)
    with resolved.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _atomic_replace(source: Path, destination: Path) -> None:
    delays = (0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.0)
    for attempt, delay in enumerate((*delays, 0.0)):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            transient = os.name == "nt" and (
                isinstance(exc, PermissionError)
                or getattr(exc, "winerror", None) in {5, 32}
            )
            if not transient or attempt >= len(delays):
                raise
            time.sleep(delay)


def write_bytes_atomic(path: Path | str, payload: bytes) -> Path:
    target = ensure_c(path, label="Prompt-8 output")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _atomic_replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def write_json_atomic(path: Path | str, value: Mapping[str, Any]) -> Path:
    return write_bytes_atomic(path, canonical_json_bytes(dict(value)))


def write_text_atomic(path: Path | str, value: str) -> Path:
    return write_bytes_atomic(path, value.encode("utf-8"))


def write_csv_atomic(path: Path | str, rows: Sequence[Mapping[str, object]]) -> Path:
    if not rows:
        raise FinalConsolidationError(f"refusing to write an empty CSV: {path}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            text = str(key)
            if text not in seen:
                seen.add(text)
                fields.append(text)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in fields})
    return write_bytes_atomic(path, stream.getvalue().encode("utf-8"))


def _csv_value(value: object) -> object:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return str(value).lower()
    return "" if value is None else value


def artifact_ref(path: Path | str) -> dict[str, str]:
    resolved = ensure_c(path, label="artifact", must_exist=True)
    if not resolved.is_file():
        raise FinalConsolidationError(f"artifact is not a file: {resolved}")
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def storage_guard(workspace: Path | str, *, fail: bool = True) -> dict[str, object]:
    root = ensure_c(workspace, label="Prompt-8 workspace")
    probe = Path("C:/") if os.name == "nt" else Path(root.anchor or "/")
    usage = shutil.disk_usage(probe)
    passed = usage.free >= MINIMUM_FREE_SPACE_BYTES
    value = {
        "schema_version": "full-pipeline-final-consolidation-storage.v1",
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
    if fail and not passed:
        raise FinalConsolidationError(
            "BLOCKED_C_DRIVE_RESERVE_35_GIB: "
            f"free={usage.free}, required={MINIMUM_FREE_SPACE_BYTES}"
        )
    return value


def deterministic_zip(
    zip_path: Path | str,
    *,
    root: Path | str,
    members: Iterable[str],
) -> Path:
    destination = ensure_c(zip_path, label="final compact ZIP")
    package_root = ensure_c(root, label="final report root", must_exist=True)
    names = tuple(sorted(set(str(item) for item in members)))
    if any(
        Path(name).is_absolute()
        or ".." in Path(name).parts
        or any(
            token in name.casefold()
            for token in ("credential", "cache", "weight", "dataset")
        )
        for name in names
    ):
        raise FinalConsolidationError("unsafe member requested for final compact ZIP")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in names:
                source = ensure_c(
                    package_root / name,
                    label=f"ZIP member {name}",
                    must_exist=True,
                )
                if not source.is_file() or source.stat().st_size > 100 * 1024 * 1024:
                    raise FinalConsolidationError(f"unsafe final ZIP member: {source}")
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes())
        _atomic_replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def validate_zip(
    zip_path: Path | str,
    *,
    expected_members: Sequence[str],
    root: Path | str,
) -> None:
    resolved = ensure_c(zip_path, label="final compact ZIP", must_exist=True)
    package_root = ensure_c(root, label="final report root", must_exist=True)
    with zipfile.ZipFile(resolved, "r") as archive:
        names = archive.namelist()
        if names != sorted(expected_members):
            raise FinalConsolidationError(
                f"final ZIP members differ: expected {sorted(expected_members)}, got {names}"
            )
        if archive.testzip() is not None:
            raise FinalConsolidationError("final ZIP CRC validation failed")
        for name in names:
            source = ensure_c(
                package_root / name,
                label=f"ZIP source member {name}",
                must_exist=True,
            )
            if not source.is_file() or archive.read(name) != source.read_bytes():
                raise FinalConsolidationError(
                    f"final ZIP member bytes differ from canonical output: {name}"
                )


__all__ = [
    "FinalConsolidationError",
    "IncompleteEvidenceError",
    "ProductionCandidateError",
    "artifact_ref",
    "blocked_status",
    "canonical_json_bytes",
    "deterministic_zip",
    "ensure_c",
    "read_csv",
    "read_json",
    "sha256_bytes",
    "sha256_file",
    "storage_guard",
    "validate_zip",
    "write_csv_atomic",
    "write_json_atomic",
    "write_text_atomic",
]
