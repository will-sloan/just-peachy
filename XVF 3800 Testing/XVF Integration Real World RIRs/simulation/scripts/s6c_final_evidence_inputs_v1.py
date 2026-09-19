"""Assemble finite evidence inputs, not acceptance. See README_S6C_FINAL_EVIDENCE_INPUTS_V1.md."""
from __future__ import annotations
import argparse,csv,hashlib,io,json
from collections import Counter,defaultdict
from pathlib import Path
SIM=Path(__file__).resolve().parents[1];REPORT=SIM/"reports/S6C/20260910T123540Z"
PIN_ASSEMBLER="ead12d3fce56177914511cd8af983e7764af5c497d3f154789ea01e2c114696e"
PINS={
"plan":("candidate_disposition/FINAL_DISPOSITION_ASSEMBLY_PLAN_V2.json","f6b19c7070a266a775b13fac4464557910e70680c9c5f9efa58c8df67dc8980f"),
"working":("candidate_disposition/working_v1/RECEIPT.json","5d84d493a377eb7b991e821cf59e412da5103ba7e17786e197bb2dd9c1ecc8dd"),
"provisional":("candidate_disposition/provisional_decisions_v1/CANDIDATE_DECISIONS_PROVISIONAL.json","1fe467a80981b9c7684f7282e312f46a888ad7a17c1e60a6eea4ddaf22e889bf"),
"timing":("paced_compact_timing/full596_v1/RESULT.json","758bc7d437e7eacfca95ea56524d3c9236e86c7a38e526be436f8978ad87d9b2"),
"timing_inputs":("paced_compact_timing/inputs/FULL596_INPUTS_V1.json","2d2fdaad3d8c1ddb5c5a6e1fad154ba2d9d186301f53b921f59b78164119c8e1"),
"long_normalization":("runtime_normalization/five_long_closed_metadata_v1/RESULT.json","6c20c932bac2b01a55ad7b894f5adbc0bd1da53484aad681c185a1aa1b0eda3c"),
"long_diagnostics":("fast_post_analysis/five_long_actual_v1/ACTUAL_EXECUTION_RESULT.json","f7b16109b06eb8eae59c4522f12a718d11da17e0d4924766b0d902292b0d429b"),
"long_compact":("fast_post_analysis/five_long_actual_v1/COMPACT_LONG_OBSERVATIONS_V1.json","fc59e34e8767353374af3b0f1266ff3faa7299aca90a13ec3af1869fdc7a6244")}
IDS={f"B{i:02}" for i in range(40)}|{"B18_C1","B20_C1","B24_FREQUENT","B24_SPARSE"}|{f"C{i:03}" for i in range(1,197)}
CASES={f"S45_{a:02}_{b:02}" for a in range(1,13) for b in range(1,21)}
FIELDS=("asr_tap","identity_tap","recipe_id","cue_condition","gallery_condition","enrollment_tier","profile_sha256","executable_condition_sha256")
def require(ok,msg):
 if not ok:raise ValueError(msg)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def pairs(v):
 d={}
 for k,x in v:require(k not in d,"Duplicate JSON key");d[k]=x
 return d
