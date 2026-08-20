"""Immutable contracts and path resolution for the controlled benchmark."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from app.utils.paths import data_root


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
DEFAULT_CONFIG_PATH = (
    TOOL_ROOT
    / "configs"
    / "automated_evaluation"
    / "controlled_diarization_benchmark.v1.yaml"
)
DEFAULT_BENCHMARK_ROOT = (
    TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1"
)
BENCHMARK_VERSION = "controlled_diarization_v1"
CONFIG_SCHEMA_VERSION = "controlled-diarization-benchmark-config.v1"
CASE_SCHEMA_VERSION = "controlled-diarization-case.v1"
RECIPE_SCHEMA_VERSION = "controlled-diarization-recipe.v1"
SOURCE_INVENTORY_SCHEMA_VERSION = "controlled-diarization-source-inventory.v1"
RESULT_SCHEMA_VERSION = "controlled-diarization-result.v1"
PIPELINE_REGISTRY_SCHEMA_VERSION = "controlled-diarization-pipeline-registry.v1"
FROZEN_PIPELINE_SCHEMA_VERSION = "controlled-diarization-frozen-pipelines.v1"
SEED = 3800


class ControlledDiarizationError(ValueError):
    """Raised when a controlled benchmark scientific contract is violated."""


def canonical_json(value: object) -> str:
    """Return the stable JSON representation used by scientific identities."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(prefix: str, value: object, *, length: int = 16) -> str:
    return f"{prefix}_{sha256_text(canonical_json(value))[:length]}"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise ControlledDiarizationError("benchmark configuration must be a mapping")
    required = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "seed": SEED,
        "speech_style": "prompted_read",
        "evaluation_locked": True,
        "sample_rate_hz": 16000,
        "channels": 1,
        "implicit_model_downloads_allowed": False,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ControlledDiarizationError(f"config {key} must be {expected!r}")
    factors = _mapping(payload.get("factors"), "factors")
    if tuple(factors.get("speaker_counts") or ()) != (2, 3, 5):
        raise ControlledDiarizationError("speaker_counts must be [2, 3, 5]")
    if tuple(factors.get("turn_cadence") or ()) != ("relaxed", "standard", "rapid"):
        raise ControlledDiarizationError(
            "turn_cadence must be [relaxed, standard, rapid]"
        )
    if tuple(factors.get("overlap_profiles") or ()) != (
        "none",
        "backchannel",
        "moderate",
    ):
        raise ControlledDiarizationError(
            "overlap_profiles must be [none, backchannel, moderate]"
        )
    return dict(payload)


def default_generated_root() -> Path:
    configured = os.environ.get("JP_GENERATED_DATA_ROOT")
    base = Path(configured).expanduser() if configured else Path.home() / "JustPeachyGeneratedData"
    return (base / BENCHMARK_VERSION).resolve()


def default_result_root() -> Path:
    configured = os.environ.get("JP_DIARIZATION_RESULT_ROOT")
    base = Path(configured).expanduser() if configured else Path.home() / "JustPeachyResults"
    return (base / "diarization" / BENCHMARK_VERSION).resolve()


def default_summary_root() -> Path:
    configured = os.environ.get("JP_RESEARCH_SUMMARY_ROOT")
    base = (
        Path(configured).expanduser()
        if configured
        else Path.home() / "JustPeachyResearchSummaries"
    )
    return base.resolve()


def resolve_source_pool_manifest(
    value: Path | None,
    config: Mapping[str, object],
) -> Path:
    raw = value or Path(str(config["source_speaker_pool_manifest"]))
    path = raw.expanduser()
    if not path.is_absolute():
        path = TOOL_ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"source speaker-pool manifest is unavailable: {path}")
    return path


def resolve_source_path(logical_path: str) -> Path:
    return (data_root().path / Path(logical_path)).resolve()


def benchmark_id(config: Mapping[str, object], source_manifest_sha256: str) -> str:
    scientific = {
        "benchmark_version": config["benchmark_version"],
        "seed": config["seed"],
        "source_manifest_sha256": source_manifest_sha256.lower(),
        "sample_rate_hz": config["sample_rate_hz"],
        "channels": config["channels"],
        "panel": config["panel"],
        "factors": config["factors"],
        "generation": config["generation"],
        "scoring": config["scoring"],
    }
    return identity(BENCHMARK_VERSION, scientific, length=12)


def global_speaker_id(source_protocol_speaker_key: str) -> str:
    return f"cvspk_{sha256_text(BENCHMARK_VERSION + '|' + source_protocol_speaker_key)[:20]}"


@dataclass(frozen=True)
class PipelineDefinition:
    pipeline_id: str
    kind: str
    environment_profile: str
    component_name: str | None
    segmentation: str
    embedding: str
    clustering: str
    execution_status: str
    diagnostic_only: bool
    configuration: dict[str, object]

    @property
    def configuration_sha256(self) -> str:
        return sha256_text(canonical_json(self.to_jsonable(include_hash=False)))

    def to_jsonable(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "pipeline_id": self.pipeline_id,
            "kind": self.kind,
            "environment_profile": self.environment_profile,
            "component_name": self.component_name,
            "segmentation": self.segmentation,
            "embedding": self.embedding,
            "clustering": self.clustering,
            "execution_status": self.execution_status,
            "diagnostic_only": self.diagnostic_only,
            "configuration": self.configuration,
        }
        if include_hash:
            value["configuration_sha256"] = self.configuration_sha256
        return value


def load_pipeline_registry(
    config: Mapping[str, object],
) -> dict[str, PipelineDefinition]:
    raw = _mapping(config.get("pipelines"), "pipelines")
    schema = raw.get("schema_version")
    if schema != PIPELINE_REGISTRY_SCHEMA_VERSION:
        raise ControlledDiarizationError(
            f"pipeline registry schema must be {PIPELINE_REGISTRY_SCHEMA_VERSION}"
        )
    rows = raw.get("definitions")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ControlledDiarizationError("pipelines.definitions must be an array")
    result: dict[str, PipelineDefinition] = {}
    for raw_row in rows:
        row = _mapping(raw_row, "pipeline definition")
        pipeline_id = str(row.get("pipeline_id") or "").strip()
        if not pipeline_id or pipeline_id in result:
            raise ControlledDiarizationError("pipeline IDs must be unique and non-empty")
        result[pipeline_id] = PipelineDefinition(
            pipeline_id=pipeline_id,
            kind=str(row.get("kind") or "full_diarizer"),
            environment_profile=str(row.get("environment_profile") or ""),
            component_name=(
                str(row["component_name"]) if row.get("component_name") else None
            ),
            segmentation=str(row.get("segmentation") or ""),
            embedding=str(row.get("embedding") or ""),
            clustering=str(row.get("clustering") or ""),
            execution_status=str(row.get("execution_status") or "NOT_INTEGRATED"),
            diagnostic_only=bool(row.get("diagnostic_only", False)),
            configuration=dict(_mapping(row.get("configuration") or {}, "configuration")),
        )
    return result


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ControlledDiarizationError(f"{label} must be a mapping")
    return value
