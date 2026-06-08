from __future__ import annotations

import importlib
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import PipelineOutput
from app.utils.json_utils import read_json, read_jsonl


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
SCRIPTS_ROOT = TOOL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

live_mic_realtime = importlib.import_module("live_mic_realtime")


class GatedFrameSource:
    is_microphone = False

    def __init__(
        self,
        *,
        first_predict_started: threading.Event,
        capture_finished: threading.Event,
        window_count: int,
        window_frames: int,
    ) -> None:
        self.first_predict_started = first_predict_started
        self.capture_finished = capture_finished
        self.window_count = window_count
        self.window_frames = window_frames
        self.emitted_batches = 0

    def capture(self, *, on_frames, duration_sec, sample_rate, stop_event) -> None:
        _ = (duration_sec, sample_rate)
        self._emit_one(on_frames)
        if not self.first_predict_started.wait(timeout=2.0):
            raise RuntimeError("first prediction did not start")
        for _ in range(self.window_count - 1):
            if stop_event.is_set():
                break
            self._emit_one(on_frames)
        self.capture_finished.set()

    def _emit_one(self, on_frames) -> None:
        now = time.monotonic()
        on_frames(np.zeros(self.window_frames, dtype=np.float32), now, now)
        self.emitted_batches += 1


class BlockingFakePipeline:
    def __init__(
        self,
        *,
        first_predict_started: threading.Event | None = None,
        capture_finished: threading.Event | None = None,
        settle_sec: float = 0.0,
    ) -> None:
        self.first_predict_started = first_predict_started or threading.Event()
        self.capture_finished = capture_finished or threading.Event()
        self.settle_sec = settle_sec
        self.records: list[dict[str, object]] = []
        self.run_configs: list[dict[str, object]] = []
        self.capture_finished_during_first_predict = False
        self.last_diagnostics = {"fake": True}

    def predict(self, record, run_config):
        self.records.append(dict(record))
        self.run_configs.append(dict(run_config))
        if len(self.records) == 1:
            self.first_predict_started.set()
            self.capture_finished_during_first_predict = self.capture_finished.wait(timeout=2.0)
            if self.settle_sec:
                time.sleep(self.settle_sec)
        return PipelineOutput(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            start_sec=float(record["start_sec"]),
            end_sec=float(record["end_sec"]),
            speaker_label=record.get("speaker_label"),
            text=f"fake realtime transcript {record['window_index']}",
            diagnostics={
                "inference_audio_path": str(record["inference_audio_path"]),
                "window_index": record["window_index"],
            },
        )


def test_capture_and_inference_are_decoupled_with_background_worker(tmp_path: Path) -> None:
    first_predict_started = threading.Event()
    capture_finished = threading.Event()
    source = GatedFrameSource(
        first_predict_started=first_predict_started,
        capture_finished=capture_finished,
        window_count=4,
        window_frames=100,
    )
    pipeline = BlockingFakePipeline(
        first_predict_started=first_predict_started,
        capture_finished=capture_finished,
        settle_sec=0.05,
    )

    result = live_mic_realtime.run_live_mic_realtime(
        config_path=CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml",
        run_id="unit_decoupled",
        duration_sec=0.4,
        window_sec=0.1,
        hop_sec=0.1,
        sample_rate=1000,
        speaker_label="Billy",
        recording_id="mic-rec",
        output_dir=tmp_path / "runs",
        keep_audio=True,
        dry_run=False,
        max_queue=10,
        drop_policy="block",
        frame_source=source,
        pipeline_runner=pipeline,
        report_dir=tmp_path / "reports",
        stdout=sys.stdout,
    )

    diagnostics_rows = list(read_jsonl(result.diagnostics_path))
    predicted_rows = [row for row in diagnostics_rows if row["status"] == "predicted"]

    assert pipeline.capture_finished_during_first_predict is True
    assert source.emitted_batches == 4
    assert result.prediction_count == 4
    assert max(row["queue_depth_at_enqueue"] for row in predicted_rows) >= 2


