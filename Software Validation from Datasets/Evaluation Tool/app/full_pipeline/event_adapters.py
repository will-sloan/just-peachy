"""Pure adapters from runtime identity/alignment values to Prompt-0 events.

The adapters accept a complete common event envelope and return new dictionaries;
they do not allocate sequences, mutate session state, write files, or run models.
All speaker comparison values are emitted as raw cosine similarities.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping, Sequence

from .alignment import TranscriptRevision, TranscriptSpan
from .identity import IdentityEvidence, IdentityState, IdentityTransition


CONTRACT_SCHEMA_VERSION = "full-pipeline-contracts.v1"
RAW_SCORE_TYPE = "cosine_similarity"
_UNKNOWN_PATTERN = re.compile(r"^Unknown_[1-9][0-9]*$")
_ENVELOPE_FIELDS = {
    "event_id",
    "event_sequence",
    "session_id",
    "pipeline_id",
    "protocol_version",
    "stream_id",
    "recording_id",
    "utterance_id",
    "correlation_id",
    "causation_event_id",
    "source_clock",
    "capture_timestamps",
    "processing_timestamps",
    "component_identity",
}


@dataclass(frozen=True)
class CandidateReference:
    candidate_speaker_id: str
    display_label: str
    reference_id: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.candidate_speaker_id,
                self.display_label,
                self.reference_id,
            )
        ):
            raise ValueError("candidate reference fields must be non-empty")


@dataclass(frozen=True)
class AnonymousSpeakerData:
    anonymous_speaker_id: str
    unknown_label: str
    unknown_ordinal: int
    cluster_state: str
    start_sec: float
    end_sec: float | None
    overlap: bool
    source_turn_ids: tuple[str, ...]
    revision_number: int
    supersedes_revision_id: str | None = None
    corrected_event_ids: tuple[str, ...] = ()
    reason: str = "anonymous_cluster_update"

    def __post_init__(self) -> None:
        if not self.anonymous_speaker_id.strip():
            raise ValueError("anonymous_speaker_id must be non-empty")
        if self.unknown_ordinal < 1:
            raise ValueError("unknown_ordinal must be >= 1")
        if self.unknown_label != f"Unknown_{self.unknown_ordinal}":
            raise ValueError("unknown_label and unknown_ordinal disagree")
        if self.cluster_state not in {
            "tentative",
            "confirmed",
            "merged",
            "split",
            "retired",
        }:
            raise ValueError("unsupported anonymous cluster state")
        if self.start_sec < 0 or (
            self.end_sec is not None and self.end_sec < self.start_sec
        ):
            raise ValueError("anonymous cluster timestamps are invalid")
        if self.revision_number < 0:
            raise ValueError("revision_number must be >= 0")
        object.__setattr__(
            self, "source_turn_ids", _unique_strings(self.source_turn_ids)
        )
        object.__setattr__(
            self, "corrected_event_ids", _unique_strings(self.corrected_event_ids)
        )


def identity_evidence_event(
    envelope: Mapping[str, object],
    evidence: IdentityEvidence,
    transition: IdentityTransition,
    *,
    enrollment_profile_id: str,
    enrollment_profile_sha256: str,
    candidate_references: Mapping[str, CandidateReference],
    threshold_identity: Mapping[str, object],
    quality_gate: Mapping[str, object],
    evidence_window_count: int,
    usable_segment_count: int,
) -> dict[str, object]:
    """Adapt one raw score observation to ``IdentityEvidenceEvent``."""

    if transition.anonymous_speaker_id != evidence.anonymous_speaker_id:
        raise ValueError("identity evidence and transition speaker IDs differ")
    if evidence_window_count < 0 or usable_segment_count < 0:
        raise ValueError("evidence counts must be >= 0")
    candidates = []
    for candidate_id, raw_score in sorted(
        evidence.candidate_scores.items(), key=lambda item: (-item[1], item[0])
    ):
        try:
            reference = candidate_references[candidate_id]
        except KeyError as exc:
            raise ValueError(
                f"candidate reference is missing for {candidate_id}"
            ) from exc
        if reference.candidate_speaker_id != candidate_id:
            raise ValueError("candidate reference ID does not match score ID")
        candidates.append(
            {
                "candidate_speaker_id": candidate_id,
                "candidate_display_label": reference.display_label,
                "reference_id": reference.reference_id,
                "raw_score": float(raw_score),
                "score_type": RAW_SCORE_TYPE,
            }
        )
    reason = _event_reason(
        transition.decision_reason,
        causal_event_ids=transition.evidence_event_ids,
    )
    payload = {
        "anonymous_speaker_id": evidence.anonymous_speaker_id,
        "enrollment_profile_id": _required_text(
            enrollment_profile_id, "enrollment_profile_id"
        ),
        "enrollment_profile_sha256": _sha256_text(enrollment_profile_sha256),
        "evidence_duration_sec": float(evidence.evidence_duration_sec),
        "evidence_window_count": int(evidence_window_count),
        "usable_segment_count": int(usable_segment_count),
        "quality_gate": deepcopy(dict(quality_gate)),
        "candidate_scores": candidates,
        "top1_candidate_speaker_id": transition.top1_candidate_id,
        "top1_raw_score": transition.top1_score,
        "top2_candidate_speaker_id": transition.top2_candidate_id,
        "top2_raw_score": transition.top2_score,
        "score_type": RAW_SCORE_TYPE,
        "top1_top2_margin": transition.margin,
        "threshold_identity": deepcopy(dict(threshold_identity)),
        "decision": _evidence_decision(transition),
        "decision_reason": reason,
    }
    return _event(
        envelope,
        contract_type="IdentityEvidenceEvent",
        event_type="identity_evidence",
        payload=payload,
        reason=reason,
    )


def identity_label_event(
    envelope: Mapping[str, object],
    evidence: IdentityEvidence,
    transition: IdentityTransition,
    *,
    threshold_identity: Mapping[str, object],
    expiry_policy_id: str,
    tentative_visible: bool = True,
    revision_id: str | None = None,
    supersedes_revision_id: str | None = None,
) -> dict[str, object]:
    """Adapt the five internal states to the three public label states."""

    public_state = _public_identity_state(transition.state)
    prior_public_state = _public_identity_state(transition.prior_state)
    current_label = _speaker_label(
        transition.speaker_label,
        public_state=public_state,
        enrolled_speaker_id=(
            transition.known_speaker_id
            if public_state == "confirmed"
            else transition.top1_candidate_id
        ),
    )
    prior_label = _speaker_label(
        transition.prior_speaker_label,
        public_state=prior_public_state,
        enrolled_speaker_id=(
            None
            if _UNKNOWN_PATTERN.fullmatch(transition.prior_speaker_label)
            else transition.prior_speaker_label
        ),
    )
    evidence_ids = transition.evidence_event_ids
    if not evidence_ids:
        fallback = envelope.get("causation_event_id")
        if fallback:
            evidence_ids = (str(fallback),)
    if not evidence_ids:
        raise ValueError(
            "IdentityLabelEvent requires at least one causal evidence event"
        )
    reason = _event_reason(transition.decision_reason, causal_event_ids=evidence_ids)
    resolved_revision_id = revision_id or _stable_id(
        "idrev",
        {
            "event_id": envelope.get("event_id"),
            "anonymous_speaker_id": transition.anonymous_speaker_id,
            "revision_number": transition.revision_number,
            "state": transition.state.value,
            "speaker_label": transition.speaker_label,
        },
    )
    payload = {
        "anonymous_speaker_id": transition.anonymous_speaker_id,
        "identity_state": public_state,
        "speaker_label": current_label,
        "visible_to_user": (
            False
            if transition.state is IdentityState.GENERIC
            else tentative_visible
            if transition.state is IdentityState.TENTATIVE_KNOWN
            else True
        ),
        "prior_identity_state": prior_public_state,
        "prior_speaker_label": prior_label,
        "evidence_event_ids": list(evidence_ids),
        "evidence_duration_sec": float(evidence.evidence_duration_sec),
        "confirmation_count": int(transition.confirmation_count),
        "required_confirmation_count": int(transition.required_confirmation_count),
        "threshold_identity": deepcopy(dict(threshold_identity)),
        "expiry_policy_id": _required_text(expiry_policy_id, "expiry_policy_id"),
        "hysteresis_applied": bool(transition.hysteresis_applied),
        "revision": _revision_metadata(
            revision_id=resolved_revision_id,
            revision_number=transition.revision_number,
            supersedes_revision_id=supersedes_revision_id,
            corrected_event_ids=evidence_ids,
            reason=reason,
        ),
    }
    return _event(
        envelope,
        contract_type="IdentityLabelEvent",
        event_type="identity_label",
        payload=payload,
        reason=reason,
    )


def anonymous_speaker_event(
    envelope: Mapping[str, object],
    data: AnonymousSpeakerData,
) -> dict[str, object]:
    """Adapt session-owned anonymous cluster data to its public event."""

    causal_ids = data.corrected_event_ids or data.source_turn_ids
    reason = _event_reason(data.reason, causal_event_ids=causal_ids)
    revision_id = _stable_id(
        "anonrev",
        {
            "event_id": envelope.get("event_id"),
            "anonymous_speaker_id": data.anonymous_speaker_id,
            "revision_number": data.revision_number,
            "cluster_state": data.cluster_state,
        },
    )
    payload = {
        "anonymous_speaker_id": data.anonymous_speaker_id,
        "unknown_label": data.unknown_label,
        "unknown_ordinal": data.unknown_ordinal,
        "cluster_state": data.cluster_state,
        "start_sec": float(data.start_sec),
        "end_sec": float(data.end_sec) if data.end_sec is not None else None,
        "overlap": bool(data.overlap),
        "source_turn_ids": list(data.source_turn_ids),
        "revision": _revision_metadata(
            revision_id=revision_id,
            revision_number=data.revision_number,
            supersedes_revision_id=data.supersedes_revision_id,
            corrected_event_ids=data.corrected_event_ids,
            reason=reason,
        ),
    }
    return _event(
        envelope,
        contract_type="AnonymousSpeakerEvent",
        event_type="anonymous_speaker",
        payload=payload,
        reason=reason,
    )


def transcript_revision_event(
    envelope: Mapping[str, object],
    revision: TranscriptRevision,
    *,
    enrolled_speaker_ids_by_label: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Adapt a deterministic internal transcript revision to its public event."""

    identities = dict(enrolled_speaker_ids_by_label or {})
    public_spans = [
        _transcript_span(value, enrolled_speaker_ids_by_label=identities)
        for value in revision.spans
    ]
    transcript_state = _transcript_state(revision.spans)
    committed = " ".join(
        value.text
        for value in revision.spans
        if value.state in {"committed", "final"} and value.text
    ).strip()
    provisional = " ".join(
        value.text
        for value in revision.spans
        if value.state == "provisional" and value.text
    ).strip()
    uncertainty = ",".join(revision.uncertain_span_ids) or None
    event_reason_code = (
        "transcript_revision_with_alignment_uncertainty"
        if revision.uncertain_span_ids
        else revision.reason
    )
    reason = _event_reason(
        event_reason_code,
        detail=uncertainty,
        causal_event_ids=revision.caused_by_event_ids,
    )
    revision_reason = _event_reason(
        revision.reason,
        detail=uncertainty,
        causal_event_ids=revision.caused_by_event_ids,
    )
    payload = {
        "transcript_id": revision.transcript_id,
        "revision": _revision_metadata(
            revision_id=revision.revision_id,
            revision_number=revision.revision_number,
            supersedes_revision_id=revision.supersedes_revision_id,
            corrected_event_ids=revision.caused_by_event_ids,
            reason=revision_reason,
        ),
        "transcript_state": transcript_state,
        "operation": revision.operation,
        "target_span_ids": list(revision.target_span_ids),
        "before_snapshot_sha256": revision.before_snapshot_sha256,
        "after_snapshot_sha256": revision.after_snapshot_sha256,
        "committed_text": committed,
        "provisional_text": provisional,
        "spans": public_spans,
        "caused_by_event_ids": list(revision.caused_by_event_ids),
    }
    return _event(
        envelope,
        contract_type="TranscriptRevisionEvent",
        event_type="transcript_revision",
        payload=payload,
        reason=reason,
    )


