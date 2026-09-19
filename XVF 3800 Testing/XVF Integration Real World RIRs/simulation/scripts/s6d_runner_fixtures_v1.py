"""Model-free supervisor fixtures and tiny child protocol; see matching README."""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import threading
import time
import psutil
sys.dont_write_bytecode = True
import s6d_runner_v1 as runner


def child(mode, result_path):
    identity = {"run_id": os.environ["S6D_RUN_ID"], "job_id": os.environ["S6D_JOB_ID"],
        "child_run_id": os.environ["S6D_CHILD_RUN_ID"], "pid": os.getpid(),
        "creation_time": psutil.Process().create_time()}
    heartbeat = {**identity, "status": "RUNNING", "progress_count": 0}
    if mode in ("auth", "quota"):
        heartbeat["interruption"] = "AUTH_REQUIRED" if mode == "auth" else "QUOTA_EXHAUSTED"
    runner.save(os.environ["S6D_HEARTBEAT_PATH"], heartbeat)
    counter = Path(result_path).with_name("child_launch_count.txt")
    with counter.open("a", encoding="utf-8") as f:
        f.write(identity["child_run_id"] + "\n")
    if mode == "hold_ignore_stop":
        time.sleep(20)
        return 5
    time.sleep(.15)
    if mode in ("failed", "auth", "quota"):
        return 3
    if mode == "missing":
        return 0
    runner.save(result_path, {"scientific_predicate": "FAIL" if mode == "bad_predicate" else "PASS", "fixture_only": True})
    runner.save(os.environ["S6D_COMPLETION_PATH"], {**identity, "status": "COMPLETE"})
    runner.save(os.environ["S6D_HEARTBEAT_PATH"], {**heartbeat, "progress_count": 1, "status": "COMPLETE"})
    return 0


def make_case(root, name, modes=("normal",), **override):
    directory = root / name
    directory.mkdir(parents=True)
    jobs = []
    for i, mode in enumerate(modes):
        jobroot = directory / ("job" + str(i))
        jobroot.mkdir()
        jobs.append({"job_id": "job" + str(i), "kind": "offline", "workload": "sensitive",
            "argv": [sys.executable, str(Path(__file__).resolve()), "--child-mode", mode,
                     "--result", str(jobroot / "result.json")], "cwd": str(directory),
            "source_bindings": [runner.binding(__file__), runner.binding(runner.__file__)],
            "heartbeat_path": str(jobroot / "heartbeat.json"), "completion_path": str(jobroot / "completion.json"),
            "stop_request_path": str(jobroot / "STOP_REQUEST.json"), "allow_owned_termination": True,
            "timeout_s": 4, "stall_after_s": 3, "heartbeat_stale_s": 1, "stop_grace_s": .1,
            "expected_artifacts": [{"path": str(jobroot / "result.json"), "format": "json",
                "min_bytes": 1, "expected_fields": {"scientific_predicate": "PASS", "fixture_only": True}}], **override})
    queue = {"schema": "s6d_approved_job_queue_v1", "run_id": "fixture_" + name, "owner_thread_id": "fixture_thread",
        "owner_session_id": "fixture_session", "fixture_only": True, "runner_sha256": runner.binding(runner.__file__)["sha256"],
        "payload_policy": {"new_payload_roots": [str(directory)], "max_new_payload_bytes": 10 * 1024 ** 2},
        "disk_policy": [], "jobs": jobs}
    queue_path = directory / "queue.json"
    runner.save(queue_path, queue, exclusive=True)
    queue_hash = runner.binding(queue_path)["sha256"]
    approval = {"schema": "s6d_queue_approval_v1", "run_id": queue["run_id"], "queue_sha256": queue_hash,
        "authorization_ref": "Bounded local model-free supervisor fixtures authorized by root",
        "approved_job_sha256": [runner.digest(job) for job in jobs],
        "executable_bindings": [runner.binding(sys.executable)], "allowed_working_directories": [str(directory)],
        "allowed_output_roots": [str(directory)]}
    approval_path = directory / "approval.json"
    runner.save(approval_path, approval, exclusive=True)
    arguments = (queue_path, approval_path, queue_hash, runner.binding(approval_path)["sha256"], directory / "state")
    return queue, approval, arguments


def rejected(call):
    try:
        call()
    except (ValueError, KeyError, FileNotFoundError):
        return True
    raise AssertionError("expected rejection")


