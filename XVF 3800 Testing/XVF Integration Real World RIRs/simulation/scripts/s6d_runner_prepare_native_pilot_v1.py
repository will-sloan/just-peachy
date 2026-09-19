"""Prepare held12-job native queue; never launch. See matching README."""
from __future__ import annotations
import argparse
import copy
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode = True
import s6d_runner_v1 as runner

MANIFEST_SHA = "ec110adcbaf230c5f33b49629967e163f5d526b7a339123c05fb000a14d7138f"
HELPER_SHA = "29ccc47374d8830d72b5214e64e62c08c41ad141265571fb149a5420fe0aed12"
OWNER = "01a0812d-3ff0-7ed0-a06c-4df61b62a459"


def prepare(report):
    report = report.resolve()
    sim = report.parents[2]
    scripts = sim / "scripts"
    manifest_path = report / "application/native_pilot_v3/MANIFEST.json"
    manifest_bound = runner.binding(manifest_path, MANIFEST_SHA)
    manifest = runner.load(manifest_path)
    helper = runner.binding(manifest["helper"]["path"], HELPER_SHA)
    if manifest["job_count"] != 12 or len(manifest["jobs"]) != 12:
        raise ValueError("reviewed twelve-cell native manifest required")
    epoch = report / "runner/source_epoch_ready_v2"
    epoch.mkdir(parents=True, exist_ok=False)
    names = ("s6d_runner_v1.py", "s6d_runner_README.md", "s6d_runner_fixtures_v1.py", "s6d_runner_fixtures_README.md",
        "s6d_runner_native_pilot_v1.py", "s6d_runner_native_pilot_README.md",
        "s6d_runner_native_pilot_fixtures_v1.py", "s6d_runner_native_pilot_fixtures_README.md")
    for name in names:
        shutil.copy2(scripts / name, epoch / name)
    frozen = {name: runner.binding(epoch / name) for name in names}
    new_payload_root = Path("G:/Just_Peachy_S6D/20260913T195357Z")
    listening = sim / "listening/S45_all240_v1"
    proposed = report / "runner/native_pilot_proposed_v1"
    proposed.mkdir(exist_ok=False)
    jobs = []
    for native in manifest["jobs"]:
        protocol = report / "runner/production_protocol_v1" / native["job_id"]
        completion = protocol / "COMPLETION.json"
        code = [frozen["s6d_runner_v1.py"], frozen["s6d_runner_native_pilot_v1.py"], helper, manifest_bound] + manifest["execution_files"]
        unique_code = list({b["path"]: b for b in code}.values())
        jobs.append({"job_id": native["job_id"], "kind": "offline", "workload": "sensitive",
            "argv": [sys.executable, frozen["s6d_runner_native_pilot_v1.py"]["path"],
                "--helper", helper["path"], "--helper-sha256", helper["sha256"],
                "--manifest", manifest_bound["path"], "--manifest-sha256", manifest_bound["sha256"],
                "--native-job-id", native["job_id"]], "cwd": manifest["source_root"],
            "source_bindings": unique_code, "heartbeat_path": str(protocol / "HEARTBEAT.json"),
            "completion_path": str(completion), "stop_request_path": str(protocol / "STOP_REQUEST.json"),
            "timeout_s": 360, "stall_after_s": 180, "heartbeat_stale_s": 45, "stop_grace_s": 75,
            "allow_owned_termination": True,
            "expected_artifacts": [{"path": str(completion), "format": "json", "min_bytes": 1,
                "expected_fields": {"status": "COMPLETE", "failure": None, "native_job_id": native["job_id"],
                    "protocol_observer_closed": True, "protocol_observer_errors": [],
                    "native_run_one_same_process": True, "subprocess_spawned_by_wrapper": False,
                    "stop_requested": False, "manifest.sha256": manifest_bound["sha256"], "helper.sha256": helper["sha256"]}},
                {"path": str(Path(native["output"]) / "RESULT.json"), "format": "json", "min_bytes": 1,
                 "expected_fields": {"status": "COMPLETE", "failure": None, "native_tested": True,
                    "resource_observer_closed": True, "observer_errors": [], "completion_errors": [],
                    "event_consumer_drained": True, "telemetry.state": "COMPLETED", "job.job_id": native["job_id"],
                    "manifest.sha256": manifest_bound["sha256"]}}],
            "native_input_seconds": native["audio_duration_sec"],
            "stop_policy_note": "Reviewed same-process checkpoint calls engine.stop;75s grace permits helper60s drain and observer closure before exact owned offline termination"})
    queue = {"schema": "s6d_approved_job_queue_v1", "run_id": report.name, "owner_thread_id": OWNER,
        "owner_session_id": OWNER, "fixture_only": False, "runner_sha256": frozen["s6d_runner_v1.py"]["sha256"],
        "campaign": {"started_utc": runner.CAMPAIGN_STARTED_UTC, "deadline_utc": "2026-09-16T19:53:57+00:00", "closeout_reserve_s": 2700},
        "disk_policy": [{"path": "C:/", "minimum_free_bytes": 50 * 1024 ** 3}, {"path": "G:/", "minimum_free_bytes": 75 * 1024 ** 3}],
        "payload_policy": {"new_payload_roots": [str(report), str(new_payload_root), str(listening)], "max_new_payload_bytes": 40 * 1024 ** 3},
        "jobs": jobs, "native_manifest": manifest_bound, "source_epoch": str(epoch), "created_utc": runner.utc(),
        "production_status": "PROPOSED_ROOT_ADOPTION_REQUIRED", "scientific_scope": "12-cell native diagnostic pilot only; no full-bank/finalist/hardware/CM5 result inferred"}
    queue_path = proposed / "PROPOSED_QUEUE.json"
    runner.save(queue_path, queue, exclusive=True)
    queue_bound = runner.binding(queue_path)
    approval = {"schema": "s6d_queue_approval_v1", "run_id": report.name, "queue_sha256": queue_bound["sha256"],
        "authorization_ref": None, "approved_job_sha256": [], "proposed_job_sha256": [runner.digest(j) for j in jobs],
        "executable_bindings": [runner.binding(sys.executable)], "allowed_working_directories": [manifest["source_root"]],
        "allowed_output_roots": [str(report), str(new_payload_root), str(listening)],
        "approval_state": "ROOT_ADOPTION_PENDING_NOT_EXECUTABLE", "owner_identity_authority": "Root verified both owner IDs; child agent task ID deliberately excluded"}
    approval_path = proposed / "PROPOSED_APPROVAL.json"
    runner.save(approval_path, approval, exclusive=True)
    try:
        runner.validate_queue(queue, approval, queue_bound["sha256"])
    except ValueError:
        pending_rejected = True
    else:
        raise AssertionError("pending approval unexpectedly executable")
    structural = copy.deepcopy(approval)
    structural["authorization_ref"] = "STRUCTURE_VALIDATION_ONLY_NOT_PERSISTED_AS_APPROVAL"
    structural["approved_job_sha256"] = approval["proposed_job_sha256"]
    runner.validate_queue(queue, structural, queue_bound["sha256"])
    runner.save(proposed / "PROPOSED_ADMISSION_CHECK.json", {"status": "STRUCTURE_VALID_PENDING_ROOT_ADOPTION",
        "jobs": 12, "source_audio_seconds": sum(j["native_input_seconds"] for j in jobs),
        "queue": queue_bound, "approval": runner.binding(approval_path), "source_epoch": frozen,
        "pending_approval_rejected_by_runner": pending_rejected, "production_jobs_launched": 0,
        "root_owner_ids": OWNER, "structure_validation_only": True,
        "root_adoption_required": "Create a distinct adopted approval with actual root authorization_ref and approved_job_sha256 equal to reviewed proposed_job_sha256; bind its SHA explicitly, then validate-only before root launch.",
        "reviewed_deadline_work_end_utc": "2026-09-16T19:08:57+00:00", "script": runner.binding(__file__)}, exclusive=True)
    print({"status": "PROPOSED_NOT_LAUNCHED", "jobs": 12, "queue": queue_bound,
        "approval": runner.binding(approval_path), "frozen_wrapper": frozen["s6d_runner_native_pilot_v1.py"]})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    prepare(p.parse_args().report)
