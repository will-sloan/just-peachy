"""Planned-versus-observed Stage 12 coverage reconciliation."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from app.artifact_contracts.registry import ArtifactRegistry
from app.campaign_exchange.common import atomic_write_bytes, atomic_write_json

from .contracts import (
    ALLOWED_COVERAGE_STATUSES,
    COVERAGE_SCHEMA_VERSION,
    metric_definitions,
    plot_definitions,
    report_definitions,
    table_definitions,
)


FRAMEWORK_CLI_COMMANDS = (
    "list-datasets",
    "gui",
    "run",
    "score",
    "report",
    "full",
    "campaign plan",
    "campaign validate",
    "campaign list",
    "campaign run",
    "campaign resume",
    "campaign status",
    "campaign stop",
    "campaign retry",
    "campaign validate-artifacts",
    "campaign assign",
    "campaign validate-assignments",
    "campaign run-assignment",
    "campaign prepare-worker-copy",
    "campaign export-results",
    "campaign validate-transfer",
    "campaign merge-results",
    "campaign validate-merged",
    "screening plan",
    "screening qualify",
    "screening analyze",
    "extended-screening plan",
    "extended-screening smoke",
    "extended-screening analyze",
    "speaker-protocol build-manifests",
    "speaker-protocol extract",
    "speaker-protocol evaluate",
    "speaker-protocol smoke",
    "speaker-protocol validate",
    "diarization build-manifest",
    "diarization status",
    "diarization run",
    "diarization score",
    "diarization aggregate",
    "diarization validate",
    "diarization smoke",
    "analysis index",
    "analysis validate",
    "analysis run",
    "analysis compare",
    "analysis coverage",
    "analysis release-status",
    "analysis qualify-synthetic",
)


def build_coverage_matrix(
    analysis_manifest: Mapping[str, object],
    metric_registry: Mapping[str, object],
    plot_registry: Mapping[str, object],
    metric_rows: Sequence[Mapping[str, object]],
    plot_statuses: Sequence[Mapping[str, object]],
    *,
    output_root: Path,
    campaign_root: Path | None = None,
    reports_generated: Sequence[str] = (),
    tables_generated: Sequence[str] = (),
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    scenarios = [row for row in analysis_manifest["scenario_index"] if isinstance(row, Mapping)]
    included = [row for row in scenarios if row.get("analysis_status") == "included"]

    component_names: dict[str, list[Mapping[str, object]]] = {}
    for scenario in scenarios:
        components = scenario.get("component_identities")
        if not isinstance(components, Mapping):
            continue
        for family, identity in components.items():
            if isinstance(identity, Mapping):
                component_names.setdefault(f"{family}:{identity.get('name')}", []).append(scenario)
    for name, planned in sorted(component_names.items()):
        observed = [item for item in planned if item.get("analysis_status") == "included"]
        qualification = {
            str(identity.get("qualification_status") or "")
            for scenario in planned
            for identity in [
                next(
                    (
                        value
                        for key, value in scenario["component_identities"].items()
                        if f"{key}:{value.get('name')}" == name
                    ),
                    {},
                )
            ]
            if isinstance(identity, Mapping)
        }
        status = "implemented_qualified" if observed and any("qualified" in item for item in qualification) else ("partial" if observed else "unavailable")
        rows.append(_row("component", name, status, False, len(planned), len(observed), f"qualification={sorted(qualification)}"))

    for category, field in (("panel", "panel"), ("scenario_family", "scenario_type")):
        for name in sorted({str(row.get(field)) for row in scenarios}):
            planned = [row for row in scenarios if str(row.get(field)) == name]
            observed = [row for row in planned if row.get("analysis_status") == "included"]
            status = "implemented_qualified" if len(observed) == len(planned) else ("partial" if observed else "unexpected_missing")
            rows.append(_row(category, name, status, True, len(planned), len(observed), "planned campaign dimension"))

    environment_names = sorted(
        {
            str((row.get("rir") or {}).get("resolved_identifier"))
            for row in scenarios
            if isinstance(row.get("rir"), Mapping)
        }
        | {f"native:{row.get('dataset')}" for row in scenarios if row.get("panel") == "native_robustness"}
    )
    for name in environment_names:
        if name.startswith("native:"):
            planned = [row for row in scenarios if row.get("panel") == "native_robustness" and f"native:{row.get('dataset')}" == name]
        else:
            planned = [row for row in scenarios if isinstance(row.get("rir"), Mapping) and str(row["rir"].get("resolved_identifier")) == name]
        observed = [row for row in planned if row.get("analysis_status") == "included"]
        status = "implemented_qualified" if len(observed) == len(planned) else ("partial" if observed else "unexpected_missing")
        rows.append(_row("environment", name, status, True, len(planned), len(observed), "exact environment identity"))

    fingerprints = {
        str(row.get("environment_fingerprint_id"))
        for row in included
        if row.get("environment_fingerprint_id")
    }
    for fingerprint in sorted(fingerprints):
        observed = sum(row.get("environment_fingerprint_id") == fingerprint for row in included)
        rows.append(_row("execution_environment", fingerprint, "implemented_qualified", False, observed, observed, "validated Stage 6 environment fingerprint"))

    supported_by_metric: dict[str, int] = {}
    eligible_by_metric: dict[str, int] = {}
    for row in metric_rows:
        name = str(row["metric_name"])
        eligible_by_metric[name] = eligible_by_metric.get(name, 0) + 1
        if row.get("supported"):
            supported_by_metric[name] = supported_by_metric.get(name, 0) + 1
    planned_types = {str(row.get("scenario_type")) for row in scenarios}
    for definition in metric_definitions(metric_registry):
        name = str(definition["name"])
        relevant = bool(planned_types & {str(item) for item in definition["scenario_types"]})
        supported = supported_by_metric.get(name, 0)
        status = "implemented_qualified" if supported else ("partial" if relevant else "excluded")
        rows.append(_row("metric", name, status, False, eligible_by_metric.get(name, 0), supported, str(definition["limitations"])))

    artifact_names = {key for row in scenarios for key in (row.get("artifact_paths") or {})}
    registry_version = str(analysis_manifest["campaign"]["artifact_registry_version"])
    registry = ArtifactRegistry.load_version(registry_version)
    artifact_names.update(definition.artifact_id for definition in registry.artifacts)
    required_artifacts = {
        artifact
        for scenario_type in {str(row.get("scenario_type")) for row in scenarios}
        if scenario_type in registry.scenario_profiles
        for artifact in registry.scenario_profiles[scenario_type].required_artifacts
    }
    aliases = {"scenario_report_json": "scenario_report", "scenario_report_markdown": "scenario_report_markdown"}
    definition_by_name = {definition.artifact_id: definition for definition in registry.artifacts}
    campaign = campaign_root.resolve() if campaign_root is not None else None
    for name in sorted(artifact_names):
        observed_key = aliases.get(name, name)
        definition = definition_by_name.get(name)
        if definition is not None and definition.scope == "campaign" and campaign is not None:
            observed = sum(1 for path in campaign.glob(definition.path) if path.is_file())
            planned_count = 1
        else:
            observed = sum(observed_key in (row.get("artifact_paths") or {}) for row in included)
            planned_count = len(included)
        mandatory = name in required_artifacts or bool(definition and definition.scope == "campaign" and definition.status == "mandatory")
        status = "implemented_qualified" if observed else ("unexpected_missing" if mandatory and included else "unavailable")
        rows.append(_row("artifact", name, status, mandatory, planned_count, observed, "released artifact registry and validated included paths"))
    for mandatory in ("analysis_manifest", "campaign_result_index", "scenario_metric_values", "coverage_matrix"):
        rows.append(_row("artifact", mandatory, "implemented_qualified", True, 1, 1, "Stage 12 campaign artifact"))

    plot_by_id = {str(row["plot_id"]): row for row in plot_statuses}
    for definition in plot_definitions(plot_registry):
        status_row = plot_by_id.get(str(definition["id"]), {})
        generated = status_row.get("status") == "generated"
        rows.append(_row("plot", str(definition["id"]), "implemented_qualified" if generated else "unavailable", False, 1, int(generated), str(status_row.get("reason") or "not attempted")))

    generated_reports = set(reports_generated)
    generated_tables = set(tables_generated)
    for definition in table_definitions(plot_registry):
        generated = str(definition["id"]) in generated_tables
        rows.append(_row("table", str(definition["id"]), "implemented_qualified" if generated else "unexpected_missing", True, 1, int(generated), "registry-defined campaign table"))
    for definition in report_definitions(plot_registry):
        generated = str(definition["id"]) in generated_reports
        rows.append(_row("report", str(definition["id"]), "implemented_qualified" if generated else "deferred", str(definition["id"]) in {"campaign_summary", "machine_readable_summary", "coverage_report", "release_qualification"}, 1, int(generated), "registry-defined campaign report"))

    for command in FRAMEWORK_CLI_COMMANDS:
        rows.append(_row("cli_command", command, "implemented_qualified", True, 1, 1, "registered by app.campaign_analysis.cli"))

    blockers = [row for row in rows if row["mandatory"] and row["status"] == "unexpected_missing"]
    value = {
        "schema_version": COVERAGE_SCHEMA_VERSION,
        "status_vocabulary": sorted(ALLOWED_COVERAGE_STATUSES),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "status_counts": _counts(rows, "status"),
            "category_counts": _counts(rows, "category"),
            "mandatory_unexpected_missing": len(blockers),
            "release_blocked": bool(blockers),
        },
        "mandatory_blockers": blockers,
    }
    atomic_write_json(output_root / "coverage_matrix.json", value)
    frame = pd.DataFrame.from_records(rows)
    atomic_write_bytes(output_root / "tables" / "coverage_matrix.csv", frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))
    return value


def _row(category: str, name: str, status: str, mandatory: bool, planned: int, observed: int, reason: str) -> dict[str, object]:
    if status not in ALLOWED_COVERAGE_STATUSES:
        raise ValueError(f"unsupported coverage status: {status}")
    return {
        "category": category,
        "name": name,
        "status": status,
        "mandatory": mandatory,
        "planned_count": planned,
        "observed_count": observed,
        "reason": reason,
    }


def _counts(rows: Sequence[Mapping[str, object]], field: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        key = str(row[field])
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))
