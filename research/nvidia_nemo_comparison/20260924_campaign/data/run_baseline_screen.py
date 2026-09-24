"""Checkpointed source-paced baseline through the common Controller. See README.md."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import sys
import time
import traceback
import uuid
import wave


def utc():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def binding(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def source_bindings(source):
    bindings = {str(path.relative_to(source)).replace("\\", "/"): digest(path)
            for folder in ("app", "vendor", "config", "release_tools")
            for path in sorted((source / folder).rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}}
    bindings.update({path.name: digest(path) for path in sorted(source.iterdir())
                     if path.is_file() and (path.name == "main.py" or path.suffix.lower() in {".cmd", ".bat", ".ps1", ".sh"})})
    return bindings


def bounded_commands(controller, seconds=120):
    end = time.monotonic() + seconds
    while controller.commands.unfinished_tasks:
        if time.monotonic() > end:
            raise TimeoutError("Controller command did not finish")
        time.sleep(0.05)
    if controller.error:
        raise RuntimeError(controller.error)


def child_worker(source, models, output, cpu, jobs, results, contract):
    """One resident model stack, fresh controller/state/data root per input cell."""
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[variable] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import psutil
    process = psutil.Process()
    if os.name == "nt":
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    else:
        process.nice(10)
    process.cpu_affinity([cpu])
    source = Path(source)
    sys.path[:0] = [str(source), str(source / "vendor")]
    from app.controller import Controller
    from app.pipeline import ResidentModels
    resident = ResidentModels()
    while True:
        job = jobs.get()
        if job is None:
            return
        started = time.monotonic()
        attempt = Path(output) / "cells" / job["job_id"] / ("attempt_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:6])
        attempt.mkdir(parents=True)
        controller = None
        result = {"job_id": job["job_id"], "cache_key": job["cache_key"], "status": "FAILED", "started_utc": utc(), "attempt": str(attempt), "worker_pid": os.getpid(), "cpu_affinity": [cpu], "resource_scope": "two-stack Windows research throughput only; not isolated latency/resource or 2GiB target claim"}
        try:
            if digest(job["audio_path"]) != job["audio_sha256"]:
                raise ValueError("Input changed since admission")
            if source_bindings(source) != contract["source_bindings"]:
                raise ValueError("Frozen common source changed")
            controller = Controller(attempt / "data", models, saved_audio_only=True)
            controller.config = replace(controller.config, asr_threads=1, speaker_threads=1, punctuation_threads=1)
            controller.models = resident
            controller.switch(mode="anonymous_conversation", recipe="balanced", tap=job["tap"], strict=False)
            bounded_commands(controller)
            if controller.store.list():
                raise RuntimeError("Research data unexpectedly contains a personal gallery")
            controller.start_file(job["audio_path"])
            bounded_commands(controller)
            engine = controller.engine
            if engine is None:
                raise RuntimeError("No native engine after start")
            (engine.session_dir / "PINNED").touch(exist_ok=True)
            samples = []
            last_sample = -10.0
            while controller.state in ("RUNNING", "STARTING", "STOPPING"):
                elapsed = time.monotonic() - started
                if elapsed > job["timeout_seconds"]:
                    raise TimeoutError("Source-paced cell exceeded bounded timeout")
                if elapsed - last_sample >= 5:
                    last_sample = elapsed
                    samples.append({"elapsed_seconds": elapsed, "rss_bytes": process.memory_info().rss, "cpu_seconds": sum(process.cpu_times()[:2]), "source_frames_sent": getattr(engine._source, "sent", 0), "state": controller.state})
                    atomic(attempt / "HEARTBEAT.json", {"utc": utc(), "job_id": job["job_id"], "elapsed_seconds": elapsed, "state": controller.state, "source_frames_sent": getattr(engine._source, "sent", 0)})
                time.sleep(0.2)
            snapshot = controller.snapshot()
            writers = [{"accepted": w.accepted, "completed": w.completed, "max_depth": w.max_depth, "error": w.error} for w in engine.text_writers]
            telemetry = engine.telemetry()
            delivered = engine._journal.committed_samples
            checks = {"controller_stopped": snapshot["state"] == "STOPPED", "no_error": not snapshot["error"], "all_frames_delivered": delivered == job["frames"], "writers_drained": all(w["accepted"] == w["completed"] and not w["error"] for w in writers), "no_gallery_queries": snapshot["metrics"].get("gallery_queries", 0) == 0, "models_loaded": resident.asr_loads > 0 and resident.speaker_loads > 0}
            atomic(attempt / "FINAL_SNAPSHOT.json", snapshot)
            atomic(attempt / "PROCESS_SAMPLES.json", samples)
            result.update({"status": "COMPLETE" if all(checks.values()) else "FAILED", "checks": checks, "controller_state": snapshot["state"], "error": snapshot["error"], "session": str(engine.session_dir), "input": {k: job[k] for k in ("audio_path", "audio_sha256", "frames", "sample_rate_hz", "gain", "tap")}, "delivered_frames": delivered, "caption_rows": len(snapshot["rows"]), "writer_counts": writers, "telemetry": telemetry, "model_cache": {"asr_loads": resident.asr_loads, "speaker_loads": resident.speaker_loads, "streams": resident.streams}, "source_delivery": "absolute source-speed saved-file delivery; actual observed scheduler clocks", "physical_latency": "NOT_MEASURED", "isolated_resource_or_target_performance": "NOT_MEASURED"})
        except BaseException as exc:
            result.update(error=type(exc).__name__ + ": " + str(exc), traceback=traceback.format_exc())
        finally:
            if controller is not None:
                try:
                    controller.close()
                    bounded_commands(controller, 125)
                    controller.worker.join(10)
                    if not controller.closed or controller.worker.is_alive():
                        raise RuntimeError("Controller did not release owned threads")
                except BaseException as exc:
                    result["status"] = "FAILED"
                    result["cleanup_error"] = repr(exc)
                    # A failed cleanup cannot share resident state with another job.
                    resident = ResidentModels()
            result["elapsed_seconds"] = time.monotonic() - started
            result["finished_utc"] = utc()
            result["evidence"] = [binding(p) for p in sorted(attempt.rglob("*")) if p.is_file() and p.suffix in {".json", ".jsonl", ".md"} and p.name != "RESULT.json"]
            atomic(attempt / "RESULT.json", result)
            atomic(Path(output) / "cells" / job["job_id"] / "CHECKPOINT.json", {"cache_key": job["cache_key"], "status": result["status"], "result": binding(attempt / "RESULT.json")})
            results.put({"pid": os.getpid(), "job_id": job["job_id"], "status": result["status"], "result": str(attempt / "RESULT.json"), "error": result.get("error")})


def main(args):
    source, models, output = Path(args.source).resolve(), Path(args.models).resolve(), Path(args.output).resolve()
    if output.is_relative_to(source):
        raise ValueError("Evidence/data must be outside the frozen source directory")
    output.mkdir(parents=True, exist_ok=True)
    progress = Path(args.progress).resolve() if args.progress else output / "PROGRESS.json"
    lock = output / "RUNNER_LOCK.json"
    import psutil
    current = psutil.Process()
    if lock.exists():
        prior = load(lock)
        alive = False
        try:
            alive = abs(psutil.Process(prior["pid"]).create_time() - prior["process_create_time"]) < 0.01
        except psutil.NoSuchProcess:
            pass
        if alive:
            raise RuntimeError("A live worker coordinator already owns this output")
        lock.rename(output / ("STALE_LOCK_" + uuid.uuid4().hex + ".json"))
    with lock.open("x", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid(), "process_create_time": current.create_time(), "utc": utc()}, handle)
    processes = []
    started = time.monotonic()
    try:
        manifest = load(args.manifest)
        assets = load(source / "config/assets.json")
        asset_bindings = []
        for asset in assets:
            ref = binding(models / asset["sha256"] / asset["filename"])
            if ref["sha256"] != asset["sha256"]:
                raise ValueError("Selected baseline model hash mismatch")
            asset_bindings.append({"component_id": asset["component_id"], **ref})
        versions = {name: importlib.metadata.version(name) for name in ("numpy", "soundfile", "onnxruntime", "sherpa-onnx", "psutil")}
        contract = {"schema": "n1-baseline-screen-v1", "runner_sha256": digest(__file__), "source_bindings": source_bindings(source), "models": asset_bindings, "runtime": {"python": sys.version, "packages": versions}, "manifest": binding(args.manifest), "screen_sha256": manifest["screen_sha256"], "recipe": "balanced", "mode": "anonymous_conversation", "thread_configuration": {"asr": 1, "speaker": 1, "punctuation": 1}, "preprocessing": "mono16k PCM16 exact supplied waveform, gain1; no enhancement", "history": "empty scene-specific controller/gallery/tracker, resident model weights only", "delivery": "source-speed absolute pacer", "evaluation": "common Controller events; no reference inputs", "scoring_version": "n1-integrity-event-v1"}
        contract_hash = stable_hash(contract)
        admission_path = output / "ADMISSION.json"
        if admission_path.exists() and load(admission_path)["contract_sha256"] != contract_hash:
            raise ValueError("Resume source/model/runtime/config/manifest binding changed; use a new output directory")
        atomic(admission_path, {"contract_sha256": contract_hash, "contract": contract, "resource_limit": "at most2 below-normal one-CPU Windows workers; not2GiB qualification"})
        work, completed, failed = [], {}, {}
        for raw in manifest["jobs"]:
            allowed = {"job_id", "audio_path", "audio_sha256", "frames", "sample_rate_hz", "gain", "reset_between_scenes", "tap"}
            if set(raw) - allowed or raw["gain"] != 1 or not raw["reset_between_scenes"]:
                raise ValueError("Audio-only firewall or gain/state contract violated")
            if not re_job_id(raw["job_id"]):
                raise ValueError("Unsafe job identity")
            if digest(raw["audio_path"]) != raw["audio_sha256"]:
                raise ValueError("Admitted input audio hash changed")
            with wave.open(raw["audio_path"], "rb") as waveform:
                if (waveform.getnchannels(), waveform.getsampwidth(), waveform.getframerate(), waveform.getnframes()) != (1, 2, raw["sample_rate_hz"], raw["frames"]):
                    raise ValueError("Admitted prepared audio header changed")
            job = dict(raw)
            job["cache_key"] = stable_hash({"contract": contract_hash, "job": raw})
            job["timeout_seconds"] = raw["frames"] / raw["sample_rate_hz"] * 5 + 120
            checkpoint = output / "cells" / job["job_id"] / "CHECKPOINT.json"
            if checkpoint.exists():
                old = load(checkpoint)
                if old["cache_key"] != job["cache_key"]:
                    raise ValueError("Cell cache identity changed")
                result_binding = old["result"]
                if digest(result_binding["path"]) != result_binding["sha256"]:
                    raise ValueError("Checkpoint result changed")
                prior = load(result_binding["path"])
                if old["status"] == "COMPLETE":
                    for evidence in prior["evidence"]:
                        if digest(evidence["path"]) != evidence["sha256"]:
                            raise ValueError("Completed evidence changed")
                    completed[job["job_id"]] = result_binding["path"]
                    continue
                if not args.retry_failed:
                    failed[job["job_id"]] = result_binding["path"]
                    continue
            work.append(job)
        total = len(manifest["jobs"])
        if args.limit:
            work = work[:args.limit]
        def report(status, error=None, active=None):
            atomic(progress, {"utc": utc(), "pid": os.getpid(), "status": status, "completed": len(completed), "failed": len(failed), "total": total, "elapsed_seconds": time.monotonic() - started, "error": error, "active": active or [], "contract_sha256": contract_hash, "remaining_audio_seconds": sum(j["frames"] / j["sample_rate_hz"] for j in work)})
        report("PREPARED")
        if args.prepare_only:
            print(json.dumps({"status": "PREPARED", "jobs_pending": len(work), "total": total, "contract_sha256": contract_hash}))
            return 0
        ctx = mp.get_context("spawn")
        results = ctx.Queue()
        cpus = current.cpu_affinity()[-args.workers:]
        slots = []
        def new_worker(cpu):
            inbox = ctx.Queue()
            process = ctx.Process(target=child_worker, args=(str(source), str(models), str(output), cpu, inbox, results, contract))
            process.start()
            processes.append(process)
            return {"process": process, "inbox": inbox, "cpu": cpu, "job": None, "start": None}
        slots = [new_worker(cpu) for cpu in cpus]
        next_report = 0
        while work or any(s["job"] for s in slots):
            for slot in slots:
                if slot["job"] is None and work:
                    slot["job"] = work.pop(0)
                    slot["start"] = time.monotonic()
                    slot["inbox"].put(slot["job"])
            try:
                message = results.get(timeout=0.5)
                slot = next(s for s in slots if s["process"].pid == message["pid"])
                if message["status"] == "COMPLETE":
                    completed[message["job_id"]] = message["result"]
                else:
                    failed[message["job_id"]] = message["result"]
                slot["job"] = None
            except queue.Empty:
                pass
            for index, slot in enumerate(slots):
                job = slot["job"]
                if job and (not slot["process"].is_alive() or time.monotonic() - slot["start"] > job["timeout_seconds"] + 180):
                    if slot["process"].is_alive():
                        slot["process"].terminate()
                    slot["process"].join(10)
                    failure = output / "cells" / job["job_id"] / ("WORKER_FAILURE_" + uuid.uuid4().hex + ".json")
                    atomic(failure, {"status": "FAILED", "job_id": job["job_id"], "cache_key": job["cache_key"], "utc": utc(), "error": "Owned worker exited or exceeded timeout", "pid": slot["process"].pid})
                    failed[job["job_id"]] = str(failure)
                    slots[index] = new_worker(slot["cpu"])
            if time.monotonic() >= next_report:
                report("RUNNING", active=[{"job_id": s["job"]["job_id"], "pid": s["process"].pid} for s in slots if s["job"]])
                next_report = time.monotonic() + 5
        for slot in slots:
            slot["inbox"].put(None)
        for process in processes:
            process.join(20)
        if source_bindings(source) != contract["source_bindings"]:
            raise RuntimeError("Frozen source changed during baseline run")
        status = "COMPLETE" if len(completed) == total and not failed else "PARTIAL" if not failed else "FAILED"
        atomic(output / "RESULT_INDEX.json", {"status": status, "completed": completed, "failed": failed, "total": total, "contract_sha256": contract_hash, "elapsed_seconds": time.monotonic() - started})
        report(status, error="One or more cells failed; evidence retained" if failed else None)
        print(json.dumps({"status": status, "completed": len(completed), "failed": len(failed), "total": total}))
        return 0 if status in {"COMPLETE", "PARTIAL"} else 1
    except BaseException as exc:
        atomic(progress, {"utc": utc(), "status": "FAILED", "completed": 0, "total": 0, "elapsed_seconds": time.monotonic() - started, "error": repr(exc)})
        raise
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(10)
        lock.unlink(missing_ok=True)


def re_job_id(value):
    return bool(value) and all(c.isalnum() or c in "_-" for c in value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Explicit immutable prototype directory")
    parser.add_argument("--models", default=r"C:\Users\amiri\JustPeachy\shared\models")
    parser.add_argument("--manifest", required=True, help="Audio-only screen manifest")
    parser.add_argument("--output", required=True, help="Private evidence directory outside source/Git")
    parser.add_argument("--progress", help="Parent-owned progress JSON")
    parser.add_argument("--workers", type=int, choices=[1, 2], default=2)
    parser.add_argument("--prepare-only", action="store_true", help="Verify bindings without model inference")
    parser.add_argument("--limit", type=int, help="Bounded number of pending smoke cells; resume without this flag")
    parser.add_argument("--retry-failed", action="store_true", help="New attempts for failed cells, preserving earlier evidence")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    raise SystemExit(main(args))
