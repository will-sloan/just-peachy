"""Exhaustive offline matrix for the three user-selected component slots.

Heavy model boundaries are replaced with recording fakes here. Backend-specific
tests remain responsible for proving that each external library/model can load;
this module proves that every supported configuration composes and runs through
the real PipelineRunner without downloads, credentials, or accelerator access.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

import numpy as np
import pytest
import soundfile as sf

from app.inference_pipeline.asr.base import NoOpASR
from app.inference_pipeline.asr.faster_whisper_adapter import FasterWhisperASR
from app.inference_pipeline.asr.sherpa_onnx_adapter import SherpaOnnxASR
from app.inference_pipeline.asr.vosk_adapter import VoskASR
from app.inference_pipeline.asr.wenet_adapter import WeNetASR
from app.inference_pipeline.asr.whisper_adapter import WhisperASR
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.diarization.base import NoOpDiarizer
from app.inference_pipeline.diarization.pyannote_adapter import PyannoteCommunityDiarizer
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.registry import REGISTERED_COMPONENTS, resolve_components
from app.inference_pipeline.segmentation.base import NoOpSegmenter
from app.inference_pipeline.segmentation.vad_chunker import VADChunker


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"


@dataclass(frozen=True)
class ComponentCase:
    case_id: str
    component: Mapping[str, object]


def _whisper_component(name: str, model_size: str, adapter: str) -> Mapping[str, object]:
    return {
        "name": name,
        "enabled": True,
        "adapter": adapter,
        "params": {
            "model_family": "whisper",
            "model_size": model_size,
            "model_name": name,
            "language": "en",
            "beam_size": 1,
            "word_timestamps": False,
            "device": "cpu",
            "dtype": "float32",
            "allow_model_downloads": False,
            "cache_dir": "models/cache/whisper",
        },
    }


SEGMENTATION_CASES = (
    ComponentCase(
        "full_window",
        {
            "name": "no_op_segmentation",
            "enabled": False,
            "adapter": "NoOpSegmentationAdapter",
            "params": {"mode": "full_window"},
        },
    ),
    ComponentCase(
        "no_op",
        {
            "name": "no_op_segmentation",
            "enabled": True,
            "adapter": "NoOpSegmentationAdapter",
            "params": {},
        },
    ),
    ComponentCase(
        "vad_chunks",
        {
            "name": "vad_chunks",
            "enabled": True,
            "adapter": "VADChunkerAdapter",
            "params": {
                "target": "asr",
                "min_chunk_sec": 0.1,
                "max_chunk_sec": 5.0,
                "merge_gap_sec": 0.0,
                "left_pad_sec": 0.0,
                "right_pad_sec": 0.0,
                "clip_to_record_bounds": True,
            },
        },
    ),
)


ASR_CASES = (
    ComponentCase(
        "no_op",
        {
            "name": "no_op_asr",
            "enabled": True,
            "adapter": "NoOpASRAdapter",
            "params": {"transcript": "matrix transcript"},
        },
    ),
    ComponentCase(
        "whisper_tiny",
        _whisper_component("whisper_tiny", "tiny", "WhisperTinyASRAdapter"),
    ),
    ComponentCase(
        "whisper_base",
        _whisper_component("whisper_base", "base", "WhisperBaseASRAdapter"),
    ),
    ComponentCase(
        "whisper_small",
        _whisper_component("whisper_small", "small", "WhisperSmallASRAdapter"),
    ),
    ComponentCase(
        "faster_whisper",
        {
            "name": "faster_whisper",
            "enabled": True,
            "adapter": "FasterWhisperASRAdapter",
            "params": {
                "model_size": "tiny",
                "beam_size": 1,
                "word_timestamps": False,
                "device": "cpu",
                "compute_type": "int8",
                "allow_model_downloads": False,
            },
        },
    ),
    ComponentCase(
        "sherpa_onnx",
        {
            "name": "sherpa_onnx",
            "enabled": True,
            "adapter": "SherpaOnnxASRAdapter",
            "params": {"sample_rate": 16000, "tail_padding_sec": 0},
        },
    ),
    ComponentCase(
        "vosk",
        {
            "name": "vosk",
            "enabled": True,
            "adapter": "VoskASRAdapter",
            "params": {"sample_rate": 16000},
        },
    ),
    ComponentCase(
        "wenet",
        {
            "name": "wenet",
            "enabled": True,
            "adapter": "WeNetASRAdapter",
            "params": {"sample_rate": 16000},
        },
    ),
)


DIARIZATION_CASES = (
    ComponentCase(
        "disabled",
        {
            "name": "no_op_diarization",
            "enabled": False,
            "adapter": "NoOpDiarizationAdapter",
            "params": {},
        },
    ),
    ComponentCase(
        "no_op",
        {
            "name": "no_op_diarization",
            "enabled": True,
            "adapter": "NoOpDiarizationAdapter",
            "params": {},
        },
    ),
    ComponentCase(
        "pyannote_community",
        {
            "name": "pyannote_community",
            "enabled": True,
            "adapter": "PyannoteCommunityDiarizer",
            "params": {
                "model_source": "matrix-fake-pyannote",
                "min_turn_sec": 0.05,
                "allow_model_downloads": False,
            },
        },
    ),
)


class RecordingWhisperModel:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.calls: list[dict[str, object]] = []

    def transcribe(self, audio_path: str, **kwargs: object) -> dict[str, object]:
        self.calls.append({"audio_path": audio_path, **kwargs})
        return {"text": f"{self.model_name} matrix transcript"}


class RecordingFasterWhisperModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def transcribe(self, samples: np.ndarray, **kwargs: object):
        self.calls.append({"samples": samples.copy(), **kwargs})
        segments = iter([SimpleNamespace(text="faster whisper matrix transcript", words=None)])
        return segments, SimpleNamespace(language="en")


class MatrixSherpaStream:
    def accept_waveform(self, sample_rate: int, samples: np.ndarray) -> None:
        _ = (sample_rate, samples)

    def input_finished(self) -> None:
        return None


class MatrixSherpaRecognizer:
    def __init__(self) -> None:
        self.decode_count = 0

    def create_stream(self) -> MatrixSherpaStream:
        return MatrixSherpaStream()

    def is_ready(self, stream: MatrixSherpaStream) -> bool:
        _ = stream
        return self.decode_count == 0

    def decode_stream(self, stream: MatrixSherpaStream) -> None:
        _ = stream
        self.decode_count += 1

    def get_result(self, stream: MatrixSherpaStream) -> str:
        _ = stream
        return "sherpa matrix transcript"


class MatrixVoskRecognizer:
    def SetWords(self, value: bool) -> None:
        _ = value

    def SetPartialWords(self, value: bool) -> None:
        _ = value

    def AcceptWaveform(self, payload: bytes) -> bool:
        _ = payload
        return False

    def FinalResult(self) -> str:
        return '{"text": "vosk matrix transcript"}'


class MatrixWeNetModel:
    def transcribe(self, audio_path: str):
        _ = audio_path
        return type("Result", (), {"text": "wenet matrix transcript"})()


class FakeTurn:
    def __init__(self, start: float, end: float) -> None:
        self.start = start
        self.end = end


class FakeAnnotation:
    def itertracks(self, yield_label: bool = False):
        assert yield_label is True
        yield FakeTurn(0.0, 0.8), "track-a", "backend-speaker-a"
        yield FakeTurn(1.0, 1.8), "track-b", "backend-speaker-b"


class RecordingDiarizationPipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []

    def __call__(self, audio_input: object, **kwargs: object) -> FakeAnnotation:
        self.calls.append((audio_input, dict(kwargs)))
        return FakeAnnotation()


def _matrix_config(
    segmentation: ComponentCase,
    asr: ComponentCase,
    diarization: ComponentCase,
) -> PipelineConfig:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["config_name"] = (
        f"matrix_{segmentation.case_id}_{asr.case_id}_{diarization.case_id}"
    )
    mapping["runtime"]["dry_run"] = False
    mapping["components"]["vad"] = {
        "name": "energy_vad",
        "enabled": True,
        "adapter": "EnergyVADAdapter",
        "params": {
            "threshold": 0.01,
            "min_speech_ms": 20,
            "min_silence_ms": 20,
            "pad_ms": 0,
            "sample_rate": 16000,
        },
    }
    mapping["components"]["segmentation"] = deepcopy(dict(segmentation.component))
    mapping["components"]["asr"] = deepcopy(dict(asr.component))
    mapping["components"]["diarization"] = deepcopy(dict(diarization.component))
    return PipelineConfig.from_mapping(mapping)


def _write_tone(path: Path, duration_sec: float = 2.0) -> Path:
    sample_rate = 16000
    timeline = np.linspace(
        0.0,
        duration_sec,
        int(sample_rate * duration_sec),
        endpoint=False,
    )
    waveform = 0.25 * np.sin(2.0 * np.pi * 220.0 * timeline)
    sf.write(path, waveform.astype(np.float32), sample_rate)
    return path


def _expected_segment_count(segmentation_id: str, diarization_id: str) -> int:
    if segmentation_id == "no_op":
        return 0
    if segmentation_id == "full_window":
        return 1
    return 2 if diarization_id == "pyannote_community" else 1


@pytest.mark.parametrize(
    "segmentation",
    SEGMENTATION_CASES,
    ids=lambda case: case.case_id,
)
@pytest.mark.parametrize(
    "asr",
    ASR_CASES,
    ids=lambda case: case.case_id,
)
@pytest.mark.parametrize(
    "diarization",
    DIARIZATION_CASES,
    ids=lambda case: case.case_id,
)
def test_every_runnable_segmentation_asr_diarization_combination(
    tmp_path: Path,
    segmentation: ComponentCase,
    asr: ComponentCase,
    diarization: ComponentCase,
) -> None:
    audio_path = _write_tone(tmp_path / "matrix.wav")
    config = _matrix_config(segmentation, asr, diarization)
    resolved = resolve_components(config)
    pipeline = PipelineRunner.from_config(config)

    whisper_model: RecordingWhisperModel | None = None
    if isinstance(pipeline.asr, WhisperASR):
        whisper_model = RecordingWhisperModel(asr.case_id)
        pipeline.asr.model = whisper_model
    faster_whisper_model: RecordingFasterWhisperModel | None = None
    if isinstance(pipeline.asr, FasterWhisperASR):
        faster_whisper_model = RecordingFasterWhisperModel()
        pipeline.asr.model = faster_whisper_model
    if isinstance(pipeline.asr, SherpaOnnxASR):
        pipeline.asr.recognizer = MatrixSherpaRecognizer()
    if isinstance(pipeline.asr, VoskASR):
        pipeline.asr.model = "matrix-vosk-model"
        pipeline.asr.recognizer_factory = lambda model, sample_rate: MatrixVoskRecognizer()
    if isinstance(pipeline.asr, WeNetASR):
        pipeline.asr.model = MatrixWeNetModel()

    diarization_pipeline: RecordingDiarizationPipeline | None = None
    if isinstance(pipeline.diarizer, PyannoteCommunityDiarizer):
        diarization_pipeline = RecordingDiarizationPipeline()
        pipeline.diarizer.pipeline = diarization_pipeline

    record = {
        "recording_id": "matrix-recording",
        "utt_id": "matrix-utterance",
        "inference_audio_path": str(audio_path),
        "audio_path_resolved": str(audio_path),
        "start_sec": 0.0,
        "end_sec": 2.0,
        "duration_sec": 2.0,
        "sample_rate_hz": 16000,
        "channel_count": 1,
    }
    output = pipeline.predict(
        record,
        {
            "runtime": {"precision": "float32"},
            "asr": {"language": "en"},
        },
    )

    expected_segments = _expected_segment_count(
        segmentation.case_id,
        diarization.case_id,
    )
    expected_turns = 2 if diarization.case_id == "pyannote_community" else 0

    assert set(resolved) == {
        "vad",
        "segmentation",
        "diarization",
        "asr",
        "speaker_embedding",
        "speaker_matching",
    }
    assert output.recording_id == "matrix-recording"
    assert output.utt_id == "matrix-utterance"
    assert output.errors == ()
    assert output.diagnostics is not None
    assert len(output.diagnostics["segments"]) == expected_segments
    assert len(output.diagnostics["diarization_turns"]) == expected_turns
    assert output.runtime_stats is not None
    assert output.runtime_stats.asr_sec is not None

    if segmentation.case_id == "full_window":
        assert pipeline.segmenter is None
    elif segmentation.case_id == "no_op":
        assert isinstance(pipeline.segmenter, NoOpSegmenter)
    else:
        assert isinstance(pipeline.segmenter, VADChunker)

    if diarization.case_id == "disabled":
        assert pipeline.diarizer is None
    elif diarization.case_id == "no_op":
        assert isinstance(pipeline.diarizer, NoOpDiarizer)
    else:
        assert isinstance(pipeline.diarizer, PyannoteCommunityDiarizer)
        assert diarization_pipeline is not None
        assert len(diarization_pipeline.calls) == 1
        assert [
            row["speaker_turn_label"]
            for row in output.diagnostics["diarization_turns"]
        ] == ["speaker_00", "speaker_01"]

    if asr.case_id == "no_op":
        assert isinstance(pipeline.asr, NoOpASR)
    elif asr.case_id.startswith("whisper_"):
        assert isinstance(pipeline.asr, WhisperASR)
        assert pipeline.asr.model_size == asr.component["params"]["model_size"]
        assert whisper_model is not None
        assert len(whisper_model.calls) == expected_segments
        assert all(call["fp16"] is False for call in whisper_model.calls)
        assert all(call["beam_size"] == 1 for call in whisper_model.calls)
    elif asr.case_id == "faster_whisper":
        assert isinstance(pipeline.asr, FasterWhisperASR)
        assert faster_whisper_model is not None
        assert len(faster_whisper_model.calls) == expected_segments
        assert all(call["beam_size"] == 1 for call in faster_whisper_model.calls)
        assert all(call["vad_filter"] is False for call in faster_whisper_model.calls)
    elif asr.case_id == "sherpa_onnx":
        assert isinstance(pipeline.asr, SherpaOnnxASR)
    elif asr.case_id == "vosk":
        assert isinstance(pipeline.asr, VoskASR)
    else:
        assert isinstance(pipeline.asr, WeNetASR)

    if expected_segments == 0:
        assert output.text == ""
    else:
        assert output.text


def test_matrix_explicitly_covers_every_registered_component_name() -> None:
    matrix_segmentation_names = {
        str(case.component["name"])
        for case in SEGMENTATION_CASES
        if bool(case.component["enabled"])
    }
    matrix_asr_names = {str(case.component["name"]) for case in ASR_CASES}
    matrix_diarization_names = {
        str(case.component["name"])
        for case in DIARIZATION_CASES
        if bool(case.component["enabled"])
    }

    assert matrix_segmentation_names <= set(REGISTERED_COMPONENTS["segmentation"])
    assert matrix_asr_names == set(REGISTERED_COMPONENTS["asr"])
    assert matrix_diarization_names <= set(REGISTERED_COMPONENTS["diarization"])


def test_matrix_contains_every_cartesian_combination() -> None:
    assert (
        len(SEGMENTATION_CASES)
        * len(ASR_CASES)
        * len(DIARIZATION_CASES)
        == 72
    )
