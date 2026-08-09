"""Versioned Stage 5 telemetry schemas and summary helpers."""

from __future__ import annotations

import json
import math
from typing import Iterable, Mapping

import pyarrow as pa


RESOURCE_USAGE_SCHEMA_VERSION = "resource-usage.v2"
COMPONENT_SPANS_SCHEMA_VERSION = "component-spans.v1"
RESOURCE_SUMMARY_SCHEMA_VERSION = "resource-summary.v1"
RESOURCE_AVAILABILITY_SCHEMA_VERSION = "resource-availability.v1"


RESOURCE_SAMPLE_SCHEMA = pa.schema(
    [
        pa.field("timestamp_utc", pa.string(), nullable=False),
        pa.field("monotonic_ns", pa.int64(), nullable=False),
        pa.field("elapsed_sec", pa.float64(), nullable=False),
        pa.field("campaign_id", pa.string(), nullable=False),
        pa.field("scenario_id", pa.string(), nullable=False),
        pa.field("attempt", pa.int64(), nullable=False),
        pa.field("worker_id", pa.string(), nullable=False),
        pa.field("host", pa.string(), nullable=False),
        pa.field("root_pid", pa.int64(), nullable=False),
        pa.field("process_tree_pids", pa.string(), nullable=False),
        pa.field("active_component", pa.string()),
        pa.field("process_cpu_percent", pa.float64()),
        pa.field("system_cpu_percent", pa.float64()),
        pa.field("process_rss_bytes", pa.int64()),
        pa.field("process_vms_bytes", pa.int64()),
        pa.field("system_ram_total_bytes", pa.int64()),
        pa.field("system_ram_available_bytes", pa.int64()),
        pa.field("system_ram_used_bytes", pa.int64()),
        pa.field("system_ram_percent", pa.float64()),
        pa.field("process_disk_read_bytes", pa.int64()),
        pa.field("process_disk_write_bytes", pa.int64()),
        pa.field("system_disk_read_bytes", pa.int64()),
        pa.field("system_disk_write_bytes", pa.int64()),
        pa.field("disk_free_bytes", pa.int64()),
        pa.field("gpu_index", pa.string()),
        pa.field("gpu_uuid", pa.string()),
        pa.field("gpu_utilization_percent", pa.float64()),
        pa.field("gpu_memory_utilization_percent", pa.float64()),
        pa.field("gpu_vram_bytes", pa.int64()),
        pa.field("gpu_peak_vram_bytes", pa.int64()),
        pa.field("gpu_total_vram_bytes", pa.int64()),
        pa.field("gpu_temperature_c", pa.float64()),
        pa.field("gpu_power_w", pa.float64()),
        pa.field("gpu_power_limit_w", pa.float64()),
        pa.field("gpu_graphics_clock_mhz", pa.float64()),
        pa.field("gpu_memory_clock_mhz", pa.float64()),
        pa.field("gpu_throttling_reasons", pa.string()),
        pa.field("process_availability_reason", pa.string()),
        pa.field("gpu_availability_reason", pa.string()),
        pa.field("sampling_gap", pa.bool_(), nullable=False),
    ]
)

RESOURCE_METRIC_FIELDS = tuple(
    field.name
    for field in RESOURCE_SAMPLE_SCHEMA
    if pa.types.is_integer(field.type) or pa.types.is_floating(field.type)
    if field.name not in {"monotonic_ns", "elapsed_sec", "attempt", "root_pid"}
)


def resource_table(rows: Iterable[Mapping[str, object]]) -> pa.Table:
    """Build the fixed typed telemetry sample table."""

    materialized = []
    for row in rows:
        normalized = dict(row)
        pids = normalized.get("process_tree_pids", [])
        if not isinstance(pids, str):
            normalized["process_tree_pids"] = json.dumps(
                [int(value) for value in pids], separators=(",", ":")
            )
        materialized.append(normalized)
    return pa.Table.from_pylist(materialized, schema=RESOURCE_SAMPLE_SCHEMA)


def percentile(values: Iterable[float | int | None], quantile: float) -> float | None:
    """Return a deterministic linearly interpolated percentile."""

    clean = sorted(
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    )
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * min(1.0, max(0.0, float(quantile)))
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return clean[lower]
    fraction = position - lower
    return clean[lower] + (clean[upper] - clean[lower]) * fraction


def metric_summary(values: Iterable[float | int | None]) -> dict[str, object]:
    """Summarize one sampled metric without inventing unsupported values."""

    clean = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    return {
        "count": len(clean),
        "min": min(clean) if clean else None,
        "mean": sum(clean) / len(clean) if clean else None,
        "p50": percentile(clean, 0.50),
        "p95": percentile(clean, 0.95),
        "p99": percentile(clean, 0.99),
        "max": max(clean) if clean else None,
    }
