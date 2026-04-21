"""Stub external model runner.

Replace ``predict_one`` with a call into another person's inference code.
The evaluator only requires a standardized ``UtterancePrediction`` back.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.model_runner.base import ModelRunner, prediction_from_record
from app.prediction_io.schema import UtterancePrediction
from app.utils.json_utils import write_jsonl


class ExternalStubRunner(ModelRunner):
    """Minimal external-inference integration point."""

    name = "external_stub"

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
            "The current stub writes blank transcript predictions so scoring can still\n"
            "exercise the missing/poor-output path. Replace predict_one() in\n"
            "app/model_runner/external_stub.py with the real inference call.\n",
            encoding="utf-8",
        )
        logger.info("Wrote external stub manifest with %d rows", len(records))

    def predict_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> UtterancePrediction:
        # Replace this method with a call such as:
        # text = external_asr.transcribe(record["audio_path_resolved"], run_config)
        text = ""
        return prediction_from_record(record, text)
