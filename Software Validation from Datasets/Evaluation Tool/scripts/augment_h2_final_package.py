"""Add checksum-bound plots and scientific supplements to the H2 final package.

This is deliberately a post-collection operation.  It never edits scientific
results, frozen policies, controller state, or the native package.  Instead it
validates the collector-produced ZIP, derives plots and explicit post-run
metrics from immutable results, copies checksum-verified axis-selection
receipts, and creates a deterministic superset ZIP with a complete manifest.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import html
import io
import json
import math
from pathlib import Path, PurePosixPath
import random
import sqlite3
import statistics
import string
import sys
import tempfile
from typing import Iterable, Mapping, Sequence
import zipfile

import yaml

_BOOTSTRAP_TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(_BOOTSTRAP_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_TOOL_ROOT))

from app.diarization_evaluation.formats import (  # noqa: E402
    RttmTurn,
    parse_rttm,
    parse_uem,
)
from app.full_pipeline_evaluation.scorers import (  # noqa: E402
    _word_edit_counts,
    score_anonymous_diarization,
)
from app.full_pipeline_evaluation.results import validate_result_tree  # noqa: E402
from app.full_pipeline_evaluation.worker import (  # noqa: E402
    _canonical_reference_speaker_id,
    _normalized_scoring_words,
    _speaker_transcription_scoring_inputs,
)
from app.h2_product_program.io import canonical_sha256  # noqa: E402
from app.h2_product_program.reporting import (  # noqa: E402
    ARM64_PACKAGE_FILES,
    validate_package_zip,
)
from scripts.audit_h2_enrollment_firewall import (  # noqa: E402
    validate_receipt as validate_enrollment_firewall_receipt,
)
from scripts.measure_h2_ui_event_latency import (  # noqa: E402
    SOURCE_FILES as UI_LATENCY_RUNTIME_SOURCE_FILES,
    validate_receipt as validate_ui_latency_receipt,
)


TOOL_ROOT = _BOOTSTRAP_TOOL_ROOT
DEFAULT_WORKSPACE = TOOL_ROOT / "automated_runs/h2_complete_product_pipeline_v17"
DEFAULT_PACKAGE_ROOT = TOOL_ROOT / "JustPeachyResearchSummaries"
SCHEMA_VERSION = "h2-augmented-presentation-package.v19"
MAX_TOTAL_BYTES = 110 * 1024 * 1024
BOOTSTRAP_REPETITIONS = 2000
BOOTSTRAP_SEED = 3800
PLOT_SOURCES = (
    "summary/h2_mode_comparison.csv",
    "summary/h2_resource_results.csv",
    "summary/h2_segmentation_frontier.csv",
)
REQUIRED_METRIC_MEMBERS = (
    "supplements/h2_required_diarization_metrics.csv",
    "supplements/H2_REQUIRED_DIARIZATION_METRICS.md",
    "supplements/h2_required_diarization_metrics_provenance.json",
)
REQUIRED_TRANSCRIPT_MEMBERS = (
    "supplements/h2_required_transcript_structure_metrics.csv",
    "supplements/H2_REQUIRED_TRANSCRIPT_STRUCTURE_METRICS.md",
    "supplements/h2_required_transcript_structure_metrics_provenance.json",
)
REQUIRED_SCIENCE_TABLE_MEMBERS = (
    "supplements/source_science/open_set_policy_frontier.csv",
    "supplements/source_science/identity_hubness.csv",
    "supplements/source_science/integrated_enrollment_matrix.csv",
    "supplements/source_science/integrated_enrollment_qc_events.csv",
    "supplements/source_science/integrated_enrollment_hubness.csv",
    "supplements/source_science/integrated_enrollment_selected_cell.csv",
    "supplements/source_science/SCIENCE_SOURCE_TABLE_PROVENANCE.json",
)
REQUIRED_OVERLAP_MEMBERS = (
    "supplements/h2_overlap_stratified_results.csv",
    "supplements/H2_OVERLAP_STRATIFIED_RESULTS.md",
    "supplements/h2_overlap_stratified_provenance.json",
)
REQUIRED_BOUNDARY_MEMBERS = (
    "supplements/h2_boundary_correction_summary.csv",
    "supplements/h2_boundary_correction_case_pairs.csv",
    "supplements/H2_BOUNDARY_CORRECTION_DIAGNOSTICS.md",
    "supplements/h2_boundary_correction_provenance.json",
)
REQUIRED_RECOMMENDATION_MEMBERS = (
    "supplements/h2_final_recommendations.json",
    "supplements/H2_FINAL_RECOMMENDATIONS.md",
)
REQUIRED_HARDWARE_PLATFORM_MEMBERS = (
    "supplements/h2_hardware_platform_assessment.csv",
    "supplements/H2_HARDWARE_PLATFORM_ASSESSMENT.md",
    "supplements/h2_hardware_platform_assessment.json",
)
REQUIRED_STREAMING_PROVENANCE_MEMBERS = (
    "supplements/H2_STREAMING_EXECUTION_PROVENANCE.md",
    "supplements/h2_streaming_execution_provenance.json",
)
STREAMING_FRESH_RESOURCE_CONFIGURATIONS = {
    "H2_KNOWN_ONLY_SERIAL_RESOURCE": "H2_KNOWN_ONLY",
    "H2_SESSION_ANONYMOUS_SERIAL_RESOURCE": "H2_SESSION_ANONYMOUS",
    "H2_SESSION_MEMORY_ENHANCED_SERIAL_RESOURCE": "H2_SESSION_MEMORY_ENHANCED",
}
HARDWARE_PLATFORM_SOURCE_URLS = {
    "arduino_uno_q_documentation": "https://docs.arduino.cc/hardware/uno-q",
    "arduino_uno_q_datasheet": (
        "https://docs.arduino.cc/resources/datasheets/ABX00162-datasheet.pdf"
    ),
    "arduino_uno_q_2gb_store": "https://store.arduino.cc/products/uno-q",
    "arduino_uno_q_4gb_store": "https://store.arduino.cc/products/uno-q-4gb",
    "raspberry_pi_cm5": "https://www.raspberrypi.com/products/compute-module-5/",
    "raspberry_pi_cm5_datasheet": (
        "https://datasheets.raspberrypi.com/cm5/cm5-datasheet.pdf"
    ),
    "raspberry_pi_5_sustained_load_cooling": (
        "https://www.raspberrypi.com/news/heating-and-cooling-raspberry-pi-5/"
    ),
    "onnxruntime_qnn": (
        "https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html"
    ),
    "sherpa_onnx_linux_arm64": (
        "https://k2-fsa.github.io/sherpa/onnx/install/index.html"
    ),
}
REQUIRED_LONG_SESSION_DRIFT_MEMBERS = (
    "supplements/h2_long_session_drift.csv",
    "supplements/H2_LONG_SESSION_DRIFT.md",
    "supplements/h2_long_session_drift_provenance.json",
)
REQUIRED_ASR_COMPARABILITY_MEMBERS = (
    "supplements/h2_asr_wer_comparability.csv",
    "supplements/H2_ASR_WER_COMPARABILITY.md",
    "supplements/h2_asr_wer_comparability_provenance.json",
)
HOST_IO_PREFIX = "reproducibility/host_io/"
HOST_IO_RECEIPT_MEMBER = f"{HOST_IO_PREFIX}windows_host_io_interference.json"
HOST_IO_COLLECTOR_MEMBER = f"{HOST_IO_PREFIX}code/capture_h2_host_io_interference.ps1"
HOST_IO_README_MEMBER = f"{HOST_IO_PREFIX}H2_HOST_IO_INTERFERENCE_README.md"
HOST_IO_SUMMARY_MEMBER = "supplements/h2_queue_backpressure_summary.csv"
HOST_IO_CASES_MEMBER = "supplements/h2_queue_backpressure_cases.csv"
HOST_IO_GUIDE_MEMBER = "supplements/H2_QUEUE_BACKPRESSURE.md"
HOST_IO_PROVENANCE_MEMBER = f"{HOST_IO_PREFIX}HOST_IO_INTERFERENCE_PROVENANCE.json"
REQUIRED_HOST_IO_MEMBERS = (
    HOST_IO_RECEIPT_MEMBER,
    HOST_IO_COLLECTOR_MEMBER,
    HOST_IO_README_MEMBER,
    HOST_IO_SUMMARY_MEMBER,
    HOST_IO_CASES_MEMBER,
    HOST_IO_GUIDE_MEMBER,
    HOST_IO_PROVENANCE_MEMBER,
)
HOST_IO_CANDIDATE_JOB_IDS = (
    "h2p1_s1_coverage_medium_d091522a94",
    "h2p1_s2_balanced_medium_214a5381e2",
    "h2p1_s6_hop_050_medium_fb86ed3ddb",
    "h2p1_s7_hop_100_medium_b6fc36bc0f",
)
HOST_IO_SELECTED_CONFIGURATIONS = ("S2_BALANCED", "S1_COVERAGE")
SERIAL_HOST_IO_GROUPS = (
    {
        "group_id": "phase2_matched_redim",
        "phase_index": 2,
        "job_kind": "resource_runtime",
        "receipt_filename": "serial_resource_phase2_redim_host_io.json",
        "job_ids": (
            "h2p2_r1_two_independent_models_matched_serial_resource_a5d81446a0",
            "h2p2_r2_one_shared_model_matched_serial_resource_6599c41691",
        ),
    },
    {
        "group_id": "phase6_selected_modes",
        "phase_index": 6,
        "job_kind": "post_selection_resource_runtime",
        "receipt_filename": "serial_resource_phase6_modes_host_io.json",
        "job_ids": (
            "h2p6_h2_known_only_serial_resource_1e27a1e89d",
            "h2p6_h2_session_anonymous_serial_resource_e379f9fbbb",
            "h2p6_h2_session_memory_enhanced_serial_resource_666392efba",
        ),
    },
)
SERIAL_HOST_IO_RECEIPT_MEMBERS = tuple(
    f"{HOST_IO_PREFIX}{group['receipt_filename']}" for group in SERIAL_HOST_IO_GROUPS
)
SERIAL_HOST_IO_WATCHER_MEMBER = f"{HOST_IO_PREFIX}code/watch_h2_serial_resource_io.ps1"
SERIAL_HOST_IO_SUMMARY_MEMBER = "supplements/h2_serial_resource_host_io_eligibility.csv"
SERIAL_HOST_IO_GUIDE_MEMBER = "supplements/H2_SERIAL_RESOURCE_HOST_IO_ELIGIBILITY.md"
SERIAL_HOST_IO_PROVENANCE_MEMBER = (
    f"{HOST_IO_PREFIX}SERIAL_RESOURCE_HOST_IO_PROVENANCE.json"
)
PHASE2_QUIET_REPLAY_PREFIX = f"{HOST_IO_PREFIX}phase2_quiet_replay/"
PHASE2_QUIET_REPLAY_BINDING_MEMBER = f"{PHASE2_QUIET_REPLAY_PREFIX}REPLAY_BINDING.json"
PHASE2_QUIET_REPLAY_MANIFEST_MEMBER = (
    f"{PHASE2_QUIET_REPLAY_PREFIX}resource_replay_manifest.json"
)
PHASE2_QUIET_REPLAY_STATE_MEMBER = f"{PHASE2_QUIET_REPLAY_PREFIX}program_state.json"
PHASE2_QUIET_REPLAY_JOB_MANIFEST_MEMBER = (
    f"{PHASE2_QUIET_REPLAY_PREFIX}job_manifest.json"
)
PHASE2_QUIET_REPLAY_COMPARISON_MEMBER = (
    f"{PHASE2_QUIET_REPLAY_PREFIX}resource_comparison.json"
)
PHASE2_QUIET_REPLAY_COMPARISON_CSV_MEMBER = (
    f"{PHASE2_QUIET_REPLAY_PREFIX}resource_comparison.csv"
)
PHASE2_QUIET_REPLAY_LAUNCHER_MEMBER = (
    f"{PHASE2_QUIET_REPLAY_PREFIX}code/replay_h2_phase2_serial_resources.py"
)
PHASE2_QUIET_REPLAY_README_MEMBER = (
    f"{PHASE2_QUIET_REPLAY_PREFIX}H2_PHASE2_QUIET_RESOURCE_REPLAY_README.md"
)
PHASE2_ORIGINAL_CONTAMINATED_RECEIPT_MEMBER = (
    f"{PHASE2_QUIET_REPLAY_PREFIX}original_serial_resource_phase2_redim_host_io.json"
)
REQUIRED_PHASE2_QUIET_REPLAY_MEMBERS = (
    PHASE2_QUIET_REPLAY_BINDING_MEMBER,
    PHASE2_QUIET_REPLAY_MANIFEST_MEMBER,
    PHASE2_QUIET_REPLAY_STATE_MEMBER,
    PHASE2_QUIET_REPLAY_JOB_MANIFEST_MEMBER,
    PHASE2_QUIET_REPLAY_COMPARISON_MEMBER,
    PHASE2_QUIET_REPLAY_COMPARISON_CSV_MEMBER,
    PHASE2_QUIET_REPLAY_LAUNCHER_MEMBER,
    PHASE2_QUIET_REPLAY_README_MEMBER,
    PHASE2_ORIGINAL_CONTAMINATED_RECEIPT_MEMBER,
)
REQUIRED_SERIAL_HOST_IO_MEMBERS = (
    *SERIAL_HOST_IO_RECEIPT_MEMBERS,
    SERIAL_HOST_IO_WATCHER_MEMBER,
    SERIAL_HOST_IO_SUMMARY_MEMBER,
    SERIAL_HOST_IO_GUIDE_MEMBER,
    SERIAL_HOST_IO_PROVENANCE_MEMBER,
)
SERIAL_HOST_IO_SUMMARY_FIELDS = (
    "schema_version",
    "group_id",
    "phase_index",
    "job_kind",
    "job_id",
    "configuration_id",
    "mode",
    "started_at_utc",
    "completed_at_utc",
    "completed_cases",
    "completed_audio_sec",
    "wall_elapsed_sec",
    "wall_rtf",
    "blocked_total_sec",
    "blocked_max_sec",
    "dropped_frames",
    "esent_event_count",
    "storage_driver_warning_or_error_count",
    "result_sha256",
    "declared_checksum_count",
    "verified_checksum_count",
    "resource_comparison_eligible",
)
HOST_IO_SUMMARY_FIELDS = (
    "schema_version",
    "job_id",
    "started_at_utc",
    "completed_at_utc",
    "completed_cases",
    "completed_audio_sec",
    "wall_elapsed_sec",
    "wall_rtf",
    "event_count",
    "blocked_total_sec",
    "blocked_max_sec",
    "cases_with_blocked_max_gt_10_sec",
    "cases_with_blocked_max_gt_60_sec",
    "dropped_frames",
    "esent_event_count",
    "esent_completed_io_event_count",
    "maximum_esent_reported_io_sec",
    "maximum_esent_event_utc",
    "maximum_duration_absolute_delta_sec",
    "acronis_vss_event_count",
    "independent_storage_guardian_event_count",
    "result_sha256",
    "declared_checksum_count",
    "verified_checksum_count",
    "accuracy_metrics_eligible",
    "resource_comparison_eligible",
)
HOST_IO_CASE_FIELDS = (
    "schema_version",
    "job_id",
    "stall_rank_within_job",
    "case_id",
    "audio_duration_sec",
    "event_count",
    "blocked_total_sec",
    "blocked_max_sec",
    "dropped_frames",
    "result_sha256",
    "resource_comparison_eligible",
)
ASR_COMPARABILITY_CONFIGURATIONS = (
    "H2_BASELINE_REFERENCE",
    "H2_KNOWN_ONLY_OPTIMIZED",
    "H2_SESSION_ANONYMOUS_OPTIMIZED",
    "H2_SESSION_MEMORY_OPTIMIZED",
)
ASR_COMPARABILITY_STRATA = (
    "OVERALL",
    "SINGLE_SPEAKER",
    "TWO_TO_FOUR_SPEAKERS",
    "FIVE_TO_TWELVE_SPEAKERS",
    "OVERLAP_PRESENT",
    "NO_OVERLAP",
)
ASR_COMPARABILITY_FIELDS = (
    "schema_version",
    "configuration_id",
    "mode",
    "evidence_split",
    "source_job_id",
    "metric_id",
    "metric_role",
    "scoring_policy_id",
    "stratum",
    "metric_status",
    "value",
    "value_percent",
    "numerator",
    "denominator",
    "substitutions",
    "deletions",
    "insertions",
    "reference_tokens_for_punctuation_rate",
    "hypothesis_tokens_for_punctuation_rate",
    "reference_ascii_punctuation_tokens",
    "hypothesis_ascii_punctuation_tokens",
    "reference_ascii_punctuation_token_rate",
    "hypothesis_ascii_punctuation_token_rate",
    "punctuation_sensitive_minus_insensitive_wer",
    "punctuation_sensitive_minus_insensitive_wer_percentage_points",
    "source_reported_metric_match",
    "scientific_selection_eligible",
    "definition",
)
LONG_SESSION_DRIFT_METRICS = (
    ("real_time_factor", "real_time_factor", "direct", "ratio"),
    ("peak_process_rss_bytes", "peak_process_rss_bytes", "direct", "bytes"),
    ("maximum_queue_depth", "maximum_queue_depth", "direct", "items"),
    ("dropped_frames_per_hour", "dropped_frame_count", "per_hour", "frames/hour"),
    (
        "transcript_revisions_per_minute",
        "transcript_revision_count",
        "per_minute",
        "revisions/minute",
    ),
    (
        "asr_partial_revisions_per_minute",
        "asr_partial_revision_count",
        "per_minute",
        "revisions/minute",
    ),
    (
        "identity_revisions_per_minute",
        "identity_revision_event_count",
        "per_minute",
        "revisions/minute",
    ),
    (
        "cluster_revisions_per_minute",
        "cluster_revision_event_count",
        "per_minute",
        "revisions/minute",
    ),
    (
        "maximum_identity_observations",
        "identity_observation_count",
        "direct",
        "items",
    ),
    ("maximum_identity_clusters", "identity_cluster_count", "direct", "items"),
    ("maximum_identity_history", "identity_history_count", "direct", "items"),
    (
        "maximum_session_roster",
        "session_memory_roster_count",
        "direct",
        "items",
    ),
    (
        "maximum_session_event_history",
        "session_memory_history_count",
        "direct",
        "items",
    ),
)
LONG_SESSION_DRIFT_FIELDS = (
    "schema_version",
    "split",
    "source_recording_id",
    "short_stream_id",
    "long_stream_id",
    "metric_id",
    "source_metric_id",
    "normalization",
    "metric_status",
    "value_30m",
    "value_60m",
    "absolute_drift_60m_minus_30m",
    "relative_drift_fraction",
    "unit",
    "reason",
)
REQUIRED_STORAGE_MEMBERS = (
    "reproducibility/storage/artifact_lifecycle.json",
    "reproducibility/storage/storage_forecast.json",
    "reproducibility/storage/last_guardian_pass.json",
    "reproducibility/storage/arm64_wheel_resolution_receipt.json",
    "reproducibility/storage/H2_STORAGE_MAINTENANCE_README.md",
    "reproducibility/storage/code/maintain_h2_storage.py",
    "reproducibility/storage/code/run_h2_storage_guardian.ps1",
    "reproducibility/storage/code/supervise_h2_product_program.ps1",
    "reproducibility/storage/code/register_h2_v17_scheduled_tasks.ps1",
    "reproducibility/storage/tests/test_h2_storage_maintenance.py",
    "reproducibility/storage/windows_atomic_publication_policy.json",
    "reproducibility/storage/windows_atomic_publication_events.jsonl",
    "reproducibility/storage/code/h2_windows_atomic_retry_bootstrap.py",
    "reproducibility/storage/code/run_h2_product_program.ps1",
    "reproducibility/storage/H2_WINDOWS_ATOMIC_RETRY_README.md",
    "reproducibility/storage/code/resolve_h2_arm64_wheels.py",
    "reproducibility/storage/H2_ARM64_WHEEL_RESOLUTION_README.md",
    "reproducibility/storage/tests/test_h2_arm64_wheel_resolver.py",
    "reproducibility/storage/code/h2_atomic_retry_child_sitecustomize.py",
    "reproducibility/storage/queue_attempt_history.csv",
    "reproducibility/storage/controller_terminal_program_state.json",
    "reproducibility/storage/STORAGE_REPRODUCIBILITY_PROVENANCE.json",
)
STORAGE_PREFIX = "reproducibility/storage/"
STORAGE_PRUNE_PREFIX = f"{STORAGE_PREFIX}prune_receipts/"
STORAGE_COMPRESSION_PREFIX = f"{STORAGE_PREFIX}compression_receipts/"
STORAGE_DYNAMIC_PREFIX = f"{STORAGE_PREFIX}dynamic_execution_manifests/"
STORAGE_ARM64_WHEEL_RECEIPT_MEMBER = (
    "reproducibility/storage/arm64_wheel_resolution_receipt.json"
)
STORAGE_ATOMIC_POLICY_MEMBER = (
    "reproducibility/storage/windows_atomic_publication_policy.json"
)
STORAGE_ATOMIC_EVENTS_MEMBER = (
    "reproducibility/storage/windows_atomic_publication_events.jsonl"
)
STORAGE_ATOMIC_BOOTSTRAP_MEMBER = (
    "reproducibility/storage/code/h2_windows_atomic_retry_bootstrap.py"
)
STORAGE_ATOMIC_CHILD_MEMBER = (
    "reproducibility/storage/code/h2_atomic_retry_child_sitecustomize.py"
)
STORAGE_ARM64_RESOLVER_MEMBER = (
    "reproducibility/storage/code/resolve_h2_arm64_wheels.py"
)
STORAGE_ARM64_RESOLVER_README_MEMBER = (
    "reproducibility/storage/H2_ARM64_WHEEL_RESOLUTION_README.md"
)
STORAGE_ARM64_RESOLVER_TEST_MEMBER = (
    "reproducibility/storage/tests/test_h2_arm64_wheel_resolver.py"
)
STORAGE_ATTEMPT_HISTORY_MEMBER = "reproducibility/storage/queue_attempt_history.csv"
STORAGE_TASK_REGISTRATION_MEMBER = "reproducibility/storage/scheduled_tasks_v17.json"
STORAGE_TASK_INSTALLER_MEMBER = (
    "reproducibility/storage/code/register_h2_v17_scheduled_tasks.ps1"
)
ARM64_REQUIREMENTS_MEMBER = "deployment/h2_arm64/requirements-linux-arm64.txt"
RUNTIME_IDENTITY_MEMBER = "protocol/runtime_implementation_identity.json"
ARM64_V2_SOURCE_PREFIX = "deployment/h2_arm64/"
ARM64_V2_PREFIX = "deployment/h2_arm64_v2/"
ARM64_V2_GUIDE_MEMBER = "supplements/H2_ARM64_DEPLOYMENT_V2.md"
ARM64_V2_PROVENANCE_MEMBER = (
    "reproducibility/arm64_deployment_v2/ARM64_DEPLOYMENT_V2_PROVENANCE.json"
)
REQUIRED_ARM64_V2_MEMBERS = (
    *tuple(f"{ARM64_V2_PREFIX}{name}" for name in ARM64_PACKAGE_FILES),
    ARM64_V2_GUIDE_MEMBER,
    ARM64_V2_PROVENANCE_MEMBER,
)
ATTEMPT_HISTORY_FIELDS = (
    "schema_version",
    "queue_database_relative_path",
    "queue_database_sha256",
    "job_id",
    "attempt_number",
    "attempt_state",
    "final_job_state",
    "recovered_after_attempt",
    "attempt_path_relative",
    "started_at_utc",
    "ended_at_utc",
    "error",
)
AUGMENTATION_PREFIX = "reproducibility/augmentation/"
REQUIRED_AUGMENTATION_MEMBERS = (
    f"{AUGMENTATION_PREFIX}augment_h2_final_package.py",
    f"{AUGMENTATION_PREFIX}watch_and_augment_h2_final_package.ps1",
    f"{AUGMENTATION_PREFIX}H2_FINAL_PACKAGE_SUPPLEMENT_README.md",
    f"{AUGMENTATION_PREFIX}test_h2_final_package_supplement.py",
    f"{AUGMENTATION_PREFIX}watch_h2_postcampaign_engineering.ps1",
    f"{AUGMENTATION_PREFIX}H2_POSTCAMPAIGN_ENGINEERING_WATCHER_README.md",
    f"{AUGMENTATION_PREFIX}asr_commonvoice_60plus.v1.yaml",
    f"{AUGMENTATION_PREFIX}AUGMENTATION_SOURCE_PROVENANCE.json",
)
ASR_COMMONVOICE_POLICY_MEMBER = REQUIRED_AUGMENTATION_MEMBERS[-2]
ASR_COMMONVOICE_POLICY_SOURCE = (
    TOOL_ROOT / "configs/automated_evaluation/asr_commonvoice_60plus.v1.yaml"
)
UI_LATENCY_PREFIX = "reproducibility/ui_event_latency/"
UI_LATENCY_RECEIPT_MEMBER = f"{UI_LATENCY_PREFIX}ui_event_latency_receipt.json"
UI_LATENCY_PROVENANCE_MEMBER = f"{UI_LATENCY_PREFIX}UI_EVENT_LATENCY_PROVENANCE.json"
UI_LATENCY_RUNTIME_PREFIX = f"{UI_LATENCY_PREFIX}runtime_source/"
UI_LATENCY_BENCHMARK_SOURCE_MEMBER = (
    f"{UI_LATENCY_PREFIX}code/measure_h2_ui_event_latency.py"
)
UI_LATENCY_README_MEMBER = f"{UI_LATENCY_PREFIX}H2_UI_EVENT_LATENCY_README.md"
UI_LATENCY_TEST_MEMBER = (
    f"{UI_LATENCY_PREFIX}tests/test_h2_ui_event_latency_benchmark.py"
)
UI_LATENCY_SUMMARY_CSV_MEMBER = "supplements/h2_controlled_ui_event_latency.csv"
UI_LATENCY_SUMMARY_GUIDE_MEMBER = "supplements/H2_CONTROLLED_UI_EVENT_LATENCY.md"
REQUIRED_UI_LATENCY_MEMBERS = (
    UI_LATENCY_RECEIPT_MEMBER,
    UI_LATENCY_BENCHMARK_SOURCE_MEMBER,
    UI_LATENCY_README_MEMBER,
    UI_LATENCY_TEST_MEMBER,
    *tuple(
        f"{UI_LATENCY_RUNTIME_PREFIX}{path.relative_to(TOOL_ROOT).as_posix()}"
        for path in UI_LATENCY_RUNTIME_SOURCE_FILES
    ),
    UI_LATENCY_SUMMARY_CSV_MEMBER,
    UI_LATENCY_SUMMARY_GUIDE_MEMBER,
    UI_LATENCY_PROVENANCE_MEMBER,
)
DATA_FIREWALL_PREFIX = "reproducibility/data_firewall/"
DATA_FIREWALL_RECEIPT_MEMBER = (
    f"{DATA_FIREWALL_PREFIX}enrollment_firewall_audit_receipt.json"
)
DATA_FIREWALL_CODE_MEMBER = (
    f"{DATA_FIREWALL_PREFIX}code/audit_h2_enrollment_firewall.py"
)
DATA_FIREWALL_README_MEMBER = (
    f"{DATA_FIREWALL_PREFIX}H2_ENROLLMENT_FIREWALL_AUDIT_README.md"
)
DATA_FIREWALL_TEST_MEMBER = (
    f"{DATA_FIREWALL_PREFIX}tests/test_h2_enrollment_firewall_audit.py"
)
DATA_FIREWALL_PROVENANCE_MEMBER = f"{DATA_FIREWALL_PREFIX}DATA_FIREWALL_PROVENANCE.json"
REQUIRED_DATA_FIREWALL_MEMBERS = (
    DATA_FIREWALL_RECEIPT_MEMBER,
    DATA_FIREWALL_CODE_MEMBER,
    DATA_FIREWALL_README_MEMBER,
    DATA_FIREWALL_TEST_MEMBER,
    DATA_FIREWALL_PROVENANCE_MEMBER,
)
DEVELOPMENT_CPU_INTERFERENCE_PREFIX = (
    "reproducibility/host_interference/development_cpu/"
)
DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER = f"{DEVELOPMENT_CPU_INTERFERENCE_PREFIX}development_host_cpu_interference_receipt.json"
DEVELOPMENT_CPU_INTERFERENCE_PROVENANCE_MEMBER = f"{DEVELOPMENT_CPU_INTERFERENCE_PREFIX}DEVELOPMENT_HOST_CPU_INTERFERENCE_PROVENANCE.json"
REQUIRED_DEVELOPMENT_CPU_INTERFERENCE_MEMBERS = (
    DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER,
    DEVELOPMENT_CPU_INTERFERENCE_PROVENANCE_MEMBER,
)
SELECTOR_CORRECTION_PREFIX = "reproducibility/selector_correction/"
SELECTOR_CORRECTION_RECEIPT_MEMBER = (
    f"{SELECTOR_CORRECTION_PREFIX}pre_freeze_selector_correction_activation.json"
)
SELECTOR_CORRECTION_MANIFEST_MEMBER = (
    f"{SELECTOR_CORRECTION_PREFIX}ACTIVATION_MANIFEST.json"
)
SELECTOR_CORRECTION_PROVENANCE_MEMBER = (
    f"{SELECTOR_CORRECTION_PREFIX}SELECTOR_CORRECTION_PROVENANCE.json"
)
REQUIRED_SELECTOR_CORRECTION_MEMBERS = (
    SELECTOR_CORRECTION_RECEIPT_MEMBER,
    SELECTOR_CORRECTION_MANIFEST_MEMBER,
    f"{SELECTOR_CORRECTION_PREFIX}README.md",
    f"{SELECTOR_CORRECTION_PREFIX}STAGING_VALIDATION.json",
    f"{SELECTOR_CORRECTION_PREFIX}pre_freeze_redim_selection_conflict.audit.json",
    f"{SELECTOR_CORRECTION_PREFIX}code/h2_prefreeze_selector_correction_bootstrap.py",
    f"{SELECTOR_CORRECTION_PREFIX}code/controller.py.patched",
    f"{SELECTOR_CORRECTION_PREFIX}code/controller.py.original",
    f"{SELECTOR_CORRECTION_PREFIX}code/h2_windows_atomic_retry_bootstrap.py",
    f"{SELECTOR_CORRECTION_PREFIX}tests/test_h2_product_program_controller.py.patched",
    f"{SELECTOR_CORRECTION_PREFIX}tests/test_prefreeze_selector_correction_bootstrap.py",
    f"{SELECTOR_CORRECTION_PREFIX}code/h2_atomic_retry_child_sitecustomize.py",
    SELECTOR_CORRECTION_PROVENANCE_MEMBER,
)
SELECTOR_CORRECTION_BINDING_MEMBERS = {
    "correction_bootstrap": REQUIRED_SELECTOR_CORRECTION_MEMBERS[5],
    "patched_controller": REQUIRED_SELECTOR_CORRECTION_MEMBERS[6],
    "original_controller": REQUIRED_SELECTOR_CORRECTION_MEMBERS[7],
    "windows_atomic_retry_bootstrap": REQUIRED_SELECTOR_CORRECTION_MEMBERS[8],
    "patched_controller_tests": REQUIRED_SELECTOR_CORRECTION_MEMBERS[9],
    "correction_bootstrap_tests": REQUIRED_SELECTOR_CORRECTION_MEMBERS[10],
    "windows_atomic_retry_child": REQUIRED_SELECTOR_CORRECTION_MEMBERS[11],
    "staging_validation": REQUIRED_SELECTOR_CORRECTION_MEMBERS[3],
    "correction_readme": REQUIRED_SELECTOR_CORRECTION_MEMBERS[2],
    "pre_freeze_conflict_audit": REQUIRED_SELECTOR_CORRECTION_MEMBERS[4],
    "protocol_manifest": "protocol/protocol_manifest.json",
    "job_manifest": "protocol/job_manifest.json",
    "prepared_runtime_identity": "protocol/runtime_implementation_identity.json",
}
OVERLAP_CONFIGURATIONS = (
    "INCLUDE_PREDICTED_OVERLAP",
    "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
)
OVERLAP_COMPOSITIONS = {
    "ALL_KNOWN": "KNOWN_KNOWN",
    "MIXED_KNOWN_UNKNOWN": "KNOWN_UNKNOWN",
    "ALL_UNKNOWN": "UNKNOWN_UNKNOWN",
}
OVERLAP_CONDITIONS = ("OVERLAP_PRESENT", "NO_OVERLAP_CONTROL")
OVERLAP_METRICS = (
    ("diarization", "miss_rate", "weighted_ratio"),
    ("identity", "stable_name_latency_sec", "weighted_ratio"),
    ("diarization", "merge_contamination_rate", "weighted_ratio"),
    ("identity", "wrong_known_time_sec", "sum"),
    ("identity", "stranger_false_known_time_sec", "sum"),
    ("identity", "identity_merge_count", "sum"),
    ("speaker_transcription", "word_speaker_label_accuracy", "weighted_ratio"),
    ("identity", "generic_known_time_sec", "sum"),
)
BOUNDARY_CONFIGURATIONS = tuple(
    f"BOUNDARY_CORRECTION_{correction_ms:04d}MS"
    for correction_ms in (0, 250, 500, 750, 1000)
)
EVIDENCE_TARGETS = (0.75, 1.5, 2.0, 3.0)
PARAGRAPH_POLICIES = (
    "T1_ASR_ENDPOINT_PUNCTUATION",
    "T2_PAUSE_ASR_ENDPOINT",
    "T3_PAUSE_ASR_SPEAKER_CHANGE",
    "T4_SPEAKER_CHANGE_DOMINANT",
)
PARAGRAPH_BOUNDARY_TOLERANCE_SEC = 0.50


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _safe_name(name: str) -> str:
    normalized = PurePosixPath(name).as_posix()
    if (
        not normalized
        or normalized != name
        or normalized.startswith("/")
        or "\\" in name
        or ":" in name
        or any(part in {"", ".", ".."} for part in PurePosixPath(name).parts)
    ):
        raise ValueError(f"unsafe ZIP member name: {name!r}")
    return normalized


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_zip(path: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("source ZIP CRC validation failed")
        for info in archive.infolist():
            name = _safe_name(info.filename)
            if info.is_dir() or info.flag_bits & 0x1:
                raise ValueError(
                    f"directory or encrypted member is not allowed: {name}"
                )
            folded = name.casefold()
            if any(existing.casefold() == folded for existing in payloads):
                raise ValueError(f"duplicate ZIP member name: {name}")
            payloads[name] = archive.read(info)
    return payloads


def _csv_rows(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _number(value: object) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_arm64_deployment_v2(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Build a deployment-only supersession without changing frozen evidence."""

    source_names = tuple(
        f"{ARM64_V2_SOURCE_PREFIX}{name}" for name in ARM64_PACKAGE_FILES
    )
    missing = [name for name in source_names if name not in source_payloads]
    if missing:
        raise ValueError(
            "native package lacks the frozen ARM64 deployment bundle: "
            + ", ".join(missing)
        )
    if RUNTIME_IDENTITY_MEMBER not in source_payloads:
        raise ValueError("native package lacks its runtime implementation identity")
    runtime_identity = json.loads(source_payloads[RUNTIME_IDENTITY_MEMBER])
    components = runtime_identity.get("components")
    if not isinstance(components, Mapping):
        raise ValueError("runtime implementation identity lacks component hashes")
    source_component_rows = {
        f"Software Validation from Datasets/Evaluation Tool/{name}": _sha256(
            source_payloads[name]
        )
        for name in source_names
    }
    source_component_sha = canonical_sha256(source_component_rows)
    if source_component_sha != components.get("h2_arm64_deployment_bundle"):
        raise ValueError("frozen ARM64 source bundle differs from runtime identity")

    generated: dict[str, bytes] = {}
    member_rows: list[dict[str, object]] = []
    for filename in ARM64_PACKAGE_FILES:
        source_name = f"{ARM64_V2_SOURCE_PREFIX}{filename}"
        output_name = f"{ARM64_V2_PREFIX}{filename}"
        source_payload = source_payloads[source_name]
        output_payload = source_payload
        if filename in {
            "Dockerfile.arm64",
            "h2-pipeline.service",
            "install_linux_arm64.sh",
            "README.md",
        }:
            text = source_payload.decode("utf-8").replace("\r\n", "\n")
            if filename == "h2-pipeline.service":
                working = (
                    "WorkingDirectory=/opt/just-peachy/Software Validation from "
                    "Datasets/Evaluation Tool"
                )
                start = (
                    "ExecStart=/opt/just-peachy/Software Validation from Datasets/"
                    "Evaluation Tool/deployment/h2_arm64/run_h2_service.sh"
                )
                if text.count(working) != 1 or text.count(start) != 1:
                    raise ValueError("frozen ARM64 systemd source shape differs")
                text = text.replace(working, f'WorkingDirectory="{working[17:]}"')
                text = text.replace(
                    start,
                    'ExecStart="/opt/just-peachy/Software Validation from Datasets/'
                    'Evaluation Tool/deployment/h2_arm64_v2/run_h2_service.sh"',
                )
            elif filename == "install_linux_arm64.sh":
                old = """\
"${PYTHON_BIN}" -m venv "${PREFIX}/venv"
VENV_PYTHON="${PREFIX}/venv/bin/python"
"${VENV_PYTHON}" -m pip install --upgrade "pip==24.2"

PIP_SOURCE=()
if [[ -n "${WHEELHOUSE}" ]]; then
  PIP_SOURCE=(--no-index --find-links "${WHEELHOUSE}")
fi
"${VENV_PYTHON}" -m pip install --only-binary=:all: \\
  "${PIP_SOURCE[@]}" -r "${SCRIPT_DIR}/requirements-linux-arm64.txt"
"""
                new = """\
"${PYTHON_BIN}" -m venv "${PREFIX}/venv"
VENV_PYTHON="${PREFIX}/venv/bin/python"
PIP_SOURCE=()
if [[ -n "${WHEELHOUSE}" ]]; then
  PIP_SOURCE=(--no-index --find-links "${WHEELHOUSE}")
fi
"${VENV_PYTHON}" -m pip install --only-binary=:all: \\
  "${PIP_SOURCE[@]}" --upgrade "pip==24.2"
"${VENV_PYTHON}" -m pip install --only-binary=:all: \\
  "${PIP_SOURCE[@]}" -r "${SCRIPT_DIR}/requirements-linux-arm64.txt"
"""
                if text.count(old) != 1:
                    raise ValueError("frozen ARM64 installer source shape differs")
                text = text.replace(old, new)
            elif filename == "Dockerfile.arm64":
                if text.count("deployment/h2_arm64/") < 2:
                    raise ValueError("frozen ARM64 Dockerfile source shape differs")
                text = text.replace("deployment/h2_arm64/", "deployment/h2_arm64_v2/")
            else:
                if "deployment/h2_arm64" not in text:
                    raise ValueError("frozen ARM64 README source shape differs")
                text = text.replace("deployment/h2_arm64", "deployment/h2_arm64_v2")
                offline = "system and pass `--wheelhouse /path/to/wheels`.\n"
                if text.count(offline) != 1:
                    raise ValueError("frozen ARM64 offline instructions differ")
                text = text.replace(
                    offline,
                    offline
                    + "The wheelhouse must include `pip==24.2` as well as every "
                    "pinned runtime wheel; both installation commands then use "
                    "`--no-index`.\n",
                )
                service_note = (
                    "are design guards, not evidence that the pipeline fits.\n"
                )
                if text.count(service_note) != 1:
                    raise ValueError("frozen ARM64 service instructions differ")
                text = text.replace(
                    service_note,
                    service_note
                    + "The v2 systemd unit quotes paths containing spaces and points "
                    "to the v2 launch script.\n",
                )
            output_payload = text.encode("utf-8")
        generated[output_name] = output_payload
        member_rows.append(
            {
                "source_member": source_name,
                "source_sha256": _sha256(source_payload),
                "v2_member": output_name,
                "v2_sha256": _sha256(output_payload),
                "bytes": len(output_payload),
                "changed": output_payload != source_payload,
            }
        )

    service_text = generated[f"{ARM64_V2_PREFIX}h2-pipeline.service"].decode("utf-8")
    installer_text = generated[f"{ARM64_V2_PREFIX}install_linux_arm64.sh"].decode(
        "utf-8"
    )
    docker_text = generated[f"{ARM64_V2_PREFIX}Dockerfile.arm64"].decode("utf-8")
    readme_text = generated[f"{ARM64_V2_PREFIX}README.md"].decode("utf-8")
    if (
        'WorkingDirectory="/opt/just-peachy/Software Validation from Datasets/'
        'Evaluation Tool"'
        not in service_text
        or 'deployment/h2_arm64_v2/run_h2_service.sh"' not in service_text
        or installer_text.count("${PIP_SOURCE[@]}") != 2
        or installer_text.index("PIP_SOURCE=()")
        > installer_text.index("pip install --only-binary=:all:")
        or "deployment/h2_arm64/" in docker_text
        or docker_text.count("deployment/h2_arm64_v2/") < 2
        or "deployment/h2_arm64_v2" not in readme_text
        or "both installation commands then use `--no-index`" not in readme_text
    ):
        raise ValueError("ARM64 deployment-v2 safety corrections were not applied")

    provenance = {
        "schema_version": "h2-arm64-deployment-v2-provenance.v1",
        "status": "PREPARED_NOT_HARDWARE_VALIDATED",
        "source_runtime_implementation_identity_sha256": runtime_identity.get(
            "identity_sha256"
        ),
        "source_arm64_component_sha256": source_component_sha,
        "source_native_members_preserved": True,
        "deployment_only_supersession": True,
        "scientific_runtime_or_policy_changed": False,
        "scientific_results_recomputed": False,
        "heldout_evidence_inspected_for_deployment_changes": False,
        "systemd_space_path_quoting_fixed": True,
        "systemd_v2_launch_path_fixed": True,
        "offline_wheelhouse_applies_to_pip_bootstrap_and_dependencies": True,
        "implicit_model_downloads_allowed": False,
        "linux_arm64_ready_claimed": False,
        "arm64_hardware_validated": False,
        "candidate_classification": "PORT_REQUIRES_WORK",
        "v2_member_count": len(generated),
        "members": member_rows,
    }
    guide = "\n".join(
        [
            "# H2 ARM64 deployment-v2 supersession",
            "",
            "Use `deployment/h2_arm64_v2/` for future Raspberry Pi / ARM64 work.",
            "The original `deployment/h2_arm64/` directory is retained byte-for-byte",
            "because it is part of the frozen v16 implementation identity.",
            "",
            "Deployment v2 fixes quoting for repository paths containing spaces,",
            "points systemd and Docker at the v2 launcher, and makes the documented",
            "offline wheelhouse apply to both the pinned pip bootstrap and runtime",
            "dependencies. It does not alter models, thresholds, scientific results,",
            "or selection. It remains `PORT_REQUIRES_WORK` until real ARM64 hardware",
            "passes loading, audio, parity, resource, restart, and sustained-stream tests.",
            "",
        ]
    ).encode("utf-8")
    generated[ARM64_V2_GUIDE_MEMBER] = guide
    generated[ARM64_V2_PROVENANCE_MEMBER] = _canonical_json(provenance)
    return generated, provenance


def _validate_arm64_deployment_v2_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_ARM64_V2_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks ARM64 deployment-v2 members: " + ", ".join(missing)
        )
    expected, provenance = build_arm64_deployment_v2(payloads)
    if any(payloads.get(name) != value for name, value in expected.items()):
        raise ValueError("ARM64 deployment-v2 rendering or source binding differs")
    packaged = json.loads(payloads[ARM64_V2_PROVENANCE_MEMBER])
    if packaged != provenance:
        raise ValueError("ARM64 deployment-v2 provenance differs")
    if (
        provenance.get("deployment_only_supersession") is not True
        or provenance.get("scientific_runtime_or_policy_changed") is not False
        or provenance.get("source_native_members_preserved") is not True
        or provenance.get("systemd_space_path_quoting_fixed") is not True
        or provenance.get(
            "offline_wheelhouse_applies_to_pip_bootstrap_and_dependencies"
        )
        is not True
        or provenance.get("linux_arm64_ready_claimed") is not False
        or provenance.get("arm64_hardware_validated") is not False
        or provenance.get("candidate_classification") != "PORT_REQUIRES_WORK"
    ):
        raise ValueError("ARM64 deployment-v2 qualification boundary differs")
    return provenance


def _computed_metric_map(
    rows: Sequence[Mapping[str, str]],
    *,
    metric_id: str,
) -> dict[str, float]:
    output: dict[str, float] = {}
    for row in rows:
        if row.get("metric_id") != metric_id:
            continue
        status = str(row.get("metric_status") or row.get("status") or "").casefold()
        if status not in {"computed", "measured", "complete"}:
            continue
        value = _number(row.get("value"))
        label = str(
            row.get("configuration_id")
            or row.get("mode")
            or row.get("policy_id")
            or row.get("job_id")
            or ""
        ).strip()
        if value is not None and label:
            output[label] = value
    return output


def build_final_recommendation_supplement(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Bind the three requested product roles to the frozen final evidence."""

    registry_name = "summary/h2_configuration_registry.yaml"
    memory_name = "summary/h2_memory_budget.json"
    linux_name = "summary/h2_linux_portability.json"
    for name in (registry_name, memory_name, linux_name):
        if name not in source_payloads:
            raise ValueError(f"final recommendation source is missing: {name}")
    registry = yaml.safe_load(source_payloads[registry_name])
    memory = json.loads(source_payloads[memory_name])
    linux = json.loads(source_payloads[linux_name])
    if not isinstance(registry, Mapping):
        raise ValueError("final recommendation registry is invalid")
    configurations = registry.get("configurations")
    if not isinstance(configurations, list):
        raise ValueError("final recommendation registry lacks configurations")
    configuration_by_id = {
        str(row.get("configuration_id")): row
        for row in configurations
        if isinstance(row, Mapping) and row.get("configuration_id")
    }
    required_ids = {
        "H2_BASELINE_REFERENCE",
        "H2_KNOWN_ONLY_OPTIMIZED",
        "H2_SESSION_ANONYMOUS_OPTIMIZED",
        "H2_SESSION_MEMORY_OPTIMIZED",
        "H2_PORTABLE_ONNX_FP32",
    }
    if set(configuration_by_id) != required_ids:
        raise ValueError("final recommendation configuration membership differs")
    portable_status = str(
        configuration_by_id["H2_PORTABLE_ONNX_FP32"].get("status") or ""
    )
    if portable_status != (
        "FROZEN_PORTABLE_CANDIDATE_PARITY_VALIDATED_NOT_ARM64_HARDWARE_VALIDATED"
    ):
        raise ValueError("portable recommendation lacks frozen parity status")
    default_mode = str(registry.get("default_product_mode") or "")
    optimized_by_mode = {
        "H2_KNOWN_ONLY": "H2_KNOWN_ONLY_OPTIMIZED",
        "H2_SESSION_ANONYMOUS": "H2_SESSION_ANONYMOUS_OPTIMIZED",
        "H2_SESSION_MEMORY_ENHANCED": "H2_SESSION_MEMORY_OPTIMIZED",
    }
    primary_id = optimized_by_mode.get(default_mode)
    if primary_id is None:
        raise ValueError("final recommendation lacks a frozen default product mode")
    selection = registry.get("default_product_mode_selection")
    if (
        not isinstance(selection, Mapping)
        or selection.get("selected_default_mode") != default_mode
        or selection.get("development_only") is not True
        or selection.get("evaluation_material_inspected") is not False
        or selection.get("weighted_composite_used") is not False
    ):
        raise ValueError("final recommendation default-mode firewall differs")
    memory_classification = str(memory.get("classification") or "")
    linux_classification = str(linux.get("candidate_classification") or "")
    if memory_classification not in {
        "HIGH_RISK_FOR_2GB",
        "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION",
    }:
        raise ValueError("final recommendation memory classification differs")
    if (
        linux.get("status") != "PREPARED_NOT_HARDWARE_VALIDATED"
        or linux_classification != "PORT_REQUIRES_WORK"
        or linux.get("linux_arm64_ready_claimed") is not False
        or linux.get("raspberry_pi_hardware_validated") is not False
    ):
        raise ValueError("final recommendation ARM64 qualification boundary differs")

    source_bindings = {
        name: _sha256(source_payloads[name])
        for name in (registry_name, memory_name, linux_name)
    }
    roles = [
        {
            "role": "DESKTOP_REFERENCE",
            "configuration_id": "H2_BASELINE_REFERENCE",
            "mode": configuration_by_id["H2_BASELINE_REFERENCE"].get("mode"),
            "recommendation_status": "REFERENCE_ONLY",
            "reason": (
                "Historical-equivalent native desktop baseline retained for "
                "scientific comparison; it is not the default product UX."
            ),
        },
        {
            "role": "PRODUCT_SOFTWARE_PRIMARY",
            "configuration_id": primary_id,
            "mode": default_mode,
            "recommendation_status": "FROZEN_DEVELOPMENT_SELECTION",
            "reason": (
                "Maps the checksum-frozen development-only default-mode "
                "selection to its optimized native configuration; held-out "
                "results did not retune this choice."
            ),
        },
        {
            "role": "2GB_ARM64_CANDIDATE",
            "configuration_id": "H2_PORTABLE_ONNX_FP32",
            "mode": configuration_by_id["H2_PORTABLE_ONNX_FP32"].get("mode"),
            "recommendation_status": "PREPARED_NOT_HARDWARE_VALIDATED",
            "memory_classification": memory_classification,
            "linux_arm64_classification": linux_classification,
            "deployment_bundle_prefix": ARM64_V2_PREFIX,
            "deployment_supersession_provenance_member": (ARM64_V2_PROVENANCE_MEMBER),
            "reason": (
                "Fresh frozen FP32 parity qualifies a portable candidate, but "
                "the exact 2 GiB ARM64 board still requires model loading, audio, "
                "numerical parity, sustained-streaming, memory, and recovery tests."
            ),
        },
    ]
    document: dict[str, object] = {
        "schema_version": "h2-final-recommendations.v1",
        "status": "COMPLETE_RECOMMENDATIONS",
        "scientific_runtime_or_frozen_policy_changed": False,
        "heldout_results_used_for_retuning": False,
        "arm64_hardware_validated": False,
        "source_bindings": source_bindings,
        "roles": roles,
    }
    markdown = [
        "# H2 final operating recommendations",
        "",
        "These roles summarize the frozen program; they do not alter any "
        "measurement, policy, or selection.",
        "",
        "| Role | Configuration | Status |",
        "|---|---|---|",
    ]
    markdown.extend(
        f"| `{row['role']}` | `{row['configuration_id']}` | "
        f"`{row['recommendation_status']}` |"
        for row in roles
    )
    markdown.extend(
        [
            "",
            "The desktop reference is a comparison baseline, while the product "
            "primary follows the development-frozen default mode. The ARM64 "
            "candidate is prepared software only and is not Raspberry Pi or "
            "Compute Module hardware validation.",
            "",
            f"2 GiB assessment: `{memory_classification}`.",
            "",
            f"Linux ARM64 assessment: `{linux_classification}`.",
            "",
            f"Use the superseding `{ARM64_V2_PREFIX}` package; the original "
            "ARM64 directory is retained only as frozen v16 provenance.",
            "",
        ]
    )
    payloads = {
        REQUIRED_RECOMMENDATION_MEMBERS[0]: _canonical_json(document),
        REQUIRED_RECOMMENDATION_MEMBERS[1]: "\n".join(markdown).encode("utf-8"),
    }
    return payloads, document


def build_hardware_platform_assessment(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Compare CM5 and UNO Q without promoting desktop evidence to ARM64 proof."""

    source_names = (
        "summary/h2_configuration_registry.yaml",
        "summary/h2_memory_budget.json",
        "summary/h2_linux_portability.json",
        "summary/h2_resource_results.csv",
    )
    missing = [name for name in source_names if name not in source_payloads]
    if missing:
        raise ValueError(
            "hardware-platform assessment source is missing: " + ", ".join(missing)
        )
    registry = yaml.safe_load(source_payloads["summary/h2_configuration_registry.yaml"])
    memory = json.loads(source_payloads["summary/h2_memory_budget.json"])
    linux = json.loads(source_payloads["summary/h2_linux_portability.json"])
    if not isinstance(registry, Mapping):
        raise ValueError("hardware-platform configuration registry is invalid")
    if (
        memory.get("analysis_schema_version") != "h2-memory-budget-analysis.v1"
        or linux.get("schema_version") != "h2-linux-portability-analysis.v1"
        or linux.get("raspberry_pi_hardware_validated") is not False
        or linux.get("arduino_uno_q_linux_hardware_validated") is not False
    ):
        raise ValueError("hardware-platform ARM64 evidence boundary differs")

    resource_rows = _csv_rows(source_payloads["summary/h2_resource_results.csv"])

    def measurements(metric_id: str) -> list[float]:
        output = []
        for row in resource_rows:
            if row.get("metric_id") != metric_id:
                continue
            status = str(row.get("metric_status") or row.get("status") or "").casefold()
            value = _number(row.get("value"))
            if status in {"computed", "measured", "complete"} and value is not None:
                output.append(value)
        return output

    rss_values = measurements("peak_rss_bytes")
    rtf_values = measurements("total_rtf")
    model_byte_values = measurements("model_bytes")
    cache_byte_values = measurements("cache_bytes")
    if (
        not rss_values
        or not rtf_values
        or not model_byte_values
        or not cache_byte_values
    ):
        raise ValueError(
            "hardware-platform assessment requires serial RSS, RTF, model-byte, "
            "and cache-byte measurements"
        )
    measured_peak_rss_bytes = max(rss_values)
    measured_best_total_rtf = min(rtf_values)
    measured_worst_total_rtf = max(rtf_values)
    measured_model_bytes = max(model_byte_values)
    measured_cache_bytes = max(cache_byte_values)
    if memory.get("desktop_serial_peak_rss_bytes") != measured_peak_rss_bytes:
        raise ValueError("hardware-platform desktop RSS binding differs")
    memory_classification = str(memory.get("classification") or "")
    if memory_classification not in {
        "HIGH_RISK_FOR_2GB",
        "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION",
    }:
        raise ValueError("hardware-platform 2 GiB classification differs")

    two_gib_bytes = 2 * 1024**3
    two_gib_headroom_bytes = two_gib_bytes - measured_peak_rss_bytes
    cm5_two_gib_candidate = (
        memory_classification == "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION"
    )
    if cm5_two_gib_candidate:
        cm5_ram_recommendation = "TEST_2GB_LEAN_ONNX_FIRST_WITH_4GB_FALLBACK"
        cm5_two_gib_role = "FIRST_LEAN_ARM64_SIZING_TARGET"
        cm5_four_gib_role = "SAFE_FALLBACK_AND_DEVELOPMENT_TARGET"
        cm5_two_gib_memory = (
            "Desktop serial peak RSS is below the frozen 1700 MiB risk boundary. "
            "Because the intended display is a simple 2D UI, 2GB is a legitimate "
            "lean-ONNX target candidate, but the OS, audio services, UI process, "
            "queues, allocator behavior, and ARM runtime still require whole-board "
            "measurement without swap."
        )
        cm5_four_gib_memory = (
            "4GB is not proven necessary by the desktop serial RSS result. It is "
            "the safer development/fallback capacity if the exact 2GB image fails "
            "startup, no-swap, deadline, restart-spike, or 60-minute soak gates."
        )
        cm5_decision_reason = (
            "The simple graphics workload does not by itself justify 4GB. The "
            "measured audio-pipeline RSS keeps CM5 2GB eligible for the first lean "
            "ONNX hardware sizing run; CM5 4GB remains the fallback until 2GB passes "
            "whole-system memory, real-time, restart, and sustained-streaming gates."
        )
    else:
        cm5_ram_recommendation = "START_WITH_4GB_KEEP_2GB_AS_OPTIMIZATION_EXPERIMENT"
        cm5_two_gib_role = "OPTIMIZATION_EXPERIMENT_ONLY"
        cm5_four_gib_role = "PRIMARY_ARM64_VALIDATION_TARGET"
        cm5_two_gib_memory = (
            "Desktop serial peak RSS exceeds the frozen 1700 MiB risk boundary. "
            "A simple display does not recover enough guaranteed headroom for the "
            "OS, audio services, queues, allocator spikes, and restart behavior, so "
            "2GB remains an optimization experiment rather than the first target."
        )
        cm5_four_gib_memory = (
            "4GB is the recommended initial validation capacity because desktop "
            "audio-pipeline RSS leaves insufficient conservative 2GB headroom. "
            "This is a risk-based recommendation, not proof that an optimized 2GB "
            "ARM64 build cannot work."
        )
        cm5_decision_reason = (
            "The audio pipeline, not the simple graphics workload, drives memory. "
            "Measured desktop RSS crosses the conservative 2GB risk boundary, so "
            "CM5 4GB should be validated first while CM5 2GB remains a later lean "
            "ONNX optimization experiment."
        )

    common = {
        "portable_pipeline_id": "H2_PORTABLE_ONNX_FP32",
        "portable_precision": "FP32",
        "measured_desktop_peak_rss_bytes": measured_peak_rss_bytes,
        "measured_desktop_best_total_rtf": measured_best_total_rtf,
        "measured_desktop_worst_total_rtf": measured_worst_total_rtf,
        "measured_desktop_model_bytes": measured_model_bytes,
        "measured_desktop_cache_bytes": measured_cache_bytes,
        "desktop_memory_classification": memory_classification,
        "hardware_validated": False,
        "scientific_ranking_changed": False,
        "accelerator_performance_assumed": False,
        "graphics_workload_assumption": "SIMPLE_2D_UI_LOW_GRAPHICS_MEMORY_DEMAND",
        "sizing_workload_driver": "AUDIO_PIPELINE_MODELS_QUEUES_AND_RUNTIME",
        "cm5_4gb_proven_necessary": False,
    }
    rows: list[dict[str, object]] = [
        {
            **common,
            "platform_id": "RASPBERRY_PI_COMPUTE_MODULE_5",
            "variant": "2GB_RAM",
            "soc": "Broadcom BCM2712",
            "cpu": "4x Arm Cortex-A76 at 2.4 GHz",
            "ram_mib": 2048,
            "storage": "16/32/64GB eMMC or carrier storage",
            "linux": "Raspberry Pi OS or Debian ARM64",
            "expected_classification": "PORT_REQUIRES_WORK",
            "native_pipeline_feasibility": "PLATFORM_BLOCKER",
            "portable_onnx_feasibility": "PORT_REQUIRES_WORK",
            "cpu_feasibility": (
                "Same preferred CM5 CPU as the larger-RAM variant; target RTF is "
                "unmeasured and is independent of the RAM-capacity decision."
            ),
            "memory_feasibility": cm5_two_gib_memory,
            "storage_feasibility": (
                "Use a measured lean OS image and retain only runtime assets, "
                "bounded logs, and rollback reserve. Scientific reconstruction maps "
                "do not require permanent device caches."
            ),
            "runtime_compatibility": (
                "Only the shared-worker lean FP32 ONNX service is a candidate; "
                "native PyTorch, duplicate model workers, and implicit downloads "
                "are excluded from the 2GB target."
            ),
            "audio_integration": (
                "Carrier USB audio or I2S is available; ALSA capture, reconnect, "
                "queue pressure, and audio-service resident memory require the exact "
                "2GB image test."
            ),
            "display_integration": (
                "A simple local 2D status/transcript UI is the assumption. Its real "
                "desktop compositor/framebuffer/process RSS must be included in the "
                "whole-system no-swap measurement; graphics inference is not used."
            ),
            "accelerator_status": (
                "CPU execution is the reference path; no GPU/NPU memory or speed "
                "relief is assumed."
            ),
            "recommended_role": cm5_two_gib_role,
            "evidence_limit": "NOT_RUN_ON_CM5_2GB",
        },
        {
            **common,
            "platform_id": "RASPBERRY_PI_COMPUTE_MODULE_5",
            "variant": "4GB_OR_GREATER",
            "soc": "Broadcom BCM2712",
            "cpu": "4x Arm Cortex-A76 at 2.4 GHz",
            "ram_mib": "4096-16384",
            "storage": "16/32/64GB eMMC or carrier storage",
            "linux": "Raspberry Pi OS or Debian ARM64",
            "expected_classification": "LIKELY_PORTABLE",
            "native_pipeline_feasibility": "PORT_REQUIRES_WORK",
            "portable_onnx_feasibility": "LIKELY_PORTABLE",
            "cpu_feasibility": (
                "Preferred CPU candidate; newer Cortex-A76 cores and higher clock "
                "than UNO Q, but no cross-board RTF is inferred."
            ),
            "memory_feasibility": (cm5_four_gib_memory),
            "storage_feasibility": (
                "Prefer 32GB or 64GB eMMC, or validated carrier storage. The 16GB "
                "variant is not rejected by desktop evidence, but OS, wheels, model "
                "assets, logs, updates, and rollback headroom must be measured on the "
                "final image before deployment."
            ),
            "runtime_compatibility": (
                "Sherpa-ONNX supports Linux aarch64; the portable FP32 bundle "
                "still requires target wheel, model-load, and numerical-parity tests."
            ),
            "audio_integration": (
                "Carrier USB audio and I2S are available; ALSA device enumeration, "
                "capture continuity, and reconnect remain hardware tests."
            ),
            "display_integration": (
                "Carrier HDMI and MIPI-DSI are mature options; GUI scanout and "
                "touch behavior remain outside desktop evidence."
            ),
            "accelerator_status": (
                "CPU execution is the reference deployment path; no GPU/NPU speedup "
                "is assumed."
            ),
            "recommended_role": cm5_four_gib_role,
            "evidence_limit": "NOT_RUN_ON_CM5",
        },
        {
            **common,
            "platform_id": "ARDUINO_UNO_Q",
            "variant": "4GB_RAM_32GB_EMMC",
            "soc": "Qualcomm Dragonwing QRB2210 plus STM32U585",
            "cpu": "4x Arm Cortex-A53 at 2.0 GHz",
            "ram_mib": 4096,
            "storage": "32GB eMMC",
            "linux": "Arduino Debian Linux",
            "expected_classification": "PORT_REQUIRES_WORK",
            "native_pipeline_feasibility": "PORT_REQUIRES_WORK",
            "portable_onnx_feasibility": "PORT_REQUIRES_WORK",
            "cpu_feasibility": (
                "Expected to be materially slower than CM5 from CPU architecture "
                "alone; actual end-to-end RTF must be measured."
            ),
            "memory_feasibility": (
                "4GB is plausible for the lean ONNX service and is Arduino's "
                "recommended standalone/SBC variant."
            ),
            "storage_feasibility": (
                "32GB eMMC is the minimum plausible self-contained target. The final "
                "gate must measure free bytes after the Debian image, pinned runtime, "
                "all referenced model assets, logs, and rollback reserve; desktop "
                "cache sizes are not treated as permanent device requirements."
            ),
            "runtime_compatibility": (
                "Generic Linux aarch64 Sherpa/ONNX paths are plausible, but the "
                "exact Debian image, Python ABI, wheels, and operators are unverified."
            ),
            "audio_integration": (
                "USB microphone/headphones are documented through a powered USB-C "
                "dongle; JMISC analog audio exists but needs a carrier/codec path."
            ),
            "display_integration": (
                "USB-C video and MIPI-DSI carrier pins are documented; powered-dongle "
                "and GUI behavior require an integrated test."
            ),
            "accelerator_status": (
                "QRB2210 acceleration is not credited: ONNX Runtime documents QNN "
                "for Android/Windows, not this Debian target."
            ),
            "recommended_role": "SECONDARY_PORTABILITY_PROTOTYPE",
            "evidence_limit": "NOT_RUN_ON_UNO_Q_4GB",
        },
        {
            **common,
            "platform_id": "ARDUINO_UNO_Q",
            "variant": "2GB_RAM_16GB_EMMC",
            "soc": "Qualcomm Dragonwing QRB2210 plus STM32U585",
            "cpu": "4x Arm Cortex-A53 at 2.0 GHz",
            "ram_mib": 2048,
            "storage": "16GB eMMC",
            "linux": "Arduino Debian Linux",
            "expected_classification": "PLATFORM_BLOCKER",
            "native_pipeline_feasibility": "PLATFORM_BLOCKER",
            "portable_onnx_feasibility": "PORT_REQUIRES_WORK",
            "cpu_feasibility": (
                "Same unmeasured A53 CPU risk as the 4GB board, with no room to "
                "mask missed real-time deadlines through buffering."
            ),
            "memory_feasibility": (
                "Only the lean ONNX-only service is a candidate. Native PyTorch, "
                "desktop GUI, and duplicate model workers are excluded."
            ),
            "storage_feasibility": (
                "16GB eMMC is high risk for a self-contained image. A headless lean "
                "runtime, bounded transient caches, explicit log rotation, and a "
                "measured update/rollback reserve are mandatory; no exact fit is "
                "claimed from the desktop package."
            ),
            "runtime_compatibility": (
                "Requires the pinned ARM64 wheel set, one shared embedding worker, "
                "bounded queues, no implicit downloads, and swap-free soak proof."
            ),
            "audio_integration": (
                "Use a powered USB-C audio path or a validated carrier; concurrent "
                "audio/display/USB bandwidth and disconnect recovery are untested."
            ),
            "display_integration": (
                "Headless service is recommended; a local desktop UI would consume "
                "the RAM headroom required by the speech pipeline."
            ),
            "accelerator_status": (
                "No Qualcomm GPU/HTP relief is assumed without Debian driver, "
                "operator, conversion, quantization, and parity validation."
            ),
            "recommended_role": "HIGH_RISK_LEAN_ONNX_EXPERIMENT_ONLY",
            "evidence_limit": "NOT_RUN_ON_UNO_Q_2GB",
        },
    ]
    fields = (
        "platform_id",
        "variant",
        "soc",
        "cpu",
        "ram_mib",
        "storage",
        "linux",
        "expected_classification",
        "native_pipeline_feasibility",
        "portable_onnx_feasibility",
        "cpu_feasibility",
        "memory_feasibility",
        "storage_feasibility",
        "runtime_compatibility",
        "audio_integration",
        "display_integration",
        "accelerator_status",
        "recommended_role",
        "evidence_limit",
        "portable_pipeline_id",
        "portable_precision",
        "measured_desktop_peak_rss_bytes",
        "measured_desktop_best_total_rtf",
        "measured_desktop_worst_total_rtf",
        "measured_desktop_model_bytes",
        "measured_desktop_cache_bytes",
        "desktop_memory_classification",
        "hardware_validated",
        "scientific_ranking_changed",
        "accelerator_performance_assumed",
        "graphics_workload_assumption",
        "sizing_workload_driver",
        "cm5_4gb_proven_necessary",
    )
    source_bindings = {name: _sha256(source_payloads[name]) for name in source_names}
    decision = {
        "primary_hardware_family": "RASPBERRY_PI_COMPUTE_MODULE_5",
        "primary_hardware_target": (
            "RASPBERRY_PI_COMPUTE_MODULE_5_2GB_LEAN_ONNX"
            if cm5_two_gib_candidate
            else "RASPBERRY_PI_COMPUTE_MODULE_5_4GB_OR_GREATER"
        ),
        "cm5_ram_recommendation": cm5_ram_recommendation,
        "cm5_2gb_candidate": cm5_two_gib_candidate,
        "cm5_4gb_proven_necessary": False,
        "cm5_2gb_desktop_headroom_bytes": two_gib_headroom_bytes,
        "graphics_workload_assumption": "SIMPLE_2D_UI_LOW_GRAPHICS_MEMORY_DEMAND",
        "sizing_workload_driver": "AUDIO_PIPELINE_MODELS_QUEUES_AND_RUNTIME",
        "secondary_hardware_target": "ARDUINO_UNO_Q_4GB",
        "conditional_experiment": "ARDUINO_UNO_Q_2GB_LEAN_ONNX_ONLY",
        "reason": cm5_decision_reason
        + (
            " CM5 remains preferable to UNO Q from expected CPU and Linux carrier "
            "maturity. UNO Q 4GB remains a secondary measured prototype and UNO Q "
            "2GB remains a high-risk lean-ONNX experiment."
        ),
    }
    document: dict[str, object] = {
        "schema_version": "h2-hardware-platform-assessment.v2",
        "status": "EXPECTED_FEASIBILITY_NOT_HARDWARE_VALIDATION",
        "review_date": "2026-08-31",
        "desktop_evidence_used": True,
        "arm64_hardware_measurements_present": False,
        "scientific_runtime_or_policy_changed": False,
        "desktop_scientific_ranking_changed": False,
        "qnn_debian_acceleration_claimed": False,
        "source_bindings": source_bindings,
        "official_source_urls": dict(HARDWARE_PLATFORM_SOURCE_URLS),
        "measured_desktop_bounds": {
            "peak_rss_bytes": measured_peak_rss_bytes,
            "best_total_rtf": measured_best_total_rtf,
            "worst_total_rtf": measured_worst_total_rtf,
            "model_bytes": measured_model_bytes,
            "cache_bytes": measured_cache_bytes,
            "memory_classification": memory_classification,
            "cm5_2gb_headroom_bytes_before_os_ui_audio_services": (
                two_gib_headroom_bytes
            ),
        },
        "decision": decision,
        "platforms": rows,
        "remaining_target_tests": [
            "OS image and aarch64 wheel resolution",
            "all model loads and numerical parity",
            "USB/ALSA capture and device reconnect",
            "display/UI operation or headless service behavior",
            "simple-UI compositor/framebuffer/process RSS on CM5 2GB",
            "cold start, peak whole-system RAM, and swap behavior",
            "true streaming RTF, deadline misses, and dropped frames",
            "worker restart, clean shutdown, and repeated sessions",
            "60-minute sustained stream, active-cooling behavior, thermal "
            "throttling, and runtime drift",
        ],
    }
    markdown = [
        "# H2 hardware-platform assessment",
        "",
        "This is an expected-feasibility comparison derived after the scientific "
        "campaign. It does not change the frozen desktop ranking and is not a "
        "claim that any ARM64 board has run the pipeline.",
        "",
        "| Platform | Expected class | Native pipeline | Portable FP32 ONNX | Role |",
        "|---|---|---|---|---|",
    ]
    markdown.extend(
        f"| `{row['platform_id']} {row['variant']}` | "
        f"`{row['expected_classification']}` | "
        f"`{row['native_pipeline_feasibility']}` | "
        f"`{row['portable_onnx_feasibility']}` | "
        f"`{row['recommended_role']}` |"
        for row in rows
    )
    markdown.extend(
        [
            "",
            f"Measured desktop peak RSS bound: "
            f"`{measured_peak_rss_bytes / 1024**2:.1f} MiB`.",
            "",
            f"Measured desktop serial total-RTF range: "
            f"`{measured_best_total_rtf:.4f}` to "
            f"`{measured_worst_total_rtf:.4f}`. These values are not extrapolated "
            "numerically to ARM64 CPUs.",
            "",
            "The CM5 sustained-stream test must include the intended production "
            "cooler and enclosure. Raspberry Pi documents thermal throttling under "
            "heavy continuous Raspberry Pi 5 loads, so an uncooled burst result is "
            "not accepted as evidence of long-session speech performance.",
            "",
            f"Measured checksum-bound model-asset footprint: "
            f"`{measured_model_bytes / 1024**3:.3f} GiB` (maximum across the "
            "serial configurations).",
            "",
            f"Measured desktop run-cache footprint: "
            f"`{measured_cache_bytes / 1024**3:.3f} GiB` (maximum across the "
            "serial configurations). This is reported for sizing evidence and is "
            "not treated as permanently required device storage.",
            "",
            "## CM5 2GB versus 4GB RAM decision",
            "",
            f"Recommendation: `{cm5_ram_recommendation}`.",
            "",
            "The intended graphics workload is a simple 2D transcript/status UI; "
            "there is no graphics inference workload. RAM sizing is therefore "
            "driven primarily by the ASR, segmentation, shared ReDimNet worker, "
            "audio services, queues, allocator/startup spikes, and OS/UI reserve.",
            "",
            f"Desktop peak RSS leaves `{two_gib_headroom_bytes / 1024**2:.1f} MiB` "
            "relative to 2 GiB before target OS, audio-service, UI, and ARM-runtime "
            "differences. CM5 4GB is not declared necessary until the exact CM5 "
            "2GB lean image either fails or passes the stated target gates.",
            "",
            "## Decision",
            "",
            decision["reason"],
            "",
            "## Platform detail",
            "",
        ]
    )
    for row in rows:
        markdown.extend(
            [
                f"### {row['platform_id']} — {row['variant']}",
                "",
                f"- **CPU:** {row['cpu']} — {row['cpu_feasibility']}",
                f"- **RAM:** {row['ram_mib']} MiB — {row['memory_feasibility']}",
                f"- **Storage:** {row['storage']} — {row['storage_feasibility']}",
                f"- **Runtime:** {row['runtime_compatibility']}",
                f"- **Audio:** {row['audio_integration']}",
                f"- **Display:** {row['display_integration']}",
                f"- **Acceleration:** {row['accelerator_status']}",
                f"- **Evidence boundary:** `{row['evidence_limit']}`.",
                "",
            ]
        )
    markdown.extend(
        [
            "## Important accelerator boundary",
            "",
            "The QRB2210 GPU/HTP is not credited. Current ONNX Runtime QNN "
            "documentation describes Android and Windows targets, so a Debian "
            "UNO Q acceleration claim would require a separate supported runtime, "
            "drivers, model conversion, operator audit, quantization study, and "
            "end-to-end parity run.",
            "",
            "## Remaining target validation",
            "",
        ]
    )
    markdown.extend(f"- {item}" for item in document["remaining_target_tests"])
    markdown.extend(
        [
            "",
            "## Official sources",
            "",
        ]
    )
    markdown.extend(
        f"- [{name}]({url})" for name, url in HARDWARE_PLATFORM_SOURCE_URLS.items()
    )
    markdown.append("")
    payloads = {
        REQUIRED_HARDWARE_PLATFORM_MEMBERS[0]: _csv_payload(rows, fields),
        REQUIRED_HARDWARE_PLATFORM_MEMBERS[1]: "\n".join(markdown).encode("utf-8"),
        REQUIRED_HARDWARE_PLATFORM_MEMBERS[2]: _canonical_json(document),
    }
    return payloads, document


def _render_streaming_execution_provenance(
    document: Mapping[str, object],
) -> bytes:
    qualification = document["qualification"]
    if not isinstance(qualification, Mapping):
        raise ValueError("streaming qualification disclosure is invalid")
    origins = qualification["asr_execution_origins"]
    if not isinstance(origins, Mapping):
        raise ValueError("streaming qualification origins are invalid")
    fresh_resource_rows = document["fresh_decode_serial_resource_evidence"]
    if not isinstance(fresh_resource_rows, list):
        raise ValueError("fresh streaming resource evidence is invalid")
    lines = [
        "# H2 streaming execution provenance",
        "",
        "This disclosure narrows the meaning of the Phase-0 `true streaming` "
        "label. It does not change a scientific result, promotion, frozen policy, "
        "or pipeline ranking.",
        "",
        "## What the qualification proved",
        "",
        "- The common causal coordinator consumed ordered 100 ms external-media "
        "frames through the file-simulation path.",
        "- Native Sherpa partial/final/reset interactions were delivered at their "
        "checksum-bound normalized-audio horizons.",
        "- Segmentation, clustering, identity, transcript alignment, queueing, and "
        "session-state logic ran through the common coordinator.",
        "",
        "## What it did not prove",
        "",
        "- It was not a physical-microphone capture.",
        "- It was not real-time 1.0x pacing.",
        "- It was not an eligible resource or target-hardware benchmark.",
        "- A replayed ASR trace is not a fresh native decoder invocation in that "
        "consumer job, even though its interactions originated from a complete "
        "native stateful stream and preserve the recorded native decode latency.",
        "",
        "## Bound qualification result",
        "",
        f"- Job: `{qualification['job_id']}`",
        f"- Result SHA-256: `{qualification['source_result_sha256']}`",
        f"- Cases: `{qualification['case_count']}`",
        f"- Classification: `{qualification['classification']}`",
        f"- Replayed native-ASR cases: `{origins.get('accuracy_replayed_case_count')}`",
        f"- Fresh native-ASR cases: `{origins.get('primary_computed_case_count')}`",
        f"- Native partial/final events: "
        f"`{qualification['native_asr_partial_event_count']}` / "
        f"`{qualification['native_asr_final_event_count']}`",
        f"- Queue policy: `{qualification['queue_policy']}`; dropped frames: "
        f"`{qualification['dropped_frame_count']}`",
        "",
        "## Fresh native decode and serial resource evidence",
        "",
    ]
    lines.extend(
        f"- `{row['configuration_id']}` / `{row['mode']}`: "
        f"`{row['classification']}`; result `{row['source_result_sha256']}`."
        for row in fresh_resource_rows
    )
    lines.extend(
        [
            "",
            "All three post-selection resource jobs ran serially with an isolated "
            "attempt-local cache and ASR stream-trace replay disabled. This is the "
            "fresh native decoder/resource evidence; it remains accelerated file "
            "input rather than physical-microphone or 1.0x wall-clock pacing.",
            "",
            "## Separate final evidence",
            "",
            "Reliability, controlled UI latency, long-session, common-application, "
            "ONNX parity, and ARM64 package evidence remain separate. None of the "
            "desktop jobs constitutes CM5 or Arduino UNO Q hardware validation.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def build_streaming_execution_provenance(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Disclose exact Phase-0 streaming compute/replay and pacing boundaries."""

    state_name = "controller/program_state.json"
    manifest_name = "protocol/job_manifest.json"
    runtime_identity_name = RUNTIME_IDENTITY_MEMBER
    required_sources = (state_name, manifest_name, runtime_identity_name)
    missing = [name for name in required_sources if name not in source_payloads]
    if missing:
        raise ValueError(
            "streaming provenance source is missing: " + ", ".join(missing)
        )
    state = json.loads(source_payloads[state_name])
    manifest = json.loads(source_payloads[manifest_name])
    if not isinstance(state, Mapping) or not isinstance(manifest, Mapping):
        raise ValueError("streaming provenance controller/manifest is invalid")
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("streaming provenance job manifest lacks jobs")
    candidates = [
        row
        for row in jobs
        if isinstance(row, Mapping)
        and row.get("job_kind") == "runtime_qualification"
        and row.get("configuration_id") == "H2_TRUE_STREAMING_QUALIFICATION"
    ]
    if len(candidates) != 1:
        raise ValueError("exactly one H2 streaming qualification job is required")
    job = candidates[0]
    case_ids = tuple(map(str, job.get("case_ids") or ()))
    job_id = str(job.get("job_id") or "")
    job_identity = str(job.get("identity_sha256") or "")
    if (
        not job_id
        or len(job_identity) != 64
        or not case_ids
        or job.get("split") != "development"
        or job.get("development_only") is not True
        or job.get("phase_index") != 0
    ):
        raise ValueError("streaming qualification job contract differs")
    state_jobs = state.get("jobs")
    raw_state_job = state_jobs.get(job_id) if isinstance(state_jobs, Mapping) else None
    expected_result_sha = (
        str(raw_state_job.get("result_sha256") or "")
        if isinstance(raw_state_job, Mapping)
        else ""
    )
    critical_names = (
        "diagnostics/cache_regime.json",
        "diagnostics/case_status.jsonl",
        "events.jsonl.gz",
        "pipeline_identity.json",
    )
    root, pipeline, critical = _validated_bound_result(
        state=state,
        job_id=job_id,
        expected_sha256=expected_result_sha,
        critical_names=critical_names,
    )
    execution = pipeline.get("execution_contract")
    if not isinstance(execution, Mapping) or (
        execution.get("h2_job_id") != job_id
        or execution.get("h2_job_identity_sha256") != job_identity
        or execution.get("h2_protocol_id") != state.get("protocol_id")
        or execution.get("h2_protocol_sha256") != state.get("protocol_sha256")
        or execution.get("product_mode") != job.get("mode")
    ):
        raise ValueError("streaming qualification execution binding differs")
    cache_regime = json.loads((root / critical_names[0]).read_bytes())
    if (
        cache_regime.get("measurement_mode") != "accuracy"
        or cache_regime.get("asr_stream_trace_enabled") is not True
        or cache_regime.get("resource_measurement_serial_required") is not False
    ):
        raise ValueError("streaming qualification cache regime differs")

    expected_cases = set(case_ids)
    case_rows = _read_jsonl(root / critical_names[1])
    observed_case_rows = {str(row.get("case_id") or ""): row for row in case_rows}
    if set(observed_case_rows) != expected_cases:
        raise ValueError("streaming qualification case-status coverage differs")
    queue_policies: set[str] = set()
    dropped_frames = 0
    for case_id, row in observed_case_rows.items():
        queue = row.get("queue_backpressure")
        if not isinstance(queue, Mapping):
            raise ValueError(f"streaming queue evidence is missing: {case_id}")
        queue_policies.add(str(queue.get("policy") or ""))
        raw_dropped = queue.get("dropped_frames")
        if isinstance(raw_dropped, bool) or not isinstance(raw_dropped, (int, float)):
            raise ValueError(f"streaming dropped-frame evidence is invalid: {case_id}")
        dropped_frames += int(raw_dropped)
    if queue_policies != {"block"}:
        raise ValueError("streaming qualification file queue policy differs")

    origin_cases: dict[str, set[str]] = defaultdict(set)
    origin_snapshot_counts: dict[str, int] = defaultdict(int)
    terminal_complete_cases: set[str] = set()
    worker_started_cases: set[str] = set()
    source_clock_types: set[str] = set()
    native_partial_count = 0
    native_final_count = 0
    native_stateful_final_count = 0
    with gzip.open(root / critical_names[2], "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                raise ValueError("streaming qualification event is invalid")
            case_id = str(row.get("evaluation_case_id") or "")
            if case_id and case_id not in expected_cases:
                raise ValueError("streaming qualification event escaped case set")
            adapter_event_type = row.get("adapter_event_type")
            if adapter_event_type in {"asr_partial", "asr_final"}:
                if adapter_event_type == "asr_partial":
                    native_partial_count += 1
                else:
                    native_final_count += 1
                accepted = row.get("accepted_audio_interval")
                if isinstance(accepted, Mapping) and accepted.get("source_clock_type"):
                    source_clock_types.add(str(accepted["source_clock_type"]))
            reason = row.get("event_reason")
            if (
                adapter_event_type == "asr_final"
                and isinstance(reason, Mapping)
                and reason.get("code") == "native_stateful_stream_update"
            ):
                native_stateful_final_count += 1
            statuses = row.get("component_statuses")
            if not isinstance(statuses, list):
                continue
            for status in statuses:
                if not isinstance(status, Mapping):
                    continue
                identity = status.get("component_identity")
                if (
                    not isinstance(identity, Mapping)
                    or identity.get("component_family") != "asr"
                ):
                    continue
                status_reason = status.get("reason")
                detail = (
                    status_reason.get("detail")
                    if isinstance(status_reason, Mapping)
                    else None
                )
                if not isinstance(detail, str):
                    continue
                try:
                    status_detail = json.loads(detail)
                except json.JSONDecodeError:
                    continue
                shared = (
                    status_detail.get("shared_execution")
                    if isinstance(status_detail, Mapping)
                    else None
                )
                if not isinstance(shared, Mapping):
                    continue
                origin = str(shared.get("execution_origin") or "")
                if origin not in {"primary_computed", "accuracy_replayed"}:
                    raise ValueError("streaming ASR execution origin differs")
                origin_snapshot_counts[origin] += 1
                if case_id:
                    origin_cases[origin].add(case_id)
                    if shared.get("worker_started") is True:
                        worker_started_cases.add(case_id)
                    terminal = shared.get("terminal_completeness")
                    if (
                        isinstance(terminal, Mapping)
                        and terminal.get("complete") is True
                        and shared.get("interaction_cursor")
                        == shared.get("interaction_count")
                    ):
                        terminal_complete_cases.add(case_id)
    covered_origin_cases = (
        set().union(*origin_cases.values()) if origin_cases else set()
    )
    if (
        covered_origin_cases != expected_cases
        or terminal_complete_cases != expected_cases
        or source_clock_types != {"external_media"}
        or native_final_count < 1
        or native_stateful_final_count != native_final_count
    ):
        raise ValueError("streaming native-interaction evidence is incomplete")
    replay_case_count = len(origin_cases.get("accuracy_replayed", set()))
    primary_case_count = len(origin_cases.get("primary_computed", set()))
    if replay_case_count == len(case_ids) and primary_case_count == 0:
        classification = "NATIVE_TRACE_REPLAY_QUALIFICATION"
    elif primary_case_count == len(case_ids) and replay_case_count == 0:
        classification = "FRESH_NATIVE_DECODE_QUALIFICATION"
    else:
        classification = "MIXED_NATIVE_COMPUTE_AND_TRACE_REPLAY_QUALIFICATION"

    qualification: dict[str, object] = {
        "job_id": job_id,
        "job_identity_sha256": job_identity,
        "source_result_sha256": expected_result_sha,
        "split": "development",
        "case_count": len(case_ids),
        "audio_duration_sec": job.get("audio_duration_sec"),
        "classification": classification,
        "input_mode": "ACCELERATED_FILE_SIMULATION",
        "input_source_clock_types": sorted(source_clock_types),
        "physical_microphone_used": False,
        "real_time_1x_pacing_used": False,
        "common_causal_coordinator_exercised": True,
        "native_stateful_interaction_order_exercised": True,
        "asr_stream_trace_enabled": True,
        "asr_execution_origins": {
            "accuracy_replayed_case_count": replay_case_count,
            "primary_computed_case_count": primary_case_count,
            "worker_started_case_count": len(worker_started_cases),
            "snapshot_counts": dict(sorted(origin_snapshot_counts.items())),
        },
        "all_native_traces_terminal_complete": True,
        "native_processing_latency_preserved_by_trace_contract": True,
        "native_asr_partial_event_count": native_partial_count,
        "native_asr_final_event_count": native_final_count,
        "native_stateful_final_event_count": native_stateful_final_count,
        "queue_policy": "block",
        "dropped_frame_count": dropped_frames,
        "accuracy_interaction_qualification_eligible": True,
        "resource_comparison_eligible": False,
        "physical_microphone_claim_eligible": False,
        "target_hardware_claim_eligible": False,
        "critical_files": critical,
    }
    expected_resource_configurations = dict(STREAMING_FRESH_RESOURCE_CONFIGURATIONS)
    resource_candidates = [
        row
        for row in jobs
        if isinstance(row, Mapping)
        and row.get("job_kind") == "post_selection_resource_runtime"
        and row.get("configuration_id") in expected_resource_configurations
    ]
    resource_by_configuration = {
        str(row.get("configuration_id") or ""): row for row in resource_candidates
    }
    if len(resource_candidates) != len(expected_resource_configurations) or set(
        resource_by_configuration
    ) != set(expected_resource_configurations):
        raise ValueError("fresh streaming resource job coverage differs")
    fresh_resource_evidence: list[dict[str, object]] = []
    for configuration_id, expected_mode in expected_resource_configurations.items():
        resource_job = resource_by_configuration[configuration_id]
        resource_job_id = str(resource_job.get("job_id") or "")
        resource_identity = str(resource_job.get("identity_sha256") or "")
        if (
            not resource_job_id
            or len(resource_identity) != 64
            or resource_job.get("mode") != expected_mode
            or resource_job.get("split") != "development"
            or resource_job.get("development_only") is not True
            or resource_job.get("serial") is not True
            or resource_job.get("phase_index") != 6
        ):
            raise ValueError(
                f"fresh streaming resource job contract differs: {configuration_id}"
            )
        resource_state = (
            state_jobs.get(resource_job_id) if isinstance(state_jobs, Mapping) else None
        )
        resource_result_sha = (
            str(resource_state.get("result_sha256") or "")
            if isinstance(resource_state, Mapping)
            else ""
        )
        resource_critical_names = (
            "diagnostics/cache_regime.json",
            "pipeline_identity.json",
        )
        resource_root, resource_pipeline, resource_critical = _validated_bound_result(
            state=state,
            job_id=resource_job_id,
            expected_sha256=resource_result_sha,
            critical_names=resource_critical_names,
        )
        resource_execution = resource_pipeline.get("execution_contract")
        if not isinstance(resource_execution, Mapping) or (
            resource_execution.get("h2_job_id") != resource_job_id
            or resource_execution.get("h2_job_identity_sha256") != resource_identity
            or resource_execution.get("h2_protocol_id") != state.get("protocol_id")
            or resource_execution.get("h2_protocol_sha256")
            != state.get("protocol_sha256")
            or resource_execution.get("product_mode") != expected_mode
        ):
            raise ValueError(
                f"fresh streaming resource execution binding differs: {configuration_id}"
            )
        resource_cache = json.loads(
            (resource_root / resource_critical_names[0]).read_bytes()
        )
        if (
            resource_cache.get("measurement_mode") != "resources"
            or resource_cache.get("runtime_cache_scope")
            != "isolated_attempt_local_resource_cold_start"
            or resource_cache.get("asr_stream_trace_enabled") is not False
            or resource_cache.get("resource_measurement_serial_required") is not True
        ):
            raise ValueError(
                f"fresh streaming resource cache regime differs: {configuration_id}"
            )
        fresh_resource_evidence.append(
            {
                "configuration_id": configuration_id,
                "mode": expected_mode,
                "job_id": resource_job_id,
                "job_identity_sha256": resource_identity,
                "source_result_sha256": resource_result_sha,
                "classification": "FRESH_NATIVE_DECODE_SERIAL_RESOURCE",
                "measurement_mode": "resources",
                "serial_execution": True,
                "runtime_cache_scope": "isolated_attempt_local_resource_cold_start",
                "asr_stream_trace_enabled": False,
                "physical_microphone_used": False,
                "real_time_1x_pacing_used": False,
                "resource_comparison_eligible": True,
                "critical_files": resource_critical,
            }
        )
    document: dict[str, object] = {
        "schema_version": "h2-streaming-execution-provenance.v1",
        "status": "VALIDATED_SCOPE_DISCLOSURE",
        "scientific_results_or_policy_changed": False,
        "scientific_selection_changed": False,
        "built_in_true_streaming_label_requires_this_disclosure": True,
        "source_bindings": {
            name: _sha256(source_payloads[name]) for name in required_sources
        },
        "qualification": qualification,
        "fresh_decode_serial_resource_evidence": fresh_resource_evidence,
        "separate_final_evidence": [
            {
                "member": "summary/h2_resource_results.csv",
                "scope": "serial resource jobs; ASR trace replay forbidden",
            },
            {
                "member": "summary/h2_ui_latency_results.csv",
                "scope": "controlled event-to-render and product UX timing",
            },
            {
                "member": "summary/h2_long_session_results.csv",
                "scope": "long-session stability and drift",
            },
            {
                "member": "summary/h2_linux_portability.json",
                "scope": "software portability preparation, not ARM64 hardware proof",
            },
        ],
    }
    payloads = {
        REQUIRED_STREAMING_PROVENANCE_MEMBERS[0]: (
            _render_streaming_execution_provenance(document)
        ),
        REQUIRED_STREAMING_PROVENANCE_MEMBERS[1]: _canonical_json(document),
    }
    return payloads, document


def _validate_streaming_execution_provenance_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [
        name for name in REQUIRED_STREAMING_PROVENANCE_MEMBERS if name not in payloads
    ]
    if missing:
        raise ValueError(
            "augmented package lacks streaming provenance disclosure: "
            + ", ".join(missing)
        )
    document = json.loads(payloads[REQUIRED_STREAMING_PROVENANCE_MEMBERS[1]])
    qualification = document.get("qualification")
    if (
        document.get("schema_version") != "h2-streaming-execution-provenance.v1"
        or document.get("status") != "VALIDATED_SCOPE_DISCLOSURE"
        or document.get("scientific_results_or_policy_changed") is not False
        or document.get("scientific_selection_changed") is not False
        or document.get("built_in_true_streaming_label_requires_this_disclosure")
        is not True
        or not isinstance(qualification, Mapping)
    ):
        raise ValueError("streaming provenance disclosure contract differs")
    origins = qualification.get("asr_execution_origins")
    case_count = qualification.get("case_count")
    if (
        not isinstance(case_count, int)
        or case_count < 1
        or not isinstance(origins, Mapping)
        or sum(
            int(origins.get(name) or 0)
            for name in (
                "accuracy_replayed_case_count",
                "primary_computed_case_count",
            )
        )
        < case_count
        or qualification.get("input_mode") != "ACCELERATED_FILE_SIMULATION"
        or qualification.get("input_source_clock_types") != ["external_media"]
        or qualification.get("physical_microphone_used") is not False
        or qualification.get("real_time_1x_pacing_used") is not False
        or qualification.get("common_causal_coordinator_exercised") is not True
        or qualification.get("native_stateful_interaction_order_exercised") is not True
        or qualification.get("asr_stream_trace_enabled") is not True
        or qualification.get("all_native_traces_terminal_complete") is not True
        or qualification.get("native_asr_final_event_count")
        != qualification.get("native_stateful_final_event_count")
        or qualification.get("queue_policy") != "block"
        or qualification.get("resource_comparison_eligible") is not False
        or qualification.get("physical_microphone_claim_eligible") is not False
        or qualification.get("target_hardware_claim_eligible") is not False
        or len(str(qualification.get("source_result_sha256") or "")) != 64
    ):
        raise ValueError("streaming qualification scope disclosure differs")
    critical = qualification.get("critical_files")
    if not isinstance(critical, Mapping) or set(critical) != {
        "diagnostics/cache_regime.json",
        "diagnostics/case_status.jsonl",
        "events.jsonl.gz",
        "pipeline_identity.json",
    }:
        raise ValueError("streaming qualification critical-file binding differs")
    for name, row in critical.items():
        if (
            not isinstance(row, Mapping)
            or len(str(row.get("sha256") or "")) != 64
            or not isinstance(row.get("bytes"), int)
            or int(row["bytes"]) < 1
        ):
            raise ValueError(f"streaming critical-file identity differs: {name}")
    fresh_resource_rows = document.get("fresh_decode_serial_resource_evidence")
    if not isinstance(fresh_resource_rows, list) or len(fresh_resource_rows) != len(
        STREAMING_FRESH_RESOURCE_CONFIGURATIONS
    ):
        raise ValueError("fresh streaming resource evidence coverage differs")
    resources_by_configuration = {
        str(row.get("configuration_id") or ""): row
        for row in fresh_resource_rows
        if isinstance(row, Mapping)
    }
    if set(resources_by_configuration) != set(STREAMING_FRESH_RESOURCE_CONFIGURATIONS):
        raise ValueError("fresh streaming resource configuration coverage differs")
    for (
        configuration_id,
        expected_mode,
    ) in STREAMING_FRESH_RESOURCE_CONFIGURATIONS.items():
        row = resources_by_configuration[configuration_id]
        resource_critical = row.get("critical_files")
        if (
            row.get("mode") != expected_mode
            or row.get("classification") != "FRESH_NATIVE_DECODE_SERIAL_RESOURCE"
            or row.get("measurement_mode") != "resources"
            or row.get("serial_execution") is not True
            or row.get("runtime_cache_scope")
            != "isolated_attempt_local_resource_cold_start"
            or row.get("asr_stream_trace_enabled") is not False
            or row.get("physical_microphone_used") is not False
            or row.get("real_time_1x_pacing_used") is not False
            or row.get("resource_comparison_eligible") is not True
            or len(str(row.get("job_identity_sha256") or "")) != 64
            or len(str(row.get("source_result_sha256") or "")) != 64
            or not isinstance(resource_critical, Mapping)
            or set(resource_critical)
            != {"diagnostics/cache_regime.json", "pipeline_identity.json"}
        ):
            raise ValueError(
                f"fresh streaming resource scope differs: {configuration_id}"
            )
        for name, identity in resource_critical.items():
            if (
                not isinstance(identity, Mapping)
                or len(str(identity.get("sha256") or "")) != 64
                or not isinstance(identity.get("bytes"), int)
                or int(identity["bytes"]) < 1
            ):
                raise ValueError(
                    f"fresh streaming resource file identity differs: "
                    f"{configuration_id}:{name}"
                )
    expected_markdown = _render_streaming_execution_provenance(document)
    if payloads[REQUIRED_STREAMING_PROVENANCE_MEMBERS[0]] != expected_markdown:
        raise ValueError("streaming provenance rendering differs")
    return dict(document)


def build_long_session_drift_supplement(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Compare matched 30- and 60-minute streams without rerunning inference."""

    source_name = "summary/h2_long_session_results.csv"
    if source_name not in source_payloads:
        raise ValueError("long-session drift source table is missing")
    source_rows = _csv_rows(source_payloads[source_name])
    target_source_metrics = {row[1] for row in LONG_SESSION_DRIFT_METRICS}
    stream_metrics: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    stream_sources: dict[tuple[str, str], str] = {}
    for row in source_rows:
        split = str(row.get("split") or "")
        stream_id = str(row.get("configuration_id") or "")
        if split not in {"development", "evaluation"} or not stream_id:
            continue
        raw_record = row.get("source_record_json")
        try:
            record = json.loads(str(raw_record or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"long-session source record is invalid: {split}/{stream_id}"
            ) from exc
        source = record.get("source") if isinstance(record, Mapping) else None
        source_id = (
            str(source.get("source_recording_id") or "")
            if isinstance(source, Mapping)
            else ""
        )
        if not source_id:
            raise ValueError(
                f"long-session source identity is missing: {split}/{stream_id}"
            )
        key = (split, stream_id)
        previous_source = stream_sources.setdefault(key, source_id)
        if previous_source != source_id:
            raise ValueError("long-session stream maps to multiple source recordings")
        metric_id = str(row.get("metric_id") or "")
        if metric_id not in target_source_metrics:
            continue
        if str(row.get("metric_status") or "").casefold() != "computed":
            continue
        value = _number(row.get("value"))
        if value is not None and metric_id:
            previous = stream_metrics[key].setdefault(metric_id, value)
            if previous != value:
                raise ValueError(
                    f"long-session metric is duplicated inconsistently: {key}/{metric_id}"
                )

    streams_by_source: dict[tuple[str, str], dict[int, str]] = defaultdict(dict)
    for (split, stream_id), source_id in stream_sources.items():
        duration = (
            30
            if stream_id.endswith("_30m")
            else 60
            if stream_id.endswith("_60m")
            else 0
        )
        if duration not in {30, 60}:
            raise ValueError(
                f"long-session stream duration suffix differs: {stream_id}"
            )
        pair = streams_by_source[(split, source_id)]
        if duration in pair and pair[duration] != stream_id:
            raise ValueError("long-session source has duplicate duration streams")
        pair[duration] = stream_id
    expected_sources = {"development": 4, "evaluation": 8}
    observed_sources = {
        split: sum(
            1
            for candidate_split, _source in streams_by_source
            if candidate_split == split
        )
        for split in expected_sources
    }
    if observed_sources != expected_sources or any(
        set(pair) != {30, 60} for pair in streams_by_source.values()
    ):
        raise ValueError(
            "long-session drift requires matched 30/60-minute streams for "
            "four development and eight evaluation sources"
        )

    def normalized(value: float, normalization: str, duration_min: int) -> float:
        if normalization == "per_minute":
            return value / duration_min
        if normalization == "per_hour":
            return value / (duration_min / 60.0)
        return value

    output_rows: list[dict[str, object]] = []
    for (split, source_id), pair in sorted(streams_by_source.items()):
        short_id, long_id = pair[30], pair[60]
        short_metrics = stream_metrics.get((split, short_id), {})
        long_metrics = stream_metrics.get((split, long_id), {})
        for (
            metric_id,
            source_metric_id,
            normalization,
            unit,
        ) in LONG_SESSION_DRIFT_METRICS:
            raw_short = short_metrics.get(source_metric_id)
            raw_long = long_metrics.get(source_metric_id)
            if raw_short is None or raw_long is None:
                short_value = long_value = absolute = relative = None
                status = "UNSUPPORTED_SOURCE_METRIC"
                reason = f"{source_metric_id} was not computed for both matched streams"
            else:
                short_value = normalized(raw_short, normalization, 30)
                long_value = normalized(raw_long, normalization, 60)
                absolute = long_value - short_value
                relative = absolute / abs(short_value) if short_value != 0 else None
                status = "COMPUTED"
                reason = None
            output_rows.append(
                {
                    "schema_version": "h2-long-session-drift-row.v1",
                    "split": split,
                    "source_recording_id": source_id,
                    "short_stream_id": short_id,
                    "long_stream_id": long_id,
                    "metric_id": metric_id,
                    "source_metric_id": source_metric_id,
                    "normalization": normalization,
                    "metric_status": status,
                    "value_30m": short_value,
                    "value_60m": long_value,
                    "absolute_drift_60m_minus_30m": absolute,
                    "relative_drift_fraction": relative,
                    "unit": unit,
                    "reason": reason,
                }
            )
    expected_count = sum(expected_sources.values()) * len(LONG_SESSION_DRIFT_METRICS)
    if len(output_rows) != expected_count:
        raise ValueError("long-session drift row coverage differs")
    provenance: dict[str, object] = {
        "schema_version": "h2-long-session-drift-provenance.v1",
        "status": "VALID",
        "source_member": source_name,
        "source_sha256": _sha256(source_payloads[source_name]),
        "source_counts": expected_sources,
        "matched_duration_minutes": [30, 60],
        "metric_ids": [row[0] for row in LONG_SESSION_DRIFT_METRICS],
        "row_count": len(output_rows),
        "development_and_heldout_evidence_pooled": False,
        "post_hoc_metrics_used_for_frozen_selection": False,
        "scientific_runtime_or_policy_changed": False,
        "thermal_drift_status": "UNSUPPORTED_NO_TEMPERATURE_TELEMETRY",
    }
    markdown = [
        "# H2 matched 30-to-60-minute drift",
        "",
        "This table compares each predeclared 30-minute stream with the matched "
        "60-minute stream from the same source recording. Count metrics are "
        "normalized per minute or hour before comparison; peaks and RTF remain "
        "direct measurements. Positive drift means the 60-minute value is higher.",
        "",
        "Development and held-out rows remain separate and these post-run "
        "derivatives did not affect selection. Temperature/thermal drift is "
        "unsupported because the desktop runtime emits no temperature telemetry.",
        "",
    ]
    return (
        {
            REQUIRED_LONG_SESSION_DRIFT_MEMBERS[0]: _csv_payload(
                output_rows, LONG_SESSION_DRIFT_FIELDS
            ),
            REQUIRED_LONG_SESSION_DRIFT_MEMBERS[1]: "\n".join(markdown).encode("utf-8"),
            REQUIRED_LONG_SESSION_DRIFT_MEMBERS[2]: _canonical_json(provenance),
        },
        provenance,
    )


def _short_label(value: str, maximum: int = 28) -> str:
    return value if len(value) <= maximum else value[: maximum - 1] + "…"


def _svg_document(title: str, body: str, *, description: str) -> bytes:
    safe_title = html.escape(title)
    safe_description = html.escape(description)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" '
        'viewBox="0 0 960 540" role="img">\n'
        f"<title>{safe_title}</title><desc>{safe_description}</desc>\n"
        '<rect width="960" height="540" fill="#fbfaf7"/>\n'
        f'<text x="480" y="38" text-anchor="middle" font-family="Segoe UI, sans-serif" '
        f'font-size="23" font-weight="600" fill="#252525">{safe_title}</text>\n'
        f"{body}\n</svg>\n"
    ).encode("utf-8")


def _bar_svg(
    title: str,
    values: Mapping[str, float],
    *,
    axis_label: str,
    scale: float = 1.0,
) -> bytes:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if not ordered:
        raise ValueError(f"no computed values for plot: {title}")
    maximum = max(value * scale for _, value in ordered)
    maximum = maximum if maximum > 0 else 1.0
    left, top, width, height = 250.0, 70.0, 650.0, 400.0
    slot = height / len(ordered)
    parts = [
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + height}" stroke="#333"/>',
        f'<text x="{left + width / 2}" y="515" text-anchor="middle" font-family="Segoe UI, sans-serif" font-size="15" fill="#333">{html.escape(axis_label)}</text>',
    ]
    for index, (label, raw) in enumerate(ordered):
        value = raw * scale
        y = top + index * slot + slot * 0.18
        bar_height = max(10.0, slot * 0.58)
        bar_width = width * value / maximum
        color = "#2f766d" if index % 2 == 0 else "#4d8f85"
        parts.extend(
            (
                f'<text x="{left - 12}" y="{y + bar_height * 0.72}" text-anchor="end" font-family="Segoe UI, sans-serif" font-size="12" fill="#333">{html.escape(_short_label(label))}</text>',
                f'<rect x="{left}" y="{y}" width="{bar_width:.3f}" height="{bar_height:.3f}" fill="{color}" rx="3"/>',
                f'<text x="{min(left + bar_width + 7, 920):.3f}" y="{y + bar_height * 0.72:.3f}" font-family="Segoe UI, sans-serif" font-size="12" fill="#222">{value:.4g}</text>',
            )
        )
    return _svg_document(
        title,
        "\n".join(parts),
        description=f"Horizontal bar chart of {axis_label} by frozen configuration.",
    )


def _scatter_svg(
    title: str,
    x_values: Mapping[str, float],
    y_values: Mapping[str, float],
    *,
    x_label: str,
    y_label: str,
) -> bytes:
    labels = sorted(set(x_values) & set(y_values))
    if not labels:
        raise ValueError(f"no paired computed values for plot: {title}")
    xs = [x_values[label] for label in labels]
    ys = [y_values[label] for label in labels]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if x_min == x_max:
        x_min, x_max = x_min - 0.5, x_max + 0.5
    if y_min == y_max:
        y_min, y_max = y_min - 0.5, y_max + 0.5
    left, top, width, height = 100.0, 70.0, 780.0, 380.0

    def sx(value: float) -> float:
        return left + width * (value - x_min) / (x_max - x_min)

    def sy(value: float) -> float:
        return top + height - height * (value - y_min) / (y_max - y_min)

    parts = [
        f'<line x1="{left}" y1="{top + height}" x2="{left + width}" y2="{top + height}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + height}" stroke="#333"/>',
        f'<text x="{left + width / 2}" y="510" text-anchor="middle" font-family="Segoe UI, sans-serif" font-size="15" fill="#333">{html.escape(x_label)}</text>',
        f'<text x="24" y="{top + height / 2}" text-anchor="middle" transform="rotate(-90 24 {top + height / 2})" font-family="Segoe UI, sans-serif" font-size="15" fill="#333">{html.escape(y_label)}</text>',
        f'<text x="{left}" y="{top + height + 22}" text-anchor="middle" font-family="Segoe UI, sans-serif" font-size="11">{x_min:.4g}</text>',
        f'<text x="{left + width}" y="{top + height + 22}" text-anchor="middle" font-family="Segoe UI, sans-serif" font-size="11">{x_max:.4g}</text>',
        f'<text x="{left - 10}" y="{top + height}" text-anchor="end" font-family="Segoe UI, sans-serif" font-size="11">{y_min:.4g}</text>',
        f'<text x="{left - 10}" y="{top + 5}" text-anchor="end" font-family="Segoe UI, sans-serif" font-size="11">{y_max:.4g}</text>',
    ]
    for index, label in enumerate(labels):
        x, y = sx(x_values[label]), sy(y_values[label])
        anchor = "start" if index % 2 == 0 else "end"
        dx = 8 if anchor == "start" else -8
        parts.extend(
            (
                f'<circle cx="{x:.3f}" cy="{y:.3f}" r="6" fill="#bd5a45" stroke="#7a3023" stroke-width="1"/>',
                f'<text x="{x + dx:.3f}" y="{y - 8:.3f}" text-anchor="{anchor}" font-family="Segoe UI, sans-serif" font-size="11" fill="#222">{html.escape(_short_label(label, 24))}</text>',
            )
        )
    return _svg_document(
        title,
        "\n".join(parts),
        description=f"Scatter plot comparing {x_label} and {y_label}.",
    )


def build_plots(
    payloads: Mapping[str, bytes],
) -> tuple[dict[str, bytes], list[dict[str, object]]]:
    missing = [name for name in PLOT_SOURCES if name not in payloads]
    if missing:
        raise ValueError(
            "native package lacks plot source tables: " + ", ".join(missing)
        )
    modes = _csv_rows(payloads[PLOT_SOURCES[0]])
    resources = _csv_rows(payloads[PLOT_SOURCES[1]])
    segmentation = _csv_rows(payloads[PLOT_SOURCES[2]])
    plots: dict[str, bytes] = {}
    provenance: list[dict[str, object]] = []

    def add(
        name: str, content: bytes, sources: Iterable[str], metrics: Iterable[str]
    ) -> None:
        plots[f"plots/{name}"] = content
        provenance.append(
            {
                "member": f"plots/{name}",
                "source_members": list(sources),
                "metric_ids": list(metrics),
                "sha256": _sha256(content),
                "bytes": len(content),
            }
        )

    mode_wrong = _computed_metric_map(modes, metric_id="wrong_known_time_sec")
    mode_stranger = _computed_metric_map(
        modes, metric_id="stranger_false_known_time_sec"
    )
    add(
        "mode_identity_safety.svg",
        _scatter_svg(
            "Frozen H2 Mode Identity Safety",
            mode_stranger,
            mode_wrong,
            x_label="Stranger false-known time (s)",
            y_label="Wrong-known time (s)",
        ),
        (PLOT_SOURCES[0],),
        ("stranger_false_known_time_sec", "wrong_known_time_sec"),
    )

    stable = _computed_metric_map(modes, metric_id="stable_name_latency_sec")
    add(
        "mode_stable_name_latency.svg",
        _bar_svg(
            "Frozen H2 Stable-Name Latency",
            stable,
            axis_label="Stable-name latency (s; lower is better)",
        ),
        (PLOT_SOURCES[0],),
        ("stable_name_latency_sec",),
    )

    peak = _computed_metric_map(resources, metric_id="peak_rss_bytes")
    add(
        "serial_peak_ram.svg",
        _bar_svg(
            "Matched Serial Peak RAM",
            peak,
            axis_label="Peak resident memory (MiB; lower is better)",
            scale=1.0 / (1024.0 * 1024.0),
        ),
        (PLOT_SOURCES[1],),
        ("peak_rss_bytes",),
    )

    rtf = _computed_metric_map(resources, metric_id="total_rtf")
    add(
        "serial_total_rtf.svg",
        _bar_svg(
            "Matched Serial Total RTF",
            rtf,
            axis_label="Real-time factor (lower is better)",
        ),
        (PLOT_SOURCES[1],),
        ("total_rtf",),
    )

    seg_miss = _computed_metric_map(segmentation, metric_id="miss_rate")
    seg_delay = _computed_metric_map(segmentation, metric_id="boundary_delay_sec")
    add(
        "segmentation_coverage_latency.svg",
        _scatter_svg(
            "Segmentation Coverage–Latency Frontier",
            seg_miss,
            seg_delay,
            x_label="Miss rate (lower is better)",
            y_label="Boundary delay (s; lower is better)",
        ),
        (PLOT_SOURCES[2],),
        ("miss_rate", "boundary_delay_sec"),
    )
    if len(plots) < 3:
        raise ValueError("fewer than three evidence-backed plots were generated")
    guide_lines = [
        "# H2 final-package plots",
        "",
        "These SVGs are deterministic presentation derivatives of immutable CSV files",
        "inside the native controller-validated package. They do not alter scientific",
        "measurements, policies, selections, or conclusions.",
        "",
    ]
    for row in provenance:
        guide_lines.extend(
            (
                f"## `{row['member']}`",
                "",
                "- Source: "
                + ", ".join(f"`{value}`" for value in row["source_members"]),
                "- Metrics: " + ", ".join(f"`{value}`" for value in row["metric_ids"]),
                f"- SHA-256: `{row['sha256']}`",
                "",
            )
        )
    guide = ("\n".join(guide_lines).rstrip() + "\n").encode("utf-8")
    plots["plots/PLOT_GUIDE.md"] = guide
    return plots, provenance


METRIC_FIELDS = (
    "schema_version",
    "configuration_id",
    "mode",
    "evidence_split",
    "source_job_id",
    "source_result_sha256",
    "metric_family",
    "metric_id",
    "variant",
    "target_sec",
    "metric_status",
    "value",
    "numerator",
    "denominator",
    "unit",
    "ci_lower_95",
    "ci_upper_95",
    "bootstrap_repetitions",
    "bootstrap_seed",
    "resampling_unit",
    "definition",
    "censoring_policy",
    "reason",
)

OVERLAP_FIELDS = (
    "schema_version",
    "configuration_id",
    "overlap_policy",
    "evidence_split",
    "composition",
    "condition",
    "metric_id",
    "metric_status",
    "value",
    "numerator",
    "denominator",
    "unit",
    "ci_lower_95",
    "ci_upper_95",
    "bootstrap_repetitions",
    "bootstrap_seed",
    "resampling_unit",
    "case_count",
    "computed_case_count",
    "unsupported_or_undefined_case_count",
    "audio_duration_sec",
    "mean_reference_overlap_ratio",
    "source_job_id",
    "source_result_sha256",
    "aggregation",
    "definition",
    "reason",
)


def _csv_payload(
    rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name) for name in fieldnames})
    return output.getvalue().encode("utf-8")


def _percentile(values: Sequence[float], probability: float) -> float | None:
    ordered = sorted(value for value in values if math.isfinite(value))
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _speaker_bootstrap(
    observations: Sequence[Mapping[str, object]],
    *,
    estimator: str,
    identity: str,
) -> tuple[float | None, float | None, int, int]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in observations:
        speaker = str(row.get("global_speaker_id") or "").strip()
        if speaker:
            grouped[speaker].append(row)
    speakers = sorted(grouped)
    seed = BOOTSTRAP_SEED + int(
        hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8], 16
    )
    if not speakers:
        return None, None, 0, seed

    def estimate(rows: Sequence[Mapping[str, object]]) -> float | None:
        if estimator == "ratio":
            numerator = sum(float(row["numerator"]) for row in rows)
            denominator = sum(float(row["denominator"]) for row in rows)
            return numerator / denominator if denominator > 0 else None
        values = [
            float(row["value"])
            for row in rows
            if row.get("value") is not None and math.isfinite(float(row["value"]))
        ]
        if not values:
            return None
        if estimator == "mean":
            return statistics.fmean(values)
        if estimator == "median":
            return statistics.median(values)
        raise ValueError(f"unknown bootstrap estimator: {estimator}")

    randomizer = random.Random(seed)
    estimates: list[float] = []
    for _ in range(BOOTSTRAP_REPETITIONS):
        sampled: list[Mapping[str, object]] = []
        for _speaker_index in speakers:
            sampled.extend(grouped[randomizer.choice(speakers)])
        value = estimate(sampled)
        if value is not None:
            estimates.append(value)
    if len(estimates) != BOOTSTRAP_REPETITIONS:
        return None, None, len(speakers), seed
    return (
        _percentile(estimates, 0.025),
        _percentile(estimates, 0.975),
        len(speakers),
        seed,
    )


def _safe_reference_path(case: Mapping[str, object], workspace: Path) -> Path:
    logical_name = str(case.get("reference_rttm_logical_path") or "")
    logical = PurePosixPath(logical_name)
    if (
        not logical_name
        or logical.is_absolute()
        or any(part in {"", ".", ".."} for part in logical.parts)
    ):
        raise ValueError(f"unsafe reference RTTM path: {logical_name!r}")
    namespace = str(
        case.get("reference_rttm_namespace")
        or case.get("audio_namespace")
        or "tool_root"
    )
    roots = {"tool_root": TOOL_ROOT.resolve(), "workspace": workspace.resolve()}
    if namespace not in roots:
        raise ValueError(f"unsupported reference RTTM namespace: {namespace}")
    root = roots[namespace]
    path = (root / Path(*logical.parts)).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"reference RTTM escaped {namespace}: {logical_name}") from exc
    if not path.is_file():
        raise ValueError(f"reference RTTM is not a file: {path}")
    expected = str(case.get("reference_rttm_sha256") or "").casefold()
    observed = _sha256(path.read_bytes())
    if len(expected) != 64 or observed.casefold() != expected:
        raise ValueError(f"reference RTTM checksum differs: {logical_name}")
    return path


def _interval_overlap(left: RttmTurn, right: RttmTurn) -> float:
    return max(
        0.0,
        min(left.end_sec, right.end_sec) - max(left.start_sec, right.start_sec),
    )


def _focused_case_events(
    case: Mapping[str, object],
    references: Sequence[RttmTurn],
    hypotheses: Sequence[RttmTurn],
) -> dict[str, list[dict[str, object]]]:
    """Compute only the four required families using the frozen v2 definitions."""

    refs = sorted(
        references, key=lambda row: (row.start_sec, row.end_sec, row.speaker_label)
    )
    hyps = sorted(
        hypotheses, key=lambda row: (row.start_sec, row.end_sec, row.speaker_label)
    )
    hyp_starts = [row.start_sec for row in hyps]
    hyp_ends = [row.end_sec for row in hyps]
    monotonic_ends = all(left <= right for left, right in zip(hyp_ends, hyp_ends[1:]))

    def overlapping(reference: RttmTurn) -> Iterable[RttmTurn]:
        upper = bisect_left(hyp_starts, reference.end_sec)
        lower = bisect_right(hyp_ends, reference.start_sec) if monotonic_ends else 0
        for hypothesis in hyps[lower:upper]:
            if hypothesis.end_sec > reference.start_sec:
                yield hypothesis

    ref_labels = sorted({row.speaker_label for row in refs})
    hyp_labels = sorted({row.speaker_label for row in hyps})
    overlap: dict[tuple[str, str], float] = defaultdict(float)
    for reference in refs:
        for hypothesis in overlapping(reference):
            overlap[(reference.speaker_label, hypothesis.speaker_label)] += (
                _interval_overlap(reference, hypothesis)
            )
    cluster_map = {
        hypothesis: max(
            ref_labels,
            key=lambda reference: (overlap[(reference, hypothesis)], reference),
        )
        for hypothesis in hyp_labels
        if ref_labels
    }
    global_speakers = dict(case.get("local_to_global_speaker") or {})
    if set(ref_labels) - set(global_speakers):
        raise ValueError(
            "case reference labels are absent from local/global speaker map"
        )

    hypothesis_duration: dict[str, float] = defaultdict(float)
    for hypothesis in hyps:
        hypothesis_duration[hypothesis.speaker_label] += hypothesis.duration_sec
    cluster_purity: dict[str, float] = {}
    contamination: list[dict[str, object]] = []
    for hypothesis in hyp_labels:
        duration = hypothesis_duration[hypothesis]
        dominant = cluster_map[hypothesis]
        purity = (
            min(1.0, overlap[(dominant, hypothesis)] / duration) if duration else 0.0
        )
        cluster_purity[hypothesis] = purity
        contamination.append(
            {
                "predicted_cluster": hypothesis,
                "dominant_global_speaker_id": global_speakers[dominant],
                "predicted_duration_sec": duration,
                "dominant_reference_fraction": purity,
            }
        )

    short_turns: list[dict[str, object]] = []
    for reference in refs:
        duration = reference.duration_sec
        if duration >= 2.0:
            continue
        correct = min(
            duration,
            sum(
                _interval_overlap(reference, hypothesis)
                for hypothesis in overlapping(reference)
                if cluster_map.get(hypothesis.speaker_label) == reference.speaker_label
            ),
        )
        short_turns.append(
            {
                "global_speaker_id": global_speakers[reference.speaker_label],
                "duration_sec": duration,
                "anonymous_speaker_correctness": correct / duration,
            }
        )

    evidence: list[dict[str, object]] = []
    latency: list[dict[str, object]] = []
    for reference_speaker in ref_labels:
        first = min(
            row.start_sec for row in refs if row.speaker_label == reference_speaker
        )
        clean = sorted(
            (
                row
                for row in hyps
                if cluster_map.get(row.speaker_label) == reference_speaker
                and cluster_purity.get(row.speaker_label, 0.0) >= 0.95
            ),
            key=lambda row: row.end_sec,
        )
        total = sum(row.duration_sec for row in clean)
        for target in EVIDENCE_TARGETS:
            achieved = total >= target
            accumulated = 0.0
            reached = None
            for row in clean:
                accumulated += row.duration_sec
                if accumulated >= target:
                    reached = row.end_sec
                    break
            common = {
                "global_speaker_id": global_speakers[reference_speaker],
                "target_sec": target,
                "clean_evidence_sec": total,
                "achieved": achieved,
            }
            evidence.append(common)
            latency.append(
                {
                    **common,
                    "latency_sec": (
                        max(0.0, reached - first) if reached is not None else None
                    ),
                    "censor_time_sec": float(case["duration_sec"]) - first,
                }
            )
    return {
        "contamination": contamination,
        "short_turns": short_turns,
        "evidence": evidence,
        "latency": latency,
    }


def _validated_result_inputs(
    *,
    workspace: Path,
    state: Mapping[str, object],
    configuration: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    configuration_id = str(configuration.get("configuration_id") or "")
    source_field = (
        "source_job_id"
        if configuration_id == "H2_BASELINE_REFERENCE"
        else "heldout_source_job_id"
    )
    sha_field = (
        "source_result_sha256"
        if configuration_id == "H2_BASELINE_REFERENCE"
        else "heldout_source_result_sha256"
    )
    job_id = str(configuration.get(source_field) or "")
    expected_sha = str(configuration.get(sha_field) or "")
    jobs = state.get("jobs")
    if not job_id or not isinstance(jobs, Mapping):
        raise ValueError(
            f"configuration lacks a source job binding: {configuration_id}"
        )
    raw_job = jobs.get(job_id)
    if not isinstance(raw_job, Mapping) or raw_job.get("state") != "COMPLETE":
        raise ValueError(f"source job is not complete: {job_id}")
    if raw_job.get("result_sha256") != expected_sha or len(expected_sha) != 64:
        raise ValueError(f"source result identity differs: {job_id}")
    raw_path = raw_job.get("result_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"source result path is absent: {job_id}")
    root = Path(raw_path).resolve(strict=True)
    results_root = Path(str(state.get("results_root") or "")).resolve(strict=True)
    try:
        root.relative_to(results_root)
    except ValueError as exc:
        raise ValueError(
            f"source result escaped controller results root: {job_id}"
        ) from exc
    report = validate_result_tree(root)
    if not report.reusable:
        reasons = "; ".join(
            f"{issue.code}:{issue.logical_path}" for issue in report.issues[:5]
        )
        raise ValueError(f"source result tree is invalid ({job_id}): {reasons}")
    checksum_path = root / "checksums.json"
    if _sha256(checksum_path.read_bytes()) != expected_sha:
        raise ValueError(f"source checksums identity differs: {job_id}")
    checksums = json.loads(checksum_path.read_bytes())
    entries = checksums.get("entries")
    if not isinstance(entries, Mapping):
        raise ValueError(f"source checksum inventory is invalid: {job_id}")
    critical_names = (
        "references/cases.jsonl",
        "predictions/diarization.rttm",
    )
    critical: dict[str, dict[str, object]] = {}
    for name in critical_names:
        raw = entries.get(name)
        path = root / Path(*PurePosixPath(name).parts)
        if not isinstance(raw, Mapping) or not path.is_file():
            raise ValueError(f"source result lacks critical input {name}: {job_id}")
        payload = path.read_bytes()
        if raw.get("sha256") != _sha256(payload) or raw.get("bytes") != len(payload):
            raise ValueError(f"source critical checksum differs ({job_id}): {name}")
        critical[name] = {
            "sha256": raw["sha256"],
            "bytes": raw["bytes"],
        }

    cases_payload = (root / "references/cases.jsonl").read_text(encoding="utf-8")
    cases = [json.loads(line) for line in cases_payload.splitlines() if line.strip()]
    case_ids = [str(case.get("protocol_case_id") or "") for case in cases]
    if (
        not cases
        or any(not value for value in case_ids)
        or len(set(case_ids)) != len(cases)
    ):
        raise ValueError(f"source case identities are missing or duplicated: {job_id}")
    expected_split = (
        "development" if configuration_id == "H2_BASELINE_REFERENCE" else "evaluation"
    )
    observed_splits = {str(case.get("partition") or "") for case in cases}
    if observed_splits != {expected_split}:
        raise ValueError(
            f"source split firewall differs ({job_id}): {sorted(observed_splits)}"
        )
    run = json.loads((root / "run.json").read_bytes())
    reuse = run.get("reuse_identity")
    if not isinstance(reuse, Mapping) or reuse.get("partition") != expected_split:
        raise ValueError(f"source run split binding differs: {job_id}")

    predicted = parse_rttm(root / "predictions/diarization.rttm")
    by_case: dict[str, list[RttmTurn]] = defaultdict(list)
    for turn in predicted:
        by_case[turn.recording_id].append(turn)
    extra_predictions = sorted(set(by_case) - set(case_ids))
    if extra_predictions:
        raise ValueError(
            f"prediction RTTM contains undeclared cases ({job_id}): {extra_predictions[:3]}"
        )

    contamination: list[dict[str, object]] = []
    short_turns: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    latency: list[dict[str, object]] = []
    reference_inventory: dict[str, dict[str, object]] = {}
    reference_cache: dict[Path, list[RttmTurn]] = {}
    for case in cases:
        case_id = str(case["protocol_case_id"])
        reference_path = _safe_reference_path(case, workspace)
        if reference_path not in reference_cache:
            reference_cache[reference_path] = parse_rttm(reference_path)
        logical_name = str(case["reference_rttm_logical_path"])
        reference_inventory[logical_name] = {
            "sha256": str(case["reference_rttm_sha256"]).casefold(),
            "bytes": reference_path.stat().st_size,
        }
        product = _focused_case_events(
            case,
            reference_cache[reference_path],
            by_case.get(case_id, ()),
        )
        contamination.extend(dict(row) for row in product["contamination"])
        short_turns.extend(dict(row) for row in product["short_turns"])
        evidence.extend(dict(row) for row in product["evidence"])
        latency.extend(dict(row) for row in product["latency"])
    source = {
        "configuration_id": configuration_id,
        "mode": configuration.get("mode"),
        "evidence_split": expected_split,
        "source_job_id": job_id,
        "source_result_path": str(root),
        "source_result_sha256": expected_sha,
        "case_count": len(cases),
        "critical_inputs": critical,
        "reference_file_count": len(reference_inventory),
        "reference_inventory_sha256": _sha256(_canonical_json(reference_inventory)),
    }
    return source, [{"kind": "contamination", **row} for row in contamination] + [
        {"kind": "short_turn", **row} for row in short_turns
    ] + [{"kind": "evidence", **row} for row in evidence] + [
        {"kind": "latency", **row} for row in latency
    ]


def _metric_row(
    source: Mapping[str, object],
    *,
    metric_family: str,
    metric_id: str,
    variant: str,
    target_sec: float | None,
    observations: Sequence[Mapping[str, object]],
    estimator: str,
    numerator: float | None,
    denominator: float | None,
    value: float | None,
    unit: str,
    definition: str,
    censoring_policy: str = "",
    reason: str = "",
) -> dict[str, object]:
    status = "COMPUTED" if value is not None else "UNDEFINED_NO_APPLICABLE_OBSERVATIONS"
    low = high = None
    speaker_count = 0
    seed = None
    if value is not None:
        low, high, speaker_count, seed = _speaker_bootstrap(
            observations,
            estimator=estimator,
            identity=(
                f"{source.get('configuration_id')}:{metric_id}:{variant}:{target_sec}"
            ),
        )
        if low is None or high is None:
            status = "UNDEFINED_BOOTSTRAP"
            reason = (
                reason or "whole-speaker bootstrap could not produce all repetitions"
            )
    return {
        "schema_version": "h2-required-diarization-metric.v1",
        "configuration_id": source.get("configuration_id"),
        "mode": source.get("mode"),
        "evidence_split": source.get("evidence_split"),
        "source_job_id": source.get("source_job_id"),
        "source_result_sha256": source.get("source_result_sha256"),
        "metric_family": metric_family,
        "metric_id": metric_id,
        "variant": variant,
        "target_sec": target_sec,
        "metric_status": status,
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "unit": unit,
        "ci_lower_95": low,
        "ci_upper_95": high,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS if value is not None else None,
        "bootstrap_seed": seed,
        "resampling_unit": (
            f"global_speaker_id ({speaker_count} observed speakers)"
            if value is not None
            else "global_speaker_id"
        ),
        "definition": definition,
        "censoring_policy": censoring_policy,
        "reason": reason,
    }


def _computed_metric_rows(
    source: Mapping[str, object], events: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    clusters = [row for row in events if row.get("kind") == "contamination"]
    cluster_observations = [
        {
            "global_speaker_id": row["dominant_global_speaker_id"],
            "numerator": float(row["dominant_reference_fraction"])
            * float(row["predicted_duration_sec"]),
            "denominator": float(row["predicted_duration_sec"]),
            "value": float(row["dominant_reference_fraction"]),
        }
        for row in clusters
    ]
    cluster_num = sum(float(row["numerator"]) for row in cluster_observations)
    cluster_den = sum(float(row["denominator"]) for row in cluster_observations)
    rows.append(
        _metric_row(
            source,
            metric_family="diarization",
            metric_id="cluster_purity",
            variant="predicted_time_micro",
            target_sec=None,
            observations=cluster_observations,
            estimator="ratio",
            numerator=cluster_num,
            denominator=cluster_den,
            value=cluster_num / cluster_den if cluster_den > 0 else None,
            unit="ratio",
            definition="Dominant-reference overlap summed across predicted clusters divided by total predicted-cluster duration.",
        )
    )
    cluster_values = [float(row["value"]) for row in cluster_observations]
    rows.append(
        _metric_row(
            source,
            metric_family="diarization",
            metric_id="cluster_purity",
            variant="macro_predicted_cluster",
            target_sec=None,
            observations=cluster_observations,
            estimator="mean",
            numerator=sum(cluster_values),
            denominator=float(len(cluster_values)),
            value=statistics.fmean(cluster_values) if cluster_values else None,
            unit="ratio",
            definition="Unweighted mean dominant-reference fraction across predicted clusters.",
        )
    )

    short = [
        row
        for row in events
        if row.get("kind") == "short_turn" and float(row["duration_sec"]) < 2.0
    ]
    short_observations = [
        {
            "global_speaker_id": row["global_speaker_id"],
            "numerator": float(row["anonymous_speaker_correctness"])
            * float(row["duration_sec"]),
            "denominator": float(row["duration_sec"]),
            "value": float(row["anonymous_speaker_correctness"]),
        }
        for row in short
    ]
    short_values = [float(row["value"]) for row in short_observations]
    rows.append(
        _metric_row(
            source,
            metric_family="diarization",
            metric_id="short_turn_recall",
            variant="lt2s_macro_reference_turn",
            target_sec=2.0,
            observations=short_observations,
            estimator="mean",
            numerator=sum(short_values),
            denominator=float(len(short_values)),
            value=statistics.fmean(short_values) if short_values else None,
            unit="ratio",
            definition="Mean correctly mapped anonymous-speaker time fraction over reference turns shorter than 2 seconds.",
        )
    )
    short_num = sum(float(row["numerator"]) for row in short_observations)
    short_den = sum(float(row["denominator"]) for row in short_observations)
    rows.append(
        _metric_row(
            source,
            metric_family="diarization",
            metric_id="short_turn_recall",
            variant="lt2s_reference_time_micro",
            target_sec=2.0,
            observations=short_observations,
            estimator="ratio",
            numerator=short_num,
            denominator=short_den,
            value=short_num / short_den if short_den > 0 else None,
            unit="ratio",
            definition="Correctly mapped anonymous-speaker time divided by total reference time in turns shorter than 2 seconds.",
        )
    )

    for target in EVIDENCE_TARGETS:
        evidence = [
            row
            for row in events
            if row.get("kind") == "evidence"
            and math.isclose(float(row["target_sec"]), target)
        ]
        yield_observations = [
            {
                "global_speaker_id": row["global_speaker_id"],
                "numerator": float(bool(row["achieved"])),
                "denominator": 1.0,
                "value": float(bool(row["achieved"])),
            }
            for row in evidence
        ]
        achieved = sum(float(row["numerator"]) for row in yield_observations)
        appearances = float(len(yield_observations))
        rows.append(
            _metric_row(
                source,
                metric_family="diarization",
                metric_id="clean_evidence_yield",
                variant="speaker_appearance",
                target_sec=target,
                observations=yield_observations,
                estimator="mean",
                numerator=achieved,
                denominator=appearances,
                value=achieved / appearances if appearances > 0 else None,
                unit="ratio",
                definition="Speaker appearances accumulating at least the target duration in a predicted cluster with at least 95% reference-speaker purity divided by all speaker appearances.",
            )
        )

        latency = [
            row
            for row in events
            if row.get("kind") == "latency"
            and math.isclose(float(row["target_sec"]), target)
        ]
        restricted = [
            {
                "global_speaker_id": row["global_speaker_id"],
                "value": float(
                    row["latency_sec"] if row["achieved"] else row["censor_time_sec"]
                ),
            }
            for row in latency
        ]
        restricted_values = [float(row["value"]) for row in restricted]
        rows.append(
            _metric_row(
                source,
                metric_family="diarization",
                metric_id="time_to_clean_evidence",
                variant="restricted_median_lower_bound",
                target_sec=target,
                observations=restricted,
                estimator="median",
                numerator=None,
                denominator=float(len(restricted_values)),
                value=(
                    statistics.median(restricted_values) if restricted_values else None
                ),
                unit="seconds",
                definition="Median elapsed time from a speaker's first reference speech to accumulated target-duration evidence at at least 95% cluster purity, retaining not-reached observations.",
                censoring_policy="Not-reached speaker appearances are retained at remaining-session censor time; the result is a restricted lower bound, not a successful-only latency.",
            )
        )
        successful = [
            {
                "global_speaker_id": row["global_speaker_id"],
                "value": float(row["latency_sec"]),
            }
            for row in latency
            if row["achieved"] and row.get("latency_sec") is not None
        ]
        successful_values = [float(row["value"]) for row in successful]
        rows.append(
            _metric_row(
                source,
                metric_family="diarization",
                metric_id="time_to_clean_evidence",
                variant="successful_only_median",
                target_sec=target,
                observations=successful,
                estimator="median",
                numerator=None,
                denominator=float(len(successful_values)),
                value=(
                    statistics.median(successful_values) if successful_values else None
                ),
                unit="seconds",
                definition="Median time to target-duration evidence at at least 95% cluster purity among speaker appearances that reached the target.",
                censoring_policy="Successful appearances only; interpret together with clean-evidence yield and the restricted median lower bound.",
            )
        )
    return rows


def _unsupported_portable_rows(
    configuration: Mapping[str, object],
) -> list[dict[str, object]]:
    source = {
        "configuration_id": configuration.get("configuration_id"),
        "mode": configuration.get("mode"),
        "evidence_split": "not_directly_measured",
        "source_job_id": None,
        "source_result_sha256": None,
    }
    specifications = [
        ("cluster_purity", "predicted_time_micro", None, "ratio"),
        ("cluster_purity", "macro_predicted_cluster", None, "ratio"),
        ("short_turn_recall", "lt2s_macro_reference_turn", 2.0, "ratio"),
        ("short_turn_recall", "lt2s_reference_time_micro", 2.0, "ratio"),
    ]
    for target in EVIDENCE_TARGETS:
        specifications.extend(
            (
                ("clean_evidence_yield", "speaker_appearance", target, "ratio"),
                (
                    "time_to_clean_evidence",
                    "restricted_median_lower_bound",
                    target,
                    "seconds",
                ),
                (
                    "time_to_clean_evidence",
                    "successful_only_median",
                    target,
                    "seconds",
                ),
            )
        )
    return [
        {
            **_metric_row(
                source,
                metric_family="diarization",
                metric_id=metric_id,
                variant=variant,
                target_sec=target,
                observations=(),
                estimator="mean",
                numerator=None,
                denominator=None,
                value=None,
                unit=unit,
                definition="See directly measured H2 configuration rows for the frozen definition.",
                reason="Portable ONNX is a parity/deployment candidate without an independent held-out RTTM run; scores are not copied from the native backend.",
            ),
            "metric_status": "NOT_DIRECTLY_MEASURED_PARITY_ONLY",
        }
        for metric_id, variant, target, unit in specifications
    ]


def build_required_metric_supplement(
    source_payloads: Mapping[str, bytes], workspace: Path
) -> tuple[dict[str, bytes], dict[str, object]]:
    registry_name = "summary/h2_configuration_registry.yaml"
    state_name = "controller/program_state.json"
    if registry_name not in source_payloads or state_name not in source_payloads:
        raise ValueError(
            "native package lacks registry/controller state for metric supplement"
        )
    registry = yaml.safe_load(source_payloads[registry_name])
    state = json.loads(source_payloads[state_name])
    if not isinstance(registry, Mapping) or not isinstance(state, Mapping):
        raise ValueError("native registry/controller state is invalid")
    configurations = registry.get("configurations")
    if not isinstance(configurations, list):
        raise ValueError("native H2 configuration registry lacks configurations")
    expected_ids = (
        "H2_BASELINE_REFERENCE",
        "H2_KNOWN_ONLY_OPTIMIZED",
        "H2_SESSION_ANONYMOUS_OPTIMIZED",
        "H2_SESSION_MEMORY_OPTIMIZED",
        "H2_PORTABLE_ONNX_FP32",
    )
    observed_ids = tuple(
        str(row.get("configuration_id") or "")
        for row in configurations
        if isinstance(row, Mapping)
    )
    if observed_ids != expected_ids:
        raise ValueError("native H2 configuration registry membership/order differs")

    metric_rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    for raw in configurations:
        if not isinstance(raw, Mapping):
            raise ValueError("native H2 configuration registry row is invalid")
        if raw.get("configuration_id") == "H2_PORTABLE_ONNX_FP32":
            metric_rows.extend(_unsupported_portable_rows(raw))
            continue
        source, events = _validated_result_inputs(
            workspace=workspace,
            state=state,
            configuration=raw,
        )
        source_rows.append(source)
        metric_rows.extend(_computed_metric_rows(source, events))
    if len(metric_rows) != 80:
        raise ValueError(
            f"required diarization metric row count differs: {len(metric_rows)}"
        )
    required_families = {
        "cluster_purity",
        "short_turn_recall",
        "clean_evidence_yield",
        "time_to_clean_evidence",
    }
    if {str(row["metric_id"]) for row in metric_rows} != required_families:
        raise ValueError("required diarization metric family coverage differs")
    measured = [row for row in metric_rows if row["metric_status"] == "COMPUTED"]
    if not measured or any(
        row.get("ci_lower_95") is None or row.get("ci_upper_95") is None
        for row in measured
    ):
        raise ValueError("computed required metrics lack whole-speaker intervals")

    provenance = {
        "schema_version": "h2-required-diarization-metric-provenance.v1",
        "status": "VALID",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "configuration_registry_member": registry_name,
        "configuration_registry_sha256": _sha256(source_payloads[registry_name]),
        "packaged_controller_state_sha256": _sha256(source_payloads[state_name]),
        "derivation_script_sha256": _sha256(Path(__file__).read_bytes()),
        "scientific_runtime_or_policy_changed": False,
        "development_and_heldout_evidence_pooled": False,
        "clean_cluster_purity_threshold": 0.95,
        "clean_evidence_targets_sec": list(EVIDENCE_TARGETS),
        "short_turn_upper_bound_sec_exclusive": 2.0,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_base_seed": BOOTSTRAP_SEED,
        "bootstrap_resampling_unit": "global_speaker_id with all observations retained together",
        "direct_result_sources": source_rows,
        "portable_onnx_policy": "NOT_DIRECTLY_MEASURED_PARITY_ONLY",
        "row_count": len(metric_rows),
        "computed_row_count": len(measured),
    }

    def display_metric(
        configuration_id: str,
        metric_id: str,
        variant: str,
        target_sec: float | None,
    ) -> str:
        row = next(
            value
            for value in metric_rows
            if value["configuration_id"] == configuration_id
            and value["metric_id"] == metric_id
            and value["variant"] == variant
            and value["target_sec"] == target_sec
        )
        if row["metric_status"] != "COMPUTED":
            return str(row["metric_status"])
        return (
            f"{float(row['value']):.4f} "
            f"[{float(row['ci_lower_95']):.4f}, {float(row['ci_upper_95']):.4f}]"
        )

    table = [
        "| Configuration | Split | Cluster purity | Short-turn recall | 2 s clean yield | 2 s restricted latency | 2 s successful latency |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for configuration_id in expected_ids:
        split = next(
            str(row["evidence_split"])
            for row in metric_rows
            if row["configuration_id"] == configuration_id
        )
        table.append(
            "| "
            + " | ".join(
                (
                    configuration_id,
                    split,
                    display_metric(
                        configuration_id,
                        "cluster_purity",
                        "predicted_time_micro",
                        None,
                    ),
                    display_metric(
                        configuration_id,
                        "short_turn_recall",
                        "lt2s_macro_reference_turn",
                        2.0,
                    ),
                    display_metric(
                        configuration_id,
                        "clean_evidence_yield",
                        "speaker_appearance",
                        2.0,
                    ),
                    display_metric(
                        configuration_id,
                        "time_to_clean_evidence",
                        "restricted_median_lower_bound",
                        2.0,
                    ),
                    display_metric(
                        configuration_id,
                        "time_to_clean_evidence",
                        "successful_only_median",
                        2.0,
                    ),
                )
            )
            + " |"
        )
    guide = (
        "# Required H2 diarization metric supplement\n\n"
        "This checksum-bound post-run analysis closes four explicit metric families "
        "from the frozen H2 specification: cluster purity, short-turn recall, "
        "clean-evidence yield, and time to clean evidence. It reuses the existing "
        "standalone-diarization definitions against immutable full-pipeline reference "
        "and prediction RTTMs; it performs no inference and changes no frozen policy.\n\n"
        "The historical baseline is reported only on development evidence. The three "
        "optimized product modes are reported only on untouched held-out evaluation "
        "evidence. They are never pooled. The portable ONNX candidate is marked "
        "parity-only because it has no independent held-out RTTM campaign.\n\n"
        "All computed rows include deterministic 95% intervals from 2,000 whole-speaker "
        "bootstrap repetitions. Clean evidence requires at least 95% predicted-cluster "
        "purity and is reported at 0.75, 1.5, 2.0, and 3.0 seconds. Not-reached latency "
        "observations remain visible through a restricted, censor-time lower bound; "
        "successful-only latency is reported separately.\n\n"
        "Values below are point estimates with deterministic 95% whole-speaker "
        "intervals. Latency values are seconds.\n\n" + "\n".join(table) + "\n\n"
        "See `h2_required_diarization_metrics_provenance.json` for every source job, "
        "result checksum, critical RTTM/case checksum, split, and derivation identity.\n"
    ).encode("utf-8")
    payloads = {
        REQUIRED_METRIC_MEMBERS[0]: _csv_payload(metric_rows, METRIC_FIELDS),
        REQUIRED_METRIC_MEMBERS[1]: guide,
        REQUIRED_METRIC_MEMBERS[2]: _canonical_json(provenance),
    }
    return payloads, provenance


TRANSCRIPT_METRIC_FIELDS = (
    "schema_version",
    "configuration_id",
    "paragraph_policy",
    "mode",
    "evidence_split",
    "source_job_id",
    "source_result_sha256",
    "metric_id",
    "variant",
    "metric_status",
    "value",
    "numerator",
    "denominator",
    "unit",
    "ci_lower_95",
    "ci_upper_95",
    "bootstrap_repetitions",
    "bootstrap_seed",
    "resampling_unit",
    "definition",
    "reason",
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _validated_bound_result(
    *,
    state: Mapping[str, object],
    job_id: str,
    expected_sha256: str,
    critical_names: Sequence[str],
) -> tuple[Path, dict[str, object], dict[str, dict[str, object]]]:
    jobs = state.get("jobs")
    if not isinstance(jobs, Mapping):
        raise ValueError("packaged controller state lacks job bindings")
    raw_job = jobs.get(job_id)
    if not isinstance(raw_job, Mapping) or raw_job.get("state") != "COMPLETE":
        raise ValueError(f"transcript source job is not complete: {job_id}")
    if len(expected_sha256) != 64 or raw_job.get("result_sha256") != expected_sha256:
        raise ValueError(f"transcript source result identity differs: {job_id}")
    raw_path = raw_job.get("result_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"transcript source result path is absent: {job_id}")
    root = Path(raw_path).resolve(strict=True)
    results_root = Path(str(state.get("results_root") or "")).resolve(strict=True)
    try:
        root.relative_to(results_root)
    except ValueError as exc:
        raise ValueError(
            f"transcript source escaped controller results root: {job_id}"
        ) from exc
    report = validate_result_tree(root)
    if not report.reusable:
        reasons = "; ".join(
            f"{issue.code}:{issue.logical_path}" for issue in report.issues[:5]
        )
        raise ValueError(
            f"transcript source result tree is invalid ({job_id}): {reasons}"
        )
    checksum_path = root / "checksums.json"
    if _sha256(checksum_path.read_bytes()) != expected_sha256:
        raise ValueError(f"transcript source checksums identity differs: {job_id}")
    checksums = json.loads(checksum_path.read_bytes())
    entries = checksums.get("entries")
    if not isinstance(entries, Mapping):
        raise ValueError(f"transcript source checksum inventory is invalid: {job_id}")
    critical: dict[str, dict[str, object]] = {}
    for name in critical_names:
        raw = entries.get(name)
        path = root / Path(*PurePosixPath(name).parts)
        if not isinstance(raw, Mapping) or not path.is_file():
            raise ValueError(f"transcript source lacks {name}: {job_id}")
        expected_bytes = raw.get("bytes")
        expected_file_sha = str(raw.get("sha256") or "")
        if expected_bytes != path.stat().st_size or len(expected_file_sha) != 64:
            raise ValueError(f"transcript source inventory differs ({job_id}): {name}")
        # validate_result_tree above has already streamed and checked every file.
        critical[name] = {
            "sha256": expected_file_sha,
            "bytes": expected_bytes,
        }
    pipeline = json.loads((root / "pipeline_identity.json").read_bytes())
    return root, pipeline, critical


def _span_order_key(span: Mapping[str, object]) -> tuple[bool, float, str]:
    start = _number(span.get("start_sec"))
    return (
        start is None,
        start if start is not None else float("inf"),
        str(span.get("span_id")),
    )


def _span_speaker_key(span: Mapping[str, object]) -> tuple[str | None, str | None]:
    anonymous = span.get("anonymous_speaker_id")
    label = span.get("speaker_label")
    if isinstance(label, Mapping):
        label = label.get("display_label")
    return (
        str(anonymous) if anonymous is not None else None,
        str(label) if label is not None else None,
    )


def _paragraph_groups(
    spans: Sequence[Mapping[str, object]],
    *,
    policy: str,
    pause_sec: float,
    maximum_words: int,
) -> list[dict[str, object]]:
    """Exact dictionary replay of the frozen ParagraphManager grouping rules."""

    ordered = sorted(spans, key=_span_order_key)
    if not ordered:
        return []
    groups: list[dict[str, object]] = []
    current: list[Mapping[str, object]] = []
    current_words = 0
    next_reason = "session_start"
    for candidate in ordered:
        reason: str | None = None
        candidate_words = len(str(candidate.get("text") or "").split())
        if current:
            if current_words + candidate_words > maximum_words:
                reason = "maximum_words"
            else:
                previous = current[-1]
                previous_end = _number(previous.get("end_sec"))
                candidate_start = _number(candidate.get("start_sec"))
                pause = (
                    candidate_start - previous_end
                    if previous_end is not None and candidate_start is not None
                    else 0.0
                )
                speaker_changed = _span_speaker_key(previous) != _span_speaker_key(
                    candidate
                )
                punctuation = (
                    str(previous.get("text") or "").rstrip().endswith((".", "?", "!"))
                )
                endpoint = str(previous.get("state") or "").lower() == "final"
                if policy == "T1_ASR_ENDPOINT_PUNCTUATION":
                    reason = (
                        "asr_endpoint_punctuation" if endpoint and punctuation else None
                    )
                elif policy == "T2_PAUSE_ASR_ENDPOINT":
                    if endpoint and pause >= pause_sec:
                        reason = "pause_asr_endpoint"
                    elif endpoint and punctuation:
                        reason = "asr_endpoint_punctuation"
                elif policy == "T3_PAUSE_ASR_SPEAKER_CHANGE":
                    if speaker_changed:
                        reason = "speaker_change"
                    elif endpoint and pause >= pause_sec:
                        reason = "pause_asr_endpoint"
                    elif endpoint and punctuation:
                        reason = "asr_endpoint_punctuation"
                elif policy == "T4_SPEAKER_CHANGE_DOMINANT":
                    if speaker_changed:
                        reason = "speaker_change_dominant"
                    elif pause >= pause_sec:
                        reason = "long_pause"
                else:
                    raise ValueError(f"unsupported paragraph policy: {policy}")
        if reason is not None and current:
            groups.append({"spans": tuple(current), "break_reason": next_reason})
            current = []
            current_words = 0
            next_reason = reason
        current.append(candidate)
        current_words += candidate_words
    if current:
        groups.append({"spans": tuple(current), "break_reason": next_reason})
    return groups


def _group_text(group: Mapping[str, object]) -> str:
    spans = group.get("spans")
    if not isinstance(spans, Sequence):
        return ""
    return " ".join(
        str(span.get("text") or "").strip()
        for span in spans
        if isinstance(span, Mapping)
    ).strip()


def _paragraph_snapshot(groups: Sequence[Mapping[str, object]]) -> tuple[object, ...]:
    output: list[object] = []
    for group in groups:
        spans = group.get("spans")
        if not isinstance(spans, Sequence):
            continue
        rows = [span for span in spans if isinstance(span, Mapping)]
        output.append(
            (
                tuple(str(span.get("span_id") or "") for span in rows),
                " ".join(_group_text(group).split()),
                tuple(_span_speaker_key(span) for span in rows),
            )
        )
    return tuple(output)


def _paragraph_structure_revised(
    previous: Sequence[Mapping[str, object]],
    current: Sequence[Mapping[str, object]],
) -> bool:
    def details(
        groups: Sequence[Mapping[str, object]],
    ) -> tuple[dict[str, int], dict[str, Mapping[str, object]]]:
        membership: dict[str, int] = {}
        spans: dict[str, Mapping[str, object]] = {}
        for group_index, group in enumerate(groups):
            raw_spans = group.get("spans")
            if not isinstance(raw_spans, Sequence):
                continue
            for span in raw_spans:
                if not isinstance(span, Mapping):
                    continue
                span_id = str(span.get("span_id") or "")
                if span_id:
                    membership[span_id] = group_index
                    spans[span_id] = span
        return membership, spans

    old_membership, old_spans = details(previous)
    new_membership, new_spans = details(current)
    common = sorted(
        set(old_spans) & set(new_spans), key=lambda key: _span_order_key(new_spans[key])
    )
    if any(
        _span_speaker_key(old_spans[key]) != _span_speaker_key(new_spans[key])
        for key in common
    ):
        return True
    if any(
        (old_membership[left] == old_membership[right])
        != (new_membership[left] == new_membership[right])
        for left, right in zip(common, common[1:])
    ):
        return True
    removed_final = {
        key
        for key, span in old_spans.items()
        if str(span.get("state") or "").lower() == "final" and key not in new_spans
    }
    return bool(removed_final)


def _matched_boundary_count(
    predicted: Sequence[float],
    reference: Sequence[float],
    tolerance_sec: float,
) -> int:
    candidates = sorted(
        (
            (abs(left - right), left_index, right_index)
            for left_index, left in enumerate(predicted)
            for right_index, right in enumerate(reference)
            if abs(left - right) <= tolerance_sec
        ),
        key=lambda row: (row[0], row[1], row[2]),
    )
    used_left: set[int] = set()
    used_right: set[int] = set()
    for _distance, left_index, right_index in candidates:
        if left_index not in used_left and right_index not in used_right:
            used_left.add(left_index)
            used_right.add(right_index)
    return len(used_left)


def _reference_speakers_for_group(
    group: Mapping[str, object],
    references: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    raw_spans = group.get("spans")
    if not isinstance(raw_spans, Sequence):
        return ()
    speakers: set[str] = set()
    for span in raw_spans:
        if not isinstance(span, Mapping):
            continue
        start = _number(span.get("start_sec"))
        end = _number(span.get("end_sec"))
        if start is None or end is None or end <= start:
            continue
        for reference in references:
            ref_start = _number(reference.get("start_sec"))
            ref_end = _number(reference.get("end_sec"))
            speaker = str(reference.get("global_speaker_id") or "")
            if (
                ref_start is not None
                and ref_end is not None
                and speaker
                and min(end, ref_end) > max(start, ref_start)
            ):
                speakers.add(speaker)
    return tuple(sorted(speakers))


def _speaker_set_bootstrap_ratio(
    observations: Sequence[Mapping[str, object]],
    *,
    identity: str,
) -> tuple[float | None, float | None, int, int]:
    speakers = sorted(
        {
            str(speaker)
            for row in observations
            for speaker in row.get("speaker_ids", ())
            if str(speaker)
        }
    )
    seed = BOOTSTRAP_SEED + int(
        hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8], 16
    )
    if not speakers:
        return None, None, 0, seed
    randomizer = random.Random(seed)
    estimates: list[float] = []
    for _ in range(BOOTSTRAP_REPETITIONS):
        counts = defaultdict(int)
        for _speaker in speakers:
            counts[randomizer.choice(speakers)] += 1
        numerator = 0.0
        denominator = 0.0
        for row in observations:
            row_speakers = tuple(str(value) for value in row.get("speaker_ids", ()))
            if not row_speakers:
                continue
            weight = sum(counts[value] for value in row_speakers) / len(row_speakers)
            numerator += weight * float(row["numerator"])
            denominator += weight * float(row["denominator"])
        if denominator > 0:
            estimates.append(numerator / denominator)
    if len(estimates) != BOOTSTRAP_REPETITIONS:
        return None, None, len(speakers), seed
    return (
        _percentile(estimates, 0.025),
        _percentile(estimates, 0.975),
        len(speakers),
        seed,
    )


def _speaker_set_bootstrap_sum(
    observations: Sequence[Mapping[str, object]],
    *,
    identity: str,
) -> tuple[float | None, float | None, int, int]:
    """Whole-speaker block bootstrap for additive case-level quantities."""

    speakers = sorted(
        {
            str(speaker)
            for row in observations
            for speaker in row.get("speaker_ids", ())
            if str(speaker)
        }
    )
    seed = BOOTSTRAP_SEED + int(
        hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8], 16
    )
    if not speakers:
        return None, None, 0, seed
    randomizer = random.Random(seed)
    estimates: list[float] = []
    for _ in range(BOOTSTRAP_REPETITIONS):
        counts = defaultdict(int)
        for _speaker in speakers:
            counts[randomizer.choice(speakers)] += 1
        estimate = 0.0
        for row in observations:
            row_speakers = tuple(str(value) for value in row.get("speaker_ids", ()))
            if not row_speakers:
                continue
            weight = sum(counts[value] for value in row_speakers) / len(row_speakers)
            estimate += weight * float(row["value"])
        estimates.append(estimate)
    return (
        _percentile(estimates, 0.025),
        _percentile(estimates, 0.975),
        len(speakers),
        seed,
    )


def _overlap_manifest_jobs(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, object], dict[str, Mapping[str, object]]]:
    name = "protocol/job_manifest.json"
    if name not in source_payloads:
        raise ValueError("native package lacks the frozen job manifest")
    manifest = json.loads(source_payloads[name])
    if not isinstance(manifest, Mapping) or not isinstance(manifest.get("jobs"), list):
        raise ValueError("native package job manifest is invalid")
    matches: dict[str, Mapping[str, object]] = {}
    for raw in manifest["jobs"]:
        if not isinstance(raw, Mapping):
            continue
        configuration_id = str(raw.get("configuration_id") or "")
        if configuration_id in OVERLAP_CONFIGURATIONS:
            if configuration_id in matches:
                raise ValueError(f"duplicate overlap configuration: {configuration_id}")
            matches[configuration_id] = raw
    if tuple(sorted(matches)) != tuple(sorted(OVERLAP_CONFIGURATIONS)):
        raise ValueError("frozen overlap configuration membership differs")
    return dict(manifest), matches


def _overlap_case_group(case: Mapping[str, object]) -> tuple[str, str]:
    overlay = str(case.get("overlay_id") or "")
    composition = OVERLAP_COMPOSITIONS.get(overlay)
    if composition is None:
        raise ValueError(f"unexpected overlap-panel identity overlay: {overlay}")
    known = int(case.get("known_speaker_count") or 0)
    unknown = int(case.get("unknown_speaker_count") or 0)
    speaker_count = len(tuple(case.get("global_speaker_ids") or ()))
    if (
        known + unknown != speaker_count
        or (overlay == "ALL_KNOWN" and (known < 1 or unknown != 0))
        or (overlay == "ALL_UNKNOWN" and (known != 0 or unknown < 1))
        or (
            overlay == "MIXED_KNOWN_UNKNOWN"
            and (
                speaker_count < 1 or (speaker_count > 1 and (known < 1 or unknown < 1))
            )
        )
    ):
        raise ValueError(f"overlap-panel composition annotation differs: {overlay}")
    ratio = _number(case.get("overlap_ratio"))
    overlap_class = str(case.get("overlap") or "")
    if ratio is None or ratio < 0:
        raise ValueError("overlap-panel case lacks a valid reference overlap ratio")
    if ratio == 0:
        # The scenario class records the intended conversational condition,
        # while the numeric ratio records whether simultaneous reference
        # speech actually materialized in the selected clip.  A small number
        # of intended backchannel cases contain no simultaneous reference
        # speech and therefore belong in the measured no-overlap control.
        condition = "NO_OVERLAP_CONTROL"
    else:
        if overlap_class == "none":
            raise ValueError("no-overlap-labelled case has positive reference overlap")
        condition = "OVERLAP_PRESENT"
    return composition, condition


def build_overlap_stratified_supplement(
    source_payloads: Mapping[str, bytes], workspace: Path
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Derive overlap-composition views from immutable development result trees."""

    state_name = "controller/program_state.json"
    if state_name not in source_payloads:
        raise ValueError("native package lacks controller state for overlap supplement")
    state = json.loads(source_payloads[state_name])
    if not isinstance(state, Mapping):
        raise ValueError("packaged controller state is invalid")
    manifest, jobs = _overlap_manifest_jobs(source_payloads)
    if manifest.get("job_manifest_sha256") != state.get("job_manifest_sha256"):
        raise ValueError("overlap job manifest/controller binding differs")

    include = jobs[OVERLAP_CONFIGURATIONS[0]]
    exclude = jobs[OVERLAP_CONFIGURATIONS[1]]
    for configuration_id, raw in jobs.items():
        if (
            raw.get("development_only") is not True
            or raw.get("split") != "development"
            or raw.get("job_kind") != "runtime_accuracy"
        ):
            raise ValueError(
                f"overlap source is not development-only accuracy: {configuration_id}"
            )
    include_cases = tuple(map(str, include.get("case_ids") or ()))
    exclude_cases = tuple(map(str, exclude.get("case_ids") or ()))
    if not include_cases or include_cases != exclude_cases:
        raise ValueError("overlap source case sets/order differ")
    if _number(include.get("audio_duration_sec")) != _number(
        exclude.get("audio_duration_sec")
    ):
        raise ValueError("overlap source audio durations differ")
    include_tuning = dict(include.get("runtime_tuning") or {})
    exclude_tuning = dict(exclude.get("runtime_tuning") or {})
    include_policy = include_tuning.pop("overlap_policy", None)
    exclude_policy = exclude_tuning.pop("overlap_policy", None)
    if (
        include_policy != OVERLAP_CONFIGURATIONS[0]
        or exclude_policy != OVERLAP_CONFIGURATIONS[1]
        or include_tuning != exclude_tuning
    ):
        raise ValueError("overlap jobs vary more than the frozen overlap-policy axis")

    axis_bindings = state.get("axis_selections")
    raw_axis = (
        axis_bindings.get("overlap_policy")
        if isinstance(axis_bindings, Mapping)
        else None
    )
    if not isinstance(raw_axis, Mapping):
        raise ValueError("overlap-policy selection receipt binding is absent")
    axis_path = (workspace / "axis_selections/overlap_policy.json").resolve(strict=True)
    axis_payload = axis_path.read_bytes()
    if _sha256(axis_payload) != str(raw_axis.get("decision_sha256") or ""):
        raise ValueError("overlap-policy selection receipt checksum differs")
    axis = json.loads(axis_payload)
    selected = axis.get("selected_candidates") if isinstance(axis, Mapping) else None
    if not isinstance(selected, list) or len(selected) != 1 or selected[0] not in jobs:
        raise ValueError("overlap-policy selected candidate differs")

    rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    expected_case_set = set(include_cases)
    for configuration_id in OVERLAP_CONFIGURATIONS:
        raw_job = jobs[configuration_id]
        job_id = str(raw_job.get("job_id") or "")
        state_jobs = state.get("jobs")
        state_job = state_jobs.get(job_id) if isinstance(state_jobs, Mapping) else None
        expected_sha = (
            str(state_job.get("result_sha256") or "")
            if isinstance(state_job, Mapping)
            else ""
        )
        root, pipeline, critical = _validated_bound_result(
            state=state,
            job_id=job_id,
            expected_sha256=expected_sha,
            critical_names=(
                "diagnostics/per_case_metrics.jsonl",
                "references/cases.jsonl",
                "pipeline_identity.json",
            ),
        )
        pipeline_tuning = pipeline.get("runtime_tuning")
        if (
            not isinstance(pipeline_tuning, Mapping)
            or pipeline_tuning.get("overlap_policy") != configuration_id
        ):
            raise ValueError(
                f"overlap result policy identity differs: {configuration_id}"
            )
        cases = _read_jsonl(root / "references/cases.jsonl")
        metrics = _read_jsonl(root / "diagnostics/per_case_metrics.jsonl")
        ordered_ids = tuple(str(case.get("protocol_case_id") or "") for case in cases)
        if ordered_ids != include_cases:
            raise ValueError(f"overlap result case order differs: {configuration_id}")
        metric_by_case = {str(row.get("case_id") or ""): row for row in metrics}
        if set(metric_by_case) != expected_case_set or len(metric_by_case) != len(
            metrics
        ):
            raise ValueError(
                f"overlap per-case metric membership differs: {configuration_id}"
            )

        grouped: dict[
            tuple[str, str], list[tuple[Mapping[str, object], Mapping[str, object]]]
        ] = defaultdict(list)
        for case in cases:
            case_id = str(case.get("protocol_case_id") or "")
            if case.get("partition") != "development":
                raise ValueError("overlap result contains non-development material")
            grouped[_overlap_case_group(case)].append((case, metric_by_case[case_id]))
        expected_groups = {
            (composition, condition)
            for composition in OVERLAP_COMPOSITIONS.values()
            for condition in OVERLAP_CONDITIONS
        }
        if set(grouped) != expected_groups:
            raise ValueError(
                f"overlap result lacks required composition/control groups: {configuration_id}"
            )

        for composition in OVERLAP_COMPOSITIONS.values():
            for condition in OVERLAP_CONDITIONS:
                group = grouped[(composition, condition)]
                duration = sum(float(case["duration_sec"]) for case, _ in group)
                mean_overlap = statistics.fmean(
                    float(case["overlap_ratio"]) for case, _ in group
                )
                for report_id, metric_id, aggregation in OVERLAP_METRICS:
                    observations: list[dict[str, object]] = []
                    skipped = 0
                    unit = ""
                    definition = ""
                    reasons: set[str] = set()
                    for case, per_case in group:
                        reports = per_case.get("reports")
                        report = (
                            reports.get(report_id)
                            if isinstance(reports, Mapping)
                            else None
                        )
                        metric_map = (
                            report.get("metrics")
                            if isinstance(report, Mapping)
                            else None
                        )
                        metric = (
                            metric_map.get(metric_id)
                            if isinstance(metric_map, Mapping)
                            else None
                        )
                        if not isinstance(metric, Mapping):
                            raise ValueError(
                                f"overlap metric is absent ({configuration_id}, {metric_id})"
                            )
                        unit = str(metric.get("unit") or unit)
                        definition = str(metric.get("definition") or definition)
                        if metric.get("status") != "computed":
                            skipped += 1
                            reasons.add(
                                str(
                                    metric.get("reason")
                                    or metric.get("status")
                                    or "unavailable"
                                )
                            )
                            continue
                        speaker_ids = tuple(
                            str(value) for value in case.get("global_speaker_ids", ())
                        )
                        if aggregation == "weighted_ratio":
                            numerator = _number(metric.get("numerator"))
                            denominator = _number(metric.get("denominator"))
                            if (
                                numerator is None
                                or denominator is None
                                or denominator <= 0
                            ):
                                raise ValueError(
                                    f"computed overlap ratio lacks sufficient statistics: {metric_id}"
                                )
                            observations.append(
                                {
                                    "speaker_ids": speaker_ids,
                                    "numerator": numerator,
                                    "denominator": denominator,
                                }
                            )
                        else:
                            details = metric.get("details")
                            value = _number(metric.get("value"))
                            if (
                                value is None
                                or not isinstance(details, Mapping)
                                or details.get("scalar_aggregation") != "sum"
                            ):
                                raise ValueError(
                                    f"computed overlap scalar is not additively aggregable: {metric_id}"
                                )
                            observations.append(
                                {"speaker_ids": speaker_ids, "value": value}
                            )
                    identity = "|".join(
                        (configuration_id, composition, condition, metric_id)
                    )
                    if aggregation == "weighted_ratio" and observations:
                        numerator = sum(float(row["numerator"]) for row in observations)
                        denominator = sum(
                            float(row["denominator"]) for row in observations
                        )
                        value = numerator / denominator
                        lower, upper, speaker_count, seed = (
                            _speaker_set_bootstrap_ratio(
                                observations, identity=identity
                            )
                        )
                    elif observations:
                        numerator = None
                        denominator = None
                        value = sum(float(row["value"]) for row in observations)
                        lower, upper, speaker_count, seed = _speaker_set_bootstrap_sum(
                            observations, identity=identity
                        )
                    else:
                        numerator = denominator = value = lower = upper = None
                        speaker_count = 0
                        seed = BOOTSTRAP_SEED + int(
                            hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8], 16
                        )
                    status = (
                        "UNSUPPORTED_OR_UNDEFINED"
                        if not observations
                        else "COMPUTED_APPLICABLE_CASES"
                        if skipped
                        else "COMPUTED"
                    )
                    if observations and (
                        lower is None or upper is None or speaker_count < 1
                    ):
                        raise ValueError(
                            "computed overlap metric lacks whole-speaker interval"
                        )
                    rows.append(
                        {
                            "schema_version": "h2-overlap-stratified-metric.v1",
                            "configuration_id": configuration_id,
                            "overlap_policy": configuration_id,
                            "evidence_split": "development",
                            "composition": composition,
                            "condition": condition,
                            "metric_id": metric_id,
                            "metric_status": status,
                            "value": value,
                            "numerator": numerator,
                            "denominator": denominator,
                            "unit": unit,
                            "ci_lower_95": lower,
                            "ci_upper_95": upper,
                            "bootstrap_repetitions": (
                                BOOTSTRAP_REPETITIONS if observations else 0
                            ),
                            "bootstrap_seed": seed,
                            "resampling_unit": "global_speaker_block",
                            "case_count": len(group),
                            "computed_case_count": len(observations),
                            "unsupported_or_undefined_case_count": skipped,
                            "audio_duration_sec": duration,
                            "mean_reference_overlap_ratio": mean_overlap,
                            "source_job_id": job_id,
                            "source_result_sha256": expected_sha,
                            "aggregation": aggregation,
                            "definition": definition,
                            "reason": "; ".join(sorted(reasons)),
                        }
                    )
        source_rows.append(
            {
                "configuration_id": configuration_id,
                "job_id": job_id,
                "result_sha256": expected_sha,
                "case_count": len(cases),
                "audio_duration_sec": sum(
                    float(case["duration_sec"]) for case in cases
                ),
                "critical_files": critical,
            }
        )

    expected_rows = (
        len(OVERLAP_CONFIGURATIONS)
        * len(OVERLAP_COMPOSITIONS)
        * len(OVERLAP_CONDITIONS)
        * len(OVERLAP_METRICS)
    )
    if len(rows) != expected_rows:
        raise ValueError(f"overlap stratified metric row count differs: {len(rows)}")
    provenance = {
        "schema_version": "h2-overlap-stratified-provenance.v1",
        "status": "VALID",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "packaged_controller_state_sha256": _sha256(source_payloads[state_name]),
        "derivation_script_sha256": _sha256(Path(__file__).read_bytes()),
        "development_only": True,
        "evaluation_material_inspected": False,
        "post_hoc_metrics_used_for_frozen_selection": False,
        "scientific_runtime_or_policy_changed": False,
        "source_case_sets_and_order_identical": True,
        "only_result_affecting_axis_varied": "overlap_policy",
        "selected_overlap_policy": selected[0],
        "selection_receipt_sha256": _sha256(axis_payload),
        "composition_definition": {
            "KNOWN_KNOWN": "ALL_KNOWN overlay: every participating reference speaker is enrolled; this includes one-speaker controls.",
            "KNOWN_UNKNOWN": "MIXED_KNOWN_UNKNOWN overlay stratum: multi-speaker cases contain at least one enrolled and one unenrolled reference speaker; deterministic one-speaker controls may contain either one enrolled or one unenrolled speaker.",
            "UNKNOWN_UNKNOWN": "ALL_UNKNOWN overlay: every participating reference speaker is unenrolled; this includes one-speaker controls.",
        },
        "condition_definition": {
            "OVERLAP_PRESENT": "Reference overlap class is not none and overlap_ratio is greater than zero.",
            "NO_OVERLAP_CONTROL": "Measured reference overlap_ratio is exactly zero. The intended scenario class may be non-none when simultaneous reference speech did not materialize in the selected clip.",
        },
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_base_seed": BOOTSTRAP_SEED,
        "bootstrap_method": "multi-membership global-speaker block bootstrap; each case weight is the mean resampled multiplicity of its participating speakers",
        "row_count": len(rows),
        "sources": source_rows,
    }

    def formatted(row: Mapping[str, object]) -> str:
        value = _number(row.get("value"))
        return str(row["metric_status"]) if value is None else f"{value:.4f}"

    guide = [
        "# H2 overlap-stratified development results",
        "",
        "This checksum-bound supplement separates overlap-policy results by identity composition and by overlap-present versus matched no-overlap control cases. It is a post-run analysis of the two immutable development jobs; it did not inspect evaluation material, change a frozen policy, or influence policy selection.",
        "",
        "`KNOWN_KNOWN` means the `ALL_KNOWN` overlay (all participating speakers enrolled), `KNOWN_UNKNOWN` is the nominal `MIXED_KNOWN_UNKNOWN` overlay stratum, and `UNKNOWN_UNKNOWN` means `ALL_UNKNOWN`. Multi-speaker mixed cases contain both enrolled and unenrolled speakers; deterministic one-speaker mixed controls may contain either one enrolled or one unenrolled speaker.",
        "",
        "Values marked `COMPUTED_APPLICABLE_CASES` exclude only cases where the source metric was explicitly unsupported or undefined. The CSV records those counts and the reason. Confidence intervals resample complete global-speaker blocks 2,000 times.",
        "",
        f"Frozen selected overlap policy: `{selected[0]}`.",
        "",
        "| Policy | Composition | Condition | Miss | Stable name (s) | Merge contamination | Wrong-known (s) | Stranger false-known (s) | Identity merges | Word speaker accuracy | Generic-known (s) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    by_key = {
        (
            str(row["configuration_id"]),
            str(row["composition"]),
            str(row["condition"]),
            str(row["metric_id"]),
        ): row
        for row in rows
    }
    for configuration_id in OVERLAP_CONFIGURATIONS:
        for composition in OVERLAP_COMPOSITIONS.values():
            for condition in OVERLAP_CONDITIONS:
                values = [
                    formatted(
                        by_key[(configuration_id, composition, condition, metric_id)]
                    )
                    for _report, metric_id, _aggregation in OVERLAP_METRICS
                ]
                guide.append(
                    "| "
                    + " | ".join((configuration_id, composition, condition, *values))
                    + " |"
                )
    guide.extend(
        (
            "",
            "The CSV is the authoritative machine-readable table and includes sufficient statistics, source identities, per-group exposure, metric availability, and 95% whole-speaker bootstrap intervals.",
            "",
        )
    )
    payloads = {
        REQUIRED_OVERLAP_MEMBERS[0]: _csv_payload(rows, OVERLAP_FIELDS),
        REQUIRED_OVERLAP_MEMBERS[1]: "\n".join(guide).encode("utf-8"),
        REQUIRED_OVERLAP_MEMBERS[2]: _canonical_json(provenance),
    }
    return payloads, provenance


def _transcript_metric_row(
    source: Mapping[str, object],
    *,
    metric_id: str,
    variant: str,
    value: float | None,
    numerator: float | None,
    denominator: float | None,
    unit: str,
    definition: str,
    observations: Sequence[Mapping[str, object]] = (),
    status: str | None = None,
    reason: str = "",
) -> dict[str, object]:
    resolved_status = status or (
        "COMPUTED" if value is not None else "UNDEFINED_NO_APPLICABLE_OBSERVATIONS"
    )
    low = high = None
    seed = None
    speaker_count = 0
    if resolved_status == "COMPUTED" and observations:
        low, high, speaker_count, seed = _speaker_set_bootstrap_ratio(
            observations,
            identity=f"{source.get('configuration_id')}:{metric_id}:{variant}",
        )
        if low is None or high is None:
            resolved_status = "UNDEFINED_BOOTSTRAP"
            reason = reason or "speaker-set bootstrap did not produce all repetitions"
    return {
        "schema_version": "h2-required-transcript-structure-metric.v1",
        "configuration_id": source.get("configuration_id"),
        "paragraph_policy": source.get("paragraph_policy"),
        "mode": source.get("mode"),
        "evidence_split": source.get("evidence_split"),
        "source_job_id": source.get("source_job_id"),
        "source_result_sha256": source.get("source_result_sha256"),
        "metric_id": metric_id,
        "variant": variant,
        "metric_status": resolved_status,
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "unit": unit,
        "ci_lower_95": low,
        "ci_upper_95": high,
        "bootstrap_repetitions": (
            BOOTSTRAP_REPETITIONS if low is not None and high is not None else None
        ),
        "bootstrap_seed": seed,
        "resampling_unit": (
            f"multi-membership global-speaker block ({speaker_count} speakers)"
            if speaker_count
            else "not applicable"
        ),
        "definition": definition,
        "reason": reason,
    }


def _event_replay_stats(
    path: Path,
    *,
    eligible_case_ids: set[str],
    final_groups: Mapping[str, Sequence[Mapping[str, object]]],
    policy: str,
    pause_sec: float,
    maximum_words: int,
) -> dict[str, dict[str, float]]:
    previous: dict[str, list[dict[str, object]]] = {}
    stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"revisions": 0.0, "transitions": 0.0}
    )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("event_type") != "transcript_revision":
                continue
            case_id = str(event.get("evaluation_case_id") or "")
            spans = event.get("spans")
            if case_id not in eligible_case_ids or not isinstance(spans, list):
                continue
            groups = _paragraph_groups(
                [row for row in spans if isinstance(row, Mapping)],
                policy=policy,
                pause_sec=pause_sec,
                maximum_words=maximum_words,
            )
            if case_id in previous:
                stats[case_id]["transitions"] += 1.0
                if _paragraph_structure_revised(previous[case_id], groups):
                    stats[case_id]["revisions"] += 1.0
            previous[case_id] = groups
    for case_id in eligible_case_ids:
        final = final_groups.get(case_id)
        last = previous.get(case_id)
        stats[case_id]["final_eligible"] = float(final is not None and last is not None)
        stats[case_id]["final_agreement"] = float(
            final is not None
            and last is not None
            and _paragraph_snapshot(final) == _paragraph_snapshot(last)
        )
    return dict(stats)


def _source_word_speaker_accuracy(root: Path) -> Mapping[str, object]:
    metrics = json.loads((root / "metrics/asr.json").read_bytes())
    try:
        raw = metrics["subviews"]["speaker_transcription"]["metrics"][
            "word_speaker_label_accuracy"
        ]
    except (KeyError, TypeError) as exc:
        raise ValueError("source result lacks word-speaker attribution metric") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("source word-speaker attribution metric is invalid")
    return raw


def _transcript_source_rows(
    source_payloads: Mapping[str, bytes],
    state: Mapping[str, object],
    registry: Mapping[str, object],
) -> list[dict[str, object]]:
    manifest_name = "protocol/job_manifest.json"
    if manifest_name not in source_payloads:
        raise ValueError("native package lacks protocol/job_manifest.json")
    manifest = json.loads(source_payloads[manifest_name])
    if not isinstance(manifest, Mapping) or manifest.get(
        "job_manifest_sha256"
    ) != state.get("job_manifest_sha256"):
        raise ValueError("packaged transcript job manifest binding differs")
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("packaged transcript job manifest lacks jobs")
    policy_jobs = {
        str(row.get("configuration_id")): row
        for row in jobs
        if isinstance(row, Mapping)
        and row.get("job_kind") == "post_selection_paragraph_validation"
    }
    if tuple(sorted(policy_jobs)) != tuple(sorted(PARAGRAPH_POLICIES)):
        raise ValueError("four frozen paragraph-policy runtime jobs are required")
    rows: list[dict[str, object]] = []
    state_jobs = state.get("jobs")
    if not isinstance(state_jobs, Mapping):
        raise ValueError("controller state lacks transcript job results")
    for policy in PARAGRAPH_POLICIES:
        job = policy_jobs[policy]
        job_id = str(job.get("job_id") or "")
        result = state_jobs.get(job_id)
        if not isinstance(result, Mapping):
            raise ValueError(f"paragraph policy result binding is absent: {policy}")
        rows.append(
            {
                "configuration_id": policy,
                "paragraph_policy": policy,
                "mode": job.get("mode"),
                "evidence_split": "development",
                "source_job_id": job_id,
                "source_result_sha256": result.get("result_sha256"),
            }
        )
    configurations = registry.get("configurations")
    if not isinstance(configurations, list):
        raise ValueError("native registry lacks transcript configurations")
    heldout_ids = (
        "H2_KNOWN_ONLY_OPTIMIZED",
        "H2_SESSION_ANONYMOUS_OPTIMIZED",
        "H2_SESSION_MEMORY_OPTIMIZED",
    )
    by_id = {
        str(row.get("configuration_id") or ""): row
        for row in configurations
        if isinstance(row, Mapping)
    }
    for configuration_id in heldout_ids:
        configuration = by_id.get(configuration_id)
        if not isinstance(configuration, Mapping):
            raise ValueError(f"native registry lacks {configuration_id}")
        rows.append(
            {
                "configuration_id": configuration_id,
                "paragraph_policy": None,
                "mode": configuration.get("mode"),
                "evidence_split": "evaluation",
                "source_job_id": configuration.get("heldout_source_job_id"),
                "source_result_sha256": configuration.get(
                    "heldout_source_result_sha256"
                ),
            }
        )
    rows.append(
        {
            "configuration_id": "H2_PORTABLE_ONNX_FP32",
            "paragraph_policy": None,
            "mode": "H2_SESSION_MEMORY_ENHANCED",
            "evidence_split": "not_directly_measured",
            "source_job_id": None,
            "source_result_sha256": None,
        }
    )
    return rows


def _computed_transcript_rows(
    source: dict[str, object],
    *,
    state: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    job_id = str(source.get("source_job_id") or "")
    expected_sha = str(source.get("source_result_sha256") or "")
    critical_names = (
        "events.jsonl.gz",
        "metrics/asr.json",
        "pipeline_identity.json",
        "predictions/labelled_transcript.jsonl",
        "references/cases.jsonl",
        "references/selected_speaker_attributed_transcripts.jsonl",
    )
    root, pipeline, critical = _validated_bound_result(
        state=state,
        job_id=job_id,
        expected_sha256=expected_sha,
        critical_names=critical_names,
    )
    tuning = pipeline.get("runtime_tuning")
    if not isinstance(tuning, Mapping):
        raise ValueError(f"transcript source lacks runtime tuning: {job_id}")
    policy = str(tuning.get("paragraph_policy") or "")
    pause_sec = float(tuning.get("paragraph_pause_sec"))
    maximum_words = int(tuning.get("paragraph_max_words"))
    if policy not in PARAGRAPH_POLICIES or pause_sec < 0 or maximum_words < 1:
        raise ValueError(f"transcript source paragraph tuning is invalid: {job_id}")
    if source.get("paragraph_policy") not in {None, policy}:
        raise ValueError(
            f"transcript source paragraph-policy binding differs: {job_id}"
        )
    source["paragraph_policy"] = policy

    cases = _read_jsonl(root / "references/cases.jsonl")
    case_by_id = {
        str(row.get("protocol_case_id") or ""): row
        for row in cases
        if row.get("protocol_case_id")
    }
    observed_splits = {str(row.get("partition") or "") for row in cases}
    if observed_splits != {source["evidence_split"]}:
        raise ValueError(f"transcript source split firewall differs: {job_id}")
    references_by_source = {
        str(row.get("source_case_id") or ""): row
        for row in _read_jsonl(
            root / "references/selected_speaker_attributed_transcripts.jsonl"
        )
        if row.get("source_case_id")
    }
    spans_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for span in _read_jsonl(root / "predictions/labelled_transcript.jsonl"):
        case_id = str(span.get("case_id") or "")
        if case_id:
            spans_by_case[case_id].append(span)

    final_groups: dict[str, list[dict[str, object]]] = {}
    case_stats: list[dict[str, object]] = []
    word_values: list[float] = []
    supported_case_ids: set[str] = set()
    for case_id, case in sorted(case_by_id.items()):
        reference = references_by_source.get(str(case.get("source_case_id") or ""))
        if (
            not isinstance(reference, Mapping)
            or reference.get("speaker_attributed_transcript_status") != "supported"
        ):
            continue
        raw_segments = reference.get("segments")
        if not isinstance(raw_segments, list):
            continue
        segments = sorted(
            (
                row
                for row in raw_segments
                if isinstance(row, Mapping)
                and row.get("speaker_attributed_transcript_status") == "supported"
                and _number(row.get("start_sec")) is not None
                and _number(row.get("end_sec")) is not None
            ),
            key=lambda row: (
                float(row["start_sec"]),
                float(row["end_sec"]),
                str(row.get("reference_segment_id") or ""),
            ),
        )
        if not segments:
            continue
        groups = _paragraph_groups(
            spans_by_case.get(case_id, ()),
            policy=policy,
            pause_sec=pause_sec,
            maximum_words=maximum_words,
        )
        final_groups[case_id] = groups
        supported_case_ids.add(case_id)
        predicted_boundaries = [
            float(start)
            for group in groups[1:]
            if (
                start := _number(
                    next(
                        (
                            span.get("start_sec")
                            for span in group.get("spans", ())
                            if isinstance(span, Mapping)
                            and _number(span.get("start_sec")) is not None
                        ),
                        None,
                    )
                )
            )
            is not None
        ]
        reference_boundaries = [
            float(current["start_sec"])
            for previous, current in zip(segments, segments[1:])
            if float(current["start_sec"]) >= float(previous["end_sec"])
        ]
        matched = _matched_boundary_count(
            predicted_boundaries,
            reference_boundaries,
            PARAGRAPH_BOUNDARY_TOLERANCE_SEC,
        )
        paragraph_count = 0
        mixed_count = 0
        length_compliant = 0
        total_words = 0
        for group in groups:
            speakers = _reference_speakers_for_group(group, segments)
            words = len(_group_text(group).split())
            if not speakers or words < 1:
                continue
            paragraph_count += 1
            mixed_count += int(len(speakers) > 1)
            length_compliant += int(words <= maximum_words)
            total_words += words
            word_values.append(float(words))
        speakers = tuple(
            sorted(str(value) for value in case.get("global_speaker_ids", ()) if value)
        )
        if not speakers:
            speakers = tuple(
                sorted(
                    {
                        str(row.get("global_speaker_id"))
                        for row in segments
                        if row.get("global_speaker_id")
                    }
                )
            )
        case_stats.append(
            {
                "case_id": case_id,
                "speaker_ids": speakers,
                "over_numerator": float(len(predicted_boundaries) - matched),
                "over_denominator": float(len(predicted_boundaries)),
                "under_numerator": float(len(reference_boundaries) - matched),
                "under_denominator": float(len(reference_boundaries)),
                "mixed_numerator": float(mixed_count),
                "mixed_denominator": float(paragraph_count),
                "words_numerator": float(total_words),
                "words_denominator": float(paragraph_count),
                "length_numerator": float(length_compliant),
                "length_denominator": float(paragraph_count),
            }
        )

    replay = _event_replay_stats(
        root / "events.jsonl.gz",
        eligible_case_ids=supported_case_ids,
        final_groups=final_groups,
        policy=policy,
        pause_sec=pause_sec,
        maximum_words=maximum_words,
    )
    for row in case_stats:
        values = replay.get(str(row["case_id"]), {})
        row["revision_numerator"] = float(values.get("revisions", 0.0))
        row["revision_denominator"] = float(values.get("transitions", 0.0))
        row["final_numerator"] = float(values.get("final_agreement", 0.0))
        row["final_denominator"] = float(values.get("final_eligible", 0.0))

    def ratio_values(
        prefix: str,
    ) -> tuple[float | None, float, float, list[dict[str, object]]]:
        observations = [
            {
                "speaker_ids": row["speaker_ids"],
                "numerator": row[f"{prefix}_numerator"],
                "denominator": row[f"{prefix}_denominator"],
            }
            for row in case_stats
            if float(row[f"{prefix}_denominator"]) > 0
        ]
        numerator = sum(float(row["numerator"]) for row in observations)
        denominator = sum(float(row["denominator"]) for row in observations)
        return (
            numerator / denominator if denominator > 0 else None,
            numerator,
            denominator,
            observations,
        )

    metric_rows: list[dict[str, object]] = []
    definitions = (
        (
            "over_segmentation_rate",
            "unmatched_predicted_boundary_fraction",
            "over",
            "Predicted paragraph boundaries farther than 0.50 seconds from every eligible non-overlap reference-turn boundary / predicted paragraph boundaries.",
        ),
        (
            "under_segmentation_rate",
            "unmatched_reference_turn_boundary_fraction",
            "under",
            "Eligible non-overlap reference-turn boundaries without a predicted paragraph boundary within 0.50 seconds / eligible reference-turn boundaries.",
        ),
        (
            "mixed_speaker_paragraph_rate",
            "reference_overlap_macro_paragraph",
            "mixed",
            "Non-empty predicted paragraphs overlapping more than one reference global speaker / predicted paragraphs overlapping reference speech.",
        ),
        (
            "words_per_paragraph",
            "mean_nonempty_reference_overlapping",
            "words",
            "Predicted words summed across non-empty reference-overlapping paragraphs / those paragraphs.",
        ),
        (
            "paragraph_revision_rate",
            "structural_revision_event_fraction",
            "revision",
            "Transcript-revision transitions that change an existing final span, an existing speaker key, or a paragraph boundary between existing spans / eligible transcript-revision transitions.",
        ),
        (
            "final_stability",
            "final_event_export_snapshot_agreement_rate",
            "final",
            "Supported cases whose final event-replayed paragraph snapshot exactly matches the exported final labelled-transcript paragraph snapshot / cases with both snapshots.",
        ),
    )
    values_by_prefix: dict[
        str, tuple[float | None, float, float, list[dict[str, object]]]
    ] = {}
    for metric_id, variant, prefix, definition in definitions:
        values = ratio_values(prefix)
        values_by_prefix[prefix] = values
        value, numerator, denominator, observations = values
        metric_rows.append(
            _transcript_metric_row(
                source,
                metric_id=metric_id,
                variant=variant,
                value=value,
                numerator=numerator,
                denominator=denominator,
                unit="ratio",
                definition=definition,
                observations=observations,
            )
        )

    metric_rows.append(
        _transcript_metric_row(
            source,
            metric_id="words_per_paragraph",
            variant="median_nonempty_reference_overlapping",
            value=statistics.median(word_values) if word_values else None,
            numerator=None,
            denominator=float(len(word_values)),
            unit="words",
            definition="Median predicted word count across non-empty reference-overlapping paragraphs.",
            status="COMPUTED_DESCRIPTIVE_NO_INTERVAL" if word_values else None,
        )
    )
    revision_total = values_by_prefix["revision"][1]
    metric_rows.append(
        _transcript_metric_row(
            source,
            metric_id="paragraph_revision_count",
            variant="structural_revision_events",
            value=revision_total,
            numerator=revision_total,
            denominator=None,
            unit="events",
            definition="Count of event-replayed structural paragraph revisions under the frozen policy.",
            status="COMPUTED_DESCRIPTIVE_NO_INTERVAL",
        )
    )
    word_accuracy = _source_word_speaker_accuracy(root)
    word_value = _number(word_accuracy.get("value"))
    metric_rows.append(
        _transcript_metric_row(
            source,
            metric_id="word_level_speaker_attribution",
            variant="source_word_speaker_label_accuracy",
            value=word_value,
            numerator=_number(word_accuracy.get("numerator")),
            denominator=_number(word_accuracy.get("denominator")),
            unit=str(word_accuracy.get("unit") or "ratio"),
            definition=str(word_accuracy.get("definition") or ""),
            status=(
                "SOURCE_REPORTED_COMPUTED"
                if str(word_accuracy.get("status")) == "computed"
                and word_value is not None
                else "SOURCE_REPORTED_UNSUPPORTED"
            ),
            reason=str(word_accuracy.get("reason") or ""),
        )
    )
    over = values_by_prefix["over"][0]
    under = values_by_prefix["under"][0]
    mixed = values_by_prefix["mixed"][0]
    length_value, _length_num, _length_den, _length_obs = ratio_values("length")
    components = (
        None if over is None else 1.0 - over,
        None if under is None else 1.0 - under,
        None if mixed is None else 1.0 - mixed,
        length_value,
    )
    readability = None
    if all(value is not None for value in components):
        resolved = [max(0.0, float(value)) for value in components if value is not None]
        readability = (
            0.0
            if any(value == 0.0 for value in resolved)
            else len(resolved) / sum(1.0 / value for value in resolved)
        )
    metric_rows.append(
        _transcript_metric_row(
            source,
            metric_id="readability_proxy",
            variant="boundary_purity_length_harmonic_mean",
            value=readability,
            numerator=None,
            denominator=None,
            unit="ratio",
            definition="Fully disclosed descriptive harmonic mean of predicted-boundary precision, reference-boundary recall, single-reference-speaker paragraph rate, and 1-to-frozen-maximum-word length compliance; it was not used for frozen selection.",
            status=(
                "COMPUTED_DESCRIPTIVE_NO_INTERVAL" if readability is not None else None
            ),
        )
    )
    if len(metric_rows) != 10:
        raise ValueError(f"transcript metric row count differs for {job_id}")
    provenance = {
        **source,
        "source_result_path": str(root),
        "critical_inputs": critical,
        "supported_case_count": len(supported_case_ids),
        "paragraph_pause_sec": pause_sec,
        "paragraph_max_words": maximum_words,
        "boundary_tolerance_sec": PARAGRAPH_BOUNDARY_TOLERANCE_SEC,
        "reference_boundary_scope": "supported non-overlap reference-turn transitions",
        "event_replay_performed": True,
    }
    return metric_rows, provenance


def _unsupported_transcript_rows(
    source: Mapping[str, object],
) -> list[dict[str, object]]:
    specifications = (
        ("over_segmentation_rate", "unmatched_predicted_boundary_fraction", "ratio"),
        (
            "under_segmentation_rate",
            "unmatched_reference_turn_boundary_fraction",
            "ratio",
        ),
        ("mixed_speaker_paragraph_rate", "reference_overlap_macro_paragraph", "ratio"),
        ("words_per_paragraph", "mean_nonempty_reference_overlapping", "words"),
        ("paragraph_revision_rate", "structural_revision_event_fraction", "ratio"),
        ("final_stability", "final_event_export_snapshot_agreement_rate", "ratio"),
        ("words_per_paragraph", "median_nonempty_reference_overlapping", "words"),
        ("paragraph_revision_count", "structural_revision_events", "events"),
        (
            "word_level_speaker_attribution",
            "source_word_speaker_label_accuracy",
            "ratio",
        ),
        ("readability_proxy", "boundary_purity_length_harmonic_mean", "ratio"),
    )
    return [
        _transcript_metric_row(
            source,
            metric_id=metric_id,
            variant=variant,
            value=None,
            numerator=None,
            denominator=None,
            unit=unit,
            definition="See directly measured native H2 rows for the frozen definition.",
            status="NOT_DIRECTLY_MEASURED_PARITY_ONLY",
            reason="Portable ONNX is a parity/deployment candidate without an independent transcript-structure campaign; native scores are not copied.",
        )
        for metric_id, variant, unit in specifications
    ]


def build_transcript_structure_supplement(
    source_payloads: Mapping[str, bytes], workspace: Path
) -> tuple[dict[str, bytes], dict[str, object]]:
    registry_name = "summary/h2_configuration_registry.yaml"
    state_name = "controller/program_state.json"
    if registry_name not in source_payloads or state_name not in source_payloads:
        raise ValueError("native package lacks registry/controller transcript bindings")
    registry = yaml.safe_load(source_payloads[registry_name])
    state = json.loads(source_payloads[state_name])
    if not isinstance(registry, Mapping) or not isinstance(state, Mapping):
        raise ValueError("native transcript registry/controller state is invalid")
    sources = _transcript_source_rows(source_payloads, state, registry)
    metric_rows: list[dict[str, object]] = []
    provenance_rows: list[dict[str, object]] = []
    for source in sources:
        if source["configuration_id"] == "H2_PORTABLE_ONNX_FP32":
            metric_rows.extend(_unsupported_transcript_rows(source))
            continue
        rows, provenance = _computed_transcript_rows(source, state=state)
        metric_rows.extend(rows)
        provenance_rows.append(provenance)
    if len(metric_rows) != 80:
        raise ValueError(
            f"required transcript metric row count differs: {len(metric_rows)}"
        )
    required_ids = {
        "over_segmentation_rate",
        "under_segmentation_rate",
        "mixed_speaker_paragraph_rate",
        "words_per_paragraph",
        "paragraph_revision_count",
        "paragraph_revision_rate",
        "word_level_speaker_attribution",
        "final_stability",
        "readability_proxy",
    }
    if {str(row["metric_id"]) for row in metric_rows} != required_ids:
        raise ValueError("required transcript metric family coverage differs")
    computed = [
        row
        for row in metric_rows
        if str(row["metric_status"]).startswith("COMPUTED")
        or row["metric_status"] == "SOURCE_REPORTED_COMPUTED"
    ]
    if not computed:
        raise ValueError("required transcript supplement has no measured rows")
    provenance = {
        "schema_version": "h2-required-transcript-structure-provenance.v1",
        "status": "VALID",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "configuration_registry_sha256": _sha256(source_payloads[registry_name]),
        "packaged_controller_state_sha256": _sha256(source_payloads[state_name]),
        "derivation_script_sha256": _sha256(Path(__file__).read_bytes()),
        "paragraph_implementation_sha256": _sha256(
            (TOOL_ROOT / "app/full_pipeline/paragraphs.py").read_bytes()
        ),
        "scientific_runtime_or_policy_changed": False,
        "post_hoc_metrics_used_for_frozen_selection": False,
        "development_and_heldout_evidence_pooled": False,
        "boundary_tolerance_sec": PARAGRAPH_BOUNDARY_TOLERANCE_SEC,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_base_seed": BOOTSTRAP_SEED,
        "bootstrap_method": "multi-membership global-speaker block bootstrap; each case weight is the mean resampled multiplicity of its participating speakers",
        "direct_result_sources": provenance_rows,
        "portable_onnx_policy": "NOT_DIRECTLY_MEASURED_PARITY_ONLY",
        "row_count": len(metric_rows),
        "computed_row_count": len(computed),
    }

    def display(configuration_id: str, metric_id: str, variant: str) -> str:
        row = next(
            value
            for value in metric_rows
            if value["configuration_id"] == configuration_id
            and value["metric_id"] == metric_id
            and value["variant"] == variant
        )
        if row["value"] is None:
            return str(row["metric_status"])
        return f"{float(row['value']):.4f}"

    table = [
        "| Configuration | Split | Policy | Over-seg. | Under-seg. | Mixed | Mean words | Revision rate | Final stability | Readability proxy |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source in sources:
        configuration_id = str(source["configuration_id"])
        table.append(
            "| "
            + " | ".join(
                (
                    configuration_id,
                    str(source["evidence_split"]),
                    str(
                        next(
                            row["paragraph_policy"]
                            for row in metric_rows
                            if row["configuration_id"] == configuration_id
                        )
                    ),
                    display(
                        configuration_id,
                        "over_segmentation_rate",
                        "unmatched_predicted_boundary_fraction",
                    ),
                    display(
                        configuration_id,
                        "under_segmentation_rate",
                        "unmatched_reference_turn_boundary_fraction",
                    ),
                    display(
                        configuration_id,
                        "mixed_speaker_paragraph_rate",
                        "reference_overlap_macro_paragraph",
                    ),
                    display(
                        configuration_id,
                        "words_per_paragraph",
                        "mean_nonempty_reference_overlapping",
                    ),
                    display(
                        configuration_id,
                        "paragraph_revision_rate",
                        "structural_revision_event_fraction",
                    ),
                    display(
                        configuration_id,
                        "final_stability",
                        "final_event_export_snapshot_agreement_rate",
                    ),
                    display(
                        configuration_id,
                        "readability_proxy",
                        "boundary_purity_length_harmonic_mean",
                    ),
                )
            )
            + " |"
        )
    guide = (
        "# Required H2 transcript-structure metric supplement\n\n"
        "This checksum-bound, inference-free replay closes the explicit transcript "
        "structure measures from Section 19 of the frozen H2 specification. It "
        "reconstructs T1-T4 paragraphs with the exact saved runtime tuning, scores "
        "final structure against supported reference-turn transcripts, and replays "
        "saved transcript-revision snapshots to measure structural paragraph changes.\n\n"
        "Development T1-T4 results and held-out optimized-mode results remain separate. "
        "The reference data supplies utterance/turn boundaries, not authored human "
        "paragraphs, so over/under-segmentation are explicitly labelled 0.50-second "
        "reference-turn-boundary proxies. Simultaneous/overlap transitions are excluded "
        "from that boundary proxy and remain visible in mixed-speaker results.\n\n"
        "The readability proxy is a disclosed descriptive harmonic mean of boundary "
        "precision, boundary recall, single-speaker paragraph rate, and frozen maximum-"
        "length compliance. It is not a hidden composite and was not used to alter the "
        "frozen policy or held-out evaluation. Derived key rates use deterministic "
        "2,000-repetition multi-membership speaker-block intervals; descriptive medians, "
        "counts, source-reported word attribution, and the proxy are labelled without "
        "invented intervals.\n\n"
        + "\n".join(table)
        + "\n\nSee the provenance JSON for source jobs, result checksums, split firewall, "
        "critical-file identities, replay rules, and bootstrap method.\n"
    ).encode("utf-8")
    payloads = {
        REQUIRED_TRANSCRIPT_MEMBERS[0]: _csv_payload(
            metric_rows, TRANSCRIPT_METRIC_FIELDS
        ),
        REQUIRED_TRANSCRIPT_MEMBERS[1]: guide,
        REQUIRED_TRANSCRIPT_MEMBERS[2]: _canonical_json(provenance),
    }
    return payloads, provenance


def _asr_comparability_sources(
    registry: Mapping[str, object],
) -> list[dict[str, object]]:
    configurations = registry.get("configurations")
    if not isinstance(configurations, list):
        raise ValueError("native registry lacks ASR comparability configurations")
    by_id = {
        str(row.get("configuration_id") or ""): row
        for row in configurations
        if isinstance(row, Mapping)
    }
    sources: list[dict[str, object]] = []
    for configuration_id in ASR_COMPARABILITY_CONFIGURATIONS:
        configuration = by_id.get(configuration_id)
        if not isinstance(configuration, Mapping):
            raise ValueError(
                f"native registry lacks ASR comparability source {configuration_id}"
            )
        baseline = configuration_id == "H2_BASELINE_REFERENCE"
        job_key = "source_job_id" if baseline else "heldout_source_job_id"
        sha_key = "source_result_sha256" if baseline else "heldout_source_result_sha256"
        job_id = str(configuration.get(job_key) or "")
        result_sha256 = str(configuration.get(sha_key) or "")
        if not job_id or len(result_sha256) != 64:
            raise ValueError(
                f"ASR comparability result binding is incomplete: {configuration_id}"
            )
        sources.append(
            {
                "configuration_id": configuration_id,
                "mode": configuration.get("mode"),
                "evidence_split": "development" if baseline else "evaluation",
                "source_job_id": job_id,
                "source_result_sha256": result_sha256,
            }
        )
    return sources


def _ascii_punctuation_insensitive_words(value: object) -> tuple[str, ...]:
    translation = str.maketrans("", "", string.punctuation)
    return tuple(
        normalized
        for word in _normalized_scoring_words(value)
        if (normalized := word.translate(translation))
    )


def _ascii_punctuation_token_count(words: Sequence[str]) -> int:
    return sum(
        1
        for word in words
        if any(character in string.punctuation for character in word)
    )


def _asr_metric(
    root: Path, filename: str, subview: str, metric_id: str
) -> Mapping[str, object]:
    document = json.loads((root / filename).read_bytes())
    try:
        metric = document["subviews"][subview]["metrics"][metric_id]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"ASR comparability source lacks {subview}.{metric_id}"
        ) from exc
    if (
        not isinstance(metric, Mapping)
        or metric.get("status") != "computed"
        or _number(metric.get("value")) is None
        or _number(metric.get("numerator")) is None
        or _number(metric.get("denominator")) is None
    ):
        raise ValueError(
            f"ASR comparability source metric is not computed: {subview}.{metric_id}"
        )
    return metric


def _asr_strata(case: Mapping[str, object]) -> tuple[str, str, str]:
    scenario = case.get("scenario")
    raw_count = scenario.get("speaker_count") if isinstance(scenario, Mapping) else None
    speaker_count = int(
        _number(raw_count)
        or len([value for value in case.get("global_speaker_ids", ()) if str(value)])
        or 1
    )
    if speaker_count == 1:
        speaker_stratum = "SINGLE_SPEAKER"
    elif speaker_count <= 4:
        speaker_stratum = "TWO_TO_FOUR_SPEAKERS"
    else:
        speaker_stratum = "FIVE_TO_TWELVE_SPEAKERS"
    overlap = _number(case.get("overlap_ratio")) or 0.0
    overlap_stratum = "OVERLAP_PRESENT" if overlap > 0.0 else "NO_OVERLAP"
    return "OVERALL", speaker_stratum, overlap_stratum


def _asr_comparability_row(
    source: Mapping[str, object],
    *,
    metric_id: str,
    metric_role: str,
    scoring_policy_id: str,
    stratum: str,
    status: str,
    value: float | None,
    numerator: float | None,
    denominator: float | None,
    substitutions: float | None,
    deletions: float | None,
    insertions: float | None,
    reference_tokens_for_punctuation_rate: float | None,
    hypothesis_tokens_for_punctuation_rate: float | None,
    reference_ascii_punctuation_tokens: float | None,
    hypothesis_ascii_punctuation_tokens: float | None,
    reference_ascii_punctuation_token_rate: float | None,
    hypothesis_ascii_punctuation_token_rate: float | None,
    punctuation_sensitive_minus_insensitive_wer: float | None,
    source_reported_metric_match: bool | None,
    definition: str,
) -> dict[str, object]:
    return {
        "schema_version": "h2-asr-wer-comparability-row.v2",
        "configuration_id": source["configuration_id"],
        "mode": source["mode"],
        "evidence_split": source["evidence_split"],
        "source_job_id": source["source_job_id"],
        "metric_id": metric_id,
        "metric_role": metric_role,
        "scoring_policy_id": scoring_policy_id,
        "stratum": stratum,
        "metric_status": status,
        "value": value,
        "value_percent": None if value is None else 100.0 * value,
        "numerator": numerator,
        "denominator": denominator,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "reference_tokens_for_punctuation_rate": (
            reference_tokens_for_punctuation_rate
        ),
        "hypothesis_tokens_for_punctuation_rate": (
            hypothesis_tokens_for_punctuation_rate
        ),
        "reference_ascii_punctuation_tokens": reference_ascii_punctuation_tokens,
        "hypothesis_ascii_punctuation_tokens": hypothesis_ascii_punctuation_tokens,
        "reference_ascii_punctuation_token_rate": (
            reference_ascii_punctuation_token_rate
        ),
        "hypothesis_ascii_punctuation_token_rate": (
            hypothesis_ascii_punctuation_token_rate
        ),
        "punctuation_sensitive_minus_insensitive_wer": (
            punctuation_sensitive_minus_insensitive_wer
        ),
        "punctuation_sensitive_minus_insensitive_wer_percentage_points": (
            None
            if punctuation_sensitive_minus_insensitive_wer is None
            else 100.0 * punctuation_sensitive_minus_insensitive_wer
        ),
        "source_reported_metric_match": source_reported_metric_match,
        "scientific_selection_eligible": False,
        "definition": definition,
    }


def _computed_asr_comparability_rows(
    source: Mapping[str, object],
    *,
    state: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    job_id = str(source["source_job_id"])
    critical_names = (
        "metrics/asr.json",
        "metrics/streaming.json",
        "pipeline_identity.json",
        "predictions/labelled_transcript.jsonl",
        "references/cases.jsonl",
        "references/selected_speaker_attributed_transcripts.jsonl",
    )
    root, _pipeline, critical = _validated_bound_result(
        state=state,
        job_id=job_id,
        expected_sha256=str(source["source_result_sha256"]),
        critical_names=critical_names,
    )
    cases = _read_jsonl(root / "references/cases.jsonl")
    observed_splits = {str(row.get("partition") or "") for row in cases}
    if observed_splits != {source["evidence_split"]}:
        raise ValueError(f"ASR comparability split firewall differs: {job_id}")
    references = {
        str(row.get("source_case_id") or ""): row
        for row in _read_jsonl(
            root / "references/selected_speaker_attributed_transcripts.jsonl"
        )
        if row.get("source_case_id")
    }
    spans_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for span in _read_jsonl(root / "predictions/labelled_transcript.jsonl"):
        case_id = str(span.get("case_id") or "")
        if case_id:
            spans_by_case[case_id].append(span)

    policies = (
        (
            "lowercase_whitespace.v1",
            "FROZEN_H2_PROTOCOL_WER",
            _normalized_scoring_words,
        ),
        (
            "evaluation-text-normalization-punctuation-insensitive.v1",
            "CROSS_PROTOCOL_ASR_COMPARABILITY",
            _ascii_punctuation_insensitive_words,
        ),
    )
    totals: dict[tuple[str, str], list[float]] = defaultdict(
        lambda: [0.0, 0.0, 0.0, 0.0, 0.0]
    )
    punctuation_totals: dict[str, list[float]] = defaultdict(
        lambda: [0.0, 0.0, 0.0, 0.0]
    )
    for case in cases:
        case_id = str(case.get("protocol_case_id") or "")
        source_case_id = str(case.get("source_case_id") or "")
        reference = references.get(source_case_id)
        if not case_id or not isinstance(reference, Mapping):
            raise ValueError(f"ASR comparability reference is absent: {job_id}")
        segments = reference.get("segments")
        if not isinstance(segments, list):
            raise ValueError(f"ASR comparability segments are absent: {job_id}")
        reference_text = " ".join(
            str(row.get("scorable_transcript") or row.get("text") or "")
            for row in sorted(
                (row for row in segments if isinstance(row, Mapping)),
                key=lambda row: (
                    float(row.get("start_sec") or 0.0),
                    float(row.get("end_sec") or 0.0),
                    str(row.get("reference_segment_id") or ""),
                ),
            )
        ).strip()
        hypothesis_text = " ".join(
            str(row.get("text") or "")
            for row in sorted(spans_by_case.get(case_id, ()), key=_span_order_key)
        ).strip()
        frozen_reference_words = _normalized_scoring_words(reference_text)
        frozen_hypothesis_words = _normalized_scoring_words(hypothesis_text)
        for stratum in _asr_strata(case):
            punctuation_total = punctuation_totals[stratum]
            punctuation_total[0] += float(len(frozen_reference_words))
            punctuation_total[1] += float(len(frozen_hypothesis_words))
            punctuation_total[2] += float(
                _ascii_punctuation_token_count(frozen_reference_words)
            )
            punctuation_total[3] += float(
                _ascii_punctuation_token_count(frozen_hypothesis_words)
            )
        for policy_id, _role, normalizer in policies:
            reference_words = normalizer(reference_text)
            hypothesis_words = normalizer(hypothesis_text)
            errors, substitutions, deletions, insertions = _word_edit_counts(
                reference_words, hypothesis_words
            )
            for stratum in _asr_strata(case):
                total = totals[(policy_id, stratum)]
                total[0] += float(errors)
                total[1] += float(substitutions)
                total[2] += float(deletions)
                total[3] += float(insertions)
                total[4] += float(len(reference_words))

    frozen = _asr_metric(root, "metrics/asr.json", "asr", "wer")
    frozen_overall = totals[("lowercase_whitespace.v1", "OVERALL")]
    reported_match = all(
        math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)
        for left, right in (
            (frozen_overall[0], frozen["numerator"]),
            (frozen_overall[4], frozen["denominator"]),
            (
                frozen_overall[0] / frozen_overall[4],
                frozen["value"],
            ),
        )
    )
    if not reported_match:
        raise ValueError(f"recomputed frozen WER differs from source metric: {job_id}")

    rows: list[dict[str, object]] = []
    for policy_id, role, _normalizer in policies:
        for stratum in ASR_COMPARABILITY_STRATA:
            errors, substitutions, deletions, insertions, denominator = totals[
                (policy_id, stratum)
            ]
            value = errors / denominator if denominator > 0 else None
            (
                reference_punctuation_denominator,
                hypothesis_punctuation_denominator,
                reference_punctuation_tokens,
                hypothesis_punctuation_tokens,
            ) = punctuation_totals[stratum]
            sensitive = totals[("lowercase_whitespace.v1", stratum)]
            insensitive = totals[
                (
                    "evaluation-text-normalization-punctuation-insensitive.v1",
                    stratum,
                )
            ]
            sensitive_wer = sensitive[0] / sensitive[4] if sensitive[4] > 0 else None
            insensitive_wer = (
                insensitive[0] / insensitive[4] if insensitive[4] > 0 else None
            )
            punctuation_wer_gap = (
                sensitive_wer - insensitive_wer
                if sensitive_wer is not None and insensitive_wer is not None
                else None
            )
            rows.append(
                _asr_comparability_row(
                    source,
                    metric_id="wer",
                    metric_role=role,
                    scoring_policy_id=policy_id,
                    stratum=stratum,
                    status=(
                        "SOURCE_REPORTED_AND_RECOMPUTED"
                        if policy_id == "lowercase_whitespace.v1"
                        and stratum == "OVERALL"
                        else (
                            "POST_RUN_RECOMPUTED"
                            if denominator > 0
                            else "UNDEFINED_EMPTY_STRATUM"
                        )
                    ),
                    value=value,
                    numerator=errors,
                    denominator=denominator,
                    substitutions=substitutions,
                    deletions=deletions,
                    insertions=insertions,
                    reference_tokens_for_punctuation_rate=(
                        reference_punctuation_denominator
                    ),
                    hypothesis_tokens_for_punctuation_rate=(
                        hypothesis_punctuation_denominator
                    ),
                    reference_ascii_punctuation_tokens=reference_punctuation_tokens,
                    hypothesis_ascii_punctuation_tokens=hypothesis_punctuation_tokens,
                    reference_ascii_punctuation_token_rate=(
                        reference_punctuation_tokens / reference_punctuation_denominator
                        if reference_punctuation_denominator > 0
                        else None
                    ),
                    hypothesis_ascii_punctuation_token_rate=(
                        hypothesis_punctuation_tokens
                        / hypothesis_punctuation_denominator
                        if hypothesis_punctuation_denominator > 0
                        else None
                    ),
                    punctuation_sensitive_minus_insensitive_wer=punctuation_wer_gap,
                    source_reported_metric_match=(
                        True
                        if policy_id == "lowercase_whitespace.v1"
                        and stratum == "OVERALL"
                        else None
                    ),
                    definition=(
                        "Final exported transcript word edit errors divided by "
                        "reference words after lowercase and whitespace collapse."
                        if policy_id == "lowercase_whitespace.v1"
                        else "The same immutable final transcript and reference, "
                        "rescored after lowercase, ASCII-punctuation removal, and "
                        "whitespace collapse for comparison with the earlier "
                        "Common Voice ASR protocol."
                    ),
                )
            )

    endpoint = _asr_metric(root, "metrics/streaming.json", "streaming", "final_wer")
    rows.append(
        _asr_comparability_row(
            source,
            metric_id="final_wer",
            metric_role="ENDPOINT_WINDOW_DIAGNOSTIC_NOT_ORDINARY_WER",
            scoring_policy_id="endpoint_window_reference_mapping.v1",
            stratum="OVERALL",
            status="SOURCE_REPORTED_DIAGNOSTIC",
            value=float(endpoint["value"]),
            numerator=float(endpoint["numerator"]),
            denominator=float(endpoint["denominator"]),
            substitutions=None,
            deletions=None,
            insertions=None,
            reference_tokens_for_punctuation_rate=None,
            hypothesis_tokens_for_punctuation_rate=None,
            reference_ascii_punctuation_tokens=None,
            hypothesis_ascii_punctuation_tokens=None,
            reference_ascii_punctuation_token_rate=None,
            hypothesis_ascii_punctuation_token_rate=None,
            punctuation_sensitive_minus_insensitive_wer=None,
            source_reported_metric_match=True,
            definition=(
                "Source-reported WER over endpoint-final streams and their mapped "
                "reference windows. A source reference turn that crosses an "
                "endpoint boundary may contribute its full text to more than one "
                "adjacent endpoint window, so this denominator is not an ordinary "
                "exported-transcript WER denominator."
            ),
        )
    )
    return rows, {
        **source,
        "source_result_path": str(root),
        "critical_inputs": critical,
        "case_count": len(cases),
        "frozen_source_metric_recomputed_exactly": True,
        "frozen_reference_word_count": frozen_overall[4],
        "endpoint_reference_word_count": float(endpoint["denominator"]),
    }


def build_asr_wer_comparability_supplement(
    source_payloads: Mapping[str, bytes], workspace: Path
) -> tuple[dict[str, bytes], dict[str, object]]:
    del (
        workspace
    )  # Result paths are accepted only through packaged controller bindings.
    commonvoice_policy_payload = ASR_COMMONVOICE_POLICY_SOURCE.read_bytes()
    commonvoice_config = yaml.safe_load(commonvoice_policy_payload)
    normalization = (
        commonvoice_config.get("normalization")
        if isinstance(commonvoice_config, Mapping)
        else None
    )
    if (
        not isinstance(normalization, Mapping)
        or normalization.get("policy_id")
        != "evaluation-text-normalization-punctuation-insensitive.v1"
        or normalization.get("lowercase") is not True
        or normalization.get("remove_punctuation") is not True
        or normalization.get("strip_whitespace") is not True
        or normalization.get("collapse_whitespace") is not True
    ):
        raise ValueError("Common Voice ASR normalization contract differs")
    registry_name = "summary/h2_configuration_registry.yaml"
    state_name = "controller/program_state.json"
    if registry_name not in source_payloads or state_name not in source_payloads:
        raise ValueError("native package lacks ASR comparability bindings")
    registry = yaml.safe_load(source_payloads[registry_name])
    state = json.loads(source_payloads[state_name])
    if not isinstance(registry, Mapping) or not isinstance(state, Mapping):
        raise ValueError("native ASR comparability bindings are invalid")
    sources = _asr_comparability_sources(registry)
    rows: list[dict[str, object]] = []
    provenance_rows: list[dict[str, object]] = []
    for source in sources:
        source_rows, source_provenance = _computed_asr_comparability_rows(
            source, state=state
        )
        rows.extend(source_rows)
        provenance_rows.append(source_provenance)
    expected_rows = len(ASR_COMPARABILITY_CONFIGURATIONS) * (
        2 * len(ASR_COMPARABILITY_STRATA) + 1
    )
    if len(rows) != expected_rows:
        raise ValueError(f"ASR comparability row count differs: {len(rows)}")

    def overall(
        configuration_id: str, scoring_policy_id: str, metric_id: str = "wer"
    ) -> Mapping[str, object]:
        return next(
            row
            for row in rows
            if row["configuration_id"] == configuration_id
            and row["scoring_policy_id"] == scoring_policy_id
            and row["metric_id"] == metric_id
            and row["stratum"] == "OVERALL"
        )

    table = [
        "| Configuration | Split | Frozen WER | Punctuation-insensitive WER | WER gap | Reference punctuated-token rate | Hypothesis punctuated-token rate | Endpoint diagnostic `final_wer` | Endpoint/reference denominator ratio |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source in sources:
        configuration_id = str(source["configuration_id"])
        frozen = overall(configuration_id, "lowercase_whitespace.v1")
        comparable = overall(
            configuration_id,
            "evaluation-text-normalization-punctuation-insensitive.v1",
        )
        endpoint = overall(
            configuration_id,
            "endpoint_window_reference_mapping.v1",
            "final_wer",
        )
        denominator_ratio = float(endpoint["denominator"]) / float(
            frozen["denominator"]
        )
        table.append(
            f"| {configuration_id} | {source['evidence_split']} | "
            f"{float(frozen['value_percent']):.3f}% | "
            f"{float(comparable['value_percent']):.3f}% | "
            f"{float(comparable['punctuation_sensitive_minus_insensitive_wer_percentage_points']):.3f} pp | "
            f"{100.0 * float(comparable['reference_ascii_punctuation_token_rate']):.3f}% | "
            f"{100.0 * float(comparable['hypothesis_ascii_punctuation_token_rate']):.3f}% | "
            f"{float(endpoint['value_percent']):.3f}% | {denominator_ratio:.3f} |"
        )

    baseline_id = "H2_BASELINE_REFERENCE"
    stratum_table = [
        "| Development baseline stratum | Comparable WER | Errors | Reference words |",
        "|---|---:|---:|---:|",
    ]
    for stratum in ASR_COMPARABILITY_STRATA:
        row = next(
            value
            for value in rows
            if value["configuration_id"] == baseline_id
            and value["scoring_policy_id"]
            == "evaluation-text-normalization-punctuation-insensitive.v1"
            and value["stratum"] == stratum
        )
        display = (
            "UNDEFINED_EMPTY_STRATUM"
            if row["value_percent"] is None
            else f"{float(row['value_percent']):.3f}%"
        )
        stratum_table.append(
            f"| {stratum} | {display} | {float(row['numerator']):.0f} | "
            f"{float(row['denominator']):.0f} |"
        )

    provenance = {
        "schema_version": "h2-asr-wer-comparability-provenance.v2",
        "status": "VALID",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "configuration_registry_sha256": _sha256(source_payloads[registry_name]),
        "packaged_controller_state_sha256": _sha256(source_payloads[state_name]),
        "derivation_script_sha256": _sha256(Path(__file__).read_bytes()),
        "commonvoice_normalization_source": {
            "member": ASR_COMMONVOICE_POLICY_MEMBER,
            "source_logical_path": str(
                ASR_COMMONVOICE_POLICY_SOURCE.relative_to(TOOL_ROOT)
            ).replace("\\", "/"),
            "sha256": _sha256(commonvoice_policy_payload),
            "policy_id": normalization["policy_id"],
        },
        "neural_inference_rerun": False,
        "scientific_runtime_or_policy_changed": False,
        "post_run_rescore_used_for_development_selection": False,
        "post_run_rescore_used_for_heldout_policy_change": False,
        "development_and_heldout_evidence_pooled": False,
        "frozen_metric_preserved": True,
        "source_reported_frozen_metrics_recomputed_exactly": True,
        "endpoint_final_wer_declared_noncomparable_to_exported_transcript_wer": True,
        "punctuation_diagnostics": {
            "character_set": "ASCII string.punctuation",
            "tokenization": "lowercase_whitespace.v1",
            "reference_and_hypothesis_punctuation_token_rates_reported": True,
            "wer_gap_definition": (
                "punctuation-sensitive WER minus punctuation-insensitive WER "
                "over the same immutable hypotheses"
            ),
            "causal_error_attribution_claimed": False,
            "scientific_selection_eligible": False,
        },
        "scoring_policies": {
            "lowercase_whitespace.v1": {
                "lowercase": True,
                "collapse_whitespace": True,
                "remove_punctuation": False,
            },
            "evaluation-text-normalization-punctuation-insensitive.v1": {
                "lowercase": True,
                "collapse_whitespace": True,
                "remove_ascii_punctuation": True,
                "purpose": "cross-protocol diagnostic only",
            },
        },
        "direct_result_sources": provenance_rows,
        "row_count": len(rows),
    }
    guide = (
        "# H2 ASR WER comparability supplement\n\n"
        "The H2 model did not undergo a hidden ASR regression. The frozen H2 "
        "protocol intentionally preserves punctuation in reference tokens, while "
        "the Sherpa Giga decoder emits predominantly unpunctuated text. A token such "
        "as `tomorrow?` therefore differs from `tomorrow` under the frozen metric.\n\n"
        "This inference-free post-run supplement retains that frozen metric and "
        "adds a second score over the exact same saved hypotheses after applying "
        "the punctuation-insensitive normalization used by the earlier Common "
        "Voice ASR evaluation. The second score is an apples-to-apples diagnostic; "
        "it did not select a configuration, alter a threshold, inspect held-out "
        "data before freeze, or replace the native result. The table also reports "
        "the WER difference in percentage points and the share of whitespace "
        "tokens containing ASCII punctuation in the reference and hypothesis. "
        "Those rates describe punctuation emission/coverage; they are not a "
        "punctuation precision or causal error-attribution score.\n\n"
        "`final_wer` remains a separate endpoint-window diagnostic. A reference "
        "turn crossing an endpoint boundary is mapped in full to every intersecting "
        "endpoint window, so the same words may contribute to more than one "
        "denominator. It must not be presented as ordinary final-transcript WER. "
        "Likewise, cpWER and speaker-attributed WER include speaker-"
        "stream assignment and insertions and may legitimately exceed 100%; they "
        "are not plain ASR WER.\n\n"
        + "\n".join(table)
        + "\n\n## Development baseline by product complexity\n\n"
        + "\n".join(stratum_table)
        + "\n\nAll rows bind to validated result trees and exact checksums. Empty strata "
        "remain explicitly undefined rather than being converted to zero.\n"
    ).encode("utf-8")
    return (
        {
            REQUIRED_ASR_COMPARABILITY_MEMBERS[0]: _csv_payload(
                rows, ASR_COMPARABILITY_FIELDS
            ),
            REQUIRED_ASR_COMPARABILITY_MEMBERS[1]: guide,
            REQUIRED_ASR_COMPARABILITY_MEMBERS[2]: _canonical_json(provenance),
        },
        provenance,
    )


def _host_io_timestamp(value: object, *, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"host-I/O timestamp is absent: {label}")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"host-I/O timestamp is invalid: {label}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"host-I/O timestamp lacks an offset: {label}")
    return parsed.astimezone(timezone.utc)


def _host_io_number(value: object, *, label: str) -> float:
    number = _number(value)
    if number is None:
        raise ValueError(f"host-I/O numeric value is invalid: {label}")
    return number


def _host_io_count(value: object, *, label: str) -> int:
    try:
        count = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"host-I/O count is invalid: {label}") from error
    if count < 0:
        raise ValueError(f"host-I/O count is negative: {label}")
    return count


def _validate_host_io_receipt_contract(
    receipt: Mapping[str, object],
    source_payloads: Mapping[str, bytes],
) -> dict[str, object]:
    state_name = "controller/program_state.json"
    manifest_name = "protocol/job_manifest.json"
    if state_name not in source_payloads or manifest_name not in source_payloads:
        raise ValueError("host-I/O evidence lacks packaged controller/manifest binding")
    state = json.loads(source_payloads[state_name])
    manifest = json.loads(source_payloads[manifest_name])
    if not isinstance(state, Mapping) or not isinstance(manifest, Mapping):
        raise ValueError("host-I/O packaged controller/manifest is invalid")
    if (
        receipt.get("schema_version") != "h2-host-io-interference.v1"
        or receipt.get("status") != "HOST_STORAGE_IO_INTERFERENCE_CONFIRMED"
        or receipt.get("protocol_id") != state.get("protocol_id")
        or receipt.get("protocol_sha256") != state.get("protocol_sha256")
        or receipt.get("job_manifest_sha256") != state.get("job_manifest_sha256")
        or manifest.get("job_manifest_sha256") != state.get("job_manifest_sha256")
    ):
        raise ValueError("host-I/O protocol/controller binding differs")
    if tuple(map(str, receipt.get("candidate_job_ids") or ())) != (
        HOST_IO_CANDIDATE_JOB_IDS
    ):
        raise ValueError("host-I/O candidate membership/order differs")

    scientific = receipt.get("scientific_interpretation")
    promotion = receipt.get("promotion")
    provenance = receipt.get("provenance")
    correlation = receipt.get("correlation")
    windows = receipt.get("windows_evidence")
    if not all(
        isinstance(value, Mapping)
        for value in (scientific, promotion, provenance, correlation, windows)
    ):
        raise ValueError("host-I/O receipt sections are invalid")
    assert isinstance(scientific, Mapping)
    assert isinstance(promotion, Mapping)
    assert isinstance(provenance, Mapping)
    assert isinstance(correlation, Mapping)
    assert isinstance(windows, Mapping)
    if (
        scientific.get("accuracy_metrics_eligible") is not True
        or scientific.get("development_promotion_eligible") is not True
        or scientific.get("operational_wall_time_eligible") is not False
        or scientific.get("resource_comparison_eligible") is not False
        or scientific.get("total_rtf_entered_promotion") is not False
        or scientific.get("scientific_results_or_policies_modified") is not False
        or scientific.get("inference_rerun") is not False
        or scientific.get("queue_policy") != "block"
        or int(scientific.get("dropped_frames_total") or 0) != 0
    ):
        raise ValueError("host-I/O scientific eligibility boundary differs")
    if (
        tuple(map(str, promotion.get("selected_candidates") or ()))
        != HOST_IO_SELECTED_CONFIGURATIONS
        or promotion.get("evaluation_material_inspected") is not False
        or promotion.get("weighted_composite_used") is not False
        or "total_rtf" in set(map(str, promotion.get("common_metric_priority") or ()))
    ):
        raise ValueError("host-I/O development-promotion firewall differs")
    if (
        provenance.get("all_candidate_result_checksums_verified") is not True
        or provenance.get("identical_case_reference_hashes_verified") is not True
        or provenance.get("job_manifest_embedded_self_hash_matches_state") is not True
        or provenance.get("host_paths_sanitized") is not True
        or provenance.get("collector") != "scripts/capture_h2_host_io_interference.ps1"
    ):
        raise ValueError("host-I/O receipt provenance differs")

    candidate_rows = receipt.get("candidate_jobs")
    correlation_rows = correlation.get("per_job")
    manifest_jobs = manifest.get("jobs")
    state_jobs = state.get("jobs")
    if (
        not isinstance(candidate_rows, list)
        or not isinstance(correlation_rows, list)
        or not isinstance(manifest_jobs, list)
        or not isinstance(state_jobs, Mapping)
    ):
        raise ValueError("host-I/O job evidence is invalid")
    candidates = {
        str(row.get("job_id") or ""): row
        for row in candidate_rows
        if isinstance(row, Mapping)
    }
    correlations = {
        str(row.get("job_id") or ""): row
        for row in correlation_rows
        if isinstance(row, Mapping)
    }
    manifest_by_id = {
        str(row.get("job_id") or ""): row
        for row in manifest_jobs
        if isinstance(row, Mapping)
    }
    expected_ids = set(HOST_IO_CANDIDATE_JOB_IDS)
    if set(candidates) != expected_ids or set(correlations) != expected_ids:
        raise ValueError("host-I/O candidate/correlation rows differ")
    if any(
        job_id not in manifest_by_id or job_id not in state_jobs
        for job_id in expected_ids
    ):
        raise ValueError("host-I/O candidates are absent from frozen program evidence")

    esent_rows = windows.get("esent_events")
    vss_rows = windows.get("acronis_vss_events")
    guardian_rows = windows.get("storage_guardian_events")
    driver_rows = windows.get("storage_driver_warnings_or_errors")
    if not all(
        isinstance(value, list)
        for value in (esent_rows, vss_rows, guardian_rows, driver_rows)
    ):
        raise ValueError("host-I/O Windows event inventories are invalid")
    assert isinstance(esent_rows, list)
    assert isinstance(vss_rows, list)
    assert isinstance(guardian_rows, list)
    assert isinstance(driver_rows, list)
    completed_io = [
        row
        for row in esent_rows
        if isinstance(row, Mapping)
        and int(row.get("event_id") or 0) in {508, 510}
        and row.get("reported_io_seconds") is not None
    ]
    if not completed_io:
        raise ValueError("host-I/O receipt lacks completed hung-I/O evidence")
    maximum_os = max(
        _host_io_number(row.get("reported_io_seconds"), label="reported_io_seconds")
        for row in completed_io
    )
    if (
        _host_io_count(
            correlation.get("esent_hung_io_event_count"), label="ESENT event count"
        )
        != len(esent_rows)
        or _host_io_count(
            correlation.get("esent_completed_io_event_count"),
            label="completed ESENT I/O count",
        )
        != len(completed_io)
        or not math.isclose(
            _host_io_number(
                correlation.get("maximum_esent_reported_io_sec"),
                label="maximum_esent_reported_io_sec",
            ),
            maximum_os,
            abs_tol=1e-9,
        )
        or _host_io_count(
            correlation.get("acronis_vss_event_count"), label="Acronis VSS count"
        )
        != len(vss_rows)
        or _host_io_count(
            correlation.get("storage_driver_warning_or_error_count"),
            label="storage-driver event count",
        )
        != len(driver_rows)
        or _host_io_count(
            correlation.get("independent_storage_guardian_event_count"),
            label="storage-guardian event count",
        )
        != len(guardian_rows)
    ):
        raise ValueError("host-I/O aggregate Windows-event evidence differs")

    summary_rows: list[dict[str, object]] = []
    case_rows: list[dict[str, object]] = []
    reference_identities: set[str] = set()
    all_starts: list[datetime] = []
    all_ends: list[datetime] = []
    for job_id in HOST_IO_CANDIDATE_JOB_IDS:
        candidate = candidates[job_id]
        job_correlation = correlations[job_id]
        state_row = state_jobs[job_id]
        manifest_row = manifest_by_id[job_id]
        if not isinstance(state_row, Mapping) or not isinstance(manifest_row, Mapping):
            raise ValueError(f"host-I/O frozen job binding is invalid: {job_id}")
        checksum = candidate.get("checksum_validation")
        if not isinstance(checksum, Mapping):
            raise ValueError(f"host-I/O checksum evidence is absent: {job_id}")
        declared = int(checksum.get("declared_entry_count") or 0)
        verified = int(checksum.get("verified_entry_count") or 0)
        if (
            checksum.get("status") != "VALID"
            or declared <= 0
            or verified != declared
            or checksum.get("failures") not in ([], ())
            or int(candidate.get("dropped_frames") or 0) != 0
            or state_row.get("state") != "COMPLETE"
            or state_row.get("result_sha256") != candidate.get("result_sha256")
            or manifest_row.get("development_only") is not True
            or manifest_row.get("split") != "development"
            or len(str(candidate.get("result_sha256") or "")) != 64
            or not str(candidate.get("result_path") or "").startswith("%RESULTS_ROOT%")
        ):
            raise ValueError(f"host-I/O candidate result binding differs: {job_id}")
        references = checksum.get("reference_hashes")
        if not isinstance(references, Mapping) or len(references) != 4:
            raise ValueError(f"host-I/O reference identity is absent: {job_id}")
        reference_identities.add(
            json.dumps(references, sort_keys=True, separators=(",", ":"))
        )

        start = _host_io_timestamp(
            candidate.get("started_at_utc"), label=f"{job_id}.start"
        )
        end = _host_io_timestamp(
            candidate.get("completed_at_utc"), label=f"{job_id}.end"
        )
        if end <= start:
            raise ValueError(f"host-I/O candidate interval is invalid: {job_id}")
        all_starts.append(start)
        all_ends.append(end)
        job_esent = [
            row
            for row in esent_rows
            if isinstance(row, Mapping)
            and start
            <= _host_io_timestamp(row.get("time_created_utc"), label="ESENT event")
            <= end
        ]
        job_completed = [
            row
            for row in job_esent
            if int(row.get("event_id") or 0) in {508, 510}
            and row.get("reported_io_seconds") is not None
        ]
        maximum_event = max(
            job_completed,
            key=lambda row: _host_io_number(
                row.get("reported_io_seconds"), label=f"{job_id}.ESENT duration"
            ),
            default=None,
        )
        maximum_job_os = (
            _host_io_number(
                maximum_event.get("reported_io_seconds"),
                label=f"{job_id}.maximum ESENT duration",
            )
            if isinstance(maximum_event, Mapping)
            else None
        )
        job_vss = [
            row
            for row in vss_rows
            if isinstance(row, Mapping)
            and start
            <= _host_io_timestamp(row.get("time_created_utc"), label="VSS event")
            <= end
        ]
        job_guardian = [
            row
            for row in guardian_rows
            if isinstance(row, Mapping)
            and start
            <= _host_io_timestamp(row.get("at_utc"), label="guardian event")
            <= end
        ]
        blocked_max = _host_io_number(
            candidate.get("blocked_max_sec"), label=f"{job_id}.blocked_max_sec"
        )
        expected_delta = (
            abs(maximum_job_os - blocked_max) if maximum_job_os is not None else None
        )
        if (
            _host_io_count(
                job_correlation.get("esent_event_count"),
                label=f"{job_id}.ESENT event count",
            )
            != len(job_esent)
            or _host_io_count(
                job_correlation.get("completed_io_event_count"),
                label=f"{job_id}.completed ESENT I/O count",
            )
            != len(job_completed)
            or _host_io_count(
                job_correlation.get("acronis_vss_event_count"),
                label=f"{job_id}.Acronis VSS count",
            )
            != len(job_vss)
            or _host_io_count(
                job_correlation.get("independent_storage_guardian_event_count"),
                label=f"{job_id}.storage-guardian event count",
            )
            != len(job_guardian)
            or (
                maximum_job_os is not None
                and not math.isclose(
                    _host_io_number(
                        job_correlation.get("maximum_esent_reported_io_sec"),
                        label=f"{job_id}.correlated maximum ESENT duration",
                    ),
                    maximum_job_os,
                    abs_tol=1e-9,
                )
            )
            or (
                isinstance(maximum_event, Mapping)
                and _host_io_timestamp(
                    job_correlation.get("maximum_esent_event_utc"),
                    label=f"{job_id}.correlated maximum ESENT timestamp",
                )
                != _host_io_timestamp(
                    maximum_event.get("time_created_utc"),
                    label=f"{job_id}.maximum ESENT timestamp",
                )
            )
            or not math.isclose(
                _host_io_number(
                    job_correlation.get("maximum_pipeline_blocked_put_sec"),
                    label=f"{job_id}.correlated queue maximum",
                ),
                blocked_max,
                abs_tol=1e-9,
            )
            or expected_delta is None
            or not math.isclose(
                _host_io_number(
                    job_correlation.get("absolute_maximum_difference_sec"),
                    label=f"{job_id}.maximum-duration difference",
                ),
                expected_delta,
                abs_tol=1e-9,
            )
        ):
            raise ValueError(
                f"host-I/O per-job timestamp correlation differs: {job_id}"
            )

        summary_rows.append(
            {
                "schema_version": "h2-queue-backpressure-summary-row.v1",
                "job_id": job_id,
                "started_at_utc": str(candidate.get("started_at_utc") or ""),
                "completed_at_utc": str(candidate.get("completed_at_utc") or ""),
                "completed_cases": int(candidate.get("completed_cases") or 0),
                "completed_audio_sec": candidate.get("completed_audio_sec"),
                "wall_elapsed_sec": candidate.get("wall_elapsed_sec"),
                "wall_rtf": candidate.get("wall_rtf"),
                "event_count": int(candidate.get("event_count") or 0),
                "blocked_total_sec": candidate.get("blocked_total_sec"),
                "blocked_max_sec": candidate.get("blocked_max_sec"),
                "cases_with_blocked_max_gt_10_sec": int(
                    candidate.get("cases_with_blocked_max_gt_10_sec") or 0
                ),
                "cases_with_blocked_max_gt_60_sec": int(
                    candidate.get("cases_with_blocked_max_gt_60_sec") or 0
                ),
                "dropped_frames": int(candidate.get("dropped_frames") or 0),
                "esent_event_count": len(job_esent),
                "esent_completed_io_event_count": len(job_completed),
                "maximum_esent_reported_io_sec": maximum_job_os,
                "maximum_esent_event_utc": (
                    maximum_event.get("time_created_utc")
                    if isinstance(maximum_event, Mapping)
                    else None
                ),
                "maximum_duration_absolute_delta_sec": expected_delta,
                "acronis_vss_event_count": len(job_vss),
                "independent_storage_guardian_event_count": len(job_guardian),
                "result_sha256": candidate.get("result_sha256"),
                "declared_checksum_count": declared,
                "verified_checksum_count": verified,
                "accuracy_metrics_eligible": True,
                "resource_comparison_eligible": False,
            }
        )
        largest = candidate.get("largest_queue_stalls")
        if not isinstance(largest, list) or not largest:
            raise ValueError(f"host-I/O top-case evidence is absent: {job_id}")
        for rank, row in enumerate(largest, start=1):
            if not isinstance(row, Mapping) or not str(row.get("case_id") or ""):
                raise ValueError(f"host-I/O top-case row is invalid: {job_id}")
            case_rows.append(
                {
                    "schema_version": "h2-queue-backpressure-case-row.v1",
                    "job_id": job_id,
                    "stall_rank_within_job": rank,
                    "case_id": row.get("case_id"),
                    "audio_duration_sec": row.get("audio_duration_sec"),
                    "event_count": int(row.get("event_count") or 0),
                    "blocked_total_sec": row.get("blocked_total_sec"),
                    "blocked_max_sec": row.get("blocked_max_sec"),
                    "dropped_frames": int(row.get("dropped_frames") or 0),
                    "result_sha256": candidate.get("result_sha256"),
                    "resource_comparison_eligible": False,
                }
            )

    if len(reference_identities) != 1:
        raise ValueError("host-I/O candidate reference identities differ")
    window = receipt.get("evidence_window")
    if (
        not isinstance(window, Mapping)
        or _host_io_timestamp(window.get("start_utc"), label="evidence start")
        != min(all_starts)
        or _host_io_timestamp(window.get("end_utc"), label="evidence end")
        != max(all_ends)
    ):
        raise ValueError("host-I/O evidence window differs")
    maximum_pipeline = max(
        _host_io_number(row["blocked_max_sec"], label="candidate maximum queue block")
        for row in candidates.values()
    )
    if not math.isclose(
        _host_io_number(
            correlation.get("maximum_pipeline_blocked_put_sec"),
            label="overall maximum pipeline block",
        ),
        maximum_pipeline,
        abs_tol=1e-9,
    ):
        raise ValueError("host-I/O overall queue maximum differs")
    closest = min(
        correlations.values(),
        key=lambda row: _host_io_number(
            row.get("absolute_maximum_difference_sec"), label="closest pair"
        ),
    )
    declared_closest = correlation.get("closest_maximum_duration_pair")
    if (
        not isinstance(declared_closest, Mapping)
        or declared_closest.get("job_id") != closest.get("job_id")
        or not math.isclose(
            _host_io_number(
                declared_closest.get("absolute_maximum_difference_sec"),
                label="declared closest pair",
            ),
            _host_io_number(
                closest.get("absolute_maximum_difference_sec"),
                label="computed closest pair",
            ),
            abs_tol=1e-9,
        )
    ):
        raise ValueError("host-I/O closest-duration pair differs")
    return {
        "summary_rows": summary_rows,
        "case_rows": case_rows,
        "closest_pair": dict(declared_closest),
        "maximum_os_io_sec": maximum_os,
        "maximum_pipeline_queue_block_sec": maximum_pipeline,
        "esent_event_count": len(esent_rows),
        "completed_io_event_count": len(completed_io),
        "candidate_checksum_count": sum(
            int(row["declared_checksum_count"]) for row in summary_rows
        ),
    }


def _render_host_io_supplement(
    receipt: Mapping[str, object], source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    validated = _validate_host_io_receipt_contract(receipt, source_payloads)
    summary_rows = validated["summary_rows"]
    case_rows = validated["case_rows"]
    assert isinstance(summary_rows, list)
    assert isinstance(case_rows, list)
    closest = validated["closest_pair"]
    assert isinstance(closest, Mapping)
    guide = (
        "# H2 queue/backpressure and Windows host-I/O evidence\n\n"
        "The four Phase-1 medium development runs produced checksum-valid accuracy "
        "outputs with zero dropped frames. Their accuracy metrics and the development "
        "promotion remain eligible. Their wall time, wall-derived RTF, and queue-blocking "
        "measurements are not eligible for resource comparison because Windows recorded "
        f"{validated['esent_event_count']} contemporaneous ESENT hung-I/O events.\n\n"
        f"The closest independent duration match is `{closest.get('job_id')}`: the "
        f"pipeline recorded {float(closest.get('maximum_pipeline_blocked_put_sec')):.3f} "
        f"seconds of maximum blocked queue time and Windows reported "
        f"{float(closest.get('maximum_esent_reported_io_sec')):.3f} seconds for a completed "
        f"OS I/O request, an absolute difference of "
        f"{float(closest.get('absolute_maximum_difference_sec')):.3f} seconds. This is "
        "independent evidence of host-wide storage interference, not proof that Acronis "
        "or any single process was the sole cause.\n\n"
        "Use the later standardized serial resource jobs for final RTF/RAM comparisons. "
        "If a serial resource interval overlaps the same Windows condition, replay that "
        "resource job cleanly; do not rerun or invalidate the checksum-valid accuracy "
        "outputs. The CSVs retain all four job summaries and each job's largest per-case "
        "queue stalls.\n"
    ).encode("utf-8")
    generated = {
        HOST_IO_SUMMARY_MEMBER: _csv_payload(summary_rows, HOST_IO_SUMMARY_FIELDS),
        HOST_IO_CASES_MEMBER: _csv_payload(case_rows, HOST_IO_CASE_FIELDS),
        HOST_IO_GUIDE_MEMBER: guide,
    }
    return generated, validated


def _host_io_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    receipt_path = (
        workspace / "diagnostics/host_io_interference/windows_host_io_interference.json"
    )
    collector_path = TOOL_ROOT / "scripts/capture_h2_host_io_interference.ps1"
    readme_path = TOOL_ROOT / "scripts/H2_HOST_IO_INTERFERENCE_README.md"
    for path in (receipt_path, collector_path, readme_path):
        if not path.is_file():
            raise ValueError(f"host-I/O reproducibility source is absent: {path}")
    receipt_payload = receipt_path.read_bytes()
    collector_payload = collector_path.read_bytes()
    readme_payload = readme_path.read_bytes()
    if b"C:\\\\Users\\\\" in receipt_payload or b"just-peachy" in receipt_payload:
        raise ValueError("host-I/O receipt contains an unsanitized host path")
    receipt = json.loads(receipt_payload)
    if not isinstance(receipt, Mapping):
        raise ValueError("host-I/O receipt is not a JSON object")
    generated, validated = _render_host_io_supplement(receipt, source_payloads)
    receipt_provenance = receipt.get("provenance")
    if not isinstance(receipt_provenance, Mapping) or receipt_provenance.get(
        "collector_sha256"
    ) != _sha256(collector_payload):
        raise ValueError("host-I/O collector checksum differs from its receipt")
    output = {
        HOST_IO_RECEIPT_MEMBER: receipt_payload,
        HOST_IO_COLLECTOR_MEMBER: collector_payload,
        HOST_IO_README_MEMBER: readme_payload,
        **generated,
    }
    member_rows = [
        {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
        for name, payload in sorted(output.items())
    ]
    provenance = {
        "schema_version": "h2-host-io-package-provenance.v1",
        "status": "VALID",
        "protocol_id": receipt.get("protocol_id"),
        "protocol_sha256": receipt.get("protocol_sha256"),
        "job_manifest_sha256": receipt.get("job_manifest_sha256"),
        "receipt_sha256": _sha256(receipt_payload),
        "collector_sha256": _sha256(collector_payload),
        "readme_sha256": _sha256(readme_payload),
        "candidate_job_ids": list(HOST_IO_CANDIDATE_JOB_IDS),
        "selected_configurations_unchanged": list(HOST_IO_SELECTED_CONFIGURATIONS),
        "candidate_checksum_count": validated["candidate_checksum_count"],
        "all_candidate_result_checksums_verified": True,
        "identical_case_reference_hashes_verified": True,
        "dropped_frames_total": 0,
        "accuracy_metrics_eligible": True,
        "development_promotion_eligible": True,
        "operational_wall_time_eligible": False,
        "resource_comparison_eligible": False,
        "development_only": True,
        "evaluation_material_inspected": False,
        "scientific_runtime_policy_or_selection_changed": False,
        "inference_rerun": False,
        "causal_attribution_is_not_sole_cause_claim": True,
        "member_count_excluding_provenance": len(member_rows),
        "members": member_rows,
    }
    output[HOST_IO_PROVENANCE_MEMBER] = _canonical_json(provenance)
    return output, provenance


def _validate_host_io_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_HOST_IO_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks host-I/O reproducibility evidence: "
            + ", ".join(missing)
        )
    receipt_payload = payloads[HOST_IO_RECEIPT_MEMBER]
    if b"C:\\\\Users\\\\" in receipt_payload or b"just-peachy" in receipt_payload:
        raise ValueError("packaged host-I/O receipt contains an unsanitized host path")
    receipt = json.loads(receipt_payload)
    provenance = json.loads(payloads[HOST_IO_PROVENANCE_MEMBER])
    if not isinstance(receipt, Mapping) or not isinstance(provenance, Mapping):
        raise ValueError("packaged host-I/O JSON evidence is invalid")
    expected_generated, validated = _render_host_io_supplement(receipt, payloads)
    if any(payloads.get(name) != value for name, value in expected_generated.items()):
        raise ValueError("packaged host-I/O summary rendering differs")
    receipt_provenance = receipt.get("provenance")
    if not isinstance(receipt_provenance, Mapping) or receipt_provenance.get(
        "collector_sha256"
    ) != _sha256(payloads[HOST_IO_COLLECTOR_MEMBER]):
        raise ValueError("packaged host-I/O collector identity differs")
    member_rows = provenance.get("members")
    if not isinstance(member_rows, list):
        raise ValueError("packaged host-I/O member inventory is invalid")
    expected_members = set(REQUIRED_HOST_IO_MEMBERS) - {HOST_IO_PROVENANCE_MEMBER}
    by_member = {
        str(row.get("member") or ""): row
        for row in member_rows
        if isinstance(row, Mapping)
    }
    if set(by_member) != expected_members:
        raise ValueError("packaged host-I/O member inventory differs")
    if any(
        row.get("sha256") != _sha256(payloads[name])
        or row.get("bytes") != len(payloads[name])
        for name, row in by_member.items()
    ):
        raise ValueError("packaged host-I/O member checksum differs")
    if (
        provenance.get("schema_version") != "h2-host-io-package-provenance.v1"
        or provenance.get("status") != "VALID"
        or provenance.get("receipt_sha256") != _sha256(receipt_payload)
        or provenance.get("collector_sha256")
        != _sha256(payloads[HOST_IO_COLLECTOR_MEMBER])
        or provenance.get("readme_sha256") != _sha256(payloads[HOST_IO_README_MEMBER])
        or tuple(map(str, provenance.get("candidate_job_ids") or ()))
        != HOST_IO_CANDIDATE_JOB_IDS
        or tuple(map(str, provenance.get("selected_configurations_unchanged") or ()))
        != HOST_IO_SELECTED_CONFIGURATIONS
        or provenance.get("candidate_checksum_count")
        != validated["candidate_checksum_count"]
        or provenance.get("all_candidate_result_checksums_verified") is not True
        or provenance.get("identical_case_reference_hashes_verified") is not True
        or provenance.get("dropped_frames_total") != 0
        or provenance.get("accuracy_metrics_eligible") is not True
        or provenance.get("development_promotion_eligible") is not True
        or provenance.get("operational_wall_time_eligible") is not False
        or provenance.get("resource_comparison_eligible") is not False
        or provenance.get("development_only") is not True
        or provenance.get("evaluation_material_inspected") is not False
        or provenance.get("scientific_runtime_policy_or_selection_changed") is not False
        or provenance.get("inference_rerun") is not False
        or provenance.get("causal_attribution_is_not_sole_cause_claim") is not True
        or provenance.get("member_count_excluding_provenance") != len(member_rows)
    ):
        raise ValueError("packaged host-I/O provenance/firewall differs")
    return dict(provenance)


def _serial_host_io_manifest_rows(
    manifest: Mapping[str, object], group: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("serial host-I/O job manifest lacks jobs")
    phase_index = int(group["phase_index"])
    job_kind = str(group["job_kind"])
    expected_ids = tuple(map(str, group["job_ids"]))
    rows = tuple(
        dict(row)
        for row in jobs
        if isinstance(row, Mapping)
        and int(row.get("phase_index") or -1) == phase_index
        and row.get("job_kind") == job_kind
        and row.get("serial") is True
    )
    if tuple(str(row.get("job_id") or "") for row in rows) != expected_ids:
        raise ValueError(
            f"serial host-I/O frozen membership differs: {group['group_id']}"
        )
    return rows


def _validate_serial_host_io_receipt_contract(
    receipt: Mapping[str, object],
    source_payloads: Mapping[str, bytes],
    group: Mapping[str, object],
) -> dict[str, object]:
    state_name = "controller/program_state.json"
    manifest_name = "protocol/job_manifest.json"
    if state_name not in source_payloads or manifest_name not in source_payloads:
        raise ValueError(
            "serial host-I/O evidence lacks packaged controller/manifest binding"
        )
    state = json.loads(source_payloads[state_name])
    manifest = json.loads(source_payloads[manifest_name])
    if not isinstance(state, Mapping) or not isinstance(manifest, Mapping):
        raise ValueError("serial host-I/O controller/manifest is invalid")
    if (
        receipt.get("schema_version") != "h2-host-io-interference.v1"
        or receipt.get("evidence_class") != "SerialResource"
        or receipt.get("protocol_id") != state.get("protocol_id")
        or receipt.get("protocol_sha256") != state.get("protocol_sha256")
        or receipt.get("job_manifest_sha256") != state.get("job_manifest_sha256")
        or manifest.get("job_manifest_sha256") != state.get("job_manifest_sha256")
    ):
        raise ValueError("serial host-I/O protocol/controller binding differs")

    status = str(receipt.get("status") or "")
    if status != "SERIAL_RESOURCE_HOST_IO_CLEAR":
        raise ValueError(
            "serial resource host-I/O evidence is not clear; replay or recapture "
            f"is required before final resource comparison: {group['group_id']} "
            f"({status or 'missing status'})"
        )
    expected_ids = tuple(map(str, group["job_ids"]))
    if tuple(map(str, receipt.get("candidate_job_ids") or ())) != expected_ids:
        raise ValueError(
            f"serial host-I/O candidate membership differs: {group['group_id']}"
        )

    manifest_rows = _serial_host_io_manifest_rows(manifest, group)
    manifest_by_id = {str(row.get("job_id") or ""): row for row in manifest_rows}
    state_jobs = state.get("jobs")
    candidate_rows = receipt.get("candidate_jobs")
    windows = receipt.get("windows_evidence")
    correlation = receipt.get("correlation")
    scientific = receipt.get("scientific_interpretation")
    provenance = receipt.get("provenance")
    if (
        not isinstance(state_jobs, Mapping)
        or not isinstance(candidate_rows, list)
        or not isinstance(windows, Mapping)
        or not isinstance(correlation, Mapping)
        or not isinstance(scientific, Mapping)
        or not isinstance(provenance, Mapping)
    ):
        raise ValueError("serial host-I/O receipt sections are invalid")
    if receipt.get("promotion") is not None:
        raise ValueError("serial host-I/O receipt unexpectedly contains promotion data")
    if (
        scientific.get("accuracy_metrics_eligible") is not True
        or scientific.get("development_promotion_eligible") is not False
        or scientific.get("operational_wall_time_eligible") is not True
        or scientific.get("resource_comparison_eligible") is not True
        or scientific.get("total_rtf_entered_promotion") is not False
        or scientific.get("scientific_results_or_policies_modified") is not False
        or scientific.get("inference_rerun") is not False
        or scientific.get("queue_policy") != "block"
        or scientific.get("host_io_interference_detected") is not False
        or scientific.get("host_io_evidence_complete") is not True
        or _host_io_count(
            scientific.get("dropped_frames_total"),
            label="serial dropped-frames total",
        )
        != 0
    ):
        raise ValueError("serial host-I/O scientific eligibility boundary differs")
    if (
        provenance.get("collector") != "scripts/capture_h2_host_io_interference.ps1"
        or provenance.get("evidence_class") != "SerialResource"
        or provenance.get("all_candidate_result_checksums_verified") is not True
        or provenance.get("identical_case_reference_hashes_verified") is not True
        or provenance.get("nonidentical_references_explicitly_allowed") is not False
        or provenance.get("job_manifest_embedded_self_hash_matches_state") is not True
        or provenance.get("host_paths_sanitized") is not True
        or len(str(provenance.get("collector_sha256") or "")) != 64
        or len(str(provenance.get("program_state_sha256_at_capture") or "")) != 64
        or len(str(provenance.get("job_manifest_file_sha256") or "")) != 64
    ):
        raise ValueError("serial host-I/O provenance differs")

    esent_rows = windows.get("esent_events")
    vss_rows = windows.get("acronis_vss_events")
    driver_rows = windows.get("storage_driver_warnings_or_errors")
    query_failures = windows.get("storage_provider_query_failures")
    guardian_rows = windows.get("storage_guardian_events")
    if not all(
        isinstance(value, list)
        for value in (
            esent_rows,
            vss_rows,
            driver_rows,
            query_failures,
            guardian_rows,
        )
    ):
        raise ValueError("serial host-I/O Windows event inventories are invalid")
    assert isinstance(esent_rows, list)
    assert isinstance(vss_rows, list)
    assert isinstance(driver_rows, list)
    assert isinstance(query_failures, list)
    assert isinstance(guardian_rows, list)
    if esent_rows or driver_rows or query_failures:
        raise ValueError(
            "serial host-I/O clear receipt contains adverse/incomplete evidence"
        )

    candidates = {
        str(row.get("job_id") or ""): row
        for row in candidate_rows
        if isinstance(row, Mapping)
    }
    correlation_rows = correlation.get("per_job")
    if not isinstance(correlation_rows, list):
        raise ValueError("serial host-I/O per-job correlation inventory is invalid")
    correlations = {
        str(row.get("job_id") or ""): row
        for row in correlation_rows
        if isinstance(row, Mapping)
    }
    if set(candidates) != set(expected_ids) or set(correlations) != set(expected_ids):
        raise ValueError("serial host-I/O candidate/correlation rows differ")

    summary_rows: list[dict[str, object]] = []
    reference_identities: set[str] = set()
    starts: list[datetime] = []
    ends: list[datetime] = []
    maximum_queue_block = 0.0
    checksum_count = 0
    for job_id in expected_ids:
        candidate = candidates[job_id]
        job_correlation = correlations[job_id]
        manifest_row = manifest_by_id[job_id]
        state_row = state_jobs.get(job_id)
        if not isinstance(state_row, Mapping):
            raise ValueError(f"serial host-I/O state row is invalid: {job_id}")
        checksum = candidate.get("checksum_validation")
        if not isinstance(checksum, Mapping):
            raise ValueError(f"serial host-I/O checksum evidence is absent: {job_id}")
        declared = _host_io_count(
            checksum.get("declared_entry_count"), label=f"{job_id}.declared checksums"
        )
        verified = _host_io_count(
            checksum.get("verified_entry_count"), label=f"{job_id}.verified checksums"
        )
        if (
            checksum.get("status") != "VALID"
            or declared <= 0
            or verified != declared
            or checksum.get("failures") not in ([], ())
            or len(str(checksum.get("checksums_sha256") or "")) != 64
            or state_row.get("state") != "COMPLETE"
            or state_row.get("result_sha256") != candidate.get("result_sha256")
            or len(str(candidate.get("result_sha256") or "")) != 64
            or not str(candidate.get("result_path") or "").startswith("%RESULTS_ROOT%")
            or candidate.get("phase_index") != group["phase_index"]
            or candidate.get("job_kind") != group["job_kind"]
            or candidate.get("measurement_mode") != "resources"
            or candidate.get("serial_execution") is not True
            or manifest_row.get("serial") is not True
            or manifest_row.get("split") != "development"
            or manifest_row.get("development_only") is not True
            or int(manifest_row.get("phase_index") or -1) != group["phase_index"]
            or manifest_row.get("job_kind") != group["job_kind"]
            or _host_io_count(candidate.get("dropped_frames"), label="dropped") != 0
        ):
            raise ValueError(f"serial host-I/O candidate binding differs: {job_id}")
        references = checksum.get("reference_hashes")
        if not isinstance(references, Mapping) or not references:
            raise ValueError(f"serial host-I/O reference identity is absent: {job_id}")
        reference_identities.add(
            json.dumps(references, sort_keys=True, separators=(",", ":"))
        )

        start = _host_io_timestamp(candidate.get("started_at_utc"), label="start")
        end = _host_io_timestamp(candidate.get("completed_at_utc"), label="end")
        if (
            end <= start
            or start
            != _host_io_timestamp(state_row.get("started_at_utc"), label="state start")
            or end
            != _host_io_timestamp(
                state_row.get("completed_at_utc"), label="state completion"
            )
        ):
            raise ValueError(f"serial host-I/O candidate interval differs: {job_id}")
        wall_sec = (end - start).total_seconds()
        candidate_wall = _host_io_number(
            candidate.get("wall_elapsed_sec"), label=f"{job_id}.wall"
        )
        audio_sec = _host_io_number(
            candidate.get("completed_audio_sec"), label=f"{job_id}.audio"
        )
        if (
            not math.isclose(candidate_wall, wall_sec, abs_tol=1e-6)
            or not math.isclose(
                audio_sec,
                _host_io_number(
                    state_row.get("completed_audio_sec"), label=f"{job_id}.state audio"
                ),
                abs_tol=1e-6,
            )
            or candidate.get("completed_cases") != state_row.get("completed_cases")
        ):
            raise ValueError(f"serial host-I/O candidate duration differs: {job_id}")
        expected_rtf = wall_sec / audio_sec if audio_sec > 0.0 else None
        actual_rtf = _number(candidate.get("wall_rtf"))
        if (
            expected_rtf is None
            or actual_rtf is None
            or not math.isclose(actual_rtf, expected_rtf, abs_tol=1e-9)
        ):
            raise ValueError(f"serial host-I/O wall RTF differs: {job_id}")

        job_vss = [
            row
            for row in vss_rows
            if isinstance(row, Mapping)
            and start
            <= _host_io_timestamp(row.get("time_created_utc"), label="VSS event")
            <= end
        ]
        job_guardian = [
            row
            for row in guardian_rows
            if isinstance(row, Mapping)
            and start
            <= _host_io_timestamp(row.get("at_utc"), label="guardian event")
            <= end
        ]
        blocked_max = _host_io_number(
            candidate.get("blocked_max_sec"), label=f"{job_id}.maximum queue block"
        )
        maximum_queue_block = max(maximum_queue_block, blocked_max)
        if (
            _host_io_count(job_correlation.get("esent_event_count"), label="ESENT") != 0
            or _host_io_count(
                job_correlation.get("completed_io_event_count"), label="completed I/O"
            )
            != 0
            or job_correlation.get("maximum_esent_reported_io_sec") is not None
            or job_correlation.get("maximum_esent_event_utc") is not None
            or job_correlation.get("absolute_maximum_difference_sec") is not None
            or not math.isclose(
                _host_io_number(
                    job_correlation.get("maximum_pipeline_blocked_put_sec"),
                    label="maximum queue correlation",
                ),
                blocked_max,
                abs_tol=1e-9,
            )
            or _host_io_count(
                job_correlation.get("acronis_vss_event_count"), label="VSS count"
            )
            != len(job_vss)
            or _host_io_count(
                job_correlation.get("independent_storage_guardian_event_count"),
                label="guardian count",
            )
            != len(job_guardian)
        ):
            raise ValueError(
                f"serial host-I/O per-job timestamp correlation differs: {job_id}"
            )
        starts.append(start)
        ends.append(end)
        checksum_count += declared
        summary_rows.append(
            {
                "schema_version": "h2-serial-resource-host-io-summary.v1",
                "group_id": group["group_id"],
                "phase_index": group["phase_index"],
                "job_kind": group["job_kind"],
                "job_id": job_id,
                "configuration_id": manifest_row.get("configuration_id"),
                "mode": manifest_row.get("mode"),
                "started_at_utc": candidate.get("started_at_utc"),
                "completed_at_utc": candidate.get("completed_at_utc"),
                "completed_cases": candidate.get("completed_cases"),
                "completed_audio_sec": candidate.get("completed_audio_sec"),
                "wall_elapsed_sec": candidate.get("wall_elapsed_sec"),
                "wall_rtf": candidate.get("wall_rtf"),
                "blocked_total_sec": candidate.get("blocked_total_sec"),
                "blocked_max_sec": candidate.get("blocked_max_sec"),
                "dropped_frames": candidate.get("dropped_frames"),
                "esent_event_count": 0,
                "storage_driver_warning_or_error_count": 0,
                "result_sha256": candidate.get("result_sha256"),
                "declared_checksum_count": declared,
                "verified_checksum_count": verified,
                "resource_comparison_eligible": True,
            }
        )

    if len(reference_identities) != 1:
        raise ValueError("serial host-I/O matched reference identities differ")
    evidence_window = receipt.get("evidence_window")
    if (
        not isinstance(evidence_window, Mapping)
        or _host_io_timestamp(evidence_window.get("start_utc"), label="window start")
        != min(starts)
        or _host_io_timestamp(evidence_window.get("end_utc"), label="window end")
        != max(ends)
    ):
        raise ValueError("serial host-I/O evidence window differs")
    if (
        _host_io_count(
            correlation.get("esent_hung_io_event_count"), label="aggregate ESENT"
        )
        != 0
        or _host_io_count(
            correlation.get("esent_completed_io_event_count"),
            label="aggregate completed I/O",
        )
        != 0
        or not math.isclose(
            _host_io_number(
                correlation.get("maximum_esent_reported_io_sec"),
                label="aggregate maximum ESENT",
            ),
            0.0,
            abs_tol=1e-9,
        )
        or not math.isclose(
            _host_io_number(
                correlation.get("maximum_pipeline_blocked_put_sec"),
                label="aggregate maximum queue block",
            ),
            maximum_queue_block,
            abs_tol=1e-9,
        )
        or not math.isclose(
            _host_io_number(
                correlation.get("absolute_maximum_difference_sec"),
                label="aggregate absolute difference",
            ),
            maximum_queue_block,
            abs_tol=1e-9,
        )
        or _host_io_count(
            correlation.get("acronis_vss_event_count"), label="aggregate VSS"
        )
        != len(vss_rows)
        or _host_io_count(
            correlation.get("storage_driver_warning_or_error_count"),
            label="aggregate storage warnings",
        )
        != 0
        or _host_io_count(
            correlation.get("independent_storage_guardian_event_count"),
            label="aggregate guardian events",
        )
        != len(guardian_rows)
        or correlation.get("closest_maximum_duration_pair") is not None
    ):
        raise ValueError("serial host-I/O aggregate correlation differs")
    return {
        "group_id": group["group_id"],
        "summary_rows": summary_rows,
        "candidate_checksum_count": checksum_count,
        "receipt_status": status,
    }


def _validate_phase2_ineligible_original_receipt(
    receipt: Mapping[str, object],
    state: Mapping[str, object],
    manifest: Mapping[str, object],
    group: Mapping[str, object],
    *,
    collector_sha256: str,
) -> None:
    """Validate the preserved non-ranking receipt without treating it as clear."""

    status = str(receipt.get("status") or "")
    expected_ids = tuple(map(str, group["job_ids"]))
    scientific = receipt.get("scientific_interpretation")
    provenance = receipt.get("provenance")
    state_jobs = state.get("jobs")
    candidates = receipt.get("candidate_jobs")
    if (
        receipt.get("schema_version") != "h2-host-io-interference.v1"
        or receipt.get("evidence_class") != "SerialResource"
        or status
        not in {
            "SERIAL_RESOURCE_HOST_IO_CONTAMINATED",
            "SERIAL_RESOURCE_HOST_IO_UNVERIFIED",
        }
        or receipt.get("protocol_id") != state.get("protocol_id")
        or receipt.get("protocol_sha256") != state.get("protocol_sha256")
        or receipt.get("job_manifest_sha256") != state.get("job_manifest_sha256")
        or manifest.get("job_manifest_sha256") != state.get("job_manifest_sha256")
        or tuple(map(str, receipt.get("candidate_job_ids") or ())) != expected_ids
        or receipt.get("promotion") is not None
        or not isinstance(scientific, Mapping)
        or scientific.get("resource_comparison_eligible") is not False
        or scientific.get("development_promotion_eligible") is not False
        or scientific.get("total_rtf_entered_promotion") is not False
        or scientific.get("scientific_results_or_policies_modified") is not False
        or scientific.get("inference_rerun") is not False
        or not isinstance(provenance, Mapping)
        or provenance.get("collector_sha256") != collector_sha256
        or provenance.get("all_candidate_result_checksums_verified") is not True
        or provenance.get("host_paths_sanitized") is not True
        or not isinstance(state_jobs, Mapping)
        or not isinstance(candidates, list)
    ):
        raise ValueError("original Phase-2 ineligible receipt binding differs")
    _serial_host_io_manifest_rows(manifest, group)
    by_id = {
        str(row.get("job_id") or ""): row
        for row in candidates
        if isinstance(row, Mapping)
    }
    if set(by_id) != set(expected_ids):
        raise ValueError("original Phase-2 ineligible receipt membership differs")
    for job_id in expected_ids:
        candidate = by_id[job_id]
        state_row = state_jobs.get(job_id)
        checksum = candidate.get("checksum_validation")
        if (
            not isinstance(state_row, Mapping)
            or state_row.get("state") != "COMPLETE"
            or state_row.get("result_sha256") != candidate.get("result_sha256")
            or candidate.get("measurement_mode") != "resources"
            or candidate.get("serial_execution") is not True
            or candidate.get("phase_index") != group["phase_index"]
            or candidate.get("job_kind") != group["job_kind"]
            or not isinstance(checksum, Mapping)
            or checksum.get("status") != "VALID"
            or checksum.get("declared_entry_count")
            != checksum.get("verified_entry_count")
            or checksum.get("failures") not in ([], ())
        ):
            raise ValueError(
                f"original Phase-2 ineligible result binding differs: {job_id}"
            )


def _phase2_quiet_replay_evidence(
    workspace: Path,
    source_payloads: Mapping[str, bytes],
    original_receipt_payload: bytes,
) -> tuple[dict[str, bytes], bytes, dict[str, bytes], dict[str, object]] | None:
    """Select the first checksum-valid eligible quiet replay without metric peeking."""

    prefix = f"{workspace.name}_resource_replay_"
    summary_parent = TOOL_ROOT / "JustPeachyResearchSummaries"
    candidates: list[tuple[str, Path, dict[str, object]]] = []
    for summary_root in sorted(summary_parent.glob(f"{prefix}*")):
        comparison_path = summary_root / "resource_comparison.json"
        if not comparison_path.is_file():
            continue
        comparison = json.loads(comparison_path.read_bytes())
        if not isinstance(comparison, dict):
            continue
        if (
            comparison.get("schema_version") != "h2-phase2-quiet-resource-comparison.v1"
            or comparison.get("status") != "COMPLETE_ELIGIBLE"
            or comparison.get("eligible_for_final_resource_ranking") is not True
            or comparison.get("host_io_status") != "SERIAL_RESOURCE_HOST_IO_CLEAR"
        ):
            continue
        candidates.append((summary_root.name[len(prefix) :], summary_root, comparison))
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0])
    attempt_id, summary_root, comparison = candidates[0]
    replay_name = f"{prefix}{attempt_id}"
    replay_workspace = TOOL_ROOT / "automated_runs" / replay_name
    replay_manifest_path = replay_workspace / "resource_replay_manifest.json"
    replay_state_path = replay_workspace / "program_state.json"
    replay_job_manifest_path = replay_workspace / "job_manifest.json"
    replay_receipt_path = (
        replay_workspace
        / "diagnostics/host_io_interference/serial_resource_replay.json"
    )
    comparison_path = summary_root / "resource_comparison.json"
    comparison_csv_path = summary_root / "resource_comparison.csv"
    launcher_path = TOOL_ROOT / "scripts/replay_h2_phase2_serial_resources.py"
    readme_path = TOOL_ROOT / "scripts/H2_PHASE2_QUIET_RESOURCE_REPLAY_README.md"
    required_paths = (
        replay_manifest_path,
        replay_state_path,
        replay_job_manifest_path,
        replay_receipt_path,
        comparison_path,
        comparison_csv_path,
        launcher_path,
        readme_path,
    )
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        raise ValueError(
            "eligible Phase-2 quiet replay is incomplete: " + ", ".join(missing)
        )

    replay_manifest_payload = replay_manifest_path.read_bytes()
    replay_state_payload = replay_state_path.read_bytes()
    replay_job_manifest_payload = replay_job_manifest_path.read_bytes()
    replay_receipt_payload = replay_receipt_path.read_bytes()
    comparison_payload = comparison_path.read_bytes()
    comparison_csv_payload = comparison_csv_path.read_bytes()
    launcher_payload = launcher_path.read_bytes()
    readme_payload = readme_path.read_bytes()
    replay_manifest = json.loads(replay_manifest_payload)
    replay_state = json.loads(replay_state_payload)
    replay_job_manifest = json.loads(replay_job_manifest_payload)
    replay_receipt = json.loads(replay_receipt_payload)
    main_state = json.loads(source_payloads["controller/program_state.json"])
    main_job_manifest = json.loads(source_payloads["protocol/job_manifest.json"])
    runtime_identity = json.loads(source_payloads[RUNTIME_IDENTITY_MEMBER])
    original_receipt = json.loads(original_receipt_payload)
    values = (
        replay_manifest,
        replay_state,
        replay_job_manifest,
        replay_receipt,
        main_state,
        main_job_manifest,
        runtime_identity,
        original_receipt,
    )
    if not all(isinstance(value, dict) for value in values):
        raise ValueError("Phase-2 quiet replay binding payloads are invalid")

    phase2_group = SERIAL_HOST_IO_GROUPS[0]
    _validate_phase2_ineligible_original_receipt(
        original_receipt,
        main_state,
        main_job_manifest,
        phase2_group,
        collector_sha256=_sha256(
            (TOOL_ROOT / "scripts/capture_h2_host_io_interference.ps1").read_bytes()
        ),
    )
    unsigned_replay_manifest = dict(replay_manifest)
    replay_manifest_sha = unsigned_replay_manifest.pop("replay_manifest_sha256", None)
    unsigned_comparison = dict(comparison)
    comparison_sha = unsigned_comparison.pop("comparison_sha256", None)
    expected_ids = tuple(map(str, phase2_group["job_ids"]))
    job_bindings = replay_manifest.get("job_bindings")
    replay_state_jobs = replay_state.get("jobs")
    comparison_jobs = comparison.get("jobs")
    main_state_jobs = main_state.get("jobs")
    manifest_jobs = replay_job_manifest.get("jobs")
    manifest_by_id = (
        {
            str(row.get("job_id") or ""): row
            for row in manifest_jobs
            if isinstance(row, Mapping)
        }
        if isinstance(manifest_jobs, list)
        else {}
    )
    if (
        replay_manifest.get("schema_version") != "h2-phase2-quiet-resource-replay.v1"
        or replay_manifest.get("attempt_id") != attempt_id
        or replay_manifest_sha != canonical_sha256(unsigned_replay_manifest)
        or replay_manifest.get("launcher_sha256") != _sha256(launcher_payload)
        or tuple(map(str, replay_manifest.get("execution_order") or ())) != expected_ids
        or replay_manifest.get("serial_execution") is not True
        or replay_manifest.get("measurement_mode") != "resources"
        or replay_manifest.get("protocol_id") != main_state.get("protocol_id")
        or replay_manifest.get("protocol_sha256") != main_state.get("protocol_sha256")
        or replay_manifest.get("job_manifest_sha256")
        != main_state.get("job_manifest_sha256")
        or replay_manifest.get("scientific_settings_changed") is not False
        or replay_manifest.get("source_results_overwritten") is not False
        or replay_manifest.get("heldout_references_opened") is not False
        or replay_state.get("status") != "COMPLETE"
        or replay_state.get("schema_version")
        != "h2-phase2-quiet-resource-replay-state.v1"
        or replay_state.get("replay_manifest_sha256") != replay_manifest_sha
        or replay_state.get("protocol_id") != main_state.get("protocol_id")
        or replay_state.get("protocol_sha256") != main_state.get("protocol_sha256")
        or replay_state.get("job_manifest_sha256")
        != main_state.get("job_manifest_sha256")
        or replay_job_manifest != main_job_manifest
        or comparison_sha != canonical_sha256(unsigned_comparison)
        or comparison.get("replay_manifest_sha256") != replay_manifest_sha
        or tuple(map(str, comparison.get("execution_order") or ())) != expected_ids
        or replay_receipt.get("status") != "SERIAL_RESOURCE_HOST_IO_CLEAR"
        or tuple(map(str, replay_receipt.get("candidate_job_ids") or ()))
        != expected_ids
        or original_receipt.get("status")
        not in {
            "SERIAL_RESOURCE_HOST_IO_CONTAMINATED",
            "SERIAL_RESOURCE_HOST_IO_UNVERIFIED",
        }
        or not isinstance(job_bindings, list)
        or not isinstance(replay_state_jobs, dict)
        or not isinstance(comparison_jobs, dict)
        or not isinstance(main_state_jobs, dict)
        or len(manifest_by_id) != len(manifest_jobs)
        or not set(expected_ids).issubset(manifest_by_id)
        or runtime_identity.get("identity_sha256")
        != replay_manifest.get("runtime_implementation_identity_sha256")
    ):
        raise ValueError("Phase-2 quiet replay scientific/provenance binding differs")
    if tuple(str(row.get("job_id") or "") for row in job_bindings) != expected_ids:
        raise ValueError("Phase-2 quiet replay job binding order differs")
    for row in job_bindings:
        job_id = str(row.get("job_id") or "")
        state_row = replay_state_jobs.get(job_id)
        comparison_row = comparison_jobs.get(job_id)
        main_row = main_state_jobs.get(job_id)
        manifest_row = manifest_by_id.get(job_id)
        if (
            not isinstance(state_row, dict)
            or not isinstance(comparison_row, dict)
            or not isinstance(main_row, dict)
            or not isinstance(manifest_row, dict)
            or state_row.get("state") != "COMPLETE"
            or state_row.get("result_sha256") != comparison_row.get("result_sha256")
            or row.get("source_result_sha256") != main_row.get("result_sha256")
            or row.get("job_identity_sha256") != manifest_row.get("identity_sha256")
            or row.get("configuration_id") != manifest_row.get("configuration_id")
            or row.get("runtime_tuning_identity_sha256")
            != canonical_sha256(manifest_row.get("runtime_tuning") or {})
            or row.get("case_ids_sha256")
            != canonical_sha256(list(manifest_row.get("case_ids") or ()))
            or row.get("case_count") != len(manifest_row.get("case_ids") or ())
            or not math.isclose(
                float(row.get("audio_duration_sec") or 0.0),
                float(manifest_row.get("audio_duration_sec") or 0.0),
                abs_tol=1e-9,
            )
        ):
            raise ValueError(f"Phase-2 quiet replay result lineage differs: {job_id}")

    sanitized_manifest = json.loads(replay_manifest_payload)
    sanitized_manifest.pop("replay_manifest_sha256")
    for key, replacement in {
        "source_workspace": "%SOURCE_WORKSPACE%",
        "source_results_root": "%SOURCE_RESULTS_ROOT%",
        "replay_workspace": "%REPLAY_WORKSPACE%",
        "replay_results_root": "%REPLAY_RESULTS_ROOT%",
    }.items():
        sanitized_manifest[key] = replacement
    sanitized_manifest["source_replay_manifest_sha256"] = replay_manifest_sha
    sanitized_manifest["source_replay_manifest_file_sha256"] = _sha256(
        replay_manifest_payload
    )
    sanitized_manifest["host_paths_redacted"] = True
    sanitized_manifest["packaged_replay_manifest_sha256"] = canonical_sha256(
        sanitized_manifest
    )
    packaged_replay_manifest_payload = _canonical_json(sanitized_manifest)

    sanitized_state = json.loads(replay_state_payload)
    for job_id in expected_ids:
        row = sanitized_state["jobs"][job_id]
        row["result_path"] = f"%REPLAY_RESULTS_ROOT%/jobs/{job_id}/result"
    packaged_state_payload = _canonical_json(sanitized_state)
    if (
        b"C:\\\\Users\\\\" in replay_receipt_payload
        or b"just-peachy" in replay_receipt_payload
    ):
        raise ValueError(
            "Phase-2 quiet replay receipt contains an unsanitized host path"
        )
    if (
        b"C:\\\\Users\\\\" in replay_job_manifest_payload
        or b"just-peachy" in replay_job_manifest_payload
    ):
        raise ValueError("Phase-2 quiet replay job manifest contains a host path")

    support_payloads = {
        PHASE2_QUIET_REPLAY_MANIFEST_MEMBER: packaged_replay_manifest_payload,
        PHASE2_QUIET_REPLAY_STATE_MEMBER: packaged_state_payload,
        PHASE2_QUIET_REPLAY_JOB_MANIFEST_MEMBER: replay_job_manifest_payload,
        PHASE2_QUIET_REPLAY_COMPARISON_MEMBER: comparison_payload,
        PHASE2_QUIET_REPLAY_COMPARISON_CSV_MEMBER: comparison_csv_payload,
        PHASE2_QUIET_REPLAY_LAUNCHER_MEMBER: launcher_payload,
        PHASE2_QUIET_REPLAY_README_MEMBER: readme_payload,
        PHASE2_ORIGINAL_CONTAMINATED_RECEIPT_MEMBER: original_receipt_payload,
    }
    binding_core = {
        "schema_version": "h2-phase2-quiet-resource-package-binding.v1",
        "status": "VALID",
        "selected_attempt_id": attempt_id,
        "selection_policy": "FIRST_LEXICOGRAPHIC_ELIGIBLE_ATTEMPT_WITHOUT_METRIC_PEEKING",
        "eligible_attempt_ids": [row[0] for row in candidates],
        "protocol_id": main_state.get("protocol_id"),
        "protocol_sha256": main_state.get("protocol_sha256"),
        "job_manifest_sha256": main_state.get("job_manifest_sha256"),
        "runtime_implementation_identity_sha256": runtime_identity.get(
            "identity_sha256"
        ),
        "replay_manifest_sha256": replay_manifest_sha,
        "replay_manifest_file_sha256": _sha256(replay_manifest_payload),
        "candidate_job_ids": list(expected_ids),
        "original_receipt_status": original_receipt.get("status"),
        "original_receipt_sha256": _sha256(original_receipt_payload),
        "replay_receipt_status": replay_receipt.get("status"),
        "replay_receipt_sha256": _sha256(replay_receipt_payload),
        "comparison_sha256": comparison_sha,
        "scientific_settings_changed": False,
        "source_results_overwritten": False,
        "packaged_support_members": [
            {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
            for name, payload in sorted(support_payloads.items())
        ],
    }
    binding = {
        **binding_core,
        "binding_sha256": canonical_sha256(binding_core),
    }
    binding_payload = _canonical_json(binding)
    support_payloads[PHASE2_QUIET_REPLAY_BINDING_MEMBER] = binding_payload
    validation_sources = dict(source_payloads)
    validation_sources["controller/program_state.json"] = packaged_state_payload
    validation_sources["protocol/job_manifest.json"] = replay_job_manifest_payload
    return (
        support_payloads,
        replay_receipt_payload,
        validation_sources,
        {
            "evidence_origin": "quiet_replay",
            "selected_attempt_id": attempt_id,
            "binding_sha256": binding["binding_sha256"],
        },
    )


def _validate_packaged_phase2_quiet_replay(
    payloads: Mapping[str, bytes],
    group: Mapping[str, object],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Validate the replay bridge using only bytes carried in the final ZIP."""

    missing = [
        name for name in REQUIRED_PHASE2_QUIET_REPLAY_MEMBERS if name not in payloads
    ]
    if missing:
        raise ValueError(
            "packaged Phase-2 quiet replay is incomplete: " + ", ".join(missing)
        )
    binding = json.loads(payloads[PHASE2_QUIET_REPLAY_BINDING_MEMBER])
    replay_manifest = json.loads(payloads[PHASE2_QUIET_REPLAY_MANIFEST_MEMBER])
    replay_state = json.loads(payloads[PHASE2_QUIET_REPLAY_STATE_MEMBER])
    replay_job_manifest = json.loads(payloads[PHASE2_QUIET_REPLAY_JOB_MANIFEST_MEMBER])
    comparison = json.loads(payloads[PHASE2_QUIET_REPLAY_COMPARISON_MEMBER])
    original_receipt = json.loads(payloads[PHASE2_ORIGINAL_CONTAMINATED_RECEIPT_MEMBER])
    main_state = json.loads(payloads["controller/program_state.json"])
    main_job_manifest = json.loads(payloads["protocol/job_manifest.json"])
    runtime_identity = json.loads(payloads[RUNTIME_IDENTITY_MEMBER])
    values = (
        binding,
        replay_manifest,
        replay_state,
        replay_job_manifest,
        comparison,
        original_receipt,
        main_state,
        main_job_manifest,
        runtime_identity,
    )
    if not all(isinstance(value, dict) for value in values):
        raise ValueError("packaged Phase-2 quiet replay JSON is invalid")

    binding_core = dict(binding)
    binding_sha = binding_core.pop("binding_sha256", None)
    packaged_manifest_core = dict(replay_manifest)
    packaged_manifest_sha = packaged_manifest_core.pop(
        "packaged_replay_manifest_sha256", None
    )
    comparison_core = dict(comparison)
    comparison_sha = comparison_core.pop("comparison_sha256", None)
    expected_ids = tuple(map(str, group["job_ids"]))
    selected_attempt = str(binding.get("selected_attempt_id") or "")
    eligible_attempts = binding.get("eligible_attempt_ids")
    support_members = binding.get("packaged_support_members")
    expected_support = set(REQUIRED_PHASE2_QUIET_REPLAY_MEMBERS) - {
        PHASE2_QUIET_REPLAY_BINDING_MEMBER
    }
    if not isinstance(support_members, list):
        raise ValueError("packaged Phase-2 quiet replay support inventory is invalid")
    support_by_name = {
        str(row.get("member") or ""): row
        for row in support_members
        if isinstance(row, Mapping)
    }
    if set(support_by_name) != expected_support or any(
        row.get("sha256") != _sha256(payloads[name])
        or row.get("bytes") != len(payloads[name])
        for name, row in support_by_name.items()
    ):
        raise ValueError(
            "packaged Phase-2 quiet replay support inventory/checksum differs"
        )

    if (
        binding.get("schema_version") != "h2-phase2-quiet-resource-package-binding.v1"
        or binding.get("status") != "VALID"
        or binding_sha != canonical_sha256(binding_core)
        or not selected_attempt
        or not isinstance(eligible_attempts, list)
        or eligible_attempts != sorted(set(map(str, eligible_attempts)))
        or selected_attempt != eligible_attempts[0]
        or binding.get("selection_policy")
        != "FIRST_LEXICOGRAPHIC_ELIGIBLE_ATTEMPT_WITHOUT_METRIC_PEEKING"
        or tuple(map(str, binding.get("candidate_job_ids") or ())) != expected_ids
        or binding.get("protocol_id") != main_state.get("protocol_id")
        or binding.get("protocol_sha256") != main_state.get("protocol_sha256")
        or binding.get("job_manifest_sha256") != main_state.get("job_manifest_sha256")
        or binding.get("runtime_implementation_identity_sha256")
        != runtime_identity.get("identity_sha256")
        or binding.get("original_receipt_status")
        not in {
            "SERIAL_RESOURCE_HOST_IO_CONTAMINATED",
            "SERIAL_RESOURCE_HOST_IO_UNVERIFIED",
        }
        or binding.get("original_receipt_sha256")
        != _sha256(payloads[PHASE2_ORIGINAL_CONTAMINATED_RECEIPT_MEMBER])
        or binding.get("replay_receipt_status") != "SERIAL_RESOURCE_HOST_IO_CLEAR"
        or binding.get("replay_receipt_sha256")
        != _sha256(payloads[SERIAL_HOST_IO_RECEIPT_MEMBERS[0]])
        or binding.get("comparison_sha256") != comparison_sha
        or binding.get("scientific_settings_changed") is not False
        or binding.get("source_results_overwritten") is not False
    ):
        raise ValueError("packaged Phase-2 quiet replay binding differs")

    if (
        replay_manifest.get("schema_version") != "h2-phase2-quiet-resource-replay.v1"
        or replay_manifest.get("attempt_id") != selected_attempt
        or replay_manifest.get("source_workspace") != "%SOURCE_WORKSPACE%"
        or replay_manifest.get("source_results_root") != "%SOURCE_RESULTS_ROOT%"
        or replay_manifest.get("replay_workspace") != "%REPLAY_WORKSPACE%"
        or replay_manifest.get("replay_results_root") != "%REPLAY_RESULTS_ROOT%"
        or replay_manifest.get("host_paths_redacted") is not True
        or packaged_manifest_sha != canonical_sha256(packaged_manifest_core)
        or replay_manifest.get("source_replay_manifest_sha256")
        != binding.get("replay_manifest_sha256")
        or replay_manifest.get("source_replay_manifest_file_sha256")
        != binding.get("replay_manifest_file_sha256")
        or replay_manifest.get("launcher_sha256")
        != _sha256(payloads[PHASE2_QUIET_REPLAY_LAUNCHER_MEMBER])
        or replay_manifest.get("protocol_id") != main_state.get("protocol_id")
        or replay_manifest.get("protocol_sha256") != main_state.get("protocol_sha256")
        or replay_manifest.get("job_manifest_sha256")
        != main_state.get("job_manifest_sha256")
        or replay_manifest.get("runtime_implementation_identity_sha256")
        != runtime_identity.get("identity_sha256")
        or tuple(map(str, replay_manifest.get("execution_order") or ())) != expected_ids
        or replay_manifest.get("measurement_mode") != "resources"
        or replay_manifest.get("serial_execution") is not True
        or replay_manifest.get("scientific_settings_changed") is not False
        or replay_manifest.get("source_results_overwritten") is not False
        or replay_manifest.get("heldout_references_opened") is not False
    ):
        raise ValueError("packaged Phase-2 quiet replay manifest differs")

    original_ids = tuple(map(str, original_receipt.get("candidate_job_ids") or ()))
    if (
        original_receipt.get("status")
        not in {
            "SERIAL_RESOURCE_HOST_IO_CONTAMINATED",
            "SERIAL_RESOURCE_HOST_IO_UNVERIFIED",
        }
        or original_receipt.get("status") != binding.get("original_receipt_status")
        or original_ids != expected_ids
    ):
        raise ValueError("packaged original Phase-2 contamination receipt differs")
    _validate_phase2_ineligible_original_receipt(
        original_receipt,
        main_state,
        main_job_manifest,
        group,
        collector_sha256=_sha256(payloads[HOST_IO_COLLECTOR_MEMBER]),
    )
    if replay_job_manifest != main_job_manifest:
        raise ValueError("packaged replay/source job manifests differ")
    if (
        replay_state.get("schema_version") != "h2-phase2-quiet-resource-replay-state.v1"
        or replay_state.get("status") != "COMPLETE"
        or replay_state.get("protocol_id") != main_state.get("protocol_id")
        or replay_state.get("protocol_sha256") != main_state.get("protocol_sha256")
        or replay_state.get("job_manifest_sha256")
        != main_state.get("job_manifest_sha256")
        or replay_state.get("replay_manifest_sha256")
        != binding.get("replay_manifest_sha256")
    ):
        raise ValueError("packaged Phase-2 quiet replay state differs")
    if (
        comparison.get("schema_version") != "h2-phase2-quiet-resource-comparison.v1"
        or comparison.get("status") != "COMPLETE_ELIGIBLE"
        or comparison.get("eligible_for_final_resource_ranking") is not True
        or comparison.get("host_io_status") != "SERIAL_RESOURCE_HOST_IO_CLEAR"
        or comparison_sha != canonical_sha256(comparison_core)
        or comparison.get("replay_manifest_sha256")
        != binding.get("replay_manifest_sha256")
        or tuple(map(str, comparison.get("execution_order") or ())) != expected_ids
    ):
        raise ValueError("packaged Phase-2 quiet replay comparison differs")

    replay_jobs = replay_state.get("jobs")
    comparison_jobs = comparison.get("jobs")
    job_bindings = replay_manifest.get("job_bindings")
    manifest_rows = replay_job_manifest.get("jobs")
    main_jobs = main_state.get("jobs")
    if (
        not isinstance(replay_jobs, dict)
        or not isinstance(comparison_jobs, dict)
        or not isinstance(job_bindings, list)
        or not isinstance(manifest_rows, list)
        or not isinstance(main_jobs, dict)
        or set(replay_jobs) != set(expected_ids)
        or set(comparison_jobs) != set(expected_ids)
        or tuple(str(row.get("job_id") or "") for row in job_bindings) != expected_ids
    ):
        raise ValueError("packaged Phase-2 quiet replay job membership differs")
    manifest_by_id = {
        str(row.get("job_id") or ""): row
        for row in manifest_rows
        if isinstance(row, Mapping)
    }
    for binding_row in job_bindings:
        job_id = str(binding_row.get("job_id") or "")
        replay_row = replay_jobs[job_id]
        comparison_row = comparison_jobs[job_id]
        source_row = main_jobs.get(job_id)
        manifest_row = manifest_by_id.get(job_id)
        if (
            not isinstance(replay_row, Mapping)
            or not isinstance(comparison_row, Mapping)
            or not isinstance(source_row, Mapping)
            or not isinstance(manifest_row, Mapping)
            or replay_row.get("state") != "COMPLETE"
            or replay_row.get("result_path")
            != f"%REPLAY_RESULTS_ROOT%/jobs/{job_id}/result"
            or replay_row.get("result_sha256") != comparison_row.get("result_sha256")
            or binding_row.get("source_result_sha256")
            != source_row.get("result_sha256")
            or binding_row.get("job_identity_sha256")
            != manifest_row.get("identity_sha256")
            or binding_row.get("configuration_id")
            != manifest_row.get("configuration_id")
            or binding_row.get("runtime_tuning_identity_sha256")
            != canonical_sha256(manifest_row.get("runtime_tuning") or {})
            or binding_row.get("case_ids_sha256")
            != canonical_sha256(list(manifest_row.get("case_ids") or ()))
            or binding_row.get("case_count") != len(manifest_row.get("case_ids") or ())
            or not math.isclose(
                float(binding_row.get("audio_duration_sec") or 0.0),
                float(manifest_row.get("audio_duration_sec") or 0.0),
                abs_tol=1e-9,
            )
        ):
            raise ValueError(
                f"packaged Phase-2 quiet replay job lineage differs: {job_id}"
            )

    comparison_csv_rows = _csv_rows(payloads[PHASE2_QUIET_REPLAY_COMPARISON_CSV_MEMBER])
    if len(comparison_csv_rows) != len(expected_ids):
        raise ValueError("packaged Phase-2 quiet replay comparison CSV differs")
    strategies = dict(zip(expected_ids, ("R1", "R2"), strict=True))
    for row, job_id in zip(comparison_csv_rows, expected_ids, strict=True):
        metrics = comparison_jobs[job_id]
        expected_values = {
            "job_id": job_id,
            "strategy": strategies[job_id],
            "eligible": "True",
            "host_io_status": "SERIAL_RESOURCE_HOST_IO_CLEAR",
            **{
                key: "" if metrics.get(key) is None else str(metrics.get(key))
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
        if any(
            str(row.get(key) or "") != value for key, value in expected_values.items()
        ):
            raise ValueError("packaged Phase-2 quiet replay comparison CSV differs")

    validation_sources = dict(payloads)
    validation_sources["controller/program_state.json"] = payloads[
        PHASE2_QUIET_REPLAY_STATE_MEMBER
    ]
    validation_sources["protocol/job_manifest.json"] = payloads[
        PHASE2_QUIET_REPLAY_JOB_MANIFEST_MEMBER
    ]
    metadata = {
        "evidence_origin": "quiet_replay",
        "selected_attempt_id": selected_attempt,
        "binding_sha256": binding_sha,
    }
    return validation_sources, metadata


def _serial_host_io_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    receipt_root = workspace / "diagnostics/host_io_interference"
    watcher_path = TOOL_ROOT / "scripts/watch_h2_serial_resource_io.ps1"
    collector_path = TOOL_ROOT / "scripts/capture_h2_host_io_interference.ps1"
    if not watcher_path.is_file() or not collector_path.is_file():
        raise ValueError("serial host-I/O collection code is absent")
    watcher_payload = watcher_path.read_bytes()
    collector_sha = _sha256(collector_path.read_bytes())
    output: dict[str, bytes] = {
        SERIAL_HOST_IO_WATCHER_MEMBER: watcher_payload,
    }
    summary_rows: list[dict[str, object]] = []
    receipt_rows: list[dict[str, object]] = []
    quiet_replay_group_count = 0
    for group_index, (group, member) in enumerate(
        zip(SERIAL_HOST_IO_GROUPS, SERIAL_HOST_IO_RECEIPT_MEMBERS, strict=True)
    ):
        path = receipt_root / str(group["receipt_filename"])
        if not path.is_file():
            raise ValueError(f"serial host-I/O receipt is absent: {path}")
        payload = path.read_bytes()
        if b"C:\\\\Users\\\\" in payload or b"just-peachy" in payload:
            raise ValueError(
                "serial host-I/O receipt contains an unsanitized host path"
            )
        receipt = json.loads(payload)
        if not isinstance(receipt, Mapping):
            raise ValueError("serial host-I/O receipt is not a JSON object")
        validation_sources: Mapping[str, bytes] = source_payloads
        evidence_metadata: dict[str, object] = {
            "evidence_origin": "main_campaign",
            "selected_attempt_id": None,
            "binding_sha256": None,
        }
        if (
            group_index == 0
            and receipt.get("status") != "SERIAL_RESOURCE_HOST_IO_CLEAR"
        ):
            replay = _phase2_quiet_replay_evidence(workspace, source_payloads, payload)
            if replay is not None:
                support, payload, validation_sources, evidence_metadata = replay
                output.update(support)
                receipt = json.loads(payload)
                quiet_replay_group_count += 1
        validated = _validate_serial_host_io_receipt_contract(
            receipt, validation_sources, group
        )
        receipt_provenance = receipt.get("provenance")
        if (
            not isinstance(receipt_provenance, Mapping)
            or receipt_provenance.get("collector_sha256") != collector_sha
        ):
            raise ValueError("serial host-I/O collector checksum differs")
        output[member] = payload
        summary_rows.extend(validated["summary_rows"])
        receipt_rows.append(
            {
                "group_id": group["group_id"],
                "member": member,
                "sha256": _sha256(payload),
                "bytes": len(payload),
                "candidate_job_ids": list(group["job_ids"]),
                "candidate_checksum_count": validated["candidate_checksum_count"],
                "status": validated["receipt_status"],
                "resource_comparison_eligible": True,
                **evidence_metadata,
            }
        )
    output[SERIAL_HOST_IO_SUMMARY_MEMBER] = _csv_payload(
        summary_rows, SERIAL_HOST_IO_SUMMARY_FIELDS
    )
    phase2_origin = str(receipt_rows[0]["evidence_origin"])
    phase2_explanation = (
        "The original Phase-2 R1/R2 receipt is retained as contaminated or "
        "unverified. The active Phase-2 receipt member and final R1/R2 resource "
        "comparison come from the first lexicographically named eligible quiet "
        "replay, bound to the original protocol, job manifest, runtime identity, "
        "source-result checksums, execution order, and clean Windows event window. "
        if phase2_origin == "quiet_replay"
        else "The Phase-2 R1/R2 receipt comes directly from the completed main "
        "campaign and passed the clear-host validation contract. "
    )
    output[SERIAL_HOST_IO_GUIDE_MEMBER] = (
        "# H2 serial-resource host-I/O eligibility\n\n"
        + phase2_explanation
        + "All five standardized resource jobs were run serially and their result "
        "checksums, frozen manifest membership, exact execution intervals, and "
        "Windows event evidence were independently validated. No ESENT hung-I/O "
        "event, storage warning/error, or genuine event-provider query failure "
        "overlapped either matched resource group. These serial measurements are "
        "eligible for final RTF, CPU, RAM, queue, and resource comparisons.\n\n"
        "The Phase-1 accuracy-run timing remains ineligible and is preserved "
        "separately. If either serial receipt is contaminated or unverified, "
        "package construction fails closed and the affected serial measurement "
        "must be replayed or recaptured.\n"
    ).encode("utf-8")
    member_rows = [
        {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
        for name, payload in sorted(output.items())
    ]
    provenance = {
        "schema_version": "h2-serial-host-io-package-provenance.v2",
        "status": "VALID",
        "collector_sha256": collector_sha,
        "watcher_sha256": _sha256(watcher_payload),
        "group_count": len(SERIAL_HOST_IO_GROUPS),
        "job_count": len(summary_rows),
        "candidate_checksum_count": sum(
            int(row["candidate_checksum_count"]) for row in receipt_rows
        ),
        "receipt_evidence": receipt_rows,
        "quiet_replay_group_count": quiet_replay_group_count,
        "all_serial_resource_receipts_clear": True,
        "all_result_checksums_verified": True,
        "resource_comparison_eligible": True,
        "accuracy_or_policy_changed": False,
        "inference_rerun_by_packager": False,
        "member_count_excluding_provenance": len(member_rows),
        "members": member_rows,
    }
    output[SERIAL_HOST_IO_PROVENANCE_MEMBER] = _canonical_json(provenance)
    return output, provenance


def _validate_serial_host_io_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_SERIAL_HOST_IO_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks serial host-I/O evidence: " + ", ".join(missing)
        )
    provenance = json.loads(payloads[SERIAL_HOST_IO_PROVENANCE_MEMBER])
    if not isinstance(provenance, Mapping):
        raise ValueError("serial host-I/O package provenance is invalid")
    declared_receipts = provenance.get("receipt_evidence")
    if not isinstance(declared_receipts, list):
        raise ValueError("serial host-I/O receipt provenance is invalid")
    declared_by_group = {
        str(row.get("group_id") or ""): row
        for row in declared_receipts
        if isinstance(row, Mapping)
    }
    if set(declared_by_group) != {
        str(group["group_id"]) for group in SERIAL_HOST_IO_GROUPS
    }:
        raise ValueError("serial host-I/O receipt provenance membership differs")
    collector_sha = _sha256(payloads[HOST_IO_COLLECTOR_MEMBER])
    summary_rows: list[dict[str, object]] = []
    receipt_evidence: list[dict[str, object]] = []
    quiet_replay_group_count = 0
    for group_index, (group, member) in enumerate(
        zip(SERIAL_HOST_IO_GROUPS, SERIAL_HOST_IO_RECEIPT_MEMBERS, strict=True)
    ):
        declared = declared_by_group[str(group["group_id"])]
        evidence_origin = str(declared.get("evidence_origin") or "")
        validation_sources: Mapping[str, bytes] = payloads
        evidence_metadata: dict[str, object]
        if group_index == 0 and evidence_origin == "quiet_replay":
            validation_sources, evidence_metadata = (
                _validate_packaged_phase2_quiet_replay(payloads, group)
            )
            quiet_replay_group_count += 1
        elif evidence_origin == "main_campaign":
            evidence_metadata = {
                "evidence_origin": "main_campaign",
                "selected_attempt_id": None,
                "binding_sha256": None,
            }
        else:
            raise ValueError("serial host-I/O evidence origin differs")
        receipt_payload = payloads[member]
        if b"C:\\\\Users\\\\" in receipt_payload or b"just-peachy" in receipt_payload:
            raise ValueError("packaged serial host-I/O receipt has an unsanitized path")
        receipt = json.loads(receipt_payload)
        if not isinstance(receipt, Mapping):
            raise ValueError("packaged serial host-I/O receipt is invalid")
        validated = _validate_serial_host_io_receipt_contract(
            receipt, validation_sources, group
        )
        receipt_provenance = receipt.get("provenance")
        if (
            not isinstance(receipt_provenance, Mapping)
            or receipt_provenance.get("collector_sha256") != collector_sha
        ):
            raise ValueError("packaged serial host-I/O collector identity differs")
        summary_rows.extend(validated["summary_rows"])
        receipt_evidence.append(
            {
                "group_id": group["group_id"],
                "member": member,
                "sha256": _sha256(receipt_payload),
                "bytes": len(receipt_payload),
                "candidate_job_ids": list(group["job_ids"]),
                "candidate_checksum_count": validated["candidate_checksum_count"],
                "status": validated["receipt_status"],
                "resource_comparison_eligible": True,
                **evidence_metadata,
            }
        )
    expected_summary = _csv_payload(summary_rows, SERIAL_HOST_IO_SUMMARY_FIELDS)
    if payloads[SERIAL_HOST_IO_SUMMARY_MEMBER] != expected_summary:
        raise ValueError("packaged serial host-I/O summary rendering differs")
    members = provenance.get("members")
    if not isinstance(members, list):
        raise ValueError("serial host-I/O member inventory is invalid")
    by_member = {
        str(row.get("member") or ""): row for row in members if isinstance(row, Mapping)
    }
    expected_members = set(REQUIRED_SERIAL_HOST_IO_MEMBERS) - {
        SERIAL_HOST_IO_PROVENANCE_MEMBER
    }
    if quiet_replay_group_count:
        expected_members.update(REQUIRED_PHASE2_QUIET_REPLAY_MEMBERS)
    if set(by_member) != expected_members or any(
        row.get("sha256") != _sha256(payloads[name])
        or row.get("bytes") != len(payloads[name])
        for name, row in by_member.items()
    ):
        raise ValueError("serial host-I/O member inventory/checksum differs")
    if (
        provenance.get("schema_version") != "h2-serial-host-io-package-provenance.v2"
        or provenance.get("status") != "VALID"
        or provenance.get("collector_sha256") != collector_sha
        or provenance.get("watcher_sha256")
        != _sha256(payloads[SERIAL_HOST_IO_WATCHER_MEMBER])
        or provenance.get("group_count") != len(SERIAL_HOST_IO_GROUPS)
        or provenance.get("job_count") != len(summary_rows)
        or provenance.get("candidate_checksum_count")
        != sum(int(row["candidate_checksum_count"]) for row in receipt_evidence)
        or provenance.get("receipt_evidence") != receipt_evidence
        or provenance.get("quiet_replay_group_count") != quiet_replay_group_count
        or provenance.get("all_serial_resource_receipts_clear") is not True
        or provenance.get("all_result_checksums_verified") is not True
        or provenance.get("resource_comparison_eligible") is not True
        or provenance.get("accuracy_or_policy_changed") is not False
        or provenance.get("inference_rerun_by_packager") is not False
        or provenance.get("member_count_excluding_provenance") != len(members)
    ):
        raise ValueError("serial host-I/O provenance/firewall differs")
    return dict(provenance)


BOUNDARY_SUMMARY_FIELDS = (
    "schema_version",
    "configuration_id",
    "boundary_correction_ms",
    "selected_by_development_receipt",
    "evidence_split",
    "case_count",
    "word_applicable_case_count",
    "paired_word_count",
    "baseline_correct_word_count",
    "candidate_correct_word_count",
    "final_word_speaker_label_accuracy",
    "final_word_speaker_label_accuracy_ci_lower_95",
    "final_word_speaker_label_accuracy_ci_upper_95",
    "changed_speaker_word_count_vs_0ms",
    "repaired_word_count_vs_0ms",
    "repaired_word_count_ci_lower_95",
    "repaired_word_count_ci_upper_95",
    "harmed_word_count_vs_0ms",
    "harmed_word_count_ci_lower_95",
    "harmed_word_count_ci_upper_95",
    "wrong_to_other_wrong_word_count_vs_0ms",
    "net_repaired_minus_harmed_words_vs_0ms",
    "initially_previous_speaker_word_count_0ms",
    "repaired_from_previous_speaker_word_count_vs_0ms",
    "initially_previous_speaker_word_time_status",
    "initially_previous_speaker_word_time_sec",
    "correct_transcribed_attributed_word_rate",
    "boundary_delay_sec",
    "speaker_relabel_revision_count",
    "mean_speaker_relabel_audio_delay_sec",
    "mean_speaker_relabel_compute_delay_sec",
    "transcript_revision_count",
    "retroactive_correction_count",
    "final_transcript_stability",
    "wrong_name_dwell_sec",
    "bootstrap_repetitions",
    "bootstrap_seed",
    "resampling_unit",
    "source_job_id",
    "source_result_sha256",
    "baseline_job_id",
    "baseline_result_sha256",
)

BOUNDARY_CASE_FIELDS = (
    "schema_version",
    "configuration_id",
    "boundary_correction_ms",
    "case_id",
    "source_case_id",
    "speaker_ids",
    "word_pair_status",
    "word_pair_reason",
    "paired_word_count",
    "baseline_correct_word_count",
    "candidate_correct_word_count",
    "changed_speaker_word_count_vs_0ms",
    "repaired_word_count_vs_0ms",
    "harmed_word_count_vs_0ms",
    "wrong_to_other_wrong_word_count_vs_0ms",
    "initially_previous_speaker_word_count_0ms",
    "repaired_from_previous_speaker_word_count_vs_0ms",
    "initially_previous_speaker_word_time_status",
    "candidate_word_speaker_label_accuracy",
    "correct_transcribed_attributed_word_rate",
    "boundary_delay_sec",
    "speaker_relabel_revision_count",
    "speaker_relabel_audio_delay_sum_sec",
    "speaker_relabel_audio_delay_count",
    "speaker_relabel_compute_delay_sum_sec",
    "speaker_relabel_compute_delay_count",
    "transcript_revision_count",
    "retroactive_correction_count",
    "final_transcript_stability",
    "wrong_name_dwell_sec",
)


def _boundary_manifest_jobs(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, object], dict[str, Mapping[str, object]]]:
    name = "protocol/job_manifest.json"
    if name not in source_payloads:
        raise ValueError("native package lacks the frozen job manifest")
    manifest = json.loads(source_payloads[name])
    if not isinstance(manifest, Mapping) or not isinstance(manifest.get("jobs"), list):
        raise ValueError("native package job manifest is invalid")
    matches: dict[str, Mapping[str, object]] = {}
    for raw in manifest["jobs"]:
        if not isinstance(raw, Mapping):
            continue
        configuration_id = str(raw.get("configuration_id") or "")
        if configuration_id in BOUNDARY_CONFIGURATIONS:
            if configuration_id in matches:
                raise ValueError(
                    f"duplicate boundary-correction configuration: {configuration_id}"
                )
            matches[configuration_id] = raw
    if tuple(sorted(matches)) != tuple(sorted(BOUNDARY_CONFIGURATIONS)):
        raise ValueError("frozen boundary-correction configuration membership differs")
    return dict(manifest), matches


def _safe_case_uem(
    case: Mapping[str, object], workspace: Path
) -> list[tuple[float, float]] | None:
    logical_name = str(case.get("reference_uem_logical_path") or "")
    expected = str(case.get("reference_uem_sha256") or "").casefold()
    if not logical_name and not expected:
        return None
    logical = PurePosixPath(logical_name)
    if (
        not logical_name
        or logical.is_absolute()
        or any(part in {"", ".", ".."} for part in logical.parts)
    ):
        raise ValueError(f"unsafe reference UEM path: {logical_name!r}")
    namespace = str(
        case.get("reference_uem_namespace")
        or case.get("audio_namespace")
        or "tool_root"
    )
    roots = {"tool_root": TOOL_ROOT.resolve(), "workspace": workspace.resolve()}
    if namespace not in roots:
        raise ValueError(f"unsupported reference UEM namespace: {namespace}")
    root = roots[namespace]
    path = (root / Path(*logical.parts)).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"reference UEM escaped {namespace}: {logical_name}") from exc
    payload = path.read_bytes()
    if len(expected) != 64 or _sha256(payload).casefold() != expected:
        raise ValueError(f"reference UEM checksum differs: {logical_name}")
    regions = parse_uem(path)
    recording_ids = {
        str(case.get("source_case_id") or ""),
        str(case.get("source_reference_id") or "").rsplit(":", 1)[-1],
    }
    selected = [row for row in regions if row.recording_id in recording_ids]
    if not selected and len({row.recording_id for row in regions}) == 1:
        selected = regions
    duration = float(case.get("duration_sec") or 0.0)
    clipped = sorted(
        {
            (max(0.0, row.start_sec), min(duration, row.end_sec))
            for row in selected
            if min(duration, row.end_sec) > max(0.0, row.start_sec)
        }
    )
    return clipped


def _case_reference_turns(
    case: Mapping[str, object], workspace: Path
) -> list[RttmTurn]:
    turns = parse_rttm(_safe_reference_path(case, workspace))
    recording_ids = {
        str(case.get("source_case_id") or ""),
        str(case.get("source_reference_id") or "").rsplit(":", 1)[-1],
    }
    selected = [row for row in turns if row.recording_id in recording_ids]
    if not selected and len({row.recording_id for row in turns}) == 1:
        selected = turns
    if not selected:
        raise ValueError(
            f"reference RTTM does not contain case {case.get('protocol_case_id')}"
        )
    return selected


def _case_metric(
    per_case: Mapping[str, object], report_id: str, metric_id: str
) -> Mapping[str, object]:
    reports = per_case.get("reports")
    report = reports.get(report_id) if isinstance(reports, Mapping) else None
    metrics = report.get("metrics") if isinstance(report, Mapping) else None
    metric = metrics.get(metric_id) if isinstance(metrics, Mapping) else None
    if not isinstance(metric, Mapping):
        raise ValueError(f"per-case metric is absent: {report_id}/{metric_id}")
    return metric


def _speaker_relabel_event_stats(
    path: Path, *, eligible_case_ids: set[str]
) -> dict[str, dict[str, float]]:
    assignments: dict[
        tuple[str, str], tuple[tuple[str | None, str | None], float | None, int | None]
    ] = {}
    stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "revision_count": 0.0,
            "audio_delay_sum_sec": 0.0,
            "audio_delay_count": 0.0,
            "compute_delay_sum_sec": 0.0,
            "compute_delay_count": 0.0,
        }
    )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("event_type") != "transcript_revision":
                continue
            case_id = str(event.get("evaluation_case_id") or "")
            spans = event.get("spans")
            if case_id not in eligible_case_ids or not isinstance(spans, list):
                continue
            capture = event.get("capture_timestamps")
            processing = event.get("processing_timestamps")
            audio_time = (
                _number(capture.get("audio_end_sec"))
                if isinstance(capture, Mapping)
                else None
            )
            emitted_raw = (
                processing.get("emitted_monotonic_ns")
                if isinstance(processing, Mapping)
                else None
            )
            emitted_ns = (
                int(emitted_raw)
                if isinstance(emitted_raw, (int, float))
                and not isinstance(emitted_raw, bool)
                else None
            )
            for span in spans:
                if not isinstance(span, Mapping):
                    continue
                span_id = str(span.get("span_id") or "")
                if not span_id:
                    continue
                key = (case_id, span_id)
                speaker = _span_speaker_key(span)
                prior = assignments.get(key)
                if prior is None:
                    assignments[key] = (speaker, audio_time, emitted_ns)
                    continue
                prior_speaker, assignment_audio, assignment_emitted = prior
                if speaker == prior_speaker:
                    continue
                stats[case_id]["revision_count"] += 1.0
                if (
                    audio_time is not None
                    and assignment_audio is not None
                    and audio_time >= assignment_audio
                ):
                    stats[case_id]["audio_delay_sum_sec"] += (
                        audio_time - assignment_audio
                    )
                    stats[case_id]["audio_delay_count"] += 1.0
                if (
                    emitted_ns is not None
                    and assignment_emitted is not None
                    and emitted_ns >= assignment_emitted
                ):
                    stats[case_id]["compute_delay_sum_sec"] += (
                        emitted_ns - assignment_emitted
                    ) / 1_000_000_000.0
                    stats[case_id]["compute_delay_count"] += 1.0
                assignments[key] = (speaker, audio_time, emitted_ns)
    return dict(stats)


def _reference_word_metadata(
    segments: Sequence[Mapping[str, object]],
    local_to_global: Mapping[str, str],
) -> list[dict[str, str | None]]:
    ordered = sorted(
        segments,
        key=lambda row: (
            float(row.get("start_sec") or 0.0),
            float(row.get("end_sec") or 0.0),
            str(row.get("reference_segment_id") or ""),
        ),
    )
    output: list[dict[str, str | None]] = []
    previous: Mapping[str, object] | None = None
    previous_speaker: str | None = None
    for segment in ordered:
        speaker = _canonical_reference_speaker_id(segment, local_to_global)
        text = segment.get("scorable_transcript") or segment.get("text")
        if speaker is None or text is None:
            continue
        prior_distinct: str | None = None
        if previous is not None and previous_speaker != speaker:
            prior_end = _number(previous.get("end_sec"))
            start = _number(segment.get("start_sec"))
            if prior_end is not None and start is not None and start >= prior_end:
                prior_distinct = previous_speaker
        output.extend(
            {
                "reference_speaker_id": speaker,
                "previous_distinct_speaker_id": prior_distinct,
            }
            for _word in _normalized_scoring_words(text)
        )
        previous = segment
        previous_speaker = speaker
    return output


def _boundary_ratio_interval(
    rows: Sequence[Mapping[str, object]],
    *,
    numerator_field: str,
    denominator_field: str,
    identity: str,
) -> tuple[float | None, float | None, float, float]:
    observations = [
        {
            "speaker_ids": row["_speaker_ids"],
            "numerator": float(row[numerator_field]),
            "denominator": float(row[denominator_field]),
        }
        for row in rows
        if float(row.get(denominator_field) or 0.0) > 0
    ]
    numerator = sum(float(row["numerator"]) for row in observations)
    denominator = sum(float(row["denominator"]) for row in observations)
    if not observations:
        return None, None, numerator, denominator
    lower, upper, _speaker_count, _seed = _speaker_set_bootstrap_ratio(
        observations, identity=identity
    )
    return lower, upper, numerator, denominator


def _boundary_sum_interval(
    rows: Sequence[Mapping[str, object]], *, field: str, identity: str
) -> tuple[float | None, float | None, float]:
    observations = [
        {"speaker_ids": row["_speaker_ids"], "value": float(row.get(field) or 0.0)}
        for row in rows
        if row.get("_speaker_ids")
    ]
    value = sum(float(row["value"]) for row in observations)
    if not observations:
        return None, None, value
    lower, upper, _speaker_count, _seed = _speaker_set_bootstrap_sum(
        observations, identity=identity
    )
    return lower, upper, value


def build_boundary_correction_supplement(
    source_payloads: Mapping[str, bytes], workspace: Path
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Pair the five immutable development boundary-correction results."""

    state_name = "controller/program_state.json"
    if state_name not in source_payloads:
        raise ValueError(
            "native package lacks controller state for boundary supplement"
        )
    state = json.loads(source_payloads[state_name])
    if not isinstance(state, Mapping):
        raise ValueError("packaged controller state is invalid")
    manifest, jobs = _boundary_manifest_jobs(source_payloads)
    if manifest.get("job_manifest_sha256") != state.get("job_manifest_sha256"):
        raise ValueError("boundary job manifest/controller binding differs")
    baseline_job = jobs[BOUNDARY_CONFIGURATIONS[0]]
    baseline_cases = tuple(map(str, baseline_job.get("case_ids") or ()))
    baseline_duration = _number(baseline_job.get("audio_duration_sec"))
    baseline_tuning = dict(baseline_job.get("runtime_tuning") or {})
    if baseline_tuning.pop("boundary_correction_ms", None) != 0 or not baseline_cases:
        raise ValueError("0ms boundary baseline identity is invalid")
    for configuration_id, job in jobs.items():
        correction_ms = int(configuration_id.rsplit("_", 1)[-1][:-2])
        tuning = dict(job.get("runtime_tuning") or {})
        observed_ms = tuning.pop("boundary_correction_ms", None)
        if (
            job.get("development_only") is not True
            or job.get("split") != "development"
            or job.get("job_kind") != "runtime_accuracy"
            or observed_ms != correction_ms
            or tuning != baseline_tuning
            or tuple(map(str, job.get("case_ids") or ())) != baseline_cases
            or _number(job.get("audio_duration_sec")) != baseline_duration
        ):
            raise ValueError(
                f"boundary jobs vary beyond the correction axis: {configuration_id}"
            )

    axis_bindings = state.get("axis_selections")
    raw_axis = (
        axis_bindings.get("boundary_correction")
        if isinstance(axis_bindings, Mapping)
        else None
    )
    if not isinstance(raw_axis, Mapping):
        raise ValueError("boundary-correction selection receipt binding is absent")
    axis_path = (workspace / "axis_selections/boundary_correction.json").resolve(
        strict=True
    )
    axis_payload = axis_path.read_bytes()
    if _sha256(axis_payload) != str(raw_axis.get("decision_sha256") or ""):
        raise ValueError("boundary-correction selection receipt checksum differs")
    axis = json.loads(axis_payload)
    selected = axis.get("selected_candidates") if isinstance(axis, Mapping) else None
    if not isinstance(selected, list) or len(selected) != 1 or selected[0] not in jobs:
        raise ValueError("boundary-correction selected candidate differs")

    state_jobs = state.get("jobs")
    if not isinstance(state_jobs, Mapping):
        raise ValueError("controller state lacks boundary job results")
    critical_names = (
        "diagnostics/per_case_metrics.jsonl",
        "events.jsonl.gz",
        "pipeline_identity.json",
        "predictions/diarization.rttm",
        "predictions/labelled_transcript.jsonl",
        "references/cases.jsonl",
        "references/selected_identity_overlays.jsonl",
        "references/selected_speaker_attributed_transcripts.jsonl",
    )
    variant_data: dict[str, dict[str, dict[str, object]]] = {}
    source_rows: list[dict[str, object]] = []
    invariant_hashes: dict[str, str] | None = None
    invariant_pipeline_tuning: dict[str, object] | None = None

    for configuration_id in BOUNDARY_CONFIGURATIONS:
        job = jobs[configuration_id]
        job_id = str(job.get("job_id") or "")
        state_job = state_jobs.get(job_id)
        expected_sha = (
            str(state_job.get("result_sha256") or "")
            if isinstance(state_job, Mapping)
            else ""
        )
        root, pipeline, critical = _validated_bound_result(
            state=state,
            job_id=job_id,
            expected_sha256=expected_sha,
            critical_names=critical_names,
        )
        correction_ms = int(configuration_id.rsplit("_", 1)[-1][:-2])
        pipeline_tuning = dict(pipeline.get("runtime_tuning") or {})
        if pipeline_tuning.pop("boundary_correction_ms", None) != correction_ms:
            raise ValueError(
                f"boundary result tuning identity differs: {configuration_id}"
            )
        if invariant_pipeline_tuning is None:
            invariant_pipeline_tuning = pipeline_tuning
        elif pipeline_tuning != invariant_pipeline_tuning:
            raise ValueError("boundary result pipelines vary beyond correction_ms")
        current_invariants = {
            name: str(critical[name]["sha256"])
            for name in (
                "references/cases.jsonl",
                "references/selected_identity_overlays.jsonl",
                "references/selected_speaker_attributed_transcripts.jsonl",
            )
        }
        if invariant_hashes is None:
            invariant_hashes = current_invariants
        elif current_invariants != invariant_hashes:
            raise ValueError("boundary result reference material differs")

        cases = _read_jsonl(root / "references/cases.jsonl")
        ordered_ids = tuple(str(row.get("protocol_case_id") or "") for row in cases)
        if ordered_ids != baseline_cases or {
            str(row.get("partition") or "") for row in cases
        } != {"development"}:
            raise ValueError(f"boundary result case/split differs: {configuration_id}")
        case_by_id = {str(row["protocol_case_id"]): row for row in cases}
        references_by_source = {
            str(row.get("source_case_id") or ""): row
            for row in _read_jsonl(
                root / "references/selected_speaker_attributed_transcripts.jsonl"
            )
            if row.get("source_case_id")
        }
        overlays_by_ref = {
            str(row.get("identity_overlay_ref") or ""): row
            for row in _read_jsonl(root / "references/selected_identity_overlays.jsonl")
            if row.get("identity_overlay_ref")
        }
        spans_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
        for span in _read_jsonl(root / "predictions/labelled_transcript.jsonl"):
            case_id = str(span.get("case_id") or "")
            if case_id:
                spans_by_case[case_id].append(span)
        per_case_rows = _read_jsonl(root / "diagnostics/per_case_metrics.jsonl")
        metrics_by_case = {str(row.get("case_id") or ""): row for row in per_case_rows}
        if set(metrics_by_case) != set(baseline_cases) or len(metrics_by_case) != len(
            per_case_rows
        ):
            raise ValueError(
                f"boundary per-case metric membership differs: {configuration_id}"
            )
        hypothesis_by_case: dict[str, list[RttmTurn]] = defaultdict(list)
        for turn in parse_rttm(root / "predictions/diarization.rttm"):
            hypothesis_by_case[turn.recording_id].append(turn)
        if set(hypothesis_by_case) - set(baseline_cases):
            raise ValueError("boundary prediction RTTM contains undeclared cases")

        policy = str(
            (pipeline.get("runtime_tuning") or {}).get("paragraph_policy") or ""
        )
        pause_sec = _number(
            (pipeline.get("runtime_tuning") or {}).get("paragraph_pause_sec")
        )
        maximum_words_raw = (pipeline.get("runtime_tuning") or {}).get(
            "paragraph_max_words"
        )
        if policy not in PARAGRAPH_POLICIES or pause_sec is None:
            raise ValueError("boundary result paragraph tuning is invalid")
        maximum_words = int(maximum_words_raw)
        supported_case_ids: set[str] = set()
        final_groups: dict[str, list[dict[str, object]]] = {}
        records: dict[str, dict[str, object]] = {}
        for case_id in baseline_cases:
            case = case_by_id[case_id]
            reference = references_by_source.get(str(case.get("source_case_id") or ""))
            raw_segments = (
                reference.get("segments") if isinstance(reference, Mapping) else None
            )
            segments = [
                dict(row)
                for row in (raw_segments or [])
                if isinstance(row, Mapping)
                and row.get("speaker_attributed_transcript_status") == "supported"
            ]
            spans = spans_by_case.get(case_id, [])
            alignment: list[dict[str, object]] | None = None
            word_reason = ""
            metadata: list[dict[str, str | None]] = []
            if (
                isinstance(reference, Mapping)
                and reference.get("speaker_attributed_transcript_status") == "supported"
                and segments
            ):
                references = _case_reference_turns(case, workspace)
                hypotheses = hypothesis_by_case.get(case_id, [])
                report = score_anonymous_diarization(
                    [
                        {
                            "start_sec": row.start_sec,
                            "end_sec": row.end_sec,
                            "speaker_id": row.speaker_label,
                        }
                        for row in references
                    ],
                    [
                        {
                            "start_sec": row.start_sec,
                            "end_sec": row.end_sec,
                            "speaker_id": row.speaker_label,
                        }
                        for row in hypotheses
                    ],
                    uem=_safe_case_uem(case, workspace),
                    collar_sec=0.0,
                    score_overlap=True,
                )
                mapping = report["der"].details.get("speaker_mapping", {})
                overlay = overlays_by_ref.get(
                    str(case.get("identity_overlay_ref") or "")
                )
                transcription = _speaker_transcription_scoring_inputs(
                    {
                        "reference_transcript_segments": segments,
                        "hypothesis_transcript_spans": spans,
                        "local_to_global_speaker": dict(
                            case.get("local_to_global_speaker") or {}
                        ),
                        "identity_overlay": overlay,
                    },
                    mapping if isinstance(mapping, Mapping) else {},
                )
                raw_alignment = transcription.get("word_alignments")
                if isinstance(raw_alignment, list):
                    alignment = [dict(row) for row in raw_alignment]
                    metadata = _reference_word_metadata(
                        segments, dict(case.get("local_to_global_speaker") or {})
                    )
                    if sum(
                        row.get("reference_word") is not None for row in alignment
                    ) != len(metadata):
                        raise ValueError(
                            f"boundary reference-word metadata differs: {case_id}"
                        )
                else:
                    word_reason = (
                        "cross-speaker reference overlap prevents frozen word alignment"
                    )
                supported_case_ids.add(case_id)
                final_groups[case_id] = _paragraph_groups(
                    spans,
                    policy=policy,
                    pause_sec=pause_sec,
                    maximum_words=maximum_words,
                )
            else:
                word_reason = "speaker-attributed transcript reference is unsupported"
            records[case_id] = {
                "case": case,
                "alignment": alignment,
                "metadata": metadata,
                "word_reason": word_reason,
                "per_case": metrics_by_case[case_id],
            }
        replay = _event_replay_stats(
            root / "events.jsonl.gz",
            eligible_case_ids=supported_case_ids,
            final_groups=final_groups,
            policy=policy,
            pause_sec=pause_sec,
            maximum_words=maximum_words,
        )
        relabel = _speaker_relabel_event_stats(
            root / "events.jsonl.gz", eligible_case_ids=supported_case_ids
        )
        for case_id, record in records.items():
            record["replay"] = replay.get(case_id, {})
            record["relabel"] = relabel.get(case_id, {})
        variant_data[configuration_id] = records
        source_rows.append(
            {
                "configuration_id": configuration_id,
                "boundary_correction_ms": correction_ms,
                "job_id": job_id,
                "result_sha256": expected_sha,
                "case_count": len(cases),
                "audio_duration_sec": sum(float(row["duration_sec"]) for row in cases),
                "critical_files": critical,
            }
        )

    baseline_id = BOUNDARY_CONFIGURATIONS[0]
    baseline_records = variant_data[baseline_id]
    case_rows: list[dict[str, object]] = []
    source_by_configuration = {str(row["configuration_id"]): row for row in source_rows}
    for configuration_id in BOUNDARY_CONFIGURATIONS:
        correction_ms = int(configuration_id.rsplit("_", 1)[-1][:-2])
        for case_id in baseline_cases:
            baseline = baseline_records[case_id]
            candidate = variant_data[configuration_id][case_id]
            baseline_alignment = baseline["alignment"]
            candidate_alignment = candidate["alignment"]
            paired = baseline_correct = candidate_correct = 0
            changed = repaired = harmed = wrong_to_wrong = 0
            initially_previous = repaired_from_previous = 0
            word_status = "COMPUTED"
            word_reason = ""
            if baseline_alignment is None or candidate_alignment is None:
                word_status = "UNSUPPORTED"
                word_reason = str(
                    candidate.get("word_reason") or baseline.get("word_reason") or ""
                )
            else:
                baseline_lexical = tuple(
                    (row.get("reference_word"), row.get("hypothesis_word"))
                    for row in baseline_alignment
                )
                candidate_lexical = tuple(
                    (row.get("reference_word"), row.get("hypothesis_word"))
                    for row in candidate_alignment
                )
                if baseline_lexical != candidate_lexical:
                    raise ValueError(
                        f"boundary lexical alignment changed on paired case: {case_id}"
                    )
                metadata = baseline["metadata"]
                reference_index = -1
                for base_row, candidate_row in zip(
                    baseline_alignment, candidate_alignment, strict=True
                ):
                    if base_row.get("reference_word") is not None:
                        reference_index += 1
                    if (
                        base_row.get("reference_word") is None
                        or base_row.get("hypothesis_word") is None
                    ):
                        continue
                    paired += 1
                    reference_speaker = base_row.get("reference_speaker_id")
                    base_speaker = base_row.get("hypothesis_speaker_id")
                    candidate_speaker = candidate_row.get("hypothesis_speaker_id")
                    base_is_correct = base_speaker == reference_speaker
                    candidate_is_correct = candidate_speaker == reference_speaker
                    baseline_correct += int(base_is_correct)
                    candidate_correct += int(candidate_is_correct)
                    changed_now = base_speaker != candidate_speaker
                    changed += int(changed_now)
                    repaired += int(not base_is_correct and candidate_is_correct)
                    harmed += int(base_is_correct and not candidate_is_correct)
                    wrong_to_wrong += int(
                        changed_now and not base_is_correct and not candidate_is_correct
                    )
                    prior_speaker = metadata[reference_index].get(
                        "previous_distinct_speaker_id"
                    )
                    from_previous = (
                        prior_speaker is not None
                        and base_speaker == prior_speaker
                        and not base_is_correct
                    )
                    initially_previous += int(from_previous)
                    repaired_from_previous += int(
                        from_previous and candidate_is_correct
                    )

            per_case = candidate["per_case"]
            word_metric = _case_metric(
                per_case, "speaker_transcription", "word_speaker_label_accuracy"
            )
            if word_status == "COMPUTED":
                if (
                    word_metric.get("status") != "computed"
                    or _number(word_metric.get("numerator")) != candidate_correct
                    or _number(word_metric.get("denominator")) != paired
                ):
                    raise ValueError(
                        f"derived/source word attribution differs: {configuration_id}/{case_id}"
                    )
            correct_attributed = _case_metric(
                per_case,
                "speaker_transcription",
                "correct_transcribed_attributed_word_rate",
            )
            boundary_delay = _case_metric(per_case, "diarization", "boundary_delay_sec")
            transcript_revisions = _case_metric(
                per_case, "ux", "transcript_revision_count"
            )
            retroactive = _case_metric(
                per_case, "speaker_transcription", "retroactive_correction_count"
            )
            wrong_dwell = _case_metric(per_case, "ux", "wrong_name_dwell_sec")
            replay = candidate.get("replay") or {}
            relabel = candidate.get("relabel") or {}
            case = candidate["case"]
            speakers = tuple(
                sorted(
                    str(value) for value in case.get("global_speaker_ids", ()) if value
                )
            )
            case_rows.append(
                {
                    "schema_version": "h2-boundary-correction-case-pair.v1",
                    "configuration_id": configuration_id,
                    "boundary_correction_ms": correction_ms,
                    "case_id": case_id,
                    "source_case_id": case.get("source_case_id"),
                    "speaker_ids": ";".join(speakers),
                    "word_pair_status": word_status,
                    "word_pair_reason": word_reason,
                    "paired_word_count": paired,
                    "baseline_correct_word_count": baseline_correct,
                    "candidate_correct_word_count": candidate_correct,
                    "changed_speaker_word_count_vs_0ms": changed,
                    "repaired_word_count_vs_0ms": repaired,
                    "harmed_word_count_vs_0ms": harmed,
                    "wrong_to_other_wrong_word_count_vs_0ms": wrong_to_wrong,
                    "initially_previous_speaker_word_count_0ms": initially_previous,
                    "repaired_from_previous_speaker_word_count_vs_0ms": repaired_from_previous,
                    "initially_previous_speaker_word_time_status": "UNSUPPORTED_NO_REFERENCE_WORD_TIMESTAMPS",
                    "candidate_word_speaker_label_accuracy": _number(
                        word_metric.get("value")
                    ),
                    "correct_transcribed_attributed_word_rate": _number(
                        correct_attributed.get("value")
                    ),
                    "boundary_delay_sec": _number(boundary_delay.get("value")),
                    "speaker_relabel_revision_count": float(
                        relabel.get("revision_count", 0.0)
                    ),
                    "speaker_relabel_audio_delay_sum_sec": float(
                        relabel.get("audio_delay_sum_sec", 0.0)
                    ),
                    "speaker_relabel_audio_delay_count": float(
                        relabel.get("audio_delay_count", 0.0)
                    ),
                    "speaker_relabel_compute_delay_sum_sec": float(
                        relabel.get("compute_delay_sum_sec", 0.0)
                    ),
                    "speaker_relabel_compute_delay_count": float(
                        relabel.get("compute_delay_count", 0.0)
                    ),
                    "transcript_revision_count": _number(
                        transcript_revisions.get("value")
                    ),
                    "retroactive_correction_count": _number(retroactive.get("value")),
                    "final_transcript_stability": (
                        float(replay.get("final_agreement", 0.0))
                        if float(replay.get("final_eligible", 0.0)) > 0
                        else None
                    ),
                    "wrong_name_dwell_sec": _number(wrong_dwell.get("value")),
                    "_speaker_ids": speakers,
                    "_word_numerator": float(candidate_correct),
                    "_word_denominator": float(paired),
                    "_correct_attr_numerator": float(
                        _number(correct_attributed.get("numerator")) or 0.0
                    ),
                    "_correct_attr_denominator": float(
                        _number(correct_attributed.get("denominator")) or 0.0
                    ),
                    "_boundary_numerator": float(
                        _number(boundary_delay.get("numerator")) or 0.0
                    ),
                    "_boundary_denominator": float(
                        _number(boundary_delay.get("denominator")) or 0.0
                    ),
                    "_final_numerator": float(replay.get("final_agreement", 0.0)),
                    "_final_denominator": float(replay.get("final_eligible", 0.0)),
                }
            )

    summary_rows: list[dict[str, object]] = []
    for configuration_id in BOUNDARY_CONFIGURATIONS:
        rows = [row for row in case_rows if row["configuration_id"] == configuration_id]
        applicable = [row for row in rows if row["word_pair_status"] == "COMPUTED"]
        correction_ms = int(configuration_id.rsplit("_", 1)[-1][:-2])
        word_low, word_high, word_num, word_den = _boundary_ratio_interval(
            applicable,
            numerator_field="_word_numerator",
            denominator_field="_word_denominator",
            identity=f"{configuration_id}:word_accuracy",
        )
        repaired_low, repaired_high, repaired_total = _boundary_sum_interval(
            applicable,
            field="repaired_word_count_vs_0ms",
            identity=f"{configuration_id}:repaired_words",
        )
        harmed_low, harmed_high, harmed_total = _boundary_sum_interval(
            applicable,
            field="harmed_word_count_vs_0ms",
            identity=f"{configuration_id}:harmed_words",
        )
        _ca_low, _ca_high, correct_num, correct_den = _boundary_ratio_interval(
            rows,
            numerator_field="_correct_attr_numerator",
            denominator_field="_correct_attr_denominator",
            identity=f"{configuration_id}:correct_attributed",
        )
        _bd_low, _bd_high, boundary_num, boundary_den = _boundary_ratio_interval(
            rows,
            numerator_field="_boundary_numerator",
            denominator_field="_boundary_denominator",
            identity=f"{configuration_id}:boundary_delay",
        )
        _fs_low, _fs_high, final_num, final_den = _boundary_ratio_interval(
            rows,
            numerator_field="_final_numerator",
            denominator_field="_final_denominator",
            identity=f"{configuration_id}:final_stability",
        )
        audio_delay_sum = sum(
            float(row["speaker_relabel_audio_delay_sum_sec"]) for row in rows
        )
        audio_delay_count = sum(
            float(row["speaker_relabel_audio_delay_count"]) for row in rows
        )
        compute_delay_sum = sum(
            float(row["speaker_relabel_compute_delay_sum_sec"]) for row in rows
        )
        compute_delay_count = sum(
            float(row["speaker_relabel_compute_delay_count"]) for row in rows
        )
        source = source_by_configuration[configuration_id]
        baseline_source = source_by_configuration[baseline_id]
        summary_rows.append(
            {
                "schema_version": "h2-boundary-correction-summary.v1",
                "configuration_id": configuration_id,
                "boundary_correction_ms": correction_ms,
                "selected_by_development_receipt": configuration_id == selected[0],
                "evidence_split": "development",
                "case_count": len(rows),
                "word_applicable_case_count": len(applicable),
                "paired_word_count": int(word_den),
                "baseline_correct_word_count": sum(
                    int(row["baseline_correct_word_count"]) for row in applicable
                ),
                "candidate_correct_word_count": int(word_num),
                "final_word_speaker_label_accuracy": (
                    word_num / word_den if word_den > 0 else None
                ),
                "final_word_speaker_label_accuracy_ci_lower_95": word_low,
                "final_word_speaker_label_accuracy_ci_upper_95": word_high,
                "changed_speaker_word_count_vs_0ms": sum(
                    int(row["changed_speaker_word_count_vs_0ms"]) for row in applicable
                ),
                "repaired_word_count_vs_0ms": int(repaired_total),
                "repaired_word_count_ci_lower_95": repaired_low,
                "repaired_word_count_ci_upper_95": repaired_high,
                "harmed_word_count_vs_0ms": int(harmed_total),
                "harmed_word_count_ci_lower_95": harmed_low,
                "harmed_word_count_ci_upper_95": harmed_high,
                "wrong_to_other_wrong_word_count_vs_0ms": sum(
                    int(row["wrong_to_other_wrong_word_count_vs_0ms"])
                    for row in applicable
                ),
                "net_repaired_minus_harmed_words_vs_0ms": int(
                    repaired_total - harmed_total
                ),
                "initially_previous_speaker_word_count_0ms": sum(
                    int(row["initially_previous_speaker_word_count_0ms"])
                    for row in applicable
                ),
                "repaired_from_previous_speaker_word_count_vs_0ms": sum(
                    int(row["repaired_from_previous_speaker_word_count_vs_0ms"])
                    for row in applicable
                ),
                "initially_previous_speaker_word_time_status": "UNSUPPORTED_NO_REFERENCE_WORD_TIMESTAMPS",
                "initially_previous_speaker_word_time_sec": None,
                "correct_transcribed_attributed_word_rate": (
                    correct_num / correct_den if correct_den > 0 else None
                ),
                "boundary_delay_sec": (
                    boundary_num / boundary_den if boundary_den > 0 else None
                ),
                "speaker_relabel_revision_count": sum(
                    float(row["speaker_relabel_revision_count"]) for row in rows
                ),
                "mean_speaker_relabel_audio_delay_sec": (
                    audio_delay_sum / audio_delay_count
                    if audio_delay_count > 0
                    else None
                ),
                "mean_speaker_relabel_compute_delay_sec": (
                    compute_delay_sum / compute_delay_count
                    if compute_delay_count > 0
                    else None
                ),
                "transcript_revision_count": sum(
                    float(row.get("transcript_revision_count") or 0.0) for row in rows
                ),
                "retroactive_correction_count": sum(
                    float(row.get("retroactive_correction_count") or 0.0)
                    for row in rows
                ),
                "final_transcript_stability": (
                    final_num / final_den if final_den > 0 else None
                ),
                "wrong_name_dwell_sec": sum(
                    float(row.get("wrong_name_dwell_sec") or 0.0) for row in rows
                ),
                "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "resampling_unit": "multi-membership global-speaker block",
                "source_job_id": source["job_id"],
                "source_result_sha256": source["result_sha256"],
                "baseline_job_id": baseline_source["job_id"],
                "baseline_result_sha256": baseline_source["result_sha256"],
            }
        )

    provenance = {
        "schema_version": "h2-boundary-correction-provenance.v1",
        "status": "VALID",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "packaged_controller_state_sha256": _sha256(source_payloads[state_name]),
        "derivation_script_sha256": _sha256(Path(__file__).read_bytes()),
        "frozen_word_alignment_module": str(
            (TOOL_ROOT / "app/full_pipeline_evaluation/worker.py").resolve()
        ),
        "frozen_word_alignment_module_sha256": _sha256(
            (TOOL_ROOT / "app/full_pipeline_evaluation/worker.py").read_bytes()
        ),
        "development_only": True,
        "evaluation_material_inspected": False,
        "post_hoc_metrics_used_for_frozen_selection": False,
        "scientific_runtime_or_policy_changed": False,
        "source_case_sets_and_order_identical": True,
        "source_reference_payloads_identical": True,
        "paired_lexical_alignments_required_identical": True,
        "only_result_affecting_axis_varied": "boundary_correction_ms",
        "baseline_configuration_id": baseline_id,
        "selected_boundary_configuration": selected[0],
        "selection_receipt_sha256": _sha256(axis_payload),
        "exact_word_time_status": "UNSUPPORTED_NO_REFERENCE_WORD_TIMESTAMPS",
        "exact_word_time_reason": "The frozen references contain segment-level timing but not per-word timing; counts are exact under the frozen lexical alignment, while seconds are intentionally not fabricated.",
        "speaker_relabel_audio_delay_definition": "Audio-evidence time between a span speaker assignment appearing in one transcript-revision snapshot and its next changed speaker assignment.",
        "speaker_relabel_compute_delay_definition": "Monotonic emitted-event time between the same two UI-visible assignment states; this is measured compute/event dwell, not speech evidence.",
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_base_seed": BOOTSTRAP_SEED,
        "bootstrap_method": "multi-membership global-speaker block bootstrap",
        "summary_row_count": len(summary_rows),
        "case_pair_row_count": len(case_rows),
        "sources": source_rows,
    }

    def display(value: object, digits: int = 4) -> str:
        number = _number(value)
        return "unsupported" if number is None else f"{number:.{digits}f}"

    guide = [
        "# H2 boundary-correction diagnostics",
        "",
        "This post-run, checksum-bound development analysis pairs the same cases and the same frozen lexical alignment across 0, 250, 500, 750, and 1,000 ms boundary-correction windows. It does not rerun inference, inspect held-out evaluation material, or change the frozen selection.",
        "",
        "A repaired word is wrong at 0 ms and correct for the candidate; a harmed word is correct at 0 ms and wrong for the candidate. `Initially previous speaker` counts the aligned words whose 0 ms label equals the immediately preceding distinct reference speaker. Exact word-time in seconds is explicitly unsupported because the references have segment timestamps but no reference word timestamps.",
        "",
        "Speaker-relabel audio delay and compute delay come from consecutive UI-visible transcript-revision snapshots and are reported separately. Final stability is exact agreement between the last replayed event snapshot and the exported final transcript structure.",
        "",
        f"Frozen selected boundary configuration: `{selected[0]}`.",
        "",
        "| Correction | Selected | Word accuracy | Repaired | Harmed | Net | Initially previous | Repaired from previous | Boundary delay (s) | Relabel revisions | Relabel audio delay (s) | Final stability | Wrong-name dwell (s) |",
        "|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        guide.append(
            "| "
            + " | ".join(
                (
                    str(row["boundary_correction_ms"]),
                    "yes" if row["selected_by_development_receipt"] else "no",
                    display(row["final_word_speaker_label_accuracy"]),
                    str(row["repaired_word_count_vs_0ms"]),
                    str(row["harmed_word_count_vs_0ms"]),
                    str(row["net_repaired_minus_harmed_words_vs_0ms"]),
                    str(row["initially_previous_speaker_word_count_0ms"]),
                    str(row["repaired_from_previous_speaker_word_count_vs_0ms"]),
                    display(row["boundary_delay_sec"]),
                    str(int(float(row["speaker_relabel_revision_count"]))),
                    display(row["mean_speaker_relabel_audio_delay_sec"]),
                    display(row["final_transcript_stability"]),
                    display(row["wrong_name_dwell_sec"]),
                )
            )
            + " |"
        )
    guide.extend(
        (
            "",
            "The summary CSV is authoritative for aggregate comparisons. The case-pair CSV preserves every paired sufficient statistic and unsupported reason. Confidence intervals resample complete global-speaker blocks 2,000 times.",
            "",
        )
    )
    payloads = {
        REQUIRED_BOUNDARY_MEMBERS[0]: _csv_payload(
            summary_rows, BOUNDARY_SUMMARY_FIELDS
        ),
        REQUIRED_BOUNDARY_MEMBERS[1]: _csv_payload(case_rows, BOUNDARY_CASE_FIELDS),
        REQUIRED_BOUNDARY_MEMBERS[2]: "\n".join(guide).encode("utf-8"),
        REQUIRED_BOUNDARY_MEMBERS[3]: _canonical_json(provenance),
    }
    return payloads, provenance


def _science_source_table_payloads(
    source_payloads: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, object]]:
    state_name = "controller/program_state.json"
    manifest_name = "protocol/job_manifest.json"
    if state_name not in source_payloads or manifest_name not in source_payloads:
        raise ValueError("native package lacks science-table controller bindings")
    state = json.loads(source_payloads[state_name])
    manifest = json.loads(source_payloads[manifest_name])
    if not isinstance(state, Mapping) or not isinstance(manifest, Mapping):
        raise ValueError("science-table controller bindings are invalid")
    if manifest.get("job_manifest_sha256") != state.get("job_manifest_sha256"):
        raise ValueError("science-table job manifest identity differs")
    jobs = manifest.get("jobs")
    state_jobs = state.get("jobs")
    if not isinstance(jobs, list) or not isinstance(state_jobs, Mapping):
        raise ValueError("science-table job/state collections are invalid")
    requirements = {
        "policy_replay": (
            "open_set_policy_frontier.csv",
            "identity_hubness.csv",
        ),
        "integrated_enrollment": (
            "integrated_enrollment_matrix.csv",
            "integrated_enrollment_qc_events.csv",
            "integrated_enrollment_hubness.csv",
            "integrated_enrollment_selected_cell.csv",
        ),
    }
    results_root = Path(str(state.get("results_root") or "")).resolve(strict=True)
    output: dict[str, bytes] = {}
    provenance_rows: list[dict[str, object]] = []
    for job_kind, filenames in requirements.items():
        matches = [
            row
            for row in jobs
            if isinstance(row, Mapping) and row.get("job_kind") == job_kind
        ]
        if len(matches) != 1:
            raise ValueError(f"exactly one {job_kind} science job is required")
        job = matches[0]
        job_id = str(job.get("job_id") or "")
        if job.get("development_only") is not True:
            raise ValueError(f"science source job is not development-only: {job_id}")
        state_row = state_jobs.get(job_id)
        if not isinstance(state_row, Mapping) or state_row.get("state") != "COMPLETE":
            raise ValueError(f"science source job is not complete: {job_id}")
        result_path = Path(str(state_row.get("result_path") or "")).resolve(strict=True)
        try:
            result_path.relative_to(results_root)
        except ValueError as exc:
            raise ValueError(f"science result escaped results root: {job_id}") from exc
        result_sha = str(state_row.get("result_sha256") or "")
        if len(result_sha) != 64 or _sha256(result_path.read_bytes()) != result_sha:
            raise ValueError(f"science source result checksum differs: {job_id}")
        document = json.loads(result_path.read_bytes())
        if document.get("evaluation_material_inspected") is not False:
            raise ValueError(
                f"science source job does not preserve the evaluation firewall: {job_id}"
            )
        artifact_manifest = document.get("artifact_manifest")
        if not isinstance(artifact_manifest, list):
            raise ValueError(f"science source lacks artifact manifest: {job_id}")
        artifacts = {
            str(row.get("path") or ""): row
            for row in artifact_manifest
            if isinstance(row, Mapping) and row.get("path")
        }
        if any(filename not in artifacts for filename in filenames):
            raise ValueError(f"science source table membership differs: {job_id}")
        for filename in filenames:
            raw = artifacts[filename]
            table_path = (result_path.parent / filename).resolve(strict=True)
            if table_path.parent != result_path.parent:
                raise ValueError(
                    f"science source table escaped artifact root: {filename}"
                )
            payload = table_path.read_bytes()
            rows = _csv_rows(payload)
            if (
                raw.get("sha256") != _sha256(payload)
                or raw.get("row_count") != len(rows)
                or not rows
            ):
                raise ValueError(
                    f"science source table checksum/row count differs: {filename}"
                )
            member = f"supplements/source_science/{filename}"
            output[member] = payload
            provenance_rows.append(
                {
                    "member": member,
                    "source_job_id": job_id,
                    "source_job_kind": job_kind,
                    "source_result_path": str(result_path),
                    "source_result_sha256": result_sha,
                    "source_relative_path": filename,
                    "source_sha256": raw["sha256"],
                    "row_count": len(rows),
                    "development_only": bool(job.get("development_only")),
                    "evaluation_material_inspected": document.get(
                        "evaluation_material_inspected"
                    ),
                }
            )
    expected_members = set(REQUIRED_SCIENCE_TABLE_MEMBERS[:-1])
    if set(output) != expected_members:
        raise ValueError("science source supplement membership differs")
    provenance = {
        "schema_version": "h2-science-source-table-provenance.v1",
        "status": "VALID",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "scientific_results_or_selection_changed": False,
        "tables_are_byte_exact_source_artifacts": True,
        "development_and_heldout_evidence_pooled": False,
        "member_count": len(output),
        "members": provenance_rows,
    }
    output[REQUIRED_SCIENCE_TABLE_MEMBERS[-1]] = _canonical_json(provenance)
    return output, provenance


def _axis_selection_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], list[dict[str, object]]]:
    state_name = "controller/program_state.json"
    if state_name not in source_payloads:
        raise ValueError("native package lacks controller/program_state.json")
    state = json.loads(source_payloads[state_name])
    declared = state.get("axis_selections")
    if not isinstance(declared, Mapping) or not declared:
        raise ValueError("final controller state lacks axis-selection decisions")
    output: dict[str, bytes] = {}
    rows: list[dict[str, object]] = []
    root = (workspace / "axis_selections").resolve(strict=True)
    for key, raw in sorted(declared.items(), key=lambda item: str(item[0])):
        if not isinstance(raw, Mapping):
            raise ValueError(f"invalid axis-selection binding: {key}")
        path = (root / f"{key}.json").resolve(strict=True)
        if path.parent != root:
            raise ValueError(f"axis-selection path escaped workspace: {key}")
        payload = path.read_bytes()
        expected = str(raw.get("decision_sha256") or "")
        if not expected or _sha256(payload) != expected:
            raise ValueError(f"axis-selection checksum differs: {key}")
        member = f"controller/axis_selections/{path.name}"
        output[member] = payload
        rows.append(
            {
                "axis": str(key),
                "member": member,
                "sha256": expected,
                "bytes": len(payload),
            }
        )
    return output, rows


def _source_controller_binding(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> dict[str, object]:
    state_name = "controller/program_state.json"
    if state_name not in source_payloads:
        raise ValueError("native package lacks controller/program_state.json")
    packaged = json.loads(source_payloads[state_name])
    current_path = workspace / "program_state.json"
    if not current_path.is_file():
        raise ValueError("active workspace lacks program_state.json")
    current = json.loads(current_path.read_bytes())
    immutable_fields = (
        "program_id",
        "protocol_id",
        "protocol_sha256",
        "job_manifest_sha256",
        "workspace",
        "results_root",
        "summary_root",
    )
    mismatches = [
        field
        for field in immutable_fields
        if packaged.get(field) != current.get(field) or packaged.get(field) is None
    ]
    if mismatches:
        raise ValueError(
            "native package/controller workspace binding differs: "
            + ", ".join(mismatches)
        )
    packaged_axes = packaged.get("axis_selections")
    current_axes = current.get("axis_selections")
    if not isinstance(packaged_axes, Mapping) or not isinstance(current_axes, Mapping):
        raise ValueError("package/workspace axis-selection binding is absent")
    packaged_hashes = {
        str(key): str(value.get("decision_sha256") or "")
        for key, value in packaged_axes.items()
        if isinstance(value, Mapping)
    }
    current_hashes = {
        str(key): str(value.get("decision_sha256") or "")
        for key, value in current_axes.items()
        if isinstance(value, Mapping)
    }
    if (
        not packaged_hashes
        or packaged_hashes != current_hashes
        or not all(packaged_hashes.values())
    ):
        raise ValueError("native package/controller axis-selection hashes differ")
    return {
        "immutable_fields": {field: packaged[field] for field in immutable_fields},
        "axis_selection_sha256s": packaged_hashes,
        "packaged_program_status": packaged.get("status"),
        "current_program_status": current.get("status"),
    }


def _selector_correction_expected_binding(
    manifest: Mapping[str, object], manifest_file_sha256: str
) -> dict[str, object]:
    raw_bindings = manifest.get("file_bindings")
    if not isinstance(raw_bindings, list):
        raise ValueError("selector correction manifest lacks file bindings")
    selected_labels = {
        "correction_bootstrap",
        "patched_controller",
        "patched_controller_tests",
        "staging_validation",
        "pre_freeze_conflict_audit",
    }
    selected_hashes = {
        str(row.get("label")): str(row.get("sha256"))
        for row in raw_bindings
        if isinstance(row, Mapping) and row.get("label") in selected_labels
    }
    if set(selected_hashes) != selected_labels or not all(selected_hashes.values()):
        raise ValueError("selector correction selection-source bindings differ")
    return {
        "schema_version": "h2-prefreeze-selector-correction.v1",
        "activation_manifest_identity_sha256": manifest.get(
            "activation_manifest_sha256"
        ),
        "activation_manifest_file_sha256": manifest_file_sha256,
        "correction_source_sha256s": dict(sorted(selected_hashes.items())),
        "activation_boundary": "DEVELOPMENT_PHASE5_BEFORE_FREEZE_AND_HELDOUT",
        "evaluation_material_inspected": False,
        "scientific_choice_changed": False,
        "qualified_selection_preserved": "R3_EXACT_WINDOW_EMBEDDING_REUSE",
    }


def _selector_correction_provenance_document(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    """Validate and summarize the checksum-bound pre-freeze controller handoff."""

    required_without_provenance = REQUIRED_SELECTOR_CORRECTION_MEMBERS[:-1]
    missing = [name for name in required_without_provenance if name not in payloads]
    if missing:
        raise ValueError(
            "selector correction reproduction sources are missing: "
            + ", ".join(missing)
        )
    manifest_payload = payloads[SELECTOR_CORRECTION_MANIFEST_MEMBER]
    manifest = _storage_json_object(
        manifest_payload, label=SELECTOR_CORRECTION_MANIFEST_MEMBER
    )
    unsigned_manifest = dict(manifest)
    manifest_identity = unsigned_manifest.pop("activation_manifest_sha256", None)
    if (
        manifest.get("schema_version") != "h2-prefreeze-selector-correction.v1"
        or manifest_identity != _sha256(_storage_canonical_bytes(unsigned_manifest))
        or manifest.get("scientific_choice_changed") is not False
        or manifest.get("evaluation_material_inspected") is not False
        or manifest.get("qualified_selection_preserved")
        != "R3_EXACT_WINDOW_EMBEDDING_REUSE"
    ):
        raise ValueError("selector correction activation manifest differs")
    manifest_file_sha256 = _sha256(manifest_payload)

    receipt_payload = payloads[SELECTOR_CORRECTION_RECEIPT_MEMBER]
    receipt = _storage_json_object(
        receipt_payload, label=SELECTOR_CORRECTION_RECEIPT_MEMBER
    )
    unsigned_receipt = dict(receipt)
    receipt_identity = unsigned_receipt.pop("receipt_sha256", None)
    if (
        receipt.get("schema_version")
        != "h2-prefreeze-selector-correction-activation.v1"
        or receipt_identity != _sha256(_storage_canonical_bytes(unsigned_receipt))
        or receipt.get("activation_manifest_identity_sha256") != manifest_identity
        or receipt.get("activation_manifest_file_sha256") != manifest_file_sha256
        or receipt.get("heldout_was_unopened_at_first_activation") is not True
        or receipt.get("scientific_choice_changed") is not False
        or receipt.get("orchestration_defect_corrected") is not True
        or not str(receipt.get("activated_at_utc") or "")
    ):
        raise ValueError("selector correction activation receipt differs")

    native_members = {
        "state": "controller/program_state.json",
        "protocol": "protocol/protocol_manifest.json",
        "jobs": "protocol/job_manifest.json",
        "runtime": "protocol/runtime_implementation_identity.json",
        "freeze": "protocol/frozen_policy.json",
    }
    missing_native = [
        name for name in native_members.values() if name not in payloads
    ]
    if missing_native:
        raise ValueError(
            "native package lacks selector correction bindings: "
            + ", ".join(missing_native)
        )
    state = _storage_json_object(payloads[native_members["state"]], label="state")
    protocol = _storage_json_object(
        payloads[native_members["protocol"]], label="protocol"
    )
    runtime = _storage_json_object(
        payloads[native_members["runtime"]], label="runtime identity"
    )
    freeze = _storage_json_object(payloads[native_members["freeze"]], label="freeze")
    expected_program = manifest.get("program_bindings")
    if not isinstance(expected_program, Mapping):
        raise ValueError("selector correction program bindings are missing")
    actual_program = {
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "runtime_implementation_identity_sha256": runtime.get("identity_sha256"),
    }
    if (
        dict(expected_program) != actual_program
        or protocol.get("protocol_id") != actual_program["protocol_id"]
        or protocol.get("protocol_sha256") != actual_program["protocol_sha256"]
        or receipt.get("workspace") != manifest.get("expected_workspace")
        or receipt.get("workspace") != state.get("workspace")
    ):
        raise ValueError("selector correction program identity binding differs")

    raw_bindings = manifest.get("file_bindings")
    if not isinstance(raw_bindings, list):
        raise ValueError("selector correction file bindings are missing")
    bindings: dict[str, Mapping[str, object]] = {}
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            raise ValueError("selector correction file binding is invalid")
        label = str(raw.get("label") or "")
        if not label or label in bindings:
            raise ValueError("selector correction file-binding labels differ")
        bindings[label] = raw
    if set(bindings) != set(SELECTOR_CORRECTION_BINDING_MEMBERS):
        raise ValueError("selector correction file-binding membership differs")
    binding_rows: list[dict[str, object]] = []
    for label, member in sorted(SELECTOR_CORRECTION_BINDING_MEMBERS.items()):
        binding = bindings[label]
        payload = payloads.get(member)
        if payload is None or binding.get("sha256") != _sha256(payload):
            raise ValueError(f"selector correction source checksum differs: {label}")
        binding_rows.append(
            {
                "label": label,
                "member": member,
                "sha256": _sha256(payload),
                "bytes": len(payload),
            }
        )

    required_jobs = manifest.get("required_completed_jobs")
    state_jobs = state.get("jobs")
    if not isinstance(required_jobs, Mapping) or not isinstance(state_jobs, Mapping):
        raise ValueError("selector correction prerequisite-job bindings are missing")
    for job_id, result_sha256 in required_jobs.items():
        row = state_jobs.get(str(job_id))
        if (
            not isinstance(row, Mapping)
            or str(row.get("state") or "").upper() != "COMPLETE"
            or row.get("result_sha256") != result_sha256
        ):
            raise ValueError(
                f"selector correction prerequisite result differs: {job_id}"
            )

    freeze_unsigned = dict(freeze)
    freeze_identity = freeze_unsigned.pop("freeze_identity_sha256", None)
    selected_runtime = freeze.get("selected_runtime")
    expected_selection_binding = _selector_correction_expected_binding(
        manifest, manifest_file_sha256
    )
    if (
        freeze_identity != _sha256(_storage_canonical_bytes(freeze_unsigned))
        or freeze.get("protocol_id") != actual_program["protocol_id"]
        or freeze.get("protocol_sha256") != actual_program["protocol_sha256"]
        or freeze.get("job_manifest_sha256") != actual_program["job_manifest_sha256"]
        or freeze.get("runtime_implementation_identity_sha256")
        != actual_program["runtime_implementation_identity_sha256"]
        or freeze.get("evaluation_material_inspected") is not False
        or not isinstance(selected_runtime, Mapping)
        or selected_runtime.get("pre_freeze_selector_correction")
        != expected_selection_binding
    ):
        raise ValueError("frozen policy does not bind the selector correction")

    source_rows = [
        {
            "member": name,
            "sha256": _sha256(payloads[name]),
            "bytes": len(payloads[name]),
        }
        for name in sorted(required_without_provenance)
    ]
    return {
        "schema_version": "h2-selector-correction-provenance.v1",
        "status": "VALID",
        "activation_manifest_identity_sha256": manifest_identity,
        "activation_manifest_file_sha256": manifest_file_sha256,
        "activation_receipt_sha256": receipt_identity,
        "activated_at_utc": receipt.get("activated_at_utc"),
        "freeze_identity_sha256": freeze_identity,
        "qualified_selection_preserved": "R3_EXACT_WINDOW_EMBEDDING_REUSE",
        "heldout_was_unopened_at_first_activation": True,
        "evaluation_material_inspected": False,
        "scientific_choice_changed": False,
        "orchestration_defect_corrected": True,
        "prepared_inference_runtime_identity_preserved": True,
        "program_bindings": actual_program,
        "selection_binding": expected_selection_binding,
        "file_bindings": binding_rows,
        "source_members": source_rows,
    }


def _selector_correction_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    staging = (
        workspace / "diagnostics/pre_freeze_selector_fix_staging"
    ).resolve(strict=True)
    sources = {
        SELECTOR_CORRECTION_RECEIPT_MEMBER: workspace
        / "diagnostics/pre_freeze_selector_correction_activation.json",
        SELECTOR_CORRECTION_MANIFEST_MEMBER: staging / "ACTIVATION_MANIFEST.json",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[2]: staging / "README.md",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[3]: staging / "STAGING_VALIDATION.json",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[4]: workspace
        / "diagnostics/pre_freeze_redim_selection_conflict.audit.json",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[5]: staging
        / "h2_prefreeze_selector_correction_bootstrap.py",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[6]: staging / "controller.py.patched",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[7]: TOOL_ROOT
        / "app/h2_product_program/controller.py",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[8]: TOOL_ROOT
        / "scripts/h2_windows_atomic_retry_bootstrap.py",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[9]: staging
        / "test_h2_product_program_controller.py.patched",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[10]: staging
        / "test_prefreeze_selector_correction_bootstrap.py",
        REQUIRED_SELECTOR_CORRECTION_MEMBERS[11]: TOOL_ROOT
        / "scripts/h2_atomic_retry_child/sitecustomize.py",
    }
    output: dict[str, bytes] = {}
    for member, source in sources.items():
        if not source.is_file():
            raise ValueError(f"selector correction reproduction source is missing: {source}")
        output[member] = source.read_bytes()
    provenance = _selector_correction_provenance_document(
        {**source_payloads, **output}
    )
    output[SELECTOR_CORRECTION_PROVENANCE_MEMBER] = _canonical_json(provenance)
    return output, provenance


def _validate_selector_correction_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_SELECTOR_CORRECTION_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks selector correction provenance: "
            + ", ".join(missing)
        )
    observed = _storage_json_object(
        payloads[SELECTOR_CORRECTION_PROVENANCE_MEMBER],
        label=SELECTOR_CORRECTION_PROVENANCE_MEMBER,
    )
    expected = _selector_correction_provenance_document(payloads)
    if observed != expected:
        raise ValueError("selector correction provenance document differs")
    return expected


def _storage_canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _storage_json_object(payload: bytes, *, label: str) -> dict[str, object]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"storage reproducibility member is not an object: {label}")
    return value


def _validate_signed_storage_document(
    document: Mapping[str, object],
    *,
    schema_version: str,
    signature_key: str,
    label: str,
) -> None:
    if document.get("schema_version") != schema_version:
        raise ValueError(f"storage reproducibility schema differs: {label}")
    unsigned = dict(document)
    observed = unsigned.pop(signature_key, None)
    expected = _sha256(_storage_canonical_bytes(unsigned))
    if observed != expected:
        raise ValueError(f"storage reproducibility signature differs: {label}")


def _validated_windows_atomic_policy(
    payload: bytes, *, launcher_payload: bytes, child_policy_payload: bytes
) -> dict[str, object]:
    policy = _storage_json_object(payload, label=STORAGE_ATOMIC_POLICY_MEMBER)
    _validate_signed_storage_document(
        policy,
        schema_version="h2-windows-atomic-publication-policy.v1",
        signature_key="policy_sha256",
        label=STORAGE_ATOMIC_POLICY_MEMBER,
    )
    if (
        policy.get("launcher_sha256") != _sha256(launcher_payload)
        or policy.get("child_process_propagation") != "PYTHONPATH_sitecustomize"
        or policy.get("child_sitecustomize_sha256")
        != _sha256(child_policy_payload)
        or policy.get("scientific_inference_or_metric_change") is not False
        or policy.get("frozen_runtime_source_tree_change") is not False
        or policy.get("operation_scope") != "os.replace only"
        or policy.get("retryable_winerrors") != [5, 32, 33]
    ):
        raise ValueError("Windows atomic-publication policy boundary differs")
    delays = policy.get("retry_delays_sec")
    if (
        not isinstance(delays, list)
        or not delays
        or policy.get("maximum_added_wait_sec") != _stable_float_sum(delays)
    ):
        raise ValueError("Windows atomic-publication retry schedule differs")
    return policy


def _stable_float_sum(values: Sequence[object]) -> float:
    """Return a stable rounded sum without depending on test-only helpers."""

    return round(sum(float(value) for value in values), 9)


def _validated_windows_atomic_events(payload: bytes) -> dict[str, int]:
    rows: list[dict[str, object]] = []
    for line_number, raw in enumerate(payload.decode("utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(
                f"Windows atomic-publication event {line_number} is not an object"
            )
        if (
            value.get("schema_version") != "h2-windows-atomic-publication-event.v1"
            or value.get("status") not in {"RETRYING", "RECOVERED", "EXHAUSTED"}
            or not value.get("source")
            or not value.get("destination")
        ):
            raise ValueError(f"Windows atomic-publication event {line_number} differs")
        rows.append(value)
    return {
        "event_count": len(rows),
        "retrying_count": sum(row["status"] == "RETRYING" for row in rows),
        "recovered_count": sum(row["status"] == "RECOVERED" for row in rows),
        "exhausted_count": sum(row["status"] == "EXHAUSTED" for row in rows),
    }


def _validated_arm64_wheel_resolution_receipt(
    payload: bytes,
    *,
    requirements_payload: bytes,
    runtime_identity_payload: bytes,
    protocol_id: object,
) -> dict[str, object]:
    """Validate the compact, payload-free ARM64 wheel reproduction map."""

    label = STORAGE_ARM64_WHEEL_RECEIPT_MEMBER
    receipt = _storage_json_object(payload, label=label)
    _validate_signed_storage_document(
        receipt,
        schema_version="h2-arm64-wheel-resolution-receipt.v1",
        signature_key="receipt_sha256",
        label=label,
    )
    source = receipt.get("source")
    target = receipt.get("target")
    resolution = receipt.get("resolution")
    boundary = receipt.get("qualification_boundary")
    wheels = receipt.get("wheels")
    if not all(
        isinstance(value, Mapping) for value in (source, target, resolution, boundary)
    ) or not isinstance(wheels, list):
        raise ValueError("ARM64 wheel receipt structure differs")
    if (
        receipt.get("status") != "PASS_RESOLVED_EXACT_ARM64_BINARY_SET"
        or receipt.get("protocol_id") != protocol_id
        or receipt.get("scientific_runtime_or_configuration_edited") is not False
        or source.get("requirements_path")
        != "deployment/h2_arm64/requirements-linux-arm64.txt"
        or source.get("requirements_sha256") != _sha256(requirements_payload)
        or source.get("index_url") != "https://pypi.org/simple"
        or target.get("operating_system") != "Linux"
        or target.get("architecture") != "aarch64"
        or target.get("python_version") != "3.12"
        or target.get("implementation") != "cp"
        or target.get("abis") != ["cp312", "abi3", "none"]
        or target.get("platform_tags")
        != [
            "manylinux_2_28_aarch64",
            "manylinux2014_aarch64",
            "manylinux_2_17_aarch64",
            "any",
        ]
        or target.get("binary_only") is not True
        or resolution.get("all_direct_and_transitive_dependencies_resolved") is not True
        or resolution.get("source_distributions_used") is not False
        or resolution.get("model_assets_downloaded") is not False
        or resolution.get("wheels_retained_after_audit") is not False
        or boundary.get("wheel_availability_and_target_tag_resolution") != "PASS"
        or boundary.get("arm64_import_and_dynamic_link_validation")
        != "NOT_RUN_REQUIRES_ARM64_LINUX"
        or boundary.get("arm64_numerical_parity") != "NOT_RUN_REQUIRES_ARM64_LINUX"
        or boundary.get("raspberry_pi_hardware_ready_claimed") is not False
        or boundary.get("candidate_classification") != "PORT_REQUIRES_WORK"
    ):
        raise ValueError("ARM64 wheel receipt qualification boundary differs")

    runtime_identity = _storage_json_object(
        runtime_identity_payload, label=RUNTIME_IDENTITY_MEMBER
    )
    if runtime_identity.get(
        "schema_version"
    ) != "h2-runtime-implementation-identity.v2" or receipt.get(
        "runtime_implementation_sha256"
    ) != runtime_identity.get("identity_sha256"):
        raise ValueError("ARM64 wheel receipt runtime identity differs")

    direct_requirements = [
        line.strip()
        for line in requirements_payload.decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    declared_count = int(resolution.get("resolved_wheel_count") or 0)
    if (
        int(resolution.get("direct_pin_count") or 0) != len(direct_requirements)
        or declared_count != len(wheels)
        or declared_count < len(direct_requirements)
    ):
        raise ValueError("ARM64 wheel receipt dependency counts differ")

    filenames: set[str] = set()
    total_bytes = 0
    for raw in wheels:
        if not isinstance(raw, Mapping):
            raise ValueError("ARM64 wheel receipt row is invalid")
        filename = str(raw.get("filename") or "")
        digest = str(raw.get("sha256") or "")
        size = int(raw.get("bytes") or 0)
        if (
            not filename
            or PurePosixPath(filename).name != filename
            or not filename.casefold().endswith(".whl")
            or filename in filenames
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or size <= 0
        ):
            raise ValueError("ARM64 wheel receipt inventory differs")
        filenames.add(filename)
        total_bytes += size
    if total_bytes != int(resolution.get("resolved_logical_bytes") or 0):
        raise ValueError("ARM64 wheel receipt logical-byte total differs")
    return receipt


def _storage_source_file(path: Path, *, parent: Path | None = None) -> bytes:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError(f"storage reproducibility source is unavailable: {candidate}")
    resolved = candidate.resolve(strict=True)
    if parent is not None and resolved.parent != parent.resolve(strict=True):
        raise ValueError(
            f"storage reproducibility source escaped its directory: {path}"
        )
    return resolved.read_bytes()


def _queue_attempt_history_payload(
    workspace: Path,
) -> tuple[bytes, list[dict[str, object]], list[dict[str, object]]]:
    """Export every durable queue attempt without packaging mutable databases."""

    workspace = Path(workspace).resolve(strict=True)
    databases = sorted(
        (
            path.resolve(strict=True)
            for path in workspace.rglob("campaign.sqlite3")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: path.relative_to(workspace).as_posix(),
    )
    if not databases:
        raise ValueError("terminal storage snapshot contains no queue databases")

    rows: list[dict[str, object]] = []
    database_rows: list[dict[str, object]] = []
    for database in databases:
        try:
            relative = database.relative_to(workspace).as_posix()
        except ValueError as exc:
            raise ValueError(f"queue database escaped workspace: {database}") from exc
        before_sha = _sha256(database.read_bytes())
        connection = sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30.0
        )
        connection.row_factory = sqlite3.Row
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or str(integrity[0]).casefold() != "ok":
                raise ValueError(f"queue database integrity failed: {relative}")
            table_names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not {"attempts", "jobs"}.issubset(table_names):
                raise ValueError(f"queue database attempt schema differs: {relative}")
            query_rows = connection.execute(
                """
                SELECT a.job_id, a.attempt_number, a.state AS attempt_state,
                       a.attempt_path, a.started_at_utc, a.ended_at_utc, a.error,
                       j.state AS final_job_state
                FROM attempts AS a
                LEFT JOIN jobs AS j ON j.job_id = a.job_id
                ORDER BY a.job_id, a.attempt_number
                """
            ).fetchall()
        finally:
            connection.close()
        after_sha = _sha256(database.read_bytes())
        if before_sha != after_sha:
            raise ValueError(
                f"queue database changed during terminal snapshot: {relative}"
            )

        noncomplete_count = 0
        recovered_count = 0
        for raw in query_rows:
            attempt_path = Path(str(raw["attempt_path"] or "")).resolve()
            try:
                attempt_relative = attempt_path.relative_to(workspace).as_posix()
            except ValueError as exc:
                raise ValueError(
                    f"queue attempt path escaped workspace: {attempt_path}"
                ) from exc
            attempt_state = str(raw["attempt_state"] or "")
            final_job_state = str(raw["final_job_state"] or "")
            recovered = attempt_state != "complete" and final_job_state == "complete"
            noncomplete_count += int(attempt_state != "complete")
            recovered_count += int(recovered)
            rows.append(
                {
                    "schema_version": "h2-queue-attempt-history-row.v1",
                    "queue_database_relative_path": relative,
                    "queue_database_sha256": before_sha,
                    "job_id": str(raw["job_id"] or ""),
                    "attempt_number": int(raw["attempt_number"]),
                    "attempt_state": attempt_state,
                    "final_job_state": final_job_state,
                    "recovered_after_attempt": recovered,
                    "attempt_path_relative": attempt_relative,
                    "started_at_utc": str(raw["started_at_utc"] or ""),
                    "ended_at_utc": str(raw["ended_at_utc"] or ""),
                    "error": str(raw["error"] or ""),
                }
            )
        database_rows.append(
            {
                "relative_path": relative,
                "sha256": before_sha,
                "attempt_count": len(query_rows),
                "noncomplete_attempt_count": noncomplete_count,
                "recovered_noncomplete_attempt_count": recovered_count,
            }
        )
    payload = _csv_payload(rows, ATTEMPT_HISTORY_FIELDS)
    return payload, rows, database_rows


def _validated_h2_v17_task_registration(
    payload: bytes,
    *,
    installer_payload: bytes,
    terminal_state: Mapping[str, object],
) -> dict[str, object]:
    receipt = _storage_json_object(payload, label="scheduled_tasks_v17.json")
    expected_names = {
        "JustPeachy H2 v17 Supervisor",
        "JustPeachy H2 v17 Milestone Notifier",
        "JustPeachy H2 v17 Serial Resource Audit",
        "JustPeachy H2 v17 Post-Campaign Engineering",
        "JustPeachy H2 v17 Final Package Watcher",
    }
    expected_superseded = {
        "JustPeachy H2 v16 Supervisor",
        "JustPeachy H2 v16 Milestone Notifier",
        "JustPeachy H2 v16 Serial Resource Audit",
        "JustPeachy H2 v16 Final Package Watcher",
    }
    task_rows = receipt.get("tasks")
    if not isinstance(task_rows, list) or any(
        not isinstance(row, Mapping) for row in task_rows
    ):
        raise ValueError("scheduled-task receipt lacks task rows")
    task_names = {str(row.get("task_name") or "") for row in task_rows}
    workspace = str(terminal_state.get("workspace") or "")
    if (
        receipt.get("schema_version") != "h2-v17-scheduled-task-registration.v1"
        or receipt.get("status") != "APPLIED_AND_VERIFIED"
        or receipt.get("applied") is not True
        or receipt.get("workspace") != terminal_state.get("workspace")
        or receipt.get("results_root") != terminal_state.get("results_root")
        or receipt.get("summary_root") != terminal_state.get("summary_root")
        or receipt.get("scientific_configuration_changed") is not False
        or receipt.get("superseded_evidence_deleted") is not False
        or receipt.get("installer_sha256") != _sha256(installer_payload)
        or task_names != expected_names
        or set(receipt.get("superseded_v16_tasks_disabled") or ())
        != expected_superseded
        or not workspace
        or any(
            workspace.casefold() not in str(row.get("arguments") or "").casefold()
            or "h2_complete_product_pipeline_v16"
            in str(row.get("arguments") or "").casefold()
            or not str(row.get("executable") or "")
            .casefold()
            .endswith("powershell.exe")
            for row in task_rows
        )
    ):
        raise ValueError("H2 v17 scheduled-task registration binding differs")
    return receipt


def _storage_reproducibility_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    state_name = "controller/program_state.json"
    manifest_name = "protocol/job_manifest.json"
    if state_name not in source_payloads or manifest_name not in source_payloads:
        raise ValueError(
            "native package lacks controller/job-manifest storage bindings"
        )
    packaged_state = _storage_json_object(source_payloads[state_name], label=state_name)
    manifest = _storage_json_object(source_payloads[manifest_name], label=manifest_name)
    terminal_status = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
    workspace = Path(workspace).resolve(strict=True)
    terminal_state_payload = _storage_source_file(
        workspace / "program_state.json", parent=workspace
    )
    state = _storage_json_object(
        terminal_state_payload, label="terminal workspace program_state.json"
    )
    if state.get("status") != terminal_status:
        raise ValueError("storage snapshot requires the terminal controller state")
    if manifest.get("job_manifest_sha256") != state.get("job_manifest_sha256"):
        raise ValueError("storage snapshot job-manifest binding differs")
    immutable_fields = (
        "program_id",
        "protocol_id",
        "protocol_sha256",
        "job_manifest_sha256",
        "workspace",
        "results_root",
        "summary_root",
    )
    mismatches = [
        field
        for field in immutable_fields
        if packaged_state.get(field) != state.get(field) or state.get(field) is None
    ]
    if mismatches:
        raise ValueError(
            "native pre-publication/controller terminal binding differs: "
            + ", ".join(mismatches)
        )

    maintenance = (workspace / "storage_maintenance").resolve(strict=True)
    if maintenance.parent != workspace or maintenance.name != "storage_maintenance":
        raise ValueError("storage-maintenance root escaped the controller workspace")

    lifecycle_payload = _storage_source_file(
        maintenance / "artifact_lifecycle.json", parent=maintenance
    )
    forecast_payload = _storage_source_file(
        maintenance / "storage_forecast.json", parent=maintenance
    )
    guardian_payload = _storage_source_file(
        maintenance / "last_guardian_pass.json", parent=maintenance
    )
    task_registration_path = maintenance / "scheduled_tasks_v17.json"
    task_registration_payload = (
        _storage_source_file(task_registration_path, parent=maintenance)
        if task_registration_path.is_file()
        else None
    )
    arm64_wheel_payload = _storage_source_file(
        maintenance / "arm64_wheel_resolution_receipt.json", parent=maintenance
    )
    atomic_policy_payload = _storage_source_file(
        maintenance / "windows_atomic_publication_policy.json", parent=maintenance
    )
    atomic_events_path = (
        workspace / "logs" / "windows_atomic_publication_events.jsonl"
    ).resolve(strict=True)
    atomic_events_payload = _storage_source_file(
        atomic_events_path, parent=(workspace / "logs").resolve(strict=True)
    )
    atomic_bootstrap_payload = _storage_source_file(
        TOOL_ROOT / "scripts/h2_windows_atomic_retry_bootstrap.py"
    )
    atomic_child_payload = _storage_source_file(
        TOOL_ROOT / "scripts/h2_atomic_retry_child/sitecustomize.py"
    )
    task_installer_payload = _storage_source_file(
        TOOL_ROOT / "scripts/register_h2_v17_scheduled_tasks.ps1"
    )
    requirements_payload = _storage_source_file(
        TOOL_ROOT / "deployment/h2_arm64/requirements-linux-arm64.txt"
    )
    runtime_identity_payload = _storage_source_file(
        workspace / "runtime_implementation_identity.json", parent=workspace
    )
    lifecycle = _storage_json_object(lifecycle_payload, label="artifact_lifecycle")
    forecast = _storage_json_object(forecast_payload, label="storage_forecast")
    guardian = _storage_json_object(guardian_payload, label="last_guardian_pass")
    _validate_signed_storage_document(
        lifecycle,
        schema_version="h2-storage-artifact-lifecycle.v1",
        signature_key="lifecycle_sha256",
        label="artifact_lifecycle",
    )
    if lifecycle.get("campaign_status") != terminal_status:
        raise ValueError("storage lifecycle was not captured after terminal completion")
    if forecast.get("schema_version") != "h2-storage-forecast.v1":
        raise ValueError("storage forecast schema differs")
    if forecast.get("program_status") != terminal_status:
        raise ValueError("storage forecast was not captured after terminal completion")
    if guardian.get("schema_version") != "h2-storage-guardian-pass.v1":
        raise ValueError("terminal storage guardian pass schema differs")
    if guardian.get("artifact_lifecycle_sha256") != lifecycle.get("lifecycle_sha256"):
        raise ValueError("terminal guardian/lifecycle checksum binding differs")
    if guardian.get("forecast") != forecast:
        raise ValueError("terminal guardian/forecast snapshot differs")
    arm64_wheel_receipt = _validated_arm64_wheel_resolution_receipt(
        arm64_wheel_payload,
        requirements_payload=requirements_payload,
        runtime_identity_payload=runtime_identity_payload,
        protocol_id=state.get("protocol_id"),
    )
    atomic_policy = _validated_windows_atomic_policy(
        atomic_policy_payload,
        launcher_payload=atomic_bootstrap_payload,
        child_policy_payload=atomic_child_payload,
    )
    expected_atomic_log = str(
        workspace / "logs" / "windows_atomic_publication_events.jsonl"
    )
    if atomic_policy.get("event_log") != expected_atomic_log:
        raise ValueError("Windows atomic-publication event-log binding differs")
    atomic_event_summary = _validated_windows_atomic_events(atomic_events_payload)
    task_registration = (
        _validated_h2_v17_task_registration(
            task_registration_payload,
            installer_payload=task_installer_payload,
            terminal_state=state,
        )
        if task_registration_payload is not None
        else None
    )

    manifest_rows = manifest.get("jobs")
    if not isinstance(manifest_rows, list):
        raise ValueError("storage snapshot job manifest lacks jobs")
    expected_jobs = {
        str(row.get("job_id")): row
        for row in manifest_rows
        if isinstance(row, Mapping) and row.get("job_id")
    }
    logical_by_execution: dict[str, str] = {}
    heldout_name = "protocol/heldout_execution_manifest.json"
    if heldout_name in source_payloads:
        heldout = _storage_json_object(
            source_payloads[heldout_name], label=heldout_name
        )
        heldout_rows = heldout.get("jobs")
        if not isinstance(heldout_rows, list):
            raise ValueError("held-out storage binding lacks execution jobs")
        for raw in heldout_rows:
            if isinstance(raw, Mapping) and raw.get("job_id"):
                expected_jobs[str(raw["job_id"])] = raw
        mapping = heldout.get("logical_to_execution")
        if not isinstance(mapping, Mapping):
            raise ValueError("held-out storage binding lacks logical mapping")
        logical_by_execution = {
            str(execution): str(logical) for logical, execution in mapping.items()
        }
    heldout_execution_ids = set(logical_by_execution)

    dynamic_kinds = {
        "post_promotion_integration",
        "post_selection_mode_validation",
        "post_selection_paragraph_validation",
        "post_selection_resource_runtime",
    }
    expected_dynamic_logical = {
        str(row.get("job_id"))
        for row in manifest_rows
        if isinstance(row, Mapping) and row.get("job_kind") in dynamic_kinds
    }
    dynamic_payloads: dict[str, bytes] = {}
    dynamic_rows: list[dict[str, object]] = []
    dynamic_execution_ids: set[str] = set()
    dynamic_root = workspace / "dynamic_queues"
    if dynamic_root.exists():
        dynamic_root = dynamic_root.resolve(strict=True)
        for path in sorted(
            dynamic_root.glob("*/dynamic_execution.json"),
            key=lambda value: value.parent.name,
        ):
            if path.is_symlink() or path.parent.parent.resolve() != dynamic_root:
                raise ValueError(
                    f"dynamic execution manifest escaped workspace: {path}"
                )
            payload = path.resolve(strict=True).read_bytes()
            dynamic = _storage_json_object(payload, label=str(path))
            unsigned = dict(dynamic)
            observed = unsigned.pop("dynamic_execution_sha256", None)
            if (
                dynamic.get("schema_version") != "h2-dynamic-development-execution.v1"
                or observed != _sha256(_storage_canonical_bytes(unsigned))
                or dynamic.get("split") != "development"
                or dynamic.get("evaluation_material_inspected") is not False
            ):
                raise ValueError(f"dynamic execution storage binding differs: {path}")
            logical_id = str(dynamic.get("logical_job_id") or "")
            logical_job = expected_jobs.get(logical_id)
            execution_job = dynamic.get("execution_job")
            if (
                logical_id not in expected_dynamic_logical
                or logical_job is None
                or not isinstance(execution_job, Mapping)
                or dynamic.get("logical_job_identity_sha256")
                != logical_job.get("identity_sha256")
            ):
                raise ValueError(f"dynamic execution logical binding differs: {path}")
            execution_id = str(execution_job.get("job_id") or "")
            if not execution_id or execution_id in expected_jobs:
                raise ValueError(f"dynamic execution identity is duplicate: {path}")
            expected_jobs[execution_id] = execution_job
            logical_by_execution[execution_id] = logical_id
            dynamic_execution_ids.add(execution_id)
            member = f"{STORAGE_DYNAMIC_PREFIX}{_safe_name(path.parent.name)}.json"
            dynamic_payloads[member] = payload
            dynamic_rows.append(
                {
                    "member": member,
                    "logical_job_id": logical_id,
                    "execution_job_id": execution_id,
                    "dynamic_execution_sha256": observed,
                }
            )
    discovered_dynamic = {str(row["logical_job_id"]) for row in dynamic_rows}
    if discovered_dynamic != expected_dynamic_logical:
        missing_dynamic = sorted(expected_dynamic_logical - discovered_dynamic)
        extra_dynamic = sorted(discovered_dynamic - expected_dynamic_logical)
        raise ValueError(
            "terminal dynamic execution storage inventory differs; "
            f"missing={missing_dynamic}; extra={extra_dynamic}"
        )

    state_jobs = state.get("jobs")
    if not isinstance(state_jobs, Mapping):
        raise ValueError("terminal controller state lacks job results")
    results_root = Path(str(state.get("results_root") or "")).resolve()
    if not results_root.is_absolute():
        raise ValueError("terminal controller results root is not absolute")

    output: dict[str, bytes] = {
        REQUIRED_STORAGE_MEMBERS[0]: lifecycle_payload,
        REQUIRED_STORAGE_MEMBERS[1]: forecast_payload,
        REQUIRED_STORAGE_MEMBERS[2]: guardian_payload,
        STORAGE_ARM64_WHEEL_RECEIPT_MEMBER: arm64_wheel_payload,
        STORAGE_ATOMIC_POLICY_MEMBER: atomic_policy_payload,
        STORAGE_ATOMIC_EVENTS_MEMBER: atomic_events_payload,
        REQUIRED_STORAGE_MEMBERS[-2]: terminal_state_payload,
        **dynamic_payloads,
    }
    if task_registration_payload is not None:
        output[STORAGE_TASK_REGISTRATION_MEMBER] = task_registration_payload
    attempt_history_payload, attempt_rows, attempt_database_rows = (
        _queue_attempt_history_payload(workspace)
    )
    output[STORAGE_ATTEMPT_HISTORY_MEMBER] = attempt_history_payload
    receipt_root = (maintenance / "receipts").resolve(strict=True)
    pending = sorted(receipt_root.glob("*.pending.json"))
    if pending:
        raise ValueError("terminal storage snapshot contains pending prune receipts")
    receipt_rows: list[dict[str, object]] = []
    pruned_logical_bytes = 0
    scope_counts: dict[str, int] = defaultdict(int)
    for path in sorted(receipt_root.glob("*.json"), key=lambda value: value.name):
        payload = _storage_source_file(path, parent=receipt_root)
        receipt = _storage_json_object(payload, label=path.name)
        _validate_signed_storage_document(
            receipt,
            schema_version="h2-storage-prune-receipt.v1",
            signature_key="receipt_sha256",
            label=path.name,
        )
        pending_receipt = receipt.get("validation_receipt")
        if not isinstance(pending_receipt, Mapping):
            raise ValueError(f"prune receipt lacks validation binding: {path.name}")
        _validate_signed_storage_document(
            pending_receipt,
            schema_version="h2-storage-prune-pending.v1",
            signature_key="pending_sha256",
            label=f"{path.name}:validation_receipt",
        )
        if pending_receipt.get("workspace") != str(workspace):
            raise ValueError(f"prune receipt belongs to another workspace: {path.name}")
        queue_completion = pending_receipt.get("queue_completion")
        retained = pending_receipt.get("retained_sealed_result")
        regenerable = pending_receipt.get("regenerable_source")
        receipt_job = pending_receipt.get("job")
        if not all(
            isinstance(value, Mapping)
            for value in (queue_completion, retained, regenerable, receipt_job)
        ):
            raise ValueError(f"prune receipt has incomplete bindings: {path.name}")
        result_sha = str(queue_completion.get("result_sha256") or "")
        if not result_sha or retained.get("checksums_sha256") != result_sha:
            raise ValueError(f"prune receipt result checksum differs: {path.name}")
        retained_root = Path(str(retained.get("absolute_path") or "")).resolve()
        try:
            retained_root.relative_to(results_root)
        except ValueError as exc:
            raise ValueError(
                f"prune receipt result escaped controller results: {path.name}"
            ) from exc
        job_id = str(receipt_job.get("job_id") or "")
        expected_job = expected_jobs.get(job_id)
        if expected_job is not None:
            if receipt_job.get("identity_sha256") != expected_job.get(
                "identity_sha256"
            ):
                raise ValueError(f"prune receipt job identity differs: {path.name}")
            scope = (
                "heldout_execution"
                if job_id in heldout_execution_ids
                else (
                    "dynamic_development_execution"
                    if job_id in dynamic_execution_ids
                    else "frozen_job_manifest"
                )
            )
            state_id = logical_by_execution.get(job_id, job_id)
            state_row = state_jobs.get(state_id)
            if isinstance(state_row, Mapping):
                recorded_sha = str(state_row.get("result_sha256") or "")
                if recorded_sha and recorded_sha != result_sha:
                    raise ValueError(
                        f"prune receipt/controller result checksum differs: {path.name}"
                    )
        elif job_id.startswith("h2smoke_") and str(
            pending_receipt.get("queue_database_relative_path") or ""
        ).startswith("bounded_timing_smoke_queue/"):
            scope = "bounded_preflight_smoke"
        else:
            raise ValueError(
                f"prune receipt job is not frozen or bounded smoke: {path.name}"
            )
        logical_bytes = int(regenerable.get("logical_bytes") or 0)
        if logical_bytes <= 0:
            raise ValueError(
                f"prune receipt has no logical-byte inventory: {path.name}"
            )
        pruned_logical_bytes += logical_bytes
        scope_counts[scope] += 1
        member = f"{STORAGE_PRUNE_PREFIX}{_safe_name(path.name)}"
        output[member] = payload
        receipt_rows.append(
            {
                "member": member,
                "job_id": job_id,
                "scope": scope,
                "result_sha256": result_sha,
                "logical_bytes_removed": logical_bytes,
                "receipt_sha256": receipt.get("receipt_sha256"),
            }
        )
    if not receipt_rows:
        raise ValueError("terminal storage snapshot contains no prune receipts")

    compression_rows: list[dict[str, object]] = []
    compression_root = maintenance / "compression_receipts"
    if compression_root.exists():
        compression_root = compression_root.resolve(strict=True)
        for path in sorted(
            compression_root.glob("*.json"), key=lambda value: value.name
        ):
            payload = _storage_source_file(path, parent=compression_root)
            receipt = _storage_json_object(payload, label=path.name)
            _validate_signed_storage_document(
                receipt,
                schema_version="h2-storage-compression-receipt.v1",
                signature_key="receipt_sha256",
                label=path.name,
            )
            if receipt.get("workspace") != str(workspace):
                raise ValueError(
                    f"compression receipt belongs to another workspace: {path.name}"
                )
            boundary = receipt.get("scientific_boundary")
            if not isinstance(boundary, Mapping) or (
                boundary.get("serial_resource_measurements_excluded") is not True
                or boundary.get("frozen_runtime_identity_affected") is not False
            ):
                raise ValueError(
                    f"compression scientific boundary differs: {path.name}"
                )
            member = f"{STORAGE_COMPRESSION_PREFIX}{_safe_name(path.name)}"
            output[member] = payload
            compression_rows.append(
                {
                    "member": member,
                    "job_id": str((receipt.get("job") or {}).get("job_id") or ""),
                    "receipt_sha256": receipt.get("receipt_sha256"),
                }
            )

    # Use explicit member names rather than tuple positions.  The storage
    # reproducibility bundle grows over time, and positional mappings can
    # silently attach a valid source file to the wrong archive member after an
    # insertion.
    support_sources = {
        "reproducibility/storage/H2_STORAGE_MAINTENANCE_README.md": TOOL_ROOT
        / "scripts/H2_STORAGE_MAINTENANCE_README.md",
        "reproducibility/storage/code/maintain_h2_storage.py": TOOL_ROOT
        / "scripts/maintain_h2_storage.py",
        "reproducibility/storage/code/run_h2_storage_guardian.ps1": TOOL_ROOT
        / "scripts/run_h2_storage_guardian.ps1",
        "reproducibility/storage/code/supervise_h2_product_program.ps1": TOOL_ROOT
        / "scripts/supervise_h2_product_program.ps1",
        STORAGE_TASK_INSTALLER_MEMBER: TOOL_ROOT
        / "scripts/register_h2_v17_scheduled_tasks.ps1",
        "reproducibility/storage/tests/test_h2_storage_maintenance.py": TOOL_ROOT
        / "tests/test_h2_storage_maintenance.py",
        STORAGE_ATOMIC_BOOTSTRAP_MEMBER: TOOL_ROOT
        / "scripts/h2_windows_atomic_retry_bootstrap.py",
        STORAGE_ATOMIC_CHILD_MEMBER: TOOL_ROOT
        / "scripts/h2_atomic_retry_child/sitecustomize.py",
        "reproducibility/storage/code/run_h2_product_program.ps1": TOOL_ROOT
        / "scripts/run_h2_product_program.ps1",
        "reproducibility/storage/H2_WINDOWS_ATOMIC_RETRY_README.md": TOOL_ROOT
        / "scripts/H2_WINDOWS_ATOMIC_RETRY_README.md",
        STORAGE_ARM64_RESOLVER_MEMBER: TOOL_ROOT / "scripts/resolve_h2_arm64_wheels.py",
        STORAGE_ARM64_RESOLVER_README_MEMBER: TOOL_ROOT
        / "scripts/H2_ARM64_WHEEL_RESOLUTION_README.md",
        STORAGE_ARM64_RESOLVER_TEST_MEMBER: TOOL_ROOT
        / "tests/test_h2_arm64_wheel_resolver.py",
    }
    for member, path in support_sources.items():
        output[member] = _storage_source_file(path)

    source_rows = [
        {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
        for name, payload in sorted(output.items())
    ]
    provenance: dict[str, object] = {
        "schema_version": "h2-storage-reproducibility-provenance.v1",
        "status": "VALID",
        "controller_status": state.get("status"),
        "native_packaged_controller_status": packaged_state.get("status"),
        "native_packaged_controller_state_sha256": _sha256(source_payloads[state_name]),
        "terminal_controller_state_member": REQUIRED_STORAGE_MEMBERS[-2],
        "terminal_controller_state_sha256": _sha256(terminal_state_payload),
        "controller_state_transition_preserved": True,
        "program_id": state.get("program_id"),
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "workspace": str(workspace),
        "results_root": str(results_root),
        "snapshot_after_terminal_guardian_pass": True,
        "artifact_lifecycle_sha256": lifecycle.get("lifecycle_sha256"),
        "storage_forecast_sha256": _sha256(forecast_payload),
        "last_guardian_pass_sha256": _sha256(guardian_payload),
        "arm64_wheel_resolution_member": STORAGE_ARM64_WHEEL_RECEIPT_MEMBER,
        "arm64_wheel_resolution_receipt_sha256": arm64_wheel_receipt.get(
            "receipt_sha256"
        ),
        "arm64_resolved_wheel_count": len(arm64_wheel_receipt["wheels"]),
        "arm64_resolved_wheel_logical_bytes": arm64_wheel_receipt["resolution"][
            "resolved_logical_bytes"
        ],
        "arm64_wheel_payloads_embedded": False,
        "windows_atomic_publication_policy_member": STORAGE_ATOMIC_POLICY_MEMBER,
        "windows_atomic_publication_policy_sha256": atomic_policy.get("policy_sha256"),
        "windows_atomic_child_policy_member": STORAGE_ATOMIC_CHILD_MEMBER,
        "windows_atomic_child_policy_sha256": _sha256(atomic_child_payload),
        "windows_atomic_publication_events_member": STORAGE_ATOMIC_EVENTS_MEMBER,
        "windows_atomic_publication_events_sha256": _sha256(atomic_events_payload),
        **atomic_event_summary,
        "scheduled_task_registration_member": (
            STORAGE_TASK_REGISTRATION_MEMBER
            if task_registration_payload is not None
            else None
        ),
        "scheduled_task_registration_sha256": (
            _sha256(task_registration_payload)
            if task_registration_payload is not None
            else None
        ),
        "scheduled_task_count": (
            len(task_registration["tasks"]) if task_registration is not None else 0
        ),
        "superseded_v16_task_count_disabled": (
            len(task_registration["superseded_v16_tasks_disabled"])
            if task_registration is not None
            else 0
        ),
        "prune_receipt_count": len(receipt_rows),
        "compression_receipt_count": len(compression_rows),
        "dynamic_execution_manifest_count": len(dynamic_rows),
        "queue_database_count": len(attempt_database_rows),
        "queue_attempt_history_member": STORAGE_ATTEMPT_HISTORY_MEMBER,
        "queue_attempt_history_sha256": _sha256(attempt_history_payload),
        "queue_attempt_history_row_count": len(attempt_rows),
        "noncomplete_attempt_count": sum(
            row["attempt_state"] != "complete" for row in attempt_rows
        ),
        "recovered_noncomplete_attempt_count": sum(
            row["recovered_after_attempt"] is True for row in attempt_rows
        ),
        "queue_databases": attempt_database_rows,
        "pruned_logical_bytes": pruned_logical_bytes,
        "receipt_scope_counts": dict(sorted(scope_counts.items())),
        "all_prune_receipt_signatures_validated": True,
        "all_nested_prune_validation_signatures_validated": True,
        "all_compression_receipt_signatures_validated": True,
        "scientific_runtime_or_policy_changed": False,
        "removed_restart_payloads_embedded": False,
        "raw_audio_model_weights_and_biometric_caches_embedded": False,
        "reconstruction_contract": (
            "Each signed prune receipt retains frozen job/case identities, former "
            "shard checksums, source manifest identities, and the retained sealed "
            "result checksum; rerun only from the separately governed source audio, "
            "model assets, environment, and frozen controller inputs."
        ),
        "prune_receipts": receipt_rows,
        "compression_receipts": compression_rows,
        "dynamic_execution_manifests": dynamic_rows,
        "source_members": source_rows,
    }
    output[REQUIRED_STORAGE_MEMBERS[-1]] = _canonical_json(provenance)
    return output, provenance


def _validate_storage_reproducibility_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_STORAGE_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks storage reproducibility members: "
            + ", ".join(missing)
        )
    provenance = _storage_json_object(
        payloads[REQUIRED_STORAGE_MEMBERS[-1]], label=REQUIRED_STORAGE_MEMBERS[-1]
    )
    if (
        provenance.get("schema_version") != "h2-storage-reproducibility-provenance.v1"
        or provenance.get("status") != "VALID"
        or provenance.get("controller_status") != "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
        or provenance.get("snapshot_after_terminal_guardian_pass") is not True
        or provenance.get("scientific_runtime_or_policy_changed") is not False
        or provenance.get("removed_restart_payloads_embedded") is not False
        or provenance.get("raw_audio_model_weights_and_biometric_caches_embedded")
        is not False
        or provenance.get("terminal_controller_state_member")
        != REQUIRED_STORAGE_MEMBERS[-2]
        or provenance.get("controller_state_transition_preserved") is not True
        or provenance.get("queue_attempt_history_member")
        != STORAGE_ATTEMPT_HISTORY_MEMBER
    ):
        raise ValueError("storage reproducibility provenance/status differs")
    native_state_name = "controller/program_state.json"
    if native_state_name not in payloads:
        raise ValueError("augmented package lacks native controller state")
    native_state = _storage_json_object(
        payloads[native_state_name], label=native_state_name
    )
    terminal_state = _storage_json_object(
        payloads[REQUIRED_STORAGE_MEMBERS[-2]],
        label=REQUIRED_STORAGE_MEMBERS[-2],
    )
    immutable_fields = (
        "program_id",
        "protocol_id",
        "protocol_sha256",
        "job_manifest_sha256",
        "workspace",
        "results_root",
        "summary_root",
    )
    if (
        terminal_state.get("status") != "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
        or provenance.get("native_packaged_controller_status")
        != native_state.get("status")
        or provenance.get("native_packaged_controller_state_sha256")
        != _sha256(payloads[native_state_name])
        or provenance.get("terminal_controller_state_sha256")
        != _sha256(payloads[REQUIRED_STORAGE_MEMBERS[-2]])
        or any(
            native_state.get(field) != terminal_state.get(field)
            or terminal_state.get(field) is None
            for field in immutable_fields
        )
    ):
        raise ValueError("native pre-publication/controller terminal state differs")
    lifecycle = _storage_json_object(
        payloads[REQUIRED_STORAGE_MEMBERS[0]], label=REQUIRED_STORAGE_MEMBERS[0]
    )
    _validate_signed_storage_document(
        lifecycle,
        schema_version="h2-storage-artifact-lifecycle.v1",
        signature_key="lifecycle_sha256",
        label=REQUIRED_STORAGE_MEMBERS[0],
    )
    if lifecycle.get(
        "campaign_status"
    ) != "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM" or lifecycle.get(
        "lifecycle_sha256"
    ) != provenance.get("artifact_lifecycle_sha256"):
        raise ValueError("packaged terminal storage lifecycle differs")
    forecast = _storage_json_object(
        payloads[REQUIRED_STORAGE_MEMBERS[1]], label=REQUIRED_STORAGE_MEMBERS[1]
    )
    guardian = _storage_json_object(
        payloads[REQUIRED_STORAGE_MEMBERS[2]], label=REQUIRED_STORAGE_MEMBERS[2]
    )
    if (
        forecast.get("program_status") != "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
        or guardian.get("forecast") != forecast
        or guardian.get("artifact_lifecycle_sha256")
        != lifecycle.get("lifecycle_sha256")
        or provenance.get("storage_forecast_sha256")
        != _sha256(payloads[REQUIRED_STORAGE_MEMBERS[1]])
        or provenance.get("last_guardian_pass_sha256")
        != _sha256(payloads[REQUIRED_STORAGE_MEMBERS[2]])
    ):
        raise ValueError("packaged terminal storage snapshots differ")

    if (
        ARM64_REQUIREMENTS_MEMBER not in payloads
        or RUNTIME_IDENTITY_MEMBER not in payloads
    ):
        raise ValueError("augmented package lacks ARM64 wheel receipt bindings")
    arm64_wheel_receipt = _validated_arm64_wheel_resolution_receipt(
        payloads[STORAGE_ARM64_WHEEL_RECEIPT_MEMBER],
        requirements_payload=payloads[ARM64_REQUIREMENTS_MEMBER],
        runtime_identity_payload=payloads[RUNTIME_IDENTITY_MEMBER],
        protocol_id=terminal_state.get("protocol_id"),
    )
    if (
        provenance.get("arm64_wheel_resolution_member")
        != STORAGE_ARM64_WHEEL_RECEIPT_MEMBER
        or provenance.get("arm64_wheel_resolution_receipt_sha256")
        != arm64_wheel_receipt.get("receipt_sha256")
        or provenance.get("arm64_resolved_wheel_count")
        != len(arm64_wheel_receipt["wheels"])
        or provenance.get("arm64_resolved_wheel_logical_bytes")
        != arm64_wheel_receipt["resolution"]["resolved_logical_bytes"]
        or provenance.get("arm64_wheel_payloads_embedded") is not False
        or any(name.casefold().endswith(".whl") for name in payloads)
    ):
        raise ValueError("packaged ARM64 wheel-resolution provenance differs")

    atomic_policy = _validated_windows_atomic_policy(
        payloads[STORAGE_ATOMIC_POLICY_MEMBER],
        launcher_payload=payloads[STORAGE_ATOMIC_BOOTSTRAP_MEMBER],
        child_policy_payload=payloads[STORAGE_ATOMIC_CHILD_MEMBER],
    )
    atomic_event_summary = _validated_windows_atomic_events(
        payloads[STORAGE_ATOMIC_EVENTS_MEMBER]
    )
    if (
        provenance.get("windows_atomic_publication_policy_member")
        != STORAGE_ATOMIC_POLICY_MEMBER
        or provenance.get("windows_atomic_publication_policy_sha256")
        != atomic_policy.get("policy_sha256")
        or provenance.get("windows_atomic_child_policy_member")
        != STORAGE_ATOMIC_CHILD_MEMBER
        or provenance.get("windows_atomic_child_policy_sha256")
        != _sha256(payloads[STORAGE_ATOMIC_CHILD_MEMBER])
        or provenance.get("windows_atomic_publication_events_member")
        != STORAGE_ATOMIC_EVENTS_MEMBER
        or provenance.get("windows_atomic_publication_events_sha256")
        != _sha256(payloads[STORAGE_ATOMIC_EVENTS_MEMBER])
        or any(
            provenance.get(key) != value for key, value in atomic_event_summary.items()
        )
    ):
        raise ValueError("packaged Windows atomic-publication provenance differs")

    task_member = provenance.get("scheduled_task_registration_member")
    if task_member is None:
        if (
            STORAGE_TASK_REGISTRATION_MEMBER in payloads
            or provenance.get("scheduled_task_registration_sha256") is not None
            or provenance.get("scheduled_task_count") != 0
            or provenance.get("superseded_v16_task_count_disabled") != 0
        ):
            raise ValueError("packaged scheduled-task absence provenance differs")
    else:
        if (
            task_member != STORAGE_TASK_REGISTRATION_MEMBER
            or STORAGE_TASK_REGISTRATION_MEMBER not in payloads
            or STORAGE_TASK_INSTALLER_MEMBER not in payloads
        ):
            raise ValueError("packaged scheduled-task member binding differs")
        task_registration = _validated_h2_v17_task_registration(
            payloads[STORAGE_TASK_REGISTRATION_MEMBER],
            installer_payload=payloads[STORAGE_TASK_INSTALLER_MEMBER],
            terminal_state=terminal_state,
        )
        if (
            provenance.get("scheduled_task_registration_sha256")
            != _sha256(payloads[STORAGE_TASK_REGISTRATION_MEMBER])
            or provenance.get("scheduled_task_count") != len(task_registration["tasks"])
            or provenance.get("superseded_v16_task_count_disabled")
            != len(task_registration["superseded_v16_tasks_disabled"])
        ):
            raise ValueError("packaged scheduled-task provenance differs")

    prune_names = sorted(
        name for name in payloads if name.startswith(STORAGE_PRUNE_PREFIX)
    )
    compression_names = sorted(
        name for name in payloads if name.startswith(STORAGE_COMPRESSION_PREFIX)
    )
    dynamic_names = sorted(
        name for name in payloads if name.startswith(STORAGE_DYNAMIC_PREFIX)
    )
    if (
        len(prune_names) != provenance.get("prune_receipt_count")
        or len(compression_names) != provenance.get("compression_receipt_count")
        or len(dynamic_names) != provenance.get("dynamic_execution_manifest_count")
        or not prune_names
    ):
        raise ValueError("packaged storage receipt counts differ")

    attempt_rows = _csv_rows(payloads[STORAGE_ATTEMPT_HISTORY_MEMBER])
    if not attempt_rows:
        raise ValueError("packaged queue attempt history is empty")
    if tuple(attempt_rows[0]) != ATTEMPT_HISTORY_FIELDS:
        raise ValueError("packaged queue attempt history schema differs")
    if provenance.get("queue_attempt_history_sha256") != _sha256(
        payloads[STORAGE_ATTEMPT_HISTORY_MEMBER]
    ) or provenance.get("queue_attempt_history_row_count") != len(attempt_rows):
        raise ValueError("packaged queue attempt history checksum/count differs")
    attempt_keys = {
        (
            row["queue_database_relative_path"],
            row["job_id"],
            row["attempt_number"],
        )
        for row in attempt_rows
    }
    if len(attempt_keys) != len(attempt_rows) or any(
        row["schema_version"] != "h2-queue-attempt-history-row.v1"
        for row in attempt_rows
    ):
        raise ValueError("packaged queue attempt history identity differs")
    for row in attempt_rows:
        expected_recovered = (
            row["attempt_state"] != "complete" and row["final_job_state"] == "complete"
        )
        if (
            row["recovered_after_attempt"].casefold()
            != str(expected_recovered).casefold()
        ):
            raise ValueError("packaged queue attempt recovery classification differs")
    noncomplete_count = sum(row["attempt_state"] != "complete" for row in attempt_rows)
    recovered_count = sum(
        row["attempt_state"] != "complete"
        and row["final_job_state"] == "complete"
        and row["recovered_after_attempt"].casefold() == "true"
        for row in attempt_rows
    )
    if (
        provenance.get("noncomplete_attempt_count") != noncomplete_count
        or provenance.get("recovered_noncomplete_attempt_count") != recovered_count
    ):
        raise ValueError("packaged queue attempt failure/recovery counts differ")
    database_rows = provenance.get("queue_databases")
    if not isinstance(database_rows, list) or len(database_rows) != provenance.get(
        "queue_database_count"
    ):
        raise ValueError("packaged queue database inventory differs")
    declared_database_paths: set[str] = set()
    for raw in database_rows:
        if not isinstance(raw, Mapping):
            raise ValueError("packaged queue database inventory row is invalid")
        relative_path = str(raw.get("relative_path") or "")
        if not relative_path or relative_path in declared_database_paths:
            raise ValueError("packaged queue database inventory identity differs")
        declared_database_paths.add(relative_path)
        matching = [
            row
            for row in attempt_rows
            if row["queue_database_relative_path"] == relative_path
        ]
        matching_noncomplete = sum(
            row["attempt_state"] != "complete" for row in matching
        )
        matching_recovered = sum(
            row["recovered_after_attempt"].casefold() == "true" for row in matching
        )
        if (
            raw.get("attempt_count") != len(matching)
            or any(
                row["queue_database_sha256"] != raw.get("sha256") for row in matching
            )
            or raw.get("noncomplete_attempt_count") != matching_noncomplete
            or raw.get("recovered_noncomplete_attempt_count") != matching_recovered
        ):
            raise ValueError("packaged queue database attempt binding differs")
    pruned_bytes = 0
    for name in prune_names:
        receipt = _storage_json_object(payloads[name], label=name)
        _validate_signed_storage_document(
            receipt,
            schema_version="h2-storage-prune-receipt.v1",
            signature_key="receipt_sha256",
            label=name,
        )
        pending = receipt.get("validation_receipt")
        if not isinstance(pending, Mapping):
            raise ValueError(f"packaged prune receipt lacks validation: {name}")
        _validate_signed_storage_document(
            pending,
            schema_version="h2-storage-prune-pending.v1",
            signature_key="pending_sha256",
            label=f"{name}:validation_receipt",
        )
        source = pending.get("regenerable_source")
        if not isinstance(source, Mapping):
            raise ValueError(f"packaged prune receipt lacks source inventory: {name}")
        pruned_bytes += int(source.get("logical_bytes") or 0)
    if pruned_bytes != provenance.get("pruned_logical_bytes"):
        raise ValueError("packaged pruned logical-byte total differs")
    for name in compression_names:
        receipt = _storage_json_object(payloads[name], label=name)
        _validate_signed_storage_document(
            receipt,
            schema_version="h2-storage-compression-receipt.v1",
            signature_key="receipt_sha256",
            label=name,
        )
    for name in dynamic_names:
        dynamic = _storage_json_object(payloads[name], label=name)
        unsigned = dict(dynamic)
        observed = unsigned.pop("dynamic_execution_sha256", None)
        if (
            dynamic.get("schema_version") != "h2-dynamic-development-execution.v1"
            or observed != _sha256(_storage_canonical_bytes(unsigned))
            or dynamic.get("split") != "development"
            or dynamic.get("evaluation_material_inspected") is not False
        ):
            raise ValueError(f"packaged dynamic storage binding differs: {name}")

    source_rows = provenance.get("source_members")
    if not isinstance(source_rows, list):
        raise ValueError("storage reproducibility source inventory is missing")
    declared = {
        str(row.get("member")): row
        for row in source_rows
        if isinstance(row, Mapping) and row.get("member")
    }
    actual_storage = {
        name
        for name in payloads
        if name.startswith(STORAGE_PREFIX) and name != REQUIRED_STORAGE_MEMBERS[-1]
    }
    if set(declared) != actual_storage or len(declared) != len(source_rows):
        raise ValueError("storage reproducibility source membership differs")
    for name, row in declared.items():
        payload = payloads[name]
        if row.get("sha256") != _sha256(payload) or row.get("bytes") != len(payload):
            raise ValueError(f"storage reproducibility source checksum differs: {name}")
    return provenance


def _ui_latency_summary_payloads(
    receipt: Mapping[str, object], runtime_sha: str
) -> dict[str, bytes]:
    metrics = receipt.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("UI latency receipt metrics are missing")
    sample_count = int(metrics.get("sample_count") or 0)
    metric_ids = (
        "minimum_ms",
        "mean_ms",
        "median_ms",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "maximum_ms",
        "population_standard_deviation_ms",
    )
    rows = [
        {
            "schema_version": "h2-controlled-ui-latency-summary.v1",
            "evidence_class": "CONTROLLED_ENGINEERING_UI_PRESENTATION_LATENCY",
            "metric_id": metric_id,
            "value": metrics.get(metric_id),
            "unit": "milliseconds",
            "sample_count": sample_count,
            "runtime_identity_sha256": runtime_sha,
            "scientific_selection_or_policy_changed": False,
            "neural_inference_executed": False,
            "physical_display_scanout_included": False,
        }
        for metric_id in metric_ids
    ]
    fields = (
        "schema_version",
        "evidence_class",
        "metric_id",
        "value",
        "unit",
        "sample_count",
        "runtime_identity_sha256",
        "scientific_selection_or_policy_changed",
        "neural_inference_executed",
        "physical_display_scanout_included",
    )
    guide = "\n".join(
        (
            "# Controlled H2 UI event latency",
            "",
            "This post-run engineering benchmark measures from the event's "
            "monotonic emission timestamp through durable JSONL polling, the "
            "bounded/coalescing UI queue, background worker-to-Tk handoff, state "
            "projection, real Tk widget updates, and `update_idletasks` completion.",
            "",
            f"- Samples: {sample_count}",
            f"- Median: {float(metrics['median_ms']):.3f} ms",
            f"- P95: {float(metrics['p95_ms']):.3f} ms",
            f"- P99: {float(metrics['p99_ms']):.3f} ms",
            f"- Maximum: {float(metrics['maximum_ms']):.3f} ms",
            f"- Frozen runtime identity: `{runtime_sha}`",
            "",
            "It excludes audio capture, neural/backend compute, the operating-"
            "system display compositor, and physical panel scanout. It is not a "
            "scientific selection input and does not replace unsupported UI-lag "
            "rows in the immutable native scientific results.",
            "",
        )
    ).encode("utf-8")
    return {
        UI_LATENCY_SUMMARY_CSV_MEMBER: _csv_payload(rows, fields),
        UI_LATENCY_SUMMARY_GUIDE_MEMBER: guide,
    }


def _ui_latency_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Package signed controlled UI latency evidence and exact exercised source."""

    if RUNTIME_IDENTITY_MEMBER not in source_payloads:
        raise ValueError("native package lacks frozen runtime identity for UI latency")
    runtime_identity = _storage_json_object(
        source_payloads[RUNTIME_IDENTITY_MEMBER], label=RUNTIME_IDENTITY_MEMBER
    )
    runtime_sha = str(runtime_identity.get("identity_sha256") or "")
    receipt_path = (
        Path(workspace).resolve()
        / "engineering_validation/ui_event_latency_receipt.json"
    )
    receipt_payload = _storage_source_file(receipt_path)
    receipt = _storage_json_object(receipt_payload, label=str(receipt_path))
    validated = validate_ui_latency_receipt(
        receipt, expected_runtime_identity_sha256=runtime_sha
    )
    runtime_binding = validated.get("runtime_binding")
    if not isinstance(runtime_binding, Mapping):
        raise ValueError("UI latency receipt runtime binding is missing")
    if runtime_binding.get("frozen_runtime_identity_file_sha256") != _sha256(
        source_payloads[RUNTIME_IDENTITY_MEMBER]
    ):
        raise ValueError("UI latency receipt frozen runtime file binding differs")

    source_paths = {
        UI_LATENCY_BENCHMARK_SOURCE_MEMBER: TOOL_ROOT
        / "scripts/measure_h2_ui_event_latency.py",
        UI_LATENCY_README_MEMBER: TOOL_ROOT / "scripts/H2_UI_EVENT_LATENCY_README.md",
        UI_LATENCY_TEST_MEMBER: TOOL_ROOT
        / "tests/test_h2_ui_event_latency_benchmark.py",
        **{
            f"{UI_LATENCY_RUNTIME_PREFIX}{path.relative_to(TOOL_ROOT).as_posix()}": path
            for path in UI_LATENCY_RUNTIME_SOURCE_FILES
        },
    }
    output = {UI_LATENCY_RECEIPT_MEMBER: receipt_payload}
    output.update(
        {member: _storage_source_file(path) for member, path in source_paths.items()}
    )
    output.update(_ui_latency_summary_payloads(validated, runtime_sha))
    exact_source_hashes = runtime_binding.get("exact_source_file_sha256")
    if not isinstance(exact_source_hashes, Mapping):
        raise ValueError("UI latency receipt exact source hashes are missing")
    for logical_path, expected_sha in exact_source_hashes.items():
        member = f"{UI_LATENCY_RUNTIME_PREFIX}{logical_path}"
        if member not in output or _sha256(output[member]) != expected_sha:
            raise ValueError(f"UI latency exercised source differs: {logical_path}")

    source_rows = [
        {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
        for name, payload in sorted(output.items())
    ]
    metrics = validated.get("metrics")
    provenance: dict[str, object] = {
        "schema_version": "h2-ui-event-latency-provenance.v1",
        "status": "VALID",
        "evidence_class": "CONTROLLED_ENGINEERING_UI_PRESENTATION_LATENCY",
        "runtime_identity_sha256": runtime_sha,
        "receipt_sha256": validated.get("receipt_sha256"),
        "sample_count": (
            metrics.get("sample_count") if isinstance(metrics, Mapping) else None
        ),
        "scientific_runtime_or_policy_changed": False,
        "used_for_scientific_selection": False,
        "native_package_member_changed": False,
        "physical_microphone_or_display_performance_claimed": False,
        "source_members": source_rows,
    }
    output[UI_LATENCY_PROVENANCE_MEMBER] = _canonical_json(provenance)
    return output, provenance


def _validate_ui_latency_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_UI_LATENCY_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks UI latency evidence: " + ", ".join(missing)
        )
    runtime_identity = _storage_json_object(
        payloads[RUNTIME_IDENTITY_MEMBER], label=RUNTIME_IDENTITY_MEMBER
    )
    runtime_sha = str(runtime_identity.get("identity_sha256") or "")
    receipt = _storage_json_object(
        payloads[UI_LATENCY_RECEIPT_MEMBER], label=UI_LATENCY_RECEIPT_MEMBER
    )
    validated = validate_ui_latency_receipt(
        receipt, expected_runtime_identity_sha256=runtime_sha
    )
    runtime_binding = validated.get("runtime_binding")
    if not isinstance(runtime_binding, Mapping) or runtime_binding.get(
        "frozen_runtime_identity_file_sha256"
    ) != _sha256(payloads[RUNTIME_IDENTITY_MEMBER]):
        raise ValueError("packaged UI latency runtime file binding differs")
    exact_source_hashes = runtime_binding.get("exact_source_file_sha256")
    if not isinstance(exact_source_hashes, Mapping):
        raise ValueError("packaged UI latency source hashes are missing")
    for logical_path, expected_sha in exact_source_hashes.items():
        member = f"{UI_LATENCY_RUNTIME_PREFIX}{logical_path}"
        if member not in payloads or _sha256(payloads[member]) != expected_sha:
            raise ValueError(f"packaged UI latency source differs: {logical_path}")

    expected_summaries = _ui_latency_summary_payloads(validated, runtime_sha)
    if any(
        payloads.get(name) != payload for name, payload in expected_summaries.items()
    ):
        raise ValueError("packaged UI latency summary rendering differs")

    provenance = _storage_json_object(
        payloads[UI_LATENCY_PROVENANCE_MEMBER],
        label=UI_LATENCY_PROVENANCE_MEMBER,
    )
    metrics = validated.get("metrics")
    if (
        provenance.get("schema_version") != "h2-ui-event-latency-provenance.v1"
        or provenance.get("status") != "VALID"
        or provenance.get("runtime_identity_sha256") != runtime_sha
        or provenance.get("receipt_sha256") != validated.get("receipt_sha256")
        or provenance.get("sample_count")
        != (metrics.get("sample_count") if isinstance(metrics, Mapping) else None)
        or provenance.get("scientific_runtime_or_policy_changed") is not False
        or provenance.get("used_for_scientific_selection") is not False
        or provenance.get("native_package_member_changed") is not False
        or provenance.get("physical_microphone_or_display_performance_claimed")
        is not False
    ):
        raise ValueError("UI latency provenance/status/firewall differs")
    rows = provenance.get("source_members")
    if not isinstance(rows, list):
        raise ValueError("UI latency source inventory is missing")
    declared = {
        str(row.get("member")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("member")
    }
    expected = set(REQUIRED_UI_LATENCY_MEMBERS[:-1])
    if set(declared) != expected or len(declared) != len(rows):
        raise ValueError("UI latency source inventory membership differs")
    for name, row in declared.items():
        if row.get("sha256") != _sha256(payloads[name]) or row.get("bytes") != len(
            payloads[name]
        ):
            raise ValueError(f"UI latency source checksum differs: {name}")
    return provenance


def _data_firewall_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Package the compact pre-open split audit without copying source manifests."""

    protocol_member = "protocol/protocol_manifest.json"
    if RUNTIME_IDENTITY_MEMBER not in source_payloads:
        raise ValueError(
            "native package lacks frozen runtime identity for firewall audit"
        )
    if protocol_member not in source_payloads:
        raise ValueError("native package lacks protocol manifest for firewall audit")
    runtime_identity = _storage_json_object(
        source_payloads[RUNTIME_IDENTITY_MEMBER], label=RUNTIME_IDENTITY_MEMBER
    )
    protocol_manifest = _storage_json_object(
        source_payloads[protocol_member], label=protocol_member
    )
    runtime_sha = str(runtime_identity.get("identity_sha256") or "")
    protocol_id = str(protocol_manifest.get("protocol_id") or "")
    receipt_path = (
        Path(workspace).resolve()
        / "engineering_validation/enrollment_firewall_audit_receipt.json"
    )
    receipt_payload = _storage_source_file(receipt_path)
    receipt = _storage_json_object(receipt_payload, label=str(receipt_path))
    validated = validate_enrollment_firewall_receipt(receipt)
    runtime_binding = validated.get("runtime_binding")
    protocol_binding = validated.get("protocol_binding")
    if (
        not isinstance(runtime_binding, Mapping)
        or runtime_binding.get("frozen_runtime_identity_sha256") != runtime_sha
        or runtime_binding.get("frozen_runtime_identity_file_sha256")
        != _sha256(source_payloads[RUNTIME_IDENTITY_MEMBER])
    ):
        raise ValueError("enrollment firewall frozen runtime binding differs")
    if (
        not isinstance(protocol_binding, Mapping)
        or protocol_binding.get("h2_protocol_id") != protocol_id
        or protocol_binding.get("h2_protocol_manifest_sha256")
        != _sha256(source_payloads[protocol_member])
    ):
        raise ValueError("enrollment firewall H2 protocol binding differs")

    source_paths = {
        DATA_FIREWALL_CODE_MEMBER: TOOL_ROOT
        / "scripts/audit_h2_enrollment_firewall.py",
        DATA_FIREWALL_README_MEMBER: TOOL_ROOT
        / "scripts/H2_ENROLLMENT_FIREWALL_AUDIT_README.md",
        DATA_FIREWALL_TEST_MEMBER: TOOL_ROOT
        / "tests/test_h2_enrollment_firewall_audit.py",
    }
    output = {DATA_FIREWALL_RECEIPT_MEMBER: receipt_payload}
    output.update(
        {member: _storage_source_file(path) for member, path in source_paths.items()}
    )
    source_rows = [
        {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
        for name, payload in sorted(output.items())
    ]
    heldout = validated.get("heldout_preopen")
    partitions = validated.get("partitions")
    provenance: dict[str, object] = {
        "schema_version": "h2-data-firewall-provenance.v1",
        "status": "VALID",
        "evidence_class": "PREOPEN_METADATA_ONLY_SPLIT_FIREWALL_AUDIT",
        "receipt_sha256": validated.get("receipt_sha256"),
        "runtime_identity_sha256": runtime_sha,
        "protocol_id": protocol_id,
        "development_registry_rows": (
            partitions.get("development", {}).get("registry_rows")
            if isinstance(partitions, Mapping)
            and isinstance(partitions.get("development"), Mapping)
            else None
        ),
        "evaluation_registry_rows": (
            partitions.get("evaluation", {}).get("registry_rows")
            if isinstance(partitions, Mapping)
            and isinstance(partitions.get("evaluation"), Mapping)
            else None
        ),
        "evaluation_job_count_at_preopen": (
            heldout.get("evaluation_job_count")
            if isinstance(heldout, Mapping)
            else None
        ),
        "all_declared_cross_partition_overlap_counts_zero": True,
        "heldout_queue_unopened_at_audit": True,
        "source_manifests_embedded": False,
        "raw_audio_or_biometric_payload_embedded": False,
        "scientific_runtime_or_policy_changed": False,
        "used_for_scientific_selection": False,
        "native_package_member_changed": False,
        "source_members": source_rows,
    }
    output[DATA_FIREWALL_PROVENANCE_MEMBER] = _canonical_json(provenance)
    return output, provenance


def _validate_data_firewall_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_DATA_FIREWALL_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks enrollment firewall evidence: "
            + ", ".join(missing)
        )
    protocol_member = "protocol/protocol_manifest.json"
    runtime_identity = _storage_json_object(
        payloads[RUNTIME_IDENTITY_MEMBER], label=RUNTIME_IDENTITY_MEMBER
    )
    protocol_manifest = _storage_json_object(
        payloads[protocol_member], label=protocol_member
    )
    runtime_sha = str(runtime_identity.get("identity_sha256") or "")
    protocol_id = str(protocol_manifest.get("protocol_id") or "")
    receipt = _storage_json_object(
        payloads[DATA_FIREWALL_RECEIPT_MEMBER],
        label=DATA_FIREWALL_RECEIPT_MEMBER,
    )
    validated = validate_enrollment_firewall_receipt(receipt)
    runtime_binding = validated.get("runtime_binding")
    protocol_binding = validated.get("protocol_binding")
    if (
        not isinstance(runtime_binding, Mapping)
        or runtime_binding.get("frozen_runtime_identity_sha256") != runtime_sha
        or runtime_binding.get("frozen_runtime_identity_file_sha256")
        != _sha256(payloads[RUNTIME_IDENTITY_MEMBER])
        or not isinstance(protocol_binding, Mapping)
        or protocol_binding.get("h2_protocol_id") != protocol_id
        or protocol_binding.get("h2_protocol_manifest_sha256")
        != _sha256(payloads[protocol_member])
    ):
        raise ValueError("packaged enrollment firewall binding differs")
    provenance = _storage_json_object(
        payloads[DATA_FIREWALL_PROVENANCE_MEMBER],
        label=DATA_FIREWALL_PROVENANCE_MEMBER,
    )
    heldout = validated.get("heldout_preopen")
    partitions = validated.get("partitions")
    if (
        provenance.get("schema_version") != "h2-data-firewall-provenance.v1"
        or provenance.get("status") != "VALID"
        or provenance.get("receipt_sha256") != validated.get("receipt_sha256")
        or provenance.get("runtime_identity_sha256") != runtime_sha
        or provenance.get("protocol_id") != protocol_id
        or provenance.get("development_registry_rows")
        != (
            partitions.get("development", {}).get("registry_rows")
            if isinstance(partitions, Mapping)
            and isinstance(partitions.get("development"), Mapping)
            else None
        )
        or provenance.get("evaluation_registry_rows")
        != (
            partitions.get("evaluation", {}).get("registry_rows")
            if isinstance(partitions, Mapping)
            and isinstance(partitions.get("evaluation"), Mapping)
            else None
        )
        or provenance.get("evaluation_job_count_at_preopen")
        != (
            heldout.get("evaluation_job_count")
            if isinstance(heldout, Mapping)
            else None
        )
        or provenance.get("all_declared_cross_partition_overlap_counts_zero")
        is not True
        or provenance.get("heldout_queue_unopened_at_audit") is not True
        or provenance.get("source_manifests_embedded") is not False
        or provenance.get("raw_audio_or_biometric_payload_embedded") is not False
        or provenance.get("scientific_runtime_or_policy_changed") is not False
        or provenance.get("used_for_scientific_selection") is not False
        or provenance.get("native_package_member_changed") is not False
    ):
        raise ValueError("enrollment firewall provenance/status differs")
    rows = provenance.get("source_members")
    if not isinstance(rows, list):
        raise ValueError("enrollment firewall source inventory is missing")
    declared = {
        str(row.get("member")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("member")
    }
    expected = set(REQUIRED_DATA_FIREWALL_MEMBERS[:-1])
    if set(declared) != expected or len(declared) != len(rows):
        raise ValueError("enrollment firewall source inventory membership differs")
    for name, row in declared.items():
        if row.get("sha256") != _sha256(payloads[name]) or row.get("bytes") != len(
            payloads[name]
        ):
            raise ValueError(f"enrollment firewall source checksum differs: {name}")
    return provenance


def _validated_development_cpu_interference_receipt(
    receipt: Mapping[str, object],
    source_payloads: Mapping[str, bytes],
) -> dict[str, object]:
    """Validate the signed host-load disclosure against immutable native inputs."""

    protocol_member = "protocol/protocol_manifest.json"
    manifest_member = "protocol/job_manifest.json"
    for name in (protocol_member, manifest_member, RUNTIME_IDENTITY_MEMBER):
        if name not in source_payloads:
            raise ValueError(
                f"native package lacks {name} for development CPU disclosure"
            )
    value = dict(receipt)
    signature = value.pop("receipt_sha256", None)
    if signature != canonical_sha256(value):
        raise ValueError("development CPU interference receipt signature differs")
    if (
        value.get("schema_version") != "h2-development-host-cpu-interference.v1"
        or value.get("status") != "HOST_CPU_INTERFERENCE_DISCLOSED_TIMING_INELIGIBLE"
    ):
        raise ValueError("development CPU interference receipt schema/status differs")

    protocol = _storage_json_object(
        source_payloads[protocol_member], label=protocol_member
    )
    manifest = _storage_json_object(
        source_payloads[manifest_member], label=manifest_member
    )
    runtime = _storage_json_object(
        source_payloads[RUNTIME_IDENTITY_MEMBER], label=RUNTIME_IDENTITY_MEMBER
    )
    if (
        value.get("protocol_id") != protocol.get("protocol_id")
        or value.get("protocol_sha256") != protocol.get("protocol_sha256")
        or value.get("job_manifest_identity_sha256")
        != manifest.get("job_manifest_sha256")
        or value.get("job_manifest_file_sha256_at_capture")
        != _sha256(source_payloads[manifest_member])
        or value.get("runtime_implementation_identity_sha256")
        != runtime.get("identity_sha256")
        or value.get("runtime_implementation_identity_file_sha256_at_capture")
        != _sha256(source_payloads[RUNTIME_IDENTITY_MEMBER])
    ):
        raise ValueError("development CPU interference native binding differs")

    affected = value.get("affected_job")
    jobs = manifest.get("jobs")
    if not isinstance(affected, Mapping) or not isinstance(jobs, list):
        raise ValueError("development CPU interference job binding is missing")
    matches = [
        row
        for row in jobs
        if isinstance(row, Mapping) and row.get("job_id") == affected.get("job_id")
    ]
    if len(matches) != 1:
        raise ValueError("development CPU interference job membership differs")
    job = matches[0]
    for key in (
        "identity_sha256",
        "phase_index",
        "phase_name",
        "job_kind",
        "configuration_id",
        "split",
        "serial",
        "audio_duration_sec",
    ):
        receipt_key = {
            "identity_sha256": "job_identity_sha256",
            "audio_duration_sec": "planned_audio_sec",
        }.get(key, key)
        if affected.get(receipt_key) != job.get(key):
            raise ValueError(
                f"development CPU interference affected-job field differs: {key}"
            )
    if (
        job.get("job_kind") != "post_promotion_integration"
        or job.get("split") != "development"
        or job.get("serial") is not False
    ):
        raise ValueError("development CPU interference scope is not post-promotion")
    case_ids = job.get("case_ids")
    if not isinstance(case_ids, list) or affected.get("planned_case_count") != len(
        case_ids
    ):
        raise ValueError("development CPU interference planned case count differs")

    interference = value.get("interference")
    interpretation = value.get("scientific_interpretation")
    remediation = value.get("remediation")
    snapshot = value.get("capture_snapshot")
    if (
        not isinstance(interference, Mapping)
        or interference.get("kind") != "UNINTENDED_DIAGNOSTIC_PROCESS_CPU_LOAD"
        or interference.get("controller_or_model_worker_stopped") is not False
        or interference.get("scientific_configuration_changed") is not False
        or interference.get("results_deleted_or_restarted") is not False
        or not isinstance(interpretation, Mapping)
        or interpretation.get("timing_and_resource_fields_eligible_as_clean_evidence")
        is not False
        or interpretation.get("development_selection_affected") is not False
        or interpretation.get("heldout_evaluation_opened") is not False
        or interpretation.get("retuning_permitted_or_performed") is not False
        or not isinstance(remediation, Mapping)
        or remediation.get("active_job_interrupted") is not False
        or remediation.get("completed_work_preserved") is not True
        or remediation.get("clean_resource_evidence_required") is not True
        or not isinstance(snapshot, Mapping)
        or snapshot.get("controller_alive_after_cleanup") is not True
    ):
        raise ValueError("development CPU interference scientific boundary differs")
    processes = interference.get("processes")
    if (
        not isinstance(processes, list)
        or len(processes) != 2
        or any(
            not isinstance(row, Mapping)
            or row.get("campaign_process") is not False
            or float(row.get("cpu_time_sec_at_stop") or 0.0) <= 0.0
            for row in processes
        )
    ):
        raise ValueError("development CPU interference process evidence differs")
    return {**value, "receipt_sha256": signature}


def _development_cpu_interference_payloads(
    workspace: Path, source_payloads: Mapping[str, bytes]
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Package a signed timing-ineligibility disclosure without changing results."""

    receipt_path = (
        Path(workspace).resolve()
        / "engineering_validation/development_host_cpu_interference_receipt.json"
    )
    receipt_payload = _storage_source_file(receipt_path)
    receipt = _storage_json_object(receipt_payload, label=str(receipt_path))
    validated = _validated_development_cpu_interference_receipt(
        receipt, source_payloads
    )
    output = {DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER: receipt_payload}
    provenance: dict[str, object] = {
        "schema_version": "h2-development-host-cpu-interference-provenance.v1",
        "status": "VALID_DISCLOSED_TIMING_INELIGIBLE",
        "receipt_sha256": validated.get("receipt_sha256"),
        "affected_job_id": validated.get("affected_job", {}).get("job_id"),
        "timing_and_resource_fields_eligible_as_clean_evidence": False,
        "development_selection_affected": False,
        "heldout_evaluation_opened_at_detection": False,
        "scientific_runtime_or_policy_changed": False,
        "native_package_member_changed": False,
        "clean_resource_replay_required": True,
        "source_members": [
            {
                "member": DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER,
                "sha256": _sha256(receipt_payload),
                "bytes": len(receipt_payload),
            }
        ],
    }
    output[DEVELOPMENT_CPU_INTERFERENCE_PROVENANCE_MEMBER] = _canonical_json(provenance)
    return output, provenance


def _validate_development_cpu_interference_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [
        name
        for name in REQUIRED_DEVELOPMENT_CPU_INTERFERENCE_MEMBERS
        if name not in payloads
    ]
    if missing:
        raise ValueError(
            "augmented package lacks development CPU interference disclosure: "
            + ", ".join(missing)
        )
    receipt = _storage_json_object(
        payloads[DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER],
        label=DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER,
    )
    validated = _validated_development_cpu_interference_receipt(receipt, payloads)
    provenance = _storage_json_object(
        payloads[DEVELOPMENT_CPU_INTERFERENCE_PROVENANCE_MEMBER],
        label=DEVELOPMENT_CPU_INTERFERENCE_PROVENANCE_MEMBER,
    )
    affected = validated.get("affected_job")
    if (
        provenance.get("schema_version")
        != "h2-development-host-cpu-interference-provenance.v1"
        or provenance.get("status") != "VALID_DISCLOSED_TIMING_INELIGIBLE"
        or provenance.get("receipt_sha256") != validated.get("receipt_sha256")
        or provenance.get("affected_job_id")
        != (affected.get("job_id") if isinstance(affected, Mapping) else None)
        or provenance.get("timing_and_resource_fields_eligible_as_clean_evidence")
        is not False
        or provenance.get("development_selection_affected") is not False
        or provenance.get("heldout_evaluation_opened_at_detection") is not False
        or provenance.get("scientific_runtime_or_policy_changed") is not False
        or provenance.get("native_package_member_changed") is not False
        or provenance.get("clean_resource_replay_required") is not True
    ):
        raise ValueError("development CPU interference provenance differs")
    rows = provenance.get("source_members")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("development CPU interference source inventory differs")
    row = rows[0]
    receipt_payload = payloads[DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER]
    if (
        not isinstance(row, Mapping)
        or row.get("member") != DEVELOPMENT_CPU_INTERFERENCE_RECEIPT_MEMBER
        or row.get("sha256") != _sha256(receipt_payload)
        or row.get("bytes") != len(receipt_payload)
    ):
        raise ValueError("development CPU interference receipt inventory differs")
    return provenance


def _augmentation_source_payloads() -> tuple[dict[str, bytes], dict[str, object]]:
    sources = {
        REQUIRED_AUGMENTATION_MEMBERS[0]: TOOL_ROOT
        / "scripts/augment_h2_final_package.py",
        REQUIRED_AUGMENTATION_MEMBERS[1]: TOOL_ROOT
        / "scripts/watch_and_augment_h2_final_package.ps1",
        REQUIRED_AUGMENTATION_MEMBERS[2]: TOOL_ROOT
        / "scripts/H2_FINAL_PACKAGE_SUPPLEMENT_README.md",
        REQUIRED_AUGMENTATION_MEMBERS[3]: TOOL_ROOT
        / "tests/test_h2_final_package_supplement.py",
        REQUIRED_AUGMENTATION_MEMBERS[4]: TOOL_ROOT
        / "scripts/watch_h2_postcampaign_engineering.ps1",
        REQUIRED_AUGMENTATION_MEMBERS[5]: TOOL_ROOT
        / "scripts/H2_POSTCAMPAIGN_ENGINEERING_WATCHER_README.md",
        ASR_COMMONVOICE_POLICY_MEMBER: ASR_COMMONVOICE_POLICY_SOURCE,
    }
    output = {member: _storage_source_file(path) for member, path in sources.items()}
    provenance: dict[str, object] = {
        "schema_version": "h2-augmentation-source-provenance.v1",
        "status": "VALID",
        "purpose": (
            "Reproduce and independently validate the deterministic post-run "
            "plots, metric supplements, source-science tables, storage snapshot, "
            "final operating recommendations, manifest, and checksums from the "
            "native controller package."
        ),
        "runs_only_after_native_package_validation": True,
        "scientific_runtime_or_frozen_policy_changed": False,
        "native_members_modified": False,
        "source_members": [
            {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
            for name, payload in sorted(output.items())
        ],
    }
    output[REQUIRED_AUGMENTATION_MEMBERS[-1]] = _canonical_json(provenance)
    return output, provenance


def _validate_augmentation_source_members(
    payloads: Mapping[str, bytes],
) -> dict[str, object]:
    missing = [name for name in REQUIRED_AUGMENTATION_MEMBERS if name not in payloads]
    if missing:
        raise ValueError(
            "augmented package lacks augmentation reproduction source: "
            + ", ".join(missing)
        )
    provenance = _storage_json_object(
        payloads[REQUIRED_AUGMENTATION_MEMBERS[-1]],
        label=REQUIRED_AUGMENTATION_MEMBERS[-1],
    )
    if (
        provenance.get("schema_version") != "h2-augmentation-source-provenance.v1"
        or provenance.get("status") != "VALID"
        or provenance.get("runs_only_after_native_package_validation") is not True
        or provenance.get("scientific_runtime_or_frozen_policy_changed") is not False
        or provenance.get("native_members_modified") is not False
    ):
        raise ValueError("augmentation source provenance/status differs")
    rows = provenance.get("source_members")
    if not isinstance(rows, list):
        raise ValueError("augmentation source inventory is missing")
    declared = {
        str(row.get("member")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("member")
    }
    expected = set(REQUIRED_AUGMENTATION_MEMBERS[:-1])
    if set(declared) != expected or len(declared) != len(rows):
        raise ValueError("augmentation source inventory membership differs")
    for name, row in declared.items():
        payload = payloads[name]
        if row.get("sha256") != _sha256(payload) or row.get("bytes") != len(payload):
            raise ValueError(f"augmentation source checksum differs: {name}")
    return provenance


def _deterministic_zip(payloads: Mapping[str, bytes], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".partial",
        dir=destination.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in sorted(payloads):
                info = zipfile.ZipInfo(
                    _safe_name(name), date_time=(1980, 1, 1, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(info, payloads[name])
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256(destination.read_bytes())


def validate_augmented_package(
    path: Path,
    *,
    source_payloads: Mapping[str, bytes] | None = None,
) -> dict[str, object]:
    payloads = _read_zip(path)
    manifest_name = "AUGMENTED_PACKAGE_MANIFEST.json"
    checksums_name = "AUGMENTED_PACKAGE_CHECKSUMS.json"
    if manifest_name not in payloads or checksums_name not in payloads:
        raise ValueError("augmented package lacks its manifest/checksums")
    manifest = json.loads(payloads[manifest_name])
    checksums = json.loads(payloads[checksums_name])
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "VALID"
        or checksums.get("schema_version") != "h2-augmented-package-checksums.v1"
    ):
        raise ValueError("augmented package metadata schema/status differs")
    rows = manifest.get("members")
    files = checksums.get("files")
    if not isinstance(rows, list) or not isinstance(files, Mapping):
        raise ValueError("augmented package inventories are invalid")
    expected = set(payloads) - {checksums_name}
    if set(map(str, files)) != expected:
        raise ValueError("augmented package checksum membership differs")
    for name, raw in files.items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"invalid checksum row: {name}")
        payload = payloads[str(name)]
        if raw.get("sha256") != _sha256(payload) or raw.get("bytes") != len(payload):
            raise ValueError(f"augmented package checksum differs: {name}")
    declared = {str(row.get("member")): row for row in rows if isinstance(row, Mapping)}
    if len(declared) != len(rows) or set(declared) != set(payloads) - {
        manifest_name,
        checksums_name,
    }:
        raise ValueError("augmented package manifest membership differs")
    if manifest.get("member_count_excluding_augmented_metadata") != len(rows):
        raise ValueError("augmented package manifest count differs")
    for name, raw in declared.items():
        payload = payloads[name]
        if raw.get("sha256") != _sha256(payload) or raw.get("bytes") != len(payload):
            raise ValueError(f"augmented package manifest checksum differs: {name}")
    svg_names = sorted(
        name for name in payloads if name.startswith("plots/") and name.endswith(".svg")
    )
    if len(svg_names) < 3 or "plots/PLOT_GUIDE.md" not in payloads:
        raise ValueError("augmented package lacks required evidence-backed plots")
    if not any(name.startswith("controller/axis_selections/") for name in payloads):
        raise ValueError("augmented package lacks axis-selection receipts")
    missing_metrics = [name for name in REQUIRED_METRIC_MEMBERS if name not in payloads]
    if missing_metrics:
        raise ValueError(
            "augmented package lacks required metric supplement: "
            + ", ".join(missing_metrics)
        )
    metric_rows = _csv_rows(payloads[REQUIRED_METRIC_MEMBERS[0]])
    metric_provenance = json.loads(payloads[REQUIRED_METRIC_MEMBERS[2]])
    if len(metric_rows) != 80 or metric_provenance.get("status") != "VALID":
        raise ValueError("required metric supplement row count/status differs")
    if {str(row.get("metric_id") or "") for row in metric_rows} != {
        "cluster_purity",
        "short_turn_recall",
        "clean_evidence_yield",
        "time_to_clean_evidence",
    }:
        raise ValueError("required metric supplement family coverage differs")
    measured_splits = {
        str(row.get("evidence_split") or "")
        for row in metric_rows
        if row.get("metric_status") == "COMPUTED"
    }
    if measured_splits != {"development", "evaluation"}:
        raise ValueError("required metric supplement split coverage differs")
    if metric_provenance.get("development_and_heldout_evidence_pooled") is not False:
        raise ValueError("required metric supplement split firewall is absent")
    missing_transcript = [
        name for name in REQUIRED_TRANSCRIPT_MEMBERS if name not in payloads
    ]
    if missing_transcript:
        raise ValueError(
            "augmented package lacks required transcript supplement: "
            + ", ".join(missing_transcript)
        )
    transcript_rows = _csv_rows(payloads[REQUIRED_TRANSCRIPT_MEMBERS[0]])
    transcript_provenance = json.loads(payloads[REQUIRED_TRANSCRIPT_MEMBERS[2]])
    if len(transcript_rows) != 80 or transcript_provenance.get("status") != "VALID":
        raise ValueError("required transcript supplement row count/status differs")
    if {str(row.get("metric_id") or "") for row in transcript_rows} != {
        "over_segmentation_rate",
        "under_segmentation_rate",
        "mixed_speaker_paragraph_rate",
        "words_per_paragraph",
        "paragraph_revision_count",
        "paragraph_revision_rate",
        "word_level_speaker_attribution",
        "final_stability",
        "readability_proxy",
    }:
        raise ValueError("required transcript supplement family coverage differs")
    transcript_splits = {
        str(row.get("evidence_split") or "")
        for row in transcript_rows
        if str(row.get("metric_status") or "") != "NOT_DIRECTLY_MEASURED_PARITY_ONLY"
    }
    if transcript_splits != {"development", "evaluation"}:
        raise ValueError("required transcript supplement split coverage differs")
    if (
        transcript_provenance.get("development_and_heldout_evidence_pooled")
        is not False
        or transcript_provenance.get("post_hoc_metrics_used_for_frozen_selection")
        is not False
    ):
        raise ValueError("required transcript supplement firewall is absent")
    missing_asr_comparability = [
        name for name in REQUIRED_ASR_COMPARABILITY_MEMBERS if name not in payloads
    ]
    if missing_asr_comparability:
        raise ValueError(
            "augmented package lacks ASR WER comparability evidence: "
            + ", ".join(missing_asr_comparability)
        )
    asr_rows = _csv_rows(payloads[REQUIRED_ASR_COMPARABILITY_MEMBERS[0]])
    asr_provenance = json.loads(payloads[REQUIRED_ASR_COMPARABILITY_MEMBERS[2]])
    expected_asr_row_count = len(ASR_COMPARABILITY_CONFIGURATIONS) * (
        2 * len(ASR_COMPARABILITY_STRATA) + 1
    )
    expected_asr_keys = {
        (configuration_id, policy_id, stratum, "wer")
        for configuration_id in ASR_COMPARABILITY_CONFIGURATIONS
        for policy_id in (
            "lowercase_whitespace.v1",
            "evaluation-text-normalization-punctuation-insensitive.v1",
        )
        for stratum in ASR_COMPARABILITY_STRATA
    } | {
        (
            configuration_id,
            "endpoint_window_reference_mapping.v1",
            "OVERALL",
            "final_wer",
        )
        for configuration_id in ASR_COMPARABILITY_CONFIGURATIONS
    }
    observed_asr_keys = {
        (
            str(row.get("configuration_id") or ""),
            str(row.get("scoring_policy_id") or ""),
            str(row.get("stratum") or ""),
            str(row.get("metric_id") or ""),
        )
        for row in asr_rows
    }
    if (
        len(asr_rows) != expected_asr_row_count
        or observed_asr_keys != expected_asr_keys
        or any(
            row.get("schema_version") != "h2-asr-wer-comparability-row.v2"
            for row in asr_rows
        )
        or any(
            str(row.get("scientific_selection_eligible") or "").casefold() != "false"
            for row in asr_rows
        )
    ):
        raise ValueError("ASR WER comparability row coverage/firewall differs")
    for configuration_id in ASR_COMPARABILITY_CONFIGURATIONS:
        frozen_overall = next(
            row
            for row in asr_rows
            if row["configuration_id"] == configuration_id
            and row["scoring_policy_id"] == "lowercase_whitespace.v1"
            and row["stratum"] == "OVERALL"
        )
        endpoint = next(
            row
            for row in asr_rows
            if row["configuration_id"] == configuration_id
            and row["metric_id"] == "final_wer"
        )
        if (
            frozen_overall.get("metric_status") != "SOURCE_REPORTED_AND_RECOMPUTED"
            or str(frozen_overall.get("source_reported_metric_match") or "").casefold()
            != "true"
            or endpoint.get("metric_role")
            != "ENDPOINT_WINDOW_DIAGNOSTIC_NOT_ORDINARY_WER"
            or _number(endpoint.get("denominator")) is None
        ):
            raise ValueError(
                f"ASR comparability source binding differs: {configuration_id}"
            )
        for stratum in ASR_COMPARABILITY_STRATA:
            sensitive = next(
                row
                for row in asr_rows
                if row["configuration_id"] == configuration_id
                and row["scoring_policy_id"] == "lowercase_whitespace.v1"
                and row["stratum"] == stratum
            )
            insensitive = next(
                row
                for row in asr_rows
                if row["configuration_id"] == configuration_id
                and row["scoring_policy_id"]
                == "evaluation-text-normalization-punctuation-insensitive.v1"
                and row["stratum"] == stratum
            )
            punctuation_fields = (
                "reference_tokens_for_punctuation_rate",
                "hypothesis_tokens_for_punctuation_rate",
                "reference_ascii_punctuation_tokens",
                "hypothesis_ascii_punctuation_tokens",
                "reference_ascii_punctuation_token_rate",
                "hypothesis_ascii_punctuation_token_rate",
                "punctuation_sensitive_minus_insensitive_wer",
            )
            sensitive_numbers = {
                field: _number(sensitive.get(field)) for field in punctuation_fields
            }
            insensitive_numbers = {
                field: _number(insensitive.get(field)) for field in punctuation_fields
            }
            if sensitive.get("metric_status") == "UNDEFINED_EMPTY_STRATUM":
                continue
            if sensitive_numbers != insensitive_numbers or any(
                sensitive_numbers[field] is None
                for field in punctuation_fields
                if field
                not in {
                    "hypothesis_ascii_punctuation_token_rate",
                    "punctuation_sensitive_minus_insensitive_wer",
                }
            ):
                raise ValueError(
                    "ASR punctuation diagnostic coverage differs: "
                    f"{configuration_id}/{stratum}"
                )
            reference_denominator = float(
                sensitive_numbers["reference_tokens_for_punctuation_rate"]
            )
            hypothesis_denominator = float(
                sensitive_numbers["hypothesis_tokens_for_punctuation_rate"]
            )
            reference_count = float(
                sensitive_numbers["reference_ascii_punctuation_tokens"]
            )
            hypothesis_count = float(
                sensitive_numbers["hypothesis_ascii_punctuation_tokens"]
            )
            reference_rate = float(
                sensitive_numbers["reference_ascii_punctuation_token_rate"]
            )
            raw_hypothesis_rate = sensitive_numbers[
                "hypothesis_ascii_punctuation_token_rate"
            ]
            gap = sensitive_numbers["punctuation_sensitive_minus_insensitive_wer"]
            sensitive_wer = _number(sensitive.get("value"))
            insensitive_wer = _number(insensitive.get("value"))
            if (
                reference_denominator <= 0
                or hypothesis_denominator < 0
                or not 0 <= reference_count <= reference_denominator
                or not 0 <= hypothesis_count <= hypothesis_denominator
                or not math.isclose(
                    reference_rate,
                    reference_count / reference_denominator,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                or (hypothesis_denominator == 0 and raw_hypothesis_rate is not None)
                or (
                    hypothesis_denominator > 0
                    and (
                        raw_hypothesis_rate is None
                        or not math.isclose(
                            float(raw_hypothesis_rate),
                            hypothesis_count / hypothesis_denominator,
                            rel_tol=0.0,
                            abs_tol=1e-12,
                        )
                    )
                )
                or (
                    (sensitive_wer is None or insensitive_wer is None)
                    and gap is not None
                )
                or (
                    sensitive_wer is not None
                    and insensitive_wer is not None
                    and (
                        gap is None
                        or not math.isclose(
                            float(gap),
                            sensitive_wer - insensitive_wer,
                            rel_tol=0.0,
                            abs_tol=1e-12,
                        )
                    )
                )
            ):
                raise ValueError(
                    "ASR punctuation diagnostic values differ: "
                    f"{configuration_id}/{stratum}"
                )
    commonvoice_source = asr_provenance.get("commonvoice_normalization_source")
    punctuation_diagnostics = asr_provenance.get("punctuation_diagnostics")
    if (
        asr_provenance.get("schema_version") != "h2-asr-wer-comparability-provenance.v2"
        or asr_provenance.get("status") != "VALID"
        or asr_provenance.get("row_count") != expected_asr_row_count
        or asr_provenance.get("neural_inference_rerun") is not False
        or asr_provenance.get("scientific_runtime_or_policy_changed") is not False
        or asr_provenance.get("post_run_rescore_used_for_development_selection")
        is not False
        or asr_provenance.get("post_run_rescore_used_for_heldout_policy_change")
        is not False
        or asr_provenance.get("development_and_heldout_evidence_pooled") is not False
        or asr_provenance.get("frozen_metric_preserved") is not True
        or asr_provenance.get("source_reported_frozen_metrics_recomputed_exactly")
        is not True
        or asr_provenance.get(
            "endpoint_final_wer_declared_noncomparable_to_exported_transcript_wer"
        )
        is not True
        or not isinstance(punctuation_diagnostics, Mapping)
        or punctuation_diagnostics.get("character_set") != "ASCII string.punctuation"
        or punctuation_diagnostics.get(
            "reference_and_hypothesis_punctuation_token_rates_reported"
        )
        is not True
        or punctuation_diagnostics.get("causal_error_attribution_claimed") is not False
        or punctuation_diagnostics.get("scientific_selection_eligible") is not False
        or not isinstance(commonvoice_source, Mapping)
        or commonvoice_source.get("member") != ASR_COMMONVOICE_POLICY_MEMBER
        or commonvoice_source.get("policy_id")
        != "evaluation-text-normalization-punctuation-insensitive.v1"
        or ASR_COMMONVOICE_POLICY_MEMBER not in payloads
        or commonvoice_source.get("sha256")
        != _sha256(payloads[ASR_COMMONVOICE_POLICY_MEMBER])
        or manifest.get("asr_wer_comparability_provenance") != asr_provenance
    ):
        raise ValueError("ASR WER comparability provenance differs")
    host_io_provenance = _validate_host_io_members(payloads)
    if manifest.get("host_io_interference_provenance") != host_io_provenance:
        raise ValueError("host-I/O manifest provenance differs")
    serial_host_io_provenance = _validate_serial_host_io_members(payloads)
    if manifest.get("serial_resource_host_io_provenance") != serial_host_io_provenance:
        raise ValueError("serial host-I/O manifest provenance differs")
    missing_overlap = [
        name for name in REQUIRED_OVERLAP_MEMBERS if name not in payloads
    ]
    if missing_overlap:
        raise ValueError(
            "augmented package lacks overlap-stratified supplement: "
            + ", ".join(missing_overlap)
        )
    overlap_rows = _csv_rows(payloads[REQUIRED_OVERLAP_MEMBERS[0]])
    overlap_provenance = json.loads(payloads[REQUIRED_OVERLAP_MEMBERS[2]])
    expected_overlap_count = (
        len(OVERLAP_CONFIGURATIONS)
        * len(OVERLAP_COMPOSITIONS)
        * len(OVERLAP_CONDITIONS)
        * len(OVERLAP_METRICS)
    )
    overlap_keys = {
        (
            str(row.get("configuration_id") or ""),
            str(row.get("composition") or ""),
            str(row.get("condition") or ""),
            str(row.get("metric_id") or ""),
        )
        for row in overlap_rows
    }
    expected_overlap_keys = {
        (configuration, composition, condition, metric_id)
        for configuration in OVERLAP_CONFIGURATIONS
        for composition in OVERLAP_COMPOSITIONS.values()
        for condition in OVERLAP_CONDITIONS
        for _report, metric_id, _aggregation in OVERLAP_METRICS
    }
    if (
        len(overlap_rows) != expected_overlap_count
        or overlap_keys != expected_overlap_keys
    ):
        raise ValueError("overlap-stratified metric coverage differs")
    computed_overlap = [
        row
        for row in overlap_rows
        if str(row.get("metric_status") or "").startswith("COMPUTED")
    ]
    if not computed_overlap or any(
        row.get("evidence_split") != "development"
        or _number(row.get("value")) is None
        or _number(row.get("ci_lower_95")) is None
        or _number(row.get("ci_upper_95")) is None
        for row in computed_overlap
    ):
        raise ValueError("computed overlap-stratified metrics are incomplete")
    if (
        overlap_provenance.get("status") != "VALID"
        or overlap_provenance.get("row_count") != expected_overlap_count
        or overlap_provenance.get("development_only") is not True
        or overlap_provenance.get("evaluation_material_inspected") is not False
        or overlap_provenance.get("post_hoc_metrics_used_for_frozen_selection")
        is not False
        or overlap_provenance.get("scientific_runtime_or_policy_changed") is not False
        or overlap_provenance.get("source_case_sets_and_order_identical") is not True
        or overlap_provenance.get("only_result_affecting_axis_varied")
        != "overlap_policy"
        or overlap_provenance.get("selected_overlap_policy")
        not in OVERLAP_CONFIGURATIONS
    ):
        raise ValueError("overlap-stratified provenance/firewall differs")
    missing_boundary = [
        name for name in REQUIRED_BOUNDARY_MEMBERS if name not in payloads
    ]
    if missing_boundary:
        raise ValueError(
            "augmented package lacks boundary-correction diagnostics: "
            + ", ".join(missing_boundary)
        )
    boundary_rows = _csv_rows(payloads[REQUIRED_BOUNDARY_MEMBERS[0]])
    boundary_case_rows = _csv_rows(payloads[REQUIRED_BOUNDARY_MEMBERS[1]])
    boundary_provenance = json.loads(payloads[REQUIRED_BOUNDARY_MEMBERS[3]])
    boundary_by_configuration = {
        str(row.get("configuration_id") or ""): row for row in boundary_rows
    }
    expected_boundary_ms = {
        configuration_id: int(configuration_id.rsplit("_", 1)[-1][:-2])
        for configuration_id in BOUNDARY_CONFIGURATIONS
    }
    if (
        len(boundary_rows) != len(BOUNDARY_CONFIGURATIONS)
        or set(boundary_by_configuration) != set(BOUNDARY_CONFIGURATIONS)
        or any(
            int(boundary_by_configuration[configuration_id]["boundary_correction_ms"])
            != correction_ms
            for configuration_id, correction_ms in expected_boundary_ms.items()
        )
        or any(row.get("evidence_split") != "development" for row in boundary_rows)
    ):
        raise ValueError("boundary-correction summary coverage differs")
    selected_boundary_rows = [
        row
        for row in boundary_rows
        if str(row.get("selected_by_development_receipt") or "").casefold() == "true"
    ]
    if len(selected_boundary_rows) != 1:
        raise ValueError("boundary-correction selected-row coverage differs")
    if any(
        row.get("initially_previous_speaker_word_time_status")
        != "UNSUPPORTED_NO_REFERENCE_WORD_TIMESTAMPS"
        or str(row.get("initially_previous_speaker_word_time_sec") or "").strip()
        for row in boundary_rows
    ):
        raise ValueError("boundary-correction word-time limitation differs")
    case_groups: dict[str, set[str]] = defaultdict(set)
    for row in boundary_case_rows:
        configuration_id = str(row.get("configuration_id") or "")
        case_id = str(row.get("case_id") or "")
        if (
            configuration_id not in BOUNDARY_CONFIGURATIONS
            or not case_id
            or case_id in case_groups[configuration_id]
            or row.get("word_pair_status") not in {"COMPUTED", "UNSUPPORTED"}
            or row.get("initially_previous_speaker_word_time_status")
            != "UNSUPPORTED_NO_REFERENCE_WORD_TIMESTAMPS"
        ):
            raise ValueError("boundary-correction case-pair row differs")
        case_groups[configuration_id].add(case_id)
    if (
        set(case_groups) != set(BOUNDARY_CONFIGURATIONS)
        or len({frozenset(values) for values in case_groups.values()}) != 1
        or any(
            len(case_groups[configuration_id])
            != int(boundary_by_configuration[configuration_id]["case_count"])
            for configuration_id in BOUNDARY_CONFIGURATIONS
        )
    ):
        raise ValueError("boundary-correction case pairing differs")
    boundary_sources = boundary_provenance.get("sources")
    if (
        boundary_provenance.get("status") != "VALID"
        or boundary_provenance.get("development_only") is not True
        or boundary_provenance.get("evaluation_material_inspected") is not False
        or boundary_provenance.get("post_hoc_metrics_used_for_frozen_selection")
        is not False
        or boundary_provenance.get("scientific_runtime_or_policy_changed") is not False
        or boundary_provenance.get("source_case_sets_and_order_identical") is not True
        or boundary_provenance.get("source_reference_payloads_identical") is not True
        or boundary_provenance.get("paired_lexical_alignments_required_identical")
        is not True
        or boundary_provenance.get("only_result_affecting_axis_varied")
        != "boundary_correction_ms"
        or boundary_provenance.get("exact_word_time_status")
        != "UNSUPPORTED_NO_REFERENCE_WORD_TIMESTAMPS"
        or boundary_provenance.get("selected_boundary_configuration")
        != selected_boundary_rows[0]["configuration_id"]
        or boundary_provenance.get("summary_row_count") != len(boundary_rows)
        or boundary_provenance.get("case_pair_row_count") != len(boundary_case_rows)
        or not isinstance(boundary_sources, list)
        or len(boundary_sources) != len(BOUNDARY_CONFIGURATIONS)
    ):
        raise ValueError("boundary-correction provenance/firewall differs")
    if any(
        not isinstance(row, Mapping)
        or str(row.get("configuration_id") or "") not in BOUNDARY_CONFIGURATIONS
        or len(str(row.get("result_sha256") or "")) != 64
        for row in boundary_sources
    ):
        raise ValueError("boundary-correction source identity differs")
    missing_science = [
        name for name in REQUIRED_SCIENCE_TABLE_MEMBERS if name not in payloads
    ]
    if missing_science:
        raise ValueError(
            "augmented package lacks source science tables: "
            + ", ".join(missing_science)
        )
    science_provenance = json.loads(payloads[REQUIRED_SCIENCE_TABLE_MEMBERS[-1]])
    science_rows = science_provenance.get("members")
    if (
        science_provenance.get("status") != "VALID"
        or science_provenance.get("tables_are_byte_exact_source_artifacts") is not True
        or science_provenance.get("development_and_heldout_evidence_pooled")
        is not False
        or not isinstance(science_rows, list)
        or len(science_rows) != 6
    ):
        raise ValueError("source science table provenance differs")
    science_by_member = {
        str(row.get("member") or ""): row
        for row in science_rows
        if isinstance(row, Mapping)
    }
    if set(science_by_member) != set(REQUIRED_SCIENCE_TABLE_MEMBERS[:-1]):
        raise ValueError("source science table provenance membership differs")
    required_columns = {
        "supplements/source_science/identity_hubness.csv": {
            "enrolled_id",
            "unknown_top1_count",
            "unknown_top1_share",
            "maximum_impostor_score",
            "mean_top1_top2_margin",
        },
        "supplements/source_science/integrated_enrollment_hubness.csv": {
            "candidate_speaker_id",
            "nearest_stranger_count",
        },
        "supplements/source_science/integrated_enrollment_qc_events.csv": {
            "cell_id",
        },
    }
    for name, row in science_by_member.items():
        payload = payloads[name]
        rows = _csv_rows(payload)
        if (
            row.get("source_sha256") != _sha256(payload)
            or row.get("row_count") != len(rows)
            or not rows
            or row.get("development_only") is not True
            or row.get("evaluation_material_inspected") is not False
        ):
            raise ValueError(f"source science table identity differs: {name}")
        expected_columns = required_columns.get(name)
        if expected_columns and not expected_columns.issubset(rows[0]):
            raise ValueError(f"source science table columns differ: {name}")
    missing_recommendations = [
        name for name in REQUIRED_RECOMMENDATION_MEMBERS if name not in payloads
    ]
    if missing_recommendations:
        raise ValueError(
            "augmented package lacks final recommendations: "
            + ", ".join(missing_recommendations)
        )
    recommendations = json.loads(payloads[REQUIRED_RECOMMENDATION_MEMBERS[0]])
    recommendation_rows = recommendations.get("roles")
    if (
        recommendations.get("schema_version") != "h2-final-recommendations.v1"
        or recommendations.get("status") != "COMPLETE_RECOMMENDATIONS"
        or recommendations.get("scientific_runtime_or_frozen_policy_changed")
        is not False
        or recommendations.get("heldout_results_used_for_retuning") is not False
        or recommendations.get("arm64_hardware_validated") is not False
        or not isinstance(recommendation_rows, list)
        or len(recommendation_rows) != 3
    ):
        raise ValueError("final recommendation contract differs")
    recommendation_by_role = {
        str(row.get("role")): row
        for row in recommendation_rows
        if isinstance(row, Mapping) and row.get("role")
    }
    if set(recommendation_by_role) != {
        "DESKTOP_REFERENCE",
        "PRODUCT_SOFTWARE_PRIMARY",
        "2GB_ARM64_CANDIDATE",
    }:
        raise ValueError("final recommendation role coverage differs")
    if (
        recommendation_by_role["DESKTOP_REFERENCE"].get("configuration_id")
        != "H2_BASELINE_REFERENCE"
        or recommendation_by_role["PRODUCT_SOFTWARE_PRIMARY"].get("configuration_id")
        not in {
            "H2_KNOWN_ONLY_OPTIMIZED",
            "H2_SESSION_ANONYMOUS_OPTIMIZED",
            "H2_SESSION_MEMORY_OPTIMIZED",
        }
        or recommendation_by_role["2GB_ARM64_CANDIDATE"].get("configuration_id")
        != "H2_PORTABLE_ONNX_FP32"
        or recommendation_by_role["2GB_ARM64_CANDIDATE"].get("recommendation_status")
        != "PREPARED_NOT_HARDWARE_VALIDATED"
    ):
        raise ValueError("final recommendation configuration mapping differs")
    expected_recommendation_payloads, expected_recommendations = (
        build_final_recommendation_supplement(payloads)
    )
    if any(
        payloads.get(name) != expected_payload
        for name, expected_payload in expected_recommendation_payloads.items()
    ):
        raise ValueError("final recommendation source binding or rendering differs")
    if manifest.get("final_recommendation_provenance") != expected_recommendations:
        raise ValueError("final recommendation manifest provenance differs")
    missing_hardware_platforms = [
        name for name in REQUIRED_HARDWARE_PLATFORM_MEMBERS if name not in payloads
    ]
    if missing_hardware_platforms:
        raise ValueError(
            "augmented package lacks hardware-platform assessment: "
            + ", ".join(missing_hardware_platforms)
        )
    hardware_platforms = json.loads(payloads[REQUIRED_HARDWARE_PLATFORM_MEMBERS[2]])
    hardware_rows = hardware_platforms.get("platforms")
    if (
        hardware_platforms.get("schema_version") != "h2-hardware-platform-assessment.v2"
        or hardware_platforms.get("status")
        != "EXPECTED_FEASIBILITY_NOT_HARDWARE_VALIDATION"
        or hardware_platforms.get("arm64_hardware_measurements_present") is not False
        or hardware_platforms.get("scientific_runtime_or_policy_changed") is not False
        or hardware_platforms.get("desktop_scientific_ranking_changed") is not False
        or hardware_platforms.get("qnn_debian_acceleration_claimed") is not False
        or not isinstance(hardware_rows, list)
        or len(hardware_rows) != 4
    ):
        raise ValueError("hardware-platform assessment contract differs")
    hardware_by_variant = {
        (str(row.get("platform_id")), str(row.get("variant"))): row
        for row in hardware_rows
        if isinstance(row, Mapping)
    }
    if set(hardware_by_variant) != {
        ("RASPBERRY_PI_COMPUTE_MODULE_5", "2GB_RAM"),
        ("RASPBERRY_PI_COMPUTE_MODULE_5", "4GB_OR_GREATER"),
        ("ARDUINO_UNO_Q", "4GB_RAM_32GB_EMMC"),
        ("ARDUINO_UNO_Q", "2GB_RAM_16GB_EMMC"),
    }:
        raise ValueError("hardware-platform variant coverage differs")
    cm5_2gb = hardware_by_variant[("RASPBERRY_PI_COMPUTE_MODULE_5", "2GB_RAM")]
    cm5_4gb = hardware_by_variant[("RASPBERRY_PI_COMPUTE_MODULE_5", "4GB_OR_GREATER")]
    uno_q_4gb = hardware_by_variant[("ARDUINO_UNO_Q", "4GB_RAM_32GB_EMMC")]
    uno_q_2gb = hardware_by_variant[("ARDUINO_UNO_Q", "2GB_RAM_16GB_EMMC")]
    measured_bounds = hardware_platforms.get("measured_desktop_bounds")
    decision = hardware_platforms.get("decision")
    if not isinstance(measured_bounds, Mapping) or not isinstance(decision, Mapping):
        raise ValueError("hardware-platform CM5 RAM decision evidence differs")
    memory_classification = str(measured_bounds.get("memory_classification") or "")
    cm5_two_gib_candidate = (
        memory_classification == "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION"
    )
    expected_cm5_2gb_role = (
        "FIRST_LEAN_ARM64_SIZING_TARGET"
        if cm5_two_gib_candidate
        else "OPTIMIZATION_EXPERIMENT_ONLY"
    )
    expected_cm5_4gb_role = (
        "SAFE_FALLBACK_AND_DEVELOPMENT_TARGET"
        if cm5_two_gib_candidate
        else "PRIMARY_ARM64_VALIDATION_TARGET"
    )
    expected_cm5_ram_recommendation = (
        "TEST_2GB_LEAN_ONNX_FIRST_WITH_4GB_FALLBACK"
        if cm5_two_gib_candidate
        else "START_WITH_4GB_KEEP_2GB_AS_OPTIMIZATION_EXPERIMENT"
    )
    if (
        cm5_2gb.get("expected_classification") != "PORT_REQUIRES_WORK"
        or cm5_2gb.get("native_pipeline_feasibility") != "PLATFORM_BLOCKER"
        or cm5_2gb.get("portable_onnx_feasibility") != "PORT_REQUIRES_WORK"
        or cm5_2gb.get("recommended_role") != expected_cm5_2gb_role
        or cm5_4gb.get("expected_classification") != "LIKELY_PORTABLE"
        or cm5_4gb.get("recommended_role") != expected_cm5_4gb_role
        or decision.get("cm5_2gb_candidate") is not cm5_two_gib_candidate
        or decision.get("cm5_ram_recommendation") != expected_cm5_ram_recommendation
        or decision.get("cm5_4gb_proven_necessary") is not False
        or decision.get("graphics_workload_assumption")
        != "SIMPLE_2D_UI_LOW_GRAPHICS_MEMORY_DEMAND"
        or decision.get("sizing_workload_driver")
        != "AUDIO_PIPELINE_MODELS_QUEUES_AND_RUNTIME"
        or uno_q_4gb.get("expected_classification") != "PORT_REQUIRES_WORK"
        or uno_q_4gb.get("recommended_role") != "SECONDARY_PORTABILITY_PROTOTYPE"
        or uno_q_2gb.get("expected_classification") != "PLATFORM_BLOCKER"
        or uno_q_2gb.get("native_pipeline_feasibility") != "PLATFORM_BLOCKER"
        or uno_q_2gb.get("recommended_role") != "HIGH_RISK_LEAN_ONNX_EXPERIMENT_ONLY"
        or any(row.get("hardware_validated") is not False for row in hardware_rows)
        or any(
            row.get("scientific_ranking_changed") is not False for row in hardware_rows
        )
        or any(
            row.get("accelerator_performance_assumed") is not False
            for row in hardware_rows
        )
        or any(
            row.get("cm5_4gb_proven_necessary") is not False for row in hardware_rows
        )
        or any(
            row.get("graphics_workload_assumption")
            != "SIMPLE_2D_UI_LOW_GRAPHICS_MEMORY_DEMAND"
            for row in hardware_rows
        )
        or any(
            row.get("sizing_workload_driver")
            != "AUDIO_PIPELINE_MODELS_QUEUES_AND_RUNTIME"
            for row in hardware_rows
        )
    ):
        raise ValueError("hardware-platform feasibility decision differs")
    expected_hardware_payloads, expected_hardware_platforms = (
        build_hardware_platform_assessment(payloads)
    )
    if any(
        payloads.get(name) != expected_payload
        for name, expected_payload in expected_hardware_payloads.items()
    ):
        raise ValueError("hardware-platform source binding or rendering differs")
    if manifest.get("hardware_platform_assessment_provenance") != (
        expected_hardware_platforms
    ):
        raise ValueError("hardware-platform manifest provenance differs")
    if manifest.get("hardware_platform_assessment_is_deployment_only") is not True:
        raise ValueError("hardware-platform deployment-only boundary differs")
    streaming_provenance = _validate_streaming_execution_provenance_members(payloads)
    if manifest.get("streaming_execution_provenance") != streaming_provenance:
        raise ValueError("streaming execution provenance manifest binding differs")
    if manifest.get("streaming_provenance_is_post_hoc_nonselection") is not True:
        raise ValueError("streaming provenance nonselection boundary differs")
    missing_long_drift = [
        name for name in REQUIRED_LONG_SESSION_DRIFT_MEMBERS if name not in payloads
    ]
    if missing_long_drift:
        raise ValueError(
            "augmented package lacks long-session drift evidence: "
            + ", ".join(missing_long_drift)
        )
    drift_rows = _csv_rows(payloads[REQUIRED_LONG_SESSION_DRIFT_MEMBERS[0]])
    drift_provenance = json.loads(payloads[REQUIRED_LONG_SESSION_DRIFT_MEMBERS[2]])
    expected_drift_count = 12 * len(LONG_SESSION_DRIFT_METRICS)
    drift_keys = {
        (
            str(row.get("split") or ""),
            str(row.get("source_recording_id") or ""),
            str(row.get("metric_id") or ""),
        )
        for row in drift_rows
    }
    if (
        len(drift_rows) != expected_drift_count
        or len(drift_keys) != expected_drift_count
        or {str(row.get("metric_id") or "") for row in drift_rows}
        != {row[0] for row in LONG_SESSION_DRIFT_METRICS}
        or {str(row.get("split") or "") for row in drift_rows}
        != {"development", "evaluation"}
        or any(
            row.get("metric_status") not in {"COMPUTED", "UNSUPPORTED_SOURCE_METRIC"}
            for row in drift_rows
        )
    ):
        raise ValueError("long-session drift metric coverage differs")
    if (
        drift_provenance.get("schema_version") != "h2-long-session-drift-provenance.v1"
        or drift_provenance.get("status") != "VALID"
        or drift_provenance.get("row_count") != expected_drift_count
        or drift_provenance.get("development_and_heldout_evidence_pooled") is not False
        or drift_provenance.get("post_hoc_metrics_used_for_frozen_selection")
        is not False
        or drift_provenance.get("scientific_runtime_or_policy_changed") is not False
        or drift_provenance.get("thermal_drift_status")
        != "UNSUPPORTED_NO_TEMPERATURE_TELEMETRY"
    ):
        raise ValueError("long-session drift provenance/firewall differs")
    expected_drift_payloads, expected_drift_provenance = (
        build_long_session_drift_supplement(payloads)
    )
    if any(
        payloads.get(name) != expected_payload
        for name, expected_payload in expected_drift_payloads.items()
    ):
        raise ValueError("long-session drift source binding or rendering differs")
    if manifest.get("long_session_drift_provenance") != expected_drift_provenance:
        raise ValueError("long-session drift manifest provenance differs")
    _validate_storage_reproducibility_members(payloads)
    _validate_ui_latency_members(payloads)
    data_firewall_provenance = _validate_data_firewall_members(payloads)
    if manifest.get("data_firewall_provenance") != data_firewall_provenance:
        raise ValueError("enrollment firewall manifest provenance differs")
    development_cpu_provenance = _validate_development_cpu_interference_members(
        payloads
    )
    if (
        manifest.get("development_cpu_interference_provenance")
        != development_cpu_provenance
        or manifest.get("development_cpu_interference_disclosed") is not True
    ):
        raise ValueError("development CPU interference manifest provenance differs")
    selector_correction_provenance = _validate_selector_correction_members(payloads)
    if (
        manifest.get("selector_correction_provenance")
        != selector_correction_provenance
        or manifest.get("selector_correction_is_pre_freeze_orchestration_only")
        is not True
    ):
        raise ValueError("selector correction manifest provenance differs")
    arm64_v2_provenance = _validate_arm64_deployment_v2_members(payloads)
    if manifest.get("arm64_deployment_v2_provenance") != arm64_v2_provenance:
        raise ValueError("ARM64 deployment-v2 manifest provenance differs")
    _validate_augmentation_source_members(payloads)
    if source_payloads is not None:
        for name, payload in source_payloads.items():
            if payloads.get(name) != payload:
                raise ValueError(f"native package member changed: {name}")
    total = sum(len(payload) for payload in payloads.values())
    if total > MAX_TOTAL_BYTES:
        raise ValueError("augmented package exceeds conservative size limit")
    streaming_qualification = streaming_provenance.get("qualification")
    if not isinstance(streaming_qualification, Mapping):
        raise ValueError("validated streaming qualification is unavailable")
    return {
        "status": "VALID",
        "path": str(path.resolve()),
        "sha256": _sha256(path.read_bytes()),
        "member_count": len(payloads),
        "plot_count": len(svg_names),
        "hardware_platform_count": len(hardware_rows),
        "streaming_qualification_case_count": int(
            streaming_qualification["case_count"]
        ),
        "total_uncompressed_bytes": total,
    }


def augment_package(
    source_zip: Path, workspace: Path, output: Path
) -> dict[str, object]:
    native = validate_package_zip(source_zip)
    source_payloads = _read_zip(source_zip)
    controller_binding = _source_controller_binding(workspace, source_payloads)
    plots, plot_rows = build_plots(source_payloads)
    axes, axis_rows = _axis_selection_payloads(workspace, source_payloads)
    metrics, metric_provenance = build_required_metric_supplement(
        source_payloads, workspace
    )
    transcript_metrics, transcript_metric_provenance = (
        build_transcript_structure_supplement(source_payloads, workspace)
    )
    asr_comparability, asr_comparability_provenance = (
        build_asr_wer_comparability_supplement(source_payloads, workspace)
    )
    host_io_payloads, host_io_provenance = _host_io_payloads(workspace, source_payloads)
    serial_host_io_payloads, serial_host_io_provenance = _serial_host_io_payloads(
        workspace, source_payloads
    )
    overlap_metrics, overlap_metric_provenance = build_overlap_stratified_supplement(
        source_payloads, workspace
    )
    boundary_metrics, boundary_metric_provenance = build_boundary_correction_supplement(
        source_payloads, workspace
    )
    science_tables, science_table_provenance = _science_source_table_payloads(
        source_payloads
    )
    recommendations, recommendation_provenance = build_final_recommendation_supplement(
        source_payloads
    )
    hardware_platforms, hardware_platform_provenance = (
        build_hardware_platform_assessment(source_payloads)
    )
    streaming_provenance_payloads, streaming_execution_provenance = (
        build_streaming_execution_provenance(source_payloads)
    )
    long_drift, long_drift_provenance = build_long_session_drift_supplement(
        source_payloads
    )
    storage_payloads, storage_provenance = _storage_reproducibility_payloads(
        workspace, source_payloads
    )
    ui_latency_payloads, ui_latency_provenance = _ui_latency_payloads(
        workspace, source_payloads
    )
    data_firewall_payloads, data_firewall_provenance = _data_firewall_payloads(
        workspace, source_payloads
    )
    development_cpu_payloads, development_cpu_provenance = (
        _development_cpu_interference_payloads(workspace, source_payloads)
    )
    selector_correction_payloads, selector_correction_provenance = (
        _selector_correction_payloads(workspace, source_payloads)
    )
    arm64_v2_payloads, arm64_v2_provenance = build_arm64_deployment_v2(source_payloads)
    augmentation_payloads, augmentation_provenance = _augmentation_source_payloads()
    additions = {
        **plots,
        **axes,
        **metrics,
        **transcript_metrics,
        **asr_comparability,
        **host_io_payloads,
        **serial_host_io_payloads,
        **overlap_metrics,
        **boundary_metrics,
        **science_tables,
        **recommendations,
        **hardware_platforms,
        **streaming_provenance_payloads,
        **long_drift,
        **storage_payloads,
        **ui_latency_payloads,
        **data_firewall_payloads,
        **development_cpu_payloads,
        **selector_correction_payloads,
        **arm64_v2_payloads,
        **augmentation_payloads,
    }
    overlap = set(source_payloads) & set(additions)
    if overlap:
        raise ValueError(
            f"supplement would overwrite native members: {sorted(overlap)}"
        )
    source_sha = str(native["sha256"])
    native_manifest = json.loads(source_payloads["PACKAGE_MANIFEST.json"])
    evidence_timestamp = native_manifest.get("evidence_completed_at_utc")
    member_rows = [
        {
            "member": name,
            "origin": (
                "native_validated_package"
                if name in source_payloads
                else "post_run_checksum_bound_supplement"
            ),
            "sha256": _sha256(payload),
            "bytes": len(payload),
        }
        for name, payload in sorted({**source_payloads, **additions}.items())
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "VALID",
        "evidence_completed_at_utc": evidence_timestamp,
        "source_native_zip": str(source_zip.resolve()),
        "source_native_zip_sha256": source_sha,
        "source_native_validation": native,
        "controller_binding": controller_binding,
        "scientific_content_unchanged": True,
        "scientific_policy_or_selection_changed": False,
        "plots_are_post_hoc_presentation_derivatives": True,
        "required_metrics_are_post_hoc_immutable_result_derivatives": True,
        "required_transcript_metrics_are_post_hoc_immutable_result_derivatives": True,
        "asr_wer_comparability_is_post_hoc_immutable_result_derivative": True,
        "host_io_evidence_is_post_hoc_nonselection_diagnostic": True,
        "serial_resource_host_io_is_post_hoc_eligibility_evidence": True,
        "development_cpu_interference_disclosed": True,
        "selector_correction_is_pre_freeze_orchestration_only": True,
        "overlap_stratification_is_post_hoc_immutable_result_derivative": True,
        "boundary_correction_pairing_is_post_hoc_immutable_result_derivative": True,
        "hardware_platform_assessment_is_deployment_only": True,
        "streaming_provenance_is_post_hoc_nonselection": True,
        "plot_provenance": plot_rows,
        "axis_selection_receipts": axis_rows,
        "required_metric_provenance": metric_provenance,
        "required_transcript_metric_provenance": transcript_metric_provenance,
        "asr_wer_comparability_provenance": asr_comparability_provenance,
        "host_io_interference_provenance": host_io_provenance,
        "serial_resource_host_io_provenance": serial_host_io_provenance,
        "overlap_stratified_metric_provenance": overlap_metric_provenance,
        "boundary_correction_metric_provenance": boundary_metric_provenance,
        "science_source_table_provenance": science_table_provenance,
        "final_recommendation_provenance": recommendation_provenance,
        "hardware_platform_assessment_provenance": hardware_platform_provenance,
        "streaming_execution_provenance": streaming_execution_provenance,
        "long_session_drift_provenance": long_drift_provenance,
        "storage_reproducibility_provenance": storage_provenance,
        "ui_event_latency_provenance": ui_latency_provenance,
        "data_firewall_provenance": data_firewall_provenance,
        "development_cpu_interference_provenance": development_cpu_provenance,
        "selector_correction_provenance": selector_correction_provenance,
        "arm64_deployment_v2_provenance": arm64_v2_provenance,
        "augmentation_source_provenance": augmentation_provenance,
        "member_count_excluding_augmented_metadata": len(member_rows),
        "members": member_rows,
    }
    payloads = {
        **source_payloads,
        **additions,
        "AUGMENTED_PACKAGE_MANIFEST.json": _canonical_json(manifest),
    }
    checksum_rows = {
        name: {"sha256": _sha256(payload), "bytes": len(payload)}
        for name, payload in sorted(payloads.items())
    }
    payloads["AUGMENTED_PACKAGE_CHECKSUMS.json"] = _canonical_json(
        {
            "schema_version": "h2-augmented-package-checksums.v1",
            "files": checksum_rows,
        }
    )
    package_sha = _deterministic_zip(payloads, output)
    validation = validate_augmented_package(output, source_payloads=source_payloads)
    if validation["sha256"] != package_sha:
        raise ValueError("augmented package changed after deterministic ZIP creation")
    receipt = {
        "schema_version": "h2-augmented-package-receipt.v1",
        "status": "VALID",
        "upload_path": str(output.resolve()),
        "sha256": package_sha,
        "source_native_zip": str(source_zip.resolve()),
        "source_native_zip_sha256": source_sha,
        "validation": validation,
    }
    receipt_path = output.with_suffix(output.suffix + ".receipt.json")
    _atomic_write(receipt_path, _canonical_json(receipt))
    return {**receipt, "receipt_path": str(receipt_path.resolve())}


def _latest_native_zip(root: Path) -> Path:
    candidates = sorted(
        (
            path
            for path in root.glob("h2_complete_product_pipeline_*.zip")
            if not path.name.endswith("_with_plots.zip")
        ),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )
    if not candidates:
        raise FileNotFoundError(f"no native H2 final ZIP found under {root}")
    return candidates[-1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", type=Path)
    args = parser.parse_args(argv)
    if args.validate_only is not None:
        print(json.dumps(validate_augmented_package(args.validate_only), indent=2))
        return 0
    source = (args.source_zip or _latest_native_zip(args.package_root)).resolve(
        strict=True
    )
    output = (args.output or source.with_name(f"{source.stem}_with_plots.zip")).resolve(
        strict=False
    )
    if output == source:
        raise ValueError("augmented output must not overwrite the native ZIP")
    result = augment_package(source, args.workspace.resolve(strict=True), output)
    print(json.dumps(result, indent=2))
    print(f"UPLOAD THIS FILE TO CHATGPT:\n{result['upload_path']}")
    print(f"SHA-256:\n{result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
