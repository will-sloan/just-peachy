from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import torch

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import AudioSegment, EvaluationRecord
from app.inference_pipeline.speaker_embedding import (
    DeterministicFakeSpeakerEmbedding,
    SpeakerEmbedding,
    SpeakerEmbeddingContext,
    build_speaker_embedding_from_config,
    is_l2_normalized,
    normalize_vector,
    summarize_similarity_distribution,
    vector_l2_norm,
)
from app.inference_pipeline.speaker_embedding.speechbrain_adapter import (
    SpeechBrainECAPAAdapter,
    SpeechBrainUnavailableError,
)
from app.utils.json_utils import read_jsonl


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"


def audio_segment(path: Path = Path("synthetic.wav"), duration_sec: float = 1.0) -> AudioSegment:
    return AudioSegment(
        audio_path=path,
        start_sec=0.25,
        end_sec=0.25 + duration_sec,
        sample_rate_hz=16000,
        channel_count=1,
        duration_sec=duration_sec,
    )


def embedding_context(segment: AudioSegment | None = None) -> SpeakerEmbeddingContext:
    segment = segment or audio_segment()
    return SpeakerEmbeddingContext(
        recording_id="rec-001",
        utt_id="utt-001",
        source_audio_path=segment.audio_path,
        segment_index=0,
        segment_start_sec=segment.start_sec,
        segment_end_sec=segment.end_sec,
        device="cpu",
        dtype="float32",
    )


def write_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 16000) -> Path:
    samples = int(duration_sec * sample_rate)
    time = np.arange(samples, dtype=np.float32) / sample_rate
    waveform = 0.2 * np.sin(2 * np.pi * 220 * time)
    sf.write(path, waveform.astype(np.float32), sample_rate)
    return path


def test_fake_adapter_returns_normalized_serializable_embedding() -> None:
    adapter = DeterministicFakeSpeakerEmbedding(dimension=8, min_duration_sec=0.5)

    embedding = adapter.embed(audio_segment(duration_sec=1.0), embedding_context())

    assert isinstance(embedding, SpeakerEmbedding)
    assert embedding.status == "ok"
    assert embedding.reliable is True
    assert embedding.dimension == 8
    assert embedding.model_name == "fake_speaker_embedding"
    assert embedding.segment_duration_sec == pytest.approx(1.0)
    assert is_l2_normalized(embedding.vector)
    assert embedding.runtime is not None
    assert embedding.runtime.realtime_factor is not None
    restored = SpeakerEmbedding.from_jsonable(json.loads(json.dumps(embedding.to_jsonable())))
    assert restored == embedding


def test_fake_adapter_is_deterministic_for_same_segment_and_context() -> None:
    adapter = DeterministicFakeSpeakerEmbedding(dimension=12, seed="stable")
    segment = audio_segment(duration_sec=1.0)
    context = embedding_context(segment)

    first = adapter.embed(segment, context)
    second = adapter.embed(segment, context)

    assert first.vector == second.vector
    assert first.embedding_id == second.embedding_id


def test_short_segment_is_flagged_without_embedding_vector() -> None:
    adapter = DeterministicFakeSpeakerEmbedding(dimension=8, min_duration_sec=0.75)

    embedding = adapter.embed(audio_segment(duration_sec=0.2), embedding_context())

    assert embedding.status == "too_short"
    assert embedding.reliable is False
    assert embedding.vector == ()
    assert embedding.dimension == 0
    assert embedding.metadata["min_duration_sec"] == pytest.approx(0.75)


def test_context_from_record_segment_preserves_identity_and_timestamps() -> None:
    segment = audio_segment(Path("sample.wav"), duration_sec=1.5)
    record = EvaluationRecord(
        recording_id="rec-xyz",
        utt_id="utt-xyz",
        inference_audio_path=segment.audio_path,
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
    )

    context = SpeakerEmbeddingContext.from_record_segment(
        record,
        segment,
        segment_index=2,
        device="cpu",
        dtype="float32",
    )

    assert context.recording_id == "rec-xyz"
    assert context.utt_id == "utt-xyz"
    assert context.segment_index == 2
    assert context.segment_start_sec == pytest.approx(0.25)
    assert context.segment_end_sec == pytest.approx(1.75)


