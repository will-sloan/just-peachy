"""Score the three native D1 profiles from bound saved receipts; see README.md."""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re

for _key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[_key]="1"

import numpy as np

from prepare import HERE,bind,fingerprint,load,sha
from score_runtime import lines,merge_segments
from scoring import activity_metrics,turn_coverage
from summarize_screen import DEFAULT_TRUTH,activity_aggregate,save,sum_numbers

PROFILES=("low_latency","very_low_latency","ultra_low_latency")
THRESHOLD=0.5


def verify(binding):
    if Path(binding["path"]).stat().st_size!=binding["bytes"] or sha(binding["path"])!=binding["sha256"]:
        raise ValueError("Bound native evidence changed")


def distribution(values):
    return {"count":len(values),"sum":float(np.sum(values)) if values else None,
            "minimum":min(values) if values else None,"median":float(np.median(values)) if values else None,
            "p95":float(np.quantile(values,.95)) if values else None,"maximum":max(values) if values else None}


def normalize_jobs(runtime_jobs,expected):
    """Permit only the historical scheduler-ID prefix, with identical audio jobs."""
    aliases={}
    for original,job in runtime_jobs.items():
        canonical="N2_"+original.removeprefix("N1_BASELINE_") if re.fullmatch(r"N1_BASELINE_S45_\d{2}_\d{2}_O[01]",original) else original
        if job["job_id"]!=original or canonical not in expected or dict(job,job_id=canonical)!=expected[canonical]:
            raise ValueError("Native source job differs beyond the allowed scheduler-ID alias")
        aliases[original]=canonical
    if len(set(aliases.values()))!=len(aliases) or set(aliases.values())!=set(expected):raise ValueError("Native scheduler aliases do not cover the exact fixed96 population")
    return aliases


