"""Deterministic Common Voice 60+ breadth protocol construction and validation."""

from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from typing import Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import soundfile as sf
import yaml

from app.benchmark_contracts.manifest_io import file_sha256
from app.speaker_protocol.contracts import MANIFEST_SCHEMA_VERSION, TOOL_ROOT
from app.speaker_protocol.evaluation import observations_from_npz
from app.speaker_protocol.extraction import load_backend_identity
from app.speaker_protocol.manifests import (
    MANIFEST_FILENAMES,
    PROTOCOL_ARROW_SCHEMA,
    leakage_report as stage10_leakage_report,
    read_protocol_rows,
    validate_protocol_manifest_set,
)
from app.utils.paths import resolve_data_path_from_logical


SCHEMA_VERSION = "speaker-breadth-commonvoice-60plus.v1"
SELECTION_ALGORITHM_VERSION = "commonvoice-speaker-breadth-selection.v1"
DEFAULT_CONFIG_PATH = (
    TOOL_ROOT
    / "configs"
    / "automated_evaluation"
    / "speaker_breadth_commonvoice_60plus.v1.yaml"
)
DEFAULT_PROTOCOL_ROOT = (
    TOOL_ROOT / "benchmarks" / "speaker_breadth" / "commonvoice_60plus_v1"
)
CORE_KINDS = ("enrollment", "calibration", "known_evaluation", "unknown_evaluation")


class SpeakerBreadthError(ValueError):
    """Raised when the breadth experiment contract is violated."""


@dataclass(frozen=True)
class CandidateClip:
    """One validated local Common Voice clip before privacy-safe publication."""

    path: str
    source_speaker_id: str
    transcript: str
    sentence_id: str
    sentence_domain: str
    age_category: str
    gender: str
    accent: str
    variant: str
    locale: str
    up_votes: str
    down_votes: str
    audio_sha256: str
    size_bytes: int
    duration_sec: float
    sample_rate_hz: int
    channels: int
    audio_format: str

    @property
    def normalized_transcript(self) -> str:
        return " ".join(self.transcript.casefold().split())

    @property
    def transcript_sha256(self) -> str:
        return _sha256_text(self.normalized_transcript).upper()


def prepare_protocol(
    output_root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    validate_audio: bool = True,
) -> dict[str, object]:
    """Audit local data and atomically freeze a new model-independent protocol."""

    destination = output_root.resolve()
    if destination.exists():
        if (destination / "protocol_files.json").is_file():
            result = validate_protocol(destination, verify_audio_hashes=True)
            return {**protocol_plan(destination, []), "reused_frozen_protocol": True, "validation": result}
        raise SpeakerBreadthError(
            f"protocol destination exists but is not a complete freeze: {destination}"
        )

    config_source = config_path.resolve()
    config = _load_config(config_source)
    release_root = resolve_data_path_from_logical(str(config["dataset"]["release_root_logical"]))
    paths = _source_paths(release_root, config)
    _validate_source_identity(paths, config)
    candidates = _load_candidates(paths["state_database"], config)
    audit = _dataset_audit(paths, candidates, config)
    protocol_identity = _protocol_identity(config_source, paths, config)
    selection = select_cohort(candidates, config, protocol_identity)
    rows_by_kind, source_rows, speakers = _build_protocol_rows(
        selection, config, protocol_identity, paths
    )

    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{destination.name}.preparing"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        _write_protocol_manifests(staging, rows_by_kind, protocol_identity, config_source, paths)
        _write_tsv(staging / "source_selection.tsv", source_rows)
        _write_tsv(staging / "speaker_inventory.tsv", speakers)
        _write_tsv(
            staging / "split_assignments.tsv",
            [
                {
                    "speaker_key": row["speaker_key"],
                    "age_category": row["age_category"],
                    "speaker_role": row["speaker_role"],
                    "unknown_split": row["unknown_split"],
                }
                for row in speakers
            ],
        )
        coverage = _metadata_coverage(source_rows)
        _write_tsv(staging / "metadata_coverage.tsv", coverage)
        durations = _duration_report(source_rows, config)
        _write_json(staging / "duration_report.json", durations)
        _write_json(staging / "dataset_audit.json", audit)
        shutil.copyfile(config_source, staging / "selection_config.yaml")
        audio_rows = _validate_selected_audio(source_rows, config) if validate_audio else []
        if validate_audio:
            _write_tsv(staging / "selected_audio_validation.tsv", audio_rows)
        leakage = _breadth_leakage(rows_by_kind, source_rows, data_paths_exist=True)
        _write_json(staging / "leakage_validation.json", leakage)
        if not leakage["all_required_checks_passed"]:
            raise SpeakerBreadthError(f"breadth leakage validation failed: {leakage}")
        summary = _protocol_summary(selection, source_rows, speakers, durations, protocol_identity)
        _write_json(staging / "protocol_summary.json", summary)
        provenance = _provenance(
            config_source, paths, config, audit, summary, protocol_identity
        )
        _write_json(staging / "dataset_provenance.json", provenance)
        _write_text(staging / "README.md", _package_readme(summary, config))
        _write_file_index(staging)
        validate_protocol(staging, verify_audio_hashes=False)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {**protocol_plan(destination, []), "reused_frozen_protocol": False}


