"""Offline S6B revision harm and censored exposure. README_S6B_REVISION_ANALYSIS.md."""
from __future__ import annotations
from collections import Counter,defaultdict
import math
from s6a_support_metrics import mapped_ranges,intersection,samples,union

def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def event_label(event):return event.get("latest_label",event.get("speaker"))
def unknown_label(label):
    return not isinstance(label,str) or not label.strip() or label.lower() in ("unknown","unassigned","speaker_?") or "overlapping speaker" in label.lower()
def label_mapper(value,assignment):
    aliases=defaultdict(set)
    for d in value["decisions"]:
        aliases[d.get("display_label",d["anonymous_label"])].add(d["anonymous_label"])
    if value.get("profile_id")=="B37":
        for label in list(aliases):
            if not unknown_label(label):aliases[label]={"AllSpeaker"}
        aliases["Speaker_1"]={"AllSpeaker"}
    def result(label):
        if unknown_label(label):return dict(status="UNKNOWN_OR_OVERLAP",speaker=None)
        candidates=aliases.get(label,{label})
        if len(candidates)!=1:return dict(status="AMBIGUOUS_DISPLAY_ALIAS",speaker=None)
        canonical=next(iter(candidates))
        if canonical in assignment.get("ambiguous_labels",[]):return dict(status="AMBIGUOUS_DURATION_MAPPING",speaker=None)
        mapped=assignment.get("mapping",{}).get(canonical)
        return dict(status="MAPPED" if mapped is not None else "UNMAPPED_LABEL",speaker=mapped)
    return result
def participant_for_span(row,support,stream,length):
    if not support["all_speaker_reference_complete"]:return "INCOMPLETE_REFERENCE",None,[]
    shift=support["output_mappings"][stream]["source_with_rir_to_output_offset_samples"]
    if shift is None:return "UNAVAILABLE_ALIGNMENT",None,[]
    a,b=row.get("source_start_sec"),row.get("source_end_sec")
    if not finite(a) or not finite(b) or b<=a:return "UNAVAILABLE_SOURCE_SPAN",None,[]
    span=[[round(a*16000),round(b*16000)]]
    people=defaultdict(list)
    for t in support["turns"]:
        if t["activity_available"]:
            people[t["speaker_key"]].extend(mapped_ranges(t["active_ranges"],shift,length))
    intersecting=sorted(p for p,ranges in people.items() if samples(intersection(span,ranges))>0)
    if len(intersecting)==1:return "ONE_KNOWN_PARTICIPANT_SOURCE_SUPPORT",intersecting[0],intersecting
    return ("NO_KNOWN_ACTIVE_SUPPORT" if not intersecting else "MULTIPLE_KNOWN_PARTICIPANTS"),None,intersecting
def transition(before,after,reference):
    if reference is None:return "UNIDENTIFIABLE_REFERENCE_SPAN"
    bc=before["status"]=="MAPPED" and before["speaker"]==reference
    ac=after["status"]=="MAPPED" and after["speaker"]==reference
    bw=before["status"]=="MAPPED" and before["speaker"]!=reference
    aw=after["status"]=="MAPPED" and after["speaker"]!=reference
    if bc and aw:return "CORRECT_TO_WRONG"
    if bw and ac:return "WRONG_TO_CORRECT"
    if bc and not ac:return "CORRECT_TO_UNKNOWN_OR_UNMAPPED"
    if not bc and not bw and ac:return "UNKNOWN_OR_UNMAPPED_TO_CORRECT"
    if not bc and not bw and aw:return "UNKNOWN_OR_UNMAPPED_TO_WRONG"
    if bw and not ac and not aw:return "WRONG_TO_UNKNOWN_OR_UNMAPPED"
    if bw and aw:return "WRONG_TO_OTHER_WRONG"
    if bc and ac:return "CORRECT_ALIAS_CHANGE"
    return "UNKNOWN_OR_UNMAPPED_CHANGE"

