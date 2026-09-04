from __future__ import annotations

from dataclasses import replace

import pytest

from app.full_pipeline.alignment import (
    ALIGNMENT_AMBIGUOUS,
    ALIGNMENT_TIMESTAMP_INSUFFICIENT,
    SpeakerRegion,
    TimeInterval,
    TranscriptSpan,
    TranscriptSpeakerAligner,
    stable_span_id,
)
from app.full_pipeline.identity import (
    FROZEN_IDENTITY_POLICIES,
    ClusterCreation,
    IdentityEvidence,
    IdentityState,
    SessionIdentityManager,
    UnknownLabelAllocator,
    challenger_policy,
)


def _creation(
    speaker_id: str = "anon-a", *, start: int = 0, sequence: int = 1
) -> ClusterCreation:
    return ClusterCreation(start, sequence, speaker_id)


def _evidence(
    *,
    speaker_id: str = "anon-a",
    at: float,
    scores: dict[str, float],
    event_id: str,
    duration: float = 2.0,
    consistency: float | None = 0.8,
    usable: bool = True,
) -> IdentityEvidence:
    return IdentityEvidence(
        anonymous_speaker_id=speaker_id,
        source_time_sec=at,
        evidence_duration_sec=duration,
        candidate_scores=scores,
        embedding_consistency=consistency,
        evidence_event_id=event_id,
        usable=usable,
    )


def test_frozen_h2_h4_h5_policy_values_are_exact() -> None:
    assert set(FROZEN_IDENTITY_POLICIES) == {"H2", "H4", "H5"}
    assert FROZEN_IDENTITY_POLICIES["H2"].score_threshold == 0.5265351286789879
    assert FROZEN_IDENTITY_POLICIES["H4"].score_threshold == 0.5331755752703802
    assert FROZEN_IDENTITY_POLICIES["H5"].score_threshold == 0.4572960706169966
    for policy in FROZEN_IDENTITY_POLICIES.values():
        assert policy.margin_threshold == 0.03
        assert policy.minimum_evidence_sec == 2.0
        assert policy.minimum_embedding_consistency == 0.35
        assert policy.consecutive_passes_to_confirm == 2
        assert policy.hysteresis_policy == "LEGACY_TWO_CONFIRM_ONE_RELEASE"
        assert policy.required_release_passes == 1
        assert policy.hysteresis == 0.02
        assert policy.identity_expiry_sec == 120.0
        assert policy.calibrated and policy.frozen_anchor


def test_unresolved_challenger_never_invents_a_known_decision() -> None:
    policy = challenger_policy("C7")
    manager = SessionIdentityManager(policy)
    manager.ensure_cluster(_creation())

    transition = manager.observe(
        _evidence(at=2.0, scores={"Alice": 0.99, "Bob": 0.0}, event_id="ev-1")
    )

    assert transition.state is IdentityState.UNKNOWN_INSTANCE
    assert transition.speaker_label == "Unknown_1"
    assert transition.decision_reason == "challenger_calibration_unresolved"
    assert transition.calibration_resolved is False
    with pytest.raises(ValueError, match="calibration_identity"):
        challenger_policy("C7", score_threshold=0.5, margin_threshold=0.03)


