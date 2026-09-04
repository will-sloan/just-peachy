from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.full_pipeline.identity import (
    ClusterCreation,
    IdentityEvidence,
    SessionIdentityManager,
)
from app.full_pipeline_evaluation.worker import _h2_integration_partition
from app.h2_product_program import science
from app.h2_product_program.contracts import H2Job, ProgramPaths
from app.h2_product_program.io import canonical_sha256
from app.h2_product_program.science import (
    OBSERVATION_SCHEMA_VERSION,
    _replay_identity_sequences,
    _short_turn_duration_bin,
    apply_frozen_integration_assignment,
    build_embedding_clustering_coverage,
    build_integrated_enrollment_matrix,
    build_memory_level_coverage,
    build_policy_frontier,
    hierarchical_speaker_case_bootstrap,
    normalize_observation,
    simulate_short_turn_events,
    unsupported_capability_row,
)


def _observation(
    index: int,
    *,
    role: str,
    truth: str,
    speaker: str,
    score: float,
    evidence: float = 2.0,
) -> dict[str, object]:
    return {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "case_id": f"case-{index}",
        "anonymous_speaker_id": "cluster-1",
        "observation_id": f"observation-{index}",
        "truth_state": truth,
        "reference_global_speaker_id": speaker,
        "reference_enrolled_id": "known-a" if truth == "KNOWN" else None,
        "calibration_role": role,
        "status": "VALID",
        "source_time_sec": 3.0,
        "evidence_duration_sec": evidence,
        "embedding_consistency": 0.5,
        "predicted_overlap": False,
        "candidate_raw_cosine_scores": {"known-a": score, "known-b": 0.2},
        "gallery_requested_size": "source_full",
        "gallery_size": 2,
        "split": "development",
        "evaluation_material_inspected": False,
    }


def test_policy_frontier_uses_stranger_speaker_units_and_counts_quality_rejects() -> (
    None
):
    rows = [
        _observation(1, role="calibration", truth="UNKNOWN", speaker="u1", score=0.8),
        _observation(2, role="calibration", truth="UNKNOWN", speaker="u1", score=0.7),
        _observation(3, role="calibration", truth="UNKNOWN", speaker="u2", score=0.6),
        _observation(4, role="selection", truth="UNKNOWN", speaker="u3", score=0.9),
        _observation(
            5,
            role="selection",
            truth="KNOWN",
            speaker="k1",
            score=0.95,
            evidence=0.5,
        ),
    ]

    frontier = build_policy_frontier(
        rows,
        target_fpirs=(0.01,),
        margins=(0.01,),
        evidence_durations=(2.0,),
        consistency_thresholds=(0.35,),
    )

    assert len(frontier) == 1
    result = frontier[0]
    assert result["calibration_unknown_clusters"] == 3
    assert result["calibration_unknown_speakers"] == 2
    assert result["smallest_empirical_fpir_step"] == 0.5
    assert result["target_empirically_resolvable"] is False
    assert result["observed_calibration_fpir"] == 0.0
    assert result["selection_known_clusters"] == 1
    assert result["selection_rejected_known_clusters"] == 1


def test_integration_assignment_overrides_legacy_role_and_is_checksum_bound() -> None:
    rows = [
        _observation(1, role="selection", truth="UNKNOWN", speaker="u1", score=0.5),
        _observation(2, role="calibration", truth="UNKNOWN", speaker="u2", score=0.5),
    ]
    core = {
        "schema_version": "h2-development-integration-partition.v1",
        "outcomes_used": False,
        "reference_content_used": False,
        "evaluation_material_used": False,
        "calibration_case_ids": ["case-1"],
        "selection_case_ids": ["case-2"],
    }
    assignment = {**core, "assignment_sha256": canonical_sha256(core)}

    assigned = apply_frozen_integration_assignment(rows, assignment)

    assert assigned[0]["legacy_calibration_role"] == "selection"
    assert assigned[0]["effective_calibration_role"] == "calibration"
    assert assigned[1]["effective_calibration_role"] == "selection"


