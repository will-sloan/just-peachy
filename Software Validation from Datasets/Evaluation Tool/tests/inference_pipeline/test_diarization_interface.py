from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.inference_pipeline.asr.base import FixedASR
from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import EvaluationRecord, SpeechRegion
from app.inference_pipeline.diarization import (
    DiarizationUnavailableError,
    FixedDiarizer,
    NoOpDiarizer,
    PyannoteCommunityDiarizer,
    PyannoteDiarizationUnavailableError,
    SpeakerTurnRegion,
    build_diarizer_from_config,
    component_report_path,
    diarization_error_rate,
    jaccard_error_rate,
    mark_overlapping_turns,
    named_speaker_false_assignment_rate,
    summarize_diarization_baseline,
    write_diarization_report,
    write_turns_jsonable,
)
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.registry import resolve_components
from app.inference_pipeline.segmentation.vad_chunker import VADChunker
from app.inference_pipeline.vad.base import FixedVAD


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"


class StaticAudioReader:
    def __init__(self, duration_sec: float = 2.0) -> None:
        self.audio = SimpleNamespace(
            audio_path=Path("synthetic.wav"),
            duration_sec=duration_sec,
            sample_rate=16000,
            num_channels=1,
        )

    def load(self, record: EvaluationRecord, run_config=None):
        _ = (record, run_config)
        return self.audio


class FakeTurn:
    def __init__(self, start: float, end: float) -> None:
        self.start = start
        self.end = end


class FakeAnnotation:
    def itertracks(self, yield_label: bool = False):
        assert yield_label is True
        yield FakeTurn(0.0, 0.8), "track-a", "Alice"
        yield FakeTurn(0.6, 1.2), "track-b", "Bob"


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def __call__(self, audio_input, **kwargs):
        self.calls.append((audio_input, kwargs))
        return FakeAnnotation()


def cpu_smoke_mapping() -> dict[str, object]:
    return PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()


def turns(*rows: tuple[float, float, str]) -> list[SpeakerTurnRegion]:
    return [
        SpeakerTurnRegion(
            start_sec=start,
            end_sec=end,
            speaker_turn_label=label,
        )
        for start, end, label in rows
    ]


def test_diarization_imports_without_pyannote_side_effects() -> None:
    before_modules = set(sys.modules)
    __import__("app.inference_pipeline.diarization.base")
    after_modules = set(sys.modules)

    assert not any(name.startswith("pyannote") for name in after_modules - before_modules)


def test_speaker_turn_region_is_anonymous_and_json_safe() -> None:
    turn = SpeakerTurnRegion(
        start_sec=0.1,
        end_sec=0.5,
        speaker_turn_label="speaker_00",
        confidence=0.9,
        is_overlap=True,
    )
    region = turn.to_speech_region()

    assert region == SpeechRegion(
        start_sec=0.1,
        end_sec=0.5,
        confidence=0.9,
        channel_index=None,
        label="diarization:speaker_00",
    )
    assert json.dumps(turn.to_jsonable())


def test_no_op_and_fixed_diarizers_are_deterministic() -> None:
    expected = turns((0.0, 1.0, "speaker_00"))

    assert NoOpDiarizer().diarize(object()) == []
    assert FixedDiarizer(expected).diarize(object()) == expected
    assert write_turns_jsonable(expected) == [expected[0].to_jsonable()]


def test_diarization_disabled_by_default_config() -> None:
    config = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml")
    resolved = resolve_components(config)

    assert resolved["diarization"].adapter_class.__name__ == "DisabledComponentAdapter"
    assert build_diarizer_from_config(config) is None


