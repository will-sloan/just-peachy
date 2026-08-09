"""Exact campaign reconciliation and portable standalone analysis manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import yaml

from app.artifact_contracts.atomic import file_sha256
from app.artifact_contracts.completion import CompletionReport, validate_scenario_completion
from app.campaign_exchange.common import atomic_write_bytes, atomic_write_json, read_json_mapping
from app.campaign_exchange.merge import validate_merged_results
from app.campaign_executor.planner import validate_campaign
from app.campaign_executor.state import CampaignStateStore

from .contracts import (
    ANALYSIS_HASH_EXCLUSIONS,
    ANALYSIS_MANIFEST_SCHEMA_VERSION,
    HASH_ALGORITHM,
    HASH_VERSION,
    RESULT_INDEX_HASH_EXCLUSIONS,
    RESULT_INDEX_SCHEMA_VERSION,
    AnalysisContractError,
    finalize_hashed_contract,
    load_registries,
    verify_hashed_contract,
)


OPTIONAL_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("resolved_scenario", "resolved_scenario.json"),
    ("run_config", "run_config.yaml"),
    ("scenario_status", "status.json"),
    ("checksums", "checksums.json"),
    ("utterance_predictions", "predictions/utterances.jsonl"),
    ("diagnostics", "predictions/diagnostics.jsonl"),
    ("words", "predictions/words.jsonl"),
    ("segments_rttm", "predictions/segments.rttm"),
    ("vad_regions", "predictions/vad_regions.jsonl"),
    ("diarization_diagnostics", "predictions/diarization_diagnostics.jsonl"),
    ("embedding_index", "embeddings/index.parquet"),
    ("embedding_npz", "embeddings/embeddings.npz"),
    ("similarity_scores", "similarity_scores.parquet"),
    ("threshold_sweep", "threshold_sweep.parquet"),
    ("item_metrics", "metrics/item_metrics.parquet"),
    ("grouped_metrics", "metrics/grouped_metrics.parquet"),
    ("metrics_summary", "metrics/summary.json"),
    ("failures", "metrics/failures.parquet"),
    ("resource_usage", "resource_logs/resource_usage.parquet"),
    ("component_spans", "resource_logs/component_spans.jsonl"),
    ("resource_summary", "resource_logs/resource_summary.json"),
    ("resource_availability", "resource_logs/availability.json"),
    ("scenario_report", "report/scenario_report.json"),
    ("scenario_report_markdown", "report/scenario_report.md"),
    ("events", "logs/events.jsonl"),
    ("runner_log", "logs/runner.log"),
    ("errors", "logs/errors.jsonl"),
)


def build_analysis_manifest(
    campaign_root: Path,
    *,
    config_root: Path | None = None,
    created_at: datetime | None = None,
) -> dict[str, object]:
    """Reconcile every planned scenario and publish stable Stage 12 indexes.

    Only validated Stage 6 merged results receive ``analysis_status=included``.
    Missing, failed, invalid, unmerged, and excluded work remains visible.
    """

    campaign = campaign_root.resolve()
    validate_campaign(campaign)
    manifest = read_json_mapping(campaign / "campaign_manifest.json")
    registries = load_registries(config_root)
    timestamp = _analysis_timestamp(campaign, created_at)
    merge_context = _merge_context(campaign)
    assignments = _assignment_index(campaign)
    state_rows = _state_index(campaign, str(manifest["campaign_id"]))

    scenario_rows: list[dict[str, object]] = []
    for scenario_id in manifest["scenario_ids"]:
        identifier = str(scenario_id)
        source_root = campaign / "scenarios" / identifier
        resolved = _resolved_scenario(source_root)
        merged = merge_context["rows"].get(identifier)
        state = state_rows.get(identifier, {})
        row = _scenario_row(
            campaign,
            identifier,
            resolved,
            merged,
            state,
            assignments.get(identifier, []),
            merge_context["environments"],
        )
        scenario_rows.append(row)

    planned_ids = [str(item) for item in manifest["scenario_ids"]]
    observed_ids = [
        str(row["scenario_id"])
        for row in scenario_rows
        if row["analysis_status"] == "included"
    ]
    counts = _status_counts(scenario_rows)
    result_index = finalize_hashed_contract(
        {
            "schema_version": RESULT_INDEX_SCHEMA_VERSION,
            "hash_version": HASH_VERSION,
            "hash_algorithm": HASH_ALGORITHM,
            "campaign_id": manifest["campaign_id"],
            "campaign_manifest_sha256": file_sha256(campaign / "campaign_manifest.json"),
            "planned_scenario_ids": planned_ids,
            "included_scenario_ids": observed_ids,
            "scenario_rows": scenario_rows,
            "status_counts": counts,
            "exact_reconciliation": {
                "planned_count": len(planned_ids),
                "indexed_count": len(scenario_rows),
                "included_count": len(observed_ids),
                "duplicate_scenario_ids": _duplicates(planned_ids),
                "unplanned_merged_scenario_ids": sorted(
                    set(merge_context["rows"]) - set(planned_ids)
                ),
                "exact": len(scenario_rows) == len(planned_ids)
                and not _duplicates(planned_ids)
                and not (set(merge_context["rows"]) - set(planned_ids)),
            },
            "created_at_utc": timestamp,
        },
        id_field="result_index_id",
        hash_field="result_index_sha256",
        id_prefix="result_index",
        exclusions=RESULT_INDEX_HASH_EXCLUSIONS,
    )

    analysis_dir = campaign / "analysis"
    index_path = analysis_dir / "campaign_result_index.json"
    atomic_write_json(index_path, result_index)
    registry_ids = _materialize_registries(campaign, registries)
    analysis_manifest = finalize_hashed_contract(
        {
            "schema_version": ANALYSIS_MANIFEST_SCHEMA_VERSION,
            "hash_version": HASH_VERSION,
            "hash_algorithm": HASH_ALGORITHM,
            "campaign": {
                "campaign_id": manifest["campaign_id"],
                "campaign_manifest_path": "campaign_manifest.json",
                "campaign_manifest_sha256": file_sha256(
                    campaign / "campaign_manifest.json"
                ),
                "artifact_registry_version": manifest["artifact_registry_version"],
                "scenario_schema_version": manifest["scenario_schema_version"],
            },
            "contract_versions": {
                "analysis_manifest": ANALYSIS_MANIFEST_SCHEMA_VERSION,
                "result_index": RESULT_INDEX_SCHEMA_VERSION,
                "scenario": manifest["scenario_schema_version"],
                "hash": HASH_VERSION,
                "hash_algorithm": HASH_ALGORITHM,
            },
            "benchmark_manifests": manifest["benchmark_manifests"],
            "source_indexes": merge_context["source_indexes"],
            "registries": registry_ids,
            "result_index": {
                "path": "analysis/campaign_result_index.json",
                "result_index_id": result_index["result_index_id"],
                "result_index_sha256": result_index["result_index_sha256"],
                "file_sha256": file_sha256(index_path),
            },
            "scenario_index": scenario_rows,
            "status_counts": counts,
            "worker_assignments": _assignment_summaries(assignments),
            "merge": merge_context["summary"],
            "failed_missing_invalid_excluded": [
                {
                    "scenario_id": row["scenario_id"],
                    "status": row["analysis_status"],
                    "reason": row["analysis_reason"],
                }
                for row in scenario_rows
                if row["analysis_status"] != "included"
            ],
            "created_at_utc": timestamp,
        },
        id_field="analysis_manifest_id",
        hash_field="analysis_manifest_sha256",
        id_prefix="analysis",
        exclusions=ANALYSIS_HASH_EXCLUSIONS,
    )
    atomic_write_json(analysis_dir / "analysis_manifest.json", analysis_manifest)
    validate_analysis_manifest(analysis_dir / "analysis_manifest.json", campaign_root=campaign)
    return analysis_manifest


def validate_analysis_manifest(path: Path, *, campaign_root: Path | None = None) -> dict[str, object]:
    value = read_json_mapping(path.resolve())
    if value.get("schema_version") != ANALYSIS_MANIFEST_SCHEMA_VERSION:
        raise AnalysisContractError("unsupported analysis manifest schema")
    verify_hashed_contract(
        value,
        id_field="analysis_manifest_id",
        hash_field="analysis_manifest_sha256",
        id_prefix="analysis",
        exclusions=ANALYSIS_HASH_EXCLUSIONS,
    )
    root = (campaign_root or path.resolve().parents[1]).resolve()
    campaign = value.get("campaign")
    if not isinstance(campaign, Mapping):
        raise AnalysisContractError("analysis manifest campaign identity is missing")
    if campaign.get("campaign_manifest_sha256") != file_sha256(
        root / "campaign_manifest.json"
    ):
        raise AnalysisContractError("analysis manifest campaign hash mismatch")
    rows = value.get("scenario_index")
    planned = read_json_mapping(root / "campaign_manifest.json")["scenario_ids"]
    if not isinstance(rows, list) or [row.get("scenario_id") for row in rows] != list(planned):
        raise AnalysisContractError("analysis scenario index does not exactly match campaign order")
    for row in rows:
        if row.get("analysis_status") == "included":
            relative = _portable_relative(row.get("result_root"))
            completion = validate_scenario_completion(root / relative)
            if not completion.complete:
                raise AnalysisContractError(
                    f"included scenario no longer validates: {row.get('scenario_id')}"
                )
    return value


def _merge_context(campaign: Path) -> dict[str, object]:
    merged_path = campaign / "analysis" / "merged_results" / "merged_result_index.json"
    analysis_input_path = campaign / "analysis" / "analysis_input_index.json"
    merge_report_path = campaign / "analysis" / "merge_validation_report.json"
    rows: dict[str, dict[str, object]] = {}
    source_indexes: dict[str, object] = {}
    summary: dict[str, object] = {
        "available": False,
        "validated": False,
        "missing_scenario_ids": [],
        "environment_differences": [],
    }
    environments: dict[str, dict[str, object]] = {}
    if merged_path.is_file():
        validation = validate_merged_results(campaign)
        merged = read_json_mapping(merged_path)
        rows = {str(row["scenario_id"]): dict(row) for row in merged["scenario_results"]}
        source_indexes["merged_result_index"] = _identity(merged_path, campaign)
        summary.update(
            {
                "available": True,
                "validated": bool(validation["valid"]),
                "index_id": merged["index_id"],
                "index_sha256": merged["index_sha256"],
                "missing_scenario_ids": merged["missing_scenario_ids"],
            }
        )
    if analysis_input_path.is_file():
        source_indexes["analysis_input_index"] = _identity(analysis_input_path, campaign)
    if merge_report_path.is_file():
        report = read_json_mapping(merge_report_path)
        source_indexes["merge_validation_report"] = _identity(merge_report_path, campaign)
        summary["merge_status"] = report.get("status")
        summary["environment_differences"] = report.get("environment_differences", [])
        for raw in report.get("environment_summary", []):
            if isinstance(raw, Mapping) and raw.get("fingerprint_id"):
                environments[str(raw["fingerprint_id"])] = dict(raw)
    return {
        "rows": rows,
        "source_indexes": source_indexes,
        "summary": summary,
        "environments": environments,
    }


def _scenario_row(
    campaign: Path,
    scenario_id: str,
    resolved: Mapping[str, object],
    merged: Mapping[str, object] | None,
    state: Mapping[str, object],
    assignments: list[dict[str, object]],
    environments: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if str(resolved.get("scenario_id")) != scenario_id:
        raise AnalysisContractError(f"resolved scenario ID mismatch: {scenario_id}")
    scenario_hash = str(resolved.get("scenario_hash") or "")
    execution_state = str(state.get("state") or "pending")
    completion: CompletionReport | None = None
    result_root: str | None = None
    artifacts: dict[str, str] = {}
    environment_id: str | None = None
    environment: dict[str, object] | None = None

    if merged is not None:
        result_root = _portable_relative(merged.get("relative_path"))
        completion = validate_scenario_completion(campaign / result_root)
        if str(merged.get("scenario_hash")) != scenario_hash:
            raise AnalysisContractError(f"merged scenario hash mismatch: {scenario_id}")
        primary = merged.get("primary_source")
        if isinstance(primary, Mapping):
            environment_id = str(primary.get("environment_fingerprint_id") or "") or None
        environment = dict(environments.get(environment_id, {})) if environment_id else None
        artifacts = _artifact_paths(campaign, result_root)
        if completion.complete:
            analysis_status = "included"
            reason = "validated Stage 6 merged result"
        else:
            analysis_status = "invalid"
            reason = f"merged result failed completion validation: {completion.state}"
    else:
        local_root = campaign / "scenarios" / scenario_id
        if local_root.is_dir():
            completion = validate_scenario_completion(local_root)
        if execution_state in {
            "failed_retryable",
            "failed_terminal",
            "timeout",
            "out_of_memory",
            "interrupted",
            "stopped",
        }:
            analysis_status = "failed"
            reason = str(state.get("concise_error") or execution_state)
        elif execution_state == "invalid" or (completion and completion.state in {"corrupt", "incompatible"}):
            analysis_status = "invalid"
            reason = f"local result is {completion.state if completion else execution_state}"
        elif completion and completion.complete:
            analysis_status = "excluded"
            reason = "complete local result was not present in the validated Stage 6 merge index"
        else:
            analysis_status = "missing"
            reason = "no validated merged result exists"

    pipeline = resolved.get("pipeline") if isinstance(resolved.get("pipeline"), Mapping) else {}
    condition = resolved.get("condition") if isinstance(resolved.get("condition"), Mapping) else {}
    dataset_slice = (
        resolved.get("dataset_slice")
        if isinstance(resolved.get("dataset_slice"), Mapping)
        else {}
    )
    artifact_contract = (
        resolved.get("artifact_contract")
        if isinstance(resolved.get("artifact_contract"), Mapping)
        else {}
    )
    return {
        "scenario_id": scenario_id,
        "scenario_hash": scenario_hash,
        "analysis_status": analysis_status,
        "analysis_reason": reason,
        "execution_state": execution_state,
        "attempt_count": int(state.get("attempt_count") or 0),
        "worker_id": state.get("worker_id"),
        "assignment_ids": [item["assignment_id"] for item in assignments],
        "assigned_workers": [item["worker_id"] for item in assignments],
        "validation_state": completion.state if completion else "not_available",
        "validation_complete": bool(completion and completion.complete),
        "validation_issues": completion.to_jsonable()["issues"] if completion else [],
        "result_root": result_root,
        "artifact_paths": artifacts,
        "environment_fingerprint_id": environment_id,
        "environment_fingerprint": environment,
        "panel": resolved.get("panel"),
        "tier": resolved.get("tier"),
        "dataset": dataset_slice.get("dataset"),
        "dataset_slice": dict(dataset_slice),
        "scenario_type": artifact_contract.get("scenario_type") or _scenario_type(resolved),
        "condition_id": condition.get("id"),
        "augmentation": condition.get("augmentation"),
        "noise_type": condition.get("noise_type"),
        "snr_db": condition.get("snr_db"),
        "rir": condition.get("rir"),
        "seed": resolved.get("seed"),
        "repetition": resolved.get("repetition"),
        "component_identities": _component_identities(pipeline),
        "model_identities": _model_identities(pipeline),
        "benchmark_manifest": resolved.get("benchmark_manifest"),
        "scoring_policy_version": resolved.get("scoring_policy_version"),
    }


def _resolved_scenario(root: Path) -> dict[str, object]:
    path = root / "resolved_scenario.json"
    if not path.is_file():
        raise AnalysisContractError(f"planned scenario definition is missing: {path}")
    return read_json_mapping(path)


def _state_index(campaign: Path, campaign_id: str) -> dict[str, dict[str, object]]:
    path = campaign / "database" / "campaign.sqlite"
    if not path.is_file():
        return {}
    store = CampaignStateStore(path)
    return {
        row.scenario_id: {
            "state": row.state,
            "worker_id": row.worker_id,
            "attempt_count": row.attempt_count,
            "exception_category": row.exception_category,
            "concise_error": row.concise_error,
            "output_completeness": row.output_completeness,
            "retry_eligible": row.retry_eligible,
        }
        for row in store.scenarios(campaign_id)
    }


def _assignment_index(campaign: Path) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    root = campaign / "worker_assignments"
    for path in sorted(root.glob("*.yaml")) if root.is_dir() else []:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise AnalysisContractError(f"cannot read assignment {path}: {exc}") from exc
        if not isinstance(value, Mapping):
            raise AnalysisContractError(f"assignment is not a mapping: {path}")
        summary = {
            "assignment_id": value.get("assignment_id"),
            "worker_id": value.get("worker_id"),
            "path": path.relative_to(campaign).as_posix(),
            "assignment_sha256": value.get("assignment_sha256"),
        }
        for scenario_id in value.get("scenario_ids", []):
            result.setdefault(str(scenario_id), []).append(dict(summary))
    for rows in result.values():
        rows.sort(key=lambda item: str(item["assignment_id"]))
    return result


def _assignment_summaries(index: Mapping[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    unique: dict[str, dict[str, object]] = {}
    for rows in index.values():
        for row in rows:
            unique[str(row["assignment_id"])] = row
    return [unique[key] for key in sorted(unique)]


def _component_identities(pipeline: Mapping[str, object]) -> dict[str, object]:
    components = pipeline.get("components")
    if not isinstance(components, Mapping):
        return {}
    result: dict[str, object] = {}
    for family, raw in sorted(components.items()):
        if not isinstance(raw, Mapping):
            continue
        result[str(family)] = {
            key: raw.get(key)
            for key in (
                "name",
                "enabled",
                "implementation_class",
                "source_config_path",
                "source_config_sha256",
                "config_contents_sha256",
                "qualification_status",
            )
        }
    return result


def _model_identities(pipeline: Mapping[str, object]) -> dict[str, object]:
    models = pipeline.get("models")
    return dict(models) if isinstance(models, Mapping) else {}


def _scenario_type(resolved: Mapping[str, object]) -> str:
    components = _component_identities(
        resolved.get("pipeline") if isinstance(resolved.get("pipeline"), Mapping) else {}
    )
    enabled = {key for key, value in components.items() if value.get("enabled")}
    if "diarization" in enabled:
        return "diarization"
    if "speaker_matching" in enabled:
        return "speaker_verification"
    if "speaker_embedding" in enabled and "asr" not in enabled:
        return "embedding_extraction"
    if "asr" in enabled:
        return "asr"
    if "vad" in enabled:
        return "vad_only"
    return "unknown"


def _artifact_paths(campaign: Path, result_root: str) -> dict[str, str]:
    root = campaign / result_root
    result: dict[str, str] = {}
    for key, relative in OPTIONAL_ARTIFACTS:
        if (root / relative).is_file():
            result[key] = f"{result_root}/{relative}"
    return result


def _identity(path: Path, campaign: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(campaign).as_posix(),
        "sha256": file_sha256(path),
    }


def _materialize_registries(campaign: Path, registries) -> dict[str, object]:
    destination = campaign / "analysis" / "contracts"
    guide = Path(__file__).resolve().parents[2] / "docs" / "automated_evaluation" / "analysis_guide.md"
    sources = {
        "metric_registry": registries.metric_registry_path,
        "plot_report_registry": registries.plot_report_registry_path,
        "decision_policy": registries.decision_policy_path,
        "analysis_guide": guide,
    }
    identities: dict[str, object] = {}
    for key, source in sources.items():
        target = destination / source.name
        payload = source.read_bytes()
        if target.is_file() and target.read_bytes() != payload:
            raise AnalysisContractError(f"refusing to overwrite changed analysis contract: {target}")
        atomic_write_bytes(target, payload)
        identities[key] = _identity(target, campaign)
    return identities


def _portable_relative(value: object) -> str:
    text = str(value or "")
    if not text or "\\" in text or text.startswith("/") or ":" in text:
        raise AnalysisContractError(f"analysis path is not portable: {text!r}")
    parts = Path(text).parts
    if ".." in parts:
        raise AnalysisContractError(f"analysis path escapes campaign: {text!r}")
    return Path(text).as_posix()


def _status_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        status = str(row["analysis_status"])
        result[status] = result.get(status, 0) + 1
    return dict(sorted(result.items()))


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _timestamp(value: datetime | None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise AnalysisContractError("analysis timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _analysis_timestamp(campaign: Path, value: datetime | None) -> str:
    if value is not None:
        return _timestamp(value)
    existing = campaign / "analysis" / "analysis_manifest.json"
    if existing.is_file():
        previous = read_json_mapping(existing).get("created_at_utc")
        if isinstance(previous, str) and previous:
            return previous
    return _timestamp(None)