def select_cohort(
    candidates: Sequence[CandidateClip],
    config: Mapping[str, object],
    protocol_identity: str,
) -> dict[str, object]:
    """Select every eligible speaker with fixed caps and deterministic role assignment."""

    eligibility = _mapping(config["eligibility"], "eligibility")
    selection_config = _mapping(config["selection"], "selection")
    known_required = int(eligibility["known_total_clips"])
    unknown_required = int(eligibility["unknown_total_clips"])
    unknown_fraction = float(selection_config["unknown_speaker_fraction"])
    if known_required < unknown_required:
        raise SpeakerBreadthError("known clip requirement cannot be below Unknown requirement")

    by_speaker: dict[str, list[CandidateClip]] = {}
    for clip in candidates:
        by_speaker.setdefault(clip.source_speaker_id, []).append(clip)
    usable: dict[str, list[CandidateClip]] = {
        speaker: _unique_transcript_clips(rows, protocol_identity, speaker)
        for speaker, rows in by_speaker.items()
    }
    eligible_unknown = {
        speaker for speaker, rows in usable.items() if len(rows) >= unknown_required
    }
    eligible_known = {
        speaker for speaker, rows in usable.items() if len(rows) >= known_required
    }
    reserve = int(eligibility["useful_reserve_clips"])
    counts = [len(rows) for rows in usable.values()]
    if not eligible_known or len(eligible_unknown - eligible_known) >= len(eligible_unknown):
        raise SpeakerBreadthError("Common Voice population cannot satisfy Stage 10 roles")

    ages = {speaker: rows[0].age_category for speaker, rows in usable.items() if rows}
    unknown_speakers: set[str] = set()
    for age in sorted({ages[speaker] for speaker in eligible_unknown}):
        age_eligible = sorted(s for s in eligible_unknown if ages[s] == age)
        forced = {speaker for speaker in age_eligible if speaker not in eligible_known}
        target = max(len(forced), int(round(len(age_eligible) * unknown_fraction)))
        ranked_optional = sorted(
            (speaker for speaker in age_eligible if speaker not in forced),
            key=lambda speaker: _rank(protocol_identity, "known-unknown", age, speaker),
        )
        unknown_speakers.update(forced)
        unknown_speakers.update(ranked_optional[: target - len(forced)])
    known_speakers = eligible_unknown - unknown_speakers
    if not known_speakers <= eligible_known:
        raise SpeakerBreadthError("a Known speaker does not satisfy the known clip minimum")

    calibration_unknown = _calibration_unknown_speakers(
        unknown_speakers,
        ages,
        float(selection_config["calibration_unknown_speaker_fraction"]),
        protocol_identity,
    )
    evaluation_unknown = unknown_speakers - calibration_unknown
    if not calibration_unknown or not evaluation_unknown:
        raise SpeakerBreadthError("Unknown calibration/evaluation speaker sets must both be non-empty")

    selected: dict[str, dict[str, object]] = {}
    for speaker in sorted(known_speakers):
        selected[speaker] = {
            "speaker_role": "known",
            "unknown_split": "not_applicable",
            "clips": usable[speaker][:known_required],
            "available_unique_clips": len(usable[speaker]),
            "available_source_clips": len(by_speaker[speaker]),
        }
    for speaker in sorted(unknown_speakers):
        selected[speaker] = {
            "speaker_role": "unknown",
            "unknown_split": (
                "calibration" if speaker in calibration_unknown else "evaluation"
            ),
            "clips": usable[speaker][:unknown_required],
            "available_unique_clips": len(usable[speaker]),
            "available_source_clips": len(by_speaker[speaker]),
        }
    return {
        "selected": selected,
        "eligible_known_speakers": len(eligible_known),
        "eligible_unknown_speakers": len(eligible_unknown),
        "eligible_known_with_reserve": sum(value >= known_required + reserve for value in counts),
        "eligible_unknown_with_reserve": sum(value >= unknown_required + reserve for value in counts),
        "unique_transcript_clip_distribution": _clip_count_distribution(counts),
        "known_speakers": known_speakers,
        "calibration_unknown_speakers": calibration_unknown,
        "evaluation_unknown_speakers": evaluation_unknown,
    }


def validate_protocol(
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    verify_audio_hashes: bool = False,
) -> dict[str, object]:
    """Validate the frozen support files, Stage 10 manifests, and source resolution."""

    root = protocol_root.resolve()
    _validate_file_index(root)
    stage10 = validate_protocol_manifest_set(root)
    source_rows = _read_tsv(root / "source_selection.tsv")
    manifest_rows = {
        kind: read_protocol_rows(root / MANIFEST_FILENAMES[kind], expected_kind=kind)
        for kind in CORE_KINDS
    }
    manifest_items = {
        str(row["item_id"]): row for rows in manifest_rows.values() for row in rows
    }
    source_items = {str(row["item_id"]): row for row in source_rows}
    if len(source_items) != len(source_rows) or set(source_items) != set(manifest_items):
        raise SpeakerBreadthError("source selection does not reconcile with core manifests")
    for item_id, support in source_items.items():
        manifest = manifest_items[item_id]
        if support["speaker_key"] != manifest["speaker_key"]:
            raise SpeakerBreadthError(f"speaker mapping mismatch for {item_id}")
        if support["logical_audio_path"] != manifest["audio_path_project_relative"]:
            raise SpeakerBreadthError(f"audio path mapping mismatch for {item_id}")
    missing = []
    hash_mismatches = []
    for row in source_rows:
        path = resolve_data_path_from_logical(row["logical_audio_path"])
        if not path.is_file():
            missing.append(row["logical_audio_path"])
        elif verify_audio_hashes and file_sha256(path).upper() != row["audio_sha256"].upper():
            hash_mismatches.append(row["logical_audio_path"])
    if missing:
        raise SpeakerBreadthError(f"{len(missing)} selected Common Voice files are missing")
    if hash_mismatches:
        raise SpeakerBreadthError(f"{len(hash_mismatches)} selected audio hashes changed")
    leakage = _breadth_leakage(manifest_rows, source_rows, data_paths_exist=not missing)
    if not leakage["all_required_checks_passed"]:
        raise SpeakerBreadthError(f"breadth protocol leakage detected: {leakage}")
    frozen_leakage = _read_json(root / "leakage_validation.json")
    for key, value in leakage.items():
        if key.endswith("_count") or key == "all_required_checks_passed":
            continue
        if key in frozen_leakage and frozen_leakage[key] != value:
            raise SpeakerBreadthError(f"frozen leakage report disagrees for {key}")
    return {
        "valid": True,
        "protocol_root": str(root),
        "selected_files": len(source_rows),
        "missing_files": 0,
        "audio_hashes_verified": verify_audio_hashes,
        "stage10_compatible": True,
        "stage10": stage10,
        "leakage": leakage,
    }


def selected_paths_exist(source_rows: Sequence[Mapping[str, object]]) -> bool:
    """Return whether every logical source path resolves through ``JP_DATA_ROOT``."""

    return all(
        resolve_data_path_from_logical(str(row["logical_audio_path"])).is_file()
        for row in source_rows
    )


