"""Headless user/research view projection for the common demo.

The projector consumes the locked Prompt-0 event contracts.  It never invokes a
model and never turns a raw similarity score into a confidence percentage.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence

from .h2_ux import H2_KNOWN_ONLY


@dataclass(frozen=True)
class TranscriptDisplaySpan:
    span_id: str
    text: str
    start_sec: float | None
    end_sec: float | None
    anonymous_speaker_id: str | None
    speaker_label: str
    transcript_state: str
    alignment_status: str | None


@dataclass(frozen=True)
class RosterParticipant:
    """One non-biometric presentation row for the volatile session roster."""

    participant_id: str
    display_label: str
    identity_state: str
    cluster_id: str | None
    active: bool = True
    last_seen_audio_sec: float | None = None


@dataclass(frozen=True)
class DemoViewState:
    """Immutable state rendered by both the User and Research tabs."""

    session_id: str | None = None
    pipeline_id: str | None = None
    product_mode: str | None = None
    scientific_config_status: str | None = None
    scientific_config_path: str | None = None
    scientific_config_sha256: str | None = None
    runtime_tuning_identity_sha256: str | None = None
    final_scientific_validation: bool = False
    processing_state: str = "idle"
    elapsed_session_sec: float = 0.0
    audio_processed_sec: float = 0.0
    realtime_factor: float | None = None
    queue_depth: int = 0
    queue_latency_sec: float = 0.0
    dropped_frames: int = 0
    asr_state: str = "waiting"
    asr_text: str = ""
    segmentation_state: str = "waiting"
    current_cluster_id: str | None = None
    transcript_spans: tuple[TranscriptDisplaySpan, ...] = ()
    anonymous_labels: Mapping[str, str] = field(default_factory=dict)
    identity_labels: Mapping[str, str] = field(default_factory=dict)
    identity_states: Mapping[str, str] = field(default_factory=dict)
    active_roster: Mapping[str, RosterParticipant] = field(default_factory=dict)
    top1_raw_score: float | None = None
    score_type: str | None = None
    top1_top2_margin: float | None = None
    top1_candidate_speaker_id: str | None = None
    top1_candidate_display_label: str | None = None
    top2_candidate_speaker_id: str | None = None
    top2_raw_score: float | None = None
    evidence_duration_sec: float | None = None
    identity_decision: str | None = None
    identity_quality_status: str | None = None
    identity_quality_reasons: tuple[str, ...] = ()
    embedding_backend_id: str | None = None
    embedding_model_id: str | None = None
    embedding_checkpoint_sha256: str | None = None
    score_threshold: float | None = None
    margin_threshold: float | None = None
    cpu_percent: float | None = None
    ram_percent: float | None = None
    process_rss_bytes: int | None = None
    last_event_sequence: int = 0
    last_event_type: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def user_transcript(self) -> str:
        """Return readable labelled text without research-only score details."""

        lines: list[str] = []
        for span in self.transcript_spans:
            text = span.text.strip()
            if not text:
                continue
            label = self.display_label_for(span)
            identity_state = self.identity_states.get(
                span.anonymous_speaker_id or "", "unknown"
            )
            if identity_state == "tentative":
                label = f"{label} (tentative)"
            elif identity_state == "confirmed":
                label = f"{label} (confirmed)"
            rendered = f"{label}: {text}"
            if not lines or lines[-1] != rendered:
                lines.append(rendered)
        if lines:
            return "\n".join(lines)
        return self.asr_text.strip()

    def display_label_for(self, span: TranscriptDisplaySpan) -> str:
        if span.anonymous_speaker_id:
            state = self.identity_states.get(span.anonymous_speaker_id, "unknown")
            known_label = self.identity_labels.get(span.anonymous_speaker_id)
            if self.product_mode == H2_KNOWN_ONLY and state not in {
                "tentative",
                "confirmed",
            }:
                return "Unknown"
            return known_label or self.anonymous_labels.get(
                span.anonymous_speaker_id,
                span.speaker_label or "Speaker",
            )
        return span.speaker_label or "Speaker"


def apply_event(
    state: DemoViewState, event: Mapping[str, object]
) -> DemoViewState:
    """Project one ordered public event into the two demo views."""

    sequence = int(event.get("event_sequence") or 0)
    if sequence and sequence <= state.last_event_sequence:
        return state
    contract = str(event.get("contract_type") or "")
    updates: dict[str, object] = {
        "session_id": str(event.get("session_id") or state.session_id or "") or None,
        "pipeline_id": str(event.get("pipeline_id") or state.pipeline_id or "") or None,
        "last_event_sequence": max(sequence, state.last_event_sequence),
        "last_event_type": contract or str(event.get("event_type") or "") or None,
    }
    if contract in {"AsrPartialEvent", "AsrFinalEvent"}:
        updates["asr_state"] = "final" if contract == "AsrFinalEvent" else "partial"
        updates["asr_text"] = str(event.get("text") or "")
    elif contract == "TranscriptRevisionEvent":
        spans = event.get("spans")
        if isinstance(spans, Sequence) and not isinstance(spans, (str, bytes)):
            updates["transcript_spans"] = tuple(
                _display_span(row, str(event.get("transcript_state") or "provisional"))
                for row in spans
                if isinstance(row, Mapping)
            )
    elif contract == "SpeechActivityEvent":
        updates["segmentation_state"] = str(event.get("activity_state") or "active")
    elif contract == "AnonymousSpeakerEvent":
        cluster = str(event.get("anonymous_speaker_id") or "")
        if cluster:
            values = dict(state.anonymous_labels)
            label = str(event.get("unknown_label") or cluster)
            if state.product_mode == H2_KNOWN_ONLY:
                label = "Unknown"
            values[cluster] = label
            updates["anonymous_labels"] = values
            updates["current_cluster_id"] = cluster
            if state.product_mode != H2_KNOWN_ONLY:
                updates["active_roster"] = _upsert_roster(
                    state.active_roster,
                    participant_id=cluster,
                    display_label=label,
                    identity_state="anonymous",
                    cluster_id=cluster,
                    active=True,
                    last_seen_audio_sec=_event_audio_time(event),
                )
    elif contract == "IdentityEvidenceEvent":
        candidate = _candidate_display(event, event.get("top1_candidate_speaker_id"))
        quality = event.get("quality_gate")
        quality_values = quality if isinstance(quality, Mapping) else {}
        component = _component_identity(event)
        updates.update(
            {
                "current_cluster_id": str(event.get("anonymous_speaker_id") or "")
                or state.current_cluster_id,
                "top1_raw_score": _optional_float(event.get("top1_raw_score")),
                "score_type": str(event.get("score_type") or "") or None,
                "top1_top2_margin": _optional_float(event.get("top1_top2_margin")),
                "top1_candidate_speaker_id": _optional_string(
                    event.get("top1_candidate_speaker_id")
                ),
                "top1_candidate_display_label": candidate,
                "top2_candidate_speaker_id": _optional_string(
                    event.get("top2_candidate_speaker_id")
                ),
                "top2_raw_score": _optional_float(event.get("top2_raw_score")),
                "evidence_duration_sec": _optional_float(
                    event.get("evidence_duration_sec")
                ),
                "identity_decision": _optional_string(event.get("decision")),
                "identity_quality_status": _optional_string(
                    quality_values.get("status")
                ),
                "identity_quality_reasons": _string_tuple(
                    quality_values.get("reason_codes")
                ),
                "embedding_backend_id": _first_string(
                    event.get("embedding_backend_id"),
                    event.get("backend_id"),
                    component.get("backend_id"),
                ),
                "embedding_model_id": _first_string(
                    event.get("embedding_model_id"),
                    event.get("model_id"),
                    component.get("model_id"),
                ),
                "embedding_checkpoint_sha256": _first_string(
                    event.get("embedding_checkpoint_sha256"),
                    event.get("model_sha256"),
                    component.get("model_sha256"),
                    component.get("checkpoint_sha256"),
                ),
            }
        )
        threshold = event.get("threshold_identity")
        if isinstance(threshold, Mapping):
            if not updates["score_type"]:
                updates["score_type"] = (
                    str(threshold.get("raw_score_type") or "") or None
                )
            updates["score_threshold"] = _optional_float(
                threshold.get("score_threshold")
            )
            updates["margin_threshold"] = _optional_float(
                threshold.get("margin_threshold")
            )
    elif contract == "IdentityLabelEvent":
        cluster = str(event.get("anonymous_speaker_id") or "")
        if cluster:
            labels = dict(state.identity_labels)
            states = dict(state.identity_states)
            labels[cluster] = _speaker_label(event.get("speaker_label"))
            states[cluster] = str(event.get("identity_state") or "unknown")
            updates["identity_labels"] = labels
            updates["identity_states"] = states
            updates["current_cluster_id"] = cluster
            updates["active_roster"] = _upsert_roster(
                state.active_roster,
                participant_id=cluster,
                display_label=labels[cluster],
                identity_state=states[cluster],
                cluster_id=cluster,
                active=str(event.get("roster_state") or "active") != "expired",
                last_seen_audio_sec=_event_audio_time(event),
            )
    elif contract in {"ActiveRosterEvent", "SessionRosterEvent"}:
        updates["active_roster"] = _roster_from_rows(
            event.get("participants") or event.get("active_roster"),
            fallback=state.active_roster,
        )
    elif contract == "ResourceTelemetryEvent":
        updates["cpu_percent"] = _optional_float(event.get("system_cpu_percent"))
        updates["ram_percent"] = _optional_float(event.get("system_ram_percent"))
        rss = event.get("process_rss_bytes")
        updates["process_rss_bytes"] = int(rss) if rss is not None else None
    elif contract == "PipelineStatusEvent":
        updates.update(_status_updates(event))
    return replace(state, **updates)


def apply_status(
    state: DemoViewState, status: Mapping[str, object]
) -> DemoViewState:
    """Project the coordinator's current atomic status snapshot."""

    value = replace(state, **_status_updates(status))
    if "active_roster" in status or "participants" in status:
        value = replace(
            value,
            active_roster=_roster_from_rows(
                status.get("active_roster") or status.get("participants"),
                fallback=value.active_roster,
            ),
        )
    return value


