"""Derive an ASR manifest from the frozen Common Voice 60+ breadth protocol."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Iterable, Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq
import soundfile as sf

from app.dataset_registry.registry import TextNormalizationSpec
from app.diarization_evaluation.artifacts import (
    file_sha256,
    write_json_atomic,
    write_parquet_atomic,
    write_text_atomic,
)
from app.scoring.text import normalize_for_scoring
from app.speaker_breadth.commonvoice import validate_protocol as validate_breadth_protocol
from app.utils.paths import resolve_data_path_from_logical

from .contracts import (
    ASRCommonVoiceError,
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROTOCOL_ROOT,
    MANIFEST_SCHEMA_VERSION,
    PROTOCOL_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    SEED,
    TOOL_ROOT,
    canonical_sha256,
    file_sha256 as contract_file_sha256,
    load_config,
)


SOURCE_PROTOCOL_ROOT = (
    TOOL_ROOT / "benchmarks" / "speaker_breadth" / "commonvoice_60plus_v1"
)
SOURCE_SELECTION = SOURCE_PROTOCOL_ROOT / "source_selection.tsv"
SOURCE_SUMMARY = SOURCE_PROTOCOL_ROOT / "protocol_summary.json"
SOURCE_PROVENANCE = SOURCE_PROTOCOL_ROOT / "dataset_provenance.json"


def audit_source(*, verify_audio_hashes: bool = False) -> dict[str, object]:
    """Audit transcript/reference eligibility without performing model inference."""

    source_validation = validate_breadth_protocol(
        SOURCE_PROTOCOL_ROOT, verify_audio_hashes=verify_audio_hashes
    )
    rows = _read_tsv(SOURCE_SELECTION)
    candidates = _candidate_transcripts()
    decoded = {
        row["item_id"]: row
        for row in _read_tsv(SOURCE_PROTOCOL_ROOT / "selected_audio_validation.tsv")
    }
    exclusions: list[dict[str, str]] = []
    transcript_hash_mismatches = 0
    selected: list[dict[str, object]] = []
    for row in rows:
        path_name = Path(row["logical_audio_path"]).name
        candidate = candidates.get(path_name)
        reasons: list[str] = []
        transcript = "" if candidate is None else str(candidate["transcript"])
        locale = "" if candidate is None else str(candidate["locale"])
        if candidate is None:
            reasons.append("reference_not_found_in_frozen_source_database")
        elif not transcript.strip():
            reasons.append("blank_reference")
        if locale.casefold() != "en":
            reasons.append("non_english_locale")
        source_hash = _source_transcript_hash(transcript)
        if transcript and source_hash != row["transcript_sha256"].upper():
            reasons.append("reference_hash_mismatch")
            transcript_hash_mismatches += 1
        audio_path = resolve_data_path_from_logical(row["logical_audio_path"])
        if not audio_path.is_file():
            reasons.append("missing_audio")
        else:
            frozen_decode = decoded.get(row["item_id"])
            if frozen_decode is None or frozen_decode.get("decoded_finite") != "True":
                reasons.append("frozen_audio_decode_validation_failed")
            try:
                info = sf.info(audio_path)
                if info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
                    reasons.append("audio_decode_invalid_metadata")
            except Exception:
                reasons.append("audio_decode_failed")
            if verify_audio_hashes and file_sha256(audio_path) != row["audio_sha256"].upper():
                reasons.append("audio_hash_mismatch")
        if reasons:
            exclusions.append({"item_id": row["item_id"], "reasons": ";".join(reasons)})
            continue
        selected.append(_manifest_row(row, transcript))
    return {
        "schema_version": "asr-commonvoice-source-audit.v1",
        "source_protocol_id": _read_json(SOURCE_SUMMARY)["protocol_id"],
        "source_selection_sha256": contract_file_sha256(SOURCE_SELECTION),
        "source_selected_items": len(rows),
        "eligible_items": len(selected),
        "excluded_items": len(exclusions),
        "exclusion_reason_counts": _reason_counts(exclusions),
        "transcript_hash_mismatches": transcript_hash_mismatches,
        "reference_words": sum(int(row["reference_words"]) for row in selected),
        "total_audio_seconds": sum(float(row["duration_sec"]) for row in selected),
        "selected_speakers": len({str(row["speaker_key"]) for row in selected}),
        "age_categories": _age_counts(selected),
        "audio_hashes_verified": verify_audio_hashes,
        "source_protocol_validation": source_validation,
        "model_inference_performed": False,
        "eligible_rows": selected,
        "exclusions": exclusions,
    }


def prepare_protocol(
    output_root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    verify_audio_hashes: bool = False,
) -> dict[str, object]:
    """Atomically freeze the model-independent ASR reference manifest."""

    destination = output_root.resolve()
    if destination.exists():
        result = validate_protocol(destination, verify_audio_hashes=verify_audio_hashes)
        return {**result, "reused_frozen_protocol": True}
    audit = audit_source(verify_audio_hashes=verify_audio_hashes)
    if audit["excluded_items"]:
        raise ASRCommonVoiceError(
            "the frozen 11,685-item source is not fully eligible; inspect Audit before freezing"
        )
    rows = list(audit.pop("eligible_rows"))
    exclusions = list(audit.pop("exclusions"))
    identity_payload = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "source_protocol_id": audit["source_protocol_id"],
        "source_selection_sha256": audit["source_selection_sha256"],
        "campaign_config_sha256": contract_file_sha256(DEFAULT_CONFIG_PATH),
        "normalization": load_config()["normalization"],
        "item_ids_sha256": canonical_sha256([row["item_id"] for row in rows]),
    }
    protocol_id = f"{PROTOCOL_VERSION}_{canonical_sha256(identity_payload)[:12].lower()}"
    for row in rows:
        row["schema_version"] = MANIFEST_SCHEMA_VERSION
        row["protocol_id"] = protocol_id
    summary = _summary(rows, protocol_id, identity_payload, audit)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.preparing"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        write_parquet_atomic(staging / "manifest.parquet", pa.Table.from_pylist(rows))
        _write_tsv(staging / "manifest.tsv", rows)
        _write_tsv(
            staging / "exclusions.tsv",
            exclusions,
            fieldnames=("item_id", "reasons"),
        )
        write_json_atomic(staging / "protocol_summary.json", summary)
        write_json_atomic(staging / "source_audit.json", audit)
        write_json_atomic(staging / "smoke_selection.json", _smoke_selection(rows))
        shutil.copyfile(DEFAULT_CONFIG_PATH, staging / "campaign_config.yaml")
        write_text_atomic(staging / "README.md", _protocol_readme(summary))
        _write_file_index(staging)
        validate_protocol(staging, verify_audio_hashes=False)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {**validate_protocol(destination), "reused_frozen_protocol": False}


def validate_protocol(
    root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    verify_audio_hashes: bool = False,
) -> dict[str, object]:
    """Validate checksums, identities, references, paths, and exact denominators."""

    root = root.resolve()
    index = _read_json(root / "protocol_files.json")
    for relative, expected in dict(index["files"]).items():
        path = root / relative
        if not path.is_file() or contract_file_sha256(path) != str(expected):
            raise ASRCommonVoiceError(f"frozen protocol file changed: {relative}")
    summary = _read_json(root / "protocol_summary.json")
    rows = pq.read_table(root / "manifest.parquet").to_pylist()
    if len(rows) != 11685 or int(summary["clips"]["total"]) != len(rows):
        raise ASRCommonVoiceError("ASR protocol denominator is not exactly 11,685")
    if len({str(row["item_id"]) for row in rows}) != len(rows):
        raise ASRCommonVoiceError("ASR protocol item IDs are not unique")
    source_ids = {row["item_id"] for row in _read_tsv(SOURCE_SELECTION)}
    if {row["item_id"] for row in rows} != source_ids:
        raise ASRCommonVoiceError("ASR protocol membership differs from frozen breadth source")
    missing = 0
    mismatched = 0
    if verify_audio_hashes:
        for row in rows:
            path = resolve_data_path_from_logical(str(row["logical_audio_path"]))
            missing += int(not path.is_file())
            if path.is_file() and file_sha256(path) != str(row["audio_sha256"]).upper():
                mismatched += 1
    if missing or mismatched:
        raise ASRCommonVoiceError(
            f"audio validation failed: missing={missing}, hash_mismatches={mismatched}"
        )
    return {
        "valid": True,
        "protocol_root": str(root),
        "protocol_id": summary["protocol_id"],
        "manifest_sha256": summary["manifest_sha256"],
        "selected_items": len(rows),
        "selected_speakers": summary["speakers"]["total"],
        "audio_hashes_verified": verify_audio_hashes,
        "model_inference_performed": False,
    }


def protocol_plan(root: Path = DEFAULT_PROTOCOL_ROOT) -> dict[str, object]:
    validation = validate_protocol(root)
    summary = _read_json(root / "protocol_summary.json")
    return {**validation, **summary, "model_inference_performed": False}


def read_manifest(root: Path = DEFAULT_PROTOCOL_ROOT) -> list[dict[str, object]]:
    validate_protocol(root)
    return [dict(row) for row in pq.read_table(root / "manifest.parquet").to_pylist()]


def read_smoke_ids(root: Path = DEFAULT_PROTOCOL_ROOT) -> tuple[str, ...]:
    return tuple(str(value) for value in _read_json(root / "smoke_selection.json")["item_ids"])


def _candidate_transcripts() -> dict[str, dict[str, str]]:
    provenance = _read_json(SOURCE_PROVENANCE)
    release = resolve_data_path_from_logical(str(provenance["common_voice_root_logical"]))
    database = (release / "prepared" / "en" / "state" / "common_voice_phase3.sqlite3").resolve()
    if not database.is_file():
        raise FileNotFoundError(f"Common Voice source database is missing: {database}")
    uri = database.as_posix()
    connection = sqlite3.connect(f"file:{uri}?mode=ro", uri=True)
    try:
        return {
            str(path): {"transcript": str(transcript), "locale": str(locale)}
            for path, transcript, locale in connection.execute(
                "SELECT path, transcript, locale FROM candidates"
            )
        }
    finally:
        connection.close()


def _manifest_row(source: Mapping[str, str], transcript: str) -> dict[str, object]:
    spec = TextNormalizationSpec(
        lowercase=True,
        remove_punctuation=True,
        strip_whitespace=True,
        collapse_whitespace=True,
    )
    duration = float(source["duration_sec"])
    reference = transcript.strip()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "protocol_id": "pending",
        "item_id": source["item_id"],
        "speaker_key": source["speaker_key"],
        "speaker_role": source["speaker_role"],
        "protocol_split": source["protocol_split"],
        "trial_role": source["trial_role"],
        "age_category": source["age_category"],
        "age_group": "eighties_plus"
        if source["age_category"] in {"eighties", "nineties"}
        else source["age_category"],
        "gender": source["gender"],
        "accent": source["accent"],
        "variant": source["variant"],
        "locale": source["locale"],
        "sentence_id": source["sentence_id"],
        "reference_text": reference,
        "reference_normalized": normalize_for_scoring(reference, spec),
        "reference_sha256": source["transcript_sha256"].upper(),
        "logical_audio_path": source["logical_audio_path"],
        "source_recording_id": source["source_recording_id"],
        "audio_sha256": source["audio_sha256"].upper(),
        "size_bytes": int(source["size_bytes"]),
        "duration_sec": duration,
        "duration_bucket": _duration_bucket(duration),
        "reference_words": len(normalize_for_scoring(reference, spec).split()),
        "transcript_length_bucket": _length_bucket(
            len(normalize_for_scoring(reference, spec).split())
        ),
        "sample_rate_hz": int(source["sample_rate_hz"]),
        "channels": int(source["channels"]),
        "audio_format": source["audio_format"],
    }


def _summary(
    rows: Sequence[Mapping[str, object]],
    protocol_id: str,
    identity: Mapping[str, object],
    audit: Mapping[str, object],
) -> dict[str, object]:
    speakers = {str(row["speaker_key"]) for row in rows}
    age_speakers: dict[str, set[str]] = {}
    for row in rows:
        age_speakers.setdefault(str(row["age_category"]), set()).add(str(row["speaker_key"]))
    manifest_payload = [
        {key: row[key] for key in row if key not in {"schema_version", "protocol_id"}}
        for row in rows
    ]
    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_id": protocol_id,
        "source_protocol_id": audit["source_protocol_id"],
        "selection_seed": SEED,
        "model_independent_manifest": True,
        "manifest_sha256": canonical_sha256(manifest_payload),
        "identity": dict(identity),
        "clips": {
            "total": len(rows),
            "enrollment": sum(row["protocol_split"] == "enrollment" for row in rows),
            "calibration": sum(row["protocol_split"] == "calibration" for row in rows),
            "evaluation": sum(row["protocol_split"] == "evaluation" for row in rows),
        },
        "speakers": {"total": len(speakers)},
        "age_category_speakers": {
            age: len(values) for age, values in sorted(age_speakers.items())
        },
        "duration": {
            "total_seconds": sum(float(row["duration_sec"]) for row in rows),
            "total_hours": sum(float(row["duration_sec"]) for row in rows) / 3600.0,
        },
        "reference_words": sum(int(row["reference_words"]) for row in rows),
        "age_categories": _age_counts(rows),
        "normalization": load_config()["normalization"],
        "exclusions": {
            "total": audit["excluded_items"],
            "reason_counts": audit["exclusion_reason_counts"],
        },
    }


def _smoke_selection(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    # Stable coverage-first selection: two clips per age, plus a ninth distinct speaker.
    chosen: list[Mapping[str, object]] = []
    used_speakers: set[str] = set()
    for age in ("sixties", "seventies", "eighties", "nineties"):
        candidates = sorted(
            (row for row in rows if row["age_category"] == age),
            key=lambda row: (str(row["speaker_key"]), str(row["item_id"])),
        )
        for row in candidates:
            if str(row["speaker_key"]) not in used_speakers:
                chosen.append(row)
                used_speakers.add(str(row["speaker_key"]))
            if sum(item["age_category"] == age for item in chosen) == 2 or (
                age == "nineties" and sum(item["age_category"] == age for item in chosen) == 2
            ):
                break
    for row in sorted(rows, key=lambda value: str(value["item_id"])):
        if len(chosen) >= 9:
            break
        if str(row["speaker_key"]) not in used_speakers:
            chosen.append(row)
            used_speakers.add(str(row["speaker_key"]))
    if len(chosen) != 9 or {row["age_category"] for row in chosen} != {
        "sixties", "seventies", "eighties", "nineties"
    }:
        raise ASRCommonVoiceError("could not build the required nine-clip smoke selection")
    return {
        "schema_version": "asr-commonvoice-smoke-selection.v1",
        "scientific_use_prohibited": True,
        "selection_method": "age-coverage-then-item-id-v1",
        "item_ids": [row["item_id"] for row in chosen],
        "speakers": len({row["speaker_key"] for row in chosen}),
        "age_categories": sorted({row["age_category"] for row in chosen}),
        "duration_seconds": sum(float(row["duration_sec"]) for row in chosen),
    }


def _write_file_index(root: Path) -> None:
    files = {
        path.relative_to(root).as_posix(): contract_file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "protocol_files.json"
    }
    write_json_atomic(
        root / "protocol_files.json",
        {"schema_version": "asr-commonvoice-protocol-files.v1", "files": files},
    )


def _protocol_readme(summary: Mapping[str, object]) -> str:
    return f"""# Frozen Common Voice 60+ ASR protocol

