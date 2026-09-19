"""Actual ProfileStore-backed S6C naming. See README_RESEARCH_S6C.md."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from .speakers import ProfileStore


def union_intervals(intervals):
    result = []
    for a, b in sorted((float(a), float(b)) for a, b in intervals):
        if not math.isfinite(a) or not math.isfinite(b) or not 0 <= a < b:
            raise ValueError("invalid clean support interval")
        if result and a <= result[-1][1] + 1e-9:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return result


def _binding(value):
    if not isinstance(value, dict) or not {"path", "sha256"} <= set(value) or set(value) - {"path", "sha256", "bytes"}:
        raise ValueError("template binding requires explicit path/hash")
    path = Path(value["path"]).resolve(strict=True)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != value["sha256"] or "bytes" in value and value["bytes"] != len(raw):
        raise ValueError("gallery byte binding differs: " + str(path))
    return path, raw, {"path": str(path), "sha256": digest, "bytes": len(raw)}


class ResearchGallery:
    """Explicit isolated gallery, validated once then immutable in memory."""

    def __init__(self, manifest_path, expected_backend_sha256, maximum_profiles=256):
        started = time.perf_counter()
        self.path = Path(manifest_path).resolve(strict=True)
        raw = self.path.read_bytes()
        manifest = json.loads(raw.decode("utf-8-sig"))
        required = {"schema_version", "gallery_id", "profile_root", "backend_sha256", "profiles"}
        if not isinstance(manifest, dict) or not required <= manifest.keys() or set(manifest) - (required | {"provenance_binding"}):
            raise ValueError("unsupported explicit research gallery manifest")
        if manifest["schema_version"] != "edge-research-gallery.v1" or manifest["backend_sha256"] != expected_backend_sha256:
            raise ValueError("research gallery schema/backend mismatch")
        self.gallery_id = manifest["gallery_id"]
        if not isinstance(self.gallery_id, str) or not self.gallery_id or len(self.gallery_id) > 128:
            raise ValueError("invalid gallery ID")
        root = Path(manifest["profile_root"]).resolve(strict=True)
        # Never fall back to or inspect the ordinary local user's profile root.
        from .config import EVALUATION_ROOT
        private = (EVALUATION_ROOT / "edge_speech_profiles").resolve()
        if root == private or private in root.parents:
            raise ValueError("private user profile directory is forbidden for S6C galleries")
        rows = manifest["profiles"]
        if not isinstance(rows, list) or not 0 <= len(rows) <= maximum_profiles:
            raise ValueError("gallery must have 0..configured maximum explicit profiles")
        expected, bindings, ids = {}, [], set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"profile_id", "display_name", "metadata", "vector"}:
                raise ValueError("unsupported gallery profile row")
            name, profile_id = row["display_name"], row["profile_id"]
            if not isinstance(name, str) or not name or len(name) > 128 or name in expected or profile_id in ids:
                raise ValueError("research names/profile IDs must be unique nonempty strings")
            mp, mb, m_binding = _binding(row["metadata"])
            vp, vb, v_binding = _binding(row["vector"])
            if mp.parent != root or vp.parent != root or mp.suffix != ".json" or vp != mp.with_suffix(".npy") or mp.stem != profile_id:
                raise ValueError("gallery profiles must be exact sibling enrollment files inside isolated root")
            metadata = json.loads(mb.decode("utf-8-sig"))
            if metadata.get("display_name") != name or metadata.get("profile_id") != profile_id or metadata.get("backend_id") != "redimnet2_b2_fp32" or metadata.get("backend_sha256") != expected_backend_sha256:
                raise ValueError("profile metadata/name/backend differs from admitted manifest")
            import io
            vector = np.load(io.BytesIO(vb), allow_pickle=False)
            if vector.shape != (192,) or vector.dtype != np.float32 or not np.all(np.isfinite(vector)) or np.linalg.norm(vector) <= 0:
                raise ValueError("gallery vectors must be finite nonzero 192D float32")
            expected[name] = {"profile_id": profile_id, "vector": vector / np.linalg.norm(vector)}
            ids.add(profile_id)
            bindings.append({"profile_id": profile_id, "display_name": name, "metadata": m_binding, "vector": v_binding})
        if {p.resolve() for p in root.glob("*.json")} != {Path(b["metadata"]["path"]) for b in bindings}:
            raise ValueError("gallery root has unmanifested/missing profile metadata")
        loaded = ProfileStore(root, expected_backend_sha256=expected_backend_sha256).load()
        if set(loaded) != set(expected):
            raise ValueError("actual ProfileStore load count/names differ from explicit gallery")
        self.names = sorted(loaded)
        for name in self.names:
            if not np.allclose(loaded[name], expected[name]["vector"], rtol=0., atol=1e-7):
                raise ValueError("actual ProfileStore template differs from admitted bytes")
        self.matrix = np.stack([loaded[n] for n in self.names]).astype(np.float32) if self.names else np.empty((0, 192), np.float32)
        self.matrix.setflags(write=False)
        self.ids = [expected[n]["profile_id"] for n in self.names]
        self.receipt = {"schema_version": "edge-research-gallery-load.v1", "gallery_id": self.gallery_id,
            "manifest": {"path": str(self.path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
            "backend_sha256": expected_backend_sha256, "loaded_count": len(self.names), "dimension": 192,
            "template_availability": "AVAILABLE" if self.names else "NO_AVAILABLE_TEMPLATES",
            "dtype": "float32", "templates": bindings, "loader": "actual speakers.ProfileStore.load",
            "loaded_elapsed_sec": time.perf_counter() - started, "preprocessing": "existing enroll_wavs; backend-bound normalized centroids"}

    def score(self, vector):
        scores = self.matrix @ vector
        order = sorted(range(len(scores)), key=lambda n: (-float(scores[n]), self.names[n]))
        return [{"profile_id": self.ids[n], "name": self.names[n], "cosine": float(scores[n])} for n in order]


class ResearchIdentityResolver:
    """Post-association naming; names never change tracker IDs or selection."""

    def __init__(self, settings, gallery=None):
        self.settings, self.gallery = settings, gallery
        if (settings.mode == "post_association") != (gallery is not None):
            raise ValueError("naming requires an actual gallery; empty control cannot accept a hidden gallery")
        self.states = {}
        self.calls = self.query_calls = self.comparisons = self.capacity_rejections = 0
        self.total_sec = 0.
        self.retired_name_states = 0
        self.retirement_records = []

    def sync_tracks(self, active_ids, now):
        """Name memory follows current live tracker state, never lifetime ID count.

        Archived anonymous tracks may re-enter, but their removed name memory
        requires a fresh query. Transcript first-name history is not erased.
        """
        for track in list(self.states):
            if track not in active_ids:
                del self.states[track]
                self.retired_name_states += 1
                self.retirement_records.append({"track_id": track, "available_at_sec": now,
                    "reason": "anonymous_track_not_in_live_registry; name must be re-identified on reentry"})
        self.retirement_records = self.retirement_records[-64:]

    def resolve(self, decision, event):
        started = time.perf_counter()
        self.calls += 1
        result = deepcopy(decision)
        anonymous = result.get("anonymous_label", "Unknown")
        track = result.get("tracker_id", result.get("track_id", result.get("cluster_id")))
        result.setdefault("tracker_id", track)
        result.setdefault("cluster_id", track)
        result.setdefault("display_label", anonymous)
        result["anonymous_state"] = result.get("state", "unknown")
        detail = {"mode": self.settings.mode, "gallery_loaded": self.gallery is not None,
            "gallery_id": self.gallery.gallery_id if self.gallery else None, "query_executed": False,
            "known_profile_id": None, "known_name": None, "naming_state": "disabled" if self.gallery is None else "unresolved",
            "reason": "empty_gallery_control" if self.gallery is None else "no_eligible_track", "scores": []}
        if self.gallery is not None and not self.gallery.names:
            detail.update(naming_state="unknown", reason="NO_AVAILABLE_TEMPLATES", available_template_count=0)
        elif self.gallery is not None and track is not None and event.get("speech", True) and not event.get("overlap", False):
            if self.settings.query_policy == "mature" and event.get("evidence_kind") != "mature":
                detail["reason"] = "short_evidence_not_a_naming_query"
                prior = self.states.get(track)
                if prior and prior.get("name"):
                    # A short observation cannot silently refresh mature name evidence.
                    detail["prior_name_not_refreshed"] = prior["name"]
                    if 0 <= event["available_at_sec"]-prior["last_query_available_sec"] <= self.settings.name_memory_sec:
                        detail.update(known_profile_id=prior["profile_id"], known_name=prior["name"],
                            naming_state=prior["naming_state"], display_label=prior["display_label"],
                            name_evidence_available_at_sec=prior["last_query_available_sec"],
                            reason="same_anonymous_track_bounded_name_memory_not_new_identification")
                        result["display_label"] = prior["display_label"]
            elif track not in self.states and len(self.states) >= self.settings.max_track_states:
                self.capacity_rejections += 1
                detail["reason"] = "bounded_identity_state_capacity"
            else:
                detail = self._query(track, anonymous, result, event, detail)
        result["identity"] = detail
        result["known_profile_id"] = detail.get("known_profile_id")
        result["known_name"] = detail.get("known_name")
        result["naming_state"] = detail["naming_state"]
        elapsed = time.perf_counter() - started
        self.total_sec += elapsed
        result["identity_compute_sec"] = elapsed
        return result

    def _query(self, track, anonymous, result, event, detail):
        s = self.settings
        vector = np.asarray(event["vector"], dtype=np.float32)
        vector = vector / max(float(np.linalg.norm(vector)), 1e-12)
        start, end = event["source_start_sec"], event["source_end_sec"]
        clean = union_intervals(event.get("clean_intervals", []))
        if any(a < start - 1e-9 or b > end + 1e-9 for a, b in clean):
            raise ValueError("naming clean support lies outside actual waveform")
        state = self.states.setdefault(track, {"intervals": [], "vectors": [], "disjoint_end": -1.,
            "disjoint_count": 0, "name": None, "profile_id": None, "naming_state": "unresolved", "observations": 0})
        prior_name, prior_id = state["name"], state["profile_id"]
        previous_sec = sum(b-a for a, b in state["intervals"])
        merged = union_intervals(state["intervals"] + clean)
        clean_sec = sum(b-a for a, b in merged)
        added = max(0., clean_sec - previous_sec)
        center = np.mean(state["vectors"], axis=0) if state["vectors"] else vector
        center /= max(float(np.linalg.norm(center)), 1e-12)
        voice_consistency = float(center @ vector)
        safe = not state["vectors"] or voice_consistency >= s.prototype_update_cosine
        if added > 1e-9 and safe and len(merged) <= s.max_intervals:
            state["intervals"] = merged
            state["vectors"].append(vector.copy())
            state["vectors"] = state["vectors"][-s.max_prototypes:]
            if start >= state["disjoint_end"] - 1e-9:
                state["disjoint_count"] += 1
                state["disjoint_end"] = end
            state["observations"] += 1
        else:
            clean_sec = previous_sec
        center = np.mean(state["vectors"], axis=0) if state["vectors"] else vector
        center /= max(float(np.linalg.norm(center)), 1e-12)
        scores = self.gallery.score(center)
        current_scores = self.gallery.score(vector)
        self.query_calls += 1
        self.comparisons += 2 * len(scores)
        top1 = scores[0]["cosine"]
        top2 = scores[1]["cosine"] if len(scores) > 1 else -1.
        margin = top1 - top2
        current_top_cosine = next(r["cosine"] for r in current_scores if r["profile_id"] == scores[0]["profile_id"])
        passes = top1 >= s.score_threshold and margin >= s.margin_threshold and current_top_cosine >= s.severe_query_cosine and safe
        mature = clean_sec >= s.minimum_unique_sec and state["disjoint_count"] >= s.minimum_disjoint_count
        name = scores[0]["name"] if passes else None
        known_id = scores[0]["profile_id"] if passes else None
        naming_state = "confirmed" if passes and mature else "tentative" if passes else "unresolved"
        display = name if naming_state == "confirmed" else name + " (tentative)" if name and s.display_tentative else anonymous
        published_name = name if naming_state == "confirmed" or s.display_tentative else None
        published_id = known_id if published_name else None
        state.update(name=published_name, profile_id=published_id, naming_state=naming_state,
            last_query_available_sec=event["available_at_sec"], display_label=display)
        detail.update(query_executed=True, known_profile_id=published_id, known_name=published_name, naming_state=naming_state,
            candidate_name=name, candidate_profile_id=known_id, name_is_displayed=published_name is not None,
            scores=scores, top1_score=top1, top2_score=top2, margin=margin,
            unique_clean_sec=clean_sec, newly_added_clean_sec=added if safe else 0., disjoint_count=state["disjoint_count"],
            query_hash=hashlib.sha256(vector.astype('<f4').tobytes()).hexdigest(),
            aggregate_hash=hashlib.sha256(center.astype('<f4').tobytes()).hexdigest(),
            current_query_name_cosine=current_top_cosine, prototype_voice_cosine=voice_consistency,
            prototype_update_accepted=bool(added > 1e-9 and safe and len(merged) <= s.max_intervals),
            reason="accepted_unique_disjoint_voice" if passes and mature else "score_pass_insufficient_unique_disjoint_evidence" if passes else "score_margin_or_voice_conflict_rejection",
            display_label=display, comparison_count=2 * len(scores), evidence_kind=event.get("evidence_kind"),
            source_start_sec=start, source_end_sec=end, available_at_sec=event["available_at_sec"],
            prior_known_name=prior_name, prior_known_profile_id=prior_id)
        result["display_label"] = display
        # Anonymous state remains independent; naming state is never tracker commitment.
        result["name_revision"] = {"track_id": track, "replacement_label": display,
            "replacement_known_name": published_name, "replacement_known_profile_id": published_id,
            "replacement_naming_state": naming_state, "reason": detail["reason"],
            "evidence_id": event["event_id"], "available_at_sec": event["available_at_sec"]}
        return detail

    def snapshot(self):
        return {"schema_version": "edge-identity-snapshot.v1", "mode": self.settings.mode,
            "gallery": self.gallery.receipt if self.gallery else None, "calls": self.calls,
            "query_calls": self.query_calls, "comparisons": self.comparisons, "policy_compute_sec": self.total_sec,
            "capacity_rejections": self.capacity_rejections, "track_states": [{"track_id": k,
                "unique_clean_sec": sum(b-a for a,b in v["intervals"]), "disjoint_count": v["disjoint_count"],
                "prototype_count": len(v["vectors"]), "known_name": v["name"], "known_profile_id": v["profile_id"],
                "naming_state": v["naming_state"]} for k,v in self.states.items()],
            "retired_name_states": self.retired_name_states, "recent_retirement_records": self.retirement_records,
            "name_memory_scope": "live anonymous tracks only; archived reentry requires fresh naming evidence",
            "bounds": {"track_states": self.settings.max_track_states, "intervals_per_track": self.settings.max_intervals,
                "prototypes_per_track": self.settings.max_prototypes}, "association_uses_names": False}
