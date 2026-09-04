"""Run the checksum-bound deadline panel without altering frozen H2 policies.

The runner selects a metric-blind prefix of the already-frozen held-out case
order, starts the second product mode in a separate durable queue, and requests
the original controller to stop at the same complete-case boundary.  It never
reads held-out metric payloads when planning the panel.
"""

# ruff: noqa: E402 -- executable scripts add the project root before app imports.

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
from typing import Any, Mapping

import psutil

EVALUATION_ROOT = Path(__file__).resolve().parents[1]
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from app.full_pipeline_evaluation.store import EvaluationStateStore
from app.h2_product_program import controller as program_controller
from app.h2_product_program.contracts import H2Job, ProgramPaths
from app.h2_product_program.execution import (
    prepare_runtime_queue,
    run_runtime_job,
)
from app.h2_product_program.io import (
    canonical_sha256,
    read_json,
    read_jsonl,
    sha256_file,
    write_json_atomic,
)
from app.h2_product_program.planning import PREPARED_PROTOCOL_ROOT


KNOWN_LOGICAL = "h2p7_h2_known_only_heldout_b5b5707476"
MEMORY_LOGICAL = "h2p7_h2_session_memory_enhanced_heldout_850ae96d34"
DEFAULT_CASE_COUNT = 24


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    values: list[str] = []
    for row in rows:
        value = row.get(field)
        values.append(str(value if value is not None else "MISSING"))
    return dict(sorted(Counter(values).items()))


def load_overlay(workspace: Path) -> tuple[dict[str, Any], dict[str, H2Job]]:
    path = workspace / "heldout_execution_manifest.json"
    manifest = read_json(path)
    unsigned = dict(manifest)
    expected = unsigned.pop("heldout_execution_sha256", None)
    if expected != canonical_sha256(unsigned):
        raise RuntimeError("held-out execution manifest checksum differs")
    jobs = {
        row.job_id: row
        for raw in manifest.get("jobs", [])
        if isinstance(raw, Mapping)
        for row in (H2Job.from_jsonable(raw),)
    }
    return manifest, jobs


def selected_inputs(
    workspace: Path, case_count: int
) -> tuple[dict[str, Any], H2Job, H2Job, list[dict[str, Any]]]:
    overlay, jobs = load_overlay(workspace)
    mapping = overlay.get("logical_to_execution")
    if not isinstance(mapping, Mapping):
        raise RuntimeError("held-out logical mapping is missing")
    known = jobs[str(mapping[KNOWN_LOGICAL])]
    memory = jobs[str(mapping[MEMORY_LOGICAL])]
    if known.case_ids != memory.case_ids:
        raise RuntimeError("held-out product modes do not have matched cases")
    if case_count < 1 or case_count > len(known.case_ids):
        raise ValueError("case count is outside the frozen held-out case set")
    selected_ids = known.case_ids[:case_count]
    rows = read_jsonl(PREPARED_PROTOCOL_ROOT / "evaluation/case_manifest.jsonl")
    index = {str(row["protocol_case_id"]): dict(row) for row in rows}
    selected = [index[case_id] for case_id in selected_ids]
    return overlay, known, memory, selected


