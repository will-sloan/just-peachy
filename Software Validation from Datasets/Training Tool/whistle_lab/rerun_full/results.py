"""Source-balanced paired uncertainty, explicit limitations and preserved default."""
from __future__ import annotations
import shutil
import numpy as np
import pandas as pd
from runtime import *
from policy import guards, primary


def paired(reference_file, candidate_file):
    a, b = pd.read_json(reference_file, lines=True), pd.read_json(candidate_file, lines=True)
    p = a.merge(b, on="item_id", suffixes=("_ref", "_candidate"), validate="one_to_one")
    if len(p) != len(a) or len(p) != len(b):
        raise ValueError("Different paired item membership")
    for field in ("reference_words", "cohort", "cluster", "source_group_id", "panel_sha256", "audio_level"):
        if not p[field+"_ref"].equals(p[field+"_candidate"]):
            raise ValueError("Paired identity differs: " + field)
    rng = np.random.default_rng(20261026)
    output, draws = {}, {}
    columns = ["word_errors_ref", "word_errors_candidate", "reference_words_ref"]
    for cohort, part in p.groupby("cohort_ref"):
        clusters = part.groupby(["cluster_ref", "source_group_id_ref"])[columns].mean().groupby(level=0).sum()
        n = len(clusters)
        delta = (clusters.word_errors_candidate.sum()-clusters.word_errors_ref.sum())/clusters.reference_words_ref.sum()
        ci = None
        if n >= 2:
            totals = clusters.to_numpy()[rng.integers(0, n, (10000, n))].sum(axis=1)
            values = (totals[:, 1]-totals[:, 0])/totals[:, 2]
            draws[cohort] = values
            ci = [float(v) for v in np.percentile(values, [2.5, 97.5])]
        output[cohort] = {"groups": n, "delta": float(delta), "ci95": ci,
                          "limited_group_coverage": n < 5,
                          "limitation": "Undefined with one group; sparse groups give fragile intervals" if n < 5 else None}
    macro = [float(v) for v in np.percentile(np.mean([draws[c] for c in COHORTS], axis=0), [2.5, 97.5])] if all(c in draws for c in COHORTS) else None
    quiet = p[p.audio_level_ref.eq("quiet")]
    q = quiet.groupby(["cohort_ref", "cluster_ref", "source_group_id_ref"])[columns].mean().groupby(level=[0, 1]).sum()
    quiet_ci = None
    if len(q) >= 2 and q.reference_words_ref.sum() >= 100:
        totals = q.to_numpy()[rng.integers(0, len(q), (10000, len(q)))].sum(axis=1)
        quiet_ci = [float(v) for v in np.percentile((totals[:, 1]-totals[:, 0])/totals[:, 2], [2.5, 97.5])]
    return {"by_cohort": output, "macro_delta_ci95": macro, "quiet_delta_ci95": quiet_ci,
            "resamples": 10000, "seed": 20261026,
            "method": "Paired meeting/session/speaker bootstrap within cohort, after averaging microphone views per source",
            "limitation": "Exploratory reused populations; development intervals are not adjusted for selecting among six checkpoints. A nine-cohort interval is undefined if any cohort has fewer than two groups."}


def annotate(step):
    target = RUN/"scores"/f"dev_{step:07d}.uncertainty.json"
    a, b = scores_path(0).with_suffix(".jsonl"), scores_path(step).with_suffix(".jsonl")
    if target.exists():
        record = read_json(target)
        if record["reference_predictions_sha256"] != sha256(a) or record["candidate_predictions_sha256"] != sha256(b):
            raise ValueError("Paired prediction identity changed")
        return record
    result = {"complete": True, "step": step, "reference_predictions_sha256": sha256(a),
              "candidate_predictions_sha256": sha256(b), **paired(a, b)}
    atomic_json(target, result)
    return result


def finish(decision):
    step = decision["selected_step"]
    confirmation = {"performed": False, "reason": "No checkpoint met development macro gain and all retention guards"}
    if step:
        a, b = read_json(scores_path(0, "confirmation")), read_json(scores_path(step, "confirmation"))
        if not a.get("complete") or not b.get("complete"):
            raise ValueError("Selected confirmation is incomplete")
        uncertainty = paired(scores_path(0, "confirmation").with_suffix(".jsonl"),
                             scores_path(step, "confirmation").with_suffix(".jsonl"))
        check = guards(a, b)
        gain = primary(a)-primary(b)
        ci = uncertainty["macro_delta_ci95"]
        confirmation = {"performed": True, "initial": a, "candidate": b,
                        "absolute_macro_gain": gain, "guards": check, "uncertainty": uncertainty,
                        "numerical_gates_passed": bool(check["passed"] and gain >= .002 and ci is not None and ci[1] < 0)}
    atomic_json(RUN/"confirmation_summary.json", confirmation)
    initial = BASE/"whistle.final.cact"
    shutil.copyfile(initial, RUN/"whistle.selected.cact")
    candidate = {}
    if step:
        weights, model = export_paths(step)
        for src, name in ((weights, "weights.experimental.msgpack"), (model, "whistle.experimental.cact")):
            shutil.copyfile(src, RUN/name)
            candidate[name] = {"path": str(RUN/name), "sha256": sha256(RUN/name)}
    result = {"complete": True, "promoted": False, "selected_experimental_step": step,
              "default_model": str(initial), "development": decision, "confirmation": confirmation,
              "independent_confirmation": False, "automatic_promotion": False,
              "reason": "The initial model remains default; this is one exploratory full-training rerun"}
    atomic_json(RUN/"decision.json", result)
    manifest = {"run": RUN.name, "method": "full", "initialization": read_json(RUN/"initialization_verification.json"),
                "configuration": read_json(RUN/"config.json"), "completed_training": read_json(RUN/"checkpoint.json"),
                "default_model": str(initial), "default_model_sha256": sha256(initial),
                "experimental_models": candidate, "training_includes_development": False,
                "base_and_runtime_license": "Apache-2.0", "inherited_license_provenance": read_json(BASE/"release_review.json"),
                "training_licenses": {"common_voice": "CC0-1.0", "ami": "CC-BY-4.0",
                                     "voices": "CC-BY-4.0", "chime6": "CC-BY-SA-4.0; resolved by user 23 October"},
                "product_microphone_validation": False, "independent_final_age_test": False,
                "independent_confirmation": False}
    atomic_json(RUN/"model_manifest.json", manifest)
    atomic_json(RUN/"summary.json", {**result, "models": manifest,
        "exposure": read_json(RUN/"split_snapshot.json"), "validation": read_json(RUN/"validation_summary.json")})
    status("complete", step=read_json(RUN/"checkpoint.json")["step"],
           message="Three-pass full-training rerun complete; initial model remains default", promoted=False)
