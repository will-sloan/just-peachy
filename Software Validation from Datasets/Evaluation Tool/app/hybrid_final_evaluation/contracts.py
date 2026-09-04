"""Paths and durable contracts for the frozen Task-2 hybrid evaluation."""

from __future__ import annotations

from pathlib import Path

from app.hybrid_speaker_attribution.product_v2_contracts import (
    PRODUCT_PROTOCOL_ROOT,
    POLICY_ROOT,
    SUMMARY_ROOT,
    TOOL_ROOT,
    V1_BENCHMARK_ROOT,
    V2_BENCHMARK_ROOT,
    atomic_json,
    atomic_text,
    checksum_tree,
    file_sha256,
    now_utc,
    read_json,
    read_jsonl,
    write_csv,
    write_jsonl,
    write_yaml,
)


SCHEMA = "hybrid-speaker-attribution-product-v2-final-evaluation"
SEED = 3800
TASK1_ROOT = TOOL_ROOT / "JustPeachyResults" / "hybrid_speaker_attribution_product_v2_development"
FROZEN_HYBRID_PATH = TASK1_ROOT / "frozen_hybrid_product_v2_selection.yaml"
FINAL_DIARIZATION_ROOT = TOOL_ROOT / "JustPeachyResults" / "diarization_finalists_final_evaluation"
RESULT_ROOT = TOOL_ROOT / "JustPeachyResults" / "hybrid_speaker_attribution_product_v2_final_evaluation"
ANALYSIS_ROOT = RESULT_ROOT / "analysis"
CACHE_ROOT = RESULT_ROOT / "_embedding_cache"
SCORE_ROOT = RESULT_ROOT / "score_bundles"
PROGRESS_PATH = RESULT_ROOT / "campaign_progress.json"
STATE_PATH = RESULT_ROOT / "controller_state.json"
STOP_PATH = RESULT_ROOT / "STOP_REQUESTED"
FINAL_SELECTION_PATH = RESULT_ROOT / "final_hybrid_product_v2_selection.yaml"

CORPORA = {
    "v1": {
        "scope": "CONTROLLED_V1",
        "benchmark_root": V1_BENCHMARK_ROOT,
        "diarization_scope": "controlled_v1",
        "generated_subdir": "controlled_diarization_v1",
    },
    "v2": {
        "scope": "CONTROLLED_V2",
        "benchmark_root": V2_BENCHMARK_ROOT,
        "diarization_scope": "controlled_v2",
        "generated_subdir": "diarization_product_v2",
    },
}


class FinalHybridEvaluationError(RuntimeError):
    """Raised when a frozen final-evaluation invariant is violated."""


def frozen_sha256_path() -> Path:
    return FROZEN_HYBRID_PATH.with_suffix(".sha256")

