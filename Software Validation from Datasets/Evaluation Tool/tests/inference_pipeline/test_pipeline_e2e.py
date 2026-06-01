from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.inference_pipeline.asr.base import ASRBase, ASRContext, normalize_text
from app.inference_pipeline.asr.whisper_adapter import WhisperASR, WhisperASRUnavailableError
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment
from app.inference_pipeline.enrollment import EnrollmentDatabase, add_enrollment_exemplar
from app.inference_pipeline.pipeline import (
    AudioFileReader,
    PipelineRunner,
    pipeline_config_mapping,
)
from app.inference_pipeline.segmentation.base import FixedSegmenter
from app.inference_pipeline.speaker_embedding import (
    SpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
    normalize_vector,
)
from app.inference_pipeline.speaker_embedding.speechbrain_adapter import (
    SpeechBrainECAPAAdapter,
    SpeechBrainUnavailableError,
)
from app.inference_pipeline.speaker_matching import CosineThresholdSpeakerMatcher
from app.inference_pipeline.speaker_matching.base import DECISION_NO_ENROLLED_SPEAKERS
from app.model_runner.external_stub import ExternalStubRunner
from app.prediction_io.jsonl import read_utterance_predictions
from app.utils.json_utils import read_jsonl


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
LOGGER = logging.getLogger(__name__)
MODEL_ID = "speaker-embedder@unit"


class SequenceASR(ASRBase):
    name = "sequence_asr"

    def __init__(self, texts: tuple[str, ...]) -> None:
        super().__init__()
        self.texts = texts

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        raw_text = self.texts[context.segment_index]
        normalized = normalize_text(raw_text)
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized
        return ASRTranscript(
            text=normalized,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            language=context.language,
        )


class StaticSpeakerEmbedding(SpeakerEmbeddingBase):
    name = "static_speaker_embedding"

    def __init__(self) -> None:
        super().__init__(model_name=MODEL_ID, min_duration_sec=0.0)

    def embed(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
    ) -> SpeakerEmbedding:
        return SpeakerEmbedding(
            embedding_id=f"{context.recording_id}:{context.utt_id}:{context.segment_index}",
            vector=normalize_vector((1.0, 0.0, 0.0)),
            model_name=MODEL_ID,
            segment_duration_sec=audio_segment.duration_sec,
            recording_id=context.recording_id,
            utt_id=context.utt_id,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            sample_rate_hz=audio_segment.sample_rate_hz,
        )


class RecordingWhisperModel:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def transcribe(self, audio_path: str, **kwargs: object) -> dict[str, object]:
        _ = audio_path
        self.kwargs = kwargs
        return {"text": "hello"}


def test_pipeline_predict_assembles_named_transcript_and_diagnostics(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "input.wav", duration_sec=2.0)
    record = sample_record(wav_path)
    segments = (
        AudioSegment(audio_path=wav_path, start_sec=1.0, end_sec=2.0, duration_sec=1.0),
        AudioSegment(audio_path=wav_path, start_sec=0.0, end_sec=1.0, duration_sec=1.0),
    )
    pipeline = PipelineRunner(
        audio_reader=AudioFileReader(),
        asr=SequenceASR(("world again", "hello world")),
        segmenter=FixedSegmenter(segments),
        speaker_embedding=StaticSpeakerEmbedding(),
        speaker_matcher=CosineThresholdSpeakerMatcher(
            threshold=0.8,
            min_margin=0.0,
            runtime_model_id=MODEL_ID,
        ),
        enrollment_db=enrollment_db(),
    )

    output = pipeline.predict(record, {"runtime": {"precision": "float32"}})

    assert output.recording_id == " rec-001 "
    assert output.utt_id == "utt-001"
    assert output.start_sec == pytest.approx(0.0)
    assert output.end_sec == pytest.approx(2.0)
    assert output.speaker_label == "Alice"
    assert output.text == "hello world again"
    assert [item.start_sec for item in output.transcript_items] == [0.0, 1.0]
    assert [item.text for item in output.transcript_items] == ["hello world", "again"]
    assert list(output.to_utterance_prediction_row()) == [
        "recording_id",
        "utt_id",
        "start_sec",
        "end_sec",
        "speaker_label",
        "text",
    ]
    assert pipeline.last_diagnostics is not None
    assert pipeline.last_diagnostics["chronological_ordering_violations"] == 1
    assert pipeline.last_diagnostics["duplicate_text_tokens_removed"] == 1
    assert pipeline.last_diagnostics["speaker_decisions"][0]["speaker_label"] == "Alice"
    assert "runtime_breakdown" in pipeline.last_diagnostics


