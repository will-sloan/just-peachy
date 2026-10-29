"""Pure checkpoint selection rules; exploratory runs never replace the default."""
from __future__ import annotations
import math
from runtime import COHORTS

LIMITS = {name: .005 for name in COHORTS}
LIMITS.update({name: .0025 for name in ("cmu_arctic_clean", "hifitts_clean", "librispeech_clean")})


def primary(summary):
    return (summary["cohorts"]["ami"]["wer"] + summary["cohorts"]["chime6"]["wer"]) / 2


def guards(reference, candidate):
    reasons = []
    for cohort, cap in LIMITS.items():
        a = reference.get("cohorts", {}).get(cohort, {}).get("wer")
        b = candidate.get("cohorts", {}).get(cohort, {}).get("wer")
        if a is None or b is None or not math.isfinite(a + b):
            reasons.append(cohort + ": missing/nonfinite WER")
        elif b - a > cap + 1e-12:
            reasons.append(cohort + ": retention limit exceeded")
    a, b = reference.get("quiet_audio", {}), candidate.get("quiet_audio", {})
    if min(a.get("reference_words", 0), b.get("reference_words", 0)) < 100 or a.get("wer") is None or b.get("wer") is None:
        reasons.append("quiet_speech: fewer than 100 reference words or missing score")
    elif b["wer"] - a["wer"] > .01 + 1e-12:
        reasons.append("quiet_speech: retention limit exceeded")
    a, b = reference.get("negative_probes", {}), candidate.get("negative_probes", {})
    if a.get("clips") != 20 or b.get("clips") != 20:
        reasons.append("silence_noise: incomplete 20-probe panel")
    elif b["false_positive_rate"] > a["false_positive_rate"] or b["inserted_words"] > a["inserted_words"]:
        reasons.append("silence_noise: more false positives/insertions")
    return {"passed": not reasons, "reasons": reasons}


def select(reference, candidates):
    """candidates: chronological (step, distinct_sources, summary) triples."""
    best_step, best_score = 0, primary(reference)
    tracked_best, stale, violations = best_score, 0, 0
    observations = []
    reason = None
    for step, sources, summary in candidates:
        if len(observations) >= 5:
            raise ValueError("More than five candidate validations")
        check = guards(reference, summary)
        score = primary(summary)
        eligible = step >= 4000 and sources >= 1000
        if eligible and check["passed"] and score < best_score:
            best_step, best_score = step, score
        if tracked_best - score >= .002 - 1e-12:
            tracked_best, stale = score, 0
        else:
            stale += 1
        violations = 0 if check["passed"] else violations + 1
        observations.append({"step": step, "distinct_sources": sources, "primary_wer": score,
                             "eligible_exposure": eligible, **check})
        if violations >= 2:
            reason = "two consecutive retention-guard violations"
        elif stale >= 3:
            reason = "three validations without 0.2 percentage-point primary improvement"
        if reason:
            break
    return {"selected_step": best_step, "selected_primary_wer": best_score,
            "reference_primary_wer": primary(reference), "observations": observations,
            "early_stop": bool(reason), "stop_reason": reason,
            "automatic_promotion": False, "default_model": "preserved_initial_final"}
