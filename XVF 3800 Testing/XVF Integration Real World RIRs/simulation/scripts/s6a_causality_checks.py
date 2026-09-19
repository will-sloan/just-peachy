"""Actual paced neural prefix and delivery checks. See README_s6a_causality_checks.md."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import psutil
from s6a_runtime_profile import atomic, identity, matches, process_tree_sample, sha, utc

NUMERIC_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
PREFIX_SEC = 12.0
SUFFIX_SEC = 6.0
TOLERANCE = 1e-5


def binding(path):
    path = Path(path)
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def events(worker):
    return [json.loads(line) for line in Path(worker["events_binding"]["path"]).read_text().splitlines()]


def comparison(a, b, tolerance=TOLERANCE):
    mismatches = []
    def walk(x, y, path):
        if len(mismatches) >= 12:
            return
        if isinstance(x, dict) and isinstance(y, dict):
            if set(x) != set(y):
                mismatches.append({"path": path, "kind": "keys", "a": sorted(x), "b": sorted(y)})
                return
            for k in sorted(x):
                walk(x[k], y[k], path + "." + k)
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                mismatches.append({"path": path, "kind": "length", "a": len(x), "b": len(y)})
            for i, (xx, yy) in enumerate(zip(x, y)):
                walk(xx, yy, path + "[" + str(i) + "]")
        elif isinstance(x, (int, float)) and not isinstance(x, bool) and isinstance(y, (int, float)) and not isinstance(y, bool):
            if not math.isfinite(x) or not math.isfinite(y):
                mismatches.append({"path": path, "kind": "nonfinite", "a": str(x), "b": str(y)})
            elif abs(x-y) > tolerance:
                mismatches.append({"path": path, "kind": "numeric", "a": x, "b": y})
        elif x != y:
            mismatches.append({"path": path, "kind": "value", "a": x, "b": y})
    walk(a, b, "$")
    return {"equivalent_within_tolerance": not mismatches, "a_count": len(a), "b_count": len(b),
            "numeric_absolute_tolerance": tolerance, "first_mismatches_max_12": mismatches}


def without_times(value):
    """Only remove enumerated measured/model-cost clocks, never labels or source spans."""
    excluded = {"wall_time_utc", "compute_ms", "compute_started_elapsed_sec", "compute_finished_elapsed_sec",
                "asr_decode_ms", "modeled_available_at_sec", "available_at_sec"}
    if isinstance(value, dict):
        return {key: without_times(item) for key, item in value.items() if key not in excluded}
    if isinstance(value, list):
        return [without_times(item) for item in value]
    return value


def prefix_checks(a, b):
    import numpy as np
    ea, eb = events(a), events(b)
    def rows(ev, name, prefix=True):
        return [e for e in ev if e["event_type"] == name and (not prefix or e["source_time_sec"] <= PREFIX_SEC)]
    def select(ev, names, keys):
        return [{"event_type": e["event_type"], "source_time_sec": e["source_time_sec"],
                 "payload": {k: e["payload"].get(k) for k in keys}}
                for e in ev if e["event_type"] in names and e["source_time_sec"] <= PREFIX_SEC]
    transcript_keys = ("text", "is_final", "utterance_index")
    display_keys = ("text", "display_text", "is_final", "utterance_index", "speaker", "speaker_state",
                    "overlap_detected", "label_revision_of", "first_display_is_preserved")
    raw = comparison(select(ea, {"transcript_partial","transcript_final"}, transcript_keys),
                     select(eb, {"transcript_partial","transcript_final"}, transcript_keys), 0)
    display = comparison(select(ea, {"transcript_partial","transcript_final"}, display_keys),
                         select(eb, {"transcript_partial","transcript_final"}, display_keys), 0)
    segmentation = comparison([without_times(e) for e in rows(ea,"research_segmentation")],
                              [without_times(e) for e in rows(eb,"research_segmentation")])
    dispatch_keys = ("source_start_sec", "source_end_sec", "native_endpoint", "advisory_endpoint", "reset_requested")
    dispatch = comparison(select(ea, {"research_asr_dispatch"}, dispatch_keys),
                          select(eb, {"research_asr_dispatch"}, dispatch_keys), 0)
    va = {e["source_time_sec"]: e["payload"] for e in rows(ea, "research_embedding")}
    vb = {e["source_time_sec"]: e["payload"] for e in rows(eb, "research_embedding")}
    common = sorted(set(va) & set(vb))
    unique_endpoints = len(va)==len(rows(ea,"research_embedding")) and len(vb)==len(rows(eb,"research_embedding"))
    span_keys = ("source_start_sec","source_end_sec","receptive_start_sec","receptive_end_sec")
    spans_exact = set(va)==set(vb) and all(tuple(va[t][k] for k in span_keys)==tuple(vb[t][k] for k in span_keys) for t in common)
    finite_vectors = all(np.all(np.isfinite(item["normalized_embedding"])) for item in list(va.values())+list(vb.values()))
    maxdiff = max((float(np.max(np.abs(np.asarray(va[t]["normalized_embedding"])-np.asarray(vb[t]["normalized_embedding"])))) for t in common), default=None)
    embed = {"a_count": len(va), "b_count": len(vb), "spans_exact": spans_exact, "unique_endpoints": unique_endpoints,
             "finite_vectors": bool(finite_vectors), "matched_vectors": len(common),
             "maximum_absolute_vector_difference": maxdiff, "numeric_absolute_tolerance": TOLERANCE,
             "equivalent_within_tolerance": bool(spans_exact and unique_endpoints and finite_vectors and maxdiff is not None and maxdiff <= TOLERANCE)}
    decision = comparison([without_times(va[t]["decision"]) for t in sorted(va)],
                          [without_times(vb[t]["decision"]) for t in sorted(vb)])
    prefix_rows = rows(ea,"research_embedding")+rows(eb,"research_embedding")+rows(ea,"research_segmentation")+rows(eb,"research_segmentation")
    receptive_ok = all(e["payload"]["receptive_end_sec"] <= PREFIX_SEC for e in prefix_rows)
    future_a = [without_times(e) for e in ea if e["event_type"]=="research_segmentation" and e["source_time_sec"]>PREFIX_SEC]
    future_b = [without_times(e) for e in eb if e["event_type"]=="research_segmentation" and e["source_time_sec"]>PREFIX_SEC]
    future_different = not comparison(future_a, future_b)["equivalent_within_tolerance"]
    return {"raw_asr_partial_and_final_sequence": raw, "native_endpoint_dispatch_sequence": dispatch,
            "segmentation_posteriors_and_gates": segmentation, "actual_redim_vectors": embed,
            "tracker_decisions_including_lineage": decision, "native_first_displayed_labels": display,
            "prefix_receptive_ends_at_or_before_cutoff": receptive_ok,
            "nonvacuity": {"prefix_has_raw_transcripts": raw["a_count"]>0, "prefix_has_embeddings": len(common)>0,
                           "different_future_changes_segmentation_outputs": future_different},
            "not_a_universal_causality_proof": True,
            "clock_exclusions": ["wall_time_utc","compute_ms","compute_started_elapsed_sec","compute_finished_elapsed_sec",
                                 "asr_decode_ms","modeled_available_at_sec","available_at_sec"],
            "scheduling_limit": "Actual concurrent speaker history availability can alter first labels even when audio features match. Model-cost clocks are reported in raw logs and intentionally excluded from semantic comparisons."}


def delivery_checks(runtime):
    data = json.loads((runtime/"RUNTIME_EXPERIMENT.json").read_text())
    results = {x: json.loads((runtime/x/"WORKER_RESULT.json").read_text()) for x in
               ("CPU_T1_D100","CPU_T1_D50","CPU_T2_D100","CPU_T2_D50")}
    pairs = []
    for a,b in (("CPU_T1_D100","CPU_T1_D50"),("CPU_T2_D100","CPU_T2_D50")):
        wa,wb=results[a],results[b]
        ea,eb=events(wa),events(wb)
        def stats(ev):
            ds=[e for e in ev if e["event_type"] in {"research_asr_dispatch","research_asr_tail_dispatch"}]
            spans=[(e["payload"]["source_start_sec"],e["payload"]["source_end_sec"]) for e in ds]
            ordered=sorted(spans)
            gaps=[{"previous_end":left[1],"next_start":right[0]} for left,right in zip(ordered,ordered[1:]) if abs(left[1]-right[0])>1e-8]
            return {"dispatch_count":len(spans),"unique_spans":len(set(spans)),
                    "contiguous_from_zero":bool(ordered) and ordered[0][0]==0 and not gaps,
                    "source_end_sec":ordered[-1][1] if ordered else None,"gaps_or_overlaps":gaps,
                    "native_endpoint_count":sum(bool(e["payload"].get("native_endpoint")) for e in ds),
                    "advisory_endpoint_count":sum(bool(e["payload"].get("advisory_endpoint")) for e in ds),
                    "final_utterance_count":sum(e["event_type"]=="transcript_final" for e in ev)}
        pairs.append({"a":a,"b":b,"a_delivery":stats(ea),"b_delivery":stats(eb),
                      "raw_final_utterances_exact":wa["final_texts"]==wb["final_texts"],
                      "concatenated_native_words_exact":" ".join(wa["final_texts"])==" ".join(wb["final_texts"]),
                      "native_pcm16_sha256_exact":wa["native_pcm16_binding"]["sha256"]==wb["native_pcm16_binding"]["sha256"],
                      "component_vector_parity":next(p for p in data["parity"] if p["a"]==a and p["b"]==b)})
    return {"status":"MEASURED","runtime_receipt":binding(runtime/"RUNTIME_EXPERIMENT.json"),"pairs":pairs,
            "claim":"Observed host-dispatch delivery comparison for this exact 89.390875 second waveform. Word equality is not a correctness/WER claim. Native endpoint polling semantics may differ for other inputs; no universal chunk invariance asserted."}


def launch(args, job, worker_script):
    out=args.output/job["job_id"]
    out.mkdir(exist_ok=True)
    complete=out/"COMPLETE.json"
    if complete.exists():
        previous=json.loads(complete.read_text())
        if previous["job_identity"]!=identity(job):
            raise RuntimeError("completed prefix job identity mismatch")
        return previous["worker"]
    argv=[sys.executable,str(worker_script),"--worker","--repo",str(args.repo),"--report",str(args.report),
          "--output",str(out),"--profile",job["profile"]["path"],"--input",job["input"]["path"],"--timeout","90"]
    owned={};samples=[];child=None;started=time.perf_counter()
    with (out/"stdout.log").open("a",encoding="utf-8") as log:
        try:
            child=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            process=psutil.Process(child.pid);created=process.create_time();owned[child.pid]=created
            atomic(out/"LAUNCH.json",{"pid":child.pid,"creation_time":created,"argv":argv,"job_identity":identity(job),"created_utc":utc()})
            print(json.dumps({"phase":"prefix_launch","job":job["job_id"],"pid":child.pid,"creation_time":created,"source_seconds":18}),flush=True)
            lastbeat=0
            while child.poll() is None:
                tree=process_tree_sample(process)
                for row in tree["processes"]:
                    owned[row["pid"]]=row["creation_time"]
                elapsed=time.perf_counter()-started
                samples.append({"elapsed_sec":elapsed,"tree":tree})
                if elapsed-lastbeat>=20:
                    atomic(args.output/"HEARTBEAT.json",{"created_utc":utc(),"job":job["job_id"],"elapsed_sec":elapsed,"owned":owned})
                    print(json.dumps({"phase":"prefix_heartbeat","job":job["job_id"],"elapsed_sec":elapsed}),flush=True)
                    lastbeat=elapsed
                if elapsed>160:
                    raise TimeoutError("prefix owned worker deadline")
                time.sleep(1)
            if child.wait(timeout=5)!=0:
                raise RuntimeError("prefix worker failed; inspect stdout.log")
            worker=json.loads((out/"WORKER_RESULT.json").read_text())
            if worker["status"]!="COMPLETE":
                raise RuntimeError("prefix worker has no complete receipt")
            for _ in range(20):
                if not any(matches(pid,c) for pid,c in owned.items()):
                    break
                time.sleep(.1)
            if any(matches(pid,c) for pid,c in owned.items()):
                raise RuntimeError("owned prefix child remains active")
            atomic(complete,{"status":"COMPLETE","created_utc":utc(),"job_identity":identity(job),"worker":worker,
                             "known_owned_processes":[{"pid":p,"creation_time":c} for p,c in owned.items()],
                             "owned_processes_closed":True,"samples":samples})
            return worker
        except BaseException:
            atomic(out/"FAILURE.json",{"created_utc":utc(),"traceback":traceback.format_exc(),"owned":owned})
            for pid,c in reversed(list(owned.items())):
                if matches(pid,c):
                    psutil.Process(pid).terminate()
            if child is not None:
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    for pid,c in reversed(list(owned.items())):
                        if matches(pid,c):psutil.Process(pid).kill()
                    child.wait(timeout=10)
            raise


def run(args):
    import numpy as np
    import soundfile as sf
    args.output.mkdir(parents=True,exist_ok=True)
    runtime=args.runtime
    rc=json.loads((runtime/"INPUT_CONTRACT.json").read_text())
    sources=rc["sources"]
    for source in sources:
        for name in ("native_pcm16", "receipt"):
            if sha(source[name]["path"]) != source[name]["sha256"]:
                raise RuntimeError("recorded input binding changed")
    a=np.fromfile(sources[0]["native_pcm16"]["path"],dtype="<i2")
    b=np.fromfile(sources[1]["native_pcm16"]["path"],dtype="<i2")
    n=round(PREFIX_SEC*16000);m=round(SUFFIX_SEC*16000)
    first=a[:n+m];second=np.concatenate([a[:n],b[:m]])
    if len(first)!=n+m or len(second)!=n+m or not np.array_equal(first[:n],second[:n]) or np.array_equal(first[n:],second[n:]):
        raise RuntimeError("prefix fixture inputs do not satisfy contract")
    app=args.repo/"Software Validation from Datasets/Evaluation Tool/app/edge_speech_pipeline"
    code={p.name:sha(p) for p in app.glob("*.py")}
    worker_script=Path(__file__).with_name("s6a_runtime_profile.py")
    profile=args.report/"profiles/P1X0.json"
    jobs=[]
    for name,wave in (("FUTURE_A",first),("FUTURE_B",second)):
        path=args.output/(name+".wav")
        expected=wave.astype(np.float32)/32768
        if not path.exists():sf.write(path,expected,16000,subtype="FLOAT")
        actual,rate=sf.read(path,dtype="float32")
        if rate!=16000 or not np.array_equal(actual,expected):
            raise RuntimeError("fixture prepared input mismatch")
        jobs.append({"job_id":name,"input":binding(path),"profile":binding(profile),"code":code,
                     "worker_runner":binding(worker_script),"test_runner":binding(__file__)})
    contract={"schema":"s6a_actual_neural_prefix_v1","created_utc":None,"jobs":jobs,"source_bindings":sources,
              "prefix_seconds":PREFIX_SEC,"different_future_seconds":SUFFIX_SEC,"prefix_pcm16_sha256":hashlib.sha256(first[:n].tobytes()).hexdigest(),
              "prefix_pcm16_bit_exact":True,"suffixes_differ":True,"source_selection":"same nontruth-selected lexical two-case runtime inputs",
              "predictor_inputs":"audio only; no reference text, speaker identity, scene truth, or XVF metadata",
              "numeric_environment":{k:os.environ[k] for k in NUMERIC_KEYS},
              "execution":"two fresh separate full native engines, true paced files, one resident worker at a time",
              "clock":"warm resident source-start timing; actual loading measured separately, no historical wall clock joins"}
    mp=args.output/"MANIFEST.json"
    if mp.exists() and identity(json.loads(mp.read_text()))!=identity(contract):
        raise RuntimeError("prefix manifest identity changed")
    if not mp.exists():atomic(mp,contract)
    current=psutil.Process();lock=args.output/"COORDINATOR.json"
    if lock.exists():
        old=json.loads(lock.read_text())
        if matches(old["pid"],old["creation_time"]):raise RuntimeError("prefix coordinator already active")
        lock.rename(args.output/("COORDINATOR_PREVIOUS_"+str(time.time_ns())+".json"))
    with lock.open("x",encoding="utf-8") as f:json.dump({"pid":current.pid,"creation_time":current.create_time(),"created_utc":utc()},f)
    print(json.dumps({"phase":"prefix_coordinator_identity","pid":current.pid,"creation_time":current.create_time(),"jobs":2}),flush=True)
    try:
        workers=[launch(args,job,worker_script) for job in jobs]
        native_arrays=[np.fromfile(w["native_pcm16_binding"]["path"],dtype="<i2") for w in workers]
        if not np.array_equal(native_arrays[0], first) or not np.array_equal(native_arrays[1], second):
            raise RuntimeError("native delivered samples differ from exact fixture inputs")
        if {p.name:sha(p) for p in app.glob("*.py")}!=code:
            raise RuntimeError("application source changed during prefix test")
        checks=prefix_checks(*workers)
        delivery=delivery_checks(runtime)
        core=all(checks[k]["equivalent_within_tolerance"] for k in
                 ("raw_asr_partial_and_final_sequence","native_endpoint_dispatch_sequence","segmentation_posteriors_and_gates","actual_redim_vectors","tracker_decisions_including_lineage"))
        nonvacuous=all(checks["nonvacuity"].values())
        receipt={"status":"COMPLETE","created_utc":utc(),"engineering_prefix_check_pass":core and nonvacuous and checks["prefix_receptive_ends_at_or_before_cutoff"],
                 "first_displayed_label_invariance_observed":checks["native_first_displayed_labels"]["equivalent_within_tolerance"],
                 "native_delivered_input_arrays_bit_exact":True,
                 "manifest":binding(mp),"checks":checks,"delivery":delivery,
                 "workers":[{"worker_receipt":binding(args.output/job["job_id"]/"WORKER_RESULT.json"),"events":w["events_binding"],
                             "source_seconds":w["source_duration_sec"],"embedding_count":w["embedding_count"],"final_utterance_count":w["final_utterance_count"]} for job,w in zip(jobs,workers)],
                 "limitations":["Two-file regression fixture, not proof over every future, source, or scheduling interleaving.",
                                "Real concurrent speaker/ASR workers can differ in which already-computed history is visible to a first display.",
                                "Paced desktop execution under concurrent study load; no CM5 throughput claim.",
                                "No neural weights or frozen application code changed by this test."],
                 "owned_workers_closed":True}
        atomic(args.output/"CAUSALITY_DELIVERY_RECEIPT.json",receipt)
        atomic(args.report/"CAUSALITY_DELIVERY_RECEIPT.json",receipt)
        atomic(args.output/"CLEANUP.json",{"status":"COMPLETE","created_utc":utc(),"coordinator_pid":current.pid,
                                         "coordinator_creation_time":current.create_time(),"owned_workers_closed":True})
        print(json.dumps({"phase":"prefix_complete","engineering_prefix_check_pass":receipt["engineering_prefix_check_pass"],
                          "first_displayed_label_invariance_observed":receipt["first_displayed_label_invariance_observed"],
                          "receipt":str(args.output/"CAUSALITY_DELIVERY_RECEIPT.json")}),flush=True)
    finally:
        if lock.exists():
            old=json.loads(lock.read_text())
            if old["pid"]==current.pid and old["creation_time"]==current.create_time():
                lock.rename(args.output/("COORDINATOR_FINISHED_"+str(time.time_ns())+".json"))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--runtime",type=Path,required=True)
    args=p.parse_args()
    for key in NUMERIC_KEYS:os.environ[key]="1"
    run(args)


if __name__=="__main__":main()