def test_confirmation_uses_current_id_hysteresis_and_two_pass_challenger() -> None:
    policy = FROZEN_IDENTITY_POLICIES["H2"]
    manager = SessionIdentityManager(policy)
    manager.ensure_cluster(_creation())

    first = manager.observe(
        _evidence(at=1.0, scores={"Alice": 0.80, "Bob": 0.10}, event_id="ev-1")
    )
    second = manager.observe(
        _evidence(at=2.0, scores={"Alice": 0.81, "Bob": 0.10}, event_id="ev-2")
    )
    assert first.state is IdentityState.TENTATIVE_KNOWN
    assert first.speaker_label == "Alice"
    assert second.state is IdentityState.CONFIRMED_KNOWN
    assert second.speaker_label == "Alice"

    # Bob is Top-1, but its Top-1/Top-2 margin fails.  The hold must inspect
    # Alice's score (the current identity), not Bob's Top-1 score.
    held = manager.observe(
        _evidence(at=3.0, scores={"Alice": 0.52, "Bob": 0.54}, event_id="ev-3")
    )
    assert held.state is IdentityState.CONFIRMED_KNOWN
    assert held.speaker_label == "Alice"
    assert held.hysteresis_applied is True
    assert held.decision_reason == "current_identity_hysteresis_hold"

    pending = manager.observe(
        _evidence(at=4.0, scores={"Alice": 0.20, "Bob": 0.90}, event_id="ev-4")
    )
    changed = manager.observe(
        _evidence(at=5.0, scores={"Alice": 0.20, "Bob": 0.91}, event_id="ev-5")
    )
    assert pending.state is IdentityState.CONFIRMED_KNOWN
    assert pending.speaker_label == "Alice"
    assert pending.decision_reason == "challenger_confirmation_pending"
    assert changed.state is IdentityState.CONFIRMED_KNOWN
    assert changed.speaker_label == "Bob"
    assert changed.decision_reason == "challenger_confirmed"


def test_frozen_hysteresis_uses_product_v2_top1_score_semantics() -> None:
    manager = SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H2"])
    manager.ensure_cluster(_creation())
    manager.observe(
        _evidence(at=1.0, scores={"Alice": 0.80, "Bob": 0.10}, event_id="ev-1")
    )
    manager.observe(
        _evidence(at=2.0, scores={"Alice": 0.81, "Bob": 0.10}, event_id="ev-2")
    )

    # Product-v2 retained the current label when Top-1 (even a challenger)
    # remained above threshold-hysteresis.  Prompt 4 freezes that exact replay
    # behavior instead of silently substituting the current identity's score.
    held = manager.observe(
        _evidence(at=3.0, scores={"Alice": 0.10, "Bob": 0.52}, event_id="ev-3")
    )
    assert held.state is IdentityState.CONFIRMED_KNOWN
    assert held.speaker_label == "Alice"
    assert held.hysteresis_applied is True
    assert held.decision_reason == "current_identity_hysteresis_hold"


def test_expiry_uses_source_clock_and_reidentification_requires_two_passes() -> None:
    manager = SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H5"])
    manager.ensure_cluster(_creation())
    manager.observe(_evidence(at=1.0, scores={"Alice": 0.8}, event_id="ev-1"))
    manager.observe(_evidence(at=2.0, scores={"Alice": 0.8}, event_id="ev-2"))

    assert manager.advance_time(121.999) == ()
    expired = manager.advance_time(122.0)
    assert len(expired) == 1
    assert expired[0].state is IdentityState.RELEASED
    assert expired[0].speaker_label == "Unknown_1"
    assert expired[0].decision_reason == "identity_evidence_expired"

    tentative = manager.observe(
        _evidence(at=123.0, scores={"Alice": 0.8}, event_id="ev-3")
    )
    confirmed = manager.observe(
        _evidence(at=124.0, scores={"Alice": 0.8}, event_id="ev-4")
    )
    assert tentative.state is IdentityState.TENTATIVE_KNOWN
    assert confirmed.state is IdentityState.CONFIRMED_KNOWN
    assert confirmed.speaker_label == "Alice"


