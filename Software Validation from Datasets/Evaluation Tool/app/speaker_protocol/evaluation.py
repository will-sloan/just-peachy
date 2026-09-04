"""Backend-specific enrollment, calibration, and speaker protocol evaluation."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Callable, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from app.benchmark_contracts.canonical import canonical_sha256
from app.speaker_protocol.contracts import (
    ENROLLMENT_SCHEMA_VERSION,
    METRICS_SCHEMA_VERSION,
    UNKNOWN_LABEL,
    BackendIdentity,
    EmbeddingObservation,
    SpeakerProtocolError,
    load_policy,
    normalize_vector,
    validate_enrollment_compatibility,
)
from app.speaker_protocol.manifests import (
    MANIFEST_FILENAMES,
    read_protocol_rows,
    validate_protocol_manifest_set,
)
from app.speaker_protocol.metrics import (
    cosine_similarity,
    equal_error_rate,
    operating_point,
    proportion_metric,
    score_distribution,
    tar_at_fixed_far,
    threshold_sweep,
)
from app.speaker_protocol.progress import EvaluationProgress


EMBEDDING_INDEX_SCHEMA = pa.schema(
    [
        pa.field("item_id", pa.string(), nullable=False),
        pa.field("embedding_id", pa.string(), nullable=True),
        pa.field("path", pa.string(), nullable=True),
        pa.field("backend_id", pa.string(), nullable=False),
        pa.field("model_id", pa.string(), nullable=False),
        pa.field("model_hash", pa.string(), nullable=False),
        pa.field("config_hash", pa.string(), nullable=False),
        pa.field("dimension", pa.int64(), nullable=True),
        pa.field("status", pa.string(), nullable=False),
        pa.field("l2_norm", pa.float64(), nullable=True),
        pa.field("duration_sec", pa.float64(), nullable=True),
        pa.field("extraction_sec", pa.float64(), nullable=True),
    ]
)
ENROLLMENT_INDEX_SCHEMA = pa.schema(
    [
        pa.field("speaker_key", pa.string(), nullable=False),
        pa.field("centroid_path", pa.string(), nullable=True),
        pa.field("requested_exemplars", pa.int64(), nullable=False),
        pa.field("successful_exemplars", pa.int64(), nullable=False),
        pa.field("dimension", pa.int64(), nullable=False),
        pa.field("backend_id", pa.string(), nullable=False),
        pa.field("model_id", pa.string(), nullable=False),
        pa.field("model_hash", pa.string(), nullable=False),
        pa.field("config_hash", pa.string(), nullable=False),
        pa.field("normalization", pa.string(), nullable=False),
        pa.field("aggregation_method", pa.string(), nullable=False),
        pa.field("preprocessing_json", pa.string(), nullable=False),
        pa.field("enrollment_item_ids_json", pa.string(), nullable=False),
        pa.field("threshold_policy_version", pa.string(), nullable=False),
    ]
)
SIMILARITY_SCHEMA = pa.schema(
    [
        pa.field("probe_id", pa.string(), nullable=False),
        pa.field("candidate_speaker_key", pa.string(), nullable=False),
        pa.field("score", pa.float64(), nullable=False),
        pa.field("is_target", pa.bool_(), nullable=False),
        pa.field("protocol_split", pa.string(), nullable=False),
        pa.field("probe_role", pa.string(), nullable=False),
        pa.field("condition", pa.string(), nullable=False),
        pa.field("score_status", pa.string(), nullable=False),
    ]
)
THRESHOLD_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.string(), nullable=False),
        pa.field("split", pa.string(), nullable=False),
        pa.field("threshold", pa.float64(), nullable=False),
        pa.field("true_accepts", pa.int64(), nullable=False),
        pa.field("false_accepts", pa.int64(), nullable=False),
        pa.field("true_rejects", pa.int64(), nullable=False),
        pa.field("false_rejects", pa.int64(), nullable=False),
        pa.field("positive_trials", pa.int64(), nullable=False),
        pa.field("negative_trials", pa.int64(), nullable=False),
        pa.field("far", pa.float64(), nullable=False),
        pa.field("frr", pa.float64(), nullable=False),
        pa.field("tar", pa.float64(), nullable=False),
        pa.field("tpr", pa.float64(), nullable=False),
        pa.field("fpr", pa.float64(), nullable=False),
        pa.field("fnr", pa.float64(), nullable=False),
    ]
)
VERIFICATION_SCHEMA = pa.schema(
    [
        pa.field("probe_id", pa.string(), nullable=False),
        pa.field("candidate_speaker_key", pa.string(), nullable=False),
        pa.field("is_target", pa.bool_(), nullable=False),
        pa.field("score", pa.float64(), nullable=False),
        pa.field("threshold", pa.float64(), nullable=False),
        pa.field("accepted", pa.bool_(), nullable=False),
        pa.field("correct", pa.bool_(), nullable=False),
        pa.field("condition", pa.string(), nullable=False),
    ]
)
RANKING_SCHEMA = pa.schema(
    [
        pa.field("probe_id", pa.string(), nullable=False),
        pa.field("candidate_speaker_key", pa.string(), nullable=False),
        pa.field("score", pa.float64(), nullable=False),
        pa.field("rank", pa.int64(), nullable=False),
        pa.field("is_target", pa.bool_(), nullable=False),
        pa.field("condition", pa.string(), nullable=False),
    ]
)
UNKNOWN_DECISION_SCHEMA = pa.schema(
    [
        pa.field("probe_id", pa.string(), nullable=False),
        pa.field("true_partition", pa.string(), nullable=False),
        pa.field("true_speaker_key", pa.string(), nullable=False),
        pa.field("predicted_speaker_key", pa.string(), nullable=False),
        pa.field("best_score", pa.float64(), nullable=True),
        pa.field("threshold", pa.float64(), nullable=True),
        pa.field("accepted_known", pa.bool_(), nullable=False),
        pa.field("correct", pa.bool_(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("condition", pa.string(), nullable=False),
    ]
)
FAILURE_SCHEMA = pa.schema(
    [
        pa.field("item_id", pa.string(), nullable=False),
        pa.field("phase", pa.string(), nullable=False),
        pa.field("error_type", pa.string(), nullable=False),
        pa.field("message", pa.string(), nullable=False),
        pa.field("backend_id", pa.string(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("counts_in_denominator", pa.bool_(), nullable=False),
    ]
)
GROUP_METRIC_SCHEMA = pa.schema(
    [
        pa.field("group_type", pa.string(), nullable=False),
        pa.field("group_value", pa.string(), nullable=False),
        pa.field("metric_name", pa.string(), nullable=False),
        pa.field("metric_value", pa.float64(), nullable=True),
        pa.field("numerator", pa.int64(), nullable=False),
        pa.field("denominator", pa.int64(), nullable=False),
        pa.field("ci_lower", pa.float64(), nullable=True),
        pa.field("ci_upper", pa.float64(), nullable=True),
    ]
)


def load_protocol_core_rows(manifest_root: Path) -> dict[str, list[dict[str, object]]]:
    validate_protocol_manifest_set(manifest_root)
    return {
        kind: read_protocol_rows(manifest_root / MANIFEST_FILENAMES[kind], expected_kind=kind)
        for kind in ("enrollment", "calibration", "known_evaluation", "unknown_evaluation")
    }


def evaluate_protocol(
    manifest_root: Path,
    observations: Sequence[EmbeddingObservation],
    identity: BackendIdentity,
    output_root: Path,
    *,
    allow_overwrite: bool = False,
    workers: int = 1,
    progress: EvaluationProgress | None = None,
    execution_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return evaluate_protocol_rows(
        load_protocol_core_rows(manifest_root),
        observations,
        identity,
        output_root,
        scope="full",
        allow_overwrite=allow_overwrite,
        workers=workers,
        progress=progress,
        execution_provenance=execution_provenance,
    )


def evaluate_protocol_rows(
    rows_by_kind: Mapping[str, Sequence[Mapping[str, object]]],
    observations: Sequence[EmbeddingObservation],
    identity: BackendIdentity,
    output_root: Path,
    *,
    scope: str,
    allow_overwrite: bool = False,
    workers: int = 1,
    progress: EvaluationProgress | None = None,
    execution_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Evaluate one embedding backend without ever deriving a prediction from references."""

    if workers < 1:
        raise SpeakerProtocolError("evaluation workers must be at least one")
    policy = load_policy()
    destination = output_root.resolve()
    if (
        destination.exists()
        and any(path.name != "evaluation_progress.json" for path in destination.iterdir())
        and not allow_overwrite
    ):
        raise SpeakerProtocolError(f"speaker protocol output already exists: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    required_kinds = {"enrollment", "calibration", "known_evaluation", "unknown_evaluation"}
    if set(rows_by_kind) != required_kinds:
        raise SpeakerProtocolError(f"speaker protocol rows must contain {sorted(required_kinds)}")
    core = {kind: [dict(row) for row in rows_by_kind[kind]] for kind in sorted(required_kinds)}
    all_rows = [row for rows in core.values() for row in rows]
    if not all_rows:
        raise SpeakerProtocolError("speaker protocol has no rows")
    protocol_ids = {str(row["protocol_id"]) for row in all_rows}
    if len(protocol_ids) != 1:
        raise SpeakerProtocolError("speaker protocol rows use different protocol IDs")
    expected_ids = {str(row["item_id"]) for row in all_rows}
    if len(expected_ids) != len(all_rows):
        raise SpeakerProtocolError("speaker protocol core rows contain duplicate item IDs")

    observed: dict[str, EmbeddingObservation] = {}
    for observation in observations:
        if observation.item_id in observed:
            raise SpeakerProtocolError(f"duplicate embedding observation {observation.item_id}")
        if observation.item_id not in expected_ids:
            raise SpeakerProtocolError(f"unexpected embedding observation {observation.item_id}")
        _validate_observation_identity(observation, identity)
        observed[observation.item_id] = observation

    failures: list[dict[str, object]] = []
    if progress:
        progress.update("BUILDING_ENROLLMENT", details={"score_matrix_status": "pending"})
    embedding_index = _publish_embedding_observations(
        destination, all_rows, observed, identity, failures
    )
    enrollment_rows, centroids, enrollment_metadata = _build_enrollment(
        destination,
        core["enrollment"],
        observed,
        identity,
        failures,
    )
    validate_enrollment_compatibility(enrollment_metadata["backend_identity"], identity)

    probe_rows = core["calibration"] + core["known_evaluation"] + core["unknown_evaluation"]
    if progress:
        progress.update("BUILDING_SCORE_MATRIX", details={"score_matrix_status": "building"})
    similarity = _score_probes(probe_rows, observed, centroids, identity, failures)
    if progress:
        progress.update("CALIBRATION", details={"score_matrix_status": "complete", "calibration_status": "running"})
    calibration_trials = [row for row in similarity if row["protocol_split"] == "calibration"]
    evaluation_trials = [row for row in similarity if row["protocol_split"] == "evaluation"]
    calibration_sweep = threshold_sweep(calibration_trials, split="calibration")
    calibration_eer = equal_error_rate(calibration_sweep)
    if calibration_eer is None:
        raise SpeakerProtocolError("calibration requires both target and non-target score trials")
    threshold = float(calibration_eer["threshold"])
    if progress:
        progress.update("EVALUATION", details={"calibration_status": "complete"})
    evaluation_sweep = threshold_sweep(evaluation_trials, split="evaluation")
    verification = _verification_decisions(evaluation_trials, threshold)
    rankings = _identification_rankings(evaluation_trials)
    decisions = _open_set_decisions(
        core["known_evaluation"] + core["unknown_evaluation"],
        rankings,
        observed,
        threshold,
    )

    evaluation_eer = equal_error_rate(evaluation_sweep)
    bootstrap_repetitions = int(policy["metrics"]["bootstrap_repetitions"])
    bootstrap_seed = int(policy["metrics"]["bootstrap_seed"])
    evaluation_same = [row for row in evaluation_trials if row["is_target"]]
    evaluation_different = [row for row in evaluation_trials if not row["is_target"]]
    drift_values = _paired_drift(core, observed)
    bootstrap_jobs = 1 + int(evaluation_eer is not None)
    bootstrap_jobs += int(len(evaluation_same) > 1) + int(len(evaluation_different) > 1)
    bootstrap_jobs += int(len(drift_values) > 1)
    bootstrap_total = bootstrap_repetitions * bootstrap_jobs
    bootstrap_completed = 0

    def bootstrap_tick(completed: int) -> None:
        nonlocal bootstrap_completed
        bootstrap_completed += completed
        if progress:
            progress.update("BOOTSTRAP", completed=bootstrap_completed, total=bootstrap_total)

    if progress:
        progress.update("BOOTSTRAP", completed=0, total=bootstrap_total, force=True)
    if evaluation_eer is not None:
        evaluation_eer["confidence_interval"] = _eer_bootstrap(
            evaluation_trials,
            seed=bootstrap_seed,
            repetitions=bootstrap_repetitions,
            workers=workers,
            progress_callback=bootstrap_tick,
        )
    calibration_eer["confidence_interval"] = _eer_bootstrap(
        calibration_trials,
        seed=bootstrap_seed,
        repetitions=bootstrap_repetitions,
        workers=workers,
        progress_callback=bootstrap_tick,
    )
    calibration_results = {
        "schema_version": "speaker-calibration-results.v1",
        "protocol_id": next(iter(protocol_ids)),
        "backend_identity_hash": identity.identity_hash,
        "threshold_policy_version": identity.threshold_policy_version,
        "threshold_source": "calibration_only",
        "evaluation_probes_used_to_select_threshold": False,
        "calibration_eer": calibration_eer,
        "operating_threshold": threshold,
        "acceptance_rule": "score >= threshold",
        "unknown_label": UNKNOWN_LABEL,
    }
    metrics, grouped_metrics = _metrics(
        core,
        observed,
        enrollment_rows,
        similarity,
        evaluation_sweep,
        evaluation_eer,
        threshold,
        rankings,
        decisions,
        failures,
        policy,
        workers=workers,
        progress_callback=bootstrap_tick,
        drift_values=drift_values,
    )
    metrics["calibration_vs_evaluation"] = {
        "calibration_eer": calibration_eer,
        "evaluation_oracle_eer_diagnostic": evaluation_eer,
        "operating_threshold_selected_from": "calibration",
        "evaluation_threshold_recalibrated": False,
    }

    run_identity = {
        "protocol_id": next(iter(protocol_ids)),
        "backend_identity_hash": identity.identity_hash,
        "scope": scope,
        "expected_item_ids_sha256": canonical_sha256(sorted(expected_ids)),
    }
    protocol_run = {
        "schema_version": "speaker-protocol-run.v1",
        "run_id": f"speaker_run_{canonical_sha256(run_identity)[:12].lower()}",
        **run_identity,
        "backend_identity": identity.to_jsonable(),
        "unknown_label": UNKNOWN_LABEL,
        "private_identity_mapping_included": False,
        "reference_identity_prediction_fallback": False,
        "expected_items": len(all_rows),
        "observed_items": len(observed),
        "successful_embeddings": sum(1 for row in embedding_index if row["status"] == "ok"),
        "evaluation_execution": {
            "workers": workers,
            "math_threads_per_worker": 1,
            "logical_processor_count": os.cpu_count(),
            **dict(execution_provenance or {}),
        },
    }

    if progress:
        progress.update("WRITING_RESULTS", force=True)
    _write_json(destination / "protocol_run.json", protocol_run)
    _write_json(destination / "backend_identity.json", identity.to_jsonable())
    _write_json(destination / "enrollment" / "metadata.json", enrollment_metadata)
    _write_parquet(destination / "embeddings" / "index.parquet", embedding_index, EMBEDDING_INDEX_SCHEMA, "speaker-embedding-index.v2")
    _write_parquet(destination / "enrollment" / "index.parquet", enrollment_rows, ENROLLMENT_INDEX_SCHEMA, "backend-enrollment-index.v1")
    _write_parquet(destination / "similarity_scores.parquet", similarity, SIMILARITY_SCHEMA, "speaker-similarity.v2")
    _write_parquet(destination / "threshold_sweep.parquet", calibration_sweep + evaluation_sweep, THRESHOLD_SCHEMA, "speaker-threshold-sweep.v1")
    _write_json(destination / "calibration_results.json", calibration_results)
    _write_parquet(destination / "verification_decisions.parquet", verification, VERIFICATION_SCHEMA, "speaker-verification-decisions.v1")
    _write_parquet(destination / "identification_rankings.parquet", rankings, RANKING_SCHEMA, "speaker-identification-rankings.v1")
    _write_parquet(destination / "unknown_rejection_decisions.parquet", decisions, UNKNOWN_DECISION_SCHEMA, "speaker-unknown-rejection.v1")
    _write_parquet(destination / "failures.parquet", failures, FAILURE_SCHEMA, "speaker-protocol-failures.v1")
    _write_json(destination / "metrics" / "summary.json", metrics)
    _write_parquet(destination / "metrics" / "grouped_metrics.parquet", grouped_metrics, GROUP_METRIC_SCHEMA, "speaker-grouped-metrics.v1")
    _write_checksums(destination)
    if progress:
        progress.update("VALIDATING", force=True)
    validate_protocol_results(destination, runtime_identity=identity)
    if progress:
        progress.update("COMPLETE", status="COMPLETE", force=True)
    return metrics


def observations_from_npz(path: Path, identity: BackendIdentity) -> list[EmbeddingObservation]:
    with np.load(path, allow_pickle=False) as archive:
        required = {"item_ids", "vectors", "statuses", "durations_sec", "extraction_sec"}
        if not required.issubset(archive.files):
            raise SpeakerProtocolError(f"observation NPZ is missing {sorted(required - set(archive.files))}")
        item_ids = archive["item_ids"]
        vectors = archive["vectors"]
        statuses = archive["statuses"]
        durations = archive["durations_sec"]
        timings = archive["extraction_sec"]
    if vectors.ndim != 2 or len(item_ids) != vectors.shape[0]:
        raise SpeakerProtocolError("observation NPZ row counts do not reconcile")
    result = []
    for index, item_id in enumerate(item_ids):
        status = str(statuses[index])
        vector = tuple(float(value) for value in vectors[index]) if status == "ok" else ()
        result.append(
            EmbeddingObservation(
                item_id=str(item_id),
                backend_id=identity.backend_id,
                model_hash=identity.model_hash,
                config_hash=identity.config_hash,
                vector=vector,
                status=status,
                duration_sec=_finite_or_none(durations[index]),
                extraction_sec=_finite_or_none(timings[index]),
            )
        )
    return result


def validate_protocol_results(
    root: Path,
    *,
    runtime_identity: BackendIdentity | None = None,
) -> dict[str, object]:
    run = _read_json(root / "protocol_run.json")
    enrolled = _read_json(root / "enrollment" / "metadata.json")
    identity = BackendIdentity.from_mapping(_mapping(run.get("backend_identity"), "backend_identity"))
    validate_enrollment_compatibility(enrolled["backend_identity"], identity)
    if runtime_identity is not None:
        validate_enrollment_compatibility(identity, runtime_identity)
    checksums = _read_json(root / "checksums.json")
    entries = _mapping(checksums.get("entries"), "checksum entries")
    for relative, raw in entries.items():
        row = _mapping(raw, f"checksums.{relative}")
        path = root / relative
        if not path.is_file() or _file_sha256(path) != str(row["sha256"]).upper():
            raise SpeakerProtocolError(f"speaker protocol checksum mismatch: {relative}")
    embedding_index = pq.read_table(root / "embeddings" / "index.parquet").to_pylist()
    decisions = pq.read_table(root / "unknown_rejection_decisions.parquet").to_pylist()
    metrics = _read_json(root / "metrics" / "summary.json")
    if any(not str(row["predicted_speaker_key"]).strip() for row in decisions):
        raise SpeakerProtocolError("speaker prediction cannot be null or empty")
    if any(row["status"] != "ok" and row["predicted_speaker_key"] != UNKNOWN_LABEL for row in decisions):
        raise SpeakerProtocolError("failed probes must preserve Unknown")
    expected = int(run["expected_items"])
    if len(embedding_index) != expected:
        raise SpeakerProtocolError("embedding index count does not match expected items")
    if int(metrics["extraction"]["expected_items"]) != expected:
        raise SpeakerProtocolError("metric extraction denominator mismatch")
    if run.get("private_identity_mapping_included") is not False:
        raise SpeakerProtocolError("private identity mapping leaked into shared results")
    return {
        "valid": True,
        "expected_items": expected,
        "decision_rows": len(decisions),
        "checksum_entries": len(entries),
    }


def _publish_embedding_observations(
    root: Path,
    rows: Sequence[Mapping[str, object]],
    observed: Mapping[str, EmbeddingObservation],
    identity: BackendIdentity,
    failures: list[dict[str, object]],
) -> list[dict[str, object]]:
    result = []
    for row in sorted(rows, key=lambda value: str(value["item_id"])):
        item_id = str(row["item_id"])
        observation = observed.get(item_id)
        if observation is None:
            status = "missing"
            _failure(failures, item_id, "extraction", "missing_embedding", "embedding observation is missing", identity, status)
            result.append(_embedding_index_row(item_id, None, identity, status))
            continue
        if observation.status != "ok":
            _failure(failures, item_id, "extraction", observation.status, observation.error or f"embedding status is {observation.status}", identity, observation.status)
            result.append(_embedding_index_row(item_id, observation, identity, observation.status))
            continue
        embedding_id = f"emb_{canonical_sha256({'item_id': item_id, 'identity': identity.identity_hash})[:16].lower()}"
        relative = f"embeddings/{embedding_id}.npz"
        _write_npz(
            root / relative,
            {
                "embedding": np.asarray(observation.vector, dtype=np.float32),
                "item_id": np.asarray([item_id]),
                "embedding_id": np.asarray([embedding_id]),
                "backend_id": np.asarray([identity.backend_id]),
                "model_hash": np.asarray([identity.model_hash]),
                "config_hash": np.asarray([identity.config_hash]),
                "schema_version": np.asarray(["speaker-embedding.v2"]),
            },
        )
        result.append(
            {
                "item_id": item_id,
                "embedding_id": embedding_id,
                "path": relative,
                "backend_id": identity.backend_id,
                "model_id": identity.model_id,
                "model_hash": identity.model_hash,
                "config_hash": identity.config_hash,
                "dimension": observation.dimension,
                "status": "ok",
                "l2_norm": math.sqrt(sum(value * value for value in observation.vector)),
                "duration_sec": observation.duration_sec,
                "extraction_sec": observation.extraction_sec,
            }
        )
    return result


def _embedding_index_row(
    item_id: str,
    observation: EmbeddingObservation | None,
    identity: BackendIdentity,
    status: str,
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "embedding_id": None,
        "path": None,
        "backend_id": identity.backend_id,
        "model_id": identity.model_id,
        "model_hash": identity.model_hash,
        "config_hash": identity.config_hash,
        "dimension": None,
        "status": status,
        "l2_norm": None,
        "duration_sec": observation.duration_sec if observation else None,
        "extraction_sec": observation.extraction_sec if observation else None,
    }


def _build_enrollment(
    root: Path,
    rows: Sequence[Mapping[str, object]],
    observed: Mapping[str, EmbeddingObservation],
    identity: BackendIdentity,
    failures: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, tuple[float, ...]], dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["speaker_key"])].append(row)
    index = []
    centroids: dict[str, tuple[float, ...]] = {}
    speaker_metadata = []
    for speaker_key, speaker_rows in sorted(grouped.items()):
        item_ids = sorted(str(row["item_id"]) for row in speaker_rows)
        vectors = [
            observed[item_id].vector
            for item_id in item_ids
            if item_id in observed and observed[item_id].status == "ok"
        ]
        relative: str | None = None
        if vectors:
            centroid = normalize_vector(
                [sum(values) / len(values) for values in zip(*vectors, strict=True)]
            )
            centroids[speaker_key] = centroid
            relative = f"enrollment/centroids/{speaker_key}.npz"
            _write_npz(
                root / relative,
                {
                    "centroid": np.asarray(centroid, dtype=np.float32),
                    "speaker_key": np.asarray([speaker_key]),
                    "backend_identity_hash": np.asarray([identity.identity_hash]),
                    "schema_version": np.asarray(["speaker-enrollment-centroid.v1"]),
                },
            )
        else:
            _failure(failures, speaker_key, "enrollment", "enrollment_failure", "speaker has no valid enrollment embeddings", identity, "failed")
        index.append(
            {
                "speaker_key": speaker_key,
                "centroid_path": relative,
                "requested_exemplars": len(item_ids),
                "successful_exemplars": len(vectors),
                "dimension": identity.embedding_dimension,
                "backend_id": identity.backend_id,
                "model_id": identity.model_id,
                "model_hash": identity.model_hash,
                "config_hash": identity.config_hash,
                "normalization": identity.normalization,
                "aggregation_method": identity.aggregation_method,
                "preprocessing_json": json.dumps(identity.preprocessing, sort_keys=True),
                "enrollment_item_ids_json": json.dumps(item_ids),
                "threshold_policy_version": identity.threshold_policy_version,
            }
        )
        speaker_metadata.append(
            {
                "speaker_key": speaker_key,
                "enrollment_item_ids": item_ids,
                "requested_exemplars": len(item_ids),
                "successful_exemplars": len(vectors),
            }
        )
    metadata = {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "backend_identity": identity.to_jsonable(),
        "embedding_dimension": identity.embedding_dimension,
        "normalization": identity.normalization,
        "preprocessing": dict(identity.preprocessing),
        "aggregation_method": identity.aggregation_method,
        "threshold_policy_version": identity.threshold_policy_version,
        "speakers": speaker_metadata,
        "private_identity_mapping_included": False,
    }
    metadata["enrollment_hash"] = canonical_sha256(metadata)
    return index, centroids, metadata