def protocol_plan(protocol_root: Path, backends: Sequence[str]) -> dict[str, object]:
    """Return a no-inference summary suitable for CLI and PowerShell display."""

    root = protocol_root.resolve()
    summary = _read_json(root / "protocol_summary.json")
    return {
        "schema_version": "speaker-breadth-plan.v1",
        "protocol_root": str(root),
        "protocol_id": summary["protocol_id"],
        "protocol_name": "Common Voice 60+ speaker breadth v1",
        "eligible_60plus_speakers": summary["eligibility"]["unknown_candidates"],
        "known_speakers": summary["speakers"]["known"],
        "calibration_unknown_speakers": summary["speakers"]["calibration_unknown"],
        "evaluation_unknown_speakers": summary["speakers"]["evaluation_unknown"],
        "enrollment_clips": summary["clips"]["enrollment"],
        "calibration_probe_clips": summary["clips"]["calibration"],
        "evaluation_probe_clips": summary["clips"]["evaluation"],
        "total_selected_clips": summary["clips"]["total"],
        "total_audio_hours": summary["duration"]["total_hours"],
        "age_categories": summary["age_categories"],
        "selected_backends": list(backends),
        "estimated_extraction_jobs": len(backends),
        "model_inference_performed": False,
    }


def validate_extraction_bundle(
    protocol_root: Path, extraction_root: Path, backend: str
) -> dict[str, object]:
    """Validate a restart candidate before reusing its backend observations."""

    root = extraction_root.resolve()
    identity = load_backend_identity(root / "backend_identity.json")
    if identity.backend_id != backend:
        raise SpeakerBreadthError("extraction backend identity does not match requested backend")
    observations = observations_from_npz(root / "observations.npz", identity)
    expected = {
        str(row["item_id"])
        for kind in CORE_KINDS
        for row in read_protocol_rows(
            protocol_root / MANIFEST_FILENAMES[kind], expected_kind=kind
        )
    }
    observed = {row.item_id for row in observations}
    if len(observed) != len(observations) or observed != expected:
        raise SpeakerBreadthError("extraction item IDs do not match the frozen protocol")
    summary = _read_json(root / "extraction_summary.json")
    if int(summary.get("expected_items") or -1) != len(expected):
        raise SpeakerBreadthError("extraction summary denominator mismatch")
    if str(summary.get("backend_identity_hash")) != identity.identity_hash:
        raise SpeakerBreadthError("extraction summary backend identity mismatch")
    return {
        "valid": True,
        "backend": backend,
        "expected_items": len(expected),
        "successful_items": sum(row.status == "ok" for row in observations),
        "failed_items": sum(row.status != "ok" for row in observations),
    }


def _build_protocol_rows(
    selection: Mapping[str, object],
    config: Mapping[str, object],
    protocol_identity: str,
    paths: Mapping[str, Path],
) -> tuple[dict[str, list[dict[str, object]]], list[dict[str, object]], list[dict[str, object]]]:
    eligibility = _mapping(config["eligibility"], "eligibility")
    enrollment_count = int(eligibility["known_enrollment_clips"])
    calibration_count = int(eligibility["known_calibration_clips"])
    source_manifest_hash = file_sha256(paths["validated_metadata"]).upper()
    dataset_name = str(config["dataset"]["dataset_id"])
    release_logical = Path(str(config["dataset"]["release_root_logical"]))
    rows_by_kind: dict[str, list[dict[str, object]]] = {kind: [] for kind in CORE_KINDS}
    source_rows: list[dict[str, object]] = []
    speaker_rows: list[dict[str, object]] = []
    speaker_keys: set[str] = set()
    for raw_speaker, speaker_data in sorted(_mapping(selection["selected"], "selected").items()):
        value = _mapping(speaker_data, f"selected.{raw_speaker}")
        clips = list(value["clips"])
        speaker_key = _speaker_key(str(raw_speaker), protocol_identity)
        if speaker_key in speaker_keys:
            raise SpeakerBreadthError("speaker pseudonym collision")
        speaker_keys.add(speaker_key)
        role = str(value["speaker_role"])
        unknown_split = str(value["unknown_split"])
        selected_duration = 0.0
        age_category = clips[0].age_category
        for index, clip in enumerate(clips):
            if role == "known" and index < enrollment_count:
                kind, split, trial_role = "enrollment", "enrollment", "enrollment"
            elif role == "known" and index < enrollment_count + calibration_count:
                kind, split, trial_role = "calibration", "calibration", "known_probe"
            elif role == "known":
                kind, split, trial_role = "known_evaluation", "evaluation", "known_probe"
            elif unknown_split == "calibration":
                kind, split, trial_role = "calibration", "calibration", "unknown_probe"
            else:
                kind, split, trial_role = "unknown_evaluation", "evaluation", "unknown_probe"
            logical_audio = (release_logical / "prepared" / "en" / "clips" / clip.path).as_posix()
            source_recording_id = f"cvclip_{_sha256_text(clip.path)[:20]}"
            item_id = f"item_{_sha256_text('|'.join((protocol_identity, clip.path, split, trial_role)))[:24]}"
            selection_rank = _rank(protocol_identity, "clip", str(raw_speaker), clip.path)
            manifest_row = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "protocol_id": protocol_identity,
                "source_manifest_sha256": source_manifest_hash,
                "benchmark_tier": "large",
                "manifest_kind": kind,
                "protocol_split": split,
                "trial_role": trial_role,
                "protocol_condition": "clean",
                "dataset": dataset_name,
                "item_id": item_id,
                "speaker_key": speaker_key,
                "source_recording_id": source_recording_id,
                "source_utterance_id": source_recording_id,
                "audio_path_project_relative": logical_audio,
                "augmentation_policy": "none",
                "selection_rank": selection_rank,
                "enrolled_speaker": role == "known",
                "known_speaker": role == "known",
                "start_sec": 0.0,
                "end_sec": float(clip.duration_sec),
                "duration_sec": float(clip.duration_sec),
                "gender": clip.gender or None,
                "accent_group": clip.accent or None,
            }
            rows_by_kind[kind].append(manifest_row)
            selected_duration += clip.duration_sec
            source_rows.append(
                {
                    "item_id": item_id,
                    "speaker_key": speaker_key,
                    "speaker_role": role,
                    "protocol_split": split,
                    "trial_role": trial_role,
                    "age_category": clip.age_category,
                    "gender": clip.gender,
                    "accent": clip.accent,
                    "variant": clip.variant,
                    "locale": clip.locale,
                    "sentence_id": clip.sentence_id,
                    "transcript_sha256": clip.transcript_sha256,
                    "logical_audio_path": logical_audio,
                    "source_recording_id": source_recording_id,
                    "audio_sha256": clip.audio_sha256.upper(),
                    "size_bytes": clip.size_bytes,
                    "duration_sec": f"{clip.duration_sec:.6f}",
                    "sample_rate_hz": clip.sample_rate_hz,
                    "channels": clip.channels,
                    "audio_format": clip.audio_format,
                    "up_votes": clip.up_votes,
                    "down_votes": clip.down_votes,
                    "selection_rank": selection_rank,
                }
            )
        speaker_rows.append(
            {
                "speaker_key": speaker_key,
                "age_category": age_category,
                "speaker_role": role,
                "unknown_split": unknown_split,
                "available_source_clips": value["available_source_clips"],
                "available_unique_transcript_clips": value["available_unique_clips"],
                "selected_clips": len(clips),
                "selected_duration_sec": f"{selected_duration:.6f}",
            }
        )
    for rows in rows_by_kind.values():
        rows.sort(key=lambda row: (str(row["speaker_key"]), str(row["selection_rank"]), str(row["item_id"])))
    source_rows.sort(key=lambda row: str(row["item_id"]))
    speaker_rows.sort(key=lambda row: str(row["speaker_key"]))
    return rows_by_kind, source_rows, speaker_rows


