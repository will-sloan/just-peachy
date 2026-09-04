from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Mapping

from app.full_pipeline.alignment import (
    SpeakerRegion,
    TranscriptSpan,
    TranscriptSpeakerAligner,
)
from app.full_pipeline.event_adapters import (
    AnonymousSpeakerData,
    CandidateReference,
    anonymous_speaker_event,
    identity_evidence_event,
    identity_label_event,
    transcript_revision_event,
)
from app.full_pipeline.identity import (
    FROZEN_IDENTITY_POLICIES,
    ClusterCreation,
    IdentityEvidence,
    IdentityState,
    SessionIdentityManager,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    TOOL_ROOT
    / "configs"
    / "automated_evaluation"
    / "schemas"
    / "full_pipeline_contracts.v1.schema.json"
)
SCHEMA = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
SHA_A = "a" * 64
SHA_B = "b" * 64


def _envelope(
    event_id: str,
    sequence: int,
    *,
    causation_event_id: str | None = None,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_sequence": sequence,
        "session_id": "session-1",
        "pipeline_id": "fullpipe_v1_ao_dr_ir",
        "protocol_version": "full_pipeline_protocol.v1",
        "stream_id": "stream-1",
        "recording_id": "recording-1",
        "utterance_id": None,
        "correlation_id": "correlation-1",
        "causation_event_id": causation_event_id,
        "source_clock": {
            "clock_id": "source-clock-1",
            "clock_type": "audio_sample",
            "sample_rate_hz": 16000,
            "utc_epoch": None,
            "monotonic_epoch_ns": 100,
        },
        "capture_timestamps": {
            "sample_start_index": 0,
            "sample_end_index": 32000,
            "audio_start_sec": 0.0,
            "audio_end_sec": 2.0,
            "capture_start_monotonic_ns": 100,
            "capture_end_monotonic_ns": 200,
            "capture_start_utc": None,
            "capture_end_utc": None,
        },
        "processing_timestamps": {
            "processing_started_monotonic_ns": 300,
            "processing_ended_monotonic_ns": 400,
            "emitted_monotonic_ns": 500,
            "emitted_at_utc": "2026-08-23T12:00:00Z",
        },
        "component_identity": {
            "component_family": "speaker_matching",
            "backend_id": "redimnet2_b2_speaker_embedding",
            "backend_config_id": "redimnet2_b2",
            "backend_config_sha256": SHA_A,
            "pipeline_config_sha256": SHA_B,
            "model_id": "redimnet2_b2_speaker_embedding:11f2cbf70100",
            "model_asset_sha256s": [SHA_A],
        },
    }


def _threshold_identity() -> dict[str, object]:
    return {
        "threshold_policy_id": "full_pipeline_open_set_decision.v1:H2",
        "threshold_policy_sha256": SHA_A,
        "calibration_protocol_id": "hybrid_speaker_attribution_product_v2_a68cc1ac26aa",
        "calibration_result_sha256": SHA_B,
        "operating_mode": "BALANCED",
        "gallery_size": 2,
        "raw_score_type": "cosine_similarity",
        "score_threshold": 0.5265351286789879,
        "margin_threshold": 0.03,
        "minimum_evidence_sec": 2.0,
        "target_fpir": 0.01,
    }


def _quality() -> dict[str, object]:
    return {
        "status": "accepted",
        "policy_id": "identity_embedding_consistency.v1",
        "policy_sha256": SHA_A,
        "metrics": {"embedding_consistency": 0.8},
        "reason_codes": [],
    }


def _identity_values():
    manager = SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H2"])
    manager.ensure_cluster(ClusterCreation(0, 1, "anon-1"))
    evidence = IdentityEvidence(
        anonymous_speaker_id="anon-1",
        source_time_sec=2.0,
        evidence_duration_sec=2.0,
        candidate_scores={"spk-alice": 0.8, "spk-bob": 0.2},
        embedding_consistency=0.8,
        evidence_event_id="identity-evidence-1",
    )
    transition = manager.observe(evidence)
    assert transition.state is IdentityState.TENTATIVE_KNOWN
    return manager, evidence, transition


