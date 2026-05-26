"""ASR multi-model benchmark runner."""

from __future__ import annotations

import csv
import importlib.util
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.dataset_registry.registry import DatasetDefinition
from app.inference_pipeline.asr.base import ASRBase, FixedASR, NoOpASR, build_asr_from_config
from app.inference_pipeline.errors import InferencePipelineError
from app.inference_pipeline.metrics.asr_metrics import (
    aggregate_wer,
    aggregate_cer,
    composite_score,
    failure_rate,
    prediction_examples,
    runtime_realtime_factor,
    select_qualitative_examples,
    text_quality_metrics,
    throughput_items_per_sec,
    total_audio_duration_sec,
)
from app.inference_pipeline.pipeline import PipelineRunner
from app.model_runner.external_stub import ExternalStubRunner
from app.prediction_io.jsonl import read_utterance_predictions
from app.scoring.scorer import ScoreResult, score_run
from app.utils.json_utils import write_json
from app.utils.paths import safe_relative_to
from app.utils.run_artifacts import (
    ensure_run_subdirs,
    read_yaml,
    relative_artifact_config,
    write_yaml,
)


@dataclass(frozen=True)
class ASRModelConfig:
    """One ASR candidate in a benchmark sweep."""

    model_id: str
    label: str
    enabled: bool
    optional: bool
    component: Mapping[str, object]
    availability: Mapping[str, object]
    notes: str | None = None

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, object],
        *,
        sweep_path: Path | None = None,
        tool_root: Path | None = None,
    ) -> "ASRModelConfig":
        model_id = str(mapping.get("id") or mapping.get("model_id") or "").strip()
        if not model_id:
            raise ValueError("ASR benchmark model entry requires id")
        component = _component_from_entry(mapping, sweep_path=sweep_path, tool_root=tool_root)
        return cls(
            model_id=model_id,
            label=str(mapping.get("label") or model_id),
            enabled=bool(mapping.get("enabled", True)),
            optional=bool(mapping.get("optional", False)),
            component=component,
            availability=_mapping_or_empty(mapping.get("availability")),
            notes=_optional_string(mapping.get("notes")),
        )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "id": self.model_id,
            "label": self.label,
            "enabled": self.enabled,
            "optional": self.optional,
            "component": dict(self.component),
            "availability": dict(self.availability),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ASRModelResult:
    """Benchmark result for one ASR candidate."""

    model_id: str
    label: str
    status: str
    run_dir: Path
    config_snapshot_path: Path | None
    predictions_path: Path | None
    metrics: dict[str, object]
    examples: dict[str, dict[str, object] | None]
    skip_reason: str | None = None
    error: str | None = None

    def to_csv_row(self, *, benchmark_root: Path | None = None) -> dict[str, object]:
        row = {
            "model_id": self.model_id,
            "label": self.label,
            "status": self.status,
            "skip_reason": self.skip_reason,
            "error": self.error,
            "run_dir": _artifact_path(self.run_dir, benchmark_root),
            "predictions_path": (
                _artifact_path(self.predictions_path, benchmark_root)
                if self.predictions_path
                else ""
            ),
        }
        for key in CSV_METRIC_FIELDS:
            row[key] = self.metrics.get(key)
        return row


@dataclass(frozen=True)
class ASRBenchmarkResult:
    """Complete ASR benchmark output."""

    run_id: str
    benchmark_root: Path
    markdown_report_path: Path
    csv_report_path: Path
    model_results: tuple[ASRModelResult, ...]
    recommended_model_id: str | None


CSV_METRIC_FIELDS = (
    "wer",
    "cer",
    "runtime_sec",
    "realtime_factor",
    "throughput_items_per_sec",
    "load_sec",
    "peak_gpu_memory_mb",
    "cpu_memory_mb",
    "failure_rate",
    "empty_output_rate",
    "repeated_word_rate",
    "repeated_ngram_rate",
    "consecutive_duplicate_token_rate",
    "hallucinated_output_rate",
    "composite_score",
    "attempted_count",
    "written_count",
    "failed_count",
    "skipped_count",
)


