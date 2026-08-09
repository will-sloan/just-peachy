"""Grouped native-condition analysis over independently completed Stage 11 results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import pyarrow as pa

from app.diarization_evaluation.artifacts import (
    write_checksum_manifest,
    write_json_atomic,
    write_parquet_atomic,
)
from app.diarization_evaluation.contracts import DiarizationEvaluationError
from app.diarization_evaluation.execution import validate_diarization_result


GROUPING_DIMENSIONS = (
    "dataset",
    "meeting_id",
    "session_id",
    "stream_type",
    "stream_id",
    "channel_id",
    "microphone_id",
    "device_id",
    "location",
    "room",
    "distractor",
    "mic",
    "position",
)


def aggregate_native_results(result_roots: Sequence[Path], output_root: Path) -> dict[str, object]:
    """Validate, index, and group native results without inventing unsupported metrics."""

    item_rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for root in sorted((path.resolve() for path in result_roots), key=str):
        validation = validate_diarization_result(root)
        run = json.loads((root / "run.json").read_text(encoding="utf-8"))
        metrics = json.loads((root / "metrics" / "summary.json").read_text(encoding="utf-8"))
        key = (str(run["evaluation_unit_id"]), str(run["backend_id"]))
        if key in seen:
            raise DiarizationEvaluationError(f"duplicate native result: {key}")
        seen.add(key)
        record = dict(run["record"])
        item_rows.append(
            {
                "schema_version": "native-diarization-item-metrics.v1",
                "evaluation_unit_id": key[0],
                "backend_id": key[1],
                "speaker_count_mode": run["speaker_count_mode"],
                "metrics_emitted": bool(metrics.get("metrics_emitted")),
                "der": metrics.get("der"),
                "jer": metrics.get("jer"),
                "missed_speech_sec": metrics.get("missed_speech_sec"),
                "false_alarm_sec": metrics.get("false_alarm_sec"),
                "speaker_confusion_sec": metrics.get("speaker_confusion_sec"),
                "reference_speaker_time_sec": metrics.get("reference_speaker_time_sec"),
                "predicted_speaker_count": metrics.get("predicted_speaker_count"),
                "reference_speaker_count": metrics.get("reference_speaker_count"),
                "speaker_count_error": metrics.get("speaker_count_error"),
                "anonymous_label_consistency": metrics.get("anonymous_label_consistency"),
                "suppression_reasons": json.dumps(metrics.get("suppression_reasons", [])),
                "result_folder": root.name,
                "artifact_count": validation["artifact_count"],
                **{dimension: record.get(dimension) for dimension in GROUPING_DIMENSIONS},
            }
        )
    if not item_rows:
        raise DiarizationEvaluationError("no completed native diarization results were supplied")
    grouped_rows = _group_rows(item_rows)
    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    write_parquet_atomic(root / "item_metrics.parquet", pa.Table.from_pylist(item_rows))
    write_parquet_atomic(root / "grouped_metrics.parquet", pa.Table.from_pylist(grouped_rows))
    summary: dict[str, object] = {
        "schema_version": "native-diarization-analysis.v1",
        "result_count": len(item_rows),
        "metric_result_count": sum(int(row["metrics_emitted"]) for row in item_rows),
        "suppressed_result_count": sum(int(not row["metrics_emitted"]) for row in item_rows),
        "backends": sorted({str(row["backend_id"]) for row in item_rows}),
        "datasets": sorted({str(row["dataset"]) for row in item_rows}),
        "grouping_dimensions": list(GROUPING_DIMENSIONS),
        "unsupported_metrics_are_null": True,
        "artifacts": ["item_metrics.parquet", "grouped_metrics.parquet"],
    }
    write_json_atomic(root / "summary.json", summary)
    write_checksum_manifest(root)
    return summary


def _group_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    backend_modes = sorted(
        {(str(row["backend_id"]), str(row["speaker_count_mode"])) for row in rows}
    )
    for backend_id, speaker_count_mode in backend_modes:
        backend_rows = [
            row
            for row in rows
            if row["backend_id"] == backend_id
            and row["speaker_count_mode"] == speaker_count_mode
        ]
        for dimension in GROUPING_DIMENSIONS:
            values = sorted(
                {str(row[dimension]) for row in backend_rows if row.get(dimension) is not None}
            )
            for value in values:
                group = [row for row in backend_rows if str(row.get(dimension)) == value]
                valid = [row for row in group if row["metrics_emitted"]]
                denominator = sum(float(row["reference_speaker_time_sec"]) for row in valid)
                missed = sum(float(row["missed_speech_sec"]) for row in valid)
                false_alarm = sum(float(row["false_alarm_sec"]) for row in valid)
                confusion = sum(float(row["speaker_confusion_sec"]) for row in valid)
                output.append(
                    {
                        "schema_version": "native-diarization-grouped-metrics.v1",
                        "backend_id": backend_id,
                        "speaker_count_mode": speaker_count_mode,
                        "grouping_dimension": dimension,
                        "grouping_value": value,
                        "result_count": len(group),
                        "metric_result_count": len(valid),
                        "suppressed_result_count": len(group) - len(valid),
                        "der": (
                            (missed + false_alarm + confusion) / denominator
                            if denominator > 0
                            else None
                        ),
                        "mean_jer": (
                            sum(float(row["jer"]) for row in valid) / len(valid)
                            if valid
                            else None
                        ),
                        "reference_speaker_time_sec": denominator if valid else None,
                        "missed_speech_sec": missed if valid else None,
                        "false_alarm_sec": false_alarm if valid else None,
                        "speaker_confusion_sec": confusion if valid else None,
                        "mean_speaker_count_error": (
                            sum(float(row["speaker_count_error"]) for row in valid) / len(valid)
                            if valid
                            else None
                        ),
                    }
                )
    return output
