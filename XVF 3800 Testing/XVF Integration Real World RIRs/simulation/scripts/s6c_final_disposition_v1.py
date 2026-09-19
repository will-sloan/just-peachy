"""Finite append-only disposition assembly. See README_S6C_FINAL_DISPOSITION_V1.md."""
from __future__ import annotations
import argparse, csv, hashlib, io, json, math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / "reports/S6C/20260910T123540Z"
PLAN_SHA = "f6b19c7070a266a775b13fac4464557910e70680c9c5f9efa58c8df67dc8980f"
WORK_SHA = "5d84d493a377eb7b991e821cf59e412da5103ba7e17786e197bb2dd9c1ecc8dd"
IDS = {f"B{i:02}" for i in range(40)} | {"B18_C1","B20_C1","B24_FREQUENT","B24_SPARSE"} | {f"C{i:03}" for i in range(1,197)}
CASES = {f"S45_{f:02}_{n:02}" for f in range(1,13) for n in range(1,21)}
SCIENTIFIC = {"HISTORICAL_CONTROL_PRESERVED","EXACT_ALIAS_NOT_EXECUTED","REPRESENTATIVE_EVALUATED","FULL_CONFIRMATION_TRADEOFF","PANEL_LIMITED_DIAGNOSTIC","ADMISSION_LIMITED_DIAGNOSTIC","CONDITIONAL_ENROLLMENT_REFERENCE","ORACLE_OR_NULL_DIAGNOSTIC","UNVERIFIED_SCOPE"}
KINDS = {"score","native","physical","paced","long","interpretation"}
FIELDS = ["final_scored_authorities_json","final_native_integration_json","final_physical_execution_json","final_paced_evidence_json","final_long_evidence_json","final_supported_interpretation_and_gaps","final_scientific_disposition","final_operating_presets_json"]
GOOD = {"SCORED","COMPLETE","COMPLETE_REUSED"}
NATIVE_GOOD = {"COMPLETE","COMPLETE_REUSED"}
LIMIT = 32 * 1024 * 1024

def require(v, message):
    if not v: raise ValueError(message)

