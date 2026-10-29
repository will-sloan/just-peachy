"""Six fixed evaluations; selection never shortens the three-pass trajectory."""
from __future__ import annotations
import math
from runtime import COHORTS, shared

# The previous experiment's missing-evidence, quiet and negative-probe checks
# are reused, but its short-run early-stop/selection policy is not.
guards = shared("policy").guards


def primary(summary):
    values = [summary.get("cohorts", {}).get(c, {}).get("wer") for c in COHORTS]
    if any(v is None or not math.isfinite(v) for v in values):
        raise ValueError("All nine finite cohort WERs are required")
    return sum(values) / len(values)


def select(reference, candidates, allowed_steps):
    best_step, best_score = 0, primary(reference)
    observations = []
    if len(candidates) > 6 or len({s for s, _ in candidates}) != len(candidates):
        raise ValueError("Extra or duplicate validation slot")
    for step, summary in sorted(candidates):
        if step not in allowed_steps or not summary.get("complete"):
            raise ValueError("Unscheduled or incomplete checkpoint")
        if summary.get("panel_sha256") != reference.get("panel_sha256"):
            raise ValueError("Development panel identity differs")
        check = guards(reference, summary)
        value = primary(summary)
        improvement = primary(reference) - value
        # A 0.2 percentage-point macro improvement is a development screening
        # threshold, not proof. Paired uncertainty follows without more trials.
        eligible = check["passed"] and improvement >= .002 - 1e-12
        if eligible and value < best_score:
            best_step, best_score = step, value
        observations.append({"step": step, "macro_wer": value, "absolute_gain": improvement,
                             "eligible": eligible, **check})
    return {"selected_step": best_step, "selected_macro_wer": best_score,
            "reference_macro_wer": primary(reference), "observations": observations,
            "early_stop": False, "automatic_promotion": False,
            "default_model": "preserved_initial_final", "objective": "equal-weight nine-cohort macro WER"}
