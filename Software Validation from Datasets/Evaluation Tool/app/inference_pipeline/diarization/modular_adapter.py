"""Composable speech-region, speaker-embedding, and clustering diarizer."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from app.inference_pipeline.asr.audio_utils import resolve_model_path
from app.inference_pipeline.config import ComponentConfig
from app.inference_pipeline.contracts import AudioSegment, SpeechRegion
from app.inference_pipeline.diarization.adapter_utils import (
    materialized_audio_path,
    mono_samples,
)
from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationParameters,
    DiarizationUnavailableError,
    SpeakerTurnRegion,
)
from app.inference_pipeline.diarization.clustering import agglomerative_cosine_labels
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.speaker_embedding import build_speaker_embedding_from_config
from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext
from app.inference_pipeline.vad.energy_vad import EnergyVAD


class ModularDiarizationUnavailableError(DiarizationUnavailableError):
    """Raised when one configured modular diarization stage cannot run."""


@dataclass(frozen=True)
class _EmbeddingWindow:
    start_sec: float
    end_sec: float
    assignment_start_sec: float
    assignment_end_sec: float


@dataclass
class ModularClusteringDiarizer(DiarizationBase):
    """Compose speech regions, an existing embedder, and local clustering.

    This adapter never identifies a person.  Cluster IDs are local anonymous
    turn labels and must not be joined to the named-speaker enrollment store.
    """

    params: DiarizationParameters | Mapping[str, object] | None = None

    name = "modular_clustering"

    def __post_init__(self) -> None:
        raw = dict(self.params or {}) if isinstance(self.params, Mapping) else {}
        DiarizationBase.__init__(self, self.params)
        self.segmentation_source = str(
            raw.get("segmentation_source") or "energy_vad"
        )
        self.embedding_component_config = str(
            raw.get("embedding_component_config") or ""
        ).strip()
        self.clustering_policy_id = str(
            raw.get("clustering_policy_id") or ""
        ).strip()
        self.clustering_threshold = float(raw.get("clustering_threshold", 0.5))
        self.window_duration_sec = float(raw.get("window_duration_sec", 1.5))
        self.window_step_sec = float(raw.get("window_step_sec", 0.75))
        self.min_embedding_window_sec = float(
            raw.get("min_embedding_window_sec", 0.5)
        )
        self.device = str(raw.get("device") or "cpu")
        self.energy_vad_params = _mapping(raw.get("energy_vad"), "energy_vad")
        self.segmentation_model_path = str(
            raw.get("segmentation_model_path") or ""
        ).strip()
        self.segmentation_onset = float(raw.get("segmentation_onset", 0.5))
        self.segmentation_offset = float(raw.get("segmentation_offset", 0.5))
        self.segmentation_min_duration_on = float(
            raw.get("segmentation_min_duration_on", 0.0)
        )
        self.segmentation_min_duration_off = float(
            raw.get("segmentation_min_duration_off", 0.0)
        )
        self._embedder: Any | None = None
        self._segmentation_inference: Any | None = None
        self.last_runtime_sec: float | None = None
        self.last_turns: tuple[SpeakerTurnRegion, ...] = ()
        self.last_diagnostics: dict[str, object] = {}
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        if self.segmentation_source not in {"energy_vad", "pyannote_segmentation_3_0"}:
            raise ContractValidationError(
                "segmentation_source must be energy_vad or pyannote_segmentation_3_0"
            )
        if not self.embedding_component_config:
            raise ContractValidationError(
                "embedding_component_config must name an existing component fragment"
            )
        if not self.clustering_policy_id:
            raise ContractValidationError(
                "clustering_policy_id must be explicit and pipeline-specific"
            )
        if not -1.0 <= self.clustering_threshold <= 1.0:
            raise ContractValidationError("clustering_threshold must be in [-1, 1]")
        if self.window_duration_sec <= 0 or self.window_step_sec <= 0:
            raise ContractValidationError("embedding window duration and step must be > 0")
        if self.window_step_sec > self.window_duration_sec:
            raise ContractValidationError(
                "window_step_sec must not exceed window_duration_sec"
            )
        if not 0 < self.min_embedding_window_sec <= self.window_duration_sec:
            raise ContractValidationError(
                "min_embedding_window_sec must be > 0 and <= window_duration_sec"
            )
        if self.segmentation_source == "pyannote_segmentation_3_0" and not self.segmentation_model_path:
            raise ContractValidationError(
                "pyannote segmentation requires segmentation_model_path"
            )

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        started_at = time.perf_counter()
        speech_regions = self._speech_regions(audio)
        windows = [
            window
            for region in speech_regions
            for window in _embedding_windows(
                region,
                duration_sec=self.window_duration_sec,
                step_sec=self.window_step_sec,
                minimum_sec=self.min_embedding_window_sec,
            )
        ]
        if not windows:
            self.last_runtime_sec = time.perf_counter() - started_at
            self.last_turns = ()
            self.last_diagnostics = self._diagnostics(speech_regions, windows, 0)
            return []

        vectors: list[tuple[float, ...]] = []
        with materialized_audio_path(audio, prefix="modular-diarization-audio-") as path:
            embedder = self._embedding_adapter()
            for index, window in enumerate(windows):
                segment = AudioSegment(
                    audio_path=path,
                    start_sec=window.start_sec,
                    end_sec=window.end_sec,
                    duration_sec=window.end_sec - window.start_sec,
                    sample_rate_hz=16000,
                    channel_count=1,
                    is_mono=True,
                )
                context = SpeakerEmbeddingContext(
                    recording_id="modular-diarization",
                    utt_id=f"window-{index:06d}",
                    source_audio_path=path,
                    segment_index=index,
                    segment_start_sec=window.start_sec,
                    segment_end_sec=window.end_sec,
                    device=self.device,
                    dtype="float32",
                    run_config={"project_root": str(_tool_root().parent)},
                )
                embedding = embedder.embed(segment, context)
                if embedding.status != "ok" or not embedding.vector:
                    raise ModularDiarizationUnavailableError(
                        "configured speaker embedder did not return a usable vector for "
                        f"window {index}: {embedding.status}"
                    )
                vectors.append(embedding.vector)

        labels = agglomerative_cosine_labels(
            vectors,
            threshold=self.clustering_threshold,
            min_clusters=self.params.min_speakers or 1,
            max_clusters=self.params.max_speakers,
        )
        turns = _merge_adjacent_turns(
            [
                SpeakerTurnRegion(
                    start_sec=window.assignment_start_sec,
                    end_sec=window.assignment_end_sec,
                    speaker_turn_label=f"speaker_{label:02d}",
                    source=(
                        f"{self.name}:{self.segmentation_source}:"
                        f"{self.clustering_policy_id}"
                    ),
                )
                for window, label in zip(windows, labels, strict=True)
            ],
            min_turn_sec=self.params.min_turn_sec,
        )
        self.last_runtime_sec = time.perf_counter() - started_at
        self.last_turns = tuple(turns)
        self.last_diagnostics = self._diagnostics(
            speech_regions, windows, len(set(labels))
        )
        return turns

    def _speech_regions(self, audio: object) -> list[SpeechRegion]:
        if self.segmentation_source == "energy_vad":
            return EnergyVAD(self.energy_vad_params).detect(audio)  # type: ignore[arg-type]
        speech, _overlap = self._speech_and_overlap_regions(audio)
        return speech

    def _speech_and_overlap_regions(
        self, audio: object
    ) -> tuple[list[SpeechRegion], list[SpeechRegion]]:
        """Return speech and model-predicted overlap without naming speakers.

        Pyannote segmentation-3.0 produces local-speaker activations.  The
        maximum activation is the existing voice-activity view; the second
        highest activation is the causal overlap view used by the frozen
        Product-v2 identity exclusion policy.  Neither view is an identity or
        an anonymous cluster assignment.
        """

        if self.segmentation_source == "energy_vad":
            return (
                EnergyVAD(self.energy_vad_params).detect(audio),  # type: ignore[arg-type]
                [],
            )
        inference = self._pyannote_inference()
        try:
            from pyannote.audio.utils.signal import Binarize
            from pyannote.core import SlidingWindowFeature

            import torch

            samples = mono_samples(audio, target_sample_rate=16000)
            scores = inference(
                {
                    "waveform": torch.from_numpy(samples).unsqueeze(0),
                    "sample_rate": 16000,
                }
            )
            if scores.data.ndim != 2 or scores.data.shape[1] != 2:
                raise RuntimeError(
                    "speech/overlap segmentation output must have exactly two channels"
                )
            binarize = Binarize(
                onset=self.segmentation_onset,
                offset=self.segmentation_offset,
                min_duration_on=self.segmentation_min_duration_on,
                min_duration_off=self.segmentation_min_duration_off,
            )

            def regions_for(channel: int, label: str) -> list[SpeechRegion]:
                feature = SlidingWindowFeature(
                    scores.data[:, channel : channel + 1],
                    scores.sliding_window,
                    labels=[label],
                )
                annotation = binarize(feature)
                regions = [
                    SpeechRegion(
                        start_sec=max(0.0, float(segment.start)),
                        end_sec=min(
                            float(getattr(audio, "duration_sec")),
                            float(segment.end),
                        ),
                        label=label,
                    )
                    for segment, _track in annotation.itertracks()
                    if float(segment.end) > float(segment.start)
                ]
                return _merge_speech_regions(regions, label=label)

            return regions_for(0, "speech"), regions_for(1, "predicted_overlap")
        except Exception as exc:
            raise ModularDiarizationUnavailableError(
                f"pyannote segmentation-3.0 inference failed: {exc}"
            ) from exc

    def _pyannote_inference(self) -> Any:
        if self._segmentation_inference is not None:
            return self._segmentation_inference
        try:
            available = importlib.util.find_spec("pyannote.audio") is not None
        except ModuleNotFoundError:
            available = False
        if not available:
            raise ModularDiarizationUnavailableError(
                "pyannote.audio is not installed in the active environment"
            )
        try:
            import torch
            from pyannote.audio import Inference, Model

            source = resolve_model_path(self.segmentation_model_path)
            model = Model.from_pretrained(str(source), map_location=torch.device(self.device))
            if model is None:
                raise RuntimeError("model loader returned None")
            self._segmentation_inference = Inference(
                model,
                device=torch.device(self.device),
                pre_aggregation_hook=_speech_overlap_channels,
            )
        except Exception as exc:
            raise ModularDiarizationUnavailableError(
                f"pyannote segmentation-3.0 model load failed: {exc}"
            ) from exc
        return self._segmentation_inference

    def _embedding_adapter(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        source = _resolve_component_path(self.embedding_component_config)
        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        if not isinstance(data, Mapping):
            raise ContractValidationError(
                f"speaker embedding component is not a mapping: {source}"
            )
        fragment = ComponentConfig.from_mapping(data, slot="speaker_embedding")
        self._embedder = build_speaker_embedding_from_config(
            {"components": {"speaker_embedding": fragment.to_jsonable()}}
        )
        if self._embedder is None:
            raise ModularDiarizationUnavailableError(
                f"speaker embedding component did not build: {source}"
            )
        return self._embedder

    def _diagnostics(
        self,
        regions: list[SpeechRegion],
        windows: list[_EmbeddingWindow],
        cluster_count: int,
    ) -> dict[str, object]:
        return {
            "segmentation_source": self.segmentation_source,
            "embedding_component_config": self.embedding_component_config,
            "clustering_policy_id": self.clustering_policy_id,
            "clustering_threshold": self.clustering_threshold,
            "speech_region_count": len(regions),
            "embedding_window_count": len(windows),
            "cluster_count": cluster_count,
            "anonymous_labels_only": True,
        }


def _embedding_windows(
    region: SpeechRegion,
    *,
    duration_sec: float,
    step_sec: float,
    minimum_sec: float,
) -> list[_EmbeddingWindow]:
    region_duration = region.end_sec - region.start_sec
    if region_duration < minimum_sec:
        return []
    if region_duration <= duration_sec:
        return [
            _EmbeddingWindow(
                region.start_sec,
                region.end_sec,
                region.start_sec,
                region.end_sec,
            )
        ]

    last_start = region.end_sec - duration_sec
    starts: list[float] = []
    current = region.start_sec
    while current < last_start:
        starts.append(current)
        current += step_sec
    starts.append(last_start)
    starts = sorted(set(round(value, 9) for value in starts))
    centers = [start + duration_sec / 2.0 for start in starts]
    boundaries = [region.start_sec]
    boundaries.extend(
        (left + right) / 2.0
        for left, right in zip(centers, centers[1:], strict=False)
    )
    boundaries.append(region.end_sec)
    return [
        _EmbeddingWindow(
            start_sec=start,
            end_sec=start + duration_sec,
            assignment_start_sec=boundaries[index],
            assignment_end_sec=boundaries[index + 1],
        )
        for index, start in enumerate(starts)
    ]


def _merge_adjacent_turns(
    turns: list[SpeakerTurnRegion],
    *,
    min_turn_sec: float,
) -> list[SpeakerTurnRegion]:
    merged: list[SpeakerTurnRegion] = []
    for turn in sorted(turns, key=lambda item: (item.start_sec, item.end_sec)):
        if (
            merged
            and merged[-1].speaker_turn_label == turn.speaker_turn_label
            and turn.start_sec <= merged[-1].end_sec + 1e-9
            and merged[-1].source == turn.source
        ):
            previous = merged[-1]
            merged[-1] = SpeakerTurnRegion(
                start_sec=previous.start_sec,
                end_sec=max(previous.end_sec, turn.end_sec),
                speaker_turn_label=previous.speaker_turn_label,
                source=previous.source,
            )
        else:
            merged.append(turn)
    return [turn for turn in merged if turn.end_sec - turn.start_sec >= min_turn_sec]


def _merge_speech_regions(
    regions: list[SpeechRegion], *, label: str = "speech"
) -> list[SpeechRegion]:
    merged: list[SpeechRegion] = []
    for region in sorted(regions, key=lambda item: (item.start_sec, item.end_sec)):
        if not merged or region.start_sec > merged[-1].end_sec:
            merged.append(region)
            continue
        previous = merged[-1]
        merged[-1] = SpeechRegion(
            start_sec=previous.start_sec,
            end_sec=max(previous.end_sec, region.end_sec),
            label=label,
        )
    return merged


def _speech_overlap_channels(scores: np.ndarray) -> np.ndarray:
    """Reduce local-speaker activations to speech and overlap channels.

    ``Inference`` applies powerset-to-multilabel conversion before this hook.
    The second-highest local-speaker activation therefore represents evidence
    that at least two speakers are active.  A one-channel backend has no
    observable overlap and receives an all-zero second channel.
    """

    values = np.asarray(scores)
    if values.ndim < 2 or values.shape[-1] < 1:
        raise ValueError("segmentation scores must have a non-empty speaker axis")
    speech = np.max(values, axis=-1, keepdims=True)
    if values.shape[-1] < 2:
        overlap = np.zeros_like(speech)
    else:
        overlap = np.partition(values, kth=values.shape[-1] - 2, axis=-1)[
            ..., -2:-1
        ]
    return np.concatenate((speech, overlap), axis=-1)


def _resolve_component_path(value: str) -> Path:
    configured = Path(value).expanduser()
    candidates = [configured] if configured.is_absolute() else [
        _tool_root() / configured,
        _tool_root().parent.parent / configured,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "speaker embedding component config does not exist; searched: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _tool_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field_name} must be a mapping")
    return value
