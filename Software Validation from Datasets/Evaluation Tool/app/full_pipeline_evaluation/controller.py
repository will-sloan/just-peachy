"""Restart-safe controller for the additive full-pipeline v1 evaluation.

This module owns orchestration only.  Model inference remains in the Prompt-1
backend-neutral runtime, protocols remain in :mod:`protocol`, and metric math
remains in :mod:`scorers`.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import threading
from typing import Callable, Mapping, Sequence
import uuid

from .io import (
    canonical_json_bytes,
    checksum_map,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from .monitor import publish_progress
from .planning import (
    DEFAULT_RESULTS_ROOT,
    DEFAULT_SEED,
    DEFAULT_SUMMARY_ROOT,
    DEFAULT_WORKSPACE_ROOT,
    build_campaign_manifest,
    filter_jobs,
    manifest_jobs,
    matrix,
)
from .store import (
    EvaluationJobSpec,
    EvaluationStateCorruptionError,
    EvaluationStateStore,
    utc_now,
)


JobProgress = Callable[..., None]
JobExecutor = Callable[
    [
        EvaluationJobSpec,
        Sequence[Mapping[str, object]],
        Path,
        JobProgress,
        Callable[[], bool],
    ],
    Mapping[str, object],
]

CAMPAIGN_MANIFEST = "campaign_manifest.json"
CAMPAIGN_DATABASE = "campaign.sqlite3"
CAMPAIGN_PROGRESS = "campaign_progress.json"
CONTROLLER_STATE = "controller_state.json"
FROZEN_GATE = "frozen_development_gate.json"
ANALYSIS_FILE = "analysis/analysis.json"
LEASE_KEEPALIVE_INTERVAL_SEC = 30.0
CONTROLLER_STOP_POLL_INTERVAL_SEC = 0.5


class EvaluationQueueInfrastructureError(RuntimeError):
    """A durable queue failure that must stop further job submission."""


def audit() -> dict[str, object]:
    """Audit installed source protocols without materializing or downloading."""

    from .protocol import audit_sources

    source_audit = audit_sources()
    matrix_status = matrix().status()
    return {
        "schema_version": "full-pipeline-evaluation-audit.v1",
        "status": "PASS"
        if source_audit.get("status") == "PASS"
        and matrix_status.get("pipeline_count") == 18
        else "FAIL",
        "source_audit": source_audit,
        "matrix": matrix_status,
        "downloads_performed": False,
        "downloads_allowed": False,
        "frozen_source_protocols_modified": False,
        "long_campaign_started": False,
    }


def prepare(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    seed: int = DEFAULT_SEED,
    case_ids: Sequence[str] = (),
    pipeline_ids: Sequence[str] = (),
    measurement_modes: Sequence[str] = ("accuracy", "resources"),
    campaign_stage: str = "full_protocol",
    decision_policy_registry_path: Path | None = None,
) -> dict[str, object]:
    """Materialize additive protocol manifests and a deterministic job database."""

    from .protocol import load_cases, prepare_protocol, validate_protocol

    workspace = Path(workspace_root).resolve()
    protocol = prepare_protocol(overwrite=False)
    checked = validate_protocol(verify_audio=False)
    if not checked.get("valid"):
        raise RuntimeError("full_speech_pipeline_v1 protocol validation failed")
    all_cases = load_cases()
    cases = _select_exact_cases(all_cases, case_ids)
    if campaign_stage.startswith("prompt4_") and any(
        str(row.get("split") or row.get("partition") or "") != "development"
        for row in cases
    ):
        raise ValueError("Prompt-4 campaigns may contain development cases only")
    registry_sha256 = (
        sha256_file(Path(decision_policy_registry_path).resolve())
        if decision_policy_registry_path is not None
        else None
    )
    manifest, jobs = build_campaign_manifest(
        cases,
        protocol_id=str(protocol["protocol_id"]),
        development_identity=_split_identity_sha(
            protocol["development_identity"], "development"
        ),
        evaluation_identity=_split_identity_sha(
            protocol["evaluation_identity"], "evaluation"
        ),
        seed=seed,
        pipeline_ids=pipeline_ids,
        measurement_modes=measurement_modes,
        campaign_stage=campaign_stage,
        decision_policy_registry_sha256=registry_sha256,
    )
    workspace.mkdir(parents=True, exist_ok=True)
    if decision_policy_registry_path is not None:
        source_registry = Path(decision_policy_registry_path).resolve()
        target_registry = workspace / "decision_policy_registry.json"
        if target_registry.is_file():
            if sha256_file(target_registry) != registry_sha256:
                raise RuntimeError(
                    "workspace decision-policy registry differs; choose a new root"
                )
        else:
            shutil.copy2(source_registry, target_registry)
    manifest_path = workspace / CAMPAIGN_MANIFEST
    if manifest_path.is_file():
        existing = read_json(manifest_path)
        if canonical_json_bytes(existing) != canonical_json_bytes(manifest):
            raise RuntimeError(
                "prepared campaign identity differs; choose a new workspace root"
            )
    else:
        write_json_atomic(manifest_path, manifest)
    manifest_sha256 = sha256_file(manifest_path)
    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    prepared = store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256=manifest_sha256,
    )
    write_json_atomic(
        workspace / "campaign_paths.json",
        {
            "schema_version": "full-pipeline-evaluation-paths.v1",
            "campaign_id": manifest["campaign_id"],
            "workspace_root": str(workspace),
            "results_root": str(
                (DEFAULT_RESULTS_ROOT / str(manifest["campaign_id"])).resolve()
            ),
            "summary_root": str(
                (DEFAULT_SUMMARY_ROOT / str(manifest["campaign_id"])).resolve()
            ),
        },
    )
    progress = publish_progress(
        store,
        campaign_id=str(manifest["campaign_id"]),
        output_path=workspace / CAMPAIGN_PROGRESS,
    )
    _write_controller_state(
        workspace,
        status="PREPARED",
        action="Prepare",
        detail="Deterministic additive protocol and job queue prepared",
        campaign_id=str(manifest["campaign_id"]),
    )
    return {
        "schema_version": "full-pipeline-evaluation-preparation.v1",
        "status": "PASS",
        "campaign_id": manifest["campaign_id"],
        "workspace_root": str(workspace),
        "protocol": protocol,
        "protocol_validation": checked,
        "job_count": len(jobs),
        "database": prepared,
        "progress": progress,
        "long_campaign_started": False,
    }


def validate(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    verify_audio: bool = False,
) -> dict[str, object]:
    """Validate protocol, campaign identity, state, and any complete results."""

    from .protocol import load_cases, validate_protocol

    workspace = Path(workspace_root).resolve()
    manifest_path = workspace / CAMPAIGN_MANIFEST
    errors: list[str] = []
    protocol = validate_protocol(verify_audio=verify_audio)
    if not protocol.get("valid"):
        errors.append("full_speech_pipeline_v1 protocol invalid")
    if not manifest_path.is_file():
        errors.append("campaign is not prepared")
        return _validation_result(workspace, protocol, errors, 0, 0)
    manifest = read_json(manifest_path)
    all_cases = load_cases()
    cases = _select_exact_cases(
        all_cases,
        tuple(str(value) for value in manifest.get("selected_case_ids", ())),
    )
    if str(manifest.get("campaign_stage") or "").startswith("prompt4_") and any(
        str(row.get("split") or row.get("partition") or "") != "development"
        for row in cases
    ):
        errors.append("Prompt-4 campaign contains held-out evaluation cases")
    registry = manifest.get("decision_policy_registry")
    registry_sha256: str | None = None
    if registry is not None:
        if not isinstance(registry, Mapping):
            errors.append("decision-policy registry reference is invalid")
        else:
            logical_path = str(registry.get("logical_path") or "")
            expected_sha = str(registry.get("sha256") or "").lower()
            registry_path = (workspace / logical_path).resolve()
            try:
                registry_path.relative_to(workspace)
            except ValueError:
                errors.append("decision-policy registry escapes the workspace")
            else:
                if not registry_path.is_file():
                    errors.append("decision-policy registry file is missing")
                elif sha256_file(registry_path) != expected_sha:
                    errors.append("decision-policy registry checksum differs")
                else:
                    registry_sha256 = expected_sha
    expected, expected_jobs = build_campaign_manifest(
        cases,
        protocol_id=str(manifest.get("full_protocol_id")),
        development_identity=str(manifest.get("development_identity")),
        evaluation_identity=str(manifest.get("evaluation_identity")),
        seed=int(manifest.get("seed", DEFAULT_SEED)),
        pipeline_ids=tuple(
            str(value) for value in manifest.get("selected_pipeline_ids", ())
        ),
        measurement_modes=tuple(
            str(value)
            for value in (
                manifest.get("measurement_modes") or ("accuracy", "resources")
            )
        ),
        campaign_stage=str(manifest.get("campaign_stage") or "full_protocol"),
        decision_policy_registry_sha256=registry_sha256,
    )
    if canonical_json_bytes(expected) != canonical_json_bytes(manifest):
        errors.append("campaign manifest no longer matches protocol/matrix identities")
    store_path = workspace / CAMPAIGN_DATABASE
    if not store_path.is_file():
        errors.append("campaign state database is missing")
        return _validation_result(workspace, protocol, errors, 0, 0)
    store = EvaluationStateStore(store_path)
    metadata = store.metadata()
    if metadata.get("campaign_id") != manifest.get("campaign_id"):
        errors.append("campaign database campaign ID mismatch")
    if metadata.get("manifest_sha256") != sha256_file(manifest_path):
        errors.append("campaign database manifest checksum mismatch")
    stored = store.list_jobs()
    if {
        row.spec.job_id: row.spec.to_jsonable() for row in stored
    } != {job.job_id: job.to_jsonable() for job in expected_jobs}:
        errors.append("campaign database job specifications differ from manifest")
    result_count = 0
    reusable_count = 0
    try:
        from .results import validate_result_tree

        results_root = _results_root(workspace, manifest)
        for row in stored:
            result_root = results_root / row.spec.result_relative_path
            if not result_root.exists():
                if row.state == "complete":
                    errors.append(
                        f"completed result tree is missing: {row.spec.job_id}"
                    )
                continue
            result_count += 1
            report = validate_result_tree(
                result_root,
                expected_reuse_identity=row.spec.reuse_identity,
            )
            if report.reusable:
                reusable_count += 1
            if row.state == "complete":
                if not report.reusable:
                    detail = "; ".join(
                        f"{issue.code}[{issue.logical_path}]={issue.message}"
                        for issue in report.issues
                    )
                    errors.append(
                        f"invalid completed result {row.spec.job_id}: {detail}"
                    )
                else:
                    checksum_sha = sha256_file(result_root / "checksums.json")
                    if row.result_sha256 != checksum_sha:
                        errors.append(
                            f"completed result database checksum mismatch: "
                            f"{row.spec.job_id}"
                        )
    except ImportError:
        errors.append("result-tree validation package is unavailable")
    return _validation_result(
        workspace, protocol, errors, result_count, reusable_count
    )


def plan(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    split: str | None = None,
    measurement_mode: str | None = None,
    pipeline_ids: Sequence[str] = (),
    protocol_ids: Sequence[str] = (),
) -> dict[str, object]:
    workspace = Path(workspace_root).resolve()
    manifest = _manifest(workspace)
    jobs = filter_jobs(
        manifest_jobs(manifest),
        split=split,
        measurement_mode=measurement_mode,
        pipeline_ids=pipeline_ids,
        protocol_ids=protocol_ids,
    )
    by_split_mode: dict[str, dict[str, object]] = {}
    for job in jobs:
        key = f"{job.split}:{job.measurement_mode}"
        row = by_split_mode.setdefault(
            key,
            {"jobs": 0, "cases": 0, "audio_duration_sec": 0.0},
        )
        row["jobs"] = int(row["jobs"]) + 1
        row["cases"] = int(row["cases"]) + job.case_count
        row["audio_duration_sec"] = (
            float(row["audio_duration_sec"]) + job.audio_duration_sec
        )
    value = {
        "schema_version": "full-pipeline-evaluation-plan.v1",
        "campaign_id": manifest["campaign_id"],
        "filters": {
            "split": split,
            "measurement_mode": measurement_mode,
            "pipeline_ids": list(pipeline_ids),
            "protocol_ids": list(protocol_ids),
        },
        "job_count": len(jobs),
        "case_count": sum(job.case_count for job in jobs),
        "audio_duration_sec": sum(job.audio_duration_sec for job in jobs),
        "pipeline_count": len({job.pipeline_id for job in jobs}),
        "protocol_count": len({job.protocol_id for job in jobs}),
        "groups": by_split_mode,
        "parallelism": {
            "accuracy_maximum": 2,
            "resources": 1,
            "memory_gate_applied_at_run": True,
        },
        "downloads_allowed": False,
        "jobs": [job.to_jsonable() for job in jobs],
    }
    write_json_atomic(workspace / "plan.json", value)
    return value


def run_development(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    measurement_mode: str = "accuracy",
    pipeline_ids: Sequence[str] = (),
    protocol_ids: Sequence[str] = (),
    parallel_jobs: int = 2,
    job_executor: JobExecutor | None = None,
) -> dict[str, object]:
    return _run(
        workspace_root=workspace_root,
        split="development",
        measurement_mode=measurement_mode,
        pipeline_ids=pipeline_ids,
        protocol_ids=protocol_ids,
        parallel_jobs=parallel_jobs,
        job_executor=job_executor,
    )


def run_evaluation(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    measurement_mode: str = "accuracy",
    pipeline_ids: Sequence[str] = (),
    protocol_ids: Sequence[str] = (),
    parallel_jobs: int = 2,
    job_executor: JobExecutor | None = None,
) -> dict[str, object]:
    workspace = Path(workspace_root).resolve()
    _require_frozen_gate(workspace)
    return _run(
        workspace_root=workspace,
        split="evaluation",
        measurement_mode=measurement_mode,
        pipeline_ids=pipeline_ids,
        protocol_ids=protocol_ids,
        parallel_jobs=parallel_jobs,
        job_executor=job_executor,
    )


def freeze(*, workspace_root: Path = DEFAULT_WORKSPACE_ROOT) -> dict[str, object]:
    """Freeze completed development outputs without choosing a winner."""

    workspace = Path(workspace_root).resolve()
    manifest = _manifest(workspace)
    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    rows = store.list_jobs(split="development", measurement_mode="accuracy")
    if not rows:
        raise RuntimeError("cannot freeze an empty development accuracy campaign")
    incomplete = [row.spec.job_id for row in rows if row.state != "complete"]
    if incomplete:
        raise RuntimeError(
            "cannot freeze before all development accuracy jobs complete; "
            f"remaining={len(incomplete)}"
        )
    development_results = _require_reusable_complete_results(
        workspace, manifest, rows
    )
    manifest_sha256 = sha256_file(workspace / CAMPAIGN_MANIFEST)
    gate = {
        "schema_version": "full-pipeline-evaluation-development-freeze.v1",
        "campaign_id": manifest["campaign_id"],
        "campaign_identity_sha256": manifest["campaign_identity_sha256"],
        "campaign_manifest_sha256": manifest_sha256,
        "frozen_at_utc": utc_now(),
        "development_identity": manifest["development_identity"],
        "evaluation_identity": manifest["evaluation_identity"],
        "matrix_sha256": manifest["matrix_sha256"],
        "runtime_config_sha256": manifest["runtime_config_sha256"],
        "scorer_version": manifest["scorer_version"],
        "development_results": development_results,
        "development_result_set_sha256": sha256_bytes(
            canonical_json_bytes(development_results)
        ),
        "evaluation_material_used_for_development": False,
        "evaluation_retuning_allowed": False,
        "selection_performed": False,
        "purpose": "freeze_methodology_and_development_evidence_only",
    }
    gate["freeze_identity_sha256"] = sha256_bytes(canonical_json_bytes(gate))
    write_json_atomic(workspace / FROZEN_GATE, gate)
    _write_controller_state(
        workspace,
        status="FROZEN",
        action="Freeze",
        detail="Development methodology frozen; no pipeline selected",
        campaign_id=str(manifest["campaign_id"]),
    )
    return gate


def status(
    *, workspace_root: Path = DEFAULT_WORKSPACE_ROOT
) -> dict[str, object]:
    workspace = Path(workspace_root).resolve()
    manifest = _manifest(workspace)
    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    return publish_progress(
        store,
        campaign_id=str(manifest["campaign_id"]),
        output_path=workspace / CAMPAIGN_PROGRESS,
    )


def stop(*, workspace_root: Path = DEFAULT_WORKSPACE_ROOT) -> dict[str, object]:
    workspace = Path(workspace_root).resolve()
    manifest = _manifest(workspace)
    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    store.request_stop()
    stopped = store.stop_not_running()
    value = publish_progress(
        store,
        campaign_id=str(manifest["campaign_id"]),
        output_path=workspace / CAMPAIGN_PROGRESS,
    )
    _write_controller_state(
        workspace,
        status="STOP_REQUESTED",
        action="Stop",
        detail=f"Graceful stop requested; {stopped} queued jobs stopped",
        campaign_id=str(manifest["campaign_id"]),
    )
    return {**value, "queued_jobs_stopped": stopped}


def analyze(*, workspace_root: Path = DEFAULT_WORKSPACE_ROOT) -> dict[str, object]:
    """Index per-view metrics without collapsing them into a weighted score."""

    workspace = Path(workspace_root).resolve()
    manifest = _manifest(workspace)
    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    results_root = _results_root(workspace, manifest)
    complete_states = store.list_jobs(states=("complete",))
    validated_results = _require_reusable_complete_results(
        workspace, manifest, complete_states
    )
    rows: list[dict[str, object]] = []
    for state_row in complete_states:
        root = results_root / state_row.spec.result_relative_path
        summary_path = root / "metrics/summary.json"
        if not summary_path.is_file():
            continue
        summary = read_json(summary_path)
        rows.append(
            {
                "job_id": state_row.spec.job_id,
                "pipeline_id": state_row.spec.pipeline_id,
                "protocol_id": state_row.spec.protocol_id,
                "source_key": state_row.spec.source_key,
                "split": state_row.spec.split,
                "measurement_mode": state_row.spec.measurement_mode,
                "reuse_identity": dict(state_row.spec.reuse_identity),
                "result_root": str(root),
                "result_checksums_sha256": validated_results[
                    state_row.spec.job_id
                ],
                "summary": summary,
            }
        )
    value = {
        "schema_version": "full-pipeline-evaluation-analysis.v1",
        "campaign_id": manifest["campaign_id"],
        "created_at_utc": utc_now(),
        "complete_result_count": len(rows),
        "pipeline_ids": sorted({str(row["pipeline_id"]) for row in rows}),
        "protocol_ids": sorted({str(row["protocol_id"]) for row in rows}),
        "weighted_composite_score_created": False,
        "resource_comparison_policy": (
            "only measurement_mode=resources serial jobs are mutually comparable"
        ),
        "rows": rows,
    }
    write_json_atomic(workspace / ANALYSIS_FILE, value)
    return value


def collect(*, workspace_root: Path = DEFAULT_WORKSPACE_ROOT) -> dict[str, object]:
    workspace = Path(workspace_root).resolve()
    manifest = _manifest(workspace)
    # Rebuild the index only after revalidating every DB-complete result.  A
    # previously written analysis is not evidence that result bytes stayed put.
    analyze(workspace_root=workspace)
    destination = DEFAULT_SUMMARY_ROOT / str(manifest["campaign_id"])
    destination.mkdir(parents=True, exist_ok=True)
    for relative in (
        CAMPAIGN_MANIFEST,
        "plan.json",
        CAMPAIGN_PROGRESS,
        FROZEN_GATE,
        ANALYSIS_FILE,
    ):
        source = workspace / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    checksums = checksum_map(destination, exclude=("checksums.json",))
    write_json_atomic(
        destination / "checksums.json",
        {
            "schema_version": "full-pipeline-evaluation-collection-checksums.v1",
            "entries": checksums,
        },
    )
    return {
        "schema_version": "full-pipeline-evaluation-collection.v1",
        "status": "PASS",
        "campaign_id": manifest["campaign_id"],
        "destination": str(destination),
        "artifact_count": len(checksums),
        "raw_audio_included": False,
        "biometric_vectors_included": False,
    }


def _run(
    *,
    workspace_root: Path,
    split: str,
    measurement_mode: str,
    pipeline_ids: Sequence[str],
    protocol_ids: Sequence[str],
    parallel_jobs: int,
    job_executor: JobExecutor | None,
) -> dict[str, object]:
    """Run one host-exclusive controller invocation.

    The invocation may still schedule two accuracy jobs internally. The host
    lock prevents a second process from overlapping those jobs with matched
    resource telemetry or exceeding the host-wide concurrency policy.
    """

    from .host_lock import HostRunLock

    host_lock_path = (
        DEFAULT_WORKSPACE_ROOT.parent / ".full_pipeline_evaluation.host.lock"
    )
    with HostRunLock(host_lock_path, measurement_mode=measurement_mode):
        return _run_locked(
            workspace_root=workspace_root,
            split=split,
            measurement_mode=measurement_mode,
            pipeline_ids=pipeline_ids,
            protocol_ids=protocol_ids,
            parallel_jobs=parallel_jobs,
            job_executor=job_executor,
        )


def _run_locked(
    *,
    workspace_root: Path,
    split: str,
    measurement_mode: str,
    pipeline_ids: Sequence[str],
    protocol_ids: Sequence[str],
    parallel_jobs: int,
    job_executor: JobExecutor | None,
) -> dict[str, object]:
    if measurement_mode not in {"accuracy", "resources"}:
        raise ValueError("measurement_mode must be accuracy or resources")
    if parallel_jobs not in {1, 2}:
        raise ValueError("parallel_jobs must be 1 or 2")
    if measurement_mode == "resources" and parallel_jobs != 1:
        raise ValueError("matched resource measurements must run one job at a time")
    workspace = Path(workspace_root).resolve()
    checked = validate(workspace_root=workspace, verify_audio=False)
    if not checked["valid"]:
        raise RuntimeError("evaluation infrastructure validation failed")
    manifest = _manifest(workspace)
    selected = filter_jobs(
        manifest_jobs(manifest),
        split=split,
        measurement_mode=measurement_mode,
        pipeline_ids=pipeline_ids,
        protocol_ids=protocol_ids,
    )
    if not selected:
        raise ValueError("exact filters selected no evaluation jobs")
    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    store.reclaim_expired_leases()
    store.clear_stop()
    selected_ids = [job.job_id for job in selected]
    selected_id_set = set(selected_ids)
    existing_audio = sum(
        row.completed_audio_sec
        for row in store.list_jobs()
        if row.spec.job_id in selected_id_set
    )
    store.set_runtime_metadata("progress_baseline_utc", utc_now())
    store.set_runtime_metadata("progress_baseline_audio_sec", str(existing_audio))
    effective_parallel, memory = _memory_gated_parallelism(
        requested=parallel_jobs, measurement_mode=measurement_mode
    )
    if job_executor is not None:
        executor = job_executor
    else:
        registry_ref = manifest.get("decision_policy_registry")
        registry_path: Path | None = None
        if isinstance(registry_ref, Mapping):
            registry_path = (
                workspace / str(registry_ref.get("logical_path") or "")
            ).resolve()

        def executor(
            job: EvaluationJobSpec,
            cases: Sequence[Mapping[str, object]],
            output_root: Path,
            progress: JobProgress,
            stop_requested: Callable[[], bool],
        ) -> Mapping[str, object]:
            return _default_job_executor(
                job,
                cases,
                output_root,
                progress,
                stop_requested,
                decision_policy_registry_path=registry_path,
            )
    _write_controller_state(
        workspace,
        status="RUNNING",
        action=f"Run{split.title()}",
        detail=(
            f"Running {len(selected)} {measurement_mode} jobs with "
            f"concurrency {effective_parallel}"
        ),
        campaign_id=str(manifest["campaign_id"]),
        extra={"memory_gate": memory, "selected_job_ids": selected_ids},
    )
    failures: list[str] = []
    infrastructure_errors: list[dict[str, str]] = []
    infrastructure_errors_lock = threading.Lock()
    controller_stop = threading.Event()
    stop_poller_shutdown = threading.Event()
    jobs_by_id = {job.job_id: job for job in selected}
    pending = list(selected)
    active: dict[Future[Mapping[str, object]], EvaluationJobSpec] = {}
    lock = threading.Lock()

    def record_infrastructure_error(
        *, phase: str, error: BaseException, job_id: str | None = None
    ) -> None:
        row = {
            "phase": phase,
            "error": f"{type(error).__name__}: {error}",
        }
        if job_id is not None:
            row["job_id"] = job_id
        with infrastructure_errors_lock:
            if row not in infrastructure_errors:
                infrastructure_errors.append(row)
        controller_stop.set()

    def poll_stop_request() -> None:
        while not stop_poller_shutdown.is_set():
            try:
                if store.stop_requested():
                    controller_stop.set()
                    return
            except Exception as exc:
                record_infrastructure_error(phase="stop_poll", error=exc)
                return
            if stop_poller_shutdown.wait(CONTROLLER_STOP_POLL_INTERVAL_SEC):
                return

    def submit_one(pool: ThreadPoolExecutor, job: EvaluationJobSpec) -> None:
        future = pool.submit(
            _run_one,
            workspace,
            manifest,
            job,
            executor,
            lock,
            controller_stop,
        )
        active[future] = job

    stop_poller = threading.Thread(
        target=poll_stop_request,
        name="fullpipe-evaluation-stop-poller",
        daemon=True,
    )
    stop_poller.start()
    try:
        with ThreadPoolExecutor(
            max_workers=effective_parallel, thread_name_prefix="fullpipe-eval"
        ) as pool:
            while pending and len(active) < effective_parallel:
                submit_one(pool, pending.pop(0))
            while active:
                completed, _ = wait(tuple(active), return_when=FIRST_COMPLETED)
                for future in completed:
                    job = active.pop(future)
                    try:
                        result = future.result()
                        if str(result.get("state")) == "failed":
                            failures.append(job.job_id)
                    except Exception as exc:
                        failures.append(job.job_id)
                        record_infrastructure_error(
                            phase="job_future", error=exc, job_id=job.job_id
                        )
                if controller_stop.is_set():
                    pending.clear()
                    continue
                while pending and len(active) < effective_parallel:
                    submit_one(pool, pending.pop(0))
                try:
                    publish_progress(
                        store,
                        campaign_id=str(manifest["campaign_id"]),
                        output_path=workspace / CAMPAIGN_PROGRESS,
                        selected_job_ids=selected_ids,
                    )
                except Exception as exc:
                    pending.clear()
                    record_infrastructure_error(
                        phase="progress_publish", error=exc
                    )
    finally:
        stop_poller_shutdown.set()
        stop_poller.join(timeout=5.0)

    if infrastructure_errors:
        _write_controller_state(
            workspace,
            status="FAILED",
            action=f"Run{split.title()}",
            detail="Queue infrastructure failed; no further jobs were scheduled",
            campaign_id=str(manifest["campaign_id"]),
            extra={
                "failures": sorted(set(failures)),
                "infrastructure_errors": infrastructure_errors,
                "memory_gate": memory,
            },
        )
        first = infrastructure_errors[0]
        raise EvaluationQueueInfrastructureError(
            f"{first['phase']}: {first['error']}"
        )

    try:
        store.assert_integrity()
        progress = publish_progress(
            store,
            campaign_id=str(manifest["campaign_id"]),
            output_path=workspace / CAMPAIGN_PROGRESS,
            selected_job_ids=selected_ids,
        )
        selected_states = {
            row.spec.job_id: row.state
            for row in store.list_jobs()
            if row.spec.job_id in selected_id_set
        }
    except Exception as exc:
        record_infrastructure_error(phase="final_queue_validation", error=exc)
        _write_controller_state(
            workspace,
            status="FAILED",
            action=f"Run{split.title()}",
            detail="Queue integrity failed after execution",
            campaign_id=str(manifest["campaign_id"]),
            extra={
                "failures": sorted(set(failures)),
                "infrastructure_errors": infrastructure_errors,
                "memory_gate": memory,
            },
        )
        raise EvaluationQueueInfrastructureError(
            f"final_queue_validation: {type(exc).__name__}: {exc}"
        ) from exc
    incomplete_states = {
        job_id: selected_states.get(job_id, "missing")
        for job_id in selected_ids
        if selected_states.get(job_id) != "complete"
    }
    if not controller_stop.is_set():
        failures = sorted(set(failures) | set(incomplete_states))
    final_status = (
        "STOPPED"
        if controller_stop.is_set()
        else "FAILED"
        if failures
        else "COMPLETE"
    )
    _write_controller_state(
        workspace,
        status=final_status,
        action=f"Run{split.title()}",
        detail=(
            "Graceful stop honored"
            if final_status == "STOPPED"
            else f"{len(selected) - len(failures)}/{len(selected)} jobs complete"
        ),
        campaign_id=str(manifest["campaign_id"]),
        extra={
            "failures": failures,
            "incomplete_states": incomplete_states,
            "memory_gate": memory,
        },
    )
    return {
        "schema_version": "full-pipeline-evaluation-run.v1",
        "status": final_status,
        "campaign_id": manifest["campaign_id"],
        "split": split,
        "measurement_mode": measurement_mode,
        "selected_job_count": len(jobs_by_id),
        "effective_parallel_jobs": effective_parallel,
        "memory_gate": memory,
        "failures": failures,
        "incomplete_states": incomplete_states,
        "progress": progress,
    }


def _run_one(
    workspace: Path,
    manifest: Mapping[str, object],
    job: EvaluationJobSpec,
    executor: JobExecutor,
    progress_lock: threading.Lock,
    controller_stop: threading.Event,
) -> Mapping[str, object]:
    from .results import result_tree_reusable

    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    results_root = _results_root(workspace, manifest)
    result_root = results_root / job.result_relative_path
    if result_tree_reusable(result_root, job.reuse_identity):
        store.mark_reused(job.job_id, result_sha256=sha256_file(result_root / "checksums.json"))
        store.assert_integrity()
        return {"state": "complete", "reused": True}
    case_index = manifest.get("case_index")
    if not isinstance(case_index, Mapping):
        raise ValueError("campaign case_index is missing")
    cases = tuple(
        dict(case_index[case_id])
        for case_id in job.case_ids
        if isinstance(case_index.get(case_id), Mapping)
    )
    if len(cases) != job.case_count:
        raise ValueError("job cases no longer match its immutable specification")
    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    claimed = store.claim(job.job_id, owner=owner)
    if claimed is None:
        current = next(
            row for row in store.list_jobs() if row.spec.job_id == job.job_id
        )
        return {"state": current.state, "reused": current.state == "complete"}
    attempt = claimed.attempt_count
    attempt_root = workspace / "attempts" / job.job_id / f"attempt_{attempt:03d}"
    work_result = attempt_root / "result"
    attempt_root.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    heartbeat_values: dict[str, object] = {
        "completed_cases": claimed.completed_cases,
        "completed_audio_sec": claimed.completed_audio_sec,
        "current_case_id": claimed.current_case_id,
        "latest_activity": "job executor starting",
        "rolling_rtf": claimed.rolling_rtf,
        "cpu_percent": claimed.cpu_percent,
        "rss_mb": claimed.rss_mb,
        "queue_depth": claimed.queue_depth,
        "cache_hits": claimed.cache_hits,
    }
    heartbeat_values_lock = threading.Lock()
    keepalive_stop = threading.Event()
    persistence_errors: list[Exception] = []
    persistence_errors_lock = threading.Lock()

    def record_persistence_error(exc: Exception) -> None:
        with persistence_errors_lock:
            if not persistence_errors:
                persistence_errors.append(exc)
        controller_stop.set()

    def persist_heartbeat(values: Mapping[str, object]) -> None:
        try:
            store.heartbeat(
                job.job_id,
                owner=owner,
                completed_cases=int(values.get("completed_cases", 0)),
                completed_audio_sec=float(values.get("completed_audio_sec", 0.0)),
                current_case_id=(
                    str(values["current_case_id"])
                    if values.get("current_case_id") is not None
                    else None
                ),
                latest_activity=str(values.get("latest_activity") or "running"),
                rolling_rtf=_optional_float(values.get("rolling_rtf")),
                cpu_percent=_optional_float(values.get("cpu_percent")),
                rss_mb=_optional_float(values.get("rss_mb")),
                queue_depth=_optional_int(values.get("queue_depth")),
                cache_hits=_optional_int(values.get("cache_hits")),
            )
        except Exception as exc:
            record_persistence_error(exc)
            raise

    def heartbeat(**values: object) -> None:
        with heartbeat_values_lock:
            heartbeat_values.update(values)
            snapshot = dict(heartbeat_values)
        persist_heartbeat(snapshot)
        with progress_lock:
            publish_progress(
                store,
                campaign_id=str(manifest["campaign_id"]),
                output_path=workspace / CAMPAIGN_PROGRESS,
            )

    def keepalive() -> None:
        while not keepalive_stop.wait(LEASE_KEEPALIVE_INTERVAL_SEC):
            with heartbeat_values_lock:
                snapshot = dict(heartbeat_values)
            try:
                persist_heartbeat(snapshot)
            except Exception:
                return

    try:
        keepalive_thread = threading.Thread(
            target=keepalive,
            name=f"evaluation-lease-{job.job_id[:40]}",
            daemon=True,
        )
        keepalive_thread.start()
        try:
            outcome = dict(
                executor(job, cases, work_result, heartbeat, controller_stop.is_set)
            )
        finally:
            keepalive_stop.set()
            keepalive_thread.join(timeout=5.0)
        with persistence_errors_lock:
            persistence_error = persistence_errors[0] if persistence_errors else None
        if persistence_error is not None:
            raise EvaluationQueueInfrastructureError(
                f"failed to persist progress for {job.job_id}: "
                f"{type(persistence_error).__name__}: {persistence_error}"
            ) from persistence_error
        state = str(outcome.get("state") or "failed")
        completed_cases = int(outcome.get("completed_cases", 0))
        completed_audio = float(outcome.get("completed_audio_sec", 0.0))
        if state == "complete":
            if not result_tree_reusable(work_result, job.reuse_identity):
                raise RuntimeError("job executor did not publish a reusable result tree")
            _publish_completed_result(
                source=work_result,
                destination=result_root,
                attempt_archive=attempt_root / "replaced_result",
            )
            checksum = sha256_file(result_root / "checksums.json")
            store.finish(
                job.job_id,
                owner=owner,
                state="complete",
                completed_cases=job.case_count,
                completed_audio_sec=job.audio_duration_sec,
                latest_activity="checksum-bound result finalized",
                result_sha256=checksum,
            )
            finish_state = "complete"
            error = None
        elif state == "failed":
            finish_state = "failed"
            error = str(outcome.get("error") or "job executor failed")
            store.finish(
                job.job_id,
                owner=owner,
                state=finish_state,
                completed_cases=completed_cases,
                completed_audio_sec=completed_audio,
                latest_activity=error,
                last_error=error,
            )
        else:
            finish_state = "stopped" if controller_stop.is_set() else "partial"
            error = str(outcome.get("error") or "job ended before completion")
            store.finish(
                job.job_id,
                owner=owner,
                state=finish_state,
                completed_cases=completed_cases,
                completed_audio_sec=completed_audio,
                latest_activity=error,
                last_error=error,
            )
        store.record_attempt(
            job_id=job.job_id,
            attempt_number=attempt,
            state=finish_state,
            attempt_path=attempt_root,
            started_at_utc=started,
            ended_at_utc=utc_now(),
            error=error,
        )
        store.assert_integrity()
        return {**outcome, "state": finish_state}
    except (
        EvaluationQueueInfrastructureError,
        EvaluationStateCorruptionError,
        sqlite3.Error,
    ):
        controller_stop.set()
        raise
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        try:
            store.finish(
                job.job_id,
                owner=owner,
                state="failed",
                completed_cases=claimed.completed_cases,
                completed_audio_sec=claimed.completed_audio_sec,
                latest_activity=message,
                last_error=message,
            )
            store.record_attempt(
                job_id=job.job_id,
                attempt_number=attempt,
                state="failed",
                attempt_path=attempt_root,
                started_at_utc=started,
                ended_at_utc=utc_now(),
                error=message,
            )
            store.assert_integrity()
        except Exception as persistence_exc:
            controller_stop.set()
            raise EvaluationQueueInfrastructureError(
                f"failed to persist terminal state for {job.job_id}: "
                f"{type(persistence_exc).__name__}: {persistence_exc}"
            ) from persistence_exc
        return {"state": "failed", "error": message}


def _default_job_executor(
    job: EvaluationJobSpec,
    cases: Sequence[Mapping[str, object]],
    output_root: Path,
    progress: JobProgress,
    stop_requested: Callable[[], bool],
    *,
    decision_policy_registry_path: Path | None = None,
) -> Mapping[str, object]:
    from .worker import execute_evaluation_job

    return execute_evaluation_job(
        job,
        cases,
        output_root,
        progress,
        stop_requested,
        decision_policy_registry_path=decision_policy_registry_path,
    )


def _publish_completed_result(
    *, source: Path, destination: Path, attempt_archive: Path
) -> None:
    source = source.resolve()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        attempt_archive.parent.mkdir(parents=True, exist_ok=True)
        if attempt_archive.exists():
            raise RuntimeError(f"attempt archive already exists: {attempt_archive}")
        os.replace(destination, attempt_archive)
    os.replace(source, destination)


def _memory_gated_parallelism(
    *, requested: int, measurement_mode: str
) -> tuple[int, dict[str, object]]:
    if measurement_mode == "resources":
        return 1, {
            "requested": requested,
            "effective": 1,
            "reason": "matched resource measurements are serial",
        }
    available: int | None = None
    try:
        import psutil

        available = int(psutil.virtual_memory().available)
    except Exception:
        available = None
    minimum_for_two = 10 * 1024**3
    effective = min(2, requested)
    reason = "requested conservative maximum"
    if effective == 2 and available is not None and available < minimum_for_two:
        effective = 1
        reason = "available memory below the measured two-job safety floor"
    return effective, {
        "requested": requested,
        "effective": effective,
        "available_memory_bytes": available,
        "two_job_minimum_available_bytes": minimum_for_two,
        "reason": reason,
    }


def _require_reusable_complete_results(
    workspace: Path,
    manifest: Mapping[str, object],
    rows: Sequence[object],
) -> dict[str, str]:
    """Return current checksum identities only for exact reusable DB results."""

    from .results import validate_result_tree

    results_root = _results_root(workspace, manifest)
    validated: dict[str, str] = {}
    for raw in rows:
        state = getattr(raw, "state", None)
        spec = getattr(raw, "spec", None)
        if state != "complete" or spec is None:
            raise RuntimeError("result integrity gate received a non-complete job")
        result_root = results_root / spec.result_relative_path
        report = validate_result_tree(
            result_root,
            expected_reuse_identity=spec.reuse_identity,
        )
        if not report.reusable:
            detail = "; ".join(
                f"{issue.code}[{issue.logical_path}]={issue.message}"
                for issue in report.issues
            )
            raise RuntimeError(
                f"completed result is not checksum-reusable: {spec.job_id}: {detail}"
            )
        checksum_sha = sha256_file(result_root / "checksums.json")
        if getattr(raw, "result_sha256", None) != checksum_sha:
            raise RuntimeError(
                f"completed result database checksum mismatch: {spec.job_id}"
            )
        validated[str(spec.job_id)] = checksum_sha
    return dict(sorted(validated.items()))


def _require_frozen_gate(workspace: Path) -> dict[str, object]:
    path = workspace / FROZEN_GATE
    if not path.is_file():
        raise RuntimeError("RunEvaluation requires Freeze after development")
    gate = read_json(path)
    expected = gate.get("freeze_identity_sha256")
    unsigned = dict(gate)
    unsigned.pop("freeze_identity_sha256", None)
    if expected != sha256_bytes(canonical_json_bytes(unsigned)):
        raise RuntimeError("development freeze checksum is invalid")
    manifest = _manifest(workspace)
    if gate.get("campaign_id") != manifest.get("campaign_id"):
        raise RuntimeError("development freeze belongs to another campaign")
    if gate.get("campaign_identity_sha256") != manifest.get(
        "campaign_identity_sha256"
    ):
        raise RuntimeError("development freeze campaign identity differs")
    if gate.get("campaign_manifest_sha256") != sha256_file(
        workspace / CAMPAIGN_MANIFEST
    ):
        raise RuntimeError("development freeze manifest checksum differs")
    store = EvaluationStateStore(workspace / CAMPAIGN_DATABASE)
    development_rows = store.list_jobs(
        split="development", measurement_mode="accuracy"
    )
    current_results = _require_reusable_complete_results(
        workspace, manifest, development_rows
    )
    if gate.get("development_results") != current_results:
        raise RuntimeError("development result identities changed after Freeze")
    if gate.get("development_result_set_sha256") != sha256_bytes(
        canonical_json_bytes(current_results)
    ):
        raise RuntimeError("development result-set checksum differs")
    if gate.get("evaluation_material_used_for_development") is not False:
        raise RuntimeError("development/evaluation firewall is not proven")
    return gate


def _manifest(workspace: Path) -> dict[str, object]:
    path = Path(workspace).resolve() / CAMPAIGN_MANIFEST
    if not path.is_file():
        raise FileNotFoundError(
            f"campaign is not prepared; run -Action Prepare first: {path}"
        )
    return read_json(path)


def _results_root(
    workspace: Path, manifest: Mapping[str, object]
) -> Path:
    paths = workspace / "campaign_paths.json"
    if paths.is_file():
        value = read_json(paths).get("results_root")
        if isinstance(value, str) and value:
            return Path(value).resolve()
    return (DEFAULT_RESULTS_ROOT / str(manifest["campaign_id"])).resolve()


def _split_identity_sha(value: object, partition: str) -> str:
    """Extract the checksum identity from a prepared protocol partition."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{partition} protocol identity must be an object")
    digest = str(value.get("identity_sha256") or "").lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{partition} protocol identity lacks a valid SHA-256")
    return digest


