"""Authorized native-condition diarization execution and result validation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import socket
import sys
import time
from typing import Mapping

import yaml

from app.diarization_evaluation.artifacts import (
    file_sha256,
    validate_checksum_manifest,
    write_checksum_manifest,
    write_json_atomic,
    write_text_atomic,
)
from app.diarization_evaluation.contracts import (
    RESULT_SCHEMA_VERSION,
    TOOL_ROOT,
    DiarizationEvaluationError,
    backend_availability,
    require_executable_backend,
    resolve_segmentation_provenance,
    scoring_policy,
)
from app.diarization_evaluation.formats import RttmTurn, UemRegion, parse_rttm, parse_uem
from app.diarization_evaluation.manifests import DATA_ROOT, read_native_manifest
from app.diarization_evaluation.scoring import score_diarization, validate_timebase
from app.inference_pipeline.audio_io.loader import load_audio
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.diarization.base import build_diarizer_from_config


def run_diarization_unit(
    manifest_root: Path,
    evaluation_unit_id: str,
    backend_id: str,
    output_root: Path,
    *,
    oracle_speaker_count_diagnostic: bool = False,
    allow_overwrite: bool = False,
) -> dict[str, object]:
    """Run one qualified backend on exactly one immutable native scoring unit."""

    root = output_root.resolve()
    if root.exists() and any(root.iterdir()):
        if allow_overwrite:
            raise DiarizationEvaluationError(
                "in-place replacement of a diarization result is prohibited; use a fresh "
                "result folder so validated evidence cannot become a mixed partial bundle"
            )
        raise FileExistsError(f"diarization result already exists: {root}")
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_root / "native_diarization_manifest.parquet"
    rows = read_native_manifest(manifest_path)
    matches = [row for row in rows if row["evaluation_unit_id"] == evaluation_unit_id]
    if len(matches) != 1:
        raise DiarizationEvaluationError(
            f"evaluation unit must resolve exactly once: {evaluation_unit_id}"
        )
    row = matches[0]
    if row["augmentation_policy"] != "native_only" or row["synthetic_augmentation_applied"]:
        raise DiarizationEvaluationError("Stage 11 execution refuses augmented native audio")

    started_utc = _now()
    started = time.perf_counter()
    try:
        status = require_executable_backend(backend_id)
        component, identity = _resolved_component(backend_id, status)
        if oracle_speaker_count_diagnostic:
            component = _with_oracle_speaker_count(component, int(row["reference_speaker_count"]))
        diarizer = build_diarizer_from_config({"components": {"diarization": component}})
        if diarizer is None:
            raise DiarizationEvaluationError("selected diarization backend resolved as disabled")
        audio_path = (DATA_ROOT / str(row["audio_path_project_relative"])).resolve()
        if not audio_path.is_file():
            raise FileNotFoundError(
                f"native source audio is unavailable: {row['audio_path_project_relative']}"
            )
        record = {
            "recording_id": row["recording_id"],
            "source_recording_id": row["source_recording_id"],
            "utt_id": row["utt_id"],
            "inference_audio_path": str(audio_path),
            "start_sec": row["source_start_sec"],
            "end_sec": row["source_end_sec"],
            "duration_sec": row["duration_sec"],
        }
        audio_started = time.perf_counter()
        audio = load_audio(
            record,
            {
                "runtime": {"sample_rate_hz": 16000},
                "audio": {"channel_policy": "mono"},
            },
        )
        audio_load_sec = time.perf_counter() - audio_started
        inference_started = time.perf_counter()
        raw_turns = diarizer.diarize(audio)
        inference_sec = time.perf_counter() - inference_started
        source_offset = float(row["source_start_sec"])
        predictions: list[RttmTurn] = []
        turn_diagnostics: list[dict[str, object]] = []
        for turn in raw_turns:
            label = str(turn.speaker_turn_label)
            if not label.startswith("speaker_"):
                raise DiarizationEvaluationError(
                    "diarization backend emitted a non-anonymous speaker label"
                )
            predictions.append(
                RttmTurn(
                    recording_id=evaluation_unit_id,
                    channel=str((turn.channel_index + 1) if turn.channel_index is not None else 1),
                    start_sec=source_offset + float(turn.start_sec),
                    end_sec=source_offset + float(turn.end_sec),
                    speaker_label=label,
                )
            )
            turn_diagnostics.append(
                {
                    "speaker_label": label,
                    "label_semantics": "anonymous_diarization",
                    "record_relative_start_sec": float(turn.start_sec),
                    "record_relative_end_sec": float(turn.end_sec),
                    "source_absolute_start_sec": source_offset + float(turn.start_sec),
                    "source_absolute_end_sec": source_offset + float(turn.end_sec),
                    "channel_index": turn.channel_index,
                    "confidence": turn.confidence,
                    "is_overlap": bool(turn.is_overlap),
                    "source": turn.source,
                }
            )
        predictions = sorted(set(predictions))
        references = [
            turn
            for turn in parse_rttm(manifest_root / "references.rttm")
            if turn.recording_id == evaluation_unit_id
        ]
        uem = [
            region
            for region in parse_uem(manifest_root / "scored_regions.uem")
            if region.recording_id == evaluation_unit_id
        ]
        if len(uem) != 1:
            raise DiarizationEvaluationError("evaluation unit must have exactly one UEM region")
        alignment = validate_timebase(references, predictions, uem)
        metrics = score_diarization(
            references,
            predictions,
            uem,
            policy=scoring_policy(),
            reference_compatible=bool(row["der_jer_eligible"]),
            incompatibility_reason=str(row["reference_reason"]),
        )
        provenance = resolve_segmentation_provenance(
            vad_enabled=False,
            vad_chunker_enabled=False,
            diarizer_enabled=True,
            diarizer_produced_turns=bool(predictions),
            backend_internal_segmentation=True,
            diarizer_output_authoritative=True,
            oracle_reference_used=False,
        )
        _write_rttm_atomic(root / "predictions" / "segments.rttm", predictions)
        _write_rttm_atomic(root / "references" / "reference.rttm", references)
        _write_uem_atomic(root / "references" / "scored_region.uem", uem)
        write_json_atomic(root / "backend_status.json", status)
        write_json_atomic(root / "resolved_component_identity.json", identity)
        write_json_atomic(root / "diagnostics" / "alignment_validation.json", alignment.to_jsonable())
        write_json_atomic(root / "diagnostics" / "segmentation_provenance.json", provenance.to_jsonable())
        write_json_atomic(
            root / "diagnostics" / "diarization.json",
            {
                "schema_version": "diarization-diagnostics.v1",
                "evaluation_unit_id": evaluation_unit_id,
                "backend_id": backend_id,
                "label_semantics": "anonymous_diarization",
                "anonymous_labels_preserved": True,
                "reference_identity_mapping_applied": False,
                "speaker_attributed_transcript_status": "not_produced_no_asr_in_standalone_diarization_run",
                "predicted_speaker_count": len({turn.speaker_label for turn in predictions}),
                "predicted_turn_count": len(predictions),
                "turns": sorted(
                    turn_diagnostics,
                    key=lambda value: (
                        float(value["record_relative_start_sec"]),
                        float(value["record_relative_end_sec"]),
                        str(value["speaker_label"]),
                    ),
                ),
                "source_timing_offset_sec": source_offset,
                "audio": {
                    "source_sample_rate_hz": audio.source_sample_rate,
                    "model_sample_rate_hz": audio.sample_rate,
                    "source_channel_count": audio.source_num_channels,
                    "model_channel_count": audio.num_channels,
                    "channel_policy": audio.channel_policy,
                    "duration_sec": audio.duration_sec,
                },
                "timing": {
                    "audio_loading_sec": audio_load_sec,
                    "diarization_inference_sec": inference_sec,
                },
            },
        )
        write_json_atomic(root / "metrics" / "summary.json", metrics)
        total_sec = time.perf_counter() - started
        run: dict[str, object] = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "succeeded" if alignment.valid else "invalid",
            "evaluation_unit_id": evaluation_unit_id,
            "backend_id": backend_id,
            "native_manifest": {
                "path": manifest_path.name,
                "sha256": file_sha256(manifest_path),
                "manifest_id": row["manifest_id"],
                "benchmark_tier": row["benchmark_tier"],
            },
            "record": _public_record(row),
            "component_identity_sha256": file_sha256(root / "resolved_component_identity.json"),
            "reference_version": row["reference_version"],
            "scoring_policy_version": metrics["scoring_policy"]["version"],
                "speaker_count_mode": (
                    "oracle_diagnostic" if oracle_speaker_count_diagnostic else "estimated"
                ),
                "oracle_reference_segmentation_used": False,
            "label_semantics": "anonymous_diarization",
            "started_at_utc": started_utc,
            "ended_at_utc": _now(),
            "total_wall_sec": total_sec,
            "environment": _environment(status),
            "conditional_outputs": {
                "rttm": True,
                "uem": True,
                "speaker_attributed_transcript": False,
                "word_timestamps": False,
                "known_speaker_matching": False,
            },
        }
        write_json_atomic(root / "run.json", run)
        _write_report(root, run, metrics, provenance.to_jsonable())
        write_checksum_manifest(root)
        validate_diarization_result(root)
        return run
    except Exception as exc:
        write_json_atomic(
            root / "failure.json",
            {
                "schema_version": "diarization-failure.v1",
                "status": "failed",
                "evaluation_unit_id": evaluation_unit_id,
                "backend_id": backend_id,
                "error_type": type(exc).__name__,
                "message": _safe_message(str(exc)),
                "failed_at_utc": _now(),
            },
        )
        write_checksum_manifest(root)
        raise


def validate_diarization_result(root: Path) -> dict[str, object]:
    required = (
        "run.json",
        "backend_status.json",
        "resolved_component_identity.json",
        "predictions/segments.rttm",
        "references/reference.rttm",
        "references/scored_region.uem",
        "diagnostics/alignment_validation.json",
        "diagnostics/segmentation_provenance.json",
        "diagnostics/diarization.json",
        "metrics/summary.json",
        "report/scenario_report.json",
        "report/scenario_report.md",
        "checksums.json",
    )
    missing = [relative for relative in required if not (root / relative).is_file()]
    if missing:
        raise DiarizationEvaluationError(f"missing diarization result artifacts: {missing}")
    checksums = validate_checksum_manifest(root)
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    if run.get("schema_version") != RESULT_SCHEMA_VERSION or run.get("status") != "succeeded":
        raise DiarizationEvaluationError("diarization result is not a successful v1 result")
    predictions = parse_rttm(root / "predictions" / "segments.rttm")
    references = parse_rttm(root / "references" / "reference.rttm")
    uem = parse_uem(root / "references" / "scored_region.uem")
    alignment = validate_timebase(references, predictions, uem)
    if not alignment.valid:
        raise DiarizationEvaluationError(f"invalid diarization timebase: {alignment.errors}")
    if any(not turn.speaker_label.startswith("speaker_") for turn in predictions):
        raise DiarizationEvaluationError("stored diarization output lost anonymous semantics")
    metrics = json.loads((root / "metrics" / "summary.json").read_text(encoding="utf-8"))
    if metrics.get("metrics_emitted") and not metrics.get("timebase_validation", {}).get("valid"):
        raise DiarizationEvaluationError("metrics were emitted for an invalid timebase")
    return {
        "valid": True,
        "evaluation_unit_id": run["evaluation_unit_id"],
        "backend_id": run["backend_id"],
        "predicted_turn_count": len(predictions),
        "metrics_emitted": bool(metrics.get("metrics_emitted")),
        **checksums,
    }


def backend_status_report() -> dict[str, object]:
    rows = backend_availability()
    return {
        "schema_version": "diarization-backend-status-report.v1",
        "implicit_model_downloads_allowed": False,
        "backends": [rows[key] for key in sorted(rows)],
        "summary": {
            "declared": len(rows),
            "executable_in_current_environment": sum(
                int(bool(row["execution_allowed"])) for row in rows.values()
            ),
        },
    }


def _resolved_component(
    backend_id: str,
    status: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    catalog = ComponentCatalog.load()
    entry = catalog.get("diarization", backend_id)
    if entry.source_config_path is None:
        raise DiarizationEvaluationError("diarization backend has no source component config")
    config_path = TOOL_ROOT / entry.source_config_path
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    component = raw.get("component", raw)
    if not isinstance(component, Mapping):
        raise DiarizationEvaluationError("diarization component config must be a mapping")
    component = dict(component)
    params = dict(component.get("params") or {})
    if params.get("allow_model_downloads", False):
        raise DiarizationEvaluationError("implicit model downloads are prohibited")
    params["allow_model_downloads"] = False
    component["params"] = params
    identity = {
        "schema_version": "resolved-diarization-component.v1",
        "backend_id": backend_id,
        "family": "diarization",
        "implementation_class": entry.implementation_class,
        "source_config_path": entry.source_config_path,
        "source_config_sha256": entry.source_config_sha256,
        "qualification_status": status["qualification_status"],
        "qualification_evidence": status["qualification_evidence"],
        "environment_profile": status["environment_profile"],
        "model_identity": dict(entry.model_identity),
        "model_asset_identity": [dict(value) for value in entry.model_asset_identity],
        "resolved_component": component,
        "overrides": {
            "params.allow_model_downloads": {
                "source": (raw.get("component", raw).get("params") or {}).get(
                    "allow_model_downloads"
                ),
                "final": False,
            }
        },
    }
    return component, identity


def _with_oracle_speaker_count(
    component: Mapping[str, object],
    speaker_count: int,
) -> dict[str, object]:
    if speaker_count < 1:
        raise DiarizationEvaluationError("oracle diagnostic requires a positive speaker count")
    value = dict(component)
    params = dict(value.get("params") or {})
    params["min_speakers"] = speaker_count
    params["max_speakers"] = speaker_count
    params["num_clusters"] = speaker_count
    value["params"] = params
    return value


def _public_record(row: Mapping[str, object]) -> dict[str, object]:
    keys = (
        "dataset",
        "recording_id",
        "source_recording_id",
        "utt_id",
        "audio_path_project_relative",
        "source_start_sec",
        "source_end_sec",
        "duration_sec",
        "meeting_id",
        "session_id",
        "stream_type",
        "stream_id",
        "channel_id",
        "microphone_id",
        "device_id",
        "location",
        "room",
        "distractor",
        "mic",
        "position",
        "degrees",
        "reference_support",
        "der_jer_eligible",
        "cpwer_eligible",
        "augmentation_policy",
    )
    return {key: row.get(key) for key in keys}


def _environment(status: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": "diarization-environment.v1",
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable_name": Path(sys.executable).name,
        "environment_profile": status["environment_profile"],
        "pid": os.getpid(),
    }


def _write_rttm_atomic(path: Path, turns: list[RttmTurn]) -> None:
    rows = [turn.to_line() for turn in sorted(set(turns))]
    write_text_atomic(path, "\n".join(rows) + ("\n" if rows else ""))


def _write_uem_atomic(path: Path, regions: list[UemRegion]) -> None:
    rows = [region.to_line() for region in sorted(set(regions))]
    write_text_atomic(path, "\n".join(rows) + ("\n" if rows else ""))


def _write_report(
    root: Path,
    run: Mapping[str, object],
    metrics: Mapping[str, object],
    provenance: Mapping[str, object],
) -> None:
    report = {
        "schema_version": "diarization-scenario-report.v1",
        "evaluation_unit_id": run["evaluation_unit_id"],
        "backend_id": run["backend_id"],
        "status": run["status"],
        "record": run["record"],
        "segmentation_provenance": dict(provenance),
        "metrics": dict(metrics),
        "interpretation": {
            "anonymous_labels_are_reference_identities": False,
            "scoring_permutation_is_internal_only": True,
            "synthetic_augmentation_applied": False,
        },
    }
    write_json_atomic(root / "report" / "scenario_report.json", report)
    metric_text = (
        f"DER `{float(metrics['der']):.4f}`, JER `{float(metrics['jer']):.4f}`"
        if metrics.get("metrics_emitted")
        else "DER/JER suppressed: " + "; ".join(metrics.get("suppression_reasons", []))
    )
    write_text_atomic(
        root / "report" / "scenario_report.md",
        "# Stage 11 Diarization Scenario\n\n"
        f"- Evaluation unit: `{run['evaluation_unit_id']}`\n"
        f"- Backend: `{run['backend_id']}`\n"
        f"- Dataset: `{run['record']['dataset']}`\n"
        f"- Stream: `{run['record'].get('stream_type')}`\n"
        f"- Effective segmentation source: `{provenance['effective_source']}`\n"
        f"- Result: {metric_text}\n\n"
        "Predicted `speaker_*` labels remain anonymous within-record clusters. Any permutation used for scoring is not written back as an identity.\n",
    )


def _safe_message(value: str) -> str:
    safe = value
    for path in (TOOL_ROOT, DATA_ROOT, Path(sys.executable).parent):
        safe = safe.replace(str(path), f"<{path.name}>")
        safe = safe.replace(str(path).replace("\\", "/"), f"<{path.name}>")
    return safe


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