def revision_metrics(value,support,assignment):
    """Map saved labels only after prediction; no truth influences runtime state."""
    raw=value.get("transcript_events") or []
    counts=Counter(str(e.get("revision_scope","UNSPECIFIED")) for e in raw if e.get("event_type")=="transcript_label_revision")
    snapshot=value.get("snapshot",{}).get("scheduler",{}).get("utterances",[])
    if not raw:
        no_readable=value.get("profile_id")!="B00" and not value.get("final_transcripts_first") and not snapshot
        return dict(status="NO_READABLE_OUTPUT" if no_readable else "UNAVAILABLE_HISTORICAL_OR_NO_TRANSCRIPT_EVENTS",revision_scope_counts=dict(counts),
            displayed_utterances=len(value.get("final_transcripts_first",[])),events=[],utterances=[],
            exposure_scope="Missing historical event availability is not zero correction delay or zero wrong exposure.",
            identifiable_utterances=0,exposure_unavailable_utterances=len(value.get("final_transcripts_first",[])),
            participant_sets={})
    grouped=defaultdict(list)
    for i,e in enumerate(raw):
        if e.get("event_type") not in ("transcript_partial","transcript_final","transcript_label_revision"):continue
        uid=e.get("utterance_id",e.get("utterance_index"))
        if uid is None or not finite(e.get("available_at_sec")):raise ValueError("Revision event lacks stable ID/availability")
        grouped[str(uid)].append((i,e))
    snap={str(x["utterance_id"]):x for x in snapshot}
    if len(snap)!=len(snapshot):raise ValueError("Duplicate snapshot utterance ID")
    allids=sorted(set(grouped)|set(snap))
    map_label=label_mapper(value,assignment);length=round(value["duration_sec"]*16000)
    horizon=max([value["duration_sec"]]+[float(e["available_at_sec"]) for _,e in sum(grouped.values(),[])]+
                [float(d["available_at_sec"]) for d in value["decisions"] if finite(d.get("available_at_sec"))])
    event_rows=[];utterances=[];participant_sets=defaultdict(set)
    for uid in allids:
        events=sorted(grouped.get(uid,[]),key=lambda item:(item[1]["available_at_sec"],item[0]))
        displays=[e for _,e in events if e["event_type"] in ("transcript_partial","transcript_final") and str(e.get("text","")).strip()]
        row=snap.get(uid)
        if row is None:
            row=displays[-1] if displays else {}
        status,reference,participants=participant_for_span(row,support,value["stream"],length)
        if not displays:
            utterances.append(dict(utterance_id=uid,status="NO_READABLE_DISPLAY_EVENT",reference_span_status=status,
                identifiable_reference_speaker=reference,reference_participants=participants,exposure_available=False))
            continue
        first=displays[0];first_label=event_label(first);first_time=float(first["available_at_sec"])
        if row.get("first_display_label") is not None and row["first_display_label"]!=first_label:raise ValueError("First display label differs from preserved snapshot")
        if finite(row.get("first_display_time")) and abs(row["first_display_time"]-first_time)>1e-8:raise ValueError("First display time differs from preserved snapshot")
        state_label=first_label;state_time=first_time;segments=[];local_changes=[]
        for order,e in events:
            at=float(e["available_at_sec"])
            if at<first_time:continue
            label=event_label(e)
            if label is None:raise ValueError("Transcript state event has no label")
            if label!=state_label:
                segments.append((state_time,at,state_label))
                before,after=map_label(state_label),map_label(label)
                kind=transition(before,after,reference)
                local_changes.append(dict(utterance_id=uid,event_id=e.get("event_id"),available_at_sec=at,
                    revision_scope=e.get("revision_scope","DISPLAY_EVENT_LABEL_CHANGE"),event_type=e["event_type"],
                    after_first_final=at>row["first_final_time"] if finite(row.get("first_final_time")) else False,
                    before_label=state_label,after_label=label,before_mapping=before,after_mapping=after,
                    reference_span_status=status,identifiable_reference_speaker=reference,transition=kind,
                    first_display_label=first_label,first_display_time=first_time,source_start_sec=row.get("source_start_sec"),source_end_sec=row.get("source_end_sec")))
                if reference is not None and (before["status"]=="MAPPED" or after["status"]=="MAPPED"):
                    participant_sets["affected_identifiable"].add(reference)
                    participant_sets[kind].add(reference)
                    if after["status"]=="MAPPED" and after["speaker"]!=reference:
                        participant_sets["wrong_attribution_recipient_after_change"].add(after["speaker"])
                    if before["status"]=="MAPPED" and before["speaker"]!=reference:
                        participant_sets["wrong_attribution_recipient_before_change"].add(before["speaker"])
                state_label=label;state_time=at
        segments.append((state_time,horizon,state_label));event_rows.extend(local_changes)
        first_mapped=map_label(first_label);first_correct=None;wrong=unknown=correct=0.
        wrong_recipients=defaultdict(float)
        for a,b,label in segments:
            if b<a:raise ValueError("Negative label exposure interval")
            mapped=map_label(label)
            if reference is None:continue
            if mapped["status"]=="MAPPED" and mapped["speaker"]==reference:
                correct+=b-a
                if first_correct is None:first_correct=a
            elif mapped["status"]=="MAPPED":
                wrong+=b-a
                wrong_recipients[mapped["speaker"]]+=b-a
                if b>a:participant_sets["known_wrong_exposure_recipient"].add(mapped["speaker"])
            else:unknown+=b-a
        exposure_available=reference is not None
        if exposure_available and abs(correct+wrong+unknown-(horizon-first_time))>1e-6:raise ValueError("Exposure denominator mismatch")
        utterances.append(dict(utterance_id=uid,status="SCORED_SOURCE_SUPPORT_DIAGNOSTIC" if exposure_available else "UNIDENTIFIABLE_REFERENCE_SPAN",
            reference_span_status=status,identifiable_reference_speaker=reference,reference_participants=participants,
            exposure_available=exposure_available,first_display_label=first_label,first_display_mapping=first_mapped,
            first_display_time=first_time,observed_session_end_sec=horizon,
            first_correct_label_time=first_correct,wait_to_first_correct_from_display_sec=first_correct-first_time if first_correct is not None else None,
            never_correct_within_observation=first_correct is None if exposure_available else None,
            observed_label_state_sec=horizon-first_time if exposure_available else None,
            known_wrong_exposure_sec=wrong if exposure_available else None,
            known_wrong_exposure_by_recipient_sec=dict(wrong_recipients) if exposure_available else None,
            unknown_or_unmapped_exposure_sec=unknown if exposure_available else None,
            correct_exposure_sec=correct if exposure_available else None,
            unresolved_observed_exposure_sec=horizon-first_time if exposure_available and first_correct is None else None,
            changed_label_count=len(local_changes),final_latest_label=state_label,source_start_sec=row.get("source_start_sec"),source_end_sec=row.get("source_end_sec")))
    eligible=[r for r in utterances if r["exposure_available"]]
    return dict(status="SCORED_OFFLINE_REVISION_DIAGNOSTICS",revision_scope_counts=dict(counts),events=event_rows,utterances=utterances,
        displayed_utterances=len(utterances),identifiable_utterances=len(eligible),exposure_unavailable_utterances=len(utterances)-len(eligible),
        never_correct_utterances=sum(r["never_correct_within_observation"] for r in eligible),
        known_wrong_exposure_sec=sum(r["known_wrong_exposure_sec"] for r in eligible),
        unknown_or_unmapped_exposure_sec=sum(r["unknown_or_unmapped_exposure_sec"] for r in eligible),
        correct_exposure_sec=sum(r["correct_exposure_sec"] for r in eligible),
        observed_identifiable_label_state_sec=sum(r["observed_label_state_sec"] for r in eligible),
        participant_sets={k:sorted(v) for k,v in participant_sets.items()},
        exposure_scope="Retained utterance-row label-state seconds on modeled availability, censored at observed session end; sums can exceed wall time. Single-participant source-span support and scene-global duration mapping are offline diagnostics, not word alignment or native paced latency.",
        first_display_preserved=True)

