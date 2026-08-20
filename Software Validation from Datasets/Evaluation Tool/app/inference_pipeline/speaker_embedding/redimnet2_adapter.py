"""Official native ReDimNet2-B2 speaker-embedding adapter."""

from __future__ import annotations

import importlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import torch

from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.inference_pipeline.speaker_embedding.adapter_utils import (
    load_segment_samples,
    non_negative_float,
    positive_int,
    resolve_embedding_model_path,
    successful_embedding,
)
from app.inference_pipeline.speaker_embedding.base import (
    SpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
)
from app.resource_telemetry.context import telemetry_span


class ReDimNet2UnavailableError(InferencePipelineError):
    """Raised when the pinned ReDimNet2 source or checkpoint cannot run."""


@dataclass
class ReDimNet2B2SpeakerEmbeddingAdapter(SpeakerEmbeddingBase):
    """Load the official B2 VoxCeleb2 large-margin checkpoint without downloads."""

    params: Mapping[str, object] | None = None
    model: Any | None = None

    name = "redimnet2_b2_speaker_embedding"

    def __post_init__(self) -> None:
        self.params = dict(self.params or {})
        self.model_name = str(
            self.params.get("model_name") or "redimnet2_b2_vox2_lm_v1_0_0"
        )
        self.model_source = str(
            self.params.get("model_source") or "PalabraAI/redimnet2"
        )
        self.source_path = self.params.get("source_path")
        self.model_path = self.params.get("model_path")
        self.source_revision = str(self.params.get("source_revision") or "")
        self.checkpoint_revision = str(self.params.get("checkpoint_revision") or "")
        self.sample_rate_hz = positive_int(
            self.params.get("sample_rate_hz", 16000), "sample_rate_hz"
        )
        self.embedding_dim = positive_int(
            self.params.get("embedding_dim", 192), "embedding_dim"
        )
        self.num_threads = positive_int(
            self.params.get("num_threads", 1), "num_threads"
        )
        self.configured_device = str(self.params.get("device") or "cpu")
        self.dtype = str(self.params.get("dtype") or "float32")
        self.allow_model_downloads = bool(
            self.params.get("allow_model_downloads", False)
        )
        if self.allow_model_downloads:
            raise ContractValidationError(
                "ReDimNet2 adapter does not permit inference-time model downloads"
            )
        if self.dtype != "float32":
            raise ContractValidationError(
                "the qualified native ReDimNet2-B2 path requires float32"
            )
        self._load_sec: float | None = None
        SpeakerEmbeddingBase.__init__(
            self,
            model_name=self.model_name,
            min_duration_sec=non_negative_float(
                self.params.get("min_duration_sec", 0.5), "min_duration_sec"
            ),
            device=self.configured_device,
            dtype=self.dtype,
        )

    def embed(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
    ) -> SpeakerEmbedding:
        started_at = time.perf_counter()
        requested_duration = self._segment_duration(audio_segment)
        if self._is_too_short(requested_duration):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=requested_duration,
            )
        audio = load_segment_samples(
            audio_segment,
            target_sample_rate=self.sample_rate_hz,
        )
        if self._is_too_short(audio.duration_sec):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=audio.duration_sec,
            )
        model = self._model(context)
        try:
            waveform = torch.from_numpy(audio.samples).unsqueeze(0).to(
                device=self.configured_device,
                dtype=torch.float32,
            )
            with telemetry_span(
                "embedding_extraction",
                phase="warm_inference",
                identifiers={
                    "recording_id": context.recording_id,
                    "utt_id": context.utt_id,
                    "segment_index": context.segment_index,
                },
                cuda=self.configured_device == "cuda",
            ):
                with torch.inference_mode():
                    vector = model(waveform)
        except Exception as exc:
            raise ReDimNet2UnavailableError(
                f"ReDimNet2-B2 embedding extraction failed: {exc}"
            ) from exc
        tensor = torch.as_tensor(vector).detach().float().cpu().reshape(-1)
        if tensor.numel() != self.embedding_dim:
            raise ContractValidationError(
                "ReDimNet2-B2 embedding dimension "
                f"{tensor.numel()} does not match configured {self.embedding_dim}"
            )
        return successful_embedding(
            self,
            audio_segment,
            context,
            tensor,
            started_at=started_at,
            duration_sec=audio.duration_sec,
            sample_rate=audio.sample_rate,
            device=self.configured_device,
            load_sec=self._load_sec,
            metadata={
                "adapter": self.name,
                "model_source": self.model_source,
                "source_revision": self.source_revision,
                "checkpoint_revision": self.checkpoint_revision,
                "official_preprocessing": {
                    "waveform": "mono float32 [-1, 1] at 16 kHz",
                    "feature_type": "official internal tf mel filterbank",
                    "mel_bins": 72,
                    "window_samples": 400,
                    "hop_samples": 160,
                    "fft_samples": 512,
                    "frequency_hz": [20, 7600],
                    "preemphasis": 0.97,
                    "waveform_normalization": True,
                    "feature_mean_normalization": True,
                    "adapter_padding_or_cropping": "none",
                },
            },
        )

    def _model(self, context: SpeakerEmbeddingContext) -> Any:
        if self.model is not None:
            return self.model
        if self.source_path is None or self.model_path is None:
            raise ReDimNet2UnavailableError(
                "ReDimNet2 source_path and model_path must both be configured"
            )
        if self.configured_device == "cuda" and not torch.cuda.is_available():
            raise ReDimNet2UnavailableError(
                "CUDA was requested for ReDimNet2 but is unavailable"
            )
        try:
            source = resolve_embedding_model_path(self.source_path, context)
            checkpoint = resolve_embedding_model_path(self.model_path, context)
            module = _official_module(source)
            payload = _load_checkpoint(checkpoint)
            model_config = payload.get("model_config")
            state_dict = payload.get("state_dict")
            if not isinstance(model_config, Mapping) or not isinstance(state_dict, Mapping):
                raise ReDimNet2UnavailableError(
                    "official checkpoint is missing model_config or state_dict"
                )
            started_at = time.perf_counter()
            torch.set_num_threads(self.num_threads)
            with telemetry_span(
                "embedding_model_load",
                phase="cold_initialization",
                cuda=self.configured_device == "cuda",
            ):
                model = module.ReDimNet2Wrap(**dict(model_config))
                load_result = model.load_state_dict(state_dict)
                if load_result.missing_keys or load_result.unexpected_keys:
                    raise ReDimNet2UnavailableError(
                        "official checkpoint state mismatch: "
                        f"missing={load_result.missing_keys}, "
                        f"unexpected={load_result.unexpected_keys}"
                    )
                model.to(device=self.configured_device, dtype=torch.float32)
                model.eval()
                for parameter in model.parameters():
                    parameter.requires_grad_(False)
            self.model = model
            self._load_sec = time.perf_counter() - started_at
        except ReDimNet2UnavailableError:
            raise
        except Exception as exc:
            raise ReDimNet2UnavailableError(
                f"ReDimNet2-B2 model load failed: {exc}"
            ) from exc
        return self.model


def _official_module(source: Path) -> Any:
    package = source / "redimnet2"
    if not (package / "redimnet2.py").is_file():
        raise ReDimNet2UnavailableError(
            f"pinned official ReDimNet2 source is incomplete: {source}"
        )
    source_text = str(source)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    previous_bytecode_policy = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        return importlib.import_module("redimnet2.redimnet2")
    except Exception as exc:
        raise ReDimNet2UnavailableError(
            f"official ReDimNet2 source import failed: {exc}"
        ) from exc
    finally:
        sys.dont_write_bytecode = previous_bytecode_policy


def _load_checkpoint(path: Path) -> Mapping[str, object]:
    try:
        value = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:  # pragma: no cover - older supported Torch fallback
        value = torch.load(path, map_location="cpu")
    if not isinstance(value, Mapping):
        raise ReDimNet2UnavailableError("official checkpoint root must be a mapping")
    return value
