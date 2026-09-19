"""Compact factual S6B component screen; see README_S6B_COMPONENT_SCREEN.md."""
from __future__ import annotations
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from s6b_analysis import read,bind,save,csv_write

SIM=Path(__file__).resolve().parents[1]
POPS=("PRIMARY_NONOVERLAP","COMPLETE_OVERLAP","INCOMPLETE_REFERENCE","STRICT_EMPTY_REFERENCE")
SHORT_FIELDS=("source_turns","contained_embedding_turns","any_known_support_turns","duration_mapped_correct_modal_turns","duration_mapped_incorrect_modal_turns","duration_mapping_unavailable_or_unknown_turns","unknown_fraction")

def native_costs(rows):
    out={}
    grouped=defaultdict(list)
    for r in rows:grouped[r["recipe_id"],r["stream"]].append(r)
    for key,items in grouped.items():
        identities=[(r["case_id"],r["stream"]) for r in items]
        if len(identities)!=len(set(identities)):raise ValueError("Duplicate upstream cost job")
        totals={}
        paths={
            "native_process_cpu_sec":("native_full_engine","process_cpu_sec"),
            "native_accelerated_elapsed_sum_sec":("native_full_engine","elapsed_sec"),
            "bundle_admission_sum_sec":("native_full_engine","separate_bundle_admission_sec"),
            "segmentation_compute_sec":("research_segmentation","compute_sec"),
            "segmentation_postprocess_sec":("research_segmentation","postprocess_compute_sec"),
            "embedding_compute_sec":("research_embedding","compute_sec"),
            "asr_decode_sec":("research_asr_dispatch","compute_sec"),
            "asr_tail_dispatch_sec":("research_asr_tail_dispatch","compute_sec"),
            "asr_eof_drain_sec":("research_asr_drain","compute_sec")}
        costs=[json.loads(r["recipe_costs"]) for r in items]
        for name,(outer,inner) in paths.items():
            values=[r.get(outer,{}).get(inner) for r in costs]
            good=[v for v in values if isinstance(v,(int,float))]
            totals[name]=sum(good) if good else None
            totals[name+"_available_jobs"]=len(good)
        totals.update(upstream_jobs=len(items),audio_duration_sec=sum(float(r["duration_sec"]) for r in items),
                      embedding_calls=sum(int(r["embedding_calls"]) for r in items),
                      segmentation_calls=sum(int(r["segmentation_calls"]) for r in items))
        out[key]=totals
    return out

