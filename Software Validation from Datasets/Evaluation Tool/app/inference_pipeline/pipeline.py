"""Modular inference pipeline invoked by the Evaluation Tool runner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from app.inference_pipeline.asr.base import ASRBase, ASRContext, build_asr_from_config
from app.inference_pipeline.audio_io import load_audio
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import (
    ASRTranscript,
    AudioSegment,
    EvaluationRecord,
    PipelineOutput,
    SpeakerDecision,
)
from app.inference_pipeline.dummy_components import (
    DummyASRComponent,
    DummyAudioReader,
    DummySpeakerLabeler,
)
from app.inference_pipeline.enrollment.schema import EnrollmentDatabase
from app.inference_pipeline.enrollment.store import load_enrollment_db
from app.inference_pipeline.runtime.stats import RuntimeAccumulator, runtime_diagnostics
from app.inference_pipeline.segmentation.base import (
    SegmenterBase,
    build_segmenter_from_config,
)
from app.inference_pipeline.speaker_embedding.base import (
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
    build_speaker_embedding_from_config,
)
from app.inference_pipeline.speaker_matching.base import (
    SpeakerMatcherBase,
    build_speaker_matcher_from_config,
)
from app.inference_pipeline.transcript import SegmentPrediction, assemble_transcript
from app.inference_pipeline.vad.base import VADBase, build_vad_from_config
from app.inference_pipeline.typing import JsonObject


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


@dataclass(frozen=True)
class AudioLoaderAdapter:
    """Audio reader that uses the M3 PyTorch-native loader."""

    config: object | None = None

    def load(
        self,
        record: EvaluationRecord,
        run_config: Mapping[str, object] | None = None,
    ) -> Any:
        _ = run_config
        return load_audio(record.to_jsonable(), self.config)


@dataclass
class PipelineRunner:
    """Run one selected metadata row through swappable pipeline components."""

    audio_reader: AudioReader
    asr: ASRComponent | ASRBase
    speaker_labeler: SpeakerLabeler | None = None
    vad: VADBase | None = None
    segmenter: SegmenterBase | None = None
    speaker_embedding: SpeakerEmbeddingBase | None = None
    speaker_matcher: SpeakerMatcherBase | None = None
    enrollment_db: EnrollmentDatabase | Mapping[str, object] | None = None
    device: str = "cpu"
    diagnostics_enabled: bool = True

    last_diagnostics: JsonObject | None = None

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

    @classmethod
    def from_config(cls, config: PipelineConfig | Mapping[str, object]) -> "PipelineRunner":
        """Build the configured end-to-end pipeline without changing runner APIs."""

        pipeline_config = (
            config
            if isinstance(config, PipelineConfig)
            else PipelineConfig.from_mapping(config)
        )
        return cls(
            audio_reader=AudioLoaderAdapter(pipeline_config),
            asr=build_asr_from_config(pipeline_config) or DummyASRComponent(text=""),
            speaker_labeler=None,
            vad=build_vad_from_config(pipeline_config),
            segmenter=build_segmenter_from_config(pipeline_config),
            speaker_embedding=build_speaker_embedding_from_config(pipeline_config),
            speaker_matcher=build_speaker_matcher_from_config(pipeline_config),
            enrollment_db=_load_enrollment_database(pipeline_config),
            device=pipeline_config.runtime.device,
        )

    @classmethod
    def from_config_path(cls, path: Path | str) -> "PipelineRunner":
        """Build a pipeline from a YAML config path."""

        return cls.from_config(PipelineConfig.from_yaml_path(path))

    def predict(
        self,
        record: Mapping[str, object],
        config: Mapping[str, object] | None = None,
    ) -> PipelineOutput:
        """Run the pipeline for one Evaluation Tool metadata row."""

        return self._predict(record, config, logger=None)

    def run_one(
        self,
        record: Mapping[str, object],
        run_config: Mapping[str, object] | None = None,
        logger: logging.Logger | None = None,
    ) -> PipelineOutput:
        """Backward-compatible wrapper for existing runner bridge tests."""

        return self._predict(record, run_config, logger=logger)

    def _predict(
        self,
        record: Mapping[str, object],
        run_config: Mapping[str, object] | None,
        *,
        logger: logging.Logger | None,
    ) -> PipelineOutput:
        accumulator = RuntimeAccumulator(device=self.device)
        evaluation_record = EvaluationRecord.from_record(record)

        with accumulator.stage("audio_load"):
            audio = self.audio_reader.load(evaluation_record, run_config)

        vad_regions = ()
        if self.vad is not None:
            with accumulator.stage("vad"):
                vad_regions = tuple(self.vad.detect(audio))

        segments = self._segments(evaluation_record, vad_regions, audio, accumulator)

        with accumulator.stage("asr"):
            segment_predictions = self._transcribe_segments(
                evaluation_record,
                audio,
                segments,
                run_config,
            )

        if not segment_predictions:
            segment_predictions = ()

        with accumulator.stage("speaker"):
            segment_predictions = self._label_segments(
                evaluation_record,
                audio,
                segment_predictions,
                run_config,
            )

        with accumulator.stage("postprocess"):
            assembly = assemble_transcript(
                evaluation_record,
                segment_predictions,
                fallback_speaker_label=None,
            )

        counters = _runtime_counters(
            vad_enabled=self.vad is not None,
            vad_region_count=len(vad_regions),
            segmentation_enabled=self.segmenter is not None,
            segment_count=len(segments),
            segmentation_sec=accumulator.stages.get("segmentation"),
            asr_base_enabled=isinstance(self.asr, ASRBase),
            asr_segment_count=len(segment_predictions) if isinstance(self.asr, ASRBase) else 1,
            speaker_embedding_enabled=self.speaker_embedding is not None,
            speaker_matching_enabled=self.speaker_matcher is not None,
            speaker_decision_count=sum(
                1
                for prediction in segment_predictions
                if prediction.speaker_decision is not None
            ),
        )
        runtime_stats = accumulator.stats(
            counters=counters,
            model_versions=_model_versions(self.asr, self.speaker_embedding),
        )
        diagnostics = {
            **assembly.diagnostics,
            "runtime_stats": runtime_diagnostics(
                runtime_stats,
                audio_duration_sec=_audio_duration(evaluation_record, audio),
            ),
        }
        self.last_diagnostics = diagnostics

        if logger is not None:
            logger.debug(
                "Pipeline produced transcript for recording_id=%s utt_id=%s segments=%d",
                evaluation_record.recording_id,
                evaluation_record.utt_id,
                len(segment_predictions),
            )

        return PipelineOutput.from_record_and_transcript(
            record=evaluation_record,
            transcript=assembly.transcript,
            speaker_decision=assembly.speaker_decision,
            runtime_stats=runtime_stats,
            transcript_items=assembly.transcript_items,
            diagnostics=diagnostics if self.diagnostics_enabled else None,
            warnings=assembly.warnings,
        )

    def _segments(
        self,
        record: EvaluationRecord,
        vad_regions: Sequence[object],
        audio: Any,
        accumulator: RuntimeAccumulator,
    ) -> tuple[AudioSegment, ...]:
        if self.segmenter is None:
            return (_record_segment(record, audio),)

        with accumulator.stage("segmentation"):
            segments = tuple(self.segmenter.segment(record, vad_regions, audio))
        return segments

    def _transcribe_segments(
        self,
        record: EvaluationRecord,
        audio: Any,
        segments: Sequence[AudioSegment],
        run_config: Mapping[str, object] | None,
    ) -> tuple[SegmentPrediction, ...]:
        if not segments:
            return ()

        if not isinstance(self.asr, ASRBase):
            transcript = self.asr.transcribe(record, audio, run_config)
            return (
                SegmentPrediction(
                    segment_index=0,
                    segment=_record_segment(record, audio),
                    transcript=transcript,
                    raw_text=transcript.text,
                    normalized_text=transcript.text,
                ),
            )

        predictions: list[SegmentPrediction] = []
        for index, segment in enumerate(segments):
            context = ASRContext.from_record_segment(
                record,
                segment,
                segment_index=index,
                run_config=run_config,
                device=self.device,
                dtype=_runtime_dtype(run_config),
                language=_asr_language(run_config),
            )
            transcript = self.asr.transcribe(segment, context)
            predictions.append(
                SegmentPrediction(
                    segment_index=index,
                    segment=segment,
                    transcript=transcript,
                    raw_text=getattr(self.asr, "last_raw_text", None) or transcript.text,
                    normalized_text=(
                        getattr(self.asr, "last_normalized_text", None)
                        or transcript.text
                    ),
                )
            )
        return tuple(predictions)

    def _label_segments(
        self,
        record: EvaluationRecord,
        audio: Any,
        segment_predictions: Sequence[SegmentPrediction],
        run_config: Mapping[str, object] | None,
    ) -> tuple[SegmentPrediction, ...]:
        if not segment_predictions:
            return ()

        if self.speaker_embedding is not None:
            labeled: list[SegmentPrediction] = []
            for prediction in segment_predictions:
                embedding_context = SpeakerEmbeddingContext.from_record_segment(
                    record,
                    prediction.segment,
                    segment_index=prediction.segment_index,
                    run_config=run_config,
                    device=self.device,
                    dtype=_runtime_dtype(run_config),
                )
                embedding = self.speaker_embedding.embed(
                    prediction.segment,
                    embedding_context,
                )
                decision = (
                    self.speaker_matcher.match(
                        embedding,
                        self.enrollment_db or EnrollmentDatabase.empty(),
                    )
                    if self.speaker_matcher is not None
                    else None
                )
                labeled.append(
                    SegmentPrediction(
                        segment_index=prediction.segment_index,
                        segment=prediction.segment,
                        transcript=prediction.transcript,
                        speaker_decision=decision,
                        raw_text=prediction.raw_text,
                        normalized_text=prediction.normalized_text,
                    )
                )
            return tuple(labeled)

        if self.speaker_labeler is None:
            return tuple(segment_predictions)

        whole_transcript = ASRTranscript(
            text=" ".join(
                prediction.transcript.text
                for prediction in segment_predictions
                if prediction.transcript.text
            ).strip(),
            start_sec=record.start_sec,
            end_sec=record.end_sec,
        )
        decision = self.speaker_labeler.label(record, audio, whole_transcript, run_config)
        return tuple(
            SegmentPrediction(
                segment_index=prediction.segment_index,
                segment=prediction.segment,
                transcript=prediction.transcript,
                speaker_decision=decision,
                raw_text=prediction.raw_text,
                normalized_text=prediction.normalized_text,
            )
            for prediction in segment_predictions
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


def _audio_duration(record: EvaluationRecord, audio: Any) -> float | None:
    value = getattr(audio, "duration_sec", None)
    if value is None:
        value = record.duration_sec
    if value is None and record.start_sec is not None and record.end_sec is not None:
        value = record.end_sec - record.start_sec
    return float(value) if value is not None else None


def _runtime_dtype(run_config: Mapping[str, object] | None) -> str:
    runtime = _mapping_child(run_config, "runtime")
    return str(
        _mapping_get(runtime, "precision")
        or _mapping_get(run_config, "precision")
        or "float32"
    )


def _asr_language(run_config: Mapping[str, object] | None) -> str | None:
    asr_config = _mapping_child(run_config, "asr")
    value = _mapping_get(asr_config, "language") or _mapping_get(run_config, "language")
    return str(value) if value is not None else None


def _load_enrollment_database(config: PipelineConfig) -> EnrollmentDatabase:
    path = _enrollment_db_path(config)
    return load_enrollment_db(path) if path is not None else load_enrollment_db()


def _enrollment_db_path(config: PipelineConfig) -> Path | None:
    matching = config.components.get("speaker_matching")
    params = matching.params if matching is not None else {}
    value = (params or {}).get("enrollment_db_path")
    if value is None or str(value).strip() == "":
        return None
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    tool_root = Path(__file__).resolve().parents[2]
    return tool_root / path


def _model_versions(
    asr: ASRComponent | ASRBase,
    speaker_embedding: SpeakerEmbeddingBase | None,
) -> JsonObject | None:
    versions: JsonObject = {}
    if isinstance(asr, ASRBase):
        versions["asr"] = getattr(asr, "model_name", asr.name)
    else:
        versions["asr"] = type(asr).__name__
    if speaker_embedding is not None:
        versions["speaker_embedding"] = speaker_embedding.model_name
    return versions or None


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
    speaker_embedding_enabled: bool,
    speaker_matching_enabled: bool,
    speaker_decision_count: int,
) -> dict[str, object] | None:
    counters: dict[str, object] = {}
    if vad_enabled:
        counters["vad_region_count"] = vad_region_count
    if segmentation_enabled:
        counters["segment_count"] = segment_count
        counters["segmentation_sec"] = segmentation_sec
    if asr_base_enabled:
        counters["asr_segment_count"] = asr_segment_count
    if speaker_embedding_enabled:
        counters["speaker_embedding_count"] = asr_segment_count
    if speaker_matching_enabled:
        counters["speaker_decision_count"] = speaker_decision_count
    return counters or None
