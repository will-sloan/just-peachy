"""Normalize LibriSpeech into metadata-only reference tables.

Updated version with lightweight progress reporting suitable for terminal/Anaconda Prompt.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import soundfile as sf
from tqdm import tqdm

from schema_defs import (
    ASR_SPLITS,
    BOOKS_COLUMNS,
    CHAPTERS_COLUMNS,
    LOG_COLUMNS,
    RECORDINGS_COLUMNS,
    SPEAKERS_COLUMNS,
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
    parser = argparse.ArgumentParser(description="Normalize LibriSpeech into metadata tables.")
    parser.add_argument("--dataset-root", required=True, help="Path to raw LibreSpeech dataset root.")
    parser.add_argument("--output-dir", required=True, help="Directory where normalized outputs will be written.")
    return parser.parse_args()


def parse_pipe_table(path: Path, expected_min_fields: int) -> List[List[str]]:
    rows: List[List[str]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < expected_min_fields:
                continue
            rows.append(parts)
    return rows


def load_speakers(path: Path) -> pd.DataFrame:
    rows = []
    for parts in parse_pipe_table(path, 5):
        rows.append(
            {
                "speaker_id": parts[0],
                "speaker_sex": parts[1],
                "speaker_subset": parts[2],
                "speaker_minutes": float(parts[3]) if parts[3] else None,
                "speaker_name": parts[4],
            }
        )
    return pd.DataFrame(rows, columns=SPEAKERS_COLUMNS)


def load_chapters(path: Path) -> pd.DataFrame:
    rows = []
    for parts in parse_pipe_table(path, 8):
        rows.append(
            {
                "chapter_id": parts[0],
                "speaker_id": parts[1],
                "chapter_minutes": float(parts[2]) if parts[2] else None,
                "chapter_subset": parts[3],
                "project_id": parts[4],
                "book_id": parts[5],
                "chapter_title": parts[6],
                "project_title": parts[7],
            }
        )
    return pd.DataFrame(rows, columns=CHAPTERS_COLUMNS)


def load_books(path: Path) -> pd.DataFrame:
    rows = []
    for parts in parse_pipe_table(path, 3):
        rows.append(
            {
                "book_id": parts[0],
                "book_title": parts[1],
                "book_authors": parts[2],
            }
        )
    return pd.DataFrame(rows, columns=BOOKS_COLUMNS)


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
    split: str = "",
    speaker_id: str = "",
    chapter_id: str = "",
    utterance_id: str = "",
    audio_path: str = "",
    transcript_path: str = "",
    issue_type: str = "",
    details: str = "",
) -> None:
    rows.append(
        {
            "level": level,
            "split": split,
            "speaker_id": speaker_id,
            "chapter_id": chapter_id,
            "utterance_id": utterance_id,
            "audio_path": audio_path,
            "transcript_path": transcript_path,
            "issue_type": issue_type,
            "details": details,
        }
    )


def parse_transcript_file(path: Path) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise ValueError(f"Could not parse transcript line at {path}:{lineno}: {raw!r}")
            rows.append((parts[0], parts[1]))
    return rows


def subset_group_from_split(split_name: str) -> str:
    return "clean" if "clean" in split_name else "other"


def build_issues_block(log_df: pd.DataFrame) -> str:
    if log_df.empty:
        return "- none"
    lines = []
    for _, row in log_df.head(50).iterrows():
        lines.append(
            f"- [{row['level']}] {row['issue_type']} | split={row['split']} "
            f"| speaker={row['speaker_id']} | chapter={row['chapter_id']} "
            f"| utt={row['utterance_id']} | details={row['details']}"
        )
    if len(log_df) > 50:
        lines.append(f"- ... {len(log_df) - 50} additional issue rows omitted from README")
    return "\n".join(lines)


def write_readme(
    output_dir: Path,
    dataset_root: Path,
    num_splits: int,
    num_transcript_rows: int,
    num_recordings: int,
    num_log_rows: int,
    issues_block: str,
) -> None:
    template_path = Path(__file__).resolve().parent / "README_normalized_template.md"
    template = template_path.read_text(encoding="utf-8")
    included_splits_block = "\n".join([f"- `{s}`" for s in ASR_SPLITS])
    excluded_folders_block = "\n".join([
        "- `intro-disclaimers`",
        "- `original-books`",
        "- `original-mp3`",
        "- `raw-metadata`",
    ])
    rendered = template.format(
        dataset_root=str(dataset_root),
        included_splits_block=included_splits_block,
        excluded_folders_block=excluded_folders_block,
        num_splits=num_splits,
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
    output_dir.mkdir(parents=True, exist_ok=True)

    recordings_rows: List[Dict] = []
    utterances_rows: List[Dict] = []
    log_rows: List[Dict[str, str]] = []

    speakers_df: Optional[pd.DataFrame] = None
    chapters_df: Optional[pd.DataFrame] = None
    books_df: Optional[pd.DataFrame] = None

    total_transcript_rows = 0
    included_split_count = 0

    print("[1/5] Discovering included ASR splits...")
    split_infos = []
    for split in ASR_SPLITS:
        split_root = dataset_root / split
        corpus_root = split_root / "LibriSpeech" / split
        metadata_root = split_root / "LibriSpeech"
        split_infos.append((split, split_root, corpus_root, metadata_root))
    available_splits = [s for s, _, c, _ in split_infos if c.exists()]
    print(f"      Found {len(available_splits)} included splits")

    print("[2/5] Loading shared metadata tables...")
    for split, _, corpus_root, metadata_root in split_infos:
        if corpus_root.exists():
            speakers_path = metadata_root / "SPEAKERS.TXT"
            chapters_path = metadata_root / "CHAPTERS.TXT"
            books_path = metadata_root / "BOOKS.TXT"
            if speakers_df is None and speakers_path.exists():
                speakers_df = load_speakers(speakers_path)
            if chapters_df is None and chapters_path.exists():
                chapters_df = load_chapters(chapters_path)
            if books_df is None and books_path.exists():
                books_df = load_books(books_path)
            break

    print("[3/5] Parsing transcript files and validating audio mappings...")
    for split, split_root, corpus_root, metadata_root in tqdm(
        split_infos, desc="Splits", unit="split", dynamic_ncols=True
    ):
        if not corpus_root.exists():
            emit_log_row(
                log_rows,
                level="WARNING",
                split=split,
                issue_type="missing_split_root",
                details=f"Expected split root not found: {corpus_root}",
            )
            continue

        included_split_count += 1
        transcript_files = sorted(corpus_root.rglob("*.trans.txt"))

        for transcript_path in tqdm(
            transcript_files,
            desc=f"{split} transcripts",
            unit="file",
            leave=False,
            dynamic_ncols=True,
        ):
            chapter_dir = transcript_path.parent
            chapter_id = chapter_dir.name
            speaker_id = chapter_dir.parent.name

            try:
                transcript_rows = parse_transcript_file(transcript_path)
            except Exception as exc:
                emit_log_row(
                    log_rows,
                    level="ERROR",
                    split=split,
                    speaker_id=speaker_id,
                    chapter_id=chapter_id,
                    transcript_path=str(transcript_path),
                    issue_type="transcript_parse_error",
                    details=str(exc),
                )
                continue

            total_transcript_rows += len(transcript_rows)
            transcript_ids = {u for u, _ in transcript_rows}
            flac_files = {p.stem: p for p in sorted(chapter_dir.glob("*.flac"))}

            speaker_meta = {}
            if speakers_df is not None:
                speaker_match = speakers_df[speakers_df["speaker_id"] == speaker_id]
                if not speaker_match.empty:
                    speaker_meta = speaker_match.iloc[0].to_dict()

            chapter_meta = {}
            if chapters_df is not None:
                chapter_match = chapters_df[chapters_df["chapter_id"] == chapter_id]
                if not chapter_match.empty:
                    chapter_meta = chapter_match.iloc[0].to_dict()

            book_meta = {}
            if books_df is not None and chapter_meta.get("book_id"):
                book_match = books_df[books_df["book_id"] == chapter_meta["book_id"]]
                if not book_match.empty:
                    book_meta = book_match.iloc[0].to_dict()

            for utterance_id, transcript_text in transcript_rows:
                audio_path = flac_files.get(utterance_id)

                if audio_path is None:
                    emit_log_row(
                        log_rows,
                        level="WARNING",
                        split=split,
                        speaker_id=speaker_id,
                        chapter_id=chapter_id,
                        utterance_id=utterance_id,
                        transcript_path=str(transcript_path),
                        issue_type="missing_audio_for_transcript",
                        details="Transcript row exists but matching FLAC was not found.",
                    )
                    continue

                try:
                    audio_info = read_audio_info(audio_path)
                except Exception as exc:
                    emit_log_row(
                        log_rows,
                        level="ERROR",
                        split=split,
                        speaker_id=speaker_id,
                        chapter_id=chapter_id,
                        utterance_id=utterance_id,
                        audio_path=str(audio_path),
                        transcript_path=str(transcript_path),
                        issue_type="audio_read_error",
                        details=str(exc),
                    )
                    continue

                recording_id = build_recording_id(speaker_id, chapter_id, utterance_id)
                text_norm = normalize_text(transcript_text)

                recordings_rows.append(
                    {
                        "recording_id": recording_id,
                        "dataset": "LibriSpeech",
                        "dataset_id": "librispeech",
                        "split": split,
                        "subset_group": subset_group_from_split(split),
                        "speaker_id": speaker_id,
                        "chapter_id": chapter_id,
                        "utterance_id": utterance_id,
                        "audio_path": str(audio_path),
                        "sample_rate_hz": audio_info.sample_rate_hz,
                        "duration_sec": round(audio_info.duration_sec, 6),
                        "num_channels": audio_info.num_channels,
                        "speaker_sex": speaker_meta.get("speaker_sex"),
                        "speaker_name": speaker_meta.get("speaker_name"),
                        "speaker_minutes": speaker_meta.get("speaker_minutes"),
                        "speaker_subset": speaker_meta.get("speaker_subset"),
                        "chapter_minutes": chapter_meta.get("chapter_minutes"),
                        "chapter_subset": chapter_meta.get("chapter_subset"),
                        "project_id": chapter_meta.get("project_id"),
                        "book_id": chapter_meta.get("book_id"),
                        "chapter_title": chapter_meta.get("chapter_title"),
                        "project_title": chapter_meta.get("project_title"),
                        "book_title": book_meta.get("book_title"),
                        "book_authors": book_meta.get("book_authors"),
                        "text_source": "chapter_transcript",
                        "raw_transcript_path": str(transcript_path),
                        "normalization_status": "ok",
                    }
                )

                utterances_rows.append(
                    {
                        "recording_id": recording_id,
                        "dataset": "LibriSpeech",
                        "dataset_id": "librispeech",
                        "split": split,
                        "subset_group": subset_group_from_split(split),
                        "speaker_id": speaker_id,
                        "chapter_id": chapter_id,
                        "utterance_id": utterance_id,
                        "start_sec": 0.0,
                        "end_sec": round(audio_info.duration_sec, 6),
                        "text_original": transcript_text,
                        "text_norm": text_norm,
                        "audio_path": str(audio_path),
                        "text_source": "chapter_transcript",
                    }
                )

            for utterance_stem, audio_path in flac_files.items():
                if utterance_stem not in transcript_ids:
                    emit_log_row(
                        log_rows,
                        level="WARNING",
                        split=split,
                        speaker_id=speaker_id,
                        chapter_id=chapter_id,
                        utterance_id=utterance_stem,
                        audio_path=str(audio_path),
                        transcript_path=str(transcript_path),
                        issue_type="missing_transcript_for_audio",
                        details="FLAC exists without transcript row.",
                    )

    print("[4/5] Writing normalized metadata files...")
    recordings_df = pd.DataFrame(recordings_rows, columns=RECORDINGS_COLUMNS)
    utterances_df = pd.DataFrame(utterances_rows, columns=UTTERANCES_COLUMNS)
    log_df = pd.DataFrame(log_rows, columns=LOG_COLUMNS)

    recordings_df.to_parquet(output_dir / "recordings.parquet", index=False)
    utterances_df.to_parquet(output_dir / "utterances.parquet", index=False)
    log_df.to_csv(output_dir / "normalization_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    if speakers_df is None:
        speakers_df = pd.DataFrame(columns=SPEAKERS_COLUMNS)
    if chapters_df is None:
        chapters_df = pd.DataFrame(columns=CHAPTERS_COLUMNS)
    if books_df is None:
        books_df = pd.DataFrame(columns=BOOKS_COLUMNS)

    speakers_df.to_parquet(output_dir / "speakers.parquet", index=False)
    chapters_df.to_parquet(output_dir / "chapters.parquet", index=False)
    books_df.to_parquet(output_dir / "books.parquet", index=False)

    issues_block = build_issues_block(log_df)
    write_readme(
        output_dir=output_dir,
        dataset_root=dataset_root,
        num_splits=included_split_count,
        num_transcript_rows=total_transcript_rows,
        num_recordings=len(recordings_df),
        num_log_rows=len(log_df),
        issues_block=issues_block,
    )

    print("[5/5] Done")
    print(f"Included splits processed: {included_split_count}")
    print(f"Transcript rows parsed: {total_transcript_rows}")
    print(f"Recordings written: {len(recordings_df)}")
    print(f"Issues logged: {len(log_df)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
