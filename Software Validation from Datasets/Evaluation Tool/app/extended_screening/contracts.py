"""Stage 9 qualification, eligibility, and protocol contracts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Mapping

import yaml

from app.benchmark_contracts.manifest_io import file_sha256
from app.inference_pipeline.catalog import ComponentCatalog
from app.utils.json_utils import read_json


TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL_PATH = (
    TOOL_ROOT / "configs" / "automated_evaluation" / "extended_screening.v1.yaml"
)
DEFAULT_REGISTRY_PATH = (
    TOOL_ROOT
    / "configs"
    / "automated_evaluation"
    / "extended_qualification_registry.v1.yaml"
)
ELIGIBLE_STATUSES = frozenset({"qualified", "qualified_with_warnings"})


def load_protocol(path: Path = DEFAULT_PROTOCOL_PATH) -> dict[str, object]:
    payload = _yaml(path)
    if payload.get("schema_version") != "extended-screening-protocol.v1":
        raise ValueError("unsupported Stage 9 screening protocol")
    if payload.get("seed") != 3800:
        raise ValueError("Stage 9 screening seed must remain 3800")
    if payload.get("reference_asr") != "whisper_base":
        raise ValueError("Stage 9 reference ASR must be Whisper Base")
    return payload


def load_qualification_registry(
    path: Path = DEFAULT_REGISTRY_PATH,
    *,
    verify_summary: bool = True,
) -> dict[str, object]:
    payload = _yaml(path)
    if payload.get("schema_version") != "extended-qualification-registry.v1":
        raise ValueError("unsupported Stage 9 qualification registry")
    rows = payload.get("backends")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Stage 9 qualification registry has no backends")
    identifiers = [str(row.get("backend_id")) for row in rows if isinstance(row, Mapping)]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Stage 9 qualification registry has duplicate backend IDs")
    if verify_summary:
        _verify_registry_against_summary(payload, path)
    return payload


def eligible_backend_rows(
    registry: Mapping[str, object],
) -> list[dict[str, object]]:
    rows = registry.get("backends")
    if not isinstance(rows, list):
        raise ValueError("qualification registry backends must be a list")
    return [
        deepcopy(dict(row))
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("status")) in ELIGIBLE_STATUSES
        and str(row.get("disposition")) in {"screen", "composition_only"}
    ]


def validate_catalog_qualification_alignment(
    registry: Mapping[str, object],
    catalog: ComponentCatalog,
) -> None:
    for row in eligible_backend_rows(registry):
        entry = catalog.get(str(row["catalog_family"]), str(row["catalog_name"]))
        if entry.qualification_backend_id != row["backend_id"]:
            raise ValueError(
                f"catalog qualification ID mismatch for {row['backend_id']}"
            )
        if entry.qualification_status != row["status"]:
            raise ValueError(
                f"catalog qualification status mismatch for {row['backend_id']}"
            )
        if str(row["profile"]) not in entry.environment_profiles:
            raise ValueError(
                f"catalog environment mismatch for {row['backend_id']}"
            )


def _verify_registry_against_summary(
    registry: Mapping[str, object], registry_path: Path
) -> None:
    source = registry.get("source_summary")
    if not isinstance(source, Mapping):
        raise ValueError("qualification registry source_summary is required")
    summary_path = TOOL_ROOT / str(source["path"])
    if not summary_path.is_file():
        raise FileNotFoundError(f"Stage 8 qualification summary is missing: {summary_path}")
    observed_hash = file_sha256(summary_path).lower()
    if observed_hash != str(source.get("sha256", "")).lower():
        raise ValueError(
            "Stage 8 qualification summary hash differs from the released Stage 9 registry"
        )
    summary = read_json(summary_path)
    if summary.get("schema_version") != source.get("schema_version"):
        raise ValueError("Stage 8 qualification summary schema mismatch")
    observed = {
        str(row["backend_id"]): (str(row["status"]), str(row["profile"]))
        for row in summary.get("results", [])
        if isinstance(row, Mapping)
    }
    declared = {
        str(row["backend_id"]): (str(row["status"]), str(row["profile"]))
        for row in registry["backends"]
        if isinstance(row, Mapping)
    }
    if observed != declared:
        raise ValueError(
            f"Stage 9 registry does not match Stage 8 evidence: {registry_path}"
        )


def _yaml(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return {str(key): value for key, value in payload.items()}
