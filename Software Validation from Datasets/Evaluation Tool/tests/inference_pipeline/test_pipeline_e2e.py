from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from app.inference_pipeline.asr.base import ASRBase, ASRContext, normalize_text
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment
from app.inference_pipeline.enrollment.schema import EnrollmentDatabase
from app.inference_pipeline.pipeline import AudioLoaderAdapter, PipelineRunner
from app.inference_pipeline.segmentation.base import FixedSegmenter
from app.model_runner.external_stub import ExternalStubRunner
from app.prediction_io.jsonl import read_utterance_predictions
from app.utils.json_utils import read_jsonl


LOGGER = logging.getLogger(__name__)


class SegmentTextASR(ASRBase):
    name = "segment_text_asr"

    def __init__(self, text_by_start: dict[float, str]) -> None:
        super().__init__()
        self.text_by_start = text_by_start

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        _ = context
        raw_text = self.text_by_start[float(audio_segment.start_sec or 0.0)]
        normalized = normalize_text(raw_text)
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized
        return ASRTranscript(
            text=normalized,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            language="en",
        )


class FixedSpeakerEmbedding:
    model_name = "fixed_speaker_embedding"

    def embed(self, audio_segment, context):
        return {
            "embedding_id": f"{context.recording_id}:{context.utt_id}:{context.segment_index}",
            "vector": [1.0, 0.0, 0.0],
            "model_name": self.model_name,
            "start_sec": audio_segment.start_sec,
            "end_sec": audio_segment.end_sec,
        }


class FixedSpeakerMatcher:
    name = "fixed_speaker_matcher"

    def match(self, embedding, enrollment_db):
        _ = (embedding, enrollment_db)
        return {
            "speaker_label": "Alice",
            "confidence": 0.99,
            "method": self.name,
            "embedding_id": embedding["embedding_id"],
            "matched_reference_id": "alice:centroid",
        }


def test_pipeline_predict_assembles_chronological_unique_utterance(tmp_path: Path) -> None:
    audio_path = write_wav(tmp_path / "augmented.wav", duration_sec=2.0)
    fallback_path = tmp_path / "original.wav"
    record = {
        "recording_id": " rec-001 ",
        "utt_id": "utt:001",
        "inference_audio_path": str(audio_path),
        "audio_path_resolved": str(fallback_path),
        "start_sec": 0.0,
        "end_sec": 2.0,
        "speaker_label": "reference-speaker",
    }
    later = AudioSegment(audio_path=audio_path, start_sec=1.0, end_sec=2.0, duration_sec=1.0)
    earlier = AudioSegment(audio_path=audio_path, start_sec=0.0, end_sec=1.0, duration_sec=1.0)
    pipeline = PipelineRunner(
        audio_reader=AudioLoaderAdapter(),
        vad=None,
        segmenter=FixedSegmenter([later, earlier]),
        asr=SegmentTextASR({0.0: "Hello world", 1.0: "world again"}),
        speaker_labeler=None,
        speaker_embedding=FixedSpeakerEmbedding(),
        speaker_matcher=FixedSpeakerMatcher(),
        enrollment_db=EnrollmentDatabase.empty(created_at="2026-06-01T00:00:00Z"),
    )

    output = pipeline.predict(record, {"runtime": {"precision": "float32"}})

    assert output.to_utterance_prediction_row() == {
        "recording_id": " rec-001 ",
        "utt_id": "utt:001",
        "start_sec": 0.0,
        "end_sec": 2.0,
        "speaker_label": "Alice",
        "text": "hello world again",
    }
    assert output.diagnostics is not None
    assert output.diagnostics["chronological_ordering_violations"] == 1
    assert output.diagnostics["raw_asr_text"] == ["Hello world", "world again"]
    assert output.diagnostics["normalized_text"] == ["hello world", "world again"]
    assert output.diagnostics["runtime_stats"]["realtime_factor"] is not None
    assert [
        segment["audio_path"]
        for segment in output.diagnostics["segments"]
    ] == [str(audio_path), str(audio_path)]


def test_external_stub_default_pipeline_writes_predictions_and_diagnostics(
    tmp_path: Path,
) -> None:
    audio_path = write_wav(tmp_path / "input.wav")
    run_dir = tmp_path / "run"
    predictions_dir = run_dir / "predictions"
    record = {
        "recording_id": "rec-002",
        "utt_id": "utt-002",
        "inference_audio_path": str(audio_path),
        "audio_path_resolved": str(audio_path),
        "start_sec": 0.0,
        "end_sec": 1.0,
        "speaker_label": "reference-speaker",
        "reference_text": "dummy pipeline transcript",
    }
    run_config = {
        "project_root": str(tmp_path),
        "run_dir": str(run_dir),
        "augmentation": {
            "mode": "none",
            "conditions": [{"condition_id": "clean", "mode": "none"}],
        },
    }

    result = ExternalStubRunner().run_batch([record], predictions_dir, run_config, LOGGER)
    rows = read_utterance_predictions(predictions_dir / "utterances.jsonl")
    diagnostics_rows = list(read_jsonl(predictions_dir / "diagnostics.jsonl"))

    assert result.written_count == 1
    assert result.failed_count == 0
    assert rows == [
        {
            "recording_id": "rec-002",
            "utt_id": "utt-002",
            "start_sec": 0.0,
            "end_sec": 1.0,
            "speaker_label": "Unknown",
            "text": "dummy pipeline transcript",
        }
    ]
    assert set(rows[0]) == {
        "recording_id",
        "utt_id",
        "start_sec",
        "end_sec",
        "speaker_label",
        "text",
    }
    assert len(diagnostics_rows) == 1
    assert diagnostics_rows[0]["recording_id"] == "rec-002"
    assert diagnostics_rows[0]["utt_id"] == "utt-002"
    assert diagnostics_rows[0]["diagnostics"]["runtime_stats"]["stage_breakdown_sec"]["audio_load_sec"] is not None


def write_wav(path: Path, *, sample_rate: int = 16000, duration_sec: float = 1.0) -> Path:
    t = np.linspace(0.0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    waveform = 0.25 * np.sin(2.0 * np.pi * 440.0 * t)
    sf.write(path, waveform.astype(np.float32), sample_rate)
    return path
