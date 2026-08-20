"""Metadata-only hybrid overlays derived from the frozen controlled benchmark."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterable, Mapping
import uuid

import yaml

from app.hybrid_speaker_attribution.contracts import (
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROTOCOL_ROOT,
    OVERLAY_SCHEMA_VERSION,
    PROTOCOL_SCHEMA_VERSION,
    HybridAttributionError,
    canonical_sha256,
    file_sha256,
    load_config,
)


TIERS = ("smoke", "development", "evaluation")


def prepare_protocol(
    *,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    output_root: Path = DEFAULT_PROTOCOL_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    """Build immutable overlay metadata without copying or changing waveforms."""

    benchmark = benchmark_root.resolve()
    output = output_root.resolve()
    config = load_config(config_path)
    benchmark_summary = _read_json(benchmark / "protocol_summary.json")
    if benchmark_summary.get("benchmark_id") != config["source_benchmark_id"]:
        raise HybridAttributionError("controlled benchmark identity does not match hybrid config")
    config_hash = file_sha256(config_path)
    benchmark_hash = file_sha256(benchmark / "protocol_summary.json")
    protocol_id = "hybrid_speaker_attribution_v1_" + canonical_sha256(
        {"config_sha256": config_hash, "benchmark_summary_sha256": benchmark_hash}
    )[:12].lower()
    if output.exists():
        try:
            existing = validate_protocol(output, benchmark_root=benchmark)
            if existing["protocol_id"] == protocol_id:
                return {**existing, "reused": True}
        except Exception:
            pass
        raise HybridAttributionError(
            f"protocol root already exists but is not the requested valid freeze: {output}"
        )

    all_known_by_tier: dict[str, dict[str, dict[str, object]]] = {}
    raw_by_tier: dict[str, list[dict[str, object]]] = {}
    cases_by_tier: dict[str, dict[str, dict[str, object]]] = {}
    for tier in TIERS:
        cases = _read_jsonl(benchmark / tier / "case_manifest.jsonl")
        overlays = _read_jsonl(benchmark / tier / "identity_overlays.jsonl")
        cases_by_tier[tier] = {str(row["case_id"]): row for row in cases}
        raw_by_tier[tier] = overlays
        known: dict[str, dict[str, object]] = {}
        for row in overlays:
            if row["overlay_id"] != "ALL_KNOWN":
                continue
            for speaker, state in dict(row["speaker_states"]).items():
                clips = list(dict(state).get("reserved_enrollment_clips") or [])
                if not clips:
                    raise HybridAttributionError(f"ALL_KNOWN lacks reserved enrollment: {speaker}")
                known[str(speaker)] = {"clips": clips, "enrolled_id": ""}
        for index, speaker in enumerate(sorted(known), start=1):
            known[speaker]["enrolled_id"] = f"ENROLLED_{tier.upper()}_{index:04d}"
        all_known_by_tier[tier] = known

    staging = output.with_name(f".{output.name}.staging-{uuid.uuid4().hex[:10]}")
    staging.mkdir(parents=True, exist_ok=False)
    counts: dict[str, int] = {}
    inventory: list[dict[str, object]] = []
    for tier in TIERS:
        case_rows = cases_by_tier[tier]
        known_pool = all_known_by_tier[tier]
        emitted: list[dict[str, object]] = []
        unknown_ids = {
            speaker: f"UNKNOWN_REFERENCE_{tier.upper()}_{index:04d}"
            for index, speaker in enumerate(sorted(known_pool), start=1)
        }
        for raw in sorted(raw_by_tier[tier], key=lambda row: (str(row["case_id"]), str(row["overlay_id"]))):
            case_id = str(raw["case_id"])
            overlay_id = str(raw["overlay_id"])
            if case_id not in case_rows:
                raise HybridAttributionError(f"overlay references unknown case: {case_id}")
            case = case_rows[case_id]
            raw_states = dict(raw["speaker_states"])
            speakers = sorted(str(value) for value in case["global_speaker_ids"])
            if sorted(raw_states) != speakers:
                raise HybridAttributionError(f"overlay speaker set mismatch: {case_id}/{overlay_id}")
            states: dict[str, object] = {}
            enrolled_database: list[dict[str, object]] = []
            for speaker in speakers:
                state = str(dict(raw_states[speaker])["identity_state"])
                if state not in {"KNOWN", "UNKNOWN"}:
                    raise HybridAttributionError("overlay identity state must be KNOWN or UNKNOWN")
                states[speaker] = {
                    "identity_state": state,
                    "enrolled_id": known_pool[speaker]["enrolled_id"] if state == "KNOWN" else None,
                    "unknown_reference_id": unknown_ids[speaker] if state == "UNKNOWN" else None,
                }
                if state == "KNOWN":
                    enrolled_database.append(_database_row(speaker, known_pool[speaker], "overlay_known"))
            candidates = [speaker for speaker in sorted(known_pool) if speaker not in speakers]
            candidates.sort(key=lambda speaker: canonical_sha256({"case_id": case_id, "overlay_id": overlay_id, "speaker": speaker}))
            for speaker in candidates[: int(config["background_impostor_enrollments_per_case"])]:
                enrolled_database.append(_database_row(speaker, known_pool[speaker], "background_impostor"))
            emitted.append(
                {
                    "schema_version": OVERLAY_SCHEMA_VERSION,
                    "protocol_id": protocol_id,
                    "benchmark_id": benchmark_summary["benchmark_id"],
                    "tier": tier,
                    "case_id": case_id,
                    "overlay_id": overlay_id,
                    "audio_logical_path": case["audio_logical_path"],
                    "audio_sha256": case["audio_sha256"],
                    "waveform_identity_unchanged": True,
                    "anonymous_der_jer_affected": False,
                    "anonymous_scope": "recording",
                    "local_to_global_speaker": case["local_to_global_speaker"],
                    "speaker_states": states,
                    "enrollment_database": enrolled_database,
                }
            )
        counts[tier] = len(emitted)
        _write_jsonl(staging / tier / "identity_overlays.jsonl", emitted)
        for speaker, value in sorted(known_pool.items()):
            for clip in value["clips"]:
                inventory.append(
                    {
                        "schema_version": "hybrid-enrollment-clip-inventory.v1",
                        "tier": tier,
                        "global_speaker_id": speaker,
                        "enrolled_id": value["enrolled_id"],
                        **dict(clip),
                    }
                )
    _write_csv(staging / "enrollment_clip_inventory.csv", inventory)
    (staging / "selection_config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8", newline="\n"
    )
    summary = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "protocol_id": protocol_id,
        "benchmark_id": benchmark_summary["benchmark_id"],
        "benchmark_summary_sha256": benchmark_hash,
        "config_sha256": config_hash,
        "seed": 3800,
        "overlay_counts": counts,
        "case_counts": dict(benchmark_summary["recording_counts"]),
        "waveforms_copied": False,
        "waveforms_modified": False,
        "anonymous_scope": "recording",
        "development_evaluation_speaker_disjoint": True,
        "full_scientific_run_started": False,
    }
    _write_json(staging / "protocol_summary.json", summary)
    _write_checksums(staging)
    validation = validate_protocol(staging, benchmark_root=benchmark)
    os.replace(staging, output)
    return {**validation, "reused": False}


def validate_protocol(
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    verify_audio_hashes: bool = False,
) -> dict[str, object]:
    root = protocol_root.resolve()
    benchmark = benchmark_root.resolve()
    summary = _read_json(root / "protocol_summary.json")
    if summary.get("schema_version") != PROTOCOL_SCHEMA_VERSION:
        raise HybridAttributionError("unsupported hybrid protocol schema")
    _validate_checksums(root)
    benchmark_summary = _read_json(benchmark / "protocol_summary.json")
    if summary.get("benchmark_id") != benchmark_summary.get("benchmark_id"):
        raise HybridAttributionError("hybrid/controlled benchmark identity mismatch")
    mixture_ids = {
        str(row["source_clip_id"])
        for row in _read_csv(benchmark / "source_clip_inventory.csv")
        if row["usage"] == "mixture"
    }
    enrollment_ids: set[str] = set()
    dev_speakers: set[str] = set()
    eval_speakers: set[str] = set()
    overlay_count = 0
    verified_audio = 0
    verified_paths: dict[Path, str] = {}
    for tier in TIERS:
        cases = {str(row["case_id"]): row for row in _read_jsonl(benchmark / tier / "case_manifest.jsonl")}
        rows = _read_jsonl(root / tier / "identity_overlays.jsonl")
        grouped: dict[str, set[str]] = {}
        for row in rows:
            if row.get("schema_version") != OVERLAY_SCHEMA_VERSION or row.get("protocol_id") != summary["protocol_id"]:
                raise HybridAttributionError("hybrid overlay identity mismatch")
            case_id = str(row["case_id"])
            grouped.setdefault(case_id, set()).add(str(row["overlay_id"]))
            case = cases.get(case_id)
            if case is None or row["audio_sha256"] != case["audio_sha256"]:
                raise HybridAttributionError("overlay waveform identity mismatch")
            if row.get("waveform_identity_unchanged") is not True or row.get("anonymous_der_jer_affected") is not False:
                raise HybridAttributionError("identity overlay changes anonymous diarization science")
            for database_row in row["enrollment_database"]:
                for clip in database_row["reserved_enrollment_clips"]:
                    clip_id = str(clip["source_clip_id"])
                    if clip_id in mixture_ids:
                        raise HybridAttributionError("reserved enrollment/mixture source leakage")
                    enrollment_ids.add(clip_id)
                    if verify_audio_hashes:
                        from app.utils.paths import resolve_data_path_from_logical

                        audio = resolve_data_path_from_logical(str(clip["logical_audio_path"]))
                        if not audio.is_file():
                            raise HybridAttributionError(f"enrollment audio is missing: {audio}")
                        if audio not in verified_paths:
                            verified_paths[audio] = file_sha256(audio)
                        if verified_paths[audio] != str(clip["source_audio_sha256"]).upper():
                            raise HybridAttributionError(f"enrollment audio/hash invalid: {audio}")
                        verified_audio = len(verified_paths)
            speakers = set(str(value) for value in case["global_speaker_ids"])
            if tier == "development":
                dev_speakers.update(speakers)
            elif tier == "evaluation":
                eval_speakers.update(speakers)
            overlay_count += 1
        required = {"ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"}
        if set(grouped) != set(cases) or any(values != required for values in grouped.values()):
            raise HybridAttributionError(f"tier lacks exact overlay coverage: {tier}")
    if dev_speakers & eval_speakers:
        raise HybridAttributionError("development/evaluation speakers overlap")
    return {
        "schema_version": "hybrid-speaker-attribution-validation.v1",
        "protocol_id": summary["protocol_id"],
        "benchmark_id": summary["benchmark_id"],
        "overlays": overlay_count,
        "unique_reserved_enrollment_clips": len(enrollment_ids),
        "enrollment_mixture_intersection": 0,
        "development_evaluation_speaker_intersection": 0,
        "verified_audio_hash_occurrences": verified_audio,
        "valid": True,
    }


def plan_protocol(protocol_root: Path = DEFAULT_PROTOCOL_ROOT) -> dict[str, object]:
    summary = _read_json(protocol_root / "protocol_summary.json")
    return {
        "schema_version": "hybrid-speaker-attribution-plan.v1",
        "protocol_id": summary["protocol_id"],
        "benchmark_id": summary["benchmark_id"],
        "development_cases": summary["case_counts"]["development"],
        "evaluation_cases": summary["case_counts"]["evaluation"],
        "identity_overlays": ["ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"],
        "development_units_per_hybrid_configuration": summary["overlay_counts"]["development"],
        "evaluation_units_per_hybrid_configuration": summary["overlay_counts"]["evaluation"],
        "model_inference_started": False,
    }


def _database_row(speaker: str, value: Mapping[str, object], role: str) -> dict[str, object]:
    return {
        "global_speaker_id": speaker,
        "enrolled_id": value["enrolled_id"],
        "database_role": role,
        "reserved_enrollment_clips": value["clips"],
    }


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HybridAttributionError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["schema_version"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_checksums(root: Path) -> None:
    entries = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "checksums.json":
            entries[path.relative_to(root).as_posix()] = {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
    _write_json(root / "checksums.json", {"schema_version": "hybrid-protocol-checksums.v1", "entries": entries})


def _validate_checksums(root: Path) -> None:
    value = _read_json(root / "checksums.json")
    if value.get("schema_version") != "hybrid-protocol-checksums.v1":
        raise HybridAttributionError("unsupported hybrid protocol checksums")
    for relative, raw in dict(value.get("entries") or {}).items():
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise HybridAttributionError("checksum path escapes protocol root") from exc
        row = dict(raw)
        if not path.is_file() or path.stat().st_size != int(row["bytes"]) or file_sha256(path) != row["sha256"]:
            raise HybridAttributionError(f"hybrid protocol checksum mismatch: {relative}")