def test_realtime_records_predictions_and_diagnostics_preserve_contract(
    tmp_path: Path,
) -> None:
    first_predict_started = threading.Event()
    capture_finished = threading.Event()
    source = GatedFrameSource(
        first_predict_started=first_predict_started,
        capture_finished=capture_finished,
        window_count=3,
        window_frames=100,
    )
    pipeline = BlockingFakePipeline(
        first_predict_started=first_predict_started,
        capture_finished=capture_finished,
        settle_sec=0.02,
    )

    result = live_mic_realtime.run_live_mic_realtime(
        config_path=CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml",
        run_id="unit_contract",
        duration_sec=0.3,
        window_sec=0.1,
        hop_sec=0.1,
        sample_rate=1000,
        speaker_label="Billy",
        recording_id="mic-rec",
        output_dir=tmp_path / "runs",
        keep_audio=True,
        dry_run=False,
        max_queue=10,
        drop_policy="block",
        frame_source=source,
        pipeline_runner=pipeline,
        report_dir=tmp_path / "reports",
        stdout=sys.stdout,
    )

    assert [record["recording_id"] for record in pipeline.records] == ["mic-rec"] * 3
    assert [record["utt_id"] for record in pipeline.records] == [
        "mic-rec_window_0001",
        "mic-rec_window_0002",
        "mic-rec_window_0003",
    ]
    assert [(record["start_sec"], record["end_sec"]) for record in pipeline.records] == [
        (0.0, 0.1),
        (0.0, 0.1),
        (0.0, 0.1),
    ]
    assert [record["speaker_label"] for record in pipeline.records] == ["Billy"] * 3

    for index, record in enumerate(pipeline.records, start=1):
        expected_path = result.run_dir / "audio" / f"window_{index:04d}.wav"
        assert Path(str(record["inference_audio_path"])) == expected_path
        assert expected_path.is_file()

    prediction_rows = list(read_jsonl(result.predictions_path))
    assert [set(row) for row in prediction_rows] == [
        set(live_mic_realtime.REQUIRED_PREDICTION_FIELDS),
        set(live_mic_realtime.REQUIRED_PREDICTION_FIELDS),
        set(live_mic_realtime.REQUIRED_PREDICTION_FIELDS),
    ]
    assert [row["text"] for row in prediction_rows] == [
        "fake realtime transcript 1",
        "fake realtime transcript 2",
        "fake realtime transcript 3",
    ]

    diagnostics_rows = list(read_jsonl(result.diagnostics_path))
    predicted_rows = [row for row in diagnostics_rows if row["status"] == "predicted"]
    required_diagnostic_fields = {
        "window_index",
        "capture_start_monotonic",
        "capture_end_monotonic",
        "inference_start_monotonic",
        "inference_end_monotonic",
        "capture_to_prediction_latency_sec",
        "asr_realtime_factor",
        "queue_depth_at_enqueue",
        "queue_depth_at_dequeue",
        "dropped_window_count",
        "inference_audio_path",
    }
    assert all(required_diagnostic_fields.issubset(row) for row in predicted_rows)
    assert [row["window_start_sec"] for row in predicted_rows] == [0.0, 0.1, 0.2]
    assert [row["window_end_sec"] for row in predicted_rows] == [0.1, 0.2, 0.3]


def test_dry_run_works_without_microphone_or_whisper_assets(tmp_path: Path) -> None:
    result = live_mic_realtime.run_live_mic_realtime(
        config_path=CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml",
        run_id="unit_dry_run",
        duration_sec=0.2,
        window_sec=0.1,
        hop_sec=0.1,
        sample_rate=1000,
        speaker_label="Dry Speaker",
        recording_id="dry-rec",
        output_dir=tmp_path / "runs",
        keep_audio=False,
        dry_run=True,
        max_queue=4,
        report_dir=tmp_path / "reports",
        stdout=sys.stdout,
    )

    rows = list(read_jsonl(result.predictions_path))
    summary = read_json(result.summary_path)

    assert result.dry_run is True
    assert result.microphone_capture_tested is False
    assert result.asr_mode == "dry_run_no_op_asr"
    assert len(rows) == 2
    assert {row["text"] for row in rows} == {"dry run transcript unavailable"}
    assert all(row["speaker_label"] == "Dry Speaker" for row in rows)
    assert not (result.run_dir / "audio").exists()
    assert summary["dry_run"] is True
    assert summary["real_asr_used"] is False
    assert summary["availability"]["asr_component"] == "whisper_tiny"


def test_input_wav_streams_like_realtime_source_without_microphone(tmp_path: Path) -> None:
    input_wav = tmp_path / "speaker.wav"
    audio = 0.1 * np.sin(2.0 * np.pi * 40.0 * np.arange(300, dtype=np.float32) / 1000)
    live_mic_realtime.write_pcm16_wav(input_wav, audio.astype(np.float32), sample_rate=1000)
    capture_finished = threading.Event()
    capture_finished.set()
    pipeline = BlockingFakePipeline(capture_finished=capture_finished)

    result = live_mic_realtime.run_live_mic_realtime(
        config_path=CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml",
        run_id="unit_input_wav",
        duration_sec=0.3,
        window_sec=0.1,
        hop_sec=0.1,
        sample_rate=1000,
        speaker_label="Billy",
        recording_id="wav-rec",
        input_wav=input_wav,
        output_dir=tmp_path / "runs",
        keep_audio=True,
        dry_run=False,
        max_queue=4,
        pipeline_runner=pipeline,
        report_dir=tmp_path / "reports",
        stdout=sys.stdout,
    )

    rows = list(read_jsonl(result.predictions_path))
    summary = read_json(result.summary_path)

    assert result.microphone_capture_tested is False
    assert result.prediction_count == 3
    assert [record["utt_id"] for record in pipeline.records] == [
        "wav-rec_window_0001",
        "wav-rec_window_0002",
        "wav-rec_window_0003",
    ]
    assert [row["speaker_label"] for row in rows] == ["Billy"] * 3
    assert summary["input_wav_path"] == str(input_wav)
    assert summary["availability"]["realtime_capture"] == "wav_file_realtime"


