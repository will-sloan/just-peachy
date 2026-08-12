"""Conflict-safe merge of independently copied worker result packages."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from app.artifact_contracts.atomic import file_sha256
from app.artifact_contracts.completion import validate_scenario_completion
from app.campaign_executor.planner import validate_campaign

from .common import (
    CampaignExchangeError,
    atomic_copy_tree,
    atomic_write_json,
    content_hash,
    directory_inventory,
    directory_sha256,
    read_json_mapping,
    require_portable_path,
    require_sha256,
    utc_timestamp,
)
from .transfers import validate_worker_transfer


MERGED_INDEX_SCHEMA_VERSION = "merged-result-index.v1"
MERGE_REPORT_SCHEMA_VERSION = "merge-validation-report.v1"
ANALYSIS_INPUT_SCHEMA_VERSION = "analysis-input-index.v1"
INDEX_HASH_EXCLUSIONS = {"index_id", "index_sha256", "updated_at_utc"}
ANALYSIS_HASH_EXCLUSIONS = {"analysis_input_id", "analysis_input_sha256", "created_at_utc"}


class MergeRejectedError(CampaignExchangeError):
    """Raised after a rejection report is saved and no result is overwritten."""


def merge_worker_results(
    campaign_root: Path,
    transfer_roots: Sequence[Path],
    *,
    created_at: datetime | None = None,
) -> dict[str, object]:
    """Validate packages, reject conflicts, and create the analysis result index."""

    campaign = campaign_root.resolve()
    validate_campaign(campaign)
    if not transfer_roots:
        raise CampaignExchangeError("at least one worker transfer is required")
    manifest = read_json_mapping(campaign / "campaign_manifest.json")
    campaign_hash = file_sha256(campaign / "campaign_manifest.json")
    analysis_root = campaign / "analysis"
    merged_root = analysis_root / "merged_results"
    scenario_target_root = merged_root / "scenarios"
    report_path = analysis_root / "merge_validation_report.json"

    validations: list[dict[str, object]] = []
    invalid: list[dict[str, object]] = []
    packages: list[tuple[Path, dict[str, object], dict[str, object]]] = []
    for raw_root in transfer_roots:
        transfer = raw_root.resolve()
        try:
            validation = validate_worker_transfer(transfer, campaign_root=campaign)
            transfer_manifest = read_json_mapping(transfer / "transfer_manifest.json")
        except Exception as exc:
            invalid.append(
                {
                    "transfer_path": str(raw_root),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        validations.append(_transfer_validation_summary(validation))
        packages.append((transfer, transfer_manifest, validation))

    environment_summary, environment_differences = _environment_comparison(packages)
    commits = {str(item.get("git_commit") or "") for item in environment_summary}
    if len(commits) > 1:
        invalid.append(
            {
                "error": "worker transfers were produced from different Git commits",
                "commits": sorted(commits),
            }
        )

    candidates, duplicate_rows, conflicts = _candidate_results(packages)
    existing_rows = _load_existing_index(campaign, merged_root)
    for scenario_id, existing in existing_rows.items():
        candidate = candidates.get(scenario_id)
        if candidate is None:
            continue
        if candidate["tree_sha256"] == existing["tree_sha256"]:
            duplicate_rows.append(
                {
                    "scenario_id": scenario_id,
                    "classification": "byte_identical_existing_result",
                    "sources": [existing.get("primary_source"), candidate["source"]],
                }
            )
            _items(candidate.get("duplicate_sources"), "duplicate sources").append(
                candidate["source"]
            )
            candidates.pop(scenario_id)
        else:
            conflicts.append(
                {
                    "scenario_id": scenario_id,
                    "classification": "conflicting_existing_result",
                    "existing_tree_sha256": existing["tree_sha256"],
                    "incoming_tree_sha256": candidate["tree_sha256"],
                    "incoming_source": candidate["source"],
                }
            )

    # A process interruption can occur after a scenario directory is
    # atomically published but before the merged index is published.  Recover
    # only byte-identical directories.  A differing unindexed directory is a
    # conflict and is never overwritten silently.
    for scenario_id, candidate in sorted(candidates.items()):
        target = scenario_target_root / scenario_id
        if not target.exists():
            continue
        observed_hash = directory_sha256(target)
        if observed_hash == candidate["tree_sha256"]:
            candidate["recovered_unindexed_target"] = True
            duplicate_rows.append(
                {
                    "scenario_id": scenario_id,
                    "classification": "byte_identical_interrupted_publication",
                    "sources": [str(target), candidate["source"]],
                }
            )
        else:
            conflicts.append(
                {
                    "scenario_id": scenario_id,
                    "classification": "conflicting_unindexed_result",
                    "existing_tree_sha256": observed_hash,
                    "incoming_tree_sha256": candidate["tree_sha256"],
                    "incoming_source": candidate["source"],
                }
            )

    if scenario_target_root.is_dir():
        recognized_targets = set(existing_rows) | set(candidates)
        for target in sorted(scenario_target_root.iterdir()):
            if target.is_dir() and target.name not in recognized_targets:
                conflicts.append(
                    {
                        "scenario_id": target.name,
                        "classification": "unrecognized_unindexed_result",
                        "existing_tree_sha256": directory_sha256(target),
                    }
                )

    timestamp = utc_timestamp(created_at)
    if invalid or conflicts:
        report = _merge_report(
            manifest=manifest,
            campaign_hash=campaign_hash,
            status="rejected",
            validations=validations,
            invalid=invalid,
            duplicates=duplicate_rows,
            conflicts=conflicts,
            environment_summary=environment_summary,
            environment_differences=environment_differences,
            merged_ids=sorted(existing_rows),
            timestamp=timestamp,
        )
        atomic_write_json(report_path, report)
        raise MergeRejectedError(
            f"merge rejected; see {report_path} for validation details"
        )

    for scenario_id, candidate in sorted(candidates.items()):
        target = scenario_target_root / scenario_id
        if candidate.get("recovered_unindexed_target") is True:
            continue
        if target.exists():
            raise MergeRejectedError(
                f"unindexed merged scenario already exists; refusing overwrite: {target}"
            )
        atomic_copy_tree(Path(str(candidate["source_path"])), target)
        if directory_sha256(target) != candidate["tree_sha256"]:
            raise CampaignExchangeError(f"post-copy merge checksum mismatch: {scenario_id}")

    rows = dict(existing_rows)
    for scenario_id, candidate in candidates.items():
        target = scenario_target_root / scenario_id
        rows[scenario_id] = _index_row(campaign, target, candidate)
    index = _finalize_index(
        {
            "schema_version": MERGED_INDEX_SCHEMA_VERSION,
            "hash_version": "merged-result-index-hash.v1",
            "hash_algorithm": "sha256",
            "campaign_id": manifest["campaign_id"],
            "campaign_manifest_sha256": campaign_hash,
            "scenario_results": [rows[key] for key in sorted(rows)],
            "missing_scenario_ids": sorted(
                {
                    str(value)
                    for value in _items(manifest.get("scenario_ids"), "scenario IDs")
                }
                - set(rows)
            ),
            "updated_at_utc": timestamp,
        }
    )
    merged_root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(merged_root / "merged_result_index.json", index)
    analysis_input = _analysis_input_index(campaign, index, timestamp=timestamp)
    atomic_write_json(analysis_root / "analysis_input_index.json", analysis_input)
    report = _merge_report(
        manifest=manifest,
        campaign_hash=campaign_hash,
        status="accepted_with_warnings" if environment_differences else "accepted",
        validations=validations,
        invalid=[],
        duplicates=duplicate_rows,
        conflicts=[],
        environment_summary=environment_summary,
        environment_differences=environment_differences,
        merged_ids=sorted(rows),
        timestamp=timestamp,
    )
    report["merged_result_index"] = {
        "path": "analysis/merged_results/merged_result_index.json",
        "sha256": file_sha256(merged_root / "merged_result_index.json"),
        "index_id": index["index_id"],
    }
    report["analysis_input_index"] = {
        "path": "analysis/analysis_input_index.json",
        "sha256": file_sha256(analysis_root / "analysis_input_index.json"),
        "analysis_input_id": analysis_input["analysis_input_id"],
    }
    atomic_write_json(report_path, report)
    return report


def validate_merged_results(campaign_root: Path) -> dict[str, object]:
    """Revalidate the merged index and every indexed scenario directory."""

    campaign = campaign_root.resolve()
    validate_campaign(campaign)
    merged_root = campaign / "analysis" / "merged_results"
    rows = _load_existing_index(campaign, merged_root, required=True)
    return {
        "schema_version": "merged-result-validation.v1",
        "campaign_id": read_json_mapping(campaign / "campaign_manifest.json")["campaign_id"],
        "scenario_ids": sorted(rows),
        "scenario_count": len(rows),
        "valid": True,
    }


def _candidate_results(
    packages: Sequence[tuple[Path, dict[str, object], dict[str, object]]]
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    candidates: dict[str, dict[str, object]] = {}
    duplicates: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    for root, manifest, validation in packages:
        source = {
            "transfer_id": manifest["transfer_id"],
            "worker_id": manifest["worker_id"],
            "environment_fingerprint_id": manifest["environment_fingerprint_id"],
        }
        for raw in _items(manifest.get("scenario_results"), "scenario results"):
            result = dict(_mapping(raw, "scenario result"))
            scenario_id = str(result["scenario_id"])
            candidate = {
                "scenario_id": scenario_id,
                "scenario_hash": result["scenario_hash"],
                "tree_sha256": result["tree_sha256"],
                "file_count": result["file_count"],
                "source": source,
                "duplicate_sources": [],
                "source_path": root / str(result["relative_path"]),
                "environment_fingerprint": validation["environment_fingerprint"],
            }
            previous = candidates.get(scenario_id)
            if previous is None:
                candidates[scenario_id] = candidate
            elif previous["tree_sha256"] == candidate["tree_sha256"]:
                _items(previous.get("duplicate_sources"), "duplicate sources").append(
                    source
                )
                duplicates.append(
                    {
                        "scenario_id": scenario_id,
                        "classification": "byte_identical_duplicate",
                        "sources": [previous["source"], source],
                    }
                )
            else:
                conflicts.append(
                    {
                        "scenario_id": scenario_id,
                        "classification": "conflicting_duplicate",
                        "first_tree_sha256": previous["tree_sha256"],
                        "second_tree_sha256": candidate["tree_sha256"],
                        "sources": [previous["source"], source],
                    }
                )
    return candidates, duplicates, conflicts


def _load_existing_index(
    campaign: Path, merged_root: Path, *, required: bool = False
) -> dict[str, dict[str, object]]:
    path = merged_root / "merged_result_index.json"
    if not path.is_file():
        if required:
            raise CampaignExchangeError("merged result index is missing")
        # The caller reconciles any directories left after an interrupted
        # publication against incoming checksums before creating a new index.
        return {}
    index = read_json_mapping(path)
    if index.get("schema_version") != MERGED_INDEX_SCHEMA_VERSION:
        raise CampaignExchangeError("unsupported merged result index schema")
    digest = content_hash(index, INDEX_HASH_EXCLUSIONS)
    if index.get("index_sha256") != digest or index.get(
        "index_id"
    ) != f"merge_index_{digest[:12].lower()}":
        raise CampaignExchangeError("merged result index hash mismatch")
    manifest = read_json_mapping(campaign / "campaign_manifest.json")
    if index.get("campaign_id") != manifest["campaign_id"] or index.get(
        "campaign_manifest_sha256"
    ) != file_sha256(campaign / "campaign_manifest.json"):
        raise CampaignExchangeError("merged result index campaign identity mismatch")
    raw_rows = index.get("scenario_results")
    if not isinstance(raw_rows, list) or any(not isinstance(item, Mapping) for item in raw_rows):
        raise CampaignExchangeError("merged result index rows are invalid")
    rows: dict[str, dict[str, object]] = {}
    for raw in raw_rows:
        row = dict(raw)
        scenario_id = str(row.get("scenario_id") or "")
        if scenario_id in rows:
            raise CampaignExchangeError("merged result index duplicates a scenario")
        relative = require_portable_path(row.get("relative_path"))
        expected = f"analysis/merged_results/scenarios/{scenario_id}"
        if relative != expected:
            raise CampaignExchangeError("merged result path does not match scenario ID")
        root = (campaign / relative).resolve()
        if require_sha256(row.get("tree_sha256"), "merged tree hash") != directory_sha256(
            root
        ):
            raise CampaignExchangeError("merged scenario checksum mismatch")
        completion = validate_scenario_completion(root)
        if not completion.complete:
            raise CampaignExchangeError(f"indexed merged result is {completion.state}")
        resolved = read_json_mapping(root / "resolved_scenario.json")
        if resolved.get("scenario_id") != scenario_id or resolved.get(
            "scenario_hash"
        ) != row.get("scenario_hash"):
            raise CampaignExchangeError("merged global scenario identity mismatch")
        rows[scenario_id] = row
    return rows


def _index_row(
    campaign: Path, scenario_root: Path, candidate: Mapping[str, object]
) -> dict[str, object]:
    scenario_id = str(candidate["scenario_id"])
    relative_root = scenario_root.relative_to(campaign).as_posix()
    artifact_paths = {}
    for key, relative in (
        ("utterance_predictions", "predictions/utterances.jsonl"),
        ("diagnostics", "predictions/diagnostics.jsonl"),
        ("item_metrics", "metrics/item_metrics.parquet"),
        ("grouped_metrics", "metrics/grouped_metrics.parquet"),
        ("metrics_summary", "metrics/summary.json"),
        ("failures", "metrics/failures.parquet"),
        ("resource_usage", "resource_logs/resource_usage.parquet"),
        ("component_spans", "resource_logs/component_spans.jsonl"),
        ("resource_summary", "resource_logs/resource_summary.json"),
        ("scenario_report", "report/scenario_report.json"),
    ):
        if (scenario_root / relative).is_file():
            artifact_paths[key] = f"{relative_root}/{relative}"
    return {
        "scenario_id": scenario_id,
        "scenario_hash": candidate["scenario_hash"],
        "relative_path": relative_root,
        "tree_sha256": candidate["tree_sha256"],
        "file_count": len(directory_inventory(scenario_root)),
        "primary_source": candidate["source"],
        "duplicate_sources": candidate["duplicate_sources"],
        "artifact_paths": artifact_paths,
    }


def _finalize_index(value: Mapping[str, object]) -> dict[str, object]:
    result = dict(value)
    digest = content_hash(result, INDEX_HASH_EXCLUSIONS)
    result["index_sha256"] = digest
    result["index_id"] = f"merge_index_{digest[:12].lower()}"
    return result


def _analysis_input_index(
    campaign: Path, merged_index: Mapping[str, object], *, timestamp: str
) -> dict[str, object]:
    rows = []
    for raw in _items(merged_index.get("scenario_results"), "merged scenario results"):
        row = dict(_mapping(raw, "merged scenario result"))
        primary_source = _mapping(row.get("primary_source"), "primary source")
        rows.append(
            {
                "scenario_id": row["scenario_id"],
                "scenario_hash": row["scenario_hash"],
                "result_root": row["relative_path"],
                "artifact_paths": row["artifact_paths"],
                "environment_fingerprint_id": primary_source[
                    "environment_fingerprint_id"
                ],
            }
        )
    result: dict[str, object] = {
        "schema_version": ANALYSIS_INPUT_SCHEMA_VERSION,
        "hash_version": "analysis-input-index-hash.v1",
        "hash_algorithm": "sha256",
        "campaign_id": merged_index["campaign_id"],
        "campaign_manifest_sha256": merged_index["campaign_manifest_sha256"],
        "merged_result_index": {
            "path": "analysis/merged_results/merged_result_index.json",
            "index_id": merged_index["index_id"],
            "index_sha256": merged_index["index_sha256"],
        },
        "scenario_results": rows,
        "missing_scenario_ids": merged_index["missing_scenario_ids"],
        "created_at_utc": timestamp,
    }
    digest = content_hash(result, ANALYSIS_HASH_EXCLUSIONS)
    result["analysis_input_sha256"] = digest
    result["analysis_input_id"] = f"analysis_input_{digest[:12].lower()}"
    _ = campaign
    return result


def _environment_comparison(
    packages: Sequence[tuple[Path, dict[str, object], dict[str, object]]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summaries: list[dict[str, object]] = []
    for _root, manifest, validation in packages:
        fingerprint = _mapping(
            validation.get("environment_fingerprint"), "environment fingerprint"
        )
        git = _mapping(fingerprint.get("git"), "fingerprint Git identity")
        packages_identity = _mapping(
            fingerprint.get("packages"), "fingerprint package identity"
        )
        os_identity = _mapping(fingerprint.get("os"), "fingerprint OS identity")
        python_identity = _mapping(
            fingerprint.get("python"), "fingerprint Python identity"
        )
        summaries.append(
            {
                "worker_id": manifest["worker_id"],
                "transfer_id": manifest["transfer_id"],
                "fingerprint_id": fingerprint["fingerprint_id"],
                "git_commit": git["commit"],
                "git_dirty": git["dirty"],
                "environment_profile": packages_identity["profile_identity"],
                "package_freeze_sha256": packages_identity["freeze_sha256"],
                "os": {
                    key: os_identity.get(key)
                    for key in ("system", "release", "machine")
                },
                "python_version": python_identity.get("version"),
                "hardware": fingerprint["hardware"],
                "accelerator": fingerprint["accelerator"],
            }
        )
    fields = (
        "git_commit",
        "git_dirty",
        "environment_profile",
        "package_freeze_sha256",
        "os",
        "python_version",
        "hardware",
        "accelerator",
    )
    differences: list[dict[str, object]] = []
    for field in fields:
        values = {str(item[field]) for item in summaries}
        if len(values) > 1:
            differences.append(
                {
                    "field": field,
                    "values_by_worker": {
                        str(item["worker_id"]): item[field] for item in summaries
                    },
                }
            )
    return summaries, differences


def _transfer_validation_summary(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value[key]
        for key in (
            "transfer_id",
            "campaign_id",
            "worker_id",
            "scenario_ids",
            "scenario_count",
            "unexported_scenario_ids",
            "valid",
        )
    }


def _merge_report(
    *,
    manifest: Mapping[str, object],
    campaign_hash: str,
    status: str,
    validations: Sequence[Mapping[str, object]],
    invalid: Sequence[Mapping[str, object]],
    duplicates: Sequence[Mapping[str, object]],
    conflicts: Sequence[Mapping[str, object]],
    environment_summary: Sequence[Mapping[str, object]],
    environment_differences: Sequence[Mapping[str, object]],
    merged_ids: Sequence[str],
    timestamp: str,
) -> dict[str, object]:
    return {
        "schema_version": MERGE_REPORT_SCHEMA_VERSION,
        "campaign_id": manifest["campaign_id"],
        "campaign_manifest_sha256": campaign_hash,
        "status": status,
        "validated_transfers": [dict(item) for item in validations],
        "invalid_transfers": [dict(item) for item in invalid],
        "duplicates": [dict(item) for item in duplicates],
        "conflicts": [dict(item) for item in conflicts],
        "environment_summary": [dict(item) for item in environment_summary],
        "environment_differences": [dict(item) for item in environment_differences],
        "merged_scenario_ids": list(merged_ids),
        "missing_scenario_ids": sorted(
            {
                str(value)
                for value in _items(manifest.get("scenario_ids"), "scenario IDs")
            }
            - set(merged_ids)
        ),
        "created_at_utc": timestamp,
    }


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CampaignExchangeError(f"{label} must be a mapping")
    return value


def _items(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise CampaignExchangeError(f"{label} must be a list")
    return value


__all__ = [
    "ANALYSIS_INPUT_SCHEMA_VERSION",
    "MERGED_INDEX_SCHEMA_VERSION",
    "MERGE_REPORT_SCHEMA_VERSION",
    "MergeRejectedError",
    "merge_worker_results",
    "validate_merged_results",
]
