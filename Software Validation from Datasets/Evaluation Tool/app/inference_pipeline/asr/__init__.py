"""ASR interfaces and adapters."""

from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    ASRRuntimeStats,
    FixedASR,
    NoOpASR,
    build_asr_from_config,
    normalize_text,
    transcript_to_jsonable,
)
from app.inference_pipeline.asr.metrics import (
    consecutive_duplicate_token_rate,
    empty_output_rate,
    hallucinated_output_rate,
    repeated_ngram_rate,
    repeated_word_rate,
)
from app.inference_pipeline.asr.report import (
    ASRQualityMetrics,
    summarize_asr_quality,
    write_asr_report,
)

__all__ = [
    "ASRBase",
    "ASRContext",
    "ASRQualityMetrics",
    "ASRRuntimeStats",
    "FixedASR",
    "NoOpASR",
    "build_asr_from_config",
    "consecutive_duplicate_token_rate",
    "empty_output_rate",
    "hallucinated_output_rate",
    "normalize_text",
    "repeated_ngram_rate",
    "repeated_word_rate",
    "summarize_asr_quality",
    "transcript_to_jsonable",
    "write_asr_report",
]
