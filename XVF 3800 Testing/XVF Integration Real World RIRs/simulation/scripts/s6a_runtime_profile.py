"""Paced full-pipeline CPU experiment; see README_s6a_runtime_profile.md."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid
import psutil

NUMERIC_ENVIRONMENT_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def utc(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def identity(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def atomic(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name("."+path.name+"."+uuid.uuid4().hex+".tmp")
    with temp.open("x",encoding="utf-8") as handle:
        json.dump(value,handle,indent=2,allow_nan=False);handle.flush();os.fsync(handle.fileno())
    for attempt in range(4):
        try:os.replace(temp,path);break
        except OSError as exc:
            if getattr(exc,"winerror",None) not in {5,32,33} or attempt==3:raise
            time.sleep(.02*(2**attempt))


def matches(pid,creation):
    try:return abs(psutil.Process(pid).create_time()-creation)<.001
    except psutil.Error:return False


def process_tree_sample(process):
    rows=[]
    candidates=[process]
    try:candidates+=process.children(recursive=True)
    except psutil.Error:pass
    for item in candidates:
        try:
            m=item.memory_full_info();c=item.cpu_times();io=item.io_counters()
            rows.append({"pid":item.pid,"creation_time":item.create_time(),"name":item.name(),"rss_bytes":m.rss,"private_resident_uss_bytes":getattr(m,"uss",None),
                         "windows_private_commit_bytes":getattr(m,"private",None),"thread_count":item.num_threads(),
                         "cpu_seconds":c.user+c.system,"io_read_bytes":io.read_bytes,"io_write_bytes":io.write_bytes})
        except psutil.Error:continue
    rss=sum(x["rss_bytes"] for x in rows)
    uss=sum(x["private_resident_uss_bytes"] or 0 for x in rows)
    return {"processes":rows,"rss_sum_upper_bound_bytes":rss,"private_resident_uss_sum_bytes":uss,
            "shared_resident_nonunique_estimate_bytes":max(0,rss-uss),
            "windows_private_commit_sum_bytes":sum(x["windows_private_commit_bytes"] or 0 for x in rows),
            "cpu_seconds":sum(x["cpu_seconds"] for x in rows),"io_write_bytes":sum(x["io_write_bytes"] for x in rows),
            "available_system_ram_bytes":psutil.virtual_memory().available,"system_cpu_percent":psutil.cpu_percent(interval=None)}


def worker(args):
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    proc=psutil.Process()
    numeric_environment={key:os.environ.get(key) for key in NUMERIC_ENVIRONMENT_KEYS}
    if any(value!="1" for value in numeric_environment.values()):
        raise RuntimeError("controlled runtime requires explicit single-thread numeric libraries before imports")
    atomic(out/"WORKER_IDENTITY.json",{"pid":proc.pid,"creation_time":proc.create_time(),"created_utc":utc(),"argv":sys.argv,"numeric_environment":numeric_environment})
    sys.path.insert(0,str(args.repo/"Software Validation from Datasets/Evaluation Tool/app"))
    from edge_speech_pipeline.config import PipelineConfig
    from edge_speech_pipeline.research_profiles import ResearchProfile
    from edge_speech_pipeline.runtime import PipelineEngine
    import numpy as np
    profile=ResearchProfile.load(args.profile)
    started=time.perf_counter()
    engine=PipelineEngine(PipelineConfig(session_root=out/"sessions",profile_root=out/"empty_gallery"),research_profile=profile)
    session=engine.start_file(args.input,realtime=True)
    launch_sec=time.perf_counter()-started
    counts=Counter();model_ms=Counter();source_started_elapsed=None
    last_beat=0.0
    while engine.state not in {"COMPLETED","FAILED"}:
        while not engine.events.empty():
            event=engine.events.get()
            counts[event.event_type]+=1
            if event.event_type=="source_started":source_started_elapsed=time.perf_counter()-started
            if event.event_type in {"research_asr_dispatch","research_asr_tail_dispatch","research_asr_drain","research_segmentation","research_embedding"}:
                model_ms[event.event_type]+=float(event.payload.get("compute_ms",0))
        elapsed=time.perf_counter()-started
        atomic(out/"LIVE.json",{"created_utc":utc(),"elapsed_sec":elapsed,"telemetry":engine.telemetry(),"counts":dict(counts),"model_ms":dict(model_ms),"launch_sec":launch_sec,"source_started_elapsed_sec":source_started_elapsed})
        if elapsed-last_beat>=20:
            print(json.dumps({"phase":"paced_worker","elapsed_sec":elapsed,"source":engine.telemetry()["source_duration_sec"],"asr_cursor":engine.telemetry()["asr_cursor_sec"],"speaker_cursor":engine.telemetry()["speaker_cursor_sec"]}),flush=True)
            last_beat=elapsed
        if elapsed>args.timeout:
            engine.stop()
            raise TimeoutError("bounded paced worker timeout")
        time.sleep(.25)
    engine.wait_for_completion(timeout=65)
    while not engine.events.empty():
        event=engine.events.get();counts[event.event_type]+=1
    summary=json.loads((session/"session_summary.json").read_text())
    if summary["state"]!="COMPLETED":raise RuntimeError("native pipeline failed")
    events=[json.loads(line) for line in (session/"events.jsonl").read_text().splitlines()]
    finals=[r["payload"] for r in events if r["event_type"]=="transcript_final"]
    features=[r["payload"] for r in events if r["event_type"]=="research_embedding"]
    seg=[r["payload"] for r in events if r["event_type"]=="research_segmentation"]
    actual_duration=summary["telemetry"]["source_duration_sec"]
    assert summary["telemetry"]["audio_frames_dropped"]==0
    assert abs(summary["telemetry"]["asr_cursor_sec"]-actual_duration)<1e-8
    modelcost={name:sum(float(e["payload"].get("compute_ms",0)) for e in events if e["event_type"]==name) for name in ("research_asr_dispatch","research_asr_tail_dispatch","research_asr_drain","research_segmentation","research_embedding")}
    modelcost["punctuation"]=summary["telemetry"]["punctuation_total_ms"]
    result={"status":"COMPLETE","created_utc":utc(),"pid":proc.pid,"creation_time":proc.create_time(),"elapsed_sec":time.perf_counter()-started,
            "launch_sec":launch_sec,"source_started_elapsed_sec":source_started_elapsed,"source_duration_sec":actual_duration,"summary":summary,
            "session_dir":str(session),"events_binding":{"path":str(session/"events.jsonl"),"sha256":sha(session/"events.jsonl")},
            "native_pcm16_binding":{"path":str(session/"audio_spool.pcm16"),"sha256":sha(session/"audio_spool.pcm16")},
            "final_texts":[f["text"] for f in finals],"final_utterance_count":len(finals),"embedding_count":len(features),"segmentation_count":len(seg),
            "model_compute_ms":modelcost,"resident_model_instances":{"sherpa_recognizer":1,"pyannote":1,"redim":1,"punctuation":1},
            "full_feature_vectors_in_native_event_log_only":True,"no_hardware_access":True,"metadata_influence":False,"numeric_environment":numeric_environment}
    atomic(out/"WORKER_RESULT.json",result)
    print(json.dumps({"phase":"worker_complete","elapsed_sec":result["elapsed_sec"],"source_duration_sec":actual_duration}),flush=True)


def prepare(args):
    import numpy as np
    import soundfile as sf
    root=args.output;root.mkdir(parents=True,exist_ok=True)
    panel=json.loads((args.report/"PROBE_PANEL.json").read_text())
    selected=sorted(panel["case_ids"])[:2]
    s5=args.report.parents[1]/"S5/20260909T130308Z"
    pieces=[];bindings=[]
    for case in selected:
        receipt_path=s5/"h2"/case/"O0/run_receipt.json"
        receipt=json.loads(receipt_path.read_text())
        if receipt["status"]!="COMPLETE":raise RuntimeError("input baseline incomplete")
        pcm=Path(receipt["session_dir"])/"audio_spool.pcm16"
        samples=np.fromfile(pcm,dtype="<i2")
        pieces.append(samples)
        bindings.append({"case_id":case,"native_pcm16":{"path":str(pcm),"sha256":sha(pcm),"samples":len(samples)},"receipt":{"path":str(receipt_path),"sha256":sha(receipt_path)}})
    joined=np.concatenate(pieces)
    if not 60<=len(joined)/16000<=90:raise RuntimeError("deterministic first two input duration outside planned60..90s")
    wav=root/"paced_input.wav"
    if not wav.exists():sf.write(wav,joined.astype(np.float32)/32768,16000,subtype="FLOAT")
    observed,rate=sf.read(wav,dtype="float32")
    if rate!=16000 or not np.array_equal(observed,joined.astype(np.float32)/32768):raise RuntimeError("prepared input mismatch")
    app=args.repo/"Software Validation from Datasets/Evaluation Tool/app/edge_speech_pipeline"
    code={p.name:sha(p) for p in app.glob("*.py")}
    input_contract={"selection":"lexically first two preselected36-panel O0 native journals; exact whole inputs concatenated","sources":bindings,"samples":len(joined),"duration_sec":len(joined)/16000,"gain":"already historicalO0+3dB; readunity","input_path":str(wav),"input_sha256":sha(wav),"scope":"paced runtime engineering; artificial file boundary, no accuracy/generalization claims"}
    atomic(root/"INPUT_CONTRACT.json",input_contract)
    sys.path.insert(0,str(app.parent))
    from edge_speech_pipeline.research_profiles import ResearchProfile
    jobs=[]
    for threads,dispatch in [(1,100),(2,100),(2,50),(1,50)]:
        name=f"CPU_T{threads}_D{dispatch}"
        profile=ResearchProfile.from_dict({"profile_id":name,"input":{"tap":"O0","gain":1.0,"already_gained":True},"asr":{"journal_read_ms":dispatch},"tracker":{"mode":"voice_time"},"runtime":{"asr_threads":threads,"speaker_threads":threads,"punctuation_threads":1},"xvf":{"mode":"none"}})
        pp=root/(name+".json")
        expected=json.dumps(profile.to_dict(),indent=2)
        if pp.exists() and pp.read_text()!=expected:raise RuntimeError("profile resume mismatch")
        if not pp.exists():pp.write_text(expected,encoding="utf-8")
        jobs.append({"job_id":name,"threads":threads,"dispatch_ms":dispatch,"profile_path":str(pp),"profile_sha256":profile.digest(),"input_sha256":input_contract["input_sha256"],"code":code,"runner_sha256":sha(__file__)})
    manifest={"schema":"s6a_paced_cpu_v2","input":input_contract,"jobs":jobs,"host":{"cpu_count_logical":psutil.cpu_count(),"platform":sys.platform},"numeric_environment":{key:os.environ.get(key) for key in NUMERIC_ENVIRONMENT_KEYS},"scope":"one worker sequentially; full paced application tree under concurrent desktop research load; OMP/OpenBLAS/MKL/NumExpr explicitly limited to one thread"}
    mp=root/"MANIFEST.json"
    if mp.exists() and identity(json.loads(mp.read_text()))!=identity(manifest):raise RuntimeError("manifest resume identity changed")
    if not mp.exists():atomic(mp,manifest)
    return manifest


def aggregate(args,manifest):
    import numpy as np
    results={}
    rows=[]
    for job in manifest["jobs"]:
        out=args.output/job["job_id"]
        r=json.loads((out/"COMPLETE.json").read_text());results[job["job_id"]]=r
        s=r["worker"];samples=r["samples"]
        active=[x for x in samples if x.get("live") and x["live"]["telemetry"]["source_duration_sec"]>1]
        def peak(key):return max((x["tree"][key] for x in samples),default=0)
        def backlog(key):
            values=[max(0.,x["live"]["telemetry"]["source_duration_sec"]-x["live"]["telemetry"][key]) for x in active]
            return {"max":max(values,default=0),"p95":float(np.percentile(values,95)) if values else None,"median":float(np.median(values)) if values else None,"last":values[-1] if values else None}
        first=samples[0]["tree"];last=samples[-1]["tree"]
        appcpu=max(0,last["cpu_seconds"]-first["cpu_seconds"])
        writes=max(0,last["io_write_bytes"]-first["io_write_bytes"])
        row={"job_id":job["job_id"],"threads":job["threads"],"dispatch_ms":job["dispatch_ms"],"input_duration_sec":s["source_duration_sec"],"elapsed_sec":s["elapsed_sec"],
             "startup_sec":s["launch_sec"],"model_compute_sec":sum(s["model_compute_ms"].values())/1000,"process_cpu_sec_sampled":appcpu,
             "cpu_average_one_core_percent":100*appcpu/max(.001,s["elapsed_sec"]),"peak_rss_sum_upper_bound_bytes":peak("rss_sum_upper_bound_bytes"),
             "peak_private_resident_uss_sum_bytes":peak("private_resident_uss_sum_bytes"),"peak_shared_resident_nonunique_estimate_bytes":peak("shared_resident_nonunique_estimate_bytes"),
             "peak_windows_private_commit_sum_bytes":peak("windows_private_commit_sum_bytes"),
             "minimum_system_available_ram_bytes":min(x["tree"]["available_system_ram_bytes"] for x in samples),
             "io_write_bytes_sampled":writes,"io_write_bytes_per_audio_sec":writes/s["source_duration_sec"],"asr_backlog_sec":backlog("asr_cursor_sec"),"speaker_backlog_sec":backlog("speaker_cursor_sec"),
             "model_calls":s["embedding_count"]+s["segmentation_count"],"embedding_count":s["embedding_count"],"segmentation_count":s["segmentation_count"],"final_utterance_count":s["final_utterance_count"],
             "no_drops":s["summary"]["telemetry"]["audio_frames_dropped"]==0,"owned_process_closed":r["process_closed"],"samples":len(samples),
             "peak_observed_tree_threads":max(sum(y["thread_count"] for y in x["tree"]["processes"]) for x in samples),"numeric_environment":s["numeric_environment"]}
        rows.append(row)
    parity=[]
    for a,b in [("CPU_T1_D100","CPU_T2_D100"),("CPU_T1_D50","CPU_T2_D50"),("CPU_T1_D100","CPU_T1_D50"),("CPU_T2_D100","CPU_T2_D50")]:
        wa=results[a]["worker"];wb=results[b]["worker"]
        def features(w):
            ev=[json.loads(line) for line in Path(w["events_binding"]["path"]).read_text().splitlines()]
            return {r["source_time_sec"]:np.asarray(r["payload"]["normalized_embedding"],dtype=np.float32) for r in ev if r["event_type"]=="research_embedding"}
        va=features(wa);vb=features(wb);common=set(va)&set(vb)
        maximum=max((float(np.max(np.abs(va[t]-vb[t]))) for t in common),default=None)
        minimum_cos=min((float(va[t]@vb[t]) for t in common),default=None)
        parity.append({"a":a,"b":b,"raw_final_texts_exact":wa["final_texts"]==wb["final_texts"],"all_words_concat_exact":" ".join(wa["final_texts"])==" ".join(wb["final_texts"]),"embedding_spans_exact":set(va)==set(vb),"matched_vectors":len(common),"maximum_absolute_vector_difference":maximum,"minimum_vector_cosine":minimum_cos,"numerical_tolerance_pass":maximum is not None and maximum<=1e-4,"native_pcm16_exact":wa["native_pcm16_binding"]["sha256"]==wb["native_pcm16_binding"]["sha256"],"label_race_parity_not_claimed":True})
    final={"status":"COMPLETE","created_utc":utc(),"rows":rows,"parity":parity,"scope":manifest["scope"],"numeric_environment":manifest["numeric_environment"],"memory_semantics":{"rss_sum":"upper bound; shared pages can be counted repeatedly","uss_sum":"unique private resident pages only; excludes shared resident pages","shared_estimate":"RSS-USS per tree, nonunique; PSS unavailable on this Windows host","windows_private_commit":"committed private virtual memory, not resident RAM; do not compare directly to CM5 physical headroom"},"target_claim":"desktop CPU evidence only; no ARM64/CM5 throughput, temperature or 2 GB fit qualification","input":manifest["input"]}
    atomic(args.output/"RUNTIME_EXPERIMENT.json",final)
    atomic(args.report/"RUNTIME_EXPERIMENT.json",final)
    return final


def coordinator(args):
    manifest=prepare(args)
    lock=args.output/"COORDINATOR.json"
    if lock.exists():
        previous=json.loads(lock.read_text())
        if matches(previous["pid"],previous["creation_time"]):raise RuntimeError("another runtime coordinator owns this run")
        lock.rename(args.output/("COORDINATOR_PREVIOUS_"+str(time.time_ns())+".json"))
    current=psutil.Process()
    with lock.open("x",encoding="utf-8") as handle:json.dump({"pid":current.pid,"creation_time":current.create_time(),"created_utc":utc()},handle)
    print(json.dumps({"phase":"coordinator_identity","pid":current.pid,"creation_time":current.create_time(),"input_seconds":manifest["input"]["duration_sec"],"jobs":4}),flush=True)
    try:
        for idx,job in enumerate(manifest["jobs"]):
            out=args.output/job["job_id"];out.mkdir(exist_ok=True)
            complete=out/"COMPLETE.json"
            if complete.exists():
                previous=json.loads(complete.read_text())
                if previous["job_identity"]!=identity(job):raise RuntimeError("completejob identity mismatch")
                print(json.dumps({"phase":"reuse","job":job["job_id"]}),flush=True);continue
            argv=[sys.executable,str(Path(__file__).resolve()),"--worker","--repo",str(args.repo),"--report",str(args.report),"--output",str(out),"--profile",job["profile_path"],"--input",manifest["input"]["input_path"],"--timeout",str(args.timeout)]
            owned={};samples=[];started=time.perf_counter()
            with (out/"stdout.log").open("a",encoding="utf-8") as log:
                child=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                try:
                    process=psutil.Process(child.pid);creation=process.create_time();owned[child.pid]=creation
                    atomic(out/"LAUNCH.json",{"pid":child.pid,"creation_time":creation,"argv":argv,"job_identity":identity(job),"created_utc":utc()})
                    print(json.dumps({"phase":"launch","job":job["job_id"],"pid":child.pid,"creation_time":creation,"planned_source_seconds":manifest["input"]["duration_sec"]}),flush=True)
                    lastbeat=0
                    while child.poll() is None:
                        tree=process_tree_sample(process)
                        for item in tree["processes"]:owned[item["pid"]]=item["creation_time"]
                        live=None
                        if (out/"LIVE.json").exists():
                            try:live=json.loads((out/"LIVE.json").read_text())
                            except (ValueError,OSError):pass
                        elapsed=time.perf_counter()-started
                        samples.append({"elapsed_sec":elapsed,"created_utc":utc(),"tree":tree,"live":live,"coordinator_rss_bytes":current.memory_info().rss})
                        if elapsed-lastbeat>=20:
                            atomic(args.output/"HEARTBEAT.json",{"phase":"paced_full_pipeline","job":job["job_id"],"completed_jobs":idx,"elapsed_job_sec":elapsed,"latest":samples[-1]})
                            print(json.dumps({"phase":"heartbeat","job":job["job_id"],"elapsed_sec":elapsed,"private_resident_uss":tree["private_resident_uss_sum_bytes"],"source_sec":live["telemetry"]["source_duration_sec"] if live else 0}),flush=True)
                            lastbeat=elapsed
                        if elapsed>args.timeout+70:raise TimeoutError("coordinator boundedworker deadline")
                        time.sleep(1)
                    code=child.wait(timeout=5)
                    if code!=0:raise RuntimeError("worker exit"+str(code))
                    result=json.loads((out/"WORKER_RESULT.json").read_text())
                    if result["status"]!="COMPLETE":raise RuntimeError("worker no complete receipt")
                    for _ in range(20):
                        if not any(matches(pid,created) for pid,created in owned.items()):break
                        time.sleep(.1)
                    if any(matches(pid,created) for pid,created in owned.items()):raise RuntimeError("an owned process or child remains active after worker exit")
                    atomic(complete,{"status":"COMPLETE","job_identity":identity(job),"worker":result,"samples":samples,"process_closed":True,"known_owned_processes":[{"pid":pid,"creation_time":c} for pid,c in owned.items()],"created_utc":utc()})
                except BaseException:
                    atomic(out/"FAILURE.json",{"created_utc":utc(),"traceback":traceback.format_exc(),"owned":owned,"samples":samples})
                    for pid,c in reversed(list(owned.items())):
                        if matches(pid,c):psutil.Process(pid).terminate()
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        for pid,c in reversed(list(owned.items())):
                            if matches(pid,c):psutil.Process(pid).kill()
                        child.wait(timeout=10)
                    raise
        final=aggregate(args,manifest)
        atomic(args.output/"CLEANUP.json",{"created_utc":utc(),"status":"COMPLETE","owned_children_closed":True,"coordinator_pid":current.pid,"coordinator_creation_time":current.create_time(),"jobs":4})
        print(json.dumps({"phase":"complete","output":str(args.output/"RUNTIME_EXPERIMENT.json"),"jobs":len(final["rows"])}),flush=True)
    finally:
        if lock.exists():
            record=json.loads(lock.read_text())
            if record["pid"]==current.pid and record["creation_time"]==current.create_time():
                lock.rename(args.output/("COORDINATOR_FINISHED_"+str(time.time_ns())+".json"))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True);p.add_argument("--report",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--worker",action="store_true");p.add_argument("--profile",type=Path);p.add_argument("--input",type=Path);p.add_argument("--timeout",type=float,default=180)
    args=p.parse_args()
    # Set before NumPy/SciPy/application import in both coordinator and worker.
    for name in NUMERIC_ENVIRONMENT_KEYS:
        os.environ[name]="1"
    return worker(args) if args.worker else coordinator(args)
if __name__=="__main__":main()
