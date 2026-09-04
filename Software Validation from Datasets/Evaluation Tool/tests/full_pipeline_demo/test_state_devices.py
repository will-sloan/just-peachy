from __future__ import annotations

from app.full_pipeline_demo.devices import enumerate_input_devices
from app.full_pipeline_demo.state import (
    DemoViewState,
    apply_event,
    apply_status,
    clear_anonymous_memory_projection,
    reset_session_projection,
)


class _SoundDevice:
    @staticmethod
    def query_devices():
        return [
            {
                "name": "Output only",
                "max_input_channels": 0,
                "default_samplerate": 48000.0,
                "hostapi": 0,
            },
            {
                "name": "Scientific microphone",
                "max_input_channels": 2,
                "default_samplerate": 48000.0,
                "hostapi": 0,
            },
        ]

    @staticmethod
    def query_hostapis():
        return [{"name": "WASAPI"}]


def test_device_enumeration_keeps_only_inputs_and_native_format() -> None:
    devices = enumerate_input_devices(lambda _name: _SoundDevice)
    assert len(devices) == 1
    assert devices[0].index == 1
    assert devices[0].sample_rate_hz == 48000
    assert devices[0].maximum_input_channels == 2
    assert "WASAPI" not in devices[0].display_name


def test_user_projection_never_formats_raw_score_as_confidence() -> None:
    state = apply_event(
        DemoViewState(),
        {
            "contract_type": "AnonymousSpeakerEvent",
            "event_sequence": 1,
            "anonymous_speaker_id": "anon_0001",
            "unknown_label": "Unknown_1",
        },
    )
    state = apply_event(
        state,
        {
            "contract_type": "IdentityEvidenceEvent",
            "event_sequence": 2,
            "anonymous_speaker_id": "anon_0001",
            "top1_raw_score": 0.8123,
            "score_type": "cosine_similarity",
            "top1_top2_margin": 0.12,
            "evidence_duration_sec": 3.0,
            "threshold_identity": {
                "score_threshold": 0.53,
                "margin_threshold": 0.03,
            },
        },
    )
    state = apply_event(
        state,
        {
            "contract_type": "TranscriptRevisionEvent",
            "event_sequence": 3,
            "transcript_state": "provisional",
            "spans": [
                {
                    "span_id": "s1",
                    "text": "hello",
                    "anonymous_speaker_id": "anon_0001",
                    "speaker_label": None,
                }
            ],
        },
    )
    assert state.top1_raw_score == 0.8123
    assert state.score_type == "cosine_similarity"
    assert state.score_threshold == 0.53
    assert state.user_transcript() == "Unknown_1: hello"
    assert "%" not in state.user_transcript()


def test_identity_revision_updates_user_label_and_status_projection() -> None:
    state = apply_event(
        DemoViewState(),
        {
            "contract_type": "TranscriptRevisionEvent",
            "event_sequence": 1,
            "transcript_state": "final",
            "spans": [
                {
                    "span_id": "s1",
                    "text": "test phrase",
                    "anonymous_speaker_id": "anon_0001",
                    "speaker_label": {"display_label": "Unknown_1"},
                }
            ],
        },
    )
    state = apply_event(
        state,
        {
            "contract_type": "IdentityLabelEvent",
            "event_sequence": 2,
            "anonymous_speaker_id": "anon_0001",
            "identity_state": "confirmed",
            "speaker_label": {"display_label": "Amina", "label_kind": "known"},
        },
    )
    state = apply_status(
        state,
        {
            "session_id": "session_1",
            "pipeline_id": "fullpipe_v1_ag_dr_ie",
            "state": "running",
            "elapsed_session_sec": 4.5,
            "audio_processed_sec": 3.0,
            "realtime_factor": 1.5,
            "queue_depth": 2,
            "queue_backpressure": {"blocked_max_sec": 0.04},
        },
    )
    assert state.user_transcript() == "Amina (confirmed): test phrase"
    assert state.identity_states["anon_0001"] == "confirmed"
    assert state.processing_state == "running"
    assert state.realtime_factor == 1.5


def test_user_projection_marks_tentative_name_explicitly() -> None:
    state = apply_event(
        DemoViewState(),
        {
            "contract_type": "TranscriptRevisionEvent",
            "event_sequence": 1,
            "spans": [
                {
                    "span_id": "s1",
                    "text": "still gathering evidence",
                    "anonymous_speaker_id": "anon_1",
                    "speaker_label": {"display_label": "Unknown_1"},
                }
            ],
        },
    )
    state = apply_event(
        state,
        {
            "contract_type": "IdentityLabelEvent",
            "event_sequence": 2,
            "anonymous_speaker_id": "anon_1",
            "identity_state": "tentative",
            "speaker_label": {"display_label": "Amina"},
        },
    )
    assert state.user_transcript() == "Amina (tentative): still gathering evidence"


def test_duplicate_or_regressive_event_is_ignored() -> None:
    state = apply_event(
        DemoViewState(),
        {"contract_type": "AsrPartialEvent", "event_sequence": 2, "text": "new"},
    )
    observed = apply_event(
        state,
        {"contract_type": "AsrPartialEvent", "event_sequence": 1, "text": "old"},
    )
    assert observed is state


def test_known_only_omits_anonymous_roster_and_reset_preserves_enrollment_boundary() -> None:
    state = apply_event(
        DemoViewState(product_mode="H2_KNOWN_ONLY"),
        {
            "contract_type": "AnonymousSpeakerEvent",
            "event_sequence": 1,
            "anonymous_speaker_id": "anon_1",
            "unknown_label": "Speaker_1",
        },
    )
    assert state.anonymous_labels == {"anon_1": "Unknown"}
    assert state.active_roster == {}
    state = apply_event(
        state,
        {
            "contract_type": "TranscriptRevisionEvent",
            "event_sequence": 2,
            "spans": [
                {
                    "span_id": "s1",
                    "text": "private transcript",
                    "anonymous_speaker_id": "anon_1",
                }
            ],
        },
    )
    reset = reset_session_projection(state, preserve_transcript=True)
    assert reset.transcript_spans == state.transcript_spans
    assert reset.identity_labels == {}
    assert reset.active_roster == {}
    deleted = reset_session_projection(state, preserve_transcript=False)
    assert deleted.transcript_spans == () and deleted.asr_text == ""


def test_clear_anonymous_projection_retains_confirmed_known_participant() -> None:
    state = DemoViewState()
    for sequence, cluster, label, identity_state in (
        (1, "anon_1", "Speaker_1", "anonymous"),
        (2, "anon_2", "Ada", "confirmed"),
    ):
        state = apply_event(
            state,
            {
                "contract_type": "AnonymousSpeakerEvent",
                "event_sequence": sequence * 2 - 1,
                "anonymous_speaker_id": cluster,
                "unknown_label": label,
            },
        )
        if identity_state == "confirmed":
            state = apply_event(
                state,
                {
                    "contract_type": "IdentityLabelEvent",
                    "event_sequence": sequence * 2,
                    "anonymous_speaker_id": cluster,
                    "identity_state": identity_state,
                    "speaker_label": {"display_label": label},
                },
            )
    cleared = clear_anonymous_memory_projection(state)
    assert set(cleared.active_roster) == {"anon_2"}
    assert cleared.identity_labels == {"anon_2": "Ada"}
