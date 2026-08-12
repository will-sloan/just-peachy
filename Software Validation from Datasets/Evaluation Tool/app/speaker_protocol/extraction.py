"""Offline extraction bridge for qualified Stage 10 embedding backends."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import time
from typing import Mapping, Sequence

import numpy as np
import soundfile as sf
import yaml

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.speaker_embedding import build_speaker_embedding_from_config
from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext
from app.speaker_protocol.contracts import (
    TOOL_ROOT,
    SpeakerProtocolError,
    backend_identity,
    eligible_embedding_backends,
)
from app.speaker_protocol.manifests import MANIFEST_FILENAMES, read_protocol_rows


BASE_CONFIG = TOOL_ROOT / "configs" / "inference" / "live_mic_whisper_base.yaml"


def extract_clean_protocol_embeddings(
    manifest_root: Path,
    component_name: str,
    output_root: Path,
    *,
    item_ids: set[str] | None = None,
) -> dict[str, object]:
    """Extract only clean source rows; degraded rows require campaign augmentation."""

    if component_name not in eligible_embedding_backends(
        backend_ids={component_name}
    ):
        raise SpeakerProtocolError(f"backend is not qualified for Stage 10: {component_name}")
    rows = []
    for kind in ("enrollment", "calibration", "known_evaluation", "unknown_evaluation"):
        rows.extend(
            read_protocol_rows(manifest_root / MANIFEST_FILENAMES[kind], expected_kind=kind)
        )
    selected = [
        row
        for row in rows
        if row["protocol_condition"] == "clean"
        and (item_ids is None or str(row["item_id"]) in item_ids)
    ]
    if item_ids is not None:
        missing = item_ids - {str(row["item_id"]) for row in selected}
        if missing:
            raise SpeakerProtocolError(
                f"requested item IDs are absent or degraded-only: {sorted(missing)}"
            )
    if not selected:
        raise SpeakerProtocolError("no clean protocol rows were selected for extraction")
    return extract_rows(selected, component_name, output_root)


def extract_rows(
    rows: Sequence[Mapping[str, object]],
    component_name: str,
    output_root: Path,
) -> dict[str, object]:
    config = _embedding_config(component_name)
    adapter = build_speaker_embedding_from_config(config)
    if adapter is None:
        raise SpeakerProtocolError(f"embedding adapter did not resolve: {component_name}")
    item_ids: list[str] = []
    statuses: list[str] = []
    vectors: list[tuple[float, ...]] = []
    durations: list[float] = []
    timings: list[float] = []
    failures: list[dict[str, str]] = []
    dimension: int | None = None
    for row in sorted(rows, key=lambda value: str(value["item_id"])):
        if row["protocol_condition"] != "clean":
            raise SpeakerProtocolError(
                "direct extraction refuses degraded rows; use an approved augmented inference path"
            )
        item_id = str(row["item_id"])
        path = (TOOL_ROOT.parent / str(row["audio_path_project_relative"])).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"speaker protocol audio is missing: {path}")
        info = sf.info(path)
        duration = float(row["duration_sec"])
        segment = AudioSegment(
            audio_path=path,
            start_sec=float(row["start_sec"]),
            end_sec=float(row["end_sec"]),
            duration_sec=duration,
            sample_rate_hz=int(info.samplerate),
            channel_count=int(info.channels),
            is_mono=int(info.channels) == 1,
        )
        context = SpeakerEmbeddingContext(
            recording_id=str(row["source_recording_id"]),
            utt_id=item_id,
            source_audio_path=path,
            segment_start_sec=float(row["start_sec"]),
            segment_end_sec=float(row["end_sec"]),
            device="cpu",
            dtype="float32",
            run_config={
                "project_root": str(TOOL_ROOT.parent),
                "runtime": {
                    "device": "cpu",
                    "precision": "float32",
                    "sample_rate_hz": 16000,
                    "allow_model_downloads": False,
                },
            },
        )
        started = time.perf_counter()
        try:
            result = adapter.embed(segment, context)
            status = str(result.status)
            vector = tuple(float(value) for value in result.vector) if status == "ok" else ()
            if status == "ok":
                if dimension is None:
                    dimension = len(vector)
                elif len(vector) != dimension:
                    raise SpeakerProtocolError("embedding dimension changed during extraction")
            else:
                failures.append(
                    {"item_id": item_id, "status": status, "message": str(result.metadata)}
                )
        except Exception as exc:  # per-item failure isolation
            status = "failed"
            vector = ()
            failures.append(
                {"item_id": item_id, "status": status, "message": f"{type(exc).__name__}: {exc}"}
            )
        item_ids.append(item_id)
        statuses.append(status)
        vectors.append(vector)
        durations.append(duration)
        timings.append(time.perf_counter() - started)
    if dimension is None:
        raise SpeakerProtocolError("embedding backend produced no valid vector")
    matrix = np.zeros((len(vectors), dimension), dtype=np.float32)
    for index, vector in enumerate(vectors):
        if vector:
            matrix[index] = np.asarray(vector, dtype=np.float32)
    identity = backend_identity(component_name, dimension)
    destination = output_root.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    bundle_path = destination / "observations.npz"
    _write_npz(
        bundle_path,
        {
            "schema_version": np.asarray(["speaker-observation-bundle.v1"]),
            "item_ids": np.asarray(item_ids),
            "vectors": matrix,
            "statuses": np.asarray(statuses),
            "durations_sec": np.asarray(durations, dtype=np.float64),
            "extraction_sec": np.asarray(timings, dtype=np.float64),
            "backend_identity_hash": np.asarray([identity.identity_hash]),
        },
    )
    identity_path = destination / "backend_identity.json"
    _write_json(identity_path, identity.to_jsonable())
    _write_json(
        destination / "extraction_summary.json",
        {
            "schema_version": "speaker-extraction-summary.v1",
            "backend_identity_hash": identity.identity_hash,
            "expected_items": len(rows),
            "successful_items": statuses.count("ok"),
            "failed_items": len(rows) - statuses.count("ok"),
            "condition": "clean",
            "degraded_source_audio_misrepresented": False,
            "implicit_model_downloads_allowed": False,
            "failures": failures,
        },
    )
    return {
        "bundle_path": bundle_path,
        "identity_path": identity_path,
        "identity": identity,
        "expected_items": len(rows),
        "successful_items": statuses.count("ok"),
        "failures": failures,
    }


def load_backend_identity(path: Path):
    from app.speaker_protocol.contracts import BackendIdentity

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SpeakerProtocolError("backend identity JSON must be a mapping")
    return BackendIdentity.from_mapping(value)


def _embedding_config(component_name: str) -> PipelineConfig:
    entry = ComponentCatalog.load().get("speaker_embedding", component_name)
    source = TOOL_ROOT / entry.source_config_path
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    fragment = raw.get("component") if isinstance(raw, Mapping) else None
    if not isinstance(fragment, Mapping):
        raise SpeakerProtocolError(f"invalid embedding component config: {source}")
    component = deepcopy(dict(fragment))
    params = dict(component.get("params") or {})
    if bool(params.get("allow_model_downloads", False)):
        raise SpeakerProtocolError("Stage 10 prohibits implicit model downloads")
    params["allow_model_downloads"] = False
    if "device" in params:
        params["device"] = "cpu"
    if "provider" in params:
        params["provider"] = "cpu"
    component["params"] = params
    mapping = PipelineConfig.from_yaml_path(BASE_CONFIG).to_jsonable()
    mapping["config_name"] = f"stage10_{component_name}"
    mapping["profile"] = "speaker_protocol"
    mapping["runtime"].update(
        {
            "device": "cpu",
            "precision": "float32",
            "sample_rate_hz": 16000,
            "allow_model_downloads": False,
            "dry_run": False,
        }
    )
    for value in mapping["components"].values():
        value["enabled"] = False
    mapping["components"]["speaker_embedding"] = component
    return PipelineConfig.from_mapping(mapping)


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_npz(path: Path, arrays: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as handle:
            np.savez(handle, **{str(key): np.asarray(value) for key, value in arrays.items()})
        with np.load(temporary, allow_pickle=False):
            pass
        _replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace(source: Path, destination: Path) -> None:
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))
