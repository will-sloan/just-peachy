"""Restart-safe, H2-only scientific program controller.

The controller owns scheduling, immutable identities, the development/evaluation
firewall, and progress reporting.  It delegates every neural runtime job to the
existing full-pipeline evaluation queue and fails closed for research job kinds
that do not yet have a truthful implementation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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

from app.full_pipeline.product_modes import H2RuntimeTuning
from app.full_pipeline_demo.runtime_config import (
    build_h2_demo_runtime_binding_payload,
    load_h2_demo_runtime_binding,
)
from app.full_pipeline_evaluation.host_lock import HostRunLock
from app.full_pipeline_evaluation.results import validate_result_tree
from app.full_pipeline_evaluation.store import EvaluationStateStore

from .contracts import (
    H2Job,
    H2_MODES,
    H2ProgramError,
    H2_PROGRAM_SCHEMA_VERSION,
    ProgramPaths,
)
from .execution import (
    RUNTIME_KINDS,
    RUNTIME_QUEUE_DATABASE,
    build_runtime_specs,
    prepare_runtime_queue,
    run_runtime_job,
    runtime_implementation_identity,
    runtime_result_reusable,
    validate_runtime_tuning,
)
from .io import (
    canonical_sha256,
    read_json,
    read_jsonl,
    read_yaml,
    sha256_file,
    write_json_atomic,
    write_jsonl_atomic,
    write_once_or_verify,
)
from .planning import (
    HISTORICAL_EVIDENCE_PATH,
    PREPARED_PROTOCOL_ROOT,
    build_job_manifest,
    build_protocol_manifest,
    default_paths,
    load_and_validate_spec,
)
from .promotion import (
    METRIC_PRIORITY,
    REQUIRED_PROMOTION_METRICS,
    REQUIRED_SAFETY_METRICS,
    REQUIRED_SHORT_TURN_METRICS,
    metric_vector_from_result,
    select_promotions,
)


SUCCESS_STATES = frozenset({"COMPLETE", "SUPERSEDED"})
TERMINAL_STATES = frozenset({"COMPLETE", "FAILED", "STOPPED", "SUPERSEDED"})
UNIMPLEMENTED_KINDS: frozenset[str] = frozenset()
STATE_LOCK_NAME = "h2_program_run.lock"
NON_RUNTIME_RESULT = "job_result.json"
HELDOUT_EXECUTION_MANIFEST = "heldout_execution_manifest.json"
HELDOUT_QUEUE_DIRECTORY = "heldout_frozen_queue"
RUNTIME_IMPLEMENTATION_IDENTITY = "runtime_implementation_identity.json"
MILESTONES_FILE = "milestones.jsonl"
LAST_QUEUE_SNAPSHOT_FILE = "last_queue_snapshot.json"
DYNAMIC_RUNTIME_KINDS = frozenset(
    {
        "post_promotion_integration",
        "post_selection_paragraph_validation",
        "post_selection_mode_validation",
        "post_selection_resource_runtime",
    }
)
HANDLER_SELECTED_AXES: Mapping[str, frozenset[str]] = {
    "embedding_reuse_parity": frozenset(
        {
            "redim_execution_strategy",
            "embedding_reuse_qualification_sha256",
        }
    ),
    "policy_replay": frozenset(
        {
            "score_threshold",
            "margin_threshold",
            "minimum_evidence_sec",
            "minimum_embedding_consistency",
            "identity_accumulation",
        }
    ),
    "memory_policy_replay": frozenset(
        {
            "hysteresis_policy",
            "consecutive_passes_to_confirm",
            "consecutive_failures_to_release",
            "hysteresis",
            "identity_expiry_sec",
            "identity_expiry_mode",
            "memory_level",
        }
    ),
    "short_turn_replay": frozenset(
        {
            "short_turn_attach_gap_sec",
            "short_turn_inheritance_max_sec",
            "retroactive_correction_sec",
        }
    ),
    "transcript_policy_replay": frozenset(
        {
            "boundary_correction_ms",
            "overlap_policy",
            "paragraph_policy",
            "paragraph_pause_sec",
            "paragraph_max_words",
        }
    ),
}
_STORAGE_SIZE_CACHE: dict[str, tuple[float, tuple[int, int, int]]] = {}
APP_VALIDATION_CAPABILITIES: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "scientific_runtime_configuration": {
        "test_paths": ("tests/full_pipeline_demo/test_runtime_config.py",),
        "source_paths": ("app/full_pipeline_demo/runtime_config.py",),
    },
    "live_microphone": {
        "test_paths": (
            "tests/full_pipeline_demo/test_state_devices.py",
            "tests/full_pipeline_demo/test_ui.py",
        ),
        "source_paths": (
            "app/full_pipeline_demo/cli.py",
            "app/full_pipeline_demo/ui.py",
            "app/full_pipeline/factory.py",
        ),
    },
    "audio_file_simulation": {
        "test_paths": (
            "tests/full_pipeline_demo/test_cli.py",
            "tests/full_pipeline_demo/test_session_export.py",
        ),
        "source_paths": (
            "app/full_pipeline_demo/cli.py",
            "app/full_pipeline_demo/session.py",
        ),
    },
    "speaker_enrollment": {
        "test_paths": ("tests/full_pipeline_demo/test_presets_enrollment.py",),
        "source_paths": (
            "app/full_pipeline_demo/enrollment.py",
            "app/full_pipeline_demo/cli.py",
        ),
    },
    "embedding_inspector": {
        "test_paths": ("tests/full_pipeline_demo/test_ui.py",),
        "source_paths": ("app/full_pipeline_demo/ui.py",),
    },
}


def _superseded_h2_evidence(
    spec: Mapping[str, object], evaluation_root: Path
) -> dict[str, Path]:
    superseded_program_id = str(spec.get("supersedes_program_id", ""))
    match = re.fullmatch(
        r"h2_complete_product_pipeline_program_(v[0-9]+)",
        superseded_program_id,
    )
    if match is None:
        raise H2ProgramError(
            "supersedes_program_id must identify an H2 product-program version"
        )
    version = match.group(1)
    prior_root = (
        evaluation_root / f"automated_runs/h2_complete_product_pipeline_{version}"
    )
    prefix = f"superseded_h2_{version}"
    evidence = {
        f"{prefix}_program_state": prior_root / "program_state.json",
        f"{prefix}_protocol_manifest": prior_root / "protocol_manifest.json",
        f"{prefix}_job_manifest": prior_root / "job_manifest.json",
        f"{prefix}_campaign_database": prior_root / "campaign.sqlite3",
        f"{prefix}_runtime_identity": (
            prior_root / "runtime_implementation_identity.json"
        ),
        f"{prefix}_validation": prior_root / "validation.json",
    }
    # A blocked development campaign may have no operator stop request. When a
    # stop record exists, bind it too; its absence is not loss of evidence.
    stop_request = prior_root / "stop_request.json"
    if stop_request.is_file():
        evidence[f"{prefix}_stop_request"] = stop_request
    supersession_receipt = prior_root / "supersession_receipt.json"
    if supersession_receipt.is_file():
        evidence[f"{prefix}_supersession_receipt"] = supersession_receipt
    return evidence


def audit(paths: ProgramPaths | None = None) -> dict[str, object]:
    paths = paths or default_paths()
    spec = load_and_validate_spec(paths.config_path)
    protocol = build_protocol_manifest(paths)
    jobs = build_job_manifest(protocol)
    _require_c_drive(paths)
    prior_state_path = (
        paths.evaluation_root / "runs/full_pipeline_program/PROGRAM_STATE.json"
    )
    handoff_path = paths.evaluation_root / "docs/full_pipeline/PROGRAM_HANDOFF.md"
    prior_campaign_root = (
        paths.evaluation_root / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1"
    )
    prior_state = read_json(prior_state_path) if prior_state_path.is_file() else None
    process_audit = _current_process_audit()
    existing_h2_state = (
        read_json(paths.state_path) if paths.state_path.is_file() else None
    )
    required_evidence = {
        "historical_evidence": HISTORICAL_EVIDENCE_PATH,
        "prior_program_state": prior_state_path,
        "program_handoff": handoff_path,
        "prior_campaign_program_state": prior_campaign_root / "program_state.json",
        "prior_campaign_stop_request": prior_campaign_root / "stop_request.json",
        "prior_campaign_milestones": prior_campaign_root / "milestones.jsonl",
    }
    required_evidence.update(_superseded_h2_evidence(spec, paths.evaluation_root))
    evidence_rows = [
        {
            "name": name,
            "path": str(path.resolve()),
            "exists": path.is_file(),
            "sha256": sha256_file(path) if path.is_file() else None,
            "size_bytes": path.stat().st_size if path.is_file() else None,
        }
        for name, path in required_evidence.items()
    ]
    prior_campaign = _preserved_campaign_audit(paths, process_audit=process_audit)
    h2_pipelines = sorted(
        {
            str(row["pipeline_id"])
            for row in jobs["jobs"]
            if isinstance(row, Mapping) and row.get("pipeline_id") != "NOT_APPLICABLE"
        }
    )
    h2_only = h2_pipelines == [
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_dr_ir",
    ]
    preserved_queue = prior_campaign.get("queue")
    preserved_queue_terminal = bool(
        isinstance(preserved_queue, Mapping)
        and preserved_queue.get("exists") is True
        and preserved_queue.get("all_jobs_terminal") is True
    )
    active_campaigns = bool(process_audit.get("other_campaigns"))
    passed = (
        all(row["exists"] for row in evidence_rows)
        and bool(process_audit.get("completed"))
        and not active_campaigns
        and h2_only
        and preserved_queue_terminal
    )
    audit_status = (
        "BLOCKED_ACTIVE_CAMPAIGN_TRANSITION"
        if active_campaigns
        else ("PASS" if passed else "FAIL")
    )
    return {
        "schema_version": "h2-product-program-audit.v1",
        "status": audit_status,
        "valid": passed,
        "program_id": spec["program_id"],
        "protocol_id": protocol["protocol_id"],
        "job_count": jobs["job_count"],
        "pipelines": h2_pipelines,
        "h2_only": h2_only,
        "preserved_prior_queue_terminal": preserved_queue_terminal,
        "workspace": str(paths.workspace),
        "results_root": str(paths.results_root),
        "summary_root": str(paths.summary_root),
        "all_paths_on_c_drive": True,
        "target_wall_hours": 192.0,
        "automatic_time_cutoff": False,
        "historical_evidence_sha256": sha256_file(HISTORICAL_EVIDENCE_PATH),
        "preserved_evidence": evidence_rows,
        "prior_program_status": (
            prior_state.get("status") if isinstance(prior_state, Mapping) else None
        ),
        "prior_long_campaign_started": prior_campaign["campaign_started"],
        "prior_campaign": prior_campaign,
        "current_process_audit": process_audit,
        "concurrent_campaign_warning": active_campaigns,
        "existing_h2_workspace_status": (
            existing_h2_state.get("status")
            if isinstance(existing_h2_state, Mapping)
            else "NOT_PREPARED"
        ),
        "long_campaign_started": bool(
            isinstance(existing_h2_state, Mapping)
            and existing_h2_state.get("started_at_utc")
        ),
    }


def _preserved_campaign_audit(
    paths: ProgramPaths, *, process_audit: Mapping[str, object]
) -> dict[str, object]:
    root = (
        paths.evaluation_root / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1"
    )
    state_path = root / "program_state.json"
    stop_path = root / "stop_request.json"
    milestones_path = root / "milestones.jsonl"
    queue_path = (
        paths.evaluation_root
        / "automated_runs/full_pipeline_development_prompt4_reduced_8day_v1_orchestrated"
        / "development_accuracy/campaign.sqlite3"
    )
    state = read_json(state_path) if state_path.is_file() else {}
    stop_request = read_json(stop_path) if stop_path.is_file() else {}
    queue_summary: dict[str, object] = {
        "path": str(queue_path.resolve()),
        "exists": queue_path.is_file(),
    }
    if queue_path.is_file():
        store = EvaluationStateStore(queue_path)
        store.assert_integrity()
        rows = store.list_jobs()
        state_counts = Counter(row.state for row in rows)
        queue_summary.update(
            {
                "sha256": sha256_file(queue_path),
                "job_count": len(rows),
                "state_counts": dict(sorted(state_counts.items())),
                "all_jobs_terminal": set(state_counts)
                <= {
                    "complete",
                    "failed",
                    "partial",
                    "stopped",
                },
                "completed_cases": sum(row.completed_cases for row in rows),
                "completed_audio_sec": sum(row.completed_audio_sec for row in rows),
            }
        )
    return {
        "campaign_started": bool(state.get("program_started_at_utc")),
        "controller_status": state.get("status"),
        "prompt_4_status": (
            state.get("stages", {}).get("4", {}).get("status")
            if isinstance(state.get("stages"), Mapping)
            and isinstance(state.get("stages", {}).get("4"), Mapping)
            else None
        ),
        "stop_requested": bool(stop_request),
        "stop_reason": stop_request.get("reason"),
        "superseded_by_h2": stop_request.get("reason")
        == "superseded_by_h2_product_decision",
        "controller_stop_timed_out_but_queue_jobs_are_terminal": (
            state.get("status") == "STOP_TIMEOUT"
            and not bool(process_audit.get("other_campaigns"))
            and queue_summary.get("all_jobs_terminal") is True
        ),
        "program_state_path": str(state_path.resolve()),
        "program_state_sha256": (
            sha256_file(state_path) if state_path.is_file() else None
        ),
        "stop_request_sha256": (
            sha256_file(stop_path) if stop_path.is_file() else None
        ),
        "milestones_sha256": (
            sha256_file(milestones_path) if milestones_path.is_file() else None
        ),
        "queue": queue_summary,
        "prior_evidence_modified": False,
    }


def _current_process_audit() -> dict[str, object]:
    """Read active scientific-controller commands without changing processes."""

    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=30.0,
        )
        if completed.returncode != 0:
            raise H2ProgramError(
                f"process query exited {completed.returncode}: {completed.stderr[-300:]}"
            )
        raw = completed.stdout.strip()
        values = json.loads(raw) if raw else []
        rows = values if isinstance(values, list) else [values]
        all_processes = [
            {
                "pid": int(row.get("ProcessId") or 0),
                "parent_pid": int(row.get("ParentProcessId") or 0),
                "name": row.get("Name"),
                "command_line": row.get("CommandLine"),
            }
            for row in rows
            if isinstance(row, Mapping)
        ]
        process_by_pid = {row["pid"]: row for row in all_processes}
        ancestor_pids: set[int] = set()
        parent_pid = process_by_pid.get(os.getpid(), {}).get("parent_pid")
        while (
            isinstance(parent_pid, int)
            and parent_pid
            and parent_pid not in ancestor_pids
        ):
            ancestor_pids.add(parent_pid)
            parent_pid = process_by_pid.get(parent_pid, {}).get("parent_pid")
        process_markers = (
            "h2_product_program",
            "full_pipeline_evaluation",
            "full_pipeline_development",
            "full_pipeline_eight_day",
            "speaker_enrollment",
            "diarization_product",
        )
        processes = [
            row
            for row in all_processes
            if any(
                marker in str(row.get("command_line") or "").casefold()
                for marker in process_markers
            )
        ]
        others = [
            row
            for row in processes
            if row["pid"] != os.getpid()
            and row["pid"] not in ancestor_pids
            and "get-ciminstance win32_process"
            not in str(row.get("command_line") or "").casefold()
            and any(
                marker in f" {str(row.get('command_line') or '').casefold()} "
                for marker in (
                    " -action run ",
                    " -action resume ",
                    " -action runforeground ",
                    " -action rundevelopment ",
                    " -action runevaluation ",
                    " -action runaccuracy ",
                    " -action runall ",
                    " h2_product_program run ",
                    " h2_product_program resume ",
                    " run-development ",
                    " run-evaluation ",
                    " runevaluation ",
                    " rundevelopment ",
                )
            )
        ]
        return {
            "completed": True,
            "method": "read_only_Win32_Process_CIM_query",
            "current_pid": os.getpid(),
            "ancestor_pids_excluded": sorted(ancestor_pids),
            "matching_processes": processes,
            "other_campaigns": others,
            "processes_stopped_or_modified": False,
        }
    except Exception as exc:
        return {
            "completed": False,
            "method": "read_only_Win32_Process_CIM_query",
            "current_pid": os.getpid(),
            "matching_processes": [],
            "other_campaigns": [],
            "error": f"{type(exc).__name__}: {exc}",
            "processes_stopped_or_modified": False,
        }


def _require_launch_transition(paths: ProgramPaths) -> dict[str, object]:
    """Fail before workspace writes when the H2 transition is not safe."""

    transition = audit(paths)
    if transition.get("valid") is not True:
        status_value = str(transition.get("status") or "FAIL")
        if status_value == "BLOCKED_ACTIVE_CAMPAIGN_TRANSITION":
            raise H2ProgramError(
                "BLOCKED_ACTIVE_CAMPAIGN_TRANSITION: another scientific campaign "
                "Run/Resume process is active; stop it gracefully before preparing "
                "or running H2"
            )
        raise H2ProgramError(
            "H2 transition audit failed before workspace writes/inference: "
            f"{status_value}"
        )
    return transition


def prepare(paths: ProgramPaths | None = None) -> dict[str, object]:
    paths = paths or default_paths()
    _require_launch_transition(paths)
    _require_c_drive(paths)
    spec = load_and_validate_spec(paths.config_path)
    paths.workspace.mkdir(parents=True, exist_ok=True)
    paths.results_root.mkdir(parents=True, exist_ok=True)
    paths.summary_root.mkdir(parents=True, exist_ok=True)
    protocol = build_protocol_manifest(paths)
    manifest = build_job_manifest(protocol)
    write_once_or_verify(paths.protocol_path, protocol)
    write_once_or_verify(paths.jobs_path, manifest)
    write_once_or_verify(
        paths.workspace / RUNTIME_IMPLEMENTATION_IDENTITY,
        runtime_implementation_identity(),
    )
    jobs = _manifest_jobs(manifest)
    queue = prepare_runtime_queue(
        paths,
        tuple(job for job in jobs if job.split != "evaluation"),
        protocol=protocol,
        job_manifest_sha256=str(manifest["job_manifest_sha256"]),
        seed=int(spec["seed"]),
    )
    if paths.state_path.is_file():
        state = read_json(paths.state_path)
        _require_state_bindings(state, protocol, manifest)
        inserted = False
    else:
        state = _initial_state(paths, protocol, manifest, jobs)
        write_json_atomic(paths.state_path, state)
        inserted = True
    return {
        "schema_version": "h2-product-program-preparation.v1",
        "status": "PASS",
        "workspace_created": inserted,
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol["protocol_sha256"],
        "job_manifest_sha256": manifest["job_manifest_sha256"],
        "job_count": len(jobs),
        "runtime_queue": queue,
        "automatic_phase_transition": True,
        "target_is_advisory_only": True,
        "automatic_time_cutoff": False,
        "long_campaign_started": False,
    }


def validate(
    paths: ProgramPaths | None = None, *, verify_results: bool = True
) -> dict[str, object]:
    paths = paths or default_paths()
    errors: list[str] = []
    try:
        _require_c_drive(paths)
        expected_protocol = build_protocol_manifest(paths)
        expected_manifest = build_job_manifest(expected_protocol)
        protocol = read_json(paths.protocol_path)
        manifest = read_json(paths.jobs_path)
        if protocol != expected_protocol:
            errors.append("protocol manifest differs from current checksum-bound plan")
        if manifest != expected_manifest:
            errors.append("job manifest differs from current checksum-bound plan")
        _verify_protocol_identity(protocol)
        _verify_job_manifest_identity(manifest)
        jobs = _manifest_jobs(manifest)
        if any(
            job.pipeline_id
            not in {
                "fullpipe_v1_ag_dr_ir",
                "fullpipe_v1_ao_dr_ir",
                "NOT_APPLICABLE",
            }
            for job in jobs
        ):
            errors.append("non-H2 pipeline escaped the H2 plan")
        for job in jobs:
            if job.job_kind in RUNTIME_KINDS:
                validate_runtime_tuning(job)
        state = read_json(paths.state_path)
        _require_state_bindings(state, protocol, manifest)
        _validate_state_jobs(state, jobs)
        for collection in ("promotions", "axis_selections"):
            decisions = state.get(collection)
            if decisions is None:
                continue
            if not isinstance(decisions, Mapping):
                errors.append(f"state {collection} must be a mapping")
                continue
            for decision_key in decisions:
                _validated_promotion_decision(
                    paths,
                    state,
                    collection=collection,
                    key=str(decision_key),
                )
        implementation_path = paths.workspace / RUNTIME_IMPLEMENTATION_IDENTITY
        if not implementation_path.is_file():
            errors.append("runtime implementation identity is missing")
        elif read_json(implementation_path) != runtime_implementation_identity():
            errors.append("result-affecting runtime implementation identity changed")
        store = EvaluationStateStore(paths.workspace / RUNTIME_QUEUE_DATABASE)
        store.assert_integrity()
        runtime_rows = {row.spec.job_id: row for row in store.list_jobs()}
        expected_runtime_ids = {
            job.job_id
            for job in jobs
            if job.job_kind in RUNTIME_KINDS and job.split != "evaluation"
        }
        if set(runtime_rows) != expected_runtime_ids:
            errors.append("runtime queue membership differs from the H2 manifest")
        seed = int(load_and_validate_spec(paths.config_path)["seed"])
        expected_specs = {
            spec.job_id: spec.to_jsonable()
            for spec in build_runtime_specs(
                tuple(
                    job
                    for job in jobs
                    if job.job_kind in RUNTIME_KINDS and job.split != "evaluation"
                ),
                protocol=protocol,
                seed=seed,
            )
        }
        if {
            job_id: row.spec.to_jsonable() for job_id, row in runtime_rows.items()
        } != expected_specs:
            errors.append("runtime queue specifications/code identities differ")
        metadata = store.metadata()
        if metadata.get("campaign_id") != protocol.get("protocol_id"):
            errors.append("runtime queue protocol binding differs")
        queue_manifest = paths.workspace / "campaign_manifest.json"
        if metadata.get("manifest_sha256") != sha256_file(queue_manifest):
            errors.append("runtime queue manifest binding differs")
        for logical_job in jobs:
            if logical_job.job_kind not in DYNAMIC_RUNTIME_KINDS:
                continue
            logical_state = _job_state(state, logical_job.job_id)
            dynamic_manifest = (
                _dynamic_paths(paths, logical_job).workspace / "dynamic_execution.json"
            )
            if dynamic_manifest.is_file() or logical_state.get("state") in {
                "RUNNING",
                "COMPLETE",
                "FAILED",
                "STOPPED",
            }:
                errors.extend(
                    _validate_dynamic_execution(
                        paths,
                        logical_job,
                        logical_state,
                        protocol=protocol,
                        seed=seed,
                        verify_result=verify_results,
                    )
                )
        if verify_results:
            for job in jobs:
                row = _job_state(state, job.job_id)
                if row.get("state") != "COMPLETE":
                    continue
                if job.job_kind in DYNAMIC_RUNTIME_KINDS:
                    continue
                if job.job_kind not in RUNTIME_KINDS:
                    result_path_value = row.get("result_path")
                    if not result_path_value:
                        errors.append(f"completed job lacks result path: {job.job_id}")
                        continue
                    result_path = Path(str(result_path_value))
                    if not result_path.is_file():
                        errors.append(f"completed job result is missing: {job.job_id}")
                    elif sha256_file(result_path) != row.get("result_sha256"):
                        errors.append(f"completed job checksum differs: {job.job_id}")
                    if job.job_kind in {
                        "long_session",
                        "long_session_evaluation",
                        "reliability",
                    }:
                        from .reliability import validate_reliability_result

                        selected = (
                            _require_frozen_gate(paths, state, jobs)["selected_runtime"]
                            if job.split == "evaluation"
                            else _selected_runtime_configuration(paths, state, jobs)
                        )
                        tuning = H2RuntimeTuning.from_mapping(
                            {
                                **dict(selected["runtime_tuning"]),
                                "product_mode": job.mode,
                            }
                        )
                        validation = validate_reliability_result(
                            paths,
                            job,
                            protocol=protocol,
                            runtime_tuning=tuning,
                        )
                        errors.extend(
                            f"{job.job_id}: {error}" for error in validation["errors"]
                        )
                    if job.job_kind == "app_validation":
                        errors.extend(
                            f"{job.job_id}: {error}"
                            for error in _validate_app_validation_result(
                                paths,
                                job,
                                row,
                                protocol=protocol,
                                state=state,
                                jobs=jobs,
                            )
                        )
                    continue
                if job.split == "evaluation":
                    execution_job = _heldout_execution_job(paths, job.job_id)
                    heldout_store = EvaluationStateStore(
                        _heldout_paths(paths).workspace / RUNTIME_QUEUE_DATABASE
                    )
                    queued = next(
                        row
                        for row in heldout_store.list_jobs()
                        if row.spec.job_id == execution_job.job_id
                    )
                    result_base = _heldout_paths(paths).results_root
                else:
                    queued = runtime_rows[job.job_id]
                    result_base = paths.results_root
                report = validate_result_tree(
                    result_base / queued.spec.result_relative_path,
                    expected_reuse_identity=queued.spec.reuse_identity,
                )
                if not report.reusable:
                    errors.append(f"runtime result is not reusable: {job.job_id}")
                if queued.result_sha256 != row.get("result_sha256"):
                    errors.append(f"runtime state checksum differs: {job.job_id}")
        heldout_complete = any(
            job.split == "evaluation"
            and _job_state(state, job.job_id).get("state") == "COMPLETE"
            for job in jobs
        )
        if heldout_complete:
            _require_frozen_gate(paths, state, jobs)
        elif paths.freeze_path.exists():
            _require_frozen_gate(paths, state, jobs, allow_no_evaluation=True)
        collection_complete = any(
            job.job_kind == "collection"
            and _job_state(state, job.job_id).get("state") == "COMPLETE"
            for job in jobs
        )
        if verify_results and collection_complete:
            from .reporting import validate_published_completion

            validate_published_completion(paths, state=state, jobs=jobs)
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    payload = {
        "schema_version": "h2-product-program-validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        "errors": errors,
        "workspace": str(paths.workspace),
        "results_verified": verify_results,
    }
    if paths.workspace.exists():
        write_json_atomic(paths.workspace / "validation.json", payload)
    return payload


def plan(paths: ProgramPaths | None = None) -> dict[str, object]:
    paths = paths or default_paths()
    protocol = (
        read_json(paths.protocol_path)
        if paths.protocol_path.is_file()
        else build_protocol_manifest(paths)
    )
    manifest = (
        read_json(paths.jobs_path)
        if paths.jobs_path.is_file()
        else build_job_manifest(protocol)
    )
    jobs = _manifest_jobs(manifest)
    expected_jobs = [job for job in jobs if not job.optional]
    for phase in (1, 2):
        phase_optional = [
            job for job in jobs if job.phase_index == phase and job.optional
        ]
        expected_jobs.extend(
            sorted(
                (
                    job
                    for job in phase_optional
                    if job.configuration_id.endswith("_MEDIUM")
                ),
                key=lambda job: job.job_id,
            )[:4]
        )
        expected_jobs.extend(
            sorted(
                (
                    job
                    for job in phase_optional
                    if job.configuration_id.endswith("_FULL")
                ),
                key=lambda job: job.job_id,
            )[:2]
        )
    phases: list[dict[str, object]] = []
    neural_execution_kinds = (
        RUNTIME_KINDS
        | DYNAMIC_RUNTIME_KINDS
        | {
            "long_session",
            "reliability",
            "onnx_parity",
        }
    )
    for phase in range(8):
        values = [job for job in jobs if job.phase_index == phase]
        phases.append(
            {
                "phase_index": phase,
                "phase_name": values[0].phase_name if values else None,
                "job_count": len(values),
                "runtime_job_count": sum(
                    job.job_kind in RUNTIME_KINDS for job in values
                ),
                "dynamic_or_special_execution_job_count": sum(
                    job.job_kind in neural_execution_kinds - RUNTIME_KINDS
                    for job in values
                ),
                "optional_job_count": sum(job.optional for job in values),
                "case_count": sum(
                    len(job.case_ids) for job in values if not job.optional
                ),
                "audio_duration_sec": sum(
                    job.audio_duration_sec for job in values if not job.optional
                ),
                "estimated_wall_hours": sum(
                    job.estimated_wall_hours for job in values if not job.optional
                ),
            }
        )
    nominal_hours = float(manifest["estimated_wall_hours_before_measured_smoke"])
    timing = _timing_estimate(paths, nominal_hours)
    expected_case_executions = sum(
        len(job.case_ids)
        for job in expected_jobs
        if job.job_kind in neural_execution_kinds
    )
    expected_case_units = sum(len(job.case_ids) for job in expected_jobs)
    expected_audio_hours = sum(job.audio_duration_sec for job in expected_jobs) / 3600.0
    integration_partition = (
        protocol.get("panels", {})
        .get("development", {})
        .get("integration_partition", {})
        if isinstance(protocol.get("panels"), Mapping)
        else {}
    )
    independent_sources = (
        int(integration_partition.get("independent_source_count") or 0)
        if isinstance(integration_partition, Mapping)
        else 0
    )
    integration_cases = (
        int(integration_partition.get("calibration_case_count") or 0)
        + int(integration_partition.get("selection_case_count") or 0)
        if isinstance(integration_partition, Mapping)
        else 0
    )
    return {
        "schema_version": "h2-product-program-plan.v1",
        "status": "PLANNED_NOT_RUN",
        "protocol_id": protocol["protocol_id"],
        "job_count": len(jobs),
        "estimated_wall_hours_before_measured_smoke": nominal_hours,
        "timing_estimate": timing,
        "expected_completion_at_utc": timing["expected_completion_at_utc"],
        "total_expected_audio_hours": round(expected_audio_hours, 3),
        "total_expected_inference_units": expected_case_executions,
        "inference_unit_definition": (
            "one fixed protocol case admitted to a neural runtime execution job"
        ),
        "total_planned_case_units_including_non_neural_replays": expected_case_units,
        "configuration_count": len({job.configuration_id for job in expected_jobs}),
        "predeclared_job_count": len(jobs),
        "cache_reuse_estimate": {
            "status": "PRELIMINARY_METADATA_BOUND",
            "all_development_integration_case_count": integration_cases,
            "independent_source_audio_count": independent_sources,
            "maximum_integration_decode_reuse_fraction": (
                round(1.0 - independent_sources / integration_cases, 4)
                if integration_cases
                else None
            ),
            "actual_hit_rate_claimed": False,
            "note": (
                "Potential decode reuse is metadata-derived; measured cache hits "
                "replace this estimate in Status."
            ),
        },
        "advisory_target_wall_hours": 192.0,
        "automatic_cutoff": False,
        "accuracy_parallel_jobs_max": 2,
        "effective_controller_parallel_jobs": 1,
        "resource_parallel_jobs": 1,
        "automatic_phase_transition": True,
        "phases": phases,
        "unimplemented_job_kinds_fail_closed": sorted(UNIMPLEMENTED_KINDS),
    }


def smoke(paths: ProgramPaths | None = None) -> dict[str, object]:
    """Run/reuse three real development cases solely for timing calibration."""

    paths = paths or default_paths()
    _require_launch_transition(paths)
    _require_c_drive(paths)
    _require_storage_reserve(paths)
    receipt_path = paths.workspace / "bounded_timing_smoke.json"
    if receipt_path.is_file():
        receipt = read_json(receipt_path)
        unsigned_receipt = dict(receipt)
        receipt_sha = unsigned_receipt.pop("receipt_sha256", None)
        if (
            receipt.get("status") != "COMPLETE"
            or receipt.get("actual_model_audio_inference") is not True
            or receipt_sha != canonical_sha256(unsigned_receipt)
        ):
            raise H2ProgramError("bounded timing smoke receipt is invalid")
        if receipt.get("runtime_implementation_identity_sha256") != (
            runtime_implementation_identity()["identity_sha256"]
        ):
            raise H2ProgramError(
                "bounded timing smoke belongs to another implementation"
            )
        return receipt
    protocol = build_protocol_manifest(paths)
    manifest = build_job_manifest(protocol)
    baseline = next(
        H2Job.from_jsonable(row)
        for row in manifest["jobs"]
        if isinstance(row, Mapping)
        and row.get("configuration_id") == "H2_BASELINE_REFERENCE"
    )
    from .execution import load_cases_for_job

    selected_case_ids = baseline.case_ids[:3]
    selected_rows = load_cases_for_job(
        replace(baseline, case_ids=selected_case_ids),
        open_evaluation=False,
    )
    audio_duration = sum(float(row.get("duration_sec") or 0.0) for row in selected_rows)
    smoke_identity = canonical_sha256(
        {
            "protocol_sha256": protocol["protocol_sha256"],
            "baseline_job_identity_sha256": baseline.identity_sha256,
            "case_ids": list(selected_case_ids),
            "runtime_implementation_identity": runtime_implementation_identity(),
        }
    )
    smoke_job = replace(
        baseline,
        job_id=f"h2smoke_{smoke_identity[:24]}",
        configuration_id=f"H2_BOUNDED_REAL_TIMING_SMOKE_{smoke_identity[:12]}",
        case_ids=selected_case_ids,
        audio_duration_sec=audio_duration,
        dependencies=(),
        optional=False,
        estimated_wall_hours=0.0,
    )
    smoke_paths = ProgramPaths(
        evaluation_root=paths.evaluation_root,
        workspace=(paths.workspace / "bounded_timing_smoke_queue").resolve(),
        results_root=(paths.results_root / "bounded_timing_smoke").resolve(),
        summary_root=paths.summary_root,
        config_path=paths.config_path,
    )
    queue_identity = canonical_sha256(
        {
            "schema_version": "h2-bounded-real-timing-smoke.v1",
            "smoke_job": smoke_job.to_jsonable(),
            "scientific_results": False,
        }
    )
    prepare_runtime_queue(
        smoke_paths,
        (smoke_job,),
        protocol=protocol,
        job_manifest_sha256=queue_identity,
        seed=int(load_and_validate_spec(paths.config_path)["seed"]),
    )
    stop_event = threading.Event()
    progress_lock = threading.Lock()
    started = time.monotonic()
    with HostRunLock(
        paths.workspace / STATE_LOCK_NAME,
        measurement_mode="h2_bounded_real_timing_smoke",
    ):
        result = run_runtime_job(
            smoke_paths,
            smoke_job,
            protocol=protocol,
            stop_event=stop_event,
            progress_lock=progress_lock,
            additional_execution_contract={
                "h2_bounded_real_timing_smoke": True,
                "scientific_campaign_result": False,
            },
            storage_reserve_callback=lambda: _require_storage_reserve(paths),
        )
    elapsed_sec = time.monotonic() - started
    if str(result.get("state")).casefold() != "complete":
        raise H2ProgramError(f"bounded real timing smoke failed: {result.get('error')}")
    result_root = Path(str(result["result_root"]))
    store = EvaluationStateStore(smoke_paths.workspace / RUNTIME_QUEUE_DATABASE)
    queued = next(
        row for row in store.list_jobs() if row.spec.job_id == smoke_job.job_id
    )
    validation = validate_result_tree(
        result_root, expected_reuse_identity=queued.spec.reuse_identity
    )
    if not validation.reusable:
        raise H2ProgramError("bounded real timing smoke result is not reusable")
    metrics = metric_vector_from_result(result_root)
    measured_rtf = metrics.get("total_rtf")
    if measured_rtf is None:
        measured_rtf = elapsed_sec / audio_duration
    nominal_hours = float(manifest["estimated_wall_hours_before_measured_smoke"])
    implied_baseline_rtf = (
        baseline.estimated_wall_hours * 3600.0 / baseline.audio_duration_sec
    )
    scale = float(measured_rtf) / implied_baseline_rtf
    expected_hours = nominal_hours * scale
    core = {
        "schema_version": "h2-bounded-real-timing-smoke-receipt.v1",
        "status": "COMPLETE",
        "actual_model_audio_inference": True,
        "scientific_campaign_result": False,
        "development_only": True,
        "evaluation_material_inspected": False,
        "case_count": len(selected_case_ids),
        "case_ids": list(selected_case_ids),
        "audio_duration_sec": audio_duration,
        "measured_wall_sec": elapsed_sec,
        "measured_total_rtf": measured_rtf,
        "cache_hits": result.get("cache_hits"),
        "result_root": str(result_root),
        "result_sha256": result.get("result_sha256"),
        "runtime_implementation_identity_sha256": runtime_implementation_identity()[
            "identity_sha256"
        ],
        "calibration_method": (
            "scale predeclared nominal work estimate by measured smoke RTF divided "
            "by the baseline panel's predeclared implied RTF"
        ),
        "nominal_hours_before_smoke": nominal_hours,
        "implied_baseline_rtf": implied_baseline_rtf,
        "timing_scale": scale,
        "low_hours": expected_hours * 0.65,
        "expected_hours": expected_hours,
        "high_hours": expected_hours * 1.75,
        "confidence": "LOW",
        "confidence_reason": (
            "Three real cases validate end-to-end throughput but do not cover all "
            "cache states, long sessions, or serial resource stages."
        ),
        "automatic_cutoff": False,
    }
    receipt = {**core, "receipt_sha256": canonical_sha256(core)}
    write_once_or_verify(receipt_path, receipt)
    return receipt


def _timing_estimate(paths: ProgramPaths, nominal_hours: float) -> dict[str, object]:
    smoke_path = paths.workspace / "bounded_timing_smoke.json"
    source = "preliminary_plan_without_measured_smoke"
    confidence = "LOW"
    low = nominal_hours * 0.75
    expected = nominal_hours
    high = nominal_hours * 1.50
    if smoke_path.is_file():
        measured = read_json(smoke_path)
        unsigned = dict(measured)
        receipt_sha = unsigned.pop("receipt_sha256", None)
        receipt_valid = receipt_sha == canonical_sha256(unsigned) and measured.get(
            "runtime_implementation_identity_sha256"
        ) == runtime_implementation_identity().get("identity_sha256")
        if (
            receipt_valid
            and measured.get("status") == "COMPLETE"
            and all(
                isinstance(measured.get(key), (int, float))
                for key in ("low_hours", "expected_hours", "high_hours")
            )
        ):
            low = float(measured["low_hours"])
            expected = float(measured["expected_hours"])
            high = float(measured["high_hours"])
            source = "checksum_bound_bounded_timing_smoke"
            confidence = str(measured.get("confidence") or "MEDIUM")
    now = datetime.now(timezone.utc)
    return {
        "source": source,
        "confidence": confidence,
        "bounded_smoke_measured": (
            smoke_path.is_file() and source == "checksum_bound_bounded_timing_smoke"
        ),
        "low_hours": round(low, 2),
        "expected_hours": round(expected, 2),
        "high_hours": round(high, 2),
        "low_completion_at_utc": (now + timedelta(hours=low)).isoformat(),
        "expected_completion_at_utc": (now + timedelta(hours=expected)).isoformat(),
        "high_completion_at_utc": (now + timedelta(hours=high)).isoformat(),
        "automatic_cutoff": False,
    }


def run(
    paths: ProgramPaths | None = None,
    *,
    maximum_jobs: int | None = None,
    retry_failed: bool = False,
) -> dict[str, object]:
    """Run/reuse jobs in order and automatically cross successful phases.

    The 192-hour target is reported but never enforced as a cutoff.  One job is
    scheduled at a time, which satisfies both the two-accuracy-job maximum and
    serial matched-resource methodology.
    """

    paths = paths or default_paths()
    _require_launch_transition(paths)
    if not paths.state_path.is_file():
        prepare(paths)
    validation = validate(paths, verify_results=False)
    if not validation["valid"]:
        raise H2ProgramError("H2 workspace validation failed before Run")
    protocol = read_json(paths.protocol_path)
    manifest = read_json(paths.jobs_path)
    jobs = _manifest_jobs(manifest)
    lock_path = paths.workspace / STATE_LOCK_NAME
    completed_this_invocation = 0
    stop_event = threading.Event()
    poller_shutdown = threading.Event()
    progress_lock = threading.Lock()

    with HostRunLock(lock_path, measurement_mode="h2_auto_serial"):
        state = read_json(paths.state_path)
        _recover_stopped_state(state, retry_failed=retry_failed)
        _archive_and_clear_stop(paths)
        stores = _execution_stores(paths)
        running_leases: list[str] = []
        for execution_store in stores:
            execution_store.clear_stop()
            execution_store.reclaim_expired_leases()
            running_leases.extend(
                row.spec.job_id
                for row in execution_store.list_jobs(states=("running",))
            )
        if running_leases:
            state["status"] = "BLOCKED"
            state["detail"] = (
                "A stale runtime lease has not expired; retry Run after the "
                f"120-second lease window: {running_leases[:3]}"
            )
            state["current_job_id"] = None
            state["updated_at_utc"] = _utc_now()
            write_json_atomic(paths.state_path, state)
            return status(paths)
        state["status"] = "RUNNING"
        state["action"] = "Run"
        state["detail"] = "Automatic H2 phase execution is active"
        state.setdefault("started_at_utc", _utc_now())
        state["updated_at_utc"] = _utc_now()
        write_json_atomic(paths.state_path, state)

        def poll_stop() -> None:
            while not poller_shutdown.wait(0.5):
                if paths.stop_path.is_file():
                    stop_event.set()
                    _request_all_queue_stops(paths)
                    return

        poller = threading.Thread(target=poll_stop, name="h2-stop-poller", daemon=True)
        poller.start()
        try:
            while True:
                state = read_json(paths.state_path)
                _apply_successive_halving(paths, state, jobs)
                _apply_phase1_axis_selections(paths, state, jobs)
                _record_completed_phase_milestones(paths, state, jobs)
                write_json_atomic(paths.state_path, state)
                if stop_event.is_set() or paths.stop_path.is_file():
                    state["status"] = "STOPPED"
                    state["detail"] = "Graceful stop honored at an atomic case boundary"
                    state["current_job_id"] = None
                    state["updated_at_utc"] = _utc_now()
                    write_json_atomic(paths.state_path, state)
                    break
                blocked = _first_failed_job(state, jobs)
                if blocked is not None:
                    state["status"] = "BLOCKED"
                    state["detail"] = (
                        f"Job {blocked.job_id} failed; inspect last_error and implement "
                        "or repair the handler before retrying"
                    )
                    state["current_job_id"] = None
                    state["updated_at_utc"] = _utc_now()
                    write_json_atomic(paths.state_path, state)
                    break
                job = _next_job(state, jobs)
                if job is None:
                    if _all_jobs_successful(state, jobs):
                        try:
                            from .reporting import finalize_program_completion

                            finalize_program_completion(
                                paths,
                                state=state,
                                jobs=jobs,
                            )
                        except Exception as exc:
                            collection_job = next(
                                value
                                for value in jobs
                                if value.job_kind == "collection"
                            )
                            collection_row = _job_state(state, collection_job.job_id)
                            collection_row["state"] = "FAILED"
                            collection_row["last_error"] = (
                                f"{type(exc).__name__}: {exc}"
                            )
                            collection_row["latest_activity"] = (
                                "final evidence/package revalidation failed"
                            )
                            collection_row["updated_at_utc"] = _utc_now()
                            state["status"] = "BLOCKED"
                            state["detail"] = (
                                "Final H2 evidence/package validation failed; "
                                "controller-only COMPLETE was rejected"
                            )
                        else:
                            state["status"] = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
                            state["detail"] = (
                                "All H2 evidence, final report, and compact ZIP "
                                "validated"
                            )
                            state["completed_at_utc"] = _utc_now()
                            _record_milestone(
                                paths,
                                state,
                                milestone_id=(
                                    "program-complete:"
                                    f"{state.get('job_manifest_sha256')}"
                                ),
                                kind="PROGRAM_COMPLETE",
                                detail=(
                                    "All planned H2 jobs, final report, and "
                                    "allowlisted compact collection validated."
                                ),
                            )
                    else:
                        state["status"] = "BLOCKED"
                        state["detail"] = (
                            "No runnable job; dependency or promotion gate is unresolved"
                        )
                    state["current_job_id"] = None
                    state["updated_at_utc"] = _utc_now()
                    write_json_atomic(paths.state_path, state)
                    break
                if (
                    maximum_jobs is not None
                    and completed_this_invocation >= maximum_jobs
                ):
                    state["status"] = "PAUSED"
                    state["detail"] = "Bounded Run invocation reached --maximum-jobs"
                    state["current_job_id"] = None
                    state["updated_at_utc"] = _utc_now()
                    write_json_atomic(paths.state_path, state)
                    break
                try:
                    _require_storage_reserve(paths)
                except Exception as exc:
                    state["status"] = "BLOCKED"
                    state["detail"] = f"{type(exc).__name__}: {exc}"
                    state["current_job_id"] = None
                    state["updated_at_utc"] = _utc_now()
                    write_json_atomic(paths.state_path, state)
                    break
                if job.split == "evaluation":
                    _require_frozen_gate(paths, state, jobs)
                _mark_job_running(state, job)
                write_json_atomic(paths.state_path, state)
                try:
                    result = _execute_job(
                        paths,
                        protocol,
                        state,
                        jobs,
                        job,
                        stop_event=stop_event,
                        progress_lock=progress_lock,
                    )
                except Exception as exc:
                    result = {
                        "state": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                _finish_job_state(state, job, result, stopped=stop_event.is_set())
                write_json_atomic(paths.state_path, state)
                completed_this_invocation += 1
        finally:
            poller_shutdown.set()
            poller.join(timeout=5.0)
    return status(paths)


def status(paths: ProgramPaths | None = None) -> dict[str, object]:
    paths = paths or default_paths()
    if not paths.state_path.is_file():
        return {
            "schema_version": "h2-product-program-status.v1",
            "status": "NOT_PREPARED",
            "workspace": str(paths.workspace),
            "next_action": "Prepare",
        }
    state = read_json(paths.state_path)
    manifest = read_json(paths.jobs_path)
    jobs = _manifest_jobs(manifest)
    reported_status = state.get("status")
    reported_detail = state.get("detail")
    if reported_status == "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM":
        try:
            from .reporting import validate_published_completion

            validate_published_completion(paths, state=state, jobs=jobs)
        except Exception as exc:
            reported_status = "BLOCKED_OTHER"
            reported_detail = (
                "Recorded completion failed current read-only package/evidence "
                f"validation: {type(exc).__name__}: {exc}"
            )
    queue_rows: dict[str, dict[str, object]] = {}
    queue_snapshot_error: str | None = None
    queue_snapshot_source = "LIVE"
    queue_snapshot_updated_at: str | None = None
    snapshot_path = paths.workspace / LAST_QUEUE_SNAPSHOT_FILE
    try:
        queue_rows = _live_status_queue_rows(paths, jobs)
        queue_snapshot_updated_at = _utc_now()
        write_json_atomic(
            snapshot_path,
            {
                "schema_version": "h2-status-queue-snapshot.v1",
                "updated_at_utc": queue_snapshot_updated_at,
                "rows": queue_rows,
            },
        )
    except Exception as exc:
        queue_snapshot_error = f"{type(exc).__name__}: {exc}"
        queue_snapshot_source = "UNAVAILABLE"
        if snapshot_path.is_file():
            try:
                previous = read_json(snapshot_path)
                raw_rows = previous.get("rows")
                if previous.get(
                    "schema_version"
                ) != "h2-status-queue-snapshot.v1" or not isinstance(raw_rows, Mapping):
                    raise H2ProgramError("last queue snapshot schema differs")
                queue_rows = {
                    str(job_id): dict(row)
                    for job_id, row in raw_rows.items()
                    if isinstance(row, Mapping)
                }
                queue_snapshot_source = "LAST_KNOWN"
                queue_snapshot_updated_at = (
                    str(previous.get("updated_at_utc") or "") or None
                )
            except Exception as snapshot_exc:
                queue_snapshot_error += (
                    "; last-known snapshot unavailable: "
                    f"{type(snapshot_exc).__name__}: {snapshot_exc}"
                )
    current_id = state.get("current_job_id")
    current_queue = queue_rows.get(current_id)
    jobs_by_id = {job.job_id: job for job in jobs}
    current_job = jobs_by_id.get(str(current_id)) if current_id else None
    current_state = (
        _job_state(state, current_job.job_id) if current_job is not None else {}
    )
    progress = _progress(state, jobs, queue_rows)
    storage = _storage_snapshot(paths)
    active_jobs = [
        job
        for job in jobs
        if _job_state(state, job.job_id).get("state") != "SUPERSEDED"
    ]
    total_cases = sum(len(job.case_ids) for job in active_jobs)
    completed_cases = 0
    total_audio_sec = sum(job.audio_duration_sec for job in active_jobs)
    completed_audio_sec = 0.0
    cache_hits = 0
    retries = 0
    for active_job in active_jobs:
        row = _job_state(state, active_job.job_id)
        queued = queue_rows.get(active_job.job_id)
        if row.get("state") == "COMPLETE":
            completed_cases += len(active_job.case_ids)
            completed_audio_sec += active_job.audio_duration_sec
        else:
            completed_cases += min(
                len(active_job.case_ids),
                int(
                    _queue_value(
                        queued,
                        "completed_cases",
                        row.get("completed_cases") or 0,
                    )
                    or 0
                ),
            )
            completed_audio_sec += min(
                active_job.audio_duration_sec,
                float(
                    _queue_value(
                        queued,
                        "completed_audio_sec",
                        row.get("completed_audio_sec") or 0.0,
                    )
                    or 0.0
                ),
            )
        cache_hits += int(
            _queue_value(queued, "cache_hits", row.get("cache_hits") or 0) or 0
        )
        retries += int(
            _queue_value(
                queued,
                "retry_count",
                row.get("retry_count")
                or max(0, int(row.get("attempt_count") or 0) - 1),
            )
            or 0
        )
    eta_hours = progress["eta_hours"]
    estimated_finish_utc = (
        (datetime.now(timezone.utc) + timedelta(hours=float(eta_hours)))
        .isoformat()
        .replace("+00:00", "Z")
        if eta_hours is not None
        else None
    )
    current_pipeline = current_job.pipeline_id if current_job is not None else None
    current_backend = _pipeline_backend_summary(current_pipeline)
    phase_rows = []
    for phase in range(8):
        values = [job for job in jobs if job.phase_index == phase]
        counts = Counter(
            str(_job_state(state, job.job_id).get("state")) for job in values
        )
        phase_rows.append(
            {
                "phase_index": phase,
                "phase_name": values[0].phase_name if values else None,
                "states": dict(sorted(counts.items())),
            }
        )
    return {
        "schema_version": "h2-product-program-status.v1",
        "status": reported_status,
        "detail": reported_detail,
        "protocol_id": state.get("protocol_id"),
        "current_phase_index": state.get("current_phase_index"),
        "current_phase_name": state.get("current_phase_name"),
        "current_job_id": current_id,
        "current_job_kind": current_job.job_kind if current_job else None,
        "current_pipeline_id": current_pipeline,
        "current_backend": current_backend,
        "current_mode": current_job.mode if current_job else None,
        "current_case_id": _queue_value(
            current_queue, "current_case_id", current_state.get("current_case_id")
        ),
        "current_activity": _queue_value(
            current_queue, "latest_activity", current_state.get("latest_activity")
        ),
        "current_completed_cases": _queue_value(
            current_queue,
            "completed_cases",
            current_state.get("completed_cases"),
        ),
        "current_planned_cases": _queue_spec_value(
            current_queue,
            "case_count",
            current_state.get("planned_cases")
            or (len(current_job.case_ids) if current_job else None),
        ),
        "current_completed_audio_sec": _queue_value(
            current_queue,
            "completed_audio_sec",
            current_state.get("completed_audio_sec"),
        ),
        "current_planned_audio_sec": _queue_spec_value(
            current_queue,
            "audio_duration_sec",
            current_state.get("planned_audio_sec")
            or (current_job.audio_duration_sec if current_job else None),
        ),
        "percent_complete": progress["percent_complete"],
        "progress_bar": _bar(float(progress["percent_complete"])),
        "eta_hours": eta_hours,
        "estimated_finish_utc": estimated_finish_utc,
        "elapsed_hours": progress["elapsed_hours"],
        "completed_jobs": progress["completed_jobs"],
        "total_jobs": progress["active_planned_jobs"],
        "active_planned_jobs": progress["active_planned_jobs"],
        "completed_cases": completed_cases,
        "total_cases": total_cases,
        "completed_audio_sec": round(completed_audio_sec, 6),
        "total_audio_sec": round(total_audio_sec, 6),
        "cache_hits": cache_hits,
        "model_instances": current_state.get("model_instances"),
        "embedding_calls": current_state.get("embedding_calls"),
        "rolling_rtf": _queue_value(
            current_queue, "rolling_rtf", current_state.get("rolling_rtf")
        ),
        "cpu_percent": _queue_value(
            current_queue, "cpu_percent", current_state.get("cpu_percent")
        ),
        "rss_mb": _queue_value(current_queue, "rss_mb", current_state.get("rss_mb")),
        "queue_depth": _queue_value(current_queue, "queue_depth", None),
        "failures": sum(
            _job_state(state, job.job_id).get("state") == "FAILED"
            for job in active_jobs
        ),
        "retries": retries,
        "latest_output": current_state.get("latest_output")
        or current_state.get("result_path"),
        "queue_snapshot_source": queue_snapshot_source,
        "queue_snapshot_stale": queue_snapshot_source == "LAST_KNOWN",
        "queue_snapshot_error": queue_snapshot_error,
        "queue_snapshot_updated_at_utc": queue_snapshot_updated_at,
        "storage": storage,
        "target_wall_hours": 192.0,
        "target_is_advisory_only": True,
        "automatic_cutoff": False,
        "automatic_phase_transition": True,
        "phase_progress": phase_rows,
        "latest_milestone": _latest_milestone(paths),
        "milestones_path": str(paths.workspace / MILESTONES_FILE),
        "updated_at_utc": state.get("updated_at_utc"),
    }


def _live_status_queue_rows(
    paths: ProgramPaths, jobs: Sequence[H2Job]
) -> dict[str, dict[str, object]]:
    """Read every ordinary, held-out, and dynamic queue without creating one."""

    database = paths.workspace / RUNTIME_QUEUE_DATABASE
    if not database.is_file():
        raise H2ProgramError(f"main runtime queue is missing: {database}")
    store = EvaluationStateStore(database)
    queue_rows = {row.spec.job_id: row.to_jsonable() for row in store.list_jobs()}
    heldout_manifest_path = paths.workspace / HELDOUT_EXECUTION_MANIFEST
    if paths.freeze_path.is_file() and heldout_manifest_path.is_file():
        heldout_database = _heldout_paths(paths).workspace / RUNTIME_QUEUE_DATABASE
        if not heldout_database.is_file():
            raise H2ProgramError(
                f"held-out runtime queue is missing: {heldout_database}"
            )
        heldout_store = EvaluationStateStore(heldout_database)
        execution_manifest = read_json(heldout_manifest_path)
        logical = execution_manifest.get("logical_to_execution")
        if not isinstance(logical, Mapping):
            raise H2ProgramError("held-out logical/execution mapping is missing")
        heldout_by_id = {
            row.spec.job_id: row.to_jsonable() for row in heldout_store.list_jobs()
        }
        for logical_id, execution_id in logical.items():
            if str(execution_id) not in heldout_by_id:
                raise H2ProgramError(
                    f"held-out execution queue row is missing: {execution_id}"
                )
            queue_rows[str(logical_id)] = heldout_by_id[str(execution_id)]
    for logical_job in jobs:
        if logical_job.job_kind not in DYNAMIC_RUNTIME_KINDS:
            continue
        dynamic = _dynamic_paths(paths, logical_job)
        dynamic_manifest_path = dynamic.workspace / "dynamic_execution.json"
        dynamic_database = dynamic.workspace / RUNTIME_QUEUE_DATABASE
        if not dynamic_manifest_path.is_file() and not dynamic_database.is_file():
            continue
        if not dynamic_manifest_path.is_file() or not dynamic_database.is_file():
            raise H2ProgramError(
                f"partial dynamic queue evidence for {logical_job.job_id}"
            )
        dynamic_manifest = read_json(dynamic_manifest_path)
        raw_execution = dynamic_manifest.get("execution_job")
        if not isinstance(raw_execution, Mapping):
            raise H2ProgramError(
                f"dynamic execution identity is missing: {logical_job.job_id}"
            )
        execution_id = H2Job.from_jsonable(raw_execution).job_id
        dynamic_rows = {
            row.spec.job_id: row.to_jsonable()
            for row in EvaluationStateStore(dynamic_database).list_jobs()
        }
        if execution_id not in dynamic_rows:
            raise H2ProgramError(f"dynamic queue row is missing: {logical_job.job_id}")
        queue_rows[logical_job.job_id] = dynamic_rows[execution_id]
    return queue_rows


def _queue_value(
    row: Mapping[str, object] | None,
    key: str,
    default: object = None,
) -> object:
    return row.get(key, default) if isinstance(row, Mapping) else default


def _queue_spec_value(
    row: Mapping[str, object] | None,
    key: str,
    default: object = None,
) -> object:
    if not isinstance(row, Mapping):
        return default
    spec = row.get("spec")
    return spec.get(key, default) if isinstance(spec, Mapping) else default


def _pipeline_backend_summary(pipeline_id: object) -> dict[str, object] | None:
    if pipeline_id not in {
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_dr_ir",
    }:
        return None
    return {
        "pipeline_id": pipeline_id,
        "asr": (
            "sherpa_giga"
            if pipeline_id == "fullpipe_v1_ag_dr_ir"
            else "sherpa_original"
        ),
        "segmentation": "pyannote_segmentation_3_0",
        "diarization_embedding": "redimnet2_b2_speaker_embedding",
        "identity_embedding": "redimnet2_b2_speaker_embedding",
    }


def stop(
    paths: ProgramPaths | None = None, *, reason: str = "operator_requested"
) -> dict[str, object]:
    paths = paths or default_paths()
    paths.workspace.mkdir(parents=True, exist_ok=True)
    request = {
        "schema_version": "h2-product-stop-request.v1",
        "requested_at_utc": _utc_now(),
        "reason": reason,
        "semantics": "finish_current_atomic_case_then_stop",
        "force_kill_requested": False,
    }
    write_json_atomic(paths.stop_path, request)
    _request_all_queue_stops(paths)
    return {
        "schema_version": "h2-product-stop-response.v1",
        "status": "STOP_REQUESTED",
        "request": request,
        "stop_file": str(paths.stop_path),
        "note": "A running case is allowed to finish; no inference process is killed.",
    }


def _execution_stores(paths: ProgramPaths) -> tuple[EvaluationStateStore, ...]:
    databases = [paths.workspace / RUNTIME_QUEUE_DATABASE]
    heldout = _heldout_paths(paths).workspace / RUNTIME_QUEUE_DATABASE
    if heldout.is_file():
        databases.append(heldout)
    dynamic_root = paths.workspace / "dynamic_queues"
    if dynamic_root.is_dir():
        databases.extend(sorted(dynamic_root.glob(f"*/{RUNTIME_QUEUE_DATABASE}")))
    return tuple(
        EvaluationStateStore(database) for database in databases if database.is_file()
    )


def _request_all_queue_stops(paths: ProgramPaths) -> None:
    for store in _execution_stores(paths):
        try:
            store.request_stop()
        except Exception:
            # Notification of a durable stop request must not be defeated by a
            # stale or not-yet-created auxiliary queue.
            continue


def analyze(paths: ProgramPaths | None = None) -> dict[str, object]:
    paths = paths or default_paths()
    state = read_json(paths.state_path)
    jobs = _manifest_jobs(read_json(paths.jobs_path))
    return _analyze(paths, state, jobs, require_complete=False)


def collect(paths: ProgramPaths | None = None) -> dict[str, object]:
    paths = paths or default_paths()
    state = read_json(paths.state_path)
    jobs = _manifest_jobs(read_json(paths.jobs_path))
    return _collect(paths, state, jobs, require_complete=False)


def export_portable(paths: ProgramPaths | None = None) -> dict[str, object]:
    paths = paths or default_paths()
    from app.h2_portability.cli import structural_self_test
    from app.h2_portability.controller_adapter import (
        validate_portability_result_artifacts,
    )
    from app.h2_portability.onnx_tooling import COMPONENTS, inspect_component
    from app.utils.paths import repository_root

    output = paths.summary_root / "portability"
    output.mkdir(parents=True, exist_ok=True)
    self_test = structural_self_test(require_linux_arm64=False)
    components = [
        inspect_component(component, repository=repository_root().path)
        for component in COMPONENTS
    ]
    receipts: list[dict[str, object]] = []
    job_states: list[str] = []
    if paths.state_path.is_file() and paths.jobs_path.is_file():
        state = read_json(paths.state_path)
        jobs = _manifest_jobs(read_json(paths.jobs_path))
        for job in jobs:
            if job.job_kind not in {"onnx_export", "onnx_parity", "linux_portability"}:
                continue
            row = _job_state(state, job.job_id)
            job_states.append(str(row.get("state")))
            result_path_value = row.get("result_path")
            result_path = Path(str(result_path_value)) if result_path_value else None
            result_value: dict[str, object] | None = None
            validation_error: str | None = None
            result_valid = False
            if result_path is not None and result_path.is_file():
                try:
                    result_value = read_json(result_path)
                    if sha256_file(result_path) != row.get("result_sha256"):
                        raise H2ProgramError("state/result checksum mismatch")
                    if (
                        result_value.get("status") != "COMPLETE"
                        or result_value.get("job_id") != job.job_id
                        or result_value.get("job_kind") != job.job_kind
                    ):
                        raise H2ProgramError("scheduled portability receipt differs")
                    validate_portability_result_artifacts(result_value)
                    result_valid = True
                except Exception as exc:
                    validation_error = f"{type(exc).__name__}: {exc}"
            receipts.append(
                {
                    "job_id": job.job_id,
                    "job_kind": job.job_kind,
                    "state": row.get("state"),
                    "result_path": result_path_value,
                    "result_exists": bool(result_path and result_path.is_file()),
                    "result_sha256": (
                        sha256_file(result_path)
                        if result_path is not None and result_path.is_file()
                        else None
                    ),
                    "state_result_sha256": row.get("result_sha256"),
                    "validated": result_valid,
                    "validation_error": validation_error,
                    "full_live_pipeline_parity_passed": (
                        result_value.get("full_live_pipeline_parity_passed")
                        if result_value is not None
                        else None
                    ),
                }
            )
    all_complete = bool(receipts) and all(
        row["state"] == "COMPLETE" and row["validated"] is True for row in receipts
    )
    any_started = any(
        value not in {"PENDING", "WAITING_PROMOTION"} for value in job_states
    )
    payload = {
        "schema_version": "h2-product-portable-export-status.v1",
        "status": (
            "COMPLETE_PORTABILITY_PREPARATION"
            if all_complete
            else "PARTIAL_PORTABILITY_PREPARATION" if any_started else "NOT_RUN"
        ),
        "self_test": self_test,
        "components": components,
        "scheduled_job_receipts": receipts,
        "legacy_dated_directory_scan_used": False,
        "onnx_export_performed": any(
            row["job_kind"] == "onnx_export"
            and row["state"] == "COMPLETE"
            and row["validated"] is True
            for row in receipts
        ),
        "arm64_hardware_validated": False,
        "scientific_parity_measured": any(
            row["job_kind"] == "onnx_parity"
            and row["state"] == "COMPLETE"
            and row["validated"] is True
            and row["full_live_pipeline_parity_passed"] is True
            for row in receipts
        ),
        "linux_arm64_classification": "PORT_REQUIRES_WORK",
        "direct_cli_help": [
            f"{sys.executable} -m app.h2_portability export --help",
            f"{sys.executable} -m app.h2_portability parity --help",
            f"{sys.executable} -m app.h2_portability arm64-diagnostic --help",
        ],
        "note": (
            "This action inventories immutable scheduled/measured evidence; it "
            "never replaces a PASS report with a structural placeholder and "
            "does not claim ARM64 hardware validation."
        ),
    }
    write_json_atomic(output / "portable_inspection.json", payload)
    return payload


def launch_demo(
    paths: ProgramPaths | None = None, *, dry_run: bool = False
) -> dict[str, object]:
    paths = paths or default_paths()
    command = [sys.executable, "-m", "app.full_pipeline_demo", "launch"]
    binding_path = (
        paths.summary_root / "frozen_configurations/h2_demo_runtime_binding.frozen.json"
    )
    binding_sha256: str | None = None
    configuration_status = "ENGINEERING_BASELINE_NOT_FINAL"
    if paths.freeze_path.is_file():
        freeze = read_json(paths.freeze_path)
        freeze_unsigned = dict(freeze)
        freeze_identity_sha256 = freeze_unsigned.pop("freeze_identity_sha256", None)
        if freeze_identity_sha256 != canonical_sha256(freeze_unsigned):
            raise H2ProgramError("demo launch refused an invalid frozen policy")
        if not binding_path.is_file():
            raise H2ProgramError(
                "frozen policy exists but the demo runtime binding is missing"
            )
        binding_sha256 = sha256_file(binding_path)
        binding = load_h2_demo_runtime_binding(
            binding_path,
            expected_sha256=binding_sha256,
        )
        if binding.lifecycle != "FROZEN":
            raise H2ProgramError("demo runtime binding is not frozen")
        binding_document = read_json(binding_path)
        provenance = binding_document.get("provenance")
        if (
            not isinstance(provenance, Mapping)
            or provenance.get("freeze_identity_sha256") != freeze_identity_sha256
            or binding.default_product_mode != freeze.get("default_product_mode")
        ):
            raise H2ProgramError("demo runtime binding belongs to another freeze")
        command.extend(
            (
                "--h2-runtime-config",
                str(binding_path),
                "--h2-runtime-config-sha256",
                binding_sha256,
            )
        )
        configuration_status = "FROZEN_SCIENTIFIC_CONFIGURATION"
    if dry_run:
        return {
            "schema_version": "h2-product-demo-launch.v1",
            "status": "DRY_RUN",
            "command": command,
            "working_directory": str(paths.evaluation_root),
            "configuration_status": configuration_status,
            "runtime_binding_path": (
                str(binding_path) if binding_sha256 is not None else None
            ),
            "runtime_binding_sha256": binding_sha256,
        }
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(paths.evaluation_root)
        if not existing
        else os.pathsep.join((str(paths.evaluation_root), existing))
    )
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        command,
        cwd=paths.evaluation_root,
        env=environment,
        creationflags=creationflags,
    )
    return {
        "schema_version": "h2-product-demo-launch.v1",
        "status": "LAUNCHED",
        "pid": process.pid,
        "command": command,
        "working_directory": str(paths.evaluation_root),
        "configuration_status": configuration_status,
        "runtime_binding_path": (
            str(binding_path) if binding_sha256 is not None else None
        ),
        "runtime_binding_sha256": binding_sha256,
    }


def _execute_job(
    paths: ProgramPaths,
    protocol: Mapping[str, object],
    state: dict[str, object],
    jobs: Sequence[H2Job],
    job: H2Job,
    *,
    stop_event: threading.Event,
    progress_lock: threading.Lock,
) -> dict[str, object]:
    if job.job_kind in RUNTIME_KINDS:
        if job.split == "evaluation":
            execution_job = _heldout_execution_job(paths, job.job_id)
            return run_runtime_job(
                _heldout_paths(paths),
                execution_job,
                protocol=protocol,
                stop_event=stop_event,
                progress_lock=progress_lock,
                storage_reserve_callback=lambda: _require_storage_reserve(paths),
                external_stop_path=paths.stop_path,
            )
        return run_runtime_job(
            paths,
            job,
            protocol=protocol,
            stop_event=stop_event,
            progress_lock=progress_lock,
            storage_reserve_callback=lambda: _require_storage_reserve(paths),
        )
    if job.job_kind in DYNAMIC_RUNTIME_KINDS:
        return _run_dynamic_runtime_job(
            paths,
            protocol,
            state,
            jobs,
            job,
            stop_event=stop_event,
            progress_lock=progress_lock,
        )
    if job.job_kind == "evidence_audit":
        return _handle_evidence_audit(paths, job)
    if job.job_kind == "freeze":
        return _handle_freeze(paths, state, jobs, job)
    if job.job_kind == "analysis":
        return _analyze(paths, state, jobs, require_complete=True)
    if job.job_kind == "collection":
        return _collect(paths, state, jobs, require_complete=True)
    if job.job_kind == "app_validation":
        return _handle_app_validation(
            paths,
            job,
            protocol=protocol,
            state=state,
            jobs=jobs,
        )
    from .science import SCIENCE_JOB_KINDS, execute_science_job

    if job.job_kind in SCIENCE_JOB_KINDS:
        return execute_science_job(paths, job, state, jobs)
    if job.job_kind in {"onnx_export", "onnx_parity", "linux_portability"}:
        from app.h2_portability.controller_adapter import execute_portability_job

        return execute_portability_job(paths, job, state, jobs)
    if job.job_kind in {
        "long_session",
        "long_session_evaluation",
        "reliability",
    }:
        from .reliability import execute_reliability_job

        selected = (
            _require_frozen_gate(paths, state, jobs)["selected_runtime"]
            if job.split == "evaluation"
            else _selected_runtime_configuration(paths, state, jobs)
        )
        state["selected_runtime_snapshot"] = selected
        selected_tuning = H2RuntimeTuning.from_mapping(
            {
                **dict(selected["runtime_tuning"]),
                "product_mode": job.mode,
            }
        )

        def reliability_progress(**values: object) -> None:
            with progress_lock:
                row = _job_state(state, job.job_id)
                row.update(
                    {
                        "current_case_id": values.get("current_item_id"),
                        "completed_cases": values.get("completed_items"),
                        "planned_cases": values.get("total_items"),
                        "completed_audio_sec": values.get("completed_audio_sec"),
                        "planned_audio_sec": values.get("total_audio_sec"),
                        "latest_activity": values.get("latest_activity"),
                        "rolling_rtf": values.get("rolling_rtf"),
                        "cpu_percent": values.get("cpu_percent"),
                        "rss_mb": values.get("rss_mb"),
                        "retry_count": values.get("retry_count"),
                        "latest_output": values.get("latest_output"),
                        "model_instances": values.get("model_instances"),
                        "embedding_calls": values.get("embedding_calls"),
                        "progress_updated_at_utc": values.get("updated_at_utc"),
                    }
                )
                state["updated_at_utc"] = _utc_now()
                write_json_atomic(paths.state_path, state)

        return execute_reliability_job(
            paths,
            job,
            protocol=protocol,
            runtime_tuning=selected_tuning,
            stop_event=stop_event,
            progress=reliability_progress,
            storage_reserve_callback=lambda: _require_storage_reserve(paths),
        )
    if job.job_kind in UNIMPLEMENTED_KINDS:
        return _blocked_job_result(
            paths,
            job,
            "No scientifically valid handler exists yet for this job kind; "
            "it was not run and is not complete.",
        )
    return _blocked_job_result(
        paths, job, f"Unknown H2 job kind {job.job_kind!r}; execution refused"
    )


def _run_dynamic_runtime_job(
    paths: ProgramPaths,
    protocol: Mapping[str, object],
    state: dict[str, object],
    jobs: Sequence[H2Job],
    logical_job: H2Job,
    *,
    stop_event: threading.Event,
    progress_lock: threading.Lock,
) -> dict[str, object]:
    """Run a logical post-selection slot with a new immutable execution ID."""

    if logical_job.job_kind == "post_promotion_integration":
        selected = _frontier_runtime_configuration(paths, state, jobs)
        stage = "post_promotion_integration"
    else:
        selected = _selected_runtime_configuration(paths, state, jobs)
        stage = "post_selection_final"
        state["selected_runtime_snapshot"] = selected
    base = H2RuntimeTuning.from_mapping(selected["runtime_tuning"])
    tuning_values = {**base.to_jsonable(), "product_mode": logical_job.mode}
    if logical_job.job_kind == "post_selection_paragraph_validation":
        tuning_values["paragraph_policy"] = logical_job.runtime_tuning[
            "paragraph_policy"
        ]
    tuning = H2RuntimeTuning.from_mapping(tuning_values)
    selection_sha = canonical_sha256(selected)
    emit_identity_score_diagnostics = (
        logical_job.job_kind == "post_promotion_integration"
    )
    seed = _dynamic_execution_seed(
        logical_job_identity_sha256=logical_job.identity_sha256,
        selection_sha256=selection_sha,
        runtime_tuning_identity_sha256=tuning.identity_sha256,
        runtime_implementation_identity_sha256=runtime_implementation_identity()[
            "identity_sha256"
        ],
        emit_identity_score_diagnostics=emit_identity_score_diagnostics,
    )
    execution_job = replace(
        logical_job,
        job_id=f"h2dyn_{seed[:24]}",
        job_kind=(
            "resource_runtime"
            if logical_job.job_kind == "post_selection_resource_runtime"
            else "runtime_accuracy"
        ),
        configuration_id=f"{logical_job.configuration_id}_SELECTED_{seed[:12]}",
        runtime_tuning=tuning.to_jsonable(),
        dependencies=(),
        optional=False,
    )
    validate_runtime_tuning(execution_job)
    dynamic_paths = _dynamic_paths(paths, logical_job)
    integration_partition: Mapping[str, object] | None = None
    if logical_job.job_kind == "post_promotion_integration":
        panels = protocol.get("panels")
        development = panels.get("development") if isinstance(panels, Mapping) else None
        raw_partition = (
            development.get("integration_partition")
            if isinstance(development, Mapping)
            else None
        )
        if not isinstance(raw_partition, Mapping):
            raise H2ProgramError("H2 post-promotion integration partition is missing")
        integration_partition = raw_partition
    core = {
        "schema_version": "h2-dynamic-development-execution.v1",
        "stage": stage,
        "logical_job_id": logical_job.job_id,
        "logical_job_identity_sha256": logical_job.identity_sha256,
        "execution_job": execution_job.to_jsonable(),
        "selection": selected,
        "selection_sha256": selection_sha,
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
        "runtime_implementation_identity_sha256": runtime_implementation_identity()[
            "identity_sha256"
        ],
        "split": "development",
        "evaluation_material_inspected": False,
        "emit_identity_score_diagnostics": emit_identity_score_diagnostics,
        "development_integration_assignment_sha256": (
            integration_partition.get("assignment_sha256")
            if integration_partition is not None
            else None
        ),
        "development_integration_independent_source_count": (
            integration_partition.get("independent_source_count")
            if integration_partition is not None
            else None
        ),
    }
    manifest = {**core, "dynamic_execution_sha256": canonical_sha256(core)}
    additional_contract: dict[str, object] = {
        "h2_dynamic_execution_sha256": manifest["dynamic_execution_sha256"],
        "h2_cumulative_selection_sha256": selection_sha,
        "emit_identity_score_diagnostics": emit_identity_score_diagnostics,
    }
    if logical_job.job_kind == "post_promotion_integration":
        if integration_partition is None:  # pragma: no cover - guarded above.
            raise H2ProgramError("H2 development integration partition is missing")
        additional_contract["h2_development_integration_partition"] = dict(
            integration_partition
        )
        core_partition = dict(integration_partition)
        assignment_sha = core_partition.pop("assignment_sha256", None)
        if assignment_sha != canonical_sha256(core_partition):
            raise H2ProgramError(
                "H2 post-promotion integration partition checksum differs"
            )
    write_once_or_verify(dynamic_paths.workspace / "dynamic_execution.json", manifest)
    spec = load_and_validate_spec(paths.config_path)
    prepare_runtime_queue(
        dynamic_paths,
        (execution_job,),
        protocol=protocol,
        job_manifest_sha256=str(manifest["dynamic_execution_sha256"]),
        seed=int(spec["seed"]),
    )
    result = run_runtime_job(
        dynamic_paths,
        execution_job,
        protocol=protocol,
        stop_event=stop_event,
        progress_lock=progress_lock,
        additional_execution_contract=additional_contract,
        storage_reserve_callback=lambda: _require_storage_reserve(paths),
        external_stop_path=paths.stop_path,
    )
    result = dict(result)
    result["logical_job_id"] = logical_job.job_id
    result["dynamic_execution_sha256"] = manifest["dynamic_execution_sha256"]
    result["runtime_tuning_identity_sha256"] = tuning.identity_sha256
    if (
        logical_job.job_kind == "post_promotion_integration"
        and result.get("state") == "complete"
    ):
        gate = _verify_post_promotion_interaction(
            paths,
            state,
            jobs,
            integration_result_root=Path(str(result["result_root"])),
            execution_manifest=manifest,
        )
        result["interaction_gate"] = gate
        result["interaction_gate_path"] = gate.get("path")
        result["interaction_gate_sha256"] = gate.get("sha256")
        if gate.get("status") != "PASS":
            result["state"] = "failed"
            result["error"] = "post-promotion combined tuning failed interaction gate"
    return result


def _dynamic_execution_seed(
    *,
    logical_job_identity_sha256: str,
    selection_sha256: str,
    runtime_tuning_identity_sha256: str,
    runtime_implementation_identity_sha256: str,
    emit_identity_score_diagnostics: bool,
) -> str:
    """Bind the private score-diagnostic switch into dynamic job identity."""

    if not isinstance(emit_identity_score_diagnostics, bool):
        raise TypeError("emit_identity_score_diagnostics must be boolean")
    return canonical_sha256(
        {
            "logical_job_identity_sha256": logical_job_identity_sha256,
            "selection_sha256": selection_sha256,
            "runtime_tuning_identity_sha256": runtime_tuning_identity_sha256,
            "runtime_implementation_identity_sha256": (
                runtime_implementation_identity_sha256
            ),
            "emit_identity_score_diagnostics": emit_identity_score_diagnostics,
        }
    )


def _verify_post_promotion_interaction(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    integration_result_root: Path,
    execution_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Require the combined phase-1/phase-2 winner to remain nondominated.

    Aggregate safety seconds are divided by each fixed panel's audio duration
    before comparison because the integration panel contains all 807
    development cases while successive-halving winners use the 180-case core.
    The gate uses no hidden composite and opens no evaluation material.
    """

    integration_job = next(
        job for job in jobs if job.configuration_id == "H2_POST_PROMOTION_INTEGRATION"
    )
    component_jobs = [
        candidate
        for candidate in (
            _best_promoted_full(paths, state, jobs, 1),
            _best_promoted_full(paths, state, jobs, 2),
        )
        if candidate is not None
    ]
    if len(component_jobs) != 2:
        raise H2ProgramError(
            "post-promotion interaction gate requires phase-1 and phase-2 winners"
        )
    raw_vectors = {
        integration_job.job_id: metric_vector_from_result(integration_result_root)
    }
    for component in component_jobs:
        raw_vectors[component.job_id] = metric_vector_from_result(
            paths.results_root / "jobs" / component.job_id / "result"
        )
    vectors = {
        integration_job.job_id: _normalised_interaction_vector(
            raw_vectors[integration_job.job_id], integration_job.audio_duration_sec
        )
    }
    for component in component_jobs:
        vectors[component.job_id] = _normalised_interaction_vector(
            raw_vectors[component.job_id], component.audio_duration_sec
        )
    safety_metrics = ("wrong_known_time_sec", "stranger_false_known_time_sec")
    missing_safety = [
        f"{job_id}:{metric_id}"
        for job_id, vector in vectors.items()
        for metric_id in safety_metrics
        if vector.get(metric_id) is None
    ]
    integration_vector = vectors[integration_job.job_id]
    safety_no_harm: dict[str, bool] = {}
    if not missing_safety:
        for metric_id in safety_metrics:
            ceiling = max(
                float(vectors[job.job_id][metric_id]) for job in component_jobs
            )
            safety_no_harm[metric_id] = float(integration_vector[metric_id]) <= ceiling
    dominance_rows: list[dict[str, object]] = []
    dominated = False
    directions = {
        metric_id: direction for metric_id, _view, direction in METRIC_PRIORITY
    }
    for component in component_jobs:
        component_vector = vectors[component.job_id]
        common = [
            metric_id
            for metric_id, _view, _direction in METRIC_PRIORITY
            if integration_vector.get(metric_id) is not None
            and component_vector.get(metric_id) is not None
        ]
        component_dominates = _vector_dominates(
            component_vector,
            integration_vector,
            common,
            directions=directions,
        )
        dominated = dominated or component_dominates
        dominance_rows.append(
            {
                "component_job_id": component.job_id,
                "common_metrics": common,
                "component_strictly_dominates_integration": component_dominates,
            }
        )
    passed = (
        not missing_safety
        and bool(safety_no_harm)
        and all(safety_no_harm.values())
        and not dominated
    )
    core = {
        "schema_version": "h2-post-promotion-interaction-gate.v1",
        "status": "PASS" if passed else "FAIL",
        "development_only": True,
        "evaluation_material_inspected": False,
        "weighted_composite_used": False,
        "integration_logical_job_id": integration_job.job_id,
        "dynamic_execution_sha256": execution_manifest.get("dynamic_execution_sha256"),
        "integration_case_count": len(integration_job.case_ids),
        "integration_audio_duration_sec": integration_job.audio_duration_sec,
        "integration_assignment_sha256": execution_manifest.get(
            "development_integration_assignment_sha256"
        ),
        "independent_source_count": execution_manifest.get(
            "development_integration_independent_source_count"
        ),
        "component_job_ids": [job.job_id for job in component_jobs],
        "raw_metric_vectors": raw_vectors,
        "comparison_metric_vectors": vectors,
        "aggregate_safety_time_normalisation": "metric_seconds_per_panel_audio_second",
        "missing_required_safety_metrics": missing_safety,
        "safety_no_additional_harm": safety_no_harm,
        "dominance_checks": dominance_rows,
        "gate_rule": (
            "required safety rates no worse than the worse component winner and "
            "combined tuning not strictly dominated on common declared metrics"
        ),
    }
    gate_path = (
        _dynamic_paths(paths, integration_job).workspace / "interaction_gate.json"
    )
    write_once_or_verify(gate_path, core)
    return {**core, "path": str(gate_path), "sha256": sha256_file(gate_path)}


