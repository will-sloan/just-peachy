from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

import pytest
import torch

from app.inference_pipeline.audio_io import LoadedAudio
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import EvaluationRecord, SpeechRegion
from app.inference_pipeline.dummy_components import DummyASRComponent, DummySpeakerLabeler
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.registry import resolve_components
from app.inference_pipeline.vad.base import FixedVAD, NoOpVAD, build_vad_from_config
from app.inference_pipeline.vad.energy_vad import EnergyVAD
from app.inference_pipeline.vad.report import summarize_vad, write_vad_report
from app.inference_pipeline.vad.silero_vad import SileroVAD, SileroVADUnavailableError


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
SAMPLE_RATE = 1000
LOGGER = logging.getLogger(__name__)


def synthetic_audio(
    duration_sec: float,
    speech_spans: list[tuple[float, float]] | None = None,
    amplitude: float = 0.8,
) -> LoadedAudio:
    samples = max(0, int(round(duration_sec * SAMPLE_RATE)))
    waveform = torch.zeros((1, samples), dtype=torch.float32)
    for start_sec, end_sec in speech_spans or []:
        start = max(0, int(round(start_sec * SAMPLE_RATE)))
        end = min(samples, int(round(end_sec * SAMPLE_RATE)))
        if end > start:
            waveform[0, start:end] = amplitude
    return LoadedAudio(
        waveform=waveform,
        sample_rate=SAMPLE_RATE,
        duration_sec=samples / SAMPLE_RATE,
        num_channels=1,
        channel_policy={"policy": "mono", "source_channels": 1, "output_channels": 1},
        source_sample_rate=SAMPLE_RATE,
        source_num_channels=1,
        source_duration_sec=samples / SAMPLE_RATE,
        segment_start_sec=None,
        segment_end_sec=None,
        audio_path=Path("synthetic.wav"),
    )


def energy_vad(**params: object) -> EnergyVAD:
    defaults: dict[str, object] = {
        "threshold": 0.1,
        "min_speech_ms": 50,
        "min_silence_ms": 50,
        "pad_ms": 0,
        "sample_rate": SAMPLE_RATE,
    }
    defaults.update(params)
    return EnergyVAD(defaults)


def test_energy_vad_silence_returns_no_regions() -> None:
    regions = energy_vad().detect(synthetic_audio(1.0))

    assert regions == []


def test_energy_vad_detects_one_speech_region() -> None:
    regions = energy_vad().detect(synthetic_audio(1.0, [(0.2, 0.6)]))

    assert len(regions) == 1
    region = regions[0]
    assert isinstance(region, SpeechRegion)
    assert region.start_sec == pytest.approx(0.2, abs=0.011)
    assert region.end_sec == pytest.approx(0.6, abs=0.011)
    assert region.end_sec > region.start_sec
    assert region.confidence is not None
    assert 0.0 <= region.confidence <= 1.0


def test_energy_vad_detects_multiple_regions() -> None:
    regions = energy_vad().detect(synthetic_audio(1.0, [(0.1, 0.25), (0.55, 0.8)]))

    assert len(regions) == 2
    assert regions[0].start_sec == pytest.approx(0.1, abs=0.011)
    assert regions[0].end_sec == pytest.approx(0.25, abs=0.011)
    assert regions[1].start_sec == pytest.approx(0.55, abs=0.011)
    assert regions[1].end_sec == pytest.approx(0.8, abs=0.011)
    assert all(region.end_sec > region.start_sec for region in regions)


def test_energy_vad_handles_very_short_audio_safely() -> None:
    regions = energy_vad(min_speech_ms=20).detect(synthetic_audio(0.005, [(0.0, 0.005)]))

    assert regions == []


def test_energy_vad_padding_and_short_silence_merge_regions() -> None:
    regions = energy_vad(min_silence_ms=120, pad_ms=20).detect(
        synthetic_audio(1.0, [(0.2, 0.3), (0.36, 0.5)])
    )

    assert len(regions) == 1
    assert regions[0].start_sec == pytest.approx(0.18, abs=0.011)
    assert regions[0].end_sec == pytest.approx(0.52, abs=0.011)


