"""Normalize VOiCES DevKit into metadata-only reference tables.

Updated version includes lightweight terminal progress reporting.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import soundfile as sf
from tqdm import tqdm

from schema_defs import (
    CONDITIONS_COLUMNS,
    LOG_COLUMNS,
    RECORDINGS_COLUMNS,
    SOURCE_MAP_COLUMNS,
    SPEAKERS_COLUMNS,
    UTTERANCES_COLUMNS,
    build_recording_id,
    normalize_speaker_id,
)
from text_normalization import normalize_text


DISTANT_FILENAME_RE = re.compile(
    r"^Lab41-SRI-VOiCES-"
    r"(?P<room>rm\d+)-"
    r"(?P<distractor>[a-z]+)-"
    r"sp(?P<speaker>\d+)-"
    r"ch(?P<chapter>\d+)-"
    r"sg(?P<segment>\d+)-"
    r"mc(?P<mic>\d+)-"
    r"(?P<device>[a-z0-9]+)-"
    r"(?P<position>[a-z0-9]+)-"
    r"dg(?P<degrees>\d+)$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize VOiCES DevKit into metadata tables.")
    parser.add_argument("--dataset-root", required=True, help="Path to raw VOiCES dataset root.")
    parser.add_argument("--output-dir", required=True, help="Directory where normalized outputs will be written.")
    return parser.parse_args()


def emit_log_row(
    rows: List[Dict[str, str]],
    *,
    level: str,
    split: str = "",
    query_name: str = "",
    speaker_id: str = "",
    distant_audio_path: str = "",
    source_audio_path: str = "",
    issue_type: str = "",
    details: str = "",
) -> None:
    rows.append(
        {
            "level": level,
            "split": split,
            "query_name": query_name,
            "speaker_id": speaker_id,
            "distant_audio_path": distant_audio_path,
            "source_audio_path": source_audio_path,
            "issue_type": issue_type,
            "details": details,
        }
    )


def read_audio_info(path: Path) -> tuple[int, float]:
    info = sf.info(str(path))
    return int(info.samplerate), float(info.frames) / float(info.samplerate)


def load_manifest(path: Path, split: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["split"] = split
    return df


def load_filename_transcripts(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_distances(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "distractor 1": "distance_distractor_1",
            "distractor 2": "distance_distractor_2",
            "distractor 3": "distance_distractor_3",
            "floor": "distance_floor",
            "foreground": "distance_foreground",
        }
    )
    return df


def load_quality_metrics(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "pesq nb": "pesq_nb",
            "pesq wb": "pesq_wb",
            "STOI": "stoi",
            "SIIB": "siib",
            "SRMR": "srmr",
        }
    )
    return df


def load_time_values(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Handle duplicate "index,index" header by renaming the second one if present.
    cols = list(df.columns)
    seen = {}
    new_cols = []
    for col in cols:
        count = seen.get(col, 0)
        if count == 0:
            new_cols.append(col)
        else:
            new_cols.append(f"{col}_{count+1}")
        seen[col] = count + 1
    df.columns = new_cols
    return df


def load_speaker_gender_dataset_tbl(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        header = next(f, None)
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                rows.append(
                    {
                        "speaker_id": parts[0],
                        "speaker_id_padded": normalize_speaker_id(parts[0]),
                        "gender": parts[1],
                        "dataset_source": parts[2],
                        "book_id": None,
                        "chapter_id": None,
                    }
                )
    return pd.DataFrame(rows, columns=SPEAKERS_COLUMNS)


def load_speaker_book_chapter_tbl(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        header = next(f, None)
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                rows.append(
                    {
                        "speaker_id": parts[0],
                        "speaker_id_padded": normalize_speaker_id(parts[0]),
                        "gender": None,
                        "dataset_source": None,
                        "book_id": parts[1],
                        "chapter_id": parts[2],
                    }
                )
    return pd.DataFrame(rows, columns=SPEAKERS_COLUMNS)


def load_test_speakers_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    rename_map = {}
    if "Speaker" in df.columns:
        rename_map["Speaker"] = "speaker_id"
    if "Gender" in df.columns:
        rename_map["Gender"] = "gender"
    if "DataSet" in df.columns:
        rename_map["DataSet"] = "dataset_source"
    df = df.rename(columns=rename_map)
    if "speaker_id" not in df.columns:
        return pd.DataFrame(columns=SPEAKERS_COLUMNS)
    df["speaker_id_padded"] = df["speaker_id"].apply(normalize_speaker_id)
    if "book_id" not in df.columns:
        df["book_id"] = None
    if "chapter_id" not in df.columns:
        df["chapter_id"] = None
    return df[[c for c in SPEAKERS_COLUMNS if c in df.columns]].reindex(columns=SPEAKERS_COLUMNS)


def build_issues_block(log_df: pd.DataFrame) -> str:
    if log_df.empty:
        return "- none"
    lines = []
    for _, row in log_df.head(50).iterrows():
        lines.append(
            f"- [{row['level']}] {row['issue_type']} | split={row['split']} "
            f"| query={row['query_name']} | speaker={row['speaker_id']} "
            f"| details={row['details']}"
        )
    if len(log_df) > 50:
        lines.append(f"- ... {len(log_df) - 50} additional issue rows omitted from README")
    return "\n".join(lines)


def write_readme(
    output_dir: Path,
    dataset_root: Path,
    num_manifest_rows: int,
    num_recordings: int,
    num_condition_rows: int,
    num_log_rows: int,
    issues_block: str,
) -> None:
    template_path = Path(__file__).resolve().parent / "README_normalized_template.md"
    template = template_path.read_text(encoding="utf-8")
    rendered = template.format(
        dataset_root=str(dataset_root),
        num_manifest_rows=num_manifest_rows,
        num_recordings=num_recordings,
        num_condition_rows=num_condition_rows,
        num_log_rows=num_log_rows,
        issues_block=issues_block,
    )
    (output_dir / "README_normalized.md").write_text(rendered, encoding="utf-8")


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    devkit_root = dataset_root / "VOiCES_devkit"
    recording_data_root = dataset_root / "recording_data"
    references_root = devkit_root / "references"

    print("[1/5] Loading primary manifests and metadata...")
    train_index = load_manifest(references_root / "train_index.csv", "train")
    test_index = load_manifest(references_root / "test_index.csv", "test")
    manifest_df = pd.concat([train_index, test_index], ignore_index=True)

    filename_transcripts = load_filename_transcripts(references_root / "filename_transcripts")
    distances_df = load_distances(recording_data_root / "distances.csv")
    quality_df = load_quality_metrics(recording_data_root / "quality_metrics.csv")

    time_values_path = references_root / "time_values.csv"
    time_values_df = load_time_values(time_values_path) if time_values_path.exists() else pd.DataFrame()

    speaker_gender_tbl = load_speaker_gender_dataset_tbl(references_root / "Lab41-SRI-VOiCES-speaker-gender-dataset.tbl")
    speaker_book_tbl = load_speaker_book_chapter_tbl(references_root / "Lab41-SRI-VOiCES-speaker-book-chapter.tbl")
    test_speakers_path = references_root / "Test-Set_Speakers.csv"
    test_speakers_df = load_test_speakers_csv(test_speakers_path) if test_speakers_path.exists() else pd.DataFrame(columns=SPEAKERS_COLUMNS)

    speakers_df = pd.concat([speaker_gender_tbl, speaker_book_tbl, test_speakers_df], ignore_index=True)
    if not speakers_df.empty:
        speakers_df = speakers_df.groupby("speaker_id_padded", as_index=False).agg(
            {
                "speaker_id": "first",
                "gender": "first",
                "dataset_source": "first",
                "book_id": "first",
                "chapter_id": "first",
            }
        )
        speakers_df = speakers_df.reindex(columns=SPEAKERS_COLUMNS)

    print(f"      Loaded {len(manifest_df)} manifest rows")

    recordings_rows: List[Dict] = []
    utterances_rows: List[Dict] = []
    conditions_rows: List[Dict] = []
    source_map_rows: List[Dict] = []
    log_rows: List[Dict[str, str]] = []

    duplicate_queries = manifest_df["query_name"].duplicated().sum()
    if duplicate_queries:
        emit_log_row(
            log_rows,
            level="WARNING",
            issue_type="duplicate_query_name",
            details=f"Found {duplicate_queries} duplicated query_name values in combined manifest.",
        )

    print("[2/5] Normalizing manifest rows and validating audio paths...")
    for row in tqdm(manifest_df.to_dict(orient="records"), desc="VOiCES rows", unit="row", dynamic_ncols=True):
        split = str(row["split"])
        query_name = str(row["query_name"])
        speaker_id = str(row["speaker"])
        speaker_id_padded = normalize_speaker_id(speaker_id)

        distant_rel = str(row["filename"])
        source_rel = str(row["source"])
        distant_path = devkit_root / distant_rel
        source_path = devkit_root / source_rel

        if not distant_path.exists():
            emit_log_row(
                log_rows,
                level="WARNING",
                split=split,
                query_name=query_name,
                speaker_id=speaker_id,
                distant_audio_path=str(distant_path),
                source_audio_path=str(source_path),
                issue_type="missing_distant_audio",
                details="Manifest row points to a distant WAV that does not exist.",
            )
            continue

        if not source_path.exists():
            emit_log_row(
                log_rows,
                level="WARNING",
                split=split,
                query_name=query_name,
                speaker_id=speaker_id,
                distant_audio_path=str(distant_path),
                source_audio_path=str(source_path),
                issue_type="missing_source_audio",
                details="Manifest row points to a source WAV that does not exist.",
            )
            continue

        try:
            distant_sr, distant_dur = read_audio_info(distant_path)
            source_sr, source_dur = read_audio_info(source_path)
        except Exception as exc:
            emit_log_row(
                log_rows,
                level="ERROR",
                split=split,
                query_name=query_name,
                speaker_id=speaker_id,
                distant_audio_path=str(distant_path),
                source_audio_path=str(source_path),
                issue_type="audio_read_error",
                details=str(exc),
            )
            continue

        parsed = DISTANT_FILENAME_RE.match(query_name)
        parsed_dict = parsed.groupdict() if parsed else {}

        if parsed is None:
            emit_log_row(
                log_rows,
                level="WARNING",
                split=split,
                query_name=query_name,
                speaker_id=speaker_id,
                distant_audio_path=str(distant_path),
                source_audio_path=str(source_path),
                issue_type="filename_parse_mismatch",
                details="query_name did not match expected distant filename regex.",
            )

        recording_id = build_recording_id(split, query_name)

        transcript_text = str(row["transcript"])
        text_norm = normalize_text(transcript_text)

        room = str(row["room"])
        distractor = str(row["distractor"])
        mic = str(row["mic"])
        degrees = str(row["degrees"])
        chapter_id = str(row["chapter"])
        segment_id = str(row["segment"])
        device = parsed_dict.get("device")
        position = parsed_dict.get("position")

        speaker_meta = {}
        if not speakers_df.empty and speaker_id_padded is not None:
            match = speakers_df[speakers_df["speaker_id_padded"] == speaker_id_padded]
            if not match.empty:
                speaker_meta = match.iloc[0].to_dict()

        recordings_rows.append(
            {
                "recording_id": recording_id,
                "dataset": "VOiCES DevKit",
                "dataset_id": "voices",
                "split": split,
                "query_name": query_name,
                "speaker_id": speaker_id,
                "speaker_id_padded": speaker_id_padded,
                "gender": row.get("gender") if pd.notna(row.get("gender")) else speaker_meta.get("gender"),
                "chapter_id": chapter_id,
                "segment_id": segment_id,
                "room": room,
                "distractor": distractor,
                "mic": mic,
                "device": device,
                "position": position,
                "degrees": degrees,
                "distant_audio_path": str(distant_path),
                "source_audio_path": str(source_path),
                "distant_sample_rate_hz": distant_sr,
                "distant_duration_sec": round(distant_dur, 6),
                "source_sample_rate_hz": source_sr,
                "source_duration_sec": round(source_dur, 6),
                "manifest_noisy_time": row.get("noisy_time"),
                "manifest_source_time": row.get("source_time"),
                "text_source": "train_test_index_csv",
                "normalization_status": "ok",
            }
        )

        utterances_rows.append(
            {
                "recording_id": recording_id,
                "dataset": "VOiCES DevKit",
                "dataset_id": "voices",
                "split": split,
                "query_name": query_name,
                "speaker_id": speaker_id,
                "speaker_id_padded": speaker_id_padded,
                "gender": row.get("gender") if pd.notna(row.get("gender")) else speaker_meta.get("gender"),
                "chapter_id": chapter_id,
                "segment_id": segment_id,
                "room": room,
                "distractor": distractor,
                "mic": mic,
                "device": device,
                "position": position,
                "degrees": degrees,
                "start_sec": 0.0,
                "end_sec": round(distant_dur, 6),
                "text_original": transcript_text,
                "text_norm": text_norm,
                "distant_audio_path": str(distant_path),
                "source_audio_path": str(source_path),
                "text_source": "train_test_index_csv",
            }
        )

    print("[3/5] Joining condition and quality metadata...")
    conditions_df = pd.DataFrame(recordings_rows)[["recording_id", "query_name", "split", "room", "distractor", "mic", "device", "position", "degrees"]].drop_duplicates()
    conditions_df = conditions_df.merge(distances_df, on="query_name", how="left")
    conditions_df = conditions_df.merge(quality_df, on="query_name", how="left")
    conditions_df = conditions_df.reindex(columns=CONDITIONS_COLUMNS)
    conditions_rows = conditions_df.to_dict(orient="records")

    if not time_values_df.empty:
        if "noisy_filename" in time_values_df.columns:
            temp = time_values_df.copy()
            temp["query_name"] = temp["noisy_filename"].astype(str).str.replace(r"\\.wav$", "", regex=True).apply(lambda s: Path(s).stem)
            source_map_df = pd.DataFrame(recordings_rows)[["recording_id", "query_name"]].drop_duplicates().merge(temp, on="query_name", how="left")
            source_map_df = source_map_df.rename(
                columns={
                    "peak cc loc (samples)": "peak_cc_loc_samples",
                    "peak cc loc (seconds)": "peak_cc_loc_seconds",
                    "peak cross corr": "peak_cross_corr",
                    "noisy_time": "noisy_time",
                    "source_time": "source_time",
                    "noisy_filename": "noisy_filename",
                    "source_filename": "source_filename",
                }
            )
            source_map_df = source_map_df.reindex(columns=SOURCE_MAP_COLUMNS)
            source_map_rows = source_map_df.to_dict(orient="records")

    print("[4/5] Writing normalized metadata files...")
    recordings_df = pd.DataFrame(recordings_rows, columns=RECORDINGS_COLUMNS)
    utterances_df = pd.DataFrame(utterances_rows, columns=UTTERANCES_COLUMNS)
    conditions_df = pd.DataFrame(conditions_rows, columns=CONDITIONS_COLUMNS)
    source_map_df = pd.DataFrame(source_map_rows, columns=SOURCE_MAP_COLUMNS)
    log_df = pd.DataFrame(log_rows, columns=LOG_COLUMNS)

    recordings_df.to_parquet(output_dir / "recordings.parquet", index=False)
    utterances_df.to_parquet(output_dir / "utterances.parquet", index=False)
    conditions_df.to_parquet(output_dir / "conditions.parquet", index=False)
    speakers_df.to_parquet(output_dir / "speakers.parquet", index=False)
    source_map_df.to_parquet(output_dir / "source_map.parquet", index=False)
    log_df.to_csv(output_dir / "normalization_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    issues_block = build_issues_block(log_df)
    write_readme(
        output_dir=output_dir,
        dataset_root=dataset_root,
        num_manifest_rows=len(manifest_df),
        num_recordings=len(recordings_df),
        num_condition_rows=len(conditions_df),
        num_log_rows=len(log_df),
        issues_block=issues_block,
    )

    print("[5/5] Done")
    print(f"Manifest rows parsed: {len(manifest_df)}")
    print(f"Recordings written: {len(recordings_df)}")
    print(f"Condition rows written: {len(conditions_df)}")
    print(f"Issues logged: {len(log_df)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
