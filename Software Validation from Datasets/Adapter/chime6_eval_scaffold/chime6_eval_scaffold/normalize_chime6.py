"""Normalize CHiME-6 into metadata-only reference tables with progress reporting."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import soundfile as sf
from tqdm import tqdm

from schema_defs import (
    LOG_COLUMNS,
    RECORDINGS_COLUMNS,
    SEGMENTS_COLUMNS,
    SPLITS,
    UTTERANCES_COLUMNS,
    build_recording_id,
    build_segment_id,
    build_utterance_key,
)
from text_normalization import normalize_text


PARTICIPANT_RE = re.compile(r"^(S\d{2})_(P\d{2})\.wav$", re.IGNORECASE)
ARRAY_RE = re.compile(r"^(S\d{2})_(U\d{2})\.(CH\d)\.wav$", re.IGNORECASE)


@dataclass
class AudioInfo:
    sample_rate_hz: int
    duration_sec: float
    num_channels: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize CHiME-6 into metadata tables.")
    parser.add_argument("--dataset-root", required=True, help="Path to raw CHiME 6 dataset root.")
    parser.add_argument("--output-dir", required=True, help="Directory where normalized outputs will be written.")
    return parser.parse_args()


def read_audio_info(path: Path) -> AudioInfo:
    info = sf.info(str(path))
    return AudioInfo(
        sample_rate_hz=int(info.samplerate),
        duration_sec=float(info.frames) / float(info.samplerate),
        num_channels=int(info.channels),
    )


def parse_time_to_seconds(value: str) -> float:
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def emit_log_row(
    rows: List[Dict[str, str]],
    *,
    level: str,
    split: str = "",
    session_id: str = "",
    speaker_id_ref: str = "",
    audio_path: str = "",
    annotation_path: str = "",
    issue_type: str = "",
    details: str = "",
) -> None:
    rows.append(
        {
            "level": level,
            "split": split,
            "session_id": session_id,
            "speaker_id_ref": speaker_id_ref,
            "audio_path": audio_path,
            "annotation_path": annotation_path,
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
            f"- [{row['level']}] {row['issue_type']} | split={row['split']} "
            f"| session={row['session_id']} | speaker={row['speaker_id_ref']} | details={row['details']}"
        )
    if len(log_df) > 50:
        lines.append(f"- ... {len(log_df) - 50} additional issue rows omitted from README")
    return "\n".join(lines)


def write_readme(
    output_dir: Path,
    dataset_root: Path,
    num_splits: int,
    num_recordings: int,
    num_utterances: int,
    num_log_rows: int,
    issues_block: str,
) -> None:
    template_path = Path(__file__).resolve().parent / "README_normalized_template.md"
    template = template_path.read_text(encoding="utf-8")
    included_splits_block = "\n".join([f"- `{s}`" for s in SPLITS])
    rendered = template.format(
        dataset_root=str(dataset_root),
        included_splits_block=included_splits_block,
        num_splits=num_splits,
        num_recordings=num_recordings,
        num_utterances=num_utterances,
        num_log_rows=num_log_rows,
        issues_block=issues_block,
    )
    (output_dir / "README_normalized.md").write_text(rendered, encoding="utf-8")


def discover_audio_root(dataset_root: Path, split: str) -> Path:
    mapping = {
        "train": dataset_root / "CHiME6_train" / "CHiME6_train" / "CHiME6" / "audio" / "train",
        "dev": dataset_root / "CHiME6_dev" / "CHiME6_dev" / "CHiME6" / "audio" / "dev",
        "eval": dataset_root / "CHiME6_eval" / "CHiME6_eval" / "CHiME6" / "audio" / "eval",
    }
    return mapping[split]


def discover_json_root(dataset_root: Path, split: str) -> Path:
    return dataset_root / "CHiME6_transcriptions" / "transcriptions" / "transcriptions" / split


def index_audio_streams(audio_root: Path, split: str, log_rows: List[Dict[str, str]]) -> List[Dict]:
    rows: List[Dict] = []
    wav_files = sorted(audio_root.glob("*.wav"))

    for audio_path in tqdm(wav_files, desc=f"{split} audio", unit="wav", leave=False, dynamic_ncols=True):
        name = audio_path.name
        participant_match = PARTICIPANT_RE.match(name)
        array_match = ARRAY_RE.match(name)

        session_id = ""
        stream_type = ""
        speaker_id_ref = None
        device_id = None
        channel_id = None

        if participant_match:
            session_id, speaker_id_ref = participant_match.groups()
            stream_type = "participant_close"
        elif array_match:
            session_id, device_id, channel_id = array_match.groups()
            stream_type = "farfield_array"
        else:
            emit_log_row(
                log_rows,
                level="WARNING",
                split=split,
                audio_path=str(audio_path),
                issue_type="unrecognized_audio_filename",
                details=f"Could not parse audio filename pattern: {name}",
            )
            continue

        try:
            info = read_audio_info(audio_path)
        except Exception as exc:
            emit_log_row(
                log_rows,
                level="ERROR",
                split=split,
                session_id=session_id,
                speaker_id_ref=speaker_id_ref or "",
                audio_path=str(audio_path),
                issue_type="audio_read_error",
                details=str(exc),
            )
            continue

        recording_id = build_recording_id(
            split=split,
            session_id=session_id,
            stream_type=stream_type,
            speaker_or_device=speaker_id_ref or device_id,
            channel_id=channel_id,
        )

        rows.append(
            {
                "recording_id": recording_id,
                "dataset": "CHiME-6",
                "dataset_id": "chime6",
                "split": split,
                "session_id": session_id,
                "stream_type": stream_type,
                "speaker_id_ref": speaker_id_ref,
                "device_id": device_id,
                "channel_id": channel_id,
                "audio_path": str(audio_path),
                "sample_rate_hz": info.sample_rate_hz,
                "duration_sec": round(info.duration_sec, 6),
                "num_channels": info.num_channels,
                "location_hint": None,
            }
        )

    return rows


def parse_json_segments(json_path: Path) -> List[Dict]:
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {json_path}")
    return data


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    recordings_rows: List[Dict] = []
    utterances_rows: List[Dict] = []
    segments_rows: List[Dict] = []
    log_rows: List[Dict[str, str]] = []

    print("[1/5] Discovering audio roots and JSON roots...")
    split_info: List[Tuple[str, Path, Path]] = []
    for split in SPLITS:
        audio_root = discover_audio_root(dataset_root, split)
        json_root = discover_json_root(dataset_root, split)
        split_info.append((split, audio_root, json_root))
        if not audio_root.exists():
            emit_log_row(log_rows, level="WARNING", split=split, issue_type="missing_audio_root", details=str(audio_root))
        if not json_root.exists():
            emit_log_row(log_rows, level="WARNING", split=split, issue_type="missing_json_root", details=str(json_root))

    available_splits = [s for s, a, j in split_info if a.exists() and j.exists()]
    print(f"      Found {len(available_splits)} usable splits")

    print("[2/5] Indexing session audio streams...")
    for split, audio_root, json_root in tqdm(split_info, desc="Splits", unit="split", dynamic_ncols=True):
        if not audio_root.exists():
            continue
        rows = index_audio_streams(audio_root, split, log_rows)
        recordings_rows.extend(rows)

    location_hint_map: Dict[Tuple[str, str, str], str] = {}

    print("[3/5] Parsing JSON transcript/segment files...")
    utterance_counter = 0
    segment_counter = 0

    for split, audio_root, json_root in tqdm(split_info, desc="Annotation splits", unit="split", dynamic_ncols=True):
        if not json_root.exists():
            continue

        json_files = sorted(json_root.glob("*.json"))
        for json_path in tqdm(json_files, desc=f"{split} json", unit="file", leave=False, dynamic_ncols=True):
            session_id = json_path.stem
            try:
                rows = parse_json_segments(json_path)
            except Exception as exc:
                emit_log_row(
                    log_rows,
                    level="ERROR",
                    split=split,
                    session_id=session_id,
                    annotation_path=str(json_path),
                    issue_type="json_parse_error",
                    details=str(exc),
                )
                continue

            for row in rows:
                utterance_counter += 1
                segment_counter += 1

                speaker_id_ref = row.get("speaker")
                start_sec = parse_time_to_seconds(row["start_time"])
                end_sec = parse_time_to_seconds(row["end_time"])
                duration_sec = round(end_sec - start_sec, 6)
                words = row.get("words", "")
                ref_device = row.get("ref")
                location = row.get("location")

                if ref_device and location:
                    location_hint_map[(split, session_id, ref_device)] = location

                utterances_rows.append(
                    {
                        "utterance_key": build_utterance_key(split, session_id, utterance_counter),
                        "dataset": "CHiME-6",
                        "dataset_id": "chime6",
                        "split": split,
                        "session_id": session_id,
                        "speaker_id_ref": speaker_id_ref,
                        "start_sec": round(start_sec, 6),
                        "end_sec": round(end_sec, 6),
                        "duration_sec": duration_sec,
                        "text_original": words,
                        "text_norm": normalize_text(words),
                        "ref_device": ref_device,
                        "location": location,
                    }
                )

                segments_rows.append(
                    {
                        "segment_id": build_segment_id(split, session_id, segment_counter),
                        "dataset": "CHiME-6",
                        "dataset_id": "chime6",
                        "split": split,
                        "session_id": session_id,
                        "speaker_id_ref": speaker_id_ref,
                        "start_sec": round(start_sec, 6),
                        "end_sec": round(end_sec, 6),
                        "duration_sec": duration_sec,
                        "ref_device": ref_device,
                        "location": location,
                        "has_overlap_candidate": False,
                    }
                )

    print("[4/5] Finalizing data tables and writing files...")
    recordings_df = pd.DataFrame(recordings_rows, columns=RECORDINGS_COLUMNS)

    if not recordings_df.empty:
        hints = []
        for _, r in recordings_df.iterrows():
            if r["stream_type"] == "farfield_array" and r["device_id"]:
                hint = location_hint_map.get((r["split"], r["session_id"], r["device_id"]))
                hints.append(hint)
            else:
                hints.append(None)
        recordings_df["location_hint"] = hints

    utterances_df = pd.DataFrame(utterances_rows, columns=UTTERANCES_COLUMNS)
    segments_df = pd.DataFrame(segments_rows, columns=SEGMENTS_COLUMNS)
    log_df = pd.DataFrame(log_rows, columns=LOG_COLUMNS)

    if not segments_df.empty:
        segments_df = segments_df.sort_values(["split", "session_id", "start_sec", "end_sec"]).reset_index(drop=True)
        overlap_flags = [False] * len(segments_df)
        for i in range(len(segments_df) - 1):
            cur = segments_df.iloc[i]
            nxt = segments_df.iloc[i + 1]
            if cur["split"] == nxt["split"] and cur["session_id"] == nxt["session_id"]:
                if nxt["start_sec"] < cur["end_sec"]:
                    overlap_flags[i] = True
                    overlap_flags[i + 1] = True
        segments_df["has_overlap_candidate"] = overlap_flags

    recordings_df.to_parquet(output_dir / "recordings.parquet", index=False)
    utterances_df.to_parquet(output_dir / "utterances.parquet", index=False)
    segments_df.to_parquet(output_dir / "segments.parquet", index=False)
    log_df.to_csv(output_dir / "normalization_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    issues_block = build_issues_block(log_df)
    write_readme(
        output_dir=output_dir,
        dataset_root=dataset_root,
        num_splits=len(available_splits),
        num_recordings=len(recordings_df),
        num_utterances=len(utterances_df),
        num_log_rows=len(log_df),
        issues_block=issues_block,
    )

    print("[5/5] Done")
    print(f"Usable splits processed: {len(available_splits)}")
    print(f"Audio streams indexed: {len(recordings_df)}")
    print(f"Transcript segments written: {len(utterances_df)}")
    print(f"Diarization segments written: {len(segments_df)}")
    print(f"Issues logged: {len(log_df)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
