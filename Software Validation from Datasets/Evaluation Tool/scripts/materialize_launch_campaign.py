"""Materialize and verify the frozen massive campaign from its launch package."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Mapping

import yaml


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.artifact_contracts.atomic import file_sha256  # noqa: E402
from app.artifact_contracts.registry import (  # noqa: E402
    LATEST_ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
)
from app.campaign_exchange import (  # noqa: E402
    create_worker_assignment,
    current_git_commit,
    validate_assignment_set,
)
from app.campaign_exchange.common import atomic_write_bytes, atomic_write_json  # noqa: E402
from app.campaign_executor.planner import plan_campaign, validate_campaign  # noqa: E402
from app.campaign_executor.state import CampaignStateStore  # noqa: E402


class LaunchPackageError(RuntimeError):
    """Raised when a launch package cannot reproduce its frozen identities."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--launch-package",
        type=Path,
        default=TOOL_ROOT
        / "configs"
        / "automated_evaluation"
        / "launch_package.v1.yaml",
    )
    parser.add_argument(
        "--automated-runs-root",
        type=Path,
        default=TOOL_ROOT / "automated_runs",
    )
    parser.add_argument(
        "--bind-current-commit",
        action="store_true",
        help=(
            "bind runtime worker assignments to the checked-out HEAD after the "
            "launch source is committed; writes a deterministic release_binding.json"
        ),
    )
    return parser


def materialize(
    package_path: Path,
    automated_runs_root: Path,
    *,
    bind_current_commit: bool = False,
) -> dict[str, object]:
    package = _read_mapping(package_path)
    if package.get("schema_version") != "launch-package.v1":
        raise LaunchPackageError("unsupported launch-package schema")
    repository = _mapping(package.get("repository"), "repository")
    expected_commit = str(repository.get("expected_commit") or "")
    actual_commit = current_git_commit(REPOSITORY_ROOT)
    if actual_commit != expected_commit and not bind_current_commit:
        raise LaunchPackageError(
            f"repository commit differs: actual={actual_commit}; expected={expected_commit}"
        )
    bound_commit = actual_commit if bind_current_commit else expected_commit

    massive = _mapping(package.get("massive_campaign"), "massive_campaign")
    catalog = TOOL_ROOT / str(
        _mapping(massive["source_catalog"], "source catalog")["path"]
    )
    expected_catalog_hash = str(
        _mapping(massive["source_catalog"], "source catalog")["sha256"]
    )
    if file_sha256(catalog) != expected_catalog_hash:
        raise LaunchPackageError("source scenario catalog hash differs")

    campaign_id = str(massive["campaign_id"])
    plan = plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=automated_runs_root.resolve(),
        campaign_id=campaign_id,
        scenario_ids=[
            str(value) for value in _items(massive.get("scenario_ids"), "scenario IDs")
        ],
        default_max_retries=_integer(
            massive.get("default_max_retries"), "default max retries"
        ),
        created_at=_timestamp(str(massive["created_at_utc"])),
        registry=ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION),
    )
    campaign_root = plan.campaign_root
    validate_campaign(campaign_root)
    actual_manifest_hash = file_sha256(campaign_root / "campaign_manifest.json")
    if actual_manifest_hash != str(massive["campaign_manifest_sha256"]):
        raise LaunchPackageError(
            "materialized campaign manifest does not match the frozen launch identity"
        )

    assignment_paths: list[Path] = []
    assignment_results: dict[str, object] = {}
    workers = _mapping(massive.get("workers"), "workers")
    if bind_current_commit:
        _archive_stale_pending_assignments(
            campaign_root,
            workers,
            bound_commit=bound_commit,
        )
    for worker_name in ("machine_a", "machine_b"):
        worker = _mapping(workers.get(worker_name), worker_name)
        relative_assignment = Path(str(worker["assignment_path"]))
        output = campaign_root / relative_assignment
        assignment = create_worker_assignment(
            campaign_root,
            worker_id=str(worker["worker_id"]),
            expected_git_commit=bound_commit,
            expected_environment_profile=str(massive["environment_profile"]),
            scenario_ids=[
                str(value)
                for value in _items(worker.get("scenario_ids"), "worker scenario IDs")
            ],
            notes=str(worker["notes"]),
            created_at=_timestamp(str(worker["created_at_utc"])),
            output_path=output,
        )
        if bound_commit == expected_commit:
            if assignment["assignment_sha256"] != worker["assignment_sha256"]:
                raise LaunchPackageError(f"{worker_name} assignment hash differs")
            if assignment["assignment_id"] != worker["assignment_id"]:
                raise LaunchPackageError(f"{worker_name} assignment ID differs")
        assignment_paths.append(output)
        assignment_results[worker_name] = {
            "assignment_id": assignment["assignment_id"],
            "assignment_sha256": assignment["assignment_sha256"],
            "scenario_count": len(assignment["scenario_ids"]),
            "path": output.relative_to(campaign_root).as_posix(),
        }

    validation = validate_assignment_set(campaign_root, assignment_paths)
    release_binding = {
        "schema_version": "launch-release-binding.v1",
        "campaign_id": campaign_id,
        "campaign_manifest_sha256": actual_manifest_hash,
        "launch_package_sha256": file_sha256(package_path.resolve()),
        "candidate_evidence_commit": expected_commit,
        "bound_git_commit": bound_commit,
        "binding_mode": (
            "current_head" if bind_current_commit else "candidate_exact_reproduction"
        ),
        "assignments": assignment_results,
        "valid": True,
    }
    release_binding_path = campaign_root / "worker_assignments" / "release_binding.json"
    atomic_write_json(release_binding_path, release_binding)
    release_binding_hash = file_sha256(release_binding_path)
    release_binding_hash_path = (
        campaign_root / "worker_assignments" / "release_binding.sha256"
    )
    atomic_write_bytes(
        release_binding_hash_path,
        f"{release_binding_hash}  release_binding.json\n".encode("ascii"),
    )
    return {
        "schema_version": "launch-campaign-materialization.v1",
        "campaign_id": campaign_id,
        "campaign_root": str(campaign_root),
        "campaign_manifest_sha256": actual_manifest_hash,
        "scenario_count": len(plan.scenario_ids),
        "assignments": assignment_results,
        "assignment_validation": validation,
        "release_binding": {
            "path": release_binding_path.relative_to(campaign_root).as_posix(),
            "sha256": release_binding_hash,
            "sha256_path": release_binding_hash_path.relative_to(
                campaign_root
            ).as_posix(),
            **release_binding,
        },
        "valid": True,
    }


