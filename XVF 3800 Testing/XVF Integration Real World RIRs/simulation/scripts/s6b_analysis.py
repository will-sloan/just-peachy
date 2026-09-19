"""Score S6B predictions without runtime truth access. See README_S6B_ANALYSIS.md."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import time
for _pool in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[_pool]="1"
import numpy as np
from scipy.optimize import linear_sum_assignment
from s6a_text_metrics import score_scene, reference_layout, normalize
from s6a_cue_score import tracking_metrics, state_intersections
from s6a_support_metrics import union,intersection,subtract,samples,contained,mapped_ranges,validate_support
from s6a_baseline_results import dependency_plan,conditional_uncertainty

SIM=Path(__file__).resolve().parents[1]
DEFAULT_REPORT=SIM/"reports/S6B/20260909T230840Z"
COMPLETE={"PRIMARY_NONOVERLAP","COMPLETE_OVERLAP"}
BIN_NAMES=("<1s","1-<2s",">=2s")
SCHEMA="jp_s6b_analysis_v1"
def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def bind(path,expected=None):
    p=Path(path);raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if expected is not None and sha!=expected:raise ValueError("Changed declared input: "+str(p))
    return dict(path=str(p.resolve()),sha256=sha,bytes=len(raw))
def verified(b):
    raw=Path(b["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=b["sha256"]:raise ValueError("Changed declared input: "+b["path"])
    return json.loads(raw)
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def csv_write(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def rate(n,d):return n/d if d else None
def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def quantiles(values):
    good=[float(v) for v in values if finite(v)]
    return dict(count=len(values),observed=len(good),missing=len(values)-len(good),
                p50=float(np.percentile(good,50)) if good else None,p90=float(np.percentile(good,90)) if good else None,
                p95=float(np.percentile(good,95)) if good else None,maximum=max(good,default=None))
def duration_assignment(turns):
    """Global one-to-one duration mapping, with alternate-optimum ambiguity visible.

    This is offline scoring only. Add dummy rows/columns so an unmatched label
    never has to be paired with an unrelated speaker. A tied optimum is not
    promoted to a correctness claim.
    """
    speakers=sorted({r["speaker_key"] for r in turns})
    labels=sorted({k for r in turns for k,v in r.get("label_samples",{}).items() if k!="Unknown" and v>0})
    if not labels:return dict(mapping={},ambiguous_labels=[],unmapped_labels=[],objective_samples=0)
    mat=np.zeros((len(labels)+len(speakers),)*2,dtype=np.int64)
    li={x:i for i,x in enumerate(labels)};si={x:i for i,x in enumerate(speakers)}
    for r in turns:
        for label,n in r.get("label_samples",{}).items():
            if label in li:mat[li[label],si[r["speaker_key"]]]+=int(n)
    ix,jx=linear_sum_assignment(-mat);best=int(mat[ix,jx].sum());mapping={};ambiguous=[];unmapped=[]
    assigned=dict(zip(ix,jx))
    for label,i in li.items():
        j=assigned[i]
        if j>=len(speakers) or mat[i,j]<=0:unmapped.append(label);continue
        alt=mat.copy();alt[i,j]=-int(mat.sum())-1
        ai,aj=linear_sum_assignment(-alt)
        if int(alt[ai,aj].sum())==best:ambiguous.append(label)
        else:mapping[label]=speakers[j]
    return dict(mapping=mapping,ambiguous_labels=ambiguous,unmapped_labels=unmapped,objective_samples=best,
                scope="One global duration-Hungarian mapping per scene over sole-active reference support; ties remain ambiguous. Not online identity truth.")

def validate_prediction(value):
    if value.get("status")!="COMPLETE":raise ValueError("Unsuccessful prediction cannot be scored as empty text")
    if not finite(value.get("duration_sec")) or value["duration_sec"]<=0:raise ValueError("Invalid measured duration")
    keys=("final_transcripts_first","final_transcripts_latest","final_transcripts_first_display")
    signatures=[]
    for key in keys:
        fs=value[key];ids=[str(f["utterance_index"]) for f in fs]
        if len(ids)!=len(set(ids)):raise ValueError("Duplicate final utterance identity")
        if any(not isinstance(f.get("text"),str) for f in fs):raise ValueError("Final words missing")
        signatures.append([(str(f["utterance_index"]),f["text"]) for f in fs])
    if signatures[1:]!=signatures[:1]*2:raise ValueError("Identity revision altered final lexical content/order")
    previous=-math.inf
    for d in value["decisions"]:
        for k in ("source_start_sec","source_end_sec","available_at_sec"):
            if not finite(d.get(k)):raise ValueError("Invalid causal decision span/availability")
        if d["source_start_sec"]>d["source_end_sec"] or d["available_at_sec"]+1e-8<d["source_end_sec"]:raise ValueError("Decision available before evidence end")
        if d["available_at_sec"]<previous:raise ValueError("Decisions not in causal availability order")
        if not isinstance(d.get("anonymous_label"),str):raise ValueError("Missing explicit anonymous decision label")
        previous=d["available_at_sec"]
    for f in value["features"]:
        a,b=f["source_start_sec"],f["source_end_sec"]
        if not finite(a) or not finite(b) or a<0 or b<=a or b>value["duration_sec"]+1e-6:raise ValueError("Invalid admitted feature span")
        available=f.get("available_at_sec")
        if available is not None and (not finite(available) or available+1e-8<b):raise ValueError("Feature available before source end")

def evidence_turns(value,support,track):
    length=round(value["duration_sec"]*16000);stream=value["stream"]
    shift=support["output_mappings"][stream]["source_with_rir_to_output_offset_samples"]
    features=value["features"];windows=[[round(f["source_start_sec"]*16000),round(f["source_end_sec"]*16000)] for f in features]
    amap=duration_assignment(track["turns"]);turns=[]
    mapped={}
    if shift is not None:
        for t in support["turns"]:
            mapped[t["segment_index"]]={k:mapped_ranges(t[k],shift,length) for k in ("active_ranges","file_support","support_ranges")}
    purity=Counter()
    if shift is not None:
        for w in windows:
            people={t["speaker_key"] for t in support["turns"] if samples(intersection([w],mapped[t["segment_index"]]["file_support"]))}
            if len(people)>1:purity["cross_person_file_envelope_windows"]+=1
            elif len(people)==1:purity["one_person_intersection_windows"]+=1
            else:purity["outside_annotated_source_windows"]+=1
    for t in track["turns"]:
        row=dict(t);label=t["modal_label"]
        row["duration_mapping_status"]="UNAVAILABLE_ALIGNMENT" if shift is None else "UNKNOWN_OR_TIED_TURN_MODE" if label is None else "AMBIGUOUS_GLOBAL_OPTIMUM" if label in amap["ambiguous_labels"] else "MAPPED" if label in amap["mapping"] else "UNMAPPED"
        row["modal_duration_mapped_correct"]=amap["mapping"].get(label)==t["speaker_key"] if row["duration_mapping_status"]=="MAPPED" else None
        row["any_known_label_present"]=(t.get("known_samples") or 0)>0 if shift is not None else None
        row["contained_embedding_count"]=None;row["first_contained_embedding_available_wait_sec"]=None
        row["first_known_label_support_wait_sec"]=None;row["first_correct_mapped_support_wait_sec"]=None
        row["duration_mapped_correct_samples"]=None
        if shift is not None:
            own=mapped[t["segment_index"]];others=union([r for sid,m in mapped.items() if sid!=t["segment_index"] for r in m["file_support"]])
            match=[i for i,w in enumerate(windows) if contained(w,own["file_support"]) and not samples(intersection([w],others))]
            row["contained_embedding_count"]=len(match)
            origin=own["file_support"][0][0]/16000 if own["file_support"] else None
            waits=[features[i].get("available_at_sec")-origin for i in match if finite(features[i].get("available_at_sec")) and origin is not None]
            row["first_contained_embedding_available_wait_sec"]=min(waits,default=None)
            otheractive=union([r for sid,m in mapped.items() if sid!=t["segment_index"] for r in m["active_ranges"]])
            sole=subtract(own["active_ranges"],otheractive)
            control="one_person" if value["profile_id"]=="B37" else "all_unknown" if value["profile_id"]=="B38" else None
            intervals=[x for a,b in sole for x in state_intersections(value["decisions"],a,b,control=control)]
            known=[a/16000-origin for a,b,l in intervals if l!="Unknown" and origin is not None]
            correct=[a/16000-origin for a,b,l in intervals if amap["mapping"].get(l)==t["speaker_key"] and origin is not None]
            row["first_known_label_support_wait_sec"]=min(known,default=None)
            row["first_correct_mapped_support_wait_sec"]=min(correct,default=None)
            row["duration_mapped_correct_samples"]=sum(n for l,n in t.get("label_samples",{}).items() if amap["mapping"].get(l)==t["speaker_key"])
            if control is not None:
                row["first_known_label_support_wait_sec"]=None
                row["first_correct_mapped_support_wait_sec"]=None
        turns.append(row)
    return turns,amap,dict(purity),dict(embedding_calls=len(windows),embedding_total_window_sec=sum(b-a for a,b in windows)/16000,
        embedding_union_sec=samples(windows)/16000,embedding_availability_missing=sum(not finite(f.get("available_at_sec")) for f in features))

def region_metrics(value,support):
    shift=support["output_mappings"][value["stream"]]["source_with_rir_to_output_offset_samples"]
    length=round(value["duration_sec"]*16000)
    intervals=lambda rows:[[round(r["source_start_sec"]*16000),round(r["source_end_sec"]*16000)] for r in rows]
    observed=union(intervals(value["segmentation"]))
    speech=union(intervals([r for r in value["segmentation"] if r["speech"]]))
    overlap=union(intervals([r for r in value["segmentation"] if r["overlap"]]))
    embeddings=union(intervals(value["features"]))
    output=[]
    for name,source in support["regions_source_with_rir_samples"].items():
        mapped=mapped_ranges(source,shift,length) if shift is not None else None
        output.append(dict(region=name,mapping_available=shift is not None,
            support_samples=samples(mapped) if mapped is not None else None,
            observed_segmentation_samples=samples(intersection(mapped,observed)) if mapped is not None else None,
            speech_flag_samples=samples(intersection(mapped,speech)) if mapped is not None else None,
            overlap_flag_samples=samples(intersection(mapped,overlap)) if mapped is not None else None,
            embedding_union_intersection_samples=samples(intersection(mapped,embeddings)) if mapped is not None else None))
    return output

def analyze(value,scene,support,allowed):
    validate_prediction(value);validate_support(scene,support)
    text_scores={}
    for name,key in (("first_final","final_transcripts_first"),("latest_revised","final_transcripts_latest"),("first_display_label_final_words","final_transcripts_first_display")):
        fs=[dict(f,speaker=f.get("speaker") or "Unknown") for f in value[key]]
        text_scores[name]=score_scene(scene,dict(state="COMPLETED",failure_events=[],final_transcripts=fs),allowed_ids=allowed,duration_s=value["duration_sec"])
    # Exact lexical identity invariant: three views differ in labels only.
    if len({digest(x["text"]) for x in text_scores.values()})!=1:raise ValueError("Label views changed lexical score")
    for name,x in text_scores.items():
        if x["population"] in COMPLETE and x["attributed_cpwer"].get("status")!="SCORED_DIAGNOSTIC":raise RuntimeError("cpWER unavailable: "+str(x["attributed_cpwer"]))
        x["attributed_cpwer"]["s6b_label_view"]=name
        x["attributed_cpwer"]["scope"]=("Final recognized words grouped by "+name+". One scene-global minimum word-cost speaker permutation; anonymous Unknown is an emitted label, not successful identity. No DER or exact word-timing claim.")
    control="one_person" if value["profile_id"]=="B37" else "all_unknown" if value["profile_id"]=="B38" else None
    track=tracking_metrics(support,value["stream"],value["decisions"],round(value["duration_sec"]*16000),control=control)
    turns,amap,purity,windowcounts=evidence_turns(value,support,track)
    expected_turns={(i,u["source_id"]) for i,u in enumerate(scene["segments"]) if u["kind"]=="utterance"}
    if {(t["segment_index"],t["source_id"]) for t in turns}!=expected_turns or len(turns)!=len(expected_turns):
        raise ValueError("Source-turn preservation failure")
    events=value["transcript_events"]
    evcounts=Counter(e["event_type"] for e in events)
    lineage=Counter(str(e.get("type",e.get("event",e.get("kind","UNSPECIFIED")))) for d in value["decisions"] for e in d.get("lineage",[]))
    finaltimes=[f.get("first_final_time") for f in value["final_transcripts_first"]]
    displaytimes=[f.get("first_display_time") for f in value["final_transcripts_first"]]
    revision_delays=[f.get("latest_label_time")-f["first_final_time"] for f in value["final_transcripts_latest"] if finite(f.get("latest_label_time")) and finite(f.get("first_final_time")) and f["latest_label_time"]>f["first_final_time"]]
    utterances=[x for x in scene["segments"] if x["kind"]=="utterance"]
    strata=dict(corpus=sorted({x["dataset"] for x in utterances}) or ["NO_DELIBERATE_SPEECH"],
        source_quality=sorted({x["quality_partition"] for x in utterances}) or ["NO_DELIBERATE_SPEECH"],
        source_level_db=sorted({str(x.get("relative_source_db","UNSPECIFIED")) for x in utterances}) or ["NO_DELIBERATE_SPEECH"],
        noise_category=sorted({x.get("category","UNSPECIFIED") for x in scene["segments"] if x["kind"]=="real_noise"}) or ["NO_ADDED_REAL_NOISE"],
        snr_db=[str((scene.get("noise_details") or {}).get("requested_snr_db","NOT_APPLICABLE"))],
        receiver_orientation=[str(scene["receiver_configuration"]["orientation"])],
        obstructed=[str(scene["receiver_configuration"]["obstructed"])])
    return dict(case_id=value["case_id"],stream=value["stream"],profile_id=value["profile_id"],recipe_id=value["recipe_id"],strata=strata,
        population=text_scores["first_final"]["population"],room=scene["receiver_configuration"]["room_table"],family_id=scene["family_id"],historical_split=scene["split"],
        duration_sec=value["duration_sec"],text_metrics=text_scores,tracking_metrics={k:v for k,v in track.items() if k!="turns"},turns=turns,duration_assignment=amap,
        embedding_purity=purity,regions=region_metrics(value,support),**windowcounts,decision_count=len(value["decisions"]),segmentation_calls=len(value["segmentation"]),
        lineage_counts=dict(lineage),transcript_event_counts=dict(evcounts),snapshot=value["snapshot"],
        policy_wall_sec=value["policy_wall_sec"],recipe_costs=value["recipe_costs"],final_utterances=len(value["final_transcripts_first"]),
        first_display_modeled_times=quantiles(displaytimes),first_final_modeled_times=quantiles(finaltimes),post_final_revision_delay_sec=quantiles(revision_delays),
        normalized_final_text=text_scores["first_final"]["text"]["hypothesis_normalized"],
        timing_scope="Source-start warm modeled upstream availability. Policy replay wall time is separate and is not charged as native execution latency. Whole-file-support waits are conditional diagnostics with missing counts; historical B00 availability may be unavailable. No phonetic-onset or CM5 latency claim.")

def counts_for(metric):
    return metric.get("word_counts") or {}
def scene_row(result):
    row={k:result[k] for k in ("case_id","stream","profile_id","recipe_id","population","room","family_id","historical_split","duration_sec","embedding_calls","embedding_total_window_sec","embedding_union_sec","embedding_availability_missing","segmentation_calls","decision_count","policy_wall_sec","final_utterances")}
    t=result["text_metrics"]["first_final"]
    lexical=t["target_only_text"] if t["population"]=="INCOMPLETE_REFERENCE" and "target_only_text" in t else t["overlap_mimo"] if t["population"]=="COMPLETE_OVERLAP" else t["text"]
    row["lexical_scope"]="target_only" if t["population"]=="INCOMPLETE_REFERENCE" else "overlap_mimo" if t["population"]=="COMPLETE_OVERLAP" else "primary" if t["population"]=="PRIMARY_NONOVERLAP" else "strict_empty"
    for k,v in counts_for(lexical).items():row["word_"+k]=v
    for k,v in (t["text"].get("character_counts") or {}).items():row["char_"+k]=v if t["population"]=="PRIMARY_NONOVERLAP" else None
    for view,x in result["text_metrics"].items():
        row["cp_"+view+"_status"]=x["attributed_cpwer"]["status"]
        for k,v in counts_for(x["attributed_cpwer"]).items():row["cp_"+view+"_"+k]=v
    row["empty_insertions"]=t["text"].get("empty_reference_insertions")
    row["tracking_status"]=result["tracking_metrics"]["status"]
    row.update({k:v for k,v in result["tracking_metrics"].items() if isinstance(v,(int,float)) or v is None})
    row["lineage_counts"]=result["lineage_counts"];row["transcript_event_counts"]=result["transcript_event_counts"]
    row["recipe_costs"]=result["recipe_costs"]
    row["strata"]=result["strata"]
    row["normalized_final_text"]=result["normalized_final_text"]
    return row

def pool(chosen,pid,stream,population):
    p=dict(profile_id=pid,stream=stream,population=population,scenes=len(chosen),duration_sec=sum(r["duration_sec"] for r in chosen))
    p["word_pool_scope"]="Primary serialized WER plus complete-overlap MIMO counts; use separate population rows for named lexical metrics" if population=="ALL_COMPLETE_NONEMPTY" else population
    prefixes=["word_","char_","cp_first_final_","cp_latest_revised_","cp_first_display_label_final_words_"]
    for prefix in prefixes:
        fields=sorted({k for r in chosen for k,v in r.items() if k.startswith(prefix) and finite(v)})
        for key in fields:p[key]=sum(r.get(key) or 0 for r in chosen)
        denom=p.get(prefix+("reference_characters" if prefix=="char_" else "reference_words"),0)
        p[prefix+"rate"]=rate(p.get(prefix+"errors",0),denom)
        p[prefix+"scored_scenes"]=sum(finite(r.get(prefix+"errors")) for r in chosen)
    for key in ("source_turns","supported_turns","unknown_turns","sole_active_samples","known_samples","unknown_samples","false_merge_samples","return_consistent","return_inconsistent","return_unknown","embedding_calls","embedding_total_window_sec","embedding_union_sec","embedding_availability_missing","segmentation_calls","decision_count","policy_wall_sec","final_utterances"):
        p[key]=sum(r.get(key) or 0 for r in chosen)
    p["alignment_unavailable"]=sum(r["tracking_status"]=="UNAVAILABLE_OUTPUT_ALIGNMENT" for r in chosen)
    p["unknown_fraction"]=rate(p["unknown_samples"],p["sole_active_samples"])
    p["mixed_fraction_all_sole"]=rate(p["false_merge_samples"],p["sole_active_samples"])
    p["mixed_fraction_known"]=rate(p["false_merge_samples"],p["known_samples"])
    p["unknown_plus_mixed_fraction"]=rate(p["unknown_samples"]+p["false_merge_samples"],p["sole_active_samples"])
    p["empty_insertions"]=sum(r.get("empty_insertions") or 0 for r in chosen) if population=="STRICT_EMPTY_REFERENCE" else None
    p["empty_insertions_per_minute"]=rate(p["empty_insertions"],p["duration_sec"]/60) if p["empty_insertions"] is not None else None
    if population=="STRICT_EMPTY_REFERENCE":p["word_rate"]=None
    p["lineage_counts"]=dict(sum((Counter(r["lineage_counts"]) for r in chosen),Counter()))
    p["transcript_event_counts"]=dict(sum((Counter(r["transcript_event_counts"]) for r in chosen),Counter()))
    return p

def summarize(scene_rows,turn_rows):
    output=[];short=[]
    groups=sorted({(r["profile_id"],r["stream"]) for r in scene_rows})
    for pid,stream in groups:
        selected=[r for r in scene_rows if (r["profile_id"],r["stream"])==(pid,stream)]
        for population in sorted({r["population"] for r in selected})+["ALL_COMPLETE_NONEMPTY"]:
            chosen=[r for r in selected if r["population"] in COMPLETE] if population=="ALL_COMPLETE_NONEMPTY" else [r for r in selected if r["population"]==population]
            output.append(pool(chosen,pid,stream,population))
        selected_turns=[r for r in turn_rows if (r["profile_id"],r["stream"])==(pid,stream)]
        for population in ["ALL_COMPLETE_NONEMPTY","PRIMARY_NONOVERLAP","COMPLETE_OVERLAP","INCOMPLETE_REFERENCE"]:
            for bin_name in BIN_NAMES:
                ts=[t for t in selected_turns if t["whole_clip_bin"]==bin_name and (t["population"] in COMPLETE if population=="ALL_COMPLETE_NONEMPTY" else t["population"]==population)]
                if not ts:continue
                sole=sum(t.get("sole_active_samples") or 0 for t in ts);known=sum(t.get("known_samples") or 0 for t in ts);unknown=sum(t.get("unknown_samples") or 0 for t in ts)
                short.append(dict(profile_id=pid,stream=stream,population=population,duration_bin=bin_name,source_turns=len(ts),
                    scene_count=len({t["case_id"] for t in ts}),mapping_unavailable=sum(not t["mapping_available"] for t in ts),
                    known_modal_turns=sum(t["modal_label"] is not None for t in ts),any_known_support_turns=sum(t["any_known_label_present"] is True for t in ts),
                    duration_mapping_ambiguous_turns=sum(t["duration_mapping_status"]=="AMBIGUOUS_GLOBAL_OPTIMUM" for t in ts),
                    duration_mapped_correct_modal_turns=sum(t["modal_duration_mapped_correct"] is True for t in ts),
                    duration_mapped_incorrect_modal_turns=sum(t["modal_duration_mapped_correct"] is False for t in ts),
                    duration_mapping_unavailable_or_unknown_turns=sum(t["modal_duration_mapped_correct"] is None for t in ts),
                    contained_embedding_turns=sum((t["contained_embedding_count"] or 0)>0 for t in ts),
                    no_contained_embedding_turns=sum(t["contained_embedding_count"]==0 for t in ts),
                    contained_embedding_mapping_unavailable=sum(t["contained_embedding_count"] is None for t in ts),
                    sole_active_samples=sole,known_samples=known,unknown_samples=unknown,unknown_fraction=rate(unknown,sole),
                    duration_mapped_correct_samples=sum(t["duration_mapped_correct_samples"] or 0 for t in ts),
                    contained_evidence_wait=quantiles([t["first_contained_embedding_available_wait_sec"] for t in ts]),
                    known_support_wait=quantiles([t["first_known_label_support_wait_sec"] for t in ts]),
                    correct_mapped_support_wait=quantiles([t["first_correct_mapped_support_wait_sec"] for t in ts])))
    return output,short

def resource_and_strata(scene_rows):
    """Keep unique neural recipe cost separate from each policy's reused evidence."""
    unique={};membership=defaultdict(set);strata=[]
    for r in scene_rows:
        key=(r["recipe_id"],r["case_id"],r["stream"])
        if key in unique and unique[key]["recipe_costs"]!=r["recipe_costs"]:
            raise ValueError("same declared neural recipe has inconsistent cost receipt")
        unique.setdefault(key,r);membership[key].add(r["profile_id"])
    resources=[]
    for key,r in sorted(unique.items()):
        resources.append(dict(recipe_id=key[0],case_id=key[1],stream=key[2],profile_reusers=sorted(membership[key]),
            duration_sec=r["duration_sec"],embedding_calls=r["embedding_calls"],segmentation_calls=r["segmentation_calls"],
            recipe_costs=r["recipe_costs"],cost_scope="Exact named upstream recipe record, counted once across tracker reusers; inherited B00 costs unavailable, not zero execution."))
    for pid,stream in sorted({(r["profile_id"],r["stream"]) for r in scene_rows}):
        selected=[r for r in scene_rows if (r["profile_id"],r["stream"])==(pid,stream)]
        groups=defaultdict(list)
        for r in selected:
            for dimension,labels in dict(room=[r["room"]],family=[r["family_id"]],historical_split=[r["historical_split"]],**r["strata"]).items():
                for label in labels:groups[dimension,str(label),r["population"]].append(r)
        for (dimension,label,population),chosen in sorted(groups.items()):
            item=pool(chosen,pid,stream,population)
            item.update(stratum_dimension=dimension,stratum_value=label,membership_scope="Whole-scene membership; multi-corpus/quality/level/noise scenes may appear in more than one value. Do not sum overlapping strata.")
            strata.append(item)
    return resources,strata

