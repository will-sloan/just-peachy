from __future__ import annotations

import gzip
import json
from pathlib import Path
from types import SimpleNamespace

from app.full_pipeline_extended_evaluation.analysis import (
    REQUIRED_REPORT_FILES,
    _aggregate_metric,
    _extended_event_metric_rows,
    _flatten_metric_document,
    _native_support_rows,
)


def test_requested_prompt6_outputs_are_complete() -> None:
    assert {
        "extended_summary.csv",
        "true_streaming_asr.csv",
        "online_diarization.csv",
        "online_identity.csv",
        "ux_latency.csv",
        "label_revision.csv",
        "native_results.csv",
        "long_session_results.csv",
        "reliability_results.csv",
        "serial_resources.csv",
        "extended_deployment_evidence.json",
        "failure_analysis.md",
        "extended_report.md",
    }.issubset(REQUIRED_REPORT_FILES)
    assert "failure_inventory.csv" in REQUIRED_REPORT_FILES
    assert "licensing_provenance.json" in REQUIRED_REPORT_FILES


def test_metric_flattening_preserves_conditional_subviews() -> None:
    document = {
        "subviews": {
            "asr": {"metrics": {"wer": {"status": "computed", "value": 0.2}}},
            "speaker_transcription": {
                "metrics": {"cpwer": {"status": "computed", "value": 0.3}}
            },
        }
    }
    rows = list(_flatten_metric_document(document, "fallback"))

    assert [(category, metric) for category, metric, _ in rows] == [
        ("asr", "wer"),
        ("speaker_transcription", "cpwer"),
    ]


def test_metric_aggregation_prefers_sufficient_statistics() -> None:
    result = _aggregate_metric(
        [
            {"status": "computed", "value": 0.5, "numerator": 1, "denominator": 2},
            {"status": "computed", "value": 0.25, "numerator": 1, "denominator": 4},
        ]
    )
    assert result == {
        "value": 2 / 6,
        "status": "computed",
        "aggregation": "micro_sufficient_statistics",
    }


def test_native_support_contract_retains_unsupported_metrics() -> None:
    plan = {
        "panels": {
            "native_chime6": {
                "pipeline_ids": ["p1"],
                "metric_support_contract": {
                    "asr": "unsupported_no_complete_transcript_reference",
                    "diarization": "supported_der_jer",
                    "identity": "unsupported_no_leakage_safe_enrollment",
                },
            }
        }
    }
    rows = _native_support_rows(plan)
    assert len(rows) == 3
    assert any(
        row["category"] == "asr" and "unsupported" in row["status"] for row in rows
    )
    assert any(
        row["category"] == "identity" and "unsupported" in row["status"] for row in rows
    )


def test_online_event_metrics_separate_evidence_compute_and_event_time(
    tmp_path: Path,
) -> None:
    job_id = "job1"
    root = tmp_path / job_id
    root.mkdir()

    def event(sequence: int, event_type: str, **extra: object) -> dict[str, object]:
        return {
            "evaluation_case_id": "case1",
            "event_sequence": sequence,
            "event_type": event_type,
            "source_clock": {"monotonic_epoch_ns": 0},
            "capture_timestamps": {
                "capture_end_monotonic_ns": sequence * 1_000_000_000 - 100_000_000,
                "audio_end_sec": float(sequence) - 0.1,
            },
            "processing_timestamps": {
                "emitted_monotonic_ns": sequence * 1_000_000_000,
                "backend_latency_ms": 20.0,
            },
            **extra,
        }

    events = [
        event(
            1,
            "speech_activity",
            event_reason={
                "detail": "algorithmic_lookahead_sec=0.5;compute_latency_ms=20"
            },
        ),
        event(
            2,
            "anonymous_speaker",
            anonymous_speaker_id="cluster1",
            unknown_label="Unknown_1",
            source_turn_ids=["window1"],
            revision={"revision_number": 0, "reason": {"detail": None}},
        ),
        event(
            3,
            "identity_label",
            anonymous_speaker_id="cluster1",
            identity_state="tentative",
            evidence_duration_sec=1.5,
            speaker_label={"enrolled_speaker_id": "known1"},
        ),
        event(
            4,
            "identity_label",
            anonymous_speaker_id="cluster1",
            identity_state="confirmed",
            evidence_duration_sec=2.0,
            speaker_label={"enrolled_speaker_id": "known1"},
        ),
    ]
    with gzip.open(root / "events.jsonl.gz", "wt", encoding="utf-8") as stream:
        for row in events:
            stream.write(json.dumps(row) + "\n")
    state = SimpleNamespace(
        state="complete",
        spec=SimpleNamespace(
            job_id=job_id, pipeline_id="pipeline1", source_key="integrated"
        ),
    )

    rows = _extended_event_metric_rows(
        tmp_path,
        [state],
        {job_id: {"panel_id": "integrated"}},
    )
    values = {row["metric_id"]: row for row in rows}

    assert values["segmentation_algorithmic_lookahead_sec"]["value"] == 0.5
    assert values["segmentation_backend_compute_latency_sec"]["value"] == 0.02
    assert values["first_tentative_name_event_sec"]["value"] == 3.0
    assert values["first_confirmed_name_event_sec"]["value"] == 4.0
    assert values["tentative_identity_evidence_duration_sec"]["value"] == 1.5
    assert values["source_capture_to_event_latency_sec"]["value"] == 0.1
    assert values["identity_flip_count"]["value"] == 0.0
