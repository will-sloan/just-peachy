"""Run real, local speech-component and interoperability smoke qualification.

This is deliberately a qualification harness, not the combinational evaluation
framework.  It executes one deterministic speech file through every configured
runtime backend, records explicit unavailable states for gated backends, and
checks a small set of meaningful end-to-end compositions.
"""

# ruff: noqa: E402 -- imports follow the deliberate local sys.path bootstrap.

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import sys
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

import soundfile as sf
import torch
import yaml


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOL_ROOT.parent.parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.asr import build_asr_from_config
from app.inference_pipeline.audio_io import load_audio
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.diarization import build_diarizer_from_config
from app.inference_pipeline.enrollment import (
    EnrollmentDatabase,
    add_enrollment_exemplar,
)
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.speaker_embedding import (
    SpeakerEmbeddingContext,
    build_speaker_embedding_from_config,
    is_l2_normalized,
)
from app.inference_pipeline.speaker_matching import build_speaker_matcher_from_config
from app.inference_pipeline.vad import build_vad_from_config


CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
COMPONENT_ROOT = CONFIG_ROOT / "components"
BASE_CONFIG_PATH = CONFIG_ROOT / "base.yaml"
DEFAULT_OUTPUT = TOOL_ROOT / "runs" / "component_qualification" / "qualification.json"

# A hard safety boundary: only these Whisper checkpoint sizes can ever be
# discovered by this harness. Faster-Whisper is separately constrained by its
# adapter/config validation to the same set.
ALLOWED_WHISPER_SIZES = frozenset({"tiny", "base", "small"})
FORBIDDEN_WHISPER_MARKERS = ("medium", "large", "turbo")


@dataclass(frozen=True)
class QualificationResult:
    result_id: str
    family: str
    component: str
    status: str
    duration_sec: float
    details: dict[str, object]
    reason: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify configured speech backends with real local inference and "
            "small end-to-end interoperability smokes."
        )
    )
    parser.add_argument(
        "--audio",
        type=Path,
        default=None,
        help="Speech WAV used for qualification (auto-detected after model bootstrap).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON result path.",
    )
    parser.add_argument(
        "--family",
        action="append",
        choices=["vad", "asr", "diarization", "speaker"],
        help="Limit to one or more families; omit to run all.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when any configured backend is not qualified.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    audio_path = _resolve_audio_path(args.audio)
    output_path = _resolve_output_path(args.output)
    families = set(args.family or ("vad", "asr", "diarization", "speaker"))
    results: list[QualificationResult] = []

    record = _record_for_audio(audio_path)
    loaded_audio = load_audio(record, {"runtime": {"sample_rate_hz": 16000}})

    if "vad" in families:
        for fragment_path in _component_fragments("vad"):
            results.append(
                _run_result(
                    result_id=f"vad:{fragment_path.stem}",
                    family="vad",
                    component=fragment_path.stem,
                    operation=lambda path=fragment_path: _qualify_vad(
                        path, record, loaded_audio
                    ),
                )
            )

    if "asr" in families:
        for fragment_path in _component_fragments("asr"):
            fragment = _read_component_fragment(fragment_path)
            _assert_permitted_asr(fragment, fragment_path)
            results.append(
                _run_result(
                    result_id=f"asr:{fragment_path.stem}",
                    family="asr",
                    component=str(fragment["name"]),
                    operation=lambda item=fragment: _qualify_asr(item, record),
                )
            )

    if "diarization" in families:
        for fragment_path in _component_fragments("diarization"):
            results.append(
                _run_result(
                    result_id=f"diarization:{fragment_path.stem}",
                    family="diarization",
                    component=fragment_path.stem,
                    operation=lambda path=fragment_path: _qualify_diarization(
                        path, record, loaded_audio
                    ),
                )
            )

    if "speaker" in families:
        for fragment_path in _component_fragments("speaker_embedding"):
            results.append(
                _run_result(
                    result_id=f"speaker:{fragment_path.stem}+cosine_threshold",
                    family="speaker",
                    component=fragment_path.stem,
                    operation=lambda path=fragment_path: _qualify_speaker_path(
                        path, record
                    ),
                )
            )

    payload = {
        "schema_version": "speech-component-qualification.v1",
        "audio_path": _portable_path(audio_path),
        "audio_sha256": _sha256(audio_path),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "picovoice_access_key_present": bool(os.getenv("PICOVOICE_ACCESS_KEY")),
            "pyannote_token_present": bool(
                os.getenv("PYANNOTE_AUTH_TOKEN") or os.getenv("HF_TOKEN")
            ),
        },
        "summary": _summary(results),
        "results": [asdict(result) for result in results],
    }
    _atomic_write_json(output_path, payload)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(f"Qualification report: {output_path}")

    if any(result.status == "failed" for result in results):
        return 1
    if args.strict and any(result.status != "qualified" for result in results):
        return 2
    return 0