def _normalised_interaction_vector(
    vector: Mapping[str, float | None], audio_duration_sec: float
) -> dict[str, float | None]:
    values = dict(vector)
    if audio_duration_sec <= 0:
        raise H2ProgramError("interaction comparison panel has no audio duration")
    for metric_id in ("wrong_known_time_sec", "stranger_false_known_time_sec"):
        value = values.get(metric_id)
        if value is not None:
            values[metric_id] = float(value) / float(audio_duration_sec)
    return values


def _vector_dominates(
    left: Mapping[str, float | None],
    right: Mapping[str, float | None],
    metric_ids: Sequence[str],
    *,
    directions: Mapping[str, str],
) -> bool:
    if not metric_ids:
        return False
    no_worse = True
    strictly_better = False
    for metric_id in metric_ids:
        left_value = float(left[metric_id])  # type: ignore[arg-type]
        right_value = float(right[metric_id])  # type: ignore[arg-type]
        if directions[metric_id] == "max":
            left_value, right_value = -left_value, -right_value
        if left_value > right_value:
            no_worse = False
            break
        strictly_better = strictly_better or left_value < right_value
    return no_worse and strictly_better


def _dynamic_paths(paths: ProgramPaths, logical_job: H2Job) -> ProgramPaths:
    portable = "".join(
        character if character.isalnum() else "_" for character in logical_job.job_id
    )[:80]
    return ProgramPaths(
        evaluation_root=paths.evaluation_root,
        workspace=(paths.workspace / "dynamic_queues" / portable).resolve(),
        results_root=paths.results_root,
        summary_root=paths.summary_root,
        config_path=paths.config_path,
    )


