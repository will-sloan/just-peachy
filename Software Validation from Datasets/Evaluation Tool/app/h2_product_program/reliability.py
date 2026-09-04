"""H2 long-session and reliability jobs over the common file runtime.

The adapter owns scientific fixtures, fault injection, measurements, and
checksum manifests.  It does not implement inference: every audio-bearing run
uses the same shared Prompt-6/common-runtime functions used by the extended
evaluation controller.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace
import threading
import time
from typing import Callable, Mapping, Sequence

from app.full_pipeline.factory import build_file_runtime
from app.full_pipeline.product_modes import H2RuntimeTuning
from app.full_pipeline_evaluation.io import checksum_map
from app.full_pipeline_extended_evaluation import (
    DEFAULT_SHARED_CACHE,
    RELIABILITY_FAULTS,
)
from app.full_pipeline_extended_evaluation import execution as shared_execution
from app.full_pipeline_extended_evaluation.io import ensure_c_drive

from .contracts import H2Job, H2ProgramError, ProgramPaths
from .io import (
    canonical_sha256,
    read_json,
    read_jsonl,
    sha256_file,
    write_json_atomic,
    write_jsonl_atomic,
)
from .planning import PREPARED_PROTOCOL_ROOT, load_and_validate_spec


LONG_SESSION_DURATIONS_SEC = (1800.0, 3600.0)
LONG_SESSION_SOURCE_COUNTS = {"development": 4, "evaluation": 8}
SESSION_RESET_RESTART_FAULT = "session_reset_restart"
H2_RELIABILITY_FAULTS = (*RELIABILITY_FAULTS, SESSION_RESET_RESTART_FAULT)
RESULT_FILE = "job_result.json"
CHECKSUM_FILE = "checksums.json"
SUBRESULT_FILE = "result.json"
OBSERVATIONS_FILE = "session_memory_over_source_time.jsonl"
CLEANUP_RECEIPTS_DIRECTORY = "cleanup_receipts"

RuntimeBuilder = Callable[..., object]
ProgressCallback = Callable[..., None]
StorageReserveCallback = Callable[[], None]


class _ProgressJournal:
    """Durable, throttled progress shared by controller Status and operators."""

    def __init__(
        self,
        root: Path,
        job: H2Job,
        *,
        total_items: int,
        total_audio_sec: float,
        callback: ProgressCallback | None,
    ) -> None:
        self.root = root
        self.job = job
        self.total_items = total_items
        self.total_audio_sec = total_audio_sec
        self.callback = callback
        self.started = time.monotonic()
        self.last_observation_write = 0.0
        self.completed_items = 0
        self.completed_audio_sec = 0.0
        self.retry_count = 0
        self.current_item: str | None = None

    def publish(
        self,
        *,
        activity: str,
        current_audio_sec: float = 0.0,
        rolling_rtf: float | None = None,
        latest_output: Path | None = None,
        force: bool = True,
    ) -> None:
        now = time.monotonic()
        if not force and now - self.last_observation_write < 5.0:
            return
        self.last_observation_write = now
        rss_mb: float | None = None
        cpu_percent: float | None = None
        try:
            import psutil

            process = psutil.Process()
            rss_mb = process.memory_info().rss / (1024**2)
            cpu_percent = process.cpu_percent(interval=None)
        except Exception:
            pass
        audio_sec = min(
            self.total_audio_sec,
            self.completed_audio_sec + max(0.0, current_audio_sec),
        )
        payload = {
            "schema_version": "h2-reliability-progress.v1",
            "job_id": self.job.job_id,
            "job_kind": self.job.job_kind,
            "split": self.job.split,
            "pipeline_id": self.job.pipeline_id,
            "mode": self.job.mode,
            "current_item_id": self.current_item,
            "completed_items": self.completed_items,
            "total_items": self.total_items,
            "completed_audio_sec": audio_sec,
            "total_audio_sec": self.total_audio_sec,
            "percent_complete": (
                100.0 * audio_sec / self.total_audio_sec
                if self.total_audio_sec > 0
                else 0.0
            ),
            "elapsed_sec": now - self.started,
            "rolling_rtf": rolling_rtf,
            "cpu_percent": cpu_percent,
            "rss_mb": rss_mb,
            "retry_count": self.retry_count,
            "latest_activity": activity,
            "latest_output": str(latest_output) if latest_output else None,
            "model_instances": None,
            "embedding_calls": None,
            "updated_at_utc": _utc_now(),
        }
        write_json_atomic(self.root / "progress.json", payload)
        if self.callback is not None:
            self.callback(**payload)

    def start(self, item_id: str, *, attempt_number: int, output: Path) -> None:
        self.current_item = item_id
        self.retry_count += max(0, attempt_number - 1)
        self.publish(
            activity=f"starting atomic reliability item {item_id}",
            latest_output=output,
        )

    def observe(self, row: Mapping[str, object], *, target_audio_sec: float) -> None:
        source = row.get("source_time_sec")
        source_sec = (
            min(target_audio_sec, max(0.0, float(source)))
            if isinstance(source, (int, float))
            else 0.0
        )
        elapsed = row.get("elapsed_wall_sec")
        rolling_rtf = (
            float(elapsed) / source_sec
            if isinstance(elapsed, (int, float)) and source_sec > 0
            else None
        )
        self.publish(
            activity=f"running atomic reliability item {self.current_item}",
            current_audio_sec=source_sec,
            rolling_rtf=rolling_rtf,
            force=False,
        )

    def complete(
        self,
        item_id: str,
        *,
        audio_sec: float,
        output: Path,
        reused: bool,
    ) -> None:
        self.current_item = item_id
        self.completed_items += 1
        self.completed_audio_sec += audio_sec
        self.publish(
            activity=(
                f"reused checksum-valid atomic item {item_id}"
                if reused
                else f"completed atomic reliability item {item_id}"
            ),
            latest_output=output,
        )


class _ProgressObservations(list[dict[str, object]]):
    def __init__(
        self, journal: _ProgressJournal, *, target_audio_sec: float
    ) -> None:
        super().__init__()
        self.journal = journal
        self.target_audio_sec = target_audio_sec

    def append(self, row: dict[str, object]) -> None:
        super().append(row)
        self.journal.observe(row, target_audio_sec=self.target_audio_sec)


def execute_reliability_job(
    paths: ProgramPaths,
    job: H2Job,
    *,
    protocol: Mapping[str, object],
    runtime_tuning: H2RuntimeTuning | Mapping[str, object],
    stop_event: threading.Event,
    runtime_builder: RuntimeBuilder | None = None,
    progress: ProgressCallback | None = None,
    storage_reserve_callback: StorageReserveCallback | None = None,
) -> dict[str, object]:
    """Execute an H2 ``long_session`` or ``reliability`` logical job.

    ``runtime_tuning`` is required because the logical phase-6 jobs are planned
    before development selection.  The controller must pass the final strict
    tuning.  Its product mode must exactly match ``job.mode``.
    """

    if job.job_kind not in {
        "long_session",
        "long_session_evaluation",
        "reliability",
    }:
        raise H2ProgramError(
            f"H2 reliability adapter cannot execute {job.job_kind!r}"
        )
    tuning = validate_reliability_tuning(job, runtime_tuning)
    _require_execution_paths(paths)
    binding = _execution_binding(paths, job, protocol, tuning)
    result_root = _job_root(paths, job)
    if reliability_result_reusable(result_root, binding):
        result_path = result_root / RESULT_FILE
        return {
            "state": "complete",
            "reused": True,
            "result_path": str(result_path),
            "result_sha256": sha256_file(result_path),
            "result_root": str(result_root),
            "checksums_sha256": sha256_file(result_root / CHECKSUM_FILE),
        }

    result_root.mkdir(parents=True, exist_ok=True)
    source_plan = build_long_session_source_plan(
        paths,
        job,
        protocol=protocol,
    )
    write_json_atomic(result_root / "long_session_source_plan.json", source_plan)
    if job.job_kind in {"long_session", "long_session_evaluation"}:
        outcome = _execute_long_sessions(
            paths,
            job,
            binding=binding,
            tuning=tuning,
            source_plan=source_plan,
            result_root=result_root,
            stop_event=stop_event,
            runtime_builder=runtime_builder,
            progress=progress,
            storage_reserve_callback=storage_reserve_callback,
        )
    else:
        outcome = _execute_reliability_matrix(
            paths,
            job,
            binding=binding,
            tuning=tuning,
            source_plan=source_plan,
            result_root=result_root,
            stop_event=stop_event,
            runtime_builder=runtime_builder,
            progress=progress,
            storage_reserve_callback=storage_reserve_callback,
        )
    return _publish_job_result(
        job,
        binding=binding,
        result_root=result_root,
        outcome=outcome,
    )


def validate_reliability_tuning(
    job: H2Job,
    value: H2RuntimeTuning | Mapping[str, object],
) -> H2RuntimeTuning:
    """Return a strict H2 tuning whose mode exactly matches the logical job."""

    if job.pipeline_id not in {"fullpipe_v1_ag_dr_ir", "fullpipe_v1_ao_dr_ir"}:
        raise H2ProgramError(f"reliability job is not an H2 runtime: {job.job_id}")
    valid_scope = (
        job.job_kind in {"long_session", "reliability"}
        and job.split == "development"
        and job.development_only
    ) or (
        job.job_kind == "long_session_evaluation"
        and job.split == "evaluation"
        and not job.development_only
    )
    if not valid_scope:
        raise H2ProgramError(
            f"reliability split/development-only contract differs: {job.job_id}"
        )
    try:
        tuning = (
            value
            if isinstance(value, H2RuntimeTuning)
            else H2RuntimeTuning.from_mapping(value)
        )
    except (TypeError, ValueError) as exc:
        raise H2ProgramError(f"invalid final H2 reliability tuning: {exc}") from exc
    if tuning.product_mode.value != job.mode:
        raise H2ProgramError(
            "controller product mode conflicts with final runtime tuning: "
            f"job={job.mode} tuning={tuning.product_mode.value}"
        )
    return tuning


def build_long_session_source_plan(
    paths: ProgramPaths,
    job: H2Job,
    *,
    protocol: Mapping[str, object],
    target_durations_sec: Sequence[float] | None = None,
    source_rows: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Resolve the presealed development/evaluation long-source membership."""

    durations = tuple(
        float(value)
        for value in (target_durations_sec or LONG_SESSION_DURATIONS_SEC)
    )
    if not durations or any(value <= 0 or not math.isfinite(value) for value in durations):
        raise H2ProgramError("long-session durations must be finite and positive")
    spec = load_and_validate_spec(paths.config_path)
    panels = spec.get("panels")
    long_policy = panels.get("long_session") if isinstance(panels, Mapping) else None
    if not isinstance(long_policy, Mapping):
        raise H2ProgramError("H2 configuration lacks a long-session source policy")
    expected_key = f"{job.split}_recordings"
    expected_count = int(long_policy.get(expected_key) or 0)
    configured = tuple(
        float(value) * 60.0
        for value in (long_policy.get("target_duration_min") or ())
    )
    if expected_count != LONG_SESSION_SOURCE_COUNTS.get(job.split):
        raise H2ProgramError(
            f"H2 {job.split} long-session source count differs"
        )
    if target_durations_sec is None and durations != configured:
        raise H2ProgramError("H2 long-session 30/60-minute policy changed")
    rows = tuple(
        dict(row)
        for row in (
            source_rows
            if source_rows is not None
            else read_jsonl(
                PREPARED_PROTOCOL_ROOT / job.split / "case_manifest.jsonl"
            )
        )
    )
    protocol_panels = protocol.get("panels")
    split_panels = (
        protocol_panels.get(job.split)
        if isinstance(protocol_panels, Mapping)
        else None
    )
    sealed_panel = (
        split_panels.get("long_session")
        if isinstance(split_panels, Mapping)
        else None
    )
    if not isinstance(sealed_panel, Mapping):
        raise H2ProgramError(f"presealed {job.split} long-session panel is missing")
    sealed_case_ids = tuple(str(value) for value in sealed_panel.get("case_ids", ()))
    if tuple(job.case_ids) != sealed_case_ids:
        raise H2ProgramError(
            f"{job.split} long-session job membership differs from presealed panel"
        )
    by_case = {
        str(row.get("protocol_case_id") or row.get("case_id") or ""): row
        for row in rows
    }
    if any(case_id not in by_case for case_id in sealed_case_ids):
        raise H2ProgramError("presealed long-session case is absent from source manifest")
    eligible = [dict(by_case[case_id]) for case_id in sealed_case_ids]
    if canonical_sha256(eligible) != sealed_panel.get("case_manifest_sha256"):
        raise H2ProgramError("presealed long-session case-manifest hash differs")
    if any(
        row.get("partition") != job.split
        or row.get("source_key") != "product_v2"
        or not isinstance(row.get("scenario"), Mapping)
        or row["scenario"].get("long_session") is not True  # type: ignore[index]
        for row in eligible
    ):
        raise H2ProgramError("presealed long-session membership contains an invalid row")
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in eligible:
        groups[_audio_identity(row)].append(row)
    if len(groups) != expected_count:
        raise H2ProgramError(
            "declared development long recordings differ: "
            f"expected={expected_count} observed={len(groups)}"
        )
    sources = [
        _source_contract(min(group, key=_canonical_source_rank))
        for _identity, group in sorted(groups.items())
    ]
    streams = [
        {
            "stream_id": (
                f"{source['source_recording_id']}_{round(duration / 60):02d}m"
            ),
            "source_index": index,
            "source_recording_id": source["source_recording_id"],
            "source_case_id": source["source_case_id"],
            "source_audio_identity": source["source_audio_identity"],
            "target_duration_sec": duration,
            "runtime_pace": 1.0,
            "controlled_prerecorded_loopback": True,
            "physical_microphone_used": False,
        }
        for index, source in enumerate(sources, start=1)
        for duration in durations
    ]
    core = {
        "schema_version": "h2-long-session-source-plan.v1",
        "job_id": job.job_id,
        "job_identity_sha256": job.identity_sha256,
        "protocol_id": protocol.get("protocol_id"),
        "protocol_sha256": protocol.get("protocol_sha256"),
        "split": job.split,
        "development_only": job.development_only,
        "source_policy": "product_v2_scenario.long_session_true",
        "presealed_panel_case_manifest_sha256": sealed_panel.get(
            "case_manifest_sha256"
        ),
        "presealed_source_membership_sha256": sealed_panel.get(
            "source_membership_sha256"
        ),
        "presealed_case_ids": list(sealed_case_ids),
        "metadata_only_selection": True,
        "predictions_or_metrics_used": False,
        "reference_content_used_for_selection": False,
        "evaluation_material_inspected_for_selection": False,
        "evaluation_material_inspected": False,
        "heldout_execution_opened_after_freeze": job.split == "evaluation",
        "no_recalibration": job.split == "evaluation",
        "ordinary_dev_core_cases_treated_as_long_streams": False,
        "logical_job_case_ids_are_presealed_source_membership": True,
        "source_count": len(sources),
        "stream_count": len(streams),
        "target_source_audio_sec": sum(
            float(row["target_duration_sec"]) for row in streams
        ),
        "target_source_hours": sum(
            float(row["target_duration_sec"]) for row in streams
        )
        / 3600.0,
        "target_durations_sec": list(durations),
        "sources": sources,
        "streams": streams,
        "identity_scoring_scope": "RESOURCE_STATE_ONLY_EMPTY_GALLERY",
        "known_identity_or_reentry_metrics_scored": False,
        "stranger_false_known_metrics_scored": False,
    }
    return {**core, "source_plan_sha256": canonical_sha256(core)}


