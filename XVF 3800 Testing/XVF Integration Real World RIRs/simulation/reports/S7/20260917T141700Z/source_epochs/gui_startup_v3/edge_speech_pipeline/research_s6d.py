"""Opt-in S6D delivery and presentation contracts. See README_RESEARCH_S6D.md."""
from __future__ import annotations

from collections import OrderedDict, deque
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import queue
import threading
import time


@dataclass(frozen=True)
class S6DSettings:
    schema_version: str = "edge-s6d.v1"
    text_delivery: bool = True
    boundary_repair: bool = True
    transcript_mode: str = "T0"
    selected_profile_ids: tuple[str, ...] = ()
    all_enrolled: bool = False
    direction_mode: str = "V0"
    direction_max_age_sec: float = 0.75
    name_max_age_sec: float = 2.0
    minimum_association_confidence: float = 0.8
    queue_capacity: int = 8192
    policy_queue_capacity: int = 2048
    punctuation_queue_capacity: int = 128
    max_display_rows: int = 4096

    def validate(self):
        if any(type(getattr(self, key)) is not bool for key in ("text_delivery", "boundary_repair", "all_enrolled")):
            raise ValueError("S6D switches require actual booleans")
        if self.schema_version != "edge-s6d.v1" or self.transcript_mode not in {"T0", "T1", "T2"} or self.direction_mode not in {"V0", "V1", "V2", "V3"}:
            raise ValueError("invalid S6D schema or mode")
        if self.transcript_mode == "T1" and (len(self.selected_profile_ids) != 1 or self.all_enrolled):
            raise ValueError("T1 requires exactly one preselected profile ID")
        if self.transcript_mode == "T2" and not (self.selected_profile_ids or self.all_enrolled):
            raise ValueError("T2 requires an explicit selected set or all_enrolled")
        if self.direction_mode == "V2" and not self.selected_profile_ids:
            raise ValueError("V2 requires an explicit selected enrolled person/set")
        if len(set(self.selected_profile_ids)) != len(self.selected_profile_ids) or any(not isinstance(x, str) or not x for x in self.selected_profile_ids):
            raise ValueError("selected profile IDs must be unique nonempty strings")
        for key in ("queue_capacity", "policy_queue_capacity", "punctuation_queue_capacity", "max_display_rows"):
            if type(getattr(self, key)) is not int or not 1 <= getattr(self, key) <= 65536:
                raise ValueError("finite positive S6D queue/state bounds required")
        for key in ("direction_max_age_sec", "name_max_age_sec"):
            if not isinstance(getattr(self, key), (int, float)) or not math.isfinite(getattr(self, key)) or not 0 < getattr(self, key) <= 30:
                raise ValueError("finite bounded evidence ages required")
        if not 0 < self.minimum_association_confidence <= 1:
            raise ValueError("invalid association confidence threshold")
        return self

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        data["selected_profile_ids"] = tuple(data.get("selected_profile_ids", ()))
        return cls(**data).validate()

    def receipt(self):
        return {**asdict(self), "selection_bound_before_predictions": True,
            "acceptance_goals": {"additional_first_text_p50_sec": 0.10, "additional_first_text_p95_sec": 0.25,
                "label_display_only_raw_words_identical": True, "p99_and_never_emitted_required": True},
            "scope": "presentation filter on complete journal; no acoustic extraction", "default_promoted": False}


