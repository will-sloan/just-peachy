"""All240 A15/B15 presentation-only replay. See README_S6D_APPLICATION_FOCUS.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

SIM=Path(__file__).resolve().parents[1]
APP=SIM.parents[2]/'Software Validation from Datasets/Evaluation Tool/app'
sys.path.insert(0,str(APP))
from edge_speech_pipeline.research_s6d import S6DSettings,PresentationState
import s6c_name_analysis_v3 as names
from s6a_support_metrics import union,intersection,samples,validate_support


def lcs(a,b):
    previous=[0]*(len(b)+1)
    for x in a:
        row=[0]
        for j,y in enumerate(b,1):
            row.append(previous[j-1]+1 if x==y else max(previous[j],row[-1]))
        previous=row
    return previous[-1]


def tokens(text):
    import re
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?",text.lower())


def write_csv(path,rows):
    with path.open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,list(rows[0]));writer.writeheader();writer.writerows(rows)


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    core=names.core
    authority=core.read(core.REPORT/'full_n01_naming_names_v3/NAME_ANALYSIS_RECEIPT.json')
    index=core.verified(authority['index'])
    indexrows=[r for r in index['rows'] if r['candidate_id'] in {'C088','C091'}]
    if len(indexrows)!=960 or len({(r['candidate_id'],r['case_id'],r['stream']) for r in indexrows})!=960:
        raise ValueError('Exact two-gallery all240/both-tap grid required')
    # Bind selection before reading predictions, Q occurrences or scorer identities.
    gallery_index=core.read(core.REPORT/'RESEARCH_GALLERY_INDEX.json')
    selections={};gallery_bindings={}
    for candidate,condition in [('C088','FIXED_ROTATION_A'),('C091','FIXED_ROTATION_B')]:
        binding=next(r['manifest'] for r in gallery_index['rows'] if r['gallery_condition']==condition and r['enrollment_tier']==15 and r['case_id'] is None)
        gallery=core.verified(binding);ids=sorted(r['profile_id'] for r in gallery['profiles'])
        if len(ids)!=15:
            raise ValueError('Original15 galleries required')
        selections[candidate]={'single':ids[:1],'set':ids[:3],'all':ids};gallery_bindings[candidate]=binding
    plan={'schema':'s6d-focus-replay-plan.v1','prediction_index':authority['index'],'galleries':gallery_bindings,
        'selection_policy':'Fixed lexicographic profile IDs: first1,first3,all15; chosen before predictions/references. Same across every scene and tap.',
        'selected_profile_ids':selections,'cells':960,'modes':['T0_single_control','T1_single','T0_set_control','T2_set','T0_all_control','T2_all'],
        'code':core.bind(__file__),'app_policy':core.bind(APP/'edge_speech_pipeline/research_s6d.py'),
        'limitations':['Replay of frozen original prediction timing, not repaired-native results or GUI latency.',
            'No word timings: conservative token LCS only for unambiguous reference-person rows; mixed visible tokens remain explicitly unclassified.',
            'Display span coverage is estimated source-support coverage, not acoustic extraction or lexical correctness.',
            'Incomplete ambient references stay incomplete; no apparent perfect target-absent recall.']}
    core.save(output/'PLAN.json',plan)
    scoremap=core.verified(authority['scorer_map']);qraw=core.verified(authority['Q'])['rows']
    q={(r['case_id'],r['segment_index']):r for r in qraw}
    scenes={r['case_id']:r for r in core.verified(authority['bank'])['scenes']}
    inputs=core.verified(core.bind(core.S6B/'INPUT_INDEX.json',core.INPUT_SHA))['rows']
    inputmap={(r['case_id'],r['stream']):r for r in inputs}
    results=[];delays=[];started=time.perf_counter()
    for i,item in enumerate(indexrows):
        value=core.verified(item['result']);core.validate_payload(value,item)
        case=item['case_id'];candidate=item['candidate_id'];tap=item['stream']
        support_binding=inputmap[case,tap]['support'];support=core.verified(support_binding)['support']
        validate_support(scenes[case],support)
        gallery=names.gallery_for(value,scoremap)
        if gallery['manifest']!=gallery_bindings[candidate]:
            raise ValueError('Frozen prediction has a substituted gallery')
        turns=names.mapped_turns(value,support,q)
        profiles={r['profile_id']:r for r in gallery['profiles']}
        words_by_person=defaultdict(list)
        for t in turns:
            words_by_person[t['metadata_identity']]+=tokens(q[case,t['segment_index']]['transcript'])
        events=value['transcript_events']
        for selection,ids in selections[candidate].items():
            selected_people={profiles[pid]['metadata_identity'] for pid in ids}
            for filtered in (False,True):
                mode='T0' if not filtered else 'T1' if selection=='single' else 'T2'
                settings=S6DSettings(text_delivery=False,boundary_repair=False,transcript_mode=mode,selected_profile_ids=tuple(ids))
                state=PresentationState(settings);visible_history=[]
                for event in events:
                    payload=dict(event)
                    if event['event_type']=='transcript_label_revision':
                        prior=state.rows.get(event['utterance_id'],{})
                        payload['target_source_end_sec']=prior.get('source_end_sec')
                    row=state.consume(event['event_type'],payload,event['available_at_sec'])
                    if row and row.get('visible') and isinstance(row.get('source_start_sec'),(int,float)) and isinstance(row.get('source_end_sec'),(int,float)):
                        visible_history.append((event['available_at_sec'],row['source_start_sec'],row['source_end_sec']))
                finals=[r for r in state.rows.values() if r['final']]
                if [r['text'] for r in finals]!=[r['text'] for r in value['final_transcripts_latest']]:
                    raise ValueError('Presentation policy changed unfiltered committed raw words')
                visible=[r for r in finals if r['visible']]
                visible_spans=union([[round(r['source_start_sec']*16000),round(r['source_end_sec']*16000)] for r in visible
                    if r.get('source_start_sec') is not None and r.get('source_end_sec') is not None])
                target_spans=union([r for t in turns if t['metadata_identity'] in selected_people for r in (t['active_ranges'] or [])])
                other_spans=union([r for t in turns if t['metadata_identity'] not in selected_people for r in (t['active_ranges'] or [])])
                assigned=defaultdict(list);non_target_words=unclassified_words=0
                for row in visible:
                    span=[[round(row['source_start_sec']*16000),round(row['source_end_sec']*16000)]]
                    status,person=names.single_reference(span,turns,support['all_speaker_reference_complete'])
                    if person is not None:
                        assigned[person]+=tokens(row['text'])
                        if person not in selected_people:non_target_words+=len(tokens(row['text']))
                    else:unclassified_words+=len(tokens(row['text']))
                target_words=sum(len(words_by_person[p]) for p in selected_people)
                retained=sum(lcs(words_by_person[p],assigned[p]) for p in selected_people)
                eligible_turns=never=0
                for turn in turns:
                    if turn['metadata_identity'] not in selected_people or not turn['active_ranges']:continue
                    eligible_turns+=1;onset=min(a for a,b in turn['active_ranges'])/16000
                    times=[stamp for stamp,a,b in visible_history if samples(intersection([[round(a*16000),round(b*16000)]],turn['active_ranges']))>0]
                    delay=max(0.,min(times)-onset) if times else None
                    never+=delay is None
                    delays.append({'candidate':candidate,'tap':tap,'case':case,'selection':selection,'mode':mode,
                        'segment_index':turn['segment_index'],'visibility_delay_sec':delay,'never_visible':delay is None,
                        'scope':'First any visible row overlapping estimated target support; not exact word onset or guaranteed correct name'})
                results.append({'candidate':candidate,'tap':tap,'case':case,'selection':selection,'mode':mode,
                    'reference_complete':support['all_speaker_reference_complete'],'target_present':bool(target_words or target_spans),
                    'target_reference_words':target_words,'target_words_matched_conservative':retained,
                    'target_words_missed_or_unresolved':target_words-retained,
                    'visible_non_target_hypothesis_words_unambiguous':non_target_words,'visible_words_unclassified_mixed_or_incomplete':unclassified_words,
                    'visible_total_hypothesis_words':sum(len(tokens(r['text'])) for r in visible),
                    'target_active_samples':samples(target_spans),'target_active_samples_visible_span':samples(intersection(target_spans,visible_spans)),
                    'non_target_active_samples_visible_span':samples(intersection(other_spans,visible_spans)),
                    'target_turns_with_support':eligible_turns,'target_turns_never_visible':never,
                    'visible_final_rows':len(visible),'all_final_rows':len(finals),'revisions':state.revisions,
                    'raw_words_invariant':True,'prediction_sha256':item['result']['sha256']})
        if (i+1)%120==0:print(json.dumps({'done_predictions':i+1,'total_predictions':960,'elapsed_sec':time.perf_counter()-started}),flush=True)
    groups=defaultdict(list)
    for row in results:groups[row['candidate'],row['tap'],row['selection'],row['mode']].append(row)
    numeric=['target_reference_words','target_words_matched_conservative','target_words_missed_or_unresolved',
        'visible_non_target_hypothesis_words_unambiguous','visible_words_unclassified_mixed_or_incomplete','visible_total_hypothesis_words',
        'target_active_samples','target_active_samples_visible_span','non_target_active_samples_visible_span','target_turns_with_support','target_turns_never_visible','visible_final_rows','all_final_rows','revisions']
    aggregate=[]
    for key,rows in sorted(groups.items()):
        total={k:sum(r[k] for r in rows) for k in numeric}
        aggregate.append(dict(zip(['candidate','tap','selection','mode'],key),cases=len(rows),
            target_present_cases=sum(r['target_present'] for r in rows),target_absent_cases=sum(not r['target_present'] for r in rows),
            complete_reference_cases=sum(r['reference_complete'] for r in rows),**total))
    write_csv(output/'PER_CASE.csv',results);write_csv(output/'VISIBILITY_DELAYS.csv',delays);write_csv(output/'AGGREGATES.csv',aggregate)
    core.save(output/'RESULT.json',{'schema':'s6d-focus-replay.v1','status':'COMPLETE_REPLAY_WITH_LIMITS','predictions':960,'policy_cells':len(results),
        'neural_calls':0,'gui_tested':False,'physical_tested':False,'cm5_tested':False,'all_raw_words_invariant':True,
        'elapsed_sec':time.perf_counter()-started,'plan':core.bind(output/'PLAN.json'),'aggregate':aggregate,
        'full_local_tables':[core.bind(output/x) for x in ['PER_CASE.csv','VISIBILITY_DELAYS.csv','AGGREGATES.csv']],
        'not_claimed':['Visibility-delay clocks are saved modeled availability, not GUI/phonetic latency.',
            'Unclassified visible words are not zero leakage; conservative word misses combine ASR deletion, mapping ambiguity and hidden text.',
            'No direction or repaired-native usefulness result is inferred from this presentation-only replay.']})
    print(json.dumps({'result':str(output/'RESULT.json'),'policy_cells':len(results),'elapsed_sec':time.perf_counter()-started}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
