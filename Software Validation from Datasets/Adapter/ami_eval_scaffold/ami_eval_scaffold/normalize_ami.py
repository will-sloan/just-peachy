"""Normalize AMI Meeting Corpus into metadata-only reference tables."""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import soundfile as sf
from tqdm import tqdm

from schema_defs import (
    LOG_COLUMNS,
    MEETINGS_COLUMNS,
    PARTICIPANTS_COLUMNS,
    RECORDINGS_COLUMNS,
    SEGMENTS_COLUMNS,
    UTTERANCES_COLUMNS,
    WORDS_COLUMNS,
    build_recording_id,
)
from text_normalization import normalize_text

NITE_NS = {"nite": "http://nite.sourceforge.net/"}
WORD_RANGE_RE = re.compile(r"#id\(([^)]+)\)\.\.id\(([^)]+)\)")


@dataclass
class AudioInfo:
    sample_rate_hz: int
    duration_sec: float
    num_channels: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize AMI Meeting Corpus into metadata tables.")
    parser.add_argument("--dataset-root", required=True, help="Path to raw AMI dataset root.")
    parser.add_argument("--output-dir", required=True, help="Directory where normalized outputs will be written.")
    parser.add_argument(
        "--annotation-root-name",
        default="ami_manual_1.6.1",
        help="Annotation root folder name under dataset root.",
    )
    parser.add_argument(
        "--meetings",
        nargs="*",
        default=None,
        help="Optional explicit list of meeting IDs to process. If omitted, process all meetings in meetings.xml.",
    )
    return parser.parse_args()


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
    meeting_id: str = "",
    agent: str = "",
    stream_type: str = "",
    stream_id: str = "",
    source_path: str = "",
    issue_type: str = "",
    details: str = "",
) -> None:
    rows.append(
        {
            "level": level,
            "meeting_id": meeting_id,
            "agent": agent,
            "stream_type": stream_type,
            "stream_id": stream_id,
            "source_path": source_path,
            "issue_type": issue_type,
            "details": details,
        }
    )


def parse_meetings_xml(path: Path) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Dict[str, str]]]]:
    tree = ET.parse(path)
    root = tree.getroot()

    meeting_rows = []
    speaker_map: Dict[str, Dict[str, Dict[str, str]]] = {}

    for meeting_el in root.findall("meeting"):
        meeting_id = meeting_el.attrib.get("observation", "")
        meeting_type = meeting_el.attrib.get("type", "")
        duration = float(meeting_el.attrib.get("duration", "0") or 0)
        visibility = meeting_el.attrib.get("visibility", "")
        seen_type = meeting_el.attrib.get("seen_type", "")

        meeting_rows.append(
            {
                "meeting_id": meeting_id,
                "meeting_type": meeting_type,
                "duration_sec": duration,
                "visibility": visibility,
                "seen_type": seen_type,
            }
        )

        speaker_map[meeting_id] = {}
        for spk_el in meeting_el.findall("speaker"):
            agent = spk_el.attrib.get("nxt_agent", "")
            speaker_map[meeting_id][agent] = {
                "channel": spk_el.attrib.get("channel", ""),
                "global_name": spk_el.attrib.get("global_name", ""),
                "role": spk_el.attrib.get("role", ""),
                "camera": spk_el.attrib.get("camera", ""),
            }

    return pd.DataFrame(meeting_rows, columns=MEETINGS_COLUMNS), speaker_map


def parse_participants_xml(path: Path) -> pd.DataFrame:
    tree = ET.parse(path)
    root = tree.getroot()
    rows = []

    for part_el in root.findall("participant"):
        rows.append(
            {
                "global_name": part_el.attrib.get("global_name", ""),
                "sex": part_el.attrib.get("sex", ""),
                "age_at_collection": part_el.attrib.get("age_at_collection", ""),
                "native_language": part_el.attrib.get("native_language", ""),
                "education": part_el.attrib.get("education", ""),
            }
        )

    return pd.DataFrame(rows, columns=PARTICIPANTS_COLUMNS)


