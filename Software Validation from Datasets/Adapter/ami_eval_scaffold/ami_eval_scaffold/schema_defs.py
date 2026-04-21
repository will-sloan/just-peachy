"""Schema helpers for normalized AMI metadata output."""

from __future__ import annotations

from typing import List


RECORDINGS_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "meeting_id",
    "stream_type",
    "stream_id",
    "audio_path",
    "sample_rate_hz",
    "duration_sec",
    "num_channels",
    "meeting_type",
    "visibility",
    "seen_type",
]

SEGMENTS_COLUMNS: List[str] = [
    "segment_ref_id",
    "recording_id",
    "dataset",
    "dataset_id",
    "meeting_id",
    "stream_type",
    "stream_id",
    "agent",
    "speaker_global_name",
    "speaker_role",
    "headset_channel",
    "start_sec",
    "end_sec",
    "text_original",
    "text_norm",
    "word_start_id",
    "word_end_id",
    "source_segments_xml",
    "source_words_xml",
]

UTTERANCES_COLUMNS: List[str] = SEGMENTS_COLUMNS.copy()

WORDS_COLUMNS: List[str] = [
    "word_ref_id",
    "meeting_id",
    "agent",
    "speaker_global_name",
    "speaker_role",
    "headset_channel",
    "word_start_sec",
    "word_end_sec",
    "token_type",
    "word_original",
    "word_norm",
    "punc_flag",
    "source_words_xml",
]

MEETINGS_COLUMNS: List[str] = [
    "meeting_id",
    "meeting_type",
    "duration_sec",
    "visibility",
    "seen_type",
]

PARTICIPANTS_COLUMNS: List[str] = [
    "global_name",
    "sex",
    "age_at_collection",
    "native_language",
    "education",
]

LOG_COLUMNS: List[str] = [
    "level",
    "meeting_id",
    "agent",
    "stream_type",
    "stream_id",
    "source_path",
    "issue_type",
    "details",
]


def build_recording_id(meeting_id: str, stream_type: str, stream_id: str) -> str:
    return f"AMI_{meeting_id}_{stream_type}_{stream_id}"
