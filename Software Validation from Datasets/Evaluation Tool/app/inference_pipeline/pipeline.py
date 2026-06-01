"""End-to-end inference pipeline runner for Evaluation Tool records."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import yaml

from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    NoOpASR,
    build_asr_from_config,
)
from app.inference_pipeline.audio_io import load_audio
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
from app.inference_pipeline.enrollment.store import load_enrollment_db
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.runtime.stats import StageRuntimeTracker
from app.inference_pipeline.segmentation.base import (
    SegmenterBase,
    build_segmenter_from_config,
    write_segments_jsonable,
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
from app.inference_pipeline.transcript.assembler import (
    SegmentPrediction,
    TranscriptAssembler,
)
from app.inference_pipeline.typing import JsonObject
from app.inference_pipeline.vad.base import (
    VADBase,
    build_vad_from_config,
    write_regions_jsonable,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PIPELINE_CONFIG = TOOL_ROOT / "configs" / "inference" / "e2e_named_transcript.yaml"


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
class AudioFileReader:
    """Load ``record["inference_audio_path"]`` with the pipeline audio loader."""

    def load(
        self,
        record: EvaluationRecord,
        run_config: Mapping[str, object] | None = None,
    ) -> Any:
        return load_audio(record.to_jsonable(), run_config)


@dataclass
class PipelineRunner:
    """Run one selected metadata row through swappable pipeline components."""

    audio_reader: AudioReader | None = None
    asr: ASRComponent | ASRBase | None = None
    speaker_labeler: SpeakerLabeler | None = None
    vad: VADBase | None = None
    segmenter: SegmenterBase | None = None
    speaker_embedding: SpeakerEmbeddingBase | None = None
    speaker_matcher: SpeakerMatcherBase | None = None
    enrollment_db: object | None = None
    device: str = "cpu"
    transcript_assembler: TranscriptAssembler = field(default_factory=TranscriptAssembler)
    last_diagnostics: JsonObject | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, object] | str | Path | None = None,
    ) -> "PipelineRunner":
        """Build the M13 pipeline from a YAML-backed inference config."""

        pipeline_config = pipeline_config_mapping(config)
        runtime = _mapping_child(pipeline_config, "runtime")
        device = str(_mapping_get(runtime, "device") or "cpu")
        return cls(
            audio_reader=AudioFileReader(),
            asr=build_asr_from_config(pipeline_config) or NoOpASR(),
            speaker_labeler=None,
            vad=build_vad_from_config(pipeline_config),
            segmenter=build_segmenter_from_config(pipeline_config),
            speaker_embedding=build_speaker_embedding_from_config(pipeline_config),
            speaker_matcher=build_speaker_matcher_from_config(pipeline_config),
            enrollment_db=_load_enrollment_db_from_config(pipeline_config),
            device=device,
        )

    @classmethod
    def with_dummy_components(
        cls,
        vad: VADBase | None = None,
        segmenter: SegmenterBase | None = None,
        asr: ASRComponent | ASRBase | None = None,
        config: object | None = None,
    ) -> "PipelineRunner":
        """Build the M4-compatible dummy pipeline without loading models."""

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

    def predict(
        self,
        record: Mapping[str, object],
        config: Mapping[str, object] | None = None,
    ) -> PipelineOutput:
        """Run the end-to-end pipeline for one Evaluation Tool metadata row."""

        run_config = dict(config or {})
        if self.audio_reader is None and self.asr is None and "components" in run_config:
            configured = PipelineRunner.from_config(run_config)
            output = configured.predict(record, run_config)
            self.last_diagnostics = configured.last_diagnostics
            return output

        evaluation_record = EvaluationRecord.from_record(record)
        tracker = StageRuntimeTracker(device=self.device)
        audio_reader = self.audio_reader or AudioFileReader()
        asr = self.asr or build_asr_from_config(run_config) or NoOpASR()

        with tracker.stage("audio_load"):
            audio = audio_reader.load(evaluation_record, run_config)

        vad_regions = ()
        if self.vad is not None:
            with tracker.stage("vad"):
                vad_regions = tuple(self.vad.detect(audio))

        segments = ()
        if self.segmenter is not None:
            with tracker.stage("segmentation"):
                segments = tuple(self.segmenter.segment(evaluation_record, vad_regions, audio))

        active_segments = _active_segments(
            evaluation_record,
            audio,
            segments,
            segmentation_enabled=self.segmenter is not None,
        )

        with tracker.stage("asr"):
            segment_predictions = _transcribe_segments(
                asr,
                evaluation_record,
                audio,
                active_segments,
                run_config,
                self.device,
                segmentation_enabled=self.segmenter is not None,
            )

        segment_predictions = self._attach_speaker_decisions(
            evaluation_record,
            audio,
            segment_predictions,
            run_config,
            tracker,
        )

        with tracker.stage("postprocess"):
            assembled = self.transcript_assembler.assemble(
                evaluation_record,
                segment_predictions,
            )

        counters = _runtime_counters(
            vad_enabled=self.vad is not None,
            vad_region_count=len(vad_regions),
            segmentation_enabled=self.segmenter is not None,
            segment_count=len(segments),
            segmentation_sec=tracker.stage_seconds.get("segmentation"),
            asr_base_enabled=isinstance(asr, ASRBase),
            asr_segment_count=len(segment_predictions) if isinstance(asr, ASRBase) else 1,
            speaker_embedding_enabled=self.speaker_embedding is not None,
            speaker_embedding_count=sum(
                1 for item in segment_predictions if item.embedding is not None
            ),
            speaker_matching_enabled=self.speaker_matcher is not None,
            speaker_decision_count=sum(
                1 for item in segment_predictions if item.speaker_decision is not None
            ),
        )
        runtime_stats = tracker.to_runtime_stats(
            counters=counters,
            model_versions=_model_versions(
                asr=asr,
                vad=self.vad,
                segmenter=self.segmenter,
                speaker_embedding=self.speaker_embedding,
                speaker_matcher=self.speaker_matcher,
            ),
        )
        output = PipelineOutput(
            recording_id=evaluation_record.recording_id,
            utt_id=evaluation_record.utt_id,
            start_sec=evaluation_record.start_sec,
            end_sec=evaluation_record.end_sec,
            speaker_label=assembled.speaker_label,
            text=assembled.transcript.text,
            transcript=assembled.transcript,
            transcript_items=assembled.transcript_items,
            runtime_stats=runtime_stats,
            warnings=assembled.warnings,
        ).validate_identity(evaluation_record)
        self.last_diagnostics = _diagnostics_row(
            record=evaluation_record,
            output=output,
            audio=audio,
            vad_regions=vad_regions,
            segments=segments,
            segment_predictions=segment_predictions,
            tracker=tracker,
            raw_text=assembled.raw_text,
            normalized_text=assembled.transcript.text,
            chronological_violations=assembled.chronological_ordering_violations,
            duplicate_text_tokens_removed=assembled.duplicate_text_tokens_removed,
        )
        return output

    def run_one(
        self,
        record: Mapping[str, object],
        run_config: Mapping[str, object] | None = None,
        logger: logging.Logger | None = None,
    ) -> PipelineOutput:
        """Backward-compatible wrapper for older milestone tests."""

        output = self.predict(record, run_config)
        if logger is not None:
            logger.debug(
                "Pipeline produced transcript for recording_id=%s utt_id=%s",
                output.recording_id,
                output.utt_id,
            )
        return output

    def _attach_speaker_decisions(
        self,
        record: EvaluationRecord,
        audio: Any,
        segment_predictions: tuple[SegmentPrediction, ...],
        run_config: Mapping[str, object],
        tracker: StageRuntimeTracker,
    ) -> tuple[SegmentPrediction, ...]:
        if not segment_predictions:
            return segment_predictions

        updated = list(segment_predictions)
        embeddings: list[object | None] = [None] * len(updated)
        if self.speaker_embedding is not None:
            with tracker.stage("speaker_embedding"):
                for index, prediction in enumerate(updated):
                    context = SpeakerEmbeddingContext.from_record_segment(
                        record,
                        prediction.segment,
                        segment_index=prediction.segment_index,
                        run_config=run_config,
                        device=self.device,
                        dtype=_runtime_dtype(run_config),
                    )
                    embeddings[index] = self.speaker_embedding.embed(
                        prediction.segment,
                        context,
                    )

        decisions: list[object | None] = [None] * len(updated)
        if self.speaker_matcher is not None:
            with tracker.stage("speaker_matching"):
                enrollment_db = self.enrollment_db
                if enrollment_db is None:
                    enrollment_db = _load_enrollment_db_from_config(run_config)
                for index, embedding in enumerate(embeddings):
                    if embedding is None:
                        continue
                    decisions[index] = self.speaker_matcher.match(embedding, enrollment_db)
        elif self.speaker_labeler is not None:
            with tracker.stage("speaker_labeling"):
                for index, prediction in enumerate(updated):
                    decisions[index] = self.speaker_labeler.label(
                        record,
                        audio,
                        prediction.transcript,
                        run_config,
                    )

        for index, prediction in enumerate(updated):
            updated[index] = replace(
                prediction,
                embedding=embeddings[index],
                speaker_decision=decisions[index],
            )
        return tuple(updated)


def pipeline_config_mapping(
    config: Mapping[str, object] | str | Path | None = None,
) -> dict[str, object]:
    """Resolve an inference config mapping, defaulting to the M13 profile."""

    if config is None:
        return _read_config(DEFAULT_PIPELINE_CONFIG)
    if isinstance(config, str | Path):
        return _read_config(_resolve_tool_path(config))
    raw = dict(config)
    if "components" in raw:
        return raw
    configured_path = _configured_inference_path(raw)
    if configured_path is not None:
        return _read_config(configured_path)
    return _read_config(DEFAULT_PIPELINE_CONFIG)


def merge_pipeline_and_run_config(
    pipeline_config: Mapping[str, object] | None,
    run_config: Mapping[str, object] | None,
) -> dict[str, object]:
    """Combine selected pipeline config with Evaluation Tool run metadata."""

    merged = dict(pipeline_config or {})
    for key, value in dict(run_config or {}).items():
        if key in {"runtime", "components", "audio", "diagnostics", "enrollment"}:
            continue
        merged[key] = value
    return merged


def _transcribe_segments(
    asr: ASRComponent | ASRBase,
    record: EvaluationRecord,
    audio: Any,
    active_segments: tuple[AudioSegment, ...],
    run_config: Mapping[str, object] | None,
    device: str,
    *,
    segmentation_enabled: bool,
) -> tuple[SegmentPrediction, ...]:
    if not isinstance(asr, ASRBase):
        transcript = asr.transcribe(record, audio, run_config)
        segment = _record_segment(record, audio)
        return (
            SegmentPrediction(
                segment_index=0,
                segment=segment,
                transcript=transcript,
                raw_text=transcript.text,
                normalized_text=transcript.text,
            ),
        )

    if segmentation_enabled and not active_segments:
        return ()

    segment_predictions: list[SegmentPrediction] = []
    segments = active_segments or (_record_segment(record, audio),)
    for index, segment in enumerate(segments):
        context = ASRContext.from_record_segment(
            record,
            segment,
            segment_index=index,
            run_config=run_config,
            device=device,
            dtype=_runtime_dtype(run_config),
            language=_asr_language(run_config),
        )
        transcript = asr.transcribe(segment, context)
        segment_predictions.append(
            SegmentPrediction(
                segment_index=index,
                segment=segment,
                transcript=transcript,
                raw_text=getattr(asr, "last_raw_text", None) or transcript.text,
                normalized_text=getattr(asr, "last_normalized_text", None) or transcript.text,
            )
        )
    return tuple(segment_predictions)


def _active_segments(
    record: EvaluationRecord,
    audio: Any,
    segments: tuple[AudioSegment, ...],
    *,
    segmentation_enabled: bool,
) -> tuple[AudioSegment, ...]:
    if segmentation_enabled:
        return segments
    return (_record_segment(record, audio),)


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
    speaker_embedding_enabled: bool = False,
    speaker_embedding_count: int = 0,
    speaker_matching_enabled: bool = False,
    speaker_decision_count: int = 0,
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
        counters["speaker_embedding_count"] = speaker_embedding_count
    if speaker_matching_enabled:
        counters["speaker_decision_count"] = speaker_decision_count
    return counters or None


def _model_versions(
    *,
    asr: object,
    vad: object | None,
    segmenter: object | None,
    speaker_embedding: object | None,
    speaker_matcher: object | None,
) -> JsonObject:
    return {
        "vad": _component_version(vad),
        "segmentation": _component_version(segmenter),
        "asr": _component_version(asr),
        "speaker_embedding": _component_version(speaker_embedding),
        "speaker_matching": _component_version(speaker_matcher),
    }


def _component_version(component: object | None) -> str | None:
    if component is None:
        return None
    value = getattr(component, "model_name", None) or getattr(component, "name", None)
    return str(value) if value is not None else component.__class__.__name__


def _diagnostics_row(
    *,
    record: EvaluationRecord,
    output: PipelineOutput,
    audio: Any,
    vad_regions: Sequence[object],
    segments: Sequence[AudioSegment],
    segment_predictions: Sequence[SegmentPrediction],
    tracker: StageRuntimeTracker,
    raw_text: str,
    normalized_text: str,
    chronological_violations: int,
    duplicate_text_tokens_removed: int,
) -> JsonObject:
    audio_duration_sec = _segment_duration(record, audio)
    return {
        "recording_id": record.recording_id,
        "utt_id": record.utt_id,
        "start_sec": record.start_sec,
        "end_sec": record.end_sec,
        "speaker_label": output.speaker_label,
        "raw_asr_text": raw_text,
        "normalized_text": normalized_text,
        "vad_regions": write_regions_jsonable(vad_regions),
        "segments": write_segments_jsonable(segments),
        "segment_predictions": [item.to_jsonable() for item in segment_predictions],
        "speaker_decisions": [
            _jsonable_object(item.speaker_decision)
            for item in segment_predictions
            if item.speaker_decision is not None
        ],
        "runtime_stats": (
            output.runtime_stats.to_jsonable()
            if output.runtime_stats is not None
            else None
        ),
        "runtime_breakdown": tracker.to_diagnostics(audio_duration_sec=audio_duration_sec),
        "chronological_ordering_violations": chronological_violations,
        "duplicate_text_tokens_removed": duplicate_text_tokens_removed,
    }


def _jsonable_object(value: object) -> object:
    if hasattr(value, "to_jsonable"):
        return value.to_jsonable()
    if isinstance(value, Mapping):
        return {str(key): _jsonable_object(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable_object(item) for item in value]
    return value


def _read_config(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, Mapping):
        raise ContractValidationError(f"inference config must be a mapping: {path}")
    mapping = _resolve_component_references(dict(data), config_dir=path.parent)
    mapping["__config_path"] = str(path)
    mapping["__config_dir"] = str(path.parent)
    return mapping


def _resolve_component_references(
    config: dict[str, object],
    *,
    config_dir: Path,
) -> dict[str, object]:
    components = config.get("components")
    if not isinstance(components, Mapping):
        return config

    resolved: dict[str, object] = {}
    changed = False
    for slot, component in components.items():
        if isinstance(component, str):
            resolved[str(slot)] = _read_component_reference(
                component,
                config_dir=config_dir,
                slot=str(slot),
            )
            changed = True
        else:
            resolved[str(slot)] = component
    if changed:
        config["components"] = resolved
    return config


def _read_component_reference(
    value: str,
    *,
    config_dir: Path,
    slot: str,
) -> dict[str, object]:
    path = Path(value).expanduser()
    candidates = [path] if path.is_absolute() else [config_dir / path, TOOL_ROOT / path]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        with candidate.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, Mapping):
            raise ContractValidationError(f"component config must be a mapping: {candidate}")
        component = data.get("component")
        if isinstance(component, Mapping):
            mapping = dict(component)
        else:
            mapping = dict(data)
        declared_slot = mapping.get("slot")
        if declared_slot is not None and str(declared_slot) != slot:
            raise ContractValidationError(
                f"component config {candidate} declares slot {declared_slot!r}, expected {slot!r}"
            )
        return mapping
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"component config reference not found for {slot}: {value}; searched {searched}")


def _configured_inference_path(config: Mapping[str, object]) -> Path | None:
    for key in ("inference_config_path", "pipeline_config_path"):
        value = config.get(key)
        if value:
            return _resolve_tool_path(value)
    inference = config.get("inference")
    if isinstance(inference, Mapping):
        for key in ("config_path", "pipeline_config_path"):
            value = inference.get(key)
            if value:
                return _resolve_tool_path(value)
    runner = config.get("runner")
    if isinstance(runner, Mapping):
        value = runner.get("inference_config_path")
        if value:
            return _resolve_tool_path(value)
    return None


def _load_enrollment_db_from_config(config: Mapping[str, object]) -> object:
    enrollment = _mapping_child(config, "enrollment")
    value = (
        _mapping_get(enrollment, "db_path")
        or _mapping_get(enrollment, "path")
        or _mapping_get(config, "enrollment_db_path")
        or "artifacts/enrollment/enrollment_db.json"
    )
    return load_enrollment_db(_resolve_config_relative_path(value, config))


def _resolve_config_relative_path(value: object, config: Mapping[str, object]) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    config_dir = config.get("__config_dir")
    candidates = []
    if config_dir:
        candidates.append(Path(str(config_dir)) / path)
    candidates.append(TOOL_ROOT / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def _resolve_tool_path(value: object) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return TOOL_ROOT / path