def _event(
    envelope: Mapping[str, object],
    *,
    contract_type: str,
    event_type: str,
    payload: Mapping[str, object],
    reason: Mapping[str, object],
) -> dict[str, object]:
    missing = sorted(field for field in _ENVELOPE_FIELDS if field not in envelope)
    if missing:
        raise ValueError(f"event envelope is missing fields: {missing}")
    event = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "contract_type": contract_type,
        **{field: deepcopy(envelope[field]) for field in _ENVELOPE_FIELDS},
        "event_type": event_type,
        "event_reason": deepcopy(dict(reason)),
    }
    event.update(deepcopy(dict(payload)))
    return event


def _speaker_label(
    display_label: str,
    *,
    public_state: str,
    enrolled_speaker_id: str | None,
) -> dict[str, object]:
    label = _required_text(display_label, "display_label")
    if public_state == "unknown":
        if not _UNKNOWN_PATTERN.fullmatch(label):
            raise ValueError("public unknown identity requires an Unknown_N label")
        return {
            "label_kind": "unknown",
            "display_label": label,
            "enrolled_speaker_id": None,
        }
    enrolled = _required_text(enrolled_speaker_id, "enrolled_speaker_id")
    if _UNKNOWN_PATTERN.fullmatch(label):
        raise ValueError("known identity cannot use an Unknown_N display label")
    return {
        "label_kind": "known",
        "display_label": label,
        "enrolled_speaker_id": enrolled,
    }


