"""Small matched comparison using frozen GigaSpeech predictions, after training."""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from common import ASSETS, CONFIG, REPO, RUN, atomic_json, environment, read_json, sha256, status
from data import load_audio

EVALUATION = REPO / "Software Validation from Datasets/Evaluation Tool"


def prepare_evaluation():
    target = RUN / "evaluation.parquet"
    if target.exists():
        return pd.read_parquet(target)
    source = pd.read_parquet(EVALUATION / "benchmarks/v1/large_source_manifest.parquet")
    scenarios = [json.loads(line) for line in (EVALUATION / "benchmarks/edge_research/scenarios_edge_large_sherpa_libri_giga.jsonl").read_text().splitlines() if line.strip()]
    parts = []
    for scenario in scenarios:
        if scenario["condition"]["augmentation"] != "none":
            continue
        metrics_path = EVALUATION / "automated_runs/campaign_edge_lg_shgiga_v1/scenarios" / scenario["scenario_id"] / "metrics/item_metrics.parquet"
        metrics = pd.read_parquet(metrics_path)
        metrics = metrics[~metrics.missing_prediction.fillna(True)]
        dataset = scenario["dataset_slice"]["dataset"]
        pool = source[source.dataset.eq(dataset)]
        joined = pool.merge(metrics[["recording_id", "utt_id", "hypothesis_text", "reference_text"]], on=["recording_id", "utt_id"], suffixes=("", "_giga"), validate="one_to_one")
        if joined.empty:
            raise ValueError(f"No exact reference match for {scenario['scenario_id']}")
        if not joined.reference_text.fillna("").eq(joined.reference_text_giga.fillna("")).all():
            raise ValueError("Historical baseline reference text differs from the frozen evaluation manifest")
        selected = joined.sample(min(64, len(joined)), random_state=CONFIG["seed"]).copy()
        selected["cohort"] = dataset + ":" + scenario["condition"]["id"]
        selected["scenario_id"] = scenario["scenario_id"]
        selected["giga_metrics_sha256"] = sha256(metrics_path)
        selected["giga_hypothesis"] = selected.hypothesis_text.fillna("")
        parts.append(selected)
    frame = pd.concat(parts, ignore_index=True)
    frame["dataset_id"] = frame.dataset
    frame["audio_root_id"] = "JP_DATA_ROOT"
    frame["audio_relative_path"] = frame.audio_path_project_relative
    frame["source_registry_row_id"] = frame.scenario_id + ":" + frame.recording_id + ":" + frame.utt_id.fillna("")
    train_paths = set(pd.read_parquet(RUN / "train.parquet", columns=["audio_relative_path"]).audio_relative_path)
    if frame.audio_relative_path.isin(train_paths).any():
        raise ValueError("Evaluation shares a source file with training; inspect before scoring")
    frame.to_parquet(target, index=False)
    atomic_json(RUN / "evaluation_plan.json", {"records": len(frame), "cohorts": frame.cohort.value_counts().to_dict(), "manifest_sha256": sha256(target), "historical_baseline": "cached GigaSpeech predictions rescored on identical selected segments with the same normalizer", "timing_comparison": "Whistle timings are local CPU measurements; historical GigaSpeech timing is not compared", "not_used_for_model_selection": True, "training_data_removed_for_evaluation": 0})
    return frame


def score(reference, hypothesis):
    from jiwer import process_words, process_characters
    from whisper_normalizer.english import EnglishTextNormalizer
    normalize = EnglishTextNormalizer()
    ref, hyp = normalize(reference or ""), normalize(hypothesis or "")
    word = process_words(ref, hyp)
    char = process_characters(ref.replace(" ", ""), hyp.replace(" ", ""))
    return {"word_errors": word.substitutions + word.deletions + word.insertions, "reference_words": word.hits + word.substitutions + word.deletions, "character_errors": char.substitutions + char.deletions + char.insertions, "reference_characters": char.hits + char.substitutions + char.deletions}