def test_v2_integration_assignment_preserves_worker_firewall_and_excludes_cases() -> (
    None
):
    rows = [
        _observation(1, role="selection", truth="UNKNOWN", speaker="u1", score=0.5),
        _observation(2, role="calibration", truth="UNKNOWN", speaker="u2", score=0.5),
    ]
    core = {
        "schema_version": "h2-development-integration-partition.v2",
        "outcomes_used": False,
        "prediction_or_metric_inputs_used": False,
        "reference_speaker_identity_metadata_used": True,
        "reference_transcript_or_audio_content_used": False,
        "evaluation_material_used": False,
        "calibration_case_count": 1,
        "selection_case_count": 1,
        "excluded_cross_cohort_case_count": 1,
        "calibration_case_ids": ["case-1"],
        "selection_case_ids": ["case-2"],
        "excluded_cross_cohort_case_ids": ["case-3"],
        "calibration_speaker_count": 1,
        "selection_speaker_count": 1,
        "calibration_speaker_ids": ["u1"],
        "selection_speaker_ids": ["u2"],
        "speaker_overlap_count": 0,
        "excluded_cases_used_for_calibration_or_selection": False,
    }
    assignment = {**core, "assignment_sha256": canonical_sha256(core)}
    for index, role in enumerate(("calibration", "selection")):
        rows[index]["h2_calibration_role"] = role
        rows[index]["h2_calibration_assignment_sha256"] = assignment[
            "assignment_sha256"
        ]

    assigned = apply_frozen_integration_assignment(rows, assignment)

    assert {row["effective_calibration_role"] for row in assigned} == {
        "calibration",
        "selection",
    }
    assert all(row["h2_observed_speaker_firewall_validated"] for row in assigned)
    excluded = dict(rows[0], case_id="case-3")
    with pytest.raises(science.H2ProgramError, match="excluded cross-cohort"):
        apply_frozen_integration_assignment((*rows, excluded), assignment)


def test_memory_replay_transition_does_not_depend_on_truth() -> None:
    first = normalize_observation(
        _observation(1, role="selection", truth="KNOWN", speaker="k1", score=0.9)
    )
    first["effective_calibration_role"] = "selection"
    changed_truth = dict(first)
    changed_truth["truth_state"] = "UNKNOWN"
    changed_truth["reference_enrolled_id"] = None
    tuning = {
        "score_threshold": 0.5,
        "margin_threshold": 0.01,
        "minimum_evidence_sec": 1.0,
        "minimum_embedding_consistency": 0.35,
        "consecutive_passes_to_confirm": 1,
        "hysteresis": 0.02,
        "identity_expiry_sec": 120.0,
    }

    known = _replay_identity_sequences((first,), tuning)[0]
    unknown = _replay_identity_sequences((changed_truth,), tuning)[0]

    for key in (
        "display_enrolled_id",
        "transition",
        "passes_open_set_gate",
        "top1_candidate_id",
    ):
        assert known[key] == unknown[key]


def test_identity_replay_has_transition_for_transition_live_manager_parity() -> None:
    rows = []
    for index, score in enumerate((0.9, 0.9, 0.1, 0.1), start=1):
        row = normalize_observation(
            {
                **_observation(
                    index,
                    role="selection",
                    truth="KNOWN",
                    speaker="known-a",
                    score=score,
                ),
                "case_id": "parity-case",
                "source_time_sec": float(index),
                "observation_id": f"parity-{index}",
            }
        )
        row["effective_calibration_role"] = "selection"
        rows.append(row)
    tuning = {
        "score_threshold": 0.5,
        "margin_threshold": 0.01,
        "minimum_evidence_sec": 1.0,
        "minimum_embedding_consistency": 0.35,
        "consecutive_passes_to_confirm": 2,
        "consecutive_failures_to_release": 2,
        "hysteresis": 0.02,
        "hysteresis_policy": "H1_TWO_CONFIRM_TWO_RELEASE",
        "identity_expiry_sec": 120.0,
    }

    replay = _replay_identity_sequences(rows, tuning)
    manager = SessionIdentityManager(science._identity_policy_from_tuning(tuning))
    manager.ensure_cluster(ClusterCreation(0, 1, "cluster-1"))
    live = []
    for row in rows:
        live.append(
            manager.observe(
                IdentityEvidence(
                    anonymous_speaker_id="cluster-1",
                    source_time_sec=float(row["source_time_sec"]),
                    evidence_duration_sec=float(row["evidence_duration_sec"]),
                    candidate_scores=dict(row["candidate_raw_cosine_scores"]),
                    embedding_consistency=float(row["embedding_consistency"]),
                    evidence_event_id=str(row["observation_id"]),
                )
            )
        )
        manager.advance_time(float(row["source_time_sec"]))

    assert len(replay) == len(live) == 4
    for replayed, transition in zip(replay, live, strict=True):
        assert replayed["decision_reason"] == transition.decision_reason
        assert replayed["identity_state"] == transition.state.value
        assert replayed["speaker_label"] == transition.speaker_label
        assert replayed["release_count"] == transition.release_count
        assert replayed["required_release_count"] == (transition.required_release_count)
        assert replayed["effective_score_threshold"] == (
            transition.effective_score_threshold
        )
        assert replayed["gallery_candidate_count"] == 2
        assert replayed["active_roster_narrowed_gallery"] is False
        assert replayed["transition_algorithm_used_truth"] is False


