"""Run a resumable Cartesian sweep over realtime inference components."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import subprocess
import sys
import time
import wave
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import yaml


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.config import PipelineConfig


@dataclass(frozen=True)
class SweepCase:
    case_id: str
    input_id: str
    input_path: Path
    recording_id: str
    duration_sec: float
    model: Mapping[str, object]
    device: Mapping[str, object]
    window: Mapping[str, object]
    vad: Mapping[str, object]
    threshold: float
    scoring_mode: str
    word_timestamps: bool
    beam_size: int
    queue: Mapping[str, object]

    def manifest_row(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "input_id": self.input_id,
            "input_path": str(self.input_path),
            "recording_id": self.recording_id,
            "duration_sec": self.duration_sec,
            "model_id": self.model["id"],
            "model_size": self.model["model_size"],
            "device_id": self.device["id"],
            "device": self.device["device"],
            "dtype": self.device["dtype"],
            "window_id": self.window["id"],
            "window_sec": self.window["window_sec"],
            "hop_sec": self.window["hop_sec"],
            "stitch_transcript": bool(self.window.get("stitch_transcript", False)),
            "vad_id": self.vad["id"],
            "speaker_threshold": self.threshold,
            "scoring_mode": self.scoring_mode,
            "word_timestamps": self.word_timestamps,
            "beam_size": self.beam_size,
            "queue_id": self.queue["id"],
            "max_queue": self.queue["max_queue"],
            "drop_policy": self.queue["drop_policy"],
        }


def load_sweep(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, Mapping):
        raise ValueError("sweep config must contain a YAML mapping")
    return dict(value)


def build_cases(
    sweep: Mapping[str, object],
    *,
    all_models: bool = False,
    model_filter: set[str] | None = None,
    device_filter: set[str] | None = None,
    input_overrides: Sequence[Path] = (),
    duration_override: float | None = None,
) -> list[SweepCase]:
    inputs = _input_entries(sweep, input_overrides, duration_override)
    models = _enabled_entries(
        sweep,
        "models",
        include_disabled=all_models or bool(model_filter),
    )
    devices = _enabled_entries(sweep, "devices", include_disabled=bool(device_filter))
    windows = _enabled_entries(sweep, "window_profiles")
    vads = _enabled_entries(sweep, "vad_profiles")
    queues = _enabled_entries(sweep, "queue_profiles")
    if model_filter:
        models = [item for item in models if str(item.get("id")) in model_filter]
    if device_filter:
        devices = [item for item in devices if str(item.get("id")) in device_filter]

    thresholds = [float(value) for value in _sequence(sweep, "speaker_thresholds")]
    scoring_modes = [str(value) for value in _sequence(sweep, "scoring_modes")]
    word_timestamps = [bool(value) for value in _sequence(sweep, "word_timestamps")]
    beam_sizes = [int(value) for value in _sequence(sweep, "beam_sizes")]
    dimensions = (
        inputs,
        models,
        devices,
        windows,
        vads,
        thresholds,
        scoring_modes,
        word_timestamps,
        beam_sizes,
        queues,
    )
    if any(not values for values in dimensions):
        raise ValueError("every enabled sweep dimension must contain at least one value")

    cases: list[SweepCase] = []
    for index, values in enumerate(itertools.product(*dimensions), start=1):
        input_item, model, device, window, vad, threshold, scoring, words, beam, queue = values
        parts = [
            str(input_item["id"]),
            str(model["id"]),
            str(device["id"]),
            str(window["id"]),
            str(vad["id"]),
            f"t{float(threshold):.2f}",
            str(scoring),
            "words" if words else "no_words",
            f"beam{beam}",
            str(queue["id"]),
        ]
        case_id = f"{index:04d}_" + "_".join(_slug(part) for part in parts)
        cases.append(
            SweepCase(
                case_id=case_id,
                input_id=str(input_item["id"]),
                input_path=Path(str(input_item["path"])),
                recording_id=str(input_item["recording_id"]),
                duration_sec=float(input_item["duration_sec"]),
                model=model,
                device=device,
                window=window,
                vad=vad,
                threshold=float(threshold),
                scoring_mode=str(scoring),
                word_timestamps=bool(words),
                beam_size=int(beam),
                queue=queue,
            )
        )
    return cases


def build_case_config(
    base_config: PipelineConfig,
    case: SweepCase,
    *,
    allow_model_downloads: bool,
) -> dict[str, object]:
    config = deepcopy(base_config.to_jsonable())
    config["config_name"] = f"realtime_sweep_{case.case_id}"
    config["profile"] = "realtime_component_sweep"
    runtime = _mapping(config, "runtime")
    runtime["device"] = str(case.device["device"])
    runtime["precision"] = str(case.device["dtype"])
    runtime["dry_run"] = False
    runtime["allow_model_downloads"] = allow_model_downloads

    components = _mapping(config, "components")
    components["asr"] = {
        "name": str(case.model["component_name"]),
        "enabled": True,
        "adapter": str(case.model["adapter"]),
        "params": {
            "model_family": "whisper",
            "model_size": str(case.model["model_size"]),
            "model_name": str(case.model["component_name"]),
            "language": case.model.get("language", "en"),
            "beam_size": case.beam_size,
            "word_timestamps": case.word_timestamps,
            "device": str(case.device["device"]),
            "dtype": str(case.device["dtype"]),
            "allow_model_downloads": allow_model_downloads,
            "cache_dir": str(case.model.get("cache_dir", "models/cache/whisper")),
        },
    }
    components["vad"], components["segmentation"] = _vad_components(case.vad)

    embedding = _mapping(components, "speaker_embedding")
    embedding_params = _mapping(embedding, "params")
    embedding_params["device"] = str(case.device["device"])
    embedding_params["allow_model_downloads"] = allow_model_downloads

    matcher = _mapping(components, "speaker_matching")
    matcher_params = _mapping(matcher, "params")
    matcher_params["threshold"] = case.threshold
    matcher_params["scoring_mode"] = case.scoring_mode
    return config


def run_case(
    case: SweepCase,
    *,
    sweep_root: Path,
    base_config: PipelineConfig,
    allow_model_downloads: bool,
    timeout_sec: float | None,
    keep_audio: bool,
) -> dict[str, object]:
    generated_dir = sweep_root / "generated_configs"
    logs_dir = sweep_root / "logs"
    runs_dir = sweep_root / "runs"
    generated_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)
    config_path = generated_dir / f"{case.case_id}.yaml"
    with config_path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(
            build_case_config(
                base_config,
                case,
                allow_model_downloads=allow_model_downloads,
            ),
            handle,
            sort_keys=False,
        )

    command = [
        sys.executable,
        str(TOOL_ROOT / "scripts" / "live_mic_realtime.py"),
        "--config",
        str(config_path),
        "--run-id",
        case.case_id,
        "--input-wav",
        str(case.input_path),
        "--duration-sec",
        str(case.duration_sec),
        "--window-sec",
        str(case.window["window_sec"]),
        "--hop-sec",
        str(case.window["hop_sec"]),
        "--sample-rate",
        "16000",
        "--recording-id",
        case.recording_id,
        "--max-queue",
        str(case.queue["max_queue"]),
        "--drop-policy",
        str(case.queue["drop_policy"]),
        "--output-dir",
        str(runs_dir),
        "--verbose",
    ]
    if bool(case.window.get("stitch_transcript", False)):
        command.extend(
            [
                "--stitch-transcript",
                "--stability-delay-sec",
                str(case.window.get("stability_delay_sec", 1.0)),
            ]
        )
    if keep_audio:
        command.append("--keep-audio")

    started_at = time.perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=TOOL_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
        return_code = completed.returncode
        output = completed.stdout
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        return_code = -1
        output = _timeout_output(exc)
    elapsed_sec = time.perf_counter() - started_at
    log_path = logs_dir / f"{case.case_id}.log"
    log_path.write_text(output, encoding="utf-8")
    summary_path = runs_dir / case.case_id / "summary.json"
    summary = _read_json(summary_path)
    status = (
        "timeout"
        if timed_out
        else "succeeded"
        if return_code == 0 and summary is not None
        else "failed"
    )
    result = {
        **case.manifest_row(),
        "status": status,
        "return_code": return_code,
        "wall_time_sec": round(elapsed_sec, 6),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "summary_path": str(summary_path),
        "log_path": str(log_path),
        "command": command,
        **summarize_run(summary),
    }
    if result["status"] != "succeeded" and not result.get("error"):
        result["error"] = _last_nonempty_line(output) or "run summary was not created"
    return result


def summarize_run(summary: Mapping[str, object] | None) -> dict[str, object]:
    if summary is None:
        return {
            "prediction_count": None,
            "dropped_window_count": None,
            "latency_mean_sec": None,
            "latency_max_sec": None,
            "asr_rtf_mean": None,
            "asr_rtf_max": None,
            "pipeline_runtime_mean_sec": None,
            "asr_stage_mean_sec": None,
            "speaker_stage_mean_sec": None,
            "speaker_accepted_count": None,
            "speaker_unknown_count": None,
            "speaker_score_mean": None,
            "error": None,
        }
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), Mapping) else {}
    latency = (
        metrics.get("latency_sec")
        if isinstance(metrics.get("latency_sec"), Mapping)
        else {}
    )
    asr_rtf = (
        metrics.get("asr_realtime_factor")
        if isinstance(metrics.get("asr_realtime_factor"), Mapping)
        else {}
    )
    diagnostics = summary.get("diagnostics_rows")
    rows = diagnostics if isinstance(diagnostics, list) else []
    pipeline_times: list[float] = []
    asr_times: list[float] = []
    speaker_times: list[float] = []
    scores: list[float] = []
    accepted = 0
    unknown = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        details = (
            row.get("diagnostics")
            if isinstance(row.get("diagnostics"), Mapping)
            else {}
        )
        runtime = (
            details.get("runtime_stats")
            if isinstance(details.get("runtime_stats"), Mapping)
            else {}
        )
        _append_number(pipeline_times, runtime.get("total_sec"))
        stages = (
            runtime.get("stage_breakdown_sec")
            if isinstance(runtime.get("stage_breakdown_sec"), Mapping)
            else {}
        )
        _append_number(asr_times, stages.get("asr_sec"))
        _append_number(speaker_times, stages.get("speaker_sec"))
        decisions = (
            details.get("speaker_decisions")
            if isinstance(details.get("speaker_decisions"), list)
            else []
        )
        for decision in decisions:
            if not isinstance(decision, Mapping):
                continue
            _append_number(scores, decision.get("confidence"))
            if bool(decision.get("accepted")):
                accepted += 1
            else:
                unknown += 1
    worker_errors = summary.get("worker_errors")
    errors = worker_errors if isinstance(worker_errors, list) else []
    return {
        "prediction_count": summary.get("prediction_count"),
        "dropped_window_count": summary.get("dropped_window_count"),
        "latency_mean_sec": latency.get("mean"),
        "latency_max_sec": latency.get("max"),
        "asr_rtf_mean": asr_rtf.get("mean"),
        "asr_rtf_max": asr_rtf.get("max"),
        "pipeline_runtime_mean_sec": _mean(pipeline_times),
        "asr_stage_mean_sec": _mean(asr_times),
        "speaker_stage_mean_sec": _mean(speaker_times),
        "speaker_accepted_count": accepted,
        "speaker_unknown_count": unknown,
        "speaker_score_mean": _mean(scores),
        "error": "; ".join(str(value) for value in errors) or None,
    }


def write_manifest(path: Path, cases: Sequence[SweepCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump([case.manifest_row() for case in cases], handle, indent=2)


def append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, Mapping):
            rows.append(dict(value))
    return rows


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        return
    excluded = {"command"}
    fields = list(dict.fromkeys(key for row in rows for key in row if key not in excluded))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a resumable realtime component sweep.")
    parser.add_argument(
        "--sweep-config",
        type=Path,
        default=Path("configs/sweeps/realtime_component_matrix.yaml"),
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("runs/realtime_component_sweeps"),
    )
    parser.add_argument("--input-wav", type=Path, action="append", default=[])
    parser.add_argument("--duration-sec", type=float, default=None)
    parser.add_argument("--models", default=None, help="Comma-separated model ids to include.")
    parser.add_argument("--devices", default=None, help="Comma-separated device profile ids.")
    parser.add_argument(
        "--all-models",
        action="store_true",
        help="Include models disabled in the matrix.",
    )
    parser.add_argument("--allow-model-downloads", action="store_true")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--timeout-sec", type=float, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the manifest without executing cases.",
    )
    parser.add_argument("--keep-audio", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sweep_path = _tool_path(args.sweep_config)
    sweep = load_sweep(sweep_path)
    run_id = args.run_id or f"{sweep.get('sweep_name', 'realtime_components')}_{int(time.time())}"
    sweep_root = _tool_path(args.output_root) / _slug(run_id)
    sweep_root.mkdir(parents=True, exist_ok=True)
    cases = build_cases(
        sweep,
        all_models=args.all_models,
        model_filter=_csv_set(args.models),
        device_filter=_csv_set(args.devices),
        input_overrides=tuple(_tool_path(path) for path in args.input_wav),
        duration_override=args.duration_sec,
    )
    if args.max_cases is not None:
        if args.max_cases < 1:
            raise ValueError("--max-cases must be >= 1")
        cases = cases[: args.max_cases]
    write_manifest(sweep_root / "manifest.json", cases)
    print(f"Sweep cases: {len(cases)}")
    print(f"Sweep output: {sweep_root}")
    if args.dry_run:
        print(f"Manifest: {sweep_root / 'manifest.json'}")
        return 0

    base_path = _tool_path(Path(str(sweep.get("base_config"))))
    base_config = PipelineConfig.from_yaml_path(base_path)
    results_path = sweep_root / "results.jsonl"
    existing = load_jsonl(results_path) if args.resume else []
    completed_ids = {str(row.get("case_id")) for row in existing}
    for position, case in enumerate(cases, start=1):
        if case.case_id in completed_ids:
            print(f"[{position}/{len(cases)}] skip {case.case_id}")
            continue
        print(f"[{position}/{len(cases)}] run  {case.case_id}")
        result = run_case(
            case,
            sweep_root=sweep_root,
            base_config=base_config,
            allow_model_downloads=args.allow_model_downloads,
            timeout_sec=args.timeout_sec,
            keep_audio=args.keep_audio,
        )
        append_jsonl(results_path, result)
        print(f"  {result['status']} in {result['wall_time_sec']} sec")

    rows = load_jsonl(results_path)
    write_csv(sweep_root / "results.csv", rows)
    succeeded = sum(row.get("status") == "succeeded" for row in rows)
    failed = len(rows) - succeeded
    print(f"Results: {sweep_root / 'results.csv'}")
    print(f"Completed: {len(rows)}; succeeded: {succeeded}; failed: {failed}")
    return 0 if failed == 0 else 1


def _input_entries(
    sweep: Mapping[str, object],
    overrides: Sequence[Path],
    duration_override: float | None,
) -> list[dict[str, object]]:
    if overrides:
        raw = [
            {
                "id": path.stem,
                "path": str(path),
                "recording_id": path.stem,
                "duration_sec": duration_override,
            }
            for path in overrides
        ]
    else:
        raw = _enabled_entries(sweep, "inputs")
    results: list[dict[str, object]] = []
    for item in raw:
        path = _tool_path(Path(str(item["path"])))
        duration = (
            duration_override
            or _optional_float(item.get("duration_sec"))
            or _wav_duration(path)
        )
        results.append(
            {
                **item,
                "id": str(item.get("id") or path.stem),
                "path": str(path),
                "recording_id": str(item.get("recording_id") or path.stem),
                "duration_sec": duration,
            }
        )
    return results


def _enabled_entries(
    mapping: Mapping[str, object],
    key: str,
    *,
    include_disabled: bool = False,
) -> list[dict[str, object]]:
    values = _sequence(mapping, key)
    entries = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError(f"{key} entries must be mappings")
        if include_disabled or bool(value.get("enabled", True)):
            entries.append(dict(value))
    return entries


def _sequence(mapping: Mapping[str, object], key: str) -> list[object]:
    value = mapping.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError(f"{key} must be a list")
    return list(value)


def _vad_components(vad: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    kind = str(vad.get("kind") or vad.get("id"))
    if kind == "none":
        return (
            {"name": "no_op_vad", "enabled": False, "adapter": "NoOpVADAdapter", "params": {}},
            {
                "name": "no_op_segmentation",
                "enabled": False,
                "adapter": "NoOpSegmentationAdapter",
                "params": {"mode": "full_window"},
            },
        )
    if kind not in {"energy", "silero"}:
        raise ValueError(f"unsupported VAD profile kind: {kind}")
    vad_name = "energy_vad" if kind == "energy" else "silero_vad"
    vad_adapter = "EnergyVADAdapter" if kind == "energy" else "SileroVADAdapter"
    return (
        {
            "name": vad_name,
            "enabled": True,
            "adapter": vad_adapter,
            "params": dict(vad.get("params") or {}),
        },
        {
            "name": "vad_chunks",
            "enabled": True,
            "adapter": "VADChunkerAdapter",
            "params": dict(vad.get("segmentation_params") or {}),
        },
    )


def _mapping(mapping: Mapping[str, object], key: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mutable mapping")
    return value


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return dict(value) if isinstance(value, Mapping) else None


def _append_number(values: list[float], value: object) -> None:
    number = _optional_float(value)
    if number is not None:
        values.append(number)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def _tool_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (TOOL_ROOT / path).resolve()


def _csv_set(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


def _slug(value: object) -> str:
    text = "".join(character.lower() if character.isalnum() else "_" for character in str(value))
    return "_".join(part for part in text.split("_") if part) or "case"


def _csv_value(value: object) -> object:
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return value


def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
    output = exc.stdout or ""
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    return f"{output}\nTimed out after {exc.timeout} seconds."


def _last_nonempty_line(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else None


if __name__ == "__main__":
    raise SystemExit(main())
