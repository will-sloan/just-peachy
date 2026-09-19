"""Build the S6B design contract and challenge set; see README_S6B_DESIGN.md.

This standard-library-only builder reads immutable S6A evidence and scene
metadata. It never imports the application, opens audio, or runs a model.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_SIM = Path(__file__).resolve().parents[1]
RUN = "20260909T230840Z"
S6A_RUN = "20260909T202250Z"
KNOWN_HASHES = {
    "bank": "69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18",
    "rir": "468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546",
    "panel": "be1a48ce8e2c0bec2b9f064b763b8f9b833b7413c005998cf531c882d53d28b2",
    "short": "859d3923b56c9d611aad4550a937f620da043342d79f66b1a3bd92bb48d4a329",
}
# ID, title, family, mode, recipe family, parent, cue route, type, new mechanism
METHODS = [
("B00","Exact original B0","controls","historical","R0",None,"none","control",None),
("B01","Common voice and time","voice_memory","voice","R0","B36","none","main",None),
("B02","Folded angle diagnostic","simple_spatial","angle","R0","B01","tracking_only","main",None),
("B03","Sustained direction change","simple_spatial","sustained","R0","B01","tracking_only","main",None),
("B04","Decaying location memory","simple_spatial","decay","R0","B01","tracking_only","main",None),
("B05","Reliability weighted spatial credit","simple_spatial","adaptive","R0","B01","tracking_only","main",None),
("B06","Static spatial fusion","simple_spatial","static","R0","B01","tracking_only","main",None),
("B07","Accumulated direction innovation","uncertainty","innovation","R0","B01","tracking_only","main",None),
("B08","Uncertain folded bearing","uncertainty","folded","R0","B01","tracking_only","main",None),
("B09","Dual memory and dormant voice reentry","voice_memory","dual_memory","R0","B01","none","main",None),
("B10","Dual memory with spatial credit","voice_memory","dual_memory","R0","B09","tracking_only","companion",None),
("B11","Bounded multiple voice prototypes","voice_memory","multiprototype","R0","B01","none","main",None),
("B12","Quarantined prototype and rollback","voice_memory","quarantine","R0","B01","none","main",None),
("B13","Tempered voice hypothesis beam","temporal_assignment","bayes","R0","B01","none","main",None),
("B14","Tempered beam with spatial credit","temporal_assignment","bayes","R0","B13","tracking_only","companion",None),
("B15","Bounded arrived-node revision graph","temporal_assignment","delay_graph","R0","B01","none","main","N07"),
("B16","Tuned component voice bundle","component_evidence","voice","R1","B01","none","main",None),
("B17","Tuned bundle with spatial credit","component_evidence","adaptive","R1","B16","tracking_only","companion",None),
("B18","Short clean posterior-gated evidence","component_evidence","voice","R2","B01","none","main",None),
("B19","Posterior short evidence with gate-only purity","component_evidence","voice","R2","B18","none","companion",None),
("B20","Long clean posterior-gated evidence","component_evidence","voice","R3","B18","none","main",None),
("B21","Hard-policy short evidence with fractional purity","component_evidence","voice","R2","B18","none","companion",None),
("B22","Faster endpoint and dispatch voice route","asr_orchestration","voice","R4","B01","none","main",None),
("B23","Protected endpoint advice only","asr_orchestration","voice","R0","B01","endpoint_only","main","N04"),
("B24","Voice evidence debt and observation floor","resource_adaptive","voice","R5","B01","none","main","N05"),
("B25","Spatial event debt with matched voice floor","resource_adaptive","adaptive","R5","B24","tracking_only","companion","N05"),
("B26","Lower gain with dispatch RMS","level_gate","voice","R6","B01","none","main",None),
("B27","Lower gain with full-window RMS","level_gate","voice","R6","B26","none","companion",None),
("B28","Bounded beam decoding and 50ms dispatch","asr_orchestration","voice","R7","B22","none","main",None),
("B29","Posterior coarse-stride short evidence","component_evidence","voice","R0","B01","none","companion",None),
("B30","Bounded duration-state hypothesis filter","temporal_assignment","hsmm","R0","B13","none","main",None),
("B31","Bounded acoustic-group assignment beam","temporal_assignment","global_assignment","R0","B13","none","main",None),
("B32","Sensor contradiction quarantine","uncertainty","adaptive","R0","B05","tracking_only","main","N01"),
("B33","Disjoint confirmation for cue-assisted updates","voice_memory","adaptive","R0","B05","tracking_only","main","N03"),
("B34","Early short evidence and later long confirmation","component_evidence","voice","R3","B20","none","main",None),
("B35","Full-window RMS on baseline gain","level_gate","voice","R0","B01","none","main",None),
("B36","Original tracker under common scheduler","controls","original_common","R0","B00","none","control",None),
("B37","One anonymous person for all","controls","one_person","R0","B36","none","control",None),
("B38","All identities unknown","controls","all_unknown","R0","B36","none","control",None),
("B39","Protected endpoint advice and spatial tracking","asr_orchestration","adaptive","R0","B23","both","companion","N04"),
]
MECHANISMS = {
"historical": ("Read immutable B0 first-output results without replacing their scheduler.", "Historical delivery differences confound a new-policy comparison; use B36 as the scheduler control."),
"voice": ("Associate normalized voice vectors by cosine margin; admit unique evidence and two disjoint observations before maturity.", "Voice ambiguity or missed embeddings produce unknown labels; no spatial rescue is available."),
"angle": ("Use arrived qualified folded bearing as a restricted anonymous association diagnostic, with shared audio eligibility.", "Same/folded bearings cannot establish identity; low unknown fraction alone is not success."),
"sustained": ("Require qualified direction evidence sustained across observed packets before using a location-change proposal.", "Sparse packets do not prove continuous physical direction; voice must protect against wrong-stable cues."),
"decay": ("Exponentially decay location credit with source observation age independently of voice memory.", "Fast decay can miss returns; slow decay can retain an obsolete seat."),
"adaptive": ("Bound spatial association credit by fresh observation reliability and audio compatibility.", "Telemetry usable does not imply correct expected sector; correlated wrong cues can reinforce errors."),
"static": ("Add bounded fixed spatial compatibility credit after common fresh-cue eligibility.", "Fixed credit ignores changing reliability and can worsen wrong-stable or same-angle cases."),
"innovation": ("Accumulate decayed above-drift direction residuals and propose a change only after threshold.", "Correlated nuisance excursions may accumulate into a false change; inspect resets and stale handling."),
"folded": ("Score a linear 0..180 bearing likelihood with explicit uncertainty rather than wrapping endpoints.", "Broad uncertainty reduces discrimination; front/rear ambiguity is irreducible without another observation."),
"dual_memory": ("Maintain slower voice and faster location state; permit dormant reentry from strong voice support.", "A stale prototype can reidentify incorrectly after long gaps; no known speaker identity enters state."),
"multiprototype": ("Retain a bounded set of clean voice prototypes and admit novelty only above quality thresholds.", "More prototypes can increase accidental similarity; caps and contamination accounting matter."),
"quarantine": ("Hold a proposed voice-prototype update and retain a rollback version until independent later evidence validates it.", "Repeated overlapping vectors are not independent confirmation; rollback must not rewrite first output."),
"bayes": ("Maintain a finite beam of tempered association hypotheses with continuity costs.", "Scores are heuristic engineering weights, not calibrated identity posterior probabilities."),
"hsmm": ("Extend bounded hypotheses with duration bins and turn-switch penalties.", "Duration priors can suppress short turns; duration-state scores are not calibrated probabilities."),
"global_assignment": ("Jointly score a bounded beam of recent acoustic microgroups against tracks, allowing sequential same-person groups.", "Do not impose an invalid one-to-one matching across sequential observations; group errors can propagate."),
"delay_graph": ("Run bounded arrived-node path revision, with explicit age and edit-count limits and forward lineage events.", "Revised identity must remain separate from first-display identity; delayed revisions cannot earn earlier credit."),
"original_common": ("Replay unchanged original association semantics under the shared causal arrival scheduler.", "Native historical B0 remains a separate control; scheduling improvements cannot be called a tracking-method gain."),
"one_person": ("Assign a single anonymous identity to all available speech output.", "Never interpret fewer unknowns as correct identity; count mixed-person sole-active support."),
"all_unknown": ("Keep all identity output unknown while retaining recognized text.", "Undefined identity mapping must remain explicit; word coverage is still scored."),
}

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
def binding(path):
    p=Path(path); raw=p.read_bytes()
    return {"path":str(p.resolve()),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
def dump(path,data):
    Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
def rows(path):
    with Path(path).open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))
def write_csv(path, data):
    if not data: raise ValueError("cannot infer empty CSV columns")
    with Path(path).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader()
        for r in data: w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def utterances(scene):
    return [(i,x) for i,x in enumerate(scene["segments"]) if x.get("kind")=="utterance"]
def duration(scene,segment):
    n=segment["source_stop_sample"]-segment["source_start_sample"]
    if n<=0 or scene["sample_rate_hz"]<=0: raise ValueError("invalid source clip span")
    return n/scene["sample_rate_hz"]
def instance(scene,i,u):
    return {"instance_id":f'{scene["case_id"]}:segment:{i}',"case_id":scene["case_id"],"segment_index":i,
            "source_id":u["source_id"],"participant_id":u["participant_id"],"speaker_key":u["speaker_key"],
            "utterance_label":u.get("utterance_label"),"source_start_sample":u["source_start_sample"],
            "source_stop_sample":u["source_stop_sample"],"sample_rate_hz":scene["sample_rate_hz"],
            "duration_sec":duration(scene,u),"whole_clip":u.get("whole_clip"),"rir_id":u["rir_id"],
            "reference_only":True}
def conditions(scene,population,geometry):
    tags={f'family:{scene["family_id"]}',f'population:{population}',f'split:{scene["split"]}'}
    for k,v in scene["receiver_configuration"].items(): tags.add(f"receiver:{k}={v}")
    turns=utterances(scene)
    for _,u in turns:
        d=duration(scene,u);tags.add("duration:" + ("<1" if d<1 else "1-2" if d<2 else ">=2"))
        for key,label in [("dataset","corpus"),("quality_partition","quality"),("relative_source_db","source_db")]:
            if key in u: tags.add(f"{label}:{u[key]}")
    noise_values=scene.get("noise_details") or []
    if isinstance(noise_values,dict):noise_values=[noise_values]
    for noise in noise_values:
        if isinstance(noise,dict):
            for k in ("noise_class","category","kind"):
                if noise.get(k):tags.add("noise:"+str(noise[k]))
    # Family tags are metadata strata, not measured outcomes or telemetry validation.
    special={"F02":"return","F03":"short_and_rapid_handoff","F04":"overlap","F05":"folded_spatial_design",
             "F06":"silent_relocation_long_return","F10":"localized_nonspeech","F11":"ambience","F12":"empty_and_noise"}
    if scene["family_id"] in special:tags.add("design_condition:"+special[scene["family_id"]])
    byperson=defaultdict(list)
    for _,u in turns:
        g=geometry[u["rir_id"]]; a=float(g["speaker_angle_deg_effective"])
        # Linear-array projected-bearing ambiguity: theta and 180-theta share sin(azimuth).
        # Stored nominal lab angles are not verified native XVF coordinates.
        byperson[u["participant_id"]].append((a,u["rir_id"]))
    if any(len(set(r for _,r in values))>1 for values in byperson.values()):
        tags.add("geometry:same_participant_multiple_rirs")
    pairs=[]
    people=sorted(byperson)
    for n,p in enumerate(people):
        for q in people[n+1:]:
            for a,_ in byperson[p]:
                for z,_ in byperson[q]:
                    delta=abs((a-z+180)%360-180)
                    folded=abs(math.sin(math.radians(a))-math.sin(math.radians(z)))
                    if delta<=10: tags.add("geometry:distinct_participants_nominal_same_angle")
                    if folded<=.05 and delta>10: tags.add("geometry:distinct_participants_nominal_folded_ambiguity")
                    pairs.append((delta,folded))
    return tags

def challenge(scenes,population,panel,geometry):
    sc={x["case_id"]:x for x in scenes}
    if len(sc)!=len(scenes) or set(sc)!=set(population): raise ValueError("scene/population coverage mismatch")
    if len(panel)!=len(set(panel)) or not set(panel)<=set(sc):raise ValueError("invalid inherited panel")
    shorts=[instance(s,i,u) for s in scenes if population[s["case_id"]] in ("primary_nonoverlap","overlap_complete")
            for i,u in utterances(s) if duration(s,u)<1]
    selected=set(panel)|{x["case_id"] for x in shorts}
    alltags={cid:conditions(s,population[cid],geometry) for cid,s in sc.items()}
    # Deterministically add only a missing available condition, never using model outcomes.
    available=set().union(*alltags.values()); covered=set().union(*(alltags[c] for c in selected))
    additions=[]
    while available-covered:
        candidates=[c for c in sc if c not in selected]
        ranked=sorted(candidates,key=lambda c:(-len(alltags[c]-covered),c))
        best=ranked[0]
        if not alltags[best]-covered:raise ValueError("uncoverable available condition")
        additions.append({"case_id":best,"reason":"missing available metadata condition","new_conditions":sorted(alltags[best]-covered)})
        selected.add(best);covered|=alltags[best]
    shortcounts=Counter(x["case_id"] for x in shorts)
    outrows=[]
    for cid in sorted(selected):
        why=[]
        if cid in panel:why.append("inherited_S6A_36")
        if shortcounts[cid]:why.append("complete_reference_subsecond_instance")
        if cid in {x["case_id"] for x in additions}:why.append("metadata_coverage_augmentation")
        outrows.append({"case_id":cid,"population":population[cid],"family_id":sc[cid]["family_id"],
                        "room":sc[cid]["receiver_configuration"]["room_table"],"selection_reasons":why,
                        "subsecond_complete_reference_instances":shortcounts[cid],"conditions":sorted(alltags[cid])})
    return {"schema":"s6b.challenge-panel.v1","status":"METADATA_ONLY_DETERMINISTIC_SELECTION",
            "case_ids":sorted(selected),"count":len(selected),"scene_output_count":len(selected)*2,"streams":["O0","O1"],
            "inherited_panel_count":len(panel),"complete_reference_subsecond_count":len(shorts),
            "complete_reference_subsecond_scene_count":len(shortcounts),"subsecond_instances":shorts,
            "added_for_metadata_coverage":additions,"rows":outrows,"covered_conditions":sorted(covered),
            "uncovered_available_conditions":sorted(available-covered),
            "scope":"Post-S6A challenge screen, not an untouched holdout or population-generalization estimate.",
            "reference_boundary":"This file contains offline reference metadata. Do not pass it or its speaker/source/geometry fields to the runtime scheduler or tracker.",
            "geometry_limit":"Nominal lab-angle equivalence is a geometric design tag only; native XVF angle transform remains unverified."}

def registry(seed):
    byid={x["profile_id"]:x for x in seed["profiles"]}
    result=[]
    for bid,title,family,mode,recipe,parent,route,kind,newid in METHODS:
        equation,risk=MECHANISMS[mode]
        seedrow=byid.get(bid)
        revised=bid in ("B19","B21","B23","B27","B29")
        delta={}
        if bid=="B32":delta={"sensor_quarantine_enabled":True}
        if bid=="B33":delta={"update_escrow_enabled":True}
        if bid in ("B26","B27"):
            delta.update({"input_variant":"relative_minus_3dB_from_raw_once","minimum_rms":.002})
        if bid in ("B27","B35"):delta["rms_policy"]="full_window"
        if bid=="B34":delta.update({"evidence_policy":"early_short_long","early_window_sec":.5,"purity_policy":"contiguous","minimum_contiguous_clean_sec":.45,"minimum_clean_fraction":.8,
            "prospective_repair":"Initial .5s contiguous-clean requirement on a .5s early window admitted zero vectors in native smoke because valid model frames leave unknown trailing support. Lowered to .45s before broad execution; preserve failed smoke and recheck repaired effective profile."})
        if bid in ("B18","B20","B21"):delta["purity_policy"]="fraction"
        if bid=="B19":delta.update({"purity_policy":"gate_only","post_policy":"posterior_hysteresis","segmentation_hop_sec":.5,"embedding_window_sec":.5})
        if bid=="B21":delta.update({"post_policy":"hard_argmax_fraction","segmentation_hop_sec":.5,"embedding_window_sec":.5})
        if bid=="B29":delta.update({"purity_policy":"gate_only","post_policy":"posterior_hysteresis","segmentation_hop_sec":.75,"embedding_window_sec":.5})
        if bid in ("B24","B25"):delta.update({"cadence_policy":"event_driven","evidence_debt_enabled":True,"matched_voice_floor":True})
        result.append({"profile_id":bid,"name":title,"classification":kind,"mechanism_family":family,
            "recipe_family_id":recipe,"tracker_mode":mode,"comparison_parent":parent,"cue_route":route,
            "cue_off_parent":"B01" if bid in ("B02","B03","B04","B05","B06","B07","B08","B32","B33") else parent,
            "new_hypothesis_ids":[newid] if newid else [],"inherited_idea_ids":seedrow.get("idea_ids",[]) if seedrow else [],
            "seed_status":"REVISED_WITH_EXPLICIT_MAPPING" if revised else "PRESERVED_ID_WITH_V2_IMPLEMENTATION" if seedrow else "NEW_S6B_ID",
            "mechanism_contract":equation,"falsification_or_failure":risk,
            "configuration_delta_contract":delta,"status":"PROPOSED_REQUIRES_IMPLEMENTATION_EFFECT_RECEIPT",
            "execution_status":"NOT_ESTABLISHED_BY_DESIGN_BUILDER",
            "screening_case_count":"CHALLENGE_PANEL.count","confirmation_scene_count":240,"streams":["O0","O1"],
            "scheduler_contract":"Common deterministic arrived-evidence order and common first-label/revision export. Native paced scheduling separately measured; B00 remains historical.",
            "compute_contract":"Reuse only identical input/settings/admitted source spans and dependency identities. Neural family is not an exact cache key. Post-hoc vector rejection does not save executed inference.",
            "acceptance":"Execute a mechanism-specific observable-effect fixture and causal/cue-off tests, screen both taps with all cases retained, then record full-bank confirmation or concrete pruning reason.",
            "comparison_caveat":"Restricted angle diagnostic, never a sufficient identity solution." if bid=="B02" else
                "Original scheduler differs; compare B36 for common-scheduler method effects." if bid=="B00" else
                "Component bundle comparison: isolate linked factors with declared companion contrasts." if bid in ("B16","B18","B22","B24","B28","B34") else None})
    counts=Counter(x["classification"] for x in result)
    assert counts=={"main":27,"companion":9,"control":4}
    assert len({x["profile_id"] for x in result})==40
    mappings=[]
    for sid,s in sorted(byid.items()):
        r=next(x for x in result if x["profile_id"]==sid)
        reason={"B19":"Revised from short-evidence spatial companion to posterior/.5-stride/.5-window/gate-only voice companion; matched purity contrast against B18.",
                "B21":"Revised from long-evidence spatial companion to hard/.5-stride/.5-window/fractional-purity voice companion; matched post-policy contrast against B18.",
                "B29":"Revised from beam spatial companion to posterior/.75-stride/.5-window/gate-only voice companion; policy contrast against B01 and stride contrast against B19.",
                "B23":"Revised from endpoint-fast plus advisory (parent B22) to protected endpoint-only on original R0 (parent B01), enabling B01/B05/B23/B39 route factorial.",
                "B27":"Revised from lower-gain cue-on companion to lower-gain full-window-RMS companion, enabling B01/B35/B26/B27 gain-by-gate-support factorial."}.get(sid,
                "Preserve inherited ID and scientific mechanism; compile named V2 implementation and disclose effective settings before execution.")
        mappings.append({"profile_id":sid,"inherited_mechanism":s["mechanism"],"inherited_recipe":s["recipe_id"],
            "inherited_metadata":s["metadata"],"inherited_parent":s["comparison_parent"],
            "inherited_idea_ids":s.get("idea_ids",[]),"current_name":r["name"],"current_recipe_family":r["recipe_family_id"],
            "current_parent":r["comparison_parent"],"change_status":r["seed_status"],"reason":reason})
    return {"schema":"s6b.candidate-registry.v1","status":"DESIGN_CONTRACT_NOT_EXECUTION_PROOF",
            "profile_count":40,"counts_by_classification":dict(counts),"distinct_named_tracker_modes":len({x["tracker_mode"] for x in result}),
            "recipe_family_count":8,"cache_identity_warning":"Eight conceptual neural recipe families; exact branch/window/admission/ASR identities are more numerous.",
            "profiles":result},mappings

NEW_HYPOTHESES = [
("N01",["B32"],"Sensor contradiction quarantine","Independent strong voice agreement contradicting fresh bearing accumulates sensor-debt; quarantine only spatial credit and recover after disjoint agreement.","Quarantine entry/hold/recovery events; voice-only counterfactual and stable-wrong/same-angle fixtures.","REQUIRED_IMPLEMENTATION"),
("N02",[],"Event-triggered posterior refresh","A causal boundary request triggers new valid Pyannote context instead of merely changing a post-hoc gate.","Actual extra segmentation calls, source spans, latency and matched no-trigger control.","DEFERRED_PENDING_DISTINCT_IMPLEMENTATION"),
("N03",["B33"],"Disjoint-evidence update escrow","Cue-assisted prototype updates remain escrowed until a later disjoint clean embedding agrees; never use overlapping windows as independent evidence.","Proposed/confirmed/expired update events with disjoint intervals, and cue-off exact voice-parent parity.","REQUIRED_IMPLEMENTATION"),
("N04",["B23","B39"],"Protected endpoint circuit breaker","Bound source-fresh XVF advisory resets by rate and independent speech/voice safety evidence, preserving ASR text delivery.","Actual endpoint branch counters, reset provenance, prefix causality and no-advice lexical comparison.","REQUIRED_IMPLEMENTATION"),
("N05",["B24","B25"],"Evidence-debt scheduler with voice floor","Admit model work from causal uncertainty/debt within shared budget, with an independent voice observation floor; spatial event is the paired optional input.","Actual model calls/admitted windows, equal budgets, floor breaches, dropped evidence and short-turn cost/coverage.","REQUIRED_IMPLEMENTATION"),
("N06",[],"Clip-risk prototype update freeze","Prevent prototype adaptation when input rail/headroom evidence indicates distortion, while retaining text and labels.","Actual clip-risk/update-freeze branch and matched gain controls.","DEFERRED_PENDING_DISTINCT_IMPLEMENTATION"),
("N07",["B15"],"Latency and edit-count revision budget","Restrict arrived-node graph revisions by both age and maximum edit count with forward-only exported lineage.","Actual bounded revisions, stable IDs, first-output immutability and latest-label scoring.","ADDITIONAL_IMPLEMENTATION_IF_EFFECT_PROVEN"),
("N08",[],"Audio-only shadow disagreement sentinel","Run a distinct audio-only shadow identity state and use disagreement to reduce spatial confidence.","Separate shadow-state evolution and disagreement trigger with controlled wrong-stable cues.","DEFERRED_PENDING_DISTINCT_IMPLEMENTATION"),
]
INTERACTIONS = [
("original_tuned_x_tracking",["B01","B05","B16","B17"],"Shared tracker voice-parent/adaptive family, scheduler and declared cue routes; component bundle main effect is not a single parameter."),
("tracking_endpoint_routes",["B01","B05","B23","B39"],"Original R0 neural settings; endpoint branch fresh, speaker features reused only if admitted spans match."),
("duration_maturity_revision",["B18","B20","B34"],"Same post policy/stride/purity where possible; exact disjoint maturity and bounded revision eligibility recorded; early-short path explicit."),
("postpolicy_stride_purity_fractional",["B01","B29","B19","B18","B21"],"Five cells: hard/.75/gate, post/.75/gate, post/.5/gate, post/.5/fraction, hard/.5/fraction. Adjacent named contrasts isolate one setting; missing cells prevent a full three-factor interaction estimate."),
("gain_x_rms_support",["B01","B35","B26","B27"],"Both taps; baseline vs raw-derived relative -3 dB, fixed .002 RMS threshold, dispatch vs full-window support."),
("cadence_floor_x_spatial_events",["B24","B25"],"Same actual max budget and voice floor; disclose neural keys separately when admitted spans differ. Other fixed schedules provide cost context, not exact isolated cadence effects."),
("decay_dormancy_condition",["B01","B04","B09","B10","B32"],"Return, relocation, nominal same/folded-angle and independently observed wrong-stable cue strata; never feed truth into runtime."),
("non_greedy_dispatch",["B01","B22","B28"],"Actual modified_beam_search branch and 50ms dispatch; endpoint/dispatch settings differ across these bundles, so inspect effective profiles and do not attribute the whole difference solely to search."),
]
REQUIREMENTS = [
("scope","Retain original B0, immutable S6A, selected model weights/frontends; no hardware, training, full S6A rerun or S6C.","Admission/dependency hashes and closure receipt."),
("profile_counts","24–30 distinct main methods; <=40 total controls/companions; inherited B00–B29 mapping explicit.","Registry counts are design checks; effective hooks/effect fixtures establish implementation."),
("families","Cover controls, simple spatial, uncertainty, temporal/global, robust memory, evidence, ASR and resource families.","Implemented family table with named actual branch and observable effect."),
("new_hypotheses","Implement at least four N01–N08 or document concrete unsupported/dominated/duplicate reasons.","N01/N03/N04/N05 required effect receipts; N07 additional; N02/N06/N08 not silently counted."),
("challenge","Screen all S6A36 plus every scene holding all40 complete-reference subsecond instances, both taps.","CHALLENGE_PANEL input-bound exact instance/case coverage."),
("confirmation","Retained general candidates run all240 both taps before shortlist; pruning reasons explicit.","Per-profile attempted/completed/failed denominators and full-bank result identities."),
("causal_scheduler","Same-code ablations use equal source/context/delivery availability, order, expiry and revision budgets.","Prefix/future divergence, stale/reorder/redelivery and cue-off parity tests."),
("no_truth","Reference text/speaker/angles/activity/timing never enter features, gate, scheduling, tracker or endpoint decisions.","Input schema/call-graph audit and truth mutation invariance."),
("provisional","Disjoint count and unique evidence distinguish maturity from elapsed/overlap time; first/latest labels separate.","Actual provisional/commit/revision events with stable utterance IDs and bounded horizon."),
("short","Retain all40 instances/tap with missing evidence or unknown labels shown, never denominator-select survivors.","Source-count, known/unknown/mixed support, contained/admitted evidence and first/latest identity tables."),
("word_metrics","Pool primary words/chars S/D/I, overlap MIMO, target-only incomplete, and strict-empty insertions/min separately.","Raw numerator/denominator tables, exact population counts, undefined WER for empty reference."),
("identity_metrics","First-display cpWER and latest-revised cpWER distinguished; no unsupported DER.","Stable-label exports, mapping coverage, sole-active support and return consistency denominators."),
("cost","Measure total engine plus stage/wrapper/posterior/gate/tracker/reset/revision/export costs; concurrency sums not wall.","Native paced timings and explicit included/excluded operations."),
("cache","Validate actual consumed bytes and effective dependency DAG; separate component subrecipes and posthoc replay.","Cache-hit/miss admission, mutation fixtures, no circular bindings."),
("runtime","Paced B0, best voice, two joint finalists on single/return/short/overlap; retain repetitions.","USS/RSS/private commit/loading/threads/backlog/write measurements; no desktop-to-CM5 RTF conversion."),
("resource","CM5 ARM64 CPU,2GB RAM,32GB eMMC target; no hardware qualification claim.","Model asset and resident/private/shared/buffer/write ledger with ARM64 path unknowns explicit."),
("robustness","Within-room paired metrics and equal-room/strata/dependency deletion sensitivities; no population generalization.","Matched denominators and whole dependent-block resampling/deletion receipts."),
("pareto","3–5 structurally distinct proposed candidates incl simple voice fallback; accuracy, coverage, latency and cost together.","Full-bank results and harms with assumptions; S6C questions remain proposed."),
("safety_run","Bound workers/threads, memory/free-space, deadline/closure and heartbeat; exact resume preserves failures.","Coordinator/resource/STOP and closure receipts."),
("handoff","Compact analysis-first archive; no raw audio, vectors, model binaries or full journals; maintained code READMEs.","Manifest/actual archive audit, <=6 plots, master V15 update instructions without competing workbook."),
]
def self_test():
    # Adversarially repeated source IDs stay separate source-turn instances; 1.0s is not subsecond.
    geometry={"r":{"speaker_angle_deg_effective":20}}
    def scene(cid,ds):
        return {"case_id":cid,"family_id":"F03","split":"development","sample_rate_hz":100,
                "receiver_configuration":{"room_table":"room"},"segments":[{"kind":"utterance","source_id":"same",
                "participant_id":"A","speaker_key":"anon","source_start_sample":i*200,"source_stop_sample":i*200+int(d*100),
                "rir_id":"r","whole_clip":True} for i,d in enumerate(ds)]}
    scenes=[scene("a",[.5,.5,1]),scene("b",[.8]),scene("c",[.2])]
    pop={"a":"primary_nonoverlap","b":"overlap_complete","c":"ambient_incomplete"}
    got=challenge(scenes,pop,["a"],geometry)
    assert got["complete_reference_subsecond_count"]==3
    assert len({x["instance_id"] for x in got["subsecond_instances"]})==3
    assert "b" in got["case_ids"] and len(got["case_ids"])==len(set(got["case_ids"]))
    # Metadata augmentation may add incomplete c, but its short source cannot enter the complete-reference 40 denominator.
    assert not any(x["case_id"]=="c" for x in got["subsecond_instances"])
    try: challenge(scenes,pop,["a","a"],geometry)
    except ValueError: pass
    else: raise AssertionError("duplicate panel not rejected")
    dummy={"profiles":[{"profile_id":f"B{i:02d}","mechanism":"seed","recipe_id":"R0","metadata":"off",
                        "comparison_parent":"old","idea_ids":[]} for i in range(30)]}
    reg,mapping=registry(dummy)
    assert reg["counts_by_classification"]=={"main":27,"companion":9,"control":4}
    assert len(mapping)==30 and {x["profile_id"] for x in mapping if x["change_status"]=="REVISED_WITH_EXPLICIT_MAPPING"}=={"B19","B21","B23","B27","B29"}
    return {"status":"PASS","tests":["repeated-source-instance retention","strict subsecond boundary",
        "incomplete-reference exclusion","deterministic scene deduplication","duplicate panel rejection",
        "40 profile/27 main/9 companion/4 control counts","explicit 30 seed mappings with five declared revisions"]}

def build(sim,output):
    a=sim/"reports/S6A"/S6A_RUN
    paths={"bank":sim/"scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json",
           "rir":sim/"rir_library/v1/RIR_MANIFEST.json","panel":a/"PROBE_PANEL.json",
           "short":a/"REFERENCE_SHORT_TURN_RESULTS.csv","coverage":a/"baseline_results/COVERAGE.csv",
           "seed":a/"design/S6B_JOINT_PLAN.json"}
    bindings={k:binding(p) for k,p in paths.items()}
    for k,expected in KNOWN_HASHES.items():
        if bindings[k]["sha256"]!=expected:raise ValueError(f"immutable input hash mismatch: {k}")
    bank=read_json(paths["bank"]); inherited=read_json(paths["panel"])
    geometry={r["run_id"]:r["geometry"] for r in read_json(paths["rir"])["records"]}
    cov=rows(paths["coverage"]); pop={r["case_id"]:r["population"] for r in cov if r["stream"]=="O0"}
    if len(cov)!=480 or len(pop)!=240 or any(r["scored"]!="True" for r in cov):raise ValueError("full S6A baseline coverage required")
    panel=challenge(bank["scenes"],pop,inherited["case_ids"],geometry)
    if panel["inherited_panel_count"]!=36 or panel["complete_reference_subsecond_count"]!=40:raise ValueError("required short/panel denominator changed")
    shortrows=[r for r in rows(paths["short"]) if r["stream"]=="O0" and r["profile"]=="B0" and r["duration_bin"]=="<1s"]
    inheritedcounts={r["case_id"]:int(r["source_turns"]) for r in shortrows if int(r["source_turns"])}
    derivedcounts=dict(Counter(x["case_id"] for x in panel["subsecond_instances"]))
    if inheritedcounts!=derivedcounts:raise ValueError(f"short source-instance count differs from accepted S6A: {inheritedcounts} vs {derivedcounts}")
    reg,mapping=registry(read_json(paths["seed"]))
    diagnostics=[{"profile_id":"B18_C1","parent":"B18","delta":{"tracker.commit_disjoint_count":1},"mechanism":"short duration by one-versus-two disjoint commitment observations"},
                 {"profile_id":"B20_C1","parent":"B20","delta":{"tracker.commit_disjoint_count":1},"mechanism":"long duration by one-versus-two disjoint commitment observations"},
                 {"profile_id":"B24_FREQUENT","parent":"B24","delta":{"embedding.cadence_policy":"frequent"},"mechanism":"fixed frequent versus budgeted event admission with matched waveform/purity/voice-floor settings"},
                 {"profile_id":"B24_SPARSE","parent":"B24","delta":{"embedding.cadence_policy":"sparse"},"mechanism":"fixed sparse versus budgeted event admission with matched waveform/purity/voice-floor settings"}]
    for d in diagnostics:d.update(classification="limited_diagnostic",scope="challenge_only_not_general_ranked",status="IMPLEMENTATION_PENDING")
    reg["challenge_count"]=panel["count"];reg["all_methods_screen_scene_output_runs"]=panel["count"]*2*44
    reg["core_profile_count"]=40;reg["limited_diagnostic_count"]=4;reg["total_named_configuration_count"]=44
    reg["count_exception"]="Prompt normally recommends <=40. Four explicitly bounded challenge-only configurations isolate required duration/commitment and cadence interactions without replacing the 27 main scientific mechanisms. They are not hidden or general-purpose ranked candidates."
    reg["maximum_fullbank_policy_outputs_if_all_40_retained"]=40*240*2
    reg["input_bindings"]=bindings
    new=[{"hypothesis_id":n,"profile_ids":p,"name":title,"mechanism":m,"required_observable_effect":proof,
          "implementation_decision":status,"execution_proven":False,
          "defer_reason":None if p else "No distinct causal mechanism is included in the approved bounded 40-profile matrix. Do not count an adjacent existing gate/quarantine/beam as this hypothesis; reconsider only after current mechanism comparisons."}
         for n,p,title,m,proof,status in NEW_HYPOTHESES]
    requirements=[{"requirement_id":k,"contract":c,"acceptance_evidence":e,"status":"PENDING_EXECUTION_OR_FINAL_AUDIT"} for k,c,e in REQUIREMENTS]
    output.mkdir(parents=True,exist_ok=True)
    dump(output/"CANDIDATE_REGISTRY.json",reg)
    dump(output/"LIMITED_DIAGNOSTICS.json",{"schema":"s6b.limited-diagnostics.v1","profiles":diagnostics,"count":4,"core_plus_diagnostic_count":44,"scope":"challenge-only; not a full-bank shortlist candidate"})
    dump(output/"CHALLENGE_PANEL.json",panel)
    write_csv(output/"CHALLENGE_PANEL.csv",panel["rows"])
    write_csv(output/"SUBSECOND_SOURCE_INSTANCES.csv",panel["subsecond_instances"])
    write_csv(output/"SEED_ID_MAPPING.csv",mapping)
    write_csv(output/"METHOD_FAMILY_COVERAGE.csv",[{k:p[k] for k in ("profile_id","name","classification","mechanism_family","tracker_mode","recipe_family_id","comparison_parent","cue_route","new_hypothesis_ids","status")} for p in reg["profiles"]])
    dump(output/"NEW_HYPOTHESIS_DECISIONS.json",{"schema":"s6b.new-mechanisms.v1","hypotheses":new,"minimum_required_distinct_new_mechanisms":4})
    dump(output/"INTERACTION_CONTRACTS.json",{"schema":"s6b.interactions.v1","contrasts":[{"id":n,"profiles":p,"interpretation_contract":c} for n,p,c in INTERACTIONS]})
    dump(output/"REQUIREMENT_ACCEPTANCE.json",{"schema":"s6b.requirements.v1","requirements":requirements})
    audit={"schema":"s6b.design-build.v1","status":"PASS_DESIGN_NOT_EXECUTION","script":binding(__file__),"input_bindings":bindings,
           "tests":self_test(),"profile_count":40,"main_count":27,"companion_count":9,"control_count":4,
           "challenge_scene_count":panel["count"],"challenge_output_count":panel["scene_output_count"],
           "complete_reference_subsecond_instances":40,"short_count_matches_S6A_B0_O0":True,
           "outputs":[binding(p) for p in sorted(output.iterdir()) if p.is_file() and p.name not in ("DESIGN_BUILD_RECEIPT.json","RECIPE_GROUP_PROPOSAL.json")]}
    dump(output/"DESIGN_BUILD_RECEIPT.json",audit)
    print(json.dumps({k:audit[k] for k in ("status","profile_count","main_count","challenge_scene_count","complete_reference_subsecond_instances")}))
    return audit

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--simulation-root",type=Path,default=DEFAULT_SIM)
    p.add_argument("--output",type=Path)
    p.add_argument("--test",action="store_true")
    args=p.parse_args()
    if args.test: print(json.dumps(self_test(),indent=2));return
    out=args.output or args.simulation_root/"reports/S6B"/RUN/"design"
    build(args.simulation_root,out)
if __name__=="__main__":main()
