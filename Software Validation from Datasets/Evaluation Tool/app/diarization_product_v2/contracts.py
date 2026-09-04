"""Paths and immutable identifiers for the Product V2 study."""

from __future__ import annotations

from pathlib import Path

from app.controlled_diarization.contracts import TOOL_ROOT


SEED = 3800
PRODUCT_VERSION = "diarization_product_v2"
DEFAULT_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks" / "stage11" / PRODUCT_VERSION
DEFAULT_GENERATED_ROOT = TOOL_ROOT / "JustPeachyGeneratedData" / PRODUCT_VERSION
DEFAULT_RESULT_ROOT = (
    TOOL_ROOT / "JustPeachyResults" / "diarization_product_v2_development"
)
DEFAULT_ANALYSIS_ROOT = DEFAULT_RESULT_ROOT / "analysis"
DEFAULT_CONFIG_PATH = (
    TOOL_ROOT
    / "configs"
    / "automated_evaluation"
    / "diarization_product_v2.development.yaml"
)
DEFAULT_FROZEN_CONFIG_PATH = DEFAULT_RESULT_ROOT / "frozen_development_pipeline_config.yaml"
DEFAULT_SELECTION_PATH = (
    DEFAULT_RESULT_ROOT / "frozen_diarization_development_selection.yaml"
)
DEFAULT_PROGRESS_PATH = DEFAULT_RESULT_ROOT / "campaign_progress.json"
DEFAULT_STATE_PATH = DEFAULT_RESULT_ROOT / "controller_state.json"
V1_PROTOCOL_ROOT = (
    TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1"
)
V1_GENERATED_ROOT = TOOL_ROOT / "JustPeachyGeneratedData" / "controlled_diarization_v1"


PRIMARY_PIPELINES = (
    "sherpa_onnx_diarization",
    "pyannote_community1",
    "modular_energy_wespeaker",
    "modular_pyannote_wespeaker",
    "modular_pyannote_redimnet2",
    "modular_pyannote_speechbrain_ecapa",
)
ORACLE_PIPELINES = (
    "oracle_turn_wespeaker_diagnostic",
    "oracle_turn_redimnet2_diagnostic",
    "oracle_turn_speechbrain_diagnostic",
)

