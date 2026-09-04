"""Prompt-5 all-18 tables, failure inventory, bootstrap, and report builder."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline_evaluation.io import read_json, write_json_atomic
from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_evaluation.store import EvaluationStateStore
from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES,
    FUTURE_LINUX_ARM64_VALIDATION,
    FUTURE_TARGET_HARDWARE_TESTS,
    LINUX_ARM64_PORTABILITY_CLASSES,
    RASPBERRY_PI_CANDIDATE_FIELDS,
    TWO_GIB_FEASIBILITY_CLASSES,
    DeploymentEvidenceError,
    classify_linux_arm64,
    classify_two_gib,
    evidence,
    load_deployment_steering,
    steering_ref,
    unknown_evidence,
    unsupported_evidence,
    validate_deployment_evidence_document,
)

from . import (
    DEPLOYMENT_EVIDENCE_FILE,
    EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
    TOOL_ROOT,
)
from .bootstrap import bootstrap_intervals, paired_comparisons
from .controller import layout, validate_resources, _validate_terminal_jobs
from .io import scope_fields, storage_preflight, write_csv
from .sufficient_stats import (
    extract_sufficient_statistics,
    read_sufficient_statistics,
)


VIEW_FILES = {
    "asr": "all18_asr.csv",
    "diarization": "all18_diarization.csv",
    "identity": "all18_identity.csv",
    "speaker_transcription": "all18_speaker_attributed_transcript.csv",
    "streaming": "all18_streaming.csv",
    "resources": "all18_resources.csv",
}
REQUIRED_METRIC_CATEGORIES = (
    "asr",
    "diarization",
    "identity",
    "speaker_transcription",
    "streaming",
    "ux",
    "resources",
)
CONDITIONAL_METRIC_POPULATION = "CHECKSUM_COMPLETE_JOB_OUTPUTS_ONLY"
END_TO_END_COVERAGE_POPULATION = "ALL_PLANNED_JOBS_INCLUDING_EXPLICIT_FAILURES"
ADDITIVE_METRICS = {
    "substitutions",
    "deletions",
    "insertions",
    "output_failure_count",
    "correctly_named_known_time_sec",
    "wrong_known_time_sec",
    "stranger_false_known_time_sec",
    "generic_known_time_sec",
    "uncovered_known_time_sec",
    "identity_split_count",
    "identity_merge_count",
    "identity_revision_count",
    "wrong_speaker_word_count",
    "wrong_speaker_word_time_sec",
    "retroactive_correction_count",
    "transcript_revision_count",
    "ux_identity_revision_count",
    "failure_count",
    "retry_count",
}


def analyze(*, workspace_root: Path) -> dict[str, object]:
    paths = layout(workspace_root)
    storage_preflight(paths.root)
    accuracy_validation = _validate_terminal_jobs(
        paths.accuracy, expected_job_count=126
    )
    resource_validation = validate_resources(paths.root)
    paths.report.mkdir(parents=True, exist_ok=True)
    stats_path = paths.report / "speaker_sufficient_statistics.jsonl.gz"
    extraction = extract_sufficient_statistics(paths.accuracy, output_path=stats_path)
    stats = read_sufficient_statistics(stats_path)
    bootstrap_rows = bootstrap_intervals(stats)
    comparison_rows = paired_comparisons(stats)
    write_csv(paths.report / "bootstrap_intervals.csv", bootstrap_rows)
    write_csv(paths.report / "paired_comparisons.csv", comparison_rows)

    accuracy_metrics = _campaign_metric_rows(paths.accuracy)
    resource_metrics = _campaign_metric_rows(paths.resources)
    # Resource jobs run the whole pipeline so their result trees also contain
    # one-case ASR/diarization/identity views.  Those diagnostic views must not
    # leak into the held-out accuracy denominators.  Only the resource view is
    # taken from the standardized serial campaign; every other table comes
    # exclusively from the common accuracy panel.
    failures = [
        *_failure_inventory(paths.accuracy, campaign_kind="accuracy"),
        *_failure_inventory(paths.resources, campaign_kind="resources"),
    ]
    wide_by_category = _separated_metric_tables(
        accuracy_metrics=accuracy_metrics,
        resource_metrics=resource_metrics,
    )
    wide_by_category = _attach_failure_coverage(wide_by_category, failures)
    for category, filename in VIEW_FILES.items():
        categories = ("streaming", "ux") if category == "streaming" else (category,)
        rows = [
            row
            for source_category in categories
            for row in wide_by_category.get(source_category, [])
        ]
        if category == "streaming":
            rows = _merge_category_rows(rows)
        write_csv(paths.report / filename, rows)

    write_csv(paths.report / "all18_failures.csv", failures)
    summary_rows = _finalist_summary(wide_by_category, failures)
    write_csv(paths.report / "all18_finalist_summary.csv", summary_rows)
    deployment_evidence = _deployment_evidence_document(
        paths,
        resource_rows=wide_by_category["resources"],
    )
    deployment_evidence_path = paths.report / DEPLOYMENT_EVIDENCE_FILE
    write_json_atomic(deployment_evidence_path, deployment_evidence)
    report = _evaluation_report(
        paths,
        summary_rows=summary_rows,
        failure_rows=failures,
        extraction=extraction,
        bootstrap_rows=bootstrap_rows,
    )
    (paths.report / "evaluation_report.md").write_text(report, encoding="utf-8")
    analysis = {
        "schema_version": "full-pipeline-core-analysis.v1",
        **scope_fields(),
        "status": "PASS",
        "pipeline_count": 18,
        "accuracy_validation": accuracy_validation,
        "resource_validation": resource_validation,
        "sufficient_statistics": extraction,
        "bootstrap_interval_count": len(bootstrap_rows),
        "paired_comparison_count": len(comparison_rows),
        "failure_inventory_row_count": len(failures),
        "deployment_evidence": {
            "path": str(deployment_evidence_path.resolve()),
            "sha256": _sha256_file(deployment_evidence_path),
            "pipeline_count": len(deployment_evidence["pipelines"]),
        },
        "weighted_composite_score_created": False,
        "production_winner_selected": False,
        "held_out_retuning_performed": False,
    }
    write_json_atomic(paths.report / "analysis.json", analysis)
    return analysis


def _deployment_evidence_document(
    paths,
    *,
    resource_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build additive deployment evidence without selecting or retuning."""

    authorization = read_json(paths.authorization)
    authority = authorization.get("deployment_steering")
    if not isinstance(authority, Mapping):
        raise DeploymentEvidenceError(
            "Prompt-5 authorization lacks deployment steering"
        )
    steering_path = Path(str(authority.get("path") or ""))
    steering = load_deployment_steering(
        steering_path,
        expected_prompt_index=5,
        expected_sha256=EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
    )
    current_authority = steering_ref(steering_path, steering)
    if dict(authority) != current_authority:
        raise DeploymentEvidenceError(
            "Prompt-5 authorization deployment steering reference differs"
        )
    resource_path = paths.report / VIEW_FILES["resources"]
    if not resource_path.is_file():
        raise DeploymentEvidenceError("serial resource report is missing")
    resources = {str(row.get("pipeline_id") or ""): row for row in resource_rows}
    pipeline_ids = list(matrix().pipeline_ids)
    if list(resources) != pipeline_ids:
        raise DeploymentEvidenceError(
            "serial resource rows do not preserve exact all-18 matrix order"
        )
    pipeline_rows = [
        _pipeline_deployment_evidence(
            pipeline_id,
            resource_row=resources[pipeline_id],
            resource_path=resource_path,
        )
        for pipeline_id in pipeline_ids
    ]
    document = {
        "schema_version": "full-pipeline-all18-deployment-evidence.v1",
        **scope_fields(),
        "status": "PASS",
        "prompt_index": 5,
        "steering_authority": current_authority,
        "input_binding": {
            "prompt5_authorization_path": str(paths.authorization.resolve()),
            "prompt5_authorization_sha256": _sha256_file(paths.authorization),
            "deployment_steering_path": current_authority["path"],
            "deployment_steering_sha256": current_authority["sha256"],
            "deployment_steering_schema_version": current_authority["schema_version"],
            "deployment_steering_id": current_authority["steering_id"],
            "deployment_steering_status": current_authority["status"],
            "serial_resources_path": str(resource_path.resolve()),
            "serial_resources_sha256": _sha256_file(resource_path),
        },
        "evidence_policy": {
            "unknown_or_unsupported_explicit": True,
            "desktop_measurement_relabelled_as_arm": False,
            "model_or_scientific_execution_modified_to_measure": False,
            "uncertainty_separate_from_feasibility_class": True,
        },
        "classification_policy": {
            "two_gib_is_design_constraint_not_prompt5_filter": True,
            "likely_2gb_requires_target_hardware_evidence": True,
            "desktop_rss_below_2gb_is_at_most_possibly_feasible": True,
            "final_raspberry_pi_winner_claimed": False,
        },
        "platform_portability_policy": {
            "current_platform": "WINDOWS_X86_64",
            "future_target_platform": "LINUX_DEBIAN_RASPBERRY_PI_OS_ARM64",
            "portability_separate_from_desktop_scientific_rank": True,
            "linux_arm64_ready_requires_actual_target_validation": True,
            "desktop_rank_used_as_final_arm_rank": False,
        },
        "pipeline_count": len(pipeline_ids),
        "pipeline_ids": pipeline_ids,
        "deployment_attribute_names": list(DEPLOYMENT_ATTRIBUTE_NAMES),
        "two_gib_feasibility_classes": list(TWO_GIB_FEASIBILITY_CLASSES),
        "linux_arm64_portability_classes": list(LINUX_ARM64_PORTABILITY_CLASSES),
        "raspberry_pi_candidate_fields": list(RASPBERRY_PI_CANDIDATE_FIELDS),
        "future_target_hardware_tests": list(FUTURE_TARGET_HARDWARE_TESTS),
        "future_linux_arm64_validation": list(FUTURE_LINUX_ARM64_VALIDATION),
        "pipelines": pipeline_rows,
        "scientific_firewall": {
            "scientific_methodology_changed": False,
            "pipeline_membership_changed": False,
            "heldout_selection_or_retuning_performed": False,
            "deployment_evidence_used_as_filter": False,
            "desktop_rank_used_as_final_arm_rank": False,
        },
    }
    validate_deployment_evidence_document(
        document,
        schema_version="full-pipeline-all18-deployment-evidence.v1",
        prompt_index=5,
        expected_pipeline_ids=pipeline_ids,
        steering=steering,
    )
    return document


