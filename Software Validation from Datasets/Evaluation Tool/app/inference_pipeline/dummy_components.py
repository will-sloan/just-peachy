"""Deterministic dummy components for the M4 external-runner bridge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app.inference_pipeline.contracts import ASRTranscript, EvaluationRecord, SpeakerDecision


DEFAULT_DUMMY_TEXT = "dummy pipeline transcript"


@dataclass(frozen=True)
class DummyAudioReference:
    """Metadata-only audio handle used by the dummy pipeline."""

    audio_path: Path
    start_sec: float | None
    end_sec: float | None


@dataclass(frozen=True)
class DummyAudioReader:
    """Read the Evaluation Tool audio path without doing audio inference."""

    verify_exists: bool = False

    def load(
        self,
        record: EvaluationRecord,
        run_config: Mapping[str, object] | None = None,
    ) -> DummyAudioReference:
        audio_path = record.inference_audio_path
        if self.verify_exists and not audio_path.exists():
            raise FileNotFoundError(f"inference_audio_path does not exist: {audio_path}")
        return DummyAudioReference(
            audio_path=audio_path,
            start_sec=record.start_sec,
            end_sec=record.end_sec,
        )


@dataclass(frozen=True)
class DummyASRComponent:
    """Return stable placeholder transcript text."""

    text: str = DEFAULT_DUMMY_TEXT

    def transcribe(
        self,
        record: EvaluationRecord,
        audio: DummyAudioReference,
        run_config: Mapping[str, object] | None = None,
    ) -> ASRTranscript:
        _ = audio.audio_path
        return ASRTranscript(
            text=self.text,
            start_sec=record.start_sec,
            end_sec=record.end_sec,
        )


@dataclass(frozen=True)
class DummySpeakerLabeler:
    """Return no speaker attribution for the M4 smoke bridge."""

    speaker_label: str | None = None

    def label(
        self,
        record: EvaluationRecord,
        audio: DummyAudioReference,
        transcript: ASRTranscript,
        run_config: Mapping[str, object] | None = None,
    ) -> SpeakerDecision:
        _ = (record, audio, transcript, run_config)
        return SpeakerDecision(speaker_label=self.speaker_label, method="dummy")
