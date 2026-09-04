from __future__ import annotations

from pathlib import Path

from app.diarization_evaluation.formats import RttmTurn
from app.diarization_final_evaluation.analysis import _forbidden_archive_name
from app.diarization_final_evaluation.contracts import EXPECTED_PIPELINES
from app.diarization_final_evaluation.decision import selected_pipelines, validate_frozen_decision
from app.diarization_final_evaluation.native import (
    _fragmentation_diagnostics,
    _is_transient_windows_replace_failure,
    native_rows,
)


def test_frozen_decision_is_exact_and_valid() -> None:
    result = validate_frozen_decision(write_authorizations=False)
    assert result["valid"], result["errors"]
    assert tuple(result["selected_pipeline_ids"]) == EXPECTED_PIPELINES
    assert selected_pipelines() == EXPECTED_PIPELINES


def test_native_panel_and_reference_scope_are_frozen() -> None:
    chime = native_rows("chime6")
    voices = native_rows("voices")
    assert len(chime) == 80
    assert len(voices) == 40
    assert sum(row["stream_type"] == "farfield_array" for row in chime) == 40
    assert sum(row["stream_type"] == "participant_close" for row in chime) == 40
    assert all(not row["der_jer_eligible"] for row in voices)


def test_voices_fragmentation_diagnostic_is_anonymous() -> None:
    turns = [
        RttmTurn("unit", "1", 0.0, 4.0, "speaker_00"),
        RttmTurn("unit", "1", 4.0, 5.0, "speaker_01"),
    ]
    result = _fragmentation_diagnostics(turns, 10.0)
    assert result["predicted_speaker_count"] == 2
    assert result["largest_cluster_fraction"] == 0.8
    assert result["phantom_speaker_duration_sec"] == 1.0
    assert result["der_jer_supported"] is False


def test_export_firewall_rejects_audio_weights_and_cache() -> None:
    assert _forbidden_archive_name("results/_native_audio_cache/a.wav")
    assert _forbidden_archive_name("models/model.onnx")
    assert _forbidden_archive_name("results/_shared_cache/vector.json")
    assert not _forbidden_archive_name("analysis/overall_results.csv")


def test_monitor_and_runner_are_read_only_restart_safe_surfaces() -> None:
    tool = Path(__file__).resolve().parents[2]
    monitor = (tool / "scripts" / "monitor_diarization_final_evaluation.ps1").read_text(encoding="utf-8")
    runner = (tool / "scripts" / "run_diarization_final_evaluation.ps1").read_text(encoding="utf-8")
    assert "Ctrl+C closes this read-only monitor only" in monitor
    assert "overall_audio_weighted_percentage" in monitor
    assert "-Background" not in runner  # switch declaration is $Background; recursive self-call is bounded
    assert "diarization-final-evaluation" in runner


def test_only_known_windows_atomic_replace_failure_is_retryable() -> None:
    transient = PermissionError(
        "[WinError 5] Access is denied: '.extraction_summary.json.tmp' -> 'extraction_summary.json'"
    )
    assert _is_transient_windows_replace_failure(transient)
    assert not _is_transient_windows_replace_failure(RuntimeError("model inference failed"))
