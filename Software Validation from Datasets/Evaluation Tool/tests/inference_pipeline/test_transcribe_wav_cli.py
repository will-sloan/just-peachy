from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from app.utils.json_utils import read_jsonl
from app.inference_pipeline.pipeline import pipeline_config_mapping


TOOL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = TOOL_ROOT / "scripts" / "transcribe_wav.py"


def test_transcribe_wav_default_text_stdout(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "sample.wav")

    result = run_cli(wav_path, "--smoke-safe")

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == "[Unknown] dummy pipeline transcript"


def test_transcribe_wav_preset_safe_stdout(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "sample.wav")

    result = run_cli(wav_path, "--preset", "safe")

    assert result.returncode == 0
    assert result.stdout.strip() == "[Unknown] dummy pipeline transcript"


def test_transcribe_wav_show_truth_infers_cmu_arctic_speaker(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "CMU Arctic" / "cmu_us_aew_arctic" / "wav" / "sample.wav")

    result = run_cli(wav_path, "--smoke-safe", "--show-truth")

    assert result.returncode == 0
    assert result.stdout.strip() == (
        "true: cmu_us_aew_arctic | predicted: Unknown | text: dummy pipeline transcript"
    )


def test_transcribe_wav_show_truth_uses_explicit_speaker(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "sample.wav")

    result = run_cli(wav_path, "--smoke-safe", "--show-truth", "--true-speaker", "alice")

    assert result.returncode == 0
    assert result.stdout.strip() == "true: alice | predicted: Unknown | text: dummy pipeline transcript"


def test_transcribe_wav_preset_configs_load() -> None:
    presets = TOOL_ROOT / "configs" / "inference" / "presets"

    assert pipeline_config_mapping(presets / "safe.yaml")["config_name"] == "safe"
    assert pipeline_config_mapping(presets / "tiny.yaml")["components"]["asr"]["name"] == "whisper_tiny"
    assert pipeline_config_mapping(presets / "base.yaml")["components"]["asr"]["name"] == "whisper_base"


def test_transcribe_wav_json_output_shape(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "sample.wav")

    result = run_cli(wav_path, "--smoke-safe", "--format", "json", "--segments")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["recording_id"] == "sample"
    assert payload["utt_id"] == "sample"
    assert payload["audio_path"] == str(wav_path.resolve())
    assert payload["speaker_label"] == "Unknown"
    assert payload["text"] == "dummy pipeline transcript"
    assert payload["segments"]


def test_transcribe_wav_jsonl_multiple_files(tmp_path: Path) -> None:
    first = write_wav(tmp_path / "first.wav")
    second = write_wav(tmp_path / "second.wav")

    result = run_cli(first, second, "--smoke-safe", "--format", "jsonl")

    assert result.returncode == 0
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert [row["recording_id"] for row in rows] == ["first", "second"]
    assert [row["text"] for row in rows] == [
        "dummy pipeline transcript",
        "dummy pipeline transcript",
    ]


def test_transcribe_wav_diagnostics_file_is_separate(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "sample.wav")
    diagnostics_path = tmp_path / "diagnostics.jsonl"

    result = run_cli(wav_path, "--smoke-safe", "--diagnostics", diagnostics_path)

    assert result.returncode == 0
    assert result.stdout.strip() == "[Unknown] dummy pipeline transcript"
    diagnostics = list(read_jsonl(diagnostics_path))
    assert diagnostics[0]["recording_id"] == "sample"
    assert diagnostics[0]["normalized_text"] == "dummy pipeline transcript"


def test_transcribe_wav_missing_wav_returns_nonzero(tmp_path: Path) -> None:
    missing = tmp_path / "missing.wav"

    result = run_cli(missing, "--smoke-safe")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "does not exist" in result.stderr


def test_transcribe_wav_enrollment_db_override_is_accepted(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "sample.wav")
    enrollment_db = tmp_path / "empty_enrollment_db.json"

    result = run_cli(
        wav_path,
        "--smoke-safe",
        "--enrollment-db",
        enrollment_db,
        "--format",
        "json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["speaker_label"] == "Unknown"


def test_transcribe_wav_disallows_identity_override_for_multiple_files(tmp_path: Path) -> None:
    first = write_wav(tmp_path / "first.wav")
    second = write_wav(tmp_path / "second.wav")

    result = run_cli(first, second, "--smoke-safe", "--recording-id", "same")

    assert result.returncode == 2
    assert "--recording-id can only be used with one WAV" in result.stderr


def test_transcribe_wav_disallows_true_speaker_override_for_multiple_files(tmp_path: Path) -> None:
    first = write_wav(tmp_path / "first.wav")
    second = write_wav(tmp_path / "second.wav")

    result = run_cli(first, second, "--smoke-safe", "--true-speaker", "same")

    assert result.returncode == 2
    assert "--true-speaker can only be used with one WAV" in result.stderr


def test_transcribe_wav_rejects_multiple_config_selectors(tmp_path: Path) -> None:
    wav_path = write_wav(tmp_path / "sample.wav")

    result = run_cli(wav_path, "--preset", "safe", "--smoke-safe")

    assert result.returncode == 2
    assert "--preset, --smoke-safe are mutually exclusive" in result.stderr


def run_cli(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(arg) for arg in args]],
        cwd=TOOL_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def write_wav(path: Path, *, duration_sec: float = 1.0, sample_rate: int = 16000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = int(duration_sec * sample_rate)
    time = np.arange(samples, dtype=np.float32) / sample_rate
    waveform = 0.25 * np.sin(2 * np.pi * 220 * time)
    sf.write(path, waveform.astype(np.float32), sample_rate)
    return path
