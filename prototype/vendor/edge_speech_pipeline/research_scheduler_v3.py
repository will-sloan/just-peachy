"""Shared S6C tracker/name scheduler. See README_RESEARCH_S6C.md."""
from __future__ import annotations

from copy import deepcopy
import heapq
import math
import time

from .research_scheduler import CausalScheduler
from .research_identity_v3 import ResearchIdentityResolver, union_intervals


class CausalSchedulerV3(CausalScheduler):
    """Reuse the sealed event merge, extend only the explicit S6C observation path."""

    def __init__(self, tracker, identity_resolver, **kwargs):
        horizon = kwargs.get("revision_horizon_sec", 2.)
        if horizon == 0:
            kwargs["revision_horizon_sec"] = 1e-12
        super().__init__(tracker, **kwargs)
        self.revision_horizon = horizon
        self.identity_resolver = identity_resolver
        self._support = {}
        self._scheduling_history = []

    def push(self, event, lane):
        with self._lock:
            row = deepcopy(event)
            support = {}
            if row.get("kind") == "embedding":
                extra = {"evidence_kind", "clean_intervals", "rms", "clipping_fraction", "clean_fraction", "observation_id"}
                support = {k: row.pop(k) for k in list(row) if k in extra}
                if support.get("evidence_kind") not in {"short", "mature"}:
                    raise ValueError("S6C embedding requires explicit short/mature evidence role")
                clean = support.get("clean_intervals")
                if not isinstance(clean, list):
                    raise ValueError("S6C embedding requires explicit estimated clean support intervals")
                spans = union_intervals(clean)
                start, end = row.get("source_start_sec"), row.get("source_end_sec")
                if any(a < start-1e-9 or b > end+1e-9 for a,b in spans):
                    raise ValueError("clean evidence outside actual waveform support")
                support["clean_intervals"] = spans
                for key in ("rms", "clipping_fraction", "clean_fraction"):
                    if key in support and (isinstance(support[key], bool) or not isinstance(support[key], (int, float)) or not math.isfinite(support[key]) or support[key] < 0):
                        raise ValueError("nonfinite/invalid S6C evidence measurement")
                if any(support.get(k, 0) > 1 for k in ("clipping_fraction", "clean_fraction")):
                    raise ValueError("evidence fraction exceeds one")
                if "observation_id" in support and support["observation_id"] != row.get("event_id"):
                    raise ValueError("observation identity must match stable event identity")
            eid = row.get("event_id")
            if eid in self._support:
                raise ValueError("duplicate pending S6C event")
            self._support[eid] = support
            try:
                return super().push(row, lane)
            except Exception:
                self._support.pop(eid, None)
                raise

    def _drain(self):
        records = []
        bound = min(self.watermarks.values())
        while self._heap and self._heap[0][0] < bound:
            _, _, _, event = heapq.heappop(self._heap)
            event.update(self._support.pop(event["event_id"], {}))
            self._last_available = event["available_at_sec"]
            if event["kind"] == "segmentation":
                self._segmentation.append(event)
                self._segmentation = self._segmentation[-4096:]
            elif event["kind"] == "embedding":
                now = event["available_at_sec"]
                spatial = self.provider.evidence(event["source_start_sec"], now) if self.cues_enabled else None
                if spatial is not None and spatial.available_at_sec > now:
                    raise ValueError("provider exposed future cue")
                started = time.perf_counter()
                decision = self.tracker.update(event["vector"], event["source_start_sec"], event["source_end_sec"], now,
                    spatial=spatial, speech=event.get("speech", True), overlap=event.get("overlap", False),
                    evidence_kind=event["evidence_kind"], clean_intervals=event["clean_intervals"], observation_id=event["event_id"])
                tracker_cost = time.perf_counter()-started
                # Publish a past-view cache; the inference lane never reads mutable future tracker state.
                context = self.tracker.scheduling_state(now)
                self._scheduling_history.append((now, deepcopy(context)))
                self._scheduling_history = self._scheduling_history[-4096:]
                self.identity_resolver.sync_tracks({r["track_id"] for r in context}, now)
                decision = self.identity_resolver.resolve(decision, event)
                cost = time.perf_counter()-started
                self.policy_total_sec += cost
                self._decisions.append((event, decision))
                self._decisions = self._decisions[-4096:]
                records.append(self._record("speaker_decision", event, {"decision": decision,
                    "policy_compute_sec": cost, "tracker_compute_sec": tracker_cost,
                    "identity_compute_sec": decision["identity_compute_sec"], "spatial_used": spatial is not None,
                    "scheduler_state_overhead_sec": max(0., cost-tracker_cost-decision["identity_compute_sec"]),
                    "timing_policy": "shared actual upstream availability; separate measured tracker/name cost"}))
                if decision["identity"]["query_executed"]:
                    records.append(self._record("identity_decision", event, {"tracker_id": decision.get("tracker_id"),
                        "anonymous_label": decision.get("anonymous_label"), "identity": decision["identity"]}))
                records.extend(self._revise(event, decision))
            else:
                records.extend(self._asr(event))
        return records

    def tracking_context(self, available_at_sec):
        with self._lock:
            eligible = [rows for stamp, rows in self._scheduling_history if stamp <= available_at_sec]
            return deepcopy(eligible[-1]) if eligible else []

    def _asr(self, event):
        records = super()._asr(event)
        row = self._utterances.get(event["utterance_id"])
        if row is not None:
            eligible = [(e,d) for e,d in self._decisions if e["available_at_sec"] <= event["available_at_sec"]
                and d.get("tracker_id") == row.get("tracker_id") and e["source_end_sec"] <= event["source_end_sec"]]
            decision = eligible[-1][1] if eligible else {}
            naming = decision.get("identity", {})
            row.setdefault("first_anonymous_label", decision.get("anonymous_label", "Unknown"))
            row.setdefault("first_known_name", None)
            row.setdefault("first_known_name_time", None)
            row.setdefault("first_final_known_name", None)
            row["latest_anonymous_label"] = decision.get("anonymous_label", "Unknown")
            # A name belongs to this currently supported display, not merely any old track score.
            name = naming.get("known_name") if row.get("latest_label") == naming.get("display_label") else None
            row["latest_known_name"] = name
            row["latest_known_profile_id"] = naming.get("known_profile_id") if name else None
            row["latest_naming_state"] = naming.get("naming_state", "unresolved") if name else "unresolved"
            if name and row["first_known_name"] is None:
                row["first_known_name"], row["first_known_name_time"] = name, event["available_at_sec"]
            if event["final"]:
                row["first_final_known_name"] = name
        # Parent emits before returning; v3 _record decorates before its sink.
        return records

    def _record(self, kind, event, payload):
        if kind in {"transcript_partial", "transcript_final"}:
            # Resolve payload fields before the native sink observes the event.
            record = self._utterances.get(event.get("utterance_id"), {})
            candidates = [(e,d) for e,d in self._decisions if e["available_at_sec"] <= event["available_at_sec"]
                and d.get("tracker_id") == payload.get("tracker_id") and e["source_end_sec"] <= event["source_end_sec"]]
            d = candidates[-1][1] if candidates else {}
            naming = d.get("identity", {})
            name = naming.get("known_name") if payload.get("latest_label") == naming.get("display_label") else None
            record.setdefault("first_anonymous_label", d.get("anonymous_label", "Unknown"))
            record.setdefault("first_known_name", None)
            record.setdefault("first_known_name_time", None)
            if name and record["first_known_name"] is None:
                record["first_known_name"], record["first_known_name_time"] = name, event["available_at_sec"]
            record.update(latest_anonymous_label=d.get("anonymous_label", "Unknown"), latest_known_name=name,
                latest_known_profile_id=naming.get("known_profile_id") if name else None,
                latest_naming_state=naming.get("naming_state", "unresolved") if name else "unresolved")
            if kind == "transcript_final":
                record["first_final_known_name"] = name
            payload = {**payload, **{k:v for k,v in record.items() if "known" in k or "naming" in k or "anonymous" in k}}
        elif kind == "transcript_label_revision":
            row = self._utterances.get(payload.get("utterance_id"))
            if row is not None:
                ongoing = payload.get("revision_scope") == "ongoing_utterance_display"
                if ongoing:
                    # The parent emits this revision before updating its row.
                    # Use the new eligible decision/payload, never the old row's name.
                    _, _, selected, _ = self._eligible(event)
                    d = selected or {}
                else:
                    candidates = [(e,d) for e,d in self._decisions if e["available_at_sec"] <= event["available_at_sec"]
                        and d.get("tracker_id") == row.get("tracker_id")]
                    d = candidates[-1][1] if candidates else {}
                naming = d.get("identity", {})
                name = naming.get("known_name") if payload.get("latest_label") == naming.get("display_label") else None
                latest = dict(latest_anonymous_label=d.get("anonymous_label", "Unknown"), latest_known_name=name,
                    latest_known_profile_id=naming.get("known_profile_id") if name else None,
                    latest_naming_state=naming.get("naming_state", "unresolved") if name else "unresolved")
                if not ongoing:
                    row.update(latest)
                if name and row.get("first_known_name") is None:
                    row["first_known_name"], row["first_known_name_time"] = name, event["available_at_sec"]
                payload = {**payload, **{k:v for k,v in row.items() if "known" in k or "naming" in k or "anonymous" in k}, **latest}
        return super()._record(kind, event, payload)

    def _revise(self, event, decision):
        if self.revision_horizon == 0:
            return []
        records = super()._revise(event, decision)
        naming = decision.get("name_revision")
        if naming is None:
            return records
        for key, row in self._utterances.items():
            now = event["available_at_sec"]
            anchor = row.get("first_final_time") if row.get("first_final_time") is not None else row["first_display_time"]
            if row.get("tracker_id") != naming["track_id"] or not 0 <= now-anchor <= self.revision_horizon:
                continue
            if row["revision_count"] >= self.max_revisions_per_utterance:
                continue
            # Mature voice must actually overlap the attributed utterance; later unrelated
            # speech from a track is not retroactive proof of an old fragment's name.
            overlap = max(row["source_start_sec"], event["source_start_sec"]) < min(row["source_end_sec"], event["source_end_sec"])
            if not overlap or row["latest_label"] == naming["replacement_label"]:
                continue
            old = row["latest_label"]
            row.update(latest_label=naming["replacement_label"], latest_label_time=now,
                latest_known_name=naming["replacement_known_name"], latest_known_profile_id=naming["replacement_known_profile_id"],
                latest_naming_state=naming["replacement_naming_state"], revision_count=row["revision_count"]+1)
            if naming["replacement_known_name"] and row.get("first_known_name") is None:
                row["first_known_name"], row["first_known_name_time"] = naming["replacement_known_name"], now
            records.append(self._record("transcript_label_revision", event, {"utterance_id": key,
                "previous_label": old, "latest_label": row["latest_label"], "latest_label_time": now,
                "latest_known_name": row["latest_known_name"], "latest_known_profile_id": row["latest_known_profile_id"],
                "latest_naming_state": row["latest_naming_state"], "first_known_name": row.get("first_known_name"),
                "first_known_name_time": row.get("first_known_name_time"), "first_display_label": row["first_display_label"],
                "first_display_time": row["first_display_time"], "first_final_label": row["first_final_label"],
                "first_final_time": row["first_final_time"], "reason": naming["reason"],
                "revision_scope": "bounded_post_association_name", "replacement_tracker_id": row["tracker_id"],
                "evidence_ids": [event["event_id"]], "label_revision_of": key, "first_display_is_preserved": True,
                "changes_words": False, "changes_anonymous_association": False}))
        return records

    def snapshot(self):
        result = super().snapshot()
        result.update(schema_version="edge-scheduler-snapshot.v3", identity=self.identity_resolver.snapshot(),
            scheduling_snapshots_retained=len(self._scheduling_history), scheduling_snapshots_bound=4096)
        return result


def build_s6c_policy(profile, gallery=None, spatial_provider=None, emit=None):
    from .research_tracking_v3 import S6CTracker
    profile.validate()
    resolver = ResearchIdentityResolver(profile.identity, gallery)
    s = profile.scheduler
    return CausalSchedulerV3(S6CTracker(profile.tracker), resolver, spatial_provider=spatial_provider,
        cues_enabled=profile.xvf.mode in {"tracking_only", "both"}, emit=emit,
        revision_horizon_sec=s.revision_horizon_sec, evidence_expiry_sec=s.evidence_expiry_sec,
        max_pending_events=s.max_pending_events, max_events=s.max_events, max_utterances=s.max_utterances,
        max_revisions_per_utterance=s.max_revisions_per_utterance)
