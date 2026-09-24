"""Aggregate four completed/partial N2 Controller screens; see README.md."""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics

from prepare import HERE,bind,fingerprint,load,sha
from score_runtime import lines,merge_segments,profile,score,score_activity_attempt
from scoring import turn_coverage

COMBINATIONS=("D0_E0","D1_E0","D0_E1","D1_E1")
DEFAULT_TRUTH="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/EVALUATOR_TRUTH.json"
DISPATCH_FIELDS={
    "research_asr_dispatch":("source_start_sec","source_end_sec","receptive_start_sec","available_source_cursor_sec","native_endpoint","advisory_endpoint","reset_requested"),
    "research_asr_reset":("native_endpoint","advisory_endpoint"),
    "research_asr_tail_dispatch":("source_start_sec","source_end_sec","samples"),
    "research_asr_drain":("source_end_sec","synthetic_right_padding_sec","padding_is_observed_audio"),
}


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    temporary.replace(path)


def canonical_rows(rows,formatted=False):
    """Preserve raw spelling/order and join Controller's flattened segments."""
    groups={}
    for row in rows:groups.setdefault(row["utterance_id"],[]).append(row)
    output=[]
    for key,parts in groups.items():
        if all("raw_asr_text" in p for p in parts):
            parts.sort(key=lambda p:p.get("token_range",[0])[0])
            value="".join((p.get("final_punctuated_display_text") or p.get("provisional_display_text") or p["raw_asr_text"]) if formatted else p["raw_asr_text"] for p in parts)
        elif len(parts)==1:
            value=parts[0].get("display_text",parts[0].get("text","")) if formatted else parts[0].get("text","")
        else:raise ValueError("Duplicate unqualified utterance rows")
        output.append({"utterance_id":key,"text":value})
    return output


def asr_signatures(events,rows):
    """Fingerprint semantic/source-bound ASR data, excluding all compute clocks."""
    observations=[];finals=[];dispatch=[]
    for row in events:
        kind=row["event_type"];p=row["payload"]
        if kind=="s6d_text_ready":
            observations.append({k:p.get(k) for k in ("event_id","utterance_id","source_start_sec","source_end_sec","text","final")})
        elif kind=="transcript_final":
            finals.append({k:p.get(k) for k in ("input_event_id","utterance_id","source_start_sec","source_end_sec","text")})
        if kind in DISPATCH_FIELDS:
            dispatch.append({"event_type":kind,"source_sec":row.get("source_sec"),**{k:p.get(k) for k in DISPATCH_FIELDS[kind]}})
    canonical=canonical_rows(rows)
    payloads={"raw_observations":observations,"raw_final_events":finals,"dispatch_reset_source_sequence":dispatch,
              "final_utterance_text":canonical,"final_raw_word_order":[word for r in canonical for word in r["text"].split()],
              "formatted_final_utterance_text":canonical_rows(rows,formatted=True)}
    return {key:{"sha256":fingerprint(value),"count":len(value)} for key,value in payloads.items()}


def numeric_queues(value,prefix=""):
    output={}
    if not isinstance(value,dict):return output
    for key,item in value.items():
        if key=="state_bounds":continue  # configuration limits are not observations
        name=f"{prefix}.{key}" if prefix else key
        if isinstance(item,dict):output.update(numeric_queues(item,name))
        elif key in {"max_depth","max_age_sec","max_handler_sec","max_pending_events","accepted","completed","depth","pending_events","queue_peak","queue_max_observed_age_seconds"} and type(item) in (int,float):
            output[name]=item
    return output


def measured_calls(events):
    """Count recorded operations, with one compute-duration source per event."""
    output={}
    for kind,field,scale in [("research_asr_dispatch","compute_ms",0.001),
                             ("research_asr_tail_dispatch","compute_ms",0.001),
                             ("research_asr_drain","compute_ms",0.001),
                             ("research_asr_reset","compute_ms",0.001),
                             ("research_embedding","compute_ms",0.001),
                             ("n2_diarization_frames","compute_sec",1.0),
                             ("s6d_punctuation_revision",None,1.0)]:
        rows=[r["payload"] for r in events if r["event_type"]==kind]
        durations=[]
        for row in rows:
            duration=row.get(field) if field else (row["compute_finished_monotonic_sec"]-row["compute_started_monotonic_sec"] if all(k in row for k in ["compute_finished_monotonic_sec","compute_started_monotonic_sec"]) else None)
            if duration is not None:
                if duration<0:raise ValueError("Negative recorded operation duration")
                durations.append(duration*scale)
        output[kind]={"recorded_events":len(rows),"events_with_duration":len(durations),
                      "compute_seconds_sum":sum(durations) if durations else None,
                      "maximum_compute_seconds":max(durations) if durations else None}
    return output


