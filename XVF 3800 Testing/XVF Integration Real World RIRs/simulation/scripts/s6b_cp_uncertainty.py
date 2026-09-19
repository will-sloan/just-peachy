"""Conditional S6B cpWER uncertainty without neural execution. README_S6B_CP_UNCERTAINTY.md."""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
import numpy as np
from s6b_analysis import read,bind,save,csv_write,verified
from s6a_text_metrics import reference_layout
from s5_coverage import components

SIM=Path(__file__).resolve().parents[1]
COMPLETE={"PRIMARY_NONOVERLAP","COMPLETE_OVERLAP"}
VIEWS=("first_final","latest_revised","first_display_label_final_words")

def closure_project(groups,all_ids,eligible):
    return [sorted(set(g)&eligible) for g in components(groups,all_ids) if set(g)&eligible]
def dependency_structure(bank):
    scenes={s["case_id"]:s for s in bank["scenes"]}
    complete={cid for cid,s in scenes.items() if reference_layout(s)["population"] in COMPLETE}
    matched=defaultdict(set);deps={k:defaultdict(set) for k in ("speaker","source_clip","prompt","book","rir","noise_parent")}
    for cid,s in scenes.items():
        for key in ("matched_pair_id","matched_group_id"):
            if s.get(key):matched[key,s[key]].add(cid)
        for segment in s["segments"]:
            deps["rir"][segment["rir_id"]].add(cid)
            if segment["kind"]=="utterance":
                source=bank["selected_sources"][segment["source_id"]]
                for kind,key in (("speaker","identity"),("source_clip","source_id"),("prompt","prompt_group"),("book","parent_book")):
                    if source.get(key):deps[kind][source[key]].add(cid)
            elif segment["kind"]=="real_noise":deps["noise_parent"][segment["parent_id"]].add(cid)
    allblocks=components(matched.values(),scenes)
    blocks=[]
    for group in allblocks:
        ids=sorted(set(group)&complete)
        if not ids:continue
        rooms={scenes[c]["receiver_configuration"]["room_table"] for c in group}
        if len(rooms)!=1:raise ValueError("Matched block crosses rooms")
        blocks.append(dict(block_id="MATCHED_"+group[0],case_ids=ids,room=next(iter(rooms))))
    # Form closures on all scenes before projection: an incomplete-reference
    # scene can still connect two complete-reference scenes through shared data.
    def project_closure(groups):
        return closure_project(allblocks+list(groups),scenes,complete)
    structures={kind:project_closure(groups.values()) for kind,groups in deps.items()}
    total=project_closure([x for groups in deps.values() for x in groups.values()])
    return dict(eligible_scene_count=len(complete),blocks=blocks,dependency_components=structures,
        all_dependency_component_sizes=sorted(map(len,total),reverse=True),
        scope="Complete nonempty reference projection of full-bank matched blocks; source-dependency closures form on all240 scenes before projection, retaining bridges through incomplete/empty-reference scenes.")

def point(pairs):
    n=sum(r[2] for r in pairs);le=sum(r[0] for r in pairs);re=sum(r[1] for r in pairs)
    return dict(scenes=len(pairs),reference_words=n,left_errors=le,right_errors=re,right_minus_left_errors=re-le,
        right_minus_left_pp=100*(re-le)/n if n else None)
