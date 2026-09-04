from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.full_pipeline_development.freeze import (
    MANDATORY_EXTENDED_PIPELINES,
    baseline_alignment_buffering_policy,
    build_extended_set,
    freeze_all_pipeline_configs,
)
from app.full_pipeline_development.policies import (
    DevelopmentPolicyError,
    FROZEN_HYBRID_SELECTION_SHA256,
    OBSERVATION_SCHEMA_VERSION,
    audit_frozen_anchor_policies,
    build_development_policy_registry,
    challenger_pipeline_ids,
    development_role,
    resolve_decision_policy_contract,
    select_development_calibration_cases,
)
from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_evaluation.store import EvaluationJobSpec
from app.full_pipeline_evaluation.worker import (
    PreparedGallery,
    _challenger_score_observations,
)


SHA = "a" * 64
ANCHOR_QUALIFICATION = {
    "schema_version": "full-pipeline-anchor-runtime-qualification.v1",
    "status": "PASS",
    "evaluation_material_inspected": False,
    "qualification_result_sha256": "c" * 64,
    "correct_diarization_embedding_provenance": True,
    "predicted_overlap_excluded_from_primary_identity": True,
    "product_v2_probe_consistency_semantics": True,
    "product_v2_hysteresis_semantics": True,
    "decision_policy_hash_is_not_enrollment_hash": True,
    "all_six_anchor_pipelines_integrated_smoke_passed": True,
}


def _observation(
    pipeline_id: str,
    ordinal: int,
    *,
    gallery_size: int = 5,
    split: str = "development",
    source_time_sec: float | None = None,
) -> dict[str, object]:
    selection = matrix().resolve(pipeline_id)
    return {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "pipeline_id": pipeline_id,
        "hybrid_label": selection.hybrid_label,
        "identity_backend_id": selection.identity["backend_id"],
        "protocol_id": "full_speech_pipeline_v1_test",
        "development_protocol_sha256": SHA,
        "gallery_identity_sha256": f"{ordinal % 16:x}" * 64,
        "gallery_requested_size": str(gallery_size),
        "enrollment_policy_sha256": selection.enrollment_policy["sha256"],
        "case_id": f"case_{ordinal:04d}",
        "anonymous_speaker_id": f"anon_{ordinal:04d}",
        "observation_id": f"obs_{ordinal:04d}",
        "split": split,
        "truth_state": "UNKNOWN",
        "calibration_role": "calibration",
        "status": "VALID",
        "overlay_condition": "ALL_UNKNOWN",
        "evaluation_material_inspected": False,
        "gallery_size": gallery_size,
        "source_time_sec": source_time_sec or 5.0,
        "evidence_duration_sec": 3.0,
        "embedding_consistency": 0.8,
        "top1_score": 0.2 + ordinal / 1000.0,
        "top1_candidate_id": "ENROLLED_0001",
        "top2_score": 0.1,
        "candidate_count": gallery_size,
        "predicted_overlap": False,
    }


def _registry(pipeline_ids: tuple[str, ...]) -> dict[str, object]:
    observations = [
        _observation(pipeline_id, ordinal + index * 1000)
        for index, pipeline_id in enumerate(pipeline_ids)
        for ordinal in range(1, 6)
    ]
    return build_development_policy_registry(
        observations,
        protocol_id="full_speech_pipeline_v1_test",
        development_identity_sha256=SHA,
        expected_pipeline_ids=pipeline_ids,
    )


def test_frozen_anchor_audit_and_contract_bind_decision_source() -> None:
    audit = audit_frozen_anchor_policies()
    assert audit["status"] == "PASS", audit["errors"]
    contract = resolve_decision_policy_contract(
        "fullpipe_v1_ao_dr_ir", realized_gallery_size=57
    )
    assert contract["score_threshold"] == 0.5265351286789879
    assert contract["target_fpir"] == 0.01
    assert contract["decision_policy_sha256"] == FROZEN_HYBRID_SELECTION_SHA256
    assert "scalar_reused" in contract["threshold_scope"]


