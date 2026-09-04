"""Atomic runtime artifacts and checksum-bound portable references."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping
import uuid


class RuntimeArtifactWriter:
    """Write one session below a declared run root without absolute-path leakage."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._references: dict[str, dict[str, object]] = {}

    def write_json(
        self,
        logical_path: str,
        value: object,
        *,
        schema_version: str,
        privacy: str = "internal",
    ) -> dict[str, object]:
        payload = (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        return self._write(
            logical_path,
            payload,
            schema_version=schema_version,
            media_type="application/json",
            privacy=privacy,
        )

    def write_jsonl(
        self,
        logical_path: str,
        rows: Iterable[Mapping[str, object]],
        *,
        schema_version: str,
        privacy: str = "internal",
    ) -> dict[str, object]:
        payload = "".join(
            json.dumps(
                dict(row), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            + "\n"
            for row in rows
        ).encode("utf-8")
        return self._write(
            logical_path,
            payload,
            schema_version=schema_version,
            media_type="application/x-ndjson",
            privacy=privacy,
        )

    def reference(self, logical_path: str) -> Mapping[str, object]:
        return dict(self._references[logical_path])

    def register_existing(
        self,
        logical_path: str,
        *,
        schema_version: str,
        media_type: str,
        privacy: str = "internal",
    ) -> dict[str, object]:
        """Checksum an artifact already written incrementally below this root."""

        normalized = self._portable(logical_path)
        path = (self.root / normalized).resolve()
        if self.root not in path.parents or not path.is_file():
            raise FileNotFoundError(path)
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        reference: dict[str, object] = {
            "artifact_id": f"artifact_{digest[:24]}",
            "logical_path": normalized,
            "resolver_alias": "FULL_PIPELINE_RUN_ROOT",
            "sha256": digest,
            "byte_count": len(payload),
            "artifact_schema_version": schema_version,
            "media_type": media_type,
            "privacy_classification": privacy,
        }
        self._references[normalized] = reference
        return dict(reference)

    @property
    def references(self) -> tuple[Mapping[str, object], ...]:
        return tuple(dict(self._references[key]) for key in sorted(self._references))

    def checksum_manifest(
        self, logical_path: str = "manifests/checksums.json"
    ) -> dict[str, object]:
        rows = [
            {
                "logical_path": key,
                "sha256": value["sha256"],
                "byte_count": value["byte_count"],
                "artifact_schema_version": value["artifact_schema_version"],
                "privacy_classification": value["privacy_classification"],
            }
            for key, value in sorted(self._references.items())
        ]
        return self.write_json(
            logical_path,
            {"schema_version": "full-pipeline-checksum-manifest.v1", "artifacts": rows},
            schema_version="full-pipeline-checksum-manifest.v1",
            privacy="internal",
        )

    def _write(
        self,
        logical_path: str,
        payload: bytes,
        *,
        schema_version: str,
        media_type: str,
        privacy: str,
    ) -> dict[str, object]:
        normalized = self._portable(logical_path)
        path = (self.root / normalized).resolve()
        if self.root not in path.parents:
            raise ValueError("artifact path escapes the runtime root")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
        digest = hashlib.sha256(payload).hexdigest()
        reference: dict[str, object] = {
            "artifact_id": f"artifact_{digest[:24]}",
            "logical_path": normalized,
            "resolver_alias": "FULL_PIPELINE_RUN_ROOT",
            "sha256": digest,
            "byte_count": len(payload),
            "artifact_schema_version": schema_version,
            "media_type": media_type,
            "privacy_classification": privacy,
        }
        self._references[normalized] = reference
        return dict(reference)

    @staticmethod
    def _portable(value: str) -> str:
        normalized = str(value).replace("\\", "/").strip("/")
        path = Path(normalized)
        if (
            not normalized
            or path.is_absolute()
            or ".." in path.parts
            or ":" in normalized
        ):
            raise ValueError(f"logical artifact path is not portable: {value!r}")
        return normalized
