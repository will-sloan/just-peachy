from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[2]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.prediction_io.schema import UTTERANCE_REQUIRED_FIELDS
from scripts.run_all_dataset_validation import (
    FAILURE_ASR,
    FAILURE_DATA,
    MILESTONE_DATASET_KEYS,
    STATUS_FAILED,
    STATUS_MISSING_ARTIFACT,
    ValidationResult,
    aggregate_run_folder,
    build_evaluation_command,
    classify_failure_mode,
    create_fixture_run_folders,
    dataset_rollups,
    load_validation_sweep_config,
    main,
    write_validation_report,
)


def test_smoke_sweep_config_parses_and_includes_all_six_datasets() -> None:
    sweep = load_validation_sweep_config(TOOL_ROOT / "configs" / "sweeps" / "all_datasets_smoke.yaml")

    assert sweep.sweep_name == "all_datasets_smoke"
    assert {job.dataset for job in sweep.jobs} == set(MILESTONE_DATASET_KEYS)
    assert len(sweep.jobs) == 6
    assert all(job.max_recordings == 1 for job in sweep.jobs)


def test_robustness_sweep_has_augmentation_and_native_condition_coverage() -> None:
    sweep = load_validation_sweep_config(TOOL_ROOT / "configs" / "sweeps" / "all_datasets_robustness.yaml")

    augmented = [job for job in sweep.jobs if job.augmentation_mode != "none"]
    native = [job for job in sweep.jobs if job.native_condition]

    assert {job.dataset for job in sweep.jobs} == set(MILESTONE_DATASET_KEYS)
    assert {job.dataset for job in augmented} >= {"cmu_arctic", "librispeech", "hifitts"}
    assert {job.dataset for job in native} >= {"ami", "voices", "chime6"}
    assert {job.augmentation.get("snr_db") for job in augmented} >= {10, 20}


def test_fixture_aggregation_groups_by_dataset_and_condition(tmp_path: Path) -> None:
    sweep = load_validation_sweep_config(TOOL_ROOT / "configs" / "sweeps" / "all_datasets_smoke.yaml")
    run_dirs = create_fixture_run_folders(tmp_path / "runs", run_id="unit_m16", jobs=sweep.jobs)

    summaries = [
        aggregate_run_folder(run_dir, job=job, run_id="unit_m16")
        for run_dir, job in zip(run_dirs, sweep.jobs, strict=True)
    ]
    result = ValidationResult(
        run_id="unit_m16",
        started_at="2026-06-02T00:00:00+00:00",
        wall_duration_sec=1.0,
        sweep=sweep,
        runs=tuple(summaries),
        dry_run_fixtures=True,
    )
    rollups = dataset_rollups(result)

    assert len({summary.run_dir for summary in summaries}) == 6
    assert all(summary.group_metrics["augmentation_condition_id"] for summary in summaries)
    assert {row["dataset"] for row in rollups} == set(MILESTONE_DATASET_KEYS)
    assert all(row["attempted_runs"] == 1 for row in rollups)
    assert all(row["missing_prediction_rate"] == 0.0 for row in rollups)


def test_missing_failed_timeout_classification() -> None:
    assert classify_failure_mode(STATUS_MISSING_ARTIFACT, {}, "missing dataset audio") == FAILURE_DATA
    assert classify_failure_mode(STATUS_FAILED, {}, "command returned 2") == "timeout/crash"
    assert classify_failure_mode("succeeded", {"missing_prediction_rate": 0.75}, None) == FAILURE_ASR


def test_validation_report_has_dataset_sections_and_cross_dataset_table(tmp_path: Path) -> None:
    sweep = load_validation_sweep_config(TOOL_ROOT / "configs" / "sweeps" / "all_datasets_smoke.yaml")
    run_dirs = create_fixture_run_folders(tmp_path / "runs", run_id="unit_report", jobs=sweep.jobs)
    summaries = tuple(
        aggregate_run_folder(run_dir, job=job, run_id="unit_report")
        for run_dir, job in zip(run_dirs, sweep.jobs, strict=True)
    )
    result = ValidationResult(
        run_id="unit_report",
        started_at="2026-06-02T00:00:00+00:00",
        wall_duration_sec=1.0,
        sweep=sweep,
        runs=summaries,
        dry_run_fixtures=True,
    )
    report_path = write_validation_report(
        tmp_path / "reports" / "validation" / "all_dataset_validation_unit_report.md",
        result,
        test_commands=["python -m pytest tests/inference_pipeline/test_all_dataset_validation.py"],
        smoke_commands=["python scripts/run_all_dataset_validation.py --dry-run-fixtures"],
    )

    text = report_path.read_text(encoding="utf-8")
    assert "## Cross-Dataset Comparison" in text
    for key in MILESTONE_DATASET_KEYS:
        assert f"(`{key}`)" in text
    assert report_path.with_suffix(".json").exists()
    assert report_path.with_suffix(".csv").exists()


def test_dry_run_main_creates_report_outputs_and_run_folders(tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "all_dataset_validation_unit_cli.md"
    exit_code = main(
        [
            "--run-id",
            "unit_cli",
            "--sweep-config",
            str(TOOL_ROOT / "configs" / "sweeps" / "all_datasets_smoke.yaml"),
            "--output-root",
            str(tmp_path / "runs"),
            "--report-path",
            str(report_path),
            "--dry-run-fixtures",
        ]
    )

    assert exit_code == 0
    assert report_path.exists()
    payload = json.loads(report_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert len(payload["runs"]) == 6
    assert all(Path(run["run_dir"]).name.startswith("unit_cli_") for run in payload["runs"])


def test_real_command_builder_preserves_existing_runner_contract() -> None:
    sweep = load_validation_sweep_config(TOOL_ROOT / "configs" / "sweeps" / "all_datasets_smoke.yaml")
    command = build_evaluation_command(
        sweep.jobs[0],
        project_root=TOOL_ROOT.parent,
        runs_root=TOOL_ROOT / "runs" / "unit",
    )

    assert "app.cli.main" in command
    assert "full" in command
    assert "--dataset" in command
    assert "--runs-root" in command
    assert UTTERANCE_REQUIRED_FIELDS == (
        "recording_id",
        "utt_id",
        "start_sec",
        "end_sec",
        "speaker_label",
        "text",
    )
