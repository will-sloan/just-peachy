"""Shared schema helpers for normalized LibriSpeech metadata output."""

from __future__ import annotations

from typing import List


ASR_SPLITS: List[str] = [
    "dev-clean",
    "dev-other",
    "test-clean",
    "test-other",
    "train-clean-100",
    "train-clean-360",
    "train-other-500",
]

RECORDINGS_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "split",
    "subset_group",
    "speaker_id",
    "chapter_id",
    "utterance_id",
    "audio_path",
    "sample_rate_hz",
    "duration_sec",
    "num_channels",
    "speaker_sex",
    "speaker_name",
    "speaker_minutes",
    "speaker_subset",
    "chapter_minutes",
    "chapter_subset",
    "project_id",
    "book_id",
    "chapter_title",
    "project_title",
    "book_title",
    "book_authors",
    "text_source",
    "raw_transcript_path",
    "normalization_status",
]

UTTERANCES_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "split",
    "subset_group",
    "speaker_id",
    "chapter_id",
    "utterance_id",
    "start_sec",
    "end_sec",
    "text_original",
    "text_norm",
    "audio_path",
    "text_source",
]

SPEAKERS_COLUMNS: List[str] = [
    "speaker_id",
    "speaker_sex",
    "speaker_subset",
    "speaker_minutes",
    "speaker_name",
]

CHAPTERS_COLUMNS: List[str] = [
    "chapter_id",
    "speaker_id",
    "chapter_minutes",
    "chapter_subset",
    "project_id",
    "book_id",
    "chapter_title",
    "project_title",
]

BOOKS_COLUMNS: List[str] = [
    "book_id",
    "book_title",
    "book_authors",
]

LOG_COLUMNS: List[str] = [
    "level",
    "split",
    "speaker_id",
    "chapter_id",
    "utterance_id",
    "audio_path",
    "transcript_path",
    "issue_type",
    "details",
]


def build_recording_id(speaker_id: str, chapter_id: str, utterance_id: str) -> str:
    return f"LIBRISPEECH_{speaker_id}_{chapter_id}_{utterance_id}"