class BoundedWorker:
    """One owner, bounded queue, nonblocking producers, explicit failure on overflow."""
    def __init__(self, name, handler, capacity):
        self.name, self.handler = name, handler
        self.queue = queue.Queue(maxsize=capacity)
        self.error = None
        self.accepted = self.completed = self.max_depth = 0
        self.max_age_sec = self.max_handler_sec = 0.0
        self.closed = False
        self._lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name=name, daemon=True)
        self.thread.start()

    def submit(self, item):
        with self._lock:
            if self.closed or self.error:
                raise RuntimeError(f"{self.name} is closed or failed: {self.error}")
            try:
                self.queue.put_nowait((time.perf_counter(), item))
            except queue.Full as exc:
                raise RuntimeError(f"{self.name} bounded queue exhausted; no silent drop") from exc
            self.accepted += 1
            self.max_depth = max(self.max_depth, self.queue.qsize())

    def _run(self):
        while True:
            stamp, item = self.queue.get()
            if item is None:
                self.queue.task_done()
                return
            start = time.perf_counter()
            self.max_age_sec = max(self.max_age_sec, start-stamp)
            try:
                self.handler(item)
                self.completed += 1
            except BaseException as exc:
                self.error = f"{type(exc).__name__}: {exc}"
            finally:
                self.max_handler_sec = max(self.max_handler_sec, time.perf_counter()-start)
                self.queue.task_done()

    def submit_at_admission(self, factory, clock=time.perf_counter):
        """Opt-in atomic factory: stamp only after locks/capacity admit insertion.

        Queue's own mutex prevents the worker observing a partially stamped item.
        Legacy submit and all existing worker/stop/drain behavior are unchanged.
        """
        with self._lock:
            if self.closed or self.error:
                raise RuntimeError(f"{self.name} is closed or failed: {self.error}")
            with self.queue.not_full:
                if self.queue.maxsize > 0 and self.queue._qsize() >= self.queue.maxsize:
                    raise RuntimeError(f"{self.name} bounded queue exhausted; no silent drop")
                stamp = clock()
                item = factory(stamp)
                self.queue._put((stamp, item))
                self.queue.unfinished_tasks += 1
                self.accepted += 1
                self.max_depth = max(self.max_depth, self.queue._qsize())
                self.queue.not_empty.notify()

    def close(self, timeout=60.0):
        if self.closed and not self.thread.is_alive():
            if self.error or self.completed != self.accepted:
                raise RuntimeError(f"{self.name} failed: {self.snapshot()}")
            return
        deadline = time.perf_counter()+timeout
        with self._lock:
            self.closed = True
        # A blocking close is restricted to finalization, never inference/publication.
        self.queue.put((time.perf_counter(), None), timeout=max(.001, deadline-time.perf_counter()))
        self.thread.join(max(0., deadline-time.perf_counter()))
        if self.thread.is_alive() or self.error or self.completed != self.accepted:
            raise RuntimeError(f"{self.name} failed to drain: {self.snapshot()}")

    def snapshot(self):
        with self.queue.mutex:
            oldest = self.queue.queue[0][0] if self.queue.queue else None
        return {"name": self.name, "depth": self.queue.qsize(), "capacity": self.queue.maxsize,
            "oldest_age_sec": max(0., time.perf_counter()-oldest) if oldest else 0.,
            "accepted": self.accepted, "completed": self.completed, "max_depth": self.max_depth,
            "max_age_sec": self.max_age_sec, "max_handler_sec": self.max_handler_sec,
            "error": self.error, "thread_alive": self.thread.is_alive(), "closed": self.closed}


class EventInbox:
    """Bounded GUI/CLI inbox; only superseded same-utterance partials coalesce."""
    def __init__(self, capacity):
        self.capacity = capacity
        self._rows = deque()
        self._condition = threading.Condition()
        self.coalesced = self.max_depth = self.consumed = 0
        self.max_age_sec = 0.

    @staticmethod
    def _key(event):
        if event.event_type == "transcript_partial" or event.event_type == "s6d_text_ready" and not event.payload.get("final"):
            return event.event_type, event.payload.get("utterance_id")
        return None

    def put(self, event):
        with self._condition:
            key = self._key(event)
            if key is not None:
                for i in range(len(self._rows)-1, -1, -1):
                    if self._key(self._rows[i][1]) == key:
                        del self._rows[i]
                        self.coalesced += 1
                        break
            if len(self._rows) >= self.capacity:
                raise RuntimeError("S6D event consumer queue full; committed events not discarded")
            self._rows.append((time.perf_counter(), event))
            self.max_depth = max(self.max_depth, len(self._rows))
            self._condition.notify()

    def get(self, block=True, timeout=None):
        with self._condition:
            if not self._rows and block:
                self._condition.wait_for(lambda: bool(self._rows), timeout=timeout)
            if not self._rows:
                raise queue.Empty
            stamp, event = self._rows.popleft()
            age = time.perf_counter()-stamp
            self.max_age_sec = max(self.max_age_sec, age)
            self.consumed += 1
            event.payload["consumer_monotonic_sec"] = time.perf_counter()
            event.payload["consumer_queue_age_sec"] = age
            return event

    def empty(self):
        return self.qsize() == 0

    def qsize(self):
        with self._condition:
            return len(self._rows)

    def snapshot(self):
        with self._condition:
            return {"depth": len(self._rows), "capacity": self.capacity, "coalesced_obsolete_ui_partials": self.coalesced,
                "max_depth": self.max_depth, "consumed": self.consumed, "max_age_sec": self.max_age_sec,
                "oldest_age_sec": time.perf_counter()-self._rows[0][0] if self._rows else 0.}