def test_named_hysteresis_release_requires_declared_consecutive_failures() -> None:
    corrected_h1 = replace(
        FROZEN_IDENTITY_POLICIES["H2"],
        hysteresis_policy="H1_TWO_CONFIRM_TWO_RELEASE",
        consecutive_failures_to_release=2,
        frozen_anchor=False,
        decision_policy_sha256=None,
    )
    manager = SessionIdentityManager(corrected_h1)
    manager.ensure_cluster(_creation())
    manager.observe(
        _evidence(at=1.0, scores={"Alice": 0.80}, event_id="confirm-1")
    )
    manager.observe(
        _evidence(at=2.0, scores={"Alice": 0.80}, event_id="confirm-2")
    )

    pending = manager.observe(
        _evidence(at=3.0, scores={"Alice": 0.10}, event_id="release-1")
    )
    assert pending.state is IdentityState.CONFIRMED_KNOWN
    assert pending.speaker_label == "Alice"
    assert pending.decision_reason == "release_confirmation_pending"
    assert pending.release_count == 1
    assert pending.required_release_count == 2

    recovered = manager.observe(
        _evidence(at=4.0, scores={"Alice": 0.80}, event_id="recovered")
    )
    assert recovered.decision_reason == "confirmed_identity_pass"
    assert recovered.release_count == 0
    pending_again = manager.observe(
        _evidence(at=5.0, scores={"Alice": 0.10}, event_id="release-2")
    )
    released = manager.observe(
        _evidence(at=6.0, scores={"Alice": 0.10}, event_id="release-3")
    )
    assert pending_again.state is IdentityState.CONFIRMED_KNOWN
    assert released.state is IdentityState.UNKNOWN_INSTANCE
    assert released.speaker_label == "Unknown_1"
    assert released.decision_reason == "known_identity_released_after_failures"

    h0 = replace(
        FROZEN_IDENTITY_POLICIES["H2"],
        hysteresis_policy="H0_ONE_PASS_DIAGNOSTIC",
        consecutive_passes_to_confirm=1,
    )
    one_pass = SessionIdentityManager(h0)
    one_pass.ensure_cluster(_creation())
    assert one_pass.observe(
        _evidence(at=1.0, scores={"Alice": 0.80}, event_id="h0-confirm")
    ).state is IdentityState.CONFIRMED_KNOWN
    immediate = one_pass.observe(
        _evidence(at=2.0, scores={"Alice": 0.10}, event_id="h0-release")
    )
    assert immediate.state is IdentityState.UNKNOWN_INSTANCE
    assert immediate.required_release_count == 1


def test_historical_frozen_policy_hash_retains_legacy_one_release_behavior() -> None:
    policy = FROZEN_IDENTITY_POLICIES["H2"]
    manager = SessionIdentityManager(policy)
    manager.ensure_cluster(_creation())
    manager.observe(
        _evidence(at=1.0, scores={"Alice": 0.80}, event_id="legacy-confirm-1")
    )
    manager.observe(
        _evidence(at=2.0, scores={"Alice": 0.80}, event_id="legacy-confirm-2")
    )

    released = manager.observe(
        _evidence(at=3.0, scores={"Alice": 0.10}, event_id="legacy-release")
    )

    assert released.state is IdentityState.UNKNOWN_INSTANCE
    assert released.required_release_count == 1
    assert released.decision_reason == "known_identity_released_after_failures"


def test_adaptive_and_duration_dependent_gates_are_causal_and_event_specific() -> None:
    adaptive = replace(
        FROZEN_IDENTITY_POLICIES["H2"],
        score_threshold=0.50,
        margin_threshold=0.10,
        minimum_evidence_sec=0.5,
        hysteresis_policy="H2A_ADAPTIVE_EARLY",
    )
    assert adaptive.effective_gate(1.5) == pytest.approx((0.55, 0.12, 2))
    assert adaptive.effective_gate(2.0) == pytest.approx((0.52, 0.11, 2))
    assert adaptive.effective_gate(3.1) == pytest.approx((0.50, 0.10, 2))

    manager = SessionIdentityManager(adaptive)
    manager.ensure_cluster(_creation())
    early = manager.observe(
        _evidence(
            at=1.0,
            duration=1.0,
            scores={"Alice": 0.54, "Bob": 0.40},
            event_id="adaptive-early",
        )
    )
    medium = manager.observe(
        _evidence(
            at=2.0,
            duration=2.0,
            scores={"Alice": 0.54, "Bob": 0.40},
            event_id="adaptive-medium",
        )
    )
    assert early.state is IdentityState.UNKNOWN_INSTANCE
    assert early.effective_score_threshold == pytest.approx(0.55)
    assert medium.state is IdentityState.TENTATIVE_KNOWN
    assert medium.effective_score_threshold == pytest.approx(0.52)

    duration_dependent = replace(
        adaptive,
        hysteresis_policy="H4_DURATION_DEPENDENT",
    )
    assert duration_dependent.effective_gate(1.5)[2] == 3
    assert duration_dependent.effective_gate(2.0)[2] == 2
    assert duration_dependent.effective_gate(3.1)[2] == 2


