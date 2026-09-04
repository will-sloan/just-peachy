"""Protected, backend-bound enrollment profiles for the streaming runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence
import uuid

import numpy as np


PROFILE_SCHEMA = "full-pipeline-enrollment-profile-store.v1"
PROFILE_ARCHIVE_SCHEMA = "full-pipeline-enrollment-profile-archive.v1"
PUBLIC_CONTRACT_SCHEMA = "full-pipeline-contracts.v1"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normal(vector: Sequence[float]) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(value))
    if value.size == 0 or not np.isfinite(norm) or norm <= 0:
        raise ValueError("enrollment vector must be finite and non-zero")
    return value / norm


@dataclass(frozen=True)
class EnrollmentTemplate:
    sample_id: str
    vector: np.ndarray
    duration_sec: float
    audio_sha256: str
    quality: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.duration_sec <= 0:
            raise ValueError("enrollment duration must be positive")
        object.__setattr__(self, "vector", _normal(self.vector))


@dataclass(frozen=True)
class RuntimeEnrollmentProfile:
    profile_id: str
    profile_sha256: str
    speaker_id: str
    display_label: str
    backend_id: str
    backend_config_sha256: str
    model_id: str
    model_sha256: str
    aggregation_method: str
    aggregation_top_k: int | None
    template_artifact: Path
    template_sha256: str
    templates: tuple[EnrollmentTemplate, ...]
    total_duration_sec: float
    within_enrollment_consistency: float
    state: str = "active"
    profile_version: int = 1
    supersedes_profile_id: str | None = None


@dataclass(frozen=True)
class ArchivedEnrollmentProfile:
    """Recoverable lifecycle record whose profile document stays byte-identical."""

    archive_id: str
    profile_id: str
    profile_sha256: str
    backend_id: str
    archived_at_utc: str
    reason: str
    replacement_profile_id: str | None
    archived_profile_path: Path
    archived_document_sha256: str


class ProtectedEnrollmentStore:
    """Keep biometric vectors in checksum-bound NPZ artifacts, not event JSONL."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.profile_root = self.root / "profiles"
        self.template_root = self.root / "biometric_templates"
        self.archive_profile_root = self.root / "archives" / "profiles"
        self.archive_receipt_root = self.root / "archives" / "receipts"

    def create_profile(
        self,
        *,
        speaker_id: str,
        display_label: str,
        backend_id: str,
        backend_config_sha256: str,
        model_id: str,
        model_sha256: str,
        aggregation_method: str,
        templates: Sequence[EnrollmentTemplate],
        aggregation_top_k: int | None = None,
        profile_id: str | None = None,
        minimum_consistency: float = 0.35,
        profile_version: int = 1,
        supersedes_profile_id: str | None = None,
    ) -> RuntimeEnrollmentProfile:
        values = tuple(templates)
        if not values:
            raise ValueError("at least one enrollment template is required")
        dimensions = {row.vector.size for row in values}
        if len(dimensions) != 1:
            raise ValueError("enrollment template dimensions are inconsistent")
        if aggregation_method not in {
            "normalized_mean",
            "duration_weighted_mean",
            "multi_template_max",
            "multi_template_top2_mean",
        }:
            raise ValueError(
                f"unsupported enrollment aggregation: {aggregation_method}"
            )
        if aggregation_method == "multi_template_top2_mean":
            aggregation_top_k = 2
        elif aggregation_method == "multi_template_max":
            aggregation_top_k = 1
        elif aggregation_top_k is not None:
            raise ValueError(
                "aggregation_top_k is only valid for multi-template aggregation"
            )
        profile_id = (
            profile_id
            or f"profile_{uuid.uuid5(uuid.NAMESPACE_URL, f'{backend_id}:{speaker_id}').hex}"
        )
        if profile_version < 1:
            raise ValueError("profile_version must be >= 1")
        self.profile_root.mkdir(parents=True, exist_ok=True)
        profile_path = self.profile_root / f"{profile_id}.json"
        if profile_path.exists():
            raise ValueError(
                f"enrollment profile ID already exists; create a new versioned ID: {profile_id}"
            )
        matrix = np.stack([row.vector for row in values]).astype(np.float32)
        durations = np.asarray([row.duration_sec for row in values], dtype=np.float32)
        consistency = self._consistency(matrix)
        state = "active" if consistency >= minimum_consistency else "invalidated"
        self.template_root.mkdir(parents=True, exist_ok=True)
        temporary = self.template_root / f".{profile_id}.{uuid.uuid4().hex}.tmp.npz"
        np.savez_compressed(
            temporary,
            vectors=matrix,
            durations_sec=durations,
            sample_ids=np.asarray([row.sample_id for row in values]),
            audio_sha256s=np.asarray([row.audio_sha256 for row in values]),
        )
        template_bytes = temporary.read_bytes()
        template_sha = _sha(template_bytes)
        template_path = self.template_root / f"{template_sha}.npz"
        if template_path.exists():
            temporary.unlink()
        else:
            temporary.replace(template_path)
        created = (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        metadata = {
            "schema_version": PROFILE_SCHEMA,
            "profile_id": profile_id,
            "profile_version": profile_version,
            "supersedes_profile_id": supersedes_profile_id,
            "speaker_id": speaker_id,
            "display_label": display_label,
            "state": state,
            "backend_id": backend_id,
            "backend_config_sha256": backend_config_sha256,
            "model_id": model_id,
            "model_sha256": model_sha256,
            "aggregation_method": aggregation_method,
            "aggregation_top_k": aggregation_top_k,
            "template_artifact": str(template_path.relative_to(self.root)).replace(
                "\\", "/"
            ),
            "template_sha256": template_sha,
            "sample_ids": [row.sample_id for row in values],
            "audio_sha256s": [row.audio_sha256 for row in values],
            "template_qualities": [
                json.loads(_canonical(dict(row.quality)).decode("utf-8"))
                for row in values
            ],
            "total_duration_sec": float(sum(row.duration_sec for row in values)),
            "within_enrollment_consistency": consistency,
            "created_at_utc": created,
            "updated_at_utc": created,
            "privacy": {
                "biometric_sensitive": True,
                "template_privacy_classification": "biometric_sensitive",
                "vectors_inline_in_event_logs": False,
            },
        }
        profile_sha = _sha(_canonical(metadata))
        document = {**metadata, "profile_sha256": profile_sha}
        temporary_json = profile_path.with_name(
            f".{profile_path.name}.{uuid.uuid4().hex}.tmp"
        )
        temporary_json.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary_json.replace(profile_path)
        return self._materialize(document, profile_path)

    def load_profiles(self, backend_id: str) -> tuple[RuntimeEnrollmentProfile, ...]:
        return self.list_profiles(backend_id=backend_id, states=("active",))

    def list_profiles(
        self,
        *,
        backend_id: str | None = None,
        states: Sequence[str] | None = None,
    ) -> tuple[RuntimeEnrollmentProfile, ...]:
        """List live profile documents without exposing vectors in status records."""

        if not self.profile_root.is_dir():
            return ()
        wanted_states = set(states) if states is not None else None
        profiles: list[RuntimeEnrollmentProfile] = []
        for path in sorted(self.profile_root.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if backend_id is not None and value.get("backend_id") != backend_id:
                continue
            if wanted_states is not None and value.get("state") not in wanted_states:
                continue
            profiles.append(self._materialize(value, path))
        return tuple(profiles)

    def get_profile(self, profile_id: str) -> RuntimeEnrollmentProfile:
        path = self.profile_root / f"{profile_id}.json"
        if not path.is_file():
            raise KeyError(profile_id)
        return self._materialize(json.loads(path.read_text(encoding="utf-8")), path)

    def save_profile(self, profile: RuntimeEnrollmentProfile) -> Path:
        path = self.profile_root / f"{profile.profile_id}.json"
        if not path.is_file():
            raise ValueError("profiles must be created through create_profile")
        return path

    def archive_profile(
        self,
        profile_id: str,
        *,
        reason: str,
        replacement_profile_id: str | None = None,
    ) -> ArchivedEnrollmentProfile:
        """Remove a profile from the active gallery while preserving exact metadata.

        The checksum-bound profile JSON is moved unchanged.  Lifecycle facts live
        in a separate receipt so a remove/rebuild never rewrites prior metadata.
        """

        normalized_reason = str(reason).strip()
        if not normalized_reason:
            raise ValueError("archive reason must be non-empty")
        source = self.profile_root / f"{profile_id}.json"
        if not source.is_file():
            raise KeyError(profile_id)
        document = json.loads(source.read_text(encoding="utf-8"))
        profile = self._materialize(document, source)
        source_bytes = source.read_bytes()
        document_sha = _sha(source_bytes)
        archived_at = (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        archive_id = f"archive_{uuid.uuid4().hex}"
        archived_path = (
            self.archive_profile_root
            / profile_id
            / f"{profile.profile_sha256}.json"
        )
        archived_path.parent.mkdir(parents=True, exist_ok=True)
        if archived_path.exists():
            if archived_path.read_bytes() != source_bytes:
                raise ValueError("archived profile identity collision")
            source.unlink()
        else:
            source.replace(archived_path)
        receipt = {
            "schema_version": PROFILE_ARCHIVE_SCHEMA,
            "archive_id": archive_id,
            "profile_id": profile_id,
            "profile_sha256": profile.profile_sha256,
            "backend_id": profile.backend_id,
            "archived_at_utc": archived_at,
            "reason": normalized_reason,
            "replacement_profile_id": replacement_profile_id,
            "archived_profile_path": str(archived_path.relative_to(self.root)).replace(
                "\\", "/"
            ),
            "archived_document_sha256": document_sha,
        }
        self.archive_receipt_root.mkdir(parents=True, exist_ok=True)
        receipt_path = self.archive_receipt_root / f"{archive_id}.json"
        temporary = receipt_path.with_name(f".{receipt_path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(receipt_path)
        return self._archive_record(receipt)

    def list_archives(
        self, *, profile_id: str | None = None
    ) -> tuple[ArchivedEnrollmentProfile, ...]:
        if not self.archive_receipt_root.is_dir():
            return ()
        rows: list[ArchivedEnrollmentProfile] = []
        for path in sorted(self.archive_receipt_root.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if profile_id is not None and value.get("profile_id") != profile_id:
                continue
            rows.append(self._archive_record(value))
        return tuple(rows)

    def restore_profile(
        self, profile_id: str, *, archive_id: str | None = None
    ) -> RuntimeEnrollmentProfile:
        """Restore an exact archived profile document to the live store."""

        if (self.profile_root / f"{profile_id}.json").exists():
            raise ValueError(f"profile is already present: {profile_id}")
        candidates = [
            row
            for row in self.list_archives(profile_id=profile_id)
            if archive_id is None or row.archive_id == archive_id
        ]
        if not candidates:
            raise KeyError(archive_id or profile_id)
        record = sorted(candidates, key=lambda row: row.archived_at_utc)[-1]
        source_bytes = record.archived_profile_path.read_bytes()
        if _sha(source_bytes) != record.archived_document_sha256:
            raise ValueError("archived enrollment profile checksum mismatch")
        destination = self.profile_root / f"{profile_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(source_bytes)
        temporary.replace(destination)
        return self.get_profile(profile_id)

    def _archive_record(
        self, value: Mapping[str, object]
    ) -> ArchivedEnrollmentProfile:
        if value.get("schema_version") != PROFILE_ARCHIVE_SCHEMA:
            raise ValueError("unsupported enrollment archive receipt")
        archived_path = (self.root / str(value["archived_profile_path"])).resolve()
        if not archived_path.is_file():
            raise ValueError(f"archived enrollment profile is missing: {archived_path}")
        document_sha = str(value["archived_document_sha256"])
        if _sha(archived_path.read_bytes()) != document_sha:
            raise ValueError("archived enrollment profile checksum mismatch")
        return ArchivedEnrollmentProfile(
            archive_id=str(value["archive_id"]),
            profile_id=str(value["profile_id"]),
            profile_sha256=str(value["profile_sha256"]),
            backend_id=str(value["backend_id"]),
            archived_at_utc=str(value["archived_at_utc"]),
            reason=str(value["reason"]),
            replacement_profile_id=(
                str(value["replacement_profile_id"])
                if value.get("replacement_profile_id") is not None
                else None
            ),
            archived_profile_path=archived_path,
            archived_document_sha256=document_sha,
        )

    def _materialize(
        self, value: Mapping[str, object], profile_path: Path
    ) -> RuntimeEnrollmentProfile:
        if value.get("schema_version") != PROFILE_SCHEMA:
            raise ValueError(f"unsupported enrollment profile: {profile_path}")
        embedded_sha = str(value.get("profile_sha256", ""))
        unsigned = {key: item for key, item in value.items() if key != "profile_sha256"}
        if _sha(_canonical(unsigned)) != embedded_sha:
            raise ValueError(f"enrollment profile checksum mismatch: {profile_path}")
        template_path = (self.root / str(value["template_artifact"])).resolve()
        if (
            not template_path.is_file()
            or _sha(template_path.read_bytes()) != value["template_sha256"]
        ):
            raise ValueError(f"enrollment template checksum mismatch: {template_path}")
        bundle = np.load(template_path, allow_pickle=False)
        vectors = bundle["vectors"]
        durations = bundle["durations_sec"]
        sample_ids = bundle["sample_ids"]
        audio_sha256s = bundle["audio_sha256s"]
        qualities = value.get("template_qualities")
        if not isinstance(qualities, list) or len(qualities) != len(vectors):
            qualities = [{} for _ in range(len(vectors))]
        templates = tuple(
            EnrollmentTemplate(
                sample_id=str(sample_ids[index]),
                vector=vectors[index],
                duration_sec=float(durations[index]),
                audio_sha256=str(audio_sha256s[index]),
                quality=(
                    dict(qualities[index])
                    if isinstance(qualities[index], Mapping)
                    else {}
                ),
            )
            for index in range(len(vectors))
        )
        return RuntimeEnrollmentProfile(
            profile_id=str(value["profile_id"]),
            profile_sha256=embedded_sha,
            speaker_id=str(value["speaker_id"]),
            display_label=str(value["display_label"]),
            backend_id=str(value["backend_id"]),
            backend_config_sha256=str(value["backend_config_sha256"]),
            model_id=str(value["model_id"]),
            model_sha256=str(value["model_sha256"]),
            aggregation_method=str(value["aggregation_method"]),
            aggregation_top_k=(
                int(value["aggregation_top_k"])
                if value.get("aggregation_top_k") is not None
                else None
            ),
            template_artifact=template_path,
            template_sha256=str(value["template_sha256"]),
            templates=templates,
            total_duration_sec=float(value["total_duration_sec"]),
            within_enrollment_consistency=float(value["within_enrollment_consistency"]),
            state=str(value["state"]),
            profile_version=int(value.get("profile_version", 1)),
            supersedes_profile_id=(
                str(value["supersedes_profile_id"])
                if value.get("supersedes_profile_id") is not None
                else None
            ),
        )

    def status(self) -> dict[str, object]:
        files = (
            list(self.profile_root.glob("*.json")) if self.profile_root.is_dir() else []
        )
        return {
            "schema_version": PROFILE_SCHEMA,
            "root": str(self.root),
            "profile_count": len(files),
            "archived_profile_count": len(self.list_archives()),
            "biometric_vectors_inline_in_status": False,
        }

    @staticmethod
    def _consistency(matrix: np.ndarray) -> float:
        if len(matrix) < 2:
            return 1.0
        # Enrollment matrices are tiny.  Keep this as an explicit reduction so
        # repeated quality checks do not depend on a platform BLAS dispatcher
        # (the campaign's Windows MKL build can abort on many tiny products).
        scores = np.einsum("ij,kj->ik", matrix, matrix, optimize=False)
        values = scores[np.triu_indices(len(matrix), k=1)]
        observed = float(np.min(values)) if values.size else 1.0
        return max(-1.0, min(1.0, observed))


def score_profile(query: Sequence[float], profile: RuntimeEnrollmentProfile) -> float:
    """Apply the exact backend-specific frozen enrollment aggregation."""

    value = _normal(query)
    vectors = np.stack([row.vector for row in profile.templates])
    scores = np.sum(vectors * value, axis=1)
    if profile.aggregation_method == "multi_template_max":
        return float(np.max(scores))
    if profile.aggregation_method == "multi_template_top2_mean":
        top = np.sort(scores)[-min(2, scores.size) :]
        return float(np.mean(top))
    if profile.aggregation_method == "duration_weighted_mean":
        durations = np.asarray([row.duration_sec for row in profile.templates])
        centroid = _normal(np.average(vectors, axis=0, weights=durations))
        return float(np.sum(centroid * value))
    centroid = _normal(np.mean(vectors, axis=0))
    return float(np.sum(centroid * value))


def export_public_enrollment_contracts(
    *,
    output_root: Path,
    profile: RuntimeEnrollmentProfile,
    backend_axis: Mapping[str, object],
    enrollment_policy: Mapping[str, object],
    runtime_config_sha256: str,
    source_audio_path: Path,
    sample_ranges_sec: Sequence[tuple[float, float]],
) -> dict[str, object]:
    """Write locked EnrollmentSample/Profile views over protected store artifacts.

    The operational profile remains the compact store document used by the
    runtime. These additive public views carry portable artifact references and
    never inline audio or biometric vectors.
    """

    root = Path(output_root).resolve()
    source = Path(source_audio_path).resolve()
    if len(sample_ranges_sec) != len(profile.templates):
        raise ValueError("sample ranges must match enrollment template count")
    source_bytes = source.read_bytes()
    source_sha = _sha(source_bytes)
    created = (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    sample_root = root / "contracts/enrollment_samples" / profile.backend_id
    profile_root = root / "contracts/enrollment_profiles"
    sample_root.mkdir(parents=True, exist_ok=True)
    profile_root.mkdir(parents=True, exist_ok=True)
    source_logical = _portable_source_path(source)
    audio_reference = _artifact_reference(
        artifact_id=f"audio_{source_sha[:24]}",
        logical_path=source_logical,
        resolver_alias="ENROLLMENT_AUDIO_ROOT",
        sha256=source_sha,
        byte_count=len(source_bytes),
        schema_version="audio-waveform.v1",
        media_type="audio/wav",
    )
    template_relative = _portable_relative(profile.template_artifact, root)
    template_reference = _artifact_reference(
        artifact_id=f"template_{profile.template_sha256[:24]}",
        logical_path=template_relative,
        resolver_alias="FULL_PIPELINE_ENROLLMENT_SMOKE_ROOT",
        sha256=profile.template_sha256,
        byte_count=profile.template_artifact.stat().st_size,
        schema_version=PROFILE_SCHEMA,
        media_type="application/x-npz",
    )
    backend_identity = _public_backend_identity(
        profile, backend_axis, enrollment_policy, runtime_config_sha256
    )
    provenance = {
        "source_dataset_id": None,
        "source_asset_id": source.stem,
        "source_asset_sha256": source_sha,
        "acquisition_route_id": "bounded_local_enrollment_smoke_input",
        "license_identifier": "SOURCE_ASSET_PROVENANCE_REVIEW_REQUIRED",
        "attribution_requirements": [],
        "redistribution_review_status": "unresolved",
        "gated_acquisition": False,
        "deployability_status": "unknown",
        "commercial_review_status": "unresolved",
        "notes": "Functional smoke only; no redistribution or production claim.",
    }
    privacy = {
        "classification": "biometric_sensitive",
        "biometric_sensitive": True,
        "private_identity_mapping_included": True,
        "consent_or_authorization_basis": "local_operator_authorized_smoke",
        "retention_policy_id": "full_pipeline_smoke_ephemeral.v1",
        "access_policy_id": "local_operator_only.v1",
        "redistribution_permitted": False,
    }
    sample_references: list[dict[str, object]] = []
    sample_hashes: list[str] = []
    sample_paths: list[str] = []
    for template, (start_sec, end_sec) in zip(
        profile.templates, sample_ranges_sec, strict=True
    ):
        sample = {
            "schema_version": PUBLIC_CONTRACT_SCHEMA,
            "contract_type": "EnrollmentSample",
            "sample_id": template.sample_id,
            "speaker_id": profile.speaker_id,
            "display_label": profile.display_label,
            "prompt_id": "bounded_repository_smoke_segment",
            "created_at_utc": created,
            "source_clock": {
                "clock_id": f"external_media:{source.stem}",
                "clock_type": "external_media",
                "sample_rate_hz": 16000,
                "utc_epoch": None,
                "monotonic_epoch_ns": None,
                "external_timebase": "source_file_media_time",
                "drift_parts_per_million": None,
            },
            "capture_timestamps": {
                "sample_start_index": round(start_sec * 16000),
                "sample_end_index": round(end_sec * 16000),
                "audio_start_sec": start_sec,
                "audio_end_sec": end_sec,
                "capture_start_monotonic_ns": None,
                "capture_end_monotonic_ns": None,
                "capture_start_utc": None,
                "capture_end_utc": None,
                "discontinuity_before": False,
                "dropped_sample_count_before": 0,
            },
            "sample_rate_hz": 16000,
            "channel_count": 1,
            "duration_sec": end_sec - start_sec,
            "audio_artifact": audio_reference,
            "audio_sha256": source_sha,
            "embedding_artifact": template_reference,
            "embedding_sha256": profile.template_sha256,
            "embedding_status": "ok",
            "backend_identity": backend_identity,
            "quality": {
                "status": "accepted_with_warnings",
                "policy_id": "full_pipeline_enrollment_smoke_quality.v1",
                "policy_sha256": runtime_config_sha256,
                "metrics": {
                    "duration_sec": end_sec - start_sec,
                    "smoke_only": True,
                },
                "reason_codes": ["smoke_only_not_production_enrollment"],
            },
            "provenance": provenance,
            "privacy": privacy,
            "notes": "Embedding artifact is a protected multi-template bundle; sample_id selects this row.",
        }
        path = sample_root / f"{template.sample_id}.json"
        _atomic_json(path, sample)
        digest = _sha(path.read_bytes())
        sample_hashes.append(digest)
        sample_paths.append(_portable_relative(path, root))
        sample_references.append(
            _artifact_reference(
                artifact_id=f"enrollment_sample_{digest[:24]}",
                logical_path=_portable_relative(path, root),
                resolver_alias="FULL_PIPELINE_ENROLLMENT_SMOKE_ROOT",
                sha256=digest,
                byte_count=path.stat().st_size,
                schema_version=PUBLIC_CONTRACT_SCHEMA,
                media_type="application/json",
            )
        )
    consistency_ok = profile.within_enrollment_consistency >= 0.35
    public_aggregation_top_k = _public_aggregation_top_k(profile)
    public_profile = {
        "schema_version": PUBLIC_CONTRACT_SCHEMA,
        "contract_type": "EnrollmentProfile",
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "profile_sha256": profile.profile_sha256,
        "speaker_id": profile.speaker_id,
        "display_label": profile.display_label,
        "state": profile.state,
        "created_at_utc": created,
        "updated_at_utc": created,
        "invalidated_at_utc": created if profile.state == "invalidated" else None,
        "invalidation_reason": (
            "within_enrollment_consistency_below_gate"
            if profile.state == "invalidated"
            else None
        ),
        "backend_identity": backend_identity,
        "threshold_identity": {
            "threshold_policy_id": "full_pipeline_enrollment_smoke_unresolved.v1",
            "threshold_policy_sha256": runtime_config_sha256,
            "calibration_protocol_id": "functional_smoke_only",
            "calibration_result_sha256": runtime_config_sha256,
            "operating_mode": "SMOKE_ONLY_NO_PRODUCTION_DECISION",
            "gallery_size": 1,
            "raw_score_type": "cosine_similarity",
            "score_threshold": 2.0,
            "margin_threshold": 2.0,
            "minimum_evidence_sec": 2.0,
            "target_fpir": None,
            "selection_tier": "development_required",
        },
        "sample_references": sample_references,
        "sample_sha256s": sample_hashes,
        "aggregation_method": profile.aggregation_method,
        "aggregation_top_k": public_aggregation_top_k,
        "template_artifacts": [template_reference],
        "template_set_sha256": profile.template_sha256,
        "quality": {
            "status": "accepted_with_warnings" if consistency_ok else "rejected",
            "policy_id": "full_pipeline_enrollment_smoke_quality.v1",
            "policy_sha256": runtime_config_sha256,
            "metrics": {
                "within_enrollment_consistency": profile.within_enrollment_consistency,
                "minimum_required_consistency": 0.35,
                "smoke_only": True,
            },
            "reason_codes": (
                ["smoke_only_not_production_enrollment"]
                if consistency_ok
                else ["within_enrollment_consistency_below_gate"]
            ),
        },
        "provenance": provenance,
        "privacy": privacy,
        "total_enrollment_duration_sec": profile.total_duration_sec,
        "within_enrollment_consistency": profile.within_enrollment_consistency,
    }
    public_profile_path = profile_root / f"{profile.profile_id}.json"
    _atomic_json(public_profile_path, public_profile)
    return {
        "sample_contract_paths": sample_paths,
        "profile_contract_path": _portable_relative(public_profile_path, root),
        "profile_quality_status": public_profile["quality"]["status"],
    }


def _public_backend_identity(
    profile: RuntimeEnrollmentProfile,
    backend_axis: Mapping[str, object],
    enrollment_policy: Mapping[str, object],
    runtime_config_sha256: str,
) -> dict[str, object]:
    return {
        "backend_id": profile.backend_id,
        "environment_profile_id": str(backend_axis["environment_profile"]),
        "model_id": profile.model_id,
        "model_sha256": profile.model_sha256,
        "backend_config_id": str(backend_axis["registry_id"]),
        "backend_config_sha256": profile.backend_config_sha256,
        "embedding_dimension": int(profile.templates[0].vector.size),
        "normalization": "l2",
        "preprocessing_policy_id": "full_pipeline_audio_normalization.v1",
        "preprocessing_policy_sha256": runtime_config_sha256,
        "aggregation_method": profile.aggregation_method,
        "aggregation_top_k": _public_aggregation_top_k(profile),
        "identity_sha256": str(backend_axis["backend_identity_sha256"]),
        "qualification_status": str(
            backend_axis.get("qualification_status") or "unknown"
        ),
    }


def _public_aggregation_top_k(profile: RuntimeEnrollmentProfile) -> int | None:
    if profile.aggregation_method == "multi_template_top2_mean":
        return 2
    if profile.aggregation_method == "multi_template_top_k_mean":
        return profile.aggregation_top_k
    return None


def _artifact_reference(
    *,
    artifact_id: str,
    logical_path: str,
    resolver_alias: str,
    sha256: str,
    byte_count: int,
    schema_version: str,
    media_type: str,
) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "logical_path": logical_path,
        "resolver_alias": resolver_alias,
        "sha256": sha256,
        "byte_count": byte_count,
        "artifact_schema_version": schema_version,
        "media_type": media_type,
        "privacy_classification": "biometric_sensitive",
    }


def _portable_source_path(path: Path) -> str:
    evaluation_root = Path(__file__).resolve().parents[2]
    try:
        return _portable_relative(path, evaluation_root)
    except ValueError:
        return (
            f"external_enrollment_audio/{_sha(path.read_bytes())}{path.suffix.lower()}"
        )


def _portable_relative(path: Path, root: Path) -> str:
    return str(Path(path).resolve().relative_to(Path(root).resolve())).replace(
        "\\", "/"
    )


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
