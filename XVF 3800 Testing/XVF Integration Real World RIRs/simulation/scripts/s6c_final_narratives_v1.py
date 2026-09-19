"""Prepare final narrative copies; see the adjacent README."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
S = Path(__file__).resolve().parent
R = S.parent / "reports/S6C/20260910T123540Z"
D = R / "handoff_drafts"
O = R / "handoff_final_v1"
def bind(p):
    p = Path(p).resolve(); b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
def edit(t, a, b):
    if t.count(a) != 1: raise ValueError("Missing/nonunique anchor: "+a[:90])
    return t.replace(a,b,1)
def para(t, prefix, new):
    p=t.split("\n\n"); ids=[i for i,x in enumerate(p) if x.startswith(prefix)]
    if len(ids)!=1: raise ValueError("Missing/nonunique paragraph: "+prefix)
    p[ids[0]]=new
    return "\n\n".join(p)
def intro(t,new):
    p=t.split("\n\n"); assert p[0].startswith("# ")
    p[1]=new
    return "\n\n".join(p)
RUNTIME = """All596 paced cells have completed native execution, actual analysis, metadata normalization and64 separate-repetition core/name score commands:520 main-panel,24 cadence,12 arrival and40 cross cells. The13 main conditions each have16 first-repetition scenes and four repeats per output. Appropriate native/shared parity passed for556 cells; B00's40 controls retain exact original native-event attribution with shared/vector parity unavailable.

