"""Small deterministic and atomic I/O helpers for evaluation infrastructure."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Iterable, Mapping
import uuid


ATOMIC_REPLACE_ATTEMPTS = 7
ATOMIC_REPLACE_BACKOFF_SEC = 0.02


def installed_tool_path_candidates(
    path_value: str | Path, *, evaluation_root: Path
) -> tuple[Path, ...]:
    """Resolve physical aliases without changing a frozen tool-logical path.

    Stage-11 manifests keep immutable
    ``benchmarks/stage11/<protocol>/...`` logical names. Their generated WAVs
    were intentionally consolidated under
    ``JustPeachyGeneratedData/<protocol>/...``. Both physical locations are
    considered while the logical path and scientific hashes remain unchanged.
    """

    value = Path(path_value)
    if value.is_absolute():
        return (value.resolve(),)
    root = Path(evaluation_root).resolve()
    candidates = [(root / value).resolve()]
    parts = value.parts
    if len(parts) >= 3 and tuple(part.casefold() for part in parts[:2]) == (
        "benchmarks",
        "stage11",
    ):
        generated = root / "JustPeachyGeneratedData" / Path(*parts[2:])
        candidates.append(generated.resolve())
    return tuple(dict.fromkeys(candidates))


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_bytes_atomic(path: Path, value: bytes) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{uuid.uuid4().hex}")
    try:
        with temporary.open("wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        replace_file_atomic(temporary, path)
    finally:
        _cleanup_owned_temporary(temporary)
    return path


def replace_file_atomic(temporary: Path, target: Path) -> Path:
    """Replace one same-directory target with bounded sharing-violation retries.

    Windows virus scanners and indexers can briefly hold a newly flushed file
    and make ``os.replace`` raise ``PermissionError``. Retrying the identical
    replace preserves atomic overwrite semantics; it never unlinks the target.
    If every attempt fails, the first exception is re-raised after best-effort
    cleanup of only the caller-owned temporary file.
    """

    source = Path(temporary).resolve()
    destination = Path(target).resolve()
    if source == destination or source.parent != destination.parent:
        raise ValueError("atomic replace requires distinct paths in one directory")
    owned_prefixes = (
        f".{destination.name}.tmp.",
        f".{destination.name}.tmp-",
    )
    if not source.name.startswith(owned_prefixes):
        raise ValueError("atomic-replace temporary name does not belong to target")
    if not source.is_file():
        raise FileNotFoundError(source)

    first_error: PermissionError | None = None
    try:
        for attempt in range(ATOMIC_REPLACE_ATTEMPTS):
            try:
                os.replace(source, destination)
                return destination
            except PermissionError as exc:
                if first_error is None:
                    first_error = exc
                if attempt + 1 < ATOMIC_REPLACE_ATTEMPTS:
                    time.sleep(ATOMIC_REPLACE_BACKOFF_SEC * (2**attempt))
        if first_error is None:  # pragma: no cover - loop invariant
            raise RuntimeError("atomic replace exhausted without an exception")
        raise first_error
    finally:
        _cleanup_owned_temporary(source)


def _cleanup_owned_temporary(path: Path) -> None:
    """Best-effort exact-temp cleanup that never masks publication failure."""

    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        # A still-open Windows handle can outlive the bounded replace window.
        # The UUID path remains attempt-local and cannot overwrite a result.
        pass


def write_json_atomic(path: Path, value: object) -> Path:
    payload = json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8") + b"\n"
    return write_bytes_atomic(path, payload)


def write_jsonl_atomic(
    path: Path, rows: Iterable[Mapping[str, object]]
) -> Path:
    payload = b"".join(
        canonical_json_bytes(dict(row)) + b"\n" for row in rows
    )
    return write_bytes_atomic(path, payload)


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def checksum_map(root: Path, *, exclude: Iterable[str] = ()) -> dict[str, str]:
    root = Path(root).resolve()
    excluded = {str(value).replace("\\", "/") for value in exclude}
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.relative_to(root).as_posix() not in excluded
        and ".tmp." not in path.name
    }
