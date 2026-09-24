"""N2 evaluator-only metrics and hash-bound conservative calibration. See README.md."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import string

SCORING_VERSION = "n2-evaluation-v1"
PROVENANCE_FIELDS = ("encoder_sha256", "preprocessing_sha256", "window_manifest_sha256", "gallery_sha256",
                     "roster_sha256", "enrollment_domain", "input_domain", "reference_seconds", "vector_dimension")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _provenance(value):
    missing = [key for key in PROVENANCE_FIELDS if key not in value]
    if missing:
        raise ValueError(f"Missing calibration provenance: {missing}")
    for key in PROVENANCE_FIELDS:
        if key.endswith("sha256") and (not isinstance(value[key], str) or len(value[key]) != 64 or any(c not in "0123456789abcdef" for c in value[key])):
            raise ValueError(f"Invalid hash: {key}")
    return {key:value[key] for key in PROVENANCE_FIELDS}


def _row_score(row):
    score, margin = float(row["score"]), float(row["margin"])
    if not math.isfinite(score) or not math.isfinite(margin) or not -1.000001 <= score <= 1.000001 or not -2.000001 <= margin <= 2.000001:
        raise ValueError("Expected finite cosine score and top1-minus-top2 margin")
    return score, margin


def _wilson_upper(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    return (p + z*z/(2*total) + z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))) / (1+z*z/total)


def calibrate_c(rows, provenance, *, false_known_target=0.01, minimum_negatives=100,
                minimum_negative_identities=5, minimum_positives=20, minimum_margin=0.05):
    """Fit one scalar on unique C sources; no Q or cross-domain operational gate.

    Each row is one independent source evaluated against one exact frozen roster:
    role=C, source_id, identity, is_known, winner_correct, score, margin.
    Max-over-roster scores define false-known; pairwise comparisons are not trials.
    """
    provenance = _provenance(provenance)
    if not 0 <= false_known_target < 1 or minimum_negatives < 1 or minimum_negative_identities < 1 or minimum_positives < 1:
        raise ValueError("Invalid calibration criterion")
    seen = set()
    for row in rows:
        if row.get("role") != "C":
            raise ValueError("Calibration accepts C role only; Q is forbidden")
        if row["source_id"] in seen:
            raise ValueError("Repeated C source cannot inflate trial denominator")
        seen.add(row["source_id"])
        _row_score(row)
    neg = [r for r in rows if not r["is_known"]]
    pos = [r for r in rows if r["is_known"]]
    negative_identities = len({r["identity"] for r in neg})
    reasons = []
    if len(neg) < minimum_negatives:
        reasons.append("INSUFFICIENT_UNIQUE_NEGATIVE_SOURCES")
    if negative_identities < minimum_negative_identities:
        reasons.append("INSUFFICIENT_DISTINCT_NEGATIVE_IDENTITIES")
    if len(pos) < minimum_positives:
        reasons.append("INSUFFICIENT_UNIQUE_POSITIVE_SOURCES")
    if provenance["input_domain"] != "clean_source" or provenance["enrollment_domain"] != "clean_source":
        reasons.append("PROCESSED_C_NOT_ADMITTED_OR_DOMAIN_TRANSFER")
    threshold = None
    if not reasons:
        candidates = sorted({-1.0, 1.000002} | {float(r["score"]) for r in rows} | {math.nextafter(float(r["score"]), math.inf) for r in neg})
        for candidate in candidates:
            nfalse = sum(r["score"] >= candidate and r["margin"] >= minimum_margin for r in neg)
            if nfalse / len(neg) <= false_known_target:
                threshold = candidate
                break
    accepted = lambda r: threshold is not None and r["score"] >= threshold and r["margin"] >= minimum_margin
    false_known = sum(accepted(r) for r in neg)
    correct_known = sum(accepted(r) and r["winner_correct"] for r in pos)
    wrong_known = sum(accepted(r) and not r["winner_correct"] for r in pos)
    curves = [{"threshold": t, "negative_source_count": len(neg),
               "false_known_count": sum(r["score"] >= t and r["margin"] >= minimum_margin for r in neg),
               "positive_source_count": len(pos),
               "correct_known_count": sum(r["score"] >= t and r["margin"] >= minimum_margin and r["winner_correct"] for r in pos)}
              for t in [-1.0,0.0,0.2,0.4,0.6,0.8,1.000002]]
    result = {"schema": "n2-C-calibration-v1", "scoring_version": SCORING_VERSION,
              "status": "UNCALIBRATED_REJECT_ALL" if reasons else "C_EMPIRICAL_CALIBRATION_ONLY",
              "reasons": reasons, "provenance": provenance, "C_rows_sha256": fingerprint(rows),
              "threshold": threshold, "minimum_margin": minimum_margin, "false_known_target": false_known_target,
              "negative_unique_sources": len(neg), "negative_identities": negative_identities,
              "positive_unique_sources": len(pos), "false_known_count": false_known,
              "correct_known_count": correct_known, "wrong_known_count": wrong_known,
              "empirical_false_known_rate": false_known / len(neg) if neg and threshold is not None else None,
              "wilson95_upper_source_independence_assumption": _wilson_upper(false_known, len(neg)) if threshold is not None else None,
              "uncertainty": "Same-person sources cluster; Wilson bound is descriptive, not a deployment guarantee. Scores and margins are not probabilities.",
              "curves_uncalibrated_when_gate_rejects": curves}
    result["gate_sha256"] = fingerprint(result)
    return result


def apply_gate(gate, provenance, score, margin):
    expected = gate.get("gate_sha256")
    if expected != fingerprint({k:v for k,v in gate.items() if k != "gate_sha256"}):
        raise ValueError("Calibration gate integrity failure")
    if _provenance(provenance) != gate["provenance"]:
        return {"accepted": False, "reason": "INCOMPATIBLE_GATE_PROVENANCE", "identity_confidence_probability": None}
    _row_score({"score": score, "margin": margin})
    if gate["status"] != "C_EMPIRICAL_CALIBRATION_ONLY":
        return {"accepted": False, "reason": "UNCALIBRATED_REJECT_ALL", "identity_confidence_probability": None}
    accept = score >= gate["threshold"] and margin >= gate["minimum_margin"]
    return {"accepted": accept, "reason": "C_SCORE_AND_MARGIN_PASSED" if accept else "UNKNOWN_SCORE_OR_MARGIN_REJECT",
            "identity_confidence_probability": None, "gate_sha256": expected}


def _assignment(cost):
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    if not cost or not cost[0]:
        return []
    rows, cols = linear_sum_assignment(np.asarray(cost, dtype=float))
    return list(zip(rows.tolist(), cols.tolist()))


def activity_metrics(reference, hypothesis, duration_s, *, complete_reference=True, grid_s=0.02, collar_s=0.25):
    """Segments use start,end,label seconds. Approximate activity only, overlap included."""
    if not complete_reference:
        return {"status": "UNAVAILABLE_INCOMPLETE_ALL_SPEAKER_REFERENCE", "approximate_activity_DER": None, "approximate_activity_JER": None}
    if duration_s <= 0 or grid_s <= 0 or collar_s < 0:
        raise ValueError("Invalid activity timing configuration")
    for seg in reference + hypothesis:
        if not 0 <= seg["start"] < seg["end"] <= duration_s:
            raise ValueError("Out-of-file/invalid segment; no silent timestamp clamping")
    labels_r = sorted({s["label"] for s in reference})
    labels_h = sorted({s["label"] for s in hypothesis})
    boundaries = [s[k] for s in reference for k in ["start", "end"]]
    frames = []
    excluded = 0
    for index in range(math.ceil(duration_s / grid_s)):
        a, b = index * grid_s, min((index+1)*grid_s, duration_s)
        midpoint = (a+b)/2
        if any(abs(midpoint-edge) < collar_s for edge in boundaries):
            excluded += b-a
            continue
        r = {s["label"] for s in reference if s["start"] <= midpoint < s["end"]}
        h = {s["label"] for s in hypothesis if s["start"] <= midpoint < s["end"]}
        frames.append((r,h,b-a))
    intersection = [[sum(dt for r,h,dt in frames if rr in r and hh in h) for hh in labels_h] for rr in labels_r]
    mapping = {labels_h[j]:labels_r[i] for i,j in _assignment([[-v for v in row] for row in intersection])}
    missed = false = confusion = ref_time = 0.0
    for r,h,dt in frames:
        correct = sum(mapping.get(hh) in r for hh in h)
        missed += max(0,len(r)-len(h))*dt
        false += max(0,len(h)-len(r))*dt
        confusion += (min(len(r),len(h))-correct)*dt
        ref_time += len(r)*dt
    rdur = [sum(dt for r,h,dt in frames if rr in r) for rr in labels_r]
    hdur = [sum(dt for r,h,dt in frames if hh in h) for hh in labels_h]
    jcost = [[1-intersection[i][j]/(rdur[i]+hdur[j]-intersection[i][j]) if rdur[i]+hdur[j]-intersection[i][j] else 1.0 for j in range(len(labels_h))] for i in range(len(labels_r))]
    jmatched = {i:jcost[i][j] for i,j in _assignment(jcost)}
    qualified_r = [i for i,d in enumerate(rdur) if d > 0]
    return {"status": "APPROXIMATE_ACTIVITY_ONLY", "grid_seconds": grid_s, "collar_seconds": collar_s,
            "overlap_policy": "include", "reference_speaker_seconds": ref_time,
            "evaluated_wall_seconds": sum(dt for _,_,dt in frames), "collar_excluded_seconds": excluded,
            "miss_seconds": missed, "false_alarm_seconds": false, "confusion_seconds": confusion,
            "approximate_activity_DER": (missed+false+confusion)/ref_time if ref_time else None,
            "approximate_activity_JER": sum(jmatched.get(i,1.0) for i in qualified_r)/len(qualified_r) if qualified_r else None,
            "JER_scope": "optimal reference-speaker mean intersection/union error; extra hyp speakers penalized by DER, not separate JER terms",
            "DER_mapping": mapping, "reference_speaker_count": len(labels_r), "hypothesis_speaker_count": len(labels_h),
            "speaker_count_error": len(labels_h)-len(labels_r), "exact_phonetic_DER": None}


def words(text):
    return text.lower().translate(str.maketrans("", "", string.punctuation)).split()


def edit_distance(left, right):
    previous = list(range(len(right)+1))
    for i,a in enumerate(left, 1):
        current = [i]
        for j,b in enumerate(right, 1):
            current.append(min(previous[j]+1,current[-1]+1,previous[j-1]+(a != b)))
        previous = current
    return previous[-1]


def cpwer(reference_streams, hypothesis_streams, *, complete_reference=True):
    """Streams contain word lists in declared within-speaker temporal order."""
    if not complete_reference:
        return {"status": "UNAVAILABLE_INCOMPLETE_REFERENCE", "cpWER": None}
    ref, hyp = list(reference_streams.values()), list(hypothesis_streams.values())
    n = max(len(ref),len(hyp))
    ref += [[] for _ in range(n-len(ref))]
    hyp += [[] for _ in range(n-len(hyp))]
    cost = [[edit_distance(a,b) for b in hyp] for a in ref]
    assignment = _assignment(cost)
    errors = sum(cost[i][j] for i,j in assignment)
    denominator = sum(map(len,ref))
    return {"status": "LEXICAL_PERMUTATION_ONLY" if denominator else "EMPTY_CONTROL_NO_WER_DENOMINATOR",
            "reference_words": denominator, "errors": errors, "cpWER": errors/denominator if denominator else None,
            "empty_control_inserted_words": sum(map(len,hyp)) if not denominator else None,
            "assignment_indices": assignment, "tcpWER": None, "tcpWER_reason": "EXACT_REFERENCE_WORD_TIMES_UNAVAILABLE"}


def asr_invariance(baseline_words, candidate_words):
    return {"raw_word_order_unchanged": baseline_words == candidate_words,
            "baseline_word_count": len(baseline_words), "candidate_word_count": len(candidate_words),
            "baseline_words_sha256": fingerprint(baseline_words), "candidate_words_sha256": fingerprint(candidate_words)}


def _union_seconds(intervals):
    end = None
    total = 0.0
    for a,b in sorted(intervals):
        if b <= a:
            raise ValueError("Invalid evidence interval")
        total += b-max(a,end) if end is not None and b > end else (b-a if end is None else 0)
        end = max(end,b) if end is not None else b
    return total


def turn_coverage(turns, track_segments, evidence_windows, *, sample_rate=16000, short_limit=1.5, return_gap=2.0):
    """Truth-dependent mapping is evaluator-only. No observed turn is silently dropped.

    Turns use private prepared schema. Track/evidence records use start,end,label in
    seconds. Every window counts once as a call; unique evidence is interval union.
    """
    mapped = []
    for turn in turns:
        spans = [(a/sample_rate,b/sample_rate) for a,b in turn["activity_ranges_samples_estimated"]]
        intersections = defaultdict(float)
        for segment in track_segments:
            overlap = sum(max(0,min(b,segment["end"])-max(a,segment["start"])) for a,b in spans)
            intersections[segment["label"]] += overlap
        best = max(intersections.values(), default=0)
        winners = [key for key,value in intersections.items() if value == best and value > 0]
        track = winners[0] if len(winners) == 1 else None
        covered = any(any(min(b,w["end"]) > max(a,w["start"]) for a,b in spans) for w in evidence_windows)
        mapped.append({"turn_id": turn["turn_id"], "identity": turn["identity"], "track": track,
                       "active_seconds": sum(b-a for a,b in spans), "evidence_available": covered,
                       "start": min((a for a,b in spans),default=None), "end": max((b for a,b in spans),default=None)})
    returns = []
    previous = {}
    for turn in sorted(mapped,key=lambda t:float("inf") if t["start"] is None else t["start"]):
        prior = previous.get(turn["identity"])
        if prior and turn["start"] is not None and prior["end"] is not None and turn["start"]-prior["end"] >= return_gap:
            returns.append("unresolved" if turn["track"] is None or prior["track"] is None else "consistent" if turn["track"] == prior["track"] else "changed_track")
        previous[turn["identity"]] = turn
    by_identity, by_track = defaultdict(set), defaultdict(set)
    for turn in mapped:
        if turn["track"] is not None:
            by_identity[turn["identity"]].add(turn["track"])
            by_track[turn["track"]].add(turn["identity"])
    contamination = []
    for window in evidence_windows:
        identities = set()
        for turn in turns:
            if any(min(b/sample_rate,window["end"]) > max(a/sample_rate,window["start"]) for a,b in turn["activity_ranges_samples_estimated"]):
                identities.add(turn["identity"])
        contamination.append(len(identities)>1)
    short = [t for t in mapped if t["active_seconds"] <= short_limit]
    return {"source_turn_denominator": len(turns), "resolved_turns": sum(t["track"] is not None for t in mapped),
            "unresolved_turns": sum(t["track"] is None for t in mapped), "short_turn_denominator": len(short),
            "short_turns_resolved": sum(t["track"] is not None for t in short),
            "short_turns_unresolved": sum(t["track"] is None for t in short),
            "short_turns_without_evidence": sum(not t["evidence_available"] for t in short),
            "turns_without_evidence": sum(not t["evidence_available"] for t in mapped),
            "return_denominator": len(returns), "return_consistent": returns.count("consistent"),
            "return_changed_track": returns.count("changed_track"), "return_unresolved": returns.count("unresolved"),
            "identities_split_across_tracks": sum(len(v)>1 for v in by_identity.values()),
            "tracks_merging_identities": sum(len(v)>1 for v in by_track.values()),
            "embedding_calls": len(evidence_windows), "unique_evidence_wall_seconds": _union_seconds([(w["start"],w["end"]) for w in evidence_windows]),
            "windows_with_multiple_reference_identities": sum(contamination), "mapped_turns_evaluator_only": mapped}
