"""Stub external model runner.

The evaluator only requires a standardized ``UtterancePrediction`` back.
M4 routes this runner through a dummy modular pipeline before real models exist.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.inference_pipeline.pipeline import PipelineRunner
from app.model_runner.base import ModelRunner
from app.prediction_io.schema import UtterancePrediction
from app.utils.json_utils import write_jsonl


class ExternalStubRunner(ModelRunner):
    """Minimal external-inference integration point."""

    name = "external_stub"

    def __init__(self, pipeline_runner: PipelineRunner | None = None) -> None:
        self.pipeline_runner = pipeline_runner or PipelineRunner.with_dummy_components()

    def before_run(
        self,
        records: list[dict[str, object]],
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        manifest_rows = []
        for record in records:
            manifest_rows.append(
                {
                    "recording_id": record.get("recording_id"),
                    "source_recording_id": record.get("source_recording_id"),
                    "utt_id": record.get("utt_id"),
                    "start_sec": record.get("start_sec"),
                    "end_sec": record.get("end_sec"),
                    "speaker_label": record.get("speaker_label"),
                    "audio_path": record.get("inference_audio_path") or record.get("audio_path_resolved"),
                    "source_audio_path": record.get("source_audio_path_resolved") or record.get("audio_path_resolved"),
                    "clean_source_audio_path": record.get("source_audio_path_resolved"),
                    "distant_audio_path": record.get("distant_audio_path_resolved"),
                    "audio_path_project_relative": record.get("inference_audio_project_relative")
                    or record.get("audio_path_project_relative"),
                    "source_audio_path_project_relative": record.get("source_audio_path_project_relative"),
                    "distant_audio_path_project_relative": record.get("distant_audio_path_project_relative"),
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
            "It receives each selected recording_id, resolved audio_path, and run_config.\n"
            "For augmented runs, predict_one() receives record['inference_audio_path'],\n"
            "which points at a temporary augmented WAV valid during that call.\n"
            "The current stub calls a dummy modular pipeline that returns deterministic\n"
            "placeholder transcript predictions so scoring can exercise the external\n"
            "runner integration path before real model adapters exist.\n",
            encoding="utf-8",
        )
        logger.info("Wrote external stub manifest with %d rows", len(records))

    def predict_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> UtterancePrediction:
        output = self.pipeline_runner.run_one(record, run_config, logger)
        return UtterancePrediction(
            recording_id=output.recording_id,
            utt_id=output.utt_id,
            start_sec=output.start_sec,
            end_sec=output.end_sec,
            speaker_label=output.speaker_label,
            text=output.text,
        )
