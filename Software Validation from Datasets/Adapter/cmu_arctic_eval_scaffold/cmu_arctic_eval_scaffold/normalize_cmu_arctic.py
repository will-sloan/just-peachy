"""Normalize CMU ARCTIC into metadata-only reference tables."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd
import soundfile as sf
import yaml

from schema_defs import (
    LOG_COLUMNS,
    RECORDINGS_COLUMNS,
    UTTERANCES_COLUMNS,
    build_recording_id,
)
from text_normalization import normalize_text


TRANSCRIPT_LINE_RE = re.compile(r'^\s*\(\s*(\S+)\s+"(.*)"\s*\)\s*$')


@dataclass
class AudioInfo:
    sample_rate_hz: int
    duration_sec: float
    num_channels: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize CMU ARCTIC into metadata tables.")
    parser.add_argument("--dataset-root", required=True, help="Path to raw CMU Arctic dataset root.")
    parser.add_argument("--output-dir", required=True, help="Directory where normalized outputs will be written.")
    parser.add_argument(
        "--speaker-metadata",
        required=True,
        help="Path to cmu_arctic_speaker_metadata.yaml.",
    )
    parser.add_argument(
        "--use-global-fallback",
        action="store_true",
        help="Use cmuarctic_data.txt as fallback for missing per-speaker transcript rows.",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def discover_speaker_dirs(dataset_root: Path) -> List[Path]:
    speaker_dirs: List[Path] = []
    for child in sorted(dataset_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("cmu_") and child.name.endswith("_arctic"):
            if (child / "etc" / "txt.done.data").exists() and (child / "wav").exists():
                speaker_dirs.append(child)
    return speaker_dirs


def parse_transcript_file(path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            match = TRANSCRIPT_LINE_RE.match(line)
            if not match:
                raise ValueError(f"Could not parse transcript line at {path}:{lineno}: {raw_line!r}")
            utt_id, text = match.groups()
            mapping[utt_id] = text
    return mapping


def maybe_parse_global_transcripts(dataset_root: Path) -> Dict[str, str]:
    global_path = dataset_root / "cmuarctic_data.txt"
    if not global_path.exists():
        return {}
    return parse_transcript_file(global_path)


def read_audio_info(path: Path) -> AudioInfo:
    info = sf.info(str(path))
    return AudioInfo(
        sample_rate_hz=int(info.samplerate),
        duration_sec=float(info.frames) / float(info.samplerate),
        num_channels=int(info.channels),
    )


def emit_log_row(
    rows: List[Dict[str, str]],
    *,
    level: str,
    speaker_id: str = "",
    utterance_id: str = "",
    audio_path: str = "",
    transcript_path: str = "",
    issue_type: str = "",
    details: str = "",
) -> None:
    rows.append(
        {
            "level": level,
            "speaker_id": speaker_id,
            "utterance_id": utterance_id,
            "audio_path": audio_path,
            "transcript_path": transcript_path,
            "issue_type": issue_type,
            "details": details,
        }
    )


def build_issues_block(log_df: pd.DataFrame) -> str:
    if log_df.empty:
        return "- none"
    lines = []
    for _, row in log_df.head(50).iterrows():
        lines.append(
            f"- [{row['level']}] {row['issue_type']} | speaker={row['speaker_id']} "
            f"| utt={row['utterance_id']} | details={row['details']}"
        )
    if len(log_df) > 50:
        lines.append(f"- ... {len(log_df) - 50} additional issue rows omitted from README")
    return "\n".join(lines)


def write_readme(
    output_dir: Path,
    dataset_root: Path,
    num_speakers: int,
    num_transcript_rows: int,
    num_recordings: int,
    num_log_rows: int,
    issues_block: str,
) -> None:
    template_path = Path(__file__).resolve().parent / "README_normalized_template.md"
    template = template_path.read_text(encoding="utf-8")
    rendered = template.format(
        dataset_root=str(dataset_root),
        num_speakers=num_speakers,
        num_transcript_rows=num_transcript_rows,
        num_recordings=num_recordings,
        num_log_rows=num_log_rows,
        issues_block=issues_block,
    )
    (output_dir / "README_normalized.md").write_text(rendered, encoding="utf-8")


def main() -> None:
    args = parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    speaker_metadata_path = Path(args.speaker_metadata).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_doc = load_yaml(speaker_metadata_path)
    speaker_metadata: Dict[str, Dict[str, str]] = metadata_doc.get("speakers", {})
    global_transcripts = maybe_parse_global_transcripts(dataset_root) if args.use_global_fallback else {}

    speaker_dirs = discover_speaker_dirs(dataset_root)

    recordings_rows: List[Dict] = []
    utterances_rows: List[Dict] = []
    log_rows: List[Dict[str, str]] = []

    total_transcript_rows = 0

    for speaker_dir in speaker_dirs:
        speaker_id = speaker_dir.name
        transcript_path = speaker_dir / "etc" / "txt.done.data"
        wav_dir = speaker_dir / "wav"

        try:
            local_transcripts = parse_transcript_file(transcript_path)
        except Exception as exc:
            emit_log_row(
                log_rows,
                level="ERROR",
                speaker_id=speaker_id,
                transcript_path=str(transcript_path),
                issue_type="transcript_parse_error",
                details=str(exc),
            )
            continue

        total_transcript_rows += len(local_transcripts)

        speaker_meta = speaker_metadata.get(speaker_id)
        if speaker_meta is None:
            emit_log_row(
                log_rows,
                level="WARNING",
                speaker_id=speaker_id,
                transcript_path=str(transcript_path),
                issue_type="speaker_metadata_missing",
                details="Speaker metadata missing from YAML.",
            )
            speaker_meta = {
                "speaker_code": speaker_id,
                "gender": "unknown",
                "accent": "unknown",
                "accent_group": "unknown",
                "speaker_variant_group": "unknown",
            }

        wav_files = {p.stem: p for p in sorted(wav_dir.glob("*.wav"))}

        for utterance_id, transcript_text in local_transcripts.items():
            audio_path = wav_files.get(utterance_id)

            if audio_path is None and args.use_global_fallback and utterance_id in global_transcripts:
                # fallback transcript only matters if later logic is extended; currently still no audio means skip
                pass

            if audio_path is None:
                emit_log_row(
                    log_rows,
                    level="WARNING",
                    speaker_id=speaker_id,
                    utterance_id=utterance_id,
                    transcript_path=str(transcript_path),
                    issue_type="missing_audio_for_transcript",
                    details="Transcript row exists but matching WAV was not found.",
                )
                continue

            try:
                audio_info = read_audio_info(audio_path)
            except Exception as exc:
                emit_log_row(
                    log_rows,
                    level="ERROR",
                    speaker_id=speaker_id,
                    utterance_id=utterance_id,
                    audio_path=str(audio_path),
                    transcript_path=str(transcript_path),
                    issue_type="audio_read_error",
                    details=str(exc),
                )
                continue

            speaker_code = speaker_meta["speaker_code"]
            recording_id = build_recording_id("cmu_arctic", speaker_code, utterance_id)
            text_norm = normalize_text(transcript_text)

            recordings_rows.append(
                {
                    "recording_id": recording_id,
                    "dataset": "CMU Arctic",
                    "dataset_id": "cmu_arctic",
                    "speaker_id": speaker_id,
                    "speaker_code": speaker_code,
                    "gender": speaker_meta["gender"],
                    "accent": speaker_meta["accent"],
                    "accent_group": speaker_meta["accent_group"],
                    "speaker_variant_group": speaker_meta["speaker_variant_group"],
                    "utterance_id": utterance_id,
                    "audio_path": str(audio_path),
                    "sample_rate_hz": audio_info.sample_rate_hz,
                    "duration_sec": round(audio_info.duration_sec, 6),
                    "num_channels": audio_info.num_channels,
                    "text_source": "per_speaker_txt.done.data",
                    "raw_transcript_path": str(transcript_path),
                    "normalization_status": "ok",
                }
            )

            utterances_rows.append(
                {
                    "recording_id": recording_id,
                    "dataset": "CMU Arctic",
                    "dataset_id": "cmu_arctic",
                    "speaker_id": speaker_id,
                    "speaker_code": speaker_code,
                    "gender": speaker_meta["gender"],
                    "accent": speaker_meta["accent"],
                    "accent_group": speaker_meta["accent_group"],
                    "speaker_variant_group": speaker_meta["speaker_variant_group"],
                    "utterance_id": utterance_id,
                    "start_sec": 0.0,
                    "end_sec": round(audio_info.duration_sec, 6),
                    "text_original": transcript_text,
                    "text_norm": text_norm,
                    "text_source": "per_speaker_txt.done.data",
                    "audio_path": str(audio_path),
                }
            )

        for utterance_id, audio_path in wav_files.items():
            if utterance_id not in local_transcripts:
                fallback_note = ""
                if args.use_global_fallback and utterance_id in global_transcripts:
                    fallback_note = " Global fallback transcript exists."
                emit_log_row(
                    log_rows,
                    level="WARNING",
                    speaker_id=speaker_id,
                    utterance_id=utterance_id,
                    audio_path=str(audio_path),
                    transcript_path=str(transcript_path),
                    issue_type="missing_transcript_for_audio",
                    details="WAV exists without per-speaker transcript row." + fallback_note,
                )

    recordings_df = pd.DataFrame(recordings_rows, columns=RECORDINGS_COLUMNS)
    utterances_df = pd.DataFrame(utterances_rows, columns=UTTERANCES_COLUMNS)
    log_df = pd.DataFrame(log_rows, columns=LOG_COLUMNS)

    recordings_df.to_parquet(output_dir / "recordings.parquet", index=False)
    utterances_df.to_parquet(output_dir / "utterances.parquet", index=False)
    log_df.to_csv(output_dir / "normalization_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    issues_block = build_issues_block(log_df)
    write_readme(
        output_dir=output_dir,
        dataset_root=dataset_root,
        num_speakers=len(speaker_dirs),
        num_transcript_rows=total_transcript_rows,
        num_recordings=len(recordings_df),
        num_log_rows=len(log_df),
        issues_block=issues_block,
    )

    print("Normalization complete.")
    print(f"Speaker folders processed: {len(speaker_dirs)}")
    print(f"Transcript rows parsed: {total_transcript_rows}")
    print(f"Recordings written: {len(recordings_df)}")
    print(f"Issues logged: {len(log_df)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
