"""Paths and immutable Task-2 identities."""

from __future__ import annotations

from pathlib import Path

from app.controlled_diarization.contracts import TOOL_ROOT


TASK1_ROOT = TOOL_ROOT / "JustPeachyResults" / "diarization_product_v2_development"
TASK1_SELECTION = TASK1_ROOT / "frozen_diarization_development_selection.yaml"
TASK1_SELECTION_CHECKSUM = TASK1_ROOT / "frozen_diarization_development_selection.sha256"
FROZEN_RUNTIME_CONFIG = TASK1_ROOT / "frozen_development_pipeline_config.yaml"

RESULT_ROOT = TOOL_ROOT / "JustPeachyResults" / "diarization_finalists_final_evaluation"
ANALYSIS_ROOT = RESULT_ROOT / "analysis"
STATE_PATH = RESULT_ROOT / "controller_state.json"
PROGRESS_PATH = RESULT_ROOT / "campaign_progress.json"
STOP_PATH = RESULT_ROOT / "STOP_REQUESTED"
AUTHORIZATION_ROOT = RESULT_ROOT / "evaluation_authorization"
SHARED_CACHE_ROOT = RESULT_ROOT / "_shared_cache"
NATIVE_AUDIO_CACHE = RESULT_ROOT / "_native_audio_cache"

V1_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1"
V1_GENERATED_ROOT = TOOL_ROOT / "JustPeachyGeneratedData" / "controlled_diarization_v1"
V1_RESULT_ROOT = RESULT_ROOT / "controlled_v1"
V2_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks" / "stage11" / "diarization_product_v2"
V2_GENERATED_ROOT = TOOL_ROOT / "JustPeachyGeneratedData" / "diarization_product_v2"
V2_RESULT_ROOT = RESULT_ROOT / "controlled_v2"

TASK1_NATIVE_ROOT = TASK1_ROOT / "native_campaign" / "manifest"
NATIVE_RESULT_ROOT = RESULT_ROOT / "native"

FINAL_PACKAGE = (
    TOOL_ROOT
    / "JustPeachyResearchSummaries"
    / "diarization_finalists_final_evaluation_diarization_product_v2_6b6c50a5de31.zip"
)

EXPECTED_PROTOCOLS = {
    "controlled_v1": "controlled_diarization_v1_acd5e6e431d8",
    "product_v2": "diarization_product_v2_6b6c50a5de31",
}
EXPECTED_PIPELINES = (
    "modular_pyannote_wespeaker",
    "modular_pyannote_redimnet2",
)
SEED = 3800

