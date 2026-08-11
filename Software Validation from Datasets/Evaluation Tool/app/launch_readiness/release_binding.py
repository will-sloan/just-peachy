"""Validate the runtime binding between a release, assignments, and Git HEAD."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from app.artifact_contracts.atomic import file_sha256
from app.campaign_exchange import (
    current_git_commit,
    validate_assignment_set,
    validate_worker_assignment,
)
from app.campaign_exchange.common import read_json_mapping, read_yaml_mapping
from app.campaign_executor.planner import validate_campaign


RELEASE_BINDING_VALIDATION_SCHEMA_VERSION = "launch-release-binding-validation.v1"


class ReleaseBindingError(RuntimeError):
    """Raised when a production release binding is missing or inconsistent."""


def validate_release_binding(
    campaign_root: Path,
    *,
    repository_root: Path,
    expected_environment_profile: str,
    worker_id: str | None = None,
    launch_package_path: Path | None = None,
) -> dict[str, object]:
    """Validate the binding, its checksum, and every referenced assignment.

    The release binding is generated after a frozen launch package is checked out.
    It is deliberately machine-independent: both workers must reference the same
    campaign and Git commit, while their local hardware evidence remains separate.
    """

    campaign = campaign_root.resolve()
    repository = repository_root.resolve()
    validate_campaign(campaign)
    manifest = read_json_mapping(campaign / "campaign_manifest.json")
    binding_path = campaign / "worker_assignments" / "release_binding.json"
    checksum_path = campaign / "worker_assignments" / "release_binding.sha256"
    if not binding_path.is_file():
        raise ReleaseBindingError(f"release binding is missing: {binding_path}")
    if not checksum_path.is_file():
        raise ReleaseBindingError(f"release binding checksum is missing: {checksum_path}")

    binding = read_json_mapping(binding_path)
    actual_binding_hash = file_sha256(binding_path)
    checksum_parts = checksum_path.read_text(encoding="ascii").strip().split()
    if checksum_parts != [actual_binding_hash, "release_binding.json"]:
        raise ReleaseBindingError("release binding checksum does not match")
    if binding.get("schema_version") != "launch-release-binding.v1":
        raise ReleaseBindingError("unsupported release binding schema")
    if binding.get("valid") is not True:
        raise ReleaseBindingError("release binding is not marked valid")
    if binding.get("binding_mode") != "current_head":
        raise ReleaseBindingError("production launch requires a current_head binding")
    if binding.get("campaign_id") != manifest.get("campaign_id"):
        raise ReleaseBindingError("release binding campaign ID differs")
    manifest_hash = file_sha256(campaign / "campaign_manifest.json")
    if binding.get("campaign_manifest_sha256") != manifest_hash:
        raise ReleaseBindingError("release binding campaign hash differs")

    commit = current_git_commit(repository)
    if binding.get("bound_git_commit") != commit:
        raise ReleaseBindingError(
            "release binding Git commit differs: "
            f"bound={binding.get('bound_git_commit')}; actual={commit}"
        )
    if launch_package_path is not None:
        package = launch_package_path.resolve()
        if not package.is_file():
            raise ReleaseBindingError(f"launch package is missing: {package}")
        if binding.get("launch_package_sha256") != file_sha256(package):
            raise ReleaseBindingError("release binding launch-package hash differs")

    raw_assignments = binding.get("assignments")
    if not isinstance(raw_assignments, Mapping) or not raw_assignments:
        raise ReleaseBindingError("release binding has no assignments")
    assignment_paths: list[Path] = []
    validated: dict[str, dict[str, object]] = {}
    for name, raw_entry in sorted(raw_assignments.items()):
        if not isinstance(raw_entry, Mapping):
            raise ReleaseBindingError(f"invalid release assignment entry: {name}")
        relative = Path(str(raw_entry.get("path") or ""))
        path = (campaign / relative).resolve()
        try:
            path.relative_to((campaign / "worker_assignments").resolve())
        except ValueError as exc:
            raise ReleaseBindingError(
                f"release assignment path escapes worker_assignments: {relative}"
            ) from exc
        if not path.is_file():
            raise ReleaseBindingError(f"release assignment is missing: {path}")
        assignment = read_yaml_mapping(path)
        validation = validate_worker_assignment(
            campaign,
            assignment,
            actual_git_commit=commit,
            actual_environment_profile=expected_environment_profile,
        )
        if raw_entry.get("assignment_id") != assignment.get("assignment_id"):
            raise ReleaseBindingError(f"release assignment ID differs: {name}")
        if raw_entry.get("assignment_sha256") != assignment.get("assignment_sha256"):
            raise ReleaseBindingError(f"release assignment hash differs: {name}")
        scenario_ids = assignment.get("scenario_ids")
        if not isinstance(scenario_ids, list):
            raise ReleaseBindingError(f"release assignment scenarios are invalid: {name}")
        if int(raw_entry.get("scenario_count") or -1) != len(scenario_ids):
            raise ReleaseBindingError(f"release assignment count differs: {name}")
        assignment_paths.append(path)
        validated[str(name)] = {
            "assignment_id": validation["assignment_id"],
            "worker_id": validation["worker_id"],
            "scenario_count": validation["scenario_count"],
            "valid": True,
        }

    assignment_set = validate_assignment_set(campaign, assignment_paths)
    if worker_id is not None and not any(
        row.get("worker_id") == worker_id for row in validated.values()
    ):
        raise ReleaseBindingError(f"worker is absent from release binding: {worker_id}")
    if assignment_set.get("missing_scenario_ids"):
        raise ReleaseBindingError("release assignments do not cover the campaign")

    return {
        "schema_version": RELEASE_BINDING_VALIDATION_SCHEMA_VERSION,
        "campaign_id": manifest["campaign_id"],
        "campaign_manifest_sha256": manifest_hash,
        "release_binding_sha256": actual_binding_hash,
        "bound_git_commit": commit,
        "expected_environment_profile": expected_environment_profile,
        "requested_worker_id": worker_id,
        "assignments": validated,
        "assignment_set": assignment_set,
        "status": "PASS",
        "valid": True,
    }


__all__ = [
    "RELEASE_BINDING_VALIDATION_SCHEMA_VERSION",
    "ReleaseBindingError",
    "validate_release_binding",
]
