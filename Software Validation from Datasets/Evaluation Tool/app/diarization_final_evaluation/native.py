"""Frozen-finalist execution on native CHiME-6 and VOiCES units."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import time
from typing import Mapping, Sequence
import uuid

import soundfile as sf

from app.controlled_diarization.contracts import (
    load_config,
    load_pipeline_registry,
    sha256_file,
    sha256_text,
    canonical_json,
)
from app.controlled_diarization.runner import _PeakMemorySampler
from app.diarization_evaluation.artifacts import (
    validate_checksum_manifest,
    write_checksum_manifest,
    write_json_atomic,
    write_text_atomic,
)
from app.diarization_evaluation.contracts import scoring_policy
from app.diarization_evaluation.formats import RttmTurn, UemRegion, parse_rttm, parse_uem
from app.diarization_evaluation.manifests import DATA_ROOT, read_native_manifest
from app.diarization_evaluation.scoring import score_diarization, validate_timebase
from app.diarization_product_v2.cross_environment import cross_environment_predictions
from app.diarization_final_evaluation.contracts import (
    FROZEN_RUNTIME_CONFIG,
    NATIVE_AUDIO_CACHE,
    NATIVE_RESULT_ROOT,
    STOP_PATH,
    TASK1_NATIVE_ROOT,
    TASK1_SELECTION,
    SHARED_CACHE_ROOT,
)


NATIVE_RESULT_SCHEMA = "diarization-final-native-result.v1"
_TRANSIENT_ACCESS_RETRIES = 3


def native_rows(dataset: str | None = None) -> list[dict[str, object]]:
    rows = read_native_manifest(TASK1_NATIVE_ROOT / "native_diarization_manifest.parquet")
    return [dict(row) for row in rows if dataset is None or row["dataset"] == dataset]


def execute_native_queue(*, dataset: str, pipeline_id: str) -> dict[str, object]:
    if dataset not in {"chime6", "voices"}:
        raise ValueError(f"unsupported native dataset: {dataset}")
    rows = native_rows(dataset)
    state_path = NATIVE_RESULT_ROOT / f"queue_state.{dataset}.{pipeline_id}.json"
    summary: dict[str, object] = {
        "schema_version": "diarization-final-native-queue.v1",
        "dataset": dataset,
        "pipeline_id": pipeline_id,
        "planned_units": len(rows),
        "valid": 0,
        "reused": 0,
        "failed": 0,
        "skipped": 0,
        "status": "RUNNING",
        "current_case": None,
        "units": [],
    }
    source_hashes: dict[Path, str] = {}
    for row in rows:
        if STOP_PATH.is_file():
            summary["skipped"] = int(summary["skipped"]) + 1
            continue
        unit = str(row["evaluation_unit_id"])
        summary["current_case"] = unit
        write_json_atomic(state_path, summary)
        destination = NATIVE_RESULT_ROOT / dataset / pipeline_id / unit
        try:
            if destination.is_dir():
                validation = validate_native_result(destination, expected_pipeline=pipeline_id)
                summary["valid"] = int(summary["valid"]) + 1
                summary["reused"] = int(summary["reused"]) + 1
                summary["units"].append({"evaluation_unit_id": unit, "status": "REUSE", **validation})
                continue
            transient_failures: list[str] = []
            for attempt in range(1, _TRANSIENT_ACCESS_RETRIES + 1):
                staging = destination.with_name(f".{unit}.attempt-{uuid.uuid4().hex[:10]}")
                try:
                    run_native_unit(
                        row=row,
                        pipeline_id=pipeline_id,
                        output_root=staging,
                        source_hashes=source_hashes,
                    )
                    validation = validate_native_result(staging, expected_pipeline=pipeline_id)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(staging, destination)
                    summary["valid"] = int(summary["valid"]) + 1
                    summary["units"].append(
                        {
                            "evaluation_unit_id": unit,
                            "status": "RUN",
                            "transient_retry_count": len(transient_failures),
                            "transient_failures": transient_failures,
                            **validation,
                        }
                    )
                    break
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    failed = _preserve(staging, NATIVE_RESULT_ROOT / "_failed" / dataset / pipeline_id)
                    if _is_transient_windows_replace_failure(exc) and attempt < _TRANSIENT_ACCESS_RETRIES:
                        transient_failures.append(error)
                        time.sleep(0.5 * attempt)
                        continue
                    summary["failed"] = int(summary["failed"]) + 1
                    summary["units"].append(
                        {
                            "evaluation_unit_id": unit,
                            "status": "FAILED",
                            "error": error,
                            "preserved_at": str(failed) if failed else None,
                            "transient_retry_count": len(transient_failures),
                            "transient_failures": transient_failures,
                        }
                    )
                    break
        finally:
            summary["current_case"] = None
            write_json_atomic(state_path, summary)
    summary["status"] = "COMPLETE" if int(summary["failed"]) == 0 else "COMPLETE_WITH_FAILURES"
    summary["current_case"] = None
    write_json_atomic(state_path, summary)
    return summary


def run_native_unit(
    *,
    row: Mapping[str, object],
    pipeline_id: str,
    output_root: Path,
    source_hashes: dict[Path, str] | None = None,
) -> dict[str, object]:
    root = output_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"native result is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    selection_sha = sha256_file(TASK1_SELECTION)
    registry = load_pipeline_registry(load_config(FROZEN_RUNTIME_CONFIG))
    if pipeline_id not in registry:
        raise ValueError(f"pipeline is absent from frozen runtime config: {pipeline_id}")
    pipeline = registry[pipeline_id]
    source = (DATA_ROOT / str(row["audio_path_project_relative"])).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"native source audio unavailable: {row['audio_path_project_relative']}")
    cache = source_hashes if source_hashes is not None else {}
    source_sha = cache.get(source)
    if source_sha is None:
        source_sha = sha256_file(source)
        cache[source] = source_sha
    slice_path, slice_sha = _materialize_slice(row, source, source_sha)
    started_at = _now()
    started = time.perf_counter()
    memory = _PeakMemorySampler()
    memory.start()
    try:
        previous = os.environ.get("JP_DIARIZATION_SHARED_CACHE_ROOT")
        os.environ["JP_DIARIZATION_SHARED_CACHE_ROOT"] = str(SHARED_CACHE_ROOT.resolve())
        try:
            inference_started = time.perf_counter()
            relative, identity = cross_environment_predictions(
                audio_path=slice_path,
                audio_sha256=slice_sha,
                recording_id=str(row["evaluation_unit_id"]),
                duration_sec=float(row["duration_sec"]),
                pipeline=pipeline,
                output_root=root,
                oracle_speaker_count=None,
            )
            inference_sec = time.perf_counter() - inference_started
        finally:
            if previous is None:
                os.environ.pop("JP_DIARIZATION_SHARED_CACHE_ROOT", None)
            else:
                os.environ["JP_DIARIZATION_SHARED_CACHE_ROOT"] = previous
        offset = float(row["source_start_sec"])
        predictions = sorted(
            {
                RttmTurn(
                    recording_id=str(row["evaluation_unit_id"]),
                    channel=turn.channel,
                    start_sec=offset + turn.start_sec,
                    end_sec=offset + turn.end_sec,
                    speaker_label=turn.speaker_label,
                )
                for turn in relative
            }
        )
        if any(not row.speaker_label.startswith("speaker_") for row in predictions):
            raise ValueError("native pipeline emitted a non-anonymous label")
        references = [
            turn for turn in parse_rttm(TASK1_NATIVE_ROOT / "references.rttm")
            if turn.recording_id == row["evaluation_unit_id"]
        ]
        uem = [
            region for region in parse_uem(TASK1_NATIVE_ROOT / "scored_regions.uem")
            if region.recording_id == row["evaluation_unit_id"]
        ]
        if len(uem) != 1:
            raise ValueError("native unit must have exactly one UEM")
        alignment = validate_timebase(references, predictions, uem)
        metrics = score_diarization(
            references,
            predictions,
            uem,
            policy=scoring_policy(),
            reference_compatible=bool(row["der_jer_eligible"]),
            incompatibility_reason=str(row["reference_reason"]),
        )
        diagnostics = _fragmentation_diagnostics(predictions, float(row["duration_sec"]))
        _write_rttm(root / "predictions" / "segments.rttm", predictions)
        _write_rttm(root / "references" / "reference.rttm", references)
        _write_uem(root / "references" / "scored_region.uem", uem)
        write_json_atomic(root / "resolved_pipeline_identity.json", identity)
        write_json_atomic(root / "metrics" / "summary.json", metrics)
        write_json_atomic(root / "diagnostics" / "alignment_validation.json", alignment.to_jsonable())
        write_json_atomic(root / "diagnostics" / "acoustic_fragmentation.json", diagnostics)
        resource = memory.stop()
        total = time.perf_counter() - started
        run = {
            "schema_version": NATIVE_RESULT_SCHEMA,
            "status": "succeeded" if alignment.valid else "invalid",
            "evaluation_unit_id": row["evaluation_unit_id"],
            "dataset": row["dataset"],
            "pipeline_id": pipeline_id,
            "pipeline_configuration_sha256": pipeline.configuration_sha256,
            "frozen_selection_sha256": selection_sha,
            "native_manifest_id": row["manifest_id"],
            "native_manifest_sha256": sha256_file(TASK1_NATIVE_ROOT / "native_diarization_manifest.parquet"),
            "source_audio_sha256": source_sha,
            "derived_native_slice_sha256": slice_sha,
            "derived_native_slice_policy": "source-range mono 16k PCM16; source audio unchanged",
            "record": {key: row.get(key) for key in row},
            "label_semantics": "anonymous_diarization",
            "known_speaker_attribution_performed": False,
            "asr_performed": False,
            "timing": {
                "diarization_inference_sec": inference_sec,
                "total_wall_sec": total,
                "audio_duration_sec": float(row["duration_sec"]),
                "real_time_factor": inference_sec / max(float(row["duration_sec"]), 1e-9),
            },
            "resource_telemetry": resource,
            "environment": {"hostname": socket.gethostname(), "pid": os.getpid()},
            "started_at_utc": started_at,
            "ended_at_utc": _now(),
        }
        write_json_atomic(root / "run.json", run)
        write_checksum_manifest(root)
        validate_native_result(root, expected_pipeline=pipeline_id)
        return run
    except Exception:
        memory.stop()
        raise


def _is_transient_windows_replace_failure(exc: BaseException) -> bool:
    """Identify only the known Windows atomic-replace sharing violation."""

    message = f"{type(exc).__name__}: {exc}".lower()
    return (
        ("winerror 5" in message or "permissionerror" in message)
        and "access is denied" in message
        and ".tmp" in message
    )


def validate_native_result(root: Path, *, expected_pipeline: str | None = None) -> dict[str, object]:
    required = (
        "run.json", "resolved_pipeline_identity.json", "predictions/segments.rttm",
        "references/reference.rttm", "references/scored_region.uem", "metrics/summary.json",
        "diagnostics/alignment_validation.json", "diagnostics/acoustic_fragmentation.json",
        "diagnostics/technical_coverage.json", "checksums.json",
    )
    missing = [item for item in required if not (root / item).is_file()]
    if missing:
        raise ValueError(f"missing native result artifacts: {missing}")
    checksums = validate_checksum_manifest(root)
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    if run.get("schema_version") != NATIVE_RESULT_SCHEMA or run.get("status") != "succeeded":
        raise ValueError("native result is not successful")
    if expected_pipeline and run.get("pipeline_id") != expected_pipeline:
        raise ValueError("native pipeline identity mismatch")
    if run.get("frozen_selection_sha256") != sha256_file(TASK1_SELECTION):
        raise ValueError("native result selection identity mismatch")
    predictions = parse_rttm(root / "predictions" / "segments.rttm")
    if any(not item.speaker_label.startswith("speaker_") for item in predictions):
        raise ValueError("native result contains non-anonymous labels")
    metric = json.loads((root / "metrics" / "summary.json").read_text(encoding="utf-8"))
    if run["dataset"] == "voices" and metric.get("metrics_emitted") is not False:
        raise ValueError("VOiCES DER/JER was not suppressed")
    return {
        "valid": True,
        "dataset": run["dataset"],
        "pipeline_id": run["pipeline_id"],
        "evaluation_unit_id": run["evaluation_unit_id"],
        "metrics_emitted": bool(metric.get("metrics_emitted")),
        **checksums,
    }


def _materialize_slice(row: Mapping[str, object], source: Path, source_sha: str) -> tuple[Path, str]:
    identity = sha256_text(canonical_json({
        "source_sha256": source_sha,
        "start_sec": float(row["source_start_sec"]),
        "end_sec": float(row["source_end_sec"]),
        "sample_rate_hz": 16000,
        "channels": 1,
        "subtype": "PCM_16",
    }))
    path = NATIVE_AUDIO_CACHE / f"{identity}.wav"
    if not path.is_file():
        from app.inference_pipeline.audio_io.loader import load_audio

        audio = load_audio(
            {
                "recording_id": row["recording_id"],
                "source_recording_id": row["source_recording_id"],
                "utt_id": row["utt_id"],
                "inference_audio_path": str(source),
                "start_sec": row["source_start_sec"],
                "end_sec": row["source_end_sec"],
                "duration_sec": row["duration_sec"],
            },
            {"runtime": {"sample_rate_hz": 16000}, "audio": {"channel_policy": "mono"}},
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp.wav")
        sf.write(temp, audio.waveform[0].detach().cpu().numpy(), 16000, subtype="PCM_16")
        try:
            os.replace(temp, path)
        except PermissionError:
            # A parallel finalist may have atomically published the identical
            # hash-bound slice while this process was rendering its temp file.
            if not path.is_file():
                raise
            temp.unlink(missing_ok=True)
    return path, sha256_file(path)


def _fragmentation_diagnostics(predictions: Sequence[RttmTurn], duration_sec: float) -> dict[str, object]:
    by: dict[str, float] = {}
    for row in predictions:
        by[row.speaker_label] = by.get(row.speaker_label, 0.0) + row.duration_sec
    predicted = sum(by.values())
    largest = max(by.values(), default=0.0)
    return {
        "schema_version": "native-acoustic-fragmentation-diagnostic.v1",
        "predicted_speaker_count": len(by),
        "predicted_turn_count": len(predictions),
        "false_speaker_changes_per_minute": max(0, len(predictions) - 1) / max(duration_sec / 60.0, 1e-9),
        "fragment_count": len(predictions),
        "largest_cluster_fraction": largest / predicted if predicted else 0.0,
        "phantom_speaker_duration_sec": max(0.0, predicted - largest),
        "predicted_speech_duration_sec": predicted,
        "der_jer_supported": False,
    }


def _write_rttm(path: Path, rows: Sequence[RttmTurn]) -> None:
    write_text_atomic(path, "\n".join(row.to_line() for row in rows) + ("\n" if rows else ""))


def _write_uem(path: Path, rows: Sequence[UemRegion]) -> None:
    write_text_atomic(path, "\n".join(row.to_line() for row in rows) + ("\n" if rows else ""))


def _preserve(source: Path, parent: Path) -> Path | None:
    if not source.exists():
        return None
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / f"{source.name.strip('.')}_{_now().replace(':', '').replace('-', '')}"
    shutil.move(str(source), str(destination))
    return destination


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
