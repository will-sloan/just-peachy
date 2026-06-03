from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import PipelineOutput
from app.utils.json_utils import read_json, read_jsonl


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
SCRIPTS_ROOT = TOOL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

live_mic_smoke = importlib.import_module("live_mic_smoke")


class FakeCapture:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def capture_chunk(self, output_path: Path, duration_sec: float, sample_rate: int) -> Path:
        self.calls.append(
            {
                "output_path": output_path,
                "duration_sec": duration_sec,
                "sample_rate": sample_rate,
            }
        )
        live_mic_smoke.write_silence_wav(
            output_path,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
        )
        return output_path


class FakePipeline:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []
        self.run_configs: list[dict[str, object]] = []
        self.last_diagnostics = {"fake": True}

    def predict(self, record, run_config):
        self.records.append(dict(record))
        self.run_configs.append(dict(run_config))
        return PipelineOutput(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            start_sec=float(record["start_sec"]),
            end_sec=float(record["end_sec"]),
            speaker_label=record.get("speaker_label"),
            text=f"fake transcript {record['chunk_index']}",
            diagnostics={
                "inference_audio_path": str(record["inference_audio_path"]),
                "chunk_index": record["chunk_index"],
            },
        )


def test_live_mic_smoke_preserves_synthetic_record_contract(tmp_path: Path) -> None:
    capture = FakeCapture()
    pipeline = FakePipeline()

    result = live_mic_smoke.run_live_mic_smoke(
        config_path=CONFIG_ROOT / "live_mic_whisper_tiny.yaml",
        run_id="unit_fake_capture",
        duration_sec=2.5,
        chunk_sec=1.0,
        sample_rate=16000,
        speaker_label="Billy",
        recording_id="mic-rec",
        output_dir=tmp_path / "runs",
        keep_audio=True,
        dry_run=False,
        capture=capture,
        pipeline_runner=pipeline,
        report_dir=tmp_path / "reports",
        stdout=sys.stdout,
    )

    assert result.chunk_count == 3
    assert result.prediction_count == 3
    assert [call["duration_sec"] for call in capture.calls] == [1.0, 1.0, 0.5]
    assert [record["recording_id"] for record in pipeline.records] == ["mic-rec"] * 3
    assert [record["utt_id"] for record in pipeline.records] == [
        "mic-rec_chunk_0001",
        "mic-rec_chunk_0002",
        "mic-rec_chunk_0003",
    ]
    assert [(record["start_sec"], record["end_sec"]) for record in pipeline.records] == [
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 0.5),
    ]
    assert [record["speaker_label"] for record in pipeline.records] == ["Billy"] * 3

    for index, record in enumerate(pipeline.records, start=1):
        expected_path = result.run_dir / "audio" / f"chunk_{index:04d}.wav"
        assert Path(str(record["inference_audio_path"])) == expected_path
        assert expected_path.is_file()

    prediction_rows = list(read_jsonl(result.predictions_path))
    assert [set(row) for row in prediction_rows] == [
        set(live_mic_smoke.REQUIRED_PREDICTION_FIELDS),
        set(live_mic_smoke.REQUIRED_PREDICTION_FIELDS),
        set(live_mic_smoke.REQUIRED_PREDICTION_FIELDS),
    ]
    assert [row["speaker_label"] for row in prediction_rows] == ["Billy"] * 3
    assert [row["text"] for row in prediction_rows] == [
        "fake transcript 1",
        "fake transcript 2",
        "fake transcript 3",
    ]

    diagnostics_rows = list(read_jsonl(result.diagnostics_path))
    assert [row["inference_audio_path"] for row in diagnostics_rows] == [
        str(result.run_dir / "audio" / "chunk_0001.wav"),
        str(result.run_dir / "audio" / "chunk_0002.wav"),
        str(result.run_dir / "audio" / "chunk_0003.wav"),
    ]


def test_dry_run_works_without_microphone_or_whisper_assets(tmp_path: Path) -> None:
    result = live_mic_smoke.run_live_mic_smoke(
        config_path=CONFIG_ROOT / "live_mic_whisper_tiny.yaml",
        run_id="unit_dry_run",
        duration_sec=0.2,
        chunk_sec=0.1,
        sample_rate=16000,
        speaker_label="Dry Speaker",
        recording_id="dry-rec",
        output_dir=tmp_path / "runs",
        keep_audio=False,
        dry_run=True,
        report_dir=tmp_path / "reports",
        stdout=sys.stdout,
    )

    rows = list(read_jsonl(result.predictions_path))
    summary = read_json(result.summary_path)

    assert result.dry_run is True
    assert result.microphone_capture_tested is False
    assert result.asr_mode == "dry_run_no_op_asr"
    assert len(rows) == 2
    assert {row["text"] for row in rows} == {"dry run transcript unavailable"}
    assert all(row["speaker_label"] == "Dry Speaker" for row in rows)
    assert not (result.run_dir / "audio").exists()
    assert summary["dry_run"] is True
    assert summary["availability"]["asr_component"] == "whisper_tiny"


def test_missing_sounddevice_dependency_is_reported_cleanly(tmp_path: Path) -> None:
    def missing_importer(name: str):
        if name == "sounddevice":
            raise ModuleNotFoundError(name)
        return importlib.import_module(name)

    capture = live_mic_smoke.SoundDeviceMicrophoneCapture(module_importer=missing_importer)

    with pytest.raises(live_mic_smoke.MicrophoneUnavailableError, match="sounddevice"):
        capture.capture_chunk(tmp_path / "chunk.wav", duration_sec=0.1, sample_rate=16000)


def test_live_mic_whisper_tiny_config_selects_real_asr_without_downloads() -> None:
    config = PipelineConfig.from_yaml_path(CONFIG_ROOT / "live_mic_whisper_tiny.yaml")
    availability = live_mic_smoke.inspect_runtime_availability(
        config,
        config_path=CONFIG_ROOT / "live_mic_whisper_tiny.yaml",
    )

    assert config.components["asr"].name == "whisper_tiny"
    assert config.components["asr"].params["allow_model_downloads"] is False
    assert config.components["vad"].enabled is False
    assert config.components["segmentation"].enabled is False
    assert availability["asr_component"] == "whisper_tiny"
    assert availability["allow_model_downloads"] is False
    assert "whisper_model_asset_searched" in availability


def test_non_dry_no_op_config_is_rejected_without_pretending_real_asr() -> None:
    config = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml")
    availability = live_mic_smoke.inspect_runtime_availability(
        config,
        config_path=CONFIG_ROOT / "cpu_smoke.yaml",
    )

    with pytest.raises(live_mic_smoke.LiveMicSmokeError, match="no_op_asr"):
        live_mic_smoke._select_pipeline(
            config,
            availability,
            dry_run=False,
            pipeline_runner=None,
        )