def test_replay_matches_coordinator_observe_then_source_clock_expiry_order() -> None:
    rows = []
    for index, source_time in enumerate((1.0, 2.0, 4.0), start=1):
        row = normalize_observation(
            {
                **_observation(
                    index,
                    role="selection",
                    truth="KNOWN",
                    speaker="known-a",
                    score=0.9,
                ),
                "case_id": "frame-order-case",
                "source_time_sec": source_time,
                "observation_id": f"frame-order-{index}",
                "raw_checkpoint_index": index,
            }
        )
        row["effective_calibration_role"] = "selection"
        rows.append(row)
    tuning = {
        "score_threshold": 0.5,
        "margin_threshold": 0.01,
        "minimum_evidence_sec": 1.0,
        "minimum_embedding_consistency": 0.35,
        "consecutive_passes_to_confirm": 2,
        "consecutive_failures_to_release": 2,
        "hysteresis": 0.02,
        "identity_expiry_sec": 2.0,
    }

    replay = _replay_identity_sequences(rows, tuning)

    assert [row["event_kind"] for row in replay] == [
        "identity_evidence",
        "identity_evidence",
        "identity_evidence",
    ]
    assert replay[-1]["decision_reason"] == "confirmed_identity_pass"
    assert replay[-1]["identity_state"] == "CONFIRMED_KNOWN"


def _short_turn_trace() -> tuple[dict[str, object], ...]:
    return (
        {
            "case_id": "short-case",
            "event_id": "evidence-1",
            "event_type": "identity_evidence",
            "source_time_sec": 1.0,
            "anonymous_speaker_id": "cluster-a",
            "evidence_duration_sec": 2.0,
            "candidate_raw_cosine_scores": {"Alice": 0.9, "Bob": 0.1},
            "embedding_consistency": 0.9,
        },
        {
            "case_id": "short-case",
            "event_id": "evidence-2",
            "event_type": "identity_evidence",
            "source_time_sec": 2.0,
            "anonymous_speaker_id": "cluster-a",
            "evidence_duration_sec": 2.0,
            "candidate_raw_cosine_scores": {"Alice": 0.9, "Bob": 0.1},
            "embedding_consistency": 0.9,
        },
        {
            "case_id": "short-case",
            "event_id": "short-lt-half",
            "event_type": "short_turn",
            "source_time_sec": 2.4,
            "turn_start_sec": 2.0,
            "turn_end_sec": 2.4,
            "anonymous_speaker_id": "cluster-a",
            "predicted_overlap": False,
            "strong_contradiction": False,
            "truth_state": "KNOWN",
            "reference_enrolled_id": "Alice",
        },
        {
            "case_id": "short-case",
            "event_id": "short-half-one",
            "event_type": "short_turn",
            "source_time_sec": 3.2,
            "turn_start_sec": 2.45,
            "turn_end_sec": 3.2,
            "anonymous_speaker_id": "cluster-a",
            "predicted_overlap": False,
            "strong_contradiction": False,
            "truth_state": "KNOWN",
            "reference_enrolled_id": "Alice",
        },
        {
            "case_id": "short-case",
            "event_id": "short-one-two",
            "event_type": "short_turn",
            "source_time_sec": 4.5,
            "turn_start_sec": 3.0,
            "turn_end_sec": 4.5,
            "anonymous_speaker_id": "cluster-a",
            "predicted_overlap": False,
            "strong_contradiction": False,
            "truth_state": "KNOWN",
            "reference_enrolled_id": "Alice",
        },
        {
            "case_id": "short-case",
            "event_id": "short-overlap",
            "event_type": "short_turn",
            "source_time_sec": 5.0,
            "turn_start_sec": 4.8,
            "turn_end_sec": 5.0,
            "anonymous_speaker_id": "cluster-a",
            "predicted_overlap": True,
            "strong_contradiction": False,
            "truth_state": "KNOWN",
            "reference_enrolled_id": "Alice",
        },
        {
            "case_id": "short-case",
            "event_id": "short-contradiction",
            "event_type": "short_turn",
            "source_time_sec": 5.4,
            "turn_start_sec": 5.2,
            "turn_end_sec": 5.4,
            "anonymous_speaker_id": "cluster-a",
            "predicted_overlap": False,
            "strong_contradiction": True,
            "truth_state": "KNOWN",
            "reference_enrolled_id": "Alice",
        },
        {
            "case_id": "short-case",
            "event_id": "short-new-cluster",
            "event_type": "short_turn",
            "source_time_sec": 6.0,
            "turn_start_sec": 5.6,
            "turn_end_sec": 6.0,
            "anonymous_speaker_id": "cluster-b",
            "predicted_overlap": False,
            "strong_contradiction": False,
            "truth_state": "UNKNOWN",
            "reference_enrolled_id": None,
        },
        {
            "case_id": "short-case",
            "event_id": "short-exact-two",
            "event_type": "short_turn",
            "source_time_sec": 8.0,
            "turn_start_sec": 6.0,
            "turn_end_sec": 8.0,
            "anonymous_speaker_id": "cluster-a",
            "predicted_overlap": False,
            "strong_contradiction": False,
            "truth_state": "KNOWN",
            "reference_enrolled_id": "Alice",
        },
    )