def plan(
    *,
    tool_root: Path,
    workspace: Path,
    results_root: Path,
    summary_root: Path,
    config: Path,
    case_count: int,
    compute_stop_utc: str,
    hard_deadline_utc: str,
) -> dict[str, Any]:
    overlay, known, memory, rows = selected_inputs(workspace, case_count)
    selected_ids = [str(row["protocol_case_id"]) for row in rows]
    unique_speakers = sorted(
        {
            str(speaker)
            for row in rows
            for speaker in row.get("global_speaker_ids", [])
        }
    )
    core: dict[str, Any] = {
        "schema_version": "h2-deadline-bounded-heldout-plan.v1",
        "created_at_utc": utc_now(),
        "amendment_timing": "after_heldout_opened",
        "scientific_label": "deadline_bounded_matched_heldout_panel_not_full_heldout",
        "reason": (
            "Observed inference throughput made the frozen 180-case x two-mode "
            "campaign incompatible with the user-authorized hard deadline."
        ),
        "selection_rule": (
            "Take the first N case IDs in the immutable frozen manifest order; "
            "do not read metric files or scores."
        ),
        "selection_uses_metrics": False,
        "heldout_metrics_used_for_retuning": False,
        "retuning_permitted": False,
        "frozen_policy_unchanged": True,
        "matched_product_modes": [known.mode, memory.mode],
        "source_execution_job_ids": [known.job_id, memory.job_id],
        "source_execution_job_identity_sha256": [
            known.identity_sha256,
            memory.identity_sha256,
        ],
        "case_count_per_mode": case_count,
        "selected_case_ids": selected_ids,
        "selected_case_ids_sha256": canonical_sha256(selected_ids),
        "selected_audio_sec_per_mode": sum(float(row["duration_sec"]) for row in rows),
        "unique_reference_speaker_count": len(unique_speakers),
        "unique_reference_speaker_ids_sha256": canonical_sha256(unique_speakers),
        "coverage": {
            field: distribution(rows, field)
            for field in (
                "source_key",
                "scenario_id",
                "overlap",
                "known_speaker_count",
                "unknown_speaker_count",
                "gallery_size",
            )
        },
        "compute_stop_utc": compute_stop_utc,
        "hard_deadline_utc": hard_deadline_utc,
        "accuracy_concurrency": 2,
        "resource_timing_from_concurrent_jobs_is_nonfinal": True,
        "original_full_campaign_preserved": True,
        "tool_root": str(tool_root),
        "workspace": str(workspace),
        "results_root": str(results_root),
        "summary_root": str(summary_root),
        "config": str(config),
        "source_bindings": {
            "frozen_policy_sha256": sha256_file(workspace / "frozen_policy.json"),
            "heldout_execution_manifest_sha256": sha256_file(
                workspace / "heldout_execution_manifest.json"
            ),
            "protocol_manifest_sha256": sha256_file(
                workspace / "protocol_manifest.json"
            ),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
        },
        "heldout_execution_sha256": overlay["heldout_execution_sha256"],
    }
    document = {**core, "receipt_sha256": canonical_sha256(core)}
    target = workspace / "timeboxed_completion/deadline_bounded_heldout_plan.json"
    if target.is_file():
        existing = read_json(target)
        unsigned = dict(existing)
        claimed = unsigned.pop("receipt_sha256", None)
        if claimed != canonical_sha256(unsigned):
            raise RuntimeError("the existing deadline-panel plan checksum differs")
        expected = {
            "case_count_per_mode": case_count,
            "selected_case_ids_sha256": canonical_sha256(selected_ids),
            "compute_stop_utc": compute_stop_utc,
            "hard_deadline_utc": hard_deadline_utc,
            "frozen_policy_sha256": core["source_bindings"][
                "frozen_policy_sha256"
            ],
            "heldout_execution_manifest_sha256": core["source_bindings"][
                "heldout_execution_manifest_sha256"
            ],
        }
        observed = {
            "case_count_per_mode": existing.get("case_count_per_mode"),
            "selected_case_ids_sha256": existing.get("selected_case_ids_sha256"),
            "compute_stop_utc": existing.get("compute_stop_utc"),
            "hard_deadline_utc": existing.get("hard_deadline_utc"),
            "frozen_policy_sha256": existing.get("source_bindings", {}).get(
                "frozen_policy_sha256"
            ),
            "heldout_execution_manifest_sha256": existing.get(
                "source_bindings", {}
            ).get("heldout_execution_manifest_sha256"),
        }
        if observed != expected:
            raise RuntimeError("an existing deadline-panel plan differs")
        return existing
    write_json_atomic(target, document)
    selected_path = workspace / "timeboxed_completion/deadline_panel_cases.jsonl"
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    selected_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return document