def _transcript_span(
    span: TranscriptSpan,
    *,
    enrolled_speaker_ids_by_label: Mapping[str, str],
) -> dict[str, object]:
    speaker_label = None
    if span.speaker_label is not None:
        is_unknown = bool(_UNKNOWN_PATTERN.fullmatch(span.speaker_label))
        speaker_label = _speaker_label(
            span.speaker_label,
            public_state="unknown" if is_unknown else "confirmed",
            enrolled_speaker_id=(
                None
                if is_unknown
                else enrolled_speaker_ids_by_label.get(
                    span.speaker_label, span.speaker_label
                )
            ),
        )
    return {
        "span_id": span.span_id,
        "start_sec": span.start_sec,
        "end_sec": span.end_sec,
        "text": span.text,
        "state": span.state,
        "anonymous_speaker_id": span.anonymous_speaker_id,
        "speaker_label": speaker_label,
        "source_event_ids": list(span.source_event_ids),
    }


def _public_identity_state(state: IdentityState) -> str:
    if state is IdentityState.TENTATIVE_KNOWN:
        return "tentative"
    if state is IdentityState.CONFIRMED_KNOWN:
        return "confirmed"
    return "unknown"


def _evidence_decision(transition: IdentityTransition) -> str:
    reason = transition.decision_reason
    if reason in {"insufficient_evidence", "unusable_evidence"}:
        return "insufficient_evidence"
    if reason == "quality_rejected":
        return "quality_rejected"
    if reason in {"challenger_calibration_unresolved", "no_candidate_scores"}:
        return "invalid"
    if reason in {
        "known_identity_tentative",
        "known_identity_confirmed",
        "confirmed_identity_pass",
        "challenger_confirmation_pending",
        "challenger_confirmed",
    }:
        return "accepted_known"
    return "rejected_unknown"


