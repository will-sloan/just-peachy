"""Registry-driven reuse of validated scenario metric artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from app.campaign_exchange.common import atomic_write_bytes, atomic_write_json

from .contracts import AnalysisContractError, metric_definitions


METRIC_VALUE_SCHEMA_VERSION = "campaign-metric-values.v1"

METRIC_VALUE_SCHEMA = pa.schema(
    [
        pa.field("schema_version", pa.string(), nullable=False),
        pa.field("scenario_id", pa.string(), nullable=False),
        pa.field("scenario_hash", pa.string(), nullable=False),
        pa.field("scenario_type", pa.string(), nullable=False),
        pa.field("dataset", pa.string()),
        pa.field("panel", pa.string()),
        pa.field("tier", pa.string()),
        pa.field("condition_id", pa.string()),
        pa.field("metric_name", pa.string(), nullable=False),
        pa.field("metric_version", pa.string(), nullable=False),
        pa.field("value", pa.float64()),
        pa.field("supported", pa.bool_(), nullable=False),
        pa.field("availability_reason", pa.string(), nullable=False),
        pa.field("source_artifact", pa.string()),
        pa.field("source_field", pa.string()),
        pa.field("interpretation_anchor", pa.string(), nullable=False),
    ]
)


def extract_campaign_metrics(
    campaign_root: Path,
    analysis_manifest: Mapping[str, object],
    metric_registry: Mapping[str, object],
    *,
    output_root: Path,
) -> list[dict[str, object]]:
    """Extract only registered, semantically eligible scenario summary metrics."""

    campaign = campaign_root.resolve()
    definitions = metric_definitions(metric_registry)
    rows: list[dict[str, object]] = []
    for scenario in analysis_manifest["scenario_index"]:
        if not isinstance(scenario, Mapping):
            raise AnalysisContractError("analysis scenario row must be a mapping")
        sources = _metric_sources(campaign, scenario)
        for definition in definitions:
            rows.append(_metric_row(scenario, definition, sources))

    table = pa.Table.from_pylist(rows, schema=METRIC_VALUE_SCHEMA)
    metadata = dict(table.schema.metadata or {})
    metadata[b"artifact_schema_version"] = METRIC_VALUE_SCHEMA_VERSION.encode()
    _write_parquet(output_root / "tables" / "scenario_metric_values.parquet", table.replace_schema_metadata(metadata))
    frame = table.to_pandas()
    atomic_write_bytes(
        output_root / "tables" / "scenario_metric_values.csv",
        frame.to_csv(index=False, lineterminator="\n").encode("utf-8"),
    )
    availability = _availability_summary(rows)
    atomic_write_json(output_root / "metric_availability.json", availability)
    return rows


def collect_failure_categories(
    campaign_root: Path,
    analysis_manifest: Mapping[str, object],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    campaign = campaign_root.resolve()
    for scenario in analysis_manifest["scenario_index"]:
        if not isinstance(scenario, Mapping):
            continue
        status = str(scenario.get("analysis_status") or "unknown")
        if status != "included":
            result.append(
                {
                    "scenario_id": scenario.get("scenario_id"),
                    "category": status,
                    "count": 1,
                    "source": "campaign_result_index",
                }
            )
            continue
        artifacts = scenario.get("artifact_paths")
        if not isinstance(artifacts, Mapping) or not artifacts.get("failures"):
            continue
        path = campaign / str(artifacts["failures"])
        try:
            frame = pq.read_table(path).to_pandas()
        except Exception as exc:
            result.append(
                {
                    "scenario_id": scenario.get("scenario_id"),
                    "category": "unreadable_failure_artifact",
                    "count": 1,
                    "source": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if frame.empty:
            continue
        category_column = next(
            (
                name
                for name in ("error_type", "category", "failure_type", "status", "stage")
                if name in frame.columns
            ),
            None,
        )
        if category_column is None:
            result.append(
                {
                    "scenario_id": scenario.get("scenario_id"),
                    "category": "uncategorized_failure",
                    "count": len(frame),
                    "source": str(artifacts["failures"]),
                }
            )
            continue
        counts = frame[category_column].fillna("Unknown").astype(str).value_counts()
        result.extend(
            {
                "scenario_id": scenario.get("scenario_id"),
                "category": category,
                "count": int(count),
                "source": str(artifacts["failures"]),
            }
            for category, count in sorted(counts.items())
        )
    return result


def metric_lookup(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    for row in rows:
        value = row.get("value")
        if row.get("supported") and _finite(value):
            result[(str(row["scenario_id"]), str(row["metric_name"]))] = float(value)
    return result


def _metric_row(
    scenario: Mapping[str, object],
    definition: Mapping[str, object],
    sources: Mapping[str, object],
) -> dict[str, object]:
    name = str(definition["name"])
    scenario_type = str(scenario.get("scenario_type") or "unknown")
    supported_types = {str(item) for item in definition.get("scenario_types", [])}
    value: float | None = None
    source_field: str | None = None
    source_artifact: str | None = None

    if name == "scenario_completion":
        value = 1.0 if scenario.get("validation_complete") and scenario.get("analysis_status") == "included" else 0.0
        reason = "derived from the existing completion validator"
        supported = True
        source_field = "analysis.validation_complete"
        source_artifact = "analysis/campaign_result_index.json"
    elif scenario.get("analysis_status") != "included":
        supported = False
        reason = f"scenario is {scenario.get('analysis_status')}; no scientific value was imputed"
    elif scenario_type not in supported_types and "*" not in supported_types:
        supported = False
        reason = f"metric is not registered for scenario type {scenario_type}"
    else:
        for path in definition.get("source_paths", []):
            raw = _lookup(sources, str(path))
            if _finite(raw):
                value = float(raw)
                source_field = str(path)
                source_artifact = _source_artifact_for_path(str(path), scenario)
                break
        supported = value is not None
        reason = (
            "registered source field present"
            if supported
            else "none of the registered source fields were present with a finite value"
        )

    return {
        "schema_version": METRIC_VALUE_SCHEMA_VERSION,
        "scenario_id": str(scenario["scenario_id"]),
        "scenario_hash": str(scenario["scenario_hash"]),
        "scenario_type": scenario_type,
        "dataset": _optional_text(scenario.get("dataset")),
        "panel": _optional_text(scenario.get("panel")),
        "tier": _optional_text(scenario.get("tier")),
        "condition_id": _optional_text(scenario.get("condition_id")),
        "metric_name": name,
        "metric_version": str(definition["version"]),
        "value": value,
        "supported": supported,
        "availability_reason": reason,
        "source_artifact": source_artifact,
        "source_field": source_field,
        "interpretation_anchor": str(definition["interpretation_anchor"]),
    }


def _metric_sources(campaign: Path, scenario: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "analysis": dict(scenario),
        "derived": {},
    }
    artifacts = scenario.get("artifact_paths")
    if not isinstance(artifacts, Mapping):
        return result
    for key in ("metrics_summary", "resource_summary", "scenario_report"):
        relative = artifacts.get(key)
        if not relative:
            continue
        try:
            value = json.loads((campaign / str(relative)).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, Mapping):
            result[key] = dict(value)
    summary = result.get("metrics_summary")
    if isinstance(summary, Mapping):
        counts = summary.get("counts")
        if isinstance(counts, Mapping):
            selected = _number(counts.get("selected_items"))
            failed = _number(counts.get("failed_items"))
            if selected and selected > 0 and failed is not None:
                result["derived"] = {"failure_rate": failed / selected}
    return result


def _lookup(value: object, dotted: str) -> object:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _source_artifact_for_path(path: str, scenario: Mapping[str, object]) -> str | None:
    prefix = path.split(".", 1)[0]
    if prefix == "analysis":
        return "analysis/campaign_result_index.json"
    artifacts = scenario.get("artifact_paths")
    if not isinstance(artifacts, Mapping):
        return None
    return _optional_text(artifacts.get(prefix))


def _availability_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_metric: dict[str, dict[str, int]] = {}
    for row in rows:
        counts = by_metric.setdefault(str(row["metric_name"]), {"supported": 0, "unavailable": 0})
        counts["supported" if row.get("supported") else "unavailable"] += 1
    return {
        "schema_version": "campaign-metric-availability.v1",
        "policy": "unsupported metrics remain absent/null with an explicit reason",
        "metrics": [
            {"metric_name": key, **by_metric[key]} for key in sorted(by_metric)
        ],
    }


def _write_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, version="2.6", compression="NONE")
    atomic_write_bytes(path, sink.getvalue().to_pybytes())


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _number(value: object) -> float | None:
    return float(value) if _finite(value) else None


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)
