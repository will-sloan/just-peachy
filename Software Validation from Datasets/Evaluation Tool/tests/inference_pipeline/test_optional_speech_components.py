from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
import torch

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.diarization import build_diarizer_from_config
from app.inference_pipeline.diarization.falcon_adapter import PicovoiceFalconDiarizer
from app.inference_pipeline.diarization.nemo_adapter import (
    NemoDiarizationUnavailableError,
    NemoDiarizer,
    _read_rttm,
    _resolve_configured_model_assets,
)
from app.inference_pipeline.diarization.sherpa_onnx_adapter import SherpaOnnxDiarizer
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.registry import REGISTERED_COMPONENTS, resolve_components
from app.inference_pipeline.speaker_embedding import (
    SpeakerEmbeddingContext,
    build_speaker_embedding_from_config,
)
from app.inference_pipeline.speaker_embedding.resemblyzer_adapter import (
    ResemblyzerSpeakerEmbeddingAdapter,
)
from app.inference_pipeline.speaker_embedding.sherpa_onnx_adapter import (
    SherpaOnnxSpeakerEmbeddingAdapter,
)
from app.inference_pipeline.speaker_embedding.wespeaker_adapter import (
    WeSpeakerEmbeddingAdapter,
)
from app.inference_pipeline.vad import build_vad_from_config
from app.inference_pipeline.vad.sherpa_onnx_vad import SherpaOnnxVAD
from app.inference_pipeline.vad.webrtc_vad import WebRTCVAD


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"


def _write_wav(path: Path, duration_sec: float = 1.0) -> Path:
    sample_rate = 16000
    time = np.arange(int(duration_sec * sample_rate), dtype=np.float32) / sample_rate
    sf.write(path, 0.2 * np.sin(2 * np.pi * 220 * time), sample_rate)
    return path


def _loaded_audio(path: Path, duration_sec: float = 1.0) -> SimpleNamespace:
    samples, sample_rate = sf.read(path, dtype="float32")
    return SimpleNamespace(
        waveform=torch.as_tensor(samples).unsqueeze(0),
        sample_rate=sample_rate,
        audio_path=path,
        duration_sec=duration_sec,
    )


def _segment_and_context(path: Path) -> tuple[AudioSegment, SpeakerEmbeddingContext]:
    segment = AudioSegment(
        audio_path=path,
        sample_rate_hz=16000,
        channel_count=1,
        duration_sec=1.0,
    )
    context = SpeakerEmbeddingContext(
        recording_id="recording",
        utt_id="utterance",
        source_audio_path=path,
        segment_index=0,
        device="cpu",
        dtype="float32",
    )
    return segment, context


class _FakeWebRTCEngine:
    def __init__(self) -> None:
        self.calls = 0

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        assert frame
        assert sample_rate == 16000
        self.calls += 1
        return 2 <= self.calls <= 12


def test_webrtc_vad_maps_frame_decisions_to_regions(tmp_path: Path) -> None:
    path = _write_wav(tmp_path / "voice.wav")
    detector = WebRTCVAD(
        {"frame_ms": 30, "min_speech_ms": 90, "min_silence_ms": 30},
        engine=_FakeWebRTCEngine(),
    )

    regions = detector.detect(_loaded_audio(path))

    assert len(regions) == 1
    assert regions[0].start_sec == pytest.approx(0.03)
    assert regions[0].end_sec == pytest.approx(0.36)


class _FakeVadSegment:
    start = 1600
    samples = np.zeros(3200, dtype=np.float32)


class _FakeSherpaVad:
    def __init__(self) -> None:
        self._segments = [_FakeVadSegment()]

    def reset(self) -> None:
        self._segments = [_FakeVadSegment()]

    def accept_waveform(self, samples: np.ndarray) -> None:
        assert samples.dtype == np.float32

    def flush(self) -> None:
        pass

    def empty(self) -> bool:
        return not self._segments

    @property
    def front(self) -> _FakeVadSegment:
        return self._segments[0]

    def pop(self) -> None:
        self._segments.pop(0)


def test_sherpa_vad_maps_backend_segments(tmp_path: Path) -> None:
    path = _write_wav(tmp_path / "voice.wav")
    regions = SherpaOnnxVAD(detector=_FakeSherpaVad()).detect(_loaded_audio(path))

    assert len(regions) == 1
    assert regions[0].start_sec == pytest.approx(0.1)
    assert regions[0].end_sec == pytest.approx(0.3)


class _FakeWeSpeaker:
    def extract_embedding_from_pcm(self, pcm: torch.Tensor, sample_rate: int) -> torch.Tensor:
        assert pcm.shape == (1, 16000)
        assert sample_rate == 16000
        return torch.tensor([1.0, 2.0, 2.0])


class _FakeSherpaStream:
    def accept_waveform(self, sample_rate: int, samples: np.ndarray) -> None:
        assert sample_rate == 16000
        assert samples.shape == (16000,)

    def input_finished(self) -> None:
        pass