def reliability_result_reusable(
    result_root: Path, expected_binding: Mapping[str, object]
) -> bool:
    """Return true only for a complete, checksum-valid result of this binding."""

    try:
        result = read_json(result_root / RESULT_FILE)
        checksums = read_json(result_root / CHECKSUM_FILE)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if result.get("status") != "COMPLETE":
        return False
    if result.get("execution_binding_sha256") != expected_binding.get(
        "execution_binding_sha256"
    ):
        return False
    entries = checksums.get("entries")
    if not isinstance(entries, Mapping):
        return False
    return dict(entries) == checksum_map(
        result_root, exclude=(CHECKSUM_FILE,)
    )


def validate_reliability_result(
    paths: ProgramPaths,
    job: H2Job,
    *,
    protocol: Mapping[str, object],
    runtime_tuning: H2RuntimeTuning | Mapping[str, object],
) -> dict[str, object]:
    """Deep-validate the result tree and exact presealed source membership."""

    errors: list[str] = []
    try:
        tuning = validate_reliability_tuning(job, runtime_tuning)
        binding = _execution_binding(paths, job, protocol, tuning)
        root = _job_root(paths, job)
        if not reliability_result_reusable(root, binding):
            errors.append("reliability result checksum tree/binding is not reusable")
        expected_plan = build_long_session_source_plan(paths, job, protocol=protocol)
        actual_plan = read_json(root / "long_session_source_plan.json")
        if actual_plan != expected_plan:
            errors.append("long-session source plan differs from presealed membership")
        result = read_json(root / RESULT_FILE)
        if result.get("job_identity_sha256") != job.identity_sha256:
            errors.append("reliability result job identity differs")
        outcome = result.get("outcome")
        if not isinstance(outcome, Mapping):
            errors.append("reliability result outcome is missing")
        elif job.job_kind in {"long_session", "long_session_evaluation"}:
            expected_streams = int(expected_plan["stream_count"])
            if outcome.get("expected_subtests") != expected_streams:
                errors.append("long-session expected stream count differs")
            if outcome.get("completed_subtests") != expected_streams:
                errors.append("long-session membership is incomplete")
            if outcome.get("identity_scoring_scope") != (
                "RESOURCE_STATE_ONLY_EMPTY_GALLERY"
            ):
                errors.append("long-session identity claim scope differs")
            if outcome.get("known_identity_or_reentry_metrics_scored") is not False:
                errors.append("long-session overclaims known identity/re-entry scoring")
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    return {
        "schema_version": "h2-reliability-result-validation.v1",
        "job_id": job.job_id,
        "valid": not errors,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def _execute_long_sessions(
    paths: ProgramPaths,
    job: H2Job,
    *,
    binding: Mapping[str, object],
    tuning: H2RuntimeTuning,
    source_plan: Mapping[str, object],
    result_root: Path,
    stop_event: threading.Event,
    runtime_builder: RuntimeBuilder | None,
    progress: ProgressCallback | None,
    storage_reserve_callback: StorageReserveCallback | None,
) -> dict[str, object]:
    sources = {
        str(row["source_recording_id"]): dict(row)
        for row in source_plan["sources"]  # type: ignore[index]
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, object]] = []
    all_observations: list[dict[str, object]] = []
    cleanup_receipts: list[dict[str, object]] = []
    expected = len(source_plan["streams"])  # type: ignore[arg-type]
    total_audio_sec = sum(
        float(row["target_duration_sec"])
        for row in source_plan["streams"]  # type: ignore[index]
        if isinstance(row, Mapping)
    )
    journal = _ProgressJournal(
        result_root,
        job,
        total_items=expected,
        total_audio_sec=total_audio_sec,
        callback=progress,
    )
    for raw_stream in source_plan["streams"]:  # type: ignore[index]
        stream = dict(raw_stream)
        stream_id = str(stream["stream_id"])
        subroot = result_root / "long_sessions" / stream_id
        expected_subbinding = _subbinding(binding, "long_session", stream_id)
        if _subresult_reusable(subroot, expected_subbinding):
            reused_payload = read_json(subroot / SUBRESULT_FILE)
            materialization = reused_payload.get("materialization")
            if not isinstance(materialization, Mapping) or not isinstance(
                materialization.get("output_path"), str
            ):
                raise H2ProgramError(
                    f"reusable long subresult lacks its materialization path: {stream_id}"
                )
            input_receipt = _cleanup_long_input_after_publish(
                result_root=result_root,
                subroot=subroot,
                binding=expected_subbinding,
                stream_id=stream_id,
                input_path=Path(str(materialization["output_path"])),
            )
            rows.append(reused_payload)
            cleanup = reused_payload.get("cleanup")
            if isinstance(cleanup, Mapping) and isinstance(
                cleanup.get("runtime"), Mapping
            ):
                cleanup_receipts.append(dict(cleanup["runtime"]))
            cleanup_receipts.append(input_receipt)
            all_observations.extend(_read_optional_jsonl(subroot / OBSERVATIONS_FILE))
            journal.complete(
                stream_id,
                audio_sec=float(stream["target_duration_sec"]),
                output=subroot / SUBRESULT_FILE,
                reused=True,
            )
            continue
        if stop_event.is_set():
            break
        if storage_reserve_callback is not None:
            try:
                storage_reserve_callback()
            except Exception as exc:
                stop_event.set()
                journal.current_item = stream_id
                journal.publish(
                    activity=(
                        "storage reserve blocked before atomic long stream: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    latest_output=subroot,
                )
                break
        source = sources[str(stream["source_recording_id"])]
        input_path, materialization = _materialize_long_stream(
            source,
            stream,
            destination_root=result_root / "inputs",
        )
        attempt_root = _next_attempt_root(subroot)
        runtime_root = attempt_root / "runtime"
        attempt_number = int(attempt_root.name.removeprefix("attempt_"))
        journal.start(
            stream_id,
            attempt_number=attempt_number,
            output=attempt_root,
        )
        observations: list[dict[str, object]] = _ProgressObservations(
            journal,
            target_audio_sec=float(stream["target_duration_sec"]),
        )
        started = time.monotonic()
        harness_error: str | None = None
        try:
            runtime_result = shared_execution.run_controlled_file_session(
                SimpleNamespace(pipeline_id=job.pipeline_id, job_id=stream_id),
                input_path=input_path,
                output_root=runtime_root,
                duration_sec=float(stream["target_duration_sec"]),
                pace=1.0,
                enrollment_root=subroot / "enrollment_empty",
                decision_policy_registry_path=None,
                source_case={},
                stop_requested=lambda: False,
                runtime_tuning=tuning,
                product_mode=job.mode,
                runtime_builder=runtime_builder,
                status_observations=observations,
            )
        except Exception as exc:
            harness_error = f"{type(exc).__name__}: {exc}"
            runtime_result = {
                "completion_state": "failed",
                "errors": [harness_error],
            }
        wall_sec = time.monotonic() - started
        contextual = [
            {"stream_id": stream_id, **row} for row in observations
        ]
        write_jsonl_atomic(subroot / OBSERVATIONS_FILE, contextual)
        evidence = _runtime_evidence(
            runtime_root,
            completions=[str(runtime_result.get("completion_state") or "failed")],
            wall_sec=wall_sec,
            observations=observations,
            tuning=tuning,
        )
        binding_evidence = _runtime_tuning_evidence(runtime_root, tuning, job.mode)
        target = float(stream["target_duration_sec"])
        assertions = [
            _assertion(
                "exact_materialized_duration",
                abs(float(materialization["duration_sec"]) - target) <= 1 / 16000,
                expected=target,
                observed=materialization["duration_sec"],
            ),
            _assertion(
                "common_runtime_completed",
                runtime_result.get("completion_state") == "complete",
                expected="complete",
                observed=runtime_result.get("completion_state"),
            ),
            _assertion(
                "true_source_clock_pacing",
                wall_sec >= target * 0.90,
                expected=f">={target * 0.90}",
                observed=wall_sec,
            ),
            _assertion(
                "strict_tuning_provenance",
                binding_evidence["status"] == "PASS",
                expected=tuning.identity_sha256,
                observed=binding_evidence,
            ),
            _assertion(
                "bounded_state_over_source_time",
                evidence["bounded_state_evidence"]["status"] == "PASS",
                expected="PASS",
                observed=evidence["bounded_state_evidence"],
            ),
        ]
        status = (
            "STOPPED"
            if runtime_result.get("completion_state") == "stopped"
            else (
                "PASS"
                if all(row["status"] == "PASS" for row in assertions)
                else "FAIL"
            )
        )
        runtime_cleanup = _cleanup_runtime_before_seal(
            subroot=subroot,
            attempt_root=attempt_root,
            runtime_root=runtime_root,
            item_kind="long_session",
            item_id=stream_id,
            harness_status=status,
        )
        input_cleanup_policy: dict[str, object]
        if status == "PASS":
            input_cleanup_policy = {
                "schema_version": "h2-long-input-cleanup-policy.v1",
                "cleanup_kind": "materialized_long_input",
                "item_id": stream_id,
                "status": "PENDING_POST_SUBRESULT_SEAL",
                "reason": "input deletion is forbidden before checksum seal",
            }
        else:
            input_cleanup_policy = _retained_long_input_receipt(
                input_path,
                stream_id=stream_id,
                harness_status=status,
            )
        payload = {
            "schema_version": "h2-long-session-result.v1",
            "execution_binding_sha256": expected_subbinding[
                "execution_binding_sha256"
            ],
            "stream_id": stream_id,
            "harness_status": status,
            "controlled_prerecorded_loopback": True,
            "physical_microphone_or_device_behavior_claimed": False,
            "identity_scoring_scope": "RESOURCE_STATE_ONLY_EMPTY_GALLERY",
            "known_identity_or_reentry_metrics_scored": False,
            "stranger_false_known_metrics_scored": False,
            "enrollment_gallery": "EMPTY",
            "source": source,
            "materialization": materialization,
            "runtime_pace": 1.0,
            "attempt_root": str(attempt_root),
            "elapsed_wall_sec": wall_sec,
            "harness_error": harness_error,
            "runtime_tuning_evidence": binding_evidence,
            "measurements": evidence,
            "assertions": assertions,
            "cleanup": {
                "runtime": runtime_cleanup,
                "materialized_input": input_cleanup_policy,
            },
        }
        _publish_subresult(subroot, payload, expected_subbinding)
        if not _subresult_checksum_valid(subroot, expected_subbinding):
            raise H2ProgramError(
                f"long-session subresult failed its post-publish checksum: {stream_id}"
            )
        cleanup_receipts.append(runtime_cleanup)
        if status == "PASS":
            cleanup_receipts.append(
                _cleanup_long_input_after_publish(
                    result_root=result_root,
                    subroot=subroot,
                    binding=expected_subbinding,
                    stream_id=stream_id,
                    input_path=input_path,
                )
            )
        else:
            cleanup_receipts.append(input_cleanup_policy)
        rows.append(payload)
        all_observations.extend(contextual)
        if status == "PASS":
            journal.complete(
                stream_id,
                audio_sec=target,
                output=subroot / SUBRESULT_FILE,
                reused=False,
            )
        if status == "STOPPED":
            break
    write_jsonl_atomic(result_root / "long_session_results.jsonl", rows)
    write_jsonl_atomic(result_root / OBSERVATIONS_FILE, all_observations)
    complete = len(rows) == expected and all(
        row.get("harness_status") == "PASS" for row in rows
    )
    stopped = (stop_event.is_set() and len(rows) < expected) or any(
        row.get("harness_status") == "STOPPED" for row in rows
    )
    return {
        "status": "STOPPED" if stopped else ("COMPLETE" if complete else "FAILED"),
        "expected_subtests": expected,
        "completed_subtests": len(rows),
        "pass_count": sum(row.get("harness_status") == "PASS" for row in rows),
        "fail_count": sum(row.get("harness_status") == "FAIL" for row in rows),
        "unsupported_count": 0,
        "progress_path": str(result_root / "progress.json"),
        "atomic_boundary_semantics": "finish_current_stream_then_stop",
        "identity_scoring_scope": "RESOURCE_STATE_ONLY_EMPTY_GALLERY",
        "known_identity_or_reentry_metrics_scored": False,
        "subresults": _subresult_bindings(result_root / "long_sessions", rows),
        "cleanup": _cleanup_summary(cleanup_receipts),
    }


def _execute_reliability_matrix(
    paths: ProgramPaths,
    job: H2Job,
    *,
    binding: Mapping[str, object],
    tuning: H2RuntimeTuning,
    source_plan: Mapping[str, object],
    result_root: Path,
    stop_event: threading.Event,
    runtime_builder: RuntimeBuilder | None,
    progress: ProgressCallback | None,
    storage_reserve_callback: StorageReserveCallback | None,
) -> dict[str, object]:
    del paths
    source = dict(source_plan["sources"][0])  # type: ignore[index]
    input_path = _resolve_source(source)
    rows: list[dict[str, object]] = []
    all_observations: list[dict[str, object]] = []
    cleanup_receipts: list[dict[str, object]] = []
    durations = {
        fault: (60.0 if fault == "continuous_session" else 30.0)
        for fault in H2_RELIABILITY_FAULTS
    }
    expected = len(H2_RELIABILITY_FAULTS)
    journal = _ProgressJournal(
        result_root,
        job,
        total_items=expected,
        total_audio_sec=sum(durations.values()),
        callback=progress,
    )
    for fault in H2_RELIABILITY_FAULTS:
        subroot = result_root / "reliability" / fault
        expected_subbinding = _subbinding(binding, "reliability", fault)
        if _subresult_reusable(subroot, expected_subbinding):
            reused_payload = read_json(subroot / SUBRESULT_FILE)
            rows.append(reused_payload)
            cleanup = reused_payload.get("cleanup")
            if isinstance(cleanup, Mapping) and isinstance(
                cleanup.get("runtime"), Mapping
            ):
                cleanup_receipts.append(dict(cleanup["runtime"]))
            all_observations.extend(_read_optional_jsonl(subroot / OBSERVATIONS_FILE))
            journal.complete(
                fault,
                audio_sec=durations[fault],
                output=subroot / SUBRESULT_FILE,
                reused=True,
            )
            continue
        if stop_event.is_set():
            break
        if storage_reserve_callback is not None:
            try:
                storage_reserve_callback()
            except Exception as exc:
                stop_event.set()
                journal.current_item = fault
                journal.publish(
                    activity=(
                        "storage reserve blocked before atomic fault scenario: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    latest_output=subroot,
                )
                break
        duration = durations[fault]
        attempt_root = _next_attempt_root(subroot)
        attempt_number = int(attempt_root.name.removeprefix("attempt_"))
        journal.start(
            fault,
            attempt_number=attempt_number,
            output=attempt_root,
        )
        observations: list[dict[str, object]] = _ProgressObservations(
            journal,
            target_audio_sec=duration,
        )
        atomic_stop_event = threading.Event()
        started = time.monotonic()
        try:
            if fault == SESSION_RESET_RESTART_FAULT:
                raw = _run_session_reset_restart(
                    job,
                    tuning=tuning,
                    input_path=input_path,
                    output_root=attempt_root / "runtime",
                    duration_sec=duration,
                    stop_event=atomic_stop_event,
                    runtime_builder=runtime_builder,
                    observations=observations,
                )
            else:
                raw = shared_execution.run_reliability_fault(
                    {
                        "fault_id": fault,
                        "target_duration_sec": duration,
                        "source_case": {},
                    },
                    spec=SimpleNamespace(pipeline_id=job.pipeline_id, job_id=fault),
                    input_path=input_path,
                    output_root=attempt_root / "runtime",
                    stop_requested=lambda: False,
                    decision_policy_registry_path=None,
                    runtime_tuning=tuning,
                    product_mode=job.mode,
                    runtime_builder=runtime_builder,
                    status_observations=observations,
                )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raw = {
                "harness_status": "FAIL",
                "fault_injected": False,
                "unsupported_reason": None,
                "error": error,
                "injection": {"harness_exception": error},
                "device_inventory": [],
                "observed_completion_states": ["failed"],
                "assertions": [
                    _assertion(
                        "harness_raised_no_exception",
                        False,
                        expected=None,
                        observed=error,
                    )
                ],
            }
        wall_sec = time.monotonic() - started
        contextual = [{"fault_id": fault, **row} for row in observations]
        write_jsonl_atomic(subroot / OBSERVATIONS_FILE, contextual)
        runtime_root = attempt_root / "runtime"
        completions = [str(value) for value in raw.get("observed_completion_states", [])]
        evidence = _runtime_evidence(
            runtime_root,
            completions=completions,
            wall_sec=wall_sec,
            observations=observations,
            tuning=tuning,
        )
        unsupported_without_runtime = fault in {
            "microphone_device_selection",
            "device_reconnect",
        }
        binding_evidence = _runtime_tuning_evidence(runtime_root, tuning, job.mode)
        assertions = [dict(row) for row in raw.get("assertions", [])]
        if not unsupported_without_runtime:
            assertions.append(
                _assertion(
                    "strict_tuning_provenance",
                    binding_evidence["status"] == "PASS",
                    expected=tuning.identity_sha256,
                    observed=binding_evidence,
                )
            )
        status = str(raw.get("harness_status") or "FAIL")
        if status == "PASS" and any(row.get("status") != "PASS" for row in assertions):
            status = "FAIL"
        runtime_cleanup = _cleanup_runtime_before_seal(
            subroot=subroot,
            attempt_root=attempt_root,
            runtime_root=runtime_root,
            item_kind="reliability_fault",
            item_id=fault,
            harness_status=status,
        )
        payload = {
            "schema_version": "h2-reliability-fault-result.v1",
            "execution_binding_sha256": expected_subbinding[
                "execution_binding_sha256"
            ],
            "fault_id": fault,
            "declared_test_duration_sec": duration,
            "harness_status": status,
            "controlled_prerecorded_loopback": True,
            "physical_human_microphone_claimed": False,
            "physical_device_behavior_claimed": False,
            "identity_scoring_scope": "RESOURCE_STATE_ONLY_EMPTY_GALLERY",
            "known_identity_or_reentry_metrics_scored": False,
            "runtime_tuning_evidence": (
                {
                    "status": "NOT_APPLICABLE_NO_RUNTIME",
                    "reason": "fault is deterministically uninjectable",
                }
                if unsupported_without_runtime
                else binding_evidence
            ),
            "measurements": evidence,
            "assertions": assertions,
            "fault_injected": bool(raw.get("fault_injected")),
            "unsupported_reason": raw.get("unsupported_reason"),
            "error": raw.get("error"),
            "injection": raw.get("injection", {}),
            "device_inventory": raw.get("device_inventory", []),
            "observed_completion_states": completions,
            "elapsed_wall_sec": wall_sec,
            "attempt_root": str(attempt_root),
            "cleanup": {"runtime": runtime_cleanup},
        }
        _publish_subresult(subroot, payload, expected_subbinding)
        if not _subresult_checksum_valid(subroot, expected_subbinding):
            raise H2ProgramError(
                f"reliability subresult failed its post-publish checksum: {fault}"
            )
        cleanup_receipts.append(runtime_cleanup)
        rows.append(payload)
        all_observations.extend(contextual)
        if status in {"PASS", "UNSUPPORTED"}:
            journal.complete(
                fault,
                audio_sec=duration,
                output=subroot / SUBRESULT_FILE,
                reused=False,
            )
    write_jsonl_atomic(result_root / "reliability_results.jsonl", rows)
    write_jsonl_atomic(result_root / OBSERVATIONS_FILE, all_observations)
    explicit = {"PASS", "FAIL", "UNSUPPORTED"}
    complete = len(rows) == expected and all(
        row.get("harness_status") in explicit for row in rows
    )
    failed = any(row.get("harness_status") == "FAIL" for row in rows)
    stopped = stop_event.is_set() and len(rows) < expected
    return {
        "status": (
            "STOPPED"
            if stopped
            else ("COMPLETE" if complete and not failed else "FAILED")
        ),
        "expected_subtests": expected,
        "completed_subtests": len(rows),
        "pass_count": sum(row.get("harness_status") == "PASS" for row in rows),
        "fail_count": sum(row.get("harness_status") == "FAIL" for row in rows),
        "unsupported_count": sum(
            row.get("harness_status") == "UNSUPPORTED" for row in rows
        ),
        "all_outcomes_explicit": complete,
        "progress_path": str(result_root / "progress.json"),
        "atomic_boundary_semantics": "finish_current_fault_then_stop",
        "identity_scoring_scope": "RESOURCE_STATE_ONLY_EMPTY_GALLERY",
        "subresults": _subresult_bindings(result_root / "reliability", rows),
        "cleanup": _cleanup_summary(cleanup_receipts),
    }


def _run_session_reset_restart(
    job: H2Job,
    *,
    tuning: H2RuntimeTuning,
    input_path: Path,
    output_root: Path,
    duration_sec: float,
    stop_event: threading.Event,
    runtime_builder: RuntimeBuilder | None,
    observations: list[dict[str, object]],
) -> dict[str, object]:
    """Reset a paused session, then start a distinct fresh runtime session."""

    builder = runtime_builder or build_file_runtime
    per_session = duration_sec / 2.0

    def construct(root: Path, suffix: str) -> object:
        return builder(
            pipeline_id=job.pipeline_id,
            input_path=input_path,
            output_root=root,
            enrollment_root=output_root / "enrollment_empty",
            session_id=f"{job.job_id}_{suffix}",
            pace=1.0,
            duration_sec=per_session,
            telemetry_enabled=True,
            cache_root=DEFAULT_SHARED_CACHE,
            product_mode=job.mode,
            runtime_tuning=tuning,
        )

    first = construct(output_root / "session_before_restart", "before_restart")
    holder: dict[str, Mapping[str, object]] = {}
    failures: list[BaseException] = []

    def run_first() -> None:
        try:
            holder["first"] = first.run()  # type: ignore[attr-defined]
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=run_first, daemon=True)
    thread.start()
    shared_execution._wait_running(first, timeout_sec=60.0)  # noqa: SLF001
    injection_at = min(5.0, per_session / 3.0)
    deadline = time.monotonic() + max(60.0, injection_at * 10.0)
    while thread.is_alive():
        status = first.status()  # type: ignore[attr-defined]
        shared_execution._observe_runtime_status(  # noqa: SLF001
            first,
            observations,
            elapsed_wall_sec=max(0.0, time.monotonic() - (deadline - 60.0)),
        )
        if float(status.get("source_time_sec") or 0.0) >= injection_at:
            break
        if stop_event.is_set() or time.monotonic() >= deadline:
            first.request_stop()  # type: ignore[attr-defined]
            break
        time.sleep(0.1)
    first.request_pause()  # type: ignore[attr-defined]
    reset = dict(first.reset_session(preserve_transcript=True))  # type: ignore[attr-defined]
    after_reset = dict(first.status())  # type: ignore[attr-defined]
    first.request_resume()  # type: ignore[attr-defined]
    while thread.is_alive():
        if stop_event.is_set():
            first.request_stop()  # type: ignore[attr-defined]
        shared_execution._observe_runtime_status(  # noqa: SLF001
            first,
            observations,
            elapsed_wall_sec=0.0,
        )
        thread.join(timeout=0.5)
    if failures:
        raise failures[0]
    second = construct(output_root / "session_after_restart", "after_restart")
    holder["second"] = shared_execution._run_with_stop(  # noqa: SLF001
        second,
        stop_requested=stop_event.is_set,
        status_observations=observations,
    )
    completions = [
        str(holder[key].get("completion_state") or "failed")
        for key in ("first", "second")
    ]
    bounded = after_reset.get("bounded_session_state")
    reset_cleared = isinstance(bounded, Mapping) and all(
        int(bounded.get(key) or 0) == 0
        for key in (
            "identity_observation_count",
            "identity_cluster_count",
            "session_memory_roster_count",
            "session_memory_history_count",
        )
    )
    assertions = [
        _assertion(
            "session_reset_executed",
            reset.get("action") == "reset_session",
            expected="reset_session",
            observed=reset,
        ),
        _assertion(
            "volatile_state_cleared_on_reset",
            reset_cleared,
            expected=True,
            observed=bounded,
        ),
        _assertion(
            "fresh_runtime_session_started",
            completions == ["complete", "complete"],
            expected=["complete", "complete"],
            observed=completions,
        ),
    ]
    status = "PASS" if all(row["status"] == "PASS" for row in assertions) else "FAIL"
    return {
        "harness_status": status,
        "fault_injected": True,
        "unsupported_reason": None,
        "error": None if status == "PASS" else "reset/restart assertion failed",
        "injection": {"reset_result": reset, "fresh_runtime_constructed": True},
        "device_inventory": [],
        "observed_completion_states": completions,
        "assertions": assertions,
    }


def _runtime_evidence(
    root: Path,
    *,
    completions: Sequence[str],
    wall_sec: float,
    observations: Sequence[Mapping[str, object]],
    tuning: H2RuntimeTuning,
) -> dict[str, object]:
    events = [
        row
        for path in root.rglob("events/events.jsonl")
        for row in _read_optional_jsonl(path)
    ]
    metrics = [
        read_json(path)
        for path in root.rglob("metrics/runtime_metrics.json")
        if path.is_file()
    ]
    telemetry = [
        row
        for path in root.rglob("telemetry/resource_samples.jsonl")
        for row in _read_optional_jsonl(path)
    ]
    event_counts = Counter(str(row.get("event_type") or "unknown") for row in events)
    source_by_session: dict[str, float] = defaultdict(float)
    for row in events:
        capture = row.get("capture_timestamps")
        end = capture.get("audio_end_sec") if isinstance(capture, Mapping) else None
        if isinstance(end, (int, float)) and math.isfinite(float(end)):
            session = str(row.get("session_id") or "unknown")
            source_by_session[session] = max(source_by_session[session], float(end))
    processed_source_sec = sum(source_by_session.values())
    queue_rows = [
        dict(value)
        for document in metrics
        if isinstance((value := document.get("queue")), Mapping)
    ]
    count_rows = [
        dict(value)
        for document in metrics
        if isinstance((value := document.get("counts")), Mapping)
    ]
    deadline = {
        str(key): sum(int(row.get(key) or 0) for row in count_rows)
        for key in sorted(
            {
                str(key)
                for row in count_rows
                for key in row
                if "deadline" in str(key).casefold()
            }
        )
    }
    rss_values = [
        int(row["process_rss_bytes"])
        for row in telemetry
        if isinstance(row.get("process_rss_bytes"), (int, float))
    ]
    bounded = _bounded_state_evidence(observations, tuning)
    return {
        "completion_states": list(completions),
        "all_sessions_completed": bool(completions)
        and all(value == "complete" for value in completions),
        "event_count": len(events),
        "event_type_counts": dict(sorted(event_counts.items())),
        "transcript_revision_count": sum(
            int(row.get("transcript_revisions") or 0) for row in count_rows
        ),
        "asr_partial_revision_count": sum(
            int(
                document.get("asr", {}).get("partial_revision_count")  # type: ignore[union-attr]
                or 0
            )
            for document in metrics
            if isinstance(document.get("asr"), Mapping)
        ),
        "identity_revision_event_count": sum(
            "identity" in str(row.get("event_type") or "").casefold()
            and "revision" in str(row.get("event_type") or "").casefold()
            for row in events
        ),
        "cluster_revision_event_count": sum(
            "cluster" in str(row.get("event_type") or "").casefold()
            and "revision" in str(row.get("event_type") or "").casefold()
            for row in events
        ),
        "maximum_queue_depth": (
            max(int(row.get("maximum_observed_depth") or 0) for row in queue_rows)
            if queue_rows
            else None
        ),
        "dropped_frame_count": (
            sum(int(row.get("dropped_frames") or 0) for row in queue_rows)
            if queue_rows
            else None
        ),
        "deadline_counters": deadline or None,
        "deadline_counter_status": (
            "EMITTED" if deadline else "UNSUPPORTED_NO_EMITTED_DEADLINE_COUNTER"
        ),
        "processed_source_time_sec": (
            processed_source_sec if processed_source_sec > 0 else None
        ),
        "elapsed_wall_sec": wall_sec,
        "real_time_factor": (
            wall_sec / processed_source_sec if processed_source_sec > 0 else None
        ),
        "real_time_factor_status": (
            "COMPUTED_FROM_EVENT_SOURCE_CLOCK"
            if processed_source_sec > 0
            else "UNSUPPORTED_NO_EVENT_SOURCE_CLOCK_DURATION"
        ),
        "peak_process_rss_bytes": max(rss_values) if rss_values else None,
        "peak_process_rss_status": (
            "EMITTED" if rss_values else "UNSUPPORTED_NO_RSS_TELEMETRY"
        ),
        "telemetry_sample_count": len(telemetry),
        "bounded_state_evidence": bounded,
    }


def _bounded_state_evidence(
    observations: Sequence[Mapping[str, object]], tuning: H2RuntimeTuning
) -> dict[str, object]:
    rows = [
        dict(row)
        for row in observations
        if isinstance(row.get("bounded_session_state"), Mapping)
    ]
    violations: list[dict[str, object]] = []
    prior_source_by_session: dict[str, float] = {}
    maxima: Counter[str] = Counter()
    for index, row in enumerate(rows):
        source = row.get("source_time_sec")
        if isinstance(source, (int, float)):
            current = float(source)
            session_id = str(row.get("session_id") or "unknown_session")
            prior_source = prior_source_by_session.get(session_id)
            if prior_source is not None and current + 1e-9 < prior_source:
                violations.append(
                    {
                        "sample_index": index,
                        "session_id": session_id,
                        "bound": "source_clock_nondecreasing",
                        "observed": current,
                        "prior": prior_source,
                    }
                )
            prior_source_by_session[session_id] = current
        bounded = dict(row["bounded_session_state"])  # type: ignore[arg-type]
        memory = row.get("session_memory")
        memory_map = dict(memory) if isinstance(memory, Mapping) else {}
        checks = {
            "identity_observation_count": (
                int(bounded.get("identity_observation_count") or 0),
                tuning.maximum_session_speakers
                * tuning.maximum_identity_observations_per_cluster,
            ),
            "identity_cluster_count": (
                int(bounded.get("identity_cluster_count") or 0),
                tuning.maximum_session_speakers,
            ),
            "session_memory_roster_count": (
                int(memory_map.get("roster_count") or 0),
                tuning.maximum_roster_entries,
            ),
            "session_memory_history_count": (
                int(memory_map.get("history_count") or 0),
                tuning.maximum_session_event_history,
            ),
        }
        cluster_count = max(1, checks["identity_cluster_count"][0])
        checks["identity_history_count"] = (
            int(bounded.get("identity_history_count") or 0),
            cluster_count * tuning.maximum_identity_history_per_cluster,
        )
        for name, (observed, bound) in checks.items():
            maxima[name] = max(maxima[name], observed)
            if observed > bound:
                violations.append(
                    {
                        "sample_index": index,
                        "source_time_sec": source,
                        "bound": name,
                        "maximum": bound,
                        "observed": observed,
                    }
                )
    return {
        "status": "PASS" if rows and not violations else "FAIL",
        "measurement_clock": "normalized_audio_source_time_sec",
        "sample_count": len(rows),
        "maximum_observed_cardinalities": dict(sorted(maxima.items())),
        "violations": violations,
        "configured_bounds": {
            "maximum_identity_observations_per_cluster": (
                tuning.maximum_identity_observations_per_cluster
            ),
            "maximum_session_speakers": tuning.maximum_session_speakers,
            "maximum_identity_history_per_cluster": (
                tuning.maximum_identity_history_per_cluster
            ),
            "maximum_roster_entries": tuning.maximum_roster_entries,
            "maximum_session_event_history": tuning.maximum_session_event_history,
        },
    }


def _runtime_tuning_evidence(
    root: Path, tuning: H2RuntimeTuning, mode: str
) -> dict[str, object]:
    paths = sorted(root.rglob("manifests/provenance.json"))
    rows: list[dict[str, object]] = []
    for path in paths:
        value = read_json(path)
        raw = value.get("h2_runtime_tuning")
        observed = dict(raw) if isinstance(raw, Mapping) else {}
        rows.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "runtime_tuning_sha256": observed.get("identity_sha256"),
                "product_mode": observed.get("product_mode"),
                "matches": observed.get("identity_sha256") == tuning.identity_sha256
                and observed.get("product_mode") == mode,
            }
        )
    return {
        "status": "PASS" if rows and all(row["matches"] for row in rows) else "FAIL",
        "expected_runtime_tuning_sha256": tuning.identity_sha256,
        "expected_product_mode": mode,
        "runtime_session_count": len(rows),
        "sessions": rows,
    }


