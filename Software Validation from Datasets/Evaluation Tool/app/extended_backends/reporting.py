"""Consolidate isolated Stage 8 qualification evidence into one portable index."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from app.extended_backends.contracts import validate_qualification_payload
from app.extended_backends.registry import TOOL_ROOT, load_backend_catalog


DEFAULT_RESULT_ROOT = TOOL_ROOT / "runs" / "extended_backend_qualification"
PROFILE_NAMES = (
    "extended-local",
    "onnx",
    "wenet",
    "wespeaker",
    "credential-diarization",
    "nemo-linux-cuda",
)


def consolidate_qualification_results(
    *,
    result_root: Path = DEFAULT_RESULT_ROOT,
    output_path: Path | None = None,
    profile_names: Sequence[str] = PROFILE_NAMES,
    expected_backend_ids: set[str] | None = None,
) -> dict[str, object]:
    """Validate and index every isolated profile result without rerunning models."""

    expected = expected_backend_ids or {
        str(item["id"])
        for item in load_backend_catalog()["backends"]
        if isinstance(item, Mapping)
    }
    artifacts: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    for profile in profile_names:
        path = result_root / f"{profile}.json"
        payload = _read_json(path)
        validate_qualification_payload(payload)
        if payload.get("profile") != profile:
            raise ValueError(
                f"qualification profile mismatch in {path}: {payload.get('profile')!r}"
            )
        artifacts.append(
            {
                "profile": profile,
                "path": _portable_result_path(path),
                "sha256": _sha256(path),
                "generated_at": payload["generated_at"],
                "environment": payload["environment"],
            }
        )
        results.extend(dict(item) for item in payload["results"])

    identifiers = [str(item["backend_id"]) for item in results]
    duplicates = sorted(
        identifier for identifier, count in Counter(identifiers).items() if count > 1
    )
    if duplicates:
        raise ValueError("duplicate backend qualification results: " + ", ".join(duplicates))
    observed = set(identifiers)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if missing or unexpected:
        raise ValueError(
            f"backend result coverage mismatch; missing={missing}, unexpected={unexpected}"
        )

    status_counts = Counter(str(item["status"]) for item in results)
    qualified_count = status_counts["qualified"] + status_counts[
        "qualified_with_warnings"
    ]
    payload: dict[str, object] = {
        "schema_version": "extended-backend-qualification-summary.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_profile_artifacts": artifacts,
        "summary": {
            "total": len(results),
            "qualified_real_output": qualified_count,
            "not_qualified": len(results) - qualified_count,
            "status_counts": dict(sorted(status_counts.items())),
            "coverage_complete": True,
        },
        "results": sorted(results, key=lambda item: str(item["backend_id"])),
        "core_cuda_prerequisite": _optional_artifact(
            result_root / "core-cuda.json", expected_schema="core-cuda-qualification.v1"
        ),
        "model_asset_inventory": _optional_artifact(
            result_root / "model_asset_inventory.json",
            expected_schema="observed-model-asset-registry.v1",
        ),
        "secret_audit": {
            "values_serialized": False,
            "credential_presence_only": True,
        },
    }
    _assert_secret_free(payload)
    destination = output_path or result_root / "qualification_summary.json"
    _atomic_write_json(destination, payload)
    _atomic_write_text(
        destination.with_suffix(destination.suffix + ".sha256"),
        f"{_sha256(destination)}  {destination.name}\n",
    )
    return payload


def _optional_artifact(path: Path, *, expected_schema: str) -> dict[str, object]:
    if not path.is_file():
        return {
            "present": False,
            "path": _portable_result_path(path),
            "expected_schema": expected_schema,
        }
    payload = _read_json(path)
    if payload.get("schema_version") != expected_schema:
        raise ValueError(f"unexpected schema in {path}: {payload.get('schema_version')!r}")
    return {
        "present": True,
        "path": _portable_result_path(path),
        "sha256": _sha256(path),
        "schema_version": expected_schema,
        "generated_at": payload.get("generated_at"),
        "summary": payload.get("summary"),
        "environment": payload.get("environment"),
    }


def _portable_result_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(TOOL_ROOT.resolve()).as_posix()
    except ValueError:
        return f"<result-root>/{path.name}"


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"missing Stage 8 qualification artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"qualification artifact root must be an object: {path}")
    return payload


def _assert_secret_free(payload: Mapping[str, object]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for name in ("PYANNOTE_AUTH_TOKEN", "HF_TOKEN", "PICOVOICE_ACCESS_KEY"):
        value = os.environ.get(name)
        if value and value in serialized:
            raise ValueError(f"qualification summary would expose {name}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)