class _FakeSherpaExtractor:
    def create_stream(self) -> _FakeSherpaStream:
        return _FakeSherpaStream()

    def is_ready(self, stream: _FakeSherpaStream) -> bool:
        return True

    def compute(self, stream: _FakeSherpaStream) -> list[float]:
        return [2.0, 0.0, 0.0]


class _FakeResemblyzer:
    def embed_utterance(self, samples: np.ndarray) -> np.ndarray:
        assert samples.shape == (16000,)
        return np.asarray([0.0, 3.0, 4.0], dtype=np.float32)


@pytest.mark.parametrize(
    ("adapter", "expected"),
    [
        (WeSpeakerEmbeddingAdapter(model=_FakeWeSpeaker()), (1 / 3, 2 / 3, 2 / 3)),
        (SherpaOnnxSpeakerEmbeddingAdapter(extractor=_FakeSherpaExtractor()), (1.0, 0.0, 0.0)),
        (
            ResemblyzerSpeakerEmbeddingAdapter(
                encoder=_FakeResemblyzer(),
                preprocess_fn=lambda samples, source_sr: samples,
            ),
            (0.0, 0.6, 0.8),
        ),
    ],
)
def test_optional_embedding_adapters_normalize_vectors(
    tmp_path: Path, adapter: object, expected: tuple[float, ...]
) -> None:
    path = _write_wav(tmp_path / "voice.wav")
    segment, context = _segment_and_context(path)

    result = adapter.embed(segment, context)

    assert result.status == "ok"
    assert result.vector == pytest.approx(expected)
    assert result.sample_rate_hz == 16000


class _FakeSherpaDiarizer:
    sample_rate = 16000

    def process(self, samples: np.ndarray) -> list[SimpleNamespace]:
        assert samples.shape == (16000,)
        return [
            SimpleNamespace(start=0.0, end=0.6, speaker=0),
            SimpleNamespace(start=0.5, end=1.0, speaker=1),
        ]


class _FakeFalcon:
    sample_rate = 16000

    def process(self, pcm: list[int]) -> list[SimpleNamespace]:
        assert len(pcm) == 16000
        return [SimpleNamespace(start_sec=0.1, end_sec=0.9, speaker_tag=3)]


def test_sherpa_and_falcon_map_anonymous_turns(tmp_path: Path) -> None:
    path = _write_wav(tmp_path / "meeting.wav")
    audio = _loaded_audio(path)

    sherpa_turns = SherpaOnnxDiarizer(diarizer=_FakeSherpaDiarizer()).diarize(audio)
    falcon_turns = PicovoiceFalconDiarizer(engine=_FakeFalcon()).diarize(audio)

    assert [turn.speaker_turn_label for turn in sherpa_turns] == [
        "speaker_00",
        "speaker_01",
    ]
    assert all(turn.is_overlap for turn in sherpa_turns)
    assert falcon_turns[0].speaker_turn_label == "speaker_03"


def test_backends_reject_unsupported_speaker_count_constraints() -> None:
    with pytest.raises(ValueError, match="exact"):
        SherpaOnnxDiarizer({"min_speakers": 1, "max_speakers": 2})
    with pytest.raises(ValueError, match="does not expose"):
        PicovoiceFalconDiarizer({"max_speakers": 2})
    with pytest.raises(ValueError, match="only when it equals"):
        NemoDiarizer({"min_speakers": 1, "max_speakers": 2})


def test_nemo_rttm_output_maps_to_pipeline_turns(tmp_path: Path) -> None:
    rttm = tmp_path / "meeting.rttm"
    rttm.write_text(
        "SPEAKER meeting 1 0.200 0.600 <NA> <NA> speaker_4 <NA> <NA>\n",
        encoding="utf-8",
    )

    turns = _read_rttm(rttm, min_turn_sec=0.05)

    assert len(turns) == 1
    assert turns[0].start_sec == pytest.approx(0.2)
    assert turns[0].end_sec == pytest.approx(0.8)
    assert turns[0].speaker_turn_label == "speaker_4"