def test_cli_quiet_mode_prints_transcript_only(tmp_path: Path, capsys) -> None:
    status = live_mic_realtime.main(
        [
            "--config",
            str(CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml"),
            "--run-id",
            "unit_cli_quiet",
            "--duration-sec",
            "0.1",
            "--window-sec",
            "0.1",
            "--hop-sec",
            "0.1",
            "--sample-rate",
            "1000",
            "--speaker-label",
            "Billy",
            "--recording-id",
            "quiet-rec",
            "--output-dir",
            str(tmp_path / "runs"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()

    assert status == 0
    assert captured.out.strip() == "Billy: dry run transcript unavailable"
    assert "Run directory:" not in captured.out
    assert "Predictions:" not in captured.out


def test_cli_verbose_mode_keeps_detailed_output_and_artifact_paths(tmp_path: Path, capsys) -> None:
    status = live_mic_realtime.main(
        [
            "--config",
            str(CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml"),
            "--run-id",
            "unit_cli_verbose",
            "--duration-sec",
            "0.1",
            "--window-sec",
            "0.1",
            "--hop-sec",
            "0.1",
            "--sample-rate",
            "1000",
            "--speaker-label",
            "Billy",
            "--recording-id",
            "verbose-rec",
            "--output-dir",
            str(tmp_path / "runs"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--dry-run",
            "--verbose",
        ]
    )

    captured = capsys.readouterr()

    assert status == 0
    assert "[DRY-RUN/NO-OP unit_cli_verbose]" in captured.out
    assert "Run directory:" in captured.out
    assert "Predictions:" in captured.out


def test_missing_sounddevice_dependency_is_reported_cleanly(tmp_path: Path) -> None:
    def missing_importer(name: str):
        if name == "sounddevice":
            raise ModuleNotFoundError(name)
        return importlib.import_module(name)

    source = live_mic_realtime.SoundDeviceFrameSource(module_importer=missing_importer)

    with pytest.raises(live_mic_realtime.MicrophoneUnavailableError, match="sounddevice"):
        source.capture(
            on_frames=lambda frames, start, end: None,
            duration_sec=0.1,
            sample_rate=16000,
            stop_event=threading.Event(),
        )


def test_queue_overflow_drop_oldest_is_deterministic(tmp_path: Path) -> None:
    first_predict_started = threading.Event()
    capture_finished = threading.Event()
    source = GatedFrameSource(
        first_predict_started=first_predict_started,
        capture_finished=capture_finished,
        window_count=4,
        window_frames=100,
    )
    pipeline = BlockingFakePipeline(
        first_predict_started=first_predict_started,
        capture_finished=capture_finished,
        settle_sec=0.05,
    )

    result = live_mic_realtime.run_live_mic_realtime(
        config_path=CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml",
        run_id="unit_drop_oldest",
        duration_sec=0.4,
        window_sec=0.1,
        hop_sec=0.1,
        sample_rate=1000,
        speaker_label="Billy",
        recording_id="mic-rec",
        output_dir=tmp_path / "runs",
        keep_audio=True,
        dry_run=False,
        max_queue=1,
        drop_policy="drop_oldest",
        frame_source=source,
        pipeline_runner=pipeline,
        report_dir=tmp_path / "reports",
        stdout=sys.stdout,
    )

    prediction_rows = list(read_jsonl(result.predictions_path))
    diagnostics_rows = list(read_jsonl(result.diagnostics_path))
    dropped_rows = [row for row in diagnostics_rows if row["status"] == "dropped"]

    assert [row["utt_id"] for row in prediction_rows] == [
        "mic-rec_window_0001",
        "mic-rec_window_0004",
    ]
    assert [row["window_index"] for row in dropped_rows] == [2, 3]
    assert result.dropped_window_count == 2
    assert all(row["drop_reason"] == "drop_oldest" for row in dropped_rows)


def test_realtime_whisper_tiny_config_selects_real_asr_without_downloads() -> None:
    config = PipelineConfig.from_yaml_path(CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml")
    availability = live_mic_realtime.live_mic_smoke.inspect_runtime_availability(
        config,
        config_path=CONFIG_ROOT / "live_mic_realtime_whisper_tiny.yaml",
    )

    assert config.components["asr"].name == "whisper_tiny"
    assert config.components["asr"].params["allow_model_downloads"] is False
    assert config.components["vad"].enabled is False
    assert config.components["segmentation"].enabled is False
    assert availability["asr_component"] == "whisper_tiny"
    assert availability["allow_model_downloads"] is False
    assert "whisper_model_asset_searched" in availability
