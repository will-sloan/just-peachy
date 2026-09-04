"""Replay the matched H2 Phase-2 R1/R2 resource jobs on a quiet host.

The original accuracy/result trees remain immutable.  This tool creates an
isolated C:-drive replay workspace with the exact original job IDs, cases,
tuning, protocol, implementation identity, and resource measurement mode.  It
runs R1 then R2 serially, captures Windows host-I/O evidence, and publishes a
comparison only when that evidence classifies the interval as clear.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.full_pipeline_evaluation.host_lock import HostRunLock  # noqa: E402
from app.full_pipeline_evaluation.store import EvaluationStateStore  # noqa: E402
from app.h2_product_program.contracts import H2Job, ProgramPaths  # noqa: E402
from app.h2_product_program.execution import (  # noqa: E402
    RUNTIME_QUEUE_DATABASE,
    prepare_runtime_queue,
    run_runtime_job,
    runtime_implementation_identity,
)
from app.h2_product_program.io import (  # noqa: E402
    canonical_sha256,
    sha256_file,
    write_json_atomic,
    write_once_or_verify,
)
from app.h2_product_program.planning import load_and_validate_spec  # noqa: E402


SCHEMA = "h2-phase2-quiet-resource-replay.v1"
STATE_SCHEMA = "h2-phase2-quiet-resource-replay-state.v1"
COMPARISON_SCHEMA = "h2-phase2-quiet-resource-comparison.v1"
SOURCE_PROGRAM_STATUS = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
SOURCE_CAMPAIGN = "h2_complete_product_pipeline_v17"
DEFAULT_SOURCE_WORKSPACE = TOOL_ROOT / "automated_runs" / SOURCE_CAMPAIGN
DEFAULT_SOURCE_RESULTS = TOOL_ROOT / "JustPeachyResults/full_pipeline" / SOURCE_CAMPAIGN
DEFAULT_SOURCE_SUMMARY = TOOL_ROOT / "JustPeachyResearchSummaries" / SOURCE_CAMPAIGN
DEFAULT_CONFIG = TOOL_ROOT / "configs/automated_evaluation/h2_product_program.v17.yaml"
R1_JOB_ID = "h2p2_r1_two_independent_models_matched_serial_resource_a5d81446a0"
R2_JOB_ID = "h2p2_r2_one_shared_model_matched_serial_resource_6599c41691"
JOB_IDS = (R1_JOB_ID, R2_JOB_ID)
EXPECTED_CONFIGURATIONS = {
    R1_JOB_ID: "R1_TWO_INDEPENDENT_MODELS_MATCHED_SERIAL_RESOURCE",
    R2_JOB_ID: "R2_ONE_SHARED_MODEL_MATCHED_SERIAL_RESOURCE",
}
HOST_LOCK_PATH = TOOL_ROOT / "automated_runs/.full_pipeline_evaluation.host.lock"
REPLAY_MANIFEST = "resource_replay_manifest.json"
REPLAY_STATE = "program_state.json"
HOST_IO_RECEIPT = "diagnostics/host_io_interference/serial_resource_replay.json"
COMPARISON_JSON = "resource_comparison.json"
COMPARISON_CSV = "resource_comparison.csv"
BLOCKING_PROCESS_TOKENS = (
    "h2_windows_atomic_retry_bootstrap.py",
    "h2_prefreeze_selector_correction_bootstrap.py",
    "maintain_h2_storage.py",
    "supervise_h2_product_program.ps1",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_c_drive(path: Path) -> bool:
    return path.resolve().drive.casefold() == "c:"


def _attempt_paths(args: argparse.Namespace) -> ProgramPaths:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", args.attempt_id):
        raise ValueError("attempt-id must use 1-32 lowercase letters, digits, _ or -")
    suffix = f"h2_complete_product_pipeline_v17_resource_replay_{args.attempt_id}"
    workspace = args.workspace or TOOL_ROOT / "automated_runs" / suffix
    results = (
        args.results_root or TOOL_ROOT / "JustPeachyResults/full_pipeline" / suffix
    )
    summary = args.summary_root or TOOL_ROOT / "JustPeachyResearchSummaries" / suffix
    return ProgramPaths(
        evaluation_root=TOOL_ROOT,
        workspace=Path(workspace).resolve(),
        results_root=Path(results).resolve(),
        summary_root=Path(summary).resolve(),
        config_path=Path(args.config).resolve(),
    )


def _source_paths(args: argparse.Namespace) -> ProgramPaths:
    return ProgramPaths(
        evaluation_root=TOOL_ROOT,
        workspace=Path(args.source_workspace).resolve(),
        results_root=Path(args.source_results_root).resolve(),
        summary_root=Path(args.source_summary_root).resolve(),
        config_path=Path(args.config).resolve(),
    )


def _source_contract(
    source: ProgramPaths,
) -> tuple[dict[str, object], dict[str, object], tuple[H2Job, ...]]:
    state = _read_json(source.state_path)
    manifest = _read_json(source.jobs_path)
    protocol = _read_json(source.protocol_path)
    if state.get("protocol_id") != manifest.get("protocol_id"):
        raise RuntimeError("source state and job-manifest protocol IDs differ")
    if state.get("protocol_id") != protocol.get("protocol_id"):
        raise RuntimeError("source state and protocol IDs differ")
    if state.get("protocol_sha256") != protocol.get("protocol_sha256"):
        raise RuntimeError("source protocol checksum differs")
    if state.get("job_manifest_sha256") != manifest.get("job_manifest_sha256"):
        raise RuntimeError("source job-manifest identity differs")
    unsigned_manifest = dict(manifest)
    recorded_manifest_sha = unsigned_manifest.pop("job_manifest_sha256", None)
    if recorded_manifest_sha != canonical_sha256(unsigned_manifest):
        raise RuntimeError("source job-manifest self hash differs")
    raw_jobs = manifest.get("jobs")
    if not isinstance(raw_jobs, list):
        raise RuntimeError("source job manifest has no jobs")
    by_id = {
        str(raw.get("job_id")): H2Job.from_jsonable(raw)
        for raw in raw_jobs
        if isinstance(raw, Mapping)
    }
    jobs: list[H2Job] = []
    state_jobs = state.get("jobs")
    if not isinstance(state_jobs, Mapping):
        raise RuntimeError("source state has no jobs")
    for job_id in JOB_IDS:
        job = by_id.get(job_id)
        if job is None:
            raise RuntimeError(f"source matched resource job is missing: {job_id}")
        if (
            job.phase_index != 2
            or job.job_kind != "resource_runtime"
            or job.split != "development"
            or not job.serial
            or job.configuration_id != EXPECTED_CONFIGURATIONS[job_id]
        ):
            raise RuntimeError(
                f"source matched resource job contract differs: {job_id}"
            )
        row = state_jobs.get(job_id)
        if not isinstance(row, Mapping) or row.get("state") != "COMPLETE":
            raise RuntimeError(
                f"source matched resource result is incomplete: {job_id}"
            )
        result_path = Path(str(row.get("result_path") or ""))
        result_sha = str(row.get("result_sha256") or "")
        if (
            not result_path.is_dir()
            or sha256_file(result_path / "checksums.json") != result_sha
        ):
            raise RuntimeError(f"source matched resource checksum differs: {job_id}")
        jobs.append(job)
    return state, {"manifest": manifest, "protocol": protocol}, tuple(jobs)


def _runtime_identity_check(source: ProgramPaths) -> dict[str, object]:
    stored = _read_json(source.workspace / "runtime_implementation_identity.json")
    current = runtime_implementation_identity()
    if current != stored:
        raise RuntimeError(
            "current inference implementation differs from source campaign"
        )
    return stored


def _contamination_receipt(source: ProgramPaths) -> dict[str, object]:
    path = (
        source.workspace
        / "diagnostics/host_io_interference/serial_resource_phase2_redim_host_io.json"
    )
    receipt = _read_json(path)
    if receipt.get("status") not in {
        "SERIAL_RESOURCE_HOST_IO_CONTAMINATED",
        "SERIAL_RESOURCE_HOST_IO_UNVERIFIED",
    }:
        raise RuntimeError("source Phase-2 resource evidence does not require replay")
    if tuple(map(str, receipt.get("candidate_job_ids") or ())) != JOB_IDS:
        raise RuntimeError("source contamination receipt job membership differs")
    return receipt


def _active_blocking_processes(source: ProgramPaths) -> list[dict[str, object]]:
    try:
        import psutil
    except ImportError as exc:  # pragma: no cover - project runtime owns dependency.
        raise RuntimeError("psutil is required for quiet-host process checks") from exc
    matches: list[dict[str, object]] = []
    source_token = str(source.workspace).casefold()
    for process in psutil.process_iter(("pid", "name", "cmdline")):
        if int(process.info.get("pid") or 0) == os.getpid():
            continue
        try:
            command = " ".join(process.info.get("cmdline") or ())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
        folded = command.casefold()
        if not folded:
            continue
        reasons = [token for token in BLOCKING_PROCESS_TOKENS if token in folded]
        if source_token in folded and (
            "app.h2_product_program" in folded or "h2_product_program" in folded
        ):
            reasons.append("source_h2_controller")
        if reasons:
            matches.append(
                {
                    "pid": int(process.info.get("pid") or 0),
                    "name": str(process.info.get("name") or ""),
                    "reasons": sorted(set(reasons)),
                }
            )
    return sorted(matches, key=lambda row: int(row["pid"]))


def _recent_esent_events(minutes: int) -> dict[str, object]:
    if os.name != "nt":
        return {"status": "UNSUPPORTED_NON_WINDOWS", "count": None, "minutes": minutes}
    command = (
        "$s=(Get-Date).AddMinutes(-"
        + str(int(minutes))
        + "); $e=@(Get-WinEvent -FilterHashtable "
        "@{LogName='Application';ProviderName='ESENT';StartTime=$s} "
        "-ErrorAction SilentlyContinue | Where-Object {$_.Id -in 508,510,532,533,901}); "
        "$e.Count"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        return {
            "status": "QUERY_FAILED",
            "count": None,
            "minutes": minutes,
            "detail": completed.stderr.strip()[:500],
        }
    try:
        count = int(completed.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {
            "status": "QUERY_FAILED",
            "count": None,
            "minutes": minutes,
            "detail": completed.stdout.strip()[:500],
        }
    return {
        "status": "PASS" if count == 0 else "RECENT_EVENTS",
        "count": count,
        "minutes": minutes,
    }


def _preflight(
    args: argparse.Namespace,
    *,
    require_source_complete: bool,
) -> dict[str, object]:
    source = _source_paths(args)
    replay = _attempt_paths(args)
    failures: list[str] = []
    for label, path in {
        "source_workspace": source.workspace,
        "source_results": source.results_root,
        "source_summary": source.summary_root,
        "replay_workspace": replay.workspace,
        "replay_results": replay.results_root,
        "replay_summary": replay.summary_root,
        "config": replay.config_path,
    }.items():
        if not _is_c_drive(path):
            failures.append(f"{label} is not on C: {path}")
    state, bound, jobs = _source_contract(source)
    identity = _runtime_identity_check(source)
    contamination = _contamination_receipt(source)
    if require_source_complete and state.get("status") != SOURCE_PROGRAM_STATUS:
        failures.append(
            f"source program is not complete: {state.get('status') or 'UNKNOWN'}"
        )
    if (source.workspace / "h2_program_run.lock").exists():
        failures.append("source H2 campaign lock is present")
    blockers = _active_blocking_processes(source)
    if blockers:
        failures.append("campaign/controller/storage processes are still active")
    free_gib = shutil.disk_usage(Path("C:/")).free / 1024**3
    if free_gib < float(args.minimum_free_gib):
        failures.append(
            f"C: free space {free_gib:.2f} GiB is below {args.minimum_free_gib:.2f} GiB"
        )
    esent = _recent_esent_events(args.quiet_window_minutes)
    if require_source_complete and esent.get("status") != "PASS":
        failures.append("quiet-window ESENT check is not clear")
    if replay.workspace.exists() and not (replay.workspace / REPLAY_MANIFEST).is_file():
        failures.append("replay workspace exists without its immutable manifest")
    return {
        "schema_version": "h2-phase2-resource-replay-preflight.v1",
        "status": "ELIGIBLE" if not failures else "NOT_ELIGIBLE",
        "checked_at_utc": _utc_now(),
        "failures": failures,
        "source_status": state.get("status"),
        "source_protocol_id": state.get("protocol_id"),
        "source_protocol_sha256": state.get("protocol_sha256"),
        "source_job_manifest_sha256": state.get("job_manifest_sha256"),
        "runtime_implementation_identity_sha256": identity.get("identity_sha256"),
        "source_contamination_status": contamination.get("status"),
        "job_ids": [job.job_id for job in jobs],
        "job_identity_sha256s": {job.job_id: job.identity_sha256 for job in jobs},
        "blocking_processes": blockers,
        "quiet_window": esent,
        "c_free_gib": round(free_gib, 2),
        "replay_workspace": str(replay.workspace),
        "replay_results_root": str(replay.results_root),
        "source_bindings_loaded": bool(bound),
        "scientific_settings_changed": False,
    }


def _replay_manifest(
    args: argparse.Namespace,
    *,
    source: ProgramPaths,
    replay: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    runtime_identity: Mapping[str, object],
) -> dict[str, object]:
    source_results = state.get("jobs")
    assert isinstance(source_results, Mapping)
    script_path = Path(__file__).resolve()
    core = {
        "schema_version": SCHEMA,
        "attempt_id": args.attempt_id,
        "purpose": "Matched quiet-host replay of contaminated Phase-2 R1/R2 serial resource evidence.",
        "source_workspace": str(source.workspace),
        "source_results_root": str(source.results_root),
        "replay_workspace": str(replay.workspace),
        "replay_results_root": str(replay.results_root),
        "protocol_id": state["protocol_id"],
        "protocol_sha256": state["protocol_sha256"],
        "job_manifest_sha256": state["job_manifest_sha256"],
        "runtime_implementation_identity_sha256": runtime_identity["identity_sha256"],
        "launcher_path": str(script_path.relative_to(TOOL_ROOT)).replace("\\", "/"),
        "launcher_sha256": _sha256(script_path),
        "measurement_mode": "resources",
        "serial_execution": True,
        "execution_order": list(JOB_IDS),
        "cooldown_sec_between_jobs": int(args.cooldown_sec),
        "quiet_window_minutes": int(args.quiet_window_minutes),
        "automatic_time_cutoff": False,
        "job_bindings": [
            {
                "job_id": job.job_id,
                "job_identity_sha256": job.identity_sha256,
                "configuration_id": job.configuration_id,
                "runtime_tuning_identity_sha256": canonical_sha256(job.runtime_tuning),
                "case_ids_sha256": canonical_sha256(list(job.case_ids)),
                "case_count": len(job.case_ids),
                "audio_duration_sec": job.audio_duration_sec,
                "source_result_sha256": source_results[job.job_id]["result_sha256"],
            }
            for job in jobs
        ],
        "heldout_references_opened": False,
        "scientific_settings_changed": False,
        "source_results_overwritten": False,
    }
    return {**core, "replay_manifest_sha256": canonical_sha256(core)}


def _write_collector_state(
    replay: ProgramPaths,
    *,
    source_state: Mapping[str, object],
    replay_manifest: Mapping[str, object],
) -> dict[str, object]:
    store = EvaluationStateStore(replay.workspace / RUNTIME_QUEUE_DATABASE)
    rows = {row.spec.job_id: row for row in store.list_jobs()}
    jobs: dict[str, object] = {}
    for job_id in JOB_IDS:
        row = rows[job_id]
        jobs[job_id] = {
            "state": row.state.upper(),
            "attempt_count": row.attempt_count,
            "completed_cases": row.completed_cases,
            "completed_audio_sec": row.completed_audio_sec,
            "started_at_utc": row.started_at_utc,
            "completed_at_utc": row.completed_at_utc,
            "result_path": str(replay.results_root / row.spec.result_relative_path),
            "result_sha256": row.result_sha256,
            "last_error": row.last_error,
        }
    complete = all(row.state == "complete" for row in rows.values())
    state = {
        "schema_version": STATE_SCHEMA,
        "status": "COMPLETE" if complete else "RUNNING",
        "protocol_id": source_state["protocol_id"],
        "protocol_sha256": source_state["protocol_sha256"],
        "job_manifest_sha256": source_state["job_manifest_sha256"],
        "replay_manifest_sha256": replay_manifest["replay_manifest_sha256"],
        "updated_at_utc": _utc_now(),
        "jobs": jobs,
    }
    write_json_atomic(replay.state_path, state)
    return state


def _capture_host_io(replay: ProgramPaths) -> dict[str, object]:
    collector = TOOL_ROOT / "scripts/capture_h2_host_io_interference.ps1"
    output = replay.workspace / HOST_IO_RECEIPT
    environment = dict(os.environ)
    environment.update(
        {
            "H2_REPLAY_COLLECTOR": str(collector),
            "H2_REPLAY_WORKSPACE": str(replay.workspace),
            "H2_REPLAY_RESULTS": str(replay.results_root),
            "H2_REPLAY_RECEIPT": str(output),
            "H2_REPLAY_JOB_IDS_JSON": json.dumps(list(JOB_IDS)),
        }
    )
    powershell = (
        "$ids=@(ConvertFrom-Json -InputObject $env:H2_REPLAY_JOB_IDS_JSON); "
        "& $env:H2_REPLAY_COLLECTOR -Workspace $env:H2_REPLAY_WORKSPACE "
        "-ResultsRoot $env:H2_REPLAY_RESULTS -EvidenceClass SerialResource "
        "-CandidateJobIds $ids -OutputPath $env:H2_REPLAY_RECEIPT; "
        "exit $LASTEXITCODE"
    )
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        powershell,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "host-I/O collector failed: "
            + (completed.stderr.strip() or completed.stdout.strip())[:1000]
        )
    return _read_json(output)


def _resource_metrics(result_root: Path) -> dict[str, object]:
    document = _read_json(result_root / "metrics/resources.json")
    subviews = document.get("subviews")
    resources = subviews.get("resources") if isinstance(subviews, Mapping) else None
    metrics = resources.get("metrics") if isinstance(resources, Mapping) else None
    if not isinstance(metrics, Mapping):
        raise RuntimeError(f"resource metrics are missing: {result_root}")
    wanted = (
        "total_rtf",
        "audio_throughput",
        "peak_rss_bytes",
        "maximum_queue_depth",
        "model_bytes",
        "cache_bytes",
        "failure_count",
        "retry_count",
    )
    result: dict[str, object] = {}
    for key in wanted:
        row = metrics.get(key)
        result[key] = row.get("value") if isinstance(row, Mapping) else None
    case_path = result_root / "diagnostics/case_status.jsonl"
    blocked_total = 0.0
    blocked_max = 0.0
    dropped = 0
    with case_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            queue = row.get("queue_backpressure") or {}
            blocked_total += float(queue.get("blocked_total_sec") or 0.0)
            blocked_max = max(blocked_max, float(queue.get("blocked_max_sec") or 0.0))
            dropped += int(queue.get("dropped_frames") or 0)
    result.update(
        {
            "blocked_total_sec": blocked_total,
            "blocked_max_sec": blocked_max,
            "dropped_frames": dropped,
        }
    )
    return result


def _analyze(replay: ProgramPaths) -> dict[str, object]:
    replay_manifest = _read_json(replay.workspace / REPLAY_MANIFEST)
    state = _read_json(replay.state_path)
    receipt = _read_json(replay.workspace / HOST_IO_RECEIPT)
    state_jobs = state.get("jobs")
    if not isinstance(state_jobs, Mapping):
        raise RuntimeError("replay state has no jobs")
    values: dict[str, dict[str, object]] = {}
    for job_id in JOB_IDS:
        row = state_jobs.get(job_id)
        if not isinstance(row, Mapping) or row.get("state") != "COMPLETE":
            raise RuntimeError(f"replay job is incomplete: {job_id}")
        root = Path(str(row["result_path"]))
        values[job_id] = _resource_metrics(root)
        values[job_id]["result_sha256"] = row.get("result_sha256")
    r1 = values[R1_JOB_ID]
    r2 = values[R2_JOB_ID]
    deltas: dict[str, object] = {}
    for key in (
        "total_rtf",
        "peak_rss_bytes",
        "blocked_total_sec",
        "blocked_max_sec",
    ):
        first = float(r1[key])
        second = float(r2[key])
        deltas[f"r2_minus_r1_{key}"] = second - first
        deltas[f"r2_reduction_fraction_{key}"] = (
            (first - second) / first if first else None
        )
    eligible = receipt.get("status") == "SERIAL_RESOURCE_HOST_IO_CLEAR"
    core = {
        "schema_version": COMPARISON_SCHEMA,
        "status": "COMPLETE_ELIGIBLE" if eligible else "COMPLETE_REPLAY_NOT_CLEAR",
        "eligible_for_final_resource_ranking": eligible,
        "host_io_status": receipt.get("status"),
        "replay_manifest_sha256": replay_manifest["replay_manifest_sha256"],
        "execution_order": list(JOB_IDS),
        "jobs": values,
        "matched_deltas": deltas,
        "interpretation": (
            "Use this replay for the final R1/R2 resource comparison."
            if eligible
            else "Do not use this attempt for final resource ranking; run a new quiet attempt."
        ),
    }
    comparison = {**core, "comparison_sha256": canonical_sha256(core)}
    write_json_atomic(replay.summary_root / COMPARISON_JSON, comparison)
    replay.summary_root.mkdir(parents=True, exist_ok=True)
    csv_path = replay.summary_root / COMPARISON_CSV
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "job_id",
                "strategy",
                "eligible",
                "host_io_status",
                "total_rtf",
                "peak_rss_bytes",
                "maximum_queue_depth",
                "blocked_total_sec",
                "blocked_max_sec",
                "dropped_frames",
                "result_sha256",
            ),
        )
        writer.writeheader()
        for job_id, strategy in ((R1_JOB_ID, "R1"), (R2_JOB_ID, "R2")):
            writer.writerow(
                {
                    "job_id": job_id,
                    "strategy": strategy,
                    "eligible": eligible,
                    "host_io_status": receipt.get("status"),
                    **{
                        key: values[job_id].get(key)
                        for key in (
                            "total_rtf",
                            "peak_rss_bytes",
                            "maximum_queue_depth",
                            "blocked_total_sec",
                            "blocked_max_sec",
                            "dropped_frames",
                            "result_sha256",
                        )
                    },
                }
            )
    return {
        **comparison,
        "comparison_json": str(replay.summary_root / COMPARISON_JSON),
        "comparison_csv": str(csv_path),
    }


def _run(args: argparse.Namespace) -> dict[str, object]:
    preflight = _preflight(args, require_source_complete=True)
    if preflight["status"] != "ELIGIBLE":
        return preflight
    source = _source_paths(args)
    replay = _attempt_paths(args)
    source_state, bound, jobs = _source_contract(source)
    protocol = bound["protocol"]
    assert isinstance(protocol, Mapping)
    identity = _runtime_identity_check(source)
    replay_manifest = _replay_manifest(
        args,
        source=source,
        replay=replay,
        state=source_state,
        jobs=jobs,
        runtime_identity=identity,
    )
    replay.workspace.mkdir(parents=True, exist_ok=True)
    replay.results_root.mkdir(parents=True, exist_ok=True)
    replay.summary_root.mkdir(parents=True, exist_ok=True)
    write_once_or_verify(replay.workspace / REPLAY_MANIFEST, replay_manifest)
    source_job_bytes = source.jobs_path.read_bytes()
    if replay.jobs_path.is_file() and replay.jobs_path.read_bytes() != source_job_bytes:
        raise RuntimeError("replay copy of the immutable job manifest differs")
    if not replay.jobs_path.is_file():
        replay.jobs_path.write_bytes(source_job_bytes)
    prepare_runtime_queue(
        replay,
        jobs,
        protocol=protocol,
        job_manifest_sha256=str(replay_manifest["replay_manifest_sha256"]),
        seed=int(load_and_validate_spec(replay.config_path)["seed"]),
    )
    _write_collector_state(
        replay, source_state=source_state, replay_manifest=replay_manifest
    )
    stop_event = threading.Event()
    progress_lock = threading.Lock()

    def storage_reserve() -> None:
        free_gib = shutil.disk_usage(Path("C:/")).free / 1024**3
        if free_gib < float(args.minimum_free_gib):
            raise RuntimeError("C: free-space reserve fell below the replay minimum")

    with HostRunLock(HOST_LOCK_PATH, measurement_mode="resources"):
        if (source.workspace / "h2_program_run.lock").exists():
            raise RuntimeError("source H2 campaign restarted after replay preflight")
        for index, job in enumerate(jobs):
            quiet = _recent_esent_events(args.quiet_window_minutes)
            blockers = _active_blocking_processes(source)
            if quiet.get("status") != "PASS" or blockers:
                raise RuntimeError(
                    f"host is not quiet before {job.job_id}: events={quiet}; blockers={blockers}"
                )
            run_runtime_job(
                replay,
                job,
                protocol=protocol,
                stop_event=stop_event,
                progress_lock=progress_lock,
                additional_execution_contract={
                    "h2_phase2_quiet_resource_replay_manifest_sha256": replay_manifest[
                        "replay_manifest_sha256"
                    ],
                    "h2_phase2_quiet_resource_replay_launcher_sha256": replay_manifest[
                        "launcher_sha256"
                    ],
                    "h2_phase2_quiet_resource_replay_source_result_sha256": replay_manifest[
                        "job_bindings"
                    ][index]["source_result_sha256"],
                },
                storage_reserve_callback=storage_reserve,
                external_stop_path=replay.workspace / "stop_request.json",
            )
            _write_collector_state(
                replay, source_state=source_state, replay_manifest=replay_manifest
            )
            if index + 1 < len(jobs) and args.cooldown_sec:
                time.sleep(int(args.cooldown_sec))
    final_state = _write_collector_state(
        replay, source_state=source_state, replay_manifest=replay_manifest
    )
    if final_state.get("status") != "COMPLETE":
        raise RuntimeError("one or more replay jobs did not complete")
    _capture_host_io(replay)
    return _analyze(replay)


def _status(replay: ProgramPaths) -> dict[str, object]:
    state_path = replay.state_path
    state = _read_json(state_path) if state_path.is_file() else {}
    receipt_path = replay.workspace / HOST_IO_RECEIPT
    receipt = _read_json(receipt_path) if receipt_path.is_file() else {}
    comparison_path = replay.summary_root / COMPARISON_JSON
    comparison = _read_json(comparison_path) if comparison_path.is_file() else {}
    return {
        "schema_version": "h2-phase2-resource-replay-status.v1",
        "status": state.get("status") or "NOT_STARTED",
        "attempt_id": replay.workspace.name,
        "jobs": state.get("jobs") or {},
        "host_io_status": receipt.get("status"),
        "eligible_for_final_resource_ranking": comparison.get(
            "eligible_for_final_resource_ranking"
        ),
        "workspace": str(replay.workspace),
        "results_root": str(replay.results_root),
        "summary_root": str(replay.summary_root),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("self-test", "preflight", "run", "status", "analyze")
    )
    parser.add_argument("--attempt-id", default="quiet01")
    parser.add_argument(
        "--source-workspace", type=Path, default=DEFAULT_SOURCE_WORKSPACE
    )
    parser.add_argument(
        "--source-results-root", type=Path, default=DEFAULT_SOURCE_RESULTS
    )
    parser.add_argument(
        "--source-summary-root", type=Path, default=DEFAULT_SOURCE_SUMMARY
    )
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--summary-root", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--minimum-free-gib", type=float, default=35.0)
    parser.add_argument("--quiet-window-minutes", type=int, default=15)
    parser.add_argument("--cooldown-sec", type=int, default=60)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    if args.minimum_free_gib < 1:
        raise ValueError("minimum-free-gib must be at least 1")
    if args.quiet_window_minutes < 1 or args.cooldown_sec < 0:
        raise ValueError(
            "quiet-window-minutes must be positive and cooldown non-negative"
        )
    replay = _attempt_paths(args)
    if args.action == "self-test":
        payload = _preflight(args, require_source_complete=False)
        payload["status"] = "PASS"
        payload["run_eligible_now"] = not payload["failures"]
        payload["active_campaign_modified"] = False
    elif args.action == "preflight":
        payload = _preflight(args, require_source_complete=True)
    elif args.action == "run":
        payload = _run(args)
    elif args.action == "status":
        payload = _status(replay)
    elif args.action == "analyze":
        payload = _analyze(replay)
    else:  # pragma: no cover - argparse owns choices.
        raise AssertionError(args.action)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 2 if payload.get("status") == "NOT_ELIGIBLE" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
