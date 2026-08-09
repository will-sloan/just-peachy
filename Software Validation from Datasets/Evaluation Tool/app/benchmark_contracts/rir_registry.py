"""Exact RIR identity registry, discrepancy audit, and condition resolution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Mapping

import yaml

from app.benchmark_contracts.canonical import normalize_project_relative_path


class RIRRegistryError(ValueError):
    """Raised when an RIR identity is missing, inaccurate, or unapproved."""


@dataclass(frozen=True)
class RIRRecord:
    """One requested-to-resolved RIR identity."""

    rir_id: str
    environment: str
    requested_identifier: str
    resolved_identifier: str | None
    relative_path: str | None
    sha256: str | None
    bytes: int | None
    status: str
    discrepancy_note: str | None

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "RIRRecord":
        return cls(
            rir_id=_required_text(value, "rir_id"),
            environment=_required_text(value, "environment"),
            requested_identifier=_required_text(value, "requested_identifier"),
            resolved_identifier=_optional_text(value.get("resolved_identifier")),
            relative_path=_optional_path(value.get("relative_path")),
            sha256=_optional_hash(value.get("sha256")),
            bytes=_optional_int(value.get("bytes")),
            status=_required_text(value, "status"),
            discrepancy_note=_optional_text(value.get("discrepancy_note")),
        )

    def identity(self) -> dict[str, object]:
        """Return the exact result-affecting identity used by a condition."""

        if self.status != "approved":
            raise RIRRegistryError(f"RIR {self.rir_id} is not approved: {self.status}")
        if not self.relative_path or not self.sha256 or not self.resolved_identifier:
            raise RIRRegistryError(f"approved RIR {self.rir_id} has incomplete identity")
        return {
            "rir_id": self.rir_id,
            "environment": self.environment,
            "resolved_identifier": self.resolved_identifier,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class RIRRegistry:
    """Versioned registry loaded from the committed Stage 2 YAML."""

    schema_version: str
    collection_root_project_relative: str
    collection_label_expected_wav_count: int
    records: tuple[RIRRecord, ...]
    bedroom_candidates: tuple[tuple[str, str, int], ...]
    source_path: Path

    @classmethod
    def load(cls, path: Path | str | None = None) -> "RIRRegistry":
        tool_root = Path(__file__).resolve().parents[2]
        source = (
            Path(path).resolve()
            if path is not None
            else tool_root / "configs" / "automated_evaluation" / "rir_registry.v1.yaml"
        )
        data = _yaml_mapping(source)
        if data.get("schema_version") != "rir-registry.v1":
            raise RIRRegistryError(f"unsupported RIR registry: {data.get('schema_version')!r}")
        raw_records = data.get("records")
        if not isinstance(raw_records, list):
            raise RIRRegistryError("RIR registry records must be a list")
        records = tuple(RIRRecord.from_mapping(item) for item in raw_records if isinstance(item, Mapping))
        if len(records) != len(raw_records):
            raise RIRRegistryError("every RIR record must be a mapping")
        if len({item.rir_id for item in records}) != len(records):
            raise RIRRegistryError("RIR IDs must be unique")
        candidates: list[tuple[str, str, int]] = []
        for raw in data.get("bedroom_candidates") or []:
            if not isinstance(raw, list) or len(raw) != 3:
                raise RIRRegistryError("bedroom candidate must be [filename, sha256, bytes]")
            candidates.append((str(raw[0]), str(raw[1]).upper(), int(raw[2])))
        registry = cls(
            schema_version="rir-registry.v1",
            collection_root_project_relative=normalize_project_relative_path(
                _required_text(data, "collection_root_project_relative")
            ),
            collection_label_expected_wav_count=int(
                data.get("collection_label_expected_wav_count") or 0
            ),
            records=records,
            bedroom_candidates=tuple(candidates),
            source_path=source,
        )
        registry._validate_semantics()
        return registry

    def get(self, rir_id: str) -> RIRRecord:
        for record in self.records:
            if record.rir_id == rir_id:
                return record
        raise RIRRegistryError(f"unknown RIR ID {rir_id!r}")

    def approved(self) -> tuple[RIRRecord, ...]:
        return tuple(record for record in self.records if record.status == "approved")

    def audit(self, project_root: Path) -> dict[str, object]:
        """Verify committed paths, sizes, hashes, unresolved requests, and candidates."""

        collection_root = project_root / self.collection_root_project_relative
        if not collection_root.is_dir():
            raise FileNotFoundError(f"RIR collection not found: {collection_root}")
        actual_names = {path.name for path in collection_root.iterdir() if path.is_file()}
        rows: list[dict[str, object]] = []
        for record in self.records:
            actual_path = (
                project_root / record.relative_path if record.relative_path is not None else None
            )
            exists = bool(actual_path and actual_path.is_file())
            observed_hash = _sha256(actual_path) if exists and actual_path is not None else None
            observed_bytes = actual_path.stat().st_size if exists and actual_path is not None else None
            if record.resolved_identifier and record.resolved_identifier not in actual_names:
                exists = False
            matches = (
                exists
                and observed_hash == record.sha256
                and observed_bytes == record.bytes
            )
            if record.status in {"approved", "excluded"} and not matches:
                raise RIRRegistryError(f"RIR identity mismatch for {record.rir_id}")
            rows.append(
                {
                    "rir_id": record.rir_id,
                    "environment": record.environment,
                    "requested_identifier": record.requested_identifier,
                    "resolved_identifier": record.resolved_identifier,
                    "actual_relative_path": record.relative_path,
                    "expected_sha256": record.sha256,
                    "observed_sha256": observed_hash,
                    "expected_bytes": record.bytes,
                    "observed_bytes": observed_bytes,
                    "status": record.status,
                    "identity_matches": matches if record.status != "unresolved" else None,
                    "discrepancy_note": record.discrepancy_note,
                }
            )
        candidate_rows: list[dict[str, object]] = []
        for filename, expected_hash, expected_bytes in self.bedroom_candidates:
            path = collection_root / filename
            observed_hash = _sha256(path) if path.is_file() else None
            observed_bytes = path.stat().st_size if path.is_file() else None
            if observed_hash != expected_hash or observed_bytes != expected_bytes:
                raise RIRRegistryError(f"bedroom candidate identity mismatch: {filename}")
            candidate_rows.append(
                {
                    "filename": filename,
                    "sha256": observed_hash,
                    "bytes": observed_bytes,
                    "status": "candidate_unapproved",
                }
            )
        observed_wav_count = len(
            [name for name in actual_names if name.lower().endswith(".wav")]
        )
        return {
            "schema_version": "rir-audit.v1",
            "registry_schema_version": self.schema_version,
            "collection_root_project_relative": self.collection_root_project_relative,
            "collection_label_expected_wav_count": self.collection_label_expected_wav_count,
            "collection_wav_count": observed_wav_count,
            "collection_count_discrepancy_note": (
                None
                if observed_wav_count == self.collection_label_expected_wav_count
                else (
                    f"Collection label implies {self.collection_label_expected_wav_count} WAVs, "
                    f"but the inspected directory contains {observed_wav_count}."
                )
            ),
            "records": rows,
            "bedroom_candidates": candidate_rows,
        }

    def _validate_semantics(self) -> None:
        kitchen = self.get("kitchen_h044_unresolved")
        parking = self.get("parking_lot_h044")
        if kitchen.status != "unresolved" or kitchen.resolved_identifier is not None:
            raise RIRRegistryError("historical h044 kitchen request must remain unresolved")
        if parking.environment != "ParkingLot" or parking.status != "excluded":
            raise RIRRegistryError("h044 ParkingLot must retain accurate excluded identity")
        if any(item.environment == "Kitchen" and item.status == "approved" for item in self.records):
            raise RIRRegistryError("no kitchen RIR is approved in v1")
        if self.get("bedroom_unresolved").status != "unresolved":
            raise RIRRegistryError("bedroom must remain unresolved pending exact approval")


def load_condition_sets(
    registry: RIRRegistry,
    path: Path | str | None = None,
) -> dict[str, tuple[dict[str, object], ...]]:
    """Load named conditions and replace each approved RIR ID with exact identity."""

    tool_root = Path(__file__).resolve().parents[2]
    source = (
        Path(path).resolve()
        if path is not None
        else tool_root / "configs" / "automated_evaluation" / "condition_sets.v1.yaml"
    )
    data = _yaml_mapping(source)
    if data.get("schema_version") != "condition-sets.v1":
        raise RIRRegistryError(f"unsupported condition set schema: {data.get('schema_version')!r}")
    raw_sets = data.get("condition_sets")
    if not isinstance(raw_sets, Mapping):
        raise RIRRegistryError("condition_sets must be a mapping")
    resolved: dict[str, tuple[dict[str, object], ...]] = {}
    for set_name, values in raw_sets.items():
        if not isinstance(values, list):
            raise RIRRegistryError(f"condition set {set_name} must be a list")
        conditions: list[dict[str, object]] = []
        for raw in values:
            if not isinstance(raw, Mapping):
                raise RIRRegistryError(f"condition in {set_name} must be a mapping")
            rir_id = _optional_text(raw.get("rir_id"))
            conditions.append(
                {
                    "id": _required_text(raw, "id"),
                    "augmentation": _required_text(raw, "augmentation"),
                    "noise_type": _optional_text(raw.get("noise_type")),
                    "snr_db": float(raw["snr_db"]) if raw.get("snr_db") is not None else None,
                    "rir": registry.get(rir_id).identity() if rir_id else None,
                }
            )
        resolved[str(set_name)] = tuple(conditions)
    expected = {
        "smoke",
        "core_controlled",
        "all_approved_rir_environments",
        "selected_rir_plus_noise_interactions",
    }
    if not expected.issubset(resolved):
        raise RIRRegistryError(f"missing required named condition sets: {sorted(expected - resolved.keys())}")
    return resolved


def _yaml_mapping(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RIRRegistryError(f"expected YAML mapping in {path}")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _required_text(value: Mapping[str, object], field: str) -> str:
    text = _optional_text(value.get(field))
    if text is None:
        raise RIRRegistryError(f"missing required RIR field {field}")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_path(value: object) -> str | None:
    text = _optional_text(value)
    return normalize_project_relative_path(text) if text is not None else None


def _optional_hash(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    upper = text.upper()
    if len(upper) != 64 or any(char not in "0123456789ABCDEF" for char in upper):
        raise RIRRegistryError(f"invalid SHA-256 {value!r}")
    return upper


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)