def _execution_binding(
    paths: ProgramPaths,
    job: H2Job,
    protocol: Mapping[str, object],
    tuning: H2RuntimeTuning,
) -> dict[str, object]:
    protocol_sha = str(protocol.get("protocol_sha256") or "")
    if len(protocol_sha) != 64:
        raise H2ProgramError("H2 reliability protocol identity is absent")
    source_files = {
        "handler": Path(__file__),
        "shared_extended_execution": Path(shared_execution.__file__),
        "common_runtime_factory": Path(build_file_runtime.__code__.co_filename),
    }
    core = {
        "schema_version": "h2-reliability-execution-binding.v1",
        "job_id": job.job_id,
        "job_identity_sha256": job.identity_sha256,
        "job_kind": job.job_kind,
        "split": job.split,
        "development_only": job.development_only,
        "heldout_no_recalibration": job.split == "evaluation",
        "protocol_id": protocol.get("protocol_id"),
        "protocol_sha256": protocol_sha,
        "config_path": str(paths.config_path),
        "config_sha256": sha256_file(paths.config_path),
        "pipeline_id": job.pipeline_id,
        "product_mode": tuning.product_mode.value,
        "runtime_tuning": tuning.to_jsonable(),
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
        "result_affecting_code": {
            name: {
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
            }
            for name, path in source_files.items()
        },
        "runtime_inference_implementation": (
            "app.full_pipeline_extended_evaluation.execution shared file runtime"
        ),
        "controlled_prerecorded_loopback": True,
        "physical_microphone_claimed": False,
        "identity_scoring_scope": "RESOURCE_STATE_ONLY_EMPTY_GALLERY",
        "storage_drive": "C:",
    }
    return {**core, "execution_binding_sha256": canonical_sha256(core)}