def main_paths(args: argparse.Namespace) -> ProgramPaths:
    return ProgramPaths(
        evaluation_root=Path(args.tool_root).resolve(),
        workspace=Path(args.workspace).resolve(),
        results_root=Path(args.results_root).resolve(),
        summary_root=Path(args.summary_root).resolve(),
        config_path=Path(args.config).resolve(),
    )


def memory_panel_job(source: H2Job, rows: list[dict[str, Any]]) -> H2Job:
    case_ids = tuple(str(row["protocol_case_id"]) for row in rows)
    identity = canonical_sha256(
        {
            "purpose": "deadline_bounded_memory_heldout",
            "source_identity": source.identity_sha256,
            "case_ids": list(case_ids),
        }
    )
    return replace(
        source,
        job_id=f"h2deadline_memory_{identity[:20]}",
        configuration_id=(
            f"{source.configuration_id}_DEADLINE_PANEL_{len(case_ids):03d}_{identity[:8]}"
        ),
        case_ids=case_ids,
        audio_duration_sec=sum(float(row["duration_sec"]) for row in rows),
        dependencies=(),
        serial=False,
        estimated_wall_hours=5.0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("Plan", "Run", "Status"))
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--case-count", type=int, default=DEFAULT_CASE_COUNT)
    parser.add_argument("--compute-stop-utc", required=True)
    parser.add_argument("--hard-deadline-utc", required=True)
    args = parser.parse_args()
    paths = main_paths(args)
    bounded_workspace = paths.workspace / "deadline_bounded_memory_queue"
    bounded_results = paths.results_root / "deadline_bounded_heldout"
    state_path = paths.workspace / "timeboxed_completion/deadline_bounded_state.json"

    if args.action == "Status":
        value = read_json(state_path) if state_path.is_file() else {"status": "NOT_STARTED"}
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0

    plan_doc = plan(
        tool_root=paths.evaluation_root,
        workspace=paths.workspace,
        results_root=paths.results_root,
        summary_root=paths.summary_root,
        config=paths.config_path,
        case_count=args.case_count,
        compute_stop_utc=args.compute_stop_utc,
        hard_deadline_utc=args.hard_deadline_utc,
    )
    if args.action == "Plan":
        print(json.dumps(plan_doc, indent=2, sort_keys=True))
        return 0

    if parse_utc(args.compute_stop_utc) <= datetime.now(timezone.utc):
        raise RuntimeError("deadline-panel compute stop is already in the past")
    _, known_source, memory_source, selected_rows = selected_inputs(
        paths.workspace, args.case_count
    )
    memory_job = memory_panel_job(memory_source, selected_rows)
    protocol = read_json(paths.workspace / "protocol_manifest.json")
    bounded_paths = ProgramPaths(
        evaluation_root=paths.evaluation_root,
        workspace=bounded_workspace,
        results_root=bounded_results,
        summary_root=paths.summary_root,
        config_path=paths.config_path,
    )
    bounded_workspace.mkdir(parents=True, exist_ok=True)
    bounded_paths.stop_path.unlink(missing_ok=True)
    prepare_runtime_queue(
        bounded_paths,
        (memory_job,),
        protocol=protocol,
        job_manifest_sha256=str(plan_doc["receipt_sha256"]),
        seed=3800,
    )
    write_json_atomic(
        state_path,
        {
            "schema_version": "h2-deadline-bounded-state.v1",
            "status": "RUNNING",
            "started_at_utc": utc_now(),
            "plan_sha256": plan_doc["receipt_sha256"],
            "known_source_job_id": known_source.job_id,
            "memory_panel_job": memory_job.to_jsonable(),
            "memory_queue": str(bounded_workspace),
            "memory_results_root": str(bounded_results),
        },
    )

    stop_event = threading.Event()
    monitor_done = threading.Event()
    original_stop_requested = threading.Event()
    original_execution_id = known_source.job_id
    original_store_path = paths.workspace / "heldout_frozen_queue/campaign.sqlite3"

    def monitor_deadlines_and_known() -> None:
        requested = False
        while not monitor_done.wait(5.0):
            now = datetime.now(timezone.utc)
            try:
                store = EvaluationStateStore(original_store_path)
                row = next(
                    item
                    for item in store.list_jobs()
                    if item.spec.job_id == original_execution_id
                )
                if row.completed_cases >= args.case_count and not requested:
                    program_controller.stop(
                        paths,
                        reason=(
                            "user_authorized_deadline_panel_reached_"
                            f"{args.case_count}_complete_cases"
                        ),
                    )
                    requested = True
                    original_stop_requested.set()
            except Exception:
                pass
            if now >= parse_utc(args.compute_stop_utc):
                if not requested:
                    program_controller.stop(
                        paths, reason="user_authorized_deadline_compute_reserve"
                    )
                    requested = True
                    original_stop_requested.set()
                write_json_atomic(
                    bounded_paths.stop_path,
                    {
                        "schema_version": "h2-deadline-panel-stop.v1",
                        "requested_at_utc": utc_now(),
                        "reason": "packaging_reserve_reached",
                    },
                )
                stop_event.set()
                return

    monitor = threading.Thread(
        target=monitor_deadlines_and_known,
        name="deadline-panel-boundary-monitor",
        daemon=True,
    )
    monitor.start()
    outcome = run_runtime_job(
        bounded_paths,
        memory_job,
        protocol=protocol,
        stop_event=stop_event,
        progress_lock=threading.Lock(),
        additional_execution_contract={
            "deadline_bounded_panel": True,
            "deadline_panel_plan_sha256": plan_doc["receipt_sha256"],
            "deadline_panel_case_count": args.case_count,
            "selection_uses_metrics": False,
            "resource_timing_final": False,
        },
        storage_reserve_callback=lambda: (
            None
            if psutil.disk_usage("C:\\").free >= 35 * 1024**3
            else (_ for _ in ()).throw(RuntimeError("C: reserve below 35 GiB"))
        ),
        external_stop_path=bounded_paths.stop_path,
    )
    # If the bounded memory mode finishes first, keep the lightweight monitor
    # alive until the original known-only pass reaches the exact same N-case
    # boundary (or until the compute reserve is reached).
    original_stop_requested.wait(
        timeout=max(
            0.0,
            (parse_utc(args.compute_stop_utc) - datetime.now(timezone.utc)).total_seconds()
            + 10.0,
        )
    )
    monitor_done.set()
    monitor.join(timeout=10.0)
    result = {
        "schema_version": "h2-deadline-bounded-result.v1",
        "status": "COMPLETE" if outcome.get("state") == "complete" else "PARTIAL",
        "completed_at_utc": utc_now(),
        "plan_sha256": plan_doc["receipt_sha256"],
        "case_count_per_mode": args.case_count,
        "memory_panel_job": memory_job.to_jsonable(),
        "memory_outcome": dict(outcome),
        "memory_result_root": str(
            bounded_results / f"jobs/{memory_job.job_id}/result"
        ),
        "original_known_execution_job_id": original_execution_id,
        "original_known_attempt_root": str(
            paths.workspace
            / f"heldout_frozen_queue/attempts/{original_execution_id}"
        ),
        "hard_deadline_utc": args.hard_deadline_utc,
        "compute_stop_utc": args.compute_stop_utc,
    }
    result["result_sha256"] = canonical_sha256(result)
    write_json_atomic(
        paths.workspace / "timeboxed_completion/deadline_bounded_results.json",
        result,
    )
    state = read_json(state_path)
    state.update(
        {
            "status": result["status"],
            "completed_at_utc": result["completed_at_utc"],
            "memory_outcome": dict(outcome),
            "result_receipt": str(
                paths.workspace
                / "timeboxed_completion/deadline_bounded_results.json"
            ),
        }
    )
    write_json_atomic(state_path, state)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if outcome.get("state") == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