def test_challenger_calibration_is_exact_pipeline_and_gallery() -> None:
    pipelines = ("fullpipe_v1_ao_dw_iw", "fullpipe_v1_ag_dw_iw")
    registry = _registry(pipelines)
    entries = {row["pipeline_id"]: row for row in registry["entries"]}
    assert entries[pipelines[0]]["calibration_identity_sha256"] != entries[pipelines[1]][
        "calibration_identity_sha256"
    ]
    contract = resolve_decision_policy_contract(
        pipelines[0],
        realized_gallery_size=5,
        gallery_requested_size=5,
        registry=registry,
    )
    assert contract["target_fpir"] == 0.01
    assert contract["margin_threshold"] == 0.03
    assert contract["decision_policy_sha256"] == entries[pipelines[0]][
        "calibration_identity_sha256"
    ]
    with pytest.raises(DevelopmentPolicyError, match="no frozen gallery-request"):
        resolve_decision_policy_contract(
            pipelines[0],
            realized_gallery_size=10,
            gallery_requested_size=10,
            registry=registry,
        )


def test_calibration_rejects_evaluation_material() -> None:
    pipeline_id = "fullpipe_v1_ao_dw_iw"
    with pytest.raises(DevelopmentPolicyError, match="non-development"):
        build_development_policy_registry(
            [_observation(pipeline_id, 1, split="evaluation")],
            protocol_id="full_speech_pipeline_v1_test",
            development_identity_sha256=SHA,
            expected_pipeline_ids=(pipeline_id,),
        )


def test_calibration_case_selector_uses_source_case_and_all_unknown() -> None:
    source_case = next(
        f"source_{index}"
        for index in range(100)
        if development_role(f"source_{index}") == "calibration"
    )
    base = {
        "partition": "development",
        "protocol_case_id": "wrapper_id",
        "source_case_id": source_case,
        "source_key": "product_v2",
        "overlay_id": "ALL_UNKNOWN",
        "gallery_requested_size": "full",
        "gallery_size": 2,
        "gallery_enrolled_ids": ["a", "b"],
    }
    selected = select_development_calibration_cases(
        [base, {**base, "overlay_id": "ALL_KNOWN"}]
    )
    assert len(selected) == 1
    assert selected[0]["gallery_requested_size"] == "full"


def test_latest_valid_checkpoint_is_used_once() -> None:
    pipeline_id = "fullpipe_v1_ao_dw_iw"
    early = _observation(pipeline_id, 1, source_time_sec=3.0)
    late = {**early, "observation_id": "later", "source_time_sec": 6.0, "top1_score": 0.9}
    registry = build_development_policy_registry(
        [early, late],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity_sha256=SHA,
        expected_pipeline_ids=(pipeline_id,),
    )
    entry = registry["entries"][0]
    assert entry["calibration_unknown_clusters"] == 1
    balanced = entry["thresholds_by_gallery_request"][0]["operating_modes"][1]
    assert balanced["score_threshold"] == 0.9


def test_freeze_writes_18_configs_with_separate_diar_and_identity_assets(
    tmp_path: Path,
) -> None:
    registry = _registry(challenger_pipeline_ids())
    result = freeze_all_pipeline_configs(
        policy_registry=registry,
        protocol_id="full_speech_pipeline_v1_test",
        development_protocol_sha256=SHA,
        development_result_set_sha256="b" * 64,
        output_root=tmp_path / "frozen_pipeline_configs",
        runtime_anchor_qualification=ANCHOR_QUALIFICATION,
    )
    assert result["pipeline_count"] == 18
    h4 = yaml.safe_load(
        (tmp_path / "frozen_pipeline_configs/fullpipe_v1_ao_dw_ir.yaml").read_text(
            encoding="utf-8"
        )
    )
    assets = h4["model_assets"]
    assert assets["diarization_embedding"]["backend_id"] == "wespeaker"
    assert assets["identity_embedding"]["backend_id"] == (
        "redimnet2_b2_speaker_embedding"
    )
    assert h4["identity_policy"]["decision_policy_sha256"] == (
        FROZEN_HYBRID_SELECTION_SHA256
    )
    with pytest.raises(FileExistsError, match="immutable"):
        freeze_all_pipeline_configs(
            policy_registry=registry,
            protocol_id="full_speech_pipeline_v1_test",
            development_protocol_sha256=SHA,
            development_result_set_sha256="b" * 64,
            output_root=tmp_path / "frozen_pipeline_configs",
            runtime_anchor_qualification=ANCHOR_QUALIFICATION,
        )


