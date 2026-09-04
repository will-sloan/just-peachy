"""Resume known-only sequentially after the deadline-panel cache collision."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

EVALUATION_ROOT = Path(__file__).resolve().parents[1]
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from app.h2_product_program import controller  # noqa: E402
from app.h2_product_program.contracts import ProgramPaths  # noqa: E402
from app.h2_product_program.io import read_json, write_json_atomic  # noqa: E402
from app.full_pipeline_evaluation.store import EvaluationStateStore  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def memory_state(workspace: Path) -> str:
    """Return the authoritative deadline-memory queue state.

    The bounded runner invokes its single queue job directly. Its derived
    campaign-progress JSON is updated during case heartbeats but is not
    necessarily republished after the terminal database commit. The SQLite
    row is the queue's durable ownership and completion record.
    """

    store = EvaluationStateStore(
        workspace / "deadline_bounded_memory_queue/campaign.sqlite3"
    )
    jobs = store.list_jobs()
    if len(jobs) != 1:
        raise RuntimeError(
            "deadline memory queue must contain exactly one job; "
            f"found {len(jobs)}"
        )
    return str(jobs[0].state or "missing").casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--compute-stop-utc", required=True)
    args = parser.parse_args()
    paths = ProgramPaths(
        evaluation_root=Path(args.tool_root).resolve(),
        workspace=Path(args.workspace).resolve(),
        results_root=Path(args.results_root).resolve(),
        summary_root=Path(args.summary_root).resolve(),
        config_path=Path(args.config).resolve(),
    )
    compute_stop = parse_utc(args.compute_stop_utc)
    while datetime.now(timezone.utc) < compute_stop:
        state = memory_state(paths.workspace)
        if state == "complete":
            break
        if state in {"failed", "partial", "stopped"}:
            raise RuntimeError(f"memory panel ended before completion: {state}")
        time.sleep(5.0)
    else:
        raise RuntimeError("compute reserve reached before memory panel completed")

    main_state = read_json(paths.state_path)
    failed = main_state.get("jobs", {}).get(
        "h2p7_h2_known_only_heldout_b5b5707476", {}
    )
    error = str(failed.get("last_error") or "")
    if "PermissionError" not in error and main_state.get("status") != "BLOCKED":
        raise RuntimeError("expected recoverable known-only failure is not recorded")
    # The timeboxed freeze bootstrap is intentionally pre-held-out only.  Once
    # the policy is frozen, Resume must use the already-activated selector
    # correction launcher, whose continuation preflight verifies the frozen
    # policy binding without reopening or changing the freeze.
    launcher = (
        paths.workspace
        / "diagnostics/pre_freeze_selector_fix_staging/"
        "h2_prefreeze_selector_correction_bootstrap.py"
    )
    receipt = {
        "schema_version": "h2-deadline-sequential-retry.v1",
        "created_at_utc": utc_now(),
        "reason": "Windows shared-cache concurrent-write PermissionError",
        "completed_case_shards_preserved": True,
        "failed_case_shard_reused": False,
        "scientific_settings_changed": False,
        "retry_concurrency": 1,
        "concurrent_timing_invalidated": True,
        "memory_state_source": "deadline_bounded_memory_queue/campaign.sqlite3",
        "stale_progress_json_observed": True,
        "stale_progress_json_state": "running",
        "durable_queue_state": "complete",
        "handoff_correction_result_affecting": False,
        "launcher_role": "post_freeze_checksum_bound_resume",
        "launcher": str(launcher),
        "launcher_sha256": sha256_file(launcher),
        "source_sha256": sha256_file(Path(__file__).resolve()),
        "compute_stop_utc": args.compute_stop_utc,
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt_path = (
        paths.workspace
        / "timeboxed_completion/deadline_sequential_retry_receipt.json"
    )
    write_json_atomic(receipt_path, receipt)
    command = [
        sys.executable,
        "-B",
        str(launcher),
        "Resume",
        "--workspace",
        str(paths.workspace),
        "--results-root",
        str(paths.results_root),
        "--summary-root",
        str(paths.summary_root),
        "--config",
        str(paths.config_path),
        "--retry-failed",
        "--maximum-jobs",
        "1",
    ]
    log_root = paths.workspace / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    with (log_root / "deadline_sequential_retry.stdout.log").open(
        "a", encoding="utf-8"
    ) as stdout, (log_root / "deadline_sequential_retry.stderr.log").open(
        "a", encoding="utf-8"
    ) as stderr:
        process = subprocess.Popen(
            command,
            cwd=paths.evaluation_root,
            stdout=stdout,
            stderr=stderr,
            text=True,
        )
        stop_requested = False
        while process.poll() is None:
            if datetime.now(timezone.utc) >= compute_stop and not stop_requested:
                controller.stop(
                    paths, reason="deadline_sequential_retry_compute_reserve"
                )
                stop_requested = True
            time.sleep(5.0)
    result = {
        **receipt,
        "status": "FINISHED" if process.returncode == 0 else "FAILED",
        "exit_code": process.returncode,
        "completed_at_utc": utc_now(),
        "command": command,
    }
    write_json_atomic(
        paths.workspace
        / "timeboxed_completion/deadline_sequential_retry_result.json",
        result,
    )
    return int(process.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
