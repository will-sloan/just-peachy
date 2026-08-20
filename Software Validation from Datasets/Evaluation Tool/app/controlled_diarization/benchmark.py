"""Source audit, deterministic mixture construction, and benchmark validation."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.signal import resample_poly
import soundfile as sf

from app.controlled_diarization.contracts import (
    BENCHMARK_VERSION,
    CASE_SCHEMA_VERSION,
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_CONFIG_PATH,
    RECIPE_SCHEMA_VERSION,
    SEED,
    SOURCE_INVENTORY_SCHEMA_VERSION,
    ControlledDiarizationError,
    benchmark_id,
    canonical_json,
    default_generated_root,
    global_speaker_id,
    identity,
    load_config,
    resolve_source_path,
    resolve_source_pool_manifest,
    sha256_file,
    sha256_text,
)
from app.diarization_evaluation.artifacts import (
    write_checksum_manifest,
    write_json_atomic,
    write_jsonl_atomic,
    write_text_atomic,
)
from app.diarization_evaluation.formats import RttmTurn, parse_rttm, parse_uem


TIERS = ("smoke", "development", "evaluation")
CADENCES = ("relaxed", "standard", "rapid")
OVERLAPS = ("none", "backchannel", "moderate")


def audit_source_pool(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    source_pool_manifest: Path | None = None,
) -> dict[str, object]:
    """Audit source feasibility without rendering benchmark audio."""

    config = load_config(config_path)
    source = _load_source_pool(config, source_pool_manifest)
    candidates = _load_candidate_clips(source)
    known = sorted(source["known_speakers"])
    per_speaker = _candidate_summary(candidates, known)
    required_speakers = sum(
        int(config["panel"][tier]["speaker_pool_count"]) for tier in TIERS
    )
    cadence_totals = {
        cadence: sum(int(row[f"{cadence}_clips"]) for row in per_speaker)
        for cadence in CADENCES
    }
    split_feasible = len(known) >= required_speakers
    clip_feasible = all(
        row["mixture_clips"] >= 20 and row["reserved_enrollment_clips"] >= 1
        for row in per_speaker
    )
    preferred_design_feasible = bool(split_feasible and clip_feasible)
    distribution = [int(row["mixture_clips"]) for row in per_speaker]
    report: dict[str, object] = {
        "schema_version": "controlled-diarization-source-audit.v1",
        "benchmark_version": BENCHMARK_VERSION,
        "source_speaker_pool_used": source["protocol_id"],
        "source_pool_manifest": source["manifest_logical_path"],
        "source_path": source["release_root_logical"],
        "canonical_source_manifest": source["validated_logical_path"],
        "canonical_source_manifest_sha256": source["source_manifest_sha256"],
        "speaker_count": len(known),
        "usable_clip_count": len(candidates),
        "speaker_clip_count_distribution": _distribution(distribution),
        "cadence_eligible_clip_counts": cadence_totals,
        "reserved_enrollment_clip_count": len(source["enrollment_rows"]),
        "reserved_enrollment_feasible": all(
            int(row["reserved_enrollment_clips"]) >= 1 for row in per_speaker
        ),
        "development_speaker_candidates": len(known),
        "evaluation_speaker_candidates": len(known),
        "required_disjoint_speakers": required_speakers,
        "speaker_disjoint_split_feasible": split_feasible,
        "preferred_60_development_120_evaluation_feasible": preferred_design_feasible,
        "estimated_generated_audio_sec": (
            sum(int(config["panel"][tier]["recording_count"]) for tier in TIERS)
            * float(config["generation"]["target_duration_sec"])
        ),
        "limitations": [
            "Common Voice speech is prompted/read; only the placement schedule is synthetic.",
            "The backchannel factor is realized as short_overlap because transcript text is not used to assert semantics.",
            "Clip-duration feasibility is based on the canonical Common Voice duration table; Prepare revalidates decoded audio.",
        ],
        "valid": preferred_design_feasible,
    }
    return report


def prepare_benchmark(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    generated_root: Path | None = None,
    source_pool_manifest: Path | None = None,
) -> dict[str, object]:
    """Freeze recipes/references and render missing external benchmark audio."""

    config = load_config(config_path)
    root = benchmark_root.resolve()
    audio_root = (generated_root or default_generated_root()).resolve()
    summary_path = root / "protocol_summary.json"
    if summary_path.is_file():
        materialized_audio_files = _materialize_frozen_audio(root, audio_root)
        validation = validate_benchmark(
            config_path=config_path,
            benchmark_root=root,
            generated_root=audio_root,
            verify_source_hashes=False,
        )
        if not validation["valid"]:
            raise ControlledDiarizationError(
                "an existing controlled benchmark failed validation; create a new version"
            )
        return {
            "schema_version": "controlled-diarization-prepare-result.v1",
            "reused": materialized_audio_files == 0,
            "materialized_audio_files": materialized_audio_files,
            "benchmark_root": str(root),
            "generated_root": str(audio_root),
            "protocol_summary": json.loads(summary_path.read_text(encoding="utf-8")),
            "validation": validation,
        }

    source = _load_source_pool(config, source_pool_manifest)
    candidates = _load_candidate_clips(source)
    audit = audit_source_pool(
        config_path=config_path,
        source_pool_manifest=Path(str(source["manifest_path"])),
    )
    if not audit["valid"]:
        raise ControlledDiarizationError(f"source feasibility audit failed: {audit}")
    root.mkdir(parents=True, exist_ok=True)
    audio_root.mkdir(parents=True, exist_ok=True)
    protocol_id = benchmark_id(config, str(source["source_manifest_sha256"]))
    speaker_rows, split_members = _split_speakers(config, source, candidates)
    cases = _case_specs(config, protocol_id)
    source_by_speaker = _source_by_speaker(candidates)
    used_clip_ids: dict[str, set[str]] = {tier: set() for tier in TIERS}
    appearances: dict[str, Counter[str]] = {tier: Counter() for tier in TIERS}
    pairs: dict[str, Counter[tuple[str, str]]] = {tier: Counter() for tier in TIERS}
    used_source_rows: dict[str, dict[str, object]] = {}
    case_rows: dict[str, list[dict[str, object]]] = {tier: [] for tier in TIERS}
    assignment_rows: list[dict[str, object]] = []

    ordered_cases = sorted(cases, key=_assignment_priority)
    for spec in ordered_cases:
        tier = str(spec["tier"])
        excluded: set[str] = set()
        for attempt in range(24):
            used_before = set(used_clip_ids[tier])
            selected = _assign_case_speakers(
                spec,
                split_members[tier],
                source_by_speaker,
                used_clip_ids[tier],
                appearances[tier],
                pairs[tier],
                excluded_speakers=excluded,
            )
            local_labels = {
                speaker: f"SPK{index:02d}" for index, speaker in enumerate(selected)
            }
            try:
                recipe, prepared_audio, clip_rows = _schedule_case(
                    config,
                    protocol_id,
                    spec,
                    selected,
                    local_labels,
                    source_by_speaker,
                    used_clip_ids[tier],
                )
                break
            except ControlledDiarizationError as exc:
                used_clip_ids[tier].clear()
                used_clip_ids[tier].update(used_before)
                match = re.search(r"speaker (cvspk_[0-9a-f]+) exhausted", str(exc))
                if match:
                    excluded.add(match.group(1))
                else:
                    excluded.update(selected)
                if attempt == 23:
                    raise
        else:  # pragma: no cover - loop always breaks or raises
            raise ControlledDiarizationError(f"could not schedule case {spec['case_id']}")
        for row in clip_rows:
            used_source_rows[str(row["source_clip_id"])] = row
        audio_dir = audio_root / tier / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / f"{spec['case_id']}.wav"
        render = _render_case(config, recipe, prepared_audio, audio_path)
        recipe["mix_peak_protection_gain_db"] = render["mix_peak_protection_gain_db"]
        recipe["output_audio_sha256"] = render["audio_sha256"]
        recipe["output_pcm_sha256"] = render["pcm_sha256"]
        recipe["output_duration_samples"] = render["duration_samples"]
        recipe["output_duration_sec"] = render["duration_sec"]
        recipe["recipe_sha256"] = sha256_text(
            canonical_json({key: value for key, value in recipe.items() if key != "recipe_sha256"})
        )
        tier_root = root / tier
        reference_dir = tier_root / "references"
        recipe_dir = tier_root / "recipes"
        reference_dir.mkdir(parents=True, exist_ok=True)
        recipe_dir.mkdir(parents=True, exist_ok=True)
        recipe_path = recipe_dir / f"{spec['case_id']}.json"
        reference_path = reference_dir / f"{spec['case_id']}.rttm"
        uem_path = reference_dir / f"{spec['case_id']}.uem"
        write_json_atomic(recipe_path, recipe)
        _write_reference_rttm(reference_path, recipe)
        write_text_atomic(
            uem_path,
            f"{spec['case_id']} 1 0.000000 {float(render['duration_sec']):.6f}\n",
        )
        stats = _case_statistics(recipe)
        row = {
            "schema_version": CASE_SCHEMA_VERSION,
            **spec,
            "benchmark_id": protocol_id,
            "speech_style": "prompted_read",
            "turn_pattern": "synthetic",
            "timing_reference": "synthetic_placement_timing_reference",
            "evaluation_locked": tier == "evaluation",
            "reference_speaker_count": len(selected),
            "global_speaker_ids": selected,
            "local_to_global_speaker": {
                local_labels[speaker]: speaker for speaker in selected
            },
            "audio_logical_path": f"{tier}/audio/{spec['case_id']}.wav",
            "audio_sha256": render["audio_sha256"],
            "pcm_sha256": render["pcm_sha256"],
            "duration_sec": render["duration_sec"],
            "recipe_path": recipe_path.relative_to(root).as_posix(),
            "recipe_sha256": recipe["recipe_sha256"],
            "reference_rttm_path": reference_path.relative_to(root).as_posix(),
            "reference_uem_path": uem_path.relative_to(root).as_posix(),
            "sample_rate_hz": int(config["sample_rate_hz"]),
            "channels": int(config["channels"]),
            "reference_statistics": stats,
        }
        case_rows[tier].append(row)
        assignment_rows.extend(
            {
                "tier": tier,
                "case_id": spec["case_id"],
                "global_speaker_id": speaker,
                "reference_label": local_labels[speaker],
                "turn_cadence": spec["turn_cadence"],
                "overlap_profile": spec["overlap_profile"],
            }
            for speaker in selected
        )
        for speaker in selected:
            appearances[tier][speaker] += 1
        for pair in itertools.combinations(sorted(selected), 2):
            pairs[tier][pair] += 1

    for tier in TIERS:
        case_rows[tier].sort(key=lambda row: str(row["case_id"]))
        write_jsonl_atomic(root / tier / "case_manifest.jsonl", case_rows[tier])
        _write_identity_overlays(
            root / tier / "identity_overlays.jsonl",
            case_rows[tier],
            source["enrollment_by_global"],
        )

    reserved_rows = _reserved_inventory_rows(source, split_members)
    inventory_rows = sorted(
        [*reserved_rows, *used_source_rows.values()],
        key=lambda row: (str(row["usage"]), str(row["global_speaker_id"]), str(row["source_clip_id"])),
    )
    _write_csv(root / "source_speaker_inventory.csv", speaker_rows)
    _write_csv(root / "source_clip_inventory.csv", inventory_rows)
    _write_csv(root / "case_speaker_assignments.csv", assignment_rows)
    appearance_rows, pair_rows = _balance_rows(case_rows)
    _write_csv(root / "speaker_appearance_counts.csv", appearance_rows)
    _write_csv(root / "speaker_pair_cooccurrence.csv", pair_rows)
    _write_review_package(root, case_rows, config)
    _write_protected_assets(root, protocol_id, speaker_rows, inventory_rows, case_rows)
    config_copy = yaml_safe_dump(config)
    write_text_atomic(root / "benchmark_config.yaml", config_copy)
    write_json_atomic(root / "source_audit.json", audit)
    summary = _protocol_summary(
        config,
        protocol_id,
        source,
        speaker_rows,
        inventory_rows,
        case_rows,
        audio_root,
    )
    write_json_atomic(root / "protocol_summary.json", summary)
    validation = validate_benchmark(
        config_path=config_path,
        benchmark_root=root,
        generated_root=audio_root,
        verify_source_hashes=False,
        write_report=False,
    )
    write_json_atomic(root / "validation_report.json", validation)
    write_checksum_manifest(root, exclude=("benchmark_files.json",))
    # A final report includes the checksum-bound metadata package.
    validation = validate_benchmark(
        config_path=config_path,
        benchmark_root=root,
        generated_root=audio_root,
        verify_source_hashes=False,
        write_report=False,
    )
    write_json_atomic(root / "validation_report.json", validation)
    write_checksum_manifest(root, exclude=("benchmark_files.json",))
    return {
        "schema_version": "controlled-diarization-prepare-result.v1",
        "reused": False,
        "benchmark_root": str(root),
        "generated_root": str(audio_root),
        "protocol_summary": summary,
        "validation": validation,
    }


def validate_benchmark(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    generated_root: Path | None = None,
    verify_source_hashes: bool = False,
    write_report: bool = True,
) -> dict[str, object]:
    """Validate frozen manifests, recipes, audio, references, balance, and leakage."""

    config = load_config(config_path)
    root = benchmark_root.resolve()
    audio_root = (generated_root or default_generated_root()).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    required = (
        "benchmark_config.yaml",
        "source_speaker_inventory.csv",
        "source_clip_inventory.csv",
        "speaker_appearance_counts.csv",
        "speaker_pair_cooccurrence.csv",
        "protocol_summary.json",
        "protected_evaluation_assets.json",
    )
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing metadata artifact: {relative}")
    if errors:
        report = _validation_report(errors, warnings, {}, {})
        if write_report:
            write_json_atomic(root / "validation_report.json", report)
        return report

    speakers = _read_csv(root / "source_speaker_inventory.csv")
    clips = _read_csv(root / "source_clip_inventory.csv")
    by_tier_speakers = {
        tier: {row["global_speaker_id"] for row in speakers if row["tier"] == tier}
        for tier in TIERS
    }
    if by_tier_speakers["development"] & by_tier_speakers["evaluation"]:
        errors.append("development and evaluation speaker pools overlap")
    mixture_ids = {row["source_clip_id"] for row in clips if row["usage"] == "mixture"}
    enrollment_ids = {
        row["source_clip_id"] for row in clips if row["usage"] == "reserved_enrollment"
    }
    if mixture_ids & enrollment_ids:
        errors.append("reserved enrollment clips overlap mixture clips")
    clip_tiers: dict[str, set[str]] = defaultdict(set)
    for row in clips:
        if row["usage"] == "mixture":
            clip_tiers[row["source_clip_id"]].add(row["tier"])
    if any(len(tiers) > 1 for tiers in clip_tiers.values()):
        errors.append("source clips cross benchmark tiers")
    case_counts: dict[str, int] = {}
    factor_counts: dict[str, Counter[tuple[str, str, str]]] = {}
    seen_case_ids: set[str] = set()
    for tier in TIERS:
        manifest_path = root / tier / "case_manifest.jsonl"
        if not manifest_path.is_file():
            errors.append(f"missing {tier} case manifest")
            continue
        rows = _read_jsonl(manifest_path)
        case_counts[tier] = len(rows)
        factor_counts[tier] = Counter()
        expected = int(config["panel"][tier]["recording_count"])
        if len(rows) != expected:
            errors.append(f"{tier} case count {len(rows)} != {expected}")
        for row in rows:
            case_id = str(row.get("case_id") or "")
            if not case_id or case_id in seen_case_ids:
                errors.append(f"duplicate or empty case ID: {case_id}")
            seen_case_ids.add(case_id)
            if int(row["reference_speaker_count"]) not in {1, 2, 3, 5}:
                errors.append(f"{case_id}: unsupported speaker count")
            factor_counts[tier][
                (
                    str(row["reference_speaker_count"]),
                    str(row["turn_cadence"]),
                    str(row["overlap_profile"]),
                )
            ] += 1
            recipe_path = root / str(row["recipe_path"])
            reference_path = root / str(row["reference_rttm_path"])
            uem_path = root / str(row["reference_uem_path"])
            for label, path in (
                ("recipe", recipe_path),
                ("RTTM", reference_path),
                ("UEM", uem_path),
            ):
                if not path.is_file():
                    errors.append(f"{case_id}: missing {label}")
            if not recipe_path.is_file():
                continue
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            expected_recipe_hash = sha256_text(
                canonical_json(
                    {key: value for key, value in recipe.items() if key != "recipe_sha256"}
                )
            )
            if recipe.get("recipe_sha256") != expected_recipe_hash:
                errors.append(f"{case_id}: recipe hash mismatch")
            placements = recipe.get("placements") or []
            labels = {str(value) for value in row["local_to_global_speaker"]}
            turns = Counter(str(value.get("reference_speaker")) for value in placements)
            if set(turns) != labels:
                errors.append(f"{case_id}: recipe/reference speaker mismatch")
            if int(row["reference_speaker_count"]) > 1 and any(
                turns[label] < int(config["generation"]["minimum_non_adjacent_turns_per_speaker"])
                for label in labels
            ):
                errors.append(f"{case_id}: speaker recurrence requirement failed")
            if int(row["reference_speaker_count"]) > 1 and any(
                str(left.get("reference_speaker")) == str(right.get("reference_speaker"))
                for left, right in zip(placements, placements[1:])
            ):
                errors.append(f"{case_id}: adjacent turns repeat the same speaker")
            duration_samples = int(recipe["output_duration_samples"])
            for turn in placements:
                start = int(turn["global_start_sample"])
                end = int(turn["global_end_sample"])
                if start < 0 or end <= start or end > duration_samples:
                    errors.append(f"{case_id}: invalid placement bounds")
            overlap_duration = float(row["reference_statistics"]["overlap_duration_sec"])
            if row["overlap_profile"] == "none" and overlap_duration > 1e-6:
                errors.append(f"{case_id}: no-overlap case contains overlap")
            if row["overlap_profile"] != "none" and overlap_duration <= 0:
                errors.append(f"{case_id}: overlap case contains no overlap")
            if reference_path.is_file():
                try:
                    observed_rttm = parse_rttm(reference_path)
                    expected_rttm = parse_rttm(
                        "\n".join(
                            RttmTurn(
                                recording_id=case_id,
                                channel="1",
                                start_sec=int(turn["global_start_sample"])
                                / int(recipe["sample_rate_hz"]),
                                end_sec=int(turn["global_end_sample"])
                                / int(recipe["sample_rate_hz"]),
                                speaker_label=str(turn["reference_speaker"]),
                            ).to_line()
                            for turn in placements
                        ),
                        from_text=True,
                    )
                    if observed_rttm != expected_rttm:
                        errors.append(f"{case_id}: RTTM does not match exact recipe placements")
                except Exception as exc:
                    errors.append(f"{case_id}: invalid RTTM: {exc}")
            if uem_path.is_file():
                try:
                    observed_uem = parse_uem(uem_path)
                    expected_end = round(duration_samples / int(recipe["sample_rate_hz"]), 6)
                    if (
                        len(observed_uem) != 1
                        or observed_uem[0].recording_id != case_id
                        or observed_uem[0].channel != "1"
                        or observed_uem[0].start_sec != 0.0
                        or observed_uem[0].end_sec != expected_end
                    ):
                        errors.append(f"{case_id}: UEM does not match the recipe duration")
                except Exception as exc:
                    errors.append(f"{case_id}: invalid UEM: {exc}")
            audio_path = audio_root / str(row["audio_logical_path"])
            if not audio_path.is_file():
                errors.append(f"{case_id}: generated audio is missing")
                continue
            info = sf.info(audio_path)
            if info.samplerate != int(config["sample_rate_hz"]) or info.channels != 1:
                errors.append(f"{case_id}: generated audio format mismatch")
            if abs(float(info.duration) - float(row["duration_sec"])) > 1.0 / info.samplerate:
                errors.append(f"{case_id}: generated audio duration mismatch")
            if not (
                float(config["generation"]["minimum_duration_sec"])
                <= float(info.duration)
                <= float(config["generation"]["maximum_duration_sec"])
            ):
                errors.append(
                    f"{case_id}: generated audio is outside the 45-75 second range"
                )
            if sha256_file(audio_path) != row["audio_sha256"]:
                errors.append(f"{case_id}: generated audio hash mismatch")
            samples, _ = sf.read(audio_path, dtype="float32", always_2d=False)
            if not np.isfinite(samples).all():
                errors.append(f"{case_id}: generated audio contains NaN/Inf")
            if np.max(np.abs(samples), initial=0.0) > 1.00001:
                errors.append(f"{case_id}: generated audio clips")
            if _wav_pcm_sha256(audio_path) != row["pcm_sha256"]:
                errors.append(f"{case_id}: generated PCM hash mismatch")

    for tier, repeats in (("development", 2), ("evaluation", 4)):
        counts = factor_counts.get(tier, Counter())
        for speaker_count in (2, 3, 5):
            for cadence in CADENCES:
                for overlap in OVERLAPS:
                    observed = counts[(str(speaker_count), cadence, overlap)]
                    if observed != repeats:
                        errors.append(
                            f"{tier}: factorial cell {speaker_count}/{cadence}/{overlap} "
                            f"contains {observed}, expected {repeats}"
                        )
    if verify_source_hashes:
        for row in clips:
            path = resolve_source_path(row["logical_audio_path"])
            if not path.is_file() or sha256_file(path).upper() != row["source_audio_sha256"].upper():
                errors.append(f"source hash mismatch: {row['source_clip_id']}")
    clip_reuse = Counter(
        turn["source_clip_id"]
        for tier in TIERS
        for case in _read_jsonl(root / tier / "case_manifest.jsonl")
        for turn in json.loads((root / case["recipe_path"]).read_text(encoding="utf-8"))[
            "placements"
        ]
    )
    reused = {key: value for key, value in clip_reuse.items() if value > 1}
    if reused:
        errors.append(f"exact source clips were reused: {len(reused)}")
    balance = {
        "case_counts": case_counts,
        "source_speaker_counts": {tier: len(value) for tier, value in by_tier_speakers.items()},
        "unique_mixture_clips": len(mixture_ids),
        "reserved_enrollment_clips": len(enrollment_ids),
        "reused_source_clips": len(reused),
    }
    report = _validation_report(errors, warnings, case_counts, balance)
    if write_report:
        write_json_atomic(root / "validation_report.json", report)
    return report


def benchmark_plan(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    generated_root: Path | None = None,
    pipelines: Sequence[str] = (),
    tier: str = "evaluation",
) -> dict[str, object]:
    """Return a model-free exact execution plan."""

    from app.controlled_diarization.contracts import load_pipeline_registry

    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    unknown = sorted(set(pipelines) - set(registry))
    if unknown:
        raise ControlledDiarizationError(f"unknown pipeline IDs: {unknown}")
    if tier not in TIERS:
        raise ControlledDiarizationError(f"unsupported tier: {tier}")
    root = benchmark_root.resolve()
    summary = (
        json.loads((root / "protocol_summary.json").read_text(encoding="utf-8"))
        if (root / "protocol_summary.json").is_file()
        else None
    )
    case_count = (
        len(_read_jsonl(root / tier / "case_manifest.jsonl"))
        if (root / tier / "case_manifest.jsonl").is_file()
        else int(config["panel"][tier]["recording_count"])
    )
    return {
        "schema_version": "controlled-diarization-plan.v1",
        "protocol": summary.get("benchmark_id") if summary else "NOT_PREPARED",
        "benchmark_version": BENCHMARK_VERSION,
        "benchmark_root": str(root),
        "generated_root": str((generated_root or default_generated_root()).resolve()),
        "tier": tier,
        "development_cases": int(config["panel"]["development"]["recording_count"]),
        "evaluation_cases": int(config["panel"]["evaluation"]["recording_count"]),
        "smoke_cases": int(config["panel"]["smoke"]["recording_count"]),
        "speaker_counts": [1, *config["factors"]["speaker_counts"]],
        "turn_cadence": list(config["factors"]["turn_cadence"]),
        "overlap_profiles": list(config["factors"]["overlap_profiles"]),
        "generated_audio_hours": (
            float(summary["total_generated_audio_sec"]) / 3600.0 if summary else None
        ),
        "selected_pipelines": list(pipelines),
        "pipeline_selection_required": not bool(pipelines),
        "pipeline_definitions": [registry[value].to_jsonable() for value in pipelines],
        "cases_in_selected_tier": case_count,
        "expected_inference_units": case_count * len(pipelines),
        "scientific_inference_started": False,
    }


def reconstruct_recipe(recipe_path: Path, output_path: Path) -> dict[str, object]:
    """Re-render one frozen recipe and return byte/canonical-sample identities."""

    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    sample_rate = int(recipe["sample_rate_hz"])
    placements: list[tuple[dict[str, object], np.ndarray]] = []
    for placement in recipe["placements"]:
        path = resolve_source_path(str(placement["logical_audio_path"]))
        audio, metadata = _prepare_source_audio(path, sample_rate, recipe["trim_policy"])
        start = int(placement["source_crop_start_sample"])
        end = int(placement["source_crop_end_sample"])
        # Frozen crops are expressed in the prepared/resampled waveform timebase.
        audio = audio[start:end]
        gain = 10.0 ** (float(placement["source_gain_db"]) / 20.0)
        placements.append((dict(placement), audio * gain))
        if metadata["source_audio_sha256"].upper() != str(placement["source_audio_sha256"]).upper():
            raise ControlledDiarizationError("recipe source hash mismatch")
    length = int(recipe["output_duration_samples"])
    mix = np.zeros(length, dtype=np.float64)
    for placement, audio in placements:
        start = int(placement["global_start_sample"])
        end = min(length, start + len(audio))
        mix[start:end] += audio[: end - start]
    mix *= 10.0 ** (float(recipe["mix_peak_protection_gain_db"]) / 20.0)
    _write_wav_atomic(output_path, mix.astype(np.float32), sample_rate)
    return {
        "audio_sha256": sha256_file(output_path),
        "pcm_sha256": _wav_pcm_sha256(output_path),
        "duration_samples": len(mix),
    }


def _materialize_frozen_audio(benchmark_root: Path, generated_root: Path) -> int:
    """Reconstruct only absent/changed external WAVs from already-frozen recipes."""

    materialized = 0
    for tier in TIERS:
        manifest_path = benchmark_root / tier / "case_manifest.jsonl"
        if not manifest_path.is_file():
            continue
        for case in _read_jsonl(manifest_path):
            output = generated_root / str(case["audio_logical_path"])
            if output.is_file() and sha256_file(output) == str(case["audio_sha256"]):
                continue
            recipe_path = benchmark_root / str(case["recipe_path"])
            if not recipe_path.is_file():
                raise ControlledDiarizationError(
                    f"cannot materialize {case['case_id']}: frozen recipe is missing"
                )
            reconstructed = reconstruct_recipe(recipe_path, output)
            if (
                reconstructed["audio_sha256"] != case["audio_sha256"]
                or reconstructed["pcm_sha256"] != case["pcm_sha256"]
            ):
                raise ControlledDiarizationError(
                    f"cannot materialize {case['case_id']}: reconstructed audio hash mismatch"
                )
            materialized += 1
    return materialized


def _load_source_pool(
    config: Mapping[str, object], source_pool_manifest: Path | None
) -> dict[str, object]:
    manifest_path = resolve_source_pool_manifest(source_pool_manifest, config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "speaker-protocol-manifest-index.v1":
        raise ControlledDiarizationError("unsupported source speaker-pool manifest")
    protocol_id = str(manifest.get("protocol_id") or "")
    source_root = manifest_path.parent
    speaker_inventory_path = source_root / "speaker_inventory.tsv"
    source_selection_path = source_root / "source_selection.tsv"
    for path in (speaker_inventory_path, source_selection_path):
        if not path.is_file():
            raise FileNotFoundError(f"source speaker-pool support file is missing: {path}")
    inventory = pd.read_csv(speaker_inventory_path, sep="\t", dtype=str).fillna("")
    known = sorted(inventory.loc[inventory["speaker_role"] == "known", "speaker_key"].tolist())
    selected = pd.read_csv(source_selection_path, sep="\t", dtype=str).fillna("")
    enrollment = selected[
        (selected["speaker_role"] == "known")
        & (selected["protocol_split"] == "enrollment")
        & selected["speaker_key"].isin(known)
    ].copy()
    enrollment_names = set(enrollment["logical_audio_path"].map(lambda value: Path(value).name))
    first_logical = Path(str(selected.iloc[0]["logical_audio_path"]))
    release_en = first_logical.parent.parent
    validated_logical = release_en / str(manifest["source_manifest"]["logical_path"])
    validated_path = resolve_source_path(validated_logical.as_posix())
    durations_path = validated_path.parent / "clip_durations.tsv"
    release_root = resolve_source_path(first_logical.parents[3].as_posix())
    if not validated_path.is_file() or not durations_path.is_file():
        raise FileNotFoundError("canonical Common Voice metadata or duration table is unavailable")
    expected_source_hash = str(manifest["source_manifest"]["sha256"])
    if sha256_file(validated_path).upper() != expected_source_hash.upper():
        raise ControlledDiarizationError("canonical Common Voice validated.tsv hash changed")
    enrollment_by_global: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in enrollment.to_dict("records"):
        speaker = global_speaker_id(str(row["speaker_key"]))
        enrollment_by_global[speaker].append(
            {
                "source_clip_id": str(row["source_recording_id"]),
                "logical_audio_path": str(row["logical_audio_path"]),
                "source_audio_sha256": str(row["audio_sha256"]).upper(),
                "duration_sec": float(row["duration_sec"]),
            }
        )
    return {
        "manifest_path": manifest_path,
        "manifest_logical_path": manifest_path.relative_to(manifest_path.parents[3]).as_posix(),
        "manifest": manifest,
        "protocol_id": protocol_id,
        "source_manifest_sha256": expected_source_hash.upper(),
        "known_speakers": known,
        "inventory": inventory,
        "enrollment_rows": enrollment.to_dict("records"),
        "enrollment_names": enrollment_names,
        "enrollment_by_global": dict(enrollment_by_global),
        "validated_path": validated_path,
        "validated_logical_path": validated_logical.as_posix(),
        "durations_path": durations_path,
        "release_en": resolve_source_path(release_en.as_posix()),
        "release_root": release_root,
        "release_root_logical": first_logical.parents[3].as_posix(),
    }


def _load_candidate_clips(source: Mapping[str, object]) -> list[dict[str, object]]:
    known = set(source["known_speakers"])
    protocol_id = str(source["protocol_id"])
    validated = pd.read_csv(
        source["validated_path"],
        sep="\t",
        usecols=["client_id", "path", "sentence", "sentence_id", "age", "gender", "accents"],
        dtype=str,
        low_memory=False,
    ).fillna("")
    validated["source_protocol_speaker_key"] = validated["client_id"].map(
        lambda value: "spk_cv60p_"
        + hashlib.sha256(f"{protocol_id}|{value}|3800".encode("utf-8")).hexdigest()[:20]
    )
    validated = validated[validated["source_protocol_speaker_key"].isin(known)].copy()
    durations = pd.read_csv(source["durations_path"], sep="\t", dtype={"clip": str})
    durations = durations[durations["clip"].isin(set(validated["path"]))]
    validated = validated.merge(durations, left_on="path", right_on="clip", how="inner")
    clips_root = Path(source["release_en"]) / "clips"
    validated["exists"] = validated["path"].map(lambda value: (clips_root / value).is_file())
    validated = validated[validated["exists"]]
    validated = validated[~validated["path"].isin(set(source["enrollment_names"]))]
    validated["duration_sec"] = validated["duration[ms]"].astype(float) / 1000.0
    validated = validated[
        (validated["duration_sec"] >= 0.55) & (validated["duration_sec"] <= 12.0)
    ]
    release_logical = Path(str(source["manifest"]["source_manifest"]["logical_path"]))
    del release_logical  # provenance is carried by source[validated_path]; audio uses stable root below.
    logical_prefix = Path(
        "Raw Datasets (Not formatted)/Common Voice/cv-corpus-26.0-2026-06-12/prepared/en/clips"
    )
    output: list[dict[str, object]] = []
    for row in validated.to_dict("records"):
        source_key = str(row["source_protocol_speaker_key"])
        filename = str(row["path"])
        transcript = " ".join(str(row["sentence"]).casefold().split())
        output.append(
            {
                "global_speaker_id": global_speaker_id(source_key),
                "source_protocol_speaker_key": source_key,
                "source_clip_id": f"cvclip_{sha256_text(filename)[:20]}",
                "filename": filename,
                "logical_audio_path": (logical_prefix / filename).as_posix(),
                "duration_sec": float(row["duration_sec"]),
                "transcript_sha256": sha256_text(transcript).upper(),
                "sentence_id_hash": sha256_text(str(row["sentence_id"]))[:20],
                "age_category": str(row["age"]),
                "gender": str(row["gender"]),
                "accent_group": str(row["accents"]),
                "selection_rank": sha256_text(
                    f"{BENCHMARK_VERSION}|{SEED}|{source_key}|{filename}"
                ),
            }
        )
    output.sort(key=lambda row: (str(row["global_speaker_id"]), str(row["selection_rank"])))
    return output


def _candidate_summary(
    candidates: Sequence[Mapping[str, object]], known_speakers: Sequence[str]
) -> list[dict[str, object]]:
    by_speaker = _source_by_speaker(candidates)
    rows = []
    for source_key in known_speakers:
        speaker = global_speaker_id(source_key)
        clips = by_speaker.get(speaker, [])
        row: dict[str, object] = {
            "global_speaker_id": speaker,
            "mixture_clips": len(clips),
            "reserved_enrollment_clips": 5,
        }
        for cadence in CADENCES:
            row[f"{cadence}_clips"] = sum(
                _cadence_accepts(cadence, float(clip["duration_sec"])) for clip in clips
            )
        rows.append(row)
    return rows


def _split_speakers(
    config: Mapping[str, object],
    source: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, list[str]]]:
    by_speaker = _source_by_speaker(candidates)
    source_keys = list(source["known_speakers"])
    required = {tier: int(config["panel"][tier]["speaker_pool_count"]) for tier in TIERS}
    if sum(required.values()) > len(source_keys):
        raise ControlledDiarizationError("source pool lacks enough disjoint speakers")
    speakers = [global_speaker_id(value) for value in source_keys]
    speakers.sort(
        key=lambda speaker: (
            -sum(
                float(row["duration_sec"])
                for row in by_speaker.get(speaker, [])
                if _cadence_accepts("rapid", float(row["duration_sec"]))
            ),
            sha256_text(f"split|{SEED}|{speaker}"),
        )
    )
    # The eight-case smoke deliberately covers three rapid configurations.
    # Give its small isolated pool the highest rapid-utterance capacities, then
    # distribute the remaining capacity proportionally across dev/eval.
    smoke_count = required["smoke"]
    split_members: dict[str, list[str]] = {tier: [] for tier in TIERS}
    split_members["smoke"] = speakers[:smoke_count]
    remaining_speakers = speakers[smoke_count:]
    slots = sorted(
        (
            ((index + 0.5) / count, sha256_text(f"slot|{tier}|{index}"), tier)
            for tier, count in required.items()
            if tier != "smoke"
            for index in range(count)
        )
    )
    for speaker, (_position, _tie, tier) in zip(
        remaining_speakers[: len(slots)], slots, strict=True
    ):
        split_members[tier].append(speaker)
    source_by_global = {global_speaker_id(value): value for value in source_keys}
    rows: list[dict[str, object]] = []
    for tier in TIERS:
        split_members[tier].sort()
        for speaker in split_members[tier]:
            clips = by_speaker[speaker]
            rows.append(
                {
                    "schema_version": SOURCE_INVENTORY_SCHEMA_VERSION,
                    "benchmark_version": BENCHMARK_VERSION,
                    "tier": tier,
                    "global_speaker_id": speaker,
                    "source_protocol_speaker_key": source_by_global[speaker],
                    "mixture_candidate_clips": len(clips),
                    "reserved_enrollment_clips": len(
                        source["enrollment_by_global"].get(speaker, [])
                    ),
                    "rapid_candidate_clips": sum(
                        _cadence_accepts("rapid", float(row["duration_sec"])) for row in clips
                    ),
                    "standard_candidate_clips": sum(
                        _cadence_accepts("standard", float(row["duration_sec"])) for row in clips
                    ),
                    "relaxed_candidate_clips": sum(
                        _cadence_accepts("relaxed", float(row["duration_sec"])) for row in clips
                    ),
                    "evaluation_locked": tier == "evaluation",
                }
            )
    return rows, split_members


def _case_specs(config: Mapping[str, object], protocol_id: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for tier, replicates, controls in (
        ("development", 2, 6),
        ("evaluation", 4, 12),
    ):
        for speaker_count in (2, 3, 5):
            for cadence in CADENCES:
                for overlap in OVERLAPS:
                    for replicate in range(1, replicates + 1):
                        factors = {
                            "tier": tier,
                            "speaker_count": speaker_count,
                            "turn_cadence": cadence,
                            "overlap_profile": overlap,
                            "replicate": replicate,
                        }
                        rows.append(
                            {
                                **factors,
                                "case_id": identity("cd", {"benchmark": protocol_id, **factors}),
                                "scientific": True,
                                "control_kind": "multi_speaker_factorial",
                            }
                        )
        for index in range(controls):
            cadence = CADENCES[index % len(CADENCES)]
            factors = {
                "tier": tier,
                "speaker_count": 1,
                "turn_cadence": cadence,
                "overlap_profile": "none",
                "replicate": index + 1,
            }
            rows.append(
                {
                    **factors,
                    "case_id": identity("cd", {"benchmark": protocol_id, **factors}),
                    "scientific": True,
                    "control_kind": "single_speaker_oversegmentation_control",
                }
            )
    smoke_specs = (
        (1, "relaxed", "none"),
        (1, "rapid", "none"),
        (2, "standard", "none"),
        (2, "standard", "backchannel"),
        (3, "rapid", "none"),
        (3, "relaxed", "moderate"),
        (5, "rapid", "backchannel"),
        (5, "standard", "moderate"),
    )
    for index, (speaker_count, cadence, overlap) in enumerate(smoke_specs, 1):
        factors = {
            "tier": "smoke",
            "speaker_count": speaker_count,
            "turn_cadence": cadence,
            "overlap_profile": overlap,
            "replicate": index,
        }
        rows.append(
            {
                **factors,
                "case_id": identity("cdsmoke", {"benchmark": protocol_id, **factors}),
                "scientific": False,
                "control_kind": "non_scientific_smoke",
            }
        )
    return rows


def _assignment_priority(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        str(row["tier"]),
        {"rapid": 0, "standard": 1, "relaxed": 2}[str(row["turn_cadence"])],
        int(row["speaker_count"]),
        str(row["overlap_profile"]),
        int(row["replicate"]),
    )


def _assign_case_speakers(
    spec: Mapping[str, object],
    members: Sequence[str],
    source_by_speaker: Mapping[str, Sequence[Mapping[str, object]]],
    used_clip_ids: set[str],
    appearances: Counter[str],
    pairs: Counter[tuple[str, str]],
    excluded_speakers: set[str] | None = None,
) -> list[str]:
    count = int(spec["speaker_count"])
    cadence = str(spec["turn_cadence"])
    active_target = {"rapid": 48.0, "standard": 52.0, "relaxed": 46.0}[cadence]
    if spec["overlap_profile"] == "moderate":
        active_target *= 1.15
    elif spec["overlap_profile"] == "backchannel":
        active_target *= 1.05
    # Metadata durations precede deterministic boundary trimming.  Keep a
    # conservative reserve so a selected speaker cannot exhaust its natural
    # complete utterances during rendering.
    minimum_capacity = active_target * 1.12 / count
    selected: list[str] = []
    for _ in range(count):
        candidates = []
        for speaker in members:
            if speaker in selected or speaker in (excluded_speakers or set()):
                continue
            remaining = [
                row
                for row in source_by_speaker.get(speaker, [])
                if row["source_clip_id"] not in used_clip_ids
                and _cadence_accepts(cadence, float(row["duration_sec"]), realized=True)
            ]
            capacity = sum(float(row["duration_sec"]) for row in remaining)
            if capacity < minimum_capacity:
                continue
            pair_pressure = sum(pairs[tuple(sorted((speaker, other)))] for other in selected)
            score = (
                appearances[speaker],
                pair_pressure,
                -capacity,
                sha256_text(f"speaker-case|{spec['case_id']}|{speaker}"),
            )
            candidates.append((score, speaker))
        if not candidates:
            raise ControlledDiarizationError(
                f"source capacity cannot support case {spec['case_id']} ({cadence})"
            )
        selected.append(min(candidates)[1])
    return sorted(selected, key=lambda value: sha256_text(f"local|{spec['case_id']}|{value}"))


def _schedule_case(
    config: Mapping[str, object],
    protocol_id: str,
    spec: Mapping[str, object],
    speakers: Sequence[str],
    local_labels: Mapping[str, str],
    source_by_speaker: Mapping[str, Sequence[Mapping[str, object]]],
    used_clip_ids: set[str],
) -> tuple[dict[str, object], list[tuple[dict[str, object], np.ndarray]], list[dict[str, object]]]:
    sample_rate = int(config["sample_rate_hz"])
    generation = config["generation"]
    cadence = str(spec["turn_cadence"])
    overlap_profile = str(spec["overlap_profile"])
    randomizer = random.Random(int(sha256_text(f"{SEED}|{spec['case_id']}")[:16], 16))
    available: dict[str, list[Mapping[str, object]]] = {}
    desired_duration = {
        "rapid": 1.5,
        "standard": 2.6,
        "relaxed": {1: 5.0, 2: 4.5, 3: 3.8, 5: 3.0}.get(len(speakers), 3.5),
    }[cadence]
    maximum_realized_duration = {
        "rapid": 4.0,
        "standard": 4.0 if len(speakers) == 5 else 6.0,
        "relaxed": {1: 10.0, 2: 8.0, 3: 5.5, 5: 4.5}.get(len(speakers), 5.5),
    }[cadence]
    for speaker in speakers:
        rows = [
            row
            for row in source_by_speaker[speaker]
            if row["source_clip_id"] not in used_clip_ids
            and _cadence_accepts(cadence, float(row["duration_sec"]), realized=True)
        ]
        rows.sort(
            key=lambda row: (
                abs(float(row["duration_sec"]) - desired_duration),
                sha256_text(f"{spec['case_id']}|{row['selection_rank']}"),
            )
        )
        available[speaker] = rows
    placements: list[dict[str, object]] = []
    prepared: list[tuple[dict[str, object], np.ndarray]] = []
    inventory_rows: list[dict[str, object]] = []
    turn_counts: Counter[str] = Counter()
    previous_speaker: str | None = None
    previous_end = 0
    turn_index = 0
    target_duration = float(
        generation.get("target_duration_sec_by_cadence", {}).get(
            cadence, generation["target_duration_sec"]
        )
    )
    target_samples = round(target_duration * sample_rate)
    minimum_samples = round(float(generation["minimum_duration_sec"]) * sample_rate)
    maximum_samples = round(float(generation["maximum_duration_sec"]) * sample_rate)
    max_end = 0
    while max_end < target_samples or any(turn_counts[speaker] < 3 for speaker in speakers):
        candidates = [speaker for speaker in speakers if speaker != previous_speaker or len(speakers) == 1]
        candidates.sort(
            key=lambda speaker: (
                turn_counts[speaker],
                sha256_text(f"turn|{spec['case_id']}|{turn_index}|{speaker}"),
            )
        )
        speaker = candidates[0]
        clip = _next_usable_clip(
            available[speaker],
            used_clip_ids,
            cadence,
            sample_rate,
            generation,
            maximum_realized_duration_sec=maximum_realized_duration,
        )
        if clip is None:
            raise ControlledDiarizationError(
                f"speaker {speaker} exhausted {cadence} source clips in {spec['case_id']}"
            )
        row, samples, prep = clip
        if turn_index == 0:
            start = 0
            overlap_sec = 0.0
        else:
            overlap_sec = _overlap_draw(overlap_profile, turn_index, randomizer, config)
            if overlap_sec > 0:
                start = max(0, previous_end - round(overlap_sec * sample_rate))
            else:
                gap_low, gap_high = config["factors"]["gap_sec"][cadence]
                gap = randomizer.uniform(float(gap_low), float(gap_high))
                start = previous_end + round(gap * sample_rate)
        end = start + len(samples)
        if end > maximum_samples:
            if max_end >= minimum_samples and all(
                turn_counts[value] >= 3 for value in speakers
            ):
                # Return this unused clip to the head of its deterministic queue.
                available[speaker].insert(0, row)
                break
            remaining_sec = (maximum_samples - start) / sample_rate
            replacement = _next_usable_clip(
                available[speaker],
                used_clip_ids,
                cadence,
                sample_rate,
                generation,
                maximum_realized_duration_sec=min(
                    maximum_realized_duration, remaining_sec
                ),
            )
            if replacement is None:
                raise ControlledDiarizationError(
                    f"speaker {speaker} exhausted {cadence} source clips in {spec['case_id']}"
                )
            row, samples, prep = replacement
            end = start + len(samples)
        gain_db = _normalization_gain_db(samples)
        placement = {
            "turn_index": turn_index,
            "reference_speaker": local_labels[speaker],
            "global_speaker_id": speaker,
            "source_clip_id": row["source_clip_id"],
            "logical_audio_path": row["logical_audio_path"],
            "source_audio_sha256": prep["source_audio_sha256"],
            "original_source_sample_rate_hz": prep["original_sample_rate_hz"],
            "original_source_channels": prep["original_channels"],
            "original_source_duration_sec": prep["original_duration_sec"],
            "trim_start_sec": prep["trim_start_sec"],
            "trim_end_sec": prep["trim_end_sec"],
            "source_crop_start_sample": 0,
            "source_crop_end_sample": len(samples),
            "source_gain_db": gain_db,
            "global_start_sample": start,
            "global_end_sample": end,
            "global_start_sec": start / sample_rate,
            "global_end_sec": end / sample_rate,
            "scheduled_overlap_with_previous_sec": overlap_sec,
            "mix_order": turn_index,
            "channel": 1,
        }
        placements.append(placement)
        prepared.append((placement, samples * (10.0 ** (gain_db / 20.0))))
        used_clip_ids.add(str(row["source_clip_id"]))
        inventory_rows.append(
            {
                "schema_version": SOURCE_INVENTORY_SCHEMA_VERSION,
                "usage": "mixture",
                "tier": spec["tier"],
                "global_speaker_id": speaker,
                "source_protocol_speaker_key": row["source_protocol_speaker_key"],
                "source_clip_id": row["source_clip_id"],
                "logical_audio_path": row["logical_audio_path"],
                "source_audio_sha256": prep["source_audio_sha256"],
                "transcript_sha256": row["transcript_sha256"],
                "duration_sec": prep["original_duration_sec"],
                "evaluation_locked": spec["tier"] == "evaluation",
            }
        )
        turn_counts[speaker] += 1
        previous_speaker = speaker
        previous_end = end
        max_end = max(max_end, end)
        turn_index += 1
        if turn_index > 500:
            raise ControlledDiarizationError("turn scheduler exceeded safety bound")
    if max_end < minimum_samples:
        raise ControlledDiarizationError(f"case {spec['case_id']} is shorter than minimum")
    if len(speakers) > 1 and any(turn_counts[speaker] < 3 for speaker in speakers):
        raise ControlledDiarizationError(f"case {spec['case_id']} lacks speaker recurrence")
    overlap_flags = _placement_overlap_flags(placements)
    for placement, overlap in zip(placements, overlap_flags, strict=True):
        placement["overlap_indicator"] = overlap
    recipe: dict[str, object] = {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "benchmark_id": protocol_id,
        "case_id": spec["case_id"],
        "tier": spec["tier"],
        "seed": SEED,
        "case_seed": int(sha256_text(f"{SEED}|{spec['case_id']}")[:16], 16),
        "sample_rate_hz": sample_rate,
        "channels": 1,
        "audio_subtype": config["audio_subtype"],
        "speech_style": "prompted_read",
        "turn_pattern": "synthetic",
        "trim_policy": {
            "version": generation["source_trim_policy"],
            "frame_ms": generation["trim_frame_ms"],
            "threshold_dbfs": generation["trim_threshold_dbfs"],
            "padding_ms": generation["trim_padding_ms"],
            "internal_pauses_removed": False,
        },
        "speaker_count": len(speakers),
        "turn_cadence": cadence,
        "overlap_profile": overlap_profile,
        "realized_overlap_kind": (
            config["generation"]["backchannel_realized_kind"]
            if overlap_profile == "backchannel"
            else overlap_profile
        ),
        "local_to_global_speaker": {
            local_labels[speaker]: speaker for speaker in speakers
        },
        "placements": placements,
        "mix_peak_protection_gain_db": 0.0,
    }
    return recipe, prepared, inventory_rows


def _next_usable_clip(
    rows: list[Mapping[str, object]],
    used: set[str],
    cadence: str,
    sample_rate: int,
    generation: Mapping[str, object],
    *,
    maximum_realized_duration_sec: float,
) -> tuple[Mapping[str, object], np.ndarray, dict[str, object]] | None:
    while rows:
        row = rows.pop(0)
        if row["source_clip_id"] in used:
            continue
        path = resolve_source_path(str(row["logical_audio_path"]))
        try:
            samples, metadata = _prepare_source_audio(
                path,
                sample_rate,
                {
                    "version": generation["source_trim_policy"],
                    "frame_ms": generation["trim_frame_ms"],
                    "threshold_dbfs": generation["trim_threshold_dbfs"],
                    "padding_ms": generation["trim_padding_ms"],
                    "internal_pauses_removed": False,
                },
            )
        except (RuntimeError, OSError, ValueError):
            continue
        realized_duration = len(samples) / sample_rate
        if (
            not _cadence_accepts(cadence, realized_duration, realized=True)
            or realized_duration > maximum_realized_duration_sec
        ):
            continue
        return row, samples, metadata
    return None


def _prepare_source_audio(
    path: Path, sample_rate: int, trim_policy: Mapping[str, object]
) -> tuple[np.ndarray, dict[str, object]]:
    source, source_rate = sf.read(path, dtype="float32", always_2d=True)
    if source.size == 0 or not np.isfinite(source).all():
        raise ControlledDiarizationError(f"invalid source audio: {path.name}")
    mono = np.mean(source, axis=1, dtype=np.float64).astype(np.float32)
    original_duration = len(mono) / source_rate
    if source_rate != sample_rate:
        divisor = math.gcd(int(source_rate), int(sample_rate))
        mono = resample_poly(mono, sample_rate // divisor, source_rate // divisor).astype(
            np.float32
        )
    frame = max(1, round(float(trim_policy["frame_ms"]) * sample_rate / 1000.0))
    pad = max(0, round(float(trim_policy["padding_ms"]) * sample_rate / 1000.0))
    threshold = 10.0 ** (float(trim_policy["threshold_dbfs"]) / 20.0)
    active: list[int] = []
    for index in range(0, len(mono), frame):
        block = mono[index : index + frame]
        rms = math.sqrt(float(np.mean(np.square(block, dtype=np.float64)))) if len(block) else 0.0
        if rms >= threshold:
            active.append(index)
    if active:
        start = max(0, active[0] - pad)
        end = min(len(mono), active[-1] + frame + pad)
    else:
        start, end = 0, len(mono)
    trimmed = np.ascontiguousarray(mono[start:end], dtype=np.float32)
    if len(trimmed) == 0 or not np.isfinite(trimmed).all():
        raise ControlledDiarizationError(f"source trim produced no finite samples: {path.name}")
    return trimmed, {
        "source_audio_sha256": sha256_file(path).upper(),
        "original_sample_rate_hz": int(source_rate),
        "original_channels": int(source.shape[1]),
        "original_duration_sec": original_duration,
        "trim_start_sec": start / sample_rate,
        "trim_end_sec": end / sample_rate,
    }


def _render_case(
    config: Mapping[str, object],
    recipe: Mapping[str, object],
    prepared_audio: Sequence[tuple[Mapping[str, object], np.ndarray]],
    output_path: Path,
) -> dict[str, object]:
    length = max(int(placement["global_end_sample"]) for placement, _audio in prepared_audio)
    mix = np.zeros(length, dtype=np.float64)
    for placement, audio in prepared_audio:
        start = int(placement["global_start_sample"])
        end = start + len(audio)
        mix[start:end] += audio
    peak = float(np.max(np.abs(mix), initial=0.0))
    target_peak = 10.0 ** (float(config["generation"]["target_peak_dbfs"]) / 20.0)
    peak_gain = min(1.0, target_peak / peak) if peak > 0 else 1.0
    mix *= peak_gain
    gain_db = 20.0 * math.log10(peak_gain) if peak_gain > 0 else -120.0
    samples = mix.astype(np.float32)
    _write_wav_atomic(output_path, samples, int(config["sample_rate_hz"]))
    return {
        "audio_sha256": sha256_file(output_path),
        "pcm_sha256": _wav_pcm_sha256(output_path),
        "duration_samples": len(samples),
        "duration_sec": len(samples) / int(config["sample_rate_hz"]),
        "mix_peak_protection_gain_db": gain_db,
    }


def _write_wav_atomic(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    sf.write(temporary, samples, sample_rate, format="WAV", subtype="PCM_16")
    os.replace(temporary, path)


def _wav_pcm_sha256(path: Path) -> str:
    samples, _sample_rate = sf.read(path, dtype="int16", always_2d=False)
    pcm = np.ascontiguousarray(samples, dtype="<i2")
    return hashlib.sha256(pcm.tobytes(order="C")).hexdigest()


def _normalization_gain_db(samples: np.ndarray) -> float:
    rms = math.sqrt(float(np.mean(np.square(samples, dtype=np.float64))))
    if rms <= 1e-9:
        return 0.0
    current_dbfs = 20.0 * math.log10(rms)
    return max(-12.0, min(12.0, -24.0 - current_dbfs))


def _overlap_draw(
    profile: str,
    turn_index: int,
    randomizer: random.Random,
    config: Mapping[str, object],
) -> float:
    if profile == "none":
        return 0.0
    interval = 6 if profile == "backchannel" else 4
    if turn_index % interval:
        return 0.0
    low, high = config["factors"]["overlap_event_sec"][profile]
    return randomizer.uniform(float(low), float(high))


def _cadence_accepts(
    cadence: str, duration_sec: float, *, realized: bool = False
) -> bool:
    bounds = (
        {
            "relaxed": (1.5, 10.0),
            "standard": (0.8, 6.0),
            "rapid": (0.4, 4.0),
        }
        if realized
        else {
            "relaxed": (2.4, 7.0),
            "standard": (1.4, 4.5),
            "rapid": (0.7, 2.75),
        }
    )[cadence]
    return bounds[0] <= duration_sec <= bounds[1]


def _placement_overlap_flags(placements: Sequence[Mapping[str, object]]) -> list[bool]:
    flags = []
    for index, row in enumerate(placements):
        start, end = int(row["global_start_sample"]), int(row["global_end_sample"])
        flags.append(
            any(
                other != index
                and max(start, int(value["global_start_sample"]))
                < min(end, int(value["global_end_sample"]))
                for other, value in enumerate(placements)
            )
        )
    return flags


def _case_statistics(recipe: Mapping[str, object]) -> dict[str, object]:
    sample_rate = int(recipe["sample_rate_hz"])
    placements = list(recipe["placements"])
    boundaries = sorted(
        {int(row["global_start_sample"]) for row in placements}
        | {int(row["global_end_sample"]) for row in placements}
    )
    speech_union = overlap = 0
    overlap_events: list[float] = []
    active_counts: list[int] = []
    current_overlap = 0
    for start, end in zip(boundaries, boundaries[1:]):
        active = sum(
            int(int(row["global_start_sample"]) < end and int(row["global_end_sample"]) > start)
            for row in placements
        )
        duration = end - start
        active_counts.append(active)
        if active:
            speech_union += duration
        if active >= 2:
            overlap += duration
            current_overlap += duration
        elif current_overlap:
            overlap_events.append(current_overlap / sample_rate)
            current_overlap = 0
    if current_overlap:
        overlap_events.append(current_overlap / sample_rate)
    by_speaker: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in placements:
        by_speaker[str(row["reference_speaker"])].append(row)
    turn_durations = [
        (int(row["global_end_sample"]) - int(row["global_start_sample"])) / sample_rate
        for row in placements
    ]
    per_speaker = {}
    total_speaker_time = sum(turn_durations)
    reentry_gaps = []
    for speaker, rows in by_speaker.items():
        ordered = sorted(rows, key=lambda value: int(value["global_start_sample"]))
        speech = sum(
            int(value["global_end_sample"]) - int(value["global_start_sample"])
            for value in ordered
        ) / sample_rate
        gaps = [
            (int(right["global_start_sample"]) - int(left["global_end_sample"])) / sample_rate
            for left, right in zip(ordered, ordered[1:])
        ]
        reentry_gaps.extend(gaps)
        per_speaker[speaker] = {
            "speech_duration_sec": speech,
            "speaker_share": speech / total_speaker_time if total_speaker_time else 0.0,
            "turn_count": len(ordered),
            "mean_turn_duration_sec": speech / len(ordered),
            "maximum_reentry_gap_sec": max(gaps, default=0.0),
        }
    gaps = []
    ordered_all = sorted(placements, key=lambda value: int(value["global_start_sample"]))
    for left, right in zip(ordered_all, ordered_all[1:]):
        gaps.append(
            max(
                0.0,
                (int(right["global_start_sample"]) - int(left["global_end_sample"]))
                / sample_rate,
            )
        )
    return {
        "total_duration_sec": int(recipe["output_duration_samples"]) / sample_rate,
        "total_reference_speech_time_sec": total_speaker_time,
        "speech_union_duration_sec": speech_union / sample_rate,
        "overlap_duration_sec": overlap / sample_rate,
        "overlap_ratio": overlap / total_speaker_time / sample_rate if total_speaker_time else 0.0,
        "overlap_event_count": len(overlap_events),
        "median_overlap_event_duration_sec": statistics.median(overlap_events) if overlap_events else 0.0,
        "max_simultaneously_active_speakers": max(active_counts, default=0),
        "number_of_turns": len(placements),
        "mean_turn_duration_sec": statistics.fmean(turn_durations),
        "median_turn_duration_sec": statistics.median(turn_durations),
        "minimum_turn_duration_sec": min(turn_durations),
        "maximum_turn_duration_sec": max(turn_durations),
        "mean_inter_turn_gap_sec": statistics.fmean(gaps) if gaps else 0.0,
        "speaker_change_count": sum(
            left["reference_speaker"] != right["reference_speaker"]
            for left, right in zip(ordered_all, ordered_all[1:])
        ),
        "same_speaker_continuation_count": sum(
            left["reference_speaker"] == right["reference_speaker"]
            for left, right in zip(ordered_all, ordered_all[1:])
        ),
        "maximum_speaker_reentry_gap_sec": max(reentry_gaps, default=0.0),
        "per_speaker": per_speaker,
    }


def _write_reference_rttm(path: Path, recipe: Mapping[str, object]) -> None:
    turns = [
        RttmTurn(
            recording_id=str(recipe["case_id"]),
            channel="1",
            start_sec=float(row["global_start_sec"]),
            end_sec=float(row["global_end_sec"]),
            speaker_label=str(row["reference_speaker"]),
        )
        for row in recipe["placements"]
    ]
    write_text_atomic(path, "\n".join(turn.to_line() for turn in turns) + "\n")


def _write_identity_overlays(
    path: Path,
    cases: Sequence[Mapping[str, object]],
    enrollment_by_global: Mapping[str, Sequence[Mapping[str, object]]],
) -> None:
    rows = []
    for case in cases:
        speakers = list(case["global_speaker_ids"])
        mixed_known = {
            speaker
            for speaker in speakers
            if int(sha256_text(f"mixed|{case['case_id']}|{speaker}")[:8], 16) % 2 == 0
        }
        desired = max(1, round(len(speakers) / 2))
        if len(mixed_known) != desired:
            mixed_known = set(
                sorted(
                    speakers,
                    key=lambda speaker: sha256_text(f"mixed-rank|{case['case_id']}|{speaker}"),
                )[:desired]
            )
        for overlay in ("ALL_UNKNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_KNOWN"):
            states = {}
            for speaker in speakers:
                known = overlay == "ALL_KNOWN" or (
                    overlay == "MIXED_KNOWN_UNKNOWN" and speaker in mixed_known
                )
                states[speaker] = {
                    "identity_state": "KNOWN" if known else "UNKNOWN",
                    "reserved_enrollment_clips": (
                        list(enrollment_by_global.get(speaker, [])) if known else []
                    ),
                }
            rows.append(
                {
                    "schema_version": "controlled-diarization-identity-overlay.v1",
                    "case_id": case["case_id"],
                    "overlay_id": overlay,
                    "anonymous_der_jer_affected": False,
                    "speaker_states": states,
                }
            )
    write_jsonl_atomic(path, rows)


def _reserved_inventory_rows(
    source: Mapping[str, object], split_members: Mapping[str, Sequence[str]]
) -> list[dict[str, object]]:
    tier_by_speaker = {
        speaker: tier for tier, speakers in split_members.items() for speaker in speakers
    }
    rows = []
    for raw in source["enrollment_rows"]:
        speaker = global_speaker_id(str(raw["speaker_key"]))
        if speaker not in tier_by_speaker:
            continue
        rows.append(
            {
                "schema_version": SOURCE_INVENTORY_SCHEMA_VERSION,
                "usage": "reserved_enrollment",
                "tier": tier_by_speaker[speaker],
                "global_speaker_id": speaker,
                "source_protocol_speaker_key": raw["speaker_key"],
                "source_clip_id": raw["source_recording_id"],
                "logical_audio_path": raw["logical_audio_path"],
                "source_audio_sha256": str(raw["audio_sha256"]).upper(),
                "transcript_sha256": str(raw["transcript_sha256"]).upper(),
                "duration_sec": float(raw["duration_sec"]),
                "evaluation_locked": tier_by_speaker[speaker] == "evaluation",
            }
        )
    return rows


def _balance_rows(
    cases: Mapping[str, Sequence[Mapping[str, object]]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    appearance_rows: list[dict[str, object]] = []
    pair_rows: list[dict[str, object]] = []
    for tier, tier_cases in cases.items():
        appearances: Counter[str] = Counter()
        seconds: Counter[str] = Counter()
        turns: Counter[str] = Counter()
        pairs: Counter[tuple[str, str]] = Counter()
        for case in tier_cases:
            stats = case["reference_statistics"]["per_speaker"]
            for local, speaker in case["local_to_global_speaker"].items():
                appearances[speaker] += 1
                seconds[speaker] += float(stats[local]["speech_duration_sec"])
                turns[speaker] += int(stats[local]["turn_count"])
            for pair in itertools.combinations(sorted(case["global_speaker_ids"]), 2):
                pairs[pair] += 1
        for speaker in sorted(appearances):
            appearance_rows.append(
                {
                    "tier": tier,
                    "global_speaker_id": speaker,
                    "recording_appearances": appearances[speaker],
                    "total_speech_sec": seconds[speaker],
                    "turn_count": turns[speaker],
                }
            )
        for (left, right), count in sorted(pairs.items()):
            pair_rows.append(
                {
                    "tier": tier,
                    "global_speaker_id_a": left,
                    "global_speaker_id_b": right,
                    "cooccurrence_count": count,
                }
            )
    return appearance_rows, pair_rows


def _write_review_package(
    root: Path,
    cases: Mapping[str, Sequence[Mapping[str, object]]],
    config: Mapping[str, object],
) -> None:
    evaluation = [row for row in cases["evaluation"] if int(row["speaker_count"]) > 1]
    selected = []
    for cell in itertools.product((2, 3, 5), CADENCES, OVERLAPS):
        candidates = [
            row
            for row in evaluation
            if (
                int(row["speaker_count"]),
                str(row["turn_cadence"]),
                str(row["overlap_profile"]),
            )
            == cell
        ]
        selected.append(sorted(candidates, key=lambda row: str(row["case_id"]))[0])
    review_root = root / "human_review"
    review_root.mkdir(parents=True, exist_ok=True)
    _write_csv(
        review_root / "review_manifest.csv",
        [
            {
                "case_id": row["case_id"],
                "speaker_count": row["speaker_count"],
                "turn_cadence": row["turn_cadence"],
                "overlap_profile": row["overlap_profile"],
                "audio_logical_path": row["audio_logical_path"],
                "reference_rttm_path": row["reference_rttm_path"],
                "review_status": "NOT_REVIEWED",
                "review_notes": "",
            }
            for row in selected
        ],
    )
    timelines = []
    rttm_lines = []
    for row in selected:
        recipe = json.loads((root / row["recipe_path"]).read_text(encoding="utf-8"))
        timelines.append(
            {
                "case_id": row["case_id"],
                "duration_sec": row["duration_sec"],
                "turns": [
                    {
                        "speaker": turn["reference_speaker"],
                        "start_sec": turn["global_start_sec"],
                        "end_sec": turn["global_end_sec"],
                        "overlap_indicator": turn["overlap_indicator"],
                    }
                    for turn in recipe["placements"]
                ],
            }
        )
        rttm_lines.extend(
            (root / row["reference_rttm_path"]).read_text(encoding="utf-8").splitlines()
        )
    write_json_atomic(
        review_root / "reference_timeline.json",
        {
            "schema_version": "controlled-diarization-review-timeline.v1",
            "timing_reference": "synthetic_placement_timing_reference",
            "human_annotation": False,
            "cases": timelines,
        },
    )
    write_text_atomic(review_root / "reference.rttm", "\n".join(rttm_lines) + "\n")


def _write_protected_assets(
    root: Path,
    protocol_id: str,
    speakers: Sequence[Mapping[str, object]],
    clips: Sequence[Mapping[str, object]],
    cases: Mapping[str, Sequence[Mapping[str, object]]],
) -> None:
    evaluation_speakers = sorted(
        row["global_speaker_id"] for row in speakers if row["tier"] == "evaluation"
    )
    evaluation_clips = sorted(
        {
            row["source_clip_id"]
            for row in clips
            if row["tier"] == "evaluation" and row["usage"] == "mixture"
        }
    )
    evaluation_mixtures = [
        {
            "case_id": row["case_id"],
            "audio_logical_path": row["audio_logical_path"],
            "audio_sha256": row["audio_sha256"],
        }
        for row in cases["evaluation"]
    ]
    write_json_atomic(
        root / "protected_evaluation_assets.json",
        {
            "schema_version": "protected-evaluation-assets.v1",
            "benchmark_id": protocol_id,
            "evaluation_locked": True,
            "prohibited_training_inputs": [
                "evaluation_speakers",
                "evaluation_source_clips",
                "generated_evaluation_mixtures",
            ],
            "development_speakers": sorted(
                row["global_speaker_id"] for row in speakers if row["tier"] == "development"
            ),
            "evaluation_speakers": evaluation_speakers,
            "evaluation_source_clips": evaluation_clips,
            "generated_evaluation_mixtures": evaluation_mixtures,
        },
    )


def _protocol_summary(
    config: Mapping[str, object],
    protocol_id: str,
    source: Mapping[str, object],
    speakers: Sequence[Mapping[str, object]],
    clips: Sequence[Mapping[str, object]],
    cases: Mapping[str, Sequence[Mapping[str, object]]],
    audio_root: Path,
) -> dict[str, object]:
    durations = {
        tier: sum(float(row["duration_sec"]) for row in rows) for tier, rows in cases.items()
    }
    return {
        "schema_version": "controlled-diarization-protocol-summary.v1",
        "benchmark_id": protocol_id,
        "benchmark_version": BENCHMARK_VERSION,
        "seed": SEED,
        "speech_style": "prompted_read",
        "turn_pattern": "synthetic",
        "timing_reference": "synthetic_placement_timing_reference",
        "human_frame_level_annotation": False,
        "source_protocol_id": source["protocol_id"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "source_path": source["release_root_logical"],
        "generated_audio_root": "${JP_GENERATED_DATA_ROOT}/controlled_diarization_v1",
        "recording_counts": {tier: len(rows) for tier, rows in cases.items()},
        "speaker_counts": {
            tier: sum(row["tier"] == tier for row in speakers) for tier in TIERS
        },
        "unique_source_speakers": len({row["global_speaker_id"] for row in speakers}),
        "unique_mixture_source_clips": len(
            {row["source_clip_id"] for row in clips if row["usage"] == "mixture"}
        ),
        "reserved_enrollment_source_clips": sum(
            row["usage"] == "reserved_enrollment" for row in clips
        ),
        "generated_audio_sec": durations,
        "total_generated_audio_sec": sum(durations.values()),
        "factor_distribution": {
            tier: {
                f"{row['speaker_count']}|{row['turn_cadence']}|{row['overlap_profile']}": sum(
                    int(
                        value["speaker_count"] == row["speaker_count"]
                        and value["turn_cadence"] == row["turn_cadence"]
                        and value["overlap_profile"] == row["overlap_profile"]
                    )
                    for value in cases[tier]
                )
                for row in cases[tier]
            }
            for tier in TIERS
        },
        "evaluation_locked": True,
        "full_scientific_diarization_run_started": False,
    }


def _validation_report(
    errors: Sequence[str],
    warnings: Sequence[str],
    case_counts: Mapping[str, int],
    balance: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema_version": "controlled-diarization-validation-report.v1",
        "valid": not errors,
        "errors": list(errors),
        "warnings": list(warnings),
        "case_counts": dict(case_counts),
        "balance": dict(balance),
        "checks": {
            "source_integrity": "PASS" if not any("source" in item for item in errors) else "FAIL",
            "generated_audio": "PASS" if not any("audio" in item for item in errors) else "FAIL",
            "timing_and_rttm": "PASS" if not any("placement" in item or "RTTM" in item for item in errors) else "FAIL",
            "factor_balance": "PASS" if not any("factorial cell" in item for item in errors) else "FAIL",
            "speaker_disjointness": "PASS" if not any("speaker pools overlap" in item for item in errors) else "FAIL",
            "reserved_enrollment_disjointness": "PASS" if not any("enrollment clips overlap" in item for item in errors) else "FAIL",
            "source_clip_reuse": "PASS" if not any("reused" in item for item in errors) else "FAIL",
        },
    }


def _source_by_speaker(
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    result: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in candidates:
        result[str(row["global_speaker_id"])].append(row)
    for rows in result.values():
        rows.sort(key=lambda row: str(row["selection_rank"]))
    return dict(result)


def _distribution(values: Sequence[int]) -> dict[str, object]:
    ordered = sorted(values)
    if not ordered:
        return {"minimum": 0, "median": 0, "maximum": 0, "mean": 0.0}
    return {
        "minimum": min(ordered),
        "p25": _percentile(ordered, 0.25),
        "median": statistics.median(ordered),
        "p75": _percentile(ordered, 0.75),
        "maximum": max(ordered),
        "mean": statistics.fmean(ordered),
    }


def _percentile(values: Sequence[int], probability: float) -> float:
    position = (len(values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(values[lower])
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        write_text_atomic(path, "")
        return
    fields = list(rows[0])
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    os.replace(temporary, path)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def yaml_safe_dump(value: Mapping[str, object]) -> str:
    import yaml

    return yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True)
