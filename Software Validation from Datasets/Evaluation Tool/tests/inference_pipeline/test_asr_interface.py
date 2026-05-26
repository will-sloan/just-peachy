from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from app.inference_pipeline.asr.base import (
    ASRContext,
    ASRRuntimeStats,
    FixedASR,
    NoOpASR,
    build_asr_from_config,
    normalize_text,
)
from app.inference_pipeline.asr.metrics import (
    consecutive_duplicate_token_rate,
    empty_output_rate,
    hallucinated_output_rate,
    repeated_ngram_rate,
    repeated_word_rate,
)
from app.inference_pipeline.asr.report import summarize_asr_quality, write_asr_report
from app.inference_pipeline.asr.whisper_adapter import WhisperASR, WhisperASRUnavailableError
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import (
    ASRTranscript,
    AudioSegment,
    EvaluationRecord,
    WordTiming,
)
from app.inference_pipeline.dummy_components import DummySpeakerLabeler
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.registry import resolve_components


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"


def audio_segment(path: Path = Path("synthetic.wav")) -> AudioSegment:
    return AudioSegment(
        audio_path=path,
        start_sec=0.25,
        end_sec=1.25,
        sample_rate_hz=16000,
        channel_count=1,
        duration_sec=1.0,
    )


def asr_context(segment: AudioSegment | None = None) -> ASRContext:
    segment = segment or audio_segment()
    return ASRContext(
        recording_id="rec-001",
        utt_id="utt-001",
        source_audio_path=segment.audio_path,
        segment_index=0,
        segment_start_sec=segment.start_sec,
        segment_end_sec=segment.end_sec,
        device="cpu",
        dtype="float32",
        language="en",
    )


def test_fixed_asr_returns_asr_transcript_with_normalized_text() -> None:
    adapter = FixedASR("  Hello   WORLD  ")

    transcript = adapter.transcribe(audio_segment(), asr_context())

    assert isinstance(transcript, ASRTranscript)
    assert transcript.text == "hello world"
    assert adapter.last_raw_text == "  Hello   WORLD  "
    assert adapter.last_normalized_text == "hello world"
    assert transcript.start_sec == pytest.approx(0.25)
    assert transcript.end_sec == pytest.approx(1.25)
    assert adapter.last_runtime_stats is not None


def test_fixed_asr_preserves_word_timestamps_when_provided() -> None:
    words = (
        WordTiming(word="hello", start_sec=0.3, end_sec=0.5, confidence=0.9),
        WordTiming(word="world", start_sec=0.6, end_sec=0.9, confidence=0.8),
    )
    adapter = FixedASR("hello world", words=words)

    transcript = adapter.transcribe(audio_segment(), asr_context())

    assert transcript.words == words


def test_asr_context_preserves_identity_and_segment_timestamps() -> None:
    segment = audio_segment(Path("sample.wav"))
    context = ASRContext.from_record_segment(
        EvaluationRecord(
            recording_id="rec-xyz",
            utt_id="utt-xyz",
            inference_audio_path=Path("sample.wav"),
        ),
        segment,
        segment_index=3,
        device="cpu",
        dtype="float32",
        language="en",
    )

    assert context.recording_id == "rec-xyz"
    assert context.utt_id == "utt-xyz"
    assert context.segment_index == 3
    assert context.segment_start_sec == pytest.approx(0.25)
    assert context.segment_end_sec == pytest.approx(1.25)


def test_no_op_asr_empty_audio_or_silence_is_deterministic(tmp_path: Path) -> None:
    silence_path = tmp_path / "silence.wav"
    sf.write(silence_path, np.zeros(1600, dtype=np.float32), 16000)
    segment = AudioSegment(
        audio_path=silence_path,
        start_sec=0.0,
        end_sec=0.1,
        sample_rate_hz=16000,
        duration_sec=0.1,
    )
    adapter = NoOpASR()

    transcript = adapter.transcribe(segment, asr_context(segment))

    assert transcript.text == ""
    assert transcript.words == ()
    assert adapter.last_runtime_stats is not None
    assert adapter.last_runtime_stats.audio_duration_sec == pytest.approx(0.1)


def test_repetition_and_empty_hallucination_metrics() -> None:
    text = "go go home go go home"

    assert repeated_word_rate(text) == pytest.approx(4 / 6)
    assert repeated_ngram_rate(text, n=2) == pytest.approx(2 / 5)
    assert consecutive_duplicate_token_rate(text) == pytest.approx(2 / 5)
    assert empty_output_rate(["", "hello", "   "]) == pytest.approx(2 / 3)
    assert hallucinated_output_rate(["noise", ""], silence_flags=[True, True]) == pytest.approx(0.5)


