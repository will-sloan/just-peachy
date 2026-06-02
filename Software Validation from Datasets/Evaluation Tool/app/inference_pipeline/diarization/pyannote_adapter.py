"""Optional pyannote community diarization adapter."""

from __future__ import annotations

import importlib.util
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationParameters,
    DiarizationUnavailableError,
    SpeakerTurnRegion,
    mark_overlapping_turns,
)
from app.inference_pipeline.errors import ContractValidationError


class PyannoteDiarizationUnavailableError(DiarizationUnavailableError):
    """Raised when pyannote dependencies, credentials, or local assets are missing."""


@dataclass
class PyannoteCommunityDiarizer(DiarizationBase):
    """Lazy pyannote adapter that never downloads models unless explicitly allowed."""

    params: DiarizationParameters | Mapping[str, object] | None = None
    pipeline: Any | None = None
    pipeline_loader: Callable[..., Any] | None = None

    name = "pyannote_community"

    def __post_init__(self) -> None:
        DiarizationBase.__init__(self, self.params)
        self.last_runtime_sec: float | None = None
        self.last_turns: tuple[SpeakerTurnRegion, ...] = ()

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        audio_path = _audio_path(audio)
        pipeline = self._pipeline()
        call_kwargs = _speaker_count_kwargs(self.params)
        started_at = time.perf_counter()
        try:
            try:
                annotation = pipeline({"audio": str(audio_path)}, **call_kwargs)
            except TypeError:
                annotation = pipeline(str(audio_path), **call_kwargs)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise PyannoteDiarizationUnavailableError(
                f"pyannote diarization failed: {exc}"
            ) from exc

        turns = _annotation_to_turns(
            annotation,
            min_turn_sec=self.params.min_turn_sec,
            source=self.name,
        )
        self.last_runtime_sec = time.perf_counter() - started_at
        self.last_turns = tuple(turns)
        return list(turns)

    def _pipeline(self) -> Any:
        if self.pipeline is not None:
            return self.pipeline
        try:
            pyannote_available = importlib.util.find_spec("pyannote.audio") is not None
        except ModuleNotFoundError:
            pyannote_available = False
        if not pyannote_available:
            raise PyannoteDiarizationUnavailableError(
                "pyannote.audio is not installed in the active environment."
            )
        if (
            not self.params.allow_model_downloads
            and not _local_assets_available(self.params)
        ):
            raise PyannoteDiarizationUnavailableError(
                "pyannote model assets are not available locally and downloads are disabled."
            )

        try:
            from pyannote.audio import Pipeline
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise PyannoteDiarizationUnavailableError(
                "pyannote.audio Pipeline is not importable."
            ) from exc

        loader = self.pipeline_loader or Pipeline.from_pretrained
        kwargs: dict[str, object] = {}
        token = os.environ.get(self.params.auth_token_env)
        if token:
            kwargs["use_auth_token"] = token
        if self.params.cache_dir:
            kwargs["cache_dir"] = self.params.cache_dir
        try:
            self.pipeline = loader(self.params.model_source, **kwargs)
        except TypeError:
            kwargs.pop("cache_dir", None)
            if "use_auth_token" in kwargs:
                kwargs["token"] = kwargs.pop("use_auth_token")
            self.pipeline = loader(self.params.model_source, **kwargs)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise PyannoteDiarizationUnavailableError(
                f"pyannote model load failed: {exc}"
            ) from exc
        return self.pipeline


def _audio_path(audio: object) -> Path:
    value = getattr(audio, "audio_path", None)
    if value is None:
        value = getattr(audio, "path", None)
    if value is None:
        raise ContractValidationError("diarization audio object must expose audio_path")
    path = Path(str(value))
    if not str(path).strip():
        raise ContractValidationError("diarization audio_path must be non-empty")
    return path


def _speaker_count_kwargs(params: DiarizationParameters) -> dict[str, int]:
    kwargs: dict[str, int] = {}
    if params.min_speakers is not None:
        kwargs["min_speakers"] = params.min_speakers
    if params.max_speakers is not None:
        kwargs["max_speakers"] = params.max_speakers
    return kwargs


def _local_assets_available(params: DiarizationParameters) -> bool:
    source = Path(params.model_source).expanduser()
    if source.exists():
        return True
    if not params.cache_dir:
        return False
    cache_dir = Path(params.cache_dir).expanduser()
    if not cache_dir.exists():
        return False
    markers = ("config.yaml", "pytorch_model.bin", "model.safetensors")
    return any(path.name in markers for path in cache_dir.rglob("*"))


def _annotation_to_turns(
    annotation: object,
    *,
    min_turn_sec: float,
    source: str,
) -> list[SpeakerTurnRegion]:
    if not hasattr(annotation, "itertracks"):
        raise PyannoteDiarizationUnavailableError(
            "pyannote output does not expose itertracks(yield_label=True)."
        )
    label_map: dict[str, str] = {}
    turns: list[SpeakerTurnRegion] = []
    for item in annotation.itertracks(yield_label=True):
        turn, _track, raw_label = item
        start_sec = float(getattr(turn, "start"))
        end_sec = float(getattr(turn, "end"))
        if end_sec - start_sec < min_turn_sec:
            continue
        label = _anonymous_label(str(raw_label), label_map)
        turns.append(
            SpeakerTurnRegion(
                start_sec=start_sec,
                end_sec=end_sec,
                speaker_turn_label=label,
                source=source,
            )
        )
    return mark_overlapping_turns(turns)


def _anonymous_label(raw_label: str, label_map: dict[str, str]) -> str:
    if raw_label not in label_map:
        label_map[raw_label] = f"speaker_{len(label_map):02d}"
    return label_map[raw_label]
