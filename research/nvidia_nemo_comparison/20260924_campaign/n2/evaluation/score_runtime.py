"""Score finished runtime observer evidence with private truth, never predictor inputs."""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import uuid

from prepare import HERE,bind,load
from scoring import activity_metrics,cpwer,edit_distance,turn_coverage,words


def lines(path):
    path=Path(path)
    if not path.exists():return []
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s]


def profile(identity):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,"just-peachy:N2:research:"+identity))


def merge_segments(segments):
    output=[]
    for label in sorted({s["label"] for s in segments}):
        for segment in sorted((s for s in segments if s["label"]==label),key=lambda s:s["start"]):
            if output and output[-1]["label"]==label and segment["start"]<=output[-1]["end"]+1e-7:
                output[-1]["end"]=max(output[-1]["end"],segment["end"])
            else:output.append(dict(segment))
    return output


def native_activity(observer_dir,runtime_events,duration):
    rows=lines(Path(observer_dir)/"n2_activity_frames.jsonl")
    if not rows and runtime_events:
        rows=[r for r in lines(runtime_events) if r.get("event_type")=="n2_diarization_frames"]
    segments=[];overhang=0.;frame_count=0
    for row in rows:
        p=row["payload"];step=p["frame_step_sec"];first=p["frame_start"]
        threshold=p.get("activity_threshold",0.5)
        for offset,probabilities in enumerate(p["probabilities"]):
            a=(first+offset)*step;b=a+step;frame_count+=1
            supported_end=min(duration,p["audio_received_sec"])
            overhang+=max(0,b-max(a,supported_end))
            if a>=supported_end:continue
            # Restrict metric support to delivered real waveform, not to truth.
            # Native times and all overhanging probabilities remain in evidence.
            for slot,probability in enumerate(probabilities):
                if probability>=threshold:
                    segments.append({"start":a,"end":min(b,supported_end),"label":p["track_ids"][slot]})
    return merge_segments(segments),{"native_frames":frame_count,"native_waveform_overhang_seconds":overhang,
                                   "support_rule":"intersection_with_actual_delivered_waveform_only; raw frames retained; no truth fitted shift"}


def word_metrics(rows,truth):
    reference=defaultdict(list)
    for turn in sorted(truth["turns"],key=lambda t:t["file_support_samples"][0] if t["file_support_samples"] else 0):
        reference[turn["identity"]].extend(words(turn["transcript_normalized"]))
    hypothesis=defaultdict(list);named=defaultdict(list);counts=Counter()
    for row in rows:
        segments=row.get("segments") or [row]
        for segment in segments:
            tokens=words(segment.get("raw_text",segment.get("text",segment.get("raw_asr_text",""))))
            hypothesis[segment.get("track_id") or "Unknown"].extend(tokens)
            named[segment.get("known_profile_id",segment.get("profile_id")) or "Unknown"].extend(tokens)
            counts["raw_words"]+=len(tokens)
            counts["unresolved_track_words"]+=len(tokens) if segment.get("track_id") is None else 0
            state=segment.get("naming_state","unknown")
            counts["verified_named_words"]+=len(tokens) if state in {"known","confirmed"} else 0
            counts["closed_assumption_words"]+=len(tokens) if state=="closed_assumption" else 0
    result={"cpWER":cpwer(reference,hypothesis,complete_reference=truth["complete_reference"]),"word_counts":dict(counts)}
    if truth["complete_reference"] and reference:
        fixed={profile(k):v for k,v in reference.items()}
        errors=sum(edit_distance(fixed.get(k,[]),named.get(k,[])) for k in set(fixed)|set(named))
        denominator=sum(map(len,fixed.values()))
        result["fixed_named_attributed_WER"]={"reference_words":denominator,"errors":errors,"WER":errors/denominator,
            "scope":"no identity permutation; closed assumptions included separately from verified labels; Unknown is a hypothesis stream so misattribution can count deletion+insertion"}
    else:result["fixed_named_attributed_WER"]={"WER":None,"reason":"EMPTY_OR_INCOMPLETE_REFERENCE"}
    return result