def _subbinding(
    binding: Mapping[str, object], kind: str, discriminator: str
) -> dict[str, object]:
    core = {
        "parent_execution_binding_sha256": binding["execution_binding_sha256"],
        "subtest_kind": kind,
        "subtest_id": discriminator,
    }
    return {**core, "execution_binding_sha256": canonical_sha256(core)}


def _materialize_long_stream(
    source: Mapping[str, object],
    stream: Mapping[str, object],
    *,
    destination_root: Path,
) -> tuple[Path, dict[str, object]]:
    source_path = _resolve_source(source)
    duration = float(stream["target_duration_sec"])
    destination = ensure_c_drive(
        destination_root / f"{stream['stream_id']}.wav",
        label="H2 long-session loopback WAV",
    )
    sidecar = destination.with_suffix(".materialization.json")
    recipe = {
        "schema_version": "h2-long-session-materialization-recipe.v1",
        "source_path": str(source_path),
        "source_sha256": sha256_file(source_path),
        "source_audio_identity": source["source_audio_identity"],
        "target_duration_sec": duration,
        "sample_rate_hz": 16000,
        "channels": 1,
        "method": "deterministic_whole_source_repeat_then_exact_frame_truncate",
    }
    recipe_sha = canonical_sha256(recipe)
    if destination.is_file() or sidecar.is_file():
        if not destination.is_file() or not sidecar.is_file():
            raise H2ProgramError("partial long-session materialization exists")
        existing = read_json(sidecar)
        if (
            existing.get("recipe_sha256") != recipe_sha
            or existing.get("output_sha256") != sha256_file(destination)
        ):
            raise H2ProgramError("existing long-session materialization differs")
    else:
        shared_execution._write_repeated_wav(  # noqa: SLF001
            source_path,
            destination,
            duration_sec=duration,
        )
        write_json_atomic(
            sidecar,
            {
                **recipe,
                "recipe_sha256": recipe_sha,
                "output_path": str(destination),
                "output_sha256": sha256_file(destination),
                "duration_sec": shared_execution._audio_duration(destination),  # noqa: SLF001
            },
        )
    value = read_json(sidecar)
    return destination, value


