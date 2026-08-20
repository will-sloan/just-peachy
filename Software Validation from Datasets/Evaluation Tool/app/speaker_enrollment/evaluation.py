"""Per-configuration calibration, held-out evaluation, and result validation."""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Mapping, Sequence

import numpy as np

from app.benchmark_contracts.canonical import canonical_sha256
from app.speaker_protocol.contracts import BackendIdentity, normalize_vector
from app.speaker_protocol.metrics import (
    cosine_similarity,
    equal_error_rate,
    operating_point,
    tar_at_fixed_far,
    threshold_sweep,
)
from app.speaker_enrollment.extraction import (
    load_cached_embeddings,
    validate_embedding_cache,
)
from app.speaker_enrollment.protocol import (
    SpeakerEnrollmentError,
    load_config,
    load_protocol_tables,
    required_slice_ids,
)


RESULT_SCHEMA_VERSION = "speaker-enrollment-configuration-result.v1"


def threshold_artifact_id(backend_identity_hash: str, configuration_identity_hash: str) -> str:
    """Return the immutable backend-and-configuration-specific threshold identity."""

    return f"threshold_{canonical_sha256({'backend': backend_identity_hash, 'configuration': configuration_identity_hash, 'split': 'calibration'})[:20].lower()}"


def normalized_mean(vectors: Sequence[Sequence[float]]) -> tuple[float, ...]:
    if not vectors:
        raise SpeakerEnrollmentError("normalized_mean requires at least one embedding")
    normalized = [normalize_vector(vector) for vector in vectors]
    return normalize_vector([sum(row[index] for row in normalized) / len(normalized) for index in range(len(normalized[0]))])


def duration_weighted_mean(
    vectors: Sequence[Sequence[float]], durations_sec: Sequence[float]
) -> tuple[float, ...]:
    if not vectors or len(vectors) != len(durations_sec):
        raise SpeakerEnrollmentError("duration-weighted mean requires matched vectors and durations")
    if any(float(value) <= 0 for value in durations_sec):
        raise SpeakerEnrollmentError("duration weights must be positive")
    normalized = [normalize_vector(vector) for vector in vectors]
    total = sum(float(value) for value in durations_sec)
    return normalize_vector(
        [
            sum(row[index] * float(weight) for row, weight in zip(normalized, durations_sec, strict=True)) / total
            for index in range(len(normalized[0]))
        ]
    )


def score_templates(
    probe: Sequence[float],
    templates: Sequence[Sequence[float]],
    method: str,
    durations_sec: Sequence[float],
) -> float:
    if method == "normalized_mean":
        return cosine_similarity(probe, normalized_mean(templates))
    if method == "duration_weighted_mean":
        return cosine_similarity(probe, duration_weighted_mean(templates, durations_sec))
    if method == "multi_template_mean_score":
        if not templates:
            raise SpeakerEnrollmentError("multi-template scoring requires enrollment templates")
        return sum(cosine_similarity(probe, normalize_vector(value)) for value in templates) / len(templates)
    raise SpeakerEnrollmentError(f"unsupported aggregation method: {method}")