def score(observer_dir,job_id,truth_path,runtime_events=None):
    observer_dir=Path(observer_dir)
    observation=load(observer_dir/"OBSERVER_RESULT.json")
    admission=load(observer_dir/"OBSERVER_ADMISSION.json")
    truth=next(t for t in load(truth_path)["cells"] if t["job_id"]==job_id)
    duration=truth["frames"]/16000
    embeddings=lines(observer_dir/"n2_actual_embedding_windows.jsonl")
    decisions=lines(observer_dir/"n2_gallery_decisions.jsonl")
    condition_entries={c["gallery_id"]:c for c in admission["conditions"]}
    by_gallery=defaultdict(list)
    for row in decisions:by_gallery[row["gallery_id"]].append(row)
    predictions,native_receipt=native_activity(observer_dir,runtime_events,duration)
    references=[{"start":a/16000,"end":b/16000,"label":t["identity"]} for t in truth["turns"] for a,b in t["activity_ranges_samples_estimated"]]
    if native_receipt["native_frames"]:
        activity=activity_metrics(references,predictions,duration,complete_reference=truth["complete_reference"],collar_s=0)
        collar_sensitivity=activity_metrics(references,predictions,duration,complete_reference=truth["complete_reference"],collar_s=0.25)
    else:
        activity={"status":"UNAVAILABLE_FULL_ANONYMOUS_ACTIVITY_TIMELINE_NOT_RECORDED","approximate_activity_DER":None,"approximate_activity_JER":None}
        collar_sensitivity=dict(activity)
    windows=[{"start":e["source_start_sec"],"end":e["source_end_sec"],"label":e.get("tracker_id")} for e in embeddings]
    # Coarse tracking diagnostics use actual chosen-window/decision support;
    # this proxy is never promoted to full diarization activity truth.
    track_proxy=[]
    if by_gallery:
        first=next(iter(by_gallery.values()))
        track_proxy=merge_segments([{"start":r["source_start_sec"],"end":r["source_end_sec"],"label":str(r["actual_tracker_id"])} for r in first if r["actual_tracker_id"] is not None])
    coverage=turn_coverage(truth["turns"],predictions or track_proxy,windows)
    coverage["evidence_availability_scope"]="any positive intersection with any emitted embedding window, including contaminated/other-track windows; not usable naming coverage"
    coverage["track_scope"]="native_activity" if predictions else "coarse_actual_embedding_decision_window_proxy"
    coverage.pop("mapped_turns_evaluator_only",None)
    condition_results=[]
    for condition in observation["conditions"]:
        gid=condition["gallery_id"];entry=condition_entries[gid]
        gallery=load(entry["gallery"]["path"]);members={p["profile_id"] for p in gallery["profiles"]}
        counts=Counter()
        for row in by_gallery[gid]:
            identities={t["identity"] for t in truth["turns"] if any(min(b/16000,row["source_end_sec"])>max(a/16000,row["source_start_sec"]) for a,b in t["activity_ranges_samples_estimated"])}
            counts["actual_query_windows"]+=1
            if len(identities)!=1:
                counts["multiple_reference_identity_windows" if identities else "no_reference_activity_windows"]+=1
                continue
            expected=profile(next(iter(identities)));known=expected in members
            counts["pure_reference_known_windows" if known else "pure_reference_stranger_windows"]+=1
            decision=row["decision"];identity=decision["identity"]
            scores=identity.get("scores",[])
            if known and scores:counts["uncalibrated_top1_correct_known_windows"]+=scores[0]["profile_id"]==expected
            predicted=decision.get("known_profile_id")
            state=decision.get("naming_state")
            if predicted:
                prefix="closed_assumption" if state=="closed_assumption" else "verified_name"
                counts[prefix+"_windows"]+=1
                counts[prefix+"_correct_windows"]+=predicted==expected
                counts[prefix+"_wrong_windows"]+=predicted!=expected
                counts[prefix+"_stranger_false_known_windows"]+=not known
            else:counts["unknown_rejected_windows"]+=1
        rows=load(condition["rows_path"])
        if "stages_path" in condition:
            stages=load(condition["stages_path"])
            stage_metrics={stage:word_metrics(stages[stage],truth) for stage in ["first_visible","first_final","latest"]}
            stage_scope="first_visible uses initial hypotheses against full reference: diagnostic only; first_final/latest separate; shadow display timing modelled"
        else:
            stage_metrics={"latest":word_metrics(rows,truth),"first_visible":{"status":"UNAVAILABLE_FULL_STAGE_SNAPSHOT_NOT_RECORDED"},"first_final":{"status":"UNAVAILABLE_FULL_STAGE_SNAPSHOT_NOT_RECORDED"}}
            stage_scope="older observer retained span history but not complete stage snapshots; do not infer missing stages"
        condition_results.append({"gallery_id":gid,"mode":entry["mode"],"domain":entry["domain"],"position":entry["position"],"stream":entry["stream"],
                                  "intended_members":entry["intended_size"],"available_members":entry["available_size"],
                                  "absent_enrolled_members":len(members-{profile(t["identity"]) for t in truth["turns"]}),
                                  "naming_window_counts":dict(counts),"naming_truth_scope":"known-reference activity only; missing ambient truth prevents absolute purity claim" if not truth["complete_reference"] else "estimated reference activity, pure single-identity windows only",
                                  "source_turn_denominator":len(truth["turns"]),"stages":stage_metrics,"stage_scope":stage_scope,
                                  "raw_words_equal_observer_base":condition["raw_words_equal_observer_base"],"formatted_words_equal_observer_base":condition["formatted_words_equal_observer_base"]})
    report={"schema":"n2-runtime-observer-score-v2","status":"ACTUALLY_SCORED_SAVED_RUNTIME_EVIDENCE","job_id":job_id,
            "encoder":observation["encoder"],"reference_class":truth["reference_class"],"screen48":truth["screen48"],
            "truth":bind(truth_path),"observer_result":bind(observer_dir/"OBSERVER_RESULT.json"),"scoring_code":bind(__file__),
            "activity":activity,"activity_collar_0p25_sensitivity":collar_sensitivity,
            "protocol_amendment":bind(HERE/"PROTOCOL_AMENDMENT_01.json"),
            "native_frame_support":native_receipt,"turn_and_evidence_coverage":coverage,"conditions":condition_results,
            "primary_actual_latest_words":word_metrics(load(observer_dir/"ACTUAL_FINAL_ROWS.json"),truth),
            "actual_vs_clone_raw_invariance":observation["actual_rows_equal_observer_base_raw"],"actual_vs_clone_formatted_invariance":observation["actual_rows_equal_observer_base_formatted"],
            "physical_timing":"NOT_MEASURED","tcpWER":"UNAVAILABLE_NO_EXACT_WORD_REFERENCES"}
    output=observer_dir/"EVALUATOR_SCORE_V2.json"
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return report