def score_native_probability(values,step,availability,truth):
    """Keep raw frames; score only each frame's actual delivered-waveform support."""
    duration=truth["frames"]/16000
    if values.ndim!=2 or values.shape[1]!=8 or not np.isfinite(values).all() or np.any(values<0) or np.any(values>1):
        raise ValueError("Native probability array must be finite [frames,8] in [0,1]")
    if not np.isfinite(step) or step<=0:raise ValueError("Invalid native frame cadence")
    cursor=0;received=0.;overhang=0.;segments=[];compute=[];delay=[];lookahead=[];capacity_seconds=0.;maximum_active=0
    for event in availability:
        start,end=event["frame_start"],event["frame_end"]
        if start!=cursor or type(start) is not int or type(end) is not int or not start<=end<=len(values):raise ValueError("Native availability has a gap, repeat or invalid range")
        supplied=event["audio_received_sec"]
        if not received<=supplied<=duration+1e-8:raise ValueError("Native availability input support is not monotone/in bounds")
        received=supplied;cursor=end
        if event["compute_sec"]<0:raise ValueError("Negative native compute time")
        compute.append(event["compute_sec"])
        delay.append(event["available_at_elapsed_sec"]-event["received_at_elapsed_sec"])
        if delay[-1]<0:raise ValueError("Availability precedes actual receipt")
        for index in range(start,end):
            a=index*step;b=a+step;supported_end=min(duration,supplied)
            overhang+=max(0,b-max(a,supported_end))
            if a>=supported_end:continue
            b=min(b,supported_end)
            active=np.flatnonzero(values[index]>=THRESHOLD)
            maximum_active=max(maximum_active,len(active))
            capacity_seconds+=(b-a) if len(active)==8 else 0
            lookahead.append(max(0,supplied-b))
            segments.extend({"start":a,"end":b,"label":str(slot)} for slot in active)
    if cursor!=len(values) or abs(received-duration)>1e-8 or not availability or availability[-1]["is_final"] is not True:
        raise ValueError("Native final availability does not cover every raw frame and delivered sample")
    predictions=merge_segments(segments)
    references=[{"start":a/16000,"end":b/16000,"label":t["identity"]} for t in truth["turns"] for a,b in t["activity_ranges_samples_estimated"]]
    metrics={str(collar):activity_metrics(references,predictions,duration,complete_reference=truth["complete_reference"],collar_s=collar) for collar in [0,0.25]}
    coverage=turn_coverage(truth["turns"],predictions,[])
    for key in ["embedding_calls","unique_evidence_wall_seconds","windows_with_multiple_reference_identities","turns_without_evidence","short_turns_without_evidence","mapped_turns_evaluator_only"]:coverage.pop(key,None)
    coverage.update({k:0 for k in ["source_turns_without_native_activity","short_turns_without_native_activity","source_turn_activity_seconds_sum","source_turn_activity_with_native_activity_seconds_sum"]})
    union=merge_segments([dict(r,label="any") for r in predictions])
    for turn in truth["turns"]:
        spans=[(a/16000,b/16000) for a,b in turn["activity_ranges_samples_estimated"]]
        active=sum(b-a for a,b in spans)
        covered=sum(max(0,min(b,p["end"])-max(a,p["start"])) for a,b in spans for p in union)
        coverage["source_turns_without_native_activity"]+=covered==0
        coverage["short_turns_without_native_activity"]+=active<=1.5 and covered==0
        coverage["source_turn_activity_seconds_sum"]+=active
        coverage["source_turn_activity_with_native_activity_seconds_sum"]+=covered
    coverage["scope"]="maximum estimated-reference intersection per fixed native slot; ties unresolved; known references only in incomplete ambient scenes"
    return {"activity":metrics["0"],"activity_collar_0p25_sensitivity":metrics["0.25"],"coverage":coverage,
            "capacity":{"reference_unique_speakers":len({t["identity"] for t in truth["turns"]}),"reference_exceeds_eight_unique_speakers":len({t["identity"] for t in truth["turns"]})>8,
                        "native_slots_active_anywhere":len({s["label"] for s in predictions}),"maximum_simultaneously_active_slots":maximum_active,
                        "seconds_all_eight_slots_active":capacity_seconds,"scope":"fixed eight-slot capacity and 0.5 heuristic activity; saturation is not proof of a ninth voice or identity confidence"},
            "frame_support":{"raw_native_frames":len(values),"raw_native_endpoint_sec":len(values)*step,"audio_seconds":duration,
                             "native_waveform_overhang_seconds":overhang,"raw_endpoint_minus_waveform_seconds":len(values)*step-duration},
            "availability":{"recorded_push_and_finish_calls":len(availability),"calls_emitting_frames":sum(e["frame_end"]>e["frame_start"] for e in availability),
                            "compute_seconds":distribution(compute),"receipt_to_available_seconds":distribution(delay),
                            "per_frame_supplied_source_lookahead_seconds":distribution(lookahead),
                            "physical_latency":"NOT_MEASURED_ACCELERATED_CAUSAL_INPUT"},
            "naming_and_embedding_evidence":"NOT_RUN_PURE_DIARIZER","transcript_metrics":"NOT_RUN_NO_ASR"}


