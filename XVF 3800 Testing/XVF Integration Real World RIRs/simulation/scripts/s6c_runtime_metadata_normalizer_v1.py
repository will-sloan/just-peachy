"""Finite runtime metadata joins; README_S6C_RUNTIME_METADATA_NORMALIZER_V1.md."""
from __future__ import annotations
import argparse,csv,hashlib,importlib,io,json,math,re,sys
from datetime import datetime,timezone
from pathlib import Path
from copy import deepcopy
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/"reports/S6C/20260910T123540Z"
PINS={
 "s6c_fast_observer_analysis_v1.py":"e5497ec28daa6c5f823fde53e7f1253cf655427cd30f8eab067de5e9a4c0f530",
 "s6c_execution_inventory_v7.py":"fc23ff6650a34c927211d142e61b9dcf7afe7ee07e832c51573ae2da0dc3c7a3",
 "s6c_final_disposition_v1.py":"ead12d3fce56177914511cd8af983e7764af5c497d3f154789ea01e2c114696e"}
WORK_SHA="5d84d493a377eb7b991e821cf59e412da5103ba7e17786e197bb2dd9c1ecc8dd"
CAP=32*2**20
KINDS={"canonical","sentinel","cross","historical","long_c","long_b36"}

def require(value,message):
 if not value:raise ValueError(message)

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def pairs(items):
 out={}
 for k,v in items:require(k not in out,"Duplicate JSON key");out[k]=v
 return out

def parse(raw):
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError("Nonfinite JSON")))

def exact(path,expected=None):
 p=Path(path).resolve();require(p.suffix.lower() in {".json",".py",".md",".csv"},"Metadata/code only")
 require(p.stat().st_size<=CAP,"Bounded metadata");raw=p.read_bytes();require(len(raw)<=CAP,"Metadata grew")
 b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 require(expected is None or b==expected,"Exact binding differs: "+str(p));return raw,b

def module(name):
 path=HERE/(name+".py");raw,b=exact(path);require(b["sha256"]==PINS[path.name],"Held module differs")
 value=importlib.import_module(name);require(Path(value.__file__).resolve()==path,"Wrong import origin");return value

def sources():
 return [exact(p)[1] for p in (Path(__file__),HERE/"README_S6C_RUNTIME_METADATA_NORMALIZER_V1.md",*(HERE/n for n in PINS))]

def doc(reader,b):
 value,actual=reader.read(Path(b["path"]),b);require(actual==b,"Expected source binding");return value

def contains(value,b):
 if isinstance(value,dict):
  if value==b:return True
  return any(contains(v,b) for v in value.values())
 return isinstance(value,list) and any(contains(v,b) for v in value)

def unique(rows,key,message):
 result={}
 for row in rows:
  k=key(row);require(k not in result,message);result[k]=row
 return result

def finite(x):
 return type(x) in (int,float) and math.isfinite(x)

def owners_closed(rows):
 if not rows:return None
 states=[]
 for row in rows:
  if type(row.get("pid")) is not int or row["pid"]<=0 or not finite(row.get("creation_time")) or row["creation_time"]<=0:return None
  state=row.get("process_state",{}).get("alive")
  if state is not None and type(state) is not bool:raise ValueError("Boolean/null process state")
  states.append(state)
 return False if True in states else None if None in states else True

def condition_key(row):
 profile=deepcopy(row["profile"]);profile.pop("profile_id")
 return digest(dict(profile=profile,cue_condition=row["cue_condition"],gallery_condition=row["gallery_condition"],enrollment_tier=row["enrollment_tier"]))

def c_condition(row,registered):
 key=(row["candidate_id"],row["asr_tap"],row["identity_tap"])
 ref=registered[key]
 value={k:row[k] for k in ("asr_tap","identity_tap","recipe_id","cue_condition","gallery_condition","enrollment_tier")}
 value.update(profile_sha256=digest(row["profile"]),executable_condition_sha256=condition_key(row))
 require(all(value[k]==ref[k] for k in value),"Actual executed C condition differs from final registered route")
 require(digest(row)==ref["row_sha256"],"Actual full registered row differs")
 return value