def evaluate_configurations(
    protocol_root: Path,
    configurations: Sequence[Mapping[str, object]],
    component_name: str,
    cache_root: Path,
    result_root: Path,
) -> dict[str, object]:
    required = required_slice_ids(protocol_root, configurations)
    validate_embedding_cache(protocol_root, component_name, cache_root, required)
    identity, observations = load_cached_embeddings(cache_root, required)
    if identity.backend_id != component_name:
        raise SpeakerEnrollmentError("backend cache identity mismatch")
    completed = reused = failed = 0
    for raw in configurations:
        configuration = {str(key): value for key, value in raw.items()}
        phase = str(configuration["phase"])
        destination = result_root.resolve() / _phase_directory(phase) / str(configuration["configuration_id"])
        if destination.is_dir():
            try:
                validate_configuration_result(destination, protocol_root=protocol_root)
                print(f"[REUSE RESULT] {component_name} {configuration['configuration_id']}")
                reused += 1
                continue
            except Exception:
                quarantine = destination.with_name(f"{destination.name}.invalid-{int(time.time())}")
                os.replace(destination, quarantine)
                print(f"[PRESERVE PARTIAL] {quarantine}")
        try:
            print(f"[CALIBRATE] {component_name} {configuration['configuration_id']}")
            result = evaluate_configuration(
                protocol_root,
                configuration,
                identity,
                observations,
                destination,
            )
            print(f"[EVALUATE] {component_name} {configuration['configuration_id']}")
            print(f"[VALIDATE] {component_name} {configuration['configuration_id']}")
            validate_configuration_result(destination, protocol_root=protocol_root)
            print(f"[PASS] {component_name} {configuration['configuration_id']}")
            if result["status"] == "complete":
                completed += 1
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {component_name} {configuration['configuration_id']}: {exc}")
    summary = {
        "schema_version": "speaker-enrollment-phase-run.v1",
        "backend_id": component_name,
        "backend_identity_hash": identity.identity_hash,
        "requested_configurations": len(configurations),
        "completed_this_call": completed,
        "reused": reused,
        "failed": failed,
    }
    if failed:
        raise SpeakerEnrollmentError(
            f"{failed} of {len(configurations)} configurations failed; valid completed results were preserved"
        )
    return summary


