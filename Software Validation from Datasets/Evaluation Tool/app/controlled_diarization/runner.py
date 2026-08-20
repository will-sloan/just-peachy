"""Restart-safe, environment-isolated controlled diarization execution."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
from typing import Mapping, Sequence
import uuid

import numpy as np
import yaml

from app.controlled_diarization.contracts import (
    BENCHMARK_VERSION,
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_CONFIG_PATH,
    FROZEN_PIPELINE_SCHEMA_VERSION,
    REPOSITORY_ROOT,
    RESULT_SCHEMA_VERSION,
    TOOL_ROOT,
    ControlledDiarizationError,
    PipelineDefinition,
    canonical_json,
    default_generated_root,
    default_result_root,
    identity,
    load_config,
    load_pipeline_registry,
    sha256_file,
    sha256_text,
)
from app.diarization_evaluation.artifacts import (
    validate_checksum_manifest,
    write_checksum_manifest,
    write_json_atomic,
    write_text_atomic,
)
from app.diarization_evaluation.contracts import (
    DiarizationScoringPolicy,
    resolve_segmentation_provenance,
)
from app.diarization_evaluation.formats import (
    RttmTurn,
    UemRegion,
    parse_rttm,
    parse_uem,
)
from app.diarization_evaluation.scoring import score_diarization, validate_timebase
from app.inference_pipeline.audio_io.loader import load_audio
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.diarization.base import build_diarizer_from_config


TIERS = ("smoke", "development", "evaluation")


def pipeline_status(
    *, config_path: Path = DEFAULT_CONFIG_PATH
) -> dict[str, object]:
    """Report integration and local environment readiness without model inference."""

    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    catalog = ComponentCatalog.load()
    rows: list[dict[str, object]] = []
    for pipeline in registry.values():
        interpreter = interpreter_for_profile(pipeline.environment_profile)
        config_path_value = None
        source_config_exists = False
        component_readiness = None
        if pipeline.component_name and pipeline.kind != "unresolved_modular":
            family = "speaker_embedding" if pipeline.kind == "oracle_turn_clustering" else "diarization"
            try:
                entry = catalog.get(family, pipeline.component_name)
                config_path_value = entry.source_config_path
                source_config_exists = bool(
                    config_path_value and (TOOL_ROOT / config_path_value).is_file()
                )
                component_readiness = entry.qualification_status
            except Exception as exc:
                component_readiness = f"UNRESOLVED:{type(exc).__name__}"
        executable = bool(
            pipeline.execution_status != "NOT_INTEGRATED"
            and interpreter is not None
            and interpreter.is_file()
            and source_config_exists
        )
        blockers = []
        if pipeline.execution_status == "NOT_INTEGRATED":
            blockers.append("pipeline_not_integrated")
        if interpreter is None or not interpreter.is_file():
            blockers.append(f"environment_unavailable:{pipeline.environment_profile}")
        if not source_config_exists and pipeline.kind != "unresolved_modular":
            blockers.append("component_config_unavailable")
        rows.append(
            {
                **pipeline.to_jsonable(),
                "interpreter": str(interpreter) if interpreter else None,
                "interpreter_exists": bool(interpreter and interpreter.is_file()),
                "source_config_path": config_path_value,
                "source_config_exists": source_config_exists,
                "component_readiness": component_readiness,
                "executable_on_this_machine": executable,
                "blockers": blockers,
            }
        )
    return {
        "schema_version": "controlled-diarization-pipeline-status.v1",
        "implicit_model_downloads_allowed": False,
        "pipelines": rows,
        "summary": {
            "declared": len(rows),
            "executable_on_this_machine": sum(row["executable_on_this_machine"] for row in rows),
            "not_integrated": sum(row["execution_status"] == "NOT_INTEGRATED" for row in rows),
        },
    }


def execute_queue(
    *,
    tier: str,
    pipelines: Sequence[str],
    config_path: Path = DEFAULT_CONFIG_PATH,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    generated_root: Path | None = None,
    result_root: Path | None = None,
    frozen_pipeline_config: Path | None = None,
    max_cases: int | None = None,
    oracle_speaker_count_diagnostic: bool = False,
) -> dict[str, object]:
    """Run or reuse selected pipeline/case units sequentially across isolated envs."""

    if tier not in TIERS:
        raise ControlledDiarizationError(f"unsupported tier {tier!r}")
    if not pipelines:
        raise ControlledDiarizationError("at least one runtime pipeline must be selected")
    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    unknown = sorted(set(pipelines) - set(registry))
    if unknown:
        raise ControlledDiarizationError(f"unknown pipelines: {unknown}")
    selected = [registry[value] for value in pipelines]
    for pipeline in selected:
        if pipeline.execution_status == "NOT_INTEGRATED":
            raise ControlledDiarizationError(f"pipeline is NOT_INTEGRATED: {pipeline.pipeline_id}")
    root = benchmark_root.resolve()
    audio_root = (generated_root or default_generated_root()).resolve()
    results = (result_root or default_result_root()).resolve()
    cases = _read_jsonl(root / tier / "case_manifest.jsonl")
    if tier == "evaluation":
        _validate_evaluation_gate(
            frozen_pipeline_config,
            root,
            selected,
        )
    planned = [
        (pipeline, case)
        for pipeline in selected
        for case in cases
        if not (
            pipeline.kind == "oracle_turn_clustering"
            and str(case["overlap_profile"]) != "none"
        )
    ]
    if max_cases is not None:
        if max_cases < 1:
            raise ControlledDiarizationError("max_cases must be >= 1")
        planned = planned[:max_cases]
    summary = {
        "schema_version": "controlled-diarization-run-queue.v1",
        "tier": tier,
        "pipelines": list(pipelines),
        "planned_units": len(planned),
        "valid": 0,
        "reused": 0,
        "failed": 0,
        "skipped": 0,
        "units": [],
    }
    results.mkdir(parents=True, exist_ok=True)
    state_path = results / "queue_state.json"
    for pipeline, case in planned:
        if (results / "STOP_REQUESTED").is_file():
            summary["skipped"] += 1
            summary["units"].append(
                {
                    "pipeline_id": pipeline.pipeline_id,
                    "case_id": case["case_id"],
                    "status": "STOP_REQUESTED",
                }
            )
            continue
        scenario = scenario_identity(config, pipeline, case, oracle_speaker_count_diagnostic)
        destination = results / tier / pipeline.pipeline_id / str(case["case_id"])
        if destination.is_dir():
            try:
                validation = validate_result(destination, expected_scenario_id=scenario)
                summary["valid"] += 1
                summary["reused"] += 1
                summary["units"].append(
                    {
                        "pipeline_id": pipeline.pipeline_id,
                        "case_id": case["case_id"],
                        "scenario_id": scenario,
                        "status": "REUSE",
                        "validation": validation,
                    }
                )
                write_json_atomic(state_path, summary)
                continue
            except Exception:
                _preserve_partial(destination, results / "_partial" / tier / pipeline.pipeline_id)
        interpreter = interpreter_for_profile(pipeline.environment_profile)
        if interpreter is None or not interpreter.is_file():
            summary["failed"] += 1
            summary["units"].append(
                {
                    "pipeline_id": pipeline.pipeline_id,
                    "case_id": case["case_id"],
                    "scenario_id": scenario,
                    "status": "FAILED",
                    "reason": f"environment unavailable: {pipeline.environment_profile}",
                }
            )
            write_json_atomic(state_path, summary)
            continue
        staging = destination.with_name(f".{destination.name}.attempt-{uuid.uuid4().hex[:10]}")
        command = [
            str(interpreter),
            str(TOOL_ROOT / "run_evaluation.py"),
            "diarization-benchmark",
            "run-case",
            "--tier",
            tier,
            "--case-id",
            str(case["case_id"]),
            "--pipeline",
            pipeline.pipeline_id,
            "--benchmark-root",
            str(root),
            "--generated-root",
            str(audio_root),
            "--output-root",
            str(staging),
            "--config",
            str(config_path.resolve()),
        ]
        if oracle_speaker_count_diagnostic:
            command.append("--oracle-speaker-count-diagnostic")
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=TOOL_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            try:
                validation = validate_result(staging, expected_scenario_id=scenario)
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, destination)
                summary["valid"] += 1
                summary["units"].append(
                    {
                        "pipeline_id": pipeline.pipeline_id,
                        "case_id": case["case_id"],
                        "scenario_id": scenario,
                        "status": "RUN",
                        "wall_sec": time.perf_counter() - started,
                        "validation": validation,
                    }
                )
            except Exception as exc:
                failed = _preserve_partial(
                    staging,
                    results / "_failed" / tier / pipeline.pipeline_id,
                )
                summary["failed"] += 1
                summary["units"].append(
                    {
                        "pipeline_id": pipeline.pipeline_id,
                        "case_id": case["case_id"],
                        "scenario_id": scenario,
                        "status": "FAILED_VALIDATION",
                        "reason": _safe_message(str(exc)),
                        "preserved_at": str(failed),
                    }
                )
        else:
            if staging.exists():
                failed = _preserve_partial(
                    staging,
                    results / "_failed" / tier / pipeline.pipeline_id,
                )
            else:
                failed = None
            summary["failed"] += 1
            summary["units"].append(
                {
                    "pipeline_id": pipeline.pipeline_id,
                    "case_id": case["case_id"],
                    "scenario_id": scenario,
                    "status": "FAILED",
                    "reason": _safe_message(completed.stderr or completed.stdout),
                    "preserved_at": str(failed) if failed else None,
                }
            )
        write_json_atomic(state_path, summary)
    write_json_atomic(state_path, summary)
    return summary


def run_one_case(
    *,
    tier: str,
    case_id: str,
    pipeline_id: str,
    output_root: Path,
    config_path: Path = DEFAULT_CONFIG_PATH,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    generated_root: Path | None = None,
    oracle_speaker_count_diagnostic: bool = False,
) -> dict[str, object]:
    """Execute one case inside its already-selected environment process."""

    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    if pipeline_id not in registry:
        raise ControlledDiarizationError(f"unknown pipeline {pipeline_id}")
    pipeline = registry[pipeline_id]
    if pipeline.execution_status == "NOT_INTEGRATED":
        raise ControlledDiarizationError(f"pipeline is NOT_INTEGRATED: {pipeline_id}")
    root = benchmark_root.resolve()
    cases = _read_jsonl(root / tier / "case_manifest.jsonl")
    matches = [row for row in cases if row["case_id"] == case_id]
    if len(matches) != 1:
        raise ControlledDiarizationError(f"case ID must resolve exactly once: {case_id}")
    case = matches[0]
    if pipeline.kind == "oracle_turn_clustering" and case["overlap_profile"] != "none":
        raise ControlledDiarizationError("oracle-turn clustering supports non-overlap cases only")
    destination = output_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"result output is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    audio_root = (generated_root or default_generated_root()).resolve()
    audio_path = audio_root / str(case["audio_logical_path"])
    if not audio_path.is_file() or sha256_file(audio_path) != case["audio_sha256"]:
        raise ControlledDiarizationError("controlled audio is missing or changed")
    references = parse_rttm(root / str(case["reference_rttm_path"]))
    uem = parse_uem(root / str(case["reference_uem_path"]))
    scenario_id = scenario_identity(config, pipeline, case, oracle_speaker_count_diagnostic)
    started_utc = _now()
    started = time.perf_counter()
    try:
        audio_started = time.perf_counter()
        audio = load_audio(
            {
                "recording_id": case_id,
                "source_recording_id": case_id,
                "utt_id": case_id,
                "inference_audio_path": str(audio_path),
                "start_sec": 0.0,
                "end_sec": float(case["duration_sec"]),
                "duration_sec": float(case["duration_sec"]),
            },
            {"runtime": {"sample_rate_hz": 16000}, "audio": {"channel_policy": "mono"}},
        )
        audio_load_sec = time.perf_counter() - audio_started
        inference_started = time.perf_counter()
        if pipeline.kind == "oracle_turn_clustering":
            raw_predictions, component_identity = _oracle_turn_predictions(
                audio_path, references, pipeline
            )
            provenance = resolve_segmentation_provenance(
                vad_enabled=False,
                vad_chunker_enabled=False,
                diarizer_enabled=True,
                diarizer_produced_turns=bool(raw_predictions),
                backend_internal_segmentation=False,
                oracle_reference_used=True,
            )
        else:
            component, component_identity = _resolved_component(pipeline)
            if oracle_speaker_count_diagnostic:
                params = dict(component.get("params") or {})
                count = int(case["reference_speaker_count"])
                params.update({"min_speakers": count, "max_speakers": count, "num_clusters": count})
                component["params"] = params
            diarizer = build_diarizer_from_config({"components": {"diarization": component}})
            if diarizer is None:
                raise ControlledDiarizationError("pipeline resolved as disabled")
            turns = diarizer.diarize(audio)
            raw_predictions = [
                RttmTurn(
                    recording_id=case_id,
                    channel=str((turn.channel_index + 1) if turn.channel_index is not None else 1),
                    start_sec=float(turn.start_sec),
                    end_sec=float(turn.end_sec),
                    speaker_label=str(turn.speaker_turn_label),
                )
                for turn in turns
            ]
            provenance = resolve_segmentation_provenance(
                vad_enabled=pipeline.segmentation.startswith("lightweight"),
                vad_chunker_enabled=False,
                diarizer_enabled=True,
                diarizer_produced_turns=bool(raw_predictions),
                backend_internal_segmentation=not pipeline.segmentation.startswith("lightweight"),
                diarizer_output_authoritative=True,
                oracle_reference_used=False,
            )
        inference_sec = time.perf_counter() - inference_started
        predictions = sorted(set(raw_predictions))
        if any(not turn.speaker_label.startswith("speaker_") for turn in predictions):
            raise ControlledDiarizationError("pipeline emitted non-anonymous speaker labels")
        alignment = validate_timebase(references, predictions, uem)
        strict = _score(config, references, predictions, uem, practical=False, oracle=oracle_speaker_count_diagnostic)
        practical = _score(config, references, predictions, uem, practical=True, oracle=oracle_speaker_count_diagnostic)
        diagnostics = _cluster_diagnostics(references, predictions, float(case["duration_sec"]))
        metrics = {
            "schema_version": "controlled-diarization-metrics.v1",
            "scenario_id": scenario_id,
            "case_id": case_id,
            "pipeline_id": pipeline_id,
            "primary_strict": strict,
            "practical_boundary_tolerant": practical,
            "speaker_count": {
                "reference": len({turn.speaker_label for turn in references}),
                "predicted": len({turn.speaker_label for turn in predictions}),
                "signed_error": len({turn.speaker_label for turn in predictions})
                - len({turn.speaker_label for turn in references}),
                "absolute_error": abs(
                    len({turn.speaker_label for turn in predictions})
                    - len({turn.speaker_label for turn in references})
                ),
                "exact": len({turn.speaker_label for turn in predictions})
                == len({turn.speaker_label for turn in references}),
            },
            **diagnostics,
        }
        _write_rttm(destination / "predictions" / "segments.rttm", predictions)
        _write_rttm(destination / "references" / "reference.rttm", references)
        _write_uem(destination / "references" / "scored_region.uem", uem)
        write_json_atomic(destination / "resolved_pipeline_identity.json", component_identity)
        write_json_atomic(destination / "diagnostics" / "alignment_validation.json", alignment.to_jsonable())
        write_json_atomic(destination / "diagnostics" / "segmentation_provenance.json", provenance.to_jsonable())
        write_json_atomic(destination / "metrics" / "summary.json", metrics)
        run = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "succeeded" if alignment.valid else "invalid",
            "scenario_id": scenario_id,
            "case_id": case_id,
            "tier": tier,
            "pipeline_id": pipeline_id,
            "pipeline_configuration_sha256": pipeline.configuration_sha256,
            "benchmark_id": case["benchmark_id"],
            "benchmark_audio_sha256": case["audio_sha256"],
            "recipe_sha256": case["recipe_sha256"],
            "speaker_count_mode": (
                "oracle_diagnostic" if oracle_speaker_count_diagnostic else "estimated"
            ),
            "oracle_turn_segmentation": pipeline.kind == "oracle_turn_clustering",
            "diagnostic_only": pipeline.diagnostic_only or oracle_speaker_count_diagnostic,
            "label_semantics": "anonymous_diarization",
            "case_factors": {
                key: case[key]
                for key in ("speaker_count", "turn_cadence", "overlap_profile", "replicate")
            },
            "timing": {
                "audio_loading_sec": audio_load_sec,
                "diarization_inference_sec": inference_sec,
                "total_wall_sec": time.perf_counter() - started,
                "audio_duration_sec": float(case["duration_sec"]),
                "real_time_factor": inference_sec / float(case["duration_sec"]),
            },
            "environment": {
                "hostname": socket.gethostname(),
                "os": platform.platform(),
                "python_version": platform.python_version(),
                "python_executable": str(Path(sys.executable).resolve()),
                "environment_profile": pipeline.environment_profile,
            },
            "started_at_utc": started_utc,
            "ended_at_utc": _now(),
        }
        write_json_atomic(destination / "run.json", run)
        _write_case_report(destination, run, metrics, provenance.to_jsonable())
        write_checksum_manifest(destination)
        validate_result(destination, expected_scenario_id=scenario_id)
        return run
    except Exception as exc:
        write_json_atomic(
            destination / "failure.json",
            {
                "schema_version": "controlled-diarization-failure.v1",
                "status": "failed",
                "scenario_id": scenario_id,
                "case_id": case_id,
                "pipeline_id": pipeline_id,
                "error_type": type(exc).__name__,
                "message": _safe_message(str(exc)),
                "failed_at_utc": _now(),
            },
        )
        write_checksum_manifest(destination)
        raise


def validate_result(root: Path, *, expected_scenario_id: str | None = None) -> dict[str, object]:
    required = (
        "run.json",
        "resolved_pipeline_identity.json",
        "predictions/segments.rttm",
        "references/reference.rttm",
        "references/scored_region.uem",
        "diagnostics/alignment_validation.json",
        "diagnostics/segmentation_provenance.json",
        "metrics/summary.json",
        "report/scenario_report.json",
        "report/scenario_report.md",
        "checksums.json",
    )
    missing = [relative for relative in required if not (root / relative).is_file()]
    if missing:
        raise ControlledDiarizationError(f"missing result artifacts: {missing}")
    checksums = validate_checksum_manifest(root)
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    if run.get("schema_version") != RESULT_SCHEMA_VERSION or run.get("status") != "succeeded":
        raise ControlledDiarizationError("result is not a successful controlled v1 result")
    if expected_scenario_id and run.get("scenario_id") != expected_scenario_id:
        raise ControlledDiarizationError("scenario identity mismatch")
    predictions = parse_rttm(root / "predictions" / "segments.rttm")
    references = parse_rttm(root / "references" / "reference.rttm")
    uem = parse_uem(root / "references" / "scored_region.uem")
    alignment = validate_timebase(references, predictions, uem)
    if not alignment.valid:
        raise ControlledDiarizationError(f"invalid result timebase: {alignment.errors}")
    if any(not turn.speaker_label.startswith("speaker_") for turn in predictions):
        raise ControlledDiarizationError("stored prediction labels are not anonymous")
    return {
        "valid": True,
        "scenario_id": run["scenario_id"],
        "case_id": run["case_id"],
        "pipeline_id": run["pipeline_id"],
        "predicted_turn_count": len(predictions),
        **checksums,
    }


def queue_status(
    *,
    pipelines: Sequence[str],
    tiers: Sequence[str] = ("development", "evaluation"),
    config_path: Path = DEFAULT_CONFIG_PATH,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    result_root: Path | None = None,
) -> dict[str, object]:
    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    results = (result_root or default_result_root()).resolve()
    rows = []
    for pipeline_id in pipelines:
        if pipeline_id not in registry:
            raise ControlledDiarizationError(f"unknown pipeline {pipeline_id}")
        for tier in tiers:
            cases = _read_jsonl(benchmark_root / tier / "case_manifest.jsonl")
            counts = Counter()
            for case in cases:
                destination = results / tier / pipeline_id / str(case["case_id"])
                if not destination.exists():
                    counts["missing"] += 1
                    continue
                try:
                    validate_result(destination)
                    counts["valid"] += 1
                except Exception:
                    counts["partial"] += 1
            failed_root = results / "_failed" / tier / pipeline_id
            counts["failed"] = len(list(failed_root.glob("*"))) if failed_root.is_dir() else 0
            rows.append(
                {
                    "pipeline_id": pipeline_id,
                    "tier": tier,
                    "planned": len(cases),
                    "valid": counts["valid"],
                    "missing": counts["missing"],
                    "partial": counts["partial"],
                    "failed_attempts": counts["failed"],
                }
            )
    return {
        "schema_version": "controlled-diarization-queue-status.v1",
        "result_root": str(results),
        "rows": rows,
    }


def scenario_identity(
    config: Mapping[str, object],
    pipeline: PipelineDefinition,
    case: Mapping[str, object],
    oracle_speaker_count_diagnostic: bool = False,
) -> str:
    return identity(
        "cdscenario",
        {
            "benchmark_id": case["benchmark_id"],
            "case_id": case["case_id"],
            "audio_sha256": case["audio_sha256"],
            "recipe_sha256": case["recipe_sha256"],
            "pipeline": pipeline.to_jsonable(),
            "scoring": config["scoring"],
            "speaker_count_mode": (
                "oracle_diagnostic" if oracle_speaker_count_diagnostic else "estimated"
            ),
        },
    )


def interpreter_for_profile(profile: str) -> Path | None:
    if profile == "core-cpu":
        return REPOSITORY_ROOT / ".venv" / "Scripts" / "python.exe"
    if profile in {
        "onnx",
        "wespeaker",
        "credential-diarization",
        "redimnet2",
        "extended-local",
        "core-cuda",
    }:
        return REPOSITORY_ROOT / ".stage8-envs" / profile / "Scripts" / "python.exe"
    return None


def _resolved_component(
    pipeline: PipelineDefinition,
) -> tuple[dict[str, object], dict[str, object]]:
    if not pipeline.component_name:
        raise ControlledDiarizationError("pipeline has no component name")
    catalog = ComponentCatalog.load()
    entry = catalog.get("diarization", pipeline.component_name)
    if entry.source_config_path is None:
        raise ControlledDiarizationError("component has no source configuration")
    source = TOOL_ROOT / entry.source_config_path
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    component = raw.get("component", raw)
    if not isinstance(component, Mapping):
        raise ControlledDiarizationError("component configuration must be a mapping")
    resolved = dict(component)
    params = dict(resolved.get("params") or {})
    if params.get("allow_model_downloads", False):
        raise ControlledDiarizationError("implicit model downloads are prohibited")
    params["allow_model_downloads"] = False
    resolved["params"] = params
    return resolved, {
        "schema_version": "controlled-diarization-resolved-pipeline.v1",
        **pipeline.to_jsonable(),
        "implementation_class": entry.implementation_class,
        "source_config_path": entry.source_config_path,
        "source_config_sha256": entry.source_config_sha256,
        "model_identity": dict(entry.model_identity),
        "model_asset_identity": [dict(row) for row in entry.model_asset_identity],
        "resolved_component": resolved,
        "implicit_model_downloads_allowed": False,
    }


def _oracle_turn_predictions(
    audio_path: Path,
    references: Sequence[RttmTurn],
    pipeline: PipelineDefinition,
) -> tuple[list[RttmTurn], dict[str, object]]:
    from app.inference_pipeline.contracts import AudioSegment
    from app.inference_pipeline.diarization.clustering import agglomerative_cosine_labels
    from app.inference_pipeline.speaker_embedding import build_speaker_embedding_from_config
    from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext

    if not pipeline.component_name:
        raise ControlledDiarizationError("oracle pipeline lacks embedding component")
    catalog = ComponentCatalog.load()
    entry = catalog.get("speaker_embedding", pipeline.component_name)
    if not entry.source_config_path:
        raise ControlledDiarizationError("embedding component has no source config")
    raw = yaml.safe_load((TOOL_ROOT / entry.source_config_path).read_text(encoding="utf-8")) or {}
    component = raw.get("component", raw)
    if not isinstance(component, Mapping):
        raise ControlledDiarizationError("embedding component config must be a mapping")
    embedder = build_speaker_embedding_from_config(
        {"components": {"speaker_embedding": dict(component)}}
    )
    if embedder is None:
        raise ControlledDiarizationError("embedding component resolved as disabled")
    vectors = []
    for index, turn in enumerate(references):
        segment = AudioSegment(
            audio_path=audio_path,
            start_sec=turn.start_sec,
            end_sec=turn.end_sec,
            duration_sec=turn.end_sec - turn.start_sec,
            sample_rate_hz=16000,
            channel_count=1,
            is_mono=True,
        )
        observation = embedder.embed(
            segment,
            SpeakerEmbeddingContext(
                recording_id=turn.recording_id,
                utt_id=f"oracle-turn-{index:04d}",
                source_audio_path=audio_path,
                segment_index=index,
                segment_start_sec=turn.start_sec,
                segment_end_sec=turn.end_sec,
                device="cpu",
                dtype="float32",
                run_config={"project_root": str(TOOL_ROOT.parent)},
            ),
        )
        if observation.status != "ok" or not observation.vector:
            raise ControlledDiarizationError("oracle-turn embedding failed")
        vectors.append(observation.vector)
    labels = agglomerative_cosine_labels(
        vectors,
        threshold=float(pipeline.configuration.get("clustering_threshold", 0.55)),
        min_clusters=1,
        max_clusters=len(references),
    )
    predictions = [
        RttmTurn(
            recording_id=turn.recording_id,
            channel=turn.channel,
            start_sec=turn.start_sec,
            end_sec=turn.end_sec,
            speaker_label=f"speaker_{int(label):02d}",
        )
        for turn, label in zip(references, labels, strict=True)
    ]
    return predictions, {
        "schema_version": "controlled-diarization-resolved-pipeline.v1",
        **pipeline.to_jsonable(),
        "implementation_class": entry.implementation_class,
        "source_config_path": entry.source_config_path,
        "source_config_sha256": entry.source_config_sha256,
        "model_identity": dict(entry.model_identity),
        "model_asset_identity": [dict(row) for row in entry.model_asset_identity],
        "oracle_reference_segmentation_used": True,
        "diagnostic_only": True,
        "implicit_model_downloads_allowed": False,
    }


def _score(
    config: Mapping[str, object],
    references: Sequence[RttmTurn],
    predictions: Sequence[RttmTurn],
    uem: Sequence[UemRegion],
    *,
    practical: bool,
    oracle: bool,
) -> dict[str, object]:
    key = "practical_diagnostic" if practical else "primary"
    raw = dict(config["scoring"][key])
    raw["speaker_count_mode"] = "oracle_diagnostic" if oracle else "estimated"
    return score_diarization(
        references,
        predictions,
        uem,
        policy=DiarizationScoringPolicy.from_mapping(raw),
    )


def _cluster_diagnostics(
    references: Sequence[RttmTurn],
    predictions: Sequence[RttmTurn],
    duration_sec: float,
) -> dict[str, object]:
    ref_labels = sorted({turn.speaker_label for turn in references})
    hyp_labels = sorted({turn.speaker_label for turn in predictions})
    overlap = np.zeros((len(ref_labels), len(hyp_labels)), dtype=np.float64)
    ref_index = {label: index for index, label in enumerate(ref_labels)}
    hyp_index = {label: index for index, label in enumerate(hyp_labels)}
    for ref in references:
        for hyp in predictions:
            seconds = max(0.0, min(ref.end_sec, hyp.end_sec) - max(ref.start_sec, hyp.start_sec))
            overlap[ref_index[ref.speaker_label], hyp_index[hyp.speaker_label]] += seconds
    fragmentation = {
        label: int(np.count_nonzero(overlap[index] > 0))
        for label, index in ref_index.items()
    }
    merging = {
        label: int(np.count_nonzero(overlap[:, index] > 0))
        for label, index in hyp_index.items()
    }
    hyp_time = np.sum(overlap, axis=0) if overlap.size else np.zeros(len(hyp_labels))
    ref_time = np.sum(overlap, axis=1) if overlap.size else np.zeros(len(ref_labels))
    purity = (
        float(np.sum(np.max(overlap, axis=0))) / float(np.sum(hyp_time))
        if overlap.size and float(np.sum(hyp_time)) > 0
        else None
    )
    coverage = (
        float(np.sum(np.max(overlap, axis=1))) / float(np.sum(ref_time))
        if overlap.size and float(np.sum(ref_time)) > 0
        else None
    )
    reentry_rows = []
    consistent = eligible = 0
    for label in ref_labels:
        turns = sorted(
            [turn for turn in references if turn.speaker_label == label],
            key=lambda turn: turn.start_sec,
        )
        if len(turns) < 2 or not hyp_labels:
            continue
        dominant_index = int(np.argmax(overlap[ref_index[label]]))
        dominant = hyp_labels[dominant_index]
        for turn_index, turn in enumerate(turns[1:], 1):
            scores = {
                hyp: sum(
                    max(0.0, min(turn.end_sec, row.end_sec) - max(turn.start_sec, row.start_sec))
                    for row in predictions
                    if row.speaker_label == hyp
                )
                for hyp in hyp_labels
            }
            assigned = max(scores, key=lambda value: (scores[value], value)) if scores else None
            gap = turn.start_sec - turns[turn_index - 1].end_sec
            eligible += 1
            is_consistent = assigned == dominant and scores.get(dominant, 0.0) > 0
            consistent += int(is_consistent)
            reentry_rows.append(
                {
                    "reference_speaker": label,
                    "turn_index": turn_index,
                    "absence_duration_sec": gap,
                    "dominant_predicted_cluster": dominant,
                    "assigned_predicted_cluster": assigned,
                    "consistent": is_consistent,
                }
            )
    boundary = {
        str(tolerance): _boundary_metrics(references, predictions, tolerance)
        for tolerance in (0.25, 0.5)
    }
    overlap_regions = _overlap_regions(references)
    overlap_metrics = None
    if overlap_regions:
        overlap_metrics = score_diarization(
            references,
            predictions,
            [UemRegion(references[0].recording_id, "1", start, end) for start, end in overlap_regions],
            policy=DiarizationScoringPolicy(collar_sec=0.0, overlap_modes=("overlap_aware",)),
        )
    return {
        "fragmentation": {
            "reference_speaker_predicted_cluster_counts": fragmentation,
            "mean_clusters_per_reference_speaker": statistics.fmean(fragmentation.values()) if fragmentation else None,
            "split_reference_speaker_count": sum(value > 1 for value in fragmentation.values()),
        },
        "merging": {
            "predicted_cluster_reference_speaker_counts": merging,
            "mean_reference_speakers_per_cluster": statistics.fmean(merging.values()) if merging else None,
            "merged_predicted_cluster_count": sum(value > 1 for value in merging.values()),
        },
        "cluster_purity": purity,
        "reference_speaker_coverage": coverage,
        "speaker_reentry_consistency": consistent / eligible if eligible else None,
        "reentry_observations": reentry_rows,
        "turn_boundary": boundary,
        "overlap_specific": overlap_metrics,
        "recording_duration_sec": duration_sec,
    }


def _overlap_regions(reference: Sequence[RttmTurn]) -> list[tuple[float, float]]:
    boundaries = sorted({turn.start_sec for turn in reference} | {turn.end_sec for turn in reference})
    regions = []
    for start, end in zip(boundaries, boundaries[1:]):
        active = sum(turn.start_sec < end and turn.end_sec > start for turn in reference)
        if active >= 2:
            if regions and abs(regions[-1][1] - start) < 1e-9:
                regions[-1] = (regions[-1][0], end)
            else:
                regions.append((start, end))
    return regions


def _boundary_metrics(
    reference: Sequence[RttmTurn], hypothesis: Sequence[RttmTurn], tolerance: float
) -> dict[str, object]:
    ref = sorted({turn.start_sec for turn in reference if turn.start_sec > 0})
    hyp = sorted({turn.start_sec for turn in hypothesis if turn.start_sec > 0})
    used: set[int] = set()
    matches = 0
    errors = []
    for value in ref:
        candidates = [
            (abs(value - other), index)
            for index, other in enumerate(hyp)
            if index not in used and abs(value - other) <= tolerance
        ]
        if candidates:
            error, index = min(candidates)
            used.add(index)
            matches += 1
            errors.append(error)
    precision = matches / len(hyp) if hyp else (1.0 if not ref else 0.0)
    recall = matches / len(ref) if ref else 1.0
    return {
        "tolerance_sec": tolerance,
        "reference_boundaries": len(ref),
        "predicted_boundaries": len(hyp),
        "matches": matches,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "mean_absolute_error_sec": statistics.fmean(errors) if errors else None,
    }


def _validate_evaluation_gate(
    frozen_path: Path | None,
    benchmark_root: Path,
    pipelines: Sequence[PipelineDefinition],
) -> None:
    if frozen_path is None or not frozen_path.is_file():
        raise ControlledDiarizationError(
            "evaluation requires an existing frozen development-derived pipeline configuration"
        )
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != FROZEN_PIPELINE_SCHEMA_VERSION:
        raise ControlledDiarizationError("unsupported frozen pipeline configuration")
    if payload.get("development_decision_status") != "frozen":
        raise ControlledDiarizationError("development pipeline decision is unresolved")
    if payload.get("evaluation_tuning_prohibited") is not True:
        raise ControlledDiarizationError("evaluation tuning prohibition is not frozen")
    summary = json.loads((benchmark_root / "protocol_summary.json").read_text(encoding="utf-8"))
    if payload.get("benchmark_id") != summary.get("benchmark_id"):
        raise ControlledDiarizationError("frozen configuration benchmark identity mismatch")
    observed = {
        str(row["pipeline_id"]): str(row["configuration_sha256"])
        for row in payload.get("pipelines", [])
    }
    for pipeline in pipelines:
        if observed.get(pipeline.pipeline_id) != pipeline.configuration_sha256:
            raise ControlledDiarizationError(
                f"frozen configuration hash mismatch for {pipeline.pipeline_id}"
            )


def _preserve_partial(source: Path, parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / f"{source.name.strip('.')}_{_now().replace(':', '').replace('-', '')}"
    if source.exists():
        shutil.move(str(source), str(destination))
    return destination


def _write_rttm(path: Path, turns: Sequence[RttmTurn]) -> None:
    write_text_atomic(path, "\n".join(turn.to_line() for turn in turns) + ("\n" if turns else ""))


def _write_uem(path: Path, regions: Sequence[UemRegion]) -> None:
    write_text_atomic(path, "\n".join(region.to_line() for region in regions) + "\n")


def _write_case_report(
    root: Path,
    run: Mapping[str, object],
    metrics: Mapping[str, object],
    provenance: Mapping[str, object],
) -> None:
    strict = metrics["primary_strict"]
    report = {
        "schema_version": "controlled-diarization-scenario-report.v1",
        "run": dict(run),
        "metrics": dict(metrics),
        "segmentation_provenance": dict(provenance),
        "interpretation": {
            "anonymous_labels": True,
            "permutation_invariant_scoring": True,
            "synthetic_placement_reference": True,
            "human_frame_annotation": False,
        },
    }
    write_json_atomic(root / "report" / "scenario_report.json", report)
    metric = (
        f"DER `{float(strict['der']):.4f}` and JER `{float(strict['jer']):.4f}`"
        if strict.get("metrics_emitted")
        else "DER/JER suppressed"
    )
    write_text_atomic(
        root / "report" / "scenario_report.md",
        "# Controlled diarization result\n\n"
        f"- Scenario: `{run['scenario_id']}`\n"
        f"- Case: `{run['case_id']}`\n"
        f"- Pipeline: `{run['pipeline_id']}`\n"
        f"- Primary strict result: {metric}\n"
        f"- Effective segmentation: `{provenance['effective_source']}`\n\n"
        "Labels remain anonymous and are aligned only inside permutation-aware scoring. "
        "The reference is the exact synthetic placement schedule, not human frame-level annotation.\n",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _safe_message(value: str) -> str:
    safe = value[-4000:]
    for path in (REPOSITORY_ROOT, TOOL_ROOT, Path.home(), Path(sys.executable).parent):
        safe = safe.replace(str(path), f"<{path.name}>")
        safe = safe.replace(str(path).replace("\\", "/"), f"<{path.name}>")
    return safe


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