def historical_condition(job,originals,generation):
 pid=job["profile_id"];require(pid in {"B00","B01","B36"},"Explicit historical comparator only")
 require((generation=="baseline")== (pid=="B00"),"Original B00/research generation mismatch")
 row=originals[pid];tap=job["stream"]
 # Registration label digest is the assembler's historical key, not a claim
 # that the old registration CSV contains executable settings.
 return dict(asr_tap=tap,identity_tap=tap,recipe_id=job["recipe_id"],
  cue_condition="CUES_OFF",gallery_condition="NONE",enrollment_tier=None,
  original_registration_row_sha256=digest(row),actual_profile_sha256=digest(job["profile"]),
  historical_generation="S6A_B00_DEFAULT" if pid=="B00" else "S6B_epoch2")

def c_tail(native,finalization,source):
 t=native.get("final_telemetry",{});scheduler=t.get("scheduler",{});n=source["duration_samples"];duration=source["duration_sec"]
 flags={
 "native_complete":native.get("status")=="COMPLETE",
 "full_source_duration":native.get("source_duration_sec")==duration and t.get("source_duration_sec")==duration,
 "full_asr_cursor":t.get("asr_cursor_sec")==duration,
 "paired_final_samples":finalization.get("source_samples")==finalization.get("identity_samples")==n,
 "finalized":finalization.get("state")=="COMPLETED" and "finalization_error" in finalization and finalization["finalization_error"] is None and finalization.get("event_and_transcript_handles_closed") is True and finalization.get("resident_bundle_lease_retained") is False and finalization.get("live_lanes_at_finalization")==[],
 "drained_scheduler":scheduler.get("closed") is True and scheduler.get("pending_events")==0,
 "no_audio_loss":all(type(t.get(k)) in (int,float) and t[k]==0 for k in ("audio_frames_dropped","portaudio_input_overflows","raw_capture_reserve_failures"))}
 return dict(tail_complete=True if all(flags.values()) else None,full_source_checks=flags,
  dispatch_tail_proof=None,dispatch_tail_scope="No separate discrete dispatch coverage certificate normalized for C; original completed analysis remains bound.",
  drain_available="closed" in scheduler and "pending_events" in scheduler,drain_proof={k:scheduler.get(k) for k in ("closed","pending_events")},
  tail_scope="Full paired source samples, terminal ASR cursor and drained finalization; not lexical first/last-word correctness or acoustic clipping.")

def historical_tail(native,job):
 duration=job["duration_sec"];journal=native.get("journal",{});t=native.get("summary",{}).get("telemetry",{})
 flags={"native_complete":native.get("status")=="COMPLETE","native_pcm_exact":native.get("native_pcm_exact") is True,
  "asr_cursor_complete":native.get("asr_cursor_complete") is True,
  "duration":native.get("source_duration_sec")==duration and abs(t.get("asr_cursor_sec",-1)-duration)<=1e-7,
  "whole_journal":journal.get("sha256")==job["input_pcm_sha256"] and journal.get("bytes")==round(duration*16000)*2,
  "no_audio_loss":all(type(t.get(k)) in (int,float) and t[k]==0 for k in ("audio_frames_dropped","portaudio_input_overflows","raw_capture_reserve_failures"))}
 pid=job["profile_id"];delivery=native.get("native_dispatch_delivery")
 if pid!="B00":
  flags["research_dispatch"]=isinstance(delivery,dict) and all(delivery.get(k) is True for k in ("no_gaps_or_duplicates","starts_at_zero","ends_at_full_duration","exact_samples"))
  scheduler=t.get("scheduler",{});flags["drained_scheduler"]=scheduler.get("closed") is True and scheduler.get("pending_events")==0
 return dict(tail_complete=True if all(flags.values()) else None,full_source_checks=flags,
  dispatch_tail_proof=None if pid=="B00" else delivery,drain_available=False if pid=="B00" else True,
  tail_scope="B00: exact full PCM journal and terminal source/ASR cursor only; research dispatch/drain instrumentation unavailable." if pid=="B00" else "Original research full-source dispatch and terminal drained scheduler.",
  lexical_boundary_correctness_available=False)

