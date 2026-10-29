"""Freeze an exploratory mixed adaptation, source sampler and retention panels."""
from __future__ import annotations
import hashlib
import json
import shutil
import pandas as pd
import numpy as np
import soundfile as sf
from runtime import *

FRAMEWORK = REPO / "training/successors/phase5a_original_adapter_training_v1/framework_manifests"
NORM = REPO / "Software Validation from Datasets/Normalized Metadata"


def partition(key):
    return int(hashlib.sha256(("20261025:" + str(key)).encode()).hexdigest()[:8], 16) % 2


def reader_key(value):
    return "librivox:" + str(value).lstrip("0")


def panel_partitions(frame):
    """Deterministic group split with coverage repair using metadata only."""
    groups = {name: set(p.cluster) for name, p in frame.groupby("cohort")}
    assigned = {key: partition(key) for key in frame.cluster.unique()}
    for cohort in sorted(groups, key=lambda name: (len(groups[name]), name)):
        keys = groups[cohort]
        if len(keys) < 2:
            raise ValueError("Cannot make disjoint panels for " + cohort)
        sides = {assigned[key] for key in keys}
        if len(sides) == 2:
            continue
        old_side = next(iter(sides))
        safe = [key for key in keys if all(
            key not in other or sum(assigned[k] == old_side for k in other) > 1
            for other in groups.values())]
        if not safe:
            raise ValueError("No group-disjoint coverage repair is available for " + cohort)
        chosen = min(safe, key=lambda key: hashlib.sha256(("coverage:" + key).encode()).hexdigest())
        assigned[chosen] = 1 - old_side
    if any(len({assigned[key] for key in keys}) != 2 for keys in groups.values()):
        raise ValueError("Panel coverage repair failed")
    return assigned


def balanced_sources(frame, target=128):
    # Round-robin source selection across groups; no scores enter selection.
    unique = frame[["source_group_id", "cluster"]].drop_duplicates("source_group_id").copy()
    unique["order"] = unique.source_group_id.map(lambda s: hashlib.sha256(("20261025:" + s).encode()).hexdigest())
    unique = unique.sort_values(["cluster", "order"])
    unique["rank"] = unique.groupby("cluster").cumcount()
    chosen = unique.sort_values(["rank", "order"]).head(target).source_group_id
    rows = []
    for _, source in frame[frame.source_group_id.isin(chosen)].groupby("source_group_id", sort=True):
        for _, family in source.groupby("mic_kind", sort=True):
            ordered = family.sort_values("source_registry_row_id")
            rows.append(ordered.iloc[[0]])
            quiet = family[family.audio_level.eq("quiet")]
            if len(quiet):
                quiet = quiet.sort_values(["rms_dbfs", "source_registry_row_id"]).iloc[[0]]
                if quiet.source_registry_row_id.iloc[0] != ordered.source_registry_row_id.iloc[0]:
                    rows.append(quiet)
    return pd.concat(rows, ignore_index=True)


