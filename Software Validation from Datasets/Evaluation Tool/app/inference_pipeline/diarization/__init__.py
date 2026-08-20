"""Optional diarization interfaces and adapters."""

from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationMetrics,
    DiarizationParameters,
    DiarizationUnavailableError,
    FixedDiarizer,
    NoOpDiarizer,
    SpeakerTurnRegion,
    build_diarizer_from_config,
    component_report_path,
    diarization_error_rate,
    jaccard_error_rate,
    mark_overlapping_turns,
    named_speaker_false_assignment_rate,
    overlap_segment_detection_rate,
    speaker_turns_to_rttm_lines,
    speaker_turns_to_speech_regions,
    summarize_diarization_baseline,
    write_diarization_report,
    write_turns_jsonable,
)
from app.inference_pipeline.diarization.pyannote_adapter import (
    PyannoteCommunityDiarizer,
    PyannoteDiarizationUnavailableError,
)
from app.inference_pipeline.diarization.falcon_adapter import (
    FalconDiarizationUnavailableError,
    PicovoiceFalconDiarizer,
)
from app.inference_pipeline.diarization.nemo_adapter import (
    NemoDiarizationUnavailableError,
    NemoDiarizer,
)
from app.inference_pipeline.diarization.sherpa_onnx_adapter import (
    SherpaOnnxDiarizationUnavailableError,
    SherpaOnnxDiarizer,
)
from app.inference_pipeline.diarization.modular_adapter import (
    ModularClusteringDiarizer,
    ModularDiarizationUnavailableError,
)

__all__ = [
    "DiarizationBase",
    "DiarizationMetrics",
    "DiarizationParameters",
    "DiarizationUnavailableError",
    "FixedDiarizer",
    "FalconDiarizationUnavailableError",
    "NemoDiarizationUnavailableError",
    "NemoDiarizer",
    "NoOpDiarizer",
    "ModularClusteringDiarizer",
    "ModularDiarizationUnavailableError",
    "PyannoteCommunityDiarizer",
    "PyannoteDiarizationUnavailableError",
    "PicovoiceFalconDiarizer",
    "SherpaOnnxDiarizationUnavailableError",
    "SherpaOnnxDiarizer",
    "SpeakerTurnRegion",
    "build_diarizer_from_config",
    "component_report_path",
    "diarization_error_rate",
    "jaccard_error_rate",
    "mark_overlapping_turns",
    "named_speaker_false_assignment_rate",
    "overlap_segment_detection_rate",
    "speaker_turns_to_rttm_lines",
    "speaker_turns_to_speech_regions",
    "summarize_diarization_baseline",
    "write_diarization_report",
    "write_turns_jsonable",
]
