"""Provisional 240-ID reporting overlay; see README_S6C_CANDIDATE_DECISIONS_OVERLAY_V1.md."""
from __future__ import annotations
import argparse, ast, csv, hashlib, io, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / "reports/S6C/20260910T123540Z"
BASE = REPORT / "candidate_disposition"
IDS = {f"B{i:02d}" for i in range(40)} | {"B18_C1","B20_C1","B24_FREQUENT","B24_SPARSE"} | {f"C{i:03d}" for i in range(1,197)}
WORK_SHA = "5d84d493a377eb7b991e821cf59e412da5103ba7e17786e197bb2dd9c1ecc8dd"
CSV_SHA = "9147e73192001fabcd446e951856c958c3d090163e04f6a51cb59e2e24c23122"
PLAN_SHA = "f6b19c7070a266a775b13fac4464557910e70680c9c5f9efa58c8df67dc8980f"
STATUS_MAP = {
"PRESERVE_HISTORICAL_CONTROL":"HISTORICAL_CONTROL_PRESERVED",
"PRESERVE_DECLARED_ALIAS_UNEXECUTED":"EXACT_ALIAS_NOT_EXECUTED",
"KEEP_ADMISSION_LIMITED_DIAGNOSTIC":"ADMISSION_LIMITED_DIAGNOSTIC",
"FULL_ALL_SEEDS_DIAGNOSTIC":"ORACLE_OR_NULL_DIAGNOSTIC",
"PANEL_ALL_SEEDS_DIAGNOSTIC":"ORACLE_OR_NULL_DIAGNOSTIC",
"FULL_CAPACITY_OPPORTUNITY_LIMITED_CONTROL":"FULL_CONFIRMATION_TRADEOFF",
"FULL_COMMITMENT_NEIGHBORHOOD_TRADEOFF":"FULL_CONFIRMATION_TRADEOFF",
"FULL_CONDITIONAL_LATER_LABEL_TRADEOFF":"FULL_CONFIRMATION_TRADEOFF",
"FULL_STRUCTURAL_TRADEOFF_PENDING_OPERATING_SELECTION":"FULL_CONFIRMATION_TRADEOFF",
"FULL_MATCHED_ROSTER_DURATION_CONDITIONAL":"CONDITIONAL_ENROLLMENT_REFERENCE",
"FULL_NAMING_CONDITIONAL_PENDING_PACE":"CONDITIONAL_ENROLLMENT_REFERENCE",
"PANEL_NAMING_CONDITIONAL":"CONDITIONAL_ENROLLMENT_REFERENCE",
"KEEP_PANEL_COMPONENT_TRADEOFF":"PANEL_LIMITED_DIAGNOSTIC",
"NATIVE_CADENCE_DIAGNOSTIC_PENDING_PACE":"PANEL_LIMITED_DIAGNOSTIC",
"PANEL_COMMITMENT_NEIGHBORHOOD":"PANEL_LIMITED_DIAGNOSTIC",
"PANEL_ENDPOINT_FACTORIAL_WORD_TRADEOFF":"PANEL_LIMITED_DIAGNOSTIC",
"PANEL_SHORT_MATURE_COUPLING_DIAGNOSTIC":"PANEL_LIMITED_DIAGNOSTIC",
"PANEL_STRUCTURAL_MECHANISM_PENDING_BROADER_COVERAGE":"PANEL_LIMITED_DIAGNOSTIC",
"PANEL_TRADEOFF_FULL_CONFIRMATION_PENDING":"FULL_CONFIRMATION_TRADEOFF",
"FIXED_SPLIT_ROUTE_FULL_CONFIRMATION_PENDING":"FULL_CONFIRMATION_TRADEOFF",
}
LATER = {
"C067":("n03", "Completed full N03 retains unchanged final words and improves latest cp against C065, with worse first-display attribution, Unknown support and return behavior. The exact 3-second mature-evidence condition is a conditional tradeoff."),
"C072":("n08n10", "Completed full N08 hard-powerset post-policy confirmation retains every same-ASR C065 final transcript. First-display cp and Unknown improve; latest-cp direction differs by tap, inconsistent returns rise, and subsecond mapped-correct modal turns fall. Unchanged words do not establish identical state."),
"C074":("n08n10", "Completed full N10 modified-beam decoder confirmation changes words. Small complete-population word-error reductions coexist with additional insertions and a material O1 strict-empty regression; primary-word uncertainty includes zero. cp changes are not solely tracking effects."),
"C076":("n12", "Completed full N12 fixed endpoint-timing confirmation substantially improves first-display-label cp against C065. Complete latest cp improves by different amounts across taps; primary improvements coexist with complete-overlap latest-cp harms. Return/Unknown and whole-condition cost qualifications remain."),
"C085":("cross", "Completed full fixed ASR O0 / identity O1 route preserves all same-ASR C065 transcripts but increases complete latest cp by 22 errors. Scene benefits and harms coexist; each candidate has only its declared asymmetric route."),
"C086":("cross", "Completed full fixed ASR O1 / identity O0 route preserves all same-ASR C065 transcripts and reduces complete latest cp by 84 errors. It still exceeds B36 latest cp; scene harms remain. This is one fixed route, not a per-scene tap selector."),
}
REPRESENTATIVES = {"C067","C122","C088","C091","C076"}
CONTROLS = {"C065","C079","C117","C118","C121","B00","B01","B36"}
NAMING_FULL = {"C088","C091","C105","C106","C111","C114"} | {f"C{i:03d}" for i in range(141,147)}
TOKEN_IDS = {"B00","B01","B36","C065","C067","C072","C074","C076","C085","C086"}
STRATA_IDS = {"B00","B01","B36","C065","C067","C076","C079","C088","C091","C117","C118","C121","C122","C085","C086"}