def _write_protocol_manifests(
    root: Path,
    rows_by_kind: Mapping[str, Sequence[Mapping[str, object]]],
    protocol_identity: str,
    config_source: Path,
    paths: Mapping[str, Path],
) -> None:
    views = {kind: list(rows_by_kind[kind]) for kind in CORE_KINDS}
    probes = [row for kind in CORE_KINDS if kind != "enrollment" for row in rows_by_kind[kind]]
    views["clean_probes"] = [{**row, "manifest_kind": "clean_probes"} for row in probes]
    views["degraded_probes"] = []
    artifacts = {}
    for kind, filename in MANIFEST_FILENAMES.items():
        rows = sorted(views[kind], key=lambda row: (str(row["speaker_key"]), str(row["item_id"])))
        path = root / filename
        table = pa.Table.from_pylist(rows, schema=PROTOCOL_ARROW_SCHEMA)
        pq.write_table(table, path, compression="zstd", use_dictionary=False, write_statistics=True)
        artifacts[kind] = {
            "path": filename,
            "rows": len(rows),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path).upper(),
        }
    index = {
        "schema_version": "speaker-protocol-manifest-index.v1",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "authoritative_representation": "parquet",
        "hash_algorithm": "sha256",
        "protocol_id": protocol_identity,
        "benchmark_tier": "large",
        "selection_seed": 3800,
        "source_manifest": {
            "path": str(paths["validated_metadata"].name),
            "logical_path": "metadata/original/validated.tsv",
            "sha256": file_sha256(paths["validated_metadata"]).upper(),
        },
        "policy": {
            "path": config_source.relative_to(TOOL_ROOT).as_posix(),
            "sha256": file_sha256(config_source).upper(),
            "schema_version": SCHEMA_VERSION,
        },
        "artifacts": artifacts,
        "privacy": {
            "speaker_ids": "deterministic pseudonyms",
            "private_real_name_mapping_included": False,
            "raw_common_voice_client_ids_included": False,
        },
    }
    _write_json(root / "speaker_protocol_manifest.json", index)
    _write_text(
        root / "speaker_protocol_manifest.sha256",
        f"{file_sha256(root / 'speaker_protocol_manifest.json').lower()}  speaker_protocol_manifest.json\n",
    )


def _load_candidates(database_path: Path, config: Mapping[str, object]) -> list[CandidateClip]:
    included = {
        age for age, include in _mapping(config["age_mapping"], "age_mapping").items() if bool(include)
    }
    locale = str(config["dataset"]["locale"])
    minimum_duration = float(config["eligibility"]["minimum_clip_duration_sec"])
    connection = sqlite3.connect(database_path)
    try:
        values = connection.execute(
            """
            SELECT c.path, c.client_id, c.transcript, c.sentence_id, c.sentence_domain,
                   c.source_age_label, c.gender, c.accents, c.variant, c.locale,
                   c.up_votes, c.down_votes, a.audio_sha256, a.size_bytes,
                   a.duration_seconds, a.sample_rate_hz, a.channels, a.format
            FROM candidates c JOIN audio_validation a USING(path)
            WHERE c.locale = ? AND a.readable = 1 AND a.duration_seconds >= ?
            ORDER BY c.client_id, c.path
            """,
            (locale, minimum_duration),
        ).fetchall()
    finally:
        connection.close()
    result = [CandidateClip(*row) for row in values if str(row[5]) in included]
    if not result:
        raise SpeakerBreadthError("no locally validated Common Voice 60+ clips were found")
    return result


def _unique_transcript_clips(
    rows: Sequence[CandidateClip], protocol_identity: str, speaker: str
) -> list[CandidateClip]:
    by_transcript: dict[str, list[CandidateClip]] = {}
    for row in rows:
        by_transcript.setdefault(row.transcript_sha256, []).append(row)
    chosen = [
        min(values, key=lambda row: _rank(protocol_identity, "deduplicate", speaker, row.path))
        for values in by_transcript.values()
    ]
    return sorted(chosen, key=lambda row: _rank(protocol_identity, "clip-order", speaker, row.path))


