"""Immutable native-condition scoring views derived from frozen Stage 2 manifests."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.manifest_io import read_manifest
from app.diarization_evaluation.artifacts import (
    file_sha256,
    write_json_atomic,
    write_jsonl_atomic,
    write_parquet_atomic,
    write_text_atomic,
)
from app.diarization_evaluation.contracts import (
    NATIVE_MANIFEST_SCHEMA_VERSION,
    REFERENCE_SCHEMA_VERSION,
    TOOL_ROOT,
    DiarizationEvaluationError,
    load_policy,
)
from app.diarization_evaluation.formats import RttmTurn, UemRegion


DATA_ROOT = TOOL_ROOT.parent
MANIFEST_INDEX_SCHEMA_VERSION = "native-diarization-manifest-index.v1"
CANONICALIZATION_VERSION = "native-diarization-canonicalization.v1"


def _field(name: str, data_type: pa.DataType, *, nullable: bool = True) -> pa.Field:
    return pa.field(name, data_type, nullable=nullable)


NATIVE_MANIFEST_SCHEMA = pa.schema(
    [
        _field("schema_version", pa.string(), nullable=False),
        _field("manifest_id", pa.string(), nullable=False),
        _field("source_manifest_sha256", pa.string(), nullable=False),
        _field("benchmark_tier", pa.string(), nullable=False),
        _field("evaluation_unit_id", pa.string(), nullable=False),
        _field("scoring_file_id", pa.string(), nullable=False),
        _field("dataset", pa.string(), nullable=False),
        _field("recording_id", pa.string(), nullable=False),
        _field("source_recording_id", pa.string(), nullable=False),
        _field("utt_id", pa.string(), nullable=False),
        _field("audio_path_project_relative", pa.string(), nullable=False),
        _field("augmentation_policy", pa.string(), nullable=False),
        _field("synthetic_augmentation_applied", pa.bool_(), nullable=False),
        _field("source_start_sec", pa.float64(), nullable=False),
        _field("source_end_sec", pa.float64(), nullable=False),
        _field("duration_sec", pa.float64(), nullable=False),
        _field("scored_region_start_sec", pa.float64(), nullable=False),
        _field("scored_region_end_sec", pa.float64(), nullable=False),
        _field("timebase", pa.string(), nullable=False),
        _field("reference_support", pa.string(), nullable=False),
        _field("reference_reason", pa.string(), nullable=False),
        _field("reference_version", pa.string(), nullable=False),
        _field("der_jer_eligible", pa.bool_(), nullable=False),
        _field("cpwer_eligible", pa.bool_(), nullable=False),
        _field("reference_segment_count", pa.int64(), nullable=False),
        _field("reference_speaker_count", pa.int64(), nullable=False),
        _field("reference_has_overlap", pa.bool_(), nullable=False),
        _field("meeting_id", pa.string()),
        _field("session_id", pa.string()),
        _field("stream_type", pa.string()),
        _field("stream_id", pa.string()),
        _field("channel_id", pa.string()),
        _field("microphone_id", pa.string()),
        _field("device_id", pa.string()),
        _field("recording_speaker_id_ref", pa.string()),
        _field("location", pa.string()),
        _field("room", pa.string()),
        _field("distractor", pa.string()),
        _field("mic", pa.string()),
        _field("position", pa.string()),
        _field("degrees", pa.string()),
    ],
    metadata={
        b"manifest_schema_version": NATIVE_MANIFEST_SCHEMA_VERSION.encode(),
        b"canonicalization_version": CANONICALIZATION_VERSION.encode(),
        b"reference_schema_version": REFERENCE_SCHEMA_VERSION.encode(),
        b"selection_seed": b"3800",
        b"hash_algorithm": b"sha256",
        b"authoritative_representation": b"parquet",
        b"synthetic_augmentation": b"forbidden",
        b"timebase": b"source_recording_absolute_seconds",
    },
)


def build_native_diarization_manifest(
    output_root: Path,
    *,
    tier: str = "small",
    policy_path: Path | None = None,
) -> dict[str, object]:
    """Build deterministic Stage 11 views without changing normalized metadata."""

    policy_source = (policy_path or (TOOL_ROOT / "configs/automated_evaluation/diarization_evaluation.v1.yaml")).resolve()
    policy = load_policy(policy_source)
    source_manifests = _mapping(policy.get("source_manifests"), "source_manifests")
    if tier not in source_manifests:
        raise DiarizationEvaluationError(f"unsupported native diarization tier {tier!r}")
    source_path = (TOOL_ROOT / str(source_manifests[tier])).resolve()
    source_hash = file_sha256(source_path)
    source_rows = [
        dict(row)
        for row in read_manifest(source_path)
        if row["panel"] == "native_robustness"
        and row["benchmark_tier"] == tier
        and row["dataset"] in {"ami", "chime6", "voices"}
    ]
    if not source_rows:
        raise DiarizationEvaluationError(f"no native Stage 11 rows exist for tier {tier}")
    _validate_native_rows(source_rows)

    policy_hash = file_sha256(policy_source)
    manifest_id = "native_diarization_" + canonical_sha256(
        {
            "schema_version": NATIVE_MANIFEST_SCHEMA_VERSION,
            "tier": tier,
            "source_manifest_sha256": source_hash,
            "policy_sha256": policy_hash,
        }
    )[:12].lower()
    reference_rows = _load_reference_rows(source_rows, policy)
    manifest_rows: list[dict[str, object]] = []
    all_turns: list[RttmTurn] = []
    all_uem: list[UemRegion] = []
    transcript_rows: list[dict[str, object]] = []

    for source in sorted(source_rows, key=_source_sort_key):
        unit_id = _unit_id(source, source_hash)
        start = float(source["start_sec"])
        end = float(source["end_sec"])
        reference = _reference_for_unit(source, unit_id, reference_rows, policy)
        turns = reference["turns"]
        uem = UemRegion(unit_id, "1", start, end)
        all_turns.extend(turns)
        all_uem.append(uem)
        transcript_rows.extend(reference["transcripts"])
        manifest_rows.append(
            {
                "schema_version": NATIVE_MANIFEST_SCHEMA_VERSION,
                "manifest_id": manifest_id,
                "source_manifest_sha256": source_hash,
                "benchmark_tier": tier,
                "evaluation_unit_id": unit_id,
                "scoring_file_id": unit_id,
                "dataset": source["dataset"],
                "recording_id": source["recording_id"],
                "source_recording_id": source["source_recording_id"],
                "utt_id": source["utt_id"],
                "audio_path_project_relative": source["audio_path_project_relative"],
                "augmentation_policy": source["augmentation_policy"],
                "synthetic_augmentation_applied": False,
                "source_start_sec": start,
                "source_end_sec": end,
                "duration_sec": end - start,
                "scored_region_start_sec": start,
                "scored_region_end_sec": end,
                "timebase": "source_recording_absolute_seconds",
                "reference_support": reference["support"],
                "reference_reason": reference["reason"],
                "reference_version": reference["version"],
                "der_jer_eligible": reference["der_jer_eligible"],
                "cpwer_eligible": reference["cpwer_eligible"],
                "reference_segment_count": len(turns),
                "reference_speaker_count": len({turn.speaker_label for turn in turns}),
                "reference_has_overlap": _has_overlap(turns),
                **{name: _optional_text(source.get(name)) for name in _PRESERVED_FIELDS},
            }
        )

    table = pa.Table.from_pylist(manifest_rows, schema=NATIVE_MANIFEST_SCHEMA)
    validate_native_manifest_table(table)
    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = write_parquet_atomic(root / "native_diarization_manifest.parquet", table)
    rttm_path = write_text_atomic(
        root / "references.rttm",
        "\n".join(turn.to_line() for turn in sorted(set(all_turns)))
        + ("\n" if all_turns else ""),
    )
    uem_path = write_text_atomic(
        root / "scored_regions.uem",
        "\n".join(region.to_line() for region in sorted(set(all_uem))) + "\n",
    )
    transcript_path = write_jsonl_atomic(
        root / "reference_transcripts.jsonl",
        sorted(transcript_rows, key=lambda row: (str(row["evaluation_unit_id"]), float(row["start_sec"]), str(row["speaker_label"]))),
    )
    counts = _compatibility_counts(manifest_rows)
    index: dict[str, object] = {
        "schema_version": MANIFEST_INDEX_SCHEMA_VERSION,
        "manifest_schema_version": NATIVE_MANIFEST_SCHEMA_VERSION,
        "reference_schema_version": REFERENCE_SCHEMA_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "hash_algorithm": "sha256",
        "authoritative_representation": "parquet",
        "manifest_id": manifest_id,
        "benchmark_tier": tier,
        "selection_seed": 3800,
        "source_manifest": {
            "path": source_path.relative_to(TOOL_ROOT).as_posix(),
            "sha256": source_hash,
            "schema_version": "benchmark-manifest.v1",
        },
        "policy": {
            "path": policy_source.relative_to(TOOL_ROOT).as_posix(),
            "sha256": policy_hash,
            "schema_version": policy["schema_version"],
        },
        "artifacts": {
            "manifest": _artifact(manifest_path, root),
            "reference_rttm": _artifact(rttm_path, root),
            "scored_regions_uem": _artifact(uem_path, root),
            "reference_transcripts": _artifact(transcript_path, root),
        },
        "counts": counts,
        "scientific_constraints": {
            "synthetic_augmentation_allowed": False,
            "absolute_source_timing_preserved": True,
            "anonymous_predictions_must_not_be_mapped_to_reference_identities": True,
            "voices_der_jer_suppressed": True,
        },
    }
    index_path = write_json_atomic(root / "native_diarization_manifest.json", index)
    write_text_atomic(
        root / "native_diarization_manifest.sha256",
        f"{file_sha256(index_path).lower()}  native_diarization_manifest.json\n",
    )
    return index


def read_native_manifest(path: Path) -> list[dict[str, object]]:
    table = pq.read_table(path)
    validate_native_manifest_table(table)
    return [dict(row) for row in table.to_pylist()]


def validate_native_manifest_table(table: pa.Table) -> None:
    if not table.schema.remove_metadata().equals(NATIVE_MANIFEST_SCHEMA.remove_metadata()):
        raise DiarizationEvaluationError("native diarization Parquet schema mismatch")
    metadata = table.schema.metadata or {}
    for key, expected in (NATIVE_MANIFEST_SCHEMA.metadata or {}).items():
        if metadata.get(key) != expected:
            raise DiarizationEvaluationError(
                f"native diarization metadata mismatch: {key.decode()}"
            )
    seen: set[str] = set()
    for row in table.to_pylist():
        if row["schema_version"] != NATIVE_MANIFEST_SCHEMA_VERSION:
            raise DiarizationEvaluationError("unsupported native manifest row version")
        if row["augmentation_policy"] != "native_only" or row["synthetic_augmentation_applied"]:
            raise DiarizationEvaluationError("native diarization rows may not be augmented")
        if row["dataset"] not in {"ami", "chime6", "voices"}:
            raise DiarizationEvaluationError("unsupported native diarization dataset")
        if row["timebase"] != "source_recording_absolute_seconds":
            raise DiarizationEvaluationError("native manifest timebase changed")
        start, end = float(row["source_start_sec"]), float(row["source_end_sec"])
        if start < 0 or end <= start or not math.isclose(end - start, float(row["duration_sec"]), abs_tol=1e-6):
            raise DiarizationEvaluationError("invalid native manifest bounds")
        unit = str(row["evaluation_unit_id"])
        if unit in seen:
            raise DiarizationEvaluationError(f"duplicate evaluation unit: {unit}")
        seen.add(unit)
        if row["dataset"] == "voices" and row["der_jer_eligible"]:
            raise DiarizationEvaluationError("VOiCES rows cannot claim DER/JER eligibility")


_PRESERVED_FIELDS = (
    "meeting_id",
    "session_id",
    "stream_type",
    "stream_id",
    "channel_id",
    "microphone_id",
    "device_id",
    "recording_speaker_id_ref",
    "location",
    "room",
    "distractor",
    "mic",
    "position",
    "degrees",
)


def _validate_native_rows(rows: Sequence[Mapping[str, object]]) -> None:
    for row in rows:
        if row.get("panel") != "native_robustness":
            raise DiarizationEvaluationError("Stage 11 accepts only native_robustness rows")
        if row.get("augmentation_policy") != "native_only":
            raise DiarizationEvaluationError("Stage 11 native rows must be native_only")
        if row.get("noise_type") is not None or row.get("rir_label") is not None:
            raise DiarizationEvaluationError("synthetic noise or RIR is forbidden for Stage 11")


def _load_reference_rows(
    source_rows: Sequence[Mapping[str, object]],
    policy: Mapping[str, object],
) -> dict[str, list[dict[str, object]]]:
    native = _mapping(policy.get("native_datasets"), "native_datasets")
    ami_recordings = sorted({str(row["recording_id"]) for row in source_rows if row["dataset"] == "ami"})
    chime_sessions = sorted({str(row["session_id"]) for row in source_rows if row["dataset"] == "chime6"})
    output: dict[str, list[dict[str, object]]] = {"ami": [], "chime6": [], "voices": []}
    if ami_recordings:
        path = _normalized_path(_mapping(native["ami"], "native_datasets.ami")["normalized_segments"])
        output["ami"] = [
            dict(row)
            for row in pq.read_table(path, filters=[("recording_id", "in", ami_recordings)]).to_pylist()
        ]
    if chime_sessions:
        path = _normalized_path(_mapping(native["chime6"], "native_datasets.chime6")["normalized_segments"])
        output["chime6"] = [
            dict(row)
            for row in pq.read_table(path, filters=[("session_id", "in", chime_sessions)]).to_pylist()
        ]
    return output


def _reference_for_unit(
    source: Mapping[str, object],
    unit_id: str,
    reference_rows: Mapping[str, Sequence[Mapping[str, object]]],
    policy: Mapping[str, object],
) -> dict[str, object]:
    dataset = str(source["dataset"])
    native = _mapping(policy["native_datasets"], "native_datasets")
    dataset_policy = _mapping(native[dataset], f"native_datasets.{dataset}")
    version = str(dataset_policy["reference_version"])
    if dataset == "voices":
        return {
            "turns": [],
            "transcripts": [],
            "support": "condition_only",
            "reason": "VOiCES has native condition metadata and whole-file text but no compatible fine-grained speech timing for DER/JER.",
            "version": version,
            "der_jer_eligible": False,
            "cpwer_eligible": False,
        }
    start = float(source["start_sec"])
    end = float(source["end_sec"])
    candidates: list[Mapping[str, object]] = []
    if dataset == "ami":
        candidates = [
            row
            for row in reference_rows[dataset]
            if row["recording_id"] == source["recording_id"]
            and float(row["end_sec"]) > start
            and float(row["start_sec"]) < end
        ]
        support = (
            "multi_speaker_manual_timing"
            if source.get("stream_type") == "array"
            else "single_speaker_close_talk_timing"
        )
        reason = (
            "AMI manual segments aligned to the selected array recording."
            if source.get("stream_type") == "array"
            else "AMI headset metadata contains the wearer reference only; single-speaker timing is valid but meeting-wide confusion is not represented."
        )
        speaker_field, text_field = "speaker_global_name", "text_norm"
    else:
        candidates = [
            row
            for row in reference_rows[dataset]
            if row["session_id"] == source["session_id"]
            and row["split"] == source["split"]
            and float(row["end_sec"]) > start
            and float(row["start_sec"]) < end
        ]
        if source.get("stream_type") == "participant_close":
            wearer = _optional_text(source.get("recording_speaker_id_ref"))
            candidates = [row for row in candidates if _optional_text(row.get("speaker_id_ref")) == wearer]
            support = "single_speaker_close_talk_timing"
            reason = "CHiME-6 participant-close scoring uses only the wearer reference."
        else:
            support = "multi_speaker_session_timing"
            reason = "CHiME-6 session segments aligned to the selected far-field stream."
        speaker_field, text_field = "speaker_id_ref", None

    turns: list[RttmTurn] = []
    transcripts: list[dict[str, object]] = []
    transcript_complete = True
    for row in candidates:
        raw_start = float(row["start_sec"])
        raw_end = float(row["end_sec"])
        clipped_start = max(start, raw_start)
        clipped_end = min(end, raw_end)
        if clipped_end <= clipped_start:
            continue
        label = _reference_speaker_label(dataset, row.get(speaker_field))
        turns.append(RttmTurn(unit_id, "1", clipped_start, clipped_end, label))
        full_segment = math.isclose(raw_start, clipped_start, abs_tol=1e-6) and math.isclose(
            raw_end, clipped_end, abs_tol=1e-6
        )
        text = _optional_text(row.get(text_field)) if text_field else None
        if not full_segment or not text:
            transcript_complete = False
        transcripts.append(
            {
                "schema_version": "speaker-attributed-reference-transcript.v1",
                "evaluation_unit_id": unit_id,
                "speaker_label": label,
                "start_sec": clipped_start,
                "end_sec": clipped_end,
                "text": text if full_segment else None,
                "full_reference_segment": full_segment,
            }
        )
    turns = sorted(set(turns))
    eligible = bool(turns)
    if not eligible:
        support = "incompatible"
        reason = "No compatible reference speech segment intersects the selected scored region."
    return {
        "turns": turns,
        "transcripts": transcripts,
        "support": support,
        "reason": reason,
        "version": version,
        "der_jer_eligible": eligible,
        "cpwer_eligible": eligible and transcript_complete and bool(transcripts),
    }


def _unit_id(source: Mapping[str, object], source_hash: str) -> str:
    payload = {
        "schema_version": NATIVE_MANIFEST_SCHEMA_VERSION,
        "source_manifest_sha256": source_hash,
        "dataset": source["dataset"],
        "source_recording_id": source["source_recording_id"],
        "utt_id": source["utt_id"],
        "start_sec": float(source["start_sec"]),
        "end_sec": float(source["end_sec"]),
    }
    return "diar_" + canonical_sha256(payload)[:12].lower()


def _reference_speaker_label(dataset: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise DiarizationEvaluationError("reference segment has no speaker label")
    digest = hashlib.sha256(f"{dataset}\0{text}".encode("utf-8")).hexdigest()[:12]
    return f"ref_{digest}"


def _has_overlap(turns: Sequence[RttmTurn]) -> bool:
    for index, left in enumerate(turns):
        for right in turns[index + 1 :]:
            if left.speaker_label != right.speaker_label and min(left.end_sec, right.end_sec) > max(left.start_sec, right.start_sec):
                return True
    return False


def _compatibility_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_dataset: dict[str, dict[str, int]] = {}
    for row in rows:
        dataset = str(row["dataset"])
        value = by_dataset.setdefault(dataset, {"units": 0, "der_jer_eligible": 0, "cpwer_eligible": 0})
        value["units"] += 1
        value["der_jer_eligible"] += int(bool(row["der_jer_eligible"]))
        value["cpwer_eligible"] += int(bool(row["cpwer_eligible"]))
    return {
        "evaluation_units": len(rows),
        "der_jer_eligible": sum(int(bool(row["der_jer_eligible"])) for row in rows),
        "cpwer_eligible": sum(int(bool(row["cpwer_eligible"])) for row in rows),
        "by_dataset": by_dataset,
    }


def _normalized_path(value: object) -> Path:
    path = (TOOL_ROOT / str(value)).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"normalized reference metadata is missing: {path}")
    return path


def _source_sort_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        str(row["dataset"]),
        str(row["recording_id"]),
        float(row["start_sec"]),
        float(row["end_sec"]),
        str(row["utt_id"]),
    )


def _artifact(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DiarizationEvaluationError(f"{label} must be a mapping")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