def test_end_session_expiry_retains_state_until_explicit_session_boundary() -> None:
    policy = replace(
        FROZEN_IDENTITY_POLICIES["H2"],
        identity_expiry_sec=3.0,
        identity_expiry_mode="end_session",
    )
    manager = SessionIdentityManager(policy)
    manager.ensure_cluster(_creation())
    manager.observe(_evidence(at=1.0, scores={"Alice": 0.8}, event_id="ev-1"))
    manager.observe(_evidence(at=2.0, scores={"Alice": 0.8}, event_id="ev-2"))

    assert manager.advance_time(500.0) == ()
    assert manager.snapshot("anon-a").state is IdentityState.CONFIRMED_KNOWN
    ended = manager.end_session(500.0)
    assert len(ended) == 1
    assert ended[0].decision_reason == "session_ended"
    assert ended[0].state is IdentityState.RELEASED
    assert manager.session_state()["cluster_count"] == 0


def test_unknown_labels_persist_through_merge_split_and_reset() -> None:
    allocator = UnknownLabelAllocator()
    allocated = allocator.allocate_many(
        [
            _creation("later", start=0, sequence=2),
            _creation("earlier", start=0, sequence=1),
        ]
    )
    assert [
        (value.anonymous_speaker_id, value.unknown_label) for value in allocated
    ] == [
        ("earlier", "Unknown_1"),
        ("later", "Unknown_2"),
    ]

    survivor = allocator.merge(["later", "earlier"])
    assert survivor.anonymous_speaker_id == "earlier"
    assert allocator.label_for("later") == "Unknown_1"

    split = allocator.split(
        "earlier",
        [
            _creation("child-late", start=20, sequence=5),
            _creation("child-early", start=10, sequence=4),
        ],
    )
    assert split.retained_child_id == "child-early"
    assert split.child_labels == {
        "child-early": "Unknown_1",
        "child-late": "Unknown_3",
    }
    assert allocator.label_for("earlier") == "Unknown_1"
    assert allocator.label_for("later") == "Unknown_1"

    allocator.reset()
    assert allocator.allocate(_creation("fresh")).unknown_label == "Unknown_1"


def test_manager_split_transfers_parent_state_only_to_earliest_child() -> None:
    manager = SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H4"])
    manager.ensure_cluster(_creation("parent"))
    manager.observe(
        _evidence(speaker_id="parent", at=1.0, scores={"Alice": 0.8}, event_id="ev-1")
    )
    manager.observe(
        _evidence(speaker_id="parent", at=2.0, scores={"Alice": 0.8}, event_id="ev-2")
    )

    result = manager.split_cluster(
        "parent",
        [
            _creation("right", start=50, sequence=4),
            _creation("left", start=10, sequence=3),
        ],
    )

    assert result.retained_child_id == "left"
    assert manager.snapshot("left").state is IdentityState.CONFIRMED_KNOWN
    assert manager.snapshot("left").speaker_label == "Alice"
    assert manager.snapshot("right").state is IdentityState.GENERIC
    assert manager.snapshot("right").speaker_label == "Unknown_2"


def _span(
    span_id: str,
    start: float | None,
    end: float | None,
    *,
    text: str | None = None,
) -> TranscriptSpan:
    return TranscriptSpan(
        span_id=span_id,
        text=text or span_id,
        start_sec=start,
        end_sec=end,
        timing_provenance="missing" if start is None else "word",
        source_event_ids=(f"asr-{span_id}",),
    )


