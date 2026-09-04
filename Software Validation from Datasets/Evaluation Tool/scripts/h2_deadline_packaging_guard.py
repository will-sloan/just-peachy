"""Fail-safe packaging guard for the H2 timeboxed campaign.

This process does not run or alter scientific work.  It waits for the normal
deadline controller, gives it a post-compute grace period, and only terminates
its currently active child pass if needed to preserve final packaging time.
If the manager itself cannot create a fresh package, the guard runs the exact
reporter whose hash was frozen before held-out evaluation opened.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

import psutil


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def append_event(path: Path, kind: str, **details: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at_utc": utc_now(), "kind": kind, **details}, sort_keys=True) + "\n")


def process_command(pid: int) -> str | None:
    try:
        return " ".join(psutil.Process(pid).cmdline())
    except (psutil.Error, OSError):
        return None


def process_alive(pid: int) -> bool:
    try:
        return psutil.Process(pid).is_running()
    except psutil.Error:
        return False


def terminate_tree(pid: int, *, workspace: Path, expected: tuple[str, ...]) -> bool:
    command = process_command(pid)
    if command is None:
        return False
    if str(workspace).casefold() not in command.casefold():
        raise RuntimeError(f"refusing to terminate PID {pid}: workspace provenance differs")
    if not any(token.casefold() in command.casefold() for token in expected):
        raise RuntimeError(f"refusing to terminate PID {pid}: command provenance differs")
    completed = subprocess.run(
        ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in {0, 128} and process_alive(pid):
        raise RuntimeError(f"taskkill failed for PID {pid}: {completed.stderr[-500:]}")
    return True


def active_pass(events_path: Path) -> tuple[str, int] | None:
    if not events_path.is_file():
        return None
    active: dict[str, int] = {}
    for line in events_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        label = str(row.get("label") or "")
        if row.get("kind") == "PASS_LAUNCHED" and label:
            active[label] = int(row["pid"])
        elif row.get("kind") == "PASS_FINISHED" and label:
            active.pop(label, None)
    if not active:
        return None
    label = next(reversed(active))
    return label, active[label]


def fresh_package(zip_path: Path, pointer_path: Path, baseline_sha: str | None) -> bool:
    if not zip_path.is_file() or not pointer_path.is_file():
        return False
    current = sha256_file(zip_path)
    return current != baseline_sha and current in pointer_path.read_text(encoding="utf-8-sig")


def run_report(args: argparse.Namespace, plan: dict[str, Any], log_path: Path) -> bool:
    reporter = Path(args.tool_root).resolve() / "scripts/h2_timeboxed_report.py"
    expected = plan.get("file_bindings", {}).get("timeboxed_report")
    if expected != sha256_file(reporter):
        raise RuntimeError("emergency reporter differs from the pre-held-out analysis plan")
    command = [
        sys.executable,
        "-B",
        str(reporter),
        "--tool-root",
        str(Path(args.tool_root).resolve()),
        "--workspace",
        str(Path(args.workspace).resolve()),
        "--results-root",
        str(Path(args.results_root).resolve()),
        "--summary-root",
        str(Path(args.summary_root).resolve()),
        "--deadline-utc",
        args.deadline_utc,
    ]
    append_event(log_path, "EMERGENCY_REPORT_STARTED", command=command)
    completed = subprocess.run(
        command,
        cwd=Path(args.tool_root).resolve(),
        capture_output=True,
        text=True,
        check=False,
    )
    (Path(args.workspace) / "logs/deadline_guard_report.stdout.log").write_text(
        completed.stdout, encoding="utf-8"
    )
    (Path(args.workspace) / "logs/deadline_guard_report.stderr.log").write_text(
        completed.stderr, encoding="utf-8"
    )
    append_event(log_path, "EMERGENCY_REPORT_FINISHED", exit_code=completed.returncode)
    return completed.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--manager-pid", required=True, type=int)
    parser.add_argument("--compute-stop-utc", required=True)
    parser.add_argument("--deadline-utc", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    summary_root = Path(args.summary_root).resolve()
    summary_root.mkdir(parents=True, exist_ok=True)
    log_path = workspace / "logs/h2_deadline_packaging_guard.jsonl"
    plan_path = workspace / "timeboxed_completion/critical_analysis_plan.json"
    plan = read_json(plan_path)
    unsigned = dict(plan)
    claimed = unsigned.pop("receipt_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("critical analysis plan checksum differs")
    state = read_json(workspace / "program_state.json")
    manifest = read_json(workspace / "job_manifest.json")
    manifest_by_id = {row["job_id"]: row for row in manifest["jobs"]}
    opened = [
        job_id
        for job_id, row in state["jobs"].items()
        if manifest_by_id[job_id].get("split") == "evaluation"
        and row.get("state") not in {"PENDING", "SUPERSEDED", "WAITING_PROMOTION"}
    ]
    if opened:
        raise RuntimeError(f"deadline guard must be registered before held-out opens: {opened}")

    source = Path(__file__).resolve()
    receipt: dict[str, Any] = {
        "schema_version": "h2-deadline-packaging-guard.v1",
        "created_at_utc": utc_now(),
        "created_before_heldout_opened": True,
        "evaluation_material_inspected": False,
        "retuning_permitted": False,
        "manager_pid": args.manager_pid,
        "compute_stop_utc": args.compute_stop_utc,
        "child_stop_grace_utc": (
            parse_utc(args.compute_stop_utc) + timedelta(minutes=10)
        ).isoformat().replace("+00:00", "Z"),
        "emergency_report_utc": (
            parse_utc(args.deadline_utc) - timedelta(minutes=30)
        ).isoformat().replace("+00:00", "Z"),
        "hard_deadline_utc": args.deadline_utc,
        "guard_source_sha256": sha256_file(source),
        "critical_analysis_plan_sha256": claimed,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    receipt_path = workspace / "timeboxed_completion/deadline_packaging_guard_receipt.json"
    write_json_atomic(receipt_path, receipt)
    shutil.copy2(source, summary_root / source.name)
    shutil.copy2(receipt_path, summary_root / "DEADLINE_PACKAGING_GUARD_RECEIPT.json")
    append_event(log_path, "GUARD_STARTED", receipt_sha256=receipt["receipt_sha256"])

    deadline = parse_utc(args.deadline_utc)
    child_grace = parse_utc(receipt["child_stop_grace_utc"])
    emergency = parse_utc(receipt["emergency_report_utc"])
    zip_path = summary_root / "H2_TIMEBOXED_FINAL_RESULTS.zip"
    pointer_path = summary_root / "UPLOAD_THIS_FILE_TO_CHATGPT.txt"
    baseline_sha = sha256_file(zip_path) if zip_path.is_file() else None
    child_terminated = False
    while datetime.now(timezone.utc) < deadline:
        if fresh_package(zip_path, pointer_path, baseline_sha):
            append_event(log_path, "FRESH_PACKAGE_CONFIRMED", zip_sha256=sha256_file(zip_path))
            return 0
        now = datetime.now(timezone.utc)
        if now >= child_grace and not child_terminated:
            active = active_pass(workspace / "logs/timeboxed_completion.jsonl")
            if active is not None and process_alive(active[1]):
                label, pid = active
                terminate_tree(
                    pid,
                    workspace=workspace,
                    expected=("h2_timeboxed_freeze_bootstrap.py", "h2_prefreeze_selector_correction_bootstrap.py"),
                )
                append_event(log_path, "ACTIVE_PASS_TERMINATED_FOR_PACKAGING", label=label, pid=pid)
            child_terminated = True
        if now >= emergency and not fresh_package(zip_path, pointer_path, baseline_sha):
            if process_alive(args.manager_pid):
                terminate_tree(
                    args.manager_pid,
                    workspace=workspace,
                    expected=("h2_timeboxed_completion.py",),
                )
                append_event(log_path, "MANAGER_TERMINATED_FOR_EMERGENCY_REPORT", pid=args.manager_pid)
            ok = run_report(args, plan, log_path)
            if ok and fresh_package(zip_path, pointer_path, baseline_sha):
                return 0
            return 1
        time.sleep(15)
    append_event(log_path, "HARD_DEADLINE_REACHED", fresh_package=False)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
