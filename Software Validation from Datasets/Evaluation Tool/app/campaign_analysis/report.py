"""Campaign report rendering from standalone Stage 12 artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from app.campaign_exchange.common import atomic_write_bytes, atomic_write_json


def build_campaign_report(
    analysis_manifest: Mapping[str, object],
    coverage: Mapping[str, object],
    release: Mapping[str, object],
    plot_statuses: Sequence[Mapping[str, object]],
    comparisons: Sequence[Mapping[str, object]],
    *,
    output_root: Path,
) -> dict[str, object]:
    rows = analysis_manifest["scenario_index"]
    excluded = analysis_manifest["failed_missing_invalid_excluded"]
    generated = [row for row in plot_statuses if row.get("status") == "generated"]
    skipped = [row for row in plot_statuses if row.get("status") != "generated"]
    report = {
        "schema_version": "campaign-report.v1",
        "campaign_id": analysis_manifest["campaign"]["campaign_id"],
        "analysis_manifest_id": analysis_manifest["analysis_manifest_id"],
        "analysis_manifest_sha256": analysis_manifest["analysis_manifest_sha256"],
        "contract_versions": analysis_manifest["contract_versions"],
        "benchmark_manifests": analysis_manifest["benchmark_manifests"],
        "scenario_counts": analysis_manifest["status_counts"],
        "planned_scenarios": len(rows),
        "included_scenarios": sum(row.get("analysis_status") == "included" for row in rows),
        "excluded_and_gaps": excluded,
        "comparison_count": len(comparisons),
        "comparisons": list(comparisons),
        "generated_plots": generated,
        "skipped_plots": skipped,
        "coverage_summary": coverage["summary"],
        "coverage_blockers": coverage["mandatory_blockers"],
        "release_qualification": release,
        "inputs": {
            "analysis_manifest": "analysis_manifest.json",
            "scenario_metric_values": "tables/scenario_metric_values.parquet",
            "scenario_index": "tables/scenario_index.csv",
            "comparisons": "tables/comparisons.csv",
            "failure_categories": "tables/failure_categories.csv",
            "repeated_finalist_variance": "tables/repeated_finalist_variance.csv",
            "coverage_matrix": "coverage_matrix.json",
            "plot_status": "plot_status.json",
        },
        "limitations": [
            "Only existing validated scenario outputs were analyzed; inference was not rerun.",
            "Every unsupported plot or metric is listed explicitly rather than synthesized.",
            "Comparisons are scientific only when benchmark, scoring, and item identities are compatible.",
            "Subgroup results are descriptive unless authorization, counts, and inferential assumptions are documented.",
        ],
        "interpretation_guide": "contracts/analysis_guide.md",
    }
    report_root = output_root / "report"
    atomic_write_json(report_root / "campaign_report.json", report)
    atomic_write_json(report_root / "release_qualification.json", release)
    _write_markdown(report_root / "campaign_report.md", report)
    _write_coverage_markdown(report_root / "coverage_report.md", coverage)
    return report


def _write_markdown(path: Path, report: Mapping[str, object]) -> None:
    counts = report["scenario_counts"]
    lines = [
        f"# Campaign report: {report['campaign_id']}",
        "",
        f"Analysis manifest: `{report['analysis_manifest_id']}` (`{report['analysis_manifest_sha256']}`).",
        "",
        "## Outcome",
        "",
        f"- Planned scenarios: `{report['planned_scenarios']}`",
        f"- Included validated scenarios: `{report['included_scenarios']}`",
        f"- Status counts: `{counts}`",
        f"- Release gate: `{report['release_qualification']['target_gate']}` → `{report['release_qualification']['status']}`",
        f"- Paired comparisons: `{report['comparison_count']}`",
        "",
        "## Exclusions and gaps",
        "",
    ]
    excluded = report["excluded_and_gaps"]
    if excluded:
        lines.extend(
            f"- `{row['scenario_id']}` — **{row['status']}**: {row['reason']}"
            for row in excluded
        )
    else:
        lines.append("No planned scenario was excluded, missing, failed, or invalid.")
    lines.extend(["", "## Plots", ""])
    for row in report["generated_plots"]:
        lines.append(f"- [{row['plot_id']}](../{row['output']}) — [interpretation](../contracts/analysis_guide.md#{row['interpretation'].split('#')[-1]})")
    if report["skipped_plots"]:
        lines.extend(["", "Skipped with explicit eligibility reasons:", ""])
        lines.extend(f"- `{row['plot_id']}`: {row['reason']}" for row in report["skipped_plots"])
    lines.extend(["", "## Release checks", ""])
    lines.extend(
        f"- {'PASS' if check['passed'] else 'BLOCK'} `{check['name']}` — observed `{check['observed']}`; required `{check['required']}`"
        for check in report["release_qualification"]["checks"]
    )
    lines.extend(["", "## Inputs and limitations", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in report["inputs"].items())
    lines.append("")
    lines.extend(f"- {value}" for value in report["limitations"])
    lines.extend(["", "See [analysis_guide.md](../contracts/analysis_guide.md) before interpreting metrics or plots.", ""])
    atomic_write_bytes(path, "\n".join(lines).encode("utf-8"))


def _write_coverage_markdown(path: Path, coverage: Mapping[str, object]) -> None:
    lines = [
        "# Campaign coverage reconciliation",
        "",
        f"Rows: `{coverage['summary']['row_count']}`. Mandatory unexplained gaps: `{coverage['summary']['mandatory_unexpected_missing']}`.",
        "",
        "| Category | Name | Status | Mandatory | Planned | Observed | Reason |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in coverage["rows"]:
        reason = str(row["reason"]).replace("|", "\\|")
        lines.append(f"| {row['category']} | {row['name']} | {row['status']} | {row['mandatory']} | {row['planned_count']} | {row['observed_count']} | {reason} |")
    lines.append("")
    atomic_write_bytes(path, "\n".join(lines).encode("utf-8"))
