"""Repeated real qualification for the explicitly scoped Stage 7 components."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import time
from typing import Mapping

import soundfile as sf
import torch

from app.core_screening.metrics import analyze_embedding_results
from app.core_screening.plan import DEFAULT_PIPELINE_PATH, candidate_component_overrides
from app.inference_pipeline.audio_io import load_audio
from app.inference_pipeline.catalog import ComponentCatalog, ComponentCatalogEntry
from app.inference_pipeline.contracts import AudioSegment, EvaluationRecord
from app.inference_pipeline.enrollment import (
    EnrollmentDatabase,
    add_enrollment_exemplar,
)
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.resolver import ResolvedPipeline, resolve_pipeline
from app.inference_pipeline.segmentation import build_segmenter_from_config
from app.inference_pipeline.speaker_embedding import (
    SpeakerEmbeddingContext,
    build_speaker_embedding_from_config,
)
from app.inference_pipeline.speaker_matching import build_speaker_matcher_from_config
from app.inference_pipeline.vad import build_vad_from_config


QUALIFICATION_SCHEMA_VERSION = "core-component-qualification.v1"
QUALIFICATION_RESULT_SCHEMA_VERSION = "core-component-qualification-result.v1"


def qualify_core_components(
    audio_path: Path,
    *,
    project_root: Path,
    repetitions: int = 2,
    degraded_audio_path: Path | None = None,
    selected_pipeline_path: Path = DEFAULT_PIPELINE_PATH,
    reference_asr: str = "whisper_base",
    output_path: Path | None = None,
) -> dict[str, object]:
    """Qualify only the Stage 7 core stack using local assets and no downloads."""

    if repetitions < 2:
        raise ValueError("Stage 7 core qualification requires at least two repetitions")
    if reference_asr not in {"whisper_tiny", "whisper_base", "whisper_small"}:
        raise ValueError(
            "reference_asr must be whisper_tiny, whisper_base, or whisper_small"
        )
    audio = audio_path.resolve()
    if not audio.is_file():
        raise FileNotFoundError(audio)
    degraded = degraded_audio_path.resolve() if degraded_audio_path else None
    if degraded is not None and not degraded.is_file():
        raise FileNotFoundError(degraded)
    duration = _audio_duration(audio)
    record = _record(audio, duration)
    run_config = {
        "project_root": str(project_root.resolve()),
        "runtime": {"sample_rate_hz": 16000, "device": "cpu", "dtype": "float32"},
    }
    catalog = ComponentCatalog.load()
    loaded_audio = load_audio(record, run_config)
    base_resolution = _candidate_resolution(
        "full_record", reference_asr, selected_pipeline_path, catalog
    )

    results: list[dict[str, object]] = []
    results.append(
        _run_qualification(
            "segmentation:full_record",
            "segmentation",
            "full_record",
            repetitions,
            catalog.get("segmentation", "no_op_segmentation"),
            lambda: _qualify_full_record(
                base_resolution, record, run_config, repetitions
            ),
        )
    )
    vad_regions: dict[str, list[object]] = {}
    for component_name, strategy in (
        ("energy_vad", "energy_observe"),
        ("silero_vad", "silero_observe"),
    ):
        resolution = _candidate_resolution(
            strategy, reference_asr, selected_pipeline_path, catalog
        )

        def vad_operation(
            resolved: ResolvedPipeline = resolution,
            name: str = component_name,
        ) -> dict[str, object]:
            details, regions = _qualify_vad(
                resolved, loaded_audio, repetitions=repetitions
            )
            vad_regions[name] = list(regions)
            return details

        results.append(
            _run_qualification(
                f"vad:{component_name}",
                "vad",
                component_name,
                repetitions,
                catalog.get("vad", component_name),
                vad_operation,
            )
        )

    chunk_resolution = _candidate_resolution(
        "energy_chunks", reference_asr, selected_pipeline_path, catalog
    )
    results.append(
        _run_qualification(
            "segmentation:vad_chunks",
            "segmentation",
            "vad_chunks",
            repetitions,
            catalog.get("segmentation", "vad_chunks"),
            lambda: _qualify_chunker(
                chunk_resolution,
                record,
                loaded_audio,
                vad_regions,
                repetitions=repetitions,
            ),
        )
    )

    for asr in ("whisper_tiny", "whisper_base", "whisper_small"):
        resolution = _candidate_resolution(
            "full_record", asr, selected_pipeline_path, catalog
        )
        results.append(
            _run_qualification(
                f"asr:{asr}",
                "asr",
                asr,
                repetitions,
                catalog.get("asr", asr),
                lambda resolved=resolution: _qualify_asr(
                    resolved,
                    record,
                    run_config,
                    repetitions=repetitions,
                ),
            )
        )

    embedding_resolution = resolve_pipeline(
        selected_pipeline_path,
        component_overrides={"speaker_embedding": "speechbrain_ecapa"},
        catalog=catalog,
    )
    embedding_cache: dict[str, object] = {}

    def embedding_operation() -> dict[str, object]:
        details, embedding = _qualify_embedding(
            embedding_resolution,
            record,
            run_config,
            repetitions=repetitions,
            degraded_audio=degraded,
        )
        embedding_cache["embedding"] = embedding
        return details

    results.append(
        _run_qualification(
            "speaker_embedding:speechbrain_ecapa",
            "speaker_embedding",
            "speechbrain_ecapa",
            repetitions,
            catalog.get("speaker_embedding", "speechbrain_ecapa"),
            embedding_operation,
        )
    )
    matcher_resolution = resolve_pipeline(
        selected_pipeline_path,
        component_overrides={
            "speaker_embedding": "speechbrain_ecapa",
            "speaker_matching": "cosine_threshold",
        },
        catalog=catalog,
    )
    results.append(
        _run_qualification(
            "speaker_matching:cosine_threshold_contract",
            "speaker_matching",
            "cosine_threshold",
            repetitions,
            catalog.get("speaker_matching", "cosine_threshold"),
            lambda: _qualify_matcher(
                matcher_resolution,
                record,
                run_config,
                embedding_cache.get("embedding"),
                repetitions=repetitions,
            ),
        )
    )

    statuses = {
        status: sum(row["status"] == status for row in results)
        for status in (
            "qualified",
            "unavailable",
            "failed",
        )
    }
    payload: dict[str, object] = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "scope": "stage7_core_only",
        "audio": {
            "path": _portable_path(audio, project_root),
            "sha256": _sha256(audio),
            "duration_sec": duration,
        },
        "degraded_audio": (
            {
                "path": _portable_path(degraded, project_root),
                "sha256": _sha256(degraded),
            }
            if degraded is not None
            else None
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
            "dtype": "float32",
        },
        "policy": {
            "repetitions": repetitions,
            "implicit_model_downloads_prohibited": True,
            "reference_asr": reference_asr,
            "whisper_sizes": ["tiny", "base", "small"],
            "whisper_large_excluded": True,
            "speaker_matching_scope": "contract_and_composition_only",
        },
        "summary": {
            "total": len(results),
            **statuses,
            "all_available_core_qualified": statuses["failed"] == 0,
        },
        "results": results,
    }
    if output_path is not None:
        _atomic_write_json(output_path.resolve(), payload)
    return payload


def _qualify_full_record(
    resolution: ResolvedPipeline,
    record: Mapping[str, object],
    run_config: Mapping[str, object],
    repetitions: int,
) -> dict[str, object]:
    runner = PipelineRunner.from_config(resolution.pipeline_config)
    outputs = [runner.predict(record, run_config) for _ in range(repetitions)]
    _validate_outputs(outputs, record)
    segment_counts = [
        len((output.diagnostics or {}).get("segments") or []) for output in outputs
    ]
    if any(value != 1 for value in segment_counts):
        raise RuntimeError("full-record baseline did not preserve one full segment")
    return {
        "config_resolution": True,
        "model_loading": True,
        "device_placement": "cpu",
        "valid_output": True,
        "schema_validation": True,
        "identity_recording": True,
        "repeated_smoke_execution": True,
        "segment_counts": segment_counts,
        "component_identity": resolution.component_identity_summary(),
    }


def _qualify_vad(
    resolution: ResolvedPipeline,
    loaded_audio: object,
    *,
    repetitions: int,
) -> tuple[dict[str, object], tuple[object, ...]]:
    detector = build_vad_from_config(resolution.pipeline_config)
    if detector is None:
        raise RuntimeError("configured VAD did not build")
    repeated = [tuple(detector.detect(loaded_audio)) for _ in range(repetitions)]
    serialized = [[region.to_jsonable() for region in regions] for regions in repeated]
    if any(value != serialized[0] for value in serialized[1:]):
        raise RuntimeError("repeated VAD output changed for identical audio")
    return (
        {
            "config_resolution": True,
            "model_loading": True,
            "device_placement": "cpu",
            "valid_output": True,
            "schema_validation": True,
            "identity_recording": True,
            "repeated_smoke_execution": True,
            "region_count": len(repeated[0]),
            "repeatable": True,
            "component_identity": resolution.component_identity_summary(),
        },
        repeated[0],
    )


def _qualify_chunker(
    resolution: ResolvedPipeline,
    record: Mapping[str, object],
    loaded_audio: object,
    regions_by_vad: Mapping[str, list[object]],
    *,
    repetitions: int,
) -> dict[str, object]:
    segmenter = build_segmenter_from_config(resolution.pipeline_config)
    if segmenter is None:
        raise RuntimeError("configured VADChunker did not build")
    evaluation_record = EvaluationRecord.from_record(record)
    compositions = {}
    for vad_name in ("energy_vad", "silero_vad"):
        regions = regions_by_vad.get(vad_name)
        if regions is None:
            compositions[vad_name] = {"status": "unavailable", "segment_count": 0}
            continue
        outputs = [
            tuple(segmenter.segment(evaluation_record, regions, loaded_audio))
            for _ in range(repetitions)
        ]
        serialized = [[segment.to_jsonable() for segment in value] for value in outputs]
        if any(value != serialized[0] for value in serialized[1:]):
            raise RuntimeError(f"VADChunker output changed with {vad_name}")
        compositions[vad_name] = {
            "status": "qualified",
            "segment_count": len(outputs[0]),
            "repeatable": True,
        }
    if not any(value["status"] == "qualified" for value in compositions.values()):
        raise RuntimeError("VADChunker had no available VAD composition")
    return {
        "config_resolution": True,
        "model_loading": True,
        "device_placement": "cpu",
        "valid_output": True,
        "schema_validation": True,
        "identity_recording": True,
        "repeated_smoke_execution": True,
        "compositions": compositions,
        "component_identity": resolution.component_identity_summary(),
    }


def _qualify_asr(
    resolution: ResolvedPipeline,
    record: Mapping[str, object],
    run_config: Mapping[str, object],
    *,
    repetitions: int,
) -> dict[str, object]:
    runner = PipelineRunner.from_config(resolution.pipeline_config)
    outputs = []
    elapsed = []
    for _index in range(repetitions):
        started = time.perf_counter()
        outputs.append(runner.predict(record, run_config))
        elapsed.append(time.perf_counter() - started)
    _validate_outputs(outputs, record)
    texts = [output.text for output in outputs]
    return {
        "config_resolution": True,
        "model_loading": True,
        "device_placement": "cpu",
        "valid_output": True,
        "schema_validation": True,
        "identity_recording": True,
        "repeated_smoke_execution": True,
        "nonempty_outputs": sum(bool(text.strip()) for text in texts),
        "text_repeatable": len(set(texts)) == 1,
        "cold_wall_sec": elapsed[0],
        "warm_wall_sec": elapsed[1:],
        "component_identity": resolution.component_identity_summary(),
    }


def _qualify_embedding(
    resolution: ResolvedPipeline,
    record: Mapping[str, object],
    run_config: Mapping[str, object],
    *,
    repetitions: int,
    degraded_audio: Path | None,
) -> tuple[dict[str, object], object]:
    embedder = build_speaker_embedding_from_config(resolution.pipeline_config)
    if embedder is None:
        raise RuntimeError("SpeechBrain ECAPA did not build")
    segment = _audio_segment(record)
    context = SpeakerEmbeddingContext.from_record_segment(
        record,
        segment,
        run_config=run_config,
        device="cpu",
        dtype="float32",
    )
    embeddings = [embedder.embed(segment, context) for _ in range(repetitions)]
    rows = [
        {
            "segment_id": "qualification",
            "condition": "clean",
            "repetition": index + 1,
            "duration_sec": embedding.segment_duration_sec,
            "status": embedding.status,
            "vector": list(embedding.vector),
        }
        for index, embedding in enumerate(embeddings)
    ]
    minimum_duration = float(getattr(embedder, "min_duration_sec", 0.75))
    short_end = max(0.01, minimum_duration / 2.0)
    short_segment = AudioSegment(
        audio_path=segment.audio_path,
        start_sec=0.0,
        end_sec=short_end,
        duration_sec=short_end,
        sample_rate_hz=16000,
    )
    short_context = SpeakerEmbeddingContext.from_record_segment(
        record,
        short_segment,
        segment_index=999,
        run_config=run_config,
        device="cpu",
        dtype="float32",
    )
    short_embedding = embedder.embed(short_segment, short_context)
    rows.append(
        {
            "segment_id": "minimum_duration_probe",
            "condition": "clean",
            "repetition": 1,
            "duration_sec": short_end,
            "status": short_embedding.status,
            "vector": list(short_embedding.vector),
        }
    )
    if degraded_audio is not None:
        degraded_segment = AudioSegment(
            audio_path=degraded_audio,
            start_sec=0.0,
            end_sec=_audio_duration(degraded_audio),
            duration_sec=_audio_duration(degraded_audio),
            sample_rate_hz=16000,
        )
        degraded_context = SpeakerEmbeddingContext(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            source_audio_path=degraded_audio,
            segment_index=0,
            device="cpu",
            dtype="float32",
            run_config=dict(run_config),
        )
        degraded_embedding = embedder.embed(degraded_segment, degraded_context)
        rows.append(
            {
                "segment_id": "qualification_degraded",
                "pair_id": "qualification",
                "condition": "degraded",
                "repetition": 1,
                "duration_sec": degraded_embedding.segment_duration_sec,
                "status": degraded_embedding.status,
                "vector": list(degraded_embedding.vector),
            }
        )
        rows[0]["pair_id"] = "qualification"
    metrics = analyze_embedding_results(rows, min_duration_sec=minimum_duration)
    if metrics["successful_extractions"] < repetitions:
        raise RuntimeError(
            "ECAPA did not return every repeated fixed-segment embedding"
        )
    if short_embedding.status != "too_short":
        raise RuntimeError("ECAPA did not explicitly reject the minimum-duration probe")
    return (
        {
            "config_resolution": True,
            "model_loading": True,
            "device_placement": "cpu",
            "valid_output": True,
            "schema_validation": True,
            "identity_recording": True,
            "repeated_smoke_execution": True,
            "metrics": metrics,
            "component_identity": resolution.component_identity_summary(),
        },
        embeddings[0],
    )


def _qualify_matcher(
    resolution: ResolvedPipeline,
    record: Mapping[str, object],
    run_config: Mapping[str, object],
    embedding: object,
    *,
    repetitions: int,
) -> dict[str, object]:
    _ = run_config
    if embedding is None or not getattr(embedding, "vector", ()):
        raise RuntimeError("cosine composition requires a qualified ECAPA embedding")
    matcher = build_speaker_matcher_from_config(resolution.pipeline_config)
    if matcher is None:
        raise RuntimeError("cosine matcher did not build")
    model_id = str(getattr(embedding, "model_name", "speechbrain_ecapa"))
    database, _exemplar = add_enrollment_exemplar(
        EnrollmentDatabase.empty(created_at="2026-01-01T00:00:00Z"),
        display_name="Qualification",
        prompt_id="stage7_contract",
        audio_path=Path(str(record["inference_audio_path"])),
        embedding=getattr(embedding, "vector"),
        model_id=model_id,
        duration_sec=getattr(embedding, "segment_duration_sec", None),
    )
    decisions = [matcher.match(embedding, database) for _ in range(repetitions)]
    if any(
        not decision.accepted or decision.speaker_label != "Qualification"
        for decision in decisions
    ):
        raise RuntimeError(
            "cosine matcher rejected its identical enrollment/query contract probe"
        )
    unknown = matcher.match(embedding, EnrollmentDatabase.empty())
    if unknown.speaker_label != "Unknown" or unknown.accepted:
        raise RuntimeError(
            "cosine matcher did not preserve Unknown for an empty enrollment DB"
        )
    return {
        "config_resolution": True,
        "model_loading": True,
        "device_placement": "cpu",
        "valid_output": True,
        "schema_validation": True,
        "identity_recording": True,
        "repeated_smoke_execution": True,
        "accepted_identical_query": True,
        "unknown_label_preserved": True,
        "scope": "contract_and_composition_only",
        "stage10_metrics_emitted": False,
        "component_identity": resolution.component_identity_summary(),
    }


def _run_qualification(
    result_id: str,
    family: str,
    component: str,
    repetitions: int,
    catalog_entry: ComponentCatalogEntry,
    operation: Callable[[], dict[str, object]],
) -> dict[str, object]:
    started = time.perf_counter()
    try:
        details = operation()
    except Exception as exc:  # component boundaries must remain isolated
        status = "unavailable" if _is_unavailable(exc) else "failed"
        details = {}
        reason = f"{type(exc).__name__}: {exc}"
    else:
        status = "qualified"
        reason = None
    return {
        "schema_version": QUALIFICATION_RESULT_SCHEMA_VERSION,
        "result_id": result_id,
        "family": family,
        "component": component,
        "status": status,
        "repetitions": repetitions,
        "duration_sec": round(time.perf_counter() - started, 6),
        "reason": reason,
        "catalog_identity": _catalog_identity(catalog_entry),
        "details": details,
    }


def _catalog_identity(entry: ComponentCatalogEntry) -> dict[str, object]:
    value = entry.to_jsonable()
    return {
        key: deepcopy(value[key])
        for key in (
            "family",
            "name",
            "implementation_class",
            "source_config_path",
            "source_config_sha256",
            "required_packages",
            "required_assets",
            "credential_requirements",
            "device_dtype_settings",
            "input_contract",
            "output_contract",
            "compatibility_rules",
            "qualification_status",
            "model_identity",
            "model_asset_identity",
        )
    }


def _candidate_resolution(
    strategy: str,
    asr: str,
    selected_pipeline_path: Path,
    catalog: ComponentCatalog,
) -> ResolvedPipeline:
    return resolve_pipeline(
        selected_pipeline_path,
        component_overrides=candidate_component_overrides(f"{strategy}__{asr}"),
        catalog=catalog,
    )


def _validate_outputs(outputs: list[object], record: Mapping[str, object]) -> None:
    for output in outputs:
        if getattr(output, "errors", ()):
            raise RuntimeError(f"pipeline output contained errors: {output.errors}")
        prediction = output.to_utterance_prediction_row()
        if prediction["recording_id"] != record["recording_id"]:
            raise RuntimeError("pipeline changed recording_id")
        if prediction["utt_id"] != record["utt_id"]:
            raise RuntimeError("pipeline changed utt_id")
        if prediction["start_sec"] != record["start_sec"]:
            raise RuntimeError("pipeline changed start_sec")
        if prediction["end_sec"] != record["end_sec"]:
            raise RuntimeError("pipeline changed end_sec")
        if not isinstance(prediction["text"], str):
            raise RuntimeError("pipeline text is not a string")


def _record(audio_path: Path, duration_sec: float) -> dict[str, object]:
    return {
        "recording_id": "stage7_core_qualification",
        "source_recording_id": "stage7_core_qualification",
        "utt_id": "stage7_core_qualification",
        "inference_audio_path": str(audio_path),
        "start_sec": 0.0,
        "end_sec": duration_sec,
        "duration_sec": duration_sec,
        "sample_rate_hz": int(sf.info(audio_path).samplerate),
        "channel_count": int(sf.info(audio_path).channels),
    }


def _audio_segment(record: Mapping[str, object]) -> AudioSegment:
    return AudioSegment(
        audio_path=Path(str(record["inference_audio_path"])),
        start_sec=float(record["start_sec"]),
        end_sec=float(record["end_sec"]),
        duration_sec=float(record["duration_sec"]),
        sample_rate_hz=int(record["sample_rate_hz"]),
        channel_count=int(record["channel_count"]),
    )


def _audio_duration(path: Path) -> float:
    info = sf.info(path)
    return float(info.frames) / float(info.samplerate)


def _is_unavailable(exc: BaseException) -> bool:
    names = [type(item).__name__.lower() for item in _exception_chain(exc)]
    text = " ".join(str(item).lower() for item in _exception_chain(exc))
    return any("unavailable" in name for name in names) or any(
        marker in text
        for marker in (
            "not installed",
            "not available locally",
            "model asset does not exist",
            "downloads are disabled",
            "cuda was requested but is not available",
        )
    )


def _exception_chain(exc: BaseException) -> list[BaseException]:
    values = []
    current: BaseException | None = exc
    while current is not None and current not in values:
        values.append(current)
        current = current.__cause__ or current.__context__
    return values


def _portable_path(path: Path | None, project_root: Path) -> str | None:
    if path is None:
        return None
    candidates = (project_root.resolve(), Path(__file__).resolve().parents[2])
    for root in candidates:
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
    return f"external:{path.name}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        json.loads(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
