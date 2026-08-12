"""Voice activity detection interfaces and adapters."""

from app.inference_pipeline.vad.base import (
    FixedVAD,
    NoOpVAD,
    VADBase,
    VADParameters,
    build_vad_from_config,
    component_report_path,
    write_regions_jsonable,
)
from app.inference_pipeline.vad.report import VADMetrics, summarize_vad, write_vad_report
from app.inference_pipeline.vad.sherpa_onnx_vad import (
    SherpaOnnxVAD,
    SherpaOnnxVADUnavailableError,
)
from app.inference_pipeline.vad.webrtc_vad import WebRTCVAD, WebRTCVADUnavailableError
from app.inference_pipeline.vad.fsmn_vad import FSMNVAD, FSMNVADUnavailableError

__all__ = [
    "FixedVAD",
    "FSMNVAD",
    "FSMNVADUnavailableError",
    "NoOpVAD",
    "SherpaOnnxVAD",
    "SherpaOnnxVADUnavailableError",
    "VADBase",
    "VADMetrics",
    "VADParameters",
    "WebRTCVAD",
    "WebRTCVADUnavailableError",
    "build_vad_from_config",
    "component_report_path",
    "summarize_vad",
    "write_regions_jsonable",
    "write_vad_report",
]