def estimate(pairs,structure,requested_cases,replicates=2000,seed=20260909):
    # pairs keyed by scene, values [left errors,right errors,reference words,room]
    grouped=defaultdict(list);included=[];excluded=[]
    for block in structure["blocks"]:
        absent=[c for c in block["case_ids"] if c not in pairs]
        if absent:
            excluded.append(dict(block_id=block["block_id"],case_ids=block["case_ids"],
                unselected_panel_cases=[c for c in absent if c not in requested_cases],
                selected_but_unscored_cases=[c for c in absent if c in requested_cases]))
            continue
        values=[pairs[c] for c in block["case_ids"]]
        if any(r[3]!=block["room"] for r in values):raise ValueError("Room/block mismatch")
        grouped[block["room"]].append(np.asarray([r[:3] for r in values],dtype=np.int64).sum(axis=0))
        included.extend(block["case_ids"])
    kept={c:pairs[c] for c in included};rng=np.random.default_rng(seed)
    boot=np.zeros((replicates,3),dtype=np.int64)
    for room,blocks in sorted(grouped.items()):
        a=np.asarray(blocks,dtype=np.int64)
        boot+=a[rng.integers(0,len(a),size=(replicates,len(a)))].sum(axis=1)
    valid=boot[:,2]>0;delta=100*(boot[valid,1]-boot[valid,0])/boot[valid,2]
    interval=[float(x) for x in np.percentile(delta,[2.5,97.5])] if len(delta) else None
    roomrows=[]
    for room in sorted({v[3] for v in pairs.values()}):
        row=point([v for v in pairs.values() if v[3]==room]);row["room"]=room;roomrows.append(row)
    leave_room=[dict(removed_room=room,**point([v for v in kept.values() if v[3]!=room])) for room in sorted(grouped)]
    deletion=[];bands={}
    for kind,groups in structure["dependency_components"].items():
        for i,group in enumerate(groups):
            removed=set(group)
            if not removed&set(kept):continue
            row=point([v for c,v in kept.items() if c not in removed])
            deletion.append(dict(dependency_type=kind,component_id=kind+":"+group[0],excluded_included_scenes=len(removed&set(kept)),**row))
        eligible=[r["right_minus_left_pp"] for r in deletion if r["dependency_type"]==kind and r["reference_words"]]
        bands[kind]=dict(minimum_delta_pp=min(eligible,default=None),maximum_delta_pp=max(eligible,default=None),
            available_deletions=len(eligible),unavailable_deletions=sum(r["dependency_type"]==kind and not r["reference_words"] for r in deletion))
    point_all=point(list(pairs.values()));point_kept=point(list(kept.values()))
    return dict(all_paired_point=point_all,bootstrap_included_point=point_kept,bootstrap_percentile95_pp=interval,
        replicates=replicates,seed=seed,matched_blocks=sum(map(len,grouped.values())),blocks_by_room={k:len(v) for k,v in grouped.items()},
        observed_rooms=len(grouped),excluded_whole_blocks=excluded,room=roomrows,
        equal_room_delta_pp=float(np.mean([r["right_minus_left_pp"] for r in roomrows if r["reference_words"]])) if any(r["reference_words"] for r in roomrows) else None,
        leave_room_out=leave_room,dependency_deletion_ranges=bands,dependency_deletions=deletion,
        all_dependency_component_sizes=structure["all_dependency_component_sizes"],
        interpretation="Conditional paired complete-reference matched-block bootstrap within observed rooms. Point on every paired scene is separate from the whole-block bootstrap subset. Shared sources/RIR/noise connect blocks; intervals may be optimistic. No independent holdout or equivalence claim.")

def comparisons(profiles,parents):
    result=[]
    for pid in profiles:
        for view in VIEWS:result.append((pid,"O0",view,pid,"O1",view,"output_pair"))
        if parents.get(pid) in profiles:
            for stream in ("O0","O1"):
                for view in VIEWS:result.append((parents[pid],stream,view,pid,stream,view,"parent_pair"))
        for stream in ("O0","O1"):
            for view in ("first_final","first_display_label_final_words"):
                result.append((pid,stream,view,pid,stream,"latest_revised","revision_pair"))
    return result

