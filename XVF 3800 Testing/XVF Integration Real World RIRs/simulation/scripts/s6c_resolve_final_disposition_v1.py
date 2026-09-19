"""Resolve final decisions with actual evidence. README_S6C_RESOLVE_FINAL_DISPOSITION_V1.md."""
from __future__ import annotations
import argparse,copy,hashlib,importlib,json
from pathlib import Path
SIM=Path(__file__).resolve().parents[1];REPORT=SIM/"reports/S6C/20260910T123540Z"
PIN="ead12d3fce56177914511cd8af983e7764af5c497d3f154789ea01e2c114696e"
require=lambda x,m:None if x else (_ for _ in ()).throw(ValueError(m))
require(hashlib.sha256((SIM/"scripts/s6c_final_disposition_v1.py").read_bytes()).hexdigest()==PIN,"Held assembler source")
F=importlib.import_module("s6c_final_disposition_v1");require(Path(F.__file__).resolve()==SIM/"scripts/s6c_final_disposition_v1.py","Exact import")
WORKING="01b2db948ef9391331e8610552190c531dbff5a628ca23ad68c8182820f14bfd"
PHYSICAL="db85900c955f1d0cf4634f7a4a41d68e7fd999f4225bc5f13715c6b8eeb21ccd"
OPERATING={"B36":("b36_o0_historical_none_fallback","RETAINED_FALLBACK","Balanced historical whole-pipeline fallback for desktop saved-file research; not an isolated tracker control or live/CM5 qualification."),
"C067":("c067_o0_conditional_latest_anonymous","RETAINED_OPERATING_PRESET","Conditional latest-attribution anonymous research option. Latest gains carry worse first-display/return/Unknown tradeoffs; no universal improvement."),
"C088":("c088_o0_original_a15_controlled_naming","RETAINED_OPERATING_PRESET","Original fixedA15 controlled naming research condition. Material source-attributed lag and false-known/stranger exposure limit use; gallery assumptions remain explicit."),
"C091":("c091_o0_original_b15_controlled_naming","RETAINED_OPERATING_PRESET","Original fixedB15 controlled naming research condition. Material source-attributed lag and false-known/stranger exposure limit use; this is not the common14 roster.")}
REPRESENTATIVES={"C067","C076","C088","C091","C122"}
LEDGERS=("c065_c067_actual_v1","c088_c091_actual_v1","controls_recovered_actual_v1","remaining116_actual_v1","six_closed_candidates_actual_v1")
NAME_PARENTS={"n01_gallery_panel_names_v2":"n01_gallery_panel_core_v2","gallery_native_names_v3":"gallery_native_core_v3","common_duration_panel_names_v3":"common_duration_panel_core_v3","common_duration_native_names_v3":"common_duration_native_core_v3","full_n01_naming_names_v3":"full_n01_naming_core_v3","full_n01_common_duration_names_v3":"full_n01_common_duration_core_v3"}
def write(out,name,d):
 p=out/name;raw=F.json_bytes(d)
 with p.open("xb") as f:f.write(raw)
 return F.binding(p)
def tests():
 require(set(OPERATING)=={"B36","C067","C088","C091"} and "C065" not in OPERATING,"Four exact selections and control")
 require(len(REPRESENTATIVES)==5 and {"C083","C084"}.isdisjoint(REPRESENTATIVES),"Five main reps, no aliases")
 require(len(LEDGERS)==5 and len(set(LEDGERS))==5,"Finite unique score ledger set")
 return dict(status="PASS",checks=3)
