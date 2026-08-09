"""Released Stage 12 registry and analysis-contract readers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

from app.artifact_contracts.atomic import file_sha256
from app.benchmark_contracts.canonical import canonical_sha256


ANALYSIS_MANIFEST_SCHEMA_VERSION = "analysis-manifest.v1"
RESULT_INDEX_SCHEMA_VERSION = "campaign-result-index.v1"
ANALYSIS_SUMMARY_SCHEMA_VERSION = "campaign-analysis-summary.v1"
METRIC_REGISTRY_SCHEMA_VERSION = "campaign-metric-registry.v1"
PLOT_REPORT_REGISTRY_SCHEMA_VERSION = "campaign-plot-report-registry.v1"
DECISION_POLICY_SCHEMA_VERSION = "campaign-decision-policy.v1"
COVERAGE_SCHEMA_VERSION = "campaign-coverage-matrix.v1"
COMPARISON_SCHEMA_VERSION = "paired-campaign-comparison.v1"
RELEASE_SCHEMA_VERSION = "campaign-release-qualification.v1"

HASH_VERSION = "campaign-analysis-hash.v1"
HASH_ALGORITHM = "sha256"
ANALYSIS_HASH_EXCLUSIONS = frozenset(
    {"analysis_manifest_id", "analysis_manifest_sha256", "created_at_utc"}
)
RESULT_INDEX_HASH_EXCLUSIONS = frozenset(
    {"result_index_id", "result_index_sha256", "created_at_utc"}
)

ALLOWED_COVERAGE_STATUSES = frozenset(
    {
        "implemented_qualified",
        "unavailable",
        "partial",
        "deferred",
        "excluded",
        "unexpected_missing",
    }
)


class AnalysisContractError(RuntimeError):
    """Raised when a Stage 12 input violates a released contract."""


@dataclass(frozen=True)
class RegistryBundle:
    metric_registry: dict[str, object]
    plot_report_registry: dict[str, object]
    decision_policy: dict[str, object]
    metric_registry_path: Path
    plot_report_registry_path: Path
    decision_policy_path: Path

    def identities(self, root: Path) -> dict[str, object]:
        return {
            "metric_registry": _file_identity(self.metric_registry_path, root),
            "plot_report_registry": _file_identity(self.plot_report_registry_path, root),
            "decision_policy": _file_identity(self.decision_policy_path, root),
        }


def default_config_root() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "automated_evaluation"


def load_registries(config_root: Path | None = None) -> RegistryBundle:
    root = (config_root or default_config_root()).resolve()
    metric_path = root / "metric_registry.v1.yaml"
    plot_path = root / "plot_report_registry.v1.yaml"
    policy_path = root / "analysis_decision_policy.v1.yaml"
    metrics = _read_yaml(metric_path)
    plots = _read_yaml(plot_path)
    policy = _read_yaml(policy_path)
    _validate_metric_registry(metrics)
    _validate_plot_report_registry(plots)
    _validate_decision_policy(policy)
    return RegistryBundle(
        metric_registry=metrics,
        plot_report_registry=plots,
        decision_policy=policy,
        metric_registry_path=metric_path,
        plot_report_registry_path=plot_path,
        decision_policy_path=policy_path,
    )


def finalize_hashed_contract(
    value: Mapping[str, object],
    *,
    id_field: str,
    hash_field: str,
    id_prefix: str,
    exclusions: frozenset[str],
) -> dict[str, object]:
    result = dict(value)
    payload = {key: item for key, item in result.items() if key not in exclusions}
    digest = canonical_sha256(payload)
    result[hash_field] = digest
    result[id_field] = f"{id_prefix}_{digest[:12].lower()}"
    return result


def verify_hashed_contract(
    value: Mapping[str, object],
    *,
    id_field: str,
    hash_field: str,
    id_prefix: str,
    exclusions: frozenset[str],
) -> None:
    payload = {key: item for key, item in value.items() if key not in exclusions}
    digest = canonical_sha256(payload)
    if value.get(hash_field) != digest:
        raise AnalysisContractError(f"{hash_field} does not match canonical content")
    if value.get(id_field) != f"{id_prefix}_{digest[:12].lower()}":
        raise AnalysisContractError(f"{id_field} does not match {hash_field}")


def metric_definitions(registry: Mapping[str, object]) -> list[dict[str, object]]:
    raw = registry.get("metrics")
    if not isinstance(raw, list):
        raise AnalysisContractError("metric registry metrics must be a list")
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def plot_definitions(registry: Mapping[str, object]) -> list[dict[str, object]]:
    raw = registry.get("plots")
    if not isinstance(raw, list):
        raise AnalysisContractError("plot registry plots must be a list")
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def report_definitions(registry: Mapping[str, object]) -> list[dict[str, object]]:
    raw = registry.get("reports")
    if not isinstance(raw, list):
        raise AnalysisContractError("plot registry reports must be a list")
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def table_definitions(registry: Mapping[str, object]) -> list[dict[str, object]]:
    raw = registry.get("tables")
    if not isinstance(raw, list):
        raise AnalysisContractError("plot registry tables must be a list")
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _read_yaml(path: Path) -> dict[str, object]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AnalysisContractError(f"cannot read Stage 12 registry {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AnalysisContractError(f"Stage 12 registry must be a mapping: {path}")
    return value


def _validate_metric_registry(value: Mapping[str, object]) -> None:
    if value.get("schema_version") != METRIC_REGISTRY_SCHEMA_VERSION:
        raise AnalysisContractError("unsupported metric registry schema")
    required = {
        "name",
        "version",
        "purpose",
        "scenario_types",
        "required_fields",
        "source_paths",
        "formula",
        "numerator",
        "denominator",
        "aggregation",
        "missing_policy",
        "failure_policy",
        "grouping",
        "statistics",
        "limitations",
        "plots",
        "tables",
        "interpretation_anchor",
    }
    seen: set[str] = set()
    for metric in metric_definitions(value):
        missing = required - set(metric)
        if missing:
            raise AnalysisContractError(
                f"metric {metric.get('name')!r} is missing fields: {sorted(missing)}"
            )
        name = str(metric["name"])
        if name in seen:
            raise AnalysisContractError(f"duplicate metric definition: {name}")
        seen.add(name)


def _validate_plot_report_registry(value: Mapping[str, object]) -> None:
    if value.get("schema_version") != PLOT_REPORT_REGISTRY_SCHEMA_VERSION:
        raise AnalysisContractError("unsupported plot/report registry schema")
    required = {
        "id",
        "question",
        "data_requirements",
        "aggregation",
        "filters",
        "statistics",
        "output",
        "limitations",
        "skip_conditions",
        "interpretation_anchor",
    }
    for kind, definitions in (
        ("plot", plot_definitions(value)),
        ("table", table_definitions(value)),
        ("report", report_definitions(value)),
    ):
        seen: set[str] = set()
        for definition in definitions:
            missing = required - set(definition)
            if missing:
                raise AnalysisContractError(
                    f"{kind} {definition.get('id')!r} is missing fields: {sorted(missing)}"
                )
            identifier = str(definition["id"])
            if identifier in seen:
                raise AnalysisContractError(f"duplicate {kind} definition: {identifier}")
            seen.add(identifier)


def _validate_decision_policy(value: Mapping[str, object]) -> None:
    if value.get("schema_version") != DECISION_POLICY_SCHEMA_VERSION:
        raise AnalysisContractError("unsupported decision-policy schema")
    for field in ("shortlist_rules", "release_gates", "statistics_policy"):
        if not isinstance(value.get(field), Mapping):
            raise AnalysisContractError(f"decision policy {field} must be a mapping")


def _file_identity(path: Path, root: Path) -> dict[str, object]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = resolved.name
    return {"path": relative, "sha256": file_sha256(resolved)}