def _calibration_unknown_speakers(
    unknown: set[str],
    ages: Mapping[str, str],
    fraction: float,
    protocol_identity: str,
) -> set[str]:
    target = max(1, min(len(unknown) - 1, int(round(len(unknown) * fraction))))
    selected: set[str] = set()
    reserved_evaluation: set[str] = set()
    age_groups = {
        age: sorted((speaker for speaker in unknown if ages[speaker] == age), key=lambda speaker: _rank(protocol_identity, "unknown-calibration", age, speaker))
        for age in sorted({ages[speaker] for speaker in unknown})
    }
    for speakers in age_groups.values():
        if len(speakers) == 1:
            reserved_evaluation.add(speakers[0])
        else:
            selected.add(speakers[0])
            reserved_evaluation.add(speakers[-1])
    remaining = sorted(
        unknown - selected - reserved_evaluation,
        key=lambda speaker: _rank(protocol_identity, "unknown-calibration-fill", ages[speaker], speaker),
    )
    if len(selected) > target:
        selected = set(sorted(selected, key=lambda speaker: _rank(protocol_identity, "unknown-calibration-trim", speaker))[:target])
    else:
        selected.update(remaining[: target - len(selected)])
    return selected


def _dataset_audit(
    paths: Mapping[str, Path],
    candidates: Sequence[CandidateClip],
    config: Mapping[str, object],
) -> dict[str, object]:
    connection = sqlite3.connect(paths["state_database"])
    try:
        metadata_rows = {
            str(bucket) + ".tsv": int(count)
            for bucket, count in connection.execute(
                "SELECT bucket, COUNT(*) FROM bucket_rows GROUP BY bucket"
            )
        }
        metadata_rows.update(
            {
                str(split) + ".tsv": int(count)
                for split, count in connection.execute(
                    "SELECT split, COUNT(*) FROM upstream GROUP BY split"
                )
            }
        )
        metadata_rows["clip_durations.tsv"] = int(connection.execute("SELECT COUNT(*) FROM durations").fetchone()[0])
        metadata_rows["reported.tsv"] = int(connection.execute("SELECT COUNT(*) FROM reported").fetchone()[0])
        total_speakers, total_clips = connection.execute(
            "SELECT COUNT(DISTINCT NULLIF(client_id, '')), COUNT(*) FROM bucket_rows"
        ).fetchone()
        duplicate_clips = int(
            connection.execute(
                "SELECT COUNT(*) FROM (SELECT path FROM bucket_rows GROUP BY path HAVING COUNT(*) > 1)"
            ).fetchone()[0]
        )
        age_rows = [
            {"age_category": age or "unspecified", "clips": int(clips), "speakers": int(speakers)}
            for age, clips, speakers in connection.execute(
                "SELECT age, COUNT(*), COUNT(DISTINCT NULLIF(client_id, '')) FROM bucket_rows GROUP BY age ORDER BY age"
            )
        ]
    finally:
        connection.close()
    for name in ("validated_sentences.tsv", "unvalidated_sentences.tsv"):
        metadata_rows[name] = _count_tsv_rows(paths["metadata_root"] / name)
    metadata_files = []
    for path in sorted(paths["metadata_root"].iterdir(), key=lambda value: value.name):
        if path.is_file():
            metadata_files.append(
                {
                    "name": path.name,
                    "rows": metadata_rows.get(path.name),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path).upper(),
                }
            )
    selected_ages = sorted({row.age_category for row in candidates})
    age_mapping = [
        {"observed_category": key, "include_in_60plus": bool(value)}
        for key, value in sorted(_mapping(config["age_mapping"], "age_mapping").items())
    ]
    clip_paths = [row.path for row in candidates]
    return {
        "schema_version": "commonvoice-local-audit.v1",
        "release_id": config["dataset"]["release_id"],
        "locale_selected": config["dataset"]["locale"],
        "metadata_root_logical": str(config["dataset"]["release_root_logical"]) + "/prepared/en/metadata/original",
        "audio_root_logical": str(config["dataset"]["release_root_logical"]) + "/prepared/en/clips",
        "metadata_files": metadata_files,
        "metadata_schema": list(config["dataset"]["required_columns"]),
        "whole_release_metadata_rows": int(total_clips),
        "whole_release_unique_speakers": int(total_speakers),
        "whole_release_unique_clip_paths": int(total_clips) - duplicate_clips,
        "whole_release_duplicate_clip_paths": duplicate_clips,
        "age_inventory": age_rows,
        "age_mapping": age_mapping,
        "selected_60plus_categories": selected_ages,
        "validated_60plus_clips": len(candidates),
        "validated_60plus_unique_clips": len(set(clip_paths)),
        "validated_60plus_unique_speakers": len({row.source_speaker_id for row in candidates}),
        "validated_60plus_duplicate_metadata_rows": 0,
        "validated_60plus_duplicate_clips": len(clip_paths) - len(set(clip_paths)),
        "materialized_audio_files": len(candidates),
        "missing_materialized_audio_files": sum(
            not (paths["audio_root"] / row.path).is_file() for row in candidates
        ),
        "audio_format": sorted({row.audio_format for row in candidates}),
        "duration": _statistics([row.duration_sec for row in candidates]),
    }


def _validate_selected_audio(
    source_rows: Sequence[Mapping[str, object]], config: Mapping[str, object]
) -> list[dict[str, object]]:
    minimum = float(config["eligibility"]["minimum_clip_duration_sec"])

    def inspect(row: Mapping[str, object]) -> dict[str, object]:
        path = resolve_data_path_from_logical(str(row["logical_audio_path"]))
        if not path.is_file():
            raise SpeakerBreadthError(f"selected audio is missing: {path}")
        digest = file_sha256(path).upper()
        if digest != str(row["audio_sha256"]).upper():
            raise SpeakerBreadthError(f"selected audio hash changed: {path}")
        audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        if not audio.size or not np.isfinite(audio).all():
            raise SpeakerBreadthError(f"selected audio is empty or non-finite: {path}")
        info = sf.info(path)
        duration = float(info.duration)
        if duration <= 0 or duration < minimum:
            raise SpeakerBreadthError(f"selected audio violates Stage 10 duration floor: {path}")
        if int(info.channels) != audio.shape[1] or int(info.samplerate) != int(sample_rate):
            raise SpeakerBreadthError(f"selected audio decode metadata mismatch: {path}")
        return {
            "item_id": row["item_id"],
            "logical_audio_path": row["logical_audio_path"],
            "audio_sha256": digest,
            "decoded_finite": True,
            "duration_sec": f"{duration:.6f}",
            "sample_rate_hz": int(sample_rate),
            "channels": int(info.channels),
            "frames": int(info.frames),
            "format": str(info.format),
        }

    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as executor:
        return sorted(executor.map(inspect, source_rows), key=lambda row: str(row["item_id"]))


