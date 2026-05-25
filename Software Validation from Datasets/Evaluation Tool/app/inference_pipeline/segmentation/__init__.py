"""Segmentation interfaces and chunking policies."""

from app.inference_pipeline.segmentation.base import (
    FixedSegmenter,
    NoOpSegmenter,
    SegmenterBase,
    SegmenterParameters,
    SegmentTrace,
    build_segmenter_from_config,
    component_report_path,
    trace_segments,
    write_segments_jsonable,
)
from app.inference_pipeline.segmentation.report import (
    SegmentationMetrics,
    summarize_segments,
    write_segmentation_report,
)
from app.inference_pipeline.segmentation.vad_chunker import VADChunker

__all__ = [
    "FixedSegmenter",
    "NoOpSegmenter",
    "SegmentTrace",
    "SegmentationMetrics",
    "SegmenterBase",
    "SegmenterParameters",
    "VADChunker",
    "build_segmenter_from_config",
    "component_report_path",
    "summarize_segments",
    "trace_segments",
    "write_segmentation_report",
    "write_segments_jsonable",
]