def test_pyannote_component_can_be_resolved_without_loading_model() -> None:
    mapping = cpu_smoke_mapping()
    mapping["components"]["diarization"] = {
        "name": "pyannote_community",
        "enabled": True,
        "adapter": "PyannoteCommunityDiarizer",
        "params": {
            "model_source": "pyannote/speaker-diarization-community-1",
            "allow_model_downloads": False,
            "cache_dir": "models/cache/pyannote",
        },
    }

    config = PipelineConfig.from_mapping(mapping)
    resolved = resolve_components(config)
    diarizer = build_diarizer_from_config(config)

    assert resolved["diarization"].adapter_class.__name__ == (
        "PyannoteCommunityDiarizationAdapter"
    )
    assert isinstance(diarizer, PyannoteCommunityDiarizer)


def test_pyannote_component_file_loads_by_reference() -> None:
    mapping = cpu_smoke_mapping()
    mapping["components"]["diarization"] = "components/diarization/pyannote_community.yaml"

    config = PipelineConfig.from_mapping(
        mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )
    resolved = resolve_components(config)

    assert resolved["diarization"].enabled is False
    assert resolved["diarization"].adapter_class.__name__ == "DisabledComponentAdapter"


def test_pyannote_adapter_maps_backend_labels_to_anonymous_turns() -> None:
    fake_pipeline = FakePipeline()
    diarizer = PyannoteCommunityDiarizer(
        {
            "model_source": "local-pyannote",
            "min_turn_sec": 0.05,
            "allow_model_downloads": False,
        },
        pipeline=fake_pipeline,
    )

    result = diarizer.diarize(SimpleNamespace(audio_path=Path("meeting.wav")))

    assert [turn.speaker_turn_label for turn in result] == ["speaker_00", "speaker_01"]
    assert all(turn.speaker_turn_label not in {"Alice", "Bob"} for turn in result)
    assert [turn.is_overlap for turn in result] == [True, True]
    assert fake_pipeline.calls == [({"audio": "meeting.wav"}, {})]


def test_pyannote_adapter_reports_unavailable_without_optional_dependency() -> None:
    diarizer = PyannoteCommunityDiarizer(
        {
            "model_source": "pyannote/speaker-diarization-community-1",
            "allow_model_downloads": False,
            "cache_dir": "models/cache/pyannote",
        }
    )

    try:
        diarizer.diarize(SimpleNamespace(audio_path=Path("meeting.wav")))
    except PyannoteDiarizationUnavailableError as exc:
        assert "pyannote" in str(exc).lower()
    else:
        pytest.skip("pyannote and local model assets are available in this environment")


def test_metrics_compute_der_jer_overlap_and_named_false_assignment() -> None:
    reference = turns((0.0, 1.0, "ref_a"), (1.0, 2.0, "ref_b"))
    predicted = turns((0.0, 1.0, "speaker_00"), (1.0, 2.0, "speaker_01"))

    assert diarization_error_rate(predicted, reference) == pytest.approx(0.0)
    assert jaccard_error_rate(predicted, reference) == pytest.approx(0.0)
    assert named_speaker_false_assignment_rate(
        ["Alice", "Mallory", "Unknown"],
        ["Alice", "Bob", "Carol"],
    ) == pytest.approx(1.0 / 3.0)

    overlap_reference = turns((0.0, 1.0, "ref_a"), (0.5, 1.5, "ref_b"))
    overlap_predicted = mark_overlapping_turns(
        turns((0.25, 1.0, "speaker_00"), (0.5, 1.25, "speaker_01"))
    )
    summary = summarize_diarization_baseline(
        overlap_predicted,
        reference_turns=overlap_reference,
        vad_only_segment_count=1,
        diarization_segment_count=2,
        runtime_sec=0.2,
        memory_overhead_mb=10.0,
    )

    assert summary.predicted_turn_count == 2
    assert summary.reference_turn_count == 2
    assert summary.overlap_predicted_turn_count == 2
    assert summary.overlap_segment_detection_rate == pytest.approx(1.0)
    assert json.dumps(summary.to_jsonable())


