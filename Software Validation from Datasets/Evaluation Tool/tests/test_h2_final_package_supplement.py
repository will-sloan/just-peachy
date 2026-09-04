from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest

import scripts.augment_h2_final_package as final_package_module

from app.diarization_evaluation.formats import parse_rttm
from app.diarization_product_v2.analysis import _case_product_metrics
from app.h2_product_program.io import canonical_sha256
from app.full_pipeline.paragraphs import build_paragraphs
from app.h2_product_program.reporting import (
    ARM64_PACKAGE_FILES,
    REQUIRED_ANALYSIS_FILES,
    validate_package_zip,
)
from scripts.augment_h2_final_package import (
    ARM64_REQUIREMENTS_MEMBER,
    ARM64_V2_PROVENANCE_MEMBER,
    BOUNDARY_CONFIGURATIONS,
    LONG_SESSION_DRIFT_METRICS,
    PLOT_SOURCES,
    HOST_IO_CANDIDATE_JOB_IDS,
    HOST_IO_COLLECTOR_MEMBER,
    HOST_IO_PROVENANCE_MEMBER,
    HOST_IO_RECEIPT_MEMBER,
    HOST_IO_SELECTED_CONFIGURATIONS,
    PHASE2_ORIGINAL_CONTAMINATED_RECEIPT_MEMBER,
    PHASE2_QUIET_REPLAY_COMPARISON_MEMBER,
    PHASE2_QUIET_REPLAY_MANIFEST_MEMBER,
    REQUIRED_PHASE2_QUIET_REPLAY_MEMBERS,
    SERIAL_HOST_IO_GROUPS,
    SERIAL_HOST_IO_RECEIPT_MEMBERS,
    REQUIRED_ASR_COMPARABILITY_MEMBERS,
    REQUIRED_ARM64_V2_MEMBERS,
    REQUIRED_BOUNDARY_MEMBERS,
    REQUIRED_DATA_FIREWALL_MEMBERS,
    REQUIRED_DEVELOPMENT_CPU_INTERFERENCE_MEMBERS,
    REQUIRED_HARDWARE_PLATFORM_MEMBERS,
    REQUIRED_METRIC_MEMBERS,
    REQUIRED_LONG_SESSION_DRIFT_MEMBERS,
    REQUIRED_HOST_IO_MEMBERS,
    REQUIRED_SERIAL_HOST_IO_MEMBERS,
    REQUIRED_OVERLAP_MEMBERS,
    REQUIRED_RECOMMENDATION_MEMBERS,
    REQUIRED_SCIENCE_TABLE_MEMBERS,
    REQUIRED_SELECTOR_CORRECTION_MEMBERS,
    REQUIRED_STORAGE_MEMBERS,
    REQUIRED_STREAMING_PROVENANCE_MEMBERS,
    STREAMING_FRESH_RESOURCE_CONFIGURATIONS,
    REQUIRED_TRANSCRIPT_MEMBERS,
    REQUIRED_UI_LATENCY_MEMBERS,
    RUNTIME_IDENTITY_MEMBER,
    augment_package,
    build_arm64_deployment_v2,
    build_asr_wer_comparability_supplement,
    build_boundary_correction_supplement,
    build_hardware_platform_assessment,
    build_overlap_stratified_supplement,
    build_plots,
    build_streaming_execution_provenance,
    _development_cpu_interference_payloads,
    _host_io_payloads,
    _serial_host_io_payloads,
    _focused_case_events,
    _paragraph_groups,
    _paragraph_structure_revised,
    _selector_correction_expected_binding,
    _selector_correction_provenance_document,
    _validate_selector_correction_members,
    _validate_storage_reproducibility_members,
    _validate_data_firewall_members,
    _validate_development_cpu_interference_members,
    _validate_ui_latency_members,
    _validate_host_io_members,
    _validate_serial_host_io_members,
    _validate_streaming_execution_provenance_members,
    validate_augmented_package,
)
from scripts.measure_h2_ui_event_latency import build_receipt


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _csv_payload(rows: list[dict[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=("configuration_id", "metric_id", "metric_status", "value"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _csv_table(rows: list[dict[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = tuple(sorted({str(key) for row in rows for key in row}))
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _plot_tables() -> dict[str, bytes]:
    modes: list[dict[str, object]] = []
    resources: list[dict[str, object]] = []
    segmentation: list[dict[str, object]] = []
    for index, configuration in enumerate(
        ("H2_KNOWN_ONLY", "H2_SESSION_ANONYMOUS", "H2_SESSION_MEMORY_ENHANCED"),
        start=1,
    ):
        modes.extend(
            (
                {
                    "configuration_id": configuration,
                    "metric_id": "wrong_known_time_sec",
                    "metric_status": "computed",
                    "value": index * 2.0,
                },
                {
                    "configuration_id": configuration,
                    "metric_id": "stranger_false_known_time_sec",
                    "metric_status": "computed",
                    "value": index * 1.5,
                },
                {
                    "configuration_id": configuration,
                    "metric_id": "stable_name_latency_sec",
                    "metric_status": "computed",
                    "value": index * 0.4,
                },
            )
        )
        resources.extend(
            (
                {
                    "configuration_id": configuration,
                    "metric_id": "peak_rss_bytes",
                    "metric_status": "computed",
                    "value": index * 100 * 1024 * 1024,
                },
                {
                    "configuration_id": configuration,
                    "metric_id": "total_rtf",
                    "metric_status": "computed",
                    "value": index * 0.2,
                },
                {
                    "configuration_id": configuration,
                    "metric_id": "model_bytes",
                    "metric_status": "computed",
                    "value": index * 200 * 1024 * 1024,
                },
                {
                    "configuration_id": configuration,
                    "metric_id": "cache_bytes",
                    "metric_status": "computed",
                    "value": index * 50 * 1024 * 1024,
                },
            )
        )
    for index, configuration in enumerate(("S1_FULL", "S2_FULL", "S7_FULL"), start=1):
        segmentation.extend(
            (
                {
                    "configuration_id": configuration,
                    "metric_id": "miss_rate",
                    "metric_status": "computed",
                    "value": 0.25 + index * 0.01,
                },
                {
                    "configuration_id": configuration,
                    "metric_id": "boundary_delay_sec",
                    "metric_status": "computed",
                    "value": 2.0 + index * 0.1,
                },
            )
        )
    return {
        PLOT_SOURCES[0]: _csv_payload(modes),
        PLOT_SOURCES[1]: _csv_payload(resources),
        PLOT_SOURCES[2]: _csv_payload(segmentation),
    }


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _long_session_table() -> bytes:
    rows: list[dict[str, object]] = []
    for split, source_count in (("development", 4), ("evaluation", 8)):
        for source_index in range(1, source_count + 1):
            source_id = f"{split}_source_{source_index:02d}"
            for duration_min in (30, 60):
                stream_id = f"{source_id}_{duration_min:02d}m"
                source_record = _json_bytes(
                    {
                        "stream_id": stream_id,
                        "source": {"source_recording_id": source_id},
                    }
                ).decode("utf-8")
                for metric_index, (
                    _metric_id,
                    source_metric_id,
                    _normalization,
                    _unit,
                ) in enumerate(LONG_SESSION_DRIFT_METRICS, start=1):
                    rows.append(
                        {
                            "split": split,
                            "configuration_id": stream_id,
                            "metric_id": source_metric_id,
                            "metric_status": "computed",
                            "value": (
                                metric_index * 10.0 + source_index + duration_min / 60.0
                            ),
                            "source_record_json": source_record,
                        }
                    )
                rows.extend(
                    (
                        {
                            "split": split,
                            "configuration_id": stream_id,
                            "metric_id": "sample_count",
                            "metric_status": "computed",
                            "value": 1,
                            "source_record_json": source_record,
                        },
                        {
                            "split": split,
                            "configuration_id": stream_id,
                            "metric_id": "sample_count",
                            "metric_status": "computed",
                            "value": 2,
                            "source_record_json": source_record,
                        },
                    )
                )
    return _csv_table(rows)


def _signed_fixture_document(
    value: dict[str, object], *, signature_key: str
) -> dict[str, object]:
    signed = dict(value)
    signed[signature_key] = _sha(_json_bytes(value).rstrip(b"\n"))
    return signed


def _firewall_receipt_fixture(
    *,
    runtime_identity_sha256: str,
    runtime_identity_file_sha256: str,
    protocol_id: str,
    protocol_manifest_sha256: str,
) -> dict[str, object]:
    source_names = (
        "protocol_summary.json",
        "development/enrollment/enrollment_registry.jsonl",
        "evaluation/enrollment/enrollment_registry.jsonl",
        "development/case_manifest.jsonl",
        "evaluation/case_manifest.jsonl",
    )
    partition = {
        "registry_rows": 1,
        "reserved_enrollment_clips": 1,
        "case_manifest_rows": 1,
        "global_speaker_count": 1,
        "enrolled_id_count": 1,
        "speaker_set_sha256": "1" * 64,
        "enrolled_id_set_sha256": "2" * 64,
        "gallery_exactly_matches_registry": True,
        "case_speakers_exactly_match_registry": True,
    }
    return _signed_fixture_document(
        {
            "schema_version": "h2-enrollment-firewall-audit.v1",
            "status": "VALID",
            "audit_id": "H2_PREOPEN_ENROLLMENT_AND_SOURCE_FIREWALL_V1",
            "created_at_utc": "2026-08-01T00:00:00.000000Z",
            "protocol_binding": {
                "h2_protocol_id": protocol_id,
                "h2_protocol_manifest_sha256": protocol_manifest_sha256,
                "h2_job_manifest_sha256": "3" * 64,
                "prepared_protocol_id": "full_speech_pipeline_fixture",
                "prepared_protocol_summary_sha256": "4" * 64,
                "development_partition_id": "development_fixture",
                "evaluation_partition_id": "evaluation_fixture",
            },
            "runtime_binding": {
                "frozen_runtime_identity_sha256": runtime_identity_sha256,
                "frozen_runtime_identity_file_sha256": (runtime_identity_file_sha256),
            },
            "partitions": {
                "development": dict(partition),
                "evaluation": {
                    **partition,
                    "speaker_set_sha256": "5" * 64,
                    "enrolled_id_set_sha256": "6" * 64,
                },
            },
            "cross_partition_overlap_counts": {
                "enrollment_registry": {
                    "enrolled_id": 0,
                    "global_speaker_id": 0,
                    "source_clip_id": 0,
                    "source_audio_sha256": 0,
                    "logical_audio_path": 0,
                },
                "case_manifest": {
                    "protocol_case_id": 0,
                    "audio_sha256": 0,
                    "pcm_sha256": 0,
                    "source_reference_id": 0,
                    "source_case_id": 0,
                    "global_speaker_ids": 0,
                    "gallery_enrolled_ids": 0,
                },
            },
            "heldout_preopen": {
                "evaluation_job_count": 1,
                "evaluation_jobs_materialized_in_queue": 0,
                "evaluation_jobs_not_yet_materialized": 1,
                "evaluation_job_ids_sha256": "7" * 64,
                "all_evaluation_jobs_pending": True,
                "evaluation_attempt_count": 0,
                "evaluation_attempt_directories_present": 0,
                "evaluation_result_directories_present": 0,
                "heldout_execution_manifest_present": False,
                "freeze_receipt_present": False,
                "evaluation_predictions_or_metrics_inspected": False,
            },
            "source_file_inventory": [
                {"logical_path": name, "sha256": "8" * 64, "bytes": 100}
                for name in source_names
            ],
            "evidence_boundaries": {
                "metadata_only": True,
                "audio_opened_or_copied": False,
                "embeddings_or_biometric_templates_opened_or_copied": False,
                "evaluation_predictions_or_metrics_opened": False,
                "evaluation_reference_content_used_for_selection": False,
                "scientific_runtime_or_policy_changed": False,
                "used_for_scientific_selection": False,
                "large_case_manifests_embedded_in_compact_receipt": False,
                "exact_source_files_bound_by_sha256": True,
            },
        },
        signature_key="receipt_sha256",
    )


def _development_cpu_interference_receipt_fixture(
    *,
    protocol_id: str,
    protocol_sha256: str,
    job_manifest_identity_sha256: str,
    job_manifest_file_sha256: str,
    runtime_identity_sha256: str,
    runtime_identity_file_sha256: str,
    job: dict[str, object],
) -> dict[str, object]:
    case_ids = job["case_ids"]
    assert isinstance(case_ids, list)
    return _signed_fixture_document(
        {
            "schema_version": "h2-development-host-cpu-interference.v1",
            "status": "HOST_CPU_INTERFERENCE_DISCLOSED_TIMING_INELIGIBLE",
            "captured_at_utc": "2026-08-31T04:40:57.0595209Z",
            "protocol_id": protocol_id,
            "protocol_sha256": protocol_sha256,
            "job_manifest_identity_sha256": job_manifest_identity_sha256,
            "job_manifest_file_sha256_at_capture": job_manifest_file_sha256,
            "runtime_implementation_identity_sha256": runtime_identity_sha256,
            "runtime_implementation_identity_file_sha256_at_capture": (
                runtime_identity_file_sha256
            ),
            "affected_job": {
                "job_id": job["job_id"],
                "job_identity_sha256": job["identity_sha256"],
                "phase_index": job["phase_index"],
                "phase_name": job["phase_name"],
                "job_kind": job["job_kind"],
                "configuration_id": job["configuration_id"],
                "split": job["split"],
                "serial": job["serial"],
                "started_at_utc": "2026-08-31T02:41:04.690492Z",
                "planned_case_count": len(case_ids),
                "planned_audio_sec": job["audio_duration_sec"],
            },
            "interference": {
                "kind": "UNINTENDED_DIAGNOSTIC_PROCESS_CPU_LOAD",
                "detected_at_utc": "2026-08-31T04:39:51.2027354Z",
                "termination_verified_before_utc": "2026-08-31T04:40:57.0595209Z",
                "processes": [
                    {
                        "process_id": 42456,
                        "cpu_time_sec_at_stop": 10.0,
                        "campaign_process": False,
                    },
                    {
                        "process_id": 34852,
                        "cpu_time_sec_at_stop": 20.0,
                        "campaign_process": False,
                    },
                ],
                "controller_or_model_worker_stopped": False,
                "scientific_configuration_changed": False,
                "results_deleted_or_restarted": False,
            },
            "capture_snapshot": {
                "controller_alive_after_cleanup": True,
            },
            "scientific_interpretation": {
                "timing_and_resource_fields_eligible_as_clean_evidence": False,
                "development_selection_affected": False,
                "heldout_evaluation_opened": False,
                "retuning_permitted_or_performed": False,
            },
            "remediation": {
                "active_job_interrupted": False,
                "completed_work_preserved": True,
                "clean_resource_evidence_required": True,
            },
        },
        signature_key="receipt_sha256",
    )


def _arm64_wheel_receipt_fixture(
    *, requirements_payload: bytes, runtime_identity_sha256: str, protocol_id: str
) -> dict[str, object]:
    direct_count = len(
        [
            line
            for line in requirements_payload.decode("utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    )
    wheels = [
        {
            "filename": f"fixture_{index:02d}-1.0-py3-none-any.whl",
            "sha256": f"{index:064x}",
            "bytes": 100 + index,
        }
        for index in range(1, direct_count + 1)
    ]
    return _signed_fixture_document(
        {
            "schema_version": "h2-arm64-wheel-resolution-receipt.v1",
            "status": "PASS_RESOLVED_EXACT_ARM64_BINARY_SET",
            "protocol_id": protocol_id,
            "runtime_implementation_sha256": runtime_identity_sha256,
            "scientific_runtime_or_configuration_edited": False,
            "source": {
                "requirements_path": (
                    "deployment/h2_arm64/requirements-linux-arm64.txt"
                ),
                "requirements_sha256": _sha(requirements_payload),
                "index_url": "https://pypi.org/simple",
            },
            "target": {
                "operating_system": "Linux",
                "architecture": "aarch64",
                "python_version": "3.12",
                "implementation": "cp",
                "abis": ["cp312", "abi3", "none"],
                "platform_tags": [
                    "manylinux_2_28_aarch64",
                    "manylinux2014_aarch64",
                    "manylinux_2_17_aarch64",
                    "any",
                ],
                "binary_only": True,
            },
            "resolution": {
                "direct_pin_count": direct_count,
                "resolved_wheel_count": len(wheels),
                "resolved_logical_bytes": sum(int(row["bytes"]) for row in wheels),
                "all_direct_and_transitive_dependencies_resolved": True,
                "source_distributions_used": False,
                "model_assets_downloaded": False,
                "wheels_retained_after_audit": False,
            },
            "wheels": wheels,
            "qualification_boundary": {
                "wheel_availability_and_target_tag_resolution": "PASS",
                "arm64_import_and_dynamic_link_validation": (
                    "NOT_RUN_REQUIRES_ARM64_LINUX"
                ),
                "arm64_numerical_parity": "NOT_RUN_REQUIRES_ARM64_LINUX",
                "raspberry_pi_hardware_ready_claimed": False,
                "candidate_classification": "PORT_REQUIRES_WORK",
            },
        },
        signature_key="receipt_sha256",
    )


def _write_terminal_storage_fixture(
    workspace: Path,
    controller_state: dict[str, object],
    manifest_rows: list[dict[str, object]],
) -> None:
    """Materialize mandatory terminal storage evidence for ZIP tests."""

    terminal = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
    assert controller_state["status"] == terminal
    maintenance = workspace / "storage_maintenance"
    receipts = maintenance / "receipts"
    receipts.mkdir(parents=True)

    dynamic_kinds = {
        "post_promotion_integration",
        "post_selection_mode_validation",
        "post_selection_paragraph_validation",
        "post_selection_resource_runtime",
    }
    for index, row in enumerate(
        (row for row in manifest_rows if row.get("job_kind") in dynamic_kinds),
        start=1,
    ):
        dynamic = _signed_fixture_document(
            {
                "schema_version": "h2-dynamic-development-execution.v1",
                "logical_job_id": row["job_id"],
                "logical_job_identity_sha256": row["identity_sha256"],
                "execution_job": {
                    "identity_sha256": f"dynamic-execution-{index}",
                    "job_id": f"h2dyn_fixture_{index:02d}",
                },
                "split": "development",
                "evaluation_material_inspected": False,
            },
            signature_key="dynamic_execution_sha256",
        )
        dynamic_path = (
            workspace / "dynamic_queues" / str(row["job_id"]) / "dynamic_execution.json"
        )
        dynamic_path.parent.mkdir(parents=True)
        dynamic_path.write_bytes(_json_bytes(dynamic))

    lifecycle = _signed_fixture_document(
        {
            "schema_version": "h2-storage-artifact-lifecycle.v1",
            "campaign_status": terminal,
        },
        signature_key="lifecycle_sha256",
    )
    forecast = {
        "schema_version": "h2-storage-forecast.v1",
        "program_status": terminal,
    }
    guardian = {
        "schema_version": "h2-storage-guardian-pass.v1",
        "artifact_lifecycle_sha256": lifecycle["lifecycle_sha256"],
        "forecast": forecast,
    }
    arm64_root = Path(__file__).resolve().parents[1] / "deployment/h2_arm64"
    requirements_payload = (arm64_root / "requirements-linux-arm64.txt").read_bytes()
    arm64_component_rows = {
        (
            "Software Validation from Datasets/Evaluation Tool/deployment/"
            f"h2_arm64/{name}"
        ): _sha((arm64_root / name).read_bytes())
        for name in ARM64_PACKAGE_FILES
    }
    runtime_identity = {
        "schema_version": "h2-runtime-implementation-identity.v2",
        "identity_sha256": "d" * 64,
        "components": {
            "h2_arm64_deployment_bundle": canonical_sha256(arm64_component_rows),
        },
    }
    protocol_manifest = {
        "schema_version": "h2-product-protocol.v1",
        "protocol_id": controller_state["protocol_id"],
        "protocol_sha256": controller_state["protocol_sha256"],
    }
    protocol_manifest_payload = _json_bytes(protocol_manifest)
    runtime_identity_payload = _json_bytes(runtime_identity)
    firewall_receipt = _firewall_receipt_fixture(
        runtime_identity_sha256=str(runtime_identity["identity_sha256"]),
        runtime_identity_file_sha256=_sha(runtime_identity_payload),
        protocol_id=str(protocol_manifest["protocol_id"]),
        protocol_manifest_sha256=_sha(protocol_manifest_payload),
    )
    job_manifest_payload = _json_bytes(
        {
            "job_manifest_sha256": controller_state["job_manifest_sha256"],
            "protocol_id": controller_state["protocol_id"],
            "protocol_sha256": controller_state["protocol_sha256"],
            "jobs": manifest_rows,
        }
    )
    interference_job = next(
        row for row in manifest_rows if row["job_kind"] == "post_promotion_integration"
    )
    development_cpu_receipt = _development_cpu_interference_receipt_fixture(
        protocol_id=str(protocol_manifest["protocol_id"]),
        protocol_sha256=str(protocol_manifest["protocol_sha256"]),
        job_manifest_identity_sha256=str(controller_state["job_manifest_sha256"]),
        job_manifest_file_sha256=_sha(job_manifest_payload),
        runtime_identity_sha256=str(runtime_identity["identity_sha256"]),
        runtime_identity_file_sha256=_sha(runtime_identity_payload),
        job=interference_job,
    )
    arm64_wheel_receipt = _arm64_wheel_receipt_fixture(
        requirements_payload=requirements_payload,
        runtime_identity_sha256=str(runtime_identity["identity_sha256"]),
        protocol_id=str(controller_state["protocol_id"]),
    )
    tool_root = Path(__file__).resolve().parents[1]
    atomic_launcher = tool_root / "scripts/h2_windows_atomic_retry_bootstrap.py"
    atomic_child = tool_root / "scripts/h2_atomic_retry_child/sitecustomize.py"
    atomic_event_log = workspace / "logs/windows_atomic_publication_events.jsonl"
    atomic_policy = _signed_fixture_document(
        {
            "schema_version": "h2-windows-atomic-publication-policy.v1",
            "platform_scope": "Windows only; other platforms use os.replace unchanged",
            "launcher_source": str(atomic_launcher.resolve()),
            "launcher_sha256": _sha(atomic_launcher.read_bytes()),
            "child_process_propagation": "PYTHONPATH_sitecustomize",
            "child_sitecustomize_source": str(atomic_child.resolve()),
            "child_sitecustomize_sha256": _sha(atomic_child.read_bytes()),
            "retryable_winerrors": [5, 32, 33],
            "retry_delays_sec": [0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 2.0, 2.0],
            "maximum_added_wait_sec": 7.15,
            "operation_scope": "os.replace only",
            "event_log": str(atomic_event_log),
            "scientific_inference_or_metric_change": False,
            "frozen_runtime_source_tree_change": False,
            "purpose": (
                "Recover transient Windows sharing violations while publishing "
                "validation, progress, status, and other atomic JSON artifacts."
            ),
        },
        signature_key="policy_sha256",
    )

    receipt_job = next(
        row for row in manifest_rows if row["job_kind"] == "runtime_accuracy"
    )
    job_id = str(receipt_job["job_id"])
    state_jobs = controller_state["jobs"]
    assert isinstance(state_jobs, dict)
    state_row = state_jobs[job_id]
    assert isinstance(state_row, dict)
    pending = _signed_fixture_document(
        {
            "schema_version": "h2-storage-prune-pending.v1",
            "workspace": str(workspace.resolve()),
            "queue_database_relative_path": "campaign.sqlite3",
            "job": {
                "job_id": job_id,
                "identity_sha256": receipt_job["identity_sha256"],
            },
            "queue_completion": {"result_sha256": state_row["result_sha256"]},
            "regenerable_source": {"logical_bytes": 4096},
            "retained_sealed_result": {
                "absolute_path": state_row["result_path"],
                "checksums_sha256": state_row["result_sha256"],
            },
        },
        signature_key="pending_sha256",
    )
    receipt = _signed_fixture_document(
        {
            "schema_version": "h2-storage-prune-receipt.v1",
            "status": "PRUNED_REGENERABLE_CASE_SHARDS",
            "validation_receipt": pending,
        },
        signature_key="receipt_sha256",
    )
    for path, value in (
        (workspace / "runtime_implementation_identity.json", runtime_identity),
        (workspace / "protocol_manifest.json", protocol_manifest),
        (maintenance / "artifact_lifecycle.json", lifecycle),
        (maintenance / "storage_forecast.json", forecast),
        (maintenance / "last_guardian_pass.json", guardian),
        (
            maintenance / "arm64_wheel_resolution_receipt.json",
            arm64_wheel_receipt,
        ),
        (maintenance / "windows_atomic_publication_policy.json", atomic_policy),
        (receipts / f"{job_id}.json", receipt),
        (
            workspace / "engineering_validation/enrollment_firewall_audit_receipt.json",
            firewall_receipt,
        ),
        (
            workspace
            / "engineering_validation/development_host_cpu_interference_receipt.json",
            development_cpu_receipt,
        ),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_json_bytes(value))
    ui_samples = []
    for index, latency_ms in enumerate((125.0, 175.0), start=1):
        emitted = 1_000_000_000 + index * 1_000_000_000
        rendered = emitted + int(latency_ms * 1_000_000)
        ui_samples.append(
            {
                "sample_index": index,
                "event_sequence": index,
                "injection_phase_offset_ms": (index - 1) * 25,
                "emitted_monotonic_ns": emitted,
                "render_completed_monotonic_ns": rendered,
                "latency_ms": latency_ms,
                "last_event_widget_value": f"#{index} IdentityLabelEvent",
                "last_event_widget_verified": True,
                "roster_widget_verified": True,
            }
        )
    ui_receipt = build_receipt(
        samples=ui_samples,
        benchmark_metadata={
            "tk_patchlevel": "fixture",
            "configured_poll_interval_ms": 100,
            "phase_offsets_ms": [0, 25],
            "durable_event_path_exercised": True,
            "coalescing_update_buffer_exercised": True,
            "background_task_runner_exercised": True,
            "tk_widget_render_verified": True,
        },
        runtime_identity=runtime_identity,
        runtime_identity_file_sha256=_sha(_json_bytes(runtime_identity)),
        warmup_count=1,
        timeout_sec=3.0,
    )
    ui_receipt_path = workspace / "engineering_validation/ui_event_latency_receipt.json"
    ui_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    ui_receipt_path.write_bytes(_json_bytes(ui_receipt))
    atomic_event_log.parent.mkdir(parents=True, exist_ok=True)
    atomic_event_log.write_bytes(b"")

    database = workspace / "campaign.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE jobs(job_id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE attempts(
                job_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                state TEXT NOT NULL,
                attempt_path TEXT NOT NULL,
                started_at_utc TEXT NOT NULL,
                ended_at_utc TEXT NOT NULL,
                error TEXT,
                PRIMARY KEY(job_id, attempt_number)
            );
            """
        )
        attempt_root = workspace / "attempts" / job_id
        connection.executemany(
            "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    job_id,
                    1,
                    "failed",
                    str(attempt_root / "attempt_001"),
                    "2026-08-01T00:00:00Z",
                    "2026-08-01T00:01:00Z",
                    "transient worker startup timeout",
                ),
                (
                    job_id,
                    2,
                    "failed",
                    str(attempt_root / "attempt_002"),
                    "2026-08-01T00:02:00Z",
                    "2026-08-01T00:03:00Z",
                    "transient Windows status publication lock",
                ),
                (
                    job_id,
                    3,
                    "complete",
                    str(attempt_root / "attempt_003"),
                    "2026-08-01T00:04:00Z",
                    "2026-08-01T00:05:00Z",
                    None,
                ),
            ),
        )
        connection.execute("INSERT INTO jobs VALUES (?, ?)", (job_id, "complete"))


def _write_metric_result(
    root: Path,
    workspace: Path,
    *,
    job_id: str,
    split: str,
    paragraph_policy: str = "T3_PAUSE_ASR_SPEAKER_CHANGE",
    boundary_correction_ms: int = 0,
    span_anonymous_ids: tuple[str, str] = ("anon_0", "anon_1"),
    event_initial_first_anonymous_id: str | None = None,
    fixture_source_key: str | None = None,
) -> tuple[Path, str]:
    result = root / "results" / "jobs" / job_id / "result"
    (result / "references").mkdir(parents=True)
    (result / "predictions").mkdir(parents=True)
    (result / "diagnostics").mkdir(parents=True)
    reference_root = workspace / "references"
    reference_root.mkdir(parents=True, exist_ok=True)
    source_key = fixture_source_key or job_id
    reference = reference_root / f"{source_key}.rttm"
    reference_payload = (
        f"SPEAKER source_{source_key} 1 0.000000 1.000000 <NA> <NA> SPK00 <NA> <NA>\n"
        f"SPEAKER source_{source_key} 1 1.000000 2.000000 <NA> <NA> SPK01 <NA> <NA>\n"
    ).encode()
    reference.write_bytes(reference_payload)
    case_id = f"case_{source_key}"
    case = {
        "protocol_case_id": case_id,
        "source_case_id": f"source_{source_key}",
        "partition": split,
        "duration_sec": 3.0,
        "audio_namespace": "workspace",
        "reference_rttm_namespace": "workspace",
        "reference_rttm_logical_path": f"references/{reference.name}",
        "reference_rttm_sha256": _sha(reference_payload),
        "local_to_global_speaker": {
            "SPK00": f"{split}_speaker_0",
            "SPK01": f"{split}_speaker_1",
        },
        "global_speaker_ids": [f"{split}_speaker_0", f"{split}_speaker_1"],
        "overlap_ratio": 0.0,
        "scenario": {"speaker_count": 2},
    }
    cases_payload = _json_bytes(case)
    prediction_payload = (
        f"SPEAKER {case_id} 1 0.000000 1.000000 <NA> <NA> anon_0 <NA> <NA>\n"
        f"SPEAKER {case_id} 1 1.000000 2.000000 <NA> <NA> anon_1 <NA> <NA>\n"
    ).encode()
    (result / "references" / "cases.jsonl").write_bytes(cases_payload)
    (result / "predictions" / "diarization.rttm").write_bytes(prediction_payload)
    labelled_rows = (
        {
            "anonymous_speaker_id": span_anonymous_ids[0],
            "case_id": case_id,
            "end_sec": 1.0,
            "span_id": "span_0",
            "speaker_label": "Speaker_1",
            "start_sec": 0.0,
            "state": "final",
            "text": "hello.",
        },
        {
            "anonymous_speaker_id": span_anonymous_ids[1],
            "case_id": case_id,
            "end_sec": 2.0,
            "span_id": "span_1",
            "speaker_label": "Speaker_2",
            "start_sec": 1.0,
            "state": "final",
            "text": "world.",
        },
    )
    labelled_payload = b"".join(_json_bytes(row) for row in labelled_rows)
    (result / "predictions" / "labelled_transcript.jsonl").write_bytes(labelled_payload)
    reference_transcript_payload = _json_bytes(
        {
            "source_case_id": f"source_{source_key}",
            "speaker_attributed_transcript_status": "supported",
            "segments": [
                {
                    "end_sec": 1.0,
                    "global_speaker_id": f"{split}_speaker_0",
                    "reference_segment_id": "ref_0",
                    "scorable_transcript": "hello.",
                    "speaker_attributed_transcript_status": "supported",
                    "start_sec": 0.0,
                },
                {
                    "end_sec": 2.0,
                    "global_speaker_id": f"{split}_speaker_1",
                    "reference_segment_id": "ref_1",
                    "scorable_transcript": "world.",
                    "speaker_attributed_transcript_status": "supported",
                    "start_sec": 1.0,
                },
            ],
        }
    )
    (
        result / "references" / "selected_speaker_attributed_transcripts.jsonl"
    ).write_bytes(reference_transcript_payload)
    overlay_payload = b""
    (result / "references" / "selected_identity_overlays.jsonl").write_bytes(
        overlay_payload
    )
    initial_first = dict(labelled_rows[0])
    initial_first["anonymous_speaker_id"] = (
        event_initial_first_anonymous_id or span_anonymous_ids[0]
    )
    event_payload = b"".join(
        (
            _json_bytes(
                {
                    "capture_timestamps": {"audio_end_sec": 1.0},
                    "evaluation_case_id": case_id,
                    "event_sequence": 1,
                    "event_type": "transcript_revision",
                    "processing_timestamps": {"emitted_monotonic_ns": 1_000_000_000},
                    "spans": [initial_first],
                }
            ),
            _json_bytes(
                {
                    "capture_timestamps": {"audio_end_sec": 2.0},
                    "evaluation_case_id": case_id,
                    "event_sequence": 2,
                    "event_type": "transcript_revision",
                    "processing_timestamps": {"emitted_monotonic_ns": 2_000_000_000},
                    "spans": list(labelled_rows),
                }
            ),
        )
    )
    event_gzip = gzip.compress(event_payload, mtime=0)
    (result / "events.jsonl.gz").write_bytes(event_gzip)
    correct_words = int(span_anonymous_ids[0] == "anon_0") + int(
        span_anonymous_ids[1] == "anon_1"
    )

    def ratio_metric(
        metric_id: str, numerator: float, denominator: float
    ) -> dict[str, object]:
        return {
            "definition": f"fixture {metric_id}",
            "denominator": denominator,
            "details": {"aggregation": "per_recording_sufficient_statistics.v1"},
            "metric_id": metric_id,
            "numerator": numerator,
            "reason": None,
            "status": "computed",
            "unit": "ratio",
            "value": numerator / denominator,
        }

    def sum_metric(metric_id: str, value: float) -> dict[str, object]:
        return {
            "definition": f"fixture {metric_id}",
            "denominator": None,
            "details": {
                "aggregation": "per_recording_sufficient_statistics.v1",
                "scalar_aggregation": "sum",
            },
            "metric_id": metric_id,
            "numerator": None,
            "reason": None,
            "status": "computed",
            "unit": "seconds" if "dwell" in metric_id else "events",
            "value": value,
        }

    correction_event_count = float(
        event_initial_first_anonymous_id is not None
        and event_initial_first_anonymous_id != span_anonymous_ids[0]
    )
    boundary_value = 0.1 + boundary_correction_ms / 1000.0
    per_case_payload = _json_bytes(
        {
            "audio_duration_sec": 3.0,
            "case_id": case_id,
            "reference_speaker_ids": [
                f"{split}_speaker_0",
                f"{split}_speaker_1",
            ],
            "reports": {
                "diarization": {
                    "metrics": {
                        "boundary_delay_sec": {
                            **ratio_metric("boundary_delay_sec", boundary_value, 1.0),
                            "unit": "seconds",
                        }
                    }
                },
                "speaker_transcription": {
                    "metrics": {
                        "correct_transcribed_attributed_word_rate": ratio_metric(
                            "correct_transcribed_attributed_word_rate",
                            float(correct_words),
                            2.0,
                        ),
                        "retroactive_correction_count": sum_metric(
                            "retroactive_correction_count", correction_event_count
                        ),
                        "word_speaker_label_accuracy": ratio_metric(
                            "word_speaker_label_accuracy", float(correct_words), 2.0
                        ),
                    }
                },
                "ux": {
                    "metrics": {
                        "transcript_revision_count": sum_metric(
                            "transcript_revision_count", 2.0
                        ),
                        "wrong_name_dwell_sec": sum_metric("wrong_name_dwell_sec", 0.0),
                    }
                },
            },
            "schema_version": "fixture-per-case-metrics.v1",
            "source_case_id": f"source_{source_key}",
        }
    )
    (result / "diagnostics" / "per_case_metrics.jsonl").write_bytes(per_case_payload)
    metrics_payload = _json_bytes(
        {
            "subviews": {
                "asr": {
                    "metrics": {
                        "wer": {
                            "definition": "fixture frozen WER",
                            "denominator": 2.0,
                            "details": {"normalization_id": "lowercase_whitespace.v1"},
                            "metric_id": "wer",
                            "numerator": 0.0,
                            "reason": None,
                            "status": "computed",
                            "unit": "ratio",
                            "value": 0.0,
                        }
                    }
                },
                "speaker_transcription": {
                    "metrics": {
                        "word_speaker_label_accuracy": {
                            "definition": "fixture word speaker accuracy",
                            "denominator": 2.0,
                            "numerator": float(correct_words),
                            "reason": None,
                            "status": "computed",
                            "unit": "ratio",
                            "value": correct_words / 2.0,
                        }
                    }
                },
            }
        }
    )
    (result / "metrics").mkdir()
    (result / "metrics" / "asr.json").write_bytes(metrics_payload)
    streaming_metrics_payload = _json_bytes(
        {
            "subviews": {
                "streaming": {
                    "metrics": {
                        "final_wer": {
                            "definition": "fixture endpoint-window WER",
                            "denominator": 3.0,
                            "metric_id": "final_wer",
                            "numerator": 0.0,
                            "reason": None,
                            "status": "computed",
                            "unit": "ratio",
                            "value": 0.0,
                        }
                    }
                }
            }
        }
    )
    (result / "metrics" / "streaming.json").write_bytes(streaming_metrics_payload)
    pipeline_payload = _json_bytes(
        {
            "runtime_tuning": {
                "paragraph_max_words": 80,
                "paragraph_pause_sec": 0.8,
                "paragraph_policy": paragraph_policy,
                "boundary_correction_ms": boundary_correction_ms,
            }
        }
    )
    (result / "pipeline_identity.json").write_bytes(pipeline_payload)
    (result / "run.json").write_bytes(
        _json_bytes(
            {
                "status": "complete",
                "reuse_identity": {"partition": split},
            }
        )
    )
    entries = {
        "references/cases.jsonl": {
            "sha256": _sha(cases_payload),
            "bytes": len(cases_payload),
        },
        "diagnostics/per_case_metrics.jsonl": {
            "sha256": _sha(per_case_payload),
            "bytes": len(per_case_payload),
        },
        "predictions/diarization.rttm": {
            "sha256": _sha(prediction_payload),
            "bytes": len(prediction_payload),
        },
        "events.jsonl.gz": {"sha256": _sha(event_gzip), "bytes": len(event_gzip)},
        "metrics/asr.json": {
            "sha256": _sha(metrics_payload),
            "bytes": len(metrics_payload),
        },
        "metrics/streaming.json": {
            "sha256": _sha(streaming_metrics_payload),
            "bytes": len(streaming_metrics_payload),
        },
        "pipeline_identity.json": {
            "sha256": _sha(pipeline_payload),
            "bytes": len(pipeline_payload),
        },
        "predictions/labelled_transcript.jsonl": {
            "sha256": _sha(labelled_payload),
            "bytes": len(labelled_payload),
        },
        "references/selected_speaker_attributed_transcripts.jsonl": {
            "sha256": _sha(reference_transcript_payload),
            "bytes": len(reference_transcript_payload),
        },
        "references/selected_identity_overlays.jsonl": {
            "sha256": _sha(overlay_payload),
            "bytes": len(overlay_payload),
        },
    }
    checksum_payload = _json_bytes({"entries": entries})
    (result / "checksums.json").write_bytes(checksum_payload)
    return result, _sha(checksum_payload)


def _write_streaming_qualification_result(
    root: Path,
    workspace: Path,
    *,
    job_id: str,
    job_identity_sha256: str,
    protocol_id: str,
    protocol_sha256: str,
) -> tuple[Path, str]:
    result, _prior_sha = _write_metric_result(
        root,
        workspace,
        job_id=job_id,
        split="development",
        fixture_source_key="streaming_qualification",
    )
    case_id = "case_streaming_qualification"
    pipeline_payload = _json_bytes(
        {
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "execution_contract": {
                "schema_version": "h2-product-execution-contract.v1",
                "h2_job_id": job_id,
                "h2_job_identity_sha256": job_identity_sha256,
                "h2_protocol_id": protocol_id,
                "h2_protocol_sha256": protocol_sha256,
                "product_mode": "H2_SESSION_MEMORY_ENHANCED",
            },
            "runtime_tuning": {
                "product_mode": "H2_SESSION_MEMORY_ENHANCED",
                "redim_execution_strategy": "R2_ONE_SHARED_MODEL",
            },
        }
    )
    (result / "pipeline_identity.json").write_bytes(pipeline_payload)
    cache_payload = _json_bytes(
        {
            "schema_version": "full-pipeline-cache-regime.v1",
            "measurement_mode": "accuracy",
            "asr_stream_trace_enabled": True,
            "runtime_cache_scope": "shared_cross_job_accuracy",
            "resource_measurement_serial_required": False,
        }
    )
    (result / "diagnostics" / "cache_regime.json").write_bytes(cache_payload)
    case_status_payload = _json_bytes(
        {
            "case_id": case_id,
            "status": "complete",
            "output_failed": False,
            "queue_backpressure": {
                "policy": "block",
                "maximum_frames": 16,
                "maximum_observed_depth": 4,
                "dropped_frames": 0,
            },
        }
    )
    (result / "diagnostics" / "case_status.jsonl").write_bytes(case_status_payload)

    def component_status(*, terminal: bool) -> dict[str, object]:
        shared = {
            "schema_version": "full-pipeline-native-asr-stream-trace.v2",
            "execution_origin": "accuracy_replayed",
            "worker_started": False,
            "interaction_cursor": 2 if terminal else 0,
            "interaction_count": 2,
            "trace_key_sha256": "1" * 64,
            "trace_sha256": "2" * 64,
            "terminal_completeness": {
                "complete": True,
                "accepted_frame_count": 1,
                "accepted_source_sample_end": 1600,
                "expected_source_sample_start": 0,
                "expected_source_sample_end": 1600,
                "contiguous_from_source_start": True,
                "failure_reason": None,
            },
            "native_processing_latency_preserved": True,
            "recorded_source_audio_horizons_preserved": True,
            "resource_measurement_eligible": False,
        }
        return {
            "evaluation_case_id": case_id,
            "event_type": "component_status",
            "component_statuses": [
                {
                    "component_identity": {
                        "component_family": "asr",
                        "backend_id": "sherpa_onnx_libri_giga_zipformer_2023_06_21",
                    },
                    "state": "completed" if terminal else "running",
                    "reason": {
                        "code": "component_status_snapshot",
                        "detail": json.dumps(
                            {
                                "kind": "native_sherpa_asr",
                                "shared_execution": shared,
                            },
                            sort_keys=True,
                        ),
                    },
                }
            ],
        }

    accepted_interval = {
        "audio_start_sec": 0.0,
        "audio_end_sec": 0.1,
        "sample_start_index": 0,
        "sample_end_index": 1600,
        "sample_rate_hz": 16000,
        "source_clock_type": "external_media",
        "source_clock_id": "external_media:fixture",
        "timing_provenance": ("native_stream_accepted_audio_since_stream_or_reset.v1"),
    }
    event_rows = [
        component_status(terminal=False),
        {
            "evaluation_case_id": case_id,
            "adapter_event_type": "asr_partial",
            "accepted_audio_interval": accepted_interval,
            "text": "fixture",
            "is_final": False,
        },
        {
            "evaluation_case_id": case_id,
            "adapter_event_type": "asr_final",
            "accepted_audio_interval": accepted_interval,
            "text": "fixture",
            "is_final": True,
            "event_reason": {
                "code": "native_stateful_stream_update",
                "detail": (
                    "timing_provenance="
                    "native_stream_accepted_audio_since_stream_or_reset.v1"
                ),
            },
        },
        component_status(terminal=True),
    ]
    event_payload = gzip.compress(
        b"".join(_json_bytes(row) for row in event_rows), mtime=0
    )
    (result / "events.jsonl.gz").write_bytes(event_payload)
    checksums = json.loads((result / "checksums.json").read_bytes())
    entries = checksums["entries"]
    for name, payload in (
        ("diagnostics/cache_regime.json", cache_payload),
        ("diagnostics/case_status.jsonl", case_status_payload),
        ("events.jsonl.gz", event_payload),
        ("pipeline_identity.json", pipeline_payload),
    ):
        entries[name] = {"sha256": _sha(payload), "bytes": len(payload)}
    checksum_payload = _json_bytes(checksums)
    (result / "checksums.json").write_bytes(checksum_payload)
    return result, _sha(checksum_payload)


def _write_fresh_resource_result(
    root: Path,
    workspace: Path,
    *,
    job_id: str,
    job_identity_sha256: str,
    mode: str,
    protocol_id: str,
    protocol_sha256: str,
) -> tuple[Path, str]:
    result, _prior_sha = _write_metric_result(
        root,
        workspace,
        job_id=job_id,
        split="development",
        fixture_source_key="fresh_serial_resource_shared",
    )
    pipeline_payload = _json_bytes(
        {
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "execution_contract": {
                "schema_version": "h2-product-execution-contract.v1",
                "h2_job_id": job_id,
                "h2_job_identity_sha256": job_identity_sha256,
                "h2_protocol_id": protocol_id,
                "h2_protocol_sha256": protocol_sha256,
                "product_mode": mode,
            },
            "runtime_tuning": {
                "product_mode": mode,
                "redim_execution_strategy": "R2_ONE_SHARED_MODEL",
            },
        }
    )
    cache_payload = _json_bytes(
        {
            "schema_version": "full-pipeline-cache-regime.v1",
            "measurement_mode": "resources",
            "runtime_cache_scope": "isolated_attempt_local_resource_cold_start",
            "asr_stream_trace_enabled": False,
            "resource_measurement_serial_required": True,
            "enrollment_profile_materialization_excluded_from_runtime_span": True,
        }
    )
    (result / "pipeline_identity.json").write_bytes(pipeline_payload)
    (result / "diagnostics" / "cache_regime.json").write_bytes(cache_payload)
    checksums = json.loads((result / "checksums.json").read_bytes())
    entries = checksums["entries"]
    for name, payload in (
        ("diagnostics/cache_regime.json", cache_payload),
        ("pipeline_identity.json", pipeline_payload),
    ):
        entries[name] = {"sha256": _sha(payload), "bytes": len(payload)}
    checksum_payload = _json_bytes(checksums)
    (result / "checksums.json").write_bytes(checksum_payload)
    return result, _sha(checksum_payload)


def _write_overlap_result(
    root: Path,
    *,
    job_id: str,
    overlap_policy: str,
) -> tuple[Path, str, list[str]]:
    result = root / "results" / "jobs" / job_id / "result"
    (result / "references").mkdir(parents=True)
    (result / "diagnostics").mkdir(parents=True)
    cases: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    for overlay, known, unknown in (
        ("ALL_KNOWN", 2, 0),
        ("MIXED_KNOWN_UNKNOWN", 1, 1),
        ("ALL_UNKNOWN", 0, 2),
    ):
        for condition, overlap_class, overlap_ratio in (
            ("overlap", "moderate", 0.25),
            ("control", "none", 0.0),
            ("zero_backchannel", "backchannel", 0.0),
        ):
            case_id = f"case_{overlay.lower()}_{condition}"
            case_known = known
            case_unknown = unknown
            if overlay == "MIXED_KNOWN_UNKNOWN" and condition == "control":
                case_known, case_unknown = 1, 0
            speaker_ids = [
                f"development_{overlay.lower()}_{condition}_{index}"
                for index in range(case_known + case_unknown)
            ]
            cases.append(
                {
                    "protocol_case_id": case_id,
                    "source_case_id": case_id,
                    "partition": "development",
                    "duration_sec": 10.0,
                    "overlay_id": overlay,
                    "known_speaker_count": case_known,
                    "unknown_speaker_count": case_unknown,
                    "overlap": overlap_class,
                    "overlap_ratio": overlap_ratio,
                    "global_speaker_ids": speaker_ids,
                }
            )
            ratio = 0.2 if condition == "overlap" else 0.1

            def ratio_metric(metric_id: str, value: float = ratio) -> dict[str, object]:
                return {
                    "definition": f"fixture {metric_id}",
                    "denominator": 10.0,
                    "details": {
                        "aggregation": "per_recording_sufficient_statistics.v1"
                    },
                    "metric_id": metric_id,
                    "numerator": value * 10.0,
                    "reason": None,
                    "status": "computed",
                    "unit": "ratio" if "latency" not in metric_id else "seconds",
                    "value": value,
                }

            def sum_metric(metric_id: str, value: float = 1.0) -> dict[str, object]:
                return {
                    "definition": f"fixture {metric_id}",
                    "denominator": None,
                    "details": {"scalar_aggregation": "sum"},
                    "metric_id": metric_id,
                    "numerator": None,
                    "reason": None,
                    "status": "computed",
                    "unit": (
                        "merges" if metric_id == "identity_merge_count" else "seconds"
                    ),
                    "value": value,
                }

            stable = ratio_metric("stable_name_latency_sec", 1.5)
            if overlay == "ALL_UNKNOWN":
                stable.update(
                    {
                        "denominator": None,
                        "numerator": None,
                        "reason": "known identity is not present",
                        "status": "unsupported",
                        "value": None,
                    }
                )
            metric_rows.append(
                {
                    "audio_duration_sec": 10.0,
                    "case_id": case_id,
                    "overlay_id": overlay,
                    "reference_speaker_ids": speaker_ids,
                    "reports": {
                        "diarization": {
                            "metrics": {
                                "miss_rate": ratio_metric("miss_rate"),
                                "merge_contamination_rate": ratio_metric(
                                    "merge_contamination_rate", ratio / 2
                                ),
                            }
                        },
                        "identity": {
                            "metrics": {
                                "stable_name_latency_sec": stable,
                                "wrong_known_time_sec": sum_metric(
                                    "wrong_known_time_sec"
                                ),
                                "stranger_false_known_time_sec": sum_metric(
                                    "stranger_false_known_time_sec"
                                ),
                                "identity_merge_count": sum_metric(
                                    "identity_merge_count"
                                ),
                                "generic_known_time_sec": sum_metric(
                                    "generic_known_time_sec"
                                ),
                            }
                        },
                        "speaker_transcription": {
                            "metrics": {
                                "word_speaker_label_accuracy": ratio_metric(
                                    "word_speaker_label_accuracy", 0.9
                                )
                            }
                        },
                    },
                }
            )
    cases_payload = b"".join(_json_bytes(row) for row in cases)
    metrics_payload = b"".join(_json_bytes(row) for row in metric_rows)
    pipeline_payload = _json_bytes(
        {"runtime_tuning": {"overlap_policy": overlap_policy}}
    )
    (result / "references" / "cases.jsonl").write_bytes(cases_payload)
    (result / "diagnostics" / "per_case_metrics.jsonl").write_bytes(metrics_payload)
    (result / "pipeline_identity.json").write_bytes(pipeline_payload)
    entries = {
        "references/cases.jsonl": {
            "sha256": _sha(cases_payload),
            "bytes": len(cases_payload),
        },
        "diagnostics/per_case_metrics.jsonl": {
            "sha256": _sha(metrics_payload),
            "bytes": len(metrics_payload),
        },
        "pipeline_identity.json": {
            "sha256": _sha(pipeline_payload),
            "bytes": len(pipeline_payload),
        },
    }
    checksum_payload = _json_bytes({"entries": entries})
    (result / "checksums.json").write_bytes(checksum_payload)
    return (
        result,
        _sha(checksum_payload),
        [str(row["protocol_case_id"]) for row in cases],
    )


def _write_science_result(
    root: Path,
    *,
    job_id: str,
    tables: dict[str, list[dict[str, object]]],
) -> tuple[Path, str]:
    artifact_root = root / "results" / "jobs" / job_id / "artifacts"
    artifact_root.mkdir(parents=True)
    manifest = []
    for filename, rows in sorted(tables.items()):
        payload = _csv_table(rows)
        (artifact_root / filename).write_bytes(payload)
        manifest.append(
            {"path": filename, "row_count": len(rows), "sha256": _sha(payload)}
        )
    result_path = artifact_root / "job_result.json"
    result_payload = _json_bytes(
        {
            "artifact_manifest": manifest,
            "evaluation_material_inspected": False,
            "status": "COMPLETE",
        }
    )
    result_path.write_bytes(result_payload)
    return result_path, _sha(result_payload)


def _write_host_io_fixture(
    workspace: Path,
    controller_state: dict[str, object],
) -> None:
    starts = (
        "2026-08-29T00:00:00+00:00",
        "2026-08-29T00:10:00+00:00",
        "2026-08-29T00:20:00+00:00",
        "2026-08-29T00:30:00+00:00",
    )
    ends = (
        "2026-08-29T00:10:00+00:00",
        "2026-08-29T00:20:00+00:00",
        "2026-08-29T00:30:00+00:00",
        "2026-08-29T00:40:00+00:00",
    )
    event_times = (
        "2026-08-29T00:05:00Z",
        "2026-08-29T00:15:00Z",
        "2026-08-29T00:25:00Z",
        "2026-08-29T00:35:00Z",
    )
    os_seconds = (5.0, 10.0, 15.0, 40.0)
    queue_seconds = (10.0, 20.0, 30.0, 39.0)
    reference_hashes = {
        "cases": "a" * 64,
        "enrollment_registry": "b" * 64,
        "identity_overlays": "c" * 64,
        "speaker_attributed_transcripts": "d" * 64,
    }
    state_jobs = controller_state["jobs"]
    assert isinstance(state_jobs, dict)
    candidates = []
    correlations = []
    esent_events = []
    guardian_events = []
    for index, job_id in enumerate(HOST_IO_CANDIDATE_JOB_IDS):
        state_row = state_jobs[job_id]
        assert isinstance(state_row, dict)
        result_sha = str(state_row["result_sha256"])
        candidates.append(
            {
                "job_id": job_id,
                "started_at_utc": starts[index],
                "completed_at_utc": ends[index],
                "completed_cases": 2,
                "completed_audio_sec": 120.0,
                "wall_elapsed_sec": 600.0,
                "wall_rtf": 5.0,
                "event_count": 200,
                "blocked_total_sec": queue_seconds[index] + 1.0,
                "blocked_max_sec": queue_seconds[index],
                "cases_with_blocked_max_gt_10_sec": int(queue_seconds[index] > 10.0),
                "cases_with_blocked_max_gt_60_sec": 0,
                "dropped_frames": 0,
                "result_sha256": result_sha,
                "result_path": f"%RESULTS_ROOT%\\jobs\\{job_id}\\result",
                "checksum_validation": {
                    "status": "VALID",
                    "declared_entry_count": 24,
                    "verified_entry_count": 24,
                    "failures": [],
                    "checksums_sha256": str(index + 1) * 64,
                    "reference_hashes": reference_hashes,
                },
                "largest_queue_stalls": [
                    {
                        "case_id": f"case_{index}_0",
                        "audio_duration_sec": 60.0,
                        "event_count": 100,
                        "blocked_total_sec": queue_seconds[index],
                        "blocked_max_sec": queue_seconds[index],
                        "dropped_frames": 0,
                    },
                    {
                        "case_id": f"case_{index}_1",
                        "audio_duration_sec": 60.0,
                        "event_count": 100,
                        "blocked_total_sec": 1.0,
                        "blocked_max_sec": 1.0,
                        "dropped_frames": 0,
                    },
                ],
            }
        )
        esent_events.append(
            {
                "time_created_utc": event_times[index],
                "provider": "ESENT",
                "event_id": 510,
                "level": "Warning",
                "reported_io_seconds": os_seconds[index],
                "message": "sanitized completed I/O delay",
            }
        )
        guardian_events.append(
            {
                "at_utc": event_times[index],
                "action": "guardian_pass",
                "capacity_risk": "OK",
                "free_gib": 140.0,
                "job_id": job_id,
            }
        )
        correlations.append(
            {
                "job_id": job_id,
                "esent_event_count": 1,
                "completed_io_event_count": 1,
                "maximum_esent_reported_io_sec": os_seconds[index],
                "maximum_esent_event_utc": event_times[index],
                "maximum_pipeline_blocked_put_sec": queue_seconds[index],
                "absolute_maximum_difference_sec": abs(
                    os_seconds[index] - queue_seconds[index]
                ),
                "acronis_vss_event_count": int(index == 3),
                "independent_storage_guardian_event_count": 1,
            }
        )
    closest = correlations[-1]
    receipt = {
        "schema_version": "h2-host-io-interference.v1",
        "status": "HOST_STORAGE_IO_INTERFERENCE_CONFIRMED",
        "generated_at_utc": "2026-08-29T00:45:00+00:00",
        "protocol_id": controller_state["protocol_id"],
        "protocol_sha256": controller_state["protocol_sha256"],
        "job_manifest_sha256": controller_state["job_manifest_sha256"],
        "candidate_job_ids": list(HOST_IO_CANDIDATE_JOB_IDS),
        "evidence_window": {
            "start_utc": starts[0],
            "end_utc": ends[-1],
            "query_start_local": "2026-08-28T23:59:00+00:00",
            "query_end_local": "2026-08-29T00:41:00+00:00",
        },
        "scientific_interpretation": {
            "accuracy_metrics_eligible": True,
            "development_promotion_eligible": True,
            "operational_wall_time_eligible": False,
            "resource_comparison_eligible": False,
            "total_rtf_entered_promotion": False,
            "scientific_results_or_policies_modified": False,
            "inference_rerun": False,
            "queue_policy": "block",
            "dropped_frames_total": 0,
            "conclusion": "fixture accuracy valid; resource timing contaminated",
            "causal_attribution": "no sole-cause claim",
        },
        "correlation": {
            "esent_hung_io_event_count": len(esent_events),
            "esent_completed_io_event_count": len(esent_events),
            "maximum_esent_reported_io_sec": max(os_seconds),
            "maximum_pipeline_blocked_put_sec": max(queue_seconds),
            "absolute_maximum_difference_sec": abs(
                max(os_seconds) - max(queue_seconds)
            ),
            "acronis_vss_event_count": 1,
            "storage_driver_warning_or_error_count": 0,
            "independent_storage_guardian_event_count": len(guardian_events),
            "per_job": correlations,
            "closest_maximum_duration_pair": closest,
        },
        "promotion": {
            "decision_path": "%WORKSPACE%\\promotions\\phase_1_full.json",
            "decision_sha256": "e" * 64,
            "selected_candidates": list(HOST_IO_SELECTED_CONFIGURATIONS),
            "pareto_frontier": [
                "S2_BALANCED",
                "S1_COVERAGE",
                "S6_HOP_050",
                "S7_HOP_100",
            ],
            "common_metric_priority": ["der", "jer"],
            "evaluation_material_inspected": False,
            "weighted_composite_used": False,
        },
        "candidate_jobs": candidates,
        "windows_evidence": {
            "esent_events": esent_events,
            "acronis_vss_events": [
                {
                    "time_created_utc": event_times[-1],
                    "provider": "VSS",
                    "event_id": 8194,
                    "level": "Information",
                    "reported_io_seconds": None,
                    "message": "sanitized backup coincidence",
                }
            ],
            "storage_driver_warnings_or_errors": [],
            "storage_provider_query_failures": [],
            "storage_guardian_events": guardian_events,
            "active_backup_process_names_at_capture": ["backup_worker"],
        },
        "host_storage": {
            "drive": "C:",
            "disk_number": 0,
            "disk_model": "fixture NVMe",
            "bus_type": "NVMe",
            "health_status": "Healthy",
            "operational_status": ["Online"],
            "volume_health_status": "Healthy",
            "volume_operational_status": ["OK"],
            "free_bytes_at_capture": 150_000_000_000,
            "size_bytes": 2_000_000_000_000,
            "reliability_counters": "UNAVAILABLE_WITHOUT_ELEVATED_CIM_ACCESS",
        },
        "host_os": {
            "caption": "fixture Windows",
            "version": "fixture",
            "build_number": "fixture",
        },
        "provenance": {
            "collector": "scripts/capture_h2_host_io_interference.ps1",
            "collector_sha256": _sha(
                (
                    Path(__file__).resolve().parents[1]
                    / "scripts/capture_h2_host_io_interference.ps1"
                ).read_bytes()
            ),
            "program_state_sha256_at_capture": _sha(_json_bytes(controller_state)),
            "job_manifest_embedded_self_hash_matches_state": True,
            "job_manifest_file_sha256": "f" * 64,
            "all_candidate_result_checksums_verified": True,
            "identical_case_reference_hashes_verified": True,
            "windows_event_queries": ["fixture"],
            "host_paths_sanitized": True,
        },
    }
    destination = (
        workspace / "diagnostics/host_io_interference/windows_host_io_interference.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_json_bytes(receipt))


def _write_serial_host_io_fixtures(
    workspace: Path,
    controller_state: dict[str, object],
    manifest_rows: list[dict[str, object]],
) -> None:
    state_jobs = controller_state["jobs"]
    assert isinstance(state_jobs, dict)
    by_id = {str(row["job_id"]): row for row in manifest_rows}
    collector_sha = _sha(
        (
            Path(__file__).resolve().parents[1]
            / "scripts/capture_h2_host_io_interference.ps1"
        ).read_bytes()
    )
    reference_hashes = {
        "cases": "a" * 64,
        "enrollment_registry": "b" * 64,
        "identity_overlays": "c" * 64,
        "speaker_attributed_transcripts": "d" * 64,
    }
    destination_root = workspace / "diagnostics/host_io_interference"
    destination_root.mkdir(parents=True, exist_ok=True)
    for group in SERIAL_HOST_IO_GROUPS:
        candidates = []
        correlations = []
        starts = []
        ends = []
        maximum_queue = 0.0
        for index, job_id in enumerate(group["job_ids"], start=1):
            state_row = state_jobs[job_id]
            manifest_row = by_id[job_id]
            assert isinstance(state_row, dict)
            starts.append(str(state_row["started_at_utc"]))
            ends.append(str(state_row["completed_at_utc"]))
            blocked_max = index / 4.0
            maximum_queue = max(maximum_queue, blocked_max)
            candidates.append(
                {
                    "job_id": job_id,
                    "phase_index": group["phase_index"],
                    "job_kind": group["job_kind"],
                    "measurement_mode": "resources",
                    "serial_execution": True,
                    "started_at_utc": state_row["started_at_utc"],
                    "completed_at_utc": state_row["completed_at_utc"],
                    "completed_cases": state_row["completed_cases"],
                    "completed_audio_sec": state_row["completed_audio_sec"],
                    "wall_elapsed_sec": 300.0,
                    "wall_rtf": 2.5,
                    "event_count": 200,
                    "blocked_total_sec": blocked_max + 0.5,
                    "blocked_max_sec": blocked_max,
                    "cases_with_blocked_max_gt_10_sec": 0,
                    "cases_with_blocked_max_gt_60_sec": 0,
                    "dropped_frames": 0,
                    "result_sha256": state_row["result_sha256"],
                    "result_path": f"%RESULTS_ROOT%\\jobs\\{job_id}\\result",
                    "checksum_validation": {
                        "status": "VALID",
                        "declared_entry_count": 24,
                        "verified_entry_count": 24,
                        "failures": [],
                        "checksums_sha256": str(index) * 64,
                        "reference_hashes": reference_hashes,
                    },
                    "largest_queue_stalls": [],
                    "fixture_configuration_id": manifest_row["configuration_id"],
                }
            )
            correlations.append(
                {
                    "job_id": job_id,
                    "esent_event_count": 0,
                    "completed_io_event_count": 0,
                    "maximum_esent_reported_io_sec": None,
                    "maximum_esent_event_utc": None,
                    "maximum_pipeline_blocked_put_sec": blocked_max,
                    "absolute_maximum_difference_sec": None,
                    "acronis_vss_event_count": 0,
                    "independent_storage_guardian_event_count": 0,
                }
            )
        receipt = {
            "schema_version": "h2-host-io-interference.v1",
            "status": "SERIAL_RESOURCE_HOST_IO_CLEAR",
            "evidence_class": "SerialResource",
            "generated_at_utc": "2026-08-29T03:00:00+00:00",
            "protocol_id": controller_state["protocol_id"],
            "protocol_sha256": controller_state["protocol_sha256"],
            "job_manifest_sha256": controller_state["job_manifest_sha256"],
            "candidate_job_ids": list(group["job_ids"]),
            "evidence_window": {
                "start_utc": starts[0],
                "end_utc": ends[-1],
                "query_start_local": starts[0],
                "query_end_local": ends[-1],
            },
            "scientific_interpretation": {
                "accuracy_metrics_eligible": True,
                "development_promotion_eligible": False,
                "operational_wall_time_eligible": True,
                "resource_comparison_eligible": True,
                "total_rtf_entered_promotion": False,
                "scientific_results_or_policies_modified": False,
                "inference_rerun": False,
                "queue_policy": "block",
                "dropped_frames_total": 0,
                "host_io_interference_detected": False,
                "host_io_evidence_complete": True,
                "conclusion": "fixture serial evidence is clear",
                "causal_attribution": "no sole-cause claim",
            },
            "correlation": {
                "esent_hung_io_event_count": 0,
                "esent_completed_io_event_count": 0,
                "maximum_esent_reported_io_sec": 0.0,
                "maximum_pipeline_blocked_put_sec": maximum_queue,
                "absolute_maximum_difference_sec": maximum_queue,
                "acronis_vss_event_count": 0,
                "storage_driver_warning_or_error_count": 0,
                "independent_storage_guardian_event_count": 0,
                "per_job": correlations,
                "closest_maximum_duration_pair": None,
            },
            "promotion": None,
            "candidate_jobs": candidates,
            "windows_evidence": {
                "esent_events": [],
                "acronis_vss_events": [],
                "storage_driver_warnings_or_errors": [],
                "storage_provider_query_failures": [],
                "storage_guardian_events": [],
                "active_backup_process_names_at_capture": [],
            },
            "host_storage": {
                "drive": "C:",
                "disk_number": 0,
                "disk_model": "fixture NVMe",
                "bus_type": "NVMe",
                "health_status": "Healthy",
                "operational_status": ["Online"],
                "volume_health_status": "Healthy",
                "volume_operational_status": ["OK"],
                "free_bytes_at_capture": 150_000_000_000,
                "size_bytes": 2_000_000_000_000,
                "reliability_counters": "UNAVAILABLE_WITHOUT_ELEVATED_CIM_ACCESS",
            },
            "host_os": {
                "caption": "fixture Windows",
                "version": "fixture",
                "build_number": "fixture",
            },
            "provenance": {
                "collector": "scripts/capture_h2_host_io_interference.ps1",
                "collector_sha256": collector_sha,
                "evidence_class": "SerialResource",
                "program_state_sha256_at_capture": "e" * 64,
                "job_manifest_embedded_self_hash_matches_state": True,
                "job_manifest_file_sha256": "f" * 64,
                "all_candidate_result_checksums_verified": True,
                "identical_case_reference_hashes_verified": True,
                "nonidentical_references_explicitly_allowed": False,
                "windows_event_queries": ["fixture"],
                "host_paths_sanitized": True,
            },
        }
        (destination_root / str(group["receipt_filename"])).write_bytes(
            _json_bytes(receipt)
        )


def _write_phase2_quiet_replay_fixture(
    root: Path,
    workspace: Path,
    native_payloads: dict[str, bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create a checksum-bound eligible replay without running model inference."""

    actual_tool_root = Path(__file__).resolve().parents[1]
    fake_tool_root = root / "evaluation_tool"
    script_root = fake_tool_root / "scripts"
    script_root.mkdir(parents=True)
    for name in (
        "capture_h2_host_io_interference.ps1",
        "watch_h2_serial_resource_io.ps1",
        "replay_h2_phase2_serial_resources.py",
        "H2_PHASE2_QUIET_RESOURCE_REPLAY_README.md",
    ):
        (script_root / name).write_bytes(
            (actual_tool_root / "scripts" / name).read_bytes()
        )
    monkeypatch.setattr(final_package_module, "TOOL_ROOT", fake_tool_root)

    phase2 = SERIAL_HOST_IO_GROUPS[0]
    job_ids = tuple(map(str, phase2["job_ids"]))
    receipt_path = (
        workspace / "diagnostics/host_io_interference" / str(phase2["receipt_filename"])
    )
    clear_receipt = json.loads(receipt_path.read_bytes())
    contaminated_receipt = json.loads(receipt_path.read_bytes())
    contaminated_receipt["status"] = "SERIAL_RESOURCE_HOST_IO_CONTAMINATED"
    contaminated_receipt["scientific_interpretation"][
        "resource_comparison_eligible"
    ] = False
    contaminated_receipt["scientific_interpretation"][
        "host_io_interference_detected"
    ] = True
    receipt_path.write_bytes(_json_bytes(contaminated_receipt))

    state = json.loads(native_payloads["controller/program_state.json"])
    job_manifest = json.loads(native_payloads["protocol/job_manifest.json"])
    runtime_identity = json.loads(native_payloads[RUNTIME_IDENTITY_MEMBER])
    manifest_by_id = {
        str(row["job_id"]): row for row in job_manifest["jobs"] if isinstance(row, dict)
    }
    source_jobs = state["jobs"]
    attempt_id = "quiet01"
    replay_name = f"{workspace.name}_resource_replay_{attempt_id}"
    replay_workspace = fake_tool_root / "automated_runs" / replay_name
    replay_summary = fake_tool_root / "JustPeachyResearchSummaries" / replay_name
    replay_results = fake_tool_root / "JustPeachyResults/full_pipeline" / replay_name
    replay_workspace.mkdir(parents=True)
    replay_summary.mkdir(parents=True)
    replay_results.mkdir(parents=True)

    launcher = script_root / "replay_h2_phase2_serial_resources.py"
    replay_manifest_core = {
        "schema_version": "h2-phase2-quiet-resource-replay.v1",
        "attempt_id": attempt_id,
        "purpose": "fixture quiet replay",
        "source_workspace": str(workspace),
        "source_results_root": str(root / "source_results"),
        "replay_workspace": str(replay_workspace),
        "replay_results_root": str(replay_results),
        "protocol_id": state["protocol_id"],
        "protocol_sha256": state["protocol_sha256"],
        "job_manifest_sha256": state["job_manifest_sha256"],
        "runtime_implementation_identity_sha256": runtime_identity["identity_sha256"],
        "launcher_path": "scripts/replay_h2_phase2_serial_resources.py",
        "launcher_sha256": _sha(launcher.read_bytes()),
        "measurement_mode": "resources",
        "serial_execution": True,
        "execution_order": list(job_ids),
        "cooldown_sec_between_jobs": 60,
        "quiet_window_minutes": 15,
        "automatic_time_cutoff": False,
        "job_bindings": [
            {
                "job_id": job_id,
                "job_identity_sha256": manifest_by_id[job_id]["identity_sha256"],
                "configuration_id": manifest_by_id[job_id]["configuration_id"],
                "runtime_tuning_identity_sha256": canonical_sha256(
                    manifest_by_id[job_id].get("runtime_tuning") or {}
                ),
                "case_ids_sha256": canonical_sha256(
                    list(manifest_by_id[job_id].get("case_ids") or ())
                ),
                "case_count": len(manifest_by_id[job_id].get("case_ids") or ()),
                "audio_duration_sec": manifest_by_id[job_id].get("audio_duration_sec")
                or 0.0,
                "source_result_sha256": source_jobs[job_id]["result_sha256"],
            }
            for job_id in job_ids
        ],
        "heldout_references_opened": False,
        "scientific_settings_changed": False,
        "source_results_overwritten": False,
    }
    replay_manifest = {
        **replay_manifest_core,
        "replay_manifest_sha256": canonical_sha256(replay_manifest_core),
    }
    (replay_workspace / "resource_replay_manifest.json").write_bytes(
        _json_bytes(replay_manifest)
    )
    (replay_workspace / "job_manifest.json").write_bytes(
        native_payloads["protocol/job_manifest.json"]
    )
    replay_state = {
        "schema_version": "h2-phase2-quiet-resource-replay-state.v1",
        "status": "COMPLETE",
        "protocol_id": state["protocol_id"],
        "protocol_sha256": state["protocol_sha256"],
        "job_manifest_sha256": state["job_manifest_sha256"],
        "replay_manifest_sha256": replay_manifest["replay_manifest_sha256"],
        "updated_at_utc": "2026-08-30T04:00:00Z",
        "jobs": {
            job_id: {
                **source_jobs[job_id],
                "result_path": str(replay_results / "jobs" / job_id / "result"),
            }
            for job_id in job_ids
        },
    }
    (replay_workspace / "program_state.json").write_bytes(_json_bytes(replay_state))
    replay_receipt_path = (
        replay_workspace
        / "diagnostics/host_io_interference/serial_resource_replay.json"
    )
    replay_receipt_path.parent.mkdir(parents=True)
    replay_receipt_path.write_bytes(_json_bytes(clear_receipt))

    metrics = {
        job_ids[0]: {
            "total_rtf": 1.4,
            "audio_throughput": 0.71,
            "peak_rss_bytes": 3_000_000_000,
            "maximum_queue_depth": 16,
            "model_bytes": 20_000_000,
            "cache_bytes": 10_000_000,
            "failure_count": 0,
            "retry_count": 0,
            "blocked_total_sec": 2.0,
            "blocked_max_sec": 0.5,
            "dropped_frames": 0,
            "result_sha256": replay_state["jobs"][job_ids[0]]["result_sha256"],
        },
        job_ids[1]: {
            "total_rtf": 1.2,
            "audio_throughput": 0.83,
            "peak_rss_bytes": 2_000_000_000,
            "maximum_queue_depth": 16,
            "model_bytes": 18_000_000,
            "cache_bytes": 10_000_000,
            "failure_count": 0,
            "retry_count": 0,
            "blocked_total_sec": 1.5,
            "blocked_max_sec": 0.5,
            "dropped_frames": 0,
            "result_sha256": replay_state["jobs"][job_ids[1]]["result_sha256"],
        },
    }
    comparison_core = {
        "schema_version": "h2-phase2-quiet-resource-comparison.v1",
        "status": "COMPLETE_ELIGIBLE",
        "eligible_for_final_resource_ranking": True,
        "host_io_status": "SERIAL_RESOURCE_HOST_IO_CLEAR",
        "replay_manifest_sha256": replay_manifest["replay_manifest_sha256"],
        "execution_order": list(job_ids),
        "jobs": metrics,
        "matched_deltas": {
            "r2_minus_r1_total_rtf": -0.2,
            "r2_reduction_fraction_total_rtf": (1.4 - 1.2) / 1.4,
        },
        "interpretation": "Use this replay for the final R1/R2 resource comparison.",
    }
    comparison = {
        **comparison_core,
        "comparison_sha256": canonical_sha256(comparison_core),
    }
    (replay_summary / "resource_comparison.json").write_bytes(_json_bytes(comparison))
    comparison_rows = []
    for job_id, strategy in zip(job_ids, ("R1", "R2"), strict=True):
        comparison_rows.append(
            {
                "job_id": job_id,
                "strategy": strategy,
                "eligible": True,
                "host_io_status": "SERIAL_RESOURCE_HOST_IO_CLEAR",
                **{
                    key: metrics[job_id][key]
                    for key in (
                        "total_rtf",
                        "peak_rss_bytes",
                        "maximum_queue_depth",
                        "blocked_total_sec",
                        "blocked_max_sec",
                        "dropped_frames",
                        "result_sha256",
                    )
                },
            }
        )
    (replay_summary / "resource_comparison.csv").write_bytes(
        _csv_table(comparison_rows)
    )


def _write_native_package(root: Path, workspace: Path) -> Path:
    fixture_protocol_id = "h2_fixture_protocol"
    fixture_protocol_sha256 = "a" * 64
    axis_root = workspace / "axis_selections"
    axis_root.mkdir(parents=True)
    decisions = {}
    for key in ("boundary_correction", "overlap_policy"):
        selected = (
            "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY"
            if key == "overlap_policy"
            else "BOUNDARY_CORRECTION_0250MS"
        )
        payload = _json_bytes(
            {
                "schema_version": "h2-development-promotion.v1",
                "status": "COMPLETE",
                "selected_candidates": [selected],
            }
        )
        path = axis_root / f"{key}.json"
        path.write_bytes(payload)
        decisions[key] = {
            "decision_path": str(path),
            "decision_sha256": _sha(payload),
        }

    result_rows = {}
    for job_id, split in (
        ("baseline_job", "development"),
        ("known_job", "evaluation"),
        ("anonymous_job", "evaluation"),
        ("memory_job", "evaluation"),
    ):
        result_path, result_sha = _write_metric_result(
            root, workspace, job_id=job_id, split=split
        )
        result_rows[job_id] = {
            "state": "COMPLETE",
            "result_path": str(result_path.resolve()),
            "result_sha256": result_sha,
        }
    streaming_job_id = "streaming_qualification_job"
    streaming_job_identity = _sha(
        _json_bytes({"fixture_job_id": streaming_job_id, "kind": "qualification"})
    )
    streaming_result, streaming_result_sha = _write_streaming_qualification_result(
        root,
        workspace,
        job_id=streaming_job_id,
        job_identity_sha256=streaming_job_identity,
        protocol_id=fixture_protocol_id,
        protocol_sha256=fixture_protocol_sha256,
    )
    result_rows[streaming_job_id] = {
        "state": "COMPLETE",
        "result_path": str(streaming_result.resolve()),
        "result_sha256": streaming_result_sha,
        "completed_cases": 1,
        "completed_audio_sec": 3.0,
    }
    streaming_job_rows = [
        {
            "audio_duration_sec": 3.0,
            "case_ids": ["case_streaming_qualification"],
            "configuration_id": "H2_TRUE_STREAMING_QUALIFICATION",
            "development_only": True,
            "identity_sha256": streaming_job_identity,
            "job_id": streaming_job_id,
            "job_kind": "runtime_qualification",
            "mode": "H2_SESSION_MEMORY_ENHANCED",
            "phase_index": 0,
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "split": "development",
        }
    ]
    paragraph_job_rows = []
    for policy in (
        "T1_ASR_ENDPOINT_PUNCTUATION",
        "T2_PAUSE_ASR_ENDPOINT",
        "T3_PAUSE_ASR_SPEAKER_CHANGE",
        "T4_SPEAKER_CHANGE_DOMINANT",
    ):
        job_id = f"paragraph_{policy.lower()}"
        result_path, result_sha = _write_metric_result(
            root,
            workspace,
            job_id=job_id,
            split="development",
            paragraph_policy=policy,
        )
        result_rows[job_id] = {
            "state": "COMPLETE",
            "result_path": str(result_path.resolve()),
            "result_sha256": result_sha,
        }
        paragraph_job_rows.append(
            {
                "configuration_id": policy,
                "job_id": job_id,
                "job_kind": "post_selection_paragraph_validation",
                "mode": "H2_SESSION_MEMORY_ENHANCED",
            }
        )
    boundary_job_rows = []
    boundary_span_assignments = {
        "BOUNDARY_CORRECTION_0000MS": ("anon_0", "anon_0"),
        "BOUNDARY_CORRECTION_0250MS": ("anon_0", "anon_1"),
        "BOUNDARY_CORRECTION_0500MS": ("anon_1", "anon_1"),
        "BOUNDARY_CORRECTION_0750MS": ("anon_0", "anon_0"),
        "BOUNDARY_CORRECTION_1000MS": ("anon_0", "anon_1"),
    }
    for configuration_id in BOUNDARY_CONFIGURATIONS:
        correction_ms = int(configuration_id.rsplit("_", 1)[-1][:-2])
        job_id = f"boundary_{correction_ms:04d}ms"
        result_path, result_sha = _write_metric_result(
            root,
            workspace,
            job_id=job_id,
            split="development",
            boundary_correction_ms=correction_ms,
            span_anonymous_ids=boundary_span_assignments[configuration_id],
            event_initial_first_anonymous_id=(
                "anon_1" if configuration_id == "BOUNDARY_CORRECTION_0250MS" else None
            ),
            fixture_source_key="boundary_shared",
        )
        result_rows[job_id] = {
            "state": "COMPLETE",
            "result_path": str(result_path.resolve()),
            "result_sha256": result_sha,
        }
        boundary_job_rows.append(
            {
                "audio_duration_sec": 3.0,
                "case_ids": ["case_boundary_shared"],
                "configuration_id": configuration_id,
                "development_only": True,
                "job_id": job_id,
                "job_kind": "runtime_accuracy",
                "runtime_tuning": {
                    "boundary_correction_ms": correction_ms,
                    "segmentation_hop_sec": 0.75,
                },
                "split": "development",
            }
        )
    overlap_job_rows = []
    overlap_cases: list[str] | None = None
    for configuration_id, job_id in (
        ("INCLUDE_PREDICTED_OVERLAP", "overlap_include_job"),
        (
            "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
            "overlap_exclude_job",
        ),
    ):
        result_path, result_sha, case_ids = _write_overlap_result(
            root,
            job_id=job_id,
            overlap_policy=configuration_id,
        )
        if overlap_cases is None:
            overlap_cases = case_ids
        else:
            assert overlap_cases == case_ids
        result_rows[job_id] = {
            "state": "COMPLETE",
            "result_path": str(result_path.resolve()),
            "result_sha256": result_sha,
        }
        overlap_job_rows.append(
            {
                "audio_duration_sec": 60.0,
                "case_ids": case_ids,
                "configuration_id": configuration_id,
                "development_only": True,
                "job_id": job_id,
                "job_kind": "runtime_accuracy",
                "runtime_tuning": {
                    "overlap_policy": configuration_id,
                    "segmentation_hop_sec": 0.75,
                },
                "split": "development",
            }
        )
    science_job_rows = []
    policy_path, policy_sha = _write_science_result(
        root,
        job_id="policy_job",
        tables={
            "open_set_policy_frontier.csv": [
                {
                    "gallery_requested_size": "10",
                    "target_fpir": 0.01,
                    "observed_fpir": 0.008,
                    "known_acceptance_rate": 0.91,
                }
            ],
            "identity_hubness.csv": [
                {
                    "enrolled_id": "speaker_0",
                    "unknown_top1_count": 3,
                    "unknown_top1_share": 0.3,
                    "maximum_impostor_score": 0.42,
                    "mean_top1_top2_margin": 0.05,
                }
            ],
        },
    )
    result_rows["policy_job"] = {
        "state": "COMPLETE",
        "result_path": str(policy_path.resolve()),
        "result_sha256": policy_sha,
    }
    science_job_rows.append(
        {
            "development_only": True,
            "job_id": "policy_job",
            "job_kind": "policy_replay",
        }
    )
    integrated_path, integrated_sha = _write_science_result(
        root,
        job_id="integrated_job",
        tables={
            "integrated_enrollment_matrix.csv": [
                {"cell_id": "cell_0", "stranger_fpir": 0.01}
            ],
            "integrated_enrollment_qc_events.csv": [
                {
                    "cell_id": "cell_0",
                    "speaker_id": "speaker_0",
                    "quality_decision": "QUALITY_ACCEPTED",
                }
            ],
            "integrated_enrollment_hubness.csv": [
                {
                    "cell_id": "cell_0",
                    "candidate_speaker_id": "speaker_0",
                    "nearest_stranger_count": 3,
                }
            ],
            "integrated_enrollment_selected_cell.csv": [
                {"cell_id": "cell_0", "selection_label": "INTEGRATED_SELECTED_CELL"}
            ],
        },
    )
    result_rows["integrated_job"] = {
        "state": "COMPLETE",
        "result_path": str(integrated_path.resolve()),
        "result_sha256": integrated_sha,
    }
    science_job_rows.append(
        {
            "development_only": True,
            "job_id": "integrated_job",
            "job_kind": "integrated_enrollment",
        }
    )
    host_io_job_rows = []
    host_starts = (
        "2026-08-29T00:00:00+00:00",
        "2026-08-29T00:10:00+00:00",
        "2026-08-29T00:20:00+00:00",
        "2026-08-29T00:30:00+00:00",
    )
    host_ends = (
        "2026-08-29T00:10:00+00:00",
        "2026-08-29T00:20:00+00:00",
        "2026-08-29T00:30:00+00:00",
        "2026-08-29T00:40:00+00:00",
    )
    for index, job_id in enumerate(HOST_IO_CANDIDATE_JOB_IDS):
        result_rows[job_id] = {
            "state": "COMPLETE",
            "result_path": result_rows["baseline_job"]["result_path"],
            "result_sha256": result_rows["baseline_job"]["result_sha256"],
            "started_at_utc": host_starts[index],
            "completed_at_utc": host_ends[index],
            "completed_cases": 2,
            "completed_audio_sec": 120.0,
        }
        host_io_job_rows.append(
            {
                "configuration_id": f"HOST_IO_MEDIUM_{index + 1}",
                "development_only": True,
                "job_id": job_id,
                "job_kind": "successive_halving_runtime",
                "mode": "H2_SESSION_MEMORY_ENHANCED",
                "phase_index": 1,
                "serial": False,
                "split": "development",
            }
        )
    serial_host_io_job_rows = []
    serial_ordinal = 0
    serial_configs = (
        "R1_TWO_INDEPENDENT_MODELS_MATCHED_SERIAL_RESOURCE",
        "R2_ONE_SHARED_MODEL_MATCHED_SERIAL_RESOURCE",
        "H2_KNOWN_ONLY_SERIAL_RESOURCE",
        "H2_SESSION_ANONYMOUS_SERIAL_RESOURCE",
        "H2_SESSION_MEMORY_ENHANCED_SERIAL_RESOURCE",
    )
    serial_modes = (
        "H2_SESSION_MEMORY_ENHANCED",
        "H2_SESSION_MEMORY_ENHANCED",
        "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_ENHANCED",
    )
    for group in SERIAL_HOST_IO_GROUPS:
        for job_id in group["job_ids"]:
            start_minute = 60 + serial_ordinal * 5
            end_minute = start_minute + 5
            started = (
                f"2026-08-29T{start_minute // 60:02d}:{start_minute % 60:02d}:00+00:00"
            )
            completed = (
                f"2026-08-29T{end_minute // 60:02d}:{end_minute % 60:02d}:00+00:00"
            )
            mode = serial_modes[serial_ordinal]
            manifest_identity = _sha(
                _json_bytes(
                    {
                        "fixture_job_id": job_id,
                        "kind": group["job_kind"],
                    }
                )
            )
            result_path = result_rows["baseline_job"]["result_path"]
            result_sha256 = result_rows["baseline_job"]["result_sha256"]
            if group["job_kind"] == "post_selection_resource_runtime":
                fresh_result, fresh_result_sha = _write_fresh_resource_result(
                    root,
                    workspace,
                    job_id=job_id,
                    job_identity_sha256=manifest_identity,
                    mode=mode,
                    protocol_id=fixture_protocol_id,
                    protocol_sha256=fixture_protocol_sha256,
                )
                result_path = str(fresh_result.resolve())
                result_sha256 = fresh_result_sha
            result_rows[job_id] = {
                "state": "COMPLETE",
                "result_path": result_path,
                "result_sha256": result_sha256,
                "started_at_utc": started,
                "completed_at_utc": completed,
                "completed_cases": 2,
                "completed_audio_sec": 120.0,
            }
            serial_host_io_job_rows.append(
                {
                    "configuration_id": serial_configs[serial_ordinal],
                    "development_only": True,
                    "job_id": job_id,
                    "job_kind": group["job_kind"],
                    "identity_sha256": manifest_identity,
                    "mode": mode,
                    "phase_index": group["phase_index"],
                    "serial": True,
                    "split": "development",
                }
            )
            serial_ordinal += 1
    controller_state = {
        "schema_version": "h2-product-program-state.v1",
        "status": "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
        "program_id": "just_peachy_h2_fixture",
        "protocol_id": fixture_protocol_id,
        "protocol_sha256": fixture_protocol_sha256,
        "job_manifest_sha256": "b" * 64,
        "workspace": str(workspace.resolve()),
        "results_root": str((root / "results").resolve()),
        "summary_root": str((root / "summary").resolve()),
        "axis_selections": decisions,
        "jobs": result_rows,
    }
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "program_state.json").write_bytes(_json_bytes(controller_state))
    registry = {
        "default_product_mode": "H2_SESSION_MEMORY_ENHANCED",
        "default_product_mode_selection": {
            "selected_default_mode": "H2_SESSION_MEMORY_ENHANCED",
            "development_only": True,
            "evaluation_material_inspected": False,
            "weighted_composite_used": False,
        },
        "configurations": [
            {
                "configuration_id": "H2_BASELINE_REFERENCE",
                "mode": "H2_SESSION_ANONYMOUS",
                "source_job_id": "baseline_job",
                "source_result_sha256": result_rows["baseline_job"]["result_sha256"],
            },
            {
                "configuration_id": "H2_KNOWN_ONLY_OPTIMIZED",
                "mode": "H2_KNOWN_ONLY",
                "heldout_source_job_id": "known_job",
                "heldout_source_result_sha256": result_rows["known_job"][
                    "result_sha256"
                ],
            },
            {
                "configuration_id": "H2_SESSION_ANONYMOUS_OPTIMIZED",
                "mode": "H2_SESSION_ANONYMOUS",
                "heldout_source_job_id": "anonymous_job",
                "heldout_source_result_sha256": result_rows["anonymous_job"][
                    "result_sha256"
                ],
            },
            {
                "configuration_id": "H2_SESSION_MEMORY_OPTIMIZED",
                "mode": "H2_SESSION_MEMORY_ENHANCED",
                "heldout_source_job_id": "memory_job",
                "heldout_source_result_sha256": result_rows["memory_job"][
                    "result_sha256"
                ],
            },
            {
                "configuration_id": "H2_PORTABLE_ONNX_FP32",
                "mode": "H2_SESSION_MEMORY_ENHANCED",
                "status": (
                    "FROZEN_PORTABLE_CANDIDATE_PARITY_VALIDATED_"
                    "NOT_ARM64_HARDWARE_VALIDATED"
                ),
            },
        ],
    }
    post_promotion_job_id = "post_promotion_integration_job"
    post_promotion_identity = _sha(
        _json_bytes({"fixture_job_id": post_promotion_job_id, "kind": "post_promotion"})
    )
    post_promotion_job_row = {
        "audio_duration_sec": 120.0,
        "case_ids": ["post_promotion_case_1", "post_promotion_case_2"],
        "configuration_id": "H2_POST_PROMOTION_INTEGRATION",
        "development_only": True,
        "identity_sha256": post_promotion_identity,
        "job_id": post_promotion_job_id,
        "job_kind": "post_promotion_integration",
        "mode": "H2_SESSION_MEMORY_ENHANCED",
        "phase_index": 2,
        "phase_name": "REDIM_EXECUTION_FRONTIER",
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "serial": False,
        "split": "development",
    }
    result_rows[post_promotion_job_id] = {
        "state": "COMPLETE",
        "result_path": result_rows["baseline_job"]["result_path"],
        "result_sha256": result_rows["baseline_job"]["result_sha256"],
        "started_at_utc": "2026-08-31T02:41:04.690492Z",
        "completed_at_utc": "2026-08-31T05:00:00.000000Z",
        "completed_cases": 2,
        "completed_audio_sec": 120.0,
    }
    job_manifest_rows = [
        *streaming_job_rows,
        *paragraph_job_rows,
        *boundary_job_rows,
        *overlap_job_rows,
        *science_job_rows,
        *host_io_job_rows,
        *serial_host_io_job_rows,
        post_promotion_job_row,
    ]
    for index, row in enumerate(job_manifest_rows, start=1):
        row.setdefault(
            "identity_sha256",
            _sha(_json_bytes({"fixture_job_id": row["job_id"], "ordinal": index})),
        )
    _write_terminal_storage_fixture(workspace, controller_state, job_manifest_rows)
    _write_host_io_fixture(workspace, controller_state)
    _write_serial_host_io_fixtures(workspace, controller_state, job_manifest_rows)

    payloads: dict[str, bytes] = {}
    for name in REQUIRED_ANALYSIS_FILES:
        payloads[f"summary/{name}"] = f"fixture {name}\n".encode()
    payloads["summary/h2_configuration_registry.yaml"] = _json_bytes(registry)
    payloads["summary/h2_memory_budget.json"] = _json_bytes(
        {
            "analysis_schema_version": "h2-memory-budget-analysis.v1",
            "classification": "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION",
            "desktop_serial_peak_rss_bytes": 300 * 1024 * 1024,
            "arm64_hardware_measured": False,
        }
    )
    payloads["summary/h2_linux_portability.json"] = _json_bytes(
        {
            "schema_version": "h2-linux-portability-analysis.v1",
            "status": "PREPARED_NOT_HARDWARE_VALIDATED",
            "candidate_classification": "PORT_REQUIRES_WORK",
            "linux_arm64_ready_claimed": False,
            "raspberry_pi_hardware_validated": False,
            "arduino_uno_q_linux_hardware_validated": False,
        }
    )
    payloads["summary/h2_long_session_results.csv"] = _long_session_table()
    payloads["protocol/job_manifest.json"] = _json_bytes(
        {
            "job_manifest_sha256": "b" * 64,
            "protocol_id": controller_state["protocol_id"],
            "protocol_sha256": controller_state["protocol_sha256"],
            "jobs": job_manifest_rows,
        }
    )
    payloads["protocol/protocol_manifest.json"] = (
        workspace / "protocol_manifest.json"
    ).read_bytes()
    arm64_root = Path(__file__).resolve().parents[1] / "deployment/h2_arm64"
    arm64_component_rows: dict[str, str] = {}
    for name in ARM64_PACKAGE_FILES:
        member = f"deployment/h2_arm64/{name}"
        payloads[member] = (arm64_root / name).read_bytes()
        arm64_component_rows[
            f"Software Validation from Datasets/Evaluation Tool/{member}"
        ] = _sha(payloads[member])
    assert (
        payloads[ARM64_REQUIREMENTS_MEMBER]
        == (arm64_root / "requirements-linux-arm64.txt").read_bytes()
    )
    arm64_component_sha = canonical_sha256(arm64_component_rows)
    packaged_runtime_identity = json.loads(
        (workspace / "runtime_implementation_identity.json").read_bytes()
    )
    assert (
        packaged_runtime_identity["components"]["h2_arm64_deployment_bundle"]
        == arm64_component_sha
    )
    payloads[RUNTIME_IDENTITY_MEMBER] = _json_bytes(packaged_runtime_identity)
    _write_selector_correction_packaging_fixture(
        workspace, payloads, controller_state, result_rows
    )
    payloads.update(_plot_tables())
    packaged_controller_state = {**controller_state, "status": "RUNNING"}
    payloads["controller/program_state.json"] = _json_bytes(packaged_controller_state)
    rows = [
        {
            "member": name,
            "category": "fixture",
            "bytes": len(payload),
            "sha256": _sha(payload),
        }
        for name, payload in sorted(payloads.items())
    ]
    manifest = {
        "schema_version": "h2-compact-package-manifest.v1",
        "status": "VALIDATED_BY_COLLECTION_BEFORE_ZIP_PUBLICATION",
        "member_count_excluding_metadata": len(rows),
        "member_inventory_sha256": canonical_sha256(rows),
        "members": rows,
    }
    payloads["PACKAGE_MANIFEST.json"] = _json_bytes(manifest)
    payloads["PACKAGE_CHECKSUMS.json"] = _json_bytes(
        {
            "schema_version": "h2-compact-package-checksums.v1",
            "files": {
                name: {"sha256": _sha(payload), "bytes": len(payload)}
                for name, payload in sorted(payloads.items())
            },
        }
    )
    destination = root / "h2_complete_product_pipeline_fixture.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(payloads.items()):
            archive.writestr(name, payload)
    assert validate_package_zip(destination)["status"] == "VALID"
    return destination


def test_build_plots_uses_only_computed_final_metrics() -> None:
    plots, provenance = build_plots(_plot_tables())
    assert len([name for name in plots if name.endswith(".svg")]) == 5
    assert "plots/PLOT_GUIDE.md" in plots
    assert len(provenance) == 5
    assert all(row["source_members"] for row in provenance)
    assert all(b"<svg" in plots[str(row["member"])] for row in provenance)


def test_hardware_assessment_requires_measured_storage_metrics() -> None:
    payloads = _plot_tables()
    resource_rows = list(
        csv.DictReader(
            io.StringIO(payloads["summary/h2_resource_results.csv"].decode("utf-8"))
        )
    )
    payloads["summary/h2_resource_results.csv"] = _csv_payload(
        [row for row in resource_rows if row["metric_id"] != "model_bytes"]
    )
    payloads["summary/h2_configuration_registry.yaml"] = _json_bytes(
        {"configurations": []}
    )
    payloads["summary/h2_memory_budget.json"] = _json_bytes(
        {
            "analysis_schema_version": "h2-memory-budget-analysis.v1",
            "classification": "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION",
            "desktop_serial_peak_rss_bytes": 300 * 1024 * 1024,
            "arm64_hardware_measured": False,
        }
    )
    payloads["summary/h2_linux_portability.json"] = _json_bytes(
        {
            "schema_version": "h2-linux-portability-analysis.v1",
            "raspberry_pi_hardware_validated": False,
            "arduino_uno_q_linux_hardware_validated": False,
        }
    )
    with pytest.raises(ValueError, match="model-byte, and cache-byte measurements"):
        build_hardware_platform_assessment(payloads)


def test_serial_host_io_uses_checksum_bound_quiet_phase2_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    source = _write_native_package(tmp_path, workspace)
    with zipfile.ZipFile(source) as archive:
        native_payloads = {name: archive.read(name) for name in archive.namelist()}
    _write_phase2_quiet_replay_fixture(
        tmp_path, workspace, native_payloads, monkeypatch
    )

    additions, provenance = _serial_host_io_payloads(workspace, native_payloads)

    assert set(additions) == (
        set(REQUIRED_SERIAL_HOST_IO_MEMBERS) | set(REQUIRED_PHASE2_QUIET_REPLAY_MEMBERS)
    )
    assert provenance["schema_version"] == ("h2-serial-host-io-package-provenance.v2")
    assert provenance["quiet_replay_group_count"] == 1
    assert provenance["receipt_evidence"][0]["evidence_origin"] == "quiet_replay"
    assert provenance["receipt_evidence"][1]["evidence_origin"] == "main_campaign"
    assert (
        json.loads(additions[PHASE2_ORIGINAL_CONTAMINATED_RECEIPT_MEMBER])["status"]
        == "SERIAL_RESOURCE_HOST_IO_CONTAMINATED"
    )
    assert (
        json.loads(additions[SERIAL_HOST_IO_RECEIPT_MEMBERS[0]])["status"]
        == "SERIAL_RESOURCE_HOST_IO_CLEAR"
    )
    packaged_manifest = json.loads(additions[PHASE2_QUIET_REPLAY_MANIFEST_MEMBER])
    assert packaged_manifest["host_paths_redacted"] is True
    assert packaged_manifest["source_workspace"] == "%SOURCE_WORKSPACE%"

    validator_payloads = {
        **native_payloads,
        HOST_IO_COLLECTOR_MEMBER: (
            final_package_module.TOOL_ROOT
            / "scripts/capture_h2_host_io_interference.ps1"
        ).read_bytes(),
        **additions,
    }
    assert _validate_serial_host_io_members(validator_payloads) == provenance

    tampered = dict(validator_payloads)
    comparison = json.loads(tampered[PHASE2_QUIET_REPLAY_COMPARISON_MEMBER])
    comparison["jobs"][SERIAL_HOST_IO_GROUPS[0]["job_ids"][0]]["total_rtf"] = 99.0
    tampered[PHASE2_QUIET_REPLAY_COMPARISON_MEMBER] = _json_bytes(comparison)
    with pytest.raises(ValueError, match="inventory/checksum differs"):
        _validate_serial_host_io_members(tampered)


def test_serial_host_io_fails_closed_without_clean_phase2_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    source = _write_native_package(tmp_path, workspace)
    with zipfile.ZipFile(source) as archive:
        native_payloads = {name: archive.read(name) for name in archive.namelist()}
    phase2 = SERIAL_HOST_IO_GROUPS[0]
    receipt_path = (
        workspace / "diagnostics/host_io_interference" / str(phase2["receipt_filename"])
    )
    receipt = json.loads(receipt_path.read_bytes())
    receipt["status"] = "SERIAL_RESOURCE_HOST_IO_CONTAMINATED"
    receipt["scientific_interpretation"]["resource_comparison_eligible"] = False
    receipt_path.write_bytes(_json_bytes(receipt))

    actual_tool_root = Path(__file__).resolve().parents[1]
    empty_tool_root = tmp_path / "empty_tool_root"
    script_root = empty_tool_root / "scripts"
    script_root.mkdir(parents=True)
    for name in (
        "capture_h2_host_io_interference.ps1",
        "watch_h2_serial_resource_io.ps1",
    ):
        (script_root / name).write_bytes(
            (actual_tool_root / "scripts" / name).read_bytes()
        )
    monkeypatch.setattr(final_package_module, "TOOL_ROOT", empty_tool_root)

    with pytest.raises(ValueError, match="is not clear"):
        _serial_host_io_payloads(workspace, native_payloads)


def test_augmenter_direct_script_launch_resolves_tool_imports() -> None:
    tool_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(tool_root / "scripts/augment_h2_final_package.py"),
            "--help",
        ],
        cwd=tool_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30.0,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--source-zip" in completed.stdout


def test_focused_required_metrics_match_frozen_product_v2_definitions() -> None:
    references = parse_rttm(
        "\n".join(
            (
                "SPEAKER source 1 0.000000 1.000000 <NA> <NA> SPK00 <NA> <NA>",
                "SPEAKER source 1 0.500000 1.000000 <NA> <NA> SPK01 <NA> <NA>",
            )
        ),
        from_text=True,
    )
    hypotheses = parse_rttm(
        "\n".join(
            (
                "SPEAKER case 1 0.000000 1.500000 <NA> <NA> anon_long <NA> <NA>",
                "SPEAKER case 1 0.750000 0.250000 <NA> <NA> anon_nested <NA> <NA>",
            )
        ),
        from_text=True,
    )
    case = {
        "duration_sec": 1.5,
        "local_to_global_speaker": {"SPK00": "global_0", "SPK01": "global_1"},
    }

    expected = _case_product_metrics(case, references, hypotheses)
    observed = _focused_case_events(case, references, hypotheses)

    assert [
        (
            row["predicted_cluster"],
            row["dominant_global_speaker_id"],
            row["predicted_duration_sec"],
            row["dominant_reference_fraction"],
        )
        for row in observed["contamination"]
    ] == [
        (
            row["predicted_cluster"],
            row["dominant_global_speaker_id"],
            row["predicted_duration_sec"],
            row["dominant_reference_fraction"],
        )
        for row in expected["contamination"]
    ]
    assert observed["short_turns"] == [
        {
            "global_speaker_id": row["global_speaker_id"],
            "duration_sec": row["duration_sec"],
            "anonymous_speaker_correctness": row["anonymous_speaker_correctness"],
        }
        for row in expected["short_turns"]
    ]
    for name in ("evidence", "latency"):
        expected_rows = [
            {key: row[key] for key in observed_row}
            for row, observed_row in zip(expected[name], observed[name], strict=True)
        ]
        assert observed[name] == expected_rows


@pytest.mark.parametrize(
    "policy",
    (
        "T1_ASR_ENDPOINT_PUNCTUATION",
        "T2_PAUSE_ASR_ENDPOINT",
        "T3_PAUSE_ASR_SPEAKER_CHANGE",
        "T4_SPEAKER_CHANGE_DOMINANT",
    ),
)
def test_paragraph_replay_matches_frozen_paragraph_manager(policy: str) -> None:
    rows = [
        {
            "anonymous_speaker_id": "anon_0",
            "end_sec": 0.5,
            "span_id": "span_0",
            "speaker_label": "Speaker_1",
            "start_sec": 0.0,
            "state": "final",
            "text": "One.",
        },
        {
            "anonymous_speaker_id": "anon_0",
            "end_sec": 1.2,
            "span_id": "span_1",
            "speaker_label": "Speaker_1",
            "start_sec": 1.0,
            "state": "final",
            "text": "Two",
        },
        {
            "anonymous_speaker_id": "anon_1",
            "end_sec": 2.2,
            "span_id": "span_2",
            "speaker_label": "Speaker_2",
            "start_sec": 2.0,
            "state": "final",
            "text": "Three!",
        },
    ]
    expected = build_paragraphs(
        [SimpleNamespace(**row) for row in rows],
        policy=policy,
        pause_sec=0.8,
        maximum_words=80,
    )
    observed = _paragraph_groups(
        rows,
        policy=policy,
        pause_sec=0.8,
        maximum_words=80,
    )

    assert [(paragraph.span_ids, paragraph.break_reason) for paragraph in expected] == [
        (
            tuple(str(span["span_id"]) for span in group["spans"]),
            group["break_reason"],
        )
        for group in observed
    ]


def test_structural_revision_excludes_append_and_normalizes_display_label() -> None:
    first = {
        "anonymous_speaker_id": "anon_0",
        "end_sec": 1.0,
        "span_id": "span_0",
        "speaker_label": {"display_label": "Speaker_1", "label_kind": "unknown"},
        "start_sec": 0.0,
        "state": "final",
        "text": "hello",
    }
    second = {
        "anonymous_speaker_id": "anon_0",
        "end_sec": 2.0,
        "span_id": "span_1",
        "speaker_label": "Speaker_1",
        "start_sec": 1.0,
        "state": "final",
        "text": "world",
    }
    previous = _paragraph_groups(
        [first],
        policy="T3_PAUSE_ASR_SPEAKER_CHANGE",
        pause_sec=0.8,
        maximum_words=80,
    )
    appended = _paragraph_groups(
        [{**first, "speaker_label": "Speaker_1"}, second],
        policy="T3_PAUSE_ASR_SPEAKER_CHANGE",
        pause_sec=0.8,
        maximum_words=80,
    )
    assert not _paragraph_structure_revised(previous, appended)

    split = [
        {"spans": (appended[0]["spans"][0],), "break_reason": "session_start"},
        {"spans": (appended[0]["spans"][1],), "break_reason": "speaker_change"},
    ]
    assert _paragraph_structure_revised(appended, split)


def test_augment_package_preserves_native_members_and_self_validates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ReusableReport:
        reusable = True
        issues: tuple[object, ...] = ()

    monkeypatch.setattr(
        "scripts.augment_h2_final_package.validate_result_tree",
        lambda _root: _ReusableReport(),
    )
    workspace = tmp_path / "workspace"
    source = _write_native_package(tmp_path, workspace)
    source_sha = _sha(source.read_bytes())
    output = tmp_path / "h2_complete_product_pipeline_fixture_with_plots.zip"

    with zipfile.ZipFile(source) as archive:
        native_payloads = {name: archive.read(name) for name in archive.namelist()}
    arm64_v2, arm64_v2_provenance = build_arm64_deployment_v2(native_payloads)
    assert set(arm64_v2) == set(REQUIRED_ARM64_V2_MEMBERS)
    assert arm64_v2_provenance["status"] == "PREPARED_NOT_HARDWARE_VALIDATED"
    assert arm64_v2_provenance["source_native_members_preserved"] is True
    assert arm64_v2_provenance["scientific_runtime_or_policy_changed"] is False
    assert arm64_v2_provenance["arm64_hardware_validated"] is False
    assert (
        b'WorkingDirectory="/opt/just-peachy/Software Validation'
        in arm64_v2["deployment/h2_arm64_v2/h2-pipeline.service"]
    )
    assert (
        arm64_v2["deployment/h2_arm64_v2/install_linux_arm64.sh"].count(
            b"${PIP_SOURCE[@]}"
        )
        == 2
    )
    asr_additions, asr_provenance = build_asr_wer_comparability_supplement(
        native_payloads, workspace
    )
    assert set(asr_additions) == set(REQUIRED_ASR_COMPARABILITY_MEMBERS)
    assert asr_provenance["status"] == "VALID"
    assert asr_provenance["schema_version"] == "h2-asr-wer-comparability-provenance.v2"
    assert asr_provenance["source_reported_frozen_metrics_recomputed_exactly"]
    assert asr_provenance["punctuation_diagnostics"][
        "reference_and_hypothesis_punctuation_token_rates_reported"
    ]
    assert not asr_provenance["punctuation_diagnostics"][
        "scientific_selection_eligible"
    ]
    host_io_additions, host_io_provenance = _host_io_payloads(
        workspace, native_payloads
    )
    assert set(host_io_additions) == set(REQUIRED_HOST_IO_MEMBERS)
    assert host_io_provenance["status"] == "VALID"
    assert host_io_provenance["accuracy_metrics_eligible"] is True
    assert host_io_provenance["resource_comparison_eligible"] is False
    serial_host_io_additions, serial_host_io_provenance = _serial_host_io_payloads(
        workspace, native_payloads
    )
    assert set(serial_host_io_additions) == set(REQUIRED_SERIAL_HOST_IO_MEMBERS)
    assert serial_host_io_provenance["status"] == "VALID"
    assert serial_host_io_provenance["job_count"] == 5
    assert serial_host_io_provenance["all_serial_resource_receipts_clear"] is True
    assert serial_host_io_provenance["resource_comparison_eligible"] is True
    hardware_additions, hardware_provenance = build_hardware_platform_assessment(
        native_payloads
    )
    assert set(hardware_additions) == set(REQUIRED_HARDWARE_PLATFORM_MEMBERS)
    assert hardware_provenance["status"] == (
        "EXPECTED_FEASIBILITY_NOT_HARDWARE_VALIDATION"
    )
    assert hardware_provenance["arm64_hardware_measurements_present"] is False
    assert hardware_provenance["desktop_scientific_ranking_changed"] is False
    assert hardware_provenance["qnn_debian_acceleration_claimed"] is False
    assert hardware_provenance["official_source_urls"][
        "arduino_uno_q_datasheet"
    ].endswith("ABX00162-datasheet.pdf")
    assert (
        "raspberrypi.com"
        in hardware_provenance["official_source_urls"][
            "raspberry_pi_5_sustained_load_cooling"
        ]
    )
    assert any(
        "active-cooling behavior" in item
        for item in hardware_provenance["remaining_target_tests"]
    )
    assert (
        b"uncooled burst result"
        in hardware_additions["supplements/H2_HARDWARE_PLATFORM_ASSESSMENT.md"]
    )
    assert hardware_provenance["measured_desktop_bounds"]["model_bytes"] == (
        600 * 1024 * 1024
    )
    assert hardware_provenance["measured_desktop_bounds"]["cache_bytes"] == (
        150 * 1024 * 1024
    )
    hardware_by_variant = {
        (row["platform_id"], row["variant"]): row
        for row in hardware_provenance["platforms"]
    }
    assert len(hardware_by_variant) == 4
    assert (
        hardware_by_variant[("RASPBERRY_PI_COMPUTE_MODULE_5", "2GB_RAM")][
            "expected_classification"
        ]
        == "PORT_REQUIRES_WORK"
    )
    assert (
        hardware_by_variant[("RASPBERRY_PI_COMPUTE_MODULE_5", "2GB_RAM")][
            "recommended_role"
        ]
        == "FIRST_LEAN_ARM64_SIZING_TARGET"
    )
    assert (
        hardware_by_variant[("RASPBERRY_PI_COMPUTE_MODULE_5", "4GB_OR_GREATER")][
            "expected_classification"
        ]
        == "LIKELY_PORTABLE"
    )
    assert (
        hardware_by_variant[("RASPBERRY_PI_COMPUTE_MODULE_5", "4GB_OR_GREATER")][
            "recommended_role"
        ]
        == "SAFE_FALLBACK_AND_DEVELOPMENT_TARGET"
    )
    assert hardware_provenance["decision"]["cm5_2gb_candidate"] is True
    assert hardware_provenance["decision"]["cm5_4gb_proven_necessary"] is False
    assert hardware_provenance["decision"]["cm5_ram_recommendation"] == (
        "TEST_2GB_LEAN_ONNX_FIRST_WITH_4GB_FALLBACK"
    )
    assert hardware_provenance["decision"]["sizing_workload_driver"] == (
        "AUDIO_PIPELINE_MODELS_QUEUES_AND_RUNTIME"
    )
    assert (
        hardware_by_variant[("ARDUINO_UNO_Q", "4GB_RAM_32GB_EMMC")][
            "expected_classification"
        ]
        == "PORT_REQUIRES_WORK"
    )
    assert (
        hardware_by_variant[("ARDUINO_UNO_Q", "2GB_RAM_16GB_EMMC")][
            "expected_classification"
        ]
        == "PLATFORM_BLOCKER"
    )
    assert (
        hardware_by_variant[("ARDUINO_UNO_Q", "2GB_RAM_16GB_EMMC")][
            "native_pipeline_feasibility"
        ]
        == "PLATFORM_BLOCKER"
    )
    assert all(
        str(row["storage_feasibility"]).strip()
        for row in hardware_provenance["platforms"]
    )
    hardware_markdown = hardware_additions[
        "supplements/H2_HARDWARE_PLATFORM_ASSESSMENT.md"
    ].decode("utf-8")
    assert "## Platform detail" in hardware_markdown
    assert "Measured checksum-bound model-asset footprint" in hardware_markdown
    assert "Measured desktop run-cache footprint" in hardware_markdown
    assert "## CM5 2GB versus 4GB RAM decision" in hardware_markdown
    assert "simple 2D transcript/status UI" in hardware_markdown
    assert "4GB is not declared necessary" in hardware_markdown
    assert "- **Storage:** 32GB eMMC" in hardware_markdown
    assert "- **Audio:**" in hardware_markdown
    assert "- **Display:**" in hardware_markdown
    streaming_additions, streaming_provenance = build_streaming_execution_provenance(
        native_payloads
    )
    assert set(streaming_additions) == set(REQUIRED_STREAMING_PROVENANCE_MEMBERS)
    assert streaming_provenance["status"] == "VALIDATED_SCOPE_DISCLOSURE"
    streaming_qualification = streaming_provenance["qualification"]
    assert streaming_qualification["classification"] == (
        "NATIVE_TRACE_REPLAY_QUALIFICATION"
    )
    assert streaming_qualification["asr_execution_origins"] == {
        "accuracy_replayed_case_count": 1,
        "primary_computed_case_count": 0,
        "snapshot_counts": {"accuracy_replayed": 2},
        "worker_started_case_count": 0,
    }
    assert streaming_qualification["physical_microphone_used"] is False
    assert streaming_qualification["real_time_1x_pacing_used"] is False
    assert streaming_qualification["resource_comparison_eligible"] is False
    fresh_resource_rows = streaming_provenance["fresh_decode_serial_resource_evidence"]
    assert {
        row["configuration_id"]: row["mode"] for row in fresh_resource_rows
    } == STREAMING_FRESH_RESOURCE_CONFIGURATIONS
    assert all(
        row["classification"] == "FRESH_NATIVE_DECODE_SERIAL_RESOURCE"
        and row["asr_stream_trace_enabled"] is False
        and row["serial_execution"] is True
        and row["resource_comparison_eligible"] is True
        for row in fresh_resource_rows
    )

    receipt = augment_package(source, workspace, output)

    assert source.is_file()
    assert _sha(source.read_bytes()) == source_sha
    assert receipt["status"] == "VALID"
    assert receipt["upload_path"] == str(output.resolve())
    assert Path(str(receipt["receipt_path"])).is_file()
    validation = validate_augmented_package(output)
    assert validation["status"] == "VALID"
    assert validation["plot_count"] == 5
    assert validation["hardware_platform_count"] == 4
    assert validation["streaming_qualification_case_count"] == 1
    second = tmp_path / "second_with_plots.zip"
    second_receipt = augment_package(source, workspace, second)
    assert second_receipt["sha256"] == receipt["sha256"]
    assert second.read_bytes() == output.read_bytes()
    with zipfile.ZipFile(source) as native, zipfile.ZipFile(output) as augmented:
        for name in native.namelist():
            assert augmented.read(name) == native.read(name)
        assert (
            "controller/axis_selections/boundary_correction.json"
            in augmented.namelist()
        )
        assert "controller/axis_selections/overlap_policy.json" in augmented.namelist()
        assert all(name in augmented.namelist() for name in REQUIRED_METRIC_MEMBERS)
        assert all(
            name in augmented.namelist()
            for name in REQUIRED_SELECTOR_CORRECTION_MEMBERS
        )
        assert all(name in augmented.namelist() for name in REQUIRED_ARM64_V2_MEMBERS)
        packaged_arm64_v2 = json.loads(augmented.read(ARM64_V2_PROVENANCE_MEMBER))
        assert packaged_arm64_v2["deployment_only_supersession"] is True
        assert packaged_arm64_v2["linux_arm64_ready_claimed"] is False
        assert all(name in augmented.namelist() for name in REQUIRED_TRANSCRIPT_MEMBERS)
        assert all(
            name in augmented.namelist() for name in REQUIRED_ASR_COMPARABILITY_MEMBERS
        )
        assert all(name in augmented.namelist() for name in REQUIRED_HOST_IO_MEMBERS)
        assert all(
            name in augmented.namelist() for name in REQUIRED_SERIAL_HOST_IO_MEMBERS
        )
        assert all(
            name in augmented.namelist()
            for name in REQUIRED_STREAMING_PROVENANCE_MEMBERS
        )
        packaged_streaming_payloads = {
            name: augmented.read(name) for name in REQUIRED_STREAMING_PROVENANCE_MEMBERS
        }
        packaged_streaming = _validate_streaming_execution_provenance_members(
            packaged_streaming_payloads
        )
        assert packaged_streaming["qualification"]["classification"] == (
            "NATIVE_TRACE_REPLAY_QUALIFICATION"
        )
        altered_streaming = dict(packaged_streaming_payloads)
        altered_document = json.loads(
            altered_streaming[REQUIRED_STREAMING_PROVENANCE_MEMBERS[1]]
        )
        altered_document["qualification"]["physical_microphone_used"] = True
        altered_streaming[REQUIRED_STREAMING_PROVENANCE_MEMBERS[1]] = _json_bytes(
            altered_document
        )
        with pytest.raises(
            ValueError, match="streaming qualification scope disclosure differs"
        ):
            _validate_streaming_execution_provenance_members(altered_streaming)
        packaged_host_io_provenance = json.loads(
            augmented.read(HOST_IO_PROVENANCE_MEMBER)
        )
        assert packaged_host_io_provenance["candidate_checksum_count"] == 96
        assert packaged_host_io_provenance["dropped_frames_total"] == 0
        assert packaged_host_io_provenance["accuracy_metrics_eligible"] is True
        assert packaged_host_io_provenance["resource_comparison_eligible"] is False
        host_io_payloads = {
            name: augmented.read(name)
            for name in augmented.namelist()
            if name in REQUIRED_HOST_IO_MEMBERS
            or name
            in {
                "controller/program_state.json",
                "protocol/job_manifest.json",
            }
        }
        assert _validate_host_io_members(host_io_payloads)["status"] == "VALID"
        altered_host_io = dict(host_io_payloads)
        altered_receipt = json.loads(altered_host_io[HOST_IO_RECEIPT_MEMBER])
        altered_receipt["correlation"]["per_job"][-1][
            "maximum_esent_reported_io_sec"
        ] = 5.0
        altered_host_io[HOST_IO_RECEIPT_MEMBER] = _json_bytes(altered_receipt)
        with pytest.raises(
            ValueError, match="host-I/O per-job timestamp correlation differs"
        ):
            _validate_host_io_members(altered_host_io)
        serial_host_io_payloads = {
            name: augmented.read(name)
            for name in augmented.namelist()
            if name in REQUIRED_SERIAL_HOST_IO_MEMBERS
            or name
            in {
                HOST_IO_COLLECTOR_MEMBER,
                "controller/program_state.json",
                "protocol/job_manifest.json",
            }
        }
        assert (
            _validate_serial_host_io_members(serial_host_io_payloads)["status"]
            == "VALID"
        )
        altered_serial = dict(serial_host_io_payloads)
        altered_receipt = json.loads(altered_serial[SERIAL_HOST_IO_RECEIPT_MEMBERS[0]])
        altered_receipt["status"] = "SERIAL_RESOURCE_HOST_IO_CONTAMINATED"
        altered_receipt["scientific_interpretation"]["resource_comparison_eligible"] = (
            False
        )
        altered_serial[SERIAL_HOST_IO_RECEIPT_MEMBERS[0]] = _json_bytes(altered_receipt)
        with pytest.raises(ValueError, match="is not clear"):
            _validate_serial_host_io_members(altered_serial)
        asr_rows = list(
            csv.DictReader(
                io.StringIO(
                    augmented.read(REQUIRED_ASR_COMPARABILITY_MEMBERS[0]).decode(
                        "utf-8"
                    )
                )
            )
        )
        assert len(asr_rows) == 52
        assert {row["configuration_id"] for row in asr_rows} == {
            "H2_BASELINE_REFERENCE",
            "H2_KNOWN_ONLY_OPTIMIZED",
            "H2_SESSION_ANONYMOUS_OPTIMIZED",
            "H2_SESSION_MEMORY_OPTIMIZED",
        }
        assert {
            row["scoring_policy_id"]
            for row in asr_rows
            if row["metric_role"] == "CROSS_PROTOCOL_ASR_COMPARABILITY"
        } == {"evaluation-text-normalization-punctuation-insensitive.v1"}
        assert all(row["scientific_selection_eligible"] == "False" for row in asr_rows)
        assert {row["schema_version"] for row in asr_rows} == {
            "h2-asr-wer-comparability-row.v2"
        }
        for configuration_id in {row["configuration_id"] for row in asr_rows}:
            frozen = next(
                row
                for row in asr_rows
                if row["configuration_id"] == configuration_id
                and row["scoring_policy_id"] == "lowercase_whitespace.v1"
                and row["stratum"] == "OVERALL"
            )
            comparable = next(
                row
                for row in asr_rows
                if row["configuration_id"] == configuration_id
                and row["scoring_policy_id"]
                == "evaluation-text-normalization-punctuation-insensitive.v1"
                and row["stratum"] == "OVERALL"
            )
            assert float(
                comparable["punctuation_sensitive_minus_insensitive_wer"]
            ) == pytest.approx(float(frozen["value"]) - float(comparable["value"]))
            assert (
                0.0
                <= float(comparable["reference_ascii_punctuation_token_rate"])
                <= 1.0
            )
            hypothesis_rate = comparable["hypothesis_ascii_punctuation_token_rate"]
            if hypothesis_rate:
                assert 0.0 <= float(hypothesis_rate) <= 1.0
        assert all(
            row["metric_role"] == "ENDPOINT_WINDOW_DIAGNOSTIC_NOT_ORDINARY_WER"
            for row in asr_rows
            if row["metric_id"] == "final_wer"
        )
        assert all(name in augmented.namelist() for name in REQUIRED_OVERLAP_MEMBERS)
        assert all(name in augmented.namelist() for name in REQUIRED_BOUNDARY_MEMBERS)
        assert all(
            name in augmented.namelist() for name in REQUIRED_SCIENCE_TABLE_MEMBERS
        )
        assert all(
            name in augmented.namelist() for name in REQUIRED_RECOMMENDATION_MEMBERS
        )
        assert all(
            name in augmented.namelist() for name in REQUIRED_HARDWARE_PLATFORM_MEMBERS
        )
        hardware_platforms = json.loads(
            augmented.read(REQUIRED_HARDWARE_PLATFORM_MEMBERS[2])
        )
        assert hardware_platforms["desktop_scientific_ranking_changed"] is False
        assert hardware_platforms["qnn_debian_acceleration_claimed"] is False
        assert len(hardware_platforms["platforms"]) == 4
        assert hardware_platforms["decision"]["cm5_2gb_candidate"] is True
        assert hardware_platforms["decision"]["cm5_4gb_proven_necessary"] is False
        recommendations = json.loads(augmented.read(REQUIRED_RECOMMENDATION_MEMBERS[0]))
        assert [row["role"] for row in recommendations["roles"]] == [
            "DESKTOP_REFERENCE",
            "PRODUCT_SOFTWARE_PRIMARY",
            "2GB_ARM64_CANDIDATE",
        ]
        assert recommendations["roles"][1]["configuration_id"] == (
            "H2_SESSION_MEMORY_OPTIMIZED"
        )
        assert recommendations["roles"][2]["recommendation_status"] == (
            "PREPARED_NOT_HARDWARE_VALIDATED"
        )
        assert recommendations["roles"][2]["deployment_bundle_prefix"] == (
            "deployment/h2_arm64_v2/"
        )
        assert all(
            name in augmented.namelist() for name in REQUIRED_LONG_SESSION_DRIFT_MEMBERS
        )
        drift_rows = list(
            csv.DictReader(
                io.StringIO(
                    augmented.read(REQUIRED_LONG_SESSION_DRIFT_MEMBERS[0]).decode(
                        "utf-8"
                    )
                )
            )
        )
        assert len(drift_rows) == 12 * len(LONG_SESSION_DRIFT_METRICS)
        assert {row["split"] for row in drift_rows} == {
            "development",
            "evaluation",
        }
        assert {row["metric_id"] for row in drift_rows} == {
            row[0] for row in LONG_SESSION_DRIFT_METRICS
        }
        assert all(name in augmented.namelist() for name in REQUIRED_STORAGE_MEMBERS)
        assert all(name in augmented.namelist() for name in REQUIRED_UI_LATENCY_MEMBERS)
        assert all(
            name in augmented.namelist() for name in REQUIRED_DATA_FIREWALL_MEMBERS
        )
        assert all(
            name in augmented.namelist()
            for name in REQUIRED_DEVELOPMENT_CPU_INTERFERENCE_MEMBERS
        )
        firewall_payloads = {
            name: augmented.read(name)
            for name in augmented.namelist()
            if name
            in {
                "protocol/protocol_manifest.json",
                RUNTIME_IDENTITY_MEMBER,
            }
            or name in REQUIRED_DATA_FIREWALL_MEMBERS
        }
        firewall_provenance = _validate_data_firewall_members(firewall_payloads)
        assert firewall_provenance["status"] == "VALID"
        assert firewall_provenance["heldout_queue_unopened_at_audit"] is True
        assert firewall_provenance["source_manifests_embedded"] is False
        cpu_payloads = {
            name: augmented.read(name)
            for name in augmented.namelist()
            if name
            in {
                "protocol/protocol_manifest.json",
                "protocol/job_manifest.json",
                RUNTIME_IDENTITY_MEMBER,
            }
            or name in REQUIRED_DEVELOPMENT_CPU_INTERFERENCE_MEMBERS
        }
        cpu_provenance = _validate_development_cpu_interference_members(cpu_payloads)
        assert cpu_provenance["status"] == "VALID_DISCLOSED_TIMING_INELIGIBLE"
        assert (
            cpu_provenance["timing_and_resource_fields_eligible_as_clean_evidence"]
            is False
        )
        assert cpu_provenance["clean_resource_replay_required"] is True
        ui_payloads = {
            name: augmented.read(name)
            for name in augmented.namelist()
            if name == RUNTIME_IDENTITY_MEMBER or name in REQUIRED_UI_LATENCY_MEMBERS
        }
        ui_provenance = _validate_ui_latency_members(ui_payloads)
        assert ui_provenance["status"] == "VALID"
        assert ui_provenance["sample_count"] == 2
        ui_summary_rows = list(
            csv.DictReader(
                io.StringIO(
                    augmented.read(
                        "supplements/h2_controlled_ui_event_latency.csv"
                    ).decode("utf-8")
                )
            )
        )
        assert len(ui_summary_rows) == 8
        assert {row["metric_id"] for row in ui_summary_rows} >= {
            "median_ms",
            "p95_ms",
            "maximum_ms",
        }
        native_state = json.loads(native.read("controller/program_state.json"))
        terminal_state = json.loads(augmented.read(REQUIRED_STORAGE_MEMBERS[-2]))
        assert native_state["status"] == "RUNNING"
        assert terminal_state["status"] == "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
        storage_provenance = json.loads(augmented.read(REQUIRED_STORAGE_MEMBERS[-1]))
        assert storage_provenance["native_packaged_controller_status"] == "RUNNING"
        assert storage_provenance["controller_state_transition_preserved"] is True
        assert storage_provenance["queue_attempt_history_row_count"] == 3
        assert storage_provenance["noncomplete_attempt_count"] == 2
        assert storage_provenance["recovered_noncomplete_attempt_count"] == 2
        attempts = list(
            csv.DictReader(
                io.StringIO(
                    augmented.read(
                        "reproducibility/storage/queue_attempt_history.csv"
                    ).decode("utf-8")
                )
            )
        )
        assert attempts[0]["attempt_state"] == "failed"
        assert attempts[0]["final_job_state"] == "complete"
        assert attempts[0]["recovered_after_attempt"] == "True"
        assert attempts[1]["attempt_state"] == "failed"
        assert attempts[1]["error"] == "transient Windows status publication lock"
        assert attempts[1]["recovered_after_attempt"] == "True"
        assert attempts[2]["attempt_state"] == "complete"
        storage_payloads = {
            name: augmented.read(name)
            for name in augmented.namelist()
            if name
            in {
                "controller/program_state.json",
                ARM64_REQUIREMENTS_MEMBER,
                RUNTIME_IDENTITY_MEMBER,
            }
            or name.startswith("reproducibility/storage/")
        }
        attempts[0]["recovered_after_attempt"] = "False"
        output_text = io.StringIO(newline="")
        writer = csv.DictWriter(
            output_text, fieldnames=tuple(attempts[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(attempts)
        altered_attempt_payload = output_text.getvalue().encode("utf-8")
        attempt_member = "reproducibility/storage/queue_attempt_history.csv"
        storage_payloads[attempt_member] = altered_attempt_payload
        storage_provenance["queue_attempt_history_sha256"] = _sha(
            altered_attempt_payload
        )
        storage_provenance["recovered_noncomplete_attempt_count"] = 1
        storage_provenance["queue_databases"][0][
            "recovered_noncomplete_attempt_count"
        ] = 1
        source_row = next(
            row
            for row in storage_provenance["source_members"]
            if row["member"] == attempt_member
        )
        source_row["sha256"] = _sha(altered_attempt_payload)
        source_row["bytes"] = len(altered_attempt_payload)
        storage_payloads[REQUIRED_STORAGE_MEMBERS[-1]] = _json_bytes(storage_provenance)
        with pytest.raises(ValueError, match="recovery classification"):
            _validate_storage_reproducibility_members(storage_payloads)
        assert "AUGMENTED_PACKAGE_MANIFEST.json" in augmented.namelist()
        assert "AUGMENTED_PACKAGE_CHECKSUMS.json" in augmented.namelist()


def test_development_cpu_interference_disclosure_rejects_tampering(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    source = _write_native_package(tmp_path, workspace)
    with zipfile.ZipFile(source) as archive:
        native_payloads = {name: archive.read(name) for name in archive.namelist()}
    additions, provenance = _development_cpu_interference_payloads(
        workspace, native_payloads
    )
    payloads = {**native_payloads, **additions}
    assert _validate_development_cpu_interference_members(payloads) == provenance

    receipt_member = REQUIRED_DEVELOPMENT_CPU_INTERFERENCE_MEMBERS[0]
    receipt = json.loads(payloads[receipt_member])
    receipt["scientific_interpretation"][
        "timing_and_resource_fields_eligible_as_clean_evidence"
    ] = True
    payloads[receipt_member] = _json_bytes(receipt)
    with pytest.raises(ValueError, match="signature differs"):
        _validate_development_cpu_interference_members(payloads)


def _write_selector_correction_packaging_fixture(
    workspace: Path,
    payloads: dict[str, bytes],
    controller_state: dict[str, object],
    result_rows: dict[str, dict[str, object]],
) -> None:
    staging = workspace / "diagnostics/pre_freeze_selector_fix_staging"
    staging.mkdir(parents=True, exist_ok=True)
    conflict_path = workspace / "diagnostics/pre_freeze_redim_selection_conflict.audit.json"
    conflict_path.parent.mkdir(parents=True, exist_ok=True)
    conflict_path.write_bytes(_json_bytes({"status": "AUDITED_FIXTURE"}))
    (workspace / "job_manifest.json").write_bytes(
        payloads["protocol/job_manifest.json"]
    )
    (workspace / "runtime_implementation_identity.json").write_bytes(
        payloads[RUNTIME_IDENTITY_MEMBER]
    )
    staging_sources = {
        "correction_bootstrap": staging
        / "h2_prefreeze_selector_correction_bootstrap.py",
        "patched_controller": staging / "controller.py.patched",
        "patched_controller_tests": staging
        / "test_h2_product_program_controller.py.patched",
        "correction_bootstrap_tests": staging
        / "test_prefreeze_selector_correction_bootstrap.py",
        "staging_validation": staging / "STAGING_VALIDATION.json",
        "correction_readme": staging / "README.md",
    }
    for label, path in staging_sources.items():
        path.write_text(f"fixture selector correction source: {label}\n", encoding="utf-8")
    tool_root = Path(__file__).resolve().parents[1]
    bound_sources = {
        **staging_sources,
        "pre_freeze_conflict_audit": conflict_path,
        "original_controller": tool_root / "app/h2_product_program/controller.py",
        "windows_atomic_retry_bootstrap": tool_root
        / "scripts/h2_windows_atomic_retry_bootstrap.py",
        "windows_atomic_retry_child": tool_root
        / "scripts/h2_atomic_retry_child/sitecustomize.py",
        "protocol_manifest": workspace / "protocol_manifest.json",
        "job_manifest": workspace / "job_manifest.json",
        "prepared_runtime_identity": workspace
        / "runtime_implementation_identity.json",
    }
    required_jobs = {
        "baseline_job": result_rows["baseline_job"]["result_sha256"],
        "integrated_job": result_rows["integrated_job"]["result_sha256"],
    }
    program_bindings = {
        "protocol_id": controller_state["protocol_id"],
        "protocol_sha256": controller_state["protocol_sha256"],
        "job_manifest_sha256": controller_state["job_manifest_sha256"],
        "runtime_implementation_identity_sha256": json.loads(
            payloads[RUNTIME_IDENTITY_MEMBER]
        )["identity_sha256"],
    }
    manifest_core = {
        "schema_version": "h2-prefreeze-selector-correction.v1",
        "expected_workspace": str(workspace.resolve()),
        "scientific_choice_changed": False,
        "evaluation_material_inspected": False,
        "qualified_selection_preserved": "R3_EXACT_WINDOW_EMBEDDING_REUSE",
        "program_bindings": program_bindings,
        "required_completed_jobs": required_jobs,
        "file_bindings": [
            {
                "label": label,
                "root": "fixture",
                "relative_path": path.name,
                "sha256": _sha(path.read_bytes()),
            }
            for label, path in sorted(bound_sources.items())
        ],
    }
    manifest = {
        **manifest_core,
        "activation_manifest_sha256": canonical_sha256(manifest_core),
    }
    manifest_payload = _json_bytes(manifest)
    (staging / "ACTIVATION_MANIFEST.json").write_bytes(manifest_payload)
    receipt_core = {
        "schema_version": "h2-prefreeze-selector-correction-activation.v1",
        "activated_at_utc": "2026-08-31T12:00:00Z",
        "activation_manifest_identity_sha256": manifest[
            "activation_manifest_sha256"
        ],
        "activation_manifest_file_sha256": _sha(manifest_payload),
        "workspace": str(workspace.resolve()),
        "heldout_was_unopened_at_first_activation": True,
        "scientific_choice_changed": False,
        "orchestration_defect_corrected": True,
    }
    activation = {
        **receipt_core,
        "receipt_sha256": canonical_sha256(receipt_core),
    }
    (workspace / "diagnostics/pre_freeze_selector_correction_activation.json").write_bytes(
        _json_bytes(activation)
    )
    selection_binding = _selector_correction_expected_binding(
        manifest, _sha(manifest_payload)
    )
    freeze_core = {
        "schema_version": "h2-product-frozen-policy.v1",
        **program_bindings,
        "evaluation_material_inspected": False,
        "selected_runtime": {
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "pre_freeze_selector_correction": selection_binding,
        },
    }
    payloads["protocol/frozen_policy.json"] = _json_bytes(
        {
            **freeze_core,
            "freeze_identity_sha256": canonical_sha256(freeze_core),
        }
    )


def _selector_correction_fixture() -> dict[str, bytes]:
    protocol_id = "h2_product_protocol_v17_test"
    protocol_sha256 = "1" * 64
    job_manifest_identity = "2" * 64
    runtime_identity = "3" * 64
    workspace = r"C:\scientific-campaign\h2_complete_product_pipeline_v17"
    required_jobs = {"r3": "4" * 64, "r4": "5" * 64}
    binding_members = final_package_module.SELECTOR_CORRECTION_BINDING_MEMBERS
    payloads: dict[str, bytes] = {
        "protocol/protocol_manifest.json": json.dumps(
            {"protocol_id": protocol_id, "protocol_sha256": protocol_sha256}
        ).encode(),
        "protocol/job_manifest.json": b'{"jobs":[]}',
        "protocol/runtime_implementation_identity.json": json.dumps(
            {"identity_sha256": runtime_identity}
        ).encode(),
    }
    for label, member in binding_members.items():
        payloads.setdefault(member, f"reproduction source: {label}\n".encode())

    program_bindings = {
        "protocol_id": protocol_id,
        "protocol_sha256": protocol_sha256,
        "job_manifest_sha256": job_manifest_identity,
        "runtime_implementation_identity_sha256": runtime_identity,
    }
    state = {
        "program_id": "h2-test",
        "protocol_id": protocol_id,
        "protocol_sha256": protocol_sha256,
        "job_manifest_sha256": job_manifest_identity,
        "workspace": workspace,
        "jobs": {
            job_id: {
                "state": "COMPLETE",
                "result_sha256": result_sha256,
            }
            for job_id, result_sha256 in required_jobs.items()
        },
    }
    payloads["controller/program_state.json"] = json.dumps(state).encode()
    manifest_core = {
        "schema_version": "h2-prefreeze-selector-correction.v1",
        "expected_workspace": workspace,
        "scientific_choice_changed": False,
        "evaluation_material_inspected": False,
        "qualified_selection_preserved": "R3_EXACT_WINDOW_EMBEDDING_REUSE",
        "program_bindings": program_bindings,
        "required_completed_jobs": required_jobs,
        "file_bindings": [
            {
                "label": label,
                "root": "synthetic_fixture",
                "relative_path": member,
                "sha256": _sha(payloads[member]),
            }
            for label, member in sorted(binding_members.items())
        ],
    }
    manifest = {
        **manifest_core,
        "activation_manifest_sha256": canonical_sha256(manifest_core),
    }
    manifest_payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    payloads[final_package_module.SELECTOR_CORRECTION_MANIFEST_MEMBER] = (
        manifest_payload
    )
    receipt_core = {
        "schema_version": "h2-prefreeze-selector-correction-activation.v1",
        "activated_at_utc": "2026-08-31T12:00:00Z",
        "activation_manifest_identity_sha256": manifest[
            "activation_manifest_sha256"
        ],
        "activation_manifest_file_sha256": _sha(manifest_payload),
        "workspace": workspace,
        "heldout_was_unopened_at_first_activation": True,
        "scientific_choice_changed": False,
        "orchestration_defect_corrected": True,
    }
    receipt = {**receipt_core, "receipt_sha256": canonical_sha256(receipt_core)}
    payloads[final_package_module.SELECTOR_CORRECTION_RECEIPT_MEMBER] = (
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    ).encode()
    selected_binding = _selector_correction_expected_binding(
        manifest, _sha(manifest_payload)
    )
    freeze_core = {
        "schema_version": "h2-product-frozen-policy.v1",
        "protocol_id": protocol_id,
        "protocol_sha256": protocol_sha256,
        "job_manifest_sha256": job_manifest_identity,
        "runtime_implementation_identity_sha256": runtime_identity,
        "evaluation_material_inspected": False,
        "selected_runtime": {
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "pre_freeze_selector_correction": selected_binding,
        },
    }
    freeze = {**freeze_core, "freeze_identity_sha256": canonical_sha256(freeze_core)}
    payloads["protocol/frozen_policy.json"] = json.dumps(freeze).encode()
    provenance = _selector_correction_provenance_document(payloads)
    payloads[final_package_module.SELECTOR_CORRECTION_PROVENANCE_MEMBER] = (
        final_package_module._canonical_json(provenance)
    )
    return payloads


def test_selector_correction_reproduction_is_complete_and_fail_closed() -> None:
    payloads = _selector_correction_fixture()
    provenance = _validate_selector_correction_members(payloads)
    assert provenance["status"] == "VALID"
    assert provenance["qualified_selection_preserved"] == (
        "R3_EXACT_WINDOW_EMBEDDING_REUSE"
    )
    assert provenance["heldout_was_unopened_at_first_activation"] is True
    assert provenance["prepared_inference_runtime_identity_preserved"] is True
    assert set(REQUIRED_SELECTOR_CORRECTION_MEMBERS).issubset(payloads)

    tampered = dict(payloads)
    tampered[final_package_module.SELECTOR_CORRECTION_BINDING_MEMBERS[
        "patched_controller"
    ]] += b"# mutation\n"
    with pytest.raises(ValueError, match="source checksum differs"):
        _validate_selector_correction_members(tampered)


def test_postcampaign_watcher_waits_through_recoverable_blocked_state() -> None:
    tool_root = Path(__file__).resolve().parents[1]
    watcher = tool_root / "scripts/watch_h2_postcampaign_engineering.ps1"
    source = watcher.read_text(encoding="utf-8-sig")
    terminal_clause = (
        "@('FAILED', 'BLOCKED_OTHER', 'BLOCKED_SCIENTIFIC_RUN', 'STOPPED')"
    )
    assert terminal_clause in source
    assert "@('FAILED', 'BLOCKED'," not in source
    assert "checksum-bound selector handoff" in source


def test_overlap_supplement_is_complete_and_development_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ReusableReport:
        reusable = True
        issues: tuple[object, ...] = ()

    monkeypatch.setattr(
        "scripts.augment_h2_final_package.validate_result_tree",
        lambda _root: _ReusableReport(),
    )
    workspace = tmp_path / "workspace"
    source = _write_native_package(tmp_path, workspace)
    with zipfile.ZipFile(source) as archive:
        payloads = {name: archive.read(name) for name in archive.namelist()}

    additions, provenance = build_overlap_stratified_supplement(payloads, workspace)

    rows = list(
        csv.DictReader(
            io.StringIO(additions[REQUIRED_OVERLAP_MEMBERS[0]].decode("utf-8"))
        )
    )
    assert len(rows) == 96
    assert {row["evidence_split"] for row in rows} == {"development"}
    assert {row["composition"] for row in rows} == {
        "KNOWN_KNOWN",
        "KNOWN_UNKNOWN",
        "UNKNOWN_UNKNOWN",
    }
    assert {row["condition"] for row in rows} == {
        "OVERLAP_PRESENT",
        "NO_OVERLAP_CONTROL",
    }
    assert {
        row["case_count"] for row in rows if row["condition"] == "NO_OVERLAP_CONTROL"
    } == {"2"}
    assert provenance["evaluation_material_inspected"] is False
    assert provenance["post_hoc_metrics_used_for_frozen_selection"] is False
    assert provenance["selected_overlap_policy"] == (
        "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY"
    )


def test_boundary_supplement_pairs_repaired_and_harmed_words(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ReusableReport:
        reusable = True
        issues: tuple[object, ...] = ()

    monkeypatch.setattr(
        "scripts.augment_h2_final_package.validate_result_tree",
        lambda _root: _ReusableReport(),
    )
    workspace = tmp_path / "workspace"
    source = _write_native_package(tmp_path, workspace)
    with zipfile.ZipFile(source) as archive:
        payloads = {name: archive.read(name) for name in archive.namelist()}

    additions, provenance = build_boundary_correction_supplement(payloads, workspace)
    summary = list(
        csv.DictReader(
            io.StringIO(additions[REQUIRED_BOUNDARY_MEMBERS[0]].decode("utf-8"))
        )
    )
    case_rows = list(
        csv.DictReader(
            io.StringIO(additions[REQUIRED_BOUNDARY_MEMBERS[1]].decode("utf-8"))
        )
    )
    by_id = {row["configuration_id"]: row for row in summary}
    assert set(by_id) == set(BOUNDARY_CONFIGURATIONS)
    assert len(case_rows) == len(BOUNDARY_CONFIGURATIONS)
    assert by_id["BOUNDARY_CORRECTION_0250MS"]["repaired_word_count_vs_0ms"] == "1"
    assert by_id["BOUNDARY_CORRECTION_0250MS"]["harmed_word_count_vs_0ms"] == "0"
    assert by_id["BOUNDARY_CORRECTION_0500MS"]["repaired_word_count_vs_0ms"] == "1"
    assert by_id["BOUNDARY_CORRECTION_0500MS"]["harmed_word_count_vs_0ms"] == "1"
    assert (
        by_id["BOUNDARY_CORRECTION_0250MS"][
            "repaired_from_previous_speaker_word_count_vs_0ms"
        ]
        == "1"
    )
    assert (
        by_id["BOUNDARY_CORRECTION_0250MS"][
            "initially_previous_speaker_word_time_status"
        ]
        == "UNSUPPORTED_NO_REFERENCE_WORD_TIMESTAMPS"
    )
    assert (
        by_id["BOUNDARY_CORRECTION_0250MS"]["mean_speaker_relabel_audio_delay_sec"]
        == "1.0"
    )
    assert provenance["development_only"] is True
    assert provenance["evaluation_material_inspected"] is False
    assert provenance["only_result_affecting_axis_varied"] == ("boundary_correction_ms")


def test_missing_computed_plot_metric_fails_closed() -> None:
    payloads = _plot_tables()
    rows = [
        row
        for row in csv.DictReader(io.StringIO(payloads[PLOT_SOURCES[0]].decode()))
        if row["metric_id"] != "stable_name_latency_sec"
    ]
    payloads[PLOT_SOURCES[0]] = _csv_payload(rows)
    try:
        build_plots(payloads)
    except ValueError as exc:
        assert "no computed values" in str(exc)
    else:
        raise AssertionError("missing computed stable-name latency must fail")


def test_augment_rejects_native_zip_from_different_controller_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    source = _write_native_package(tmp_path, workspace)
    state_path = workspace / "program_state.json"
    state = json.loads(state_path.read_bytes())
    state["protocol_sha256"] = "c" * 64
    state_path.write_bytes(_json_bytes(state))

    with pytest.raises(ValueError, match="binding differs: protocol_sha256"):
        augment_package(source, workspace, tmp_path / "must_not_publish.zip")
    assert not (tmp_path / "must_not_publish.zip").exists()