def evaluate_configuration(
    protocol_root: Path,
    configuration: Mapping[str, object],
    identity: BackendIdentity,
    observations: Mapping[str, Mapping[str, object]],
    output_root: Path,
) -> dict[str, object]:
    tables = load_protocol_tables(protocol_root)
    protocol_summary = _read_json(protocol_root / "protocol_summary.json")
    config = load_config(protocol_root / "selection_config.yaml")
    configuration_hash = canonical_sha256(_configuration_identity(configuration))
    family = str(configuration["selection_family_id"])
    method = str(configuration["aggregation_method"])
    enrollment_rows = [row for row in tables["enrollment_sets"] if row["selection_family_id"] == family]
    known_speakers = {
        row["speaker_key"] for row in tables["cohort"] if row["study_role"] == "known"
    }
    if {row["speaker_key"] for row in enrollment_rows} != known_speakers:
        raise SpeakerEnrollmentError("configuration enrollment cohort is not the frozen paired cohort")
    templates: dict[str, dict[str, object]] = {}
    enrollment_failures: dict[str, str] = {}
    aggregation_started = time.perf_counter()
    for row in enrollment_rows:
        ids = json.loads(row["slice_ids_json"])
        values = [observations[value] for value in ids]
        invalid = [value for value in values if value["status"] != "ok"]
        if invalid:
            enrollment_failures[row["speaker_key"]] = "TECHNICALLY_INVALID" if any(value["status"] == "too_short" for value in invalid) else "EXTRACTION_FAILED"
            continue
        vectors = [value["vector"] for value in values]
        durations = [float(value["duration_sec"]) for value in values]
        if method == "normalized_mean":
            representation = normalized_mean(vectors)
        elif method == "duration_weighted_mean":
            representation = duration_weighted_mean(vectors, durations)
        elif method == "multi_template_mean_score":
            representation = None
        else:
            raise SpeakerEnrollmentError(f"unsupported aggregation method: {method}")
        templates[row["speaker_key"]] = {
            "vectors": vectors,
            "durations_sec": durations,
            "representation": representation,
            "actual_audio_sec": float(row["actual_audio_sec"]),
            "actual_utterance_count": int(row["actual_utterance_count"]),
        }
    aggregation_runtime_sec = time.perf_counter() - aggregation_started
    probe_label = str(configuration["probe_duration_label"])
    probe_variants = [row for row in tables["probe_variants"] if row["duration_label"] == probe_label]
    if not probe_variants:
        raise SpeakerEnrollmentError(f"no probe variants exist for {probe_label}")
    trials: list[dict[str, object]] = []
    probe_status: dict[str, str] = {}
    scoring_started = time.perf_counter()
    for probe in probe_variants:
        slice_id = probe["slice_id"]
        observation = observations[slice_id]
        if observation["status"] != "ok":
            probe_status[slice_id] = "TECHNICALLY_INVALID" if observation["status"] == "too_short" else "EXTRACTION_FAILED"
            continue
        probe_status[slice_id] = "ok"
        for candidate, template in sorted(templates.items()):
            score = score_templates(
                observation["vector"],
                template["vectors"],
                method,
                template["durations_sec"],
            )
            trials.append(
                {
                    "probe_id": slice_id,
                    "parent_probe_id": probe["parent_item_id"],
                    "protocol_split": probe["protocol_split"],
                    "probe_partition": probe["speaker_role"],
                    "true_speaker_key": probe["speaker_key"],
                    "candidate_speaker_key": candidate,
                    "score": score,
                    "is_target": probe["speaker_role"] == "known" and probe["speaker_key"] == candidate,
                }
            )
    scoring_runtime_sec = time.perf_counter() - scoring_started
    calibration_trials = [row for row in trials if row["protocol_split"] == "calibration"]
    evaluation_trials = [row for row in trials if row["protocol_split"] == "evaluation"]
    calibration_sweep = threshold_sweep(calibration_trials, split="calibration")
    calibration_eer = equal_error_rate(calibration_sweep)
    if calibration_eer is None:
        raise SpeakerEnrollmentError("calibration has no valid target/non-target score distribution")
    threshold = float(calibration_eer["threshold"])
    evaluation_sweep = threshold_sweep(evaluation_trials, split="evaluation")
    evaluation_eer = equal_error_rate(evaluation_sweep)
    evaluation_operating = operating_point(evaluation_trials, threshold)
    decisions = _probe_decisions(
        probe_variants,
        trials,
        observations,
        templates,
        threshold,
        identity,
    )
    known_decisions = [row for row in decisions if row["true_partition"] == "known"]
    unknown_decisions = [row for row in decisions if row["true_partition"] == "unknown"]
    same_scores = [float(row["score"]) for row in evaluation_trials if row["is_target"]]
    different_known = [
        float(row["score"])
        for row in evaluation_trials
        if row["probe_partition"] == "known" and not row["is_target"]
    ]
    unknown_impostor = [
        float(row["score"]) for row in evaluation_trials if row["probe_partition"] == "unknown"
    ]
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "complete",
        "protocol_id": protocol_summary["protocol_id"],
        "source_protocol_id": protocol_summary["source_protocol_id"],
        "configuration": dict(configuration),
        "configuration_identity_hash": configuration_hash,
        "backend_id": identity.backend_id,
        "backend_identity_hash": identity.identity_hash,
        "backend_embedding_dimension": identity.embedding_dimension,
        "threshold_artifact_id": threshold_artifact_id(identity.identity_hash, configuration_hash),
        "threshold_policy": "calibration_eer_per_configuration",
        "threshold_source": "calibration_only",
        "evaluation_used_for_threshold": False,
        "operating_threshold": threshold,
        "calibration_eer": calibration_eer,
        "evaluation_eer_oracle_diagnostic": evaluation_eer,
        "evaluation_at_calibrated_threshold": evaluation_operating,
        "tar_at_fixed_far": {
            str(value): tar_at_fixed_far(evaluation_sweep, float(value))
            for value in config["calibration"]["fixed_far_targets"]
        },
        "metrics": _decision_metrics(known_decisions, unknown_decisions, evaluation_trials, threshold, config),
        "score_distributions": {
            "same_speaker": _distribution(same_scores),
            "different_known_speaker": _distribution(different_known),
            "known_vs_unknown_impostor": _distribution(unknown_impostor),
        },
        "extraction": {
            "required_slices": len(
                {
                    value
                    for row in enrollment_rows
                    for value in json.loads(row["slice_ids_json"])
                }
                | {row["slice_id"] for row in probe_variants}
            ),
            "invalid_enrollment_speakers": len(enrollment_failures),
            "technically_invalid_probes": sum(value == "TECHNICALLY_INVALID" for value in probe_status.values()),
            "failed_probes": sum(value == "EXTRACTION_FAILED" for value in probe_status.values()),
            "nan_or_inf_scores": sum(not math.isfinite(float(row["score"])) for row in trials),
        },
        "representation_cost": _representation_cost(
            templates,
            method,
            identity.embedding_dimension,
            len(decisions),
            aggregation_runtime_sec,
            scoring_runtime_sec,
        ),
        "statistics": {
            "bootstrap_cluster": "speaker",
            "bootstrap_seed": int(config["metrics"]["bootstrap_seed"]),
            "bootstrap_repetitions": int(config["metrics"]["bootstrap_repetitions"]),
            "confidence_level": float(config["metrics"]["confidence_level"]),
            "confidence_intervals_generated_by": "Analyze",
        },
        "speech_style": "prompted_read",
        "session_diversity": "unavailable",
        "product_decision_automatic": False,
    }
    output_root.mkdir(parents=True, exist_ok=False)
    _write_json(output_root / "configuration_result.json", result)
    _write_json(
        output_root / "calibration.json",
        {
            "schema_version": "speaker-enrollment-calibration.v1",
            "threshold_artifact_id": result["threshold_artifact_id"],
            "backend_identity_hash": identity.identity_hash,
            "configuration_identity_hash": configuration_hash,
            "threshold": threshold,
            "calibration_eer": calibration_eer,
            "evaluation_used": False,
        },
    )
    _write_csv(output_root / "probe_decisions.csv", decisions)
    _write_csv(output_root / "speaker_results.csv", _speaker_results(decisions, enrollment_rows, enrollment_failures))
    _write_trials(output_root / "score_trials.npz", trials)
    _write_checksums(output_root)
    return result


