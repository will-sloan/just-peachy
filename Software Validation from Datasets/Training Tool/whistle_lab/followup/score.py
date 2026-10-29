"""Resumable native-runtime scoring. Search uses development; production uses frozen test."""
from __future__ import annotations
import argparse
import json
import time
from shared import BASE, HOME, configure, initial_complete, paused, atomic_json, read_json, sha256, run_dir, qualified, policy


def records(path):
    if not path.exists():
        return []
    output=[]
    # Recover only an interrupted final append; malformed interior lines are errors.
    with path.open("rb+") as handle:
        while True:
            start=handle.tell(); line=handle.readline()
            if not line: break
            try:
                output.append(json.loads(line))
                if not line.endswith(b"\n"):
                    handle.seek(0,2); handle.write(b"\n")
            except (ValueError,UnicodeDecodeError):
                if handle.read(1): raise
                handle.truncate(start)
                break
    return output


def summarize(items):
    import pandas as pd
    frame=pd.DataFrame(items)
    result={}
    for ds,part in frame.groupby("dataset"):
        # Equal source-utterance weight across views; sum error/reference counts per source.
        sources=part.groupby("source_group_id")[["word_errors","reference_words","character_errors","reference_characters"]].mean()
        words=float(sources.reference_words.sum())
        chars=float(sources.reference_characters.sum())
        result[ds]={"wer":float(sources.word_errors.sum()/words) if words else None,"cer":float(sources.character_errors.sum()/chars) if chars else None,"sources":len(sources),"clips":len(part),"rtf":float(part.wall_seconds.sum()/part.audio_seconds.sum())}
    macro=sum(x["wer"] for x in result.values() if x["wer"] is not None)/sum(x["wer"] is not None for x in result.values())
    quiet=frame[frame.get("audio_level",pd.Series("unknown",index=frame.index)).eq("quiet")]
    quiet_words=float(quiet.reference_words.sum())
    return {"macro_wer":macro,"datasets":result,"quiet_audio":{"clips":len(quiet),"reference_words":quiet_words,"wer":float(quiet.word_errors.sum()/quiet_words) if quiet_words else None},"mic_slices":{f"{ds}/{mic}":float(p.word_errors.sum()/p.reference_words.sum()) if p.reference_words.sum() else None for (ds,mic),p in frame.groupby(["dataset","mic_kind"])}}


def reuse_identical(folder, label, weights, identity, summaries):
    """Reuse a completed decode in this invocation on the same panel/runtime.

    Byte-identical weights only. No cross-run cache that could hide runtime,
    normalization or panel changes. Timing reuse is disclosed in the result.
    """
    from common import atomic_bytes
    for previous_label, summary in summaries.items():
        if summary["model_sha256"] != identity:
            continue
        target = folder / f"{label}.dev.jsonl"
        atomic_bytes(target, (folder / summary["predictions"]).read_bytes())
        atomic_bytes(folder / f"{label}.negative.jsonl", (folder / f"{previous_label}.negative.jsonl").read_bytes())
        return {**summary, "predictions":target.name, "weights":weights.name,
                "reused_identical_model_from":previous_label,
                "timing_note":"Reused from the identical model decoded in this invocation; not an independent timing measurement"}
    return None


def negative_probes(model, path, identity, scorer):
    """Twenty fixed, transcript-free probes; evaluation only, never training data."""
    import numpy as np
    previous=records(path)
    if any(r["model_sha256"]!=identity or r.get("probe_version")!=1 for r in previous):
        raise ValueError("Negative probe identity changed")
    done={r["item_id"] for r in previous}
    for duration in (3,5,10,20):
        for level in (None,-60,-40,-20, -10):
            item=f"{duration}s_{level}"
            if item in done: continue
            if paused(): return None
            rng=np.random.default_rng(policy()["seed"]+duration)
            wave=np.zeros(duration*16000,np.float32) if level is None else (rng.normal(size=duration*16000)*10**(level/20)).astype(np.float32)
            prediction=model.transcribe(wave,language="en")["text"]
            count=scorer("",prediction)["word_errors"]
            result={"item_id":item,"model_sha256":identity,"probe_version":1,"hypothesis":prediction,"inserted_words":count,"duration":duration,"rms_dbfs":level}
            with path.open("a",encoding="utf-8") as handle: handle.write(json.dumps(result)+"\n"); handle.flush()
            previous.append(result)
    return {"clips":len(previous),"false_positive_rate":sum(r["inserted_words"]>0 for r in previous)/len(previous),"inserted_words":sum(r["inserted_words"] for r in previous),"interpretation":"Fixed silence and generated Gaussian noise; not a guarantee on real product recordings"}


