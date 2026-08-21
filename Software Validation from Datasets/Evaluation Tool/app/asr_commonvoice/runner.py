"""Restart-safe single-backend execution for the Common Voice 60+ ASR study."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Mapping, Sequence

import psutil
import pyarrow as pa

from app.dataset_registry.registry import TextNormalizationSpec
from app.diarization_evaluation.artifacts import (
    file_sha256,
    write_json_atomic,
    write_jsonl_atomic,
    write_parquet_atomic,
)
from app.inference_pipeline.metrics.asr_metrics import character_error_rate
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.resolver import resolve_pipeline
from app.scoring.text import normalize_for_scoring
from app.scoring.wer import compute_wer
from app.utils.paths import resolve_data_path_from_logical

from .contracts import (
    ASRCommonVoiceError,
    BASE_INFERENCE_CONFIG,
    MODEL_COMPONENT_IDS,
    RESULT_SCHEMA_VERSION,
    campaign_identity,
    canonical_sha256,
    git_sha,
    implementation_sha256,
    resolve_models,
)
from .protocol import read_manifest, read_smoke_ids, validate_protocol


LOGGER = logging.getLogger("asr_commonvoice")


def run_backend(
    component_id: str,
    result_root: Path,
    protocol_root: Path,
    *,
    smoke: bool = False,
    concurrent_model_limit: int = 1,
) -> dict[str, object]:
    """Run one exact backend, reusing only validated successful item artifacts."""

    if component_id not in MODEL_COMPONENT_IDS:
        raise ASRCommonVoiceError(f"unsupported campaign backend: {component_id}")
    if concurrent_model_limit not in {1, 2, 3}:
        raise ASRCommonVoiceError("concurrent model limit must be 1, 2, or 3")
    protocol = validate_protocol(protocol_root)
    model = next(row for row in resolve_models() if row["component_id"] == component_id)
    _validate_runtime(model)
    if not smoke:
        _require_clean_scientific_sources()
    rows = read_manifest(protocol_root)
    if smoke:
        ids = set(read_smoke_ids(protocol_root))
        rows = [row for row in rows if str(row["item_id"]) in ids]
    expected = 9 if smoke else 11685
    if len(rows) != expected:
        raise ASRCommonVoiceError(f"run selection must contain {expected} items")

    mode = "smoke_non_scientific" if smoke else "scientific_full"
    campaign_id = campaign_identity(protocol)
    backend_run_id = f"run_{canonical_sha256({'campaign_id': campaign_id, 'component_id': component_id, 'git_sha': git_sha(), 'mode': mode, 'concurrent_model_limit': concurrent_model_limit})[:16].lower()}"
    backend_root = (result_root.resolve() / component_id).resolve()
    items_root = backend_root / "items"
    backend_root.mkdir(parents=True, exist_ok=True)
    identity = {
        "schema_version": "asr-commonvoice-backend-identity.v1",
        "campaign_id": campaign_id,
        "backend_run_id": backend_run_id,
        "mode": mode,
        "scientific_use_prohibited": smoke,
        "protocol_id": protocol["protocol_id"],
        "protocol_manifest_sha256": protocol["manifest_sha256"],
        "implementation_sha256": implementation_sha256(),
        "repository_git_sha": git_sha(),
        "execution": {
            "concurrent_model_limit": concurrent_model_limit,
            "resource_metrics_collected_during_concurrent_models": concurrent_model_limit > 1,
        },
        "model": model,
        "host": {
            "node": platform.node(),
            "platform": platform.platform(),
            "python": sys.version,
            "processor": platform.processor(),
        },
    }
    identity_path = backend_root / "backend_identity.json"
    if identity_path.is_file():
        prior = json.loads(identity_path.read_text(encoding="utf-8"))
        if prior != identity:
            raise ASRCommonVoiceError(
                f"result directory contains a different backend identity: {backend_root}"
            )
    else:
        write_json_atomic(identity_path, identity)

    resolution = resolve_pipeline(
        BASE_INFERENCE_CONFIG,
        component_overrides={"asr": component_id},
        setting_overrides={
            "runtime.dry_run": False,
            "runtime.allow_model_downloads": False,
            "runtime.device": "cpu",
            "runtime.sample_rate_hz": 16000,
            "runtime.max_batch_size": 1,
            # Disabled means PipelineRunner uses its established full-record
            # fallback. The base config's enabled NoOpSegmenter intentionally
            # emits zero segments and is only suitable for dry-run plumbing.
            "components.vad.enabled": False,
            "components.segmentation.enabled": False,
        },
        environment_profile=str(model["environment_profile"]),
    )
    resolution.write_artifacts(backend_root / "inference")
    pipeline = PipelineRunner.from_config(resolution.pipeline_config)
    started = time.perf_counter()
    completed = 0
    reused = 0
    failed = 0
    total_audio = sum(float(row["duration_sec"]) for row in rows)
    processed_audio = 0.0
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    for index, row in enumerate(rows, start=1):
        item_path = _item_path(items_root, str(row["item_id"]))
        prior = _valid_success(item_path, backend_run_id, row)
        if prior is not None:
            completed += 1
            reused += 1
            processed_audio += float(row["duration_sec"])
            _write_progress(
                backend_root, component_id, mode, index, len(rows), completed,
                failed, reused, started, processed_audio, total_audio, row,
                concurrent_model_limit,
            )
            continue
        item_started = time.perf_counter()
        cpu_before = _process_cpu_seconds(process)
        audio_path = resolve_data_path_from_logical(str(row["logical_audio_path"]))
        record = {
            "recording_id": str(row["source_recording_id"]),
            "utt_id": str(row["item_id"]),
            "inference_audio_path": str(audio_path),
            "start_sec": 0.0,
            "end_sec": float(row["duration_sec"]),
            "duration_sec": float(row["duration_sec"]),
            "sample_rate_hz": int(row["sample_rate_hz"]),
            "source_recording_id": str(row["source_recording_id"]),
            "augmentation_mode": "none",
        }
        try:
            output = pipeline.predict(record, {"runtime": resolution.pipeline_config.runtime.to_jsonable()})
            elapsed = time.perf_counter() - item_started
            raw_hypothesis = getattr(pipeline.asr, "last_raw_text", None)
            hypothesis = str(output.text or "")
            scored = _score(row, hypothesis)
            payload = {
                "schema_version": RESULT_SCHEMA_VERSION,
                "status": "ok",
                "backend_run_id": backend_run_id,
                "component_id": component_id,
                "item_id": row["item_id"],
                "speaker_key": row["speaker_key"],
                "age_category": row["age_category"],
                "duration_sec": row["duration_sec"],
                "reference_text": row["reference_text"],
                "reference_normalized": row["reference_normalized"],
                "hypothesis_raw": str(raw_hypothesis if raw_hypothesis is not None else hypothesis),
                "hypothesis_text": hypothesis,
                **scored,
                "elapsed_sec": elapsed,
                "process_cpu_sec": _process_cpu_seconds(process) - cpu_before,
                "process_rss_mb": process.memory_info().rss / (1024 * 1024),
                "realtime_factor": elapsed / float(row["duration_sec"]),
                "warnings": list(output.warnings or ()),
                "asr_backend_runtime": dict(output.diagnostics or {}).get("asr_backend_runtime"),
            }
            write_json_atomic(item_path, payload)
            completed += 1
        except Exception as exc:  # item boundary intentionally preserves campaign progress
            failed += 1
            payload = {
                "schema_version": RESULT_SCHEMA_VERSION,
                "status": "failed",
                "backend_run_id": backend_run_id,
                "component_id": component_id,
                "item_id": row["item_id"],
                "error_type": type(exc).__name__,
                "message": _safe_message(str(exc)),
                "elapsed_sec": time.perf_counter() - item_started,
                "process_cpu_sec": _process_cpu_seconds(process) - cpu_before,
                "process_rss_mb": process.memory_info().rss / (1024 * 1024),
            }
            write_json_atomic(item_path, payload)
        processed_audio += float(row["duration_sec"])
        peak_rss = max(peak_rss, process.memory_info().rss)
        _write_progress(
            backend_root, component_id, mode, index, len(rows), completed,
            failed, reused, started, processed_audio, total_audio, row,
            concurrent_model_limit,
        )

    rows_out = _load_results(items_root, backend_run_id, rows)
    write_jsonl_atomic(backend_root / "predictions.jsonl", rows_out)
    write_parquet_atomic(backend_root / "utterance_results.parquet", pa.Table.from_pylist(rows_out))
    elapsed_total = time.perf_counter() - started
    success_rows = [row for row in rows_out if row["status"] == "ok"]
    summary = {
        "schema_version": "asr-commonvoice-backend-summary.v1",
        "component_id": component_id,
        "backend_run_id": backend_run_id,
        "campaign_id": campaign_id,
        "mode": mode,
        "scientific_use_prohibited": smoke,
        "expected_items": len(rows),
        "successful_items": len(success_rows),
        "failed_items": len(rows_out) - len(success_rows),
        "reused_items_this_invocation": reused,
        "elapsed_sec_this_invocation": elapsed_total,
        "audio_duration_sec": total_audio,
        "aggregate_wer": _micro_wer(success_rows),
        "aggregate_cer": _micro_cer(success_rows),
        "empty_output_count": sum(not str(row.get("hypothesis_normalized") or "") for row in success_rows),
        "realtime_factor_this_invocation": elapsed_total / total_audio,
        "peak_process_rss_mb_this_invocation": peak_rss / (1024 * 1024),
        "concurrent_model_limit": concurrent_model_limit,
        "resource_metrics_collected_during_concurrent_models": concurrent_model_limit > 1,
        "complete": len(success_rows) == len(rows),
    }
    write_json_atomic(backend_root / "summary.json", summary)
    validation = validate_backend(backend_root, protocol_root)
    write_json_atomic(backend_root / "validation.json", validation)
    if smoke and not validation["valid"]:
        raise ASRCommonVoiceError(
            f"NON-SCIENTIFIC SMOKE failed output validation for {component_id}"
        )
    return summary


def validate_backend(backend_root: Path, protocol_root: Path) -> dict[str, object]:
    identity = _read_json(backend_root / "backend_identity.json")
    protocol = validate_protocol(protocol_root)
    if identity["protocol_id"] != protocol["protocol_id"]:
        raise ASRCommonVoiceError("backend result protocol identity mismatch")
    all_rows = read_manifest(protocol_root)
    if identity["mode"] == "smoke_non_scientific":
        ids = set(read_smoke_ids(protocol_root))
        all_rows = [row for row in all_rows if row["item_id"] in ids]
    results = _load_results(backend_root / "items", str(identity["backend_run_id"]), all_rows)
    failures = [row for row in results if row["status"] != "ok"]
    empty_outputs = sum(
        row["status"] == "ok" and not str(row.get("hypothesis_normalized") or "")
        for row in results
    )
    smoke_output_valid = identity["mode"] != "smoke_non_scientific" or empty_outputs == 0
    return {
        "schema_version": "asr-commonvoice-backend-validation.v1",
        "valid": not failures and len(results) == len(all_rows) and smoke_output_valid,
        "component_id": identity["model"]["component_id"],
        "expected_items": len(all_rows),
        "observed_items": len(results),
        "successful_items": len(results) - len(failures),
        "failed_items": len(failures),
        "empty_output_items": empty_outputs,
        "mode": identity["mode"],
        "scientific_use_prohibited": identity["scientific_use_prohibited"],
    }


def status(result_root: Path, protocol_root: Path) -> dict[str, object]:
    protocol = validate_protocol(protocol_root)
    models: list[dict[str, object]] = []
    for component_id in MODEL_COMPONENT_IDS:
        root = result_root.resolve() / component_id
        if not (root / "backend_identity.json").is_file():
            models.append({"component_id": component_id, "state": "not_started"})
            continue
        validation = (
            _read_json(root / "validation.json")
            if (root / "validation.json").is_file()
            else None
        )
        progress = _read_json(root / "progress.json") if (root / "progress.json").is_file() else {}
        pid = int(progress.get("pid") or 0)
        running = False
        if pid and psutil.pid_exists(pid):
            try:
                active = psutil.Process(pid)
                running = True
                progress["live_process_cpu_percent"] = active.cpu_percent(interval=0.0)
                progress["live_process_rss_mb"] = active.memory_info().rss / (1024 * 1024)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
        state = (
            "complete"
            if validation and validation.get("valid") is True
            else "running"
            if running
            else "incomplete"
        )
        models.append({"component_id": component_id, "state": state, "validation": validation, "progress": progress})
    return {
        "schema_version": "asr-commonvoice-status.v1",
        "campaign_id": campaign_identity(protocol),
        "protocol_id": protocol["protocol_id"],
        "result_root": str(result_root.resolve()),
        "models": models,
        "all_complete": all(row["state"] == "complete" for row in models),
    }


def _score(row: Mapping[str, object], hypothesis: str) -> dict[str, object]:
    spec = TextNormalizationSpec(lowercase=True, remove_punctuation=True, strip_whitespace=True, collapse_whitespace=True)
    normalized = normalize_for_scoring(hypothesis, spec)
    reference = str(row["reference_normalized"])
    wer = compute_wer(reference, normalized)
    return {
        "hypothesis_normalized": normalized,
        "wer": wer.wer,
        "errors": wer.errors,
        "substitutions": wer.substitutions,
        "deletions": wer.deletions,
        "insertions": wer.insertions,
        "reference_words": wer.reference_words,
        "hypothesis_words": wer.hypothesis_words,
        "cer": character_error_rate(reference, normalized),
    }


def _micro_wer(rows: Sequence[Mapping[str, object]]) -> float | None:
    denominator = sum(int(row.get("reference_words") or 0) for row in rows)
    return sum(int(row.get("errors") or 0) for row in rows) / denominator if denominator else None


def _micro_cer(rows: Sequence[Mapping[str, object]]) -> float | None:
    denominator = sum(len(str(row.get("reference_normalized") or "").replace(" ", "")) for row in rows)
    numerator = sum(float(row.get("cer") or 0.0) * len(str(row.get("reference_normalized") or "").replace(" ", "")) for row in rows)
    return numerator / denominator if denominator else None


def _item_path(root: Path, item_id: str) -> Path:
    return root / item_id[-2:] / f"{item_id}.json"


def _valid_success(path: Path, backend_run_id: str, row: Mapping[str, object]) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if value.get("status") != "ok" or value.get("backend_run_id") != backend_run_id or value.get("item_id") != row["item_id"]:
        return None
    return value


def _load_results(root: Path, backend_run_id: str, manifest: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for row in manifest:
        path = _item_path(root, str(row["item_id"]))
        if not path.is_file():
            results.append({"schema_version": RESULT_SCHEMA_VERSION, "status": "missing", "backend_run_id": backend_run_id, "item_id": row["item_id"]})
            continue
        result = _read_json(path)
        if result.get("backend_run_id") != backend_run_id:
            results.append({"schema_version": RESULT_SCHEMA_VERSION, "status": "identity_mismatch", "backend_run_id": backend_run_id, "item_id": row["item_id"]})
        else:
            results.append(result)
    return results


def _write_progress(
    root: Path, component: str, mode: str, attempted: int, total: int,
    completed: int, failed: int, reused: int, started: float,
    processed_audio: float, total_audio: float, row: Mapping[str, object],
    concurrent_model_limit: int,
) -> None:
    elapsed = max(time.perf_counter() - started, 1e-9)
    remaining_audio = max(total_audio - processed_audio, 0.0)
    rtf = elapsed / processed_audio if processed_audio else None
    payload = {
        "schema_version": "asr-commonvoice-progress.v1",
        "component_id": component,
        "mode": mode,
        "pid": os.getpid(),
        "attempted_items": attempted,
        "completed_items": completed,
        "failed_items": failed,
        "reused_items": reused,
        "total_items": total,
        "percent": 100.0 * attempted / total,
        "current_item_id": row["item_id"],
        "elapsed_sec": elapsed,
        "processed_audio_sec": processed_audio,
        "total_audio_sec": total_audio,
        "observed_realtime_factor": rtf,
        "estimated_remaining_sec": remaining_audio * rtf if rtf is not None else None,
        "clips_per_sec": attempted / elapsed,
        "processed_audio_hours": processed_audio / 3600.0,
        "latest_result_activity_utc": datetime.now(timezone.utc).isoformat(),
        "concurrent_model_limit": concurrent_model_limit,
        "resource_metrics_collected_during_concurrent_models": concurrent_model_limit > 1,
    }
    try:
        write_json_atomic(root / "progress.json", payload)
    except PermissionError:
        # A monitor or scanner may briefly hold the replace target on Windows.
        # Progress is non-scientific and must never abort a backend run.
        LOGGER.warning("progress update skipped because progress.json remained locked")


def _validate_runtime(model: Mapping[str, object]) -> None:
    expected = Path(str(model["environment_interpreter"])).resolve()
    actual = Path(sys.executable).resolve()
    if actual != expected:
        raise ASRCommonVoiceError(f"{model['component_id']} requires {expected}; current interpreter is {actual}")
    if not model["asset_ready"] or not model["environment_ready"]:
        raise ASRCommonVoiceError(f"qualified local prerequisites are not ready for {model['component_id']}")


def _require_clean_scientific_sources() -> None:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", "Software Validation from Datasets/Evaluation Tool/app/asr_commonvoice", "Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/asr_commonvoice_60plus.v1.yaml", "Software Validation from Datasets/Evaluation Tool/benchmarks/asr_commonvoice", "Software Validation from Datasets/Evaluation Tool/scripts/run_asr_commonvoice_60plus.ps1"],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0 or completed.stdout.strip():
        raise ASRCommonVoiceError("scientific Run requires committed, clean campaign code/config/protocol/wrapper paths")


def _safe_message(value: str) -> str:
    return value.replace(str(Path.cwd()), "<repository_root>").replace(str(Path.cwd()).replace("\\", "/"), "<repository_root>")


def _process_cpu_seconds(process: psutil.Process) -> float:
    times = process.cpu_times()
    return float(times.user + times.system)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ASRCommonVoiceError(f"expected JSON object: {path}")
    return value
