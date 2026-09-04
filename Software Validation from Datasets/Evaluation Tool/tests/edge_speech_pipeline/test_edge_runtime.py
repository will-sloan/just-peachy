from __future__ import annotations

import json
from pathlib import Path
import threading
import time

import numpy as np

from app.edge_speech_pipeline.audio import AudioJournal
from app.edge_speech_pipeline.config import PipelineConfig
from app.edge_speech_pipeline.contracts import SpatialEvidence
from app.edge_speech_pipeline.speakers import ProfileStore, SpeakerTracker
from app.edge_speech_pipeline.text_format import (
    finalize_punctuation_output,
    format_partial_display,
    prepare_for_punctuation,
)
from app.edge_speech_pipeline.runtime import PipelineEngine


def _read_all(journal: AudioJournal, *, delay_sec: float = 0.0) -> np.ndarray:
    cursor = 0
    blocks = []
    while cursor < journal.committed_samples or not journal.finished:
        block = journal.read(cursor, 733, wait_sec=0.01)
        if block.size:
            blocks.append(block)
            cursor += block.size
            if delay_sec:
                time.sleep(delay_sec)
        elif journal.finished:
            break
    return np.concatenate(blocks) if blocks else np.empty(0, np.float32)


def test_journal_preserves_exact_samples_for_fast_and_slow_consumers(tmp_path: Path) -> None:
    journal = AudioJournal(tmp_path / "audio.pcm16")
    source = np.linspace(-0.8, 0.8, 32_000, dtype=np.float32)
    results: dict[str, np.ndarray] = {}
    fast = threading.Thread(target=lambda: results.setdefault("fast", _read_all(journal)))
    slow = threading.Thread(target=lambda: results.setdefault("slow", _read_all(journal, delay_sec=0.0005)))
    fast.start()
    slow.start()
    for block in np.array_split(source, 137):
        journal.append(block)
    journal.finish()
    fast.join(timeout=5)
    slow.join(timeout=5)
    expected = np.round(np.clip(source, -1.0, 0.999969) * 32768).astype("<i2").astype(np.float32) / 32768
    assert journal.committed_samples == source.size
    assert np.array_equal(results["fast"], expected)
    assert np.array_equal(results["slow"], expected)


def test_frozen_identity_requires_score_margin_and_evidence(tmp_path: Path) -> None:
    config = PipelineConfig(profile_root=tmp_path)
    vector = np.zeros(192, np.float32)
    vector[0] = 1.0
    np.save(tmp_path / "known.npy", vector, allow_pickle=False)
    (tmp_path / "known.json").write_text(
        json.dumps({"profile_id": "known", "display_name": "Known", "backend_id": "redimnet2_b2_fp32"}),
        encoding="utf-8",
    )
    tracker = SpeakerTracker(config, ProfileStore(tmp_path))
    first = tracker.update(vector, 0.5)
    confirmed = tracker.update(vector, 2.5)
    assert first.state == "tentative"
    assert confirmed.state == "confirmed"
    assert confirmed.display_label == "Known"
    assert confirmed.margin is not None and confirmed.margin >= config.identity_margin_threshold


def test_spatial_contract_is_timestamped_and_inactive_by_default() -> None:
    evidence = SpatialEvidence(1.0, 1.5)
    assert evidence.source_clock == "audio_sample_clock"
    assert evidence.provider == "none"
    assert evidence.energy is None
    assert evidence.angle_deg is None


def test_profile_is_invalidated_by_checkpoint_hash(tmp_path: Path) -> None:
    vector = np.zeros(192, np.float32)
    vector[0] = 1.0
    np.save(tmp_path / "profile.npy", vector, allow_pickle=False)
    metadata_path = tmp_path / "profile.json"
    metadata_path.write_text(
        json.dumps(
            {
                "display_name": "Known",
                "backend_id": "redimnet2_b2_fp32",
                "backend_sha256": "old-checkpoint",
            }
        ),
        encoding="utf-8",
    )
    assert ProfileStore(
        tmp_path, expected_backend_sha256="current-checkpoint"
    ).load() == {}


def test_text_normalization_and_punctuation_fallback() -> None:
    assert prepare_for_punctuation("HELLO I AM HERE") == "hello i am here"
    assert format_partial_display("HELLO I AM HERE") == "Hello I am here"
    assert finalize_punctuation_output("Are you ready?", "ARE YOU READY") == "Are you ready?"
    assert finalize_punctuation_output("I am ready", "I AM READY") == "I am ready."
    assert finalize_punctuation_output("What time is dinner,", "WHAT TIME IS DINNER") == "What time is dinner?"
    assert finalize_punctuation_output("Would you like coffee", "WOULD YOU LIKE COFFEE") == "Would you like coffee?"


def test_overlap_transcript_is_explicitly_uncertain(tmp_path: Path) -> None:
    engine = PipelineEngine(
        PipelineConfig(
            session_root=tmp_path / "sessions",
            profile_root=tmp_path / "profiles",
        )
    )
    engine._overlap_active = True
    engine._transcript_event(
        "TWO PEOPLE TALKING",
        1.0,
        final=True,
        utterance=0,
        decode_ms=1.0,
        punctuation={"text": "Two people talking?", "status": "learned"},
    )
    event = engine.events.get()
    assert event.payload["overlap_detected"] is True
    assert event.payload["speaker_state"] == "overlap_uncertain"
    assert "overlapping speaker" in str(event.payload["speaker"])
    assert event.payload["display_text"] == "Two people talking?"
    assert event.payload["text"] == "TWO PEOPLE TALKING"
