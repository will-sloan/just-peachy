"""Resumable native decoding of one frozen exploratory panel."""
from __future__ import annotations
import argparse
import json
import time
import traceback
from runtime import *


def records(path):
    if not path.exists():
        return []
    output = []
    with path.open("rb+") as handle:
        while True:
            start = handle.tell()
            line = handle.readline()
            if not line:
                break
            try:
                output.append(json.loads(line))
                if not line.endswith(b"\n"):
                    handle.seek(0, 2)
                    handle.write(b"\n")
            except (ValueError, UnicodeDecodeError):
                if handle.read(1):
                    raise ValueError("Malformed interior scoring record")
                handle.truncate(start)
                break
    return output


def summarize(items):
    import pandas as pd
    frame = pd.DataFrame(items)
    cohorts = {}
    for name, p in frame.groupby("cohort"):
        sources = p.groupby("source_group_id")[["word_errors", "reference_words", "character_errors", "reference_characters"]].mean()
        cohorts[name] = {"wer": float(sources.word_errors.sum() / sources.reference_words.sum()),
                         "cer": float(sources.character_errors.sum() / sources.reference_characters.sum()),
                         "sources": len(sources), "clips": len(p), "clusters": p.cluster.nunique(),
                         "reference_words": float(sources.reference_words.sum())}
    quiet = frame[frame.audio_level.eq("quiet")]
    q = quiet.groupby(["cohort", "source_group_id"])[["word_errors", "reference_words"]].mean()
    words = float(q.reference_words.sum())
    return {"cohorts": cohorts, "macro_wer": sum(c["wer"] for c in cohorts.values()) / len(cohorts),
            "primary_wer": (cohorts["ami"]["wer"] + cohorts["chime6"]["wer"]) / 2,
            "quiet_audio": {"clips": len(quiet), "sources": len(q), "reference_words": words,
                            "wer": float(q.word_errors.sum() / words) if words else None},
            "mic_slices": {str(k): {"clips": len(p), "wer": float(p.word_errors.sum()/p.reference_words.sum())}
                           for k, p in frame.groupby(["cohort", "mic_kind"]) if p.reference_words.sum()}}


def main():
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument("step", type=int)
    parser.add_argument("--role", choices=["dev", "confirmation"], default="dev")
    args = parser.parse_args()
    if paused():
        return 75
    verify()
    locks = []
    for path in (BASE / "trainer.lock", FOLLOWUP / "gpu.lock", RUN / "worker.lock"):
        handle = path.open("a+b")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 73
        locks.append(handle)
    import os
    os.environ["JAX_PLATFORMS"] = "cpu"
    common.environment()
    import audioio
    import numpy as np
    import pandas as pd
    import needle
    from evaluate import score
    if args.role == "confirmation":
        decision = read_json(RUN / "development_decision.json")
        if not decision.get("frozen") or args.step not in (0, decision["selected_step"]):
            raise ValueError("Confirmation requires one already-frozen development checkpoint")
    _, weights = export_paths(args.step)
    identity = sha256(weights)
    panel = RUN / (args.role + ".parquet")
    panel_hash = sha256(panel)
    out = scores_path(args.step, args.role)
    previous_summary = read_json(out)
    if previous_summary.get("complete"):
        if previous_summary["model_sha256"] != identity or previous_summary["panel_sha256"] != panel_hash:
            raise ValueError("Completed scoring identity changed")
        return 0
    out.parent.mkdir(exist_ok=True)
    path = out.with_suffix(".jsonl")
    frame = pd.read_parquet(panel)
    previous = records(path)
    if any(r["model_sha256"] != identity or r["panel_sha256"] != panel_hash for r in previous):
        raise ValueError("Partial scoring identity changed")
    done = {r["item_id"] for r in previous}
    if len(done) != len(previous) or not done <= set(frame.source_registry_row_id):
        raise ValueError("Unknown or duplicate scored items")
    model = needle.Whistle(weights=str(weights))
    status("evaluating", step=args.step, role=args.role, message="Native decoding on a frozen exploratory panel")
    for row in frame.to_dict("records"):
        if row["source_registry_row_id"] in done:
            continue
        if paused():
            status("paused", message="Scoring paused; completed predictions retained")
            return 75
        wave = audioio.load_audio(row)
        start = time.perf_counter()
        result = model.transcribe(wave, language="en")
        elapsed = time.perf_counter() - start
        record = {"item_id": row["source_registry_row_id"], "cohort": row["cohort"],
                  "source_group_id": row["source_group_id"], "cluster": row["cluster"],
                  "mic_kind": row["mic_kind"], "audio_level": row["audio_level"],
                  "hypothesis": result["text"], "model_sha256": identity, "panel_sha256": panel_hash,
                  "audio_seconds": len(wave)/16000, "wall_seconds": elapsed,
                  **score(row["text"], result["text"])}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, allow_nan=False) + "\n")
        previous.append(record)
        if len(previous) % 10 == 0 or len(previous) == 1:
            atomic_json(RUN / "scoring_status.json", {"role": args.role, "step": args.step,
                "completed": len(previous), "total": len(frame), "updated_at": time.time()})
            print(f"{args.role} step {args.step}: {len(previous)}/{len(frame)}", flush=True)
    probe_path = out.with_suffix(".negative.jsonl")
    probes = records(probe_path)
    if any(r["model_sha256"] != identity for r in probes):
        raise ValueError("Probe model identity changed")
    done = {r["item_id"] for r in probes}
    for duration in (3, 5, 10, 20):
        for level in (None, -60, -40, -20, -10):
            item = f"{duration}s_{level}"
            if item in done:
                continue
            if paused():
                return 75
            rng = np.random.default_rng(20261022 + duration)
            wave = np.zeros(duration*16000, np.float32) if level is None else (rng.normal(size=duration*16000)*10**(level/20)).astype(np.float32)
            hypothesis = model.transcribe(wave, language="en")["text"]
            record = {"item_id": item, "model_sha256": identity, "hypothesis": hypothesis,
                      "inserted_words": score("", hypothesis)["word_errors"]}
            with probe_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
            probes.append(record)
    summary = {"complete": True, "role": args.role, "step": args.step, "model_sha256": identity,
               "panel_sha256": panel_hash, "predictions": path.name, **summarize(previous),
               "negative_probes": {"clips": len(probes), "false_positive_rate": sum(p["inserted_words"] > 0 for p in probes)/len(probes),
                                   "inserted_words": sum(p["inserted_words"] for p in probes)},
               "independent_confirmation": False, "real_product_validation": False,
               "normalization": "Whisper EnglishTextNormalizer; source-balanced microphone views"}
    atomic_json(out, summary)
    atomic_json(RUN / "scoring_status.json", {"role": args.role, "step": args.step, "completed": len(frame),
                                            "total": len(frame), "complete": True, "updated_at": time.time()})
    print(json.dumps({"complete": True, "step": args.step, "role": args.role, "macro_wer": summary["macro_wer"],
                      "primary_wer": summary["primary_wer"]}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        status("failed", message=str(error), traceback=traceback.format_exc())
        raise
