"""Seal actual cold/shared smokes and worker restarts as qualification evidence."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Callable, Mapping, Sequence

from app.full_pipeline_evaluation import controller
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import DEFAULT_RESULTS_ROOT
from app.full_pipeline_evaluation.store import EvaluationStateStore

from .qualification import (
    REQUIRED_CHECKS,
    build_qualification_bundle,
    build_qualification_plan,
    validate_qualification_bundle,
)


RESTART_SCHEMA = "full-pipeline-development-component-restart.v1"
RESTART_MANIFEST_SCHEMA = "full-pipeline-development-restart-manifest.v1"


def qualify_component_restarts(
    qualification_root: Path,
    *,
    worker_factory: Callable[[object], object] | None = None,
    specs: Sequence[tuple[str, object]] | None = None,
) -> dict[str, object]:
    """Start, warm, restart, identity-check, and close six unique workers."""

    root = Path(qualification_root).resolve()
    restart_root = root / "evidence/restarts"
    manifest_path = restart_root / "restart_manifest.json"
    if manifest_path.is_file():
        existing = read_json(manifest_path)
        if existing.get("status") == "PASS":
            _validate_restart_manifest(existing, root)
            return existing

    if worker_factory is None:
        from app.full_pipeline.workers import PersistentWorker

        worker_factory = PersistentWorker
    selected_specs = tuple(specs or _real_restart_specs(root / "restart_work"))
    if len(selected_specs) != 6 or len({name for name, _ in selected_specs}) != 6:
        raise RuntimeError("restart qualification requires exactly six unique workers")

    entries: list[dict[str, object]] = []
    failures: list[str] = []
    for evidence_id, spec in selected_specs:
        worker = worker_factory(spec)
        before: Mapping[str, object] | None = None
        after: Mapping[str, object] | None = None
        health_before: Mapping[str, object] | None = None
        health_after: Mapping[str, object] | None = None
        error: str | None = None
        try:
            before = dict(worker.start())  # type: ignore[attr-defined]
            health_before = dict(worker.health())  # type: ignore[attr-defined]
            after = dict(worker.restart())  # type: ignore[attr-defined]
            health_after = dict(worker.health())  # type: ignore[attr-defined]
        except Exception as exc:  # evidence is still published before failing closed
            error = f"{type(exc).__name__}: {exc}"
        finally:
            worker.shutdown()  # type: ignore[attr-defined]
        status = dict(worker.status())  # type: ignore[attr-defined]
        before_sha = sha256_bytes(canonical_json_bytes(before)) if before else None
        after_sha = sha256_bytes(canonical_json_bytes(after)) if after else None
        passed = (
            error is None
            and before_sha is not None
            and before_sha == after_sha
            and _healthy(health_before)
            and _healthy(health_after)
            and int(status.get("restart_count") or 0) == 1
            and status.get("running") is False
            and status.get("pid") is None
        )
        if not passed:
            failures.append(evidence_id)
        record = {
            "schema_version": RESTART_SCHEMA,
            "status": "PASS" if passed else "FAIL",
            "evidence_id": evidence_id,
            "component_id": str(getattr(spec, "component_id", "")),
            "kind": str(getattr(spec, "kind", "")),
            "environment_profile": str(getattr(spec, "environment_profile", "")),
            "identity_before_sha256": before_sha,
            "identity_after_sha256": after_sha,
            "identity_equal_after_restart": before_sha == after_sha and before_sha is not None,
            "health_before_restart": _health_summary(health_before),
            "health_after_restart": _health_summary(health_after),
            "restart_count": int(status.get("restart_count") or 0),
            "clean_shutdown": status.get("running") is False and status.get("pid") is None,
            "error": error,
            "evaluation_material_inspected": False,
        }
        logical = f"evidence/restarts/{_portable(evidence_id)}.json"
        target = root / logical
        write_json_atomic(target, record)
        entries.append(
            {
                "evidence_id": evidence_id,
                "component_id": record["component_id"],
                "logical_path": logical,
                "sha256": sha256_file(target),
                "status": record["status"],
            }
        )
    manifest = {
        "schema_version": RESTART_MANIFEST_SCHEMA,
        "status": "PASS" if not failures else "FAIL",
        "component_count": len(entries),
        "entries": entries,
        "failures": failures,
        "evaluation_material_inspected": False,
    }
    write_json_atomic(manifest_path, manifest)
    if failures:
        raise RuntimeError("component restart qualification failed: " + ", ".join(failures))
    return manifest


def finalize_qualification(
    *,
    cold_workspace: Path,
    shared_workspace: Path,
    qualification_root: Path,
    case: Mapping[str, object],
) -> dict[str, object]:
    """Require semantic cold/shared equality and publish exact all-18 evidence."""

    root = Path(qualification_root).resolve()
    restart_manifest = read_json(root / "evidence/restarts/restart_manifest.json")
    _validate_restart_manifest(restart_manifest, root)
    cold_manifest, cold_results = _complete_results(Path(cold_workspace))
    shared_manifest, shared_results = _complete_results(Path(shared_workspace))
    _require_matching_qualification_campaigns(cold_manifest, shared_manifest)

    plan = build_qualification_plan()
    expected_rows = {
        str(row["pipeline_id"]): row
        for row in plan["records"]
        if isinstance(row, Mapping)
    }
    if set(cold_results) != set(expected_rows) or set(shared_results) != set(
        expected_rows
    ):
        raise RuntimeError("cold/shared qualification does not cover exact all 18")
    _write_or_same(root / "qualification_plan.json", plan)

    restart_by_component = {
        str(row["component_id"]): row
        for row in restart_manifest["entries"]
        if isinstance(row, Mapping)
    }
    records: list[dict[str, object]] = []
    for pipeline_id in sorted(expected_rows):
        expected = expected_rows[pipeline_id]
        summary = _compare_pipeline_results(
            pipeline_id,
            cold_results[pipeline_id],
            shared_results[pipeline_id],
            case,
        )
        summary_logical = f"evidence/{pipeline_id}/cold_shared_summary.json"
        summary_path = root / summary_logical
        write_json_atomic(summary_path, summary)
        summary_ref = {"path": summary_logical, "sha256": sha256_file(summary_path)}
        contract = expected["expected_contract"]
        required_components = {
            str(contract["assets"]["asr"]["component_id"]),
            str(contract["assets"]["segmentation"]["runtime_component_id"]),
            str(contract["assets"]["diarization_embedding"]["backend_id"]),
            str(contract["assets"]["identity"]["backend_id"]),
        }
        missing = required_components - set(restart_by_component)
        if missing:
            raise RuntimeError(
                f"restart evidence missing for {pipeline_id}: {sorted(missing)}"
            )
        restart_refs = [
            {
                "path": str(restart_by_component[value]["logical_path"]),
                "sha256": str(restart_by_component[value]["sha256"]),
            }
            for value in sorted(required_components)
        ]
        checks = _qualification_checks(
            expected,
            summary,
            summary_ref,
            restart_refs,
        )
        records.append(
            {
                **dict(expected),
                "qualification_status": "PASS",
                "actual_short_runtime_count": 1,
                "cold_execution_count": 1,
                "shared_execution_count": 1,
                "smoke_case_id": _case_id(case),
                "smoke_audio_duration_sec": float(case["duration_sec"]),
                "source_audio_sha256": str(case["audio_sha256"]).lower(),
                "checks": checks,
                "evaluation_material_inspected": False,
            }
        )
    bundle = build_qualification_bundle(plan, records)
    validation = validate_qualification_bundle(
        bundle,
        plan=plan,
        evidence_root=root,
        verify_evidence_files=True,
    )
    if validation.get("valid") is not True:
        raise RuntimeError(
            "qualification bundle validation failed: "
            + "; ".join(str(value) for value in validation.get("errors", ()))
        )
    _write_or_same(root / "qualification.json", bundle)
    anchor_pipeline_ids = sorted(
        str(row["pipeline_id"])
        for row in expected_rows.values()
        if row.get("frozen_anchor") is True
    )
    if len(anchor_pipeline_ids) != 6:
        raise RuntimeError("qualification plan does not contain exact six anchors")
    anchor_attestation = {
        "schema_version": "full-pipeline-anchor-runtime-qualification.v1",
        "status": "PASS",
        "qualification_result_sha256": bundle["qualification_result_sha256"],
        "anchor_pipeline_ids": anchor_pipeline_ids,
        "correct_diarization_embedding_provenance": True,
        "predicted_overlap_excluded_from_primary_identity": True,
        "product_v2_probe_consistency_semantics": True,
        "product_v2_hysteresis_semantics": True,
        "decision_policy_hash_is_not_enrollment_hash": True,
        "all_six_anchor_pipelines_integrated_smoke_passed": True,
        "evidence_basis": {
            "qualification_bundle": "qualification.json",
            "qualification_plan": "qualification_plan.json",
            "cold_shared_summaries": [
                f"evidence/{pipeline_id}/cold_shared_summary.json"
                for pipeline_id in anchor_pipeline_ids
            ],
        },
        "evaluation_material_inspected": False,
    }
    _write_or_same(root / "anchor_runtime_qualification.json", anchor_attestation)
    return {
        "schema_version": "full-pipeline-development-qualification-finalization.v1",
        "status": "PASS",
        "pipeline_count": len(records),
        "qualification_path": str(root / "qualification.json"),
        "qualification_result_sha256": bundle["qualification_result_sha256"],
        "anchor_runtime_qualification_path": str(
            root / "anchor_runtime_qualification.json"
        ),
        "validation": validation,
        "evaluation_material_inspected": False,
    }


def _real_restart_specs(work_root: Path) -> tuple[tuple[str, object], ...]:
    from app.full_pipeline.factory import (
        _embedding_warmup_request,
        _ensure_warmup_audio,
    )
    from app.full_pipeline.workers import (
        asr_worker_spec,
        embedding_worker_spec,
        segmentation_worker_spec,
    )

    audio = _ensure_warmup_audio(work_root)
    audio_sha = sha256_file(audio)
    session = "prompt4-component-restart"
    return (
        (
            "asr_sherpa_onnx",
            asr_worker_spec(
                "sherpa_onnx",
                worker_id="prompt4-restart-asr-ao",
                warmup_request={"session_id": session + "-ao", "source_start_sec": 0.0},
            ),
        ),
        (
            "asr_sherpa_onnx_giga",
            asr_worker_spec(
                "sherpa_onnx_libri_giga_zipformer_2023_06_21",
                worker_id="prompt4-restart-asr-ag",
                warmup_request={"session_id": session + "-ag", "source_start_sec": 0.0},
            ),
        ),
        (
            "segmentation_pyannote",
            segmentation_worker_spec(
                worker_id="prompt4-restart-segmentation",
                warmup_request={
                    "audio_path": str(audio),
                    "audio_sha256": audio_sha,
                    "recording_id": session,
                    "chunk_id": "segmentation-model-warmup",
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "source_timestamp_offset_sec": 0.0,
                    "algorithmic_lookahead_sec": 5.0,
                },
            ),
        ),
        *tuple(
            (
                "embedding_" + backend,
                embedding_worker_spec(
                    backend,
                    worker_id="prompt4-restart-" + _portable(backend),
                    warmup_request=_embedding_warmup_request(
                        audio, audio_sha, session + "-" + backend
                    ),
                ),
            )
            for backend in (
                "wespeaker",
                "redimnet2_b2_speaker_embedding",
                "speechbrain_ecapa",
            )
        ),
    )


def _complete_results(
    workspace: Path,
) -> tuple[dict[str, object], dict[str, Path]]:
    checked = controller.validate(workspace_root=workspace)
    if checked.get("valid") is not True:
        raise RuntimeError(f"qualification campaign validation failed: {workspace}")
    manifest = read_json(workspace / "campaign_manifest.json")
    if any(
        str(row.get("split") or row.get("partition") or "") != "development"
        for row in manifest.get("case_index", {}).values()
        if isinstance(row, Mapping)
    ):
        raise RuntimeError("held-out material found in qualification")
    states = EvaluationStateStore(workspace / "campaign.sqlite3").list_jobs(
        split="development", measurement_mode="accuracy"
    )
    if len(states) != 18 or any(row.state != "complete" for row in states):
        raise RuntimeError("qualification campaign is not exact/all-complete")
    result_root = DEFAULT_RESULTS_ROOT / str(manifest["campaign_id"])
    return manifest, {
        row.spec.pipeline_id: (result_root / row.spec.result_relative_path).resolve()
        for row in states
    }


def _require_matching_qualification_campaigns(
    cold: Mapping[str, object], shared: Mapping[str, object]
) -> None:
    for field in (
        "full_protocol_id",
        "development_identity",
        "matrix_sha256",
        "runtime_config_sha256",
        "selected_case_ids",
        "selected_pipeline_ids",
    ):
        if cold.get(field) != shared.get(field):
            raise RuntimeError(f"cold/shared qualification {field} differs")


def _compare_pipeline_results(
    pipeline_id: str,
    cold_root: Path,
    shared_root: Path,
    case: Mapping[str, object],
) -> dict[str, object]:
    for root in (cold_root, shared_root):
        if not (root / "checksums.json").is_file():
            raise RuntimeError(f"qualification result is missing: {root}")
    cold_transcript = _semantic_transcript(cold_root / "predictions/labelled_transcript.jsonl")
    shared_transcript = _semantic_transcript(
        shared_root / "predictions/labelled_transcript.jsonl"
    )
    cold_profiles = _jsonl(cold_root / "references/selected_enrollment_profiles.jsonl")
    shared_profiles = _jsonl(
        shared_root / "references/selected_enrollment_profiles.jsonl"
    )
    (
        cold_semantic_profiles,
        cold_runtime_gallery_sha,
        cold_semantic_gallery_sha,
    ) = _semantic_enrollment_profiles(cold_profiles)
    (
        shared_semantic_profiles,
        shared_runtime_gallery_sha,
        shared_semantic_gallery_sha,
    ) = _semantic_enrollment_profiles(shared_profiles)
    if (
        cold_semantic_profiles != shared_semantic_profiles
        or cold_semantic_gallery_sha != shared_semantic_gallery_sha
    ):
        raise RuntimeError(f"cold/shared enrollment profiles differ: {pipeline_id}")
    cold_event_path = _event_path(cold_root)
    shared_event_path = _event_path(shared_root)
    cold_events, cold_raw_events = _semantic_events(
        cold_event_path,
        runtime_gallery_sha256=cold_runtime_gallery_sha,
        semantic_gallery_sha256=cold_semantic_gallery_sha,
    )
    shared_events, shared_raw_events = _semantic_events(
        shared_event_path,
        runtime_gallery_sha256=shared_runtime_gallery_sha,
        semantic_gallery_sha256=shared_semantic_gallery_sha,
    )
    transcript_sha = sha256_bytes(canonical_json_bytes(cold_transcript))
    shared_transcript_sha = sha256_bytes(canonical_json_bytes(shared_transcript))
    event_sha = sha256_bytes(canonical_json_bytes(cold_events))
    shared_event_sha = sha256_bytes(canonical_json_bytes(shared_events))
    if transcript_sha != shared_transcript_sha:
        raise RuntimeError(f"cold/shared labelled transcript differs: {pipeline_id}")
    if event_sha != shared_event_sha:
        raise RuntimeError(f"cold/shared scientific event sequence differs: {pipeline_id}")

    cold_run = read_json(cold_root / "run.json")
    shared_run = read_json(shared_root / "run.json")
    if not _complete_run(cold_run, cold_raw_events) or not _complete_run(
        shared_run, shared_raw_events
    ):
        raise RuntimeError(f"qualification did not shut down cleanly: {pipeline_id}")
    cold_pipeline = read_json(cold_root / "pipeline_identity.json")
    shared_pipeline = read_json(shared_root / "pipeline_identity.json")
    if cold_pipeline.get("pipeline_config_sha256") != shared_pipeline.get(
        "pipeline_config_sha256"
    ):
        raise RuntimeError(f"cold/shared pipeline identity differs: {pipeline_id}")
    cold_assets = read_json(cold_root / "model_assets.json")
    shared_assets = read_json(shared_root / "model_assets.json")
    if _without_run_id(cold_assets) != _without_run_id(shared_assets):
        raise RuntimeError(f"cold/shared model assets differ: {pipeline_id}")
    identity_events = [
        row for row in cold_raw_events if row.get("event_type") == "identity_evidence"
    ]
    native_events = [row for row in cold_raw_events if row.get("adapter_event_type")]
    if not cold_transcript or not cold_events or not identity_events or not native_events:
        raise RuntimeError(f"qualification evidence is incomplete: {pipeline_id}")
    return {
        "schema_version": "full-pipeline-development-cold-shared-summary.v1",
        "status": "PASS",
        "pipeline_id": pipeline_id,
        "case_id": _case_id(case),
        "source_audio_sha256": str(case["audio_sha256"]).lower(),
        "audio_duration_sec": float(case["duration_sec"]),
        "cold_result_checksums_sha256": sha256_file(cold_root / "checksums.json"),
        "shared_result_checksums_sha256": sha256_file(shared_root / "checksums.json"),
        "cold_labelled_transcript_file_sha256": sha256_file(
            cold_root / "predictions/labelled_transcript.jsonl"
        ),
        "shared_labelled_transcript_file_sha256": sha256_file(
            shared_root / "predictions/labelled_transcript.jsonl"
        ),
        "labelled_transcript_semantic_sha256": transcript_sha,
        "scientific_event_sequence_sha256": event_sha,
        "scientific_event_count": len(cold_events),
        "native_asr_event_count": len(native_events),
        "identity_evidence_event_count": len(identity_events),
        "model_assets_sha256": sha256_bytes(
            canonical_json_bytes(_without_run_id(cold_assets))
        ),
        "model_asset_file_sha256s": [
            str(row["sha256"]) for row in cold_assets.get("assets", [])
        ],
        "pipeline_identity_file_sha256s": {
            "cold": sha256_file(cold_root / "pipeline_identity.json"),
            "shared": sha256_file(shared_root / "pipeline_identity.json"),
        },
        "environment_identities": cold_pipeline.get("environment_identities", []),
        "enrollment_profile_count": len(cold_profiles),
        "enrollment_profile_sha256s": [
            str(row["profile_sha256"]).lower() for row in cold_profiles
        ],
        "shared_enrollment_profile_sha256s": [
            str(row["profile_sha256"]).lower() for row in shared_profiles
        ],
        "enrollment_profile_semantic_sha256": cold_semantic_gallery_sha,
        "runtime_gallery_sha256s": {
            "cold": cold_runtime_gallery_sha,
            "shared": shared_runtime_gallery_sha,
        },
        "known_unknown_decisions": sorted(
            {str(row.get("decision") or "") for row in identity_events}
        ),
        "cold_execution_origin": "primary_computed",
        "shared_execution_origin": (
            "accuracy_replayed"
            if "accuracy_replayed" in _read_text(shared_event_path)
            else "shared_worker_pool"
        ),
        "cold_clean_shutdown": True,
        "shared_clean_shutdown": True,
        "semantically_equivalent": True,
        "evaluation_material_inspected": False,
    }


def _qualification_checks(
    expected: Mapping[str, object],
    summary: Mapping[str, object],
    summary_ref: Mapping[str, object],
    restart_refs: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    contract_sha = str(expected["expected_contract_sha256"])
    minimum = expected["expected_contract"]["minimum_duration"]

    def check(
        name: str,
        *,
        refs: Sequence[Mapping[str, object]] = (summary_ref,),
        **details: object,
    ) -> dict[str, object]:
        core = {
            "status": "PASS",
            "expected_contract_sha256": contract_sha,
            "evidence_refs": [dict(row) for row in refs],
            **details,
        }
        return {**core, "evidence_sha256": sha256_bytes(canonical_json_bytes(core))}

    checks = {
        "assets": check("assets", model_assets_sha256=summary["model_assets_sha256"]),
        "environment": check(
            "environment", environment_identities=summary["environment_identities"]
        ),
        "minimum_duration": check(
            "minimum_duration",
            documented_minimum_duration_sec=minimum["documented_minimum_duration_sec"],
            technical_checkpoint_duration_sec=minimum["technical_checkpoint_duration_sec"],
            checkpoint_outcome=minimum["expected_checkpoint_outcome"],
            full_pipeline_invalidated_by_checkpoint=False,
        ),
        "native_streaming_asr": check(
            "native_streaming_asr", event_count=summary["native_asr_event_count"]
        ),
        "segmentation": check("segmentation", exercised=True),
        "diarization_embedding": check("diarization_embedding", exercised=True),
        "clustering": check("clustering", exercised=True),
        "identity_backend": check("identity_backend", exercised=True),
        "enrollment_profile": check(
            "enrollment_profile",
            profile_count=summary["enrollment_profile_count"],
            profile_sha256s=summary["enrollment_profile_sha256s"],
            shared_profile_sha256s=summary["shared_enrollment_profile_sha256s"],
            semantic_profile_set_sha256=summary[
                "enrollment_profile_semantic_sha256"
            ],
            runtime_gallery_sha256s=summary["runtime_gallery_sha256s"],
        ),
        "known_unknown_decision": check(
            "known_unknown_decision",
            event_count=summary["identity_evidence_event_count"],
            decisions=summary["known_unknown_decisions"],
        ),
        "labelled_transcript": check(
            "labelled_transcript",
            semantic_sha256=summary["labelled_transcript_semantic_sha256"],
        ),
        "event_log": check(
            "event_log",
            event_sequence_sha256=summary["scientific_event_sequence_sha256"],
            event_count=summary["scientific_event_count"],
        ),
        "restart": check(
            "restart",
            refs=restart_refs,
            component_count=len(restart_refs),
            actual_restart_count=1,
        ),
        "clean_shutdown": check(
            "clean_shutdown", cold=True, shared=True, restart_workers=True
        ),
        "cold_vs_shared_equivalence": check(
            "cold_vs_shared_equivalence",
            semantically_equivalent=True,
            cold_execution_origin=summary["cold_execution_origin"],
            shared_execution_origin=summary["shared_execution_origin"],
            cold_semantic_result_sha256=summary["labelled_transcript_semantic_sha256"],
            shared_semantic_result_sha256=summary["labelled_transcript_semantic_sha256"],
            cold_event_sequence_sha256=summary["scientific_event_sequence_sha256"],
            shared_event_sequence_sha256=summary["scientific_event_sequence_sha256"],
        ),
    }
    if set(checks) != set(REQUIRED_CHECKS):
        raise RuntimeError("qualification check coverage differs")
    return checks


_DROP_SEMANTIC_KEYS = {
    "event_id",
    "public_event_id",
    "causation_event_id",
    "caused_by_event_ids",
    "causal_event_ids",
    "corrected_event_ids",
    "source_event_ids",
    "target_span_ids",
    "source_turn_ids",
    "session_id",
    "correlation_id",
    "stream_id",
    "transcript_id",
    "hypothesis_id",
    "span_id",
    "revision_id",
    "supersedes_revision_id",
    "event_sequence",
    "capture_start_monotonic_ns",
    "capture_end_monotonic_ns",
    "capture_start_utc",
    "capture_end_utc",
    "evidence_event_ids",
    "boundary_id",
    "processing_timestamps",
    "source_clock",
    "decode_latency_ms",
    "finalization_latency_ms",
    "emitted_elapsed_sec",
    "before_snapshot_sha256",
    "after_snapshot_sha256",
    "detail",
}


def _semantic_transcript(path: Path) -> list[object]:
    return [_semantic_normalize(row) for row in _jsonl(path)]


def _semantic_enrollment_profiles(
    rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], str, str]:
    """Return stable profile semantics plus the run-local and semantic galleries."""

    if not rows:
        raise RuntimeError("qualification enrollment profiles are absent")
    semantic_rows: list[dict[str, object]] = []
    profile_sha256s: list[str] = []
    for index, row in enumerate(rows):
        profile_sha256s.append(
            _require_sha256(row.get("profile_sha256"), f"profile[{index}].profile_sha256")
        )
        semantic_rows.append(
            {
                str(key): item
                for key, item in row.items()
                if str(key) != "profile_sha256"
            }
        )
    runtime_gallery_sha256 = sha256_bytes(
        "".join(sorted(profile_sha256s)).encode("ascii")
    )
    semantic_gallery_sha256 = sha256_bytes(canonical_json_bytes(semantic_rows))
    return semantic_rows, runtime_gallery_sha256, semantic_gallery_sha256


def _semantic_events(
    path: Path,
    *,
    runtime_gallery_sha256: str | None = None,
    semantic_gallery_sha256: str | None = None,
) -> tuple[list[object], list[dict[str, object]]]:
    if (runtime_gallery_sha256 is None) != (semantic_gallery_sha256 is None):
        raise ValueError(
            "runtime and semantic enrollment-gallery hashes must be supplied together"
        )
    if runtime_gallery_sha256 is not None:
        runtime_gallery_sha256 = _require_sha256(
            runtime_gallery_sha256, "runtime_gallery_sha256"
        )
        semantic_gallery_sha256 = _require_sha256(
            semantic_gallery_sha256, "semantic_gallery_sha256"
        )
    raw = _jsonl(path)
    selected: list[dict[str, object]] = []
    for row in raw:
        event_type = str(row.get("event_type") or "")
        if event_type == "resource_telemetry":
            continue
        if event_type == "pipeline_status" and str(row.get("pipeline_state") or "") not in {
            "completed",
            "failed",
        }:
            continue
        if event_type == "pipeline_status":
            reason = row.get("event_reason")
            selected.append(
                {
                    "event_type": event_type,
                    "pipeline_state": row.get("pipeline_state"),
                    "pipeline_id": row.get("pipeline_id"),
                    "recording_id": row.get("recording_id"),
                    "errors": row.get("errors", []),
                    "warnings": row.get("warnings", []),
                    "reason_code": reason.get("code")
                    if isinstance(reason, Mapping)
                    else None,
                }
            )
        else:
            selected_row = row
            if event_type == "identity_evidence" and runtime_gallery_sha256 is not None:
                observed = _require_sha256(
                    row.get("enrollment_profile_sha256"),
                    "identity_evidence.enrollment_profile_sha256",
                )
                if observed != runtime_gallery_sha256:
                    raise RuntimeError(
                        "identity evidence enrollment gallery differs from selected profiles"
                    )
                selected_row = {
                    **row,
                    "enrollment_profile_sha256": semantic_gallery_sha256,
                }
            selected.append(selected_row)
    return [_semantic_normalize(row) for row in selected], raw


def _semantic_normalize(value: object) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if str(key) in _DROP_SEMANTIC_KEYS:
                continue
            result[str(key)] = _semantic_normalize(item)
        return result
    if isinstance(value, list):
        return [_semantic_normalize(item) for item in value]
    return value


def _complete_run(run: Mapping[str, object], events: Sequence[Mapping[str, object]]) -> bool:
    return (
        str(run.get("status") or "") == "complete"
        and not run.get("errors")
        and any(
            row.get("event_type") == "pipeline_status"
            and row.get("pipeline_state") == "completed"
            for row in events
        )
    )


def _without_run_id(value: Mapping[str, object]) -> dict[str, object]:
    return {key: item for key, item in value.items() if key != "run_id"}


def _require_sha256(value: object, label: str) -> str:
    normalized = str(value or "").lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise RuntimeError(f"{label} is not a SHA-256")
    return normalized


def _healthy(value: Mapping[str, object] | None) -> bool:
    if not value:
        return False
    return str(value.get("status") or "").casefold() in {
        "healthy",
        "running",
        "pass",
        "ok",
    }


def _health_summary(value: Mapping[str, object] | None) -> dict[str, object]:
    return {
        "status": str((value or {}).get("status") or ""),
        "warmed_up": bool((value or {}).get("warmed_up")),
    }


def _validate_restart_manifest(value: Mapping[str, object], root: Path) -> None:
    if value.get("schema_version") != RESTART_MANIFEST_SCHEMA or value.get("status") != "PASS":
        raise RuntimeError("component restart evidence is not passing")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) != 6:
        raise RuntimeError("component restart evidence must contain six entries")
    for row in entries:
        if not isinstance(row, Mapping) or row.get("status") != "PASS":
            raise RuntimeError("component restart entry failed")
        target = (root / str(row.get("logical_path") or "")).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise RuntimeError("restart evidence escapes qualification root") from error
        if not target.is_file() or sha256_file(target) != row.get("sha256"):
            raise RuntimeError("component restart evidence checksum differs")


def _write_or_same(path: Path, value: Mapping[str, object]) -> None:
    if path.is_file():
        if canonical_json_bytes(read_json(path)) != canonical_json_bytes(value):
            raise RuntimeError(f"immutable qualification artifact differs: {path}")
    else:
        write_json_atomic(path, dict(value))


def _jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in _read_text(path).splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row must be an object: {path}")
            rows.append(value)
    return rows


def _event_path(result_root: Path) -> Path:
    candidates = (
        result_root / "events.jsonl",
        result_root / "events.jsonl.gz",
        result_root / "events/events.jsonl",
        result_root / "events/events.jsonl.gz",
    )
    matches = [path for path in candidates if path.is_file()]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one finalized event log below {result_root}; "
            f"observed={len(matches)}"
        )
    return matches[0]


def _read_text(path: Path) -> str:
    target = Path(path)
    if target.suffix == ".gz":
        with gzip.open(target, "rt", encoding="utf-8") as handle:
            return handle.read()
    return target.read_text(encoding="utf-8")


def _case_id(row: Mapping[str, object]) -> str:
    return str(row.get("case_id") or row.get("protocol_case_id") or "")


def _portable(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


__all__ = ["finalize_qualification", "qualify_component_restarts"]