def _breadth_leakage(
    rows_by_kind: Mapping[str, Sequence[Mapping[str, object]]],
    source_rows: Sequence[Mapping[str, object]],
    *,
    data_paths_exist: bool,
) -> dict[str, object]:
    core = {kind: list(rows_by_kind[kind]) for kind in CORE_KINDS}
    stage10 = stage10_leakage_report(core)
    known = {
        str(row["speaker_key"])
        for kind in ("enrollment", "calibration", "known_evaluation")
        for row in core[kind]
        if row["trial_role"] in {"enrollment", "known_probe"}
    }
    unknown = {
        str(row["speaker_key"])
        for kind in ("calibration", "unknown_evaluation")
        for row in core[kind]
        if row["trial_role"] == "unknown_probe"
    }
    calibration_unknown = {
        str(row["speaker_key"])
        for row in core["calibration"]
        if row["trial_role"] == "unknown_probe"
    }
    evaluation_unknown = {str(row["speaker_key"]) for row in core["unknown_evaluation"]}
    paths_by_split: dict[str, set[str]] = {}
    transcript_splits: dict[tuple[str, str], set[str]] = {}
    global_transcript_splits: dict[str, set[str]] = {}
    speaker_ages: dict[str, set[str]] = {}
    for row in source_rows:
        split = str(row["protocol_split"])
        paths_by_split.setdefault(split, set()).add(str(row["logical_audio_path"]))
        transcript = str(row["transcript_sha256"])
        speaker = str(row["speaker_key"])
        transcript_splits.setdefault((speaker, transcript), set()).add(split)
        global_transcript_splits.setdefault(transcript, set()).add(split)
        speaker_ages.setdefault(speaker, set()).add(str(row["age_category"]))
    all_paths = [str(row["logical_audio_path"]) for row in source_rows]
    all_items = [str(row["item_id"]) for row in source_rows]
    result: dict[str, object] = {
        **stage10,
        "source_audio_unique_across_all_roles": len(all_paths) == len(set(all_paths)),
        "item_ids_unique": len(all_items) == len(set(all_items)),
        "known_unknown_speakers_disjoint": not bool(known & unknown),
        "unknown_speakers_never_enrolled": not bool(unknown & {str(row["speaker_key"]) for row in core["enrollment"]}),
        "calibration_evaluation_unknown_speakers_disjoint": not bool(calibration_unknown & evaluation_unknown),
        "speaker_age_mapping_consistent": all(len(ages) == 1 for ages in speaker_ages.values()),
        "selected_paths_exist": data_paths_exist,
        "same_speaker_transcript_cross_split_count": sum(len(splits) > 1 for splits in transcript_splits.values()),
        "global_transcript_cross_split_count": sum(len(splits) > 1 for splits in global_transcript_splits.values()),
    }
    required = [
        value
        for key, value in result.items()
        if isinstance(value, bool) and key != "private_identity_mapping_absent"
    ]
    result["all_required_checks_passed"] = all(required) and bool(result["private_identity_mapping_absent"])
    return result