This is the model-independent ASR view of the existing frozen speaker-breadth
selection. It contains exactly {summary['clips']['total']} English clips from
{summary['speakers']['total']} pseudonymous speakers and no audio or raw Common
Voice client identifiers. `manifest.parquet` is authoritative; `manifest.tsv`
is its human-readable copy. References came from the frozen read-only source
database and were hash-checked against `source_selection.tsv`.

Protocol ID: `{summary['protocol_id']}`

Scoring lowercases text, removes ASCII punctuation, strips outer whitespace,
and collapses internal whitespace identically for reference and hypothesis.
No augmentation is used. Physical audio paths resolve through `JP_DATA_ROOT`.
This protocol is not a redistribution grant for Common Voice audio.
"""


def _duration_bucket(value: float) -> str:
    if value < 2.0:
        return "lt_2s"
    if value < 4.0:
        return "2_to_lt_4s"
    if value < 6.0:
        return "4_to_lt_6s"
    return "ge_6s"


def _length_bucket(value: int) -> str:
    if value <= 5:
        return "1_to_5_words"
    if value <= 10:
        return "6_to_10_words"
    if value <= 15:
        return "11_to_15_words"
    return "16plus_words"


def _source_transcript_hash(text: str) -> str:
    import hashlib

    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()


def _reason_counts(rows: Iterable[Mapping[str, str]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        for reason in str(row["reasons"]).split(";"):
            result[reason] = result.get(reason, 0) + 1
    return dict(sorted(result.items()))


def _age_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for age in sorted({str(row["age_category"]) for row in rows}):
        selected = [row for row in rows if str(row["age_category"]) == age]
        result[age] = {
            "speakers": len({str(row["speaker_key"]) for row in selected}),
            "utterances": len(selected),
            "reference_words": sum(int(row["reference_words"]) for row in selected),
            "audio_duration_sec": sum(float(row["duration_sec"]) for row in selected),
        }
    return result


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ASRCommonVoiceError(f"expected JSON object: {path}")
    return value


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream, delimiter="\t")]


def _write_tsv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> None:
    columns = list(fieldnames or (list(rows[0]) if rows else ()))
    if not columns:
        raise ASRCommonVoiceError(f"TSV columns are required: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
