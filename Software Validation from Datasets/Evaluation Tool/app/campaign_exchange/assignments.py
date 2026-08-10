"""Deterministic worker assignment creation and validation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

from app.artifact_contracts.atomic import file_sha256, validate_campaign_manifest_pair
from app.artifact_contracts.layout import validate_scenario_id
from app.artifact_contracts.registry import registry_for_campaign
from app.benchmark_contracts.scenario import validate_scenario
from app.campaign_executor.planner import parse_scenario_range, validate_campaign

from .common import (
    CampaignExchangeError,
    atomic_write_yaml,
    content_hash,
    identity_digest,
    read_json_mapping,
    read_yaml_mapping,
    require_git_commit,
    require_no_credentials,
    require_portable_path,
    require_sha256,
    require_worker_id,
    utc_timestamp,
)


WORKER_ASSIGNMENT_SCHEMA_VERSION = "worker-assignment.v1"
WORKER_ASSIGNMENT_HASH_VERSION = "worker-assignment-hash.v1"
WORKER_ASSIGNMENT_ALGORITHM = "sha256"
ASSIGNMENT_HASH_EXCLUSIONS = {
    "assignment_id",
    "assignment_sha256",
    "created_at_utc",
    "notes",
}


def create_worker_assignment(
    campaign_root: Path,
    *,
    worker_id: str,
    expected_git_commit: str,
    expected_environment_profile: str,
    scenario_ids: Sequence[str] | None = None,
    scenario_range: tuple[str, str] | None = None,
    component_filters: Mapping[str, str] | None = None,
    datasets: Sequence[str] | None = None,
    panels: Sequence[str] | None = None,
    partition_index: int | None = None,
    partition_count: int | None = None,
    maximum_scenario_count: int | None = None,
    allow_overlap: bool = False,
    notes: str | None = None,
    created_at: datetime | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Select global scenarios deterministically and publish one assignment YAML."""

    root = campaign_root.resolve()
    validate_campaign(root)
    worker = require_worker_id(worker_id)
    commit = require_git_commit(expected_git_commit)
    profile = str(expected_environment_profile or "").strip()
    if not profile:
        raise CampaignExchangeError("expected environment profile is required")
    if notes is not None and not isinstance(notes, str):
        raise CampaignExchangeError("assignment notes must be text")
    _validate_partition(partition_index, partition_count)
    if maximum_scenario_count is not None and maximum_scenario_count <= 0:
        raise CampaignExchangeError("maximum scenario count must be positive")

    manifest = _campaign_manifest(root)
    scenarios = _campaign_scenarios(root, manifest)
    selected = _select_assignment_scenarios(
        scenarios,
        scenario_ids=scenario_ids,
        scenario_range=scenario_range,
        component_filters=component_filters,
        datasets=datasets,
        panels=panels,
        partition_index=partition_index,
        partition_count=partition_count,
        maximum_scenario_count=maximum_scenario_count,
    )
    seeds = {int(item["seed"]) for item in selected}
    if len(seeds) != 1:
        raise CampaignExchangeError(
            f"one assignment requires one global seed; selected seeds are {sorted(seeds)}"
        )
    identity_catalog, scenario_records = _assignment_identities(selected)
    assignment: dict[str, object] = {
        "schema_version": WORKER_ASSIGNMENT_SCHEMA_VERSION,
        "hash_version": WORKER_ASSIGNMENT_HASH_VERSION,
        "hash_algorithm": WORKER_ASSIGNMENT_ALGORITHM,
        "campaign_id": manifest["campaign_id"],
        "campaign_manifest_sha256": file_sha256(root / "campaign_manifest.json"),
        "benchmark_manifests": [dict(item) for item in manifest["benchmark_manifests"]],
        "worker_id": worker,
        "expected_git_commit": commit,
        "expected_environment_profile": profile,
        "seed": next(iter(seeds)),
        "allow_overlap": bool(allow_overlap),
        "selection": {
            "scenario_ids": sorted(set(scenario_ids or ())),
            "scenario_range": (
                {"start": scenario_range[0], "end": scenario_range[1]}
                if scenario_range is not None
                else None
            ),
            "component_filters": dict(sorted((component_filters or {}).items())),
            "datasets": sorted(set(datasets or ())),
            "panels": sorted(set(panels or ())),
            "deterministic_partition": (
                {
                    "algorithm": "scenario_hash_modulo.v1",
                    "index": partition_index,
                    "count": partition_count,
                }
                if partition_index is not None
                else None
            ),
            "maximum_scenario_count": maximum_scenario_count,
            "ordering": "scenario_id_ascending",
        },
        "scenario_ids": [str(item["scenario_id"]) for item in selected],
        "scenarios": scenario_records,
        "identity_catalog": identity_catalog,
        "created_at_utc": utc_timestamp(created_at),
        "notes": notes,
    }
    digest = content_hash(assignment, ASSIGNMENT_HASH_EXCLUSIONS)
    assignment["assignment_sha256"] = digest
    assignment["assignment_id"] = f"assignment_{digest[:12].lower()}"
    require_no_credentials(assignment, "worker assignment")

    target = output_path or root / "worker_assignments" / f"worker_{worker}.yaml"
    target = target.resolve()
    _require_assignment_path(target, root)
    existing_assignments = _existing_assignments(root, except_path=target)
    overlaps = _overlap_rows(assignment, existing_assignments)
    if overlaps:
        raise CampaignExchangeError(
            "assignment overlaps existing work without bilateral reproducibility permission: "
            f"{overlaps}"
        )
    if target.exists():
        existing = read_yaml_mapping(target)
        validate_worker_assignment(root, existing)
        if existing.get("assignment_sha256") != assignment["assignment_sha256"]:
            raise CampaignExchangeError(f"refusing to overwrite worker assignment: {target}")
        return existing
    atomic_write_yaml(target, assignment)
    validate_worker_assignment(root, target)
    return assignment