def paired_comparisons(scene_rows,registry,dependency,bootstrap=True):
    by={(r["profile_id"],r["stream"],r["case_id"]):r for r in scene_rows};profiles=sorted({r["profile_id"] for r in scene_rows})
    parents={r["profile_id"]:r.get("comparison_parent") or r.get("parent") for r in registry}
    choices=[]
    for pid in profiles:
        choices.append((pid,"O0",pid,"O1","same_profile_output"))
        parent=parents.get(pid)
        if parent in profiles:
            for stream in ("O0","O1"):choices.append((parent,stream,pid,stream,"candidate_minus_parent"))
    out=[];uncertainties=[]
    allcases=sorted({r["case_id"] for r in scene_rows})
    for lp,ls,rp,rs,kind in choices:
        pairs=[(by.get((lp,ls,c)),by.get((rp,rs,c))) for c in allcases]
        good=[(a,b) for a,b in pairs if a is not None and b is not None]
        for population in ("PRIMARY_NONOVERLAP","COMPLETE_OVERLAP","INCOMPLETE_REFERENCE","STRICT_EMPTY_REFERENCE","ALL_COMPLETE_NONEMPTY"):
            chosen=[(a,b) for a,b in good if a["population"] in COMPLETE] if population=="ALL_COMPLETE_NONEMPTY" else [(a,b) for a,b in good if a["population"]==population]
            for prefix in ("word_","cp_first_final_","cp_latest_revised_","cp_first_display_label_final_words_"):
                valid=[(a,b) for a,b in chosen if finite(a.get(prefix+"errors")) and finite(b.get(prefix+"errors"))]
                if not valid:continue
                denoms=[(a.get(prefix+"reference_words",0),b.get(prefix+"reference_words",0)) for a,b in valid]
                if any(a!=b for a,b in denoms):raise ValueError("Paired scoring denominator mismatch")
                den=sum(a for a,b in denoms);le=sum(a[prefix+"errors"] for a,b in valid);re=sum(b[prefix+"errors"] for a,b in valid)
                rooms=[]
                for room in sorted({a["room"] for a,b in valid}):
                    rows=[(a,b) for a,b in valid if a["room"]==room];d=sum(a.get(prefix+"reference_words",0) for a,b in rows)
                    rooms.append(dict(room=room,scenes=len(rows),reference_words=d,left_errors=sum(a[prefix+"errors"] for a,b in rows),right_errors=sum(b[prefix+"errors"] for a,b in rows),
                        delta_pp=100*sum(b[prefix+"errors"]-a[prefix+"errors"] for a,b in rows)/d if d else None))
                out.append(dict(left_profile=lp,left_stream=ls,right_profile=rp,right_stream=rs,comparison=kind,population=population,metric=prefix.rstrip("_"),
                    paired_scenes=len(valid),unpaired_scene_outputs=len(pairs)-len(good),reference_words=den,left_errors=le,right_errors=re,right_minus_left_errors=re-le,
                    right_minus_left_pp=100*(re-le)/den if den else None,rooms=rooms,equal_room_delta_pp=float(np.mean([r["delta_pp"] for r in rooms if r["delta_pp"] is not None])) if den else None,
                    lexical_changed_scenes=sum(a["normalized_final_text"]!=b["normalized_final_text"] for a,b in valid) if prefix=="word_" else None))
        if bootstrap:
            nativepairs=[dict(case_id=a["case_id"],room=a["room"],O0=dict(text=dict(word_counts={k[5:]:v for k,v in a.items() if k.startswith("word_") and finite(v)})),
                O1=dict(text=dict(word_counts={k[5:]:v for k,v in b.items() if k.startswith("word_") and finite(v)}))) for a,b in good if a["population"]=="PRIMARY_NONOVERLAP"]
            u=conditional_uncertainty(nativepairs,dependency,replicates=2000)
            u.pop("bootstrap_delta_pp",None)
            u.update(left_profile=lp,left_stream=ls,right_profile=rp,right_stream=rs,
                label_contract="Reused pure bootstrap API uses O0=left and O1=right internally, even for two profiles on one tap. All numeric deltas are right minus left.")
            uncertainties.append(u)
    return out,uncertainties

