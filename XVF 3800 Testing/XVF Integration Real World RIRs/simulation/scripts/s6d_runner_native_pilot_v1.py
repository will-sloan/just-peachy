"""In-process frozen native pilot protocol bridge; see matching README."""
from __future__ import annotations
import argparse
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import threading
import time
import psutil
sys.dont_write_bytecode = True
from s6d_runner_v1 import binding, finite_number, identity_matches, load, save, utc


class NativeStopRequested(RuntimeError):
    pass


def semantic_result(result, job, manifest_bound, helper_bound, identity):
    checks = {
        "status_complete": result.get("status") == "COMPLETE",
        "failure_absent": result.get("failure") is None,
        "native_tested": result.get("native_tested") is True,
        "observer_closed": result.get("resource_observer_closed") is True,
        "observer_errors_empty": result.get("observer_errors") == [],
        "native_completion_errors_empty": result.get("completion_errors") == [],
        "event_consumer_drained": result.get("event_consumer_drained") is True,
        "same_process": result.get("pid") == identity["pid"] and abs(result.get("process_create_time", 0) - identity["creation_time"]) < .001,
        "exact_native_job": result.get("job") == job,
        "exact_manifest": result.get("manifest") == manifest_bound,
        "exact_helper": result.get("helper") == helper_bound,
        "engine_completed": result.get("telemetry", {}).get("state") == "COMPLETED",
    }
    queues = result.get("telemetry", {}).get("s6d")
    if job.get("settings") is not None:
        checks["s6d_queue_state_present"] = isinstance(queues, dict)
    if isinstance(queues, dict):
        consumer = queues.get("event_consumer")
        checks["consumer_queue_empty"] = isinstance(consumer, dict) and consumer.get("depth") == 0
        for lane in ("journal", "punctuation", "policy"):
            worker = queues.get(lane)
            if worker is not None:
                checks[lane + "_fully_drained"] = (
                    worker.get("depth") == 0 and worker.get("accepted") == worker.get("completed")
                    and worker.get("error") is None and worker.get("closed") is True and worker.get("thread_alive") is False)
    if not all(checks.values()):
        raise ValueError("native semantic completion rejected: " + ", ".join(k for k, v in checks.items() if not v))
    return checks


class ProtocolBridge:
    def __init__(self, identity, heartbeat_path, stop_path, native_job, heartbeat_interval=5):
        self.identity, self.heartbeat_path, self.stop_path = identity, Path(heartbeat_path), Path(stop_path)
        self.native_job = native_job
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.closed = threading.Event()
        self.progress_count = 0
        self.checkpoint_count = 0
        self.latest = {"stage": "WRAPPER_ADMISSION", "done_source_sec": 0., "source_admitted_sec": 0., "completed_work_items": 0}
        self.failure = None
        self.completed = False
        self.observer_errors = []
        self.heartbeat_interval = heartbeat_interval
        self.thread = threading.Thread(target=self.observe, name="s6d-native-protocol", daemon=True)

    def update(self, stage, done=0., admitted=0., completed=0):
        with self.lock:
            previous = self.latest
            actual_advance = (stage != previous["stage"] or done > previous["done_source_sec"]
                or admitted > previous["source_admitted_sec"] or completed > previous["completed_work_items"])
            if actual_advance:
                self.progress_count += 1
            self.latest = {"stage": stage, "done_source_sec": max(done, previous["done_source_sec"]),
                "source_admitted_sec": max(admitted, previous["source_admitted_sec"]),
                "completed_work_items": max(completed, previous["completed_work_items"])}

    def heartbeat(self):
        with self.lock:
            value = {**self.identity, "utc": utc(), "status": "FAILED" if self.failure else ("COMPLETE" if self.completed else "RUNNING"),
                "progress_count": self.progress_count, "checkpoint_count": self.checkpoint_count,
                "native_job_id": self.native_job["job_id"], "native_output": self.native_job["output"],
                "total_source_sec": self.native_job["audio_duration_sec"], "progress": dict(self.latest),
                "stop_requested": self.stop.is_set(), "error": self.failure, "queue_age_s": None}
        save(self.heartbeat_path, value)

    def observe(self):
        last_write = 0
        try:
            while not self.closed.is_set():
                if self.stop_path.exists():
                    request = load(self.stop_path, retries=2, delay=.02)
                    if identity_matches(request, self.identity) and request.get("pid") == self.identity["pid"] and abs(request.get("creation_time", 0) - self.identity["creation_time"]) < .001:
                        self.stop.set()
                if time.monotonic() - last_write >= self.heartbeat_interval:
                    self.heartbeat()
                    last_write = time.monotonic()
                self.closed.wait(.1)
        except BaseException as exc:
            self.observer_errors.append(repr(exc))
            self.stop.set()

    def checkpoint(self, engine, telemetry, job, output):
        if job != self.native_job or Path(output).resolve() != Path(self.native_job["output"]).resolve():
            self.stop.set()
            raise RuntimeError("native checkpoint job/output mismatch")
        with self.lock:
            self.checkpoint_count += 1
        queues = telemetry.get("s6d") or {}
        completed = sum(worker.get("completed", 0) for key, worker in queues.items()
            if key in ("journal", "punctuation", "policy") and isinstance(worker, dict))
        consumer = queues.get("event_consumer")
        if isinstance(consumer, dict):
            completed += consumer.get("consumed", 0)
        done, admitted = telemetry.get("asr_cursor_sec", 0.), telemetry.get("source_duration_sec", 0.)
        if not all(finite_number(x) for x in (done, admitted, completed)):
            engine.stop()
            raise RuntimeError("nonfinite native progress")
        self.update(str(telemetry.get("state", engine.state)), done, admitted, completed)
        if self.stop.is_set():
            engine.stop()
            raise NativeStopRequested("explicit same-run STOP_REQUEST; native engine.stop invoked")

    def close(self):
        self.closed.set()
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError("native protocol observer failed to close")


