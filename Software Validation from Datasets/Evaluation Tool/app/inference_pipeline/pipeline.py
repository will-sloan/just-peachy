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
from app.inference_pipeline.segmentation.base import (
    SegmenterBase,
    build_segmenter_from_config,
)
from app.inference_pipeline.vad.base import VADBase, build_vad_from_config


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
    vad: VADBase | None = None
    segmenter: SegmenterBase | None = None
    device: str = "cpu"

    @classmethod
    def with_dummy_components(
        cls,
        vad: VADBase | None = None,
        segmenter: SegmenterBase | None = None,
        config: object | None = None,
    ) -> "PipelineRunner":
        """Build the M4 dummy pipeline without loading models."""

        selected_vad = vad
        if selected_vad is None and config is not None:
            selected_vad = build_vad_from_config(config)
        selected_segmenter = segmenter
        if selected_segmenter is None and config is not None:
            selected_segmenter = build_segmenter_from_config(config)
        return cls(
            audio_reader=DummyAudioReader(),
            asr=DummyASRComponent(),
            speaker_labeler=DummySpeakerLabeler(),
            vad=selected_vad,
            segmenter=selected_segmenter,
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
        vad_sec = None
        vad_regions = ()
        if self.vad is not None:
            vad_started_at = time.perf_counter()
            vad_regions = tuple(self.vad.detect(audio))
            vad_sec = time.perf_counter() - vad_started_at
        segments = ()
        segmentation_sec = None
        if self.segmenter is not None:
            segmentation_started_at = time.perf_counter()
            segments = tuple(self.segmenter.segment(evaluation_record, vad_regions, audio))
            segmentation_sec = time.perf_counter() - segmentation_started_at
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
            runtime_stats=RuntimeStats(
                total_sec=elapsed,
                vad_sec=vad_sec,
                device=self.device,
                counters=_runtime_counters(
                    vad_enabled=self.vad is not None,
                    vad_region_count=len(vad_regions),
                    segmentation_enabled=self.segmenter is not None,
                    segment_count=len(segments),
                    segmentation_sec=segmentation_sec,
                ),
            ),
        )


def _runtime_counters(
    *,
    vad_enabled: bool,
    vad_region_count: int,
    segmentation_enabled: bool,
    segment_count: int,
    segmentation_sec: float | None,
) -> dict[str, object] | None:
    counters: dict[str, object] = {}
    if vad_enabled:
        counters["vad_region_count"] = vad_region_count
    if segmentation_enabled:
        counters["segment_count"] = segment_count
        counters["segmentation_sec"] = segmentation_sec
    return counters or None