def _archive_stale_pending_assignments(
    campaign_root: Path,
    workers: Mapping[str, object],
    *,
    bound_commit: str,
) -> None:
    """Preserve stale bindings only when no scenario work has started.

    Runtime assignments bind a frozen campaign to a checkout after publication.
    Re-running setup at a newer checkout may therefore need a new assignment
    identity.  Moving an assignment after work starts would make result
    provenance ambiguous, so this path is intentionally limited to an entirely
    pending campaign.
    """

    stale: list[tuple[Path, Mapping[str, object]]] = []
    for worker_name in ("machine_a", "machine_b"):
        worker = _mapping(workers.get(worker_name), worker_name)
        path = campaign_root / Path(str(worker["assignment_path"]))
        if not path.is_file():
            continue
        existing = _read_mapping(path)
        if str(existing.get("expected_git_commit") or "") != bound_commit:
            stale.append((path, existing))
    if not stale:
        return

    manifest = json.loads(
        (campaign_root / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    state = CampaignStateStore(campaign_root / "database" / "campaign.sqlite")
    summary = state.summary(str(manifest["campaign_id"]))
    expected = len(manifest["scenario_ids"])
    if summary["state_counts"] != {"pending": expected}:
        raise LaunchPackageError(
            "refusing to rebind stale assignments after campaign work has started"
        )

    history = campaign_root / "worker_assignments" / "history"
    history.mkdir(parents=True, exist_ok=True)
    for path, existing in stale:
        assignment_id = str(existing.get("assignment_id") or "unknown")
        target = history / f"{path.stem}_{assignment_id}.yaml"
        if target.exists():
            if target.read_bytes() != path.read_bytes():
                raise LaunchPackageError(
                    f"stale assignment history conflicts: {target}"
                )
            path.unlink()
        else:
            path.replace(target)


def _read_mapping(path: Path) -> Mapping[str, object]:
    value = yaml.safe_load(path.resolve().read_text(encoding="utf-8"))
    return _mapping(value, "launch package")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise LaunchPackageError(f"{label} must be a mapping")
    return value


def _items(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise LaunchPackageError(f"{label} must be a list")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise LaunchPackageError(f"{label} must be an integer")
    return int(value)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = materialize(
            args.launch_package,
            args.automated_runs_root,
            bind_current_commit=args.bind_current_commit,
        )
    except (RuntimeError, FileNotFoundError, KeyError, ValueError) as exc:
        print(
            f"launch materialization failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
