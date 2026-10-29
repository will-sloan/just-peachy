"""Convert the AGE_ROBUST freeze, recording only verified unusable annotations."""
from concurrent.futures import ThreadPoolExecutor
import json
import time
import numpy as np
import pandas as pd
from common import ASSETS, CONFIG, REPO, ROOT, RUN, atomic_json, audio_path, environment, read_json, sha256, status
from data import capacities, clean_text, plan_batches


def main():
    environment()
    from needle.model.whistle_finetune import WhistleTokenizer
    tokenizer = WhistleTokenizer()
    source = REPO / CONFIG["source_manifest_directory"]
    report = {"created_at": time.time(), "selection": "full existing AGE_ROBUST training manifests; no new holdout", "files": {}, "splits": {}, "release_review_required": CONFIG["release_review_required"]}
    quarantine = read_json(ROOT / "annotation_quarantine.json")
    report["annotation_quarantine"] = {"records": len(quarantine["records"]), "reason": quarantine["reason"], "sha256": sha256(ROOT / "annotation_quarantine.json"), "source_manifest": quarantine["source_manifest"]}
    columns = ["dataset_id", "source_registry_row_id", "source_group_id", "audio_root_id", "audio_relative_path", "start_sec", "end_sec", "raw_transcript", "training_text", "duration_seconds", "license_id", "evaluation_exact_match", "evaluation_group_match", "evaluation_cross_dataset_match", "evaluation_content_hash_match"]
    for split, names in (("train", CONFIG["training_manifests"]), ("dev", CONFIG["development_manifests"])):
        frames = []
        for name in names:
            path = source / split / name
            status("preparing", message=f"Auditing {split}/{name}")
            frame = pd.read_parquet(path, columns=columns)
            if frame[[c for c in columns if c.startswith("evaluation_")]].fillna(False).any().any():
                raise ValueError(f"Evaluation overlap found in {path}")
            report["files"][f"{split}/{name}"] = {"sha256": sha256(path), "rows": len(frame)}
            if f"{split}/{name}" == quarantine["source_manifest"]:
                if sha256(path) != quarantine["source_sha256"]:
                    raise ValueError("Quarantine evidence does not match the source manifest")
                expected = pd.DataFrame(quarantine["records"])
                selected = frame[frame.source_registry_row_id.isin(expected.source_registry_row_id)]
                if len(selected) != len(expected) or not selected.source_registry_row_id.is_unique:
                    raise ValueError("Quarantine IDs are missing or duplicated")
                compared = selected.merge(expected, on="source_registry_row_id", suffixes=("", "_audit"), validate="one_to_one")
                for column in ("audio_root_id", "audio_relative_path", "start_sec", "end_sec"):
                    if not compared[column].equals(compared[column + "_audit"]):
                        raise ValueError(f"Quarantine annotation changed: {column}")
                frame = frame[~frame.source_registry_row_id.isin(expected.source_registry_row_id)].copy()
                report["annotation_quarantine"]["physical_hours"] = float((selected.end_sec - selected.start_sec).sum() / 3600)
                report["annotation_quarantine"]["unique_sources"] = selected.source_group_id.nunique()
            frame["text"] = [clean_text(raw, ds, old) for raw, ds, old in zip(frame.raw_transcript, frame.dataset_id, frame.training_text)]
            unique = frame.text.drop_duplicates().tolist()
            token_map = {text: [2, tokenizer.text, *tokenizer.encode(text), 1] for text in unique}
            frame["tokens"] = frame.text.map(token_map)
            cap = [capacities(end - start, len(tokens)) for start, end, tokens in zip(frame.start_sec, frame.end_sec, frame.tokens)]
            frame["audio_capacity"] = [c[0] for c in cap]
            frame["token_capacity"] = [c[1] for c in cap]
            frame["sample_weight"] = 1.0
            frames.append(frame.drop(columns=["raw_transcript", "training_text"]))
        frame = pd.concat(frames, ignore_index=True)
        unique_paths = frame[["audio_root_id", "audio_relative_path"]].drop_duplicates().to_dict("records")
        def exists(row):
            path = audio_path(row["audio_root_id"], row["audio_relative_path"])
            return None if path.is_file() else str(path)
        with ThreadPoolExecutor(max_workers=12) as pool:
            missing = [p for p in pool.map(exists, unique_paths) if p is not None]
        if missing:
            atomic_json(RUN / "missing_audio.json", missing)
            raise FileNotFoundError(f"{len(missing)} source files missing; see missing_audio.json")
        if split == "train":
            # Retain every microphone view, while correcting its contribution to loss.
            for dataset, part in frame.groupby("dataset_id"):
                counts = part.groupby("source_group_id")["source_group_id"].transform("count")
                frame.loc[part.index, "sample_weight"] = (CONFIG["dataset_weights"][dataset] * len(frame) / part.source_group_id.nunique() / counts)
        summaries = []
        for dataset, part in frame.groupby("dataset_id"):
            summaries.append({"dataset": dataset, "records": len(part), "physical_hours": float((part.end_sec - part.start_sec).sum() / 3600), "unique_source_hours": float(part.drop_duplicates("source_group_id").duration_seconds.sum() / 3600), "blank_targets": int(part.text.eq("").sum()), "longer_than_30_seconds": int(((part.end_sec - part.start_sec) > 30).sum()), "license": sorted(part.license_id.unique().tolist())})
        target = RUN / f"{split}.parquet"
        frame.to_parquet(target, index=False)
        report["splits"][split] = {"records": len(frame), "datasets": summaries, "sha256": sha256(target), "steps_per_epoch": len(plan_batches(frame, 0))}
        if split == "dev":
            selected = []
            for _, part in frame.groupby("dataset_id"):
                selected.append(part.sample(min(CONFIG["validation_per_dataset"], len(part)), random_state=CONFIG["seed"]))
            pd.concat(selected, ignore_index=True).to_parquet(RUN / "validation_monitor.parquet", index=False)
        print(json.dumps(report["splits"][split], indent=2), flush=True)
    atomic_json(RUN / "data_audit.json", report)
    status("ready", message="Full training pool audited; ready for GPU benchmark", total_records=report["splits"]["train"]["records"], datasets=report["splits"]["train"]["datasets"])


if __name__ == "__main__":
    main()
