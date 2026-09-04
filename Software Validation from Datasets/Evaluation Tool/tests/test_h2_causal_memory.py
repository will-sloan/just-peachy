from __future__ import annotations

from copy import deepcopy

import pytest

from app.h2_product_program.causal_memory import (
    CAUSAL_MEMORY_BINDING_SCHEMA_VERSION,
    CAUSAL_MEMORY_OUTCOME_SCHEMA_VERSION,
    CAUSAL_MEMORY_SCHEMA_VERSION,
    CausalCellSpec,
    calibrate_reconciliation_policy,
    declared_memory_cells,
    execute_causal_primitive_cell,
    exact_evidence_coverage,
    exact_short_turn_coverage,
    load_exact_evidence_directory,
    load_exact_runtime_cell,
    score_runtime_outcomes,
    validate_source_binding,
    write_exact_runtime_cell,
)
from app.h2_product_program.contracts import H2ProgramError
from app.h2_product_program.io import canonical_sha256
from app.full_pipeline.identity import IdentityPolicy


def _events() -> list[dict[str, object]]:
    return [
        {
            "event_id": "evt-1",
            "event_sequence": 1,
            "event_type": "anonymous_speaker",
            "anonymous_speaker_id": "cluster-a",
        },
        {
            "event_id": "evt-2",
            "event_sequence": 2,
            "event_type": "identity_evidence",
            "anonymous_speaker_id": "cluster-a",
        },
    ]


def _binding(events: list[dict[str, object]]) -> dict[str, object]:
    core: dict[str, object] = {
        "schema_version": CAUSAL_MEMORY_BINDING_SCHEMA_VERSION,
        "split": "development",
        "evaluation_material_inspected": False,
        "assignment_sha256": "a" * 64,
        "source_result_sha256": "b" * 64,
        "runtime_config_sha256": "c" * 64,
        "runtime_implementation_sha256": "d" * 64,
        "runtime_event_log_sha256": canonical_sha256(events),
        "neural_cache_manifest_sha256": "e" * 64,
        "reference_manifest_sha256": "f" * 64,
        "case_sha256_by_id": {
            "case-cal": "1" * 64,
            "case-sel": "2" * 64,
        },
        "case_role_by_id": {
            "case-cal": "calibration",
            "case-sel": "selection",
        },
        "speaker_ids_by_role": {
            "calibration": ["speaker-cal"],
            "selection": ["speaker-sel"],
        },
        "active_roster_narrowed_gallery": False,
        "full_gallery_safety_enforced": True,
        "shared_neural_cache_reuse": True,
    }
    return {**core, "binding_sha256": canonical_sha256(core)}


def _outcome(
    cell: CausalCellSpec,
    *,
    case_id: str = "case-sel",
    reference_speaker: str = "speaker-sel",
    returning: bool = False,
    short: bool = False,
    display: str | None = "Alice",
    reference_id: str | None = "Alice",
    truth: str = "KNOWN",
    cluster: str = "cluster-a",
) -> dict[str, object]:
    duration = 0.4 if short else 1.5
    return {
        "schema_version": CAUSAL_MEMORY_OUTCOME_SCHEMA_VERSION,
        "cell_id": cell.cell_id,
        "causal_executor": "PipelineCoordinator",
        "decision_used_reference": False,
        "runtime_config_sha256": "c" * 64,
        "case_id": case_id,
        "effective_calibration_role": (
            "calibration" if case_id == "case-cal" else "selection"
        ),
        "source_case_sha256": "1" * 64 if case_id == "case-cal" else "2" * 64,
        "source_event_ids": ["evt-1", "evt-2"],
        "identity_decision_attempted": True,
        "full_gallery_enrolled_ids": ["Alice", "Bob"],
        "scored_gallery_enrolled_ids": ["Bob", "Alice"],
        "active_roster_narrowed_gallery": False,
        "active_roster_prior_applied": False,
        "active_roster_speaker_ids": [],
        "full_gallery_completed_before_decision": True,
        "turn_id": f"{case_id}:turn",
        "turn_start_sec": 1.0,
        "turn_end_sec": 1.0 + duration,
        "turn_duration_sec": duration,
        "first_name_latency_sec": 0.0 if display else None,
        "confirmed_name_latency_sec": 0.1 if display else None,
        "last_verified_age_sec": 0.2,
        "embedding_compute_sec": 0.04,
        "compute_saved_sec": 0.04 if short else 0.0,
        "embedding_calls": 0 if short else 1,
        "embedding_calls_avoided": 1 if short else 0,
        "word_count": 2,
        "bounded_cluster_count": 2,
        "bounded_identity_history_count": 5,
        "bounded_roster_count": 0,
        "returning_turn": returning,
        "short_turn": short,
        "inherited_name": short and display is not None,
        "inherited_from_full_gallery_evidence": short and display is not None,
        "fresh_identity_evidence_used": not short,
        "stale_inheritance": False,
        "false_inheritance": bool(display and display != reference_id),
        "new_speaker_lockout": truth == "UNKNOWN" and display is not None,
        "fragmented_reference_speaker": False,
        "reentry_consistent": returning,
        "correction_observed": False,
        "retraction_observed": False,
        "expiry_observed": False,
        "confidence_decay_applied": False,
        "confidence_decay_policy_enabled": cell.memory_level
        in {"M4_ACTIVE_ROSTER_DECAY", "M5_CLUSTER_RECONCILIATION"},
        "cluster_reconciliation_applied": False,
        "cluster_reconciliation_similarity": None,
        "cluster_reconciliation_survivor": None,
        "cluster_reconciliation_contaminated": False,
        "short_turn_policy": (
            cell.short_turn_policy or "C_CONFIRMED_NAME_INHERITANCE"
        )
        if short
        else None,
        "duration_bin": "LT_0P5" if short else None,
        "contradiction_outcome": "NONE",
        "reference_truth_state": truth,
        "reference_enrolled_id": reference_id,
        "reference_global_speaker_id": reference_speaker,
        "anonymous_speaker_id": cluster,
        "display_enrolled_id": display,
        "display_label": display or "Speaker_1",
    }


