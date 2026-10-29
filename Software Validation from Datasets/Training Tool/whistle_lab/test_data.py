"""Coverage, audio-boundary, and recovery-plan contracts; run pytest test_data.py."""
import numpy as np
import pandas as pd
import pytest
from common import CONFIG, audio_path
from data import BatchLoader, capacities, clean_text, load_audio, plan_batches


def test_full_coverage_and_resume_order():
    frame = pd.DataFrame({"audio_capacity": [5] * 19 + [150] * 3, "token_capacity": [32] * 19 + [512] * 3})
    plan = plan_batches(frame, 0)
    indices = np.concatenate([item[0] for item in plan])
    assert sorted(indices.tolist()) == list(range(len(frame)))
    assert any(len(item[0]) < item[3] for item in plan)
    rebuilt = plan_batches(frame, 0)
    for first, second in zip(plan[2:], rebuilt[2:]):
        np.testing.assert_array_equal(first[0], second[0])
        assert first[1:] == second[1:]


def test_long_records_never_silently_truncated():
    assert capacities(128.4, 740) == (150, 1024)
    assert capacities(5.001, 20) == (10, 32)
    assert capacities(5.0, 20) == (10, 32)
    with pytest.raises(ValueError):
        capacities(151, 10)
    with pytest.raises(ValueError):
        capacities(5, 1100)


def test_text_keeps_punctuation_and_handles_known_annotation_issues():
    assert clean_text("Hello, world!\tmetadata\nmore", "common_voice", "HELLO WORLD") == "Hello, world!"
    assert clean_text("...", "ami", "") == ""
    assert clean_text("[laughs] Yes .", "chime6", "LAUGHS YES") == "Yes."


def test_partial_batch_preserves_audio_and_masks_padding(monkeypatch):
    import data
    frame = pd.DataFrame([{"tokens": [2, 8192, 12, 1], "sample_weight": 0.5, "source_registry_row_id": "fixture"}])
    audio = np.arange(1600, dtype=np.float32) / 1600
    monkeypatch.setattr(data, "load_audio", lambda row: audio)
    loader = BatchLoader(frame, 1)
    wav, lengths, tokens, weights = loader.batch((np.array([0]), 5, 32, 4))
    loader.close()
    np.testing.assert_array_equal(wav[0, :1600], audio)
    np.testing.assert_array_equal(weights, [0.5, 0, 0, 0])
    assert lengths[0] == 1600
    assert tokens[0, 3] == 1


def test_manifest_selection_and_mixture():
    assert len(CONFIG["training_manifests"]) == 4
    assert abs(sum(CONFIG["dataset_weights"].values()) - 1) < 1e-12
    assert "cmu_relaxed_exploratory_train.parquet" not in CONFIG["training_manifests"]


def test_existing_whole_mp3_with_estimated_duration():
    # Reference the existing dataset; never copy Common Voice audio into Git.
    relative = "datasets/common_voice/english/cv-corpus-26.0-2026-06-12/prepared/en/clips/common_voice_en_21852518.mp3"
    if not audio_path("JP_TRAINING_ROOT", relative).exists():
        pytest.skip("Local Common Voice regression clip is not installed")
    samples = load_audio({"audio_root_id": "JP_TRAINING_ROOT", "audio_relative_path": relative,
                          "start_sec": 0., "end_sec": 8.052993197278912,
                          "source_registry_row_id": "common_voice_en_21852518.mp3"})
    # Both independent decoders produced 352512 source frames at 44100 Hz.
    assert len(samples) == round(352512 * 16000 / 44100)
    assert np.isfinite(samples).all()


def test_segment_beyond_available_wav_still_fails(tmp_path, monkeypatch):
    import data
    import soundfile as sf
    path = tmp_path / "short.wav"
    sf.write(path, np.zeros(1600, np.float32), 16000)
    monkeypatch.setattr(data, "audio_path", lambda *_: path)
    with pytest.raises(ValueError, match="Invalid segment bounds"):
        load_audio({"audio_root_id": "fixture", "audio_relative_path": "short.wav",
                    "start_sec": 0., "end_sec": .2, "source_registry_row_id": "fixture"})