def runtime_row(input_id,kind,pid,condition,native_binding,duration,owner_rows,tail,proofs,case=None,repetition=None,job_id=None):
 closed=owners_closed(owner_rows)
 return dict(input_id=input_id,kind="long" if kind.startswith("long_") else "paced",family=kind,candidate_id=pid,
  **condition,condition_sha256=condition.get("executable_condition_sha256",condition.get("original_registration_row_sha256")),
  condition=condition,status="COMPLETE" if closed is True and tail["tail_complete"] is True else "PENDING_OR_UNVERIFIED",
  case_id=case,repetition=repetition,job_id=job_id,source_duration_sec=duration,
  continuous=kind.startswith("long_"),owner_closed=closed,owners=owner_rows,native_result_sha256=native_binding["sha256"],
  native_result=native_binding,**tail,proof_bindings=proofs,
  scope="Admitted actual metadata and completed original analysis only. No new scoring/model/raw-log read or final operating selection.")

def load_registration(reader,b):
 require(b["sha256"]==WORK_SHA,"Exact reviewed working registration receipt")
 work=doc(reader,b);require(work["status"]=="COMPLETE_WORKING_PROPOSAL_ONLY","Working registration status")
 def output(name):
  matches=[x for x in work["outputs"] if Path(x["path"]).name==name];require(len(matches)==1,"Unique registration output");return matches[0]
 rb=output("REGISTERED_ROUTE_SETTINGS_PROVENANCE.json");routes=doc(reader,rb)
 ob=output("ORIGINAL_REGISTRATION_SNAPSHOT.csv");raw,actual=exact(ob["path"],ob)
 rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))));require(len(rows)==160,"Original registration160")
 originals=unique(rows,lambda r:r["candidate_id"],"Duplicate original registration")
 return unique(routes["routes"],lambda r:(r["candidate_id"],r["asr_tap"],r["identity_tap"]),"Duplicate registered route"),originals,[b,rb,actual]

def analysis_chain(reader,req,observer,A):
 result_b=req["analysis_receipt"];result=doc(reader,result_b);apb=result["plan"];plan=doc(reader,apb)
 request_bindings=[b for b in plan["sources"] if Path(b["path"]).name=="REQUEST.json" and "fast_post_analysis_admission" in Path(b["path"]).parts]
 require(len(request_bindings)==1,"Exactly one reviewed fast-analysis input request")
 request_b=request_bindings[0];request=doc(reader,request_b)
 require(request["schema"]=="s6c-fast-post-analysis-inputs.v1" and request["status"]=="EXPLICIT_INPUTS_FOR_CLOSED_ANALYSIS","Actual fast analysis request")
 require(request["kind"]==req["kind"] and request["generation"]==req.get("generation") and request["observer_index"]==observer,"Analysis family/generation/observer context differs")
 require(request["sources"]==A.sources(),"Analysis helper/inventory sources differ")
 inputs=request["inputs"];expected={"admissions":req["admissions"]} if req["kind"]=="long_c" else {"manifest":req["manifest"]}
 if req["kind"] in {"canonical","sentinel","cross"}:expected["index"]=req["paced_index"]
 require(inputs==expected,"Exact analysis/runtime inputs differ")
 require(observer in plan["sources"] and request_b in plan["sources"],"Analysis plan did not bind explicit observer/request")
 adapter,original=A.make_adapter(req["kind"],observer,request_b,list(req.get("admissions",[]))+[x for x in (req.get("manifest"),req.get("paced_index"),apb) if x])
 callback="source_bindings" if req["kind"] in {"canonical","sentinel","cross"} else "own_sources" if req["kind"]=="long_b36" else "sources"
 require(plan["sources"]==adapter.namespace[callback](),"Original analysis source context differs")
 wanted={"long_c":"COMPLETE_DIRECT_OBSERVATIONS","long_b36":"COMPLETE_OBSERVATIONS_ONLY"}.get(req["kind"],"COMPLETE")
 require(result["status"]==wanted,"Completed original post-analysis required")
 require(plan["schema"]==adapter.namespace["SCHEMA"] and result["schema"]==plan["schema"],"Exact original analysis schema")
 if req["kind"] in {"canonical","sentinel","cross"}:
  require(result["manifest"]==req["manifest"] and result["paced_index"]==req["paced_index"] and result["failed"]==0,"Completed paired analysis input/counts")
 return result,result_b,adapter,[result_b,apb,request_b,observer]