def _qualify_vad(
    fragment_path: Path,
    record: Mapping[str, object],
    loaded_audio: object,
) -> dict[str, object]:
    fragment = _read_component_fragment(fragment_path)
    config = _config_with_components(vad=fragment)
    detector = build_vad_from_config(config)
    if detector is None:
        raise RuntimeError("configured VAD did not build")
    regions = tuple(detector.detect(loaded_audio))
    if not regions:
        raise RuntimeError("VAD loaded but found no speech in qualification audio")

    combo_config = _config_with_components(
        vad=fragment,
        segmentation=_read_component_fragment(
            COMPONENT_ROOT / "segmentation" / "vad_chunks.yaml"
        ),
        asr=_reference_asr_fragment(),
    )
    runner = PipelineRunner.from_config(combo_config)
    runner.vad = detector
    output = runner.predict(record, _run_config())
    segment_count = len((output.diagnostics or {}).get("segments", ()))
    if output.errors or segment_count < 1:
        raise RuntimeError(
            "VAD + VADChunker + reference ASR did not produce valid segments"
        )
    return {
        "speech_region_count": len(regions),
        "segment_count": segment_count,
        # Empty text is a measurable ASR/segmentation quality outcome, not a
        # component contract failure, provided valid chunks reached the ASR.
        "transcript_nonempty": bool(output.text.strip()),
        "combination": f"{fragment['name']} + vad_chunks + {_reference_asr_fragment()['name']}",
    }


def _qualify_asr(
    fragment: Mapping[str, object],
    record: Mapping[str, object],
) -> dict[str, object]:
    config = _config_with_components(asr=fragment)
    adapter = build_asr_from_config(config)
    if adapter is None:
        raise RuntimeError("configured ASR did not build")
    runner = PipelineRunner.from_config(config)
    runner.asr = adapter
    output = runner.predict(record, _run_config())
    if output.errors or not output.text.strip():
        raise RuntimeError("ASR produced no usable transcript")
    prediction = output.to_utterance_prediction_row()
    if prediction["recording_id"] != record["recording_id"]:
        raise RuntimeError("ASR pipeline changed recording identity")
    if prediction["utt_id"] != record["utt_id"]:
        raise RuntimeError("ASR pipeline changed utterance identity")
    return {
        "text": output.text,
        "word_count": len(output.text.split()),
        "full_record_segmentation": True,
        "prediction_schema_valid": True,
    }


def _qualify_diarization(
    fragment_path: Path,
    record: Mapping[str, object],
    loaded_audio: object,
) -> dict[str, object]:
    fragment = _read_component_fragment(fragment_path)
    config = _config_with_components(diarization=fragment)
    diarizer = build_diarizer_from_config(config)
    if diarizer is None:
        raise RuntimeError("configured diarizer did not build")
    turns = tuple(diarizer.diarize(loaded_audio))
    if not turns:
        raise RuntimeError("diarizer loaded but emitted no turns")

    combo_config = _config_with_components(
        diarization=fragment,
        segmentation=_read_component_fragment(
            COMPONENT_ROOT / "segmentation" / "vad_chunks.yaml"
        ),
        asr=_reference_asr_fragment(),
    )
    runner = PipelineRunner.from_config(combo_config)
    runner.diarizer = diarizer
    output = runner.predict(record, _run_config())
    diagnostics = output.diagnostics or {}
    diagnostic_turns = diagnostics.get("diarization_turns", ())
    items = diagnostics.get("segment_predictions", ())
    if output.errors or not output.text.strip() or len(diagnostic_turns) < 1:
        raise RuntimeError("diarization + segmentation + ASR composition failed")
    if not any(
        isinstance(item, Mapping) and item.get("speaker_decision") for item in items
    ):
        raise RuntimeError(
            "diarization labels were not propagated to transcript segments"
        )
    return {
        "turn_count": len(turns),
        "speaker_labels": sorted({turn.speaker_turn_label for turn in turns}),
        "transcript_nonempty": True,
        "speaker_labels_propagated": True,
        "combination": f"{fragment['name']} + vad_chunks + {_reference_asr_fragment()['name']}",
    }


