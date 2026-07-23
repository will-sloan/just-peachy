"""ONNX-first speech pipeline package for the existing Evaluation Tool."""

from .contracts import InferenceRecord, UtterancePredictionData, SpeakerMatch, SpeechSegment
from .config import PipelineConfig, load_pipeline_config
from .pipeline import OnnxSpeechPipeline

__all__ = [
    "InferenceRecord",
    "UtterancePredictionData",
    "SpeakerMatch",
    "SpeechSegment",
    "PipelineConfig",
    "load_pipeline_config",
    "OnnxSpeechPipeline",
]
