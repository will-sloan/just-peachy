"""Example integration patch for `external_stub.py`.

Copy the ideas from this file into the real runner once the backends are implemented.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.onnx_pipeline.adapters.evaluation_tool import (
    prediction_to_evaluation_dict,
    record_from_evaluation_dict,
)
from app.onnx_pipeline.factory import build_pipeline_from_config


@lru_cache(maxsize=1)
def _get_pipeline():
    config_path = Path("configs/onnx_pipeline.desktop.example.yaml")
    return build_pipeline_from_config(config_path)


def predict_one_example(record: dict, run_config: dict | None = None, logger=None) -> dict:
    pipeline = _get_pipeline()
    inference_record = record_from_evaluation_dict(record)
    prediction = pipeline.predict_record(inference_record)
    if logger is not None:
        logger.info("Predicted record_id=%s utt_id=%s", prediction.recording_id, prediction.utt_id)
    return prediction_to_evaluation_dict(prediction)