def build(args):
    report=args.report;analysis=report/args.analysis_subdir;revision=report/args.revision_subdir
    cpdir=report/args.cp_subdir;out=report/args.output_subdir
    if out.resolve()==report.resolve() or report.resolve() not in out.resolve().parents:raise ValueError("Output must be a report child")
    ar=read(analysis/"ANALYSIS_RECEIPT.json");rr=read(revision/"REVISION_ANALYSIS_RECEIPT.json");cr=read(cpdir/"CP_UNCERTAINTY_RECEIPT.json")
    if any(r["status"]!="COMPLETE_REQUESTED_INDEX" for r in (ar,rr,cr)):raise ValueError("Complete requested analysis chain required")
    if ar["index"]!=rr["index"] or ar["index"]!=cr["index"]:raise ValueError("Different input indexes")
    registry=read(report/"EFFECTIVE_PROFILE_REGISTRY.json")["profiles"];reg={r["profile_id"]:r for r in registry}
    profile_rows=read(analysis/"PROFILE_RESULTS.json");profiles={(r["profile_id"],r["stream"],r["population"]):r for r in profile_rows}
    shorts={(r["profile_id"],r["stream"],r["duration_bin"]):r for r in read(analysis/"SHORT_REPLY_RESULTS.json") if r["population"]=="ALL_COMPLETE_NONEMPTY"}
    revisions={(r["profile_id"],r["stream"]):r for r in read(revision/"REVISION_PROFILE_RESULTS.json")}
    with (analysis/"RECIPE_COST_RESULTS.csv").open(encoding="utf-8-sig",newline="") as f:costs=native_costs(list(csv.DictReader(f)))
    result=[]
    for pid,stream in sorted(revisions):
        config=reg[pid];rid=config["recipe_id"];r=revisions[pid,stream];complete=profiles[pid,stream,"ALL_COMPLETE_NONEMPTY"]
        row=dict(profile_id=pid,stream=stream,recipe_id=rid,name=config["name"],classification=config["classification"],
                 comparison_parent=config.get("comparison_parent"),method_family=config["mechanism_family"])
        for pop,tag in (("PRIMARY_NONOVERLAP","primary"),("COMPLETE_OVERLAP","overlap_mimo"),("INCOMPLETE_REFERENCE","ambient_target"),("STRICT_EMPTY_REFERENCE","empty")):
            p=profiles.get((pid,stream,pop),{})
            for field in ("scenes","word_errors","word_reference_words","word_rate","char_rate","empty_insertions","empty_insertions_per_minute"):
                if field in p:row[tag+"_"+field]=p[field]
        for field in ("scenes","cp_first_final_errors","cp_first_final_reference_words","cp_first_final_rate","cp_latest_revised_errors","cp_latest_revised_rate",
                      "cp_first_display_label_final_words_errors","cp_first_display_label_final_words_rate","source_turns","unknown_fraction","mixed_fraction_all_sole","mixed_fraction_known",
                      "return_consistent","return_inconsistent","return_unknown","embedding_calls","embedding_union_sec","embedding_total_window_sec","sole_active_samples"):
            row["complete_"+field]=complete.get(field)
        for duration,tag in (("<1s","subsecond"),("1-<2s","one_to_two_second")):
            s=shorts[pid,stream,duration]
            for field in SHORT_FIELDS:row[tag+"_"+field]=s.get(field)
            for field in ("contained_evidence_wait","known_support_wait","correct_mapped_support_wait"):row[tag+"_"+field]=s.get(field)
        for field in ("derived_changed_label_transitions","post_final_changed_label_transitions","transition_counts","actual_revision_scope_counts","identifiable_utterances",
                      "exposure_unavailable_utterances","never_correct_utterances","known_wrong_exposure_sec","unknown_or_unmapped_exposure_sec","observed_identifiable_label_state_sec",
                      "distinct_wrong_attribution_recipient_count"):
            row["revision_"+field]=r.get(field)
        row["policy_wall_sec_all_scenes"]=sum(profiles.get((pid,stream,pop),{}).get("policy_wall_sec",0) for pop in POPS)
        row.update({"recipe_"+k:v for k,v in costs[rid,stream].items()})
        base=costs.get(("R0",stream),{})
        for key in ("native_process_cpu_sec","embedding_calls","segmentation_calls"):
            n,d=costs[rid,stream].get(key),base.get(key)
            row["recipe_"+key+"_relative_R0"]=n/d if n is not None and d else None
        result.append(row)
    out.mkdir(parents=True,exist_ok=True)
    csv_write(out/"COMPONENT_SCREEN.csv",result);save(out/"COMPONENT_SCREEN.json",result)
    receipt=dict(status="COMPLETE_REQUESTED_INDEX",schema="jp_s6b_component_screen_v1",index=ar["index"],code=bind(__file__),
        dependencies=[bind(analysis/name) for name in ("ANALYSIS_RECEIPT.json","PROFILE_RESULTS.json","SHORT_REPLY_RESULTS.json","RECIPE_COST_RESULTS.csv")]+
                     [bind(revision/name) for name in ("REVISION_ANALYSIS_RECEIPT.json","REVISION_PROFILE_RESULTS.json")]+
                     [bind(cpdir/"CP_UNCERTAINTY_RECEIPT.json"),bind(report/"EFFECTIVE_PROFILE_REGISTRY.json")],
        rows=len(result),profiles=len({r["profile_id"] for r in result}),scenes_per_tap=ar["requested_scene_count"],
        interpretation="Factual screen, no weighted score/ranking. Cost per exact upstream recipe is repeated for profile comparison, never summed over reusers. Full-engine CPU and nested phases overlap and must not be added. Native accelerated elapsed sums are not deployment latency. Retained-row exposure is not word-aligned harm. Causal/condition scope comes from the matched interaction contract.",
        outputs=[bind(out/name) for name in ("COMPONENT_SCREEN.csv","COMPONENT_SCREEN.json")])
    save(out/"COMPONENT_SCREEN_RECEIPT.json",receipt)
    return {k:receipt[k] for k in ("status","rows","profiles","scenes_per_tap")}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path,default=SIM/"reports/S6B/20260909T230840Z")
    p.add_argument("--analysis-subdir",default="challenge_analysis_v1")
    p.add_argument("--revision-subdir",default="challenge_revision_v1")
    p.add_argument("--cp-subdir",default="challenge_cp_uncertainty_v1")
    p.add_argument("--output-subdir",default="component_screen_v1")
    print(json.dumps(build(p.parse_args()),indent=2))
if __name__=="__main__":main()
