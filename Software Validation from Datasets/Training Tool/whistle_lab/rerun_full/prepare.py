"""Metadata-only preparation: every qualified training view, unchanged weights."""
from __future__ import annotations
import json
import shutil
import subprocess
import numpy as np
import pandas as pd
from runtime import *


def reweight(frame, weights):
    frame = frame.copy()
    if set(frame.dataset_id.unique()) != set(weights) or any(v <= 0 for v in weights.values()):
        raise ValueError("Exactly the original four positive dataset weights are required")
    for ds, part in frame.groupby("dataset_id"):
        quality = part.view_confidence.astype(float)
        if not np.isfinite(quality).all() or (quality <= 0).any():
            raise ValueError("Quarantined/invalid views cannot enter training")
        totals = quality.groupby(part.source_group_id).transform("sum")
        frame.loc[part.index, "sample_weight"] = weights[ds]/sum(weights.values()) * len(frame)/part.source_group_id.nunique() * quality/totals
    return frame


def training_clusters(frame):
    clusters = set()
    for ds, p in frame.groupby("dataset_id"):
        field = "meeting_id" if ds == "ami" else "session_id" if ds == "chime6" else "speaker_id"
        for value in p[field].drop_duplicates():
            if pd.isna(value) or not str(value):
                raise ValueError("Missing training group")
            if ds == "voices":
                # Published speaker identifiers are zero-padded LibriVox IDs.
                value = "librivox:" + str(int(str(value).split(":")[-1]))
            else:
                value = ds + ":" + str(value)
            clusters.add(value)
    return clusters