def test_pipeline_uses_diarization_turns_for_segmentation_when_enabled() -> None:
    record = {
        "recording_id": "rec-001",
        "utt_id": "utt-001",
        "inference_audio_path": "synthetic.wav",
        "duration_sec": 2.0,
        "start_sec": 0.0,
        "end_sec": 2.0,
    }
    pipeline = PipelineRunner(
        audio_reader=StaticAudioReader(2.0),
        vad=FixedVAD([SpeechRegion(start_sec=0.0, end_sec=2.0, label="speech")]),
        diarizer=FixedDiarizer(turns((0.0, 0.7, "speaker_00"), (0.9, 1.6, "speaker_01"))),
        segmenter=VADChunker(
            {
                "min_chunk_sec": 0.1,
                "max_chunk_sec": 5.0,
                "merge_gap_sec": 0.0,
                "left_pad_sec": 0.0,
                "right_pad_sec": 0.0,
                "clip_to_record_bounds": True,
            }
        ),
        asr=FixedASR("hello"),
    )

    output = pipeline.predict(record, {})

    assert output.recording_id == "rec-001"
    assert output.utt_id == "utt-001"
    assert output.start_sec == 0.0
    assert output.end_sec == 2.0
    assert output.diagnostics is not None
    assert [row["speaker_turn_label"] for row in output.diagnostics["diarization_turns"]] == [
        "speaker_00",
        "speaker_01",
    ]
    assert [
        segment["start_sec"]
        for segment in output.diagnostics["segments"]
    ] == [0.0, 0.9]
    assert output.runtime_stats is not None
    assert output.runtime_stats.diarization_sec is not None
    assert output.runtime_stats.counters["diarization_turn_count"] == 2


def test_pipeline_falls_back_to_vad_when_diarization_is_unavailable() -> None:
    class UnavailableDiarizer(FixedDiarizer):
        def diarize(self, audio: object):
            _ = audio
            raise DiarizationUnavailableError("missing local model")

    record = {
        "recording_id": "rec-002",
        "utt_id": "utt-002",
        "inference_audio_path": "synthetic.wav",
        "duration_sec": 1.0,
    }
    pipeline = PipelineRunner(
        audio_reader=StaticAudioReader(1.0),
        vad=FixedVAD([SpeechRegion(start_sec=0.2, end_sec=0.6, label="speech")]),
        diarizer=UnavailableDiarizer(()),
        segmenter=VADChunker(
            {
                "min_chunk_sec": 0.1,
                "max_chunk_sec": 5.0,
                "merge_gap_sec": 0.0,
                "left_pad_sec": 0.0,
                "right_pad_sec": 0.0,
                "clip_to_record_bounds": True,
            }
        ),
        asr=FixedASR("fallback"),
    )

    output = pipeline.predict(record, {})

    assert output.diagnostics is not None
    assert output.diagnostics["diarization_turns"] == []
    assert "diarization unavailable" in output.diagnostics["diarization_warnings"][0]
    assert output.diagnostics["segments"][0]["start_sec"] == pytest.approx(0.2)
    assert output.warnings


def test_diarization_report_writer(tmp_path: Path) -> None:
    metrics = summarize_diarization_baseline(
        turns((0.0, 1.0, "speaker_00")),
        reference_turns=turns((0.0, 1.0, "ref_a")),
        vad_only_segment_count=1,
        diarization_segment_count=1,
        runtime_sec=0.01,
    )
    report_path = component_report_path(tmp_path, "unit")
    written = write_diarization_report(
        report_path,
        run_id="unit",
        backend_name="fixed_diarization",
        metrics=metrics,
        files_changed=["app/inference_pipeline/diarization/base.py"],
        test_commands=["python -m pytest tests/inference_pipeline/test_diarization_interface.py"],
        smoke_checks=["synthetic fixed diarizer comparison"],
        pyannote_status="not required for core tests",
        runner_contract="recording_id and utt_id are preserved.",
        enabled_disabled_status="disabled and enabled paths tested.",
        recommendation="Keep diarization optional until real AMI/CHiME assets are available.",
    )

    text = written.read_text(encoding="utf-8")
    assert "M17 - Optional Diarization and Overlap Baseline" in text
    assert "DER" in text
