"""Predeclared development-only comparisons with paired cluster bootstrap."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from shared import HOME, DATASETS, policy, read_json, run_dir


def result(name):
    data=read_json(run_dir(name)/"scores.json")
    if not data.get("complete") or data.get("role")!="development":
        raise ValueError(f"No complete development score for {name}")
    return data["models"][data["selected"]]


def paired(reference,candidate):
    a,b=result(reference),result(candidate)
    x=pd.read_json(run_dir(reference)/a["predictions"],lines=True)
    y=pd.read_json(run_dir(candidate)/b["predictions"],lines=True)
    if set(x.item_id)!=set(y.item_id): raise ValueError("Different evaluation examples")
    merged=x.merge(y[["item_id","word_errors","reference_words"]],on="item_id",suffixes=("_a","_b"),validate="one_to_one")
    if not merged.reference_words_a.eq(merged.reference_words_b).all(): raise ValueError("Reference mismatch")
    rng=np.random.default_rng(policy()["seed"])
    repetitions=policy()["bootstrap_repetitions"]
    draws=np.zeros(repetitions)
    dataset_count=0
    for ds,part in merged.groupby("dataset"):
        # Views share a source; speakers/sessions/meetings form the resampling unit.
        source=part.groupby(["cluster","source_group_id"])[["word_errors_a","word_errors_b","reference_words_a"]].mean().reset_index()
        groups=source.groupby("cluster")[["word_errors_a","word_errors_b","reference_words_a"]].sum().to_numpy()
        indexes=rng.integers(0,len(groups),size=(repetitions,len(groups)))
        totals=groups[indexes].sum(axis=1)
        denominators=np.maximum(totals[:,2],1.)
        draws+=(totals[:,1]-totals[:,0])/denominators
        dataset_count+=1
    draws/=dataset_count
    p=policy()
    delta=b["macro_wer"]-a["macro_wer"]
    guard={d:b["datasets"][d]["wer"]-a["datasets"][d]["wer"] for d in DATASETS}
    ci=np.quantile(draws,[.025,.975]).tolist()
    relative=-delta/max(a["macro_wer"],1e-9)
    na,nb=a["negative_probes"],b["negative_probes"]
    noise_ok=nb["false_positive_rate"]<=na["false_positive_rate"] and nb["inserted_words"]<=na["inserted_words"]
    qa,qb=a.get("quiet_audio",{}),b.get("quiet_audio",{})
    quiet_ok=qa.get("wer") is None or qb.get("wer") is None or min(qa.get("reference_words",0),qb.get("reference_words",0))<100 or qb["wer"]<=qa["wer"]+.03
    return {"reference":reference,"candidate":candidate,"macro_wer_delta":delta,"relative_gain":relative,"paired_cluster_95pct_interval":ci,"dataset_deltas":guard,"silence_noise_guard_passed":noise_ok,"quiet_audio_guard_passed":quiet_ok,"promote":bool(relative>=p["promotion_minimum_relative_wer_gain"] and ci[1]<0 and max(guard.values())<=p["maximum_dataset_absolute_wer_regression"] and noise_ok and quiet_ok),"interpretation":"development evidence only; intervals do not correct for the entire model search; quiet guard only applied with at least 100 reference words"}


def choose(reference,candidates):
    comparisons=[paired(reference,name) for name in candidates]
    allowed=[c["candidate"] for c in comparisons if c["promote"]]
    best=min(allowed,key=lambda n:result(n)["macro_wer"]) if allowed else reference
    return {"selected":best,"reference":reference,"comparisons":comparisons}