Five further uninterrupted host sessions completed on September12 at16:40:58 UTC: C065 O0/NONE control, C067 O0/NONE, C088 O0/originalA15, C091 O0/originalB15 and historical B36 O0/NONE. Each consumed1,827.426625 source seconds (30min27.426625sec) from38 prior captures with74 seconds of inserted silence. All five original parent exits were0; full source cursors, journals, tail/drain and scheduler closure were observed. These are five dependent-input host sessions, not continuous hidden XVF state or additional physical-XVF captures."""
TIMING = """On the16-scene O0 first-repetition panels, partial-event source-cursor lag p50/p95 was0.180/0.331s for B36,0.375/0.695s for C065,0.585/1.210s for C067,2.767/6.112s for C088 and2.437/4.812s for C091 (377 partial emissions per condition). This is emitted-event lag, not phonetic or GUI latency. Long-session sampled RSS maxima ranged from466.0 to549.9MiB, with observation gaps of51.2–63.3s. C event-consumer queue peaks were2,697–3,405 events; terminal scheduler pending counts and recorded audio-drop counters were zero. Sparse samples do not establish continuous worst-case memory, absence of leaks or CM5 suitability. RUNTIME_RESULTS.md preserves clocks, denominators and generation-specific instrumentation."""
SELECT = """The four retained research conditions are historical B36 O0/NONE as fallback, C067 O0/NONE when later revised anonymous attribution is the priority, and C088 O0/originalA15 plus C091 O0/originalB15 for controlled naming with the exact predefined rosters. C065 remains the matched anonymous control. Each retained complete condition has its own main paced and continuous evidence. None is a universal winner, an untested mixture or a new production default. Enrollment improves some correct-name support while allowing false-known exposure and materially longer observed output delays. See OPERATING_ENVELOPES.md and OPERATING_COMMANDS.md."""
CENSUS = """The fresh final machine census observed5,891 physical attempts:5,289 legacy and602 fast. Row statuses are5,889 COMPLETE, one STARTED without a confirmed session, and one failed outer C065 attempt whose native body completed. Thus5,890 observed native-body completions are not5,890 accepted attempts. The fast scope is596 accepted paced cells, five accepted long sessions and that failed C065 attempt. All5,284 prior native-index bindings were found; six late pools have zero coverage gaps. All7,411 concrete owner observations are closed. One virtual failed-C065 observer flag remains unverified with no recorded identity. Preserve the original INCOMPLETE_WITH_FLAGS/CLOSURE_UNVERIFIED inventory labels and unknown historical exits. Acceptance of completed successful scope does not rewrite failed-attempt facts."""
FAILURE = """The first C065 attempt processed one44.6954375-second source and produced a COMPLETE native body before its outer integrity check failed, contributing zero accepted paced cells. A model-free reproduction exposed the unstable marshal-based guard; a separately reviewed structural guard supported the later successful generation. Original dispatcher telemetry failures, unknown orphan exits, and the controls cross-volume lease archive failure remain preserved. The separately reviewed exact-byte controls lease recovery added zero native sessions. See RUNTIME_REPAIRS_AND_EVIDENCE_CONTINUITY.md."""
def main():
    if O.exists(): raise FileExistsError(O)
    invp=R/"execution_inventory/final_whole_study_v1_fast/EXECUTION_INVENTORY.json"
    inv=json.loads(invp.read_bytes())
    assert inv["unique_physical_attempts_observed"]==5891
    assert inv["summary"]["status_counts"]=={"COMPLETE":5889,"STARTED":1,"FAILED_OUTER_NATIVE_COMPLETE_PROTECTION_UNVERIFIED":1}
    lp=R/"fast_post_analysis/five_long_actual_v1/COMPACT_LONG_OBSERVATIONS_V1.json"
    rows=json.loads(lp.read_bytes())["rows"]
    assert len(rows)==5 and all(x["owner_closed"] and x["tail_complete"] for x in rows)
    names=["S6C_JOINT_REPORT.md","WORKBOOK_UPDATE.md","NEXT_STAGE_INPUTS.md","RUN_RESUME_README.md","OPERATING_ENVELOPES.md","RUNTIME_RESULTS.md","PIPELINE_EXECUTION_MAP.md","CUE_AUTHORITY_FINDINGS.md","ENROLLMENT_RESULTS.md","METRIC_READING_GUIDE.md","RECIPE_IDENTIFIER_GUIDE.md","TOKEN_BOUNDARY_AND_STRATA_RESULTS.md","TRACK_AND_GALLERY_EXPLAINER.md"]
    docs={n:(D/n).read_text(encoding="utf-8") for n in names}
    introductions={
      "S6C_JOINT_REPORT.md":"Completed offline findings and runtime observations, with explicit limitations. Final package acceptance is recorded separately in its bound acceptance receipt. Four conditional research conditions are retained without promoting a production default.",
      "WORKBOOK_UPDATE.md":"Completed-results insertion text for review and yellow highlighting in XVF_Measurement_V17.docx or the user's later edited master. The original Word workbook has not been overwritten. Use the final acceptance and exact execution/disposition tables with this interpretation.",
      "NEXT_STAGE_INPUTS.md":"Use the completed S6C findings, acceptance and exact coverage tables for the next planning discussion. Four conditional research conditions are retained; this document does not start S6D or change the application default.",
      "RUN_RESUME_README.md":"Instructions for completed S6C evidence and optional reproduction. The original native queues,596 paced cells and five continuous sessions are closed; do not rerun them to read the handoff. C065 below is the matched empty-gallery control. Exact retained-condition commands are in OPERATING_COMMANDS.md.",
      "OPERATING_ENVELOPES.md":"Root retains the four exact conditions below after their own main paced and uninterrupted host sessions completed. These are conditional research operating/fallback selections. Final disposition and package acceptance supply the exact bindings; no production default or hardware qualification is promoted.",
      "RUNTIME_RESULTS.md":"Actual runtime observations are complete. Retained-condition selection and final acceptance are bound separately. These results establish complete saved-input delivery and process/scheduler closure for admitted conditions; accuracy, useful response time and hardware suitability remain separate judgments.",
      "PIPELINE_EXECUTION_MAP.md":"Execution paths for the completed S6C offline study. Final execution/disposition tables distinguish implementation, actual native work, cache reuse, policy replay and diagnostics.",
      "CUE_AUTHORITY_FINDINGS.md":"The carried physical audit, full anonymous comparison, three-seed/nominal comparisons, endpoint-advice execution and paced cadence diagnostic are complete. This does not establish a spatial accuracy specification or force a spatial operating recommendation.",
      "ENROLLMENT_RESULTS.md":"Source preparation, native templates, panel/full-bank naming, fixed-roster duration,408 gallery-bearing native integration cells and declared paced/continuous conditions are complete. Native/cached attribution differences remain visible. Actual emitted-name timing is separate in PACED_NATIVE_RESULTS.md. Continuous lexical/name correctness is unavailable, not inferred from event counts.",
      "METRIC_READING_GUIDE.md":"Completed result receipts and their specific populations govern numerical claims. This guide keeps metric units, populations, clocks and missing observations separate.",
      "TOKEN_BOUNDARY_AND_STRATA_RESULTS.md":"Completed offline diagnostics. They do not themselves establish timed operation or an operating preset; separate actual runtime and disposition evidence supply those scopes.",
      "TRACK_AND_GALLERY_EXPLAINER.md":"Explanation of the implemented and exercised system. Examples explain mechanisms; measured tradeoffs and retained conditions are in the joint report and operating envelopes."
    }
    for n,t in introductions.items(): docs[n]=intro(docs[n],t)
    changes={
      "S6C_JOINT_REPORT.md":[
        ("but genuine uninterrupted native host runs remain required for retained profiles.","and five uninterrupted native host sessions are now complete, with their measured scope reported below."),
        ("C076 is retained as a fifth scientific paced representative, with operating selection still pending.","C076 remains a completed scientific paced representative outside the four retained operating conditions."),
        ("runtime synthesis is in progress.","PACED_NATIVE_RESULTS.md supplies the actual repeated-panel synthesis."),
        ("## Confirmation and acceptance still to resolve","## Completed confirmation and its boundaries"),
        ("The final interpretation must combine","The final interpretation combines"),
        ("Source-paced panel and 30–60-minute host sessions will determine runtime acceptance of the final retained conditions.","The completed source-paced panel and five continuous sessions provide runtime observations; source completion is not a response-time guarantee."),
        ("## Scope of the eventual result","## Scope of the result"),
        ("WORKBOOK_UPDATE.md will supply insertion text after acceptance and independent review.","WORKBOOK_UPDATE.md supplies insertion text for review; the original workbook remains unchanged."),
        ("No continuous 30–60-minute runtime proof exists yet; five original prepared sessions remain required.","Five original continuous sessions and their diagnostics have since completed, as summarized below."),
        ("No final operating preset or study completion is claimed.","Those failures remain excluded from accepted coverage; retained conditions use their exact later successful evidence.")],
      "WORKBOOK_UPDATE.md":[
        ("as of this draft","in this invocation"),
        ("Final execution counts will come from the closed machine inventory.","Final counts and preserved exceptions are summarized below from the fresh machine census."),
        ("Cross-routing and paced/endurance evidence remain pending before operating choices.","Cross-routing and paced/continuous evidence are complete and reported below; neither candidate becomes an operating preset."),
        ("C076 remains a fifth scientific paced representative, pending runtime acceptance and any operating selection.","C076 remains a completed scientific paced representative outside the four retained operating conditions."),
        ("Actual paced naming timing still requires the pending runtime tests.","Actual paced naming timing is separate in PACED_NATIVE_RESULTS.md and RUNTIME_RESULTS.md."),
        ("A separately declared 12-cell source-paced sentinel is prepared for this scene; its empirical repeat results remain pending and do not replace the main balanced runtime panel.","The separately declared12-cell source-paced sentinel has completed actual analysis and three separately scored repetitions; it does not replace the main balanced runtime panel."),
        ("## Required completion insertions","## Completed runtime and operating interpretation")],
      "NEXT_STAGE_INPUTS.md":[("WORKBOOK_UPDATE.md will provide reviewed insertion text and captions","WORKBOOK_UPDATE.md provides insertion text and captions for review")],
      "RUN_RESUME_README.md":[("The final selected profile/gallery/telemetry commands will be inserted in OPERATING_ENVELOPES.md after selection and paced acceptance. The example above does not substitute for those results.","OPERATING_COMMANDS.md binds the four retained complete conditions and explicit invocations. OPERATING_ENVELOPES.md states their measured tradeoffs; this C065 control example is not a substitute.")],
      "OPERATING_ENVELOPES.md":[
        ("# Operating envelopes: conditional draft","# Four retained research operating conditions"),
        ("All prospective routes","All retained routes"),("| Potential use |","| Retained use |"),
        ("Its continuous control session remains required even if it is not retained as an operating preset.","Its continuous control session completed and remains evidence although it is not an operating preset."),
        ("Actual paced emissions are needed to describe display behavior.","Actual paced emissions describe display behavior separately in PACED_NATIVE_RESULTS.md and RUNTIME_RESULTS.md.")],
      "RUNTIME_RESULTS.md":[
        ("The required paced grid contains596 completed cells:","The completed paced grid contains596 cells, including additional scientific diagnostics:"),
        ("C model startup is separately recorded","C resource counts include the terminal observation. B36's586 are periodic resource observations; its separate child-exit terminal record contains no resource sample. C model startup is separately recorded")],
      "PIPELINE_EXECUTION_MAP.md":[("The separate prepared runtime panel","The separately executed runtime panel")],
      "CUE_AUTHORITY_FINDINGS.md":[
        ("The prepared paced C071/C082 diagnostic will measure released\ncontext, debt and runtime behavior at source speed.","The completed paced C071/C082 diagnostic records released\ncontext, debt and runtime behavior at source speed; its24cells retain their own scope."),
        ("The final artifact index will bind","The local artifact index binds"),
        ("Paced receipts remain pending actual execution.","Actual paced receipts are bound in fast_post_analysis/remaining116_actual_v1 and paced_scoring/remaining116_actual_v1; no direct-trigger efficacy is inferred from pacing.")],
      "TRACK_AND_GALLERY_EXPLAINER.md":[("Actual paced/continuous process memory remains a separate pending measurement.","Actual paced/continuous process memory is separate in RUNTIME_RESULTS.md, with observed sample counts and gaps.")]
    }
    for n,pairs in changes.items():
        for a,b in pairs: docs[n]=edit(docs[n],a,b)
    docs["WORKBOOK_UPDATE.md"]=para(docs["WORKBOOK_UPDATE.md"],"The completed full N03, N08, N10 and N12 tradeoffs are recorded above.",RUNTIME)
    docs["WORKBOOK_UPDATE.md"]=para(docs["WORKBOOK_UPDATE.md"],"Report new native calls, verified reuse",SELECT+"\n\n"+TIMING+"\n\n"+CENSUS)
    docs["WORKBOOK_UPDATE.md"]=para(docs["WORKBOOK_UPDATE.md"],"The timed-runtime queue is declared but incomplete.",FAILURE)
    docs["OPERATING_ENVELOPES.md"]=para(docs["OPERATING_ENVELOPES.md"],"Finalization checklist for this document:","Activation commands and effective profile/gallery/source bindings are in OPERATING_COMMANDS.md. Each retained condition uses its own admitted paced and long evidence. C065 remains the matched control; unselected methods retain positive and negative findings.")
    docs["S6C_JOINT_REPORT.md"]+="\n\n## Completed runtime, retained conditions and accounting\n\n"+RUNTIME+"\n\n"+TIMING+"\n\n"+SELECT+"\n\n"+CENSUS
    docs["PIPELINE_EXECUTION_MAP.md"]+="\n\n## Final accounting boundary\n\n"+RUNTIME+"\n\n"+CENSUS
    docs["OPERATING_ENVELOPES.md"]+="\n\n## Measured runtime limits\n\n"+TIMING+"\n\nThe enrolled conditions are research options where delayed updates and abstention are acceptable. Their observed delays do not support a low-latency live naming recommendation. Unsupported identity should remain Unknown or anonymous. Galleries A and B are separate predefined conditions, not alternatives selected using a speaker's ground truth."
    O.mkdir()
    for n,t in docs.items(): (O/n).write_text(t.rstrip()+"\n",encoding="utf-8",newline="\n")
    rec=dict(schema="s6c-final-narrative-preparation.v1",status="COMPLETE_NARRATIVE_PREPARATION_PENDING_INDEPENDENT_ACCEPTANCE",created_utc=datetime.now(timezone.utc).isoformat(),inputs=[bind(D/n) for n in names],actual_authorities=[bind(invp),bind(lp)],outputs=[bind(O/n) for n in names],helper=bind(__file__),readme=bind(S/"README_S6C_FINAL_NARRATIVES_V1.md"),whole_study_complete=False,scope="Narrative preparation only; no inference, scores, physical rows, Word editing or campaign acceptance.")
    p=O/"NARRATIVE_PREPARATION_RECEIPT.json";p.write_text(json.dumps(rec,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(status=rec["status"],documents=len(docs),receipt=bind(p))))
if __name__=="__main__": main()

