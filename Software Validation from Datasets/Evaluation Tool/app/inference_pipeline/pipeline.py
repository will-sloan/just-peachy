"""Small modular inference pipeline skeleton for external-runner smoke tests."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from app.inference_pipeline.contracts import (
    ASRTranscript,
    EvaluationRecord,
    PipelineOutput,
    RuntimeStats,
    SpeakerDecision,
)
from app.inference_pipeline.dummy_components import (
    DummyASRComponent,
    DummyAudioReader,
    DummySpeakerLabeler,
)


class AudioReader(Protocol):
    def load(
        self,
        record: EvaluationRecord,
        run_config: Mapping[str, object] | None = None,
    ) -> Any:
        """Return an audio handle for a selected Evaluation Tool record."""


class ASRComponent(Protocol):
    def transcribe(
        self,
        record: EvaluationRecord,
        audio: Any,
        run_config: Mapping[str, object] | None = None,
    ) -> ASRTranscript:
        """Return an utterance transcript."""


class SpeakerLabeler(Protocol):
    def label(
        self,
        record: EvaluationRecord,
        audio: Any,
        transcript: ASRTranscript,
        run_config: Mapping[str, object] | None = None,
    ) -> SpeakerDecision:
        """Return a speaker decision for the transcript."""


@dataclass
class PipelineRunner:
    """Run one selected metadata row through swappable pipeline components."""

    audio_reader: AudioReader
    asr: ASRComponent
    speaker_labeler: SpeakerLabeler
    device: str = "cpu"

    @classmethod
    def with_dummy_components(cls) -> "PipelineRunner":
        """Build the M4 dummy pipeline without loading models."""

        return cls(
            audio_reader=DummyAudioReader(),
            asr=DummyASRComponent(),
            speaker_labeler=DummySpeakerLabeler(),
        )

    def run_one(
        self,
        record: Mapping[str, object],
        run_config: Mapping[str, object] | None = None,
        logger: logging.Logger | None = None,
    ) -> PipelineOutput:
        """Run the pipeline for one Evaluation Tool metadata row."""

        started_at = time.perf_counter()
        evaluation_record = EvaluationRecord.from_record(record)
        audio = self.audio_reader.load(evaluation_record, run_config)
        transcript = self.asr.transcribe(evaluation_record, audio, run_config)
        speaker_decision = self.speaker_labeler.label(
            evaluation_record,
            audio,
            transcript,
            run_config,
        )
        elapsed = time.perf_counter() - started_at
        if logger is not None:
            logger.debug(
                "Dummy pipeline produced transcript for recording_id=%s utt_id=%s",
                evaluation_record.recording_id,
                evaluation_record.utt_id,
            )

        return PipelineOutput.from_record_and_transcript(
            record=evaluation_record,
            transcript=transcript,
            speaker_decision=speaker_decision,
            runtime_stats=RuntimeStats(total_sec=elapsed, device=self.device),
        )