def validate_configuration_result(
    result_root: Path,
    *,
    protocol_root: Path,
) -> dict[str, object]:
    root = result_root.resolve()
    _validate_checksums(root)
    result = _read_json(root / "configuration_result.json")
    calibration = _read_json(root / "calibration.json")
    protocol = _read_json(protocol_root / "protocol_summary.json")
    if result.get("schema_version") != RESULT_SCHEMA_VERSION or result.get("status") != "complete":
        raise SpeakerEnrollmentError("configuration result is incomplete or incompatible")
    if result.get("protocol_id") != protocol.get("protocol_id"):
        raise SpeakerEnrollmentError("configuration result belongs to another protocol")
    expected_hash = canonical_sha256(_configuration_identity(result["configuration"]))
    if result.get("configuration_identity_hash") != expected_hash:
        raise SpeakerEnrollmentError("configuration identity hash mismatch")
    if calibration.get("configuration_identity_hash") != expected_hash:
        raise SpeakerEnrollmentError("threshold is not bound to this configuration")
    if calibration.get("backend_identity_hash") != result.get("backend_identity_hash"):
        raise SpeakerEnrollmentError("threshold is not bound to this backend")
    if calibration.get("evaluation_used") is not False or result.get("evaluation_used_for_threshold") is not False:
        raise SpeakerEnrollmentError("evaluation data influenced calibration")
    if float(calibration["threshold"]) != float(result["operating_threshold"]):
        raise SpeakerEnrollmentError("calibration threshold mismatch")
    return {
        "schema_version": "speaker-enrollment-result-validation.v1",
        "configuration_id": result["configuration"]["configuration_id"],
        "backend_id": result["backend_id"],
        "threshold_backend_specific": True,
        "threshold_configuration_specific": True,
        "evaluation_held_out": True,
        "valid": True,
    }


