from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.inference_pipeline.benchmarking.asr_benchmark import (
    ASRModelConfig,
    _missing_availability,
    load_asr_sweep_config,
    run_asr_benchmark,
)
from app.inference_pipeline.metrics.asr_metrics import (
    aggregate_cer,
    aggregate_wer,
    composite_score,
    select_qualitative_examples,
    prediction_examples,
)
from app.prediction_io.jsonl import read_utterance_predictions


TOOL_ROOT = Path(__file__).resolve().parents[2]


def records(tmp_path: Path) -> list[dict[str, object]]:
    return [
        {
            "recording_id": "rec-001",
            "utt_id": "utt-001",
            "audio_path_resolved": str(tmp_path / "one.wav"),
            "inference_audio_path": str(tmp_path / "one.wav"),
            "start_sec": 0.0,
            "end_sec": 1.0,
            "reference_text": "hello world",
        },
        {
            "recording_id": "rec-002",
            "utt_id": "utt-002",
            "audio_path_resolved": str(tmp_path / "two.wav"),
            "inference_audio_path": str(tmp_path / "two.wav"),
            "start_sec": 1.0,
            "end_sec": 2.0,
            "reference_text": "repeat word",
        },
    ]


def base_run_config(tmp_path: Path) -> dict[str, object]:
    return {
        "project_root": str(tmp_path),
        "run_dir": str(tmp_path / "benchmark"),
        "augmentation": {
            "mode": "none",
            "conditions": [{"condition_id": "clean", "mode": "none"}],
        },
        "runner": {"name": "external-stub"},
    }


def model_configs() -> list[ASRModelConfig]:
    return [
        ASRModelConfig.from_mapping(
            {
                "id": "no_op_empty",
                "label": "No-op empty",
                "component": {
                    "name": "no_op_asr",
                    "enabled": True,
                    "params": {"transcript": ""},
                },
            }
        ),
        ASRModelConfig.from_mapping(
            {
                "id": "fixed_repeat",
                "label": "Fixed repeat",
                "component": {
                    "name": "fixed_asr",
                    "enabled": True,
                    "params": {"transcript": "hello hello hello"},
                },
            }
        ),
        ASRModelConfig.from_mapping(
            {
                "id": "unavailable_optional",
                "label": "Unavailable optional",
                "availability": {
                    "requires_package": "definitely_missing_asr_package_for_test",
                },
                "component": {
                    "name": "fixed_asr",
                    "enabled": True,
                    "params": {"transcript": "should not run"},
                },
            }
        ),
    ]


def run_benchmark(tmp_path: Path):
    return run_asr_benchmark(
        records=records(tmp_path),
        model_configs=model_configs(),
        run_id="unit",
        output_root=tmp_path / "runs",
        report_dir=tmp_path / "reports",
        project_root=tmp_path,
        base_run_config=base_run_config(tmp_path),
    )


def test_benchmark_runner_uses_same_records_and_preserves_prediction_contract(tmp_path: Path) -> None:
    result = run_benchmark(tmp_path)
    ran = {model.model_id: model for model in result.model_results if model.status == "ran"}

    assert set(ran) == {"no_op_empty", "fixed_repeat"}
    for model in ran.values():
        assert model.predictions_path is not None
        rows = read_utterance_predictions(model.predictions_path)
        assert [(row["recording_id"], row["utt_id"]) for row in rows] == [
            ("rec-001", "utt-001"),
            ("rec-002", "utt-002"),
        ]
        assert [(row["start_sec"], row["end_sec"]) for row in rows] == [
            (0.0, 1.0),
            (1.0, 2.0),
        ]


def test_each_model_gets_own_output_directory_and_config_snapshot(tmp_path: Path) -> None:
    result = run_benchmark(tmp_path)

    run_dirs = {model.run_dir for model in result.model_results}
    assert len(run_dirs) == 3
    for model in result.model_results:
        assert model.config_snapshot_path is not None
        assert model.config_snapshot_path.exists()
        assert model.config_snapshot_path.parent == model.run_dir


def test_unavailable_model_is_skipped_without_failing_benchmark(tmp_path: Path) -> None:
    result = run_benchmark(tmp_path)
    skipped = [model for model in result.model_results if model.model_id == "unavailable_optional"][0]

    assert skipped.status == "skipped"
    assert "missing python package" in str(skipped.skip_reason)
    assert result.recommended_model_id in {"no_op_empty", "fixed_repeat"}