def _resolve_source(source: Mapping[str, object]) -> Path:
    return shared_execution._resolve_audio(  # noqa: SLF001
        str(source["audio_logical_path"]),
        expected_sha256=source["audio_sha256"],
    )


def _source_contract(row: Mapping[str, object]) -> dict[str, object]:
    scenario = row.get("scenario")
    return {
        "canonical_protocol_case_id": row.get("protocol_case_id"),
        "source_case_id": row.get("protocol_case_id"),
        "source_recording_id": row.get("source_case_id"),
        "source_audio_identity": _audio_identity(row),
        "audio_logical_path": row.get("audio_logical_path"),
        "audio_sha256": str(row.get("audio_sha256") or "").casefold(),
        "pcm_sha256": str(row.get("pcm_sha256") or "").casefold(),
        "source_duration_sec": float(row.get("duration_sec") or 0.0),
        "sample_rate_hz": int(row.get("sample_rate_hz") or 0),
        "channels": int(row.get("channels") or 0),
        "scenario_id": row.get("scenario_id"),
        "scenario": dict(scenario) if isinstance(scenario, Mapping) else {},
        "canonical_overlay_row": row.get("overlay_id"),
        "canonical_gallery_requested_size": row.get("gallery_requested_size"),
        "canonical_gallery_enrolled_id_count": len(
            row.get("gallery_enrolled_ids") or []
        ),
        "runtime_gallery_policy": "EMPTY_RESOURCE_STATE_ONLY",
        "source_protocol_id": row.get("source_protocol_id"),
        "recipe_sha256": row.get("recipe_sha256"),
    }


