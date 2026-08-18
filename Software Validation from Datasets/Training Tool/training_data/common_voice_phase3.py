"""Selective Common Voice materialization and immutable Phase-3 freeze.

The source archive remains below JP_DATA_ROOT.  Derived metadata, selected MP3
files, state, registries, and audits live below JP_TRAINING_ROOT.  Canonical
identities use logical roots and relative member names, never physical paths.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterable, Iterator

import pandas as pd
import soundfile as sf

from training_data.common_voice import load_release, sha256_file
from training_data.registry import _frame_hash, _json_hash


PHASE3_SCHEMA = "training-data-freeze-phase3.v1"
REGISTRY_SCHEMA = "common-voice-older-registry.v1"
SPLIT_SCHEMA = "common-voice-older-split.v1"
SPLIT_ALGORITHM_VERSION = "speaker_age_duration_greedy.v1"
SPLIT_SEED = "just-peachy-common-voice-older-v1"
AGE_MAP = {
    "sixties": "60s",
    "seventies": "70s",
    "eighties": "80s",
    "nineties": "90s",
    "one_hundreds": "100+",
    "hundreds": "100+",
    "100+": "100+",
}
METADATA_NAMES = {
    "README.md",
    "validated.tsv",
    "invalidated.tsv",
    "other.tsv",
    "train.tsv",
    "dev.tsv",
    "test.tsv",
    "reported.tsv",
    "clip_durations.tsv",
    "validated_sentences.tsv",
    "unvalidated_sentences.tsv",
}
PARTIAL_SUFFIXES = (".crdownload", ".part", ".tmp", ".download")


class Phase3Error(RuntimeError):
    """Raised when a Phase-3 invariant fails and work must stop."""


@dataclass(frozen=True)
class Phase3Paths:
    data_root: Path
    training_root: Path
    archive: Path
    release_id: str

    @property
    def release_root(self) -> Path:
        return self.training_root / "datasets" / "common_voice" / "english" / self.release_id

    @property
    def prepared_root(self) -> Path:
        return self.release_root / "prepared" / "en"

    @property
    def original_metadata(self) -> Path:
        return self.prepared_root / "metadata" / "original"

    @property
    def derived_metadata(self) -> Path:
        return self.prepared_root / "metadata" / "derived"

    @property
    def clips(self) -> Path:
        return self.prepared_root / "clips"

    @property
    def state(self) -> Path:
        return self.prepared_root / "state"

    @property
    def phase3_root(self) -> Path:
        return self.training_root / "successors" / "common_voice_26_english_phase3"

    @property
    def registries(self) -> Path:
        return self.phase3_root / "registries"

    @property
    def audits(self) -> Path:
        return self.phase3_root / "audits"

    @property
    def manifests(self) -> Path:
        return self.phase3_root / "manifests"

    @property
    def license_evidence(self) -> Path:
        return self.phase3_root / "license_evidence"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _replace_with_windows_retry(temporary, path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    _replace_with_windows_retry(temporary, path)


def _replace_with_windows_retry(source: Path, destination: Path) -> None:
    """Atomically replace a file despite brief Windows reader locks."""
    for attempt in range(40):
        try:
            source.replace(destination)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.1)


def markdown_json(title: str, payload: Any) -> str:
    return f"# {title}\n\n```json\n{json.dumps(payload, indent=2, sort_keys=True)}\n```\n"


def detect_archive_format(path: Path) -> str:
    with path.open("rb") as stream:
        signature = stream.read(8)
    if signature.startswith(b"\x1f\x8b\x08"):
        return "gzip-compressed tar"
    if signature.startswith(b"PK\x03\x04"):
        return "zip"
    if signature.startswith(b"Rar!\x1a\x07"):
        return "rar"
    if signature.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    return "unknown"


def discover_archive(data_root: Path, release: dict[str, Any]) -> Path:
    raw_root = data_root / "Raw Datasets (Not formatted)"
    if not raw_root.is_dir():
        raise Phase3Error(f"Raw dataset root does not exist: {raw_root}")
    partials = [
        path for path in raw_root.iterdir()
        if path.is_file() and "common voice" in path.name.casefold()
        and path.name.casefold().endswith(PARTIAL_SUFFIXES)
    ]
    if partials:
        raise Phase3Error(f"Common Voice partial download is still present: {partials[0].name}")
    candidates = [
        path for path in raw_root.iterdir()
        if path.is_file() and "common voice" in path.name.casefold()
    ]
    expected = int(release["archive_size_bytes"])
    exact = [path for path in candidates if path.stat().st_size == expected]
    if len(exact) != 1:
        description = ", ".join(f"{path.name} ({path.stat().st_size} bytes)" for path in candidates)
        raise Phase3Error(
            f"Expected one Common Voice archive with {expected} bytes, found {len(exact)}. Candidates: {description}"
        )
    if detect_archive_format(exact[0]) != "gzip-compressed tar":
        raise Phase3Error(f"Common Voice source is not the pinned gzip-compressed tar: {exact[0]}")
    return exact[0]


def safe_member_name(name: str, prefix: str) -> bool:
    pure = PurePosixPath(name)
    return (
        not pure.is_absolute()
        and ".." not in pure.parts
        and "" not in pure.parts
        and name.startswith(prefix + "/")
    )


class HashingReader(io.RawIOBase):
    """Hash every compressed byte consumed by a streaming tar reader."""

    def __init__(self, raw: BinaryIO) -> None:
        self.raw = raw
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        chunk = self.raw.read(size)
        if chunk:
            self.digest.update(chunk)
            self.bytes_read += len(chunk)
        return chunk

    def readinto(self, buffer: bytearray) -> int:
        count = self.raw.readinto(buffer)
        if count:
            self.digest.update(memoryview(buffer)[:count])
            self.bytes_read += count
        return count

    def drain(self) -> None:
        while self.read(8 * 1024 * 1024):
            pass

    @property
    def hexdigest(self) -> str:
        return self.digest.hexdigest().upper()


def _copy_member(archive: tarfile.TarFile, member: tarfile.TarInfo, target: Path) -> None:
    source = archive.extractfile(member)
    if source is None:
        raise Phase3Error(f"Could not read archive member: {member.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with source, temporary.open("wb") as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)
    if temporary.stat().st_size != member.size:
        raise Phase3Error(f"Extracted metadata size mismatch: {member.name}")
    temporary.replace(target)


def _metadata_info(path: Path, archive_member: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_archive_member": archive_member,
        "prepared_relative_path": f"metadata/original/{path.name}",
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "rows": None,
        "columns": [],
    }
    if path.suffix.casefold() == ".tsv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, delimiter="\t")
            result["columns"] = next(reader, [])
            result["rows"] = sum(1 for _ in reader)
    return result


def source_audit(paths: Phase3Paths, release: dict[str, Any]) -> dict[str, Any]:
    """One full pass: compressed hash, structure validation, member index, metadata."""
    audit_path = paths.audits / "common_voice_source_archive_audit.json"
    index_path = paths.state / "archive_members.sqlite3"
    if audit_path.is_file() and index_path.is_file():
        existing = json.loads(audit_path.read_text(encoding="utf-8"))
        if (
            existing.get("archive_sha256") == str(release["archive_sha256"]).upper()
            and existing.get("archive_bytes") == int(release["archive_size_bytes"])
            and existing.get("archive_structure_valid") is True
            and all(
                (paths.original_metadata / item["prepared_relative_path"].split("/")[-1]).is_file()
                for item in existing.get("metadata_files", [])
            )
        ):
            return existing

    for directory in (
        paths.original_metadata,
        paths.derived_metadata,
        paths.clips,
        paths.state,
        paths.registries,
        paths.audits,
        paths.manifests,
        paths.license_evidence,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    prefix = f"{release['release_id']}/en"
    staging = paths.state / "source_audit_staging"
    if staging.exists():
        if staging.resolve().parent != paths.state.resolve():
            raise Phase3Error("Unsafe source-audit staging path")
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    staging_index = staging / "archive_members.sqlite3"
    connection = sqlite3.connect(staging_index)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute(
        "CREATE TABLE members (member TEXT PRIMARY KEY, size_bytes INTEGER NOT NULL, kind TEXT NOT NULL)"
    )
    member_rows: list[tuple[str, int, str]] = []
    metadata_members: dict[str, str] = {}
    member_count = 0
    clip_member_count = 0
    stat_before = paths.archive.stat()
    with paths.archive.open("rb") as raw:
        hashing = HashingReader(raw)
        with tarfile.open(fileobj=hashing, mode="r|gz") as archive:
            for member in archive:
                member_count += 1
                if not safe_member_name(member.name, prefix):
                    raise Phase3Error(f"Unsafe or unexpected archive member: {member.name}")
                kind = "file" if member.isfile() else "directory" if member.isdir() else "other"
                if kind == "other":
                    raise Phase3Error(f"Unsupported archive member type: {member.name}")
                member_rows.append((member.name, int(member.size), kind))
                if len(member_rows) >= 10_000:
                    connection.executemany("INSERT INTO members VALUES (?, ?, ?)", member_rows)
                    connection.commit()
                    member_rows.clear()
                relative = member.name.removeprefix(prefix + "/")
                if relative.startswith("clips/") and member.isfile():
                    clip_member_count += 1
                if relative in METADATA_NAMES and member.isfile():
                    _copy_member(archive, member, staging / "metadata" / relative)
                    metadata_members[relative] = member.name
        hashing.drain()
    if member_rows:
        connection.executemany("INSERT INTO members VALUES (?, ?, ?)", member_rows)
        connection.commit()
    connection.execute("CREATE INDEX members_size_idx ON members(size_bytes)")
    connection.commit()
    connection.close()
    stat_after = paths.archive.stat()

    expected_sha = str(release["archive_sha256"]).upper()
    if hashing.bytes_read != int(release["archive_size_bytes"]) or hashing.hexdigest != expected_sha:
        raise Phase3Error(
            f"Pinned archive identity mismatch: bytes={hashing.bytes_read}, sha256={hashing.hexdigest}"
        )
    if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
        raise Phase3Error("Source archive changed during verification")
    required = {"README.md", "validated.tsv", "invalidated.tsv", "other.tsv", "train.tsv", "dev.tsv", "test.tsv", "reported.tsv", "clip_durations.tsv"}
    missing = sorted(required - set(metadata_members))
    if missing:
        raise Phase3Error(f"Required source metadata is missing: {', '.join(missing)}")

    for name, member_name in sorted(metadata_members.items()):
        source = staging / "metadata" / name
        target = paths.original_metadata / name
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
    staging_index.replace(index_path)
    shutil.rmtree(staging)
    metadata_info = [
        _metadata_info(paths.original_metadata / name, member)
        for name, member in sorted(metadata_members.items())
    ]
    audit = {
        "schema_version": "common-voice-source-archive-audit.v1",
        "archive_logical_root": "JP_DATA_ROOT",
        "archive_relative_path": paths.archive.relative_to(paths.data_root).as_posix(),
        "archive_actual_filename": paths.archive.name,
        "archive_display_name": paths.archive.stem,
        "archive_detected_format": detect_archive_format(paths.archive),
        "archive_bytes": hashing.bytes_read,
        "archive_sha256": hashing.hexdigest,
        "expected_bytes_match": True,
        "expected_sha256_match": True,
        "archive_structure_valid": True,
        "archive_member_count": member_count,
        "archive_clip_member_count": clip_member_count,
        "archive_full_sequential_passes": 1,
        "metadata_files": metadata_info,
        "source_archive_copied": False,
        "source_archive_moved": False,
        "verified_at_utc": utc_now(),
    }
    atomic_json(audit_path, audit)
    atomic_text(paths.audits / "common_voice_source_archive_audit.md", markdown_json("Common Voice source archive audit", audit))
    return audit


def iter_tsv(path: Path) -> tuple[list[str], Iterator[dict[str, str]]]:
    stream = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.DictReader(stream, delimiter="\t")
    columns = list(reader.fieldnames or [])

    def rows() -> Iterator[dict[str, str]]:
        try:
            yield from reader
        finally:
            stream.close()

    return columns, rows()


def require_columns(columns: Iterable[str], required: Iterable[str], filename: str) -> None:
    missing = sorted(set(required) - set(columns))
    if missing:
        raise Phase3Error(f"{filename} is missing required columns: {', '.join(missing)}")


def _duration_columns(columns: list[str]) -> tuple[str, str]:
    path_column = next((name for name in ("clip", "path", "audio_file") if name in columns), None)
    duration_column = next(
        (name for name in ("duration[ms]", "duration_ms", "duration") if name in columns), None
    )
    if not path_column or not duration_column:
        raise Phase3Error(f"clip_durations.tsv has unsupported columns: {columns}")
    return path_column, duration_column


def _insert_batches(
    connection: sqlite3.Connection,
    statement: str,
    values: Iterable[tuple[Any, ...]],
    *,
    batch_size: int = 20_000,
) -> int:
    batch: list[tuple[Any, ...]] = []
    count = 0
    for value in values:
        batch.append(value)
        if len(batch) >= batch_size:
            connection.executemany(statement, batch)
            connection.commit()
            count += len(batch)
            batch.clear()
    if batch:
        connection.executemany(statement, batch)
        connection.commit()
        count += len(batch)
    return count


def _duration_values(path: Path) -> Iterator[tuple[str, int]]:
    columns, rows = iter_tsv(path)
    path_column, duration_column = _duration_columns(columns)
    for row in rows:
        clip = (row.get(path_column) or "").strip()
        raw_duration = (row.get(duration_column) or "").strip()
        if not clip or not raw_duration:
            continue
        try:
            duration_ms = int(float(raw_duration))
        except ValueError as error:
            raise Phase3Error(f"Invalid duration for {clip}: {raw_duration}") from error
        yield clip, duration_ms


def _upstream_values(path: Path, split: str) -> Iterator[tuple[str, str]]:
    columns, rows = iter_tsv(path)
    require_columns(columns, ("path",), path.name)
    for row in rows:
        clip = (row.get("path") or "").strip()
        if clip:
            yield clip, split


def _reported_values(path: Path) -> Iterator[tuple[str, str]]:
    columns, rows = iter_tsv(path)
    key = "sentence_id" if "sentence_id" in columns else "sentence" if "sentence" in columns else None
    if key is None:
        raise Phase3Error(f"reported.tsv has no sentence identifier: {columns}")
    reason_columns = [name for name in columns if "reason" in name.casefold()]
    for row in rows:
        identifier = (row.get(key) or "").strip()
        if not identifier:
            continue
        reasons = sorted({(row.get(name) or "").strip() for name in reason_columns if (row.get(name) or "").strip()})
        yield identifier, "|".join(reasons)


def _bucket_values(path: Path, bucket: str) -> Iterator[tuple[str, str, str, str]]:
    columns, rows = iter_tsv(path)
    require_columns(columns, ("path", "client_id", "age"), path.name)
    for row in rows:
        yield (
            bucket,
            (row.get("path") or "").strip(),
            (row.get("age") or "").strip(),
            (row.get("client_id") or "").strip(),
        )


def _candidate_values(path: Path, selected_age_labels: set[str]) -> Iterator[tuple[Any, ...]]:
    columns, rows = iter_tsv(path)
    required = ("client_id", "path", "sentence", "sentence_id", "age", "accents", "locale")
    require_columns(columns, required, path.name)
    for row in rows:
        age = (row.get("age") or "").strip()
        if age not in selected_age_labels:
            continue
        client_id = (row.get("client_id") or "").strip()
        clip_path = (row.get("path") or "").strip()
        transcript = (row.get("sentence") or "").strip()
        locale = (row.get("locale") or "").strip()
        if not client_id or not clip_path or not transcript or locale != "en":
            continue
        if PurePosixPath(clip_path).name != clip_path or ".." in PurePosixPath(clip_path).parts:
            raise Phase3Error(f"Unsafe Common Voice clip path in validated.tsv: {clip_path}")
        yield (
            clip_path,
            client_id,
            transcript,
            (row.get("sentence_id") or "").strip(),
            (row.get("sentence_domain") or "").strip(),
            age,
            AGE_MAP[age],
            (row.get("gender") or "").strip(),
            (row.get("accents") or "").strip(),
            (row.get("variant") or "").strip(),
            locale,
            (row.get("up_votes") or "").strip(),
            (row.get("down_votes") or "").strip(),
        )


def build_metadata_state(paths: Phase3Paths, release: dict[str, Any]) -> dict[str, Any]:
    """Import archive TSVs into a resumable local SQLite analysis state."""
    summary_path = paths.derived_metadata / "common_voice_metadata_summary.json"
    database_path = paths.state / "common_voice_phase3.sqlite3"
    member_list_path = paths.manifests / "common_voice_older_candidate_archive_members.v1.txt"
    if summary_path.is_file() and database_path.is_file() and member_list_path.is_file():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
        if existing.get("release_id") == release["release_id"]:
            return existing

    if database_path.exists():
        database_path.unlink()
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(
        """
        CREATE TABLE durations (path TEXT PRIMARY KEY, duration_ms INTEGER NOT NULL);
        CREATE TABLE upstream (path TEXT PRIMARY KEY, split TEXT NOT NULL);
        CREATE TABLE reported (sentence_key TEXT NOT NULL, reasons TEXT NOT NULL);
        CREATE INDEX reported_key_idx ON reported(sentence_key);
        CREATE TABLE bucket_rows (
            bucket TEXT NOT NULL, path TEXT NOT NULL, age TEXT NOT NULL, client_id TEXT NOT NULL
        );
        CREATE INDEX bucket_age_idx ON bucket_rows(bucket, age);
        CREATE INDEX bucket_path_idx ON bucket_rows(path);
        CREATE TABLE candidates (
            path TEXT PRIMARY KEY, client_id TEXT NOT NULL, transcript TEXT NOT NULL,
            sentence_id TEXT NOT NULL, sentence_domain TEXT NOT NULL,
            source_age_label TEXT NOT NULL, normalized_age_bin TEXT NOT NULL,
            gender TEXT NOT NULL, accents TEXT NOT NULL, variant TEXT NOT NULL,
            locale TEXT NOT NULL, up_votes TEXT NOT NULL, down_votes TEXT NOT NULL
        );
        CREATE TABLE audio_validation (
            path TEXT PRIMARY KEY, audio_sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            duration_seconds REAL NOT NULL, sample_rate_hz INTEGER NOT NULL,
            channels INTEGER NOT NULL, format TEXT NOT NULL, readable INTEGER NOT NULL,
            duration_delta_seconds REAL
        );
        """
    )
    metadata = paths.original_metadata
    duration_rows = _insert_batches(
        connection,
        "INSERT INTO durations VALUES (?, ?)",
        _duration_values(metadata / "clip_durations.tsv"),
    )
    for name, split in (("train.tsv", "train"), ("dev.tsv", "dev"), ("test.tsv", "test")):
        try:
            _insert_batches(
                connection,
                "INSERT INTO upstream VALUES (?, ?)",
                _upstream_values(metadata / name, split),
            )
        except sqlite3.IntegrityError as error:
            raise Phase3Error("Mozilla upstream train/dev/test splits overlap by clip path") from error
    _insert_batches(connection, "INSERT INTO reported VALUES (?, ?)", _reported_values(metadata / "reported.tsv"))
    for name, bucket in (("validated.tsv", "validated"), ("invalidated.tsv", "invalidated"), ("other.tsv", "other")):
        _insert_batches(
            connection,
            "INSERT INTO bucket_rows VALUES (?, ?, ?, ?)",
            _bucket_values(metadata / name, bucket),
        )
    observed_age_labels = {
        row[0] for row in connection.execute("SELECT DISTINCT age FROM bucket_rows WHERE age <> ''")
    }
    selected_age_labels = set(AGE_MAP) & observed_age_labels
    if not selected_age_labels:
        raise Phase3Error("The verified archive contains no explicit age>=60 labels")
    candidate_rows = _insert_batches(
        connection,
        "INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _candidate_values(metadata / "validated.tsv", selected_age_labels),
    )
    if candidate_rows == 0:
        raise Phase3Error("No validated English age>=60 metadata candidates were found")

    prefix = f"{release['release_id']}/en/clips/"
    connection.execute("ATTACH DATABASE ? AS archive", (str(paths.state / "archive_members.sqlite3"),))
    missing_members = connection.execute(
        """
        SELECT COUNT(*) FROM candidates c
        LEFT JOIN archive.members m ON m.member = ? || c.path AND m.kind = 'file'
        WHERE m.member IS NULL
        """,
        (prefix,),
    ).fetchone()[0]
    if missing_members:
        raise Phase3Error(f"{missing_members} older candidate MP3 members are missing from the archive")
    selected = list(
        connection.execute(
            """
            SELECT ? || c.path, c.path, m.size_bytes
            FROM candidates c JOIN archive.members m ON m.member = ? || c.path
            ORDER BY 1
            """,
            (prefix, prefix),
        )
    )
    connection.execute("DETACH DATABASE archive")
    member_text = "".join(f"{member}\n" for member, _, _ in selected)
    atomic_text(member_list_path, member_text)
    member_sha = hashlib.sha256(member_text.encode("utf-8")).hexdigest().upper()
    selected_bytes = sum(int(size) for _, _, size in selected)

    bucket_summary: dict[str, Any] = {}
    for bucket in ("validated", "invalidated", "other"):
        clips, duration_ms = connection.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(d.duration_ms), 0)
            FROM bucket_rows b LEFT JOIN durations d ON d.path = b.path
            WHERE b.bucket = ?
            """,
            (bucket,),
        ).fetchone()
        bucket_summary[bucket] = {"clips": int(clips), "hours": float(duration_ms) / 3_600_000}
    upstream = {
        split: int(connection.execute("SELECT COUNT(*) FROM upstream WHERE split = ?", (split,)).fetchone()[0])
        for split in ("train", "dev", "test")
    }
    upstream["validated_unassigned"] = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM bucket_rows b LEFT JOIN upstream u ON u.path = b.path
            WHERE b.bucket = 'validated' AND u.path IS NULL
            """
        ).fetchone()[0]
    )
    age_inventory: list[dict[str, Any]] = []
    for age in sorted(observed_age_labels | {""}):
        whole_clips, whole_speakers = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT NULLIF(client_id, '')) FROM bucket_rows WHERE age = ?",
            (age,),
        ).fetchone()
        validated_clips, validated_speakers, duration_ms = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT NULLIF(b.client_id, '')), COALESCE(SUM(d.duration_ms), 0)
            FROM bucket_rows b LEFT JOIN durations d ON d.path = b.path
            WHERE b.bucket = 'validated' AND b.age = ?
            """,
            (age,),
        ).fetchone()
        age_inventory.append(
            {
                "age_label": age or "unspecified",
                "whole_release_clips": int(whole_clips),
                "whole_release_speakers": int(whole_speakers),
                "validated_clips": int(validated_clips),
                "validated_speakers": int(validated_speakers),
                "validated_hours": float(duration_ms) / 3_600_000,
            }
        )
    candidate_speakers = int(connection.execute("SELECT COUNT(DISTINCT client_id) FROM candidates").fetchone()[0])
    missing_age_validated = int(
        connection.execute("SELECT COUNT(*) FROM bucket_rows WHERE bucket = 'validated' AND age = ''").fetchone()[0]
    )
    connection.commit()
    connection.close()
    summary = {
        "schema_version": "common-voice-metadata-summary.v1",
        "release_id": release["release_id"],
        "duration_rows": duration_rows,
        "buckets": bucket_summary,
        "upstream_splits": upstream,
        "age_inventory": age_inventory,
        "selected_older_age_labels": sorted(selected_age_labels),
        "older_metadata_candidate_clips": candidate_rows,
        "older_metadata_candidate_speakers": candidate_speakers,
        "missing_age_validated_clips": missing_age_validated,
        "selected_archive_member_count": len(selected),
        "selected_archive_member_list_sha256": member_sha,
        "selected_audio_estimated_bytes": selected_bytes,
        "accent_filter_policy": "none",
        "validated_tsv_used_as_canonical_source": True,
        "upstream_splits_concatenated": False,
    }
    atomic_json(summary_path, summary)
    return summary


