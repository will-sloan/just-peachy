"""Canonical Parquet benchmark representation and validation."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app.benchmark_contracts.canonical import (
    canonical_sha256,
    normalize_project_relative_path,
    stable_rank,
)
from app.benchmark_contracts.policy import augmentation_policy_for_record
from app.benchmark_contracts.versions import (
    HASH_ALGORITHM,
    MANIFEST_CANONICALIZATION_VERSION,
    MANIFEST_HASH_VERSION,
    MANIFEST_SCHEMA_VERSION,
    SELECTION_SEED,
)


class ManifestValidationError(ValueError):
    """Raised when a manifest violates the released v1 contract."""


_REQUIRED_STRING_FIELDS = (
    "manifest_schema_version",
    "manifest_version",
    "benchmark_tier",
    "panel",
    "dataset",
    "recording_id",
    "source_recording_id",
    "utt_id",
    "source_utterance_id",
    "audio_path_project_relative",
    "reference_text",
    "speaker_id",
    "role",
    "augmentation_policy",
    "selection_stratum",
    "selection_rank",
    "source_metadata_hash",
)


def _field(name: str, data_type: pa.DataType, *, nullable: bool = True) -> pa.Field:
    return pa.field(name, data_type, nullable=nullable)


MANIFEST_ARROW_SCHEMA = pa.schema(
    [
        *[_field(name, pa.string(), nullable=False) for name in _REQUIRED_STRING_FIELDS],
        _field("protocol_condition", pa.string()),
        _field("gender", pa.string()),
        _field("accent", pa.string()),
        _field("accent_group", pa.string()),
        _field("split", pa.string()),
        _field("subset_group", pa.string()),
        _field("audio_quality", pa.string()),
        _field("speaker_code", pa.string()),
        _field("speaker_variant_group", pa.string()),
        _field("reader_id", pa.string()),
        _field("chapter_id", pa.string()),
        _field("book_id", pa.string()),
        _field("meeting_id", pa.string()),
        _field("meeting_type", pa.string()),
        _field("visibility", pa.string()),
        _field("seen_type", pa.string()),
        _field("stream_type", pa.string()),
        _field("stream_id", pa.string()),
        _field("agent", pa.string()),
        _field("session_id", pa.string()),
        _field("speaker_id_ref", pa.string()),
        _field("recording_speaker_id_ref", pa.string()),
        _field("device_id", pa.string()),
        _field("channel_id", pa.string()),
        _field("microphone_id", pa.string()),
        _field("location", pa.string()),
        _field("room", pa.string()),
        _field("distractor", pa.string()),
        _field("mic", pa.string()),
        _field("position", pa.string()),
        _field("degrees", pa.string()),
        _field("query_name", pa.string()),
        _field("segment_id", pa.string()),
        _field("source_audio_path_project_relative", pa.string()),
        _field("start_sec", pa.float64(), nullable=False),
        _field("end_sec", pa.float64(), nullable=False),
        _field("duration_sec", pa.float64(), nullable=False),
        _field("word_count", pa.int64(), nullable=False),
        _field("selection_seed", pa.int64(), nullable=False),
        _field("notes", pa.string()),
    ],
    metadata={
        b"manifest_schema_version": MANIFEST_SCHEMA_VERSION.encode(),
        b"canonicalization_version": MANIFEST_CANONICALIZATION_VERSION.encode(),
        b"hash_version": MANIFEST_HASH_VERSION.encode(),
        b"hash_algorithm": HASH_ALGORITHM.encode(),
        b"selection_seed": str(SELECTION_SEED).encode(),
        b"authoritative_representation": b"parquet",
    },
)

ROW_FIELD_NAMES = tuple(field.name for field in MANIFEST_ARROW_SCHEMA)


def manifest_row(
    record: Mapping[str, object],
    *,
    tier: str,
    panel: str,
    dataset: str,
    role: str,
    selection_stratum: str,
    protocol_condition: str | None = None,
    source_utterance_id: str | None = None,
    notes: str | None = None,
) -> dict[str, object]:
    """Convert one existing-loader record into the frozen manifest superset."""

    recording_id = _required_record_text(record, "recording_id")
    source_recording_id = _optional_text(record.get("source_recording_id")) or recording_id
    utt_id = _required_record_text(record, "utt_id")
    reference_text = _required_record_text(record, "reference_text")
    audio_path = normalize_project_relative_path(
        _required_record_text(record, "audio_path_project_relative")
    )
    speaker_id = _speaker_id(record)
    start_sec, end_sec, duration_sec = _bounds(record)
    source_utt = source_utterance_id or utt_id
    policy_context = dict(record)
    policy_context.update({"panel": panel, "dataset": dataset})
    policy = augmentation_policy_for_record(panel, dataset, policy_context)
    source_identity = {
        "dataset": dataset,
        "recording_id": recording_id,
        "source_recording_id": source_recording_id,
        "utt_id": utt_id,
        "source_utterance_id": source_utt,
        "audio_path_project_relative": audio_path,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "reference_text": reference_text,
        "speaker_id": speaker_id,
    }
    row: dict[str, object] = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_version": MANIFEST_SCHEMA_VERSION,
        "benchmark_tier": tier,
        "panel": panel,
        "dataset": dataset,
        "recording_id": recording_id,
        "source_recording_id": source_recording_id,
        "utt_id": utt_id,
        "source_utterance_id": source_utt,
        "audio_path_project_relative": audio_path,
        "reference_text": reference_text,
        "speaker_id": speaker_id,
        "role": role,
        "augmentation_policy": policy,
        "selection_stratum": selection_stratum,
        "selection_rank": stable_rank(SELECTION_SEED, dataset, source_recording_id, utt_id),
        "source_metadata_hash": canonical_sha256(source_identity),
        "protocol_condition": protocol_condition,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": duration_sec,
        "word_count": len(reference_text.split()),
        "selection_seed": SELECTION_SEED,
        "notes": notes,
    }
    string_fields = (
        "gender",
        "accent",
        "accent_group",
        "split",
        "subset_group",
        "audio_quality",
        "speaker_code",
        "speaker_variant_group",
        "reader_id",
        "chapter_id",
        "book_id",
        "meeting_id",
        "meeting_type",
        "visibility",
        "seen_type",
        "stream_type",
        "stream_id",
        "agent",
        "session_id",
        "speaker_id_ref",
        "recording_speaker_id_ref",
        "device_id",
        "channel_id",
        "microphone_id",
        "location",
        "room",
        "distractor",
        "mic",
        "position",
        "degrees",
        "query_name",
        "segment_id",
    )
    for field in string_fields:
        row[field] = _optional_text(record.get(field))
    source_audio = _optional_text(record.get("source_audio_path_project_relative"))
    row["source_audio_path_project_relative"] = (
        normalize_project_relative_path(source_audio) if source_audio else None
    )
    return {name: row.get(name) for name in ROW_FIELD_NAMES}


def write_manifest(path: Path, rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Write deterministic uncompressed Parquet and return its immutable identity."""

    normalized = [dict(row) for row in rows]
    normalized.sort(key=_row_sort_key)
    validate_manifest_rows(normalized)
    table = pa.Table.from_pylist(normalized, schema=MANIFEST_ARROW_SCHEMA)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        path,
        version="2.6",
        data_page_version="2.0",
        compression="NONE",
        use_dictionary=False,
        write_statistics=True,
        row_group_size=65536,
        store_schema=True,
    )
    identity = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "canonicalization_version": MANIFEST_CANONICALIZATION_VERSION,
        "hash_version": MANIFEST_HASH_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
        "authoritative_representation": "parquet",
        "sha256": file_sha256(path),
        "bytes": path.stat().st_size,
        "rows": len(normalized),
    }
    identity["manifest_id"] = f"manifest_{str(identity['sha256'])[:12].lower()}"
    return identity


