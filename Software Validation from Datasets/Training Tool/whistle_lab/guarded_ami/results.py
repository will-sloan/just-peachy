"""Paired cluster uncertainty and publication without automatic promotion."""
from __future__ import annotations
import json
import shutil
import numpy as np
import pandas as pd
from runtime import *
from policy import guards, primary


def paired(reference_file, candidate_file):
    left, right = pd.read_json(reference_file, lines=True), pd.read_json(candidate_file, lines=True)
    merged = left.merge(right, on="item_id", suffixes=("_ref", "_candidate"), validate="one_to_one")
    if len(merged) != len(left) or len(merged) != len(right):
        raise ValueError("Paired confirmation has different item membership")
    for field in ("reference_words", "cohort", "cluster", "source_group_id", "panel_sha256"):
        if not merged[field+"_ref"].equals(merged[field+"_candidate"]):
            raise ValueError("Paired scoring identity differs: " + field)
    rng = np.random.default_rng(20261025)
    output, draws = {}, {}
    for cohort, p in merged.groupby("cohort_ref"):
        sources = p.groupby(["cluster_ref", "source_group_id_ref"])[
            ["word_errors_ref", "word_errors_candidate", "reference_words_ref"]].mean()
        clusters = sources.groupby(level=0).sum()
        n = len(clusters)
        delta = (clusters.word_errors_candidate.sum()-clusters.word_errors_ref.sum()) / clusters.reference_words_ref.sum()
        if n < 2:
            output[cohort] = {"groups": n, "delta": float(delta), "ci95": None, "reason": "Fewer than two independent sampling groups"}
            continue
        indices = rng.integers(0, n, (10000, n))
        data = clusters.to_numpy()
        sums = data[indices].sum(axis=1)
        values = (sums[:, 1]-sums[:, 0]) / sums[:, 2]
        draws[cohort] = values
        output[cohort] = {"groups": n, "delta": float(delta),
                          "ci95": [float(v) for v in np.percentile(values, [2.5, 97.5])]}
    primary_ci = [float(v) for v in np.percentile((draws["ami"]+draws["chime6"])/2, [2.5, 97.5])] if all(k in draws for k in ("ami", "chime6")) else None
    quiet = merged[merged.audio_level_ref.eq("quiet")]
    q = quiet.groupby(["cohort_ref", "cluster_ref", "source_group_id_ref"])[["word_errors_ref", "word_errors_candidate", "reference_words_ref"]].mean().groupby(level=[0, 1]).sum()
    quiet_ci = None
    if len(q) >= 2 and q.reference_words_ref.sum() >= 100:
        totals = q.to_numpy()[rng.integers(0, len(q), (10000, len(q)))].sum(axis=1)
        quiet_ci = [float(v) for v in np.percentile((totals[:, 1]-totals[:, 0])/totals[:, 2], [2.5, 97.5])]
    return {"by_cohort": output, "primary_delta_ci95": primary_ci,
            "quiet_delta_ci95": quiet_ci, "quiet_sampling_groups": len(q), "resamples": 10000, "seed": 20261025,
            "method": "Paired cluster bootstrap; source utterance mean across microphone variants before meeting/session/speaker resampling",
            "interpretation": "Exploratory intervals on previously used source populations; no independent-improvement claim"}


def finish(decision):
    step = decision["selected_step"]
    confirmation = {"performed": False, "reason": "No nonzero development checkpoint passed selection"}
    if step:
        a, b = read_json(scores_path(0, "confirmation")), read_json(scores_path(step, "confirmation"))
        if not a.get("complete") or not b.get("complete"):
            raise ValueError("Selected confirmation is incomplete")
        uncertainty = paired(scores_path(0, "confirmation").with_suffix(".jsonl"),
                             scores_path(step, "confirmation").with_suffix(".jsonl"))
        check = guards(a, b)
        gain = (primary(a)-primary(b))/primary(a) if primary(a) else 0.
        ci = uncertainty["primary_delta_ci95"]
        confirmation = {"performed": True, "initial": a, "candidate": b, "relative_primary_gain": gain,
                        "guards": check, "uncertainty": uncertainty,
                        "numerical_gates_passed": bool(check["passed"] and gain >= .02 and ci is not None and ci[1] < 0)}
    atomic_json(RUN / "confirmation_summary.json", confirmation)
    # The explicit exploratory amendment keeps the original default even if
    # numerical criteria pass. Candidate artifacts are separately named.
    for src, dst in ((BASE/"adapter.final.safetensors", RUN/"adapter.selected.safetensors"),
                     (BASE/"whistle.final.cact", RUN/"whistle.selected.cact")):
        shutil.copyfile(src, dst)
    candidate = {}
    if step:
        adapter, model = export_paths(step)
        for src, name in ((adapter, "adapter.experimental.safetensors"), (model, "whistle.experimental.cact")):
            shutil.copyfile(src, RUN/name)
            candidate[name] = sha256(RUN/name)
    result = {"complete": True, "promoted": False, "selected_experimental_step": step,
              "default_model": str(BASE/"whistle.final.cact"),
              "reason": "User authorized exploratory adaptation and retained the initial model as default",
              "independent_confirmation": False, "automatic_promotion": False,
              "development": decision, "confirmation": confirmation}
    atomic_json(RUN / "decision.json", result)
    manifest = {"run": RUN.name, "initialization": read_json(RUN/"initialization_verification.json"),
                "configuration": read_json(RUN/"config.json"), "completed_training": read_json(RUN/"checkpoint.json"),
                "default_model_sha256": sha256(RUN/"whistle.selected.cact"), "experimental_models": candidate,
                "training_includes_development": False, "base_license": "Apache-2.0",
                "inherited_license_provenance": read_json(BASE/"release_review.json"),
                "additional_clean_replay_license": "LibriSpeech CC-BY-4.0; preserve attribution",
                "product_microphone_validation": False, "independent_final_age_test": False}
    atomic_json(RUN/"model_manifest.json", manifest)
    atomic_json(RUN/"summary.json", {**result, "models": manifest, "coverage": read_json(RUN/"split_snapshot.json")["coverage"],
                                    "validation": read_json(RUN/"validation_summary.json")})
    status("complete", step=read_json(RUN/"checkpoint.json")["step"], message="Exploratory adaptation complete; initial model remains default",
           training_launched=True, promoted=False)
