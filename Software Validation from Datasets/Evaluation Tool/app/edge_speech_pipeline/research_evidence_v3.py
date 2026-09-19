"""Real short/mature inference admission; README_RESEARCH_S6C.md."""
from __future__ import annotations

import math
import time
import numpy as np

from .research_identity_v3 import union_intervals


class EvidenceAdmissionV3:
    def __init__(self, profile):
        self.profile = profile
        self.settings = profile.embedding
        self.clean = []
        self.last = {"short": None, "mature": None}
        self.vectors = {}
        self.cosine = {"short": 1., "mature": 1.}
        self.last_track_admission = {}
        self.last_angle = None
        self.last_delivery = -1.
        self.last_sequence = None
        self.previous_speech = False

    def segmentation(self, views, end):
        p = self.profile.segmentation
        mask = ((np.asarray(views["speech_probability"]) >= p.onset) &
                (np.asarray(views["overlap_probability"]) < p.overlap_fraction_threshold)) if p.post_policy == "posterior_hysteresis" else (
                np.asarray(views["speech"]).astype(bool) & ~np.asarray(views["overlap"]).astype(bool))
        centers = end - 10. + .0619375 / 2 + np.arange(len(mask)) * .016875
        self.clean = union_intervals([(max(0., float(c-.016875/2)), min(end, float(c+.016875/2)))
            for c, valid in zip(centers, mask) if valid and min(end, float(c+.016875/2)) > max(0., float(c-.016875/2))])

    def candidates(self, rolling, block, end, speech, overlap, *, tracking_context=None, observation=None):
        e = self.settings
        context = tracking_context or []
        onset = speech and not self.previous_speech
        self.previous_speech = speech
        cue_event = False
        if e.cadence_cues_enabled and observation is not None:
            age = end - observation.available_at_sec
            source_end = getattr(observation, "source_end_sec", None)
            valid = observation.valid and observation.angle_deg is not None and math.isfinite(observation.angle_deg)
            valid = valid and 0 <= age <= getattr(self.profile.tracker, "direction_max_age_sec", .25)
            valid = valid and (source_end is None or 0 <= end-source_end <= getattr(self.profile.tracker, "direction_max_age_sec", .25))
            valid = valid and observation.reliability >= self.profile.xvf.minimum_reliability
            seq = getattr(observation, "sequence", None)
            valid = valid and (seq is None or self.last_sequence is None or seq > self.last_sequence)
            if valid and observation.available_at_sec > self.last_delivery:
                cue_event = self.last_angle is not None and abs(observation.angle_deg-self.last_angle) >= e.cadence_direction_deg
                self.last_angle, self.last_delivery, self.last_sequence = observation.angle_deg, observation.available_at_sec, seq
        # Context is published from already released anonymous decisions only.
        # No known name/gallery score participates in these deficits.
        debts = []
        for row in context:
            track = row.get("track_id")
            unique = float(row.get("unique_clean_sec", 0.))
            disjoint = int(row.get("disjoint_count", 0))
            deficit = max(0., e.debt_target_unique_sec-unique)
            if deficit > 0 or disjoint < e.debt_target_disjoint_count or row.get("state") in {"provisional", "unresolved", "unknown"}:
                last = self.last_track_admission.get(track)
                due = last is None or end-last >= e.voice_observation_floor_sec-1e-9
                debts.append({"track_id": track, "unique_sec_deficit": deficit,
                    "disjoint_count_deficit": max(0, e.debt_target_disjoint_count-disjoint), "due": due})
        if not context:
            last = self.last_track_admission.get(None)
            debts = [{"track_id": None, "unique_sec_deficit": e.debt_target_unique_sec,
                "disjoint_count_deficit": e.debt_target_disjoint_count,
                "due": last is None or end-last >= e.voice_observation_floor_sec-1e-9}]
        roles = ["short", "mature"] if e.evidence_policy == "dual" else ["short"] if e.evidence_policy == "short_only" else ["mature"]
        result = []
        dispatch_rms = float(np.sqrt(np.mean(np.square(block), dtype=np.float64)))
        for role in roles:
            window = e.short_window_sec if role == "short" else e.window_sec
            size = round(window * 16000)
            start = end-window
            samples = rolling[-size:]
            full_rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if rolling.size >= size else None
            clipping = float(np.mean(np.abs(samples) >= .999)) if rolling.size >= size else None
            spans = [(max(a, start), min(b, end)) for a,b in self.clean if min(b,end) > max(a,start)]
            clean_sec = sum(b-a for a,b in spans)
            fraction = min(1., clean_sec/window)
            longest = max((b-a for a,b in spans), default=0.)
            purity = e.purity_policy == "gate_only" or (fraction >= e.minimum_clean_fraction and
                (e.purity_policy != "contiguous" or longest >= e.minimum_contiguous_clean_sec))
            rms = dispatch_rms if e.rms_policy == "dispatch" else full_rms
            base_hop = e.short_hop_sec if role == "short" else e.mature_hop_sec
            uncertainty = onset or self.cosine[role] < e.uncertainty_cosine or any(d["due"] for d in debts) or cue_event
            hop = base_hop
            if e.cadence_policy == "frequent":
                hop = e.hop_sec
            elif e.cadence_policy == "sparse" or e.cadence_policy == "uncertainty" and not uncertainty:
                hop = max(base_hop, e.sparse_hop_sec)
            since = math.inf if self.last[role] is None else end-self.last[role]
            reason = "admitted"
            for reject, why in ((not speech, "no_speech_gate"), (overlap, "overlap_gate"),
                (rolling.size < size, "insufficient_contiguous_audio"), (rms is None or rms < e.minimum_rms, "below_rms"),
                (clipping is not None and clipping > e.clipping_fraction_max, "clipped_window"),
                (not purity, "unclean_window"), (since < hop-1e-9, "cadence_budget")):
                if reject:
                    reason = why
                    break
            result.append({"admitted": reason == "admitted", "reason": reason, "evidence_kind": role,
                "samples": size, "source_start_sec": max(0., start), "source_end_sec": end,
                "window_sec": window, "dispatch_rms": dispatch_rms, "full_window_rms": full_rms,
                "selected_rms": rms, "clipping_fraction": clipping, "clean_intervals": spans,
                "estimated_clean_sec": clean_sec, "clean_fraction": fraction, "contiguous_clean_sec": longest,
                "purity_policy": e.purity_policy, "selected_hop_sec": hop, "cadence_policy": e.cadence_policy,
                "uncertainty_trigger": uncertainty if e.cadence_policy == "uncertainty" else False,
                "cue_event": cue_event, "track_debts": debts if e.cadence_policy == "uncertainty" else [],
                "naming_used_for_schedule": False, "since_last_role_sec": None if not math.isfinite(since) else since})
        return result

    def admitted(self, role, vector, end, diagnostic):
        v = np.asarray(vector, dtype=np.float32)
        self.cosine[role] = float(v @ self.vectors[role]) if role in self.vectors else 1.
        self.vectors[role] = v.copy()
        self.last[role] = end
        for debt in diagnostic.get("track_debts", []):
            if debt["due"]:
                self.last_track_admission[debt["track_id"]] = end
        if len(self.last_track_admission) > 1024:
            # Evidence-budget ledger is separate from externally visible IDs.
            for key, _ in sorted(self.last_track_admission.items(), key=lambda item: item[1])[:-1024]:
                del self.last_track_admission[key]


