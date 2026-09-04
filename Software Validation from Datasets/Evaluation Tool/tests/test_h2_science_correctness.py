from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.h2_product_program.contracts import H2Job, H2ProgramError, ProgramPaths
from app.h2_product_program.io import read_jsonl, write_json_atomic
from app.h2_product_program import reporting
from app.h2_product_program.promotion import (
    METRIC_PRIORITY,
    REQUIRED_SHORT_TURN_METRICS,
    select_promotions,
    validate_metric_priority_contract,
)
from app.h2_product_program.selection import build_panel_manifest
from app.full_pipeline_evaluation.schema import TRACK_B_CATEGORY_TO_RESULT_VIEW
from app.h2_product_program.science import (
    OBSERVATION_SCHEMA_VERSION,
    build_policy_frontier,
    hierarchical_speaker_case_bootstrap,
)


def _observation(
    index: int,
    *,
    role: str,
    truth: str,
    speaker: str,
    score: float,
    evidence: float = 2.0,
) -> dict[str, object]:
    return {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "case_id": f"case-{index}",
        "anonymous_speaker_id": "cluster-1",
        "observation_id": f"observation-{index}",
        "truth_state": truth,
        "reference_global_speaker_id": speaker,
        "reference_enrolled_id": "known-a" if truth == "KNOWN" else None,
        "calibration_role": role,
        "status": "VALID",
        "source_time_sec": 3.0,
        "evidence_duration_sec": evidence,
        "embedding_consistency": 0.5,
        "predicted_overlap": False,
        "candidate_raw_cosine_scores": {"known-a": score, "known-b": 0.2},
        "gallery_requested_size": "source_full",
        "gallery_size": 2,
        "split": "development",
        "evaluation_material_inspected": False,
    }


def test_promotion_priority_contract_matches_catalog() -> None:
    validate_metric_priority_contract()
    priority = {metric_id: category for metric_id, category, _ in METRIC_PRIORITY}
    assert priority["miss_rate"] == "diarization"
    assert (
        priority["correct_transcribed_attributed_word_rate"] == "speaker_transcription"
    )
    assert priority["wrong_name_dwell_sec"] == "ux"
    assert priority["transcript_revision_count"] == "ux"
    assert REQUIRED_SHORT_TURN_METRICS <= set(priority)


def test_successive_halving_panels_are_nested_and_short_turn_qualified() -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    protocol_root = evaluation_root / "benchmarks/full_pipeline/full_speech_pipeline_v1"
    development = read_jsonl(protocol_root / "development/case_manifest.jsonl")
    evaluation = read_jsonl(protocol_root / "evaluation/case_manifest.jsonl")

    first = build_panel_manifest(
        development,
        evaluation,
        tool_root=evaluation_root,
        seed=3800,
    )
    second = build_panel_manifest(
        development,
        evaluation,
        tool_root=evaluation_root,
        seed=3800,
    )

    assert first == second
    assert all(first["nesting"].values())
    strategy = first["development"]["successive_halving_panel_strategy"]
    assert strategy["membership_selection_reference_turn_durations_inspected"] is False
    assert strategy["evaluation_reference_content_inspected"] is False
    for panel_name in ("small", "medium"):
        audit = strategy["development_reference_turn_duration_qualification"][
            panel_name
        ]
        assert audit["all_required_bins_have_evidence"] is True
        assert set(audit["bins"]) == REQUIRED_SHORT_TURN_METRICS
        assert all(
            row["turn_count"] > 0
            and row["reference_speech_duration_sec"] > 0.0
            and row["has_evidence"] is True
            for row in audit["bins"].values()
        )


def test_historical_steering_values_are_rederived_from_bound_sources(
    tmp_path: Path,
) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    paths = ProgramPaths(
        evaluation_root=evaluation_root,
        workspace=tmp_path / "workspace",
        results_root=tmp_path / "results",
        summary_root=tmp_path / "summary",
        config_path=evaluation_root
        / "configs/automated_evaluation/h2_product_program.v8.yaml",
    )

    rows, sources, manifest_sha = reporting._verified_historical_values(paths)
    by_key = {(str(row["evidence_family"]), str(row["metric_id"])): row for row in rows}

    assert len(rows) == 30
    assert len(sources) == 8
    assert len(manifest_sha) == 64
    assert by_key[("FROZEN_H2_PRODUCT_V2", "peak_rss_mb")][
        "historical_value"
    ] == pytest.approx(1044.8809341357655)
    assert by_key[("STANDALONE_PYANNOTE_REDIM", "miss_rate")][
        "historical_value"
    ] == pytest.approx(0.3127426647163661)
    assert by_key[("REDIM_ENROLLMENT_LIVE_V2", "tpir_3s")][
        "historical_value"
    ] == pytest.approx(0.8853695324283559)
    assert (
        by_key[("REDIM_ENROLLMENT_LIVE_V2", "embedding_dimension")]["historical_value"]
        == 192.0
    )