def _probe_decisions(
    probe_variants: Sequence[Mapping[str, str]],
    trials: Sequence[Mapping[str, object]],
    observations: Mapping[str, Mapping[str, object]],
    templates: Mapping[str, Mapping[str, object]],
    threshold: float,
    identity: BackendIdentity,
) -> list[dict[str, object]]:
    by_probe: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in trials:
        by_probe[str(row["probe_id"])].append(row)
    result = []
    for probe in probe_variants:
        if probe["protocol_split"] != "evaluation":
            continue
        slice_id = probe["slice_id"]
        observation = observations[slice_id]
        ranked = sorted(by_probe.get(slice_id, []), key=lambda row: (-float(row["score"]), str(row["candidate_speaker_key"])))
        status = "ok"
        if observation["status"] == "too_short":
            status = "TECHNICALLY_INVALID"
        elif observation["status"] != "ok" or not ranked:
            status = "EXTRACTION_FAILED"
        predicted = "Unknown"
        best_score = None
        if status == "ok":
            best_score = float(ranked[0]["score"])
            if best_score >= threshold:
                predicted = str(ranked[0]["candidate_speaker_key"])
        true_partition = probe["speaker_role"]
        true_speaker = probe["speaker_key"]
        top_ids = [str(row["candidate_speaker_key"]) for row in ranked[:5]]
        correct = status == "ok" and (
            (true_partition == "known" and predicted == true_speaker)
            or (true_partition == "unknown" and predicted == "Unknown")
        )
        result.append(
            {
                "probe_id": slice_id,
                "parent_probe_id": probe["parent_item_id"],
                "true_speaker_key": true_speaker,
                "true_partition": true_partition,
                "predicted_speaker": predicted,
                "best_score": "" if best_score is None else best_score,
                "threshold": threshold,
                "accepted_known": predicted != "Unknown",
                "correct": correct,
                "top1_correct": bool(top_ids and top_ids[0] == true_speaker) if true_partition == "known" and status == "ok" else False,
                "top3_correct": true_speaker in top_ids[:3] if true_partition == "known" and status == "ok" else False,
                "top5_correct": true_speaker in top_ids[:5] if true_partition == "known" and status == "ok" else False,
                "false_unknown": true_partition == "known" and predicted == "Unknown",
                "false_known_attribution": true_partition == "unknown" and predicted != "Unknown",
                "status": status,
                "backend_id": identity.backend_id,
            }
        )
    return result


def _decision_metrics(
    known: Sequence[Mapping[str, object]],
    unknown: Sequence[Mapping[str, object]],
    evaluation_trials: Sequence[Mapping[str, object]],
    threshold: float,
    config: Mapping[str, object],
) -> dict[str, object]:
    valid_known = [row for row in known if row["status"] == "ok"]
    valid_unknown = [row for row in unknown if row["status"] == "ok"]
    verification_correct = sum((float(row["score"]) >= threshold) == bool(row["is_target"]) for row in evaluation_trials)
    metrics = {
        "verification_accuracy": _ratio(verification_correct, len(evaluation_trials)),
        "top1_identification": _ratio(sum(bool(row["top1_correct"]) for row in known), len(known)),
        "top3_identification": _ratio(sum(bool(row["top3_correct"]) for row in known), len(known)),
        "top5_identification": _ratio(sum(bool(row["top5_correct"]) for row in known), len(known)),
        "known_open_set_correct": _ratio(sum(bool(row["correct"]) for row in known), len(known)),
        "unknown_rejection": _ratio(sum(bool(row["correct"]) for row in unknown), len(unknown)),
        "false_known_attribution": _ratio(sum(bool(row["false_known_attribution"]) for row in unknown), len(unknown)),
        "known_false_unknown": _ratio(sum(bool(row["false_unknown"]) for row in known), len(known)),
        "valid_probe_rate": _ratio(len(valid_known) + len(valid_unknown), len(known) + len(unknown)),
        "failed_unknown_probes_credited_as_rejections": False,
    }
    operating = operating_point(evaluation_trials, threshold)
    if operating:
        metrics["far"] = operating["far"]
        metrics["frr"] = operating["frr"]
        metrics["tar"] = operating["tar"]
    return metrics


def _speaker_results(
    decisions: Sequence[Mapping[str, object]],
    enrollment_rows: Sequence[Mapping[str, str]],
    failures: Mapping[str, str],
) -> list[dict[str, object]]:
    enrollment = {row["speaker_key"]: row for row in enrollment_rows}
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in decisions:
        grouped[(str(row["true_partition"]), str(row["true_speaker_key"]))].append(row)
    result = []
    for (partition, speaker), rows in sorted(grouped.items()):
        enrolled = enrollment.get(speaker)
        result.append(
            {
                "speaker_key": speaker,
                "partition": partition,
                "probe_count": len(rows),
                "valid_probe_count": sum(row["status"] == "ok" for row in rows),
                "correct_count": sum(bool(row["correct"]) for row in rows),
                "top1_correct_count": sum(bool(row["top1_correct"]) for row in rows),
                "false_known_count": sum(bool(row["false_known_attribution"]) for row in rows),
                "false_unknown_count": sum(bool(row["false_unknown"]) for row in rows),
                "enrollment_status": failures.get(speaker, "ok") if enrolled else "not_applicable",
                "enrollment_audio_sec": enrolled["actual_audio_sec"] if enrolled else "",
                "enrollment_utterances": enrolled["actual_utterance_count"] if enrolled else "",
                "distinct_enrollment_texts": enrolled["distinct_enrollment_texts"] if enrolled else "",
            }
        )
    return result


