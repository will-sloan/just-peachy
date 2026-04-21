"""Score standardized predictions against normalized references."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from app.augmentation.processor import record_duration_sec
from app.dataset_registry.registry import DatasetDefinition
from app.prediction_io.jsonl import prediction_files_present, read_utterance_predictions
from app.prediction_io.rttm import RttmSegment, read_rttm_segments
from app.scoring.text import normalize_for_scoring
from app.scoring.wer import compute_wer
from app.utils.json_utils import write_json


@dataclass(frozen=True)
class ScoreResult:
    """Paths and aggregate metrics from scoring."""

    per_recording_metrics_path: Path
    aggregate_metrics_path: Path
    aggregate_metrics: dict[str, object]


def score_run(
    run_dir: Path,
    definition: DatasetDefinition,
    selection_records: list[dict[str, object]],
    logger: logging.Logger,
) -> ScoreResult:
    """Score a run folder's ``predictions/utterances.jsonl`` file."""

    predictions_path = run_dir / "predictions" / "utterances.jsonl"
    if predictions_path.exists():
        prediction_rows = read_utterance_predictions(predictions_path)
    else:
        prediction_rows = []
        logger.warning("Prediction file does not exist: %s", predictions_path)

    predictions_by_key: dict[tuple[str, str], dict[str, object]] = {}
    duplicate_count = 0
    for row in prediction_rows:
        recording_id = str(row["recording_id"])
        utt_id = str(row.get("utt_id") or recording_id)
        key = (recording_id, utt_id)
        if key in predictions_by_key:
            duplicate_count += 1
            continue
        predictions_by_key[key] = row

    metric_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    for record in tqdm(selection_records, desc="Scoring", unit="utt"):
        recording_id = str(record["recording_id"])
        utt_id = str(record.get("utt_id") or recording_id)
        prediction = predictions_by_key.get((recording_id, utt_id))
        missing_prediction = prediction is None
        if missing_prediction:
            hypothesis_text = None
            missing_row = _missing_prediction_record(definition, record, recording_id, utt_id)
            missing_rows.append(missing_row)
            logger.warning(
                "Missing prediction for recording_id=%s utt_id=%s condition=%s",
                recording_id,
                utt_id,
                record.get("augmentation_condition_id") or "clean",
            )
        else:
            hypothesis_text = prediction.get("text", "")

        reference_norm = normalize_for_scoring(
            record.get("reference_text", ""),
            definition.text_normalization,
        )
        if missing_prediction:
            hypothesis_norm = ""
            wer = None
        else:
            hypothesis_norm = normalize_for_scoring(
                hypothesis_text,
                definition.text_normalization,
            )
            wer = compute_wer(reference_norm, hypothesis_norm)
        reference_speaker = _normalize_speaker_label(record.get("speaker_label"))
        predicted_speaker = _normalize_speaker_label(
            prediction.get("speaker_label") if prediction is not None else None
        )
        speaker_label_scored = bool(reference_speaker or predicted_speaker)
        speaker_label_match = (
            reference_speaker == predicted_speaker if speaker_label_scored and not missing_prediction else None
        )

        row = {
            "recording_id": recording_id,
            "source_recording_id": record.get("source_recording_id", recording_id),
            "utt_id": utt_id,
            "speaker_label": record.get("speaker_label"),
            "predicted_speaker_label": predicted_speaker,
            "speaker_label_scored": speaker_label_scored,
            "speaker_label_match": speaker_label_match,
            "reference_text": reference_norm,
            "hypothesis_text": hypothesis_norm,
            "transcript_scored": not missing_prediction,
            "wer": wer.wer if wer is not None else None,
            "errors": wer.errors if wer is not None else None,
            "substitutions": wer.substitutions if wer is not None else None,
            "deletions": wer.deletions if wer is not None else None,
            "insertions": wer.insertions if wer is not None else None,
            "reference_words": wer.reference_words if wer is not None else len(reference_norm.split()),
            "hypothesis_words": wer.hypothesis_words if wer is not None else None,
            "duration_sec": record_duration_sec(record),
            "missing_prediction": missing_prediction,
            "audio_exists": record.get("audio_exists"),
            "audio_path_project_relative": record.get("audio_path_project_relative"),
        }
        optional_columns = {
            "augmentation_condition_id",
            "augmentation_mode",
            "rir_path",
            "rir_label",
            "noise_type",
            "snr_db",
            "split",
            "subset_group",
            "session_id",
            "speaker_id",
            "speaker_id_ref",
            "recording_speaker_id_ref",
            "speaker_code",
            "gender",
            "accent",
            "accent_group",
            "speaker_variant_group",
            "query_name",
            "speaker_id_padded",
            "room",
            "distractor",
            "mic",
            "device",
            "device_id",
            "channel_id",
            "microphone_id",
            "position",
            "degrees",
            "ref_device",
            "location",
            "location_hint",
            "distance_distractor_1",
            "distance_distractor_2",
            "distance_distractor_3",
            "distance_floor",
            "distance_foreground",
            "distance_foreground_class",
            "pesq_nb",
            "pesq_wb",
            "pesq_wb_class",
            "stoi",
            "stoi_class",
            "siib",
            "srmr",
            "srmr_class",
            "distant_audio_path_project_relative",
            "source_audio_path_project_relative",
            "meeting_id",
            "stream_type",
            "stream_id",
            "agent",
            "speaker_global_name",
            "speaker_role",
            "headset_channel",
            "meeting_type",
            "visibility",
            "seen_type",
            "utterance_key",
            "segment_ref_id",
            "segment_id",
            "word_start_id",
            "word_end_id",
            "has_overlap_candidate",
            "participant_sex",
            "native_language",
            "education",
            "reader_id",
            "reader_name",
            "reader_split",
            "audio_quality",
            "clean_vs_other",
            "chapter_id",
            "book_id",
            "audio_filepath_relative",
            *definition.supported_subset_filters,
            *definition.group_metric_columns,
        }
        for optional in sorted(optional_columns):
            if optional in record:
                row[optional] = record.get(optional)
        metric_rows.append(row)

    metrics_dir = run_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    per_recording_path = metrics_dir / "per_recording_metrics.csv"
    metrics_df = _sanitize_metric_dataframe(pd.DataFrame(metric_rows))
    metrics_df.to_csv(per_recording_path, index=False)

    aggregate = _aggregate_metrics(
        metrics_df=metrics_df,
        prediction_count=len(prediction_rows),
        duplicate_count=duplicate_count,
        unexpected_prediction_count=len(
            set(predictions_by_key)
            - {
                (str(r["recording_id"]), str(r.get("utt_id") or r["recording_id"]))
                for r in selection_records
            }
        ),
    )
    aggregate["prediction_files_present"] = prediction_files_present(run_dir / "predictions")
    rttm_summary = _score_rttm_segments(run_dir, selection_records, metrics_dir)
    if rttm_summary is not None:
        aggregate["segment_speaker_summary"] = rttm_summary
    aggregate_path = metrics_dir / "aggregate_metrics.json"
    write_json(aggregate_path, aggregate)

    missing_predictions_path = metrics_dir / "missing_predictions.csv"
    pd.DataFrame(missing_rows, columns=_missing_prediction_columns(definition)).to_csv(
        missing_predictions_path,
        index=False,
    )
    _write_speaker_confusion(metrics_df, metrics_dir)

    if "augmentation_condition_id" in metrics_df.columns and metrics_df["augmentation_condition_id"].notna().any():
        for condition, group in metrics_df.groupby("augmentation_condition_id", dropna=False):
            if pd.isna(condition):
                continue
            condition_dir = metrics_dir / _safe_condition_folder(str(condition))
            condition_dir.mkdir(parents=True, exist_ok=True)
            group.to_csv(condition_dir / "per_recording_metrics.csv", index=False)
            write_json(
                condition_dir / "aggregate_metrics.json",
                _aggregate_metrics(
                    metrics_df=group,
                    prediction_count=int(_scored_metrics_df(group).shape[0]),
                    duplicate_count=0,
                    unexpected_prediction_count=0,
                ),
            )

    group_columns = [
        *definition.group_metric_columns,
        "augmentation_condition_id",
        "augmentation_mode",
        "snr_db",
        "rir_label",
        "noise_type",
    ]
    for group_column in dict.fromkeys(group_columns):
        if group_column in metrics_df.columns and metrics_df[group_column].notna().any():
            group_df = _group_metrics(metrics_df, group_column)
            group_df.to_csv(metrics_dir / f"{group_column}_metrics.csv", index=False)

    logger.info("Scored %d selected recordings", len(selection_records))
    return ScoreResult(
        per_recording_metrics_path=per_recording_path,
        aggregate_metrics_path=aggregate_path,
        aggregate_metrics=aggregate,
    )


