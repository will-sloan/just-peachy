from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.cli.main import build_parser
from app.controlled_diarization.analysis import analyze_results
from app.controlled_diarization.benchmark import (
    _balance_rows,
    _case_specs,
    _case_statistics,
    _materialize_frozen_audio,
    _overlap_draw,
    _render_case,
    _schedule_case,
    _split_speakers,
    _write_reference_rttm,
    benchmark_plan,
    reconstruct_recipe,
)
from app.controlled_diarization.contracts import (
    BENCHMARK_VERSION,
    CASE_SCHEMA_VERSION,
    DEFAULT_CONFIG_PATH,
    RECIPE_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    ControlledDiarizationError,
    benchmark_id,
    global_speaker_id,
    load_config,
    load_pipeline_registry,
    sha256_file,
)
from app.controlled_diarization.runner import (
    execute_queue,
    scenario_identity,
    validate_result,
)
from app.diarization_evaluation.artifacts import (
    write_checksum_manifest,
    write_json_atomic,
    write_text_atomic,
)
from app.diarization_evaluation.formats import parse_rttm


def _small_config() -> dict[str, object]:
    config = load_config()
    config["panel"] = {
        **config["panel"],
        "smoke": {**config["panel"]["smoke"], "speaker_pool_count": 1},
        "development": {**config["panel"]["development"], "speaker_pool_count": 2},
        "evaluation": {**config["panel"]["evaluation"], "speaker_pool_count": 3},
    }
    return config


def _split_fixture():
    source_keys = [f"spk_cv60p_{index:020d}" for index in range(6)]
    candidates = []
    enrollment = {}
    for index, source_key in enumerate(source_keys):
        speaker = global_speaker_id(source_key)
        enrollment[speaker] = [{"source_clip_id": f"enroll-{index}"}]
        for clip in range(30):
            candidates.append(
                {
                    "global_speaker_id": speaker,
                    "source_protocol_speaker_key": source_key,
                    "source_clip_id": f"clip-{index}-{clip}",
                    "duration_sec": 1.0 + (clip % 6) * 0.5,
                    "selection_rank": f"{clip:04d}",
                }
            )
    source = {
        "known_speakers": source_keys,
        "enrollment_by_global": enrollment,
    }
    return source, candidates


def test_deterministic_speaker_split_is_disjoint_and_pseudonymous() -> None:
    config = _small_config()
    source, candidates = _split_fixture()
    first_rows, first = _split_speakers(config, source, candidates)
    second_rows, second = _split_speakers(config, source, candidates)
    assert first_rows == second_rows
    assert first == second
    assert set(first["development"]).isdisjoint(first["evaluation"])
    assert set(first["smoke"]).isdisjoint(first["development"])
    assert all(value.startswith("cvspk_") for values in first.values() for value in values)
    assert global_speaker_id(source["known_speakers"][0]) == global_speaker_id(
        source["known_speakers"][0]
    )


def test_factorial_design_and_pair_audits_are_balanced() -> None:
    config = load_config()
    protocol = benchmark_id(config, "a" * 64)
    first = _case_specs(config, protocol)
    second = _case_specs(config, protocol)
    assert first == second
    assert sum(row["tier"] == "development" for row in first) == 60
    assert sum(row["tier"] == "evaluation" for row in first) == 120
    assert sum(row["tier"] == "smoke" for row in first) == 8
    cells = {
        (row["speaker_count"], row["turn_cadence"], row["overlap_profile"]): 0
        for row in first
        if row["tier"] == "evaluation" and row["speaker_count"] > 1
    }
    for row in first:
        key = (row["speaker_count"], row["turn_cadence"], row["overlap_profile"])
        if row["tier"] == "evaluation" and key in cells:
            cells[key] += 1
    assert len(cells) == 27
    assert set(cells.values()) == {4}
    appearances, pairs = _balance_rows(
        {
            "smoke": [],
            "development": [],
            "evaluation": [
                {
                    "global_speaker_ids": ["a", "b"],
                    "local_to_global_speaker": {"SPK00": "a", "SPK01": "b"},
                    "reference_statistics": {
                        "per_speaker": {
                            "SPK00": {"speech_duration_sec": 2.0, "turn_count": 3},
                            "SPK01": {"speech_duration_sec": 2.0, "turn_count": 3},
                        }
                    },
                }
            ],
        }
    )
    assert len(appearances) == 2
    assert pairs == [
        {
            "tier": "evaluation",
            "global_speaker_id_a": "a",
            "global_speaker_id_b": "b",
            "cooccurrence_count": 1,
        }
    ]