def score_activity_attempt(attempt_dir,job_id,truth_path):
    """No-gallery attempt: score actual Controller rows/native activity only."""
    attempt=Path(attempt_dir)
    truth=next(t for t in load(truth_path)["cells"] if t["job_id"]==job_id)
    duration=truth["frames"]/16000
    predictions,native_receipt=native_activity(attempt/"galleries",attempt/"RUNTIME_EVENTS.jsonl",duration)
    references=[{"start":a/16000,"end":b/16000,"label":t["identity"]} for t in truth["turns"] for a,b in t["activity_ranges_samples_estimated"]]
    if native_receipt["native_frames"]:
        metrics={str(collar):activity_metrics(references,predictions,duration,complete_reference=truth["complete_reference"],collar_s=collar) for collar in [0,0.25]}
    else:metrics={str(collar):{"status":"UNAVAILABLE_FULL_ANONYMOUS_ACTIVITY_TIMELINE_NOT_RECORDED","approximate_activity_DER":None,"approximate_activity_JER":None} for collar in [0,0.25]}
    snapshot=load(attempt/"FINAL_SNAPSHOT.json")
    events=lines(attempt/"RUNTIME_EVENTS.jsonl")
    windows=[{"start":r["payload"]["source_start_sec"],"end":r["payload"]["source_end_sec"],"label":r["payload"].get("tracker_id")} for r in events if r["event_type"]=="research_embedding"]
    coverage=turn_coverage(truth["turns"],predictions,windows) if predictions else {"status":"UNAVAILABLE_ACTIVITY_ONLY; embedding-window proxy omitted in no-gallery mode","source_turn_denominator":len(truth["turns"]),"embedding_calls":len(windows)}
    coverage.pop("mapped_turns_evaluator_only",None)
    coverage["evidence_availability_scope"]="any positive intersection with any emitted window, not usable naming coverage"
    report={"schema":"n2-runtime-activity-only-score-v2","status":"ACTUALLY_SCORED_SAVED_RUNTIME_EVIDENCE","job_id":job_id,
            "reference_class":truth["reference_class"],"activity":metrics["0"],"activity_collar_0p25_sensitivity":metrics["0.25"],
            "native_frame_support":native_receipt,"turn_and_evidence_coverage":coverage,
            "actual_latest_words":word_metrics(snapshot["rows"],truth),"naming_metrics":"NOT_RUN_NO_GALLERY_OBSERVER",
            "truth":bind(truth_path),"runtime_events":bind(attempt/"RUNTIME_EVENTS.jsonl"),"final_snapshot":bind(attempt/"FINAL_SNAPSHOT.json"),
            "protocol_amendment":bind(HERE/"PROTOCOL_AMENDMENT_01.json"),"scoring_code":bind(__file__)}
    (attempt/"EVALUATOR_ACTIVITY_SCORE_V2.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--observer-dir")
    inputs.add_argument("--attempt-dir",help="No-gallery runtime attempt with FINAL_SNAPSHOT and RUNTIME_EVENTS")
    parser.add_argument("--job-id",required=True)
    parser.add_argument("--truth",default="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/EVALUATOR_TRUTH.json")
    parser.add_argument("--runtime-events")
    args=parser.parse_args()
    result=score_activity_attempt(args.attempt_dir,args.job_id,args.truth) if args.attempt_dir else score(args.observer_dir,args.job_id,args.truth,args.runtime_events)
    print(json.dumps({"status":result["status"],"job_id":result["job_id"],"activity":result["activity"],"coverage":result["turn_and_evidence_coverage"]},indent=2))
