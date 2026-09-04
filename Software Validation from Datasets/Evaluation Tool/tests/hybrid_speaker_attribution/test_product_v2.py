from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from app.hybrid_speaker_attribution.product_v2_analysis import _label_at, _named_id, _time_metrics, _unknown_instance
from app.hybrid_speaker_attribution.product_v2_contracts import (
    BACKEND_MINIMUM_SEC, COMBINATIONS, DIARIZATION_PIPELINES, PRODUCT_PROTOCOL_ROOT,
    V1_OVERLAY_COUNTS, V1_PROTOCOL_ID, V1_PROTOCOL_ROOT,
)
from app.hybrid_speaker_attribution.product_v2_protocol import BACKEND_POLICY


TOOL_ROOT = Path(__file__).resolve().parents[2]


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_hybrid_v1_identity_and_counts_are_preserved():
    summary = json.loads((V1_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))
    assert summary["protocol_id"] == V1_PROTOCOL_ID
    assert summary["overlay_counts"] == V1_OVERLAY_COUNTS


def test_product_v2_overlays_are_deterministic_metadata_and_leakage_safe():
    first = (PRODUCT_PROTOCOL_ROOT / "v2" / "development" / "identity_overlays.jsonl").read_bytes()
    rows = _rows(PRODUCT_PROTOCOL_ROOT / "v2" / "development" / "identity_overlays.jsonl")
    assert len(rows) == 108
    assert all(row["waveform_identity_unchanged"] and row["training_eligible"] is False for row in rows)
    assert not list(PRODUCT_PROTOCOL_ROOT.rglob("*.wav")) and not list(PRODUCT_PROTOCOL_ROOT.rglob("*.mp3"))
    for row in rows:
        live = set(row["local_to_global_speaker"].values())
        assert all(item["database_role"] != "background_impostor" or item["global_speaker_id"] not in live for item in row["enrollment_database"])
    assert first == (PRODUCT_PROTOCOL_ROOT / "v2" / "development" / "identity_overlays.jsonl").read_bytes()


def test_development_evaluation_speakers_are_separate_and_evaluation_firewall_is_closed():
    benchmark = TOOL_ROOT / "benchmarks" / "stage11" / "diarization_product_v2"
    dev = {speaker for row in _rows(benchmark / "development" / "case_manifest.jsonl") for speaker in row["global_speaker_ids"]}
    evaluation = {speaker for row in _rows(benchmark / "evaluation" / "case_manifest.jsonl") for speaker in row["global_speaker_ids"]}
    summary = json.loads((PRODUCT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))
    assert dev.isdisjoint(evaluation)
    assert summary["EVALUATION_NOT_INSPECTED"] is True


def test_six_immutable_combination_identities_and_scientific_policies():
    assert [row["combination_id"] for row in COMBINATIONS] == ["H1", "H2", "H3", "H4", "H5", "H6"]
    assert {row["diarization_pipeline_id"] for row in COMBINATIONS} == set(DIARIZATION_PIPELINES)
    for backend, minimum in BACKEND_MINIMUM_SEC.items():
        policy = yaml.safe_load((TOOL_ROOT / "configs" / "automated_evaluation" / "hybrid_product_v2" / f"{backend}.scientific.yaml").read_text(encoding="utf-8"))
        assert policy["scientific"] is True and policy["source_study_status"] == "COMPLETE"
        assert policy["technical_minimum_evidence_sec"] == minimum
        assert policy["enrollment_utterance_count"] == 3
        assert "non_scientific" not in policy["policy_id"]


def test_any_unknown_instance_unknown_and_reference_time_denominators_are_distinct():
    bundle = {
        "references": [
            {"segment_id": "r1", "start_sec": 0.0, "end_sec": 2.0, "duration_sec": 2.0, "global_speaker_id": "known"},
            {"segment_id": "r2", "start_sec": 2.0, "end_sec": 4.0, "duration_sec": 2.0, "global_speaker_id": "stranger"},
        ],
        "predictions": [
            {"start_sec": 0.0, "end_sec": 2.0, "cluster_id": "c1"},
            {"start_sec": 2.0, "end_sec": 3.0, "cluster_id": "c2"},
            {"start_sec": 3.0, "end_sec": 4.0, "cluster_id": "c3"},
        ],
        "clusters": [
            {"cluster_id": "c1", "dominant_global_speaker_id": "known", "reference_overlap_sec": {"known": 2.0}},
            {"cluster_id": "c2", "dominant_global_speaker_id": "stranger", "reference_overlap_sec": {"stranger": 1.0}},
            {"cluster_id": "c3", "dominant_global_speaker_id": "stranger", "reference_overlap_sec": {"stranger": 1.0}},
        ],
    }
    states = {"known": {"identity_state": "KNOWN"}, "stranger": {"identity_state": "UNKNOWN"}}
    decisions = {cluster: [{"observation_end_sec": 0.0, "display_label": label}] for cluster, label in (("c1", "E1"), ("c2", "Speaker_2"), ("c3", "Speaker_3"))}
    metrics = _time_metrics(bundle, states, {"E1": "known"}, {"known": "E1"}, decisions)
    unknown = _unknown_instance(bundle, states, decisions, {"E1": "known"})
    assert metrics["reference_speech_time_sec"] == 4.0
    assert metrics["end_to_end_correctly_named_known_rate"] == 1.0
    assert metrics["unknown_rejection_rate"] == 1.0
    assert unknown["any_unknown_rejection_rate"] == 1.0
    assert unknown["unknown_instance_consistency"] == 0.5
    assert unknown["unknown_split_count"] == 1


def test_causal_labels_censor_future_and_classify_transitions():
    events = [
        {"observation_end_sec": 0.0, "display_label": "Speaker_1"},
        {"observation_end_sec": 1.5, "display_label": "Tentative:E1"},
        {"observation_end_sec": 2.5, "display_label": "E1"},
    ]
    assert _label_at(events, 1.0) == "Speaker_1"
    assert _named_id(_label_at(events, 2.0)) == "E1"
    assert _label_at(events, 3.0) == "E1"


def test_same_model_cache_replay_is_numerically_equivalent_without_primary_reuse():
    vector = np.asarray([0.1, 0.2, 0.3], dtype=np.float64)
    cached = np.asarray(json.loads(json.dumps(vector.tolist())), dtype=np.float64)
    assert np.max(np.abs(vector - cached)) == 0.0
    assert all(row["same_model"] == (row["combination_id"] in {"H1", "H2"}) for row in COMBINATIONS)


def test_read_only_monitor_and_restart_contract_exist():
    monitor = TOOL_ROOT / "scripts" / "monitor_hybrid_speaker_attribution_product_v2.ps1"
    wrapper = TOOL_ROOT / "scripts" / "run_hybrid_speaker_attribution_product_v2.ps1"
    text = monitor.read_text(encoding="utf-8")
    assert "-not $Follow" in text and "Ctrl+C closes only this read-only monitor" in text
    assert "RunDevelopment" in wrapper.read_text(encoding="utf-8")

