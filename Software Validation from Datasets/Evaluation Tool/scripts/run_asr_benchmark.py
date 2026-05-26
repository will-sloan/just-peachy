"""Run an ASR multi-model benchmark sweep."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.augmentation import build_augmentation_plan, expand_records_for_augmentation
from app.augmentation.processor import total_duration_sec
from app.dataset_registry.loader import load_dataset_selection, selection_records
from app.dataset_registry.registry import get_dataset
from app.inference_pipeline.benchmarking.asr_benchmark import (
    load_asr_sweep_config,
    run_asr_benchmark,
)
from app.utils.json_utils import write_jsonl
from app.utils.logging_utils import setup_run_logger
from app.utils.paths import find_project_root
from app.utils.run_artifacts import (
    read_yaml,
    relative_artifact_config,
    relative_artifact_records,
    write_yaml,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project_root = find_project_root(args.project_root)
    tool_root = project_root / "Evaluation Tool"
    sweep_path = (tool_root / args.sweep_config).resolve() if not args.sweep_config.is_absolute() else args.sweep_config
    sweep = read_yaml(sweep_path)
    dataset_key = args.dataset or str((sweep.get("defaults") or {}).get("dataset") or "cmu_arctic")
    max_recordings = args.max_recordings
    if max_recordings is None:
        max_recordings = int((sweep.get("defaults") or {}).get("max_recordings") or 1)
    run_id = args.run_id or "m8_asr_benchmark_smoke"
    runs_root = (args.runs_root or (tool_root / "runs" / "asr_benchmarks")).resolve()
    benchmark_root = runs_root / run_id
    logger = setup_run_logger(benchmark_root / "logs" / "benchmark.log")

    definition = get_dataset(dataset_key)
    selection = load_dataset_selection(
        project_root=project_root,
        definition=definition,
        subset_filters=None,
        max_recordings=max_recordings,
    )
    base_records = selection_records(selection.dataframe)
    augmentation_plan = build_augmentation_plan(
        project_root=project_root,
        mode="none",
        rir_path_values=[],
        noise_types=[],
        snr_values=[],
        preview_enabled=False,
        preview_recording_id=None,
        seed=1337,
    )
    records = expand_records_for_augmentation(base_records, augmentation_plan)
    base_run_config = {
        "command": "asr_benchmark",
        "project_root": str(project_root),
        "run_dir": str(benchmark_root),
        "dataset": {
            "key": definition.key,
            "name": definition.display_name,
            "dataset_id": definition.dataset_id,
            "normalized_metadata_dir": definition.normalized_metadata_dir.as_posix(),
        },
        "selection": {
            "max_recordings": max_recordings,
            "selected_source_recordings": len(base_records),
            "selected_recordings": len(records),
            "total_source_duration_sec": total_duration_sec(base_records),
            "total_evaluation_duration_sec": total_duration_sec(records),
        },
        "augmentation": {
            **augmentation_plan.to_jsonable(),
            "preview_count": 0,
        },
        "runner": {
            "name": "external-stub",
            "simulation_mode": None,
        },
        "prediction_contract": {
            "minimum_file": "predictions/utterances.jsonl",
            "optional_files": ["predictions/words.jsonl", "predictions/segments.rttm"],
        },
    }
    benchmark_root.mkdir(parents=True, exist_ok=True)
    write_yaml(
        benchmark_root / "benchmark_run_config.yaml",
        relative_artifact_config(
            base_run_config,
            artifact_root=benchmark_root,
            project_root=project_root,
        ),
    )
    write_jsonl(
        benchmark_root / "dataset_selection_records.jsonl",
        relative_artifact_records(records, artifact_root=benchmark_root, project_root=project_root),
    )

    model_configs = load_asr_sweep_config(sweep_path, tool_root=tool_root)
    result = run_asr_benchmark(
        records=records,
        model_configs=model_configs,
        run_id=run_id,
        output_root=runs_root,
        report_dir=tool_root / "reports" / "component_reports" / "asr",
        project_root=project_root,
        base_run_config=base_run_config,
        dataset_definition=definition,
        logger=logger,
    )
    print(f"Benchmark root: {result.benchmark_root}")
    print(f"Markdown report: {result.markdown_report_path}")
    print(f"CSV report: {result.csv_report_path}")
    print(f"Recommended ASR: {result.recommended_model_id or 'n/a'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ASR model benchmark sweep.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root. Defaults to auto-discovery.",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Dataset key. Defaults to sweep config or cmu_arctic.",
    )
    parser.add_argument(
        "--max-recordings",
        type=int,
        default=None,
        help="Limit selected recordings. Defaults to sweep config or 1.",
    )
    parser.add_argument(
        "--sweep-config",
        type=Path,
        default=Path("configs/sweeps/asr_models.yaml"),
        help="ASR sweep YAML path, absolute or Evaluation Tool relative.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Benchmark run id. Defaults to m8_asr_benchmark_smoke.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=None,
        help="Benchmark output root. Defaults to Evaluation Tool/runs/asr_benchmarks.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
