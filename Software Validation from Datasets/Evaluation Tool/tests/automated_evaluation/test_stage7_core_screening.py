from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from app.campaign_executor.runtime import _resolve_and_verify_pipeline
from app.core_screening.analysis import analyze_screening_campaign
from app.core_screening.metrics import (
    STAGE10_ONLY_METRICS,
    analyze_asr_items,
    analyze_embedding_results,
    analyze_reliability,
    analyze_vad_segments,
)
from app.core_screening.plan import DEFAULT_PROTOCOL_PATH, build_screening_plan
from app.core_screening.qualification import qualify_core_components
from app.core_screening.selection import AdvancementRules, Objective, select_candidates


TOOL_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = TOOL_ROOT.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
BENCHMARK_ROOT = TOOL_ROOT / "benchmarks" / "v1"
REAL_AUDIO = (
    PROJECT_ROOT
    / "Raw Datasets (Not formatted)"
    / "CMU Arctic"
    / "cmu_us_aew_arctic"
    / "wav"
    / "arctic_b0476.wav"
)


def test_asr_metrics_keep_missing_failed_and_bad_rows_in_view() -> None:
    expected = [
        {
            "recording_id": "a",
            "utt_id": "u1",
            "reference_text": "one two",
            "duration_sec": 2.0,
        },
        {
            "recording_id": "b",
            "utt_id": "u2",
            "reference_text": "three four",
            "duration_sec": 2.0,
        },
    ]
    predictions = [
        {"recording_id": "a", "utt_id": "u1", "text": "one six"},
        {"recording_id": "a", "utt_id": "u1", "text": "duplicate"},
        {"recording_id": "extra", "utt_id": "u9", "text": "unexpected"},
        {"recording_id": "broken", "text": 42},
        "not-a-row",
    ]
    failures = [{"recording_id": "b", "utt_id": "u2", "status": "failed"}]

    result = analyze_asr_items(expected, predictions, failure_rows=failures)

    assert result["expected_items"] == 2
    assert result["valid_predictions"] == 1
    assert result["missing_predictions"] == 1
    assert result["failed_items"] == 1
    assert result["duplicate_predictions"] == 1
    assert result["unexpected_predictions"] == 1
    assert result["malformed_predictions"] == 2
    assert result["substitutions"] == 1
    assert result["deletions"] == 2
    assert result["micro_wer"] == pytest.approx(0.75)
    assert result["macro_wer"] == pytest.approx(0.75)
    assert result["micro_cer"] is not None
    assert "hallucinated_silent_output_rate" not in result
    assert result["unsupported_metrics"][0]["metric"] == (
        "hallucinated_silent_output_rate"
    )


def test_asr_metric_output_is_deterministic_and_silence_metric_is_conditional() -> None:
    expected = [
        {
            "recording_id": "a",
            "utt_id": "u",
            "reference_text": "",
            "duration_sec": 1.0,
            "is_silence": True,
        }
    ]
    predictions = [{"recording_id": "a", "utt_id": "u", "text": "hello hello"}]

    first = analyze_asr_items(expected, predictions)
    second = analyze_asr_items(expected, predictions)

    assert first == second
    assert first["hallucinated_silent_output_rate"] == 1.0
    assert first["repetition_diagnostics"]["mean_repeated_word_rate"] == 0.5


def test_vad_metrics_emit_reference_scores_only_when_supported() -> None:
    referenced = analyze_vad_segments(
        [
            {
                "duration_sec": 5.0,
                "reference_regions": [{"start_sec": 1.0, "end_sec": 3.0}],
                "predicted_regions": [{"start_sec": 1.1, "end_sec": 3.1}],
                "segments": [{"start_sec": 1.1, "end_sec": 3.1}],
            }
        ],
        collar_sec=0.1,
        boundary_tolerance_sec=0.1,
    )
    unreferenced = analyze_vad_segments(
        [
            {
                "duration_sec": 5.0,
                "predicted_regions": [{"start_sec": 1.1, "end_sec": 3.1}],
                "segments": [{"start_sec": 1.1, "end_sec": 3.1}],
            }
        ]
    )

    assert referenced["speech_precision"] == pytest.approx(0.95)
    assert referenced["speech_recall"] == pytest.approx(0.95)
    assert referenced["speech_f1"] == pytest.approx(0.95)
    assert referenced["boundary_within_tolerance_rate"] == 1.0
    assert "speech_precision" not in unreferenced
    assert any(
        row["metric"] == "speech_precision"
        for row in unreferenced["unsupported_metrics"]
    )
    assert unreferenced["segment_count"] == 1


