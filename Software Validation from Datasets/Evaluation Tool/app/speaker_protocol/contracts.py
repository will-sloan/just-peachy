"""Versioned identities and validation for the Stage 10 speaker protocol."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from app.benchmark_contracts.canonical import canonical_sha256
from app.inference_pipeline.catalog import ComponentCatalog


TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = (
    TOOL_ROOT / "configs" / "automated_evaluation" / "speaker_protocol.v1.yaml"
)
POLICY_SCHEMA_VERSION = "speaker-protocol-policy.v1"
MANIFEST_SCHEMA_VERSION = "speaker-protocol-manifest.v1"
ENROLLMENT_SCHEMA_VERSION = "backend-enrollment.v1"
THRESHOLD_POLICY_VERSION = "speaker-threshold-policy.v1"
METRICS_SCHEMA_VERSION = "speaker-protocol-metrics.v1"
UNKNOWN_LABEL = "Unknown"
ELIGIBLE_QUALIFICATION_STATUSES = frozenset({"qualified", "qualified_with_warnings"})


class SpeakerProtocolError(ValueError):
    """Raised when a Stage 10 public contract is violated."""


@dataclass(frozen=True)
class BackendIdentity:
    """Result-affecting identity that binds an enrollment to one backend."""

    backend_id: str
    environment_profile: str
    model_id: str
    model_hash: str
    config_path: str
    config_hash: str
    embedding_dimension: int
    normalization: str
    preprocessing: Mapping[str, object]
    aggregation_method: str
    threshold_policy_version: str
    qualification_status: str

    def __post_init__(self) -> None:
        for name in (
            "backend_id",
            "environment_profile",
            "model_id",
            "model_hash",
            "config_path",
            "config_hash",
            "normalization",
            "aggregation_method",
            "threshold_policy_version",
            "qualification_status",
        ):
            if not str(getattr(self, name)).strip():
                raise SpeakerProtocolError(f"backend identity {name} must be non-empty")
        if self.embedding_dimension < 1:
            raise SpeakerProtocolError("embedding_dimension must be positive")
        for name in ("model_hash", "config_hash"):
            if not _is_sha256(str(getattr(self, name))):
                raise SpeakerProtocolError(f"{name} must be SHA-256")
        if self.normalization != "l2":
            raise SpeakerProtocolError("Stage 10 v1 requires L2-normalized embeddings")
        if self.threshold_policy_version != THRESHOLD_POLICY_VERSION:
            raise SpeakerProtocolError("unsupported threshold policy version")
        object.__setattr__(self, "preprocessing", dict(self.preprocessing))

    @property
    def identity_hash(self) -> str:
        return canonical_sha256(self.to_jsonable(include_hash=False))

    def to_jsonable(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": "speaker-backend-identity.v1",
            "backend_id": self.backend_id,
            "environment_profile": self.environment_profile,
            "model_id": self.model_id,
            "model_hash": self.model_hash.upper(),
            "config_path": self.config_path,
            "config_hash": self.config_hash.upper(),
            "embedding_dimension": self.embedding_dimension,
            "normalization": self.normalization,
            "preprocessing": dict(self.preprocessing),
            "aggregation_method": self.aggregation_method,
            "threshold_policy_version": self.threshold_policy_version,
            "qualification_status": self.qualification_status,
        }
        if include_hash:
            value["identity_hash"] = self.identity_hash
        return value

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "BackendIdentity":
        identity = cls(
            backend_id=_required(value, "backend_id"),
            environment_profile=_required(value, "environment_profile"),
            model_id=_required(value, "model_id"),
            model_hash=_required(value, "model_hash").upper(),
            config_path=_required(value, "config_path"),
            config_hash=_required(value, "config_hash").upper(),
            embedding_dimension=int(value.get("embedding_dimension") or 0),
            normalization=_required(value, "normalization"),
            preprocessing=_mapping(value.get("preprocessing"), "preprocessing"),
            aggregation_method=_required(value, "aggregation_method"),
            threshold_policy_version=_required(value, "threshold_policy_version"),
            qualification_status=_required(value, "qualification_status"),
        )
        declared_hash = value.get("identity_hash")
        if declared_hash is not None and str(declared_hash).upper() != identity.identity_hash:
            raise SpeakerProtocolError("backend identity hash mismatch")
        return identity


@dataclass(frozen=True)
class EmbeddingObservation:
    """One backend-bound extraction result consumed by protocol scoring."""

    item_id: str
    backend_id: str
    model_hash: str
    config_hash: str
    vector: tuple[float, ...] = ()
    status: str = "ok"
    duration_sec: float | None = None
    extraction_sec: float | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip() or not self.backend_id.strip():
            raise SpeakerProtocolError("embedding observation IDs must be non-empty")
        if self.status not in {"ok", "too_short", "failed", "missing", "invalid"}:
            raise SpeakerProtocolError(f"unsupported embedding status {self.status!r}")
        vector = tuple(float(value) for value in self.vector)
        object.__setattr__(self, "vector", vector)
        if self.status == "ok":
            if not vector or not all(math.isfinite(value) for value in vector):
                raise SpeakerProtocolError("successful embedding must be finite and non-empty")
            if not math.isclose(_norm(vector), 1.0, rel_tol=1e-4, abs_tol=1e-4):
                raise SpeakerProtocolError("successful embedding must be L2 normalized")
        elif vector:
            raise SpeakerProtocolError("failed embedding observations must not contain a vector")

    @property
    def dimension(self) -> int:
        return len(self.vector)


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SpeakerProtocolError("speaker protocol policy must be a mapping")
    expected = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "enrollment_schema_version": ENROLLMENT_SCHEMA_VERSION,
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "seed": 3800,
        "authoritative_representation": "parquet",
        "hash_algorithm": "sha256",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise SpeakerProtocolError(f"speaker protocol policy {key} must be {value!r}")
    privacy = _mapping(payload.get("privacy"), "privacy")
    authorized = privacy.get("authorized_demographic_fields")
    if not isinstance(authorized, list) or any(not str(value).strip() for value in authorized):
        raise SpeakerProtocolError("authorized demographic fields must be an explicit list")
    return {str(key): value for key, value in payload.items()}


def eligible_embedding_backends(
    policy: Mapping[str, object] | None = None,
    catalog: ComponentCatalog | None = None,
) -> dict[str, dict[str, object]]:
    active_policy = dict(policy or load_policy())
    declared = _mapping(active_policy.get("backends"), "backends")
    active_catalog = catalog or ComponentCatalog.load()
    result: dict[str, dict[str, object]] = {}
    for backend_id, raw in declared.items():
        row = _mapping(raw, f"backends.{backend_id}")
        entry = active_catalog.get("speaker_embedding", str(backend_id))
        allowed = {str(value) for value in row.get("qualification_statuses", [])}
        if entry.qualification_status not in ELIGIBLE_QUALIFICATION_STATUSES:
            continue
        if entry.qualification_status not in allowed:
            raise SpeakerProtocolError(
                f"{backend_id} qualification status is not admitted by Stage 10 policy"
            )
        profile = _required(row, "environment_profile")
        if profile not in entry.environment_profiles:
            raise SpeakerProtocolError(f"{backend_id} is incompatible with profile {profile}")
        if any(asset.get("present") is False for asset in entry.model_asset_identity):
            raise SpeakerProtocolError(f"{backend_id} has a missing model asset")
        result[str(backend_id)] = {
            "backend_id": str(backend_id),
            "environment_profile": profile,
            "qualification_status": entry.qualification_status,
            "config_path": entry.source_config_path,
            "config_hash": entry.source_config_sha256,
            "model_identity": dict(entry.model_identity),
            "model_asset_identity": [dict(value) for value in entry.model_asset_identity],
        }
    return result


def backend_identity(
    backend_id: str,
    embedding_dimension: int,
    *,
    policy: Mapping[str, object] | None = None,
    catalog: ComponentCatalog | None = None,
) -> BackendIdentity:
    active_policy = dict(policy or load_policy())
    active_catalog = catalog or ComponentCatalog.load()
    eligible = eligible_embedding_backends(active_policy, active_catalog)
    if backend_id not in eligible:
        raise SpeakerProtocolError(f"embedding backend is not Stage 10-qualified: {backend_id}")
    entry = active_catalog.get("speaker_embedding", backend_id)
    declared = eligible[backend_id]
    enrollment = _mapping(active_policy.get("enrollment"), "enrollment")
    model_payload = {
        "model_identity": dict(entry.model_identity),
        "model_asset_identity": [dict(value) for value in entry.model_asset_identity],
    }
    return BackendIdentity(
        backend_id=backend_id,
        environment_profile=str(declared["environment_profile"]),
        model_id=f"{backend_id}:{canonical_sha256(dict(entry.model_identity))[:12].lower()}",
        model_hash=canonical_sha256(model_payload),
        config_path=entry.source_config_path,
        config_hash=entry.source_config_sha256,
        embedding_dimension=int(embedding_dimension),
        normalization=str(enrollment["normalization"]),
        preprocessing=_mapping(enrollment.get("preprocessing"), "enrollment.preprocessing"),
        aggregation_method=str(enrollment["aggregation_method"]),
        threshold_policy_version=str(active_policy["threshold_policy_version"]),
        qualification_status=entry.qualification_status,
    )


def validate_enrollment_compatibility(
    enrollment_identity: BackendIdentity | Mapping[str, object],
    runtime_identity: BackendIdentity | Mapping[str, object],
) -> None:
    enrolled = (
        enrollment_identity
        if isinstance(enrollment_identity, BackendIdentity)
        else BackendIdentity.from_mapping(enrollment_identity)
    )
    runtime = (
        runtime_identity
        if isinstance(runtime_identity, BackendIdentity)
        else BackendIdentity.from_mapping(runtime_identity)
    )
    checked = (
        "backend_id",
        "model_id",
        "model_hash",
        "config_hash",
        "embedding_dimension",
        "normalization",
        "preprocessing",
        "aggregation_method",
        "threshold_policy_version",
    )
    mismatches = [name for name in checked if getattr(enrolled, name) != getattr(runtime, name)]
    if mismatches:
        raise SpeakerProtocolError(
            "enrollment is incompatible with runtime identity: " + ", ".join(mismatches)
        )


def privacy_safe_speaker_id(source_speaker_id: str, protocol_id: str) -> str:
    digest = canonical_sha256(
        {"protocol_id": protocol_id, "source_speaker_id": source_speaker_id, "seed": 3800}
    )
    return f"spk_{digest[:12].lower()}"


def privacy_safe_item_id(row: Mapping[str, object], protocol_id: str) -> str:
    digest = canonical_sha256(
        {
            "protocol_id": protocol_id,
            "source_recording_id": str(row["source_recording_id"]),
            "source_utterance_id": str(row["source_utterance_id"]),
            "protocol_condition": str(row["protocol_condition"]),
        }
    )
    return f"item_{digest[:16].lower()}"


def normalize_vector(values: Sequence[float]) -> tuple[float, ...]:
    vector = tuple(float(value) for value in values)
    norm = _norm(vector)
    if not vector or not math.isfinite(norm) or norm <= 0:
        raise SpeakerProtocolError("cannot normalize an empty or non-finite vector")
    return tuple(value / norm for value in vector)


def _norm(values: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in values))


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SpeakerProtocolError(f"{name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _required(value: Mapping[str, object], name: str) -> str:
    text = str(value.get(name) or "").strip()
    if not text:
        raise SpeakerProtocolError(f"{name} must be non-empty")
    return text


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value)