def fixtures(output):
    output = output.resolve()
    if output.exists():
        raise ValueError("fixture output must be new")
    output.mkdir(parents=True)
    outcomes = []
    def record(name, detail):
        outcomes.append({"name": name, "status": "PASS", "detail": detail})
    baseline = dict(alive=True, exit_code=None, heartbeat_valid=True, heartbeat_age=1,
        progress_age=1, elapsed=1, heartbeat_stale=30, stall_after=60, timeout=100, completion_ok=False)
    assert runner.classify(**baseline)[0] == "WAIT"
    assert runner.classify(**{**baseline, "heartbeat_age": 40}) == ("WAIT", "alive with stale/missing heartbeat; not assumed dead or hung")
    assert runner.classify(**{**baseline, "progress_age": 70})[0] == "REVIEW_FAILURE"
    assert runner.classify(**{**baseline, "alive": False, "exit_code": 0})[0] == "REPORT_BLOCKED"
    record("health_classification", "normal, stale-alive, true declared progress stall, missing completion")
    assert not runner.process_matches(os.getpid(), psutil.Process().create_time() + 1)
    assert not runner.process_matches(123456789, 0)
    record("pid_identity", "reused PID creation mismatch and exited/absent PID rejected")
    partial = output / "partial.json"
    partial.write_text('{"value":', encoding="utf-8")
    thread = threading.Thread(target=lambda: (time.sleep(.02), partial.write_text('{"value":1}', encoding="utf-8")))
    thread.start()
    assert runner.load(partial, retries=4, delay=.03) == {"value": 1}
    thread.join()
    partial.write_text('{"value":', encoding="utf-8")
    rejected(lambda: runner.load(partial, retries=2, delay=.001))
    record("partial_json", "bounded retry accepts completed write and rejects persistent truncation")
    q, a, arguments = make_case(output, "normal_resume", modes=("normal", "normal"))
    first = runner.Supervisor(*arguments, test_interval=.03).run()
    assert first["action"] == "FINISH"
    resumed = runner.Supervisor(*arguments, test_interval=.03).run()
    assert resumed["action"] == "FINISH"
    assert all(len(Path(j["completion_path"]).with_name("child_launch_count.txt").read_text().splitlines()) == 1 for j in q["jobs"])
    record("normal_and_resume", "two actual tiny children complete; explicit resume revalidates artifacts and launches zero completed jobs")
    for mode, expected in (("failed", "REVIEW_FAILURE"), ("missing", "REPORT_BLOCKED"),
                           ("bad_predicate", "REPORT_BLOCKED"), ("auth", "REPORT_BLOCKED"), ("quota", "REPORT_BLOCKED")):
        q, a, arguments = make_case(output, mode, modes=(mode,))
        result = runner.Supervisor(*arguments, test_interval=.03).run()
        assert result["action"] == expected, (mode, result)
        assert len(Path(q["jobs"][0]["completion_path"]).with_name("child_launch_count.txt").read_text().splitlines()) == 1
        record(mode, "one bounded actual child, expected stop state, no automatic retry; predicate PASS never inferred from exit0")
    q, a, arguments = make_case(output, "owned_timeout", modes=("hold_ignore_stop",), timeout_s=.3, stall_after_s=2)
    result = runner.Supervisor(*arguments, test_interval=.03).run()
    assert result["action"] == "REVIEW_FAILURE" and "TERMINATION_VERIFIED" in result["reason"]
    assert Path(q["jobs"][0]["stop_request_path"]).exists()
    record("owned_offline_termination", "STOP_REQUEST grace precedes PID+creation-guarded termination of only fixture child")
    q, a, arguments = make_case(output, "allowlist")
    assert runner.validate_queue(q, a, a["queue_sha256"])
    for kind in ("inline_code", "cwd", "output_escape", "hash", "shell", "unsafe_id"):
        changed, approval = copy.deepcopy(q), copy.deepcopy(a)
        job = changed["jobs"][0]
        if kind == "inline_code": job["argv"].append("-c")
        if kind == "cwd": job["cwd"] = str(output.parent)
        if kind == "output_escape": job["heartbeat_path"] = str(output.parent / "not_owned.json")
        if kind == "hash": job["source_bindings"][0]["sha256"] = "0" * 64
        if kind == "shell": job["argv"][0] = "C:\\Windows\\System32\\cmd.exe"
        if kind == "unsafe_id": job["job_id"] = "../other"
        approval["approved_job_sha256"] = [runner.digest(job)]
        rejected(lambda: runner.validate_queue(changed, approval, approval["queue_sha256"]))
    record("allowlist_and_bindings", "inline code, cwd escape, output escape, source tamper, shell and path-shaped job IDs rejected")
    for value in (float("nan"), float("inf"), -float("inf"), True):
        assert not runner.finite_number(value, strict=True)
        changed, approval = copy.deepcopy(q), copy.deepcopy(a)
        changed["jobs"][0]["timeout_s"] = value
        # A nonfinite job cannot even acquire a canonical approved digest.
        rejected(lambda: runner.digest(changed["jobs"][0])) if not isinstance(value, bool) else None
        if isinstance(value, bool):
            approval["approved_job_sha256"] = [runner.digest(changed["jobs"][0])]
            rejected(lambda: runner.validate_queue(changed, approval, approval["queue_sha256"]))
    record("finite_policy_numbers", "NaN/infinities rejected in canonical policy and booleans rejected as numeric durations")
    for key in ("home", "CodeX_Home", "userPROFILE", "s6d_child_run_id"):
        changed, approval = copy.deepcopy(q), copy.deepcopy(a)
        changed["jobs"][0]["environment"] = {key: "forbidden"}
        approval["approved_job_sha256"] = [runner.digest(changed["jobs"][0])]
        rejected(lambda: runner.validate_queue(changed, approval, approval["queue_sha256"]))
    record("windows_environment_identity", "case-insensitive system and S6D run-identity names rejected")
    production = copy.deepcopy(q)
    production["fixture_only"] = False
    rejected(lambda: runner.validate_queue(production, a, a["queue_sha256"]))
    production["campaign"] = {"started_utc": runner.CAMPAIGN_STARTED_UTC,
        "deadline_utc": "2026-09-16T19:53:57+00:00", "closeout_reserve_s": 2700}
    rejected(lambda: runner.validate_queue(production, a, a["queue_sha256"]))
    production["disk_policy"] = [{"path": "C:/", "minimum_free_bytes": 50 * 1024 ** 3},
                                {"path": "G:/", "minimum_free_bytes": 75 * 1024 ** 3}]
    assert runner.validate_queue(production, a, a["queue_sha256"])
    assert runner.work_deadline(production) == runner.timestamp("2026-09-16T19:08:57+00:00")
    for field, value in (("closeout_reserve_s", float("nan")), ("closeout_reserve_s", 2699),
                         ("deadline_utc", "2026-09-17T19:53:57+00:00"),
                         ("started_utc", "2026-09-14T19:53:57+00:00")):
        bad = copy.deepcopy(production)
        bad["campaign"][field] = value
        rejected(lambda: runner.validate_queue(bad, a, a["queue_sha256"]))
    record("campaign_admission", "fixed start72h max,45min closeout, finite policy and production C50/G75GiB floors enforced; fixture exemption explicit")
    qexp, aexp, exp_args = make_case(output, "expired_campaign")
    qexp.update(fixture_only=False, campaign={"started_utc": runner.CAMPAIGN_STARTED_UTC,
        "deadline_utc": "2026-09-13T20:39:57+00:00", "closeout_reserve_s": 2700}, disk_policy=production["disk_policy"])
    runner.save(exp_args[0], qexp)
    aexp["queue_sha256"] = runner.binding(exp_args[0])["sha256"]
    runner.save(exp_args[1], aexp)
    expired = runner.Supervisor(exp_args[0], exp_args[1], aexp["queue_sha256"], runner.binding(exp_args[1])["sha256"], exp_args[-1]).run()
    assert expired["action"] == "REPORT_BLOCKED" and "deadline" in expired["reason"]
    assert not Path(qexp["jobs"][0]["heartbeat_path"]).exists()
    record("expired_campaign_prelaunch", "fixed work deadline excludes new child before launch; zero child files")
    qhealth, ahealth, health_args = make_case(output, "health_campaign_deadline", modes=("hold_ignore_stop",))
    old_deadline, calls = runner.work_deadline, []
    def crossing_deadline(queue):
        calls.append(1)
        return time.time() + 30 if len(calls) == 1 else time.time() - 1
    runner.work_deadline = crossing_deadline
    try:
        crossed = runner.Supervisor(*health_args, test_interval=.03).run()
    finally:
        runner.work_deadline = old_deadline
    assert crossed["action"] == "REPORT_BLOCKED" and "deadline reached" in crossed["reason"]
    assert Path(qhealth["jobs"][0]["stop_request_path"]).exists()
    record("campaign_deadline_during_health", "synthetic deadline crossing signals STOP then verifies owned tiny-child termination; no production process")
    lockdir = output / "lock_case"
    lockdir.mkdir()
    lock = runner.OwnerLock(lockdir, "fixture_lock", "a" * 64)
    lock.acquire()
    rejected(lambda: runner.OwnerLock(lockdir, "fixture_lock", "a" * 64).acquire())
    lock.close()
    record("exclusive_owner", "live PID+creation owner prevents second supervisor before launch")
    q, a, arguments = make_case(output, "hardware_policy")
    supervisor = runner.Supervisor(*arguments, test_interval=.01)
    supervisor.lock.acquire()
    identity = {"run_id": q["run_id"], "job_id": "fixture_hardware", "child_run_id": "fixture_child", "pid": 123456789, "creation_time": 0}
    job = {"kind": "hardware", "stop_grace_s": .03, "stop_request_path": str(output / "hardware_policy/STOP_REQUEST.json"),
        "restoration_path": str(output / "hardware_policy/RESTORATION.json"), "allow_owned_termination": True}
    assert runner.terminate_owned_offline(job, identity) == "TERMINATION_NOT_AUTHORIZED"
    result = supervisor.stop_child(job, identity, "fixture only; no device exists")
    assert result == "HARDWARE_RESTORATION_PENDING_NO_TERMINATION" and supervisor.lock.keep_unresolved
    assert supervisor.lock.close() == "RETAINED_UNRESOLVED_HARDWARE"
    rejected(lambda: runner.OwnerLock(arguments[-1], q["run_id"], a["queue_sha256"]).acquire())
    runner.save(job["restoration_path"], {**identity, "status": "RESTORED", "verified": True})
    assert runner.restored(job, identity)
    assert not runner.restored(job, {**identity, "child_run_id": "wrong"})
    record("hardware_restoration_guard", "no hardware process/device launched; simulated missing restoration retains blocking lock, wrong identity rejected, hardware termination forbidden")
    called = []
    awake = runner.KeepAwake(True, api=lambda value: (called.append(value), 1)[1])
    awake.acquire()
    assert awake.close()["restored"] and called == [0x80000001, 0x80000000]
    assert runner.KeepAwake().close()["requested"] is False
    failed = runner.KeepAwake(True, api=lambda value: 1 if value == 0x80000001 else 0)
    failed.acquire()
    assert failed.close()["status"] == "RESTORATION_FAILED"
    record("keep_awake_ownership", "simulated API only: restore only after owned acquisition and expose failure")
    delta = runner.bounded_delta({"run_id": "test", "reason": "x" * 20000, "next_command": "x" * 20000,
        "checkpoint_path": "x" * 20000, "log_path": "x" * 20000, "resource_maxima": {"rss_bytes": 1}, "action": "WAIT"})
    assert len(json.dumps(delta, separators=(",", ":")).encode()) <= 2048
    record("delta_and_manual_continuation", "<=2048 bytes; real fixture resume requests contain explicit thread/session and argv; no model/tool turn installed")
    # Any already-completed artifact change blocks reuse and never restarts that job.
    _, _, normal_args = (None, None, None)
    normal_dir = output / "normal_resume"
    queue_path, approval_path = normal_dir / "queue.json", normal_dir / "approval.json"
    queue, approval = runner.load(queue_path), runner.load(approval_path)
    artifact = Path(queue["jobs"][0]["expected_artifacts"][0]["path"])
    runner.save(artifact, {"scientific_predicate": "PASS", "fixture_only": True, "tampered": True})
    blocked = runner.Supervisor(queue_path, approval_path, runner.binding(queue_path)["sha256"],
        runner.binding(approval_path)["sha256"], normal_dir / "state", test_interval=.03).run()
    assert blocked["action"] == "REPORT_BLOCKED"
    record("completed_artifact_changed", "semantic PASS alone is insufficient: immutable completed receipt hash changes block resume")
    receipt = {"status": "PASS", "fixture_count": len(outcomes), "fixtures": outcomes,
        "scope": "Only tiny local Python child fixtures; zero neural/device/production jobs and no OS keep-awake change",
        "runner": runner.binding(runner.__file__), "fixtures_code": runner.binding(__file__),
        "production_queue_available": False, "unattended_model_resume_installed": False,
        "model_usage": None, "manual_fallback": True, "created_utc": runner.utc()}
    runner.save(output / "FRAMEWORK_FIXTURE_RECEIPT.json", receipt, exclusive=True)
    print(json.dumps({"status": "PASS", "fixture_count": len(outcomes), "receipt": str(output / "FRAMEWORK_FIXTURE_RECEIPT.json")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child-mode")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args.child_mode:
        raise SystemExit(child(args.child_mode, args.result))
    if args.output is None:
        parser.error("--output required for fixtures")
    fixtures(args.output)
