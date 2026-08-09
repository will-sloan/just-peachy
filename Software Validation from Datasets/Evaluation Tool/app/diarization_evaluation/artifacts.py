"""Small atomic artifact helpers for Stage 11 standalone result bundles."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Iterable, Mapping
import uuid

import pyarrow as pa
import pyarrow.parquet as pq


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json_atomic(path: Path, value: object) -> Path:
    payload = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    return write_bytes_atomic(path, payload)


def write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, object]]) -> Path:
    payload = "".join(
        json.dumps(dict(row), sort_keys=True, ensure_ascii=False) + "\n" for row in rows
    ).encode("utf-8")
    return write_bytes_atomic(path, payload)


def write_text_atomic(path: Path, value: str) -> Path:
    return write_bytes_atomic(path, value.encode("utf-8"))


def write_parquet_atomic(path: Path, table: pa.Table) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        pq.write_table(table, temporary, version="2.6", compression="NONE")
        _fsync_file(temporary)
        pq.read_table(temporary)
        _replace_with_retry(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_bytes_atomic(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_checksum_manifest(root: Path, *, exclude: Iterable[str] = ()) -> dict[str, object]:
    excluded = {str(value).replace("\\", "/") for value in exclude}
    entries: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".tmp." in path.name:
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "checksums.json" or relative in excluded:
            continue
        entries[relative] = {
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    payload: dict[str, object] = {
        "schema_version": "diarization-checksums.v1",
        "hash_algorithm": "sha256",
        "entries": entries,
    }
    write_json_atomic(root / "checksums.json", payload)
    return payload


def validate_checksum_manifest(root: Path) -> dict[str, object]:
    path = root / "checksums.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "diarization-checksums.v1":
        raise ValueError("unsupported diarization checksum manifest")
    entries = payload.get("entries")
    if not isinstance(entries, Mapping):
        raise ValueError("diarization checksum entries must be a mapping")
    for relative, raw in entries.items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"invalid checksum entry: {relative}")
        artifact = (root / str(relative)).resolve()
        try:
            artifact.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"checksum path escapes result root: {relative}") from exc
        if not artifact.is_file():
            raise ValueError(f"missing checksummed artifact: {relative}")
        if int(raw.get("bytes", -1)) != artifact.stat().st_size:
            raise ValueError(f"artifact byte count mismatch: {relative}")
        if str(raw.get("sha256", "")).upper() != file_sha256(artifact):
            raise ValueError(f"artifact checksum mismatch: {relative}")
    temporary = [path for path in root.rglob("*") if path.is_file() and ".tmp." in path.name]
    if temporary:
        raise ValueError("unresolved temporary diarization artifacts remain")
    return {"valid": True, "artifact_count": len(entries)}


def _temporary_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp.{uuid.uuid4().hex}")


def _replace_with_retry(source: Path, destination: Path) -> None:
    """Tolerate brief Windows scanner/indexer locks without weakening atomicity."""

    for attempt in range(7):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 6:
                raise
            time.sleep(0.02 * (2**attempt))


def _fsync_file(path: Path) -> None:
    # Windows requires a writable descriptor for FlushFileBuffers/os.fsync.
    with path.open("rb+") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