def canonical_rows(reader,req,observer,A,registered):
 result,rb,adapter,proofs=analysis_chain(reader,req,observer,A);v=adapter.inventory
 plan,pb,spec=v.admit_plan(reader,req["manifest"]);index,ib=v.admit_paced_index(reader,req["paced_index"],plan,pb)
 require(result["requested"]==result["completed"]==len(plan["jobs"]),"Complete analysis cardinality")
 measurements=[(doc(reader,b),b) for b in result["cell_measurements"]]
 by=unique(measurements,lambda x:x[0]["job_id"],"Duplicate analysis job")
 require(set(by)=={j["job_id"] for j in plan["jobs"]},"Exact analysis/native job set")
 rows=[]
 for job in plan["jobs"]:
  chain=v.admit_complete_cell(reader,job,plan,pb,spec);m,mb=by[job["job_id"]]
  for k in ("job_id","candidate_id","case_id","asr_tap","identity_tap","repetition"):require(m[k]==job[k],"Analysis/native identity mismatch")
  require(m["status"]=="COMPLETE" and m["native_result"]==chain["native_binding"] and m["completion"]==chain["complete_binding"] and m["cell_result"]==chain["cell_binding"],"Exact analyzed native chain")
  source=doc(reader,job["source"]);fb=next(b for b in chain["native"]["native_artifacts"] if Path(b["path"]).name=="session_finalization_v3.json")
  final=doc(reader,fb);tail=c_tail(chain["native"],final,source)
  rows.append(runtime_row(req["input_id"],req["kind"],job["candidate_id"],c_condition(job["profile_row"],registered),
   chain["native_binding"],source["duration_sec"],chain["owner_observations"]+chain["coordinator_owner_observations"],tail,
   proofs+[pb,ib,mb,chain["complete_binding"],fb,job["source"]],job["case_id"],job["repetition"],job["job_id"]))
 return rows

def historical_rows(reader,req,observer,A,originals):
 result,rb,adapter,proofs=analysis_chain(reader,req,observer,A);v=adapter.inventory
 plan,pb,spec=v.admit_plan(reader,req["manifest"]);mod=importlib.import_module("s6c_historical_paced_analysis_v1")
 jobs=mod.selected_jobs(plan,req["generation"]);require(result["requested"]==result["completed"]==len(jobs),"Historical generation cardinality")
 by=unique([(doc(reader,b),b) for b in result["measurements"]],lambda x:x[0]["job"]["job_id"],"Duplicate historical measurement")
 require(set(by)=={j["job_id"] for j in jobs},"Exact historical generation jobs")
 records,owners=v.invocation_rows(reader,plan,pb);v.ensure_invocations_closed(records,owners);rows=[]
 for job in jobs:
  physical,native,nb,cb,tb,owned,lb=mod.cell_chain(v,reader,job,plan,pb);m,mb=by[job["job_id"]]
  require(m["status"]=="COMPLETE" and m["job"]==job and m["native_result"]==nb and m["completion"]==cb,"Historical analysis/native chain")
  current=[dict(pid=p,creation_time=c,process_state=v.process_state(p,c)) for p,c in owned]
  rows.append(runtime_row(req["input_id"],"historical",job["profile_id"],historical_condition(job,originals,req["generation"]),
   nb,job["duration_sec"],current+owners,historical_tail(native,job),proofs+[pb,mb,cb,lb],job["case_id"],job["repetition"],job["job_id"]))
 return rows

def long_c_rows(reader,req,observer,A,registered):
 result,rb,adapter,proofs=analysis_chain(reader,req,observer,A)
 observations=[(doc(reader,b),b) for b in result["results"]]
 require(result["sessions"]==len(observations)==len(req["admissions"]),"Exact long analysis/session count")
 by=unique(observations,lambda x:x[0]["native_result"]["sha256"],"Duplicate analyzed native long result");rows=[]
 for ab in req["admissions"]:
  chain=adapter.namespace["admit_closed"](reader,ab);record=chain["record"];plan=chain["plan"];native=chain["native"];nb=chain["native_binding"];m,mb=by.pop(nb["sha256"])
  require(m["status"]=="COMPLETE_DIRECT_OBSERVATIONS" and m["native_result"]==nb and m["profile"]==plan["profile_row"] and m["source_duration_sec"]==native["source_duration_sec"],"Exact long observation/native source")
  owner=record["owner"];owners=[dict(**owner,process_state=adapter.inventory.process_state(owner["pid"],owner["creation_time"]))]
  rows.append(runtime_row(req["input_id"],"long_c",plan["profile_row"]["candidate_id"],c_condition(plan["profile_row"],registered),nb,
   native["source_duration_sec"],owners,c_tail(native,chain["finalization"],chain["composition"]),
   proofs+[ab,mb,record["manifest"],record["closure"],chain["finalization_binding"]],repetition=1))
 require(not by,"Unmatched long analysis session");return rows