def main():
    RUN.mkdir(exist_ok=True)
    common.environment()
    import os
    os.environ['JAX_PLATFORMS'] = 'cpu'
    from needle.model.whistle_finetune import WhistleTokenizer
    from data import capacities
    tokenizer = WhistleTokenizer()
    if (RUN / "config.json").exists():
        verify()
        print(json.dumps(read_json(RUN / "split_snapshot.json"), indent=2))
        return
    if paused():
        raise RuntimeError("A user pause is active")
    status("preparing", training_launched=False, step=0, message="Freezing exploratory mixed training and disjoint retention panels")
    if read_json(FOLLOWUP / "summary.json").get("complete") is not True:
        raise ValueError("The prior bounded campaign must be complete")
    amendment = read_json(SOURCE / "execution_amendment.json")
    if amendment.get("user_choice") != "Run exploratory adaptation; keep the initial model as default and disclose the evaluation limitation":
        raise ValueError("Exploratory authorization missing")
    frozen = RUN / "execution_amendment.json"
    if frozen.exists() and read_json(frozen) != amendment:
        raise ValueError("Execution amendment is immutable")
    atomic_json(frozen, amendment)
    proposal_path = LAB / "proposals/initial_ami_guarded_v1/plan.json"
    atomic_json(RUN / "proposal_snapshot.json", {"proposal": read_json(proposal_path), "sha256": sha256(proposal_path)})
    quality = read_json(FOLLOWUP / "audio_quality.json")
    if not quality.get("complete"):
        raise ValueError("Completed quality generation required")
    for split in ("train", "dev"):
        if sha256(FOLLOWUP / "quality" / (split + ".parquet")) != quality["sha256"][split]:
            raise ValueError("Qualified pool hash changed")

    parent = pd.read_parquet(BASE / "train.parquet", columns=["dataset_id", "source_group_id", "source_registry_row_id"])
    trained_clusters = {}
    for name, ds, key in (("age", "common_voice", "speaker_id"), ("ami", "ami", "meeting_id"),
                          ("chime", "chime6", "session_id"), ("voices", "voices", "speaker_id")):
        m = pd.read_parquet(FRAMEWORK / "train" / f"{name}_train.parquet",
                            columns=["source_registry_row_id", key])
        joined = parent[parent.dataset_id.eq(ds)].merge(m, on="source_registry_row_id", how="left", validate="one_to_one")
        if joined[key].isna().any():
            raise ValueError("Parent identity join missing: " + ds)
        trained_clusters[ds] = set(joined[key].astype(str).str.lstrip("0"))
    qualified = pd.read_parquet(FOLLOWUP / "quality/train.parquet")
    if not set(qualified.source_group_id) <= set(parent.source_group_id):
        raise ValueError("New qualified sources outside the parent's eligible training population")
    if (qualified.view_confidence <= 0).any():
        raise ValueError("A quarantined view entered training")
    # Clean replay uses an official training split, with speakers reserved from
    # every evaluation cohort below. It does not use the historical test clips.
    clean = pd.read_parquet(NORM / "LibriSpeech/recordings.parquet")
    clean = clean[clean.split.eq("train-clean-100")].copy()
    clean = clean[clean.duration_sec.gt(0) & clean.duration_sec.le(150)].copy()
    clean["order"] = clean.recording_id.map(lambda s: hashlib.sha256(("20261025:" + s).encode()).hexdigest())
    clean = clean.sort_values("order").head(8000).copy()
    text = pd.read_parquet(NORM / "LibriSpeech/utterances.parquet", columns=["recording_id", "text_original"])
    clean = clean.merge(text, on="recording_id", validate="one_to_one")
    clean_speakers = set(clean.speaker_id.astype(str).str.lstrip("0"))
    clean_frame = pd.DataFrame({
        "dataset_id": "librispeech_clean", "source_group_id": "librispeech:" + clean.recording_id,
        "source_registry_row_id": "librispeech:" + clean.recording_id,
        "audio_root_id": "JP_DATA_ROOT",
        "audio_relative_path": clean.audio_path.map(lambda s: str(s).replace(chr(92), "/").split("/Software Validation from Datasets/", 1)[1]),
        "start_sec": 0., "end_sec": clean.duration_sec, "duration_seconds": clean.duration_sec,
        "text": clean.text_original, "channel_index": 0, "view_confidence": 1.,
        "audio_level": "not_measured", "mic_kind": "clean", "cluster": clean.speaker_id.map(reader_key),
        "license_id": "CC-BY-4.0",
    })
    clean_frame["tokens"] = [[2, tokenizer.text, *tokenizer.encode(t), 1] for t in clean_frame.text]
    caps = [capacities(d, len(t)) for d, t in zip(clean_frame.duration_seconds, clean_frame.tokens)]
    clean_frame["audio_capacity"] = [c[0] for c in caps]
    clean_frame["token_capacity"] = [c[1] for c in caps]
    for row in clean_frame.to_dict("records"):
        info = sf.info(str(common.audio_path(row["audio_root_id"], row["audio_relative_path"])))
        if row["end_sec"] > info.duration + .05:
            raise ValueError("Clean replay annotation exceeds actual audio")
    pool_train = pd.concat([qualified, clean_frame], ignore_index=True)
    weights = amendment["training"]["dataset_probabilities"]
    rng = np.random.default_rng(20261022)
    visits = []
    for ds, count in amendment["training"]["schedule_visits"].items():
        p = pool_train[pool_train.dataset_id.eq(ds)]
        groups = p.groupby("source_group_id", sort=True).indices
        keys = sorted(groups)
        order = []
        while len(order) < count:
            order.extend(rng.permutation(len(keys)).tolist())
        for key in order[:count]:
            indices = groups[keys[key]]
            confidence = p.iloc[indices].view_confidence.to_numpy(float)
            choice = int(rng.choice(indices, p=confidence / confidence.sum()))
            visits.append(p.index[choice])
    train = pool_train.loc[visits].reset_index(drop=True).copy()
    train["sample_weight"] = 1.
    train["schedule_visit"] = np.arange(len(train), dtype=np.int64)
    del qualified, pool_train

    dev = pd.read_parquet(FOLLOWUP / "quality/dev.parquet")
    dev["cohort"] = dev.dataset_id.replace({"common_voice": "common_voice_age"})
    parts = []
    for ds, p in dev.groupby("dataset_id"):
        key = "meeting_id" if ds == "ami" else "session_id" if ds == "chime6" else "speaker_id"
        p = p[~p[key].astype(str).str.lstrip("0").isin(trained_clusters[ds])].copy()
        if ds == "voices":
            p = p[~p[key].astype(str).str.lstrip("0").isin(clean_speakers)].copy()
        p["cluster"] = p[key].map(reader_key) if ds == "voices" else ds + ":" + p[key].astype(str)
        parts.append(p)
    # Extra CHiME held-out sessions improve coverage beyond its two dev sessions.
    historical = pd.read_parquet(REPO / "Software Validation from Datasets/Evaluation Tool/benchmarks/v1/large_source_manifest.parquet",
                                 filters=[("dataset", "==", "chime6")])
    historical = historical[~historical.session_id.isin(trained_clusters["chime6"]) & historical.start_sec.ge(1)].copy()
    extra = pd.DataFrame({
        "dataset_id": "chime6", "cohort": "chime6",
        "source_group_id": "chime6:historical:" + historical.source_utterance_id,
        "source_registry_row_id": "chime6:historical:" + historical.recording_id + ":" + historical.utt_id,
        "cluster": "chime6:" + historical.session_id, "mic_kind": "array",
        "audio_root_id": "JP_DATA_ROOT", "audio_relative_path": historical.audio_path_project_relative,
        "start_sec": historical.start_sec, "end_sec": historical.end_sec,
        "text": historical.reference_text, "channel_index": 0, "audio_level": "not_measured", "rms_dbfs": np.nan,
    })
    parts.append(extra)
    # Retention data are evaluation-only. Exclude LibriVox speakers trained through VOiCES.
    old = pd.read_parquet(BASE / "evaluation.parquet", columns=["audio_relative_path"])
    for folder, dataset in (("CMU_Arctic", "cmu_arctic"), ("HiFiTTS", "hifitts"), ("LibriSpeech", "librispeech")):
        rec = pd.read_parquet(NORM / folder / "recordings.parquet")
        utt = pd.read_parquet(NORM / folder / "utterances.parquet")
        text_key = "text" if dataset == "hifitts" else "text_original"
        rec = rec.merge(utt[["recording_id", text_key]], on="recording_id", validate="one_to_one")
        speaker = "reader_id" if dataset == "hifitts" else "speaker_id"
        if dataset != "cmu_arctic":
            rec = rec[~rec[speaker].astype(str).str.lstrip("0").isin((trained_clusters["voices"] | clean_speakers))]
        if dataset == "librispeech":
            rec = rec[rec.split.isin(["dev-clean", "dev-other"])]
        # Exclude the inspected 512 exact clips. The population itself is still exposed.
        rec["audio_relative_path"] = rec.audio_path.map(lambda s: str(s).replace(chr(92), "/").split("/Software Validation from Datasets/", 1)[1])
        rec = rec[~rec.audio_relative_path.isin(old.audio_relative_path)]
        duration = "duration_sec_audio" if dataset == "hifitts" else "duration_sec"
        rec = rec[rec[duration].gt(0) & rec[text_key].fillna("").str.strip().ne("")].copy()
        mic = pd.Series("clean", index=rec.index)
        if dataset == "hifitts":
            mic = rec.audio_quality.map({"clean": "clean", "other": "native"})
        if dataset == "librispeech":
            mic = rec.split.map({"dev-clean": "clean", "dev-other": "native"})
        cluster = rec[speaker].map(reader_key) if dataset != "cmu_arctic" else "cmu:" + rec.speaker_code.astype(str)
        parts.append(pd.DataFrame({
            "dataset_id": dataset, "cohort": dataset + "_" + mic, "cluster": cluster,
            "source_group_id": dataset + ":" + rec.recording_id,
            "source_registry_row_id": dataset + ":" + rec.recording_id, "mic_kind": mic,
            "audio_root_id": "JP_DATA_ROOT", "audio_relative_path": rec.audio_relative_path,
            "start_sec": 0., "end_sec": rec[duration].astype(float),
            "text": rec[text_key], "channel_index": 0, "audio_level": "not_measured", "rms_dbfs": np.nan,
        }))
    columns = ["dataset_id", "cohort", "source_group_id", "source_registry_row_id", "cluster", "mic_kind",
               "audio_root_id", "audio_relative_path", "start_sec", "end_sec", "text", "channel_index",
               "audio_level", "rms_dbfs"]
    pool = pd.concat([p[columns] for p in parts], ignore_index=True)
    assignment = panel_partitions(pool)
    pool["partition"] = pool.cluster.map(assignment)
    panels = {}
    for role, value in (("dev", 0), ("confirmation", 1)):
        selected = [balanced_sources(p) for _, p in pool[pool.partition.eq(value)].groupby("cohort")]
        panel = pd.concat(selected, ignore_index=True).sort_values(["cohort", "source_registry_row_id"]).reset_index(drop=True)
        if set(panel.cohort) != set(COHORTS) or panel.source_registry_row_id.duplicated().any():
            raise ValueError(f"Invalid {role} panel: cohorts={sorted(set(panel.cohort))}; duplicate IDs={int(panel.source_registry_row_id.duplicated().sum())}")
        panel["sample_weight"] = 1.
        panels[role] = panel
    if set(panels["dev"].cluster) & set(panels["confirmation"].cluster):
        raise ValueError("Development/confirmation cluster overlap")
    if set(train.source_group_id) & set(pool.source_group_id):
        raise ValueError("New training overlaps evaluation sources")
    # Validate only selected evaluation file headers; do not launch a new level audit.
    checked = {}
    for p in panels.values():
        for row in p.to_dict("records"):
            path = common.audio_path(row["audio_root_id"], row["audio_relative_path"])
            key = str(path)
            if key not in checked:
                info = sf.info(str(path)); checked[key] = (info.duration, info.channels)
            duration, channels = checked[key]
            if row["start_sec"] < 0 or row["end_sec"] <= row["start_sec"] or row["end_sec"] > duration + .05 or row["channel_index"] >= channels:
                raise ValueError("Evaluation header/annotation mismatch: " + row["source_registry_row_id"])
    for name, frame in {"train": train, **panels}.items():
        frame.to_parquet(RUN / (name + ".parquet"), index=False)
    hashes = {key: sha256(RUN / (key + ".parquet")) for key in ("train", "dev", "confirmation")}
    coverage = {role: {cohort: {"clips": len(p), "sources": p.source_group_id.nunique(), "clusters": p.cluster.nunique(),
                                "quiet_clips": int(p.audio_level.eq("quiet").sum())}
                        for cohort, p in frame.groupby("cohort")} for role, frame in panels.items()}
    snapshot = {"complete": True, "sha256": hashes, "coverage": coverage,
                "cluster_assignment": assignment,
                "coverage_shortfalls": {role: {name: value for name, value in cohorts.items()
                    if value["sources"] < 128 or value["clusters"] < 2} for role, cohorts in coverage.items()},
                "training_rows": len(train), "training_sources": train.source_group_id.nunique(),
                "training_dataset_visits": train.dataset_id.value_counts().to_dict(),
                "training_dataset_sources": train.groupby("dataset_id").source_group_id.nunique().to_dict(),
                "clean_training_speakers": sorted(clean_speakers),
                "parent_training_excluded": True, "development_confirmation_clusters_disjoint": True,
                "quality_generation": "ce763f776b2cf4a81168", "quality_sha256": quality["sha256"],
                "independent_confirmation": False, "automatic_promotion": False,
                "limitation": "Exploratory held-out utterances and disjoint panels from previously evaluated populations; not independent confirmation.",
                "metadata_sha256": {str(p.relative_to(REPO)): sha256(p) for p in
                    [NORM / f / (n + ".parquet") for f in ("CMU_Arctic", "HiFiTTS", "LibriSpeech") for n in ("recordings", "utterances")]}}
    atomic_json(RUN / "split_snapshot.json", snapshot)
    config = read_json(LAB / "config.json")
    config.update(run_name=RUN.name, epochs=1, learning_rate=1e-5, max_batch_size=8,
                  batch_audio_seconds=60, batch_tokens=1024, max_steps=10000, max_active_seconds=3600,
                  warmup_steps=200, end_learning_rate=5e-7, dataset_weights=weights,
                  amendment_sha256=sha256(frozen), split_snapshot_sha256=sha256(RUN / "split_snapshot.json"),
                  initial_adapter_sha256=read_json(RUN / "proposal_snapshot.json")["proposal"]["initialization"]["adapter_sha256"])
    atomic_json(RUN / "data_audit.json", {"splits": {k: {"sha256": v} for k, v in hashes.items()}, "training_rows": len(train)})
    atomic_json(RUN / "audio_header_audit.json", {"invalid_segments": 0, "manifest_sha256": {k: hashes[k] for k in ("train", "dev")},
                                                "training_evidence": str(FOLLOWUP / "audio_quality.json"), "evaluation_headers_checked": len(checked)})
    for file in ("assets.json", "release_review.json"):
        shutil.copyfile(BASE / file, RUN / file)
    if not (RUN / "control.json").exists():
        atomic_json(RUN / "control.json", {"paused": False})
    atomic_json(RUN / "config.json", config)  # publish last
    status("prepared", training_launched=False, step=0, message="Exploratory mixed-replay schedule and panels frozen; GPU initialization pending")
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
