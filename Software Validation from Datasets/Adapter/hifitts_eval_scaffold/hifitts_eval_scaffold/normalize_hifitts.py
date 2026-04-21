"""Normalize Hi Fi TTS into metadata-only reference tables."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import soundfile as sf
import yaml
from tqdm import tqdm

from schema_defs import (
    BOOK_BANDWIDTH_COLUMNS,
    LOG_COLUMNS,
    READERS_COLUMNS,
    READER_BOOKS_COLUMNS,
    RECORDINGS_COLUMNS,
    UTTERANCES_COLUMNS,
    build_recording_id,
)
from text_normalization import normalize_text


@dataclass
class AudioInfo:
    sample_rate_hz: int
    duration_sec: float
    num_channels: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Hi Fi TTS into metadata tables.")
    parser.add_argument("--dataset-root", required=True, help="Path to raw hi_fi_tts_v0 dataset root.")
    parser.add_argument("--output-dir", required=True, help="Directory where normalized outputs will be written.")
    parser.add_argument("--reader-metadata", required=True, help="Path to hifitts_reader_metadata.yaml.")
    return parser.parse_args()


def load_yaml(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def emit_log_row(
    rows: List[Dict[str, str]],
    *,
    level: str,
    reader_id: str = "",
    audio_quality: str = "",
    split: str = "",
    book_id: str = "",
    audio_filepath_relative: str = "",
    manifest_path: str = "",
    issue_type: str = "",
    details: str = "",
) -> None:
    rows.append(
        {
            "level": level,
            "reader_id": reader_id,
            "audio_quality": audio_quality,
            "split": split,
            "book_id": book_id,
            "audio_filepath_relative": audio_filepath_relative,
            "manifest_path": manifest_path,
            "issue_type": issue_type,
            "details": details,
        }
    )


def parse_manifest_filename(path: Path) -> Optional[Dict[str, str]]:
    # <reader_id>_manifest_<audio_quality>_<split>.json
    stem = path.stem
    parts = stem.split("_")
    if len(parts) < 4:
        return None
    if parts[1] != "manifest":
        return None
    reader_id = parts[0]
    audio_quality = parts[2]
    split = parts[3]
    return {"reader_id": reader_id, "audio_quality": audio_quality, "split": split}


def read_audio_info(path: Path) -> AudioInfo:
    info = sf.info(str(path))
    return AudioInfo(
        sample_rate_hz=int(info.samplerate),
        duration_sec=float(info.frames) / float(info.samplerate),
        num_channels=int(info.channels),
    )


def load_reader_books(path: Path, audio_quality: str) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("READER_ID"):
                continue
            reader_id, book_ids = line.split(":", 1)
            for book_id in book_ids.split("|"):
                book_id = book_id.strip()
                if book_id:
                    rows.append(
                        {
                            "audio_quality": audio_quality,
                            "reader_id": reader_id.strip(),
                            "book_id": book_id,
                        }
                    )
    return pd.DataFrame(rows, columns=READER_BOOKS_COLUMNS)


def load_book_bandwidth(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        header = next(f, None)
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            rows.append(
                {
                    "reader_id": parts[0].strip(),
                    "book_id": parts[1].strip(),
                    "audio_quality": parts[2].strip(),
                    "book_bandwidth": parts[3].strip(),
                    "book_bandwidth_comment": parts[4].strip(),
                }
            )
    return pd.DataFrame(rows, columns=BOOK_BANDWIDTH_COLUMNS)


def build_issues_block(log_df: pd.DataFrame) -> str:
    if log_df.empty:
        return "- none"
    lines = []
    for _, row in log_df.head(50).iterrows():
        lines.append(
            f"- [{row['level']}] {row['issue_type']} | reader={row['reader_id']} "
            f"| quality={row['audio_quality']} | split={row['split']} | book={row['book_id']} "
            f"| details={row['details']}"
        )
    if len(log_df) > 50:
        lines.append(f"- ... {len(log_df) - 50} additional issue rows omitted from README")
    return "\n".join(lines)


def write_readme(
    output_dir: Path,
    dataset_root: Path,
    num_manifest_files: int,
    num_manifest_rows: int,
    num_recordings: int,
    num_log_rows: int,
    issues_block: str,
) -> None:
    template_path = Path(__file__).resolve().parent / "README_normalized_template.md"
    template = template_path.read_text(encoding="utf-8")
    rendered = template.format(
        dataset_root=str(dataset_root),
        num_manifest_files=num_manifest_files,
        num_manifest_rows=num_manifest_rows,
        num_recordings=num_recordings,
        num_log_rows=num_log_rows,
        issues_block=issues_block,
    )
    (output_dir / "README_normalized.md").write_text(rendered, encoding="utf-8")


def main() -> None:
    args = parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    reader_metadata_path = Path(args.reader_metadata).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] Loading reader and book metadata...")
    metadata_doc = load_yaml(reader_metadata_path)
    reader_metadata = metadata_doc.get("readers", {})

    readers_rows = []
    for reader_id, meta in reader_metadata.items():
        readers_rows.append(
            {
                "reader_id": reader_id,
                "reader_name": meta.get("reader_name"),
                "gender": meta.get("gender"),
                "audio_quality_groups": "|".join(meta.get("audio_quality_groups", [])),
                "hours_clean": meta.get("hours_clean"),
                "hours_other": meta.get("hours_other"),
                "hours_total": meta.get("hours_total"),
            }
        )
    readers_df = pd.DataFrame(readers_rows, columns=READERS_COLUMNS)

    reader_books_frames = []
    clean_map = dataset_root / "readers_books_clean.txt"
    other_map = dataset_root / "readers_books_other.txt"
    if clean_map.exists():
        reader_books_frames.append(load_reader_books(clean_map, "clean"))
    if other_map.exists():
        reader_books_frames.append(load_reader_books(other_map, "other"))
    reader_books_df = (
        pd.concat(reader_books_frames, ignore_index=True)
        if reader_books_frames
        else pd.DataFrame(columns=READER_BOOKS_COLUMNS)
    )

    bandwidth_path = dataset_root / "books_bandwidth.tsv"
    book_bandwidth_df = (
        load_book_bandwidth(bandwidth_path)
        if bandwidth_path.exists()
        else pd.DataFrame(columns=BOOK_BANDWIDTH_COLUMNS)
    )

    print("[2/5] Discovering manifest files...")
    manifest_files = sorted(dataset_root.glob("*_manifest_*_*.json"))
    print(f"      Found {len(manifest_files)} manifest files")

    recordings_rows: List[Dict] = []
    utterances_rows: List[Dict] = []
    log_rows: List[Dict[str, str]] = []
    total_manifest_rows = 0

    print("[3/5] Parsing manifest rows and validating audio mappings...")
    for manifest_path in tqdm(manifest_files, desc="Manifests", unit="manifest", dynamic_ncols=True):
        parsed_name = parse_manifest_filename(manifest_path)
        if parsed_name is None:
            emit_log_row(
                log_rows,
                level="WARNING",
                manifest_path=str(manifest_path),
                issue_type="manifest_filename_unparsed",
                details="Could not parse manifest naming convention.",
            )
            continue

        reader_id = parsed_name["reader_id"]
        audio_quality = parsed_name["audio_quality"]
        split = parsed_name["split"]

        reader_meta = reader_metadata.get(reader_id)
        if reader_meta is None:
            emit_log_row(
                log_rows,
                level="WARNING",
                reader_id=reader_id,
                audio_quality=audio_quality,
                split=split,
                manifest_path=str(manifest_path),
                issue_type="reader_metadata_missing",
                details="Reader metadata missing from YAML.",
            )
            reader_meta = {
                "reader_name": None,
                "gender": None,
                "hours_clean": None,
                "hours_other": None,
                "hours_total": None,
            }

        with manifest_path.open("r", encoding="utf-8") as f:
            for line_num, raw in enumerate(f, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception as exc:
                    emit_log_row(
                        log_rows,
                        level="ERROR",
                        reader_id=reader_id,
                        audio_quality=audio_quality,
                        split=split,
                        manifest_path=str(manifest_path),
                        issue_type="manifest_json_parse_error",
                        details=f"Line {line_num}: {exc}",
                    )
                    continue

                total_manifest_rows += 1

                audio_filepath_relative = row["audio_filepath"]
                audio_path = dataset_root / audio_filepath_relative

                # audio/<reader_id>_<quality>/<book_id>/<file>.flac
                rel_parts = Path(audio_filepath_relative).parts
                book_id = rel_parts[2] if len(rel_parts) >= 3 else ""

                if not audio_path.exists():
                    emit_log_row(
                        log_rows,
                        level="WARNING",
                        reader_id=reader_id,
                        audio_quality=audio_quality,
                        split=split,
                        book_id=book_id,
                        audio_filepath_relative=audio_filepath_relative,
                        manifest_path=str(manifest_path),
                        issue_type="missing_audio_for_manifest_row",
                        details="Manifest row exists but FLAC file was not found.",
                    )
                    continue

                try:
                    audio_info = read_audio_info(audio_path)
                except Exception as exc:
                    emit_log_row(
                        log_rows,
                        level="ERROR",
                        reader_id=reader_id,
                        audio_quality=audio_quality,
                        split=split,
                        book_id=book_id,
                        audio_filepath_relative=audio_filepath_relative,
                        manifest_path=str(manifest_path),
                        issue_type="audio_read_error",
                        details=str(exc),
                    )
                    continue

                rb_match = None
                if not reader_books_df.empty:
                    rb = reader_books_df[
                        (reader_books_df["reader_id"] == reader_id)
                        & (reader_books_df["audio_quality"] == audio_quality)
                        & (reader_books_df["book_id"] == book_id)
                    ]
                    if not rb.empty:
                        rb_match = True
                    else:
                        emit_log_row(
                            log_rows,
                            level="INFO",
                            reader_id=reader_id,
                            audio_quality=audio_quality,
                            split=split,
                            book_id=book_id,
                            audio_filepath_relative=audio_filepath_relative,
                            manifest_path=str(manifest_path),
                            issue_type="reader_books_mapping_missing",
                            details="Book was not found in readers_books mapping.",
                        )

                bandwidth_row = {}
                if not book_bandwidth_df.empty:
                    bw = book_bandwidth_df[
                        (book_bandwidth_df["reader_id"] == reader_id)
                        & (book_bandwidth_df["book_id"] == book_id)
                        & (book_bandwidth_df["audio_quality"] == audio_quality)
                    ]
                    if not bw.empty:
                        bandwidth_row = bw.iloc[0].to_dict()
                    else:
                        emit_log_row(
                            log_rows,
                            level="INFO",
                            reader_id=reader_id,
                            audio_quality=audio_quality,
                            split=split,
                            book_id=book_id,
                            audio_filepath_relative=audio_filepath_relative,
                            manifest_path=str(manifest_path),
                            issue_type="book_bandwidth_missing",
                            details="No bandwidth metadata found for this reader/book/quality.",
                        )

                filename_stem = Path(audio_filepath_relative).stem
                recording_id = build_recording_id(reader_id, audio_quality, split, book_id, filename_stem)

                text = row.get("text", "")
                text_no_preprocessing = row.get("text_no_preprocessing", "")
                text_normalized = row.get("text_normalized", "")
                text_norm_eval = normalize_text(text)

                recordings_rows.append(
                    {
                        "recording_id": recording_id,
                        "dataset": "Hi Fi TTS",
                        "dataset_id": "hifitts",
                        "reader_id": reader_id,
                        "reader_name": reader_meta.get("reader_name"),
                        "gender": reader_meta.get("gender"),
                        "audio_quality": audio_quality,
                        "split": split,
                        "book_id": book_id,
                        "audio_path": str(audio_path),
                        "audio_filepath_relative": audio_filepath_relative,
                        "sample_rate_hz": audio_info.sample_rate_hz,
                        "duration_sec_audio": round(audio_info.duration_sec, 6),
                        "duration_sec_manifest": row.get("duration"),
                        "num_channels": audio_info.num_channels,
                        "reader_hours_clean": reader_meta.get("hours_clean"),
                        "reader_hours_other": reader_meta.get("hours_other"),
                        "reader_hours_total": reader_meta.get("hours_total"),
                        "book_bandwidth": bandwidth_row.get("book_bandwidth"),
                        "book_bandwidth_comment": bandwidth_row.get("book_bandwidth_comment"),
                        "text_source": "manifest_jsonl",
                        "raw_manifest_path": str(manifest_path),
                        "normalization_status": "ok",
                    }
                )

                utterances_rows.append(
                    {
                        "recording_id": recording_id,
                        "dataset": "Hi Fi TTS",
                        "dataset_id": "hifitts",
                        "reader_id": reader_id,
                        "reader_name": reader_meta.get("reader_name"),
                        "gender": reader_meta.get("gender"),
                        "audio_quality": audio_quality,
                        "split": split,
                        "book_id": book_id,
                        "start_sec": 0.0,
                        "end_sec": round(audio_info.duration_sec, 6),
                        "text": text,
                        "text_no_preprocessing": text_no_preprocessing,
                        "text_normalized": text_normalized,
                        "text_norm_eval": text_norm_eval,
                        "audio_path": str(audio_path),
                        "audio_filepath_relative": audio_filepath_relative,
                        "raw_manifest_path": str(manifest_path),
                    }
                )

    print("[4/5] Writing normalized metadata files...")
    recordings_df = pd.DataFrame(recordings_rows, columns=RECORDINGS_COLUMNS)
    utterances_df = pd.DataFrame(utterances_rows, columns=UTTERANCES_COLUMNS)
    log_df = pd.DataFrame(log_rows, columns=LOG_COLUMNS)

    recordings_df.to_parquet(output_dir / "recordings.parquet", index=False)
    utterances_df.to_parquet(output_dir / "utterances.parquet", index=False)
    readers_df.to_parquet(output_dir / "readers.parquet", index=False)
    reader_books_df.to_parquet(output_dir / "reader_books.parquet", index=False)
    book_bandwidth_df.to_parquet(output_dir / "book_bandwidth.parquet", index=False)
    log_df.to_csv(output_dir / "normalization_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    issues_block = build_issues_block(log_df)
    write_readme(
        output_dir=output_dir,
        dataset_root=dataset_root,
        num_manifest_files=len(manifest_files),
        num_manifest_rows=total_manifest_rows,
        num_recordings=len(recordings_df),
        num_log_rows=len(log_df),
        issues_block=issues_block,
    )

    print("[5/5] Done")
    print(f"Manifest files parsed: {len(manifest_files)}")
    print(f"Manifest rows parsed: {total_manifest_rows}")
    print(f"Recordings written: {len(recordings_df)}")
    print(f"Issues logged: {len(log_df)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