def validate_worker_assignment(
    campaign_root: Path,
    assignment: Path | Mapping[str, object],
    *,
    actual_git_commit: str | None = None,
    actual_environment_profile: str | None = None,
) -> dict[str, object]:
    """Validate an assignment against immutable local campaign artifacts."""

    root = campaign_root.resolve()
    validate_campaign(root)
    value = (
        read_yaml_mapping(assignment.resolve())
        if isinstance(assignment, Path)
        else dict(assignment)
    )
    required = {
        "schema_version",
        "hash_version",
        "hash_algorithm",
        "assignment_id",
        "assignment_sha256",
        "campaign_id",
        "campaign_manifest_sha256",
        "benchmark_manifests",
        "worker_id",
        "expected_git_commit",
        "expected_environment_profile",
        "seed",
        "allow_overlap",
        "selection",
        "scenario_ids",
        "scenarios",
        "identity_catalog",
        "created_at_utc",
        "notes",
    }
    missing = required - set(value)
    if missing:
        raise CampaignExchangeError(f"assignment missing fields: {sorted(missing)}")
    if value["schema_version"] != WORKER_ASSIGNMENT_SCHEMA_VERSION:
        raise CampaignExchangeError("unsupported worker assignment schema")
    if value["hash_version"] != WORKER_ASSIGNMENT_HASH_VERSION:
        raise CampaignExchangeError("unsupported worker assignment hash version")
    if value["hash_algorithm"] != WORKER_ASSIGNMENT_ALGORITHM:
        raise CampaignExchangeError("worker assignments require SHA-256")
    digest = content_hash(value, ASSIGNMENT_HASH_EXCLUSIONS)
    if require_sha256(value["assignment_sha256"], "assignment hash") != digest:
        raise CampaignExchangeError("worker assignment content hash mismatch")
    if value["assignment_id"] != f"assignment_{digest[:12].lower()}":
        raise CampaignExchangeError("worker assignment ID mismatch")
    worker = require_worker_id(value["worker_id"])
    _ = worker
    expected_commit = require_git_commit(value["expected_git_commit"])
    profile = str(value["expected_environment_profile"] or "").strip()
    if not profile:
        raise CampaignExchangeError("expected environment profile is missing")
    if not isinstance(value["allow_overlap"], bool):
        raise CampaignExchangeError("allow_overlap must be boolean")
    require_no_credentials(value, "worker assignment")

    manifest = _campaign_manifest(root)
    if value["campaign_id"] != manifest["campaign_id"]:
        raise CampaignExchangeError("assignment campaign ID mismatch")
    if value["campaign_manifest_sha256"] != file_sha256(
        root / "campaign_manifest.json"
    ):
        raise CampaignExchangeError("assignment campaign manifest hash mismatch")
    if value["benchmark_manifests"] != manifest["benchmark_manifests"]:
        raise CampaignExchangeError("assignment benchmark manifest identities mismatch")
    _validate_benchmark_files(root, value["benchmark_manifests"])

    raw_ids = value["scenario_ids"]
    raw_records = value["scenarios"]
    if not isinstance(raw_ids, list) or not raw_ids:
        raise CampaignExchangeError("assignment scenario_ids must be a non-empty list")
    if any(not isinstance(item, str) for item in raw_ids):
        raise CampaignExchangeError("assignment scenario IDs must be strings")
    scenario_ids = [str(item) for item in raw_ids]
    if scenario_ids != sorted(set(scenario_ids)):
        raise CampaignExchangeError("assignment scenario IDs must be unique and sorted")
    for scenario_id in scenario_ids:
        validate_scenario_id(scenario_id)
    if not isinstance(raw_records, list) or any(
        not isinstance(item, Mapping) for item in raw_records
    ):
        raise CampaignExchangeError("assignment scenarios must be a mapping list")
    records = [dict(item) for item in raw_records]
    if [item.get("scenario_id") for item in records] != scenario_ids:
        raise CampaignExchangeError("assignment scenario record ordering mismatch")

    scenarios = {item["scenario_id"]: item for item in _campaign_scenarios(root, manifest)}
    unknown = set(scenario_ids) - set(scenarios)
    if unknown:
        raise CampaignExchangeError(f"assignment references unknown scenarios: {sorted(unknown)}")
    catalog = value["identity_catalog"]
    if not isinstance(catalog, Mapping):
        raise CampaignExchangeError("assignment identity catalog must be a mapping")
    expected_catalog, expected_records = _assignment_identities(
        [scenarios[scenario_id] for scenario_id in scenario_ids]
    )
    if dict(catalog) != expected_catalog or records != expected_records:
        raise CampaignExchangeError("assignment component/model/scenario identities mismatch")
    expected_seed = int(value["seed"])
    if any(int(scenarios[item]["seed"]) != expected_seed for item in scenario_ids):
        raise CampaignExchangeError("assignment seed mismatch")

    if actual_git_commit is not None and require_git_commit(actual_git_commit) != expected_commit:
        raise CampaignExchangeError("local Git commit differs from worker assignment")
    if actual_environment_profile is not None and actual_environment_profile != profile:
        raise CampaignExchangeError("local environment profile differs from worker assignment")
    return {
        "schema_version": "worker-assignment-validation.v1",
        "assignment_id": value["assignment_id"],
        "campaign_id": value["campaign_id"],
        "worker_id": value["worker_id"],
        "scenario_count": len(scenario_ids),
        "scenario_ids": scenario_ids,
        "valid": True,
    }