def test_embedding_qualification_measures_repeatability_drift_and_short_rejection() -> (
    None
):
    rows = [
        {
            "segment_id": "s1",
            "pair_id": "p1",
            "condition": "clean",
            "repetition": 1,
            "duration_sec": 1.0,
            "status": "ok",
            "vector": [1.0, 0.0],
        },
        {
            "segment_id": "s1",
            "pair_id": "p1",
            "condition": "clean",
            "repetition": 2,
            "duration_sec": 1.0,
            "status": "ok",
            "vector": [1.0, 0.0],
        },
        {
            "segment_id": "s1-degraded",
            "pair_id": "p1",
            "condition": "degraded",
            "repetition": 1,
            "duration_sec": 1.0,
            "status": "ok",
            "vector": [0.0, 1.0],
        },
        {
            "segment_id": "short",
            "condition": "clean",
            "repetition": 1,
            "duration_sec": 0.2,
            "status": "too_short",
            "vector": [],
        },
    ]

    result = analyze_embedding_results(rows, min_duration_sec=0.75)

    assert result["successful_extractions"] == 3
    assert result["dimensions"] == {"2": 3}
    assert result["repeatability_cosine"]["mean"] == 1.0
    assert result["clean_to_degraded_cosine_drift"]["mean"] == 1.0
    assert result["minimum_duration_rejection_rate"] == 1.0
    for metric in STAGE10_ONLY_METRICS:
        assert metric not in result


def test_reliability_rates_use_all_attempted_rows() -> None:
    result = analyze_reliability(
        [
            {"status": "succeeded", "attempt": 1},
            {"status": "successful", "attempt": 1},
            {"status": "timeout", "attempt": 2},
            {"status": "out_of_memory", "attempt": 1},
            {"status": "failed_terminal", "attempt": 1},
        ]
    )

    assert result["attempted"] == 5
    assert result["scenario_completion_rate"] == 0.4
    assert result["timeout_rate"] == 0.2
    assert result["oom_rate"] == 0.2
    assert result["retry_rate"] == 0.2


def test_pareto_selection_preserves_accuracy_resource_tradeoff() -> None:
    rules = AdvancementRules(
        objectives=(
            Objective("micro_wer", "min", "accuracy"),
            Objective("mean_rtf", "min", "resource"),
            Objective("valid_output_rate", "max", "reliability"),
        ),
        maximum_candidates=2,
    )
    candidates = [
        _candidate("accurate_slow", wer=0.10, rtf=2.0),
        _candidate("fast_tradeoff", wer=0.15, rtf=1.0),
        _candidate("dominated", wer=0.20, rtf=3.0),
    ]

    result = select_candidates(candidates, rules)

    assert result["pareto_frontier"] == ["accurate_slow", "fast_tradeoff"]
    assert set(result["advanced_candidate_ids"]) == {
        "accurate_slow",
        "fast_tradeoff",
    }
    dominated = next(
        row for row in result["evaluations"] if row["candidate_id"] == "dominated"
    )
    assert set(dominated["dominated_by"]) == {"accurate_slow", "fast_tradeoff"}


def test_advancement_hard_gates_and_repetition_requirements_are_explicit() -> None:
    rules = AdvancementRules(
        objectives=(Objective("micro_wer", "min", "accuracy"),),
        maximum_candidates=1,
        minimum_repetitions=3,
    )
    candidate = _candidate("one", wer=0.1, rtf=1.0)
    candidate["repetitions"] = 1

    result = select_candidates([candidate], rules)

    assert result["advanced_candidate_ids"] == []
    assert (
        "repetitions must be at least 3"
        in result["evaluations"][0]["hard_gate_reasons"]
    )


