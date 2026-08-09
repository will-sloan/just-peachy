"""Typed artifact validation without adding a runtime schema dependency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Mapping

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from app.artifact_contracts.registry import (
    SCENARIO_TYPES,
    ArtifactDefinition,
)
from app.artifact_contracts.environment import (
    EnvironmentFingerprintError,
    validate_environment_fingerprint,
)
from app.benchmark_contracts.manifest_io import read_manifest
from app.benchmark_contracts.scenario import ScenarioValidationError, validate_scenario
from app.prediction_io.schema import UTTERANCE_REQUIRED_FIELDS, WORD_REQUIRED_FIELDS


class ArtifactSchemaError(ValueError):
    """Raised when an artifact is malformed or violates its declared schema."""


class IncompatibleArtifactError(ArtifactSchemaError):
    """Raised when an artifact declares an unsupported contract version."""


@dataclass(frozen=True)
class ArtifactInspection:
    """Validated artifact facts used by completeness reconciliation."""

    row_count: int | None = None
    values: Mapping[str, object] | None = None


PARQUET_REQUIRED_COLUMNS: Mapping[str, frozenset[str]] = {
    "item-metrics.v1": frozenset({"recording_id", "utt_id"}),
    "grouped-metrics.v1": frozenset(
        {"group_key", "group_value", "metric_name", "metric_value"}
    ),
    "failures.v1": frozenset({"recording_id", "utt_id", "error_type", "message"}),
    "embedding-index.v1": frozenset(
        {"embedding_id", "recording_id", "utt_id", "path", "dimensions", "model_id"}
    ),
    "speaker-similarity.v1": frozenset(
        {"probe_id", "candidate_speaker_id", "score", "decision"}
    ),
    "resource-usage.v1": frozenset({"elapsed_sec"}),
    "resource-usage.v2": frozenset(
        {
            "timestamp_utc", "monotonic_ns", "elapsed_sec", "campaign_id",
            "scenario_id", "attempt", "worker_id", "host", "root_pid",
            "process_tree_pids", "active_component", "process_cpu_percent",
            "system_cpu_percent", "process_rss_bytes", "process_vms_bytes",
            "system_ram_total_bytes", "system_ram_available_bytes",
            "system_ram_used_bytes", "system_ram_percent",
            "process_disk_read_bytes", "process_disk_write_bytes",
            "system_disk_read_bytes", "system_disk_write_bytes", "disk_free_bytes",
            "gpu_index", "gpu_uuid", "gpu_utilization_percent",
            "gpu_memory_utilization_percent", "gpu_vram_bytes",
            "gpu_peak_vram_bytes", "gpu_total_vram_bytes", "gpu_temperature_c",
            "gpu_power_w", "gpu_power_limit_w", "gpu_graphics_clock_mhz",
            "gpu_memory_clock_mhz", "gpu_throttling_reasons",
            "process_availability_reason", "gpu_availability_reason", "sampling_gap",
        }
    ),
}
PARQUET_REQUIRED_TYPES: Mapping[str, Mapping[str, str]] = {
    "item-metrics.v1": {"recording_id": "string", "utt_id": "string"},
    "grouped-metrics.v1": {
        "group_key": "string",
        "group_value": "string",
        "metric_name": "string",
        "metric_value": "float64",
    },
    "failures.v1": {
        "recording_id": "string",
        "utt_id": "string",
        "error_type": "string",
        "message": "string",
    },
    "embedding-index.v1": {
        "embedding_id": "string",
        "recording_id": "string",
        "utt_id": "string",
        "path": "string",
        "dimensions": "int64",
        "model_id": "string",
    },
    "speaker-similarity.v1": {
        "probe_id": "string",
        "candidate_speaker_id": "string",
        "score": "float64",
        "decision": "string",
    },
    "resource-usage.v1": {"elapsed_sec": "float64"},
    "resource-usage.v2": {
        "timestamp_utc": "string",
        "monotonic_ns": "int64",
        "elapsed_sec": "float64",
        "campaign_id": "string",
        "scenario_id": "string",
        "attempt": "int64",
        "worker_id": "string",
        "host": "string",
        "root_pid": "int64",
        "process_tree_pids": "string",
        "active_component": "string",
        "process_cpu_percent": "float64",
        "system_cpu_percent": "float64",
        "process_rss_bytes": "int64",
        "process_vms_bytes": "int64",
        "system_ram_total_bytes": "int64",
        "system_ram_available_bytes": "int64",
        "system_ram_used_bytes": "int64",
        "system_ram_percent": "float64",
        "process_disk_read_bytes": "int64",
        "process_disk_write_bytes": "int64",
        "system_disk_read_bytes": "int64",
        "system_disk_write_bytes": "int64",
        "disk_free_bytes": "int64",
        "gpu_index": "string",
        "gpu_uuid": "string",
        "gpu_utilization_percent": "float64",
        "gpu_memory_utilization_percent": "float64",
        "gpu_vram_bytes": "int64",
        "gpu_peak_vram_bytes": "int64",
        "gpu_total_vram_bytes": "int64",
        "gpu_temperature_c": "float64",
        "gpu_power_w": "float64",
        "gpu_power_limit_w": "float64",
        "gpu_graphics_clock_mhz": "float64",
        "gpu_memory_clock_mhz": "float64",
        "gpu_throttling_reasons": "string",
        "process_availability_reason": "string",
        "gpu_availability_reason": "string",
        "sampling_gap": "bool",
    },
}
_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|auth[_-]?token|access[_-]?key|password)"
    r"\s*[:=]\s*['\"]?[^\s'\"]{8,}"
)


def validate_artifact(
    path: Path,
    definition: ArtifactDefinition,
    *,
    scenario_id: str | None = None,
    scenario_hash: str | None = None,
) -> ArtifactInspection:
    """Validate one materialized artifact against its registry definition."""

    if not path.is_file():
        raise ArtifactSchemaError(f"artifact is not a file: {path}")
    if definition.format == "json":
        return _validate_json(path, definition, scenario_id, scenario_hash)
    if definition.format == "jsonl":
        return _validate_jsonl(path, definition, scenario_id)
    if definition.format == "yaml":
        return _validate_yaml(path, definition, scenario_id, scenario_hash)
    if definition.format == "parquet":
        return _validate_parquet(path, definition)
    if definition.format == "rttm":
        return _validate_rttm(path)
    if definition.format == "npz":
        return _validate_npz(path, definition)
    if definition.format == "text":
        text = _read_utf8(path)
        if "nonempty" in definition.validation_rules and not text.strip():
            raise ArtifactSchemaError(f"artifact must be nonempty: {path}")
        if "no_credentials" in definition.validation_rules:
            _reject_credentials(text, path)
        return ArtifactInspection()
    if definition.format == "sha256":
        text = _read_utf8(path).strip()
        if not _is_sha256(text):
            raise ArtifactSchemaError("detached checksum must be uppercase SHA-256")
        return ArtifactInspection(values={"sha256": text})
    if definition.format == "sqlite":
        return _validate_sqlite(path, definition)
    raise IncompatibleArtifactError(
        f"unsupported artifact format {definition.format!r}"
    )


def _validate_json(
    path: Path,
    definition: ArtifactDefinition,
    scenario_id: str | None,
    scenario_hash: str | None,
) -> ArtifactInspection:
    value = _json_mapping(path)
    expected_version = definition.schema_version
    if definition.artifact_id == "resolved_scenario":
        if value.get("schema_version") != expected_version:
            raise IncompatibleArtifactError("unsupported resolved scenario schema")
        try:
            validate_scenario(value)
        except ScenarioValidationError as exc:
            raise ArtifactSchemaError(str(exc)) from exc
    elif definition.artifact_id == "checksums":
        _require_schema(value, expected_version)
        _validate_checksums_mapping(
            value,
            scenario_id,
            expected_registry_version=definition.registry_version,
        )
    elif definition.artifact_id == "campaign_manifest":
        _require_schema(value, expected_version)
        _validate_campaign_manifest(
            value,
            expected_registry_version=definition.registry_version,
        )
    elif definition.artifact_id == "environment_fingerprint":
        _require_schema(value, expected_version)
        try:
            validate_environment_fingerprint(value)
        except EnvironmentFingerprintError as exc:
            raise ArtifactSchemaError(str(exc)) from exc
    else:
        _require_schema(value, expected_version)
        _validate_scenario_mapping(value, definition, scenario_id, scenario_hash)
        if definition.artifact_id == "resource_summary":
            _validate_resource_summary(value)
        elif definition.artifact_id == "resource_availability":
            _validate_resource_availability(value)
    if "no_credentials" in definition.validation_rules:
        _reject_credentials(json.dumps(value, ensure_ascii=False), path)
    return ArtifactInspection(values=value)


def _validate_yaml(
    path: Path,
    definition: ArtifactDefinition,
    scenario_id: str | None,
    scenario_hash: str | None,
) -> ArtifactInspection:
    try:
        value = yaml.safe_load(_read_utf8(path)) or {}
    except yaml.YAMLError as exc:
        raise ArtifactSchemaError(f"invalid YAML: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ArtifactSchemaError("YAML artifact must contain a mapping")
    mapped = dict(value)
    _require_schema(mapped, definition.schema_version)
    _validate_scenario_mapping(mapped, definition, scenario_id, scenario_hash)
    _reject_absolute_paths(mapped)
    if "no_credentials" in definition.validation_rules:
        _reject_credentials(yaml.safe_dump(mapped), path)
    return ArtifactInspection(values=mapped)


def _validate_jsonl(
    path: Path,
    definition: ArtifactDefinition,
    scenario_id: str | None,
) -> ArtifactInspection:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ArtifactSchemaError(
                    f"truncated or invalid JSONL at line {line_number}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise ArtifactSchemaError(f"JSONL line {line_number} is not an object")
            _validate_jsonl_row(value, definition, line_number, scenario_id)
            if "no_credentials" in definition.validation_rules:
                _reject_credentials(json.dumps(value, ensure_ascii=False), path)
            rows.append(value)
    if definition.artifact_id == "component_spans":
        try:
            from app.resource_telemetry.validation import validate_spans

            validate_spans(rows, scenario_id=scenario_id)
        except ValueError as exc:
            raise ArtifactSchemaError(str(exc)) from exc
    return ArtifactInspection(row_count=len(rows))


def _validate_jsonl_row(
    row: Mapping[str, object],
    definition: ArtifactDefinition,
    line_number: int,
    scenario_id: str | None,
) -> None:
    artifact_id = definition.artifact_id
    if artifact_id == "utterance_predictions":
        if set(row) != set(UTTERANCE_REQUIRED_FIELDS):
            raise ArtifactSchemaError(
                f"utterance line {line_number} must have exactly protected fields"
            )
        _validate_identity_bounds(row, line_number)
        if not isinstance(row.get("text"), str):
            raise ArtifactSchemaError(f"utterance line {line_number} text must be a string")
    elif artifact_id == "words":
        if set(row) != set(WORD_REQUIRED_FIELDS):
            raise ArtifactSchemaError(f"word line {line_number} has incorrect fields")
        _validate_identity_bounds(row, line_number)
        if not isinstance(row.get("word"), str):
            raise ArtifactSchemaError(f"word line {line_number} word must be a string")
    elif artifact_id in {"diagnostics", "diarization_diagnostics"}:
        _require_row_fields(row, ("recording_id", "utt_id"), line_number)
    elif artifact_id == "vad_regions":
        _require_row_fields(
            row, ("recording_id", "utt_id", "start_sec", "end_sec"), line_number
        )
        _validate_identity_bounds(row, line_number)
    elif artifact_id in {"events", "errors"}:
        required = ("schema_version", "scenario_id", "timestamp_utc")
        _require_row_fields(row, required, line_number)
        if row.get("schema_version") != definition.schema_version:
            raise IncompatibleArtifactError(
                f"unsupported {artifact_id} row schema at line {line_number}"
            )
        if scenario_id is not None and row.get("scenario_id") != scenario_id:
            raise ArtifactSchemaError(f"{artifact_id} line {line_number} scenario mismatch")
        _parse_rfc3339_utc(row.get("timestamp_utc"), f"{artifact_id} line {line_number}")
        if artifact_id == "events":
            _require_row_fields(row, ("event_type",), line_number)
        else:
            _require_row_fields(row, ("error_type", "message"), line_number)
    elif artifact_id == "component_spans":
        required = (
            "schema_version", "scenario_id", "span_id", "parent_span_id",
            "name", "phase", "start_timestamp_utc", "start_monotonic_ns",
            "end_monotonic_ns", "duration_ns", "status",
        )
        _require_row_fields(row, required, line_number)
        if row.get("schema_version") != definition.schema_version:
            raise IncompatibleArtifactError(
                f"unsupported component span schema at line {line_number}"
            )
        if scenario_id is not None and row.get("scenario_id") != scenario_id:
            raise ArtifactSchemaError(f"component span line {line_number} scenario mismatch")
        _parse_rfc3339_utc(
            row.get("start_timestamp_utc"), f"component span line {line_number}"
        )


def _validate_parquet(
    path: Path,
    definition: ArtifactDefinition,
) -> ArtifactInspection:
    if definition.schema_version == "benchmark-manifest.v1":
        rows = read_manifest(path)
        return ArtifactInspection(row_count=len(rows))
    try:
        table = pq.read_table(path)
    except Exception as exc:
        raise ArtifactSchemaError(f"truncated or unreadable Parquet: {exc}") from exc
    metadata = table.schema.metadata or {}
    observed = metadata.get(b"artifact_schema_version")
    if observed is None or observed.decode("utf-8", errors="replace") != definition.schema_version:
        raise IncompatibleArtifactError(
            f"Parquet artifact schema must be {definition.schema_version}"
        )
    required = PARQUET_REQUIRED_COLUMNS.get(definition.schema_version, frozenset())
    missing = required - set(table.column_names)
    if missing:
        raise ArtifactSchemaError(f"Parquet artifact missing columns: {sorted(missing)}")
    for column, expected_type in PARQUET_REQUIRED_TYPES.get(
        definition.schema_version, {}
    ).items():
        if not _arrow_type_matches(table.schema.field(column).type, expected_type):
            raise ArtifactSchemaError(
                f"Parquet column {column} must have type {expected_type}"
            )
    if definition.artifact_id == "embedding_index" and "path" in table.column_names:
        for value in table.column("path").to_pylist():
            if not _is_portable_relative_string(value):
                raise ArtifactSchemaError("embedding index contains a nonportable path")
    if definition.artifact_id == "resource_usage" and table.num_rows > 1:
        elapsed = [float(value) for value in table.column("elapsed_sec").to_pylist()]
        if elapsed != sorted(elapsed):
            raise ArtifactSchemaError("resource sample times must be monotonic")
        if "monotonic_ns" in table.column_names:
            monotonic = [int(value) for value in table.column("monotonic_ns").to_pylist()]
            if monotonic != sorted(monotonic):
                raise ArtifactSchemaError("resource monotonic timestamps must be ordered")
    if "no_credentials" in definition.validation_rules:
        for field in table.schema:
            if pa.types.is_string(field.type):
                for value in table.column(field.name).to_pylist():
                    if value is not None:
                        _reject_credentials(str(value), path)
    return ArtifactInspection(row_count=table.num_rows)


def _validate_rttm(path: Path) -> ArtifactInspection:
    count = 0
    for line_number, line in enumerate(_read_utf8(path).splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 9 or parts[0].upper() != "SPEAKER":
            raise ArtifactSchemaError(f"invalid RTTM line {line_number}")
        try:
            start_sec = float(parts[3])
            duration_sec = float(parts[4])
        except ValueError as exc:
            raise ArtifactSchemaError(f"invalid RTTM time at line {line_number}") from exc
        if not math.isfinite(start_sec) or not math.isfinite(duration_sec):
            raise ArtifactSchemaError(f"non-finite RTTM time at line {line_number}")
        if start_sec < 0 or duration_sec < 0:
            raise ArtifactSchemaError(f"negative RTTM segment at line {line_number}")
        count += 1
    return ArtifactInspection(row_count=count)


def _validate_npz(path: Path, definition: ArtifactDefinition) -> ArtifactInspection:
    try:
        with np.load(path, allow_pickle=False) as archive:
            if "schema_version" not in archive or "embedding" not in archive:
                raise ArtifactSchemaError("embedding NPZ requires schema_version and embedding")
            schema_value = np.asarray(archive["schema_version"]).reshape(-1)
            if len(schema_value) != 1 or str(schema_value[0]) != definition.schema_version:
                raise IncompatibleArtifactError("unsupported embedding NPZ schema")
            embedding = np.asarray(archive["embedding"])
            if embedding.ndim != 1 or embedding.size == 0:
                raise ArtifactSchemaError("embedding must be a nonempty 1-D array")
            if not np.issubdtype(embedding.dtype, np.number) or not np.isfinite(embedding).all():
                raise ArtifactSchemaError("embedding must contain finite numeric values")
    except (ArtifactSchemaError, IncompatibleArtifactError):
        raise
    except Exception as exc:
        raise ArtifactSchemaError(f"truncated or unsafe NPZ: {exc}") from exc
    return ArtifactInspection(row_count=1)


def _validate_sqlite(path: Path, definition: ArtifactDefinition) -> ArtifactInspection:
    if path.read_bytes()[:16] != b"SQLite format 3\x00":
        raise ArtifactSchemaError("invalid SQLite header")
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "SELECT version FROM artifact_schema_version LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise ArtifactSchemaError(f"invalid campaign database: {exc}") from exc
    if row is None or row[0] != definition.schema_version:
        raise IncompatibleArtifactError("unsupported campaign database schema")
    return ArtifactInspection()


def _validate_scenario_mapping(
    value: Mapping[str, object],
    definition: ArtifactDefinition,
    scenario_id: str | None,
    scenario_hash: str | None,
) -> None:
    if definition.artifact_id in {
        "run_config",
        "scenario_status",
        "metrics_summary",
        "scenario_report_json",
    }:
        if not re.fullmatch(
            r"scenario_[0-9a-f]{12}", str(value.get("scenario_id") or "")
        ):
            raise ArtifactSchemaError(f"{definition.artifact_id} has invalid scenario ID")
        if not _is_sha256(value.get("scenario_hash")):
            raise ArtifactSchemaError(f"{definition.artifact_id} has invalid scenario hash")
    if scenario_id is not None and value.get("scenario_id") != scenario_id:
        raise ArtifactSchemaError(f"{definition.artifact_id} scenario ID mismatch")
    if (
        scenario_hash is not None
        and "scenario_hash" in value
        and value.get("scenario_hash") != scenario_hash
    ):
        raise ArtifactSchemaError(f"{definition.artifact_id} scenario hash mismatch")
    if "counts" in value:
        counts = value.get("counts")
        if not isinstance(counts, Mapping):
            raise ArtifactSchemaError(f"{definition.artifact_id} counts must be a mapping")
        _validate_nonnegative_counts(counts)
    if definition.artifact_id == "scenario_status":
        required = {
            "artifact_registry_version",
            "scenario_hash",
            "scenario_type",
            "state",
            "counts",
        }
        missing = required - set(value)
        if missing:
            raise ArtifactSchemaError(f"scenario status missing fields: {sorted(missing)}")
        if value.get("state") not in {
            "pending",
            "running",
            "successful",
            "failed",
            "stopped",
        }:
            raise ArtifactSchemaError("invalid scenario status state")
        if value.get("scenario_type") not in SCENARIO_TYPES:
            raise IncompatibleArtifactError("unsupported scenario status type")
        if value.get("artifact_registry_version") != definition.registry_version:
            raise IncompatibleArtifactError("unsupported status artifact registry")
    if definition.artifact_id == "run_config":
        required = {"artifact_registry_version", "scenario_hash", "settings"}
        missing = required - set(value)
        if missing:
            raise ArtifactSchemaError(f"run config missing fields: {sorted(missing)}")
        if not isinstance(value.get("settings"), Mapping):
            raise ArtifactSchemaError("run config settings must be a mapping")
        if value.get("artifact_registry_version") != definition.registry_version:
            raise IncompatibleArtifactError("unsupported run config artifact registry")
    if definition.artifact_id == "metrics_summary":
        required = {"scenario_hash", "counts", "metrics"}
        missing = required - set(value)
        if missing:
            raise ArtifactSchemaError(f"metrics summary missing fields: {sorted(missing)}")
        if not isinstance(value.get("metrics"), Mapping):
            raise ArtifactSchemaError("metrics summary metrics must be a mapping")
    if definition.artifact_id == "scenario_report_json":
        required = {"scenario_hash", "counts", "metrics", "completion_state"}
        missing = required - set(value)
        if missing:
            raise ArtifactSchemaError(f"scenario report missing fields: {sorted(missing)}")
        if value.get("completion_state") not in {
            "complete",
            "incomplete",
            "corrupt",
            "incompatible",
        }:
            raise ArtifactSchemaError("invalid scenario report completion state")


def _validate_campaign_manifest(
    value: Mapping[str, object],
    *,
    expected_registry_version: str,
) -> None:
    required = {
        "campaign_id",
        "artifact_registry_version",
        "scenario_schema_version",
        "benchmark_manifests",
        "scenario_ids",
        "created_at_utc",
    }
    missing = required - set(value)
    if missing:
        raise ArtifactSchemaError(f"campaign manifest missing fields: {sorted(missing)}")
    if value.get("artifact_registry_version") != expected_registry_version:
        raise IncompatibleArtifactError("unsupported campaign artifact registry")
    if value.get("scenario_schema_version") != "scenario-definition.v1":
        raise IncompatibleArtifactError("unsupported campaign scenario schema")
    if not re.fullmatch(
        r"campaign_[a-z0-9][a-z0-9_-]{2,31}", str(value.get("campaign_id") or "")
    ):
        raise ArtifactSchemaError("invalid campaign ID")
    scenario_ids = value.get("scenario_ids")
    manifests = value.get("benchmark_manifests")
    if not isinstance(scenario_ids, list) or any(not isinstance(item, str) for item in scenario_ids):
        raise ArtifactSchemaError("campaign scenario_ids must be a string list")
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ArtifactSchemaError("campaign scenario IDs must be unique")
    if any(not re.fullmatch(r"scenario_[0-9a-f]{12}", item) for item in scenario_ids):
        raise ArtifactSchemaError("campaign contains an invalid scenario ID")
    if not isinstance(manifests, list) or any(not isinstance(item, Mapping) for item in manifests):
        raise ArtifactSchemaError("benchmark_manifests must be a mapping list")
    for item in manifests:
        if not {"manifest_id", "path", "sha256"}.issubset(item):
            raise ArtifactSchemaError("campaign benchmark identity is incomplete")
        if not _is_portable_relative_string(item.get("path")):
            raise ArtifactSchemaError("campaign benchmark path must be portable and relative")
        if not _is_sha256(item.get("sha256")):
            raise ArtifactSchemaError("campaign benchmark hash is invalid")
        if not str(item.get("path")).startswith("benchmark_manifests/"):
            raise ArtifactSchemaError("campaign benchmark must be under benchmark_manifests")
        expected_manifest_id = f"manifest_{str(item['sha256'])[:12].lower()}"
        if item.get("manifest_id") != expected_manifest_id:
            raise ArtifactSchemaError("campaign benchmark ID/hash mismatch")
    _parse_rfc3339_utc(value.get("created_at_utc"), "campaign created_at_utc")


def _validate_checksums_mapping(
    value: Mapping[str, object],
    scenario_id: str | None,
    *,
    expected_registry_version: str,
) -> None:
    if not re.fullmatch(
        r"scenario_[0-9a-f]{12}", str(value.get("scenario_id") or "")
    ):
        raise ArtifactSchemaError("checksum manifest has invalid scenario ID")
    if scenario_id is not None and value.get("scenario_id") != scenario_id:
        raise ArtifactSchemaError("checksum manifest scenario ID mismatch")
    if value.get("hash_algorithm") != "sha256":
        raise IncompatibleArtifactError("unsupported checksum algorithm")
    if value.get("artifact_registry_version") != expected_registry_version:
        raise IncompatibleArtifactError("unsupported checksum artifact registry")
    _parse_rfc3339_utc(value.get("updated_at_utc"), "checksum updated_at_utc")
    entries = value.get("entries")
    if not isinstance(entries, Mapping):
        raise ArtifactSchemaError("checksum entries must be a mapping")
    for relative_path, raw in entries.items():
        if not _is_portable_relative_string(relative_path) or not isinstance(raw, Mapping):
            raise ArtifactSchemaError("invalid checksum entry")
        if not _is_sha256(raw.get("sha256")):
            raise ArtifactSchemaError(f"invalid checksum for {relative_path}")
        byte_count = raw.get("bytes")
        if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
            raise ArtifactSchemaError(f"invalid byte count for {relative_path}")


def _validate_resource_summary(value: Mapping[str, object]) -> None:
    required = {
        "scenario_hash", "campaign_id", "attempt", "worker_id", "host",
        "sampling_interval_sec", "sample_count", "span_count", "resources",
        "components", "phases", "availability", "warnings",
    }
    missing = required - set(value)
    if missing:
        raise ArtifactSchemaError(f"resource summary missing fields: {sorted(missing)}")
    if not _is_sha256(value.get("scenario_hash")):
        raise ArtifactSchemaError("resource summary has invalid scenario hash")
    for field in ("sample_count", "span_count"):
        item = value.get(field)
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ArtifactSchemaError(f"resource summary {field} must be nonnegative")
    if not isinstance(value.get("warnings"), list):
        raise ArtifactSchemaError("resource summary warnings must be a list")


def _validate_resource_availability(value: Mapping[str, object]) -> None:
    if not _is_sha256(value.get("scenario_hash")):
        raise ArtifactSchemaError("resource availability has invalid scenario hash")
    fields = value.get("fields")
    if not isinstance(fields, Mapping):
        raise ArtifactSchemaError("resource availability fields must be a mapping")
    for field, raw in fields.items():
        if not isinstance(field, str) or not isinstance(raw, Mapping):
            raise ArtifactSchemaError("invalid resource availability entry")
        if not isinstance(raw.get("available"), bool):
            raise ArtifactSchemaError(f"availability for {field} requires a boolean")
        if raw.get("available") is False and not raw.get("reason"):
            raise ArtifactSchemaError(f"unavailable resource field {field} requires a reason")


def _validate_identity_bounds(row: Mapping[str, object], line_number: int) -> None:
    _require_row_fields(row, ("recording_id", "utt_id", "start_sec", "end_sec"), line_number)
    start = row.get("start_sec")
    end = row.get("end_sec")
    if start is None and end is None:
        return
    start_number = _finite_float(start)
    end_number = _finite_float(end)
    if start_number is None or end_number is None or end_number < start_number:
        raise ArtifactSchemaError(f"invalid bounds at line {line_number}")


def _require_row_fields(
    row: Mapping[str, object], fields: tuple[str, ...], line_number: int
) -> None:
    missing = [field for field in fields if field not in row]
    if missing:
        raise ArtifactSchemaError(f"line {line_number} missing fields: {missing}")
    for field in fields:
        if field in {"recording_id", "utt_id", "scenario_id"} and not isinstance(
            row.get(field), str
        ):
            raise ArtifactSchemaError(f"line {line_number} {field} must be a string")


def _validate_nonnegative_counts(counts: Mapping[str, object]) -> None:
    for name, value in counts.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ArtifactSchemaError(f"count {name} must be a nonnegative integer")


def _json_mapping(path: Path) -> dict[str, object]:
    try:
        value = json.loads(_read_utf8(path))
    except json.JSONDecodeError as exc:
        raise ArtifactSchemaError(f"truncated or invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactSchemaError("JSON artifact must contain a mapping")
    return value


def _require_schema(value: Mapping[str, object], expected: str) -> None:
    if value.get("schema_version") != expected:
        raise IncompatibleArtifactError(
            f"artifact schema must be {expected}, got {value.get('schema_version')!r}"
        )


def _reject_absolute_paths(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).endswith(("_path", "_dir", "_root")) and isinstance(item, str):
                if not _is_portable_relative_string(item):
                    raise ArtifactSchemaError(f"nonportable path in field {key}")
            else:
                _reject_absolute_paths(item)
    elif isinstance(value, list):
        for item in value:
            _reject_absolute_paths(item)


def _is_portable_relative_string(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactSchemaError(f"artifact is not UTF-8: {path}") from exc


def _reject_credentials(text: str, path: Path) -> None:
    if _SECRET_PATTERN.search(text):
        raise ArtifactSchemaError(f"possible credential value in {path}")


def _parse_rfc3339_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ArtifactSchemaError(f"{field} must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ArtifactSchemaError(f"{field} must be RFC3339 UTC") from exc


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(character in "0123456789ABCDEF" for character in text)


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _finite_float(value: object) -> float | None:
    if not _finite_number(value):
        return None
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return float(value)


def _arrow_type_matches(value: pa.DataType, expected: str) -> bool:
    return {
        "string": pa.types.is_string,
        "float64": pa.types.is_float64,
        "int64": pa.types.is_int64,
        "bool": pa.types.is_boolean,
    }[expected](value)
