"""Shared schema helpers for normalized metadata output."""

from __future__ import annotations

from typing import List


RECORDINGS_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "speaker_id",
    "speaker_code",
    "gender",
    "accent",
    "accent_group",
    "speaker_variant_group",
    "utterance_id",
    "audio_path",
    "sample_rate_hz",
    "duration_sec",
    "num_channels",
    "text_source",
    "raw_transcript_path",
    "normalization_status",
]

UTTERANCES_COLUMNS: List[str] = [
    "recording_id",
    "dataset",
    "dataset_id",
    "speaker_id",
    "speaker_code",
    "gender",
    "accent",
    "accent_group",
    "speaker_variant_group",
    "utterance_id",
    "start_sec",
    "end_sec",
    "text_original",
    "text_norm",
    "text_source",
    "audio_path",
]

LOG_COLUMNS: List[str] = [
    "level",
    "speaker_id",
    "utterance_id",
    "audio_path",
    "transcript_path",
    "issue_type",
    "details",
]


def build_recording_id(dataset_id: str, speaker_code: str, utterance_id: str) -> str:
    return f"{dataset_id.upper()}_{speaker_code}_{utterance_id}"


README_FIELDS = {
    "dataset_name": "CMU Arctic",
    "dataset_id": "cmu_arctic",
    "evaluation_unit": "single utterance file",
    "primary_transcript_source": "per-speaker etc/txt.done.data",
    "global_fallback_source": "cmuarctic_data.txt (optional only)",
}
