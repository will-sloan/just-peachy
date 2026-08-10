"""Atomic artifact publication and SHA-256 manifest maintenance."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Iterable, Mapping
import uuid

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from app.artifact_contracts.registry import (
    ArtifactDefinition,
    ArtifactRegistry,
    ArtifactRegistryError,
    normalize_artifact_path,
)
from app.artifact_contracts.schemas import validate_artifact


PhaseHook = Callable[[str, Path], None]
TemporaryWriter = Callable[[Path], None]

_TRANSIENT_WINDOWS_FILE_ERROR_CODES = frozenset({5, 32, 33})
_FILE_OPERATION_RETRY_DELAYS_SEC = (0.025, 0.05, 0.1, 0.2, 0.4, 0.8)


class AtomicArtifactError(RuntimeError):
    """Raised when an artifact cannot be safely published."""


class ScenarioArtifactStore:
    """Publish registered scenario artifacts and maintain checksums.json."""

    def __init__(
        self,
        scenario_root: Path,
        scenario_id: str,
        *,
        registry: ArtifactRegistry | None = None,
        phase_hook: PhaseHook | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.scenario_root = scenario_root.resolve()
        self.scenario_id = scenario_id
        self.registry = registry or ArtifactRegistry.load()
        self.phase_hook = phase_hook
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()

    def publish_json(self, relative_path: str, value: object) -> dict[str, object]:
        payload = (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        return self.publish_bytes(relative_path, payload)

    def publish_jsonl(
        self,
        relative_path: str,
        rows: Iterable[Mapping[str, object]],
    ) -> dict[str, object]:
        materialized = [dict(row) for row in rows]
        payload = "".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
            for row in materialized
        ).encode("utf-8")
        return self.publish_bytes(relative_path, payload)

    def publish_yaml(
        self, relative_path: str, value: Mapping[str, object]
    ) -> dict[str, object]:
        payload = yaml.safe_dump(
            dict(value), sort_keys=False, allow_unicode=True
        ).encode("utf-8")
        return self.publish_bytes(relative_path, payload)

    def publish_text(self, relative_path: str, value: str) -> dict[str, object]:
        return self.publish_bytes(relative_path, value.encode("utf-8"))

    def publish_parquet(self, relative_path: str, table: pa.Table) -> dict[str, object]:
        definition = self._definition(relative_path)
        if definition.format != "parquet":
            raise ArtifactRegistryError(f"{relative_path} is not registered as Parquet")
        metadata = dict(table.schema.metadata or {})
        metadata[b"artifact_schema_version"] = definition.schema_version.encode("utf-8")
        prepared = table.replace_schema_metadata(metadata)

        def writer(path: Path) -> None:
            pq.write_table(prepared, path, version="2.6", compression="NONE")

        return self._publish(relative_path, definition, writer)

    def publish_npz(
        self,
        relative_path: str,
        arrays: Mapping[str, object],
    ) -> dict[str, object]:
        definition = self._definition(relative_path)
        if definition.format != "npz":
            raise ArtifactRegistryError(f"{relative_path} is not registered as NPZ")
        values: dict[str, np.ndarray] = {
            str(key): np.asarray(value) for key, value in arrays.items()
        }
        values["schema_version"] = np.asarray([definition.schema_version])

        def writer(path: Path) -> None:
            with path.open("wb") as handle:
                np.savez(handle, **values)

        return self._publish(relative_path, definition, writer)

    def publish_bytes(self, relative_path: str, payload: bytes) -> dict[str, object]:
        definition = self._definition(relative_path)

        def writer(path: Path) -> None:
            with path.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

        return self._publish(relative_path, definition, writer)

    def reconcile_checksum_manifest(self) -> dict[str, object]:
        """Revalidate registered files and rebuild checksums after an interrupted commit."""

        with self._lock:
            entries: dict[str, object] = {}
            scenario_hash = self._resolved_scenario_hash()
            for path in sorted(self.scenario_root.rglob("*")):
                if not path.is_file() or is_temporary_artifact(path, self.registry):
                    continue
                relative = path.relative_to(self.scenario_root).as_posix()
                if relative == "checksums.json":
                    continue
                definition = self.registry.match("scenario", relative)
                validate_artifact(
                    path,
                    definition,
                    scenario_id=self.scenario_id,
                    scenario_hash=scenario_hash,
                )
                entries[relative] = checksum_entry(path, definition)
            payload = self._checksum_payload(entries)
            self._write_checksum_manifest(payload)
            return payload

    def _definition(self, relative_path: str) -> ArtifactDefinition:
        definition = self.registry.match("scenario", relative_path)
        if definition.artifact_id == "checksums":
            raise AtomicArtifactError(
                "checksums.json is maintained internally and cannot be published recursively"
            )
        if definition.checksum_policy != "sha256":
            raise AtomicArtifactError(
                f"scenario artifact {definition.artifact_id} must use SHA-256 policy"
            )
        return definition

    def _publish(
        self,
        relative_path: str,
        definition: ArtifactDefinition,
        writer: TemporaryWriter,
    ) -> dict[str, object]:
        normalized = normalize_artifact_path(relative_path)
        target = self._target(normalized)
        with self._lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(
                f".{target.name}{self.registry.temporary_file_marker}{uuid.uuid4().hex}"
            )
            try:
                writer(temporary)
                _fsync_file(temporary)
                self._phase("after_write", target)
                validate_artifact(
                    temporary,
                    definition,
                    scenario_id=self.scenario_id,
                    scenario_hash=self._resolved_scenario_hash(),
                )
                self._phase("after_validate", target)
                entry = checksum_entry(temporary, definition)
                self._phase("after_checksum", target)
                replace_file_with_retry(temporary, target)
                _fsync_directory(target.parent)
                self._phase("after_replace", target)
                manifest = self._read_checksum_manifest()
                raw_entries = manifest.get("entries")
                if not isinstance(raw_entries, Mapping):
                    raise AtomicArtifactError("checksum entries must be a mapping")
                entries = dict(raw_entries)
                entries[normalized] = entry
                self._phase("before_checksum_manifest", target)
                self._write_checksum_manifest(self._checksum_payload(entries))
                self._phase("after_checksum_manifest", target)
                return entry
            except BaseException:
                best_effort_unlink(temporary)
                raise

    def _read_checksum_manifest(self) -> dict[str, object]:
        path = self.scenario_root / "checksums.json"
        if not path.exists():
            return self._checksum_payload({})
        definition = self.registry.get("checksums")
        inspection = validate_artifact(path, definition, scenario_id=self.scenario_id)
        value = dict(inspection.values or {})
        entries = value.get("entries")
        if not isinstance(entries, Mapping):
            raise AtomicArtifactError("checksum manifest entries must be a mapping")
        for relative, raw in entries.items():
            registered = self.registry.match("scenario", str(relative))
            if registered.artifact_id == "checksums" or not isinstance(raw, Mapping):
                raise AtomicArtifactError(f"invalid checksum entry {relative!r}")
            if (
                raw.get("artifact_id") != registered.artifact_id
                or raw.get("schema_version") != registered.schema_version
            ):
                raise AtomicArtifactError(
                    f"checksum entry identity mismatch: {relative}"
                )
        return value

    def _write_checksum_manifest(self, payload: Mapping[str, object]) -> None:
        path = self.scenario_root / "checksums.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(
            f".{path.name}{self.registry.temporary_file_marker}{uuid.uuid4().hex}"
        )
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            validate_artifact(
                temporary,
                self.registry.get("checksums"),
                scenario_id=self.scenario_id,
            )
            replace_file_with_retry(temporary, path)
            _fsync_directory(path.parent)
        finally:
            best_effort_unlink(temporary)

    def _checksum_payload(self, entries: Mapping[str, object]) -> dict[str, object]:
        return {
            "schema_version": self.registry.checksum_manifest_schema_version,
            "artifact_registry_version": self.registry.schema_version,
            "hash_algorithm": "sha256",
            "scenario_id": self.scenario_id,
            "updated_at_utc": _rfc3339_utc(self.clock()),
            "entries": dict(sorted(entries.items())),
        }

    def _resolved_scenario_hash(self) -> str | None:
        path = self.scenario_root / "resolved_scenario.json"
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return str(value.get("scenario_hash")) if isinstance(value, Mapping) else None

    def _target(self, normalized: str) -> Path:
        target = (self.scenario_root / normalized).resolve()
        try:
            target.relative_to(self.scenario_root)
        except ValueError as exc:
            raise ArtifactRegistryError(
                f"artifact path escapes scenario root: {normalized}"
            ) from exc
        return target

    def _phase(self, phase: str, target: Path) -> None:
        if self.phase_hook is not None:
            self.phase_hook(phase, target)


def publish_campaign_manifest(
    campaign_root: Path,
    manifest: Mapping[str, object],
    *,
    registry: ArtifactRegistry | None = None,
) -> dict[str, object]:
    """Atomically publish the campaign manifest and detached SHA-256 sidecar."""

    active_registry = registry or ArtifactRegistry.load()
    root = campaign_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / "campaign_manifest.json"
    definition = active_registry.get("campaign_manifest")
    payload = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    _atomic_bytes(target, payload, lambda path: validate_artifact(path, definition))
    digest = file_sha256(target)
    sidecar = root / "campaign_manifest.sha256"
    sidecar_definition = active_registry.get("campaign_manifest_checksum")
    _atomic_bytes(
        sidecar,
        (digest + "\n").encode("ascii"),
        lambda path: validate_artifact(path, sidecar_definition),
    )
    return {"path": target.name, "bytes": target.stat().st_size, "sha256": digest}


def validate_campaign_manifest_pair(
    campaign_root: Path,
    *,
    registry: ArtifactRegistry | None = None,
) -> None:
    active_registry = registry or ArtifactRegistry.load()
    manifest_path = campaign_root / "campaign_manifest.json"
    sidecar_path = campaign_root / "campaign_manifest.sha256"
    validate_artifact(manifest_path, active_registry.get("campaign_manifest"))
    inspection = validate_artifact(
        sidecar_path, active_registry.get("campaign_manifest_checksum")
    )
    if (inspection.values or {}).get("sha256") != file_sha256(manifest_path):
        raise AtomicArtifactError("campaign manifest detached checksum mismatch")


def checksum_entry(path: Path, definition: ArtifactDefinition) -> dict[str, object]:
    return {
        "artifact_id": definition.artifact_id,
        "schema_version": definition.schema_version,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def find_temporary_artifacts(
    root: Path, registry: ArtifactRegistry
) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and is_temporary_artifact(path, registry)
        )
    )


def is_temporary_artifact(path: Path, registry: ArtifactRegistry) -> bool:
    return registry.temporary_file_marker in path.name


def _atomic_bytes(
    target: Path,
    payload: bytes,
    validator: Callable[[Path], object],
) -> None:
    temporary = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex}")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        validator(temporary)
        replace_file_with_retry(temporary, target)
        _fsync_directory(target.parent)
    finally:
        best_effort_unlink(temporary)


def replace_file_with_retry(source: Path, target: Path) -> None:
    """Retry only transient Windows sharing violations during atomic replacement."""

    for attempt in range(len(_FILE_OPERATION_RETRY_DELAYS_SEC) + 1):
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            if not _is_transient_windows_file_error(exc) or attempt >= len(
                _FILE_OPERATION_RETRY_DELAYS_SEC
            ):
                raise
            time.sleep(_FILE_OPERATION_RETRY_DELAYS_SEC[attempt])


def best_effort_unlink(path: Path) -> None:
    """Remove a temporary file without masking the publication's primary error."""

    for attempt in range(len(_FILE_OPERATION_RETRY_DELAYS_SEC) + 1):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError as exc:
            if not _is_transient_windows_file_error(exc) or attempt >= len(
                _FILE_OPERATION_RETRY_DELAYS_SEC
            ):
                return
            time.sleep(_FILE_OPERATION_RETRY_DELAYS_SEC[attempt])


def _is_transient_windows_file_error(error: OSError) -> bool:
    return os.name == "nt" and getattr(error, "winerror", None) in (
        _TRANSIENT_WINDOWS_FILE_ERROR_CODES
    )


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rfc3339_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise AtomicArtifactError("atomic artifact clock must return an aware datetime")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
