"""Frozen protocol construction for enrollment quantity and live-duration science."""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import tempfile
from typing import Mapping, Sequence

import yaml

from app.benchmark_contracts.canonical import canonical_sha256
from app.speaker_breadth.commonvoice import validate_protocol as validate_source_protocol
from app.utils.paths import resolve_data_path_from_logical


TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    TOOL_ROOT / "configs" / "automated_evaluation" / "speaker_enrollment_duration.v1.yaml"
)
DEFAULT_SOURCE_PROTOCOL_ROOT = (
    TOOL_ROOT / "benchmarks" / "speaker_breadth" / "commonvoice_60plus_v1"
)
DEFAULT_PROTOCOL_ROOT = (
    TOOL_ROOT / "benchmarks" / "speaker_enrollment" / "speaker_enrollment_duration_v1"
)
SCHEMA_VERSION = "speaker-enrollment-duration-protocol.v1"
SLICE_SCHEMA_VERSION = "speaker-audio-slice.v1"
CONFIG_SCHEMA_VERSION = "speaker-enrollment-configuration.v1"


class SpeakerEnrollmentError(ValueError):
    """Raised when the additive enrollment-study contract is violated."""


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise SpeakerEnrollmentError("enrollment study config must be a mapping")
    required = {
        "schema_version": "speaker-enrollment-duration-policy.v1",
        "protocol_version": "speaker_enrollment_duration_v1",
        "selection_algorithm_version": "speaker-enrollment-duration-selection.v1",
        "seed": 3800,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise SpeakerEnrollmentError(f"config {key} must be {expected!r}")
    return {str(key): value for key, value in payload.items()}


def audit_source_protocol(
    source_protocol_root: Path = DEFAULT_SOURCE_PROTOCOL_ROOT,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    """Measure feasibility without creating slices or running model inference."""

    config = load_config(config_path)
    source_root = source_protocol_root.resolve()
    validate_source_protocol(source_root, verify_audio_hashes=False)
    summary = _read_json(source_root / "protocol_summary.json")
    rows = _read_tsv(source_root / "source_selection.tsv")
    grouped = _group_source_rows(rows)
    paired = _mapping(config["paired_cohort"], "paired_cohort")
    required_enrollment = int(paired["enrollment_clips_per_known"])
    required_audio = float(paired["enrollment_audio_sec_required"])
    required_parents = int(paired["probe_parents_per_speaker_per_split"])
    required_probe = float(paired["probe_parent_min_duration_sec"])

    known = sorted(
        speaker
        for role, split, speaker in grouped
        if role == "known" and split == "enrollment"
    )
    calibration_unknown = sorted(
        speaker
        for role, split, speaker in grouped
        if role == "unknown" and split == "calibration"
    )
    evaluation_unknown = sorted(
        speaker
        for role, split, speaker in grouped
        if role == "unknown" and split == "evaluation"
    )
    enrollment_totals = {
        speaker: sum(float(row["duration_sec"]) for row in grouped[("known", "enrollment", speaker)])
        for speaker in known
    }
    enrollment_counts = {
        speaker: len(grouped[("known", "enrollment", speaker)]) for speaker in known
    }

    def probe_count(role: str, split: str, speaker: str, duration: float) -> int:
        return sum(
            float(row["duration_sec"]) + 1e-9 >= duration
            for row in grouped[(role, split, speaker)]
        )

    core = [
        speaker
        for speaker in known
        if enrollment_counts[speaker] >= required_enrollment
        and enrollment_totals[speaker] + 1e-9 >= required_audio
        and probe_count("known", "calibration", speaker, required_probe) >= required_parents
        and probe_count("known", "evaluation", speaker, required_probe) >= required_parents
    ]
    feasible_cal_unknown = [
        speaker
        for speaker in calibration_unknown
        if probe_count("unknown", "calibration", speaker, required_probe) >= required_parents
    ]
    feasible_eval_unknown = [
        speaker
        for speaker in evaluation_unknown
        if probe_count("unknown", "evaluation", speaker, required_probe) >= required_parents
    ]
    clip_durations = sorted(float(row["duration_sec"]) for row in rows)
    enrollment_total_values = sorted(enrollment_totals.values())
    probe_durations = [
        float(value)
        for value in list(config["probe_durations_sec"])
        + list(config["optional_probe_durations_sec"])
    ]
    budget_support = {
        _seconds_label(float(target)): sum(
            total + 1e-9 >= float(target) for total in enrollment_totals.values()
        )
        for target in config["enrollment_audio_budgets_sec"]
    }
    probe_support: dict[str, object] = {}
    for duration in probe_durations:
        label = _seconds_label(duration)
        known_cal = sum(
            probe_count("known", "calibration", speaker, duration) >= required_parents
            for speaker in known
        )
        known_eval = sum(
            probe_count("known", "evaluation", speaker, duration) >= required_parents
            for speaker in known
        )
        paired_known = sum(
            enrollment_totals[speaker] + 1e-9 >= required_audio
            and probe_count("known", "calibration", speaker, duration) >= required_parents
            and probe_count("known", "evaluation", speaker, duration) >= required_parents
            for speaker in known
        )
        probe_support[label] = {
            "minimum_parent_probes_per_partition": required_parents,
            "known_calibration_speakers": known_cal,
            "known_evaluation_speakers": known_eval,
            "known_paired_with_20_sec_enrollment": paired_known,
            "calibration_unknown_speakers": sum(
                probe_count("unknown", "calibration", speaker, duration) >= required_parents
                for speaker in calibration_unknown
            ),
            "evaluation_unknown_speakers": sum(
                probe_count("unknown", "evaluation", speaker, duration) >= required_parents
                for speaker in evaluation_unknown
            ),
        }
    clip_counts = [len(grouped[key]) for key in grouped]
    result = {
        "schema_version": "speaker-enrollment-feasibility-audit.v1",
        "source_protocol_id": summary["protocol_id"],
        "source_protocol_root": str(source_root),
        "model_inference_performed": False,
        "source_speakers": dict(summary["speakers"]),
        "source_clips": dict(summary["clips"]),
        "clips_per_speaker": _statistics([float(value) for value in clip_counts]),
        "clip_duration_sec": _statistics(clip_durations),
        "known_enrollment_total_sec": _statistics(enrollment_total_values),
        "speakers_supporting_enrollment_count": {
            str(count): sum(value >= int(count) for value in enrollment_counts.values())
            for count in config["enrollment_counts"]
        },
        "speakers_supporting_enrollment_audio_sec": budget_support,
        "probe_support": probe_support,
        "requested_core_requirements": {
            "enrollment_clips": required_enrollment,
            "enrollment_audio_sec": required_audio,
            "probe_parents_per_split": required_parents,
            "probe_parent_duration_sec": required_probe,
        },
        "recommended_core": {
            "known_speakers": len(core),
            "calibration_unknown_speakers": len(feasible_cal_unknown),
            "evaluation_unknown_speakers": len(feasible_eval_unknown),
            "known_speaker_keys_sha256": canonical_sha256(sorted(core)),
            "calibration_unknown_keys_sha256": canonical_sha256(sorted(feasible_cal_unknown)),
            "evaluation_unknown_keys_sha256": canonical_sha256(sorted(feasible_eval_unknown)),
        },
        "design_adjustments": [
            {
                "requested": "optional 10.0-second nested probe prefix",
                "eligible_paired_known_speakers": int(
                    probe_support[_seconds_label(10.0)]["known_paired_with_20_sec_enrollment"]
                ),
                "decision": "excluded_from_primary_v1_grid",
                "reason": "severe paired-cohort collapse; retained in the audit for a future secondary protocol",
            },
            {
                "requested": "five independent enrollment selections at N=5",
                "eligible_source_enrollment_clips_per_speaker": required_enrollment,
                "decision": "five deterministic repetitions retain the same complete set at N=5",
                "reason": "the frozen upstream split has exactly five enrollment clips; order changes do not create new evidence",
            },
        ],
    }
    result["audit_id"] = f"audit_{canonical_sha256(result)[:16].lower()}"
    return result


def prepare_protocol(
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    source_protocol_root: Path = DEFAULT_SOURCE_PROTOCOL_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    """Create the immutable additive protocol, or validate and reuse an existing freeze."""

    destination = protocol_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        validated = validate_protocol(destination, source_protocol_root=source_protocol_root)
        return {**validated, "reused": True}
    config = load_config(config_path)
    source_root = source_protocol_root.resolve()
    audit = audit_source_protocol(source_root, config_path=config_path)
    source_summary = _read_json(source_root / "protocol_summary.json")
    source_selection_path = source_root / "source_selection.tsv"
    identity_payload = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": config["protocol_version"],
        "selection_algorithm_version": config["selection_algorithm_version"],
        "source_protocol_id": source_summary["protocol_id"],
        "source_selection_sha256": _file_sha256(source_selection_path),
        "config_sha256": _file_sha256(config_path),
    }
    protocol_id = f"speaker_enrollment_duration_v1_{canonical_sha256(identity_payload)[:12].lower()}"
    source_rows = _read_tsv(source_selection_path)
    built = _build_protocol_rows(source_rows, config, protocol_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        _write_json(staging / "feasibility_audit.json", audit)
        _write_json(
            staging / "protocol_summary.json",
            {
                "schema_version": SCHEMA_VERSION,
                "protocol_id": protocol_id,
                "source_protocol_id": source_summary["protocol_id"],
                "selection_seed": config["seed"],
                "speech_style": config["scientific_labels"]["speech_style"],
                "duration_quantity": config["duration_policy"]["duration_quantity"],
                "known_speakers": len(built["known_speakers"]),
                "calibration_unknown_speakers": len(built["calibration_unknown_speakers"]),
                "evaluation_unknown_speakers": len(built["evaluation_unknown_speakers"]),
                "probe_parents_per_speaker_per_split": int(config["paired_cohort"]["probe_parents_per_speaker_per_split"]),
                "audio_slices": len(built["audio_slices"]),
                "probe_variants": len(built["probe_variants"]),
                "enrollment_sets": len(built["enrollment_sets"]),
                "phase_a_configurations": sum(row["phase"] == "EnrollmentCount" for row in built["configurations"]),
                "phase_b_configurations": sum(row["phase"] == "EnrollmentDuration" for row in built["configurations"]),
                "phase_c_configurations": sum(row["phase"] == "Aggregation" for row in built["configurations"]),
                "phase_d_requires_reference_selection": True,
                "phase_e_requires_operator_decision_gate": True,
                "full_scientific_study_run": False,
            },
        )
        _write_json(
            staging / "provenance.json",
            {
                "schema_version": "speaker-enrollment-provenance.v1",
                "protocol_id": protocol_id,
                "source_protocol_id": source_summary["protocol_id"],
                "source_selection_sha256": _file_sha256(source_selection_path),
                "source_protocol_manifest_sha256": _file_sha256(source_root / "protocol_files.json"),
                "selection_config_sha256": _file_sha256(config_path),
                "source_protocol_root_supplied_explicitly": True,
                "raw_audio_copied": False,
                "stage10_modified": False,
                "speaker_breadth_protocol_modified": False,
                "speech_style": "prompted_read",
                "session_diversity": "unavailable",
            },
        )
        shutil.copy2(config_path, staging / "selection_config.yaml")
        _write_tsv(staging / "cohort.tsv", built["cohort"])
        _write_tsv(staging / "probe_parents.tsv", built["probe_parents"])
        _write_tsv(staging / "audio_slices.tsv", built["audio_slices"])
        _write_tsv(staging / "probe_variants.tsv", built["probe_variants"])
        _write_tsv(staging / "enrollment_sets.tsv", built["enrollment_sets"])
        _write_tsv(staging / "configurations.tsv", built["configurations"])
        _write_json(
            staging / "phase_templates.json",
            {
                "schema_version": "speaker-enrollment-phase-templates.v1",
                "ProbeDuration": {
                    "requires_reference_enrollment_configuration_id": True,
                    "probe_durations_sec": config["probe_durations_sec"],
                },
                "JointFrontier": {
                    "requires_decision_gate": True,
                    "decision_gate_schema": {
                        "schema_version": "speaker-enrollment-joint-decision.v1",
                        "enrollment_configuration_ids": ["cfg_selected_after_phases_a_to_c"],
                        "probe_durations_sec": ["selected_after_phase_d"],
                    },
                },
            },
        )
        _write_json(staging / "lexical_diagnostic.json", built["lexical_diagnostic"])
        _write_text(staging / "README.md", _frozen_readme(protocol_id, source_summary["protocol_id"], built, config))
        _write_file_index(staging)
        validate_protocol(staging, source_protocol_root=source_root, verify_file_index=True)
        if destination.exists():
            destination.rmdir()
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    validated = validate_protocol(destination, source_protocol_root=source_root)
    return {**validated, "reused": False}


def validate_protocol(
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    source_protocol_root: Path = DEFAULT_SOURCE_PROTOCOL_ROOT,
    verify_file_index: bool = True,
    verify_source_paths: bool = True,
) -> dict[str, object]:
    root = protocol_root.resolve()
    if verify_file_index:
        _validate_file_index(root)
    config = load_config(root / "selection_config.yaml")
    summary = _read_json(root / "protocol_summary.json")
    provenance = _read_json(root / "provenance.json")
    lexical = _read_json(root / "lexical_diagnostic.json")
    source_root = source_protocol_root.resolve()
    source_validation = validate_source_protocol(source_root, verify_audio_hashes=False)
    source_summary = _read_json(source_root / "protocol_summary.json")
    if summary["source_protocol_id"] != source_summary["protocol_id"]:
        raise SpeakerEnrollmentError("selected source protocol ID differs from the frozen source")
    if provenance["source_selection_sha256"] != _file_sha256(source_root / "source_selection.tsv"):
        raise SpeakerEnrollmentError("source_selection.tsv changed after enrollment protocol freeze")
    if provenance["source_protocol_manifest_sha256"] != _file_sha256(source_root / "protocol_files.json"):
        raise SpeakerEnrollmentError("source protocol manifest changed after enrollment protocol freeze")
    if provenance["selection_config_sha256"] != _file_sha256(root / "selection_config.yaml"):
        raise SpeakerEnrollmentError("frozen selection config hash mismatch")
    if int(lexical.get("same_speaker_enrollment_probe_overlap_count", -1)) != 0:
        raise SpeakerEnrollmentError("same-speaker lexical overlap is present")

    cohort = _read_tsv(root / "cohort.tsv")
    slices = _read_tsv(root / "audio_slices.tsv")
    parents = _read_tsv(root / "probe_parents.tsv")
    variants = _read_tsv(root / "probe_variants.tsv")
    sets = _read_tsv(root / "enrollment_sets.tsv")
    configs = _read_tsv(root / "configurations.tsv")
    _require_unique(cohort, "speaker_key", "cohort speaker")
    _require_unique(slices, "slice_id", "audio slice")
    _require_unique(variants, "probe_variant_id", "probe variant")
    _require_unique(configs, "configuration_id", "configuration")
    slice_by_id = {row["slice_id"]: row for row in slices}
    expected_known = {row["speaker_key"] for row in cohort if row["study_role"] == "known"}
    cal_unknown = {
        row["speaker_key"] for row in cohort if row["study_role"] == "calibration_unknown"
    }
    eval_unknown = {
        row["speaker_key"] for row in cohort if row["study_role"] == "evaluation_unknown"
    }
    if expected_known & (cal_unknown | eval_unknown):
        raise SpeakerEnrollmentError("known and Unknown speaker cohorts overlap")
    if cal_unknown & eval_unknown:
        raise SpeakerEnrollmentError("calibration and evaluation Unknown speakers overlap")
    for row in slices:
        expected = audio_slice_id(
            row["parent_item_id"],
            float(row["start_sec"]),
            float(row["end_sec"]),
            row["duration_policy_version"],
        )
        if row["slice_id"] != expected:
            raise SpeakerEnrollmentError(f"duration slice identity changed: {row['slice_id']}")
        duration = float(row["duration_sec"])
        if duration <= 0 or not math.isclose(
            duration, float(row["end_sec"]) - float(row["start_sec"]), abs_tol=1e-6
        ):
            raise SpeakerEnrollmentError(f"invalid slice duration: {row['slice_id']}")
        if float(row["end_sec"]) > float(row["parent_duration_sec"]) + 1e-6:
            raise SpeakerEnrollmentError(f"slice exceeds parent duration: {row['slice_id']}")
        if verify_source_paths and not resolve_data_path_from_logical(row["audio_path_project_relative"]).is_file():
            raise SpeakerEnrollmentError(f"source audio is missing: {row['audio_path_project_relative']}")
    parent_roles: dict[str, set[str]] = defaultdict(set)
    for row in slices:
        parent_roles[row["parent_item_id"]].add(row["protocol_split"])
    if any(len(value) != 1 for value in parent_roles.values()):
        raise SpeakerEnrollmentError("one source item appears in multiple protocol splits")
    if any(row["speaker_role"] == "unknown" and row["protocol_split"] == "enrollment" for row in slices):
        raise SpeakerEnrollmentError("Unknown speaker was enrolled")
    families: dict[str, set[str]] = defaultdict(set)
    for row in sets:
        families[row["selection_family_id"]].add(row["speaker_key"])
        ids = json.loads(row["slice_ids_json"])
        if not ids or any(value not in slice_by_id for value in ids):
            raise SpeakerEnrollmentError(f"enrollment set references invalid slices: {row['selection_id']}")
    if any(value != expected_known for value in families.values()):
        raise SpeakerEnrollmentError("paired enrollment families do not contain the identical core cohort")
    variant_lookup = {(row["parent_item_id"], row["duration_label"]): row for row in variants}
    required_labels = ["natural", *(_seconds_label(float(v)) for v in config["probe_durations_sec"])]
    for parent in parents:
        rows_for_parent = [variant_lookup.get((parent["parent_item_id"], label)) for label in required_labels]
        if any(row is None for row in rows_for_parent):
            raise SpeakerEnrollmentError(f"probe parent lacks a nested duration variant: {parent['parent_item_id']}")
        starts = {float(row["start_sec"]) for row in rows_for_parent if row is not None}
        if starts != {0.0}:
            raise SpeakerEnrollmentError("nested probe prefixes do not share the same start")
        numeric = [row for row in rows_for_parent if row is not None and row["duration_label"] != "natural"]
        if [float(row["end_sec"]) for row in numeric] != sorted(float(row["end_sec"]) for row in numeric):
            raise SpeakerEnrollmentError("nested probe prefix ends are not monotonic")
    config_families = {row["selection_family_id"] for row in configs}
    if not config_families <= set(families):
        raise SpeakerEnrollmentError("configuration references an unknown enrollment family")
    return {
        "schema_version": "speaker-enrollment-validation.v1",
        "protocol_id": summary["protocol_id"],
        "source_protocol_id": summary["source_protocol_id"],
        "known_speakers": len(expected_known),
        "calibration_unknown_speakers": len(cal_unknown),
        "evaluation_unknown_speakers": len(eval_unknown),
        "audio_slices": len(slices),
        "configurations": len(configs),
        "source_paths_checked": verify_source_paths,
        "source_protocol_valid": bool(source_validation),
        "split_disjointness": "PASS",
        "unknown_never_enrolled": "PASS",
        "calibration_evaluation_unknown_disjoint": "PASS",
        "core_cohort_consistent": "PASS",
        "duration_slice_determinism": "PASS",
        "nested_probe_prefixes": "PASS",
        "configuration_hash": "PASS",
        "same_speaker_lexical_overlap": "PASS",
        "valid": True,
    }


def protocol_plan(
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    *,
    source_protocol_root: Path = DEFAULT_SOURCE_PROTOCOL_ROOT,
    backends: Sequence[str] = (),
    phase: str = "All",
) -> dict[str, object]:
    validation = validate_protocol(
        protocol_root, source_protocol_root=source_protocol_root, verify_source_paths=True
    )
    root = protocol_root.resolve()
    summary = _read_json(root / "protocol_summary.json")
    slices = _read_tsv(root / "audio_slices.tsv")
    variants = _read_tsv(root / "probe_variants.tsv")
    configs = _read_tsv(root / "configurations.tsv")
    phases = ["EnrollmentCount", "EnrollmentDuration", "Aggregation"]
    selected_phases = phases if phase == "All" else [phase]
    phase_rows = [row for row in configs if row["phase"] in selected_phases]
    families = {row["selection_family_id"] for row in phase_rows}
    enrollment_sets = [
        row for row in _read_tsv(root / "enrollment_sets.tsv") if row["selection_family_id"] in families
    ]
    slice_ids = {
        value for row in enrollment_sets for value in json.loads(row["slice_ids_json"])
    }
    if any(row["probe_duration_label"] == "natural" for row in phase_rows):
        slice_ids.update(row["slice_id"] for row in variants if row["duration_label"] == "natural")
    phase_workload = {}
    for name in ["EnrollmentCount", "EnrollmentDuration", "Aggregation"]:
        subset = [row for row in configs if row["phase"] == name]
        family_ids = {row["selection_family_id"] for row in subset}
        ids = {
            value
            for row in _read_tsv(root / "enrollment_sets.tsv")
            if row["selection_family_id"] in family_ids
            for value in json.loads(row["slice_ids_json"])
        }
        if subset:
            ids.update(row["slice_id"] for row in variants if row["duration_label"] == "natural")
        phase_workload[name] = {
            "evaluation_configurations": len(subset),
            "unique_embedding_slices": len(ids),
        }
    all_prefix_ids = {row["slice_id"] for row in variants if row["duration_label"] != "natural"}
    phase_workload["ProbeDuration"] = {
        "evaluation_configurations": len(load_config(root / "selection_config.yaml")["probe_durations_sec"]),
        "unique_probe_prefix_slices": len(all_prefix_ids),
        "requires_reference_enrollment_configuration": True,
    }
    phase_workload["JointFrontier"] = {
        "evaluation_configurations": "decision_gate_dependent",
        "unique_embedding_slices": "decision_gate_dependent_and_cached",
        "requires_operator_decision_gate": True,
    }
    known = int(summary["known_speakers"])
    calibration_unknown = int(summary["calibration_unknown_speakers"])
    evaluation_unknown = int(summary["evaluation_unknown_speakers"])
    parents_per_split = int(summary["probe_parents_per_speaker_per_split"])
    calibration_probes = (known + calibration_unknown) * parents_per_split
    evaluation_probes = (known + evaluation_unknown) * parents_per_split
    score_trials_per_configuration = (calibration_probes + evaluation_probes) * known
    if phase == "All":
        slice_ids = {row["slice_id"] for row in slices}
        planned_configurations: int | str = len(configs) + len(load_config(root / "selection_config.yaml")["probe_durations_sec"])
    elif phase == "ProbeDuration":
        slice_ids = set(all_prefix_ids)
        planned_configurations = len(load_config(root / "selection_config.yaml")["probe_durations_sec"])
    elif phase == "JointFrontier":
        planned_configurations = "decision_gate_dependent"
    else:
        planned_configurations = len(phase_rows)
    embedding_count = len(slice_ids) * max(1, len(backends))
    return {
        "schema_version": "speaker-enrollment-plan.v1",
        "protocol_id": summary["protocol_id"],
        "source_protocol_id": summary["source_protocol_id"],
        "selected_phase": phase,
        "selected_backends": list(backends),
        "core_known_speakers": summary["known_speakers"],
        "calibration_unknown_speakers": summary["calibration_unknown_speakers"],
        "evaluation_unknown_speakers": summary["evaluation_unknown_speakers"],
        "unique_source_clips": len({row["parent_item_id"] for row in slices}),
        "unique_audio_slices": len(slice_ids),
        "unique_embeddings_per_backend": len(slice_ids),
        "unique_embedding_extractions": embedding_count,
        "evaluation_configurations": planned_configurations,
        "score_trials_per_configuration": score_trials_per_configuration,
        "estimated_embedding_vector_bytes_per_backend_at_256d_float32": len(slice_ids) * 256 * 4,
        "estimated_embedding_cache_bytes_per_backend_at_256d_including_item_overhead": len(slice_ids) * (256 * 4 + 2500),
        "estimated_result_bytes_per_backend_before_joint_frontier": (len(configs) + len(load_config(root / "selection_config.yaml")["probe_durations_sec"])) * score_trials_per_configuration * 12,
        "result_root": str(Path.home() / "JustPeachyResults" / "speaker_enrollment" / str(summary["protocol_id"])),
        "phase_workload": phase_workload,
        "model_inference_performed": False,
        "validation": validation,
    }


def audio_slice_id(parent_item_id: str, start_sec: float, end_sec: float, policy: str) -> str:
    payload = {
        "schema_version": SLICE_SCHEMA_VERSION,
        "parent_item_id": str(parent_item_id),
        "start_microseconds": round(float(start_sec) * 1_000_000),
        "end_microseconds": round(float(end_sec) * 1_000_000),
        "duration_policy_version": str(policy),
    }
    return f"slice_{canonical_sha256(payload)[:24].lower()}"


def load_protocol_tables(protocol_root: Path) -> dict[str, list[dict[str, str]]]:
    root = protocol_root.resolve()
    return {
        name: _read_tsv(root / f"{name}.tsv")
        for name in ("cohort", "probe_parents", "audio_slices", "probe_variants", "enrollment_sets", "configurations")
    }


def resolve_phase_configurations(
    protocol_root: Path,
    phase: str,
    *,
    reference_enrollment_configuration_id: str = "",
    decision_gate: Path | None = None,
) -> list[dict[str, object]]:
    tables = load_protocol_tables(protocol_root)
    base = [dict(row) for row in tables["configurations"]]
    if phase in {"EnrollmentCount", "EnrollmentDuration", "Aggregation"}:
        return [row for row in base if row["phase"] == phase]
    config = load_config(protocol_root / "selection_config.yaml")
    by_id = {row["configuration_id"]: row for row in base}
    if phase == "ProbeDuration":
        if reference_enrollment_configuration_id not in by_id:
            raise SpeakerEnrollmentError(
                "ProbeDuration requires -ReferenceEnrollmentConfigId from a completed EnrollmentCount, EnrollmentDuration, or Aggregation result"
            )
        references = [by_id[reference_enrollment_configuration_id]]
        durations = [float(value) for value in config["probe_durations_sec"]]
    elif phase == "JointFrontier":
        if decision_gate is None:
            raise SpeakerEnrollmentError("JointFrontier requires an explicit -DecisionGate created after earlier-phase analysis")
        gate = yaml.safe_load(decision_gate.read_text(encoding="utf-8")) or {}
        if gate.get("schema_version") != "speaker-enrollment-joint-decision.v1":
            raise SpeakerEnrollmentError("JointFrontier decision gate schema is invalid")
        ids = [str(value) for value in gate.get("enrollment_configuration_ids", [])]
        durations = [float(value) for value in gate.get("probe_durations_sec", [])]
        if not ids or not durations:
            raise SpeakerEnrollmentError("JointFrontier decision gate must select enrollment configurations and probe durations")
        unknown = sorted(set(ids) - set(by_id))
        if unknown:
            raise SpeakerEnrollmentError(f"decision gate references unknown configurations: {unknown}")
        allowed = {float(value) for value in config["probe_durations_sec"]}
        if not set(durations) <= allowed:
            raise SpeakerEnrollmentError("decision gate requests probe durations outside the frozen v1 grid")
        references = [by_id[value] for value in ids]
    else:
        raise SpeakerEnrollmentError(f"unsupported phase: {phase}")
    result = []
    for reference in references:
        for duration in durations:
            payload = {
                "schema_version": CONFIG_SCHEMA_VERSION,
                "phase": phase,
                "reference_configuration_id": reference["configuration_id"],
                "selection_family_id": reference["selection_family_id"],
                "enrollment_basis": reference["enrollment_basis"],
                "enrollment_count": reference["enrollment_count"],
                "enrollment_target_audio_sec": reference["enrollment_target_audio_sec"],
                "repetition": reference["repetition"],
                "aggregation_method": reference["aggregation_method"],
                "probe_duration_label": _seconds_label(duration),
                "probe_target_audio_sec": _format_float(duration),
            }
            payload["configuration_id"] = f"cfg_{canonical_sha256(payload)[:20].lower()}"
            result.append(payload)
    return result


def required_slice_ids(
    protocol_root: Path,
    configurations: Sequence[Mapping[str, object]],
) -> set[str]:
    tables = load_protocol_tables(protocol_root)
    families = {str(row["selection_family_id"]) for row in configurations}
    result = {
        value
        for row in tables["enrollment_sets"]
        if row["selection_family_id"] in families
        for value in json.loads(row["slice_ids_json"])
    }
    labels = {str(row["probe_duration_label"]) for row in configurations}
    result.update(
        row["slice_id"] for row in tables["probe_variants"] if row["duration_label"] in labels
    )
    return result


def _build_protocol_rows(
    source_rows: Sequence[Mapping[str, str]],
    config: Mapping[str, object],
    protocol_id: str,
) -> dict[str, object]:
    grouped = _group_source_rows(source_rows)
    paired = _mapping(config["paired_cohort"], "paired_cohort")
    required_count = int(paired["enrollment_clips_per_known"])
    required_audio = float(paired["enrollment_audio_sec_required"])
    required_parents = int(paired["probe_parents_per_speaker_per_split"])
    required_probe = float(paired["probe_parent_min_duration_sec"])
    known_candidates = sorted(
        speaker for role, split, speaker in grouped if role == "known" and split == "enrollment"
    )

    def enough(role: str, split: str, speaker: str) -> bool:
        return sum(float(row["duration_sec"]) + 1e-9 >= required_probe for row in grouped[(role, split, speaker)]) >= required_parents

    known = [
        speaker
        for speaker in known_candidates
        if len(grouped[("known", "enrollment", speaker)]) >= required_count
        and sum(float(row["duration_sec"]) for row in grouped[("known", "enrollment", speaker)]) + 1e-9 >= required_audio
        and enough("known", "calibration", speaker)
        and enough("known", "evaluation", speaker)
    ]
    calibration_unknown = sorted(
        speaker
        for role, split, speaker in grouped
        if role == "unknown" and split == "calibration" and enough(role, split, speaker)
    )
    evaluation_unknown = sorted(
        speaker
        for role, split, speaker in grouped
        if role == "unknown" and split == "evaluation" and enough(role, split, speaker)
    )
    cohort: list[dict[str, object]] = []
    for study_role, speakers, source_role, split in (
        ("known", known, "known", "enrollment"),
        ("calibration_unknown", calibration_unknown, "unknown", "calibration"),
        ("evaluation_unknown", evaluation_unknown, "unknown", "evaluation"),
    ):
        for speaker in speakers:
            row = grouped[(source_role, split, speaker)][0]
            cohort.append(
                {
                    "speaker_key": speaker,
                    "study_role": study_role,
                    "age_category": row.get("age_category", ""),
                    "gender": row.get("gender", ""),
                    "accent": row.get("accent", ""),
                    "variant": row.get("variant", ""),
                    "locale": row.get("locale", ""),
                    "session_id": "",
                    "device_id": "",
                    "speech_style": "prompted_read",
                }
            )
    selected_probe_parents: list[dict[str, object]] = []
    for role, split, speakers in (
        ("known", "calibration", known),
        ("known", "evaluation", known),
        ("unknown", "calibration", calibration_unknown),
        ("unknown", "evaluation", evaluation_unknown),
    ):
        for speaker in speakers:
            candidates = [
                row for row in grouped[(role, split, speaker)] if float(row["duration_sec"]) + 1e-9 >= required_probe
            ]
            selected = sorted(
                candidates,
                key=lambda row: _rank(protocol_id, "probe-parent", speaker, split, row["item_id"]),
            )[:required_parents]
            for ordinal, row in enumerate(selected, start=1):
                selected_probe_parents.append(
                    {
                        "parent_item_id": row["item_id"],
                        "speaker_key": speaker,
                        "speaker_role": role,
                        "protocol_split": split,
                        "parent_ordinal": ordinal,
                        "parent_duration_sec": _format_float(float(row["duration_sec"])),
                        "transcript_sha256": row.get("transcript_sha256", ""),
                        "selection_rank": _rank(protocol_id, "probe-parent", speaker, split, row["item_id"]),
                    }
                )
    source_by_id = {row["item_id"]: row for row in source_rows}
    duration_policy = str(config["duration_policy"]["version"])
    slice_by_id: dict[str, dict[str, object]] = {}

    def add_slice(parent: Mapping[str, str], end_sec: float) -> str:
        end = round(float(end_sec), int(config["duration_policy"]["end_rounding_decimals"]))
        start = float(config["duration_policy"]["start_sec"])
        item_id = audio_slice_id(parent["item_id"], start, end, duration_policy)
        row = {
            "slice_id": item_id,
            "parent_item_id": parent["item_id"],
            "speaker_key": parent["speaker_key"],
            "speaker_role": parent["speaker_role"],
            "protocol_split": parent["protocol_split"],
            "trial_role": parent["trial_role"],
            "protocol_condition": "clean",
            "audio_path_project_relative": parent["logical_audio_path"],
            "source_recording_id": parent["source_recording_id"],
            "parent_audio_sha256": parent["audio_sha256"],
            "parent_duration_sec": _format_float(float(parent["duration_sec"])),
            "start_sec": _format_float(start),
            "end_sec": _format_float(end),
            "duration_sec": _format_float(end - start),
            "duration_policy_version": duration_policy,
            "duration_quantity": config["duration_policy"]["duration_quantity"],
            "speech_style": "prompted_read",
            "transcript_sha256": parent.get("transcript_sha256", ""),
            "age_category": parent.get("age_category", ""),
            "gender": parent.get("gender", ""),
            "accent": parent.get("accent", ""),
            "variant": parent.get("variant", ""),
            "locale": parent.get("locale", ""),
        }
        prior = slice_by_id.setdefault(item_id, row)
        if prior != row:
            raise SpeakerEnrollmentError("audio-slice ID collision")
        return item_id

    enrollment_order: dict[str, list[Mapping[str, str]]] = {}
    for speaker in known:
        values = sorted(
            grouped[("known", "enrollment", speaker)],
            key=lambda row: _rank(protocol_id, "enrollment-order", speaker, row["item_id"]),
        )[:required_count]
        enrollment_order[speaker] = values
        for row in values:
            add_slice(row, float(row["duration_sec"]))
    repetitions = int(config["enrollment_selection_repetitions"])
    enrollment_sets: list[dict[str, object]] = []
    for count in config["enrollment_counts"]:
        for repetition in range(repetitions):
            family = f"count_n{int(count)}_rep{repetition}"
            for speaker in known:
                ordered = _rotate(enrollment_order[speaker], repetition)
                chosen = ordered[: int(count)]
                ids = [add_slice(row, float(row["duration_sec"])) for row in chosen]
                enrollment_sets.append(
                    _enrollment_set_row(protocol_id, family, "natural_utterance_count", int(count), None, repetition, speaker, ids, chosen, slice_by_id)
                )
    for target in config["enrollment_audio_budgets_sec"]:
        budget = float(target)
        for repetition in range(repetitions):
            family = f"duration_{_seconds_label(budget)}_rep{repetition}"
            for speaker in known:
                ordered = _rotate(enrollment_order[speaker], repetition)
                remaining = budget
                ids: list[str] = []
                parents_used: list[Mapping[str, str]] = []
                for parent in ordered:
                    if remaining <= 1e-9:
                        break
                    use = min(float(parent["duration_sec"]), remaining)
                    ids.append(add_slice(parent, use))
                    parents_used.append(parent)
                    remaining -= use
                if remaining > 1e-6:
                    raise SpeakerEnrollmentError(f"speaker {speaker} cannot meet {budget}s budget")
                enrollment_sets.append(
                    _enrollment_set_row(protocol_id, family, "available_audio_budget", None, budget, repetition, speaker, ids, parents_used, slice_by_id)
                )
    probe_variants: list[dict[str, object]] = []
    duration_values = [float(value) for value in config["probe_durations_sec"]]
    for selected in selected_probe_parents:
        parent = source_by_id[str(selected["parent_item_id"])]
        variants: list[tuple[str, float]] = [("natural", float(parent["duration_sec"]))]
        variants.extend((_seconds_label(value), value) for value in duration_values)
        for label, end in variants:
            slice_id = add_slice(parent, end)
            probe_variants.append(
                {
                    "probe_variant_id": f"probe_{canonical_sha256({'parent': parent['item_id'], 'label': label, 'slice': slice_id})[:24].lower()}",
                    "parent_item_id": parent["item_id"],
                    "slice_id": slice_id,
                    "speaker_key": parent["speaker_key"],
                    "speaker_role": parent["speaker_role"],
                    "protocol_split": parent["protocol_split"],
                    "duration_label": label,
                    "target_audio_sec": "" if label == "natural" else _format_float(end),
                    "actual_audio_sec": _format_float(end),
                    "start_sec": "0.000000",
                    "end_sec": _format_float(end),
                    "duration_policy_version": duration_policy,
                }
            )
    configurations: list[dict[str, object]] = []

    def add_config(phase: str, family: str, basis: str, count: int | None, budget: float | None, repetition: int, method: str) -> None:
        payload = {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "phase": phase,
            "selection_family_id": family,
            "enrollment_basis": basis,
            "enrollment_count": "" if count is None else int(count),
            "enrollment_target_audio_sec": "" if budget is None else _format_float(budget),
            "repetition": repetition,
            "aggregation_method": method,
            "probe_duration_label": "natural",
            "probe_target_audio_sec": "",
            "reference_configuration_id": "",
        }
        payload["configuration_id"] = f"cfg_{canonical_sha256(payload)[:20].lower()}"
        configurations.append(payload)

    for count in config["enrollment_counts"]:
        for repetition in range(repetitions):
            add_config("EnrollmentCount", f"count_n{int(count)}_rep{repetition}", "natural_utterance_count", int(count), None, repetition, "normalized_mean")
    for target in config["enrollment_audio_budgets_sec"]:
        for repetition in range(repetitions):
            add_config("EnrollmentDuration", f"duration_{_seconds_label(float(target))}_rep{repetition}", "available_audio_budget", None, float(target), repetition, "normalized_mean")
    for count in config["phase_design"]["Aggregation"]["enrollment_counts"]:
        for repetition in range(repetitions):
            for method in config["aggregation_methods"]:
                add_config("Aggregation", f"count_n{int(count)}_rep{repetition}", "natural_utterance_count", int(count), None, repetition, str(method))
    enrollment_transcripts = {
        speaker: {
            row.get("transcript_sha256", "")
            for row in grouped[("known", "enrollment", speaker)]
            if row.get("transcript_sha256")
        }
        for speaker in known
    }
    probe_transcripts: dict[str, set[str]] = defaultdict(set)
    for row in selected_probe_parents:
        if row["speaker_role"] == "known" and row.get("transcript_sha256"):
            probe_transcripts[str(row["speaker_key"])].add(str(row["transcript_sha256"]))
    overlap = {
        speaker: sorted(enrollment_transcripts[speaker] & probe_transcripts.get(speaker, set()))
        for speaker in known
    }
    overlap = {speaker: values for speaker, values in overlap.items() if values}
    lexical_diagnostic = {
        "schema_version": "speaker-enrollment-lexical-diagnostic.v1",
        "known_speakers": len(known),
        "enrollment_transcript_hashes_present": sum(len(value) for value in enrollment_transcripts.values()),
        "selected_probe_transcript_hashes_present": sum(len(value) for value in probe_transcripts.values()),
        "same_speaker_enrollment_probe_overlap_speakers": len(overlap),
        "same_speaker_enrollment_probe_overlap_count": sum(len(value) for value in overlap.values()),
        "overlap_hashes_by_speaker": overlap,
        "formal_repeated_phrase_comparison_performed": False,
        "diagnostic_only": True,
    }
    return {
        "known_speakers": known,
        "calibration_unknown_speakers": calibration_unknown,
        "evaluation_unknown_speakers": evaluation_unknown,
        "cohort": sorted(cohort, key=lambda row: (str(row["study_role"]), str(row["speaker_key"]))),
        "probe_parents": sorted(selected_probe_parents, key=lambda row: (str(row["protocol_split"]), str(row["speaker_role"]), str(row["speaker_key"]), int(row["parent_ordinal"]))),
        "audio_slices": sorted(slice_by_id.values(), key=lambda row: str(row["slice_id"])),
        "probe_variants": sorted(probe_variants, key=lambda row: str(row["probe_variant_id"])),
        "enrollment_sets": sorted(enrollment_sets, key=lambda row: (str(row["selection_family_id"]), str(row["speaker_key"]))),
        "configurations": sorted(configurations, key=lambda row: (str(row["phase"]), str(row["configuration_id"]))),
        "lexical_diagnostic": lexical_diagnostic,
    }


def _enrollment_set_row(
    protocol_id: str,
    family: str,
    basis: str,
    count: int | None,
    budget: float | None,
    repetition: int,
    speaker: str,
    slice_ids: Sequence[str],
    parents: Sequence[Mapping[str, str]],
    slice_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    actual = sum(float(slice_by_id[value]["duration_sec"]) for value in slice_ids)
    parent_ids = [row["item_id"] for row in parents]
    transcripts = {row.get("transcript_sha256", "") for row in parents if row.get("transcript_sha256")}
    payload = {
        "protocol_id": protocol_id,
        "selection_family_id": family,
        "speaker_key": speaker,
        "slice_ids": list(slice_ids),
    }
    return {
        "selection_id": f"ensel_{canonical_sha256(payload)[:24].lower()}",
        "selection_family_id": family,
        "enrollment_basis": basis,
        "target_count": "" if count is None else count,
        "target_audio_sec": "" if budget is None else _format_float(budget),
        "repetition": repetition,
        "speaker_key": speaker,
        "slice_ids_json": json.dumps(list(slice_ids), separators=(",", ":")),
        "parent_item_ids_json": json.dumps(parent_ids, separators=(",", ":")),
        "actual_utterance_count": len(parent_ids),
        "actual_audio_sec": _format_float(actual),
        "distinct_enrollment_texts": len(transcripts),
        "source_session_diversity": "unavailable",
        "selection_reuse_note": "all_five_source_clips_reused_at_n5" if count == 5 else "deterministic_cyclic_selection_may_overlap_across_repetitions",
    }


def _frozen_readme(
    protocol_id: str,
    source_protocol_id: str,
    built: Mapping[str, object],
    config: Mapping[str, object],
) -> str:
    return f"""# Frozen speaker enrollment-duration protocol

Protocol ID: `{protocol_id}`
Source protocol ID: `{source_protocol_id}`

This package contains only deterministic manifests, provenance, feasibility evidence, and checksums. It contains no audio, embeddings, model assets, or identity reverse map. The source is Common Voice prompted/read speech; every duration is available waveform duration beginning at the source-file start, not measured voiced-speech duration.

The primary paired cohort contains {len(built['known_speakers'])} known speakers, {len(built['calibration_unknown_speakers'])} calibration Unknown speakers, and {len(built['evaluation_unknown_speakers'])} evaluation Unknown speakers. Each retained speaker supplies three independent source probe parents per applicable partition, and every parent supports all nested prefixes through 5.0 seconds. Known speakers also support all five source enrollment clips and 20.0 seconds of accumulated enrollment audio.

The proposed optional 10-second probe is not in v1 because no known speaker supports three 10-second calibration parents, three 10-second evaluation parents, and the 20-second enrollment requirement simultaneously. It remains visible in `feasibility_audit.json`. Phase D requires an explicit reference enrollment configuration chosen after earlier-phase analysis. Phase E requires an explicit operator decision gate; no product threshold or duration is selected automatically.

Use `app/speaker_enrollment/README.md` and `scripts/run_speaker_enrollment_study.ps1` for Anaconda Prompt, Command Prompt, PowerShell, inputs, outputs, and restart-safe execution.
"""


def _group_source_rows(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    result: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for original in rows:
        row = dict(original)
        result[(row["speaker_role"], row["protocol_split"], row["speaker_key"])].append(row)
    return result


def _rotate(values: Sequence[Mapping[str, str]], amount: int) -> list[Mapping[str, str]]:
    if not values:
        return []
    index = int(amount) % len(values)
    return [*values[index:], *values[:index]]


def _seconds_label(value: float) -> str:
    return f"{float(value):.2f}s".replace(".", "p")


def _format_float(value: float) -> str:
    return f"{float(value):.6f}"


def _rank(protocol_id: str, *values: str) -> str:
    return hashlib.sha256("|".join((protocol_id, *map(str, values))).encode("utf-8")).hexdigest()


def _statistics(values: Sequence[float]) -> dict[str, object]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"count": 0}
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "p05": _quantile(ordered, 0.05),
        "p25": _quantile(ordered, 0.25),
        "median": statistics.median(ordered),
        "p75": _quantile(ordered, 0.75),
        "p95": _quantile(ordered, 0.95),
        "maximum": ordered[-1],
        "mean": statistics.mean(ordered),
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    weight = position - lower
    return float(values[lower]) * (1.0 - weight) + float(values[upper]) * weight


def _require_unique(rows: Sequence[Mapping[str, str]], field: str, label: str) -> None:
    values = [row[field] for row in rows]
    if len(values) != len(set(values)):
        raise SpeakerEnrollmentError(f"duplicate {label} identity")


def _write_file_index(root: Path) -> None:
    excluded = {"protocol_files.json", "protocol_files.sha256"}
    rows = []
    for path in sorted(value for value in root.rglob("*") if value.is_file() and value.name not in excluded):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    payload = {"schema_version": "speaker-enrollment-file-index.v1", "files": rows}
    _write_json(root / "protocol_files.json", payload)
    _write_text(root / "protocol_files.sha256", f"{_file_sha256(root / 'protocol_files.json')}  protocol_files.json\n")


def _validate_file_index(root: Path) -> None:
    index_path = root / "protocol_files.json"
    declared = (root / "protocol_files.sha256").read_text(encoding="utf-8").split()[0]
    if declared.upper() != _file_sha256(index_path).upper():
        raise SpeakerEnrollmentError("protocol file index checksum changed")
    payload = _read_json(index_path)
    for row in payload.get("files", []):
        path = root / str(row["path"])
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or _file_sha256(path).upper() != str(row["sha256"]).upper():
            raise SpeakerEnrollmentError(f"frozen protocol artifact changed: {row['path']}")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SpeakerEnrollmentError(f"JSON document must be an object: {path}")
    return {str(key): item for key, item in value.items()}


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def _write_tsv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise SpeakerEnrollmentError(f"refusing to write empty TSV: {path}")
    fields = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SpeakerEnrollmentError(f"{name} must be a mapping")
    return {str(key): item for key, item in value.items()}
