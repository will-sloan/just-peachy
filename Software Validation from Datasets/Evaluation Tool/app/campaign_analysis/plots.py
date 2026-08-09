"""Eligibility-gated Stage 12 plots with provenance sidecars."""

from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
from typing import Mapping, Sequence
import uuid

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.parquet as pq

from app.campaign_exchange.common import atomic_write_json

from .contracts import plot_definitions
from .metrics import metric_lookup


PLOT_STATUS_SCHEMA_VERSION = "campaign-plot-status.v1"


def build_campaign_plots(
    campaign_root: Path,
    analysis_manifest: Mapping[str, object],
    metric_rows: Sequence[Mapping[str, object]],
    plot_registry: Mapping[str, object],
    failure_rows: Sequence[Mapping[str, object]],
    *,
    output_root: Path,
) -> list[dict[str, object]]:
    campaign = campaign_root.resolve()
    values = metric_lookup(metric_rows)
    statuses: list[dict[str, object]] = []
    for definition in plot_definitions(plot_registry):
        eligible, reason = _eligible(definition, analysis_manifest, values, failure_rows)
        output = str(definition["output"])
        status = {
            "schema_version": PLOT_STATUS_SCHEMA_VERSION,
            "plot_id": definition["id"],
            "question": definition["question"],
            "status": "skipped",
            "reason": reason,
            "output": None,
            "metadata": None,
            "interpretation": f"contracts/analysis_guide.md#{definition['interpretation_anchor']}",
        }
        if eligible:
            try:
                path = output_root / output
                _render(
                    campaign,
                    path,
                    definition,
                    analysis_manifest,
                    values,
                    failure_rows,
                )
                metadata_path = path.with_suffix(path.suffix + ".metadata.json")
                metadata = _metadata(definition, analysis_manifest, metric_rows, output_root, path)
                atomic_write_json(metadata_path, metadata)
                status.update(
                    {
                        "status": "generated",
                        "reason": "all registered data requirements were satisfied",
                        "output": path.relative_to(output_root).as_posix(),
                        "metadata": metadata_path.relative_to(output_root).as_posix(),
                    }
                )
            except Exception as exc:
                status["status"] = "skipped"
                status["reason"] = f"render failed safely: {type(exc).__name__}: {exc}"
        statuses.append(status)
    atomic_write_json(
        output_root / "plot_status.json",
        {
            "schema_version": PLOT_STATUS_SCHEMA_VERSION,
            "plots": statuses,
            "generated_count": sum(item["status"] == "generated" for item in statuses),
            "skipped_count": sum(item["status"] == "skipped" for item in statuses),
        },
    )
    return statuses


def _eligible(
    definition: Mapping[str, object],
    manifest: Mapping[str, object],
    values: Mapping[tuple[str, str], float],
    failures: Sequence[Mapping[str, object]],
) -> tuple[bool, str]:
    rows = [row for row in manifest["scenario_index"] if isinstance(row, Mapping)]
    included = [row for row in rows if row.get("analysis_status") == "included"]
    for requirement in definition.get("data_requirements", []):
        name = str(requirement)
        if name in {"analysis_manifest", "coverage_matrix", "metric_values", "plot_status", "release_gate_results"}:
            continue
        if name == "exact_rir_identity":
            if not any(isinstance(row.get("rir"), Mapping) for row in included):
                return False, "no validated included scenario has an exact RIR identity"
        elif name == "native_panel":
            if not any(row.get("panel") == "native_robustness" for row in included):
                return False, "no validated native-robustness scenario is included"
        elif name == "multiple_environment_fingerprints":
            fingerprints = {row.get("environment_fingerprint_id") for row in included if row.get("environment_fingerprint_id")}
            if len(fingerprints) < 2:
                return False, "fewer than two environment fingerprints are available"
        elif name == "speaker_similarity_scores":
            if not any(_artifact(row, "similarity_scores") for row in included):
                return False, "no compatible speaker similarity-score artifact is available"
        elif name == "speaker_threshold_sweep":
            if not any(_artifact(row, "threshold_sweep") for row in included):
                return False, "no compatible speaker threshold-sweep artifact is available"
        elif name == "authorized_subgroup_metric":
            if not any(_artifact(row, "grouped_metrics") for row in included):
                return False, "no authorized grouped-metric artifact is available"
        elif name == "failure_records":
            if not failures:
                return False, "no failure categories were observed"
        elif not any((str(row["scenario_id"]), name) in values for row in included):
            return False, f"registered metric {name} has no supported included value"
    return True, "eligible"


