"""Build concise Markdown and JSON run reports."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.utils.json_utils import read_json, write_json


def build_report(run_dir: Path, logger: logging.Logger) -> Path:
    """Build a Markdown report for a scored run."""

    aggregate_path = run_dir / "metrics" / "aggregate_metrics.json"
    per_recording_path = run_dir / "metrics" / "per_recording_metrics.csv"
    if not aggregate_path.exists():
        raise FileNotFoundError(f"Cannot build report; missing {aggregate_path}")
    if not per_recording_path.exists():
        raise FileNotFoundError(f"Cannot build report; missing {per_recording_path}")

    aggregate = read_json(aggregate_path)
    if not isinstance(aggregate, dict):
        raise ValueError(f"Expected object in {aggregate_path}")
    per_recording = _sanitize_per_recording(pd.read_csv(per_recording_path))
    scored = _scored_rows(per_recording)
    worst = scored.sort_values(["wer", "errors"], ascending=False).head(10) if not scored.empty else scored

    report_dir = run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"
    summary_path = report_dir / "summary.json"

    lines = [
        "# Evaluation Report",
        "",
        f"- Run folder: `{run_dir.name}`",
        f"- Selected recordings: `{aggregate.get('selected_recordings')}`",
        f"- Prediction rows: `{aggregate.get('prediction_rows')}`",
        f"- Processed predictions: `{aggregate.get('processed_prediction_count', aggregate.get('processed_predictions'))}`",
        f"- Missing predictions: `{aggregate.get('missing_predictions')}`",
        f"- Missing prediction rate: `{_format_metric(aggregate.get('missing_prediction_rate'))}`",
        f"- Aggregate WER: `{_format_metric(aggregate.get('aggregate_wer'))}`",
        f"- Mean per-recording WER: `{_format_metric(aggregate.get('mean_recording_wer'))}`",
        f"- Reference words: `{aggregate.get('reference_words')}`",
        f"- Errors: `{aggregate.get('errors')}`",
        f"- Substitutions: `{aggregate.get('substitutions')}`",
        f"- Insertions: `{aggregate.get('insertions')}`",
        f"- Deletions: `{aggregate.get('deletions')}`",
        f"- Speaker label accuracy: `{_format_metric(aggregate.get('speaker_label_accuracy'))}`",
        f"- Speaker labels scored: `{aggregate.get('speaker_label_scored')}`",
        f"- Total duration sec: `{_format_metric(aggregate.get('total_duration_sec'))}`",
        "",
        "## Worst Recordings",
        "",
    ]
    if worst.empty:
        lines.append("No recordings with predictions were scored.")
    else:
        lines.append("| recording_id | WER | errors | missing |")
        lines.append("|---|---:|---:|---:|")
        for row in worst.itertuples(index=False):
            lines.append(
                f"| {_format_label(getattr(row, 'recording_id'))} | "
                f"{_format_metric(getattr(row, 'wer'))} | "
                f"{_format_count(getattr(row, 'errors'))} | "
                f"{getattr(row, 'missing_prediction')} |"
            )

    missing_path = run_dir / "metrics" / "missing_predictions.csv"
    if missing_path.exists():
        missing_df = pd.read_csv(missing_path)
        if not missing_df.empty:
            lines.extend(
                [
                    "",
                    "## Missing Predictions",
                    "",
                    f"`{len(missing_df)}` selected item(s) did not produce a prediction and were excluded from transcript-error aggregates.",
                    "",
                    "| recording_id | utt_id | reason | condition |",
                    "|---|---|---|---|",
                ]
            )
            for row in missing_df.head(20).itertuples(index=False):
                lines.append(
                    f"| {_format_label(getattr(row, 'recording_id', ''))} | "
                    f"{_format_label(getattr(row, 'utt_id', ''))} | "
                    f"{_format_label(getattr(row, 'reason', 'missing prediction'))} | "
                    f"{_format_label(getattr(row, 'augmentation_condition_id', 'clean'))} |"
                )

    segment_summary = aggregate.get("segment_speaker_summary")
    if isinstance(segment_summary, dict):
        lines.extend(
            [
                "",
                "## Segment Speaker Summary",
                "",
                f"- RTTM predicted segments: `{segment_summary.get('predicted_segments')}`",
                f"- Reference segments scored: `{segment_summary.get('reference_segments_scored')}`",
                f"- Segments with overlap: `{segment_summary.get('segments_with_overlap')}`",
                f"- Segment speaker accuracy: `{_format_metric(segment_summary.get('segment_speaker_accuracy'))}`",
                f"- Overlap coverage: `{_format_metric(segment_summary.get('overlap_coverage'))}`",
            ]
        )

    for group_metrics_path in sorted((run_dir / "metrics").glob("*_metrics.csv")):
        if group_metrics_path.name in {"per_recording_metrics.csv", "missing_predictions.csv"}:
            continue
        group_column = group_metrics_path.stem.removesuffix("_metrics")
        group_df = pd.read_csv(group_metrics_path)
        if group_df.empty or group_column not in group_df.columns:
            continue
        title = group_column.replace("_", " ").title()
        lines.extend(
            [
                "",
                f"## {title} Summary",
                "",
                f"| {group_column} | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |",
            ]
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for row in group_df.itertuples(index=False):
            lines.append(
                f"| {_format_label(getattr(row, group_column))} | "
                f"{_format_count(getattr(row, 'file_count', getattr(row, 'recordings', 0)))} | "
                f"{_format_metric(getattr(row, 'total_duration_sec', None))} | "
                f"{_format_metric(getattr(row, 'aggregate_wer', None))} | "
                f"{_format_count(getattr(row, 'substitutions', 0))} | "
                f"{_format_count(getattr(row, 'insertions', 0))} | "
                f"{_format_count(getattr(row, 'deletions', 0))} | "
                f"{_format_count(getattr(row, 'missing_predictions', 0))} |"
            )

    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `predictions/utterances.jsonl`",
            "- `metrics/per_recording_metrics.csv`",
            "- `metrics/aggregate_metrics.json`",
            "- `metrics/missing_predictions.csv`",
            "- `metrics/speaker_label_confusion.csv` when speaker-attributed predictions are scored",
            "- `metrics/segment_speaker_metrics.csv` when `predictions/segments.rttm` exists",
            "- `plots/`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(summary_path, aggregate)
    logger.info("Wrote report to %s", report_path)
    return report_path


def _format_metric(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        if pd.isna(value):
            return "n/a"
    except (TypeError, ValueError):
        pass
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _sanitize_per_recording(per_recording: pd.DataFrame) -> pd.DataFrame:
    result = per_recording.copy()
    if "missing_prediction" not in result.columns:
        result["missing_prediction"] = False
    result["missing_prediction"] = result["missing_prediction"].fillna(False).astype(bool)
    if "transcript_scored" not in result.columns:
        result["transcript_scored"] = ~result["missing_prediction"]
    result["transcript_scored"] = result["transcript_scored"].fillna(False).astype(bool)
    for column in ("wer", "errors"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _scored_rows(per_recording: pd.DataFrame) -> pd.DataFrame:
    scored = per_recording[
        (per_recording["missing_prediction"] == False)  # noqa: E712
        & (per_recording["transcript_scored"] == True)  # noqa: E712
    ].copy()
    if "wer" in scored.columns:
        scored = scored[scored["wer"].notna()]
    return scored


def _format_label(value: object) -> str:
    if value is None:
        return "(missing)"
    try:
        if pd.isna(value):
            return "(missing)"
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "null"}:
        return "(missing)"
    return text.replace("|", "\\|")


def _format_count(value: object) -> str:
    if value is None:
        return "0"
    try:
        if pd.isna(value):
            return "0"
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)