def _validate_dynamic_execution(
    paths: ProgramPaths,
    logical_job: H2Job,
    logical_state: Mapping[str, object],
    *,
    protocol: Mapping[str, object],
    seed: int,
    verify_result: bool,
) -> list[str]:
    """Validate a post-selection queue against a freshly built full spec."""

    errors: list[str] = []
    dynamic = _dynamic_paths(paths, logical_job)
    manifest_path = dynamic.workspace / "dynamic_execution.json"
    if not manifest_path.is_file():
        return [f"dynamic execution manifest is missing: {logical_job.job_id}"]
    try:
        manifest = read_json(manifest_path)
        unsigned = dict(manifest)
        digest = unsigned.pop("dynamic_execution_sha256", None)
        if digest != canonical_sha256(unsigned):
            errors.append(f"dynamic manifest checksum differs: {logical_job.job_id}")
        if manifest.get("logical_job_id") != logical_job.job_id:
            errors.append(f"dynamic logical job mapping differs: {logical_job.job_id}")
        if manifest.get("logical_job_identity_sha256") != logical_job.identity_sha256:
            errors.append(f"dynamic logical identity differs: {logical_job.job_id}")
        if manifest.get("evaluation_material_inspected") is not False:
            errors.append(
                f"dynamic job crossed held-out firewall: {logical_job.job_id}"
            )
        selection = manifest.get("selection")
        if not isinstance(selection, Mapping) or manifest.get(
            "selection_sha256"
        ) != canonical_sha256(selection):
            errors.append(f"dynamic selection checksum differs: {logical_job.job_id}")
        implementation = runtime_implementation_identity()
        if manifest.get("runtime_implementation_identity_sha256") != implementation.get(
            "identity_sha256"
        ):
            errors.append(
                f"dynamic implementation identity differs: {logical_job.job_id}"
            )
        raw_execution = manifest.get("execution_job")
        if not isinstance(raw_execution, Mapping):
            raise H2ProgramError("dynamic execution job is missing")
        execution_job = H2Job.from_jsonable(raw_execution)
        tuning = validate_runtime_tuning(execution_job)
        if execution_job.case_ids != logical_job.case_ids:
            errors.append(f"dynamic case membership differs: {logical_job.job_id}")
        if (
            execution_job.split != logical_job.split
            or execution_job.pipeline_id != logical_job.pipeline_id
            or execution_job.mode != logical_job.mode
        ):
            errors.append(f"dynamic fixed dimensions differ: {logical_job.job_id}")
        if manifest.get("runtime_tuning_identity_sha256") != tuning.identity_sha256:
            errors.append(f"dynamic tuning identity differs: {logical_job.job_id}")
        database = dynamic.workspace / RUNTIME_QUEUE_DATABASE
        store = EvaluationStateStore(database)
        store.assert_integrity()
        queued = {row.spec.job_id: row for row in store.list_jobs()}
        expected = {
            spec.job_id: spec.to_jsonable()
            for spec in build_runtime_specs(
                (execution_job,), protocol=protocol, seed=seed
            )
        }
        actual = {job_id: row.spec.to_jsonable() for job_id, row in queued.items()}
        if actual != expected:
            errors.append(f"dynamic queue specification differs: {logical_job.job_id}")
        queue_manifest = dynamic.workspace / "campaign_manifest.json"
        metadata = store.metadata()
        if not queue_manifest.is_file() or metadata.get(
            "manifest_sha256"
        ) != sha256_file(queue_manifest):
            errors.append(
                f"dynamic queue manifest binding differs: {logical_job.job_id}"
            )
        if metadata.get("campaign_id") != protocol.get("protocol_id"):
            errors.append(
                f"dynamic queue protocol binding differs: {logical_job.job_id}"
            )
        if verify_result and logical_state.get("state") == "COMPLETE":
            queued_row = queued.get(execution_job.job_id)
            if queued_row is None:
                errors.append(
                    f"dynamic result queue row is absent: {logical_job.job_id}"
                )
            else:
                report = validate_result_tree(
                    dynamic.results_root / queued_row.spec.result_relative_path,
                    expected_reuse_identity=queued_row.spec.reuse_identity,
                )
                if not report.reusable:
                    errors.append(
                        f"dynamic result is not reusable: {logical_job.job_id}"
                    )
                if queued_row.result_sha256 != logical_state.get("result_sha256"):
                    errors.append(
                        f"dynamic result checksum differs: {logical_job.job_id}"
                    )
            if logical_job.job_kind == "post_promotion_integration":
                gate_path_value = logical_state.get("interaction_gate_path")
                gate_sha = logical_state.get("interaction_gate_sha256")
                if not gate_path_value:
                    errors.append("post-promotion integration gate is missing")
                else:
                    gate_path = Path(str(gate_path_value))
                    if not gate_path.is_file() or sha256_file(gate_path) != gate_sha:
                        errors.append(
                            "post-promotion interaction gate checksum differs"
                        )
                    elif read_json(gate_path).get("status") != "PASS":
                        errors.append("post-promotion interaction gate did not pass")
    except Exception as exc:
        errors.append(
            f"dynamic validation failed for {logical_job.job_id}: "
            f"{type(exc).__name__}: {exc}"
        )
    return errors