def _validation_result(
    workspace: Path,
    protocol: Mapping[str, object],
    errors: Sequence[str],
    result_count: int,
    reusable_count: int,
) -> dict[str, object]:
    value = {
        "schema_version": "full-pipeline-evaluation-validation.v1",
        "valid": not errors,
        "status": "PASS" if not errors else "FAIL",
        "workspace_root": str(workspace),
        "protocol": dict(protocol),
        "result_tree_count": result_count,
        "checksum_reusable_result_count": reusable_count,
        "errors": list(errors),
        "downloads_performed": False,
        "frozen_source_protocols_modified": False,
    }
    write_json_atomic(workspace / "validation.json", value)
    return value


def _write_controller_state(
    workspace: Path,
    *,
    status: str,
    action: str,
    detail: str,
    campaign_id: str,
    extra: Mapping[str, object] | None = None,
) -> None:
    write_json_atomic(
        workspace / CONTROLLER_STATE,
        {
            "schema_version": "full-pipeline-evaluation-controller.v1",
            "campaign_id": campaign_id,
            "status": status,
            "action": action,
            "detail": detail,
            "updated_at_utc": utc_now(),
            **dict(extra or {}),
        },
    )


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None


def _select_exact_cases(
    cases: Sequence[Mapping[str, object]], case_ids: Sequence[str]
) -> tuple[dict[str, object], ...]:
    """Select exact cases in protocol order and reject unknown/duplicate IDs."""

    rows = tuple(dict(row) for row in cases)
    if not case_ids:
        return rows
    requested = tuple(str(value) for value in case_ids)
    if len(requested) != len(set(requested)):
        raise ValueError("case_ids contains duplicates")
    indexed: dict[str, dict[str, object]] = {}
    for row in rows:
        value = (
            row.get("case_id")
            or row.get("protocol_case_id")
            or row.get("recording_id")
            or row.get("utt_id")
        )
        if value is not None:
            indexed[str(value)] = row
    missing = set(requested) - set(indexed)
    if missing:
        raise ValueError("unknown exact case ID(s): " + ", ".join(sorted(missing)))
    return tuple(indexed[value] for value in requested)