def _audio_identity(row: Mapping[str, object]) -> str:
    value = str(row.get("pcm_sha256") or row.get("audio_sha256") or "").casefold()
    if len(value) != 64:
        raise H2ProgramError("long-session source lacks a 64-character audio identity")
    return value


def _canonical_source_rank(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        row.get("overlay_id") != "ALL_UNKNOWN",
        str(row.get("gallery_requested_size")).casefold() != "full",
        str(row.get("protocol_case_id") or ""),
    )


def _cleanup_receipt_path(
    root: Path,
    *,
    cleanup_kind: str,
    item_id: str,
    attempt_id: str | None = None,
) -> Path:
    identity = canonical_sha256(
        {
            "cleanup_kind": cleanup_kind,
            "item_id": item_id,
            "attempt_id": attempt_id,
        }
    )[:20]
    return root / CLEANUP_RECEIPTS_DIRECTORY / f"{cleanup_kind}_{identity}.json"


def _write_cleanup_receipt(path: Path, core: Mapping[str, object]) -> dict[str, object]:
    payload = {**dict(core), "receipt_sha256": canonical_sha256(core)}
    write_json_atomic(path, payload)
    return payload


def _valid_cleanup_receipt(
    path: Path,
    *,
    cleanup_kind: str,
    item_id: str,
) -> dict[str, object] | None:
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    unsigned = dict(payload)
    receipt_sha256 = unsigned.pop("receipt_sha256", None)
    if receipt_sha256 != canonical_sha256(unsigned):
        return None
    if (
        payload.get("cleanup_kind") != cleanup_kind
        or payload.get("item_id") != item_id
        or payload.get("status") not in {"REMOVED", "ALREADY_ABSENT"}
    ):
        return None
    return payload