def _handle_evidence_audit(paths: ProgramPaths, job: H2Job) -> dict[str, object]:
    protocol = build_protocol_manifest(paths)
    spec = load_and_validate_spec(paths.config_path)
    historical = read_yaml(HISTORICAL_EVIDENCE_PATH)
    expected: dict[str, tuple[Path, str | None]] = {
        "h2_config": (paths.config_path, str(protocol["config_sha256"])),
        "pipeline_matrix": (
            Path(str(protocol["matrix_path"])),
            str(protocol["matrix_sha256"]),
        ),
        "runtime_config": (
            Path(str(protocol["runtime_path"])),
            str(protocol["runtime_sha256"]),
        ),
        "historical_evidence": (
            HISTORICAL_EVIDENCE_PATH,
            str(protocol["historical_evidence_sha256"]),
        ),
        "prepared_protocol_summary": (
            PREPARED_PROTOCOL_ROOT / "protocol_summary.json",
            str(protocol["prepared_protocol_summary_sha256"]),
        ),
        "prepared_development_cases": (
            PREPARED_PROTOCOL_ROOT / "development/case_manifest.jsonl",
            None,
        ),
        "prepared_evaluation_cases": (
            PREPARED_PROTOCOL_ROOT / "evaluation/case_manifest.jsonl",
            None,
        ),
        "prior_program_state": (
            paths.evaluation_root / "runs/full_pipeline_program/PROGRAM_STATE.json",
            None,
        ),
        "program_handoff": (
            paths.evaluation_root / "docs/full_pipeline/PROGRAM_HANDOFF.md",
            None,
        ),
        "prior_campaign_state": (
            paths.evaluation_root
            / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1/program_state.json",
            None,
        ),
        "prior_campaign_stop": (
            paths.evaluation_root
            / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1/stop_request.json",
            None,
        ),
        "prior_campaign_milestones": (
            paths.evaluation_root
            / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1/milestones.jsonl",
            None,
        ),
        "prior_campaign_queue": (
            paths.evaluation_root
            / "automated_runs/full_pipeline_development_prompt4_reduced_8day_v1_orchestrated"
            / "development_accuracy/campaign.sqlite3",
            None,
        ),
    }
    expected.update(
        {
            artifact_id: (path, None)
            for artifact_id, path in _superseded_h2_evidence(
                spec, paths.evaluation_root
            ).items()
        }
    )

    def collect_historical(value: object, prefix: str) -> None:
        if isinstance(value, Mapping):
            raw_path = value.get("path")
            raw_sha = value.get("sha256")
            if isinstance(raw_path, str) and isinstance(raw_sha, str):
                candidate = Path(raw_path)
                if not candidate.is_absolute():
                    candidate = paths.evaluation_root / candidate
                expected[f"historical:{prefix}"] = (candidate, raw_sha)
            for key, child in value.items():
                collect_historical(child, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect_historical(child, f"{prefix}[{index}]")

    collect_historical(historical, "")
    rows: list[dict[str, object]] = []
    for artifact_id, (path, expected_sha) in sorted(expected.items()):
        resolved = path.resolve()
        exists = resolved.is_file()
        actual_sha = sha256_file(resolved) if exists else None
        rows.append(
            {
                "artifact_id": artifact_id,
                "path": str(resolved),
                "exists": exists,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "hash_matches": (
                    exists and (expected_sha is None or actual_sha == expected_sha)
                ),
                "size_bytes": resolved.stat().st_size if exists else None,
            }
        )
    failures = [
        row
        for row in rows
        if row["exists"] is not True or row["hash_matches"] is not True
    ]
    complete = not failures
    payload = {
        "schema_version": "h2-baseline-evidence-audit.v1",
        "status": "COMPLETE" if complete else "FAILED",
        "job_id": job.job_id,
        "evidence": rows,
        "required_artifact_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "prior_evidence_modified": False,
        "neural_inference_performed": False,
        "scientific_metrics_recomputed": False,
    }
    result_path = _nonruntime_result_path(paths, job)
    write_json_atomic(result_path, payload)
    return {
        "state": "complete" if complete else "failed",
        "error": (
            None
            if complete
            else "required immutable baseline evidence is missing or hash-mismatched"
        ),
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
    }


def _select_development_default_mode(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    """Select the product default from matched development-mode evidence only."""

    candidates = tuple(
        job for job in jobs if job.job_kind == "post_selection_mode_validation"
    )
    by_mode = {job.mode: job for job in candidates}
    if (
        len(candidates) != len(H2_MODES)
        or set(by_mode) != set(H2_MODES)
        or any(
            job.split != "development" or job.development_only is not True
            for job in candidates
        )
    ):
        raise H2ProgramError(
            "default-mode selection requires exactly one development-only result "
            "for each H2 product mode"
        )
    reference = candidates[0]
    if any(
        job.case_ids != reference.case_ids
        or job.audio_duration_sec != reference.audio_duration_sec
        for job in candidates[1:]
    ):
        raise H2ProgramError("default-mode selection evidence is not matched")

    rows: list[dict[str, object]] = []
    vectors: dict[str, dict[str, float | None]] = {}
    for mode in H2_MODES:
        mode_job = by_mode[mode]
        state_row = _job_state(state, mode_job.job_id)
        if state_row.get("state") != "COMPLETE":
            raise H2ProgramError(
                f"default-mode development result is incomplete: {mode_job.job_id}"
            )
        result_root = Path(str(state_row.get("result_path") or "")).resolve()
        if result_root.is_file():
            result_root = result_root.parent
        checksum_path = result_root / "checksums.json"
        if not checksum_path.is_file() or sha256_file(checksum_path) != state_row.get(
            "result_sha256"
        ):
            raise H2ProgramError(
                f"default-mode development result checksum differs: {mode_job.job_id}"
            )
        validation = validate_result_tree(result_root)
        if not validation.reusable:
            raise H2ProgramError(
                f"default-mode development result is invalid: {mode_job.job_id}"
            )
        vector = metric_vector_from_result(result_root)
        vectors[mode] = vector
        rows.append(
            {
                "mode": mode,
                "job_id": mode_job.job_id,
                "job_identity_sha256": mode_job.identity_sha256,
                "result_root": str(result_root),
                "result_sha256": state_row.get("result_sha256"),
                "metrics": vector,
                "missing_metrics": sorted(
                    metric_id for metric_id, value in vector.items() if value is None
                ),
            }
        )
    common_metrics = tuple(
        metric_id
        for metric_id, _view, _direction in METRIC_PRIORITY
        if all(vectors[mode].get(metric_id) is not None for mode in H2_MODES)
    )
    if not REQUIRED_SAFETY_METRICS.issubset(common_metrics):
        raise H2ProgramError(
            "default-mode selection lacks common development safety metrics"
        )
    directions = {
        metric_id: direction for metric_id, _view, direction in METRIC_PRIORITY
    }
    tie_preference = (
        "H2_SESSION_MEMORY_ENHANCED",
        "H2_SESSION_ANONYMOUS",
        "H2_KNOWN_ONLY",
    )
    tie_rank = {mode: index for index, mode in enumerate(tie_preference)}

    def selection_key(mode: str) -> tuple[float | int, ...]:
        values: list[float | int] = []
        for metric_id in common_metrics:
            raw = vectors[mode][metric_id]
            if raw is None:  # pragma: no cover - common-metric guard above.
                raise H2ProgramError("default-mode common metric is missing")
            number = float(raw)
            values.append(number if directions[metric_id] == "min" else -number)
        values.append(tie_rank[mode])
        return tuple(values)

    selected_mode = min(H2_MODES, key=selection_key)
    unsigned = {
        "schema_version": "h2-development-default-mode-selection.v1",
        "status": "COMPLETE",
        "development_only": True,
        "evaluation_material_inspected": False,
        "weighted_composite_used": False,
        "method": "declared-priority lexicographic selection on matched development results",
        "required_safety_metrics": sorted(REQUIRED_SAFETY_METRICS),
        "common_metric_priority": list(common_metrics),
        "tie_preference": list(tie_preference),
        "matched_case_ids_sha256": canonical_sha256(list(reference.case_ids)),
        "matched_case_count": len(reference.case_ids),
        "matched_audio_duration_sec": reference.audio_duration_sec,
        "selected_default_mode": selected_mode,
        "candidates": rows,
    }
    return {
        **unsigned,
        "selection_identity_sha256": canonical_sha256(unsigned),
    }


def _demo_binding_configurations(
    selected_runtime: Mapping[str, object],
    *,
    source_result_sha256: str,
    freeze_identity_sha256: str | None = None,
) -> list[dict[str, object]]:
    raw_tuning = selected_runtime.get("runtime_tuning")
    if not isinstance(raw_tuning, Mapping):
        raise H2ProgramError("selected runtime tuning is missing for demo binding")
    configurations: list[dict[str, object]] = []
    for pipeline_id in (
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_dr_ir",
    ):
        for mode in H2_MODES:
            tuning = H2RuntimeTuning.from_mapping(
                {**dict(raw_tuning), "product_mode": mode}
            )
            row: dict[str, object] = {
                "configuration_id": f"{pipeline_id}:{mode}",
                "pipeline_id": pipeline_id,
                "mode": mode,
                "runtime_tuning": tuning.to_jsonable(),
                "runtime_tuning_identity_sha256": tuning.identity_sha256,
                "source_result_sha256": source_result_sha256,
            }
            if freeze_identity_sha256 is not None:
                row["freeze_identity_sha256"] = freeze_identity_sha256
            configurations.append(row)
    return configurations


def _handle_app_validation(
    paths: ProgramPaths,
    job: H2Job,
    *,
    protocol: Mapping[str, object],
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    """Run the exact current model-free common-application acceptance set."""

    default_mode_selection = _select_development_default_mode(paths, state, jobs)
    selected_runtime = _selected_runtime_configuration(paths, state, jobs)

    test_paths = sorted(
        {
            value
            for capability in APP_VALIDATION_CAPABILITIES.values()
            for value in capability["test_paths"]
        }
    )
    source_paths = sorted(
        {
            value
            for capability in APP_VALIDATION_CAPABILITIES.values()
            for value in capability["source_paths"]
        }
    )
    all_paths = tuple(test_paths + source_paths)
    missing = [
        value for value in all_paths if not (paths.evaluation_root / value).is_file()
    ]
    result_path = _nonruntime_result_path(paths, job)
    binding_path = result_path.parent / "h2_demo_runtime_binding.development.json"
    binding_payload = build_h2_demo_runtime_binding_payload(
        lifecycle="DEVELOPMENT_SELECTED",
        default_product_mode=str(default_mode_selection["selected_default_mode"]),
        configurations=_demo_binding_configurations(
            selected_runtime,
            source_result_sha256=str(
                default_mode_selection["selection_identity_sha256"]
            ),
        ),
        provenance={
            "development_default_mode_selection_sha256": (
                default_mode_selection["selection_identity_sha256"]
            ),
            "selected_runtime_tuning_identity_sha256": selected_runtime[
                "runtime_tuning_identity_sha256"
            ],
            "evaluation_material_inspected": False,
        },
    )
    write_json_atomic(binding_path, binding_payload)
    binding_file_sha256 = sha256_file(binding_path)
    binding = load_h2_demo_runtime_binding(
        binding_path,
        expected_sha256=binding_file_sha256,
    )
    resolved_binding_nodes = [
        {
            "pipeline_id": pipeline_id,
            "mode": mode,
            "runtime_tuning_identity_sha256": binding.select(
                pipeline_id, mode
            ).runtime_tuning_identity_sha256,
        }
        for pipeline_id in (
            "fullpipe_v1_ag_dr_ir",
            "fullpipe_v1_ao_dr_ir",
        )
        for mode in H2_MODES
    ]
    pycache_root = result_path.parent / "pycache"
    environment = dict(os.environ)
    environment["PYTHONPYCACHEPREFIX"] = str(pycache_root)
    commands = (
        (
            "python_compile",
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                *source_paths,
                *test_paths,
            ],
        ),
        (
            "ruff_check",
            [sys.executable, "-m", "ruff", "check", *source_paths, *test_paths],
        ),
        (
            "targeted_pytest",
            [sys.executable, "-m", "pytest", *test_paths, "-q"],
        ),
    )
    outcomes: list[dict[str, object]] = []
    if not missing:
        for command_id, command in commands:
            started = time.monotonic()
            try:
                completed = _run_app_validation_command(
                    command,
                    cwd=paths.evaluation_root,
                    env=environment,
                )
                outcomes.append(
                    {
                        "command_id": command_id,
                        "command": command,
                        "returncode": completed.returncode,
                        "elapsed_sec": time.monotonic() - started,
                        "stdout_tail": completed.stdout[-12000:],
                        "stderr_tail": completed.stderr[-12000:],
                    }
                )
            except Exception as exc:
                outcomes.append(
                    {
                        "command_id": command_id,
                        "command": command,
                        "returncode": None,
                        "elapsed_sec": time.monotonic() - started,
                        "stdout_tail": "",
                        "stderr_tail": f"{type(exc).__name__}: {exc}",
                    }
                )
    pytest_outcome = next(
        (row for row in outcomes if row["command_id"] == "targeted_pytest"),
        None,
    )
    pytest_text = (
        str(pytest_outcome.get("stdout_tail") or "")
        if isinstance(pytest_outcome, Mapping)
        else ""
    )
    passed_matches = re.findall(r"(?<!\d)(\d+)\s+passed", pytest_text)
    passed_count = int(passed_matches[-1]) if passed_matches else 0
    return_codes = {str(row["command_id"]): row.get("returncode") for row in outcomes}
    complete = (
        not missing
        and return_codes.get("python_compile") == 0
        and return_codes.get("ruff_check") == 0
        and return_codes.get("targeted_pytest") == 0
        and passed_count >= 1
        and binding.lifecycle == "DEVELOPMENT_SELECTED"
        and binding.default_product_mode
        == default_mode_selection["selected_default_mode"]
        and len(resolved_binding_nodes) == 6
    )
    test_hashes = {
        value: sha256_file(paths.evaluation_root / value)
        for value in test_paths
        if (paths.evaluation_root / value).is_file()
    }
    source_hashes = {
        value: sha256_file(paths.evaluation_root / value)
        for value in source_paths
        if (paths.evaluation_root / value).is_file()
    }
    capabilities = {
        capability_id: {
            "status": "PASS" if complete else "FAIL",
            "test_paths": list(definition["test_paths"]),
            "source_paths": list(definition["source_paths"]),
        }
        for capability_id, definition in APP_VALIDATION_CAPABILITIES.items()
    }
    payload = {
        "schema_version": "h2-app-validation-result.v1",
        "status": "COMPLETE" if complete else "FAILED",
        "job_id": job.job_id,
        "job_identity_sha256": job.identity_sha256,
        "protocol_id": protocol.get("protocol_id"),
        "protocol_sha256": protocol.get("protocol_sha256"),
        "runtime_implementation_identity_sha256": (
            runtime_implementation_identity()["identity_sha256"]
        ),
        "handler_source_path": "app/h2_product_program/controller.py",
        "handler_source_sha256": sha256_file(Path(__file__)),
        "model_free": True,
        "neural_inference_performed": False,
        "physical_microphone_performance_claimed": False,
        "controlled_or_mocked_device_behavior_only": True,
        "missing_paths": missing,
        "validation": {
            "status": "PASS" if complete else "FAIL",
            "passed_count": passed_count,
            "failed_count": 0 if complete else 1,
            "python_compile_passed": return_codes.get("python_compile") == 0,
            "ruff_check_passed": return_codes.get("ruff_check") == 0,
        },
        "test_hashes": test_hashes,
        "source_hashes": source_hashes,
        "capabilities": capabilities,
        "development_default_mode_selection": default_mode_selection,
        "scientific_runtime_binding": {
            "status": "PASS" if complete else "FAIL",
            "path": str(binding_path),
            "file_sha256": binding_file_sha256,
            "binding_identity_sha256": binding.binding_identity_sha256,
            "lifecycle": binding.lifecycle,
            "default_product_mode": binding.default_product_mode,
            "resolved_nodes": resolved_binding_nodes,
        },
        "commands": outcomes,
    }
    write_json_atomic(result_path, payload)
    return {
        "state": "complete" if complete else "failed",
        "error": None if complete else "current common-app validation failed",
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
        "completed_cases": 0,
        "completed_audio_sec": 0.0,
        "cache_hits": 0,
    }


def _run_app_validation_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=dict(env),
        capture_output=True,
        text=True,
        check=False,
        timeout=900.0,
    )


def _validate_app_validation_result(
    paths: ProgramPaths,
    job: H2Job,
    state_row: Mapping[str, object],
    *,
    protocol: Mapping[str, object],
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> list[str]:
    errors: list[str] = []
    try:
        result_path = Path(str(state_row.get("result_path") or "")).resolve(strict=True)
        payload = read_json(result_path)
        if payload.get("schema_version") != "h2-app-validation-result.v1":
            errors.append("app validation schema differs")
        if payload.get("status") != "COMPLETE":
            errors.append("app validation is not complete")
        if (
            payload.get("job_id") != job.job_id
            or payload.get("job_identity_sha256") != job.identity_sha256
        ):
            errors.append("app validation job binding differs")
        if payload.get("protocol_sha256") != protocol.get("protocol_sha256"):
            errors.append("app validation protocol binding differs")
        if (
            payload.get("runtime_implementation_identity_sha256")
            != runtime_implementation_identity()["identity_sha256"]
        ):
            errors.append("app validation runtime implementation changed")
        if payload.get("handler_source_sha256") != sha256_file(Path(__file__)):
            errors.append("app validation handler source changed")
        if (
            payload.get("model_free") is not True
            or payload.get("neural_inference_performed") is not False
            or payload.get("physical_microphone_performance_claimed") is not False
        ):
            errors.append("app validation scope/claim differs")
        validation = payload.get("validation")
        if not isinstance(validation, Mapping) or not (
            validation.get("status") == "PASS"
            and isinstance(validation.get("passed_count"), int)
            and int(validation["passed_count"]) >= 1
            and validation.get("failed_count") == 0
            and validation.get("python_compile_passed") is True
            and validation.get("ruff_check_passed") is True
        ):
            errors.append("app validation command result differs")
        test_hashes = payload.get("test_hashes")
        source_hashes = payload.get("source_hashes")
        if not isinstance(test_hashes, Mapping) or not isinstance(
            source_hashes, Mapping
        ):
            errors.append("app validation checksum maps are missing")
        else:
            expected_tests = {
                value
                for definition in APP_VALIDATION_CAPABILITIES.values()
                for value in definition["test_paths"]
            }
            expected_sources = {
                value
                for definition in APP_VALIDATION_CAPABILITIES.values()
                for value in definition["source_paths"]
            }
            if set(test_hashes) != expected_tests:
                errors.append("app validation test membership differs")
            if set(source_hashes) != expected_sources:
                errors.append("app validation source membership differs")
            for logical, expected_sha in {
                **dict(test_hashes),
                **dict(source_hashes),
            }.items():
                source = paths.evaluation_root / str(logical)
                if (
                    not source.is_file()
                    or not isinstance(expected_sha, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
                    or sha256_file(source) != expected_sha
                ):
                    errors.append(f"app validation current checksum differs: {logical}")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, Mapping) or set(capabilities) != set(
            APP_VALIDATION_CAPABILITIES
        ):
            errors.append("app validation capabilities differ")
        else:
            for capability_id, definition in APP_VALIDATION_CAPABILITIES.items():
                row = capabilities.get(capability_id)
                if not isinstance(row, Mapping) or (
                    row.get("status") != "PASS"
                    or row.get("test_paths") != list(definition["test_paths"])
                    or row.get("source_paths") != list(definition["source_paths"])
                ):
                    errors.append(f"app validation capability differs: {capability_id}")
        expected_selection = _select_development_default_mode(paths, state, jobs)
        if payload.get("development_default_mode_selection") != expected_selection:
            errors.append("app validation development default-mode selection differs")
        binding_row = payload.get("scientific_runtime_binding")
        if not isinstance(binding_row, Mapping):
            errors.append("app validation scientific runtime binding is missing")
        else:
            binding_path = Path(str(binding_row.get("path") or ""))
            binding_sha = str(binding_row.get("file_sha256") or "")
            if not binding_path.is_file() or sha256_file(binding_path) != binding_sha:
                errors.append(
                    "app validation scientific runtime binding checksum differs"
                )
            else:
                binding = load_h2_demo_runtime_binding(
                    binding_path,
                    expected_sha256=binding_sha,
                )
                expected_runtime = _selected_runtime_configuration(paths, state, jobs)
                expected_nodes = [
                    {
                        "pipeline_id": pipeline_id,
                        "mode": mode,
                        "runtime_tuning_identity_sha256": binding.select(
                            pipeline_id, mode
                        ).runtime_tuning_identity_sha256,
                    }
                    for pipeline_id in (
                        "fullpipe_v1_ag_dr_ir",
                        "fullpipe_v1_ao_dr_ir",
                    )
                    for mode in H2_MODES
                ]
                expected_configurations = _demo_binding_configurations(
                    expected_runtime,
                    source_result_sha256=str(
                        expected_selection["selection_identity_sha256"]
                    ),
                )
                expected_payload = build_h2_demo_runtime_binding_payload(
                    lifecycle="DEVELOPMENT_SELECTED",
                    default_product_mode=str(
                        expected_selection["selected_default_mode"]
                    ),
                    configurations=expected_configurations,
                    provenance={
                        "development_default_mode_selection_sha256": (
                            expected_selection["selection_identity_sha256"]
                        ),
                        "selected_runtime_tuning_identity_sha256": expected_runtime[
                            "runtime_tuning_identity_sha256"
                        ],
                        "evaluation_material_inspected": False,
                    },
                )
                if read_json(binding_path) != expected_payload:
                    errors.append("app validation scientific runtime payload differs")
                if (
                    binding_row.get("status") != "PASS"
                    or binding_row.get("binding_identity_sha256")
                    != binding.binding_identity_sha256
                    or binding_row.get("lifecycle") != "DEVELOPMENT_SELECTED"
                    or binding_row.get("default_product_mode")
                    != expected_selection["selected_default_mode"]
                    or binding_row.get("resolved_nodes") != expected_nodes
                ):
                    errors.append(
                        "app validation scientific runtime resolution differs"
                    )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    return errors


def _handle_freeze(
    paths: ProgramPaths,
    state: dict[str, object],
    jobs: Sequence[H2Job],
    job: H2Job,
) -> dict[str, object]:
    integrity = validate(paths, verify_results=True)
    if integrity.get("valid") is not True:
        return _blocked_job_result(
            paths,
            job,
            "development integrity validation failed before freeze: "
            + "; ".join(map(str, integrity.get("errors") or ()))[:1200],
        )
    development = [
        candidate for candidate in jobs if candidate.phase_index in range(1, 7)
    ]
    incomplete = [
        candidate.job_id
        for candidate in development
        if _job_state(state, candidate.job_id).get("state") not in SUCCESS_STATES
    ]
    if incomplete:
        return _blocked_job_result(
            paths, job, f"development is not complete: {incomplete[:5]}"
        )
    result_identities = {
        candidate.job_id: _job_state(state, candidate.job_id).get("result_sha256")
        for candidate in development
        if _job_state(state, candidate.job_id).get("state") == "COMPLETE"
    }
    if any(not value for value in result_identities.values()):
        return _blocked_job_result(paths, job, "development result identity is missing")
    selected = _selected_runtime_configuration(paths, state, jobs)
    _verify_final_selected_execution_tuning(paths, state, jobs, selected)
    default_mode_selection = _select_development_default_mode(paths, state, jobs)
    app_jobs = [
        candidate for candidate in jobs if candidate.job_kind == "app_validation"
    ]
    if len(app_jobs) != 1:
        return _blocked_job_result(paths, job, "freeze requires one app validation job")
    app_state = _job_state(state, app_jobs[0].job_id)
    app_validation_sha256 = str(app_state.get("result_sha256") or "")
    if app_state.get("state") != "COMPLETE" or not re.fullmatch(
        r"[0-9a-f]{64}", app_validation_sha256
    ):
        return _blocked_job_result(
            paths, job, "freeze requires checksum-bound app validation"
        )
    implementation = read_json(paths.workspace / RUNTIME_IMPLEMENTATION_IDENTITY)
    if implementation != runtime_implementation_identity():
        return _blocked_job_result(
            paths,
            job,
            "result-affecting runtime code/environment changed before freeze",
        )
    unsigned = {
        "schema_version": "h2-frozen-development-policy.v1",
        "protocol_id": state["protocol_id"],
        "protocol_sha256": state["protocol_sha256"],
        "job_manifest_sha256": state["job_manifest_sha256"],
        "selection_uses_development_only": True,
        "evaluation_material_inspected": False,
        "evaluation_recalibration_allowed": False,
        "development_results": dict(sorted(result_identities.items())),
        "runtime_implementation_identity": implementation,
        "runtime_implementation_identity_sha256": implementation["identity_sha256"],
        "selected_runtime": selected,
        "default_product_mode_selection": default_mode_selection,
        "default_product_mode": default_mode_selection["selected_default_mode"],
        "app_validation_result_sha256": app_validation_sha256,
        "product_modes": list(H2_MODES),
    }
    payload = {**unsigned, "freeze_identity_sha256": canonical_sha256(unsigned)}
    write_once_or_verify(paths.freeze_path, payload)
    frozen_root = paths.summary_root / "frozen_configurations"
    for mode in payload["product_modes"]:
        tuning = dict(selected["runtime_tuning"])
        tuning["product_mode"] = mode
        strict = H2RuntimeTuning.from_mapping(tuning)
        config = {
            "schema_version": "h2-frozen-product-configuration.v1",
            "mode": mode,
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "freeze_identity_sha256": payload["freeze_identity_sha256"],
            "runtime_tuning": strict.to_jsonable(),
            "runtime_tuning_identity_sha256": strict.identity_sha256,
        }
        write_once_or_verify(frozen_root / f"{mode}.json", config)
    demo_binding_path = frozen_root / "h2_demo_runtime_binding.frozen.json"
    demo_binding_payload = build_h2_demo_runtime_binding_payload(
        lifecycle="FROZEN",
        default_product_mode=str(payload["default_product_mode"]),
        configurations=_demo_binding_configurations(
            selected,
            source_result_sha256=str(
                default_mode_selection["selection_identity_sha256"]
            ),
            freeze_identity_sha256=str(payload["freeze_identity_sha256"]),
        ),
        validation_identity_sha256=app_validation_sha256,
        provenance={
            "freeze_identity_sha256": payload["freeze_identity_sha256"],
            "development_default_mode_selection_sha256": (
                default_mode_selection["selection_identity_sha256"]
            ),
            "app_validation_result_sha256": app_validation_sha256,
            "evaluation_material_inspected": False,
        },
    )
    write_once_or_verify(demo_binding_path, demo_binding_payload)
    demo_binding_file_sha256 = sha256_file(demo_binding_path)
    verified_demo_binding = load_h2_demo_runtime_binding(
        demo_binding_path,
        expected_sha256=demo_binding_file_sha256,
    )
    for pipeline_id in ("fullpipe_v1_ag_dr_ir", "fullpipe_v1_ao_dr_ir"):
        for mode in H2_MODES:
            verified_demo_binding.select(pipeline_id, mode)
    _prepare_heldout_execution_queue(paths, jobs, payload)
    _record_milestone(
        paths,
        state,
        milestone_id=f"development-freeze:{payload['freeze_identity_sha256']}",
        kind="DEVELOPMENT_FREEZE_COMPLETE",
        detail="Development policy and executable H2 runtime tuning are frozen.",
        extra={
            "freeze_identity_sha256": payload["freeze_identity_sha256"],
            "default_product_mode": payload["default_product_mode"],
        },
    )
    _record_milestone(
        paths,
        state,
        milestone_id=f"heldout-open:{payload['freeze_identity_sha256']}",
        kind="HELDOUT_OPENED",
        detail="Frozen held-out queue is prepared and may now run automatically.",
        extra={"freeze_identity_sha256": payload["freeze_identity_sha256"]},
    )
    result_path = _nonruntime_result_path(paths, job)
    write_json_atomic(
        result_path,
        {
            "schema_version": "h2-freeze-job-result.v1",
            "status": "COMPLETE",
            "freeze_path": str(paths.freeze_path),
            "freeze_identity_sha256": payload["freeze_identity_sha256"],
            "default_product_mode": payload["default_product_mode"],
            "default_mode_selection_sha256": default_mode_selection[
                "selection_identity_sha256"
            ],
            "demo_runtime_binding_path": str(demo_binding_path),
            "demo_runtime_binding_file_sha256": demo_binding_file_sha256,
            "demo_runtime_binding_identity_sha256": (
                verified_demo_binding.binding_identity_sha256
            ),
        },
    )
    return {
        "state": "complete",
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
        "freeze_identity_sha256": payload["freeze_identity_sha256"],
    }


def _verify_final_selected_execution_tuning(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    selected: Mapping[str, object],
) -> None:
    raw_tuning = selected.get("runtime_tuning")
    if not isinstance(raw_tuning, Mapping):
        raise H2ProgramError("selected final runtime tuning is missing")
    for logical in jobs:
        if logical.job_kind not in {
            "post_selection_mode_validation",
            "post_selection_resource_runtime",
        }:
            continue
        if _job_state(state, logical.job_id).get("state") != "COMPLETE":
            raise H2ProgramError(
                f"final selected-tuning validation is incomplete: {logical.job_id}"
            )
        manifest = read_json(
            _dynamic_paths(paths, logical).workspace / "dynamic_execution.json"
        )
        raw_execution = manifest.get("execution_job")
        if not isinstance(raw_execution, Mapping):
            raise H2ProgramError(
                f"final selected-tuning execution is missing: {logical.job_id}"
            )
        execution = H2Job.from_jsonable(raw_execution)
        expected = H2RuntimeTuning.from_mapping(
            {**dict(raw_tuning), "product_mode": logical.mode}
        )
        actual = H2RuntimeTuning.from_mapping(execution.runtime_tuning)
        if actual.identity_sha256 != expected.identity_sha256:
            raise H2ProgramError(
                f"final validation measured stale tuning: {logical.job_id}"
            )


def _selected_runtime_configuration(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    frontier = _frontier_runtime_configuration(paths, state, jobs)
    tuning = dict(frontier["runtime_tuning"])
    selected_jobs = list(frontier["selected_job_ids"])
    axis_provenance = {
        str(key): dict(value)
        for key, value in frontier["selected_axis_provenance"].items()
    }
    integration = next(
        (
            job
            for job in jobs
            if job.configuration_id == "H2_POST_PROMOTION_INTEGRATION"
        ),
        None,
    )
    integration_identity: dict[str, object] | None = None
    enrollment_policy_binding: dict[str, object] | None = None
    if integration is not None:
        integration_state = _job_state(state, integration.job_id)
        if integration_state.get("state") != "COMPLETE":
            raise H2ProgramError(
                "final selection requires complete H2_POST_PROMOTION_INTEGRATION"
            )
        integration_identity = {
            "job_id": integration.job_id,
            "result_path": integration_state.get("result_path"),
            "result_sha256": integration_state.get("result_sha256"),
            "interaction_gate_path": integration_state.get("interaction_gate_path"),
            "interaction_gate_sha256": integration_state.get("interaction_gate_sha256"),
        }
        selected_jobs.append(integration.job_id)
    enrollment_jobs = [job for job in jobs if job.job_kind == "integrated_enrollment"]
    if len(enrollment_jobs) > 1:
        raise H2ProgramError("freeze has multiple integrated enrollment jobs")
    if enrollment_jobs:
        enrollment_policy_binding = _selected_enrollment_policy_binding(
            state, enrollment_jobs[0]
        )
        selected_jobs.append(enrollment_jobs[0].job_id)
    # Scientific replay handlers can select only their declared executable
    # axes.  Each result must prove development-only selection and is checksum
    # bound into the freeze.  Full tuning mappings are accepted only when the
    # explicit selected_runtime_axes list limits which values are consumed.
    for source_job in jobs:
        allowed = HANDLER_SELECTED_AXES.get(source_job.job_kind)
        if not allowed:
            continue
        row = _job_state(state, source_job.job_id)
        if row.get("state") != "COMPLETE":
            continue
        result_path_value = row.get("result_path")
        if not result_path_value:
            raise H2ProgramError(
                f"selected-axis handler result path is missing: {source_job.job_id}"
            )
        result_path = Path(str(result_path_value))
        if not result_path.is_file() or sha256_file(result_path) != row.get(
            "result_sha256"
        ):
            raise H2ProgramError(
                f"selected-axis handler checksum differs: {source_job.job_id}"
            )
        result = read_json(result_path)
        if result.get("development_only_selection") is not True:
            raise H2ProgramError(
                f"handler lacks development-only selection proof: {source_job.job_id}"
            )
        if result.get("evaluation_material_inspected") is not False:
            raise H2ProgramError(
                f"handler crossed the held-out firewall: {source_job.job_id}"
            )
        if (
            result.get("promotion_eligible") is not True
            or result.get("status") == "GATED_NOT_PROMOTED"
        ):
            selected_axes = result.get("selected_runtime_axes")
            if selected_axes not in ([], ()):
                raise H2ProgramError(
                    f"non-promoted handler selected runtime axes: {source_job.job_id}"
                )
            continue
        selected_tuning = result.get("selected_runtime_tuning")
        selected_axes = result.get("selected_runtime_axes")
        if not isinstance(selected_tuning, Mapping) or not isinstance(
            selected_axes, list
        ):
            raise H2ProgramError(
                f"handler lacks selected_runtime_tuning/axes: {source_job.job_id}"
            )
        axes = tuple(str(value) for value in selected_axes)
        if not axes or len(set(axes)) != len(axes):
            raise H2ProgramError(
                f"handler selected axes are empty/duplicate: {source_job.job_id}"
            )
        unexpected = set(axes) - allowed
        if unexpected:
            raise H2ProgramError(
                f"handler selected forbidden axes {sorted(unexpected)}: {source_job.job_id}"
            )
        missing = set(axes) - set(selected_tuning)
        if missing:
            raise H2ProgramError(
                f"handler selected tuning lacks axes {sorted(missing)}: {source_job.job_id}"
            )
        for axis in axes:
            prior = axis_provenance.get(axis)
            new_value = selected_tuning[axis]
            if prior is not None and tuning.get(axis) != new_value:
                raise H2ProgramError(
                    f"conflicting development selections for {axis}: "
                    f"{prior['job_id']} versus {source_job.job_id}"
                )
            tuning[axis] = new_value
            axis_provenance[axis] = {
                "job_id": source_job.job_id,
                "job_kind": source_job.job_kind,
                "selection_source": "checksum_bound_science_handler",
                "result_path": str(result_path),
                "result_sha256": row.get("result_sha256"),
            }
        selected_jobs.append(source_job.job_id)
    strict = H2RuntimeTuning.from_mapping(tuning)
    return {
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "selected_job_ids": selected_jobs,
        "runtime_tuning": strict.to_jsonable(),
        "runtime_tuning_identity_sha256": strict.identity_sha256,
        "selected_axis_provenance": dict(sorted(axis_provenance.items())),
        "calibration_integration_result": integration_identity,
        "enrollment_policy_binding": enrollment_policy_binding,
    }


def _selected_enrollment_policy_binding(
    state: Mapping[str, object], enrollment_job: H2Job
) -> dict[str, object]:
    """Validate and bind the development-only enrollment recommendation.

    The integrated cell is advisory unless a matched full-gallery policy
    calibration proves compatibility.  This study uses a separate 16-speaker
    gallery, so the exact historical H2 policy remains effective.
    """

    enrollment_state = _job_state(state, enrollment_job.job_id)
    result_path = Path(str(enrollment_state.get("result_path") or ""))
    if (
        enrollment_state.get("state") != "COMPLETE"
        or not result_path.is_file()
        or sha256_file(result_path) != enrollment_state.get("result_sha256")
    ):
        raise H2ProgramError("integrated enrollment result is incomplete or corrupt")
    result = read_json(result_path)
    selected = result.get("selected_enrollment_policy")
    if not isinstance(selected, Mapping):
        raise H2ProgramError("integrated enrollment lacks its selected cell")
    unsigned = dict(selected)
    policy_sha = str(unsigned.pop("policy_provenance_sha256", ""))
    if policy_sha != canonical_sha256(unsigned):
        raise H2ProgramError("selected enrollment policy provenance differs")
    if (
        selected.get("selection_label") != "INTEGRATED_SELECTED_CELL"
        or selected.get("selection_uses_development_only") is not True
        or selected.get("evaluation_material_inspected") is not False
        or selected.get("live_identity_threshold_altered_by_handler") is not False
    ):
        raise H2ProgramError("selected enrollment policy crossed its science firewall")
    app_aggregation = {
        "normalized_mean": "normalized_mean",
        "frozen_redim_multi_template": "multi_template_max",
    }.get(str(selected.get("aggregation")))
    if app_aggregation is None:
        raise H2ProgramError("selected enrollment aggregation is not application-safe")
    if result.get("full_gallery_policy_compatibility_proven") is not False:
        raise H2ProgramError(
            "integrated enrollment made an unsupported full-gallery compatibility claim"
        )
    if result.get("integrated_recommendation_runtime_activation_eligible") is not False:
        raise H2ProgramError(
            "integrated enrollment recommendation is unexpectedly runtime-active"
        )
    historical = result.get("historical_evidence")
    if not isinstance(historical, Mapping):
        raise H2ProgramError("integrated enrollment lacks historical policy provenance")
    historical_path = Path(str(historical.get("frozen_policy_path") or ""))
    historical_sha = str(historical.get("frozen_policy_sha256") or "")
    if (
        not historical_path.is_file()
        or sha256_file(historical_path).casefold() != historical_sha.casefold()
    ):
        raise H2ProgramError("historical H2 enrollment policy checksum differs")
    effective = read_yaml(historical_path)
    if (
        int(effective.get("enrollment_utterance_count") or 0) != 3
        or float(effective.get("enrollment_total_target_sec") or 0.0) != 10.0
        or effective.get("aggregation_method") != "multi_template_max"
        or effective.get("identity_backend_id") != "redimnet2_b2_speaker_embedding"
    ):
        raise H2ProgramError("historical effective H2 enrollment policy differs")
    binding = {
        "schema_version": "h2-frozen-enrollment-policy-binding.v1",
        "activation_decision": "PRESERVE_HISTORICAL_POLICY_INTEGRATED_CELL_ADVISORY",
        "compatibility_proof": {
            "score_definition_compatibility_is_sufficient": False,
            "same_full_gallery_policy_calibration_present": False,
            "same_enrollment_distribution_present": False,
            "runtime_activation_eligible": False,
        },
        "effective_policy": {
            "source_policy_path": str(historical_path),
            "source_policy_sha256": historical_sha,
            "policy_id": effective.get("policy_id"),
            "backend_id": effective.get("identity_backend_id"),
            "utterance_count": effective.get("enrollment_utterance_count"),
            "total_target_sec": effective.get("enrollment_total_target_sec"),
            "clip_selection": effective.get("clip_selection"),
            "application_aggregation": effective.get("aggregation_method"),
            "quality_control_required": True,
        },
        "integrated_study_recommendation": {
            "source_job_id": enrollment_job.job_id,
            "source_result_path": str(result_path),
            "source_result_sha256": enrollment_state.get("result_sha256"),
            "policy_provenance_sha256": policy_sha,
            "panel_sha256": selected.get("panel_sha256"),
            "backend_id": selected.get("backend_id"),
            "backend_identity_hash": selected.get("backend_identity_hash"),
            "utterance_count": selected.get("utterances"),
            "total_target_sec": selected.get("total_duration_sec"),
            "session_condition": selected.get("sessions"),
            "study_aggregation": selected.get("aggregation"),
            "application_aggregation": app_aggregation,
            "quality_filter": selected.get("quality_filter"),
            "score_definition": selected.get("score_definition"),
            "study_score_threshold": selected.get("score_threshold"),
            "study_margin_threshold": selected.get("margin_threshold"),
            "runtime_activation_eligible": False,
        },
        "live_identity_threshold_altered": False,
    }
    return {**binding, "binding_sha256": canonical_sha256(binding)}


def _frontier_runtime_configuration(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    baseline_job = next(
        candidate
        for candidate in jobs
        if candidate.configuration_id == "H2_BASELINE_REFERENCE"
    )
    tuning = dict(baseline_job.runtime_tuning)
    selected_jobs: list[str] = [baseline_job.job_id]
    axis_provenance: dict[str, dict[str, object]] = {}
    phase1 = _best_promoted_full(paths, state, jobs, 1)
    if phase1 is not None:
        selected_jobs.append(phase1.job_id)
        for key in (
            "segmentation_hop_sec",
            "segmentation_onset",
            "segmentation_offset",
            "segmentation_min_speech_sec",
            "segmentation_min_silence_sec",
        ):
            tuning[key] = phase1.runtime_tuning[key]
            axis_provenance[key] = {
                "job_id": phase1.job_id,
                "job_kind": phase1.job_kind,
                "selection_source": "successive_halving_development_result",
                "result_sha256": _job_state(state, phase1.job_id).get("result_sha256"),
            }
    phase2 = _best_promoted_full(paths, state, jobs, 2)
    if phase2 is not None:
        selected_jobs.append(phase2.job_id)
        for key in (
            "embedding_window_sec",
            "embedding_hop_sec",
            "minimum_embedding_sec",
            "redim_execution_strategy",
            "clustering_threshold",
            "short_turn_attach_gap_sec",
        ):
            tuning[key] = phase2.runtime_tuning[key]
            axis_provenance[key] = {
                "job_id": phase2.job_id,
                "job_kind": phase2.job_kind,
                "selection_source": "successive_halving_development_result",
                "result_sha256": _job_state(state, phase2.job_id).get("result_sha256"),
            }
    axis_selections = state.get("axis_selections")
    for decision_key, axis, configurations in (
        (
            "boundary_correction",
            "boundary_correction_ms",
            {
                job.configuration_id
                for job in jobs
                if job.configuration_id.startswith("BOUNDARY_CORRECTION_")
            },
        ),
        (
            "overlap_policy",
            "overlap_policy",
            {
                "INCLUDE_PREDICTED_OVERLAP",
                "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
            }
            & {job.configuration_id for job in jobs},
        ),
    ):
        if not configurations:
            continue
        if not isinstance(axis_selections, Mapping):
            raise H2ProgramError("phase-1 boundary/overlap selections are missing")
        decision = _validated_promotion_decision(
            paths,
            state,
            collection="axis_selections",
            key=decision_key,
        )
        chosen = decision.get("selected_candidates")
        if not isinstance(chosen, list) or len(chosen) != 1:
            raise H2ProgramError(f"development selection is invalid: {decision_key}")
        chosen_id = str(chosen[0])
        selected_job = next(
            (job for job in jobs if job.configuration_id == chosen_id), None
        )
        if (
            selected_job is None
            or _job_state(state, selected_job.job_id).get("state") != "COMPLETE"
        ):
            raise H2ProgramError(f"selected development job is incomplete: {chosen_id}")
        tuning[axis] = selected_job.runtime_tuning[axis]
        selected_jobs.append(selected_job.job_id)
        axis_provenance[axis] = {
            "job_id": selected_job.job_id,
            "job_kind": selected_job.job_kind,
            "selection_source": "phase1_development_pareto",
            "result_sha256": _job_state(state, selected_job.job_id).get(
                "result_sha256"
            ),
            "decision_sha256": decision.get("decision_sha256"),
        }
    strict = H2RuntimeTuning.from_mapping(tuning)
    return {
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "selected_job_ids": selected_jobs,
        "runtime_tuning": strict.to_jsonable(),
        "runtime_tuning_identity_sha256": strict.identity_sha256,
        "selected_axis_provenance": dict(sorted(axis_provenance.items())),
    }


def _prepare_heldout_execution_queue(
    paths: ProgramPaths,
    jobs: Sequence[H2Job],
    freeze: Mapping[str, object],
) -> dict[str, object]:
    """Materialize immutable post-freeze held-out execution identities.

    The pre-freeze manifest fixes case membership, modes, and pipelines.  It
    intentionally does not pretend its historical baseline tuning is the
    development winner.  This overlay creates new queue job IDs whose reuse
    identities include the freeze checksum and selected strict tuning.
    """

    selected = freeze.get("selected_runtime")
    if not isinstance(selected, Mapping) or not isinstance(
        selected.get("runtime_tuning"), Mapping
    ):
        raise H2ProgramError("freeze lacks selected runtime tuning")
    base = H2RuntimeTuning.from_mapping(selected["runtime_tuning"])
    evaluation_jobs = [
        job
        for job in jobs
        if job.split == "evaluation" and job.job_kind in RUNTIME_KINDS
    ]
    execution_jobs: list[H2Job] = []
    logical_to_execution: dict[str, str] = {}
    for logical in evaluation_jobs:
        mode_tuning = H2RuntimeTuning.from_mapping(
            {**base.to_jsonable(), "product_mode": logical.mode}
        )
        identity_seed = canonical_sha256(
            {
                "freeze_identity_sha256": freeze["freeze_identity_sha256"],
                "logical_job_identity_sha256": logical.identity_sha256,
                "runtime_tuning_identity_sha256": mode_tuning.identity_sha256,
            }
        )
        # Keep attempt/result paths below conservative Windows path limits;
        # the manifest preserves the full logical-to-execution mapping.
        execution_id = f"h2eval_{identity_seed[:24]}"
        execution = replace(
            logical,
            job_id=execution_id,
            configuration_id=f"{logical.configuration_id}_FROZEN_{identity_seed[:12]}",
            runtime_tuning=mode_tuning.to_jsonable(),
            dependencies=(),
            optional=False,
        )
        validate_runtime_tuning(execution)
        execution_jobs.append(execution)
        logical_to_execution[logical.job_id] = execution.job_id
    core = {
        "schema_version": "h2-heldout-execution-manifest.v1",
        "protocol_id": freeze["protocol_id"],
        "protocol_sha256": freeze["protocol_sha256"],
        "job_manifest_sha256": freeze["job_manifest_sha256"],
        "freeze_identity_sha256": freeze["freeze_identity_sha256"],
        "runtime_implementation_identity_sha256": freeze[
            "runtime_implementation_identity_sha256"
        ],
        "evaluation_case_membership_changed": False,
        "evaluation_modes_changed": False,
        "evaluation_pipelines_changed": False,
        "selected_tuning_bound_after_development_freeze": True,
        "evaluation_material_inspected_to_construct_overlay": False,
        "logical_to_execution": logical_to_execution,
        "jobs": [job.to_jsonable() for job in execution_jobs],
    }
    manifest = {**core, "heldout_execution_sha256": canonical_sha256(core)}
    path = paths.workspace / HELDOUT_EXECUTION_MANIFEST
    write_once_or_verify(path, manifest)
    protocol = read_json(paths.protocol_path)
    spec = load_and_validate_spec(paths.config_path)
    queue = prepare_runtime_queue(
        _heldout_paths(paths),
        execution_jobs,
        protocol=protocol,
        job_manifest_sha256=str(manifest["heldout_execution_sha256"]),
        seed=int(spec["seed"]),
    )
    return {"manifest": manifest, "queue": queue}


def _heldout_execution_job(paths: ProgramPaths, logical_job_id: str) -> H2Job:
    manifest_path = paths.workspace / HELDOUT_EXECUTION_MANIFEST
    if not manifest_path.is_file():
        raise H2ProgramError("held-out execution overlay was not frozen")
    manifest = read_json(manifest_path)
    unsigned = dict(manifest)
    expected = unsigned.pop("heldout_execution_sha256", None)
    if expected != canonical_sha256(unsigned):
        raise H2ProgramError("held-out execution manifest checksum is invalid")
    mapping = manifest.get("logical_to_execution")
    if not isinstance(mapping, Mapping) or logical_job_id not in mapping:
        raise H2ProgramError(f"held-out logical job is absent: {logical_job_id}")
    execution_id = str(mapping[logical_job_id])
    values = manifest.get("jobs")
    if not isinstance(values, list):
        raise H2ProgramError("held-out execution jobs are missing")
    for value in values:
        if isinstance(value, Mapping):
            job = H2Job.from_jsonable(value)
            if job.job_id == execution_id:
                return job
    raise H2ProgramError(f"held-out execution job is absent: {execution_id}")


def _heldout_paths(paths: ProgramPaths) -> ProgramPaths:
    return ProgramPaths(
        evaluation_root=paths.evaluation_root,
        workspace=(paths.workspace / HELDOUT_QUEUE_DIRECTORY).resolve(),
        results_root=paths.results_root,
        summary_root=paths.summary_root,
        config_path=paths.config_path,
    )


def _analyze(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    require_complete: bool,
) -> dict[str, object]:
    try:
        from .reporting import execute_analysis
    except ImportError as exc:
        raise H2ProgramError(
            "The checksum-validating H2 reporting adapter is unavailable; "
            "analysis was not marked complete"
        ) from exc
    return execute_analysis(
        paths,
        state=state,
        jobs=jobs,
        require_complete=require_complete,
    )


def _collect(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    require_complete: bool,
) -> dict[str, object]:
    try:
        from .reporting import execute_collection
    except ImportError as exc:
        raise H2ProgramError(
            "The checksum-validating H2 reporting adapter is unavailable; "
            "collection was not marked complete"
        ) from exc
    return execute_collection(
        paths,
        state=state,
        jobs=jobs,
        require_complete=require_complete,
    )


def _blocked_job_result(
    paths: ProgramPaths, job: H2Job, reason: str
) -> dict[str, object]:
    result_path = _nonruntime_result_path(paths, job)
    payload = {
        "schema_version": "h2-job-blocked.v1",
        "status": "BLOCKED_UNIMPLEMENTED_OR_INCOMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "reason": reason,
        "scientific_work_performed": False,
        "marked_complete": False,
    }
    write_json_atomic(result_path, payload)
    return {
        "state": "failed",
        "error": reason,
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
    }


def _apply_successive_halving(
    paths: ProgramPaths, state: dict[str, object], jobs: Sequence[H2Job]
) -> None:
    for phase in (1, 2):
        phase_jobs = [job for job in jobs if job.phase_index == phase]
        for source_suffix, target_suffix, maximum in (
            ("_SMALL", "_MEDIUM", 4),
            ("_MEDIUM", "_FULL", 2),
        ):
            source = [
                job
                for job in phase_jobs
                if job.job_kind == "successive_halving_runtime"
                and job.configuration_id.endswith(source_suffix)
                and _job_state(state, job.job_id).get("state") != "SUPERSEDED"
            ]
            target = [
                job
                for job in phase_jobs
                if job.job_kind == "successive_halving_runtime"
                and job.configuration_id.endswith(target_suffix)
            ]
            if not source or not target:
                continue
            if not all(
                _job_state(state, job.job_id).get("state") == "COMPLETE"
                for job in source
            ):
                continue
            key = f"phase_{phase}_{target_suffix.removeprefix('_').casefold()}"
            promotions = state.setdefault("promotions", {})
            if not isinstance(promotions, dict):
                raise H2ProgramError("state promotions must be a mapping")
            if key in promotions:
                decision = _validated_promotion_decision(
                    paths,
                    state,
                    collection="promotions",
                    key=key,
                )
            else:
                decision = select_promotions(
                    source,
                    results_root=paths.results_root,
                    maximum=maximum,
                )
                decision_path = paths.workspace / "promotions" / f"{key}.json"
                write_once_or_verify(decision_path, decision)
                promotions[key] = {
                    **dict(decision),
                    "decision_path": str(decision_path),
                    "decision_sha256": sha256_file(decision_path),
                }
            selected = set(decision["selected_candidates"])
            for job in target:
                candidate = _candidate_base(job.configuration_id)
                row = _job_state(state, job.job_id)
                if candidate in selected:
                    if row.get("state") == "WAITING_PROMOTION":
                        row["state"] = "PENDING"
                        row["latest_activity"] = f"promoted by {key}"
                elif row.get("state") in {"WAITING_PROMOTION", "PENDING"}:
                    row["state"] = "SUPERSEDED"
                    row["latest_activity"] = f"not promoted by {key}"
                    row["completed_at_utc"] = _utc_now()


def _apply_phase1_axis_selections(
    paths: ProgramPaths, state: dict[str, object], jobs: Sequence[H2Job]
) -> None:
    """Select boundary correction and overlap on development before calibration."""

    groups = {
        "boundary_correction": [
            job
            for job in jobs
            if job.phase_index == 1
            and job.configuration_id.startswith("BOUNDARY_CORRECTION_")
        ],
        "overlap_policy": [
            job
            for job in jobs
            if job.phase_index == 1
            and job.configuration_id
            in {
                "INCLUDE_PREDICTED_OVERLAP",
                "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
            }
        ],
    }
    decisions = state.setdefault("axis_selections", {})
    if not isinstance(decisions, dict):
        raise H2ProgramError("state axis_selections must be a mapping")
    for key, candidates in groups.items():
        if key in decisions:
            _validated_promotion_decision(
                paths,
                state,
                collection="axis_selections",
                key=key,
            )
            continue
        if not candidates:
            continue
        if not all(
            _job_state(state, job.job_id).get("state") == "COMPLETE"
            for job in candidates
        ):
            continue
        decision = select_promotions(
            candidates,
            results_root=paths.results_root,
            maximum=1,
        )
        decision_path = paths.workspace / "axis_selections" / f"{key}.json"
        write_once_or_verify(decision_path, decision)
        decisions[key] = {
            **dict(decision),
            "decision_path": str(decision_path),
            "decision_sha256": sha256_file(decision_path),
        }


def _next_job(state: Mapping[str, object], jobs: Sequence[H2Job]) -> H2Job | None:
    for phase in range(8):
        earlier = [job for job in jobs if job.phase_index < phase]
        if any(
            _job_state(state, job.job_id).get("state") not in SUCCESS_STATES
            for job in earlier
        ):
            return None
        current = [job for job in jobs if job.phase_index == phase]
        for job in current:
            row = _job_state(state, job.job_id)
            if row.get("state") != "PENDING":
                continue
            if all(
                _job_state(state, dependency).get("state") in SUCCESS_STATES
                for dependency in job.dependencies
            ):
                return job
        if any(
            _job_state(state, job.job_id).get("state") not in SUCCESS_STATES
            for job in current
        ):
            return None
    return None


def _first_failed_job(
    state: Mapping[str, object], jobs: Sequence[H2Job]
) -> H2Job | None:
    for job in jobs:
        if _job_state(state, job.job_id).get("state") == "FAILED":
            return job
    return None


def _all_jobs_successful(state: Mapping[str, object], jobs: Sequence[H2Job]) -> bool:
    return all(
        _job_state(state, job.job_id).get("state") in SUCCESS_STATES for job in jobs
    )


def _mark_job_running(state: dict[str, object], job: H2Job) -> None:
    row = _job_state(state, job.job_id)
    row["state"] = "RUNNING"
    row["attempt_count"] = int(row.get("attempt_count") or 0) + 1
    row["started_at_utc"] = row.get("started_at_utc") or _utc_now()
    row["updated_at_utc"] = _utc_now()
    row["latest_activity"] = "job starting"
    row["last_error"] = None
    state["current_job_id"] = job.job_id
    state["current_phase_index"] = job.phase_index
    state["current_phase_name"] = job.phase_name
    state["detail"] = f"Running {job.configuration_id}"
    state["updated_at_utc"] = _utc_now()


def _finish_job_state(
    state: dict[str, object],
    job: H2Job,
    result: Mapping[str, object],
    *,
    stopped: bool,
) -> None:
    row = _job_state(state, job.job_id)
    outcome = str(result.get("state") or "failed").casefold()
    if outcome == "complete":
        final = "COMPLETE"
    elif stopped or outcome in {"stopped", "partial"}:
        final = "STOPPED"
    else:
        final = "FAILED"
    row["state"] = final
    row["completed_cases"] = int(result.get("completed_cases") or 0)
    row["completed_audio_sec"] = float(result.get("completed_audio_sec") or 0.0)
    row["cache_hits"] = int(result.get("cache_hits") or 0)
    row["result_sha256"] = result.get("result_sha256")
    row["result_path"] = result.get("result_path") or result.get("result_root")
    for key in (
        "dynamic_execution_sha256",
        "runtime_tuning_identity_sha256",
        "interaction_gate_path",
        "interaction_gate_sha256",
    ):
        if result.get(key) is not None:
            row[key] = result[key]
    row["last_error"] = result.get("error") if final != "COMPLETE" else None
    row["latest_activity"] = (
        "checksum-bound result complete" if final == "COMPLETE" else row["last_error"]
    )
    row["updated_at_utc"] = _utc_now()
    row["completed_at_utc"] = _utc_now() if final in TERMINAL_STATES else None
    if result.get("freeze_identity_sha256"):
        state["freeze_identity_sha256"] = result["freeze_identity_sha256"]
    state["current_job_id"] = None
    state["updated_at_utc"] = _utc_now()


def _initial_state(
    paths: ProgramPaths,
    protocol: Mapping[str, object],
    manifest: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    return {
        "schema_version": H2_PROGRAM_SCHEMA_VERSION,
        "program_id": str(protocol["program_id"]),
        "status": "PREPARED",
        "action": "Prepare",
        "detail": "Checksum-bound H2-only program is prepared; no long run started",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol["protocol_sha256"],
        "job_manifest_sha256": manifest["job_manifest_sha256"],
        "workspace": str(paths.workspace),
        "results_root": str(paths.results_root),
        "summary_root": str(paths.summary_root),
        "target_wall_hours": float(protocol["target_wall_hours"]),
        "target_is_advisory_only": bool(protocol["target_is_advisory_only"]),
        "automatic_time_cutoff": False,
        "current_phase_index": None,
        "current_phase_name": None,
        "current_job_id": None,
        "created_at_utc": _utc_now(),
        "updated_at_utc": _utc_now(),
        "promotions": {},
        "axis_selections": {},
        "milestone_ids": [],
        "latest_milestone": None,
        "jobs": {
            job.job_id: {
                "state": "WAITING_PROMOTION" if job.optional else "PENDING",
                "attempt_count": 0,
                "completed_cases": 0,
                "completed_audio_sec": 0.0,
                "cache_hits": 0,
                "latest_activity": (
                    "waiting for development promotion" if job.optional else "prepared"
                ),
                "last_error": None,
                "result_sha256": None,
                "result_path": None,
                "started_at_utc": None,
                "completed_at_utc": None,
                "updated_at_utc": _utc_now(),
            }
            for job in jobs
        },
    }


def _recover_stopped_state(state: dict[str, object], *, retry_failed: bool) -> None:
    jobs = state.get("jobs")
    if not isinstance(jobs, Mapping):
        raise H2ProgramError("program state lacks jobs")
    for row in jobs.values():
        if not isinstance(row, dict):
            raise H2ProgramError("program job state is invalid")
        if row.get("state") in {"STOPPED", "RUNNING"}:
            row["state"] = "PENDING"
            row["latest_activity"] = "restart-safe retry scheduled"
        elif retry_failed and row.get("state") == "FAILED":
            row["state"] = "PENDING"
            row["latest_activity"] = "explicit failed-job retry scheduled"
            row["last_error"] = None


def _archive_and_clear_stop(paths: ProgramPaths) -> None:
    if not paths.stop_path.is_file():
        return
    request = read_json(paths.stop_path)
    history_path = paths.workspace / "stop_history.jsonl"
    history: list[Mapping[str, object]] = []
    if history_path.is_file():
        history.extend(read_jsonl(history_path))
    history.append(request)
    write_jsonl_atomic(history_path, history)
    paths.stop_path.unlink(missing_ok=True)


def _record_completed_phase_milestones(
    paths: ProgramPaths, state: dict[str, object], jobs: Sequence[H2Job]
) -> None:
    for phase in range(8):
        phase_jobs = [job for job in jobs if job.phase_index == phase]
        if not phase_jobs or not all(
            _job_state(state, job.job_id).get("state") in SUCCESS_STATES
            for job in phase_jobs
        ):
            continue
        _record_milestone(
            paths,
            state,
            milestone_id=(f"phase-complete:{phase}:{state.get('job_manifest_sha256')}"),
            kind="PHASE_COMPLETE",
            detail=f"Phase {phase} ({phase_jobs[0].phase_name}) completed.",
            extra={
                "phase_index": phase,
                "phase_name": phase_jobs[0].phase_name,
                "job_count": len(phase_jobs),
            },
        )


def _record_milestone(
    paths: ProgramPaths,
    state: dict[str, object],
    *,
    milestone_id: str,
    kind: str,
    detail: str,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    path = paths.workspace / MILESTONES_FILE
    rows = list(read_jsonl(path)) if path.is_file() else []
    existing = next(
        (row for row in rows if row.get("milestone_id") == milestone_id), None
    )
    expected = {
        "kind": kind,
        "detail": detail,
        "extra": dict(extra or {}),
    }
    if existing is not None:
        for key, value in expected.items():
            if existing.get(key) != value:
                raise H2ProgramError(
                    f"durable milestone identity changed: {milestone_id}"
                )
        event = existing
    else:
        event = {
            "schema_version": "h2-product-program-milestone.v1",
            "milestone_id": milestone_id,
            **expected,
            "recorded_at_utc": _utc_now(),
        }
        rows.append(event)
        write_jsonl_atomic(path, rows)
    ids = state.setdefault("milestone_ids", [])
    if not isinstance(ids, list):
        raise H2ProgramError("state milestone_ids must be a list")
    if milestone_id not in ids:
        ids.append(milestone_id)
    state["latest_milestone"] = dict(event)
    return dict(event)


def _latest_milestone(paths: ProgramPaths) -> dict[str, object] | None:
    path = paths.workspace / MILESTONES_FILE
    if not path.is_file():
        return None
    rows = read_jsonl(path)
    return dict(rows[-1]) if rows else None


def _require_frozen_gate(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    *,
    allow_no_evaluation: bool = False,
) -> dict[str, object]:
    del allow_no_evaluation
    if not paths.freeze_path.is_file():
        raise H2ProgramError(
            "held-out evaluation requires an immutable development freeze"
        )
    freeze = read_json(paths.freeze_path)
    expected = freeze.get("freeze_identity_sha256")
    unsigned = dict(freeze)
    unsigned.pop("freeze_identity_sha256", None)
    if expected != canonical_sha256(unsigned):
        raise H2ProgramError("frozen policy checksum is invalid")
    if freeze.get("protocol_sha256") != state.get("protocol_sha256"):
        raise H2ProgramError("frozen policy protocol differs")
    if freeze.get("job_manifest_sha256") != state.get("job_manifest_sha256"):
        raise H2ProgramError("frozen policy job manifest differs")
    if freeze.get("evaluation_material_inspected") is not False:
        raise H2ProgramError("frozen policy lacks the held-out firewall assertion")
    expected_default_selection = _select_development_default_mode(paths, state, jobs)
    if freeze.get("default_product_mode_selection") != expected_default_selection:
        raise H2ProgramError("frozen development default-mode selection differs")
    if freeze.get("default_product_mode") != expected_default_selection.get(
        "selected_default_mode"
    ):
        raise H2ProgramError("frozen default product mode differs")
    selected_runtime = freeze.get("selected_runtime")
    if not isinstance(selected_runtime, Mapping):
        raise H2ProgramError("frozen selected runtime is missing")
    app_validation_sha256 = str(freeze.get("app_validation_result_sha256") or "")
    demo_binding_path = (
        paths.summary_root / "frozen_configurations/h2_demo_runtime_binding.frozen.json"
    )
    expected_demo_payload = build_h2_demo_runtime_binding_payload(
        lifecycle="FROZEN",
        default_product_mode=str(freeze["default_product_mode"]),
        configurations=_demo_binding_configurations(
            selected_runtime,
            source_result_sha256=str(
                expected_default_selection["selection_identity_sha256"]
            ),
            freeze_identity_sha256=str(expected),
        ),
        validation_identity_sha256=app_validation_sha256,
        provenance={
            "freeze_identity_sha256": expected,
            "development_default_mode_selection_sha256": (
                expected_default_selection["selection_identity_sha256"]
            ),
            "app_validation_result_sha256": app_validation_sha256,
            "evaluation_material_inspected": False,
        },
    )
    if (
        not demo_binding_path.is_file()
        or read_json(demo_binding_path) != expected_demo_payload
    ):
        raise H2ProgramError("frozen demo runtime binding differs")
    demo_binding = load_h2_demo_runtime_binding(
        demo_binding_path,
        expected_sha256=sha256_file(demo_binding_path),
    )
    for pipeline_id in ("fullpipe_v1_ag_dr_ir", "fullpipe_v1_ao_dr_ir"):
        for mode in H2_MODES:
            demo_binding.select(pipeline_id, mode)
    prepared_implementation = read_json(
        paths.workspace / RUNTIME_IMPLEMENTATION_IDENTITY
    )
    current_implementation = runtime_implementation_identity()
    if prepared_implementation != current_implementation:
        raise H2ProgramError(
            "result-affecting runtime implementation changed after preparation"
        )
    if freeze.get("runtime_implementation_identity") != prepared_implementation:
        raise H2ProgramError("frozen runtime implementation identity differs")
    if freeze.get(
        "runtime_implementation_identity_sha256"
    ) != current_implementation.get("identity_sha256"):
        raise H2ProgramError("frozen runtime implementation checksum differs")
    recorded = freeze.get("development_results")
    if not isinstance(recorded, Mapping):
        raise H2ProgramError("frozen policy lacks development result identities")
    for job in jobs:
        if job.phase_index not in range(1, 7):
            continue
        row = _job_state(state, job.job_id)
        if row.get("state") == "SUPERSEDED":
            continue
        if row.get("state") != "COMPLETE":
            raise H2ProgramError(f"development changed after freeze: {job.job_id}")
        if recorded.get(job.job_id) != row.get("result_sha256"):
            raise H2ProgramError(f"development result checksum changed: {job.job_id}")
        if job.job_kind in RUNTIME_KINDS and not runtime_result_reusable(paths, job):
            raise H2ProgramError(
                f"development result is no longer reusable: {job.job_id}"
            )
        if job.job_kind in DYNAMIC_RUNTIME_KINDS:
            dynamic_errors = _validate_dynamic_execution(
                paths,
                job,
                row,
                protocol=read_json(paths.protocol_path),
                seed=int(load_and_validate_spec(paths.config_path)["seed"]),
                verify_result=True,
            )
            if dynamic_errors:
                raise H2ProgramError("; ".join(dynamic_errors))
        if job.job_kind not in RUNTIME_KINDS | DYNAMIC_RUNTIME_KINDS:
            result_path = Path(str(row.get("result_path") or ""))
            if not result_path.is_file() or sha256_file(result_path) != row.get(
                "result_sha256"
            ):
                raise H2ProgramError(
                    f"development artifact checksum changed: {job.job_id}"
                )
    overlay_path = paths.workspace / HELDOUT_EXECUTION_MANIFEST
    if not overlay_path.is_file():
        raise H2ProgramError("post-freeze held-out execution manifest is missing")
    overlay = read_json(overlay_path)
    overlay_unsigned = dict(overlay)
    overlay_digest = overlay_unsigned.pop("heldout_execution_sha256", None)
    if overlay_digest != canonical_sha256(overlay_unsigned):
        raise H2ProgramError("post-freeze held-out execution identity is invalid")
    if overlay.get("freeze_identity_sha256") != expected:
        raise H2ProgramError("held-out execution overlay belongs to another freeze")
    if overlay.get("runtime_implementation_identity_sha256") != freeze.get(
        "runtime_implementation_identity_sha256"
    ):
        raise H2ProgramError("held-out overlay implementation identity differs")
    if overlay.get("evaluation_material_inspected_to_construct_overlay") is not False:
        raise H2ProgramError("held-out overlay construction crossed the firewall")
    expected_logical = {
        job.job_id
        for job in jobs
        if job.split == "evaluation" and job.job_kind in RUNTIME_KINDS
    }
    logical = overlay.get("logical_to_execution")
    if not isinstance(logical, Mapping) or set(logical) != expected_logical:
        raise H2ProgramError("held-out overlay membership differs from the frozen plan")
    execution_values = overlay.get("jobs")
    if not isinstance(execution_values, list):
        raise H2ProgramError("held-out overlay jobs are missing")
    execution_jobs = tuple(
        H2Job.from_jsonable(value)
        for value in execution_values
        if isinstance(value, Mapping)
    )
    if {job.job_id for job in execution_jobs} != set(map(str, logical.values())):
        raise H2ProgramError("held-out overlay job IDs differ")
    for execution_job in execution_jobs:
        validate_runtime_tuning(execution_job)
    heldout_store = EvaluationStateStore(
        _heldout_paths(paths).workspace / RUNTIME_QUEUE_DATABASE
    )
    heldout_store.assert_integrity()
    if {row.spec.job_id for row in heldout_store.list_jobs()} != {
        job.job_id for job in execution_jobs
    }:
        raise H2ProgramError(
            "held-out queue membership differs from the frozen overlay"
        )
    protocol = read_json(paths.protocol_path)
    seed = int(load_and_validate_spec(paths.config_path)["seed"])
    expected_specs = {
        spec.job_id: spec.to_jsonable()
        for spec in build_runtime_specs(
            execution_jobs,
            protocol=protocol,
            seed=seed,
        )
    }
    actual_specs = {
        row.spec.job_id: row.spec.to_jsonable() for row in heldout_store.list_jobs()
    }
    if actual_specs != expected_specs:
        raise H2ProgramError("held-out queue specifications/code identities differ")
    return freeze


def _require_state_bindings(
    state: Mapping[str, object],
    protocol: Mapping[str, object],
    manifest: Mapping[str, object],
) -> None:
    if state.get("schema_version") != H2_PROGRAM_SCHEMA_VERSION:
        raise H2ProgramError("unexpected H2 program state schema")
    for state_key, source, source_key in (
        ("protocol_id", protocol, "protocol_id"),
        ("protocol_sha256", protocol, "protocol_sha256"),
        ("job_manifest_sha256", manifest, "job_manifest_sha256"),
    ):
        if state.get(state_key) != source.get(source_key):
            raise H2ProgramError(f"program state binding differs: {state_key}")


def _verify_protocol_identity(protocol: Mapping[str, object]) -> None:
    unsigned = dict(protocol)
    digest = unsigned.pop("protocol_sha256", None)
    unsigned.pop("protocol_id", None)
    if digest != canonical_sha256(unsigned):
        raise H2ProgramError("protocol identity checksum is invalid")


def _verify_job_manifest_identity(manifest: Mapping[str, object]) -> None:
    unsigned = dict(manifest)
    digest = unsigned.pop("job_manifest_sha256", None)
    if digest != canonical_sha256(unsigned):
        raise H2ProgramError("job manifest checksum is invalid")


def _validate_state_jobs(state: Mapping[str, object], jobs: Sequence[H2Job]) -> None:
    values = state.get("jobs")
    if not isinstance(values, Mapping):
        raise H2ProgramError("program state jobs are missing")
    if set(values) != {job.job_id for job in jobs}:
        raise H2ProgramError("program state job membership differs")


def _manifest_jobs(manifest: Mapping[str, object]) -> tuple[H2Job, ...]:
    values = manifest.get("jobs")
    if not isinstance(values, list):
        raise H2ProgramError("job manifest jobs must be a list")
    return tuple(H2Job.from_jsonable(row) for row in values if isinstance(row, Mapping))


def _job_state(state: Mapping[str, object], job_id: str) -> dict[str, object]:
    jobs = state.get("jobs")
    if not isinstance(jobs, Mapping) or not isinstance(jobs.get(job_id), dict):
        raise H2ProgramError(f"program state lacks job: {job_id}")
    return jobs[job_id]  # type: ignore[return-value]


def _progress(
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    queue_rows: Mapping[str, object],
) -> dict[str, object]:
    active = [
        job
        for job in jobs
        if _job_state(state, job.job_id).get("state") != "SUPERSEDED"
    ]
    total_units = 0.0
    completed_units = 0.0
    completed_jobs = 0
    for job in active:
        units = float(max(1, len(job.case_ids)))
        total_units += units
        row = _job_state(state, job.job_id)
        if row.get("state") == "COMPLETE":
            completed_units += units
            completed_jobs += 1
        elif row.get("state") == "RUNNING" and job.job_id in queue_rows:
            completed_units += min(
                units,
                float(
                    _queue_value(
                        queue_rows[job.job_id],
                        "completed_cases",
                        row.get("completed_cases") or 0,
                    )
                    or 0
                ),
            )
        elif row.get("state") == "RUNNING":
            completed_units += min(units, float(row.get("completed_cases") or 0))
    fraction = completed_units / total_units if total_units else 0.0
    started = _parse_utc(state.get("started_at_utc"))
    elapsed_hours = (
        (datetime.now(timezone.utc) - started).total_seconds() / 3600.0
        if started is not None
        else 0.0
    )
    eta = elapsed_hours * (1.0 - fraction) / fraction if fraction > 0 else None
    return {
        "percent_complete": round(100.0 * fraction, 2),
        "elapsed_hours": round(elapsed_hours, 2),
        "eta_hours": round(eta, 2) if eta is not None else None,
        "completed_jobs": completed_jobs,
        "active_planned_jobs": len(active),
    }


def _storage_snapshot(paths: ProgramPaths) -> dict[str, object]:
    usage = shutil.disk_usage(Path("C:/"))
    cache_key = "|".join(
        str(value.resolve())
        for value in (paths.workspace, paths.results_root, paths.summary_root)
    )
    now = time.monotonic()
    cached = _STORAGE_SIZE_CACHE.get(cache_key)
    if cached is None or now - cached[0] >= 60.0:
        sizes = (
            _tree_size(paths.workspace),
            _tree_size(paths.results_root),
            _tree_size(paths.summary_root),
        )
        _STORAGE_SIZE_CACHE[cache_key] = (now, sizes)
    else:
        sizes = cached[1]
    return {
        "drive": "C:",
        "free_gib": round(usage.free / 1024**3, 2),
        "total_gib": round(usage.total / 1024**3, 2),
        "minimum_reserve_gib": 35.0,
        "reserve_satisfied": usage.free >= 35 * 1024**3,
        "workspace_bytes": sizes[0],
        "results_bytes": sizes[1],
        "summary_bytes": sizes[2],
        "directory_sizes_cache_ttl_sec": 60.0,
    }


def _require_storage_reserve(paths: ProgramPaths) -> None:
    snapshot = _storage_snapshot(paths)
    if not snapshot["reserve_satisfied"]:
        raise H2ProgramError(
            "C: free-space reserve is below 35 GiB; no new atomic case was started. "
            "Existing results were preserved and nothing was deleted."
        )


def _require_c_drive(paths: ProgramPaths) -> None:
    for name, path in (
        ("evaluation_root", paths.evaluation_root),
        ("workspace", paths.workspace),
        ("results_root", paths.results_root),
        ("summary_root", paths.summary_root),
        ("config_path", paths.config_path),
    ):
        if Path(path).resolve().drive.casefold() != "c:":
            raise H2ProgramError(f"{name} must stay on C: {path}")


def _tree_size(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for base, _directories, files in os.walk(root):
        for name in files:
            try:
                total += (Path(base) / name).stat().st_size
            except OSError:
                continue
    return total


def _validated_promotion_decision(
    paths: ProgramPaths,
    state: Mapping[str, object],
    *,
    collection: str,
    key: str,
) -> dict[str, object]:
    values = state.get(collection)
    if not isinstance(values, Mapping) or not isinstance(values.get(key), Mapping):
        raise H2ProgramError(f"development decision is missing: {collection}/{key}")
    state_row = dict(values[key])  # type: ignore[arg-type]
    expected_path = (paths.workspace / collection / f"{key}.json").resolve()
    raw_path = state_row.pop("decision_path", None)
    expected_sha = state_row.pop("decision_sha256", None)
    if not raw_path or Path(str(raw_path)).resolve() != expected_path:
        raise H2ProgramError(
            f"mutable state redirected development decision: {collection}/{key}"
        )
    if not expected_path.is_file() or sha256_file(expected_path) != expected_sha:
        raise H2ProgramError(
            f"development decision checksum differs: {collection}/{key}"
        )
    artifact = read_json(expected_path)
    if artifact != state_row:
        raise H2ProgramError(
            f"mutable state content differs from decision artifact: {collection}/{key}"
        )
    if (
        artifact.get("schema_version") != "h2-development-promotion.v1"
        or artifact.get("status") != "COMPLETE"
        or artifact.get("development_only") is not True
        or artifact.get("evaluation_material_inspected") is not False
        or artifact.get("weighted_composite_used") is not False
        or artifact.get("required_safety_metrics")
        != sorted(REQUIRED_SAFETY_METRICS)
        or artifact.get("required_short_turn_metrics")
        != sorted(REQUIRED_SHORT_TURN_METRICS)
        or artifact.get("required_promotion_metrics")
        != sorted(REQUIRED_PROMOTION_METRICS)
    ):
        raise H2ProgramError(
            f"development decision firewall differs: {collection}/{key}"
        )
    selected = artifact.get("selected_candidates")
    if not isinstance(selected, list) or not selected:
        raise H2ProgramError(
            f"development decision selected candidates are invalid: {collection}/{key}"
        )
    return {
        **artifact,
        "decision_path": str(expected_path),
        "decision_sha256": expected_sha,
    }


def _best_promoted_full(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    phase: int,
) -> H2Job | None:
    values = [
        job
        for job in jobs
        if job.phase_index == phase
        and job.configuration_id.endswith("_FULL")
        and _job_state(state, job.job_id).get("state") == "COMPLETE"
    ]
    if not values:
        return None
    key = f"phase_{phase}_full"
    decision = _validated_promotion_decision(
        paths,
        state,
        collection="promotions",
        key=key,
    )
    selected = decision["selected_candidates"]
    if not isinstance(selected, list):  # pragma: no cover - validator owns
        raise H2ProgramError(f"invalid selected candidates for {key}")
    order = {str(candidate): index for index, candidate in enumerate(selected)}
    return min(
        values,
        key=lambda job: (
            order.get(_candidate_base(job.configuration_id), 999),
            job.job_id,
        ),
    )


def _candidate_base(configuration_id: str) -> str:
    for suffix in ("_SMALL", "_MEDIUM", "_FULL"):
        if configuration_id.endswith(suffix):
            return configuration_id[: -len(suffix)]
    return configuration_id


def _nonruntime_result_path(paths: ProgramPaths, job: H2Job) -> Path:
    return paths.results_root / "jobs" / job.job_id / "artifacts" / NON_RUNTIME_RESULT


def _bar(percent: float, width: int = 24) -> str:
    filled = max(0, min(width, round(width * percent / 100.0)))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "analyze",
    "audit",
    "collect",
    "export_portable",
    "launch_demo",
    "plan",
    "prepare",
    "run",
    "status",
    "stop",
    "validate",
]