def clear_anonymous_memory_projection(state: DemoViewState) -> DemoViewState:
    """Drop session-local anonymous rows while preserving known-name evidence.

    This changes presentation state only and must be called only after the
    runtime confirms its corresponding anonymous-memory control.
    """

    known_states = {"tentative", "confirmed", "known"}
    retained_ids = {
        participant_id
        for participant_id, participant in state.active_roster.items()
        if participant.identity_state in known_states
    }
    return replace(
        state,
        anonymous_labels={},
        identity_labels={
            participant_id: label
            for participant_id, label in state.identity_labels.items()
            if participant_id in retained_ids
        },
        identity_states={
            participant_id: identity_state
            for participant_id, identity_state in state.identity_states.items()
            if participant_id in retained_ids
        },
        active_roster={
            participant_id: participant
            for participant_id, participant in state.active_roster.items()
            if participant_id in retained_ids
        },
        current_cluster_id=(
            state.current_cluster_id
            if state.current_cluster_id in retained_ids
            else None
        ),
    )


def reset_session_projection(
    state: DemoViewState,
    *,
    preserve_transcript: bool,
) -> DemoViewState:
    """Project a confirmed H2 reset without deleting permanent enrollment."""

    return replace(
        state,
        asr_state="waiting",
        asr_text=state.asr_text if preserve_transcript else "",
        segmentation_state="waiting",
        current_cluster_id=None,
        transcript_spans=(state.transcript_spans if preserve_transcript else ()),
        anonymous_labels={},
        identity_labels={},
        identity_states={},
        active_roster={},
        top1_raw_score=None,
        score_type=None,
        top1_top2_margin=None,
        top1_candidate_speaker_id=None,
        top1_candidate_display_label=None,
        top2_candidate_speaker_id=None,
        top2_raw_score=None,
        evidence_duration_sec=None,
        identity_decision=None,
        identity_quality_status=None,
        identity_quality_reasons=(),
        score_threshold=None,
        margin_threshold=None,
    )