def _short_turn_tuning(*, expiry: float = 20.0) -> dict[str, object]:
    return {
        "score_threshold": 0.5,
        "margin_threshold": 0.1,
        "minimum_evidence_sec": 1.0,
        "minimum_embedding_consistency": 0.35,
        "consecutive_passes_to_confirm": 2,
        "consecutive_failures_to_release": 2,
        "hysteresis": 0.02,
        "hysteresis_policy": "H1_TWO_CONFIRM_TWO_RELEASE",
        "identity_expiry_sec": expiry,
    }


def test_short_turn_replay_covers_named_policies_bins_and_contradictions() -> None:
    trace = _short_turn_trace()
    results = {
        policy: simulate_short_turn_events(
            trace,
            _short_turn_tuning(),
            short_turn_policy=policy,
            maximum_turn_duration_sec=2.0,
            maximum_real_evidence_age_sec=10.0,
        )
        for policy in science.SHORT_TURN_POLICIES
    }
    confirmed = {row["event_id"]: row for row in results["CONFIRMED_NAME_INHERITANCE"]}
    checked = {
        row["event_id"]: row for row in results["INHERITANCE_WITH_CONTRADICTION_CHECKS"]
    }

    assert {
        confirmed["short-lt-half"]["duration_bin"],
        confirmed["short-half-one"]["duration_bin"],
        confirmed["short-one-two"]["duration_bin"],
    } == set(science.SHORT_TURN_DURATION_BINS)
    assert confirmed["short-lt-half"]["display_enrolled_id"] == "Alice"
    assert confirmed["short-overlap"]["display_enrolled_id"] == "Alice"
    assert confirmed["short-contradiction"]["display_enrolled_id"] == "Alice"
    assert checked["short-lt-half"]["display_enrolled_id"] == "Alice"
    assert checked["short-overlap"]["display_enrolled_id"] is None
    assert checked["short-contradiction"]["display_enrolled_id"] is None
    assert checked["short-new-cluster"]["display_enrolled_id"] is None
    assert confirmed["short-exact-two"]["within_current_turn_duration_gate"] is (False)
    assert confirmed["short-exact-two"]["display_enrolled_id"] is None
    assert all(
        row["display_enrolled_id"] is None
        for row in results["GENERIC_UNTIL_LATER_CORRECTION"]
    )
    assert all(
        row["transition_algorithm_used_truth"] is False
        for values in results.values()
        for row in values
    )
    assert _short_turn_duration_bin(0.499) == "LT_0P5"
    assert _short_turn_duration_bin(0.5) == "GE_0P5_LT_1P0"
    assert _short_turn_duration_bin(1.0) == "GE_1P0_LE_2P0"
    assert _short_turn_duration_bin(2.0) == "GE_1P0_LE_2P0"


