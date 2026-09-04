"""Bounded Prompt-7 production-candidate selection and hardening controller."""

from __future__ import annotations

from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[2]
SCOPE_ID = "full_pipeline_prompts_4_8_eight_day_c_only.v1"
SCOPE_CLASS = "BOUNDED_REDUCED"
ORIGINAL_FULL_SCOPE_COMPLETE = False
PROMPT5_MARKER = "COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1"
PROMPT6_MARKER = "COMPLETE_EXTENDED_PIPELINE_EVALUATION_REDUCED_8DAY_V1"
PROMPT7_MARKER = "COMPLETE_PRODUCTION_CANDIDATE_HARDENING_REDUCED_8DAY_V1"
PROMPT_INDEX = 7
MINIMUM_FREE_SPACE_GIB = 35
MINIMUM_FREE_SPACE_BYTES = MINIMUM_FREE_SPACE_GIB * 1024**3
DEFAULT_ROOT = (
    TOOL_ROOT
    / "automated_runs/full_pipeline_production_candidate_hardening_reduced_8day_v1"
)
DEFAULT_AMENDMENT = (
    TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
)
DEFAULT_PROGRAM_STATE = TOOL_ROOT / "runs/full_pipeline_program/PROGRAM_STATE.json"
DEFAULT_PI_DEPLOYMENT_STEERING = (
    TOOL_ROOT / "runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json"
)
PI_DEPLOYMENT_STEERING_SHA256 = (
    "f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4"
)
PI_SHORTLIST_FILE = "raspberry_pi_candidate_shortlist.json"
PI_SHORTLIST_SCHEMA = "full-pipeline-raspberry-pi-candidate-shortlist.v1"
REPORT_CHECKSUMS_FILE = "report_checksums.json"
MATRIX_PATH = TOOL_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
RUNTIME_PATH = TOOL_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
SELECTION_POLICY_DOCUMENT = TOOL_ROOT / "docs/full_pipeline/PIPELINE_MATRIX.md"
LICENSE_DOCUMENT = TOOL_ROOT / "docs/full_pipeline/LICENSE_AND_ASSET_MANIFEST.md"

ANCHOR_PIPELINES = (
    "fullpipe_v1_ao_dr_ir",  # AO-H2
    "fullpipe_v1_ag_dr_ir",  # AG-H2
    "fullpipe_v1_ao_dw_ir",  # AO-H4
    "fullpipe_v1_ag_dw_ir",  # AG-H4
    "fullpipe_v1_ao_dr_ie",  # AO-H5
    "fullpipe_v1_ag_dr_ie",  # AG-H5
)

PROMPT5_REQUIRED_FILES = (
    "all18_finalist_summary.csv",
    "all18_asr.csv",
    "all18_diarization.csv",
    "all18_identity.csv",
    "all18_speaker_attributed_transcript.csv",
    "all18_streaming.csv",
    "all18_resources.csv",
    "all18_failures.csv",
    "paired_comparisons.csv",
    "bootstrap_intervals.csv",
    "evaluation_report.md",
    "prompt5_authorization.json",
    "all18_deployment_evidence.json",
)

PROMPT6_REQUIRED_FILES = (
    "extended_summary.csv",
    "true_streaming_asr.csv",
    "online_diarization.csv",
    "online_identity.csv",
    "ux_latency.csv",
    "label_revision.csv",
    "native_results.csv",
    "long_session_results.csv",
    "reliability_results.csv",
    "serial_resources.csv",
    "failure_analysis.md",
    "extended_report.md",
    "hardening_input_manifest.json",
    "extended_deployment_evidence.json",
)

REQUIRED_PROMPT7_REPORTS = (
    "production_candidate_catalog.yaml",
    "production_candidate_summary.csv",
    "PRIMARY_PIPELINE.md",
    "FALLBACK_PIPELINE.md",
    "ALTERNATIVE_PIPELINE.md",
    "DEMO_RUNBOOK.md",
    "TROUBLESHOOTING.md",
    "VALIDATION_CHECKLIST.md",
    PI_SHORTLIST_FILE,
    REPORT_CHECKSUMS_FILE,
)


def scope_fields() -> dict[str, object]:
    return {
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": ORIGINAL_FULL_SCOPE_COMPLETE,
    }


__all__ = [
    "ANCHOR_PIPELINES",
    "DEFAULT_AMENDMENT",
    "DEFAULT_PROGRAM_STATE",
    "DEFAULT_PI_DEPLOYMENT_STEERING",
    "DEFAULT_ROOT",
    "LICENSE_DOCUMENT",
    "MATRIX_PATH",
    "MINIMUM_FREE_SPACE_BYTES",
    "ORIGINAL_FULL_SCOPE_COMPLETE",
    "PROMPT5_MARKER",
    "PROMPT6_MARKER",
    "PROMPT7_MARKER",
    "PROMPT_INDEX",
    "PI_DEPLOYMENT_STEERING_SHA256",
    "PI_SHORTLIST_FILE",
    "PI_SHORTLIST_SCHEMA",
    "REQUIRED_PROMPT7_REPORTS",
    "REPORT_CHECKSUMS_FILE",
    "RUNTIME_PATH",
    "SCOPE_CLASS",
    "SCOPE_ID",
    "SELECTION_POLICY_DOCUMENT",
    "TOOL_ROOT",
    "scope_fields",
]
