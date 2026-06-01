from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from app.cli.main import build_parser
from app.inference_pipeline.contracts import PipelineOutput
from app.inference_pipeline.dummy_components import (
    DEFAULT_DUMMY_TEXT,
    DummyASRComponent,
    DummyAudioReader,
    DummySpeakerLabeler,
)
from app.inference_pipeline.pipeline import PipelineRunner
from app.model_runner.external_stub import ExternalStubRunner
from app.prediction_io.jsonl import read_utterance_predictions
from app.prediction_io.schema import UtterancePrediction


LOGGER = logging.getLogger(__name__)


def sample_record(audio_path: Path) -> dict[str, object]:
    return {
        "recording_id": " rec-001 ",
        "utt_id": "utt:001",
        "inference_audio_path": str(audio_path),
        "audio_path_resolved": str(audio_path),
        "start_sec": 1.25,
        "end_sec": 3.5,
        "speaker_label": "speaker-a",
        "reference_text": "reference words",
    }


class SpyPipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], dict[str, object], logging.Logger]] = []

    def run_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> PipelineOutput:
        self.calls.append((record, run_config, logger))
        return PipelineOutput(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            start_sec=record.get("start_sec"),
            end_sec=record.get("end_sec"),
            speaker_label=None,
            text="spy bridge transcript",
        )


class TrackingAudioReader:
    def __init__(self) -> None:
        self.paths: list[Path] = []
        self.delegate = DummyAudioReader()

    def load(self, record, run_config=None):
        self.paths.append(record.inference_audio_path)
        return self.delegate.load(record, run_config)


def test_external_stub_predict_one_calls_pipeline_and_returns_prediction(tmp_path: Path) -> None:
    record = sample_record(tmp_path / "input.wav")
    run_config = {"runner": {"name": "external-stub"}}
    pipeline = SpyPipeline()
    runner = ExternalStubRunner(pipeline_runner=pipeline)

    prediction = runner.predict_one(record, run_config, LOGGER)

    assert isinstance(prediction, UtterancePrediction)
    assert pipeline.calls == [(record, run_config, LOGGER)]
    assert prediction.recording_id == " rec-001 "
    assert prediction.utt_id == "utt:001"
    assert prediction.start_sec == 1.25
    assert prediction.end_sec == 3.5
    assert prediction.speaker_label is None
    assert prediction.text == "spy bridge transcript"


def test_default_dummy_pipeline_output_is_deterministic(tmp_path: Path) -> None:
    audio_path = write_wav(tmp_path / "input.wav")
    record = sample_record(audio_path)
    runner = ExternalStubRunner()

    first = runner.predict_one(dict(record), {}, LOGGER)
    second = runner.predict_one(dict(record), {}, LOGGER)

    assert first.text == DEFAULT_DUMMY_TEXT
    assert second.text == DEFAULT_DUMMY_TEXT
    assert first == second
    assert first.speaker_label == "Unknown"


def test_pipeline_reads_inference_audio_path_not_fallback(tmp_path: Path) -> None:
    inference_audio_path = tmp_path / "augmented.wav"
    fallback_audio_path = tmp_path / "original.wav"
    record = sample_record(inference_audio_path)
    record["audio_path_resolved"] = str(fallback_audio_path)
    audio_reader = TrackingAudioReader()
    pipeline = PipelineRunner(
        audio_reader=audio_reader,
        asr=DummyASRComponent(),
        speaker_labeler=DummySpeakerLabeler(),
    )

    output = pipeline.run_one(record, {}, LOGGER)

    assert audio_reader.paths == [inference_audio_path]
    assert output.recording_id == " rec-001 "
    assert output.utt_id == "utt:001"
    assert output.start_sec == 1.25
    assert output.end_sec == 3.5
    assert output.speaker_label is None
    assert output.text == DEFAULT_DUMMY_TEXT


def test_external_stub_run_batch_writes_schema_compatible_jsonl(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    predictions_dir = run_dir / "predictions"
    audio_path = write_wav(tmp_path / "input.wav")
    records = [sample_record(audio_path)]
    run_config = {
        "project_root": str(tmp_path),
        "run_dir": str(run_dir),
        "augmentation": {
            "mode": "none",
            "conditions": [{"condition_id": "clean", "mode": "none"}],
        },
    }

    result = ExternalStubRunner().run_batch(records, predictions_dir, run_config, LOGGER)
    rows = read_utterance_predictions(predictions_dir / "utterances.jsonl")

    assert result.written_count == 1
    assert result.failed_count == 0
    assert rows == [
        {
            "recording_id": " rec-001 ",
            "utt_id": "utt:001",
            "start_sec": 1.25,
            "end_sec": 3.5,
            "speaker_label": "Unknown",
            "text": DEFAULT_DUMMY_TEXT,
        }
    ]
    assert (predictions_dir / "pipeline_diagnostics.jsonl").exists()


def test_cli_accepts_inference_config_for_external_stub() -> None:
    args = build_parser().parse_args(
        [
            "full",
            "--dataset",
            "cmu_arctic",
            "--runner",
            "external-stub",
            "--inference-config",
            "configs/inference/e2e_real_local.yaml",
        ]
    )

    assert args.runner == "external-stub"
    assert args.inference_config == Path("configs/inference/e2e_real_local.yaml")


def write_wav(path: Path, *, duration_sec: float = 3.5, sample_rate: int = 16000) -> Path:
    samples = int(duration_sec * sample_rate)
    time = np.arange(samples, dtype=np.float32) / sample_rate
    waveform = 0.25 * np.sin(2 * np.pi * 220 * time)
    sf.write(path, waveform.astype(np.float32), sample_rate)
    return path