def test_fixed_vad_is_deterministic_test_adapter() -> None:
    expected = [SpeechRegion(start_sec=0.1, end_sec=0.2, confidence=0.9)]
    vad = FixedVAD(expected)

    assert vad.detect(synthetic_audio(0.5)) == expected
    assert vad.detect(synthetic_audio(0.5)) == expected


def test_vad_can_be_selected_by_config() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["vad"] = {
        "name": "energy_vad",
        "enabled": True,
        "adapter": "EnergyVADAdapter",
        "params": {
            "threshold": 0.1,
            "min_speech_ms": 50,
            "min_silence_ms": 50,
            "pad_ms": 0,
            "sample_rate": SAMPLE_RATE,
        },
    }
    config = PipelineConfig.from_mapping(mapping)
    resolved = resolve_components(config)
    vad = build_vad_from_config(config)
    pipeline = PipelineRunner.with_dummy_components(config=config)

    assert resolved["vad"].adapter_class.__name__ == "EnergyVADAdapter"
    assert isinstance(vad, EnergyVAD)
    assert isinstance(pipeline.vad, EnergyVAD)
    assert vad.params.threshold == 0.1


def test_silero_vad_can_be_selected_by_config_without_eager_model_load() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["vad"] = {
        "name": "silero_vad",
        "enabled": True,
        "adapter": "SileroVADAdapter",
        "params": {
            "threshold": 0.5,
            "min_speech_ms": 100,
            "min_silence_ms": 100,
            "pad_ms": 30,
            "sample_rate": SAMPLE_RATE,
        },
    }
    config = PipelineConfig.from_mapping(mapping)
    resolved = resolve_components(config)
    vad = build_vad_from_config(config)

    assert resolved["vad"].adapter_class.__name__ == "SileroVADAdapter"
    assert isinstance(vad, SileroVAD)
    assert vad.model is None


def test_vad_disabled_path_remains_supported() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["vad"]["enabled"] = False
    config = PipelineConfig.from_mapping(mapping)
    resolved = resolve_components(config)

    assert resolved["vad"].adapter_class.__name__ == "DisabledComponentAdapter"
    assert build_vad_from_config(config) is None
    assert NoOpVAD().detect(synthetic_audio(0.5)) == []


def test_silero_vad_maps_timestamps_with_injected_backend() -> None:
    calls: dict[str, object] = {}
    model = object()

    def fake_timestamps(audio, loaded_model, **kwargs):
        calls["sample_count"] = audio.numel()
        calls["model"] = loaded_model
        calls["threshold"] = kwargs["threshold"]
        calls["sampling_rate"] = kwargs["sampling_rate"]
        calls["min_speech_duration_ms"] = kwargs["min_speech_duration_ms"]
        calls["min_silence_duration_ms"] = kwargs["min_silence_duration_ms"]
        calls["speech_pad_ms"] = kwargs["speech_pad_ms"]
        calls["return_seconds"] = kwargs["return_seconds"]
        return [{"start": 0.2, "end": 0.5}]

    vad = SileroVAD(
        {
            "threshold": 0.4,
            "min_speech_ms": 75,
            "min_silence_ms": 60,
            "pad_ms": 20,
            "sample_rate": SAMPLE_RATE,
        },
        model=model,
        timestamp_fn=fake_timestamps,
    )

    regions = vad.detect(synthetic_audio(1.0, [(0.2, 0.5)]))

    assert regions == [
        SpeechRegion(start_sec=0.2, end_sec=0.5, confidence=None, label="speech")
    ]
    assert calls == {
        "sample_count": SAMPLE_RATE,
        "model": model,
        "threshold": 0.4,
        "sampling_rate": SAMPLE_RATE,
        "min_speech_duration_ms": 75,
        "min_silence_duration_ms": 60,
        "speech_pad_ms": 20,
        "return_seconds": True,
    }