def test_short_turn_source_clock_expiry() -> None:
    expired_trace = (
        *_short_turn_trace()[:2],
        {
            "case_id": "short-case",
            "event_id": "expired-short",
            "event_type": "short_turn",
            "source_time_sec": 5.0,
            "turn_start_sec": 4.6,
            "turn_end_sec": 5.0,
            "anonymous_speaker_id": "cluster-a",
            "predicted_overlap": False,
            "strong_contradiction": False,
        },
    )
    expired = simulate_short_turn_events(
        expired_trace,
        _short_turn_tuning(expiry=3.0),
        short_turn_policy="CONFIRMED_NAME_INHERITANCE",
        maximum_turn_duration_sec=2.0,
        maximum_real_evidence_age_sec=10.0,
    )
    assert expired[0]["display_enrolled_id"] is None
    assert expired[0]["same_cluster_last_real_evidence_age_sec"] == 3.0


def test_integrated_enrollment_matrix_has_exact_protocol_bound_coverage() -> None:
    exact = {
        "utterances": 3,
        "total_duration_sec": 10.0,
        "sessions": "single",
        "aggregation": "normalized_mean",
        "quality_filter": "blind_accept",
        "configuration_id": "exact-cell",
        "configuration_identity_hash": "a" * 64,
        "configuration_outcome": "SCORED",
        "source_table": "configuration_results.csv",
        "source_sha256": "b" * 64,
        "fpir": 0.01,
        "dir_rank1": 0.75,
        "valid_rate": 0.99,
        "embedding_vector": [1.0, 2.0],
    }
    rows = build_integrated_enrollment_matrix(
        (exact,), source_bindings=({"source_sha256": "c" * 64},)
    )

    assert len(rows) == 32
    assert len({str(row["cell_id"]) for row in rows}) == 32
    assert sum(row["status"] == "MEASURED" for row in rows) == 1
    assert sum(row["status"] == "UNSUPPORTED_CAPABILITY" for row in rows) == 31
    measured = next(row for row in rows if row["status"] == "MEASURED")
    assert measured["fpir"] == 0.01
    assert measured["dir_rank1"] == 0.75
    assert measured["biometric_vectors_written"] is False
    assert "embedding_vector" not in measured
    assert "template_vectors" not in measured
    for row in rows:
        unsigned = dict(row)
        digest = unsigned.pop("outcome_sha256")
        assert digest == canonical_sha256(unsigned)


def _coverage_job(
    job_id: str,
    *,
    configuration_id: str,
    kind: str = "successive_halving_runtime",
    tuning: dict[str, object] | None = None,
    serial: bool = False,
) -> H2Job:
    return H2Job(
        job_id=job_id,
        phase_index=2,
        phase_name="REDIM_EXECUTION_FRONTIER",
        job_kind=kind,
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id=configuration_id,
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=("case-a",),
        audio_duration_sec=1.0,
        runtime_tuning=tuning or {},
        serial=serial,
    )


def _coverage_paths(tmp_path: Path) -> ProgramPaths:
    root = Path(__file__).resolve().parents[1]
    return ProgramPaths(
        evaluation_root=root,
        workspace=tmp_path / "workspace",
        results_root=tmp_path / "results",
        summary_root=tmp_path / "summary",
        config_path=root / "configs/automated_evaluation/h2_product_program.v1.yaml",
    )