def aggregate(cells):
    rows=[c["score"] for c in cells]
    rss=[c["sampled_peak_rss_bytes"] for c in cells if c["sampled_peak_rss_bytes"] is not None]
    lifetime=[c["worker_lifetime_peak_wset_bytes"] for c in cells if c["worker_lifetime_peak_wset_bytes"] is not None]
    wall=sum(c["wall_sec"] for c in cells);audio=sum(c["audio_seconds"] for c in cells);cpu=sum(c["process_cpu_sec"] for c in cells)
    return {"scored_cells":len(cells),"reference_classes":dict(Counter(c["reference_class"] for c in cells)),
            "activity_primary_collar0":activity_aggregate(rows,"activity"),"activity_collar_0p25_sensitivity":activity_aggregate(rows,"activity_collar_0p25_sensitivity"),
            "activity_primary_by_reference_class":{kind:activity_aggregate([c["score"] for c in cells if c["reference_class"]==kind],"activity") for kind in sorted({c["reference_class"] for c in cells})},
            "activity_sensitivity_by_reference_class":{kind:activity_aggregate([c["score"] for c in cells if c["reference_class"]==kind],"activity_collar_0p25_sensitivity") for kind in sorted({c["reference_class"] for c in cells})},
            "turn_coverage":sum_numbers([r["coverage"] for r in rows]),
            "turn_coverage_by_reference_class":{kind:sum_numbers([c["score"]["coverage"] for c in cells if c["reference_class"]==kind]) for kind in sorted({c["reference_class"] for c in cells})},
            "capacity":{"cells_at_eight_simultaneous_active_slots":sum(r["capacity"]["maximum_simultaneously_active_slots"]==8 for r in rows),
                        "maximum_simultaneously_active_slots":max((r["capacity"]["maximum_simultaneously_active_slots"] for r in rows),default=None),
                        "seconds_all_eight_slots_active":sum(r["capacity"]["seconds_all_eight_slots_active"] for r in rows),
                        "reference_exceeds_eight_unique_speaker_cells":sum(r["capacity"]["reference_exceeds_eight_unique_speakers"] for r in rows)},
            "frame_support":sum_numbers([r["frame_support"] for r in rows]),
            "resources":{"audio_seconds":audio,"native_cell_wall_seconds":wall,"native_process_cpu_seconds":cpu,
                         "accelerated_wall_RTF":wall/audio if audio else None,"process_CPU_seconds_per_audio_second":cpu/audio if audio else None,
                         "maximum_sampled_process_rss_bytes":max(rss) if rss else None,"rss_measured_cells":len(rss),
                         "maximum_worker_lifetime_peak_wset_bytes":max(lifetime) if lifetime else None,"lifetime_peak_scope":"worker lifetime watermark; not per-cell incremental peak",
                         "push_and_finish_calls":sum(r["availability"]["recorded_push_and_finish_calls"] for r in rows),
                         "calls_emitting_frames":sum(r["availability"]["calls_emitting_frames"] for r in rows),
                         "summed_call_compute_seconds":sum(r["availability"]["compute_seconds"]["sum"] or 0 for r in rows),
                         "maximum_call_compute_seconds":max((r["availability"]["compute_seconds"]["maximum"] for r in rows),default=None),
                         "input_queue_limit":1,"resident_model_load_included":False,"GPU_memory_measured":False,
                         "scope":"accelerated causal native-only process; CPU support/RSS measured, CUDA device measurements separate; no ASR, embeddings, policy, GUI, playback, Pi or total-system2GB claim"}}