def long_b36_rows(reader,req,observer,A,originals):
 result,rb,adapter,proofs=analysis_chain(reader,req,observer,A);mod=importlib.import_module("s6c_long_b36_diagnostics_v1")
 plan,pb,a,closure=mod.closed(adapter.inventory,reader,req["manifest"]);job=plan["jobs"][0]
 outer=doc(reader,closure["native"]["continuous_result"]);nb=outer["native_result"];native=doc(reader,nb)
 require(result["manifest"]==pb and result["native_result"]==nb and result["outer_result"]==closure["native"]["continuous_result"],"Exact B36 long analysis chain")
 require(result["profile_id"]=="B36" and result["tap"]==job["stream"] and result["logical_sessions"]==1 and result["source_samples"]==29238826 and result["duration_sec"]==job["duration_sec"],"Actual B36 continuous scope")
 return [runtime_row(req["input_id"],"long_b36","B36",historical_condition(job,originals,"research"),nb,job["duration_sec"],
  closure["current_owners"],historical_tail(native,job),proofs+[pb,outer["native_result"],closure["native"]["continuous_result"]],repetition=1,job_id=job["job_id"])]

def physical_rows(reader,item):
 inventory_b=item["inventory"];inv=doc(reader,inventory_b)
 require(inv["schema"]=="s6c-execution-inventory.v1" and inv.get("adapter_schema")=="s6c-execution-inventory-additive.v7","Explicit V7 inventory authority")
 require(inv["status"]=="WHOLE_STUDY_COUNTING_WITH_EXPLICIT_PRIOR_AND_FAST_APPEND","Whole-study inventory result")
 pb=inv["outputs"]["physical_json"];data=doc(reader,pb);require(len(data)==inv["unique_physical_attempts_observed"],"Inventory physical denominator")
 by=unique(data,lambda r:r["physical_id"],"Duplicate inventory physical identity");ids=item["physical_ids"];require(ids and len(ids)==len(set(ids)),"Explicit distinct physical IDs")
 rows=[]
 for pid in ids:
  row=by[pid];matches=[o for o in inv["owner_identity_summary"] if o.get("pid")==row.get("pid") and o.get("creation_time")==row.get("creation_time")]
  closure=owners_closed(matches);alive=None if closure is None else not closure
  rows.append(dict(input_id=item["input_id"],kind="physical",candidate_id=row["candidate_id"],physical_id=pid,
   pid=row.get("pid"),creation_time=row.get("creation_time"),alive=alive,status=row["status"],
   native_session_complete=row.get("native_session_complete"),session_dir=row.get("session_dir"),
   asr_tap=row.get("asr_tap"),identity_tap=row.get("identity_tap"),closed_cell_analysis_eligible=row.get("closed_cell_analysis_eligible"),
   proof_bindings=[inventory_b,pb]+row.get("receipt_bindings",[]),inventory_observed_utc=inv.get("created_utc"),
   scope="One exact inventory physical row, including failed/unknown attempts; no inference from scores or prepared plans, no cross-authority sum. Closure is as recorded by this inventory."))
 return rows

def native_session(native):
 if native.get("session_dir"):
  return str(Path(native["session_dir"]).resolve())
 journals=native.get("native_journals",{})
 require(journals,"Actual native session identity unavailable")
 parents={str(Path(b["path"]).resolve().parent) for b in journals.values()}
 require(len(parents)==1,"Native journals span multiple sessions")
 return next(iter(parents))

def require_distinct_runtime_sessions(rows):
 result_paths=set();result_hashes=set();sessions=set()
 for row in rows:
  b=row["native_result"];path=str(Path(b["path"]).resolve()).casefold();sha=b["sha256"]
  require(row.get("native_session_dir"),"Explicit actual native session identity required")
  session=str(Path(row["native_session_dir"]).resolve()).casefold()
  require(path not in result_paths and sha not in result_hashes and session not in sessions,"Actual native result/session repeated across runtime requests")
  result_paths.add(path);result_hashes.add(sha);sessions.add(session)
 return rows