def test_identity_evidence_and_label_events_match_locked_contract_shape() -> None:
    _manager, evidence, transition = _identity_values()
    evidence_envelope = _envelope("event-evidence", 1)
    label_envelope = _envelope(
        "event-label", 2, causation_event_id=evidence.evidence_event_id
    )
    threshold = _threshold_identity()
    quality = _quality()
    originals = deepcopy((evidence_envelope, label_envelope, threshold, quality))

    evidence_event = identity_evidence_event(
        evidence_envelope,
        evidence,
        transition,
        enrollment_profile_id="gallery-profile-1",
        enrollment_profile_sha256=SHA_B,
        candidate_references={
            "spk-alice": CandidateReference("spk-alice", "Alice", "template-alice"),
            "spk-bob": CandidateReference("spk-bob", "Bob", "template-bob"),
        },
        threshold_identity=threshold,
        quality_gate=quality,
        evidence_window_count=3,
        usable_segment_count=2,
    )
    label_event = identity_label_event(
        label_envelope,
        evidence,
        transition,
        threshold_identity=threshold,
        expiry_policy_id="full_pipeline_identity_expiry_120s.v1",
    )

    _assert_event_contract(evidence_event, "IdentityEvidenceEvent")
    _assert_event_contract(label_event, "IdentityLabelEvent")
    assert evidence_event["decision"] == "accepted_known"
    assert evidence_event["candidate_scores"][0] == {
        "candidate_speaker_id": "spk-alice",
        "candidate_display_label": "Alice",
        "reference_id": "template-alice",
        "raw_score": 0.8,
        "score_type": "cosine_similarity",
    }
    assert label_event["identity_state"] == "tentative"
    assert label_event["speaker_label"] == {
        "label_kind": "known",
        "display_label": "spk-alice",
        "enrolled_speaker_id": "spk-alice",
    }
    assert label_event["evidence_event_ids"] == ["identity-evidence-1"]
    assert (evidence_envelope, label_envelope, threshold, quality) == originals
    _assert_no_misleading_score_fields(evidence_event)
    _assert_no_misleading_score_fields(label_event)


def test_generic_and_released_states_map_to_public_unknown_with_stable_label() -> None:
    manager = SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H5"])
    manager.ensure_cluster(ClusterCreation(0, 1, "anon-1"))
    short = IdentityEvidence(
        anonymous_speaker_id="anon-1",
        source_time_sec=0.5,
        evidence_duration_sec=0.5,
        candidate_scores={"spk-alice": 0.9},
        embedding_consistency=0.8,
        evidence_event_id="short-evidence",
    )
    generic = manager.observe(short)
    generic_event = identity_label_event(
        _envelope("generic-label", 1, causation_event_id="short-evidence"),
        short,
        generic,
        threshold_identity=_threshold_identity(),
        expiry_policy_id="full_pipeline_identity_expiry_120s.v1",
    )
    assert generic.state is IdentityState.GENERIC
    assert generic_event["identity_state"] == "unknown"
    assert generic_event["visible_to_user"] is False
    assert generic_event["speaker_label"] == {
        "label_kind": "unknown",
        "display_label": "Unknown_1",
        "enrolled_speaker_id": None,
    }

    full_1 = IdentityEvidence(
        anonymous_speaker_id="anon-1",
        source_time_sec=1.0,
        evidence_duration_sec=2.0,
        candidate_scores={"spk-alice": 0.9},
        embedding_consistency=0.8,
        evidence_event_id="full-1",
    )
    full_2 = IdentityEvidence(
        anonymous_speaker_id="anon-1",
        source_time_sec=2.0,
        evidence_duration_sec=2.0,
        candidate_scores={"spk-alice": 0.9},
        embedding_consistency=0.8,
        evidence_event_id="full-2",
    )
    manager.observe(full_1)
    manager.observe(full_2)
    released = manager.advance_time(122.0)[0]
    released_event = identity_label_event(
        _envelope("released-label", 2, causation_event_id="expiry-status-event"),
        full_2,
        released,
        threshold_identity=_threshold_identity(),
        expiry_policy_id="full_pipeline_identity_expiry_120s.v1",
    )
    _assert_event_contract(generic_event, "IdentityLabelEvent")
    _assert_event_contract(released_event, "IdentityLabelEvent")
    assert released_event["identity_state"] == "unknown"
    assert released_event["speaker_label"]["display_label"] == "Unknown_1"
    assert released_event["prior_identity_state"] == "confirmed"
    assert released_event["evidence_event_ids"] == ["expiry-status-event"]


def test_anonymous_speaker_event_matches_contract_and_binds_unknown_ordinal() -> None:
    event = anonymous_speaker_event(
        _envelope("anonymous-event", 1),
        AnonymousSpeakerData(
            anonymous_speaker_id="anon-1",
            unknown_label="Unknown_1",
            unknown_ordinal=1,
            cluster_state="confirmed",
            start_sec=0.0,
            end_sec=2.0,
            overlap=False,
            source_turn_ids=("turn-2", "turn-1"),
            revision_number=1,
            corrected_event_ids=("cluster-update-1",),
        ),
    )

    _assert_event_contract(event, "AnonymousSpeakerEvent")
    assert event["unknown_label"] == "Unknown_1"
    assert event["unknown_ordinal"] == 1
    assert event["source_turn_ids"] == ["turn-1", "turn-2"]
    assert event["revision"]["corrected_event_ids"] == ["cluster-update-1"]


