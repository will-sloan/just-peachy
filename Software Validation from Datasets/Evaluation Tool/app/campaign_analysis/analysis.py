"""Stage 12 campaign analysis orchestration without inference reruns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from app.campaign_exchange.common import atomic_write_bytes, atomic_write_json, directory_inventory
from app.benchmark_contracts.canonical import canonical_sha256

from .contracts import ANALYSIS_SUMMARY_SCHEMA_VERSION, load_registries
from .coverage import build_coverage_matrix
from .index import build_analysis_manifest
from .metrics import collect_failure_categories, extract_campaign_metrics
from .plots import build_campaign_plots
from .release import evaluate_release_gates
from .report import build_campaign_report
from .statistics import paired_comparison, repeated_finalist_variance


def analyze_campaign(
    campaign_root: Path,
    *,
    comparisons: Sequence[Mapping[str, str]] = (),
    prerequisite_evidence_path: Path | None = None,
    config_root: Path | None = None,
) -> dict[str, object]:
    """Build indexes, comparisons, plots, reports, coverage, and release status."""

    campaign = campaign_root.resolve()
    registries = load_registries(config_root)
    manifest = build_analysis_manifest(campaign, config_root=config_root)
    output = campaign / "analysis"
    metric_rows = extract_campaign_metrics(
        campaign,
        manifest,
        registries.metric_registry,
        output_root=output,
    )
    atomic_write_bytes(
        output / "tables" / "scenario_index.csv",
        pd.json_normalize(manifest["scenario_index"], sep=".")
        .to_csv(index=False, lineterminator="\n")
        .encode("utf-8"),
    )
    comparison_rows = _comparisons(campaign, manifest, comparisons, registries.decision_policy)
    atomic_write_json(
        output / "comparisons.json",
        {"schema_version": "campaign-comparisons.v1", "comparisons": comparison_rows},
    )
    atomic_write_bytes(
        output / "tables" / "comparisons.csv",
        pd.json_normalize(comparison_rows).to_csv(index=False, lineterminator="\n").encode("utf-8"),
    )
    repetition_rows = _repetition_variance(manifest, metric_rows)
    atomic_write_json(
        output / "repeated_finalist_variance.json",
        {
            "schema_version": "repeated-finalist-variance.v1",
            "groups": repetition_rows,
        },
    )
    atomic_write_bytes(
        output / "tables" / "repeated_finalist_variance.csv",
        pd.json_normalize(repetition_rows)
        .to_csv(index=False, lineterminator="\n")
        .encode("utf-8"),
    )
    failure_rows = collect_failure_categories(campaign, manifest)
    atomic_write_bytes(
        output / "tables" / "failure_categories.csv",
        pd.DataFrame.from_records(failure_rows).to_csv(index=False, lineterminator="\n").encode("utf-8"),
    )
    plot_statuses = build_campaign_plots(
        campaign,
        manifest,
        metric_rows,
        registries.plot_report_registry,
        failure_rows,
        output_root=output,
    )
    reports = (
        "campaign_summary",
        "machine_readable_summary",
        "coverage_report",
        "release_qualification",
    )
    tables = (
        "scenario_index",
        "scenario_metric_values",
        "paired_comparisons",
        "failure_categories",
        "coverage_matrix",
        "repeated_finalist_variance",
    )
    coverage = build_coverage_matrix(
        manifest,
        registries.metric_registry,
        registries.plot_report_registry,
        metric_rows,
        plot_statuses,
        output_root=output,
        campaign_root=campaign,
        reports_generated=reports,
        tables_generated=tables,
    )
    evidence = _read_optional_json(prerequisite_evidence_path)
    release = evaluate_release_gates(
        manifest,
        coverage,
        registries.decision_policy,
        prerequisite_evidence=evidence,
    )
    report = build_campaign_report(
        manifest,
        coverage,
        release,
        plot_statuses,
        comparison_rows,
        output_root=output,
    )
    summary = {
        "schema_version": ANALYSIS_SUMMARY_SCHEMA_VERSION,
        "campaign_id": manifest["campaign"]["campaign_id"],
        "analysis_manifest_id": manifest["analysis_manifest_id"],
        "analysis_manifest_sha256": manifest["analysis_manifest_sha256"],
        "planned_scenario_count": len(manifest["scenario_index"]),
        "included_scenario_count": sum(row["analysis_status"] == "included" for row in manifest["scenario_index"]),
        "metric_value_count": sum(row["supported"] for row in metric_rows),
        "comparison_count": len(comparison_rows),
        "repeated_finalist_group_count": len(repetition_rows),
        "generated_plot_count": sum(row["status"] == "generated" for row in plot_statuses),
        "skipped_plot_count": sum(row["status"] == "skipped" for row in plot_statuses),
        "release_status": release["status"],
        "coverage_blocker_count": coverage["summary"]["mandatory_unexpected_missing"],
        "report": "report/campaign_report.json",
    }
    atomic_write_json(output / "analysis_summary.json", summary)
    _write_analysis_checksums(output)
    _ = report
    return summary


def _comparisons(
    campaign: Path,
    manifest: Mapping[str, object],
    declarations: Sequence[Mapping[str, str]],
    policy: Mapping[str, object],
) -> list[dict[str, object]]:
    by_id = {str(row["scenario_id"]): row for row in manifest["scenario_index"]}
    statistics = policy["statistics_policy"]
    results: list[dict[str, object]] = []
    for declaration in declarations:
        baseline_id = str(declaration["baseline_scenario_id"])
        candidate_id = str(declaration["candidate_scenario_id"])
        metric = str(declaration["metric"])
        baseline = by_id.get(baseline_id)
        candidate = by_id.get(candidate_id)
        if not baseline or not candidate:
            raise ValueError("comparison references a scenario outside the campaign")
        _require_compatible_pair(baseline, candidate)
        baseline_path = _item_metrics_path(campaign, baseline)
        candidate_path = _item_metrics_path(campaign, candidate)
        results.append(
            paired_comparison(
                baseline_path,
                candidate_path,
                metric=str(declaration.get("item_field") or metric),
                baseline_scenario_id=baseline_id,
                candidate_scenario_id=candidate_id,
                seed=int(policy["seed"]),
                bootstrap_repetitions=int(statistics["bootstrap_repetitions"]),
                confidence_level=float(statistics["confidence_level"]),
            )
        )
    return results


def _require_compatible_pair(baseline: Mapping[str, object], candidate: Mapping[str, object]) -> None:
    for field in ("benchmark_manifest", "panel", "tier", "dataset", "scoring_policy_version"):
        if baseline.get(field) != candidate.get(field):
            raise ValueError(f"paired comparison has incompatible {field}")
    if baseline.get("analysis_status") != "included" or candidate.get("analysis_status") != "included":
        raise ValueError("paired comparison requires two validated included scenarios")


def _item_metrics_path(campaign: Path, row: Mapping[str, object]) -> Path:
    artifacts = row.get("artifact_paths")
    if not isinstance(artifacts, Mapping) or not artifacts.get("item_metrics"):
        raise ValueError(f"scenario has no item metrics: {row.get('scenario_id')}")
    return campaign / str(artifacts["item_metrics"])


def _read_optional_json(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("prerequisite evidence must be a JSON mapping")
    return value


def _repetition_variance(
    manifest: Mapping[str, object],
    metric_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    scenarios = {str(row["scenario_id"]): row for row in manifest["scenario_index"]}
    groups: dict[tuple[str, str], list[tuple[str, float, int]]] = {}
    identities: dict[str, dict[str, object]] = {}
    for row in metric_rows:
        if not row.get("supported") or row.get("value") is None:
            continue
        scenario = scenarios[str(row["scenario_id"])]
        identity = {
            "dataset": scenario.get("dataset"),
            "panel": scenario.get("panel"),
            "tier": scenario.get("tier"),
            "condition_id": scenario.get("condition_id"),
            "component_identities": scenario.get("component_identities"),
            "model_identities": scenario.get("model_identities"),
            "scoring_policy_version": scenario.get("scoring_policy_version"),
        }
        group_id = canonical_sha256(identity)[:12].lower()
        identities[group_id] = identity
        key = (group_id, str(row["metric_name"]))
        groups.setdefault(key, []).append(
            (
                str(row["scenario_id"]),
                float(row["value"]),
                int(scenario.get("repetition") or 1),
            )
        )
    result: list[dict[str, object]] = []
    for (group_id, metric), values in sorted(groups.items()):
        repetitions = {item[2] for item in values}
        if len(values) < 2 or len(repetitions) < 2:
            continue
        result.append(
            {
                "group_id": f"repeat_{group_id}",
                "metric": metric,
                "scenario_ids": sorted(item[0] for item in values),
                "repetitions": sorted(repetitions),
                "identity": identities[group_id],
                **repeated_finalist_variance([item[1] for item in values]),
            }
        )
    return result


def _write_analysis_checksums(output: Path) -> None:
    entries = []
    for row in directory_inventory(output):
        if row["path"] == "analysis_checksums.json" or str(row["path"]).startswith("merged_results/"):
            continue
        entries.append(row)
    atomic_write_json(
        output / "analysis_checksums.json",
        {
            "schema_version": "campaign-analysis-checksums.v1",
            "hash_algorithm": "sha256",
            "entries": entries,
        },
    )
