from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from app.inference_pipeline.asr.base import ASRContext, build_asr_from_config
from app.inference_pipeline.asr.sherpa_onnx_adapter import (
    SherpaOnnxASR,
    SherpaOnnxLibriGigaZipformer20230621ASR,
)
from app.inference_pipeline.asr.vosk_adapter import VoskASR
from app.inference_pipeline.asr.wenet_adapter import WeNetASR
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import AudioSegment
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


class FakeSherpaStream:
    def __init__(self) -> None:
        self.accepted: list[tuple[int, np.ndarray]] = []
        self.finished = False

    def accept_waveform(self, sample_rate: int, samples: np.ndarray) -> None:
        self.accepted.append((sample_rate, samples.copy()))

    def input_finished(self) -> None:
        self.finished = True


class FakeSherpaRecognizer:
    def __init__(self) -> None:
        self.streams: list[FakeSherpaStream] = []
        self.decode_count = 0

    def create_stream(self) -> FakeSherpaStream:
        stream = FakeSherpaStream()
        self.streams.append(stream)
        return stream

    def is_ready(self, stream: FakeSherpaStream) -> bool:
        assert stream.finished
        return self.decode_count == 0

    def decode_stream(self, stream: FakeSherpaStream) -> None:
        assert stream.finished
        self.decode_count += 1

    def get_result(self, stream: FakeSherpaStream) -> str:
        assert stream.finished
        return "Hello from Sherpa"


def test_sherpa_adapter_crops_resamples_and_decodes(tmp_path: Path) -> None:
    path = _write_stereo_audio(tmp_path / "sherpa.wav")
    recognizer = FakeSherpaRecognizer()
    adapter = SherpaOnnxASR(
        {"sample_rate": 16000, "tail_padding_sec": 0, "language": "en"},
        recognizer=recognizer,
    )

    transcript = adapter.transcribe(_segment(path), _context(path))

    assert transcript.text == "hello from sherpa"
    assert transcript.start_sec == pytest.approx(0.25)
    assert transcript.end_sec == pytest.approx(1.25)
    assert recognizer.decode_count == 1
    assert recognizer.streams[0].finished is True
    sample_rate, samples = recognizer.streams[0].accepted[0]
    assert sample_rate == 16000
    assert len(samples) == 16000
    assert adapter.last_runtime_stats is not None
    assert adapter.last_runtime_stats.audio_duration_sec == pytest.approx(1.0)


def test_libri_giga_sherpa_identity_preserves_segment_contract(tmp_path: Path) -> None:
    path = _write_stereo_audio(tmp_path / "sherpa-libri-giga.wav")
    recognizer = FakeSherpaRecognizer()
    adapter = SherpaOnnxLibriGigaZipformer20230621ASR(
        {"sample_rate": 16000, "tail_padding_sec": 0},
        recognizer=recognizer,
    )

    transcript = adapter.transcribe(_segment(path), _context(path))

    assert adapter.name == "sherpa_onnx_libri_giga_zipformer_2023_06_21"
    assert adapter.native_streaming_replay is False
    assert transcript.text == "hello from sherpa"
    assert recognizer.decode_count == 1


class FakeVoskRecognizer:
    def __init__(self) -> None:
        self.payloads: list[bytes] = []
        self.words_enabled = False
        self.partial_words_enabled = False

    def SetWords(self, value: bool) -> None:
        self.words_enabled = value

    def SetPartialWords(self, value: bool) -> None:
        self.partial_words_enabled = value

    def AcceptWaveform(self, payload: bytes) -> bool:
        self.payloads.append(payload)
        return False

    def FinalResult(self) -> str:
        return json.dumps(
            {
                "text": "Hello from Vosk",
                "result": [
                    {"word": "hello", "start": 0.0, "end": 0.2, "conf": 0.9},
                    {"word": "vosk", "start": 0.3, "end": 0.6, "conf": 0.8},
                ],
            }
        )


def test_vosk_adapter_streams_pcm16_and_preserves_words(tmp_path: Path) -> None:
    path = _write_stereo_audio(tmp_path / "vosk.wav")
    recognizers: list[FakeVoskRecognizer] = []

    def factory(model: object, sample_rate: float) -> FakeVoskRecognizer:
        assert model == "fake-vosk-model"
        assert sample_rate == pytest.approx(16000)
        recognizer = FakeVoskRecognizer()
        recognizers.append(recognizer)
        return recognizer

    adapter = VoskASR(
        {"sample_rate": 16000, "chunk_frames": 4000, "words": True},
        model="fake-vosk-model",
        recognizer_factory=factory,
    )

    transcript = adapter.transcribe(_segment(path), _context(path))

    assert transcript.text == "hello from vosk"
    assert [word.word for word in transcript.words] == ["hello", "vosk"]
    assert transcript.words[0].start_sec == pytest.approx(0.25)
    assert transcript.words[0].end_sec == pytest.approx(0.45)
    assert transcript.words[1].start_sec == pytest.approx(0.55)
    assert transcript.words[1].end_sec == pytest.approx(0.85)
    assert transcript.words[0].confidence == pytest.approx(0.9)
    assert recognizers[0].words_enabled is True
    assert sum(len(payload) for payload in recognizers[0].payloads) == 16000 * 2


class FakeWeNetModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def transcribe(self, audio_path: str) -> SimpleNamespace:
        info = sf.info(audio_path)
        self.calls.append(
            {
                "path_exists": Path(audio_path).is_file(),
                "sample_rate": int(info.samplerate),
                "channels": int(info.channels),
                "frames": int(info.frames),
            }
        )
        return SimpleNamespace(text="Hello from WeNet")


def test_wenet_adapter_uses_temporary_mono_pcm16_wav(tmp_path: Path) -> None:
    path = _write_stereo_audio(tmp_path / "wenet.wav")
    model = FakeWeNetModel()
    adapter = WeNetASR({"sample_rate": 16000}, model=model)

    transcript = adapter.transcribe(_segment(path), _context(path))

    assert transcript.text == "hello from wenet"
    assert model.calls == [
        {
            "path_exists": True,
            "sample_rate": 16000,
            "channels": 1,
            "frames": 16000,
        }
    ]


@pytest.mark.parametrize(
    ("component_file", "adapter_name", "runtime_class", "module_name"),
    (
        ("sherpa_onnx.yaml", "SherpaOnnxASRAdapter", SherpaOnnxASR, "sherpa_onnx"),
        (
            "sherpa_onnx_libri_giga_zipformer_2023_06_21.yaml",
            "SherpaOnnxLibriGigaZipformer20230621ASRAdapter",
            SherpaOnnxLibriGigaZipformer20230621ASR,
            "sherpa_onnx",
        ),
        ("vosk.yaml", "VoskASRAdapter", VoskASR, "vosk"),
        ("wenet.yaml", "WeNetASRAdapter", WeNetASR, "wenet"),
    ),
)
def test_new_asr_component_configs_resolve_without_importing_optional_packages(
    component_file: str,
    adapter_name: str,
    runtime_class: type,
    module_name: str,
) -> None:
    before_modules = set(sys.modules)
    mapping = PipelineConfig.from_yaml_path(
        CONFIG_ROOT / "cpu_smoke.yaml"
    ).to_jsonable()
    mapping["components"]["asr"] = f"components/asr/{component_file}"

    config = PipelineConfig.from_mapping(
        mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )
    resolved = resolve_components(config)
    runtime = build_asr_from_config(config)

    assert resolved["asr"].adapter_class.__name__ == adapter_name
    assert isinstance(runtime, runtime_class)
    assert module_name not in set(sys.modules) - before_modules