def test_transcript_revision_event_strips_internal_fields_and_keeps_uncertainty() -> (
    None
):
    aligner = TranscriptSpeakerAligner(
        "transcript-1",
        (
            TranscriptSpan(
                span_id="word-1",
                text="hello",
                start_sec=0.0,
                end_sec=0.5,
                state="committed",
                timing_provenance="word",
                anonymous_speaker_id="anon-1",
                speaker_label="Alice",
                alignment_status="identity_relabelled",
                source_event_ids=("asr-1",),
            ),
            TranscriptSpan(
                span_id="word-2",
                text="there",
                start_sec=None,
                end_sec=None,
                state="provisional",
                timing_provenance="missing",
                source_event_ids=("asr-2",),
            ),
        ),
    )
    revision = aligner.align_regions(
        (SpeakerRegion(0.0, 0.5, "anon-1", "Alice", "diarization-update"),),
        caused_by_event_ids=("diarization-update",),
        source_time_sec=1.0,
    )
    assert revision is not None

    event = transcript_revision_event(
        _envelope("transcript-event", 1, causation_event_id="diarization-update"),
        revision,
        enrolled_speaker_ids_by_label={"Alice": "spk-alice"},
    )

    _assert_event_contract(event, "TranscriptRevisionEvent")
    spans = {value["span_id"]: value for value in event["spans"]}
    assert spans["word-1"]["speaker_label"] == {
        "label_kind": "known",
        "display_label": "Alice",
        "enrolled_speaker_id": "spk-alice",
    }
    assert spans["word-2"]["speaker_label"] is None
    assert "timing_provenance" not in spans["word-2"]
    assert "alignment_status" not in spans["word-2"]
    assert (
        event["event_reason"]["code"]
        == "transcript_revision_with_alignment_uncertainty"
    )
    assert event["event_reason"]["detail"] == "word-2"
    assert event["transcript_state"] == "provisional"
    assert event["committed_text"] == "hello"
    assert event["provisional_text"] == "there"


def _assert_event_contract(event: Mapping[str, object], contract_type: str) -> None:
    """Check required/closed shapes directly from the locked Draft-2020 schema."""

    event_definition = SCHEMA["$defs"][contract_type]
    envelope_definition = SCHEMA["$defs"]["eventEnvelope"]
    body_definition = event_definition["allOf"][1]
    required = set(envelope_definition["required"]) | set(body_definition["required"])
    allowed = set(envelope_definition["properties"]) | set(
        body_definition["properties"]
    )
    assert required <= set(event)
    assert set(event) <= allowed
    assert event["schema_version"] == "full-pipeline-contracts.v1"
    assert event["contract_type"] == contract_type
    assert event["event_type"] == body_definition["properties"]["event_type"]["const"]
    assert json.loads(json.dumps(event, allow_nan=False)) == event

    for field, definition_name in (
        ("source_clock", "sourceClock"),
        ("capture_timestamps", "captureTimestamps"),
        ("processing_timestamps", "processingTimestamps"),
        ("component_identity", "componentIdentity"),
        ("event_reason", "eventReason"),
    ):
        _assert_closed_object(event[field], definition_name)
    if "threshold_identity" in event:
        _assert_closed_object(event["threshold_identity"], "thresholdIdentity")
    if "quality_gate" in event:
        _assert_closed_object(event["quality_gate"], "qualityAssessment")
    if "candidate_scores" in event:
        for value in event["candidate_scores"]:
            _assert_closed_object(value, "candidateScore")
    if "revision" in event:
        _assert_closed_object(event["revision"], "revisionMetadata")
    if contract_type == "IdentityLabelEvent":
        _assert_closed_object(event["speaker_label"], "speakerLabel")
        expected_kind = "unknown" if event["identity_state"] == "unknown" else "known"
        assert event["speaker_label"]["label_kind"] == expected_kind
    if contract_type == "TranscriptRevisionEvent":
        for span in event["spans"]:
            _assert_closed_object(span, "transcriptSpan")
            if span["speaker_label"] is not None:
                _assert_closed_object(span["speaker_label"], "speakerLabel")


def _assert_closed_object(value: object, definition_name: str) -> None:
    assert isinstance(value, Mapping)
    definition = SCHEMA["$defs"][definition_name]
    assert set(definition.get("required", ())) <= set(value)
    if definition.get("additionalProperties") is False:
        assert set(value) <= set(definition.get("properties", {}))


def _assert_no_misleading_score_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            assert "confidence" not in str(key).casefold()
            assert "probability" not in str(key).casefold()
            _assert_no_misleading_score_fields(child)
    elif isinstance(value, list | tuple):
        for child in value:
            _assert_no_misleading_score_fields(child)