def _metadata(cell: CausalCellSpec) -> dict[str, object]:
    return {
        "completion_state": "complete",
        "runtime_tuning_sha256": "c" * 64,
        "memory_level": cell.memory_level,
        "identity_expiry_sec": 60.0,
        "identity_expiry_mode": "source_clock",
        "short_turn_policy": cell.short_turn_policy,
    }


def test_declared_memory_grid_is_complete_and_missing_evidence_stays_explicit() -> None:
    cells = declared_memory_cells()
    assert len(cells) == 30
    assert len({cell.cell_id for cell in cells}) == 30

    coverage = exact_evidence_coverage({})

    assert len(coverage) == 31
    assert all(row["status"] == "UNSUPPORTED_CAPABILITY" for row in coverage)
    assert all(row["metrics"] is None for row in coverage)
    m4 = [row for row in coverage if row["memory_level"] == "M4_ACTIVE_ROSTER_DECAY"]
    m5 = [row for row in coverage if row["memory_level"] == "M5_CLUSTER_RECONCILIATION"]
    assert len(m4) == len(m5) == 5
    assert all("no checksum-valid" in str(row["reason"]) for row in m4)
    assert all("no checksum-valid" in str(row["reason"]) for row in m5)
    decay = [row for row in coverage if row["cell_id"] == "CONFIDENCE_BASED_DECAY"]
    assert len(decay) == 1
    assert decay[0]["status"] == "UNSUPPORTED_CAPABILITY"
    assert decay[0]["metrics"] is None
    assert decay[0]["identity_expiry_mode"] == "confidence_based"


def test_exact_cell_is_immutable_restart_safe_and_checksum_bound(tmp_path) -> None:
    events = _events()
    cell = CausalCellSpec(
        "M3_SHORT_TURN", 60.0, "C_CONFIRMED_NAME_INHERITANCE"
    )
    path = tmp_path / "cell.json"
    outcome = _outcome(cell, returning=True, short=True)

    first = write_exact_runtime_cell(
        path,
        cell=cell,
        source_binding=_binding(events),
        runtime_events=events,
        outcomes=[outcome],
        execution_metadata=_metadata(cell),
    )
    second = write_exact_runtime_cell(
        path,
        cell=cell,
        source_binding=_binding(events),
        runtime_events=events,
        outcomes=[outcome],
        execution_metadata=_metadata(cell),
    )
    loaded = load_exact_runtime_cell(
        path, expected_cell=cell, expected_assignment_sha256="a" * 64
    )

    assert first["write_disposition"] == "CREATED"
    assert second["write_disposition"] == "REUSED"
    assert loaded["schema_version"] == CAUSAL_MEMORY_SCHEMA_VERSION
    assert loaded["runtime_event_payload_sha256"] == canonical_sha256(events)
    assert loaded["truth_used_only_after_runtime_decisions"] is True
    assert loaded["metrics"]["warm_reacquisition_rate"] == 1.0
    assert loaded["metrics_by_development_role"]["selection"][
        "warm_reacquisition_rate"
    ] == 1.0

    changed = deepcopy(outcome)
    changed["display_enrolled_id"] = "Bob"
    with pytest.raises(ValueError, match="immutable artifact differs"):
        write_exact_runtime_cell(
            path,
            cell=cell,
            source_binding=_binding(events),
            runtime_events=events,
            outcomes=[changed],
            execution_metadata=_metadata(cell),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"split": "evaluation"}, "held-out firewall"),
        ({"evaluation_material_inspected": True}, "held-out firewall"),
        ({"active_roster_narrowed_gallery": True}, "narrowed"),
        ({"full_gallery_safety_enforced": False}, "not enforced"),
        ({"shared_neural_cache_reuse": False}, "shared neural cache"),
    ],
)
def test_source_binding_fails_closed_on_science_and_gallery_violations(
    mutation: dict[str, object], message: str
) -> None:
    binding = _binding(_events())
    binding.update(mutation)
    binding.pop("binding_sha256", None)
    binding["binding_sha256"] = canonical_sha256(binding)

    with pytest.raises(H2ProgramError, match=message):
        validate_source_binding(binding)


def test_source_binding_rejects_speaker_overlap() -> None:
    binding = _binding(_events())
    binding["speaker_ids_by_role"] = {
        "calibration": ["same"],
        "selection": ["same"],
    }
    binding.pop("binding_sha256", None)
    binding["binding_sha256"] = canonical_sha256(binding)

    with pytest.raises(H2ProgramError, match="overlap"):
        validate_source_binding(binding)


def test_exact_outcome_rejects_projection_missing_event_and_gallery_narrowing(
    tmp_path,
) -> None:
    events = _events()
    cell = CausalCellSpec("M2_CONFIRMED_NAME", 60.0)
    base = _outcome(cell)

    invalid_rows = []
    projection = deepcopy(base)
    projection["live_projection"] = {"fabricated": True}
    invalid_rows.append((projection, "live_projection"))
    missing = deepcopy(base)
    missing["source_event_ids"] = ["not-an-event"]
    invalid_rows.append((missing, "actual runtime events"))
    narrowed = deepcopy(base)
    narrowed["scored_gallery_enrolled_ids"] = ["Alice"]
    invalid_rows.append((narrowed, "complete enrolled gallery"))
    truth_leak = deepcopy(base)
    truth_leak["decision_used_reference"] = True
    invalid_rows.append((truth_leak, "may not use reference"))

    for index, (row, message) in enumerate(invalid_rows):
        with pytest.raises(H2ProgramError, match=message):
            write_exact_runtime_cell(
                tmp_path / f"invalid-{index}.json",
                cell=cell,
                source_binding=_binding(events),
                runtime_events=events,
                outcomes=[row],
                execution_metadata=_metadata(cell),
            )


def test_generic_no_decision_allows_empty_scored_gallery_but_inheritance_is_anchored(
    tmp_path,
) -> None:
    events = _events()
    cell = CausalCellSpec("M0_STATELESS", 60.0)
    generic = _outcome(cell, display=None)
    generic.update(
        {
            "identity_decision_attempted": False,
            "scored_gallery_enrolled_ids": [],
            "inherited_name": False,
            "inherited_from_full_gallery_evidence": False,
            "fresh_identity_evidence_used": False,
        }
    )
    written = write_exact_runtime_cell(
        tmp_path / "generic.json",
        cell=cell,
        source_binding=_binding(events),
        runtime_events=events,
        outcomes=[generic],
        execution_metadata={**_metadata(cell), "memory_level": "M0_STATELESS"},
    )
    assert written["metrics"]["turn_count"] == 1
    assert written["outcomes"][0]["scored_gallery_enrolled_ids"] == []

    unanchored = deepcopy(generic)
    unanchored.update(
        {
            "display_enrolled_id": "Alice",
            "display_label": "Alice",
            "inherited_name": True,
            "inherited_from_full_gallery_evidence": False,
        }
    )
    with pytest.raises(H2ProgramError, match="prior full-gallery anchor"):
        write_exact_runtime_cell(
            tmp_path / "unanchored.json",
            cell=cell,
            source_binding=_binding(events),
            runtime_events=events,
            outcomes=[unanchored],
            execution_metadata={**_metadata(cell), "memory_level": "M0_STATELESS"},
        )


def test_metrics_cover_returning_short_safety_fragmentation_compute_and_bounds() -> None:
    cell = CausalCellSpec(
        "M3_SHORT_TURN", 60.0, "D_INHERITANCE_WITH_CONTRADICTION_CHECKS"
    )
    first = _outcome(cell, case_id="case-cal", reference_speaker="speaker-cal")
    returning = _outcome(cell, returning=True, short=True)
    fragmented = _outcome(
        cell,
        returning=True,
        short=True,
        cluster="cluster-b",
        display="Bob",
    )
    fragmented["stale_inheritance"] = True
    fragmented["new_speaker_lockout"] = True
    fragmented["fragmented_reference_speaker"] = True
    fragmented["reentry_consistent"] = False
    fragmented["correction_observed"] = True
    fragmented["retraction_observed"] = True
    fragmented["expiry_observed"] = True
    fragmented["contradiction_outcome"] = "BLOCKED_STRONG_REDIM_MISMATCH"

    metrics = score_runtime_outcomes([first, returning, fragmented])

    assert metrics["turn_count"] == 3
    assert metrics["warm_reacquisition_rate"] == 0.5
    assert metrics["short_turn_correct_name_rate"] == 0.5
    assert metrics["stale_inheritance_rate"] == 0.5
    assert metrics["false_inheritance_rate"] == 0.5
    assert metrics["new_speaker_lockout_rate"] == pytest.approx(1 / 3)
    assert metrics["fragmentation_reference_speaker_rate"] == 0.5
    assert metrics["reentry_consistency_rate"] == 0.5
    assert metrics["embedding_calls"] == 1
    assert metrics["embedding_calls_avoided"] == 2
    assert metrics["compute_saved_sec"] == 0.08
    assert metrics["contradiction_outcomes"] == {
        "BLOCKED_STRONG_REDIM_MISMATCH": 1
    }
    assert metrics["expiry_observed_count"] == 1
    assert metrics["maximum_bounded_cluster_count"] == 2
    assert metrics["confidence_decay_status"] == "NOT_ENABLED_FOR_CELL"


def test_m4_m5_can_be_written_only_as_explicit_advanced_measurements(tmp_path) -> None:
    events = _events()
    for level in ("M4_ACTIVE_ROSTER_DECAY", "M5_CLUSTER_RECONCILIATION"):
        cell = CausalCellSpec(level, 60.0)
        reconciliation = (
            {
                "threshold": 0.81,
                "maximum_gap_sec": 45.0,
                "minimum_embeddings_per_cluster": 2,
            }
            if level == "M5_CLUSTER_RECONCILIATION"
            else None
        )
        measured = write_exact_runtime_cell(
            tmp_path / f"{level}.json",
            cell=cell,
            source_binding=_binding(events),
            runtime_events=events,
            outcomes=[_outcome(cell)],
            execution_metadata={
                **_metadata(CausalCellSpec("M3_SHORT_TURN", 60.0)),
                "memory_level": level,
                "confidence_decay": {
                    "half_life_sec": 30.0,
                    "release_floor": 0.25,
                    "source_clock_only": True,
                },
                "reconciliation_policy": reconciliation,
            },
        )
        assert measured["confidence_decay_measured"] is True
        assert measured["active_roster_narrowed_gallery"] is False
        assert measured["cluster_reconciliation_measured"] is (
            level == "M5_CLUSTER_RECONCILIATION"
        )
        row = next(
            value
            for value in exact_evidence_coverage({cell.cell_id: measured})
            if value["cell_id"] == cell.cell_id
        )
        assert row["confidence_decay_half_life_sec"] == 30.0
        assert row["confidence_decay_release_floor"] == 0.25
        assert row["cluster_reconciliation_threshold"] == (
            0.81 if reconciliation else None
        )


def test_directory_loader_and_short_turn_coverage_keep_missing_bins_unsupported(
    tmp_path,
) -> None:
    events = _events()
    cell = CausalCellSpec(
        "M3_SHORT_TURN", 60.0, "C_CONFIRMED_NAME_INHERITANCE"
    )
    write_exact_runtime_cell(
        tmp_path / cell.cell_id / "evidence.json",
        cell=cell,
        source_binding=_binding(events),
        runtime_events=events,
        outcomes=[_outcome(cell, returning=True, short=True)],
        execution_metadata=_metadata(cell),
    )

    loaded = load_exact_evidence_directory(
        tmp_path, expected_assignment_sha256="a" * 64
    )
    coverage = exact_short_turn_coverage(loaded)

    assert set(loaded) == {cell.cell_id}
    assert len(coverage) == 15
    measured = [row for row in coverage if row["status"] == "MEASURED"]
    assert len(measured) == 1
    assert measured[0]["short_turn_policy"] == "C_CONFIRMED_NAME_INHERITANCE"
    assert measured[0]["duration_bin"] == "LT_0P5"
    assert measured[0]["metrics"]["short_turn_correct_name_rate"] == 1.0
    assert sum(row["status"] == "UNSUPPORTED_CAPABILITY" for row in coverage) == 14


def _actual_runtime_events() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case_index, case_id in enumerate(("case-cal", "case-sel")):
        cluster = f"cluster-{case_index}"
        for index, (start, end) in enumerate(((0.0, 1.0), (1.0, 2.0)), start=1):
            anonymous_id = f"{case_id}-anonymous-{index}"
            rows.extend(
                [
                    {
                        "evaluation_case_id": case_id,
                        "event_id": anonymous_id,
                        "event_sequence": index * 2 - 1,
                        "event_type": "anonymous_speaker",
                        "anonymous_speaker_id": cluster,
                        "start_sec": start,
                        "end_sec": end,
                        "unknown_label": "Unknown_1",
                        "overlap": False,
                        "source_turn_ids": [f"speech-{index}_window_000000"],
                        "capture_timestamps": {"audio_end_sec": end},
                    },
                    {
                        "evaluation_case_id": case_id,
                        "event_id": f"{case_id}-evidence-{index}",
                        "event_sequence": index * 2,
                        "event_type": "identity_evidence",
                        "anonymous_speaker_id": cluster,
                        "causation_event_id": anonymous_id,
                        "evidence_duration_sec": 2.0,
                        "candidate_scores": [
                            {
                                "candidate_speaker_id": "Alice",
                                "raw_score": 0.9,
                            },
                            {
                                "candidate_speaker_id": "Bob",
                                "raw_score": 0.1,
                            },
                        ],
                        "quality_gate": {
                            "status": "accepted",
                            "metrics": {"embedding_consistency": 0.9},
                        },
                        "processing_timestamps": {"backend_latency_ms": 40.0},
                        "capture_timestamps": {"audio_end_sec": end},
                    },
                ]
            )
        rows.append(
            {
                "evaluation_case_id": case_id,
                "event_id": f"{case_id}-short",
                "event_sequence": 5,
                "event_type": "anonymous_speaker",
                "anonymous_speaker_id": cluster,
                "start_sec": 2.1,
                "end_sec": 2.4,
                "unknown_label": "Unknown_1",
                "overlap": False,
                "source_turn_ids": [f"short:{case_id}"],
                "capture_timestamps": {"audio_end_sec": 2.4},
            }
        )
    return rows


def _actual_observations() -> list[dict[str, object]]:
    return [
        {
            "split": "development",
            "evaluation_material_inspected": False,
            "status": "VALID",
            "case_id": case_id,
            "anonymous_speaker_id": f"cluster-{index}",
            "effective_calibration_role": role,
            "truth_state": "KNOWN",
            "reference_enrolled_id": "Alice",
            "reference_global_speaker_id": speaker,
            "gallery_enrolled_ids": ["Alice", "Bob"],
            "candidate_raw_cosine_scores": {"Alice": 0.9, "Bob": 0.1},
        }
        for index, (case_id, role, speaker) in enumerate(
            (
                ("case-cal", "calibration", "speaker-cal"),
                ("case-sel", "selection", "speaker-sel"),
            )
        )
    ]


def _identity_policy() -> IdentityPolicy:
    return IdentityPolicy(
        hybrid_label="H2",
        policy_id="test-policy",
        score_threshold=0.5,
        margin_threshold=0.1,
        minimum_evidence_sec=1.0,
        minimum_embedding_consistency=0.35,
        consecutive_passes_to_confirm=2,
        consecutive_failures_to_release=2,
        hysteresis_policy="H1_TWO_CONFIRM_TWO_RELEASE",
    )


def _fragmented_runtime_fixture() -> tuple[
    list[dict[str, object]], list[dict[str, object]]
]:
    gallery = ["Alice", "Bob", "Carol"]
    cluster_specs = (
        ("case-cal-fragments", "calibration", "cal-a", "speaker-cal-a", "Alice", 0.0),
        ("case-cal-fragments", "calibration", "cal-b", "speaker-cal-b", "Bob", 3.0),
        (
            "case-cal-fragments",
            "calibration",
            "cal-a-fragment",
            "speaker-cal-a",
            "Alice",
            6.0,
        ),
        ("case-sel-fragments", "selection", "sel-a", "speaker-sel-a", "Alice", 0.0),
        (
            "case-sel-fragments",
            "selection",
            "sel-a-fragment",
            "speaker-sel-a",
            "Alice",
            4.0,
        ),
    )
    signatures = {
        "Alice": {"Alice": 0.90, "Bob": 0.10, "Carol": 0.20},
        "Bob": {"Alice": 0.08, "Bob": 0.92, "Carol": 0.18},
    }
    events: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    sequence_by_case: dict[str, int] = {}
    for case_id, role, cluster_id, global_speaker, enrolled_id, base_start in cluster_specs:
        observations.append(
            {
                "split": "development",
                "evaluation_material_inspected": False,
                "status": "VALID",
                "case_id": case_id,
                "anonymous_speaker_id": cluster_id,
                "effective_calibration_role": role,
                "truth_state": "KNOWN",
                "reference_enrolled_id": enrolled_id,
                "reference_global_speaker_id": global_speaker,
                "gallery_enrolled_ids": gallery,
                "candidate_raw_cosine_scores": signatures[enrolled_id],
            }
        )
        for window_index in range(2):
            start = base_start + window_index
            end = start + 1.0
            sequence_by_case[case_id] = sequence_by_case.get(case_id, 0) + 1
            anonymous_event_id = f"{case_id}-{cluster_id}-anonymous-{window_index}"
            events.append(
                {
                    "evaluation_case_id": case_id,
                    "event_id": anonymous_event_id,
                    "event_sequence": sequence_by_case[case_id],
                    "event_type": "anonymous_speaker",
                    "anonymous_speaker_id": cluster_id,
                    "start_sec": start,
                    "end_sec": end,
                    "unknown_label": f"Unknown_{cluster_id}",
                    "overlap": False,
                    "source_turn_ids": [f"turn:{cluster_id}:{window_index}"],
                    "capture_timestamps": {"audio_end_sec": end},
                }
            )
            sequence_by_case[case_id] += 1
            events.append(
                {
                    "evaluation_case_id": case_id,
                    "event_id": f"{case_id}-{cluster_id}-evidence-{window_index}",
                    "event_sequence": sequence_by_case[case_id],
                    "event_type": "identity_evidence",
                    "anonymous_speaker_id": cluster_id,
                    "causation_event_id": anonymous_event_id,
                    "evidence_duration_sec": 2.0,
                    "candidate_scores": [
                        {
                            "candidate_speaker_id": speaker_id,
                            "raw_score": score,
                        }
                        for speaker_id, score in signatures[enrolled_id].items()
                    ],
                    "quality_gate": {
                        "status": "accepted",
                        "metrics": {"embedding_consistency": 0.9},
                    },
                    "processing_timestamps": {"backend_latency_ms": 20.0},
                    "capture_timestamps": {"audio_end_sec": end},
                }
            )
    return events, observations


def test_m5_calibration_and_execution_merge_only_causal_same_speaker_fragments() -> None:
    events, observations = _fragmented_runtime_fixture()

    frozen_policy = calibrate_reconciliation_policy(
        runtime_events=events,
        observations=observations,
    )

    assert frozen_policy["evaluation_role_used"] is False
    assert frozen_policy["calibration_positive_pair_count"] == 1
    assert frozen_policy["calibration_negative_pair_count"] == 2
    assert frozen_policy["calibration_false_merge_rate"] <= 0.01
    assert frozen_policy["future_spatial_hook_result_effect"] is False

    outcomes = execute_causal_primitive_cell(
        cell=CausalCellSpec("M5_CLUSTER_RECONCILIATION", 60.0),
        policy=_identity_policy(),
        runtime_config_sha256=canonical_sha256(
            {"test": "m5-causal-reconciliation", "policy": frozen_policy}
        ),
        runtime_events=events,
        observations=observations,
        case_sha256_by_id={
            "case-cal-fragments": "3" * 64,
            "case-sel-fragments": "4" * 64,
        },
        reconciliation_policy=frozen_policy,
    )

    selection_fragment = [
        row
        for row in outcomes
        if row["case_id"] == "case-sel-fragments"
        and row["anonymous_speaker_id"] == "sel-a-fragment"
    ]
    assert selection_fragment
    assert any(row["cluster_reconciliation_applied"] for row in selection_fragment)
    assert all(
        row["cluster_reconciliation_survivor"] == "sel-a"
        for row in selection_fragment
        if row["cluster_reconciliation_applied"]
    )
    assert not any(row["cluster_reconciliation_contaminated"] for row in outcomes)
    assert all(
        row["full_gallery_completed_before_decision"]
        for row in outcomes
        if row["identity_decision_attempted"]
    )