def _qualify_speaker_path(
    fragment_path: Path,
    record: Mapping[str, object],
) -> dict[str, object]:
    fragment = _read_component_fragment(fragment_path)
    matcher_fragment = _read_component_fragment(
        COMPONENT_ROOT / "speaker_matching" / "cosine_threshold.yaml"
    )
    model_id = str((fragment.get("params") or {}).get("model_name") or fragment["name"])
    matcher_fragment = deepcopy(matcher_fragment)
    matcher_params = dict(matcher_fragment.get("params") or {})
    matcher_params["runtime_model_id"] = model_id
    matcher_fragment["params"] = matcher_params
    config = _config_with_components(
        asr=_reference_asr_fragment(),
        speaker_embedding=fragment,
        speaker_matching=matcher_fragment,
    )
    embedder = build_speaker_embedding_from_config(config)
    matcher = build_speaker_matcher_from_config(config)
    if embedder is None or matcher is None:
        raise RuntimeError("speaker embedding or matcher did not build")

    segment = _audio_segment(record)
    context = SpeakerEmbeddingContext(
        recording_id=str(record["recording_id"]),
        utt_id=str(record["utt_id"]),
        source_audio_path=Path(str(record["inference_audio_path"])),
        segment_index=0,
        device="cpu",
        dtype="float32",
        run_config={"project_root": str(TOOL_ROOT.parent)},
    )
    embedding = embedder.embed(segment, context)
    if embedding.status != "ok" or not embedding.vector:
        raise RuntimeError(f"embedding status is {embedding.status!r}")
    if not is_l2_normalized(embedding.vector):
        raise RuntimeError("embedding is not L2 normalized")

    database, _ = add_enrollment_exemplar(
        EnrollmentDatabase.empty(created_at="2026-01-01T00:00:00Z"),
        display_name="Qualification",
        prompt_id="component_qualification",
        audio_path=Path(str(record["inference_audio_path"])),
        embedding=embedding.vector,
        model_id=model_id,
        duration_sec=embedding.segment_duration_sec,
    )
    decision = matcher.match(embedding, database)
    if not decision.accepted or decision.speaker_label != "Qualification":
        raise RuntimeError(
            f"cosine matcher rejected identical enrollment/query: {decision.notes}"
        )

    runner = PipelineRunner.from_config(config)
    runner.speaker_embedding = embedder
    runner.speaker_matcher = matcher
    runner.enrollment_db = database
    output = runner.predict(record, _run_config())
    if (
        output.errors
        or not output.text.strip()
        or output.speaker_label != "Qualification"
    ):
        raise RuntimeError("embedding + cosine matcher + ASR composition failed")
    return {
        "dimension": len(embedding.vector),
        "l2_normalized": True,
        "matcher_accepted_identical_query": True,
        "transcript_speaker_label": output.speaker_label,
        "combination": f"{fragment['name']} + cosine_threshold + {_reference_asr_fragment()['name']}",
    }


def _run_result(
    *,
    result_id: str,
    family: str,
    component: str,
    operation: Callable[[], dict[str, object]],
) -> QualificationResult:
    started = time.perf_counter()
    try:
        details = operation()
    except Exception as exc:  # every backend boundary must be recorded independently
        status = "unavailable" if _is_availability_error(exc) else "failed"
        result = QualificationResult(
            result_id=result_id,
            family=family,
            component=component,
            status=status,
            duration_sec=round(time.perf_counter() - started, 6),
            details={},
            reason=f"{type(exc).__name__}: {exc}",
        )
    else:
        result = QualificationResult(
            result_id=result_id,
            family=family,
            component=component,
            status="qualified",
            duration_sec=round(time.perf_counter() - started, 6),
            details=details,
        )
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    print(f"[{result.status.upper()}] {result.result_id}")
    if result.reason:
        print(f"  {result.reason}")
    return result


def _config_with_components(**overrides: Mapping[str, object]) -> PipelineConfig:
    mapping = PipelineConfig.from_yaml_path(BASE_CONFIG_PATH).to_jsonable()
    mapping["config_name"] = "component_qualification"
    mapping["profile"] = "local_component_qualification"
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


