from __future__ import annotations

from pathlib import Path

from .config import PipelineConfig, load_pipeline_config
from .pipeline import OnnxSpeechPipeline
from .speaker.store import EnrollmentStore


def build_pipeline_from_config(config: PipelineConfig | str | Path) -> OnnxSpeechPipeline:
    """Build the pipeline from config.

    Deliberately conservative:
    - generic orchestration is owned here
    - model backends should be filled in by Codex prompt sequence
    """
    if isinstance(config, (str, Path)):
        config = load_pipeline_config(config)

    enrollment_store = None
    if config.enrollment.enabled:
        enrollment_store = EnrollmentStore(Path(config.enrollment.store_path))
        if enrollment_store.path.exists():
            enrollment_store.load()

    # TODO:
    # - create SherpaWhisperBackend when config.asr.backend == "sherpa_whisper"
    # - create SherpaMoonshineBackend when config.asr.backend == "sherpa_moonshine"
    # - create SileroOnnxBackend when config.vad.enabled
    # - create WeSpeakerCampPlusOnnxBackend when config.speaker.enabled
    # - create SherpaPunctuationBackend when config.punctuation.enabled

    return OnnxSpeechPipeline(
        asr=None,
        vad=None,
        speaker_embedder=None,
        punctuator=None,
        enrollment_store=enrollment_store,
        accept_threshold=config.thresholds.accept_threshold,
        margin_threshold=config.thresholds.margin_threshold,
        unknown_label=config.thresholds.unknown_label,
        asr_sample_rate=config.asr.sample_rate,
        vad_trim_only=config.vad.trim_only,
    )