def test_alignment_is_timestamp_based_and_missing_or_mixed_timing_is_uncertain() -> (
    None
):
    aligner = TranscriptSpeakerAligner(
        "tx-1",
        [
            _span("a", 0.0, 0.5),
            _span("boundary", 0.75, 1.25),
            _span("b", 1.25, 1.75),
            _span("missing", None, None),
        ],
    )
    revision = aligner.align_regions(
        [
            SpeakerRegion(1.0, 2.0, "anon-b", "Unknown_2", "diar-b"),
            SpeakerRegion(0.0, 1.0, "anon-a", "Unknown_1", "diar-a"),
        ],
        caused_by_event_ids=("diar-b", "diar-a"),
        source_time_sec=2.0,
    )
    assert revision is not None
    values = {value.span_id: value for value in aligner.spans}
    assert values["a"].anonymous_speaker_id == "anon-a"
    assert values["a"].speaker_label == "Unknown_1"
    assert values["b"].anonymous_speaker_id == "anon-b"
    assert values["boundary"].speaker_label is None
    assert values["boundary"].alignment_status == ALIGNMENT_AMBIGUOUS
    assert values["missing"].speaker_label is None
    assert values["missing"].alignment_status == ALIGNMENT_TIMESTAMP_INSUFFICIENT
    assert set(revision.uncertain_span_ids) == {"boundary", "missing"}


def test_identity_relabel_is_cluster_scoped_interval_scoped_and_idempotent() -> None:
    aligner = TranscriptSpeakerAligner(
        "tx-2",
        [_span("a1", 0.0, 0.5), _span("a2", 0.5, 1.0), _span("b1", 1.0, 1.5)],
    )
    aligner.align_regions(
        [
            SpeakerRegion(0.0, 1.0, "anon-a", "Unknown_1", "diar-a"),
            SpeakerRegion(1.0, 1.5, "anon-b", "Unknown_2", "diar-b"),
        ],
        caused_by_event_ids=("diar-a", "diar-b"),
        source_time_sec=1.5,
    )

    revision = aligner.relabel_identity(
        anonymous_speaker_id="anon-a",
        speaker_label="Alice",
        effective_intervals=(TimeInterval(0.0, 0.5),),
        caused_by_event_ids=("identity-a",),
        source_time_sec=1.5,
    )
    assert revision is not None
    assert revision.target_span_ids == ("a1",)
    values = {value.span_id: value for value in aligner.spans}
    assert values["a1"].speaker_label == "Alice"
    assert values["a2"].speaker_label == "Unknown_1"
    assert values["b1"].speaker_label == "Unknown_2"
    assert revision.before_snapshot_sha256 != revision.after_snapshot_sha256
    assert revision.after_snapshot_sha256 == aligner.snapshot_sha256

    same_hash = aligner.snapshot_sha256
    repeated = aligner.relabel_identity(
        anonymous_speaker_id="anon-a",
        speaker_label="Alice",
        effective_intervals=(TimeInterval(0.0, 0.5),),
        caused_by_event_ids=("identity-a",),
        source_time_sec=1.5,
    )
    assert repeated is None
    assert aligner.snapshot_sha256 == same_hash


def test_alignment_hashes_and_revision_ids_ignore_input_order() -> None:
    spans = [_span("second", 0.5, 1.0), _span("first", 0.0, 0.5)]
    regions = [
        SpeakerRegion(0.5, 1.0, "anon-b", "Unknown_2", "diar-b"),
        SpeakerRegion(0.0, 0.5, "anon-a", "Unknown_1", "diar-a"),
    ]
    left = TranscriptSpeakerAligner("tx-stable", spans)
    right = TranscriptSpeakerAligner("tx-stable", reversed(spans))
    left_revision = left.align_regions(
        regions,
        caused_by_event_ids=("diar-b", "diar-a"),
        source_time_sec=1.0,
    )
    right_revision = right.align_regions(
        list(reversed(regions)),
        caused_by_event_ids=("diar-a", "diar-b"),
        source_time_sec=1.0,
    )
    assert left_revision is not None and right_revision is not None
    assert left.snapshot_sha256 == right.snapshot_sha256
    assert left_revision.revision_id == right_revision.revision_id

    first_id = stable_span_id(
        transcript_id="tx-stable",
        source_event_ids=("asr-1",),
        start_sec=0.0,
        end_sec=0.5,
        source_ordinal=0,
    )
    second_id = stable_span_id(
        transcript_id="tx-stable",
        source_event_ids=("asr-1",),
        start_sec=0.0,
        end_sec=0.5,
        source_ordinal=0,
    )
    assert first_id == second_id
