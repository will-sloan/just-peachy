"""Small modular inference pipeline skeleton for external-runner smoke tests."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from app.inference_pipeline.asr.base import ASRBase, ASRContext, build_asr_from_config
from app.inference_pipeline.contracts import (
    ASRTranscript,
    AudioSegment,
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
    asr: ASRComponent | ASRBase
    speaker_labeler: SpeakerLabeler
    vad: VADBase | None = None
    segmenter: SegmenterBase | None = None
    device: str = "cpu"

    @classmethod
    def with_dummy_components(
        cls,
        vad: VADBase | None = None,
        segmenter: SegmenterBase | None = None,
        asr: ASRComponent | ASRBase | None = None,
        config: object | None = None,
    ) -> "PipelineRunner":
        """Build the M4 dummy pipeline without loading models."""

        selected_vad = vad
        if selected_vad is None and config is not None:
            selected_vad = build_vad_from_config(config)
        selected_segmenter = segmenter
        if selected_segmenter is None and config is not None:
            selected_segmenter = build_segmenter_from_config(config)
        selected_asr = asr
        if selected_asr is None and config is not None:
            selected_asr = build_asr_from_config(config)
        return cls(
            audio_reader=DummyAudioReader(),
            asr=selected_asr or DummyASRComponent(),
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
        asr_started_at = time.perf_counter()
        transcript = _transcribe(
            self.asr,
            evaluation_record,
            audio,
            segments,
            run_config,
            self.device,
            segmentation_enabled=self.segmenter is not None,
        )
        asr_sec = time.perf_counter() - asr_started_at
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
                asr_sec=asr_sec,
                device=self.device,
                counters=_runtime_counters(
                    vad_enabled=self.vad is not None,
                    vad_region_count=len(vad_regions),
                    segmentation_enabled=self.segmenter is not None,
                    segment_count=len(segments),
                    segmentation_sec=segmentation_sec,
                    asr_base_enabled=isinstance(self.asr, ASRBase),
                    asr_segment_count=len(segments) if self.segmenter is not None else 1,
                ),
            ),
        )


def _transcribe(
    asr: ASRComponent | ASRBase,
    record: EvaluationRecord,
    audio: Any,
    segments: tuple[AudioSegment, ...],
    run_config: Mapping[str, object] | None,
    device: str,
    *,
    segmentation_enabled: bool,
) -> ASRTranscript:
    if not isinstance(asr, ASRBase):
        return asr.transcribe(record, audio, run_config)

    active_segments = segments if segmentation_enabled else (_record_segment(record, audio),)
    if not active_segments:
        return ASRTranscript(text="", start_sec=record.start_sec, end_sec=record.end_sec)

    transcripts: list[ASRTranscript] = []
    for index, segment in enumerate(active_segments):
        context = ASRContext.from_record_segment(
            record,
            segment,
            segment_index=index,
            run_config=run_config,
            device=device,
            dtype=_runtime_dtype(run_config),
            language=_asr_language(run_config),
        )
        transcripts.append(asr.transcribe(segment, context))
    if len(transcripts) == 1:
        return transcripts[0]
    return ASRTranscript(
        text=" ".join(transcript.text for transcript in transcripts if transcript.text).strip(),
        words=tuple(word for transcript in transcripts for word in transcript.words),
        language=transcripts[0].language,
        start_sec=transcripts[0].start_sec,
        end_sec=transcripts[-1].end_sec,
    )


def _record_segment(record: EvaluationRecord, audio: Any) -> AudioSegment:
    channel_count = (
        record.channel_count
        if record.channel_count is not None
        else int(getattr(audio, "num_channels", 1) or 1)
    )
    sample_rate_hz = (
        record.sample_rate_hz
        if record.sample_rate_hz is not None
        else _optional_int(getattr(audio, "sample_rate", None))
    )
    duration = _segment_duration(record, audio)
    return AudioSegment(
        audio_path=record.inference_audio_path,
        start_sec=record.start_sec,
        end_sec=record.end_sec,
        sample_rate_hz=sample_rate_hz,
        channel_index=record.channel_index,
        channel_count=channel_count,
        is_mono=channel_count == 1,
        duration_sec=duration,
    )


def _segment_duration(record: EvaluationRecord, audio: Any) -> float | None:
    if record.start_sec is not None and record.end_sec is not None:
        return record.end_sec - record.start_sec
    value = getattr(audio, "duration_sec", None)
    if value is None:
        value = record.duration_sec
    return float(value) if value is not None else None


def _runtime_dtype(run_config: Mapping[str, object] | None) -> str:
    runtime = _mapping_child(run_config, "runtime")
    return str(_mapping_get(runtime, "precision") or _mapping_get(run_config, "precision") or "float32")


def _asr_language(run_config: Mapping[str, object] | None) -> str | None:
    asr_config = _mapping_child(run_config, "asr")
    value = _mapping_get(asr_config, "language") or _mapping_get(run_config, "language")
    return str(value) if value is not None else None


def _mapping_child(config: Mapping[str, object] | None, key: str) -> Mapping[str, object] | None:
    value = _mapping_get(config, key)
    return value if isinstance(value, Mapping) else None


def _mapping_get(config: Mapping[str, object] | None, key: str) -> object | None:
    return config.get(key) if isinstance(config, Mapping) else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _runtime_counters(
    *,
    vad_enabled: bool,
    vad_region_count: int,
    segmentation_enabled: bool,
    segment_count: int,
    segmentation_sec: float | None,
    asr_base_enabled: bool,
    asr_segment_count: int,
) -> dict[str, object] | None:
    counters: dict[str, object] = {}
    if vad_enabled:
        counters["vad_region_count"] = vad_region_count
    if segmentation_enabled:
        counters["segment_count"] = segment_count
        counters["segmentation_sec"] = segmentation_sec
    if asr_base_enabled:
        counters["asr_segment_count"] = asr_segment_count
    return counters or None
