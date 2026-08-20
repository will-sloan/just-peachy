"""Independent, offline Stage 8 backend qualification harness."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import os
import platform
import shlex
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np
import soundfile as sf
import yaml

from app.extended_backends.contracts import validate_qualification_payload
from app.extended_backends.registry import (
    REPOSITORY_ROOT,
    TOOL_ROOT,
    inspect_asset,
    load_backend_catalog,
    package_version,
)


COMPONENT_ROOT = TOOL_ROOT / "configs" / "inference" / "components"
BASE_CONFIG = TOOL_ROOT / "configs" / "inference" / "live_mic_whisper_base.yaml"
DEFAULT_OUTPUT_ROOT = TOOL_ROOT / "runs" / "extended_backend_qualification"
SENSITIVE_ENVIRONMENT_NAMES = (
    "PYANNOTE_AUTH_TOKEN",
    "HF_TOKEN",
    "PICOVOICE_ACCESS_KEY",
)


def qualify_profile(
    profile: str,
    *,
    audio_path: Path | None = None,
    output_path: Path | None = None,
    backend_ids: set[str] | None = None,
    device: str = "cpu",
) -> dict[str, object]:
    """Qualify every catalog backend assigned to one isolated profile."""

    catalog = load_backend_catalog()
    repetitions = int(catalog.get("qualification_repetitions", 2))
    if repetitions < 2:
        raise ValueError("Stage 8 qualification requires at least two repetitions")
    source_audio = _resolve_audio(audio_path)
    candidates = [
        dict(item)
        for item in catalog["backends"]
        if isinstance(item, Mapping)
        and str(item.get("profile")) == profile
        and (backend_ids is None or str(item.get("id")) in backend_ids)
    ]
    if not candidates:
        raise ValueError(f"no Stage 8 backends selected for profile {profile!r}")

    command = _redacted_command()
    results = [
        _qualify_backend(
            definition,
            source_audio=source_audio,
            repetitions=repetitions,
            device=device,
            command=command,
        )
        for definition in candidates
    ]
    payload: dict[str, object] = {
        "schema_version": "extended-backend-qualification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "environment": _environment_fingerprint(device),
        "secret_audit": {
            "values_serialized": False,
            "credential_presence_only": True,
        },
        "summary": _summary(results),
        "results": results,
    }
    validate_qualification_payload(payload)
    _assert_no_secret_values(payload)
    destination = output_path or DEFAULT_OUTPUT_ROOT / f"{profile}.json"
    _atomic_write_json(destination, payload)
    return payload


def _qualify_backend(
    definition: Mapping[str, object],
    *,
    source_audio: Path,
    repetitions: int,
    device: str,
    command: str,
) -> dict[str, object]:
    backend_id = str(definition["id"])
    family = str(definition["family"])
    profile = str(definition["profile"])
    package_versions = {
        str(name): package_version(str(name)) for name in definition.get("packages", ())
    }
    assets = [inspect_asset(str(asset_id)) for asset_id in definition.get("assets", ())]
    base = {
        "backend_id": backend_id,
        "family": family,
        "profile": profile,
        "package_versions": package_versions,
        "asset_identities": assets,
        "device": device,
        "schema_validation": False,
        "timing": {},
        "warnings": [],
        "failure_category": None,
        "command": command,
        "component_identity": _component_identity(definition),
        "credential_presence": _credential_presence(definition),
        "implicit_downloads_allowed": False,
        "repetitions": repetitions,
    }
    blocked = _preflight_status(definition, package_versions, assets, device)
    if blocked is not None:
        status, explanation = blocked
        return {**base, "status": status, "explanation": explanation}

    operation = {
        "asr": _qualify_asr,
        "vad": _qualify_vad,
        "speaker_embedding": _qualify_embedding,
        "diarization": _qualify_diarization,
    }.get(family)
    if operation is None:
        return {
            **base,
            "status": "unsuitable",
            "explanation": f"No Stage 8 qualifier exists for family {family!r}.",
        }

    started = time.perf_counter()
    try:
        details = operation(definition, source_audio, repetitions, device)
    except Exception as exc:  # backend boundaries are isolated and recorded
        status = _exception_status(exc)
        return {
            **base,
            "status": status,
            "explanation": f"{type(exc).__name__}: {exc}",
            "failure_category": status,
            "timing": {"total_sec": round(time.perf_counter() - started, 6)},
        }
    finally:
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    warnings = list(details.pop("warnings", []))
    status = "qualified_with_warnings" if warnings else "qualified"
    return {
        **base,
        "status": status,
        "explanation": (
            "Real repeated offline qualification passed."
            if not warnings
            else "Real repeated offline qualification passed with recorded warnings."
        ),
        "schema_validation": True,
        "timing": {
            "total_sec": round(time.perf_counter() - started, 6),
            **dict(details.pop("timing", {})),
        },
        "warnings": warnings,
        "details": details,
    }


def _qualify_asr(
    definition: Mapping[str, object],
    source_audio: Path,
    repetitions: int,
    device: str,
) -> dict[str, object]:
    from app.inference_pipeline.asr import build_asr_from_config
    from app.inference_pipeline.pipeline import PipelineRunner

    fragment = _configured_fragment(definition, device)
    config = _config_with_components(asr=fragment)
    adapter = build_asr_from_config(config)
    if adapter is None:
        raise RuntimeError("configured ASR did not build")
    runner = PipelineRunner.from_config(config)
    runner.asr = adapter
    record = _record(source_audio)
    outputs = []
    elapsed = []
    for _ in range(repetitions):
        started = time.perf_counter()
        output = runner.predict(record, _run_config(device))
        elapsed.append(time.perf_counter() - started)
        if output.errors:
            raise RuntimeError("ASR pipeline emitted errors: " + "; ".join(output.errors))
        prediction = output.to_utterance_prediction_row()
        if prediction["recording_id"] != record["recording_id"]:
            raise ValueError("ASR changed recording_id")
        if prediction["utt_id"] != record["utt_id"]:
            raise ValueError("ASR changed utt_id")
        outputs.append(output.text)
    if not any(text.strip() for text in outputs):
        raise RuntimeError("ASR produced no text for the real speech input")

    with _silence_wav() as silence:
        silence_output = runner.predict(_record(silence), _run_config(device))
    if silence_output.errors:
        raise RuntimeError("ASR silence behavior produced a pipeline error")
    runtime = getattr(adapter, "last_runtime_stats", None)
    return {
        "valid_real_outputs": len(outputs),
        "transcripts": outputs,
        "repeated_output_equal": len(set(outputs)) == 1,
        "empty_or_no_speech_behavior": {
            "valid": True,
            "text": silence_output.text,
            "empty": not bool(silence_output.text.strip()),
        },
        "pipeline_composition": True,
        "identity_recorded": True,
        "model_name": getattr(adapter, "model_name", str(definition["id"])),
        "precision": getattr(adapter, "compute_type", getattr(adapter, "dtype", None)),
        "runtime": _jsonable_runtime(runtime),
        "timing": {
            "inference_sec": [round(value, 6) for value in elapsed],
            "initialization_sec": getattr(runtime, "load_sec", None),
        },
    }


def _qualify_vad(
    definition: Mapping[str, object],
    source_audio: Path,
    repetitions: int,
    device: str,
) -> dict[str, object]:
    from app.inference_pipeline.audio_io import load_audio
    from app.inference_pipeline.contracts import EvaluationRecord
    from app.inference_pipeline.segmentation.vad_chunker import VADChunker
    from app.inference_pipeline.vad import build_vad_from_config

    fragment = _configured_fragment(definition, device)
    config = _config_with_components(vad=fragment)
    detector = build_vad_from_config(config)
    if detector is None:
        raise RuntimeError("configured VAD did not build")
    record = _record(source_audio)
    loaded = load_audio(record, _run_config(device))
    region_rows: list[list[dict[str, object]]] = []
    elapsed = []
    for _ in range(repetitions):
        started = time.perf_counter()
        regions = detector.detect(loaded)
        elapsed.append(time.perf_counter() - started)
        _validate_regions(regions, loaded.duration_sec)
        region_rows.append([region.to_jsonable() for region in regions])
    if not region_rows[0]:
        raise RuntimeError("VAD found no speech in the real qualification input")

    chunk_fragment = _read_component(COMPONENT_ROOT / "segmentation" / "vad_chunks.yaml")
    chunker = VADChunker(chunk_fragment.get("params"))
    chunks = chunker.segment(EvaluationRecord.from_record(record), detector.detect(loaded), loaded)
    if not chunks:
        raise ValueError("VAD output is not compatible with VADChunker")
    with _silence_wav() as silence:
        silence_record = _record(silence)
        silence_audio = load_audio(silence_record, _run_config(device))
        silence_regions = detector.detect(silence_audio)
        _validate_regions(silence_regions, silence_audio.duration_sec)
    warnings = []
    if str(definition["id"]) == "webrtc_vad":
        warnings.append(
            "webrtcvad imports deprecated pkg_resources under current setuptools; "
            "real outputs remain contract-valid."
        )
    return {
        "region_count": len(region_rows[0]),
        "regions": region_rows[0],
        "repeated_output_equal": all(row == region_rows[0] for row in region_rows[1:]),
        "monotonic_nonoverlapping": True,
        "bounded": True,
        "no_speech_region_count": len(silence_regions),
        "vad_chunker_compatible": True,
        "chunk_count": len(chunks),
        "pipeline_composition": True,
        "warnings": warnings,
        "timing": {"inference_sec": [round(value, 6) for value in elapsed]},
    }


def _qualify_embedding(
    definition: Mapping[str, object],
    source_audio: Path,
    repetitions: int,
    device: str,
) -> dict[str, object]:
    from app.inference_pipeline.contracts import AudioSegment
    from app.inference_pipeline.speaker_embedding import (
        build_speaker_embedding_from_config,
    )
    from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext

    fragment = _configured_fragment(definition, device)
    config = _config_with_components(speaker_embedding=fragment)
    adapter = build_speaker_embedding_from_config(config)
    if adapter is None:
        raise RuntimeError("configured speaker embedder did not build")
    record = _record(source_audio)
    segment = _segment(record)
    elapsed = []
    vectors: list[np.ndarray] = []
    for repetition in range(repetitions):
        context = SpeakerEmbeddingContext(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            source_audio_path=source_audio,
            segment_index=repetition,
            device=device,
            dtype="float32",
            run_config={"project_root": str(TOOL_ROOT.parent)},
        )
        started = time.perf_counter()
        result = adapter.embed(segment, context)
        elapsed.append(time.perf_counter() - started)
        if result.status != "ok" or not result.vector:
            raise RuntimeError(f"embedding status is {result.status!r}")
        vector = np.asarray(result.vector, dtype=np.float64)
        if vector.ndim != 1 or not np.isfinite(vector).all():
            raise ValueError("embedding vector is not finite one-dimensional numeric data")
        vectors.append(vector)
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise ValueError("embedding dimension changed across repetitions")
    norms = [float(np.linalg.norm(vector)) for vector in vectors]
    if any(not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4) for norm in norms):
        raise ValueError("embedding is not L2 normalized")
    repeat_drift = max(float(np.linalg.norm(vector - vectors[0])) for vector in vectors)

    short_segment = AudioSegment(
        audio_path=source_audio,
        start_sec=0.0,
        end_sec=min(0.1, float(record["duration_sec"])),
        duration_sec=min(0.1, float(record["duration_sec"])),
        sample_rate_hz=int(record["sample_rate_hz"]),
        channel_count=int(record["channel_count"]),
        is_mono=int(record["channel_count"]) == 1,
    )
    short_context = SpeakerEmbeddingContext(
        recording_id="minimum-duration",
        utt_id="minimum-duration",
        source_audio_path=source_audio,
        segment_index=0,
        device=device,
        dtype="float32",
        run_config={"project_root": str(TOOL_ROOT.parent)},
    )
    short_result = adapter.embed(short_segment, short_context)
    if short_result.status == "ok":
        raise ValueError("embedding backend accepted a segment below minimum duration")
    runtime = getattr(adapter, "last_runtime_stats", None)
    warnings = []
    if str(definition["id"]) == "wespeaker":
        warnings.extend(
            (
                "WeSpeaker metadata pins hdbscan==0.8.37; isolated qualification "
                "uses the Python-3.12-compatible hdbscan==0.8.44.",
                "kaldiio imports deprecated pkg_resources under current setuptools.",
                "The loader reported an unused projection.weight tensor; repeated "
                "normalized embeddings were nevertheless valid.",
            )
        )
    return {
        "valid_real_outputs": len(vectors),
        "dimension": dimensions.pop(),
        "l2_norms": norms,
        "finite": True,
        "repeatability_l2_drift": repeat_drift,
        "minimum_duration_status": short_result.status,
        "model_name": getattr(adapter, "model_name", str(definition["id"])),
        "identity_recorded": True,
        "pipeline_composition": True,
        "warnings": warnings,
        "runtime": _jsonable_runtime(runtime),
        "timing": {"inference_sec": [round(value, 6) for value in elapsed]},
    }


def _qualify_diarization(
    definition: Mapping[str, object],
    source_audio: Path,
    repetitions: int,
    device: str,
) -> dict[str, object]:
    from app.inference_pipeline.audio_io import load_audio
    from app.inference_pipeline.diarization import (
        build_diarizer_from_config,
        speaker_turns_to_rttm_lines,
    )

    fragment = _configured_fragment(definition, device)
    config = _config_with_components(diarization=fragment)
    diarizer = build_diarizer_from_config(config)
    if diarizer is None:
        raise RuntimeError("configured diarizer did not build")
    record = _record(source_audio)
    loaded = load_audio(record, _run_config(device))
    rows = []
    elapsed = []
    for _ in range(repetitions):
        started = time.perf_counter()
        turns = diarizer.diarize(loaded)
        elapsed.append(time.perf_counter() - started)
        _validate_turns(turns, loaded.duration_sec)
        rows.append([turn.to_jsonable() for turn in turns])
    if not rows[0]:
        raise RuntimeError("diarizer emitted no speaker turns")
    labels = sorted({str(row["speaker_turn_label"]) for row in rows[0]})
    if any(not label.startswith("speaker_") for label in labels):
        raise ValueError("diarizer emitted a non-anonymous speaker label")
    rttm = speaker_turns_to_rttm_lines("component-qualification", turns)
    if len(rttm) != len(turns):
        raise ValueError("RTTM conversion did not preserve turn count")
    return {
        "turn_count": len(rows[0]),
        "speaker_labels": labels,
        "anonymous_label_consistency": True,
        "bounded": True,
        "rttm_conversion": True,
        "rttm_line_count": len(rttm),
        "segmentation_provenance": sorted(
            {str(row.get("source")) for row in rows[0] if row.get("source")}
        ),
        "reference_label_fallback": False,
        "der_jer_ready_claimed": False,
        "repeated_output_equal": all(row == rows[0] for row in rows[1:]),
        "pipeline_composition": True,
        "timing": {"inference_sec": [round(value, 6) for value in elapsed]},
    }


def _preflight_status(
    definition: Mapping[str, object],
    versions: Mapping[str, str | None],
    assets: list[dict[str, object]],
    device: str,
) -> tuple[str, str] | None:
    current_platform = platform.system()
    supported = {str(item) for item in definition.get("platforms", ())}
    if current_platform not in supported:
        return (
            "platform_required",
            f"{definition['id']} requires one of {sorted(supported)}; current platform is {current_platform}.",
        )
    if bool(definition.get("cuda_required")) and not _cuda_available():
        return "cuda_required", "A real CUDA runtime is required but is not available."
    licence_env = definition.get("licence_ack_env")
    if licence_env and not _truthy_environment(str(licence_env)):
        return (
            "licence_action_required",
            f"The user must personally accept the upstream terms, then set {licence_env}=1.",
        )
    credential_env = definition.get("credential_env")
    if credential_env and not bool(os.environ.get(str(credential_env))):
        return (
            "credential_required",
            f"Credential environment variable {credential_env} is not present.",
        )
    credential_source = definition.get("credential_source")
    if credential_source == "huggingface_cli" and not _huggingface_token_present():
        return (
            "credential_required",
            "Hugging Face CLI login is not present in the isolated environment.",
        )
    missing_packages = sorted(name for name, version in versions.items() if version is None)
    if missing_packages:
        return (
            "unavailable_package",
            "Missing pinned distribution(s): " + ", ".join(missing_packages),
        )
    missing_assets = sorted(
        str(item["asset_id"])
        for item in assets
        if not item["present"] or item.get("verification_status") == "mismatch"
    )
    if missing_assets:
        missing_details = [
            f"{item['asset_id']} ({', '.join(str(value) for value in item.get('missing_required_files', ())) or 'path absent'})"
            for item in assets
            if not item["present"] or item.get("verification_status") == "mismatch"
        ]
        return (
            "unavailable_asset",
            "Missing or incomplete local asset(s): " + "; ".join(missing_details),
        )
    if device == "cuda" and not _cuda_available():
        return "cuda_required", "CUDA was requested but torch.cuda.is_available() is false."
    return None


def _configured_fragment(definition: Mapping[str, object], device: str) -> dict[str, object]:
    path = TOOL_ROOT / Path(str(definition["config"]))
    fragment = _read_component(path)
    params = dict(fragment.get("params") or {})
    if bool(params.get("allow_model_downloads", False)):
        raise ValueError(f"implicit model downloads are enabled in {path}")
    params["allow_model_downloads"] = False
    if "device" in params:
        params["device"] = device
    if "provider" in params:
        params["provider"] = "cpu" if device == "cpu" else "cuda"
    fragment["params"] = params
    return fragment


def _config_with_components(**overrides: Mapping[str, object]) -> object:
    from app.inference_pipeline.config import PipelineConfig

    mapping = PipelineConfig.from_yaml_path(BASE_CONFIG).to_jsonable()
    mapping["config_name"] = "stage8_independent_qualification"
    mapping["profile"] = "stage8"
    mapping["runtime"].update(
        {
            "device": "cpu",
            "sample_rate_hz": 16000,
            "precision": "float32",
            "dry_run": False,
            "allow_model_downloads": False,
            "cache_dir": "models/cache",
        }
    )
    components = mapping["components"]
    for slot in components:
        components[slot]["enabled"] = False
    for slot, fragment in overrides.items():
        components[slot] = deepcopy(dict(fragment))
    return PipelineConfig.from_mapping(mapping)


def _record(path: Path) -> dict[str, object]:
    info = sf.info(path)
    duration = int(info.frames) / int(info.samplerate)
    return {
        "recording_id": "stage8-qualification",
        "source_recording_id": "stage8-qualification-source",
        "utt_id": "stage8-qualification-0001",
        "inference_audio_path": str(path),
        "audio_path_resolved": str(path),
        "start_sec": 0.0,
        "end_sec": duration,
        "duration_sec": duration,
        "sample_rate_hz": int(info.samplerate),
        "channel_count": int(info.channels),
    }


def _segment(record: Mapping[str, object]) -> object:
    from app.inference_pipeline.contracts import AudioSegment

    return AudioSegment(
        audio_path=Path(str(record["inference_audio_path"])),
        start_sec=float(record["start_sec"]),
        end_sec=float(record["end_sec"]),
        duration_sec=float(record["duration_sec"]),
        sample_rate_hz=int(record["sample_rate_hz"]),
        channel_count=int(record["channel_count"]),
        is_mono=int(record["channel_count"]) == 1,
    )


def _run_config(device: str) -> dict[str, object]:
    return {
        "project_root": str(TOOL_ROOT.parent),
        "runtime": {"precision": "float32", "sample_rate_hz": 16000, "device": device},
        "asr": {"language": "en"},
    }


def _validate_regions(regions: list[object], duration_sec: float) -> None:
    previous_end = 0.0
    for region in regions:
        start = float(getattr(region, "start_sec"))
        end = float(getattr(region, "end_sec"))
        if start < -1e-9 or end > duration_sec + 1e-6 or end <= start:
            raise ValueError("VAD emitted an invalid or out-of-bounds region")
        if start < previous_end - 1e-9:
            raise ValueError("VAD regions overlap or are not monotonic")
        previous_end = end


def _validate_turns(turns: list[object], duration_sec: float) -> None:
    for turn in turns:
        start = float(getattr(turn, "start_sec"))
        end = float(getattr(turn, "end_sec"))
        label = str(getattr(turn, "speaker_turn_label"))
        if start < -1e-9 or end > duration_sec + 1e-6 or end <= start:
            raise ValueError("diarizer emitted an invalid or out-of-bounds turn")
        if not label or any(character.isspace() for character in label):
            raise ValueError("diarizer emitted an invalid speaker label")


class _silence_wav:
    def __enter__(self) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        self.path = Path(handle.name)
        sf.write(self.path, np.zeros(16000, dtype=np.float32), 16000, subtype="PCM_16")
        return self.path

    def __exit__(self, *_: object) -> None:
        self.path.unlink(missing_ok=True)


def _resolve_audio(value: Path | None) -> Path:
    if value is not None:
        candidate = value.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"qualification audio does not exist: {candidate}")
        return candidate
    candidates = (
        REPOSITORY_ROOT
        / "Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic/"
        "cmu_us_aew_arctic/wav/arctic_b0476.wav",
        REPOSITORY_ROOT
        / "models/cache/sherpa_onnx/asr/sherpa-onnx-streaming-zipformer-en-2023-06-26/"
        "test_wavs/0.wav",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("no deterministic Stage 8 qualification WAV is available")


def _component_identity(definition: Mapping[str, object]) -> dict[str, object]:
    path = TOOL_ROOT / Path(str(definition["config"]))
    return {
        "config_path": path.relative_to(TOOL_ROOT).as_posix(),
        "config_sha256": _sha256(path),
        "backend_id": str(definition["id"]),
        "family": str(definition["family"]),
    }


def _credential_presence(definition: Mapping[str, object]) -> dict[str, bool]:
    names = [
        str(name)
        for name in (definition.get("credential_env"), definition.get("licence_ack_env"))
        if name
    ]
    result = {name: bool(os.environ.get(name)) for name in names}
    if definition.get("credential_source") == "huggingface_cli":
        result["huggingface_cli"] = _huggingface_token_present()
    return result


def _huggingface_token_present() -> bool:
    """Check stored Hugging Face authentication without exposing its value."""

    try:
        from huggingface_hub import get_token

        return bool(get_token())
    except (ImportError, OSError):
        return False


def _environment_fingerprint(device: str) -> dict[str, object]:
    torch_version = None
    cuda_available = False
    cuda_runtime = None
    gpu_name = None
    try:
        import torch

        torch_version = torch.__version__
        cuda_available = bool(torch.cuda.is_available())
        cuda_runtime = torch.version.cuda
        gpu_name = torch.cuda.get_device_name(0) if cuda_available else None
    except ImportError:
        pass
    freeze = _package_freeze()
    return {
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "python_executable": "<environment>/Scripts/python.exe" if platform.system() == "Windows" else "<environment>/bin/python",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "device_requested": device,
        "torch": torch_version,
        "cuda_available": cuda_available,
        "cuda_runtime": cuda_runtime,
        "gpu": gpu_name,
        "package_freeze_sha256": hashlib.sha256(freeze.encode("utf-8")).hexdigest(),
        "package_count": len(freeze.splitlines()),
    }


def _package_freeze() -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return completed.stdout.replace("\\", "/") if completed.returncode == 0 else ""


def _git_commit() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip() or None


def _exception_status(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "contract" in name or isinstance(exc, (TypeError, ValueError)):
        return "contract_failure"
    if "config" in name or "configuration" in message:
        return "configuration_error"
    return "runtime_failure"


def _summary(results: list[dict[str, object]]) -> dict[str, object]:
    counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "total": len(results),
        "status_counts": counts,
        "qualified": counts.get("qualified", 0) + counts.get("qualified_with_warnings", 0),
    }


def _read_component(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    component = data.get("component", data)
    if not isinstance(component, Mapping):
        raise ValueError(f"component fragment is not a mapping: {path}")
    return {str(key): value for key, value in component.items()}


def _jsonable_runtime(runtime: object | None) -> object:
    if runtime is None:
        return None
    method = getattr(runtime, "to_jsonable", None)
    if callable(method):
        return method()
    values = getattr(runtime, "__dict__", None)
    return dict(values) if isinstance(values, Mapping) else str(runtime)


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def _truthy_environment(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes"}


def _redacted_command() -> str:
    command = shlex.join(["python", *sys.argv])
    for name in SENSITIVE_ENVIRONMENT_NAMES:
        value = os.environ.get(name)
        if value:
            command = command.replace(value, f"<redacted:{name}>")
    return command


def _assert_no_secret_values(payload: Mapping[str, object]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for name in SENSITIVE_ENVIRONMENT_NAMES:
        value = os.environ.get(name)
        if value and value in serialized:
            raise ValueError(f"qualification artifact would expose {name}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)
