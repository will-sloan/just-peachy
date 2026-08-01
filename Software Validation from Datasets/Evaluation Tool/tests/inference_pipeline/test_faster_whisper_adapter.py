from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from app.inference_pipeline.asr.base import ASRContext, build_asr_from_config
from app.inference_pipeline.asr.faster_whisper_adapter import (
    FasterWhisperASR,
    FasterWhisperASRUnavailableError,
    _download_cache_path,
)
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.registry import resolve_components


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"


def _write_stereo_audio(path: Path) -> Path:
    sample_rate = 8000
    timeline = np.linspace(0.0, 2.0, sample_rate * 2, endpoint=False)
    left = 0.1 * np.sin(2.0 * np.pi * 220.0 * timeline)
    right = 0.2 * np.sin(2.0 * np.pi * 440.0 * timeline)
    sf.write(path, np.column_stack((left, right)).astype(np.float32), sample_rate)
    return path


def _segment(path: Path) -> AudioSegment:
    return AudioSegment(
        audio_path=path,
        start_sec=0.25,
        end_sec=1.25,
        sample_rate_hz=8000,
        channel_index=1,
        channel_count=2,
        duration_sec=1.0,
    )


def _context(path: Path) -> ASRContext:
    return ASRContext(
        recording_id="rec",
        utt_id="utt",
        source_audio_path=path,
        segment_start_sec=0.25,
        segment_end_sec=1.25,
        language="en",
    )


class RecordingFasterWhisperModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def transcribe(self, audio: np.ndarray, **kwargs: object):
        self.calls.append({"audio": audio.copy(), **kwargs})
        words = [
            SimpleNamespace(word=" Hello", start=0.0, end=0.2, probability=0.95),
            SimpleNamespace(word=" world", start=0.3, end=0.6, probability=0.85),
        ]
        segments = iter(
            [
                SimpleNamespace(text=" Hello", words=words[:1]),
                SimpleNamespace(text=" world ", words=words[1:]),
            ]
        )
        return segments, SimpleNamespace(language="en")


def test_faster_whisper_crops_resamples_and_exhausts_segment_generator(
    tmp_path: Path,
) -> None:
    path = _write_stereo_audio(tmp_path / "faster.wav")
    model = RecordingFasterWhisperModel()
    adapter = FasterWhisperASR(
        {
            "model_size": "tiny",
            "device": "cpu",
            "compute_type": "int8",
            "beam_size": 2,
            "word_timestamps": True,
            "vad_filter": False,
        },
        model=model,
    )

    transcript = adapter.transcribe(_segment(path), _context(path))

    assert transcript.text == "hello world"
    assert transcript.language == "en"
    assert transcript.start_sec == pytest.approx(0.25)
    assert transcript.end_sec == pytest.approx(1.25)
    assert [word.word for word in transcript.words] == ["Hello", "world"]
    assert transcript.words[0].start_sec == pytest.approx(0.25)
    assert transcript.words[0].end_sec == pytest.approx(0.45)
    assert transcript.words[1].start_sec == pytest.approx(0.55)
    assert transcript.words[1].end_sec == pytest.approx(0.85)
    assert transcript.words[0].confidence == pytest.approx(0.95)
    assert len(model.calls) == 1
    assert isinstance(model.calls[0]["audio"], np.ndarray)
    assert model.calls[0]["audio"].dtype == np.float32
    assert len(model.calls[0]["audio"]) == 16000
    assert model.calls[0]["beam_size"] == 2
    assert model.calls[0]["vad_filter"] is False
    assert adapter.last_runtime_stats is not None
    assert adapter.last_runtime_stats.audio_duration_sec == pytest.approx(1.0)


def test_faster_whisper_loads_explicit_local_model_in_offline_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "tiny"
    model_path.mkdir()
    for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        (model_path / filename).touch()
    loaded_model = object()
    calls: list[tuple[str, dict[str, object]]] = []

    def factory(source: str, **kwargs: object) -> object:
        calls.append((source, dict(kwargs)))
        return loaded_model

    fake_module = ModuleType("faster_whisper")
    fake_module.WhisperModel = factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    original_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: object() if name == "faster_whisper" else original_find_spec(name),
    )
    adapter = FasterWhisperASR(
        {
            "model_size": "tiny",
            "model_path": str(model_path),
            "allow_model_downloads": False,
        }
    )

    result = adapter._model()

    assert result is loaded_model
    assert calls[0][0] == str(model_path)
    assert calls[0][1]["local_files_only"] is True


def test_faster_whisper_missing_local_model_fails_without_download(
    tmp_path: Path,
) -> None:
    adapter = FasterWhisperASR(
        {
            "model_size": "tiny",
            "model_path": str(tmp_path / "missing" / "tiny"),
            "allow_model_downloads": False,
        }
    )

    with pytest.raises(FasterWhisperASRUnavailableError, match="local model assets"):
        adapter._model()


def test_faster_whisper_rejects_unapproved_model_size_before_loading() -> None:
    with pytest.raises(ContractValidationError, match="not permitted"):
        FasterWhisperASR({"model_size": "unsupported"})


def test_faster_whisper_component_resolves_without_importing_runtime() -> None:
    before_modules = set(sys.modules)
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["asr"] = "components/asr/faster_whisper.yaml"
    config = PipelineConfig.from_mapping(
        mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )

    resolved = resolve_components(config)
    runtime = build_asr_from_config(config)

    assert resolved["asr"].adapter_class.__name__ == "FasterWhisperASRAdapter"
    assert isinstance(runtime, FasterWhisperASR)
    assert "faster_whisper" not in set(sys.modules) - before_modules


def test_faster_whisper_relative_cache_targets_repository_root() -> None:
    cache_dir = Path("models/cache/faster_whisper")

    assert _download_cache_path(cache_dir) == TOOL_ROOT.parent.parent / cache_dir
