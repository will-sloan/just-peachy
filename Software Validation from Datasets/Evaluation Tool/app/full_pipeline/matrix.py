"""Resolve the locked 18-row matrix into runtime component identities."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

import yaml


@dataclass(frozen=True)
class PipelineSelection:
    pipeline_id: str
    protocol_version: str
    asr_alias: str
    diarization_alias: str
    identity_alias: str
    hybrid_label: str
    asr: Mapping[str, object]
    diarization: Mapping[str, object]
    diarization_embedding: Mapping[str, object]
    identity: Mapping[str, object]
    enrollment_policy: Mapping[str, object]
    hybrid_policy: Mapping[str, object]
    runtime_config_sha256: str
    pipeline_config_sha256: str
    matrix_row: Mapping[str, object]

    @property
    def frozen_hybrid_anchor(self) -> bool:
        return self.hybrid_label in {"H2", "H4", "H5"}


class FullPipelineMatrix:
    def __init__(self, matrix_path: Path, runtime_path: Path | None = None) -> None:
        self.matrix_path = Path(matrix_path).resolve()
        self.runtime_path = Path(runtime_path).resolve() if runtime_path else None
        self.matrix = self._load_yaml(self.matrix_path)
        self.runtime = self._load_yaml(self.runtime_path) if self.runtime_path else {}
        rows = self.matrix.get("pipelines", [])
        self._rows = {
            str(row["pipeline_id"]): row
            for row in rows
            if isinstance(row, Mapping) and row.get("pipeline_id")
        }
        if len(self._rows) != 18:
            raise ValueError(
                f"locked full-pipeline matrix must contain 18 rows, found {len(self._rows)}"
            )

    @staticmethod
    def _load_yaml(path: Path | None) -> dict[str, object]:
        if path is None or not path.is_file():
            raise FileNotFoundError(path)
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(value, dict):
            raise ValueError(f"YAML root must be a mapping: {path}")
        return value

    @property
    def pipeline_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._rows))

    def resolve(self, pipeline_id: str) -> PipelineSelection:
        row = self._rows.get(pipeline_id)
        if row is None:
            raise KeyError(f"unknown full-pipeline ID: {pipeline_id}")
        axes = self.matrix["axes"]
        policies = self.matrix["policies"]
        hybrid_labels = self.matrix["hybrid_labels"]
        asr_alias = str(row["asr"])
        diar_alias = str(row["anonymous_diarization"])
        identity_alias = str(row["identity"])
        hybrid_label = str(row["hybrid_label"])
        diarization = dict(axes["anonymous_diarization"][diar_alias])
        diarization_backend_id = str(diarization["embedding_backend_id"])
        diarization_embedding_matches = [
            dict(value)
            for value in axes["identity"].values()
            if isinstance(value, Mapping)
            and str(value.get("backend_id")) == diarization_backend_id
        ]
        if len(diarization_embedding_matches) != 1:
            raise ValueError(
                "locked diarization embedding axis is ambiguous for "
                f"{diarization_backend_id}: {len(diarization_embedding_matches)} matches"
            )
        runtime_hash = (
            hashlib.sha256(self.runtime_path.read_bytes()).hexdigest()
            if self.runtime_path is not None
            else hashlib.sha256(
                json.dumps(self.runtime, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
        )
        matrix_hash = hashlib.sha256(self.matrix_path.read_bytes()).hexdigest()
        pipeline_hash = hashlib.sha256(
            json.dumps(
                {
                    "matrix_sha256": matrix_hash,
                    "runtime_sha256": runtime_hash,
                    "pipeline": row,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return PipelineSelection(
            pipeline_id=pipeline_id,
            protocol_version=str(row["protocol_version"]),
            asr_alias=asr_alias,
            diarization_alias=diar_alias,
            identity_alias=identity_alias,
            hybrid_label=hybrid_label,
            asr=dict(axes["asr"][asr_alias]),
            diarization=diarization,
            diarization_embedding=diarization_embedding_matches[0],
            identity=dict(axes["identity"][identity_alias]),
            enrollment_policy=dict(policies["enrollment"][identity_alias]),
            hybrid_policy=dict(hybrid_labels[hybrid_label]),
            runtime_config_sha256=runtime_hash,
            pipeline_config_sha256=pipeline_hash,
            matrix_row=dict(row),
        )

    def status(self) -> dict[str, object]:
        return {
            "schema_version": "full-pipeline-runtime-status.v1",
            "matrix_path": str(self.matrix_path),
            "matrix_sha256": hashlib.sha256(self.matrix_path.read_bytes()).hexdigest(),
            "runtime_config_path": str(self.runtime_path)
            if self.runtime_path
            else None,
            "runtime_config_sha256": (
                hashlib.sha256(self.runtime_path.read_bytes()).hexdigest()
                if self.runtime_path and self.runtime_path.is_file()
                else None
            ),
            "pipeline_count": len(self._rows),
            "pipeline_ids": list(self.pipeline_ids),
        }