def _tree_inventory(root: Path) -> tuple[int, int]:
    if not root.exists():
        return 0, 0
    if not root.is_dir():
        raise H2ProgramError(f"cleanup target is not a directory: {root}")
    file_count = 0
    byte_count = 0
    for path in root.rglob("*"):
        if path.is_file():
            file_count += 1
            byte_count += path.stat().st_size
    return file_count, byte_count


def _runtime_cleanup_target(
    subroot: Path,
    attempt_root: Path,
    runtime_root: Path,
) -> tuple[Path, Path, Path]:
    safe_subroot = subroot.resolve()
    safe_attempts = (safe_subroot / "attempts").resolve()
    safe_attempt = attempt_root.resolve()
    safe_runtime = runtime_root.resolve()
    attempt_suffix = attempt_root.name.removeprefix("attempt_")
    if (
        safe_attempt.parent != safe_attempts
        or not attempt_root.name.startswith("attempt_")
        or not attempt_suffix.isdigit()
        or safe_runtime.parent != safe_attempt
        or safe_runtime.name != "runtime"
        or safe_runtime != (safe_attempt / "runtime").resolve()
    ):
        raise H2ProgramError(
            "runtime cleanup target escaped its exact numbered subresult attempt"
        )
    return safe_subroot, safe_attempt, safe_runtime


def _cleanup_runtime_before_seal(
    *,
    subroot: Path,
    attempt_root: Path,
    runtime_root: Path,
    item_kind: str,
    item_id: str,
    harness_status: str,
) -> dict[str, object]:
    """Remove only a successful attempt's regenerable runtime tree.

    The receipt is written outside ``runtime`` but inside the subresult before
    that subresult is checksum-sealed.  Failed/stopped attempts remain intact.
    """

    receipt_path = _cleanup_receipt_path(
        subroot,
        cleanup_kind="runtime_tree",
        item_id=item_id,
        attempt_id=attempt_root.name,
    )
    base = {
        "schema_version": "h2-runtime-cleanup-receipt.v1",
        "cleanup_kind": "runtime_tree",
        "item_kind": item_kind,
        "item_id": item_id,
        "attempt_id": attempt_root.name,
        "harness_status": harness_status,
        "attempt_root": str(attempt_root),
        "runtime_root": str(runtime_root),
        "cleanup_phase": "before_subresult_checksum_seal",
    }
    try:
        _safe_subroot, _safe_attempt, safe_runtime = _runtime_cleanup_target(
            subroot,
            attempt_root,
            runtime_root,
        )
        files, bytes_on_disk = _tree_inventory(safe_runtime)
        if harness_status not in {"PASS", "UNSUPPORTED"}:
            return _write_cleanup_receipt(
                receipt_path,
                {
                    **base,
                    "status": "RETAINED_FOR_DIAGNOSIS",
                    "reason": "failed_or_stopped_atomic_attempt",
                    "strict_path_containment_validated": True,
                    "files_removed": 0,
                    "bytes_reclaimed": 0,
                    "retained_file_count": files,
                    "retained_bytes": bytes_on_disk,
                },
            )
        existed = safe_runtime.exists()
        if existed:
            shutil.rmtree(safe_runtime)
        if safe_runtime.exists():
            raise H2ProgramError(
                f"runtime cleanup did not remove its exact target: {safe_runtime}"
            )
        return _write_cleanup_receipt(
            receipt_path,
            {
                **base,
                "status": "REMOVED" if existed else "ALREADY_ABSENT",
                "reason": "checksum_distilled_successful_runtime",
                "strict_path_containment_validated": True,
                "files_removed": files if existed else 0,
                "bytes_reclaimed": bytes_on_disk if existed else 0,
                "retained_file_count": 0,
                "retained_bytes": 0,
            },
        )
    except Exception as exc:
        _write_cleanup_receipt(
            receipt_path,
            {
                **base,
                "status": "REFUSED",
                "reason": f"{type(exc).__name__}: {exc}",
                "strict_path_containment_validated": False,
                "files_removed": 0,
                "bytes_reclaimed": 0,
            },
        )
        if isinstance(exc, H2ProgramError):
            raise
        raise H2ProgramError(f"runtime cleanup failed closed: {exc}") from exc


def _retained_long_input_receipt(
    input_path: Path,
    *,
    stream_id: str,
    harness_status: str,
) -> dict[str, object]:
    sidecar = input_path.with_suffix(".materialization.json")
    existing = [path for path in (input_path, sidecar) if path.is_file()]
    return {
        "schema_version": "h2-long-input-cleanup-receipt.v1",
        "cleanup_kind": "materialized_long_input",
        "item_id": stream_id,
        "harness_status": harness_status,
        "status": "RETAINED_FOR_DIAGNOSIS",
        "reason": "failed_or_stopped_atomic_attempt",
        "cleanup_phase": "not_permitted_for_failed_or_stopped_subresult",
        "input_path": str(input_path),
        "sidecar_path": str(sidecar),
        "files_removed": 0,
        "bytes_reclaimed": 0,
        "retained_file_count": len(existing),
        "retained_bytes": sum(path.stat().st_size for path in existing),
    }