def _representation_cost(
    templates: Mapping[str, Mapping[str, object]],
    method: str,
    dimension: int,
    probes: int,
    aggregation_runtime_sec: float,
    scoring_runtime_sec: float,
) -> dict[str, object]:
    counts = [len(value["vectors"]) for value in templates.values()]
    mean_templates = sum(counts) / len(counts) if counts else 0.0
    stored_templates = mean_templates if method == "multi_template_mean_score" else 1.0
    comparisons = len(templates) * probes * mean_templates if method == "multi_template_mean_score" else len(templates) * probes
    return {
        "mean_source_templates_per_speaker": mean_templates,
        "stored_templates_per_speaker": stored_templates,
        "estimated_bytes_per_speaker_float32": stored_templates * dimension * 4,
        "estimated_cosine_comparisons": comparisons,
        "enrollment_aggregation_runtime_sec": aggregation_runtime_sec,
        "probe_scoring_runtime_sec": scoring_runtime_sec,
        "aggregation_runtime_measured_separately": True,
    }


def _distribution(values: Sequence[float]) -> dict[str, object]:
    if not values:
        return {"count": 0, "mean": None, "minimum": None, "maximum": None, "standard_deviation": None}
    mean = sum(values) / len(values)
    return {
        "count": len(values),
        "mean": mean,
        "minimum": min(values),
        "maximum": max(values),
        "standard_deviation": math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)),
    }


def _ratio(numerator: int, denominator: int) -> dict[str, object]:
    return {"numerator": int(numerator), "denominator": int(denominator), "value": float(numerator) / denominator if denominator else None}


def _write_trials(path: Path, trials: Sequence[Mapping[str, object]]) -> None:
    speakers = sorted({str(row["true_speaker_key"]) for row in trials})
    speaker_index = {value: index for index, value in enumerate(speakers)}
    _write_npz(
        path,
        {
            "schema_version": np.asarray(["speaker-enrollment-score-trials.v1"]),
            "score": np.asarray([float(row["score"]) for row in trials], dtype=np.float32),
            "is_target": np.asarray([bool(row["is_target"]) for row in trials], dtype=np.bool_),
            "split": np.asarray([str(row["protocol_split"]) for row in trials]),
            "probe_partition": np.asarray([str(row["probe_partition"]) for row in trials]),
            "speaker_index": np.asarray([speaker_index[str(row["true_speaker_key"])] for row in trials], dtype=np.int32),
            "speakers": np.asarray(speakers),
        },
    )


def _configuration_identity(configuration: Mapping[str, object]) -> dict[str, object]:
    return {
        str(key): value
        for key, value in configuration.items()
        if str(key) not in {"configuration_id"}
    }


def _phase_directory(phase: str) -> str:
    return {
        "EnrollmentCount": "phase_a_enrollment_count",
        "EnrollmentDuration": "phase_b_enrollment_duration",
        "Aggregation": "phase_c_aggregation",
        "ProbeDuration": "phase_d_probe_duration",
        "JointFrontier": "phase_e_joint_frontier",
    }[phase]


def _write_checksums(root: Path) -> None:
    rows = []
    for path in sorted(value for value in root.rglob("*") if value.is_file() and value.name != "checksums.json"):
        rows.append({"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
    _write_json(root / "checksums.json", {"schema_version": "speaker-enrollment-result-checksums.v1", "files": rows})


def _validate_checksums(root: Path) -> None:
    payload = _read_json(root / "checksums.json")
    for row in payload.get("files", []):
        path = root / str(row["path"])
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or _sha256(path).upper() != str(row["sha256"]).upper():
            raise SpeakerEnrollmentError(f"configuration artifact checksum failed: {row['path']}")


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_npz(path: Path, arrays: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez_compressed(handle, **{key: np.asarray(value) for key, value in arrays.items()})


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SpeakerEnrollmentError(f"JSON object required: {path}")
    return {str(key): item for key, item in value.items()}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
