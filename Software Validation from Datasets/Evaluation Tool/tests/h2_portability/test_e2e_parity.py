from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.h2_portability.e2e_parity import (
    H2E2EParityError,
    compare_full_pipeline_runs,
    freeze_e2e_parity_protocol,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _events(cluster: str, unknown: str, *, score: float) -> list[dict[str, object]]:
    common = {
        "schema_version": "full-pipeline-contracts.v1",
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "session_id": "volatile-session",
        "processing_timestamps": {"published_utc": "volatile"},
    }
    return [
        {
            **common,
            "event_type": "pipeline_status",
            "contract_type": "PipelineStatusEvent",
            "event_sequence": 1,
            "pipeline_state": "running",
            "errors": [],
            "warnings": [],
        },
        {
            **common,
            "event_type": "speech_activity",
            "contract_type": "SpeechActivityEvent",
            "event_sequence": 2,
            "activity_state": "speech_ended",
            "start_sec": 0.25,
            "end_sec": 1.75,
            "raw_score": 0.9,
        },
        {
            **common,
            "event_type": "anonymous_speaker",
            "contract_type": "AnonymousSpeakerEvent",
            "event_sequence": 3,
            "anonymous_speaker_id": cluster,
            "unknown_label": unknown,
            "unknown_ordinal": 99,
            "cluster_state": "confirmed",
            "start_sec": 0.25,
            "end_sec": 1.75,
            "overlap": False,
            "revision": {"revision_number": 0, "revision_id": "volatile"},
        },
        {
            **common,
            "event_type": "identity_evidence",
            "contract_type": "IdentityEvidenceEvent",
            "event_sequence": 4,
            "anonymous_speaker_id": cluster,
            "evidence_duration_sec": 1.5,
            "candidate_scores": [
                {
                    "candidate_speaker_id": "speaker-a",
                    "candidate_display_label": "Alice",
                    "reference_id": "profile-a",
                    "raw_score": score,
                    "score_type": "cosine_similarity",
                }
            ],
            "top1_candidate_speaker_id": "speaker-a",
            "top1_raw_score": score,
            "top2_candidate_speaker_id": None,
            "top2_raw_score": None,
            "top1_top2_margin": None,
            "decision": "CONFIRMED_KNOWN",
            "decision_reason": {"code": "confirmed", "detail": None},
        },
        {
            **common,
            "event_type": "identity_label",
            "contract_type": "IdentityLabelEvent",
            "event_sequence": 5,
            "anonymous_speaker_id": cluster,
            "identity_state": "confirmed",
            "speaker_label": {"display_label": "Alice", "speaker_id": "speaker-a"},
            "prior_identity_state": "unknown",
            "prior_speaker_label": {"display_label": unknown},
            "evidence_duration_sec": 1.5,
            "confirmation_count": 2,
            "required_confirmation_count": 2,
        },
    ]


def _run_root(
    root: Path,
    *,
    cluster: str,
    unknown: str,
    score: float,
    text: str = "hello world",
    boundary_delta: float = 0.0,
) -> None:
    events = _events(cluster, unknown, score=score)
    if boundary_delta:
        events[1]["end_sec"] = float(events[1]["end_sec"]) + boundary_delta
        events[2]["end_sec"] = float(events[2]["end_sec"]) + boundary_delta
    _write_json(root / "result.json", {"completion_state": "complete", "errors": []})
    _write_jsonl(root / "events/events.jsonl", events)
    _write_json(
        root / "transcript/final_transcript.json",
        {
            "transcript_id": "volatile-transcript",
            "spans": [
                {
                    "span_id": "volatile-span",
                    "anonymous_speaker_id": cluster,
                    "speaker_label": {"display_label": "Alice"},
                    "start_sec": 0.25,
                    "end_sec": 1.75,
                    "state": "final",
                    "text": text,
                }
            ],
        },
    )
    anon = [events[2]]
    _write_jsonl(root / "speakers/anonymous.jsonl", anon)
    _write_jsonl(root / "speakers/identity_evidence.jsonl", [events[3]])
    _write_jsonl(root / "speakers/identity_labels.jsonl", [events[4]])


def _freeze(tmp_path: Path) -> Path:
    path = tmp_path / "freeze.json"
    freeze_e2e_parity_protocol(
        path,
        planned_cases=[{"case_id": "synthetic-enrolled", "identity_required": True}],
    )
    return path


def test_permutation_and_fp32_score_delta_pass(tmp_path: Path) -> None:
    native = tmp_path / "native"
    portable = tmp_path / "portable"
    _run_root(native, cluster="anon-native-9", unknown="Unknown_9", score=0.7)
    _run_root(
        portable,
        cluster="anon-portable-1",
        unknown="Unknown_1",
        score=0.7000001,
    )
    report = compare_full_pipeline_runs(
        native,
        portable,
        output_path=tmp_path / "report.json",
        freeze_receipt_path=_freeze(tmp_path),
        case_identity={"require_identity_exercised": True},
    )
    assert report["status"] == "E2E_PARITY_PASS"
    assert report["exact_checks"]["cluster_coassignment"] is True
    assert report["identity_path_exercised"] is True


@pytest.mark.parametrize(
    ("text", "boundary_delta"),
    (("different words", 0.0), ("hello world", 1.0e-5)),
)
def test_semantic_or_boundary_drift_fails(
    tmp_path: Path, text: str, boundary_delta: float
) -> None:
    native = tmp_path / "native"
    portable = tmp_path / "portable"
    _run_root(native, cluster="anon-a", unknown="Unknown_1", score=0.7)
    _run_root(
        portable,
        cluster="anon-b",
        unknown="Unknown_7",
        score=0.7,
        text=text,
        boundary_delta=boundary_delta,
    )
    report = compare_full_pipeline_runs(
        native,
        portable,
        output_path=tmp_path / "report.json",
        freeze_receipt_path=_freeze(tmp_path),
        case_identity={"require_identity_exercised": True},
    )
    assert report["status"] == "E2E_PARITY_FAIL"


def test_tampered_freeze_receipt_is_rejected(tmp_path: Path) -> None:
    freeze = _freeze(tmp_path)
    value = json.loads(freeze.read_text(encoding="utf-8"))
    value["tolerances"]["identity_score_max_abs"] = 1.0
    _write_json(freeze, value)
    with pytest.raises(H2E2EParityError, match="does not match code contract"):
        freeze_e2e_parity_protocol(freeze, planned_cases=[])