def _pipeline_deployment_evidence(
    pipeline_id: str,
    *,
    resource_row: Mapping[str, object],
    resource_path: Path,
) -> dict[str, object]:
    selection = matrix().resolve(pipeline_id)
    matrix_path = matrix().matrix_path
    environment_profiles = list(
        dict.fromkeys(
            str(value)
            for value in (
                selection.asr.get("environment_profile"),
                selection.diarization.get("segmentation_environment_profile"),
                selection.diarization.get("embedding_environment_profile"),
                selection.identity.get("environment_profile"),
            )
            if value
        )
    )
    package_identities = list(
        dict.fromkeys(
            str(value)
            for value in (
                selection.asr.get("package_identity"),
                selection.diarization_embedding.get("package_identity"),
                selection.identity.get("package_identity"),
            )
            if value
        )
    )
    same_embedding_backend = str(
        selection.diarization_embedding.get("backend_id") or ""
    ) == str(selection.identity.get("backend_id") or "")
    asr_files = selection.asr.get("model_asset", {})
    asr_result_files = (
        asr_files.get("result_affecting_files", {})
        if isinstance(asr_files, Mapping)
        else {}
    )
    asr_onnx_files = [
        str(name) for name in asr_result_files if str(name).casefold().endswith(".onnx")
    ]
    int8_asr_files = [
        name for name in asr_onnx_files if ".int8.onnx" in name.casefold()
    ]
    embedding_dimensions = {
        "diarization": int(
            selection.diarization_embedding.get("embedding_dimension") or 0
        ),
        "identity": int(selection.identity.get("embedding_dimension") or 0),
    }
    config = lambda value, unit, reason, field, details=None: evidence(  # noqa: E731
        value,
        unit=unit,
        evidence_status="DERIVED",
        reason_code=reason,
        measurement_context="FROZEN_CONFIGURATION",
        source_path=matrix_path,
        source_field=field,
        details=details,
    )
    attributes = {
        "model_file_size_bytes": _resource_metric_evidence(
            resource_row, "model_bytes", resource_path, "bytes"
        ),
        "loaded_model_memory_bytes": unknown_evidence(
            unit="bytes",
            reason_code="NO_COMPONENT_LOADED_MEMORY_ATTRIBUTION",
            source_path=resource_path,
            source_field="peak_rss_bytes",
        ),
        "peak_process_rss_bytes": unknown_evidence(
            unit="bytes",
            reason_code="RESOURCE_METRIC_IS_PROCESS_TREE_NOT_SINGLE_PROCESS",
            source_path=resource_path,
            source_field="peak_rss_bytes",
        ),
        "total_pipeline_peak_rss_bytes": _resource_metric_evidence(
            resource_row, "peak_rss_bytes", resource_path, "bytes"
        ),
        "simultaneously_resident_neural_model_count": unknown_evidence(
            unit="count",
            reason_code="MODEL_RESIDENCY_COUNT_NOT_INSTRUMENTED",
            source_path=resource_path,
        ),
        "worker_process_count": unknown_evidence(
            unit="count",
            reason_code="PROCESS_TELEMETRY_DOES_NOT_IDENTIFY_WORKER_ROLES",
            source_path=resource_path,
        ),
        "runtime_environment_count": config(
            len(environment_profiles),
            "count",
            "UNIQUE_FROZEN_ENVIRONMENT_PROFILES",
            f"pipelines.{pipeline_id}.components.environment_profiles",
            {"environment_profiles": environment_profiles},
        ),
        "embedding_dimensions": config(
            embedding_dimensions,
            "dimensions",
            "FROZEN_EMBEDDING_COMPONENT_DIMENSIONS",
            f"pipelines.{pipeline_id}.embedding_dimensions",
        ),
        "persistent_enrollment_template_memory_bytes": unknown_evidence(
            unit="bytes",
            reason_code="ENROLLMENT_POPULATION_AND_TEMPLATE_COUNT_NOT_RESOURCE_MEASURED",
            source_path=matrix_path,
            source_field=f"pipelines.{pipeline_id}.enrollment_policy",
        ),
        "cache_requirements_bytes": _resource_metric_evidence(
            resource_row, "cache_bytes", resource_path, "bytes"
        ),
        "initialization_time_sec": _resource_metric_evidence(
            resource_row, "model_startup_sec", resource_path, "seconds"
        ),
        "warmup_time_sec": unsupported_evidence(
            unit="seconds",
            reason_code="WARMUP_DURATION_NOT_EXPOSED_BY_PROMPT5_RESOURCE_METRICS",
            source_path=resource_path,
        ),
        "native_onnx_availability": config(
            {
                "asr": "AVAILABLE_CURRENT_ASSET" if asr_onnx_files else "UNKNOWN",
                "segmentation": "UNKNOWN",
                "diarization_embedding": "UNKNOWN",
                "identity_embedding": "UNKNOWN",
                "complete_pipeline_native_onnx": False,
            },
            "structured_status",
            "CURRENT_FROZEN_ASSET_FORMATS_ONLY",
            f"pipelines.{pipeline_id}.asr.model_asset.result_affecting_files",
            {"asr_onnx_files": asr_onnx_files},
        ),
        "pytorch_dependency": config(
            {
                "asr": False,
                "segmentation": True,
                "diarization_embedding_package": str(
                    selection.diarization_embedding.get("package_identity") or "UNKNOWN"
                ),
                "identity_embedding_package": str(
                    selection.identity.get("package_identity") or "UNKNOWN"
                ),
            },
            "structured_status",
            "CURRENT_FROZEN_RUNTIME_DEPENDENCY_DECLARATIONS",
            f"pipelines.{pipeline_id}.components",
        ),
        "arm_compatibility_status": unknown_evidence(
            unit="status",
            reason_code="NO_LINUX_ARM64_BUILD_OR_EXECUTION_IN_PROMPT5",
            source_path=matrix_path,
            source_field=f"pipelines.{pipeline_id}",
        ),
        "int8_status": config(
            {
                "asr_int8_files": int8_asr_files,
                "asr_partial_or_full_int8": bool(int8_asr_files),
                "segmentation": "UNKNOWN",
                "diarization_embedding": "UNKNOWN",
                "identity_embedding": "UNKNOWN",
            },
            "structured_status",
            "CURRENT_FROZEN_ASSET_FILENAMES_ONLY",
            f"pipelines.{pipeline_id}.asr.model_asset.result_affecting_files",
        ),
        "fp16_status": unknown_evidence(
            unit="status",
            reason_code="FP16_EXPORT_OR_RUNTIME_NOT_EVALUATED",
            source_path=matrix_path,
            source_field=f"pipelines.{pipeline_id}",
        ),
        "export_status": config(
            {
                "asr_current_asset": "NATIVE_ONNX" if asr_onnx_files else "UNKNOWN",
                "segmentation": "NOT_ESTABLISHED",
                "diarization_embedding": "NOT_ESTABLISHED",
                "identity_embedding": "NOT_ESTABLISHED",
                "complete_pipeline_export": "NOT_ESTABLISHED",
            },
            "structured_status",
            "CURRENT_ASSET_FORMAT_NOT_EXPORT_FEASIBILITY",
            f"pipelines.{pipeline_id}.components",
        ),
        "quantization_readiness": unknown_evidence(
            unit="status",
            reason_code="NO_EXPORT_PARITY_OR_QUANTIZATION_STUDY",
            source_path=matrix_path,
            source_field=f"pipelines.{pipeline_id}",
        ),
        "executorch_feasibility": unknown_evidence(
            unit="status",
            reason_code="EXECUTORCH_EXPORT_NOT_ATTEMPTED",
            source_path=matrix_path,
            source_field=f"pipelines.{pipeline_id}",
        ),
        "onnx_runtime_export_feasibility": unknown_evidence(
            unit="status",
            reason_code="NON_ASR_ONNX_EXPORT_AND_PARITY_NOT_ATTEMPTED",
            source_path=matrix_path,
            source_field=f"pipelines.{pipeline_id}",
            details={"asr_current_native_onnx": bool(asr_onnx_files)},
        ),
        "model_instance_sharing_opportunities": config(
            {
                "same_diarization_and_identity_backend": same_embedding_backend,
                "potential_only": same_embedding_backend,
                "measured_shared_instance_benefit": False,
            },
            "structured_status",
            "FROZEN_BACKEND_IDENTITY_COMPARISON_ONLY",
            f"pipelines.{pipeline_id}.components",
        ),
        "embedding_reuse_opportunities": config(
            {
                "same_diarization_and_identity_backend": same_embedding_backend,
                "potential_only": same_embedding_backend,
                "scientific_role_keys_must_remain_distinct": True,
                "measured_reuse_benefit": False,
            },
            "structured_status",
            "FROZEN_BACKEND_IDENTITY_COMPARISON_ONLY",
            f"pipelines.{pipeline_id}.components",
        ),
        "duplicated_feature_extraction": unknown_evidence(
            unit="status",
            reason_code="FEATURE_EXTRACTION_DUPLICATION_NOT_INSTRUMENTED",
            source_path=resource_path,
        ),
        "dependency_complexity": config(
            {
                "runtime_environment_count": len(environment_profiles),
                "environment_profiles": environment_profiles,
                "declared_package_identities": package_identities,
                "linux_arm64_installability_tested": False,
            },
            "structured_status",
            "FROZEN_ENVIRONMENT_AND_PACKAGE_DECLARATIONS",
            f"pipelines.{pipeline_id}.components",
        ),
    }
    windows_assumptions = evidence(
        [
            {
                "assumption": "Prompt-5 launcher and controller are qualified on Windows",
                "scope": "orchestration_and_measurement",
            },
            {
                "assumption": "serial resource values are Windows/x86_64 desktop evidence",
                "scope": "resource_interpretation",
            },
        ],
        unit="structured_status",
        evidence_status="DERIVED",
        reason_code="CURRENT_EVALUATION_PLATFORM_DECLARATION",
        measurement_context="FROZEN_CONFIGURATION",
        source_path=TOOL_ROOT / "scripts/run_full_pipeline_core_evaluation.ps1",
        source_field="PowerShell C-only Prompt-5 launcher",
    )
    dependency_status = unknown_evidence(
        unit="structured_status",
        reason_code="LINUX_ARM64_DEPENDENCY_INSTALL_AND_LOAD_NOT_TESTED",
        source_path=matrix_path,
        source_field=f"pipelines.{pipeline_id}.components",
        details={
            "declared_package_identities": package_identities,
            "environment_profiles": environment_profiles,
        },
    )
    replacements = unknown_evidence(
        unit="structured_status",
        reason_code="REQUIRED_ARM64_EXPORT_OR_REPLACEMENT_LIBRARIES_NOT_ESTABLISHED",
        source_path=matrix_path,
        source_field=f"pipelines.{pipeline_id}.components",
        details={
            "must_validate": [
                "segmentation_runtime",
                "diarization_embedding_runtime",
                "identity_embedding_runtime",
                "audio_capture_and_service_startup",
            ]
        },
    )
    two_gib = classify_two_gib(attributes["total_pipeline_peak_rss_bytes"])
    portability = classify_linux_arm64(
        windows_specific_assumptions=windows_assumptions,
        linux_arm64_dependency_status=dependency_status,
        required_platform_replacements=replacements,
    )
    return {
        "pipeline_id": pipeline_id,
        "asr_alias": selection.asr_alias,
        "asr_component_id": selection.asr.get("component_id"),
        "segmentation_component_id": selection.diarization.get("segmentation_id"),
        "diarization_alias": selection.diarization_alias,
        "diarization_embedding_backend_id": selection.diarization_embedding.get(
            "backend_id"
        ),
        "identity_alias": selection.identity_alias,
        "identity_embedding_backend_id": selection.identity.get("backend_id"),
        "hybrid_label": selection.hybrid_label,
        "deployment_attributes": attributes,
        "desktop_resource_context": {
            "operating_system": "WINDOWS",
            "architecture": "X86_64",
            "serial_resource_sample": True,
            "resource_report_path": str(resource_path.resolve()),
            "resource_report_sha256": _sha256_file(resource_path),
            "arm_measurement": False,
        },
        "two_gib_feasibility": two_gib,
        "linux_arm64_portability": portability,
        "windows_specific_assumptions": windows_assumptions,
        "linux_arm64_dependency_status": dependency_status,
        "required_platform_replacements": replacements,
        "used_to_filter_pipeline": False,
    }


