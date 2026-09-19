"""Independent S6C tracker fixtures; see README_S6C_TRACKING_REVIEW_CHECKS.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import numpy as np

SIM=Path(__file__).resolve().parents[1]
APP=SIM.parents[2]/"Software Validation from Datasets/Evaluation Tool/app"
REPORT=SIM/"reports/S6C/20260910T123540Z"
sys.dont_write_bytecode=True

def binding(p):
    p=Path(p);b=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def save(p,v):
    with Path(p).open("x",encoding="utf-8") as f:json.dump(v,f,indent=2,allow_nan=False);f.write("\n")

def vector(cosine=1.):
    a=np.zeros(192,np.float32);a[0]=cosine;a[1]=np.sqrt(1.-cosine*cosine);return a

def bearing(angle,end,stamp=None,sequence=None):
    return SimpleNamespace(valid=True,available_at_sec=end if stamp is None else stamp,source_start_sec=end-.01,
      source_end_sec=end,sequence=int(end*1000) if sequence is None else sequence,angle_deg=float(angle),reliability=1.,energy=1.)

def run(source,output):
    output=output.resolve()
    if not output.is_relative_to(REPORT.resolve()):raise ValueError("New S6C output required")
    output.mkdir(parents=True,exist_ok=False)
    raw=source.read_bytes();snapshot=output/"REVIEWED_TRACKER_SOURCE.py";snapshot.write_bytes(raw)
    sys.path.insert(0,str(APP))
    name="edge_speech_pipeline._s6c_independent_review_source"
    spec=importlib.util.spec_from_file_location(name,snapshot)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    C,T=mod.S6CTrackingConfig,mod.S6CTracker
    checks=[];observed=[]
    def test(name,function):
        try:
            detail=function()
            checks.append(dict(name=name,status="PASS",detail=detail))
        except Exception as e:checks.append(dict(name=name,status="FAIL",error=repr(e)))
    def update(t,v,start,end,angle=None,**kw):
        return t.update(v,start,end,end,spatial=bearing(angle,end) if angle is not None else None,**kw)
    for mode in mod.MODES:
        def basic(mode=mode):
            t=T(C(mode=mode,cues_enabled=True,lifecycle_policy="none"))
            first=update(t,vector(),0,.5,30)
            second=update(t,vector(.34),.5,1,30)
            assert first["tracker_id"]==1
            assert second["tracker_id"]==(2 if mode=="old_voice_gate" else 1)
            bad=T(C(mode=mode,cues_enabled=True,lifecycle_policy="none"))
            update(bad,vector(),0,.5,30)
            severe=update(bad,vector(.10),.5,1,30)
            assert severe["tracker_id"]!=1
            relocate=T(C(mode=mode,cues_enabled=True,lifecycle_policy="none"))
            update(relocate,vector(),0,.5,30)
            moved=update(relocate,vector(),.5,1,150)
            assert moved["tracker_id"]==1
            return dict(borderline_choice=second["tracker_id"],severe_choice=severe["tracker_id"],strong_relocation=moved["tracker_id"])
        test("joint gate/rescue/severe/strong relocation "+mode,basic)
        def conflict(mode=mode):
            choices=[]
            for weight in (.6,1.,1.5):
                t=T(C(mode=mode,cues_enabled=True,lifecycle_policy="none",joint_spatial_weight=weight))
                update(t,vector(),0,.5,30)
                result=update(t,vector(.4),.5,1,150)
                choices.append(dict(weight=weight,choice=result["tracker_id"],joint=result["joint_choice"]))
            if mode=="old_voice_gate":assert all(x["choice"]==1 for x in choices)
            else:assert any(x["choice"]!=1 for x in choices)
            return dict(scope="Bounded parameter reachability; nominal retention is not an empirical error.",settings=choices)
        test("sole-candidate angle conflict neighborhood "+mode,conflict)
        def roles(mode=mode):
            t=T(C(mode=mode,lifecycle_policy="none"))
            seq=[(0,.5,"short"),(0,1,"mature"),(.5,1,"short"),(.5,1.5,"mature"),(1,2,"mature")]
            for a,b,kind in seq:update(t,vector(),a,b,evidence_kind=kind)
            track=t.tracks[0]
            assert track.unique_sec==2. and track.mature_count==2 and track.disjoint_count==3
            assert track.committed
            return dict(unique=track.unique_sec,mature_disjoint=track.mature_count,disjoint=track.disjoint_count)
        test("continuous short/mature independent frontiers "+mode,roles)
        def prefix(mode=mode):
            a=T(C(mode=mode));b=T(C(mode=mode))
            prefix=[vector(),vector(),vector(.4)]
            left=[];right=[]
            for i,v in enumerate(prefix):left.append(update(a,v,i*.5,(i+1)*.5))
            for i,v in enumerate(prefix+[vector(-.9),vector(.8)]):
                r=update(b,v,i*.5,(i+1)*.5)
                if i<len(prefix):right.append(r)
            assert left==right
            return dict(exact_prefix_decisions=len(left),different_future_observations=2)
        test("finite prefix future invariance "+mode,prefix)
        for capacity in (16,32,64,128,256):
            def cap(mode=mode,capacity=capacity):
                rng=np.random.default_rng(904)
                t=T(C(mode=mode,max_tracks=capacity,lifecycle_policy="none"))
                vectors=rng.normal(size=(capacity+1,192)).astype(np.float32)
                vectors/=np.linalg.norm(vectors,axis=1)[:,None]
                ids=[]
                for i,v in enumerate(vectors):
                    d=update(t,v,i*.5,(i+1)*.5)
                    if d["tracker_id"] is not None:ids.append(d["tracker_id"])
                # This chosen fixed numerical sequence must actually create distinct hypotheses.
                assert len(t.tracks)==capacity and t.next_track==capacity+1
                assert sorted(set(ids))==list(range(1,capacity+1))
                assert t.operations["track_capacity_rejection"]>=1
                assert len(t.archive)==0
                return dict(capacity=capacity,live=len(t.tracks),lifetime=t.next_track-1,rejections=t.operations["track_capacity_rejection"])
            test("matched allocation bound "+mode+" "+str(capacity),cap)
    def archived_overlap():
        t=T(C(mode="normalized_joint",dormancy_sec=.5,pressure_retirement_sec=.5,
              retirement_sec=.5,provisional_retirement_sec=.5))
        update(t,vector(),0,1)
        d=update(t,vector(),.5,1.5)
        assert d["tracker_id"]==1 and t.operations["archive_reactivate"]==1
        assert t.tracks[0].unique_sec==1.5 and t.tracks[0].disjoint_count==1
        return dict(unique=t.tracks[0].unique_sec,archive_reactivated=t.operations["archive_reactivate"])
    test("archive reentry preserves overlapping clean union",archived_overlap)
    def shadow():
        t=T(C(mode="shadow_gallery_joint",lifecycle_policy="none"))
        update(t,vector(),0,.5)
        before=[v.copy() for v in t.tracks[0].prototypes]
        update(t,vector(.6),.5,1)
        assert t.tracks[0].version==0 and len(t.tracks[0].prototypes)==len(before)
        assert all(np.array_equal(a,b) for a,b in zip(before,t.tracks[0].prototypes))
        d=update(t,vector(.6),1,1.5)
        assert t.operations["clean_shadow_promote"]==1 and t.tracks[0].version==1
        return dict(pending_does_not_mutate_live=True,promotions=1)
    test("clean shadow isolation then actual promotion",shadow)
    def merge():
        t=T(C(mode="normalized_joint",structural_merge_enabled=True,structural_merge_disjoint_count=2,lifecycle_policy="none"))
        events=[]
        a=t._create(vector(),1.5,1.5,events);a.ranges=[[0,.5],[1,1.5]];a.disjoint_end=1.5;a.mature_disjoint_end=1.5
        a.disjoint_count=a.mature_count=2;a.dormant=True
        b=t._create(vector(),3,3,events);b.ranges=[[2,2.5],[2.5,3]];b.disjoint_end=b.mature_disjoint_end=3
        b.disjoint_count=b.mature_count=2;b.committed=True
        before_union=sum(y-x for x,y in mod._union(a.ranges+b.ranges))
        survivor=t._merge(b,3,events)
        assert survivor.identifier==1 and len(t.tracks)==1 and t.operations["structural_track_merge"]==1
        assert survivor.disjoint_end==3 and survivor.mature_disjoint_end==3
        assert survivor.unique_sec==before_union
        d=update(t,vector(),2.25,3.25)
        assert abs(t.tracks[0].unique_sec-(before_union+.25))<1e-9
        assert t.tracks[0].disjoint_count==2 and t.tracks[0].mature_count==2
        assert t.next_track==3
        return dict(scope="Explicit valid synthetic track-state setup; actual merge and following update execute.",union_after=t.tracks[0].unique_sec,external_survivor=1,lifetime_next=3)
    test("actual merge preserves union and both disjoint frontiers",merge)
    def split():
        t=T(C(mode="quarantine_joint",structural_split_enabled=True,voice_learning_rate=.8,lifecycle_policy="none"))
        result=[]
        for i,v in enumerate((vector(),vector(.6),vector(.6),vector())):
            result.append(update(t,v,i*.5,(i+1)*.5))
        assert t.operations["prototype_escrow_hold"]>=1 and t.operations["prototype_escrow_release"]==1
        assert t.operations["prototype_rollback"]==1 and t.operations["structural_track_split"]==1
        assert len(t.tracks)==2 and t.next_track==3
        revisions=[x for d in result for x in d["lineage"] if x["event"]=="label_revision"]
        assert revisions and revisions[0]["original_available_at_sec"]<revisions[0]["available_at_sec"]
        return dict(scope="Actual successive-vector update path, no injected tracker state.",operations=dict(t.operations),forward_revisions=len(revisions))
    test("actual escrow rollback and structural split",split)
    def long_run():
        t=T(C(mode="normalized_joint",max_tracks=2,archive_capacity=4,retirement_sec=10,provisional_retirement_sec=5,dormancy_sec=1,pressure_retirement_sec=1))
        created=[]
        for i in range(400):
            v=np.eye(192,dtype=np.float32)[i%192]
            d=update(t,v,i*10,i*10+.5)
            created.extend(x["track_id"] for x in d["lineage"] if x["event"]=="track_create")
            assert len(t.tracks)<=2 and len(t.archive)<=4 and len(t.nodes)<=t.config.max_revision_records
        last=t.tracks[-1].identifier
        d=update(t,np.eye(192,dtype=np.float32)[399%192],4000,4000.5)
        assert d["tracker_id"]==last and t.operations["archive_reactivate"]>=1
        assert created==list(range(1,len(created)+1))
        s=t.snapshot()
        return dict(observations=401,synthetic_source_duration_sec=4000.5,live=len(t.tracks),archive=len(t.archive),
                    lifetime_ids=t.next_track-1,actual_archive_reentries=t.operations["archive_reactivate"],state_bytes=s["state_bytes"],
                    scope="Model-free synthetic chronology, not host endurance or continuous XVF adaptive state.")
    test("bounded long lifecycle and monotone archive reentry",long_run)
    def stale():
        t=T(C(cues_enabled=True))
        update(t,vector(),0,.5,30)
        observations=[bearing(30,.5,stamp=1,sequence=500),bearing(30,2,stamp=2),bearing(30,1.5)]
        reasons=[]
        for i,o in enumerate(observations):
            end=1+i*.5
            r=t.update(vector(),end-.5,end,end,spatial=o)
            reasons.append(r["cue"]["reason"])
        assert reasons[0]=="invalid_or_stale_source" and reasons[1]=="future_delivery"
        return dict(reasons=reasons)
    test("old redelivery and future packet remain inadmissible",stale)
    def inputs():
        for field,value in (("reference_speaker","x"),("nominal_angle",30),("gallery_name","person")):
            try:C.from_mapping({field:value})
            except ValueError:pass
            else:raise AssertionError("Truth/unknown config key accepted")
        for mode in ("hypothesis_joint","semimarkov_joint","bounded_global_joint"):
            try:C.from_mapping(dict(mode=mode,joint_margin=.2))
            except ValueError:pass
            else:raise AssertionError("Inactive temporal joint_margin accepted")
        t=T(C());update(t,vector(),0,.5)
        try:update(t,vector(),0,.5)
        except ValueError:pass
        else:raise AssertionError("Duplicate span accepted")
        return dict(config_boundary=True,temporal_inactive_guard=True,duplicate_span=True)
    test("truth-free typed input and inactive parameter guard",inputs)
    result=dict(schema="s6c.independent_tracker_checks.v1",status="PASS" if all(x["status"]=="PASS" for x in checks) else "FAIL",
                code=binding(__file__),readme=binding(Path(__file__).with_name("README_S6C_TRACKING_REVIEW_CHECKS.md")),
                reviewed_source_original_path=str(source),reviewed_source=binding(snapshot),
                supplied_source_sha256=hashlib.sha256(raw).hexdigest(),
                source_unchanged_during_check=binding(source)["sha256"]==hashlib.sha256(raw).hexdigest(),
                historical_v2=binding(APP/"edge_speech_pipeline/research_tracking_v2.py"),
                checks=checks,passed=sum(x["status"]=="PASS" for x in checks),total=len(checks),
                models=0,hardware=0,new_empirical_speech_errors_claimed=0,
                scope="Independent synthetic action/lifecycle/control fixtures. Does not claim native integration or bank accuracy.")
    save(output/"CHECK_RECEIPT.json",result)
    print(json.dumps({k:v for k,v in result.items() if k in ("status","passed","total","source_unchanged_during_check")}))
    print(json.dumps([x for x in checks if x["status"]!="PASS"],indent=2))
    return 0 if result["status"]=="PASS" else 1

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=APP/"edge_speech_pipeline/research_tracking_v3.py")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.source,a.output))

