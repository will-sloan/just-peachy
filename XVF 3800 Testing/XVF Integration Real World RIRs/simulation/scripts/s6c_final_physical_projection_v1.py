"""Compact exact final census metadata; see README_S6C_FINAL_PHYSICAL_PROJECTION_V1.md."""
from __future__ import annotations
import argparse,hashlib,json,math
from collections import Counter
from pathlib import Path
SIM=Path(__file__).resolve().parents[1];REPORT=SIM/"reports/S6C/20260910T123540Z"
INVENTORY=REPORT/"execution_inventory/final_whole_study_v1_fast/EXECUTION_INVENTORY.json"
INVENTORY_SHA="eb22fabc22733599bcdf7303bf2d9cbb5fa7464629e18c5bbfae558716f43fb9"
PHYSICAL_SHA="0368a24785e15576e4fa1312e0c9ebe8b9574329ddb992ad462852f141452c71"
PHYSICAL_BYTES=51344039
FIELDS=("physical_id","candidate_id","branch","status","epoch","profile_id","recipe_id","case_id","asr_tap","identity_tap","repetition","execution_mode","job_key","inference_dependency_key","pid","creation_time","session_dir","session_evidence","started_utc","finished_utc","elapsed_sec","native_elapsed_sec","process_cpu_sec","audio_duration_sec","rss_end_bytes","worker_model_bundle_loads","bundle_admission_sec","gallery_cache_hit","gallery_admission_sec","real_gallery_load_observed","declared_output_bytes","bindings_missing_byte_counts","hardware_invocations","oracle_like","cue_condition","gallery_condition","enrollment_tier","profile_sha256","native_session_complete","source_kind","source_composition_epoch","protected_functions_restored","closed_cell_analysis_eligible")
NESTED=("actual_counts","receipt_bindings","source_asr","source_identity","telemetry","gallery_manifest","epoch_manifest","historical_asset_epoch","historical_native_driver","historical_baseline_authority","worker_status_binding","source_composition","source","continuous_result","trajectory_counts","observer_stats")
FIELDS=FIELDS+("error",)
def require(ok,msg):
 if not ok:raise ValueError(msg)