def test_embedding_clustering_contract_accounts_for_every_declared_cell(
    tmp_path: Path,
) -> None:
    jobs = (
        _coverage_job(
            "cluster-low",
            configuration_id="C1_CLUSTER_THRESHOLD_025_SMALL",
            tuning={
                "clustering_threshold": 0.25,
                "short_turn_attach_gap_sec": 0.5,
            },
        ),
        _coverage_job(
            "cluster-high-gap-low",
            configuration_id="C2_CLUSTER_THRESHOLD_045_SMALL",
            tuning={
                "clustering_threshold": 0.45,
                "short_turn_attach_gap_sec": 0.25,
            },
        ),
        _coverage_job(
            "gap-high",
            configuration_id="C4_SHORT_ATTACH_GAP_075_SMALL",
            tuning={
                "clustering_threshold": 0.35,
                "short_turn_attach_gap_sec": 0.75,
            },
        ),
        _coverage_job(
            "r3-parity",
            configuration_id="R3_EXACT_WINDOW_EMBEDDING_REUSE",
            kind="embedding_reuse_parity",
        ),
        _coverage_job(
            "r4-parity",
            configuration_id="R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
            kind="embedding_reuse_parity",
        ),
    )
    state = {"jobs": {job.job_id: {"state": "PENDING"} for job in jobs}}
    rows = build_embedding_clustering_coverage(
        _coverage_paths(tmp_path), state=state, jobs=jobs
    )

    assert len(rows) == 32
    assert len({str(row["cell_id"]) for row in rows}) == 32
    assert {row["status"] for row in rows} == {"UNSUPPORTED_CAPABILITY"}
    assert {row["value"] for row in rows if row["axis"] == "clustering_threshold"} == {
        0.25,
        0.35,
        0.45,
    }
    assert {
        row["value"] for row in rows if row["axis"] == "short_turn_attach_gap_sec"
    } == {0.25, 0.5, 0.75}
    for row in rows:
        assert row["metrics_computed"] is False
        assert "metrics" not in row
        unsigned = dict(row)
        digest = unsigned.pop("outcome_sha256")
        assert digest == canonical_sha256(unsigned)


def test_accuracy_runtime_is_not_relabelled_as_matched_resource_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    accuracy = _coverage_job(
        "r1-accuracy",
        configuration_id="R1_TWO_INDEPENDENT_MODELS_FULL",
        tuning={"redim_execution_strategy": "R1_TWO_INDEPENDENT_MODELS"},
    )
    resource = _coverage_job(
        "r1-resource",
        configuration_id="R1_TWO_INDEPENDENT_MODELS_MATCHED_SERIAL_RESOURCE",
        kind="resource_runtime",
        tuning={"redim_execution_strategy": "R1_TWO_INDEPENDENT_MODELS"},
        serial=True,
    )
    jobs = (accuracy, resource)
    state = {
        "jobs": {
            accuracy.job_id: {
                "state": "COMPLETE",
                "result_path": str(tmp_path),
                "result_sha256": "d" * 64,
            },
            resource.job_id: {"state": "PENDING"},
        }
    }
    monkeypatch.setattr(
        science,
        "_completed_result_root",
        lambda _state, _job: (tmp_path, "d" * 64),
    )
    monkeypatch.setattr(science, "_require_valid_result_tree", lambda _root: None)

    rows = build_embedding_clustering_coverage(
        _coverage_paths(tmp_path), state=state, jobs=jobs
    )
    r1 = next(
        row
        for row in rows
        if row["axis"] == "redim_execution_strategy"
        and row["value"] == "R1_TWO_INDEPENDENT_MODELS"
    )
    assert r1["status"] == "MEASURED"
    assert r1["evidence_class"] == "accuracy_development"
    assert r1["matched_resource_evidence"] is False

    state["jobs"][resource.job_id] = {
        "state": "COMPLETE",
        "result_path": str(tmp_path),
        "result_sha256": "e" * 64,
    }
    rows = build_embedding_clustering_coverage(
        _coverage_paths(tmp_path), state=state, jobs=jobs
    )
    r1 = next(
        row
        for row in rows
        if row["axis"] == "redim_execution_strategy"
        and row["value"] == "R1_TWO_INDEPENDENT_MODELS"
    )
    assert r1["matched_resource_evidence"] is True
    assert len(r1["source_bindings"]) == 2


def test_unsupported_capability_has_no_synthetic_metrics_and_is_checksum_bound() -> (
    None
):
    row = unsupported_capability_row(
        study_id="test-study",
        cell_id="missing-cell",
        reason="causal evidence is unavailable",
        axes={"axis": "example", "value": 1},
        source_bindings=({"source_sha256": "f" * 64},),
    )
    assert row["status"] == "UNSUPPORTED_CAPABILITY"
    assert row["metrics_computed"] is False
    assert row["synthetic_metrics_emitted"] is False
    assert "metrics" not in row
    unsigned = dict(row)
    digest = unsigned.pop("outcome_sha256")
    assert digest == canonical_sha256(unsigned)