def _metadata_coverage(source_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    speaker_count = len({str(row["speaker_key"]) for row in source_rows})
    result = []
    for field in ("age_category", "gender", "accent", "variant", "locale"):
        nonmissing = [row for row in source_rows if str(row[field]).strip()]
        speakers = {str(row["speaker_key"]) for row in nonmissing}
        categories = sorted({str(row[field]) for row in nonmissing})
        result.append(
            {
                "field": field,
                "non_missing_rows": len(nonmissing),
                "total_rows": len(source_rows),
                "row_coverage_percent": f"{100 * len(nonmissing) / len(source_rows):.3f}",
                "non_missing_speakers": len(speakers),
                "total_speakers": speaker_count,
                "speaker_coverage_percent": f"{100 * len(speakers) / speaker_count:.3f}",
                "observed_categories_json": json.dumps(categories, ensure_ascii=False, separators=(",", ":")),
            }
        )
    return result


def _duration_report(
    source_rows: Sequence[Mapping[str, object]], config: Mapping[str, object]
) -> dict[str, object]:
    groups: dict[str, list[float]] = {}
    per_speaker: dict[str, float] = {}
    for row in source_rows:
        value = float(row["duration_sec"])
        groups.setdefault(str(row["protocol_split"]), []).append(value)
        per_speaker[str(row["speaker_key"])] = per_speaker.get(str(row["speaker_key"]), 0.0) + value
    values = [float(row["duration_sec"]) for row in source_rows]
    short_floor = float(config["eligibility"]["minimum_clip_duration_sec"])
    long_flag = float(config["duration_diagnostics"]["unusually_long_sec"])
    return {
        "schema_version": "speaker-breadth-duration-report.v1",
        "all_selected_clips": _statistics(values),
        "by_protocol_split": {key: _statistics(group) for key, group in sorted(groups.items())},
        "per_speaker_total": _statistics(list(per_speaker.values())),
        "stage10_minimum_duration_sec": short_floor,
        "below_stage10_minimum_count": sum(value < short_floor for value in values),
        "unusually_long_threshold_sec": long_flag,
        "unusually_long_count": sum(value > long_flag for value in values),
    }


def _protocol_summary(
    selection: Mapping[str, object],
    source_rows: Sequence[Mapping[str, object]],
    speakers: Sequence[Mapping[str, object]],
    durations: Mapping[str, object],
    protocol_identity: str,
) -> dict[str, object]:
    age_categories: dict[str, dict[str, int]] = {}
    for row in speakers:
        age = str(row["age_category"])
        role = str(row["speaker_role"])
        group = age_categories.setdefault(age, {"known": 0, "calibration_unknown": 0, "evaluation_unknown": 0, "total": 0})
        if role == "known":
            group["known"] += 1
        elif row["unknown_split"] == "calibration":
            group["calibration_unknown"] += 1
        else:
            group["evaluation_unknown"] += 1
        group["total"] += 1
    split_counts = {split: sum(str(row["protocol_split"]) == split for row in source_rows) for split in ("enrollment", "calibration", "evaluation")}
    return {
        "schema_version": "speaker-breadth-protocol-summary.v1",
        "protocol_id": protocol_identity,
        "selection_seed": 3800,
        "model_independent_manifest": True,
        "eligibility": {
            "known_candidates": selection["eligible_known_speakers"],
            "unknown_candidates": selection["eligible_unknown_speakers"],
            "known_candidates_with_five_clip_reserve": selection["eligible_known_with_reserve"],
            "unknown_candidates_with_five_clip_reserve": selection["eligible_unknown_with_reserve"],
            "known_minimum_clips": 30,
            "unknown_minimum_clips": 25,
            "unique_transcript_clip_distribution": selection["unique_transcript_clip_distribution"],
        },
        "speakers": {
            "known": len(selection["known_speakers"]),
            "calibration_unknown": len(selection["calibration_unknown_speakers"]),
            "evaluation_unknown": len(selection["evaluation_unknown_speakers"]),
            "total": len(speakers),
        },
        "clips": {**split_counts, "total": len(source_rows)},
        "duration": {
            "total_seconds": durations["all_selected_clips"]["total"],
            "total_hours": float(durations["all_selected_clips"]["total"]) / 3600.0,
        },
        "age_categories": age_categories,
    }


def _provenance(
    config_source: Path,
    paths: Mapping[str, Path],
    config: Mapping[str, object],
    audit: Mapping[str, object],
    summary: Mapping[str, object],
    protocol_identity: str,
) -> dict[str, object]:
    state = _read_json(paths["materialization_state"])
    return {
        "schema_version": "speaker-breadth-dataset-provenance.v1",
        "protocol_id": protocol_identity,
        "repository_git_sha_at_prepare": _git_sha(),
        "common_voice_root_logical": config["dataset"]["release_root_logical"],
        "common_voice_release": config["dataset"]["release_id"],
        "locale": config["dataset"]["locale"],
        "metadata_source_logical": str(config["dataset"]["release_root_logical"]) + "/prepared/en/metadata/original/validated.tsv",
        "metadata_source_sha256": file_sha256(paths["validated_metadata"]).upper(),
        "metadata_file_hashes": state["metadata_file_hashes"],
        "source_archive_sha256": state["source_archive_sha256"],
        "selected_materialization_membership_sha256": state["candidate_membership_list_sha256"],
        "selection_config_path": config_source.relative_to(TOOL_ROOT).as_posix(),
        "selection_config_sha256": file_sha256(config_source).upper(),
        "selection_seed": 3800,
        "selection_algorithm_version": SELECTION_ALGORITHM_VERSION,
        "candidate_60plus_speakers": audit["validated_60plus_unique_speakers"],
        "eligible_known_speakers": summary["eligibility"]["known_candidates"],
        "eligible_unknown_speakers": summary["eligibility"]["unknown_candidates"],
        "selected_speakers": summary["speakers"],
        "selected_clips": summary["clips"]["total"],
        "selected_audio_duration_seconds": summary["duration"]["total_seconds"],
        "age_category_counts": summary["age_categories"],
        "raw_common_voice_client_ids_published": False,
    }


def _source_paths(release_root: Path, config: Mapping[str, object]) -> dict[str, Path]:
    prepared = release_root / "prepared" / "en"
    return {
        "release_root": release_root,
        "metadata_root": prepared / "metadata" / "original",
        "validated_metadata": prepared / "metadata" / "original" / str(config["dataset"]["canonical_metadata"]),
        "audio_root": prepared / "clips",
        "state_database": prepared / "state" / str(config["dataset"]["state_database"]),
        "materialization_state": prepared / "state" / "materialization_complete.json",
    }


def _validate_source_identity(paths: Mapping[str, Path], config: Mapping[str, object]) -> None:
    for name, path in paths.items():
        if name != "release_root" and not path.exists():
            raise SpeakerBreadthError(f"Common Voice source artifact is missing: {path}")
    state = _read_json(paths["materialization_state"])
    if state.get("completion_state") != "complete":
        raise SpeakerBreadthError("Common Voice selective materialization is incomplete")
    if state.get("release_id") != config["dataset"]["release_id"]:
        raise SpeakerBreadthError("Common Voice release identity does not match configuration")
    expected = str(state["metadata_file_hashes"][str(config["dataset"]["canonical_metadata"])]).upper()
    if file_sha256(paths["validated_metadata"]).upper() != expected:
        raise SpeakerBreadthError("Common Voice canonical metadata hash changed")


def _protocol_identity(
    config_source: Path, paths: Mapping[str, Path], config: Mapping[str, object]
) -> str:
    state = _read_json(paths["materialization_state"])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "algorithm": SELECTION_ALGORITHM_VERSION,
        "release_id": config["dataset"]["release_id"],
        "metadata_sha256": file_sha256(paths["validated_metadata"]).upper(),
        "membership_sha256": state["candidate_membership_list_sha256"],
        "config_sha256": file_sha256(config_source).upper(),
        "seed": 3800,
    }
    return f"commonvoice_60plus_v1_{_sha256_text(json.dumps(payload, sort_keys=True, separators=(',', ':')))[:12]}"