def digest(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def json_bytes(v):
    return (json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode()

def unique_pairs(pairs):
    out={}
    for k,v in pairs:
        require(k not in out,"Duplicate JSON key: "+k); out[k]=v
    return out

def parse(raw):
    return json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON "+x)))

def pointer(value, path):
    require(isinstance(path,str) and (path=="" or path.startswith("/")),"JSON pointer required")
    for piece in path.split("/")[1:]:
        piece=piece.replace("~1","/").replace("~0","~")
        value=value[int(piece)] if isinstance(value,list) else value[piece]
    return value

def contains_binding(value, target):
    if isinstance(value,dict):
        if all(value.get(k)==target.get(k) for k in ("path","sha256","bytes")): return True
        return any(contains_binding(v,target) for v in value.values())
    return isinstance(value,list) and any(contains_binding(v,target) for v in value)

class Reader:
    def __init__(self): self.bindings={}; self.buffers={}
    def raw(self, binding):
        require(set(("path","sha256","bytes")) <= binding.keys(),"Exact binding required")
        p=Path(binding["path"]);require(p.is_absolute(),"Absolute bound metadata path required")
        require(p.suffix.lower() in {".json",".csv",".md"},"Metadata only")
        key=str(p.resolve());require(p.stat().st_size<=LIMIT,"Metadata exceeds32MiB")
        raw=p.read_bytes();require(len(raw)<=LIMIT,"Metadata grew beyond limit")
        got={"path":str(p),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
        require(got=={k:binding[k] for k in got},"Changed bound metadata: "+str(p))
        require(key not in self.bindings or self.bindings[key]==got,"Conflicting path authority")
        self.bindings[key]=got;self.buffers[key]=raw
        return raw
    def doc(self,binding): return parse(self.raw(binding))

def binding(path):
    p=Path(path);require(p.stat().st_size<=LIMIT,"Bounded metadata")
    b=p.read_bytes();return {"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}

def csv_rows(raw):
    f=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields=f.fieldnames or []
    require(len(fields)==len(set(fields)) and fields,"Distinct CSV columns")
    rows=list(f);require(all(None not in r for r in rows),"Malformed CSV row")
    return fields,rows

def expected(receipt, assertions):
    require(isinstance(assertions,dict) and assertions,"Explicit source assertions required")
    for path,value in assertions.items():
        require(pointer(receipt,path)==value,"Authority assertion failed: "+path)

def completed_assertions(receipt, assertions):
    expected(receipt,assertions)
    values=[v for k,v in assertions.items() if k.rsplit('/',1)[-1] in {'status','audit_status'}]
    def good(v):
        return isinstance(v,str) and (v=='PASS' or v.startswith(('COMPLETE','PASS_','NATIVE_COMPLETE'))) and not any(t in v for t in ('PARTIAL','UNVERIFIED','PENDING','FAILED','NOT_','PREPARED'))
    require(any(good(v) for v in values),'Explicit successful completion status required')

def validate_working(reader, spec):
    plan=reader.doc(spec["plan"]);require(spec["plan"]["sha256"]==PLAN_SHA,"Pinned V2 assembly plan")
    work=reader.doc(spec["working_receipt"]);require(spec["working_receipt"]["sha256"]==WORK_SHA,"Pinned working receipt")
    require(work["status"]=="COMPLETE_WORKING_PROPOSAL_ONLY","Working authority status")
    def output(name):
        matches=[x for x in work["outputs"] if Path(x["path"]).name==name]
        require(len(matches)==1,"Unique working output");return matches[0]
    raw=reader.raw(output("CANDIDATE_DISPOSITION_PROPOSAL.csv"));fields,rows=csv_rows(raw)
    require(len(rows)==240 and {r["candidate_id"] for r in rows}==IDS,"Exact44B+196C")
    require(len({r["candidate_id"] for r in rows})==240,"Duplicate candidate")
    require(not set(fields)&set(FIELDS),"Final overlay already present")
    original_raw=reader.raw(output("ORIGINAL_REGISTRATION_SNAPSHOT.csv"));_,original=csv_rows(original_raw)
    originals={r["candidate_id"]:r for r in original};require(len(original)==len(originals)==160,"Original160")
    routes=reader.doc(output("REGISTERED_ROUTE_SETTINGS_PROVENANCE.json"));require(len(routes["routes"])==388,"Exact388 C route settings")
    byroute={(r["candidate_id"],r["asr_tap"],r["identity_tap"]):r for r in routes["routes"]}
    require(len(byroute)==388,"Distinct C routes")
    for r in rows:
        pid=r["candidate_id"];require(r["physical_inference_count"]=="","Preserve blank physical count")
        if pid in originals:
            require(parse(r["original_registration_row_json"])==originals[pid],"Original setting row changed")
            require(digest(originals[pid])==r["original_registration_row_sha256"],"Original row digest")
        else: require(r["original_registration_row_json"]=="","Invented additive original")
        for c in parse(r["exact_route_settings_provenance_json"]):
            ref=byroute[(pid,c["asr_tap"],c["identity_tap"])]
            require(all(ref[k]==v for k,v in c.items()),"Working registered route changed")
    return plan,work,fields,rows,original_raw,byroute

def load_resources(reader, resources):
    """Finite DAG: children must be byte-bound by an already admitted parent."""
    result={};roots=set();paths=set()
    for item in resources:
        rid=item["resource_id"];require(rid not in result,"Duplicate resource ID")
        b=item["binding"];key=str(Path(b["path"]).resolve())
        require(key not in paths,"Repeated resource path; refer to existing ID")
        if item.get("parent"):
            require(item["parent"] in result,"Resource DAG parent must precede child")
            require(contains_binding(result[item["parent"]]["value"],b),"Child is not bound by parent")
        else:
            require(b["sha256"] not in roots,"Duplicate root authority content")
            roots.add(b["sha256"])
        raw=reader.raw(b)
        fmt=item["format"];require(fmt in {"json","csv","text"},"Metadata format")
        if fmt=="json": value=parse(raw)
        elif fmt=="csv": value=csv_rows(raw)[1]
        else: value=raw.decode("utf-8-sig")
        if not item.get("parent"):
            require(fmt=="json","Root authority must be structured JSON")
            expected(value,item["assertions"])
        elif item.get("assertions"): expected(value,item["assertions"])
        result[rid]={"value":value,"binding":b,"parent":item.get("parent"),"root":result[item["parent"]]["root"] if item.get("parent") else rid}
        paths.add(key)
    return result

def fact(resources, ref):
    require(set(ref)=={"resource_id","pointer"},"Facts must come from exact resource pointers")
    return pointer(resources[ref["resource_id"]]["value"],ref["pointer"])

def project_rows(resources, selection):
    source=resources[selection["resource_id"]]
    rows=pointer(source["value"],selection.get("pointer",""))
    require(isinstance(rows,list),"Explicit metadata row list required")
    out=[]
    for row in rows:
        if not all(pointer(row,k)==v for k,v in selection.get("where",{}).items()): continue
        out.append({k:pointer(row,path) for k,path in selection["columns"].items()})
    return out

def integer(x):
    require(isinstance(x,int) and not isinstance(x,bool) and x>=0,"Nonnegative integer metadata");return x

def finite(x):
    require(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x),"Finite numeric metadata");return float(x)

def route_for(pid, condition, working, byroute):
    require(condition["asr_tap"] in ("O0","O1") and condition["identity_tap"] in ("O0","O1"),"Tap value")
    require([condition["asr_tap"],condition["identity_tap"]] in parse(working["registered_routes"]),"Unregistered route")
    if pid.startswith("C"):
        r=byroute[(pid,condition["asr_tap"],condition["identity_tap"])]
        for field in ("recipe_id","cue_condition","gallery_condition","enrollment_tier","profile_sha256","executable_condition_sha256"):
            require(condition.get(field)==r[field],"Exact C condition differs: "+field)
    else:
        require(condition.get("original_registration_row_sha256")==working["original_registration_row_sha256"],"Exact historical settings")
        require(condition.get("gallery_condition")=="NONE" and condition.get("enrollment_tier") is None,"Historical gallery scope")
    return condition

def validate_evidence(e, resources, working, byroute):
    kind=e["kind"];pid=e["candidate_id"];require(kind in KINDS and pid in working,"Evidence kind/candidate")
    require(e["scope_label"] and e["repetition"] is not None,"Explicit authority scope and repetition")
    root=resources[e["authority_id"]];require(root["parent"] is None,"Declared evidence authority must be DAG root")
    condition=e.get("condition")
    if kind not in ("interpretation","physical"):
        route_for(pid,condition,working[pid],byroute)
    require(e["status"] in {"AVAILABLE","PREPARED","PARTIAL_OR_FAILED","PENDING_OR_UNVERIFIED","NOT_EXECUTED_WITH_EXPLICIT_FINAL_AUTHORITY"},"Evidence availability status")
    if e["status"]!="AVAILABLE":
        require(e.get("reason"),"Unresolved scope needs a reason")
        return dict(e,computed_status=e["status"],full_bank_in_this_authority=False)
    # No inline 'completed' flags: every assertion refers to source metadata.
    require(e.get("completion_checks"),"Completed source proof required")
    for check in e["completion_checks"]:
        require(resources[check["resource_id"]]["root"]==e["authority_id"],"Completion proof from another authority")
        completed_assertions(resources[check["resource_id"]]["value"],check["equals"])
    if kind=="interpretation":
        require(e.get("text") and e.get("limitations"),"Interpretation and limits")
        return dict(e,computed_status="SOURCE_BOUND_INTERPRETATION")
    sel=e["records"];require(resources[sel["resource_id"]]["root"]==e["authority_id"],"Foreign evidence rows")
    rows=project_rows(resources,sel)
    require(rows,"Available evidence has no actual rows")
    require(all(r["candidate_id"]==pid for r in rows),"Another candidate's native/scored/runtime evidence")
    if kind!="physical":
        require(all(r["asr_tap"]==condition["asr_tap"] and r["identity_tap"]==condition["identity_tap"] for r in rows),"Route inflation")
    result=dict(e,source_rows=rows,row_count=len(rows),full_bank_in_this_authority=False)
    if kind in {"score","native"}:
        require(all(r["case_id"] in CASES for r in rows),"Noncanonical source case")
        keys=[(r["case_id"],r.get("repetition",e["repetition"])) for r in rows]
        require(len(keys)==len(set(keys)),"Duplicate case within one authority/repetition")
        if kind=="native":
            require(all(r["status"] in NATIVE_GOOD for r in rows),"Native rows require COMPLETE or COMPLETE_REUSED; scoring status is not native completion")
            require(all(r.get("job_key") and r.get("receipt_sha256") for r in rows),"Actual native job/receipt identities required")
            require(len({r["job_key"] for r in rows})==len(rows),"Duplicate native job")
        scored=[r for r in rows if r["status"] in (NATIVE_GOOD if kind=="native" else GOOD)]
        cases={r["case_id"] for r in scored}
        require(len({r.get("repetition",e["repetition"]) for r in rows})==1,"Repetitions must be separate evidence records")
        result.update(status_counts=dict(Counter(r["status"] for r in rows)),successful_case_ids=sorted(cases),
            declared_case_ids=sorted({r["case_id"] for r in rows}),full_bank_in_this_authority=cases==CASES,
            computed_status=("COMPLETE_SCORING" if len(scored)==len(rows) else "PARTIAL_SCORING") if kind=="score" else ("ESTABLISHED_IN_EXACT_CLOSED_SCOPE" if len(scored)==len(rows) else "PENDING_OR_UNVERIFIED"))
    elif kind=="physical":
        require(all(r.get("physical_id") for r in rows),"Exact physical identity")
        require(len({r["physical_id"] for r in rows})==len(rows),"Duplicate physical ID inside authority")
        for r in rows:
            if r.get("creation_time") is not None: require(finite(r["creation_time"])>0,"Owner creation")
            if r.get("pid") is not None: require(integer(r["pid"])>0,"Owner PID")
            require(r.get("alive") is None or type(r.get("alive")) is bool,"Nullable closure state")
        result.update(computed_status="EXACT_INVENTORY_RECORDS_NOT_SCORE_DERIVED",
            physical_ids=[r["physical_id"] for r in rows],
            unknown_creation_or_closure=sum(r.get("creation_time") is None or r.get("alive") is None for r in rows),
            counts_scope="Unique IDs in this one authority only; no cross-authority sum, model-call conversion or score-derived count.")
    else:
        # Runtime metadata must explicitly expose the executed condition, not a title.
        for r in rows:
            for field in ("cue_condition","gallery_condition","enrollment_tier"):
                require(r.get(field)==condition.get(field),"Runtime condition mismatch: "+field)
            require(r.get("condition_sha256")==condition.get("executable_condition_sha256",condition.get("original_registration_row_sha256")),"Runtime executed condition fingerprint")
            require(r.get("owner_closed") is True and r.get("tail_complete") is True,"Closed owner and complete tail required")
            require(r["status"]=="COMPLETE","Incomplete actual runtime cell")
            require(r.get("native_result_sha256"),"Actual native result authority required")
            require(finite(r["source_duration_sec"])>0,"Positive actual source duration")
        if kind=="paced":
            keys=[(r["case_id"],r["repetition"]) for r in rows]
            require(len(keys)==len(set(keys)),"Repeated paced logical cell")
            require(all(r["case_id"] in CASES and integer(r["repetition"])>=1 for r in rows),"Canonical paced grid")
            require(set(map(tuple,e["expected_grid"]))==set(keys),"Exact explicit paced manifest grid")
            primary={r["case_id"] for r in rows if r["repetition"]==1}
            repeated={r["case_id"] for r in rows if r["repetition"]>1}
            result.update(computed_status="COMPLETE_OBSERVED_SCOPE",main_panel_qualified=e["scope_label"]=="MAIN_BALANCED_PACED" and len(primary)>=12 and len(repeated)>=4 and repeated<=primary,
                main_case_count=len(primary),repeat_case_count=len(repeated))
        else:
            require(len(rows)==1 and rows[0].get("continuous") is True,"One actual continuous native session")
            require(1800<=finite(rows[0]["source_duration_sec"])<=3600,"Required30–60-minute actual source")
            result.update(computed_status="COMPLETE_CONTINUOUS_OBSERVED_SCOPE")
    return result

def same_condition(a,b): return a==b

def validate_operating(records, evidence, working, byroute):
    require(2<=len(records)<=4,"Final operating selection requires2–4 exact conditions")
    require(len({r["preset_id"] for r in records})==len(records),"Unique preset IDs")
    seen=set()
    for r in records:
        pid=r["candidate_id"];condition=route_for(pid,r["condition"],working[pid],byroute)
        key=(pid,digest(condition));require(key not in seen,"Duplicate operating bundle");seen.add(key)
        require(r["status"] in {"RETAINED_OPERATING_PRESET","RETAINED_FALLBACK"} and r.get("reason"),"Explicit root operating decision")
        p=evidence[r["paced_evidence_id"]];l=evidence[r["long_evidence_id"]]
        require(p["kind"]=="paced" and p.get("main_panel_qualified") is True,"Completed main paced coverage required")
        require(l["kind"]=="long" and l["computed_status"]=="COMPLETE_CONTINUOUS_OBSERVED_SCOPE","Completed continuous evidence required")
        require(p["candidate_id"]==l["candidate_id"]==pid and same_condition(p["condition"],condition) and same_condition(l["condition"],condition),"Operating bundle differs from tested bundle")
    return records

def prepare_template(plan_path, output):
    pb=binding(Path(plan_path));require(pb["sha256"]==PLAN_SHA,"Pinned plan")
    plan=parse(Path(plan_path).read_bytes())
    wb=next(b for b in plan["basis"] if Path(b["path"]).name=="RECEIPT.json" and b["sha256"]==WORK_SHA)
    out={"schema":"s6c.final_disposition_inputs.v1","status":"UNRESOLVED_TEMPLATE","plan":pb,"working_receipt":wb,
        "resources":[],"evidence":[],"candidate_decisions":[{"candidate_id":pid,"scientific_disposition":"UNVERIFIED_SCOPE","interpretation":"PENDING","limitations":["Final authority selection pending"],"evidence_ids":[],"resolved":False} for pid in sorted(IDS)],
        "operating_presets":[],"required_evidence_ids":[],"requirement_resolution":{"resolved":False,"authority_id":None,"checks":[]},
        "instructions":"Fill finite source-bound metadata resources, evidence projections, explicit240 decisions and2–4 completed exact operating bundles. No raw logs/models/prediction bodies; no final completion from this template."}
    path=Path(output);require(not path.exists(),"Fresh template path")
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(json_bytes(out));return binding(path)

def assemble(spec_path, output):
    reader=Reader();sb=binding(Path(spec_path));spec=reader.doc(sb)
    require(spec["schema"]=="s6c.final_disposition_inputs.v1" and spec["status"]=="READY_FOR_FINAL_ASSEMBLY","Unresolved template cannot complete")
    plan,work,fields,rows,original,byroute=validate_working(reader,spec)
    working={r["candidate_id"]:r for r in rows};resources=load_resources(reader,spec["resources"])
    evidence={}
    for e in spec["evidence"]:
        eid=e["evidence_id"];require(eid not in evidence,"Duplicate evidence ID")
        evidence[eid]=validate_evidence(e,resources,working,byroute)
    decisions=spec["candidate_decisions"];require(len(decisions)==240 and {d["candidate_id"] for d in decisions}==IDS,"Exact240 final decisions")
    require(len({d["candidate_id"] for d in decisions})==240,"Duplicate final decision")
    required=spec["required_evidence_ids"];require(required and len(required)==len(set(required)),"Explicit finite mandatory evidence list")
    for eid in required:
        require(eid in evidence and evidence[eid]["computed_status"] in {"COMPLETE_SCORING","ESTABLISHED_IN_EXACT_CLOSED_SCOPE","EXACT_INVENTORY_RECORDS_NOT_SCORE_DERIVED","COMPLETE_OBSERVED_SCOPE","COMPLETE_CONTINUOUS_OBSERVED_SCOPE","SOURCE_BOUND_INTERPRETATION"},"Required evidence unresolved")
        if evidence[eid]['kind']=='physical':
            require(evidence[eid]['unknown_creation_or_closure']==0 and all(r.get('alive') is False for r in evidence[eid]['source_rows']),'Required physical closure unresolved')
    resolution=spec["requirement_resolution"];require(resolution["resolved"] is True and resolution["checks"],"Requirement authority unresolved")
    require(resolution["authority_id"] in resources,"Missing requirement authority")
    completed_assertions(resources[resolution["authority_id"]]["value"],resolution["checks"])
    operating=validate_operating(spec["operating_presets"],evidence,working,byroute)
    final=[];detailed=[]
    kindfield=dict(score=FIELDS[0],native=FIELDS[1],physical=FIELDS[2],paced=FIELDS[3],long=FIELDS[4])
    for d in decisions:
        pid=d["candidate_id"];require(d["resolved"] is True and d["scientific_disposition"] in SCIENTIFIC,"Unresolved scientific decision")
        require(d["interpretation"] and d["interpretation"]!="PENDING" and d["limitations"],"Explicit interpretation/limitations")
        require(len(d["evidence_ids"])==len(set(d["evidence_ids"])),"Duplicate candidate evidence reference")
        es=[evidence[i] for i in d["evidence_ids"]];require(all(e["candidate_id"]==pid for e in es),"Candidate evidence identity mismatch")
        require(set(d["evidence_ids"])=={i for i,e in evidence.items() if e["candidate_id"]==pid},"Omitted candidate evidence")
        if pid in {"C083","C084"}:
            require(d["scientific_disposition"]=="EXACT_ALIAS_NOT_EXECUTED" and not any(e["kind"] in {"score","native","physical","paced","long"} and e["status"]=="AVAILABLE" for e in es),"Alias receives propagated execution")
        if d["scientific_disposition"]=="REPRESENTATIVE_EVALUATED":
            require(any(e.get("main_panel_qualified") for e in es),"Representative lacks actual main paced scope")
        out=dict(working[pid])
        for k,f in kindfield.items():out[f]=json.dumps([e for e in es if e["kind"]==k],ensure_ascii=False,allow_nan=False,separators=(",",":"))
        out[FIELDS[5]]=json.dumps({"interpretation":d["interpretation"],"limitations":d["limitations"],"evidence_ids":d["evidence_ids"]},ensure_ascii=False)
        out[FIELDS[6]]=d["scientific_disposition"]
        out[FIELDS[7]]=json.dumps([r for r in operating if r["candidate_id"]==pid] or [{"status":"NOT_SELECTED_FOR_OPERATION"}],ensure_ascii=False,allow_nan=False)
        require(all(out[k]==working[pid][k] for k in fields),"Working column mutated")
        final.append(out);detailed.append({"candidate_id":pid,"decision":d,"evidence":es})
    output=Path(output).resolve();base=(REPORT/"candidate_disposition").resolve()
    require(output.is_relative_to(base) and output!=base and not output.exists(),"Fresh contained final namespace")
    # No final output is published before every admission succeeds.
    output.mkdir(parents=True)
    def publish(name,raw):
        p=output/name
        with p.open("xb") as f:f.write(raw)
        return binding(p)
    buf=io.StringIO(newline="");w=csv.DictWriter(buf,fieldnames=fields+FIELDS);w.writeheader();w.writerows(final)
    outputs=[publish("CANDIDATE_DISPOSITION_FINAL.csv",buf.getvalue().encode()),
        publish("ORIGINAL_REGISTRATION_SNAPSHOT.csv",original),
        publish("FINAL_ROUTE_EVIDENCE.json",json_bytes(detailed)),
        publish("OPERATING_PRESETS.json",json_bytes(operating))]
    lines=["# Final candidate disposition assembly","","All240 original working rows/settings are preserved. Final overlays are source-bound metadata joins, not new models, scores, physical recount or whole-campaign certification.","","| Candidate | Scientific disposition | Operating preset IDs |","|---|---|---|"]
    for d in sorted(decisions,key=lambda d:d["candidate_id"]):
        names=[r["preset_id"] for r in operating if r["candidate_id"]==d["candidate_id"]]
        lines.append("| "+d["candidate_id"]+" | "+d["scientific_disposition"]+" | "+(", ".join(names) or "Not selected")+" |")
    outputs.append(publish("FINAL_DISPOSITION.md",("\n".join(lines)+"\n").encode()))
    code=binding(Path(__file__));readme=binding(Path(__file__).with_name("README_S6C_FINAL_DISPOSITION_V1.md"))
    receipt={"schema":"s6c.final_disposition_assembly.v1","status":"COMPLETE_EXPLICIT_DISPOSITION_ASSEMBLY","whole_study_complete":False,
        "candidate_count":240,"registered_c_routes":388,"original_rows_preserved":160,"appended_rows":80,"operating_preset_count":len(operating),
        "created_utc":datetime.now(timezone.utc).isoformat(),"input_manifest":sb,"code":code,"readme":readme,
        "source_bindings":list(reader.bindings.values()),"outputs":outputs,"model_calls":0,"score_runs":0,"physical_counts_recomputed_from_scores":False,
        "scope":"Exact finite metadata admission only. Existing working physical-count cells remain blank; authority/repetition populations remain separate. Final study acceptance is a separate root responsibility."}
    return publish("RECEIPT.json",json_bytes(receipt))

def tests():
    passed=[]
    def yes(name,fn):fn();passed.append(name)
    def no(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError,IndexError):passed.append(name);return
        raise AssertionError("Expected rejection: "+name)
    yes("240 actual IDs",lambda:require(len(IDS)==240 and "B43" not in IDS and "B18_C1" in IDS,"IDs"))
    no("duplicate JSON",lambda:parse(b'{"a":1,"a":2}'))
    no("nonfinite JSON",lambda:parse(b'{"a":NaN}'))
    no("bool owner",lambda:finite(True))
    no("nan owner",lambda:finite(float("nan")))
    yes("pointer escapes",lambda:require(pointer({"a/b":{"x~y":3}},"/a~1b/x~0y")==3,"pointer"))
    no("CSV duplicate column",lambda:csv_rows(b"a,a\n1,2\n"))
    no("CSV overflow",lambda:csv_rows(b"a\n1,2\n"))
    yes("binding traversal",lambda:require(contains_binding({"outputs":[{"path":"p","sha256":"s","bytes":2}]},{"path":"p","sha256":"s","bytes":2}),"link"))
    no("foreign binding",lambda:require(contains_binding({"path":"p","sha256":"other","bytes":2},{"path":"p","sha256":"s","bytes":2}),"foreign"))
    no("unresolved assertion",lambda:expected({"status":"PREPARED"},{"/status":"COMPLETE"}))
    no("empty completion proof",lambda:expected({},{}))
    resource={"r":{"value":[{"pid":"C001","tap":"O0","case":"x"}],"binding":{},"parent":None,"root":"r"}}
    sel={"resource_id":"r","columns":{"candidate_id":"/pid"},"where":{"/tap":"O1"}}
    yes("filter does not manufacture rows",lambda:require(project_rows(resource,sel)==[],"filter"))
    no("literal fabricated fact",lambda:fact(resource,{"value":240}))
    no("two-to-four operating guard",lambda:validate_operating([],{}, {},{}))
    no('prepared is not completed',lambda:completed_assertions({'status':'PREPARED'},{'/status':'PREPARED'}))
    no('partial is not completed',lambda:completed_assertions({'status':'COMPLETE_PARTIAL'},{'/status':'COMPLETE_PARTIAL'}))
    no('unverified closure is not completed',lambda:completed_assertions({'status':'NATIVE_COMPLETE_CLOSURE_UNVERIFIED'},{'/status':'NATIVE_COMPLETE_CLOSURE_UNVERIFIED'}))
    cond=dict(asr_tap='O0',identity_tap='O0',recipe_id='N01',cue_condition='CUES_OFF',gallery_condition='NONE',enrollment_tier=None,profile_sha256='profile',executable_condition_sha256='condition')
    working={'C065':{'registered_routes':'[["O0","O0"]]'}}
    registry={('C065','O0','O0'):dict(candidate_id='C065',**cond)}
    def evaluate(kind,records,changes=None):
        resource={'root':{'value':{'status':'COMPLETE','rows':records},'parent':None,'root':'root','binding':{}}}
        cols={k:'/'+k for k in records[0]}
        e=dict(evidence_id='e',kind=kind,candidate_id='C065',scope_label='MAIN_BALANCED_PACED' if kind=='paced' else 'EXPLICIT_FIXTURE_SCOPE',repetition=1,authority_id='root',condition=dict(cond),status='AVAILABLE',completion_checks=[{'resource_id':'root','equals':{'/status':'COMPLETE'}}],records={'resource_id':'root','pointer':'/rows','columns':cols})
        if kind=='paced':e['expected_grid']=[[r['case_id'],r['repetition']] for r in records]
        e.update(changes or {})
        return validate_evidence(e,resource,working,registry)
    score=[dict(candidate_id='C065',asr_tap='O0',identity_tap='O0',case_id=c,status='SCORED') for c in sorted(CASES)]
    yes('one authority full240',lambda:require(evaluate('score',score)['full_bank_in_this_authority'],'full'))
    yes('120 panel remains partial scope',lambda:require(not evaluate('score',score[:120])['full_bank_in_this_authority'],'panel'))
    yes('failed row kept in denominator',lambda:require(evaluate('score',[dict(r,status='FAILED') if i==0 else r for i,r in enumerate(score)])['computed_status']=='PARTIAL_SCORING','failed'))
    no('duplicate case in authority',lambda:evaluate('score',score+[score[0]]))
    no('wrong candidate native credit',lambda:evaluate('score',[dict(score[0],candidate_id='C066')]))
    no('wrong identity tap',lambda:evaluate('score',[dict(score[0],identity_tap='O1')]))
    no('score rows cannot be native receipts',lambda:evaluate('native',score))
    no('SCORED plus native-shaped identity cannot grant native completion',lambda:evaluate('native',[dict(score[0],job_key='real-shaped-key',receipt_sha256='receipt-shaped-hash')]))
    no('two repeats cannot create single authority full',lambda:evaluate('score',[dict(r,repetition=1+i%2) for i,r in enumerate(score)]))
    runtimebase=dict(candidate_id='C065',asr_tap='O0',identity_tap='O0',status='COMPLETE',cue_condition='CUES_OFF',gallery_condition='NONE',enrollment_tier=None,condition_sha256='condition',owner_closed=True,tail_complete=True,native_result_sha256='native',source_duration_sec=44.7)
    paced=[dict(runtimebase,case_id=c,repetition=1) for c in sorted(CASES)[:16]]+[dict(runtimebase,case_id=c,repetition=2) for c in sorted(CASES)[:4]]
    pe=evaluate('paced',paced);le=evaluate('long',[dict(runtimebase,continuous=True,source_duration_sec=1827.4)])
    yes('actual16plus4 main qualifies',lambda:require(pe['main_panel_qualified'],'paced'))
    yes('diagnostic6 not main',lambda:require(not evaluate('paced',paced[:6])['main_panel_qualified'],'six'))
    no('foreign roster runtime',lambda:evaluate('paced',[dict(paced[0],gallery_condition='FIXED_ROSTER_A')]))
    no('unfinished owner runtime',lambda:evaluate('paced',[dict(paced[0],owner_closed=False)]))
    no('incomplete tail runtime',lambda:evaluate('paced',[dict(paced[0],tail_complete=False)]))
    no('29minute long insufficient',lambda:evaluate('long',[dict(runtimebase,continuous=True,source_duration_sec=1740)]))
    no('chronology not actual continuous',lambda:evaluate('long',[dict(runtimebase,continuous=False,source_duration_sec=1827)]))
    no('two sessions not one long',lambda:evaluate('long',[dict(runtimebase,continuous=True,source_duration_sec=1827)]*2))
    no('wrong prepared paced grid',lambda:evaluate('paced',paced,{'expected_grid':[[paced[0]['case_id'],1]]}))
    physical=dict(candidate_id='C065',physical_id='pid:1:created:2:session:x',creation_time=None,pid=1,alive=None)
    yes('unknown physical closure retained',lambda:require(evaluate('physical',[physical])['unknown_creation_or_closure']==1,'unknown'))
    no('duplicate physical identity',lambda:evaluate('physical',[physical,physical]))
    no('numeric false not closure boolean',lambda:evaluate('physical',[dict(physical,alive=0)]))
    cond1=dict(cond,asr_tap='O1',identity_tap='O1',profile_sha256='profile1',executable_condition_sha256='condition1')
    working['C065']['registered_routes']='[["O0","O0"],["O1","O1"]]'
    registry['C065','O1','O1']=dict(candidate_id='C065',**cond1)
    evidence={'p0':pe,'l0':le,'p1':dict(pe,condition=cond1),'l1':dict(le,condition=cond1)}
    presets=[dict(preset_id='first',candidate_id='C065',condition=cond,status='RETAINED_OPERATING_PRESET',reason='fixture',paced_evidence_id='p0',long_evidence_id='l0'),dict(preset_id='second',candidate_id='C065',condition=cond1,status='RETAINED_FALLBACK',reason='fixture',paced_evidence_id='p1',long_evidence_id='l1')]
    yes('two exact operating bundles',lambda:validate_operating(presets,evidence,working,registry))
    no('duplicate operating bundle',lambda:validate_operating([presets[0],dict(presets[0],preset_id='other')],evidence,working,registry))
    no('prepared long cannot retain',lambda:validate_operating(presets,dict(evidence,l0=dict(le,computed_status='PREPARED')),working,registry))
    no('diagnostic paced cannot retain',lambda:validate_operating(presets,dict(evidence,p0=dict(pe,main_panel_qualified=False)),working,registry))
    no('opposite-tap evidence cannot retain',lambda:validate_operating([dict(presets[0],long_evidence_id='l1'),presets[1]],evidence,working,registry))
    require(len(passed)==44,"Fixture count")
    return {"status":"PASS","checks":passed,"count":len(passed),"scope":"Small pure parser/binding/status fixtures; no actual assembly, models, scores or bank reads."}

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest="command",required=True)
    sub.add_parser("test")
    p=sub.add_parser("template");p.add_argument("--plan",required=True);p.add_argument("--output",required=True)
    p=sub.add_parser("assemble");p.add_argument("--manifest",required=True);p.add_argument("--output-subdir",required=True)
    a=ap.parse_args()
    if a.command=="test": result=tests()
    elif a.command=="template":result=prepare_template(a.plan,a.output)
    else:
        require(Path(a.output_subdir).name==a.output_subdir and a.output_subdir not in {"",".",".."},"One output directory name")
        result=assemble(a.manifest,REPORT/"candidate_disposition"/a.output_subdir)
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=="__main__":main()