def test_corrected_metrics_enter_common_promotion_priority(tmp_path: Path) -> None:
    jobs = tuple(
        H2Job(
            job_id=f"job_{candidate}",
            phase_index=1,
            phase_name="SEGMENTATION_FRONTIER",
            job_kind="successive_halving_runtime",
            split="development",
            pipeline_id="fullpipe_v1_ag_dr_ir",
            configuration_id=f"{candidate}_SMALL",
            mode="H2_SESSION_MEMORY_ENHANCED",
            case_ids=("case",),
            audio_duration_sec=1.0,
            runtime_tuning={},
        )
        for candidate in ("SAFE", "LESS_SAFE")
    )
    for ordinal, job in enumerate(jobs):
        by_result_view: dict[str, dict[str, dict[str, object]]] = {}
        for metric_id, category, direction in METRIC_PRIORITY:
            value = float(ordinal) if direction == "min" else 1.0 - 0.1 * float(ordinal)
            result_view = TRACK_B_CATEGORY_TO_RESULT_VIEW[category]
            subviews = by_result_view.setdefault(result_view, {})
            subviews.setdefault(category, {})[metric_id] = {
                "status": "computed",
                "value": value,
            }
        for result_view, subviews in by_result_view.items():
            write_json_atomic(
                tmp_path
                / "jobs"
                / job.job_id
                / "result"
                / "metrics"
                / f"{result_view}.json",
                {
                    "subviews": {
                        category: {"metrics": metrics}
                        for category, metrics in subviews.items()
                    }
                },
            )

        metric_root = tmp_path / "jobs" / job.job_id / "result" / "metrics"
        assert not (metric_root / "speaker_transcription.json").exists()
        assert not (metric_root / "ux.json").exists()

    decision = select_promotions(jobs, results_root=tmp_path, maximum=1)

    assert decision["selected_candidates"] == ["SAFE"]
    assert decision["common_metric_priority"] == [
        metric_id for metric_id, _category, _direction in METRIC_PRIORITY
    ]


def test_promotion_fails_closed_when_a_required_short_turn_bin_is_missing(
    tmp_path: Path,
) -> None:
    job = H2Job(
        job_id="job_missing_short_turn_bin",
        phase_index=1,
        phase_name="SEGMENTATION_FRONTIER",
        job_kind="successive_halving_runtime",
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id="MISSING_BIN_SMALL",
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=("case",),
        audio_duration_sec=1.0,
        runtime_tuning={},
    )
    by_result_view: dict[str, dict[str, dict[str, object]]] = {}
    missing_metric = "short_turn_der_lt_0_5_sec"
    for metric_id, category, _direction in METRIC_PRIORITY:
        result_view = TRACK_B_CATEGORY_TO_RESULT_VIEW[category]
        subviews = by_result_view.setdefault(result_view, {})
        subviews.setdefault(category, {})[metric_id] = {
            "status": "undefined" if metric_id == missing_metric else "computed",
            "value": None if metric_id == missing_metric else 0.0,
        }
    for result_view, subviews in by_result_view.items():
        write_json_atomic(
            tmp_path
            / "jobs"
            / job.job_id
            / "result"
            / "metrics"
            / f"{result_view}.json",
            {
                "subviews": {
                    category: {"metrics": metrics}
                    for category, metrics in subviews.items()
                }
            },
        )

    with pytest.raises(
        H2ProgramError,
        match="required development safety and short-turn metric",
    ):
        select_promotions((job,), results_root=tmp_path, maximum=1)


def test_no_eligible_calibration_scores_use_finite_reject_all_threshold() -> None:
    rows = [
        _observation(
            1,
            role="calibration",
            truth="UNKNOWN",
            speaker="u1",
            score=0.8,
            evidence=0.5,
        ),
        _observation(
            2,
            role="calibration",
            truth="UNKNOWN",
            speaker="u2",
            score=0.7,
            evidence=0.5,
        ),
        _observation(
            3,
            role="selection",
            truth="KNOWN",
            speaker="k1",
            score=0.9,
        ),
    ]

    result = build_policy_frontier(
        rows,
        target_fpirs=(0.01,),
        margins=(0.01,),
        evidence_durations=(2.0,),
        consistency_thresholds=(0.35,),
    )[0]

    assert math.isfinite(float(result["score_threshold"]))
    assert float(result["score_threshold"]) > 0.8
    assert result["eligible_calibration_unknown_clusters"] == 0
    assert result["eligible_calibration_unknown_speakers"] == 0
    assert result["accepted_calibration_unknown_speakers"] == 0
    assert result["margin_empty_fallback_used"] is True
    assert result["empirical_fpir_resolution"] == 0.5
    assert result["target_below_empirical_resolution"] is True
    assert result["target_fpir_demonstrated"] is False
    assert result["target_fpir_claim"] == (
        "NOT_DEMONSTRATED_BELOW_EMPIRICAL_RESOLUTION"
    )
    assert result["zero_false_id_binomial_upper_95"] == pytest.approx(
        1.0 - math.sqrt(0.05)
    )


