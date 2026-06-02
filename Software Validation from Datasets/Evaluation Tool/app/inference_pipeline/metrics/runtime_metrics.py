"""Runtime metric summaries for reusable component reports."""

from __future__ import annotations

from typing import Mapping, Sequence


def summarize_runtime_diagnostics(
    diagnostics_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Summarize per-record runtime diagnostics emitted by the pipeline."""

    runtime_rows = tuple(
        runtime
        for row in diagnostics_rows
        if (runtime := _runtime_stats(row)) is not None
    )
    totals = [_optional_float(row.get("total_sec")) for row in runtime_rows]
    rtfs = [_optional_float(row.get("realtime_factor")) for row in runtime_rows]
    durations = [_optional_float(row.get("audio_duration_sec")) for row in runtime_rows]
    stage_values: dict[str, list[float]] = {}
    devices: list[str] = []

    for row in runtime_rows:
        device = row.get("device")
        if device is not None:
            devices.append(str(device))
        breakdown = row.get("stage_breakdown_sec")
        if isinstance(breakdown, Mapping):
            for stage, value in breakdown.items():
                numeric = _optional_float(value)
                if numeric is not None:
                    stage_values.setdefault(str(stage), []).append(numeric)

    return {
        "runtime_row_count": len(runtime_rows),
        "total_runtime_sec_mean": _mean([value for value in totals if value is not None]),
        "total_runtime_sec_max": _max([value for value in totals if value is not None]),
        "audio_duration_sec_total": sum(value for value in durations if value is not None),
        "realtime_factor_mean": _mean([value for value in rtfs if value is not None]),
        "realtime_factor_max": _max([value for value in rtfs if value is not None]),
        "device": devices[0] if devices else None,
        "stage_breakdown_sec_mean": {
            stage: _mean(values)
            for stage, values in sorted(stage_values.items())
        },
    }


def extract_model_versions_from_diagnostics(
    diagnostics_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return the first non-empty model version block from diagnostics rows."""

    for row in diagnostics_rows:
        runtime = _runtime_stats(row)
        if runtime is None:
            continue
        versions = runtime.get("model_versions")
        if isinstance(versions, Mapping) and versions:
            return {str(key): value for key, value in versions.items()}
    return {}


def runtime_primary_recommendation(metrics: Mapping[str, object]) -> str:
    """Return a concise runtime recommendation for report indexes."""

    rtf = _optional_float(metrics.get("realtime_factor_mean"))
    if rtf is None:
        return "Add runtime diagnostics before comparing deployment readiness."
    if rtf <= 1.0:
        return "Runtime is faster than real time for this artifact set."
    if rtf <= 2.0:
        return "Runtime is close to real time; optimize before Raspberry Pi deployment."
    return "Prioritize runtime optimization before deployment-oriented comparisons."


def _runtime_stats(row: Mapping[str, object]) -> Mapping[str, object] | None:
    if "total_sec" in row and "stage_breakdown_sec" in row:
        return row
    diagnostics = row.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return None
    runtime = diagnostics.get("runtime_stats")
    return runtime if isinstance(runtime, Mapping) else None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _max(values: Sequence[float]) -> float | None:
    return max(values) if values else None
