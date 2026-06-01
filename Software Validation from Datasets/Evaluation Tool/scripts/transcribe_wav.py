"""Transcribe one or more WAV files through the inference pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import soundfile as sf


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.pipeline import PipelineRunner, pipeline_config_mapping
from app.utils.json_utils import write_jsonl


REAL_LOCAL_CONFIG = TOOL_ROOT / "configs" / "inference" / "e2e_real_local.yaml"
SMOKE_SAFE_CONFIG = TOOL_ROOT / "configs" / "inference" / "e2e_named_transcript.yaml"
PRESET_CONFIGS = {
    "safe": TOOL_ROOT / "configs" / "inference" / "presets" / "safe.yaml",
    "tiny": TOOL_ROOT / "configs" / "inference" / "presets" / "tiny.yaml",
    "base": TOOL_ROOT / "configs" / "inference" / "presets" / "base.yaml",
}
AUDIO_SUFFIXES = {".wav"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return transcribe_wavs(args)
    except ValueError as exc:
        print(f"transcribe_wav: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcribe WAV files through the local inference pipeline.",
    )
    parser.add_argument("audio", type=Path, nargs="+", help="One or more WAV files.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Advanced inference pipeline YAML config. Overrides preset selection.",
    )
    parser.add_argument(
        "--preset",
        choices=tuple(PRESET_CONFIGS),
        default=None,
        help="User-friendly config preset. Defaults to tiny when available.",
    )
    parser.add_argument(
        "--smoke-safe",
        action="store_true",
        help="Alias for --preset safe.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Stdout output format.",
    )
    parser.add_argument(
        "--segments",
        action="store_true",
        help="Include assembled transcript segments in JSON/JSONL output.",
    )
    parser.add_argument(
        "--diagnostics",
        type=Path,
        default=None,
        help="Optional JSONL file for pipeline diagnostics.",
    )
    parser.add_argument("--recording-id", default=None, help="Override recording_id for one WAV.")
    parser.add_argument("--utt-id", default=None, help="Override utt_id for one WAV.")
    parser.add_argument(
        "--true-speaker",
        default=None,
        help="Ground-truth speaker label for one WAV. CMU Arctic paths can be inferred.",
    )
    parser.add_argument(
        "--show-truth",
        action="store_true",
        help="Show true speaker, predicted speaker, and text in text output.",
    )
    parser.add_argument("--start-sec", type=float, default=0.0, help="Optional start time in seconds.")
    parser.add_argument("--end-sec", type=float, default=None, help="Optional end time in seconds.")
    parser.add_argument(
        "--enrollment-db",
        type=Path,
        default=None,
        help="Optional enrollment DB path for this direct CLI run.",
    )
    return parser


def transcribe_wavs(args: argparse.Namespace) -> int:
    audio_paths = validate_audio_paths(args.audio)
    validate_identity_overrides(args, audio_paths)
    config = load_cli_config(args)
    pipeline = PipelineRunner.from_config(config)

    rows: list[dict[str, object]] = []
    diagnostics_rows: list[dict[str, object]] = []
    failures: list[str] = []

    for index, audio_path in enumerate(audio_paths):
        try:
            record = wav_record(audio_path, args=args, index=index)
            output = pipeline.predict(record, config)
            include_true_speaker = args.show_truth or args.true_speaker is not None
            rows.append(
                output_row(
                    output,
                    audio_path,
                    include_segments=args.segments,
                    true_speaker_label=(
                        record.get("true_speaker_label") if include_true_speaker else None
                    ),
                    true_speaker_requested=include_true_speaker,
                )
            )
            diagnostics = getattr(pipeline, "last_diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics_rows.append(dict(diagnostics))
        except Exception as exc:  # pragma: no cover - exercised via subprocess boundary
            failures.append(f"{audio_path}: {exc}")

    if args.diagnostics is not None:
        write_jsonl(args.diagnostics, diagnostics_rows)

    write_stdout(rows, args.format)
    if failures:
        for failure in failures:
            print(f"failed: {failure}", file=sys.stderr)
        return 1
    return 0


def validate_audio_paths(paths: Sequence[Path]) -> list[Path]:
    resolved: list[Path] = []
    for path in paths:
        candidate = path.expanduser()
        if candidate.suffix.lower() not in AUDIO_SUFFIXES:
            raise ValueError(f"input must be a WAV file: {candidate}")
        if not candidate.is_file():
            raise ValueError(f"WAV file does not exist: {candidate}")
        resolved.append(candidate.resolve())
    return resolved


def validate_identity_overrides(args: argparse.Namespace, audio_paths: Sequence[Path]) -> None:
    if len(audio_paths) <= 1:
        return
    if args.recording_id is not None:
        raise ValueError("--recording-id can only be used with one WAV")
    if args.utt_id is not None:
        raise ValueError("--utt-id can only be used with one WAV")
    if args.true_speaker is not None:
        raise ValueError("--true-speaker can only be used with one WAV")


def load_cli_config(args: argparse.Namespace) -> dict[str, object]:
    selected_flags = [
        name
        for name, enabled in (
            ("--config", args.config is not None),
            ("--preset", args.preset is not None),
            ("--smoke-safe", bool(args.smoke_safe)),
        )
        if enabled
    ]
    if len(selected_flags) > 1:
        raise ValueError(f"{', '.join(selected_flags)} are mutually exclusive")
    config_path = selected_config_path(args)
    config = pipeline_config_mapping(config_path)
    config["project_root"] = str(PROJECT_ROOT)
    config["command"] = "transcribe_wav"
    if args.enrollment_db is not None:
        config["enrollment"] = {
            **dict(config.get("enrollment") or {}),
            "db_path": str(args.enrollment_db.expanduser()),
        }
    return config


def selected_config_path(args: argparse.Namespace) -> Path:
    if args.smoke_safe:
        return _preset_path("safe")
    if args.preset is not None:
        return _preset_path(args.preset)
    if args.config is not None:
        return args.config
    tiny_preset = PRESET_CONFIGS["tiny"]
    if tiny_preset.is_file():
        return tiny_preset
    if REAL_LOCAL_CONFIG.is_file():
        return REAL_LOCAL_CONFIG
    return SMOKE_SAFE_CONFIG


def _preset_path(name: str) -> Path:
    path = PRESET_CONFIGS[name]
    if path.is_file():
        return path
    if name == "safe":
        return SMOKE_SAFE_CONFIG
    if name == "tiny":
        return REAL_LOCAL_CONFIG
    if name == "base":
        fallback = TOOL_ROOT / "configs" / "inference" / "e2e_whisper_base.yaml"
        if fallback.is_file():
            return fallback
    raise ValueError(f"preset {name!r} is not available: {path}")


def wav_record(audio_path: Path, *, args: argparse.Namespace, index: int) -> dict[str, object]:
    info = sf.info(audio_path)
    source_duration_sec = float(info.frames) / float(info.samplerate)
    start_sec = args.start_sec
    end_sec = args.end_sec if args.end_sec is not None else source_duration_sec
    if start_sec is not None and end_sec is not None and end_sec < start_sec:
        raise ValueError("end_sec must be >= start_sec")

    stem = audio_path.stem
    recording_id = args.recording_id if args.recording_id is not None else stem
    utt_id = args.utt_id if args.utt_id is not None else stem
    if index:
        recording_id = stem
        utt_id = stem
    return {
        "recording_id": recording_id,
        "utt_id": utt_id,
        "inference_audio_path": str(audio_path),
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": source_duration_sec,
        "sample_rate_hz": int(info.samplerate),
        "channel_count": int(info.channels),
        "true_speaker_label": true_speaker_label(audio_path, args=args),
    }


def true_speaker_label(audio_path: Path, *, args: argparse.Namespace) -> str | None:
    if args.true_speaker is not None:
        return str(args.true_speaker)
    return infer_cmu_arctic_speaker_label(audio_path)


def infer_cmu_arctic_speaker_label(audio_path: Path) -> str | None:
    parts = audio_path.parts
    for index, part in enumerate(parts):
        if part == "wav" and index > 0:
            speaker = parts[index - 1]
            if speaker.startswith("cmu_us_") and speaker.endswith("_arctic"):
                return speaker
    return None


def output_row(
    output: object,
    audio_path: Path,
    *,
    include_segments: bool,
    true_speaker_label: object = None,
    true_speaker_requested: bool = False,
) -> dict[str, object]:
    row = {
        "recording_id": getattr(output, "recording_id"),
        "utt_id": getattr(output, "utt_id"),
        "audio_path": str(audio_path),
        "start_sec": getattr(output, "start_sec"),
        "end_sec": getattr(output, "end_sec"),
        "speaker_label": getattr(output, "speaker_label") or "Unknown",
        "text": getattr(output, "text"),
    }
    if true_speaker_requested:
        row["true_speaker_label"] = str(true_speaker_label or "(unavailable)")
    if include_segments:
        row["segments"] = [
            item.to_jsonable() if hasattr(item, "to_jsonable") else dict(item)
            for item in getattr(output, "transcript_items", ())
        ]
    return row


def write_stdout(rows: list[dict[str, object]], output_format: str) -> None:
    if output_format == "json":
        payload: object = rows[0] if len(rows) == 1 else rows
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    if output_format == "jsonl":
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return
    for row in rows:
        label = row.get("speaker_label") or "Unknown"
        if row.get("true_speaker_label"):
            print(
                " | ".join(
                    (
                        f"true: {row['true_speaker_label']}",
                        f"predicted: {label}",
                        f"text: {row.get('text') or ''}",
                    )
                ).rstrip()
            )
        else:
            print(f"[{label}] {row.get('text') or ''}".rstrip())


if __name__ == "__main__":
    raise SystemExit(main())
