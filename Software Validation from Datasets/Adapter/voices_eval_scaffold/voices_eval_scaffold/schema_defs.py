"""Shared schema helpers for normalized VOiCES metadata output."""

from __future__ import annotations

from typing import List


RECORDINGS_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "split",
    "query_name",
    "speaker_id",
    "speaker_id_padded",
    "gender",
    "chapter_id",
    "segment_id",
    "room",
    "distractor",
    "mic",
    "device",
    "position",
    "degrees",
    "distant_audio_path",
    "source_audio_path",
    "distant_sample_rate_hz",
    "distant_duration_sec",
    "source_sample_rate_hz",
    "source_duration_sec",
    "manifest_noisy_time",
    "manifest_source_time",
    "text_source",
    "normalization_status",
]

UTTERANCES_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "split",
    "query_name",
    "speaker_id",
    "speaker_id_padded",
    "gender",
    "chapter_id",
    "segment_id",
    "room",
    "distractor",
    "mic",
    "device",
    "position",
    "degrees",
    "start_sec",
    "end_sec",
    "text_original",
    "text_norm",
    "distant_audio_path",
    "source_audio_path",
    "text_source",
]

CONDITIONS_COLUMNS: List[str] = [
    "recording_id",
    "query_name",
    "split",
    "room",
    "distractor",
    "mic",
    "device",
    "position",
    "degrees",
    "distance_distractor_1",
    "distance_distractor_2",
    "distance_distractor_3",
    "distance_floor",
    "distance_foreground",
    "pesq_nb",
    "pesq_wb",
    "stoi",
    "siib",
    "srmr",
]

SPEAKERS_COLUMNS: List[str] = [
    "speaker_id",
    "speaker_id_padded",
    "gender",
    "dataset_source",
    "book_id",
    "chapter_id",
]

SOURCE_MAP_COLUMNS: List[str] = [
    "recording_id",
    "query_name",
    "noisy_filename",
    "source_filename",
    "peak_cc_loc_samples",
    "peak_cc_loc_seconds",
    "peak_cross_corr",
    "noisy_time",
    "source_time",
]

LOG_COLUMNS: List[str] = [
    "level",
    "split",
    "query_name",
    "speaker_id",
    "distant_audio_path",
    "source_audio_path",
    "issue_type",
    "details",
]


def build_recording_id(split: str, query_name: str) -> str:
    return f"VOICES_{split}_{query_name}"


def normalize_speaker_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    return digits.zfill(4)