def test_config_can_select_fake_and_speechbrain_backends_without_eager_speechbrain_import() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["speaker_embedding"] = {
        "name": "fake_speaker_embedding",
        "enabled": True,
        "adapter": "DeterministicFakeSpeakerEmbedding",
        "params": {"dimension": 10, "min_duration_sec": 0.1},
    }
    fake_config = PipelineConfig.from_mapping(mapping)
    fake = build_speaker_embedding_from_config(fake_config)

    before_modules = set(__import__("sys").modules)
    speechbrain_config = PipelineConfig.from_yaml_path(CONFIG_ROOT / "desktop_gpu.yaml")
    speechbrain = build_speaker_embedding_from_config(speechbrain_config)
    after_modules = set(__import__("sys").modules)

    assert isinstance(fake, DeterministicFakeSpeakerEmbedding)
    assert fake.dimension == 10
    assert isinstance(speechbrain, SpeechBrainECAPAAdapter)
    assert "speechbrain" not in after_modules - before_modules


class InjectedEncoder:
    def encode_batch(self, waveform: torch.Tensor) -> torch.Tensor:
        assert waveform.ndim == 2
        return torch.tensor([[[1.0, 2.0, 2.0]]], dtype=torch.float32)


def test_speechbrain_adapter_with_injected_model_outputs_normalized_embedding(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "speaker.wav", duration_sec=1.0)
    segment = AudioSegment(
        audio_path=wav_path,
        start_sec=None,
        end_sec=None,
        sample_rate_hz=16000,
        channel_count=1,
        duration_sec=1.0,
    )
    context = embedding_context(segment)
    adapter = SpeechBrainECAPAAdapter(
        {"embedding_dim": 3, "min_duration_sec": 0.1, "device": "cpu"},
        model=InjectedEncoder(),
    )

    embedding = adapter.embed(segment, context)

    assert embedding.status == "ok"
    assert embedding.dimension == 3
    assert embedding.vector == pytest.approx((1 / 3, 2 / 3, 2 / 3))
    assert vector_l2_norm(embedding.vector) == pytest.approx(1.0)
    assert embedding.sample_rate_hz == 16000
    assert embedding.runtime is not None
    assert embedding.runtime.realtime_factor is not None


def test_speechbrain_adapter_reports_unavailable_without_dependency_or_assets(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "speaker.wav", duration_sec=1.0)
    segment = AudioSegment(audio_path=wav_path, sample_rate_hz=16000, duration_sec=1.0)
    adapter = SpeechBrainECAPAAdapter(
        {
            "allow_model_downloads": False,
            "savedir": str(tmp_path / "missing-assets"),
            "min_duration_sec": 0.1,
        }
    )

    try:
        adapter.embed(segment, embedding_context(segment))
    except SpeechBrainUnavailableError as exc:
        assert "SpeechBrain" in str(exc)
    else:
        assert importlib.util.find_spec("speechbrain") is not None
        assert adapter.model is not None


def test_similarity_distribution_separates_same_and_different_speakers() -> None:
    rows = [
        {"speaker_label": "a", "vector": normalize_vector((1.0, 0.0, 0.0))},
        {"speaker_label": "a", "vector": normalize_vector((1.0, 0.0, 0.0))},
        {"speaker_label": "b", "vector": normalize_vector((0.0, 1.0, 0.0))},
    ]

    distribution = summarize_similarity_distribution(rows)

    assert distribution is not None
    assert distribution.same_speaker_count == 1
    assert distribution.different_speaker_count == 2
    assert distribution.same_speaker_mean == pytest.approx(1.0)
    assert distribution.different_speaker_mean == pytest.approx(0.0)


def test_folder_embedding_script_smoke_writes_jsonl_and_report(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    write_wav(audio_dir / "a1.wav", duration_sec=0.5)
    write_wav(audio_dir / "a2.wav", duration_sec=0.5)
    write_wav(audio_dir / "b1.wav", duration_sec=0.5)
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text(
        "file_name,speaker_label\n"
        "a1.wav,a\n"
        "a2.wav,a\n"
        "b1.wav,b\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "embeddings.jsonl"
    report_path = tmp_path / "embedding_quality_test.md"

    script_path = TOOL_ROOT / "scripts" / "embed_speaker_folder.py"
    spec = importlib.util.spec_from_file_location("embed_speaker_folder", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    exit_code = module.main(
        [
            str(audio_dir),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--labels-csv",
            str(labels_csv),
            "--dimension",
            "8",
            "--min-duration-sec",
            "0.1",
            "--run-id",
            "unit",
        ]
    )

    rows = list(read_jsonl(output_path))
    assert exit_code == 0
    assert len(rows) == 3
    assert all(row["status"] == "ok" for row in rows)
    assert all(row["dimension"] == 8 for row in rows)
    assert "Speaker Embedding Component Report" in report_path.read_text(encoding="utf-8")
