"""Real single-job CUDA qualification for the Stage 7 core models."""

from __future__ import annotations

import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np
import soundfile as sf
import torch
import yaml

from app.extended_backends.registry import REPOSITORY_ROOT, TOOL_ROOT


def qualify_core_cuda(audio_path: Path | None = None, output_path: Path | None = None) -> dict[str, object]:
    if not torch.cuda.is_available():
        raise RuntimeError("core CUDA qualification requires torch.cuda.is_available()")
    source_audio = _resolve_audio(audio_path)
    results = [_qualify_whisper(size, source_audio) for size in ("tiny", "base", "small")]
    results.append(_qualify_ecapa(source_audio))
    payload: dict[str, object] = {
        "schema_version": "core-cuda-qualification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {"single_gpu_job_only": True, "implicit_downloads_allowed": False},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "gpu_count": torch.cuda.device_count(),
        },
        "results": results,
        "summary": {
            "total": len(results),
            "qualified": sum(result["status"] == "qualified" for result in results),
        },
    }
    destination = output_path or TOOL_ROOT / "runs/extended_backend_qualification/core-cuda.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return payload


def _qualify_whisper(size: str, audio_path: Path) -> dict[str, object]:
    from app.inference_pipeline.asr import build_asr_from_config
    from app.inference_pipeline.config import PipelineConfig
    from app.inference_pipeline.pipeline import PipelineRunner

    fragment = _component(f"asr/whisper_{size}.yaml")
    fragment["params"] = {
        **dict(fragment.get("params") or {}),
        "device": "cuda",
        "dtype": "float16",
        "allow_model_downloads": False,
    }
    config = _single_component_config(PipelineConfig, "asr", fragment, "cuda", "float16")
    adapter = build_asr_from_config(config)
    if adapter is None:
        raise RuntimeError(f"Whisper {size} did not build")
    runner = PipelineRunner.from_config(config)
    runner.asr = adapter
    outputs = []
    timings = []
    record = _record(audio_path)
    torch.cuda.reset_peak_memory_stats()
    for _ in range(2):
        started = time.perf_counter()
        output = runner.predict(record, _run_config())
        torch.cuda.synchronize()
        timings.append(time.perf_counter() - started)
        if output.errors or not output.text.strip():
            raise RuntimeError(f"Whisper {size} failed real CUDA inference")
        outputs.append(output.text)
    return {
        "component": f"whisper_{size}",
        "status": "qualified",
        "device": "cuda",
        "dtype": "float16",
        "outputs_equal": len(set(outputs)) == 1,
        "inference_sec": timings,
        "peak_vram_bytes": torch.cuda.max_memory_allocated(),
    }


def _qualify_ecapa(audio_path: Path) -> dict[str, object]:
    from app.inference_pipeline.config import PipelineConfig
    from app.inference_pipeline.speaker_embedding import build_speaker_embedding_from_config
    from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext

    fragment = _component("speaker_embedding/speechbrain_ecapa.yaml")
    fragment["params"] = {
        **dict(fragment.get("params") or {}),
        "device": "cuda",
        "dtype": "float32",
        "allow_model_downloads": False,
    }
    config = _single_component_config(PipelineConfig, "speaker_embedding", fragment, "cuda", "float32")
    adapter = build_speaker_embedding_from_config(config)
    if adapter is None:
        raise RuntimeError("SpeechBrain ECAPA did not build")
    record = _record(audio_path)
    segment = _segment(record)
    vectors = []
    timings = []
    torch.cuda.reset_peak_memory_stats()
    for index in range(2):
        context = SpeakerEmbeddingContext(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            source_audio_path=audio_path,
            segment_index=index,
            device="cuda",
            dtype="float32",
            run_config={"project_root": str(TOOL_ROOT.parent)},
        )
        started = time.perf_counter()
        result = adapter.embed(segment, context)
        torch.cuda.synchronize()
        timings.append(time.perf_counter() - started)
        if result.status != "ok" or not result.vector:
            raise RuntimeError("SpeechBrain ECAPA failed real CUDA extraction")
        vector = np.asarray(result.vector)
        if not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-4):
            raise RuntimeError("SpeechBrain ECAPA returned an invalid vector")
        vectors.append(vector)
    return {
        "component": "speechbrain_ecapa",
        "status": "qualified",
        "device": "cuda",
        "dtype": "float32",
        "dimension": int(vectors[0].size),
        "repeatability_l2_drift": float(np.linalg.norm(vectors[1] - vectors[0])),
        "inference_sec": timings,
        "peak_vram_bytes": torch.cuda.max_memory_allocated(),
    }


def _single_component_config(config_type: object, slot: str, fragment: Mapping[str, object], device: str, precision: str) -> object:
    mapping = config_type.from_yaml_path(TOOL_ROOT / "configs/inference/live_mic_whisper_base.yaml").to_jsonable()
    mapping["runtime"].update({"device": device, "precision": precision, "allow_model_downloads": False})
    for value in mapping["components"].values():
        value["enabled"] = False
    mapping["components"][slot] = dict(fragment)
    return config_type.from_mapping(mapping)


def _component(relative: str) -> dict[str, object]:
    data = yaml.safe_load((TOOL_ROOT / "configs/inference/components" / relative).read_text(encoding="utf-8"))
    return dict(data["component"])


def _record(path: Path) -> dict[str, object]:
    info = sf.info(path)
    duration = info.frames / info.samplerate
    return {"recording_id": "core-cuda", "utt_id": "core-cuda-0001", "inference_audio_path": str(path), "audio_path_resolved": str(path), "start_sec": 0.0, "end_sec": duration, "duration_sec": duration, "sample_rate_hz": info.samplerate, "channel_count": info.channels}


def _segment(record: Mapping[str, object]) -> object:
    from app.inference_pipeline.contracts import AudioSegment
    return AudioSegment(audio_path=Path(str(record["inference_audio_path"])), start_sec=0.0, end_sec=float(record["end_sec"]), duration_sec=float(record["duration_sec"]), sample_rate_hz=int(record["sample_rate_hz"]), channel_count=int(record["channel_count"]), is_mono=int(record["channel_count"]) == 1)


def _run_config() -> dict[str, object]:
    return {"project_root": str(TOOL_ROOT.parent), "runtime": {"device": "cuda", "precision": "float16", "sample_rate_hz": 16000}, "asr": {"language": "en"}}


def _resolve_audio(value: Path | None) -> Path:
    candidate = value or REPOSITORY_ROOT / "Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic/cmu_us_aew_arctic/wav/arctic_b0476.wav"
    candidate = candidate.expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate
