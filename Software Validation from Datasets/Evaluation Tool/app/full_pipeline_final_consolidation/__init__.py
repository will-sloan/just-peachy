"""Bounded Prompt-8 evidence consolidation for the eight-day program."""

from __future__ import annotations

from pathlib import Path

from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES as PI_DEPLOYMENT_ATTRIBUTES,
    FUTURE_LINUX_ARM64_VALIDATION as PI_FUTURE_LINUX_ARM64_TESTS,
    FUTURE_TARGET_HARDWARE_TESTS as PI_FUTURE_TESTS,
    LINUX_ARM64_PORTABILITY_CLASSES as PI_LINUX_ARM64_PORTABILITY_CLASSES,
    RASPBERRY_PI_CANDIDATE_FIELDS as PI_CANDIDATE_FIELDS,
    TWO_GIB_FEASIBILITY_CLASSES as PI_FEASIBILITY_CLASSES,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
SCOPE_ID = "full_pipeline_prompts_4_8_eight_day_c_only.v1"
SCOPE_CLASS = "BOUNDED_REDUCED"
ORIGINAL_FULL_SCOPE_COMPLETE = False
PROMPT_INDEX = 8
MINIMUM_FREE_SPACE_GIB = 35
MINIMUM_FREE_SPACE_BYTES = MINIMUM_FREE_SPACE_GIB * 1024**3

MANDATORY_EXTENDED_ANCHORS = (
    "fullpipe_v1_ao_dr_ir",  # AO-H2
    "fullpipe_v1_ag_dr_ir",  # AG-H2
    "fullpipe_v1_ao_dw_ir",  # AO-H4
    "fullpipe_v1_ag_dw_ir",  # AG-H4
    "fullpipe_v1_ao_dr_ie",  # AO-H5
    "fullpipe_v1_ag_dr_ie",  # AG-H5
)

COMPLETION_MARKERS = {
    4: "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE_REDUCED_8DAY_V1",
    5: "COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1",
    6: "COMPLETE_EXTENDED_PIPELINE_EVALUATION_REDUCED_8DAY_V1",
    7: "COMPLETE_PRODUCTION_CANDIDATE_HARDENING_REDUCED_8DAY_V1",
    8: "COMPLETE_FULL_PIPELINE_PROGRAM_REDUCED_8DAY_V1",
}
RESERVED_ORIGINAL_MARKER = "COMPLETE_FULL_PIPELINE_PROGRAM"

DEFAULT_ROOT = (
    TOOL_ROOT / "automated_runs/full_pipeline_final_consolidation_reduced_8day_v1"
)
DEFAULT_OUTPUT_ROOT = (
    TOOL_ROOT
    / "JustPeachyResearchSummaries/full_pipeline/final/full_pipeline_program_reduced_8day_v1"
)
DEFAULT_ZIP = DEFAULT_OUTPUT_ROOT.with_suffix(".zip")
DEFAULT_AMENDMENT = (
    TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
)
DEFAULT_EXECUTION_POLICY_ADDENDUM = (
    TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_EXECUTION_POLICY_ADDENDUM.json"
)
DEFAULT_ADAPTER_REGISTRY = (
    TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_ADAPTERS.json"
)
DEFAULT_PI_DEPLOYMENT_STEERING = (
    TOOL_ROOT / "runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json"
)
DEFAULT_PROGRAM_STATE = TOOL_ROOT / "runs/full_pipeline_program/PROGRAM_STATE.json"
DEFAULT_MATRIX = TOOL_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
DEFAULT_RUNTIME = (
    TOOL_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
)
DEFAULT_LICENSE_DOCUMENT = (
    TOOL_ROOT / "docs/full_pipeline/LICENSE_AND_ASSET_MANIFEST.md"
)

PI_HANDOFF_FILENAME = "RASPBERRY_PI_DEPLOYMENT_HANDOFF.json"

FINAL_OUTPUTS = (
    "FINAL_PIPELINE_REPORT.md",
    "FINAL_PIPELINE_RANKING.csv",
    "PIPELINE_PARETO_FRONTIER.csv",
    "PIPELINE_FAILURE_ANALYSIS.md",
    "FINE_TUNING_CANDIDATES.md",
    "XVF3800_INTEGRATION_HANDOFF.md",
    PI_HANDOFF_FILENAME,
    "REPRODUCIBILITY_MANIFEST.json",
    "RESULT_FILE_INVENTORY.csv",
    "FINAL_RUNBOOK.md",
)

REQUIRED_STAGE_BASENAMES = {
    4: (
        "development_matrix.csv",
        "development_summary.csv",
        "extended_set.yaml",
        "development_report.md",
        "metric_guide.md",
        "failure_inventory.csv",
        "resource_spot_checks.csv",
    ),
    5: (
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
        "all18_deployment_evidence.json",
        "evaluation_report.md",
        "prompt5_authorization.json",
    ),
    6: (
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
        "failure_inventory.csv",
        "failure_analysis.md",
        "extended_report.md",
        "analysis.json",
        "licensing_provenance.json",
        "hardening_input_manifest.json",
        "extended_deployment_evidence.json",
    ),
    7: (
        "production_candidate_catalog.yaml",
        "production_candidate_summary.csv",
        "PRIMARY_PIPELINE.md",
        "FALLBACK_PIPELINE.md",
        "ALTERNATIVE_PIPELINE.md",
        "DEMO_RUNBOOK.md",
        "TROUBLESHOOTING.md",
        "VALIDATION_CHECKLIST.md",
        "technical_ranking.csv",
        "licensing_ranking.csv",
        "pareto_frontier.csv",
        "failure_inventory.csv",
        "licensing_provenance.json",
        "acceptance_summary.csv",
        "evidence_index.json",
        "h2_simplicity_measurement.csv",
        "common_demo_production_catalog.yaml",
        "raspberry_pi_candidate_shortlist.json",
    ),
}


def scope_fields() -> dict[str, object]:
    return {
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": ORIGINAL_FULL_SCOPE_COMPLETE,
    }


__all__ = [
    "COMPLETION_MARKERS",
    "DEFAULT_ADAPTER_REGISTRY",
    "DEFAULT_AMENDMENT",
    "DEFAULT_EXECUTION_POLICY_ADDENDUM",
    "DEFAULT_LICENSE_DOCUMENT",
    "DEFAULT_MATRIX",
    "DEFAULT_OUTPUT_ROOT",
    "DEFAULT_PI_DEPLOYMENT_STEERING",
    "DEFAULT_PROGRAM_STATE",
    "DEFAULT_ROOT",
    "DEFAULT_RUNTIME",
    "DEFAULT_ZIP",
    "FINAL_OUTPUTS",
    "MANDATORY_EXTENDED_ANCHORS",
    "MINIMUM_FREE_SPACE_BYTES",
    "PI_CANDIDATE_FIELDS",
    "PI_DEPLOYMENT_ATTRIBUTES",
    "PI_FEASIBILITY_CLASSES",
    "PI_FUTURE_TESTS",
    "PI_FUTURE_LINUX_ARM64_TESTS",
    "PI_HANDOFF_FILENAME",
    "PI_LINUX_ARM64_PORTABILITY_CLASSES",
    "PROMPT_INDEX",
    "REQUIRED_STAGE_BASENAMES",
    "RESERVED_ORIGINAL_MARKER",
    "SCOPE_CLASS",
    "SCOPE_ID",
    "TOOL_ROOT",
    "scope_fields",
]
