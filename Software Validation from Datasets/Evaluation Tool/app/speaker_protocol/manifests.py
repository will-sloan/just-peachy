"""Deterministic, privacy-safe Stage 10 speaker manifest derivation."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time
from typing import Iterable, Mapping

import pyarrow as pa
import pyarrow.parquet as pq

from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.manifest_io import file_sha256, read_manifest
from app.speaker_protocol.contracts import (
    MANIFEST_SCHEMA_VERSION,
    TOOL_ROOT,
    SpeakerProtocolError,
    load_policy,
    privacy_safe_item_id,
    privacy_safe_speaker_id,
)


PROTOCOL_MANIFEST_INDEX_VERSION = "speaker-protocol-manifest-index.v1"
PROTOCOL_CANONICALIZATION_VERSION = "speaker-protocol-canonicalization.v1"
MANIFEST_FILENAMES = {
    "enrollment": "enrollment.parquet",
    "calibration": "calibration.parquet",
    "known_evaluation": "known_evaluation.parquet",
    "unknown_evaluation": "unknown_evaluation.parquet",
    "clean_probes": "clean_probes.parquet",
    "degraded_probes": "degraded_probes.parquet",
}


def _field(name: str, data_type: pa.DataType, *, nullable: bool = False) -> pa.Field:
    return pa.field(name, data_type, nullable=nullable)


PROTOCOL_ARROW_SCHEMA = pa.schema(
    [
        _field("schema_version", pa.string()),
        _field("protocol_id", pa.string()),
        _field("source_manifest_sha256", pa.string()),
        _field("benchmark_tier", pa.string()),
        _field("manifest_kind", pa.string()),
        _field("protocol_split", pa.string()),
        _field("trial_role", pa.string()),
        _field("protocol_condition", pa.string()),
        _field("dataset", pa.string()),
        _field("item_id", pa.string()),
        _field("speaker_key", pa.string()),
        _field("source_recording_id", pa.string()),
        _field("source_utterance_id", pa.string()),
        _field("audio_path_project_relative", pa.string()),
        _field("augmentation_policy", pa.string()),
        _field("selection_rank", pa.string()),
        _field("enrolled_speaker", pa.bool_()),
        _field("known_speaker", pa.bool_()),
        _field("start_sec", pa.float64()),
        _field("end_sec", pa.float64()),
        _field("duration_sec", pa.float64()),
        _field("gender", pa.string(), nullable=True),
        _field("accent_group", pa.string(), nullable=True),
    ],
    metadata={
        b"manifest_schema_version": MANIFEST_SCHEMA_VERSION.encode(),
        b"canonicalization_version": PROTOCOL_CANONICALIZATION_VERSION.encode(),
        b"hash_algorithm": b"sha256",
        b"authoritative_representation": b"parquet",
        b"privacy_identity": b"pseudonymous-speaker-keys",
        b"selection_seed": b"3800",
    },
)


def build_protocol_manifests(
    output_root: Path,
    *,
    tier: str = "small",
    policy_path: Path | None = None,
) -> dict[str, object]:
    """Derive Stage 10 manifests without modifying the frozen Stage 2 source."""

    if tier not in {"small", "standard", "large"}:
        raise SpeakerProtocolError(f"unsupported speaker protocol tier {tier!r}")
    policy_source = (policy_path or (TOOL_ROOT / "configs/automated_evaluation/speaker_protocol.v1.yaml")).resolve()
    policy = load_policy(policy_source)
    source_path = (TOOL_ROOT / str(policy["source_manifest"])).resolve()
    source_hash = file_sha256(source_path).upper()
    policy_hash = file_sha256(policy_source).upper()
    protocol_payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "canonicalization_version": PROTOCOL_CANONICALIZATION_VERSION,
        "source_manifest_sha256": source_hash,
        "policy_sha256": policy_hash,
        "benchmark_tier": tier,
        "seed": 3800,
    }
    protocol_id = f"speaker_protocol_{canonical_sha256(protocol_payload)[:12].lower()}"
    source_rows = [
        dict(row)
        for row in read_manifest(source_path)
        if row["panel"] == "speaker_protocol" and row["benchmark_tier"] == tier
    ]
    if not source_rows:
        raise SpeakerProtocolError(f"source speaker manifest has no {tier} rows")

    core = _partition_rows(source_rows, protocol_id, source_hash, policy)
    views = {
        "enrollment": core["enrollment"],
        "calibration": core["calibration"],
        "known_evaluation": core["known_evaluation"],
        "unknown_evaluation": core["unknown_evaluation"],
    }
    probes = [row for kind, rows in views.items() if kind != "enrollment" for row in rows]
    views["clean_probes"] = [
        {**row, "manifest_kind": "clean_probes"}
        for row in probes
        if row["protocol_condition"] == "clean"
    ]
    views["degraded_probes"] = [
        {**row, "manifest_kind": "degraded_probes"}
        for row in probes
        if row["protocol_condition"] == "degraded"
    ]

    destination = output_root.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, object]] = {}
    for kind, filename in MANIFEST_FILENAMES.items():
        rows = sorted(views[kind], key=_row_sort_key)
        path = destination / filename
        _write_parquet_atomic(path, rows)
        validate_protocol_table(pq.read_table(path), expected_kind=kind)
        artifacts[kind] = {
            "path": filename,
            "rows": len(rows),
            "sha256": file_sha256(path).upper(),
            "bytes": path.stat().st_size,
        }

    validate_protocol_manifest_set(destination)
    leakage = leakage_report(core)
    if not all(bool(value) for value in leakage.values()):
        raise SpeakerProtocolError(f"speaker protocol leakage validation failed: {leakage}")
    index: dict[str, object] = {
        "schema_version": PROTOCOL_MANIFEST_INDEX_VERSION,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "canonicalization_version": PROTOCOL_CANONICALIZATION_VERSION,
        "hash_algorithm": "sha256",
        "authoritative_representation": "parquet",
        "protocol_id": protocol_id,
        "benchmark_tier": tier,
        "selection_seed": 3800,
        "source_manifest": {
            "path": str(policy["source_manifest"]),
            "sha256": source_hash,
            "schema_version": "benchmark-manifest.v1",
        },
        "policy": {
            "path": policy_source.relative_to(TOOL_ROOT).as_posix(),
            "sha256": policy_hash,
            "schema_version": policy["schema_version"],
        },
        "artifacts": artifacts,
        "leakage_validation": leakage,
        "privacy": {
            "speaker_ids": "deterministic pseudonyms",
            "private_real_name_mapping_included": False,
            "authorized_demographic_fields": policy["privacy"][
                "authorized_demographic_fields"
            ],
        },
    }
    index_path = destination / "speaker_protocol_manifest.json"
    _write_json_atomic(index_path, index)
    _write_text_atomic(
        destination / "speaker_protocol_manifest.sha256",
        file_sha256(index_path).lower() + "  speaker_protocol_manifest.json\n",
    )
    return index


def read_protocol_rows(path: Path, *, expected_kind: str | None = None) -> list[dict[str, object]]:
    table = pq.read_table(path)
    validate_protocol_table(table, expected_kind=expected_kind)
    return [dict(row) for row in table.to_pylist()]


def validate_protocol_table(table: pa.Table, *, expected_kind: str | None = None) -> None:
    if not table.schema.remove_metadata().equals(PROTOCOL_ARROW_SCHEMA.remove_metadata()):
        raise SpeakerProtocolError("speaker protocol Parquet schema mismatch")
    metadata = table.schema.metadata or {}
    for key, expected in (PROTOCOL_ARROW_SCHEMA.metadata or {}).items():
        if metadata.get(key) != expected:
            raise SpeakerProtocolError(f"speaker protocol metadata mismatch: {key.decode()}")
    rows = table.to_pylist()
    keys: set[str] = set()
    for index, row in enumerate(rows):
        if row["schema_version"] != MANIFEST_SCHEMA_VERSION:
            raise SpeakerProtocolError(f"row {index} has unsupported manifest version")
        if row["benchmark_tier"] not in {"small", "standard", "large"}:
            raise SpeakerProtocolError(f"row {index} has invalid tier")
        if row["protocol_split"] not in {"enrollment", "calibration", "evaluation"}:
            raise SpeakerProtocolError(f"row {index} has invalid protocol split")
        if row["trial_role"] not in {"enrollment", "known_probe", "unknown_probe"}:
            raise SpeakerProtocolError(f"row {index} has invalid trial role")
        if row["protocol_condition"] not in {"clean", "degraded"}:
            raise SpeakerProtocolError(f"row {index} has invalid condition")
        if row["trial_role"] == "enrollment" and row["protocol_condition"] != "clean":
            raise SpeakerProtocolError("enrollment must remain clean")
        if not str(row["speaker_key"]).startswith("spk_"):
            raise SpeakerProtocolError("speaker identities must be privacy-safe keys")
        if not str(row["item_id"]).startswith("item_"):
            raise SpeakerProtocolError("item identities must be privacy-safe keys")
        if not _is_sha256(str(row["source_manifest_sha256"])):
            raise SpeakerProtocolError("source manifest identity must be SHA-256")
        if expected_kind is not None and row["manifest_kind"] != expected_kind:
            raise SpeakerProtocolError(f"row {index} is not part of {expected_kind}")
        if float(row["end_sec"]) <= float(row["start_sec"]):
            raise SpeakerProtocolError("speaker protocol bounds must be positive")
        if not math.isclose(
            float(row["duration_sec"]),
            float(row["end_sec"]) - float(row["start_sec"]),
            abs_tol=1e-6,
        ):
            raise SpeakerProtocolError("speaker protocol duration does not match bounds")
        if row["item_id"] in keys:
            raise SpeakerProtocolError(f"duplicate item ID in manifest: {row['item_id']}")
        keys.add(str(row["item_id"]))


def validate_protocol_manifest_set(root: Path) -> dict[str, object]:
    rows_by_kind = {
        kind: read_protocol_rows(root / filename, expected_kind=kind)
        for kind, filename in MANIFEST_FILENAMES.items()
    }
    core = {key: rows_by_kind[key] for key in rows_by_kind if key not in {"clean_probes", "degraded_probes"}}
    leakage = leakage_report(core)
    if not all(bool(value) for value in leakage.values()):
        raise SpeakerProtocolError(f"manifest-set leakage detected: {leakage}")
    probe_rows = [
        row for kind, rows in core.items() if kind != "enrollment" for row in rows
    ]
    expected_clean = {str(row["item_id"]) for row in probe_rows if row["protocol_condition"] == "clean"}
    expected_degraded = {
        str(row["item_id"]) for row in probe_rows if row["protocol_condition"] == "degraded"
    }
    observed_clean = {str(row["item_id"]) for row in rows_by_kind["clean_probes"]}
    observed_degraded = {str(row["item_id"]) for row in rows_by_kind["degraded_probes"]}
    if expected_clean != observed_clean or expected_degraded != observed_degraded:
        raise SpeakerProtocolError("clean/degraded probe views do not reconcile with split manifests")
    return {
        "valid": True,
        "core_rows": sum(len(rows) for rows in core.values()),
        "clean_probe_rows": len(observed_clean),
        "degraded_probe_rows": len(observed_degraded),
        **leakage,
    }


def leakage_report(core: Mapping[str, Iterable[Mapping[str, object]]]) -> dict[str, bool]:
    enrollment = list(core.get("enrollment", []))
    calibration = list(core.get("calibration", []))
    known_eval = list(core.get("known_evaluation", []))
    unknown_eval = list(core.get("unknown_evaluation", []))
    evaluation = known_eval + unknown_eval
    enrollment_sources = {_source_key(row) for row in enrollment}
    calibration_sources = {_source_key(row) for row in calibration}
    evaluation_sources = {_source_key(row) for row in evaluation}
    enrolled_speakers = {str(row["speaker_key"]) for row in enrollment}
    unknown_speakers = {
        str(row["speaker_key"])
        for row in calibration + unknown_eval
        if row["trial_role"] == "unknown_probe"
    }
    calibration_unknown = {
        str(row["speaker_key"])
        for row in calibration
        if row["trial_role"] == "unknown_probe"
    }
    evaluation_unknown = {str(row["speaker_key"]) for row in unknown_eval}
    source_splits: dict[tuple[str, str, str], set[str]] = {}
    for row in calibration + evaluation:
        source_splits.setdefault(_source_key(row), set()).add(str(row["protocol_split"]))
    return {
        "enrollment_probe_source_disjoint": not bool(
            enrollment_sources & (calibration_sources | evaluation_sources)
        ),
        "calibration_evaluation_source_disjoint": not bool(
            calibration_sources & evaluation_sources
        ),
        "unknown_speakers_not_enrolled": not bool(unknown_speakers & enrolled_speakers),
        "calibration_evaluation_unknown_speakers_disjoint": not bool(
            calibration_unknown & evaluation_unknown
        ),
        "clean_degraded_variants_stay_in_one_split": all(
            len(splits) == 1 for splits in source_splits.values()
        ),
        "private_identity_mapping_absent": True,
    }


def _partition_rows(
    source_rows: list[dict[str, object]],
    protocol_id: str,
    source_hash: str,
    policy: Mapping[str, object],
) -> dict[str, list[dict[str, object]]]:
    selection = policy["selection"]
    known_fraction = float(selection["calibration_source_fraction_per_known_speaker"])
    unknown_fraction = float(selection["calibration_unknown_speaker_fraction"])
    source_speakers = sorted({str(row["speaker_id"]) for row in source_rows})
    speaker_keys = {
        speaker: privacy_safe_speaker_id(speaker, protocol_id) for speaker in source_speakers
    }
    enrollment_source = [row for row in source_rows if row["role"] == "enrollment"]
    known_source = [row for row in source_rows if row["role"] == "known_probe"]
    unknown_source = [row for row in source_rows if row["role"] == "unknown_probe"]

    result: dict[str, list[dict[str, object]]] = {
        "enrollment": [],
        "calibration": [],
        "known_evaluation": [],
        "unknown_evaluation": [],
    }
    result["enrollment"] = [
        _protocol_row(
            row,
            protocol_id,
            source_hash,
            speaker_keys[str(row["speaker_id"])],
            manifest_kind="enrollment",
            protocol_split="enrollment",
        )
        for row in enrollment_source
    ]

    known_by_speaker = _group_source_variants(known_source)
    for speaker, sources in sorted(known_by_speaker.items()):
        ordered = sorted(sources.items(), key=lambda value: _split_rank(protocol_id, speaker, value[0]))
        calibration_count = _partition_count(len(ordered), known_fraction)
        calibration_ids = {source_id for source_id, _ in ordered[:calibration_count]}
        for source_id, variants in ordered:
            split = "calibration" if source_id in calibration_ids else "evaluation"
            kind = "calibration" if split == "calibration" else "known_evaluation"
            for row in variants:
                result[kind].append(
                    _protocol_row(
                        row,
                        protocol_id,
                        source_hash,
                        speaker_keys[speaker],
                        manifest_kind=kind,
                        protocol_split=split,
                    )
                )

    unknown_by_speaker = _group_source_variants(unknown_source)
    ordered_unknown = sorted(
        unknown_by_speaker,
        key=lambda speaker: canonical_sha256(
            {"protocol_id": protocol_id, "speaker": speaker, "purpose": "unknown-split"}
        ),
    )
    unknown_calibration_count = _partition_count(len(ordered_unknown), unknown_fraction)
    calibration_unknown = set(ordered_unknown[:unknown_calibration_count])
    for speaker, sources in sorted(unknown_by_speaker.items()):
        split = "calibration" if speaker in calibration_unknown else "evaluation"
        kind = "calibration" if split == "calibration" else "unknown_evaluation"
        for variants in sources.values():
            for row in variants:
                result[kind].append(
                    _protocol_row(
                        row,
                        protocol_id,
                        source_hash,
                        speaker_keys[speaker],
                        manifest_kind=kind,
                        protocol_split=split,
                    )
                )
    return result


def _protocol_row(
    source: Mapping[str, object],
    protocol_id: str,
    source_hash: str,
    speaker_key: str,
    *,
    manifest_kind: str,
    protocol_split: str,
) -> dict[str, object]:
    condition = str(source["protocol_condition"])
    role = str(source["role"])
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "protocol_id": protocol_id,
        "source_manifest_sha256": source_hash,
        "benchmark_tier": str(source["benchmark_tier"]),
        "manifest_kind": manifest_kind,
        "protocol_split": protocol_split,
        "trial_role": role,
        "protocol_condition": condition,
        "dataset": str(source["dataset"]),
        "item_id": privacy_safe_item_id(source, protocol_id),
        "speaker_key": speaker_key,
        "source_recording_id": str(source["source_recording_id"]),
        "source_utterance_id": str(source["source_utterance_id"]),
        "audio_path_project_relative": str(source["audio_path_project_relative"]),
        "augmentation_policy": str(source["augmentation_policy"]),
        "selection_rank": str(source["selection_rank"]),
        "enrolled_speaker": role in {"enrollment", "known_probe"},
        "known_speaker": role in {"enrollment", "known_probe"},
        "start_sec": float(source["start_sec"]),
        "end_sec": float(source["end_sec"]),
        "duration_sec": float(source["duration_sec"]),
        "gender": _optional_text(source.get("gender")),
        "accent_group": _optional_text(source.get("accent_group")),
    }


def _group_source_variants(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, list[Mapping[str, object]]]]:
    result: dict[str, dict[str, list[Mapping[str, object]]]] = {}
    for row in rows:
        speaker = str(row["speaker_id"])
        source_id = str(row["source_utterance_id"])
        result.setdefault(speaker, {}).setdefault(source_id, []).append(row)
    for sources in result.values():
        for source_id, variants in sources.items():
            conditions = {str(row["protocol_condition"]) for row in variants}
            if conditions != {"clean", "degraded"}:
                raise SpeakerProtocolError(
                    f"probe source {source_id} lacks a clean/degraded pair: {sorted(conditions)}"
                )
    return result


def _partition_count(total: int, fraction: float) -> int:
    if total < 2:
        raise SpeakerProtocolError("calibration/evaluation partition requires at least two units")
    return max(1, min(total - 1, int(round(total * fraction))))


def _split_rank(protocol_id: str, speaker: str, source_id: str) -> str:
    return canonical_sha256(
        {
            "protocol_id": protocol_id,
            "speaker": speaker,
            "source_utterance_id": source_id,
            "purpose": "calibration-evaluation-split",
        }
    )


def _source_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(row["dataset"]),
        str(row["speaker_key"]),
        str(row["source_utterance_id"]),
    )


def _row_sort_key(row: Mapping[str, object]) -> tuple[str, ...]:
    return (
        str(row["protocol_split"]),
        str(row["trial_role"]),
        str(row["speaker_key"]),
        str(row["source_utterance_id"]),
        str(row["protocol_condition"]),
        str(row["item_id"]),
    )


def _write_parquet_atomic(path: Path, rows: list[Mapping[str, object]]) -> None:
    table = pa.Table.from_pylist([dict(row) for row in rows], schema=PROTOCOL_ARROW_SCHEMA)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        pq.write_table(
            table,
            temporary,
            version="2.6",
            compression="NONE",
            use_dictionary=False,
            write_statistics=True,
        )
        validate_protocol_table(pq.read_table(temporary), expected_kind=rows[0]["manifest_kind"] if rows else None)
        _replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )


def _write_text_atomic(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8", newline="\n")
        _replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_with_retry(source: Path, destination: Path) -> None:
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value)