def _read_component_fragment(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    component = data.get("component", data)
    if not isinstance(component, Mapping):
        raise ValueError(f"component fragment is not a mapping: {path}")
    return {str(key): value for key, value in component.items()}


def _component_fragments(slot: str) -> tuple[Path, ...]:
    folder = COMPONENT_ROOT / slot
    paths = tuple(sorted(folder.glob("*.yaml"), key=lambda path: path.name))
    if not paths:
        raise FileNotFoundError(f"no component fragments found for {slot}: {folder}")
    return paths


def _reference_asr_fragment() -> dict[str, object]:
    candidate = COMPONENT_ROOT / "asr" / "whisper_base.yaml"
    if candidate.is_file():
        fragment = _read_component_fragment(candidate)
        _assert_permitted_asr(fragment, candidate)
        return fragment
    raise FileNotFoundError("Whisper Base reference ASR component is not configured")


def _assert_permitted_asr(component: Mapping[str, object], path: Path) -> None:
    name = str(component.get("name") or "").lower()
    params = component.get("params") or {}
    if not isinstance(params, Mapping):
        raise ValueError(f"ASR params must be a mapping: {path}")
    model_size = str(params.get("model_size") or "").lower()
    combined = f"{name} {model_size} {path.name.lower()}"
    is_whisper = name.startswith("whisper_") or name == "faster_whisper"
    if is_whisper and any(marker in combined for marker in FORBIDDEN_WHISPER_MARKERS):
        raise RuntimeError(
            f"prohibited Whisper model found in runnable ASR catalog: {path}"
        )
    if name.startswith("whisper_") and model_size not in ALLOWED_WHISPER_SIZES:
        raise RuntimeError(f"Whisper size is not permitted: {model_size!r}")
    if name == "faster_whisper" and model_size not in ALLOWED_WHISPER_SIZES:
        raise RuntimeError(f"Faster-Whisper size is not permitted: {model_size!r}")


def _record_for_audio(path: Path) -> dict[str, object]:
    info = sf.info(path)
    duration_sec = int(info.frames) / int(info.samplerate)
    return {
        "recording_id": "component-qualification",
        "utt_id": "component-qualification-0001",
        "inference_audio_path": str(path),
        "audio_path_resolved": str(path),
        "start_sec": 0.0,
        "end_sec": duration_sec,
        "duration_sec": duration_sec,
        "sample_rate_hz": int(info.samplerate),
        "channel_count": int(info.channels),
    }


def _audio_segment(record: Mapping[str, object]) -> AudioSegment:
    return AudioSegment(
        audio_path=Path(str(record["inference_audio_path"])),
        start_sec=float(record["start_sec"]),
        end_sec=float(record["end_sec"]),
        duration_sec=float(record["duration_sec"]),
        sample_rate_hz=int(record["sample_rate_hz"]),
        channel_count=int(record["channel_count"]),
        is_mono=int(record["channel_count"]) == 1,
    )


def _run_config() -> dict[str, object]:
    return {
        "project_root": str(TOOL_ROOT.parent),
        "runtime": {"precision": "float32", "sample_rate_hz": 16000},
        "asr": {"language": "en"},
    }


def _resolve_audio_path(value: Path | None) -> Path:
    if value is not None:
        candidate = value.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"qualification audio does not exist: {candidate}")
        return candidate
    candidates = (
        REPO_ROOT / "models/cache/sherpa_onnx/asr/"
        "sherpa-onnx-streaming-zipformer-en-2023-06-26/test_wavs/0.wav",
        TOOL_ROOT / "tests/fixtures/audio/component_qualification.wav",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "no qualification WAV was found; run scripts/bootstrap_models.py or pass --audio"
    )


def _resolve_output_path(value: Path) -> Path:
    expanded = value.expanduser()
    return expanded if expanded.is_absolute() else TOOL_ROOT / expanded


def _is_availability_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return (
        "unavailable" in name
        or "access key" in message
        or "auth token" in message
        or "authentication token" in message
        or "not installed" in message
        or "downloads are disabled" in message
        or "model assets are not available" in message
        or "supported linux" in message
    )


def _summary(results: list[QualificationResult]) -> dict[str, object]:
    counts = {status: 0 for status in ("qualified", "unavailable", "failed")}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "total": len(results),
        **counts,
        "all_qualified": bool(results) and counts["qualified"] == len(results),
    }


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