def validate_assignment_set(
    campaign_root: Path,
    assignment_paths: Sequence[Path] | None = None,
) -> dict[str, object]:
    """Validate assignments together and expose overlap and missing global work."""

    root = campaign_root.resolve()
    manifest = _campaign_manifest(root)
    paths = list(assignment_paths or sorted((root / "worker_assignments").glob("*.yaml")))
    if not paths:
        raise CampaignExchangeError("no worker assignments were supplied")
    assignments: list[dict[str, object]] = []
    validations: list[dict[str, object]] = []
    for path in paths:
        value = read_yaml_mapping(path.resolve())
        validations.append(validate_worker_assignment(root, value))
        assignments.append(value)
    overlaps = _all_overlaps(assignments)
    forbidden = [item for item in overlaps if not item["allowed"]]
    if forbidden:
        raise CampaignExchangeError(f"worker assignments overlap: {forbidden}")
    commits = {str(item["expected_git_commit"]) for item in assignments}
    if len(commits) > 1:
        raise CampaignExchangeError(
            f"worker assignments expect different Git commits: {sorted(commits)}"
        )
    assigned = sorted(
        {str(item) for assignment in assignments for item in assignment["scenario_ids"]}
    )
    missing = sorted(set(manifest["scenario_ids"]) - set(assigned))
    return {
        "schema_version": "worker-assignment-set-validation.v1",
        "campaign_id": manifest["campaign_id"],
        "assignments": validations,
        "overlaps": overlaps,
        "assigned_scenario_count": len(assigned),
        "missing_scenario_ids": missing,
        "valid": True,
    }