def require(ok, message):
    if not ok: raise ValueError(message)

def pairs(items):
    out={}
    for k,v in items:
        require(k not in out, "Duplicate JSON key")
        out[k]=v
    return out

def parse(raw):
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2)+"\n").encode()

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def bind(path, raw):
    return dict(path=str(path.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def read_bound(b):
    p=Path(b["path"]).resolve()
    require(p.is_relative_to(SIM) and p.suffix.lower() in {".json",".md",".py",".csv"}, "Metadata/source path only")
    require(p.stat().st_size<=3*1024*1024, "Bounded small source only")
    raw=p.read_bytes()
    require(bind(p,raw)==dict(path=str(p),bytes=b["bytes"],sha256=b["sha256"]), "Exact source binding")
    return raw

def literal(tree,name):
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets):
            return ast.literal_eval(n.value)
    raise ValueError("Missing assembler literal "+name)

def row_decision(row):
    pid=row["candidate_id"];status=STATUS_MAP[row["proposed_working_disposition"]]
    interpretation=row["supported_interpretation"];limits=[row["remaining_empirical_gaps"]]
    refs=[];later=None
    if pid in LATER:
        later,interpretation=LATER[pid]
        refs=[later+"_interpretation",later+"_review",later+"_core",later+"_native"]
        limits=["Full offline confirmation is complete in the named authority; actual paced and continuous operating applicability remains unresolved here.",
                "No final dominance, per-scene route selection, hardware speed or phonetic/display-latency claim."]
        if pid in {"C085","C086"}:
            limits.append("Cross-summary cp_first_final is distinct from first-display-label cp; only the declared asymmetric route receives this evidence.")
    if row["family"]=="cue_authority":
        status="ORACLE_OR_NULL_DIAGNOSTIC"
        limits.append("N00 admission limitation still applies; nominal geometry is evaluator-derived and is not deployable cue evidence.")
    if pid in TOKEN_IDS:
        refs += ["token_result","diagnostic_review"]
        limits.append("Token positions are serialized-text diagnostics; overlap token alignment is not core MIMO scoring and does not identify reset or clipping causality.")
    if pid in STRATA_IDS:
        refs += ["strata_result","strata_interpretation","diagnostic_review"]
        limits.append("Strata dimensions overlap; descriptive adverse maxima are not independent failures or a selection ranking. Core strata do not score known names.")
    if pid in NAMING_FULL:
        refs += ["cold_warm_interpretation","cold_warm_review","naming_review"]
        interpretation += " The full-bank cold/warm query supplement is available: cold lifetime-track state is distinct from first identifiable reference-person exposure."
        limits.append("Cached policy queries are overlapping opportunities, not unique speech or actual paced observations; identifiable-only correct/wrong/unknown partitions exclude unidentifiable queries.")
    if pid.startswith("C") and 141<=int(pid[1:])<=146:
        refs += ["common_duration"]
        limits.append("Each common roster has 14 people (9 CMU + 5 HiFi), 28 combined. Estimated tier, whole-clip material, window count and template content change together.")
    runtime=["Later final inventory and requirement resolution must retain exact physical attempts, failures/reuse and closure separately from scores."]
    role="NO_OPERATING_SELECTION_PROPOSED"
    if pid in REPRESENTATIVES:
        role="CONDITIONAL_PACED_REPRESENTATIVE"
        runtime += ["Complete and review the exact registered main paced panel with repeats before REPRESENTATIVE_EVALUATED can be used.",
                    "If subsequently retained for operation, qualify this exact route/profile/gallery/cue condition in its own actual 30-60-minute continuous session."]
    elif pid in CONTROLS:
        role="MATCHED_OR_HISTORICAL_CONTROL"
        runtime += ["Review exact matched main paced coverage; control preparation or reuse does not select an operating fallback."]
    elif pid in {"C071","C082","C085","C086","C105"}:
        role="CONDITIONAL_BOUNDED_RUNTIME_DIAGNOSTIC"
        runtime += ["Review the separately declared gate, fixed cross-route or arrival-sensitive sentinel scope without promoting it to a full representative panel."]
    if pid=="C122": runtime += ["Retain exact cue-off C121, normalized C065/C079 and new-generation old-gate C117/C118 matched controls; C065 alone is not its cue parent."]
    if pid in {"C088","C091"}: runtime += ["Compare with identity.mode=none C065; exact roster/tier and source availability remain conditional."]
    if pid=="B36": runtime += ["Preserve original cross-generation full-pipeline comparison; fallback choice remains unresolved."]
    if pid in {"B36","C067","C088","C091"}:
        runtime += ["Prospective exact operating bundle is O0 ASR / O0 identity at this registered profile, cue and gallery setting; final selection requires its actual paced and continuous evidence."]
    if pid=="C067": runtime += ["Additional exact O0 fast_v2 continuous preparation is deferred until quiet release; no execution is claimed."]
    if pid in {"C083","C084"}:
        require(status=="EXACT_ALIAS_NOT_EXECUTED","Alias disposition")
        require(all(x["case_union_count"]==0 for x in parse(row["scored_scope_json"].encode())),"No propagated alias scores")
        refs=[];later=None;role="EXACT_ALIAS_ONLY"
        runtime=["No score, native or runtime credit may propagate from C065; preserve the declared omitted-alias-job authority."]
    return dict(candidate_id=pid, family=row["family"],registered_parent=row["registered_parent"],
        recipe_id=row["recipe_id"],registered_routes=parse(row["registered_routes"].encode()),
        working_row_sha256=digest(row),proposed_final_scientific_disposition=status,
        interpretation=interpretation,limitations=limits,
        inherited_evidence_references=parse(row["evidence_references_json"].encode()),
        later_interpretation_source_ids=sorted(set(refs)),later_full_authority_group=later,
        native_scope_update="SEPARATE_CLOSED_AUTHORITY_REFERENCE_ONLY" if later else "INHERIT_WORKING_EXPLICIT_AUTHORITY_SCOPE",
        physical_inference_count=None,runtime_role=role,runtime_dependencies=runtime,
        runtime_evidence_status="PENDING_OR_UNVERIFIED",evidence_ids=[],resolved=False)

def verify_decisions(ds,allowed):
    require(len(ds)==240 and {d["candidate_id"] for d in ds}==IDS,"Exact 240 IDs")
    require(len({d["candidate_id"] for d in ds})==240,"No duplicate IDs")
    require(all(d["proposed_final_scientific_disposition"] in allowed and not d["resolved"] for d in ds),"Unresolved exact assembler vocabulary")
    require(all(d["physical_inference_count"] is None and not d["evidence_ids"] for d in ds),"No manufactured physical count or final evidence graph")
    require(not any(d["proposed_final_scientific_disposition"]=="REPRESENTATIVE_EVALUATED" for d in ds),"No premature paced representative")
    require({d["candidate_id"] for d in ds if d["proposed_final_scientific_disposition"]=="EXACT_ALIAS_NOT_EXECUTED"}=={"C083","C084"},"Exact aliases")
    require({d["candidate_id"] for d in ds if d["runtime_role"]=="CONDITIONAL_PACED_REPRESENTATIVE"}==REPRESENTATIVES,"Conditional five representatives")
    require(next(d for d in ds if d["candidate_id"]=="C085")["registered_routes"]==[["O0","O1"]],"C085 route")
    require(next(d for d in ds if d["candidate_id"]=="C086")["registered_routes"]==[["O1","O0"]],"C086 route")

def run(plan_path,output):
    raw=Path(plan_path).read_bytes();plan=parse(raw);sources={}
    require(plan["schema"]=="s6c.provisional_decisions_source_plan.v1","Source plan")
    for key,b in plan["sources"].items(): sources[key]=read_bound(b)
    require(plan["sources"]["working_receipt"]["sha256"]==WORK_SHA and plan["sources"]["working_csv"]["sha256"]==CSV_SHA,"Original working pins")
    require(plan["sources"]["assembly_plan"]["sha256"]==PLAN_SHA,"Plan pin")
    work=parse(sources["working_receipt"])
    require(work["status"]=="COMPLETE_WORKING_PROPOSAL_ONLY","Working status")
    require(any(b["sha256"]==CSV_SHA for b in work["outputs"]),"Working output authority")
    reader=csv.DictReader(io.StringIO(sources["working_csv"].decode("utf-8-sig")))
    fields=reader.fieldnames;require(fields and len(fields)==len(set(fields)),"CSV columns")
    rows=list(reader);require(all(None not in r and None not in r.values() for r in rows),"Exact CSV row widths")
    require(len(rows)==240 and {r["candidate_id"] for r in rows}==IDS,"Working 240")
    require(all(r["physical_inference_count"]=="" for r in rows),"Working counts remain blank")
    tree=ast.parse(sources["assembler"].decode("utf-8-sig"))
    allowed=literal(tree,"SCIENTIFIC")
    require(literal(tree,"PLAN_SHA")==PLAN_SHA and literal(tree,"WORK_SHA")==WORK_SHA,"Actual assembler continuity")
    decisions=[row_decision(r) for r in rows];verify_decisions(decisions,allowed)
    require(all(k in sources for d in decisions for k in d["later_interpretation_source_ids"]),"Exact finite source references")
    # No native/source row projection occurs here. Final evidence must pass the separate assembler.
    overlay=dict(schema="s6c.provisional_candidate_decisions_overlay.v1",
        status="WORKING_PROPOSAL_NOT_READY_FOR_FINAL_ASSEMBLY",created_utc=datetime.now(timezone.utc).isoformat(),
        final_assembly_ready=False,whole_study_complete=False,operating_presets=[],requirement_resolution={"resolved":False},
        prospective_operating_dependencies=[
            dict(candidate_id="B36",asr_tap="O0",identity_tap="O0",role="POSSIBLE_HISTORICAL_FALLBACK",selected=False),
            dict(candidate_id="C067",asr_tap="O0",identity_tap="O0",role="POSSIBLE_LATEST_ATTRIBUTION_TRADEOFF",selected=False),
            dict(candidate_id="C088",asr_tap="O0",identity_tap="O0",role="POSSIBLE_FIXED_A15_NAMING",selected=False),
            dict(candidate_id="C091",asr_tap="O0",identity_tap="O0",role="POSSIBLE_FIXED_B15_NAMING",selected=False)],
        candidate_count=240,historical_count=44,c_candidate_count=196,
        source_plan=bind(Path(plan_path),raw),sources=plan["sources"],candidate_decisions=decisions,
        population_and_metric_limits=[
            "Full complete nonempty: 203 scenes/6016 words/693 turns/292 return groups per route; incomplete26 and strict-empty11 remain separate.",
            "Complete inherited word errors combine primary serialized WER and complete-overlap MIMO; token overlap diagnostics use a separate serialized alignment.",
            "First-display-label cp uses final words and first shown labels, not partial transcript WER. Cross prose cp_first_final is a different field.",
            "O0/O1 share captures; per-authority full support cannot be constructed by unions or duplicate pooling.",
            "No current paced/long outcome is read or certified by this overlay. Stored working fields remain historical snapshots."
        ],
        merge_instructions=[
            "Join only by exact candidate_id onto the unchanged 240 working rows; preserve every original column.",
            "Use proposed_final_scientific_disposition as a proposal for scientific_disposition; keep resolved false until root accepts exact final evidence and limitations.",
            "Resolve inherited and later source references into candidate/route-specific resources and evidence records using the separate assembler guards.",
            "Interpretation-source IDs are not assembler evidence_ids. Do not directly substitute them or fabricate row projections.",
            "Resolve exact physical/paced/long evidence, mandatory requirements and 2-4 exact operating bundles separately. No automatic fallback or NOT_SELECTED_FOR_OPERATION decision is made here.",
            "The separate final input must remain unresolved until all guards pass; this overlay is deliberately not a final-assembler input schema."
        ])
    out=Path(output).resolve()
    require(out.is_relative_to(BASE) and out!=BASE and not out.exists(),"Fresh contained output namespace")
    out.mkdir(parents=True)
    outputs=[]
    def write(name,data):
        p=out/name
        with p.open("xb") as f:f.write(data)
        outputs.append(bind(p,data))
    write("CANDIDATE_DECISIONS_PROVISIONAL.json",encoded(overlay))
    write("WORKING_ROWS_UNCHANGED.csv",sources["working_csv"])
    counts=Counter(d["proposed_final_scientific_disposition"] for d in decisions)
    text=["# Provisional candidate decisions","",
        "This source-bound reporting overlay retains all 240 exact IDs and every original working row. It updates completed offline conclusions without finalizing scientific selection, runtime qualification or operating presets.","",
        "N03, N08/N10, N12 and both fixed cross routes are complete in their named offline authorities. Their score and native references remain separate. The older working CSV is an immutable snapshot; stale pending-full wording there is superseded only by the corresponding overlay row.","",
        "| Proposed assembler disposition | IDs |","|---|---:|"]
    text += [f"| {k} | {v} |" for k,v in sorted(counts.items())]
    text += ["","C067, C122, C088, C091 and C076 are conditional paced representatives. None is marked REPRESENTATIVE_EVALUATED. C065, C079, C117/C118, C121 and historical B00/B01/B36 serve distinct control roles. C065 is not automatically an operating fallback; B36 remains a whole-pipeline comparator.",
        "","Four prospective exact operating dependencies are B36 O0/O0 historical fallback, C067 O0/O0 latest-attribution tradeoff and C088/C091 O0/O0 fixed A15/B15 naming conditions. None is selected. Each requires its own actual paced/continuous qualification. C067 long preparation is deferred; C065 O0 remains a required no-gallery/control long. C122 need not become an operating preset to retain its scientific evidence.",
        "","C083/C084 remain unexecuted exact aliases with no propagated score/native/runtime credit. C085 and C086 each retain one asymmetric route. C143/C146 retain separate intended-roster semantics even where gallery bytes match a 30-second anchor.",
        "","Admission-limited N00, unactivated mechanisms, panel-only families, all null seeds/nominal controls, calibrated galleries and scene-conditioned rosters retain their original limitations. Completed token/strata/cold-warm supplements add interpretation, not new experiments or native counts.",
        "","The JSON has per-ID interpretations, limitations, current proposal, unchanged-row fingerprint, inherited and later source references, and unresolved runtime dependencies. WORKING_ROWS_UNCHANGED.csv is an exact byte copy of the prior working file. Follow merge_instructions; the final assembler must independently admit its resources/evidence and final 2-4 operating bundles. This overlay cannot be passed directly to final assembly."]
    write("EXPLANATION.md",("\n".join(text)+"\n").encode())
    receipt=dict(schema="s6c.provisional_decisions_receipt.v1",status="COMPLETE_PROVISIONAL_OVERLAY_ONLY",
        source_plan=bind(Path(plan_path),raw),source=bind(Path(__file__),Path(__file__).read_bytes()),
        readme=bind(Path(__file__).with_name("README_S6C_CANDIDATE_DECISIONS_OVERLAY_V1.md"),Path(__file__).with_name("README_S6C_CANDIDATE_DECISIONS_OVERLAY_V1.md").read_bytes()),
        outputs=outputs,counts=dict(counts),candidate_count=240,rows_preserved=240,
        byte_identical_working_csv=outputs[1]["sha256"]==CSV_SHA,
        final_ready=False,all_decisions_unresolved=True,model_calls=0,scorer_runs=0,
        source_reads="Finite explicit metadata/source buffers only; no transitive scan, predictions, raw logs, audio, assets, or runtime results.",
        validation="Actual assembler vocabulary/pins; exact240 IDs, routes and alias restrictions; fresh namespace; immutable input hashes; all interpretation IDs resolve.")
    p=out/"RECEIPT.json";p.write_bytes(encoded(receipt));return bind(p,p.read_bytes())

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source-plan",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();print(json.dumps(run(a.source_plan,a.output),indent=2))
