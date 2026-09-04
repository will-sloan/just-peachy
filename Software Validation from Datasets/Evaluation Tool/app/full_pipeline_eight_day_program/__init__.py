"""C:-only controller for the bounded eight-day full-pipeline program."""

from __future__ import annotations

SCOPE_ID = "full_pipeline_prompts_4_8_eight_day_c_only.v1"
SCOPE_CLASS = "BOUNDED_REDUCED"
AMENDMENT_SCHEMA = "just-peachy-full-pipeline-scope-amendment.v1"
ADAPTER_CONFIG_SCHEMA = "full-pipeline-eight-day-adapters.v1"
STATE_SCHEMA = "full-pipeline-eight-day-program-state.v1"
STAGE_COMPLETION_SCHEMA = "full-pipeline-eight-day-stage-completion.v1"
ARTIFACT_MANIFEST_SCHEMA = "full-pipeline-eight-day-artifact-manifest.v1"
GATE_SCHEMA = "full-pipeline-eight-day-gate.v1"

PROMPTS = (4, 5, 6, 7, 8)
STAGE_BUDGET_HOURS = {4: 48.0, 5: 60.0, 6: 30.0, 7: 12.0, 8: 4.0}
TOTAL_BUDGET_HOURS = 192.0
SHARED_CONTINGENCY_HOURS = 38.0
MINIMUM_FREE_GIB = 35.0
TIME_TARGET_POLICY = "ADVISORY_ONLY_NO_AUTOMATIC_STOP"

COMPLETION_MARKERS = {
    4: "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE_REDUCED_8DAY_V1",
    5: "COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1",
    6: "COMPLETE_EXTENDED_PIPELINE_EVALUATION_REDUCED_8DAY_V1",
    7: "COMPLETE_PRODUCTION_CANDIDATE_HARDENING_REDUCED_8DAY_V1",
    8: "COMPLETE_FULL_PIPELINE_PROGRAM_REDUCED_8DAY_V1",
}

RESERVED_ORIGINAL_MARKERS = {
    "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE",
    "COMPLETE_ALL18_CORE_EVALUATION",
    "COMPLETE_EXTENDED_PIPELINE_EVALUATION",
    "COMPLETE_PRODUCTION_CANDIDATE_HARDENING",
    "COMPLETE_FULL_PIPELINE_PROGRAM",
}

REQUIRED_GATE_NAMES = (
    "hash_validation",
    "firewall_validation",
    "prerequisite_validation",
)

MATERIAL_PATH_CLASSES = (
    "inputs",
    "workspaces",
    "caches",
    "temporary",
    "logs",
    "results",
    "reports",
    "packages",
    "checkpoints",
)