def test_zero_false_id_upper_bound_can_support_resolvable_target() -> None:
    rows = [
        _observation(
            index,
            role="calibration",
            truth="UNKNOWN",
            speaker=f"u{index}",
            score=0.4,
        )
        for index in range(400)
    ]
    rows.append(
        _observation(
            1000,
            role="selection",
            truth="KNOWN",
            speaker="k1",
            score=0.9,
        )
    )

    result = build_policy_frontier(
        rows,
        target_fpirs=(0.01,),
        margins=(0.01,),
        evidence_durations=(2.0,),
        consistency_thresholds=(0.35,),
    )[0]

    assert result["empirical_fpir_resolution"] == pytest.approx(1.0 / 400.0)
    assert result["target_empirically_resolvable"] is True
    assert result["accepted_calibration_unknown_speakers"] == 0
    assert result["zero_false_id_binomial_upper_95"] < 0.01
    assert result["target_fpir_demonstrated"] is True
    assert result["target_fpir_claim"] == "DEMONSTRATED_ON_CALIBRATION_COHORT"


def _bootstrap_row(
    case_id: str,
    speakers: list[str],
    *,
    value: float,
    numerator: float | None = None,
    denominator: float | None = None,
    metric_id: str = "wer",
) -> dict[str, object]:
    return {
        "job_id": "heldout",
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "mode": "H2_SESSION_MEMORY_ENHANCED",
        "case_id": case_id,
        "source_key": "controlled_v1",
        "reference_speaker_ids": speakers,
        "category": "asr",
        "metric_id": metric_id,
        "status": "computed",
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
    }


def test_bootstrap_keeps_all_probes_in_each_sampled_speaker_cluster() -> None:
    rows = [
        _bootstrap_row("c1", ["s1"], value=0.0, numerator=0.0, denominator=4.0),
        _bootstrap_row("c2", ["s1"], value=1.0, numerator=4.0, denominator=4.0),
    ]

    interval = hierarchical_speaker_case_bootstrap(rows, repetitions=40, seed=3800)[0]

    assert interval["point_estimate"] == 0.5
    assert interval["ci_lower_95"] == 0.5
    assert interval["ci_upper_95"] == 0.5
    assert interval["reference_speaker_cluster_count"] == 1
    assert interval["speaker_cluster_probe_count_min"] == 2
    assert interval["speaker_cluster_probe_count_max"] == 2
    assert interval["within_speaker_case_resampling"] is False


def test_bootstrap_fractional_multi_speaker_point_and_seed_are_deterministic() -> None:
    rows = [
        _bootstrap_row("c1", ["s1", "s2"], value=0.5, numerator=2.0, denominator=4.0),
        _bootstrap_row("c2", ["s1"], value=0.0, numerator=0.0, denominator=4.0),
    ]

    first = hierarchical_speaker_case_bootstrap(rows, repetitions=100, seed=7)
    second = hierarchical_speaker_case_bootstrap(rows, repetitions=100, seed=7)
    interval = first[0]

    assert first == second
    assert interval["point_estimate"] == 0.25
    assert interval["reference_speaker_cluster_count"] == 2
    assert interval["resampling_cluster_count"] == 2
    assert interval["fallback_case_unit_count"] == 0
    assert interval["resampling_unit"] == (
        "whole_speaker_cluster_all_probes_with_case_fallback"
    )
    assert interval["multi_speaker_case_weighting"] == (
        "fractional_by_reference_speaker_count"
    )


def test_bootstrap_uses_explicit_case_fallback_units_without_speakers() -> None:
    rows = [
        _bootstrap_row("c1", [], value=0.0),
        _bootstrap_row("c2", [], value=1.0),
    ]

    interval = hierarchical_speaker_case_bootstrap(rows, repetitions=50, seed=11)[0]

    assert interval["point_estimate"] == 0.5
    assert interval["reference_speaker_cluster_count"] == 0
    assert interval["resampling_cluster_count"] == 2
    assert interval["fallback_case_unit_count"] == 2
    assert interval["fallback_case_unit_row_count"] == 2
