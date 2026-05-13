from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import torch

from app.inference_pipeline.audio_io import LoadedAudio, load_audio
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.errors import ContractValidationError, MissingRequiredFieldError


TOOL_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = TOOL_ROOT / "tests" / "fixtures" / "audio"
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
SOURCE_SAMPLE_RATE = 8000


@pytest.fixture(scope="module")
def audio_fixtures() -> dict[str, object]:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    samples = SOURCE_SAMPLE_RATE
    left = np.linspace(-0.5, 0.5, samples, endpoint=False, dtype=np.float32)
    right = np.linspace(0.5, -0.5, samples, endpoint=False, dtype=np.float32)
    mono = np.full(samples, 0.25, dtype=np.float32)

    stereo_path = FIXTURE_DIR / "m3_stereo_8k.wav"
    mono_path = FIXTURE_DIR / "m3_mono_8k.wav"
    alternate_path = FIXTURE_DIR / "m3_alternate_8k.wav"
    generated_paths = (stereo_path, mono_path, alternate_path)

    sf.write(stereo_path, np.stack([left, right], axis=1), SOURCE_SAMPLE_RATE, subtype="FLOAT")
    sf.write(mono_path, mono, SOURCE_SAMPLE_RATE, subtype="FLOAT")
    sf.write(alternate_path, np.zeros(samples // 2, dtype=np.float32), SOURCE_SAMPLE_RATE, subtype="FLOAT")

    yield {
        "stereo_path": stereo_path,
        "mono_path": mono_path,
        "alternate_path": alternate_path,
        "left": left,
        "right": right,
        "mono": mono,
    }

    for path in generated_paths:
        path.unlink(missing_ok=True)


def base_record(path: Path) -> dict[str, object]:
    return {
        "recording_id": "ami-session-001",
        "utt_id": "ami-session-001_0001",
        "inference_audio_path": str(path),
        "speaker_label": "speaker-a",
    }


def test_load_audio_full_file_defaults_to_16khz_mono(audio_fixtures: dict[str, object]) -> None:
    result = load_audio(base_record(audio_fixtures["stereo_path"]), {})

    assert isinstance(result, LoadedAudio)
    assert isinstance(result.waveform, torch.Tensor)
    assert result.sample_rate == 16000
    assert result.waveform.shape == (1, 16000)
    assert result.num_channels == 1
    assert result.source_sample_rate == SOURCE_SAMPLE_RATE
    assert result.source_num_channels == 2
    assert result.channel_policy == {
        "policy": "mono",
        "source_channels": 2,
        "output_channels": 1,
    }
    assert result.duration_sec == pytest.approx(1.0, abs=0.001)


def test_load_audio_segment_crops_ami_style_row(audio_fixtures: dict[str, object]) -> None:
    record = base_record(audio_fixtures["stereo_path"])
    record.update(
        {
            "recording_id": "AMI_ES2002a",
            "utt_id": "AMI_ES2002a_000450_000950",
            "start_sec": 0.25,
            "end_sec": 0.75,
        }
    )

    result = load_audio(record, {"runtime": {"sample_rate_hz": 16000}})

    assert result.sample_rate == 16000
    assert result.waveform.shape == (1, 8000)
    assert result.duration_sec == pytest.approx(0.5, abs=0.001)
    assert result.segment_start_sec == 0.25
    assert result.segment_end_sec == 0.75


def test_load_audio_requires_inference_audio_path(audio_fixtures: dict[str, object]) -> None:
    record = {
        "recording_id": "rec-001",
        "utt_id": "utt-001",
        "audio_path_resolved": str(audio_fixtures["stereo_path"]),
    }

    with pytest.raises(MissingRequiredFieldError, match="inference_audio_path"):
        load_audio(record, {})


def test_load_audio_reports_missing_file() -> None:
    record = base_record(FIXTURE_DIR / "does_not_exist.wav")

    with pytest.raises(FileNotFoundError, match="inference_audio_path"):
        load_audio(record, {})


@pytest.mark.parametrize(
    ("start_sec", "end_sec"),
    [
        (-0.1, 0.5),
        (0.5, 0.5),
        (0.75, 0.5),
        ("not-a-number", 0.5),
        (0.5, "not-a-number"),
        (0.9, 1.2),
    ],
)
def test_load_audio_rejects_invalid_timestamps(
    audio_fixtures: dict[str, object],
    start_sec: object,
    end_sec: object,
) -> None:
    record = base_record(audio_fixtures["stereo_path"])
    record.update({"start_sec": start_sec, "end_sec": end_sec})

    with pytest.raises(ContractValidationError):
        load_audio(record, {})


def test_load_audio_selects_configured_channel(audio_fixtures: dict[str, object]) -> None:
    result = load_audio(
        base_record(audio_fixtures["stereo_path"]),
        {
            "runtime": {"sample_rate_hz": SOURCE_SAMPLE_RATE},
            "audio": {"channel_policy": "select", "channel_index": 1},
        },
    )

    assert result.sample_rate == SOURCE_SAMPLE_RATE
    assert result.waveform.shape == (1, SOURCE_SAMPLE_RATE)
    expected = torch.from_numpy(audio_fixtures["right"])
    other_channel = torch.from_numpy(audio_fixtures["left"])
    assert torch.allclose(result.waveform[0], expected, atol=1e-6)
    assert not torch.allclose(result.waveform[0], other_channel, atol=1e-6)
    assert result.channel_policy == {
        "policy": "select",
        "channel_index": 1,
        "source_channels": 2,
        "output_channels": 1,
    }


def test_load_audio_preserves_all_channels(audio_fixtures: dict[str, object]) -> None:
    result = load_audio(
        base_record(audio_fixtures["stereo_path"]),
        {
            "runtime": {"sample_rate_hz": SOURCE_SAMPLE_RATE},
            "audio": {"channel_policy": "preserve"},
        },
    )

    assert result.waveform.shape == (2, SOURCE_SAMPLE_RATE)
    assert result.num_channels == 2
    assert torch.allclose(result.waveform[0], torch.from_numpy(audio_fixtures["left"]), atol=1e-6)
    assert torch.allclose(result.waveform[1], torch.from_numpy(audio_fixtures["right"]), atol=1e-6)
    assert result.channel_policy == {
        "policy": "preserve",
        "source_channels": 2,
        "output_channels": 2,
    }


def test_load_audio_resamples_to_configured_target(audio_fixtures: dict[str, object]) -> None:
    result = load_audio(
        base_record(audio_fixtures["mono_path"]),
        {
            "runtime": {"sample_rate_hz": 12000},
            "audio": {"channel_policy": "mono"},
        },
    )

    assert result.sample_rate == 12000
    assert result.waveform.shape == (1, 12000)
    assert result.duration_sec == pytest.approx(1.0, abs=0.001)


def test_load_audio_uses_inference_path_over_audio_path_resolved(
    audio_fixtures: dict[str, object],
) -> None:
    record = base_record(audio_fixtures["mono_path"])
    record["audio_path_resolved"] = str(FIXTURE_DIR / "missing_source_should_not_be_used.wav")

    result = load_audio(record, {"runtime": {"sample_rate_hz": SOURCE_SAMPLE_RATE}})

    assert result.audio_path == audio_fixtures["mono_path"]
    assert result.waveform.shape == (1, SOURCE_SAMPLE_RATE)


def test_load_audio_accepts_pipeline_config_runtime_sample_rate(
    audio_fixtures: dict[str, object],
) -> None:
    config = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml")

    result = load_audio(base_record(audio_fixtures["mono_path"]), config)

    assert result.sample_rate == config.runtime.sample_rate_hz
    assert result.waveform.shape == (1, config.runtime.sample_rate_hz)


def test_load_audio_rejects_invalid_channel_policy(audio_fixtures: dict[str, object]) -> None:
    with pytest.raises(ContractValidationError, match="unsupported channel_policy"):
        load_audio(
            base_record(audio_fixtures["stereo_path"]),
            {"audio": {"channel_policy": "front-left-plus-vibes"}},
        )


def test_load_audio_rejects_invalid_channel_index(audio_fixtures: dict[str, object]) -> None:
    with pytest.raises(ContractValidationError, match="channel_index"):
        load_audio(
            base_record(audio_fixtures["stereo_path"]),
            {
                "runtime": {"sample_rate_hz": SOURCE_SAMPLE_RATE},
                "audio": {"channel_policy": "select", "channel_index": 9},
            },
        )
