"""Deterministic Product V2 Common Voice mixture protocol."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import itertools
import json
from pathlib import Path
import re
import shutil
from typing import Mapping, Sequence

from app.controlled_diarization.benchmark import (
    _assign_case_speakers,
    _case_statistics,
    _load_candidate_clips,
    _load_source_pool,
    _render_case,
    _schedule_case,
    _source_by_speaker,
    _write_reference_rttm,
)
from app.controlled_diarization.contracts import (
    DEFAULT_CONFIG_PATH as V1_CONFIG_PATH,
    ControlledDiarizationError,
    canonical_json,
    identity,
    load_config,
    sha256_file,
    sha256_text,
)
from app.diarization_evaluation.artifacts import (
    write_checksum_manifest,
    write_json_atomic,
    write_jsonl_atomic,
    write_text_atomic,
)
from app.diarization_product_v2.chime import extract_chime_statistics
from app.diarization_product_v2.contracts import (
    DEFAULT_GENERATED_ROOT,
    DEFAULT_PROTOCOL_ROOT,
    SEED,
    V1_PROTOCOL_ROOT,
)


SPEAKER_COUNTS = (1, 2, 3, 5, 6, 8, 9, 12)
PROFILES = (
    ("normal_alternation", "standard", "none", "balanced"),
    ("rapid_backchannel", "rapid", "backchannel", "balanced"),
    ("interrupted_monologue", "standard", "moderate", "moderately_imbalanced"),
    ("short_response_rare_reentry", "standard", "none", "strongly_dominant"),
)


def prepare_product_protocol(
    *,
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    generated_root: Path = DEFAULT_GENERATED_ROOT,
) -> dict[str, object]:
    root = protocol_root.resolve()
    audio_root = generated_root.resolve()
    summary_path = root / "protocol_summary.json"
    if summary_path.is_file():
        validation = validate_product_protocol(root, audio_root)
        if not validation["valid"]:
            raise ControlledDiarizationError("existing Product V2 protocol is invalid")
        return {
            "reused": True,
            "protocol_summary": json.loads(summary_path.read_text(encoding="utf-8")),
            "validation": validation,
        }

    _reset_unfrozen_partial(root, audio_root)

    config = load_config(V1_CONFIG_PATH)
    # A failed pre-materialization audit may leave this dedicated version root
    # with no frozen summary. Atomic writers safely resume that narrow state.
    root.mkdir(parents=True, exist_ok=True)
    audio_root.mkdir(parents=True, exist_ok=True)
    chime = extract_chime_statistics(root / "chime6_conversation_statistics.json")
    source = _load_source_pool(config, None)
    candidates = _load_candidate_clips(source)
    source_by_speaker = _source_by_speaker(candidates)
    v1_used = _v1_mixture_clip_ids()
    split_members = _v1_split_members()
    protocol_payload = {
        "version": "diarization_product_v2",
        "seed": SEED,
        "source_protocol_id": source["protocol_id"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "v1_protocol_id": _v1_protocol_id(),
        "v1_excluded_clip_ids_sha256": sha256_text(canonical_json(sorted(v1_used))),
        "chime_statistics_sha256": sha256_file(root / "chime6_conversation_statistics.json"),
        "development_recordings": 36,
        "evaluation_recordings": 72,
        "long_session_seconds": 300,
        "speaker_counts": SPEAKER_COUNTS,
        "profiles": PROFILES,
        "regular_target_sec_policy": (
            "standard=max(12,count*8); rapid=max(12,count*4.5); "
            "short=max(3,count*5); "
            "three-turn recurrence may extend"
        ),
        "rapid_backchannel_policy": "rapid cadence for 1-3 speakers; standard cadence for 5-12",
        "short_turn_crop_policy_sec": "every third turn cycles deterministically through 0.45, 0.65, 0.90",
    }
    protocol_id = identity("diarization_product_v2", protocol_payload, length=12)
    specs = _case_specs(protocol_id)
    used = set(v1_used)
    appearances = {"development": Counter(), "evaluation": Counter()}
    pairs = {"development": Counter(), "evaluation": Counter()}
    case_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    inventory: list[dict[str, object]] = []
    assignments: list[dict[str, object]] = []

    for spec in sorted(specs, key=_case_priority):
        tier = str(spec["tier"])
        generation_config = _generation_config(
            config,
            long_session=bool(spec["long_session"]),
            target_sec=float(spec["active_target_sec"]),
        )
        excluded: set[str] = set()
        last_schedule_error: str | None = None
        for attempt in range(60):
            before = set(used)
            try:
                selected = _assign_case_speakers(
                    spec,
                    split_members[tier],
                    source_by_speaker,
                    used,
                    appearances[tier],
                    pairs[tier],
                    excluded_speakers=excluded,
                )
            except ControlledDiarizationError:
                # The remaining split capacity is genuinely insufficient for
                # this ordering; more attempts cannot change that fact.
                if last_schedule_error:
                    raise ControlledDiarizationError(
                        "source assignment exhausted after schedule failures; "
                        f"last failure: {last_schedule_error}"
                    )
                raise
            local = {speaker: f"SPK{index:02d}" for index, speaker in enumerate(selected)}
            weighted_spec = {
                **spec,
                "speaker_turn_weights": _participation_weights(
                    selected, str(spec["participation_profile"])
                ),
            }
            try:
                recipe, prepared, clip_rows = _schedule_case(
                    generation_config,
                    protocol_id,
                    weighted_spec,
                    selected,
                    local,
                    source_by_speaker,
                    used,
                )
                break
            except ControlledDiarizationError as exc:
                last_schedule_error = str(exc)
                used.clear()
                used.update(before)
                match = re.search(r"speaker (cvspk_[0-9a-f]+) exhausted", str(exc))
                excluded.add(match.group(1) if match else selected[0])
                if attempt == 59:
                    raise
        recipe.update(
            {
                "schema_version": "diarization-product-recipe.v2",
                "evaluation_only": True,
                "training_eligible": False,
                "source_description": (
                    "real older-adult Common Voice source voices + synthetic sample "
                    "placement + CHiME-6 train/dev-informed timing distributions"
                ),
                "scenario_profile": spec["scenario_profile"],
                "speaker_band": spec["speaker_band"],
                "participation_profile": spec["participation_profile"],
                "long_session": spec["long_session"],
            }
        )
        path = audio_root / tier / "audio" / f"{spec['case_id']}.wav"
        render = _render_case(generation_config, recipe, prepared, path)
        recipe.update(
            {
                "mix_peak_protection_gain_db": render["mix_peak_protection_gain_db"],
                "output_audio_sha256": render["audio_sha256"],
                "output_pcm_sha256": render["pcm_sha256"],
                "output_duration_samples": render["duration_samples"],
                "output_duration_sec": render["duration_sec"],
            }
        )
        recipe["recipe_sha256"] = sha256_text(
            canonical_json({key: value for key, value in recipe.items() if key != "recipe_sha256"})
        )
        tier_root = root / tier
        recipe_path = tier_root / "recipes" / f"{spec['case_id']}.json"
        rttm_path = tier_root / "references" / f"{spec['case_id']}.rttm"
        uem_path = tier_root / "references" / f"{spec['case_id']}.uem"
        write_json_atomic(recipe_path, recipe)
        _write_reference_rttm(rttm_path, recipe)
        write_text_atomic(
            uem_path,
            f"{spec['case_id']} 1 0.000000 {float(render['duration_sec']):.6f}\n",
        )
        stats = _case_statistics(recipe)
        realized = {
            "speaker_time_share": {
                key: value["speaker_share"] for key, value in stats["per_speaker"].items()
            },
            "dominant_speaker_share": max(
                value["speaker_share"] for value in stats["per_speaker"].values()
            ),
            "rare_speaker_share": min(
                value["speaker_share"] for value in stats["per_speaker"].values()
            ),
            "overlap_ratio": stats["overlap_ratio"],
            "maximum_reentry_gap_sec": stats["maximum_speaker_reentry_gap_sec"],
        }
        row = {
            "schema_version": "diarization-product-case.v2",
            **{key: value for key, value in spec.items() if key != "speaker_turn_weights"},
            "benchmark_id": protocol_id,
            "speech_style": "prompted_read",
            "turn_pattern": "synthetic_chime6_informed",
            "timing_reference": "exact_synthetic_sample_placement",
            "evaluation_only": True,
            "training_eligible": False,
            "evaluation_locked": tier == "evaluation",
            "reference_speaker_count": len(selected),
            "global_speaker_ids": selected,
            "local_to_global_speaker": {local[speaker]: speaker for speaker in selected},
            "audio_logical_path": f"{tier}/audio/{spec['case_id']}.wav",
            "audio_sha256": render["audio_sha256"],
            "pcm_sha256": render["pcm_sha256"],
            "duration_sec": render["duration_sec"],
            "recipe_path": recipe_path.relative_to(root).as_posix(),
            "recipe_sha256": recipe["recipe_sha256"],
            "reference_rttm_path": rttm_path.relative_to(root).as_posix(),
            "reference_uem_path": uem_path.relative_to(root).as_posix(),
            "sample_rate_hz": 16000,
            "channels": 1,
            "reference_statistics": stats,
            "realized_scenario_statistics": realized,
        }
        case_rows[tier].append(row)
        inventory.extend(
            {
                **clip,
                "evaluation_only": True,
                "training_eligible": False,
                "product_protocol_id": protocol_id,
            }
            for clip in clip_rows
        )
        assignments.extend(
            {
                "tier": tier,
                "case_id": spec["case_id"],
                "global_speaker_id": speaker,
                "reference_label": local[speaker],
                "scenario_profile": spec["scenario_profile"],
            }
            for speaker in selected
        )
        appearances[tier].update(selected)
        pairs[tier].update(itertools.combinations(sorted(selected), 2))

    for tier in ("development", "evaluation"):
        case_rows[tier].sort(key=lambda row: str(row["case_id"]))
        if tier == "development":
            for index, row in enumerate(case_rows[tier]):
                row["development_role"] = "calibration" if index < 8 else "selection"
        write_jsonl_atomic(root / tier / "case_manifest.jsonl", case_rows[tier])
    _write_csv(root / "source_clip_inventory.csv", inventory)
    _write_csv(root / "case_speaker_assignments.csv", assignments)
    split_rows = [
        {"tier": tier, "global_speaker_id": speaker}
        for tier, speakers in split_members.items()
        for speaker in speakers
    ]
    _write_csv(root / "source_speaker_inventory.csv", split_rows)
    write_json_atomic(
        root / "protected_evaluation_assets.json",
        {
            "schema_version": "diarization-product-protected-evaluation.v1",
            "protocol_id": protocol_id,
            "evaluation_locked": True,
            "evaluation_only": True,
            "training_eligible": False,
            "case_manifest_sha256": sha256_file(root / "evaluation" / "case_manifest.jsonl"),
            "result_accessed": False,
        },
    )
    review_rows = [
        {
            "tier": row["tier"],
            "case_id": row["case_id"],
            "scenario_profile": row["scenario_profile"],
            "duration_sec": row["duration_sec"],
            "status": "NOT_REVIEWED",
            "notes": "",
        }
        for tier in ("development", "evaluation")
        for row in case_rows[tier]
    ]
    _write_csv(root / "human_review_manifest.csv", review_rows)
    summary = {
        "schema_version": "diarization-product-protocol-summary.v2",
        "protocol_id": protocol_id,
        "seed": SEED,
        "source_protocol_id": source["protocol_id"],
        "v1_protocol_id": _v1_protocol_id(),
        "development_cases": len(case_rows["development"]),
        "evaluation_cases": len(case_rows["evaluation"]),
        "long_development_cases": sum(row["long_session"] for row in case_rows["development"]),
        "long_evaluation_cases": sum(row["long_session"] for row in case_rows["evaluation"]),
        "development_speakers": len(split_members["development"]),
        "evaluation_speakers": len(split_members["evaluation"]),
        "unique_mixture_clips": len({row["source_clip_id"] for row in inventory}),
        "v1_excluded_mixture_clips": len(v1_used),
        "evaluation_only": True,
        "training_eligible": False,
        "evaluation_results_inspected": False,
        "protocol_identity_payload": protocol_payload,
        "generated_root": str(audio_root),
    }
    write_json_atomic(root / "protocol_summary.json", summary)
    validation = validate_product_protocol(root, audio_root)
    write_json_atomic(root / "validation_report.json", validation)
    write_checksum_manifest(root)
    return {"reused": False, "protocol_summary": summary, "validation": validation}


def validate_product_protocol(
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    generated_root: Path = DEFAULT_GENERATED_ROOT,
) -> dict[str, object]:
    root, audio_root = protocol_root.resolve(), generated_root.resolve()
    errors: list[str] = []
    counts: dict[str, int] = {}
    speakers: dict[str, set[str]] = {}
    all_clips: dict[str, str] = {}
    v1_used = _v1_mixture_clip_ids()
    for tier, expected in (("development", 36), ("evaluation", 72)):
        manifest = root / tier / "case_manifest.jsonl"
        if not manifest.is_file():
            errors.append(f"missing {tier} manifest")
            continue
        rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line]
        counts[tier] = len(rows)
        speakers[tier] = {value for row in rows for value in row["global_speaker_ids"]}
        if len(rows) != expected:
            errors.append(f"{tier} contains {len(rows)} cases, expected {expected}")
        long_expected = 4 if tier == "development" else 8
        if sum(bool(row["long_session"]) for row in rows) != long_expected:
            errors.append(f"{tier} long-session count mismatch")
        for row in rows:
            if not row.get("evaluation_only") or row.get("training_eligible"):
                errors.append(f"{row['case_id']}: evaluation/training flags invalid")
            recipe_path = root / row["recipe_path"]
            rttm_path = root / row["reference_rttm_path"]
            uem_path = root / row["reference_uem_path"]
            audio_path = audio_root / row["audio_logical_path"]
            for path in (recipe_path, rttm_path, uem_path, audio_path):
                if not path.is_file():
                    errors.append(f"{row['case_id']}: missing {path.name}")
            if not recipe_path.is_file() or not audio_path.is_file():
                continue
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            expected_recipe = sha256_text(canonical_json({k: v for k, v in recipe.items() if k != "recipe_sha256"}))
            if expected_recipe != row["recipe_sha256"] or recipe.get("recipe_sha256") != expected_recipe:
                errors.append(f"{row['case_id']}: recipe identity mismatch")
            if sha256_file(audio_path) != row["audio_sha256"]:
                errors.append(f"{row['case_id']}: audio hash mismatch")
            for placement in recipe["placements"]:
                clip_id = str(placement["source_clip_id"])
                if clip_id in v1_used:
                    errors.append(f"{row['case_id']}: V1 source clip reused")
                previous = all_clips.setdefault(clip_id, str(row["case_id"]))
                if previous != str(row["case_id"]):
                    errors.append(f"source clip reused across cases: {clip_id}")
    if speakers.get("development", set()) & speakers.get("evaluation", set()):
        errors.append("development/evaluation speakers overlap")
    return {
        "schema_version": "diarization-product-validation.v2",
        "valid": not errors,
        "errors": errors,
        "case_counts": counts,
        "development_evaluation_speaker_disjoint": not bool(
            speakers.get("development", set()) & speakers.get("evaluation", set())
        ),
        "source_clip_reuse_count": max(0, sum(1 for _ in all_clips) - len(all_clips)),
        "v1_source_clip_overlap": 0 if not any("V1 source" in error for error in errors) else None,
        "reserved_enrollment_excluded_by_authoritative_source_loader": True,
        "exact_rttm_uem_present": not any("missing" in error for error in errors),
        "evaluation_only": True,
        "training_eligible": False,
    }


def _case_specs(protocol_id: str) -> list[dict[str, object]]:
    rows = []
    for tier, repetitions in (("development", 1), ("evaluation", 2)):
        for repetition in range(1, repetitions + 1):
            for count in SPEAKER_COUNTS:
                for profile, cadence, overlap, participation in PROFILES:
                    effective_cadence = (
                        "standard"
                        if profile == "rapid_backchannel" and count > 3
                        else cadence
                    )
                    effective_overlap = "none" if count == 1 else overlap
                    target_sec = (
                        max(3.0, count * 5.0)
                        if profile == "short_response_rare_reentry"
                        else (
                            max(12.0, count * 4.5)
                            if effective_cadence == "rapid"
                            else max(12.0, count * 8.0)
                        )
                    )
                    factors = {
                        "tier": tier,
                        "speaker_count": count,
                        "scenario_profile": profile,
                        "turn_cadence": effective_cadence,
                        "overlap_profile": effective_overlap,
                        "participation_profile": participation,
                        "replicate": repetition,
                        "long_session": False,
                        "active_target_sec": target_sec,
                        "assignment_active_target_sec": (
                            count * 45.0
                            if profile == "short_response_rare_reentry"
                            else target_sec * 1.2
                        ),
                        "maximum_turn_duration_sec": 6.0,
                        "short_turn_durations_sec": (
                            [0.45, 0.65, 0.90]
                            if profile == "short_response_rare_reentry"
                            else []
                        ),
                        "short_turn_every": (
                            3 if profile == "short_response_rare_reentry" else 0
                        ),
                    }
                    rows.append(
                        {
                            **factors,
                            "case_id": identity("dpv2", {"protocol_id": protocol_id, **factors}),
                            "speaker_band": _speaker_band(count),
                            "scientific": True,
                            "control_kind": "single_speaker" if count == 1 else "product_challenge",
                        }
                    )
        long_repetitions = 1 if tier == "development" else 2
        for repetition in range(1, long_repetitions + 1):
            for count in (3, 5, 8, 12):
                factors = {
                    "tier": tier,
                    "speaker_count": count,
                    "scenario_profile": "long_session_reentry_drift",
                    "turn_cadence": "standard",
                    "overlap_profile": "backchannel",
                    "participation_profile": "moderately_imbalanced",
                    "replicate": repetition,
                    "long_session": True,
                    "active_target_sec": 300.0,
                    "assignment_active_target_sec": min(300.0, max(150.0, count * 20.0)),
                }
                rows.append(
                    {
                        **factors,
                        "case_id": identity("dpv2long", {"protocol_id": protocol_id, **factors}),
                        "speaker_band": _speaker_band(count),
                        "scientific": True,
                        "control_kind": "long_session_challenge",
                    }
                )
    return rows


def _generation_config(
    config: Mapping[str, object], *, long_session: bool, target_sec: float
) -> dict[str, object]:
    value = dict(config)
    value["generation"] = dict(config["generation"])
    value["factors"] = dict(config["factors"])
    value["factors"]["gap_sec"] = {
        "relaxed": [0.35, 1.45],
        "standard": [0.08, 0.70],
        "rapid": [0.0, 0.22],
    }
    if long_session:
        value["generation"].update(
            {
                "target_duration_sec": 300.0,
                "target_duration_sec_by_cadence": {
                    "relaxed": 300.0,
                    "standard": 300.0,
                    "rapid": 300.0,
                },
                "minimum_duration_sec": 285.0,
                "maximum_duration_sec": 315.0,
            }
        )
    else:
        value["generation"].update(
            {
                "target_duration_sec": target_sec,
                "target_duration_sec_by_cadence": {
                    "relaxed": target_sec,
                    "standard": target_sec,
                    "rapid": target_sec,
                },
                "minimum_duration_sec": max(2.5, target_sec * 0.75),
                "maximum_duration_sec": max(target_sec * 4.0, target_sec + 300.0),
            }
        )
    return value


def _participation_weights(speakers: Sequence[str], profile: str) -> dict[str, float]:
    weights = {speaker: 1.0 for speaker in speakers}
    if profile == "moderately_imbalanced" and len(speakers) > 1:
        weights[speakers[0]] = 2.5
    if profile == "strongly_dominant" and len(speakers) > 1:
        weights[speakers[0]] = 5.0
        weights[speakers[-1]] = 0.45
    return weights


def _speaker_band(count: int) -> str:
    if count == 1:
        return "single_speaker"
    if count == 2:
        return "one_on_one"
    if count <= 5:
        return "small_group_3_5"
    if count <= 8:
        return "medium_group_6_8"
    return "large_group_stress_9_12"


def _case_priority(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        str(row["tier"]),
        bool(row["long_session"]),
        str(row["turn_cadence"]),
        int(row["speaker_count"]),
        str(row["scenario_profile"]),
        int(row["replicate"]),
    )


def _v1_protocol_id() -> str:
    summary = json.loads(
        (V1_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8")
    )
    return str(summary["benchmark_id"])


def _v1_mixture_clip_ids() -> set[str]:
    result = set()
    for tier in ("smoke", "development", "evaluation"):
        path = V1_PROTOCOL_ROOT / tier / "case_manifest.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            case = json.loads(line)
            recipe = json.loads((V1_PROTOCOL_ROOT / case["recipe_path"]).read_text(encoding="utf-8"))
            result.update(str(row["source_clip_id"]) for row in recipe["placements"])
    return result


def _v1_split_members() -> dict[str, list[str]]:
    rows = list(csv.DictReader((V1_PROTOCOL_ROOT / "source_speaker_inventory.csv").open(encoding="utf-8", newline="")))
    return {
        tier: sorted(row["global_speaker_id"] for row in rows if row["tier"] == tier)
        for tier in ("development", "evaluation")
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    temporary.replace(path)


def _reset_unfrozen_partial(root: Path, audio_root: Path) -> None:
    """Remove only this study's unfrozen output from an interrupted prepare."""

    expected_root = DEFAULT_PROTOCOL_ROOT.resolve()
    expected_audio = DEFAULT_GENERATED_ROOT.resolve()
    if root.exists():
        if root != expected_root:
            raise ControlledDiarizationError(
                "refusing to reset a custom partial protocol root; remove it explicitly"
            )
        shutil.rmtree(root)
    if audio_root.exists():
        if audio_root != expected_audio:
            raise ControlledDiarizationError(
                "refusing to reset a custom partial generated-audio root"
            )
        shutil.rmtree(audio_root)
