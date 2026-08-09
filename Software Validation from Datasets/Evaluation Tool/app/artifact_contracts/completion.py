"""Registry-driven scenario completion and transfer validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app.artifact_contracts.atomic import file_sha256, find_temporary_artifacts
from app.artifact_contracts.registry import (
    ArtifactRegistry,
    ArtifactRegistryError,
    registry_for_scenario,
    scenario_type_from_resolved,
)
from app.artifact_contracts.schemas import (
    ArtifactInspection,
    ArtifactSchemaError,
    IncompatibleArtifactError,
    validate_artifact,
)


COMPLETION_STATES = ("complete", "incomplete", "corrupt", "incompatible")


@dataclass(frozen=True)
class ValidationIssue:
    """One machine-readable completion problem."""

    classification: str
    code: str
    artifact_path: str | None
    message: str

    def to_jsonable(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            "code": self.code,
            "artifact_path": self.artifact_path,
            "message": self.message,
        }


@dataclass(frozen=True)
class CompletionReport:
    """Final classified outcome for one scenario directory."""

    scenario_id: str
    state: str
    scenario_type: str | None
    expected_artifact_ids: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]
    observed_counts: Mapping[str, int]

    @property
    def complete(self) -> bool:
        return self.state == "complete"

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": "completion-validation.v1",
            "scenario_id": self.scenario_id,
            "state": self.state,
            "scenario_type": self.scenario_type,
            "expected_artifact_ids": list(self.expected_artifact_ids),
            "issues": [issue.to_jsonable() for issue in self.issues],
            "observed_counts": dict(sorted(self.observed_counts.items())),
        }


def validate_scenario_completion(
    scenario_root: Path,
    *,
    registry: ArtifactRegistry | None = None,
) -> CompletionReport:
    """Classify a scenario as complete, incomplete, corrupt, or incompatible."""

    active_registry = registry or registry_for_scenario(scenario_root)
    root = scenario_root.resolve()
    scenario_id = root.name
    issues: list[ValidationIssue] = []
    inspections: dict[str, list[ArtifactInspection]] = {}
    paths_by_id: dict[str, list[Path]] = {}
    resolved: dict[str, object] | None = None
    scenario_hash: str | None = None
    scenario_type: str | None = None
    required_ids: tuple[str, ...] = ()

    temporary_paths = frozenset(find_temporary_artifacts(root, active_registry))
    for temporary in temporary_paths:
        issues.append(
            _issue(
                "incomplete",
                "stale_temporary_file",
                _relative(temporary, root),
                "temporary artifact remains after interruption",
            )
        )

    resolved_path = root / "resolved_scenario.json"
    if not resolved_path.is_file():
        issues.append(
            _issue("incomplete", "missing_resolved_scenario", "resolved_scenario.json", "required artifact is missing")
        )
    else:
        try:
            inspection = validate_artifact(
                resolved_path,
                active_registry.get("resolved_scenario"),
                scenario_id=scenario_id,
            )
            resolved = dict(inspection.values or {})
            scenario_hash = str(resolved.get("scenario_hash") or "")
            if resolved.get("scenario_id") != scenario_id:
                issues.append(
                    _issue(
                        "corrupt",
                        "scenario_directory_mismatch",
                        "resolved_scenario.json",
                        "directory name does not match resolved scenario ID",
                    )
                )
            try:
                scenario_type = scenario_type_from_resolved(resolved)
                required_ids = active_registry.required_artifact_ids(resolved)
            except ArtifactRegistryError as exc:
                issues.append(
                    _issue("incompatible", "scenario_type", "resolved_scenario.json", str(exc))
                )
        except IncompatibleArtifactError as exc:
            issues.append(
                _issue("incompatible", "resolved_scenario_schema", "resolved_scenario.json", str(exc))
            )
        except ArtifactSchemaError as exc:
            issues.append(
                _issue("corrupt", "resolved_scenario_invalid", "resolved_scenario.json", str(exc))
            )

    for path in sorted(root.rglob("*")) if root.exists() else []:
        if not path.is_file() or path == resolved_path or path in temporary_paths:
            continue
        relative = _relative(path, root)
        try:
            definition = active_registry.match("scenario", relative)
        except ArtifactRegistryError as exc:
            issues.append(_issue("incompatible", "unregistered_artifact", relative, str(exc)))
            continue
        paths_by_id.setdefault(definition.artifact_id, []).append(path)
        try:
            inspection = validate_artifact(
                path,
                definition,
                scenario_id=scenario_id,
                scenario_hash=scenario_hash,
            )
            inspections.setdefault(definition.artifact_id, []).append(inspection)
        except IncompatibleArtifactError as exc:
            issues.append(
                _issue("incompatible", "unsupported_artifact_schema", relative, str(exc))
            )
        except ArtifactSchemaError as exc:
            issues.append(_issue("corrupt", "artifact_invalid", relative, str(exc)))

    if resolved_path.is_file():
        paths_by_id.setdefault("resolved_scenario", []).append(resolved_path)
        if resolved is not None:
            inspections.setdefault("resolved_scenario", []).append(
                ArtifactInspection(values=resolved)
            )

    for artifact_id in required_ids:
        if not paths_by_id.get(artifact_id):
            definition = active_registry.get(artifact_id)
            issues.append(
                _issue(
                    "incomplete",
                    "missing_required_artifact",
                    definition.path,
                    f"{artifact_id} is required for {scenario_type}",
                )
            )

    status = _mapping_from_inspections(inspections, "scenario_status")
    if status is not None:
        if status.get("state") != "successful":
            issues.append(
                _issue(
                    "incomplete",
                    "status_not_successful",
                    "status.json",
                    f"scenario state is {status.get('state')!r}",
                )
            )
        if scenario_type is not None and status.get("scenario_type") != scenario_type:
            issues.append(
                _issue(
                    "incompatible",
                    "scenario_type_mismatch",
                    "status.json",
                    "status scenario type differs from resolved scenario",
                )
            )
        if status.get("artifact_registry_version") != active_registry.schema_version:
            issues.append(
                _issue(
                    "incompatible",
                    "artifact_registry_version",
                    "status.json",
                    "status uses an unsupported artifact registry",
                )
            )

    _validate_checksums(
        root,
        active_registry,
        paths_by_id,
        inspections,
        issues,
    )
    observed_counts = _observed_counts(paths_by_id, inspections)
    if resolved is not None and status is not None and scenario_type is not None:
        _reconcile_counts(
            resolved,
            status,
            scenario_type,
            observed_counts,
            inspections,
            issues,
        )

    report = _mapping_from_inspections(inspections, "scenario_report_json")
    if report is not None and report.get("completion_state") != "complete":
        issues.append(
            _issue(
                "incomplete",
                "report_not_complete",
                "report/scenario_report.json",
                "successful scenario report must declare completion_state=complete",
            )
        )

    state = _classify(issues)
    return CompletionReport(
        scenario_id=scenario_id,
        state=state,
        scenario_type=scenario_type,
        expected_artifact_ids=required_ids,
        issues=tuple(issues),
        observed_counts=observed_counts,
    )


def _validate_checksums(
    root: Path,
    registry: ArtifactRegistry,
    paths_by_id: Mapping[str, list[Path]],
    inspections: Mapping[str, list[ArtifactInspection]],
    issues: list[ValidationIssue],
) -> None:
    checksum_values = _mapping_from_inspections(inspections, "checksums")
    if checksum_values is None:
        return
    if checksum_values.get("artifact_registry_version") != registry.schema_version:
        issues.append(
            _issue(
                "incompatible",
                "checksum_registry_version",
                "checksums.json",
                "checksum manifest uses an unsupported artifact registry",
            )
        )
    raw_entries = checksum_values.get("entries")
    if not isinstance(raw_entries, Mapping):
        return
    existing: dict[str, Path] = {}
    for artifact_id, paths in paths_by_id.items():
        if artifact_id == "checksums":
            continue
        definition = registry.get(artifact_id)
        if definition.checksum_policy != "sha256":
            continue
        for path in paths:
            existing[_relative(path, root)] = path
    for relative, path in existing.items():
        entry = raw_entries.get(relative)
        if not isinstance(entry, Mapping):
            issues.append(
                _issue(
                    "incomplete",
                    "missing_checksum_entry",
                    relative,
                    "materialized artifact has no checksum entry",
                )
            )
            continue
        definition = registry.match("scenario", relative)
        if entry.get("artifact_id") != definition.artifact_id or entry.get(
            "schema_version"
        ) != definition.schema_version:
            issues.append(
                _issue(
                    "incompatible",
                    "checksum_identity_mismatch",
                    relative,
                    "checksum entry does not match registry identity",
                )
            )
        if entry.get("bytes") != path.stat().st_size or entry.get("sha256") != file_sha256(path):
            issues.append(
                _issue(
                    "corrupt",
                    "checksum_mismatch",
                    relative,
                    "stored size or SHA-256 does not match artifact bytes",
                )
            )
    for relative in raw_entries:
        if relative not in existing:
            issues.append(
                _issue(
                    "incomplete",
                    "checksum_target_missing",
                    str(relative),
                    "checksum entry refers to a missing transfer artifact",
                )
            )


def _observed_counts(
    paths_by_id: Mapping[str, list[Path]],
    inspections: Mapping[str, list[ArtifactInspection]],
) -> dict[str, int]:
    mapping = {
        "utterance_predictions": "predictions",
        "diagnostics": "diagnostics",
        "item_metrics": "item_metrics",
        "grouped_metrics": "grouped_metrics",
        "failures": "failed_items",
        "words": "words",
        "vad_regions": "vad_regions",
        "embedding_index": "embeddings",
        "similarity_scores": "similarity_scores",
        "segments_rttm": "diarization_segments",
        "diarization_diagnostics": "diarization_diagnostics",
        "events": "events",
        "errors": "error_records",
    }
    observed: dict[str, int] = {}
    for artifact_id, count_name in mapping.items():
        values = inspections.get(artifact_id) or []
        observed[count_name] = sum(item.row_count or 0 for item in values)
    observed["embedding_files"] = len(paths_by_id.get("embedding_npz") or [])
    return observed


def _reconcile_counts(
    resolved: Mapping[str, object],
    status: Mapping[str, object],
    scenario_type: str,
    observed: Mapping[str, int],
    inspections: Mapping[str, list[ArtifactInspection]],
    issues: list[ValidationIssue],
) -> None:
    counts = status.get("counts")
    if not isinstance(counts, Mapping):
        return
    data_slice = resolved.get("dataset_slice")
    expected_selected = data_slice.get("row_count") if isinstance(data_slice, Mapping) else None
    selected = counts.get("selected_items")
    successful = counts.get("successful_items")
    failed = counts.get("failed_items")
    for field in ("selected_items", "successful_items", "failed_items", "diagnostics"):
        if field not in counts:
            issues.append(
                _issue(
                    "corrupt",
                    "missing_count",
                    "status.json",
                    f"status counts missing {field}",
                )
            )
    if expected_selected is not None and selected != expected_selected:
        issues.append(
            _issue(
                "corrupt",
                "selected_count_mismatch",
                "status.json",
                "selected_items does not match resolved dataset slice row_count",
            )
        )
    if isinstance(selected, int) and isinstance(successful, int) and isinstance(failed, int):
        if successful + failed != selected:
            issues.append(
                _issue(
                    "corrupt",
                    "outcome_count_mismatch",
                    "status.json",
                    "successful_items + failed_items must equal selected_items",
                )
            )
    comparisons = {
        "failed_items": ("failures", observed.get("failed_items")),
        "diagnostics": ("diagnostics", observed.get("diagnostics")),
        "grouped_metrics": ("grouped_metrics", observed.get("grouped_metrics")),
        "error_records": ("errors", observed.get("error_records")),
    }
    if scenario_type != "synthetic_executor":
        comparisons["item_metrics"] = ("item_metrics", observed.get("item_metrics"))
    if scenario_type == "asr":
        comparisons["predictions"] = (
            "utterance_predictions",
            observed.get("predictions"),
        )
    for name, (artifact_id, actual) in comparisons.items():
        if inspections.get(artifact_id) and name in counts and counts.get(name) != actual:
            issues.append(
                _issue(
                    "corrupt",
                    "observed_count_mismatch",
                    "status.json",
                    f"stored {name}={counts.get(name)!r}, observed {actual!r}",
                )
            )
    if counts.get("diagnostics") != successful:
        issues.append(
            _issue(
                "corrupt",
                "diagnostic_count_mismatch",
                "status.json",
                "one diagnostic row is required per successful item",
            )
        )
    if scenario_type == "asr" and counts.get("predictions") != successful:
        issues.append(
            _issue(
                "corrupt",
                "prediction_count_mismatch",
                "status.json",
                "one utterance prediction is required per successful ASR item",
            )
        )
    if scenario_type != "synthetic_executor" and counts.get("item_metrics") != selected:
        issues.append(
            _issue(
                "corrupt",
                "metric_count_mismatch",
                "status.json",
                "one item metric row is required per selected item",
            )
        )
    if scenario_type in {"embedding_extraction", "speaker_verification"} and inspections.get(
        "embedding_index"
    ):
        if observed.get("embeddings") != successful or observed.get("embedding_files") != successful:
            issues.append(
                _issue(
                    "corrupt",
                    "embedding_count_mismatch",
                    "predictions/embeddings",
                    "embedding index rows and NPZ files must equal successful_items",
                )
            )
    conditional_artifacts = {
        "words": "words",
        "vad_regions": "vad_regions",
        "similarity_scores": "similarity_scores",
        "diarization_segments": "segments_rttm",
        "diarization_diagnostics": "diarization_diagnostics",
    }
    for count_name, artifact_id in conditional_artifacts.items():
        if (
            inspections.get(artifact_id)
            and count_name in counts
            and counts[count_name] != observed.get(count_name)
        ):
            issues.append(
                _issue(
                    "corrupt",
                    "conditional_count_mismatch",
                    "status.json",
                    f"stored {count_name} does not match materialized rows",
                )
            )
    summary = _mapping_from_inspections(inspections, "metrics_summary")
    if summary is not None and summary.get("counts") != counts:
        issues.append(
            _issue(
                "corrupt",
                "summary_count_mismatch",
                "metrics/summary.json",
                "metrics summary counts must exactly match status counts",
            )
        )


def _mapping_from_inspections(
    inspections: Mapping[str, list[ArtifactInspection]], artifact_id: str
) -> Mapping[str, object] | None:
    values = inspections.get(artifact_id) or []
    if not values:
        return None
    return values[0].values


def _classify(issues: list[ValidationIssue]) -> str:
    classifications = {issue.classification for issue in issues}
    for state in ("incompatible", "corrupt", "incomplete"):
        if state in classifications:
            return state
    return "complete"


def _issue(
    classification: str,
    code: str,
    artifact_path: str | None,
    message: str,
) -> ValidationIssue:
    return ValidationIssue(classification, code, artifact_path, message)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