def fixtures():
    structure=dict(blocks=[dict(block_id="ab",case_ids=["a","b"],room="R"),dict(block_id="c",case_ids=["c"],room="R")],
        dependency_components={"speaker":[["a","b"],["c"]]},all_dependency_component_sizes=[3])
    pairs={"a":[1,2,10,"R"],"b":[2,2,20,"R"],"c":[3,1,30,"R"]}
    complete=estimate(pairs,structure,set(pairs),100)
    assert complete["all_paired_point"]["reference_words"]==60 and complete["bootstrap_included_point"]["reference_words"]==60
    partial=estimate({k:v for k,v in pairs.items() if k!="b"},structure,{"a","c"},100)
    assert partial["all_paired_point"]["reference_words"]==40 and partial["bootstrap_included_point"]["reference_words"]==30
    assert partial["excluded_whole_blocks"][0]["unselected_panel_cases"]==["b"]
    assert partial["bootstrap_percentile95_pp"]==[-100/15,-100/15]
    assert closure_project([["a","bridge"],["bridge","b"]],{"a","b","bridge"},{"a","b"})==[["a","b"]]
    return dict(status="PASS",tests=["pooled unequal reference denominators","whole-block exclusion retains separate all-paired point","unselected versus failed members distinct","conditional interval exact single retained block","dependency bridges retained before reference projection"])

