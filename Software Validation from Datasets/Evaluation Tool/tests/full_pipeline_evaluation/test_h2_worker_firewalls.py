from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.full_pipeline_evaluation.io import canonical_json_bytes
from app.full_pipeline_evaluation.worker import (
    PreparedGallery,
    _challenger_score_observations,
    _h2_integration_partition,
    execute_evaluation_job,
)


def _partition() -> dict[str, object]:
    core = {
        "schema_version": "h2-development-integration-partition.v2",
        "outcomes_used": False,
        "prediction_or_metric_inputs_used": False,
        "reference_transcript_or_audio_content_used": False,
        "evaluation_material_used": False,
        "calibration_case_count": 1,
        "selection_case_count": 1,
        "excluded_cross_cohort_case_count": 1,
        "calibration_case_ids": ["case-cal"],
        "selection_case_ids": ["case-select"],
        "excluded_cross_cohort_case_ids": ["case-excluded"],
        "calibration_speaker_ids": ["speaker-cal"],
        "selection_speaker_ids": ["speaker-select"],
        "speaker_overlap_count": 0,
        "excluded_cases_used_for_calibration_or_selection": False,
    }
    return {
        **core,
        "assignment_sha256": hashlib.sha256(canonical_json_bytes(core)).hexdigest(),
    }


def _case(case_id: str, speaker_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "partition": "development",
        "global_speaker_ids": [speaker_id],
    }


def test_v2_partition_inventories_excluded_but_executes_only_eligible_cases() -> None:
    partition = _partition()
    cases = (
        _case("case-cal", "speaker-cal"),
        _case("case-select", "speaker-select"),
    )
    validated = _h2_integration_partition(
        {"h2_development_integration_partition": partition},
        job=SimpleNamespace(split="development"),
        cases=cases,
    )

    assert validated == partition
    assert set(validated["excluded_cross_cohort_case_ids"]) == {"case-excluded"}


def test_v2_excluded_case_rejected_before_runtime_construction(tmp_path: Path) -> None:
    constructions = 0

    def runtime_builder(**_kwargs: object) -> object:
        nonlocal constructions
        constructions += 1
        return object()

    cases = (
        _case("case-cal", "speaker-cal"),
        _case("case-select", "speaker-select"),
        _case("case-excluded", "speaker-other"),
    )
    job = SimpleNamespace(case_count=3, split="development")
    with pytest.raises(ValueError, match="exactly match calibration and selection"):
        execute_evaluation_job(
            job,  # type: ignore[arg-type]
            cases,
            tmp_path / "result",
            lambda **_values: None,
            lambda: False,
            runtime_builder=runtime_builder,
            execution_contract={
                "h2_development_integration_partition": _partition(),
                "emit_identity_score_diagnostics": True,
            },
        )
    assert constructions == 0


def test_evaluation_score_diagnostics_rejected_before_runtime_construction(
    tmp_path: Path,
) -> None:
    constructions = 0

    def runtime_builder(**_kwargs: object) -> object:
        nonlocal constructions
        constructions += 1
        return object()

    with pytest.raises(ValueError, match="development-only"):
        execute_evaluation_job(
            SimpleNamespace(case_count=1, split="evaluation"),  # type: ignore[arg-type]
            ({"case_id": "heldout"},),
            tmp_path / "result",
            lambda **_values: None,
            lambda: False,
            runtime_builder=runtime_builder,
            execution_contract={"emit_identity_score_diagnostics": True},
        )
    assert constructions == 0


def _score_inputs() -> tuple[object, ...]:
    job = SimpleNamespace(
        pipeline_id="fullpipe_v1_ag_dr_ir",
        split="development",
        protocol_identity="1" * 64,
    )
    case = {
        "case_id": "case-cal",
        "source_case_id": "source-cal",
        "source_key": "fixture",
        "gallery_enrolled_ids": ["enrolled-a", "enrolled-b"],
        "gallery_requested_size": "2",
        "overlay_id": "MIXED_KNOWN_UNKNOWN",
        "local_to_global_speaker": {"local-a": "speaker-cal"},
    }
    science = {
        "overlay": {
            "speaker_states": {
                "speaker-cal": {
                    "identity_state": "KNOWN",
                    "enrolled_id": "enrolled-a",
                }
            }
        },
        "diarization_segments": [
            {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "local-a"}
        ],
    }
    hypotheses = [
        {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "anon-a"}
    ]
    selection = SimpleNamespace(
        hybrid_label="H2",
        identity={"backend_id": "redimnet2_b2_speaker_embedding"},
        enrollment_policy={"policy_id": "enroll", "sha256": "2" * 64},
    )
    gallery = PreparedGallery(
        root=Path("gallery"),
        profiles=(
            {"profile_id": "profile-a", "gallery_sha256": "3" * 64},
            {"profile_id": "profile-b", "gallery_sha256": "3" * 64},
        ),
    )
    return job, case, science, hypotheses, selection, gallery


def _diagnostic(predicted_overlap: object = False) -> dict[str, object]:
    return {
        "schema_version": "full-pipeline-development-identity-score-diagnostic.v1",
        "anonymous_speaker_id": "anon-a",
        "source_time_sec": 1.0,
        "evidence_duration_sec": 1.0,
        "embedding_consistency": 0.9,
        "predicted_overlap": predicted_overlap,
        "candidate_raw_cosine_scores": {
            "enrolled-a": 0.8,
            "enrolled-b": 0.2,
        },
    }


def _observations(row: dict[str, object]) -> list[dict[str, object]]:
    job, case, science, hypotheses, selection, gallery = _score_inputs()
    return _challenger_score_observations(
        [row],
        job=job,  # type: ignore[arg-type]
        case=case,  # type: ignore[arg-type]
        science=science,  # type: ignore[arg-type]
        hypothesis_segments=hypotheses,  # type: ignore[arg-type]
        selection=selection,
        gallery=gallery,  # type: ignore[arg-type]
        h2_integration_partition=_partition(),
    )


def test_predicted_overlap_is_preserved_and_bound_into_observation_identity() -> None:
    without_overlap = _observations(_diagnostic(False))[0]
    with_overlap = _observations(_diagnostic(True))[0]

    assert without_overlap["predicted_overlap"] is False
    assert with_overlap["predicted_overlap"] is True
    assert without_overlap["observation_id"] != with_overlap["observation_id"]


def test_new_score_diagnostic_requires_explicit_boolean_predicted_overlap() -> None:
    missing = _diagnostic()
    missing.pop("predicted_overlap")
    with pytest.raises(ValueError, match="predicted_overlap"):
        _observations(missing)
    with pytest.raises(ValueError, match="predicted_overlap"):
        _observations(_diagnostic("false"))


def test_excluded_case_never_becomes_a_policy_score_observation() -> None:
    job, case, science, hypotheses, selection, gallery = _score_inputs()
    excluded = {**case, "case_id": "case-excluded"}
    rows = _challenger_score_observations(
        [_diagnostic(True)],
        job=job,  # type: ignore[arg-type]
        case=excluded,
        science=science,  # type: ignore[arg-type]
        hypothesis_segments=hypotheses,  # type: ignore[arg-type]
        selection=selection,
        gallery=gallery,  # type: ignore[arg-type]
        h2_integration_partition=_partition(),
    )
    assert rows == []
