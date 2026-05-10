import json
from pathlib import Path

import pytest

from app.inference_pipeline.contracts import (
    ASRTranscript,
    AudioSegment,
    EvaluationRecord,
    PipelineOutput,
    RuntimeStats,
    SpeakerDecision,
    SpeakerEmbedding,
    SpeechRegion,
    TranscriptItem,
    WordTiming,
)
from app.inference_pipeline.errors import (
    ContractValidationError,
    IdentityMismatchError,
    MissingRequiredFieldError,
)


def sample_record() -> dict[str, object]:
    return {
        "recording_id": " rec-001 ",
        "utt_id": "utt-001",
        "inference_audio_path": "runs/tmp/augmented.wav",
        "start_sec": 1.25,
        "end_sec": 4.5,
        "speaker_label": "speaker-a",
        "augmentation_condition_id": "noise_5db",
        "dataset_specific": {"room": "rm1"},
    }


def test_contract_classes_import_without_ml_dependencies() -> None:
    assert EvaluationRecord
    assert AudioSegment
    assert SpeechRegion
    assert ASRTranscript
    assert WordTiming
    assert SpeakerEmbedding
    assert SpeakerDecision
    assert TranscriptItem
    assert RuntimeStats
    assert PipelineOutput


def test_evaluation_record_preserves_identity_and_timing() -> None:
    record = EvaluationRecord.from_record(sample_record())

    assert record.recording_id == " rec-001 "
    assert record.utt_id == "utt-001"
    assert record.inference_audio_path == Path("runs/tmp/augmented.wav")
    assert record.start_sec == 1.25
    assert record.end_sec == 4.5
    assert record.speaker_label == "speaker-a"
    assert record.extras == {"dataset_specific": {"room": "rm1"}}


@pytest.mark.parametrize("missing_field", ["recording_id", "utt_id", "inference_audio_path"])
def test_evaluation_record_requires_runner_contract_fields(missing_field: str) -> None:
    record = sample_record()
    record.pop(missing_field)

    with pytest.raises(MissingRequiredFieldError):
        EvaluationRecord.from_record(record)


def test_audio_segment_defaults_to_mono() -> None:
    segment = AudioSegment(audio_path=Path("audio.wav"))

    assert segment.channel_count == 1
    assert segment.is_mono is True
    assert json.dumps(segment.to_jsonable())


def test_speech_region_validates_time_ordering() -> None:
    with pytest.raises(ContractValidationError):
        SpeechRegion(start_sec=5.0, end_sec=4.0)


def test_word_timing_requires_non_empty_word() -> None:
    with pytest.raises(ContractValidationError):
        WordTiming(word=" ")


def test_speaker_embedding_validates_dim_against_vector_length() -> None:
    embedding = SpeakerEmbedding(embedding_id="emb-1", vector=(0.1, 0.2), dim=2)

    assert embedding.dim == 2
    assert embedding.to_jsonable()["vector"] == [0.1, 0.2]

    with pytest.raises(ContractValidationError):
        SpeakerEmbedding(embedding_id="emb-2", vector=(0.1, 0.2), dim=3)


def test_pipeline_output_maps_to_exact_utterance_prediction_fields() -> None:
    record = EvaluationRecord.from_record(sample_record())
    transcript = ASRTranscript(
        text="hello world",
        words=(WordTiming(word="hello", start_sec=1.25, end_sec=1.7),),
        confidence=0.95,
        start_sec=1.25,
        end_sec=4.5,
    )
    output = PipelineOutput.from_record_and_transcript(
        record=record,
        transcript=transcript,
        speaker_decision=SpeakerDecision(speaker_label="speaker-b", confidence=0.8),
        runtime_stats=RuntimeStats(total_sec=0.5, device="cpu"),
        transcript_items=(
            TranscriptItem(text="hello world", start_sec=1.25, end_sec=4.5),
        ),
    )

    row = output.to_utterance_prediction_row()

    assert list(row) == [
        "recording_id",
        "utt_id",
        "start_sec",
        "end_sec",
        "speaker_label",
        "text",
    ]
    assert row == {
        "recording_id": " rec-001 ",
        "utt_id": "utt-001",
        "start_sec": 1.25,
        "end_sec": 4.5,
        "speaker_label": "speaker-b",
        "text": "hello world",
    }
    assert json.dumps(output.to_jsonable())


def test_pipeline_output_detects_source_identity_mismatch() -> None:
    record = EvaluationRecord.from_record(sample_record())
    output = PipelineOutput(
        recording_id="other",
        utt_id=record.utt_id,
        start_sec=record.start_sec,
        end_sec=record.end_sec,
        speaker_label=record.speaker_label,
        text="hello",
    )

    with pytest.raises(IdentityMismatchError):
        output.validate_identity(record)

