"""Deterministic and atomic file helpers for the H2 controller."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable, Mapping, Sequence

import yaml


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def read_yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return value


def read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_number} is not an object: {path}")
            rows.append(value)
    return tuple(rows)


def write_json_atomic(path: Path, value: object) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomic(destination, canonical_json_bytes(value) + b"\n")


def write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    payload = b"".join(canonical_json_bytes(dict(row)) + b"\n" for row in rows)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomic(destination, payload)


def write_yaml_atomic(path: Path, value: object) -> None:
    payload = yaml.safe_dump(value, sort_keys=False, allow_unicode=True).encode("utf-8")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomic(destination, payload)


def write_csv_atomic(
    path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fieldnames), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dict(row) for row in rows)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_once_or_verify(path: Path, value: object) -> None:
    destination = Path(path)
    payload = canonical_json_bytes(value) + b"\n"
    if destination.is_file():
        if destination.read_bytes() != payload:
            raise ValueError(f"immutable artifact differs: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomic(destination, payload)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "canonical_json_bytes",
    "canonical_sha256",
    "read_json",
    "read_jsonl",
    "read_yaml",
    "sha256_file",
    "write_csv_atomic",
    "write_json_atomic",
    "write_jsonl_atomic",
    "write_once_or_verify",
    "write_yaml_atomic",
]
