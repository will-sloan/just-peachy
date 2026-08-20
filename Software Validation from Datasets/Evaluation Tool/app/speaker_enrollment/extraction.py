"""Restart-safe per-slice embedding cache for the enrollment-duration study."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Mapping, Sequence

import numpy as np
import soundfile as sf

from app.benchmark_contracts.canonical import canonical_sha256
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.speaker_embedding import build_speaker_embedding_from_config
from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext
from app.speaker_protocol.contracts import BackendIdentity, backend_identity, normalize_vector
from app.speaker_protocol.extraction import _embedding_config
from app.speaker_enrollment.protocol import (
    SpeakerEnrollmentError,
    load_protocol_tables,
)
from app.utils.paths import resolve_data_path_from_logical


CACHE_SCHEMA_VERSION = "speaker-enrollment-embedding-cache.v1"
ITEM_SCHEMA_VERSION = "speaker-enrollment-cached-embedding.v1"


def cache_item_identity(row: Mapping[str, str], runtime_cache_identity: str) -> str:
    """Bind one cached vector to its backend, source bytes, crop, and policy."""

    return canonical_sha256(
        {
            "schema_version": ITEM_SCHEMA_VERSION,
            "runtime_cache_identity": runtime_cache_identity,
            "slice_id": row["slice_id"],
            "parent_audio_sha256": row["parent_audio_sha256"],
            "start_sec": float(row["start_sec"]),
            "end_sec": float(row["end_sec"]),
            "duration_policy_version": row["duration_policy_version"],
        }
    )


def extract_slice_cache(
    protocol_root: Path,
    component_name: str,
    cache_root: Path,
    required_slice_ids: set[str],
) -> dict[str, object]:
    tables = load_protocol_tables(protocol_root)
    by_id = {row["slice_id"]: row for row in tables["audio_slices"]}
    missing = sorted(required_slice_ids - set(by_id))
    if missing:
        raise SpeakerEnrollmentError(f"requested slices are absent from the protocol: {missing[:5]}")
    root = cache_root.resolve()
    items_root = root / "items"
    items_root.mkdir(parents=True, exist_ok=True)
    identity_path = root / "backend_identity.json"
    existing_identity = _load_identity(identity_path) if identity_path.is_file() else None
    runtime_key = _runtime_cache_identity(protocol_root, component_name)
    reused = 0
    extracted = 0
    failed = 0
    dimension = existing_identity.embedding_dimension if existing_identity else None
    pending: list[dict[str, str]] = []
    for slice_id in sorted(required_slice_ids):
        row = by_id[slice_id]
        path = items_root / f"{slice_id}.npz"
        if _valid_item(path, row, component_name, runtime_key, dimension):
            print(f"[REUSE EMBEDDING] {component_name} {slice_id}")
            reused += 1
        else:
            if path.exists():
                quarantine = path.with_name(f"{path.name}.invalid-{int(time.time())}")
                os.replace(path, quarantine)
            pending.append(row)
    adapter = None
    if pending:
        adapter = build_speaker_embedding_from_config(_embedding_config(component_name))
        if adapter is None:
            raise SpeakerEnrollmentError(f"embedding adapter did not resolve: {component_name}")
    statuses: list[tuple[float, str]] = []
    for row in pending:
        slice_id = row["slice_id"]
        print(f"[EXTRACT] {component_name} {slice_id}")
        source = resolve_data_path_from_logical(row["audio_path_project_relative"]).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"speaker enrollment source audio is missing: {source}")
        info = sf.info(source)
        start = float(row["start_sec"])
        end = float(row["end_sec"])
        duration = float(row["duration_sec"])
        segment = AudioSegment(
            audio_path=source,
            start_sec=start,
            end_sec=end,
            duration_sec=duration,
            sample_rate_hz=int(info.samplerate),
            channel_count=int(info.channels),
            is_mono=int(info.channels) == 1,
        )
        context = SpeakerEmbeddingContext(
            recording_id=row["source_recording_id"],
            utt_id=slice_id,
            source_audio_path=source,
            segment_start_sec=start,
            segment_end_sec=end,
            device="cpu",
            dtype="float32",
            run_config={
                "project_root": str(Path(__file__).resolve().parents[3]),
                "runtime": {
                    "device": "cpu",
                    "precision": "float32",
                    "sample_rate_hz": 16000,
                    "allow_model_downloads": False,
                },
            },
        )
        started = time.perf_counter()
        error = ""
        try:
            result = adapter.embed(segment, context)  # type: ignore[union-attr]
            status = str(result.status)
            vector = tuple(float(value) for value in result.vector) if status == "ok" else ()
            if status == "ok":
                vector = normalize_vector(vector)
                if dimension is None:
                    dimension = len(vector)
                elif len(vector) != dimension:
                    raise SpeakerEnrollmentError("embedding dimension changed during extraction")
            else:
                error = json.dumps(dict(result.metadata), sort_keys=True, default=str)
        except Exception as exc:  # isolate one scientific observation failure
            status = "failed"
            vector = ()
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        statuses.append((duration, status))
        if status != "ok":
            failed += 1
        extracted += 1
        _write_item(
            items_root / f"{slice_id}.npz",
            row,
            component_name,
            runtime_key,
            status,
            vector,
            elapsed,
            error,
        )
    if dimension is None:
        raise SpeakerEnrollmentError("backend produced no valid embedding in this cache")
    identity = backend_identity(component_name, dimension)
    if existing_identity is not None and existing_identity.identity_hash != identity.identity_hash:
        raise SpeakerEnrollmentError("backend identity changed inside an existing embedding cache")
    _write_json(identity_path, identity.to_jsonable())
    summary = _cache_summary(protocol_root, component_name, runtime_key, required_slice_ids, root, identity)
    summary.update(
        {
            "reused_items_this_call": reused,
            "extracted_items_this_call": extracted,
            "failed_items_this_call": failed,
            "minimum_technically_accepted_duration_sec_observed": min(
                (duration for duration, status in statuses if status == "ok"), default=None
            ),
            "maximum_technically_rejected_duration_sec_observed": max(
                (duration for duration, status in statuses if status == "too_short"), default=None
            ),
        }
    )
    _write_json(root / "cache_summary.json", summary)
    return summary


def validate_embedding_cache(
    protocol_root: Path,
    component_name: str,
    cache_root: Path,
    required_slice_ids: set[str],
) -> dict[str, object]:
    root = cache_root.resolve()
    identity = _load_identity(root / "backend_identity.json")
    if identity.backend_id != component_name:
        raise SpeakerEnrollmentError("embedding cache belongs to another backend")
    runtime_key = _runtime_cache_identity(protocol_root, component_name)
    rows = {row["slice_id"]: row for row in load_protocol_tables(protocol_root)["audio_slices"]}
    missing = []
    invalid = []
    statuses: dict[str, int] = {}
    for slice_id in sorted(required_slice_ids):
        if slice_id not in rows:
            invalid.append(slice_id)
            continue
        path = root / "items" / f"{slice_id}.npz"
        if not path.is_file():
            missing.append(slice_id)
            continue
        if not _valid_item(path, rows[slice_id], component_name, runtime_key, identity.embedding_dimension):
            invalid.append(slice_id)
            continue
        value = _read_item(path)
        statuses[value["status"]] = statuses.get(value["status"], 0) + 1
    if missing or invalid:
        raise SpeakerEnrollmentError(
            f"embedding cache incomplete: missing={len(missing)} invalid={len(invalid)}"
        )
    return {
        "schema_version": "speaker-enrollment-cache-validation.v1",
        "backend_id": component_name,
        "backend_identity_hash": identity.identity_hash,
        "required_items": len(required_slice_ids),
        "statuses": statuses,
        "valid": True,
    }


def load_cached_embeddings(
    cache_root: Path,
    slice_ids: set[str],
) -> tuple[BackendIdentity, dict[str, dict[str, object]]]:
    root = cache_root.resolve()
    identity = _load_identity(root / "backend_identity.json")
    result = {}
    for slice_id in sorted(slice_ids):
        path = root / "items" / f"{slice_id}.npz"
        if not path.is_file():
            raise SpeakerEnrollmentError(f"cached embedding is missing: {slice_id}")
        result[slice_id] = _read_item(path)
    return identity, result


def _runtime_cache_identity(protocol_root: Path, component_name: str) -> str:
    from app.speaker_protocol.contracts import eligible_embedding_backends

    eligible = eligible_embedding_backends(backend_ids={component_name})
    if component_name not in eligible:
        raise SpeakerEnrollmentError(f"backend is not qualified and locally available: {component_name}")
    summary = json.loads((protocol_root / "protocol_summary.json").read_text(encoding="utf-8"))
    config_hash = _sha256(protocol_root / "selection_config.yaml")
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "extractor_code_identity": _git_sha(),
        "protocol_id": summary["protocol_id"],
        "protocol_config_sha256": config_hash,
        "backend": eligible[component_name],
        "preprocessing": {"sample_rate_hz": 16000, "channels": 1, "dtype": "float32"},
    }
    return canonical_sha256(payload)


def _write_item(
    path: Path,
    row: Mapping[str, str],
    component_name: str,
    runtime_key: str,
    status: str,
    vector: Sequence[float],
    extraction_sec: float,
    error: str,
) -> None:
    metadata = {
        "schema_version": ITEM_SCHEMA_VERSION,
        "slice_id": row["slice_id"],
        "backend_id": component_name,
        "runtime_cache_identity": runtime_key,
        "cache_item_identity": cache_item_identity(row, runtime_key),
        "parent_audio_sha256": row["parent_audio_sha256"],
        "start_sec": float(row["start_sec"]),
        "end_sec": float(row["end_sec"]),
        "duration_policy_version": row["duration_policy_version"],
        "status": status,
        "duration_sec": float(row["duration_sec"]),
        "extraction_sec": float(extraction_sec),
        "error": error,
    }
    _write_npz(
        path,
        {
            "metadata_json": np.asarray([json.dumps(metadata, sort_keys=True)]),
            "vector": np.asarray(vector, dtype=np.float32),
        },
    )


def _valid_item(
    path: Path,
    row: Mapping[str, str],
    component_name: str,
    runtime_key: str,
    dimension: int | None,
) -> bool:
    try:
        value = _read_item(path)
        if value["schema_version"] != ITEM_SCHEMA_VERSION:
            return False
        if value["slice_id"] != row["slice_id"] or value["backend_id"] != component_name:
            return False
        if value["runtime_cache_identity"] != runtime_key:
            return False
        if value.get("cache_item_identity") != cache_item_identity(row, runtime_key):
            return False
        if value["parent_audio_sha256"].upper() != row["parent_audio_sha256"].upper():
            return False
        if not math.isclose(float(value["start_sec"]), float(row["start_sec"]), abs_tol=1e-6):
            return False
        if not math.isclose(float(value["end_sec"]), float(row["end_sec"]), abs_tol=1e-6):
            return False
        vector = value["vector"]
        if value["status"] == "ok":
            return bool(vector) and (dimension is None or len(vector) == dimension) and all(math.isfinite(float(item)) for item in vector)
        return not vector and value["status"] in {"too_short", "failed", "invalid", "missing"}
    except Exception:
        return False


def _read_item(path: Path) -> dict[str, object]:
    with np.load(path, allow_pickle=False) as bundle:
        metadata = json.loads(str(bundle["metadata_json"][0]))
        vector = tuple(float(value) for value in bundle["vector"].tolist())
    metadata["vector"] = vector
    return metadata


def _load_identity(path: Path) -> BackendIdentity:
    value = json.loads(path.read_text(encoding="utf-8"))
    return BackendIdentity.from_mapping(value)


def _cache_summary(
    protocol_root: Path,
    component_name: str,
    runtime_key: str,
    required: set[str],
    root: Path,
    identity: BackendIdentity,
) -> dict[str, object]:
    statuses: dict[str, int] = {}
    durations: dict[str, list[float]] = {}
    total_seconds = 0.0
    for slice_id in required:
        value = _read_item(root / "items" / f"{slice_id}.npz")
        status = str(value["status"])
        statuses[status] = statuses.get(status, 0) + 1
        durations.setdefault(status, []).append(float(value["duration_sec"]))
        total_seconds += float(value["extraction_sec"])
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "protocol_id": json.loads((protocol_root / "protocol_summary.json").read_text(encoding="utf-8"))["protocol_id"],
        "backend_id": component_name,
        "backend_identity_hash": identity.identity_hash,
        "runtime_cache_identity": runtime_key,
        "cached_items_in_requested_scope": len(required),
        "statuses": statuses,
        "total_extraction_sec_in_requested_scope": total_seconds,
        "minimum_ok_duration_sec": min(durations.get("ok", []), default=None),
        "maximum_too_short_duration_sec": max(durations.get("too_short", []), default=None),
        "implicit_model_downloads_allowed": False,
        "invalid_audio_padded": False,
    }


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        return "UNKNOWN"


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _write_npz(path: Path, arrays: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as handle:
            np.savez(handle, **{key: np.asarray(value) for key, value in arrays.items()})
        with np.load(temporary, allow_pickle=False):
            pass
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
