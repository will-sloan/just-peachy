"""Capture short microphone chunks and run them through PipelineRunner."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
import re
import sys
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence, TextIO


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
DEFAULT_CONFIG_PATH = TOOL_ROOT / "configs" / "inference" / "live_mic_whisper_tiny.yaml"
DEFAULT_OUTPUT_ROOT = TOOL_ROOT / "runs" / "live_mic"
DEFAULT_REPORT_DIR = TOOL_ROOT / "reports" / "component_reports" / "live_mic"
REQUIRED_PREDICTION_FIELDS = (
    "recording_id",
    "utt_id",
    "start_sec",
    "end_sec",
    "speaker_label",
    "text",
)

if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.asr.base import NoOpASR  # noqa: E402
from app.inference_pipeline.config import PipelineConfig  # noqa: E402
from app.inference_pipeline.pipeline import AudioLoaderAdapter, PipelineRunner  # noqa: E402
from app.utils.json_utils import write_json  # noqa: E402


class LiveMicSmokeError(RuntimeError):
    """Raised when live microphone smoke validation cannot continue."""


class MicrophoneUnavailableError(LiveMicSmokeError):
    """Raised when optional microphone capture support is unavailable."""


class ChunkCapture(Protocol):
    """Protocol for a microphone or synthetic chunk capture implementation."""

    def capture_chunk(self, output_path: Path, duration_sec: float, sample_rate: int) -> Path:
        """Write one WAV chunk and return its path."""


@dataclass(frozen=True)
class LiveMicSmokeResult:
    """Summary of one live microphone smoke run."""

    run_id: str
    run_dir: Path
    predictions_path: Path
    diagnostics_path: Path
    summary_path: Path
    component_report_path: Path | None
    dry_run: bool
    asr_mode: str
    microphone_capture_tested: bool
    audio_retained: bool
    chunk_count: int
    prediction_count: int
    config_path: Path
    availability: dict[str, object]

    def to_jsonable(self) -> dict[str, object]:
        """Return a JSON-safe run summary."""

        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "predictions_path": str(self.predictions_path),
            "diagnostics_path": str(self.diagnostics_path),
            "summary_path": str(self.summary_path),
            "component_report_path": (
                str(self.component_report_path) if self.component_report_path is not None else None
            ),
            "dry_run": self.dry_run,
            "asr_mode": self.asr_mode,
            "microphone_capture_tested": self.microphone_capture_tested,
            "audio_retained": self.audio_retained,
            "chunk_count": self.chunk_count,
            "prediction_count": self.prediction_count,
            "config_path": str(self.config_path),
            "availability": self.availability,
        }


class SoundDeviceMicrophoneCapture:
    """Lazy sounddevice-backed microphone capture."""

    def __init__(
        self,
        *,
        channels: int = 1,
        dtype: str = "float32",
        module_importer: Callable[[str], Any] | None = None,
    ) -> None:
        self.channels = channels
        self.dtype = dtype
        self._module_importer = module_importer or importlib.import_module

    def capture_chunk(self, output_path: Path, duration_sec: float, sample_rate: int) -> Path:
        sd = self._import_sounddevice()
        sf = self._import_soundfile()
        frames = max(1, int(round(duration_sec * sample_rate)))
        try:
            audio = sd.rec(
                frames,
                samplerate=sample_rate,
                channels=self.channels,
                dtype=self.dtype,
            )
            sd.wait()
        except Exception as exc:  # pragma: no cover - hardware boundary
            raise MicrophoneUnavailableError(
                "Microphone capture failed. Check OS microphone permission, the selected "
                f"input device, and sample rate {sample_rate}: {exc}"
            ) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            sf.write(output_path, audio, sample_rate, subtype="PCM_16")
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise MicrophoneUnavailableError(f"Failed to write microphone WAV chunk: {exc}") from exc
        return output_path

    def _import_sounddevice(self) -> Any:
        try:
            return self._module_importer("sounddevice")
        except ModuleNotFoundError as exc:
            raise MicrophoneUnavailableError(
                "Missing optional microphone dependency 'sounddevice'. Install it in the "
                "repository .venv for real microphone capture, or rerun with --dry-run."
            ) from exc

    def _import_soundfile(self) -> Any:
        try:
            return self._module_importer("soundfile")
        except ModuleNotFoundError as exc:
            raise MicrophoneUnavailableError(
                "Missing audio writer dependency 'soundfile'; cannot write microphone WAV chunks."
            ) from exc


class DryRunWavCapture:
    """Synthetic WAV capture used by --dry-run."""

    def capture_chunk(self, output_path: Path, duration_sec: float, sample_rate: int) -> Path:
        write_silence_wav(output_path, duration_sec=duration_sec, sample_rate=sample_rate)
        return output_path


def run_live_mic_smoke(
    *,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    run_id: str | None = None,
    duration_sec: float = 10.0,
    chunk_sec: float = 3.0,
    sample_rate: int = 16000,
    speaker_label: str | None = None,
    recording_id: str = "live_mic",
    output_dir: Path | str | None = None,
    keep_audio: bool = False,
    dry_run: bool = False,
    capture: ChunkCapture | None = None,
    pipeline_runner: Any | None = None,
    report_dir: Path | str | None = None,
    write_report: bool = True,
    stdout: TextIO | None = None,
    command: Sequence[str] = (),
) -> LiveMicSmokeResult:
    """Run a file-backed microphone smoke test through PipelineRunner."""

    _validate_smoke_args(duration_sec, chunk_sec, sample_rate, recording_id)
    output = stdout or sys.stdout
    resolved_config_path = resolve_config_path(config_path)
    config = PipelineConfig.from_yaml_path(resolved_config_path)
    availability = inspect_runtime_availability(config, config_path=resolved_config_path)

    selected_run_id = _safe_run_id(run_id or _default_run_id())
    output_root = resolve_output_root(output_dir)
    run_dir = output_root / selected_run_id
    audio_dir = run_dir / "audio"
    predictions_dir = run_dir / "predictions"
    predictions_path = predictions_dir / "utterances.jsonl"
    diagnostics_path = predictions_dir / "diagnostics.jsonl"
    summary_path = run_dir / "summary.json"

    predictions_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    predictions_path.write_text("", encoding="utf-8")
    diagnostics_path.write_text("", encoding="utf-8")

    pipeline, asr_mode = _select_pipeline(
        config,
        availability,
        dry_run=dry_run,
        pipeline_runner=pipeline_runner,
    )
    selected_capture = capture or (DryRunWavCapture() if dry_run else SoundDeviceMicrophoneCapture())

    chunk_durations = _chunk_durations(duration_sec, chunk_sec)
    prediction_rows: list[dict[str, object]] = []
    diagnostics_rows: list[dict[str, object]] = []
    captured_audio_paths: list[Path] = []
    run_config = _run_config(
        config=config,
        config_path=resolved_config_path,
        run_id=selected_run_id,
        run_dir=run_dir,
        duration_sec=duration_sec,
        chunk_sec=chunk_sec,
        sample_rate=sample_rate,
        speaker_label=speaker_label,
        recording_id=recording_id,
        dry_run=dry_run,
        command=command,
        availability=availability,
    )

    timeline_start = 0.0
    for chunk_index, current_chunk_sec in enumerate(chunk_durations, start=1):
        audio_path = audio_dir / f"chunk_{chunk_index:04d}.wav"
        captured_path = selected_capture.capture_chunk(
            audio_path,
            duration_sec=current_chunk_sec,
            sample_rate=sample_rate,
        )
        captured_audio_paths.append(captured_path)
        record = build_synthetic_record(
            recording_id=recording_id,
            chunk_index=chunk_index,
            audio_path=captured_path,
            chunk_duration_sec=current_chunk_sec,
            sample_rate=sample_rate,
            speaker_label=speaker_label,
            chunk_start_sec=timeline_start,
        )
        try:
            pipeline_output = pipeline.predict(record, run_config)
        except Exception as exc:
            _append_jsonl(
                diagnostics_path,
                _failed_diagnostics_row(
                    record,
                    chunk_index=chunk_index,
                    dry_run=dry_run,
                    error=exc,
                ),
            )
            raise LiveMicSmokeError(
                f"Pipeline prediction failed for chunk {chunk_index:04d}: {exc}"
            ) from exc

        prediction_row = _prediction_row(pipeline_output, record=record)
        diagnostics_row = _diagnostics_row(
            pipeline_output,
            pipeline,
            record,
            chunk_index=chunk_index,
            dry_run=dry_run,
        )
        prediction_rows.append(prediction_row)
        diagnostics_rows.append(diagnostics_row)
        _append_jsonl(predictions_path, prediction_row)
        _append_jsonl(diagnostics_path, diagnostics_row)
        _print_transcript_line(
            output,
            run_id=selected_run_id,
            chunk_index=chunk_index,
            chunk_count=len(chunk_durations),
            prediction_row=prediction_row,
            dry_run=dry_run,
        )
        timeline_start += current_chunk_sec

    if not keep_audio:
        _remove_audio_files(captured_audio_paths, audio_dir)

    component_report_path = (
        resolve_report_dir(report_dir) / f"live_mic_smoke_{selected_run_id}.md"
        if write_report
        else None
    )
    result = LiveMicSmokeResult(
        run_id=selected_run_id,
        run_dir=run_dir,
        predictions_path=predictions_path,
        diagnostics_path=diagnostics_path,
        summary_path=summary_path,
        component_report_path=component_report_path,
        dry_run=dry_run,
        asr_mode=asr_mode,
        microphone_capture_tested=not dry_run,
        audio_retained=keep_audio,
        chunk_count=len(chunk_durations),
        prediction_count=len(prediction_rows),
        config_path=resolved_config_path,
        availability=availability,
    )
    summary = {
        **result.to_jsonable(),
        "recording_id": recording_id,
        "speaker_label": speaker_label,
        "duration_sec": duration_sec,
        "chunk_sec": chunk_sec,
        "sample_rate": sample_rate,
        "prediction_required_fields": list(REQUIRED_PREDICTION_FIELDS),
        "prediction_rows": prediction_rows,
        "diagnostics_rows": diagnostics_rows,
    }
    write_json(summary_path, summary)
    if component_report_path is not None:
        write_component_report(
            result,
            speaker_label=speaker_label,
            command=command,
            duration_sec=duration_sec,
            chunk_sec=chunk_sec,
            sample_rate=sample_rate,
        )
    return result


def build_synthetic_record(
    *,
    recording_id: str,
    chunk_index: int,
    audio_path: Path,
    chunk_duration_sec: float,
    sample_rate: int,
    speaker_label: str | None,
    chunk_start_sec: float,
) -> dict[str, object]:
    """Create one Evaluation Tool record for a microphone chunk WAV."""

    chunk_duration_sec = _round_seconds(chunk_duration_sec)
    chunk_start_sec = _round_seconds(chunk_start_sec)
    return {
        "recording_id": recording_id,
        "utt_id": f"{recording_id}_chunk_{chunk_index:04d}",
        "inference_audio_path": str(audio_path),
        "audio_path_resolved": str(audio_path),
        "start_sec": 0.0,
        "end_sec": chunk_duration_sec,
        "duration_sec": chunk_duration_sec,
        "sample_rate_hz": sample_rate,
        "channel_count": 1,
        "speaker_label": speaker_label,
        "source_recording_id": recording_id,
        "chunk_index": chunk_index,
        "chunk_start_sec": chunk_start_sec,
        "chunk_end_sec": _round_seconds(chunk_start_sec + chunk_duration_sec),
        "capture_source": "live_microphone",
    }


def write_silence_wav(path: Path, *, duration_sec: float, sample_rate: int) -> Path:
    """Write a mono PCM silence WAV without microphone dependencies."""

    frames = max(1, int(round(duration_sec * sample_rate)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)
    return path


def inspect_runtime_availability(
    config: PipelineConfig,
    *,
    config_path: Path,
) -> dict[str, object]:
    """Return dependency and model-asset status without loading model weights."""

    asr = config.components["asr"]
    status: dict[str, object] = {
        "asr_component": asr.name,
        "asr_enabled": asr.enabled,
        "mic_package": "sounddevice",
        "mic_package_available": importlib.util.find_spec("sounddevice") is not None,
        "whisper_package_available": None,
        "whisper_model_asset_path": None,
        "whisper_model_asset_searched": [],
        "allow_model_downloads": config.runtime.allow_model_downloads,
        "blocker": None,
    }
    if not asr.enabled:
        status["blocker"] = "selected config has ASR disabled"
        return status

    if asr.name == "no_op_asr":
        status["blocker"] = (
            "selected config uses no_op_asr; pass --dry-run for a contract-only smoke "
            "or choose configs/inference/live_mic_whisper_tiny.yaml for real ASR"
        )
        return status

    if asr.name in {"whisper_tiny", "whisper_base"}:
        params = dict(asr.params or {})
        model_size = str(params.get("model_size") or asr.name.removeprefix("whisper_"))
        allow_downloads = _boolish(
            params.get("allow_model_downloads"),
            default=config.runtime.allow_model_downloads,
        )
        candidates = _whisper_model_asset_candidates(
            model_size,
            cache_dir=_optional_path(params.get("cache_dir")),
            config_path=config_path,
        )
        model_asset = next((candidate for candidate in candidates if candidate.is_file()), None)
        whisper_available = importlib.util.find_spec("whisper") is not None
        status.update(
            {
                "whisper_package_available": whisper_available,
                "whisper_model_size": model_size,
                "whisper_model_asset_path": str(model_asset) if model_asset is not None else None,
                "whisper_model_asset_searched": [str(path) for path in candidates],
                "allow_model_downloads": allow_downloads,
            }
        )
        if not whisper_available:
            status["blocker"] = (
                "OpenAI Whisper package is not installed in the active .venv."
            )
        elif not allow_downloads and model_asset is None:
            searched = ", ".join(str(path) for path in candidates)
            status["blocker"] = (
                f"Whisper model assets for model_size={model_size!r} were not found and "
                f"allow_model_downloads is false. Expected one of: {searched}"
            )
        return status

    if asr.name == "faster_whisper":
        package_available = importlib.util.find_spec("faster_whisper") is not None
        status.update(
            {
                "faster_whisper_package_available": package_available,
                "blocker": (
                    "faster_whisper execution is not wired for this live smoke path; "
                    "use whisper_tiny when local assets are available"
                ),
            }
        )
        return status

    return status


def write_component_report(
    result: LiveMicSmokeResult,
    *,
    speaker_label: str | None,
    command: Sequence[str],
    duration_sec: float,
    chunk_sec: float,
    sample_rate: int,
) -> Path:
    """Write the per-run live microphone component report."""

    if result.component_report_path is None:
        raise ValueError("component_report_path is required")
    result.component_report_path.parent.mkdir(parents=True, exist_ok=True)
    command_text = " ".join(command) if command else "not captured"
    availability = result.availability
    asr_blocker = availability.get("blocker") or "none for completed run"
    mic_dependency_available = availability.get("mic_package_available")
    if mic_dependency_available is False:
        mic_blocker = "missing optional dependency 'sounddevice'"
    elif result.dry_run:
        mic_blocker = "not exercised in dry-run mode"
    else:
        mic_blocker = "none for completed run"
    microphone_status = (
        "actual microphone capture was attempted"
        if result.microphone_capture_tested
        else "not tested; dry-run generated synthetic WAV chunks"
    )
    asr_status = (
        "dry-run no-op ASR"
        if result.dry_run
        else f"configured real ASR: {availability.get('asr_component')}"
    )
    remaining = (
        "- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, "
        "Whisper package, and local model assets are available."
        if result.dry_run
        else "- No incomplete work was identified by this smoke run."
    )
    text = f"""# Live Microphone Smoke Report

