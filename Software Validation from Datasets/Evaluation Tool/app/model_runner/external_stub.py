"""External model runner integration point."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.inference_pipeline.pipeline import PipelineRunner
from app.model_runner.base import ModelRunner
from app.prediction_io.schema import UtterancePrediction
from app.utils.json_utils import write_jsonl
from app.utils.run_artifacts import relative_artifact_record


class ExternalStubRunner(ModelRunner):
    """Minimal external-inference integration point."""

    name = "external_stub"

    def __init__(
        self,
        pipeline_runner: PipelineRunner | None = None,
        *,
        config_path: Path | str | None = None,
    ) -> None:
        self.pipeline_runner = pipeline_runner
        self.config_path = Path(config_path) if config_path is not None else _default_config_path()
        self._diagnostics_rows: list[dict[str, object]] = []

    def before_run(
        self,
        records: list[dict[str, object]],
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
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
            "The current runner calls the modular inference pipeline and writes\n"
            "diagnostics.jsonl beside utterances.jsonl for debugging. The evaluator\n"
            "contract remains predictions/utterances.jsonl.\n",
            encoding="utf-8",
        )
        self._diagnostics_rows = []
        logger.info("Wrote external stub manifest with %d rows", len(records))

    def after_run(
        self,
        result,
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        _ = (result, run_config)
        if not self._diagnostics_rows:
            return
        write_jsonl(predictions_dir / "diagnostics.jsonl", self._diagnostics_rows)
        logger.info("Wrote external stub diagnostics with %d rows", len(self._diagnostics_rows))

    def predict_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> UtterancePrediction:
        pipeline = self._pipeline_runner()
        output = _run_pipeline(pipeline, record, run_config, logger)
        self._diagnostics_rows.append(_diagnostics_row(output, pipeline))
        return UtterancePrediction(
            recording_id=output.recording_id,
            utt_id=output.utt_id,
            start_sec=output.start_sec,
            end_sec=output.end_sec,
            speaker_label=output.speaker_label,
            text=output.text,
        )

    def _pipeline_runner(self) -> PipelineRunner:
        if self.pipeline_runner is None:
            self.pipeline_runner = PipelineRunner.from_config_path(self.config_path)
        return self.pipeline_runner


def _run_pipeline(
    pipeline: Any,
    record: dict[str, object],
    run_config: dict[str, object],
    logger: logging.Logger,
):
    predict = getattr(pipeline, "predict", None)
    if callable(predict):
        return predict(record, run_config)
    return pipeline.run_one(record, run_config, logger)


def _diagnostics_row(output: Any, pipeline: Any) -> dict[str, object]:
    diagnostics = getattr(output, "diagnostics", None)
    if diagnostics is None:
        diagnostics = getattr(pipeline, "last_diagnostics", None)
    return {
        "recording_id": output.recording_id,
        "utt_id": output.utt_id,
        "start_sec": output.start_sec,
        "end_sec": output.end_sec,
        "speaker_label": output.speaker_label,
        "diagnostics": diagnostics or {},
        "warnings": list(getattr(output, "warnings", ()) or ()),
        "errors": list(getattr(output, "errors", ()) or ()),
    }


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "inference" / "e2e_named_transcript.yaml"