def run(args):
    report=args.report;index_path=args.index if args.index.is_absolute() else report/args.index
    index=read(index_path);analysis=report/args.analysis_subdir;out=report/args.output_subdir
    if Path(args.output_subdir).is_absolute() or report.resolve() not in out.resolve().parents:raise ValueError("Output must be a report child")
    bank_path=SIM/"scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json"
    bank=read(bank_path);structure=dependency_structure(bank)
    if bind(bank_path)["sha256"]!="69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18":raise ValueError("Frozen bank changed")
    analysis_receipt=read(analysis/"ANALYSIS_RECEIPT.json")
    if analysis_receipt["index"]!=bind(index_path):raise ValueError("Core analysis/index identity mismatch")
    registry_path=report/"EFFECTIVE_PROFILE_REGISTRY.json"
    registry=read(registry_path)["profiles"]
    parents={r["profile_id"]:r.get("comparison_parent") or r.get("parent") for r in registry}
    data={};bindings=[];failures=[];started=time.perf_counter()
    expected={(p,s,c) for p in index["profiles"] for s in ("O0","O1") for c in index["case_ids"]}
    declared=[(r["profile_id"],r["stream"],r["case_id"]) for r in index["rows"]]
    if len(declared)!=len(set(declared)) or not set(declared)<=expected:raise ValueError("Invalid prediction coverage")
    for item in index["rows"]:
        cid,stream,pid=item["case_id"],item["stream"],item["profile_id"];path=analysis/"scores"/pid/cid/(stream+".json")
        try:
            score=read(path)
            if score["analysis_identity"]["prediction"]!=item["result"]:raise ValueError("Score/prediction identity mismatch")
            if score["population"] in COMPLETE:
                counts={}
                for view in VIEWS:
                    c=score["text_metrics"][view]["attributed_cpwer"].get("word_counts")
                    if not c or c["reference_words"]<=0 or c["errors"]!=c["substitutions"]+c["deletions"]+c["insertions"]:raise ValueError("cpWER unavailable or invalid")
                    counts[view]=c
                data[pid,stream,cid]=(counts,score["room"])
            bindings.append(bind(path))
        except Exception as exc:failures.append(dict(profile_id=pid,stream=stream,case_id=cid,error=type(exc).__name__+": "+str(exc)))
    if args.require_complete and (failures or set(declared)!=expected or index["status"]!="COMPLETE"):raise ValueError("Complete requested score index required")
    result=[];details=[];deletion_rows=[]
    for lp,ls,lv,rp,rs,rv,kind in comparisons(index["profiles"],parents):
        pairs={}
        for cid in index["case_ids"]:
            left=data.get((lp,ls,cid));right=data.get((rp,rs,cid))
            if left is None or right is None:continue
            lc,rc=left[0][lv],right[0][rv]
            if lc["reference_words"]!=rc["reference_words"] or left[1]!=right[1]:raise ValueError("Paired cp denominator/room mismatch")
            pairs[cid]=[lc["errors"],rc["errors"],lc["reference_words"],left[1]]
        identity=dict(left_profile=lp,left_stream=ls,left_view=lv,right_profile=rp,right_stream=rs,right_view=rv,comparison=kind)
        est=estimate(pairs,structure,set(index["case_ids"]),args.replicates)
        details.append(dict(**identity,**{k:v for k,v in est.items() if k!="dependency_deletions"}))
        deletion_rows.extend(dict(**identity,**row) for row in est["dependency_deletions"])
        result.append(dict(**identity,paired_scenes=est["all_paired_point"]["scenes"],reference_words=est["all_paired_point"]["reference_words"],
            right_minus_left_pp=est["all_paired_point"]["right_minus_left_pp"],
            bootstrap_included_scenes=est["bootstrap_included_point"]["scenes"],bootstrap_included_reference_words=est["bootstrap_included_point"]["reference_words"],
            bootstrap_included_delta_pp=est["bootstrap_included_point"]["right_minus_left_pp"],bootstrap_percentile95_pp=est["bootstrap_percentile95_pp"],
            matched_blocks=est["matched_blocks"],observed_rooms=est["observed_rooms"],equal_room_delta_pp=est["equal_room_delta_pp"],
            excluded_blocks=len(est["excluded_whole_blocks"]),dependency_deletion_ranges=est["dependency_deletion_ranges"]))
    out.mkdir(parents=True,exist_ok=True)
    csv_write(out/"CP_PAIRED_UNCERTAINTY.csv",result);csv_write(out/"CP_DEPENDENCY_DELETIONS.csv",deletion_rows)
    save(out/"CP_PAIRED_UNCERTAINTY.json",details);save(out/"DEPENDENCY_STRUCTURE.json",structure)
    receipt=dict(status="COMPLETE_REQUESTED_INDEX" if not failures and set(declared)==expected and index["status"]=="COMPLETE" else "PARTIAL_RESUMABLE",
        schema="jp_s6b_cp_uncertainty_v1",index=bind(index_path),bank=bind(bank_path),code=bind(__file__),score_bindings=bindings,
        core_analysis_receipt=bind(analysis/"ANALYSIS_RECEIPT.json"),effective_profile_registry=bind(registry_path),
        tests=fixtures(),requested_score_outputs=len(expected),available_score_outputs=len(bindings),failures=failures,
        paired_contrasts=len(result),replicates=args.replicates,elapsed_sec=time.perf_counter()-started,
        scope="Complete nonempty reference cpWER only. No population generalization, no independent frame/word resampling. All paired point and whole-block bootstrap subset separately reported.",
        tables=[bind(out/name) for name in ("CP_PAIRED_UNCERTAINTY.csv","CP_DEPENDENCY_DELETIONS.csv","CP_PAIRED_UNCERTAINTY.json","DEPENDENCY_STRUCTURE.json")])
    save(out/"CP_UNCERTAINTY_RECEIPT.json",receipt)
    return {k:receipt[k] for k in ("status","requested_score_outputs","available_score_outputs","paired_contrasts","elapsed_sec")}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--report",type=Path,default=SIM/"reports/S6B/20260909T230840Z")
    p.add_argument("--index",type=Path);p.add_argument("--analysis-subdir");p.add_argument("--output-subdir",default="cp_uncertainty_v1")
    p.add_argument("--replicates",type=int,default=2000);p.add_argument("--require-complete",action="store_true");p.add_argument("--test",action="store_true")
    a=p.parse_args()
    if a.test:print(json.dumps(fixtures(),indent=2));return
    if a.index is None or not a.analysis_subdir:p.error("--index and --analysis-subdir required")
    if a.replicates<100:p.error("at least100 bootstrap replicates required")
    print(json.dumps(run(a),indent=2))
if __name__=="__main__":main()
