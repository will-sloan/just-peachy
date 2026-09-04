"""Restart-safe held-out embedding extraction and frozen score-bundle generation."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Iterable, Mapping, Sequence
import uuid

import numpy as np

from app.controlled_diarization.runner import interpreter_for_profile
from app.diarization_evaluation.formats import parse_rttm
from app.hybrid_final_evaluation.contracts import (
    CACHE_ROOT,
    CORPORA,
    FINAL_DIARIZATION_ROOT,
    FROZEN_HYBRID_PATH,
    PRODUCT_PROTOCOL_ROOT,
    PROGRESS_PATH,
    RESULT_ROOT,
    SCORE_ROOT,
    STATE_PATH,
    STOP_PATH,
    TOOL_ROOT,
    FinalHybridEvaluationError,
    atomic_json,
    file_sha256,
    now_utc,
    read_json,
    read_jsonl,
    write_jsonl,
)
from app.hybrid_final_evaluation.decision import require_valid_decision
from app.hybrid_speaker_attribution.embedding_cache import embedding_job, load_cached
from app.hybrid_speaker_attribution.product_v2_runner import _cluster_events, _overlap
from app.speaker_protocol.contracts import eligible_embedding_backends
from app.utils.paths import resolve_data_path_from_logical


_CACHE_INDICES: dict[str, dict[str, Mapping[str, object]]] = {}
_TEMPLATE_CACHE: dict[str, dict[str, dict[str, object]]] = {}
_ENROLLMENT_DATABASE_CACHE: dict[str, Mapping[str, object]] | None = None
_FINALISTS_CACHE: tuple[dict[str, object], ...] | None = None


def plan() -> dict[str, object]:
    frozen, finalists = require_valid_decision()
    cases = evaluation_cases()
    overlays = overlay_index()
    replay_units = 0
    for finalist in finalists:
        for corpus, rows in cases.items():
            for case in rows:
                for overlay_id in ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"):
                    overlay = overlays[(corpus, str(case["case_id"]), overlay_id)]
                    replay_units += 2 * sum(row.get("status") == "VALID" for row in overlay["gallery_subsets"])
    result = {
        "schema_version": "hybrid-final-plan.v1",
        "status": "READY",
        "frozen_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
        "selected_finalists": [row["hybrid_combination_id"] for row in finalists],
        "controlled_cases": {key: len(value) for key, value in cases.items()},
        "controlled_score_bundles": sum(len(value) for value in cases.values()) * len(finalists),
        "frozen_policy_replay_units": replay_units,
        "identity_backends": sorted({str(row["identity_backend_id"]) for row in finalists}),
        "anonymous_diarization": "REUSE_COMPLETE_HELD_OUT_RESULTS",
        "chime6": "CHIME6_HYBRID_NOT_SCIENTIFICALLY_SUPPORTED",
        "voices": "NOT_SUPPORTED_NO_FROZEN_IDENTITY_PROTOCOL",
        "asr": "NOT_RUN",
        "xvf3800": "NOT_RUN",
        "fine_tuning": "NOT_RUN",
    }
    atomic_json(RESULT_ROOT / "plan.json", result)
    return result


def run_controlled(*, parallel_backends: int = 2, max_cases: int | None = None) -> dict[str, object]:
    global _FINALISTS_CACHE
    frozen, finalists = require_valid_decision()
    _FINALISTS_CACHE = finalists
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    STOP_PATH.unlink(missing_ok=True)
    cases = evaluation_cases(max_cases=max_cases)
    started = time.time()
    _write_run_authorization(frozen, finalists, cases)
    _state("RUNNING", "CONTROLLED_V1", "Valid frozen decision; preparing held-out identity jobs")
    jobs_by_backend = {
        backend: _build_jobs(backend, finalists, cases)
        for backend in sorted({str(row["identity_backend_id"]) for row in finalists})
    }
    _initialize_progress(started, jobs_by_backend, cases, finalists)
    errors: list[dict[str, str]] = []
    _state("RUNNING", "EMBEDDING_EXTRACTION", "Extracting independent held-out identity embeddings")
    with ThreadPoolExecutor(max_workers=max(1, min(parallel_backends, len(jobs_by_backend)))) as executor:
        futures = {executor.submit(_extract_backend, backend, jobs): backend for backend, jobs in jobs_by_backend.items()}
        while futures:
            for future in [item for item in futures if item.done()]:
                backend = futures.pop(future)
                try:
                    future.result()
                except Exception as exc:
                    errors.append({"backend": backend, "error": f"{type(exc).__name__}: {exc}"})
            _refresh_progress(started, cases, finalists)
            if futures:
                time.sleep(2)
    if errors:
        atomic_json(RESULT_ROOT / "embedding_failures.json", {"failures": errors})
        _state("FAILED", "EMBEDDING_EXTRACTION", json.dumps(errors))
        raise FinalHybridEvaluationError(f"held-out embedding extraction failed: {errors}")
    if STOP_PATH.exists():
        _state("STOPPED", "EMBEDDING_EXTRACTION", "Stopped after active backend workers completed")
        return status()

    _state("RUNNING", "SCORE_BUNDLES", "Generating checksum-bound held-out score bundles")
    units = [
        {"combination_id": finalist["hybrid_combination_id"], "corpus": corpus, "case_id": case["case_id"]}
        for finalist in finalists
        for corpus, rows in cases.items()
        for case in rows
    ]
    failures = _execute_score_worker_batches(units, started, cases, finalists)
    atomic_json(RESULT_ROOT / "score_bundle_failures.json", {"schema_version": "hybrid-final-score-failures.v1", "failures": failures})
    if failures:
        _state("FAILED", "SCORE_BUNDLES", f"{len(failures)} held-out score bundles failed")
        raise FinalHybridEvaluationError(f"{len(failures)} held-out score bundles failed")
    if STOP_PATH.exists():
        _state("STOPPED", "SCORE_BUNDLES", "Stopped after current checksum-bound score unit")
        return status()
    _write_native_scope_status()
    _refresh_progress(started, cases, finalists)
    _state("SCORES_COMPLETE", "ANALYSIS", "All 576 held-out score bundles are complete; frozen policy replay is pending")
    return status()


def run_native_scope(scope: str) -> dict[str, object]:
    require_valid_decision()
    _write_native_scope_status()
    if scope.lower() == "chime6":
        return {
            "status": "CHIME6_HYBRID_NOT_SCIENTIFICALLY_SUPPORTED",
            "reason": "Task 1 could not prove source-time and synchronized-duplicate disjointness for close enrollment versus far-field probes; no inference was run.",
        }
    if scope.lower() == "voices":
        return {
            "status": "NOT_SUPPORTED",
            "label": "VOICES FAR-FIELD IDENTITY DIAGNOSTIC",
            "reason": "Task 1 did not freeze a scientifically valid enrollment/probe identity mapping for VOiCES; no unsupported hybrid metrics were calculated.",
        }
    raise FinalHybridEvaluationError(f"unknown native scope: {scope}")


def stop() -> dict[str, object]:
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    STOP_PATH.write_text(f"requested_at_utc={now_utc()}\n", encoding="utf-8")
    return {"status": "STOP_REQUESTED", "path": str(STOP_PATH), "policy": "finish active backend workers or current score unit, then stop"}


def status() -> dict[str, object]:
    state = read_json(STATE_PATH) if STATE_PATH.is_file() else {"status": "NOT_STARTED", "stage": "NONE"}
    progress = read_json(PROGRESS_PATH) if PROGRESS_PATH.is_file() else {}
    return {
        "schema_version": "hybrid-final-status.v1",
        "controller": state,
        "progress": progress,
        "result_root": str(RESULT_ROOT),
        "stop_requested": STOP_PATH.exists(),
    }


def evaluation_cases(max_cases: int | None = None) -> dict[str, list[dict[str, object]]]:
    result = {
        corpus: read_jsonl(Path(settings["benchmark_root"]) / "evaluation" / "case_manifest.jsonl")
        for corpus, settings in CORPORA.items()
    }
    return {key: rows[:max_cases] for key, rows in result.items()} if max_cases is not None else result


def overlay_index() -> dict[tuple[str, str, str], Mapping[str, object]]:
    result: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for corpus in CORPORA:
        for row in read_jsonl(PRODUCT_PROTOCOL_ROOT / corpus / "evaluation" / "identity_overlays.jsonl"):
            result[(corpus, str(row["case_id"]), str(row["overlay_id"]))] = row
    return result


def score_bundle_path(combination_id: str, corpus: str, case_id: str) -> Path:
    return SCORE_ROOT / combination_id / corpus / f"{case_id}.json.gz"


def load_score_bundle(combination_id: str, corpus: str, case_id: str) -> dict[str, object]:
    path = score_bundle_path(combination_id, corpus, case_id)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not path.is_file() or not sidecar.is_file() or file_sha256(path).lower() != sidecar.read_text(encoding="utf-8").split()[0].lower():
        raise FinalHybridEvaluationError(f"invalid held-out score bundle: {path}")
    return _read_gzip_json(path)


def validate_score_bundles() -> dict[str, object]:
    _, finalists = require_valid_decision()
    expected = sum(len(rows) for rows in evaluation_cases().values())
    counts: dict[str, int] = defaultdict(int)
    errors = []
    for path in SCORE_ROOT.glob("*/*/*.json.gz"):
        try:
            value = _read_gzip_json(path)
            sidecar = path.with_suffix(path.suffix + ".sha256")
            if not sidecar.is_file() or file_sha256(path).lower() != sidecar.read_text(encoding="utf-8").split()[0].lower():
                raise ValueError("checksum mismatch")
            if value.get("schema_version") != "hybrid-final-score-bundle.v1" or value.get("status") != "SUCCEEDED":
                raise ValueError("schema/status mismatch")
            if value.get("frozen_hybrid_selection_sha256") != file_sha256(FROZEN_HYBRID_PATH).lower():
                raise ValueError("frozen decision binding mismatch")
            counts[str(value["combination_id"])] += 1
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})
    for row in finalists:
        combo = str(row["hybrid_combination_id"])
        if counts.get(combo, 0) != expected:
            errors.append({"combination_id": combo, "error": f"expected {expected}, observed {counts.get(combo, 0)}"})
    return {"status": "PASS" if not errors else "FAIL", "expected_per_finalist": expected, "counts": dict(counts), "errors": errors}


def score_unit(combination_id: str, corpus: str, case_id: str) -> None:
    finalists = _finalists()
    finalist = next((row for row in finalists if row["hybrid_combination_id"] == combination_id), None)
    if finalist is None:
        raise FinalHybridEvaluationError(f"not a frozen finalist: {combination_id}")
    case = next(row for row in evaluation_cases()[corpus] if row["case_id"] == case_id)
    _score_case(finalist, corpus, case)


def _build_jobs(backend: str, finalists: Sequence[Mapping[str, object]], cases_by_corpus: Mapping[str, Sequence[Mapping[str, object]]]) -> list[dict[str, object]]:
    jobs: list[dict[str, object]] = []
    relevant_pipelines = {str(row["diarization_pipeline_id"]) for row in finalists if row["identity_backend_id"] == backend}
    finalist = next(row for row in finalists if row["identity_backend_id"] == backend)
    count = int(finalist["enrollment_utterance_count"])
    for item in _enrollment_database().values():
        for clip in list(item["reserved_enrollment_clips"])[:count]:
            jobs.append(embedding_job(
                job_id=_enrollment_job_id(str(item["enrolled_id"]), str(clip["source_clip_id"])),
                audio_path=resolve_data_path_from_logical(str(clip["logical_audio_path"])),
                audio_sha256=str(clip["source_audio_sha256"]),
                start_sec=0.0,
                end_sec=float(clip["duration_sec"]),
                role="reserved_scientific_evaluation_enrollment",
                metadata={"enrolled_id": item["enrolled_id"], "global_speaker_id": item["global_speaker_id"], "tier": "evaluation"},
            ))
    for corpus, cases in cases_by_corpus.items():
        benchmark = Path(CORPORA[corpus]["benchmark_root"])
        for case in cases:
            audio = _audio_path(corpus, case)
            for index, turn in enumerate(parse_rttm(benchmark / str(case["reference_rttm_path"]))):
                jobs.append(embedding_job(
                    job_id=_reference_job_id(corpus, str(case["case_id"]), index),
                    audio_path=audio,
                    audio_sha256=str(case["audio_sha256"]),
                    start_sec=float(turn.start_sec),
                    end_sec=float(turn.start_sec + turn.duration_sec),
                    role="held_out_oracle_reference_turn_diagnostic",
                    metadata={"corpus": corpus, "case_id": case["case_id"], "speaker_label": turn.speaker_label, "tier": "evaluation"},
                ))
            for pipeline in relevant_pipelines:
                result = _diarization_result_root(corpus, pipeline, str(case["case_id"]))
                for index, turn in enumerate(parse_rttm(result / "predictions" / "segments.rttm")):
                    jobs.append(embedding_job(
                        job_id=_prediction_job_id(corpus, pipeline, str(case["case_id"]), index),
                        audio_path=audio,
                        audio_sha256=str(case["audio_sha256"]),
                        start_sec=float(turn.start_sec),
                        end_sec=float(turn.start_sec + turn.duration_sec),
                        role="held_out_independent_identity_predicted_segment",
                        metadata={"corpus": corpus, "case_id": case["case_id"], "pipeline_id": pipeline, "cluster_id": turn.speaker_label, "tier": "evaluation"},
                    ))
    unique = {str(row["job_identity"]): row for row in jobs}
    rows = sorted(unique.values(), key=lambda row: str(row["job_id"]))
    manifest = RESULT_ROOT / "cache_inventory" / f"{backend}.jobs.jsonl"
    write_jsonl(manifest, rows)
    atomic_json(manifest.with_suffix(".summary.json"), {
        "schema_version": "hybrid-final-job-inventory.v1",
        "backend_id": backend,
        "jobs": len(rows),
        "audio_sec": sum(float(row["end_sec"]) - float(row["start_sec"]) for row in rows),
        "roles": dict(_counts(str(row["role"]) for row in rows)),
        "manifest_sha256": file_sha256(manifest).lower(),
        "frozen_hybrid_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
    })
    return rows


def _extract_backend(backend: str, jobs: Sequence[Mapping[str, object]]) -> dict[str, object]:
    eligible = eligible_embedding_backends(backend_ids={backend})
    if backend not in eligible:
        raise FinalHybridEvaluationError(f"qualified frozen backend unavailable: {backend}")
    interpreter = interpreter_for_profile(str(eligible[backend]["environment_profile"]))
    if interpreter is None or not interpreter.is_file():
        raise FinalHybridEvaluationError(f"frozen backend environment unavailable: {backend}")
    manifest = RESULT_ROOT / "cache_inventory" / f"{backend}.jobs.jsonl"
    progress = RESULT_ROOT / "embedding_progress" / f"{backend}.json"
    log_root = RESULT_ROOT / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    completed = subprocess.run(
        [str(interpreter), "-m", "app.hybrid_speaker_attribution.embedding_cache", "--backend", backend, "--jobs", str(manifest), "--cache-root", str(CACHE_ROOT), "--progress-path", str(progress)],
        cwd=TOOL_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    wall = time.perf_counter() - started
    (log_root / f"{backend}.stdout.log").write_text(completed.stdout, encoding="utf-8", errors="replace")
    (log_root / f"{backend}.stderr.log").write_text(completed.stderr, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise FinalHybridEvaluationError(f"{backend} embedding worker exited {completed.returncode}: {(completed.stderr or completed.stdout)[-2000:]}")
    summary = read_json(CACHE_ROOT / backend / "extraction_summary.json")
    if not summary.get("backend_identity"):
        raise FinalHybridEvaluationError(f"{backend} produced no valid held-out embeddings")
    atomic_json(RESULT_ROOT / "cache_inventory" / f"{backend}.runtime.json", {
        "schema_version": "hybrid-final-backend-runtime.v1",
        "backend_id": backend,
        "worker_wall_sec": wall,
        "jobs": summary["jobs"],
        "successful": summary["successful"],
        "failed": summary["failed"],
        "reused": summary["reused"],
    })
    return summary


def _execute_score_worker_batches(units: Sequence[Mapping[str, object]], started: float, cases: Mapping[str, Sequence[Mapping[str, object]]], finalists: Sequence[Mapping[str, object]], batch_size: int = 8) -> list[dict[str, object]]:
    failures = []
    for offset in range(0, len(units), batch_size):
        if STOP_PATH.exists():
            break
        batch = list(units[offset: offset + batch_size])
        completed = _invoke_score_worker(batch, f"batch_{offset // batch_size:04d}")
        if completed["returncode"] != 0:
            for unit in batch:
                isolated = _invoke_score_worker([unit], f"isolated_{unit['combination_id']}_{unit['corpus']}_{unit['case_id']}")
                if isolated["returncode"] != 0:
                    failures.append({**dict(unit), "error": str(isolated["stderr"] or isolated["stdout"])[-3000:]})
        _refresh_progress(started, cases, finalists, current=batch[-1])
    return failures


def _invoke_score_worker(units: Sequence[Mapping[str, object]], label: str) -> dict[str, object]:
    manifest = RESULT_ROOT / "score_worker_manifests" / f".{label}.{uuid.uuid4().hex[:8]}.json"
    atomic_json(manifest, {"schema_version": "hybrid-final-score-worker-manifest.v1", "units": list(units)})
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "app.hybrid_final_evaluation.score_worker", "--manifest", str(manifest)],
            cwd=TOOL_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=900,
        )
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"returncode": 124, "stdout": exc.stdout or "", "stderr": f"worker timed out: {exc.stderr or ''}"}
    finally:
        manifest.unlink(missing_ok=True)


def _score_case(finalist: Mapping[str, object], corpus: str, case: Mapping[str, object]) -> None:
    combination_id = str(finalist["hybrid_combination_id"])
    destination = score_bundle_path(combination_id, corpus, str(case["case_id"]))
    if _valid_bundle(destination, finalist, case):
        return
    backend = str(finalist["identity_backend_id"])
    pipeline = str(finalist["diarization_pipeline_id"])
    cache = _cache_index(backend)
    result_root = _diarization_result_root(corpus, pipeline, str(case["case_id"]))
    benchmark = Path(CORPORA[corpus]["benchmark_root"])
    predictions = []
    identity_embedding_sec = 0.0
    for index, turn in enumerate(parse_rttm(result_root / "predictions" / "segments.rttm")):
        item = _cached(backend, cache, _prediction_job_id(corpus, pipeline, str(case["case_id"]), index))
        identity_embedding_sec += float(item.get("extraction_sec") or 0.0)
        predictions.append({
            "segment_id": f"pred_{index:04d}",
            "start_sec": float(turn.start_sec),
            "end_sec": float(turn.start_sec + turn.duration_sec),
            "duration_sec": float(turn.duration_sec),
            "cluster_id": str(turn.speaker_label),
            "embedding_status": item["status"],
            "vector": item["vector"],
            "predicted_overlap": False,
        })
    for row in predictions:
        row["predicted_overlap"] = any(other is not row and other["cluster_id"] != row["cluster_id"] and _overlap(row, other) > 0 for other in predictions)
    references = []
    for index, turn in enumerate(parse_rttm(benchmark / str(case["reference_rttm_path"]))):
        references.append({
            "segment_id": f"ref_{index:04d}",
            "start_sec": float(turn.start_sec),
            "end_sec": float(turn.start_sec + turn.duration_sec),
            "duration_sec": float(turn.duration_sec),
            "speaker_label": str(turn.speaker_label),
            "global_speaker_id": str(dict(case["local_to_global_speaker"])[str(turn.speaker_label)]),
        })
    templates = _templates(backend, cache, finalist)
    policy = {
        "aggregation_method": finalist["enrollment_aggregation"],
        "technical_minimum_evidence_sec": 0.50 if backend == "redimnet2_b2_speaker_embedding" else 0.75,
    }
    clusters = []
    for cluster_id in sorted({str(row["cluster_id"]) for row in predictions}, key=lambda value: min(float(row["start_sec"]) for row in predictions if row["cluster_id"] == value)):
        segments = sorted((row for row in predictions if row["cluster_id"] == cluster_id), key=lambda row: (float(row["end_sec"]), str(row["segment_id"])))
        reference_overlap: dict[str, float] = defaultdict(float)
        for segment in segments:
            for reference in references:
                reference_overlap[str(reference["global_speaker_id"])] += _overlap(segment, reference)
        primary_events = _cluster_events([row for row in segments if not row["predicted_overlap"]], templates, policy)
        diagnostic_events = _cluster_events(segments, templates, policy)
        total = sum(reference_overlap.values())
        dominant = max(reference_overlap, key=reference_overlap.get) if reference_overlap else None
        clusters.append({
            "cluster_id": cluster_id,
            "first_start_sec": min(float(row["start_sec"]) for row in segments),
            "last_end_sec": max(float(row["end_sec"]) for row in segments),
            "predicted_speech_sec": sum(float(row["duration_sec"]) for row in segments),
            "reference_overlap_sec": dict(reference_overlap),
            "dominant_global_speaker_id": dominant,
            "contamination": 1.0 - (float(reference_overlap.get(dominant, 0.0)) / total if dominant and total else 0.0),
            "events": primary_events,
            "events_include_predicted_overlap_diagnostic": diagnostic_events,
        })
    run = read_json(result_root / "run.json")
    diar_identity = read_json(result_root / "resolved_pipeline_identity.json")
    diar_metrics = read_json(result_root / "metrics" / "summary.json")
    extraction = read_json(CACHE_ROOT / backend / "extraction_summary.json")
    duration = float(case["duration_sec"])
    diar_sec = float(dict(run.get("timing") or {}).get("diarization_inference_sec") or 0.0)
    strict = dict(diar_metrics.get("primary_strict") or {})
    resource = {
        "identity_embedding_sec": identity_embedding_sec,
        "identity_embedding_rtf": identity_embedding_sec / duration if duration else None,
        "diarization_sec": diar_sec,
        "diarization_rtf": diar_sec / duration if duration else None,
        "total_hybrid_sec": diar_sec + identity_embedding_sec,
        "total_rtf": (diar_sec + identity_embedding_sec) / duration if duration else None,
        "peak_rss_mb": dict(run.get("resource_telemetry") or {}).get("peak_rss_mb"),
        "embedding_count": len(predictions),
        "asr_runtime_sec": 0.0,
    }
    payload = {
        "schema_version": "hybrid-final-score-bundle.v1",
        "status": "SUCCEEDED",
        "created_at_utc": now_utc(),
        "combination_id": combination_id,
        "corpus": corpus,
        "case_id": case["case_id"],
        "benchmark_id": case["benchmark_id"],
        "protocol_id": read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")["protocol_id"],
        "tier": "evaluation",
        "evaluation_role": "held_out_final_evaluation",
        "speaker_count": case["speaker_count"],
        "active_speaker_band": _active_band(int(case["speaker_count"])),
        "duration_sec": case["duration_sec"],
        "scenario_profile": case.get("scenario_profile") or "controlled_v1_factorial",
        "turn_cadence": case.get("turn_cadence"),
        "overlap_profile": case.get("overlap_profile"),
        "participation_profile": case.get("participation_profile"),
        "long_session": bool(case.get("long_session", False)),
        "diarization_pipeline_id": pipeline,
        "diarization_configuration_sha256": diar_identity.get("configuration_sha256") or diar_identity.get("pipeline_configuration_sha256") or run.get("pipeline_configuration_sha256"),
        "identity_backend_id": backend,
        "identity_backend_identity": extraction["backend_identity"],
        "scientific_enrollment_policy_id": finalist["scientific_enrollment_policy_id"],
        "scientific_enrollment_policy_sha256": finalist["scientific_enrollment_policy_sha256"],
        "frozen_score_threshold": finalist["score_threshold"],
        "frozen_margin_threshold": finalist["margin_threshold"],
        "frozen_minimum_evidence_sec": finalist["minimum_evidence_sec"],
        "independent_identity_reembedding": True,
        "same_model_reuse_used_for_primary": False,
        "references": references,
        "predictions": [{key: value for key, value in row.items() if key != "vector"} for row in predictions],
        "clusters": clusters,
        "resource": resource,
        "anonymous_diarization": {
            "der": strict.get("der"),
            "jer": strict.get("jer"),
            "speaker_count_error": dict(diar_metrics.get("speaker_count") or {}).get("signed_error"),
            "cluster_purity": diar_metrics.get("cluster_purity"),
            "reference_coverage": diar_metrics.get("reference_speaker_coverage"),
            "fragmentation": diar_metrics.get("fragmentation"),
            "merging": diar_metrics.get("merging"),
        },
        "frozen_hybrid_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
        "evaluation_results_inspected": True,
        "evaluation_tuning_performed": False,
        "asr_run": False,
        "xvf_available": False,
        "fine_tuning_run": False,
    }
    payload["evaluation_unit_sha256"] = hashlib.sha256(json.dumps({
        "combination_id": combination_id,
        "case_id": case["case_id"],
        "audio_sha256": case["audio_sha256"],
        "diarization_configuration_sha256": payload["diarization_configuration_sha256"],
        "identity_backend_identity": payload["identity_backend_identity"],
        "scientific_enrollment_policy_sha256": payload["scientific_enrollment_policy_sha256"],
        "frozen_hybrid_selection_sha256": payload["frozen_hybrid_selection_sha256"],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    _write_gzip_json(destination, payload)


def _templates(backend: str, cache: Mapping[str, Mapping[str, object]], finalist: Mapping[str, object]) -> dict[str, dict[str, object]]:
    if backend in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[backend]
    result = {}
    for enrolled_id, item in _enrollment_database().items():
        vectors = []
        clip_ids = []
        for clip in list(item["reserved_enrollment_clips"])[: int(finalist["enrollment_utterance_count"])]:
            cached = _cached(backend, cache, _enrollment_job_id(str(enrolled_id), str(clip["source_clip_id"])))
            if cached["status"] == "ok":
                vectors.append(_normal(cached["vector"]))
                clip_ids.append(str(clip["source_clip_id"]))
        result[str(enrolled_id)] = {"global_speaker_id": item["global_speaker_id"], "vectors": vectors, "source_clip_ids": clip_ids}
    _TEMPLATE_CACHE[backend] = result
    return result


def _enrollment_database() -> dict[str, Mapping[str, object]]:
    global _ENROLLMENT_DATABASE_CACHE
    if _ENROLLMENT_DATABASE_CACHE is not None:
        return _ENROLLMENT_DATABASE_CACHE
    result: dict[str, Mapping[str, object]] = {}
    for corpus in CORPORA:
        path = PRODUCT_PROTOCOL_ROOT / corpus / "evaluation" / "identity_overlays.jsonl"
        for overlay in read_jsonl(path):
            for item in overlay["enrollment_database"]:
                key = str(item["enrolled_id"])
                # database_role is overlay-local: the same enrolled identity can
                # be a live known speaker in one case and a background impostor
                # in another.  Scientific template identity is instead bound to
                # the global speaker plus exact reserved clip IDs/hashes.
                if key in result and _enrollment_identity(result[key]) != _enrollment_identity(item):
                    raise FinalHybridEvaluationError(f"conflicting held-out enrollment definition: {key}")
                result.setdefault(key, item)
    _ENROLLMENT_DATABASE_CACHE = result
    return result


def _enrollment_identity(item: Mapping[str, object]) -> object:
    return {
        "enrolled_id": item["enrolled_id"],
        "global_speaker_id": item["global_speaker_id"],
        "reserved_enrollment_clips": [
            {
                "source_clip_id": clip["source_clip_id"],
                "source_audio_sha256": clip["source_audio_sha256"],
                "logical_audio_path": clip["logical_audio_path"],
                "duration_sec": clip["duration_sec"],
            }
            for clip in item["reserved_enrollment_clips"]
        ],
    }


def _cache_index(backend: str) -> dict[str, Mapping[str, object]]:
    if backend not in _CACHE_INDICES:
        summary = read_json(CACHE_ROOT / backend / "extraction_summary.json")
        _CACHE_INDICES[backend] = {str(row["job_id"]): row for row in summary["cache_entries"]}
    return _CACHE_INDICES[backend]


def _cached(backend: str, index: Mapping[str, Mapping[str, object]], job_id: str) -> dict[str, object]:
    row = index.get(job_id)
    if row is None:
        raise FinalHybridEvaluationError(f"cache index lacks held-out job: {backend}/{job_id}")
    return load_cached(CACHE_ROOT / backend / str(row["filename"]), str(row["job_identity"]), str(row["cache_identity"]))


def _finalists() -> tuple[dict[str, object], ...]:
    global _FINALISTS_CACHE
    if _FINALISTS_CACHE is None:
        _, _FINALISTS_CACHE = require_valid_decision()
    return _FINALISTS_CACHE


def _audio_path(corpus: str, case: Mapping[str, object]) -> Path:
    path = TOOL_ROOT / "JustPeachyGeneratedData" / str(CORPORA[corpus]["generated_subdir"]) / str(case["audio_logical_path"])
    if not path.is_file():
        raise FinalHybridEvaluationError(f"held-out controlled audio missing: {path}")
    return path


def _diarization_result_root(corpus: str, pipeline: str, case_id: str) -> Path:
    return FINAL_DIARIZATION_ROOT / str(CORPORA[corpus]["diarization_scope"]) / "evaluation" / pipeline / case_id


def _valid_bundle(path: Path, finalist: Mapping[str, object], case: Mapping[str, object]) -> bool:
    try:
        sidecar = path.with_suffix(path.suffix + ".sha256")
        if not path.is_file() or not sidecar.is_file() or file_sha256(path).lower() != sidecar.read_text(encoding="utf-8").split()[0].lower():
            return False
        value = _read_gzip_json(path)
        return (
            value.get("schema_version") == "hybrid-final-score-bundle.v1"
            and value.get("status") == "SUCCEEDED"
            and value.get("combination_id") == finalist["hybrid_combination_id"]
            and value.get("case_id") == case["case_id"]
            and value.get("frozen_hybrid_selection_sha256") == file_sha256(FROZEN_HYBRID_PATH).lower()
            and value.get("evaluation_tuning_performed") is False
        )
    except Exception:
        return False


def _write_gzip_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", newline="\n", compresslevel=6) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    last_error: PermissionError | None = None
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            break
        except PermissionError as exc:
            last_error = exc
            time.sleep(min(0.5, 0.01 * (attempt + 1)))
    else:
        if last_error:
            raise last_error
    path.with_suffix(path.suffix + ".sha256").write_text(f"{file_sha256(path).lower()}  {path.name}\n", encoding="utf-8", newline="\n")


def _read_gzip_json(path: Path) -> dict[str, object]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def _write_run_authorization(frozen: Mapping[str, object], finalists: Sequence[Mapping[str, object]], cases: Mapping[str, Sequence[Mapping[str, object]]]) -> None:
    package_root = TOOL_ROOT / "app" / "hybrid_final_evaluation"
    source = [{"path": str(path.relative_to(TOOL_ROOT)), "sha256": file_sha256(path).lower()} for path in sorted(package_root.glob("*.py"))]
    atomic_json(RESULT_ROOT / "evaluation_authorization.json", {
        "schema_version": "hybrid-final-evaluation-authorization.v1",
        "authorized_at_utc": now_utc(),
        "frozen_hybrid_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
        "selected_finalists": [row["hybrid_combination_id"] for row in finalists],
        "case_counts": {key: len(value) for key, value in cases.items()},
        "source_code": source,
        "frozen_policy_mutation_after_start_forbidden": True,
        "evaluation_tuning_performed": False,
    })


def _write_native_scope_status() -> None:
    rows = []
    for finalist in _finalists():
        common = {"combination_id": finalist["hybrid_combination_id"], "diarization_pipeline_id": finalist["diarization_pipeline_id"], "identity_backend_id": finalist["identity_backend_id"]}
        rows.append({**common, "scope": "CHIME6", "status": "CHIME6_HYBRID_NOT_SCIENTIFICALLY_SUPPORTED", "reason": "Task 1 did not prove source-time/synchronized-duplicate disjointness; no native hybrid inference run."})
    from app.hybrid_final_evaluation.contracts import write_csv
    write_csv(RESULT_ROOT / "chime6_hybrid_results.csv", rows)
    voice_rows = [{"combination_id": row["hybrid_combination_id"], "scope": "VOICES FAR-FIELD IDENTITY DIAGNOSTIC", "status": "NOT_SUPPORTED", "reason": "No frozen scientifically valid VOiCES identity enrollment/probe mapping from Task 1; no unsupported metrics calculated."} for row in _finalists()]
    write_csv(RESULT_ROOT / "voices_identity_diagnostics.csv", voice_rows)


def _initialize_progress(started: float, jobs: Mapping[str, Sequence[Mapping[str, object]]], cases: Mapping[str, Sequence[Mapping[str, object]]], finalists: Sequence[Mapping[str, object]]) -> None:
    atomic_json(PROGRESS_PATH, {
        "schema_version": "hybrid-final-progress.v1",
        "started_at_epoch": started,
        "stage": "EMBEDDING_EXTRACTION",
        "current_scope": "CONTROLLED_V1",
        "current_finalist": None,
        "current_case": None,
        "overlay": None,
        "gallery_size": None,
        "embedding_backends": {backend: {"status": "PENDING", "planned_jobs": len(rows), "completed_jobs": 0, "planned_audio_sec": sum(float(row["end_sec"]) - float(row["start_sec"]) for row in rows), "completed_audio_sec": 0.0} for backend, rows in jobs.items()},
        "score_bundles": {"planned": sum(len(rows) for rows in cases.values()) * len(finalists), "completed": 0},
        "policy_replay": {"planned": 0, "completed": 0},
        "overall_percent": 0.0,
        "cache_reuse": 0,
        "failures": 0,
        "warnings": 2,
        "evaluation_tuning_performed": False,
        "updated_at_utc": now_utc(),
    })


def _refresh_progress(started: float, cases: Mapping[str, Sequence[Mapping[str, object]]], finalists: Sequence[Mapping[str, object]], current: Mapping[str, object] | None = None) -> None:
    old = read_json(PROGRESS_PATH) if PROGRESS_PATH.is_file() else {}
    backends = dict(old.get("embedding_backends") or {})
    reuse = failures = 0
    for backend in backends:
        path = RESULT_ROOT / "embedding_progress" / f"{backend}.json"
        if path.is_file():
            try:
                candidate = read_json(path)
                if int(candidate.get("planned_jobs") or -1) == int(dict(backends[backend]).get("planned_jobs") or -2):
                    backends[backend] = candidate
            except Exception:
                pass
        summary = CACHE_ROOT / backend / "extraction_summary.json"
        if summary.is_file():
            value = read_json(summary)
            reuse += int(value.get("reused") or 0)
            failures += int(value.get("failed") or 0)
    planned_bundles = sum(len(rows) for rows in cases.values()) * len(finalists)
    completed_bundles = sum(1 for path in SCORE_ROOT.glob("*/*/*.json.gz") if path.with_suffix(path.suffix + ".sha256").is_file())
    planned_audio = sum(float(row.get("planned_audio_sec") or 0.0) for row in backends.values())
    completed_audio = sum(float(row.get("completed_audio_sec") or 0.0) for row in backends.values())
    embed_fraction = completed_audio / planned_audio if planned_audio else 0.0
    bundle_fraction = completed_bundles / planned_bundles if planned_bundles else 0.0
    replay = dict(old.get("policy_replay") or {})
    replay_fraction = float(replay.get("completed") or 0) / float(replay.get("planned") or 1) if replay.get("planned") else 0.0
    overall = 70.0 * embed_fraction + 20.0 * bundle_fraction + 10.0 * replay_fraction
    elapsed = time.time() - started
    measured = 0.7 * embed_fraction + 0.2 * bundle_fraction
    eta = elapsed * (0.9 - measured) / measured if 0.02 < measured < 0.9 else None
    scope = "CONTROLLED_V1" if current and current.get("corpus") == "v1" else "CONTROLLED_V2" if current else old.get("current_scope")
    atomic_json(PROGRESS_PATH, {
        **old,
        "stage": "SCORE_BUNDLES" if backends and all(row.get("status") == "COMPLETE" for row in backends.values()) else "EMBEDDING_EXTRACTION",
        "current_scope": scope,
        "current_finalist": current.get("combination_id") if current else old.get("current_finalist"),
        "current_case": current.get("case_id") if current else old.get("current_case"),
        "embedding_backends": backends,
        "score_bundles": {"planned": planned_bundles, "completed": completed_bundles},
        "overall_percent": overall,
        "elapsed_sec": elapsed,
        "eta_sec": eta,
        "cache_reuse": reuse,
        "failures": failures,
        "updated_at_utc": now_utc(),
    })


def update_analysis_progress(completed: int, planned: int, *, scope: str, finalist: str | None, case_id: str | None, overlay: str | None, gallery_size: object | None, stage: str = "ANALYSIS") -> None:
    progress = read_json(PROGRESS_PATH) if PROGRESS_PATH.is_file() else {}
    progress.update({
        "stage": stage,
        "current_scope": scope,
        "current_finalist": finalist,
        "current_case": case_id,
        "overlay": overlay,
        "gallery_size": gallery_size,
        "policy_replay": {"planned": planned, "completed": completed},
        "overall_percent": 90.0 + 10.0 * (completed / planned if planned else 1.0),
        "updated_at_utc": now_utc(),
    })
    atomic_json(PROGRESS_PATH, progress)


def set_controller(status_value: str, stage: str, detail: str) -> None:
    _state(status_value, stage, detail)


def _state(status_value: str, stage: str, detail: str) -> None:
    atomic_json(STATE_PATH, {"schema_version": "hybrid-final-controller.v1", "status": status_value, "stage": stage, "detail": detail, "pid": os.getpid(), "updated_at_utc": now_utc(), "evaluation_tuning_performed": False})


def _prediction_job_id(corpus: str, pipeline: str, case_id: str, index: int) -> str:
    return f"evaluation__{corpus}__{pipeline}__{case_id}__pred_{index:04d}"


def _reference_job_id(corpus: str, case_id: str, index: int) -> str:
    return f"evaluation__{corpus}__{case_id}__oracle_{index:04d}"


def _enrollment_job_id(enrolled_id: str, clip_id: str) -> str:
    return f"evaluation_enroll__{enrolled_id}__{clip_id}"


def _normal(value: object) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if not math.isfinite(norm) or norm <= 0:
        raise FinalHybridEvaluationError("non-normalizable held-out embedding")
    return array / norm


def _active_band(count: int) -> str:
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 5:
        return "3-5"
    if count <= 8:
        return "6-8"
    return "9-12"


def _counts(values: Iterable[str]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for value in values:
        result[value] += 1
    return dict(result)