def execution_identity(events,contract):
    native=next((r["payload"] for r in events if r["event_type"]=="n2_diarization_binding"),{})
    if native:
        device="CUDA" if native.get("gpu") is True else "CPU" if native.get("gpu") is False else "UNRECORDED"
    else:device="CPU_BASELINE_ONNX" if contract["combination"].startswith("D0") else "UNRECORDED"
    return {"diarizer_device":device,"native_library_sha256":native.get("library_sha256"),
            "native_model_sha256":native.get("model_sha256"),"native_precision":native.get("precision"),
            "profile":contract.get("profile"),"input_buffer_sec":native.get("input_buffer_sec"),
            "right_context_sec":native.get("right_context_sec"),"source_bindings_sha256":fingerprint(contract.get("source_bindings",{})),
            "threads":contract.get("threads"),"gpu_memory_measured":False}


def query_diagnostics(events,truth,existing):
    embeddings={};decisions=[]
    for row in events:
        p=row["payload"]
        if row["event_type"]=="research_embedding":
            key=p.get("evidence_event_id",p.get("event_id"))
            if key is None:raise ValueError("Runtime embedding lacks an event ID")
            if key in embeddings:raise ValueError("Repeated runtime embedding event ID")
            embeddings[key]=p
        elif row["event_type"]=="speaker_decision":decisions.append(p)
    windows=[{"start":p["source_start_sec"],"end":p["source_end_sec"],"label":p.get("tracker_id")} for p in embeddings.values()]
    proxy=[];track_ids=set();matched=set()
    for decision in decisions:
        nested=decision.get("decision",{})
        track=decision.get("tracker_id",nested.get("tracker_id",decision.get("track_id")))
        eid=decision.get("input_event_id",decision.get("evidence_id",decision.get("event_id")))
        if track is not None:track_ids.add(str(track))
        if eid in embeddings and track is not None:
            event=embeddings[eid];matched.add(eid)
            proxy.append({"start":event["source_start_sec"],"end":event["source_end_sec"],"label":str(track)})
    if "resolved_turns" in existing:
        coverage=dict(existing)
    else:
        coverage=turn_coverage(truth["turns"],merge_segments(proxy),windows)
        coverage.pop("mapped_turns_evaluator_only",None)
        coverage["track_scope"]="coarse_actual_embedding_decision_window_proxy_not_full_diarization"
    coverage["embedding_calls"]=len(embeddings)
    coverage["actual_decisions_with_matched_embedding"]=len(matched)
    coverage["actual_embedding_without_resolved_track_decision"]=len(embeddings)-len(matched)
    coverage["evidence_availability_scope"]="any positive reference intersection with any admitted window, not a claim of usable naming evidence"
    coverage["known_reference_speaker_count"]=len({t["identity"] for t in truth["turns"]})
    coverage["observed_track_id_count"]=len(track_ids)
    coverage["track_id_count_error_proxy"]=len(track_ids)-coverage["known_reference_speaker_count"]
    coverage["window_seconds_sum_with_repeated_support"]=sum(w["end"]-w["start"] for w in windows)
    coverage.update({k:0.0 for k in ["source_turn_activity_seconds_sum","source_turn_activity_with_any_window_seconds_sum","short_turn_activity_seconds_sum","short_turn_activity_with_any_window_seconds_sum"]})
    for turn in truth["turns"]:
        active=sum((b-a)/16000 for a,b in turn["activity_ranges_samples_estimated"])
        intersections=[]
        for a,b in turn["activity_ranges_samples_estimated"]:
            for window in windows:
                start=max(a/16000,window["start"]);end=min(b/16000,window["end"])
                if end>start:intersections.append({"start":start,"end":end,"label":"evidence"})
        covered=sum(s["end"]-s["start"] for s in merge_segments(intersections))
        coverage["source_turn_activity_seconds_sum"]+=active
        coverage["source_turn_activity_with_any_window_seconds_sum"]+=covered
        if active<=1.5:
            coverage["short_turn_activity_seconds_sum"]+=active
            coverage["short_turn_activity_with_any_window_seconds_sum"]+=covered
    counts=Counter();overlap_seconds=0.0
    for window in windows:
        by_identity=defaultdict(list)
        for turn in truth["turns"]:
            for a,b in turn["activity_ranges_samples_estimated"]:
                start=max(a/16000,window["start"]);end=min(b/16000,window["end"])
                if end>start:by_identity[turn["identity"]].append((start,end))
        counts["windows_touching_multiple_reference_identities"]+=len(by_identity)>1
        counts["windows_touching_no_reference_activity"]+=not by_identity
        intersections=[];identities=list(by_identity)
        for i,left in enumerate(identities):
            for right in identities[i+1:]:
                for a,b in by_identity[left]:
                    for c,d in by_identity[right]:
                        if min(b,d)>max(a,c):intersections.append({"start":max(a,c),"end":min(b,d),"label":"overlap"})
        merged=merge_segments(intersections)
        counts["windows_with_simultaneous_reference_overlap"]+=bool(merged)
        overlap_seconds+=sum(s["end"]-s["start"] for s in merged)
    coverage.update(counts)
    coverage["simultaneous_reference_overlap_seconds_sum_across_windows"]=overlap_seconds
    coverage["contamination_scope"]="complete estimated-activity reference" if truth["complete_reference"] else "known references only; missing ambient speech prevents a full purity claim"
    return coverage


