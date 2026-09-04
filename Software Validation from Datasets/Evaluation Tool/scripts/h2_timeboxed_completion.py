"""Deadline-aware completion controller for the H2 v17 scientific campaign.

This wrapper preserves completed evidence, gives the active development job a
graceful atomic-boundary stop, runs the frozen held-out comparison first, then
uses any remaining compute window for critical engineering validation.  It
never changes model parameters or frozen decision policies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any


MEMORY_DEV = "h2p5_h2_session_memory_enhanced_development_a6462711fc"
HELDOUT_JOBS = (
    "h2p7_h2_known_only_heldout_b5b5707476",
    "h2p7_h2_session_memory_enhanced_heldout_850ae96d34",
)
SCIENCE_JOBS = (
    "h2p7_h2_development_policy_freeze_df5fab350a",
    "h2p7_h2_known_only_heldout_b5b5707476",
    "h2p7_h2_session_memory_enhanced_heldout_850ae96d34",
)
ORIGINAL_BOOTSTRAP_JOB = "h2p7_h2_speaker_hierarchical_bootstrap_69921c45e4"
ENGINEERING_JOBS = (
    "h2p6_h2_current_common_app_targeted_validation_634db2b15e",
    "h2p6_h2_portable_onnx_fp32_export_ab64c99d16",
    "h2p6_h2_portable_onnx_fp32_frozen_fixture_parity_00fe1b8a0e",
    "h2p6_h2_linux_arm64_package_2b90ee6f83",
    "h2p6_h2_reliability_cd5a42580a",
)
FREEZE_RESOURCE_JOBS = (
    "h2p6_h2_known_only_serial_resource_1e27a1e89d",
    "h2p6_h2_session_anonymous_serial_resource_e379f9fbbb",
    "h2p6_h2_session_memory_enhanced_serial_resource_666392efba",
)
DEFERRED_JOBS = {
    "h2p6_h2_long_session_reference_b2ecb1e646": "30-60 minute long-session expansion",
    "h2p7_h2_session_anonymous_heldout_0efd6b5205": "third product mode held-out repeat",
    "h2p7_h2_original_sherpa_reduced_regression_8387b44dcd": "legacy ASR regression",
    "h2p7_h2_commonvoice_60plus_asr_c4433ded6f": "native diagnostic repeat",
    "h2p7_h2_chime6_diarization_only_8fac12ee7c": "native diagnostic repeat",
    "h2p7_h2_voices_asr_e2d97a78f4": "native diagnostic repeat",
    "h2p7_h2_long_session_heldout_8source_30m_60m_3d40d2c2ea": "eight-source 30/60 minute expansion",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    for attempt in range(20):
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                raise TypeError(f"{path} is not a JSON object")
            return value
        except (OSError, json.JSONDecodeError):
            if attempt == 19:
                raise
            time.sleep(0.1)
    raise AssertionError("unreachable")


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for attempt in range(40):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.1)


class Timebox:
    def __init__(self, args: argparse.Namespace) -> None:
        self.tool_root = Path(args.tool_root).resolve()
        self.workspace = Path(args.workspace).resolve()
        self.results_root = Path(args.results_root).resolve()
        self.summary_root = Path(args.summary_root).resolve()
        self.config = Path(args.config).resolve()
        self.deadline = parse_utc(args.deadline_utc)
        self.compute_stop = self.deadline - timedelta(minutes=args.packaging_reserve_minutes)
        self.python = Path(sys.executable).resolve()
        self.control = self.workspace / "timeboxed_completion"
        self.log_path = self.workspace / "logs" / "timeboxed_completion.jsonl"
        self.stop_path = self.workspace / "stop_request.json"
        self.state_path = self.workspace / "program_state.json"
        self.manifest_path = self.workspace / "job_manifest.json"
        self.launcher = (
            self.workspace
            / "diagnostics/pre_freeze_selector_fix_staging/h2_prefreeze_selector_correction_bootstrap.py"
        )
        self.timeboxed_freeze_launcher = (
            self.tool_root / "scripts/h2_timeboxed_freeze_bootstrap.py"
        )
        self.scope_path = self.control / "scope_amendment.json"
        self.process: subprocess.Popen[str] | None = None

    def event(self, kind: str, **details: Any) -> None:
        row = {"at_utc": utc_now(), "kind": kind, **details}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    def stop_request(self, reason: str) -> None:
        if self.stop_path.exists():
            return
        request = {
            "schema_version": "h2-program-stop-request.v1",
            "requested_at_utc": utc_now(),
            "reason": reason,
            "requested_by": "h2_timeboxed_completion.py",
            "hard_deadline_utc": self.deadline.isoformat().replace("+00:00", "Z"),
        }
        write_json_atomic(self.stop_path, request)
        self.event("GRACEFUL_STOP_REQUESTED", reason=reason, request_sha256=sha256_file(self.stop_path))

    def wait_for_initial_boundary(self) -> None:
        self.event("WAITING_FOR_ACTIVE_DEVELOPMENT", job_id=MEMORY_DEV)
        while True:
            state = read_json(self.state_path)
            row = state["jobs"][MEMORY_DEV]
            if row["state"] == "COMPLETE":
                self.stop_request("Apply user-authorized ten-hour scope at the next controller boundary")
                break
            if row["state"] == "FAILED":
                raise RuntimeError(f"active development job failed: {row.get('last_error')}")
            if datetime.now(timezone.utc) >= self.compute_stop:
                self.stop_request("Compute reserve reached before development job completed")
                break
            time.sleep(5)
        limit = time.monotonic() + 900
        while time.monotonic() < limit:
            state = read_json(self.state_path)
            lock = self.workspace / "h2_program_run.lock"
            if not lock.exists():
                state.update({
                    "status": "STOPPED",
                    "detail": "Superseded legacy controller is absent; safe timebox handoff boundary recorded",
                    "current_job_id": None,
                    "updated_at_utc": utc_now(),
                })
                write_json_atomic(self.state_path, state)
                self.event("INITIAL_CONTROLLER_ABSENT_AT_BOUNDARY", prior_status=state.get("status"))
                return
            if state.get("status") in {"STOPPED", "PAUSED", "BLOCKED"}:
                self.event("INITIAL_CONTROLLER_STOPPED", status=state.get("status"), detail=state.get("detail"))
                lock_limit = time.monotonic() + 120
                while lock.exists() and time.monotonic() < lock_limit:
                    time.sleep(1)
                if lock.exists():
                    raise TimeoutError("existing controller stopped but did not release its campaign lock")
                return
            time.sleep(2)
        raise TimeoutError("existing controller did not honor the graceful stop within 15 minutes")

    def apply_scope(self) -> None:
        self.control.mkdir(parents=True, exist_ok=True)
        if self.scope_path.exists():
            receipt = read_json(self.scope_path)
            claimed = receipt.pop("receipt_sha256", None)
            actual = hashlib.sha256(canonical_bytes(receipt)).hexdigest()
            if claimed != actual:
                raise RuntimeError("existing timebox scope receipt checksum is invalid")
            self.event("SCOPE_ALREADY_APPLIED", receipt_sha256=claimed)
            return
        state = read_json(self.state_path)
        manifest = read_json(self.manifest_path)
        by_id = {row["job_id"]: row for row in manifest["jobs"]}
        missing = (set(SCIENCE_JOBS) | set(ENGINEERING_JOBS) | set(DEFERRED_JOBS)) - set(by_id)
        if missing:
            raise RuntimeError(f"declared timebox jobs missing from frozen manifest: {sorted(missing)}")
        opened = [
            job_id for job_id, row in state["jobs"].items()
            if by_id[job_id].get("split") == "evaluation" and row.get("state") not in {"PENDING", "WAITING_PROMOTION", "SUPERSEDED"}
        ]
        if opened:
            raise RuntimeError(f"held-out firewall was already opened before amendment: {opened}")
        snapshot = self.control / "program_state.pre_timebox.json"
        shutil.copy2(self.state_path, snapshot)
        receipt: dict[str, Any] = {
            "schema_version": "h2-timeboxed-scope-amendment.v1",
            "created_at_utc": utc_now(),
            "hard_deadline_utc": self.deadline.isoformat().replace("+00:00", "Z"),
            "compute_stop_utc": self.compute_stop.isoformat().replace("+00:00", "Z"),
            "pre_amendment_state_sha256": sha256_file(snapshot),
            "job_manifest_sha256": sha256_file(self.manifest_path),
            "evaluation_material_inspected": False,
            "retuning_permitted": False,
            "completed_evidence_modified": False,
            "science_first_jobs": list(SCIENCE_JOBS),
            "post_freeze_engineering_jobs": list(ENGINEERING_JOBS),
            "deferred_jobs": DEFERRED_JOBS,
            "method": "Frozen held-out comparison first; engineering validation second; hard deadline enforced.",
        }
        receipt["receipt_sha256"] = hashlib.sha256(canonical_bytes(receipt)).hexdigest()
        write_json_atomic(self.scope_path, receipt)

        now = utc_now()
        keep_pending = set(SCIENCE_JOBS)
        for job_id, row in state["jobs"].items():
            if row.get("state") == "COMPLETE":
                continue
            if job_id in keep_pending:
                row["state"] = "PENDING"
                row["latest_activity"] = "scheduled by checksum-bound ten-hour science-first amendment"
                row["last_error"] = None
            else:
                row["state"] = "SUPERSEDED"
                row["latest_activity"] = "deferred by checksum-bound ten-hour scope amendment"
                row["last_error"] = None
                row["completed_at_utc"] = now
            row["updated_at_utc"] = now
        state.update({
            "status": "STOPPED",
            "detail": "Ten-hour scope amendment applied before held-out evaluation",
            "current_job_id": None,
            "target_wall_hours": 10.0,
            "target_is_advisory_only": False,
            "automatic_time_cutoff": True,
            "hard_deadline_utc": receipt["hard_deadline_utc"],
            "compute_stop_utc": receipt["compute_stop_utc"],
            "timeboxed_scope_receipt": str(self.scope_path),
            "timeboxed_scope_receipt_sha256": receipt["receipt_sha256"],
            "updated_at_utc": now,
        })
        write_json_atomic(self.state_path, state)
        self.stop_path.unlink(missing_ok=True)
        self.event("SCOPE_APPLIED", receipt_sha256=receipt["receipt_sha256"])

    def launch(
        self,
        maximum_jobs: int,
        label: str,
        *,
        launcher: Path | None = None,
    ) -> subprocess.Popen[str]:
        selected_launcher = launcher or self.launcher
        command = [
            str(self.python), "-B", str(selected_launcher), "Resume",
            "--workspace", str(self.workspace),
            "--results-root", str(self.results_root),
            "--summary-root", str(self.summary_root),
            "--config", str(self.config),
            "--retry-failed", "--maximum-jobs", str(maximum_jobs),
        ]
        stdout = (self.workspace / "logs" / f"timeboxed_{label}.stdout.log").open("a", encoding="utf-8")
        stderr = (self.workspace / "logs" / f"timeboxed_{label}.stderr.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen(command, cwd=self.tool_root, stdout=stdout, stderr=stderr, text=True)
        self.event(
            "PASS_LAUNCHED", label=label, pid=self.process.pid,
            maximum_jobs=maximum_jobs, launcher=str(selected_launcher),
        )
        return self.process

    def wait_pass(self, label: str) -> bool:
        assert self.process is not None
        while self.process.poll() is None:
            now = datetime.now(timezone.utc)
            if now >= self.compute_stop and not self.stop_path.exists():
                self.stop_request("Packaging reserve reached")
            if now >= self.deadline:
                self.event("HARD_DEADLINE_PROCESS_TERMINATION", label=label, pid=self.process.pid)
                subprocess.run(
                    ["taskkill.exe", "/PID", str(self.process.pid), "/T", "/F"],
                    capture_output=True, text=True, check=False,
                )
                return False
            time.sleep(5)
        code = self.process.returncode
        state = read_json(self.state_path)
        self.event("PASS_FINISHED", label=label, exit_code=code, status=state.get("status"), detail=state.get("detail"))
        return code == 0 and state.get("status") in {"PAUSED", "STOPPED", "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"}

    def reopen_engineering(self) -> int:
        state = read_json(self.state_path)
        now = utc_now()
        count = 0
        retained = set(SCIENCE_JOBS) | set(ENGINEERING_JOBS)
        for job_id, row in state["jobs"].items():
            if job_id not in retained and row.get("state") != "COMPLETE":
                row.update({
                    "state": "SUPERSEDED",
                    "latest_activity": "deferred by checksum-bound ten-hour scope amendment",
                    "last_error": None,
                    "completed_at_utc": now,
                    "updated_at_utc": now,
                })
        for job_id in ENGINEERING_JOBS:
            row = state["jobs"][job_id]
            if row.get("state") != "COMPLETE":
                row.update({
                    "state": "PENDING", "latest_activity": "post-freeze engineering validation scheduled",
                    "last_error": None, "completed_at_utc": None, "updated_at_utc": now,
                })
                count += 1
        state.update({"status": "STOPPED", "detail": "Science pass complete; engineering pass scheduled", "current_job_id": None, "updated_at_utc": now})
        write_json_atomic(self.state_path, state)
        self.stop_path.unlink(missing_ok=True)
        self.event("ENGINEERING_REOPENED", pending_jobs=count)
        return count

    def prepare_freeze_resource_prerequisites(self) -> int:
        """Schedule the three matched serial-resource rows required by freeze."""

        state = read_json(self.state_path)
        heldout_opened = [
            job for job in HELDOUT_JOBS
            if state["jobs"][job].get("state") not in {"PENDING", "SUPERSEDED"}
        ]
        if heldout_opened:
            raise RuntimeError(
                "cannot revise freeze prerequisites after held-out opened: "
                f"{heldout_opened}"
            )
        revision_path = self.control / "scope_amendment.revision_2.json"
        if not revision_path.exists():
            original = read_json(self.scope_path)
            revision: dict[str, Any] = {
                "schema_version": "h2-timeboxed-scope-amendment-revision.v1",
                "created_at_utc": utc_now(),
                "prior_receipt_sha256": original["receipt_sha256"],
                "job_manifest_sha256": sha256_file(self.manifest_path),
                "evaluation_material_inspected": False,
                "retuning_permitted": False,
                "completed_evidence_modified": False,
                "change": "Run all three matched serial-resource validations required by the existing frozen-policy gate; retain held-out comparison for two product modes only.",
                "freeze_resource_prerequisites": list(FREEZE_RESOURCE_JOBS),
                "hard_deadline_utc": self.deadline.isoformat().replace("+00:00", "Z"),
            }
            revision["receipt_sha256"] = hashlib.sha256(canonical_bytes(revision)).hexdigest()
            write_json_atomic(revision_path, revision)
        revision = read_json(revision_path)
        claimed = revision.pop("receipt_sha256", None)
        if claimed != hashlib.sha256(canonical_bytes(revision)).hexdigest():
            raise RuntimeError("freeze-prerequisite scope revision checksum is invalid")

        now = utc_now()
        keep = set(FREEZE_RESOURCE_JOBS) | set(SCIENCE_JOBS)
        for job_id, row in state["jobs"].items():
            if row.get("state") == "COMPLETE":
                continue
            if job_id in keep:
                row.update({
                    "state": "PENDING",
                    "latest_activity": "scheduled by pre-held-out freeze-prerequisite revision",
                    "last_error": None,
                    "completed_at_utc": None,
                    "updated_at_utc": now,
                })
            else:
                row.update({
                    "state": "SUPERSEDED",
                    "latest_activity": "deferred by checksum-bound ten-hour scope amendment",
                    "last_error": None,
                    "completed_at_utc": now,
                    "updated_at_utc": now,
                })
        state.update({
            "status": "STOPPED",
            "detail": "Matched serial-resource prerequisites scheduled before policy freeze",
            "current_job_id": None,
            "timeboxed_scope_revision": str(revision_path),
            "timeboxed_scope_revision_sha256": claimed,
            "updated_at_utc": now,
        })
        write_json_atomic(self.state_path, state)
        self.stop_path.unlink(missing_ok=True)
        pending = sum(state["jobs"][job]["state"] != "COMPLETE" for job in FREEZE_RESOURCE_JOBS)
        self.event("FREEZE_RESOURCE_PREREQUISITES_SCHEDULED", pending_jobs=pending, revision_sha256=claimed)
        return pending

    def prepare_timeboxed_freeze_override(self) -> str:
        """Bind a reduced engineering prerequisite before held-out opens."""

        state = read_json(self.state_path)
        manifest = read_json(self.manifest_path)
        by_id = {row["job_id"]: row for row in manifest["jobs"]}
        opened = [
            job_id for job_id, row in state["jobs"].items()
            if by_id[job_id].get("split") == "evaluation"
            and row.get("state") not in {"PENDING", "SUPERSEDED", "WAITING_PROMOTION"}
        ]
        if opened:
            raise RuntimeError(
                "cannot activate timeboxed freeze override after held-out opened: "
                f"{opened}"
            )
        if not self.timeboxed_freeze_launcher.is_file():
            raise RuntimeError("timeboxed freeze launcher is missing")
        original = self.launcher
        patched = self.launcher.parent / "controller.py.patched"
        partial_progress_path = (
            self.workspace
            / "dynamic_queues/h2p6_h2_known_only_serial_resource_1e27a1e89d/campaign_progress.json"
        )
        partial_progress = read_json(partial_progress_path) if partial_progress_path.is_file() else None
        revision_path = self.control / "scope_amendment.revision_3.json"
        if not revision_path.exists():
            prior_path = self.control / "scope_amendment.revision_2.json"
            prior = read_json(prior_path) if prior_path.is_file() else read_json(self.scope_path)
            revision: dict[str, Any] = {
                "schema_version": "h2-timeboxed-scope-amendment-revision.v1",
                "created_at_utc": utc_now(),
                "prior_receipt_sha256": prior["receipt_sha256"],
                "job_manifest_sha256": sha256_file(self.manifest_path),
                "evaluation_material_inspected": False,
                "retuning_permitted": False,
                "completed_evidence_modified": False,
                "change": "Move long serial-resource validation out of the freeze gate after measured RTF showed it would consume the deadline; retain exact three-mode development/tuning validation and run two-mode held-out science first.",
                "observed_partial_resource_progress": partial_progress,
                "heldout_jobs": list(HELDOUT_JOBS),
                "file_bindings": {
                    "timeboxed_freeze_bootstrap": sha256_file(self.timeboxed_freeze_launcher),
                    "selector_correction_bootstrap": sha256_file(original),
                    "patched_controller": sha256_file(patched),
                },
                "hard_deadline_utc": self.deadline.isoformat().replace("+00:00", "Z"),
            }
            revision["receipt_sha256"] = hashlib.sha256(canonical_bytes(revision)).hexdigest()
            write_json_atomic(revision_path, revision)
        revision = read_json(revision_path)
        claimed = revision.pop("receipt_sha256", None)
        if claimed != hashlib.sha256(canonical_bytes(revision)).hexdigest():
            raise RuntimeError("timeboxed freeze override receipt checksum is invalid")
        expected_bindings = {
            "timeboxed_freeze_bootstrap": sha256_file(self.timeboxed_freeze_launcher),
            "selector_correction_bootstrap": sha256_file(original),
            "patched_controller": sha256_file(patched),
        }
        if revision.get("file_bindings") != expected_bindings:
            raise RuntimeError("timeboxed freeze override executable bindings changed")

        analysis_path = self.control / "critical_analysis_plan.json"
        report_script = self.tool_root / "scripts/h2_timeboxed_report.py"
        if not report_script.is_file():
            raise RuntimeError("timeboxed report script is missing")
        if not analysis_path.exists():
            analysis: dict[str, Any] = {
                "schema_version": "h2-timeboxed-critical-analysis-plan.v1",
                "created_at_utc": utc_now(),
                "created_before_heldout_opened": True,
                "evaluation_material_inspected": False,
                "retuning_permitted": False,
                "heldout_jobs": list(HELDOUT_JOBS),
                "speaker_bootstrap": {
                    "source_jobs": list(HELDOUT_JOBS),
                    "repetitions": 2000,
                    "seed": 3800,
                    "resampling_unit": "reference speaker cluster with case fallback",
                    "original_manifest_job": ORIGINAL_BOOTSTRAP_JOB,
                    "reason_for_report_stage": "the original manifest bootstrap requires deferred held-out expansions; the timeboxed analysis uses only the two predeclared retained product modes",
                },
                "file_bindings": {
                    "timeboxed_report": sha256_file(report_script),
                    "timeboxed_completion": sha256_file(Path(__file__).resolve()),
                },
                "hard_deadline_utc": self.deadline.isoformat().replace("+00:00", "Z"),
            }
            analysis["receipt_sha256"] = hashlib.sha256(canonical_bytes(analysis)).hexdigest()
            write_json_atomic(analysis_path, analysis)
        analysis = read_json(analysis_path)
        analysis_claimed = analysis.pop("receipt_sha256", None)
        if analysis_claimed != hashlib.sha256(canonical_bytes(analysis)).hexdigest():
            raise RuntimeError("critical analysis plan checksum is invalid")
        if analysis.get("file_bindings") != {
            "timeboxed_report": sha256_file(report_script),
            "timeboxed_completion": sha256_file(Path(__file__).resolve()),
        }:
            raise RuntimeError("critical analysis executable bindings changed")

        now = utc_now()
        for job_id, row in state["jobs"].items():
            if row.get("state") == "COMPLETE":
                continue
            if job_id in SCIENCE_JOBS:
                row.update({
                    "state": "PENDING",
                    "latest_activity": "scheduled by checksum-bound timeboxed freeze override",
                    "last_error": None, "completed_at_utc": None, "updated_at_utc": now,
                })
            else:
                row.update({
                    "state": "SUPERSEDED",
                    "latest_activity": "deferred by checksum-bound ten-hour scope amendment revision 3",
                    "last_error": None, "completed_at_utc": now, "updated_at_utc": now,
                })
        state.update({
            "status": "STOPPED",
            "detail": "Timeboxed pre-held-out freeze override activated without policy retuning",
            "current_job_id": None,
            "timeboxed_scope_revision": str(revision_path),
            "timeboxed_scope_revision_sha256": claimed,
            "timeboxed_critical_analysis_plan": str(analysis_path),
            "timeboxed_critical_analysis_plan_sha256": analysis_claimed,
            "updated_at_utc": now,
        })
        write_json_atomic(self.state_path, state)
        self.stop_path.unlink(missing_ok=True)
        self.event("TIMEBOXED_FREEZE_OVERRIDE_ACTIVATED", revision_sha256=claimed)
        return str(claimed)

    def collect(self) -> None:
        report_script = self.tool_root / "scripts/h2_timeboxed_report.py"
        command = [
            str(self.python), "-B", str(report_script),
            "--tool-root", str(self.tool_root), "--workspace", str(self.workspace),
            "--results-root", str(self.results_root), "--summary-root", str(self.summary_root),
            "--deadline-utc", self.deadline.isoformat().replace("+00:00", "Z"),
        ]
        completed = subprocess.run(command, cwd=self.tool_root, text=True, capture_output=True)
        (self.workspace / "logs/timeboxed_report.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (self.workspace / "logs/timeboxed_report.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"timeboxed report failed: {completed.stderr[-2000:]}")
        self.event("PACKAGE_COMPLETE", output=completed.stdout.strip())

    def run(self) -> None:
        (self.control / "failure.json").unlink(missing_ok=True)
        self.event("TIMEBOX_STARTED", deadline_utc=self.deadline.isoformat().replace("+00:00", "Z"), compute_stop_utc=self.compute_stop.isoformat().replace("+00:00", "Z"))
        if datetime.now(timezone.utc) >= self.deadline:
            raise RuntimeError("hard deadline is already in the past")
        self.wait_for_initial_boundary()
        self.apply_scope()
        state = read_json(self.state_path)
        freeze_incomplete = state["jobs"][SCIENCE_JOBS[0]]["state"] != "COMPLETE"
        science_launcher: Path | None = None
        if freeze_incomplete:
            self.prepare_timeboxed_freeze_override()
            science_launcher = self.timeboxed_freeze_launcher
        science_pending = sum(read_json(self.state_path)["jobs"][j]["state"] != "COMPLETE" for j in SCIENCE_JOBS)
        if science_pending:
            self.launch(science_pending, "science", launcher=science_launcher)
            science_pass_ok = self.wait_pass("science")
        else:
            science_pass_ok = True
        current = read_json(self.state_path)
        science_jobs_complete = all(current["jobs"][job]["state"] == "COMPLETE" for job in SCIENCE_JOBS)
        science_pass_ok = science_pass_ok or science_jobs_complete
        heldout_complete = all(current["jobs"][job]["state"] == "COMPLETE" for job in HELDOUT_JOBS)
        if science_pass_ok and heldout_complete and datetime.now(timezone.utc) < self.compute_stop:
            engineering_pending = self.reopen_engineering()
            if engineering_pending:
                self.launch(engineering_pending, "engineering")
                self.wait_pass("engineering")
        else:
            self.event(
                "ENGINEERING_SKIPPED",
                science_pass_ok=science_pass_ok,
                heldout_complete=heldout_complete,
                compute_window_open=datetime.now(timezone.utc) < self.compute_stop,
            )
        self.stop_path.unlink(missing_ok=True)
        self.collect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--deadline-utc", required=True)
    parser.add_argument("--packaging-reserve-minutes", type=int, default=75)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        Timebox(args).run()
    except Exception as exc:
        workspace = Path(args.workspace).resolve()
        failure = {"status": "BLOCKED_TIMEBOX", "at_utc": utc_now(), "error": f"{type(exc).__name__}: {exc}"}
        write_json_atomic(workspace / "timeboxed_completion/failure.json", failure)
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
