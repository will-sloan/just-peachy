"""ASR-first presentation of genuine single-D1 evidence. See README_LATE_LABELS.md."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import math
import time


def _sample(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Finite nonnegative source time required")
    return round(value*16000)


class SingleD1LateLabels:
    """Consume already-admitted S7 snapshot rows; never call or wait for a model.

    Call on the existing serialized caption consumer. Evidence comes from the
    pinned installed N2/S7 presentation, not arbitrary external dictionaries.
    DOA alone is never identity evidence. The underlying native event log remains
    authoritative and unchanged even when this view rejects a late label.
    """
    def __init__(self, selection, session_id, source_id, *, maximum_rows=128, maximum_spans=512):
        selection.validate()
        if selection.speaker_attribution != "single_d1_late_labels":
            raise ValueError("Explicit ASR-first single-D1 mode required")
        if not isinstance(session_id, str) or not session_id or not isinstance(source_id, str) or not source_id:
            raise ValueError("Exact session and source identities required")
        if type(maximum_rows) is not int or not 1 <= maximum_rows <= 512:
            raise ValueError("Bounded caption count required")
        if type(maximum_spans) is not int or not 1 <= maximum_spans <= 1024:
            raise ValueError("Bounded span count required")
        self.session_id, self.source_id = session_id, source_id
        self.window = selection.revision_window_seconds
        self.maximum_rows, self.maximum_spans = maximum_rows, maximum_spans
        self.rows = OrderedDict()
        self.retired_through = -1
        self.last_now = -math.inf

    def _clock(self, now):
        now = time.perf_counter() if now is None else now
        if type(now) not in (int, float) or not math.isfinite(now) or now < self.last_now:
            raise ValueError("Monotonic presentation clock required")
        self.last_now = now
        return now

    @staticmethod
    def _evidence(span, start, end, row=None):
        history = span.get("speaker_history", [])
        if not history:
            return None
        latest = history[-1]
        if not isinstance(latest, dict):
            return None
        label, track, event = latest.get("label"), latest.get("track_id"), latest.get("event_id")
        version, support = latest.get("identity_version"), latest.get("source_evidence_span")
        if (not isinstance(label, str) or not label or len(label) > 256 or
                not isinstance(event, str) or not event.startswith("n2-caption:") or len(event) > 256 or
                not isinstance(version, (list, tuple)) or len(version) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in version) or
                not isinstance(support, (list, tuple)) or len(support) != 2):
            return None
        left, right = _sample(support[0]), _sample(support[1])
        if max(left, start) >= min(right, end):
            return None
        unresolved = label in ("Unknown", "Pending identity", "Mixed supported / pending")
        anonymous = None
        if unresolved and row is not None:
            from admitted_identity import admitted_anonymous_identity
            anonymous = admitted_anonymous_identity(row, span, latest)
            if anonymous is not None:
                label, unresolved = anonymous["label"], False
        if not unresolved and (not isinstance(track, str) or not track or len(track) > 512):
            return None
        # Unknown from a genuine native correction can retract a prior label.
        return dict(label="Unknown" if unresolved else label, track_id=None if unresolved else track,
                    known_profile_id=None if unresolved else latest.get("profile_id"),
                    evidence_event_id=event, evidence_start_sample=left, evidence_end_sample=right,
                    identity_version=list(version), supported=not unresolved,
                    evidence_kind="admitted_native_anonymous_track" if anonymous else "native_caption_identity")

    def _projection(self, state, now):
        spans = []
        for token in state["spans"].values():
            expired = now >= token["deadline"]
            evidence = token["evidence"]
            supported = bool(evidence and evidence["supported"])
            spans.append(dict(span_id=token["id"], start_sample=token["start"], end_sample=token["end"],
                speaker=evidence["label"] if evidence else "Unknown", supported=supported,
                status=("expired_supported" if supported else "expired_unknown") if expired else
                       ("attributed" if supported else "pending"),
                revision_deadline_monotonic=token["deadline"],
                evidence=deepcopy(evidence) if evidence else None,
                timing_kind="ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT"))
        all_supported = bool(spans) and all(row["supported"] for row in spans) and not state["overflow"]
        any_supported = any(row["supported"] for row in spans)
        pending = any(row["status"] == "pending" for row in spans) or (not spans and now < state["deadline"])
        labels = {row["speaker"] for row in spans if row["supported"]}
        label = next(iter(labels)) if all_supported and len(labels) == 1 else (
            "Multiple speakers" if all_supported else "Mixed supported / Unknown" if any_supported else "Unknown")
        status = "attributed" if all_supported else "partially_attributed" if any_supported else "pending"
        if not pending and not all_supported:
            status = "expired_supported" if any_supported else "expired_unknown"
        elif all_supported and spans and all(row["status"].startswith("expired_") for row in spans):
            status = "expired_supported"
        return dict(speaker_attribution="single_d1_late_labels", speaker=label, label=label,
                    known_name=None, known_profile_id=None, provisional=pending,
                    attribution_status=status, speaker_supported=any_supported,
                    fully_attributed=all_supported, attribution_spans=spans,
                    evidence_capacity_exceeded=state["overflow"], source_id=self.source_id,
                    sample_rate=16000, native_dual_worker=False)

    def project(self, row, *, now=None):
        now = self._clock(now)
        if row.get("session_id") != self.session_id:
            raise ValueError("Foreign caption session")
        utterance = row.get("utterance_id")
        if not isinstance(utterance, str) or not utterance:
            raise ValueError("Stable utterance ID required")
        key = self.session_id+"/"+utterance
        if row.get("caption_key", key) != key:
            raise ValueError("Caption identity differs from session/utterance")
        start, end = _sample(row["source_start_sec"]), _sample(row["source_end_sec"])
        if end < start:
            raise ValueError("Reversed caption interval")
        text, display = row.get("text"), row.get("display_text", row.get("text"))
        if not isinstance(text, str) or not isinstance(display, str):
            raise ValueError("Unchanged ASR text required")
        state = self.rows.get(key)
        if state is None:
            if end <= self.retired_through:
                return None
            if len(self.rows) >= self.maximum_rows:
                _, retired = self.rows.popitem(last=False)
                self.retired_through = max(self.retired_through, retired["end"])
            state = dict(start=start, end=end, deadline=now+self.window, spans={}, signature=None, overflow=False)
            self.rows[key] = state
        elif start != state["start"]:
            raise ValueError("Caption source origin changed")
        state["end"] = max(state["end"], end)
        incoming = row.get("word_spans", [])
        state["overflow"] = len(incoming) > self.maximum_spans
        retained = {}
        for span in incoming[:self.maximum_spans]:
            identifier = span.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in retained:
                raise ValueError("Unique stable span ID required")
            left, right = _sample(span["source_start_sec"]), _sample(span["source_end_sec"])
            if not start <= left <= right <= end:
                raise ValueError("Span outside actual caption source interval")
            token = state["spans"].get(identifier)
            if token is None:
                observed = span.get("first_seen_monotonic_sec", now)
                if type(observed) not in (int, float) or not math.isfinite(observed) or observed > now+1e-6:
                    raise ValueError("Invalid span publication clock")
                token = dict(id=identifier, start=left, end=right,
                             deadline=observed+self.window, evidence=None)
            elif (token["start"], token["end"]) != (left, right):
                raise ValueError("Existing span source interval changed")
            if now < token["deadline"]:
                evidence = self._evidence(span, left, right, row)
                old = token["evidence"]
                if evidence and (old is None or tuple(evidence["identity_version"]) > tuple(old["identity_version"])):
                    token["evidence"] = evidence
            retained[identifier] = token
        state["spans"] = retained
        result = dict(session_id=self.session_id, utterance_id=utterance, caption_key=key,
                      source_start_sec=row["source_start_sec"], source_end_sec=row["source_end_sec"],
                      text=text, display_text=display, text_revision_id=row.get("text_revision_id"),
                      final=bool(row.get("final")), **self._projection(state, now))
        signature = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if signature == state["signature"]:
            return None
        state["signature"] = signature
        return result

    def expire(self, *, now=None):
        """Compact status patches for the controller's normal health tick."""
        now = self._clock(now)
        patches = []
        for key, state in self.rows.items():
            result = self._projection(state, now)
            signature = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
            if result["attribution_status"].startswith("expired_") and signature != state.get("expiry_signature"):
                state["expiry_signature"] = signature
                patches.append(dict(caption_key=key, **result))
        return patches
