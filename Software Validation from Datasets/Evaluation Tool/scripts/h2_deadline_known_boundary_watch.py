"""Request an exact graceful boundary stop for the deadline held-out panel."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

EVALUATION_ROOT = Path(__file__).resolve().parents[1]
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from app.h2_product_program import controller  # noqa: E402
from app.h2_product_program.contracts import ProgramPaths  # noqa: E402
from app.h2_product_program.io import read_json, write_json_atomic  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--execution-job-id", required=True)
    parser.add_argument("--target-completed-cases", required=True, type=int)
    parser.add_argument("--deadline-utc", required=True)
    args = parser.parse_args()
    paths = ProgramPaths(
        evaluation_root=Path(args.tool_root).resolve(),
        workspace=Path(args.workspace).resolve(),
        results_root=Path(args.results_root).resolve(),
        summary_root=Path(args.summary_root).resolve(),
        config_path=Path(args.config).resolve(),
    )
    deadline = datetime.fromisoformat(args.deadline_utc.replace("Z", "+00:00"))
    # The worker starts the next case immediately after publishing progress.
    # Request at N-1 so the already-started Nth atomic case finishes, producing
    # an exact N-case result without killing inference.
    trigger = max(0, args.target_completed_cases - 1)
    receipt = {
        "schema_version": "h2-deadline-known-boundary-watch.v1",
        "created_at_utc": utc_now(),
        "execution_job_id": args.execution_job_id,
        "target_completed_cases": args.target_completed_cases,
        "trigger_completed_cases": trigger,
        "semantics": "request_graceful_stop_while_target_case_is_active",
        "metric_payloads_read": False,
        "force_kill_permitted": False,
        "source_sha256": sha256_file(Path(__file__).resolve()),
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt_path = (
        paths.workspace
        / "timeboxed_completion/deadline_known_boundary_watch_receipt.json"
    )
    write_json_atomic(receipt_path, receipt)
    progress_path = paths.workspace / "heldout_frozen_queue/campaign_progress.json"
    while datetime.now(timezone.utc) < deadline:
        progress = read_json(progress_path)
        row = next(
            (
                value
                for value in progress.get("jobs", [])
                if value.get("job_id") == args.execution_job_id
            ),
            None,
        )
        if row is None:
            raise RuntimeError("execution job is absent from held-out progress")
        completed = int(row.get("completed_cases") or 0)
        state = str(row.get("state") or "").casefold()
        if completed >= trigger and state == "running":
            response = controller.stop(
                paths,
                reason=(
                    "user_authorized_deadline_exact_boundary_target_"
                    f"{args.target_completed_cases}"
                ),
            )
            write_json_atomic(
                paths.workspace
                / "timeboxed_completion/deadline_known_boundary_watch_result.json",
                {
                    **receipt,
                    "status": "STOP_REQUESTED",
                    "observed_completed_cases": completed,
                    "requested_at_utc": utc_now(),
                    "controller_response": response,
                },
            )
            return 0
        if state in {"complete", "failed", "stopped", "partial"}:
            return 0
        time.sleep(1.0)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