class PolicyDispatcher:
    """Move the existing sealed policy merge off both inference lanes."""
    def __init__(self, scheduler, capacity):
        self.scheduler = scheduler
        self.worker = BoundedWorker("edge-s6d-policy", self._handle, capacity)
        self._context = []

    def _handle(self, command):
        op, arg = command
        if op == "push":
            self.scheduler.push(*arg)
        elif op == "advance":
            self.scheduler.advance(arg)
        else:
            self.scheduler.finish()
        self._context = tuple(self.scheduler._scheduling_history)

    def push(self, event, lane):
        self.worker.submit(("push", (deepcopy(event), lane)))

    def advance(self, watermarks):
        self.worker.submit(("advance", dict(watermarks)))

    def tracking_context(self, available_at_sec):
        eligible = [rows for stamp, rows in self._context if stamp <= available_at_sec]
        return deepcopy(eligible[-1]) if eligible else []

    def finish(self):
        self.worker.submit(("finish", None))
        self.worker.close()

    def snapshot(self):
        return {**self.scheduler.snapshot(), "s6d_dispatch": self.worker.snapshot()}


class PresentationState:
    """Runtime/GUI policy. Receives predictions only, never scene references/seats."""
    def __init__(self, settings):
        self.settings = settings.validate()
        self.rows = OrderedDict()
        self._tokens = OrderedDict()
        self.revisions = self.evicted_final_rows = 0

    def token_ids(self, key, text, revision):
        words = text.split()
        previous, ids = self._tokens.get(key, ([], []))
        prefix = 0
        while prefix < min(len(words), len(previous)) and words[prefix] == previous[prefix]:
            prefix += 1
        ids = ids[:prefix] + [f"{key}:r{revision}:t{i}" for i in range(prefix, len(words))]
        self._tokens[key] = (words, ids)
        while len(self._tokens) > self.settings.max_display_rows:
            self._tokens.popitem(last=False)
        return list(ids)

    def consume(self, kind, payload, now=None):
        now = time.perf_counter() if now is None else now
        key = payload.get("utterance_id")
        if not key or kind not in {"s6d_text_ready", "transcript_partial", "transcript_final", "transcript_label_revision", "s6d_punctuation_revision"}:
            return None
        row = self.rows.get(key)
        if row is None:
            if kind in {"transcript_label_revision", "s6d_punctuation_revision"}:
                return None  # No correction of whichever row is currently visible.
            if len(self.rows) >= self.settings.max_display_rows:
                first = next((k for k,r in self.rows.items() if r.get("final")), None)
                if first is None:
                    raise RuntimeError("bounded display state exhausted by unfinished utterances")
                del self.rows[first]
                self.evicted_final_rows += 1
            row = {"utterance_id": key, "text": "", "display_text": "", "label": "Pending identity",
                "known_profile_id": None, "naming_state": "unresolved", "first_text_monotonic_sec": now,
                "first_visible_monotonic_sec": None, "final": False, "revision_count": 0}
            self.rows[key] = row
        if kind == "s6d_text_ready" and payload.get("text", "") != row["text"]:
            # Earlier confirmed identity does not license newly arrived words.
            # Keep the full text journal while this enlarged span is pending.
            row.update(label="Pending identity", known_profile_id=None, naming_state="unresolved")
        current_end = row.get("source_end_sec")
        target_end = payload.get("target_source_end_sec", payload.get("source_end_sec"))
        current_text_supported = payload.get("text") == row["text"] or (isinstance(target_end, (int,float)) and
            (current_end is None or target_end >= current_end))
        label_event = kind in {"transcript_partial", "transcript_final", "transcript_label_revision"}
        if label_event and current_text_supported:
            row["label"] = payload.get("latest_label", payload.get("speaker", row["label"]))
            row["known_profile_id"] = payload.get("latest_known_profile_id", row["known_profile_id"])
            row["naming_state"] = payload.get("latest_naming_state", row["naming_state"])
        if kind in {"s6d_text_ready", "transcript_partial", "transcript_final"}:
            # Delayed policy partials cannot regress already committed raw words.
            final = kind == "transcript_final" or payload.get("final", False)
            source_ordered = kind == "s6d_text_ready" or current_end is None or (isinstance(payload.get("source_end_sec"), (int,float)) and payload["source_end_sec"] >= current_end)
            if (not row["final"] or final) and source_ordered:
                row.update(text=payload.get("text", row["text"]),
                    display_text=payload.get("display_text", payload.get("text", row["display_text"])), final=bool(final))
                row.setdefault("source_start_sec", payload.get("source_start_sec"))
                row["source_end_sec"] = payload.get("source_end_sec", row.get("source_end_sec"))
        if kind == "s6d_punctuation_revision":
            row["punctuated_display_text"] = payload["display_text"]
            row["punctuated_raw_text"] = payload["text"]
        if row.get("punctuated_raw_text") == row["text"]:
            row["display_text"] = row["punctuated_display_text"]
        if kind.endswith("revision"):
            row["revision_count"] += 1
            self.revisions += 1
        known = row["known_profile_id"] is not None and row["naming_state"] == "confirmed"
        selected = known and (self.settings.all_enrolled or row["known_profile_id"] in self.settings.selected_profile_ids)
        row["visible"] = self.settings.transcript_mode == "T0" or selected
        row["visibility_state"] = "visible" if row["visible"] else "hidden_unselected" if known else "pending_identity"
        if row["visible"] and row["first_visible_monotonic_sec"] is None:
            row["first_visible_monotonic_sec"] = now
        row["controller_update_monotonic_sec"] = now
        return deepcopy(row)

    def lines(self, full_view=False):
        return [f'{r["label"]}: {r["display_text"]}' + (" …" if not r["final"] else "")
            for r in self.rows.values() if full_view or r.get("visible")]

    def directions(self, observations, speech, identities, now):
        """Fresh independent evidence only; unknown beam-to-voice links stay unknown.

        Each observation must bind source support and the independently observed
        voice evidence ID. Provider packet receipt time alone is insufficient.
        """
        def finite(value):
            return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value)
        def support_valid(row):
            return all(finite(row.get(k)) for k in ('source_start_sec','source_end_sec','available_at_sec')) and 0 <= row['source_start_sec'] <= row['source_end_sec'] <= row['available_at_sec']
        def same_route(row,obs):
            return all(isinstance(obs.get(k),str) and bool(obs[k]) and row.get(k)==obs[k]
                for k in ('capture_source_id','route_id','stream_id'))
        arrows, suppressed = [], []
        mode = self.settings.direction_mode
        if not finite(now) or now < 0:
            return {"mode":mode,"arrows":[],"suppressed":[{"reason":"invalid_current_clock"}],"evaluated_at_sec":None,
                "association_unavailable_is_not_pass":True}
        active_ids = set()
        for obs in observations:
            reason = None
            angle = obs.get("angle_deg")
            available = obs.get("available_at_sec")
            age = now-available if finite(available) else math.inf
            if not finite(angle) or not 0 <= angle <= 180 or obs.get("valid") is not True or not 0 <= age <= self.settings.direction_max_age_sec:
                reason = "invalid_or_stale_direction"
            matches=[r for r in identities if r.get("evidence_id") == obs.get("voice_evidence_id") and obs.get("voice_evidence_id") is not None]
            identity=matches[0] if len(matches)==1 else None
            speaking = [r for r in speech if r.get("speech") is True and r.get("overlap") is False and support_valid(r) and support_valid(obs) and
                0 <= now-r["available_at_sec"] <= self.settings.direction_max_age_sec and
                max(r["source_start_sec"], obs.get("source_start_sec", math.inf)) < min(r["source_end_sec"], obs.get("source_end_sec", -math.inf))]
            if mode in {'V2','V3'}:
                speaking=[r for r in speaking if same_route(r,obs) and isinstance(obs.get('speech_evidence_id'),str)
                    and bool(obs['speech_evidence_id']) and r.get('evidence_id')==obs['speech_evidence_id']]
            if mode != "V0" and not speaking:
                reason = reason or "no_current_exclusive_speech"
            if mode in {"V2", "V3"}:
                if not identity or not support_valid(identity) or identity.get("naming_state") != "confirmed" or not identity.get("known_profile_id") or not 0 <= now-identity["available_at_sec"] <= self.settings.name_max_age_sec:
                    reason = reason or "no_current_confirmed_voice"
                elif not support_valid(obs) or not same_route(identity,obs) or obs.get("association_verified") is not True or not finite(obs.get("association_confidence")) or not self.settings.minimum_association_confidence <= obs['association_confidence'] <= 1:
                    reason = reason or "beam_voice_association_unavailable"
                elif mode == "V2" and identity["known_profile_id"] not in self.settings.selected_profile_ids:
                    reason = reason or "unselected_voice"
                elif identity["known_profile_id"] in active_ids:
                    reason = reason or "duplicate_voice"
                elif not max(identity["source_start_sec"], obs.get("source_start_sec", math.inf)) < min(identity["source_end_sec"], obs.get("source_end_sec", -math.inf)):
                    reason = reason or "voice_direction_support_disjoint"
                elif not any(max(identity['source_start_sec'],obs['source_start_sec'],r['source_start_sec']) <
                    min(identity['source_end_sec'],obs['source_end_sec'],r['source_end_sec']) for r in speaking):
                    reason = reason or 'voice_speech_direction_support_disjoint'
            if reason:
                suppressed.append({"observation_id": obs.get("observation_id"), "reason": reason})
                continue
            if mode in {'V2','V3'}:
                speaking=[r for r in speaking if max(identity['source_start_sec'],obs['source_start_sec'],r['source_start_sec']) <
                    min(identity['source_end_sec'],obs['source_end_sec'],r['source_end_sec'])]
            if len(arrows) >= (2 if mode == "V3" else 1):
                suppressed.append({"observation_id": obs.get("observation_id"), "reason": "mode_arrow_bound"})
                continue
            pid = identity.get("known_profile_id") if identity and mode in {"V2", "V3"} else None
            if pid:
                active_ids.add(pid)
            remaining=self.settings.direction_max_age_sec-age
            if mode!='V0':
                remaining=min(remaining,max(self.settings.direction_max_age_sec-(now-r['available_at_sec']) for r in speaking))
            if mode in {'V2','V3'}:
                remaining=min(remaining,self.settings.name_max_age_sec-(now-identity['available_at_sec']))
            arrows.append({"angle_deg": angle, "known_profile_id": pid, 'known_name':identity.get('known_name') if pid else None,"age_sec": age,
                "indicator": "recent_diagnostic" if mode == "V0" else "active_speech",
                "association_confidence": obs.get("association_confidence"), "observation_id": obs.get("observation_id"),
                "folded_linear_ambiguity": True,'valid_for_sec':remaining,
                'speech_scope':'global_mono_gate' if mode=='V1' else 'independently_bound_stream' if mode in {'V2','V3'} else 'diagnostic_only',
                'capture_source_id':obs.get('capture_source_id'),'route_id':obs.get('route_id'),'stream_id':obs.get('stream_id')})
        return {"mode": mode, "arrows": arrows, "suppressed": suppressed, "evaluated_at_sec": now,
            "association_unavailable_is_not_pass": True}


