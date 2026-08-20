"""Gated, restart-safe execution for the hybrid attribution protocol."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
from typing import Iterable, Mapping, Sequence
import uuid

from app.controlled_diarization.contracts import default_generated_root, load_config as load_diarization_config, load_pipeline_registry
from app.controlled_diarization.runner import (
    execute_queue as execute_diarization_queue,
    interpreter_for_profile,
    pipeline_status as diarization_pipeline_status,
    validate_result as validate_diarization_result,
)
from app.diarization_evaluation.artifacts import validate_checksum_manifest, write_checksum_manifest
from app.diarization_evaluation.formats import parse_rttm
from app.hybrid_speaker_attribution.attribution import (
    AttributionSettings,
    attribute_recording,
    score_recording,
)
from app.hybrid_speaker_attribution.contracts import (
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_PROTOCOL_ROOT,
    FROZEN_CONFIG_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    TOOL_ROOT,
    HybridAttributionError,
    canonical_sha256,
    default_result_root,
    file_sha256,
    load_enrollment_policy,
    load_frozen_config,
)
from app.hybrid_speaker_attribution.embedding_cache import embedding_job, load_cached
from app.hybrid_speaker_attribution.protocol import plan_protocol, prepare_protocol, validate_protocol
from app.speaker_protocol.contracts import eligible_embedding_backends
from app.utils.paths import resolve_data_path_from_logical


def audit(
    *, speaker_backend: str, diarization_pipeline: str, enrollment_policy: Path,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT, protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
    generated_root: Path | None = None,
) -> dict[str, object]:
    policy = load_enrollment_policy(enrollment_policy)
    eligible = eligible_embedding_backends(backend_ids={speaker_backend})
    errors = []
    if speaker_backend not in eligible:
        errors.append("speaker backend is not qualified or its local assets are missing")
    if policy["speaker_backend_id"] != speaker_backend:
        errors.append("enrollment policy/backend mismatch")
    registry = load_pipeline_registry(load_diarization_config())
    pipeline = registry.get(diarization_pipeline)
    pipeline_readiness = next(
        (row for row in diarization_pipeline_status()["pipelines"] if row["pipeline_id"] == diarization_pipeline),
        None,
    )
    if pipeline is None:
        errors.append("selected diarization pipeline does not exist")
    elif pipeline.execution_status == "NOT_INTEGRATED":
        errors.append("selected diarization pipeline is not integrated")
    elif interpreter_for_profile(pipeline.environment_profile) is None or not interpreter_for_profile(pipeline.environment_profile).is_file():
        errors.append(f"diarization environment is unavailable: {pipeline.environment_profile}")
    elif not pipeline_readiness or not pipeline_readiness["executable_on_this_machine"]:
        errors.append(f"diarization pipeline is not executable: {pipeline_readiness.get('blockers') if pipeline_readiness else 'unresolved'}")
    try:
        protocol = validate_protocol(protocol_root, benchmark_root=benchmark_root)
    except Exception as exc:
        protocol = None
        errors.append(f"protocol invalid or absent: {type(exc).__name__}: {exc}")
    missing_enrollment = []
    if protocol is not None:
        inventory = _read_csv(protocol_root / "enrollment_clip_inventory.csv")
        for row in inventory:
            path = resolve_data_path_from_logical(str(row["logical_audio_path"]))
            if not path.is_file():
                missing_enrollment.append(str(path))
        if missing_enrollment:
            errors.append(f"reserved enrollment audio missing ({len(missing_enrollment)})")
    generated = (generated_root or default_generated_root()).resolve()
    smoke_cases = _read_jsonl(benchmark_root / "smoke" / "case_manifest.jsonl")
    missing_audio = [str(generated / str(row["audio_logical_path"])) for row in smoke_cases if not (generated / str(row["audio_logical_path"])).is_file()]
    if missing_audio:
        errors.append(f"controlled generated audio missing ({len(missing_audio)})")
    return {
        "schema_version": "hybrid-speaker-attribution-audit.v1",
        "speaker_backend": speaker_backend,
        "speaker_backend_identity": eligible.get(speaker_backend),
        "diarization_pipeline": diarization_pipeline,
        "diarization_pipeline_identity": pipeline.to_jsonable() if pipeline else None,
        "diarization_pipeline_readiness": pipeline_readiness,
        "enrollment_policy_id": policy["policy_id"],
        "protocol": protocol,
        "generated_root": str(generated),
        "errors": errors,
        "missing_reserved_enrollment_files": missing_enrollment[:10],
        "ready": not errors,
        "model_inference_started": False,
        "asr_started": False,
    }


def plan(
    *, speaker_backend: str, diarization_pipeline: str, enrollment_policy: Path,
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    diarization_result_root: Path | None = None,
) -> dict[str, object]:
    policy = load_enrollment_policy(enrollment_policy)
    base = plan_protocol(protocol_root)
    enrollment_jobs = {
        str(row["source_clip_id"])
        for row in _read_csv(protocol_root / "enrollment_clip_inventory.csv")
    }
    reference_jobs = 0
    reusable_diarization = 0
    known_prediction_jobs = 0
    missing_prediction_case_count = 0
    diar_root = diarization_result_root.resolve() if diarization_result_root else None
    for tier in ("development", "evaluation"):
        for case in _read_jsonl(benchmark_root / tier / "case_manifest.jsonl"):
            reference_jobs += len(parse_rttm(benchmark_root / str(case["reference_rttm_path"])))
            root = diar_root / tier / diarization_pipeline / str(case["case_id"]) if diar_root else None
            if root and root.is_dir():
                try:
                    validate_diarization_result(root)
                    reusable_diarization += 1
                    known_prediction_jobs += len(parse_rttm(root / "predictions" / "segments.rttm"))
                    continue
                except Exception:
                    pass
            missing_prediction_case_count += 1
    return {
        **base,
        "speaker_backend": speaker_backend,
        "diarization_pipeline": diarization_pipeline,
        "enrollment_policy_id": policy["policy_id"],
        "development_configurations": "declared grid; embeddings and diarization reused",
        "evaluation_configuration": "exact frozen development winner only",
        "reusable_diarization_results": reusable_diarization,
        "missing_diarization_results": missing_prediction_case_count,
        "unique_reserved_enrollment_embeddings": len(enrollment_jobs),
        "oracle_reference_turn_embeddings": reference_jobs,
        "known_predicted_segment_embeddings": known_prediction_jobs,
        "predicted_segment_embeddings_for_missing_diarization": "determined only after diarization; one per emitted segment",
        "asr_in_scope": False,
    }


def run_tier(
    *, tier: str, speaker_backend: str, diarization_pipeline: str,
    enrollment_policy_path: Path, diarization_result_root: Path,
    result_root: Path | None = None, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT, generated_root: Path | None = None,
    frozen_diarization_config: Path | None = None, frozen_hybrid_config: Path | None = None,
    max_cases: int | None = None, settings_override: Mapping[str, object] | None = None,
    run_diarization: bool = True,
) -> dict[str, object]:
    if tier not in {"smoke", "development", "evaluation"}:
        raise HybridAttributionError(f"unsupported tier: {tier}")
    protocol_validation = validate_protocol(protocol_root, benchmark_root=benchmark_root)
    policy = load_enrollment_policy(enrollment_policy_path)
    if policy["speaker_backend_id"] != speaker_backend:
        raise HybridAttributionError("enrollment policy was frozen for a different backend")
    eligible = eligible_embedding_backends(backend_ids={speaker_backend})
    if speaker_backend not in eligible:
        raise HybridAttributionError("selected speaker backend is not qualified and available")
    frozen = None
    if tier == "evaluation":
        if settings_override:
            raise HybridAttributionError("evaluation rejects ad hoc attribution overrides")
        if frozen_hybrid_config is None:
            raise HybridAttributionError("evaluation requires --frozen-hybrid-config")
        frozen = load_frozen_config(frozen_hybrid_config)
        _validate_frozen_inputs(
            frozen, protocol_validation, speaker_backend, diarization_pipeline,
            policy, frozen_diarization_config,
        )
        runtime = dict(frozen["attribution_settings"])
    else:
        runtime = _settings_from_policy(policy)
        runtime.update(dict(settings_override or {}))
    settings = AttributionSettings(**runtime)
    results = (result_root or default_result_root()).resolve()
    diar_results = diarization_result_root.resolve()
    generated = (generated_root or default_generated_root()).resolve()
    if run_diarization:
        diar_summary = execute_diarization_queue(
            tier=tier,
            pipelines=[diarization_pipeline],
            benchmark_root=benchmark_root,
            generated_root=generated,
            result_root=diar_results,
            frozen_pipeline_config=frozen_diarization_config,
            max_cases=max_cases,
        )
    else:
        diar_summary = {"planned_units": 0, "reused": 0, "valid": 0, "external_reuse_only": True}
    cases = _read_jsonl(benchmark_root / tier / "case_manifest.jsonl")
    if max_cases is not None:
        cases = cases[:max_cases]
    overlays = {
        (str(row["case_id"]), str(row["overlay_id"])): row
        for row in _read_jsonl(protocol_root / tier / "identity_overlays.jsonl")
    }
    config_identity = {
        "protocol_id": protocol_validation["protocol_id"],
        "speaker_backend": speaker_backend,
        "speaker_backend_declared_identity": eligible[speaker_backend],
        "diarization_pipeline": diarization_pipeline,
        "enrollment_policy_id": policy["policy_id"],
        "enrollment_policy_sha256": policy["policy_sha256"],
        "attribution_settings": runtime,
        "frozen_hybrid_config_sha256": file_sha256(frozen_hybrid_config) if frozen_hybrid_config else None,
    }
    config_id = "hybrid_" + canonical_sha256(config_identity)[:16].lower()
    queue = {
        "schema_version": "hybrid-speaker-attribution-queue.v1",
        "tier": tier,
        "configuration_id": config_id,
        "diarization": diar_summary,
        "planned": len(cases) * 3,
        "valid": 0,
        "reused": 0,
        "failed": 0,
        "units": [],
    }
    for case in cases:
        case_id = str(case["case_id"])
        diar_root = diar_results / tier / diarization_pipeline / case_id
        try:
            validate_diarization_result(diar_root)
            case_payload = _prepare_case_payload(
                tier=tier, case=case, diar_root=diar_root, generated_root=generated,
                speaker_backend=speaker_backend, overlays=overlays, policy=policy,
                cache_root=results / "embedding_cache",
            )
            for overlay_id in ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"):
                destination = results / tier / config_id / diarization_pipeline / speaker_backend / case_id / overlay_id
                if destination.is_dir():
                    try:
                        validation = validate_result(destination, expected_configuration_id=config_id)
                        queue["valid"] += 1
                        queue["reused"] += 1
                        queue["units"].append({"case_id": case_id, "overlay_id": overlay_id, "status": "REUSE", "validation": validation})
                        continue
                    except Exception:
                        _preserve_partial(destination, results / "_partial" / tier / config_id)
                overlay = overlays[(case_id, overlay_id)]
                _execute_overlay(
                    destination=destination, case=case, overlay=overlay,
                    case_payload=case_payload, settings=settings,
                    configuration_id=config_id, configuration_identity=config_identity,
                    pipeline_id=diarization_pipeline, backend_id=speaker_backend,
                    policy=policy, diarization_root=diar_root,
                )
                queue["valid"] += 1
                queue["units"].append({"case_id": case_id, "overlay_id": overlay_id, "status": "SUCCEEDED"})
        except Exception as exc:
            queue["failed"] += 3
            queue["units"].append({"case_id": case_id, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
            _write_json(results / "_failed" / tier / config_id / f"{case_id}_{uuid.uuid4().hex[:8]}.json", queue["units"][-1])
    _write_json(results / tier / config_id / "queue_state.json", queue)
    if queue["failed"]:
        raise HybridAttributionError(f"hybrid queue completed with failed units; see {results / tier / config_id / 'queue_state.json'}")
    return queue


def freeze_configuration(
    *, development_configuration_id: str, speaker_backend: str,
    diarization_pipeline: str, enrollment_policy_path: Path,
    frozen_diarization_config: Path, output_path: Path,
    attribution_settings: Mapping[str, object], decision_note: str,
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT, development_result_root: Path,
) -> dict[str, object]:
    if not decision_note.strip():
        raise HybridAttributionError("a development decision note is required")
    protocol = validate_protocol(protocol_root)
    policy = load_enrollment_policy(enrollment_policy_path)
    if policy["speaker_backend_id"] != speaker_backend:
        raise HybridAttributionError("policy/backend mismatch")
    if not frozen_diarization_config.is_file():
        raise HybridAttributionError("frozen diarization configuration is missing")
    eligible = eligible_embedding_backends(backend_ids={speaker_backend})
    if speaker_backend not in eligible:
        raise HybridAttributionError("selected speaker backend is not qualified and available")
    scientific_identity = {
        "protocol_id": protocol["protocol_id"],
        "speaker_backend": speaker_backend,
        "speaker_backend_declared_identity": eligible[speaker_backend],
        "diarization_pipeline": diarization_pipeline,
        "enrollment_policy_id": policy["policy_id"],
        "enrollment_policy_sha256": policy["policy_sha256"],
        "attribution_settings": dict(attribution_settings),
        "frozen_hybrid_config_sha256": None,
    }
    selected_id = "hybrid_" + canonical_sha256(scientific_identity)[:16].lower()
    valid_development = []
    candidate_root = development_result_root.resolve() / "development" / development_configuration_id
    for run_path in candidate_root.glob("*/*/*/*/run.json") if candidate_root.is_dir() else ():
        validation = validate_result(run_path.parent, expected_configuration_id=development_configuration_id)
        valid_development.append({"path": str(run_path.parent), "case_id": validation["case_id"], "overlay_id": validation["overlay_id"]})
    if not valid_development:
        raise HybridAttributionError("freeze requires validated development results for the exact configuration")
    source_identity = json.loads(
        (Path(valid_development[0]["path"]) / "configuration_identity.json").read_text(encoding="utf-8")
    )
    immutable_expected = {
        "protocol_id": protocol["protocol_id"],
        "speaker_backend": speaker_backend,
        "diarization_pipeline": diarization_pipeline,
        "enrollment_policy_id": policy["policy_id"],
        "enrollment_policy_sha256": policy["policy_sha256"],
    }
    for key, value in immutable_expected.items():
        if source_identity.get(key) != value:
            raise HybridAttributionError(f"development result dependency mismatch: {key}")
    payload = {
        "schema_version": FROZEN_CONFIG_SCHEMA_VERSION,
        "development_decision_status": "frozen",
        "frozen_at_utc": _now(),
        "git_sha": _git_sha(),
        "development_configuration_id": development_configuration_id,
        "selected_hybrid_configuration_id": selected_id,
        "validated_development_result_units": len(valid_development),
        "development_result_identity_sha256": canonical_sha256(valid_development),
        "protocol_id": protocol["protocol_id"],
        "benchmark_id": protocol["benchmark_id"],
        "speaker_backend_id": speaker_backend,
        "diarization_pipeline_id": diarization_pipeline,
        "enrollment_policy_id": policy["policy_id"],
        "enrollment_policy_sha256": policy["policy_sha256"],
        "frozen_diarization_config_path": str(frozen_diarization_config.resolve()),
        "frozen_diarization_config_sha256": file_sha256(frozen_diarization_config),
        "attribution_settings": dict(attribution_settings),
        "decision_note": decision_note,
        "evaluation_tuning_prohibited": True,
    }
    payload["hybrid_config_sha256"] = canonical_sha256(payload)
    _write_json(output_path, payload)
    return payload


def status(result_root: Path | None = None) -> dict[str, object]:
    root = (result_root or default_result_root()).resolve()
    rows = []
    for path in root.glob("*/hybrid_*/*/*/*/*/run.json") if root.is_dir() else ():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validation = validate_result(path.parent)
            rows.append({"tier": value["tier"], "configuration_id": value["configuration_id"], "case_id": value["case_id"], "overlay_id": value["overlay_id"], "status": "VALID", "validation": validation})
        except Exception:
            rows.append({"path": str(path), "status": "INVALID"})
    failures = len(list((root / "_failed").rglob("*.json"))) if (root / "_failed").is_dir() else 0
    return {"schema_version": "hybrid-speaker-attribution-status.v1", "result_root": str(root), "valid_or_declared_units": rows, "failures": failures}


def validate_result(root: Path, expected_configuration_id: str | None = None) -> dict[str, object]:
    required = (
        "run.json", "configuration_identity.json", "diarization_identity.json",
        "speaker_backend_identity.json", "enrollment_identity.json",
        "runtime_identity.json",
        "predictions/final_clusters.jsonl", "predictions/progressive_turns.jsonl",
        "predictions/evidence_checkpoints.jsonl", "predictions/future_asr_turns.jsonl",
        "references/reference_turns.jsonl", "metrics/summary.json", "metrics/error_events.jsonl",
        "oracle/oracle_diarization_identity_metrics.json", "resource_usage.json", "checksums.json",
    )
    missing = [relative for relative in required if not (root / relative).is_file()]
    if missing:
        raise HybridAttributionError(f"missing hybrid artifacts: {missing}")
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    if run.get("schema_version") != RESULT_SCHEMA_VERSION or run.get("status") != "succeeded":
        raise HybridAttributionError("hybrid result is not successful")
    if expected_configuration_id and run.get("configuration_id") != expected_configuration_id:
        raise HybridAttributionError("hybrid configuration identity mismatch")
    checksums = validate_checksum_manifest(root)
    return {"valid": True, "case_id": run["case_id"], "overlay_id": run["overlay_id"], "configuration_id": run["configuration_id"], **checksums}


def _prepare_case_payload(
    *, tier: str, case: Mapping[str, object], diar_root: Path, generated_root: Path,
    speaker_backend: str, overlays: Mapping[tuple[str, str], Mapping[str, object]],
    policy: Mapping[str, object], cache_root: Path,
) -> dict[str, object]:
    case_id = str(case["case_id"])
    audio_path = generated_root / str(case["audio_logical_path"])
    predictions = _turn_rows(diar_root / "predictions" / "segments.rttm", case_id, "cluster_id")
    references = _turn_rows(diar_root / "references" / "reference.rttm", case_id, "speaker_label")
    jobs: list[dict[str, object]] = []
    for row in predictions:
        jobs.append(embedding_job(job_id=str(row["segment_id"]), audio_path=audio_path, audio_sha256=str(case["audio_sha256"]), start_sec=float(row["start_sec"]), end_sec=float(row["end_sec"]), role="predicted_segment", metadata={"recording_id": case_id, "cluster_id": row["cluster_id"]}))
    for row in references:
        jobs.append(embedding_job(job_id=f"oracle_{row['segment_id']}", audio_path=audio_path, audio_sha256=str(case["audio_sha256"]), start_sec=float(row["start_sec"]), end_sec=float(row["end_sec"]), role="oracle_reference_turn", metadata={"recording_id": case_id, "speaker_label": row["speaker_label"]}))
    enrollment_count = int(policy["enrollment_utterance_count"])
    all_database: dict[str, Mapping[str, object]] = {}
    for overlay_id in ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"):
        for database_row in overlays[(case_id, overlay_id)]["enrollment_database"]:
            all_database[str(database_row["enrolled_id"])] = database_row
    for enrolled_id, database_row in sorted(all_database.items()):
        clips = list(database_row["reserved_enrollment_clips"])
        if len(clips) < enrollment_count:
            raise HybridAttributionError(f"enrollment policy requests too many clips: {enrolled_id}")
        for clip in clips[:enrollment_count]:
            path = resolve_data_path_from_logical(str(clip["logical_audio_path"]))
            jobs.append(embedding_job(job_id=f"enroll_{enrolled_id}_{clip['source_clip_id']}", audio_path=path, audio_sha256=str(clip["source_audio_sha256"]), start_sec=0.0, end_sec=float(clip["duration_sec"]), role="reserved_enrollment", metadata={"recording_id": case_id, "enrolled_id": enrolled_id, "source_clip_id": clip["source_clip_id"]}))
    unique = {str(row["job_identity"]): row for row in jobs}
    extraction = _invoke_embedding_worker(speaker_backend, unique.values(), cache_root)
    if not extraction.get("backend_identity"):
        raise HybridAttributionError("speaker backend produced no usable embeddings")
    cache_entries = {str(row["job_id"]): dict(row) for row in extraction["cache_entries"]}
    cached = {
        str(row["job_id"]): load_cached(
            cache_root / speaker_backend / str(cache_entries[str(row["job_id"])]["filename"]),
            expected_job_identity=str(row["job_identity"]),
            expected_cache_identity=str(cache_entries[str(row["job_id"])]["cache_identity"]),
        )
        for row in unique.values()
    }
    return {"predictions": predictions, "references": references, "jobs": jobs, "cached": cached, "backend_identity": extraction["backend_identity"], "extraction_summary": extraction}


def _execute_overlay(
    *, destination: Path, case: Mapping[str, object], overlay: Mapping[str, object],
    case_payload: Mapping[str, object], settings: AttributionSettings,
    configuration_id: str, configuration_identity: Mapping[str, object],
    pipeline_id: str, backend_id: str, policy: Mapping[str, object], diarization_root: Path,
) -> None:
    staging = destination.with_name(f".{destination.name}.staging-{uuid.uuid4().hex[:8]}")
    staging.mkdir(parents=True, exist_ok=False)
    try:
        cached = dict(case_payload["cached"])
        predictions = []
        for row in case_payload["predictions"]:
            observation = cached[str(row["segment_id"])]
            predictions.append({**dict(row), "status": observation["status"], "vector": observation["vector"], "duration_sec": float(row["end_sec"]) - float(row["start_sec"]), "predicted_overlap": _has_cross_cluster_overlap(row, case_payload["predictions"])})
        enrollment: dict[str, list[dict[str, object]]] = {}
        template_identities = []
        count = int(policy["enrollment_utterance_count"])
        for database_row in overlay["enrollment_database"]:
            enrolled_id = str(database_row["enrolled_id"])
            enrollment[enrolled_id] = []
            for clip in list(database_row["reserved_enrollment_clips"])[:count]:
                item = cached[f"enroll_{enrolled_id}_{clip['source_clip_id']}"]
                enrollment[enrolled_id].append({"status": item["status"], "vector": item["vector"], "duration_sec": item["duration_sec"]})
            template_identities.append({
                "enrolled_id": enrolled_id,
                "aggregation_method": policy["aggregation_method"],
                "selected_source_clip_ids": [clip["source_clip_id"] for clip in list(database_row["reserved_enrollment_clips"])[:count]],
                "cache_job_identities": [cached[f"enroll_{enrolled_id}_{clip['source_clip_id']}"]["job_identity"] for clip in list(database_row["reserved_enrollment_clips"])[:count]],
                "template_sha256": canonical_sha256(enrollment[enrolled_id]),
            })
        decisions = attribute_recording(recording_id=str(case["case_id"]), segments=predictions, enrollment=enrollment, settings=settings)
        metrics = score_recording(reference_turns=case_payload["references"], predicted_turns=case_payload["predictions"], local_to_global=dict(overlay["local_to_global_speaker"]), speaker_states=dict(overlay["speaker_states"]), final_decisions=decisions["final"], progressive_decisions=decisions["progressive"])
        oracle_segments = []
        for row in case_payload["references"]:
            item = cached[f"oracle_{row['segment_id']}"]
            oracle_segments.append({**dict(row), "cluster_id": str(row["speaker_label"]), "status": item["status"], "vector": item["vector"], "duration_sec": float(row["end_sec"]) - float(row["start_sec"]), "predicted_overlap": False})
        oracle_decisions = attribute_recording(recording_id=str(case["case_id"]), segments=oracle_segments, enrollment=enrollment, settings=settings)
        oracle_metrics = score_recording(reference_turns=case_payload["references"], predicted_turns=oracle_segments, local_to_global=dict(overlay["local_to_global_speaker"]), speaker_states=dict(overlay["speaker_states"]), final_decisions=oracle_decisions["final"], progressive_decisions=oracle_decisions["progressive"])
        diar_identity = json.loads((diarization_root / "resolved_pipeline_identity.json").read_text(encoding="utf-8"))
        _write_json(staging / "configuration_identity.json", {**dict(configuration_identity), "configuration_id": configuration_id})
        _write_json(staging / "diarization_identity.json", diar_identity)
        _write_json(staging / "speaker_backend_identity.json", case_payload["backend_identity"])
        _write_json(staging / "enrollment_identity.json", {"policy": dict(policy), "overlay_id": overlay["overlay_id"], "local_to_global_speaker": overlay["local_to_global_speaker"], "speaker_states": overlay["speaker_states"], "enrollment_database": overlay["enrollment_database"], "templates": template_identities})
        _write_json(staging / "runtime_identity.json", {"schema_version": "hybrid-runtime-identity.v1", "management_python": sys.executable, "management_python_version": sys.version, "platform": platform.platform(), "hostname": socket.gethostname(), "git_sha": _git_sha(), "generated_at_utc": _now()})
        _write_jsonl(staging / "predictions" / "final_clusters.jsonl", decisions["final"])
        _write_jsonl(staging / "predictions" / "progressive_turns.jsonl", decisions["progressive"])
        _write_jsonl(staging / "predictions" / "evidence_checkpoints.jsonl", decisions["evidence_checkpoints"])
        _write_jsonl(staging / "predictions" / "future_asr_turns.jsonl", _future_asr_rows(case_payload["predictions"], decisions["progressive"]))
        _write_jsonl(staging / "references" / "reference_turns.jsonl", case_payload["references"])
        anonymous_metrics = json.loads((diarization_root / "metrics" / "summary.json").read_text(encoding="utf-8"))
        _write_json(staging / "metrics" / "summary.json", {**metrics, "anonymous_diarization_metrics": anonymous_metrics})
        _write_jsonl(staging / "metrics" / "error_events.jsonl", _error_events(case, overlay, metrics, anonymous_metrics, decisions["final"]))
        _write_json(staging / "oracle" / "oracle_diarization_identity_metrics.json", oracle_metrics)
        backend_runtime = [dict(item.get("backend_runtime") or {}) for item in dict(case_payload["cached"]).values() if item.get("backend_runtime")]
        extraction_summary = dict(case_payload["extraction_summary"])
        _write_json(staging / "resource_usage.json", {"schema_version": "hybrid-resource-usage.v1", "shared_case_level_cost_repeated_across_overlays": True, "embedding_extraction_wall_sec": sum(float(dict(item).get("extraction_sec") or 0) for item in dict(case_payload["cached"]).values()), "backend_inference_sec": sum(float(item.get("inference_sec") or 0) for item in backend_runtime), "peak_cpu_memory_mb": max((float(item.get("cpu_memory_mb") or 0) for item in backend_runtime), default=None), "peak_gpu_memory_mb": max((float(item.get("peak_gpu_memory_mb") or 0) for item in backend_runtime), default=None), "cache_observations": len(dict(case_payload["cached"])), "cache_reused_observations_this_invocation": extraction_summary.get("reused", 0), "asr_runtime_sec": 0.0})
        _write_json(staging / "run.json", {"schema_version": RESULT_SCHEMA_VERSION, "status": "succeeded", "tier": case["tier"], "configuration_id": configuration_id, "case_id": case["case_id"], "overlay_id": overlay["overlay_id"], "pipeline_id": pipeline_id, "speaker_backend_id": backend_id, "protocol_id": overlay["protocol_id"], "benchmark_id": overlay["benchmark_id"], "speaker_count": case["speaker_count"], "turn_cadence": case["turn_cadence"], "overlap_profile": case["overlap_profile"], "recording_duration_sec": case["duration_sec"], "scientific": bool(policy.get("scientific", True)) and case["tier"] != "smoke", "started_asr": False, "completed_at_utc": _now()})
        write_checksum_manifest(staging)
        validate_result(staging, expected_configuration_id=configuration_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _invoke_embedding_worker(backend: str, jobs: Iterable[Mapping[str, object]], cache_root: Path) -> dict[str, object]:
    eligible = eligible_embedding_backends(backend_ids={backend})[backend]
    interpreter = interpreter_for_profile(str(eligible["environment_profile"]))
    if interpreter is None or not interpreter.is_file():
        raise HybridAttributionError(f"backend environment unavailable: {eligible['environment_profile']}")
    cache_root.mkdir(parents=True, exist_ok=True)
    manifest = cache_root / f".{backend}_jobs_{uuid.uuid4().hex[:8]}.jsonl"
    _write_jsonl(manifest, jobs)
    try:
        completed = subprocess.run(
            [str(interpreter), "-m", "app.hybrid_speaker_attribution.embedding_cache", "--backend", backend, "--jobs", str(manifest), "--cache-root", str(cache_root)],
            cwd=TOOL_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if completed.returncode:
            message = (completed.stderr or completed.stdout)[-4000:]
            raise HybridAttributionError(f"embedding worker failed ({completed.returncode}): {message}")
        return json.loads((cache_root / backend / "extraction_summary.json").read_text(encoding="utf-8"))
    finally:
        manifest.unlink(missing_ok=True)


def _turn_rows(path: Path, case_id: str, label_key: str) -> list[dict[str, object]]:
    rows = []
    for index, turn in enumerate(parse_rttm(path)):
        start, end = float(turn.start_sec), float(turn.start_sec + turn.duration_sec)
        rows.append({"recording_id": case_id, "segment_id": f"{case_id}_{label_key}_{index:04d}", "start_sec": start, "end_sec": end, label_key: str(turn.speaker_label), "cluster_id": str(turn.speaker_label)})
    return rows


def _future_asr_rows(turns: Sequence[Mapping[str, object]], progressive: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    labels = {str(row["segment_id"]): row for row in progressive}
    return [{"recording_id": row["recording_id"], "turn_id": row["segment_id"], "start_sec": row["start_sec"], "end_sec": row["end_sec"], "anonymous_cluster_id": row["cluster_id"], "speaker_label": labels[str(row["segment_id"])]["assigned_label"], "speaker_decision_state": labels[str(row["segment_id"])]["decision_state"], "text": None, "asr_status": "NOT_RUN"} for row in turns]


def _error_events(case: Mapping[str, object], overlay: Mapping[str, object], metrics: Mapping[str, object], anonymous: Mapping[str, object], final_decisions: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    categories = (
        "DIARIZATION_MISS", "DIARIZATION_FALSE_ALARM", "DIARIZATION_CONFUSION",
        "DIARIZATION_FRAGMENTATION", "DIARIZATION_MERGE", "KNOWN_CORRECT",
        "WRONG_KNOWN", "REJECTED_AS_UNKNOWN", "UNKNOWN_CORRECTLY_REJECTED",
        "FALSE_KNOWN", "INSUFFICIENT_EVIDENCE", "IDENTITY_CHURN",
    )
    primary = dict(anonymous.get("primary_strict") or {})
    values = {
        "DIARIZATION_MISS": primary.get("missed_speech_sec"),
        "DIARIZATION_FALSE_ALARM": primary.get("false_alarm_sec"),
        "DIARIZATION_CONFUSION": primary.get("speaker_confusion_sec"),
        "DIARIZATION_FRAGMENTATION": metrics.get("fragmentation_count", 0),
        "DIARIZATION_MERGE": metrics.get("merge_count", 0),
        "KNOWN_CORRECT": metrics.get("known_correct_time_sec", 0),
        "WRONG_KNOWN": metrics.get("wrong_known_time_sec", 0),
        "REJECTED_AS_UNKNOWN": metrics.get("known_rejected_as_unknown_time_sec", 0),
        "UNKNOWN_CORRECTLY_REJECTED": metrics.get("unknown_correctly_rejected_time_sec", 0),
        "FALSE_KNOWN": metrics.get("false_known_time_sec", 0),
        "INSUFFICIENT_EVIDENCE": sum(row.get("decision_category") == "INSUFFICIENT_EVIDENCE" for row in final_decisions),
        "IDENTITY_CHURN": metrics.get("identity_churn_count", 0),
    }
    return [{"case_id": case["case_id"], "overlay_id": overlay["overlay_id"], "error_category": category, "value": values.get(category), "available": category in values} for category in categories]


def _settings_from_policy(policy: Mapping[str, object]) -> dict[str, object]:
    return {
        "product_threshold": float(policy["product_threshold"]),
        "score_margin": float(policy.get("score_margin") or 0.0),
        "minimum_segment_duration_sec": float(policy["minimum_segment_duration_sec"]),
        "minimum_evidence_duration_sec": float(policy["minimum_evidence_duration_sec"]),
        "enrollment_aggregation": str(policy["aggregation_method"]),
        "cluster_aggregation": "normalized_mean",
        "overlap_policy": "include_predicted_overlap",
    }


def _validate_frozen_inputs(frozen: Mapping[str, object], protocol: Mapping[str, object], backend: str, pipeline: str, policy: Mapping[str, object], frozen_diarization: Path | None) -> None:
    expected = {"protocol_id": protocol["protocol_id"], "benchmark_id": protocol["benchmark_id"], "speaker_backend_id": backend, "diarization_pipeline_id": pipeline, "enrollment_policy_id": policy["policy_id"], "enrollment_policy_sha256": policy["policy_sha256"]}
    for key, value in expected.items():
        if frozen.get(key) != value:
            raise HybridAttributionError(f"frozen evaluation input mismatch: {key}")
    if frozen_diarization is None or file_sha256(frozen_diarization) != frozen["frozen_diarization_config_sha256"]:
        raise HybridAttributionError("frozen diarization configuration hash mismatch")


def _preserve_partial(source: Path, parent: Path) -> None:
    parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, parent / f"{source.parent.name}_{source.name}_{uuid.uuid4().hex[:8]}")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_csv(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text("".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _has_cross_cluster_overlap(row: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> bool:
    return any(
        str(other["segment_id"]) != str(row["segment_id"])
        and str(other["cluster_id"]) != str(row["cluster_id"])
        and min(float(row["end_sec"]), float(other["end_sec"])) > max(float(row["start_sec"]), float(other["start_sec"]))
        for other in rows
    )


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=TOOL_ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "UNAVAILABLE"
