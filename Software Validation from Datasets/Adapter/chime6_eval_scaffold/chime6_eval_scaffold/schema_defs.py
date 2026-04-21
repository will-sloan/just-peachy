"""Shared schema helpers for normalized CHiME-6 metadata output."""

from __future__ import annotations

from typing import List


SPLITS: List[str] = ["train", "dev", "eval"]

RECORDINGS_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "split",
    "session_id",
    "stream_type",
    "speaker_id_ref",
    "device_id",
    "channel_id",
    "audio_path",
    "sample_rate_hz",
    "duration_sec",
    "num_channels",
    "location_hint",
]

UTTERANCES_COLUMNS: List[str] = [
    "utterance_key",
    "dataset",
    "dataset_id",
    "split",
    "session_id",
    "speaker_id_ref",
    "start_sec",
    "end_sec",
    "duration_sec",
    "text_original",
    "text_norm",
    "ref_device",
    "location",
]

SEGMENTS_COLUMNS: List[str] = [
    "segment_id",
    "dataset",
    "dataset_id",
    "split",
    "session_id",
    "speaker_id_ref",
    "start_sec",
    "end_sec",
    "duration_sec",
    "ref_device",
    "location",
    "has_overlap_candidate",
]

LOG_COLUMNS: List[str] = [
    "level",
    "split",
    "session_id",
    "speaker_id_ref",
    "audio_path",
    "annotation_path",
    "issue_type",
    "details",
]


def build_recording_id(split: str, session_id: str, stream_type: str, speaker_or_device: str, channel_id: str | None = None) -> str:
    if channel_id:
        return f"CHIME6_{split}_{session_id}_{stream_type}_{speaker_or_device}_{channel_id}"
    return f"CHIME6_{split}_{session_id}_{stream_type}_{speaker_or_device}"


def build_utterance_key(split: str, session_id: str, idx: int) -> str:
    return f"CHIME6_{split}_{session_id}_utt_{idx:06d}"


def build_segment_id(split: str, session_id: str, idx: int) -> str:
    return f"CHIME6_{split}_{session_id}_seg_{idx:06d}"
