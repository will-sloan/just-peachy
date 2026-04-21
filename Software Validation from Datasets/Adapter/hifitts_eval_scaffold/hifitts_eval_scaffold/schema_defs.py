"""Shared schema helpers for normalized Hi Fi TTS metadata output."""

from __future__ import annotations

from typing import List


RECORDINGS_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "reader_id",
    "reader_name",
    "gender",
    "audio_quality",
    "split",
    "book_id",
    "audio_path",
    "audio_filepath_relative",
    "sample_rate_hz",
    "duration_sec_audio",
    "duration_sec_manifest",
    "num_channels",
    "reader_hours_clean",
    "reader_hours_other",
    "reader_hours_total",
    "book_bandwidth",
    "book_bandwidth_comment",
    "text_source",
    "raw_manifest_path",
    "normalization_status",
]

UTTERANCES_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "reader_id",
    "reader_name",
    "gender",
    "audio_quality",
    "split",
    "book_id",
    "start_sec",
    "end_sec",
    "text",
    "text_no_preprocessing",
    "text_normalized",
    "text_norm_eval",
    "audio_path",
    "audio_filepath_relative",
    "raw_manifest_path",
]

READERS_COLUMNS: List[str] = [
    "reader_id",
    "reader_name",
    "gender",
    "audio_quality_groups",
    "hours_clean",
    "hours_other",
    "hours_total",
]

READER_BOOKS_COLUMNS: List[str] = [
    "audio_quality",
    "reader_id",
    "book_id",
]

BOOK_BANDWIDTH_COLUMNS: List[str] = [
    "reader_id",
    "book_id",
    "audio_quality",
    "book_bandwidth",
    "book_bandwidth_comment",
]

LOG_COLUMNS: List[str] = [
    "level",
    "reader_id",
    "audio_quality",
    "split",
    "book_id",
    "audio_filepath_relative",
    "manifest_path",
    "issue_type",
    "details",
]


def build_recording_id(reader_id: str, audio_quality: str, split: str, book_id: str, filename_stem: str) -> str:
    return f"HIFITTS_{reader_id}_{audio_quality}_{split}_{book_id}_{filename_stem}"
