from __future__ import annotations

from app.hybrid_final_evaluation.decision import load_frozen, validate_frozen_decision
from app.hybrid_final_evaluation.runner import plan


def test_task1_frozen_decision_and_all_exact_identities_validate() -> None:
    result = validate_frozen_decision(write_result=False)
    assert result["status"] == "VALID", result["errors"]
    assert result["selected_finalists"] == ["H2", "H5", "H4"]


def test_final_plan_is_held_out_and_has_576_checksum_bound_units() -> None:
    result = plan()
    assert result["controlled_cases"] == {"v1": 120, "v2": 72}
    assert result["controlled_score_bundles"] == 576
    assert result["anonymous_diarization"] == "REUSE_COMPLETE_HELD_OUT_RESULTS"


def test_frozen_policy_exposes_no_task2_tuning_surface() -> None:
    frozen = load_frozen()
    for row in frozen["selected_finalists"]:
        assert row["label_display_policy"] == "ADAPTIVE"
        assert row["margin_threshold"] == 0.03
        assert row["minimum_evidence_sec"] == 2.0
        assert row["overlap_policy"] == "exclude_predicted_overlap_for_identity_primary_include_diagnostic"
    assert frozen["evaluation_authorized"] is True
    assert frozen["EVALUATION_NOT_INSPECTED"] is True