def _load_config(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise SpeakerBreadthError("unsupported Common Voice breadth configuration")
    if payload.get("selection_seed") != 3800:
        raise SpeakerBreadthError("Common Voice breadth selection seed must be 3800")
    eligibility = _mapping(payload.get("eligibility"), "eligibility")
    if sum(int(eligibility[key]) for key in ("known_enrollment_clips", "known_calibration_clips", "known_evaluation_clips")) != int(eligibility["known_total_clips"]):
        raise SpeakerBreadthError("known clip allocation does not sum to the required total")
    if int(eligibility["known_total_clips"]) != 30 or int(eligibility["unknown_total_clips"]) != 25:
        raise SpeakerBreadthError("breadth v1 must preserve Stage 10 Large clip minima")
    return {str(key): value for key, value in payload.items()}


def _write_file_index(root: Path) -> None:
    excluded = {"protocol_files.json", "protocol_files.sha256"}
    entries = {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path).upper(),
        }
        for path in sorted(root.rglob("*"), key=lambda value: value.as_posix())
        if path.is_file() and path.name not in excluded
    }
    _write_json(
        root / "protocol_files.json",
        {
            "schema_version": "speaker-breadth-file-index.v1",
            "hash_algorithm": "sha256",
            "entries": entries,
        },
    )
    _write_text(
        root / "protocol_files.sha256",
        f"{file_sha256(root / 'protocol_files.json').lower()}  protocol_files.json\n",
    )


def _validate_file_index(root: Path) -> None:
    index_path = root / "protocol_files.json"
    index = _read_json(index_path)
    if index.get("schema_version") != "speaker-breadth-file-index.v1":
        raise SpeakerBreadthError("protocol file index version mismatch")
    checksum_line = (root / "protocol_files.sha256").read_text(encoding="utf-8").strip()
    if checksum_line.split()[0].upper() != file_sha256(index_path).upper():
        raise SpeakerBreadthError("protocol file index checksum changed")
    for relative, raw in _mapping(index.get("entries"), "entries").items():
        row = _mapping(raw, f"entries.{relative}")
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(row["bytes"]) or file_sha256(path).upper() != str(row["sha256"]).upper():
            raise SpeakerBreadthError(f"frozen protocol artifact changed: {relative}")


def _package_readme(summary: Mapping[str, object], config: Mapping[str, object]) -> str:
    speakers = summary["speakers"]
    clips = summary["clips"]
    return f"""# Common Voice 60+ speaker breadth v1

This is a frozen, model-independent source protocol for breadth confirmation of Stage 10 speaker-recognition finalists. It changes the source population and audio only; Stage 10 enrollment, cosine scoring, backend-specific calibration, identification, Unknown rejection, and bootstrap methodology remain unchanged.

## Inputs

- Logical data root: `{config['dataset']['release_root_logical']}` under `JP_DATA_ROOT`.
- Canonical metadata: `prepared/en/metadata/original/validated.tsv`.
- Locale: `{config['dataset']['locale']}`.
- Included self-reported age categories: `sixties`, `seventies`, `eighties`, `nineties`.
- Selection seed: `3800`.

## Frozen design

- Known speakers: {speakers['known']} (5 enrollment, 10 calibration, 15 evaluation clips each).
- Calibration Unknown speakers: {speakers['calibration_unknown']} (25 clips each).
- Evaluation Unknown speakers: {speakers['evaluation_unknown']} (25 clips each).
- Enrollment clips: {clips['enrollment']}.
- Calibration probes: {clips['calibration']}.
- Evaluation probes: {clips['evaluation']}.
- Total clips: {clips['total']}.

All selected source clips and within-speaker transcripts are unique. Raw Common Voice client IDs are never published. `source_selection.tsv` joins every Stage 10 `item_id` to age and optional metadata diagnostics.

## Run from Anaconda Prompt or PowerShell

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\\Evaluation Tool\\scripts\\run_speaker_breadth_commonvoice.ps1" -Action Plan -Backends @("PLACEHOLDER_FINALIST_1")
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\\Evaluation Tool\\scripts\\run_speaker_breadth_commonvoice.ps1" -Action Validate
```

Run only after Stage 10 finalist selection. Pass the chosen backends at runtime; the wrapper selects each backend's qualified environment and runs them sequentially. Use `-Action Collect` afterward for the compact analysis package.

## Outputs

The Parquet files are consumed unchanged by `speaker-protocol extract`, `evaluate`, and `validate`. TSV/JSON files contain selection, speaker inventory, age/covariate coverage, durations, source provenance, decoded-audio validation, and leakage evidence. Raw audio and model assets are not included.

This package is frozen. Do not regenerate it in place; use a new protocol version for a result-affecting change.
"""


def _statistics(values: Sequence[float]) -> dict[str, object]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"count": 0, "total": 0.0, "minimum": None, "p05": None, "median": None, "p95": None, "maximum": None, "mean": None}
    return {
        "count": len(ordered),
        "total": sum(ordered),
        "minimum": ordered[0],
        "p05": _quantile(ordered, 0.05),
        "median": _quantile(ordered, 0.5),
        "p95": _quantile(ordered, 0.95),
        "maximum": ordered[-1],
        "mean": sum(ordered) / len(ordered),
    }


def _clip_count_distribution(values: Sequence[int]) -> dict[str, int]:
    bins = {
        "00-04": 0,
        "05-09": 0,
        "10-24": 0,
        "25-29": 0,
        "30-34": 0,
        "35-49": 0,
        "50-99": 0,
        "100+": 0,
    }
    for value in values:
        if value < 5:
            key = "00-04"
        elif value < 10:
            key = "05-09"
        elif value < 25:
            key = "10-24"
        elif value < 30:
            key = "25-29"
        elif value < 35:
            key = "30-34"
        elif value < 50:
            key = "35-49"
        elif value < 100:
            key = "50-99"
        else:
            key = "100+"
        bins[key] += 1
    return bins


def _quantile(values: Sequence[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def _count_tsv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return sum(1 for _ in csv.reader(stream, delimiter="\t")) - 1


def _speaker_key(source_speaker_id: str, protocol_identity: str) -> str:
    return f"spk_cv60p_{_sha256_text('|'.join((protocol_identity, source_speaker_id, '3800')))[:20]}"


def _rank(protocol_identity: str, *values: str) -> str:
    return _sha256_text("|".join((protocol_identity, *values)))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=TOOL_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SpeakerBreadthError(f"{name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, path.name)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream, delimiter="\t")]


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def _write_tsv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise SpeakerBreadthError(f"refusing to write empty TSV: {path.name}")
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
