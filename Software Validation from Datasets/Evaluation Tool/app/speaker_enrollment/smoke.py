"""Bounded NON-SCIENTIFIC synthetic smoke for enrollment-study contracts."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Mapping, Sequence

from app.benchmark_contracts.canonical import canonical_sha256
from app.speaker_protocol.contracts import BackendIdentity, normalize_vector
from app.speaker_enrollment.analysis import analyze_results
from app.speaker_enrollment.evaluation import evaluate_configuration, validate_configuration_result
from app.speaker_enrollment.protocol import load_protocol_tables


def run_smoke(protocol_root: Path, output_root: Path) -> dict[str, object]:
    output = output_root.resolve()
    if output.exists() and any(output.iterdir()):
        preserved = output.with_name(f"{output.name}.previous-{int(time.time())}")
        os.replace(output, preserved)
    mini = output / "protocol_non_scientific"
    results = output / "results"
    backend = "synthetic_smoke_backend"
    backend_root = results / backend
    tables = load_protocol_tables(protocol_root)
    known = sorted(row["speaker_key"] for row in tables["cohort"] if row["study_role"] == "known")[:2]
    calibration_unknown = sorted(row["speaker_key"] for row in tables["cohort"] if row["study_role"] == "calibration_unknown")[:1]
    evaluation_unknown = sorted(row["speaker_key"] for row in tables["cohort"] if row["study_role"] == "evaluation_unknown")[:1]
    selected_speakers = set(known + calibration_unknown + evaluation_unknown)
    cohort = [row for row in tables["cohort"] if row["speaker_key"] in selected_speakers]
    families = {"count_n1_rep0", "count_n2_rep0"}
    enrollment_sets = [
        row for row in tables["enrollment_sets"]
        if row["speaker_key"] in known and row["selection_family_id"] in families
    ]
    selected_variants = []
    for speaker in selected_speakers:
        role = "known" if speaker in known else "unknown"
        split = "calibration" if speaker in calibration_unknown else "evaluation"
        if speaker in known:
            for known_split in ("calibration", "evaluation"):
                candidates = [
                    row for row in tables["probe_variants"]
                    if row["speaker_key"] == speaker
                    and row["protocol_split"] == known_split
                    and row["duration_label"] in {"0p75s", "3p00s"}
                ]
                first_parent = sorted({row["parent_item_id"] for row in candidates})[0]
                selected_variants.extend(row for row in candidates if row["parent_item_id"] == first_parent)
        else:
            candidates = [
                row for row in tables["probe_variants"]
                if row["speaker_key"] == speaker
                and row["protocol_split"] == split
                and row["speaker_role"] == role
                and row["duration_label"] in {"0p75s", "3p00s"}
            ]
            first_parent = sorted({row["parent_item_id"] for row in candidates})[0]
            selected_variants.extend(row for row in candidates if row["parent_item_id"] == first_parent)
    required_ids = {
        value for row in enrollment_sets for value in json.loads(row["slice_ids_json"])
    } | {row["slice_id"] for row in selected_variants}
    slices = [row for row in tables["audio_slices"] if row["slice_id"] in required_ids]
    mini.mkdir(parents=True, exist_ok=True)
    shutil.copy2(protocol_root / "selection_config.yaml", mini / "selection_config.yaml")
    source_summary = json.loads((protocol_root / "protocol_summary.json").read_text(encoding="utf-8"))
    (mini / "protocol_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "speaker-enrollment-duration-protocol.v1",
                "protocol_id": f"{source_summary['protocol_id']}_NON_SCIENTIFIC_SMOKE",
                "source_protocol_id": source_summary["source_protocol_id"],
                "known_speakers": 2,
                "calibration_unknown_speakers": 1,
                "evaluation_unknown_speakers": 1,
                "non_scientific": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_tsv(mini / "cohort.tsv", cohort)
    _write_tsv(mini / "audio_slices.tsv", slices)
    _write_tsv(mini / "probe_variants.tsv", selected_variants)
    _write_tsv(mini / "enrollment_sets.tsv", enrollment_sets)
    _write_tsv(mini / "probe_parents.tsv", [{"non_scientific": "see probe_variants.tsv"}])
    configurations = []
    for family, count, method in (
        ("count_n1_rep0", 1, "normalized_mean"),
        ("count_n2_rep0", 2, "normalized_mean"),
        ("count_n2_rep0", 2, "duration_weighted_mean"),
    ):
        for label, seconds in (("0p75s", 0.75), ("3p00s", 3.0)):
            value = {
                "schema_version": "speaker-enrollment-configuration.v1",
                "phase": "ProbeDuration",
                "reference_configuration_id": "NON_SCIENTIFIC_SMOKE",
                "selection_family_id": family,
                "enrollment_basis": "natural_utterance_count",
                "enrollment_count": count,
                "enrollment_target_audio_sec": "",
                "repetition": 0,
                "aggregation_method": method,
                "probe_duration_label": label,
                "probe_target_audio_sec": seconds,
            }
            value["configuration_id"] = f"cfg_smoke_{canonical_sha256(value)[:16].lower()}"
            configurations.append(value)
    _write_tsv(mini / "configurations.tsv", configurations)
    identity = BackendIdentity(
        backend_id=backend,
        environment_profile="synthetic-non-scientific",
        model_id="synthetic-contract-only",
        model_hash="0" * 64,
        config_path="NON_SCIENTIFIC",
        config_hash="1" * 64,
        embedding_dimension=4,
        normalization="l2",
        preprocessing={"sample_rate_hz": 16000, "channel_count": 1, "dtype": "float32"},
        aggregation_method="normalized_mean",
        threshold_policy_version="speaker-threshold-policy.v1",
        qualification_status="qualified",
    )
    observations = {}
    bases = {
        known[0]: (1.0, 0.05, 0.0, 0.0),
        known[1]: (0.05, 1.0, 0.0, 0.0),
        calibration_unknown[0]: (-0.8, -0.6, 0.1, 0.0),
        evaluation_unknown[0]: (-0.7, -0.7, 0.0, 0.1),
    }
    slice_by_id = {row["slice_id"]: row for row in slices}
    for slice_id, row in slice_by_id.items():
        base = list(bases[row["speaker_key"]])
        jitter = (int(hashlib.sha256(slice_id.encode("utf-8")).hexdigest()[:4], 16) % 19 - 9) / 1000.0
        base[2] += jitter
        observations[slice_id] = {
            "schema_version": "speaker-enrollment-cached-embedding.v1",
            "slice_id": slice_id,
            "backend_id": backend,
            "status": "ok",
            "duration_sec": float(row["duration_sec"]),
            "vector": normalize_vector(base),
        }
    for configuration in configurations:
        destination = backend_root / "phase_d_probe_duration" / configuration["configuration_id"]
        evaluate_configuration(mini, configuration, identity, observations, destination)
        validate_configuration_result(destination, protocol_root=mini)
    analysis = analyze_results(mini, results, output / "analysis", [backend], bootstrap_repetitions=20)
    smoke_summary = {
        "schema_version": "speaker-enrollment-smoke.v1",
        "label": "NON-SCIENTIFIC",
        "backend": backend,
        "known_speakers": 2,
        "calibration_unknown_speakers": 1,
        "evaluation_unknown_speakers": 1,
        "enrollment_counts": [1, 2],
        "probe_durations_sec": [0.75, 3.0],
        "aggregation_methods": ["normalized_mean", "duration_weighted_mean"],
        "configurations": len(configurations),
        "valid_results": len(configurations),
        "analysis_completed": analysis["completed_configurations"] == len(configurations),
        "model_inference_performed": False,
        "scientific_evidence": False,
        "passed": True,
        "output_root": str(output),
    }
    (output / "SMOKE_SUMMARY.json").write_text(
        json.dumps(smoke_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return smoke_summary


def _write_tsv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
