"""Restart-safe segment embedding cache for hybrid attribution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Iterable, Mapping

import numpy as np
import soundfile as sf

from app.hybrid_speaker_attribution.contracts import HybridAttributionError, canonical_sha256, file_sha256
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.speaker_embedding import build_speaker_embedding_from_config
from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext
from app.speaker_protocol.contracts import backend_identity, eligible_embedding_backends
from app.speaker_protocol.extraction import _embedding_config


SCHEMA_VERSION = "hybrid-speaker-embedding-cache.v1"


def cache_identity(job_identity: str, backend_id: str, declared_backend_identity_hash: str) -> str:
    return canonical_sha256(
        {
            "job_identity": job_identity,
            "backend_id": backend_id,
            "declared_backend_identity_hash": declared_backend_identity_hash,
        }
    )


def embedding_job(
    *, job_id: str, audio_path: Path, audio_sha256: str, start_sec: float,
    end_sec: float, role: str, metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        "job_id": job_id,
        "audio_path": str(audio_path.resolve()),
        "audio_sha256": audio_sha256.upper(),
        "start_sec": float(start_sec),
        "end_sec": float(end_sec),
        "role": role,
        "metadata": dict(metadata or {}),
    }
    if payload["end_sec"] <= payload["start_sec"]:
        raise HybridAttributionError("embedding job has an invalid interval")
    payload["job_identity"] = canonical_sha256(
        {key: value for key, value in payload.items() if key not in {"audio_path", "metadata"}}
    )
    return payload


def extract_jobs(
    component_name: str,
    jobs: Iterable[Mapping[str, object]],
    cache_root: Path,
    progress_path: Path | None = None,
) -> dict[str, object]:
    """Extract missing jobs with one model load and atomically publish each item."""

    eligible = eligible_embedding_backends(backend_ids={component_name})
    if component_name not in eligible:
        raise HybridAttributionError(f"speaker backend is not qualified and available: {component_name}")
    rows = sorted((dict(row) for row in jobs), key=lambda row: str(row["job_id"]))
    declared_backend_identity_hash = canonical_sha256(eligible[component_name])
    for row in rows:
        row["cache_identity"] = cache_identity(
            str(row["job_identity"]), component_name, declared_backend_identity_hash
        )
    destination = cache_root.resolve() / component_name
    destination.mkdir(parents=True, exist_ok=True)
    reused = 0
    pending = []
    for row in rows:
        cached = destination / f"{row['cache_identity']}.json"
        try:
            load_cached(cached, expected_job_identity=str(row["job_identity"]), expected_cache_identity=str(row["cache_identity"]))
            reused += 1
        except Exception:
            pending.append(row)
    adapter = None
    dimension = None
    failures = []
    observed_audio_hashes: dict[Path, str] = {}
    completed_audio_sec = sum(float(row["end_sec"]) - float(row["start_sec"]) for row in rows if row not in pending)
    planned_audio_sec = sum(float(row["end_sec"]) - float(row["start_sec"]) for row in rows)
    if progress_path:
        _write_json(progress_path, {"schema_version": "hybrid-embedding-progress.v1", "backend_id": component_name, "status": "RUNNING", "completed_jobs": reused, "planned_jobs": len(rows), "completed_audio_sec": completed_audio_sec, "planned_audio_sec": planned_audio_sec, "current_job_id": None, "updated_at_epoch": time.time()})
    if pending:
        adapter = build_speaker_embedding_from_config(_embedding_config(component_name))
        if adapter is None:
            raise HybridAttributionError(f"speaker backend did not build: {component_name}")
    for pending_index, row in enumerate(pending, start=1):
        started = time.perf_counter()
        status, vector, error = "failed", (), None
        result = None
        try:
            path = Path(str(row["audio_path"]))
            if not path.is_file():
                raise FileNotFoundError(path)
            if path not in observed_audio_hashes:
                observed_audio_hashes[path] = file_sha256(path)
            observed_hash = observed_audio_hashes[path]
            if observed_hash != str(row["audio_sha256"]).upper():
                raise HybridAttributionError(f"source audio SHA-256 mismatch: {path}")
            info = sf.info(path)
            segment = AudioSegment(
                audio_path=path,
                start_sec=float(row["start_sec"]),
                end_sec=float(row["end_sec"]),
                duration_sec=float(row["end_sec"]) - float(row["start_sec"]),
                sample_rate_hz=int(info.samplerate),
                channel_count=int(info.channels),
                is_mono=int(info.channels) == 1,
            )
            context = SpeakerEmbeddingContext(
                recording_id=str(dict(row.get("metadata") or {}).get("recording_id") or row["job_id"]),
                utt_id=str(row["job_id"]),
                source_audio_path=path,
                segment_start_sec=float(row["start_sec"]),
                segment_end_sec=float(row["end_sec"]),
                device="cpu",
                dtype="float32",
            )
            result = adapter.embed(segment, context)  # type: ignore[union-attr]
            status = str(result.status)
            if status == "ok":
                raw = np.asarray(result.vector, dtype=np.float64)
                norm = float(np.linalg.norm(raw))
                if not np.isfinite(norm) or norm <= 0:
                    raise HybridAttributionError("backend returned a non-normalizable embedding")
                vector = tuple(float(value) for value in raw / norm)
                dimension = len(vector) if dimension is None else dimension
                if len(vector) != dimension:
                    raise HybridAttributionError("embedding dimension changed during extraction")
            else:
                error = str(result.metadata)
        except Exception as exc:  # isolate one bad segment without losing the rest
            status, vector, error = "failed", (), f"{type(exc).__name__}: {exc}"
            failures.append({"job_id": row["job_id"], "error": error})
        payload = {
            "schema_version": SCHEMA_VERSION,
            "job_id": row["job_id"],
            "job_identity": row["job_identity"],
            "cache_identity": row["cache_identity"],
            "backend_id": component_name,
            "declared_backend_identity_hash": declared_backend_identity_hash,
            "status": status,
            "vector": vector,
            "duration_sec": float(row["end_sec"]) - float(row["start_sec"]),
            "extraction_sec": time.perf_counter() - started,
            "backend_runtime": result.runtime.to_jsonable() if status == "ok" and result is not None and result.runtime is not None else None,
            "error": error,
            "role": row["role"],
            "metadata": row.get("metadata") or {},
        }
        _write_json(destination / f"{row['cache_identity']}.json", payload)
        completed_audio_sec += float(row["end_sec"]) - float(row["start_sec"])
        if progress_path and (pending_index == len(pending) or pending_index % 10 == 0):
            _write_json(progress_path, {"schema_version": "hybrid-embedding-progress.v1", "backend_id": component_name, "status": "RUNNING", "completed_jobs": reused + pending_index, "planned_jobs": len(rows), "completed_audio_sec": completed_audio_sec, "planned_audio_sec": planned_audio_sec, "current_job_id": row["job_id"], "failures": len(failures), "updated_at_epoch": time.time()})
    successful = sum(
        load_cached(destination / f"{row['cache_identity']}.json")["status"] == "ok"
        for row in rows
    )
    if successful:
        observed = next(
            len(load_cached(destination / f"{row['cache_identity']}.json")["vector"])
            for row in rows
            if load_cached(destination / f"{row['cache_identity']}.json")["status"] == "ok"
        )
        identity = backend_identity(component_name, observed).to_jsonable()
    else:
        identity = None
    summary = {
        "schema_version": "hybrid-speaker-embedding-extraction.v1",
        "backend_id": component_name,
        "backend_identity": identity,
        "jobs": len(rows),
        "successful": successful,
        "failed": len(rows) - successful,
        "reused": reused,
        "declared_backend_identity_hash": declared_backend_identity_hash,
        "cache_entries": [
            {
                "job_id": row["job_id"],
                "job_identity": row["job_identity"],
                "cache_identity": row["cache_identity"],
                "filename": f"{row['cache_identity']}.json",
            }
            for row in rows
        ],
        "implicit_model_downloads_allowed": False,
        "failures": failures,
    }
    _write_json(destination / "extraction_summary.json", summary)
    if progress_path:
        _write_json(progress_path, {"schema_version": "hybrid-embedding-progress.v1", "backend_id": component_name, "status": "COMPLETE", "completed_jobs": len(rows), "planned_jobs": len(rows), "completed_audio_sec": planned_audio_sec, "planned_audio_sec": planned_audio_sec, "current_job_id": None, "failures": len(failures), "updated_at_epoch": time.time()})
    return summary


def load_cached(path: Path, expected_job_identity: str | None = None, expected_cache_identity: str | None = None) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != SCHEMA_VERSION:
        raise HybridAttributionError("unsupported cached embedding schema")
    if expected_job_identity and value.get("job_identity") != expected_job_identity:
        raise HybridAttributionError("cached embedding job identity mismatch")
    if expected_cache_identity and value.get("cache_identity") != expected_cache_identity:
        raise HybridAttributionError("cached embedding/backend identity mismatch")
    vector = value.get("vector") or []
    if value.get("status") == "ok" and (not vector or not all(np.isfinite(float(item)) for item in vector)):
        raise HybridAttributionError("cached successful embedding is invalid")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    last_error: PermissionError | None = None
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(min(0.5, 0.01 * (attempt + 1)))
    if last_error is not None:
        raise last_error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract cached hybrid speaker embeddings")
    parser.add_argument("--backend", required=True)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--progress-path", type=Path, default=None)
    args = parser.parse_args(argv)
    jobs = [json.loads(line) for line in args.jobs.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(json.dumps(extract_jobs(args.backend, jobs, args.cache_root, args.progress_path), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
