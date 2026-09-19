"""S6C separate-word/anonymous/route scoring. See README_S6C_ANALYSIS_V3.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
import csv,gzip,hashlib,json,math,os,time
from pathlib import Path
from importlib.metadata import version
for _name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[_name]="1"
import s6b_analysis as inherited
import s6c_scoring_extensions as extensions
from s6a_baseline_results import dependency_plan
from s6a_support_metrics import validate_support

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/"reports/S6C/20260910T123540Z"
S6B=SIM/"reports/S6B/20260909T230840Z"
BANK=SIM/"scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json"
BANK_SHA="69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18"
INPUT_SHA="97b20d821c671794b24b1f8a4a9d4049fd192767bd0a093309887c279b48e70d"
SCHEMA="jp_s6c_core_analysis.v3"
CODES=("s6c_analysis_v3.py","s6c_scoring_extensions.py","s6c_analysis_v2.py","s6c_analysis.py","s6b_analysis.py","s6a_text_metrics.py","s6a_cue_score.py","s6a_support_metrics.py","s6a_baseline_results.py","s4_h2_analysis.py","s5_statistics.py")

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def bind(p,expected=None):
 p=Path(p).resolve();raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if expected is not None and sha!=expected:raise ValueError("Changed declared input: "+str(p))
 return dict(path=str(p),bytes=len(raw),sha256=sha)
def verified(b):
 p=Path(b["path"]);raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=b["sha256"] or "bytes" in b and len(raw)!=b["bytes"]:raise ValueError("Declared input bytes differ: "+str(p))
 return json.loads(gzip.decompress(raw) if p.suffix==".gz" else raw)
def read(p):return verified(bind(p))
def save(p,v):
 import uuid
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise ValueError("New result namespace required: "+str(p))
 tmp=p.with_name("."+p.name+"."+uuid.uuid4().hex+".tmp")
 with tmp.open("x",encoding="utf-8") as f:json.dump(v,f,ensure_ascii=False,allow_nan=False,indent=2);f.write("\n");f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def csv_write(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with Path(p).open("x",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def numeric(v):return inherited.finite(v)

def route_key(row):
 pid=row.get("candidate_id",row.get("profile_id"))
 tap=row.get("stream",row.get("asr_tap"));identity=row.get("identity_tap",tap)
 if not isinstance(pid,str) or not pid or tap not in ("O0","O1") or identity not in ("O0","O1"):raise ValueError("Explicit candidate/ASR/identity route required")
 return pid,tap,identity

def expected_grid(index,allowed):
 ids=index.get("case_ids");routes=index.get("profile_routes")
 if not isinstance(ids,list) or len(ids)!=len(set(ids)) or not set(ids)<=allowed:raise ValueError("Explicit unique canonical case_ids required")
 if not isinstance(routes,list) or not routes:raise ValueError("Explicit profile_routes required; split routes must not imply two outputs")
 declared_routes=[route_key(r) for r in routes]
 if len(declared_routes)!=len(set(declared_routes)):raise ValueError("Duplicate profile route")
 if len({(p,t) for p,t,i in declared_routes})!=len(declared_routes):raise ValueError("Each candidate/ASR tap must have exactly one declared identity tap; use separate candidate IDs for distinct routes")
 expected={(p,t,i,c) for p,t,i in declared_routes for c in ids}
 rows=[(*route_key(r),r["case_id"]) for r in index["rows"]]
 if len(rows)!=len(set(rows)) or not set(rows)<=expected:raise ValueError("Duplicate or outside-grid prediction row")
 return expected

def validate_payload(value,item):
 pid,tap,itap=route_key(item)
 if (value.get("profile_id",value.get("candidate_id")),value.get("stream"),value.get("identity_tap",value.get("stream")),value.get("case_id"))!=(pid,tap,itap,item["case_id"]):raise ValueError("Prediction/index route identity mismatch")
 if value.get("schema") in ("jp_s6c_prediction.v1","jp_s6c_policy_prediction.v1") and (not isinstance(value.get("identity"),dict) or digest(value["identity"])!=value.get("prediction_key")):raise ValueError("S6C prediction identity digest mismatch")
 inherited.validate_prediction(value)

def lifecycle_metrics(value):
 tracker=value.get("snapshot",{}).get("tracker",{})
 counters={k:v for k,v in tracker.items() if numeric(v) or isinstance(v,bool)}
 final=tracker.get("counts",{})
 for k,v in final.items():
  if numeric(v):counters["final_"+k]=v
 observed=defaultdict(list)
 for d in value["decisions"]:
  for k,v in (d.get("lifecycle_counts") or {}).items():
   if numeric(v):observed[k].append(v)
 for k,v in observed.items():counters["peak_observed_"+k]=max(v)
 cues=Counter()
 for d in value["decisions"]:
  cue=d.get("cue") or {}
  cues["decisions"]+=1
  cues["qualified_cue_decisions"]+=cue.get("qualified_bearing_deg") is not None
  cues["retained_event_records"]+=len(d.get("lineage",[]))
 return dict(counters=counters,activation_counts=dict(cues),
   scope="Actual tracker snapshot/fresh decision counters. Active and dormant partition live; provisional overlaps those categories. Lifetime IDs, archive, retirements and capacity counters are separate. No correct-person or accuracy inference from activation.")

def analyze(value,scene,support,allowed):
 # Text scoring consumes real ASR final words/labels; inherited analyze never
 # uses stream for lexical arithmetic. Evidence geometry must use ID tap.
 original_stream=value["stream"];identity_tap=value.get("identity_tap",original_stream)
 local=deepcopy(value);local["stream"]=identity_tap
 result=inherited.analyze(local,scene,support,allowed)
 result["stream"]=original_stream;result["identity_tap"]=identity_tap
 result["route"]=original_stream+"_ASR_"+identity_tap+"_ID"
 result["schema"]=SCHEMA
 result["lifecycle"]=lifecycle_metrics(value)
 result["oracle_like"]=bool(value.get("oracle_like",value.get("identity",{}).get("oracle_like",False)))
 result["neural_source_binding"]=value.get("identity",{}).get("source")
 result["evidence_mapping_tap"]=identity_tap
 result["asr_lexical_tap"]=original_stream
 result["naming_metrics"]={"status":"NOT_IMPLEMENTED_IN_CORE_SCORER","reason":"Actual displayed names are included in separate label-view cp metrics, but that permutation metric is not real identity accuracy. A source-bound gallery truth-map and dedicated name/exposure scorer are required.","assigned_name_decisions":sum(bool(d.get("known_name")) for d in value["decisions"])}
 result["snapshot"]={"tracker_lifecycle":result["lifecycle"],"identity":value.get("snapshot",{}).get("scheduler",{}).get("identity")}
 for view,score in result["text_metrics"].items():
  score["attributed_cpwer"].pop("s6b_label_view",None)
  score["attributed_cpwer"]["s6c_label_view"]=view
 result["timing_scope"]="Inherited .75-second source-evidence expiry and source-support scoring only. Anonymous evidence and windows use the identity-tap mapping once; lexical counts use actual ASR-tap words. Modeled availability is not phonetic latency, actual native release, or CM5 time. Dedicated retained name exposure remains separate."
 return result

def tables(records):
 scenes=[];turns=[];regions=[];lifecycle=[]
 for r in records:
  base=dict(identity_tap=r["identity_tap"],route=r["route"],oracle_like=r["oracle_like"])
  scenes.append({**inherited.scene_row(r),**base})
  for t in r["turns"]:turns.append(dict(case_id=r["case_id"],stream=r["stream"],profile_id=r["profile_id"],population=r["population"],**base,**{k:v for k,v in t.items() if k!="label_samples"}))
  for region in r["regions"]:regions.append(dict(case_id=r["case_id"],stream=r["stream"],profile_id=r["profile_id"],population=r["population"],**base,**region))
  lifecycle.append(dict(case_id=r["case_id"],stream=r["stream"],profile_id=r["profile_id"],**base,**r["lifecycle"]["counters"],activation_counts=r["lifecycle"]["activation_counts"],lineage_counts=r["lineage_counts"]))
 summary,short=inherited.summarize(scenes,turns)
 # Do not invoke the old recipe-id cost deduplicator: N07's full policy and
 # routing can legitimately give different calls/costs under one recipe label.
 resources=[];strata=[];seen={}
 for r in records:
  source=r["neural_source_binding"]
  key=digest(source) if source is not None else digest(dict(profile=r["profile_id"],route=r["route"],case_id=r["case_id"],cost=r["recipe_costs"]))
  if key in seen:
   if seen[key]["recipe_costs"]!=r["recipe_costs"]:raise ValueError("Same exact bound source has inconsistent cost")
   seen[key]["profile_reusers"].append(r["profile_id"]);continue
  seen[key]=dict(neural_source_key=key,source_binding=source,profile_reusers=[r["profile_id"]],case_id=r["case_id"],stream=r["stream"],identity_tap=r["identity_tap"],recipe_id=r["recipe_id"],duration_sec=r["duration_sec"],recipe_costs=r["recipe_costs"],scope="Exact source receipt binding when supplied; otherwise conservative per-profile record. Nested API/dispatch costs and overlapping native lanes are not additive.")
 resources=list(seen.values())
 for pid,stream in sorted({(r["profile_id"],r["stream"]) for r in scenes}):
  chosen=[r for r in scenes if (r["profile_id"],r["stream"])==(pid,stream)]
  groups=defaultdict(list)
  for row in chosen:
   for dim,labels in dict(room=[row["room"]],family=[row["family_id"]],historical_split=[row["historical_split"]],**row["strata"]).items():
    for label in labels:groups[dim,str(label),row["population"]].append(row)
  for (dim,label,pop),rs in sorted(groups.items()):
   pooled=inherited.pool(rs,pid,stream,pop)
   pooled.update(stratum_dimension=dim,stratum_value=label,membership_scope="Whole-scene memberships may overlap; do not sum across corpus/quality/noise values.")
   strata.append(pooled)
 return scenes,turns,summary,short,regions,lifecycle,resources,strata

def registered_candidates(specs=(),expected_count=184):
 return extensions.registry(specs,expected_count)


def fixtures():
 out=extensions.fixture_checks()["checks"]
 registry,_=registered_candidates();assert len(registry)==184;out.append("184 registered labels and exact amendment parents admitted")
 def passed(name):out.append(name)
 grid=dict(case_ids=["A","B"],profile_routes=[dict(candidate_id="C",stream="O0",identity_tap="O1")],rows=[dict(candidate_id="C",stream="O0",identity_tap="O1",case_id="A")])
 assert len(expected_grid(grid,{"A","B"}))==2;passed("fixed split route has one declared output per scene")
 bad=deepcopy(grid);bad["rows"]*=2
 try:expected_grid(bad,{"A","B"})
 except ValueError:passed("duplicate prediction route rejected")
 else:raise AssertionError("Duplicate accepted")
 bad=deepcopy(grid);bad["profile_routes"].append(dict(candidate_id="C",stream="O0",identity_tap="O0"))
 try:expected_grid(bad,{"A","B"})
 except ValueError:passed("same candidate ASR tap cannot silently pool distinct identity routes")
 else:raise AssertionError("Ambiguous pooled route accepted")
 old=inherited.fixtures();assert old["status"]=="PASS";out.extend(old["tests"])
 assert route_key({"profile_id":"B00","stream":"O0"})==("B00","O0","O0");passed("historical same-tap adapter is explicit")
 return dict(status="PASS",checks=out)

def run(args):
 index_path=args.index if args.index.is_absolute() else REPORT/args.index
 index_binding=bind(index_path);index=verified(index_binding)
 bank_binding=bind(BANK,BANK_SHA);bank=verified(bank_binding);scenes={s["case_id"]:s for s in bank["scenes"]};allowed=frozenset(scenes)
 input_binding=bind(S6B/"INPUT_INDEX.json",INPUT_SHA);inputs=verified(input_binding)["rows"];inputrows={(r["case_id"],r["stream"]):r for r in inputs}
 expected=expected_grid(index,allowed)
 registry,registry_bindings=registered_candidates(args.registry_extension,args.expected_candidates)
 registered_ids={r["candidate_id"] for r in registry}
 if any(p not in registered_ids for p,t,i,c in expected):raise ValueError("Prediction candidate lacks explicit admitted registration")
 if args.require_complete and (index.get("status")!="COMPLETE" or len(index["rows"])!=len(expected)):raise ValueError("Index does not cover its exact declared grid")
 output=REPORT/args.output_subdir
 if Path(args.output_subdir).is_absolute() or REPORT.resolve() not in output.resolve().parents:raise ValueError("Output must be a child of current S6C report")
 # Completed aggregate namespaces are immutable. Interrupted scoring may reuse
 # exact per-output identities, but never overwrite existing aggregate files.
 if (output/"ANALYSIS_RECEIPT.json").exists():raise ValueError("Completed analysis exists; use a new versioned namespace")
 output.mkdir(parents=True,exist_ok=True)
 codes=[bind(SIM/"scripts"/n) for n in CODES];packages={n:version(n) for n in ("numpy","scipy","meeteval")}
 if packages["meeteval"]!="0.4.3":raise ValueError("Pinned MeetEval0.4.3 required")
 records=[];coverage=[];supports={};started=time.perf_counter()
 selected=index["rows"][:args.limit] if args.limit else index["rows"]
 for item in selected:
  pid,tap,itap=route_key(item);cid=item["case_id"];route=tap+"_ASR_"+itap+"_ID";keyrow=dict(profile_id=pid,stream=tap,identity_tap=itap,case_id=cid)
  if item.get("status","COMPLETE") not in ("COMPLETE","COMPLETE_REUSED"):
   coverage.append(dict(**keyrow,status=item.get("status"),error="Unsuccessful index output is not empty ASR"));continue
  try:
   value=verified(item["result"]);validate_payload(value,item)
   sb=inputrows[cid,itap]["support"]
   if cid in supports:
    if supports[cid][0]!=sb:raise ValueError("Same-scene declared support binding differs")
   else:supports[cid]=(sb,verified(sb)["support"])
   support=supports[cid][1];validate_support(scenes[cid],support)
   identity=dict(prediction=item["result"],support=sb,bank=bank_binding,codes=codes,registry_sources=registry_bindings,packages=packages,metric_schema=SCHEMA,asr_tap=tap,identity_tap=itap)
   identity_key=digest(identity);target=output/"scores"/pid/cid/(route+".json")
   if target.exists():
    result=read(target)
    if result.get("analysis_key")!=identity_key or result.get("analysis_identity")!=identity or result.get("schema")!=SCHEMA:raise ValueError("Changed per-output analysis dependency")
   else:
    result=analyze(value,scenes[cid],support,allowed);result.update(analysis_key=identity_key,analysis_identity=identity);save(target,result)
   records.append(result);coverage.append(dict(**keyrow,status="SCORED",result=bind(target)))
  except Exception as exc:coverage.append(dict(**keyrow,status="FAILED_ANALYSIS",error=type(exc).__name__+": "+str(exc)))
  if len(coverage)%100==0:print(json.dumps(dict(phase="S6C_CORE_SCORING",scored=len(records),attempted=len(coverage),requested=len(expected),elapsed_sec=time.perf_counter()-started)),flush=True)
 present={(r["profile_id"],r["stream"],r["identity_tap"],r["case_id"]) for r in coverage}
 for pid,tap,itap,cid in sorted(expected-present):coverage.append(dict(profile_id=pid,stream=tap,identity_tap=itap,case_id=cid,status="NOT_AVAILABLE_OR_NOT_SCORED"))
 scene_rows,turn_rows,summary,short,regions,lifecycle,resources,strata=tables(records)
 registry_path=REPORT/"design/REGISTERED_DESIGN_V1.json"
 dependency=dependency_plan(scenes,bank["selected_sources"])
 comparisons,uncertainty=inherited.paired_comparisons(scene_rows,[dict(profile_id=r["candidate_id"],parent=r.get("parent")) for r in registry],dependency,bootstrap=not args.no_bootstrap)
 table_rows={"SCENE_RESULTS.csv":scene_rows,"TURN_RESULTS.csv":turn_rows,"PROFILE_RESULTS.csv":summary,"SHORT_REPLY_RESULTS.csv":short,"REGION_RESULTS.csv":regions,"TRACK_LIFECYCLE_RESULTS.csv":lifecycle,"RECIPE_COST_RESULTS.csv":resources,"STRATA_RESULTS.csv":strata,"PAIRED_COMPARISONS.csv":comparisons,"COVERAGE.csv":coverage}
 for name,rows in table_rows.items():csv_write(output/name,rows)
 for name,value in (("PROFILE_RESULTS.json",summary),("SHORT_REPLY_RESULTS.json",short),("PAIRED_UNCERTAINTY.json",uncertainty),("DEPENDENCY_PLAN.json",dependency)):save(output/name,value)
 failures=[r for r in coverage if r["status"]!="SCORED"]
 success=index.get("status")=="COMPLETE" and len(records)==len(expected) and not failures
 full_routes=[]
 for pid,tap,itap in sorted({route_key(r) for r in index["profile_routes"]}):
  cases={r["case_id"] for r in coverage if r["status"]=="SCORED" and (r["profile_id"],r["stream"],r["identity_tap"])==(pid,tap,itap)}
  if cases==allowed:full_routes.append(dict(profile_id=pid,stream=tap,identity_tap=itap,scenes=240))
 receipt=dict(schema=SCHEMA,status="COMPLETE_REQUESTED_INDEX" if success else "PARTIAL_RESUMABLE",
  index=index_binding,input_index=input_binding,bank=bank_binding,codes=codes,packages=packages,registry=bind(registry_path),registry_sources=registry_bindings,
  tests=fixtures(),requested=len(expected),scored=len(records),unscored=len(failures),full240_confirmed_routes=full_routes,
  profile_routes=index["profile_routes"],case_ids=index["case_ids"],tables=[bind(output/n) for n in table_rows],
  requested_source_turn_outputs=sum(r["source_turns"] for r in scene_rows),
  observed_complete_subsecond_turn_outputs=sum(r["population"] in inherited.COMPLETE and r["whole_clip_bin"]=="<1s" for r in turn_rows),
  observed_complete_one_to_two_sec_turn_outputs=sum(r["population"] in inherited.COMPLETE and r["whole_clip_bin"]=="1-<2s" for r in turn_rows),
  results=summary,short_results=short,elapsed_sec=time.perf_counter()-started,
  scope="Exact declared routes only. Full240 route confirmation is listed separately. Primary, overlap-MIMO, incomplete-target and strict-empty denominators remain separate. Anonymous tracking uses identity-tap source mapping once; actual label-view cpWER is not name accuracy. All failures/unavailable rows retained.",
  naming_metrics_status="Dedicated gallery-bound identification and exposure analysis remains required; core completion does not imply it is complete.")
 save(output/"ANALYSIS_RECEIPT.json",receipt)
 print(json.dumps({k:receipt[k] for k in ("status","requested","scored","unscored","full240_confirmed_routes")},indent=2))
 if args.require_complete and not success:raise RuntimeError("Not every required declared output scored; see COVERAGE.csv")
 return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--index",type=Path);p.add_argument("--output-subdir",default="core_analysis_v3")
 p.add_argument("--require-complete",action="store_true");p.add_argument("--no-bootstrap",action="store_true")
 p.add_argument("--registry-extension",nargs=2,action="append",default=[],metavar=("PATH","SHA256"))
 p.add_argument("--expected-candidates",type=int,default=184)
 p.add_argument("--limit",type=int);p.add_argument("--test",action="store_true")
 args=p.parse_args()
 if args.test:print(json.dumps(fixtures(),indent=2));return
 if args.index is None:p.error("--index required")
 if args.limit is not None and (args.limit<1 or args.require_complete):p.error("Positive --limit is incompatible with --require-complete")
 run(args)
if __name__=="__main__":main()