def _sanitize_metric_dataframe(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize metric dtypes so missing predictions remain safe downstream."""

    result = metrics_df.copy()
    if "missing_prediction" in result.columns:
        result["missing_prediction"] = result["missing_prediction"].fillna(False).astype(bool)
    else:
        result["missing_prediction"] = False
    if "transcript_scored" not in result.columns:
        result["transcript_scored"] = ~result["missing_prediction"]
    result["transcript_scored"] = result["transcript_scored"].fillna(False).astype(bool)

    for column in (
        "wer",
        "errors",
        "substitutions",
        "deletions",
        "insertions",
        "reference_words",
        "hypothesis_words",
        "duration_sec",
    ):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    for column in ("recording_id", "utt_id", "reference_text", "hypothesis_text"):
        if column in result.columns:
            result[column] = result[column].fillna("").astype(str)
    return result


def _scored_metrics_df(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Return rows with real prediction text metrics."""

    if metrics_df.empty:
        return metrics_df
    scored = metrics_df
    if "missing_prediction" in scored.columns:
        scored = scored[scored["missing_prediction"] == False]  # noqa: E712
    if "transcript_scored" in scored.columns:
        scored = scored[scored["transcript_scored"] == True]  # noqa: E712
    if "wer" in scored.columns:
        scored = scored[scored["wer"].notna()]
    return scored


def _missing_prediction_columns(definition: DatasetDefinition) -> list[str]:
    columns = [
        "dataset",
        "dataset_id",
        "recording_id",
        "utt_id",
        "source_recording_id",
        "audio_path_project_relative",
        "audio_path_resolved",
        "reason",
        "augmentation_condition_id",
        "augmentation_mode",
        "rir_label",
        "noise_type",
        "snr_db",
    ]
    for column in definition.group_metric_columns:
        if column not in columns:
            columns.append(column)
    return columns


def _missing_prediction_record(
    definition: DatasetDefinition,
    record: dict[str, object],
    recording_id: str,
    utt_id: str,
) -> dict[str, object]:
    row = {column: record.get(column) for column in _missing_prediction_columns(definition)}
    row.update(
        {
            "dataset": record.get("dataset") or definition.display_name,
            "dataset_id": record.get("dataset_id") or definition.dataset_id,
            "recording_id": recording_id,
            "utt_id": utt_id,
            "source_recording_id": record.get("source_recording_id", recording_id),
            "audio_path_project_relative": record.get("audio_path_project_relative"),
            "audio_path_resolved": record.get("audio_path_resolved"),
            "reason": "no matching row in predictions/utterances.jsonl",
            "augmentation_condition_id": record.get("augmentation_condition_id") or "clean",
            "augmentation_mode": record.get("augmentation_mode") or "none",
        }
    )
    return row


def _aggregate_metrics(
    metrics_df: pd.DataFrame,
    prediction_count: int,
    duplicate_count: int,
    unexpected_prediction_count: int,
) -> dict[str, object]:
    if metrics_df.empty:
        return {
            "selected_recordings": 0,
            "selected_recording_count": 0,
            "prediction_rows": int(prediction_count),
            "processed_predictions": 0,
            "processed_prediction_count": 0,
            "duplicate_prediction_rows_ignored": int(duplicate_count),
            "unexpected_prediction_recordings": int(unexpected_prediction_count),
            "aggregate_wer": None,
            "mean_recording_wer": None,
            "missing_predictions": 0,
            "missing_prediction_count": 0,
            "missing_prediction_rate": 0.0,
            "speaker_label_scored": 0,
            "speaker_label_matches": 0,
            "speaker_label_accuracy": None,
        }

    selected_count = int(len(metrics_df))
    scored_df = _scored_metrics_df(metrics_df)
    missing_count = int(metrics_df["missing_prediction"].fillna(False).astype(bool).sum())
    reference_words = int(scored_df["reference_words"].sum()) if not scored_df.empty else 0
    errors = int(scored_df["errors"].sum()) if not scored_df.empty else 0
    aggregate_wer = errors / reference_words if reference_words else 0.0
    speaker_summary = _speaker_label_summary(metrics_df)
    return {
        "selected_recordings": selected_count,
        "selected_recording_count": selected_count,
        "prediction_rows": int(prediction_count),
        "processed_predictions": int(len(scored_df)),
        "processed_prediction_count": int(len(scored_df)),
        "duplicate_prediction_rows_ignored": int(duplicate_count),
        "unexpected_prediction_recordings": int(unexpected_prediction_count),
        "missing_predictions": missing_count,
        "missing_prediction_count": missing_count,
        "missing_prediction_rate": missing_count / selected_count if selected_count else 0.0,
        "audio_missing": int((metrics_df["audio_exists"] == False).sum()),  # noqa: E712
        "total_duration_sec": float(metrics_df["duration_sec"].sum()),
        "scored_duration_sec": float(scored_df["duration_sec"].sum()) if not scored_df.empty else 0.0,
        "reference_words": reference_words,
        "hypothesis_words": int(scored_df["hypothesis_words"].sum()) if not scored_df.empty else 0,
        "errors": errors,
        "substitutions": int(scored_df["substitutions"].sum()) if not scored_df.empty else 0,
        "deletions": int(scored_df["deletions"].sum()) if not scored_df.empty else 0,
        "insertions": int(scored_df["insertions"].sum()) if not scored_df.empty else 0,
        "aggregate_wer": aggregate_wer,
        "mean_recording_wer": _optional_mean(scored_df, "wer"),
        "median_recording_wer": _optional_median(scored_df, "wer"),
        "max_recording_wer": _optional_max(scored_df, "wer"),
        **speaker_summary,
    }


def _group_metrics(metrics_df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    working = _metrics_with_valid_group_labels(metrics_df, group_column)
    output_columns = [
        group_column,
        "file_count",
        "recordings",
        "processed_predictions",
        "processed_prediction_count",
        "missing_predictions",
        "missing_prediction_count",
        "total_duration_sec",
        "scored_duration_sec",
        "reference_words",
        "errors",
        "substitutions",
        "deletions",
        "insertions",
        "aggregate_wer",
        "mean_recording_wer",
        "speaker_label_scored",
        "speaker_label_matches",
        "speaker_label_accuracy",
    ]
    if working.empty:
        return pd.DataFrame(columns=output_columns)
    rows: list[dict[str, object]] = []
    for value, group in working.groupby("_group_label", sort=True, dropna=True):
        scored_group = _scored_metrics_df(group)
        reference_words = int(scored_group["reference_words"].sum()) if not scored_group.empty else 0
        errors = int(scored_group["errors"].sum()) if not scored_group.empty else 0
        row = {
            group_column: value,
            "file_count": int(len(group)),
            "recordings": int(len(group)),
            "processed_predictions": int(len(scored_group)),
            "processed_prediction_count": int(len(scored_group)),
            "missing_predictions": int(group["missing_prediction"].fillna(False).astype(bool).sum()),
            "missing_prediction_count": int(group["missing_prediction"].fillna(False).astype(bool).sum()),
            "total_duration_sec": float(group["duration_sec"].sum()),
            "scored_duration_sec": float(scored_group["duration_sec"].sum()) if not scored_group.empty else 0.0,
            "reference_words": reference_words,
            "errors": errors,
            "substitutions": int(scored_group["substitutions"].sum()) if not scored_group.empty else 0,
            "deletions": int(scored_group["deletions"].sum()) if not scored_group.empty else 0,
            "insertions": int(scored_group["insertions"].sum()) if not scored_group.empty else 0,
            "aggregate_wer": errors / reference_words if reference_words else 0.0,
            "mean_recording_wer": _optional_mean(scored_group, "wer"),
        }
        row.update(_speaker_label_summary(group))
        rows.append(row)
    return pd.DataFrame(rows, columns=output_columns).sort_values(
        group_column,
        key=lambda series: series.astype(str),
    )


def _metrics_with_valid_group_labels(metrics_df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """Return the full metrics table restricted only by valid labels for this group."""

    if group_column not in metrics_df.columns:
        return metrics_df.iloc[0:0].copy()
    working = metrics_df.copy()
    working["_group_label"] = working[group_column].map(_group_label_or_none)
    return working[working["_group_label"].notna()].copy()


def _speaker_label_summary(metrics_df: pd.DataFrame) -> dict[str, object]:
    if "speaker_label_scored" not in metrics_df.columns or "speaker_label_match" not in metrics_df.columns:
        return {
            "speaker_label_scored": 0,
            "speaker_label_matches": 0,
            "speaker_label_accuracy": None,
        }
    scored = metrics_df[
        (metrics_df["speaker_label_scored"] == True)  # noqa: E712
        & (metrics_df["missing_prediction"] == False)  # noqa: E712
    ]
    scored_count = int(len(scored))
    matches = int((scored["speaker_label_match"] == True).sum()) if scored_count else 0  # noqa: E712
    return {
        "speaker_label_scored": scored_count,
        "speaker_label_matches": matches,
        "speaker_label_accuracy": matches / scored_count if scored_count else None,
    }


def _write_speaker_confusion(metrics_df: pd.DataFrame, metrics_dir: Path) -> None:
    required = {"speaker_label", "predicted_speaker_label", "speaker_label_scored"}
    if metrics_df.empty or not required.issubset(metrics_df.columns):
        return
    scored = metrics_df[
        (metrics_df["speaker_label_scored"] == True)  # noqa: E712
        & (metrics_df["missing_prediction"] == False)  # noqa: E712
    ].copy()
    if scored.empty:
        return
    scored["speaker_label"] = scored["speaker_label"].fillna("").astype(str)
    scored["predicted_speaker_label"] = scored["predicted_speaker_label"].fillna("").astype(str)
    confusion = (
        scored.groupby(["speaker_label", "predicted_speaker_label"], dropna=False)
        .agg(
            file_count=("recording_id", "size"),
            total_duration_sec=("duration_sec", "sum"),
            mean_wer=("wer", "mean"),
        )
        .reset_index()
        .sort_values("file_count", ascending=False)
    )
    confusion.to_csv(metrics_dir / "speaker_label_confusion.csv", index=False)


def _score_rttm_segments(
    run_dir: Path,
    selection_records: list[dict[str, object]],
    metrics_dir: Path,
) -> dict[str, object] | None:
    rttm_path = run_dir / "predictions" / "segments.rttm"
    if not rttm_path.exists():
        return None

    predicted_segments = read_rttm_segments(rttm_path)
    predicted_by_recording: dict[str, list[RttmSegment]] = {}
    for segment in predicted_segments:
        predicted_by_recording.setdefault(segment.recording_id, []).append(segment)

    rows: list[dict[str, object]] = []
    total_reference_duration = 0.0
    total_overlap_duration = 0.0
    speaker_matches = 0
    segments_with_overlap = 0

    for record in selection_records:
        recording_id = str(record["recording_id"])
        start_sec = _optional_float(record.get("start_sec"))
        end_sec = _optional_float(record.get("end_sec"))
        reference_speaker = _normalize_speaker_label(record.get("speaker_label"))
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            continue
        duration_sec = end_sec - start_sec
        total_reference_duration += duration_sec
        best_segment, overlap_sec = _best_overlap(
            predicted_by_recording.get(recording_id, []),
            start_sec,
            end_sec,
        )
        predicted_speaker = best_segment.speaker_label if best_segment is not None else ""
        speaker_match = bool(best_segment and predicted_speaker == reference_speaker)
        if best_segment is not None and overlap_sec > 0:
            segments_with_overlap += 1
            total_overlap_duration += overlap_sec
        if speaker_match:
            speaker_matches += 1
        rows.append(
            {
                "recording_id": recording_id,
                "utt_id": record.get("utt_id"),
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": duration_sec,
                "reference_speaker_label": reference_speaker,
                "predicted_speaker_label": predicted_speaker,
                "best_overlap_sec": overlap_sec,
                "best_overlap_ratio": overlap_sec / duration_sec if duration_sec else 0.0,
                "speaker_match": speaker_match,
            }
        )

    if rows:
        pd.DataFrame(rows).to_csv(metrics_dir / "segment_speaker_metrics.csv", index=False)

    summary = {
        "rttm_path": "predictions/segments.rttm",
        "predicted_segments": len(predicted_segments),
        "reference_segments_scored": len(rows),
        "segments_with_overlap": segments_with_overlap,
        "speaker_matches_on_best_overlap": speaker_matches,
        "segment_speaker_accuracy": speaker_matches / len(rows) if rows else None,
        "reference_duration_sec": total_reference_duration,
        "overlap_duration_sec": total_overlap_duration,
        "overlap_coverage": (
            total_overlap_duration / total_reference_duration if total_reference_duration else None
        ),
    }
    write_json(metrics_dir / "segment_speaker_summary.json", summary)
    return summary


def _best_overlap(
    predicted_segments: list[RttmSegment],
    reference_start: float,
    reference_end: float,
) -> tuple[RttmSegment | None, float]:
    best_segment: RttmSegment | None = None
    best_overlap = 0.0
    for segment in predicted_segments:
        overlap = max(0.0, min(reference_end, segment.end_sec) - max(reference_start, segment.start_sec))
        if overlap > best_overlap:
            best_overlap = overlap
            best_segment = segment
    return best_segment, best_overlap


def _normalize_speaker_label(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _label_value(value: object) -> str:
    label = _group_label_or_none(value)
    return label if label is not None else "(missing)"


def _group_label_or_none(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "null"}:
        return None
    return text


def _optional_mean(metrics_df: pd.DataFrame, column: str) -> float | None:
    if metrics_df.empty or column not in metrics_df.columns:
        return None
    value = metrics_df[column].mean()
    return None if pd.isna(value) else float(value)


def _optional_median(metrics_df: pd.DataFrame, column: str) -> float | None:
    if metrics_df.empty or column not in metrics_df.columns:
        return None
    value = metrics_df[column].median()
    return None if pd.isna(value) else float(value)


def _optional_max(metrics_df: pd.DataFrame, column: str) -> float | None:
    if metrics_df.empty or column not in metrics_df.columns:
        return None
    value = metrics_df[column].max()
    return None if pd.isna(value) else float(value)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_condition_folder(condition: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in condition)[:120]