def execute(helper_path, helper_sha256, manifest_path, manifest_sha256, native_job_id, heartbeat_interval=5):
    helper_bound, manifest_bound = binding(helper_path, helper_sha256), binding(manifest_path, manifest_sha256)
    manifest = load(manifest_path)
    if manifest.get("schema") != "s6d-native-pilot.v1" or manifest["helper"]["sha256"] != helper_bound["sha256"]:
        raise ValueError("native manifest/helper contract mismatch")
    jobs = [job for job in manifest["jobs"] if job["job_id"] == native_job_id]
    if len(jobs) != 1:
        raise ValueError("native job ID is absent or ambiguous")
    job = jobs[0]
    for source in manifest["execution_files"]:
        binding(source["path"], source["sha256"])
    identity = {"run_id": os.environ["S6D_RUN_ID"], "job_id": os.environ["S6D_JOB_ID"],
        "child_run_id": os.environ["S6D_CHILD_RUN_ID"], "pid": os.getpid(), "creation_time": psutil.Process().create_time()}
    heartbeat_path, completion_path, stop_path = (Path(os.environ[k]) for k in (
        "S6D_HEARTBEAT_PATH", "S6D_COMPLETION_PATH", "S6D_STOP_REQUEST_PATH"))
    if heartbeat_path.exists() or completion_path.exists() or Path(job["output"]).exists():
        raise ValueError("native wrapper requires fresh protocol and native output paths")
    bridge = ProtocolBridge(identity, heartbeat_path, stop_path, job, heartbeat_interval)
    bridge.thread.start()
    failure, checks, result_bound = None, None, None
    try:
        # The frozen native model constructors validate all8 declared model hashes.
        # Do not duplicate multi-GiB asset hashing in this bridge or supervisor health loop.
        if bridge.stop.is_set():
            raise NativeStopRequested("STOP requested before native initialization")
        module_name = "s6d_native_pilot_frozen_helper"
        specification = importlib.util.spec_from_file_location(module_name, helper_bound["path"])
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        specification.loader.exec_module(module)
        if "checkpoint" not in inspect.signature(module.run_one).parameters:
            raise ValueError("frozen native helper lacks the reviewed checkpoint STOP hook")
        bridge.update("NATIVE_RUN_ONE_ENTERED")
        module.run_one(Path(manifest_bound["path"]), native_job_id, checkpoint=bridge.checkpoint)
        if bridge.stop.is_set() or bridge.observer_errors:
            raise NativeStopRequested("native/protocol observer stopped or failed")
        result_path = Path(job["output"]) / "RESULT.json"
        result_bound = binding(result_path)
        checks = semantic_result(load(result_path), job, manifest_bound, helper_bound, identity)
        if bridge.checkpoint_count == 0:
            raise ValueError("native helper did not invoke reviewed checkpoint hook")
        bridge.update("SEMANTIC_COMPLETION_VALIDATED")
        bridge.completed = True
    except BaseException as exc:
        failure = type(exc).__name__ + ": " + str(exc)
        bridge.failure = failure
    finally:
        try:
            bridge.close()
        except BaseException as exc:
            failure = failure or repr(exc)
            bridge.failure = failure
        bridge.heartbeat()
    result = {**identity, "native_job_id": native_job_id, "created_utc": utc(),
        "status": "COMPLETE" if failure is None else "FAILED", "failure": failure,
        "manifest": manifest_bound, "helper": helper_bound, "wrapper": binding(__file__),
        "native_result": result_bound, "declared_model_assets": manifest["assets"],
        "model_asset_hash_validation": "Frozen native models.py constructors before execution; wrapper/supervisor do not repeat large-asset hashing",
        "semantic_checks": checks, "protocol_observer_closed": not bridge.thread.is_alive(),
        "protocol_observer_errors": bridge.observer_errors, "checkpoint_count": bridge.checkpoint_count,
        "progress_count": bridge.progress_count, "native_run_one_same_process": True,
        "subprocess_spawned_by_wrapper": False, "stop_requested": bridge.stop.is_set()}
    if failure is None:
        save(completion_path, result, exclusive=True)
    else:
        save(completion_path.with_name("WRAPPER_FAILURE.json"), result, exclusive=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--helper-sha256", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--native-job-id", required=True)
    args = parser.parse_args()
    result = execute(args.helper, args.helper_sha256, args.manifest, args.manifest_sha256, args.native_job_id)
    print(json.dumps({"status": result["status"], "failure": result["failure"], "native_job_id": args.native_job_id}), flush=True)
    raise SystemExit(0 if result["status"] == "COMPLETE" else 2)