def test_named_hysteresis_and_memory_cell_contracts_are_exact_and_exhaustive() -> None:
    policy_tuning = {
        "score_threshold": 0.5,
        "margin_threshold": 0.1,
        "minimum_evidence_sec": 1.0,
        "minimum_embedding_consistency": 0.35,
    }
    named = {
        (policy_id, expiry): science._named_hysteresis_tuning(
            policy_tuning,
            policy_id=policy_id,
            expiry_cell=expiry,
        )
        for policy_id in science.NAMED_HYSTERESIS_POLICIES
        for expiry in science.EXPIRY_CELLS
    }
    assert len(named) == 25
    assert named[("H0_ONE_PASS_DIAGNOSTIC", 15.0)]["consecutive_passes_to_confirm"] == 1
    assert (
        named[("H1_TWO_CONFIRM_TWO_RELEASE", 30.0)]["consecutive_failures_to_release"]
        == 2
    )
    assert named[("H3_THREE_CONFIRM_SAFE", 60.0)]["consecutive_passes_to_confirm"] == 3
    assert (
        named[("H4_DURATION_DEPENDENT", "end_of_session")]["identity_expiry_mode"]
        == "end_session"
    )
    for tuning in named.values():
        science._identity_policy_from_tuning(tuning)

    memory = build_memory_level_coverage({"source_sha256": "a" * 64})
    assert len(memory) == 31
    assert len({str(row["cell_id"]) for row in memory}) == 31
    expiry_rows = [row for row in memory if row["cell_id"] != "CONFIDENCE_BASED_DECAY"]
    assert {row["memory_level"] for row in expiry_rows} == set(science.MEMORY_LEVELS)
    assert {row["identity_expiry_sec"] for row in expiry_rows} == set(
        science.EXPIRY_CELLS
    )
    assert {row["status"] for row in memory} == {"UNSUPPORTED_CAPABILITY"}
    assert all(row["metrics_computed"] is False for row in memory)
    decay = next(row for row in memory if row["cell_id"] == "CONFIDENCE_BASED_DECAY")
    assert decay["identity_expiry_mode"] == "confidence_based"
    assert decay["status"] == "UNSUPPORTED_CAPABILITY"


def test_hierarchical_bootstrap_is_deterministic_and_preserves_speaker_clusters() -> (
    None
):
    rows = [
        {
            "job_id": "heldout",
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "mode": "H2_SESSION_MEMORY_ENHANCED",
            "case_id": "c1",
            "source_key": "controlled_v1",
            "reference_speaker_ids": ["s1", "s2"],
            "category": "asr",
            "metric_id": "wer",
            "status": "computed",
            "value": 0.5,
            "numerator": 2.0,
            "denominator": 4.0,
        },
        {
            "job_id": "heldout",
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "mode": "H2_SESSION_MEMORY_ENHANCED",
            "case_id": "c2",
            "source_key": "controlled_v1",
            "reference_speaker_ids": ["s1"],
            "category": "asr",
            "metric_id": "wer",
            "status": "computed",
            "value": 0.0,
            "numerator": 0.0,
            "denominator": 4.0,
        },
    ]

    first = hierarchical_speaker_case_bootstrap(rows, repetitions=50, seed=7)
    second = hierarchical_speaker_case_bootstrap(rows, repetitions=50, seed=7)

    assert first == second
    assert first[0]["reference_speaker_cluster_count"] == 2
    assert first[0]["case_count"] == 2
    assert first[0]["resampling_unit"] == (
        "whole_speaker_cluster_all_probes_with_case_fallback"
    )
    assert first[0]["within_speaker_case_resampling"] is False
    assert first[0]["point_estimate"] == 0.25


def test_worker_h2_partition_is_development_only_and_exhaustive() -> None:
    core = {
        "schema_version": "h2-development-integration-partition.v1",
        "outcomes_used": False,
        "reference_content_used": False,
        "evaluation_material_used": False,
        "calibration_case_ids": ["c1"],
        "selection_case_ids": ["c2"],
    }
    partition = {**core, "assignment_sha256": canonical_sha256(core)}
    contract = {"h2_development_integration_partition": partition}
    cases = ({"case_id": "c1"}, {"case_id": "c2"})

    result = _h2_integration_partition(
        contract, job=SimpleNamespace(split="development"), cases=cases
    )

    assert result == partition
    with pytest.raises(ValueError, match="outside development"):
        _h2_integration_partition(
            contract, job=SimpleNamespace(split="evaluation"), cases=cases
        )