def _transcript_state(spans: Sequence[TranscriptSpan]) -> str:
    if any(value.state == "provisional" for value in spans):
        return "provisional"
    if spans and all(value.state == "final" for value in spans):
        return "final"
    return "committed"


def _revision_metadata(
    *,
    revision_id: str,
    revision_number: int,
    supersedes_revision_id: str | None,
    corrected_event_ids: Sequence[str],
    reason: Mapping[str, object],
) -> dict[str, object]:
    if revision_number < 0:
        raise ValueError("revision_number must be >= 0")
    return {
        "revision_id": _required_text(revision_id, "revision_id"),
        "revision_number": int(revision_number),
        "supersedes_revision_id": supersedes_revision_id,
        "corrected_event_ids": list(_unique_strings(corrected_event_ids)),
        "reason": deepcopy(dict(reason)),
    }


def _event_reason(
    code: str,
    *,
    detail: str | None = None,
    causal_event_ids: Sequence[str] = (),
) -> dict[str, object]:
    return {
        "code": _required_text(code, "event reason code"),
        "detail": detail,
        "causal_event_ids": list(_unique_strings(causal_event_ids)),
    }


def _unique_strings(values: Sequence[str]) -> tuple[str, ...]:
    materialized = tuple(str(value).strip() for value in values)
    if any(not value for value in materialized):
        raise ValueError("event identity values must be non-empty")
    if len(materialized) != len(set(materialized)):
        raise ValueError("event identity values must be unique")
    return tuple(sorted(materialized))


def _required_text(value: object, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{field_name} must be non-empty")
    return str(value)


def _sha256_text(value: str) -> str:
    text = _required_text(value, "sha256").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError("sha256 must contain 64 hexadecimal characters")
    return text


def _stable_id(prefix: str, value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:20]}"