def test_initial_plan_is_deterministic_targeted_and_uses_whisper_base_reference(
    tmp_path: Path,
) -> None:
    first = build_screening_plan(BENCHMARK_ROOT, tmp_path / "first")
    second = build_screening_plan(BENCHMARK_ROOT, tmp_path / "second")

    assert first["plan_hash"] == second["plan_hash"]
    assert first["scenario_catalog"]["sha256"] == second["scenario_catalog"]["sha256"]
    assert first["reference_asr"] == "whisper_base"
    assert first["benchmark"]["item_count"] == 165
    assert first["scenario_catalog"]["scenario_count"] == 84
    stages = {stage["stage_id"]: stage for stage in first["stages"]}
    assert len(stages["B"]["candidates"]) == 3
    assert len(stages["C"]["candidates"]) == 5
    assert stages["C"]["fixed"]["asr"] == "whisper_base"
    assert stages["D"]["status"] == "pending_selection"
    assert stages["D"]["candidates"] == []
    assert stages["E"]["matcher_scope"] == "cosine contract and composition only"
    assert len(first["candidate_definitions"]) == 7
    assert (
        len(stages["B"]["scenario_ids_by_candidate"]["full_record__whisper_tiny"]) == 12
    )
    assert (
        stages["B"]["scenario_ids_by_candidate"]["full_record__whisper_base"]
        == stages["C"]["scenario_ids_by_candidate"]["full_record__whisper_base"]
    )


def test_targeted_plan_crosses_only_declared_shortlist_and_repeats_finalist(
    tmp_path: Path,
) -> None:
    result = build_screening_plan(
        BENCHMARK_ROOT,
        tmp_path,
        segmentation_shortlist=["energy_chunks", "silero_chunks"],
        finalists=["energy_chunks__whisper_tiny"],
    )
    stages = {stage["stage_id"]: stage for stage in result["stages"]}

    assert len(stages["D"]["candidates"]) == 6
    assert set(stages["D"]["candidates"]) == {
        f"{segmentation}__{asr}"
        for segmentation in ("energy_chunks", "silero_chunks")
        for asr in ("whisper_tiny", "whisper_base", "whisper_small")
    }
    assert (
        len(stages["FINAL"]["scenario_ids_by_candidate"]["energy_chunks__whisper_tiny"])
        == 36
    )
    finalist_ids = set(
        stages["FINAL"]["scenario_ids_by_candidate"]["energy_chunks__whisper_tiny"]
    )
    repetitions = {
        row["repetition"]
        for line in (tmp_path / "screening_scenarios.jsonl").read_text().splitlines()
        if (row := json.loads(line))["scenario_id"] in finalist_ids
    }
    assert repetitions == {1, 2, 3}


def test_whisper_base_is_the_configured_default_but_reference_is_overridable(
    tmp_path: Path,
) -> None:
    protocol_path = tmp_path / "tiny_reference.yaml"
    protocol_path.write_text(
        DEFAULT_PROTOCOL_PATH.read_text(encoding="utf-8").replace(
            "reference_asr: whisper_base", "reference_asr: whisper_tiny"
        ),
        encoding="utf-8",
    )

    result = build_screening_plan(
        BENCHMARK_ROOT,
        tmp_path / "plan",
        protocol_path=protocol_path,
    )
    stage_c = next(stage for stage in result["stages"] if stage["stage_id"] == "C")

    assert result["reference_asr"] == "whisper_tiny"
    assert stage_c["fixed"]["asr"] == "whisper_tiny"
    assert set(stage_c["candidates"]) == {
        "full_record__whisper_tiny",
        "energy_observe__whisper_tiny",
        "energy_chunks__whisper_tiny",
        "silero_observe__whisper_tiny",
        "silero_chunks__whisper_tiny",
    }


def test_campaign_runtime_reconstructs_frozen_stage7_component_overrides(
    tmp_path: Path,
) -> None:
    plan = build_screening_plan(BENCHMARK_ROOT, tmp_path)
    stage_b = next(stage for stage in plan["stages"] if stage["stage_id"] == "B")
    scenario_id = stage_b["scenario_ids_by_candidate"]["full_record__whisper_tiny"][0]
    scenario = next(
        json.loads(line)
        for line in (tmp_path / "screening_scenarios.jsonl").read_text().splitlines()
        if json.loads(line)["scenario_id"] == scenario_id
    )

    resolution = _resolve_and_verify_pipeline(PROJECT_ROOT, scenario)

    assert resolution.pipeline_config.components["asr"].name == "whisper_tiny"
    assert resolution.pipeline_config.components["vad"].enabled is False
    assert resolution.pipeline_config.components["segmentation"].enabled is False