def fixtures():
    support=dict(all_speaker_reference_complete=True,output_mappings={"O0":{"source_with_rir_to_output_offset_samples":0}},
        turns=[dict(speaker_key="a",activity_available=True,active_ranges=[[0,32000]]),
               dict(speaker_key="b",activity_available=True,active_ranges=[[64000,80000]])])
    base=dict(duration_sec=5.,stream="O0",profile_id="fixture",decisions=[dict(anonymous_label="P",display_label="P"),dict(anonymous_label="Q",display_label="Q")],
        final_transcripts_first=[dict(utterance_index=0)],snapshot={"scheduler":{"utterances":[dict(utterance_id="u",source_start_sec=0.,source_end_sec=1.5,first_display_label="Q",first_display_time=.5)]}})
    base["transcript_events"]=[
        dict(event_type="transcript_partial",event_id="e1",utterance_id="u",text="words",speaker="Q",available_at_sec=.5),
        dict(event_type="transcript_label_revision",event_id="e2",utterance_id="u",latest_label="P",available_at_sec=1.,revision_scope="bounded_forward_reconciliation"),
        dict(event_type="transcript_final",event_id="e3",utterance_id="u",text="words",speaker="P",available_at_sec=1.5)]
    assignment=dict(mapping={"P":"a","Q":"b"},ambiguous_labels=[])
    got=revision_metrics(base,support,assignment)
    assert got["events"][0]["transition"]=="WRONG_TO_CORRECT"
    assert got["known_wrong_exposure_sec"]==.5 and got["correct_exposure_sec"]==4.
    assert got["utterances"][0]["known_wrong_exposure_by_recipient_sec"]=={"b":.5}
    assert got["participant_sets"]["known_wrong_exposure_recipient"]==["b"]
    assert got["utterances"][0]["wait_to_first_correct_from_display_sec"]==.5
    amb=revision_metrics(base,support,dict(mapping={},ambiguous_labels=["P","Q"]))
    assert amb["known_wrong_exposure_sec"]==0 and amb["never_correct_utterances"]==1
    assert amb["unknown_or_unmapped_exposure_sec"]==4.5
    base["snapshot"]["scheduler"]["utterances"][0]["source_end_sec"]=5.
    mixed=revision_metrics(base,support,assignment)
    assert mixed["identifiable_utterances"]==0 and mixed["exposure_unavailable_utterances"]==1
    base["transcript_events"]=[]
    missing=revision_metrics(base,support,assignment)
    assert missing["status"]=="UNAVAILABLE_HISTORICAL_OR_NO_TRANSCRIPT_EVENTS"
    base["final_transcripts_first"]=[];base["snapshot"]={"scheduler":{"utterances":[]}}
    empty=revision_metrics(base,support,assignment)
    assert empty["status"]=="NO_READABLE_OUTPUT" and empty["exposure_unavailable_utterances"]==0
    return dict(status="PASS",tests=["wrong-to-correct exposure and wait","wrong attribution to another mapped participant retained","global mapping ambiguity remains unknown and censored","mixed-participant span remains unidentifiable","missing historical timing is unavailable","actual empty display distinguished from missing history"])
