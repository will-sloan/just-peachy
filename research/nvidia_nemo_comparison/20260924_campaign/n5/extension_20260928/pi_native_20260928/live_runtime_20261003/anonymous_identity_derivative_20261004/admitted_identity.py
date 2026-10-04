"""Resolve existing anonymous voice tracks. See README_IDENTITY_CORRECTION.md."""
import math


UNRESOLVED = frozenset(("", "Unknown", "Pending identity", "Mixed supported / pending"))


def _interval(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value) or
            not 0 <= value[0] < value[1]):
        return None
    return tuple(value)


def admitted_anonymous_identity(row, span, history):
    """Return an existing N2 anonymous label, never infer a person's name.

    The caller supplies an actual pinned S7 snapshot. A latest Unknown name is
    eligible only when its same-token, same-version admitted segment still owns
    a genuine native voice track. A missing/null track remains a retraction.
    Direction, label spelling and a prior superseded history cannot establish
    ownership. Source windows are ASR observation windows, not word alignment.
    """
    if not isinstance(history, dict) or history.get("label") != "Unknown":
        return None
    event, track = history.get("event_id"), history.get("track_id")
    if (not isinstance(event, str) or not event.startswith("n2-caption:") or
            not event.removeprefix("n2-caption:").isdigit() or len(event) > 256 or
            not isinstance(track, str) or not 0 < len(track) <= 512 or
            history.get("profile_id") is not None):
        return None
    support = _interval(history.get("source_evidence_span"))
    window = _interval([span.get("source_start_sec"), span.get("source_end_sec")])
    version = history.get("identity_version")
    if (support is None or window is None or max(support[0], window[0]) >= min(support[1], window[1]) or
            not isinstance(version, (list, tuple)) or len(version) != 2 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in version)):
        return None
    identifier, revision = span.get("id"), row.get("text_revision_id")
    if not isinstance(identifier, str) or not identifier or not isinstance(revision, str) or not revision:
        return None
    matches = [segment for segment in row.get("segments", [])
               if identifier in segment.get("token_ids", [])]
    if len(matches) != 1:
        return None
    segment = matches[0]
    target = _interval(segment.get("identity_target_span"))
    anonymous = segment.get("anonymous_label")
    if (segment.get("ownership_state") != "supported_history" or
            segment.get("session_id") != row.get("session_id") or
            segment.get("caption_key") != row.get("caption_key") or
            segment.get("text_revision_id") != revision or
            segment.get("target_revision_authority") != "EXACT_TARGET_REVISION" or
            not isinstance(segment.get("accepted_text_revision_id"), str) or
            not segment["accepted_text_revision_id"] or
            identifier not in segment.get("accepted_token_ids", []) or
            segment.get("identity_event_id") != event or
            segment.get("track_id") != track or segment.get("known_profile_id") is not None or
            segment.get("label") != "Unknown" or
            segment.get("identity_version") != list(version) or
            _interval(segment.get("identity_source_span")) != support or
            target is None or not target[0] <= window[0] < window[1] <= target[1] or
            not isinstance(anonymous, str) or not 0 < len(anonymous) <= 256 or
            anonymous in UNRESOLVED):
        return None
    # N2-caption's admitted track/source association is anonymous voice evidence
    # even when no embedding has yet produced a named-gallery match.
    return dict(label=anonymous, track_id=track, known_profile_id=None,
                evidence_kind="admitted_native_anonymous_track",
                evidence_event_id=event, identity_version=list(version),
                source_evidence_span=list(support))
