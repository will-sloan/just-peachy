"""Deterministic campaign planning from frozen Stage 2 scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import uuid

import yaml

from app.artifact_contracts.atomic import (
    ScenarioArtifactStore,
    file_sha256,
    publish_campaign_manifest,
    validate_campaign_manifest_pair,
)
from app.artifact_contracts.layout import CampaignLayout
from app.artifact_contracts.registry import (
    ArtifactRegistry,
    registry_for_campaign,
)
from app.artifact_contracts.schemas import validate_artifact
from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.scenario import validate_scenario
from app.benchmark_contracts.versions import SCENARIO_SCHEMA_VERSION
from app.campaign_executor.state import CampaignStateError, CampaignStateStore


CAMPAIGN_MANIFEST_VERSION = "campaign-manifest.v1"


class CampaignPlanError(RuntimeError):
    """Raised when a campaign cannot be planned without changing identity."""


@dataclass(frozen=True)
class CampaignPlan:
    campaign_id: str
    campaign_root: Path
    scenario_ids: tuple[str, ...]
    benchmark_manifests: tuple[Mapping[str, object], ...]
    dry_run: bool

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": "campaign-plan-summary.v1",
            "campaign_id": self.campaign_id,
            "campaign_root": str(self.campaign_root),
            "scenario_count": len(self.scenario_ids),
            "scenario_ids": list(self.scenario_ids),
            "benchmark_manifests": [dict(item) for item in self.benchmark_manifests],
            "dry_run": self.dry_run,
        }


def load_scenario_catalog(path: Path) -> list[dict[str, object]]:
    """Load and fully validate a Stage 2 JSONL scenario catalog."""

    catalog_path = path.resolve()
    scenarios: list[dict[str, object]] = []
    seen: set[str] = set()
    with catalog_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CampaignPlanError(
                    f"invalid scenario JSON at line {line_number}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise CampaignPlanError(f"scenario line {line_number} is not an object")
            validate_scenario(value)
            scenario_id = str(value["scenario_id"])
            if scenario_id in seen:
                raise CampaignPlanError(f"duplicate scenario ID in catalog: {scenario_id}")
            seen.add(scenario_id)
            scenarios.append(value)
    if not scenarios:
        raise CampaignPlanError("scenario catalog is empty")
    return sorted(scenarios, key=lambda item: str(item["scenario_id"]))


def select_scenarios(
    scenarios: Iterable[Mapping[str, object]],
    *,
    scenario_ids: Sequence[str] | None = None,
    scenario_range: tuple[str, str] | None = None,
    panels: Sequence[str] | None = None,
    tiers: Sequence[str] | None = None,
    component_filters: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    """Apply stable identity/config filters without relying on catalog row order."""

    requested = set(scenario_ids or ())
    selected: list[dict[str, object]] = []
    for raw in sorted(scenarios, key=lambda item: str(item["scenario_id"])):
        scenario = dict(raw)
        scenario_id = str(scenario["scenario_id"])
        if requested and scenario_id not in requested:
            continue
        if scenario_range is not None and not (
            scenario_range[0] <= scenario_id <= scenario_range[1]
        ):
            continue
        if panels and str(scenario.get("panel")) not in panels:
            continue
        if tiers and str(scenario.get("tier")) not in tiers:
            continue
        if component_filters and not _components_match(scenario, component_filters):
            continue
        selected.append(scenario)
    found = {str(item["scenario_id"]) for item in selected}
    missing = requested - found
    if missing:
        raise CampaignPlanError(f"requested scenario IDs were not selected: {sorted(missing)}")
    if not selected:
        raise CampaignPlanError("scenario filters selected no work")
    return selected


def plan_campaign(
    *,
    scenario_catalog: Path,
    automated_runs_root: Path,
    campaign_id: str | None = None,
    scenario_ids: Sequence[str] | None = None,
    scenario_range: tuple[str, str] | None = None,
    panels: Sequence[str] | None = None,
    tiers: Sequence[str] | None = None,
    component_filters: Mapping[str, str] | None = None,
    default_max_retries: int = 0,
    dry_run: bool = False,
    registry: ArtifactRegistry | None = None,
    created_at: datetime | None = None,
) -> CampaignPlan:
    """Create immutable campaign files and transactional scenario queue state."""

    if default_max_retries < 0:
        raise CampaignPlanError("default_max_retries must be nonnegative")
    active_registry = registry or ArtifactRegistry.load()
    catalog_path = scenario_catalog.resolve()
    all_scenarios = load_scenario_catalog(catalog_path)
    selected = select_scenarios(
        all_scenarios,
        scenario_ids=scenario_ids,
        scenario_range=scenario_range,
        panels=panels,
        tiers=tiers,
        component_filters=component_filters,
    )
    selected_ids = tuple(str(item["scenario_id"]) for item in selected)
    resolved_campaign_id = campaign_id or _campaign_id(catalog_path, selected_ids)
    layout = CampaignLayout.resolve(automated_runs_root, resolved_campaign_id)
    benchmark_sources = _benchmark_sources(catalog_path.parent, selected)
    benchmark_records = tuple(
        {
            "manifest_id": identity["manifest_id"],
            "path": f"benchmark_manifests/{source.name}",
            "sha256": identity["sha256"],
        }
        for source, identity in benchmark_sources
    )
    plan = CampaignPlan(
        campaign_id=resolved_campaign_id,
        campaign_root=layout.campaign_root,
        scenario_ids=selected_ids,
        benchmark_manifests=benchmark_records,
        dry_run=dry_run,
    )
    if dry_run:
        return plan

    layout.create(selected_ids)
    for (source, identity), record in zip(benchmark_sources, benchmark_records, strict=True):
        target = layout.campaign_root / str(record["path"])
        _copy_immutable(source, target, expected_sha256=str(identity["sha256"]))
        validate_artifact(target, active_registry.get("benchmark_manifest"))

    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise CampaignPlanError("campaign creation time must be timezone-aware")
    manifest = {
        "schema_version": CAMPAIGN_MANIFEST_VERSION,
        "campaign_id": resolved_campaign_id,
        "created_at_utc": _timestamp(timestamp),
        "artifact_registry_version": active_registry.schema_version,
        "scenario_schema_version": SCENARIO_SCHEMA_VERSION,
        "benchmark_manifests": [dict(item) for item in benchmark_records],
        "scenario_ids": list(selected_ids),
        "planning": {
            "schema_version": "campaign-planning-provenance.v1",
            "scenario_catalog_sha256": file_sha256(catalog_path),
            "scenario_order": "scenario_id_ascending",
            "default_max_retries": default_max_retries,
        },
    }
    manifest_path = layout.campaign_root / "campaign_manifest.json"
    if manifest_path.exists():
        validate_campaign_manifest_pair(layout.campaign_root, registry=active_registry)
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        _require_existing_campaign_matches(existing, manifest)
    else:
        publish_campaign_manifest(layout.campaign_root, manifest, registry=active_registry)

    database = CampaignStateStore(layout.campaign_root / "database" / "campaign.sqlite")
    database.register_campaign(resolved_campaign_id, file_sha256(manifest_path))
    registrations: list[dict[str, object]] = []
    for scenario in selected:
        scenario_id = str(scenario["scenario_id"])
        scenario_root = layout.scenario_root(scenario_id)
        store = ScenarioArtifactStore(scenario_root, scenario_id, registry=active_registry)
        _publish_json_if_absent_or_equal(
            store,
            scenario_root / "resolved_scenario.json",
            "resolved_scenario.json",
            scenario,
        )
        benchmark_name = Path(str(scenario["benchmark_manifest"]["path"])).name
        run_config = {
            "schema_version": "run-config.v1",
            "artifact_registry_version": active_registry.schema_version,
            "scenario_id": scenario_id,
            "scenario_hash": scenario["scenario_hash"],
            "settings": {
                "benchmark_manifest": f"benchmark_manifests/{benchmark_name}",
                "pipeline_id": scenario["pipeline"]["pipeline_id"],
                "condition_id": scenario["condition"]["id"],
                "execution_order": "scenario_id_ascending",
                "implicit_model_downloads_prohibited": True,
            },
        }
        _publish_yaml_if_absent_or_equal(
            store,
            scenario_root / "run_config.yaml",
            "run_config.yaml",
            run_config,
        )
        scenario_retries = _scenario_max_retries(scenario, default_max_retries)
        registrations.append(
            {
                "scenario_id": scenario_id,
                "scenario_hash": scenario["scenario_hash"],
                "max_attempts": scenario_retries + 1,
                "expected_artifacts": active_registry.required_artifact_ids(scenario),
            }
        )
    database.register_scenarios(resolved_campaign_id, registrations)
    validate_campaign(layout.campaign_root, registry=active_registry)
    return plan


def validate_campaign(
    campaign_root: Path,
    *,
    registry: ArtifactRegistry | None = None,
) -> dict[str, object]:
    """Validate immutable campaign identity, database schema, and queued scenarios."""

    active_registry = registry or registry_for_campaign(campaign_root)
    root = campaign_root.resolve()
    validate_campaign_manifest_pair(root, registry=active_registry)
    manifest = json.loads((root / "campaign_manifest.json").read_text(encoding="utf-8"))
    campaign_id = str(manifest["campaign_id"])
    validate_artifact(
        root / "database" / "campaign.sqlite",
        active_registry.get("campaign_database"),
    )
    state = CampaignStateStore(root / "database" / "campaign.sqlite")
    summary = state.summary(campaign_id)
    if summary["manifest_sha256"] != file_sha256(root / "campaign_manifest.json"):
        raise CampaignStateError("campaign database manifest identity does not match disk")
    manifest_ids = tuple(str(item) for item in manifest["scenario_ids"])
    queued = state.scenarios(campaign_id)
    queued_ids = tuple(item.scenario_id for item in queued)
    if queued_ids != manifest_ids:
        raise CampaignStateError("campaign database scenario ordering differs from manifest")
    for record in queued:
        path = root / "scenarios" / record.scenario_id / "resolved_scenario.json"
        scenario = json.loads(path.read_text(encoding="utf-8"))
        validate_scenario(scenario)
        if scenario["scenario_hash"] != record.scenario_hash:
            raise CampaignStateError(f"queued hash mismatch for {record.scenario_id}")
    return {
        "schema_version": "campaign-validation.v1",
        "campaign_id": campaign_id,
        "scenario_count": len(queued),
        "state_counts": summary["state_counts"],
        "valid": True,
    }


def parse_scenario_range(value: str | None) -> tuple[str, str] | None:
    if value is None:
        return None
    parts = value.split(":", 1)
    if len(parts) != 2 or not all(part.startswith("scenario_") for part in parts):
        raise CampaignPlanError("scenario range must be START:END using full scenario IDs")
    if parts[0] > parts[1]:
        raise CampaignPlanError("scenario range start must not exceed end")
    return parts[0], parts[1]


def _components_match(
    scenario: Mapping[str, object],
    filters: Mapping[str, str],
) -> bool:
    pipeline = scenario.get("pipeline")
    components = pipeline.get("components") if isinstance(pipeline, Mapping) else None
    if not isinstance(components, Mapping):
        return False
    for family, expected in filters.items():
        component = components.get(family)
        if not isinstance(component, Mapping) or component.get("name") != expected:
            return False
    return True


def _benchmark_sources(
    catalog_root: Path,
    scenarios: Sequence[Mapping[str, object]],
) -> list[tuple[Path, Mapping[str, object]]]:
    identities: dict[str, tuple[Path, Mapping[str, object]]] = {}
    for scenario in scenarios:
        identity = scenario.get("benchmark_manifest")
        if not isinstance(identity, Mapping):
            raise CampaignPlanError("scenario benchmark manifest identity is missing")
        source = (catalog_root / str(identity["path"])).resolve()
        if not source.is_file():
            raise CampaignPlanError(f"benchmark manifest is missing: {source}")
        observed = file_sha256(source)
        if observed != identity.get("sha256"):
            raise CampaignPlanError(f"benchmark manifest hash mismatch: {source.name}")
        manifest_id = str(identity["manifest_id"])
        previous = identities.get(manifest_id)
        if previous is not None and previous[0] != source:
            raise CampaignPlanError(f"manifest ID resolves to multiple files: {manifest_id}")
        identities[manifest_id] = (source, dict(identity))
    return [identities[key] for key in sorted(identities)]


def _copy_immutable(source: Path, target: Path, *, expected_sha256: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if file_sha256(target) != expected_sha256:
            raise CampaignPlanError(f"refusing to overwrite changed artifact: {target}")
        return
    temporary = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex}")
    try:
        with source.open("rb") as source_handle, temporary.open("wb") as target_handle:
            for chunk in iter(lambda: source_handle.read(1024 * 1024), b""):
                target_handle.write(chunk)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        if file_sha256(temporary) != expected_sha256:
            raise CampaignPlanError(f"copied artifact hash mismatch: {target}")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _publish_json_if_absent_or_equal(
    store: ScenarioArtifactStore,
    path: Path,
    relative_path: str,
    value: Mapping[str, object],
) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != value:
            raise CampaignPlanError(f"refusing to overwrite existing {relative_path}")
        return
    store.publish_json(relative_path, value)


def _publish_yaml_if_absent_or_equal(
    store: ScenarioArtifactStore,
    path: Path,
    relative_path: str,
    value: Mapping[str, object],
) -> None:
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8"))
        if existing != value:
            raise CampaignPlanError(f"refusing to overwrite existing {relative_path}")
        return
    store.publish_yaml(relative_path, value)


def _campaign_id(catalog_path: Path, scenario_ids: Sequence[str]) -> str:
    digest = canonical_sha256(
        {
            "schema_version": "campaign-plan-identity.v1",
            "scenario_catalog_sha256": file_sha256(catalog_path),
            "scenario_ids": list(scenario_ids),
        }
    )
    return f"campaign_{digest[:12].lower()}"


def _scenario_max_retries(
    scenario: Mapping[str, object],
    default_max_retries: int,
) -> int:
    policy = scenario.get("failure_policy")
    if isinstance(policy, Mapping) and "max_scenario_retries" in policy:
        value = int(policy["max_scenario_retries"])
        if value < 0:
            raise CampaignPlanError("max_scenario_retries must be nonnegative")
        return value
    return default_max_retries


def _require_existing_campaign_matches(
    existing: Mapping[str, object],
    requested: Mapping[str, object],
) -> None:
    for field in (
        "schema_version",
        "campaign_id",
        "artifact_registry_version",
        "scenario_schema_version",
        "benchmark_manifests",
        "scenario_ids",
        "planning",
    ):
        if existing.get(field) != requested.get(field):
            raise CampaignPlanError(
                f"existing campaign manifest differs in immutable field {field}"
            )


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )
