from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path
import sys
from types import SimpleNamespace
from types import ModuleType

import numpy as np
import pytest

try:  # The focused policy tests do not decode audio.
    import soundfile as _soundfile  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - minimal CI/unit environment
    sys.modules["soundfile"] = ModuleType("soundfile")
try:
    import torch as _torch  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - no inference in this file
    sys.modules["torch"] = ModuleType("torch")

from app.full_pipeline.alignment import (
    SpeakerRegion,
    TranscriptSpan,
    TranscriptSpeakerAligner,
)
from app.full_pipeline.clustering import OnlineClusterConfig, OnlineClusterManager
from app.full_pipeline.coordinator import CoordinatorConfig, StreamingPipelineCoordinator
from app.full_pipeline.enrollment import EnrollmentTemplate, RuntimeEnrollmentProfile
from app.full_pipeline.factory import build_file_runtime, build_microphone_runtime
from app.full_pipeline.identity import (
    FROZEN_IDENTITY_POLICIES,
    ClusterCreation,
    IdentityEvidence,
    IdentityState,
    SessionIdentityManager,
)
from app.full_pipeline.models import ComponentRuntimeIdentity, EmbeddingResult
from app.full_pipeline.paragraphs import build_paragraphs
from app.full_pipeline.product_modes import (
    BoundedSessionMemory,
    H2ProductMode,
    H2RuntimeTuning,
)


def _evidence(event_id: str, at: float) -> IdentityEvidence:
    return IdentityEvidence(
        anonymous_speaker_id="anon-1",
        source_time_sec=at,
        evidence_duration_sec=2.0,
        candidate_scores={"Alice": 0.9},
        embedding_consistency=0.9,
        evidence_event_id=event_id,
    )


def test_runtime_tuning_is_strict_roundtrippable_and_hash_bound() -> None:
    tuning = H2RuntimeTuning(
        product_mode=H2ProductMode.KNOWN_ONLY,
        boundary_correction_ms=500,
        paragraph_policy="T4_SPEAKER_CHANGE_DOMINANT",
    )
    payload = {**tuning.to_jsonable(), "identity_sha256": tuning.identity_sha256}
    restored = H2RuntimeTuning.from_mapping(payload)
    assert restored == tuning
    assert hash(restored) == hash(tuning)
    assert restored.behavior.public_unknown_label("Unknown_7") == "Unknown"
    assert (
        replace(restored, product_mode=H2ProductMode.SESSION_ANONYMOUS)
        .behavior.public_unknown_label("Unknown_7")
        == "Speaker_7"
    )
    assert restored.behavior.short_turn_inheritance is False
    assert (
        replace(restored, product_mode=H2ProductMode.SESSION_MEMORY_ENHANCED)
        .behavior.short_turn_inheritance
        is True
    )
    with pytest.raises(ValueError, match="unsupported runtime tuning keys"):
        H2RuntimeTuning.from_mapping({"not_executable": True})
    reuse = H2RuntimeTuning(
        redim_execution_strategy="R3_EXACT_WINDOW_EMBEDDING_REUSE"
    )
    assert reuse.to_jsonable()["schema_version"] == "h2-runtime-tuning.v3"
    assert H2RuntimeTuning.from_mapping(reuse.to_jsonable()) == reuse
    legacy_reuse = reuse.to_jsonable()
    legacy_reuse["schema_version"] = "h2-runtime-tuning.v2"
    legacy_reuse.pop("embedding_reuse_qualification_sha256")
    with pytest.raises(ValueError, match="legacy runtime tuning cannot identify R3/R4"):
        H2RuntimeTuning.from_mapping(legacy_reuse)


def test_v1_runtime_tuning_hash_cannot_authorize_unbound_v2_policy_fields() -> None:
    tuning = H2RuntimeTuning()
    payload = tuning.to_jsonable()
    payload["schema_version"] = "h2-runtime-tuning.v1"
    for field in (
        "consecutive_failures_to_release",
        "identity_expiry_mode",
        "hysteresis_policy",
        "adaptive_early_max_evidence_sec",
        "adaptive_standard_evidence_sec",
        "adaptive_early_score_delta",
        "adaptive_early_margin_delta",
        "adaptive_medium_score_delta",
        "adaptive_medium_margin_delta",
        "memory_level",
    ):
        payload.pop(field)
    payload["identity_sha256"] = tuning._legacy_v1_identity_sha256()

    restored = H2RuntimeTuning.from_mapping(payload)
    assert restored == tuning
    payload["hysteresis_policy"] = "H0_ONE_PASS_DIAGNOSTIC"
    with pytest.raises(ValueError, match="unbound v2 fields"):
        H2RuntimeTuning.from_mapping(payload)


def test_corrected_h1_gets_new_v2_policy_identity_without_reusing_frozen_hash() -> None:
    frozen = FROZEN_IDENTITY_POLICIES["H2"]
    assert frozen.hysteresis_policy == "LEGACY_TWO_CONFIRM_ONE_RELEASE"
    corrected = H2RuntimeTuning(
        hysteresis_policy="H1_TWO_CONFIRM_TWO_RELEASE",
        consecutive_passes_to_confirm=2,
        consecutive_failures_to_release=2,
    ).apply_identity_policy(frozen)

    assert corrected.hysteresis_policy == "H1_TWO_CONFIRM_TWO_RELEASE"
    assert corrected.required_release_passes == 2
    assert corrected.policy_id.startswith("h2_product_runtime.v2:")
    assert corrected.decision_policy_sha256 != frozen.decision_policy_sha256
    assert corrected.frozen_anchor is False


def test_m0_through_m5_behavior_is_executable_and_advanced_cells_require_policy() -> None:
    expected = {
        "M0_STATELESS": (False, False, False, False),
        "M1_CLUSTER": (True, False, False, False),
        "M2_CONFIRMED_NAME": (True, True, False, False),
        "M3_SHORT_TURN": (True, True, True, False),
    }
    for memory_level, flags in expected.items():
        behavior = H2RuntimeTuning(memory_level=memory_level).behavior
        assert (
            behavior.anonymous_profiles_across_turns,
            behavior.confirmed_name_inheritance,
            behavior.short_turn_inheritance,
            behavior.active_roster,
        ) == flags
    with pytest.raises(ValueError, match="calibrated confidence decay"):
        H2RuntimeTuning(memory_level="M4_ACTIVE_ROSTER_DECAY")
    m4 = H2RuntimeTuning(
        memory_level="M4_ACTIVE_ROSTER_DECAY",
        confidence_decay_half_life_sec=30.0,
    )
    assert m4.to_jsonable()["schema_version"] == "h2-runtime-tuning.v4"
    assert H2RuntimeTuning.from_mapping(m4.to_jsonable()) == m4
    assert (
        m4.behavior.anonymous_profiles_across_turns,
        m4.behavior.confirmed_name_inheritance,
        m4.behavior.short_turn_inheritance,
        m4.behavior.active_roster,
    ) == (True, True, True, True)
    with pytest.raises(ValueError, match="reconciliation threshold"):
        H2RuntimeTuning(
            memory_level="M5_CLUSTER_RECONCILIATION",
            confidence_decay_half_life_sec=30.0,
        )
    m5 = H2RuntimeTuning(
        memory_level="M5_CLUSTER_RECONCILIATION",
        confidence_decay_half_life_sec=30.0,
        cluster_reconciliation_threshold=0.75,
    )
    assert m5.behavior.active_roster is True


def test_active_roster_is_observational_and_requires_full_gallery_safety() -> None:
    memory = BoundedSessionMemory(H2RuntimeTuning())
    memory.observe_cluster(
        anonymous_speaker_id="cluster-a",
        public_label="Speaker_1",
        source_time_sec=1.0,
    )
    snapshot = memory.snapshot()
    assert snapshot["scoring_effect"] is False
    assert snapshot["full_gallery_safety_check_required"] is True
    assert len(snapshot["roster"]) == 1


def test_m4_roster_prior_reorders_but_never_narrows_full_gallery() -> None:
    tuning = H2RuntimeTuning(
        memory_level="M4_ACTIVE_ROSTER_DECAY",
        confidence_decay_half_life_sec=30.0,
    )
    memory = BoundedSessionMemory(tuning)
    manager = SessionIdentityManager(
        replace(FROZEN_IDENTITY_POLICIES["H2"], identity_expiry_sec=120.0)
    )
    manager.ensure_cluster(ClusterCreation(0, 1, "anon-1"))
    memory.observe_cluster(
        anonymous_speaker_id="anon-1",
        public_label="Speaker_1",
        source_time_sec=0.0,
    )
    memory.observe_identity(manager.observe(_evidence("ev-1", 1.0)))
    memory.observe_identity(manager.observe(_evidence("ev-2", 2.0)))

    order = memory.full_gallery_search_order(
        ["Bob", "Alice", "Carol"], source_time_sec=3.0
    )
    assert order == ("Alice", "Bob", "Carol")
    assert set(order) == {"Alice", "Bob", "Carol"}
    snapshot = memory.snapshot()
    assert snapshot["scoring_effect"] == "search_order_only"
    assert snapshot["gallery_membership_effect"] is False


def test_m4_source_time_confidence_decay_only_releases_a_name() -> None:
    manager = SessionIdentityManager(
        replace(FROZEN_IDENTITY_POLICIES["H2"], identity_expiry_sec=120.0)
    )
    manager.ensure_cluster(ClusterCreation(0, 1, "anon-1"))
    manager.observe(_evidence("ev-1", 1.0))
    manager.observe(_evidence("ev-2", 2.0))

    assert manager.advance_time(
        3.9,
        confidence_decay_half_life_sec=1.0,
        confidence_decay_release_floor=0.25,
    ) == ()
    released = manager.advance_time(
        4.0,
        confidence_decay_half_life_sec=1.0,
        confidence_decay_release_floor=0.25,
    )
    assert len(released) == 1
    assert released[0].decision_reason == "identity_confidence_decayed"
    assert released[0].state is IdentityState.RELEASED
    assert released[0].known_speaker_id is None
    assert released[0].confidence_strength == pytest.approx(0.25)


def test_factory_exposes_backward_compatible_mode_and_tuning_keywords() -> None:
    for builder in (build_file_runtime, build_microphone_runtime):
        signature = inspect.signature(builder)
        assert signature.parameters["product_mode"].default is None
        assert signature.parameters["runtime_tuning"].default is None


def test_confirmed_short_turn_inheritance_does_not_extend_verification_expiry() -> None:
    manager = SessionIdentityManager(
        replace(FROZEN_IDENTITY_POLICIES["H2"], identity_expiry_sec=3.0),
        maximum_evidence_history_per_cluster=3,
    )
    manager.ensure_cluster(ClusterCreation(0, 1, "anon-1"))
    manager.observe(_evidence("ev-1", 1.0))
    manager.observe(_evidence("ev-2", 2.0))
    inherited = manager.inherit_confirmed_short_turn(
        "anon-1", source_time_sec=2.5, maximum_gap_sec=1.0
    )
    assert inherited is not None
    assert inherited.state is IdentityState.CONFIRMED_KNOWN
    assert inherited.speaker_label == "Alice"
    assert inherited.evidence_event_ids == ("ev-2",)
    assert inherited.decision_reason == "confirmed_name_inherited_short_turn"
    expired = manager.advance_time(5.0)
    assert len(expired) == 1
    assert expired[0].state is IdentityState.RELEASED
    # Existing event-adapter behavior stays backward compatible; the manager's
    # bound real event is available separately to the coordinator.
    assert expired[0].evidence_event_ids == ()
    assert manager.last_evidence_event_id("anon-1") == "ev-2"
    assert len(manager.session_state()["clusters"][0]["evidence_history"]) <= 3


def test_online_cluster_state_has_hard_embedding_and_speaker_bounds() -> None:
    manager = OnlineClusterManager(
        OnlineClusterConfig(
            threshold=0.99,
            maximum_clusters=2,
            maximum_embeddings_per_cluster=2,
        )
    )
    for index in range(4):
        manager.observe(
            window_id=f"same-{index}",
            start_sec=float(index),
            end_sec=float(index + 1),
            embedding=[1.0, 0.0],
        )
    snapshot = manager.snapshot()
    assert snapshot["clusters"][0]["embedding_member_count"] == 2
    for index, vector in enumerate(([0.0, 1.0], [-1.0, 0.0]), start=10):
        manager.observe(
            window_id=f"new-{index}",
            start_sec=float(index),
            end_sec=float(index + 1),
            embedding=vector,
        )
    assert len(manager.snapshot()["clusters"]) <= 2


def test_online_cluster_short_turn_history_is_bounded_without_embeddings() -> None:
    manager = OnlineClusterManager(
        OnlineClusterConfig(
            maximum_clusters=2,
            maximum_embeddings_per_cluster=2,
        )
    )
    for index in range(5):
        manager.observe(
            window_id=f"short-{index}",
            start_sec=float(index) / 10.0,
            end_sec=float(index + 1) / 10.0,
            embedding=None,
        )
    snapshot = manager.snapshot()
    assert len(snapshot["clusters"][0]["member_window_ids"]) == 2
    assert len(snapshot["assignments"]) == 2


def test_m5_reconciles_only_causal_nonoverlapping_voice_fragments() -> None:
    manager = OnlineClusterManager(
        OnlineClusterConfig(
            threshold=0.95,
            reconciliation_enabled=True,
            reconciliation_threshold=0.75,
            reconciliation_max_gap_sec=20.0,
            reconciliation_min_embeddings=2,
        )
    )
    first = manager.observe(
        window_id="a-1", start_sec=0.0, end_sec=1.0, embedding=[1.0, 0.0]
    )
    fragment_1 = manager.observe(
        window_id="b-1", start_sec=10.0, end_sec=11.0, embedding=[0.8, 0.6]
    )
    assert fragment_1.assignment.cluster_id != first.assignment.cluster_id
    reconciled = manager.observe(
        window_id="b-2", start_sec=11.0, end_sec=12.0, embedding=[0.8, 0.6]
    )

    assert reconciled.reconciliation is not None
    assert reconciled.assignment.cluster_id == first.assignment.cluster_id
    assert {
        row.window_id for row in reconciled.reconciliation.revisions
    } == {"b-1", "b-2"}
    assert len(manager.snapshot()["clusters"]) == 1


def test_paragraph_policy_detects_hidden_mode_a_speaker_change() -> None:
    spans = [
        TranscriptSpan(
            span_id="a",
            text="first",
            start_sec=0.0,
            end_sec=0.5,
            state="final",
            timing_provenance="word",
            anonymous_speaker_id="anon-a",
            speaker_label="Unknown",
        ),
        TranscriptSpan(
            span_id="b",
            text="second",
            start_sec=0.5,
            end_sec=1.0,
            state="final",
            timing_provenance="word",
            anonymous_speaker_id="anon-b",
            speaker_label="Unknown",
        ),
    ]
    paragraphs = build_paragraphs(
        spans,
        policy="T4_SPEAKER_CHANGE_DOMINANT",
        pause_sec=0.8,
        maximum_words=80,
    )
    assert len(paragraphs) == 2
    assert paragraphs[1].break_reason == "speaker_change_dominant"


def _identity(component: str) -> ComponentRuntimeIdentity:
    return ComponentRuntimeIdentity(
        component_family=component,
        backend_id=component,
        backend_config_id=component,
        backend_config_sha256="0" * 64,
        pipeline_config_sha256="1" * 64,
        model_id=None,
        model_asset_sha256s=(),
    )


def _coordinator(tmp_path: Path) -> StreamingPipelineCoordinator:
    selection = SimpleNamespace(
        pipeline_id="fullpipe_v1_ag_dr_ir",
        protocol_version="test.v1",
        pipeline_config_sha256="1" * 64,
        runtime_config_sha256="2" * 64,
        identity={
            "backend_id": "redimnet2_b2_speaker_embedding",
            "config_sha256": "3" * 64,
            "model_identity_sha256": "4" * 64,
        },
    )
    coordinator = StreamingPipelineCoordinator(
        config=CoordinatorConfig("session", "recording", tmp_path, telemetry_enabled=False),
        selection=selection,
        source=SimpleNamespace(),
        normalizer=SimpleNamespace(),
        asr=SimpleNamespace(),
        segmenter=SimpleNamespace(),
        diarization_embedder=SimpleNamespace(),
        cluster_manager=OnlineClusterManager(),
        identity_embedder=SimpleNamespace(),
        enrollment_store=SimpleNamespace(),
        identity_manager=SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H2"]),
        transcript_aligner=TranscriptSpeakerAligner("transcript"),
        identities={
            "pipeline": _identity("pipeline"),
            "speaker_matching": _identity("speaker_matching"),
        },
        runtime_tuning=H2RuntimeTuning(),
    )
    coordinator._emit_status = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    coordinator._maybe_write_live_status = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: None
    )
    return coordinator


def _run_calibrated_identity_once(
    coordinator: StreamingPipelineCoordinator,
    tmp_path: Path,
    *,
    emit_diagnostics: bool,
) -> None:
    template = EnrollmentTemplate(
        sample_id="sample-a",
        vector=np.asarray([1.0, 0.0], dtype=np.float32),
        duration_sec=3.0,
        audio_sha256="a" * 64,
        quality={"status": "accepted"},
    )
    coordinator._profiles = (
        RuntimeEnrollmentProfile(
            profile_id="profile-a",
            profile_sha256="b" * 64,
            speaker_id="speaker-a",
            display_label="Speaker A",
            backend_id="redimnet2_b2_speaker_embedding",
            backend_config_sha256="3" * 64,
            model_id="ReDimNet2-B2",
            model_sha256="4" * 64,
            aggregation_method="normalized_mean",
            aggregation_top_k=None,
            template_artifact=tmp_path / "profile-a.npz",
            template_sha256="c" * 64,
            templates=(template,),
            total_duration_sec=3.0,
            within_enrollment_consistency=1.0,
        ),
    )
    coordinator.emit_identity_score_diagnostics = emit_diagnostics
    coordinator.identity_manager.ensure_cluster(ClusterCreation(0.0, 1, "anon-a"))
    coordinator._process_identity(
        "anon-a",
        EmbeddingResult(
            window_id="window-a",
            backend_id="redimnet2_b2_speaker_embedding",
            model_id="ReDimNet2-B2",
            model_sha256="4" * 64,
            vector=np.asarray([1.0, 0.0], dtype=np.float32),
            duration_sec=1.5,
            role="identity_matching",
            quality={"status": "accepted"},
            cache_key=None,
            compute_latency_ms=1.0,
        ),
        1.5,
        {"event_id": "anonymous-a"},
        "window-a",
        predicted_overlap=False,
    )


def test_development_score_diagnostics_are_opt_in_and_do_not_change_decision(
    tmp_path: Path,
) -> None:
    ordinary = _coordinator(tmp_path / "ordinary")
    diagnostic = _coordinator(tmp_path / "diagnostic")
    _run_calibrated_identity_once(ordinary, tmp_path, emit_diagnostics=False)
    _run_calibrated_identity_once(diagnostic, tmp_path, emit_diagnostics=True)

    assert ordinary._calibrated_identity_score_diagnostics == []
    assert len(diagnostic._calibrated_identity_score_diagnostics) == 1
    score_row = diagnostic._calibrated_identity_score_diagnostics[0]
    assert score_row["candidate_raw_cosine_scores"] == {"speaker-a": 1.0}
    assert score_row["predicted_overlap"] is False
    assert score_row["raw_embedding_vectors_present"] is False
    ordinary_payload = ordinary._event_groups["identity_evidence"][-1]
    diagnostic_payload = diagnostic._event_groups["identity_evidence"][-1]
    for key in (
        "top1_candidate_speaker_id",
        "top1_raw_score",
        "top2_candidate_speaker_id",
        "top2_raw_score",
        "top1_top2_margin",
        "decision",
        "threshold_identity",
    ):
        assert ordinary_payload[key] == diagnostic_payload[key]


def test_clear_anonymous_memory_preserves_enrollment_and_optionally_transcript(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    profile = SimpleNamespace(profile_id="permanent-profile")
    coordinator._profiles = (profile,)
    coordinator.identity_manager.ensure_cluster(ClusterCreation(0, 1, "anon-1"))
    coordinator._identity_vectors = {
        "anon-1": {"window": (np.asarray([1.0], dtype=np.float32), 1.0)}
    }
    coordinator.transcript_aligner.append_spans(
        [
            TranscriptSpan(
                span_id="span",
                text="keep me",
                start_sec=0.0,
                end_sec=1.0,
                state="final",
                timing_provenance="word",
            )
        ],
        caused_by_event_ids=["asr"],
        source_time_sec=1.0,
    )
    result = coordinator.clear_anonymous_memory(preserve_transcript=True)
    assert result["permanent_enrollment_preserved"] is True
    assert coordinator._profiles == (profile,)
    assert coordinator.identity_manager.session_state()["cluster_count"] == 0
    assert coordinator._identity_vectors == {}
    assert [row.text for row in coordinator.transcript_aligner.spans] == ["keep me"]

    coordinator.clear_anonymous_memory(preserve_transcript=False)
    assert coordinator.transcript_aligner.spans == ()
    assert coordinator._profiles == (profile,)


def test_expiry_emits_identity_label_event_without_degrading_pipeline(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    manager = coordinator.identity_manager
    manager.ensure_cluster(ClusterCreation(0, 1, "anon-1"))
    manager.observe(_evidence("ev-1", 1.0))
    manager.observe(_evidence("ev-2", 2.0))
    manager.bind_latest_evidence_event("anon-1", "ev-2")
    coordinator._event_groups["identity_evidence"].append(
        {"event_id": "ev-2", "evidence_duration_sec": 2.0}
    )
    expired = manager.advance_time(122.0)[0]
    coordinator._emit_expiry_transition(expired, SimpleNamespace())
    assert coordinator._event_groups["identity_label"][-1]["event_reason"]["code"] == (
        "identity_evidence_expired"
    )
    assert coordinator._event_groups["identity_label"][-1]["identity_state"] == (
        "unknown"
    )
    assert coordinator._state == "created"


def test_boundary_correction_moves_only_bounded_recent_assignment(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)
    original = SpeakerRegion(
        start_sec=0.0,
        end_sec=1.0,
        anonymous_speaker_id="anon-1",
        speaker_label="Speaker_1",
        source_event_id="anonymous-1",
    )
    coordinator._speaker_regions_by_window = {"old-window": original}
    coordinator._speaker_regions = [original]
    coordinator._window_cluster_intervals = {
        "old-window": ("anon-1", 0.0, 1.0)
    }
    coordinator._cluster_intervals = {"anon-1": [(0.0, 1.0)]}
    corrected = coordinator._apply_boundary_correction(
        previous_cluster_id="anon-1",
        next_cluster_id="anon-2",
        original_boundary_sec=1.0,
        correction_ms=500,
        source_window_id="new-window",
    )
    assert corrected == pytest.approx(0.5)
    assert coordinator._speaker_regions_by_window["old-window"].end_sec == (
        pytest.approx(0.5)
    )
    record = coordinator._boundary_corrections[-1]
    assert record["original_boundary_sec"] == 1.0
    assert record["corrected_boundary_sec"] == 0.5
    assert record["changed_assignments"][0]["original_assignment"]["end_sec"] == 1.0