def test_every_science_selector_puts_wrong_known_before_stranger_risk() -> None:
    common = {
        "selection_tpir": 0.8,
        "selection_fnir": 0.2,
        "minimum_evidence_sec": 2.0,
        "minimum_embedding_consistency": 0.35,
        "margin_threshold": 0.03,
        "score_threshold": 0.5,
    }
    safer_known = {
        **common,
        "selection_wrong_known_rate": 0.01,
        "selection_unknown_speaker_fpir": 0.20,
        "selection_stranger_fpir": 0.20,
    }
    safer_stranger = {
        **common,
        "selection_wrong_known_rate": 0.02,
        "selection_unknown_speaker_fpir": 0.00,
        "selection_stranger_fpir": 0.00,
    }
    assert (
        min((safer_known, safer_stranger), key=science._open_set_policy_selection_key)
        is safer_known
    )

    hysteresis_common = {
        "selection_wrong_known_dwell_rate": 0.01,
        "selection_premature_wrong_name_event_count": 0,
        "selection_harmful_known_to_known_switch_count": 0,
        "selection_stranger_false_known_dwell_rate": 0.0,
        "selection_identity_oscillation_count": 0,
        "selection_identity_revision_rate": 0.0,
        "selection_never_identified_rate": 0.0,
        "selection_correct_known_rate": 0.9,
        "selection_first_correct_latency_sec": 1.0,
        "identity_expiry_sec": 30.0,
        "hysteresis_policy": "H1_TWO_CONFIRM_TWO_RELEASE",
    }
    hysteresis_known = {
        **hysteresis_common,
        "selection_wrong_known_rate": 0.01,
        "selection_unknown_speaker_fpir": 0.20,
    }
    hysteresis_stranger = {
        **hysteresis_common,
        "selection_wrong_known_rate": 0.02,
        "selection_unknown_speaker_fpir": 0.00,
    }
    assert (
        min(
            (hysteresis_known, hysteresis_stranger),
            key=science._hysteresis_selection_key,
        )
        is hysteresis_known
    )

    memory_common = {
        "selection_false_inheritance_rate": 0.0,
        "selection_stale_inheritance_rate": 0.0,
        "selection_new_speaker_lockout_rate": 0.0,
        "selection_correct_known_turn_rate": 0.9,
        "selection_returning_turn_name_latency_sec_mean": 1.0,
        "selection_reentry_consistency_rate": 0.9,
        "identity_expiry_sec": 30.0,
        "memory_level": "M3_SHORT_TURN",
    }
    memory_known = {
        **memory_common,
        "selection_wrong_known_turn_rate": 0.01,
        "selection_stranger_false_known_turn_rate": 0.20,
    }
    memory_stranger = {
        **memory_common,
        "selection_wrong_known_turn_rate": 0.02,
        "selection_stranger_false_known_turn_rate": 0.00,
    }
    assert (
        min((memory_known, memory_stranger), key=science._memory_selection_key)
        is memory_known
    )

    short_common = {
        "false_inheritance_rate": 0.0,
        "stale_inheritance_rate": 0.0,
        "new_speaker_lockout_rate": 0.0,
        "short_turn_correct_name_rate": 0.9,
    }
    short_known = {
        "cell": SimpleNamespace(short_turn_policy="A_FRESH_EMBEDDING"),
        "metrics": {
            **short_common,
            "wrong_known_turn_rate": 0.01,
            "stranger_false_known_turn_rate": 0.20,
        },
    }
    short_stranger = {
        "cell": SimpleNamespace(short_turn_policy="B_ANONYMOUS_CLUSTER_INHERITANCE"),
        "metrics": {
            **short_common,
            "wrong_known_turn_rate": 0.02,
            "stranger_false_known_turn_rate": 0.00,
        },
    }
    assert (
        min((short_known, short_stranger), key=science._short_turn_selection_key)
        is short_known
    )
    assert science.TRANSCRIPT_POLICY_PRIORITY[:2] == (
        ("wrong_known_time_sec", "min"),
        ("stranger_false_known_time_sec", "min"),
    )