def _score_probes(
    rows: Sequence[Mapping[str, object]],
    observed: Mapping[str, EmbeddingObservation],
    centroids: Mapping[str, tuple[float, ...]],
    identity: BackendIdentity,
    failures: list[dict[str, object]],
) -> list[dict[str, object]]:
    result = []
    for row in sorted(rows, key=lambda value: str(value["item_id"])):
        item_id = str(row["item_id"])
        observation = observed.get(item_id)
        if observation is None or observation.status != "ok":
            continue
        if row["trial_role"] == "known_probe" and row["speaker_key"] not in centroids:
            _failure(failures, item_id, "scoring", "enrollment_unavailable", "true enrolled speaker has no centroid", identity, "failed")
        for candidate, centroid in sorted(centroids.items()):
            result.append(
                {
                    "probe_id": item_id,
                    "candidate_speaker_key": candidate,
                    "score": cosine_similarity(observation.vector, centroid),
                    "is_target": row["trial_role"] == "known_probe" and candidate == row["speaker_key"],
                    "protocol_split": str(row["protocol_split"]),
                    "probe_role": str(row["trial_role"]),
                    "condition": str(row["protocol_condition"]),
                    "score_status": "ok",
                }
            )
    return result


def _verification_decisions(trials: Sequence[Mapping[str, object]], threshold: float) -> list[dict[str, object]]:
    return [
        {
            "probe_id": row["probe_id"],
            "candidate_speaker_key": row["candidate_speaker_key"],
            "is_target": row["is_target"],
            "score": row["score"],
            "threshold": threshold,
            "accepted": float(row["score"]) >= threshold,
            "correct": (float(row["score"]) >= threshold) == bool(row["is_target"]),
            "condition": row["condition"],
        }
        for row in trials
    ]


