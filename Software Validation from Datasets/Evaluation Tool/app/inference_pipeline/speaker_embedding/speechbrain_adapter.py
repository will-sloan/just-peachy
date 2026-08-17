"""Lazy SpeechBrain ECAPA speaker embedding adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import soundfile as sf
import torch

from app.inference_pipeline.audio_io.resample import resample_audio, validate_sample_rate
from app.inference_pipeline.audio_io.segments import resolve_segment_frames
from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.inference_pipeline.speaker_embedding.base import (
    DEFAULT_MIN_DURATION_SEC,
    EMBEDDING_STATUS_OK,
    SpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
    SpeakerEmbeddingRuntimeStats,
    embedding_id,
    normalize_vector,
    peak_gpu_memory_mb,
    process_memory_mb,
)
from app.resource_telemetry.context import telemetry_span
from app.utils.paths import model_root, resolve_model_path_from_logical


class SpeechBrainUnavailableError(InferencePipelineError):
    """Raised when SpeechBrain dependencies or local assets are unavailable."""


@dataclass
class SpeechBrainECAPAAdapter(SpeakerEmbeddingBase):
    """SpeechBrain ECAPA adapter that avoids implicit model downloads by default."""

    params: Mapping[str, object] | None = None
    model: Any | None = None

    name = "speechbrain_ecapa"

    def __post_init__(self) -> None:
        self.params = dict(self.params or {})
        self.model_source = str(
            self.params.get("model_source")
            or self.params.get("source")
            or "speechbrain/spkrec-ecapa-voxceleb"
        )
        self.model_name = str(self.params.get("model_name") or "speechbrain_ecapa")
        self.sample_rate_hz = _positive_int(
            self.params.get("sample_rate_hz", 16000),
            "sample_rate_hz",
        )
        self.embedding_dim = _optional_int(self.params.get("embedding_dim"))
        self.configured_device = _optional_string(self.params.get("device"))
        self.dtype = str(self.params.get("dtype") or "float32")
        self.allow_model_downloads = bool(self.params.get("allow_model_downloads", False))
        self.savedir = _optional_path(self.params.get("savedir") or self.params.get("cache_dir"))
        self._load_sec: float | None = None
        SpeakerEmbeddingBase.__init__(
            self,
            model_name=self.model_name,
            min_duration_sec=_float_value(
                self.params.get("min_duration_sec", DEFAULT_MIN_DURATION_SEC),
                "min_duration_sec",
            ),
            device=self.configured_device or "cpu",
            dtype=self.dtype,
        )

    def embed(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
    ) -> SpeakerEmbedding:
        started_at = time.perf_counter()
        device = self._active_device(context)
        requested_duration = self._segment_duration(audio_segment)
        if self._is_too_short(requested_duration):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=requested_duration,
            )

        waveform, duration_sec, sample_rate_hz = _load_waveform(
            audio_segment,
            target_sample_rate=self.sample_rate_hz,
        )
        if self._is_too_short(duration_sec):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=duration_sec,
                reason="loaded audio segment shorter than min_duration_sec",
            )
        model = self._model(context, device)
        waveform = _move_waveform(waveform, device)

        with telemetry_span(
            "embedding_extraction",
            phase="warm_inference",
            identifiers={
                "recording_id": context.recording_id,
                "utt_id": context.utt_id,
                "segment_index": context.segment_index,
            },
            cuda=device == "cuda",
        ):
            with torch.inference_mode():
                raw_embedding = _encode_batch(model, waveform)
        vector_tensor = torch.as_tensor(raw_embedding).detach().float().cpu().reshape(-1)
        if vector_tensor.numel() == 0:
            raise SpeechBrainUnavailableError("SpeechBrain returned an empty embedding vector.")
        if self.embedding_dim is not None and int(vector_tensor.numel()) != self.embedding_dim:
            raise ContractValidationError(
                "SpeechBrain embedding dimension "
                f"{int(vector_tensor.numel())} does not match configured {self.embedding_dim}"
            )

        runtime = SpeakerEmbeddingRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=time.perf_counter() - started_at,
            audio_duration_sec=duration_sec,
            device=device,
            dtype=self.dtype,
            peak_gpu_memory_mb=peak_gpu_memory_mb(device),
            cpu_memory_mb=process_memory_mb(),
        )
        embedding = SpeakerEmbedding(
            embedding_id=embedding_id(context),
            vector=normalize_vector(vector_tensor),
            model_name=self.model_name,
            segment_duration_sec=duration_sec,
            device=device,
            runtime=runtime,
            status=EMBEDDING_STATUS_OK,
            reliable=True,
            recording_id=context.recording_id,
            utt_id=context.utt_id,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            sample_rate_hz=sample_rate_hz,
            metadata={
                "adapter": self.name,
                "model_source": self.model_source,
                "min_duration_sec": self.min_duration_sec,
            },
        )
        self.last_embedding = embedding
        self.last_runtime_stats = runtime
        return embedding

    def _active_device(self, context: SpeakerEmbeddingContext) -> str:
        device = self.configured_device or context.device or self.device
        if device == "cuda" and not torch.cuda.is_available():
            raise SpeechBrainUnavailableError("CUDA was requested but is not available.")
        return device

    def _model(self, context: SpeakerEmbeddingContext, device: str) -> Any:
        if self.model is not None:
            return self.model
        if importlib.util.find_spec("speechbrain") is None:
            raise SpeechBrainUnavailableError(
                "SpeechBrain package is not installed in the active environment."
            )
        savedir = self._savedir(context)
        source = self._source_for_load(savedir)
        if not self.allow_model_downloads and not self._local_assets_available(savedir):
            raise SpeechBrainUnavailableError(
                "SpeechBrain ECAPA model assets are not available locally and downloads are disabled."
            )

        try:
            try:
                from speechbrain.inference.speaker import EncoderClassifier
            except Exception:
                from speechbrain.pretrained import EncoderClassifier  # type: ignore[no-redef]
            from speechbrain.utils.fetching import LocalStrategy
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SpeechBrainUnavailableError("SpeechBrain EncoderClassifier is not importable.") from exc

        started_at = time.perf_counter()
        try:
            with telemetry_span(
                "embedding_model_load",
                phase="cold_initialization",
                cuda=device == "cuda",
            ):
                self.model = EncoderClassifier.from_hparams(
                    source=source,
                    savedir=str(savedir) if savedir is not None else None,
                    run_opts={"device": device},
                    local_strategy=LocalStrategy.COPY,
                )
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SpeechBrainUnavailableError(f"SpeechBrain model load failed: {exc}") from exc
        self._load_sec = time.perf_counter() - started_at
        return self.model

    def _source_for_load(self, savedir: Path | None) -> str:
        source_path = Path(self.model_source).expanduser()
        if source_path.exists():
            return str(source_path)
        if savedir is not None and _has_speechbrain_assets(savedir):
            return str(savedir)
        return self.model_source

    def _local_assets_available(self, savedir: Path | None) -> bool:
        source_path = Path(self.model_source).expanduser()
        if source_path.exists():
            return True
        return bool(savedir is not None and _has_speechbrain_assets(savedir))

    def _savedir(self, context: SpeakerEmbeddingContext) -> Path | None:
        if self.savedir is None:
            return None
        return _resolve_relative_path(self.savedir, context)


def _load_waveform(
    audio_segment: AudioSegment,
    *,
    target_sample_rate: int,
) -> tuple[torch.Tensor, float, int]:
    audio_path = audio_segment.audio_path
    if not audio_path.is_file():
        raise FileNotFoundError(f"speaker embedding audio path does not exist: {audio_path}")
    info = sf.info(audio_path)
    source_sample_rate = int(info.samplerate)
    source_frames = int(info.frames)
    validate_sample_rate(source_sample_rate, "source_sample_rate")
    segment = resolve_segment_frames(
        audio_segment.start_sec,
        audio_segment.end_sec,
        source_sample_rate,
        source_frames,
    )
    audio, _sample_rate = sf.read(
        audio_path,
        start=segment.start_frame,
        frames=segment.frame_count,
        dtype="float32",
        always_2d=True,
    )
    mono = _select_channel(audio.astype(np.float32, copy=False), audio_segment.channel_index)
    resampled = resample_audio(mono, source_sample_rate, target_sample_rate)
    waveform = torch.from_numpy(np.ascontiguousarray(resampled[:, 0])).unsqueeze(0)
    return waveform, waveform.shape[1] / target_sample_rate, target_sample_rate


def _select_channel(audio: np.ndarray, channel_index: int | None) -> np.ndarray:
    if audio.ndim != 2:
        raise ContractValidationError("speaker embedding audio must have shape (samples, channels)")
    if channel_index is None:
        return audio.mean(axis=1, keepdims=True).astype(np.float32, copy=False)
    if channel_index < 0 or channel_index >= audio.shape[1]:
        raise ContractValidationError("channel_index out of range for speaker embedding audio")
    return audio[:, channel_index : channel_index + 1].astype(np.float32, copy=False)


def _move_waveform(waveform: torch.Tensor, device: str) -> torch.Tensor:
    try:
        return waveform.to(device=device, dtype=torch.float32)
    except Exception as exc:
        raise SpeechBrainUnavailableError(f"unable to move waveform to device {device!r}") from exc


def _encode_batch(model: Any, waveform: torch.Tensor) -> Any:
    if hasattr(model, "encode_batch"):
        return model.encode_batch(waveform)
    if callable(model):
        return model(waveform)
    raise SpeechBrainUnavailableError("SpeechBrain model does not expose encode_batch().")


def _resolve_relative_path(path: Path, context: SpeakerEmbeddingContext) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    candidates = [resolve_model_path_from_logical(expanded)]
    project_root = _project_root_from_context(context)
    if project_root is not None and model_root().source != "environment override":
        candidates.extend(
            [
                project_root / "Evaluation Tool" / expanded,
                project_root / expanded,
                project_root.parent / expanded,
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _project_root_from_context(context: SpeakerEmbeddingContext) -> Path | None:
    if not isinstance(context.run_config, Mapping):
        return None
    value = context.run_config.get("project_root")
    if value is None:
        return None
    return Path(str(value)).expanduser()


def _has_speechbrain_assets(path: Path) -> bool:
    if not path.exists():
        return False
    if (path / "hyperparams.yaml").is_file():
        return True
    return any(path.glob("*.ckpt")) or any(path.rglob("*.ckpt"))


def _optional_string(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _optional_path(value: object) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    return Path(str(value)).expanduser()


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("embedding_dim must be an integer") from exc


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    validate_sample_rate(parsed, field_name)
    return parsed


def _float_value(value: object, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc
    if parsed < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    return parsed