def _validate_audio_file(path: Path, expected_duration_ms: int | None) -> tuple[Any, ...]:
    audio_sha = sha256_file(path)
    try:
        info = sf.info(path)
        duration = float(info.duration)
        sample_rate = int(info.samplerate)
        channels = int(info.channels)
        audio_format = str(info.format or "MP3")
        readable = 1
    except Exception:  # libsndfile reports several format-specific exception types
        duration = 0.0
        sample_rate = 0
        channels = 0
        audio_format = "unreadable"
        readable = 0
    delta = None if expected_duration_ms is None or not readable else duration - expected_duration_ms / 1000
    return (
        path.name,
        audio_sha,
        path.stat().st_size,
        duration,
        sample_rate,
        channels,
        audio_format,
        readable,
        delta,
    )


def _record_audio(connection: sqlite3.Connection, value: tuple[Any, ...]) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO audio_validation
        (path, audio_sha256, size_bytes, duration_seconds, sample_rate_hz, channels, format, readable, duration_delta_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        value,
    )


def _materialization_state(
    paths: Phase3Paths,
    release: dict[str, Any],
    metadata_summary: dict[str, Any],
    *,
    expected: int,
    materialized: int,
    materialized_bytes: int,
    complete: bool,
    full_passes: int,
) -> dict[str, Any]:
    return {
        "schema_version": "common-voice-materialization-state.v1",
        "source_archive_sha256": str(release["archive_sha256"]).upper(),
        "release_id": release["release_id"],
        "candidate_membership_list_sha256": metadata_summary["selected_archive_member_list_sha256"],
        "expected_selected_clips": expected,
        "materialized_selected_clips": materialized,
        "materialized_bytes": materialized_bytes,
        "metadata_file_hashes": {
            path.name: sha256_file(path) for path in sorted(paths.original_metadata.iterdir()) if path.is_file()
        },
        "completion_state": "complete" if complete else "incomplete",
        "archive_full_sequential_passes_this_run": full_passes,
        "updated_at_utc": utc_now(),
    }