def prepare(output):
 out=Path(output).resolve();require(out.parent==REPORT/"candidate_disposition" and not out.exists(),"Fresh final input namespace")
 reader=F.Reader();b=F.binding(REPORT/"candidate_disposition/final_inputs_working_v1/FINAL_INPUTS_UNRESOLVED.json");require(b["sha256"]==WORKING,"Held unresolved assembly")
 spec=reader.doc(b);plan,work,fields,original_rows,original_raw,routes=F.validate_working(reader,spec)
 working={x["candidate_id"]:x for x in original_rows}
 pb=F.binding(REPORT/"execution_inventory/final_physical_projection_v1/RESULT.json");require(pb["sha256"]==PHYSICAL,"Reviewed exact physical projection")
 proj=reader.doc(pb);physical=reader.doc(proj["outputs"]["physical_rows"])
 require(proj["row_count"]==5891 and proj["virtual_unavailable_owner_observations"]==1,"All census scopes")
 resources=spec["resources"];by_path={x["binding"]["path"]:x["resource_id"] for x in resources}
 def add_resource(b,rid,parent=None,status=None):
  if b["path"] in by_path:return by_path[b["path"]]
  x=dict(resource_id=rid,binding=b,format="csv" if b["path"].endswith(".csv") else "json")
  if parent:x["parent"]=parent
  else:require(status,"Root actual status");x["assertions"]={"/status":status}
  resources.append(x);by_path[b["path"]]=rid;return rid
 def add(e):require(e["candidate_id"] not in {"C083","C084"} or e["kind"]=="interpretation","Alias execution propagation");spec["evidence"].append(e)
 def condition(pid,a,i):
  if pid.startswith("C"):return {k:routes[(pid,a,i)][k] for k in ("asr_tap","identity_tap","recipe_id","cue_condition","gallery_condition","enrollment_tier","profile_sha256","executable_condition_sha256")}
  return dict(asr_tap=a,identity_tap=i,original_registration_row_sha256=working[pid]["original_registration_row_sha256"],gallery_condition="NONE",enrollment_tier=None)
 def scoring(receipt,repeat,scope,parent_core=None):
  d=reader.doc(receipt);isname=d["status"]=="COMPLETE_REQUESTED_NAME_INDEX"
  require(d["status"] in ("COMPLETE_REQUESTED_INDEX","COMPLETE_REQUESTED_NAME_INDEX"),"Completed actual score receipt")
  require(d.get("unscored",d.get("failed_or_missing"))==0,"No unscored output")
  if isname:
   require(parent_core is not None and d["index"]==parent_core["index"],"Exact core/name index equality")
   rs=parent_core["profile_routes"]
  else:rs=d["profile_routes"]
  rid=add_resource(receipt,"final_score_"+str(len(resources)),status=d["status"])
  cv=next(x for x in d["tables"] if Path(x["path"]).name=="COVERAGE.csv");cr=add_resource(cv,rid+"_coverage",rid)
  for x in rs:
   pid=x["candidate_id"];a=x["stream"];i=x["identity_tap"];eid=f"finalscore_{len(spec['evidence']):04}_{pid}_{a}_{i}"
   add(dict(evidence_id=eid,kind="score",candidate_id=pid,authority_id=rid,scope_label=scope+("; modeled source-support name scoring" if isname else "; core scoring"),repetition=repeat,status="AVAILABLE",condition=condition(pid,a,i),completion_checks=[dict(resource_id=rid,equals={"/status":d["status"]})],records=dict(resource_id=cr,pointer="",where={"/profile_id":pid,"/stream":a,"/identity_tap":i},columns=dict(candidate_id="/profile_id",asr_tap="/stream",identity_tap="/identity_tap",case_id="/case_id",status="/status"))))
  return d
 ledger_bindings=[];score_counts={"core":0,"name":0};receipt_seen=set()
 for label in LEDGERS:
  lb=F.binding(REPORT/"paced_scoring"/label/"EXECUTION_RESULT.json");ld=reader.doc(lb);ledger_bindings.append(lb);cores={}
  for run in ld["runs"]:
   require(run["returncode"]==0 and run["receipt"]["sha256"] not in receipt_seen,"One completed score invocation");receipt_seen.add(run["receipt"]["sha256"])
   d=reader.doc(run["receipt"])
   if run["kind"]=="core":cores[d["index"]["sha256"]]=d
   scored=scoring(run["receipt"],run["repetition"],"ACTUAL_PACED_SEPARATE_REPETITION "+label,cores.get(d["index"]["sha256"]))
   score_counts[run["kind"]]+=scored["scored"]
 require(score_counts=={"core":596,"name":596},"All596 core and modeled-name rows")
 full_name_bindings=[]
 for names,core in NAME_PARENTS.items():
  nb=F.binding(REPORT/names/"NAME_ANALYSIS_RECEIPT.json");cb=F.binding(REPORT/core/"ANALYSIS_RECEIPT.json")
  cd=reader.doc(cb);scoring(nb,0,"OFFLINE_OR_NATIVE_INTEGRATION_NAMES "+names,cd);full_name_bindings.append(nb)
 prid=add_resource(pb,"final_physical_projection",status=proj["status"]);pr=add_resource(proj["outputs"]["physical_rows"],"final_physical_rows",prid)
 for pid in sorted({x["candidate_id"] for x in physical}):
  require(pid in F.IDS,"Exact candidate physical mapping")
  eid="physical_"+pid
  add(dict(evidence_id=eid,kind="physical",candidate_id=pid,authority_id=prid,scope_label="ALL_OBSERVED_ATTEMPTS_IN_FINAL_CENSUS",repetition="PHYSICAL_ATTEMPT_IDS",status="AVAILABLE",completion_checks=[dict(resource_id=prid,equals={"/status":proj["status"]})],records=dict(resource_id=pr,pointer="",where={"/candidate_id":pid},columns={k:"/"+k for k in ("candidate_id","physical_id","pid","creation_time","alive","classification","branch","status","asr_tap","identity_tap","source_row_pointer","source_row_sha256")})))
 out.mkdir()
 operating=[]
 for p in spec["prospective_operating_dependencies"]:
  pid=p["candidate_id"];key,status,reason=OPERATING[pid]
  operating.append(dict(preset_id=key,candidate_id=pid,condition=p["condition"],status=status,reason=reason,paced_evidence_id=p["paced_evidence_id"],long_evidence_id=p["long_evidence_id"]))
 decisions=spec["candidate_decisions"]
 for d in decisions:
  pid=d["candidate_id"];d["resolved"]=True
  if pid in REPRESENTATIVES:d["scientific_disposition"]="REPRESENTATIVE_EVALUATED"
  d["limitations"]=[x.replace("Final census physical records and root acceptance/selection are unresolved in this input preparation.","Final census retains one STARTED/no-session attempt, one failed outer/native-complete attempt and one virtual missing-observer closure flag; concrete recorded owners were closed.") for x in d["limitations"]]
  d["limitations"]=[x.replace("actual paced and continuous operating applicability remains unresolved here.","actual paced/continuous evidence is listed in its separate exact scope; operating use is restricted to the root-selected research bundles.") for x in d["limitations"]]
  d["interpretation"]=d["interpretation"].replace("Root may resolve final representative and operating decisions after census and combined review.","Root selections are separately bound.")
  d["limitations"].append("Completed saved-file runtime is not product latency/accuracy, live low-latency, default, hardware or CM5 qualification. C088/C091 have material lag/false-known risk; long observer gaps51-63s limit peak interpretation.")
  if pid in OPERATING:d["interpretation"]+=" Root retains the exact O0 research condition with the operating limitations listed separately."
  if pid=="C065":d["interpretation"]+=" C065 remains the empty-gallery/control condition and is not an operating fallback."
  if pid in REPRESENTATIVES:d["interpretation"]+=" The predeclared representative completed its main16-case/tap plus4 repeated-case/tap paced scope."
  d["evidence_ids"]=[e["evidence_id"] for e in spec["evidence"] if e["candidate_id"]==pid]+["interpretation_"+pid]
 decision_authority=dict(schema="s6c.root_disposition_decision.v1",status="COMPLETE_ROOT_DISPOSITION_DECISION",authority_origin="Root agent explicit instruction after census writer window closed, 2026-09-12. Exact four selections and permitted original proposal classifications are recorded here without new model or metric work.",source_input=b,physical_projection=pb,scientific_representatives=sorted(REPRESENTATIVES),operating_presets=operating,control_candidate="C065",candidate_decisions=decisions,whole_study_complete=False,scope="Final candidate/evidence and research-condition decisions only. Final produced-artifact/independent acceptance follows separately; no per-scene tap selection or live/CM5/default endorsement.")
 db=write(out,"ROOT_DECISION_AUTHORITY.json",decision_authority);dr=add_resource(db,"root_decision_authority",status=decision_authority["status"])
 for d in decisions:
  eid="interpretation_"+d["candidate_id"]
  add(dict(evidence_id=eid,kind="interpretation",candidate_id=d["candidate_id"],authority_id=dr,scope_label="ROOT_RESOLVED_SCIENTIFIC_SCOPE_AND_LIMITATIONS",repetition="DECISION_AUTHORITY",status="AVAILABLE",completion_checks=[dict(resource_id=dr,equals={"/status":decision_authority["status"]})],text=d["interpretation"],limitations=d["limitations"]))
  d["evidence_ids"]=[e["evidence_id"] for e in spec["evidence"] if e["candidate_id"]==d["candidate_id"]]
 reqb=F.binding(REPORT/"candidate_disposition/final_inputs_working_v1/REQUIREMENT_RESOLUTION_INPUTS.json");req=reader.doc(reqb)
 for row in req["requirements"]:
  rid=row["requirement_id"];row["accounting_resolved"]=True;row["resolved"]=False
  if rid=="R24":
   row["terminal_accounting_status"]="OPTIONAL_NOT_EXECUTED";row["actual_satisfaction"]="OPTIONAL_BRANCH_EXPLICITLY_NOT_EXECUTED";row["update"]="No new device/HIL branch; XVF was disconnected. Saved-file offline work was independent of device connection."
  elif rid.startswith("D"):
   row["terminal_accounting_status"]="SUBSEQUENT_PRODUCED_ARTIFACT_BINDING_REQUIRED";row["actual_satisfaction"]="NOT_CERTIFIED_BY_THIS_PRE_ASSEMBLY_LEDGER";row["update"]="Root handoff/export/package work supplies the actual artifact hash and independent acceptance later. No future file or package receipt is fabricated."
  elif rid in ("R30","R31"):
   row["terminal_accounting_status"]="SUBSEQUENT_FINAL_BOUNDARY_AUTHORITY_REQUIRED";row["actual_satisfaction"]="EXISTING_SCOPED_EVIDENCE_RETAINED_FINAL_BOUNDARY_PENDING"
   row["update"]=("Fresh census and concrete owner closure are bound with the original virtual missing-observer flag. Root must bind final current-resource/cap and owner certification separately; no atomic snapshot or CM5 claim." if rid=="R30" else "Prior independent source/numeric/runtime/physical-projection reviews remain bound to their exact scopes. Final combined produced-artifact review and whole-study acceptance remain pending.")
  else:
   row["terminal_accounting_status"]="SCOPED_SCIENTIFIC_EVIDENCE_ACCOUNTED";row["actual_satisfaction"]="ROOT_RESOLVED_IN_DECLARED_EVIDENCE_SCOPE";row["resolved"]=True
   if rid=="R04":row["update"]="Fresh final census and compact projection complete with explicit historical/observer flags; final machine export is bound separately."
   if rid=="R26":row["update"]="Five predeclared representatives C067/C076/C088/C091/C122 completed main balanced16+4 both-tap panels; matched/historical controls remain separate."
   if rid=="R28":row["update"]="All four retained exact O0 bundles have continuous1827.426625s saved-file diagnostics; C065's fifth long is a control."
  row["updated_state"]=row["terminal_accounting_status"]
 req.update(schema="s6c.requirement_resolution_accounting.v1",status="COMPLETE_REQUIREMENT_RESOLUTION_ACCOUNTING",original_input=reqb,root_decision=db,physical_projection=pb,paced_score_ledgers=ledger_bindings,offline_name_receipts=full_name_bindings,accounting_complete=True,all46_present=True,whole_study_complete=False,final_acceptance=False,required_subsequent_artifact_ids=[f"D{i:02}" for i in range(1,16)],scope="All46 exact original obligations are classified and linked to existing finite authorities. COMPLETE means resolution bookkeeping only. No generated candidate/file/package or independent acceptance is represented before actual production; all15 deliverable bindings are deferred, particularly D05/D13/D14/D15.")
 qb=write(out,"REQUIREMENT_RESOLUTION_ACCOUNTING.json",req);qr=add_resource(qb,"requirement_resolution_accounting",status=req["status"])
 spec.update(status="READY_FOR_FINAL_ASSEMBLY",operating_presets=operating,required_evidence_ids=[e["evidence_id"] for e in spec["evidence"]],requirement_resolution=dict(resolved=True,authority_id=qr,checks={"/status":req["status"],"/accounting_complete":True,"/all46_present":True,"/whole_study_complete":False}),unresolved_fields=[dict(field="Final produced-artifact/independent acceptance",owner="root",needed="Subsequent actual artifacts and acceptance receipt; whole_study_complete remains false.")],whole_study_complete=False)
 spec["root_decision_authority"]=db
 fb=write(out,"FINAL_INPUTS.json",spec)
 receipt=write(out,"PREPARATION_RECEIPT.json",dict(status="COMPLETE_RESOLVED_ASSEMBLY_INPUT_PREPARATION",source=F.binding(Path(__file__)),readme=F.binding(Path(__file__).with_name("README_S6C_RESOLVE_FINAL_DISPOSITION_V1.md")),original_unresolved=b,physical_projection=pb,root_decision=db,requirement_accounting=qb,final_inputs=fb,paced_score_rows=score_counts,paced_score_ledgers=ledger_bindings,full_name_receipts=full_name_bindings,tests=tests(),whole_study_complete=False,scope="Root-authorized finite metadata assembly only. Original sources untouched. Held final assembler still must validate every exact metadata DAG and projection before publishing its result."))
 print(json.dumps(receipt))
if __name__=="__main__":
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);prepare(p.parse_args().output)
