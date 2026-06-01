"""External model runner integration point."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping

from app.inference_pipeline.pipeline import (
    PipelineRunner,
    merge_pipeline_and_run_config,
    pipeline_config_mapping,
)
from app.model_runner.base import ModelRunner
from app.model_runner.base import RunnerResult
from app.prediction_io.schema import UtterancePrediction
from app.utils.json_utils import write_json
from app.utils.json_utils import write_jsonl
from app.utils.run_artifacts import relative_artifact_record


class ExternalStubRunner(ModelRunner):
    """Evaluation Tool bridge for the end-to-end inference pipeline."""

    name = "external_stub"

    def __init__(
        self,
        pipeline_runner: object | None = None,
        inference_config: Mapping[str, object] | str | Path | None = None,
    ) -> None:
        self.pipeline_runner = pipeline_runner
        self.inference_config = inference_config
        self._pipeline_config: dict[str, object] | None = None
        self._diagnostic_rows: list[dict[str, object]] = []

    def before_run(
        self,
        records: list[dict[str, object]],
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        self._ensure_pipeline(run_config)
        self._diagnostic_rows = []
        manifest_rows = []
        for record in records:
            artifact_record = relative_artifact_record(record, artifact_root=predictions_dir)
            audio_path = (
                artifact_record.get("inference_audio_path")
                or artifact_record.get("audio_path")
                or artifact_record.get("inference_audio_project_relative")
                or artifact_record.get("audio_path_project_relative")
            )
            source_audio_path = (
                artifact_record.get("source_audio_path")
                or artifact_record.get("source_audio_path_project_relative")
                or audio_path
            )
            manifest_rows.append(
                {
                    "recording_id": record.get("recording_id"),
                    "source_recording_id": record.get("source_recording_id"),
                    "utt_id": record.get("utt_id"),
                    "start_sec": record.get("start_sec"),
                    "end_sec": record.get("end_sec"),
                    "speaker_label": record.get("speaker_label"),
                    "audio_path": audio_path,
                    "source_audio_path": source_audio_path,
                    "clean_source_audio_path": artifact_record.get("clean_source_audio_path")
                    or artifact_record.get("source_audio_path_project_relative"),
                    "distant_audio_path": artifact_record.get("distant_audio_path"),
                    "audio_path_project_relative": artifact_record.get("inference_audio_project_relative")
                    or artifact_record.get("audio_path_project_relative"),
                    "source_audio_path_project_relative": artifact_record.get(
                        "source_audio_path_project_relative"
                    ),
                    "distant_audio_path_project_relative": artifact_record.get(
                        "distant_audio_path_project_relative"
                    ),
                    "augmentation_condition_id": record.get("augmentation_condition_id"),
                    "augmentation_mode": record.get("augmentation_mode"),
                    "rir_label": record.get("rir_label"),
                    "noise_type": record.get("noise_type"),
                    "snr_db": record.get("snr_db"),
                    "expected_prediction_file": "utterances.jsonl",
                }
            )
        write_jsonl(predictions_dir / "external_input_manifest.jsonl", manifest_rows)
        (predictions_dir / "README_external_stub.md").write_text(
            "# External Stub Runner\n\n"
            "This runner is a replaceable integration point for another ASR system.\n"
            "Its persisted manifest records project-relative audio paths and ids.\n"
            "For augmented runs, predict_one() receives record['inference_audio_path'],\n"
            "which points at a temporary augmented WAV valid during that call.\n"
            "The current bridge calls the configurable end-to-end inference pipeline\n"
            "and writes pipeline_diagnostics.jsonl beside the evaluator-compatible\n"
            "utterances.jsonl contract.\n",
            encoding="utf-8",
        )
        logger.info("Wrote external stub manifest with %d rows", len(records))

    def after_run(
        self,
        result: RunnerResult,
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        diagnostics_path = predictions_dir / "pipeline_diagnostics.jsonl"
        write_jsonl(diagnostics_path, self._diagnostic_rows)
        write_json(
            predictions_dir / "pipeline_diagnostics_summary.json",
            _diagnostics_summary(self._diagnostic_rows, result),
        )
        logger.info("Wrote pipeline diagnostics with %d rows", len(self._diagnostic_rows))

    def predict_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> UtterancePrediction:
        pipeline = self._ensure_pipeline(run_config)
        predict_config = merge_pipeline_and_run_config(self._pipeline_config, run_config)
        if hasattr(pipeline, "predict"):
            output = pipeline.predict(record, predict_config)
        else:
            output = pipeline.run_one(record, predict_config, logger)
        diagnostics = getattr(pipeline, "last_diagnostics", None)
        if isinstance(diagnostics, dict):
            self._diagnostic_rows.append(
                _diagnostic_row_with_reference(record, diagnostics)
            )
        return UtterancePrediction(
            recording_id=output.recording_id,
            utt_id=output.utt_id,
            start_sec=output.start_sec,
            end_sec=output.end_sec,
            speaker_label=output.speaker_label,
            text=output.text,
        )

    def _ensure_pipeline(self, run_config: Mapping[str, object]) -> object:
        if self.pipeline_runner is not None:
            return self.pipeline_runner
        self._pipeline_config = pipeline_config_mapping(self.inference_config or run_config)
        self.pipeline_runner = PipelineRunner.from_config(self._pipeline_config)
        return self.pipeline_runner


def _diagnostic_row_with_reference(
    record: Mapping[str, object],
    diagnostics: dict[str, object],
) -> dict[str, object]:
    row = dict(diagnostics)
    row["reference_speaker_label"] = record.get("speaker_label")
    row["augmentation_condition_id"] = record.get("augmentation_condition_id") or "clean"
    row["augmentation_mode"] = record.get("augmentation_mode") or "none"
    return row


def _diagnostics_summary(
    rows: list[dict[str, object]],
    result: RunnerResult,
) -> dict[str, object]:
    total = len(rows)
    unknown_count = 0
    known_count = 0
    false_known_count = 0
    speaker_label_scored = 0
    speaker_label_matches = 0
    chronological_violations = 0
    duplicate_tokens_removed = 0
    stage_seconds: dict[str, float] = {}
    realtime_factors: list[float] = []
    thresholds: set[float] = set()
    min_margins: set[float] = set()

    for row in rows:
        predicted = _label(row.get("speaker_label"))
        reference = _label(row.get("reference_speaker_label"))
        if reference:
            speaker_label_scored += 1
            if predicted == reference:
                speaker_label_matches += 1
        if predicted in {"", "Unknown"}:
            unknown_count += 1
        else:
            known_count += 1
            if reference and predicted != reference:
                false_known_count += 1
        speaker_decisions = row.get("speaker_decisions")
        if isinstance(speaker_decisions, list):
            for decision in speaker_decisions:
                if not isinstance(decision, Mapping):
                    continue
                threshold = _optional_float(decision.get("threshold"))
                min_margin = _optional_float(decision.get("min_margin"))
                if threshold is not None:
                    thresholds.add(threshold)
                if min_margin is not None:
                    min_margins.add(min_margin)
        chronological_violations += _int_value(row.get("chronological_ordering_violations"))
        duplicate_tokens_removed += _int_value(row.get("duplicate_text_tokens_removed"))
        runtime_breakdown = row.get("runtime_breakdown")
        if isinstance(runtime_breakdown, Mapping):
            rtf = _optional_float(runtime_breakdown.get("pipeline_realtime_factor"))
            if rtf is not None:
                realtime_factors.append(rtf)
            stages = runtime_breakdown.get("stage_seconds")
            if isinstance(stages, Mapping):
                for stage, seconds in stages.items():
                    stage_seconds[str(stage)] = stage_seconds.get(str(stage), 0.0) + (
                        _optional_float(seconds) or 0.0
                    )

    return {
        "runner": ExternalStubRunner.name,
        "attempted_count": result.attempted_count,
        "written_count": result.written_count,
        "failed_count": result.failed_count,
        "diagnostic_rows": total,
        "known_speaker_assignments": known_count,
        "unknown_speaker_assignments": unknown_count,
        "unknown_rate": unknown_count / total if total else None,
        "speaker_label_scored": speaker_label_scored,
        "speaker_label_matches": speaker_label_matches,
        "speaker_label_accuracy": (
            speaker_label_matches / speaker_label_scored
            if speaker_label_scored
            else None
        ),
        "false_known_speaker_assignments": false_known_count,
        "false_known_speaker_assignment_rate": false_known_count / total if total else None,
        "speaker_matching_thresholds": sorted(thresholds),
        "speaker_matching_min_margins": sorted(min_margins),
        "chronological_ordering_violations": chronological_violations,
        "duplicate_text_tokens_removed": duplicate_tokens_removed,
        "mean_pipeline_realtime_factor": (
            sum(realtime_factors) / len(realtime_factors)
            if realtime_factors
            else None
        ),
        "stage_runtime_sec": dict(sorted(stage_seconds.items())),
    }


def _label(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int_value(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
