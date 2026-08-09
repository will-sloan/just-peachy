"""Explicit configured-pipeline runner for ordinary Evaluation Tool runs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

from app.inference_pipeline.contracts import PipelineOutput
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.resolver import ResolvedPipeline
from app.model_runner.base import ModelRunner
from app.prediction_io.rttm import write_rttm_lines
from app.prediction_io.schema import UtterancePrediction
from app.utils.json_utils import write_json, write_jsonl
from app.utils.run_artifacts import relative_artifact_config


UNKNOWN_SPEAKER_LABEL = "Unknown"
UNKNOWN_SPEAKER_ALIASES = frozenset(
    {
        "<unknown>",
        "unk",
        "unknown",
        "unknown speaker",
        "unknown_speaker",
        "speaker unknown",
        "speaker_unknown",
        "unavailable",
    }
)
PROVENANCE_FIELDS = (
    "source_recording_id",
    "channel_index",
    "channel_count",
    "channel_id",
    "stream_id",
    "stream_type",
    "microphone_id",
    "device_id",
    "session_id",
    "meeting_id",
    "augmentation_condition_id",
    "augmentation_mode",
    "rir_label",
    "noise_type",
    "snr_db",
)


class ConfiguredRunnerOutputError(ValueError):
    """Raised when configured inference returns malformed or changed identity."""


class ConfiguredEvaluatorRunner(ModelRunner):
    """Run a resolved pipeline through the existing Evaluation Tool lifecycle."""

    name = "configured"

    def __init__(
        self,
        resolution: ResolvedPipeline,
        *,
        pipeline_runner: PipelineRunner | object | None = None,
    ) -> None:
        self.resolution = resolution
        self.pipeline_runner = pipeline_runner
        self._diagnostics_rows: list[dict[str, object]] = []
        self._failure_rows: list[dict[str, object]] = []
        self._diarization_rttm_lines: list[str] = []

    def before_run(
        self,
        records: list[dict[str, object]],
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        _ = records
        self._diagnostics_rows = []
        self._failure_rows = []
        self._diarization_rttm_lines = []
        run_dir = _run_dir(predictions_dir, run_config)
        artifact_paths = self.resolution.write_artifacts(run_dir / "inference")
        write_json(
            run_dir / "inference" / "configured_runner_artifacts.json",
            {
                "schema_version": "configured-runner-artifacts.v1",
                "runner": self.name,
                "files": {
                    key: path.relative_to(run_dir).as_posix()
                    for key, path in artifact_paths.items()
                },
                "predictions": "predictions/utterances.jsonl",
                "diagnostics": "predictions/diagnostics.jsonl",
                "failures": "predictions/failures.jsonl",
            },
        )
        logger.info(
            "Configured runner selected %s with %d warning(s)",
            self.resolution.pipeline_config.config_name,
            len(self.resolution.warnings),
        )

    def after_run(
        self,
        result,
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        _ = result
        project_root = _optional_path(run_config.get("project_root"))
        diagnostics = [
            relative_artifact_config(
                row,
                artifact_root=predictions_dir,
                project_root=project_root,
            )
            for row in self._diagnostics_rows
        ]
        failures = [
            relative_artifact_config(
                row,
                artifact_root=predictions_dir,
                project_root=project_root,
            )
            for row in self._failure_rows
        ]
        write_jsonl(predictions_dir / "diagnostics.jsonl", diagnostics)
        write_jsonl(predictions_dir / "failures.jsonl", failures)
        if self._diarization_rttm_lines:
            lines = list(dict.fromkeys(self._diarization_rttm_lines))
            write_rttm_lines(predictions_dir / "segments.rttm", lines)
        logger.info(
            "Configured runner wrote %d diagnostic row(s) and %d failure row(s)",
            len(diagnostics),
            len(failures),
        )

    def predict_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> UtterancePrediction:
        output = _run_pipeline(
            self._pipeline(),
            record,
            _pipeline_run_config(run_config, self.resolution),
            logger,
        )
        validated = _validated_output(output, record)
        original_speaker_label = validated.speaker_label
        normalized_speaker_label = _normalize_unknown_speaker(
            original_speaker_label,
            configured_unknown_tokens=_configured_unknown_tokens(self.resolution),
        )
        text = validated.text
        if text is None:
            text = ""
        if not isinstance(text, str):
            raise ConfiguredRunnerOutputError("pipeline output text must be a string or null")
        errors = tuple(validated.errors or ())
        if errors:
            raise ConfiguredRunnerOutputError(
                "pipeline output contains error(s): " + "; ".join(str(item) for item in errors)
            )

        diagnostics = dict(validated.diagnostics or {})
        rttm_lines = diagnostics.get("diarization_rttm_lines")
        if isinstance(rttm_lines, list):
            self._diarization_rttm_lines.extend(
                str(line) for line in rttm_lines if str(line).strip()
            )
        row: dict[str, object] = {
            "recording_id": validated.recording_id,
            "utt_id": validated.utt_id,
            "start_sec": validated.start_sec,
            "end_sec": validated.end_sec,
            "speaker_label": normalized_speaker_label,
            "provenance": _record_provenance(record),
            "diagnostics": diagnostics,
            "warnings": list(validated.warnings or ()),
            "errors": [],
        }
        if original_speaker_label != normalized_speaker_label:
            row["speaker_label_normalization"] = {
                "original": original_speaker_label,
                "normalized": normalized_speaker_label,
            }
        self._diagnostics_rows.append(row)
        return UtterancePrediction(
            recording_id=validated.recording_id,
            utt_id=validated.utt_id,
            start_sec=validated.start_sec,
            end_sec=validated.end_sec,
            speaker_label=normalized_speaker_label,
            text=text,
        )

    def on_item_failure(
        self,
        record: dict[str, object],
        error: Exception,
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        _ = (predictions_dir, logger)
        status, prerequisite_status = _failure_status(error)
        self._failure_rows.append(
            {
                "recording_id": record.get("recording_id"),
                "utt_id": record.get("utt_id"),
                "start_sec": record.get("start_sec"),
                "end_sec": record.get("end_sec"),
                "provenance": _record_provenance(record),
                "status": status,
                "prerequisite_status": prerequisite_status,
                "error_type": type(error).__name__,
                "message": _safe_error_message(str(error), run_config),
            }
        )

    def _pipeline(self) -> Any:
        if self.pipeline_runner is None:
            self.pipeline_runner = PipelineRunner.from_config(self.resolution.pipeline_config)
        return self.pipeline_runner


def _run_pipeline(
    pipeline: object,
    record: dict[str, object],
    run_config: dict[str, object],
    logger: logging.Logger,
) -> object:
    predict = getattr(pipeline, "predict", None)
    if callable(predict):
        return predict(record, run_config)
    run_one = getattr(pipeline, "run_one", None)
    if callable(run_one):
        return run_one(record, run_config, logger)
    raise ConfiguredRunnerOutputError("configured pipeline has no predict or run_one method")


def _validated_output(output: object, record: Mapping[str, object]) -> PipelineOutput:
    if not isinstance(output, PipelineOutput):
        raise ConfiguredRunnerOutputError(
            f"configured pipeline must return PipelineOutput, got {type(output).__name__}"
        )
    expected_recording_id = str(record.get("recording_id") or "")
    expected_utt_id = str(record.get("utt_id") or "")
    if output.recording_id != expected_recording_id:
        raise ConfiguredRunnerOutputError(
            f"recording_id changed from {expected_recording_id!r} to {output.recording_id!r}"
        )
    if output.utt_id != expected_utt_id:
        raise ConfiguredRunnerOutputError(
            f"utt_id changed from {expected_utt_id!r} to {output.utt_id!r}"
        )
    for field in ("start_sec", "end_sec"):
        expected = _optional_float(record.get(field))
        actual = getattr(output, field)
        if expected != actual:
            raise ConfiguredRunnerOutputError(
                f"{field} changed from {expected!r} to {actual!r}"
            )
    return output


def _pipeline_run_config(
    run_config: Mapping[str, object],
    resolution: ResolvedPipeline,
) -> dict[str, object]:
    result = dict(run_config)
    result["runtime"] = resolution.pipeline_config.runtime.to_jsonable()
    result["resolved_inference_config"] = {
        "config_name": resolution.pipeline_config.config_name,
        "profile": resolution.pipeline_config.profile,
        "allow_model_downloads": False,
    }
    return result


def _configured_unknown_tokens(resolution: ResolvedPipeline) -> tuple[str, ...]:
    params = resolution.pipeline_config.components["speaker_matching"].params or {}
    value = params.get("unknown_label")
    return (str(value),) if value is not None and str(value).strip() else ()


def _normalize_unknown_speaker(
    value: str | None,
    *,
    configured_unknown_tokens: tuple[str, ...],
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    aliases = set(UNKNOWN_SPEAKER_ALIASES)
    aliases.update(token.strip().casefold() for token in configured_unknown_tokens)
    return UNKNOWN_SPEAKER_LABEL if text.casefold() in aliases else text


def _record_provenance(record: Mapping[str, object]) -> dict[str, object]:
    return {field: record[field] for field in PROVENANCE_FIELDS if field in record}


def _failure_status(error: Exception) -> tuple[str, str | None]:
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    if "credential" in message or "access key" in message or "auth token" in message:
        return "unavailable", "credential_required"
    if isinstance(error, FileNotFoundError) or "asset" in message or "model path" in message:
        return "unavailable", "asset_required"
    if "platform" in message or "linux" in message:
        return "unavailable", "platform_required"
    if isinstance(error, ImportError) or "unavailable" in name or "not installed" in message:
        return "unavailable", "unavailable"
    return "failed", None


def _safe_error_message(message: str, run_config: Mapping[str, object]) -> str:
    safe = message
    for key in ("project_root", "run_dir"):
        value = run_config.get(key)
        if value is not None and str(value):
            safe = safe.replace(str(value), f"<{key}>")
            safe = safe.replace(str(value).replace("\\", "/"), f"<{key}>")
    return safe


def _run_dir(predictions_dir: Path, run_config: Mapping[str, object]) -> Path:
    value = run_config.get("run_dir")
    return Path(str(value)).resolve() if value is not None else predictions_dir.parent.resolve()


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfiguredRunnerOutputError("record timestamp must be numeric or null") from exc


def _optional_path(value: object) -> Path | None:
    if value is None or not str(value).strip():
        return None
    return Path(str(value))
