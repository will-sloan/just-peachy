"""Restart-safe Task-2 controller for the frozen standalone evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Mapping, Sequence

from app.controlled_diarization.benchmark import validate_benchmark
from app.controlled_diarization.contracts import TOOL_ROOT
from app.controlled_diarization.runner import execute_queue, queue_status
from app.diarization_evaluation.artifacts import write_json_atomic, write_text_atomic
from app.diarization_product_v2.protocol import validate_product_protocol
from app.diarization_final_evaluation.contracts import (
    ANALYSIS_ROOT,
    AUTHORIZATION_ROOT,
    FROZEN_RUNTIME_CONFIG,
    NATIVE_RESULT_ROOT,
    PROGRESS_PATH,
    RESULT_ROOT,
    SHARED_CACHE_ROOT,
    STATE_PATH,
    STOP_PATH,
    TASK1_NATIVE_ROOT,
    V1_GENERATED_ROOT,
    V1_PROTOCOL_ROOT,
    V1_RESULT_ROOT,
    V2_GENERATED_ROOT,
    V2_PROTOCOL_ROOT,
    V2_RESULT_ROOT,
)
from app.diarization_final_evaluation.decision import require_valid_decision, selected_pipelines
from app.diarization_final_evaluation.native import execute_native_queue, native_rows, validate_native_result


SCOPES = ("all", "controlled", "chime6", "voices")


def validate() -> dict[str, object]:
    decision = require_valid_decision()
    v1 = validate_benchmark(
        config_path=FROZEN_RUNTIME_CONFIG,
        benchmark_root=V1_PROTOCOL_ROOT,
        generated_root=V1_GENERATED_ROOT,
        verify_source_hashes=False,
    )
    v2 = validate_product_protocol()
    rows = native_rows()
    missing_audio = []
    from app.diarization_evaluation.manifests import DATA_ROOT

    for row in rows:
        if row["dataset"] in {"chime6", "voices"} and not (DATA_ROOT / str(row["audio_path_project_relative"])).is_file():
            missing_audio.append(str(row["audio_path_project_relative"]))
    result = {
        "schema_version": "diarization-final-validation.v1",
        "valid": bool(decision["valid"] and v1["valid"] and v2["valid"] and not missing_audio),
        "frozen_decision": decision,
        "controlled_v1": v1,
        "controlled_v2": v2,
        "native_manifest": {
            "path": str(TASK1_NATIVE_ROOT / "native_diarization_manifest.parquet"),
            "chime6_units": sum(row["dataset"] == "chime6" for row in rows),
            "voices_units": sum(row["dataset"] == "voices" for row in rows),
            "missing_audio_count": len(missing_audio),
            "voices_der_jer_suppressed": all(not row["der_jer_eligible"] for row in rows if row["dataset"] == "voices"),
        },
        "firewall": {
            "anonymous_diarization_only": True,
            "known_speaker_attribution": False,
            "enrollment_policy": False,
            "hybrid": False,
            "asr_cpwer": False,
            "fine_tuning": False,
            "evaluation_retuning_allowed": False,
        },
    }
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json_atomic(RESULT_ROOT / "validation.json", result)
    return result


def plan() -> dict[str, object]:
    value = validate()
    if not value["valid"]:
        raise RuntimeError("final evaluation validation failed")
    pipelines = selected_pipelines()
    phases = []
    for name, benchmark in (("controlled_v1", V1_PROTOCOL_ROOT), ("controlled_v2", V2_PROTOCOL_ROOT)):
        rows = _jsonl(benchmark / "evaluation" / "case_manifest.jsonl")
        phases.append({
            "phase": name,
            "dataset": "Common Voice controlled " + ("V1" if name.endswith("v1") else "Product V2"),
            "cases_per_pipeline": len(rows),
            "inference_units": len(rows) * len(pipelines),
            "audio_hours": sum(float(row["duration_sec"]) for row in rows) * len(pipelines) / 3600.0,
        })
    for dataset in ("chime6", "voices"):
        rows = native_rows(dataset)
        phases.append({
            "phase": dataset,
            "dataset": "CHiME-6 native small panel" if dataset == "chime6" else "VOiCES acoustic fragmentation diagnostic",
            "cases_per_pipeline": len(rows),
            "inference_units": len(rows) * len(pipelines),
            "audio_hours": sum(float(row["duration_sec"]) for row in rows) * len(pipelines) / 3600.0,
        })
    result = {
        "schema_version": "diarization-final-plan.v1",
        "selected_pipeline_ids": list(pipelines),
        "parallel_pipeline_range": [1, 2],
        "phases": phases,
        "total_inference_units": sum(int(row["inference_units"]) for row in phases),
        "total_audio_hours": sum(float(row["audio_hours"]) for row in phases),
        "restart_safe": True,
        "evaluation_retuning_prohibited": True,
        "result_root": str(RESULT_ROOT),
    }
    write_json_atomic(RESULT_ROOT / "plan.json", result)
    _refresh_progress()
    return result


def run(*, scope: str = "all", parallel_pipelines: int = 2) -> dict[str, object]:
    if scope not in SCOPES:
        raise ValueError(f"unsupported scope: {scope}")
    if parallel_pipelines not in {1, 2}:
        raise ValueError("parallel_pipelines must be 1 or 2")
    checked = validate()
    if not checked["valid"]:
        raise RuntimeError("frozen final-evaluation validation failed")
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    STOP_PATH.unlink(missing_ok=True)
    for root in (V1_RESULT_ROOT, V2_RESULT_ROOT):
        (root / "STOP_REQUESTED").unlink(missing_ok=True)
    for marker in RESULT_ROOT.glob("active.*.json"):
        marker.unlink(missing_ok=True)
    baseline = float(_refresh_progress()["completed_audio_seconds"])
    _state("RUNNING", "STARTING", f"Starting frozen final evaluation scope={scope}", start_new=True, baseline_audio=baseline)
    failures: list[str] = []
    try:
        if scope in {"all", "controlled"}:
            _state("RUNNING", "CONTROLLED_EVALUATION", "Running untouched controlled V1 and Product V2 evaluation")
            failures.extend(_run_parallel_workers("controlled", selected_pipelines(), parallel_pipelines))
        if not failures and scope in {"all", "chime6"} and not STOP_PATH.is_file():
            _state("RUNNING", "CHIME6_NATIVE_FINALISTS", "Running frozen finalists on the CHiME-6 native panel")
            failures.extend(_run_parallel_workers("chime6", selected_pipelines(), parallel_pipelines))
        if not failures and scope in {"all", "voices"} and not STOP_PATH.is_file():
            _state("RUNNING", "VOICES_ACOUSTIC_DIAGNOSTIC", "Running frozen finalists on VOiCES diagnostics")
            failures.extend(_run_parallel_workers("voices", selected_pipelines(), parallel_pipelines))
        _refresh_progress()
        if STOP_PATH.is_file():
            _state("STOPPED", "STOPPED", "Graceful stop honored between evaluation units")
        elif failures:
            _state("FAILED", "FAILED", "; ".join(failures), last_error=failures[-1])
        elif _all_complete():
            _state("RUNNING", "ANALYSIS", "All frozen evaluation units complete; building final analysis")
            from app.diarization_final_evaluation.analysis import analyze, collect

            analysis = analyze()
            package = collect()
            _state("COMPLETE", "FROZEN_FINAL_ANALYSIS", "Final standalone diarization evaluation complete and packaged")
            _refresh_progress()
            return {"status": "COMPLETE", "analysis": analysis, "package": package, "progress": _read(PROGRESS_PATH)}
        else:
            _state("PARTIAL", "PARTIAL_SCOPE_COMPLETE", f"Requested scope complete: {scope}")
        return status()
    except Exception as exc:
        _state("FAILED", "FAILED", f"{type(exc).__name__}: {exc}", last_error=str(exc))
        _refresh_progress()
        raise


def worker_controlled(pipeline_id: str) -> dict[str, object]:
    os.environ["JP_DIARIZATION_PIPELINE_STATE"] = "1"
    os.environ["JP_DIARIZATION_SHARED_CACHE_ROOT"] = str(SHARED_CACHE_ROOT.resolve())
    outputs = []
    for benchmark, generated, results, gate in (
        (V1_PROTOCOL_ROOT, V1_GENERATED_ROOT, V1_RESULT_ROOT, AUTHORIZATION_ROOT / "controlled_v1.frozen_gate.json"),
        (V2_PROTOCOL_ROOT, V2_GENERATED_ROOT, V2_RESULT_ROOT, AUTHORIZATION_ROOT / "product_v2.frozen_gate.json"),
    ):
        outputs.append(execute_queue(
            tier="evaluation",
            pipelines=(pipeline_id,),
            config_path=FROZEN_RUNTIME_CONFIG,
            benchmark_root=benchmark,
            generated_root=generated,
            result_root=results,
            frozen_pipeline_config=gate,
        ))
        if int(outputs[-1]["failed"]):
            break
    return {"pipeline_id": pipeline_id, "queues": outputs, "failed": sum(int(row["failed"]) for row in outputs)}


def worker_native(dataset: str, pipeline_id: str) -> dict[str, object]:
    return execute_native_queue(dataset=dataset, pipeline_id=pipeline_id)


def status() -> dict[str, object]:
    progress = _refresh_progress()
    pipelines = selected_pipelines()
    return {
        "schema_version": "diarization-final-status.v1",
        "controller": _read(STATE_PATH),
        "progress": progress,
        "controlled_v1": _safe_controlled_status(V1_PROTOCOL_ROOT, V1_RESULT_ROOT, pipelines),
        "controlled_v2": _safe_controlled_status(V2_PROTOCOL_ROOT, V2_RESULT_ROOT, pipelines),
        "native": _native_status(pipelines),
        "stop_requested": STOP_PATH.is_file(),
        "analysis_exists": (ANALYSIS_ROOT / "analysis_manifest.json").is_file(),
    }


def stop() -> dict[str, object]:
    write_text_atomic(STOP_PATH, "graceful stop requested\n")
    for root in (V1_RESULT_ROOT, V2_RESULT_ROOT):
        write_text_atomic(root / "STOP_REQUESTED", "graceful stop requested\n")
    _state("STOP_REQUESTED", "STOP_REQUESTED", "Stop requested; active case may finish")
    return {"status": "STOP_REQUESTED", "scope": "between checksum-bound evaluation units"}


def analyze() -> dict[str, object]:
    if not _all_complete():
        raise RuntimeError("all controlled and native frozen-finalist units must validate before analysis")
    from app.diarization_final_evaluation.analysis import analyze as build

    _state("RUNNING", "ANALYSIS", "Building final standalone analysis")
    value = build()
    _state("ANALYZED", "ANALYZED", "Final standalone analysis complete")
    return value


def collect() -> dict[str, object]:
    from app.diarization_final_evaluation.analysis import collect as build

    value = build()
    _state("COMPLETE", "FROZEN_FINAL_ANALYSIS", "Final standalone evaluation package complete")
    return value


def _run_parallel_workers(kind: str, pipelines: Sequence[str], parallel: int) -> list[str]:
    pending = list(pipelines)
    active: dict[str, tuple[subprocess.Popen[str], object, object, Path]] = {}
    errors: list[str] = []
    log_root = RESULT_ROOT / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    while pending or active:
        while pending and len(active) < parallel and not STOP_PATH.is_file():
            pipeline = pending.pop(0)
            command = [sys.executable, str(TOOL_ROOT / "run_evaluation.py"), "diarization-final-evaluation", f"worker-{kind}", "--pipeline", pipeline]
            if kind in {"chime6", "voices"}:
                command += ["--dataset", kind]
            stdout_path = log_root / f"{kind}.{pipeline}.stdout.log"
            stderr_path = log_root / f"{kind}.{pipeline}.stderr.log"
            stdout = stdout_path.open("w", encoding="utf-8")
            stderr = stderr_path.open("w", encoding="utf-8")
            process = subprocess.Popen(command, cwd=TOOL_ROOT, stdout=stdout, stderr=stderr, text=True)
            marker = RESULT_ROOT / f"active.{kind}.{pipeline}.json"
            write_json_atomic(marker, {"pid": process.pid, "phase": kind, "pipeline_id": pipeline, "started_at": _now()})
            active[pipeline] = (process, stdout, stderr, marker)
        _refresh_progress()
        for pipeline, (process, stdout, stderr, marker) in list(active.items()):
            returncode = process.poll()
            if returncode is None:
                continue
            stdout.close()
            stderr.close()
            marker.unlink(missing_ok=True)
            del active[pipeline]
            if returncode:
                tail = ""
                path = log_root / f"{kind}.{pipeline}.stderr.log"
                if path.is_file():
                    tail = path.read_text(encoding="utf-8", errors="replace")[-1500:]
                errors.append(f"{kind}/{pipeline} exited {returncode}: {tail}")
        if active:
            time.sleep(2)
        if STOP_PATH.is_file() and not active:
            break
    return errors


def _all_complete() -> bool:
    pipelines = selected_pipelines()
    for benchmark, root in ((V1_PROTOCOL_ROOT, V1_RESULT_ROOT), (V2_PROTOCOL_ROOT, V2_RESULT_ROOT)):
        value = _safe_controlled_status(benchmark, root, pipelines)
        if not value or any(int(row["valid"]) != int(row["planned"]) for row in value.get("rows", [])):
            return False
    for dataset in ("chime6", "voices"):
        planned = len(native_rows(dataset))
        for pipeline in pipelines:
            valid = 0
            for row in native_rows(dataset):
                root = NATIVE_RESULT_ROOT / dataset / pipeline / str(row["evaluation_unit_id"])
                try:
                    validate_native_result(root, expected_pipeline=pipeline)
                    valid += 1
                except Exception:
                    pass
            if valid != planned:
                return False
    return True


def _refresh_progress() -> dict[str, object]:
    pipelines = selected_pipelines()
    rows: list[dict[str, object]] = []
    for phase, benchmark, result in (
        ("controlled_v1", V1_PROTOCOL_ROOT, V1_RESULT_ROOT),
        ("controlled_v2", V2_PROTOCOL_ROOT, V2_RESULT_ROOT),
    ):
        cases = _jsonl(benchmark / "evaluation" / "case_manifest.jsonl")
        index = {str(row["case_id"]): float(row["duration_sec"]) for row in cases}
        for pipeline in pipelines:
            roots = [result / "evaluation" / pipeline / case_id for case_id in index]
            rows.append(_progress_row(phase, pipeline, index, roots, result / f"queue_state.{pipeline}.json"))
    for dataset in ("chime6", "voices"):
        cases = native_rows(dataset)
        index = {str(row["evaluation_unit_id"]): float(row["duration_sec"]) for row in cases}
        for pipeline in pipelines:
            roots = [NATIVE_RESULT_ROOT / dataset / pipeline / case_id for case_id in index]
            rows.append(_progress_row(dataset, pipeline, index, roots, NATIVE_RESULT_ROOT / f"queue_state.{dataset}.{pipeline}.json"))
    planned_units = sum(int(row["planned_cases"]) for row in rows)
    completed_units = sum(int(row["completed_cases"]) for row in rows)
    planned_audio = sum(float(row["planned_audio_seconds"]) for row in rows)
    completed_audio = sum(float(row["completed_audio_seconds"]) for row in rows)
    state = _read(STATE_PATH) or {}
    started = _parse_time(state.get("run_started_at"))
    elapsed = max(0.0, time.time() - started.timestamp()) if started else 0.0
    baseline = float(state.get("resume_completed_audio_seconds") or 0.0)
    gained = max(0.0, completed_audio - baseline)
    remaining = max(0.0, planned_audio - completed_audio)
    eta = elapsed * remaining / gained if gained > 0 and remaining > 0 else (0.0 if remaining == 0 else None)
    active = [_read(path) for path in RESULT_ROOT.glob("active.*.json")]
    active = [row for row in active if row]
    rss, cpu = _process_telemetry([int(row["pid"]) for row in active if row.get("pid")])
    value = {
        "schema_version": "diarization-final-progress.v1",
        "status": state.get("status", "NOT_STARTED"),
        "phase": state.get("stage", "NOT_STARTED"),
        "selected_pipeline_ids": list(pipelines),
        "planned_units": planned_units,
        "completed_units": completed_units,
        "failed_units": sum(int(row["failed_cases"]) for row in rows),
        "overall_unit_percentage": 100.0 * completed_units / planned_units if planned_units else 100.0,
        "planned_audio_seconds": planned_audio,
        "completed_audio_seconds": completed_audio,
        "overall_audio_weighted_percentage": 100.0 * completed_audio / planned_audio if planned_audio else 100.0,
        "elapsed_seconds": elapsed,
        "eta_seconds": eta,
        "estimated_completion_clock_time": (datetime.fromtimestamp(time.time() + eta).astimezone().isoformat() if eta is not None else None),
        "current_process_pids": [row["pid"] for row in active],
        "current_rss_mb": rss,
        "current_cpu_percent": cpu,
        "pipelines": rows,
        "evaluation_tuning_performed": False,
        "updated_at": _now(),
    }
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json_atomic(PROGRESS_PATH, value)
    return value


def _progress_row(phase: str, pipeline: str, index: Mapping[str, float], roots: Sequence[Path], state_path: Path) -> dict[str, object]:
    completed = 0
    audio = 0.0
    inference = 0.0
    peak = None
    for case_id, root in zip(index, roots, strict=True):
        run_path = root / "run.json"
        if not run_path.is_file():
            continue
        try:
            run = _read(run_path) or {}
            if run.get("status") != "succeeded":
                continue
            completed += 1
            audio += float(index[case_id])
            timing = dict(run.get("timing") or {})
            inference += float(timing.get("diarization_inference_sec") or 0.0)
            ram = dict(run.get("resource_telemetry") or {}).get("peak_rss_mb")
            if ram is not None:
                peak = max(float(ram), float(peak or 0.0))
        except Exception:
            continue
    queue = _read(state_path) or {}
    planned_audio = sum(index.values())
    if completed == len(index):
        display_status = "COMPLETE"
    elif int(queue.get("failed") or 0):
        display_status = "COMPLETE_WITH_FAILURES" if queue.get("status") == "COMPLETE_WITH_FAILURES" else "RUNNING_WITH_FAILURES"
    elif queue.get("status") == "RUNNING":
        display_status = "RUNNING"
    else:
        display_status = "PENDING"
    return {
        "phase": phase,
        "dataset": _dataset_label(phase),
        "pipeline": pipeline,
        "planned_cases": len(index),
        "completed_cases": completed,
        "failed_cases": int(queue.get("failed") or 0),
        "current_case": queue.get("current_case"),
        "unit_percentage": 100.0 * completed / len(index) if index else 100.0,
        "planned_audio_seconds": planned_audio,
        "completed_audio_seconds": audio,
        "audio_weighted_percentage": 100.0 * audio / planned_audio if planned_audio else 100.0,
        "rolling_rtf": inference / audio if audio else None,
        "peak_ram_mb": peak,
        "status": display_status,
    }


def _completed_audio_seconds() -> float:
    if not PROGRESS_PATH.is_file():
        _refresh_progress()
    return float((_read(PROGRESS_PATH) or {}).get("completed_audio_seconds") or 0.0)


def _safe_controlled_status(benchmark: Path, result: Path, pipelines: Sequence[str]) -> dict[str, object] | None:
    try:
        return queue_status(
            pipelines=pipelines,
            tiers=("evaluation",),
            config_path=FROZEN_RUNTIME_CONFIG,
            benchmark_root=benchmark,
            result_root=result,
        )
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "rows": []}


def _native_status(pipelines: Sequence[str]) -> dict[str, object]:
    rows = []
    for dataset in ("chime6", "voices"):
        planned = len(native_rows(dataset))
        for pipeline in pipelines:
            valid = sum((NATIVE_RESULT_ROOT / dataset / pipeline / str(row["evaluation_unit_id"]) / "run.json").is_file() for row in native_rows(dataset))
            queue = _read(NATIVE_RESULT_ROOT / f"queue_state.{dataset}.{pipeline}.json") or {}
            rows.append({"dataset": dataset, "pipeline_id": pipeline, "planned": planned, "valid": valid, "failed": int(queue.get("failed") or 0), "status": queue.get("status", "PENDING")})
    return {"rows": rows}


def _state(status_value: str, stage: str, detail: str, *, last_error: str | None = None, start_new: bool = False, baseline_audio: float = 0.0) -> None:
    existing = _read(STATE_PATH) or {}
    value = {
        "schema_version": "diarization-final-controller.v1",
        "status": status_value,
        "stage": stage,
        "detail": detail,
        "last_error": last_error,
        "pid": os.getpid(),
        "run_started_at": _now() if start_new else existing.get("run_started_at"),
        "resume_completed_audio_seconds": baseline_audio if start_new else existing.get("resume_completed_audio_seconds", 0.0),
        "updated_at": _now(),
    }
    write_json_atomic(STATE_PATH, value)


def _process_telemetry(pids: Sequence[int]) -> tuple[float | None, float | None]:
    try:
        import psutil

        rss = 0
        cpu = 0.0
        seen = set()
        for pid in pids:
            try:
                processes = [psutil.Process(pid), *psutil.Process(pid).children(recursive=True)]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            for process in processes:
                if process.pid in seen:
                    continue
                seen.add(process.pid)
                try:
                    rss += process.memory_info().rss
                    cpu += process.cpu_percent(interval=None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        return (rss / 1024 / 1024 if seen else None), (cpu if seen else None)
    except ImportError:
        return None, None


def _dataset_label(phase: str) -> str:
    return {"controlled_v1": "Common Voice controlled V1", "controlled_v2": "Common Voice controlled Product V2", "chime6": "CHiME-6 native", "voices": "VOiCES acoustic diagnostic"}[phase]


def _read(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _parse_time(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