def _resource_metric_evidence(
    row: Mapping[str, object], metric_id: str, source_path: Path, unit: str
) -> dict[str, object]:
    status = str(row.get(f"{metric_id}__status") or "missing")
    value = row.get(metric_id)
    if status in {"computed", "supported"} and value is not None:
        return evidence(
            value,
            unit=unit,
            evidence_status="MEASURED",
            reason_code="STANDARDIZED_SERIAL_RESOURCE_SAMPLE",
            measurement_context="WINDOWS_X86_64_DESKTOP",
            source_path=source_path,
            source_field=metric_id,
            desktop_measurement=True,
            details={
                "aggregation": row.get(f"{metric_id}__aggregation"),
                "status": status,
            },
        )
    return unsupported_evidence(
        unit=unit,
        reason_code="SERIAL_RESOURCE_METRIC_UNSUPPORTED_OR_MISSING",
        source_path=source_path,
        source_field=metric_id,
        details={"metric_status": status},
    )


def _sha256_file(path: Path) -> str:
    from app.full_pipeline_evaluation.io import sha256_file

    return sha256_file(path)


def _campaign_metric_rows(root: Path) -> list[dict[str, object]]:
    paths = read_json(root / "campaign_paths.json")
    results_root = Path(str(paths["results_root"])).resolve()
    store = EvaluationStateStore(root / "campaign.sqlite3")
    values: list[dict[str, object]] = []
    for state in store.list_jobs(states=("complete",)):
        result_root = results_root / state.spec.result_relative_path
        for view in ("asr", "diarization", "identity", "streaming", "resources"):
            document_path = result_root / f"metrics/{view}.json"
            if not document_path.is_file():
                continue
            document = read_json(document_path)
            for category, metric_id, metric in _flatten_metric_document(document, view):
                values.append(
                    {
                        "pipeline_id": state.spec.pipeline_id,
                        "category": category,
                        "metric_id": metric_id,
                        "source_key": state.spec.source_key,
                        "job_id": state.spec.job_id,
                        "case_count": state.spec.case_count,
                        "status": metric.get("status"),
                        "value": metric.get("value"),
                        "numerator": metric.get("numerator"),
                        "denominator": metric.get("denominator"),
                        "reason": metric.get("reason"),
                        "unit": metric.get("unit"),
                        "higher_is_better": metric.get("higher_is_better"),
                        "details": metric.get("details") or {},
                    }
                )
    return values


