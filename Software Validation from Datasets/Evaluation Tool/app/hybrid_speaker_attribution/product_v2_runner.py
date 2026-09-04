"""Restart-safe embedding extraction and score-bundle generation for Hybrid Product V2."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
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
import yaml

from app.controlled_diarization.runner import interpreter_for_profile
from app.diarization_evaluation.formats import parse_rttm
from app.hybrid_speaker_attribution.embedding_cache import embedding_job, load_cached
from app.hybrid_speaker_attribution.product_v2_contracts import (
    BACKEND_MINIMUM_SEC, COMBINATIONS, EVIDENCE_CHECKPOINTS_SEC, POLICY_ROOT,
    PRODUCT_PROTOCOL_ROOT, RESULT_ROOT, TOOL_ROOT, UPSTREAM_DIARIZATION_ROOT,
    V1_BENCHMARK_ROOT, V2_BENCHMARK_ROOT, ProductV2Error, atomic_json,
    file_sha256, now_utc, read_json, read_jsonl, write_jsonl,
)
from app.speaker_protocol.contracts import eligible_embedding_backends
from app.utils.paths import resolve_data_path_from_logical


CACHE_ROOT = RESULT_ROOT / "_embedding_cache"
SCORE_ROOT = RESULT_ROOT / "score_bundles"
STOP_PATH = RESULT_ROOT / "STOP_REQUESTED"
PROGRESS_PATH = RESULT_ROOT / "campaign_progress.json"
STATE_PATH = RESULT_ROOT / "controller_state.json"
_BACKEND_EXTRACTION_TOTALS: dict[str, float] = {}
_CACHE_INDICES: dict[str, dict[str, Mapping[str, object]]] = {}
_TEMPLATE_CACHE: dict[str, dict[str, dict[str, object]]] = {}
_ENROLLMENT_DATABASE_CACHE: dict[str, Mapping[str, object]] | None = None


def run_development(*, parallel_backends: int = 2, max_cases: int | None = None) -> dict[str, object]:
    """Run all missing development embeddings and score bundles; never reads evaluation results."""

    from app.hybrid_speaker_attribution.product_v2_protocol import audit, plan, prepare, validate

    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    STOP_PATH.unlink(missing_ok=True)
    started = time.time()
    _state("RUNNING", "AUDIT", "Validating frozen upstream inputs")
    if audit()["status"] != "PASS":
        raise ProductV2Error("upstream audit failed")
    if not (PRODUCT_PROTOCOL_ROOT / "protocol_summary.json").is_file():
        prepare()
    validate()
    plan()
    combinations = list(COMBINATIONS)
    cases_by_corpus = _cases(max_cases)
    jobs_by_backend = {backend: _build_jobs(backend, combinations, cases_by_corpus) for backend in sorted({str(row["identity_backend_id"]) for row in combinations})}
    _initialize_progress(started, jobs_by_backend, cases_by_corpus, combinations)
    _state("RUNNING", "EMBEDDING_EXTRACTION", "Independent identity-backend embedding extraction")
    errors = []
    with ThreadPoolExecutor(max_workers=max(1, min(parallel_backends, len(jobs_by_backend)))) as executor:
        futures = {executor.submit(_extract_backend, backend, jobs): backend for backend, jobs in jobs_by_backend.items()}
        while futures:
            done = [future for future in futures if future.done()]
            for future in done:
                backend = futures.pop(future)
                try:
                    future.result()
                except Exception as exc:
                    errors.append({"backend": backend, "error": f"{type(exc).__name__}: {exc}"})
            _refresh_progress(started, cases_by_corpus, combinations)
            if STOP_PATH.exists():
                _state("STOPPING", "EMBEDDING_EXTRACTION", "Graceful stop requested; active backend workers will finish their current jobs")
            if futures:
                time.sleep(2)
    if errors:
        _state("FAILED", "EMBEDDING_EXTRACTION", json.dumps(errors))
        raise ProductV2Error(f"embedding extraction failed: {errors}")
    if STOP_PATH.exists():
        _state("STOPPED", "EMBEDDING_EXTRACTION", "Stopped after completing active extraction workers")
        return status()
    _state("RUNNING", "SCORE_BUNDLES", "Generating restart-safe case score bundles")
    score_units = [
        {"combination_id": combination["combination_id"], "corpus": corpus, "case_id": case["case_id"]}
        for combination in combinations
        for corpus, cases in cases_by_corpus.items()
        for case in cases
    ]
    failed_units = _execute_score_worker_batches(score_units)
    atomic_json(RESULT_ROOT / "score_bundle_failures.json", {"schema_version": "hybrid-product-v2-failures.v1", "failures": failed_units})
    if failed_units:
        _state("FAILED", "SCORE_BUNDLES", f"{len(failed_units)} score bundles failed")
        raise ProductV2Error(f"{len(failed_units)} score bundles failed")
    _state("SCORES_COMPLETE", "POLICY_REPLAY_PENDING", "All independent embeddings and case score bundles are complete")
    _refresh_progress(started, cases_by_corpus, combinations)
    return status()


def _execute_score_worker_batches(units: Sequence[Mapping[str, object]], batch_size: int = 8) -> list[dict[str, object]]:
    """Bound Windows process lifetime while preserving per-case atomic reuse."""

    failures = []
    for offset in range(0, len(units), batch_size):
        if STOP_PATH.exists():
            break
        batch = list(units[offset: offset + batch_size])
        completed = _invoke_score_worker(batch, f"batch_{offset // batch_size:04d}")
        if completed["returncode"] == 0:
            continue
        # Isolate a bad case instead of invalidating the entire eight-case batch.
        for unit in batch:
            isolated = _invoke_score_worker([unit], f"isolated_{unit['combination_id']}_{unit['corpus']}_{unit['case_id']}")
            if isolated["returncode"] != 0:
                failures.append({**dict(unit), "error": str(isolated["stderr"] or isolated["stdout"])[-3000:]})
    return failures


def _invoke_score_worker(units: Sequence[Mapping[str, object]], label: str) -> dict[str, object]:
    manifest = RESULT_ROOT / "score_worker_manifests" / f".{label}.{uuid.uuid4().hex[:8]}.json"
    atomic_json(manifest, {"schema_version": "hybrid-product-v2-score-worker-manifest.v1", "units": list(units)})
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "app.hybrid_speaker_attribution.product_v2_score_worker", "--manifest", str(manifest)],
            cwd=TOOL_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            timeout=600,
        )
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"returncode": 124, "stdout": exc.stdout or "", "stderr": f"score worker timed out after 600 seconds: {exc.stderr or ''}"}
    finally:
        manifest.unlink(missing_ok=True)


def stop() -> dict[str, object]:
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    STOP_PATH.write_text(f"requested_at_utc={now_utc()}\n", encoding="utf-8")
    return {"status": "STOP_REQUESTED", "path": str(STOP_PATH), "policy": "finish active embedding workers or current score unit, then stop"}


def status() -> dict[str, object]:
    state = read_json(STATE_PATH) if STATE_PATH.is_file() else {"status": "NOT_STARTED", "stage": "NONE"}
    progress = read_json(PROGRESS_PATH) if PROGRESS_PATH.is_file() else {}
    return {"schema_version": "hybrid-product-v2-status.v1", "controller": state, "progress": progress, "result_root": str(RESULT_ROOT), "stop_requested": STOP_PATH.exists()}


def validate_score_bundles() -> dict[str, object]:
    errors = []
    counts = defaultdict(int)
    for path in SCORE_ROOT.glob("*/*/*.json.gz"):
        sha_path = path.with_suffix(path.suffix + ".sha256")
        observed = file_sha256(path).lower()
        expected = sha_path.read_text(encoding="utf-8").strip().split()[0] if sha_path.is_file() else ""
        try:
            value = _read_gzip_json(path)
            if observed != expected or value.get("status") != "SUCCEEDED":
                raise ProductV2Error("checksum/status mismatch")
            counts[str(value["combination_id"])] += 1
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})
    return {"status": "PASS" if not errors else "FAIL", "counts": dict(counts), "errors": errors}


def score_bundle_path(combination_id: str, corpus: str, case_id: str) -> Path:
    return SCORE_ROOT / combination_id / corpus / f"{case_id}.json.gz"


def load_score_bundle(combination_id: str, corpus: str, case_id: str) -> dict[str, object]:
    path = score_bundle_path(combination_id, corpus, case_id)
    sha = path.with_suffix(path.suffix + ".sha256")
    if not path.is_file() or not sha.is_file() or file_sha256(path).lower() != sha.read_text(encoding="utf-8").strip().split()[0]:
        raise ProductV2Error(f"invalid score bundle: {path}")
    return _read_gzip_json(path)


def _cases(max_cases: int | None) -> dict[str, list[dict[str, object]]]:
    result = {
        "v1": read_jsonl(V1_BENCHMARK_ROOT / "development" / "case_manifest.jsonl"),
        "v2": read_jsonl(V2_BENCHMARK_ROOT / "development" / "case_manifest.jsonl"),
    }
    if max_cases is not None:
        return {key: rows[:max_cases] for key, rows in result.items()}
    return result


def _build_jobs(backend: str, combinations: Sequence[Mapping[str, object]], cases_by_corpus: Mapping[str, Sequence[Mapping[str, object]]]) -> list[dict[str, object]]:
    jobs: list[dict[str, object]] = []
    relevant_pipelines = {str(row["diarization_pipeline_id"]) for row in combinations if row["identity_backend_id"] == backend}
    enrollment = _enrollment_database()
    policy = _load_policy(backend)
    for item in enrollment.values():
        for clip in list(item["reserved_enrollment_clips"])[: int(policy["enrollment_utterance_count"])]:
            jobs.append(embedding_job(
                job_id=_enrollment_job_id(str(item["enrolled_id"]), str(clip["source_clip_id"])),
                audio_path=resolve_data_path_from_logical(str(clip["logical_audio_path"])),
                audio_sha256=str(clip["source_audio_sha256"]), start_sec=0.0,
                end_sec=float(clip["duration_sec"]), role="reserved_scientific_enrollment",
                metadata={"enrolled_id": item["enrolled_id"], "global_speaker_id": item["global_speaker_id"]},
            ))
    for corpus, cases in cases_by_corpus.items():
        benchmark = V1_BENCHMARK_ROOT if corpus == "v1" else V2_BENCHMARK_ROOT
        for case in cases:
            audio = _audio_path(corpus, case)
            for index, turn in enumerate(parse_rttm(benchmark / str(case["reference_rttm_path"]))):
                jobs.append(embedding_job(
                    job_id=_reference_job_id(corpus, str(case["case_id"]), index), audio_path=audio,
                    audio_sha256=str(case["audio_sha256"]), start_sec=float(turn.start_sec),
                    end_sec=float(turn.start_sec + turn.duration_sec), role="oracle_reference_turn",
                    metadata={"corpus": corpus, "case_id": case["case_id"], "speaker_label": turn.speaker_label},
                ))
            for pipeline in relevant_pipelines:
                result = UPSTREAM_DIARIZATION_ROOT / corpus / "development" / pipeline / str(case["case_id"])
                _validate_diarization_result(result, pipeline, case)
                for index, turn in enumerate(parse_rttm(result / "predictions" / "segments.rttm")):
                    jobs.append(embedding_job(
                        job_id=_prediction_job_id(corpus, pipeline, str(case["case_id"]), index),
                        audio_path=audio, audio_sha256=str(case["audio_sha256"]),
                        start_sec=float(turn.start_sec), end_sec=float(turn.start_sec + turn.duration_sec),
                        role="independent_identity_predicted_segment",
                        metadata={"corpus": corpus, "case_id": case["case_id"], "pipeline_id": pipeline, "cluster_id": turn.speaker_label},
                    ))
    unique = {str(row["job_identity"]): row for row in jobs}
    rows = sorted(unique.values(), key=lambda row: str(row["job_id"]))
    manifest = RESULT_ROOT / "cache_inventory" / f"{backend}.jobs.jsonl"
    write_jsonl(manifest, rows)
    atomic_json(manifest.with_suffix(".summary.json"), {"schema_version": "hybrid-product-v2-job-inventory.v1", "backend_id": backend, "jobs": len(rows), "audio_sec": sum(float(row["end_sec"]) - float(row["start_sec"]) for row in rows), "roles": dict(_counts(str(row["role"]) for row in rows)), "manifest_sha256": file_sha256(manifest).lower()})
    return rows


def _extract_backend(backend: str, jobs: Sequence[Mapping[str, object]]) -> dict[str, object]:
    eligible = eligible_embedding_backends(backend_ids={backend})
    if backend not in eligible:
        raise ProductV2Error(f"qualified backend unavailable: {backend}")
    interpreter = interpreter_for_profile(str(eligible[backend]["environment_profile"]))
    if interpreter is None or not interpreter.is_file():
        raise ProductV2Error(f"backend environment unavailable: {backend}")
    manifest = RESULT_ROOT / "cache_inventory" / f"{backend}.jobs.jsonl"
    progress = RESULT_ROOT / "embedding_progress" / f"{backend}.json"
    progress.parent.mkdir(parents=True, exist_ok=True)
    shard_count = 2 if backend == "wespeaker" and len(jobs) >= 1000 else 1
    shard_results = []
    if shard_count == 1:
        shard_results.append(_run_embedding_process(interpreter, backend, manifest, progress, "full"))
    else:
        shard_manifests = []
        for shard in range(shard_count):
            shard_manifest = RESULT_ROOT / "cache_inventory" / f"{backend}.shard{shard}.jobs.jsonl"
            write_jsonl(shard_manifest, jobs[shard::shard_count])
            shard_manifests.append(shard_manifest)
        with ThreadPoolExecutor(max_workers=shard_count) as shard_executor:
            shard_futures = {
                shard_executor.submit(
                    _run_embedding_process, interpreter, backend, shard_manifest,
                    RESULT_ROOT / "embedding_progress" / f"{backend}.shard{shard}.json", f"shard{shard}",
                ): shard
                for shard, shard_manifest in enumerate(shard_manifests)
            }
            while shard_futures:
                for future in [item for item in shard_futures if item.done()]:
                    shard_results.append(future.result())
                    shard_futures.pop(future)
                _aggregate_shard_progress(backend, shard_count, len(jobs), progress)
                if shard_futures:
                    time.sleep(1)
        # A cache-only full pass publishes one authoritative complete index after
        # the disjoint workers finish. It performs no neural inference.
        shard_results.append(_run_embedding_process(interpreter, backend, manifest, progress, "consolidate"))
    failed = [row for row in shard_results if int(row["returncode"]) != 0]
    (RESULT_ROOT / "logs").mkdir(parents=True, exist_ok=True)
    (RESULT_ROOT / "logs" / f"{backend}.stdout.log").write_text("\n".join(str(row["stdout"]) for row in shard_results), encoding="utf-8", errors="replace")
    (RESULT_ROOT / "logs" / f"{backend}.stderr.log").write_text("\n".join(str(row["stderr"]) for row in shard_results), encoding="utf-8", errors="replace")
    if failed:
        message = str(failed[0]["stderr"] or failed[0]["stdout"])[-2000:]
        raise ProductV2Error(f"{backend} embedding worker exited {failed[0]['returncode']}: {message}")
    summary = read_json(CACHE_ROOT / backend / "extraction_summary.json")
    if not summary.get("backend_identity"):
        raise ProductV2Error(f"{backend} produced no valid embeddings")
    return summary


def _run_embedding_process(interpreter: Path, backend: str, manifest: Path, progress: Path, label: str) -> dict[str, object]:
    completed = subprocess.run(
        [str(interpreter), "-m", "app.hybrid_speaker_attribution.embedding_cache", "--backend", backend,
         "--jobs", str(manifest), "--cache-root", str(CACHE_ROOT), "--progress-path", str(progress)],
        cwd=TOOL_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    return {"label": label, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def _aggregate_shard_progress(backend: str, shard_count: int, planned_jobs: int, destination: Path) -> None:
    rows = []
    for shard in range(shard_count):
        path = RESULT_ROOT / "embedding_progress" / f"{backend}.shard{shard}.json"
        if path.is_file():
            try:
                rows.append(read_json(path))
            except Exception:
                pass
    if not rows:
        return
    planned_audio = sum(float(row.get("planned_audio_sec") or 0.0) for row in rows)
    atomic_json(destination, {"schema_version": "hybrid-embedding-progress.v1", "backend_id": backend, "status": "COMPLETE" if len(rows) == shard_count and all(row.get("status") == "COMPLETE" for row in rows) else "RUNNING", "completed_jobs": sum(int(row.get("completed_jobs") or 0) for row in rows), "planned_jobs": planned_jobs, "completed_audio_sec": sum(float(row.get("completed_audio_sec") or 0.0) for row in rows), "planned_audio_sec": planned_audio, "current_job_id": ";".join(str(row.get("current_job_id") or "") for row in rows), "failures": sum(int(row.get("failures") or 0) for row in rows), "shards": shard_count, "updated_at_epoch": time.time()})


def _score_case(combination: Mapping[str, object], corpus: str, case: Mapping[str, object]) -> None:
    combination_id = str(combination["combination_id"])
    destination = score_bundle_path(combination_id, corpus, str(case["case_id"]))
    if _valid_bundle(destination, combination, case):
        return
    backend = str(combination["identity_backend_id"])
    pipeline = str(combination["diarization_pipeline_id"])
    policy = _load_policy(backend)
    cache = _cache_index(backend)
    result_root = UPSTREAM_DIARIZATION_ROOT / corpus / "development" / pipeline / str(case["case_id"])
    benchmark = V1_BENCHMARK_ROOT if corpus == "v1" else V2_BENCHMARK_ROOT
    predictions = []
    for index, turn in enumerate(parse_rttm(result_root / "predictions" / "segments.rttm")):
        item = _cached(backend, cache, _prediction_job_id(corpus, pipeline, str(case["case_id"]), index))
        predictions.append({"segment_id": f"pred_{index:04d}", "start_sec": float(turn.start_sec), "end_sec": float(turn.start_sec + turn.duration_sec), "duration_sec": float(turn.duration_sec), "cluster_id": str(turn.speaker_label), "embedding_status": item["status"], "vector": item["vector"], "predicted_overlap": False})
    for row in predictions:
        row["predicted_overlap"] = any(other is not row and other["cluster_id"] != row["cluster_id"] and _overlap(row, other) > 0 for other in predictions)
    references = []
    for index, turn in enumerate(parse_rttm(benchmark / str(case["reference_rttm_path"]))):
        references.append({"segment_id": f"ref_{index:04d}", "start_sec": float(turn.start_sec), "end_sec": float(turn.start_sec + turn.duration_sec), "duration_sec": float(turn.duration_sec), "speaker_label": str(turn.speaker_label), "global_speaker_id": str(dict(case["local_to_global_speaker"])[str(turn.speaker_label)])})
    templates = _templates(backend, cache, policy)
    clusters = []
    for cluster_id in sorted({str(row["cluster_id"]) for row in predictions}, key=lambda value: min(float(row["start_sec"]) for row in predictions if row["cluster_id"] == value)):
        segments = sorted((row for row in predictions if row["cluster_id"] == cluster_id), key=lambda row: (float(row["end_sec"]), str(row["segment_id"])))
        reference_overlap = defaultdict(float)
        for segment in segments:
            for reference in references:
                reference_overlap[str(reference["global_speaker_id"])] += _overlap(segment, reference)
        events = _cluster_events([row for row in segments if not row["predicted_overlap"]], templates, policy)
        events_include_overlap = _cluster_events(segments, templates, policy)
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
            "events": events,
            "events_include_predicted_overlap_diagnostic": events_include_overlap,
        })
    diar_identity = read_json(result_root / "resolved_pipeline_identity.json")
    extraction = read_json(CACHE_ROOT / backend / "extraction_summary.json")
    payload = {
        "schema_version": "hybrid-product-v2-score-bundle.v2",
        "status": "SUCCEEDED",
        "created_at_utc": now_utc(),
        "combination_id": combination_id,
        "corpus": corpus,
        "case_id": case["case_id"],
        "benchmark_id": case["benchmark_id"],
        "protocol_id": read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")["protocol_id"],
        "development_role": case.get("development_role") or ("calibration" if int(hashlib.sha256(str(case["case_id"]).encode()).hexdigest()[:8], 16) % 5 == 0 else "selection"),
        "speaker_count": case["speaker_count"],
        "active_speaker_band": _active_band(int(case["speaker_count"])),
        "duration_sec": case["duration_sec"],
        "diarization_pipeline_id": pipeline,
        "diarization_configuration_sha256": diar_identity.get("configuration_sha256") or diar_identity.get("pipeline_configuration_sha256"),
        "identity_backend_id": backend,
        "identity_backend_identity": extraction["backend_identity"],
        "enrollment_policy_id": policy["policy_id"],
        "enrollment_policy_sha256": file_sha256(POLICY_ROOT / f"{backend}.scientific.yaml").lower(),
        "independent_identity_reembedding": True,
        "same_model_reuse_used_for_primary": False,
        "references": references,
        "predictions": [{key: value for key, value in row.items() if key != "vector"} for row in predictions],
        "clusters": clusters,
        "resource": _resource_row(predictions, backend, cache, float(case["duration_sec"]), result_root),
        "evaluation_results_inspected": False,
        "xvf_available": False,
    }
    _write_gzip_json(destination, payload)


def _cluster_events(segments: Sequence[Mapping[str, object]], templates: Mapping[str, Mapping[str, object]], policy: Mapping[str, object]) -> list[dict[str, object]]:
    usable = [row for row in segments if row["embedding_status"] == "ok"]
    events = []
    for checkpoint in EVIDENCE_CHECKPOINTS_SEC:
        chosen = _prefix(usable, checkpoint)
        if checkpoint < float(policy["technical_minimum_evidence_sec"]):
            events.append({"checkpoint_sec": checkpoint, "status": "TECHNICALLY_INVALID", "evidence_sec": 0.0, "observation_end_sec": None, "scores": {}, "embedding_consistency": None})
            continue
        if not chosen:
            events.append({"checkpoint_sec": checkpoint, "status": "INSUFFICIENT_VALID_EMBEDDINGS", "evidence_sec": 0.0, "observation_end_sec": None, "scores": {}, "embedding_consistency": None})
            continue
        aggregate = _aggregate(chosen)
        scores = {enrolled_id: _template_score(aggregate, value["vectors"], str(policy["aggregation_method"])) for enrolled_id, value in templates.items() if value["vectors"]}
        consistency = float(np.mean([float(np.dot(aggregate, _normal(row["vector"]))) for row in chosen]))
        events.append({"checkpoint_sec": checkpoint, "status": "VALID", "evidence_sec": sum(float(row["duration_sec"]) for row in chosen), "observation_end_sec": max(float(row["end_sec"]) for row in chosen), "scores": scores, "embedding_consistency": consistency})
    if usable:
        aggregate = _aggregate(usable)
        scores = {enrolled_id: _template_score(aggregate, value["vectors"], str(policy["aggregation_method"])) for enrolled_id, value in templates.items() if value["vectors"]}
        events.append({"checkpoint_sec": "full", "status": "VALID", "evidence_sec": sum(float(row["duration_sec"]) for row in usable), "observation_end_sec": max(float(row["end_sec"]) for row in usable), "scores": scores, "embedding_consistency": float(np.mean([float(np.dot(aggregate, _normal(row["vector"]))) for row in usable]))})
    return events


def _templates(backend: str, cache: Mapping[str, Mapping[str, object]], policy: Mapping[str, object]) -> dict[str, dict[str, object]]:
    if backend in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[backend]
    result = {}
    for enrolled_id, item in _enrollment_database().items():
        vectors = []
        clip_ids = []
        for clip in list(item["reserved_enrollment_clips"])[: int(policy["enrollment_utterance_count"])]:
            cached = _cached(backend, cache, _enrollment_job_id(str(enrolled_id), str(clip["source_clip_id"])))
            if cached["status"] == "ok":
                vectors.append(_normal(cached["vector"]))
                clip_ids.append(str(clip["source_clip_id"]))
        result[enrolled_id] = {"global_speaker_id": item["global_speaker_id"], "vectors": vectors, "source_clip_ids": clip_ids}
    _TEMPLATE_CACHE[backend] = result
    return result


def _cache_index(backend: str) -> dict[str, Mapping[str, object]]:
    if backend in _CACHE_INDICES:
        return _CACHE_INDICES[backend]
    summary = read_json(CACHE_ROOT / backend / "extraction_summary.json")
    _CACHE_INDICES[backend] = {str(row["job_id"]): row for row in summary["cache_entries"]}
    return _CACHE_INDICES[backend]


def _cached(backend: str, index: Mapping[str, Mapping[str, object]], job_id: str) -> dict[str, object]:
    row = index.get(job_id)
    if row is None:
        raise ProductV2Error(f"cache index lacks job: {backend}/{job_id}")
    return load_cached(CACHE_ROOT / backend / str(row["filename"]), str(row["job_identity"]), str(row["cache_identity"]))


def _enrollment_database() -> dict[str, Mapping[str, object]]:
    global _ENROLLMENT_DATABASE_CACHE
    if _ENROLLMENT_DATABASE_CACHE is not None:
        return _ENROLLMENT_DATABASE_CACHE
    result = {}
    for row in read_jsonl(PRODUCT_PROTOCOL_ROOT / "v1" / "development" / "identity_overlays.jsonl"):
        for item in row["enrollment_database"]:
            result[str(item["enrolled_id"])] = item
    _ENROLLMENT_DATABASE_CACHE = result
    return result


def _load_policy(backend: str) -> dict[str, object]:
    return yaml.safe_load((POLICY_ROOT / f"{backend}.scientific.yaml").read_text(encoding="utf-8"))


def _audio_path(corpus: str, case: Mapping[str, object]) -> Path:
    root = TOOL_ROOT / "JustPeachyGeneratedData" / ("controlled_diarization_v1" if corpus == "v1" else "diarization_product_v2")
    path = root / str(case["audio_logical_path"])
    if not path.is_file():
        raise ProductV2Error(f"controlled audio missing: {path}")
    return path


def _validate_diarization_result(root: Path, pipeline: str, case: Mapping[str, object]) -> None:
    run = read_json(root / "run.json")
    if run.get("status") != "succeeded" or run.get("pipeline_id") != pipeline or run.get("case_id") != case["case_id"] or run.get("benchmark_audio_sha256", "").lower() != str(case["audio_sha256"]).lower():
        raise ProductV2Error(f"invalid frozen diarization result: {root}")
    if not (root / "predictions" / "segments.rttm").is_file():
        raise ProductV2Error(f"frozen diarization segments missing: {root}")


def _resource_row(predictions: Sequence[Mapping[str, object]], backend: str, cache: Mapping[str, Mapping[str, object]], duration: float, result_root: Path) -> dict[str, object]:
    diar = read_json(result_root / "run.json")
    inventory = read_json(RESULT_ROOT / "cache_inventory" / f"{backend}.jobs.summary.json")
    backend_audio = float(inventory["audio_sec"])
    if backend not in _BACKEND_EXTRACTION_TOTALS:
        total_path = RESULT_ROOT / "cache_inventory" / f"{backend}.extraction_total.json"
        if total_path.is_file():
            _BACKEND_EXTRACTION_TOTALS[backend] = float(read_json(total_path)["extraction_sec"])
        else:
            backend_summary = read_json(CACHE_ROOT / backend / "extraction_summary.json")
            _BACKEND_EXTRACTION_TOTALS[backend] = sum(
                float(load_cached(CACHE_ROOT / backend / str(entry["filename"])).get("extraction_sec") or 0.0)
                for entry in backend_summary["cache_entries"]
            )
            atomic_json(total_path, {"schema_version": "hybrid-product-v2-extraction-total.v1", "backend_id": backend, "extraction_sec": _BACKEND_EXTRACTION_TOTALS[backend], "jobs": len(backend_summary["cache_entries"])})
    backend_total = _BACKEND_EXTRACTION_TOTALS[backend]
    apportioned = backend_total * duration / backend_audio if backend_audio else 0.0
    diar_timing = dict(diar.get("timing") or {})
    peak = dict(diar.get("resource_telemetry") or {}).get("peak_rss_mb")
    return {"identity_embedding_sec_apportioned": apportioned, "identity_rtf_apportioned": apportioned / duration if duration else None, "diarization_sec": diar_timing.get("diarization_inference_sec"), "diarization_rtf": diar_timing.get("real_time_factor"), "total_rtf": (float(diar_timing.get("diarization_inference_sec") or 0.0) + apportioned) / duration if duration else None, "peak_rss_mb": peak, "asr_runtime_sec": 0.0}


def _valid_bundle(path: Path, combination: Mapping[str, object], case: Mapping[str, object]) -> bool:
    try:
        sha = path.with_suffix(path.suffix + ".sha256")
        if not path.is_file() or not sha.is_file() or file_sha256(path).lower() != sha.read_text(encoding="utf-8").strip().split()[0]:
            return False
        value = _read_gzip_json(path)
        return value.get("schema_version") == "hybrid-product-v2-score-bundle.v2" and value.get("status") == "SUCCEEDED" and value.get("combination_id") == combination["combination_id"] and value.get("case_id") == case["case_id"] and value.get("evaluation_results_inspected") is False
    except Exception:
        return False


def _write_gzip_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", newline="\n", compresslevel=6) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(temporary, path)
    path.with_suffix(path.suffix + ".sha256").write_text(f"{file_sha256(path).lower()}  {path.name}\n", encoding="utf-8", newline="\n")


def _read_gzip_json(path: Path) -> dict[str, object]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def _initialize_progress(started: float, jobs: Mapping[str, Sequence[Mapping[str, object]]], cases: Mapping[str, Sequence[Mapping[str, object]]], combinations: Sequence[Mapping[str, object]]) -> None:
    atomic_json(PROGRESS_PATH, {"schema_version": "hybrid-product-v2-progress.v1", "started_at_epoch": started, "stage": "EMBEDDING_EXTRACTION", "embedding_backends": {backend: {"planned_jobs": len(rows), "planned_audio_sec": sum(float(row["end_sec"]) - float(row["start_sec"]) for row in rows), "completed_jobs": 0, "completed_audio_sec": 0.0, "status": "PENDING"} for backend, rows in jobs.items()}, "score_bundles": {"planned": sum(len(rows) for rows in cases.values()) * len(combinations), "completed": 0}, "policy_replay": {"planned": sum(len(rows) for rows in cases.values()) * len(combinations) * 3, "completed": 0}, "overall_percent": 0.0, "evaluation_run": False, "updated_at_utc": now_utc()})


def _refresh_progress(started: float, cases: Mapping[str, Sequence[Mapping[str, object]]], combinations: Sequence[Mapping[str, object]]) -> None:
    old = read_json(PROGRESS_PATH) if PROGRESS_PATH.is_file() else {}
    backends = dict(old.get("embedding_backends") or {})
    for backend in backends:
        path = RESULT_ROOT / "embedding_progress" / f"{backend}.json"
        if path.is_file():
            try:
                candidate = read_json(path)
                if int(candidate.get("planned_jobs") or -1) == int(dict(backends[backend]).get("planned_jobs") or -2):
                    backends[backend] = candidate
            except Exception:
                pass
    planned_bundles = sum(len(rows) for rows in cases.values()) * len(combinations)
    completed_bundles = sum(1 for path in SCORE_ROOT.glob("*/*/*.json.gz") if path.with_suffix(path.suffix + ".sha256").is_file())
    planned_audio = sum(float(row.get("planned_audio_sec") or 0.0) for row in backends.values())
    completed_audio = sum(float(row.get("completed_audio_sec") or 0.0) for row in backends.values())
    embed_fraction = completed_audio / planned_audio if planned_audio else 0.0
    bundle_fraction = completed_bundles / planned_bundles if planned_bundles else 0.0
    overall = 70.0 * embed_fraction + 20.0 * bundle_fraction + 10.0 * float(dict(old.get("policy_replay") or {}).get("fraction") or 0.0)
    status_values = [str(row.get("status", "PENDING")) for row in backends.values()]
    stage = "SCORE_BUNDLES" if status_values and all(value == "COMPLETE" for value in status_values) else "EMBEDDING_EXTRACTION"
    elapsed = time.time() - started
    measured_fraction = (0.7 * embed_fraction + 0.2 * bundle_fraction)
    eta = elapsed * (0.9 - measured_fraction) / measured_fraction if measured_fraction > 0.02 and measured_fraction < 0.9 else None
    atomic_json(PROGRESS_PATH, {**old, "stage": stage, "embedding_backends": backends, "score_bundles": {"planned": planned_bundles, "completed": completed_bundles, "fraction": bundle_fraction}, "overall_percent": overall, "elapsed_sec": elapsed, "eta_sec": eta, "updated_at_utc": now_utc()})


def update_replay_progress(completed: int, planned: int, detail: str) -> None:
    progress = read_json(PROGRESS_PATH) if PROGRESS_PATH.is_file() else {}
    fraction = completed / planned if planned else 1.0
    progress["stage"] = "POLICY_REPLAY"
    progress["policy_replay"] = {"planned": planned, "completed": completed, "fraction": fraction, "detail": detail}
    progress["overall_percent"] = 90.0 + 10.0 * fraction
    progress["updated_at_utc"] = now_utc()
    atomic_json(PROGRESS_PATH, progress)


def set_controller(status_value: str, stage: str, detail: str) -> None:
    _state(status_value, stage, detail)


def _state(status_value: str, stage: str, detail: str) -> None:
    atomic_json(STATE_PATH, {"schema_version": "hybrid-product-v2-controller.v1", "status": status_value, "stage": stage, "detail": detail, "pid": os.getpid(), "updated_at_utc": now_utc(), "evaluation_run": False})


def _prediction_job_id(corpus: str, pipeline: str, case_id: str, index: int) -> str:
    return f"{corpus}__{pipeline}__{case_id}__pred_{index:04d}"


def _reference_job_id(corpus: str, case_id: str, index: int) -> str:
    return f"{corpus}__{case_id}__oracle_{index:04d}"


def _enrollment_job_id(enrolled_id: str, clip_id: str) -> str:
    return f"enroll__{enrolled_id}__{clip_id}"


def _prefix(rows: Sequence[Mapping[str, object]], budget: float) -> list[Mapping[str, object]]:
    chosen = []
    total = 0.0
    for row in rows:
        chosen.append(row)
        total += float(row["duration_sec"])
        if total >= budget:
            break
    return chosen


def _aggregate(rows: Sequence[Mapping[str, object]]) -> np.ndarray:
    vectors = np.asarray([_normal(row["vector"]) for row in rows], dtype=np.float64)
    weights = np.asarray([float(row["duration_sec"]) for row in rows], dtype=np.float64)
    return _normal(np.average(vectors, axis=0, weights=weights))


def _template_score(probe: np.ndarray, templates: Sequence[np.ndarray], method: str) -> float:
    scores = sorted((float(np.dot(probe, _normal(vector))) for vector in templates), reverse=True)
    if not scores:
        return float("nan")
    if method == "multi_template_max":
        return scores[0]
    if method == "multi_template_top2_mean":
        return float(np.mean(scores[:2]))
    return float(np.dot(probe, _normal(np.mean(np.asarray(templates), axis=0))))


def _normal(value: object) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if not math.isfinite(norm) or norm <= 0:
        raise ProductV2Error("non-normalizable embedding")
    return array / norm


def _overlap(left: Mapping[str, object], right: Mapping[str, object]) -> float:
    return max(0.0, min(float(left["end_sec"]), float(right["end_sec"])) - max(float(left["start_sec"]), float(right["start_sec"])))


def _active_band(count: int) -> str:
    if count == 1: return "1"
    if count == 2: return "2"
    if count <= 5: return "3-5"
    if count <= 8: return "6-8"
    return "9-12"


def _counts(values: Iterable[str]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for value in values:
        result[value] += 1
    return dict(result)
