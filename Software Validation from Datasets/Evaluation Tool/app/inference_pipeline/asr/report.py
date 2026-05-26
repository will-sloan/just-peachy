"""ASR component report writing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.inference_pipeline.asr.base import ASRRuntimeStats
from app.inference_pipeline.asr.metrics import (
    consecutive_duplicate_token_rate,
    empty_output_rate,
    hallucinated_output_rate,
    repeated_ngram_rate,
    repeated_word_rate,
)


@dataclass(frozen=True)
class ASRQualityMetrics:
    """Small ASR text-quality diagnostics."""

    repeated_word_rate: float
    repeated_ngram_rate: float
    consecutive_duplicate_token_rate: float
    empty_output_rate: float
    hallucinated_output_rate: float | None
    wer: float | None = None
    cer: float | None = None

    def to_markdown_rows(self) -> list[str]:
        return [
            f"- WER: `{_format_metric(self.wer)}`",
            f"- CER: `{_format_metric(self.cer)}`",
            f"- Repeated word rate: `{_format_metric(self.repeated_word_rate)}`",
            f"- Repeated n-gram rate: `{_format_metric(self.repeated_ngram_rate)}`",
            (
                "- Consecutive duplicate token rate: "
                f"`{_format_metric(self.consecutive_duplicate_token_rate)}`"
            ),
            f"- Empty-output rate: `{_format_metric(self.empty_output_rate)}`",
            f"- Hallucinated-output rate: `{_format_metric(self.hallucinated_output_rate)}`",
        ]


def summarize_asr_quality(
    outputs: Sequence[str],
    *,
    silence_flags: Sequence[bool] | None = None,
    wer: float | None = None,
    cer: float | None = None,
) -> ASRQualityMetrics:
    """Summarize diagnostic rates over ASR outputs."""

    joined = " ".join(outputs)
    return ASRQualityMetrics(
        repeated_word_rate=repeated_word_rate(joined),
        repeated_ngram_rate=repeated_ngram_rate(joined),
        consecutive_duplicate_token_rate=consecutive_duplicate_token_rate(joined),
        empty_output_rate=empty_output_rate(outputs),
        hallucinated_output_rate=(
            hallucinated_output_rate(outputs, silence_flags=silence_flags)
            if silence_flags is not None
            else None
        ),
        wer=wer,
        cer=cer,
    )


def write_asr_report(
    path: Path,
    *,
    run_id: str,
    backend_name: str,
    whisper_status: str,
    runtime_stats: ASRRuntimeStats | None,
    quality_metrics: ASRQualityMetrics | None,
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_command: str,
    runner_contract: str,
    config_switch_status: str,
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the M7 ASR component report artifact."""

    lines = [
        "# ASR Component Report",
        "",
        "## Milestone",
        "",
        "M7 - ASR Interface and First ASR Model Adapter",
        "",
        f"- Run id: `{run_id}`",
        f"- Selected ASR backend/model: `{backend_name}`",
        f"- Whisper status: {whisper_status}",
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Summary",
        "",
        "M7 adds a swappable ASR interface plus lazy real-model adapter boundaries.",
        "Deterministic adapters provide local smoke coverage without model downloads.",
        "",
        "## Runner Contract Preservation",
        "",
        runner_contract,
        "",
        "## Commands",
        "",
        *[f"- `{command}`" for command in test_commands],
        f"- `{smoke_command}`",
        "",
        "## Runtime Stats",
        "",
    ]
    if runtime_stats is None:
        lines.append("- Runtime stats: `n/a`")
    else:
        lines.extend(
            [
                f"- Model load time sec: `{_format_metric(runtime_stats.load_sec)}`",
                f"- Inference time sec: `{_format_metric(runtime_stats.inference_sec)}`",
                f"- Real-time factor: `{_format_metric(runtime_stats.realtime_factor)}`",
                f"- Device: `{runtime_stats.device}`",
                f"- Dtype: `{runtime_stats.dtype}`",
                f"- Peak GPU memory MB: `{_format_metric(runtime_stats.peak_gpu_memory_mb)}`",
                f"- CPU memory MB: `{_format_metric(runtime_stats.cpu_memory_mb)}`",
            ]
        )
    lines.extend(["", "## Quality Metrics", ""])
    if quality_metrics is None:
        lines.append("- Quality metrics: `n/a`")
    else:
        lines.extend(quality_metrics.to_markdown_rows())
    lines.extend(
        [
            "",
            "## Config Switch Status",
            "",
            config_switch_status,
            "",
            "## Blockers",
            "",
        ]
    )
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- None known.")
    lines.extend(["", "## Incomplete", ""])
    if incomplete:
        lines.extend(f"- {item}" for item in incomplete)
    else:
        lines.append("- None known.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"