def supplement_naming(report,truth,rosters,observer_dir):
    if not report.get("conditions"):return
    admission=load(Path(observer_dir)/"OBSERVER_ADMISSION.json")
    entries={r["gallery_id"]:r for r in admission["conditions"]}
    for condition in report["conditions"]:
        entry=entries[condition["gallery_id"]]
        gallery=load(entry["gallery"]["path"])
        condition["reference_class"]=truth["reference_class"]
        condition["gate_status"]=gallery["calibration"]["status"]
        members={p["profile_id"] for p in gallery["profiles"]}
        roster=next(r for r in rosters["primary"] if r["mode"]==condition["mode"] and r["domain"]==condition["domain"])
        intended={profile(person) for person in roster["intended_identities"]}
        condition["source_turn_availability"]={"all_source_turns":len(truth["turns"]),
            "available_member_turns":sum(profile(t["identity"]) in members for t in truth["turns"]),
            "known_reference_stranger_turns":sum(profile(t["identity"]) not in members for t in truth["turns"]),
            "intended_member_turns_missing_E":sum(profile(t["identity"]) in intended-members for t in truth["turns"]),
            "intended_members":len(intended),"available_members":len(members),"unavailable_members":len(intended-members),
            "absent_available_members":len(members-{profile(t["identity"]) for t in truth["turns"]})}


def activity_aggregate(rows,key):
    eligible=[r[key] for r in rows if r[key].get("status")=="APPROXIMATE_ACTIVITY_ONLY"]
    denominators=sum(r.get("reference_speaker_seconds",0) for r in eligible)
    sums={name:sum(r.get(name,0) for r in eligible) for name in ("reference_speaker_seconds","evaluated_wall_seconds","collar_excluded_seconds","miss_seconds","false_alarm_seconds","confusion_seconds")}
    jers=[r["approximate_activity_JER"] for r in eligible if r.get("approximate_activity_JER") is not None]
    before_collar=sum(r["activity"].get("reference_speaker_seconds",0) for r in rows if r[key].get("status")=="APPROXIMATE_ACTIVITY_ONLY")
    return {"included_cells":len(eligible),"unavailable_cells":len(rows)-len(eligible),
            "unavailable_reasons":dict(Counter(r[key].get("status","MISSING") for r in rows if r[key].get("status")!="APPROXIMATE_ACTIVITY_ONLY")),
            **sums,"micro_approximate_activity_DER":(sums["miss_seconds"]+sums["false_alarm_seconds"]+sums["confusion_seconds"])/denominators if denominators else None,
            "reference_speaker_seconds_before_collar":before_collar,"reference_speaker_seconds_excluded_by_collar":max(0,before_collar-denominators),
            "reference_speaker_time_retained_fraction":denominators/before_collar if before_collar else None,
            "macro_scene_approximate_activity_JER":statistics.mean(jers) if jers else None,"JER_scene_denominator":len(jers),
            "speaker_count_signed_error_sum":sum(r.get("speaker_count_error",0) for r in eligible),
            "speaker_count_absolute_error_sum":sum(abs(r.get("speaker_count_error",0)) for r in eligible),
            "speaker_count_error_cells":sum(r.get("speaker_count_error",0)!=0 for r in eligible)}