def run_speaker_lane_v3(engine, models):
    """Native ReDimNet/segmentation execution on the identity journal only."""
    from .research_profiles import segmentation_gate
    journal = engine._identity_journal
    if journal is None or engine._scheduler is None:
        raise RuntimeError("v3 speaker lane requires the paired identity journal and shared policy")
    profile, config = engine._research_profile, engine.config
    admission = EvidenceAdmissionV3(profile)
    step = round(profile.embedding.hop_sec*16000)
    seg_step = round(profile.segmentation.hop_sec*16000)
    rolling = np.empty(0, np.float32)
    pending = np.empty(0, np.float32)
    cursor = since_seg = seg_serial = embed_serial = 0
    ready = 0.
    empty_context_dispatches = 0
    maximum_context_age = 0.
    speech = overlap = False
    try:
        while True:
            if engine._state == "FAILED":
                raise RuntimeError("S6C identity lane aborts after session failure")
            audio = journal.read(cursor, step)
            if audio.size:
                cursor += len(audio)
                pending = np.concatenate((pending, audio))
                while pending.size >= step:
                    if engine._state == "FAILED":
                        raise RuntimeError("S6C identity dispatch aborts after session failure")
                    dispatch_started = time.perf_counter()
                    block, pending = pending[:step], pending[step:]
                    end = (cursor-len(pending))/16000
                    rolling = np.concatenate((rolling, block))[-160000:]
                    since_seg += len(block)
                    seg_api = embed_api = 0.
                    if since_seg >= seg_step:
                        since_seg %= seg_step
                        started = time.perf_counter()
                        views = models.segment(np.pad(rolling, (160000-len(rolling), 0)), include_posteriors=True)
                        seg_api = time.perf_counter()-started
                        started = time.perf_counter()
                        gate = segmentation_gate(views, config, speech)
                        speech, overlap = gate["speech"], gate["overlap"]
                        admission.segmentation(views, end)
                        post = time.perf_counter()-started
                        ready = max(ready, end)+seg_api+post
                        seg_serial += 1
                        payload = {**gate, "source_start_sec": max(0., end-profile.segmentation.hop_sec), "source_end_sec": end,
                            "receptive_start_sec": max(0., end-10.), "receptive_end_sec": end,
                            "left_padding_sec": max(0., 10.-end), "modeled_available_at_sec": ready,
                            "compute_ms": models.last_segment_ms, "model_api_elapsed_ms": seg_api*1000,
                            "postprocess_compute_ms": post*1000, "frame_step_sec": .016875,
                            "frame_duration_sec": .0619375, "identity_tap": profile.input.identity_tap,
                            "compute_finished_elapsed_sec": time.perf_counter()-engine._started_monotonic,
                            **{key+"_frames": np.asarray(views[key]).tolist() for key in
                                ("speech", "overlap", "speech_probability", "overlap_probability")}}
                        engine._emit("research_segmentation", end, payload)
                        engine._emit("segmentation", end, {**gate, "compute_ms": models.last_segment_ms})
                        engine._scheduler.push({"kind": "segmentation", "event_id": f"seg:{seg_serial:08d}",
                            "source_start_sec": payload["source_start_sec"], "source_end_sec": end,
                            "available_at_sec": ready, "speech": speech, "overlap": overlap}, "speaker")
                    started = time.perf_counter()
                    context = engine._scheduler.tracking_context(end) if profile.embedding.cadence_policy == "uncertainty" else []
                    context_stamp = max((r["snapshot_available_at_sec"] for r in context), default=None)
                    context_age = end-context_stamp if context_stamp is not None else None
                    if profile.embedding.cadence_policy == "uncertainty":
                        empty_context_dispatches += not bool(context)
                        maximum_context_age = max(maximum_context_age, context_age or 0.)
                    spatial = engine._spatial_provider.evidence(max(0., end-profile.embedding.window_sec), end) if profile.embedding.cadence_cues_enabled else None
                    candidates = admission.candidates(rolling, block, end, speech, overlap, tracking_context=context, observation=spatial)
                    gate_sec = time.perf_counter()-started
                    ready = max(ready, end)+gate_sec
                    for diagnostic in candidates:
                        engine._emit("research_embedding_admission", end, {**diagnostic,
                            "modeled_available_at_sec": ready, "compute_ms": gate_sec*1000/len(candidates),
                            "shared_admission_call": True, "identity_tap": profile.input.identity_tap,
                            "tracking_snapshot_available_at_sec": context_stamp, "tracking_context_age_sec": context_age,
                            "tracking_context_empty": not bool(context),
                            "tracking_context_used": profile.embedding.cadence_policy == "uncertainty"})
                        if not diagnostic["admitted"]:
                            continue
                        started = time.perf_counter()
                        vector = models.embed(rolling[-diagnostic["samples"]:])
                        elapsed = time.perf_counter()-started
                        embed_api += elapsed
                        ready += elapsed
                        admission.admitted(diagnostic["evidence_kind"], vector, end, diagnostic)
                        embed_serial += 1
                        eid = f"embedding:{embed_serial:08d}"
                        event = {"kind": "embedding", "event_id": eid, "observation_id": eid,
                            "source_start_sec": diagnostic["source_start_sec"], "source_end_sec": end,
                            "receptive_start_sec": diagnostic["source_start_sec"], "receptive_end_sec": end,
                            "available_at_sec": ready, "vector": vector.tolist(), "speech": speech, "overlap": overlap,
                            "evidence_kind": diagnostic["evidence_kind"], "clean_intervals": diagnostic["clean_intervals"],
                            "rms": diagnostic["selected_rms"], "clipping_fraction": diagnostic["clipping_fraction"],
                            "clean_fraction": diagnostic["clean_fraction"]}
                        engine._emit("research_embedding", end, {**{k:v for k,v in event.items() if k != "vector"},
                            "normalized_embedding": vector.tolist(), "evidence_event_id": eid,
                            "modeled_available_at_sec": ready, "compute_ms": models.last_embed_ms,
                            "model_api_elapsed_ms": elapsed*1000, "compute_finished_elapsed_sec": time.perf_counter()-engine._started_monotonic,
                            "admission": diagnostic, "identity_tap": profile.input.identity_tap,
                            "availability_method": "one serial actual segmentation/ReDimNet lane plus admission; tracker/name cost separate"})
                        engine._emit("research_embedding_observation", end, event)
                        engine._scheduler.push(event, "speaker")
                    before = time.perf_counter()
                    engine._scheduler_advance("speaker", end, ready)
                    engine._emit("research_speaker_dispatch_cost", end, {"source_start_sec": end-step/16000,
                        "source_end_sec": end, "segment_model_api_ms": seg_api*1000,
                        "embedding_model_api_ms": embed_api*1000, "gate_compute_ms": gate_sec*1000,
                        "scheduler_dispatch_ms": (time.perf_counter()-before)*1000,
                        "full_dispatch_elapsed_ms": (time.perf_counter()-dispatch_started)*1000,
                        "modeled_available_at_sec": ready, "identity_tap": profile.input.identity_tap})
                    engine._telemetry.update(speaker_cursor_sec=end, speaker_analyzed_through_sec=end,
                        speaker_lag_sec=max(0., journal.duration_sec-end),
                        s6c_schedule_empty_context_dispatches=empty_context_dispatches,
                        s6c_schedule_max_observed_context_age_sec=maximum_context_age)
            elif journal.finished and cursor >= journal.committed_samples:
                break
        engine._telemetry.update(speaker_cursor_sec=cursor/16000,
            speaker_unanalyzed_short_tail_sec=len(pending)/16000, speaker_lag_sec=0.,
            identity_audio_samples=journal.committed_samples, paired_audio_samples=engine._journal.committed_samples)
    except Exception as exc:
        engine._fail("S6C identity lane failed: " + str(exc))
    finally:
        engine._scheduler_advance("speaker", float("inf"), ready)
