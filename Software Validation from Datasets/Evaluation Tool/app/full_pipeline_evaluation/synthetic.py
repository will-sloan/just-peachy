"""Tiny model-free result fixtures used by Prompt-3 smoke and tests."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

from .results import ResultTreeBuilder, ResultTreeValidation
from .schema import (
    ARTIFACT_SUPPORT_IDS,
    MODEL_ASSETS_SCHEMA_VERSION,
    PIPELINE_IDENTITY_SCHEMA_VERSION,
    build_metric_documents_from_reports,
    build_run_document,
)
from .scorers import score_full_pipeline


def publish_synthetic_result(
    root: Path,
    *,
    reuse_identity: Mapping[str, object],
    failed: bool = False,
) -> ResultTreeValidation:
    """Publish a tiny perfect or explicit-output-failure common result tree."""

    pipeline_id = str(reuse_identity["pipeline_id"])
    identity_sha = str(reuse_identity["identity_sha256"])
    run_id = f"synthetic_{identity_sha[:16]}_{'fail' if failed else 'perfect'}"
    attempt_id = f"attempt_{identity_sha[:12]}"
    timestamp = _utc_now()
    support = {
        artifact_id: {"status": "supported", "reason": None}
        for artifact_id in ARTIFACT_SUPPORT_IDS
    }
    builder = ResultTreeBuilder(Path(root), reuse_identity)
    prepared = build_run_document(
        run_id=run_id,
        attempt_id=attempt_id,
        reuse_identity=reuse_identity,
        status="prepared",
        created_at_utc=timestamp,
        artifact_support=support,
        counts={"cases": 1, "audio_duration_sec": 1.0},
    )
    builder.publish_run(prepared)
    builder.publish_pipeline_identity(
        {
            "schema_version": PIPELINE_IDENTITY_SCHEMA_VERSION,
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "protocol_version": "full_speech_pipeline_v1",
            "pipeline_config_sha256": reuse_identity["pipeline_config_sha256"],
            "matrix_sha256": "1" * 64,
            "aliases": {"asr": "synthetic", "diarization": "synthetic", "identity": "synthetic"},
            "component_identities": [],
            "policy_identities": [],
            "environment_identities": [],
        }
    )
    builder.publish_model_assets(
        {
            "schema_version": MODEL_ASSETS_SCHEMA_VERSION,
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "assets": [
                {
                    "role": "synthetic_fixture",
                    "asset_id": "no_model_loaded",
                    "sha256": "2" * 64,
                }
            ],
            "no_implicit_downloads": True,
        }
    )
    hypothesis = "" if failed else "perfect synthetic transcript"
    builder.publish_events(
        [
            {
                "schema_version": "full-pipeline-evaluation-synthetic-event.v1",
                "event_sequence": 1,
                "event_type": "output_failure" if failed else "final_transcript",
                "case_id": "synthetic_case_001",
                "text": hypothesis,
            }
        ]
    )
    builder.publish_predictions(
        transcript_rows=[
            {
                "case_id": "synthetic_case_001",
                "text": hypothesis,
                "status": "failed" if failed else "final",
            }
        ],
        labelled_rows=[
            {
                "case_id": "synthetic_case_001",
                "text": hypothesis,
                "speaker_label": None if failed else "Speaker_1",
                "status": "failed" if failed else "final",
            }
        ],
        diarization_rttm=(
            "" if failed else "SPEAKER synthetic 1 0.000 1.000 <NA> <NA> Speaker_1 <NA> <NA>\n"
        ),
    )
    reference_bytes = (
        json.dumps(
            {
                "case_id": "synthetic_case_001",
                "transcript": "perfect synthetic transcript",
                "speaker": "Speaker_1",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    builder.publish_references(
        {
            "artifacts": [
                {
                    "artifact_id": "synthetic_reference",
                    "status": "available",
                    "logical_path": "references/synthetic_case.json",
                    "reason": None,
                }
            ]
        },
        artifacts={"references/synthetic_case.json": reference_bytes},
    )
    reports = score_full_pipeline(
        asr_utterances=[
            {
                "utterance_id": "synthetic_case_001",
                "reference_text": "perfect synthetic transcript",
                "hypothesis_text": None if failed else hypothesis,
                "output_failed": failed,
            }
        ],
        diarization_references=(
            [{"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "Speaker_1"}]
            if not failed
            else None
        ),
        diarization_hypotheses=(
            [{"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "Speaker_1"}]
            if not failed
            else None
        ),
        attribution_intervals=(
            [
                {
                    "start_sec": 0.0,
                    "end_sec": 1.0,
                    "reference_speaker_id": "Speaker_1",
                    "reference_is_known": True,
                    "predicted_speaker_id": "Speaker_1",
                    "decision_state": "confirmed_known",
                    "temperature": "warm",
                    "stable_name_latency_sec": 0.2,
                    "identity_revision_count": 0,
                    "episode_id": "episode_1",
                }
            ]
            if not failed
            else None
        ),
        reference_speaker_texts=(
            {"Speaker_1": "perfect synthetic transcript"} if not failed else None
        ),
        hypothesis_speaker_texts=(
            {"Speaker_1": "perfect synthetic transcript"} if not failed else None
        ),
        speaker_transcript_prerequisites=(
            {
                "reference_streams_complete": True,
                "hypothesis_streams_complete": True,
                "normalization_id": "lowercase_whitespace.v1",
                "permutation_scope": "per_recording",
                "identities_comparable": True,
            }
            if not failed
            else None
        ),
        resource_samples=None,
        resource_kwargs={
            "audio_duration_sec": 1.0,
            "startup_sec": 0.0,
            "model_bytes": 0,
            "cache_bytes": 0,
            "failure_count": 1 if failed else 0,
            "retry_count": 0,
        },
    )
    documents = build_metric_documents_from_reports(
        reports, run_id=run_id, pipeline_id=pipeline_id
    )
    for view, document in documents.items():
        builder.publish_metric(view, document)
    diagnostic = (
        json.dumps(
            {
                "synthetic": True,
                "inference_performed": False,
                "failure_exercised": failed,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    builder.publish_diagnostics(
        {
            "artifacts": [
                {
                    "artifact_id": "synthetic_diagnostic",
                    "status": "available",
                    "logical_path": "diagnostics/synthetic.json",
                    "reason": None,
                }
            ]
        },
        artifacts={"diagnostics/synthetic.json": diagnostic},
    )
    terminal = build_run_document(
        run_id=run_id,
        attempt_id=attempt_id,
        reuse_identity=reuse_identity,
        status="failed" if failed else "complete",
        created_at_utc=timestamp,
        started_at_utc=timestamp,
        ended_at_utc=_utc_now(),
        artifact_support=support,
        counts={"cases": 1, "audio_duration_sec": 1.0},
        errors=(
            [{"code": "synthetic_output_failure", "detail": "expected test path"}]
            if failed
            else []
        ),
    )
    builder.publish_run(terminal)
    return builder.finalize()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