def _status_updates(value: Mapping[str, object]) -> dict[str, object]:
    queue = value.get("queue_backpressure")
    queue_values = queue if isinstance(queue, Mapping) else {}
    counts = value.get("counts")
    count_values = counts if isinstance(counts, Mapping) else {}
    warnings = value.get("warnings")
    errors = value.get("errors")
    updates: dict[str, object] = {
        "session_id": str(value.get("session_id") or "") or None,
        "pipeline_id": str(value.get("pipeline_id") or "") or None,
        "processing_state": str(
            value.get("state") or value.get("pipeline_state") or "unknown"
        ),
        "elapsed_session_sec": float(value.get("elapsed_session_sec") or 0.0),
        "audio_processed_sec": float(value.get("audio_processed_sec") or 0.0),
        "realtime_factor": _optional_float(value.get("realtime_factor")),
        "queue_depth": int(value.get("queue_depth") or 0),
        "queue_latency_sec": float(queue_values.get("blocked_max_sec") or 0.0),
        "dropped_frames": int(
            value.get("dropped_frame_count") or count_values.get("dropped_frames") or 0
        ),
        "warnings": _string_tuple(warnings),
        "errors": _string_tuple(errors),
    }
    product_mode = value.get("product_mode") or value.get("h2_product_mode")
    if product_mode:
        updates["product_mode"] = str(product_mode)
    scientific_configuration = value.get("scientific_runtime_configuration")
    scientific_values = (
        scientific_configuration
        if isinstance(scientific_configuration, Mapping)
        else {}
    )
    for state_key, direct_key, nested_key in (
        ("scientific_config_status", "scientific_config_status", "status"),
        ("scientific_config_path", "scientific_config_path", "source_path"),
        (
            "scientific_config_sha256",
            "scientific_config_sha256",
            "source_file_sha256",
        ),
        (
            "runtime_tuning_identity_sha256",
            "runtime_tuning_identity_sha256",
            "runtime_tuning_identity_sha256",
        ),
    ):
        selected = value.get(direct_key) or scientific_values.get(nested_key)
        if selected:
            updates[state_key] = str(selected)
    final_validation = value.get("final_scientific_validation")
    if final_validation is None:
        final_validation = scientific_values.get("final_scientific_validation")
    if final_validation is not None:
        updates["final_scientific_validation"] = bool(final_validation)
    return updates