def test_runtime_stats_calculate_realtime_factor() -> None:
    stats = ASRRuntimeStats.from_timings(
        model_name="fixed_asr",
        load_sec=0.1,
        inference_sec=0.25,
        audio_duration_sec=1.0,
        device="cpu",
        dtype="float32",
    )

    assert stats.realtime_factor == pytest.approx(0.25)
    assert stats.to_jsonable()["model_name"] == "fixed_asr"


def test_asr_config_can_select_real_and_no_op_backends() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    no_op = PipelineConfig.from_mapping(mapping)
    whisper_mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    whisper_mapping["components"]["asr"] = "components/asr/whisper_tiny.yaml"
    whisper = PipelineConfig.from_mapping(
        whisper_mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )

    no_op_resolved = resolve_components(no_op)
    whisper_resolved = resolve_components(whisper)

    assert no_op_resolved["asr"].adapter_class.__name__ == "NoOpASRAdapter"
    assert isinstance(build_asr_from_config(no_op), NoOpASR)
    assert whisper_resolved["asr"].adapter_class.__name__ == "WhisperTinyASRAdapter"
    assert isinstance(build_asr_from_config(whisper), WhisperASR)


def test_whisper_base_config_resolves_without_model_imports() -> None:
    before_modules = set(sys.modules)
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["asr"] = "components/asr/whisper_base.yaml"
    config = PipelineConfig.from_mapping(mapping, config_dir=CONFIG_ROOT, tool_root=TOOL_ROOT)
    resolved = resolve_components(config)
    after_modules = set(sys.modules)

    assert resolved["asr"].adapter_class.__name__ == "WhisperBaseASRAdapter"
    assert "whisper" not in after_modules - before_modules


def test_whisper_adapter_is_lazy_and_reports_unavailable_without_dependency_or_assets() -> None:
    adapter = WhisperASR({"model_size": "tiny", "allow_model_downloads": False})

    assert adapter.model is None
    try:
        adapter.transcribe(audio_segment(), asr_context())
    except WhisperASRUnavailableError as exc:
        assert "Whisper" in str(exc)
    else:
        assert adapter.model is not None


class StaticAudioReader:
    def __init__(self, duration_sec: float) -> None:
        self.audio = SimpleNamespace(
            audio_path=Path("synthetic.wav"),
            duration_sec=duration_sec,
            sample_rate=16000,
            num_channels=1,
        )

    def load(self, record: EvaluationRecord, run_config=None):
        _ = (record, run_config)
        return self.audio


def test_pipeline_runs_with_asr_base_and_preserves_prediction_identity() -> None:
    record = {
        "recording_id": "rec-001",
        "utt_id": "utt-001",
        "inference_audio_path": "synthetic.wav",
        "start_sec": 0.0,
        "end_sec": 1.0,
        "duration_sec": 1.0,
    }
    pipeline = PipelineRunner(
        audio_reader=StaticAudioReader(1.0),
        asr=FixedASR("Real transcript text"),
        speaker_labeler=DummySpeakerLabeler(),
    )

    output = pipeline.run_one(record, {"runtime": {"precision": "float32"}})

    assert output.recording_id == "rec-001"
    assert output.utt_id == "utt-001"
    assert output.start_sec == pytest.approx(0.0)
    assert output.end_sec == pytest.approx(1.0)
    assert output.text == "real transcript text"
    assert output.runtime_stats is not None
    assert output.runtime_stats.asr_sec is not None
    assert output.runtime_stats.counters == {"asr_segment_count": 1}


def test_asr_quality_report_writer(tmp_path: Path) -> None:
    runtime = ASRRuntimeStats.from_timings(
        model_name="fixed_asr",
        load_sec=0.0,
        inference_sec=0.1,
        audio_duration_sec=1.0,
        device="cpu",
        dtype="float32",
    )
    metrics = summarize_asr_quality(
        ["hello hello", ""],
        silence_flags=[False, True],
        wer=1.0,
        cer=None,
    )

    report_path = write_asr_report(
        tmp_path / "asr_model_report_test.md",
        run_id="test",
        backend_name="fixed_asr",
        whisper_status="not available",
        runtime_stats=runtime,
        quality_metrics=metrics,
        files_changed=["app/inference_pipeline/asr/base.py"],
        test_commands=["python -m pytest tests/inference_pipeline/test_asr_interface.py"],
        smoke_command="direct synthetic smoke",
        runner_contract="recording_id and utt_id are preserved.",
        config_switch_status="dummy and real configs resolve.",
    )

    assert metrics.repeated_word_rate == pytest.approx(0.5)
    assert metrics.empty_output_rate == pytest.approx(0.5)
    assert "M7 - ASR Interface and First ASR Model Adapter" in report_path.read_text(encoding="utf-8")


def test_asr_modules_do_not_import_faster_whisper_at_package_import() -> None:
    before_modules = set(sys.modules)
    importlib.import_module("app.inference_pipeline.asr")
    after_modules = set(sys.modules)

    assert "faster_whisper" not in after_modules - before_modules
