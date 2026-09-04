"""Job adapter from the Prompt-3 controller to the Prompt-1 streaming runtime.

One job owns one immutable pipeline/protocol/split identity.  Cases execute
through ``build_file_runtime`` at unpaced engineering speed; this module only
collects outputs and invokes pure scorers.  It never imports a model directly
and never downloads data or checkpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import threading
import time
from typing import Callable, Iterable, Mapping, Protocol, Sequence

from app.full_pipeline.factory import (
    DEFAULT_CACHE_ROOT,
    _embedding_warmup_request,
    _ensure_warmup_audio,
    build_file_runtime,
)
from app.full_pipeline.provenance import runtime_identities
from app.utils.paths import resolve_data_path_from_logical

from .io import (
    canonical_json_bytes,
    installed_tool_path_candidates,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from .planning import EVALUATION_ROOT, MATRIX_PATH, matrix
from .protocol import DEFAULT_PROTOCOL_ROOT
from .results import ResultTreeBuilder
from .schema import (
    ARTIFACT_SUPPORT_IDS,
    MODEL_ASSETS_SCHEMA_VERSION,
    PIPELINE_IDENTITY_SCHEMA_VERSION,
    build_metric_documents_from_reports,
    build_run_document,
)
from .metrics import (
    MetricDefinition,
    MetricReport,
    MetricValue,
    build_metric_report,
    computed_metric,
    undefined_metric,
    unsupported_metric,
)
from .scorers import (
    attribution_intervals_from_prompt1_events,
    score_anonymous_diarization,
    score_full_pipeline,
    score_known_unknown_attribution,
    score_speaker_attributed_transcription,
    score_streaming,
    score_ux,
)
from .store import EvaluationJobSpec


ProgressCallback = Callable[..., None]
StopCallback = Callable[[], bool]
StorageReserveCallback = Callable[[], None]


@dataclass(frozen=True)
class ProtocolContext:
    """Prepared split registries used to hydrate portable case references."""

    root: Path
    split: str
    references: Mapping[str, Mapping[str, object]]
    overlays: Mapping[str, Mapping[str, object]]
    enrollments: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class PreparedGallery:
    """Attempt-local protected store and non-biometric public profile identities."""

    root: Path
    profiles: tuple[Mapping[str, object], ...] = ()


class EnrollmentPreparer(Protocol):
    def prepare(
        self, case: Mapping[str, object], context: ProtocolContext
    ) -> PreparedGallery: ...

    def close(self) -> None: ...


RuntimeBuilder = Callable[..., object]


def execute_evaluation_job(
    job: EvaluationJobSpec,
    cases: Sequence[Mapping[str, object]],
    output_root: Path,
    progress: ProgressCallback,
    stop_requested: StopCallback,
    *,
    runtime_builder: RuntimeBuilder = build_file_runtime,
    enrollment_preparer: EnrollmentPreparer | None = None,
    decision_policy_registry_path: Path | None = None,
    execution_contract: Mapping[str, object] | None = None,
    runtime_tuning: Mapping[str, object] | None = None,
    stop_at_case_boundary: bool = False,
    storage_reserve_callback: StorageReserveCallback | None = None,
) -> Mapping[str, object]:
    """Execute one real job through the shared runtime and common scorers."""

    if len(cases) != job.case_count:
        raise ValueError("job case materialization differs from its frozen identity")
    raw_emit_identity_scores = dict(execution_contract or {}).get(
        "emit_identity_score_diagnostics", False
    )
    if not isinstance(raw_emit_identity_scores, bool):
        raise ValueError("emit_identity_score_diagnostics must be boolean")
    emit_identity_score_diagnostics = raw_emit_identity_scores
    if emit_identity_score_diagnostics and job.split != "development":
        raise ValueError(
            "identity score diagnostics are development-only and forbidden "
            f"for split {job.split}"
        )
    h2_integration_partition = _h2_integration_partition(
        execution_contract,
        job=job,
        cases=cases,
    )
    _apply_deterministic_seed(job.seed)
    selection = matrix().resolve(job.pipeline_id)
    if selection.pipeline_config_sha256 != job.pipeline_identity:
        raise ValueError("job pipeline identity no longer matches the locked matrix")
    run_id = f"run_{str(job.reuse_identity['identity_sha256'])[:24]}"
    attempt_id = Path(output_root).resolve().parent.name
    created_at = _utc_now()
    builder = ResultTreeBuilder(output_root, job.reuse_identity, compact=True)
    artifact_support = {
        value: {"status": "supported", "reason": None} for value in ARTIFACT_SUPPORT_IDS
    }
    builder.publish_run(
        build_run_document(
            run_id=run_id,
            attempt_id=attempt_id,
            reuse_identity=job.reuse_identity,
            status="running",
            created_at_utc=created_at,
            started_at_utc=created_at,
            artifact_support=artifact_support,
            counts={"planned_cases": job.case_count},
            result_tree_schema_version=builder.result_tree_schema_version,
        )
    )
    decision_registry_identity: dict[str, object] | None = None
    decision_identity_sha256: str | None = None
    if decision_policy_registry_path is not None:
        registry_path = Path(decision_policy_registry_path).resolve()
        registry_value = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(registry_value, Mapping):
            raise ValueError("decision-policy registry must be an object")
        registry_identity_sha256 = str(
            registry_value.get("registry_identity_sha256") or ""
        ).lower()
        if len(registry_identity_sha256) != 64:
            raise ValueError("decision-policy registry lacks its identity SHA-256")
        if selection.hybrid_label not in {"H2", "H4", "H5"}:
            decision_identity_sha256 = registry_identity_sha256
        decision_registry_identity = {
            "registry_identity_sha256": registry_identity_sha256,
            "registry_file_sha256": sha256_file(registry_path),
            "calibration_partition": registry_value.get("calibration_partition"),
            "evaluation_material_inspected": registry_value.get(
                "evaluation_material_inspected"
            ),
            "applies_to_pipeline": selection.hybrid_label not in {"H2", "H4", "H5"},
        }
        if decision_registry_identity["evaluation_material_inspected"] is not False:
            raise ValueError(
                "decision-policy registry lacks the development-only firewall"
            )
    identities = runtime_identities(
        selection,
        evaluation_root=EVALUATION_ROOT,
        decision_policy_sha256=decision_identity_sha256,
    )
    protocol_context = _load_protocol_context(job.split, cases)
    pipeline_identity_document: dict[str, object] = {
        "schema_version": PIPELINE_IDENTITY_SCHEMA_VERSION,
        "run_id": run_id,
        "pipeline_id": job.pipeline_id,
        "protocol_version": selection.protocol_version,
        "pipeline_config_sha256": selection.pipeline_config_sha256,
        "matrix_sha256": sha256_file(MATRIX_PATH),
        "aliases": {
            "asr": selection.asr_alias,
            "anonymous_diarization": selection.diarization_alias,
            "identity": selection.identity_alias,
            "hybrid": selection.hybrid_label,
        },
        "component_identities": [
            value.to_contract() for _, value in sorted(identities.items())
        ],
        "policy_identities": {
            "enrollment": dict(selection.enrollment_policy),
            "hybrid": dict(selection.hybrid_policy),
            "decision_policy_registry": decision_registry_identity,
        },
        "environment_identities": [
            {
                "environment_profile_id": profile_id,
                "environment_fingerprint_sha256": fingerprint,
            }
            for profile_id, fingerprint in sorted(
                {
                    (
                        str(value.environment_profile_id or "unspecified"),
                        value.environment_fingerprint_sha256,
                    )
                    for value in identities.values()
                },
                key=lambda row: row[0],
            )
        ],
    }
    if execution_contract is not None:
        pipeline_identity_document["execution_contract"] = dict(execution_contract)
    if runtime_tuning is not None:
        pipeline_identity_document["runtime_tuning"] = dict(runtime_tuning)
    pipeline_identity_document["stop_semantics"] = (
        "finish_current_atomic_case_then_stop"
        if stop_at_case_boundary
        else "runtime_interruptible_legacy"
    )
    builder.publish_pipeline_identity(pipeline_identity_document)
    builder.publish_model_assets(
        {
            "schema_version": MODEL_ASSETS_SCHEMA_VERSION,
            "run_id": run_id,
            "pipeline_id": job.pipeline_id,
            "assets": _model_assets(identities),
            "no_implicit_downloads": True,
        }
    )

    runtime_root = Path(output_root).resolve().parent / "runtime_cases"
    runtime_root.mkdir(parents=True, exist_ok=True)
    transcript_rows: list[dict[str, object]] = []
    labelled_rows: list[dict[str, object]] = []
    hypothesis_segments: list[dict[str, object]] = []
    asr_rows: list[dict[str, object]] = []
    resource_samples: list[dict[str, object]] = []
    case_status: list[dict[str, object]] = []
    case_reports: dict[str, list[MetricReport]] = {
        "streaming": [],
        "diarization": [],
        "identity": [],
        "speaker_transcription": [],
        "ux": [],
    }
    # Preserve one complete metric report per atomic case.  The campaign-level
    # documents below remain the canonical aggregate, while this compact
    # diagnostic is the dependency-preserving input for later case/speaker
    # bootstrap intervals.  It contains no embeddings or biometric vectors.
    per_case_metric_rows: list[dict[str, object]] = []
    challenger_score_observations: list[dict[str, object]] = []
    overlap_score_diagnostics: list[dict[str, object]] = []
    short_turn_diagnostics: list[dict[str, object]] = []
    embedding_reuse_observations: list[dict[str, object]] = []
    embedding_reuse_telemetry: list[dict[str, object]] = []
    selected_profile_rows: list[dict[str, object]] = []
    completed_cases = 0
    completed_audio = 0.0
    cache_hits = 0
    maximum_queue_depth_seen = 0.0
    measured_runtime_wall_sec = 0.0
    started_monotonic = time.monotonic()
    errors: list[dict[str, object]] = []
    stopped = False
    runtime_cache_root = (
        DEFAULT_CACHE_ROOT
        if job.measurement_mode == "accuracy"
        else Path(output_root).resolve().parent / "resource_runtime_cache"
    )
    staging_root = Path(output_root).resolve().parent / "result_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    event_staging_path = staging_root / "events.jsonl.gz"
    event_raw_stream = event_staging_path.open("wb")
    event_stream = gzip.GzipFile(
        filename="", fileobj=event_raw_stream, mode="wb", mtime=0
    )
    attempt_root = Path(output_root).resolve().parent
    case_shard_root = attempt_root.parent / "case_shards_v1"
    case_cursor_binding = _case_cursor_binding(job, cases)
    valid_case_shards: dict[str, str] = {}
    shared_worker_pool: object | None = None
    shared_worker_warmup_audio: Path | None = None
    shared_execution_enabled = runtime_builder is build_file_runtime
    if shared_execution_enabled:
        from app.full_pipeline_development.shared_execution import SharedWorkerPool

        shared_worker_warmup_audio = _ensure_warmup_audio(
            attempt_root / "shared_runtime_work"
        )
        shared_worker_pool = SharedWorkerPool(pool_id=f"evaluation-job:{job.job_id}")
    owns_gallery_preparer = enrollment_preparer is None
    gallery_preparer = enrollment_preparer or _FrozenGalleryPreparer(
        selection=selection,
        attempt_root=attempt_root,
        worker_pool=shared_worker_pool,
        lazy_worker_start=shared_execution_enabled,
        worker_warmup_audio_path=shared_worker_warmup_audio,
    )

    try:
        for index, case in enumerate(cases, start=1):
            if stop_requested():
                stopped = True
                break
            case_id = _case_id(case)
            duration = _duration(case)
            case_root = runtime_root / _portable_id(case_id)
            shard_path = case_shard_root / _portable_id(case_id) / "case_shard.json"
            shard = _load_valid_case_shard(
                shard_path,
                job=job,
                case=case,
                ordinal=index,
            )
            if shard is not None:
                raw_payload = shard["payload"]
                if not isinstance(
                    raw_payload, Mapping
                ):  # pragma: no cover - validator owns
                    raise ValueError("validated case shard payload is not an object")
                payload = dict(raw_payload)
                cleanup = _cleanup_completed_case_roots_after_valid_shard(
                    attempt_root.parent,
                    runtime_root,
                    case_id,
                )
                cleanup_rows = _mapping_rows(payload, "case_status")
                if cleanup_rows and cleanup["status"] != "ALREADY_ABSENT":
                    cleanup_rows[-1]["runtime_case_cleanup"] = cleanup["status"]
                    cleanup_rows[-1]["runtime_case_cleanup_detail"] = cleanup.get(
                        "reason"
                    )
                    payload["case_status"] = cleanup_rows
                    shard = _write_case_shard(
                        shard_path,
                        job=job,
                        case=case,
                        ordinal=index,
                        payload=payload,
                    )
                events = _mapping_rows(payload, "events")
                for event in events:
                    event_stream.write(canonical_json_bytes(event) + b"\n")
                transcript_rows.extend(_mapping_rows(payload, "transcript_rows"))
                labelled_rows.extend(_mapping_rows(payload, "labelled_rows"))
                hypothesis_segments.extend(
                    _mapping_rows(payload, "hypothesis_segments")
                )
                asr_rows.extend(_mapping_rows(payload, "asr_rows"))
                resource_samples.extend(_mapping_rows(payload, "resource_samples"))
                per_case_metric_rows.extend(
                    _mapping_rows(payload, "per_case_metric_rows")
                )
                challenger_score_observations.extend(
                    _mapping_rows(payload, "challenger_score_observations")
                )
                overlap_score_diagnostics.extend(
                    _mapping_rows(payload, "overlap_score_diagnostics")
                )
                short_turn_diagnostics.extend(
                    _mapping_rows(payload, "short_turn_diagnostics")
                )
                embedding_reuse_observations.extend(
                    _mapping_rows(payload, "embedding_reuse_observations")
                )
                embedding_reuse_telemetry.extend(
                    _mapping_rows(payload, "embedding_reuse_telemetry")
                )
                selected_profile_rows.extend(
                    _mapping_rows(payload, "selected_profile_rows")
                )
                case_status.extend(_mapping_rows(payload, "case_status"))
                raw_reports = payload.get("case_reports")
                if not isinstance(raw_reports, Mapping):
                    raise ValueError("case shard lacks case_reports")
                for category, raw_report in raw_reports.items():
                    if str(category) not in case_reports or not isinstance(
                        raw_report, Mapping
                    ):
                        raise ValueError("case shard report category differs")
                    case_reports[str(category)].append(
                        _metric_report_from_json(raw_report)
                    )
                completed_cases += 1
                completed_audio += duration
                cache_hits += int(payload.get("cache_hits") or 0)
                measured_runtime_wall_sec += float(
                    payload.get("measured_runtime_wall_sec") or 0.0
                )
                queue_depth = payload.get("maximum_queue_depth")
                if isinstance(queue_depth, (int, float)):
                    maximum_queue_depth_seen = max(
                        maximum_queue_depth_seen, float(queue_depth)
                    )
                shard_sha = str(shard["shard_sha256"])
                valid_case_shards[case_id] = shard_sha
                _write_case_cursor(
                    case_shard_root,
                    binding=case_cursor_binding,
                    completed_shards=valid_case_shards,
                )
                elapsed = time.monotonic() - started_monotonic
                progress(
                    completed_cases=completed_cases,
                    completed_audio_sec=completed_audio,
                    current_case_id=case_id,
                    latest_activity=(f"reused checksum-valid case shard {case_id}"),
                    rolling_rtf=(
                        elapsed / completed_audio if completed_audio > 0 else None
                    ),
                    rss_mb=payload.get("rss_mb"),
                    queue_depth=queue_depth,
                    cache_hits=cache_hits,
                )
                if stop_at_case_boundary and stop_requested():
                    stopped = True
                    break
                continue
            if storage_reserve_callback is not None:
                try:
                    storage_reserve_callback()
                except Exception as exc:
                    errors.append(
                        {
                            "case_id": case_id,
                            "code": "storage_reserve_blocked",
                            "detail": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    stopped = True
                    progress(
                        completed_cases=completed_cases,
                        completed_audio_sec=completed_audio,
                        current_case_id=case_id,
                        latest_activity=(
                            "storage reserve blocked before starting case " f"{case_id}"
                        ),
                        cache_hits=cache_hits,
                    )
                    break
            progress(
                completed_cases=completed_cases,
                completed_audio_sec=completed_audio,
                current_case_id=case_id,
                latest_activity=f"starting case {case_id}",
                cache_hits=cache_hits,
            )
            science: Mapping[str, object] = {}
            row_offsets = {
                "transcript_rows": len(transcript_rows),
                "labelled_rows": len(labelled_rows),
                "hypothesis_segments": len(hypothesis_segments),
                "asr_rows": len(asr_rows),
                "resource_samples": len(resource_samples),
                "per_case_metric_rows": len(per_case_metric_rows),
                "challenger_score_observations": len(challenger_score_observations),
                "overlap_score_diagnostics": len(overlap_score_diagnostics),
                "short_turn_diagnostics": len(short_turn_diagnostics),
                "embedding_reuse_observations": len(embedding_reuse_observations),
                "embedding_reuse_telemetry": len(embedding_reuse_telemetry),
                "selected_profile_rows": len(selected_profile_rows),
                "case_status": len(case_status),
            }
            runtime_wall_before = measured_runtime_wall_sec
            try:
                science = _hydrate_case(case, protocol_context)
                _require_declared_prerequisites(case, science)
                source_audio = _audio_path(case)
                _verify_case_audio(source_audio, case)
                runtime_audio = _prepare_runtime_audio(source_audio, case, case_root)
                gallery = gallery_preparer.prepare(case, protocol_context)
                selected_profile_rows.extend(
                    {"case_id": case_id, **dict(row)} for row in gallery.profiles
                )
                session_id = f"{run_id}_{index:06d}"
                realized_gallery_size = int(
                    case.get("gallery_size")
                    if case.get("gallery_size") is not None
                    else len(case.get("gallery_enrolled_ids", []))
                )
                case_identity_score_diagnostics = (
                    emit_identity_score_diagnostics
                    and _h2_integration_case_role(h2_integration_partition, case_id)
                    != "excluded_cross_cohort"
                )
                runtime_kwargs: dict[str, object] = {
                    "decision_policy_registry_path": (
                        Path(decision_policy_registry_path).resolve()
                        if decision_policy_registry_path is not None
                        else None
                    ),
                    "gallery_requested_size": case.get("gallery_requested_size"),
                    "realized_gallery_size": realized_gallery_size,
                    "emit_identity_score_diagnostics": (
                        case_identity_score_diagnostics
                    ),
                }
                if runtime_tuning is not None:
                    runtime_kwargs["runtime_tuning"] = dict(runtime_tuning)
                if shared_execution_enabled:
                    trace_enabled = job.measurement_mode == "accuracy"
                    runtime_kwargs.update(
                        {
                            "worker_pool": shared_worker_pool,
                            "lazy_worker_start": True,
                            "worker_warmup_audio_path": shared_worker_warmup_audio,
                            "asr_stream_trace_root": (
                                DEFAULT_CACHE_ROOT / "asr_stream_traces"
                            ),
                            "asr_stream_trace_enabled": trace_enabled,
                            "evaluation_measurement_mode": job.measurement_mode,
                        }
                    )
                    if job.measurement_mode == "resources" and trace_enabled:
                        raise RuntimeError(
                            "resource measurement must never enable ASR stream replay"
                        )
                runtime = runtime_builder(
                    pipeline_id=job.pipeline_id,
                    input_path=runtime_audio,
                    output_root=case_root,
                    enrollment_root=gallery.root,
                    session_id=session_id,
                    pace=0.0,
                    telemetry_enabled=True,
                    cache_root=runtime_cache_root,
                    play_audio=False,
                    **runtime_kwargs,
                )
                runtime_started = time.monotonic()
                try:
                    result = dict(
                        _run_runtime_with_stop(
                            runtime,
                            (
                                (lambda: False)
                                if stop_at_case_boundary
                                else stop_requested
                            ),
                        )
                    )
                finally:
                    measured_runtime_wall_sec += time.monotonic() - runtime_started
                completion = str(result.get("completion_state") or "failed")
                stopped = stopped or (stop_requested() and completion != "complete")
                case_events = _jsonl(case_root / "events/events.jsonl")
                enriched = [_enrich_event(row, case_id) for row in case_events]
                enriched = _merge_asr_diagnostics(
                    enriched,
                    _jsonl(case_root / "diagnostics/asr_native_events.jsonl"),
                    case_id,
                )
                for event in enriched:
                    event_stream.write(canonical_json_bytes(event) + b"\n")
                case_transcript = _final_transcript(case_root)
                hypothesis_text = " ".join(
                    str(row.get("text") or "") for row in case_transcript
                ).strip()
                reference_text = str(science.get("reference_text") or "")
                output_failed = completion != "complete" or not hypothesis_text
                asr_rows.append(
                    {
                        "utterance_id": case_id,
                        "reference_text": reference_text,
                        "hypothesis_text": (
                            hypothesis_text if not output_failed else None
                        ),
                        "output_failed": output_failed,
                    }
                )
                case_streaming_references = _streaming_reference_map(enriched, science)
                case_hypothesis_texts: dict[str, list[str]] = {}
                for span_index, span in enumerate(case_transcript):
                    row = {"case_id": case_id, **span}
                    transcript_rows.append(row)
                    labelled_rows.append(dict(row))
                    # cpWER requires complete hypothesis streams.  A word must
                    # never disappear merely because the product had not yet
                    # attached speaker evidence.  Keep each unassigned span in
                    # a distinct deterministic stream so missing attribution is
                    # represented as fragmentation instead of silently omitted.
                    label = _anonymous_speaker_id(span) or (
                        "__UNASSIGNED_SPAN__::" f"{span.get('span_id') or span_index}"
                    )
                    case_hypothesis_texts.setdefault(label, []).append(
                        str(span.get("text") or "")
                    )
                case_hypothesis_segments = _hypothesis_segments(case_root, case_id)
                hypothesis_segments.extend(case_hypothesis_segments)
                case_reference_segments = [
                    dict(row) for row in science.get("diarization_segments", [])
                ]
                case_identity_intervals = _identity_intervals(
                    case, science, case_hypothesis_segments, enriched
                )
                # Raw candidate score vectors are a development-calibration
                # artifact only.  Evaluation still computes the frozen public
                # attribution metrics, but must neither recalibrate nor export
                # biometric score vectors from the untouched held-out split.
                if job.split == "development":
                    score_diagnostic_rows = _jsonl(
                        case_root / "diagnostics/unresolved_identity_scores.jsonl"
                    )
                    if case_identity_score_diagnostics:
                        score_diagnostic_rows.extend(
                            _jsonl(
                                case_root
                                / "diagnostics/identity_score_diagnostics.jsonl"
                            )
                        )
                    challenger_score_observations.extend(
                        _challenger_score_observations(
                            score_diagnostic_rows,
                            job=job,
                            case=case,
                            science=science,
                            hypothesis_segments=case_hypothesis_segments,
                            selection=selection,
                            gallery=gallery,
                            h2_integration_partition=h2_integration_partition,
                        )
                    )
                case_reuse_observations = _jsonl(
                    case_root / "diagnostics/embedding_reuse_observations.jsonl"
                )
                embedding_reuse_observations.extend(
                    {"case_id": case_id, **dict(row)} for row in case_reuse_observations
                )
                case_reuse_telemetry = _read_optional_json(
                    case_root / "diagnostics/embedding_reuse_telemetry.json"
                )
                if case_reuse_telemetry:
                    embedding_reuse_telemetry.append(
                        {"case_id": case_id, **dict(case_reuse_telemetry)}
                    )
                if job.split == "development":
                    overlap_score_diagnostics.extend(
                        {
                            **dict(row),
                            "case_id": case_id,
                            "pipeline_id": job.pipeline_id,
                            "split": job.split,
                            "evaluation_material_inspected": False,
                        }
                        for row in _jsonl(
                            case_root / "diagnostics/overlap_identity_scores.jsonl"
                        )
                    )
                short_turn_diagnostics.extend(
                    {"case_id": case_id, **dict(row)}
                    for row in _jsonl(
                        case_root / "diagnostics/short_turn_decisions.jsonl"
                    )
                )
                case_scoring = {
                    "case_id": case_id,
                    "events": enriched,
                    "streaming_references": case_streaming_references,
                    "reference_segments": case_reference_segments,
                    "hypothesis_segments": case_hypothesis_segments,
                    "uem": science.get("uem"),
                    "attribution_intervals": case_identity_intervals,
                    "short_turn_max_duration_sec": 0.5,
                    "reentry_episodes": _reference_reentry_episodes(
                        case_reference_segments,
                        case_hypothesis_segments,
                        case_id=case_id,
                    ),
                    "reference_speaker_texts": dict(science.get("speaker_texts", {})),
                    "hypothesis_speaker_texts": {
                        key: " ".join(value).strip()
                        for key, value in case_hypothesis_texts.items()
                    },
                    "reference_transcript_segments": [
                        dict(row)
                        for row in science.get("transcript_segments", [])
                        if isinstance(row, Mapping)
                    ],
                    "hypothesis_transcript_spans": [
                        dict(row) for row in case_transcript
                    ],
                    "local_to_global_speaker": (
                        dict(case.get("local_to_global_speaker", {}))
                        if isinstance(case.get("local_to_global_speaker"), Mapping)
                        else {}
                    ),
                    "identity_overlay": (
                        dict(science["overlay"])
                        if isinstance(science.get("overlay"), Mapping)
                        else None
                    ),
                    "product_mode": str(
                        dict(runtime_tuning or {}).get("product_mode") or ""
                    ),
                    "speaker_transcript_supported": bool(
                        science.get("speaker_transcript_supported")
                    ),
                }
                isolated_reports = _score_isolated_case_views(
                    [case_scoring], all_cases_complete=(completion == "complete")
                )
                for category, report in isolated_reports.items():
                    case_reports[category].append(report)
                local_to_global = case.get("local_to_global_speaker")
                speaker_map = (
                    {str(key): str(value) for key, value in local_to_global.items()}
                    if isinstance(local_to_global, Mapping)
                    else {}
                )
                reference_speaker_ids = sorted(
                    {
                        speaker_map.get(
                            str(row.get("speaker_id") or row.get("speaker")),
                            str(row.get("speaker_id") or row.get("speaker")),
                        )
                        for row in case_reference_segments
                        if row.get("speaker_id") is not None
                        or row.get("speaker") is not None
                    }
                )
                per_case_metric_rows.append(
                    {
                        "schema_version": "full-pipeline-per-case-metrics.v1",
                        "case_id": case_id,
                        "source_case_id": str(case.get("source_case_id") or case_id),
                        "source_key": case.get("source_key"),
                        "overlay_id": case.get("overlay_id"),
                        "audio_duration_sec": duration,
                        "reference_speaker_ids": reference_speaker_ids,
                        "reports": {
                            category: report.to_jsonable()
                            for category, report in sorted(isolated_reports.items())
                        },
                    }
                )
                samples = (
                    _jsonl(case_root / "telemetry/resource_samples.jsonl")
                    if job.measurement_mode == "resources"
                    else []
                )
                if samples:
                    resource_samples.extend(
                        {"evaluation_case_id": case_id, **row} for row in samples
                    )
                case_cache_hits = sum(
                    "cache_hit" in json.dumps(row.get("event_reason") or {})
                    for row in enriched
                )
                cache_hits += case_cache_hits
                runtime_metrics = _read_optional_json(
                    case_root / "metrics/runtime_metrics.json"
                )
                case_queue_backpressure = _queue_backpressure_evidence(
                    enriched, runtime_metrics
                )
                case_queue_depth = _maximum_queue_depth(enriched, runtime_metrics)
                if case_queue_depth is not None:
                    maximum_queue_depth_seen = max(
                        maximum_queue_depth_seen, float(case_queue_depth)
                    )
                if completion == "complete":
                    completed_cases += 1
                    completed_audio += duration
                elapsed = time.monotonic() - started_monotonic
                progress(
                    completed_cases=completed_cases,
                    completed_audio_sec=completed_audio,
                    current_case_id=case_id,
                    latest_activity=f"{completion} case {case_id}",
                    rolling_rtf=(
                        elapsed / completed_audio if completed_audio > 0 else None
                    ),
                    cpu_percent=_last_number(samples, "process_cpu_percent"),
                    rss_mb=(
                        _last_number(samples, "process_rss_bytes") / (1024**2)
                        if _last_number(samples, "process_rss_bytes") is not None
                        else None
                    ),
                    queue_depth=case_queue_depth,
                    cache_hits=cache_hits,
                )
                status_row = {
                    "case_id": case_id,
                    "status": completion,
                    "audio_duration_sec": duration,
                    "runtime_result_sha256": result.get("result_sha256"),
                    "output_failed": output_failed,
                    "cache_hits": case_cache_hits,
                    "event_count": len(enriched),
                    "maximum_queue_depth": case_queue_depth,
                    "queue_backpressure": case_queue_backpressure,
                }
                if completion == "complete":
                    status_row["runtime_case_cleanup"] = "PENDING_SHARD_VALIDATION"
                else:
                    status_row["runtime_case_cleanup"] = (
                        "retained_for_failure_diagnosis"
                    )
                case_status.append(status_row)
                if completion == "complete":
                    shard_payload = {
                        key: [dict(row) for row in values[row_offsets[key] :]]
                        for key, values in (
                            ("transcript_rows", transcript_rows),
                            ("labelled_rows", labelled_rows),
                            ("hypothesis_segments", hypothesis_segments),
                            ("asr_rows", asr_rows),
                            ("resource_samples", resource_samples),
                            ("per_case_metric_rows", per_case_metric_rows),
                            (
                                "challenger_score_observations",
                                challenger_score_observations,
                            ),
                            (
                                "overlap_score_diagnostics",
                                overlap_score_diagnostics,
                            ),
                            (
                                "short_turn_diagnostics",
                                short_turn_diagnostics,
                            ),
                            (
                                "embedding_reuse_observations",
                                embedding_reuse_observations,
                            ),
                            (
                                "embedding_reuse_telemetry",
                                embedding_reuse_telemetry,
                            ),
                            ("selected_profile_rows", selected_profile_rows),
                            ("case_status", case_status),
                        )
                    }
                    shard_payload.update(
                        {
                            "events": [dict(row) for row in enriched],
                            "case_reports": {
                                category: report.to_jsonable()
                                for category, report in sorted(isolated_reports.items())
                            },
                            "cache_hits": case_cache_hits,
                            "measured_runtime_wall_sec": (
                                measured_runtime_wall_sec - runtime_wall_before
                            ),
                            "maximum_queue_depth": case_queue_depth,
                            "queue_backpressure": case_queue_backpressure,
                            "rss_mb": (
                                _last_number(samples, "process_rss_bytes") / (1024**2)
                                if _last_number(samples, "process_rss_bytes")
                                is not None
                                else None
                            ),
                        }
                    )
                    shard_document = _write_case_shard(
                        shard_path,
                        job=job,
                        case=case,
                        ordinal=index,
                        payload=shard_payload,
                    )
                    validated_shard = _load_valid_case_shard(
                        shard_path,
                        job=job,
                        case=case,
                        ordinal=index,
                    )
                    if validated_shard is None:
                        raise ValueError(
                            f"newly written case shard failed validation: {case_id}"
                        )
                    cleanup = _cleanup_completed_case_root(runtime_root, case_root)
                    status_row["runtime_case_cleanup"] = cleanup["status"]
                    status_row["runtime_case_cleanup_detail"] = cleanup.get("reason")
                    shard_payload["case_status"] = [
                        dict(row) for row in case_status[row_offsets["case_status"] :]
                    ]
                    shard_document = _write_case_shard(
                        shard_path,
                        job=job,
                        case=case,
                        ordinal=index,
                        payload=shard_payload,
                    )
                    if (
                        _load_valid_case_shard(
                            shard_path,
                            job=job,
                            case=case,
                            ordinal=index,
                        )
                        is None
                    ):
                        raise ValueError(
                            f"final case shard failed validation: {case_id}"
                        )
                    valid_case_shards[case_id] = str(shard_document["shard_sha256"])
                    _write_case_cursor(
                        case_shard_root,
                        binding=case_cursor_binding,
                        completed_shards=valid_case_shards,
                    )
                if completion != "complete":
                    if not stopped:
                        errors.append(
                            {
                                "case_id": case_id,
                                "code": "runtime_failed",
                                "detail": result.get("errors"),
                            }
                        )
                    break
                if stop_at_case_boundary and stop_requested():
                    stopped = True
                    break
            except Exception as exc:
                errors.append(
                    {
                        "case_id": case_id,
                        "code": "case_exception",
                        "detail": f"{type(exc).__name__}: {exc}",
                    }
                )
                asr_rows.append(
                    {
                        "utterance_id": case_id,
                        "reference_text": str(
                            science.get("reference_text")
                            or _reference_text(
                                case, _case_reference(case, protocol_context)
                            )
                        ),
                        "hypothesis_text": None,
                        "output_failed": True,
                    }
                )
                case_status.append(
                    {
                        "case_id": case_id,
                        "status": "failed",
                        "audio_duration_sec": duration,
                        "error": errors[-1],
                    }
                )
                break
    finally:
        teardown_error: BaseException | None = None
        teardown_operations = [event_stream.close, event_raw_stream.close]
        if owns_gallery_preparer:
            teardown_operations.append(gallery_preparer.close)
        if shared_worker_pool is not None:
            teardown_operations.append(
                shared_worker_pool.close  # type: ignore[attr-defined]
            )
        for operation in teardown_operations:
            try:
                operation()
            except BaseException as exc:  # close everything before propagating
                if teardown_error is None:
                    teardown_error = exc
        if teardown_error is not None:
            raise teardown_error

    reports = dict(
        score_full_pipeline(
            asr_utterances=asr_rows,
            resource_samples=(
                resource_samples if job.measurement_mode == "resources" else None
            ),
            resource_kwargs=(
                {
                    "audio_duration_sec": completed_audio or None,
                    "wall_time_sec": (
                        measured_runtime_wall_sec if completed_audio > 0 else None
                    ),
                    "startup_sec": None,
                    "model_bytes": _model_bytes(selection),
                    "cache_bytes": _directory_bytes(runtime_cache_root),
                    "maximum_queue_depth": maximum_queue_depth_seen,
                    "failure_count": len(errors),
                    "retry_count": 0,
                }
                if job.measurement_mode == "resources"
                else {
                    "failure_count": len(errors),
                    "retry_count": 0,
                }
            ),
        )
    )
    reports.update(
        {
            category: _aggregate_recording_reports(category, rows)
            for category, rows in case_reports.items()
        }
    )
    metric_documents = build_metric_documents_from_reports(
        reports, run_id=run_id, pipeline_id=job.pipeline_id
    )
    builder.publish_events_file(event_staging_path)
    builder.publish_predictions(
        transcript_rows=transcript_rows,
        labelled_rows=labelled_rows,
        diarization_rttm=_rttm(hypothesis_segments),
    )
    reference_payload = b"".join(
        canonical_json_bytes(_portable_reference(case)) + b"\n" for case in cases
    )
    reference_artifacts = {
        "references/cases.jsonl": reference_payload,
        **_selected_protocol_reference_artifacts(cases, protocol_context),
    }
    if selected_profile_rows:
        reference_artifacts["references/selected_enrollment_profiles.jsonl"] = b"".join(
            canonical_json_bytes(row) + b"\n"
            for row in sorted(
                selected_profile_rows,
                key=lambda value: (
                    str(value.get("case_id")),
                    str(value.get("profile_id")),
                ),
            )
        )
    builder.publish_references(
        {
            "artifacts": [
                {
                    "artifact_id": Path(logical_path).stem,
                    "status": "available",
                    "logical_path": logical_path,
                    "reason": None,
                }
                for logical_path in sorted(reference_artifacts)
            ]
        },
        artifacts=reference_artifacts,
    )
    for view, document in metric_documents.items():
        builder.publish_metric(view, document)
    diagnostic_payload = b"".join(
        canonical_json_bytes(row) + b"\n" for row in case_status
    )
    diagnostic_artifacts = {
        "diagnostics/case_status.jsonl": diagnostic_payload,
        "diagnostics/per_case_metrics.jsonl": b"".join(
            canonical_json_bytes(row) + b"\n" for row in per_case_metric_rows
        ),
        "diagnostics/cache_regime.json": canonical_json_bytes(
            {
                "schema_version": "full-pipeline-cache-regime.v1",
                "measurement_mode": job.measurement_mode,
                "runtime_cache_scope": (
                    "shared_cross_job_accuracy"
                    if job.measurement_mode == "accuracy"
                    else "isolated_attempt_local_resource_cold_start"
                ),
                "asr_stream_trace_enabled": job.measurement_mode == "accuracy",
                "resource_measurement_serial_required": (
                    job.measurement_mode == "resources"
                ),
                "enrollment_profile_materialization_excluded_from_runtime_span": True,
            }
        ),
    }
    diagnostic_manifest_rows = [
        {
            "artifact_id": "case_status",
            "status": "available",
            "logical_path": "diagnostics/case_status.jsonl",
            "reason": None,
        },
        {
            "artifact_id": "per_case_metrics",
            "status": "available",
            "logical_path": "diagnostics/per_case_metrics.jsonl",
            "reason": None,
        },
        {
            "artifact_id": "cache_regime",
            "status": "available",
            "logical_path": "diagnostics/cache_regime.json",
            "reason": None,
        },
    ]
    if challenger_score_observations:
        logical_path = "diagnostics/challenger_identity_scores.jsonl"
        diagnostic_artifacts[logical_path] = b"".join(
            canonical_json_bytes(row) + b"\n" for row in challenger_score_observations
        )
        diagnostic_manifest_rows.append(
            {
                "artifact_id": "challenger_identity_scores",
                "status": "available",
                "logical_path": logical_path,
                "reason": None,
            }
        )
    if overlap_score_diagnostics:
        logical_path = "diagnostics/overlap_identity_scores.jsonl"
        diagnostic_artifacts[logical_path] = b"".join(
            canonical_json_bytes(row) + b"\n" for row in overlap_score_diagnostics
        )
        diagnostic_manifest_rows.append(
            {
                "artifact_id": "overlap_identity_scores",
                "status": "available",
                "logical_path": logical_path,
                "reason": None,
            }
        )
    if short_turn_diagnostics:
        logical_path = "diagnostics/short_turn_decisions.jsonl"
        diagnostic_artifacts[logical_path] = b"".join(
            canonical_json_bytes(row) + b"\n" for row in short_turn_diagnostics
        )
        diagnostic_manifest_rows.append(
            {
                "artifact_id": "short_turn_decisions",
                "status": "available",
                "logical_path": logical_path,
                "reason": None,
            }
        )
    builder.publish_diagnostics(
        {"artifacts": diagnostic_manifest_rows},
        artifacts=diagnostic_artifacts,
    )
    terminal = "stopped" if stopped else "failed" if errors else "complete"
    builder.publish_run(
        build_run_document(
            run_id=run_id,
            attempt_id=attempt_id,
            reuse_identity=job.reuse_identity,
            status=terminal,
            created_at_utc=created_at,
            started_at_utc=created_at,
            ended_at_utc=_utc_now(),
            artifact_support=artifact_support,
            counts={
                "planned_cases": job.case_count,
                "completed_cases": completed_cases,
                "planned_audio_sec": job.audio_duration_sec,
                "completed_audio_sec": completed_audio,
            },
            errors=errors,
            result_tree_schema_version=builder.result_tree_schema_version,
        )
    )
    validation = builder.finalize()
    event_staging_path.unlink(missing_ok=True)
    if staging_root.is_dir() and not any(staging_root.iterdir()):
        staging_root.rmdir()
    if runtime_root.is_dir() and not any(runtime_root.iterdir()):
        runtime_root.rmdir()
    return {
        "state": terminal,
        "completed_cases": completed_cases,
        "completed_audio_sec": completed_audio,
        "result_valid": validation.valid,
        "result_reusable": validation.reusable,
        "error": errors[-1] if errors else None,
    }


def _case_cursor_binding(
    job: EvaluationJobSpec, cases: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    core = {
        "schema_version": "full-pipeline-case-cursor-binding.v1",
        "job_id": job.job_id,
        "reuse_identity_sha256": job.reuse_identity["identity_sha256"],
        "case_order": [
            {
                "ordinal": index,
                "case_id": _case_id(case),
                "case_identity_sha256": sha256_bytes(canonical_json_bytes(case)),
            }
            for index, case in enumerate(cases, start=1)
        ],
    }
    return {**core, "binding_sha256": sha256_bytes(canonical_json_bytes(core))}


def _write_case_cursor(
    root: Path,
    *,
    binding: Mapping[str, object],
    completed_shards: Mapping[str, str],
) -> dict[str, object]:
    case_ids = {
        str(row["case_id"])
        for row in binding.get("case_order", [])  # type: ignore[union-attr]
        if isinstance(row, Mapping) and row.get("case_id")
    }
    if set(completed_shards) - case_ids:
        raise ValueError("case cursor contains an undeclared case shard")
    core = {
        "schema_version": "full-pipeline-case-cursor.v1",
        "binding": dict(binding),
        "completed_case_count": len(completed_shards),
        "completed_shards": dict(sorted(completed_shards.items())),
    }
    document = {
        **core,
        "cursor_sha256": sha256_bytes(canonical_json_bytes(core)),
    }
    write_json_atomic(root / "cursor.json", document)
    return document


def _write_case_shard(
    path: Path,
    *,
    job: EvaluationJobSpec,
    case: Mapping[str, object],
    ordinal: int,
    payload: Mapping[str, object],
) -> dict[str, object]:
    core = {
        "schema_version": "full-pipeline-case-shard.v1",
        "status": "complete",
        "job_id": job.job_id,
        "reuse_identity_sha256": job.reuse_identity["identity_sha256"],
        "ordinal": ordinal,
        "case_id": _case_id(case),
        "case_identity_sha256": sha256_bytes(canonical_json_bytes(case)),
        "payload": dict(payload),
    }
    document = {
        **core,
        "shard_sha256": sha256_bytes(canonical_json_bytes(core)),
    }
    write_json_atomic(path, document)
    return document


def _cleanup_completed_case_root(
    runtime_root: Path, case_root: Path
) -> dict[str, object]:
    """Delete only a verified generated case tree after its shard is durable.

    Failed and partial cases never call this helper.  The exact target must be
    one direct, non-symlink child of the intended runtime root; shared caches,
    enrollment galleries, source audio, and model assets are outside that root.
    """

    runtime_path = Path(runtime_root)
    if runtime_path.is_symlink():
        raise ValueError("completed-case cleanup refuses a symlink runtime root")
    intended = runtime_path.resolve(strict=False)
    target_path = Path(case_root)
    target = target_path.resolve(strict=False)
    if target == intended or target.parent != intended:
        raise ValueError(
            f"completed-case cleanup target escaped runtime root: {target}"
        )
    if target_path.is_symlink():
        raise ValueError("completed-case cleanup refuses symlink targets")
    if not target_path.exists():
        return {
            "status": "ALREADY_ABSENT",
            "target": str(target),
            "reason": "no completed runtime tree remained",
        }
    try:
        shutil.rmtree(target)
    except OSError as exc:
        return {
            "status": "FAILED",
            "target": str(target),
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": "DELETED_AFTER_CHECKSUM_VALID_SHARD",
        "target": str(target),
        "reason": "regenerable completed runtime tree removed",
    }


def _cleanup_completed_case_roots_after_valid_shard(
    attempts_root: Path,
    current_runtime_root: Path,
    case_id: str,
) -> dict[str, object]:
    """Clean crash leftovers for one checksum-valid shard across attempts."""

    root_path = Path(attempts_root)
    root = root_path.resolve(strict=False)
    if root_path.is_symlink():
        raise ValueError("completed-case cleanup refuses a symlink attempts root")
    current_path = Path(current_runtime_root)
    if current_path.is_symlink():
        raise ValueError("completed-case cleanup refuses a symlink runtime root")
    current = current_path.resolve(strict=False)
    if current.name != "runtime_cases" or current.parent.parent != root:
        raise ValueError("current runtime root escaped the intended attempts root")
    runtime_roots: set[Path] = {current}
    if root_path.is_dir():
        for attempt_path in root_path.glob("attempt_[0-9][0-9][0-9]"):
            if not attempt_path.is_dir() or attempt_path.is_symlink():
                continue
            attempt = attempt_path.resolve(strict=False)
            if attempt.parent != root:
                raise ValueError("attempt cleanup candidate escaped attempts root")
            runtime_path = attempt_path / "runtime_cases"
            if runtime_path.is_symlink():
                raise ValueError("completed-case cleanup refuses symlink runtime roots")
            runtime = runtime_path.resolve(strict=False)
            if runtime.parent != attempt or runtime.name != "runtime_cases":
                raise ValueError("runtime cleanup candidate escaped attempt")
            runtime_roots.add(runtime)
    outcomes = [
        _cleanup_completed_case_root(
            runtime,
            runtime / _portable_id(case_id),
        )
        for runtime in sorted(runtime_roots, key=str)
    ]
    failures = [row for row in outcomes if row["status"] == "FAILED"]
    deleted = [
        row for row in outcomes if row["status"] == "DELETED_AFTER_CHECKSUM_VALID_SHARD"
    ]
    if failures:
        return {
            "status": "FAILED",
            "reason": "; ".join(str(row.get("reason")) for row in failures),
            "outcomes": outcomes,
        }
    return {
        "status": (
            f"DELETED_{len(deleted)}_CHECKSUM_VALID_RUNTIME_TREES"
            if deleted
            else "ALREADY_ABSENT"
        ),
        "reason": (
            "removed completed crash leftovers after checksum-valid shard"
            if deleted
            else "no completed runtime tree remained"
        ),
        "outcomes": outcomes,
    }


def _load_valid_case_shard(
    path: Path,
    *,
    job: EvaluationJobSpec,
    case: Mapping[str, object],
    ordinal: int,
) -> dict[str, object] | None:
    try:
        document = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    unsigned = dict(document)
    expected = unsigned.pop("shard_sha256", None)
    if expected != sha256_bytes(canonical_json_bytes(unsigned)):
        return None
    exact = {
        "schema_version": "full-pipeline-case-shard.v1",
        "status": "complete",
        "job_id": job.job_id,
        "reuse_identity_sha256": job.reuse_identity["identity_sha256"],
        "ordinal": ordinal,
        "case_id": _case_id(case),
        "case_identity_sha256": sha256_bytes(canonical_json_bytes(case)),
    }
    if any(document.get(key) != value for key, value in exact.items()):
        return None
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        return None
    try:
        for key in (
            "events",
            "transcript_rows",
            "labelled_rows",
            "hypothesis_segments",
            "asr_rows",
            "resource_samples",
            "per_case_metric_rows",
            "challenger_score_observations",
            "overlap_score_diagnostics",
            "short_turn_diagnostics",
            "embedding_reuse_observations",
            "embedding_reuse_telemetry",
            "selected_profile_rows",
            "case_status",
        ):
            _mapping_rows(payload, key)
        reports = payload.get("case_reports")
        if not isinstance(reports, Mapping) or set(reports) != {
            "streaming",
            "diarization",
            "identity",
            "speaker_transcription",
            "ux",
        }:
            return None
        for report in reports.values():
            if not isinstance(report, Mapping):
                return None
            _metric_report_from_json(report)
    except (TypeError, ValueError, KeyError):
        return None
    return document


def _mapping_rows(value: Mapping[str, object], key: str) -> list[dict[str, object]]:
    rows = value.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError(f"case shard {key} must be a list of objects")
    return [dict(row) for row in rows]


def _metric_report_from_json(value: Mapping[str, object]) -> MetricReport:
    raw_metrics = value.get("metrics")
    if not isinstance(raw_metrics, Mapping):
        raise ValueError("case shard metric report lacks metrics")
    metrics: dict[str, MetricValue] = {}
    for metric_id, raw in raw_metrics.items():
        if not isinstance(raw, Mapping) or str(raw.get("metric_id")) != str(metric_id):
            raise ValueError("case shard metric identity differs")
        prerequisites = raw.get("prerequisites")
        details = raw.get("details")
        if not isinstance(prerequisites, list) or not isinstance(details, Mapping):
            raise ValueError("case shard metric contract differs")
        definition = MetricDefinition(
            metric_id=str(metric_id),
            category=str(raw["category"]),
            display_name=str(raw["display_name"]),
            definition=str(raw["definition"]),
            unit=str(raw["unit"]),
            higher_is_better=(
                bool(raw["higher_is_better"])
                if raw.get("higher_is_better") is not None
                else None
            ),
            prerequisites=tuple(str(item) for item in prerequisites),
        )
        status_value = str(raw["status"])
        if status_value not in {"computed", "unsupported", "undefined"}:
            raise ValueError("case shard metric status differs")
        metrics[str(metric_id)] = MetricValue(
            definition=definition,
            status=status_value,  # type: ignore[arg-type]
            value=raw.get("value"),  # type: ignore[arg-type]
            numerator=raw.get("numerator"),  # type: ignore[arg-type]
            denominator=raw.get("denominator"),  # type: ignore[arg-type]
            reason=(str(raw["reason"]) if raw.get("reason") is not None else None),
            details=dict(details),
        )
    warnings = value.get("warnings")
    if not isinstance(warnings, list):
        raise ValueError("case shard report warnings differ")
    return MetricReport(
        category=str(value["category"]),
        metrics=metrics,
        warnings=tuple(str(item) for item in warnings),
        schema_version=str(value["schema_version"]),
    )


def _load_protocol_context(
    split: str,
    cases: Sequence[Mapping[str, object]],
    *,
    protocol_root: Path | None = None,
) -> ProtocolContext:
    root = Path(protocol_root or DEFAULT_PROTOCOL_ROOT).resolve()
    controlled = any(case.get("source_reference_id") for case in cases)
    split_root = root / split
    paths = {
        "references": split_root / "references/speaker_attributed_transcript.jsonl",
        "overlays": split_root / "identity/identity_overlays.jsonl",
        "enrollments": split_root / "enrollment/enrollment_registry.jsonl",
    }
    if controlled:
        missing = [str(path) for path in paths.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "prepared protocol context is incomplete: " + ", ".join(missing)
            )

    def indexed(path: Path, key: str) -> dict[str, Mapping[str, object]]:
        result: dict[str, Mapping[str, object]] = {}
        for row in _jsonl(path):
            identity = str(row.get(key) or "")
            if not identity or identity in result:
                raise ValueError(f"invalid or duplicate {key} in {path}")
            if str(row.get("partition") or split) != split:
                raise ValueError(f"{key} belongs to another protocol split")
            result[identity] = row
        return result

    context = ProtocolContext(
        root=root,
        split=split,
        references=(
            indexed(paths["references"], "source_reference_id")
            if paths["references"].is_file()
            else {}
        ),
        overlays=(
            indexed(paths["overlays"], "identity_overlay_ref")
            if paths["overlays"].is_file()
            else {}
        ),
        enrollments=(
            indexed(paths["enrollments"], "enrolled_id")
            if paths["enrollments"].is_file()
            else {}
        ),
    )
    for case in cases:
        reference_id = case.get("source_reference_id")
        if reference_id is None:
            continue
        if str(reference_id) not in context.references:
            raise KeyError(
                f"case {_case_id(case)} references absent transcript {reference_id}"
            )
        overlay_id = str(case.get("identity_overlay_ref") or "")
        if overlay_id not in context.overlays:
            raise KeyError(
                f"case {_case_id(case)} references absent overlay {overlay_id}"
            )
        gallery = {str(value) for value in case.get("gallery_enrolled_ids", [])}
        if gallery - set(context.enrollments):
            raise KeyError(
                f"case {_case_id(case)} references absent enrollment identities: "
                f"{sorted(gallery - set(context.enrollments))}"
            )
        overlay_gallery = {
            str(row.get("enrolled_id") or "")
            for row in context.overlays[overlay_id].get("enrollment_database", [])
        }
        if gallery - overlay_gallery:
            raise KeyError(
                f"case {_case_id(case)} gallery is absent from overlay {overlay_id}: "
                f"{sorted(gallery - overlay_gallery)}"
            )
    return context


def _case_reference(
    case: Mapping[str, object], context: ProtocolContext
) -> Mapping[str, object]:
    reference_id = case.get("source_reference_id")
    if reference_id is None:
        return case
    return context.references[str(reference_id)]


def _case_overlay(
    case: Mapping[str, object], context: ProtocolContext
) -> Mapping[str, object] | None:
    overlay_id = case.get("identity_overlay_ref")
    if overlay_id is None:
        return None
    return context.overlays[str(overlay_id)]


def _selected_protocol_reference_artifacts(
    cases: Sequence[Mapping[str, object]], context: ProtocolContext
) -> dict[str, bytes]:
    reference_ids = sorted(
        {
            str(case["source_reference_id"])
            for case in cases
            if case.get("source_reference_id")
        }
    )
    overlay_ids = sorted(
        {
            str(case["identity_overlay_ref"])
            for case in cases
            if case.get("identity_overlay_ref")
        }
    )
    enrollment_ids = sorted(
        {str(value) for case in cases for value in case.get("gallery_enrolled_ids", [])}
    )
    artifacts: dict[str, bytes] = {}
    for logical_path, rows in (
        (
            "references/selected_speaker_attributed_transcripts.jsonl",
            [context.references[value] for value in reference_ids],
        ),
        (
            "references/selected_identity_overlays.jsonl",
            [context.overlays[value] for value in overlay_ids],
        ),
        (
            "references/selected_enrollment_registry.jsonl",
            [context.enrollments[value] for value in enrollment_ids],
        ),
    ):
        if rows:
            artifacts[logical_path] = b"".join(
                canonical_json_bytes(row) + b"\n" for row in rows
            )
    return artifacts


def _hydrate_case(
    case: Mapping[str, object], context: ProtocolContext
) -> dict[str, object]:
    reference = _case_reference(case, context)
    if case.get("source_reference_id") is None and case.get(
        "reference_transcripts_logical_path"
    ):
        reference = _native_transcript_reference(case)
    offset = float(case.get("source_start_sec") or 0.0)
    duration = _duration(case)
    recording_ids = {
        str(value)
        for value in (
            case.get("source_case_id"),
            case.get("source_recording_id"),
            case.get("protocol_case_id"),
        )
        if value
    }
    diarization_segments: list[dict[str, object]] = []
    rttm_value = case.get("reference_rttm_logical_path")
    if isinstance(rttm_value, str) and rttm_value:
        rttm_path = _resolve_reference_path(
            rttm_value, expected_sha256=case.get("reference_rttm_sha256")
        )
        diarization_segments = _parse_rttm(
            rttm_path,
            recording_ids=recording_ids,
            source_offset_sec=offset,
            duration_sec=duration,
        )
    if not diarization_segments:
        diarization_segments = _reference_segments(case, reference)

    uem: list[tuple[float, float]] | None = None
    uem_value = case.get("reference_uem_logical_path")
    if isinstance(uem_value, str) and uem_value:
        uem_path = _resolve_reference_path(
            uem_value, expected_sha256=case.get("reference_uem_sha256")
        )
        uem = _parse_uem(
            uem_path,
            recording_ids=recording_ids,
            source_offset_sec=offset,
            duration_sec=duration,
        )
    segments = [
        dict(value)
        for value in reference.get("segments", [])
        if isinstance(value, Mapping)
    ]
    return {
        "reference": reference,
        "overlay": _case_overlay(case, context),
        "reference_text": _reference_text(case, reference),
        "speaker_texts": _speaker_texts(case, reference),
        "transcript_segments": segments,
        "speaker_transcript_supported": bool(segments)
        and all(
            value.get("scorable_transcript") is not None
            and value.get("text", value.get("scorable_transcript")) is not None
            for value in segments
        ),
        "diarization_segments": diarization_segments,
        "uem": uem,
    }


def _require_declared_prerequisites(
    case: Mapping[str, object], science: Mapping[str, object]
) -> None:
    supported = {str(value) for value in case.get("supported_views", [])}
    missing: list[str] = []
    if "asr" in supported and not str(science.get("reference_text") or "").strip():
        missing.append("ASR transcript")
    if "diarization" in supported:
        if not science.get("diarization_segments"):
            missing.append("RTTM/reference segments")
        if science.get("uem") is None:
            missing.append("UEM scored regions")
    if "identity" in supported:
        if not isinstance(science.get("overlay"), Mapping):
            missing.append("identity overlay")
        if not case.get("gallery_enrolled_ids"):
            missing.append("frozen gallery")
    if "speaker_attributed_transcript" in supported and not science.get(
        "speaker_texts"
    ):
        missing.append("speaker-attributed transcript")
    if missing:
        raise ValueError(
            f"declared supported views lack hydrated prerequisites for "
            f"{_case_id(case)}: {', '.join(missing)}"
        )


def _resolve_reference_path(
    logical_path: str, *, expected_sha256: object | None = None
) -> Path:
    value = Path(logical_path)
    candidates = [value] if value.is_absolute() else [EVALUATION_ROOT / value]
    candidates.extend(
        [resolve_data_path_from_logical(value), EVALUATION_ROOT.parents[1] / value]
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if not resolved.is_file():
            continue
        if (
            expected_sha256 is not None
            and sha256_file(resolved).casefold() != str(expected_sha256).casefold()
        ):
            raise ValueError(f"reference checksum mismatch: {logical_path}")
        return resolved
    raise FileNotFoundError(logical_path)


def _native_transcript_reference(case: Mapping[str, object]) -> dict[str, object]:
    path = _resolve_reference_path(str(case["reference_transcripts_logical_path"]))
    source_id = str(case.get("source_case_id") or "")
    offset = float(case.get("source_start_sec") or 0.0)
    duration = _duration(case)
    segments: list[dict[str, object]] = []
    for row in _jsonl(path):
        if str(row.get("evaluation_unit_id")) != source_id:
            continue
        start = float(row["start_sec"]) - offset
        end = float(row["end_sec"]) - offset
        clipped_start = max(0.0, start)
        clipped_end = min(duration, end)
        if clipped_end <= clipped_start:
            continue
        full = bool(row.get("full_reference_segment")) and row.get("text") is not None
        segments.append(
            {
                **row,
                "start_sec": clipped_start,
                "end_sec": clipped_end,
                "global_speaker_id": str(row.get("speaker_label") or "unknown"),
                "scorable_transcript": str(row["text"]) if full else None,
                "scorable_transcript_normalized": str(row["text"]) if full else None,
            }
        )
    return {
        "source_reference_id": source_id,
        "segments": sorted(
            segments, key=lambda row: (row["start_sec"], row["end_sec"])
        ),
        "speaker_attributed_transcript_status": (
            "supported"
            if segments
            and all(row.get("scorable_transcript") is not None for row in segments)
            else "partial"
        ),
    }


def _parse_rttm(
    path: Path,
    *,
    recording_ids: set[str],
    source_offset_sec: float,
    duration_sec: float,
) -> list[dict[str, object]]:
    parsed: list[tuple[str, dict[str, object]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[0] != "SPEAKER":
            continue
        start = float(fields[3]) - source_offset_sec
        end = start + float(fields[4])
        clipped_start = max(0.0, start)
        clipped_end = min(duration_sec, end)
        if clipped_end > clipped_start:
            parsed.append(
                (
                    fields[1],
                    {
                        "start_sec": clipped_start,
                        "end_sec": clipped_end,
                        "speaker_id": fields[7],
                    },
                )
            )
    selected = [row for recording, row in parsed if recording in recording_ids]
    if not selected and len({recording for recording, _ in parsed}) == 1:
        selected = [row for _, row in parsed]
    return sorted(
        selected, key=lambda row: (row["start_sec"], row["end_sec"], row["speaker_id"])
    )


def _parse_uem(
    path: Path,
    *,
    recording_ids: set[str],
    source_offset_sec: float,
    duration_sec: float,
) -> list[tuple[float, float]]:
    parsed: list[tuple[str, tuple[float, float]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        start = max(0.0, float(fields[2]) - source_offset_sec)
        end = min(duration_sec, float(fields[3]) - source_offset_sec)
        if end > start:
            parsed.append((fields[0], (start, end)))
    selected = [row for recording, row in parsed if recording in recording_ids]
    if not selected and len({recording for recording, _ in parsed}) == 1:
        selected = [row for _, row in parsed]
    return sorted(set(selected))


def _prepare_runtime_audio(
    source: Path, case: Mapping[str, object], case_root: Path
) -> Path:
    start = float(case.get("source_start_sec") or 0.0)
    end_raw = case.get("source_end_sec")
    if end_raw is None:
        return source
    end = float(end_raw)
    if end <= start:
        raise ValueError(f"invalid native source interval for {_case_id(case)}")
    import soundfile as sf

    info = sf.info(source)
    source_duration = info.frames / info.samplerate
    if start <= 0 and end >= source_duration:
        return source
    start_frame = round(start * info.samplerate)
    end_frame = round(end * info.samplerate)
    audio, sample_rate = sf.read(
        source,
        start=start_frame,
        stop=end_frame,
        dtype="float32",
        always_2d=True,
    )
    if len(audio) == 0:
        raise ValueError(f"native source interval is empty for {_case_id(case)}")
    target = case_root / "input/source_excerpt.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp.wav")
    sf.write(temporary, audio, sample_rate, subtype="FLOAT")
    temporary.replace(target)
    return target


def _run_runtime_with_stop(
    runtime: object, stop_requested: StopCallback
) -> Mapping[str, object]:
    finished = threading.Event()

    def watch() -> None:
        while not finished.wait(0.1):
            if not stop_requested():
                continue
            request_stop = getattr(runtime, "request_stop", None)
            if callable(request_stop):
                request_stop()
            return

    watcher = threading.Thread(target=watch, name="evaluation-case-stop", daemon=True)
    watcher.start()
    try:
        run = getattr(runtime, "run", None)
        if not callable(run):
            raise TypeError("runtime builder did not return a runnable coordinator")
        value = run()
        if not isinstance(value, Mapping):
            raise TypeError("runtime result must be a mapping")
        return value
    finally:
        finished.set()
        watcher.join(timeout=1.0)


def _merge_asr_diagnostics(
    events: Sequence[Mapping[str, object]],
    diagnostics: Sequence[Mapping[str, object]],
    case_id: str,
) -> list[dict[str, object]]:
    merged = [dict(row) for row in events]
    seen = {str(row.get("event_id")) for row in merged if row.get("event_id")}
    for row in diagnostics:
        event_id = str(row.get("event_id") or "")
        if event_id and event_id in seen:
            continue
        merged.append(_enrich_event(row, case_id))
        if event_id:
            seen.add(event_id)
    return sorted(
        merged,
        key=lambda row: (
            int(row.get("event_sequence") or 0),
            str(row.get("event_id") or ""),
        ),
    )


def _anonymous_speaker_id(span: Mapping[str, object]) -> str:
    direct = span.get("anonymous_speaker_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    label = span.get("speaker_label")
    if isinstance(label, Mapping):
        value = label.get("anonymous_speaker_id")
        return str(value).strip() if value else ""
    return ""


def _streaming_reference_map(
    events: Sequence[Mapping[str, object]], science: Mapping[str, object]
) -> dict[str, str]:
    finals = [row for row in events if row.get("event_type") == "asr_final"]
    segments = [
        row
        for row in science.get("transcript_segments", [])
        if isinstance(row, Mapping)
        and (row.get("scorable_transcript") is not None or row.get("text") is not None)
    ]
    result: dict[str, str] = {}
    for event in finals:
        capture = event.get("capture_timestamps")
        start = end = None
        if isinstance(capture, Mapping):
            start = capture.get("audio_start_sec")
            end = capture.get("audio_end_sec")
        if end is None:
            end = event.get("audio_consumed_through_sec") or event.get("end_sec")
        if start is None and len(finals) == 1:
            start = 0.0
        texts: list[str] = []
        if start is not None and end is not None:
            for row in sorted(segments, key=lambda value: float(value["start_sec"])):
                if float(row["start_sec"]) < float(end) and float(
                    row["end_sec"]
                ) > float(start):
                    text = row.get("scorable_transcript") or row.get("text")
                    if text:
                        texts.append(str(text))
        reference = " ".join(texts).strip()
        if not reference and len(finals) == 1:
            reference = str(science.get("reference_text") or "").strip()
        if reference:
            result[str(event.get("hypothesis_id"))] = reference
    return result


def _h2_integration_partition(
    execution_contract: Mapping[str, object] | None,
    *,
    job: EvaluationJobSpec,
    cases: Sequence[Mapping[str, object]],
) -> dict[str, object] | None:
    """Validate an optional H2 source-group calibration assignment.

    Legacy evaluation callers do not provide this contract and retain their
    existing development role.  V1 is exhaustive over its execution job.  V2
    inventories the original panel while execution is exactly its speaker-
    disjoint calibration/selection subset; excluded cross-cohort cases are
    rejected before any model worker is started.
    """

    if execution_contract is None:
        return None
    raw = execution_contract.get("h2_development_integration_partition")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("H2 integration partition must be an object")
    if job.split != "development":
        raise ValueError("H2 integration partition is forbidden outside development")
    partition = dict(raw)
    schema = str(partition.get("schema_version") or "")
    if schema not in {
        "h2-development-integration-partition.v1",
        "h2-development-integration-partition.v2",
    }:
        raise ValueError("unexpected H2 integration partition schema")
    if partition.get("outcomes_used") is not False:
        raise ValueError("H2 integration partition used outcomes")
    if schema == "h2-development-integration-partition.v1":
        if partition.get("reference_content_used") is not False:
            raise ValueError("H2 integration partition used reference content")
    else:
        if partition.get("prediction_or_metric_inputs_used") is not False:
            raise ValueError("H2 integration partition used predictions or metrics")
        if partition.get("reference_transcript_or_audio_content_used") is not False:
            raise ValueError("H2 integration partition used reference content")
    if partition.get("evaluation_material_used") is not False:
        raise ValueError("H2 integration partition used evaluation material")
    expected_sha256 = str(partition.get("assignment_sha256") or "")
    unsigned = dict(partition)
    unsigned.pop("assignment_sha256", None)
    observed_sha256 = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    if expected_sha256 != observed_sha256:
        raise ValueError("H2 integration partition checksum differs")
    calibration = set(map(str, partition.get("calibration_case_ids") or ()))
    selection = set(map(str, partition.get("selection_case_ids") or ()))
    excluded = (
        set(map(str, partition.get("excluded_cross_cohort_case_ids") or ()))
        if schema == "h2-development-integration-partition.v2"
        else set()
    )
    case_ids = {_case_id(case) for case in cases}
    if (
        not calibration
        or not selection
        or calibration & selection
        or calibration & excluded
        or selection & excluded
    ):
        raise ValueError("H2 integration roles are empty or overlapping")
    if schema == "h2-development-integration-partition.v1":
        if calibration | selection != case_ids:
            raise ValueError("H2 integration roles do not exactly cover the job cases")
    else:
        # The immutable v2 partition inventories every case in the original
        # 807-case development integration panel, including cross-cohort cases
        # excluded by the speaker-disjoint firewall.  The execution job is the
        # smaller, predeclared integration_eligible panel and therefore must be
        # exactly calibration | selection and disjoint from the excluded set.
        if case_ids != calibration | selection:
            raise ValueError(
                "H2 v2 execution cases must exactly match calibration and "
                "selection roles"
            )
        if case_ids & excluded:
            raise ValueError("H2 v2 execution included an excluded cross-cohort case")
        if int(partition.get("calibration_case_count") or -1) != len(calibration):
            raise ValueError("H2 v2 calibration case count differs")
        if int(partition.get("selection_case_count") or -1) != len(selection):
            raise ValueError("H2 v2 selection case count differs")
        if int(partition.get("excluded_cross_cohort_case_count") or -1) != len(
            excluded
        ):
            raise ValueError("H2 v2 excluded case count differs")
    if schema == "h2-development-integration-partition.v2":
        calibration_speakers = set(
            map(str, partition.get("calibration_speaker_ids") or ())
        )
        selection_speakers = set(map(str, partition.get("selection_speaker_ids") or ()))
        if not calibration_speakers or not selection_speakers:
            raise ValueError("H2 integration speaker roles are empty")
        if calibration_speakers & selection_speakers:
            raise ValueError("H2 integration speaker roles overlap")
        if partition.get("speaker_overlap_count") != 0:
            raise ValueError("H2 integration declared nonzero speaker overlap")
        if (
            partition.get("excluded_cases_used_for_calibration_or_selection")
            is not False
        ):
            raise ValueError("H2 integration reused excluded cross-cohort cases")
        observed_by_role: dict[str, set[str]] = {
            "calibration": set(),
            "selection": set(),
        }
        for case in cases:
            case_id = _case_id(case)
            role = (
                "calibration"
                if case_id in calibration
                else "selection" if case_id in selection else "excluded_cross_cohort"
            )
            if role == "excluded_cross_cohort":
                continue
            speakers = set(map(str, case.get("global_speaker_ids") or ()))
            if not speakers:
                mapping = case.get("local_to_global_speaker")
                if isinstance(mapping, Mapping):
                    speakers = set(map(str, mapping.values()))
            if not speakers:
                raise ValueError(
                    f"H2 integration {role} case lacks speaker metadata: {case_id}"
                )
            observed_by_role[role].update(speakers)
        if observed_by_role["calibration"] - calibration_speakers:
            raise ValueError("H2 calibration case speaker is absent from its cohort")
        if observed_by_role["selection"] - selection_speakers:
            raise ValueError("H2 selection case speaker is absent from its cohort")
        if observed_by_role["calibration"] & observed_by_role["selection"]:
            raise ValueError("H2 integration case speakers cross role cohorts")
    return partition


def _h2_integration_case_role(
    partition: Mapping[str, object] | None, case_id: str
) -> str | None:
    if partition is None:
        return None
    for role, key in (
        ("calibration", "calibration_case_ids"),
        ("selection", "selection_case_ids"),
        ("excluded_cross_cohort", "excluded_cross_cohort_case_ids"),
    ):
        if case_id in set(map(str, partition.get(key) or ())):
            return role
    raise ValueError(f"H2 integration case has no role: {case_id}")


def _challenger_score_observations(
    rows: Sequence[Mapping[str, object]],
    *,
    job: EvaluationJobSpec,
    case: Mapping[str, object],
    science: Mapping[str, object],
    hypothesis_segments: Sequence[Mapping[str, object]],
    selection: object,
    gallery: PreparedGallery,
    h2_integration_partition: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    """Join raw challenger scores to frozen development truth and gallery IDs."""

    if not rows:
        return []
    if job.split != "development":
        raise ValueError(
            "unresolved challenger scores are forbidden outside development"
        )
    from app.full_pipeline_development.policies import development_role

    truth_by_cluster = _anonymous_reference_truth(case, science, hypothesis_segments)
    case_id = _case_id(case)
    source_case_id = str(case.get("source_case_id") or case_id)
    gallery_ids = tuple(str(value) for value in case.get("gallery_enrolled_ids", ()))
    profile_rows = tuple(dict(value) for value in gallery.profiles)
    gallery_identity = (
        str(profile_rows[0].get("gallery_sha256"))
        if profile_rows and profile_rows[0].get("gallery_sha256")
        else hashlib.sha256(
            canonical_json_bytes(
                {
                    "gallery_enrolled_ids": gallery_ids,
                    "profiles": profile_rows,
                }
            )
        ).hexdigest()
    )
    observations: list[dict[str, object]] = []
    h2_role: str | None = None
    h2_assignment_sha256: str | None = None
    if h2_integration_partition is not None:
        calibration_ids = set(
            map(str, h2_integration_partition["calibration_case_ids"])
        )
        selection_ids = set(map(str, h2_integration_partition["selection_case_ids"]))
        excluded_ids = set(
            map(
                str,
                h2_integration_partition.get("excluded_cross_cohort_case_ids", ()),
            )
        )
        if case_id in calibration_ids:
            h2_role = "calibration"
        elif case_id in selection_ids:
            h2_role = "selection"
        elif case_id in excluded_ids:
            # Excluded cross-cohort cases remain valid runtime/accuracy cases,
            # but must not emit private score observations or enter policy fit.
            return []
        else:  # Defensive; the contract is validated before inference.
            raise ValueError(f"H2 integration case has no role: {case_id}")
        h2_assignment_sha256 = str(h2_integration_partition["assignment_sha256"])
    for index, raw in enumerate(rows):
        diagnostic_schema = str(raw.get("schema_version") or "")
        if diagnostic_schema == (
            "full-pipeline-development-identity-score-diagnostic.v1"
        ):
            predicted_overlap_value = raw.get("predicted_overlap")
            if not isinstance(predicted_overlap_value, bool):
                raise ValueError(
                    "development identity-score diagnostic lacks boolean "
                    "predicted_overlap"
                )
            predicted_overlap = predicted_overlap_value
        else:
            predicted_overlap = bool(raw.get("predicted_overlap", False))
        cluster_id = str(raw.get("anonymous_speaker_id") or "")
        truth = truth_by_cluster.get(cluster_id)
        raw_scores = raw.get("candidate_raw_cosine_scores")
        scores = (
            {str(key): float(value) for key, value in raw_scores.items()}
            if isinstance(raw_scores, Mapping)
            else {}
        )
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        top1_id, top1_score = ranked[0] if ranked else ("MISSING", None)
        top2_id, top2_score = ranked[1] if len(ranked) > 1 else (None, None)
        score_vector_complete = (
            bool(cluster_id)
            and truth is not None
            and set(scores) == set(gallery_ids)
            and len(scores) == len(gallery_ids)
        )
        observation_core = {
            "pipeline_id": job.pipeline_id,
            "case_id": case_id,
            "anonymous_speaker_id": cluster_id,
            "source_time_sec": float(raw.get("source_time_sec") or 0.0),
            "predicted_overlap": predicted_overlap,
            "candidate_raw_cosine_scores": dict(sorted(scores.items())),
        }
        observation_id = hashlib.sha256(
            canonical_json_bytes(observation_core)
        ).hexdigest()
        observation = {
            "schema_version": "full-pipeline-challenger-score-observation.v1",
            "pipeline_id": job.pipeline_id,
            "hybrid_label": str(selection.hybrid_label),
            "identity_backend_id": str(selection.identity["backend_id"]),
            "case_id": case_id,
            "source_case_id": source_case_id,
            "source_key": case.get("source_key"),
            "anonymous_speaker_id": cluster_id,
            "observation_id": observation_id,
            "truth_state": str(truth.get("truth_state")) if truth else "UNKNOWN",
            "reference_global_speaker_id": (
                truth.get("global_speaker_id") if truth else None
            ),
            "reference_enrolled_id": (truth.get("enrolled_id") if truth else None),
            "calibration_role": development_role(source_case_id),
            "status": "VALID" if score_vector_complete else "INVALID",
            "source_time_sec": float(raw.get("source_time_sec") or 0.0),
            "evidence_duration_sec": float(raw.get("evidence_duration_sec") or 0.0),
            "embedding_consistency": float(raw.get("embedding_consistency") or 0.0),
            "predicted_overlap": predicted_overlap,
            "top1_candidate_id": top1_id,
            "top1_score": top1_score,
            "top2_candidate_id": top2_id,
            "top2_score": top2_score,
            "candidate_count": len(scores),
            "candidate_raw_cosine_scores": dict(sorted(scores.items())),
            "gallery_requested_size": str(
                case.get("gallery_requested_size") or len(gallery_ids)
            ),
            "gallery_size": len(gallery_ids),
            "gallery_identity_sha256": gallery_identity,
            "gallery_enrolled_ids": list(gallery_ids),
            "selected_profile_identities": list(profile_rows),
            "overlay_condition": str(case.get("overlay_id") or "UNSPECIFIED"),
            "enrollment_policy_id": str(selection.enrollment_policy["policy_id"]),
            "enrollment_policy_sha256": str(selection.enrollment_policy["sha256"]),
            "protocol_id": str(case.get("protocol_id") or ""),
            "development_protocol_sha256": job.protocol_identity,
            "split": "development",
            "evaluation_material_inspected": False,
            "raw_checkpoint_index": index,
        }
        if h2_role is not None:
            observation["h2_calibration_role"] = h2_role
            observation["h2_calibration_assignment_sha256"] = h2_assignment_sha256
        observations.append(observation)
    return observations


def _anonymous_reference_truth(
    case: Mapping[str, object],
    science: Mapping[str, object],
    hypotheses: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    overlay = science.get("overlay")
    if not isinstance(overlay, Mapping):
        return {}
    references = [
        row
        for row in science.get("diarization_segments", [])
        if isinstance(row, Mapping)
    ]
    local_to_global = case.get("local_to_global_speaker")
    mapping = dict(local_to_global) if isinstance(local_to_global, Mapping) else {}
    states = overlay.get("speaker_states")
    state_by_speaker = dict(states) if isinstance(states, Mapping) else {}
    overlaps: dict[str, dict[str, float]] = {}
    for hypothesis in hypotheses:
        cluster_id = str(hypothesis["speaker_id"])
        by_global = overlaps.setdefault(cluster_id, {})
        for reference in references:
            duration = max(
                0.0,
                min(float(reference["end_sec"]), float(hypothesis["end_sec"]))
                - max(float(reference["start_sec"]), float(hypothesis["start_sec"])),
            )
            if duration <= 0.0:
                continue
            local_id = str(reference["speaker_id"])
            global_id = str(mapping.get(local_id) or local_id)
            by_global[global_id] = by_global.get(global_id, 0.0) + duration
    result: dict[str, dict[str, object]] = {}
    for cluster_id, by_global in overlaps.items():
        if not by_global:
            continue
        global_id = max(by_global, key=lambda value: (by_global[value], value))
        raw_state = state_by_speaker.get(global_id)
        state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
        known = str(state.get("identity_state") or "").upper() == "KNOWN"
        result[cluster_id] = {
            "global_speaker_id": global_id,
            "truth_state": "KNOWN" if known else "UNKNOWN",
            "enrolled_id": state.get("enrolled_id") if known else None,
            "overlap_duration_sec": by_global[global_id],
        }
    return result


def _identity_intervals(
    case: Mapping[str, object],
    science: Mapping[str, object],
    hypotheses: Sequence[Mapping[str, object]],
    events: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    overlay = science.get("overlay")
    if not isinstance(overlay, Mapping):
        return []
    references = sorted(
        (
            row
            for row in science.get("diarization_segments", [])
            if isinstance(row, Mapping)
        ),
        key=lambda row: (float(row["start_sec"]), float(row["end_sec"])),
    )
    local_to_global = case.get("local_to_global_speaker")
    mapping = dict(local_to_global) if isinstance(local_to_global, Mapping) else {}
    states = overlay.get("speaker_states")
    state_by_speaker = dict(states) if isinstance(states, Mapping) else {}
    reference_intervals: list[dict[str, object]] = []
    last_end_by_known_identity: dict[str, float] = {}
    temperature_by_known_identity: dict[str, str] = {}
    for index, reference in enumerate(references):
        local_id = str(reference["speaker_id"])
        global_id = str(mapping.get(local_id) or local_id)
        raw_state = state_by_speaker.get(global_id)
        state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
        known = str(state.get("identity_state") or "").upper() == "KNOWN"
        reference_identity = str(
            state.get("enrolled_id")
            if known
            else state.get("unknown_reference_id") or global_id
        )
        temperature = None
        if known:
            start_sec = float(reference["start_sec"])
            prior_end = last_end_by_known_identity.get(reference_identity)
            if prior_end is None:
                temperature_by_known_identity[reference_identity] = "cold"
            elif start_sec > prior_end + 1e-9:
                temperature_by_known_identity[reference_identity] = "warm"
            temperature = temperature_by_known_identity[reference_identity]
            last_end_by_known_identity[reference_identity] = max(
                float(reference["end_sec"]),
                prior_end if prior_end is not None else float("-inf"),
            )
        anonymous = _dominant_hypothesis_for_reference(reference, hypotheses)
        if anonymous is None:
            anonymous = f"uncovered:{global_id}"
        reference_intervals.append(
            {
                "start_sec": float(reference["start_sec"]),
                "end_sec": float(reference["end_sec"]),
                "anonymous_speaker_id": anonymous,
                "reference_speaker_id": reference_identity,
                "reference_is_known": known,
                "episode_id": f"{_case_id(case)}:{index:06d}",
                "temperature": temperature,
            }
        )
    return [
        {
            "start_sec": row.start_sec,
            "end_sec": row.end_sec,
            "reference_speaker_id": row.reference_speaker_id,
            "reference_is_known": row.reference_is_known,
            "predicted_speaker_id": row.predicted_speaker_id,
            "decision_state": row.decision_state,
            "predicted_unknown_label": row.predicted_unknown_label,
            "episode_id": row.episode_id,
            "temperature": row.temperature,
        }
        for row in attribution_intervals_from_prompt1_events(
            events, reference_intervals
        )
    ]


def _dominant_hypothesis_for_reference(
    reference: Mapping[str, object],
    hypotheses: Sequence[Mapping[str, object]],
) -> str | None:
    overlap_by_speaker: dict[str, float] = {}
    for hypothesis in hypotheses:
        duration = max(
            0.0,
            min(float(reference["end_sec"]), float(hypothesis["end_sec"]))
            - max(float(reference["start_sec"]), float(hypothesis["start_sec"])),
        )
        if duration <= 0:
            continue
        speaker_id = str(hypothesis["speaker_id"])
        overlap_by_speaker[speaker_id] = (
            overlap_by_speaker.get(speaker_id, 0.0) + duration
        )
    if not overlap_by_speaker:
        return None
    return max(
        overlap_by_speaker,
        key=lambda speaker_id: (overlap_by_speaker[speaker_id], speaker_id),
    )


def _reference_reentry_episodes(
    references: Sequence[Mapping[str, object]],
    hypotheses: Sequence[Mapping[str, object]],
    *,
    case_id: str,
) -> list[dict[str, object]]:
    """Derive scorer-only re-entry annotations from ordered reference turns.

    Reference speaker identity and turn timing are used only by the scorer.  A
    re-entry is a later non-contiguous reference turn for the same speaker; the
    before/after anonymous IDs are the dominant-overlap runtime hypotheses.
    No reference field is sent back into runtime inference.
    """

    by_speaker: dict[str, list[Mapping[str, object]]] = {}
    for reference in references:
        by_speaker.setdefault(str(reference["speaker_id"]), []).append(reference)
    output: list[dict[str, object]] = []
    for reference_speaker_id in sorted(by_speaker):
        turns = sorted(
            by_speaker[reference_speaker_id],
            key=lambda row: (float(row["start_sec"]), float(row["end_sec"])),
        )
        previous = turns[0] if turns else None
        reentry_index = 0
        for current in turns[1:]:
            if previous is None:
                previous = current
                continue
            if float(current["start_sec"]) > float(previous["end_sec"]) + 1e-9:
                output.append(
                    {
                        "episode_id": (
                            f"{case_id}:{reference_speaker_id}:reentry:"
                            f"{reentry_index:06d}"
                        ),
                        "reference_speaker_id": reference_speaker_id,
                        "before_hypothesis_speaker_id": (
                            _dominant_hypothesis_for_reference(previous, hypotheses)
                        ),
                        "after_hypothesis_speaker_id": (
                            _dominant_hypothesis_for_reference(current, hypotheses)
                        ),
                    }
                )
                reentry_index += 1
            previous = current
    return output


_WORD_ALIGNMENT_POLICY_ID = (
    "global_levenshtein_span_speaker_labels_substitution_deletion_insertion.v1"
)
_IDENTITY_MAPPING_POLICY_ID = (
    "reference_global_ids_with_time_overlap_anonymous_mapping.v1"
)


def _normalized_scoring_words(value: object) -> tuple[str, ...]:
    """Apply the exact frozen cpWER/WER text normalizer and return words."""

    return tuple(re.sub(r"\s+", " ", str(value or "").strip().lower()).split())


def _canonical_reference_speaker_id(
    segment: Mapping[str, object], local_to_global: Mapping[str, str]
) -> str | None:
    raw = (
        segment.get("global_speaker_id")
        or segment.get("speaker_id")
        or segment.get("speaker")
        or segment.get("reference_speaker")
        or segment.get("speaker_label")
    )
    if raw is None:
        return None
    speaker_id = str(raw)
    return str(local_to_global.get(speaker_id) or speaker_id)


def _visible_speaker_label(
    span: Mapping[str, object],
) -> tuple[str | None, str | None]:
    value = span.get("speaker_label")
    if isinstance(value, Mapping):
        kind = str(value.get("label_kind") or "") or None
        label = (
            value.get("enrolled_speaker_id")
            if kind == "known"
            else value.get("display_label")
        )
        return (str(label) if label else None), kind
    if value is None or not str(value).strip():
        return None, None
    return str(value).strip(), None


def _enrolled_global_speaker_map(
    overlay: Mapping[str, object] | None,
) -> dict[str, str]:
    result: dict[str, str] = {}
    if overlay is None:
        return result
    states = overlay.get("speaker_states")
    if isinstance(states, Mapping):
        for global_id, raw_state in states.items():
            if not isinstance(raw_state, Mapping):
                continue
            enrolled_id = raw_state.get("enrolled_id")
            if enrolled_id:
                result[str(enrolled_id)] = str(global_id)
    database = overlay.get("enrollment_database")
    if isinstance(database, Sequence) and not isinstance(database, (str, bytes)):
        for row in database:
            if not isinstance(row, Mapping):
                continue
            enrolled_id = row.get("enrolled_id")
            global_id = row.get("global_speaker_id")
            if enrolled_id and global_id:
                result[str(enrolled_id)] = str(global_id)
    return result


def _canonical_hypothesis_speaker_id(
    span: Mapping[str, object],
    *,
    anonymous_to_reference: Mapping[str, str],
    enrolled_to_global: Mapping[str, str],
    reference_speaker_ids: frozenset[str],
) -> str | None:
    visible, label_kind = _visible_speaker_label(span)
    if visible is None:
        return None
    if visible in reference_speaker_ids:
        return visible
    if visible in enrolled_to_global:
        return enrolled_to_global[visible]
    normalized = visible.casefold().replace(" ", "_")
    if normalized in {"unknown", "generic_unknown", "uncovered"}:
        return "unknown"
    anonymous = _anonymous_speaker_id(span)
    if (
        anonymous
        and anonymous in anonymous_to_reference
        and (
            label_kind == "unknown"
            or normalized.startswith("speaker_")
            or normalized.startswith("unknown_")
        )
    ):
        return anonymous_to_reference[anonymous]
    # Preserve an unmatched visible label as a distinct, specific output.  It
    # will score as wrong rather than being dropped or oracle-remapped.
    return f"output_label::{visible}"


def _align_speaker_word_records(
    reference: Sequence[tuple[str, str]],
    hypothesis: Sequence[tuple[str, str | None]],
) -> list[dict[str, object]]:
    """Frozen global Levenshtein alignment with stable operation tie breaks.

    Lexical equality is normalized before this function.  Exact match and
    substitution use the diagonal, followed by deletion, then insertion on
    equal edit cost.  Speaker labels never influence the lexical path.
    """

    rows = len(reference)
    columns = len(hypothesis)
    costs = [[0] * (columns + 1) for _ in range(rows + 1)]
    operations = [[""] * (columns + 1) for _ in range(rows + 1)]
    for row in range(1, rows + 1):
        costs[row][0] = row
        operations[row][0] = "delete"
    for column in range(1, columns + 1):
        costs[0][column] = column
        operations[0][column] = "insert"
    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            equal = reference[row - 1][0] == hypothesis[column - 1][0]
            candidates = (
                (
                    costs[row - 1][column - 1] + (0 if equal else 1),
                    0,
                    "match" if equal else "substitute",
                ),
                (costs[row - 1][column] + 1, 1, "delete"),
                (costs[row][column - 1] + 1, 2, "insert"),
            )
            cost, _priority, operation = min(candidates)
            costs[row][column] = cost
            operations[row][column] = operation
    aligned: list[dict[str, object]] = []
    row = rows
    column = columns
    while row or column:
        operation = operations[row][column]
        if operation in {"match", "substitute"}:
            ref_word, ref_speaker = reference[row - 1]
            hyp_word, hyp_speaker = hypothesis[column - 1]
            aligned.append(
                {
                    "reference_word": ref_word,
                    "hypothesis_word": hyp_word,
                    "reference_speaker_id": ref_speaker,
                    "hypothesis_speaker_id": hyp_speaker,
                    "reference_duration_sec": None,
                }
            )
            row -= 1
            column -= 1
        elif operation == "delete":
            ref_word, ref_speaker = reference[row - 1]
            aligned.append(
                {
                    "reference_word": ref_word,
                    "hypothesis_word": None,
                    "reference_speaker_id": ref_speaker,
                    "hypothesis_speaker_id": None,
                    "reference_duration_sec": None,
                }
            )
            row -= 1
        elif operation == "insert":
            hyp_word, hyp_speaker = hypothesis[column - 1]
            aligned.append(
                {
                    "reference_word": None,
                    "hypothesis_word": hyp_word,
                    "reference_speaker_id": None,
                    "hypothesis_speaker_id": hyp_speaker,
                    "reference_duration_sec": None,
                }
            )
            column -= 1
        else:  # pragma: no cover - defensive corruption guard
            raise RuntimeError("word-alignment backtrace is incomplete")
    aligned.reverse()
    return aligned


def _cross_speaker_reference_overlap(
    segments: Sequence[Mapping[str, object]],
    local_to_global: Mapping[str, str],
) -> bool:
    timed = [
        (
            float(row["start_sec"]),
            float(row["end_sec"]),
            _canonical_reference_speaker_id(row, local_to_global),
        )
        for row in segments
        if row.get("start_sec") is not None and row.get("end_sec") is not None
    ]
    for index, left in enumerate(timed):
        for right in timed[index + 1 :]:
            if left[2] == right[2]:
                continue
            if max(left[0], right[0]) < min(left[1], right[1]):
                return True
    return False


def _speaker_transcription_scoring_inputs(
    case: Mapping[str, object],
    hypothesis_to_reference: Mapping[str, str],
) -> dict[str, object]:
    reference_segments = [
        dict(row)
        for row in case.get("reference_transcript_segments", [])
        if isinstance(row, Mapping)
    ]
    hypothesis_spans = [
        dict(row)
        for row in case.get("hypothesis_transcript_spans", [])
        if isinstance(row, Mapping)
    ]
    local_raw = case.get("local_to_global_speaker")
    local_to_global = (
        {str(key): str(value) for key, value in local_raw.items()}
        if isinstance(local_raw, Mapping)
        else {}
    )
    anonymous_to_reference = {
        str(anonymous): str(local_to_global.get(str(reference)) or reference)
        for anonymous, reference in hypothesis_to_reference.items()
    }
    overlay_raw = case.get("identity_overlay")
    overlay = dict(overlay_raw) if isinstance(overlay_raw, Mapping) else None
    enrolled_to_global = _enrolled_global_speaker_map(overlay)

    ordered_references = sorted(
        reference_segments,
        key=lambda row: (
            float(row.get("start_sec") or 0.0),
            float(row.get("end_sec") or 0.0),
            str(row.get("reference_segment_id") or ""),
        ),
    )
    reference_stream_parts: dict[str, list[str]] = {}
    reference_words: list[tuple[str, str]] = []
    for segment in ordered_references:
        speaker_id = _canonical_reference_speaker_id(segment, local_to_global)
        text = segment.get("scorable_transcript") or segment.get("text")
        if speaker_id is None or text is None:
            continue
        reference_stream_parts.setdefault(speaker_id, []).append(str(text))
        reference_words.extend(
            (word, speaker_id) for word in _normalized_scoring_words(text)
        )
    reference_speaker_ids = frozenset(reference_stream_parts)

    hypothesis_stream_parts: dict[str, list[str]] = {}
    hypothesis_words: list[tuple[str, str | None]] = []
    ordered_hypotheses = sorted(
        hypothesis_spans,
        key=lambda row: (
            float(row.get("start_sec") or 0.0),
            float(row.get("end_sec") or 0.0),
            str(row.get("span_id") or ""),
        ),
    )
    for index, span in enumerate(ordered_hypotheses):
        text = str(span.get("text") or "")
        speaker_id = _canonical_hypothesis_speaker_id(
            span,
            anonymous_to_reference=anonymous_to_reference,
            enrolled_to_global=enrolled_to_global,
            reference_speaker_ids=reference_speaker_ids,
        )
        stream_id = speaker_id or (
            "__UNASSIGNED_VISIBLE_SPAN__::" f"{span.get('span_id') or index}"
        )
        hypothesis_stream_parts.setdefault(stream_id, []).append(text)
        hypothesis_words.extend(
            (word, speaker_id) for word in _normalized_scoring_words(text)
        )

    word_alignments = None
    if reference_words and not _cross_speaker_reference_overlap(
        ordered_references, local_to_global
    ):
        word_alignments = _align_speaker_word_records(reference_words, hypothesis_words)
    return {
        "identity_reference_speaker_texts": {
            key: " ".join(values).strip()
            for key, values in reference_stream_parts.items()
        },
        "identity_hypothesis_speaker_texts": {
            key: " ".join(values).strip()
            for key, values in hypothesis_stream_parts.items()
        },
        "identities_comparable": bool(reference_stream_parts),
        "identity_mapping_id": _IDENTITY_MAPPING_POLICY_ID,
        "word_alignments": word_alignments,
        "word_alignment_id": (
            _WORD_ALIGNMENT_POLICY_ID if word_alignments is not None else None
        ),
    }


def _score_isolated_case_views(
    cases: Sequence[Mapping[str, object]], *, all_cases_complete: bool
) -> dict[str, MetricReport]:
    grouped: dict[str, list[MetricReport]] = {
        "streaming": [],
        "diarization": [],
        "identity": [],
        "speaker_transcription": [],
        "ux": [],
    }
    for case in cases:
        events = list(case.get("events", []))
        references = list(case.get("reference_segments", []))
        hypotheses = list(case.get("hypothesis_segments", []))
        grouped["streaming"].append(
            score_streaming(
                events,
                reference_text_by_hypothesis=(
                    dict(case["streaming_references"])
                    if case.get("streaming_references")
                    else None
                ),
            )
        )
        diarization_report = score_anonymous_diarization(
            references if references else None,
            hypotheses if references else None,
            uem=case.get("uem"),
            collar_sec=0.0,
            score_overlap=True,
            score_standard_short_turn_bins=True,
            short_turn_max_duration_sec=(
                float(case["short_turn_max_duration_sec"])
                if case.get("short_turn_max_duration_sec") is not None
                else None
            ),
            reentry_episodes=(
                list(case["reentry_episodes"])
                if case.get("reentry_episodes") is not None
                else None
            ),
        )
        grouped["diarization"].append(diarization_report)
        intervals = list(case.get("attribution_intervals", []))
        grouped["identity"].append(
            score_known_unknown_attribution(
                intervals if intervals else None,
                identity_events=events,
            )
        )
        speaker_supported = bool(case.get("speaker_transcript_supported"))
        diarization_mapping = diarization_report["der"].details.get(
            "speaker_mapping", {}
        )
        transcription_inputs = (
            _speaker_transcription_scoring_inputs(
                case,
                diarization_mapping if isinstance(diarization_mapping, Mapping) else {},
            )
            if speaker_supported
            else {}
        )
        grouped["speaker_transcription"].append(
            score_speaker_attributed_transcription(
                (
                    dict(case.get("reference_speaker_texts", {}))
                    if speaker_supported
                    else None
                ),
                (
                    dict(case.get("hypothesis_speaker_texts", {}))
                    if speaker_supported
                    else None
                ),
                prerequisites=(
                    {
                        "reference_streams_complete": True,
                        "hypothesis_streams_complete": all_cases_complete,
                        "normalization_id": "lowercase_whitespace.v1",
                        "permutation_scope": "per_recording",
                        "identities_comparable": bool(
                            transcription_inputs.get("identities_comparable")
                        ),
                        "identity_mapping_id": transcription_inputs.get(
                            "identity_mapping_id"
                        ),
                        "word_alignment_id": transcription_inputs.get(
                            "word_alignment_id"
                        ),
                    }
                    if speaker_supported
                    else None
                ),
                identity_reference_speaker_texts=(
                    transcription_inputs.get("identity_reference_speaker_texts")
                    if speaker_supported
                    else None
                ),
                identity_hypothesis_speaker_texts=(
                    transcription_inputs.get("identity_hypothesis_speaker_texts")
                    if speaker_supported
                    else None
                ),
                word_alignments=(
                    transcription_inputs.get("word_alignments")
                    if speaker_supported
                    else None
                ),
                revision_events=events if speaker_supported else None,
            )
        )
        grouped["ux"].append(
            score_ux(
                events,
                attribution_intervals=intervals if intervals else None,
            )
        )
    return {
        category: _aggregate_recording_reports(category, reports)
        for category, reports in grouped.items()
    }


_ADDITIVE_RECORDING_METRIC_IDS = frozenset(
    {
        "correctly_named_known_time_sec",
        "wrong_known_time_sec",
        "stranger_false_known_time_sec",
        "generic_known_time_sec",
        "uncovered_known_time_sec",
        "identity_split_count",
        "identity_merge_count",
        "identity_revision_count",
        "wrong_speaker_word_count",
        "wrong_speaker_word_time_sec",
        "retroactive_correction_count",
        "wrong_name_dwell_sec",
        "transcript_revision_count",
        "ux_identity_revision_count",
        "dropped_audio_sec",
        "stall_time_sec",
    }
)


def _aggregate_recording_reports(
    category: str, reports: Sequence[MetricReport]
) -> MetricReport:
    if not reports:
        return build_metric_report(
            category, (), missing_reason="no completed recording supplied this view"
        )
    values = []
    metric_ids = tuple(reports[0].metrics)
    for metric_id in metric_ids:
        all_rows = [report.metrics[metric_id] for report in reports]
        unsupported = [row for row in all_rows if row.status == "unsupported"]
        rows = [row for row in all_rows if row.status != "unsupported"]
        details = {
            "aggregation": "per_recording_sufficient_statistics.v1",
            "recording_count": len(all_rows),
            "applicable_recording_count": len(rows),
            "unsupported_recording_count": len(unsupported),
            "per_recording_status": [row.status for row in all_rows],
            "unsupported_reasons": sorted(
                {str(row.reason) for row in unsupported if row.reason}
            ),
        }
        for provenance_key in (
            "identity_mapping",
            "word_alignment_id",
            "scope",
        ):
            provenance_values = {
                str(row.details[provenance_key])
                for row in rows
                if row.details.get(provenance_key) is not None
            }
            if len(provenance_values) == 1:
                details[provenance_key] = next(iter(provenance_values))
            elif provenance_values:
                details[f"{provenance_key}_variants"] = sorted(provenance_values)
        unlabelled_unknown = [
            float(row.details["unlabelled_unknown_duration_sec"])
            for row in rows
            if row.details.get("unlabelled_unknown_duration_sec") is not None
        ]
        if unlabelled_unknown:
            details["unlabelled_unknown_duration_sec"] = sum(unlabelled_unknown)
        if not rows:
            values.append(
                unsupported_metric(
                    metric_id,
                    "metric prerequisites were unavailable for every recording",
                )
            )
            continue
        sufficient_rows = [
            row
            for row in rows
            if row.numerator is not None and row.denominator is not None
        ]
        computed_rows = [row for row in rows if row.status == "computed"]
        if sufficient_rows and len(sufficient_rows) == len(rows):
            numerator = sum(float(row.numerator or 0.0) for row in sufficient_rows)
            denominator = sum(float(row.denominator or 0.0) for row in sufficient_rows)
            if denominator > 0:
                values.append(
                    computed_metric(
                        metric_id,
                        numerator / denominator,
                        numerator=numerator,
                        denominator=denominator,
                        details=details,
                    )
                )
            else:
                values.append(
                    undefined_metric(
                        metric_id,
                        "aggregate recording denominator is zero",
                        numerator=numerator,
                        denominator=denominator,
                    )
                )
            continue
        if computed_rows:
            scalar_values = [float(row.value or 0.0) for row in computed_rows]
            details["computed_recording_count"] = len(computed_rows)
            details["undefined_recording_count"] = len(rows) - len(computed_rows)
            if metric_id in _ADDITIVE_RECORDING_METRIC_IDS:
                aggregate_value = sum(scalar_values)
                details["scalar_aggregation"] = "sum"
                numerator = None
                denominator = None
            else:
                aggregate_value = sum(scalar_values) / len(scalar_values)
                details["scalar_aggregation"] = "per_recording_mean"
                numerator = sum(scalar_values)
                denominator = float(len(scalar_values))
            values.append(
                computed_metric(
                    metric_id,
                    aggregate_value,
                    numerator=numerator,
                    denominator=denominator,
                    details=details,
                )
            )
            continue
        values.append(
            undefined_metric(
                metric_id,
                "metric is undefined for every recording",
            )
        )
    return build_metric_report(
        category,
        values,
        warnings=tuple(
            sorted({warning for report in reports for warning in report.warnings})
        ),
    )


class _FrozenGalleryPreparer:
    """Build exact gallery-only protected stores from frozen reserved clips."""

    def __init__(
        self,
        *,
        selection: object,
        attempt_root: Path,
        worker_pool: object | None = None,
        lazy_worker_start: bool = False,
        worker_warmup_audio_path: Path | None = None,
    ) -> None:
        self.selection = selection
        self.attempt_root = Path(attempt_root).resolve()
        self.worker_pool = worker_pool
        self.lazy_worker_start = bool(lazy_worker_start)
        self.worker_warmup_audio_path = (
            Path(worker_warmup_audio_path).resolve()
            if worker_warmup_audio_path is not None
            else None
        )
        self._adapter: object | None = None
        self._prepared: dict[str, PreparedGallery] = {}

    def prepare(
        self, case: Mapping[str, object], context: ProtocolContext
    ) -> PreparedGallery:
        gallery_ids = tuple(
            sorted(str(value) for value in case.get("gallery_enrolled_ids", []))
        )
        backend_id = str(self.selection.identity["backend_id"])
        identity = {
            "backend_id": backend_id,
            "backend_config_sha256": str(self.selection.identity["config_sha256"]),
            "model_id": str(self.selection.identity["model_id"]),
            "model_sha256": str(self.selection.identity["model_identity_sha256"]),
            "policy": dict(self.selection.enrollment_policy),
            "gallery": [context.enrollments[value] for value in gallery_ids],
        }
        gallery_sha = hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
        existing = self._prepared.get(gallery_sha)
        if existing is not None:
            return existing
        root = self.attempt_root / "enrollment_galleries" / gallery_sha
        root.mkdir(parents=True, exist_ok=True)
        if not gallery_ids:
            prepared = PreparedGallery(root=root)
            self._prepared[gallery_sha] = prepared
            return prepared

        from app.full_pipeline.enrollment import (
            EnrollmentTemplate,
            ProtectedEnrollmentStore,
        )

        adapter: object | None = None
        store = ProtectedEnrollmentStore(root)
        profile_rows: list[Mapping[str, object]] = []
        utterance_count = int(self.selection.enrollment_policy["utterance_count"])
        expected_profile_ids = {
            (
                f"eval_{_portable_id(backend_id)}_{_portable_id(enrolled_id)}_"
                f"{gallery_sha[:12]}"
            )
            for enrolled_id in gallery_ids
        }
        observed_profile_ids = {
            profile.profile_id for profile in store.list_profiles(backend_id=backend_id)
        }
        unexpected_profiles = observed_profile_ids - expected_profile_ids
        if unexpected_profiles:
            raise ValueError(
                "frozen enrollment gallery contains unexpected profiles: "
                + ", ".join(sorted(unexpected_profiles))
            )
        for enrolled_id in gallery_ids:
            enrollment = context.enrollments[enrolled_id]
            clips = [
                dict(value)
                for value in enrollment.get("reserved_enrollment_clips", [])
                if isinstance(value, Mapping)
            ]
            if len(clips) < utterance_count:
                raise ValueError(
                    f"frozen enrollment {enrolled_id} has fewer than "
                    f"{utterance_count} reserved clips"
                )
            selected = clips[:utterance_count]
            profile_id = (
                f"eval_{_portable_id(backend_id)}_{_portable_id(enrolled_id)}_"
                f"{gallery_sha[:12]}"
            )
            profile_path = store.profile_root / f"{profile_id}.json"
            if profile_path.is_file():
                profile = store.get_profile(profile_id)
                self._validate_existing_profile(
                    profile,
                    enrolled_id=enrolled_id,
                    selected=selected,
                )
            else:
                if adapter is None:
                    adapter = self._embedding_adapter()
                templates = []
                for clip in selected:
                    path = _resolve_reference_path(
                        str(clip["logical_audio_path"]),
                        expected_sha256=clip["source_audio_sha256"],
                    )
                    samples = _load_enrollment_audio(path)
                    duration = len(samples) / 16000.0
                    result = adapter.embed(
                        _enrollment_window(
                            sample_id=str(clip["source_clip_id"]),
                            samples=samples,
                            duration_sec=duration,
                        )
                    )
                    templates.append(
                        EnrollmentTemplate(
                            sample_id=str(clip["source_clip_id"]),
                            vector=result.vector,
                            duration_sec=duration,
                            audio_sha256=str(clip["source_audio_sha256"]).lower(),
                            quality={
                                "status": "accepted",
                                "frozen_reserved_clip": True,
                            },
                        )
                    )
                profile = store.create_profile(
                    profile_id=profile_id,
                    speaker_id=enrolled_id,
                    display_label=enrolled_id,
                    backend_id=backend_id,
                    backend_config_sha256=str(self.selection.identity["config_sha256"]),
                    model_id=str(self.selection.identity["model_id"]),
                    model_sha256=str(self.selection.identity["model_identity_sha256"]),
                    aggregation_method=str(
                        self.selection.enrollment_policy["aggregation"]
                    ),
                    templates=templates,
                    # The frozen hybrid study enrolled the first three complete
                    # reserved clips without a new profile-level rejection gate.
                    # The 0.35 consistency gate belongs to live probe evidence.
                    minimum_consistency=-1.0,
                )
            if profile.state != "active":
                raise ValueError(
                    f"frozen enrollment profile failed quality gate: {enrolled_id}"
                )
            profile_rows.append(
                {
                    "schema_version": "full-pipeline-evaluation-selected-profile.v1",
                    "gallery_sha256": gallery_sha,
                    "gallery_size": len(gallery_ids),
                    "enrolled_id": enrolled_id,
                    "global_speaker_id": enrollment.get("global_speaker_id"),
                    "profile_id": profile.profile_id,
                    "profile_sha256": profile.profile_sha256,
                    "template_sha256": profile.template_sha256,
                    "backend_id": profile.backend_id,
                    "backend_config_sha256": profile.backend_config_sha256,
                    "model_id": profile.model_id,
                    "model_sha256": profile.model_sha256,
                    "aggregation_method": profile.aggregation_method,
                    "within_enrollment_consistency": (
                        profile.within_enrollment_consistency
                    ),
                    "profile_activation_policy": (
                        "frozen_first_three_reserved_clips_no_new_rejection.v1"
                    ),
                    "source_clips": [
                        {
                            "source_clip_id": clip["source_clip_id"],
                            "source_audio_sha256": clip["source_audio_sha256"],
                        }
                        for clip in selected
                    ],
                    "biometric_vectors_in_result": False,
                }
            )
        prepared = PreparedGallery(root=root, profiles=tuple(profile_rows))
        self._prepared[gallery_sha] = prepared
        return prepared

    def _validate_existing_profile(
        self,
        profile: object,
        *,
        enrolled_id: str,
        selected: Sequence[Mapping[str, object]],
    ) -> None:
        """Fail closed or reuse one exact immutable generated gallery profile."""

        exact = {
            "state": "active",
            "speaker_id": enrolled_id,
            "display_label": enrolled_id,
            "backend_id": str(self.selection.identity["backend_id"]),
            "backend_config_sha256": str(self.selection.identity["config_sha256"]),
            "model_id": str(self.selection.identity["model_id"]),
            "model_sha256": str(self.selection.identity["model_identity_sha256"]),
            "aggregation_method": str(self.selection.enrollment_policy["aggregation"]),
        }
        if any(getattr(profile, key, None) != value for key, value in exact.items()):
            raise ValueError(
                f"frozen enrollment profile identity differs: {enrolled_id}"
            )
        expected_templates = [
            (
                str(clip["source_clip_id"]),
                str(clip["source_audio_sha256"]).lower(),
            )
            for clip in selected
        ]
        actual_templates = [
            (str(row.sample_id), str(row.audio_sha256).lower())
            for row in getattr(profile, "templates", ())
        ]
        if actual_templates != expected_templates:
            raise ValueError(
                f"frozen enrollment profile source clips differ: {enrolled_id}"
            )

    def _embedding_adapter(self) -> object:
        if self._adapter is not None:
            return self._adapter
        from app.full_pipeline.cache import ContentAddressedCache
        from app.full_pipeline.runtime_components import WorkerEmbeddingAdapter
        from app.full_pipeline.workers import PersistentWorker, embedding_worker_spec

        backend_id = str(self.selection.identity["backend_id"])
        warmup_request = None
        if self.worker_warmup_audio_path is not None:
            warmup_sha256 = hashlib.sha256(
                self.worker_warmup_audio_path.read_bytes()
            ).hexdigest()
            warmup_request = _embedding_warmup_request(
                self.worker_warmup_audio_path,
                warmup_sha256,
                "full-pipeline-evaluation-enrollment",
            )
        spec = embedding_worker_spec(
            backend_id,
            worker_id=f"evaluation-enrollment-{backend_id}-{id(self):x}",
            pool_partition_id="speaker_embedding:identity",
            warmup_request=warmup_request,
        )
        worker = (
            PersistentWorker(spec)
            if self.worker_pool is None
            else self.worker_pool.acquire(spec)  # type: ignore[attr-defined]
        )
        adapter = WorkerEmbeddingAdapter(
            worker=worker,
            work_root=self.attempt_root / "enrollment_embedding_work",
            backend_config_sha256=str(self.selection.identity["config_sha256"]),
            model_id=str(self.selection.identity["model_id"]),
            model_sha256=str(self.selection.identity["model_identity_sha256"]),
            cache=ContentAddressedCache(DEFAULT_CACHE_ROOT),
            lazy_worker_start=self.lazy_worker_start,
        )
        adapter.start("full-pipeline-evaluation-enrollment")
        self._adapter = adapter
        return adapter

    def close(self) -> None:
        if self._adapter is not None:
            self._adapter.close()
            self._adapter = None


def _load_enrollment_audio(path: Path) -> object:
    import numpy as np
    import soundfile as sf

    from app.inference_pipeline.audio_io.resample import resample_audio

    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(audio, axis=1, keepdims=True, dtype=np.float32)
    return resample_audio(mono, int(rate), 16000)[:, 0]


def _enrollment_window(
    *, sample_id: str, samples: object, duration_sec: float
) -> object:
    from app.full_pipeline.models import EmbeddingWindow

    return EmbeddingWindow(
        window_id=sample_id,
        start_sec=0.0,
        end_sec=duration_sec,
        assignment_start_sec=0.0,
        assignment_end_sec=duration_sec,
        samples=samples,
        role="enrollment_embedding",
    )


def _model_assets(identities: Mapping[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for role, raw in sorted(identities.items()):
        identity = raw.to_contract()  # type: ignore[attr-defined]
        for index, value in enumerate(identity.get("model_asset_sha256s") or []):
            key = (role, str(value))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "role": role,
                    "asset_id": f"{identity['backend_id']}_{index + 1}",
                    "sha256": str(value),
                }
            )
    if not rows:
        raise RuntimeError("locked pipeline has no checksum-bound model assets")
    return rows


def _audio_path(case: Mapping[str, object]) -> Path:
    for key in (
        "mixture_audio_path",
        "audio_path",
        "generated_audio_path",
        "audio_path_project_relative",
        "logical_audio_path",
        "audio_logical_path",
    ):
        raw = case.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = Path(raw)
        candidates = list(
            installed_tool_path_candidates(path, evaluation_root=EVALUATION_ROOT)
        )
        candidates.extend(
            [resolve_data_path_from_logical(path), EVALUATION_ROOT.parents[1] / path]
        )
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file():
                return resolved
    raise FileNotFoundError(f"case {_case_id(case)} has no installed audio path")


def _verify_case_audio(path: Path, case: Mapping[str, object]) -> None:
    expected = case.get("audio_sha256") or case.get("mixture_audio_sha256")
    if (
        expected is not None
        and str(expected).casefold() != sha256_file(path).casefold()
    ):
        raise ValueError(f"audio checksum mismatch for {_case_id(case)}")


def _final_transcript(root: Path) -> list[dict[str, object]]:
    value = _read_optional_json(root / "transcript/final_transcript.json")
    spans = value.get("spans")
    return (
        [dict(row) for row in spans if isinstance(row, Mapping)]
        if isinstance(spans, list)
        else []
    )


def _hypothesis_segments(root: Path, case_id: str) -> list[dict[str, object]]:
    rows = _jsonl(root / "speakers/anonymous.jsonl")
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        revision = row.get("revision")
        revision_id = (
            str(revision.get("revision_id"))
            if isinstance(revision, Mapping)
            else str(row.get("event_id"))
        )
        latest[revision_id.split(":revision:")[0]] = row
    return [
        {
            "case_id": case_id,
            "start_sec": float(row["start_sec"]),
            "end_sec": float(row["end_sec"]),
            "speaker_id": str(row["anonymous_speaker_id"]),
        }
        for row in latest.values()
        if row.get("start_sec") is not None and row.get("end_sec") is not None
    ]


def _reference_segments(
    case: Mapping[str, object], reference: Mapping[str, object] | None = None
) -> list[dict[str, object]]:
    raw = (
        case.get("reference_segments")
        or case.get("diarization_reference")
        or case.get("speaker_segments")
        or (reference or {}).get("segments")
        or []
    )
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    sample_rate = float(case.get("sample_rate_hz") or 16000)
    rows: list[dict[str, object]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            continue
        start = value.get("start_sec")
        end = value.get("end_sec")
        if start is None and value.get("sample_start") is not None:
            start = float(value["sample_start"]) / sample_rate
        if end is None and value.get("sample_end") is not None:
            end = float(value["sample_end"]) / sample_rate
        speaker = (
            value.get("speaker_id")
            or value.get("speaker")
            or value.get("reference_speaker")
            or value.get("speaker_label")
            or value.get("global_speaker_id")
        )
        if start is not None and end is not None and speaker is not None:
            rows.append(
                {
                    "start_sec": float(start),
                    "end_sec": float(end),
                    "speaker_id": str(speaker),
                }
            )
    return rows


def _attribution_intervals(case: Mapping[str, object]) -> list[dict[str, object]]:
    raw = case.get("attribution_reference_intervals") or case.get("identity_intervals")
    return (
        [dict(row) for row in raw if isinstance(row, Mapping)]
        if isinstance(raw, list)
        else []
    )


def _speaker_texts(
    case: Mapping[str, object], reference: Mapping[str, object] | None = None
) -> dict[str, str]:
    raw = case.get("speaker_attributed_transcript") or case.get(
        "reference_speaker_texts"
    )
    if isinstance(raw, Mapping):
        return {str(key): str(value) for key, value in raw.items()}
    streams: dict[str, list[str]] = {}
    for value in (reference or {}).get("segments", []):
        if not isinstance(value, Mapping):
            continue
        text = value.get("scorable_transcript") or value.get("text")
        speaker = (
            value.get("global_speaker_id")
            or value.get("speaker_label")
            or value.get("reference_speaker")
            or value.get("speaker_id")
        )
        if text is not None and speaker is not None:
            streams.setdefault(str(speaker), []).append(str(text))
    return {key: " ".join(values).strip() for key, values in streams.items()}


def _word_alignments(case: Mapping[str, object]) -> list[dict[str, object]]:
    raw = case.get("word_alignments")
    return (
        [dict(row) for row in raw if isinstance(row, Mapping)]
        if isinstance(raw, list)
        else []
    )


def _reference_text(
    case: Mapping[str, object], reference: Mapping[str, object] | None = None
) -> str:
    for key in (
        "exact_source_transcript",
        "reference_transcript",
        "transcript",
        "reference_text",
        "text",
    ):
        value = case.get(key)
        if isinstance(value, str):
            return value
    segments = [
        value
        for value in (reference or {}).get("segments", [])
        if isinstance(value, Mapping)
    ]
    if segments:
        return " ".join(
            str(value.get("scorable_transcript") or value.get("text") or "")
            for value in sorted(
                segments,
                key=lambda row: (
                    float(row.get("start_sec") or 0.0),
                    float(row.get("end_sec") or 0.0),
                ),
            )
        ).strip()
    speaker = _speaker_texts(case, reference)
    return " ".join(value for _, value in sorted(speaker.items())).strip()


def _enrich_event(row: Mapping[str, object], case_id: str) -> dict[str, object]:
    value = {"evaluation_case_id": case_id, **dict(row)}
    if value.get("event_type") in {"asr_partial", "asr_final"}:
        prior = str(
            value.get("hypothesis_id") or value.get("line_id") or value.get("event_id")
        )
        value["hypothesis_id"] = f"{case_id}:{prior}"
    return value


def _rttm(rows: Iterable[Mapping[str, object]]) -> str:
    lines = []
    for row in rows:
        start = float(row["start_sec"])
        duration = float(row["end_sec"]) - start
        if duration <= 0:
            continue
        recording = _portable_id(str(row.get("case_id") or "recording"))
        speaker = _portable_id(str(row["speaker_id"]))
        lines.append(
            f"SPEAKER {recording} 1 {start:.6f} {duration:.6f} "
            f"<NA> <NA> {speaker} <NA> <NA>"
        )
    return "\n".join(lines) + ("\n" if lines else "")


def _portable_reference(case: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in case.items():
        if key.endswith("_physical_path"):
            continue
        if (
            key.endswith("_path")
            and isinstance(value, str)
            and Path(value).is_absolute()
        ):
            result[key] = {"absolute_path_redacted": True}
        else:
            result[str(key)] = value
    return result


def _model_bytes(selection: object) -> int | None:
    total = 0
    observed = False
    for axis in (selection.asr, selection.identity):  # type: ignore[attr-defined]
        for key in ("installed_bytes", "model_asset_bytes"):
            value = axis.get(key)
            if isinstance(value, (int, float)):
                total += int(value)
                observed = True
        asset = axis.get("model_asset")
        if isinstance(asset, Mapping) and isinstance(asset.get("installed_bytes"), int):
            total += int(asset["installed_bytes"])
            observed = True
    return total if observed else None


def _directory_bytes(path: Path) -> int | None:
    try:
        return sum(
            value.stat().st_size for value in Path(path).rglob("*") if value.is_file()
        )
    except OSError:
        return None


def _maximum_queue_depth(
    events: Sequence[Mapping[str, object]], runtime_metrics: Mapping[str, object]
) -> int | None:
    values: list[int] = []
    for row in events:
        for container in (row, row.get("payload")):
            if not isinstance(container, Mapping):
                continue
            value = container.get("queue_depth")
            if isinstance(value, (int, float)):
                values.append(int(value))
            backpressure = container.get("queue_backpressure")
            if isinstance(backpressure, Mapping):
                for key in ("maximum_depth", "maximum_observed_depth"):
                    value = backpressure.get(key)
                    if isinstance(value, (int, float)):
                        values.append(int(value))
    for key in ("maximum_queue_depth", "max_queue_depth"):
        value = runtime_metrics.get(key)
        if isinstance(value, (int, float)):
            values.append(int(value))
    queue_metrics = runtime_metrics.get("queue")
    if isinstance(queue_metrics, Mapping):
        for key in ("maximum_observed_depth", "maximum_depth"):
            value = queue_metrics.get(key)
            if isinstance(value, (int, float)):
                values.append(int(value))
    return max(values) if values else None


def _queue_backpressure_evidence(
    events: Sequence[Mapping[str, object]], runtime_metrics: Mapping[str, object]
) -> dict[str, object] | None:
    """Preserve final bounded-queue evidence instead of only its high-water mark."""

    evidence: dict[str, object] = {}
    queue_metrics = runtime_metrics.get("queue")
    if isinstance(queue_metrics, Mapping):
        for key in (
            "policy",
            "maximum_frames",
            "maximum_observed_depth",
            "dropped_frames",
            "blocked_total_sec",
            "blocked_max_sec",
        ):
            value = queue_metrics.get(key)
            if isinstance(value, (str, int, float, bool)):
                evidence[key] = value
    maximum_depth = _maximum_queue_depth(events, runtime_metrics)
    if maximum_depth is not None:
        evidence["maximum_observed_depth"] = maximum_depth
    return evidence or None


def _last_number(rows: Sequence[Mapping[str, object]], key: str) -> float | None:
    for row in reversed(rows):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _case_id(case: Mapping[str, object]) -> str:
    value = (
        case.get("case_id")
        or case.get("protocol_case_id")
        or case.get("recording_id")
        or case.get("utt_id")
    )
    if value is None:
        raise ValueError("evaluation case lacks case_id")
    return str(value)


def _duration(case: Mapping[str, object]) -> float:
    return float(case.get("duration_sec") or case.get("audio_duration_sec") or 0.0)


def _portable_id(value: str) -> str:
    normalized = "".join(
        char if char.isalnum() or char in "_.-" else "_" for char in value
    )
    return normalized[:120] or "unnamed"


def _optional_path(value: object) -> Path | None:
    return Path(str(value)).resolve() if isinstance(value, str) and value else None


def _jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _read_optional_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return dict(value) if isinstance(value, Mapping) else {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _apply_deterministic_seed(seed: int) -> None:
    """Bind management and newly spawned worker processes to the job seed."""

    if seed < 0:
        raise ValueError("evaluation seed must be non-negative")
    os.environ["JUST_PEACHY_EVALUATION_SEED"] = str(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover - management environment includes NumPy
        pass