def summarize_records(records):
    """Do not sum speaker identities as independent scene occurrences."""
    output=[]
    for pid,stream in sorted({(r["profile_id"],r["stream"]) for r in records}):
        chosen=[r for r in records if (r["profile_id"],r["stream"])==(pid,stream)]
        metrics=[r["metrics"] for r in chosen]
        scopes=sum((Counter(m["revision_scope_counts"]) for m in metrics),Counter())
        changes=[e for m in metrics for e in m["events"]]
        utterances=[u for m in metrics for u in m["utterances"]]
        identifiable=[u for u in utterances if u["exposure_available"]]
        waits=[u.get("wait_to_first_correct_from_display_sec") for u in identifiable]
        good=[x for x in waits if finite(x)]
        from s6b_analysis import quantiles
        populations={}
        for population in ("PRIMARY_NONOVERLAP","COMPLETE_OVERLAP","ALL_COMPLETE_NONEMPTY"):
            picked=[r for r in chosen if r["population"] in ("PRIMARY_NONOVERLAP","COMPLETE_OVERLAP")] if population=="ALL_COMPLETE_NONEMPTY" else [r for r in chosen if r["population"]==population]
            if not picked:continue
            cp={}
            for view in ("first_final","latest_revised","first_display_label_final_words"):
                words=[r["cp"][view] for r in picked if r["cp"][view]]
                count={k:sum(x[k] for x in words) for k in ("errors","reference_words","substitutions","deletions","insertions")}
                count["scored_scenes"]=len(words);count["rate"]=count["errors"]/count["reference_words"] if count["reference_words"] else None
                cp[view]=count
            if len({x["reference_words"] for x in cp.values()})!=1:raise ValueError("Revision label views have unequal reference denominator")
            n=cp["first_final"]["reference_words"]
            populations[population]=dict(cp=cp,
                latest_minus_first_final_errors=cp["latest_revised"]["errors"]-cp["first_final"]["errors"],
                latest_minus_first_display_errors=cp["latest_revised"]["errors"]-cp["first_display_label_final_words"]["errors"],
                latest_minus_first_final_pp=100*(cp["latest_revised"]["errors"]-cp["first_final"]["errors"])/n if n else None,
                latest_minus_first_display_pp=100*(cp["latest_revised"]["errors"]-cp["first_display_label_final_words"]["errors"])/n if n else None,
                scenes_latest_cp_improves=sum(r["cp"]["latest_revised"].get("errors",0)<r["cp"]["first_final"].get("errors",0) for r in picked),
                scenes_latest_cp_harms=sum(r["cp"]["latest_revised"].get("errors",0)>r["cp"]["first_final"].get("errors",0) for r in picked))
        participants=defaultdict(set)
        for m in metrics:
            for label,people in m.get("participant_sets",{}).items():participants[label].update(people)
        wrong_recipient_seconds=defaultdict(float)
        for u in identifiable:
            for person,seconds in (u.get("known_wrong_exposure_by_recipient_sec") or {}).items():wrong_recipient_seconds[person]+=seconds
        output.append(dict(profile_id=pid,stream=stream,scenes=len(chosen),
            historical_or_event_unavailable_scenes=sum(m["status"]=="UNAVAILABLE_HISTORICAL_OR_NO_TRANSCRIPT_EVENTS" for m in metrics),
            no_readable_output_scenes=sum(m["status"]=="NO_READABLE_OUTPUT" for m in metrics),
            actual_revision_scope_counts=dict(scopes),derived_changed_label_transitions=len(changes),
            post_final_changed_label_transitions=sum(e["after_first_final"] for e in changes),
            transition_counts=dict(Counter(e["transition"] for e in changes)),
            affected_identifiable_participant_count=len(participants.get("affected_identifiable",set())),
            participant_counts_by_transition={k:len(v) for k,v in participants.items()},
            participant_sets_by_transition={k:sorted(v) for k,v in participants.items()},
            displayed_utterances=sum(m["displayed_utterances"] for m in metrics),
            identifiable_utterances=len(identifiable),exposure_unavailable_utterances=sum(m["exposure_unavailable_utterances"] for m in metrics),
            never_correct_utterances=sum(u["never_correct_within_observation"] for u in identifiable),
            wait_to_first_correct_from_display_sec=quantiles(waits),
            known_wrong_exposure_sec=sum(u["known_wrong_exposure_sec"] for u in identifiable),
            known_wrong_exposure_by_recipient_sec=dict(wrong_recipient_seconds),
            distinct_wrong_attribution_recipient_count=len(participants.get("known_wrong_exposure_recipient",set())),
            unknown_or_unmapped_exposure_sec=sum(u["unknown_or_unmapped_exposure_sec"] for u in identifiable),
            correct_exposure_sec=sum(u["correct_exposure_sec"] for u in identifiable),
            observed_identifiable_label_state_sec=sum(u["observed_label_state_sec"] for u in identifiable),
            observed_censored_never_correct_exposure_sec=sum(u.get("unresolved_observed_exposure_sec") or 0 for u in identifiable),
            reference_span_status_counts=dict(Counter(u["reference_span_status"] for u in utterances)),populations=populations,
            scope="Duration mapping and single-participant source support are offline diagnostics. Retained-row exposure is censored modeled utterance-seconds, not wall time or word-aligned native latency."))
    return output

