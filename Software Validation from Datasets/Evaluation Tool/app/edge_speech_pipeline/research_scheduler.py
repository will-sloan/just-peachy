"""S6B incremental causal merge and forward-only transcript label history.

The caller seals each lane with a lower bound on its next possible event. An
event is invisible until every lane is sealed strictly beyond its availability.
This handles native thread arrival races without assuming wall-time order.
"""
from __future__ import annotations

from copy import deepcopy
import heapq
import math
from numbers import Real
import threading
import time

import numpy as np


class CausalScheduler:
    def __init__(self, tracker, spatial_provider=None, cues_enabled=False,
                 revision_horizon_sec=2.0, emit=None, lanes=("speaker", "asr"),
                 evidence_expiry_sec=0.75, max_pending_events=20000,
                 max_events=1000000, max_utterances=4096, max_revisions_per_utterance=4):
        self.tracker = tracker
        self.provider = spatial_provider
        self.cues_enabled = bool(cues_enabled)
        if self.cues_enabled and self.provider is None:
            raise ValueError("cue-enabled scheduler requires a causal provider")
        if not math.isfinite(revision_horizon_sec) or revision_horizon_sec <= 0:
            raise ValueError("positive finite revision horizon required")
        self.revision_horizon = revision_horizon_sec
        if not math.isfinite(evidence_expiry_sec) or evidence_expiry_sec <= 0:
            raise ValueError("positive finite evidence expiry required")
        for value in (max_pending_events, max_events, max_utterances, max_revisions_per_utterance):
            if type(value) is not int or value < 1:
                raise ValueError("positive integer scheduler bounds required")
        self.evidence_expiry = evidence_expiry_sec
        self.max_pending_limit = max_pending_events
        self.max_events = max_events
        self.max_utterances = max_utterances
        self.max_revisions_per_utterance = max_revisions_per_utterance
        self.emit = emit
        self.watermarks = dict.fromkeys(lanes, 0.0)
        self._heap = []
        self._ids = set()
        self._lock = threading.RLock()
        self._closed = False
        self._decisions = []
        self._segmentation = []
        self._utterances = {}
        self._serial = 0
        self._last_available = 0.0
        self.policy_total_sec = 0.0
        self.max_pending = 0

    def push(self, event: dict, lane: str):
        with self._lock:
            if self._closed or lane not in self.watermarks:
                raise ValueError("closed scheduler or unknown lane")
            row = deepcopy(event)
            required = {"kind", "event_id", "source_start_sec", "source_end_sec", "available_at_sec"}
            if not required <= row.keys():
                raise ValueError("scheduler event is missing its identity/span/availability")
            if row["kind"] not in {"segmentation", "embedding", "asr"}:
                raise ValueError("unsupported scheduler event kind")
            allowed = required | {
                "embedding": {"vector", "speech", "overlap", "receptive_start_sec", "receptive_end_sec"},
                "segmentation": {"speech", "overlap"},
                "asr": {"utterance_id", "text", "final", "display_text", "punctuation", "asr_decode_ms"},
            }[row["kind"]]
            if set(row) - allowed:
                raise ValueError("unknown/reference fields are forbidden in scheduler input: " + str(sorted(set(row) - allowed)))
            for key in ("source_start_sec", "source_end_sec", "available_at_sec"):
                if not isinstance(row[key], (int, float)) or isinstance(row[key], bool):
                    raise ValueError("scheduler times must be numeric, not booleans or strings")
            start, end, ready = (float(row[k]) for k in ("source_start_sec", "source_end_sec", "available_at_sec"))
            if not all(math.isfinite(x) for x in (start, end, ready)) or not 0 <= start <= end <= ready:
                raise ValueError("invalid source/context/availability ordering")
            if ready < self.watermarks[lane]:
                raise ValueError("event arrived behind a sealed lane watermark")
            event_id = row["event_id"]
            if not isinstance(event_id, str) or not event_id or len(event_id) > 128 or event_id in self._ids:
                raise ValueError("event IDs must be unique nonempty strings")
            if row["kind"] == "embedding":
                vector = row.get("vector")
                if vector is None or len(vector) != 192 or not all(isinstance(x, Real) and not isinstance(x, (bool, np.bool_)) and math.isfinite(float(x)) for x in vector):
                    raise ValueError("finite 192-D embedding vector required")
                rstart, rend = row.get("receptive_start_sec", start), row.get("receptive_end_sec", end)
                if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in (rstart, rend)) or not 0 <= rstart <= start <= end <= rend <= ready:
                    raise ValueError("embedding context has not become available")
            if row["kind"] in {"embedding", "segmentation"}:
                if any(key in row and not isinstance(row[key], bool) for key in ("speech", "overlap")):
                    raise ValueError("speech/overlap must be boolean")
            if row["kind"] == "asr" and (not isinstance(row.get("utterance_id"), str) or not isinstance(row.get("text"), str) or not isinstance(row.get("final"), bool)):
                raise ValueError("ASR event needs stable utterance_id, text and boolean final")
            if row["kind"] == "asr":
                if not row["utterance_id"] or len(row["utterance_id"]) > 128 or "display_text" in row and not isinstance(row["display_text"], str):
                    raise ValueError("invalid ASR utterance ID/display text")
                punctuation = row.get("punctuation")
                if punctuation is not None and (not isinstance(punctuation, dict) or set(punctuation) - {"text", "status", "terminal_fallback", "compute_ms", "model_id", "model_sha256", "error"}):
                    raise ValueError("unknown/reference punctuation fields are forbidden")
                costs = [row.get("asr_decode_ms", 0.0)] + ([punctuation.get("compute_ms", 0.0)] if punctuation else [])
                if any(not isinstance(x, Real) or isinstance(x, (bool, np.bool_)) or not math.isfinite(x) or x < 0 for x in costs):
                    raise ValueError("ASR/punctuation compute durations must be finite and nonnegative")
            self._ids.add(event_id)
            if len(self._ids) > self.max_events or len(self._heap) >= self.max_pending_limit:
                raise RuntimeError("bounded scheduler event budget exceeded; no silent eviction")
            priority = {"segmentation": 0, "embedding": 1, "asr": 2}[row["kind"]]
            heapq.heappush(self._heap, (ready, priority, event_id, row))
            self.max_pending = max(self.max_pending, len(self._heap))
            return self._drain()

    def advance(self, watermarks: dict):
        with self._lock:
            for lane, value in watermarks.items():
                if lane not in self.watermarks or math.isnan(value) or value < self.watermarks[lane]:
                    raise ValueError("watermarks must advance monotonically on known lanes")
                self.watermarks[lane] = float(value)
            return self._drain()

    def finish(self):
        with self._lock:
            self.watermarks = dict.fromkeys(self.watermarks, math.inf)
            result = self._drain()
            self._closed = True
            return result

    def snapshot(self):
        with self._lock:
            return {"schema_version": "edge-scheduler-snapshot.v2", "utterances": deepcopy(list(self._utterances.values())),
                    "pending_events": len(self._heap), "max_pending_events": self.max_pending,
                    "watermarks": {k: v if math.isfinite(v) else "closed" for k, v in self.watermarks.items()},
                    "policy_total_sec": self.policy_total_sec, "closed": self._closed,
                    "total_input_events": len(self._ids), "emitted_events": self._serial,
                    "speaker_decisions_retained": len(self._decisions), "segmentation_observations_retained": len(self._segmentation),
                    "state_bounds": {"max_pending_events": self.max_pending_limit, "max_total_events": self.max_events,
                                     "max_utterances": self.max_utterances, "max_reconciliations_per_utterance": self.max_revisions_per_utterance,
                                     "speaker_history": 4096, "segmentation_history": 4096}}

    def _record(self, kind, event, payload):
        self._serial += 1
        result = {"event_type": kind, "event_id": f"scheduler:{self._serial:08d}",
                  "source_start_sec": event["source_start_sec"], "source_end_sec": event["source_end_sec"],
                  "available_at_sec": event["available_at_sec"], "input_available_at_sec": event["available_at_sec"],
                  "release_watermark_lower_bound_sec": min(self.watermarks.values()) if math.isfinite(min(self.watermarks.values())) else None,
                  "release_after_all_lanes_closed": all(math.isinf(x) for x in self.watermarks.values()),
                  "input_event_id": event["event_id"], **payload}
        if self.emit:
            self.emit(deepcopy(result))
        return result

    def _drain(self):
        result = []
        bound = min(self.watermarks.values())
        while self._heap and self._heap[0][0] < bound:
            _, _, _, event = heapq.heappop(self._heap)
            self._last_available = event["available_at_sec"]
            if event["kind"] == "segmentation":
                self._segmentation.append(event)
                self._segmentation = self._segmentation[-4096:]
            elif event["kind"] == "embedding":
                now = event["available_at_sec"]
                observation = self.provider.evidence(event["source_start_sec"], now) if self.cues_enabled else None
                if observation is not None and observation.available_at_sec > now:
                    raise ValueError("provider exposed future spatial evidence")
                started = time.perf_counter()
                decision = self.tracker.update(event["vector"], event["source_start_sec"], event["source_end_sec"], now,
                                               spatial=observation, speech=event.get("speech", True), overlap=event.get("overlap", False))
                cost = time.perf_counter() - started
                self.policy_total_sec += cost
                decision = deepcopy(decision)
                decision.setdefault("evidence_id", event["event_id"])
                self._decisions.append((event, decision))
                self._decisions = self._decisions[-4096:]
                result.append(self._record("speaker_decision", event, {"decision": decision, "policy_compute_sec": cost,
                    "timing_policy": "shared upstream availability; measured policy cost reported separately", "spatial_used": observation is not None}))
                result.extend(self._revise(event, decision))
            else:
                result.extend(self._asr(event))
        return result

    def _eligible(self, event):
        diagnostic = getattr(getattr(self.tracker, "config", None), "mode", None)
        if diagnostic in {"one_person", "all_unknown"}:
            label = "Speaker_1" if diagnostic == "one_person" else "Unknown"
            return label, "diagnostic_control", {"display_label": label, "diagnostic_control": diagnostic,
                "evidence_id": None, "decision_id": None, "tracker_id": 1 if diagnostic == "one_person" else None}, False
        eligible = [(e, d) for e, d in self._decisions
                    if e["source_end_sec"] <= event["source_end_sec"] and e["available_at_sec"] <= event["available_at_sec"]
                    and e["source_end_sec"] > event["source_start_sec"]
                    and event["available_at_sec"] - e["source_end_sec"] <= self.evidence_expiry + 1e-9]
        segments = [e for e in self._segmentation if e["source_end_sec"] <= event["source_end_sec"] and e["available_at_sec"] <= event["available_at_sec"]
                    and event["available_at_sec"] - e["source_end_sec"] <= self.evidence_expiry + 1e-9]
        overlap = bool(segments and segments[-1].get("overlap", False))
        decision = eligible[-1][1] if eligible else None
        label = decision.get("display_label", decision.get("anonymous_label", "Speaker_?")) if decision else "Speaker_?"
        state = decision.get("state", "pending") if decision else "pending"
        if overlap:
            label, state = "Speaker_? + overlapping speaker", "overlap_uncertain"
        return label, state, decision, overlap

    def _asr(self, event):
        if not event["text"].strip():
            return []
        key = event["utterance_id"]
        label, state, decision, overlap = self._eligible(event)
        record = self._utterances.get(key)
        if record is not None and record["first_final_time"] is not None:
            raise ValueError("ASR observation arrived after final for stable utterance ID")
        changes = []
        attribution_reason = "fresh admitted utterance evidence" if decision else "no unexpired admitted utterance evidence"
        if (event["final"] and record is not None and decision is None and not overlap
                and record.get("latest_state") not in {"pending", "unknown", "uncertain", "overlap_uncertain"}
                and record.get("evidence_id") is not None):
            label, state = record["latest_label"], record["latest_state"]
            decision = {"evidence_id": record.get("evidence_id"), "decision_id": record.get("decision_id"),
                        "tracker_id": record.get("tracker_id")}
            attribution_reason = "finalization retains prior utterance label"
        if record is None:
            if len(self._utterances) >= self.max_utterances:
                raise RuntimeError("bounded scheduler utterance budget exceeded")
            record = {"utterance_id": key, "source_start_sec": event["source_start_sec"],
                      "first_display_label": label, "first_display_time": event["available_at_sec"],
                      "first_final_label": None, "first_final_time": None, "revision_count": 0, "ongoing_display_label_changes": 0}
            self._utterances[key] = record
        elif label != record["latest_label"]:
            record["ongoing_display_label_changes"] += 1
            changes.append(self._record("transcript_label_revision", event, {"utterance_id": key,
                "previous_label": record["latest_label"], "latest_label": label, "latest_label_time": event["available_at_sec"],
                "first_display_label": record["first_display_label"], "first_display_time": record["first_display_time"],
                "first_final_label": record["first_final_label"], "first_final_time": record["first_final_time"],
                "reason": "newly available evidence on subsequent ASR display", "revision_scope": "ongoing_utterance_display",
                "evidence_ids": [decision.get("evidence_id")] if decision else [], "label_revision_of": key,
                "first_display_is_preserved": True, "changes_words": False}))
        if record["first_final_time"] is not None and event["final"]:
            raise ValueError("duplicate final for stable utterance ID")
        record.update(source_end_sec=event["source_end_sec"], text=event["text"], display_text=event.get("display_text", event["text"]),
                      latest_label=label, latest_label_time=event["available_at_sec"], latest_state=state,
                      evidence_id=decision.get("evidence_id") if decision else None,
                      decision_id=decision.get("decision_id", decision.get("first_decision_id")) if decision else None,
                      tracker_id=decision.get("tracker_id", decision.get("cluster_id")) if decision else None,
                      is_final=event["final"])
        if event["final"]:
            record["first_final_label"], record["first_final_time"] = label, event["available_at_sec"]
        payload = {**deepcopy(record), "speaker": label, "speaker_state": state, "overlap_detected": overlap,
                   "punctuation": event.get("punctuation"), "asr_decode_ms": event.get("asr_decode_ms", 0.0),
                   "first_display_is_preserved": True, "label_revision_of": None,
                   "attribution_reason": attribution_reason}
        if decision and decision.get("diagnostic_control"):
            payload["diagnostic_control"] = decision["diagnostic_control"]
        return changes + [self._record("transcript_final" if event["final"] else "transcript_partial", event, payload)]

    def _revise(self, event, decision):
        result = []
        label = decision.get("display_label", decision.get("anonymous_label", "Speaker_?"))
        committed = decision.get("committed", decision.get("state") in {"committed", "known", "anonymous", "confirmed"})
        # Later admitted acoustic evidence may resolve pending labels only within
        # the declared horizon and an actually overlapping source span. Explicit
        # tracker lineage can additionally replace an identified earlier branch.
        revisions = [x for x in decision.get("lineage", []) if isinstance(x, dict) and "revision" in str(x.get("type", x.get("event", x.get("kind", ""))))]
        for key, row in self._utterances.items():
            now = event["available_at_sec"]
            anchor = row["first_final_time"] if row["first_final_time"] is not None else row["first_display_time"]
            age = now - anchor
            if not 0 <= age <= self.revision_horizon or row["revision_count"] >= self.max_revisions_per_utterance:
                continue
            overlap = max(row["source_start_sec"], event["source_start_sec"]) < min(row["source_end_sec"], event["source_end_sec"])
            unknown = row["latest_state"] in {"pending", "provisional", "uncertain", "unknown"}
            lineage = next((r for r in revisions if row.get("decision_id") is not None and (row.get("decision_id") == r.get("revision_of") or row.get("decision_id") in r.get("target_decision_ids", [])) or row.get("evidence_id") is not None and (row.get("evidence_id") == r.get("evidence_id") or row.get("evidence_id") in r.get("target_evidence_ids", []))), None)
            if not ((unknown and overlap and committed) or lineage):
                continue
            replacement = (lineage or {}).get("replacement_anonymous_label", (lineage or {}).get("replacement_label", label))
            if replacement == row["latest_label"]:
                continue
            old = row["latest_label"]
            replacement_id = (lineage or {}).get("replacement_track_id", decision.get("tracker_id", decision.get("cluster_id")))
            is_unknown = replacement in {"Unknown", "Speaker_?"} or replacement_id is None
            replacement_state = "unknown" if is_unknown else (lineage or {}).get("replacement_state", decision["state"] if replacement_id == decision.get("tracker_id", decision.get("cluster_id")) else "reconciled")
            row.update(latest_label=replacement, latest_label_time=now, latest_state=replacement_state,
                tracker_id=None if is_unknown else replacement_id,
                evidence_id=None if is_unknown else decision.get("evidence_id"),
                decision_id=None if is_unknown else decision.get("decision_id", decision.get("first_decision_id")),
                revision_count=row["revision_count"] + 1)
            result.append(self._record("transcript_label_revision", event, {"utterance_id": key,
                "previous_label": old, "latest_label": replacement, "latest_label_time": now,
                "latest_state": replacement_state, "replacement_tracker_id": None if is_unknown else replacement_id,
                "first_display_label": row["first_display_label"], "first_display_time": row["first_display_time"],
                "first_final_label": row["first_final_label"], "first_final_time": row["first_final_time"],
                "reason": (lineage or {}).get("reason", "later overlapping committed acoustic evidence"),
                "revision_scope": "bounded_forward_reconciliation",
                "evidence_ids": [decision.get("evidence_id", event["event_id"])], "label_revision_of": key,
                "first_display_is_preserved": True, "changes_words": False}))
        return result


