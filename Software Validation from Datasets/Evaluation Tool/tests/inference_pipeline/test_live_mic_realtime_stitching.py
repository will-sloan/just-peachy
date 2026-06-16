from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path

import pytest

from app.inference_pipeline.contracts import ASRTranscript, PipelineOutput, WordTiming
from app.inference_pipeline.realtime.speaker_state import (
    SPEAKER_STATUS_CONFIRMED,
    SPEAKER_STATUS_TENTATIVE,
    SPEAKER_STATUS_UNKNOWN,
    SpeakerEvidenceAccumulator,
)
from app.inference_pipeline.realtime.stitching import RealtimeTranscriptStitcher
from app.utils.json_utils import read_jsonl


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
SCRIPTS_ROOT = TOOL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

live_mic_realtime = importlib.import_module("live_mic_realtime")


def test_exact_overlap_is_removed_from_stitched_transcript() -> None:
    stitcher = RealtimeTranscriptStitcher(stability_delay_sec=0.0)

    first = stitcher.update(
        raw_text="i do not blame you",
        window_start_sec=0.0,
        window_end_sec=2.0,
        window_index=1,
    )
    second = stitcher.update(
        raw_text="blame you for anything",
        window_start_sec=1.0,
        window_end_sec=3.0,
        window_index=2,
    )

    assert first.committed_text == "i do not blame you"
    assert second.overlap_removed_tokens == 2
    assert second.committed_text == "i do not blame you for anything"
    assert second.newly_committed_text == "for anything"


def test_fuzzy_overlap_handles_punctuation_and_casing() -> None:
    stitcher = RealtimeTranscriptStitcher(stability_delay_sec=0.0)

    stitcher.update(
        raw_text="I do not blame YOU.",
        window_start_sec=0.0,
        window_end_sec=2.0,
        window_index=1,
    )
    update = stitcher.update(
        raw_text="blame you, for anything",
        window_start_sec=1.0,
        window_end_sec=3.0,
        window_index=2,
    )

    assert update.overlap_removed_tokens == 2
    assert update.committed_text == "I do not blame YOU for anything"


def test_word_timestamps_are_converted_to_stream_absolute_time() -> None:
    stitcher = RealtimeTranscriptStitcher(stability_delay_sec=0.0)

    update = stitcher.update(
        raw_text="hello world",
        words=(
            WordTiming(word="hello", start_sec=0.1, end_sec=0.4),
            WordTiming(word="world", start_sec=0.5, end_sec=0.9),
        ),
        window_start_sec=10.0,
        window_end_sec=11.0,
        window_index=7,
    )

    assert update.using_word_timestamps is True
    assert update.committed_words[0].start_sec == pytest.approx(10.1)
    assert update.committed_words[0].end_sec == pytest.approx(10.4)
    assert update.committed_words[1].start_sec == pytest.approx(10.5)
    assert update.committed_words[1].end_sec == pytest.approx(10.9)


def test_provisional_words_become_committed_after_stability_delay() -> None:
    stitcher = RealtimeTranscriptStitcher(stability_delay_sec=1.0)

    first = stitcher.update(
        raw_text="hello",
        words=(WordTiming(word="hello", start_sec=1.4, end_sec=1.8),),
        window_start_sec=0.0,
        window_end_sec=2.0,
        window_index=1,
    )
    second = stitcher.update(
        raw_text="",
        window_start_sec=2.0,
        window_end_sec=3.0,
        window_index=2,
    )

    assert first.committed_text == ""
    assert first.provisional_text == "hello"
    assert second.newly_committed_text == "hello"
    assert second.committed_text == "hello"


def test_provisional_delta_excludes_words_committed_in_same_update() -> None:
    stitcher = RealtimeTranscriptStitcher(stability_delay_sec=1.0)

    update = stitcher.update(
        raw_text="i do not blame you friend",
        window_start_sec=0.0,
        window_end_sec=2.0,
        window_index=1,
    )

    assert update.newly_committed_text == "i do not"
    assert update.provisional_delta_text == "blame you friend"


def test_speaker_evidence_accumulator_confirms_and_resets_labels() -> None:
    accumulator = SpeakerEvidenceAccumulator(
        confirmation_windows=3,
        confirmation_threshold=2,
        score_threshold=0.7,
    )

    first = accumulator.add_evidence({"Alice": 0.91})
    second = accumulator.add_evidence({"Alice": 0.88})
    weak = accumulator.add_evidence({"Alice": 0.2})
    changed_once = accumulator.add_evidence({"Bob": 0.93})
    changed_twice = accumulator.add_evidence({"Bob": 0.94})

    assert first.status == SPEAKER_STATUS_TENTATIVE
    assert second.status == SPEAKER_STATUS_CONFIRMED
    assert second.speaker_label == "Alice"
    assert weak.status == SPEAKER_STATUS_UNKNOWN
    assert weak.speaker_label == "Unknown"
    assert changed_once.status == SPEAKER_STATUS_TENTATIVE
    assert changed_once.speaker_label == "Bob"
    assert changed_twice.status == SPEAKER_STATUS_CONFIRMED
    assert changed_twice.speaker_label == "Bob"


def test_quiet_realtime_output_does_not_print_overlap_duplicates(tmp_path: Path) -> None:
    stdout = io.StringIO()
    pipeline = SequencePipeline(("i do not blame you", "blame you for anything"))

    result = live_mic_realtime.run_live_mic_realtime(
        config_path=CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml",
        run_id="unit_stitch_quiet",
        duration_sec=3.0,
        window_sec=2.0,
        hop_sec=1.0,
        sample_rate=10,
        speaker_label="Unknown",
        recording_id="stitch-rec",
        output_dir=tmp_path / "runs",
        keep_audio=False,
        dry_run=False,
        max_queue=4,
        drop_policy="block",
        frame_source=live_mic_realtime.DryRunFrameSource(real_time=False),
        pipeline_runner=pipeline,
        report_dir=tmp_path / "reports",
        stdout=stdout,
        stitch_transcript=True,
        stability_delay_sec=0.0,
    )

    output_text = " ".join(line.split(": ", 1)[1] for line in stdout.getvalue().splitlines())
    diagnostics_rows = list(read_jsonl(result.diagnostics_path))
    predicted_rows = [row for row in diagnostics_rows if row["status"] == "predicted"]

    assert output_text == "i do not blame you for anything"
    assert "blame you blame you" not in output_text
    assert [row["overlap_removed_tokens"] for row in predicted_rows] == [0, 2]
    assert predicted_rows[-1]["committed_text"] == "i do not blame you for anything"


class SequencePipeline:
    def __init__(self, texts: tuple[str, ...]) -> None:
        self.texts = texts
        self.last_diagnostics: dict[str, object] = {}

    def predict(self, record, run_config):
        _ = run_config
        index = int(record["window_index"]) - 1
        text = self.texts[index] if index < len(self.texts) else ""
        self.last_diagnostics = {
            "raw_asr_text": text,
            "normalized_asr_text": text,
            "speaker_scores": {},
        }
        return PipelineOutput(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            start_sec=float(record["start_sec"]),
            end_sec=float(record["end_sec"]),
            speaker_label=record.get("speaker_label"),
            text=text,
            transcript=ASRTranscript(text=text),
            diagnostics=self.last_diagnostics,
        )