def run_cli(args):
    from pathlib import Path
    import time
    from s6b_analysis import read,verified,bind,save,csv_write
    report=args.report;index_path=args.index if args.index.is_absolute() else report/args.index
    out=report/args.output_subdir;analysis=report/args.analysis_subdir
    if Path(args.output_subdir).is_absolute() or report.resolve() not in out.resolve().parents:
        raise ValueError("Output must be a named report child directory")
    index=read(index_path);inputs=read(report/"INPUT_INDEX.json")
    inp={(r["case_id"],r["stream"]):r for r in inputs["rows"]}
    keys=[(r["profile_id"],r["stream"],r["case_id"]) for r in index["rows"]]
    expected={(p,s,c) for p in index["profiles"] for s in ("O0","O1") for c in index["case_ids"]}
    if len(keys)!=len(set(keys)) or not set(keys)<=expected:raise ValueError("Invalid prediction index coverage")
    if args.require_complete and (set(keys)!=expected or index["status"]!="COMPLETE"):raise ValueError("Incomplete requested index")
    started=time.perf_counter();records=[];failures=[];sources=[]
    for i,item in enumerate(index["rows"]):
        cid,stream,pid=item["case_id"],item["stream"],item["profile_id"]
        score_path=analysis/"scores"/pid/cid/(stream+".json")
        try:
            value=verified(item["result"]);score=read(score_path)
            if score["analysis_identity"]["prediction"]!=item["result"]:raise ValueError("Score/prediction binding mismatch")
            support_binding=inp[cid,stream]["support"]
            if score["analysis_identity"]["support"]!=support_binding:raise ValueError("Score/reference binding mismatch")
            support=verified(support_binding)["support"]
            metrics=revision_metrics(value,support,score["duration_assignment"])
            cp={k:(v["attributed_cpwer"].get("word_counts") or {}) for k,v in score["text_metrics"].items()}
            records.append(dict(case_id=cid,stream=stream,profile_id=pid,population=score["population"],room=score["room"],metrics=metrics,cp=cp))
            sources.append(dict(prediction=item["result"],score=bind(score_path),support=support_binding))
        except Exception as exc:
            failures.append(dict(case_id=cid,stream=stream,profile_id=pid,error=type(exc).__name__+": "+str(exc)))
        if (i+1)%176==0:
            save(out/"HEARTBEAT.json",dict(attempted=i+1,scored=len(records),requested=len(expected),elapsed_sec=time.perf_counter()-started))
    summary=summarize_records(records)
    event_rows=[dict(case_id=r["case_id"],stream=r["stream"],profile_id=r["profile_id"],population=r["population"],**e) for r in records for e in r["metrics"]["events"]]
    utterance_rows=[dict(case_id=r["case_id"],stream=r["stream"],profile_id=r["profile_id"],population=r["population"],**u) for r in records for u in r["metrics"]["utterances"]]
    scene_rows=[]
    for r in records:
        m=r["metrics"];row={k:r[k] for k in ("case_id","stream","profile_id","population","room")}
        row.update({k:v for k,v in m.items() if k not in ("events","utterances","exposure_scope")})
        for view,counts in r["cp"].items():
            for name,count in counts.items():row["cp_"+view+"_"+name]=count
        scene_rows.append(row)
    out.mkdir(parents=True,exist_ok=True)
    for name,rows in (("REVISION_PROFILE_RESULTS.csv",summary),("REVISION_SCENE_RESULTS.csv",scene_rows),("REVISION_EVENTS.csv",event_rows),("UTTERANCE_EXPOSURE.csv",utterance_rows)):
        csv_write(out/name,rows)
    save(out/"REVISION_PROFILE_RESULTS.json",summary)
    receipt=dict(status="COMPLETE_REQUESTED_INDEX" if len(records)==len(expected) and not failures else "PARTIAL_RESUMABLE",
        schema="jp_s6b_revision_exposure_v1",index=bind(index_path),analysis_directory=str(analysis),code=bind(__file__),
        source_score_code=bind(Path(__file__).parent/"s6b_analysis.py"),tests=fixtures(),requested=len(expected),scored=len(records),
        failures=failures,sources=sources,results=summary,elapsed_sec=time.perf_counter()-started,
        interpretation="First-label history is immutable. Ongoing display revisions and bounded reconciliation are separate. Exposure never infers word timestamps; ambiguous mapping or multi-person/incomplete spans stay unidentified.",
        tables=[bind(out/name) for name in ("REVISION_PROFILE_RESULTS.csv","REVISION_SCENE_RESULTS.csv","REVISION_EVENTS.csv","UTTERANCE_EXPOSURE.csv")])
    save(out/"REVISION_ANALYSIS_RECEIPT.json",receipt)
    if args.require_complete and (failures or len(records)!=len(expected)):raise RuntimeError("Incomplete revision scoring; inspect receipt")
    return {k:receipt[k] for k in ("status","requested","scored","elapsed_sec")}

def main():
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path,default=Path(__file__).resolve().parents[1]/"reports/S6B/20260909T230840Z")
    p.add_argument("--index",type=Path);p.add_argument("--analysis-subdir");p.add_argument("--output-subdir",default="revision_analysis_v1")
    p.add_argument("--require-complete",action="store_true");p.add_argument("--test",action="store_true")
    a=p.parse_args()
    if a.test:print(json.dumps(fixtures(),indent=2));return
    if a.index is None or not a.analysis_subdir:p.error("--index and --analysis-subdir are required unless --test")
    print(json.dumps(run_cli(a),indent=2))

if __name__=="__main__":main()