def main():
    if (RUN / "execution_snapshot.json").exists():
        verify()
        print("Existing frozen preparation verified; no changes.")
        return
    if (RUN / "checkpoint.json").exists():
        raise RuntimeError("Cannot prepare over a started trajectory")
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "scores").mkdir(exist_ok=True)
    (RUN / "exports").mkdir(exist_ok=True)
    status("preparing", message="Reusing the completed audio audit; checking metadata identities")
    original_config = read_json(BASE / "config.json") or read_json(LAB / "config.json")
    previous = read_json(PREVIOUS / "split_snapshot.json")
    quality = read_json(FOLLOWUP / "audio_quality.json")
    if not quality.get("complete"):
        raise ValueError("Completed published audio-quality audit required")
    qualified = FOLLOWUP / "quality/train.parquet"
    if sha256(qualified) != previous["quality_sha256"]["train"]:
        raise ValueError("Published qualified training pool changed")
    frame = pd.read_parquet(qualified)
    if len(frame) != 2052751 or not frame.source_registry_row_id.is_unique or not frame.source_split.eq("train").all():
        raise ValueError("Full qualified training pool membership differs")
    weights = original_config["dataset_weights"]
    frame = reweight(frame, weights)
    train_clusters = training_clusters(frame)
    train_sources = set(frame.source_group_id)
    panels = {}
    for role in ("dev", "confirmation"):
        src = PREVIOUS / (role + ".parquet")
        if sha256(src) != previous["sha256"][role]:
            raise ValueError("Previously frozen evaluation panel changed")
        p = pd.read_parquet(src)
        if train_clusters & set(p.cluster) or train_sources & set(p.source_group_id):
            raise ValueError("Training/evaluation overlap in " + role)
        panels[role] = p
        shutil.copyfile(src, RUN / src.name)
    if set(panels["dev"].cluster) & set(panels["confirmation"].cluster):
        raise ValueError("Development and confirmation groups overlap")
    frame.to_parquet(RUN / "train.parquet", index=False)
    digests = {role: sha256(RUN / (role + ".parquet")) for role in ("train", "dev", "confirmation")}
    config = {**original_config, "run_name": RUN.name, "method": "full", "seed": 20261026,
              "epochs": 3, "learning_rate": 1e-5, "end_learning_rate": 5e-7, "warmup_steps": 1000,
              "max_batch_size": 8, "batch_audio_seconds": 60, "batch_tokens": 1024,
              "checkpoint_seconds": 300, "loader_workers": 12,
              "training_includes_development": False, "automatic_promotion": False,
              "initialization": "fresh_pinned_pretrained_base", "dataset_weights": weights,
              "loss_normalization": "full_pool_per_clip", "quantization_mode": "upstream_full"}
    from data import plan_batches
    plans = [plan_batches(frame, epoch, config) for epoch in range(3)]
    lengths = [len(p) for p in plans]
    if len(set(lengths)) != 1:
        raise ValueError("Epoch plan lengths differ")
    for plan in plans:
        indices = np.concatenate([item[0] for item in plan])
        if len(indices) != len(frame) or not np.array_equal(np.sort(indices), np.arange(len(frame))):
            raise ValueError("A pass does not visit every qualified row exactly once")
    config.update(batches_per_epoch=lengths[0], total_steps=sum(lengths),
                  validation_steps=validation_steps(lengths[0]))
    coverage = {ds: {"views_per_pass": len(p), "distinct_sources": p.source_group_id.nunique(),
                     "objective_weight": float(p.sample_weight.sum()/frame.sample_weight.sum()),
                     "quiet_views": int(p.audio_level.eq("quiet").sum())}
                for ds, p in frame.groupby("dataset_id")}
    for ds, row in coverage.items():
        if abs(row["objective_weight"]-weights[ds]/sum(weights.values())) > 1e-10:
            raise ValueError("Original dataset objective weight not preserved")
    atomic_json(RUN / "split_snapshot.json", {
        "complete": True, "sha256": digests, "coverage": previous["coverage"],
        "training": coverage, "training_rows": len(frame),
        "training_sources": frame.source_group_id.nunique(), "training_clusters": len(train_clusters),
        "total_planned_visits": len(frame)*3, "all_views_each_pass_verified": True,
        "batches_per_epoch": lengths[0], "validation_steps": config["validation_steps"],
        "training_evaluation_groups_disjoint": True, "development_confirmation_groups_disjoint": True,
        "quality_generation": previous["quality_generation"],
        "quality_train_sha256": previous["quality_sha256"]["train"],
        "independent_confirmation": False, "coverage_shortfalls": previous["coverage_shortfalls"],
        "limitation": "Reused exploratory panels from previously evaluated populations; no fresh independent confirmation."})
    for name in ("assets.json", "release_review.json"):
        shutil.copyfile(BASE / name, RUN / name)
    atomic_json(RUN / "data_audit.json", {"splits": {s: {"sha256": digests[s]} for s in ("train", "dev")},
                "source": "published qualified train plus unchanged exploratory dev", "no_new_audio_audit": True})
    atomic_json(RUN / "audio_header_audit.json", {"invalid_segments": 0, "manifest_sha256": {s: digests[s] for s in ("train", "dev")},
                "inherited_evidence": {"quality": str(FOLLOWUP / "audio_quality.json"),
                                      "panel": str(PREVIOUS / "audio_header_audit.json")},
                "no_audio_rescanned": True})
    baseline = read_json(PREVIOUS / "scores/dev_00000.json")
    reference_sha = sha256(BASE / "whistle.final.cact")
    if not baseline.get("complete") or baseline["model_sha256"] != reference_sha or baseline["panel_sha256"] != digests["dev"]:
        raise ValueError("Cached initial-model baseline identity differs")
    for suffix in (".json", ".jsonl", ".negative.jsonl"):
        src = PREVIOUS / ("scores/dev_00000" + suffix)
        shutil.copyfile(src, scores_path(0).with_suffix(suffix))
    baseline.update(predictions=scores_path(0).with_suffix(".jsonl").name,
                    reused_from=str(PREVIOUS / "scores/dev_00000.json"))
    atomic_json(scores_path(0), baseline)
    atomic_json(RUN / "baseline_reuse.json", {"complete": True, "model": str(BASE / "whistle.final.cact"),
                "model_sha256": reference_sha, "panel_sha256": digests["dev"],
                "source": str(PREVIOUS / "scores/dev_00000.json"),
                "source_sha256": sha256(PREVIOUS / "scores/dev_00000.json"),
                "scoring_id_zero_is_initial_reference": True, "fresh_base_zero_export_has_distinct_name": True})
    atomic_json(RUN / "config.json", config)
    inputs = ("config.json", "split_snapshot.json", "train.parquet", "dev.parquet", "confirmation.parquet",
              "assets.json", "release_review.json", "data_audit.json", "audio_header_audit.json", "baseline_reuse.json",
              "scores/dev_0000000.json", "scores/dev_0000000.jsonl", "scores/dev_0000000.negative.jsonl")
    code = list(SOURCE.glob("*.py")) + [LAB/n for n in ("common.py", "data.py", "train.py", "evaluate.py")]
    code += [LAB/"guarded_ami"/n for n in ("audioio.py", "score.py", "policy.py", "results.py")]
    frozen = {"complete": True, "authorized_full_rerun": True, "frozen_at": time.time(),
              "request": "26 October 2026: rerun initial-model training, seek incremental transcription improvement; full fine-tuning and same dataset weights allowed.",
              "files": {n: sha256(RUN/n) for n in inputs},
              "source_sha256": {p.relative_to(LAB).as_posix(): sha256(p) for p in code},
              "base_sha256": {n: sha256(BASE/n) for n in ("assets/whistle.safetensors", "adapter.final.safetensors", "whistle.final.cact")},
              "needle_commit": subprocess.check_output(["git", "-C", str(REPO/"training/toolchains/needle-whistle"), "rev-parse", "HEAD"], text=True).strip(),
              "training": "One fresh-base full-parameter trajectory, three complete passes, six half-pass validations, no short-pilot early-stop, refit, sweep or automatic promotion.",
              "selection": "Screen native nine-cohort macro WER gain >=0.2 percentage points with all retention guards; one selected exploratory confirmation; preserve initial default."}
    atomic_json(RUN / "execution_snapshot.json", frozen)
    atomic_json(RUN / "control.json", {"paused": False})
    atomic_json(RUN / "monitor_state.json", {"prepared_at": time.time(), "preparation": {"all_rows": len(frame), "passes": 3},
                "cadence_minutes": 15, "cadence_reason": "startup/preflight", "last_analyzed_milestone": None})
    status("prepared", message="Frozen full-parameter rerun ready", total_steps=config["total_steps"],
           training_rows=len(frame), planned_passes=3, training_launched=False)
    print(json.dumps({"prepared": True, "views": len(frame), "total_steps": config["total_steps"],
                      "validation_steps": config["validation_steps"], "coverage": coverage}, indent=2))


if __name__ == "__main__":
    main()