def sum_numbers(rows,exclude=()):
    counts=defaultdict(float);support=Counter()
    for row in rows:
        for key,value in row.items():
            if key not in exclude and type(value) in (int,float):counts[key]+=value;support[key]+=1
    return {"sums":dict(counts),"cells_supporting_each_sum":dict(support)}


def word_aggregate(metrics):
    cp=[m["cpWER"] for m in metrics if isinstance(m.get("cpWER"),dict)]
    valid=[r for r in cp if r.get("cpWER") is not None]
    words=sum(r["reference_words"] for r in valid);errors=sum(r["errors"] for r in valid)
    named=[m["fixed_named_attributed_WER"] for m in metrics if m.get("fixed_named_attributed_WER",{}).get("WER") is not None]
    named_words=sum(r["reference_words"] for r in named);named_errors=sum(r["errors"] for r in named)
    return {"cells":len(metrics),"cpWER_supported_cells":len(valid),"cpWER_reference_words":words,"cpWER_errors":errors,
            "micro_cpWER":errors/words if words else None,
            "cpWER_unavailable_reasons":dict(Counter(r.get("status","MISSING") for r in cp if r.get("cpWER") is None)),
            "empty_control_inserted_words":sum(r.get("empty_control_inserted_words") or 0 for r in cp),
            "fixed_named_WER_supported_cells":len(named),"fixed_named_reference_words":named_words,"fixed_named_errors":named_errors,
            "micro_fixed_named_WER":named_errors/named_words if named_words else None,
            "word_counts":sum_numbers([m.get("word_counts",{}) for m in metrics]),
            "tcpWER":None,"qualification":"complete-reference lexical attribution only; no exact word times; fixed-ID naming counts closed assumptions separately"}


def aggregate_group(cells):
    score_rows=[c["score"] for c in cells]
    conditions=defaultdict(list)
    for cell in cells:
        for row in cell["score"].get("conditions",[]):
            key=(row["mode"],row["domain"],row["position"].rsplit("_",1)[-1],row["stream"])
            conditions[key].append(row)
    naming=[]
    for key,rows in sorted(conditions.items()):
        stages={stage:word_aggregate([r["stages"][stage] for r in rows if r["stages"].get(stage,{}).get("word_counts") is not None]) for stage in ("first_visible","first_final","latest")}
        naming.append({"mode":key[0],"enrollment_domain":key[1],"enrollment_position":key[2],"enrollment_stream":key[3],"cells":len(rows),
                       "naming_window_counts":sum_numbers([r["naming_window_counts"] for r in rows]),
                       "naming_window_counts_by_reference_class":{kind:sum_numbers([r["naming_window_counts"] for r in rows if r["reference_class"]==kind]) for kind in sorted({r["reference_class"] for r in rows})},
                       "gate_status_counts":dict(Counter(r["gate_status"] for r in rows)),
                       "source_turn_and_missing_E_denominators":sum_numbers([r.get("source_turn_availability",{}) for r in rows]),
                       "caption_stages":stages,"stage_scope":"first-visible partial hypotheses against final reference are diagnostic; shadow label timing modelled",
                       "raw_word_invariance_failures":sum(not r["raw_words_equal_observer_base"] for r in rows),
                       "formatted_invariance_failures":sum(not r["formatted_words_equal_observer_base"] for r in rows)})
    queues=defaultdict(list)
    for cell in cells:
        for key,value in cell["queues"].items():queues[key].append(value)
    rss=[c["peak_sampled_rss_bytes"] for c in cells if c["peak_sampled_rss_bytes"] is not None]
    cpu=[c["cpu_seconds"] for c in cells if c["cpu_seconds"] is not None]
    calls={}
    for kind in sorted({kind for c in cells for kind in c["calls"]}):
        records=[c["calls"][kind] for c in cells if kind in c["calls"]]
        durations=[r["compute_seconds_sum"] for r in records if r["compute_seconds_sum"] is not None]
        maxima=[r["maximum_compute_seconds"] for r in records if r["maximum_compute_seconds"] is not None]
        calls[kind]={"recorded_events":sum(r["recorded_events"] for r in records),"events_with_duration":sum(r["events_with_duration"] for r in records),
                     "compute_seconds_sum":sum(durations) if durations else None,"maximum_compute_seconds":max(maxima) if maxima else None}
    return {"completed_cells":len(cells),"reference_classes":dict(Counter(c["reference_class"] for c in cells)),
            "activity_primary_collar0":activity_aggregate(score_rows,"activity"),
            "activity_collar_0p25_sensitivity":activity_aggregate(score_rows,"activity_collar_0p25_sensitivity"),
            "turn_window_coverage":sum_numbers([c["coverage"] for c in cells]),
            "turn_window_coverage_by_reference_class":{kind:sum_numbers([c["coverage"] for c in cells if c["reference_class"]==kind]) for kind in sorted({c["reference_class"] for c in cells})},
            "native_frame_support":sum_numbers([r.get("native_frame_support",{}) for r in score_rows]),
            "primary_actual_latest_words":word_aggregate([c["score"].get("primary_actual_latest_words",c["score"].get("actual_latest_words",{})) for c in cells]),
            "primary_actual_stage_availability":{"latest":"actual Controller final snapshot","first_visible":"unavailable as full actual GUI snapshot in these receipts","first_final":"unavailable as full actual GUI snapshot in these receipts"},
            "naming_conditions":naming,
            "resources":{"audio_seconds":sum(c["audio_seconds"] for c in cells),"controller_attempt_elapsed_seconds":sum(c["elapsed_seconds"] for c in cells),
                         "cpu_seconds":sum(cpu) if cpu else None,"cpu_measured_cells":len(cpu),"maximum_sampled_process_rss_bytes":max(rss) if rss else None,"rss_measured_cells":len(rss),
                         "operation_events":calls,"operation_event_scope":"recorded dispatch/reset/drain, emitted embedding/native-frame results and punctuation revisions; native calls without an emitted frame event are not recoverable; parallel durations are not wall latency",
                         "queue_metrics":{key:{"maximum":max(values),"sum":sum(values),"cells":len(values)} for key,values in queues.items()},
                         "observer_online_compute_seconds":sum(c["observer"].get("observer_compute_seconds",0) for c in cells),
                         "observer_deferred_caption_replay_seconds":sum(c["observer"].get("deferred_caption_replay_seconds",0) for c in cells),
                         "scope":"observed Windows process and sampled RSS; resident weights shared within each runner; includes observer when present; not Pi, total-system2GB or independent GPU-memory measurement"}}


