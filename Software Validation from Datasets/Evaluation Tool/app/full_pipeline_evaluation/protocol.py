"""Deterministic, additive ``full_speech_pipeline_v1`` protocol builder.

The builder never downloads data, copies audio, loads a model, or runs inference.
It binds existing frozen source manifests by SHA-256, creates exact controlled
speaker-attributed references, and keeps component-only diagnostics explicit.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    installed_tool_path_candidates,
    read_json,
    sha256_file,
    write_json_atomic,
    write_jsonl_atomic,
)
from app.utils.paths import resolve_data_path_from_logical


CONFIG_SCHEMA_VERSION = "full-speech-pipeline-config.v1"
PROTOCOL_SCHEMA_VERSION = "full-speech-pipeline.v1"
PROTOCOL_BUILDER_ID = "full-speech-pipeline-builder.v2"
CASE_SCHEMA_VERSION = "full-speech-pipeline-case.v1"
REFERENCE_SCHEMA_VERSION = "full-speech-pipeline-reference.v1"
OVERLAY_SCHEMA_VERSION = "full-speech-pipeline-identity-overlay.v1"
ENROLLMENT_SCHEMA_VERSION = "full-speech-pipeline-enrollment-reference.v1"
AUDIT_SCHEMA_VERSION = "full-speech-pipeline-source-audit.v1"
VALIDATION_SCHEMA_VERSION = "full-speech-pipeline-validation.v1"
PLAN_SCHEMA_VERSION = "full-speech-pipeline-plan.v1"
PREFLIGHT_SCHEMA_VERSION = "full-speech-pipeline-case-contract-preflight.v1"

TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = TOOL_ROOT / "configs/automated_evaluation/full_speech_pipeline_v1.yaml"
DEFAULT_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks/full_pipeline/full_speech_pipeline_v1"


class ProtocolError(ValueError):
    """The installed source state cannot support the declared protocol."""


def audit_sources(
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    *,
    preflight_case_contracts: bool = True,
) -> dict[str, object]:
    """Hash-audit every frozen input without preparing protocol artifacts."""

    config_path = _absolute_config_path(config_path)
    config = _load_config(config_path)
    config_sha256 = sha256_file(config_path).upper()
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, object]] = []

    for source in config["sources"]:
        source_errors: list[str] = []
        identities: dict[str, str] = {}
        for identity in source.get("identity_files", []):
            path = _tool_path(identity["path"])
            if not path.is_file():
                source_errors.append(f"missing frozen identity file: {identity['path']}")
                continue
            actual = sha256_file(path).upper()
            expected = str(identity["sha256"]).upper()
            identities[str(identity["path"])] = actual
            if actual != expected:
                source_errors.append(
                    f"frozen identity mismatch: {identity['path']} expected {expected}, got {actual}"
                )
        rows.append(
            {
                "source_key": str(source["source_key"]),
                "kind": str(source["kind"]),
                "protocol_id": str(source["source_protocol_id"]),
                "root": str(source.get("source_root") or source.get("manifest") or ""),
                "identity_files": [str(item["path"]) for item in source.get("identity_files", [])],
                "identity_sha256s": identities,
                "supported_views": list(source.get("supported_views", [])),
                "unsupported_views": list(source.get("unsupported_views", [])),
                "installed": not source_errors,
                "errors": source_errors,
            }
        )
        errors.extend(f"{source['source_key']}: {value}" for value in source_errors)

    transcript = config["transcript_source"]
    transcript_path = _transcript_path(transcript)
    transcript_installed = transcript_path.is_file()
    transcript_actual = sha256_file(transcript_path).upper() if transcript_installed else None
    transcript_expected = str(transcript["sha256"]).upper()
    transcript_errors: list[str] = []
    if not transcript_installed:
        transcript_errors.append(f"missing transcript source: {transcript_path}")
    elif transcript_actual != transcript_expected:
        transcript_errors.append(
            f"transcript source mismatch: expected {transcript_expected}, got {transcript_actual}"
        )
    rows.append(
        {
            "source_key": "commonvoice_transcript_source",
            "kind": "exact_source_transcript",
            "protocol_id": "commonvoice_validated_tsv_368ead1ab9d7",
            "root": str(transcript.get("logical_path") or transcript_path),
            "identity_files": [str(transcript.get("logical_path") or transcript_path)],
            "identity_sha256s": {
                str(transcript.get("logical_path") or transcript_path): transcript_actual
            },
            "supported_views": ["exact_source_transcript"],
            "unsupported_views": [],
            "installed": not transcript_errors,
            "errors": transcript_errors,
        }
    )
    errors.extend(transcript_errors)

    source_preflight = (
        _preflight_declared_sources(config) if preflight_case_contracts and not errors else None
    )
    if source_preflight is not None and not source_preflight["valid"]:
        errors.extend(str(value) for value in source_preflight["errors"])
    identity_payload = _protocol_identity_payload(config, config_sha256, rows)
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "config_id": _protocol_id(identity_payload),
        "config_sha256": config_sha256,
        "sources": rows,
        "errors": errors,
        "warnings": warnings,
        "case_contract_preflight": source_preflight,
        "downloads_attempted": False,
        "inference_started": False,
    }


def prepare_protocol(
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    protocol_root: Path | str = DEFAULT_PROTOCOL_ROOT,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    """Prepare deterministic manifests and references from installed frozen inputs."""

    config_path = _absolute_config_path(config_path)
    protocol_root = Path(protocol_root).resolve()
    config = _load_config(config_path)
    audit = audit_sources(config_path, preflight_case_contracts=False)
    if audit["errors"]:
        raise ProtocolError("source audit failed: " + "; ".join(audit["errors"]))

    existing_summary = protocol_root / "protocol_summary.json"
    if existing_summary.is_file() and not overwrite:
        validation = validate_protocol(protocol_root, config_path=config_path)
        if validation["valid"] and validation["protocol_id"] == audit["config_id"]:
            summary = read_json(existing_summary)
            return _prepare_result(summary, protocol_root, status="UNCHANGED")
        raise ProtocolError(
            f"protocol root already exists but is not the requested valid identity: {protocol_root}"
        )

    protocol_root.mkdir(parents=True, exist_ok=True)
    protocol_id = str(audit["config_id"])
    transcript_lookup = _load_transcript_lookup(config["transcript_source"])
    cases: dict[str, list[dict[str, object]]] = {"development": [], "evaluation": []}
    references: dict[str, list[dict[str, object]]] = {"development": [], "evaluation": []}
    overlays: dict[str, list[dict[str, object]]] = {"development": [], "evaluation": []}
    enrollment: dict[str, dict[str, dict[str, object]]] = {
        "development": {},
        "evaluation": {},
    }

    for source in config["sources"]:
        kind = source["kind"]
        if kind == "controlled_primary":
            _prepare_controlled_source(
                source,
                protocol_id=protocol_id,
                transcript_lookup=transcript_lookup,
                cases=cases,
                references=references,
                overlays=overlays,
                enrollment=enrollment,
            )
        elif kind in {
            "native_diagnostic",
            "standard_asr_diagnostic",
            "commonvoice_asr_diagnostic",
        }:
            cases[str(source["partition"])].extend(
                _diagnostic_cases(source, protocol_id=protocol_id)
            )
        else:
            raise ProtocolError(f"unknown source kind {kind!r}")

    for split in cases:
        cases[split].sort(key=lambda row: str(row["protocol_case_id"]))
        references[split].sort(key=lambda row: str(row["source_reference_id"]))
        overlays[split].sort(key=lambda row: str(row["identity_overlay_ref"]))
        enrollment_rows = sorted(
            enrollment[split].values(), key=lambda row: str(row["enrolled_id"])
        )
        split_root = protocol_root / split
        write_jsonl_atomic(split_root / "case_manifest.jsonl", cases[split])
        write_jsonl_atomic(
            split_root / "references/speaker_attributed_transcript.jsonl",
            references[split],
        )
        write_jsonl_atomic(split_root / "identity/identity_overlays.jsonl", overlays[split])
        write_jsonl_atomic(split_root / "enrollment/enrollment_registry.jsonl", enrollment_rows)

    primary_speakers = {
        split: sorted(
            {
                str(speaker)
                for case in cases[split]
                if case["measurement_mode"] == "controlled_end_to_end"
                for speaker in case["global_speaker_ids"]
            }
        )
        for split in cases
    }
    overlap = set(primary_speakers["development"]) & set(primary_speakers["evaluation"])
    if overlap:
        raise ProtocolError(
            f"primary development/evaluation speakers overlap: {sorted(overlap)[:5]}"
        )
    enrollment_speakers = {
        split: {
            str(row["global_speaker_id"]) for row in enrollment[split].values()
        }
        for split in enrollment
    }
    enrollment_overlap = (
        enrollment_speakers["development"] & enrollment_speakers["evaluation"]
    )
    if enrollment_overlap:
        raise ProtocolError(
            "development/evaluation enrollment-gallery speakers overlap: "
            f"{sorted(enrollment_overlap)[:5]}"
        )

    case_counts = {split: len(rows) for split, rows in cases.items()}
    duration = {
        split: round(sum(float(row["duration_sec"]) for row in rows), 9)
        for split, rows in cases.items()
    }
    source_protocol_ids = {
        str(source["source_key"]): str(source["source_protocol_id"])
        for source in config["sources"]
    }
    split_identities = {
        split: _split_identity(protocol_id, split, cases[split]) for split in cases
    }
    unsupported = {
        str(source["source_key"]): list(source.get("unsupported_views", []))
        for source in config["sources"]
        if source.get("unsupported_views")
    }
    summary = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "protocol_id": protocol_id,
        "protocol_name": str(config["protocol_name"]),
        "protocol_version": int(config["protocol_version"]),
        "protocol_builder_id": PROTOCOL_BUILDER_ID,
        "selection_seed": int(config["selection_seed"]),
        "config_path": _relative_tool_path(config_path),
        "config_sha256": str(audit["config_sha256"]),
        "development_identity": split_identities["development"],
        "evaluation_identity": split_identities["evaluation"],
        "case_counts": case_counts,
        "audio_duration_sec": duration,
        "primary_speaker_counts": {
            split: len(values) for split, values in primary_speakers.items()
        },
        "primary_development_evaluation_speaker_disjoint": True,
        "development_evaluation_enrollment_gallery_speaker_disjoint": True,
        "source_protocol_ids": source_protocol_ids,
        "unsupported": unsupported,
        "evaluation_only": True,
        "training_eligible": False,
        "audio_copied_or_modified": False,
        "downloads_attempted": False,
        "inference_started": False,
    }
    write_json_atomic(protocol_root / "source_audit.json", audit)
    write_json_atomic(protocol_root / "protocol_summary.json", summary)
    checksums = checksum_map(protocol_root, exclude=("checksums.json",))
    write_json_atomic(
        protocol_root / "checksums.json",
        {
            "schema_version": "full-speech-pipeline-checksums.v1",
            "protocol_id": protocol_id,
            "files": checksums,
        },
    )

    validation = validate_protocol(protocol_root, config_path=config_path)
    if not validation["valid"]:
        raise ProtocolError("prepared protocol did not validate: " + "; ".join(validation["errors"]))
    return _prepare_result(summary, protocol_root, status="PREPARED")


def validate_protocol(
    protocol_root: Path | str = DEFAULT_PROTOCOL_ROOT,
    *,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    verify_audio: bool = False,
) -> dict[str, object]:
    """Validate generated identities, hashes, split science, and reference links."""

    protocol_root = Path(protocol_root).resolve()
    config_path = _absolute_config_path(config_path)
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    summary_path = protocol_root / "protocol_summary.json"
    checksums_path = protocol_root / "checksums.json"
    if not summary_path.is_file() or not checksums_path.is_file():
        missing = [str(path) for path in (summary_path, checksums_path) if not path.is_file()]
        errors.append("missing prepared protocol files: " + ", ".join(missing))
        return _validation_result(None, {}, {}, checks, errors, warnings)

    summary = read_json(summary_path)
    checksum_document = read_json(checksums_path)
    expected_files = checksum_document.get("files")
    if not isinstance(expected_files, dict):
        errors.append("checksums.json files must be an object")
        expected_files = {}
    actual_files = checksum_map(protocol_root, exclude=("checksums.json",))
    checks["generated_file_hashes_match"] = actual_files == expected_files
    if not checks["generated_file_hashes_match"]:
        errors.append("generated file checksums differ")

    audit = audit_sources(config_path, preflight_case_contracts=False)
    checks["frozen_sources_match"] = not bool(audit["errors"])
    if audit["errors"]:
        errors.extend(str(value) for value in audit["errors"])
    checks["protocol_identity_matches_sources"] = summary.get("protocol_id") == audit["config_id"]
    if not checks["protocol_identity_matches_sources"]:
        errors.append("protocol identity does not match config and frozen source identities")

    cases_by_split: dict[str, list[dict[str, object]]] = {}
    primary_speakers: dict[str, set[str]] = {}
    enrollment_speakers: dict[str, set[str]] = {}
    for split in ("development", "evaluation"):
        cases = list(_read_jsonl(protocol_root / split / "case_manifest.jsonl"))
        refs = {
            str(row["source_reference_id"]): row
            for row in _read_jsonl(
                protocol_root / split / "references/speaker_attributed_transcript.jsonl"
            )
        }
        overlay_rows = {
            str(row["identity_overlay_ref"]): row
            for row in _read_jsonl(protocol_root / split / "identity/identity_overlays.jsonl")
        }
        enrollment_rows = {
            str(row["enrolled_id"]): row
            for row in _read_jsonl(protocol_root / split / "enrollment/enrollment_registry.jsonl")
        }
        enrollment_speakers[split] = {
            str(row["global_speaker_id"]) for row in enrollment_rows.values()
        }
        cases_by_split[split] = cases
        case_ids = [str(row.get("protocol_case_id")) for row in cases]
        if case_ids != sorted(case_ids) or len(case_ids) != len(set(case_ids)):
            errors.append(f"{split} case IDs are not sorted and unique")
        for case in cases:
            if case.get("schema_version") != CASE_SCHEMA_VERSION:
                errors.append(f"invalid case schema: {case.get('protocol_case_id')}")
            if case.get("protocol_id") != summary.get("protocol_id"):
                errors.append(f"case protocol identity differs: {case.get('protocol_case_id')}")
            if case.get("partition") != split:
                errors.append(f"case partition differs: {case.get('protocol_case_id')}")
            if case.get("measurement_mode") == "controlled_end_to_end":
                ref_id = str(case.get("source_reference_id"))
                overlay_id = str(case.get("identity_overlay_ref"))
                if ref_id not in refs:
                    errors.append(f"case references missing transcript {ref_id}")
                    continue
                if overlay_id not in overlay_rows:
                    errors.append(f"case references missing identity overlay {overlay_id}")
                    continue
                overlay = overlay_rows[overlay_id]
                gallery_ids = {str(value) for value in case.get("gallery_enrolled_ids", [])}
                if int(case.get("gallery_size", -1)) != len(gallery_ids):
                    errors.append(f"gallery size differs: {case.get('protocol_case_id')}")
                if not gallery_ids <= set(enrollment_rows):
                    errors.append(f"gallery references absent enrollment: {case.get('protocol_case_id')}")
                mixture_ids = {
                    str(segment["source_clip_id"])
                    for segment in refs[ref_id].get("segments", [])
                }
                enrolled_ids = {
                    clip_id
                    for record in overlay.get("enrollment_database", [])
                    for clip_id in record.get("reserved_source_clip_ids", [])
                }
                if mixture_ids & enrolled_ids:
                    errors.append(f"enrollment/mixture overlap: {case.get('protocol_case_id')}")
                for segment in refs[ref_id].get("segments", []):
                    sample_rate = int(case["sample_rate_hz"])
                    start_delta = abs(
                        float(segment["start_sec"])
                        - int(segment["start_sample"]) / sample_rate
                    )
                    end_delta = abs(
                        float(segment["end_sec"])
                        - int(segment["end_sample"]) / sample_rate
                    )
                    if max(start_delta, end_delta) > 1.0 / sample_rate:
                        errors.append(f"sample/second placement differs: {ref_id}")
            if verify_audio:
                _verify_case_audio(case, errors)
        if verify_audio:
            for enrollment_row in enrollment_rows.values():
                _verify_enrollment_audio(enrollment_row, errors)
        primary_speakers[split] = {
            str(speaker)
            for case in cases
            if case.get("measurement_mode") == "controlled_end_to_end"
            for speaker in case.get("global_speaker_ids", [])
        }

    checks["case_ids_unique_and_sorted"] = not any(
        "case IDs are not sorted and unique" in value for value in errors
    )
    checks["reference_links_resolve"] = not any(
        "references missing" in value for value in errors
    )
    checks["enrollment_mixture_disjoint"] = not any(
        "enrollment/mixture overlap" in value for value in errors
    )
    checks["exact_sample_placement"] = not any(
        "sample/second placement differs" in value for value in errors
    )
    checks["primary_development_evaluation_speaker_disjoint"] = not bool(
        primary_speakers.get("development", set())
        & primary_speakers.get("evaluation", set())
    )
    if not checks["primary_development_evaluation_speaker_disjoint"]:
        errors.append("primary development/evaluation speakers overlap")
    checks["development_evaluation_enrollment_gallery_speaker_disjoint"] = not bool(
        enrollment_speakers.get("development", set())
        & enrollment_speakers.get("evaluation", set())
    )
    if not checks["development_evaluation_enrollment_gallery_speaker_disjoint"]:
        errors.append("development/evaluation enrollment-gallery speakers overlap")
    case_counts = {split: len(rows) for split, rows in cases_by_split.items()}
    expected_counts = summary.get("case_counts", {})
    checks["case_counts_match_summary"] = case_counts == expected_counts
    if not checks["case_counts_match_summary"]:
        errors.append("case counts differ from protocol summary")

    contract_preflight = preflight_case_contracts(protocol_root)
    checks["supported_view_contracts_hydrate"] = bool(contract_preflight["valid"])
    if not contract_preflight["valid"]:
        errors.extend(str(value) for value in contract_preflight["errors"])

    return _validation_result(
        summary.get("protocol_id"),
        case_counts,
        summary,
        checks,
        errors,
        warnings,
    )


def load_cases(
    protocol_root: Path | str = DEFAULT_PROTOCOL_ROOT,
    *,
    split: str | None = None,
    source_keys: Sequence[str] | None = None,
    overlay_ids: Sequence[str] | None = None,
) -> tuple[dict[str, object], ...]:
    """Load prepared cases in stable protocol-case order with optional filters."""

    root = Path(protocol_root).resolve()
    splits = (split,) if split else ("development", "evaluation")
    wanted_sources = set(source_keys or ())
    wanted_overlays = set(overlay_ids or ())
    rows = [row for part in splits for row in _read_jsonl(root / part / "case_manifest.jsonl")]
    if wanted_sources:
        rows = [row for row in rows if str(row.get("source_key")) in wanted_sources]
    if wanted_overlays:
        rows = [row for row in rows if str(row.get("overlay_id")) in wanted_overlays]
    return tuple(sorted(rows, key=lambda row: str(row["protocol_case_id"])))


def preflight_case_contracts(
    protocol_root: Path | str = DEFAULT_PROTOCOL_ROOT,
    *,
    cases: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Resolve every declared supported-view reference without model inference.

    This is intentionally stricter than checking that a pointer-shaped field is
    present: the referenced row/file must exist and contain the case identity.
    """

    root = Path(protocol_root).resolve()
    selected = tuple(cases) if cases is not None else load_cases(root)
    errors: list[str] = []
    warnings: list[str] = []
    supported_counts: Counter[str] = Counter()
    hydrated_counts: Counter[str] = Counter()
    partition_indexes: dict[str, dict[str, object]] = {}

    for case in selected:
        split = str(case.get("partition") or case.get("split") or "")
        case_id = str(case.get("protocol_case_id") or case.get("case_id") or "")
        if split not in {"development", "evaluation"} or not case_id:
            errors.append(f"case contract lacks a valid identity/partition: {case_id!r}")
            continue
        if split not in partition_indexes:
            partition_indexes[split] = _partition_contract_indexes(root, split)
        indexes = partition_indexes[split]
        supported = {str(value) for value in case.get("supported_views", [])}
        supported_counts.update(supported)
        mode = str(case.get("measurement_mode"))
        if mode == "controlled_end_to_end":
            reference = indexes["references"].get(str(case.get("source_reference_id")))
            overlay = indexes["overlays"].get(str(case.get("identity_overlay_ref")))
            enrollment = indexes["enrollment"]
            if not isinstance(reference, Mapping):
                errors.append(f"{case_id}: controlled transcript reference cannot hydrate")
                continue
            segments = reference.get("segments")
            if not isinstance(segments, list) or not segments:
                errors.append(f"{case_id}: controlled transcript reference has no segments")
                continue
            scorable = [
                row
                for row in segments
                if isinstance(row, Mapping)
                and row.get("speaker_attributed_transcript_status") == "supported"
                and isinstance(row.get("scorable_transcript"), str)
                and str(row["scorable_transcript"]).strip()
            ]
            if "asr" in supported:
                if scorable:
                    hydrated_counts["asr"] += 1
                else:
                    errors.append(f"{case_id}: supported ASR has no scorable transcript")
            if "speaker_attributed_transcript" in supported:
                if scorable and all(row.get("global_speaker_id") for row in scorable):
                    hydrated_counts["speaker_attributed_transcript"] += 1
                else:
                    errors.append(
                        f"{case_id}: speaker-attributed transcript cannot hydrate"
                    )
            if "diarization" in supported:
                if _case_timing_references_hydrate(case, indexes):
                    hydrated_counts["diarization"] += 1
                else:
                    errors.append(f"{case_id}: RTTM/UEM reference cannot hydrate")
            if "identity" in supported:
                identity_error = _controlled_identity_contract_error(
                    case, overlay, enrollment
                )
                if identity_error is None:
                    hydrated_counts["identity"] += 1
                else:
                    errors.append(f"{case_id}: {identity_error}")
        elif mode == "component_diagnostic":
            if "asr" in supported:
                if _diagnostic_asr_reference_hydrates(case, indexes):
                    hydrated_counts["asr"] += 1
                else:
                    errors.append(f"{case_id}: diagnostic ASR reference cannot hydrate")
            if "speaker_attributed_transcript" in supported:
                if _native_transcript_reference_hydrates(case, indexes):
                    hydrated_counts["speaker_attributed_transcript"] += 1
                else:
                    errors.append(
                        f"{case_id}: native speaker-attributed reference cannot hydrate"
                    )
            if "diarization" in supported:
                if _native_timing_reference_hydrates(case, indexes):
                    hydrated_counts["diarization"] += 1
                else:
                    errors.append(f"{case_id}: native RTTM/UEM reference cannot hydrate")
            if "identity" in supported:
                errors.append(
                    f"{case_id}: diagnostic identity is declared supported without a gallery"
                )
        else:
            errors.append(f"{case_id}: unsupported measurement_mode {mode!r}")

        for view in supported & {"streaming", "resources"}:
            if _case_audio_contract_hydrates(case):
                hydrated_counts[view] += 1
            else:
                errors.append(f"{case_id}: {view} audio contract cannot hydrate")

    return {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "valid": not errors,
        "status": "PASS" if not errors else "FAIL",
        "case_count": len(selected),
        "supported_view_counts": dict(sorted(supported_counts.items())),
        "hydrated_view_counts": dict(sorted(hydrated_counts.items())),
        "errors": errors,
        "warnings": warnings,
        "model_inference_performed": False,
    }