def test_extended_set_is_mandatory_six_plus_unweighted_pareto_challengers() -> None:
    rows = []
    for index, pipeline_id in enumerate(matrix().pipeline_ids):
        values = [5.0 + index / 100.0] * 6
        if pipeline_id == "fullpipe_v1_ao_dw_iw":
            values = [0.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        elif pipeline_id == "fullpipe_v1_ag_de_ie":
            values = [1.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        rows.append(
            {
                "pipeline_id": pipeline_id,
                "split": "development",
                "evaluation_material_inspected": False,
                "qualification_status": "VALID",
                **dict(
                    zip(
                        (
                            "wrong_known_rate",
                            "stranger_false_known_rate",
                            "speaker_attributed_wer",
                            "stable_name_latency_sec",
                            "total_rtf",
                            "peak_rss_bytes",
                        ),
                        values,
                        strict=True,
                    )
                ),
            }
        )
    value = build_extended_set(rows)
    assert value["weighted_composite_score_used"] is False
    assert value["mandatory_pipeline_ids"] == list(MANDATORY_EXTENDED_PIPELINES)
    assert len(value["additional_challenger_pipeline_ids"]) <= 2
    assert set(value["additional_challenger_pipeline_ids"]) <= {
        "fullpipe_v1_ao_dw_iw",
        "fullpipe_v1_ag_de_ie",
    }


def test_baseline_alignment_policy_is_checksum_bound() -> None:
    value = baseline_alignment_buffering_policy()
    assert len(value["identity_sha256"]) == 64
    assert value["development_tuned"] is False


def test_evaluator_enriches_complete_unknown_score_rows_for_calibration() -> None:
    source_case_id = next(
        f"case-{index}"
        for index in range(100)
        if development_role(f"case-{index}") == "calibration"
    )
    pipeline_id = "fullpipe_v1_ao_dw_iw"
    selection = matrix().resolve(pipeline_id)
    job = EvaluationJobSpec(
        job_id="job",
        pipeline_id=pipeline_id,
        protocol_id="source-protocol",
        split="development",
        source_key="controlled_v1",
        measurement_mode="accuracy",
        seed=5107,
        case_count=1,
        audio_duration_sec=2.0,
        protocol_identity="a" * 64,
        pipeline_identity=selection.pipeline_config_sha256,
        reuse_identity={"identity_sha256": "b" * 64},
        case_ids=("fspcase",),
        result_relative_path="development/accuracy/test",
    )
    case = {
        "protocol_case_id": "fspcase",
        "source_case_id": source_case_id,
        "protocol_id": "full_speech_pipeline_v1_test",
        "source_key": "controlled_v1",
        "overlay_id": "ALL_UNKNOWN",
        "gallery_requested_size": 2,
        "gallery_size": 2,
        "gallery_enrolled_ids": ["ENROLLED_1", "ENROLLED_2"],
        "local_to_global_speaker": {"SPK00": "GLOBAL_1"},
    }
    science = {
        "diarization_segments": [
            {"start_sec": 0.0, "end_sec": 2.0, "speaker_id": "SPK00"}
        ],
        "overlay": {
            "speaker_states": {
                "GLOBAL_1": {
                    "identity_state": "UNKNOWN",
                    "unknown_reference_id": "UNKNOWN_REF_1",
                }
            }
        },
    }
    gallery = PreparedGallery(
        root=Path("gallery"),
        profiles=(
            {"gallery_sha256": "c" * 64, "enrolled_id": "ENROLLED_1"},
            {"gallery_sha256": "c" * 64, "enrolled_id": "ENROLLED_2"},
        ),
    )
    rows = _challenger_score_observations(
        [
            {
                "anonymous_speaker_id": "anon_0001",
                "source_time_sec": 2.0,
                "evidence_duration_sec": 2.0,
                "embedding_consistency": 0.9,
                "candidate_raw_cosine_scores": {
                    "ENROLLED_1": 0.42,
                    "ENROLLED_2": 0.31,
                },
            }
        ],
        job=job,
        case=case,
        science=science,
        hypothesis_segments=[
            {
                "start_sec": 0.0,
                "end_sec": 2.0,
                "speaker_id": "anon_0001",
            }
        ],
        selection=selection,
        gallery=gallery,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["schema_version"] == (
        "full-pipeline-challenger-score-observation.v1"
    )
    assert row["truth_state"] == "UNKNOWN"
    assert row["calibration_role"] == "calibration"
    assert row["top1_candidate_id"] == "ENROLLED_1"
    assert row["top2_candidate_id"] == "ENROLLED_2"
    assert row["candidate_count"] == row["gallery_size"] == 2
    assert row["gallery_identity_sha256"] == "c" * 64
    assert row["development_protocol_sha256"] == "a" * 64
    assert row["evaluation_material_inspected"] is False