def _cleanup_long_input_after_publish(
    *,
    result_root: Path,
    subroot: Path,
    binding: Mapping[str, object],
    stream_id: str,
    input_path: Path,
) -> dict[str, object]:
    """Delete a successful stream's generated WAV only after a valid seal."""

    receipt_path = _cleanup_receipt_path(
        result_root,
        cleanup_kind="materialized_long_input",
        item_id=stream_id,
    )
    input_root = (result_root.resolve() / "inputs").resolve()
    expected_input = (input_root / f"{stream_id}.wav").resolve()
    expected_sidecar = expected_input.with_suffix(".materialization.json")
    actual_input = input_path.resolve()
    actual_sidecar = actual_input.with_suffix(".materialization.json")
    base = {
        "schema_version": "h2-long-input-cleanup-receipt.v1",
        "cleanup_kind": "materialized_long_input",
        "item_id": stream_id,
        "cleanup_phase": "after_valid_subresult_checksum_seal",
        "input_path": str(input_path),
        "sidecar_path": str(input_path.with_suffix(".materialization.json")),
    }
    try:
        if (
            expected_input.parent != input_root
            or actual_input != expected_input
            or actual_sidecar != expected_sidecar
            or actual_input.parent != input_root
        ):
            raise H2ProgramError(
                "long-input cleanup target escaped its exact job input directory"
            )
        if not _subresult_reusable(subroot, binding):
            raise H2ProgramError(
                "long-input cleanup requires a checksum-valid reusable subresult"
            )
        existing_receipt = _valid_cleanup_receipt(
            receipt_path,
            cleanup_kind="materialized_long_input",
            item_id=stream_id,
        )
        targets = (actual_input, actual_sidecar)
        if existing_receipt is not None and not any(path.exists() for path in targets):
            return existing_receipt
        if any(path.exists() and not path.is_file() for path in targets):
            raise H2ProgramError("long-input cleanup target is not a regular file")
        existing = [path for path in targets if path.is_file()]
        bytes_on_disk = sum(path.stat().st_size for path in existing)
        for path in existing:
            path.unlink()
        if any(path.exists() for path in targets):
            raise H2ProgramError("long-input cleanup left a generated input behind")
        return _write_cleanup_receipt(
            receipt_path,
            {
                **base,
                "status": "REMOVED" if existing else "ALREADY_ABSENT",
                "reason": "successful_subresult_is_checksum_sealed",
                "strict_path_containment_validated": True,
                "subresult_checksums_sha256": sha256_file(subroot / CHECKSUM_FILE),
                "files_removed": len(existing),
                "bytes_reclaimed": bytes_on_disk,
                "retained_file_count": 0,
                "retained_bytes": 0,
            },
        )
    except Exception as exc:
        _write_cleanup_receipt(
            receipt_path,
            {
                **base,
                "status": "REFUSED",
                "reason": f"{type(exc).__name__}: {exc}",
                "strict_path_containment_validated": False,
                "files_removed": 0,
                "bytes_reclaimed": 0,
            },
        )
        if isinstance(exc, H2ProgramError):
            raise
        raise H2ProgramError(f"long-input cleanup failed closed: {exc}") from exc


def _cleanup_summary(
    receipts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    statuses = Counter(str(row.get("status") or "MISSING") for row in receipts)
    kinds = Counter(str(row.get("cleanup_kind") or "MISSING") for row in receipts)
    return {
        "schema_version": "h2-runtime-cleanup-summary.v1",
        "receipt_count": len(receipts),
        "cleanup_kind_counts": dict(sorted(kinds.items())),
        "status_counts": dict(sorted(statuses.items())),
        "runtime_tree_receipt_count": kinds.get("runtime_tree", 0),
        "materialized_long_input_receipt_count": kinds.get(
            "materialized_long_input", 0
        ),
        "files_removed": sum(int(row.get("files_removed") or 0) for row in receipts),
        "bytes_reclaimed": sum(
            int(row.get("bytes_reclaimed") or 0) for row in receipts
        ),
        "retained_file_count": sum(
            int(row.get("retained_file_count") or 0) for row in receipts
        ),
        "retained_bytes": sum(
            int(row.get("retained_bytes") or 0) for row in receipts
        ),
        "path_refusal_count": statuses.get("REFUSED", 0),
        "successful_runtime_compactions": sum(
            row.get("cleanup_kind") == "runtime_tree"
            and row.get("status") in {"REMOVED", "ALREADY_ABSENT"}
            for row in receipts
        ),
    }


def _subresult_checksum_valid(
    root: Path,
    expected_binding: Mapping[str, object],
) -> bool:
    try:
        result = read_json(root / SUBRESULT_FILE)
        checksums = read_json(root / CHECKSUM_FILE)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if result.get("execution_binding_sha256") != expected_binding.get(
        "execution_binding_sha256"
    ):
        return False
    entries = checksums.get("entries")
    return isinstance(entries, Mapping) and dict(entries) == checksum_map(
        root, exclude=(CHECKSUM_FILE,)
    )


def _publish_subresult(
    root: Path,
    payload: Mapping[str, object],
    binding: Mapping[str, object],
) -> None:
    write_json_atomic(root / SUBRESULT_FILE, payload)
    write_json_atomic(
        root / CHECKSUM_FILE,
        {
            "schema_version": "h2-reliability-subresult-checksums.v1",
            "execution_binding_sha256": binding["execution_binding_sha256"],
            "entries": checksum_map(root, exclude=(CHECKSUM_FILE,)),
        },
    )


def _subresult_reusable(
    root: Path, expected_binding: Mapping[str, object]
) -> bool:
    try:
        result = read_json(root / SUBRESULT_FILE)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if result.get("harness_status") not in {"PASS", "UNSUPPORTED"}:
        return False
    return _subresult_checksum_valid(root, expected_binding)


def _publish_job_result(
    job: H2Job,
    *,
    binding: Mapping[str, object],
    result_root: Path,
    outcome: Mapping[str, object],
) -> dict[str, object]:
    status = str(outcome.get("status") or "FAILED")
    payload = {
        "schema_version": "h2-long-reliability-job-result.v1",
        "status": status,
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "job_identity_sha256": job.identity_sha256,
        "execution_binding": dict(binding),
        "execution_binding_sha256": binding["execution_binding_sha256"],
        "controlled_prerecorded_loopback": True,
        "physical_microphone_or_device_behavior_claimed": False,
        "all_artifacts_on_c_drive": True,
        "outcome": dict(outcome),
        "completed_at_utc": _utc_now(),
    }
    result_path = result_root / RESULT_FILE
    write_json_atomic(result_path, payload)
    write_json_atomic(
        result_root / CHECKSUM_FILE,
        {
            "schema_version": "h2-long-reliability-checksums.v1",
            "execution_binding_sha256": binding["execution_binding_sha256"],
            "entries": checksum_map(result_root, exclude=(CHECKSUM_FILE,)),
        },
    )
    state = {"COMPLETE": "complete", "STOPPED": "stopped"}.get(status, "failed")
    return {
        "state": state,
        "reused": False,
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
        "result_root": str(result_root),
        "checksums_sha256": sha256_file(result_root / CHECKSUM_FILE),
        "error": None if state != "failed" else f"{job.job_kind} assertions failed",
    }


def _subresult_bindings(
    root: Path, rows: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        discriminator = str(row.get("stream_id") or row.get("fault_id") or "")
        path = root / discriminator / CHECKSUM_FILE
        if path.is_file():
            result.append(
                {
                    "subtest_id": discriminator,
                    "harness_status": row.get("harness_status"),
                    "checksums_path": str(path),
                    "checksums_sha256": sha256_file(path),
                }
            )
    return result


def _next_attempt_root(subroot: Path) -> Path:
    """Allocate a new attempt without deleting prior diagnostic evidence."""

    attempts = subroot / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    indexes = []
    for path in attempts.glob("attempt_*"):
        try:
            indexes.append(int(path.name.removeprefix("attempt_")))
        except ValueError:
            continue
    root = attempts / f"attempt_{max(indexes, default=0) + 1:03d}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def _assertion(
    assertion_id: str, passed: bool, *, expected: object, observed: object
) -> dict[str, object]:
    return {
        "assertion_id": assertion_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "observed": observed,
    }


def _read_optional_jsonl(path: Path) -> list[dict[str, object]]:
    return list(read_jsonl(path)) if path.is_file() else []


def _job_root(paths: ProgramPaths, job: H2Job) -> Path:
    return ensure_c_drive(
        paths.results_root / "jobs" / job.job_id / "reliability_result",
        label="H2 reliability result root",
    )


def _require_execution_paths(paths: ProgramPaths) -> None:
    for label, path in (
        ("H2 workspace", paths.workspace),
        ("H2 result root", paths.results_root),
        ("H2 summary root", paths.summary_root),
        ("H2 configuration", paths.config_path),
        ("H2 prepared protocol", PREPARED_PROTOCOL_ROOT),
    ):
        ensure_c_drive(path, label=label, must_exist=path in {paths.config_path, PREPARED_PROTOCOL_ROOT})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "H2_RELIABILITY_FAULTS",
    "LONG_SESSION_DURATIONS_SEC",
    "SESSION_RESET_RESTART_FAULT",
    "build_long_session_source_plan",
    "execute_reliability_job",
    "reliability_result_reusable",
    "validate_reliability_result",
    "validate_reliability_tuning",
]