def parse_words_xml(path: Path, meeting_id: str, agent: str, speaker_info: Dict[str, str]) -> Tuple[List[Dict], Dict[str, Dict]]:
    tree = ET.parse(path)
    root = tree.getroot()

    word_rows: List[Dict] = []
    word_lookup: Dict[str, Dict] = {}

    for child in root:
        tag = child.tag.split("}")[-1]
        ref_id = child.attrib.get("{http://nite.sourceforge.net/}id", "") or child.attrib.get("nite:id", "")
        start = child.attrib.get("starttime", "")
        end = child.attrib.get("endtime", "")

        row = {
            "word_ref_id": ref_id,
            "meeting_id": meeting_id,
            "agent": agent,
            "speaker_global_name": speaker_info.get("global_name", ""),
            "speaker_role": speaker_info.get("role", ""),
            "headset_channel": speaker_info.get("channel", ""),
            "word_start_sec": float(start) if start != "" else None,
            "word_end_sec": float(end) if end != "" else None,
            "token_type": tag,
            "word_original": (child.text or "").strip(),
            "word_norm": normalize_text((child.text or "").strip()) if tag == "w" else "",
            "punc_flag": child.attrib.get("punc", ""),
            "source_words_xml": str(path),
        }
        word_rows.append(row)
        word_lookup[ref_id] = row

    return word_rows, word_lookup


def parse_word_range_from_href(href: str) -> Tuple[str, str]:
    match = WORD_RANGE_RE.search(href)
    if not match:
        raise ValueError(f"Could not parse word range from href: {href}")
    return match.group(1), match.group(2)


def collect_segment_text(word_lookup: Dict[str, Dict], start_id: str, end_id: str) -> str:
    keys = list(word_lookup.keys())
    try:
        i0 = keys.index(start_id)
        i1 = keys.index(end_id)
    except ValueError:
        return ""
    selected = keys[i0 : i1 + 1]
    tokens = []
    for wid in selected:
        row = word_lookup[wid]
        if row["token_type"] == "w":
            token = row["word_original"]
            if token:
                tokens.append(token)
    return " ".join(tokens)


def parse_segments_xml(
    path: Path,
    meeting_id: str,
    agent: str,
    speaker_info: Dict[str, str],
    word_lookup: Dict[str, Dict],
) -> List[Dict]:
    tree = ET.parse(path)
    root = tree.getroot()

    segment_rows: List[Dict] = []

    for seg_el in root.findall("segment"):
        seg_id = seg_el.attrib.get("{http://nite.sourceforge.net/}id", "") or seg_el.attrib.get("nite:id", "")
        start = seg_el.attrib.get("transcriber_start", "")
        end = seg_el.attrib.get("transcriber_end", "")
        child_ref = None
        for child in seg_el.findall("nite:child", NITE_NS):
            child_ref = child.attrib.get("href", "")
            break
        if not child_ref:
            continue

        try:
            word_start_id, word_end_id = parse_word_range_from_href(child_ref)
        except Exception:
            word_start_id, word_end_id = "", ""

        text_original = collect_segment_text(word_lookup, word_start_id, word_end_id)
        text_norm = normalize_text(text_original) if text_original else ""

        segment_rows.append(
            {
                "segment_ref_id": seg_id,
                "meeting_id": meeting_id,
                "agent": agent,
                "speaker_global_name": speaker_info.get("global_name", ""),
                "speaker_role": speaker_info.get("role", ""),
                "headset_channel": speaker_info.get("channel", ""),
                "start_sec": float(start) if start != "" else None,
                "end_sec": float(end) if end != "" else None,
                "text_original": text_original,
                "text_norm": text_norm,
                "word_start_id": word_start_id,
                "word_end_id": word_end_id,
                "source_segments_xml": str(path),
                "source_words_xml": str(path).replace(".segments.xml", ".words.xml"),
            }
        )

    return segment_rows


def build_issues_block(log_df: pd.DataFrame) -> str:
    if log_df.empty:
        return "- none"
    lines = []
    for _, row in log_df.head(50).iterrows():
        lines.append(
            f"- [{row['level']}] {row['issue_type']} | meeting={row['meeting_id']} "
            f"| agent={row['agent']} | stream={row['stream_type']}:{row['stream_id']} "
            f"| details={row['details']}"
        )
    if len(log_df) > 50:
        lines.append(f"- ... {len(log_df) - 50} additional issue rows omitted from README")
    return "\n".join(lines)