def load_asr_sweep_config(path: Path, *, tool_root: Path | None = None) -> list[ASRModelConfig]:
    """Load ASR benchmark candidates from a sweep YAML file."""

    sweep_path = path.resolve()
    data = read_yaml(sweep_path)
    entries = data.get("models", [])
    if not isinstance(entries, list):
        raise ValueError("ASR sweep config requires a models list")
    return [
        ASRModelConfig.from_mapping(
            _mapping_value(entry, "models[]"),
            sweep_path=sweep_path,
            tool_root=tool_root or _default_tool_root(sweep_path),
        )
        for entry in entries
    ]


def run_asr_benchmark(
    *,
    records: Sequence[Mapping[str, object]],
    model_configs: Sequence[ASRModelConfig],
    run_id: str,
    output_root: Path,
    report_dir: Path,
    project_root: Path,
    base_run_config: Mapping[str, object],
    dataset_definition: DatasetDefinition | None = None,
    logger: logging.Logger | None = None,
) -> ASRBenchmarkResult:
    """Run ASR candidates over the same selected Evaluation Tool records."""

    active_logger = logger or logging.getLogger(__name__)
    benchmark_root = output_root / _safe_name(run_id)
    benchmark_root.mkdir(parents=True, exist_ok=True)
    write_json(
        benchmark_root / "benchmark_manifest.json",
        {
            "run_id": run_id,
            "record_count": len(records),
            "model_ids": [config.model_id for config in model_configs],
        },
    )

    results: list[ASRModelResult] = []
    for config in model_configs:
        model_run_dir = benchmark_root / _safe_name(config.model_id)
        ensure_run_subdirs(model_run_dir)
        snapshot_path = model_run_dir / "asr_config_snapshot.yaml"
        write_yaml(snapshot_path, config.to_jsonable())
        if not config.enabled:
            results.append(
                _skipped_result(
                    config,
                    model_run_dir,
                    snapshot_path,
                    "model disabled in sweep config",
                )
            )
            continue
        missing = _missing_availability(config.availability, project_root=project_root)
        if missing:
            results.append(
                _skipped_result(
                    config,
                    model_run_dir,
                    snapshot_path,
                    "; ".join(missing),
                )
            )
            continue
        try:
            results.append(
                _run_one_model(
                    config=config,
                    model_run_dir=model_run_dir,
                    snapshot_path=snapshot_path,
                    records=records,
                    base_run_config=base_run_config,
                    dataset_definition=dataset_definition,
                    logger=active_logger,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive benchmark boundary
            active_logger.exception("ASR benchmark model failed: %s", config.model_id)
            results.append(
                ASRModelResult(
                    model_id=config.model_id,
                    label=config.label,
                    status="failed",
                    run_dir=model_run_dir,
                    config_snapshot_path=snapshot_path,
                    predictions_path=None,
                    metrics=_empty_metrics(),
                    examples=_empty_examples(),
                    error=str(exc),
                )
            )

    recommended_model_id = _recommended_model(results)
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / f"asr_comparison_{_safe_name(run_id)}.md"
    csv_path = report_dir / f"asr_comparison_{_safe_name(run_id)}.csv"
    _write_csv(csv_path, results, benchmark_root=benchmark_root)
    _write_markdown(
        markdown_path,
        run_id=run_id,
        records=records,
        results=results,
        recommended_model_id=recommended_model_id,
        dataset_name=dataset_definition.display_name if dataset_definition else "not provided",
    )
    return ASRBenchmarkResult(
        run_id=run_id,
        benchmark_root=benchmark_root,
        markdown_report_path=markdown_path,
        csv_report_path=csv_path,
        model_results=tuple(results),
        recommended_model_id=recommended_model_id,
    )


def _run_one_model(
    *,
    config: ASRModelConfig,
    model_run_dir: Path,
    snapshot_path: Path,
    records: Sequence[Mapping[str, object]],
    base_run_config: Mapping[str, object],
    dataset_definition: DatasetDefinition | None,
    logger: logging.Logger,
) -> ASRModelResult:
    asr = _build_asr(config)
    run_config = dict(base_run_config)
    run_config["run_dir"] = str(model_run_dir)
    run_config["asr"] = {
        "benchmark_model_id": config.model_id,
        "component": dict(config.component),
    }
    project_root = _config_path(run_config.get("project_root"))
    write_yaml(
        model_run_dir / "run_config.yaml",
        relative_artifact_config(
            run_config,
            artifact_root=model_run_dir,
            project_root=project_root,
        ),
    )

    pipeline = PipelineRunner.with_dummy_components(asr=asr)
    runner_result = ExternalStubRunner(pipeline).run_batch(
        [dict(record) for record in records],
        model_run_dir / "predictions",
        run_config,
        logger,
    )
    score_result = (
        score_run(model_run_dir, dataset_definition, [dict(record) for record in records], logger)
        if dataset_definition is not None
        else None
    )
    predictions = read_utterance_predictions(runner_result.predictions_path)
    metrics, examples = _summarize_run(
        records=records,
        predictions=predictions,
        runner_result=runner_result,
        asr=asr,
        score_result=score_result,
    )
    status, error = _status_from_runner_result(runner_result)
    write_json(
        model_run_dir / "benchmark_result.json",
        {
            "model_id": config.model_id,
            "label": config.label,
            "status": status,
            "metrics": metrics,
            "examples": examples,
            "error": error,
        },
    )
    return ASRModelResult(
        model_id=config.model_id,
        label=config.label,
        status=status,
        run_dir=model_run_dir,
        config_snapshot_path=snapshot_path,
        predictions_path=runner_result.predictions_path,
        metrics=metrics,
        examples=examples,
        error=error,
    )


def _summarize_run(
    *,
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    runner_result: object,
    asr: ASRBase,
    score_result: ScoreResult | None,
) -> tuple[dict[str, object], dict[str, dict[str, object] | None]]:
    outputs = _outputs_for_records(records, predictions)
    text_metrics = text_quality_metrics(outputs)
    total_duration = total_audio_duration_sec(records)
    runtime_sec = float(getattr(runner_result, "run_duration_sec"))
    realtime_factor = runtime_realtime_factor(runtime_sec, total_duration)
    runtime_stats = getattr(asr, "last_runtime_stats", None)
    empty_count = sum(1 for output in outputs if not output.strip())
    invalid_output_count = _invalid_prediction_count(predictions)
    failure_rate_value = failure_rate(
        attempted_count=int(getattr(runner_result, "attempted_count")),
        failed_count=int(getattr(runner_result, "failed_count")),
        skipped_count=int(getattr(runner_result, "skipped_count")),
        invalid_output_count=invalid_output_count,
        empty_output_count=empty_count,
    )
    wer = aggregate_wer(records, predictions)
    if wer is None and score_result is not None:
        wer = _optional_float(score_result.aggregate_metrics.get("aggregate_wer"))
    cer = aggregate_cer(records, predictions)
    memory_mb = (
        runtime_stats.peak_gpu_memory_mb
        if runtime_stats is not None and runtime_stats.peak_gpu_memory_mb is not None
        else None
    )
    metrics: dict[str, object] = {
        "wer": wer,
        "cer": cer,
        "runtime_sec": runtime_sec,
        "realtime_factor": realtime_factor,
        "throughput_items_per_sec": throughput_items_per_sec(
            int(getattr(runner_result, "written_count")),
            runtime_sec,
        ),
        "load_sec": runtime_stats.load_sec if runtime_stats is not None else None,
        "peak_gpu_memory_mb": runtime_stats.peak_gpu_memory_mb if runtime_stats is not None else None,
        "cpu_memory_mb": runtime_stats.cpu_memory_mb if runtime_stats is not None else None,
        "failure_rate": failure_rate_value,
        "empty_output_rate": text_metrics["empty_output_rate"],
        "repeated_word_rate": text_metrics["repeated_word_rate"],
        "repeated_ngram_rate": text_metrics["repeated_ngram_rate"],
        "consecutive_duplicate_token_rate": text_metrics["consecutive_duplicate_token_rate"],
        "hallucinated_output_rate": text_metrics["hallucinated_output_rate"],
        "composite_score": composite_score(
            wer=wer,
            realtime_factor=realtime_factor,
            failure_rate_value=failure_rate_value,
            memory_mb=memory_mb,
        ),
        "attempted_count": int(getattr(runner_result, "attempted_count")),
        "written_count": int(getattr(runner_result, "written_count")),
        "failed_count": int(getattr(runner_result, "failed_count")),
        "skipped_count": int(getattr(runner_result, "skipped_count")),
        "total_audio_duration_sec": total_duration,
        "condition_metrics": _condition_metrics(records, predictions),
    }
    examples = {
        key: example.to_jsonable() if example is not None else None
        for key, example in select_qualitative_examples(
            prediction_examples(records, predictions)
        ).items()
    }
    return metrics, examples


def _build_asr(config: ASRModelConfig) -> ASRBase:
    name = str(config.component.get("name") or "")
    params = _mapping_or_empty(config.component.get("params"))
    if name == "fixed_asr":
        return FixedASR(str(params.get("transcript", "")))
    if name == "no_op_asr":
        return NoOpASR(str(params.get("transcript", "")))
    asr = build_asr_from_config({"asr": config.component})
    if asr is None:
        raise InferencePipelineError(f"ASR component {name!r} is disabled")
    return asr


def _status_from_runner_result(runner_result: object) -> tuple[str, str | None]:
    attempted = int(getattr(runner_result, "attempted_count"))
    written = int(getattr(runner_result, "written_count"))
    failed = int(getattr(runner_result, "failed_count"))
    skipped = int(getattr(runner_result, "skipped_count"))
    if failed or skipped:
        message = (
            f"inference failed/skipped for {failed + skipped} of {attempted} "
            "record(s); see benchmark log"
        )
        return ("failed" if written == 0 else "ran_with_failures", message)
    return "ran", None


def _component_from_entry(
    mapping: Mapping[str, object],
    *,
    sweep_path: Path | None,
    tool_root: Path | None,
) -> Mapping[str, object]:
    component = mapping.get("component")
    if isinstance(component, Mapping):
        return _unwrap_component(component)
    component_path = mapping.get("component_path")
    if component_path is not None:
        path = _resolve_reference_path(
            str(component_path),
            sweep_path=sweep_path,
            tool_root=tool_root,
        )
        return _unwrap_component(read_yaml(path))
    raise ValueError("ASR benchmark model entry requires component or component_path")


def _unwrap_component(mapping: Mapping[str, object]) -> Mapping[str, object]:
    component = mapping.get("component")
    if isinstance(component, Mapping):
        return component
    return mapping


def _resolve_reference_path(
    value: str,
    *,
    sweep_path: Path | None,
    tool_root: Path | None,
) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidates: list[Path] = []
    if sweep_path is not None:
        candidates.append(sweep_path.parent / path)
    if tool_root is not None:
        candidates.append(tool_root / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1] if candidates else path


def _missing_availability(
    availability: Mapping[str, object],
    *,
    project_root: Path,
) -> list[str]:
    missing: list[str] = []
    package = availability.get("requires_package")
    if package is not None and importlib.util.find_spec(str(package)) is None:
        missing.append(f"missing python package {package!r}")
    file_value = availability.get("requires_file")
    if file_value is not None:
        path = Path(str(file_value))
        candidate = path if path.is_absolute() else project_root / "Evaluation Tool" / path
        if not candidate.exists():
            missing.append(f"missing local file {candidate}")
    whisper_model = availability.get("requires_whisper_model")
    if whisper_model is not None and not _whisper_model_available(
        str(whisper_model),
        availability=availability,
        project_root=project_root,
    ):
        missing.append(f"missing local Whisper model asset {whisper_model!r}")
    return missing


def _skipped_result(
    config: ASRModelConfig,
    model_run_dir: Path,
    snapshot_path: Path,
    reason: str,
) -> ASRModelResult:
    return ASRModelResult(
        model_id=config.model_id,
        label=config.label,
        status="skipped",
        run_dir=model_run_dir,
        config_snapshot_path=snapshot_path,
        predictions_path=None,
        metrics=_empty_metrics(),
        examples=_empty_examples(),
        skip_reason=reason,
    )


def _empty_metrics() -> dict[str, object]:
    return {key: None for key in CSV_METRIC_FIELDS}


def _empty_examples() -> dict[str, dict[str, object] | None]:
    return {
        "best": None,
        "median": None,
        "worst": None,
        "high_stutter": None,
        "empty_output": None,
        "hallucination": None,
    }


def _invalid_prediction_count(predictions: Sequence[Mapping[str, object]]) -> int:
    required = {"recording_id", "utt_id", "start_sec", "end_sec", "speaker_label", "text"}
    return sum(1 for prediction in predictions if not required.issubset(prediction))


def _outputs_for_records(
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
) -> list[str]:
    predictions_by_key = {
        (
            str(prediction.get("recording_id")),
            str(prediction.get("utt_id") or prediction.get("recording_id")),
        ): prediction
        for prediction in predictions
    }
    outputs: list[str] = []
    for record in records:
        key = (
            str(record.get("recording_id")),
            str(record.get("utt_id") or record.get("recording_id")),
        )
        outputs.append(str(predictions_by_key.get(key, {}).get("text") or ""))
    return outputs


def _condition_metrics(
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for record in records:
        condition = str(record.get("augmentation_condition_id") or "clean")
        grouped.setdefault(condition, []).append(record)
    return {
        condition: {
            "record_count": len(group_records),
            "wer": aggregate_wer(group_records, predictions),
            "cer": aggregate_cer(group_records, predictions),
        }
        for condition, group_records in sorted(grouped.items())
    }


def _recommended_model(results: Sequence[ASRModelResult]) -> str | None:
    runnable = [result for result in results if result.status == "ran"]
    if not runnable:
        return None
    return max(
        runnable,
        key=lambda result: (
            _optional_float(result.metrics.get("composite_score")) or 0.0,
            result.model_id,
        ),
    ).model_id


def _write_csv(
    path: Path,
    results: Sequence[ASRModelResult],
    *,
    benchmark_root: Path,
) -> None:
    rows = [result.to_csv_row(benchmark_root=benchmark_root) for result in results]
    columns = [
        "model_id",
        "label",
        "status",
        "skip_reason",
        "error",
        "run_dir",
        "predictions_path",
        *CSV_METRIC_FIELDS,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _artifact_path(path: Path, root: Path | None) -> str:
    if root is None:
        return path.as_posix()
    return safe_relative_to(path, root)


def _config_path(value: object) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value))


def _write_markdown(
    path: Path,
    *,
    run_id: str,
    records: Sequence[Mapping[str, object]],
    results: Sequence[ASRModelResult],
    recommended_model_id: str | None,
    dataset_name: str,
) -> None:
    lines = [
        "# ASR Multi-Model Benchmark Comparison",
        "",
        "## Milestone",
        "",
        "M8 - ASR Multi-Model Benchmark and Comparison Report",
        "",
        f"- Run id: `{run_id}`",
        f"- Dataset: `{dataset_name}`",
        f"- Record count: `{len(records)}`",
        f"- Recommended default ASR: `{recommended_model_id or 'n/a'}`",
        "",
        "## Compared Models",
        "",
        "| Model | Status | WER | CER | RTF | Throughput | Failure Rate | Empty Rate | Composite |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            "| "
            f"`{result.model_id}` | "
            f"{result.status}{_reason_suffix(result)} | "
            f"{_fmt(result.metrics.get('wer'))} | "
            f"{_fmt(result.metrics.get('cer'))} | "
            f"{_fmt(result.metrics.get('realtime_factor'))} | "
            f"{_fmt(result.metrics.get('throughput_items_per_sec'))} | "
            f"{_fmt(result.metrics.get('failure_rate'))} | "
            f"{_fmt(result.metrics.get('empty_output_rate'))} | "
            f"{_fmt(result.metrics.get('composite_score'))} |"
        )
    lines.extend(
        [
            "",
            "## Runtime And Robustness",
            "",
            "| Model | Load Sec | Runtime Sec | Peak GPU MB | CPU MB | Repeated Word | Repeated N-Gram | Duplicate Token | Hallucination |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for result in results:
        lines.append(
            "| "
            f"`{result.model_id}` | "
            f"{_fmt(result.metrics.get('load_sec'))} | "
            f"{_fmt(result.metrics.get('runtime_sec'))} | "
            f"{_fmt(result.metrics.get('peak_gpu_memory_mb'))} | "
            f"{_fmt(result.metrics.get('cpu_memory_mb'))} | "
            f"{_fmt(result.metrics.get('repeated_word_rate'))} | "
            f"{_fmt(result.metrics.get('repeated_ngram_rate'))} | "
            f"{_fmt(result.metrics.get('consecutive_duplicate_token_rate'))} | "
            f"{_fmt(result.metrics.get('hallucinated_output_rate'))} |"
        )
    lines.extend(["", "## Qualitative Examples", ""])
    for result in results:
        lines.extend([f"### `{result.model_id}`", ""])
        if result.status != "ran":
            lines.extend([result.skip_reason or result.error or "not run", ""])
            continue
        for label, example in result.examples.items():
            lines.append(f"- {label}: {_example_text(example)}")
        lines.append("")
    lines.extend(["## Metrics By Augmentation Condition", ""])
    for result in results:
        lines.extend([f"### `{result.model_id}`", ""])
        condition_metrics = result.metrics.get("condition_metrics")
        if not isinstance(condition_metrics, Mapping) or not condition_metrics:
            lines.extend(["- `n/a`", ""])
            continue
        for condition, metrics in condition_metrics.items():
            if not isinstance(metrics, Mapping):
                continue
            lines.append(
                f"- `{condition}`: WER `{_fmt(metrics.get('wer'))}`, "
                f"CER `{_fmt(metrics.get('cer'))}`, records `{metrics.get('record_count')}`"
            )
        lines.append("")
    lines.extend(
        [
            "## Blockers",
            "",
        ]
    )
    blockers = [
        f"`{result.model_id}`: {result.skip_reason or result.error}"
        for result in results
        if result.status != "ran"
    ]
    lines.extend(f"- {blocker}" for blocker in blockers) if blockers else lines.append("- None.")
    lines.extend(
        [
            "",
            "## Incomplete",
            "",
            "- Speaker diarization, speaker embeddings, speaker matching, optimization, quantization, ExecuTorch export, and hardware acceleration remain out of scope for M8.",
            "- CER is computed by benchmark helper logic; WER is taken from existing scorer output when dataset references are available.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _reason_suffix(result: ASRModelResult) -> str:
    reason = result.skip_reason or result.error
    return f" ({reason})" if reason else ""


def _example_text(example: Mapping[str, object] | None) -> str:
    if example is None:
        return "`n/a`"
    reference = str(example.get("reference_text") or "")
    hypothesis = str(example.get("hypothesis_text") or "")
    wer = _fmt(example.get("wer"))
    return (
        f"`{example.get('recording_id')}/{example.get('utt_id')}` "
        f"WER `{wer}` ref=`{reference[:80]}` hyp=`{hypothesis[:80]}`"
    )


def _fmt(value: object) -> str:
    number = _optional_float(value)
    if number is None:
        return "n/a"
    return f"{number:.4f}"


def _mapping_value(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _mapping_or_empty(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._-")[:100] or "asr"


def _whisper_model_available(
    model_size: str,
    *,
    availability: Mapping[str, object],
    project_root: Path,
) -> bool:
    cache_dir = availability.get("whisper_cache_dir") or "models/cache/whisper"
    cache_path = Path(str(cache_dir))
    candidates = [
        cache_path if cache_path.is_absolute() else project_root / "Evaluation Tool" / cache_path,
        cache_path if cache_path.is_absolute() else project_root / cache_path,
        cache_path if cache_path.is_absolute() else project_root.parent / cache_path,
        Path.home() / ".cache" / "whisper",
    ]
    expected = f"{model_size}.pt"
    return any((candidate / expected).is_file() for candidate in candidates)


def _default_tool_root(path: Path) -> Path:
    for parent in path.parents:
        if parent.name == "Evaluation Tool":
            return parent
    return path.parents[2] if len(path.parents) > 2 else path.parent
