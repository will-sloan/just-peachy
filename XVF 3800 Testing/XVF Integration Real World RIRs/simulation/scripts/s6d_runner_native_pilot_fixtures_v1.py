"""No-model fixture helper + in-process wrapper checks; see matching README."""
from __future__ import annotations
import argparse
import copy
import os
from pathlib import Path
import sys
import threading
import time
import psutil
sys.dont_write_bytecode = True
import s6d_runner_v1 as runner
import s6d_runner_native_pilot_v1 as wrapper


def run_one(manifest_path, job_id, checkpoint=None):
    """Fixture double, never production model inference."""
    manifest = runner.load(manifest_path)
    job = next(j for j in manifest["jobs"] if j["job_id"] == job_id)
    output = Path(job["output"])
    output.mkdir(parents=True)
    class Engine:
        state = "RUNNING"
        stopped = False
        def stop(self):
            self.stopped = True
            self.state = "STOPPED"
    engine = Engine()
    worker = {"depth": 0, "accepted": 3, "completed": 3, "error": None, "closed": True, "thread_alive": False}
    telemetry = {"state": "RUNNING", "asr_cursor_sec": 0., "source_duration_sec": 0.,
        "s6d": {"event_consumer": {"depth": 0, "consumed": 3}, "journal": dict(worker),
                 "punctuation": dict(worker), "policy": dict(worker)}}
    failure = None
    try:
        for i in range(12 if job["fixture_mode"] == "stop" else 5):
            telemetry.update(asr_cursor_sec=i / 10, source_duration_sec=i / 10)
            if job["fixture_mode"] != "missing_checkpoint":
                checkpoint(engine=engine, telemetry=telemetry, job=job, output=output)
            time.sleep(.03)
    except BaseException as exc:
        failure = repr(exc)
    engine.state = "STOPPED" if engine.stopped else "COMPLETED"
    telemetry["state"] = engine.state
    result = {"schema": "s6d-native-cell.v1", "status": "FAILED" if failure else "COMPLETE", "job": job,
        "manifest": runner.binding(manifest_path), "helper": runner.binding(__file__),
        "pid": os.getpid(), "process_create_time": psutil.Process().create_time(), "failure": failure,
        "telemetry": telemetry, "resource_observer_closed": True, "event_consumer_drained": True,
        "observer_errors": [], "completion_errors": [], "native_tested": True,
        "fixture_only": True, "engine_stop_called": engine.stopped}
    mode = job["fixture_mode"]
    if mode == "undrained": result["telemetry"]["s6d"]["policy"]["depth"] = 1
    if mode == "observer_alive": result["resource_observer_closed"] = False
    if mode == "consumer_pending": result["event_consumer_drained"] = False
    if mode == "native_error": result["completion_errors"] = ["fixture adverse completion"]
    if mode == "wrong_pid": result["pid"] += 1
    if mode == "false_complete": result.update(status="FAILED", failure="fixture failure", native_tested=False)
    runner.save(output / "RESULT.json", result, exclusive=True)
    if failure:
        raise RuntimeError(failure)
    return result


def fixtures(output):
    output = output.resolve()
    if output.exists():
        raise ValueError("new fixture output directory required")
    output.mkdir(parents=True)
    outcomes = []
    for mode in ("normal", "undrained", "observer_alive", "consumer_pending", "native_error", "wrong_pid", "false_complete", "missing_checkpoint", "stop"):
        root = output / mode
        root.mkdir()
        job = {"job_id": "native_fixture_" + mode, "output": str(root / "native"), "audio_duration_sec": .5,
            "settings": {"fixture_only": True}, "fixture_mode": mode}
        manifest = {"schema": "s6d-native-pilot.v1", "helper": runner.binding(__file__),
            "execution_files": [runner.binding(__file__), runner.binding(wrapper.__file__), runner.binding(runner.__file__)],
            "assets": [], "jobs": [job], "fixture_only": True}
        manifest_path = root / "MANIFEST.json"
        runner.save(manifest_path, manifest, exclusive=True)
        env = {"S6D_RUN_ID": "wrapper_fixture", "S6D_JOB_ID": job["job_id"], "S6D_CHILD_RUN_ID": "child_" + mode,
            "S6D_HEARTBEAT_PATH": str(root / "HEARTBEAT.json"), "S6D_COMPLETION_PATH": str(root / "COMPLETION.json"),
            "S6D_STOP_REQUEST_PATH": str(root / "STOP_REQUEST.json")}
        prior = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        stop_thread = None
        if mode == "stop":
            identity = {"run_id": env["S6D_RUN_ID"], "job_id": env["S6D_JOB_ID"], "child_run_id": env["S6D_CHILD_RUN_ID"],
                "pid": os.getpid(), "creation_time": psutil.Process().create_time()}
            def request_stop():
                time.sleep(.04)
                runner.save(env["S6D_STOP_REQUEST_PATH"], {**identity, "request": "STOP_AND_RESTORE"})
            stop_thread = threading.Thread(target=request_stop)
            stop_thread.start()
        try:
            result = wrapper.execute(__file__, runner.binding(__file__)["sha256"], manifest_path,
                runner.binding(manifest_path)["sha256"], job["job_id"], heartbeat_interval=.02)
        finally:
            if stop_thread:
                stop_thread.join()
            for key, value in prior.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        expected = "COMPLETE" if mode == "normal" else "FAILED"
        assert result["status"] == expected, (mode, result)
        assert (root / "COMPLETION.json").exists() == (mode == "normal")
        assert result["protocol_observer_closed"] and not result["subprocess_spawned_by_wrapper"]
        if mode == "normal":
            assert result["checkpoint_count"] == 5 and result["progress_count"] > 1
            assert all(result["semantic_checks"].values())
        if mode == "stop":
            assert runner.load(root / "native/RESULT.json")["engine_stop_called"]
            assert result["stop_requested"]
        outcomes.append({"fixture": mode, "status": "PASS", "wrapper_result_status": result["status"],
            "same_process_pid": result["pid"], "completion_file_exists": (root / "COMPLETION.json").exists()})
    bridge = wrapper.ProtocolBridge({"run_id": "fixture", "job_id": "fixture", "child_run_id": "fixture",
        "pid": os.getpid(), "creation_time": psutil.Process().create_time()}, output / "unused.json", output / "no_stop.json",
        {"job_id": "fixture", "output": str(output), "audio_duration_sec": 1})
    bridge.update("RUNNING", 1, 1, 1)
    initial = bridge.progress_count
    for i in range(100):
        bridge.update("RUNNING", 1, 1, 1)
    assert bridge.progress_count == initial
    outcomes.append({"fixture": "progress_not_wall_clock", "status": "PASS", "unchanged_observation_updates": 100,
        "progress_count_changed": False})
    receipt = {"status": "PASS", "fixtures": outcomes, "fixture_count": len(outcomes), "created_utc": runner.utc(),
        "wrapper": runner.binding(wrapper.__file__), "fixture_code": runner.binding(__file__),
        "production_native_helper_invoked": False, "models_loaded": 0, "device_calls": 0,
        "scope": "In-process fake engine only; semantic adverse controls and real protocol STOP event; no native model result claimed"}
    runner.save(output / "NATIVE_WRAPPER_FIXTURE_RECEIPT.json", receipt, exclusive=True)
    print({"status": "PASS", "fixture_count": len(outcomes), "receipt": str(output / "NATIVE_WRAPPER_FIXTURE_RECEIPT.json")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    fixtures(parser.parse_args().output)