def _render(
    campaign: Path,
    path: Path,
    definition: Mapping[str, object],
    manifest: Mapping[str, object],
    values: Mapping[tuple[str, str], float],
    failures: Sequence[Mapping[str, object]],
) -> None:
    handler = str(definition.get("handler") or "bars")
    rows = [row for row in manifest["scenario_index"] if isinstance(row, Mapping)]
    included = [row for row in rows if row.get("analysis_status") == "included"]
    fig, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    if handler == "status_counts":
        counts = Counter(str(row.get("analysis_status")) for row in rows)
        labels = sorted(counts)
        axis.bar(labels, [counts[label] for label in labels], color="#35618a")
        axis.set_ylabel("Scenario count")
    elif handler == "scatter":
        x_metric = str(definition["x_metric"])
        y_metric = str(definition["y_metric"])
        points = [
            (values[(str(row["scenario_id"]), x_metric)], values[(str(row["scenario_id"]), y_metric)], _short_label(row))
            for row in included
            if (str(row["scenario_id"]), x_metric) in values and (str(row["scenario_id"]), y_metric) in values
        ]
        axis.scatter([item[0] for item in points], [item[1] for item in points], color="#c24e3e")
        for x_value, y_value, label in points[:20]:
            axis.annotate(label, (x_value, y_value), fontsize=7)
        axis.set_xlabel(x_metric)
        axis.set_ylabel(y_metric)
    elif handler == "rir_heatmap":
        _render_rir_heatmap(axis, included, values, str(definition["primary_metric"]))
    elif handler == "failure_categories":
        counts: Counter[str] = Counter()
        for row in failures:
            counts[str(row["category"])] += int(row["count"])
        labels = [item[0] for item in counts.most_common(15)]
        axis.barh(labels[::-1], [counts[label] for label in labels[::-1]], color="#9f4b66")
        axis.set_xlabel("Observed count")
    elif handler in {"speaker_distribution", "roc_det", "threshold", "subgroup"}:
        _render_special_artifact(campaign, axis, included, handler)
    else:
        metric = str(definition.get("primary_metric") or "scenario_completion")
        grouped = _group_metric(included, values, metric, handler)
        labels = list(grouped)
        axis.bar(range(len(labels)), [grouped[label] for label in labels], color="#3a7f70")
        axis.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
        axis.set_ylabel(metric)
    axis.set_title(str(definition["question"]))
    axis.grid(axis="y", alpha=0.2)
    _atomic_savefig(fig, path)
    plt.close(fig)


def _render_rir_heatmap(
    axis,
    rows: Sequence[Mapping[str, object]],
    values: Mapping[tuple[str, str], float],
    metric: str,
) -> None:
    records: list[dict[str, object]] = []
    for row in rows:
        rir = row.get("rir")
        key = (str(row["scenario_id"]), metric)
        if not isinstance(rir, Mapping) or key not in values:
            continue
        records.append(
            {
                "pipeline": _pipeline_label(row),
                "rir": str(rir.get("resolved_identifier") or rir.get("rir_id")),
                "value": values[key],
            }
        )
    frame = pd.DataFrame.from_records(records)
    pivot = frame.pivot_table(index="pipeline", columns="rir", values="value", aggfunc="mean")
    image = axis.imshow(pivot.to_numpy(), aspect="auto", interpolation="nearest", cmap="viridis")
    axis.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
    axis.set_yticks(range(len(pivot.index)), pivot.index)
    axis.figure.colorbar(image, ax=axis, label=metric)


