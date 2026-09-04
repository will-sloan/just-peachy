"""Directly resume the frozen known-only queue job to the deadline boundary.

This is an orchestration-only fallback for a frozen held-out job whose normal
program-level Resume spends too much deadline time revalidating the complete
program. It uses the existing runtime job implementation and queue, preserves
sealed shards, and stops only after the predeclared matched case count.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
from typing import Any, Mapping

EVALUATION_ROOT = Path(__file__).resolve().parents[1]
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from app.full_pipeline_evaluation.store import EvaluationStateStore  # noqa: E402
from app.h2_product_program.contracts import H2Job, ProgramPaths  # noqa: E402
from app.h2_product_program.execution import run_runtime_job  # noqa: E402
from app.h2_product_program.io import (  # noqa: E402
    canonical_sha256,
    read_json,
    write_json_atomic,
)


KNOWN_EXECUTION_ID = "h2eval_803ba2ccf2530618fbd5fced"


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


def verified_inputs(
    paths: ProgramPaths, *, target_cases: int
) -> tuple[dict[str, Any], dict[str, Any], H2Job, ProgramPaths]:
    plan_path = paths.workspace / "timeboxed_completion/deadline_bounded_heldout_plan.json"
    plan = read_json(plan_path)
    unsigned = dict(plan)
    claimed = unsigned.pop("receipt_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("deadline-panel plan checksum differs")
    selected = [str(value) for value in plan.get("selected_case_ids") or []]
    if len(selected) != target_cases:
        raise RuntimeError("deadline-panel target differs from the frozen plan")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, Mapping):
        raise RuntimeError("deadline-panel source bindings are missing")
    frozen_path = paths.workspace / "frozen_policy.json"
    heldout_path = paths.workspace / "heldout_execution_manifest.json"
    if sha256_file(frozen_path) != bindings.get("frozen_policy_sha256"):
        raise RuntimeError("frozen policy differs from the deadline plan")
    if sha256_file(heldout_path) != bindings.get("heldout_execution_manifest_sha256"):
        raise RuntimeError("held-out execution manifest differs from the deadline plan")
    heldout = read_json(heldout_path)
    raw_jobs = heldout.get("jobs")
    if not isinstance(raw_jobs, list):
        raise RuntimeError("held-out execution jobs are missing")
    raw_job = next(
        (
            row
            for row in raw_jobs
            if isinstance(row, Mapping) and row.get("job_id") == KNOWN_EXECUTION_ID
        ),
        None,
    )
    if raw_job is None:
        raise RuntimeError("frozen known-only execution job is missing")
    job = H2Job.from_jsonable(raw_job)
    if list(job.case_ids[:target_cases]) != selected:
        raise RuntimeError("known-only ordered case prefix differs from the frozen panel")
    expected_identities = {
        str(value) for value in plan.get("source_execution_job_identity_sha256") or []
    }
    if job.identity_sha256 not in expected_identities:
        raise RuntimeError("known-only execution identity differs from the frozen plan")
    heldout_paths = ProgramPaths(
        evaluation_root=paths.evaluation_root,
        workspace=(paths.workspace / "heldout_frozen_queue").resolve(),
        results_root=paths.results_root,
        summary_root=paths.summary_root,
        config_path=paths.config_path,
    )
    store = EvaluationStateStore(heldout_paths.workspace / "campaign.sqlite3")
    row = next((value for value in store.list_jobs() if value.spec.job_id == job.job_id), None)
    heldout_protocol_id = str(heldout.get("protocol_id") or "")
    if row is None or any(
        (
            tuple(row.spec.case_ids) != tuple(job.case_ids),
            row.spec.pipeline_id != job.pipeline_id,
            not heldout_protocol_id or row.spec.protocol_id != heldout_protocol_id,
            row.spec.split != job.split,
            abs(row.spec.audio_duration_sec - job.audio_duration_sec) > 1e-9,
            row.spec.measurement_mode != "accuracy",
            row.spec.reuse_identity.get("case_manifest_id")
            != f"{job.job_id}:{job.configuration_id}",
        )
    ):
        raise RuntimeError("known-only durable queue specification differs")
    if row.state == "running":
        raise RuntimeError("known-only queue already has an active owner")
    protocol = read_json(paths.workspace / "protocol_manifest.json")
    return plan, protocol, job, heldout_paths


def install_windows_atomic_retry(paths: ProgramPaths) -> None:
    scripts_root = paths.evaluation_root / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    import h2_windows_atomic_retry_bootstrap as atomic

    if os.name == "nt":
        os.replace = atomic._retrying_replace
    os.environ["H2_ATOMIC_RETRY_POLICY_ROOT"] = str(
        paths.workspace / "storage_maintenance"
    )
    os.environ["H2_ATOMIC_RETRY_EVENT_LOG"] = str(
        paths.workspace / "logs/windows_atomic_publication_events.jsonl"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--target-cases", type=int, default=24)
    parser.add_argument("--compute-stop-utc", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    paths = ProgramPaths(
        evaluation_root=Path(args.tool_root).resolve(),
        workspace=Path(args.workspace).resolve(),
        results_root=Path(args.results_root).resolve(),
        summary_root=Path(args.summary_root).resolve(),
        config_path=Path(args.config).resolve(),
    )
    plan, protocol, job, heldout_paths = verified_inputs(
        paths, target_cases=args.target_cases
    )
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "status": "ELIGIBLE",
                    "scientific_settings_changed": False,
                    "job_id": job.job_id,
                    "job_identity_sha256": job.identity_sha256,
                    "target_cases": args.target_cases,
                    "plan_sha256": plan["receipt_sha256"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if datetime.now(timezone.utc) >= parse_utc(args.compute_stop_utc):
        raise RuntimeError("compute cutoff reached before direct known-only retry")
    install_windows_atomic_retry(paths)
    stop_event = threading.Event()
    monitor_done = threading.Event()
    store = EvaluationStateStore(heldout_paths.workspace / "campaign.sqlite3")

    def monitor_boundary() -> None:
        while not monitor_done.wait(2.0):
            row = next(value for value in store.list_jobs() if value.spec.job_id == job.job_id)
            if row.completed_cases >= args.target_cases:
                stop_event.set()
                return
            if datetime.now(timezone.utc) >= parse_utc(args.compute_stop_utc):
                stop_event.set()
                return

    monitor = threading.Thread(target=monitor_boundary, daemon=True)
    monitor.start()
    try:
        outcome = run_runtime_job(
            heldout_paths,
            job,
            protocol=protocol,
            stop_event=stop_event,
            progress_lock=threading.Lock(),
            additional_execution_contract={
                "deadline_direct_known_retry": True,
                "deadline_panel_plan_sha256": plan["receipt_sha256"],
                "deadline_target_cases": args.target_cases,
                "selection_uses_metrics": False,
                "resource_timing_final": False,
            },
            storage_reserve_callback=lambda: (
                None
                if shutil.disk_usage("C:/").free >= 35 * 1024**3
                else (_ for _ in ()).throw(RuntimeError("C: reserve below 35 GiB"))
            ),
        )
    finally:
        monitor_done.set()
        monitor.join(timeout=5.0)
    final_row = next(value for value in store.list_jobs() if value.spec.job_id == job.job_id)
    receipt = {
        "schema_version": "h2-deadline-direct-known-retry.v1",
        "created_at_utc": utc_now(),
        "status": "TARGET_REACHED" if final_row.completed_cases >= args.target_cases else "INCOMPLETE",
        "job_id": job.job_id,
        "job_identity_sha256": job.identity_sha256,
        "target_cases": args.target_cases,
        "completed_cases": final_row.completed_cases,
        "completed_audio_sec": final_row.completed_audio_sec,
        "queue_state": final_row.state,
        "outcome": dict(outcome),
        "plan_sha256": plan["receipt_sha256"],
        "source_sha256": sha256_file(Path(__file__).resolve()),
        "scientific_settings_changed": False,
        "metrics_inspected_for_recovery": False,
        "failed_case_shard_reused": False,
        "sealed_case_shards_preserved": True,
        "retry_concurrency": 1,
        "compute_stop_utc": args.compute_stop_utc,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    write_json_atomic(
        paths.workspace / "timeboxed_completion/deadline_direct_known_retry_result.json",
        receipt,
    )
    return 0 if final_row.completed_cases >= args.target_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
