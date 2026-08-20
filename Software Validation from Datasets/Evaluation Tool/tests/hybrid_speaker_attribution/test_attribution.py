from __future__ import annotations

import copy

import pytest

from app.hybrid_speaker_attribution.attribution import AttributionSettings, attribute_recording, score_recording


def _settings(**changes) -> AttributionSettings:
    values = {
        "product_threshold": 0.8,
        "score_margin": 0.05,
        "minimum_segment_duration_sec": 0.25,
        "minimum_evidence_duration_sec": 0.5,
    }
    values.update(changes)
    return AttributionSettings(**values)


def _segment(segment_id, cluster_id, start, end, vector, **extra):
    return {"segment_id": segment_id, "cluster_id": cluster_id, "start_sec": start, "end_sec": end, "duration_sec": end - start, "status": "ok", "vector": vector, **extra}


def test_known_unknown_and_multiple_unknown_labels_are_persistent():
    segments = [
        _segment("a1", "speaker_00", 0, 1, [1.0, 0.0]),
        _segment("u1", "speaker_01", 1, 2, [0.0, 1.0]),
        _segment("u2", "speaker_02", 2, 3, [-1.0, 0.0]),
        _segment("u1_return", "speaker_01", 4, 5, [0.0, 1.0]),
    ]
    result = attribute_recording(recording_id="rec", segments=segments, enrollment={"Alice": [{"vector": [1.0, 0.0], "duration_sec": 2, "status": "ok"}]}, settings=_settings())
    final = {row["cluster_id"]: row["assigned_label"] for row in result["final"]}
    assert final == {"speaker_00": "Alice", "speaker_01": "Unknown_2", "speaker_02": "Unknown_3"}
    reentry = [row["assigned_label"] for row in result["progressive"] if row["cluster_id"] == "speaker_01"]
    assert reentry == ["Unknown_2", "Unknown_2"]


def test_progressive_decision_has_no_future_information_leakage():
    prefix = [_segment("one", "speaker_00", 0, 1, [0.0, 1.0])]
    later = _segment("two", "speaker_00", 2, 4, [1.0, 0.0])
    enrollment = {"Alice": [{"vector": [1.0, 0.0], "duration_sec": 2, "status": "ok"}]}
    settings = _settings(cluster_aggregation="duration_weighted_mean")
    before = attribute_recording(recording_id="rec", segments=prefix, enrollment=enrollment, settings=settings)
    after = attribute_recording(recording_id="rec", segments=prefix + [later], enrollment=enrollment, settings=settings)
    assert before["progressive"][0] == after["progressive"][0]
    assert before["final"][0]["assigned_label"] != after["final"][0]["assigned_label"]


def test_minimum_evidence_and_margin_are_explicit():
    short = [_segment("one", "speaker_00", 0, 0.4, [1.0, 0.0])]
    enrollment = {
        "Alice": [{"vector": [1.0, 0.0], "duration_sec": 2, "status": "ok"}],
        "Bob": [{"vector": [0.999, 0.045], "duration_sec": 2, "status": "ok"}],
    }
    provisional = attribute_recording(recording_id="rec", segments=short, enrollment=enrollment, settings=_settings())["final"][0]
    assert provisional["decision_category"] == "INSUFFICIENT_EVIDENCE"
    enough = [dict(short[0], end_sec=1.0, duration_sec=1.0)]
    rejected = attribute_recording(recording_id="rec", segments=enough, enrollment=enrollment, settings=_settings(score_margin=0.1))["final"][0]
    assert rejected["decision_state"] == "UNKNOWN"


def test_overlap_exclusion_keeps_invalid_evidence_out():
    segments = [_segment("one", "speaker_00", 0, 1, [1.0, 0.0], predicted_overlap=True)]
    result = attribute_recording(recording_id="rec", segments=segments, enrollment={"Alice": [{"vector": [1.0, 0.0], "duration_sec": 2, "status": "ok"}]}, settings=_settings(overlap_policy="exclude_predicted_overlap_segments"))
    assert result["final"][0]["usable_segment_count"] == 0
    assert result["final"][0]["decision_state"] == "PROVISIONAL"


def test_wrong_known_false_known_fragmentation_and_merge_are_visible():
    refs = [
        {"start_sec": 0, "end_sec": 1, "speaker_label": "SPK00"},
        {"start_sec": 2, "end_sec": 3, "speaker_label": "SPK00"},
        {"start_sec": 3, "end_sec": 4, "speaker_label": "SPK01"},
    ]
    predicted = [
        {"segment_id": "p1", "start_sec": 0, "end_sec": 1, "cluster_id": "c1"},
        {"segment_id": "p2", "start_sec": 2, "end_sec": 4, "cluster_id": "c2"},
    ]
    final = [
        {"cluster_id": "c1", "assigned_label": "Bob", "decision_state": "KNOWN"},
        {"cluster_id": "c2", "assigned_label": "Alice", "decision_state": "KNOWN"},
    ]
    progressive = [
        {"segment_id": "p1", "cluster_id": "c1", "assigned_label": "Bob", "observation_end_sec": 1},
        {"segment_id": "p2", "cluster_id": "c2", "assigned_label": "Alice", "observation_end_sec": 4},
    ]
    metrics = score_recording(
        reference_turns=refs, predicted_turns=predicted,
        local_to_global={"SPK00": "global_a", "SPK01": "global_u"},
        speaker_states={
            "global_a": {"identity_state": "KNOWN", "enrolled_id": "Alice", "unknown_reference_id": None},
            "global_u": {"identity_state": "UNKNOWN", "enrolled_id": None, "unknown_reference_id": "unknown_ref"},
        }, final_decisions=final, progressive_decisions=progressive,
    )
    assert metrics["wrong_known_time_sec"] == pytest.approx(1.0)
    assert metrics["false_known_time_sec"] == pytest.approx(1.0)
    assert metrics["fragmentation_count"] == 1
    assert metrics["merge_count"] == 1


def test_unknown_scoring_is_permutation_invariant():
    refs = [
        {"start_sec": 0, "end_sec": 1, "speaker_label": "SPK00"},
        {"start_sec": 1, "end_sec": 2, "speaker_label": "SPK01"},
    ]
    predicted = [
        {"segment_id": "p1", "start_sec": 0, "end_sec": 1, "cluster_id": "c1"},
        {"segment_id": "p2", "start_sec": 1, "end_sec": 2, "cluster_id": "c2"},
    ]
    decisions = [
        {"cluster_id": "c1", "assigned_label": "Unknown_2", "decision_state": "UNKNOWN"},
        {"cluster_id": "c2", "assigned_label": "Unknown_1", "decision_state": "UNKNOWN"},
    ]
    progressive = [
        {**predicted[0], **decisions[0], "observation_end_sec": 1},
        {**predicted[1], **decisions[1], "observation_end_sec": 2},
    ]
    metrics = score_recording(reference_turns=refs, predicted_turns=predicted, local_to_global={"SPK00": "g0", "SPK01": "g1"}, speaker_states={"g0": {"identity_state": "UNKNOWN", "unknown_reference_id": "ref0"}, "g1": {"identity_state": "UNKNOWN", "unknown_reference_id": "ref1"}}, final_decisions=decisions, progressive_decisions=progressive)
    assert metrics["unknown_rejection_rate"] == 1.0
    assert metrics["false_known_rate"] == 0.0