def _identification_rankings(trials: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in trials:
        grouped[str(row["probe_id"])].append(row)
    result = []
    for probe_id, values in sorted(grouped.items()):
        ordered = sorted(values, key=lambda row: (-float(row["score"]), str(row["candidate_speaker_key"])))
        for rank, row in enumerate(ordered, start=1):
            result.append(
                {
                    "probe_id": probe_id,
                    "candidate_speaker_key": row["candidate_speaker_key"],
                    "score": row["score"],
                    "rank": rank,
                    "is_target": row["is_target"],
                    "condition": row["condition"],
                }
            )
    return result


def _open_set_decisions(
    rows: Sequence[Mapping[str, object]],
    rankings: Sequence[Mapping[str, object]],
    observed: Mapping[str, EmbeddingObservation],
    threshold: float,
) -> list[dict[str, object]]:
    best = {str(row["probe_id"]): row for row in rankings if int(row["rank"]) == 1}
    result = []
    for row in sorted(rows, key=lambda value: str(value["item_id"])):
        item_id = str(row["item_id"])
        observation = observed.get(item_id)
        candidate = best.get(item_id)
        status = "ok" if observation is not None and observation.status == "ok" and candidate else "failed"
        accepted = status == "ok" and float(candidate["score"]) >= threshold
        predicted = str(candidate["candidate_speaker_key"]) if accepted else UNKNOWN_LABEL
        known = row["trial_role"] == "known_probe"
        correct = status == "ok" and ((known and predicted == row["speaker_key"]) or (not known and predicted == UNKNOWN_LABEL))
        result.append(
            {
                "probe_id": item_id,
                "true_partition": "known" if known else "unknown",
                "true_speaker_key": str(row["speaker_key"]),
                "predicted_speaker_key": predicted,
                "best_score": float(candidate["score"]) if candidate is not None else None,
                "threshold": threshold if candidate is not None else None,
                "accepted_known": accepted,
                "correct": correct,
                "status": status,
                "condition": str(row["protocol_condition"]),
            }
        )
    return result


def _metrics(
    core: Mapping[str, Sequence[Mapping[str, object]]],
    observed: Mapping[str, EmbeddingObservation],
    enrollment_index: Sequence[Mapping[str, object]],
    similarity: Sequence[Mapping[str, object]],
    evaluation_sweep: Sequence[Mapping[str, object]],
    evaluation_eer: Mapping[str, object] | None,
    threshold: float,
    rankings: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
    failures: Sequence[Mapping[str, object]],
    policy: Mapping[str, object],
    *,
    workers: int = 1,
    progress_callback: Callable[[int], None] | None = None,
    drift_values: Sequence[float] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    all_rows = [row for rows in core.values() for row in rows]
    successful = sum(1 for row in all_rows if observed.get(str(row["item_id"])) and observed[str(row["item_id"])].status == "ok")
    short = sum(1 for value in observed.values() if value.status == "too_short")
    invalid_norm = sum(
        1
        for value in observed.values()
        if value.status == "ok"
        and not math.isclose(math.sqrt(sum(item * item for item in value.vector)), 1.0, abs_tol=1e-4)
    )
    evaluation_trials = [row for row in similarity if row["protocol_split"] == "evaluation"]
    same = [float(row["score"]) for row in evaluation_trials if row["is_target"]]
    different = [float(row["score"]) for row in evaluation_trials if not row["is_target"]]
    evaluation_operating = operating_point(evaluation_trials, threshold)
    known_decisions = [row for row in decisions if row["true_partition"] == "known"]
    unknown_decisions = [row for row in decisions if row["true_partition"] == "unknown"]
    ranking_by_probe: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rankings:
        ranking_by_probe[str(row["probe_id"])].append(row)
    top_k = {}
    for k in policy["metrics"]["top_k"]:
        correct = 0
        for decision in known_decisions:
            target = str(decision["true_speaker_key"])
            correct += any(
                str(row["candidate_speaker_key"]) == target and int(row["rank"]) <= int(k)
                for row in ranking_by_probe.get(str(decision["probe_id"]), [])
            )
        top_k[f"top_{k}"] = proportion_metric(correct, len(known_decisions))
    unknown_correct = sum(1 for row in unknown_decisions if row["correct"])
    false_known = sum(1 for row in unknown_decisions if row["accepted_known"])
    known_open_correct = sum(1 for row in known_decisions if row["correct"])
    selected_drift = list(drift_values) if drift_values is not None else _paired_drift(core, observed)
    repetitions = int(policy["metrics"]["bootstrap_repetitions"])
    seed = int(policy["metrics"]["bootstrap_seed"])
    metrics: dict[str, object] = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "counts_reconcile": True,
        "failures_preserved_in_denominators": True,
        "extraction": {
            "expected_items": len(all_rows),
            "observed_items": len(observed),
            "successful_items": successful,
            "success_rate": proportion_metric(successful, len(all_rows)),
            "short_audio_rejections": short,
            "invalid_norms": invalid_norm,
        },
        "enrollment": {
            "speakers_requested": len(enrollment_index),
            "speakers_enrolled": sum(1 for row in enrollment_index if int(row["successful_exemplars"]) > 0),
            "enrollment_failures": sum(1 for row in enrollment_index if int(row["successful_exemplars"]) == 0),
        },
        "score_distributions": {
            "same_speaker": score_distribution(same, seed=seed, repetitions=repetitions, workers=workers, progress_callback=progress_callback),
            "different_speaker": score_distribution(different, seed=seed + 1, repetitions=repetitions, workers=workers, progress_callback=progress_callback),
        },
        "embedding_drift": score_distribution(selected_drift, seed=seed + 2, repetitions=repetitions, workers=workers, progress_callback=progress_callback),
        "verification": {
            "operating_threshold_source": "calibration_only",
            "operating_threshold": threshold,
            "evaluation_at_calibrated_threshold": evaluation_operating,
            "evaluation_oracle_eer_diagnostic": evaluation_eer,
            "tar_at_fixed_far": [
                tar_at_fixed_far(evaluation_sweep, float(target))
                for target in policy["calibration"]["fixed_far_targets"]
            ],
            "roc_det_rows": len(evaluation_sweep),
        },
        "closed_set_identification": {
            "probe_count": len(known_decisions),
            **top_k,
        },
        "open_set_identification": {
            "known_probe_accuracy": proportion_metric(known_open_correct, len(known_decisions)),
            "unknown_rejection": proportion_metric(unknown_correct, len(unknown_decisions)),
            "false_known_assignment": proportion_metric(false_known, len(unknown_decisions)),
            "failed_unknown_probes_credited_as_rejections": False,
            "unknown_label": UNKNOWN_LABEL,
        },
        "probe_failures": proportion_metric(
            sum(1 for row in decisions if row["status"] != "ok"), len(decisions)
        ),
        "failure_records": len(failures),
        "calibration_evaluation_separate": True,
        "open_closed_set_results_separate": True,
    }
    grouped = _grouped_metrics(core, decisions)
    return metrics, grouped


def _grouped_metrics(
    core: Mapping[str, Sequence[Mapping[str, object]]],
    decisions: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = core["known_evaluation"] + core["unknown_evaluation"]
    row_by_id = {str(row["item_id"]): row for row in rows}
    result = []
    for group_type in ("speaker_key", "protocol_condition", "gender", "accent_group"):
        grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for decision in decisions:
            source = row_by_id[str(decision["probe_id"])]
            value = source.get(group_type)
            if value is not None and str(value).strip():
                grouped[str(value)].append(decision)
        for value, group in sorted(grouped.items()):
            correct = sum(1 for row in group if row["correct"])
            metric = proportion_metric(correct, len(group))
            interval = metric["confidence_interval"] or {}
            result.append(
                {
                    "group_type": group_type,
                    "group_value": value,
                    "metric_name": "open_set_accuracy",
                    "metric_value": metric["value"],
                    "numerator": correct,
                    "denominator": len(group),
                    "ci_lower": interval.get("lower"),
                    "ci_upper": interval.get("upper"),
                }
            )
    return result


def _paired_drift(
    core: Mapping[str, Sequence[Mapping[str, object]]],
    observed: Mapping[str, EmbeddingObservation],
) -> list[float]:
    pairs: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for kind in ("calibration", "known_evaluation", "unknown_evaluation"):
        for row in core[kind]:
            pairs[(str(row["speaker_key"]), str(row["source_utterance_id"]))][
                str(row["protocol_condition"])
            ] = str(row["item_id"])
    drift = []
    for conditions in pairs.values():
        clean = observed.get(conditions.get("clean", ""))
        degraded = observed.get(conditions.get("degraded", ""))
        if clean and degraded and clean.status == degraded.status == "ok":
            drift.append(1.0 - cosine_similarity(clean.vector, degraded.vector))
    return drift


def _eer_bootstrap(
    trials: Sequence[Mapping[str, object]],
    *,
    seed: int,
    repetitions: int,
    workers: int = 1,
    progress_callback: Callable[[int], None] | None = None,
) -> dict[str, float] | None:
    positives = np.asarray([float(row["score"]) for row in trials if row["is_target"]], dtype=np.float64)
    negatives = np.asarray([float(row["score"]) for row in trials if not row["is_target"]], dtype=np.float64)
    if not len(positives) or not len(negatives):
        return None
    count = max(1, repetitions)
    values: list[float | None] = [None] * count
    if workers == 1:
        for repetition in range(count):
            values[repetition] = _eer_bootstrap_replicate(positives, negatives, seed, repetition)
            if progress_callback:
                progress_callback(1)
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="speaker-eer") as executor:
            futures = {
                executor.submit(_eer_bootstrap_replicate, positives, negatives, seed, repetition): repetition
                for repetition in range(count)
            }
            for future in as_completed(futures):
                values[futures[future]] = future.result()
                if progress_callback:
                    progress_callback(1)
    materialized = [float(value) for value in values if value is not None]
    materialized.sort()
    if not materialized:
        return None
    return {
        "confidence_level": 0.95,
        "lower": _percentile(materialized, 0.025),
        "upper": _percentile(materialized, 0.975),
        "bootstrap_repetitions": len(materialized),
    }


def _eer_bootstrap_replicate(
    positives: np.ndarray,
    negatives: np.ndarray,
    seed: int,
    repetition: int,
) -> float:
    """Return one schedule-independent bootstrap EER using shared score arrays."""

    rng = np.random.default_rng(np.random.SeedSequence([int(seed), int(repetition)]))
    sampled_positive = positives[rng.integers(0, len(positives), size=len(positives))]
    sampled_negative = negatives[rng.integers(0, len(negatives), size=len(negatives))]
    scores = np.concatenate((sampled_positive, sampled_negative))
    targets = np.concatenate(
        (np.ones(len(sampled_positive), dtype=np.int8), np.zeros(len(sampled_negative), dtype=np.int8))
    )
    order = np.argsort(-scores, kind="stable")
    ordered_scores = scores[order]
    ordered_targets = targets[order]
    boundaries = np.r_[np.flatnonzero(ordered_scores[:-1] != ordered_scores[1:]), len(scores) - 1]
    cumulative_positive = np.cumsum(ordered_targets, dtype=np.int64)[boundaries]
    accepted = boundaries + 1
    cumulative_negative = accepted - cumulative_positive
    far = cumulative_negative / len(sampled_negative)
    frr = (len(sampled_positive) - cumulative_positive) / len(sampled_positive)
    best = int(np.argmin(np.abs(far - frr)))
    return float((far[best] + frr[best]) / 2.0)


def _percentile(values: Sequence[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def _validate_observation_identity(observation: EmbeddingObservation, identity: BackendIdentity) -> None:
    mismatches = []
    if observation.backend_id != identity.backend_id:
        mismatches.append("backend_id")
    if observation.model_hash.upper() != identity.model_hash.upper():
        mismatches.append("model_hash")
    if observation.config_hash.upper() != identity.config_hash.upper():
        mismatches.append("config_hash")
    if observation.status == "ok" and observation.dimension != identity.embedding_dimension:
        mismatches.append("embedding_dimension")
    if mismatches:
        raise SpeakerProtocolError(
            f"embedding observation {observation.item_id} identity mismatch: {', '.join(mismatches)}"
        )


def _failure(
    failures: list[dict[str, object]],
    item_id: str,
    phase: str,
    error_type: str,
    message: str,
    identity: BackendIdentity,
    status: str,
) -> None:
    failures.append(
        {
            "item_id": item_id,
            "phase": phase,
            "error_type": error_type,
            "message": str(message),
            "backend_id": identity.backend_id,
            "status": status,
            "counts_in_denominator": True,
        }
    )


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    _write_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"),
    )


def _write_parquet(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    schema: pa.Schema,
    schema_version: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(schema.metadata or {})
    metadata[b"artifact_schema_version"] = schema_version.encode()
    table = pa.Table.from_pylist([dict(row) for row in rows], schema=schema).replace_schema_metadata(metadata)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        pq.write_table(table, temporary, version="2.6", compression="NONE", use_dictionary=False)
        pq.read_table(temporary)
        _replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_npz(path: Path, arrays: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as handle:
            np.savez(handle, **{str(key): np.asarray(value) for key, value in arrays.items()})
        with np.load(temporary, allow_pickle=False):
            pass
        _replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace(source: Path, destination: Path) -> None:
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))


def _write_checksums(root: Path) -> None:
    entries = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in {"checksums.json", "evaluation_progress.json"} or path.name.endswith(".tmp"):
            continue
        relative = path.relative_to(root).as_posix()
        entries[relative] = {
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
            "privacy_classification": "biometric_sensitive" if path.suffix == ".npz" else "internal",
        }
    _write_json(
        root / "checksums.json",
        {
            "schema_version": "speaker-protocol-checksums.v1",
            "hash_algorithm": "sha256",
            "entries": entries,
        },
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SpeakerProtocolError(f"JSON root must be a mapping: {path}")
    return {str(key): item for key, item in value.items()}


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SpeakerProtocolError(f"{name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _finite_or_none(value: object) -> float | None:
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None