class EmbeddingAdmission:
    """Audio-derived bounded observation scheduling; never a speech drop gate.

    Purity uses the latest *arrived* full-context segmentation frame supports.
    Unknown newer samples count as unclean. Debt can bypass a sparse cadence,
    but cannot bypass RMS, overlap, minimum length or purity requirements.
    """
    def __init__(self, profile):
        self.profile = profile
        self.settings = profile.embedding
        self.last_end = None
        self.last_vector = None
        self.last_cosine = 1.0
        self.previous_speech = False
        self.early_admitted = False
        self.clean_intervals = []
        self.last_angle = None
        self.last_cue_delivery = -1.0
        self.last_cue_sequence = None

    def segmentation(self, views, source_end_sec):
        p = self.profile.segmentation
        if p.post_policy == "posterior_hysteresis":
            mask = (np.asarray(views["speech_probability"]) >= p.onset) & (np.asarray(views["overlap_probability"]) < p.overlap_fraction_threshold)
        else:
            mask = np.asarray(views["speech"]).astype(bool) & ~np.asarray(views["overlap"]).astype(bool)
        step = .016875
        centers = source_end_sec - 10.0 + .0619375 / 2 + np.arange(len(mask)) * step
        intervals = []
        for center, clean in zip(centers, mask):
            start, end = max(0.0, float(center - step / 2)), min(source_end_sec, float(center + step / 2))
            if clean and end > start:
                if intervals and start <= intervals[-1][1] + 1e-9:
                    intervals[-1][1] = end
                else:
                    intervals.append([start, end])
        self.clean_intervals = intervals

    def candidate(self, rolling, block, source_end_sec, speech, overlap, observation=None):
        e = self.settings
        onset = speech and not self.previous_speech
        if not speech:
            self.early_admitted = False
        self.previous_speech = speech
        window = e.early_window_sec if e.evidence_policy == "early_short_long" and not self.early_admitted else e.window_sec
        size = round(window * 16000)
        dispatch_rms = float(np.sqrt(np.mean(np.square(block), dtype=np.float64)))
        full_rms = float(np.sqrt(np.mean(np.square(rolling[-size:]), dtype=np.float64))) if rolling.size >= size else None
        selected_rms = dispatch_rms if e.rms_policy == "dispatch" else full_rms
        start = source_end_sec - window
        spans = [(max(a, start), min(b, source_end_sec)) for a, b in self.clean_intervals if min(b, source_end_sec) > max(a, start)]
        clean_sec = sum(b-a for a,b in spans)
        longest = max((b-a for a,b in spans), default=0.0)
        fraction = min(1.0, clean_sec / window)
        purity = e.purity_policy == "gate_only" or (fraction >= e.minimum_clean_fraction and (e.purity_policy != "contiguous" or longest >= e.minimum_contiguous_clean_sec))
        since = float("inf") if self.last_end is None else source_end_sec - self.last_end
        cue_event = False
        if e.cadence_cues_enabled:
            from .research_profiles import spatial_is_fresh
            if spatial_is_fresh(observation, source_end_sec, self.profile) and observation.angle_deg is not None:
                seq = getattr(observation, "sequence", None)
                ordered = seq is None or self.last_cue_sequence is None or seq > self.last_cue_sequence
                if ordered and observation.available_at_sec > self.last_cue_delivery:
                    cue_event = self.last_angle is not None and abs(observation.angle_deg - self.last_angle) >= e.cadence_direction_deg
                    self.last_angle = observation.angle_deg
                    self.last_cue_delivery = observation.available_at_sec
                    self.last_cue_sequence = seq
        audio_event = onset or self.last_cosine < e.event_cosine_threshold
        debt = e.evidence_debt_enabled and since >= e.voice_observation_floor_sec - 1e-9
        hop = {"fixed": e.hop_sec, "frequent": e.frequent_hop_sec, "sparse": e.sparse_hop_sec,
               "event_driven": e.frequent_hop_sec if audio_event or cue_event or debt else e.sparse_hop_sec}[e.cadence_policy]
        cadence = since >= hop - 1e-9
        reason = "admitted"
        for reject, why in ((not speech, "no_speech_gate"), (overlap, "overlap_gate"), (rolling.size < size, "insufficient_contiguous_audio"),
                            (selected_rms is None or selected_rms < e.minimum_rms, "below_rms"), (not purity, "unclean_window"), (not cadence, "cadence_budget")):
            if reject:
                reason = why
                break
        diagnostic = {"admitted": reason == "admitted", "reason": reason, "window_sec": window,
            "source_start_sec": max(0.0, start), "source_end_sec": source_end_sec,
            "dispatch_rms": dispatch_rms, "full_window_rms": full_rms, "selected_rms": selected_rms,
            "rms_policy": e.rms_policy, "clean_fraction": fraction, "contiguous_clean_sec": longest,
            "purity_policy": e.purity_policy, "audio_event": bool(audio_event), "cue_event": bool(cue_event),
            "evidence_debt_due": bool(debt), "selected_hop_sec": hop,
            "since_last_observation_sec": since if math.isfinite(since) else None,
            "voice_floor_is_admission_opportunity_not_unsafe_embedding_override": True}
        return size if reason == "admitted" else None, diagnostic

    def admitted(self, vector, source_end_sec):
        vector = np.asarray(vector, dtype=np.float32)
        self.last_cosine = float(np.dot(vector, self.last_vector)) if self.last_vector is not None else 1.0
        self.last_vector = vector.copy()
        self.last_end = source_end_sec
        self.early_admitted = True

