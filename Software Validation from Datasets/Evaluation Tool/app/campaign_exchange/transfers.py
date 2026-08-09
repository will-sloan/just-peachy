"""Independent worker-result packaging and transfer validation."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Mapping
import uuid

from app.artifact_contracts.atomic import file_sha256
from app.artifact_contracts.completion import validate_scenario_completion
from app.artifact_contracts.environment import (
    collect_environment_fingerprint,
    validate_environment_fingerprint,
)

from .assignments import (
    assignment_environment_hashes,
    validate_worker_assignment,
)
from .common import (
    CampaignExchangeError,
    atomic_copy_tree,
    atomic_write_json,
    atomic_write_yaml,
    content_hash,
    directory_inventory,
    directory_sha256,
    read_json_mapping,
    read_yaml_mapping,
    require_inventory,
    require_no_credentials,
    require_portable_path,
    require_sha256,
    utc_timestamp,
)


WORKER_TRANSFER_SCHEMA_VERSION = "worker-result-transfer.v1"
WORKER_TRANSFER_HASH_VERSION = "worker-result-transfer-hash.v1"
TRANSFER_HASH_EXCLUSIONS = {"transfer_id", "transfer_sha256", "created_at_utc"}


def export_worker_results(
    campaign_root: Path,
    assignment_path: Path,
    destination: Path,
    *,
    repository_root: Path | None = None,
    actual_git_commit: str | None = None,
    actual_environment_profile: str | None = None,
    environment_fingerprint: Mapping[str, object] | None = None,
    created_at: datetime | None = None,
) -> dict[str, object]:
    """Package complete assigned scenario folders without copying campaign SQLite."""

    campaign = campaign_root.resolve()
    assignment_file = assignment_path.resolve()
    assignment = read_yaml_mapping(assignment_file)
    expected_profile = str(assignment.get("expected_environment_profile") or "")
    validate_worker_assignment(
        campaign,
        assignment,
        actual_git_commit=actual_git_commit,
        actual_environment_profile=actual_environment_profile or expected_profile,
    )
    model_hashes, component_hashes = assignment_environment_hashes(assignment)
    if environment_fingerprint is None:
        if repository_root is None:
            raise CampaignExchangeError(
                "repository_root is required when collecting an environment fingerprint"
            )
        fingerprint = collect_environment_fingerprint(
            repository_root,
            profile_identity=expected_profile,
            model_hashes=model_hashes,
            component_config_hashes=component_hashes,
        )
    else:
        fingerprint = dict(environment_fingerprint)
    validate_environment_fingerprint(fingerprint)
    _validate_fingerprint_against_assignment(fingerprint, assignment)

    final_root = destination.resolve()
    if final_root.exists():
        raise CampaignExchangeError(f"refusing to overwrite transfer destination: {final_root}")
    final_root.parent.mkdir(parents=True, exist_ok=True)
    staging = final_root.with_name(f".{final_root.name}.tmp-{uuid.uuid4().hex}")
    try:
        staging.mkdir(parents=True)
        assignment_target = staging / "worker_assignment.yaml"
        fingerprint_target = staging / "environment_fingerprint.json"
        atomic_write_yaml(assignment_target, assignment)
        atomic_write_json(fingerprint_target, fingerprint)

        results: list[dict[str, object]] = []
        incomplete: list[dict[str, object]] = []
        scenario_records = {
            str(item["scenario_id"]): dict(item)
            for item in assignment["scenarios"]
            if isinstance(item, Mapping)
        }
        for scenario_id in assignment["scenario_ids"]:
            source = campaign / "scenarios" / str(scenario_id)
            completion = validate_scenario_completion(source)
            if not completion.complete:
                incomplete.append(
                    {
                        "scenario_id": scenario_id,
                        "state": completion.state,
                        "issues": [item.to_jsonable() for item in completion.issues],
                    }
                )
                continue
            target = staging / "scenarios" / str(scenario_id)
            atomic_copy_tree(source, target)
            inventory = directory_inventory(target)
            record = scenario_records[str(scenario_id)]
            results.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_hash": record["scenario_hash"],
                    "relative_path": f"scenarios/{scenario_id}",
                    "file_count": len(inventory),
                    "tree_sha256": directory_sha256(target),
                    "files": inventory,
                }
            )
        manifest: dict[str, object] = {
            "schema_version": WORKER_TRANSFER_SCHEMA_VERSION,
            "hash_version": WORKER_TRANSFER_HASH_VERSION,
            "hash_algorithm": "sha256",
            "campaign_id": assignment["campaign_id"],
            "campaign_manifest_sha256": assignment["campaign_manifest_sha256"],
            "assignment_id": assignment["assignment_id"],
            "assignment_sha256": assignment["assignment_sha256"],
            "worker_id": assignment["worker_id"],
            "expected_git_commit": assignment["expected_git_commit"],
            "expected_environment_profile": assignment["expected_environment_profile"],
            "environment_fingerprint_id": fingerprint["fingerprint_id"],
            "environment_fingerprint_sha256": fingerprint["fingerprint_sha256"],
            "supporting_files": {
                "worker_assignment": _file_record(assignment_target),
                "environment_fingerprint": _file_record(fingerprint_target),
            },
            "scenario_results": results,
            "unexported_scenarios": incomplete,
            "created_at_utc": utc_timestamp(created_at),
        }
        digest = content_hash(manifest, TRANSFER_HASH_EXCLUSIONS)
        manifest["transfer_sha256"] = digest
        manifest["transfer_id"] = f"transfer_{digest[:12].lower()}"
        require_no_credentials(manifest, "worker result transfer")
        atomic_write_json(staging / "transfer_manifest.json", manifest)
        validate_worker_transfer(staging, campaign_root=campaign)
        os.replace(staging, final_root)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def validate_worker_transfer(
    transfer_root: Path,
    *,
    campaign_root: Path,
) -> dict[str, object]:
    """Validate a copied transfer independently from the source campaign database."""

    root = transfer_root.resolve()
    campaign = campaign_root.resolve()
    manifest = read_json_mapping(root / "transfer_manifest.json")
    required = {
        "schema_version",
        "hash_version",
        "hash_algorithm",
        "transfer_id",
        "transfer_sha256",
        "campaign_id",
        "campaign_manifest_sha256",
        "assignment_id",
        "assignment_sha256",
        "worker_id",
        "expected_git_commit",
        "expected_environment_profile",
        "environment_fingerprint_id",
        "environment_fingerprint_sha256",
        "supporting_files",
        "scenario_results",
        "unexported_scenarios",
        "created_at_utc",
    }
    missing = required - set(manifest)
    if missing:
        raise CampaignExchangeError(f"transfer manifest missing fields: {sorted(missing)}")
    if manifest["schema_version"] != WORKER_TRANSFER_SCHEMA_VERSION:
        raise CampaignExchangeError("unsupported worker transfer schema")
    if manifest["hash_version"] != WORKER_TRANSFER_HASH_VERSION:
        raise CampaignExchangeError("unsupported worker transfer hash version")
    if manifest["hash_algorithm"] != "sha256":
        raise CampaignExchangeError("worker transfers require SHA-256")
    digest = content_hash(manifest, TRANSFER_HASH_EXCLUSIONS)
    if require_sha256(manifest["transfer_sha256"], "transfer hash") != digest:
        raise CampaignExchangeError("worker transfer content hash mismatch")
    if manifest["transfer_id"] != f"transfer_{digest[:12].lower()}":
        raise CampaignExchangeError("worker transfer ID mismatch")
    require_no_credentials(manifest, "worker result transfer")

    supporting = manifest["supporting_files"]
    if not isinstance(supporting, Mapping):
        raise CampaignExchangeError("transfer supporting files are invalid")
    assignment_path = _validate_supporting_file(root, supporting, "worker_assignment")
    fingerprint_path = _validate_supporting_file(
        root, supporting, "environment_fingerprint"
    )
    assignment = read_yaml_mapping(assignment_path)
    validate_worker_assignment(campaign, assignment)
    if manifest["assignment_id"] != assignment["assignment_id"] or manifest[
        "assignment_sha256"
    ] != assignment["assignment_sha256"]:
        raise CampaignExchangeError("transfer assignment identity mismatch")
    for field in (
        "campaign_id",
        "campaign_manifest_sha256",
        "worker_id",
        "expected_git_commit",
        "expected_environment_profile",
    ):
        if manifest[field] != assignment[field]:
            raise CampaignExchangeError(f"transfer/assignment {field} mismatch")

    fingerprint = read_json_mapping(fingerprint_path)
    validate_environment_fingerprint(fingerprint)
    _validate_fingerprint_against_assignment(fingerprint, assignment)
    if manifest["environment_fingerprint_id"] != fingerprint["fingerprint_id"] or manifest[
        "environment_fingerprint_sha256"
    ] != fingerprint["fingerprint_sha256"]:
        raise CampaignExchangeError("transfer environment fingerprint identity mismatch")

    raw_results = manifest["scenario_results"]
    if not isinstance(raw_results, list) or any(
        not isinstance(item, Mapping) for item in raw_results
    ):
        raise CampaignExchangeError("transfer scenario results must be a mapping list")
    assignment_records = {
        str(item["scenario_id"]): dict(item)
        for item in assignment["scenarios"]
        if isinstance(item, Mapping)
    }
    result_ids: list[str] = []
    completion_reports = []
    for raw in raw_results:
        result = dict(raw)
        scenario_id = str(result.get("scenario_id") or "")
        if scenario_id not in assignment_records:
            raise CampaignExchangeError(f"transfer contains unassigned scenario: {scenario_id}")
        if scenario_id in result_ids:
            raise CampaignExchangeError(f"transfer duplicates scenario: {scenario_id}")
        result_ids.append(scenario_id)
        expected_path = f"scenarios/{scenario_id}"
        if require_portable_path(result.get("relative_path")) != expected_path:
            raise CampaignExchangeError("transferred scenario path does not match global ID")
        scenario_root = (root / expected_path).resolve()
        try:
            scenario_root.relative_to(root)
        except ValueError as exc:
            raise CampaignExchangeError("transferred scenario path escapes package") from exc
        inventory = require_inventory(scenario_root, result.get("files"))
        if result.get("file_count") != len(inventory):
            raise CampaignExchangeError("transferred scenario file count mismatch")
        if require_sha256(result.get("tree_sha256"), "scenario tree hash") != directory_sha256(
            scenario_root
        ):
            raise CampaignExchangeError("transferred scenario tree hash mismatch")
        assigned = assignment_records[scenario_id]
        if result.get("scenario_hash") != assigned["scenario_hash"]:
            raise CampaignExchangeError("transferred scenario hash mismatch")
        completion = validate_scenario_completion(scenario_root)
        if not completion.complete:
            raise CampaignExchangeError(
                f"transferred scenario is {completion.state}: {scenario_id}"
            )
        resolved = read_json_mapping(scenario_root / "resolved_scenario.json")
        if resolved.get("scenario_id") != scenario_id or resolved.get(
            "scenario_hash"
        ) != assigned["scenario_hash"]:
            raise CampaignExchangeError("transferred global scenario identity mismatch")
        if resolved.get("seed") != assignment["seed"]:
            raise CampaignExchangeError("transferred scenario seed mismatch")
        completion_reports.append(completion.to_jsonable())

    observed_directories = sorted(
        item.name for item in (root / "scenarios").glob("scenario_*") if item.is_dir()
    ) if (root / "scenarios").is_dir() else []
    if observed_directories != sorted(result_ids):
        raise CampaignExchangeError("transfer has missing or unlisted scenario directories")
    expected_unexported = sorted(set(assignment["scenario_ids"]) - set(result_ids))
    declared_unexported = manifest["unexported_scenarios"]
    if not isinstance(declared_unexported, list) or sorted(
        str(item.get("scenario_id"))
        for item in declared_unexported
        if isinstance(item, Mapping)
    ) != expected_unexported:
        raise CampaignExchangeError("transfer unexported scenario list does not reconcile")
    return {
        "schema_version": "worker-result-transfer-validation.v1",
        "transfer_id": manifest["transfer_id"],
        "campaign_id": manifest["campaign_id"],
        "worker_id": manifest["worker_id"],
        "scenario_ids": sorted(result_ids),
        "scenario_count": len(result_ids),
        "unexported_scenario_ids": expected_unexported,
        "environment_fingerprint": fingerprint,
        "completion_reports": completion_reports,
        "valid": True,
    }


def _validate_fingerprint_against_assignment(
    fingerprint: Mapping[str, object], assignment: Mapping[str, object]
) -> None:
    git = fingerprint.get("git")
    packages = fingerprint.get("packages")
    if not isinstance(git, Mapping) or git.get("commit") != assignment[
        "expected_git_commit"
    ]:
        raise CampaignExchangeError("environment fingerprint Git commit mismatch")
    if not isinstance(packages, Mapping) or packages.get("profile_identity") != assignment[
        "expected_environment_profile"
    ]:
        raise CampaignExchangeError("environment fingerprint profile mismatch")
    model_hashes, component_hashes = assignment_environment_hashes(assignment)
    if fingerprint.get("model_hashes") != model_hashes:
        raise CampaignExchangeError("environment fingerprint model identities mismatch")
    if fingerprint.get("component_config_hashes") != component_hashes:
        raise CampaignExchangeError("environment fingerprint component identities mismatch")


def _file_record(path: Path) -> dict[str, object]:
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def _validate_supporting_file(
    root: Path, supporting: Mapping[str, object], key: str
) -> Path:
    record = supporting.get(key)
    if not isinstance(record, Mapping):
        raise CampaignExchangeError(f"transfer supporting file is missing: {key}")
    relative = require_portable_path(record.get("path"))
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise CampaignExchangeError("transfer supporting path escapes package") from exc
    if not path.is_file() or path.stat().st_size != record.get("bytes") or file_sha256(
        path
    ) != require_sha256(record.get("sha256"), f"{key} hash"):
        raise CampaignExchangeError(f"transfer supporting file is missing or modified: {key}")
    return path


__all__ = [
    "WORKER_TRANSFER_SCHEMA_VERSION",
    "export_worker_results",
    "validate_worker_transfer",
]
