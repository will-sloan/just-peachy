from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.enrollment import EnrollmentDatabase, add_enrollment_exemplar
from app.inference_pipeline.speaker_embedding import normalize_vector
from app.inference_pipeline.speaker_matching import (
    DECISION_ACCEPTED,
    DECISION_AMBIGUOUS,
    DECISION_BELOW_THRESHOLD,
    DECISION_MODEL_MISMATCH,
    DECISION_NO_ENROLLED_SPEAKERS,
    CosineThresholdSpeakerMatcher,
    build_speaker_matcher_from_config,
)
from app.inference_pipeline.speaker_matching.thresholds import (
    CalibrationSample,
    calibrate_thresholds,
    threshold_calibration_report_path,
    write_threshold_calibration_report,
)


CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
MODEL_ID = "speaker-embedder@1"


def test_obvious_match_returns_enrolled_name_with_score_and_margin() -> None:
    db = enrollment_db()
    matcher = CosineThresholdSpeakerMatcher(
        threshold=0.80,
        min_margin=0.10,
        runtime_model_id=MODEL_ID,
        scoring_mode="exemplar",
    )

    decision = matcher.match(query_embedding((0.98, 0.04, 0.0)), db)

    assert decision.threshold_decision == DECISION_ACCEPTED
    assert decision.accepted is True
    assert decision.speaker_label == "Alice"
    assert decision.best_label == "Alice"
    assert decision.confidence is not None
    assert decision.confidence > 0.99
    assert decision.margin is not None
    assert decision.margin > 0.90
    assert decision.matched_reference_id is not None
    assert json.dumps(decision.to_jsonable())


def test_below_threshold_returns_unknown_conservatively() -> None:
    db = enrollment_db()
    matcher = CosineThresholdSpeakerMatcher(
        threshold=0.95,
        min_margin=0.05,
        runtime_model_id=MODEL_ID,
    )

    decision = matcher.match(query_embedding((0.60, 0.80, 0.0)), db)

    assert decision.threshold_decision == DECISION_BELOW_THRESHOLD
    assert decision.accepted is False
    assert decision.speaker_label == "Unknown"
    assert decision.best_label == "Bob"
    assert decision.confidence == pytest.approx(0.80, abs=1e-4)


def test_ambiguous_match_returns_unknown_when_margin_is_too_small() -> None:
    db = enrollment_db()
    matcher = CosineThresholdSpeakerMatcher(
        threshold=0.60,
        min_margin=0.20,
        runtime_model_id=MODEL_ID,
    )

    decision = matcher.match(query_embedding((1.0, 1.0, 0.0)), db)

    assert decision.threshold_decision == DECISION_AMBIGUOUS
    assert decision.accepted is False
    assert decision.speaker_label == "Unknown"
    assert decision.best_label in {"Alice", "Bob"}
    assert decision.margin is not None
    assert decision.margin < 0.02


def test_no_enrolled_speakers_returns_unknown() -> None:
    db = EnrollmentDatabase.empty(created_at="2026-05-28T00:00:00Z")
    matcher = CosineThresholdSpeakerMatcher(
        threshold=0.70,
        min_margin=0.0,
        runtime_model_id=MODEL_ID,
    )

    decision = matcher.match(query_embedding((1.0, 0.0, 0.0)), db)

    assert decision.threshold_decision == DECISION_NO_ENROLLED_SPEAKERS
    assert decision.accepted is False
    assert decision.speaker_label == "Unknown"
    assert decision.confidence is None


def test_model_mismatch_returns_unknown_before_assignment() -> None:
    db = enrollment_db()
    matcher = CosineThresholdSpeakerMatcher(
        threshold=0.50,
        min_margin=0.0,
        runtime_model_id="speaker-embedder@2",
        enforce_model_id=True,
    )

    decision = matcher.match(query_embedding((1.0, 0.0, 0.0), model_id="speaker-embedder@2"), db)

    assert decision.threshold_decision == DECISION_MODEL_MISMATCH
    assert decision.accepted is False
    assert decision.speaker_label == "Unknown"
    assert "model_id mismatch" in str(decision.notes)


