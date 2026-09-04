"""Bounded Prompt-6 true-streaming and reliability evaluation controller.

This additive package contains orchestration, bounded panel selection, and
reporting only.  Neural inference remains in the checksum-bound common
full-pipeline runtime and Prompt-3 evaluation worker.
"""

from __future__ import annotations

from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[2]
SCOPE_ID = "full_pipeline_prompts_4_8_eight_day_c_only.v1"
SCOPE_CLASS = "BOUNDED_REDUCED"
ORIGINAL_FULL_SCOPE_COMPLETE = False
PROMPT5_COMPLETION_MARKER = "COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1"
PROMPT6_COMPLETION_MARKER = "COMPLETE_EXTENDED_PIPELINE_EVALUATION_REDUCED_8DAY_V1"
PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA = "full-pipeline-all18-deployment-evidence.v1"
PROMPT6_DEPLOYMENT_EVIDENCE_SCHEMA = "full-pipeline-extended-deployment-evidence.v1"
PI_DEPLOYMENT_STEERING_SHA256 = (
    "f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4"
)
SELECTION_SEED = 3800
MINIMUM_FREE_SPACE_GIB = 35
MINIMUM_FREE_SPACE_BYTES = MINIMUM_FREE_SPACE_GIB * 1024**3
NOMINAL_STAGE_TARGET_HOURS = 30
MAXIMUM_ACCURACY_JOBS = 2
RESOURCE_CONCURRENCY = 1

MANDATORY_ANCHORS = (
    "fullpipe_v1_ao_dr_ir",  # AO-H2
    "fullpipe_v1_ag_dr_ir",  # AG-H2
    "fullpipe_v1_ao_dw_ir",  # AO-H4
    "fullpipe_v1_ag_dw_ir",  # AG-H4
    "fullpipe_v1_ao_dr_ie",  # AO-H5
    "fullpipe_v1_ag_dr_ie",  # AG-H5
)
RELIABILITY_FAULTS = (
    "microphone_device_selection",
    "device_reconnect",
    "sample_rate_mismatch",
    "silence",
    "continuous_session",
    "sudden_stop",
    "worker_restart",
    "queue_pressure",
    "slow_ui",
    "no_enrolled_speakers",
    "corrupted_enrollment_profile",
    "file_end",
    "repeated_sessions",
)

DEFAULT_ROOT = TOOL_ROOT / (
    "automated_runs/full_pipeline_extended_evaluation_reduced_8day_v1"
)
DEFAULT_REPORT_ROOT = TOOL_ROOT / (
    "JustPeachyResearchSummaries/full_pipeline/extended/"
    "full_speech_pipeline_v1_reduced_8day_v1"
)
DEFAULT_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks/full_pipeline/full_speech_pipeline_v1"
DEFAULT_CASE_MANIFEST = DEFAULT_PROTOCOL_ROOT / "evaluation/case_manifest.jsonl"
DEFAULT_ENROLLMENT_REGISTRY = (
    DEFAULT_PROTOCOL_ROOT / "evaluation/enrollment/enrollment_registry.jsonl"
)
DEFAULT_PROGRAM_STATE = TOOL_ROOT / "runs/full_pipeline_program/PROGRAM_STATE.json"
DEFAULT_AMENDMENT = (
    TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
)
DEFAULT_PI_DEPLOYMENT_STEERING = (
    TOOL_ROOT / "runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json"
)
DEFAULT_SHARED_CACHE = TOOL_ROOT / "JustPeachyResults/full_pipeline/_shared_cache"
DEFAULT_PROMPT5_WORKSPACE = TOOL_ROOT / (
    "automated_runs/full_pipeline_core_evaluation_reduced_8day_v1"
)
DEFAULT_PROMPT5_COMPLETION = DEFAULT_PROMPT5_WORKSPACE / "completion_marker.json"


def scope_fields() -> dict[str, object]:
    return {
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": ORIGINAL_FULL_SCOPE_COMPLETE,
    }


__all__ = [
    "DEFAULT_AMENDMENT",
    "DEFAULT_CASE_MANIFEST",
    "DEFAULT_ENROLLMENT_REGISTRY",
    "DEFAULT_PI_DEPLOYMENT_STEERING",
    "DEFAULT_PROGRAM_STATE",
    "DEFAULT_PROMPT5_COMPLETION",
    "DEFAULT_PROTOCOL_ROOT",
    "DEFAULT_REPORT_ROOT",
    "DEFAULT_ROOT",
    "DEFAULT_SHARED_CACHE",
    "MANDATORY_ANCHORS",
    "MAXIMUM_ACCURACY_JOBS",
    "NOMINAL_STAGE_TARGET_HOURS",
    "MINIMUM_FREE_SPACE_BYTES",
    "ORIGINAL_FULL_SCOPE_COMPLETE",
    "PI_DEPLOYMENT_STEERING_SHA256",
    "PROMPT5_COMPLETION_MARKER",
    "PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA",
    "PROMPT6_COMPLETION_MARKER",
    "PROMPT6_DEPLOYMENT_EVIDENCE_SCHEMA",
    "RELIABILITY_FAULTS",
    "RESOURCE_CONCURRENCY",
    "SCOPE_CLASS",
    "SCOPE_ID",
    "SELECTION_SEED",
    "TOOL_ROOT",
    "scope_fields",
]