def test_default_e2e_config_runs_without_model_assets(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "speech.wav", duration_sec=1.0)
    config = pipeline_config_mapping(CONFIG_ROOT / "e2e_named_transcript.yaml")
    configured = PipelineRunner.from_config(config)
    pipeline = PipelineRunner()

    assert configured.vad is not None
    assert configured.segmenter is not None
    output = pipeline.predict(sample_record(wav_path, end_sec=1.0), config)

    assert output.recording_id == " rec-001 "
    assert output.utt_id == "utt-001"
    assert output.text == "dummy pipeline transcript"
    assert output.speaker_label == "Unknown"
    assert pipeline.last_diagnostics is not None
    assert pipeline.last_diagnostics["segments"]
    assert pipeline.last_diagnostics["runtime_breakdown"]["pipeline_realtime_factor"] is not None


def test_real_local_config_selects_real_adapters_without_loading_models() -> None:
    config = pipeline_config_mapping(CONFIG_ROOT / "e2e_real_local.yaml")
    configured = PipelineRunner.from_config(config)

    assert config["components"]["asr"]["name"] == "whisper_tiny"
    assert config["components"]["speaker_embedding"]["name"] == "speechbrain_ecapa"
    assert config["components"]["speaker_matching"]["name"] == "cosine_threshold"
    assert getattr(configured.asr, "model_name") == "whisper_tiny"
    assert getattr(configured.speaker_embedding, "model_name") == "speechbrain_ecapa@1.1.0"
    assert getattr(configured.speaker_matcher, "threshold") == pytest.approx(0.82)


def test_component_reference_configs_resolve_for_runtime_pipeline() -> None:
    config = pipeline_config_mapping(CONFIG_ROOT / "desktop_gpu.yaml")

    assert isinstance(config["components"]["asr"], dict)
    assert config["components"]["asr"]["name"] == "whisper_tiny"
    assert config["components"]["speaker_embedding"]["name"] == "speechbrain_ecapa"


def test_pipeline_empty_enrollment_db_returns_unknown(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "input.wav", duration_sec=1.0)
    pipeline = PipelineRunner(
        audio_reader=AudioFileReader(),
        asr=SequenceASR(("hello world",)),
        speaker_embedding=StaticSpeakerEmbedding(),
        speaker_matcher=CosineThresholdSpeakerMatcher(
            threshold=0.8,
            min_margin=0.0,
            runtime_model_id=MODEL_ID,
        ),
        enrollment_db=EnrollmentDatabase.empty(created_at="2026-05-31T00:00:00Z"),
    )

    output = pipeline.predict(sample_record(wav_path, end_sec=1.0), {})

    assert output.speaker_label == "Unknown"
    assert pipeline.last_diagnostics is not None
    assert pipeline.last_diagnostics["speaker_decisions"][0]["threshold_decision"] == (
        DECISION_NO_ENROLLED_SPEAKERS
    )


def test_whisper_missing_local_asset_error_lists_expected_paths(tmp_path: Path) -> None:
    asr = WhisperASR(
        {
            "model_size": "unit_missing_model",
            "cache_dir": str(tmp_path / "missing_whisper"),
            "allow_model_downloads": False,
        }
    )
    context = ASRContext(
        recording_id="rec",
        utt_id="utt",
        source_audio_path=tmp_path / "audio.wav",
        run_config={"project_root": str(tmp_path)},
    )

    with pytest.raises(WhisperASRUnavailableError, match="Expected unit_missing_model.pt"):
        asr._model(context)


