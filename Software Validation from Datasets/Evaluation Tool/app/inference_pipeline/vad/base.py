"""Voice activity detection interfaces and shared helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, TYPE_CHECKING

from app.inference_pipeline.contracts import SpeechRegion
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject

if TYPE_CHECKING:
    from app.inference_pipeline.audio_io import LoadedAudio


@dataclass(frozen=True)
class VADParameters:
    """Common VAD configuration shared by swappable backends."""

    threshold: float = 0.1
    min_speech_ms: int = 250
    min_silence_ms: int = 100
    pad_ms: int = 0
    sample_rate: int = 16000

    def __post_init__(self) -> None:
        if self.threshold < 0:
            raise ContractValidationError("vad threshold must be >= 0")
        for field_name in ("min_speech_ms", "min_silence_ms", "pad_ms"):
            if getattr(self, field_name) < 0:
                raise ContractValidationError(f"{field_name} must be >= 0")
        if self.sample_rate < 1:
            raise ContractValidationError("vad sample_rate must be >= 1")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object] | None = None) -> "VADParameters":
        data = dict(mapping or {})
        return cls(
            threshold=_float_value(data.get("threshold", 0.1), "threshold"),
            min_speech_ms=_int_alias(
                data,
                ("min_speech_ms", "min_speech_duration_ms"),
                250,
                "min_speech_ms",
            ),
            min_silence_ms=_int_alias(
                data,
                ("min_silence_ms", "min_silence_duration_ms"),
                100,
                "min_silence_ms",
            ),
            pad_ms=_int_alias(data, ("pad_ms", "speech_pad_ms"), 0, "pad_ms"),
            sample_rate=_int_alias(data, ("sample_rate", "sample_rate_hz"), 16000, "sample_rate"),
        )

    def to_jsonable(self) -> JsonObject:
        return {
            "threshold": self.threshold,
            "min_speech_ms": self.min_speech_ms,
            "min_silence_ms": self.min_silence_ms,
            "pad_ms": self.pad_ms,
            "sample_rate": self.sample_rate,
        }


class VADBase(ABC):
    """Backend-swappable voice activity detector interface."""

    name = "vad_base"

    def __init__(self, params: VADParameters | Mapping[str, object] | None = None) -> None:
        self.params = (
            params
            if isinstance(params, VADParameters)
            else VADParameters.from_mapping(params)
        )

    @abstractmethod
    def detect(self, audio: "LoadedAudio") -> list[SpeechRegion]:
        """Return speech-like regions for model-ready audio."""


class NoOpVAD(VADBase):
    """Disabled VAD adapter that emits no regions."""

    name = "no_op_vad"

    def detect(self, audio: "LoadedAudio") -> list[SpeechRegion]:
        _ = audio
        return []


class FixedVAD(VADBase):
    """Deterministic adapter for tests and smoke report generation."""

    name = "fixed_vad"

    def __init__(self, regions: Sequence[SpeechRegion]) -> None:
        super().__init__()
        self.regions = tuple(regions)

    def detect(self, audio: "LoadedAudio") -> list[SpeechRegion]:
        _ = audio
        return list(self.regions)


def build_vad_from_config(config: object) -> VADBase | None:
    """Instantiate the configured VAD without changing Evaluation Tool contracts."""

    component = _vad_component(config)
    if component is None:
        return None
    enabled = _component_enabled(component)
    if not enabled:
        return None

    name = _component_name(component)
    params = _component_params(component)
    if name == "no_op_vad":
        return NoOpVAD(params)
    if name == "energy_vad":
        from app.inference_pipeline.vad.energy_vad import EnergyVAD

        return EnergyVAD(params)
    if name == "silero_vad":
        from app.inference_pipeline.vad.silero_vad import SileroVAD

        return SileroVAD(params)
    if name == "webrtc_vad":
        from app.inference_pipeline.vad.webrtc_vad import WebRTCVAD

        return WebRTCVAD(params)
    if name == "sherpa_onnx_vad":
        from app.inference_pipeline.vad.sherpa_onnx_vad import SherpaOnnxVAD

        return SherpaOnnxVAD(params)
    raise ContractValidationError(f"unknown vad component {name!r}")


def write_regions_jsonable(regions: Sequence[SpeechRegion]) -> list[JsonObject]:
    """Return JSON-safe SpeechRegion rows."""

    return [region.to_jsonable() for region in regions]


def _vad_component(config: object) -> object | None:
    components = getattr(config, "components", None)
    if isinstance(components, Mapping):
        return components.get("vad")
    if isinstance(config, Mapping):
        raw_components = config.get("components")
        if isinstance(raw_components, Mapping):
            return raw_components.get("vad")
        return config.get("vad")
    return None


def _component_name(component: object) -> str:
    if isinstance(component, Mapping):
        return str(component.get("name") or "")
    return str(getattr(component, "name", ""))


def _component_enabled(component: object) -> bool:
    if isinstance(component, Mapping):
        return bool(component.get("enabled", True))
    return bool(getattr(component, "enabled", True))


def _component_params(component: object) -> Mapping[str, object]:
    if isinstance(component, Mapping):
        value = component.get("params") or {}
    else:
        value = getattr(component, "params", {}) or {}
    if not isinstance(value, Mapping):
        raise ContractValidationError("vad params must be a mapping")
    return value


def _float_value(value: object, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc


def _int_alias(
    data: Mapping[str, object],
    aliases: tuple[str, ...],
    default: int,
    field_name: str,
) -> int:
    value = default
    for alias in aliases:
        if alias in data:
            value = data[alias]
            break
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc


def component_report_path(reports_root: Path, run_id: str) -> Path:
    """Return the required VAD component report path for a run id."""

    return reports_root / "component_reports" / "vad" / f"vad_comparison_{run_id}.md"