def test_turn_timing_overlap_rttm_and_bounds(tmp_path: Path) -> None:
    recipe = {
        "case_id": "case-overlap",
        "sample_rate_hz": 16000,
        "output_duration_samples": 64000,
        "placements": [
            {
                "reference_speaker": "SPK00",
                "global_start_sample": 0,
                "global_end_sample": 32000,
                "global_start_sec": 0.0,
                "global_end_sec": 2.0,
            },
            {
                "reference_speaker": "SPK01",
                "global_start_sample": 24000,
                "global_end_sample": 56000,
                "global_start_sec": 1.5,
                "global_end_sec": 3.5,
            },
            {
                "reference_speaker": "SPK00",
                "global_start_sample": 56000,
                "global_end_sample": 64000,
                "global_start_sec": 3.5,
                "global_end_sec": 4.0,
            },
        ],
    }
    stats = _case_statistics(recipe)
    assert stats["overlap_duration_sec"] == pytest.approx(0.5)
    assert stats["max_simultaneously_active_speakers"] == 2
    assert all(
        0 <= row["global_start_sample"] < row["global_end_sample"] <= 64000
        for row in recipe["placements"]
    )
    path = tmp_path / "reference.rttm"
    _write_reference_rttm(path, recipe)
    turns = parse_rttm(path)
    assert all(
        max(left.start_sec, right.start_sec) < min(left.end_sec, right.end_sec)
        for left, right in [(turns[0], turns[1])]
    )


def test_overlap_schedule_is_deterministic_and_none_is_zero() -> None:
    import random

    config = load_config()
    left = random.Random(3800)
    right = random.Random(3800)
    observed_left = [_overlap_draw("moderate", index, left, config) for index in range(1, 20)]
    observed_right = [_overlap_draw("moderate", index, right, config) for index in range(1, 20)]
    assert observed_left == observed_right
    assert any(value > 0 for value in observed_left)
    assert all(_overlap_draw("none", index, left, config) == 0 for index in range(1, 20))


def test_turn_schedule_and_render_are_deterministic(tmp_path: Path) -> None:
    sample_rate = 16000
    config = load_config()
    config["generation"] = {
        **config["generation"],
        "target_duration_sec_by_cadence": {
            **config["generation"]["target_duration_sec_by_cadence"],
            "rapid": 6.0,
        },
        "minimum_duration_sec": 5.0,
        "maximum_duration_sec": 10.0,
    }
    speakers = ("cvspk_test_a", "cvspk_test_b")
    source_by_speaker = {}
    for speaker_index, speaker in enumerate(speakers):
        rows = []
        for clip_index in range(8):
            path = tmp_path / f"{speaker}-{clip_index}.wav"
            frequency = 180 + speaker_index * 80 + clip_index
            samples = (
                0.1
                * np.sin(2 * np.pi * frequency * np.arange(sample_rate) / sample_rate)
            ).astype(np.float32)
            sf.write(path, samples, sample_rate, subtype="PCM_16")
            rows.append(
                {
                    "source_clip_id": f"clip-{speaker_index}-{clip_index}",
                    "logical_audio_path": str(path.resolve()),
                    "duration_sec": 1.0,
                    "selection_rank": f"{clip_index:04d}",
                    "source_protocol_speaker_key": f"source-{speaker_index}",
                    "transcript_sha256": f"{clip_index:064x}",
                }
            )
        source_by_speaker[speaker] = rows
    spec = {
        "case_id": "unit-schedule",
        "tier": "smoke",
        "speaker_count": 2,
        "turn_cadence": "rapid",
        "overlap_profile": "none",
        "replicate": 1,
    }
    labels = {speakers[0]: "SPK00", speakers[1]: "SPK01"}
    first = _schedule_case(
        config, "unit-protocol", spec, speakers, labels, source_by_speaker, set()
    )
    second = _schedule_case(
        config, "unit-protocol", spec, speakers, labels, source_by_speaker, set()
    )
    assert first[0] == second[0]
    placements = first[0]["placements"]
    assert {row["reference_speaker"] for row in placements} == {"SPK00", "SPK01"}
    assert all(
        sum(row["reference_speaker"] == label for row in placements) >= 3
        for label in ("SPK00", "SPK01")
    )
    assert all(
        left["reference_speaker"] != right["reference_speaker"]
        for left, right in zip(placements, placements[1:])
    )
    assert max(row["global_end_sample"] for row in placements) <= 10 * sample_rate
    first_render = _render_case(config, first[0], first[1], tmp_path / "mix-first.wav")
    second_render = _render_case(config, second[0], second[1], tmp_path / "mix-second.wav")
    assert first_render["audio_sha256"] == second_render["audio_sha256"]
    assert first_render["pcm_sha256"] == second_render["pcm_sha256"]


