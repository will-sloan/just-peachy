"""Restart-safe development-only Product V2 campaign controller."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Mapping, Sequence

import yaml

from app.controlled_diarization.contracts import (
    TOOL_ROOT,
    load_config,
    load_pipeline_registry,
    sha256_file,
)
from app.controlled_diarization.runner import pipeline_status, queue_status
from app.diarization_evaluation.artifacts import write_json_atomic, write_text_atomic
from app.diarization_product_v2.contracts import (
    DEFAULT_ANALYSIS_ROOT,
    DEFAULT_CONFIG_PATH,
    DEFAULT_FROZEN_CONFIG_PATH,
    DEFAULT_GENERATED_ROOT,
    DEFAULT_PROGRESS_PATH,
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_RESULT_ROOT,
    DEFAULT_SELECTION_PATH,
    DEFAULT_STATE_PATH,
    ORACLE_PIPELINES,
    PRIMARY_PIPELINES,
    V1_GENERATED_ROOT,
    V1_PROTOCOL_ROOT,
)
from app.diarization_product_v2.protocol import (
    prepare_product_protocol,
    validate_product_protocol,
)


CALIBRATED_PIPELINES = (
    "modular_pyannote_wespeaker",
    "modular_pyannote_redimnet2",
    "modular_pyannote_speechbrain_ecapa",
)
THRESHOLD_GRID = (0.35, 0.45, 0.55, 0.65)


def audit() -> dict[str, object]:
    prepared = prepare_product_protocol()
    status = pipeline_status(config_path=DEFAULT_CONFIG_PATH)
    result = {
        "schema_version": "diarization-product-audit.v2",
        "protocol_id": prepared["protocol_summary"]["protocol_id"],
        "protocol_validation": prepared["validation"],
        "v1_protocol_id": json.loads(
            (V1_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8")
        )["benchmark_id"],
        "pipeline_status": status,
        "all_primary_pipelines_executable": all(
            row["executable_on_this_machine"]
            for row in status["pipelines"]
            if row["pipeline_id"] in PRIMARY_PIPELINES
        ),
        "evaluation_results_inspected": False,
        "known_speaker_attribution_enabled": False,
        "asr_enabled": False,
    }
    write_json_atomic(DEFAULT_RESULT_ROOT / "audit.json", result)
    return result


def validate() -> dict[str, object]:
    v2 = validate_product_protocol()
    v1 = json.loads((V1_PROTOCOL_ROOT / "validation_report.json").read_text(encoding="utf-8"))
    result = {
        "schema_version": "diarization-product-combined-validation.v2",
        "valid": bool(v1.get("valid")) and bool(v2.get("valid")),
        "v1": v1,
        "v2": v2,
        "evaluation_results_inspected": False,
    }
    write_json_atomic(DEFAULT_RESULT_ROOT / "validation.json", result)
    return result


def plan() -> dict[str, object]:
    prepare_product_protocol()
    protocols = []
    total_cases = total_audio = 0.0
    for name, root in (("controlled_v1", V1_PROTOCOL_ROOT), ("product_v2", DEFAULT_PROTOCOL_ROOT)):
        cases = _read_jsonl(root / "development" / "case_manifest.jsonl")
        seconds = sum(float(row["duration_sec"]) for row in cases)
        protocols.append(
            {
                "name": name,
                "protocol_id": cases[0]["benchmark_id"],
                "development_cases": len(cases),
                "development_audio_sec": seconds,
                "evaluation_cases_planned_but_not_authorized": len(
                    _read_jsonl(root / "evaluation" / "case_manifest.jsonl")
                ),
            }
        )
        total_cases += len(cases)
        total_audio += seconds
    readiness = pipeline_status(config_path=DEFAULT_CONFIG_PATH)
    reusable = _completed_primary_units()
    planned_units = int(total_cases) * len(PRIMARY_PIPELINES)
    # Broad pre-run estimate until measured smoke telemetry is available.
    estimate = {
        "label": "ESTIMATE",
        "basis": "audio hours and qualified CPU pipeline family; refined by measured progress",
        "low_hours": total_audio / 3600 * 0.35,
        "expected_hours": total_audio / 3600 * 0.85,
        "high_hours": total_audio / 3600 * 1.8,
        "parallel_pipeline_workers": 2,
    }
    result = {
        "schema_version": "diarization-product-plan.v2",
        "protocols": protocols,
        "pipelines": list(PRIMARY_PIPELINES),
        "oracle_diagnostics": list(ORACLE_PIPELINES),
        "development_cases_per_pipeline": int(total_cases),
        "total_inference_units": planned_units,
        "development_audio_hours_per_pipeline": total_audio / 3600,
        "aggregate_audio_hours": total_audio * len(PRIMARY_PIPELINES) / 3600,
        "segmentation_cache": {
            "shared_across": list(CALIBRATED_PIPELINES),
            "same_window_manifest": True,
            "expected_unique_segmentation_cases": int(total_cases),
        },
        "embedding_jobs": "derived exactly from cached shared window manifests",
        "reusable_valid_units": reusable,
        "result_root": str(DEFAULT_RESULT_ROOT),
        "available_assets_and_environments": readiness,
        "runtime_estimate": estimate,
        "controlled_evaluation_authorized": False,
    }
    write_json_atomic(DEFAULT_RESULT_ROOT / "plan.json", result)
    return result


def smoke() -> dict[str, object]:
    prepare_product_protocol()
    root = DEFAULT_RESULT_ROOT / "engineering_smoke"
    shared = DEFAULT_RESULT_ROOT / "_shared_cache"
    rows = []
    for pipeline in CALIBRATED_PIPELINES:
        result_root = root / pipeline
        completed = _invoke_queue(
            config=DEFAULT_CONFIG_PATH,
            benchmark=DEFAULT_PROTOCOL_ROOT,
            generated=DEFAULT_GENERATED_ROOT,
            result=result_root,
            pipeline=pipeline,
            max_cases=1,
            shared_cache=shared,
        )
        rows.append(
            {
                "pipeline_id": pipeline,
                "returncode": completed.returncode,
                "log": str(result_root / "controller.log"),
                "status": queue_status(
                    pipelines=[pipeline],
                    tiers=["development"],
                    config_path=DEFAULT_CONFIG_PATH,
                    benchmark_root=DEFAULT_PROTOCOL_ROOT,
                    result_root=result_root,
                ),
            }
        )
        if completed.returncode:
            raise RuntimeError(f"engineering smoke failed for {pipeline}")
    # The second and third modular paths must reuse the first segmentation.
    technical = []
    for path in root.rglob("technical_coverage.json"):
        technical.append(json.loads(path.read_text(encoding="utf-8")))
    result = {
        "schema_version": "diarization-product-engineering-smoke.v2",
        "scientific": False,
        "pipelines": rows,
        "technical_coverage": technical,
        "segmentation_cache_reuse_observed": any(
            bool(row.get("segmentation_cache_reused")) for row in technical
        ),
    }
    write_json_atomic(root / "smoke_summary.json", result)
    return result


def run(*, parallel_pipelines: int = 2) -> dict[str, object]:
    """Run calibration and both development protocols, then analyze/freeze/export."""

    if parallel_pipelines < 1 or parallel_pipelines > 3:
        raise ValueError("parallel_pipelines must be 1-3")
    DEFAULT_RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    for stop_marker in (
        DEFAULT_RESULT_ROOT / "STOP_REQUESTED",
        DEFAULT_RESULT_ROOT / "v1" / "STOP_REQUESTED",
        DEFAULT_RESULT_ROOT / "v2" / "STOP_REQUESTED",
    ):
        stop_marker.unlink(missing_ok=True)
    for active_marker in DEFAULT_RESULT_ROOT.glob("pipeline_active.*.json"):
        active_marker.unlink(missing_ok=True)
    prepared = prepare_product_protocol()
    validation = validate()
    if not validation["valid"]:
        raise RuntimeError("protocol validation failed")
    _state("RUNNING", "development_calibration", "Calibrating clustering on V2 development only")
    thresholds = _calibrate()
    frozen_config = _freeze_runtime_config(thresholds)
    _state("RUNNING", "controlled_development", "Running V1 and V2 development; evaluation locked")
    _initialize_progress(frozen_config)
    errors = _run_primary_campaign(frozen_config, parallel_pipelines)
    _refresh_progress(frozen_config)
    if errors:
        _state("FAILED", "controlled_development", "; ".join(errors), errors[-1])
        raise RuntimeError("; ".join(errors))
    _state("RUNNING", "oracle_diagnostics", "Running bounded development-only oracle diagnostics")
    oracle = _run_oracles(frozen_config)
    _state("RUNNING", "analysis", "Analyzing development evidence only")
    from app.diarization_product_v2.analysis import analyze_and_freeze

    analysis = analyze_and_freeze(config_path=frozen_config)
    _state("COMPLETE", "frozen", "Development selection frozen; evaluation not inspected")
    return {
        "schema_version": "diarization-product-run.v2",
        "protocol_id": prepared["protocol_summary"]["protocol_id"],
        "thresholds": thresholds,
        "frozen_runtime_config": str(frozen_config),
        "oracle_diagnostics": oracle,
        "analysis": analysis,
        "selection_file": str(DEFAULT_SELECTION_PATH),
        "evaluation_run": False,
    }


def status() -> dict[str, object]:
    state = _read_json(DEFAULT_STATE_PATH) or {
        "status": "NOT_STARTED",
        "stage": "not_started",
    }
    progress = _read_json(DEFAULT_PROGRESS_PATH)
    config = DEFAULT_FROZEN_CONFIG_PATH if DEFAULT_FROZEN_CONFIG_PATH.is_file() else DEFAULT_CONFIG_PATH
    return {
        "schema_version": "diarization-product-status.v2",
        "controller": state,
        "progress": progress,
        "v1": _safe_queue_status(V1_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v1", config),
        "v2": _safe_queue_status(DEFAULT_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v2", config),
        "selection_exists": DEFAULT_SELECTION_PATH.is_file(),
        "evaluation_results_inspected": False,
    }


def stop() -> dict[str, object]:
    write_text_atomic(DEFAULT_RESULT_ROOT / "STOP_REQUESTED", "graceful stop requested\n")
    for root in (DEFAULT_RESULT_ROOT / "v1", DEFAULT_RESULT_ROOT / "v2"):
        write_text_atomic(root / "STOP_REQUESTED", "graceful stop requested\n")
    return {"status": "STOP_REQUESTED", "scope": "between controlled development cases"}


def analyze() -> dict[str, object]:
    from app.diarization_product_v2.analysis import analyze_and_freeze

    config = DEFAULT_FROZEN_CONFIG_PATH if DEFAULT_FROZEN_CONFIG_PATH.is_file() else DEFAULT_CONFIG_PATH
    return analyze_and_freeze(config_path=config)


def collect() -> dict[str, object]:
    from app.diarization_product_v2.analysis import collect_package

    return collect_package()


def _calibrate() -> dict[str, float]:
    shared = DEFAULT_RESULT_ROOT / "_shared_cache"
    thresholds: dict[str, float] = {}
    rows = []
    for pipeline in CALIBRATED_PIPELINES:
        candidates = []
        for threshold in THRESHOLD_GRID:
            config = DEFAULT_RESULT_ROOT / "calibration" / pipeline / f"threshold_{threshold:.2f}.yaml"
            _write_threshold_config(DEFAULT_CONFIG_PATH, config, {pipeline: threshold})
            result = DEFAULT_RESULT_ROOT / "calibration" / pipeline / f"threshold_{threshold:.2f}"
            completed = _invoke_queue(
                config=config,
                benchmark=DEFAULT_PROTOCOL_ROOT,
                generated=DEFAULT_GENERATED_ROOT,
                result=result,
                pipeline=pipeline,
                max_cases=8,
                shared_cache=shared,
            )
            if completed.returncode:
                raise RuntimeError(f"calibration failed: {pipeline} threshold={threshold}")
            metrics = [
                json.loads(path.read_text(encoding="utf-8"))["primary_strict"]
                for path in result.rglob("metrics/summary.json")
            ]
            ders = [float(row["der"]) for row in metrics if row.get("metrics_emitted")]
            confusion = [
                float(row["speaker_confusion_sec"]) / max(float(row["reference_speaker_time_sec"]), 1e-9)
                for row in metrics
                if row.get("metrics_emitted")
            ]
            value = {
                "pipeline_id": pipeline,
                "threshold": threshold,
                "valid_cases": len(ders),
                "mean_der": sum(ders) / len(ders) if ders else None,
                "mean_confusion_rate": sum(confusion) / len(confusion) if confusion else None,
                "selection_key": [
                    sum(confusion) / len(confusion) if confusion else 1e9,
                    sum(ders) / len(ders) if ders else 1e9,
                    threshold,
                ],
            }
            rows.append(value)
            candidates.append(value)
        chosen = min(candidates, key=lambda row: tuple(row["selection_key"]))
        thresholds[pipeline] = float(chosen["threshold"])
    write_json_atomic(
        DEFAULT_RESULT_ROOT / "calibration" / "development_calibration.json",
        {
            "schema_version": "diarization-product-development-calibration.v1",
            "development_only": True,
            "evaluation_inspected": False,
            "calibration_cases": 8,
            "grid": list(THRESHOLD_GRID),
            "rows": rows,
            "selected": thresholds,
        },
    )
    return thresholds


def _freeze_runtime_config(thresholds: Mapping[str, float]) -> Path:
    updates = dict(thresholds)
    wespeaker = float(thresholds["modular_pyannote_wespeaker"])
    updates["modular_energy_wespeaker"] = wespeaker
    updates["oracle_turn_wespeaker_diagnostic"] = wespeaker
    updates["oracle_turn_redimnet2_diagnostic"] = float(
        thresholds["modular_pyannote_redimnet2"]
    )
    updates["oracle_turn_speechbrain_diagnostic"] = float(
        thresholds["modular_pyannote_speechbrain_ecapa"]
    )
    _write_threshold_config(DEFAULT_CONFIG_PATH, DEFAULT_FROZEN_CONFIG_PATH, updates)
    return DEFAULT_FROZEN_CONFIG_PATH


def _write_threshold_config(source: Path, destination: Path, updates: Mapping[str, float]) -> None:
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    for row in payload["pipelines"]["definitions"]:
        if row["pipeline_id"] in updates:
            row.setdefault("configuration", {})["clustering_threshold"] = float(
                updates[row["pipeline_id"]]
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(destination, yaml.safe_dump(payload, sort_keys=False))


def _run_primary_campaign(config: Path, parallel_pipelines: int) -> list[str]:
    """Poll pipeline subprocesses directly so progress cannot deadlock on threads."""

    stages = (
        ("v1", V1_PROTOCOL_ROOT, V1_GENERATED_ROOT, DEFAULT_RESULT_ROOT / "v1"),
        ("v2", DEFAULT_PROTOCOL_ROOT, DEFAULT_GENERATED_ROOT, DEFAULT_RESULT_ROOT / "v2"),
    )
    pending = list(PRIMARY_PIPELINES)
    active: dict[str, dict[str, object]] = {}
    errors: list[str] = []

    def start(pipeline: str, stage_index: int) -> None:
        label, benchmark, generated, result = stages[stage_index]
        result.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(TOOL_ROOT / "run_evaluation.py"),
            "diarization-benchmark",
            "run",
            "--tier", "development",
            "--pipeline", pipeline,
            "--config", str(config.resolve()),
            "--benchmark-root", str(benchmark.resolve()),
            "--generated-root", str(generated.resolve()),
            "--result-root", str(result.resolve()),
        ]
        environment = os.environ.copy()
        environment["JP_DIARIZATION_SHARED_CACHE_ROOT"] = str(
            (DEFAULT_RESULT_ROOT / "_shared_cache").resolve()
        )
        environment["JP_DIARIZATION_PIPELINE_STATE"] = "1"
        stream = (result / "controller.log").open("a", encoding="utf-8", newline="\n")
        stream.write(f"\n[{_now()}] {' '.join(command)}\n")
        stream.flush()
        marker = DEFAULT_RESULT_ROOT / f"pipeline_active.{pipeline}.json"
        write_json_atomic(
            marker,
            {
                "pipeline_id": pipeline,
                "protocol": label,
                "status": "RUNNING",
                "started_at": _now(),
            },
        )
        process = subprocess.Popen(
            command,
            cwd=TOOL_ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        active[pipeline] = {
            "process": process,
            "stage_index": stage_index,
            "stream": stream,
            "marker": marker,
        }

    while pending or active:
        while pending and len(active) < parallel_pipelines and not (
            DEFAULT_RESULT_ROOT / "STOP_REQUESTED"
        ).is_file():
            start(pending.pop(0), 0)
        _refresh_progress(config)
        stopping = (DEFAULT_RESULT_ROOT / "STOP_REQUESTED").is_file()
        if stopping:
            for root in (DEFAULT_RESULT_ROOT / "v1", DEFAULT_RESULT_ROOT / "v2"):
                write_text_atomic(root / "STOP_REQUESTED", "graceful stop requested\n")
        for pipeline, value in list(active.items()):
            process = value["process"]
            returncode = process.poll()  # type: ignore[union-attr]
            if returncode is None:
                continue
            value["stream"].close()  # type: ignore[union-attr]
            stage_index = int(value["stage_index"])
            if returncode != 0:
                errors.append(f"{pipeline}: queue stage {stages[stage_index][0]} failed with exit code {returncode}")
                Path(value["marker"]).unlink(missing_ok=True)
                del active[pipeline]
            elif stopping:
                errors.append(f"{pipeline}: STOP_REQUESTED")
                Path(value["marker"]).unlink(missing_ok=True)
                del active[pipeline]
            elif stage_index + 1 < len(stages):
                start(pipeline, stage_index + 1)
            else:
                Path(value["marker"]).unlink(missing_ok=True)
                del active[pipeline]
        if stopping and not active:
            errors.extend(f"{pipeline}: STOP_REQUESTED" for pipeline in pending)
            pending.clear()
        if pending or active:
            time.sleep(2)
    return errors


def _run_oracles(config: Path) -> list[dict[str, object]]:
    rows = []
    for pipeline in ORACLE_PIPELINES:
        root = DEFAULT_RESULT_ROOT / "oracle" / pipeline
        completed = _invoke_queue(
            config=config,
            benchmark=DEFAULT_PROTOCOL_ROOT,
            generated=DEFAULT_GENERATED_ROOT,
            result=root,
            pipeline=pipeline,
            max_cases=6,
            shared_cache=DEFAULT_RESULT_ROOT / "_shared_cache",
        )
        rows.append({"pipeline_id": pipeline, "returncode": completed.returncode, "max_cases": 6})
    write_json_atomic(DEFAULT_RESULT_ROOT / "oracle" / "oracle_summary.json", {"rows": rows})
    return rows


def _invoke_queue(
    *, config: Path, benchmark: Path, generated: Path, result: Path,
    pipeline: str, max_cases: int | None, shared_cache: Path,
) -> subprocess.CompletedProcess[str]:
    result.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(TOOL_ROOT / "run_evaluation.py"),
        "diarization-benchmark",
        "run",
        "--tier", "development",
        "--pipeline", pipeline,
        "--config", str(config.resolve()),
        "--benchmark-root", str(benchmark.resolve()),
        "--generated-root", str(generated.resolve()),
        "--result-root", str(result.resolve()),
    ]
    if max_cases is not None:
        command.extend(["--max-cases", str(max_cases)])
    environment = os.environ.copy()
    environment["JP_DIARIZATION_SHARED_CACHE_ROOT"] = str(shared_cache.resolve())
    environment["JP_DIARIZATION_PIPELINE_STATE"] = "1"
    log = result / "controller.log"
    with log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"\n[{_now()}] {' '.join(command)}\n")
        stream.flush()
        return subprocess.run(
            command,
            cwd=TOOL_ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            check=False,
        )


def _initialize_progress(config: Path) -> None:
    cases = {
        "v1": _read_jsonl(V1_PROTOCOL_ROOT / "development" / "case_manifest.jsonl"),
        "v2": _read_jsonl(DEFAULT_PROTOCOL_ROOT / "development" / "case_manifest.jsonl"),
    }
    rows = []
    for pipeline in PRIMARY_PIPELINES:
        planned = sum(len(value) for value in cases.values())
        seconds = sum(float(row["duration_sec"]) for value in cases.values() for row in value)
        rows.append(
            {
                "pipeline": pipeline,
                "phase": "WAITING",
                "status": "WAITING",
                "planned_cases": planned,
                "completed_cases": 0,
                "valid_cases": 0,
                "failed_cases": 0,
                "current_case": None,
                "planned_audio_seconds": seconds,
                "completed_audio_seconds": 0.0,
                "unit_percentage": 0.0,
                "audio_weighted_percentage": 0.0,
                "rolling_rtf": None,
                "current_rss_mb": _rss_mb(),
                "current_process_pid": os.getpid(),
                "last_error": None,
            }
        )
    # Populate the baseline from checksum-valid on-disk results before the first
    # refresh so resume reuse is never mistaken for newly measured throughput.
    case_maps = {
        "v1": {row["case_id"]: row for row in cases["v1"]},
        "v2": {row["case_id"]: row for row in cases["v2"]},
    }
    resume_audio = 0.0
    resume_units = 0
    for pipeline in PRIMARY_PIPELINES:
        for label, result in (("v1", DEFAULT_RESULT_ROOT / "v1"), ("v2", DEFAULT_RESULT_ROOT / "v2")):
            for case_id, case in case_maps[label].items():
                if (result / "development" / pipeline / str(case_id) / "run.json").is_file():
                    resume_audio += float(case["duration_sec"])
                    resume_units += 1
    write_json_atomic(
        DEFAULT_PROGRESS_PATH,
        {
            "schema_version": "diarization-product-progress.v2",
            "protocol_id": json.loads((DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))["protocol_id"],
            "tier": "development",
            "started_timestamp": _now(),
            "updated_timestamp": _now(),
            "overall_audio_weighted_percentage": 0.0,
            "overall_unit_percentage": 0.0,
            "elapsed_seconds": 0.0,
            "resume_completed_audio_seconds": resume_audio,
            "resume_completed_units": resume_units,
            "eta_seconds": None,
            "estimated_completion_clock_time": None,
            "pipelines": rows,
            "evaluation_results_inspected": False,
        },
    )


def _refresh_progress(config: Path) -> None:
    progress = _read_json(DEFAULT_PROGRESS_PATH)
    if not progress:
        return
    started = datetime.fromisoformat(str(progress["started_timestamp"]).replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    case_maps = {
        "v1": {row["case_id"]: row for row in _read_jsonl(V1_PROTOCOL_ROOT / "development" / "case_manifest.jsonl")},
        "v2": {row["case_id"]: row for row in _read_jsonl(DEFAULT_PROTOCOL_ROOT / "development" / "case_manifest.jsonl")},
    }
    output_rows = []
    for old in progress["pipelines"]:
        pipeline = str(old["pipeline"])
        completed = failed = 0
        seconds = inference = 0.0
        current = None
        for label, result in (("v1", DEFAULT_RESULT_ROOT / "v1"), ("v2", DEFAULT_RESULT_ROOT / "v2")):
            state = _read_json(result / f"queue_state.{pipeline}.json") or {}
            completed += int(state.get("valid", 0))
            failed += int(state.get("failed", 0))
            units = list(state.get("units") or [])
            if state.get("current_case"):
                current = state["current_case"]
            elif "current_case" not in state and units:
                current = units[-1].get("case_id")
            for case_id, case in case_maps[label].items():
                run_path = result / "development" / pipeline / str(case_id) / "run.json"
                if run_path.is_file():
                    run = _read_json(run_path) or {}
                    seconds += float(case["duration_sec"])
                    inference += float(dict(run.get("timing") or {}).get("diarization_inference_sec") or 0)
        planned = int(old["planned_cases"])
        planned_audio = float(old["planned_audio_seconds"])
        active = (DEFAULT_RESULT_ROOT / f"pipeline_active.{pipeline}.json").is_file()
        status_value = "COMPLETE" if completed == planned else ("RUNNING" if active or completed or current else "WAITING")
        output_rows.append(
            {
                **old,
                "phase": "COMPLETE" if status_value == "COMPLETE" else "DEVELOPMENT",
                "status": status_value,
                "completed_cases": completed,
                "valid_cases": completed,
                "failed_cases": failed,
                "current_case": current,
                "completed_audio_seconds": seconds,
                "unit_percentage": 100 * completed / planned if planned else 0.0,
                "audio_weighted_percentage": 100 * seconds / planned_audio if planned_audio else 0.0,
                "rolling_rtf": inference / seconds if seconds else None,
                "current_rss_mb": _rss_mb(),
                "current_process_pid": os.getpid(),
                "last_error": None,
            }
        )
    total_audio = sum(float(row["planned_audio_seconds"]) for row in output_rows)
    done_audio = sum(float(row["completed_audio_seconds"]) for row in output_rows)
    total_units = sum(int(row["planned_cases"]) for row in output_rows)
    done_units = sum(int(row["completed_cases"]) for row in output_rows)
    elapsed = (now - started).total_seconds()
    eta = _measured_eta_seconds(
        elapsed_seconds=elapsed,
        total_audio_seconds=total_audio,
        completed_audio_seconds=done_audio,
        resume_audio_seconds=float(progress.get("resume_completed_audio_seconds") or 0.0),
    )
    progress.update(
        {
            "updated_timestamp": _now(),
            "overall_audio_weighted_percentage": 100 * done_audio / total_audio if total_audio else 0.0,
            "overall_unit_percentage": 100 * done_units / total_units if total_units else 0.0,
            "elapsed_seconds": elapsed,
            "eta_seconds": eta,
            "estimated_completion_clock_time": (
                (now + timedelta(seconds=eta)).isoformat() if eta is not None else None
            ),
            "current_rss_mb": _rss_mb(),
            "current_process_pid": os.getpid(),
            "pipelines": output_rows,
        }
    )
    write_json_atomic(DEFAULT_PROGRESS_PATH, progress)


def _measured_eta_seconds(
    *, elapsed_seconds: float, total_audio_seconds: float,
    completed_audio_seconds: float, resume_audio_seconds: float,
) -> float | None:
    """Estimate remaining wall time only from materially new measured audio."""

    newly_completed_audio = max(0.0, completed_audio_seconds - resume_audio_seconds)
    # Ignore sub-second floating-point residue from summing the same resumed
    # durations in a different order. ETA begins only after real new audio.
    if elapsed_seconds < 30.0 or newly_completed_audio < 1.0:
        return None
    return max(
        0.0,
        elapsed_seconds
        * max(0.0, total_audio_seconds - completed_audio_seconds)
        / newly_completed_audio,
    )


def _completed_primary_units() -> int:
    total = 0
    config = DEFAULT_FROZEN_CONFIG_PATH if DEFAULT_FROZEN_CONFIG_PATH.is_file() else DEFAULT_CONFIG_PATH
    for benchmark, result in ((V1_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v1"), (DEFAULT_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v2")):
        if not result.exists():
            continue
        try:
            value = queue_status(
                pipelines=PRIMARY_PIPELINES,
                tiers=["development"],
                config_path=config,
                benchmark_root=benchmark,
                result_root=result,
            )
            total += sum(int(row["valid"]) for row in value["rows"])
        except Exception:
            pass
    return total


def _safe_queue_status(benchmark: Path, result: Path, config: Path) -> object:
    try:
        return queue_status(
            pipelines=PRIMARY_PIPELINES,
            tiers=["development"],
            config_path=config,
            benchmark_root=benchmark,
            result_root=result,
        )
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def _state(status_value: str, stage: str, detail: str, last_error: str | None = None) -> None:
    write_json_atomic(
        DEFAULT_STATE_PATH,
        {
            "schema_version": "diarization-product-controller.v2",
            "status": status_value,
            "stage": stage,
            "detail": detail,
            "updated_at": _now(),
            "pid": os.getpid(),
            "last_error": last_error,
            "evaluation_results_inspected": False,
        },
    )


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
