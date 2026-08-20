"""Optional pyannote community diarization adapter."""

from __future__ import annotations

import importlib.util
import inspect
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from app.inference_pipeline.asr.audio_utils import resolve_model_path
from app.inference_pipeline.diarization.adapter_utils import mono_samples
from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationParameters,
    DiarizationUnavailableError,
    SpeakerTurnRegion,
    mark_overlapping_turns,
)


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
        raw = dict(self.params or {}) if isinstance(self.params, Mapping) else {}
        DiarizationBase.__init__(self, self.params)
        self.device = str(raw.get("device") or "cpu")
        self.last_runtime_sec: float | None = None
        self.last_turns: tuple[SpeakerTurnRegion, ...] = ()

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        pipeline = self._pipeline()
        call_kwargs = _speaker_count_kwargs(self.params)
        started_at = time.perf_counter()
        try:
            import torch

            samples = mono_samples(audio, target_sample_rate=16000)
            annotation = pipeline(
                {
                    "waveform": torch.from_numpy(samples).unsqueeze(0),
                    "sample_rate": 16000,
                },
                **call_kwargs,
            )
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
        token = _auth_token(self.params)
        source = _resolve_pipeline_source(self.params, token=token)
        kwargs = _loader_kwargs(loader, self.params, token=token)
        try:
            self.pipeline = loader(source, **kwargs)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise PyannoteDiarizationUnavailableError(
                f"pyannote model load failed: {exc}"
            ) from exc
        if self.pipeline is None:
            raise PyannoteDiarizationUnavailableError(
                "pyannote model loader returned no pipeline; verify model access and cache completeness."
            )
        if self.device != "cpu" and hasattr(self.pipeline, "to"):
            try:
                import torch

                self.pipeline.to(torch.device(self.device))
            except Exception as exc:  # pragma: no cover - dependency boundary
                raise PyannoteDiarizationUnavailableError(
                    f"pyannote could not move the pipeline to {self.device!r}: {exc}"
                ) from exc
        return self.pipeline


def _speaker_count_kwargs(params: DiarizationParameters) -> dict[str, int]:
    kwargs: dict[str, int] = {}
    if params.min_speakers is not None:
        kwargs["min_speakers"] = params.min_speakers
    if params.max_speakers is not None:
        kwargs["max_speakers"] = params.max_speakers
    return kwargs


def _auth_token(params: DiarizationParameters) -> str | None:
    configured = os.environ.get(params.auth_token_env)
    if configured:
        return configured
    # ``HF_TOKEN`` is Hugging Face's standard variable and is also what the
    # repository bootstrap uses.  Supporting it avoids two divergent secrets.
    fallback = os.environ.get("HF_TOKEN")
    if fallback:
        return fallback
    try:
        from huggingface_hub import get_token

        return get_token()
    except (ImportError, OSError):
        return None


def _loader_kwargs(
    loader: Callable[..., Any],
    params: DiarizationParameters,
    *,
    token: str | None,
) -> dict[str, object]:
    try:
        signature = inspect.signature(loader)
        parameters = signature.parameters
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
    except (TypeError, ValueError):
        parameters = {}
        accepts_kwargs = True

    kwargs: dict[str, object] = {}
    if token:
        if "token" in parameters or accepts_kwargs:
            kwargs["token"] = token
        elif "use_auth_token" in parameters:
            kwargs["use_auth_token"] = token
    cache_dir = params.cache_dir
    if cache_dir:
        if "cache_dir" in parameters or accepts_kwargs:
            kwargs["cache_dir"] = str(_cache_dir(cache_dir))
    return kwargs


def _resolve_pipeline_source(
    params: DiarizationParameters,
    *,
    token: str | None,
) -> str:
    try:
        local_source = resolve_model_path(params.model_source)
    except (FileNotFoundError, ValueError):
        local_source = None
    if local_source is not None:
        return str(local_source)

    if params.allow_model_downloads:
        if not token:
            raise PyannoteDiarizationUnavailableError(
                f"pyannote model downloads require a Hugging Face token; set "
                f"{params.auth_token_env} or HF_TOKEN after accepting the model terms."
            )
        return params.model_source

    try:
        from huggingface_hub import snapshot_download

        snapshot = snapshot_download(
            repo_id=params.model_source,
            cache_dir=str(_cache_dir(params.cache_dir)) if params.cache_dir else None,
            token=token,
            local_files_only=True,
        )
    except Exception as exc:
        raise PyannoteDiarizationUnavailableError(
            "pyannote downloads are disabled and no complete local snapshot was found; "
            "bootstrap the gated model first or configure a local model_source."
        ) from exc
    return str(Path(snapshot).resolve())


def _cache_dir(value: str) -> Path:
    configured = Path(value).expanduser()
    if configured.is_absolute():
        return configured
    try:
        return resolve_model_path(configured)
    except FileNotFoundError:
        tool_root = Path(__file__).resolve().parents[3]
        return (tool_root.parent.parent / configured).resolve()


def _local_assets_available(params: DiarizationParameters) -> bool:
    """Return whether a complete local source/snapshot can be resolved."""

    try:
        _resolve_pipeline_source(params, token=_auth_token(params))
    except PyannoteDiarizationUnavailableError:
        return False
    return True


def _annotation_to_turns(
    annotation: object,
    *,
    min_turn_sec: float,
    source: str,
) -> list[SpeakerTurnRegion]:
    # pyannote.audio 4 wraps the Annotation in a DiarizeOutput object while
    # pyannote.audio 3 returns the Annotation directly.
    wrapped = getattr(annotation, "speaker_diarization", None)
    if wrapped is not None:
        annotation = wrapped
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