def test_silero_vad_loads_packaged_model_when_available() -> None:
    if importlib.util.find_spec("silero_vad") is None:
        pytest.skip("silero_vad package is not installed")

    vad = SileroVAD(
        {
            "threshold": 0.5,
            "min_speech_ms": 100,
            "min_silence_ms": 100,
            "pad_ms": 30,
            "sample_rate": 16000,
        }
    )
    silence = LoadedAudio(
        waveform=torch.zeros((1, 1600), dtype=torch.float32),
        sample_rate=16000,
        duration_sec=0.1,
        num_channels=1,
        channel_policy={"policy": "mono", "source_channels": 1, "output_channels": 1},
        source_sample_rate=16000,
        source_num_channels=1,
        source_duration_sec=0.1,
        segment_start_sec=None,
        segment_end_sec=None,
        audio_path=Path("synthetic_silence.wav"),
    )

    try:
        regions = vad.detect(silence)
    except SileroVADUnavailableError as exc:
        pytest.skip(str(exc))

    assert regions == []
    assert vad.model is not None


class StaticAudioReader:
    def __init__(self, audio: LoadedAudio) -> None:
        self.audio = audio

    def load(self, record: EvaluationRecord, run_config=None) -> LoadedAudio:
        _ = (record, run_config)
        return self.audio


def test_pipeline_runs_with_vad_enabled_and_disabled() -> None:
    record = {
        "recording_id": "rec-001",
        "utt_id": "utt-001",
        "inference_audio_path": "synthetic.wav",
    }
    audio = synthetic_audio(1.0, [(0.25, 0.75)])
    enabled_pipeline = PipelineRunner(
        audio_reader=StaticAudioReader(audio),
        asr=DummyASRComponent(),
        speaker_labeler=DummySpeakerLabeler(),
        vad=energy_vad(),
    )
    disabled_pipeline = PipelineRunner(
        audio_reader=StaticAudioReader(audio),
        asr=DummyASRComponent(),
        speaker_labeler=DummySpeakerLabeler(),
    )

    enabled_output = enabled_pipeline.run_one(record, {}, LOGGER)
    disabled_output = disabled_pipeline.run_one(record, {}, LOGGER)

    assert enabled_output.runtime_stats is not None
    assert enabled_output.runtime_stats.vad_sec is not None
    assert enabled_output.runtime_stats.counters == {"vad_region_count": 1}
    assert disabled_output.runtime_stats is not None
    assert disabled_output.runtime_stats.vad_sec is None
    assert disabled_output.runtime_stats.counters is None
    assert enabled_output.recording_id == "rec-001"
    assert enabled_output.utt_id == "utt-001"


def test_vad_report_metrics_and_writer(tmp_path: Path) -> None:
    predicted = [
        SpeechRegion(start_sec=0.1, end_sec=0.5, confidence=0.8),
        SpeechRegion(start_sec=0.7, end_sec=0.9, confidence=0.8),
    ]
    reference = [SpeechRegion(start_sec=0.0, end_sec=0.5, confidence=1.0)]

    metrics = summarize_vad(
        predicted,
        audio_duration_sec=1.0,
        runtime_sec=0.02,
        reference_regions=reference,
    )
    report_path = write_vad_report(
        tmp_path / "vad_comparison_test.md",
        run_id="test",
        backend_name="energy_vad",
        metrics=metrics,
        files_changed=["app/inference_pipeline/vad/base.py"],
        test_commands=["python -m pytest tests/inference_pipeline/test_vad.py"],
        smoke_command="not run",
        silero_status="not available",
        runner_contract="recording_id and utt_id are preserved.",
        enabled_disabled_status="enabled and disabled paths tested.",
    )

    assert metrics.speech_coverage_ratio == pytest.approx(0.6)
    assert metrics.segment_count_per_minute == pytest.approx(120.0)
    assert metrics.realtime_factor == pytest.approx(0.02)
    assert metrics.missed_speech_rate == pytest.approx(0.2)
    assert metrics.false_speech_rate == pytest.approx(0.4)
    assert metrics.boundary_error_sec == pytest.approx(0.05)
    assert "M5 - VAD Interface and First VAD Adapter" in report_path.read_text(encoding="utf-8")
