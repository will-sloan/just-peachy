"""Component registry for dry-run inference pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.inference_pipeline.config import (
    COMPONENT_SLOTS,
    ComponentConfig,
    ConfigValidationError,
    PipelineConfig,
)
from app.inference_pipeline.typing import JsonObject


class UnknownComponentError(ConfigValidationError):
    """Raised when a config names a component that is not registered."""


class ComponentAdapter:
    """Base class for lightweight adapter placeholders."""

    component_slot: ClassVar[str] = ""
    component_name: ClassVar[str] = ""

    @classmethod
    def dry_run_metadata(cls, component: ComponentConfig) -> JsonObject:
        """Return adapter metadata without loading model weights."""

        return {
            "component_slot": cls.component_slot,
            "component_name": cls.component_name,
            "adapter_class": cls.__name__,
            "enabled": component.enabled,
            "params": dict(component.params or {}),
        }


class DisabledComponentAdapter(ComponentAdapter):
    """Placeholder for components intentionally disabled by config."""

    component_slot = "disabled"
    component_name = "disabled"


class NoOpVADAdapter(ComponentAdapter):
    component_slot = "vad"
    component_name = "no_op_vad"


class SileroVADAdapter(ComponentAdapter):
    component_slot = "vad"
    component_name = "silero_vad"


class NoOpSegmentationAdapter(ComponentAdapter):
    component_slot = "segmentation"
    component_name = "no_op_segmentation"


class NoOpASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "no_op_asr"


class WhisperTinyASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "whisper_tiny"


class NoOpSpeakerEmbeddingAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "no_op_speaker_embedding"


class SpeechBrainECAPAAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "speechbrain_ecapa"


class NoOpSpeakerMatchingAdapter(ComponentAdapter):
    component_slot = "speaker_matching"
    component_name = "no_op_speaker_matching"


REGISTERED_COMPONENTS: dict[str, dict[str, type[ComponentAdapter]]] = {
    "vad": {
        NoOpVADAdapter.component_name: NoOpVADAdapter,
        SileroVADAdapter.component_name: SileroVADAdapter,
    },
    "segmentation": {
        NoOpSegmentationAdapter.component_name: NoOpSegmentationAdapter,
    },
    "asr": {
        NoOpASRAdapter.component_name: NoOpASRAdapter,
        WhisperTinyASRAdapter.component_name: WhisperTinyASRAdapter,
    },
    "speaker_embedding": {
        NoOpSpeakerEmbeddingAdapter.component_name: NoOpSpeakerEmbeddingAdapter,
        SpeechBrainECAPAAdapter.component_name: SpeechBrainECAPAAdapter,
    },
    "speaker_matching": {
        NoOpSpeakerMatchingAdapter.component_name: NoOpSpeakerMatchingAdapter,
    },
}


@dataclass(frozen=True)
class ResolvedComponent:
    """A config component resolved to a lightweight adapter class."""

    slot: str
    name: str
    enabled: bool
    adapter_class: type[ComponentAdapter]
    requested_adapter: str | None
    params: JsonObject

    def to_jsonable(self) -> JsonObject:
        """Return dry-run safe details for this resolved component."""

        return {
            "slot": self.slot,
            "name": self.name,
            "enabled": self.enabled,
            "adapter_class": self.adapter_class.__name__,
            "requested_adapter": self.requested_adapter,
            "params": dict(self.params),
        }


def resolve_component(slot: str, component: ComponentConfig) -> ResolvedComponent:
    """Resolve one configured component to its adapter class."""

    if slot not in COMPONENT_SLOTS:
        raise UnknownComponentError(f"unknown component slot {slot!r}")
    if not component.enabled:
        return ResolvedComponent(
            slot=slot,
            name=component.name,
            enabled=False,
            adapter_class=DisabledComponentAdapter,
            requested_adapter=component.adapter,
            params=dict(component.params or {}),
        )

    registry = REGISTERED_COMPONENTS.get(slot, {})
    adapter_class = registry.get(component.name)
    if adapter_class is None:
        known = ", ".join(sorted(registry)) or "none"
        raise UnknownComponentError(
            f"unknown component {component.name!r} for slot {slot!r}; known: {known}"
        )
    return ResolvedComponent(
        slot=slot,
        name=component.name,
        enabled=True,
        adapter_class=adapter_class,
        requested_adapter=component.adapter,
        params=dict(component.params or {}),
    )


def resolve_components(config: PipelineConfig) -> dict[str, ResolvedComponent]:
    """Resolve all configured components without instantiating model adapters."""

    return {
        slot: resolve_component(slot, config.components[slot])
        for slot in COMPONENT_SLOTS
    }


def dry_run_config(config: PipelineConfig) -> JsonObject:
    """Return JSON-safe selected component details without loading models."""

    resolved = resolve_components(config)
    return {
        "config_name": config.config_name,
        "profile": config.profile,
        "future": config.future,
        "notes": config.notes,
        "runtime": config.runtime.to_jsonable(),
        "components": {
            slot: component.to_jsonable()
            for slot, component in resolved.items()
        },
    }