def build_presentation_state(settings, *, s7=None):
    """Preserve historical defaults; enable the explicit S7 presentation contract only on request."""
    if s7 is None:
        return PresentationState(settings)
    from .research_s7_presentation import S7PresentationState
    return S7PresentationState(settings, options=s7)


def build_s6d_scheduler(profile, gallery, provider, emit, settings, *, observed_clock=None):
    from .research_scheduler_v3 import CausalSchedulerV3
    from .research_tracking_v3 import S6CTracker
    from .research_identity_v3 import ResearchIdentityResolver

    class BoundedRevisionScheduler(CausalSchedulerV3):
        def _record(self, kind, event, payload):
            if kind == "transcript_label_revision":
                target = self._utterances.get(payload.get("utterance_id"), {})
                if payload.get("revision_scope") == "ongoing_utterance_display":
                    # The parent emits before storing this new ASR extent.
                    # Its selected decision/target fields refer to the incoming
                    # ASR revision, never the previously displayed shorter row.
                    payload = {**payload, "target_source_start_sec": event["source_start_sec"],
                        "target_source_end_sec": event["source_end_sec"],
                        "target_text_revision_id": event["event_id"]}
                else:
                    payload = {**payload, "target_source_start_sec": target.get("source_start_sec"),
                        "target_source_end_sec": target.get("source_end_sec"),
                        "target_text_revision_id": target.get("text_revision_id")}
            return super()._record(kind, event, payload)

        def _revise(self, event, decision):
            # Keep original rules unless explicitly enabled. A late committed
            # observation cannot borrow a neighbouring voice's source span.
            if not settings.boundary_repair:
                return super()._revise(event, decision)
            records = []
            now = event["available_at_sec"]
            for key,row in self._utterances.items():
                overlap = max(row["source_start_sec"], event["source_start_sec"]) < min(row["source_end_sec"], event["source_end_sec"])
                fresh = 0 <= now-event["source_end_sec"] <= self.evidence_expiry
                conflicting = row.get("tracker_id") is not None and row.get("tracker_id") != decision.get("tracker_id") and row.get("latest_state") not in {"pending", "provisional", "unknown", "uncertain"}
                anchor = row.get("first_final_time") if row.get("first_final_time") is not None else row.get("last_text_available_at_sec", row["first_display_time"])
                if not overlap or not fresh or conflicting or event.get("overlap") or not event.get("speech", True) or not 0 <= now-anchor <= self.revision_horizon or row["revision_count"] >= self.max_revisions_per_utterance:
                    continue
                pending = row.get("latest_state") in {"pending", "provisional", "unknown", "uncertain"}
                committed = decision.get("committed", decision.get("state") in {"committed", "known", "anonymous", "confirmed"})
                naming = decision.get("identity", {})
                same_track = row.get("tracker_id") is not None and row["tracker_id"] == decision.get("tracker_id")
                name_revision = decision.get("name_revision")
                same_track_name_update = same_track and isinstance(name_revision,dict) and name_revision.get('track_id') == row['tracker_id']
                if not (pending and committed or same_track and naming.get("naming_state") == "confirmed" or same_track_name_update):
                    continue
                label = decision.get("display_label", decision.get("anonymous_label", "Unknown"))
                if label == row["latest_label"]:
                    continue
                old = row["latest_label"]
                row.update(latest_label=label, latest_label_time=now, latest_state=decision.get("state", "unknown"),
                    tracker_id=decision.get("tracker_id"), evidence_id=event["event_id"],
                    decision_id=decision.get("decision_id"), revision_count=row["revision_count"]+1)
                records.append(self._record("transcript_label_revision", event, {"utterance_id": key,
                    "previous_label": old, "latest_label": label, "latest_label_time": now,
                    "latest_state": row["latest_state"], "replacement_tracker_id": row["tracker_id"],
                    "first_display_label": row["first_display_label"], "first_display_time": row["first_display_time"],
                    "first_final_label": row["first_final_label"], "first_final_time": row["first_final_time"],
                    "reason": "fresh overlapping voice revises stable utterance; active-text horizon",
                    "revision_scope": "s6d_bounded_active_text", "revision_anchor_sec": anchor,
                    "evidence_ids": [event["event_id"]], "label_revision_of": key,
                    "first_display_is_preserved": True, "changes_words": False}))
            return records

        def _asr(self, event):
            result = super()._asr(event)
            if settings.boundary_repair:
                row = self._utterances.get(event["utterance_id"])
                if row is not None:
                    row["last_text_available_at_sec"] = event["available_at_sec"]
            return result

    s = profile.scheduler
    policy_class = BoundedRevisionScheduler
    if observed_clock is not None:
        from .research_s7_policy import ObservedEligibility
        class ObservedBoundedScheduler(ObservedEligibility, BoundedRevisionScheduler):
            pass
        policy_class = ObservedBoundedScheduler
    policy = policy_class(S6CTracker(profile.tracker), ResearchIdentityResolver(profile.identity, gallery),
        spatial_provider=provider, cues_enabled=profile.xvf.mode in {"tracking_only", "both"}, emit=emit,
        revision_horizon_sec=s.revision_horizon_sec, evidence_expiry_sec=s.evidence_expiry_sec,
        max_pending_events=s.max_pending_events, max_events=s.max_events, max_utterances=s.max_utterances,
        max_revisions_per_utterance=s.max_revisions_per_utterance)
    if observed_clock is not None:
        if not settings.text_delivery:
            raise ValueError("Observed availability requires bounded policy dispatch")
        from .research_s7_policy import ObservedPolicyDispatcher
        return ObservedPolicyDispatcher(policy, settings.policy_queue_capacity, observed_clock)
    return PolicyDispatcher(policy, settings.policy_queue_capacity) if settings.text_delivery else policy
