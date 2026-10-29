"""Metadata/header-only expansion, leakage checks and reproducible pilot manifests."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import soundfile as sf
from shared import BASE, DATASETS, HOME, REPO, LAB, atomic_json, read_json, sha256, policy, run_dir, qualified, freeze_policy
from common import audio_path
from data import capacities, plan_batches


def reweight(frame, weights):
    frame = frame.copy()
    active = {d: float(weights[d]) for d in frame.dataset_id.unique()}
    total = sum(active.values())
    if total <= 0 or any(v <= 0 for v in active.values()):
        raise ValueError("Every included dataset needs positive weight")
    for ds, part in frame.groupby("dataset_id"):
        quality = part.get("view_confidence", pd.Series(1., index=part.index)).astype(float)
        if (quality <= 0).any():
            raise ValueError("Quarantined views must be removed before weighting")
        totals = quality.groupby(part.source_group_id).transform("sum")
        frame.loc[part.index, "sample_weight"] = active[ds] / total * len(frame) / part.source_group_id.nunique() * quality / totals
    return frame


def mic_kind(row):
    path = row["audio_relative_path"]
    if row["dataset_id"] == "ami":
        return "headset" if ".Headset-" in path else "array"
    if row["dataset_id"] == "chime6":
        return "array" if re.search(r"_U\d+\.CH", path) else "worn"
    if row["dataset_id"] == "voices":
        return "clean" if "source-16k" in path else "close" if "-mc01-" in path else "far"
    return "age"


def expanded(split, files, header_cache):
    frame = pd.read_parquet(BASE / f"{split}.parquet")
    frame["channel_index"] = 0
    # Attach source split and speaker/session metadata without reading any PCM.
    names = {"common_voice": "age", "ami": "ami", "chime6": "chime", "voices": "voices"}
    metadata = []
    for ds, name in names.items():
        src = REPO / "training/successors/phase5a_original_adapter_training_v1/framework_manifests" / split / f"{name}_{split}.parquet"
        metadata.append(pd.read_parquet(src, columns=["source_registry_row_id", "speaker_id", "meeting_id", "session_id"]))
    frame = frame.merge(pd.concat(metadata), on="source_registry_row_id", how="left", validate="one_to_one")
    frame["source_split"] = split
    additions, exclusions = [], []
    chime = frame[frame.dataset_id.eq("chime6")]
    # The source manifests use the synchronized CHiME-6 transcription times.
    for session, part in chime.groupby("session_id"):
        session_files = [p for p in files["chime6"] if p.name.startswith(str(session) + "_U")]
        for path in session_files:
            extra = part.copy()
            extra["audio_relative_path"] = path.relative_to(REPO / "Software Validation from Datasets").as_posix()
            extra["source_registry_row_id"] = part.source_registry_row_id + ":" + path.stem
            additions.append(extra)
    second = chime.copy()
    second["channel_index"] = 1
    second["source_registry_row_id"] += ":channel1"
    additions.append(second)
    # All locally available AMI speech microphones are already Array1 + own headset.
    observed_ami = {p.name.split(".", 1)[1].rsplit(".", 1)[0] for p in files["ami"]}
    if any(not (m.startswith("Array1-") or m.startswith("Headset-")) for m in observed_ami):
        raise ValueError("New AMI microphone family needs its participant mapping audited")
    voices = frame[frame.dataset_id.eq("voices")].drop_duplicates("source_group_id")
    clean_index = {}
    for path in files["voices"]:
        match = re.search(r"-src-sp(\d+)-ch(\d+)-sg(\d+)\.wav$", path.name)
        if match:
            clean_index[f"voices:source:{int(match[1]):04d}:{int(match[2])}:{int(match[3])}"] = path
    for row in voices.to_dict("records"):
        path = clean_index.get(row["source_group_id"])
        if path is None:
            raise ValueError(f"Missing clean VOiCES source for {row['source_group_id']}")
        info = sf.info(str(path))
        row.update(audio_relative_path=path.relative_to(REPO / "Software Validation from Datasets").as_posix(), start_sec=0., end_sec=info.duration, duration_seconds=info.duration, channel_index=0, source_registry_row_id=row["source_group_id"] + ":clean")
        row["audio_capacity"], row["token_capacity"] = capacities(info.duration, len(row["tokens"]))
        additions.append(pd.DataFrame([row]))
    result = pd.concat([frame, *additions], ignore_index=True)
    # Check actual lengths for every new file/channel. Existing files were audited.
    paths=result[["audio_root_id","audio_relative_path"]].drop_duplicates().to_dict("records")
    missing=[r for r in paths if r["audio_root_id"]+":"+r["audio_relative_path"] not in header_cache]
    def inspect(row):
        info=sf.info(str(audio_path(row["audio_root_id"],row["audio_relative_path"])))
        return row["audio_root_id"]+":"+row["audio_relative_path"],{"duration":info.duration,"channels":info.channels,"sample_rate":info.samplerate}
    with ThreadPoolExecutor(max_workers=4) as pool:
        header_cache.update(pool.map(inspect,missing))
    keys=result.audio_root_id+":"+result.audio_relative_path
    durations=keys.map({k:v["duration"] for k,v in header_cache.items()})
    channels=keys.map({k:v["channels"] for k,v in header_cache.items()})
    valid=(result.start_sec.ge(0)&result.end_sec.gt(result.start_sec)&result.end_sec.le(durations+.05)&result.channel_index.lt(channels)).to_numpy()
    for i in np.flatnonzero(~valid):
        r=result.iloc[i]
        exclusions.append({"id":r.source_registry_row_id,"path":r.audio_relative_path,"start":r.start_sec,"end":r.end_sec,"audio_duration":durations.iloc[i],"reason":"new view ends before annotation or channel absent"})
    # Existing audited rows must remain; only unusable additional views may be excluded.
    if not valid[:len(frame)].all():
        raise ValueError("An original audited row failed expansion checks")
    result = result[valid].reset_index(drop=True)
    result["mic_kind"] = [mic_kind(r) for r in result[["dataset_id", "audio_relative_path"]].to_dict("records")]
    result["cluster"] = [str(r.meeting_id) if r.dataset_id == "ami" else str(r.session_id) if r.dataset_id == "chime6" else str(r.speaker_id) for r in result.itertuples()]
    return result, exclusions


def development_panel(frame):
    selected = []
    seed = policy()["seed"]
    for ds, part in frame.groupby("dataset_id"):
        sources = part.source_group_id.drop_duplicates().sample(min(policy()["development_sources_per_dataset"], part.source_group_id.nunique()), random_state=seed)
        for number, (_, group) in enumerate(part[part.source_group_id.isin(sources)].groupby("source_group_id", sort=True)):
            # Each original utterance stays one cluster; compare distinct microphone families.
            for _, family in group.groupby("mic_kind", sort=True):
                chosen=family.sample(1, random_state=seed + number)
                selected.append(chosen)
                if "view_confidence" in family and family.view_confidence.lt(1).any():
                    quiet=family.loc[family.view_confidence.lt(1)].nsmallest(1,"rms_dbfs")
                    if quiet.source_registry_row_id.iloc[0]!=chosen.source_registry_row_id.iloc[0]: selected.append(quiet)
    panel = pd.concat(selected, ignore_index=True)
    panel["sample_weight"] = 1.
    return panel


def prepare_pool():
    HOME.mkdir(parents=True, exist_ok=True)
    if (HOME / "pool.json").exists():
        record = read_json(HOME / "pool.json")
        for split in ("train", "dev", "development"):
            if sha256(HOME / f"{split}.parquet") != record["sha256"][split]:
                raise ValueError("Prepared campaign data changed")
        return record
    raw = REPO / "Software Validation from Datasets/Raw Datasets (Not formatted)"
    files = {ds: list((raw / folder).rglob("*.wav")) for ds, folder in (("ami", "AMI Meeting Corpus"), ("chime6", "CHiME 6"), ("voices", "VOiCES"))}
    original_headers=pd.read_parquet(BASE/"audio_header_audit.parquet")
    cache={r.audio_root_id+":"+r.audio_relative_path:{"duration":r.actual_seconds,"channels":int(r.channels),"sample_rate":int(r.sample_rate)} for r in original_headers.itertuples() if not r.error}
    all_frames, excluded = {}, {}
    for split in ("train", "dev"):
        all_frames[split], excluded[split] = expanded(split, files, cache)
    if set(all_frames["train"].source_group_id) & set(all_frames["dev"].source_group_id):
        raise ValueError("Train/development source overlap")
    # Protect whole meeting/session/speaker identities of every frozen benchmark source.
    frozen = pd.read_parquet(REPO / "Software Validation from Datasets/Evaluation Tool/benchmarks/v1/large_source_manifest.parquet")
    checks = {}
    for ds, key in (("ami", "meeting_id"), ("chime6", "session_id"), ("voices", "speaker_id")):
        def normalize(values):
            return {str(v).lstrip("0") for v in values.dropna() if str(v).strip()}
        protected = normalize(frozen.loc[frozen.dataset.eq(ds), key])
        selected = normalize(pd.concat([f.loc[f.dataset_id.eq(ds), key] for f in all_frames.values()]))
        overlap = protected & selected
        removed = {}
        for split, frame in all_frames.items():
            reserved = frame.dataset_id.eq(ds) & frame[key].astype(str).str.lstrip("0").isin(protected)
            removed[split] = int(reserved.sum())
            all_frames[split] = frame.loc[~reserved].reset_index(drop=True)
        checks[ds] = {"identity": key, "protected": len(protected), "identities_reserved_from_expansion": sorted(overlap), "rows_reserved": removed, "remaining_overlap": []}
    panel = development_panel(all_frames["dev"])
    for split, frame in {**all_frames, "development": panel}.items():
        frame.to_parquet(HOME / f"{split}.parquet", index=False)
    record = {"rows": {k:len(v) for k,v in all_frames.items()}, "development_rows": len(panel), "sha256": {s:sha256(HOME / f"{s}.parquet") for s in ("train", "dev", "development")}, "views": {s:f.groupby(["dataset_id","mic_kind"]).size().to_dict() for s,f in all_frames.items()}, "frozen_test_checks":checks, "excluded_additional_views":excluded, "sources": "all original eligible source utterances and locally available aligned speech views; Common Voice remains age-filtered", "excluded_unlabelled_audio": "VOiCES distractor-only files have no foreground transcript; no invented labels", "chime_opening_second_included":bool((pd.concat(list(all_frames.values())).query("dataset_id == 'chime6'").start_sec < 1).any())}
    record["views"] = {s:{'/'.join(k):int(v) for k,v in values.items()} for s,values in record["views"].items()}
    atomic_json(HOME / "headers.json", cache)
    atomic_json(HOME / "pool.json", record)
    return record


def prepare_run(name, spec):
    folder = run_dir(name)
    folder.mkdir(parents=True, exist_ok=True)
    config = read_json(LAB / "config.json")
    config.update(spec)
    config.update(run_name=f"whistle_followups_v1/runs/{name}", seed=spec.get("seed",policy()["seed"]), epochs=policy()["final_epochs"] if spec.get("production") else policy()["pilot_max_epochs"], validation_every_steps=5000, max_steps=None if spec.get("production") else policy()["pilot_steps"], max_active_seconds=None if spec.get("production") else policy()["pilot_max_active_seconds"], campaign_policy_sha256=freeze_policy())
    config.setdefault("method", "lora")
    if spec.get("extension_id"):
        from extension import config_limits
        config.update(config_limits(name, spec))
    config["dataset_weights"] = spec.get("dataset_weights", config["dataset_weights"])
    if (folder / "config.json").exists():
        if read_json(folder / "config.json") != config:
            raise ValueError("Experiment configuration is immutable once prepared")
        return config
    train = pd.read_parquet(qualified("train"))
    if spec.get("production"):
        train = pd.concat([train,pd.read_parquet(qualified("dev"))], ignore_index=True)
    train = train[train.dataset_id.isin(spec.get("datasets", DATASETS))].reset_index(drop=True)
    train = reweight(train, config["dataset_weights"])
    train.to_parquet(folder / "train.parquet", index=False)
    # Final production has no model selection on development data folded into training.
    panel = pd.read_parquet(qualified("development"))
    panel.to_parquet(folder / "dev.parquet", index=False)
    panel.to_parquet(folder / "validation_monitor.parquet", index=False)
    hashes = {s:sha256(folder / f"{s}.parquet") for s in ("train", "dev")}
    atomic_json(folder / "data_audit.json", {"splits": {s:{"sha256":h} for s,h in hashes.items()}, "campaign_pool":read_json(HOME / "pool.json")["sha256"], "production":bool(spec.get("production")), "training_rows":len(train), "dataset_rows":{str(k):int(v) for k,v in train.groupby("dataset_id").size().items()}, "dataset_sources":{str(k):int(v) for k,v in train.groupby("dataset_id").source_group_id.nunique().items()}})
    atomic_json(folder / "audio_header_audit.json", {"invalid_segments":0, "manifest_sha256":hashes, "evidence":str(HOME / "pool.json")})
    for filename in ("assets.json", "release_review.json"):
        shutil.copyfile(BASE / filename, folder / filename)
    atomic_json(folder / "config.json", config)
    atomic_json(folder / "control.json", {"paused":False})
    return config


if __name__ == "__main__":
    print(json.dumps(prepare_pool(), indent=2))
