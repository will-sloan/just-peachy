"""Execute one frozen scenario through the existing evaluator lifecycle."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Mapping

import pandas as pd
import pyarrow as pa
import yaml

from app.artifact_contracts.atomic import ScenarioArtifactStore, file_sha256
from app.artifact_contracts.registry import (
    ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
    scenario_type_from_resolved,
)
from app.augmentation.config import AugmentationCondition, AugmentationPlan
from app.augmentation.processor import expand_records_for_augmentation
from app.benchmark_contracts.manifest_io import read_manifest
from app.benchmark_contracts.scenario import (
    pipeline_identity_from_resolution,
    validate_scenario,
)
from app.dataset_registry.registry import get_dataset
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.resolver import resolve_pipeline
from app.model_runner.configured import ConfiguredEvaluatorRunner
from app.plotting.plots import build_plots
from app.reporting.reporter import build_report
from app.scoring.scorer import score_run
from app.utils.json_utils import read_jsonl
from app.utils.logging_utils import setup_run_logger
from app.resource_telemetry.context import (
    REGISTRY_ENV,
    activate_recorder,
    recorder_from_environment,
    telemetry_span,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        execute_scenario(
            args.campaign_root.resolve(),
            args.scenario_id,
            args.project_root.resolve(),
            attempt=args.attempt,
        )
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f"configuration error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 78
    except MemoryError as exc:
        print(f"out of memory: {exc}", file=sys.stderr)
        return 88
    return 0


def execute_scenario(
    campaign_root: Path,
    scenario_id: str,
    project_root: Path,
    *,
    attempt: int,
) -> None:
    """Run configured inference, existing scoring/plots/report, then adapt artifacts."""

    registry = _artifact_registry_from_environment()
    recorder = recorder_from_environment()
    with activate_recorder(recorder):
        with telemetry_span("scenario_total", phase="total_scenario"):
            _execute_scenario_impl(
                campaign_root,
                scenario_id,
                project_root,
                attempt=attempt,
                registry=registry,
            )


def _execute_scenario_impl(
    campaign_root: Path,
    scenario_id: str,
    project_root: Path,
    *,
    attempt: int,
    registry: ArtifactRegistry,
) -> None:
    """Implementation body kept separate so telemetry activation is exception-safe."""

    scenario_root = campaign_root / "scenarios" / scenario_id
    scenario = json.loads(
        (scenario_root / "resolved_scenario.json").read_text(encoding="utf-8")
    )
    validate_scenario(scenario)
    if scenario["scenario_id"] != scenario_id:
        raise ValueError("scenario directory and identity differ")
    if scenario_type_from_resolved(scenario) != "asr":
        raise ValueError(
            "the Stage 4 evaluator adapter currently supports ASR scenarios; "
            "other scenario types require real component outputs"
        )
    work_dir = campaign_root / "audit" / "work" / scenario_id / f"attempt_{attempt:04d}"
    if work_dir.exists():
        raise ValueError(f"attempt workspace already exists: {work_dir}")
    for relative in ("predictions", "metrics", "plots", "report", "logs"):
        (work_dir / relative).mkdir(parents=True, exist_ok=True)
    logger = setup_run_logger(work_dir / "logs" / "evaluation.log")

    manifest_path = _campaign_manifest_path(campaign_root, scenario)
    records = _scenario_records(read_manifest(manifest_path), scenario, project_root)
    resolution = _resolve_and_verify_pipeline(project_root, scenario)
    condition_plan = _augmentation_plan(scenario)
    expanded = expand_records_for_augmentation(records, condition_plan)
    if len(expanded) != int(scenario["dataset_slice"]["row_count"]):
        raise ValueError(
            "resolved scenario row count differs from frozen manifest slice"
        )
    definition = get_dataset(str(scenario["dataset_slice"]["dataset"]))
    run_config: dict[str, object] = {
        "command": "campaign-scenario",
        "project_root": str(project_root),
        "run_dir": str(work_dir),
        "dataset": {
            "key": definition.key,
            "name": definition.display_name,
            "dataset_id": definition.dataset_id,
        },
        "selection": {"selected_recordings": len(expanded)},
        "augmentation": condition_plan.to_jsonable(),
        "runner": {
            "name": "configured",
            "pipeline_id": scenario["pipeline"]["pipeline_id"],
            "implicit_model_downloads_prohibited": True,
        },
    }
    runner = ConfiguredEvaluatorRunner(resolution)
    runner_result = runner.run_batch(
        expanded,
        work_dir / "predictions",
        run_config,
        logger,
    )
    with telemetry_span("scoring", phase="scenario_postprocess"):
        score_result = score_run(work_dir, definition, expanded, logger)
    with telemetry_span("plotting", phase="scenario_postprocess"):
        build_plots(work_dir, definition.key, logger)
    with telemetry_span("reporting", phase="scenario_postprocess"):
        build_report(work_dir, logger)
    failed_items = runner_result.failed_count + runner_result.skipped_count
    failure_rate = failed_items / len(expanded) if expanded else 1.0
    failure_policy = scenario.get("failure_policy")
    maximum_failure_rate = (
        float(failure_policy.get("max_missing_prediction_rate", 0.0))
        if isinstance(failure_policy, Mapping)
        else 0.0
    )
    policy_accepted = failure_rate <= maximum_failure_rate
    with telemetry_span("prediction_serialization", phase="scenario_postprocess"):
        _publish_final_artifacts(
            scenario_root,
            scenario,
            work_dir,
            runner_result=runner_result,
            aggregate_metrics=score_result.aggregate_metrics,
            records=expanded,
            completion_state="complete" if policy_accepted else "incomplete",
            registry=registry,
        )
    if not policy_accepted:
        raise ValueError(
            f"failure policy exceeded: item failure rate {failure_rate:.6f} "
            f"> {maximum_failure_rate:.6f}"
        )


def _campaign_manifest_path(
    campaign_root: Path,
    scenario: Mapping[str, object],
) -> Path:
    identity = scenario["benchmark_manifest"]
    name = Path(str(identity["path"])).name
    path = campaign_root / "benchmark_manifests" / name
    if not path.is_file():
        raise FileNotFoundError(path)
    if file_sha256(path) != identity["sha256"]:
        raise ValueError("campaign benchmark manifest hash mismatch")
    return path


def _scenario_records(
    rows: list[dict[str, object]],
    scenario: Mapping[str, object],
    project_root: Path,
) -> list[dict[str, object]]:
    data_slice = scenario["dataset_slice"]
    filters = data_slice["filters"]
    selected: list[dict[str, object]] = []
    for row in rows:
        if row.get("dataset") != data_slice["dataset"]:
            continue
        if (
            row.get("benchmark_tier") != scenario["tier"]
            or row.get("panel") != scenario["panel"]
        ):
            continue
        if any(
            row.get(key) != value for key, value in filters.items() if value is not None
        ):
            continue
        current = {key: value for key, value in row.items() if value is not None}
        relative = str(row["audio_path_project_relative"])
        audio_path = (project_root / relative).resolve()
        if not audio_path.is_file():
            raise FileNotFoundError(f"frozen source audio is missing: {relative}")
        current.update(
            {
                "audio_path_resolved": str(audio_path),
                "audio_exists": True,
                "dataset": row["dataset"],
                "dataset_id": row["dataset"],
                "speaker_label": row["speaker_id"],
            }
        )
        selected.append(current)
    selected.sort(
        key=lambda item: (
            str(item.get("selection_rank") or ""),
            str(item["recording_id"]),
            str(item["utt_id"]),
        )
    )
    expected = int(data_slice["row_count"])
    if len(selected) != expected:
        raise ValueError(
            f"frozen slice selected {len(selected)} rows; expected {expected}"
        )
    return selected


def _resolve_and_verify_pipeline(project_root: Path, scenario: Mapping[str, object]):
    pipeline = scenario["pipeline"]
    pipeline_id = str(pipeline["pipeline_id"])
    candidates: list[Path] = []
    inference_root = project_root / "Evaluation Tool" / "configs" / "inference"
    if not inference_root.is_dir():
        inference_root = Path(__file__).resolve().parents[2] / "configs" / "inference"
    for path in inference_root.rglob("*.yaml"):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(value, Mapping) and value.get("config_name") == pipeline_id:
            candidates.append(path)
    selected_hash = str(pipeline["selected_config_sha256"])
    candidates = [path for path in candidates if file_sha256(path) == selected_hash]
    if len(candidates) != 1:
        raise ValueError(
            f"pipeline {pipeline_id!r} selected hash resolved to {len(candidates)} source configs"
        )
    catalog = ComponentCatalog.load()
    source_resolution = resolve_pipeline(candidates[0], catalog=catalog)
    frozen_components = pipeline.get("components")
    if not isinstance(frozen_components, Mapping):
        raise ValueError("frozen pipeline has no component identities")
    component_overrides = {
        str(family): str(component["name"])
        for family, component in frozen_components.items()
        if isinstance(component, Mapping)
        and family in source_resolution.pipeline_config.components
        and source_resolution.pipeline_config.components[str(family)].name
        != str(component.get("name") or "")
    }
    resolution = resolve_pipeline(
        candidates[0],
        component_overrides=component_overrides,
        environment_profile=(
            str(pipeline["environment_profile"])
            if pipeline.get("environment_profile") is not None
            else None
        ),
        catalog=catalog,
    )
    observed = pipeline_identity_from_resolution(resolution)
    for field in (
        "pipeline_id",
        "selected_config_sha256",
        "resolved_config_sha256",
        "components",
        "models",
        "environment_profile",
    ):
        if field in pipeline and observed[field] != pipeline[field]:
            raise ValueError(
                f"current pipeline differs from frozen scenario field {field}"
            )
    return resolution


def _augmentation_plan(scenario: Mapping[str, object]) -> AugmentationPlan:
    condition = scenario["condition"]
    rir = condition.get("rir")
    rir_path = str(rir["relative_path"]) if isinstance(rir, Mapping) else None
    rir_label = str(rir["environment"]) if isinstance(rir, Mapping) else None
    resolved = AugmentationCondition(
        condition_id=str(condition["id"]),
        mode=str(condition["augmentation"]),
        rir_path=rir_path,
        rir_label=rir_label,
        noise_type=condition.get("noise_type"),
        snr_db=float(condition["snr_db"])
        if condition.get("snr_db") is not None
        else None,
    )
    return AugmentationPlan(
        mode=str(condition["augmentation"]),
        conditions=(resolved,),
        seed=int(scenario["seed"]),
    )


def _publish_final_artifacts(
    scenario_root: Path,
    scenario: Mapping[str, object],
    work_dir: Path,
    *,
    runner_result,
    aggregate_metrics: Mapping[str, object],
    records: list[dict[str, object]],
    completion_state: str,
    registry: ArtifactRegistry,
) -> None:
    scenario_id = str(scenario["scenario_id"])
    scenario_hash = str(scenario["scenario_hash"])
    store = ScenarioArtifactStore(scenario_root, scenario_id, registry=registry)
    predictions = read_jsonl(work_dir / "predictions" / "utterances.jsonl")
    diagnostics = read_jsonl(work_dir / "predictions" / "diagnostics.jsonl")
    raw_failures = read_jsonl(work_dir / "predictions" / "failures.jsonl")
    failures = [
        {
            "recording_id": str(row.get("recording_id") or ""),
            "utt_id": str(row.get("utt_id") or row.get("recording_id") or ""),
            "error_type": str(
                row.get("error_type") or row.get("status") or "ItemFailure"
            ),
            "message": str(row.get("message") or "inference item failed"),
        }
        for row in raw_failures
    ]
    outcome_keys = {
        (str(row.get("recording_id") or ""), str(row.get("utt_id") or ""))
        for row in [*predictions, *failures]
    }
    for record in records:
        key = (str(record["recording_id"]), str(record["utt_id"]))
        if key in outcome_keys:
            continue
        failures.append(
            {
                "recording_id": str(record["recording_id"]),
                "utt_id": str(record["utt_id"]),
                "error_type": "MissingPipelineOutput",
                "message": "pipeline returned no standardized prediction",
            }
        )
    item_frame = pd.read_csv(work_dir / "metrics" / "per_recording_metrics.csv")
    item_frame["recording_id"] = item_frame["recording_id"].fillna("").astype(str)
    item_frame["utt_id"] = item_frame["utt_id"].fillna("").astype(str)
    item_table = pa.Table.from_pandas(item_frame, preserve_index=False)
    grouped_rows = [
        {
            "group_key": "aggregate",
            "group_value": "all",
            "metric_name": str(key),
            "metric_value": float(value),
        }
        for key, value in sorted(aggregate_metrics.items())
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    grouped_table = pa.table(
        {
            "group_key": pa.array(
                [row["group_key"] for row in grouped_rows], pa.string()
            ),
            "group_value": pa.array(
                [row["group_value"] for row in grouped_rows], pa.string()
            ),
            "metric_name": pa.array(
                [row["metric_name"] for row in grouped_rows], pa.string()
            ),
            "metric_value": pa.array(
                [row["metric_value"] for row in grouped_rows], pa.float64()
            ),
        }
    )
    failure_table = pa.table(
        {
            "recording_id": pa.array(
                [row["recording_id"] for row in failures], pa.string()
            ),
            "utt_id": pa.array([row["utt_id"] for row in failures], pa.string()),
            "error_type": pa.array(
                [row["error_type"] for row in failures], pa.string()
            ),
            "message": pa.array([row["message"] for row in failures], pa.string()),
        }
    )
    errors_path = scenario_root / "logs" / "errors.jsonl"
    if not errors_path.exists():
        store.publish_jsonl("logs/errors.jsonl", [])
    errors = _jsonl_count(errors_path)
    counts = {
        "selected_items": len(records),
        "successful_items": len(predictions),
        "failed_items": len(failures),
        "predictions": len(predictions),
        "diagnostics": len(diagnostics),
        "item_metrics": item_table.num_rows,
        "grouped_metrics": grouped_table.num_rows,
        "error_records": errors,
    }
    if counts["successful_items"] + counts["failed_items"] != counts["selected_items"]:
        raise ValueError("runner outcome counts do not reconcile")
    store.publish_jsonl("predictions/utterances.jsonl", predictions)
    store.publish_jsonl("predictions/diagnostics.jsonl", diagnostics)
    store.publish_parquet("metrics/item_metrics.parquet", item_table)
    store.publish_parquet("metrics/grouped_metrics.parquet", grouped_table)
    store.publish_parquet("metrics/failures.parquet", failure_table)
    metrics = _json_safe_metrics(aggregate_metrics)
    store.publish_json(
        "metrics/summary.json",
        {
            "schema_version": "metrics-summary.v1",
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "counts": counts,
            "metrics": metrics,
        },
    )
    warnings: list[str] = []
    warning_path = work_dir / "inference" / "configuration_warnings.json"
    if warning_path.is_file():
        warning_payload = json.loads(warning_path.read_text(encoding="utf-8"))
        warnings = [str(item) for item in warning_payload.get("warnings", [])]
    store.publish_json(
        "status.json",
        {
            "schema_version": "scenario-status.v1",
            "artifact_registry_version": registry.schema_version,
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "scenario_type": "asr",
            "state": "successful" if completion_state == "complete" else "failed",
            "counts": counts,
            "warnings": warnings,
            "runner": {
                "attempted_count": runner_result.attempted_count,
                "written_count": runner_result.written_count,
                "failed_count": runner_result.failed_count,
            },
        },
    )
    store.publish_json(
        "report/scenario_report.json",
        {
            "schema_version": "scenario-report.v1",
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "completion_state": completion_state,
            "counts": counts,
            "metrics": metrics,
        },
    )
    ordinary_report = (work_dir / "report" / "report.md").read_text(encoding="utf-8")
    store.publish_text(
        "report/scenario_report.md",
        f"# Scenario {scenario_id}\n\n{ordinary_report}",
    )
    rttm_source = work_dir / "predictions" / "segments.rttm"
    if rttm_source.is_file():
        store.publish_text(
            "predictions/segments.rttm", rttm_source.read_text(encoding="utf-8")
        )


def _json_safe_metrics(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in value.items():
        if item is None or isinstance(item, (str, int, float, bool)):
            result[str(key)] = item
    return result


def _jsonl_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def _artifact_registry_from_environment() -> ArtifactRegistry:
    version = os.environ.get(REGISTRY_ENV, ARTIFACT_REGISTRY_VERSION)
    return ArtifactRegistry.load_version(version)


if __name__ == "__main__":
    sys.exit(main())