def test_recipe_reconstruction_is_byte_deterministic(tmp_path: Path) -> None:
    sample_rate = 16000
    source = tmp_path / "source.wav"
    samples = (0.1 * np.sin(2 * np.pi * 220 * np.arange(sample_rate) / sample_rate)).astype(
        np.float32
    )
    sf.write(source, samples, sample_rate, subtype="PCM_16")
    recipe = {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "sample_rate_hz": sample_rate,
        "output_duration_samples": sample_rate,
        "mix_peak_protection_gain_db": 0.0,
        "trim_policy": {
            "version": "deterministic_boundary_rms_v1",
            "frame_ms": 20,
            "threshold_dbfs": -60.0,
            "padding_ms": 20,
            "internal_pauses_removed": False,
        },
        "placements": [
            {
                "logical_audio_path": str(source.resolve()),
                "source_audio_sha256": sha256_file(source).upper(),
                "source_crop_start_sample": 0,
                "source_crop_end_sample": sample_rate,
                "source_gain_db": 0.0,
                "global_start_sample": 0,
            }
        ],
    }
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    first = reconstruct_recipe(recipe_path, tmp_path / "first.wav")
    second = reconstruct_recipe(recipe_path, tmp_path / "second.wav")
    assert first == second
    assert first["audio_sha256"] == sha256_file(tmp_path / "first.wav")
    benchmark_root = tmp_path / "benchmark"
    (benchmark_root / "smoke").mkdir(parents=True)
    frozen_recipe = benchmark_root / "recipe.json"
    frozen_recipe.write_text(json.dumps(recipe), encoding="utf-8")
    (benchmark_root / "smoke" / "case_manifest.jsonl").write_text(
        json.dumps(
            {
                "case_id": "fixture",
                "recipe_path": "recipe.json",
                "audio_logical_path": "smoke/audio/fixture.wav",
                "audio_sha256": first["audio_sha256"],
                "pcm_sha256": first["pcm_sha256"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    generated_root = tmp_path / "generated"
    assert _materialize_frozen_audio(benchmark_root, generated_root) == 1
    assert sha256_file(generated_root / "smoke" / "audio" / "fixture.wav") == first[
        "audio_sha256"
    ]
    assert _materialize_frozen_audio(benchmark_root, generated_root) == 0


def _case(benchmark: str) -> dict[str, object]:
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "benchmark_id": benchmark,
        "case_id": "case-001",
        "audio_sha256": "a" * 64,
        "recipe_sha256": "b" * 64,
        "speaker_count": 1,
        "reference_speaker_count": 1,
        "turn_cadence": "relaxed",
        "overlap_profile": "none",
        "replicate": 1,
        "control_kind": "single_speaker_oversegmentation_control",
        "duration_sec": 2.0,
    }


def _valid_result(root: Path, scenario: str) -> None:
    write_json_atomic(
        root / "run.json",
        {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "succeeded",
            "scenario_id": scenario,
            "case_id": "case-001",
            "tier": "smoke",
            "pipeline_id": "sherpa_onnx_diarization",
            "diagnostic_only": False,
            "speaker_count_mode": "estimated",
            "timing": {
                "audio_duration_sec": 2.0,
                "audio_loading_sec": 0.01,
                "diarization_inference_sec": 0.02,
                "total_wall_sec": 0.04,
                "real_time_factor": 0.01,
            },
            "environment": {"environment_profile": "onnx", "hostname": "fixture"},
        },
    )
    write_json_atomic(root / "resolved_pipeline_identity.json", {"pipeline_id": "sherpa_onnx_diarization"})
    write_text_atomic(
        root / "predictions" / "segments.rttm",
        "SPEAKER case-001 1 0.000000 2.000000 <NA> <NA> speaker_00 <NA> <NA>\n",
    )
    write_text_atomic(
        root / "references" / "reference.rttm",
        "SPEAKER case-001 1 0.000000 2.000000 <NA> <NA> SPK00 <NA> <NA>\n",
    )
    write_text_atomic(root / "references" / "scored_region.uem", "case-001 1 0.000000 2.000000\n")
    write_json_atomic(root / "diagnostics" / "alignment_validation.json", {"valid": True})
    write_json_atomic(root / "diagnostics" / "segmentation_provenance.json", {"effective_source": "backend_internal"})
    write_json_atomic(
        root / "metrics" / "summary.json",
        {
            "primary_strict": {
                "metrics_emitted": True,
                "der": 0.0,
                "jer": 0.0,
                "missed_speech_sec": 0.0,
                "false_alarm_sec": 0.0,
                "speaker_confusion_sec": 0.0,
                "reference_speaker_time_sec": 2.0,
                "modes": {"overlap_excluded": {"der": 0.0}},
            },
            "practical_boundary_tolerant": {"der": 0.0},
            "speaker_count": {
                "reference": 1,
                "predicted": 1,
                "signed_error": 0,
                "absolute_error": 0,
                "exact": True,
            },
            "fragmentation": {
                "mean_clusters_per_reference_speaker": 1.0,
                "split_reference_speaker_count": 0,
            },
            "merging": {
                "mean_reference_speakers_per_cluster": 1.0,
                "merged_predicted_cluster_count": 0,
            },
            "cluster_purity": 1.0,
            "reference_speaker_coverage": 1.0,
            "speaker_reentry_consistency": 1.0,
            "reentry_observations": [],
            "turn_boundary": {"0.25": {"f1": 1.0}, "0.5": {"f1": 1.0}},
            "overlap_specific": None,
        },
    )
    write_json_atomic(root / "report" / "scenario_report.json", {"valid": True})
    write_text_atomic(root / "report" / "scenario_report.md", "# Fixture\n")
    write_checksum_manifest(root)


def test_plan_validate_and_restart_reuse(tmp_path: Path) -> None:
    config = load_config()
    registry = load_pipeline_registry(config)
    benchmark = benchmark_id(config, "c" * 64)
    case = _case(benchmark)
    benchmark_root = tmp_path / "benchmark"
    (benchmark_root / "smoke").mkdir(parents=True)
    (benchmark_root / "smoke" / "case_manifest.jsonl").write_text(
        json.dumps(case) + "\n", encoding="utf-8"
    )
    (benchmark_root / "protocol_summary.json").write_text(
        json.dumps({"benchmark_id": benchmark, "total_generated_audio_sec": 2.0}),
        encoding="utf-8",
    )
    plan = benchmark_plan(
        benchmark_root=benchmark_root,
        pipelines=("sherpa_onnx_diarization",),
        tier="smoke",
    )
    assert plan["expected_inference_units"] == 1
    scenario = scenario_identity(config, registry["sherpa_onnx_diarization"], case)
    result_root = tmp_path / "results"
    result = result_root / "smoke" / "sherpa_onnx_diarization" / "case-001"
    _valid_result(result, scenario)
    assert validate_result(result, expected_scenario_id=scenario)["valid"]
    summary = execute_queue(
        tier="smoke",
        pipelines=("sherpa_onnx_diarization",),
        benchmark_root=benchmark_root,
        generated_root=tmp_path / "generated-not-needed-for-reuse",
        result_root=result_root,
    )
    assert summary["reused"] == 1
    assert summary["failed"] == 0
    write_text_atomic(result / "predictions" / "segments.rttm", "corrupted\n")
    with pytest.raises((ValueError, ControlledDiarizationError)):
        validate_result(result, expected_scenario_id=scenario)


def test_analysis_writes_required_tables(tmp_path: Path) -> None:
    config = load_config()
    registry = load_pipeline_registry(config)
    benchmark = benchmark_id(config, "d" * 64)
    case = _case(benchmark)
    benchmark_root = tmp_path / "benchmark"
    (benchmark_root / "smoke").mkdir(parents=True)
    (benchmark_root / "smoke" / "case_manifest.jsonl").write_text(
        json.dumps(case) + "\n", encoding="utf-8"
    )
    (benchmark_root / "protocol_summary.json").write_text(
        json.dumps({"benchmark_id": benchmark}), encoding="utf-8"
    )
    scenario = scenario_identity(config, registry["sherpa_onnx_diarization"], case)
    result_root = tmp_path / "results"
    _valid_result(
        result_root / "smoke" / "sherpa_onnx_diarization" / "case-001", scenario
    )
    output = tmp_path / "analysis"
    manifest = analyze_results(
        pipelines=("sherpa_onnx_diarization",),
        tiers=("smoke",),
        benchmark_root=benchmark_root,
        result_root=result_root,
        output_root=output,
    )
    assert manifest["valid_results"] == 1
    for name in (
        "analysis_manifest.json",
        "overall_results.csv",
        "recording_results.csv",
        "factor_results.csv",
        "speaker_count_results.csv",
        "overlap_results.csv",
        "turn_cadence_results.csv",
        "fragmentation_results.csv",
        "merge_results.csv",
        "single_speaker_controls.csv",
        "reentry_results.csv",
        "resource_results.csv",
        "reliability_summary.csv",
        "report.md",
    ):
        assert (output / name).is_file()


def test_cli_is_discoverable() -> None:
    parser = build_parser()
    args = parser.parse_args(["diarization-benchmark", "plan"])
    assert args.controlled_diarization_command == "plan"