def validate_request(req):
 require(req.get("kind") in KINDS and isinstance(req.get("input_id"),str) and req["input_id"],"Explicit request family/ID")
 allowed={"input_id","kind","analysis_receipt"}
 if req["kind"]=="long_c":
  allowed.add("admissions");require(isinstance(req.get("admissions"),list) and req["admissions"],"Actual outer admissions required")
  require(len({digest(b) for b in req["admissions"]})==len(req["admissions"]),"Duplicate outer admission")
 else:allowed.add("manifest")
 if req["kind"] in {"canonical","sentinel","cross"}:allowed.add("paced_index")
 if req["kind"]=="historical":allowed.add("generation");require(req.get("generation") in {"baseline","research"},"Explicit historical generation")
 require(set(req)==allowed,"Exact mode-specific request fields")
 return req

def run(args):
 require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Quiet lease remains; no normalization")
 A=module("s6c_fast_observer_analysis_v1");V=module("s6c_execution_inventory_v7");module("s6c_final_disposition_v1")
 raw,sb=exact(args.spec);require(sb["sha256"]==args.spec_sha256,"Explicit spec hash");spec=parse(raw)
 require(spec["schema"]=="s6c-runtime-normalization-inputs.v1" and spec["status"]=="EXPLICIT_FINITE_SCOPE","Normalizer specification")
 require(re.fullmatch(r"[A-Za-z0-9_-]{1,70}",args.namespace),"Simple fresh namespace")
 out=REPORT/"runtime_normalization"/args.namespace;require(not out.exists(),"Preserve prior output");out.mkdir(parents=True)
 reader=V.base.MetadataReader(out);V.admit_observer_index(reader,spec["observer_index"]);registered,originals,reg_sources=load_registration(reader,spec["working_registration"])
 unique(spec["requests"]+spec.get("physical_inventories",[]),lambda r:r["input_id"],"Duplicate explicit input ID")
 runtime=[];physical=[];seen=set()
 try:
  for req in spec["requests"]:
   validate_request(req);require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"New quiet lease")
   key=(req["kind"],digest(req.get("manifest",req.get("admissions"))),req.get("generation"));require(key not in seen,"Duplicate runtime authority/generation");seen.add(key)
   if req["kind"] in {"canonical","sentinel","cross"}:rows=canonical_rows(reader,req,spec["observer_index"],A,registered)
   elif req["kind"]=="historical":rows=historical_rows(reader,req,spec["observer_index"],A,originals)
   elif req["kind"]=="long_c":rows=long_c_rows(reader,req,spec["observer_index"],A,registered)
   else:rows=long_b36_rows(reader,req,spec["observer_index"],A,originals)
   runtime+=rows
  for item in spec.get("physical_inventories",[]):physical+=physical_rows(reader,item)
  require(runtime or physical,"Explicit nonempty normalization")
  for row in runtime:row["native_session_dir"]=native_session(doc(reader,row["native_result"]))
  require_distinct_runtime_sessions(runtime)
  # Refuse duplicated physical selections even when two inventory authorities
  # reference the same attempt. Distinct repetitions remain separate.
  unique(physical,lambda r:r["physical_id"],"Physical attempt repeated across explicit inventories")
  require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"New quiet lease")
  outputs={"runtime_rows":A.write_new(out/"RUNTIME_ROWS.json",runtime),"physical_rows":A.write_new(out/"PHYSICAL_ROWS.json",physical)}
  value=dict(schema="s6c-runtime-metadata-normalization.v1",status="COMPLETE_METADATA_NORMALIZATION",created_utc=datetime.now(timezone.utc).isoformat(),spec=sb,
   requested_input_ids=[r["input_id"] for r in spec["requests"]+spec.get("physical_inventories",[])],outputs=outputs,
   runtime_rows=len(runtime),unresolved_runtime_rows=sum(r["status"]!="COMPLETE" for r in runtime),physical_rows=len(physical),
   source_bindings=sources()+reg_sources+[sb,spec["observer_index"]],metadata_sources=reader.sources,
   whole_study_complete=False,model_calls=0,scoring_runs=0,raw_log_audio_model_reads=0,
   tail_complete_meaning="Only admitted full-source journal/sample/cursor completion. Dispatch/drain proofs are separate; B00 has no research dispatch proof. No first/last-word correctness or acoustic clipping claim.",
   scope="Finite source-bound metadata join only. Root owns scientific disposition and operating selection. Unavailable proof remains unresolved.")
  return A.write_new(out/"RESULT.json",value)
 except Exception as exc:
  A.write_new(out/"FAILURE.json",dict(status="FAILED_PRESERVED",spec=sb,error=repr(exc),metadata_sources=reader.sources));raise