def main():
    import fcntl
    parser=argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("--baseline",action="store_true")
    parser.add_argument("--final",action="store_true")
    args=parser.parse_args()
    if not initial_complete(): raise RuntimeError("Original comparison is not complete")
    if paused(): return 75
    locks=[]
    for path in (BASE/"trainer.lock",HOME/"gpu.lock"):
        handle=path.open("a+b")
        try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return 73
        locks.append(handle)
    if args.baseline:
        folder=HOME/"baseline"; folder.mkdir(exist_ok=True)
    else:
        config,folder=configure(args.run)
    import common
    common.environment()
    import audio
    import pandas as pd
    import needle
    from evaluate import score,aggregate
    if args.final:
        if sha256(BASE/"evaluation.parquet")!=read_json(BASE/"evaluation_plan.json")["manifest_sha256"]:
            raise ValueError("Frozen comparison manifest changed")
        frame=pd.read_parquet(BASE/"evaluation.parquet")
        frame["text"]=frame.reference_text
        frame["source_group_id"]=frame.source_registry_row_id
        frame["cluster"]=frame.recording_id
        frame["mic_kind"]=frame.cohort
        frame["channel_index"]=0
    else:
        frame=pd.read_parquet(qualified("development"))
    if args.baseline:
        base4=folder/"whistle.base.w4a8.cact"
        if not base4.exists():
            from needle.model.whistle_finetune import load_base,WhistleTokenizer,build
            params,cfg=load_base(str(BASE/"assets/whistle.safetensors"))
            build(params,cfg,WhistleTokenizer(languages=cfg.languages),str(base4))
        models=[("base_w4a8",base4),("initial_best",BASE/"whistle.best.cact"),("initial_final",BASE/"whistle.final.cact")]
    else:
        models=[("best",folder/"whistle.best.cact"),("final",folder/"whistle.final.cact")]
        if args.final: models=[models[-1]]
    summaries={}
    panel_hash=sha256(BASE/"evaluation.parquet" if args.final else qualified("development"))
    for label,weights in models:
        path=folder/f"{label}.{'test' if args.final else 'dev'}.jsonl"
        identity=sha256(weights)
        previous=records(path)
        if any(r["model_sha256"]!=identity or r["panel_sha256"]!=panel_hash for r in previous):
            raise ValueError("Scoring model or panel changed after partial results")
        reused = None if args.final else reuse_identical(folder,label,weights,identity,summaries)
        if reused is not None:
            summaries[label] = reused
            continue
        done={r["item_id"] for r in previous}
        model=needle.Whistle(weights=str(weights))
        for number,row in enumerate(frame.to_dict("records")):
            if row["source_registry_row_id"] in done: continue
            if paused(): return 75
            wave=audio.load_audio(row)
            start=time.perf_counter()
            prediction=model.transcribe(wave,language="en")
            elapsed=time.perf_counter()-start
            result={"item_id":row["source_registry_row_id"],"source_group_id":row["source_group_id"],"cluster":row["cluster"],"dataset":row["dataset_id"],"mic_kind":row["mic_kind"],"audio_level":row.get("audio_level","not_measured"),"model_sha256":identity,"panel_sha256":panel_hash,"hypothesis":prediction["text"],"wall_seconds":elapsed,"audio_seconds":len(wave)/16000,"ttft_ms":prediction.get("ttft_ms"),**score(row["text"],prediction["text"])}
            with path.open("a",encoding="utf-8") as handle:
                handle.write(json.dumps(result,allow_nan=False)+"\n"); handle.flush()
            previous.append(result)
            if number%10==0:
                atomic_json(folder/"scoring_status.json",{"model":label,"completed":len(previous),"total":len(frame),"updated_at":time.time()})
        probes=negative_probes(model,folder/f"{label}.negative.jsonl",identity,score)
        if probes is None: return 75
        summaries[label]={**summarize(previous),"negative_probes":probes,"predictions":path.name,"weights":weights.name,"model_sha256":identity}
        if args.final:
            summaries[label]["matched_cohort_metrics"]=aggregate([{**r,"model":"whistle_production_final","cohort":r["mic_kind"]} for r in previous])
        del model
    selected=min(summaries,key=lambda k:summaries[k]["macro_wer"])
    output={"complete":True,"role":"frozen_test" if args.final else "development","models":summaries,"selected":selected,"panel_sha256":panel_hash,"normalization":"Whisper English text normalizer; same for every model","production":args.final,"real_product_validation_available":False,"independent_age_test_available":False if args.final else True}
    if args.final:
        comparison={"complete":True,"run":args.run,"panel_sha256":panel_hash,"metrics":read_json(BASE/"evaluation_summary.json")["metrics"]+summaries["final"]["matched_cohort_metrics"],"timing_comparison":"Whistle CPU timing is on this WSL host; historical GigaSpeech latency is not directly comparable","production_noise_probes":summaries["final"]["negative_probes"],"real_product_validation_available":False,"independent_age_test_available":False}
        atomic_json(folder/"matched_comparison.json",comparison)
        # The amended supervisor publishes a combined comparison only after both
        # preselected production identities are scored; never overwrite the first.
        from extension import plan as amendment_plan
        if not amendment_plan():
            atomic_json(HOME/"matched_comparison.json",comparison)
    atomic_json(folder/("test_scores.json" if args.final else "scores.json"),output)
    print(json.dumps(output,indent=2),flush=True)
    return 0


if __name__=="__main__": raise SystemExit(main())