def current_git_commit(repository_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root.resolve(),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise CampaignExchangeError("cannot determine repository Git commit") from exc
    return require_git_commit(result.stdout.strip())


def _select_assignment_scenarios(
    scenarios: Sequence[Mapping[str, object]],
    *,
    scenario_ids: Sequence[str] | None,
    scenario_range: tuple[str, str] | None,
    component_filters: Mapping[str, str] | None,
    datasets: Sequence[str] | None,
    panels: Sequence[str] | None,
    partition_index: int | None,
    partition_count: int | None,
    maximum_scenario_count: int | None,
) -> list[dict[str, object]]:
    requested = set(scenario_ids or ())
    known = {str(item["scenario_id"]) for item in scenarios}
    missing = requested - known
    if missing:
        raise CampaignExchangeError(f"unknown requested scenario IDs: {sorted(missing)}")
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
        data_slice = scenario.get("dataset_slice")
        dataset = data_slice.get("dataset") if isinstance(data_slice, Mapping) else None
        if datasets and dataset not in datasets:
            continue
        if panels and scenario.get("panel") not in panels:
            continue
        if component_filters and not _components_match(scenario, component_filters):
            continue
        if partition_index is not None and int(str(scenario["scenario_hash"]), 16) % int(
            partition_count
        ) != partition_index:
            continue
        selected.append(scenario)
    if maximum_scenario_count is not None:
        selected = selected[:maximum_scenario_count]
    if not selected:
        raise CampaignExchangeError("assignment selectors matched no campaign scenarios")
    return selected


def _assignment_identities(
    scenarios: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    component_catalog: dict[str, object] = {}
    model_catalog: dict[str, object] = {}
    records: list[dict[str, object]] = []
    for scenario in sorted(scenarios, key=lambda item: str(item["scenario_id"])):
        pipeline = scenario.get("pipeline")
        if not isinstance(pipeline, Mapping):
            raise CampaignExchangeError("scenario pipeline identity is missing")
        components = pipeline.get("components")
        models = pipeline.get("models")
        if not isinstance(components, Mapping) or not isinstance(models, Mapping):
            raise CampaignExchangeError("scenario component/model identities are missing")
        component_ids: list[str] = []
        for family, raw in sorted(components.items()):
            if not isinstance(raw, Mapping):
                raise CampaignExchangeError(f"invalid component identity: {family}")
            summary = {
                "family": str(family),
                "name": raw.get("name"),
                "enabled": raw.get("enabled"),
                "implementation_class": raw.get("implementation_class"),
                "qualification_status": raw.get("qualification_status"),
                "source_config_sha256": raw.get("source_config_sha256"),
                "config_contents_sha256": raw.get("config_contents_sha256"),
            }
            digest = identity_digest(summary)
            component_catalog.setdefault(digest, summary)
            component_ids.append(digest)
        model_ids: list[str] = []
        for family, raw in sorted(models.items()):
            if not isinstance(raw, Mapping):
                raise CampaignExchangeError(f"invalid model identity: {family}")
            raw_assets = raw.get("assets")
            if not isinstance(raw_assets, list):
                raise CampaignExchangeError(f"invalid model asset identity: {family}")
            assets = []
            for asset in raw_assets:
                if not isinstance(asset, Mapping):
                    raise CampaignExchangeError(f"invalid model asset row: {family}")
                assets.append(
                    {
                        key: asset.get(key)
                        for key in (
                            "configured_identity",
                            "expected_bytes",
                            "expected_sha256",
                            "observed_bytes",
                            "observed_sha256",
                            "present",
                            "hash_matches",
                        )
                    }
                )
            summary = {
                "family": str(family),
                "model_identity": raw.get("model_identity"),
                "assets": assets,
            }
            digest = identity_digest(summary)
            model_catalog.setdefault(digest, summary)
            model_ids.append(digest)
        data_slice = scenario.get("dataset_slice")
        benchmark = scenario.get("benchmark_manifest")
        if not isinstance(data_slice, Mapping) or not isinstance(benchmark, Mapping):
            raise CampaignExchangeError("scenario dataset or benchmark identity is missing")
        records.append(
            {
                "scenario_id": scenario["scenario_id"],
                "scenario_hash": scenario["scenario_hash"],
                "panel": scenario["panel"],
                "dataset": data_slice["dataset"],
                "benchmark_manifest_id": benchmark["manifest_id"],
                "benchmark_manifest_sha256": benchmark["sha256"],
                "seed": scenario["seed"],
                "component_identity_sha256": component_ids,
                "model_identity_sha256": model_ids,
            }
        )
    return (
        {
            "components": dict(sorted(component_catalog.items())),
            "models": dict(sorted(model_catalog.items())),
        },
        records,
    )


def assignment_environment_hashes(
    assignment: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Convert assignment identity catalogs to environment-fingerprint hash maps."""

    catalog = assignment.get("identity_catalog")
    if not isinstance(catalog, Mapping):
        raise CampaignExchangeError("assignment identity catalog is missing")
    components = catalog.get("components")
    models = catalog.get("models")
    if not isinstance(components, Mapping) or not isinstance(models, Mapping):
        raise CampaignExchangeError("assignment identity catalogs are invalid")
    component_hashes = {f"component_{index:04d}": digest for index, digest in enumerate(sorted(components))}
    model_hashes = {f"model_{index:04d}": digest for index, digest in enumerate(sorted(models))}
    return model_hashes, component_hashes


def _campaign_manifest(root: Path) -> dict[str, object]:
    validate_campaign_manifest_pair(root, registry=registry_for_campaign(root))
    return read_json_mapping(root / "campaign_manifest.json")


def _campaign_scenarios(
    root: Path, manifest: Mapping[str, object]
) -> list[dict[str, object]]:
    scenarios = []
    for scenario_id in manifest["scenario_ids"]:
        path = root / "scenarios" / str(scenario_id) / "resolved_scenario.json"
        scenario = read_json_mapping(path)
        validate_scenario(scenario)
        if scenario["scenario_id"] != scenario_id:
            raise CampaignExchangeError(f"scenario directory identity mismatch: {scenario_id}")
        scenarios.append(scenario)
    return scenarios


def _campaign_scenario(root: Path, scenario_id: str) -> dict[str, object]:
    scenario = read_json_mapping(root / "scenarios" / scenario_id / "resolved_scenario.json")
    validate_scenario(scenario)
    return scenario


def _validate_benchmark_files(root: Path, raw: object) -> None:
    if not isinstance(raw, list) or any(not isinstance(item, Mapping) for item in raw):
        raise CampaignExchangeError("benchmark manifest identities must be a mapping list")
    for item in raw:
        relative = require_portable_path(item.get("path"))
        expected = require_sha256(item.get("sha256"), "benchmark manifest hash")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise CampaignExchangeError("benchmark path escapes campaign") from exc
        if not path.is_file() or file_sha256(path) != expected:
            raise CampaignExchangeError(f"benchmark manifest is missing or changed: {relative}")


def _components_match(
    scenario: Mapping[str, object], filters: Mapping[str, str]
) -> bool:
    pipeline = scenario.get("pipeline")
    components = pipeline.get("components") if isinstance(pipeline, Mapping) else None
    if not isinstance(components, Mapping):
        return False
    for family, name in filters.items():
        component = components.get(family)
        if not isinstance(component, Mapping) or component.get("name") != name:
            return False
    return True


def _validate_partition(index: int | None, count: int | None) -> None:
    if (index is None) != (count is None):
        raise CampaignExchangeError("partition index and count must be supplied together")
    if index is not None and (count is None or count < 2 or index < 0 or index >= count):
        raise CampaignExchangeError("partition requires count >= 2 and 0 <= index < count")


def _require_assignment_path(path: Path, campaign_root: Path) -> None:
    assignment_root = (campaign_root / "worker_assignments").resolve()
    try:
        path.relative_to(assignment_root)
    except ValueError as exc:
        raise CampaignExchangeError("worker assignment must remain under worker_assignments") from exc
    if path.parent != assignment_root or path.suffix.lower() != ".yaml":
        raise CampaignExchangeError("worker assignment must be a direct YAML file")


def _existing_assignments(
    campaign_root: Path, *, except_path: Path
) -> list[dict[str, object]]:
    values = []
    for path in sorted((campaign_root / "worker_assignments").glob("*.yaml")):
        if path.resolve() == except_path:
            continue
        value = read_yaml_mapping(path)
        validate_worker_assignment(campaign_root, value)
        values.append(value)
    return values


def _overlap_rows(
    candidate: Mapping[str, object], existing: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    rows = []
    candidate_ids = set(candidate["scenario_ids"])
    for other in existing:
        overlap = sorted(candidate_ids & set(other["scenario_ids"]))
        allowed = bool(candidate["allow_overlap"] and other["allow_overlap"])
        if overlap and not allowed:
            rows.append(
                {
                    "workers": sorted([candidate["worker_id"], other["worker_id"]]),
                    "scenario_ids": overlap,
                }
            )
    return rows


def _all_overlaps(assignments: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rows = []
    for index, first in enumerate(assignments):
        for second in assignments[index + 1 :]:
            overlap = sorted(set(first["scenario_ids"]) & set(second["scenario_ids"]))
            if overlap:
                rows.append(
                    {
                        "workers": sorted([first["worker_id"], second["worker_id"]]),
                        "scenario_ids": overlap,
                        "allowed": bool(first["allow_overlap"] and second["allow_overlap"]),
                    }
                )
    return rows


__all__ = [
    "WORKER_ASSIGNMENT_SCHEMA_VERSION",
    "assignment_environment_hashes",
    "create_worker_assignment",
    "current_git_commit",
    "parse_scenario_range",
    "validate_assignment_set",
    "validate_worker_assignment",
]