def test_analysis_keeps_missing_scenarios_visible_and_emits_no_stage10_metrics(
    tmp_path: Path,
) -> None:
    plan_root = tmp_path / "plan"
    plan = build_screening_plan(BENCHMARK_ROOT, plan_root)
    campaign = tmp_path / "campaign"
    (campaign / "analysis").mkdir(parents=True)
    (campaign / "benchmark_manifests").mkdir()
    manifest_name = str(plan["benchmark"]["manifest"]["path"])
    shutil.copy2(
        BENCHMARK_ROOT / manifest_name,
        campaign / "benchmark_manifests" / manifest_name,
    )
    index_path = campaign / "analysis" / "analysis_input_index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema_version": "analysis-input-index.v1",
                "campaign_id": "campaign_missing",
                "analysis_input_id": "analysis_input_missing",
                "scenario_results": [],
            }
        ),
        encoding="utf-8",
    )

    result = analyze_screening_campaign(
        plan_root / "core_screening_plan.json",
        index_path,
        output_dir=tmp_path / "analysis_output",
    )

    stages = {stage["stage_id"]: stage for stage in result["stages"]}
    assert set(stages) == {"B", "C", "D"}
    assert stages["B"]["identical_benchmark_items"] is True
    assert all(
        candidate["missing_prediction_rate"] == 1.0
        for candidate in stages["B"]["candidates"]
    )
    assert all(
        candidate["worst_condition_micro_wer"] == 1.0
        for candidate in stages["B"]["candidates"]
    )
    assert {
        "dataset",
        "condition_id",
        "noise_type",
        "snr_db",
        "rir_environment",
        "speaker_id",
        "gender",
        "accent",
    }.issubset(stages["B"]["candidates"][0]["grouped_metrics"])
    assert stages["B"]["selection"]["advanced_candidate_ids"] == []
    assert result["stage10_metric_fields_emitted"] is False


def test_real_stage7_core_qualification_when_local_assets_are_available(
    tmp_path: Path,
) -> None:
    pytest.importorskip("whisper")
    pytest.importorskip("speechbrain")
    model_root = REPOSITORY_ROOT / "models" / "cache" / "whisper"
    if not REAL_AUDIO.is_file() or not all(
        (model_root / name).is_file() for name in ("tiny.pt", "base.pt", "small.pt")
    ):
        pytest.skip("real core qualification audio or Whisper assets are unavailable")
    ecapa_root = (
        REPOSITORY_ROOT / "models" / "cache" / "speechbrain" / "spkrec-ecapa-voxceleb"
    )
    if not ecapa_root.is_dir():
        pytest.skip("SpeechBrain ECAPA assets are unavailable")

    result = qualify_core_components(
        REAL_AUDIO,
        project_root=PROJECT_ROOT,
        repetitions=2,
        output_path=tmp_path / "qualification.json",
    )

    statuses = {row["result_id"]: row["status"] for row in result["results"]}
    assert set(statuses) == {
        "segmentation:full_record",
        "vad:energy_vad",
        "vad:silero_vad",
        "segmentation:vad_chunks",
        "asr:whisper_tiny",
        "asr:whisper_base",
        "asr:whisper_small",
        "speaker_embedding:speechbrain_ecapa",
        "speaker_matching:cosine_threshold_contract",
    }
    assert set(statuses.values()) == {"qualified"}
    assert result["policy"]["implicit_model_downloads_prohibited"] is True
    matcher = next(
        row
        for row in result["results"]
        if row["result_id"] == "speaker_matching:cosine_threshold_contract"
    )
    assert matcher["details"]["unknown_label_preserved"] is True
    assert matcher["details"]["stage10_metrics_emitted"] is False


def _candidate(candidate_id: str, *, wer: float, rtf: float) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "micro_wer": wer,
        "mean_rtf": rtf,
        "valid_output_rate": 1.0,
        "failure_rate": 0.0,
        "timeout_rate": 0.0,
        "oom_rate": 0.0,
        "repetitions": 1,
    }
