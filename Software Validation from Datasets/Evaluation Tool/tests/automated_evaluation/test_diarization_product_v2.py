from __future__ import annotations

import json
from pathlib import Path

from app.diarization_evaluation.formats import RttmTurn
from app.diarization_product_v2.analysis import (
    _case_product_metrics,
    _dominates,
    _latency_summary,
    _speaker_cluster_bootstrap,
)
from app.diarization_product_v2.contracts import (
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_RESULT_ROOT,
    TOOL_ROOT,
)
from app.diarization_product_v2.controller import _measured_eta_seconds
from app.diarization_product_v2.protocol import prepare_product_protocol


def test_frozen_product_protocol_reuses_deterministically_and_preserves_firewall() -> None:
    first = json.loads(
        (DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8")
    )
    result = prepare_product_protocol()
    assert result["reused"] is True
    assert result["protocol_summary"]["protocol_id"] == first["protocol_id"]
    assert result["validation"]["valid"] is True
    assert result["validation"]["development_evaluation_speaker_disjoint"] is True
    assert result["validation"]["v1_source_clip_overlap"] == 0
    assert first["evaluation_only"] is True
    assert first["training_eligible"] is False
    assert first["evaluation_results_inspected"] is False


def test_product_metrics_cover_short_boundary_reentry_contamination_and_censoring() -> None:
    case = {
        "case_id": "case",
        "duration_sec": 8.0,
        "local_to_global_speaker": {"SPK00": "global_a", "SPK01": "global_b"},
    }
    refs = [
        RttmTurn("case", "1", 0.0, 0.45, "SPK00"),
        RttmTurn("case", "1", 0.6, 1.4, "SPK01"),
        RttmTurn("case", "1", 5.0, 7.5, "SPK00"),
    ]
    hyps = [
        RttmTurn("case", "1", 0.05, 0.5, "speaker_00"),
        RttmTurn("case", "1", 0.65, 1.35, "speaker_01"),
        RttmTurn("case", "1", 5.1, 7.4, "speaker_00"),
    ]
    value = _case_product_metrics(case, refs, hyps)
    assert {row["duration_bucket"] for row in value["short_turns"]} >= {
        "lt_0_50",
        "0_50_to_1_00",
        "2_00_to_5_00",
    }
    assert value["boundaries"]
    assert value["reentry"][0]["absence_bucket"] == "1_to_5"
    assert all(0.0 <= row["contamination"] <= 1.0 for row in value["contamination"])
    target = [row for row in value["latency"] if row["target_sec"] == 3.0]
    assert target and any(row["censored"] for row in target)


def test_predeclared_dominance_uses_tolerance_and_requires_meaningful_gain() -> None:
    criteria = (("der", "min", 0.01), ("clean", "max", 0.01), ("rtf", "min", 0.02))
    assert _dominates(
        {"der": 0.10, "clean": 0.90, "rtf": 0.30},
        {"der": 0.13, "clean": 0.89, "rtf": 0.31},
        criteria,
    )
    assert not _dominates(
        {"der": 0.10, "clean": 0.90, "rtf": 0.30},
        {"der": 0.105, "clean": 0.895, "rtf": 0.31},
        criteria,
    )


def test_latency_summary_retains_censored_failures_and_speaker_bootstrap_groups() -> None:
    rows = [
        {"protocol": "v2", "pipeline_id": "p", "target_sec": 2.0, "global_speaker_id": "a", "achieved": True, "latency_sec": 1.5, "censor_time_sec": 6.0},
        {"protocol": "v2", "pipeline_id": "p", "target_sec": 2.0, "global_speaker_id": "b", "achieved": False, "latency_sec": None, "censor_time_sec": 5.0},
    ]
    summary = _latency_summary(rows, ("protocol", "pipeline_id", "target_sec"))[0]
    assert summary["censored_not_reached_count"] == 1
    assert summary["failure_probability"] == 0.5
    assert summary["restricted_mean_latency_lower_bound_sec"] == 3.25
    low, high, groups = _speaker_cluster_bootstrap(
        rows,
        value_getter=lambda row: row["latency_sec"] if row["achieved"] else row["censor_time_sec"],
        group_getter=lambda row: [row["global_speaker_id"]],
        repetitions=100,
        seed=3800,
    )
    assert groups == 2
    assert low is not None and high is not None and low <= high


def test_resumed_eta_ignores_float_residue_until_real_new_audio() -> None:
    assert _measured_eta_seconds(
        elapsed_seconds=60.0,
        total_audio_seconds=40_000.0,
        completed_audio_seconds=4_122.587937500001,
        resume_audio_seconds=4_122.5879375,
    ) is None
    value = _measured_eta_seconds(
        elapsed_seconds=60.0,
        total_audio_seconds=40_000.0,
        completed_audio_seconds=4_222.5879375,
        resume_audio_seconds=4_122.5879375,
    )
    assert value is not None and 0 < value < 100_000


def test_cross_environment_smoke_proves_shared_segmentation_reuse() -> None:
    summary = json.loads(
        (
            DEFAULT_RESULT_ROOT
            / "engineering_smoke"
            / "smoke_summary.json"
        ).read_text(encoding="utf-8")
    )
    assert summary["segmentation_cache_reuse_observed"] is True
    assert len(summary["pipelines"]) == 3
    assert all(row["returncode"] == 0 for row in summary["pipelines"])
    assert all(row["technical_coverage"] == 1.0 for row in summary["technical_coverage"])


def test_monitor_is_read_only_and_exposes_audio_weighted_progress_eta_and_pid() -> None:
    text = (
        TOOL_ROOT / "scripts" / "monitor_diarization_product_v2.ps1"
    ).read_text(encoding="utf-8")
    assert "overall_audio_weighted_percentage" in text
    assert "eta_seconds" in text
    assert "current_process_pid" in text
    assert "scenario:" in text
    assert "CPU:" in text
    assert "latest result activity:" in text
    assert "STOP_REQUESTED" not in text