def checks():
 done=[]
 def ok(n,v=True):require(v,n);done.append(n)
 def bad(n,f):
  try:f()
  except (ValueError,KeyError,TypeError):ok(n);return
  raise AssertionError(n)
 bad("duplicate JSON key",lambda:parse(b'{"a":1,"a":2}'))
 bad("nonfinite JSON",lambda:parse(b'{"a":NaN}'))
 ok("unknown owner remains null",owners_closed([dict(pid=1,creation_time=1.,process_state=dict(alive=None))]) is None)
 ok("live owner remains false",owners_closed([dict(pid=1,creation_time=1.,process_state=dict(alive=True))]) is False)
 ok("empty owner not closed",owners_closed([]) is None)
 ok("boolean creation not closed",owners_closed([dict(pid=1,creation_time=True,process_state=dict(alive=False))]) is None)
 owner=[dict(pid=1,creation_time=1.,process_state=dict(alive=False))]
 ok("finite closed owner",owners_closed(owner) is True)
 bad("numeric closure rejected",lambda:owners_closed([dict(pid=1,creation_time=1.,process_state=dict(alive=0))]))
 original={"B00":dict(candidate_id="B00"),"B36":dict(candidate_id="B36")}
 job=dict(profile_id="B00",stream="O0",recipe_id="R0",profile=None,duration_sec=1.,input_pcm_sha256="pcm")
 cond=historical_condition(job,original,"baseline")
 bad("B00 not research",lambda:historical_condition(job,original,"research"))
 n=dict(status="COMPLETE",native_pcm_exact=True,asr_cursor_complete=True,source_duration_sec=1.,journal=dict(sha256="pcm",bytes=32000),
  summary=dict(telemetry=dict(asr_cursor_sec=1.,audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0)))
 tail=historical_tail(n,job);ok("B00 limited full-source proof",tail["tail_complete"] is True and tail["dispatch_tail_proof"] is None and tail["drain_available"] is False)
 badjob=dict(job,profile_id="B36");ok("B36 missing research proof unresolved",historical_tail(n,badjob)["tail_complete"] is None)
 n["journal"]["bytes"]=31998;ok("truncated B00 journal unresolved",historical_tail(n,job)["tail_complete"] is None)
 source=dict(duration_sec=1.,duration_samples=16000);native=dict(status="COMPLETE",source_duration_sec=1.,final_telemetry=dict(source_duration_sec=1.,asr_cursor_sec=1.,scheduler=dict(closed=True,pending_events=0),audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0))
 final=dict(source_samples=16000,identity_samples=16000,state="COMPLETED",finalization_error=None,event_and_transcript_handles_closed=True,resident_bundle_lease_retained=False,live_lanes_at_finalization=[])
 ok("paired full-source proof",c_tail(native,final,source)["tail_complete"] is True)
 ok("missing finalization error evidence unresolved",c_tail(native,{k:v for k,v in final.items() if k!="finalization_error"},source)["tail_complete"] is None)
 for key,value in (("source_samples",15999),("identity_samples",15999),("resident_bundle_lease_retained",True),("event_and_transcript_handles_closed",False)):
  ok("unresolved "+key,c_tail(native,dict(final,**{key:value}),source)["tail_complete"] is None)
 row=runtime_row("x","historical","B00",cond,dict(sha256="native"),1.,owner,tail,[],case="S45_01_01",repetition=1)
 ok("accepted limited historical row",row["status"]=="COMPLETE" and row["continuous"] is False)
 ok("source preparation not completion",runtime_row("x","long_c","C065",{},dict(sha256="native"),1827.,[],dict(tail_complete=None),[])["status"]=="PENDING_OR_UNVERIFIED")
 ok("repeat not invented",row["repetition"]==1)
 bad("duplicate physical identity",lambda:unique([dict(physical_id="same")]*2,lambda r:r["physical_id"],"duplicate"))
 c=dict(candidate_id="C065",asr_tap="O0",identity_tap="O0",recipe_id="N01",cue_condition="CUES_OFF",gallery_condition="NONE",enrollment_tier=None,profile=dict(profile_id="x",tracker={}))
 ref=dict(c,profile_sha256=digest(c["profile"]),executable_condition_sha256=condition_key(c),row_sha256=digest(c));registered={("C065","O0","O0"):ref}
 ok("condition from exact registered row",c_condition(c,registered)["executable_condition_sha256"]==condition_key(c))
 bad("wrong gallery rejected",lambda:c_condition(dict(c,gallery_condition="FIXED_ROTATION_A"),registered))
 bad("wrong executable profile rejected",lambda:c_condition(dict(c,profile=dict(profile_id="x",tracker={"x":1})),registered))
 class FixtureReader:
  def __init__(self,data):self.data=data
  def read(self,path,expected=None):return self.data[str(path)],expected
 ib=dict(path="fixture_inventory.json",bytes=1,sha256="i");pb=dict(path="fixture_physical.json",bytes=1,sha256="p")
 actual=dict(physical_id="attempt1",candidate_id="C065",pid=1,creation_time=1.,status="FAILED_OUTER_NATIVE_COMPLETE_PROTECTION_UNVERIFIED",native_session_complete=True,session_dir="session",closed_cell_analysis_eligible=False)
 inv=dict(schema="s6c-execution-inventory.v1",adapter_schema="s6c-execution-inventory-additive.v7",status="WHOLE_STUDY_COUNTING_WITH_EXPLICIT_PRIOR_AND_FAST_APPEND",outputs=dict(physical_json=pb),unique_physical_attempts_observed=1,owner_identity_summary=owner)
 fixture=FixtureReader({ib["path"]:inv,pb["path"]:[actual]});item=dict(input_id="failed_v1",inventory=ib,physical_ids=["attempt1"])
 result=physical_rows(fixture,item)[0]
 ok("actual failed physical row remains failed",result["status"]==actual["status"] and result["native_session_complete"] is True and result["closed_cell_analysis_eligible"] is False and result["alive"] is False)
 inv["owner_identity_summary"]=[];ok("missing current inventory closure stays null",physical_rows(fixture,item)[0]["alive"] is None)
 bad("duplicate physical selection rejected",lambda:physical_rows(fixture,dict(item,physical_ids=["attempt1","attempt1"])))
 request=dict(input_id="one",kind="canonical",manifest={},paced_index={},analysis_receipt={});ok("exact canonical request",validate_request(request)==request)
 bad("irrelevant generation rejected",lambda:validate_request(dict(request,generation="baseline")))
 bad("missing historical generation",lambda:validate_request(dict(input_id="x",kind="historical",manifest={},analysis_receipt={})))
 r1=dict(native_result=dict(path="runA/RESULT.json",sha256="a"),native_session_dir="sessionA",repetition=1)
 r2=dict(native_result=dict(path="runB/RESULT.json",sha256="b"),native_session_dir="sessionB",repetition=2)
 ok("distinct physical repetitions retained",require_distinct_runtime_sessions([r1,r2])==[r1,r2])
 bad("overlapping continuous admission requests rejected",lambda:require_distinct_runtime_sessions([r1,r1,r2]))
 bad("aliased native result bytes rejected",lambda:require_distinct_runtime_sessions([r1,dict(r2,native_result=dict(path="copy/RESULT.json",sha256="a"))]))
 bad("same actual session under distinct result rejected",lambda:require_distinct_runtime_sessions([r1,dict(r2,native_session_dir="sessionA")]))
 ok("C native session from actual journals",native_session(dict(native_journals={"a":dict(path="sessionA/audio_spool.pcm16"),"b":dict(path="sessionA/identity_audio_spool.pcm16")}))==str(Path("sessionA").resolve()))
 return dict(schema="s6c-runtime-normalizer-source-checks.v1",status="PASS_PURE_METADATA_CHECKS",checks=len(done),names=done,sources=sources(),actual_normalization_run=False,new_models=0,raw_payload_reads=0)

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);sub=p.add_subparsers(dest="action",required=True);sub.add_parser("checks")
 a=sub.add_parser("run");a.add_argument("--spec",required=True,type=Path);a.add_argument("--spec-sha256",required=True);a.add_argument("--namespace",required=True)
 args=p.parse_args();print(json.dumps(checks() if args.action=="checks" else run(args),indent=2,allow_nan=False))
if __name__=="__main__":main()