def parse(raw):
 def pairs(xs):
  d={}
  for k,v in xs:require(k not in d,"Duplicate JSON key");d[k]=v
  return d
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
def encode(v):return (json.dumps(v,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n").encode()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode()).hexdigest()
def bind(p,raw):return dict(path=str(Path(p).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(p,expected=None,cap=32*1024**2):
 p=Path(p).resolve();require(p.stat().st_size<=cap,"Finite declared metadata cap");raw=p.read_bytes();b=bind(p,raw)
 if expected:require(all(b[k]==expected[k] for k in ("path","bytes","sha256")),"Exact same-buffer binding")
 return parse(raw),b
def project(x,n):
 require(isinstance(x,dict) and x.get("physical_id"),"Actual physical record")
 out={k:x.get(k) for k in FIELDS};out.update({k:x.get(k) for k in NESTED})
 ps=x.get("process_state")
 require(isinstance(ps,dict),"Original process state")
 out.update(classification=x["status"],alive=ps.get("alive"),process_state=ps,source_row_pointer="/"+str(n),source_row_sha256=digest(x),missing_original_fields=[k for k in FIELDS+NESTED if k not in x])
 require(out["pid"] is None or isinstance(out["pid"],int) and not isinstance(out["pid"],bool) and out["pid"]>0,"PID type")
 require(out["creation_time"] is None or isinstance(out["creation_time"],(int,float)) and not isinstance(out["creation_time"],bool) and math.isfinite(out["creation_time"]) and out["creation_time"]>0,"Creation type")
 require(out["alive"] is None or type(out["alive"]) is bool,"Closure missingness")
 return out
def checks():
 base=dict(physical_id="id",candidate_id="C065",status="STARTED",pid=2,creation_time=1.5,process_state=dict(alive=False))
 a=project(base,0);require(a["status"]=="STARTED" and a["native_session_complete"] is None and "native_session_complete" in a["missing_original_fields"],"Started and missing native preserved")
 b=dict(base,native_session_complete=False);require(project(b,1)["native_session_complete"] is False and "native_session_complete" not in project(b,1)["missing_original_fields"],"False distinct from missing")
 c=dict(base,process_state=dict(alive=None));require(project(c,2)["alive"] is None,"Unknown not closed")
 c=dict(base,status="FAILED_OUTER_NATIVE_COMPLETE_PROTECTION_UNVERIFIED",native_session_complete=True);require(project(c,3)["status"].startswith("FAILED") and project(c,3)["native_session_complete"] is True,"Failed outer with native retained")
 e=dict(base,error="Original guard error");require(project(e,4)["error"]=="Original guard error","Exact error retained")
 n=5
 for key,value in (("pid",True),("creation_time",float("nan")),("process_state",dict(alive=0))):
  bad=dict(base);bad[key]=value
  try:project(bad,0)
  except (ValueError,TypeError):n+=1
  else:raise AssertionError("Malformed owner accepted")
 return dict(status="PASS",check_count=n)
def run(output):
 inv,ib=load(INVENTORY);require(ib["sha256"]==INVENTORY_SHA,"Pinned final census")
 pb=inv["outputs"]["physical_json"];require(pb["sha256"]==PHYSICAL_SHA and pb["bytes"]==PHYSICAL_BYTES,"Pinned large input only")
 # Only this one explicitly pinned original metadata input may exceed32MiB.
 original,pb=load(pb["path"],pb,cap=PHYSICAL_BYTES)
 require(len(original)==inv["unique_physical_attempts_observed"]==5891,"All observed attempts")
 rows=[project(x,n) for n,x in enumerate(original)];require(len({x["physical_id"] for x in rows})==len(rows),"No physical duplication")
 counts=dict(Counter(x["status"] for x in rows));require(counts==inv["summary"]["status_counts"],"Exact upstream status totals")
 require(all(x["alive"] is False and x["pid"] is not None and x["creation_time"] is not None for x in rows),"All concrete attempt identities closed")
 require(not any(x["candidate_id"] in ("C083","C084") for x in rows),"Aliases not assigned physical observations")
 owners=[]
 for n,x in enumerate(inv["owner_identity_summary"]):
  owners.append(dict(owner_observation_index=n,branch=x.get("branch"),pid=x.get("pid"),creation_time=x.get("creation_time"),alive=x.get("process_state",{}).get("alive"),process_state=x.get("process_state"),source=x.get("source"),original_row_sha256=digest(x)))
 require(len(owners)==7412 and sum(x["alive"] is False for x in owners)==7411 and sum(x["alive"] is None for x in owners)==1,"All owner observations including virtual unknown")
 flags=dict(process_closure=inv["process_closure"],unavailable_owner_observations=[x for x in owners if x["alive"] is not False],physical_noncomplete_rows=[x for x in rows if x["status"]!="COMPLETE"],prior_process_closure=inv["prior_process_closure"],scope="A virtual missing observer exit is not a new physical attempt. Original STARTED and failed outer rows remain unavailable as scientific success, while their concrete owner identities are closed.")
 modelbindings={}
 for x in rows:
  for k in ("epoch_manifest","historical_asset_epoch","historical_native_driver","historical_baseline_authority"):
   b=x.get(k)
   if isinstance(b,dict) and set(("path","bytes","sha256"))<=set(b):modelbindings[(b["path"],b["sha256"])]=b
 out=Path(output).resolve();require(out.parent==REPORT/"execution_inventory" and not out.exists(),"Fresh finite output namespace");out.mkdir()
 def write(name,v):
  raw=encode(v);require(len(raw)<=32*1024**2,"Compact output stays within held assembler cap");p=out/name
  with p.open("xb") as f:f.write(raw)
  return bind(p,raw)
 physical=write("PHYSICAL_ROWS.json",rows)
 own=write("OWNER_OBSERVATIONS.json",owners)
 flagged=write("UNAVAILABLE_AND_FAILURES.json",flags)
 # This compact index points to exact original declaration rows; it does not
 # reopen their audio, weights, outputs or session directories.
 model=write("MODEL_AND_CACHE_RECEIPTS.json",dict(status="COMPLETE_METADATA_RECEIPT_INDEX",inventory=ib,original_physical_rows=pb,physical_projection=physical,model_asset_source_authorities=list(modelbindings.values()),original_source_bindings=inv["source_bindings"],original_receipt_locations="PHYSICAL_ROWS.receipt_bindings and source_row_pointer into exact original physical JSON",summary=inv["summary"],native_index_reference_coverage=inv["prior_native_index_reference_coverage"],index_reference_accounting=inv["prior_index_reference_accounting"],scope="Exact declared model/epoch/input/gallery/cache/event-count metadata and source receipts only. Index references/reuse are not new physical attempts; no raw payload verification or fresh model load is inferred.",whole_study_complete=False))
 coverage_fields=list(FIELDS)+["classification","alive","source_row_pointer","source_row_sha256","missing_original_fields_json","process_state_json","actual_counts_json","receipt_bindings_json","source_asr_json","source_identity_json","telemetry_json","gallery_manifest_json","epoch_manifest_json","historical_asset_epoch_json","historical_native_driver_json","historical_baseline_authority_json"]
 matrix=[coverage_fields]
 for x in rows:
  vals=[]
  for k in coverage_fields:
   v=x.get(k[:-5]) if k.endswith("_json") else x.get(k)
   vals.append(json.dumps(v,ensure_ascii=False,allow_nan=False,separators=(",",":")) if k.endswith("_json") else v)
  matrix.append(vals)
 csvinput=write("EXECUTION_COVERAGE_MATRIX.json",dict(columns=coverage_fields,values=matrix,source=physical,rows=5891,scope="One row per observed physical attempt. Null scalar values remain blank in CSV and are disambiguated by missing_original_fields_json. JSON projection is typed authority."))
 result=write("RESULT.json",dict(schema="s6c.final_physical_projection.v1",status="COMPLETE_PHYSICAL_METADATA_PROJECTION_WITH_FLAGS",inventory=ib,original_physical_rows=pb,outputs=dict(physical_rows=physical,owner_observations=own,failures=flagged,model_and_cache_receipts=model,csv_matrix=csvinput),row_count=len(rows),status_counts=counts,complete_native_sessions_observed=inv["complete_native_sessions_observed"],actual_physical_candidate_count=len({x["candidate_id"] for x in rows}),owner_count=len(owners),concrete_closed_owner_observations=7411,virtual_unavailable_owner_observations=1,upstream_audit_status=inv["audit_status"],upstream_process_closure=inv["process_closure"]["status"],tests=checks(),source=bind(__file__,Path(__file__).read_bytes()),readme=bind(Path(__file__).with_name("README_S6C_FINAL_PHYSICAL_PROJECTION_V1.md"),Path(__file__).with_name("README_S6C_FINAL_PHYSICAL_PROJECTION_V1.md").read_bytes()),whole_study_complete=False,new_native_or_score_calls=0,scope="Exact all-row compact projection, not a second census or payload scan. Held assembler32MiB cap unchanged; sole large source is exact51,344,039-byte pinned original metadata. Unknown and failed states are preserved."))
 print(json.dumps(result))
if __name__=="__main__":
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);run(p.parse_args().output)