def _display_span(value: Mapping[str, object], transcript_state: str) -> TranscriptDisplaySpan:
    return TranscriptDisplaySpan(
        span_id=str(value.get("span_id") or "span"),
        text=str(value.get("text") or ""),
        start_sec=_optional_float(value.get("start_sec")),
        end_sec=_optional_float(value.get("end_sec")),
        anonymous_speaker_id=(
            str(value["anonymous_speaker_id"])
            if value.get("anonymous_speaker_id") is not None
            else None
        ),
        speaker_label=_speaker_label(value.get("speaker_label")),
        transcript_state=str(value.get("state") or transcript_state),
        alignment_status=(
            str(value["alignment_status"])
            if value.get("alignment_status") is not None
            else None
        ),
    )


def _speaker_label(value: object) -> str:
    if isinstance(value, Mapping):
        return str(value.get("display_label") or "Speaker")
    return str(value or "Speaker")


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(str(row) for row in value)
    return ()


def _optional_string(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _first_string(*values: object) -> str | None:
    return next(
        (text for value in values if (text := _optional_string(value)) is not None),
        None,
    )


def _candidate_display(event: Mapping[str, object], speaker_id: object) -> str | None:
    target = _optional_string(speaker_id)
    candidates = event.get("candidate_scores")
    if not target or not isinstance(candidates, Sequence) or isinstance(
        candidates, (str, bytes)
    ):
        return None
    for row in candidates:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("candidate_speaker_id") or "") == target:
            return _optional_string(row.get("candidate_display_label"))
    return None


def _component_identity(event: Mapping[str, object]) -> Mapping[str, object]:
    value = event.get("component_identity")
    return value if isinstance(value, Mapping) else {}


def _event_audio_time(event: Mapping[str, object]) -> float | None:
    for name in ("audio_end_sec", "assignment_end_sec", "event_audio_sec"):
        value = _optional_float(event.get(name))
        if value is not None:
            return value
    interval = event.get("audio_interval")
    if isinstance(interval, Mapping):
        return _optional_float(interval.get("end_sec"))
    return None


def _upsert_roster(
    roster: Mapping[str, RosterParticipant],
    *,
    participant_id: str,
    display_label: str,
    identity_state: str,
    cluster_id: str | None,
    active: bool,
    last_seen_audio_sec: float | None,
) -> dict[str, RosterParticipant]:
    values = dict(roster)
    prior = values.get(participant_id)
    values[participant_id] = RosterParticipant(
        participant_id=participant_id,
        display_label=display_label or (prior.display_label if prior else participant_id),
        identity_state=identity_state or (
            prior.identity_state if prior else "anonymous"
        ),
        cluster_id=cluster_id or (prior.cluster_id if prior else None),
        active=active,
        last_seen_audio_sec=(
            last_seen_audio_sec
            if last_seen_audio_sec is not None
            else (prior.last_seen_audio_sec if prior else None)
        ),
    )
    return values


def _roster_from_rows(
    value: object,
    *,
    fallback: Mapping[str, RosterParticipant],
) -> Mapping[str, RosterParticipant]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return fallback
    result: dict[str, RosterParticipant] = {}
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            continue
        participant_id = _first_string(
            row.get("participant_id"),
            row.get("anonymous_speaker_id"),
            row.get("cluster_id"),
            row.get("speaker_id"),
        ) or f"participant_{index + 1}"
        cluster_id = _first_string(
            row.get("cluster_id"), row.get("anonymous_speaker_id")
        )
        label = _first_string(
            row.get("display_label"),
            row.get("speaker_label"),
            row.get("unknown_label"),
        ) or participant_id
        state = _first_string(
            row.get("identity_state"), row.get("state")
        ) or "anonymous"
        result[participant_id] = RosterParticipant(
            participant_id=participant_id,
            display_label=label,
            identity_state=state,
            cluster_id=cluster_id,
            active=bool(row.get("active", state != "expired")),
            last_seen_audio_sec=_optional_float(
                row.get("last_seen_audio_sec") or row.get("last_seen_sec")
            ),
        )
    return result
