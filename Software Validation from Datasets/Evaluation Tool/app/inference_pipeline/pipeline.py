"""Modular inference pipeline invoked by the Evaluation Tool runner."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, is_dataclass, replace
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
from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationUnavailableError,
    build_diarizer_from_config,
    speaker_turns_to_rttm_lines,
    speaker_turns_to_speech_regions,
    write_turns_jsonable,
)
from app.inference_pipeline.enrollment.schema import EnrollmentDatabase
from app.inference_pipeline.enrollment.store import load_enrollment_db
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.runtime.stats import RuntimeAccumulator, runtime_diagnostics
from app.inference_pipeline.realtime.speaker_state import SpeakerEvidenceAccumulator
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
from app.inference_pipeline.vad.base import (
    VADBase,
    build_vad_from_config,
    write_regions_jsonable,
)
from app.inference_pipeline.typing import JsonObject
from app.resource_telemetry.context import telemetry_span


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
    diarizer: DiarizationBase | None = None
    speaker_embedding: SpeakerEmbeddingBase | None = None
    speaker_matcher: SpeakerMatcherBase | None = None
    enrollment_db: EnrollmentDatabase | Mapping[str, object] | None = None
    device: str = "cpu"
    diagnostics_enabled: bool = True
    speaker_evidence_params: Mapping[str, object] | None = None

    last_diagnostics: JsonObject | None = None
    last_segment_diarization_labels: tuple[str | None, ...] = ()
    last_speaker_evidence_updates: tuple[JsonObject, ...] = ()

    @classmethod
    def with_dummy_components(
        cls,
        vad: VADBase | None = None,
        segmenter: SegmenterBase | None = None,
        diarizer: DiarizationBase | None = None,
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
        selected_diarizer = diarizer
        if selected_diarizer is None and config is not None:
            selected_diarizer = build_diarizer_from_config(config)
        selected_asr = asr
        if selected_asr is None and config is not None:
            selected_asr = build_asr_from_config(config)
        return cls(
            audio_reader=DummyAudioReader(),
            asr=selected_asr or DummyASRComponent(),
            speaker_labeler=DummySpeakerLabeler(),
            vad=selected_vad,
            segmenter=selected_segmenter,
            diarizer=selected_diarizer,
        )

    @classmethod
    def from_config(
        cls, config: PipelineConfig | Mapping[str, object]
    ) -> "PipelineRunner":
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
            diarizer=build_diarizer_from_config(pipeline_config),
            speaker_embedding=build_speaker_embedding_from_config(pipeline_config),
            speaker_matcher=build_speaker_matcher_from_config(pipeline_config),
            enrollment_db=_load_enrollment_database(pipeline_config),
            device=pipeline_config.runtime.device,
            speaker_evidence_params=_speaker_evidence_params(pipeline_config),
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
        telemetry_ids = {
            "recording_id": evaluation_record.recording_id,
            "utt_id": evaluation_record.utt_id,
        }
        self.last_segment_diarization_labels = ()
        self.last_speaker_evidence_updates = ()

        with telemetry_span(
            "audio_loading", phase="per_item", identifiers=telemetry_ids
        ):
            with accumulator.stage("audio_load"):
                audio = self.audio_reader.load(evaluation_record, run_config)

        vad_regions = ()
        if self.vad is not None:
            with telemetry_span("vad", phase="per_item", identifiers=telemetry_ids):
                with accumulator.stage("vad"):
                    vad_regions = tuple(self.vad.detect(audio))

        diarization_turns = ()
        diarization_warnings: tuple[str, ...] = ()
        if self.diarizer is not None:
            try:
                with telemetry_span(
                    "diarization",
                    phase="per_item",
                    identifiers=telemetry_ids,
                    cuda=self.device == "cuda",
                ):
                    with accumulator.stage("diarization"):
                        diarization_turns = tuple(self.diarizer.diarize(audio))
            except DiarizationUnavailableError as exc:
                diarization_warnings = (f"diarization unavailable: {exc}",)
                if logger is not None:
                    logger.warning(
                        "Diarization unavailable for recording_id=%s utt_id=%s: %s",
                        evaluation_record.recording_id,
                        evaluation_record.utt_id,
                        exc,
                    )

        segments = self._segments(
            evaluation_record,
            vad_regions,
            diarization_turns,
            audio,
            accumulator,
        )

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
            segment_predictions = self._apply_diarization_labels(
                evaluation_record,
                segment_predictions,
                diarization_turns,
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
            diarization_enabled=self.diarizer is not None,
            diarization_turn_count=len(diarization_turns),
            diarization_overlap_turn_count=sum(
                1 for turn in diarization_turns if getattr(turn, "is_overlap", False)
            ),
            diarization_warning_count=len(diarization_warnings),
            segmentation_enabled=self.segmenter is not None,
            segment_count=len(segments),
            segmentation_sec=accumulator.stages.get("segmentation"),
            asr_base_enabled=isinstance(self.asr, ASRBase),
            asr_segment_count=len(segment_predictions)
            if isinstance(self.asr, ASRBase)
            else 1,
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
            model_versions=_model_versions(
                self.asr, self.speaker_embedding, self.diarizer
            ),
        )
        speaker_warnings = _speaker_configuration_warnings(
            self.speaker_matcher,
            self.enrollment_db,
        )
        diagnostics = {
            **assembly.diagnostics,
            "vad_regions": write_regions_jsonable(vad_regions),
            "diarization_turns": write_turns_jsonable(diarization_turns),
            "diarization_rttm_lines": speaker_turns_to_rttm_lines(
                evaluation_record.recording_id,
                diarization_turns,
                time_offset_sec=evaluation_record.start_sec or 0.0,
            ),
            "diarization_timebase": {
                "turns": "record_relative",
                "rttm": "recording_absolute",
                "record_offset_sec": evaluation_record.start_sec or 0.0,
            },
            "diarization_warnings": list(diarization_warnings),
            "segment_diarization_labels": list(self.last_segment_diarization_labels),
            "speaker_evidence_updates": list(self.last_speaker_evidence_updates),
            "speaker_warnings": list(speaker_warnings),
            "runtime_stats": runtime_diagnostics(
                runtime_stats,
                audio_duration_sec=_audio_duration(evaluation_record, audio),
            ),
            "asr_backend_runtime": (
                self.asr.last_runtime_stats.to_jsonable()
                if isinstance(self.asr, ASRBase)
                and self.asr.last_runtime_stats is not None
                else None
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
            warnings=(*assembly.warnings, *diarization_warnings, *speaker_warnings),
        )

    def _segments(
        self,
        record: EvaluationRecord,
        vad_regions: Sequence[object],
        diarization_turns: Sequence[object],
        audio: Any,
        accumulator: RuntimeAccumulator,
    ) -> tuple[AudioSegment, ...]:
        if self.segmenter is None:
            return (_record_segment(record, audio),)

        identifiers = {"recording_id": record.recording_id, "utt_id": record.utt_id}
        with telemetry_span("segmentation", phase="per_item", identifiers=identifiers):
            with accumulator.stage("segmentation"):
                if (
                    diarization_turns
                    and getattr(self.segmenter, "name", None) == "vad_chunks"
                ):
                    labeled_segments: list[tuple[AudioSegment, str]] = []
                    for turn in diarization_turns:
                        regions = speaker_turns_to_speech_regions((turn,))
                        labeled_segments.extend(
                            (segment, str(getattr(turn, "speaker_turn_label")))
                            for segment in self.segmenter.segment(
                                record, regions, audio
                            )
                        )
                    labeled_segments.sort(
                        key=lambda item: (
                            _segment_start(item[0]),
                            _segment_end(item[0]),
                            item[1],
                        )
                    )
                    segments = tuple(item[0] for item in labeled_segments)
                    self.last_segment_diarization_labels = tuple(
                        item[1] for item in labeled_segments
                    )
                else:
                    segmentation_regions = (
                        tuple(speaker_turns_to_speech_regions(diarization_turns))
                        if diarization_turns
                        else vad_regions
                    )
                    segments = tuple(
                        self.segmenter.segment(record, segmentation_regions, audio)
                    )
                    self.last_segment_diarization_labels = tuple(None for _ in segments)
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
            with telemetry_span(
                "asr",
                phase="per_item",
                identifiers={
                    "recording_id": record.recording_id,
                    "utt_id": record.utt_id,
                },
            ):
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
            with telemetry_span(
                "asr",
                phase="per_item",
                identifiers={
                    "recording_id": record.recording_id,
                    "utt_id": record.utt_id,
                    "segment_index": index,
                },
            ):
                transcript = self.asr.transcribe(segment, context)
            predictions.append(
                SegmentPrediction(
                    segment_index=index,
                    segment=segment,
                    transcript=transcript,
                    raw_text=getattr(self.asr, "last_raw_text", None)
                    or transcript.text,
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
                identifiers = {
                    "recording_id": record.recording_id,
                    "utt_id": record.utt_id,
                    "segment_index": prediction.segment_index,
                }
                with telemetry_span(
                    "speaker_embedding",
                    phase="per_item",
                    identifiers=identifiers,
                ):
                    embedding = self.speaker_embedding.embed(
                        prediction.segment,
                        embedding_context,
                    )
                if self.speaker_matcher is not None:
                    with telemetry_span(
                        "speaker_matching",
                        phase="per_item",
                        identifiers=identifiers,
                    ):
                        decision = self.speaker_matcher.match(
                            embedding,
                            self.enrollment_db or EnrollmentDatabase.empty(),
                        )
                else:
                    decision = None
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
            return self._apply_speaker_evidence(tuple(labeled))

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
        with telemetry_span(
            "speaker_matching",
            phase="per_item",
            identifiers={"recording_id": record.recording_id, "utt_id": record.utt_id},
        ):
            decision = self.speaker_labeler.label(
                record, audio, whole_transcript, run_config
            )
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

    def _apply_speaker_evidence(
        self,
        predictions: Sequence[SegmentPrediction],
    ) -> tuple[SegmentPrediction, ...]:
        params = dict(self.speaker_evidence_params or {})
        if not params or not bool(params.get("enabled", True)):
            return tuple(predictions)
        accumulator = SpeakerEvidenceAccumulator(
            confirmation_windows=int(params.get("confirmation_windows", 3)),
            confirmation_threshold=int(params.get("confirmation_threshold", 2)),
            score_threshold=float(params.get("score_threshold", 0.5)),
            unknown_label=str(params.get("unknown_label") or "Unknown"),
        )
        unknown_label = accumulator.unknown_label
        updated_predictions: list[SegmentPrediction] = []
        updates: list[JsonObject] = []
        for prediction in predictions:
            decision = prediction.speaker_decision
            scores = _accepted_speaker_scores(decision)
            update = accumulator.add_evidence(scores)
            updates.append(update.to_jsonable())
            updated_decision = _decision_with_speaker_evidence(
                decision,
                update,
                unknown_label=unknown_label,
            )
            updated_predictions.append(
                replace(prediction, speaker_decision=updated_decision)
            )
        self.last_speaker_evidence_updates = tuple(updates)
        return tuple(updated_predictions)

    def _apply_diarization_labels(
        self,
        record: EvaluationRecord,
        predictions: Sequence[SegmentPrediction],
        diarization_turns: Sequence[object],
    ) -> tuple[SegmentPrediction, ...]:
        if not predictions or not diarization_turns:
            return tuple(predictions)
        updated: list[SegmentPrediction] = []
        for prediction in predictions:
            if _has_named_speaker_decision(prediction.speaker_decision):
                updated.append(prediction)
                continue
            label = (
                self.last_segment_diarization_labels[prediction.segment_index]
                if prediction.segment_index < len(self.last_segment_diarization_labels)
                else None
            )
            turn = _turn_for_segment(
                prediction.segment,
                diarization_turns,
                record_start_sec=record.start_sec or 0.0,
                preferred_label=label,
            )
            if turn is None:
                updated.append(prediction)
                continue
            decision = _anonymous_diarization_decision(
                prediction.speaker_decision,
                turn,
            )
            updated.append(replace(prediction, speaker_decision=decision))
        return tuple(updated)


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


def _speaker_evidence_params(config: PipelineConfig) -> Mapping[str, object] | None:
    matching = config.components.get("speaker_matching")
    params = matching.params if matching is not None else {}
    value = (params or {}).get("temporal_evidence")
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ContractValidationError(
            "speaker_matching.params.temporal_evidence must be a mapping"
        )
    data = dict(value)
    allowed = {
        "enabled",
        "confirmation_windows",
        "confirmation_threshold",
        "score_threshold",
        "unknown_label",
    }
    unknown = sorted(str(key) for key in data if key not in allowed)
    if unknown:
        raise ContractValidationError(
            "speaker_matching.params.temporal_evidence contains unsupported keys: "
            + ", ".join(unknown)
        )

    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ContractValidationError(
            "speaker_matching.params.temporal_evidence.enabled must be a boolean"
        )
    confirmation_windows = data.get("confirmation_windows", 3)
    confirmation_threshold = data.get("confirmation_threshold", 2)
    for key, candidate in (
        ("confirmation_windows", confirmation_windows),
        ("confirmation_threshold", confirmation_threshold),
    ):
        if isinstance(candidate, bool) or not isinstance(candidate, int):
            raise ContractValidationError(
                f"speaker_matching.params.temporal_evidence.{key} must be an integer"
            )
    score_threshold = data.get("score_threshold", 0.5)
    if isinstance(score_threshold, bool) or not isinstance(
        score_threshold, (int, float)
    ):
        raise ContractValidationError(
            "speaker_matching.params.temporal_evidence.score_threshold must be a number"
        )
    score_threshold = float(score_threshold)
    if not math.isfinite(score_threshold) or score_threshold < 0.0:
        raise ContractValidationError(
            "speaker_matching.params.temporal_evidence.score_threshold must be finite "
            "and >= 0"
        )
    unknown_label = data.get("unknown_label", "Unknown")
    if not isinstance(unknown_label, str) or not unknown_label.strip():
        raise ContractValidationError(
            "speaker_matching.params.temporal_evidence.unknown_label must be a "
            "non-empty string"
        )

    try:
        SpeakerEvidenceAccumulator(
            confirmation_windows=confirmation_windows,
            confirmation_threshold=confirmation_threshold,
            score_threshold=score_threshold,
            unknown_label=unknown_label.strip(),
        )
    except ValueError as exc:
        raise ContractValidationError(
            f"Invalid speaker_matching.params.temporal_evidence: {exc}"
        ) from exc
    return {
        "enabled": enabled,
        "confirmation_windows": confirmation_windows,
        "confirmation_threshold": confirmation_threshold,
        "score_threshold": score_threshold,
        "unknown_label": unknown_label.strip(),
    }


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
    diarizer: DiarizationBase | None,
) -> JsonObject | None:
    versions: JsonObject = {}
    if isinstance(asr, ASRBase):
        versions["asr"] = getattr(asr, "model_name", asr.name)
    else:
        versions["asr"] = type(asr).__name__
    if diarizer is not None:
        versions["diarization"] = getattr(diarizer, "model_name", diarizer.name)
    if speaker_embedding is not None:
        versions["speaker_embedding"] = speaker_embedding.model_name
    return versions or None


def _mapping_child(
    config: Mapping[str, object] | None, key: str
) -> Mapping[str, object] | None:
    value = _mapping_get(config, key)
    return value if isinstance(value, Mapping) else None


def _mapping_get(config: Mapping[str, object] | None, key: str) -> object | None:
    return config.get(key) if isinstance(config, Mapping) else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _segment_start(segment: AudioSegment) -> float:
    return float(segment.start_sec) if segment.start_sec is not None else float("inf")


def _segment_end(segment: AudioSegment) -> float:
    return float(segment.end_sec) if segment.end_sec is not None else float("inf")


def _turn_for_segment(
    segment: AudioSegment,
    turns: Sequence[object],
    *,
    record_start_sec: float,
    preferred_label: str | None,
) -> object | None:
    if segment.start_sec is None or segment.end_sec is None:
        return None
    overlaps: dict[str, float] = {}
    representative: dict[str, object] = {}
    for turn in turns:
        label = str(getattr(turn, "speaker_turn_label", "") or "")
        if not label:
            continue
        start = record_start_sec + float(getattr(turn, "start_sec"))
        end = record_start_sec + float(getattr(turn, "end_sec"))
        overlap = max(
            0.0,
            min(float(segment.end_sec), end) - max(float(segment.start_sec), start),
        )
        if overlap <= 0:
            continue
        overlaps[label] = overlaps.get(label, 0.0) + overlap
        current = representative.get(label)
        if current is None or overlap > _turn_overlap(
            segment, current, record_start_sec
        ):
            representative[label] = turn

    if preferred_label and preferred_label in representative:
        return representative[preferred_label]
    ranked = sorted(overlaps.items(), key=lambda item: (-item[1], item[0]))
    if not ranked:
        return None
    if len(ranked) > 1 and abs(ranked[0][1] - ranked[1][1]) <= 1e-9:
        # A full-record or merged segment with equal evidence for multiple
        # anonymous speakers cannot be attributed safely.
        return None
    return representative[ranked[0][0]]


def _turn_overlap(
    segment: AudioSegment,
    turn: object,
    record_start_sec: float,
) -> float:
    if segment.start_sec is None or segment.end_sec is None:
        return 0.0
    start = record_start_sec + float(getattr(turn, "start_sec"))
    end = record_start_sec + float(getattr(turn, "end_sec"))
    return max(
        0.0,
        min(float(segment.end_sec), end) - max(float(segment.start_sec), start),
    )


def _accepted_speaker_scores(decision: object | None) -> dict[str, float]:
    if decision is None:
        return {}
    accepted = (
        decision.get("accepted")
        if isinstance(decision, Mapping)
        else getattr(decision, "accepted", False)
    )
    if not bool(accepted):
        return {}
    raw_scores = (
        decision.get("scores", ())
        if isinstance(decision, Mapping)
        else getattr(decision, "scores", ())
    )
    scores: dict[str, float] = {}
    for score in raw_scores or ():
        if isinstance(score, Mapping):
            label = score.get("speaker_label")
            value = score.get("score")
        else:
            label = getattr(score, "speaker_label", None)
            value = getattr(score, "score", None)
        if label is None or value is None:
            continue
        scores[str(label)] = float(value)
    if scores:
        return scores
    label = (
        decision.get("speaker_label")
        if isinstance(decision, Mapping)
        else getattr(decision, "speaker_label", None)
    )
    confidence = (
        decision.get("confidence")
        if isinstance(decision, Mapping)
        else getattr(decision, "confidence", None)
    )
    if label is not None and confidence is not None:
        scores[str(label)] = float(confidence)
    return scores


def _decision_with_speaker_evidence(
    decision: object | None,
    update: object,
    *,
    unknown_label: str,
) -> object | None:
    if decision is None:
        return None
    status = str(getattr(update, "status"))
    confirmed = status == "confirmed"
    label = str(getattr(update, "speaker_label")) if confirmed else unknown_label
    method = (
        decision.get("method")
        if isinstance(decision, Mapping)
        else getattr(decision, "method", None)
    )
    previous_notes = (
        decision.get("notes")
        if isinstance(decision, Mapping)
        else getattr(decision, "notes", None)
    )
    notes = "; ".join(
        value
        for value in (
            str(previous_notes) if previous_notes else None,
            f"temporal speaker evidence status={status}",
        )
        if value
    )
    if is_dataclass(decision):
        changes: dict[str, object] = {
            "speaker_label": label,
            "method": f"{method or 'speaker_matching'}+temporal_evidence",
            "notes": notes,
        }
        if hasattr(decision, "accepted"):
            changes["accepted"] = confirmed
        if not confirmed and hasattr(decision, "threshold_decision"):
            changes["threshold_decision"] = "temporal_confirmation_pending"
        return replace(decision, **changes)
    if isinstance(decision, Mapping):
        updated = dict(decision)
        updated.update(
            {
                "speaker_label": label,
                "method": f"{method or 'speaker_matching'}+temporal_evidence",
                "notes": notes,
            }
        )
        if "accepted" in updated:
            updated["accepted"] = confirmed
        if not confirmed and "threshold_decision" in updated:
            updated["threshold_decision"] = "temporal_confirmation_pending"
        return updated
    return SpeakerDecision(
        speaker_label=label,
        confidence=_optional_float(getattr(decision, "confidence", None)),
        method=f"{method or 'speaker_matching'}+temporal_evidence",
        notes=notes,
    )


def _has_named_speaker_decision(decision: object | None) -> bool:
    if decision is None:
        return False
    accepted = (
        decision.get("accepted")
        if isinstance(decision, Mapping)
        else getattr(decision, "accepted", None)
    )
    if accepted is True:
        return True
    label = (
        decision.get("speaker_label")
        if isinstance(decision, Mapping)
        else getattr(decision, "speaker_label", None)
    )
    if label is None:
        return False
    return str(label).strip().casefold() not in {"", "unknown", "unavailable"}


def _anonymous_diarization_decision(
    previous_decision: object | None,
    turn: object,
) -> object:
    label = str(getattr(turn, "speaker_turn_label"))
    confidence = _optional_float(getattr(turn, "confidence", None))
    source = str(getattr(turn, "source", "") or "diarization")
    method = f"anonymous_diarization:{source}"
    fallback_note = "Anonymous within-record speaker cluster; not an enrolled identity."
    if previous_decision is None:
        return SpeakerDecision(
            speaker_label=label,
            confidence=confidence,
            method=method,
            notes=fallback_note,
        )

    previous_notes = (
        previous_decision.get("notes")
        if isinstance(previous_decision, Mapping)
        else getattr(previous_decision, "notes", None)
    )
    notes = "; ".join(
        value
        for value in (
            str(previous_notes) if previous_notes else None,
            fallback_note,
        )
        if value
    )
    if is_dataclass(previous_decision):
        return replace(
            previous_decision,
            speaker_label=label,
            confidence=confidence,
            method=f"{getattr(previous_decision, 'method', None) or 'speaker_matching'}+{method}",
            notes=notes,
        )
    if isinstance(previous_decision, Mapping):
        updated = dict(previous_decision)
        updated.update(
            {
                "speaker_label": label,
                "confidence": confidence,
                "method": f"{previous_decision.get('method') or 'speaker_matching'}+{method}",
                "notes": notes,
            }
        )
        return updated
    return SpeakerDecision(
        speaker_label=label,
        confidence=confidence,
        method=method,
        notes=notes,
    )


def _speaker_configuration_warnings(
    matcher: SpeakerMatcherBase | None,
    enrollment_db: EnrollmentDatabase | Mapping[str, object] | None,
) -> tuple[str, ...]:
    if matcher is None or getattr(matcher, "name", "") == "no_op_speaker_matching":
        return ()
    if isinstance(enrollment_db, Mapping):
        speakers = enrollment_db.get("speakers") or ()
    else:
        speakers = (
            getattr(enrollment_db, "speakers", ()) if enrollment_db is not None else ()
        )
    if speakers:
        return ()
    return (
        "speaker matching is enabled but the enrollment database is empty or missing; "
        "named-speaker decisions will remain Unknown until identities are enrolled",
    )


def _runtime_counters(
    *,
    vad_enabled: bool,
    vad_region_count: int,
    diarization_enabled: bool,
    diarization_turn_count: int,
    diarization_overlap_turn_count: int,
    diarization_warning_count: int,
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
    if diarization_enabled:
        counters["diarization_turn_count"] = diarization_turn_count
        counters["diarization_overlap_turn_count"] = diarization_overlap_turn_count
        if diarization_warning_count:
            counters["diarization_warning_count"] = diarization_warning_count
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
