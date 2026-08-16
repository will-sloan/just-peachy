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


class EnergyVADAdapter(ComponentAdapter):
    component_slot = "vad"
    component_name = "energy_vad"


class WebRTCVADAdapter(ComponentAdapter):
    component_slot = "vad"
    component_name = "webrtc_vad"


class SherpaOnnxVADAdapter(ComponentAdapter):
    component_slot = "vad"
    component_name = "sherpa_onnx_vad"


class FSMNVADAdapter(ComponentAdapter):
    component_slot = "vad"
    component_name = "fsmn_vad"


class NoOpSegmentationAdapter(ComponentAdapter):
    component_slot = "segmentation"
    component_name = "no_op_segmentation"


class VADChunkerAdapter(ComponentAdapter):
    component_slot = "segmentation"
    component_name = "vad_chunks"


class NoOpDiarizationAdapter(ComponentAdapter):
    component_slot = "diarization"
    component_name = "no_op_diarization"


class PyannoteCommunityDiarizationAdapter(ComponentAdapter):
    component_slot = "diarization"
    component_name = "pyannote_community"


class SherpaOnnxDiarizationAdapter(ComponentAdapter):
    component_slot = "diarization"
    component_name = "sherpa_onnx_diarization"


class PicovoiceFalconDiarizationAdapter(ComponentAdapter):
    component_slot = "diarization"
    component_name = "picovoice_falcon"


class NemoDiarizationAdapter(ComponentAdapter):
    component_slot = "diarization"
    component_name = "nemo_diarization"


class NoOpASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "no_op_asr"


class WhisperTinyASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "whisper_tiny"


class WhisperBaseASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "whisper_base"


class WhisperSmallASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "whisper_small"


class FasterWhisperASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "faster_whisper"


class SherpaOnnxASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "sherpa_onnx"


class SherpaOnnxLibriGigaZipformer20230621ASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "sherpa_onnx_libri_giga_zipformer_2023_06_21"


class SherpaOnnxStreamingZipformer20MInt8ASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "sherpa_onnx_streaming_zipformer_20m_int8"


class MoonshineStreamingTinyASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "moonshine_streaming_tiny"


class MoonshineStreamingSmallASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "moonshine_streaming_small"


class MoonshineStreamingMediumASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "moonshine_streaming_medium"


class VoskASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "vosk"


class WeNetASRAdapter(ComponentAdapter):
    component_slot = "asr"
    component_name = "wenet"


class NoOpSpeakerEmbeddingAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "no_op_speaker_embedding"


class SpeechBrainECAPAAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "speechbrain_ecapa"


class WeSpeakerEmbeddingAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "wespeaker"


class SherpaOnnxSpeakerEmbeddingAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "sherpa_onnx_speaker_embedding"


class CAMPlusSpeakerEmbeddingCatalogAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "campplus_speaker_embedding"


class ERes2NetBaseSpeakerEmbeddingCatalogAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "eres2net_base_speaker_embedding"


class ResemblyzerSpeakerEmbeddingAdapter(ComponentAdapter):
    component_slot = "speaker_embedding"
    component_name = "resemblyzer"


class NoOpSpeakerMatchingAdapter(ComponentAdapter):
    component_slot = "speaker_matching"
    component_name = "no_op_speaker_matching"


class CosineThresholdSpeakerMatchingAdapter(ComponentAdapter):
    component_slot = "speaker_matching"
    component_name = "cosine_threshold"


REGISTERED_COMPONENTS: dict[str, dict[str, type[ComponentAdapter]]] = {
    "vad": {
        EnergyVADAdapter.component_name: EnergyVADAdapter,
        FSMNVADAdapter.component_name: FSMNVADAdapter,
        NoOpVADAdapter.component_name: NoOpVADAdapter,
        SherpaOnnxVADAdapter.component_name: SherpaOnnxVADAdapter,
        SileroVADAdapter.component_name: SileroVADAdapter,
        WebRTCVADAdapter.component_name: WebRTCVADAdapter,
    },
    "segmentation": {
        NoOpSegmentationAdapter.component_name: NoOpSegmentationAdapter,
        VADChunkerAdapter.component_name: VADChunkerAdapter,
    },
    "diarization": {
        NemoDiarizationAdapter.component_name: NemoDiarizationAdapter,
        NoOpDiarizationAdapter.component_name: NoOpDiarizationAdapter,
        PicovoiceFalconDiarizationAdapter.component_name: PicovoiceFalconDiarizationAdapter,
        PyannoteCommunityDiarizationAdapter.component_name: PyannoteCommunityDiarizationAdapter,
        SherpaOnnxDiarizationAdapter.component_name: SherpaOnnxDiarizationAdapter,
    },
    "asr": {
        FasterWhisperASRAdapter.component_name: FasterWhisperASRAdapter,
        MoonshineStreamingMediumASRAdapter.component_name: MoonshineStreamingMediumASRAdapter,
        MoonshineStreamingSmallASRAdapter.component_name: MoonshineStreamingSmallASRAdapter,
        MoonshineStreamingTinyASRAdapter.component_name: MoonshineStreamingTinyASRAdapter,
        NoOpASRAdapter.component_name: NoOpASRAdapter,
        SherpaOnnxASRAdapter.component_name: SherpaOnnxASRAdapter,
        SherpaOnnxLibriGigaZipformer20230621ASRAdapter.component_name: SherpaOnnxLibriGigaZipformer20230621ASRAdapter,
        SherpaOnnxStreamingZipformer20MInt8ASRAdapter.component_name: SherpaOnnxStreamingZipformer20MInt8ASRAdapter,
        VoskASRAdapter.component_name: VoskASRAdapter,
        WeNetASRAdapter.component_name: WeNetASRAdapter,
        WhisperBaseASRAdapter.component_name: WhisperBaseASRAdapter,
        WhisperSmallASRAdapter.component_name: WhisperSmallASRAdapter,
        WhisperTinyASRAdapter.component_name: WhisperTinyASRAdapter,
    },
    "speaker_embedding": {
        CAMPlusSpeakerEmbeddingCatalogAdapter.component_name: CAMPlusSpeakerEmbeddingCatalogAdapter,
        ERes2NetBaseSpeakerEmbeddingCatalogAdapter.component_name: ERes2NetBaseSpeakerEmbeddingCatalogAdapter,
        NoOpSpeakerEmbeddingAdapter.component_name: NoOpSpeakerEmbeddingAdapter,
        ResemblyzerSpeakerEmbeddingAdapter.component_name: ResemblyzerSpeakerEmbeddingAdapter,
        SherpaOnnxSpeakerEmbeddingAdapter.component_name: SherpaOnnxSpeakerEmbeddingAdapter,
        SpeechBrainECAPAAdapter.component_name: SpeechBrainECAPAAdapter,
        WeSpeakerEmbeddingAdapter.component_name: WeSpeakerEmbeddingAdapter,
    },
    "speaker_matching": {
        CosineThresholdSpeakerMatchingAdapter.component_name: CosineThresholdSpeakerMatchingAdapter,
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
            slot: component.to_jsonable() for slot, component in resolved.items()
        },
    }
