"""Model-free pilot adapter for frozen S6B replay. README_S6B_PILOT_ANALYSIS_ADAPTER.md."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
for key in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[key]="1"
import numpy as np
from s6b_common import REPORT,PAYLOAD,read,save,bind,digest,utc
from s6b_replay import api,run_scheduler,historical

PROFILE_IDS=("B00","B01","B05","B16","B17","B18","B20","B22","B24","B26","B28","B36","B37","B38")
def run(report,epoch):
    spec_path=report/(epoch.upper()+"_EXECUTION_MANIFEST.json");spec=read(spec_path)
    for source in spec["execution_files"]:bind(source["path"],source["sha256"])
    replay_source=next(x for x in spec["execution_files"] if Path(x["path"]).name=="s6b_replay.py")
    bind(Path(__file__).parent/"s6b_replay.py",replay_source["sha256"])
    for key in ("input_index","gain_index","challenge_panel","scene_manifest"):bind(spec[key]["path"],spec[key]["sha256"])
    profile_path=report/"EFFECTIVE_PROFILE_REGISTRY.json";registry=read(profile_path)
    candidates={p["profile_id"]:p for p in registry["profiles"]}
    if not set(PROFILE_IDS)<=set(candidates):raise ValueError("Missing required pilot profile")
    inputs=read(spec["input_index"]["path"])["rows"]
    panel=set(read(spec["challenge_panel"]["path"])["case_ids"])
    scenes=read(spec["scene_manifest"]["path"])["scenes"]
    case_ids=sorted(min(s["case_id"] for s in scenes if s["case_id"] in panel and s["family_id"]==family) for family in ("F01","F03","F04","F06"))
    chosen=[x for x in inputs if x["case_id"] in case_ids]
    if len(chosen)!=8:raise ValueError("Pilot must contain four cases and both taps")
    evidence_cache={};missing=[]
    required={(candidates[p]["recipe_id"],i["case_id"],i["stream"]) for p in PROFILE_IDS if p!="B00" for i in chosen}
    for recipe,cid,stream in sorted(required):
        path=PAYLOAD/epoch/"neural"/recipe/cid/stream/"run_receipt.json"
        if not path.exists():missing.append(str(path));continue
        receipt=read(path)
        if receipt["status"]!="COMPLETE":missing.append(str(path));continue
        bind(receipt["evidence"]["path"],receipt["evidence"]["sha256"])
        evidence=read(receipt["evidence"]["path"])
        bind(evidence["vectors"]["path"],evidence["vectors"]["sha256"])
        evidence_cache[recipe,cid,stream]=(receipt,evidence,bind(path))
    if missing:
        return dict(status="WAITING_FOR_COMPLETE_NATIVE_PILOT",required_unique_recipe_outputs=len(required),missing_count=len(missing),first_missing=missing[:5])
    classes=api(spec);Profile,Provider,_,_=classes
    code=bind(__file__);profile_binding=bind(profile_path);spec_binding=bind(spec_path)
    output=report/"pilot_validation_predictions";records=[];providers={};started=time.perf_counter()
    for item in chosen:
        cid,stream=item["case_id"],item["stream"]
        for pid in PROFILE_IDS:
            candidate=candidates[pid];recipe=candidate["recipe_id"]
            if pid=="B00":
                for key in ("baseline_events","baseline_features"):bind(item[key]["path"],item[key]["sha256"])
                source=dict(historical_events=item["baseline_events"],historical_features=item["baseline_features"])
            else:
                receipt,evidence,receipt_binding=evidence_cache[recipe,cid,stream]
                source=dict(native_receipt=receipt_binding,evidence=receipt["evidence"],recipe_job_key=receipt["job_key"])
            identity=dict(schema="jp_s6b_pilot_analysis_adapter_v1",code=code,frozen_replay_code=replay_source,execution=spec_binding,
                effective_profiles=profile_binding,profile=candidate,source=source,
                telemetry=item["telemetry"] if (candidate.get("profile") or {}).get("tracker",{}).get("cues_enabled") else None,
                purpose="Independent model-free pilot analysis validation; no main-prediction cache reuse; reference labels never enter run_scheduler.")
            key=digest(identity);target=output/pid/cid/(stream+".json")
            if target.exists():
                value=read(target)
                if value["prediction_key"]!=key:raise ValueError("Pilot prediction dependency changed; use a new named adapter output version")
            else:
                if pid=="B00":value=historical(item)
                else:
                    vectors=np.load(evidence["vectors"]["path"],allow_pickle=False)["vectors"]
                    if len(vectors)!=len(evidence["features"]) or not np.isfinite(vectors).all():raise ValueError("Invalid actual vector cache")
                    profile=Profile.from_dict(candidate["profile"]);provider=None
                    if profile.tracker.cues_enabled:
                        if cid not in providers:
                            bind(item["telemetry"]["path"],item["telemetry"]["sha256"]);providers[cid]=Provider(Path(item["telemetry"]["path"]))
                        provider=providers[cid]
                    value=run_scheduler(profile,provider,evidence,vectors,classes)
                value.update(schema="jp_s6b_profile_prediction_v1",status="COMPLETE",prediction_key=key,identity=identity,
                    case_id=cid,stream=stream,profile_id=pid,recipe_id=recipe,duration_sec=item["duration_sec"],
                    timing_scope="Frozen APP deterministic common scheduler over actual epoch2 native upstream availability; independent policy replay wall cost; historical B00 remains historical.",
                    created_utc=utc())
                save(target,value)
            records.append(dict(case_id=cid,stream=stream,profile_id=pid,recipe_id=recipe,status="COMPLETE",result=bind(target)))
    index=dict(schema="jp_s6b_prediction_index_v1",status="COMPLETE",requested=len(PROFILE_IDS)*8,completed=len(records),
        profiles=list(PROFILE_IDS),case_ids=case_ids,panel="independent_four_case_pilot_validation",epoch=epoch,rows=records,
        execution_manifest=spec_binding,effective_profiles=profile_binding,adapter_code=code,
        unique_native_recipe_outputs=len(required),elapsed_sec=time.perf_counter()-started,created_utc=utc(),
        scope="Model-free pilot validation only. These predictions are never reused as main challenge/all240 prediction artifacts.")
    path=report/"PILOT_VALIDATION_PREDICTION_INDEX.json";save(path,index)
    return dict(status="COMPLETE",predictions=len(records),profiles=len(PROFILE_IDS),cases=len(case_ids),unique_native_recipe_outputs=len(required),index=str(path))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--report",type=Path,default=REPORT);p.add_argument("--epoch",default="epoch2")
    a=p.parse_args();print(json.dumps(run(a.report,a.epoch),indent=2))
if __name__=="__main__":main()

