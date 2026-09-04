"""Versioned contracts and paths for hybrid speaker attribution."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping

import yaml

from app.utils.paths import evaluation_output_root


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
DEFAULT_CONFIG_PATH = TOOL_ROOT / "configs" / "automated_evaluation" / "hybrid_speaker_attribution.v1.yaml"
DEFAULT_BENCHMARK_ROOT = TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1"
DEFAULT_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks" / "hybrid_speaker_attribution" / "hybrid_speaker_attribution_v1"
CONFIG_SCHEMA_VERSION = "hybrid-speaker-attribution-config.v1"
PROTOCOL_SCHEMA_VERSION = "hybrid-speaker-attribution-protocol.v1"
OVERLAY_SCHEMA_VERSION = "hybrid-speaker-attribution-overlay.v1"
ENROLLMENT_POLICY_SCHEMA_VERSION = "hybrid-enrollment-policy.v1"
FROZEN_CONFIG_SCHEMA_VERSION = "hybrid-speaker-attribution-frozen-config.v1"
RESULT_SCHEMA_VERSION = "hybrid-speaker-attribution-result.v1"
SEED = 3800


class HybridAttributionError(ValueError):
    """Raised when a hybrid scientific contract is violated."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, Mapping):
        raise HybridAttributionError("hybrid configuration must be a mapping")
    if value.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise HybridAttributionError("unsupported hybrid configuration schema")
    if int(value.get("seed", -1)) != SEED:
        raise HybridAttributionError("hybrid v1 seed must be 3800")
    required = list(value.get("required_overlays") or [])
    if required != ["ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"]:
        raise HybridAttributionError("hybrid v1 requires the three frozen identity overlays")
    return {str(key): item for key, item in value.items()}


def load_enrollment_policy(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, Mapping) or value.get("schema_version") != ENROLLMENT_POLICY_SCHEMA_VERSION:
        raise HybridAttributionError(
            f"enrollment policy must use {ENROLLMENT_POLICY_SCHEMA_VERSION}"
        )
    required = (
        "policy_id",
        "speaker_backend_id",
        "source_study_protocol_id",
        "enrollment_utterance_count",
        "aggregation_method",
        "normalization",
        "scoring_method",
        "product_threshold",
        "minimum_segment_duration_sec",
        "minimum_evidence_duration_sec",
        "evaluation_tuning_prohibited",
    )
    missing = [key for key in required if key not in value]
    if missing:
        raise HybridAttributionError(f"enrollment policy is incomplete: {missing}")
    if value["aggregation_method"] not in {
        "normalized_mean",
        "duration_weighted_mean",
        "multi_template_mean_score",
    }:
        raise HybridAttributionError("unsupported enrollment aggregation method")
    if value["normalization"] != "l2" or value["scoring_method"] != "cosine_similarity":
        raise HybridAttributionError("hybrid v1 requires L2 normalization and cosine similarity")
    if value["evaluation_tuning_prohibited"] is not True:
        raise HybridAttributionError("enrollment policy must prohibit evaluation tuning")
    result = {str(key): item for key, item in value.items()}
    declared = str(result.get("policy_sha256") or "")
    payload = {key: item for key, item in result.items() if key != "policy_sha256"}
    observed = canonical_sha256(payload)
    if declared and declared.upper() != observed:
        raise HybridAttributionError("enrollment policy SHA-256 mismatch")
    result["policy_sha256"] = observed
    return result


def load_frozen_config(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or value.get("schema_version") != FROZEN_CONFIG_SCHEMA_VERSION:
        raise HybridAttributionError("unsupported frozen hybrid configuration")
    if value.get("development_decision_status") != "frozen":
        raise HybridAttributionError("hybrid development decision is not frozen")
    if value.get("evaluation_tuning_prohibited") is not True:
        raise HybridAttributionError("frozen hybrid configuration does not prohibit evaluation tuning")
    declared = str(value.get("hybrid_config_sha256") or "")
    payload = {str(key): item for key, item in value.items() if key != "hybrid_config_sha256"}
    observed = canonical_sha256(payload)
    if declared.upper() != observed:
        raise HybridAttributionError("frozen hybrid configuration hash mismatch")
    return {str(key): item for key, item in value.items()}


def default_result_root() -> Path:
    configured = os.environ.get("JP_HYBRID_ATTRIBUTION_RESULT_ROOT", "").strip()
    return Path(configured).resolve() if configured else evaluation_output_root("results") / "hybrid_speaker_attribution"


def default_summary_root(config_id: str, git_sha: str) -> Path:
    return evaluation_output_root("research_summaries") / f"hybrid_speaker_attribution_{config_id}_{git_sha[:12]}"