## Report Metadata
- Run id: `{result.run_id}`
- Date: `{datetime.now(timezone.utc).isoformat()}`
- Config path: `{result.config_path}`
- Run directory: `{result.run_dir}`

## What Changed
- Added a file-backed live microphone smoke path that records each chunk to WAV and calls `PipelineRunner.predict(...)` with `record["inference_audio_path"]`.
- Preserved the existing utterance prediction contract: `{", ".join(REQUIRED_PREDICTION_FIELDS)}`.

## How To Run
```bash
python scripts/live_mic_smoke.py --config configs/inference/live_mic_whisper_tiny.yaml --run-id {result.run_id} --duration-sec {duration_sec:g} --chunk-sec {chunk_sec:g} --sample-rate {sample_rate} --speaker-label {speaker_label or "Unknown"} --keep-audio
```

## Execution Mode
- Microphone capture: {microphone_status}.
- Microphone dependency available: `{mic_dependency_available}`.
- Real microphone blocker: `{mic_blocker}`.
- ASR mode: {asr_status}.
- Dry-run: `{result.dry_run}`.
- Whisper package available: `{availability.get("whisper_package_available")}`.
- Whisper model asset: `{availability.get("whisper_model_asset_path")}`.
- Model downloads allowed: `{availability.get("allow_model_downloads")}`.
- ASR/config blocker: `{asr_blocker}`.