def plan_protocol(
    protocol_root: Path | str = DEFAULT_PROTOCOL_ROOT,
    *,
    splits: Sequence[str] = ("development", "evaluation"),
    source_keys: Sequence[str] | None = None,
    overlay_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Return a read-only deterministic workload plan for controller integration."""

    root = Path(protocol_root).resolve()
    summary = read_json(root / "protocol_summary.json")
    cases = tuple(
        row
        for split in splits
        for row in load_cases(
            root,
            split=split,
            source_keys=source_keys,
            overlay_ids=overlay_ids,
        )
    )
    case_counts = Counter(str(row["partition"]) for row in cases)
    scenario_counts = Counter(str(row.get("scenario_id", "not_applicable")) for row in cases)
    overlap_counts = Counter(str(row.get("overlap", "not_applicable")) for row in cases)
    gallery_counts = Counter(
        str(row["gallery_size"]) for row in cases if row.get("gallery_size") is not None
    )
    supported = Counter(
        str(view) for row in cases for view in row.get("supported_views", [])
    )
    unsupported: dict[str, set[str]] = defaultdict(set)
    for row in cases:
        for item in row.get("unsupported_views", []):
            if isinstance(item, dict):
                unsupported[str(item.get("id"))].add(str(item.get("reason")))
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "protocol_id": summary["protocol_id"],
        "filters": {
            "splits": list(splits),
            "source_keys": list(source_keys or []),
            "overlay_ids": list(overlay_ids or []),
        },
        "case_counts": dict(sorted(case_counts.items())),
        "audio_duration_sec": round(sum(float(row["duration_sec"]) for row in cases), 9),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "overlap_counts": dict(sorted(overlap_counts.items())),
        "gallery_size_counts": dict(sorted(gallery_counts.items())),
        "supported_views": dict(sorted(supported.items())),
        "unsupported": {
            key: sorted(values) for key, values in sorted(unsupported.items())
        },
        "case_ids": [str(row["protocol_case_id"]) for row in cases],
        "inference_started": False,
    }


def _prepare_controlled_source(
    source: Mapping[str, object],
    *,
    protocol_id: str,
    transcript_lookup: Mapping[str, str],
    cases: dict[str, list[dict[str, object]]],
    references: dict[str, list[dict[str, object]]],
    overlays: dict[str, list[dict[str, object]]],
    enrollment: dict[str, dict[str, dict[str, object]]],
) -> None:
    source_root = _tool_path(source["source_root"])
    overlay_root = _tool_path(source["identity_overlay_root"])
    source_checksum_path = source_root / "checksums.json"
    source_checksum_entries: Mapping[str, object] = {}
    if source_checksum_path.is_file():
        source_checksum_entries = read_json(source_checksum_path).get("entries", {})
    inventory = {
        str(row["source_clip_id"]): row
        for row in _read_csv(source_root / str(source["source_inventory"]))
    }
    for split in source["partitions"]:
        split = str(split)
        source_cases = list(
            _read_jsonl(source_root / str(source["case_manifests"][split]))
        )
        overlay_rows = list(
            _read_jsonl(overlay_root / str(source["identity_overlays"][split]))
        )
        by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in overlay_rows:
            by_case[str(row["case_id"])].append(row)
        for source_case in source_cases:
            case_id = str(source_case["case_id"])
            recipe_relative = str(source_case["recipe_path"]).replace("\\", "/")
            recipe_path = source_root / recipe_relative
            recipe_file_identity = source_checksum_entries.get(recipe_relative)
            if isinstance(recipe_file_identity, dict):
                expected_file_sha = str(recipe_file_identity.get("sha256", ""))
                if sha256_file(recipe_path).lower() != expected_file_sha.lower():
                    raise ProtocolError(f"frozen recipe file SHA-256 differs: {recipe_path}")
            recipe = read_json(recipe_path)
            if str(recipe.get("recipe_sha256", "")).lower() != str(
                source_case["recipe_sha256"]
            ).lower():
                raise ProtocolError(f"recipe scientific identity differs: {recipe_path}")
            placements = recipe.get("placements")
            if not isinstance(placements, list):
                raise ProtocolError(f"recipe has no placements: {recipe_path}")
            frozen_file_hashes = {
                "recipe_file_sha256": _checksum_entry_sha(
                    source_checksum_entries, recipe_relative
                ),
                "reference_rttm_sha256": _checksum_entry_sha(
                    source_checksum_entries,
                    str(source_case["reference_rttm_path"]).replace("\\", "/"),
                ),
                "reference_uem_sha256": _checksum_entry_sha(
                    source_checksum_entries,
                    str(source_case["reference_uem_path"]).replace("\\", "/"),
                ),
            }
            source_reference = _controlled_reference(
                source,
                split,
                source_case,
                placements,
                inventory,
                transcript_lookup,
            )
            references[split].append(source_reference)
            mixture_clip_ids = {
                str(segment["source_clip_id"])
                for segment in source_reference["segments"]
            }
            if not by_case.get(case_id):
                raise ProtocolError(f"case has no known/unknown overlay: {source['source_key']} {case_id}")
            for overlay_source in sorted(by_case[case_id], key=lambda row: str(row["overlay_id"])):
                overlay = _controlled_overlay(
                    source,
                    split,
                    overlay_source,
                    mixture_clip_ids,
                    enrollment[split],
                )
                overlays[split].append(overlay)
                for gallery in _valid_galleries(overlay_source):
                    gallery_ids = tuple(sorted(str(value) for value in gallery["enrolled_ids"]))
                    known_enrolled_ids = {
                        str(state["enrolled_id"])
                        for state in overlay_source["speaker_states"].values()
                        if state.get("identity_state") == "KNOWN"
                    }
                    if not known_enrolled_ids <= set(gallery_ids):
                        raise ProtocolError(
                            f"valid gallery omits live known identity: {case_id}/{overlay_source['overlay_id']}"
                        )
                    case_identity = {
                        "source_key": source["source_key"],
                        "source_case_id": case_id,
                        "overlay_id": overlay_source["overlay_id"],
                        "gallery_requested_size": gallery["requested_size"],
                        "gallery_enrolled_ids": gallery_ids,
                    }
                    generated_id = "fspcase_" + _canonical_sha(case_identity)[:20]
                    cases[split].append(
                        _controlled_case(
                            protocol_id,
                            source,
                            split,
                            source_case,
                            source_reference,
                            overlay,
                            gallery,
                            generated_id,
                            frozen_file_hashes,
                        )
                    )


def _preflight_declared_sources(config: Mapping[str, object]) -> dict[str, object]:
    """Prove frozen source rows can become executable case contracts in memory."""

    errors: list[str] = []
    counts: Counter[str] = Counter()
    transcript_lookup: Mapping[str, str] | None = None
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover - production environment includes pandas
        pd = None

    for source in config["sources"]:
        source_key = str(source["source_key"])
        kind = str(source["kind"])
        try:
            if kind == "controlled_primary":
                if transcript_lookup is None:
                    transcript_lookup = _load_transcript_lookup(config["transcript_source"])
                source_root = _tool_path(source["source_root"])
                overlay_root = _tool_path(source["identity_overlay_root"])
                inventory = {
                    str(row["source_clip_id"]): row
                    for row in _read_csv(
                        source_root / str(source["source_inventory"])
                    )
                }
                for split in source["partitions"]:
                    split = str(split)
                    cases = list(
                        _read_jsonl(
                            source_root / str(source["case_manifests"][split])
                        )
                    )
                    overlays = list(
                        _read_jsonl(
                            overlay_root / str(source["identity_overlays"][split])
                        )
                    )
                    overlays_by_case = Counter(str(row.get("case_id")) for row in overlays)
                    for case in cases:
                        case_id = str(case["case_id"])
                        counts[source_key] += 1
                        if overlays_by_case[case_id] == 0:
                            errors.append(f"{source_key}/{case_id}: identity overlay absent")
                        for reference_key in ("reference_rttm_path", "reference_uem_path"):
                            if not (source_root / str(case[reference_key])).is_file():
                                errors.append(
                                    f"{source_key}/{case_id}: {reference_key} absent"
                                )
                        recipe = read_json(source_root / str(case["recipe_path"]))
                        placements = recipe.get("placements")
                        if not isinstance(placements, list) or not placements:
                            errors.append(f"{source_key}/{case_id}: recipe placements absent")
                            continue
                        for placement in placements:
                            clip_id = str(placement.get("source_clip_id"))
                            inventory_row = inventory.get(clip_id)
                            filename = Path(
                                str(placement.get("logical_audio_path") or "")
                            ).name
                            if inventory_row is None:
                                errors.append(
                                    f"{source_key}/{case_id}: inventory clip absent {clip_id}"
                                )
                            elif filename not in transcript_lookup:
                                errors.append(
                                    f"{source_key}/{case_id}: transcript absent {filename}"
                                )
                            else:
                                normalized = _normalize_source_transcript(
                                    transcript_lookup[filename]
                                )
                                actual = hashlib.sha256(
                                    normalized.encode("utf-8")
                                ).hexdigest()
                                if actual.lower() != str(
                                    inventory_row["transcript_sha256"]
                                ).lower():
                                    errors.append(
                                        f"{source_key}/{case_id}: transcript identity differs {clip_id}"
                                    )
            elif kind == "native_diagnostic":
                if pd is None:
                    raise ProtocolError("pandas is required for native preflight")
                frame = pd.read_parquet(_tool_path(source["manifest"]))
                transcript_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
                for row in _read_jsonl(_tool_path(source["reference_transcripts"])):
                    transcript_rows[str(row.get("evaluation_unit_id"))].append(row)
                rttm_ids = _read_timing_ids(_tool_path(source["reference_rttm"]), "rttm")
                uem_ids = _read_timing_ids(_tool_path(source["reference_uem"]), "uem")
                for raw in frame.to_dict(orient="records"):
                    row = _clean_mapping(raw)
                    if row.get("dataset") not in {"ami", "chime6"}:
                        continue
                    case_id = str(row["evaluation_unit_id"])
                    counts[source_key] += 1
                    if bool(row.get("der_jer_eligible")) and (
                        case_id not in rttm_ids or case_id not in uem_ids
                    ):
                        errors.append(f"{source_key}/{case_id}: native timing refs absent")
                    if bool(row.get("cpwer_eligible")):
                        refs = transcript_rows.get(case_id, [])
                        if not refs or not all(
                            value.get("full_reference_segment") is True
                            and isinstance(value.get("text"), str)
                            and str(value["text"]).strip()
                            for value in refs
                        ):
                            errors.append(
                                f"{source_key}/{case_id}: cpWER transcript refs incomplete"
                            )
            elif kind in {"standard_asr_diagnostic", "commonvoice_asr_diagnostic"}:
                if pd is None:
                    raise ProtocolError("pandas is required for ASR preflight")
                frame = pd.read_parquet(_tool_path(source["manifest"]))
                if kind == "standard_asr_diagnostic":
                    frame = frame[frame["dataset"].isin(list(source["include_datasets"]))]
                    id_column = "recording_id"
                else:
                    frame = frame[frame["protocol_split"] == source["source_split"]]
                    id_column = "item_id"
                counts[source_key] += len(frame)
                missing = frame["reference_text"].isna() | (
                    frame["reference_text"].astype(str).str.strip() == ""
                )
                for value in frame.loc[missing, id_column].head(20):
                    errors.append(f"{source_key}/{value}: ASR transcript absent")
                if int(missing.sum()) > 20:
                    errors.append(
                        f"{source_key}: {int(missing.sum()) - 20} additional ASR transcripts absent"
                    )
            else:
                errors.append(f"{source_key}: unsupported source kind {kind!r}")
        except Exception as error:
            errors.append(
                f"{source_key}: case-contract preflight failed: "
                f"{type(error).__name__}: {error}"
            )
    return {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "scope": "declared_frozen_sources",
        "valid": not errors,
        "status": "PASS" if not errors else "FAIL",
        "case_counts": dict(sorted(counts.items())),
        "errors": errors,
        "model_inference_performed": False,
    }


def _controlled_reference(
    source: Mapping[str, object],
    split: str,
    source_case: Mapping[str, object],
    placements: Sequence[Mapping[str, object]],
    inventory: Mapping[str, Mapping[str, str]],
    transcript_lookup: Mapping[str, str],
) -> dict[str, object]:
    segments: list[dict[str, object]] = []
    unsupported_count = 0
    for index, placement in enumerate(placements):
        clip_id = str(placement["source_clip_id"])
        if clip_id not in inventory:
            raise ProtocolError(f"placement clip absent from source inventory: {clip_id}")
        inventory_row = inventory[clip_id]
        filename = Path(str(placement["logical_audio_path"])).name
        if filename not in transcript_lookup:
            raise ProtocolError(f"source transcript absent for {filename}")
        source_text = transcript_lookup[filename]
        normalized = _normalize_source_transcript(source_text)
        actual_text_sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        expected_text_sha = str(inventory_row["transcript_sha256"]).lower()
        if actual_text_sha != expected_text_sha:
            raise ProtocolError(f"source transcript SHA-256 differs for {clip_id}")
        cropped = bool(placement.get("product_short_turn_crop", False))
        if cropped:
            unsupported_count += 1
        segments.append(
            {
                "reference_segment_id": f"{source['source_key']}:{source_case['case_id']}:{index:04d}",
                "turn_index": int(placement.get("turn_index", index)),
                "reference_speaker": str(placement["reference_speaker"]),
                "global_speaker_id": str(placement["global_speaker_id"]),
                "start_sample": int(placement["global_start_sample"]),
                "end_sample": int(placement["global_end_sample"]),
                "start_sec": float(placement["global_start_sec"]),
                "end_sec": float(placement["global_end_sec"]),
                "source_clip_id": clip_id,
                "source_audio_logical_path": str(placement["logical_audio_path"]),
                "source_audio_sha256": str(placement["source_audio_sha256"]).upper(),
                "source_crop_start_sample": int(placement["source_crop_start_sample"]),
                "source_crop_end_sample": int(placement["source_crop_end_sample"]),
                "source_transcript": source_text,
                "source_transcript_normalized": normalized,
                "source_transcript_sha256": actual_text_sha.upper(),
                "scorable_transcript": None if cropped else source_text,
                "scorable_transcript_normalized": None if cropped else normalized,
                "speaker_attributed_transcript_status": "unsupported" if cropped else "supported",
                "unsupported_reason": (
                    "product_short_turn_crop does not contain the complete source utterance"
                    if cropped
                    else None
                ),
                "product_short_turn_crop": cropped,
                "overlap_indicator": bool(placement.get("overlap_indicator", False)),
            }
        )
    status = "supported" if unsupported_count == 0 else "partial"
    return {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "source_reference_id": f"{source['source_key']}:{source_case['case_id']}",
        "source_key": str(source["source_key"]),
        "source_protocol_id": str(source["source_protocol_id"]),
        "source_case_id": str(source_case["case_id"]),
        "partition": split,
        "sample_rate_hz": int(source_case["sample_rate_hz"]),
        "speaker_attributed_transcript_status": status,
        "unsupported_segment_count": unsupported_count,
        "segments": segments,
    }


def _controlled_overlay(
    source: Mapping[str, object],
    split: str,
    row: Mapping[str, object],
    mixture_clip_ids: set[str],
    registry: dict[str, dict[str, object]],
) -> dict[str, object]:
    database_refs: list[dict[str, object]] = []
    for record in row.get("enrollment_database", []):
        enrolled_id = str(record["enrolled_id"])
        clips = [
            {
                "source_clip_id": str(clip["source_clip_id"]),
                "logical_audio_path": str(clip["logical_audio_path"]),
                "source_audio_sha256": str(clip["source_audio_sha256"]).upper(),
                "duration_sec": float(clip["duration_sec"]),
            }
            for clip in record.get("reserved_enrollment_clips", [])
        ]
        reserved_ids = {str(clip["source_clip_id"]) for clip in clips}
        overlap = mixture_clip_ids & reserved_ids
        if overlap:
            raise ProtocolError(
                f"enrollment/mixture overlap for {row['case_id']}/{row['overlay_id']}: {sorted(overlap)}"
            )
        enrollment_record = {
            "schema_version": ENROLLMENT_SCHEMA_VERSION,
            "enrolled_id": enrolled_id,
            "global_speaker_id": str(record["global_speaker_id"]),
            "partition": split,
            "source_protocol_ids": [str(source["source_protocol_id"])],
            "reserved_enrollment_clips": clips,
        }
        existing = registry.get(enrolled_id)
        if existing is not None:
            existing_core = {
                key: value for key, value in existing.items() if key != "source_protocol_ids"
            }
            incoming_core = {
                key: value
                for key, value in enrollment_record.items()
                if key != "source_protocol_ids"
            }
            if existing_core != incoming_core:
                raise ProtocolError(f"enrollment identity changes within partition: {enrolled_id}")
            existing["source_protocol_ids"] = sorted(
                {
                    *existing["source_protocol_ids"],
                    str(source["source_protocol_id"]),
                }
            )
        else:
            registry[enrolled_id] = enrollment_record
        database_refs.append(
            {
                "enrolled_id": enrolled_id,
                "global_speaker_id": str(record["global_speaker_id"]),
                "database_role": str(record["database_role"]),
                "reserved_source_clip_ids": sorted(reserved_ids),
            }
        )
    return {
        "schema_version": OVERLAY_SCHEMA_VERSION,
        "identity_overlay_ref": f"{source['source_key']}:{row['case_id']}:{row['overlay_id']}",
        "source_key": str(source["source_key"]),
        "source_protocol_id": str(source["source_protocol_id"]),
        "identity_overlay_protocol_id": str(source["identity_overlay_protocol_id"]),
        "source_case_id": str(row["case_id"]),
        "partition": split,
        "overlay_id": str(row["overlay_id"]),
        "speaker_states": row["speaker_states"],
        "enrollment_database": sorted(database_refs, key=lambda value: value["enrolled_id"]),
        "enrollment_mixture_disjoint": True,
        "waveform_identity_unchanged": bool(row.get("waveform_identity_unchanged", False)),
    }


def _valid_galleries(row: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    galleries = row.get("gallery_subsets")
    if isinstance(galleries, list):
        result = [
            {
                "requested_size": item["requested_size"],
                "realized_size": int(item["realized_size"]),
                "enrolled_ids": list(item["enrolled_ids"]),
                "primary": bool(item.get("primary", False)),
            }
            for item in galleries
            if item.get("status") == "VALID"
        ]
    else:
        enrolled_ids = sorted(
            {str(record["enrolled_id"]) for record in row.get("enrollment_database", [])}
        )
        result = [
            {
                "requested_size": "source_full",
                "realized_size": len(enrolled_ids),
                "enrolled_ids": enrolled_ids,
                "primary": True,
            }
        ]
    if not result:
        raise ProtocolError(f"overlay has no scientifically valid gallery: {row['case_id']}")
    return tuple(result)


def _controlled_case(
    protocol_id: str,
    source: Mapping[str, object],
    split: str,
    source_case: Mapping[str, object],
    reference: Mapping[str, object],
    overlay: Mapping[str, object],
    gallery: Mapping[str, object],
    generated_id: str,
    frozen_file_hashes: Mapping[str, object],
) -> dict[str, object]:
    source_root = str(source["source_root"]).rstrip("/\\")
    speaker_states = overlay["speaker_states"]
    known = sum(state.get("identity_state") == "KNOWN" for state in speaker_states.values())
    unknown = sum(state.get("identity_state") == "UNKNOWN" for state in speaker_states.values())
    ref_status = str(reference["speaker_attributed_transcript_status"])
    supported = list(source.get("supported_views", []))
    unsupported = list(source.get("unsupported_views", []))
    scorable_segment_count = sum(
        isinstance(row, Mapping)
        and row.get("speaker_attributed_transcript_status") == "supported"
        for row in reference.get("segments", [])
    )
    if scorable_segment_count == 0:
        supported = [
            view
            for view in supported
            if view not in {"asr", "speaker_attributed_transcript"}
        ]
        unsupported = [
            *unsupported,
            {
                "id": "asr",
                "reason": "Every source turn is a deliberate partial crop; no complete transcript is scorable.",
            },
            {
                "id": "speaker_attributed_transcript",
                "reason": "Every source turn is a deliberate partial crop; no complete speaker transcript is scorable.",
            },
        ]
    if ref_status == "partial":
        unsupported = [
            *unsupported,
            {
                "id": "speaker_attributed_transcript_complete_case",
                "reason": "One or more Product V2 turns are deliberate partial source crops.",
            },
        ]
    scenario_id = str(
        source_case.get("scenario_profile")
        or f"{source_case.get('turn_cadence', 'unknown')}:{source_case.get('speaker_count', 'unknown')}"
    )
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "protocol_id": protocol_id,
        "protocol_case_id": generated_id,
        "partition": split,
        "measurement_mode": "controlled_end_to_end",
        "scoring_stratum": "controlled_end_to_end",
        "source_key": str(source["source_key"]),
        "source_protocol_id": str(source["source_protocol_id"]),
        "source_case_id": str(source_case["case_id"]),
        "source_reference_id": str(reference["source_reference_id"]),
        "identity_overlay_ref": str(overlay["identity_overlay_ref"]),
        "overlay_id": str(overlay["overlay_id"]),
        "gallery_requested_size": gallery["requested_size"],
        "gallery_size": int(gallery["realized_size"]),
        "gallery_primary": bool(gallery["primary"]),
        "gallery_enrolled_ids": sorted(str(value) for value in gallery["enrolled_ids"]),
        "known_speaker_count": known,
        "unknown_speaker_count": unknown,
        "global_speaker_ids": sorted(str(value) for value in source_case["global_speaker_ids"]),
        "local_to_global_speaker": source_case["local_to_global_speaker"],
        "audio_logical_path": f"{source_root}/{source_case['audio_logical_path']}",
        "audio_namespace": "tool_root",
        "audio_sha256": str(source_case["audio_sha256"]).upper(),
        "pcm_sha256": str(source_case["pcm_sha256"]).upper(),
        "sample_rate_hz": int(source_case["sample_rate_hz"]),
        "channels": int(source_case["channels"]),
        "duration_sec": float(source_case["duration_sec"]),
        "recipe_logical_path": f"{source_root}/{source_case['recipe_path']}",
        "recipe_sha256": str(source_case["recipe_sha256"]).upper(),
        "recipe_file_sha256": frozen_file_hashes["recipe_file_sha256"],
        "reference_rttm_logical_path": f"{source_root}/{source_case['reference_rttm_path']}",
        "reference_rttm_sha256": frozen_file_hashes["reference_rttm_sha256"],
        "reference_uem_logical_path": f"{source_root}/{source_case['reference_uem_path']}",
        "reference_uem_sha256": frozen_file_hashes["reference_uem_sha256"],
        "scenario_id": scenario_id,
        "scenario": {
            "profile": source_case.get("scenario_profile"),
            "speaker_count": int(source_case["speaker_count"]),
            "speaker_band": source_case.get("speaker_band"),
            "turn_cadence": source_case.get("turn_cadence"),
            "turn_pattern": source_case.get("turn_pattern"),
            "participation_profile": source_case.get("participation_profile"),
            "long_session": bool(source_case.get("long_session", False)),
        },
        "overlap": str(source_case.get("overlap_profile", "unknown")),
        "overlap_ratio": float(
            source_case.get("reference_statistics", {}).get("overlap_ratio", 0.0)
        ),
        "speaker_attributed_transcript_status": ref_status,
        "supported_views": supported,
        "unsupported_views": unsupported,
        "development_evaluation_speaker_disjoint_scope": "controlled_primary",
        "evaluation_only": True,
        "training_eligible": False,
    }


def _diagnostic_cases(
    source: Mapping[str, object], *, protocol_id: str
) -> list[dict[str, object]]:
    try:
        import pandas as pd
    except ImportError as error:  # pragma: no cover - exercised only in incomplete envs
        raise ProtocolError("pandas and a Parquet engine are required to prepare diagnostics") from error

    manifest = _tool_path(source["manifest"])
    frame = pd.read_parquet(manifest)
    kind = str(source["kind"])
    split = str(source["partition"])
    rows: list[dict[str, object]] = []
    if kind == "native_diagnostic":
        frame = frame[frame["dataset"].isin(["ami", "chime6"])]
        for raw in frame.to_dict(orient="records"):
            row = _clean_mapping(raw)
            dataset = str(row["dataset"])
            der = bool(row.get("der_jer_eligible"))
            cpwer = bool(row.get("cpwer_eligible"))
            scoring_stratum = (
                "ami_cpwer_and_diarization"
                if dataset == "ami" and cpwer
                else "ami_diarization_only"
                if dataset == "ami"
                else "chime6_diarization_only"
            )
            supported = ["streaming", "resources"]
            if der:
                supported.append("diarization")
            if cpwer:
                supported.extend(["asr", "speaker_attributed_transcript"])
            unsupported = [
                {
                    "id": "identity",
                    "reason": "No frozen enrollment/probe-disjoint known/unknown gallery exists for the native source.",
                }
            ]
            if not cpwer:
                unsupported.append(
                    {
                        "id": "speaker_attributed_transcript",
                        "reason": "The frozen native unit has no complete cpWER-compatible transcript reference.",
                    }
                )
            rows.append(
                _diagnostic_case_base(
                    protocol_id,
                    source,
                    split,
                    source_id=str(row["evaluation_unit_id"]),
                    dataset=dataset,
                    audio_path=str(row["audio_path_project_relative"]),
                    duration=float(row["duration_sec"]),
                    sample_rate=None,
                    channels=None,
                    supported=supported,
                    unsupported=unsupported,
                    extra={
                        "source_recording_id": row.get("source_recording_id"),
                        "source_start_sec": row.get("source_start_sec"),
                        "source_end_sec": row.get("source_end_sec"),
                        "scored_region_start_sec": row.get("scored_region_start_sec"),
                        "scored_region_end_sec": row.get("scored_region_end_sec"),
                        "der_jer_eligible": der,
                        "cpwer_eligible": cpwer,
                        "scoring_stratum": scoring_stratum,
                        "reference_transcripts_logical_path": str(source["reference_transcripts"]),
                        "reference_rttm_logical_path": str(source["reference_rttm"]),
                        "reference_uem_logical_path": str(source["reference_uem"]),
                    },
                )
            )
    elif kind == "standard_asr_diagnostic":
        frame = frame[frame["dataset"].isin(list(source["include_datasets"]))]
        for raw in frame.to_dict(orient="records"):
            row = _clean_mapping(raw)
            dataset = str(row["dataset"])
            unsupported = list(source.get("unsupported_views", []))
            if dataset == "voices":
                unsupported = [
                    *unsupported,
                    {
                        "id": "voices_scope",
                        "reason": "VOiCES is retained only for source-utterance acoustic/ASR robustness diagnostics.",
                    },
                ]
            rows.append(
                _diagnostic_case_base(
                    protocol_id,
                    source,
                    split,
                    source_id=str(row["recording_id"]),
                    dataset=dataset,
                    audio_path=str(row["audio_path_project_relative"]),
                    duration=float(row["duration_sec"]),
                    sample_rate=None,
                    channels=None,
                    supported=list(source["supported_views"]),
                    unsupported=unsupported,
                    extra={
                        "reference_text": row.get("reference_text"),
                        "reference_speaker_id": row.get("speaker_id"),
                        "source_start_sec": row.get("start_sec"),
                        "source_end_sec": row.get("end_sec"),
                        "source_manifest_sha256": str(source["identity_files"][0]["sha256"]).upper(),
                        "scoring_stratum": f"{dataset}_asr",
                    },
                )
            )
    elif kind == "commonvoice_asr_diagnostic":
        frame = frame[frame["protocol_split"] == source["source_split"]]
        for raw in frame.to_dict(orient="records"):
            row = _clean_mapping(raw)
            rows.append(
                _diagnostic_case_base(
                    protocol_id,
                    source,
                    split,
                    source_id=str(row["item_id"]),
                    dataset="commonvoice_60plus",
                    audio_path=str(row["logical_audio_path"]),
                    duration=float(row["duration_sec"]),
                    sample_rate=int(row["sample_rate_hz"]),
                    channels=int(row["channels"]),
                    supported=list(source["supported_views"]),
                    unsupported=list(source.get("unsupported_views", [])),
                    extra={
                        "reference_text": row["reference_text"],
                        "reference_normalized": row["reference_normalized"],
                        "reference_sha256": str(row["reference_sha256"]).upper(),
                        "reference_speaker_id": row["speaker_key"],
                        "audio_sha256": str(row["audio_sha256"]).upper(),
                        "protocol_split": row["protocol_split"],
                        "scoring_stratum": "commonvoice_60plus_asr",
                    },
                )
            )
    return rows


def _diagnostic_case_base(
    protocol_id: str,
    source: Mapping[str, object],
    split: str,
    *,
    source_id: str,
    dataset: str,
    audio_path: str,
    duration: float,
    sample_rate: int | None,
    channels: int | None,
    supported: Sequence[str],
    unsupported: Sequence[object],
    extra: Mapping[str, object],
) -> dict[str, object]:
    identity = {
        "source_key": source["source_key"],
        "source_protocol_id": source["source_protocol_id"],
        "source_id": source_id,
    }
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "protocol_id": protocol_id,
        "protocol_case_id": "fspdiag_" + _canonical_sha(identity)[:20],
        "partition": split,
        "measurement_mode": "component_diagnostic",
        "source_key": str(source["source_key"]),
        "source_protocol_id": str(source["source_protocol_id"]),
        "source_case_id": source_id,
        "source_dataset": dataset,
        "audio_logical_path": audio_path,
        "audio_namespace": "data_root",
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "duration_sec": duration,
        "global_speaker_ids": [],
        "source_reference_id": None,
        "identity_overlay_ref": None,
        "overlay_id": None,
        "gallery_size": None,
        "scenario_id": f"diagnostic:{dataset}",
        "overlap": "source_native_or_not_applicable",
        "supported_views": sorted(set(str(value) for value in supported)),
        "unsupported_views": list(unsupported),
        "development_evaluation_speaker_disjoint_scope": "not_claimed_source_frozen_evaluation_diagnostic",
        "evaluation_only": True,
        "training_eligible": False,
        **extra,
    }


def _load_transcript_lookup(source: Mapping[str, object]) -> dict[str, str]:
    path = _transcript_path(source)
    lookup: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            filename = Path(str(row[source["path_column"]])).name
            text = str(row[source["text_column"]])
            previous = lookup.get(filename)
            if previous is not None and previous != text:
                raise ProtocolError(f"conflicting source transcripts for {filename}")
            lookup[filename] = text
    return lookup


def _transcript_path(source: Mapping[str, object]) -> Path:
    if source.get("physical_path"):
        return Path(str(source["physical_path"])).resolve()
    return resolve_data_path_from_logical(str(source["logical_path"])).resolve()


def _verify_case_audio(case: Mapping[str, object], errors: list[str]) -> None:
    logical = str(case["audio_logical_path"])
    if case.get("audio_namespace") == "tool_root":
        candidates = installed_tool_path_candidates(
            logical, evaluation_root=TOOL_ROOT
        )
        path = next(
            (candidate for candidate in candidates if candidate.is_file()),
            candidates[0],
        )
    else:
        path = resolve_data_path_from_logical(logical)
    if not path.is_file():
        errors.append(f"case audio missing: {logical}")
        return
    expected = case.get("audio_sha256")
    if expected and sha256_file(path).upper() != str(expected).upper():
        errors.append(f"case audio SHA-256 differs: {logical}")


def _verify_enrollment_audio(
    enrollment: Mapping[str, object], errors: list[str]
) -> None:
    enrolled_id = str(enrollment.get("enrolled_id") or "unknown")
    for clip in enrollment.get("reserved_enrollment_clips", []):
        if not isinstance(clip, Mapping):
            errors.append(f"enrollment clip record is invalid: {enrolled_id}")
            continue
        logical = str(clip.get("logical_audio_path") or "")
        path = _data_or_absolute_path(logical)
        if not path.is_file():
            errors.append(f"reserved enrollment audio missing: {enrolled_id}: {logical}")
            continue
        expected = str(clip.get("source_audio_sha256") or "")
        if not expected or sha256_file(path).upper() != expected.upper():
            errors.append(
                f"reserved enrollment audio SHA-256 differs: {enrolled_id}: {logical}"
            )


def _partition_contract_indexes(root: Path, split: str) -> dict[str, object]:
    references = {
        str(row["source_reference_id"]): row
        for row in _read_jsonl(
            root / split / "references/speaker_attributed_transcript.jsonl"
        )
    }
    overlays = {
        str(row["identity_overlay_ref"]): row
        for row in _read_jsonl(root / split / "identity/identity_overlays.jsonl")
    }
    enrollment = {
        str(row["enrolled_id"]): row
        for row in _read_jsonl(root / split / "enrollment/enrollment_registry.jsonl")
    }
    return {
        "references": references,
        "overlays": overlays,
        "enrollment": enrollment,
        "native_transcripts": {},
        "native_rttm_ids": {},
        "native_uem_ids": {},
        "file_sha256s": {},
    }


def _case_timing_references_hydrate(
    case: Mapping[str, object], indexes: dict[str, object]
) -> bool:
    hashes = indexes["file_sha256s"]
    if not isinstance(hashes, dict):
        return False
    for path_key, hash_key in (
        ("reference_rttm_logical_path", "reference_rttm_sha256"),
        ("reference_uem_logical_path", "reference_uem_sha256"),
    ):
        logical = case.get(path_key)
        expected = case.get(hash_key)
        if not isinstance(logical, str) or not logical or not expected:
            return False
        path = _tool_path(logical)
        key = str(path)
        if key not in hashes:
            hashes[key] = sha256_file(path).upper() if path.is_file() else None
        if hashes[key] != str(expected).upper():
            return False
    return True


def _controlled_identity_contract_error(
    case: Mapping[str, object],
    overlay: object,
    enrollment: object,
) -> str | None:
    if not isinstance(overlay, Mapping):
        return "identity overlay cannot hydrate"
    if not isinstance(enrollment, Mapping):
        return "enrollment registry cannot hydrate"
    states = overlay.get("speaker_states")
    if not isinstance(states, Mapping):
        return "identity overlay speaker states are absent"
    expected_speakers = {str(value) for value in case.get("global_speaker_ids", [])}
    if set(str(value) for value in states) != expected_speakers:
        return "identity overlay speakers differ from the mixture"
    gallery = {str(value) for value in case.get("gallery_enrolled_ids", [])}
    if int(case.get("gallery_size", -1)) != len(gallery) or not gallery <= set(enrollment):
        return "gallery IDs do not resolve to the enrollment registry"
    known = {
        str(value.get("enrolled_id"))
        for value in states.values()
        if isinstance(value, Mapping) and value.get("identity_state") == "KNOWN"
    }
    if not known <= gallery:
        return "known reference identity is absent from the selected gallery"
    for speaker_id, state in states.items():
        if not isinstance(state, Mapping):
            return f"speaker state is invalid for {speaker_id}"
        identity_state = state.get("identity_state")
        if identity_state == "KNOWN" and not state.get("enrolled_id"):
            return f"known speaker lacks enrolled_id: {speaker_id}"
        if identity_state == "UNKNOWN" and not state.get("unknown_reference_id"):
            return f"unknown speaker lacks unknown_reference_id: {speaker_id}"
        if identity_state not in {"KNOWN", "UNKNOWN"}:
            return f"invalid identity state for {speaker_id}"
    return None


def _diagnostic_asr_reference_hydrates(
    case: Mapping[str, object], indexes: dict[str, object]
) -> bool:
    text = case.get("reference_text")
    if isinstance(text, str) and text.strip():
        return True
    return _native_transcript_reference_hydrates(case, indexes)


def _native_transcript_reference_hydrates(
    case: Mapping[str, object], indexes: dict[str, object]
) -> bool:
    logical = case.get("reference_transcripts_logical_path")
    if not isinstance(logical, str) or not logical:
        return False
    path = _tool_path(logical)
    cache = indexes["native_transcripts"]
    if not isinstance(cache, dict):
        return False
    key = str(path)
    if key not in cache:
        rows: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in _read_jsonl(path):
            rows[str(row.get("evaluation_unit_id"))].append(row)
        cache[key] = rows
    rows = cache[key].get(str(case.get("source_case_id")), [])
    return bool(rows) and all(
        row.get("full_reference_segment") is True
        and isinstance(row.get("text"), str)
        and str(row["text"]).strip()
        for row in rows
    )


def _native_timing_reference_hydrates(
    case: Mapping[str, object], indexes: dict[str, object]
) -> bool:
    case_id = str(case.get("source_case_id"))
    rttm_path = case.get("reference_rttm_logical_path")
    uem_path = case.get("reference_uem_logical_path")
    if not isinstance(rttm_path, str) or not isinstance(uem_path, str):
        return False
    rttm_ids = _timing_file_ids(_tool_path(rttm_path), "rttm", indexes)
    uem_ids = _timing_file_ids(_tool_path(uem_path), "uem", indexes)
    return case_id in rttm_ids and case_id in uem_ids


def _timing_file_ids(
    path: Path, kind: str, indexes: dict[str, object]
) -> set[str]:
    cache_key = "native_rttm_ids" if kind == "rttm" else "native_uem_ids"
    cache = indexes[cache_key]
    if not isinstance(cache, dict):
        return set()
    key = str(path)
    if key not in cache:
        values: set[str] = set()
        if path.is_file():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    fields = line.split()
                    index = 1 if kind == "rttm" else 0
                    if len(fields) > index:
                        values.add(fields[index])
        cache[key] = values
    return set(cache[key])


def _read_timing_ids(path: Path, kind: str) -> set[str]:
    values: set[str] = set()
    if not path.is_file():
        return values
    index = 1 if kind == "rttm" else 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            fields = line.split()
            if len(fields) > index:
                values.add(fields[index])
    return values


def _case_audio_contract_hydrates(case: Mapping[str, object]) -> bool:
    logical = case.get("audio_logical_path")
    namespace = case.get("audio_namespace")
    return bool(
        isinstance(logical, str)
        and logical
        and namespace in {"tool_root", "data_root"}
        and float(case.get("duration_sec") or 0) > 0
    )


def _data_or_absolute_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else resolve_data_path_from_logical(path).resolve()


def _protocol_identity_payload(
    config: Mapping[str, object],
    config_sha256: str,
    audited_sources: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "protocol_name": config["protocol_name"],
        "protocol_version": config["protocol_version"],
        "protocol_builder_id": PROTOCOL_BUILDER_ID,
        "selection_seed": config["selection_seed"],
        "config_sha256": config_sha256,
        "sources": [
            {
                "source_key": row["source_key"],
                "protocol_id": row["protocol_id"],
                "identity_sha256s": row["identity_sha256s"],
            }
            for row in audited_sources
        ],
    }


def _protocol_id(identity_payload: Mapping[str, object]) -> str:
    return "full_speech_pipeline_v1_" + _canonical_sha(identity_payload)[:12]


def _split_identity(
    protocol_id: str, split: str, cases: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    payload = {
        "protocol_id": protocol_id,
        "partition": split,
        "case_ids": [str(row["protocol_case_id"]) for row in cases],
    }
    digest = _canonical_sha(payload)
    return {
        "partition_id": f"{protocol_id}_{split}_{digest[:12]}",
        "case_count": len(cases),
        "case_ids_sha256": hashlib.sha256(
            "\n".join(payload["case_ids"]).encode("utf-8")
        ).hexdigest().upper(),
        "identity_sha256": digest.upper(),
    }


def _validation_result(
    protocol_id: object,
    case_counts: Mapping[str, int],
    summary: Mapping[str, object],
    checks: Mapping[str, bool],
    errors: Sequence[str],
    warnings: Sequence[str],
) -> dict[str, object]:
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "valid": not errors,
        "protocol_id": protocol_id,
        "development_identity": summary.get("development_identity"),
        "evaluation_identity": summary.get("evaluation_identity"),
        "case_counts": dict(case_counts),
        "checks": dict(checks),
        "errors": list(errors),
        "warnings": list(warnings),
        "unsupported": summary.get("unsupported", {}),
        "inference_started": False,
    }


def _prepare_result(
    summary: Mapping[str, object], protocol_root: Path, *, status: str
) -> dict[str, object]:
    return {
        "schema_version": "full-speech-pipeline-prepare.v1",
        "status": status,
        "protocol_id": summary["protocol_id"],
        "protocol_root": str(protocol_root),
        "development_identity": summary["development_identity"],
        "evaluation_identity": summary["evaluation_identity"],
        "case_counts": summary["case_counts"],
        "audio_duration_sec": summary["audio_duration_sec"],
        "files": checksum_map(protocol_root, exclude=("checksums.json",)),
        "source_protocol_ids": summary["source_protocol_ids"],
        "unsupported": summary["unsupported"],
        "inference_started": False,
    }


def _load_config(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProtocolError(f"protocol config must be a mapping: {path}")
    if value.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ProtocolError(f"unsupported protocol config schema: {value.get('schema_version')}")
    required = {
        "protocol_name",
        "protocol_version",
        "selection_seed",
        "dataset_policy",
        "transcript_source",
        "sources",
    }
    missing = required - set(value)
    if missing:
        raise ProtocolError(f"protocol config missing fields: {sorted(missing)}")
    policy = value["dataset_policy"]
    if not policy.get("installed_only") or policy.get("downloads_allowed"):
        raise ProtocolError("protocol dataset policy must be installed-only with downloads disabled")
    return value


def _absolute_config_path(path: Path | str) -> Path:
    value = Path(path)
    return value.resolve() if value.is_absolute() else (TOOL_ROOT / value).resolve()


def _tool_path(path: object) -> Path:
    value = Path(str(path))
    return value.resolve() if value.is_absolute() else (TOOL_ROOT / value).resolve()


def _relative_tool_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(TOOL_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    if not path.is_file():
        raise ProtocolError(f"required JSONL file is missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ProtocolError(f"JSONL row is not an object: {path}:{line_number}")
            yield value


def _read_csv(path: Path) -> Iterable[dict[str, str]]:
    if not path.is_file():
        raise ProtocolError(f"required CSV file is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def _normalize_source_transcript(text: str) -> str:
    return " ".join(text.casefold().split())


def _checksum_entry_sha(entries: Mapping[str, object], path: str) -> str | None:
    entry = entries.get(path)
    if not isinstance(entry, dict) or not entry.get("sha256"):
        return None
    return str(entry["sha256"]).upper()


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _clean_mapping(row: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _clean_scalar(value) for key, value in row.items()}


def _clean_scalar(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value