def aggregate(records):
    frame = pd.DataFrame(records)
    output = []
    for (model, cohort), part in frame.groupby(["model", "cohort"]):
        words, characters = int(part.reference_words.sum()), int(part.reference_characters.sum())
        item = {"model": model, "cohort": cohort, "records": len(part), "wer": float(part.word_errors.sum() / words) if words else None, "cer": float(part.character_errors.sum() / characters) if characters else None, "reference_words": words}
        if "wall_seconds" in part and part.wall_seconds.notna().any():
            item.update(rtf=float(part.wall_seconds.sum() / part.audio_seconds.sum()), median_ttft_ms=float(part.ttft_ms.median()), p95_ttft_ms=float(part.ttft_ms.quantile(.95)))
        output.append(item)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    environment()
    frame = prepare_evaluation()
    if args.prepare_only:
        print(json.dumps(read_json(RUN / "evaluation_plan.json"), indent=2))
        return
    import needle
    import psutil
    models = [("whistle_base", ASSETS / "whistle.cact")]
    if args.smoke:
        frame = frame.groupby("cohort", group_keys=False).head(1).reset_index(drop=True)
    else:
        models += [("whistle_tuned_best", RUN / "whistle.best.cact"), ("whistle_tuned_final", RUN / "whistle.final.cact")]
        status("evaluating", percent=100., message="Training is complete; scoring base and tuned models on matched historical benchmark segments")
    rows = []
    for row in frame.to_dict("records"):
        rows.append({"model": "sherpa_gigaspeech_cached", "cohort": row["cohort"], "item_id": row["source_registry_row_id"], **score(row["reference_text"], row["giga_hypothesis"])})
    for name, weights in models:
        path = RUN / (name + (".smoke.jsonl" if args.smoke else ".predictions.jsonl"))
        previous = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        identity = sha256(weights)
        if any(item["model_sha256"] != identity for item in previous):
            raise ValueError("Evaluation weights changed since partial results were written")
        rows.extend(previous)
        done = {item["item_id"] for item in previous}
        model = needle.Whistle(weights=str(weights))
        for index, row in enumerate(frame.to_dict("records")):
            if row["source_registry_row_id"] in done:
                continue
            if not args.smoke and read_json(RUN / "control.json").get("paused", False):
                status("paused", message="Post-training comparison paused; saved predictions will resume")
                return 75
            samples = load_audio(row)
            start = time.perf_counter()
            prediction = model.transcribe(samples, language="en")
            elapsed = time.perf_counter() - start
            result = {"model": name, "cohort": row["cohort"], "item_id": row["source_registry_row_id"], "model_sha256": identity, "hypothesis": prediction["text"], "wall_seconds": elapsed, "audio_seconds": len(samples) / 16000, "ttft_ms": prediction.get("ttft_ms"), "decode_tps": prediction.get("decode_tps"), "rss_mb": psutil.Process().memory_info().rss / 1024**2, **score(row["reference_text"], prediction["text"])}
            rows.append(result)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, allow_nan=False) + "\n")
            print(f"{name}: {index + 1}/{len(frame)} {row['cohort']} {elapsed:.3f}s", flush=True)
            if not args.smoke and (index % 8 == 0 or index + 1 == len(frame)):
                status("evaluating", percent=100., message=f"Training complete; scoring {name}: {index + 1}/{len(frame)} clips")
        if args.smoke:
            # Only test API availability; this is not a speaker-recognition claim.
            samples = load_audio(frame.iloc[0].to_dict())
            start = time.perf_counter()
            embedding = np.asarray(model.embed(samples), np.float32)
            atomic_json(RUN / "embedding_probe.json", {"available": True, "values": int(embedding.size), "finite": bool(np.isfinite(embedding).all()), "seconds": time.perf_counter() - start, "audio_seconds": len(samples) / 16000, "speaker_identification_validated": False, "dataset": frame.iloc[0].dataset_id})
            events = list(model.stream([samples[i:i+16000] for i in range(0, len(samples), 16000)], language="en"))
            atomic_json(RUN / "streaming_probe.json", {"events": len(events), "text": " ".join(event.get("text", "") for event in events), "pass_ms": [event.get("pass_ms") for event in events], "note": "API smoke test on prerecorded one-second chunks, not Raspberry Pi latency"})
    summary = {"complete": not args.smoke, "smoke_only": args.smoke, "metrics": aggregate(rows), "normalization": "whisper-normalizer EnglishTextNormalizer for all models, including rescored historical predictions", "timing_hardware": "current Windows machine through Linux WSL2 CPU; not Raspberry Pi", "training_records_held_back": 0}
    atomic_json(RUN / ("smoke_summary.json" if args.smoke else "evaluation_summary.json"), summary)
    print(json.dumps(summary, indent=2))
    if not args.smoke:
        status("complete", percent=100., message="Full-pool fine-tuning, export and matched comparison complete")


if __name__ == "__main__":
    raise SystemExit(main())