def fixtures():
    good=[dict(speaker_key="a",label_samples={"P":100},modal_label="P"),dict(speaker_key="b",label_samples={"Q":100},modal_label="Q")]
    assert duration_assignment(good)["mapping"]=={"P":"a","Q":"b"}
    tied=[dict(speaker_key="a",label_samples={"P":100},modal_label="P"),dict(speaker_key="b",label_samples={"P":100},modal_label="P")]
    assert duration_assignment(tied)["ambiguous_labels"]==["P"]
    q=quantiles([.2,None,.8]);assert q["missing"]==1 and q["observed"]==2
    fake=dict(status="COMPLETE",duration_sec=2.,decisions=[],features=[],final_transcripts_first=[dict(utterance_index=1,text="keep words")],
        final_transcripts_latest=[dict(utterance_index=1,text="keep words")],final_transcripts_first_display=[dict(utterance_index=1,text="keep words")])
    validate_prediction(fake);fake["final_transcripts_latest"][0]["text"]="changed"
    try:validate_prediction(fake)
    except ValueError:pass
    else:raise AssertionError("revision word mutation accepted")
    return dict(status="PASS",tests=["duration assignment unique mapping","global mapping ties remain ambiguous","missing waits retained","label-only lexical identity invariant"])

def run(args):
    report=args.report;index_path=args.index or report/"PREDICTION_INDEX.json"
    if not index_path.is_absolute():index_path=report/index_path
    output=report/args.output_subdir
    if Path(args.output_subdir).is_absolute() or output.resolve()==report.resolve() or report.resolve() not in output.resolve().parents:
        raise ValueError("--output-subdir must be a new child of the report root")
    index=read(index_path);index_binding=bind(index_path)
    bank_path=SIM/"scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json";bank=read(bank_path)
    if bind(bank_path)["sha256"]!="69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18":raise ValueError("Frozen source bank changed")
    scenes={s["case_id"]:s for s in bank["scenes"]};allowed=frozenset(scenes)
    inputs=read(report/"INPUT_INDEX.json");inputrows={(r["case_id"],r["stream"]):r for r in inputs["rows"]}
    expected={(p,s,c) for p in index["profiles"] for s in ("O0","O1") for c in index["case_ids"]}
    declared=[(r["profile_id"],r["stream"],r["case_id"]) for r in index["rows"]]
    if len(declared)!=len(set(declared)) or not set(declared)<=expected:raise ValueError("Duplicate or unexpected prediction index row")
    if not set(index["case_ids"])<=allowed:raise ValueError("Outside authorized bank")
    if args.require_complete and (set(declared)!=expected or index.get("status")!="COMPLETE"):raise ValueError("Incomplete requested prediction coverage")
    codes=[bind(Path(__file__).parent/name) for name in ("s6b_analysis.py","s6a_text_metrics.py","s6a_cue_score.py","s6a_support_metrics.py","s6a_baseline_results.py","s4_h2_analysis.py","s5_statistics.py")]
    packages={name:version(name) for name in ("numpy","scipy","meeteval")}
    if packages["meeteval"]!="0.4.3":raise RuntimeError("Pinned MeetEval0.4.3 required")
    supports={};records=[];coverage=[];started=time.perf_counter()
    selected=index["rows"][:args.limit] if args.limit else index["rows"]
    for item in selected:
        cid,stream,pid=item["case_id"],item["stream"],item["profile_id"]
        item_status=item.get("status","COMPLETE")
        if item_status!="COMPLETE":
            coverage.append(dict(case_id=cid,stream=stream,profile_id=pid,status=item_status,error="Index declares unsuccessful output"));continue
        try:
            value=verified(item["result"])
            if (value["profile_id"],value["stream"],value["case_id"])!=(pid,stream,cid):raise ValueError("Index/prediction identity mismatch")
            sb=inputrows[cid,stream]["support"]
            if cid not in supports:supports[cid]=verified(sb)["support"]
            identity=dict(prediction=item["result"],support=sb,bank=bind(bank_path),codes=codes,packages=packages,metric_schema=SCHEMA)
            key=digest(identity);target=output/"scores"/pid/cid/(stream+".json")
            if target.exists():
                result=read(target)
                if result["analysis_key"]!=key:raise ValueError("Changed scoring dependency requires a new --output-subdir")
            else:
                result=analyze(value,scenes[cid],supports[cid],allowed)
                result.update(analysis_key=key,analysis_identity=identity)
                save(target,result)
            records.append(result);coverage.append(dict(case_id=cid,stream=stream,profile_id=pid,status="SCORED",result=bind(target)))
        except Exception as exc:
            coverage.append(dict(case_id=cid,stream=stream,profile_id=pid,status="FAILED_ANALYSIS",error=type(exc).__name__+": "+str(exc)))
        if len(coverage)%88==0:
            save(output/"HEARTBEAT.json",dict(scored=len(records),attempted=len(coverage),requested=len(expected),elapsed_sec=time.perf_counter()-started))
            print(json.dumps(dict(phase="S6B_ANALYSIS",scored=len(records),attempted=len(coverage),requested=len(expected))),flush=True)
    present={(r["profile_id"],r["stream"],r["case_id"]) for r in coverage}
    for pid,stream,cid in sorted(expected-present):coverage.append(dict(case_id=cid,stream=stream,profile_id=pid,status="NOT_SCORED_NOT_AVAILABLE_OR_LIMITED"))
    scene_rows=[scene_row(r) for r in records]
    turn_rows=[dict(case_id=r["case_id"],stream=r["stream"],profile_id=r["profile_id"],population=r["population"],
        **{k:v for k,v in t.items() if k!="label_samples"}) for r in records for t in r["turns"]]
    summary,short=summarize(scene_rows,turn_rows)
    resource_rows,strata_rows=resource_and_strata(scene_rows)
    region_rows=[dict(case_id=r["case_id"],stream=r["stream"],profile_id=r["profile_id"],population=r["population"],**region) for r in records for region in r["regions"]]
    registry=read(report/"design/CANDIDATE_REGISTRY.json")["profiles"]
    diagnostics=read(report/"design/LIMITED_DIAGNOSTICS.json")["profiles"] if (report/"design/LIMITED_DIAGNOSTICS.json").exists() else []
    dependency=dependency_plan(scenes,bank["selected_sources"])
    comparisons,uncertainty=paired_comparisons(scene_rows,registry+diagnostics,dependency,bootstrap=not args.no_bootstrap)
    output.mkdir(parents=True,exist_ok=True)
    for name,rs in (("SCENE_RESULTS.csv",scene_rows),("TURN_RESULTS.csv",turn_rows),("PROFILE_RESULTS.csv",summary),("SHORT_REPLY_RESULTS.csv",short),("PAIRED_COMPARISONS.csv",comparisons),("COVERAGE.csv",coverage),("RECIPE_COST_RESULTS.csv",resource_rows),("STRATA_RESULTS.csv",strata_rows),("REGION_RESULTS.csv",region_rows)):
        csv_write(output/name,rs)
    save(output/"PROFILE_RESULTS.json",summary);save(output/"SHORT_REPLY_RESULTS.json",short)
    save(output/"PAIRED_UNCERTAINTY.json",uncertainty);save(output/"DEPENDENCY_PLAN.json",dependency)
    perprofile={p:Counter(r["status"] for r in coverage if r["profile_id"]==p) for p in index["profiles"]}
    full_profiles=[p for p,c in perprofile.items() if c.get("SCORED")==480 and set(index["case_ids"])==allowed]
    failures=[r for r in coverage if r["status"]!="SCORED"]
    receipt=dict(schema=SCHEMA,status="COMPLETE_REQUESTED_INDEX" if len(records)==len(expected) and not failures else "PARTIAL_RESUMABLE",
        index=index_binding,input_index=bind(report/"INPUT_INDEX.json"),codes=codes,packages=packages,tests=fixtures(),requested=len(expected),scored=len(records),unscored=len(failures),
        counts_by_profile={p:dict(c) for p,c in perprofile.items()},all240_two_tap_confirmed_profiles=full_profiles,
        requested_scene_count=len(index["case_ids"]),requested_profiles=index["profiles"],panel=index.get("panel"),
        source_turn_outputs=len(turn_rows),subsecond_complete_source_turn_outputs=sum(r["population"] in COMPLETE and r["whole_clip_bin"]=="<1s" for r in turn_rows),
        results=summary,short_results=short,elapsed_sec=time.perf_counter()-started,
        interpretation="Complete means the declared index was scored, not all240 confirmation unless listed. Failures never become empty ASR. Primary/overlap/incomplete/empty denominators remain separate. No real-world holdout, no DER, no CM5 qualification.",
        unique_recipe_scene_output_records=len(resource_rows),
        tables=[bind(output/name) for name in ("SCENE_RESULTS.csv","TURN_RESULTS.csv","PROFILE_RESULTS.csv","SHORT_REPLY_RESULTS.csv","PAIRED_COMPARISONS.csv","COVERAGE.csv","RECIPE_COST_RESULTS.csv","STRATA_RESULTS.csv","REGION_RESULTS.csv")])
    save(output/"ANALYSIS_RECEIPT.json",receipt)
    if args.require_complete and failures:raise RuntimeError(f"{len(failures)} requested outputs unscored; inspect COVERAGE.csv")
    print(json.dumps({k:receipt[k] for k in ("status","requested","scored","unscored","all240_two_tap_confirmed_profiles")},indent=2))
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--report",type=Path,default=DEFAULT_REPORT)
    p.add_argument("--index",type=Path);p.add_argument("--output-subdir",default="analysis_v1")
    p.add_argument("--require-complete",action="store_true");p.add_argument("--limit",type=int)
    p.add_argument("--no-bootstrap",action="store_true");p.add_argument("--test",action="store_true")
    args=p.parse_args()
    if args.test:print(json.dumps(fixtures(),indent=2));return
    if args.limit is not None and args.limit<=0:p.error("--limit must be positive")
    if args.limit and args.require_complete:p.error("--limit and --require-complete are incompatible")
    run(args)
if __name__=="__main__":main()