def test_executable_producer_drives_live_manager_for_all_m0_m5_expiry_cells() -> None:
    events = _actual_runtime_events()
    observations = _actual_observations()
    case_hashes = {"case-cal": "1" * 64, "case-sel": "2" * 64}
    produced = {}

    for cell in declared_memory_cells():
        if not cell.executable:
            continue
        outcomes = execute_causal_primitive_cell(
            cell=cell,
            policy=_identity_policy(),
            runtime_config_sha256=canonical_sha256(
                {"cell": cell.to_jsonable(), "policy": "test-policy"}
            ),
            runtime_events=events,
            observations=observations,
            case_sha256_by_id=case_hashes,
            reconciliation_policy=(
                {
                    "evaluation_role_used": False,
                    "threshold": 1.0,
                    "maximum_gap_sec": 120.0,
                    "minimum_embeddings_per_cluster": 2,
                }
                if cell.memory_level == "M5_CLUSTER_RECONCILIATION"
                else None
            ),
        )
        produced[cell.cell_id] = outcomes
        assert outcomes
        assert all(row["causal_executor"] == "SessionIdentityManager" for row in outcomes)
        assert all(row["decision_used_reference"] is False for row in outcomes)
        assert all(
            set(row["scored_gallery_enrolled_ids"])
            in ({"Alice", "Bob"}, set())
            for row in outcomes
        )

    assert len(produced) == 30
    m0_short = next(
        row
        for row in produced["M0_STATELESS__60S"]
        if row["short_turn"] and row["effective_calibration_role"] == "selection"
    )
    m3_short = next(
        row
        for row in produced["M3_SHORT_TURN__60S"]
        if row["short_turn"] and row["effective_calibration_role"] == "selection"
    )
    assert m0_short["display_enrolled_id"] is None
    assert m3_short["display_enrolled_id"] == "Alice"
    assert m3_short["inherited_name"] is True
    assert m3_short["embedding_calls_avoided"] == 1


def test_short_turn_a_is_precisely_unsupported_without_actual_fresh_embedding() -> None:
    cell = CausalCellSpec("M3_SHORT_TURN", 60.0, "A_FRESH_EMBEDDING")

    with pytest.raises(H2ProgramError, match="did not emit a full-gallery"):
        execute_causal_primitive_cell(
            cell=cell,
            policy=_identity_policy(),
            runtime_config_sha256="c" * 64,
            runtime_events=_actual_runtime_events(),
            observations=_actual_observations(),
            case_sha256_by_id={"case-cal": "1" * 64, "case-sel": "2" * 64},
        )


def test_short_turn_d_uses_actual_overlap_contradiction() -> None:
    events = _actual_runtime_events()
    for row in events:
        if row["event_id"] == "case-sel-short":
            row["overlap"] = True
    cell = CausalCellSpec(
        "M3_SHORT_TURN", 60.0, "D_INHERITANCE_WITH_CONTRADICTION_CHECKS"
    )

    outcomes = execute_causal_primitive_cell(
        cell=cell,
        policy=_identity_policy(),
        runtime_config_sha256="c" * 64,
        runtime_events=events,
        observations=_actual_observations(),
        case_sha256_by_id={"case-cal": "1" * 64, "case-sel": "2" * 64},
    )
    short = next(
        row
        for row in outcomes
        if row["turn_id"] == "short:case-sel"
    )

    assert short["display_enrolled_id"] is None
    assert short["contradiction_outcome"] == "BLOCKED_PREDICTED_OVERLAP"
    assert short["contradiction_signals_available"]["xvf_direction_conflict"] is False