def read_manifest(path: Path) -> list[dict[str, object]]:
    """Read and validate one canonical Parquet manifest."""

    table = pq.read_table(path)
    validate_manifest_table(table)
    rows = table.to_pylist()
    validate_manifest_rows(rows)
    return rows


def validate_manifest_table(table: pa.Table) -> None:
    if not table.schema.remove_metadata().equals(MANIFEST_ARROW_SCHEMA.remove_metadata()):
        raise ManifestValidationError("manifest Parquet schema does not match benchmark-manifest.v1")
    metadata = table.schema.metadata or {}
    expected = MANIFEST_ARROW_SCHEMA.metadata or {}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ManifestValidationError(
                f"manifest metadata {key.decode()} does not match released contract"
            )


def validate_manifest_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    project_root: Path | None = None,
) -> None:
    materialized = list(rows)
    keys: set[tuple[object, ...]] = set()
    enrollment_sources: set[tuple[str, str, str, str]] = set()
    probe_sources: set[tuple[str, str, str, str]] = set()
    for index, row in enumerate(materialized):
        if row.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
            raise ManifestValidationError(f"row {index} has unsupported manifest schema")
        if row.get("manifest_version") != MANIFEST_SCHEMA_VERSION:
            raise ManifestValidationError(f"row {index} has unsupported manifest version")
        for field in _REQUIRED_STRING_FIELDS:
            if not _optional_text(row.get(field)):
                raise ManifestValidationError(f"row {index} missing required field {field}")
        tier = str(row["benchmark_tier"])
        panel = str(row["panel"])
        role = str(row["role"])
        protocol_condition = row.get("protocol_condition")
        if tier not in {"small", "standard", "large"}:
            raise ManifestValidationError(f"row {index} has invalid benchmark tier")
        if panel not in {"controlled_clean", "native_robustness", "speaker_protocol"}:
            raise ManifestValidationError(f"row {index} has invalid benchmark panel")
        if panel == "speaker_protocol":
            if role not in {"enrollment", "known_probe", "unknown_probe"}:
                raise ManifestValidationError(f"row {index} has invalid speaker role")
            if protocol_condition not in {"clean", "degraded"}:
                raise ManifestValidationError(
                    f"row {index} has invalid speaker protocol condition"
                )
            if role == "enrollment" and protocol_condition != "clean":
                raise ManifestValidationError(f"row {index} enrollment must be clean")
        elif role != "evaluation" or protocol_condition is not None:
            raise ManifestValidationError(
                f"row {index} non-speaker panel must use evaluation role and null protocol"
            )
        if row.get("selection_seed") != SELECTION_SEED:
            raise ManifestValidationError(f"row {index} uses inconsistent seed")
        portable = normalize_project_relative_path(str(row["audio_path_project_relative"]))
        if portable != row["audio_path_project_relative"]:
            raise ManifestValidationError(f"row {index} path is not canonical")
        if project_root is not None and not (project_root / portable).is_file():
            raise ManifestValidationError(f"row {index} audio path is missing: {portable}")
        source_audio = row.get("source_audio_path_project_relative")
        if source_audio is not None:
            source_portable = normalize_project_relative_path(str(source_audio))
            if source_portable != source_audio:
                raise ManifestValidationError(f"row {index} source audio path is not canonical")
        expected_rank = stable_rank(
            SELECTION_SEED,
            str(row["dataset"]),
            str(row["source_recording_id"]),
            str(row["utt_id"]),
        )
        if row.get("selection_rank") != expected_rank:
            raise ManifestValidationError(f"row {index} selection rank mismatch")
        if not _is_sha256(row.get("selection_rank")):
            raise ManifestValidationError(f"row {index} selection rank is not SHA-256")
        if not _is_sha256(row.get("source_metadata_hash")):
            raise ManifestValidationError(f"row {index} source metadata hash is not SHA-256")
        expected_source_hash = canonical_sha256(
            {
                "dataset": row["dataset"],
                "recording_id": row["recording_id"],
                "source_recording_id": row["source_recording_id"],
                "utt_id": row["utt_id"],
                "source_utterance_id": row["source_utterance_id"],
                "audio_path_project_relative": row["audio_path_project_relative"],
                "start_sec": row["start_sec"],
                "end_sec": row["end_sec"],
                "reference_text": row["reference_text"],
                "speaker_id": row["speaker_id"],
            }
        )
        if row.get("source_metadata_hash") != expected_source_hash:
            raise ManifestValidationError(f"row {index} source metadata hash mismatch")
        start_sec = float(row.get("start_sec") or 0.0)
        end_sec = float(row.get("end_sec") or 0.0)
        duration_sec = float(row.get("duration_sec") or 0.0)
        if start_sec < 0 or end_sec <= start_sec or duration_sec <= 0:
            raise ManifestValidationError(f"row {index} has non-positive duration")
        if not math.isclose(duration_sec, end_sec - start_sec, abs_tol=1e-6):
            raise ManifestValidationError(f"row {index} duration does not match bounds")
        if row.get("word_count") != len(str(row["reference_text"]).split()):
            raise ManifestValidationError(f"row {index} word count mismatch")
        expected_policy = augmentation_policy_for_record(
            str(row["panel"]), str(row["dataset"]), row
        )
        if row.get("augmentation_policy") != expected_policy:
            raise ManifestValidationError(f"row {index} augmentation policy mismatch")
        key = (
            row["benchmark_tier"],
            row["panel"],
            row["dataset"],
            row["recording_id"],
            row["utt_id"],
            row["role"],
            row.get("protocol_condition"),
        )
        if key in keys:
            raise ManifestValidationError(f"duplicate manifest key at row {index}: {key}")
        keys.add(key)
        source_key = (
            str(row["benchmark_tier"]),
            str(row["dataset"]),
            str(row["speaker_id"]),
            str(row["source_utterance_id"]),
        )
        role = str(row["role"])
        if role == "enrollment":
            enrollment_sources.add(source_key)
        elif role in {"known_probe", "unknown_probe"}:
            probe_sources.add(source_key)
    overlap = enrollment_sources & probe_sources
    if overlap:
        raise ManifestValidationError(
            f"enrollment/probe source utterances overlap: {sorted(overlap)[:3]}"
        )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rows_summary(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return {
            "realized_count": 0,
            "total_duration_sec": 0.0,
            "speaker_count": 0,
            "gender_distribution": {},
            "accent_distribution": {},
        }
    return {
        "realized_count": int(len(frame)),
        "total_duration_sec": round(float(frame["duration_sec"].sum()), 6),
        "speaker_count": int(frame["speaker_id"].replace("", pd.NA).dropna().nunique()),
        "gender_distribution": _distribution(frame, "gender"),
        "accent_distribution": _distribution(frame, "accent"),
    }


def _distribution(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame.columns:
        return {}
    values = frame[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return {str(key): int(value) for key, value in values.value_counts().sort_index().items()}


def _row_sort_key(row: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(
        "" if value is None else str(value)
        for value in (
            row.get("benchmark_tier"),
            row.get("panel"),
            row.get("dataset"),
            row.get("selection_stratum"),
            row.get("selection_rank"),
            row.get("recording_id"),
            row.get("utt_id"),
            row.get("role"),
            row.get("protocol_condition"),
        )
    )


def _speaker_id(record: Mapping[str, object]) -> str:
    for field in (
        "speaker_label",
        "speaker_id",
        "speaker_id_padded",
        "speaker_global_name",
        "speaker_id_ref",
        "reader_id",
        "speaker_code",
    ):
        value = _optional_text(record.get(field))
        if value:
            return value
    raise ManifestValidationError("selected row has no canonical speaker identity")


def _bounds(record: Mapping[str, object]) -> tuple[float, float, float]:
    start = _float_or_none(record.get("start_sec"))
    end = _float_or_none(record.get("end_sec"))
    if start is not None and end is not None and end > start:
        return start, end, end - start
    for field in (
        "duration_sec_audio",
        "duration_sec_manifest",
        "duration_sec",
        "distant_duration_sec",
        "source_duration_sec",
    ):
        duration = _float_or_none(record.get(field))
        if duration is not None and duration > 0:
            return 0.0, duration, duration
    raise ManifestValidationError("selected row has no positive time bounds")


def _required_record_text(record: Mapping[str, object], field: str) -> str:
    text = _optional_text(record.get(field))
    if text is None:
        raise ManifestValidationError(f"selected row missing {field}")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if pd.notna(numeric) else None


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789ABCDEF" for char in text)