def _render_special_artifact(
    campaign: Path,
    axis,
    rows: Sequence[Mapping[str, object]],
    handler: str,
) -> None:
    if handler == "speaker_distribution":
        frames = _artifact_frames(campaign, rows, "similarity_scores")
        frame = pd.concat(frames, ignore_index=True)
        label_column = next(name for name in ("same_speaker", "is_same_speaker", "trial_type") if name in frame.columns)
        score_column = next(name for name in ("score", "cosine_similarity", "similarity") if name in frame.columns)
        for label, group in frame.groupby(label_column):
            axis.hist(pd.to_numeric(group[score_column], errors="coerce").dropna(), bins=30, alpha=0.5, label=str(label))
        axis.legend()
        axis.set_xlabel("Similarity score")
        return
    if handler in {"roc_det", "threshold"}:
        frame = pd.concat(_artifact_frames(campaign, rows, "threshold_sweep"), ignore_index=True)
        threshold = next(name for name in ("threshold", "score_threshold") if name in frame.columns)
        far = next(name for name in ("far", "false_accept_rate") if name in frame.columns)
        frr = next(name for name in ("frr", "false_reject_rate") if name in frame.columns)
        if handler == "roc_det":
            axis.plot(frame[far], frame[frr], marker=".")
            axis.set_xlabel("FAR")
            axis.set_ylabel("FRR")
        else:
            axis.plot(frame[threshold], frame[far], label="FAR")
            axis.plot(frame[threshold], frame[frr], label="FRR")
            axis.legend()
            axis.set_xlabel("Threshold")
        return
    frames = _artifact_frames(campaign, rows, "grouped_metrics")
    frame = pd.concat(frames, ignore_index=True)
    numeric = [name for name in frame.columns if pd.api.types.is_numeric_dtype(frame[name])]
    if not numeric:
        raise ValueError("grouped metrics have no numeric field")
    values = pd.to_numeric(frame[numeric[0]], errors="coerce").dropna()
    axis.hist(values, bins=min(20, max(5, len(values))))
    axis.set_xlabel(numeric[0])


def _artifact_frames(campaign: Path, rows: Sequence[Mapping[str, object]], artifact: str) -> list[pd.DataFrame]:
    frames = []
    for row in rows:
        relative = _artifact(row, artifact)
        if relative:
            frames.append(pq.read_table(campaign / relative).to_pandas())
    if not frames:
        raise ValueError(f"no {artifact} frames")
    return frames


def _group_metric(
    rows: Sequence[Mapping[str, object]],
    values: Mapping[tuple[str, str], float],
    metric: str,
    handler: str,
) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        key = (str(row["scenario_id"]), metric)
        if key not in values:
            continue
        if handler == "condition_bars":
            label = str(row.get("condition_id") or "Unknown")
        elif handler == "panel_bars":
            label = f"{row.get('dataset')}:{row.get('condition_id')}"
        elif handler == "environment_bars":
            label = str(row.get("environment_fingerprint_id") or "Unknown")
        else:
            label = _short_label(row)
        grouped.setdefault(label, []).append(values[key])
    return {label: sum(items) / len(items) for label, items in sorted(grouped.items())}


def _metadata(
    definition: Mapping[str, object],
    manifest: Mapping[str, object],
    metric_rows: Sequence[Mapping[str, object]],
    output_root: Path,
    path: Path,
) -> dict[str, object]:
    required = {str(item) for item in definition.get("data_requirements", [])}
    scenario_ids = sorted(
        {
            str(row["scenario_id"])
            for row in metric_rows
            if row.get("supported") and str(row.get("metric_name")) in required
        }
    )
    if not scenario_ids:
        scenario_ids = sorted(
            str(row["scenario_id"])
            for row in manifest["scenario_index"]
            if isinstance(row, Mapping) and row.get("analysis_status") == "included"
        )
    return {
        "schema_version": "campaign-plot-metadata.v1",
        "plot_id": definition["id"],
        "question": definition["question"],
        "output": path.relative_to(output_root).as_posix(),
        "analysis_manifest_id": manifest["analysis_manifest_id"],
        "analysis_manifest_sha256": manifest["analysis_manifest_sha256"],
        "campaign_id": manifest["campaign"]["campaign_id"],
        "benchmark_manifests": manifest["benchmark_manifests"],
        "scenario_ids": scenario_ids,
        "contract_versions": manifest["contract_versions"],
        "data_requirements": definition["data_requirements"],
        "aggregation": definition["aggregation"],
        "filters": definition["filters"],
        "statistics": definition["statistics"],
        "limitations": definition["limitations"],
        "interpretation": f"contracts/analysis_guide.md#{definition['interpretation_anchor']}",
    }


def _artifact(row: Mapping[str, object], key: str) -> str | None:
    artifacts = row.get("artifact_paths")
    if isinstance(artifacts, Mapping) and artifacts.get(key):
        return str(artifacts[key])
    return None


def _short_label(row: Mapping[str, object]) -> str:
    return f"{row.get('dataset')}:{str(row.get('scenario_id'))[-6:]}"


def _pipeline_label(row: Mapping[str, object]) -> str:
    components = row.get("component_identities")
    if not isinstance(components, Mapping):
        return _short_label(row)
    names = [str(value.get("name")) for value in components.values() if isinstance(value, Mapping) and value.get("enabled")]
    return "+".join(names) or _short_label(row)


def _atomic_savefig(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.tmp-{uuid.uuid4().hex}{path.suffix}")
    try:
        fig.savefig(temporary, dpi=160)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
