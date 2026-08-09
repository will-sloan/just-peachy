"""Deterministic subprocess used to qualify Stage 4 without models or a GPU."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

import pyarrow as pa

from app.artifact_contracts.atomic import ScenarioArtifactStore
from app.artifact_contracts.registry import ARTIFACT_REGISTRY_VERSION, ArtifactRegistry
from app.resource_telemetry.context import REGISTRY_ENV


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-root", required=True, type=Path)
    parser.add_argument(
        "--behavior",
        required=True,
        choices=(
            "success",
            "success-warnings",
            "incomplete",
            "corrupt",
            "transient",
            "terminal",
            "oom",
            "sleep",
            "partial-transient",
        ),
    )
    parser.add_argument("--sleep-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)
    root = args.scenario_root.resolve()
    scenario = json.loads((root / "resolved_scenario.json").read_text(encoding="utf-8"))
    scenario_id = str(scenario["scenario_id"])
    scenario_hash = str(scenario["scenario_hash"])
    registry = ArtifactRegistry.load_version(
        os.environ.get(REGISTRY_ENV, ARTIFACT_REGISTRY_VERSION)
    )

    if args.behavior == "sleep":
        print("synthetic worker sleeping", flush=True)
        time.sleep(args.sleep_seconds)
        return 0
    if args.behavior == "transient":
        print("transient I/O: temporarily unavailable", flush=True)
        return 75
    if args.behavior == "terminal":
        print("configuration error: synthetic schema validation failure", flush=True)
        return 78
    if args.behavior == "oom":
        print("CUDA out of memory: synthetic qualification", flush=True)
        return 88
    if args.behavior == "partial-transient":
        store = ScenarioArtifactStore(root, scenario_id, registry=registry)
        store.publish_json(
            "metrics/summary.json",
            {
                "schema_version": "metrics-summary.v1",
                "scenario_id": scenario_id,
                "scenario_hash": scenario_hash,
                "counts": {
                    "selected_items": 0,
                    "successful_items": 0,
                    "failed_items": 0,
                    "diagnostics": 0,
                    "error_records": 0,
                },
                "metrics": {"partial": True},
            },
        )
        print("transient I/O after partial output", flush=True)
        return 75

    _publish_success(
        root,
        scenario,
        warnings=args.behavior == "success-warnings",
        registry=registry,
    )
    if args.behavior == "incomplete":
        (root / "report" / "scenario_report.md").unlink(missing_ok=True)
    elif args.behavior == "corrupt":
        (root / "metrics" / "summary.json").write_text("{truncated", encoding="utf-8")
    return 0


def _publish_success(
    root: Path,
    scenario: dict[str, object],
    *,
    warnings: bool,
    registry: ArtifactRegistry,
) -> None:
    scenario_id = str(scenario["scenario_id"])
    scenario_hash = str(scenario["scenario_hash"])
    data_slice = scenario.get("dataset_slice")
    selected = int(data_slice.get("row_count", 1)) if isinstance(data_slice, dict) else 1
    store = ScenarioArtifactStore(root, scenario_id, registry=registry)
    diagnostics = [
        {"recording_id": f"synthetic-{index}", "utt_id": f"utt-{index}"}
        for index in range(selected)
    ]
    store.publish_jsonl("predictions/diagnostics.jsonl", diagnostics)
    store.publish_parquet(
        "metrics/failures.parquet",
        pa.table(
            {
                "recording_id": pa.array([], type=pa.string()),
                "utt_id": pa.array([], type=pa.string()),
                "error_type": pa.array([], type=pa.string()),
                "message": pa.array([], type=pa.string()),
            }
        ),
    )
    errors_path = root / "logs" / "errors.jsonl"
    if not errors_path.exists():
        store.publish_jsonl("logs/errors.jsonl", [])
    error_count = _jsonl_count(errors_path)
    counts = {
        "selected_items": selected,
        "successful_items": selected,
        "failed_items": 0,
        "diagnostics": selected,
        "grouped_metrics": 0,
        "error_records": error_count,
    }
    metrics = {"synthetic_success": 1.0}
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
    store.publish_json(
        "report/scenario_report.json",
        {
            "schema_version": "scenario-report.v1",
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "completion_state": "complete",
            "counts": counts,
            "metrics": metrics,
        },
    )
    store.publish_text(
        "report/scenario_report.md",
        f"# Synthetic scenario {scenario_id}\n\nStage 4 subprocess qualification output.\n",
    )
    store.publish_json(
        "status.json",
        {
            "schema_version": "scenario-status.v1",
            "artifact_registry_version": registry.schema_version,
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "scenario_type": "synthetic_executor",
            "state": "successful",
            "counts": counts,
            "warnings": ["synthetic warning"] if warnings else [],
        },
    )


def _jsonl_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


if __name__ == "__main__":
    sys.exit(main())