def summarize(index_path,truth_path,out_dir,public_dir):
    index_path=Path(index_path);index_bytes=index_path.read_bytes();index=json.loads(index_bytes.decode("utf-8-sig"));admission=load(index_path.with_name("ADMISSION.json"));contract=admission["contract"]
    index_snapshot=Path(out_dir)/"INPUT_RESULT_INDEX_SNAPSHOT.json";index_snapshot.parent.mkdir(parents=True,exist_ok=True);index_snapshot.write_bytes(index_bytes)
    native_hash=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    if native_hash!=admission["contract_sha256"] or index["contract_sha256"]!=native_hash:raise ValueError("Native index/admission contract mismatch")
    prepared=load(Path(truth_path).with_name("MANIFEST_RECEIPT.json"))
    expected_outputs={Path(r["path"]).name:r["sha256"] for r in prepared["outputs"]}
    if expected_outputs.get(Path(truth_path).name)!=sha(truth_path):raise ValueError("Frozen evaluator truth drift")
    manifest_path=Path(truth_path).with_name("AUDIO_ONLY.json");verify(contract["manifest"])
    if expected_outputs.get(manifest_path.name)!=sha(manifest_path):raise ValueError("Frozen query population drift")
    expected={j["job_id"]:j for j in load(manifest_path)["jobs"]}
    truths={t["job_id"]:t for t in load(truth_path)["cells"]}
    if len(expected)!=96 or set(expected)!={k for k,t in truths.items() if t["screen48"]}:raise ValueError("Native screen must use exactly the fixed96 cells")
    aliases=normalize_jobs(contract["jobs_by_id"],expected)
    frozen_screen=next(r for r in prepared["inputs"] if Path(r["path"]).name=="SCREEN_48.json")
    verify(frozen_screen)
    if contract["screen_sha256"]!=frozen_screen["sha256"] or load(contract["manifest"]["path"]).get("screen_sha256")!=frozen_screen["sha256"]:raise ValueError("Original N1 fixed-screen plan binding differs")
    if {j["job_id"]:j for j in load(contract["manifest"]["path"])["jobs"]}!=contract["jobs_by_id"]:raise ValueError("Native admission jobs differ from its bound manifest")
    if not set(contract["profiles"])<=set(PROFILES) or not contract["profiles"]:raise ValueError("Unknown or missing native profile")
    for field in ["model","library","frozen_runner","frozen_adapter"]:verify(contract[field])
    for item in contract["native_runtime_files"]:verify(item)
    if set(index["completed"])&set(index["failed"]):raise ValueError("Native cell marked both completed and failed")
    execution={"device":contract["native_device"],"native_library_sha256":contract["library"]["sha256"],"native_model_sha256":contract["model"]["sha256"],
               "adapter_sha256":contract["frozen_adapter"]["sha256"],"runner_sha256":contract["frozen_runner"]["sha256"],"cpu_threads":contract["cpu_threads"],
               "delivery":contract["delivery"],"profiles":contract["profiles"],"runtime_file_sha256s":sorted(r["sha256"] for r in contract["native_runtime_files"])}
    cells=[];failures=[]
    for cell_id,binding in index["failed"].items():
        try:verify(binding);failure=load(binding["path"]);reason=failure.get("failure_class","RUNTIME_FAILED")
        except Exception:reason="FAILURE_RECEIPT_INTEGRITY_FAILED"
        failures.append({"cell_id":cell_id,"reason":reason,"result":binding})
    for cell_id,binding in index["completed"].items():
        try:
            profile,original_job_id=cell_id.split("/")
            if profile not in contract["profiles"] or original_job_id not in aliases:raise ValueError("Unadmitted native cell")
            job_id=aliases[original_job_id]
            verify(binding);result=load(binding["path"]);attempt=Path(binding["path"]).parent;checkpoint=load(attempt.parent/"CHECKPOINT.json")
            if checkpoint["result"]!=binding or checkpoint["status"]!="COMPLETE" or result["status"]!="COMPLETE":raise ValueError("Native checkpoint/result mismatch")
            key=fingerprint({"contract":native_hash,"profile":profile,"job":contract["jobs_by_id"][original_job_id]})
            if result["cache_key"]!=key or checkpoint["cache_key"]!=key:raise ValueError("Native cache identity changed")
            if result["profile"]!=profile or result["job_id"]!=original_job_id or result["input"]!=contract["jobs_by_id"][original_job_id] or not result["all_audio_samples_delivered"] or result["delivered_audio_samples"]!=expected[job_id]["frames"]:raise ValueError("Native waveform/profile/delivery mismatch")
            if result["gpu"]!=contract["gpu"] or result["gpu_device"]!=contract["gpu_device"]:raise ValueError("Native execution device changed")
            runtime=result["runtime_manifest"]
            if runtime["model_sha256"]!=contract["model"]["sha256"] or runtime["library_sha256"]!=contract["library"]["sha256"] or runtime["profile"]!=contract["profiles"][profile] or runtime["gain"]!=1 or runtime["sample_rate_hz"]!=16000 or runtime["num_speakers"]!=8 or runtime["gpu"]!=contract["gpu"]:raise ValueError("Native runtime manifest changed")
            for item in result["evidence"]:verify(item)
            if (attempt/"AVAILABILITY.jsonl").resolve() not in {Path(r["path"]).resolve() for r in result["evidence"]}:raise ValueError("Availability evidence not bound")
            verify(result["probability_file"])
            with np.load(result["probability_file"]["path"],allow_pickle=False) as payload:
                values=payload["probabilities"];step=float(payload["seconds_per_frame"]);samples=int(payload["audio_samples"])
            if samples!=expected[job_id]["frames"] or list(values.shape)!=result["shape"] or len(values)!=samples//160+1:raise ValueError("Native probability geometry mismatch")
            scored=score_native_probability(values,step,lines(attempt/"AVAILABILITY.jsonl"),truths[job_id])
            if abs(scored["frame_support"]["raw_native_endpoint_sec"]-result["native_clock_end_sec"])>1e-8:raise ValueError("Native frame cadence/end changed")
            cells.append({"cell_id":cell_id,"profile":profile,"job_id":job_id,"original_job_id":original_job_id,"tap":expected[job_id]["tap"],"reference_class":truths[job_id]["reference_class"],"result":binding,"score":scored,
                          "audio_seconds":samples/16000,"wall_sec":result["wall_sec"],"process_cpu_sec":result["process_cpu_sec"],"sampled_peak_rss_bytes":result.get("sampled_peak_rss_bytes"),
                          "worker_lifetime_peak_wset_bytes":result.get("worker_lifetime_peak_wset_bytes")})
        except Exception as exc:failures.append({"cell_id":cell_id,"reason":"SCORING_OR_INTEGRITY_FAILED","error":type(exc).__name__+": "+str(exc),"result":binding})
    by_profile={profile:{c["job_id"]:c for c in cells if c["profile"]==profile} for profile in PROFILES}
    common=set.intersection(*(set(rows) for rows in by_profile.values()))
    groups=[]
    for population in ["all_completed","matched_three_profiles"]:
        for profile in PROFILES:
            for tap in ["O0","O1"]:
                selected=[c for c in by_profile[profile].values() if c["tap"]==tap and (population=="all_completed" or c["job_id"] in common)]
                groups.append({"population":population,"profile":profile,"tap":tap,**aggregate(selected)})
    ratios=[]
    for profile in PROFILES[1:]:
        for tap in ["O0","O1"]:
            keys=sorted(k for k in set(by_profile["low_latency"])&set(by_profile[profile]) if expected[k]["tap"]==tap)
            base=aggregate([by_profile["low_latency"][k] for k in keys]);candidate=aggregate([by_profile[profile][k] for k in keys])
            ratios.append({"profile":profile,"baseline_profile":"low_latency","tap":tap,"matched_cells":len(keys),"expected_cells":48,
                "accelerated_wall_ratio":candidate["resources"]["native_cell_wall_seconds"]/base["resources"]["native_cell_wall_seconds"] if base["resources"]["native_cell_wall_seconds"] else None,
                "primary_approximate_DER_difference":candidate["activity_primary_collar0"]["micro_approximate_activity_DER"]-base["activity_primary_collar0"]["micro_approximate_activity_DER"] if all(r["activity_primary_collar0"]["micro_approximate_activity_DER"] is not None for r in [base,candidate]) else None,
                "scope":"same-device, same-source matched saved cells; runtime ratio excludes model load and is not integrated caption latency"})
    status="COMPLETE" if len(cells)==288 and not failures else "FAILED" if failures else "PARTIAL"
    historical_errors=[{"receipt":bind(path),"failure_class":load(path).get("failure_class","UNRECORDED")} for path in sorted(index_path.parent.glob("COORDINATOR_ERROR_*.json"))]
    summary={"schema":"n2-native-three-profile-summary-v1","created_utc":datetime.now(timezone.utc).isoformat(),"status":status,"expected_cells":288,"scored_cells":len(cells),"execution":execution,
             "coverage":[{"profile":p,"expected_cells":96,"scored_cells":len(by_profile[p]),"missing_job_ids":sorted(set(expected)-set(by_profile[p]))} for p in PROFILES],
             "matched_three_profile_cells":len(common),"failure_counts":dict(Counter(f["reason"] for f in failures)),"groups":groups,"matched_profile_ratios":ratios,
             "historical_coordinator_incidents":{"counts":dict(Counter(r["failure_class"] for r in historical_errors)),"scope":"preserved prior coordinator incidents; completed numerical cells may resume unchanged; current-launch elapsed is not whole-run cost"},
             "definition":{"activity":"0.5 heuristic native activity; zero-collar primary and250ms sensitivity; overlap included, complete estimated references only; no phonetic DER or published benchmark comparison",
                           "native_frame_support":"raw frames retained and intersected with actual delivered waveform per availability event, never truth fitted",
                           "turns":"all known source turns, short replies <=1.5s and returns after >=2s; maximum activity-intersection slot with ties unresolved; no embeddings/names/ASR in this pure runner",
                           "capacity":"eight fixed slots, no recycling; saturation is descriptive and not proof of a ninth speaker",
                           "resources":"accelerated causal native-only CPU or CUDA process, explicitly bound device/runtime, model load amortized; CPU/RSS not device memory or CM5/Pi total-system suitability"},
             "index_sha256":sha(index_snapshot),"truth_sha256":sha(truth_path),"scorer_sha256":sha(__file__),"activity_scoring_sha256":sha(HERE/"scoring.py"),"protocol_amendment_sha256":sha(HERE/"PROTOCOL_AMENDMENT_01.json"),
             "scheduler_aliases":{"changed_ID_count":sum(k!=v for k,v in aliases.items()),"receipt_sha256":fingerprint(aliases),"original_SCREEN_48_sha256":frozen_screen["sha256"],"rule":"N1_BASELINE_S45_xx_yy_Ot to N2_S45_xx_yy_Ot only; every other job field equal including audio hash/path/frames/rate/gain/tap/reset; original IDs retained in private receipts"},
             "redaction":"No names, actor IDs, transcripts, waveforms, vectors, native probabilities or source file paths"}
    save(Path(out_dir)/"NATIVE_PROFILE_EVIDENCE.json",{"summary":summary,"inputs":{"index":bind(index_snapshot),"original_index_path":str(index_path),"admission":bind(index_path.with_name("ADMISSION.json")),"truth":bind(truth_path)},"scheduler_alias_receipt":aliases,"historical_coordinator_incidents":historical_errors,"cells":cells,"failures":failures})
    save(Path(public_dir)/"NATIVE_PROFILE_SUMMARY.json",summary)
    text=["# N2 native profile screen","",f"Status: **{status}**. Scored {len(cells)} of288 fixed cells; {len(common)} match all three profiles. Device: {execution['device']['kind']}.","",
          "| Profile | Scored / expected |","| --- | ---: |"]
    text += [f"| {p} | {len(by_profile[p])} /96 |" for p in PROFILES]
    percent=lambda value:"unavailable" if value is None else f"{100*value:.2f}%"
    number=lambda value:"unavailable" if value is None else f"{value:.4f}"
    text += ["","| Profile | Tap | Complete-reference cells | DER collar0 | Macro JER collar0 | DER collar250ms | Macro JER collar250ms | Retained speaker-time | Native wall/audio |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for group in groups:
        if group["population"]!="all_completed":continue
        primary=group["activity_primary_collar0"];sensitivity=group["activity_collar_0p25_sensitivity"]
        text.append(f"| {group['profile']} | {group['tap']} | {primary['included_cells']} /48 | {percent(primary['micro_approximate_activity_DER'])} | {percent(primary['macro_scene_approximate_activity_JER'])} | {percent(sensitivity['micro_approximate_activity_DER'])} | {percent(sensitivity['macro_scene_approximate_activity_JER'])} | {percent(sensitivity['reference_speaker_time_retained_fraction'])} | {number(group['resources']['accelerated_wall_RTF'])} |")
    text += ["","DER/JER above are estimated activity diagnostics. JER averages supported nonempty scenes; its scene denominator is in JSON. Empty controls retain false activity seconds and a null individual DER denominator. Reference-class breakdowns expose those failures separately.","",
             "| Profile | Tap | Resolved / source turns | Resolved / short turns | Consistent / returns | Changed / unresolved returns | Split identities / merging slots |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for group in groups:
        if group["population"]!="all_completed":continue
        coverage=group["turn_coverage"]["sums"]
        count=lambda key:int(coverage.get(key,0))
        text.append(f"| {group['profile']} | {group['tap']} | {count('resolved_turns')} /{count('source_turn_denominator')} | {count('short_turns_resolved')} /{count('short_turn_denominator')} | {count('return_consistent')} /{count('return_denominator')} | {count('return_changed_track')} /{count('return_unresolved')} | {count('identities_split_across_tracks')} /{count('tracks_merging_identities')} |")
    text += ["","Zero-collar estimated activity DER/JER are primary; 250ms sensitivity retains explicit speaker-time and wall-time exclusions. Missing/failed cells stay in the denominator. Raw native endpoint frames are preserved and scoring uses only delivered waveform support.","",
             "This is a pure native diarizer with accelerated causal input. It does not measure the application's ASR, embeddings, naming, caption latency, Pi behavior, GPU memory or total-system2GB suitability. Detailed turn/short/return/capacity counts and matched profile runtime ratios are in NATIVE_PROFILE_SUMMARY.json. Private evidence remains outside Git."]
    if historical_errors:text += ["",f"The evidence retains {len(historical_errors)} historical coordinator incident receipt(s), separately from final numerical-cell outcomes. Processing costs sum completed cells; a resume launch's elapsed time is not presented as whole-run time."]
    (Path(public_dir)/"NATIVE_PROFILE_SUMMARY.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index",required=True)
    parser.add_argument("--truth",default=DEFAULT_TRUTH)
    parser.add_argument("--out",default="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/native_profile_summary")
    parser.add_argument("--public-out",default=str(HERE))
    parser.add_argument("--require-complete",action="store_true")
    args=parser.parse_args();result=summarize(args.index,args.truth,args.out,args.public_out)
    print(json.dumps({k:result[k] for k in ["status","scored_cells","expected_cells","matched_three_profile_cells"]},indent=2))
    if result["status"]=="FAILED" or args.require_complete and result["status"]!="COMPLETE":raise SystemExit(1)
