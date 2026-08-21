"""Frozen identities and portable paths for the Common Voice 60+ ASR study."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

import yaml

from app.inference_pipeline.catalog import ComponentCatalog
from app.utils.paths import evaluation_output_root, repository_root


TOOL_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_VERSION = "commonvoice_60plus_asr_v1"
PROTOCOL_SCHEMA_VERSION = "asr-commonvoice-protocol.v1"
MANIFEST_SCHEMA_VERSION = "asr-commonvoice-manifest.v1"
CONFIG_SCHEMA_VERSION = "asr-commonvoice-60plus-config.v1"
RESULT_SCHEMA_VERSION = "asr-commonvoice-backend-result.v1"
ANALYSIS_SCHEMA_VERSION = "asr-commonvoice-analysis.v1"
SEED = 3800
DEFAULT_CONFIG_PATH = (
    TOOL_ROOT / "configs" / "automated_evaluation" / "asr_commonvoice_60plus.v1.yaml"
)
DEFAULT_PROTOCOL_ROOT = (
    TOOL_ROOT / "benchmarks" / "asr_commonvoice" / PROTOCOL_VERSION
)
BASE_INFERENCE_CONFIG = TOOL_ROOT / "configs" / "inference" / "base.yaml"
MODEL_COMPONENT_IDS = (
    "sherpa_onnx",
    "sherpa_onnx_libri_giga_zipformer_2023_06_21",
    "whisper_small",
)


class ASRCommonVoiceError(ValueError):
    """Raised when a frozen campaign or result contract is violated."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise ASRCommonVoiceError("campaign configuration must be a mapping")
    required = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "seed": SEED,
        "augmentation": "none",
        "language": "en",
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ASRCommonVoiceError(f"config {key} must be {expected!r}")
    models = payload.get("models")
    if not isinstance(models, Sequence) or isinstance(models, (str, bytes)):
        raise ASRCommonVoiceError("config models must be an array")
    observed = tuple(str(_mapping(row, "model").get("component_id")) for row in models)
    if observed != MODEL_COMPONENT_IDS:
        raise ASRCommonVoiceError(
            f"config must preserve exact model order {MODEL_COMPONENT_IDS}, got {observed}"
        )
    return {str(key): value for key, value in payload.items()}


def resolve_models(config_path: Path = DEFAULT_CONFIG_PATH) -> list[dict[str, object]]:
    """Resolve the exact prior components without loading model runtimes."""

    config = load_config(config_path)
    catalog = ComponentCatalog.load()
    resolved: list[dict[str, object]] = []
    for raw in config["models"]:
        row = _mapping(raw, "model")
        component_id = str(row["component_id"])
        registry_id = str(row["registry_id"])
        if registry_id != f"asr.{component_id}":
            raise ASRCommonVoiceError(f"registry/component mismatch for {component_id}")
        entry = catalog.get("asr", component_id)
        profile = str(row["environment_profile"])
        if profile not in entry.environment_profiles:
            raise ASRCommonVoiceError(
                f"{component_id} is not registered for environment {profile}"
            )
        assets = [dict(asset) for asset in entry.model_asset_identity]
        asset_ready = bool(assets) and all(
            bool(asset.get("present"))
            and asset.get("hash_matches") is not False
            and str(asset.get("verification_status") or "verified") == "verified"
            for asset in assets
        )
        interpreter = environment_interpreter(profile)
        resolved.append(
            {
                "human_name": str(row["human_name"]),
                "component_id": component_id,
                "registry_id": registry_id,
                "adapter": entry.registry_adapter_class,
                "implementation_class": entry.implementation_class,
                "implementation_path": entry.implementation_path,
                "config_path": entry.source_config_path,
                "config_sha256": entry.source_config_sha256,
                "model_identity": dict(entry.model_identity),
                "model_assets": assets,
                "asset_ready": asset_ready,
                "environment_profile": profile,
                "environment_interpreter": str(interpreter),
                "environment_ready": interpreter.is_file(),
                "runtime": "openai-whisper==20250625" if component_id == "whisper_small" else "sherpa-onnx==1.13.4",
                "device": str(row["device"]),
                "precision": str(row["precision"]),
                "sample_rate_hz": 16000,
                "licence": str(row["licence"]),
                "qualification_status": entry.qualification_status,
                "qualification_evidence": entry.qualification_evidence,
                "compatibility_rules": list(entry.compatibility_rules),
            }
        )
    return resolved


def environment_interpreter(profile: str) -> Path:
    repository = repository_root().path
    if profile == "core-cpu":
        return repository / ".venv" / "Scripts" / "python.exe"
    return repository / ".stage8-envs" / profile / "Scripts" / "python.exe"


def campaign_identity(protocol_summary: Mapping[str, object]) -> str:
    models = resolve_models()
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "protocol_id": protocol_summary["protocol_id"],
        "manifest_sha256": protocol_summary["manifest_sha256"],
        "config_sha256": file_sha256(DEFAULT_CONFIG_PATH),
        "models": [
            {
                "component_id": row["component_id"],
                "config_sha256": row["config_sha256"],
                "environment_profile": row["environment_profile"],
                "device": row["device"],
                "precision": row["precision"],
                "model_assets": row["model_assets"],
            }
            for row in models
        ],
        "implementation_sha256": implementation_sha256(),
    }
    return f"campaign_{PROTOCOL_VERSION}_{canonical_sha256(payload)[:12].lower()}"


def implementation_sha256() -> str:
    paths = sorted(Path(__file__).resolve().parent.glob("*.py"))
    paths.append(DEFAULT_CONFIG_PATH)
    payload = [
        {
            "path": path.relative_to(TOOL_ROOT).as_posix(),
            "sha256": file_sha256(path),
        }
        for path in paths
        if path.is_file()
    ]
    return canonical_sha256(payload)


def default_result_root(protocol_summary: Mapping[str, object]) -> Path:
    return (
        evaluation_output_root("results")
        / "asr_commonvoice"
        / PROTOCOL_VERSION
        / campaign_identity(protocol_summary)
    ).resolve()


def default_collection_root(protocol_summary: Mapping[str, object]) -> Path:
    return (
        evaluation_output_root("research_summaries")
        / f"asr_commonvoice_60plus_{protocol_summary['protocol_id']}_{campaign_identity(protocol_summary)}"
    ).resolve()


def default_smoke_result_root(protocol_summary: Mapping[str, object]) -> Path:
    return (
        evaluation_output_root("results")
        / "asr_commonvoice_smoke"
        / PROTOCOL_VERSION
        / campaign_identity(protocol_summary)
    ).resolve()


def default_smoke_collection_root(protocol_summary: Mapping[str, object]) -> Path:
    return (
        evaluation_output_root("research_summaries")
        / "asr_commonvoice_smoke"
        / f"{protocol_summary['protocol_id']}_{campaign_identity(protocol_summary)}"
    ).resolve()


def git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=TOOL_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ASRCommonVoiceError(f"{name} must be a mapping")
    return value