def summarize(index_paths,truth_path,out_dir,public_dir,expected_manifest=None,scope="screen48"):
    out_dir,public_dir=Path(out_dir),Path(public_dir)
    truth_doc=load(truth_path);truths={t["job_id"]:t for t in truth_doc["cells"]}
    manifest_path=Path(expected_manifest) if expected_manifest else Path(truth_path).with_name("AUDIO_ONLY.json")
    expected_doc=load(manifest_path);expected={j["job_id"]:j for j in expected_doc["jobs"]}
    if len(expected)!=len(expected_doc["jobs"]):raise ValueError("Duplicate expected jobs")
    if scope=="screen48" and (len(expected)!=96 or set(expected)!={k for k,t in truths.items() if t["screen48"]}):
        raise ValueError("Screen48 expected population must remain exactly96 admitted cells")
    if set(expected)-set(truths):raise ValueError("Expected job lacks frozen evaluator truth")
    rosters=load(Path(truth_path).with_name("ROSTERS.json"))
    receipt=load(Path(truth_path).with_name("MANIFEST_RECEIPT.json"))
    prepared={Path(r["path"]).name:r["sha256"] for r in receipt["outputs"]}
    for path in [Path(truth_path),Path(truth_path).with_name("ROSTERS.json")]:
        if prepared.get(path.name)!=sha(path):raise ValueError("Frozen evaluator manifest drift")
    indexes={};cells=[];failures=[];receipts=[]
    for index_path in index_paths:
        index_path=Path(index_path);index_bytes=index_path.read_bytes();index=json.loads(index_bytes.decode("utf-8-sig"));admission=load(index_path.with_name("ADMISSION.json"));contract=admission["contract"]
        combo=contract["combination"]
        if combo not in COMBINATIONS or combo in indexes:raise ValueError("Need at most one RESULT_INDEX per factorial combination")
        if index["contract_sha256"]!=admission["contract_sha256"]:raise ValueError("Index/admission contract mismatch")
        if fingerprint(contract)!=admission["contract_sha256"]:raise ValueError("Admission contents differ from contract hash")
        if index.get("total")!=len(expected):raise ValueError("Index expected-population denominator differs")
        if set(index.get("failed",{})) & set(index.get("completed",{})):raise ValueError("Cell marked both completed and failed")
        if sha(contract["manifest"]["path"])!=contract["manifest"]["sha256"]:raise ValueError("Runtime audio-only manifest drift")
        runtime_jobs={j["job_id"]:j for j in load(contract["manifest"]["path"])["jobs"]}
        if any(runtime_jobs.get(k)!=value for k,value in expected.items()):raise ValueError("Runtime jobs differ from expected accepted audio/gain/scope")
        index_snapshot=out_dir/"input_indexes"/(combo+"_RESULT_INDEX.json");index_snapshot.parent.mkdir(parents=True,exist_ok=True);index_snapshot.write_bytes(index_bytes)
        indexes[combo]=index;receipts.append({"combination":combo,"index":bind(index_snapshot),"original_index_path":str(index_path),"admission":bind(index_path.with_name("ADMISSION.json"))})
        for job_id,result_path in index.get("failed",{}).items():
            failures.append({"combination":combo,"job_id":job_id,"reason":"RUNTIME_FAILED","result_path":result_path})
        for job_id,result_path in index.get("completed",{}).items():
            if job_id not in expected:raise ValueError("Unadmitted completed cell")
            try:
                result_path=Path(result_path);result=load(result_path);attempt=result_path.parent
                checkpoint=load(attempt.parent/"CHECKPOINT.json")
                if checkpoint["status"]!="COMPLETE" or sha(result_path)!=checkpoint["result"]["sha256"]:raise ValueError("Checkpoint/result integrity failure")
                if result["status"]!="COMPLETE" or result["job_id"]!=job_id or result["combination"]!=combo or result["audio"]!=expected[job_id]:raise ValueError("Completed result/source/combination mismatch")
                for evidence in result["evidence"]:
                    if sha(evidence["path"])!=evidence["sha256"]:raise ValueError("Runtime evidence hash mismatch")
                bound_paths={Path(r["path"]).resolve() for r in result["evidence"]}
                if not all((attempt/name).resolve() in bound_paths for name in ["FINAL_SNAPSHOT.json","RUNTIME_EVENTS.jsonl"]):raise ValueError("Required runtime evidence not bound")
                snapshot=load(attempt/"FINAL_SNAPSHOT.json");events=lines(attempt/"RUNTIME_EVENTS.jsonl")
                if not any(r["event_type"]=="research_asr_dispatch" for r in events):raise ValueError("Missing source-bound ASR dispatch observations")
                observer_dir=attempt/"galleries";observer={}
                if contract.get("galleries") and not (observer_dir/"OBSERVER_RESULT.json").exists():raise ValueError("Admitted gallery observer evidence is missing")
                if (observer_dir/"OBSERVER_RESULT.json").exists():
                    observer=load(observer_dir/"OBSERVER_RESULT.json")
                    if result.get("recorder",{}).get("galleries")!=observer:raise ValueError("Observer receipt differs from bound runtime result")
                    for condition in observer["conditions"]:
                        if sha(condition["rows_path"])!=condition["rows_sha256"]:raise ValueError("Observer row hash drift")
                        if "stages_path" in condition and sha(condition["stages_path"])!=condition["stages_sha256"]:raise ValueError("Observer stage hash drift")
                    scored=score(observer_dir,job_id,truth_path,attempt/"RUNTIME_EVENTS.jsonl")
                    supplement_naming(scored,truths[job_id],rosters,observer_dir)
                else:scored=score_activity_attempt(attempt,job_id,truth_path)
                coverage=query_diagnostics(events,truths[job_id],scored["turn_and_evidence_coverage"])
                cells.append({"combination":combo,"job_id":job_id,"tap":expected[job_id]["tap"],"reference_class":truths[job_id]["reference_class"],
                              "result":bind(result_path),"score":scored,"coverage":coverage,"execution":execution_identity(events,contract),
                              "asr_signatures":asr_signatures(events,snapshot["rows"]),"audio_sha256":expected[job_id]["audio_sha256"],
                              "audio_seconds":expected[job_id]["frames"]/16000,"elapsed_seconds":result["elapsed_seconds"],"cpu_seconds":result.get("cpu_seconds"),"calls":measured_calls(events),
                              "peak_sampled_rss_bytes":result.get("peak_sampled_rss_bytes"),"queues":numeric_queues({"telemetry":result.get("telemetry",{}),"recorder":result.get("recorder",{})}),
                              "observer":{k:observer[k] for k in ("observer_compute_seconds","deferred_caption_replay_seconds","queue_peak","queue_max_observed_age_seconds") if k in observer}})
            except Exception as exc:
                failures.append({"combination":combo,"job_id":job_id,"reason":"SCORING_OR_INTEGRITY_FAILED","error":type(exc).__name__+": "+str(exc),"result_path":str(result_path)})
    by_combo={combo:{c["job_id"]:c for c in cells if c["combination"]==combo} for combo in COMBINATIONS}
    common=set.intersection(*(set(by_combo[c]) for c in COMBINATIONS))
    comparisons=[]
    for combo in COMBINATIONS[1:]:
        for job_id in sorted(set(by_combo["D0_E0"])&set(by_combo[combo])):
            baseline,candidate=by_combo["D0_E0"][job_id],by_combo[combo][job_id]
            if baseline["audio_sha256"]!=candidate["audio_sha256"]:raise ValueError("ASR comparison audio differs")
            checks={key:baseline["asr_signatures"][key]==candidate["asr_signatures"][key] for key in baseline["asr_signatures"]}
            comparisons.append({"combination":combo,"job_id":job_id,"tap":candidate["tap"],"checks":checks})
    groups=defaultdict(list)
    for subset in ("all_completed","matched_four_way"):
        for cell in cells:
            if subset=="matched_four_way" and cell["job_id"] not in common:continue
            ex=cell["execution"];key=(subset,cell["combination"],cell["tap"],fingerprint(ex))
            groups[key].append(cell)
    public_groups=[]
    for key,group in sorted(groups.items()):
        public_groups.append({"population":key[0],"combination":key[1],"tap":key[2],"execution":group[0]["execution"],**aggregate_group(group)})
    coverage=[{"combination":combo,"expected_cells":len(expected),"scored_cells":len(by_combo[combo]),
               "missing_job_ids":sorted(set(expected)-set(by_combo[combo])),"runtime_index_supplied":combo in indexes} for combo in COMBINATIONS]
    paired=Counter(job.rsplit("_",1)[0] for job in common)
    invariance=[]
    for combo in COMBINATIONS[1:]:
        for tap in ["O0","O1"]:
            rows=[c for c in comparisons if c["combination"]==combo and c["tap"]==tap]
            invariance.append({"combination":combo,"tap":tap,"expected_comparisons":sum(j["tap"]==tap for j in expected.values()),"compared_cells":len(rows),
                "checks":{key:{"equal":sum(r["checks"][key] for r in rows),"different":sum(not r["checks"][key] for r in rows)} for key in (rows[0]["checks"] if rows else ["raw_observations","raw_final_events","dispatch_reset_source_sequence","final_utterance_text","final_raw_word_order","formatted_final_utterance_text"])}})
    complete=all(len(by_combo[c])==len(expected) and indexes[c].get("status")=="COMPLETE" for c in COMBINATIONS) and not failures
    asr_failed=any(not all(r["checks"].values()) for r in comparisons)
    caption_invariance=[]
    for combo in COMBINATIONS:
        observed=[c["score"] for c in cells if c["combination"]==combo and "conditions" in c["score"]]
        caption_invariance.append({"combination":combo,"observer_cells":len(observed),
            "actual_vs_base_raw_failures":sum(r.get("actual_vs_clone_raw_invariance") is False for r in observed),
            "actual_vs_base_formatted_failures":sum(r.get("actual_vs_clone_formatted_invariance") is False for r in observed),
            "condition_raw_failures":sum(not condition["raw_words_equal_observer_base"] for r in observed for condition in r["conditions"]),
            "condition_formatted_failures":sum(not condition["formatted_words_equal_observer_base"] for r in observed for condition in r["conditions"])})
    caption_failed=any(row[k]>0 for row in caption_invariance for k in row if k.endswith("failures"))
    capture_status="COMPLETE" if complete else "FAILED" if failures else "PARTIAL"
    summary={"schema":"n2-four-way-screen-summary-v1","created_utc":datetime.now(timezone.utc).isoformat(),"scope":scope,
             "status":"FAILED_ASR_INVARIANCE" if complete and asr_failed else "FAILED_CAPTION_INVARIANCE" if complete and caption_failed else capture_status,"collection_status":capture_status,
             "ASR_invariance_status":"FAILED" if asr_failed else "PASS_ALL_MATCHED" if complete else "PARTIAL_OR_UNAVAILABLE",
             "caption_invariance_status":"FAILED" if caption_failed else "PASS_OBSERVED_ONLY" if any(r["observer_cells"] for r in caption_invariance) else "UNAVAILABLE_NO_OBSERVER",
             "caption_invariance":caption_invariance,
             "expected_cells_per_combination":len(expected),"expected_total_cells":len(expected)*4,"scored_total_cells":len(cells),
             "coverage":coverage,"matched_four_way_cells":len(common),"matched_four_way_paired_scenes":sum(n==2 for n in paired.values()),
             "failure_counts":dict(Counter(r["reason"] for r in failures)),"ASR_invariance":invariance,"groups":public_groups,
             "definitions":{"DER_JER":"estimated activity only; primary collar0 and mandatory250ms sensitivity; no published phonetic benchmark comparison",
                 "D0_activity":"full anonymous activity unavailable; count/merge/split/return diagnostics use actual embedding-decision window proxy, not DER",
                 "cpWER":"complete-reference per-scene lexical stream permutation; Unknown retained; no tcpWER without exact word-time truth",
                 "ASR_invariance":"exact raw observation/final text and source-bound dispatch/reset semantic sequences against D0/E0 same audio; timestamps/compute/label fields excluded",
                 "gallery_conditions":"online names scored on actual selected windows; captions replay original publication order and captured name snapshots; shadow timing modelled",
                 "window_coverage":"any positive intersection, not usable naming evidence; simultaneous overlap and multi-identity contamination separate; incomplete ambient references retained and qualified",
                 "resource_scope":"desktop process measures, sampled RSS, queues and explicitly separated CPU/CUDA runtime hashes; not Pi/total2GB or isolated GPU-memory proof"},
             "redaction":"No audio, vectors, names, profile IDs, actor identities, source transcripts or waveform paths in this public report",
             "input_index_hashes":[{"combination":r["combination"],"sha256":r["index"]["sha256"]} for r in receipts],
             "truth_sha256":sha(truth_path),"expected_manifest_sha256":sha(manifest_path),"scorer_sha256":sha(__file__)}
    private={"summary":summary,"inputs":receipts,"truth":bind(truth_path),"expected_manifest":bind(manifest_path),"cells":cells,"failures":failures,"ASR_comparisons":comparisons}
    save(out_dir/"SCREEN_EVIDENCE.json",private);save(public_dir/"SCREEN_SUMMARY.json",summary)
    markdown=["# N2 four-way saved-audio screen", "",f"Status: **{summary['status']}**. Scored {len(cells)} of {len(expected)*4} expected cells; {len(common)} cells are matched across all four combinations. Missing and failed cells remain in the denominator.","",
              "| Combination | Scored / expected | Missing |","| --- | ---: | ---: |"]
    markdown += [f"| {r['combination']} | {r['scored_cells']} / {r['expected_cells']} | {len(r['missing_job_ids'])} |" for r in coverage]
    markdown += ["",f"ASR invariance: **{summary['ASR_invariance_status']}**. Exact raw observation/final-word, source dispatch/reset and formatted-final checks are reported separately against matched D0/E0 cells.","",
                 "Activity DER/JER use estimated 20 ms references: zero-collar primary and 250 ms sensitivity with retained speaker-time denominators. D0 full activity scores remain unavailable. cpWER retains Unknown streams and uses complete reference scenes; tcpWER remains unavailable. First-visible, first-final and latest caption stages stay separate.","",
                 "CPU/CUDA runtime identities are separate strata. Resource counts include process work and any observer work; they do not establish Pi performance, total 2 GB suitability or an isolated GPU benchmark. Full aggregate denominators, source-turn coverage, strangers, missing enrollment, closed assumptions and queue measurements are in SCREEN_SUMMARY.json. Private cell evidence is retained outside Git."]
    (public_dir/"SCREEN_SUMMARY.md").write_text("\n".join(markdown)+"\n",encoding="utf-8")
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index",action="append",required=True,help="RESULT_INDEX.json; repeat for each of four combinations; partial inputs allowed")
    parser.add_argument("--truth",default=DEFAULT_TRUTH)
    parser.add_argument("--out",default="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/screen_summary")
    parser.add_argument("--public-out",default=str(HERE))
    parser.add_argument("--scope",choices=["screen48","regression"],default="screen48")
    parser.add_argument("--expected-manifest",help="For separate regression population; screen48 still enforces original96")
    parser.add_argument("--require-complete",action="store_true",help="Exit unsuccessfully unless all admitted cells and invariance checks pass")
    args=parser.parse_args()
    result=summarize(args.index,args.truth,args.out,args.public_out,args.expected_manifest,args.scope)
    print(json.dumps({k:result[k] for k in ["status","collection_status","scored_total_cells","expected_total_cells","matched_four_way_cells","ASR_invariance_status"]},indent=2))
    if result["status"].startswith("FAILED") or args.require_complete and result["status"]!="COMPLETE":raise SystemExit(1)
