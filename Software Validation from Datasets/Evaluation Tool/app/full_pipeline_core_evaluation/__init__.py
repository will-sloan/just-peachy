"""Bounded, untouched held-out Prompt-5 orchestration.

This additive package binds the immutable Prompt-4 development freeze to the
predeclared eight-day held-out panel.  It deliberately contains no model
implementation; inference is delegated to :mod:`app.full_pipeline_evaluation`.
"""

from __future__ import annotations

from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[2]
SCOPE_ID = "full_pipeline_prompts_4_8_eight_day_c_only.v1"
SCOPE_CLASS = "BOUNDED_REDUCED"
ORIGINAL_FULL_SCOPE_COMPLETE = False
PROMPT4_COMPLETION_MARKER = "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE_REDUCED_8DAY_V1"
PROMPT5_COMPLETION_MARKER = "COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1"
SELECTION_TAG = "prompt5_reduced_core_v1"
SELECTION_SEED = 5107
EXPECTED_CASE_COUNT = 2240
EXPECTED_SELECTED_CASE_SHA256 = (
    "0269ab1545cbd657732f88b73d75aeda734e4e3cdf72ac92af639633afaf82cd"
)
EXPECTED_SOURCE_CASE_COUNTS = {
    "commonvoice_60plus_asr": 730,
    "controlled_v1": 360,
    "product_v2": 808,
    "cmu_arctic": 54,
    "hifitts": 30,
    "librispeech": 219,
    "voices": 39,
}
MINIMUM_FREE_SPACE_GIB = 35
MINIMUM_FREE_SPACE_BYTES = MINIMUM_FREE_SPACE_GIB * 1024**3

DEFAULT_ROOT = (
    TOOL_ROOT / "automated_runs/full_pipeline_core_evaluation_reduced_8day_v1"
)
DEFAULT_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks/full_pipeline/full_speech_pipeline_v1"
DEFAULT_CASE_MANIFEST = DEFAULT_PROTOCOL_ROOT / "evaluation/case_manifest.jsonl"
DEFAULT_AMENDMENT = (
    TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
)
DEFAULT_PROGRAM_STATE = TOOL_ROOT / "runs/full_pipeline_program/PROGRAM_STATE.json"
DEFAULT_PI_DEPLOYMENT_STEERING = (
    TOOL_ROOT / "runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json"
)
EXPECTED_PI_DEPLOYMENT_STEERING_SHA256 = (
    "f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4"
)
DEPLOYMENT_EVIDENCE_FILE = "all18_deployment_evidence.json"


__all__ = [
    "DEFAULT_AMENDMENT",
    "DEFAULT_CASE_MANIFEST",
    "DEFAULT_PROGRAM_STATE",
    "DEFAULT_PI_DEPLOYMENT_STEERING",
    "DEFAULT_PROTOCOL_ROOT",
    "DEFAULT_ROOT",
    "EXPECTED_CASE_COUNT",
    "EXPECTED_PI_DEPLOYMENT_STEERING_SHA256",
    "EXPECTED_SELECTED_CASE_SHA256",
    "MINIMUM_FREE_SPACE_BYTES",
    "ORIGINAL_FULL_SCOPE_COMPLETE",
    "PROMPT4_COMPLETION_MARKER",
    "PROMPT5_COMPLETION_MARKER",
    "DEPLOYMENT_EVIDENCE_FILE",
    "SCOPE_CLASS",
    "SCOPE_ID",
    "SELECTION_SEED",
    "SELECTION_TAG",
    "TOOL_ROOT",
]