## Commands Run
- `{command_text}`

## Output Artifacts
- Predictions: `{result.predictions_path}`
- Diagnostics: `{result.diagnostics_path}`
- Summary: `{result.summary_path}`
- Audio retained: `{result.audio_retained}`

## Remaining Incomplete Work
{remaining}
"""
    result.component_report_path.write_text(text, encoding="utf-8")
    return result.component_report_path


def resolve_config_path(path: Path | str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    cwd_candidate = Path.cwd() / candidate
    if cwd_candidate.is_file():
        return cwd_candidate.resolve()
    return (TOOL_ROOT / candidate).resolve()


def resolve_output_root(path: Path | str | None) -> Path:
    if path is None:
        return DEFAULT_OUTPUT_ROOT
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return TOOL_ROOT / candidate


def resolve_report_dir(path: Path | str | None) -> Path:
    if path is None:
        return DEFAULT_REPORT_DIR
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return TOOL_ROOT / candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record short microphone chunks and run Evaluation Tool inference.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/inference/live_mic_whisper_tiny.yaml"),
        help="Inference config path, absolute or Evaluation Tool relative.",
    )
    parser.add_argument("--run-id", default=None, help="Run id. Defaults to a UTC timestamp.")
    parser.add_argument("--duration-sec", type=float, default=10.0, help="Total capture seconds.")
    parser.add_argument("--chunk-sec", type=float, default=3.0, help="Seconds per chunk.")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Microphone sample rate.")
    parser.add_argument(
        "--speaker-label",
        default="Unknown",
        help="Speaker label placed in each synthetic Evaluation Tool record.",
    )
    parser.add_argument(
        "--recording-id",
        default="live_mic",
        help="Recording id placed in each synthetic Evaluation Tool record.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/live_mic"),
        help="Root directory that will contain the run-id folder.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/component_reports/live_mic"),
        help="Directory for the live mic component report.",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Retain captured chunk WAV files under the run directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate synthetic WAV chunks and use no-op ASR; no microphone or Whisper required.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = ("python", "scripts/live_mic_smoke.py", *(argv if argv is not None else sys.argv[1:]))
    try:
        result = run_live_mic_smoke(
            config_path=args.config,
            run_id=args.run_id,
            duration_sec=args.duration_sec,
            chunk_sec=args.chunk_sec,
            sample_rate=args.sample_rate,
            speaker_label=args.speaker_label,
            recording_id=args.recording_id,
            output_dir=args.output_dir,
            keep_audio=args.keep_audio,
            dry_run=args.dry_run,
            report_dir=args.report_dir,
            command=command,
        )
    except LiveMicSmokeError as exc:
        print(f"live mic smoke blocked: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("live mic smoke interrupted", file=sys.stderr)
        return 130

    print(f"Run directory: {result.run_dir}")
    print(f"Predictions: {result.predictions_path}")
    print(f"Diagnostics: {result.diagnostics_path}")
    print(f"Summary: {result.summary_path}")
    if result.component_report_path is not None:
        print(f"Component report: {result.component_report_path}")
    return 0


def _select_pipeline(
    config: PipelineConfig,
    availability: Mapping[str, object],
    *,
    dry_run: bool,
    pipeline_runner: Any | None,
) -> tuple[Any, str]:
    if pipeline_runner is not None:
        return pipeline_runner, "injected_pipeline"
    if dry_run:
        return (
            PipelineRunner(
                audio_reader=AudioLoaderAdapter(config),
                asr=NoOpASR("dry run transcript unavailable"),
                speaker_labeler=None,
                vad=None,
                segmenter=None,
                diarizer=None,
                speaker_embedding=None,
                speaker_matcher=None,
                device=config.runtime.device,
            ),
            "dry_run_no_op_asr",
        )
    blocker = availability.get("blocker")
    if blocker:
        raise LiveMicSmokeError(str(blocker))
    return PipelineRunner.from_config(config), str(availability.get("asr_component") or "configured_asr")


def _run_config(
    *,
    config: PipelineConfig,
    config_path: Path,
    run_id: str,
    run_dir: Path,
    duration_sec: float,
    chunk_sec: float,
    sample_rate: int,
    speaker_label: str | None,
    recording_id: str,
    dry_run: bool,
    command: Sequence[str],
    availability: Mapping[str, object],
) -> dict[str, object]:
    return {
        "command": "live_mic_smoke",
        "command_argv": list(command),
        "project_root": str(PROJECT_ROOT),
        "run_dir": str(run_dir),
        "config_path": str(config_path),
        "runtime": config.runtime.to_jsonable(),
        "components": {
            slot: component.to_jsonable()
            for slot, component in config.components.items()
        },
        "live_mic": {
            "run_id": run_id,
            "recording_id": recording_id,
            "speaker_label": speaker_label,
            "duration_sec": duration_sec,
            "chunk_sec": chunk_sec,
            "sample_rate": sample_rate,
            "dry_run": dry_run,
        },
        "availability": dict(availability),
    }


def _prediction_row(output: Any, *, record: Mapping[str, object] | None = None) -> dict[str, object]:
    to_row = getattr(output, "to_utterance_prediction_row", None)
    if callable(to_row):
        raw_row = to_row()
    else:
        raw_row = {
            field: getattr(output, field)
            for field in REQUIRED_PREDICTION_FIELDS
        }
    row = {field: raw_row.get(field) for field in REQUIRED_PREDICTION_FIELDS}
    if row.get("speaker_label") is None and record is not None:
        row["speaker_label"] = record.get("speaker_label")
    missing = [field for field in REQUIRED_PREDICTION_FIELDS if field not in row]
    if missing:
        raise LiveMicSmokeError(f"prediction row missing required fields: {missing}")
    return row


def _diagnostics_row(
    output: Any,
    pipeline: Any,
    record: Mapping[str, object],
    *,
    chunk_index: int,
    dry_run: bool,
) -> dict[str, object]:
    diagnostics = getattr(output, "diagnostics", None)
    if diagnostics is None:
        diagnostics = getattr(pipeline, "last_diagnostics", None)
    return {
        "chunk_index": chunk_index,
        "recording_id": getattr(output, "recording_id"),
        "utt_id": getattr(output, "utt_id"),
        "start_sec": getattr(output, "start_sec"),
        "end_sec": getattr(output, "end_sec"),
        "speaker_label": getattr(output, "speaker_label") or record.get("speaker_label"),
        "inference_audio_path": str(record["inference_audio_path"]),
        "dry_run": dry_run,
        "diagnostics": diagnostics or {},
        "warnings": list(getattr(output, "warnings", ()) or ()),
        "errors": list(getattr(output, "errors", ()) or ()),
    }


def _failed_diagnostics_row(
    record: Mapping[str, object],
    *,
    chunk_index: int,
    dry_run: bool,
    error: Exception,
) -> dict[str, object]:
    return {
        "chunk_index": chunk_index,
        "recording_id": record.get("recording_id"),
        "utt_id": record.get("utt_id"),
        "start_sec": record.get("start_sec"),
        "end_sec": record.get("end_sec"),
        "speaker_label": record.get("speaker_label"),
        "inference_audio_path": str(record.get("inference_audio_path")),
        "dry_run": dry_run,
        "diagnostics": {},
        "warnings": [],
        "errors": [f"{type(error).__name__}: {error}"],
    }


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _print_transcript_line(
    output: TextIO,
    *,
    run_id: str,
    chunk_index: int,
    chunk_count: int,
    prediction_row: Mapping[str, object],
    dry_run: bool,
) -> None:
    mode = "DRY-RUN" if dry_run else "LIVE"
    speaker = prediction_row.get("speaker_label") or "Unknown"
    text = str(prediction_row.get("text") or "").strip() or "(empty transcript)"
    print(f"[{mode} {run_id}] chunk {chunk_index}/{chunk_count} {speaker}: {text}", file=output)


def _remove_audio_files(paths: Sequence[Path], audio_dir: Path) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        audio_dir.rmdir()
    except OSError:
        pass


def _chunk_durations(duration_sec: float, chunk_sec: float) -> list[float]:
    chunk_count = max(1, int(math.ceil(duration_sec / chunk_sec)))
    durations = []
    for index in range(chunk_count):
        elapsed = index * chunk_sec
        durations.append(_round_seconds(min(chunk_sec, duration_sec - elapsed)))
    return [duration for duration in durations if duration > 0]


def _validate_smoke_args(
    duration_sec: float,
    chunk_sec: float,
    sample_rate: int,
    recording_id: str,
) -> None:
    if duration_sec <= 0:
        raise LiveMicSmokeError("--duration-sec must be > 0")
    if chunk_sec <= 0:
        raise LiveMicSmokeError("--chunk-sec must be > 0")
    if sample_rate < 1:
        raise LiveMicSmokeError("--sample-rate must be >= 1")
    if not str(recording_id).strip():
        raise LiveMicSmokeError("--recording-id must be non-empty")


def _whisper_model_asset_candidates(
    model_size: str,
    *,
    cache_dir: Path | None,
    config_path: Path,
) -> list[Path]:
    expected_name = f"{model_size}.pt"
    directories: list[Path] = []
    if cache_dir is not None:
        directories.append(cache_dir)
        if not cache_dir.is_absolute():
            directories.extend(
                [
                    Path.cwd() / cache_dir,
                    TOOL_ROOT / cache_dir,
                    PROJECT_ROOT / "Evaluation Tool" / cache_dir,
                    PROJECT_ROOT / cache_dir,
                    PROJECT_ROOT.parent / cache_dir,
                    config_path.parent / cache_dir,
                ]
            )
    directories.append(Path.home() / ".cache" / "whisper")
    return [_path / expected_name for _path in _dedupe_paths(directories)]


def _dedupe_paths(paths: Sequence[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path.expanduser())
    return unique


def _optional_path(value: object) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    return Path(str(value)).expanduser()


def _boolish(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes"}:
            return True
        if lowered in {"0", "false", "no"}:
            return False
    return bool(value)


def _safe_run_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    if not cleaned:
        raise LiveMicSmokeError("--run-id must contain at least one safe path character")
    return cleaned


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_live_mic")


def _round_seconds(value: float) -> float:
    return round(float(value), 6)


if __name__ == "__main__":
    raise SystemExit(main())