def test_config_can_build_cosine_threshold_matcher() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["speaker_matching"] = {
        "name": "cosine_threshold",
        "enabled": True,
        "adapter": "CosineThresholdSpeakerMatcher",
        "params": {
            "threshold": 0.77,
            "min_margin": 0.11,
            "runtime_model_id": MODEL_ID,
        },
    }
    config = PipelineConfig.from_mapping(mapping)

    matcher = build_speaker_matcher_from_config(config)

    assert isinstance(matcher, CosineThresholdSpeakerMatcher)
    assert matcher.threshold == pytest.approx(0.77)
    assert matcher.min_margin == pytest.approx(0.11)
    assert matcher.runtime_model_id == MODEL_ID


def test_threshold_calibration_recommends_conservative_threshold_and_writes_report(
    tmp_path: Path,
) -> None:
    db = enrollment_db()
    samples = (
        CalibrationSample(
            sample_id="alice-q1",
            true_label="Alice",
            embedding=normalize_vector((0.99, 0.01, 0.0)),
            model_id=MODEL_ID,
        ),
        CalibrationSample(
            sample_id="bob-q1",
            true_label="Bob",
            embedding=normalize_vector((0.01, 0.99, 0.0)),
            model_id=MODEL_ID,
        ),
        CalibrationSample(
            sample_id="unknown-near-bob",
            true_label="Mallory",
            embedding=normalize_vector((0.60, 0.80, 0.0)),
            model_id=MODEL_ID,
        ),
    )

    result = calibrate_thresholds(
        samples,
        db,
        run_id="unit",
        thresholds=(0.50, 0.80, 0.95),
        min_margin=0.05,
        runtime_model_id=MODEL_ID,
    )
    report_path = threshold_calibration_report_path(tmp_path / "reports", "unit")
    write_threshold_calibration_report(
        report_path,
        result,
        files_changed=["tests/inference_pipeline/test_speaker_matching.py"],
        test_commands=["python -m pytest tests/inference_pipeline/test_speaker_matching.py"],
        smoke_commands=[],
        runner_contract="Unit calibration test does not touch the runner contract.",
    )

    assert result.recommended_threshold == pytest.approx(0.95)
    assert result.recommended_metrics is not None
    assert result.recommended_metrics.false_known_rate == pytest.approx(0.0)
    assert result.recommended_metrics.unknown_rejection_rate == pytest.approx(1.0)
    assert result.verification.equal_error_rate is not None
    assert "Recommended threshold" in report_path.read_text(encoding="utf-8")


def enrollment_db() -> EnrollmentDatabase:
    db = EnrollmentDatabase.empty(created_at="2026-05-28T00:00:00Z")
    db, _ = add_enrollment_exemplar(
        db,
        display_name="Alice",
        prompt_id="clean_enrollment_v1",
        audio_path=Path("alice_1.wav"),
        embedding=(1.0, 0.0, 0.0),
        model_id=MODEL_ID,
        created_at="2026-05-28T00:00:01Z",
        duration_sec=1.0,
        validate_audio_path=False,
    )
    db, _ = add_enrollment_exemplar(
        db,
        display_name="Alice",
        prompt_id="clean_enrollment_v1",
        audio_path=Path("alice_2.wav"),
        embedding=(0.98, 0.02, 0.0),
        model_id=MODEL_ID,
        created_at="2026-05-28T00:00:02Z",
        duration_sec=1.0,
        validate_audio_path=False,
    )
    db, _ = add_enrollment_exemplar(
        db,
        display_name="Bob",
        prompt_id="clean_enrollment_v1",
        audio_path=Path("bob_1.wav"),
        embedding=(0.0, 1.0, 0.0),
        model_id=MODEL_ID,
        created_at="2026-05-28T00:00:03Z",
        duration_sec=1.0,
        validate_audio_path=False,
    )
    return db


def query_embedding(
    vector: tuple[float, ...],
    *,
    model_id: str = MODEL_ID,
) -> dict[str, object]:
    return {
        "embedding_id": "query-001",
        "vector": list(normalize_vector(vector)),
        "model_id": model_id,
    }
