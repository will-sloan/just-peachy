"""Versioned scientific and backend contracts for Stage 11."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import math
import os
from pathlib import Path
import platform
from typing import Mapping, Sequence

import yaml

from app.benchmark_contracts.manifest_io import file_sha256
from app.inference_pipeline.catalog import ComponentCatalog


TOOL_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = TOOL_ROOT / "configs" / "automated_evaluation" / "diarization_evaluation.v1.yaml"
QUALIFICATION_REGISTRY_PATH = (
    TOOL_ROOT
    / "configs"
    / "automated_evaluation"
    / "extended_qualification_registry.v1.yaml"
)
EXTENDED_BACKEND_CATALOG_PATH = (
    TOOL_ROOT / "configs" / "automated_evaluation" / "extended_backends.v1.yaml"
)
POLICY_SCHEMA_VERSION = "diarization-evaluation-policy.v1"
NATIVE_MANIFEST_SCHEMA_VERSION = "native-diarization-manifest.v1"
REFERENCE_SCHEMA_VERSION = "native-diarization-reference.v1"
SCORING_POLICY_VERSION = "diarization-scoring-policy.v1"
RESULT_SCHEMA_VERSION = "diarization-result.v1"
METRICS_SCHEMA_VERSION = "diarization-metrics.v1"
BACKEND_REGISTRY_SCHEMA_VERSION = "diarization-backend-status.v1"
ELIGIBLE_BACKEND_STATUSES = frozenset({"qualified", "qualified_with_warnings"})
AUTHORIZED_DIARIZATION_BACKENDS = (
    "pyannote_community",
    "sherpa_onnx_diarization",
    "picovoice_falcon",
    "nemo_diarization",
)


class DiarizationEvaluationError(ValueError):
    """Raised when a Stage 11 scientific contract is violated."""


@dataclass(frozen=True)
class DiarizationScoringPolicy:
    """Explicit parameters that make a diarization score interpretable."""

    version: str = SCORING_POLICY_VERSION
    collar_sec: float = 0.25
    overlap_modes: tuple[str, ...] = ("overlap_aware", "overlap_excluded")
    require_uem: bool = True
    speaker_count_mode: str = "estimated"
    reference_version: str = REFERENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.version != SCORING_POLICY_VERSION:
            raise DiarizationEvaluationError("unsupported diarization scoring-policy version")
        if not math.isfinite(float(self.collar_sec)) or self.collar_sec < 0:
            raise DiarizationEvaluationError("collar_sec must be finite and >= 0")
        if not self.overlap_modes:
            raise DiarizationEvaluationError("at least one overlap mode is required")
        allowed = {"overlap_aware", "overlap_excluded"}
        if set(self.overlap_modes) - allowed:
            raise DiarizationEvaluationError("unsupported overlap policy")
        if self.speaker_count_mode not in {"estimated", "oracle_diagnostic"}:
            raise DiarizationEvaluationError("invalid speaker-count mode")
        if not self.reference_version.strip():
            raise DiarizationEvaluationError("reference_version must be non-empty")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "DiarizationScoringPolicy":
        modes = value.get("overlap_modes", ("overlap_aware", "overlap_excluded"))
        if not isinstance(modes, Sequence) or isinstance(modes, (str, bytes)):
            raise DiarizationEvaluationError("overlap_modes must be an array")
        return cls(
            version=str(value.get("version") or ""),
            collar_sec=float(value.get("collar_sec", 0.25)),
            overlap_modes=tuple(str(item) for item in modes),
            require_uem=bool(value.get("require_uem", True)),
            speaker_count_mode=str(value.get("speaker_count_mode") or "estimated"),
            reference_version=str(value.get("reference_version") or ""),
        )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "version": self.version,
            "collar_sec": self.collar_sec,
            "overlap_modes": list(self.overlap_modes),
            "require_uem": self.require_uem,
            "speaker_count_mode": self.speaker_count_mode,
            "reference_version": self.reference_version,
        }


@dataclass(frozen=True)
class SegmentationProvenance:
    """What actually determined the final segments, independent of intent."""

    requested_sources: tuple[str, ...]
    effective_source: str
    processing_chain: tuple[str, ...]
    external_vad_affected_final_segments: bool
    diarization_replaced_external_vad: bool
    oracle_reference_used: bool
    diagnostic_only: bool

    def __post_init__(self) -> None:
        allowed = {
            "full_record",
            "vad",
            "vad_chunker",
            "diarizer",
            "backend_internal",
            "oracle_reference",
        }
        if self.effective_source not in allowed:
            raise DiarizationEvaluationError(
                f"unsupported effective segmentation source {self.effective_source!r}"
            )
        if self.oracle_reference_used and not self.diagnostic_only:
            raise DiarizationEvaluationError(
                "oracle segmentation must be labelled diagnostic-only"
            )
        if self.diarization_replaced_external_vad and self.external_vad_affected_final_segments:
            raise DiarizationEvaluationError(
                "replaced external VAD cannot also affect final segmentation"
            )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": "segmentation-provenance.v1",
            "requested_sources": list(self.requested_sources),
            "effective_source": self.effective_source,
            "processing_chain": list(self.processing_chain),
            "external_vad_affected_final_segments": self.external_vad_affected_final_segments,
            "diarization_replaced_external_vad": self.diarization_replaced_external_vad,
            "oracle_reference_used": self.oracle_reference_used,
            "diagnostic_only": self.diagnostic_only,
        }


def resolve_segmentation_provenance(
    *,
    vad_enabled: bool,
    vad_chunker_enabled: bool,
    diarizer_enabled: bool,
    diarizer_produced_turns: bool,
    backend_internal_segmentation: bool,
    diarizer_output_authoritative: bool = False,
    oracle_reference_used: bool = False,
) -> SegmentationProvenance:
    """Resolve provenance from observed execution rather than configured names."""

    requested: list[str] = []
    if vad_enabled:
        requested.append("vad")
    if vad_chunker_enabled:
        requested.append("vad_chunker")
    if diarizer_enabled:
        requested.append("diarizer")
    if oracle_reference_used:
        requested.append("oracle_reference")
        return SegmentationProvenance(
            requested_sources=tuple(requested),
            effective_source="oracle_reference",
            processing_chain=("oracle_reference",),
            external_vad_affected_final_segments=False,
            diarization_replaced_external_vad=vad_enabled,
            oracle_reference_used=True,
            diagnostic_only=True,
        )
    if diarizer_enabled and (diarizer_produced_turns or diarizer_output_authoritative):
        first = "backend_internal" if backend_internal_segmentation else "diarizer"
        chain = [first]
        if vad_chunker_enabled:
            chain.append("vad_chunker_postprocessing")
        return SegmentationProvenance(
            requested_sources=tuple(requested),
            effective_source=first,
            processing_chain=tuple(chain),
            external_vad_affected_final_segments=False,
            diarization_replaced_external_vad=vad_enabled,
            oracle_reference_used=False,
            diagnostic_only=False,
        )
    if vad_enabled and vad_chunker_enabled:
        return SegmentationProvenance(
            requested_sources=tuple(requested),
            effective_source="vad_chunker",
            processing_chain=("vad", "vad_chunker"),
            external_vad_affected_final_segments=True,
            diarization_replaced_external_vad=False,
            oracle_reference_used=False,
            diagnostic_only=False,
        )
    if vad_enabled:
        return SegmentationProvenance(
            requested_sources=tuple(requested),
            effective_source="vad",
            processing_chain=("vad",),
            external_vad_affected_final_segments=True,
            diarization_replaced_external_vad=False,
            oracle_reference_used=False,
            diagnostic_only=False,
        )
    return SegmentationProvenance(
        requested_sources=tuple(requested),
        effective_source="full_record",
        processing_chain=("full_record",),
        external_vad_affected_final_segments=False,
        diarization_replaced_external_vad=False,
        oracle_reference_used=False,
        diagnostic_only=False,
    )


def load_policy(path: Path = POLICY_PATH) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise DiarizationEvaluationError("diarization policy must be a mapping")
    required = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "native_manifest_schema_version": NATIVE_MANIFEST_SCHEMA_VERSION,
        "reference_schema_version": REFERENCE_SCHEMA_VERSION,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "selection_seed": 3800,
        "implicit_model_downloads_allowed": False,
        "synthetic_augmentation_allowed": False,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise DiarizationEvaluationError(f"policy {key} must be {expected!r}")
    return dict(payload)


def scoring_policy(policy: Mapping[str, object] | None = None) -> DiarizationScoringPolicy:
    active = dict(policy or load_policy())
    raw = active.get("scoring")
    if not isinstance(raw, Mapping):
        raise DiarizationEvaluationError("policy scoring section must be a mapping")
    return DiarizationScoringPolicy.from_mapping(raw)


def backend_availability(
    *,
    catalog: ComponentCatalog | None = None,
    registry_path: Path = QUALIFICATION_REGISTRY_PATH,
) -> dict[str, dict[str, object]]:
    """Return frozen qualification plus current non-secret runtime availability."""

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if registry.get("schema_version") != "extended-qualification-registry.v1":
        raise DiarizationEvaluationError("unsupported extended qualification registry")
    rows = registry.get("backends")
    if not isinstance(rows, list):
        raise DiarizationEvaluationError("qualification registry backends must be an array")
    by_id = {
        str(row.get("backend_id")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("catalog_family") == "diarization"
    }
    backend_catalog = yaml.safe_load(
        EXTENDED_BACKEND_CATALOG_PATH.read_text(encoding="utf-8")
    ) or {}
    backend_catalog_rows = backend_catalog.get("backends")
    if not isinstance(backend_catalog_rows, list):
        raise DiarizationEvaluationError("extended backend catalog backends must be an array")
    backend_requirements = {
        str(row.get("id")): row
        for row in backend_catalog_rows
        if isinstance(row, Mapping) and row.get("family") == "diarization"
    }
    active_catalog = catalog or ComponentCatalog.load()
    result: dict[str, dict[str, object]] = {}
    for backend_id in AUTHORIZED_DIARIZATION_BACKENDS:
        if backend_id not in by_id:
            raise DiarizationEvaluationError(f"missing backend status: {backend_id}")
        frozen = by_id[backend_id]
        declared_requirements = backend_requirements.get(backend_id, {})
        entry = active_catalog.get("diarization", backend_id)
        package_available = _package_available(backend_id)
        credential_names = set(entry.credential_requirements)
        credential_names.update(
            str(declared_requirements[key])
            for key in ("credential_env", "licence_ack_env")
            if declared_requirements.get(key)
        )
        credential_state = _credential_state(sorted(credential_names))
        supported_operating_systems = {
            str(value).casefold() for value in entry.supported_operating_systems
        }
        os_supported = platform.system().casefold() in supported_operating_systems
        assets_present = not any(
            item.get("present") is False for item in entry.model_asset_identity
        )
        cuda_required = bool(declared_requirements.get("cuda_required", False))
        cuda_available = _cuda_available() if cuda_required else True
        qualified = str(frozen.get("status")) in ELIGIBLE_BACKEND_STATUSES
        execution_allowed = bool(
            qualified
            and package_available
            and os_supported
            and assets_present
            and cuda_available
            and all(credential_state.values())
        )
        blockers: list[str] = []
        if not qualified:
            blockers.append(f"qualification_status:{frozen.get('status')}")
        if not package_available:
            blockers.append("required_package_unavailable")
        if not os_supported:
            blockers.append(f"platform_required:{','.join(entry.supported_operating_systems)}")
        if not assets_present:
            blockers.append("model_asset_unavailable")
        if not cuda_available:
            blockers.append("cuda_required")
        blockers.extend(
            f"credential_or_licence_required:{name}"
            for name, present in credential_state.items()
            if not present
        )
        result[backend_id] = {
            "schema_version": BACKEND_REGISTRY_SCHEMA_VERSION,
            "backend_id": backend_id,
            "implementation_class": entry.implementation_class,
            "environment_profile": frozen.get("profile"),
            "qualification_status": frozen.get("status"),
            "qualification_disposition": frozen.get("disposition"),
            "qualification_evidence": frozen.get("evidence_path"),
            "source_config_path": entry.source_config_path,
            "source_config_sha256": entry.source_config_sha256,
            "model_identity": dict(entry.model_identity),
            "model_asset_identity": [dict(item) for item in entry.model_asset_identity],
            "package_available_in_current_environment": package_available,
            "supported_on_current_os": os_supported,
            "credential_and_licence_presence": credential_state,
            "cuda_required": cuda_required,
            "cuda_available": cuda_available,
            "implicit_downloads_allowed": False,
            "execution_allowed": execution_allowed,
            "blockers": blockers,
            "qualification_registry": {
                "path": registry_path.relative_to(TOOL_ROOT).as_posix(),
                "sha256": file_sha256(registry_path).upper(),
            },
        }
    return result


def require_executable_backend(backend_id: str) -> dict[str, object]:
    statuses = backend_availability()
    if backend_id not in statuses:
        raise DiarizationEvaluationError(f"unknown Stage 11 backend {backend_id!r}")
    row = statuses[backend_id]
    if not row["execution_allowed"]:
        raise DiarizationEvaluationError(
            f"backend {backend_id} is not authorized and available: {', '.join(row['blockers'])}"
        )
    return row


def _package_available(backend_id: str) -> bool:
    module = {
        "pyannote_community": "pyannote.audio",
        "sherpa_onnx_diarization": "sherpa_onnx",
        "picovoice_falcon": "pvfalcon",
        "nemo_diarization": "nemo.collections.asr",
    }[backend_id]
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError):
        return False


def _credential_state(requirements: Sequence[str]) -> dict[str, bool]:
    return {
        str(name): bool((os.environ.get(str(name)) or "").strip())
        for name in requirements
    }


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False