def test_nemo_materializes_only_the_loaded_record_audio(tmp_path: Path) -> None:
    source_path = _write_wav(tmp_path / "long_meeting.wav", duration_sec=3.0)
    config_path = tmp_path / "nemo.yaml"
    config_path.write_text("name: ClusterDiarizer\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeNemoRuntime:
        def __init__(self, out_dir: Path) -> None:
            self.out_dir = out_dir

        def diarize(self) -> None:
            rttm_dir = self.out_dir / "pred_rttms"
            rttm_dir.mkdir(parents=True)
            (rttm_dir / "record_audio.rttm").write_text(
                "SPEAKER record_audio 1 0.100 0.500 <NA> <NA> speaker_0 <NA> <NA>\n",
                encoding="utf-8",
            )

    def factory(config: Path, manifest: Path, out_dir: Path) -> FakeNemoRuntime:
        captured["config"] = config
        row = json.loads(manifest.read_text(encoding="utf-8"))
        captured["manifest"] = row
        captured["duration"] = float(sf.info(row["audio_filepath"]).duration)
        captured["is_source"] = Path(row["audio_filepath"]) == source_path
        return FakeNemoRuntime(out_dir)

    audio = SimpleNamespace(
        audio_path=source_path,
        waveform=torch.zeros(1, 16000),
        sample_rate=16000,
        segment_start_sec=1.0,
        segment_end_sec=2.0,
    )
    diarizer = NemoDiarizer(
        {
            "model_source": "nemo-local-test",
            "config_path": str(config_path),
            "allow_model_downloads": False,
        },
        diarizer_factory=factory,
    )

    result = diarizer.diarize(audio)

    assert captured["duration"] == pytest.approx(1.0)
    assert captured["is_source"] is False
    assert captured["manifest"]["offset"] == 0.0
    assert captured["manifest"]["duration"] == pytest.approx(1.0)
    assert result[0].start_sec == pytest.approx(0.1)
    assert result[0].end_sec == pytest.approx(0.6)


def test_nemo_rejects_implicit_pretrained_model_downloads() -> None:
    config = {
        "name": "ClusterDiarizer",
        "diarizer": {
            "oracle_vad": False,
            "vad": {
                "model_path": "vad_multilingual_marblenet",
                "external_vad_manifest": None,
            },
            "speaker_embeddings": {"model_path": "titanet_large"},
            "asr": {"parameters": {"asr_based_vad": False}},
        },
    }

    class FakeOmegaConf:
        @staticmethod
        def update(config, key, value, merge=False):
            raise AssertionError("remote model names must not be rewritten as local paths")

    with pytest.raises(NemoDiarizationUnavailableError, match="downloads are disabled"):
        _resolve_configured_model_assets(
            config,
            allow_model_downloads=False,
            omega_conf=FakeOmegaConf,
        )


@pytest.mark.parametrize(
    ("slot", "fragment", "expected_type"),
    [
        ("vad", "components/vad/webrtc.yaml", WebRTCVAD),
        ("vad", "components/vad/sherpa_onnx.yaml", SherpaOnnxVAD),
        (
            "speaker_embedding",
            "components/speaker_embedding/wespeaker.yaml",
            WeSpeakerEmbeddingAdapter,
        ),
        (
            "speaker_embedding",
            "components/speaker_embedding/sherpa_onnx.yaml",
            SherpaOnnxSpeakerEmbeddingAdapter,
        ),
        (
            "speaker_embedding",
            "components/speaker_embedding/resemblyzer.yaml",
            ResemblyzerSpeakerEmbeddingAdapter,
        ),
        (
            "diarization",
            "components/diarization/sherpa_onnx.yaml",
            SherpaOnnxDiarizer,
        ),
        (
            "diarization",
            "components/diarization/picovoice_falcon.yaml",
            PicovoiceFalconDiarizer,
        ),
        (
            "diarization",
            "components/diarization/nemo_diarization.yaml",
            NemoDiarizer,
        ),
    ],
)
def test_component_fragments_resolve_and_build(
    slot: str, fragment: str, expected_type: type
) -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"][slot] = fragment
    config = PipelineConfig.from_mapping(
        mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )

    resolved = resolve_components(config)
    if slot == "vad":
        built = build_vad_from_config(config)
    elif slot == "speaker_embedding":
        built = build_speaker_embedding_from_config(config)
    else:
        built = build_diarizer_from_config(config)

    assert resolved[slot].name in REGISTERED_COMPONENTS[slot]
    assert isinstance(built, expected_type)


def test_simple_speaker_change_profile_loads_without_running_evaluation() -> None:
    config = PipelineConfig.from_yaml_path(
        CONFIG_ROOT / "simple_vad_speaker_change_enrollment.yaml"
    )

    assert config.components["vad"].name == "silero_vad"
    assert config.components["segmentation"].name == "vad_chunks"
    assert config.components["diarization"].enabled is False
    assert config.components["speaker_matching"].name == "cosine_threshold"
    temporal = config.components["speaker_matching"].params["temporal_evidence"]
    assert temporal == {
        "enabled": True,
        "confirmation_windows": 3,
        "confirmation_threshold": 2,
        "score_threshold": 0.70,
        "unknown_label": "Unknown",
    }
    pipeline = PipelineRunner.from_config(config)
    assert pipeline.speaker_evidence_params == temporal


@pytest.mark.parametrize(
    "temporal_evidence",
    [
        {"enabled": "yes"},
        {"confirmation_windows": 1.5},
        {"confirmation_windows": 1, "confirmation_threshold": 2},
        {"score_threshold": float("nan")},
        {"unknown_label": "  "},
        {"typo_confirmation_windows": 3},
    ],
)
def test_speaker_temporal_evidence_config_is_validated(
    temporal_evidence: dict[str, object],
) -> None:
    mapping = PipelineConfig.from_yaml_path(
        CONFIG_ROOT / "simple_vad_speaker_change_enrollment.yaml"
    ).to_jsonable()
    mapping["components"]["speaker_matching"]["params"][
        "temporal_evidence"
    ] = temporal_evidence
    config = PipelineConfig.from_mapping(
        mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )

    with pytest.raises(ContractValidationError, match="temporal_evidence"):
        PipelineRunner.from_config(config)