def test_whisper_adapter_passes_beam_size_to_model(tmp_path: Path) -> None:
    model = RecordingWhisperModel()
    asr = WhisperASR({"beam_size": 5, "dtype": "float32"}, model=model)
    audio_path = tmp_path / "audio.wav"
    context = ASRContext(
        recording_id="rec",
        utt_id="utt",
        source_audio_path=audio_path,
    )

    asr.transcribe(
        AudioSegment(audio_path=audio_path, start_sec=0.0, end_sec=1.0, duration_sec=1.0),
        context,
    )

    assert model.kwargs is not None
    assert model.kwargs["beam_size"] == 5
    assert model.kwargs["fp16"] is False


def test_speechbrain_missing_local_asset_error_lists_savedir(tmp_path: Path) -> None:
    adapter = SpeechBrainECAPAAdapter(
        {
            "savedir": str(tmp_path / "missing_speechbrain"),
            "allow_model_downloads": False,
        }
    )
    context = SpeakerEmbeddingContext(
        recording_id="rec",
        utt_id="utt",
        source_audio_path=tmp_path / "audio.wav",
        run_config={"project_root": str(tmp_path)},
    )

    with pytest.raises(SpeechBrainUnavailableError, match="savedir"):
        adapter._model(context, "cpu")


def test_external_stub_writes_predictions_and_pipeline_diagnostics(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "input.wav", duration_sec=2.0)
    record = sample_record(wav_path)
    record["audio_path_resolved"] = str(wav_path)
    run_dir = tmp_path / "run"
    predictions_dir = run_dir / "predictions"
    run_config = {
        "project_root": str(tmp_path),
        "run_dir": str(run_dir),
        "augmentation": {
            "mode": "none",
            "conditions": [{"condition_id": "clean", "mode": "none"}],
        },
    }
    pipeline = PipelineRunner(
        audio_reader=AudioFileReader(),
        asr=SequenceASR(("hello world",)),
        speaker_embedding=StaticSpeakerEmbedding(),
        speaker_matcher=CosineThresholdSpeakerMatcher(
            threshold=0.8,
            min_margin=0.0,
            runtime_model_id=MODEL_ID,
        ),
        enrollment_db=enrollment_db(),
    )

    result = ExternalStubRunner(pipeline_runner=pipeline).run_batch(
        [record],
        predictions_dir,
        run_config,
        LOGGER,
    )

    rows = read_utterance_predictions(predictions_dir / "utterances.jsonl")
    diagnostics = list(read_jsonl(predictions_dir / "pipeline_diagnostics.jsonl"))
    summary_path = predictions_dir / "pipeline_diagnostics_summary.json"

    assert result.written_count == 1
    assert result.failed_count == 0
    assert rows == [
        {
            "recording_id": " rec-001 ",
            "utt_id": "utt-001",
            "start_sec": 0.0,
            "end_sec": 2.0,
            "speaker_label": "Alice",
            "text": "hello world",
        }
    ]
    assert diagnostics[0]["recording_id"] == " rec-001 "
    assert diagnostics[0]["reference_speaker_label"] == "Alice"
    assert summary_path.exists()


def sample_record(path: Path, *, end_sec: float = 2.0) -> dict[str, object]:
    return {
        "recording_id": " rec-001 ",
        "utt_id": "utt-001",
        "inference_audio_path": str(path),
        "start_sec": 0.0,
        "end_sec": end_sec,
        "speaker_label": "Alice",
        "reference_text": "hello world",
    }


def write_wav(path: Path, *, duration_sec: float, sample_rate: int = 16000) -> Path:
    samples = int(duration_sec * sample_rate)
    time = np.arange(samples, dtype=np.float32) / sample_rate
    waveform = 0.25 * np.sin(2 * np.pi * 220 * time)
    sf.write(path, waveform.astype(np.float32), sample_rate)
    return path


def enrollment_db() -> EnrollmentDatabase:
    db = EnrollmentDatabase.empty(created_at="2026-05-31T00:00:00Z")
    db, _ = add_enrollment_exemplar(
        db,
        display_name="Alice",
        prompt_id="unit",
        audio_path=Path("alice.wav"),
        embedding=normalize_vector((1.0, 0.0, 0.0)),
        model_id=MODEL_ID,
        created_at="2026-05-31T00:00:01Z",
        duration_sec=1.0,
        validate_audio_path=False,
    )
    return db