def test_comparison_reports_are_written_with_aggregate_rows(tmp_path: Path) -> None:
    result = run_benchmark(tmp_path)

    assert result.markdown_report_path.exists()
    assert result.csv_report_path.exists()
    markdown = result.markdown_report_path.read_text(encoding="utf-8")
    assert "M8 - ASR Multi-Model Benchmark and Comparison Report" in markdown
    assert "Recommended default ASR" in markdown
    with result.csv_report_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["model_id"] for row in rows] == [
        "no_op_empty",
        "fixed_repeat",
        "unavailable_optional",
    ]
    assert rows[0]["composite_score"] != ""


def test_qualitative_examples_and_composite_score_are_deterministic(tmp_path: Path) -> None:
    prediction_rows = [
        {"recording_id": "rec-001", "utt_id": "utt-001", "text": "hello world"},
        {"recording_id": "rec-002", "utt_id": "utt-002", "text": "repeat repeat repeat"},
    ]
    examples = prediction_examples(records(tmp_path), prediction_rows)
    selected = select_qualitative_examples(examples)

    assert selected["best"] is not None
    assert selected["best"].recording_id == "rec-001"
    assert selected["high_stutter"] is not None
    assert selected["high_stutter"].recording_id == "rec-002"
    assert composite_score(
        wer=0.25,
        realtime_factor=0.5,
        failure_rate_value=0.0,
        memory_mb=None,
    ) == pytest.approx(75.4167)


def test_reference_metrics_are_available_without_dataset_scorer(tmp_path: Path) -> None:
    prediction_rows = [
        {"recording_id": "rec-001", "utt_id": "utt-001", "text": "hello world"},
        {"recording_id": "rec-002", "utt_id": "utt-002", "text": ""},
    ]

    assert aggregate_wer(records(tmp_path), prediction_rows) == pytest.approx(2 / 4)
    assert aggregate_cer(records(tmp_path), prediction_rows) is not None


def test_sweep_config_can_drive_rerun_without_code_edits(tmp_path: Path) -> None:
    sweep_path = tmp_path / "asr_models.yaml"
    sweep_path.write_text(
        """
models:
  - id: fixed_from_yaml
    label: Fixed from YAML
    component:
      name: fixed_asr
      enabled: true
      params:
        transcript: yaml transcript
  - id: skipped_from_yaml
    availability:
      requires_package: definitely_missing_asr_package_for_test
    component:
      name: fixed_asr
      enabled: true
      params:
        transcript: skipped
""",
        encoding="utf-8",
    )

    configs = load_asr_sweep_config(sweep_path, tool_root=TOOL_ROOT)
    result = run_asr_benchmark(
        records=records(tmp_path),
        model_configs=configs,
        run_id="yaml",
        output_root=tmp_path / "runs",
        report_dir=tmp_path / "reports",
        project_root=tmp_path,
        base_run_config=base_run_config(tmp_path),
    )

    assert [model.model_id for model in result.model_results] == [
        "fixed_from_yaml",
        "skipped_from_yaml",
    ]
    assert result.model_results[0].status == "ran"
    assert result.model_results[1].status == "skipped"


def test_default_sweep_config_loads() -> None:
    configs = load_asr_sweep_config(
        TOOL_ROOT / "configs" / "sweeps" / "asr_models.yaml",
        tool_root=TOOL_ROOT,
    )

    assert [config.model_id for config in configs] == [
        "no_op_empty",
        "fixed_dummy",
        "whisper_tiny",
        "whisper_base",
        "whisper_small",
        "faster_whisper",
        "sherpa_onnx",
        "vosk",
        "wenet",
    ]
    assert configs[2].availability["requires_package"] == "whisper"
    assert configs[3].availability["requires_package"] == "whisper"
    assert configs[4].availability["requires_package"] == "whisper"
    assert configs[5].availability["requires_package"] == "faster_whisper"
    assert configs[6].availability["requires_package"] == "sherpa_onnx"
    assert configs[7].availability["requires_package"] == "vosk"
    assert configs[8].availability["requires_package"] == "wenet"


def test_availability_accepts_multiple_assets_from_repository_root(tmp_path: Path) -> None:
    project_root = tmp_path / "Software Validation from Datasets"
    project_root.mkdir()
    asset_root = tmp_path / "models" / "cache" / "sherpa_onnx" / "asr"
    asset_root.mkdir(parents=True)
    for filename in ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"):
        (asset_root / filename).touch()

    missing = _missing_availability(
        {
            "requires_files": [
                f"models/cache/sherpa_onnx/asr/{filename}"
                for filename in ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
            ]
        },
        project_root=project_root,
    )

    assert missing == []