def write_readme(
    output_dir: Path,
    dataset_root: Path,
    annotation_root: Path,
    num_meetings: int,
    num_recordings: int,
    num_segments: int,
    num_words: int,
    num_log_rows: int,
    issues_block: str,
) -> None:
    template_path = Path(__file__).resolve().parent / "README_normalized_template.md"
    template = template_path.read_text(encoding="utf-8")
    rendered = template.format(
        dataset_root=str(dataset_root),
        annotation_root=str(annotation_root),
        num_meetings=num_meetings,
        num_recordings=num_recordings,
        num_segments=num_segments,
        num_words=num_words,
        num_log_rows=num_log_rows,
        issues_block=issues_block,
    )
    (output_dir / "README_normalized.md").write_text(rendered, encoding="utf-8")


def main() -> None:
    args = parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    annotation_root = dataset_root / args.annotation_root_name
    output_dir.mkdir(parents=True, exist_ok=True)

    meetings_xml = annotation_root / "corpusResources" / "meetings.xml"
    participants_xml = annotation_root / "corpusResources" / "participants.xml"
    words_dir = annotation_root / "words"
    segments_dir = annotation_root / "segments"

    print("[1/5] Loading meeting and participant metadata...")
    meetings_df, speaker_map = parse_meetings_xml(meetings_xml)
    participants_df = parse_participants_xml(participants_xml) if participants_xml.exists() else pd.DataFrame(columns=PARTICIPANTS_COLUMNS)

    meeting_ids = args.meetings if args.meetings else meetings_df["meeting_id"].tolist()
    print(f"      Meetings selected: {len(meeting_ids)}")

    print("[2/5] Discovering audio streams...")
    array_roots = sorted([p for p in dataset_root.iterdir() if p.is_dir() and p.name.startswith("Array1-")])
    headset_root = dataset_root / "headset"

    recordings_rows: List[Dict] = []
    words_rows: List[Dict] = []
    segment_projection_rows: List[Dict] = []
    utterance_rows: List[Dict] = []
    log_rows: List[Dict[str, str]] = []

    meeting_lookup = {row["meeting_id"]: row for _, row in meetings_df.iterrows()}

    def add_recording_row(meeting_id: str, stream_type: str, stream_id: str, audio_path: Path, meeting_row: Dict):
        if not audio_path.exists():
            emit_log_row(
                log_rows,
                level="WARNING",
                meeting_id=meeting_id,
                stream_type=stream_type,
                stream_id=stream_id,
                source_path=str(audio_path),
                issue_type="missing_audio_stream",
                details="Expected audio stream file not found.",
            )
            return None
        try:
            info = read_audio_info(audio_path)
        except Exception as exc:
            emit_log_row(
                log_rows,
                level="ERROR",
                meeting_id=meeting_id,
                stream_type=stream_type,
                stream_id=stream_id,
                source_path=str(audio_path),
                issue_type="audio_read_error",
                details=str(exc),
            )
            return None

        recording_id = build_recording_id(meeting_id, stream_type, stream_id)
        recordings_rows.append(
            {
                "recording_id": recording_id,
                "dataset": "AMI Meeting Corpus",
                "dataset_id": "ami",
                "meeting_id": meeting_id,
                "stream_type": stream_type,
                "stream_id": stream_id,
                "audio_path": str(audio_path),
                "sample_rate_hz": info.sample_rate_hz,
                "duration_sec": round(info.duration_sec, 6),
                "num_channels": info.num_channels,
                "meeting_type": meeting_row.get("meeting_type", ""),
                "visibility": meeting_row.get("visibility", ""),
                "seen_type": meeting_row.get("seen_type", ""),
            }
        )
        return recording_id

    print("[3/5] Parsing words and segments, projecting onto streams...")
    for meeting_id in tqdm(meeting_ids, desc="Meetings", unit="meeting", dynamic_ncols=True):
        meeting_row = meeting_lookup.get(meeting_id)
        if meeting_row is None:
            emit_log_row(
                log_rows,
                level="WARNING",
                meeting_id=meeting_id,
                issue_type="meeting_missing_from_meetings_xml",
                details="Meeting requested but not found in meetings.xml.",
            )
            continue

        farfield_recording_ids = {}
        for array_root in array_roots:
            array_name = array_root.name
            audio_path = array_root / meeting_id / "audio" / f"{meeting_id}.{array_name}.wav"
            rec_id = add_recording_row(meeting_id, "array", array_name, audio_path, meeting_row)
            if rec_id:
                farfield_recording_ids[array_name] = rec_id

        for agent, spk_info in speaker_map.get(meeting_id, {}).items():
            words_xml = words_dir / f"{meeting_id}.{agent}.words.xml"
            segments_xml = segments_dir / f"{meeting_id}.{agent}.segments.xml"

            if not words_xml.exists():
                emit_log_row(
                    log_rows,
                    level="WARNING",
                    meeting_id=meeting_id,
                    agent=agent,
                    source_path=str(words_xml),
                    issue_type="missing_words_xml",
                    details="Expected words XML missing.",
                )
                continue

            if not segments_xml.exists():
                emit_log_row(
                    log_rows,
                    level="WARNING",
                    meeting_id=meeting_id,
                    agent=agent,
                    source_path=str(segments_xml),
                    issue_type="missing_segments_xml",
                    details="Expected segments XML missing.",
                )
                continue

            word_rows_local, word_lookup = parse_words_xml(words_xml, meeting_id, agent, spk_info)
            words_rows.extend(word_rows_local)
            segments_local = parse_segments_xml(segments_xml, meeting_id, agent, spk_info, word_lookup)

            channel = spk_info.get("channel", "")
            headset_stream_id = f"Headset-{channel}" if channel != "" else ""
            headset_audio = headset_root / meeting_id / "audio" / f"{meeting_id}.{headset_stream_id}.wav"
            headset_recording_id = add_recording_row(meeting_id, "headset", headset_stream_id, headset_audio, meeting_row) if headset_stream_id else None

            for seg in segments_local:
                if headset_recording_id:
                    row = {
                        "recording_id": headset_recording_id,
                        "dataset": "AMI Meeting Corpus",
                        "dataset_id": "ami",
                        "stream_type": "headset",
                        "stream_id": headset_stream_id,
                        **seg,
                    }
                    segment_projection_rows.append(row)
                    utterance_rows.append(dict(row))

                for array_name, array_recording_id in farfield_recording_ids.items():
                    row = {
                        "recording_id": array_recording_id,
                        "dataset": "AMI Meeting Corpus",
                        "dataset_id": "ami",
                        "stream_type": "array",
                        "stream_id": array_name,
                        **seg,
                    }
                    segment_projection_rows.append(row)
                    utterance_rows.append(dict(row))

    print("[4/5] Writing normalized metadata files...")
    recordings_df = pd.DataFrame(recordings_rows, columns=RECORDINGS_COLUMNS).drop_duplicates(subset=["recording_id"])
    words_df = pd.DataFrame(words_rows, columns=WORDS_COLUMNS)
    segments_df = pd.DataFrame(segment_projection_rows, columns=SEGMENTS_COLUMNS)
    utterances_df = pd.DataFrame(utterance_rows, columns=UTTERANCES_COLUMNS)
    log_df = pd.DataFrame(log_rows, columns=LOG_COLUMNS)

    recordings_df.to_parquet(output_dir / "recordings.parquet", index=False)
    words_df.to_parquet(output_dir / "words.parquet", index=False)
    segments_df.to_parquet(output_dir / "segments.parquet", index=False)
    utterances_df.to_parquet(output_dir / "utterances.parquet", index=False)
    meetings_df.to_parquet(output_dir / "meetings.parquet", index=False)
    participants_df.to_parquet(output_dir / "participants.parquet", index=False)
    log_df.to_csv(output_dir / "normalization_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    print("[5/5] Done")
    issues_block = build_issues_block(log_df)
    write_readme(
        output_dir=output_dir,
        dataset_root=dataset_root,
        annotation_root=annotation_root,
        num_meetings=len(meeting_ids),
        num_recordings=len(recordings_df),
        num_segments=len(segments_df),
        num_words=len(words_df),
        num_log_rows=len(log_df),
        issues_block=issues_block,
    )

    print(f"Meetings processed: {len(meeting_ids)}")
    print(f"Recording streams written: {len(recordings_df)}")
    print(f"Segment/utterance rows written: {len(segments_df)}")
    print(f"Word rows written: {len(words_df)}")
    print(f"Issues logged: {len(log_df)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