def parse(b):return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def encoded(d):return (json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode()
def bind(p,b):return dict(path=str(Path(p).resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
class Reader:
 def __init__(self):self.sources={};self.cache={}
 def read(self,p,b=None):
  p=Path(p).resolve();key=str(p)
  if key not in self.cache:
   require(p.stat().st_size<=32*1024**2,"Finite metadata only");raw=p.read_bytes();self.cache[key]=raw;self.sources[key]=bind(p,raw)
  actual=self.sources[key]
  if b:require(all(actual[k]==b[k] for k in ("path","bytes","sha256")),"Changed bound metadata "+key)
  return self.cache[key],actual
 def doc(self,p,b=None):
  raw,actual=self.read(p,b);return parse(raw),actual
def condition(pid,a,i,work,routes):
 if pid.startswith("C"):return {k:routes[(pid,a,i)][k] for k in FIELDS}
 return dict(asr_tap=a,identity_tap=i,original_registration_row_sha256=work[pid]["original_registration_row_sha256"],gallery_condition="NONE",enrollment_tier=None)
def tests():
 require(len(IDS)==240 and len(CASES)==240,"Exact populations")
 require("B18_C1" in IDS and "B43" not in IDS,"Actual historical IDs")
 for bad in ['{"a":1,"a":2}','{"x":NaN}']:
  try:parse(bad)
  except ValueError:pass
  else:raise AssertionError("Malformed JSON accepted")
 # Same-case union is never used to assert full coverage.
 require(set(list(sorted(CASES))[:120])!=CASES and set(list(sorted(CASES))[120:])!=CASES,"Separate panels not full")
 return dict(status="PASS",checks=5)
def run(output):
 reader=Reader();docs={};bindings={}
 for key,(rel,sha) in PINS.items():
  d,b=reader.doc(REPORT/rel);require(b["sha256"]==sha,"Pinned "+key);docs[key]=d;bindings[key]=b
 raw,ab=reader.read(SIM/"scripts/s6c_final_disposition_v1.py");require(ab["sha256"]==PIN_ASSEMBLER,"Held assembler unchanged")
 working=docs["working"];outbind={Path(x["path"]).name:x for x in working["outputs"]}
 raw,wb=reader.read(outbind["CANDIDATE_DISPOSITION_PROPOSAL.csv"]["path"],outbind["CANDIDATE_DISPOSITION_PROPOSAL.csv"])
 wr=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))));work={x["candidate_id"]:x for x in wr}
 require(len(wr)==len(work)==240 and set(work)==IDS,"Exact unchanged240")
 rb=outbind["REGISTERED_ROUTE_SETTINGS_PROVENANCE.json"];rd,_=reader.doc(rb["path"],rb);routes={(x["candidate_id"],x["asr_tap"],x["identity_tap"]):x for x in rd["routes"]}
 require(len(routes)==388,"Exact route settings")
 sb=outbind["SCORING_AND_NATIVE_AUTHORITIES.json"];old,_=reader.doc(sb["path"],sb)
 pp,_=reader.doc(REPORT/"candidate_disposition/PROVISIONAL_DECISIONS_SOURCE_PLAN_V1.json")
 require(pp==reader.doc(docs["provisional"]["source_plan"]["path"],docs["provisional"]["source_plan"])[0],"Exact provisional source plan")
 resources=[];by_path={};evidence=[];mapping={pid:dict(candidate_id=pid,working_row_sha256=digest(work[pid]),registered_routes=parse(work[pid]["registered_routes"]),score_scopes=[],native_scopes=[],paced_scopes=[],long_scopes=[],physical_evidence_status="PENDING_FINAL_CENSUS",physical_inference_count=None) for pid in sorted(IDS)}
 def resource(b,rid,parent=None,assertions=None,fmt="json",value=None):
  if b["path"] in by_path:return by_path[b["path"]]
  obj=dict(resource_id=rid,binding=b,format=fmt)
  if parent:obj["parent"]=parent
  else:require(assertions,"Root assertions required");obj["assertions"]=assertions
  resources.append(obj);by_path[b["path"]]=rid;return rid
 def root(b,rid,d):
  require(isinstance(d.get("status"),str),"Structured authority status")
  return resource(b,rid,assertions={"/status":d["status"]})
 def add(e):require(e["candidate_id"] not in {"C083","C084"} or e["kind"]=="interpretation","No alias execution");evidence.append(e)
 def complete(rid,d):return [dict(resource_id=rid,equals={"/status":d["status"]})]
 score=list(old["scoring_authorities"])
 for group in ("n08n10","n12","cross"):
  b=pp["sources"][group+"_core"];d,_=reader.doc(b["path"],b);require(d["status"]=="COMPLETE_REQUESTED_INDEX" and d["unscored"]==0,"Closed full core")
  cv=next(x for x in d["tables"] if Path(x["path"]).name=="COVERAGE.csv")
  for route in d["profile_routes"]:
   score.append(dict(candidate_id=route["candidate_id"],asr_tap=route["stream"],identity_tap=route["identity_tap"],source_id=group+"_full_closed",scope_label=group+"_full_closed; exact original full-bank authority",execution_scope="ACTUAL_NATIVE_THEN_SHARED_PARITY_SCORING",repetition=0,analysis_authority=b,coverage_binding=cv,route_rows=len(d["case_ids"]),status_counts={"SCORED":len(d["case_ids"])},scored_cases=d["case_ids"],full_bank_in_this_authority=set(d["case_ids"])==CASES))
 for x in score:
  pid,a,i=x["candidate_id"],x["asr_tap"],x["identity_tap"];require(pid in IDS and [a,i] in mapping[pid]["registered_routes"],"Registered score route")
  b=x["analysis_authority"];d,_=reader.doc(b["path"],b);require(d["status"]=="COMPLETE_REQUESTED_INDEX" and d["unscored"]==0,"Actual complete analysis")
  require(x["coverage_binding"] in d["tables"],"Original coverage byte binding")
  rid=root(b,"score_authority_"+str(len(resources)),d);cv=resource(x["coverage_binding"],rid+"_coverage",rid,fmt="csv")
  eid=f"score_{len(evidence):04}_{pid}_{a}_{i}";hist=pid.startswith("B")
  cols=dict(candidate_id="/profile_id",asr_tap="/stream",identity_tap="/stream" if hist else "/identity_tap",case_id="/case_id",status="/status")
  where={"/profile_id":pid,"/stream":a}
  if not hist:where["/identity_tap"]=i
  e=dict(evidence_id=eid,kind="score",candidate_id=pid,authority_id=rid,scope_label=x["scope_label"],repetition=x["repetition"],status="AVAILABLE",condition=condition(pid,a,i,work,routes),completion_checks=complete(rid,d),records=dict(resource_id=cv,pointer="",where=where,columns=cols))
  add(e);mapping[pid]["score_scopes"].append(dict(evidence_id=eid,authority=b,execution_scope=x["execution_scope"],asr_tap=a,identity_tap=i,repetition=x["repetition"],case_count=x["route_rows"],status_counts=x["status_counts"],full_bank_in_this_authority=set(x["scored_cases"])==CASES,coverage=x["coverage_binding"],case_membership_sha256=digest(sorted(x["scored_cases"]))))
 # Native source metadata remains a separate ledger; no score count creates an attempt.
 batches=[dict(x) for x in old["native_batches"]]
 for group in ("n08n10","n12","cross"):
  cb=pp["sources"][group+"_native"];cd,_=reader.doc(cb["path"],cb)
  require(cd["status"]=="PASS_COMPLETE_NATIVE_GRID_AND_OWNERS_CLOSED","Exact closed later native authority")
  batches.append(dict(batch=group+"_full_closed",closure_review=cb,native_results=cd["results"]))
 for batch in batches:
  b=batch["native_results"];d,_=reader.doc(b["path"],b)
  require(d["status"]=="COMPLETE" and len(d["rows"])==d["completed"],"Completed native result metadata")
  rid=root(b,"native_authority_"+str(len(resources)),d)
  groups=defaultdict(list)
  for x in d["rows"]:groups[(x["candidate_id"],x["asr_tap"],x["identity_tap"])].append(x)
  for (pid,a,i),rows in sorted(groups.items()):
   require(pid in IDS and len({x["case_id"] for x in rows})==len(rows),"Native unique canonical route")
   require(all(x["status"] in ("COMPLETE","COMPLETE_REUSED") for x in rows),"Native success status")
   eid=f"native_{len(evidence):04}_{pid}_{a}_{i}"
   add(dict(evidence_id=eid,kind="native",candidate_id=pid,authority_id=rid,scope_label=batch["batch"]+"; native source logical cells incl reuse",repetition=0,status="AVAILABLE",condition=condition(pid,a,i,work,routes),completion_checks=complete(rid,d),records=dict(resource_id=rid,pointer="/rows",where={"/candidate_id":pid,"/asr_tap":a,"/identity_tap":i},columns=dict(candidate_id="/candidate_id",asr_tap="/asr_tap",identity_tap="/identity_tap",case_id="/case_id",status="/status",job_key="/job_key",receipt_sha256="/receipt/sha256"))))
   mapping[pid]["native_scopes"].append(dict(evidence_id=eid,authority=b,closure_review=batch["closure_review"],batch=batch["batch"],asr_tap=a,identity_tap=i,logical_cells=len(rows),status_counts=dict(Counter(x["status"] for x in rows)),full_bank_in_this_authority={x["case_id"] for x in rows}==CASES,physical_count_not_inferred=True))
 runtime_inputs=[(x["normalization"],x["cohort"]) for x in docs["timing_inputs"]["inputs"]]+[(bindings["long_normalization"],"continuous")]
 total=Counter();native_sessions=set();seen_normalizations=set()
 for nb,cohort in runtime_inputs:
  key=(nb["path"],nb["sha256"],cohort)
  if key in seen_normalizations:continue
  seen_normalizations.add(key)
  n,_=reader.doc(nb["path"],nb);require(n["status"]=="COMPLETE_METADATA_NORMALIZATION" and n["unresolved_runtime_rows"]==0,"Closed typed normalization")
  rb=n["outputs"]["runtime_rows"];rows,_=reader.doc(rb["path"],rb);require(len(rows)==n["runtime_rows"],"Runtime row count")
  rid=root(nb,"runtime_authority_"+str(len(resources)),n);rr=resource(rb,rid+"_rows",rid);groups=defaultdict(list)
  for x in rows:
   pid=x["candidate_id"];a=x["asr_tap"];i=x["identity_tap"];c=condition(pid,a,i,work,routes)
   require(all(x["condition"].get(k)==v for k,v in c.items()) and x["status"]=="COMPLETE" and x["owner_closed"] is True and x["tail_complete"] is True,"Exact executed condition/closure/tail")
   require(x["native_result_sha256"] not in native_sessions,"No repeated actual native session");native_sessions.add(x["native_result_sha256"]);groups[(pid,a,i)].append(x);total[cohort]+=1
  for (pid,a,i),xs in sorted(groups.items()):
   kind="long" if cohort=="continuous" else "paced";label={"main":"MAIN_BALANCED_PACED","cadence_gate":"CADENCE_GATE_DIAGNOSTIC","arrival":"ARRIVAL_SENTINEL_EXPLORATORY","cross":"FIXED_CROSS_ROUTE_PACED","continuous":"CONTINUOUS_SAVED_FILE"}[cohort]
   cols={k:"/"+k for k in ("candidate_id","asr_tap","identity_tap","cue_condition","gallery_condition","enrollment_tier","condition_sha256","status","owner_closed","tail_complete","native_result_sha256","source_duration_sec","continuous","case_id","repetition")}
   eid=f"{kind}_{len(evidence):04}_{pid}_{a}_{i}"
   require(all(x["condition"]==xs[0]["condition"] for x in xs),"One exact runtime condition per route")
   e=dict(evidence_id=eid,kind=kind,candidate_id=pid,authority_id=rid,scope_label=label,repetition="EXACT_DECLARED_REPETITIONS" if kind=="paced" else 1,status="AVAILABLE",condition=xs[0]["condition"],completion_checks=complete(rid,n),records=dict(resource_id=rr,pointer="",where={"/candidate_id":pid,"/asr_tap":a,"/identity_tap":i},columns=cols))
   if kind=="paced":e["expected_grid"]=[[x["case_id"],x["repetition"]] for x in xs]
   add(e);mapping[pid][kind+"_scopes"].append(dict(evidence_id=eid,authority=nb,rows=rb,asr_tap=a,identity_tap=i,scope_label=label,cells=len(xs),repetition_counts=dict(Counter(str(x["repetition"]) for x in xs)),actual_condition=e["condition"],main_panel_qualified=cohort=="main",full_bank=False,scientific_selection=False))
 require(total=={"main":520,"cadence_gate":24,"arrival":12,"cross":40,"continuous":5},"Exact596+5")
 # Carry reviewed interpretations without reranking or discarding prior settings.
 prov={x["candidate_id"]:x for x in docs["provisional"]["candidate_decisions"]};require(set(prov)==IDS,"Exact provisional IDs")
 decisions=[]
 for pid in sorted(IDS):
  p=prov[pid];m=mapping[pid]
  limits=[]
  for x in p["limitations"]:
   if x.startswith("Current S6C source-paced/continuous"):x="Only B00/B01/B36 have new main paced historical evidence; B36 O0 has the continuous comparator. Other historical settings keep original scope."
   if "Paced C071/C082 diagnostic remains pending." in x:x=x.replace("Paced C071/C082 diagnostic remains pending.","The exact C071/C082 six-case paced diagnostic is complete; it does not establish full-bank paced performance.")
   if x.startswith("Paced and continuous operating retention pending."):x=x.replace("Paced and continuous operating retention pending.","Operating retention remains a root decision after runtime interpretation.")
   limits.append(x)
  limits.extend(["Final census physical records and root acceptance/selection are unresolved in this input preparation.","Scores, native logical rows/reuse and actual paced repetitions remain separate authorities; no cross-authority summation."])
  interpretation=p["interpretation"]
  if m["paced_scopes"]:interpretation+=" Actual paced metadata is complete in the explicitly listed main/diagnostic routes; completion alone does not select an operating profile."
  if m["long_scopes"]:interpretation+=" The exact O0 continuous saved-file condition has completed diagnostic and normalized closure/tail evidence; continuous lexical/name correctness is unavailable."
  decisions.append(dict(candidate_id=pid,scientific_disposition=p["proposed_final_scientific_disposition"],proposed_final_scientific_disposition=p["proposed_final_scientific_disposition"],interpretation=interpretation,limitations=limits,evidence_ids=[e["evidence_id"] for e in evidence if e["candidate_id"]==pid],resolved=False))
  m["prior_decision_source"]=bindings["provisional"];m["proposed_final_scientific_disposition"]=p["proposed_final_scientific_disposition"];m["root_selection_resolved"]=False
 require(not mapping["C083"]["score_scopes"] and not mapping["C084"]["native_scopes"],"Aliases unpropagated")
 # Preserve all46 original obligations/rows. This is an input overlay, not acceptance.
 reqraw,reqb=reader.read(REPORT/"REQUIREMENT_COVERAGE_WORKING.csv");req=list(csv.DictReader(io.StringIO(reqraw.decode("utf-8-sig"))));require(len(req)==46,"Exact46 obligations")
 reqsources,qsb=reader.doc(REPORT/"REQUIREMENT_COVERAGE_WORKING_SOURCES.json")
 later={
 "R02":("candidate_map","Exact240 IDs/388 C routes preserved; census/selection still separate."),
 "R04":("census","Finite49-manifest census inputs reviewed; fresh physical census and machine exports pending."),
 "R05":("paced","All596 completed analyses and normalized actual emissions are available; inherited per-generation parity limits retained."),
 "R06":("candidate_map","Retain exact family gate/mechanism and panel scopes; final per-ID disposition requires root decision."),
 "R07":("offline","Registered full/endpoint/cadence comparisons completed; no best-null or inactive-branch rejection."),
 "R08":("offline","Full N03/N08/N10/N12 and both registered asymmetric cross routes complete; no panel unions."),
 "R10":("long","Five continuous diagnostics now complete; sampled resource gaps and exact condition limits remain."),
 "R14":("paced","Cadence floor native neighborhood and C071/C082 six-case paced diagnostic complete."),
 "R15":("offline","Fixed timing/decoder/dispatch plus endpoint factorial complete with separate raw-word effects."),
 "R16":("offline","18-route full token-boundary supplement complete; inherited overlap/strict-empty semantics retained."),
 "R17":("offline","C085/C086 exact asymmetric full240 routes and40 actual paced cells complete."),
 "R21":("enrollment","Two original A/B15 conditions plus C065 empty control have actual paced and O0 continuous evidence; common14 each/28 combined remain separate."),
 "R22":("paced","Offline live/retained/cold-warm and actual emission/name timing available; no conflation of first track/person."),
 "R23":("offline","Completed full paired/token/strata evidence available; final candidate disposition pending."),
 "R24":("hardware","Optional hardware not executed; saved-file work needs no attached XVF3800."),
 "R25":("long","Five1827.426625s uninterrupted host sessions completed;38-capture composition is not continuous hardware."),
 "R26":("paced","Main520cells cover13 exact conditions,16 primary+4 repeated cases on each tap; representative selection remains root-owned."),
 "R27":("paced","Each main condition has32 primary+8 repeat cells;72 descriptive timing groups retain repetition."),
 "R28":("long","Five exact O0 continuous conditions now available, including C065 control; retained2-4 still unselected."),
 "R29":("paced","596 actual emission/name/revision timing and diagnostics complete; modeled support/phonetic/GUI claims remain distinct."),
 "R30":("census","Native closures reported; fresh census and final current-resource/owner authority pending."),
 "R31":("acceptance","Prior bounded reviews preserved; final combined assembly/acceptance review pending.")}
 artifact_dependencies={"D01":"acceptance","D02":"artifacts","D03":"census","D04":"artifacts","D05":"candidate_map","D06":"long","D07":"enrollment","D08":"census","D09":"paced","D10":"hardware","D11":"selection","D12":"artifacts","D13":"artifacts","D14":"package","D15":"acceptance"}
 requirement_rows=[]
 for x in req:
  rid=x["requirement_id"];dep,note=later.get(rid,(artifact_dependencies.get(rid,"inherited"),"Prior source authority retained. Final deliverable/acceptance must be bound; this preparation does not certify it."))
  state="EVIDENCE_UPDATED_FINAL_RESOLUTION_PENDING" if rid in later and dep not in ("census","acceptance") else "FINAL_ARTIFACT_OR_AUTHORITY_PENDING" if rid.startswith("D") or dep in ("census","acceptance") else "INHERITED_SCOPED_EVIDENCE_FINAL_REVIEW_PENDING"
  if rid=="R24":state="OPTIONAL_NOT_EXECUTED_PENDING_FINAL_STATUS_ARTIFACT"
  requirement_rows.append(dict(requirement_id=rid,original_row=x,original_row_sha256=digest(x),updated_state=state,dependency_group=dep,update=note,resolved=False))
 require({x["requirement_id"] for x in requirement_rows}=={f"R{i:02}" for i in range(1,32)}|{f"D{i:02}" for i in range(1,16)},"Exact requirement IDs")
 output=Path(output).resolve();require(output.parent==REPORT/"candidate_disposition" and not output.exists(),"Fresh candidate_disposition child only");output.mkdir()
 def write(name,d):
  p=output/name;raw=encoded(d) if not isinstance(d,str) else d.encode()
  with p.open("xb") as f:f.write(raw)
  return bind(p,raw)
 unresolved=[
 dict(field="physical evidence",owner="Components/root",needed="Final fresh census output plus typed normalized physical rows, with exact failed/reused/unknown distinctions."),
 dict(field="candidate_decisions[].resolved",owner="root",needed="Review exact240 proposed statuses/interpretations and explicitly resolve without promoting aliases/panel scope."),
 dict(field="operating_presets",owner="root",needed="Select2-4 exact tested bundles; prospective B36/C067/C088/C091 O0 are not selected by this helper."),
 dict(field="requirement_resolution",owner="root",needed="Completed46-row authority linking finalized artifacts, requirement checks and remaining limitations."),
 dict(field="resource validation",owner="root/assembler",needed="Final assembler must read and hash all bound metadata resources, including original COVERAGE.csv. This preparation only binds those tables via exact completed receipts; no large score CSV reread.") ]
 prospective=[]
 for pid in ("B36","C067","C088","C091"):
  es=[e for e in evidence if e["candidate_id"]==pid and e["kind"]=="paced" and e["scope_label"]=="MAIN_BALANCED_PACED" and e["condition"]["asr_tap"]=="O0"]
  ls=[e for e in evidence if e["candidate_id"]==pid and e["kind"]=="long"]
  require(len(es)==len(ls)==1 and es[0]["condition"]==ls[0]["condition"],"Prospective exact main/long bundle")
  prospective.append(dict(candidate_id=pid,condition=es[0]["condition"],paced_evidence_id=es[0]["evidence_id"],long_evidence_id=ls[0]["evidence_id"],selected=False))
 inputs=dict(schema="s6c.final_disposition_inputs.v1",status="UNRESOLVED_FINAL_INPUT_ASSEMBLY",plan=bindings["plan"],working_receipt=bindings["working"],resources=resources,evidence=evidence,candidate_decisions=decisions,operating_presets=[],required_evidence_ids=[],requirement_resolution=dict(resolved=False,authority_id=None,checks=[]),prospective_operating_dependencies=prospective,unresolved_fields=unresolved,whole_study_complete=False)
 outputs=[write("FINAL_INPUTS_UNRESOLVED.json",inputs),write("CANDIDATE_EVIDENCE_MAP.json",dict(status="COMPLETE_SCOPED_INPUT_MAPPING_NOT_FINAL_DISPOSITION",candidate_count=240,registered_c_routes=388,candidates=list(mapping.values()),sources=bindings)),write("REQUIREMENT_RESOLUTION_INPUTS.json",dict(status="UNRESOLVED46_REQUIREMENT_INPUTS",original_csv=reqb,original_sources=qsb,requirements=requirement_rows,later_authorities=bindings,final_acceptance=False))]
 counts=dict(candidates=240,c_routes=388,evidence_by_kind=dict(Counter(e["kind"] for e in evidence)),runtime_cells_by_cohort=dict(total),scored_candidate_count=sum(bool(m["score_scopes"]) for m in mapping.values()),full_scored_candidate_count=sum(any(x["full_bank_in_this_authority"] for x in m["score_scopes"]) for m in mapping.values()),native_candidate_count=sum(bool(m["native_scopes"]) for m in mapping.values()),paced_candidate_count=sum(bool(m["paced_scopes"]) for m in mapping.values()),long_candidate_count=sum(bool(m["long_scopes"]) for m in mapping.values()))
 text="# Final input assembly awaiting root resolution\n\nExact240 candidate IDs and all46 requirements are preserved. No original CSV, registry, interpretation, score or native artifact was edited. This is an evidence input assembly, not final acceptance or operating selection.\n\n"+json.dumps(counts,indent=2)+"\n\nCompleted596 paced and five continuous typed rows map to exact executed conditions. Main520, cadence24, arrival12 and cross40 retain distinct scopes. Actual normalizer closure/tail means saved-file source completion, not first/last-token or continuous name correctness. B00 remains instrumentation-limited. Resource gaps51-63s constrain observed peaks.\n\nAll original score authorities and later full confirmations remain separate; full membership is per-authority, never a union. Original native metadata retains COMPLETE versus COMPLETE_REUSED; these are not physical attempt totals. C083/C084 remain unexecuted aliases. Candidate-level scientific proposals remain those reviewed previously. Root may resolve final representative and operating decisions after census and combined review.\n\nFour prospective O0 bundles (B36 NONE, C067 NONE, C088 originalA15, C091 originalB15) have exact main/long evidence references; selected=false. C065 remains the empty-gallery/control long. Common-duration rosters are each14, combined28, and are not substituted for original A/B15.\n\nNext: bind fresh physical census/normalization; finalize46 requirement/artifact authority; root explicitly resolves240 decisions and2-4 operating presets; invoke unchanged final assembler with a new READY input after full metadata DAG validation. Do not relabel this unresolved file READY.\n"
 outputs.append(write("ASSEMBLY_NOTES.md",text))
 sources=list(reader.sources.values())
 for p in (Path(__file__),Path(__file__).with_name("README_S6C_FINAL_EVIDENCE_INPUTS_V1.md")):
  raw=p.read_bytes();sources.append(bind(p,raw))
 receipt=write("PREPARATION_RECEIPT.json",dict(schema="s6c.final_evidence_input_preparation.v1",status="COMPLETE_INPUT_PREPARATION_NOT_FINAL_ACCEPTANCE",counts=counts,tests=tests(),sources=sources,outputs=outputs,unresolved_fields=unresolved,new_models=0,new_scores=0,actual_final_assembly=False,scope="Finite existing receipts and metadata only; no score values, predictions, logs, audio or physical census read. COVERAGE tables are deferred source-bound projections."))
 print(json.dumps(receipt))
if __name__=="__main__":
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument("--output",required=True);run(p.parse_args().output)