def materialize_selected_audio(
    paths: Phase3Paths,
    release: dict[str, Any],
    metadata_summary: dict[str, Any],
) -> dict[str, Any]:
    """Materialize every missing selected MP3 in one sequential archive pass."""
    database_path = paths.state / "common_voice_phase3.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute("ATTACH DATABASE ? AS archive", (str(paths.state / "archive_members.sqlite3"),))
    prefix = f"{release['release_id']}/en/clips/"
    selected_rows = list(
        connection.execute(
            """
            SELECT ? || c.path, c.path, m.size_bytes, d.duration_ms
            FROM candidates c
            JOIN archive.members m ON m.member = ? || c.path
            LEFT JOIN durations d ON d.path = c.path
            ORDER BY 1
            """,
            (prefix, prefix),
        )
    )
    connection.execute("DETACH DATABASE archive")
    expected_by_member = {
        member: (clip_path, int(size), int(duration) if duration is not None else None)
        for member, clip_path, size, duration in selected_rows
    }
    expected_by_path = {clip_path: (member, size, duration) for member, (clip_path, size, duration) in expected_by_member.items()}

    existing_rows = {
        row[0]: row for row in connection.execute("SELECT path, audio_sha256, size_bytes FROM audio_validation")
    }
    missing_members: set[str] = set()
    unindexed_existing: list[tuple[Path, int | None]] = []
    for clip_path, (member, size, duration_ms) in expected_by_path.items():
        target = paths.clips / clip_path
        prior = existing_rows.get(clip_path)
        if target.is_file() and target.stat().st_size == size and prior and int(prior[2]) == size:
            continue
        if target.is_file() and target.stat().st_size == size:
            unindexed_existing.append((target, duration_ms))
            continue
        missing_members.add(member)

    if unindexed_existing:
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as executor:
            for value in executor.map(lambda pair: _validate_audio_file(*pair), unindexed_existing):
                _record_audio(connection, value)
        connection.commit()

    missing_bytes = sum(expected_by_member[member][1] for member in missing_members)
    free_before = shutil.disk_usage(paths.prepared_root).free
    safety_margin = max(1_073_741_824, int(missing_bytes * 0.10))
    if free_before < missing_bytes + safety_margin:
        connection.close()
        raise Phase3Error(
            f"Insufficient space for selected Common Voice audio: need {missing_bytes + safety_margin}, "
            f"free {free_before}"
        )

    passes = 0
    extracted_this_run = 0
    if missing_members:
        passes = 1
        state_path = paths.state / "materialization_state.json"
        atomic_json(
            state_path,
            _materialization_state(
                paths,
                release,
                metadata_summary,
                expected=len(selected_rows),
                materialized=len(selected_rows) - len(missing_members),
                materialized_bytes=0,
                complete=False,
                full_passes=passes,
            ),
        )
        prefix_root = f"{release['release_id']}/en"
        stat_before = paths.archive.stat()
        with tarfile.open(paths.archive, mode="r|gz") as archive:
            for member in archive:
                if not safe_member_name(member.name, prefix_root):
                    raise Phase3Error(f"Unsafe archive member during selective extraction: {member.name}")
                if member.name not in missing_members:
                    continue
                clip_path, expected_size, duration_ms = expected_by_member[member.name]
                if not member.isfile() or member.size != expected_size:
                    raise Phase3Error(f"Selected archive member changed: {member.name}")
                source = archive.extractfile(member)
                if source is None:
                    raise Phase3Error(f"Could not read selected archive member: {member.name}")
                target = paths.clips / clip_path
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".part")
                digest = hashlib.sha256()
                written = 0
                with source, temporary.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
                        written += len(chunk)
                if written != expected_size:
                    raise Phase3Error(f"Selected extraction size mismatch: {member.name}")
                temporary.replace(target)
                value = _validate_audio_file(target, duration_ms)
                if value[1] != digest.hexdigest().upper():
                    raise Phase3Error(f"Post-write content hash mismatch: {member.name}")
                _record_audio(connection, value)
                missing_members.remove(member.name)
                extracted_this_run += 1
                if extracted_this_run % 1000 == 0:
                    connection.commit()
                    current_count, current_bytes = connection.execute(
                        "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM audio_validation"
                    ).fetchone()
                    atomic_json(
                        state_path,
                        _materialization_state(
                            paths,
                            release,
                            metadata_summary,
                            expected=len(selected_rows),
                            materialized=int(current_count),
                            materialized_bytes=int(current_bytes),
                            complete=False,
                            full_passes=passes,
                        ),
                    )
                if not missing_members:
                    break
        connection.commit()
        stat_after = paths.archive.stat()
        if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
            raise Phase3Error("Source archive changed during selective materialization")
        if missing_members:
            raise Phase3Error(f"{len(missing_members)} selected members were not found during extraction")

    materialized, materialized_bytes, readable, corrupt = connection.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(size_bytes), 0),
               SUM(CASE WHEN readable = 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN readable = 0 THEN 1 ELSE 0 END)
        FROM audio_validation WHERE path IN (SELECT path FROM candidates)
        """
    ).fetchone()
    format_counts = {
        str(audio_format): int(count)
        for audio_format, count in connection.execute(
            "SELECT format, COUNT(*) FROM audio_validation "
            "WHERE path IN (SELECT path FROM candidates) GROUP BY format ORDER BY format"
        )
    }
    missing = len(selected_rows) - int(materialized)
    complete = missing == 0
    state = _materialization_state(
        paths,
        release,
        metadata_summary,
        expected=len(selected_rows),
        materialized=int(materialized),
        materialized_bytes=int(materialized_bytes),
        complete=complete,
        full_passes=passes,
    )
    atomic_json(paths.state / "materialization_state.json", state)
    if complete:
        atomic_json(paths.state / "materialization_complete.json", state)
    audit = {
        **state,
        "archive_backend_used": "Python tarfile streaming gzip",
        "why_backend_selected": (
            "A single streaming traversal extracts all selected members directly to JP_TRAINING_ROOT, "
            "avoiding full extraction, per-clip archive reopening, and WSL-to-Windows full-corpus copying."
        ),
        "destination_free_bytes_before": free_before,
        "selected_audio_estimated_bytes": metadata_summary["selected_audio_estimated_bytes"],
        "selected_audio_actual_bytes": int(materialized_bytes),
        "selected_audio_materialized_files": int(materialized),
        "materialized_clips_readable": int(readable or 0),
        "materialized_clips_missing": int(missing),
        "materialized_clips_corrupt": int(corrupt or 0),
        "materialized_audio_formats": format_counts,
        "source_mp3_converted_to_wav": False,
        "full_common_voice_extraction": False,
        "raw_full_corpus_duplicated": False,
        "materialization_resumable": True,
        "extracted_this_run": extracted_this_run,
    }
    connection.close()
    atomic_json(paths.audits / "common_voice_materialization_audit.json", audit)
    atomic_text(paths.audits / "common_voice_materialization_audit.md", markdown_json("Common Voice materialization audit", audit))
    return audit


def _normalized_transcript(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _evaluation_transcripts(tool_root: Path, parent_freeze: dict[str, Any]) -> set[str]:
    transcripts: set[str] = set()
    for manifest in parent_freeze["evaluation_manifests"]:
        path = tool_root / manifest["canonical_path"]
        frame = pd.read_parquet(path)
        column = next(
            (name for name in ("reference_transcript", "transcript", "text", "sentence") if name in frame),
            None,
        )
        if column:
            transcripts.update(
                _normalized_transcript(value)
                for value in frame[column].dropna().astype(str)
                if _normalized_transcript(value)
            )
    return transcripts


def _resolve_evaluation_audio(data_root: Path, logical_path: str) -> Path:
    relative = PurePosixPath(str(logical_path).replace("\\", "/"))
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise Phase3Error(f"Unsafe evaluation audio path: {logical_path}")
    if relative.parts and ":" in relative.parts[0]:
        raise Phase3Error(f"Non-portable evaluation audio path: {logical_path}")
    resolved = data_root.joinpath(*relative.parts).resolve()
    if not resolved.is_relative_to(data_root.resolve()):
        raise Phase3Error(f"Evaluation audio path escapes JP_DATA_ROOT: {logical_path}")
    if not resolved.is_file():
        raise Phase3Error(f"Frozen evaluation source audio is missing: {logical_path}")
    return resolved


def _evaluation_content_hash_index(
    paths: Phase3Paths,
    exclusion: pd.DataFrame,
) -> tuple[set[str], dict[str, Any]]:
    """Hash the audio referenced by the frozen evaluation exclusion index."""
    columns = ("source_audio_logical_path", "source_original_audio_logical_path")
    logical_paths = sorted(
        {
            str(value)
            for column in columns
            if column in exclusion
            for value in exclusion[column].dropna().astype(str)
            if str(value).strip()
        }
    )
    cache_path = paths.state / "evaluation_content_hashes.json"
    cache_items: dict[str, dict[str, Any]] = {}
    if cache_path.is_file():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache.get("schema_version") == "evaluation-content-hash-cache.v1":
            cache_items = {
                str(item["logical_path"]): item
                for item in cache.get("items", [])
                if isinstance(item, dict) and item.get("logical_path")
            }

    records: dict[str, dict[str, Any]] = {}
    pending: list[tuple[str, Path, int, int]] = []
    reused = 0
    for logical_path in logical_paths:
        resolved = _resolve_evaluation_audio(paths.data_root, logical_path)
        stat = resolved.stat()
        cached = cache_items.get(logical_path)
        if (
            cached
            and cached.get("bytes") == stat.st_size
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and cached.get("sha256")
        ):
            records[logical_path] = cached
            reused += 1
        else:
            pending.append((logical_path, resolved, stat.st_size, stat.st_mtime_ns))

    def hash_record(item: tuple[str, Path, int, int]) -> dict[str, Any]:
        logical_path, resolved, size_bytes, mtime_ns = item
        return {
            "logical_path": logical_path,
            "bytes": size_bytes,
            "mtime_ns": mtime_ns,
            "sha256": sha256_file(resolved),
        }

    if pending:
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as executor:
            for record in executor.map(hash_record, pending):
                records[str(record["logical_path"])] = record

    ordered = [records[logical_path] for logical_path in logical_paths]
    atomic_json(
        cache_path,
        {"schema_version": "evaluation-content-hash-cache.v1", "items": ordered},
    )
    canonical = [
        {"logical_path": item["logical_path"], "bytes": item["bytes"], "sha256": item["sha256"]}
        for item in ordered
    ]
    summary = {
        "schema_version": "evaluation-content-hash-index.v1",
        "logical_path_count": len(ordered),
        "total_bytes": sum(int(item["bytes"]) for item in ordered),
        "sha256": _json_hash(canonical),
        "hashes_computed_this_run": len(pending),
        "hashes_reused_from_cache": reused,
        "all_referenced_audio_available": True,
    }
    return {str(item["sha256"]) for item in ordered}, summary


def _hash_rank(speaker: str, age_bin: str) -> str:
    return hashlib.sha256(f"{SPLIT_SEED}|{age_bin}|{speaker}".encode("utf-8")).hexdigest()


def deterministic_speaker_split(frame: pd.DataFrame) -> tuple[dict[str, str], dict[str, bool]]:
    """Assign speakers with age-bin strata and duration-first greedy targets."""
    speaker_age = (
        frame.groupby(["speaker_id", "normalized_age_bin"], as_index=False)["duration_seconds"]
        .sum()
        .sort_values(
            ["speaker_id", "duration_seconds", "normalized_age_bin"],
            ascending=[True, False, True],
            kind="mergesort",
        )
        .drop_duplicates("speaker_id")
    )
    speaker_duration = frame.groupby("speaker_id", as_index=False)["duration_seconds"].sum()
    speakers = speaker_age[["speaker_id", "normalized_age_bin"]].merge(speaker_duration, on="speaker_id")
    assignments: dict[str, str] = {}
    underpowered: dict[str, bool] = {}
    targets = {"train": 0.8, "dev": 0.1, "heldout": 0.1}
    order = ("train", "dev", "heldout")
    for age_bin, group in speakers.groupby("normalized_age_bin", sort=True):
        values = [
            (str(row.speaker_id), float(row.duration_seconds), _hash_rank(str(row.speaker_id), str(age_bin)))
            for row in group.itertuples(index=False)
        ]
        values.sort(key=lambda value: (-value[1], value[2], value[0]))
        underpowered[str(age_bin)] = len(values) < 10
        total_duration = sum(value[1] for value in values)
        current = {name: 0.0 for name in order}
        current_speakers = {name: 0 for name in order}
        minimum = {name: (1 if len(values) >= 3 else 0) for name in order}
        for index, (speaker, duration, rank) in enumerate(values):
            remaining_including = len(values) - index
            missing_roles = [name for name in order if current_speakers[name] < minimum[name]]
            if missing_roles and remaining_including == len(missing_roles):
                role = min(missing_roles, key=lambda name: (order.index(name), rank))
            else:
                role = max(
                    order,
                    key=lambda name: (
                        (targets[name] * total_duration - current[name]) / max(targets[name], 1e-9),
                        -order.index(name),
                    ),
                )
            assignments[speaker] = role
            current[role] += duration
            current_speakers[role] += 1
    return assignments, underpowered


def _apply_common_voice_eligibility(frame: pd.DataFrame, initially_eligible: pd.Series) -> None:
    """Apply license eligibility and the non-negotiable heldout training lock."""
    frame["technical_training_eligible"] = initially_eligible
    frame["commercial_training_eligible"] = initially_eligible
    frame["review_gated_training_eligible"] = False
    frame["strict_training_eligible"] = initially_eligible & frame["training_role"].ne("heldout")
    frame["relaxed_training_eligible"] = frame["strict_training_eligible"]


def _phase2_pool_stats(frame: pd.DataFrame, dataset: str) -> dict[str, Any]:
    source = frame.loc[frame["dataset_id"].eq(dataset)].copy()
    if dataset == "chime6":
        eligible = source.loc[
            source["strict_training_eligible"].fillna(False)
            & source["review_gated_training_eligible"].fillna(False)
        ].copy()
    else:
        eligible = source.loc[
            source["strict_training_eligible"].fillna(False)
            & source["commercial_training_eligible"].fillna(False)
        ].copy()
    unique_key = "source_utterance_id" if dataset in {"ami", "chime6", "voices"} else "source_item_id"
    unique = eligible.sort_values("source_item_id", kind="mergesort").drop_duplicates(unique_key)
    physical_hours = float(pd.to_numeric(eligible["duration_seconds"], errors="coerce").fillna(0).sum()) / 3600
    unique_hours = float(pd.to_numeric(unique["duration_seconds"], errors="coerce").fillna(0).sum()) / 3600
    result = {
        "dataset": dataset,
        "registry_records": int(len(source)),
        "physical_hours": float(pd.to_numeric(source["duration_seconds"], errors="coerce").fillna(0).sum()) / 3600,
        "unique_source_hours": float(
            pd.to_numeric(
                source.sort_values("source_item_id", kind="mergesort").drop_duplicates(unique_key)["duration_seconds"],
                errors="coerce",
            ).fillna(0).sum()
        ) / 3600,
        "strict_eligible_records": int(len(eligible)),
        "strict_eligible_physical_hours": physical_hours,
        "strict_eligible_unique_hours": unique_hours,
        "strict_eligible_speakers": int(eligible["speaker_id"].dropna().astype(str).nunique()),
        "license_composition": eligible["license_id"].fillna("unknown").value_counts().to_dict(),
    }
    if dataset == "ami":
        result.update(
            strict_eligible_meetings=int(eligible["meeting_id"].dropna().astype(str).nunique()),
            available_acoustic_views=sorted(
                value for value in eligible["source_recording_id"].dropna().astype(str).str.replace(r"^AMI_[^_]+_", "", regex=True).unique()
            ),
        )
    if dataset == "chime6":
        result.update(
            strict_eligible_sessions=int(eligible["session_id"].dropna().astype(str).nunique()),
            channel_view_count=int(eligible["source_recording_id"].dropna().astype(str).nunique()),
            model_release_review_required=True,
        )
    if dataset == "voices":
        unique_utterances = int(eligible["source_utterance_id"].dropna().astype(str).nunique())
        result.update(
            unique_source_utterances=unique_utterances,
            retransmission_count=int(len(eligible) - unique_utterances),
        )
    return result


def _combine_pool(name: str, components: list[dict[str, Any]], *, review: bool) -> dict[str, Any]:
    return {
        "name": name,
        "datasets": [component["dataset"] for component in components],
        "records": sum(int(component.get("strict_eligible_records", component.get("records", 0))) for component in components),
        "physical_hours": sum(float(component.get("strict_eligible_physical_hours", component.get("hours", 0))) for component in components),
        "unique_source_hours": sum(float(component.get("strict_eligible_unique_hours", component.get("hours", 0))) for component in components),
        "speakers": sum(int(component.get("strict_eligible_speakers", component.get("speakers", 0))) for component in components),
        "sessions": sum(
            int(component.get("strict_eligible_sessions", 0)) + int(component.get("strict_eligible_meetings", 0))
            for component in components
        ),
        "license_composition": dict(
            sum((Counter(component.get("license_composition", {})) for component in components), Counter())
        ),
        "release_review_required": review,
    }


def build_registry_and_freeze(
    paths: Phase3Paths,
    release: dict[str, Any],
    metadata_summary: dict[str, Any],
    materialization: dict[str, Any],
    *,
    parent_freeze_path: Path,
    evaluation_exclusion_path: Path,
    phase2_registry_path: Path,
    tool_root: Path,
) -> dict[str, Any]:
    if not materialization.get("completion_state") == "complete":
        raise Phase3Error("Materialization is incomplete; refusing to create Phase-3 freeze")
    parent = json.loads(parent_freeze_path.read_text(encoding="utf-8"))
    exclusion = pd.read_parquet(evaluation_exclusion_path)
    exact_recordings = set(exclusion["source_recording_id"].dropna().astype(str))
    exact_utterances = set(exclusion["source_utterance_id"].dropna().astype(str))
    exact_paths = set(exclusion["source_audio_logical_path"].dropna().astype(str))
    strict_groups = set(exclusion["strict_group_id"].dropna().astype(str))
    evaluation_transcripts = _evaluation_transcripts(tool_root, parent)
    evaluation_content_hashes, evaluation_content_index = _evaluation_content_hash_index(paths, exclusion)

    connection = sqlite3.connect(paths.state / "common_voice_phase3.sqlite3")
    query = """
        SELECT c.path, c.client_id, c.transcript, c.sentence_id, c.sentence_domain,
               c.source_age_label, c.normalized_age_bin, c.gender, c.accents, c.variant,
               c.locale, c.up_votes, c.down_votes,
               COALESCE(u.split, 'validated_unassigned'), d.duration_ms,
               a.audio_sha256, a.size_bytes, a.duration_seconds, a.sample_rate_hz,
               a.channels, a.format, a.readable,
               EXISTS(SELECT 1 FROM reported r WHERE r.sentence_key IN (c.sentence_id, c.transcript)),
               COALESCE((SELECT GROUP_CONCAT(DISTINCT reasons) FROM reported r
                         WHERE r.sentence_key IN (c.sentence_id, c.transcript)), '')
        FROM candidates c
        LEFT JOIN upstream u ON u.path = c.path
        LEFT JOIN durations d ON d.path = c.path
        LEFT JOIN audio_validation a ON a.path = c.path
        ORDER BY c.path
    """
    rows = list(connection.execute(query))
    connection.close()
    columns = [
        "path", "client_id", "transcript", "sentence_id", "sentence_domain",
        "source_age_label", "normalized_age_bin", "gender", "accents", "variant",
        "locale", "up_votes", "down_votes", "upstream_common_voice_split", "duration_ms",
        "audio_sha256", "size_bytes", "duration_seconds", "sample_rate_hz", "channels",
        "audio_format", "readable", "reported_sentence_flag", "reported_reasons",
    ]
    raw = pd.DataFrame(rows, columns=columns)
    raw["readable"] = raw["readable"].fillna(0).astype(bool)
    raw["reported_sentence_flag"] = raw["reported_sentence_flag"].astype(bool)
    raw["duration_seconds"] = pd.to_numeric(raw["duration_seconds"], errors="coerce").fillna(
        pd.to_numeric(raw["duration_ms"], errors="coerce").fillna(0) / 1000
    )
    raw["source_item_id"] = raw["path"].map(lambda value: f"common_voice:{release['release_id']}:{value}")
    raw["source_recording_id"] = raw["source_item_id"]
    raw["source_utterance_id"] = raw.apply(
        lambda row: f"common_voice:{row['sentence_id']}:{row['path']}", axis=1
    )
    raw["speaker_id"] = raw["client_id"]
    raw["speaker_group_id"] = "common_voice:speaker:" + raw["client_id"]
    raw["source_archive_member"] = raw["path"].map(
        lambda value: f"{release['release_id']}/en/clips/{value}"
    )
    raw["source_audio_relative_path"] = raw["source_archive_member"]
    raw["prepared_audio_relative_path"] = "clips/" + raw["path"]
    raw["resolved_audio_path"] = raw["path"].map(lambda value: str(paths.clips / value))
    raw["transcript_sha256"] = raw["transcript"].map(
        lambda value: hashlib.sha256(str(value).encode("utf-8")).hexdigest().upper()
    )
    raw["evaluation_exact_match"] = (
        raw["source_recording_id"].isin(exact_recordings)
        | raw["source_utterance_id"].isin(exact_utterances)
        | raw["source_audio_relative_path"].isin(exact_paths)
    )
    raw["evaluation_group_match"] = raw["speaker_group_id"].isin(strict_groups)
    raw["evaluation_cross_dataset_match"] = False
    raw["evaluation_content_hash_match"] = raw["audio_sha256"].isin(evaluation_content_hashes)
    raw["evaluation_transcript_only_match"] = raw["transcript"].map(_normalized_transcript).isin(
        evaluation_transcripts
    )

    hash_counts = raw.loc[raw["audio_sha256"].notna(), "audio_sha256"].value_counts()
    duplicate_hashes = set(hash_counts[hash_counts.gt(1)].index)
    canonical_by_hash = (
        raw.loc[raw["audio_sha256"].isin(duplicate_hashes)]
        .sort_values("path", kind="mergesort")
        .drop_duplicates("audio_sha256")
        .set_index("audio_sha256")["path"]
        .to_dict()
    )
    raw["duplicate_audio_canonical_path"] = raw["audio_sha256"].map(canonical_by_hash)
    raw["duplicate_audio_excluded"] = raw.apply(
        lambda row: bool(row["audio_sha256"] in duplicate_hashes and row["path"] != canonical_by_hash[row["audio_sha256"]]),
        axis=1,
    )
    raw["materialized_available"] = raw["path"].map(lambda value: (paths.clips / value).is_file())
    reasons: list[str | None] = []
    for row in raw.itertuples(index=False):
        values: list[str] = []
        if not row.materialized_available:
            values.append("materialized_audio_missing")
        if not row.readable:
            values.append("audio_unreadable")
        if row.evaluation_exact_match:
            values.append("evaluation_exact_match")
        if row.evaluation_group_match:
            values.append("evaluation_group_match")
        if row.evaluation_cross_dataset_match:
            values.append("evaluation_cross_dataset_match")
        if row.evaluation_content_hash_match:
            values.append("evaluation_content_hash_match")
        if row.duplicate_audio_excluded:
            values.append(f"duplicate_audio:{row.duplicate_audio_canonical_path}")
        reasons.append(";".join(values) if values else None)
    raw["exclusion_reason"] = reasons
    initially_eligible = raw["exclusion_reason"].isna()
    assignments, underpowered = deterministic_speaker_split(raw.loc[initially_eligible])
    raw["just_peachy_training_split"] = raw["speaker_id"].map(assignments)
    raw["training_role"] = raw["just_peachy_training_split"]
    _apply_common_voice_eligibility(raw, initially_eligible)
    raw["license_policy_status"] = "verified_cc0_training_allowed"
    raw["commercial_training_status"] = "allowed"
    raw["commercial_release_review_status"] = "normal_provenance_review"

    registry = pd.DataFrame(
        {
            "registry_schema_version": REGISTRY_SCHEMA,
            "dataset_id": "common_voice",
            "dataset_version": release["corpus_version"],
            "common_voice_release_id": release["release_id"],
            "source_archive_id": "common_voice_source_" + str(release["archive_sha256"])[:12].lower(),
            "source_archive_sha256": str(release["archive_sha256"]).upper(),
            "source_archive_member": raw["source_archive_member"],
            "source_item_id": raw["source_item_id"],
            "source_recording_id": raw["source_recording_id"],
            "source_utterance_id": raw["source_utterance_id"],
            "source_audio_root_id": "JP_DATA_ROOT",
            "source_audio_relative_path": raw["source_audio_relative_path"],
            "prepared_audio_root_id": "JP_TRAINING_ROOT",
            "prepared_audio_relative_path": raw["prepared_audio_relative_path"],
            "resolved_audio_path": raw["resolved_audio_path"],
            "audio_sha256": raw["audio_sha256"],
            "raw_transcript": raw["transcript"],
            "transcript": raw["transcript"],
            "transcript_sha256": raw["transcript_sha256"],
            "speaker_id": raw["speaker_id"],
            "speaker_group_id": raw["speaker_group_id"],
            "upstream_common_voice_split": raw["upstream_common_voice_split"],
            "just_peachy_training_split": raw["just_peachy_training_split"],
            "training_role": raw["training_role"],
            "language": "English",
            "locale": raw["locale"],
            "duration_seconds": raw["duration_seconds"],
            "sample_rate_hz": raw["sample_rate_hz"],
            "channels": raw["channels"],
            "source_age_label": raw["source_age_label"],
            "normalized_age_bin": raw["normalized_age_bin"],
            "gender": raw["gender"].replace("", pd.NA),
            "accents": raw["accents"].replace("", pd.NA),
            "variant": raw["variant"].replace("", pd.NA),
            "sentence_id": raw["sentence_id"],
            "sentence_domain": raw["sentence_domain"].replace("", pd.NA),
            "up_votes": pd.to_numeric(raw["up_votes"], errors="coerce").astype("Int64"),
            "down_votes": pd.to_numeric(raw["down_votes"], errors="coerce").astype("Int64"),
            "reported_sentence_flag": raw["reported_sentence_flag"],
            "reported_reasons": raw["reported_reasons"].replace("", pd.NA),
            "license_id": "CC0-1.0",
            "license_policy_status": raw["license_policy_status"],
            "commercial_training_status": raw["commercial_training_status"],
            "commercial_release_review_status": raw["commercial_release_review_status"],
            "attribution_required": False,
            "sharealike_flag": False,
            "source_available": True,
            "materialized_available": raw["materialized_available"],
            "evaluation_exact_match": raw["evaluation_exact_match"],
            "evaluation_group_match": raw["evaluation_group_match"],
            "evaluation_cross_dataset_match": raw["evaluation_cross_dataset_match"],
            "evaluation_content_hash_match": raw["evaluation_content_hash_match"],
            "evaluation_transcript_only_match": raw["evaluation_transcript_only_match"],
            "duplicate_audio_canonical_path": raw["duplicate_audio_canonical_path"],
            "technical_training_eligible": raw["technical_training_eligible"],
            "commercial_training_eligible": raw["commercial_training_eligible"],
            "review_gated_training_eligible": raw["review_gated_training_eligible"],
            "strict_training_eligible": raw["strict_training_eligible"],
            "relaxed_training_eligible": raw["relaxed_training_eligible"],
            "exclusion_reason": raw["exclusion_reason"],
        }
    ).sort_values("source_item_id", kind="mergesort").reset_index(drop=True)
    split = registry.loc[registry["exclusion_reason"].isna(), [
        "source_item_id", "speaker_id", "source_age_label", "normalized_age_bin",
        "duration_seconds", "just_peachy_training_split", "training_role", "strict_training_eligible",
    ]].copy()
    split.insert(0, "split_schema_version", SPLIT_SCHEMA)

    registry_sha = _frame_hash(registry, omit=("resolved_audio_path",))
    split_sha = _frame_hash(split)
    registry_id = "common_voice_older_registry_" + registry_sha[:12].lower()
    split_id = "common_voice_older_split_" + split_sha[:12].lower()
    registry_path = paths.registries / "common_voice_older_registry.parquet"
    split_path = paths.registries / "common_voice_older_split.parquet"
    registry.to_parquet(registry_path, index=False)
    split.to_parquet(split_path, index=False)

    eligible = registry.loc[registry["exclusion_reason"].isna()].copy()
    split_summary: dict[str, Any] = {
        "schema_version": "common-voice-older-split-summary.v1",
        "split_algorithm_version": SPLIT_ALGORITHM_VERSION,
        "split_seed": SPLIT_SEED,
        "split_id": split_id,
        "split_sha256": split_sha,
        "roles": {},
        "per_age": {},
        "speaker_overlaps": {},
    }
    role_speakers: dict[str, set[str]] = {}
    for role in ("train", "dev", "heldout"):
        part = eligible.loc[eligible["training_role"].eq(role)]
        role_speakers[role] = set(part["speaker_id"].astype(str))
        split_summary["roles"][role] = {
            "speakers": len(role_speakers[role]),
            "clips": int(len(part)),
            "hours": float(part["duration_seconds"].sum()) / 3600,
        }
    for left, right in (("train", "dev"), ("train", "heldout"), ("dev", "heldout")):
        split_summary["speaker_overlaps"][f"{left}_{right}"] = len(role_speakers[left] & role_speakers[right])
    if any(split_summary["speaker_overlaps"].values()):
        raise Phase3Error("Speaker-disjoint split invariant failed")
    for age_bin in sorted(eligible["normalized_age_bin"].unique()):
        split_summary["per_age"][age_bin] = {"underpowered": underpowered.get(age_bin, True)}
        for role in ("train", "dev", "heldout"):
            part = eligible.loc[
                eligible["normalized_age_bin"].eq(age_bin) & eligible["training_role"].eq(role)
            ]
            split_summary["per_age"][age_bin][role] = {
                "speakers": int(part["speaker_id"].nunique()),
                "clips": int(len(part)),
                "hours": float(part["duration_seconds"].sum()) / 3600,
            }
    if bool(eligible.loc[eligible["training_role"].eq("heldout"), "strict_training_eligible"].any()):
        raise Phase3Error("Heldout lock invariant failed")

    accents: dict[str, dict[str, Any]] = {}
    accent_speakers: defaultdict[str, set[str]] = defaultdict(set)
    accent_clips: Counter[str] = Counter()
    accent_seconds: Counter[str] = Counter()
    multiple_accent_speakers: set[str] = set()
    unspecified_accent_speakers: set[str] = set()
    for row in eligible.itertuples(index=False):
        raw_accents = "" if pd.isna(row.accents) else str(row.accents)
        tokens = sorted({token.strip() for token in raw_accents.split(",") if token.strip()})
        if not tokens:
            tokens = ["unspecified"]
            unspecified_accent_speakers.add(str(row.speaker_id))
        if len(tokens) > 1:
            multiple_accent_speakers.add(str(row.speaker_id))
        for accent in tokens:
            accent_speakers[accent].add(str(row.speaker_id))
            accent_clips[accent] += 1
            accent_seconds[accent] += float(row.duration_seconds)
    for accent in sorted(accent_clips):
        accents[accent] = {
            "speaker_incidence": len(accent_speakers[accent]),
            "clip_incidence": accent_clips[accent],
            "hours": accent_seconds[accent] / 3600,
        }

    phase2 = pd.read_parquet(phase2_registry_path)
    phase2_stats = {dataset: _phase2_pool_stats(phase2, dataset) for dataset in ("cmu_arctic", "ami", "chime6", "voices", "librispeech", "hifitts")}
    age_train = eligible.loc[eligible["training_role"].eq("train")]
    age_component = {
        "dataset": "common_voice_older_train",
        "records": int(len(age_train)),
        "hours": float(age_train["duration_seconds"].sum()) / 3600,
        "speakers": int(age_train["speaker_id"].nunique()),
        "license_composition": {"CC0-1.0": int(len(age_train))},
    }
    robust_components = [phase2_stats[name] for name in ("ami", "chime6", "voices")]
    pool_previews = {
        "age": {
            **age_component,
            "age_distribution": split_summary["per_age"],
            "accent_distribution": accents,
            "prepared_audio_root": "JP_TRAINING_ROOT:" + paths.prepared_root.relative_to(paths.training_root).as_posix(),
        },
        "cmu": phase2_stats["cmu_arctic"],
        "ami": phase2_stats["ami"],
        "chime": phase2_stats["chime6"],
        "voices": phase2_stats["voices"],
    }
    pool_previews["robust"] = _combine_pool("robust", robust_components, review=True)
    pool_previews["age_robust"] = _combine_pool("age_robust", [age_component, *robust_components], review=True)
    pool_previews["age_robust_cmu"] = _combine_pool(
        "age_robust_cmu", [age_component, *robust_components, phase2_stats["cmu_arctic"]], review=True
    )
    for name, preview in pool_previews.items():
        preview["preview_id"] = f"{name}_pool_preview_{_json_hash(preview)[:12].lower()}"

    release_sha = _json_hash(release)
    selected_sha = metadata_summary["selected_archive_member_list_sha256"]
    release_identity = "common_voice_release_" + release_sha[:12].lower()
    selected_identity = "common_voice_selected_members_" + selected_sha[:12].lower()
    source_identity = "common_voice_source_" + str(release["archive_sha256"])[:12].lower()
    freeze = {
        "schema_version": PHASE3_SCHEMA,
        "parent_freeze": {
            "training_data_freeze_id": parent["training_data_freeze_id"],
            "training_data_freeze_sha256": parent["training_data_freeze_sha256"],
            "registry": parent["registry"],
            "evaluation_exclusion_index": parent["evaluation_exclusion_index"],
            "license_policy_id": parent["license_policy_id"],
            "license_policy_sha256": parent["license_policy_sha256"],
        },
        "common_voice_release": {"id": release_identity, "sha256": release_sha},
        "common_voice_source_archive": {
            "id": source_identity,
            "sha256": str(release["archive_sha256"]).upper(),
            "bytes": int(release["archive_size_bytes"]),
            "logical_root": "JP_DATA_ROOT",
            "relative_path": paths.archive.relative_to(paths.data_root).as_posix(),
        },
        "common_voice_selected_members": {"id": selected_identity, "sha256": selected_sha},
        "common_voice_older_registry": {"id": registry_id, "sha256": registry_sha},
        "common_voice_split": {"id": split_id, "sha256": split_sha},
        "evaluation_content_hash_index": {
            "id": "evaluation_content_hash_index_" + evaluation_content_index["sha256"][:12].lower(),
            "sha256": evaluation_content_index["sha256"],
            "logical_path_count": evaluation_content_index["logical_path_count"],
            "total_bytes": evaluation_content_index["total_bytes"],
        },
        "evaluation_manifests": parent["evaluation_manifests"],
        "pool_previews": {name: value["preview_id"] for name, value in pool_previews.items()},
    }
    freeze_sha = _json_hash(freeze)
    freeze["training_data_freeze_id"] = "training_freeze_phase3_" + freeze_sha[:12].lower()
    freeze["training_data_freeze_sha256"] = freeze_sha

    leakage = {
        "exact_evaluation_collisions": int(registry["evaluation_exact_match"].sum()),
        "content_hash_collisions": int(registry["evaluation_content_hash_match"].sum()),
        "known_cross_dataset_collisions": int(registry["evaluation_cross_dataset_match"].sum()),
        "transcript_only_duplicates": int(registry["evaluation_transcript_only_match"].sum()),
        "items_excluded_for_leakage": int(
            registry[["evaluation_exact_match", "evaluation_group_match", "evaluation_cross_dataset_match", "evaluation_content_hash_match"]].any(axis=1).sum()
        ),
        "evaluation_content_hash_index": evaluation_content_index,
    }
    registry_summary = {
        "schema_version": "common-voice-older-summary.v1",
        "registry_id": registry_id,
        "registry_sha256": registry_sha,
        "candidate_records": int(len(registry)),
        "final_eligible_records": int(len(eligible)),
        "final_eligible_speakers": int(eligible["speaker_id"].nunique()),
        "final_eligible_hours": float(eligible["duration_seconds"].sum()) / 3600,
        "duplicate_audio_groups": len(duplicate_hashes),
        "leakage": leakage,
        "accent_filter_policy": "none",
        "accent_inventory": accents,
        "older_speakers_with_unspecified_accent": len(unspecified_accent_speakers),
        "older_speakers_with_multiple_accents": len(multiple_accent_speakers),
        "accent_categories_excluded": 0,
        "pool_previews": pool_previews,
        "phase2_dataset_stats": phase2_stats,
    }
    atomic_json(paths.registries / "common_voice_older_summary.json", registry_summary)
    atomic_json(paths.registries / "common_voice_older_split_summary.json", split_summary)
    atomic_json(paths.registries / "training_data_freeze_phase3.json", freeze)

    bucket_audit = metadata_summary["buckets"] | {
        "bucket_policy": "validated_only",
        "invalidated_audio_materialized": False,
        "other_audio_materialized": False,
    }
    age_audit = {
        "age_inventory": metadata_summary["age_inventory"],
        "selected_older_age_labels": metadata_summary["selected_older_age_labels"],
        "older_metadata_candidate_clips": metadata_summary["older_metadata_candidate_clips"],
        "older_metadata_candidate_speakers": metadata_summary["older_metadata_candidate_speakers"],
        "older_final_eligible_clips": int(len(eligible)),
        "older_final_eligible_speakers": int(eligible["speaker_id"].nunique()),
        "older_final_eligible_hours": float(eligible["duration_seconds"].sum()) / 3600,
    }
    accent_audit = {
        "accent_filter_policy": "none",
        "inventory": accents,
        "older_speakers_with_unspecified_accent": len(unspecified_accent_speakers),
        "older_speakers_with_multiple_accents": len(multiple_accent_speakers),
        "accent_categories_excluded": 0,
    }
    for filename, title, payload in (
        ("common_voice_bucket_audit", "Common Voice bucket audit", bucket_audit),
        ("common_voice_age_audit", "Common Voice age audit", age_audit),
        ("common_voice_accent_audit", "Common Voice accent audit", accent_audit),
        ("common_voice_split_audit", "Common Voice split audit", split_summary),
        ("common_voice_leakage_audit", "Common Voice leakage audit", leakage),
    ):
        atomic_json(paths.audits / f"{filename}.json", payload)
        atomic_text(paths.audits / f"{filename}.md", markdown_json(title, payload))
    license_record = {
        "schema_version": "common-voice-license-evidence.v1",
        "dataset_name": release["dataset_name"],
        "release_id": release["release_id"],
        "dataset_license_name": release["dataset_license_name"],
        "dataset_license_identifier": release["dataset_license_identifier"],
        "official_license_source": release["official_license_source"],
        "platform_consumer_terms": release["platform_consumer_terms"],
        "forbidden_usage": release["forbidden_usage"],
        "commercial_training_status": release["commercial_training_status"],
        "attribution_required": release["attribution_required_by_cc0"],
        "sharealike": release["sharealike"],
    }
    atomic_json(paths.license_evidence / "common_voice_26_english_license_record.json", license_record)
    return {
        "freeze": freeze,
        "registry_summary": registry_summary,
        "split_summary": split_summary,
        "registry_path": str(registry_path),
        "split_path": str(split_path),
        "freeze_path": str(paths.registries / "training_data_freeze_phase3.json"),
    }


def immutability_snapshot(
    paths: Phase3Paths,
    *,
    parent_freeze_path: Path,
    evaluation_exclusion_path: Path,
    tool_root: Path,
) -> dict[str, str]:
    parent = json.loads(parent_freeze_path.read_text(encoding="utf-8"))
    targets = {parent_freeze_path.resolve(), evaluation_exclusion_path.resolve()}
    targets.update((tool_root / item["canonical_path"]).resolve() for item in parent["evaluation_manifests"])
    edge_root = tool_root / "benchmarks" / "edge_research"
    if edge_root.is_dir():
        targets.update(path.resolve() for path in edge_root.rglob("*") if path.is_file())
    result: dict[str, str] = {}
    for target in sorted(targets, key=lambda value: str(value).casefold()):
        if target.is_relative_to(paths.training_root):
            logical = "JP_TRAINING_ROOT:" + target.relative_to(paths.training_root).as_posix()
        elif target.is_relative_to(tool_root):
            logical = "EVALUATION_TOOL:" + target.relative_to(tool_root).as_posix()
        else:
            logical = target.name
        result[logical] = sha256_file(target)
    return result


def run_phase3(
    *,
    data_root: Path,
    training_root: Path,
    tool_root: Path,
    parent_freeze_path: Path,
    evaluation_exclusion_path: Path,
    phase2_registry_path: Path,
) -> dict[str, Any]:
    release = load_release()
    archive = discover_archive(data_root, release)
    paths = Phase3Paths(data_root.resolve(), training_root.resolve(), archive.resolve(), release["release_id"])
    before = immutability_snapshot(
        paths,
        parent_freeze_path=parent_freeze_path,
        evaluation_exclusion_path=evaluation_exclusion_path,
        tool_root=tool_root,
    )
    source = source_audit(paths, release)
    metadata = build_metadata_state(paths, release)
    materialization = materialize_selected_audio(paths, release, metadata)
    result = build_registry_and_freeze(
        paths,
        release,
        metadata,
        materialization,
        parent_freeze_path=parent_freeze_path,
        evaluation_exclusion_path=evaluation_exclusion_path,
        phase2_registry_path=phase2_registry_path,
        tool_root=tool_root,
    )
    after = immutability_snapshot(
        paths,
        parent_freeze_path=parent_freeze_path,
        evaluation_exclusion_path=evaluation_exclusion_path,
        tool_root=tool_root,
    )
    audit = {
        "schema_version": "phase3-immutability-audit.v1",
        "files": [
            {
                "path": path,
                "sha_before": digest,
                "sha_after": after.get(path),
                "byte_identical": after.get(path) == digest,
            }
            for path, digest in before.items()
        ],
    }
    if not all(item["byte_identical"] for item in audit["files"]):
        raise Phase3Error("A protected Phase-2/evaluation artifact changed during Phase 3")
    atomic_json(paths.audits / "phase3_immutability_audit.json", audit)
    atomic_text(paths.audits / "phase3_immutability_audit.md", markdown_json("Phase-3 immutability audit", audit))
    return {
        "source_audit": source,
        "metadata_summary": metadata,
        "materialization": materialization,
        "phase3": result,
        "immutability": audit,
        "prepared_root": str(paths.prepared_root),
    }


def verify_phase3_freeze(
    freeze_path: Path,
    *,
    parent_freeze_path: Path,
    registry_path: Path,
    split_path: Path,
) -> dict[str, Any]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    canonical = {
        key: value for key, value in freeze.items()
        if key not in {"training_data_freeze_id", "training_data_freeze_sha256"}
    }
    reasons: list[str] = []
    if _json_hash(canonical) != freeze.get("training_data_freeze_sha256"):
        reasons.append("phase3 freeze self-hash mismatch")
    parent = json.loads(parent_freeze_path.read_text(encoding="utf-8"))
    if freeze.get("parent_freeze", {}).get("training_data_freeze_sha256") != parent.get("training_data_freeze_sha256"):
        reasons.append("parent freeze mismatch")
    registry = pd.read_parquet(registry_path)
    split = pd.read_parquet(split_path)
    if _frame_hash(registry, omit=("resolved_audio_path",)) != freeze["common_voice_older_registry"]["sha256"]:
        reasons.append("Common Voice registry hash mismatch")
    if _frame_hash(split) != freeze["common_voice_split"]["sha256"]:
        reasons.append("Common Voice split hash mismatch")
    overlaps = {}
    speakers = {
        role: set(split.loc[split["training_role"].eq(role), "speaker_id"].astype(str))
        for role in ("train", "dev", "heldout")
    }
    for left, right in (("train", "dev"), ("train", "heldout"), ("dev", "heldout")):
        overlaps[f"{left}_{right}"] = len(speakers[left] & speakers[right])
    if any(overlaps.values()):
        reasons.append("speaker split overlap")
    if bool(split.loc[split["training_role"].eq("heldout"), "strict_training_eligible"].any()):
        reasons.append("heldout lock violation")
    return {
        "valid": not reasons,
        "freeze_id": freeze.get("training_data_freeze_id"),
        "reasons": reasons,
        "speaker_overlaps": overlaps,
    }