def _separated_metric_tables(
    *,
    accuracy_metrics: Sequence[Mapping[str, object]],
    resource_metrics: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    tables = _wide_metric_tables(accuracy_metrics)
    serial_resource_rows = [
        row for row in resource_metrics if row.get("category") == "resources"
    ]
    resource_tables = _wide_metric_tables(serial_resource_rows)
    tables["resources"] = resource_tables.get(
        "resources",
        [
            {
                **scope_fields(),
                "pipeline_id": pipeline,
                "category": "resources",
                "row_status": "MISSING",
            }
            for pipeline in matrix().pipeline_ids
        ],
    )
    return tables


def _flatten_metric_document(
    document: Mapping[str, object], fallback_category: str
) -> list[tuple[str, str, Mapping[str, object]]]:
    rows: list[tuple[str, str, Mapping[str, object]]] = []
    subviews = document.get("subviews")
    if isinstance(subviews, Mapping):
        for category, report in subviews.items():
            if not isinstance(report, Mapping):
                continue
            metrics = report.get("metrics")
            if isinstance(metrics, Mapping):
                rows.extend(
                    (str(category), str(metric_id), metric)
                    for metric_id, metric in metrics.items()
                    if isinstance(metric, Mapping)
                )
        return rows
    metrics = document.get("metrics")
    if isinstance(metrics, Mapping):
        rows.extend(
            (fallback_category, str(metric_id), metric)
            for metric_id, metric in metrics.items()
            if isinstance(metric, Mapping)
        )
    return rows


def _wide_metric_tables(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[
            (str(row["pipeline_id"]), str(row["category"]), str(row["metric_id"]))
        ].append(row)
    by_category: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for (pipeline, category, metric_id), values in sorted(grouped.items()):
        target = by_category[category].setdefault(
            pipeline,
            {
                **scope_fields(),
                "pipeline_id": pipeline,
                "category": category,
            },
        )
        aggregate = _aggregate_metric(metric_id, values)
        target[metric_id] = aggregate["value"]
        target[f"{metric_id}__status"] = aggregate["status"]
        target[f"{metric_id}__aggregation"] = aggregate["aggregation"]
        target[f"{metric_id}__applicable_jobs"] = aggregate["applicable_jobs"]
        target[f"{metric_id}__unsupported_jobs"] = aggregate["unsupported_jobs"]
    expected = list(matrix().pipeline_ids)
    categories = tuple(
        dict.fromkeys((*REQUIRED_METRIC_CATEGORIES, *sorted(by_category)))
    )
    return {
        category: [
            pipelines.get(
                pipeline,
                {
                    **scope_fields(),
                    "pipeline_id": pipeline,
                    "category": category,
                    "row_status": "MISSING",
                    "conditional_metric_population": CONDITIONAL_METRIC_POPULATION,
                    "end_to_end_coverage_population": END_TO_END_COVERAGE_POPULATION,
                },
            )
            for pipeline in expected
        ]
        for category in categories
        for pipelines in (by_category.get(category, {}),)
    }


def _aggregate_metric(
    metric_id: str, rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    computed = [
        row
        for row in rows
        if str(row.get("status")) in {"computed", "supported"}
        and row.get("value") is not None
    ]
    if not computed:
        reasons = sorted({str(row.get("reason")) for row in rows if row.get("reason")})
        return {
            "status": "unsupported",
            "value": None,
            "aggregation": "no_computed_job",
            "applicable_jobs": 0,
            "unsupported_jobs": len(rows),
            "reasons": reasons,
        }
    sufficient = [
        row
        for row in computed
        if row.get("numerator") is not None and row.get("denominator") is not None
    ]
    if len(sufficient) == len(computed):
        numerator = sum(float(row["numerator"]) for row in sufficient)
        denominator = sum(float(row["denominator"]) for row in sufficient)
        value = numerator / denominator if denominator else None
        aggregation = "micro_sufficient_statistics"
        status = "computed" if denominator else "undefined"
    elif metric_id in ADDITIVE_METRICS or all(
        (row.get("details") or {}).get("scalar_aggregation") == "sum"
        for row in computed
    ):
        value = sum(float(row["value"]) for row in computed)
        aggregation = "sum_across_disjoint_jobs"
        status = "computed"
    else:
        weights = [
            float(
                (row.get("details") or {}).get("applicable_recording_count")
                or row["case_count"]
            )
            for row in computed
        ]
        total = sum(weights)
        value = (
            sum(float(row["value"]) * weight for row, weight in zip(computed, weights))
            / total
            if total
            else None
        )
        aggregation = "case_count_weighted_mean_across_disjoint_jobs"
        status = "computed" if total else "undefined"
    return {
        "status": status,
        "value": value,
        "aggregation": aggregation,
        "applicable_jobs": len(computed),
        "unsupported_jobs": len(rows) - len(computed),
    }


def _merge_category_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for row in rows:
        pipeline = str(row["pipeline_id"])
        target = merged.setdefault(
            pipeline,
            {**scope_fields(), "pipeline_id": pipeline, "category": "streaming_and_ux"},
        )
        prefix = "ux__" if row.get("category") == "ux" else ""
        for key, value in row.items():
            if key in {
                "scope_id",
                "scope_class",
                "original_full_scope_complete",
                "pipeline_id",
                "category",
            }:
                continue
            target[f"{prefix}{key}"] = value
    return [
        merged.get(
            pipeline,
            {
                **scope_fields(),
                "pipeline_id": pipeline,
                "category": "streaming_and_ux",
                "row_status": "MISSING",
                "conditional_metric_population": CONDITIONAL_METRIC_POPULATION,
                "end_to_end_coverage_population": END_TO_END_COVERAGE_POPULATION,
            },
        )
        for pipeline in matrix().pipeline_ids
    ]


def _attach_failure_coverage(
    tables: Mapping[str, Sequence[Mapping[str, object]]],
    failures: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Attach failure-inclusive coverage without fabricating accuracy scores."""

    coverage = _pipeline_failure_coverage(failures)
    output: dict[str, list[dict[str, object]]] = {}
    for category in REQUIRED_METRIC_CATEGORIES:
        campaign_kind = "resources" if category == "resources" else "accuracy"
        rows_by_pipeline = {
            str(row.get("pipeline_id")): dict(row) for row in tables.get(category, ())
        }
        output[category] = []
        for pipeline_id in matrix().pipeline_ids:
            row = rows_by_pipeline.get(
                pipeline_id,
                {
                    **scope_fields(),
                    "pipeline_id": pipeline_id,
                    "category": category,
                    "row_status": "MISSING",
                },
            )
            row.update(
                coverage.get(
                    (campaign_kind, pipeline_id),
                    _empty_failure_coverage(campaign_kind),
                )
            )
            row["conditional_metric_population"] = CONDITIONAL_METRIC_POPULATION
            row["end_to_end_coverage_population"] = END_TO_END_COVERAGE_POPULATION
            output[category].append(row)
    for category, rows in tables.items():
        if category not in output:
            output[category] = [dict(row) for row in rows]
    return output


def _pipeline_failure_coverage(
    failures: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in failures:
        campaign_kind = str(row.get("campaign_kind") or "")
        pipeline_id = str(row.get("pipeline_id") or "")
        if campaign_kind and pipeline_id:
            grouped[(campaign_kind, pipeline_id)].append(row)
    output: dict[tuple[str, str], dict[str, object]] = {}
    for key, rows in grouped.items():
        campaign_kind, _ = key
        planned_jobs = len(rows)
        failed_jobs = sum(str(row.get("state")) == "failed" for row in rows)
        complete_jobs = sum(str(row.get("state")) == "complete" for row in rows)
        planned_cases = sum(max(0, int(row.get("case_count") or 0)) for row in rows)
        completed_cases = sum(
            max(0, int(row.get("completed_cases") or 0)) for row in rows
        )
        completed_cases = min(planned_cases, completed_cases)
        planned_audio = sum(
            max(0.0, float(row.get("planned_audio_sec") or 0.0)) for row in rows
        )
        completed_audio = sum(
            max(0.0, float(row.get("completed_audio_sec") or 0.0)) for row in rows
        )
        completed_audio = min(planned_audio, completed_audio)
        output[key] = {
            "coverage_campaign_kind": campaign_kind,
            "end_to_end_planned_job_count": planned_jobs,
            "conditional_complete_job_count": complete_jobs,
            "explicit_failed_job_count": failed_jobs,
            "end_to_end_job_failure_numerator": failed_jobs,
            "end_to_end_job_failure_denominator": planned_jobs,
            "end_to_end_job_failure_rate": (
                failed_jobs / planned_jobs if planned_jobs else None
            ),
            "end_to_end_planned_case_count": planned_cases,
            "conditional_completed_case_count": completed_cases,
            "end_to_end_case_noncompletion_numerator": max(
                0, planned_cases - completed_cases
            ),
            "end_to_end_case_noncompletion_denominator": planned_cases,
            "end_to_end_case_noncompletion_rate": (
                (planned_cases - completed_cases) / planned_cases
                if planned_cases
                else None
            ),
            "end_to_end_planned_audio_sec": planned_audio,
            "conditional_completed_audio_sec": completed_audio,
            "end_to_end_audio_noncompletion_sec": max(
                0.0, planned_audio - completed_audio
            ),
            "pipeline_has_explicit_failure": failed_jobs > 0,
        }
    return output


def _empty_failure_coverage(campaign_kind: str) -> dict[str, object]:
    return {
        "coverage_campaign_kind": campaign_kind,
        "end_to_end_planned_job_count": 0,
        "conditional_complete_job_count": 0,
        "explicit_failed_job_count": 0,
        "end_to_end_job_failure_numerator": 0,
        "end_to_end_job_failure_denominator": 0,
        "end_to_end_job_failure_rate": None,
        "end_to_end_planned_case_count": 0,
        "conditional_completed_case_count": 0,
        "end_to_end_case_noncompletion_numerator": 0,
        "end_to_end_case_noncompletion_denominator": 0,
        "end_to_end_case_noncompletion_rate": None,
        "end_to_end_planned_audio_sec": 0.0,
        "conditional_completed_audio_sec": 0.0,
        "end_to_end_audio_noncompletion_sec": 0.0,
        "pipeline_has_explicit_failure": False,
    }


def _failure_inventory(root: Path, *, campaign_kind: str) -> list[dict[str, object]]:
    manifest = read_json(root / "campaign_manifest.json")
    paths = read_json(root / "campaign_paths.json")
    results_root = Path(str(paths["results_root"])).resolve()
    store = EvaluationStateStore(root / "campaign.sqlite3")
    attempts_by_job: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for attempt in store.attempt_rows():
        attempts_by_job[str(attempt["job_id"])].append(attempt)
    rows: list[dict[str, object]] = []
    for state in store.list_jobs():
        result_root = results_root / state.spec.result_relative_path
        attempts = attempts_by_job.get(state.spec.job_id, [])
        rows.append(
            {
                **scope_fields(),
                "campaign_kind": campaign_kind,
                "campaign_id": manifest["campaign_id"],
                "job_id": state.spec.job_id,
                "pipeline_id": state.spec.pipeline_id,
                "source_key": state.spec.source_key,
                "measurement_mode": state.spec.measurement_mode,
                "state": state.state,
                "case_count": state.spec.case_count,
                "completed_cases": state.completed_cases,
                "planned_audio_sec": state.spec.audio_duration_sec,
                "completed_audio_sec": state.completed_audio_sec,
                "attempt_count": len(attempts),
                "last_error": state.last_error,
                "explicit_failure": state.state == "failed",
                "missing_result": state.state == "complete"
                and not result_root.is_dir(),
                "result_root": str(result_root),
                "result_checksum_sha256": state.result_sha256,
            }
        )
    return rows


def _finalist_summary(
    tables: Mapping[str, Sequence[Mapping[str, object]]],
    failures: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    lookup = {
        (category, str(row["pipeline_id"])): row
        for category, rows in tables.items()
        for row in rows
    }
    failure_counts: dict[str, int] = defaultdict(int)
    for row in failures:
        failure_counts[str(row["pipeline_id"])] += int(bool(row["explicit_failure"]))
    key_metrics = {
        "asr": ("wer", "cer"),
        "diarization": ("der", "jer"),
        "identity": (
            "correctly_named_known_rate",
            "wrong_known_time_sec",
            "stranger_false_known_time_sec",
            "fpir",
            "fnir",
        ),
        "speaker_transcription": (
            "cpwer",
            "speaker_attributed_wer",
            "correct_transcribed_attributed_word_rate",
        ),
        "streaming": (
            "first_readable_partial_latency_sec",
            "stable_prefix_latency_sec",
        ),
        "resources": ("total_rtf", "peak_rss_bytes", "failure_count"),
    }
    output: list[dict[str, object]] = []
    for pipeline in matrix().pipeline_ids:
        accuracy_coverage = lookup.get(("asr", pipeline), {})
        resource_coverage = lookup.get(("resources", pipeline), {})
        row: dict[str, object] = {
            **scope_fields(),
            "pipeline_id": pipeline,
            "explicit_failed_job_count": failure_counts[pipeline],
            "conditional_metric_population": CONDITIONAL_METRIC_POPULATION,
            "end_to_end_coverage_population": END_TO_END_COVERAGE_POPULATION,
            "ranking_or_winner_selected": False,
        }
        for prefix, source in (
            ("accuracy", accuracy_coverage),
            ("resources", resource_coverage),
        ):
            for key in (
                "end_to_end_planned_job_count",
                "conditional_complete_job_count",
                "explicit_failed_job_count",
                "end_to_end_job_failure_numerator",
                "end_to_end_job_failure_denominator",
                "end_to_end_job_failure_rate",
                "end_to_end_planned_case_count",
                "conditional_completed_case_count",
                "end_to_end_case_noncompletion_numerator",
                "end_to_end_case_noncompletion_denominator",
                "end_to_end_case_noncompletion_rate",
            ):
                row[f"{prefix}_{key}"] = source.get(key)
        for category, metrics in key_metrics.items():
            source = lookup.get((category, pipeline), {})
            for metric in metrics:
                row[metric] = source.get(metric)
                row[f"{metric}__status"] = source.get(f"{metric}__status", "missing")
        output.append(row)
    return output


def _evaluation_report(
    paths,
    *,
    summary_rows: Sequence[Mapping[str, object]],
    failure_rows: Sequence[Mapping[str, object]],
    extraction: Mapping[str, object],
    bootstrap_rows: Sequence[Mapping[str, object]],
) -> str:
    selection = read_json(paths.root / "selection/selection_manifest.json")
    failures = sum(bool(row.get("explicit_failure")) for row in failure_rows)
    return f"""# Prompt 5 — Bounded Untouched Held-Out Core Evaluation

## Evidence boundary

- Scope: `{selection["scope_id"]}` / `{selection["scope_class"]}`
- Original full scope complete: **false**
- Frozen all-18 pipelines: **18**
- Selected held-out cases: **{selection["selected_case_count"]}** of **{selection["original_requested_case_count"]}**
- Selected-case SHA-256: `{selection["selected_case_sha256"]}`
- Native AMI/CHiME: deferred to bounded Prompt 6
- Held-out retuning: **none**
- Weighted composite or production winner: **not created**

The panel was selected deterministically from metadata and references before any
corresponding prediction was inspected. Every pipeline received the identical
case inventory. The original requested full held-out breadth remains unrun.

## Scientific methods

Accuracy jobs used no more than two concurrent jobs. The standardized resource
panel ran one pipeline at a time with an isolated attempt-local cache. Conditional
component metrics remain separate from end-to-end speaker-attributed metrics.
Unsupported, undefined, failed, and missing evidence is retained explicitly.

Speaker confidence intervals use {len(bootstrap_rows)} metric/pipeline/scope rows
and 2,000 deterministic speaker-cluster resamples. All probes for a reference
speaker share one resampling weight. Multi-speaker mixtures contribute
fractionally to each participating speaker, preventing one mixture from being
counted in full once per speaker. Paired pipeline intervals reuse identical
speaker draws.

## Coverage and failures

- Logical pipeline summary rows: {len(summary_rows)}
- Case-metric sufficient-statistic rows: {extraction["statistic_row_count"]}
- Explicit failed jobs: {failures}
- Source counts: `{json.dumps(selection["source_case_counts"], sort_keys=True)}`

Every category table has exactly one row per pipeline. Scientific metric values
are explicitly conditional on checksum-complete job outputs. Separate
`end_to_end_*` coverage, job-failure, and case-noncompletion numerators and
denominators include every planned terminal job, so failures remain visible
without inventing WER/DER/identity values for absent output. See
`all18_failures.csv` for the complete terminal-job inventory. This report ranks
nothing; selection belongs to later prompts under the frozen predeclared rules.
"""
