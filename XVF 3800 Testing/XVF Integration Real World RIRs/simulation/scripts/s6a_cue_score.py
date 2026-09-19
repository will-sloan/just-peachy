"""Reference-only scoring for S6 causal trackers. See README_S6A_CUES.md."""
from __future__ import annotations
import bisect
from collections import Counter,defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import time
import numpy as np
from s6a_cues import (read,save,binding,verified,write_csv,digest,load_jobs,resolve_native,
                     DEFAULT_REPORT,H2,PROFILES,now)
from s6a_support_metrics import union,intersection,subtract,samples,validate_support
from s6a_text_metrics import reference_layout,_backend,_rate,normalize,CP_SCOPE

POLICY={
    'schema':'jp_s6a_causal_tracking_metrics_v1',
    'reference':'All240 unchanged source references; unknown environmental speech excluded from complete-reference identity metrics',
    'state':'Latest first decision already available at query time; no retroactive revision applied to first output',
    'expiry_sec':.75,
    'timeline':'Integer sample intervals, approximate saved capture/output alignment; positive source activity estimated at20ms',
    'unknown':'No decision, explicit Unknown, or decision older than0.75s of input endpoint',
    'sole_speech':'Turn active support after subtracting every other source active support; no simultaneous identity oracle',
    'false_merge':'Within each predicted label, sole-speech seconds outside its dominant reference identity; mapping used only for diagnostics',
    'turn_mode':'Largest duration label including Unknown; ties or Unknown-largest remain unassigned',
    'returns':'Immediate previous occurrence of same reference identity, including missing/tied predecessor; after-other separately flagged',
    'attributed_text':'Exact final words grouped by actual predicted final label, one global assignment; no word alignment or DER',
    'controls':'One-person and all-unknown diagnostics retain same lexical output; both must fail the combined unassigned/conflation check on a two-speaker fixture',
    'revisions':'Count actual emitted operation events and preserve first decisions; no claim revised identity is correct without separate analysis',
}


def state_intersections(decisions,start,stop,*,control=None):
    """Exact interval integration, without per-frame rounding or future labels."""
    if stop<=start:return []
    if control=='all_unknown':return [(start,stop,'Unknown')]
    if control=='one_person':return [(start,stop,'AllSpeaker')]
    stamps=[round(d['available_at_sec']*16000) for d in decisions]
    boundaries={start,stop}
    for d,t in zip(decisions,stamps):
        if start<t<stop:boundaries.add(t)
        expiry=round((d['source_end_sec']+POLICY['expiry_sec'])*16000)
        if start<expiry<stop:boundaries.add(expiry)
    ordered=sorted(boundaries);out=[]
    for a,b in zip(ordered,ordered[1:]):
        i=bisect.bisect_right(stamps,a)-1
        label='Unknown'
        if i>=0 and a<round((decisions[i]['source_end_sec']+POLICY['expiry_sec'])*16000):
            label=decisions[i]['anonymous_label']
            if not label or label.lower() in ('unknown','unassigned'):label='Unknown'
        out.append((a,b,label))
    return out


def tracking_metrics(support,stream,decisions,duration_samples,*,control=None):
    mapping=support['output_mappings'][stream]['source_with_rir_to_output_offset_samples']
    if mapping is None:
        unscored=[dict(segment_index=t['segment_index'],speaker_key=t['speaker_key'],participant_id=t['participant_id'],
                       source_id=t['source_id'],whole_clip_bin=t['whole_clip_bin'],active_duration_bin=t['active_duration_bin'],
                       whole_clip_duration_s=t['whole_clip_duration_s'],activity_available=t['activity_available'],
                       active_samples=None,sole_active_samples=None,unknown_samples=None,known_samples=None,
                       modal_label=None,predicted_labels=None,first_source_sample=t['file_support'][0][0],
                       label_samples={},return_status='UNAVAILABLE_ALIGNMENT',return_after_other=None,
                       mapping_available=False) for t in support['turns']]
        return dict(status='UNAVAILABLE_OUTPUT_ALIGNMENT',turns=unscored,source_turns=len(support['turns']),
                    supported_turns=0,unknown_turns=None,sole_active_samples=None,false_merge_samples=None,
                    known_samples=None,unknown_samples=None,return_consistent=0,return_inconsistent=0,return_unknown=0)
    ranges={}
    for turn in support['turns']:
        active=turn['active_ranges'] if turn['activity_available'] else []
        ranges[turn['segment_index']]=union([[max(0,a+mapping),min(duration_samples,b+mapping)] for a,b in active])
    label_identity=defaultdict(Counter);identity_label=defaultdict(Counter);rows=[];sole_total=known=unknown=0
    for turn in sorted(support['turns'],key=lambda t:t['file_support'][0][0]):
        sid=turn['segment_index'];own=ranges[sid]
        others=union([span for key,value in ranges.items() if key!=sid for span in value])
        sole=subtract(own,others);counts=Counter()
        for start,stop in sole:
            for a,b,label in state_intersections(decisions,start,stop,control=control):counts[label]+=b-a
        denominator=samples(sole);sole_total+=denominator;unknown+=counts['Unknown'];known+=denominator-counts['Unknown']
        for label,count in counts.items():
            if label!='Unknown':
                label_identity[label][turn['speaker_key']]+=count
                identity_label[turn['speaker_key']][label]+=count
        ranking=counts.most_common()
        winner=(ranking[0][0] if ranking and ranking[0][0]!='Unknown'
                and (len(ranking)==1 or ranking[0][1]>ranking[1][1]) else None)
        rows.append(dict(segment_index=sid,speaker_key=turn['speaker_key'],participant_id=turn['participant_id'],
                         source_id=turn['source_id'],whole_clip_bin=turn['whole_clip_bin'],
                         active_duration_bin=turn['active_duration_bin'],whole_clip_duration_s=turn['whole_clip_duration_s'],
                         activity_available=turn['activity_available'],active_samples=samples(own),sole_active_samples=denominator,
                         unknown_samples=counts['Unknown'],known_samples=denominator-counts['Unknown'],
                         modal_label=winner,predicted_labels=len([k for k,v in counts.items() if k!='Unknown' and v]),
                         first_source_sample=turn['file_support'][0][0],label_samples=dict(counts),mapping_available=True))
    false_merge=sum(sum(c.values())-max(c.values()) for c in label_identity.values() if c)
    fragmented=sum(max(0,len(c)-1) for c in identity_label.values())
    previous={};consistent=inconsistent=missing=0
    for i,row in enumerate(rows):
        earlier=previous.get(row['speaker_key'])
        if earlier is not None:
            old_index,old=earlier
            after_other=any(r['speaker_key']!=row['speaker_key'] for r in rows[old_index+1:i])
            if old['modal_label'] is None or row['modal_label'] is None:status='UNKNOWN';missing+=1
            elif old['modal_label']==row['modal_label']:status='CONSISTENT';consistent+=1
            else:status='INCONSISTENT';inconsistent+=1
            row['return_status']=status;row['return_after_other']=after_other
        else:row['return_status']='FIRST';row['return_after_other']=False
        previous[row['speaker_key']]=(i,row)
    return dict(status='SCORED_APPROXIMATE_SOURCE_SUPPORT' if support['all_speaker_reference_complete'] else 'LIMITED_KNOWN_TARGETS_ONLY',
                turns=rows,source_turns=len(rows),supported_turns=sum(r['sole_active_samples']>0 for r in rows),
                unknown_turns=sum(r['modal_label'] is None for r in rows),sole_active_samples=sole_total,
                false_merge_samples=false_merge,known_samples=known,unknown_samples=unknown,
                false_merge_fraction_of_known=false_merge/known if known else None,
                unknown_fraction=unknown/sole_total if sole_total else None,
                unassigned_or_conflated_fraction=(unknown+false_merge)/sole_total if sole_total else None,
                excess_labels_per_reference_identity=fragmented,
                turn_multilabel_count=sum(r['predicted_labels']>1 for r in rows),
                return_consistent=consistent,return_inconsistent=inconsistent,return_unknown=missing)


def attributed(scene,finals,cp):
    layout=reference_layout(scene)
    if not layout['complete'] or not layout['reference']:
        return dict(status='NOT_APPLICABLE_INCOMPLETE_OR_EMPTY',wer=None)
    hyp=defaultdict(list)
    for row in finals:
        text=normalize(row['text'])
        if text:hyp[row.get('speaker') or 'Unknown'].append(text)
    hyp={k:' '.join(v) for k,v in hyp.items()}
    result=cp({k:' '.join(v) for k,v in layout['streams'].items()},hyp,reference_sort=False,hypothesis_sort=False)
    return _rate(result,sum(len(t.split()) for t in hyp.values()),'CP_WER',CP_SCOPE)


def baseline_parity(report):
    """Recomputed exact vectors must reproduce historical B0 label decisions."""
    import sys
    from s6a_common import SNAPSHOT
    if str(SNAPSHOT) not in sys.path:sys.path.insert(0,str(SNAPSHOT))
    from edge_speech_pipeline.speakers import SpeakerTracker
    from app.edge_speech_pipeline.config import PipelineConfig
    class EmptyProfiles:
        def load(self):return {}
    index=read(report/'cues/FEATURE_INDEX.json');rows=[]
    for item in index['rows']:
        if item['status']!='COMPLETE':continue
        feature=read(verified(item['result']));vectors=np.load(verified(feature['vectors']),allow_pickle=False)['vectors']
        tracker=SpeakerTracker(PipelineConfig(),EmptyProfiles());wrong=[]
        for j,(vector,record) in enumerate(zip(vectors,feature['features'])):
            actual=tracker.update(vector,record['source_end_sec']).anonymous_label
            if actual!=record['native_anonymous_label']:wrong.append(dict(index=j,actual=actual,native=record['native_anonymous_label']))
        rows.append(dict(case_id=item['case_id'],stream=item['stream'],windows=len(vectors),mismatches=wrong,
                         feature_binding=item['result']))
    count=sum(len(r['mismatches']) for r in rows)
    result=dict(schema='jp_s6a_actual_vector_B0_parity_v1',status='PASS' if not count and len(rows)==480 else 'PARTIAL' if not count else 'FAIL',
                outputs=len(rows),windows=sum(r['windows'] for r in rows),mismatches=count,rows=rows,
                tracker_source=binding(SNAPSHOT/'edge_speech_pipeline/speakers.py'),created_utc=now())
    save(report/'CUE_FEATURE_B0_PARITY.json',result)
    if count:raise ValueError('actual vectors failed historical B0 label parity')
    return result


def aggregate(rows):
    output=[]
    fields=('sole_active_samples','false_merge_samples','known_samples','unknown_samples','source_turns','supported_turns',
            'unknown_turns','turn_multilabel_count','return_consistent','return_inconsistent','return_unknown')
    for profile in list(PROFILES)+['CONTROL_ONE_PERSON','CONTROL_ALL_UNKNOWN']:
        for stream in ('O0','O1'):
            for population in ('ALL_COMPLETE_NONEMPTY','PRIMARY_NONOVERLAP','COMPLETE_OVERLAP','INCOMPLETE_REFERENCE','STRICT_EMPTY_REFERENCE'):
                selected=[r for r in rows if r['profile']==profile and r['stream']==stream
                          and (r['population'] in ('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP') if population=='ALL_COMPLETE_NONEMPTY' else r['population']==population)]
                if not selected:continue
                merged=dict(profile=profile,stream=stream,population=population,scenes=len(selected),
                            alignment_unavailable=sum(r['tracking_status']=='UNAVAILABLE_OUTPUT_ALIGNMENT' for r in selected))
                for key in fields:merged[key]=sum(r.get(key) or 0 for r in selected)
                for key in ('cp_errors','cp_reference_words','cp_substitutions','cp_deletions','cp_insertions','decisions','tracks','splits','merges','revisions'):
                    merged[key]=sum(r.get(key) or 0 for r in selected)
                merged['cpwer']=merged['cp_errors']/merged['cp_reference_words'] if merged['cp_reference_words'] else None
                merged['unknown_fraction']=merged['unknown_samples']/merged['sole_active_samples'] if merged['sole_active_samples'] else None
                merged['false_merge_fraction_of_known']=merged['false_merge_samples']/merged['known_samples'] if merged['known_samples'] else None
                merged['unassigned_or_conflated_fraction']=(merged['unknown_samples']+merged['false_merge_samples'])/merged['sole_active_samples'] if merged['sole_active_samples'] else None
                output.append(merged)
    return output


def score(report=DEFAULT_REPORT):
    report=Path(report);jobs,bank=load_jobs(report);scenes={s['case_id']:s for s in bank['scenes']}
    joblookup={(j['case_id'],j['stream']):j for j in jobs};folder=report/'cues'
    reference_index=read(folder/'REFERENCE_INDEX.json')
    if reference_index['completed']!=2880:raise ValueError('require all2880profileoutputs before finalscoring')
    source_index=read(report/'support/FROZEN_SUPPORT_INDEX.json')
    sources={r['case_id']:r for r in source_index['scenes']};_,cp=_backend()
    rows=[];turn_rows=[];short_rows=[];started=time.perf_counter();code=binding(__file__)
    for item in reference_index['rows']:
        cid,stream,profile=item['case_id'],item['stream'],item['profile'];job=joblookup[(cid,stream)]
        prediction=read(verified(item['result']));support_binding=sources[cid]['support']
        support=read(verified(support_binding))['support'];validate_support(scenes[cid],support)
        native=resolve_native(job);duration_samples=native['receipt']['adapter']['samples']
        choices=[(profile,None,prediction)]
        if profile=='B0':
            for name,control in (('CONTROL_ONE_PERSON','one_person'),('CONTROL_ALL_UNKNOWN','all_unknown')):
                label='AllSpeaker' if control=='one_person' else 'Unknown'
                control_prediction=dict(prediction,final_transcripts=[dict(f,speaker=label) for f in prediction['final_transcripts']])
                choices.append((name,control,control_prediction))
        for name,control,value in choices:
            identity=dict(prediction_sha256=item['result']['sha256'],support=support_binding,code=code,
                          profile=name,policy_sha256=digest(POLICY))
            target=folder/'scores'/cid/stream/(name+'.json')
            if target.exists():
                result=read(target)
                if result['analysis_identity']!=digest(identity):raise ValueError('score cache requires versioned output')
            else:
                track=tracking_metrics(support,stream,value['decisions'],duration_samples,control=control)
                text=attributed(scenes[cid],value['final_transcripts'],cp)
                lineage=Counter(e['event'] for d in value['decisions'] for e in d.get('lineage',[])) if control is None else Counter()
                result=dict(schema=POLICY['schema'],analysis_identity=digest(identity),identity=identity,case_id=cid,
                            stream=stream,profile=name,population=reference_layout(scenes[cid])['population'],
                            tracking=track,attributed_cpwer=text,lineage_counts=dict(lineage),
                            hypothesis_words=sum(len(normalize(f['text']).split()) for f in value['final_transcripts']),
                            policy=POLICY,created_utc=now())
                save(target,result)
            counts=result['attributed_cpwer'].get('word_counts',{});track=result['tracking'];lineage=result['lineage_counts']
            row=dict(case_id=cid,stream=stream,profile=name,split=scenes[cid]['split'],population=result['population'],
                     tracking_status=track['status'],cp_status=result['attributed_cpwer']['status'],
                     cp_errors=counts.get('errors'),cp_reference_words=counts.get('reference_words'),
                     cp_substitutions=counts.get('substitutions'),cp_deletions=counts.get('deletions'),cp_insertions=counts.get('insertions'),
                     decisions=len(value['decisions']),tracks=value['snapshot']['track_count'] if control is None else 1,
                     splits=lineage.get('split_provisional_branch',0),merges=lineage.get('merge_provisional_branch',0),
                     revisions=lineage.get('label_revision',0),policy_wall_sec=value['policy_wall_sec'] if control is None else 0.,
                     **{k:v for k,v in track.items() if k not in ('turns','status')})
            rows.append(row)
            for turn in track['turns']:
                turn_rows.append(dict(case_id=cid,stream=stream,profile=name,population=result['population'],
                                      **{k:v for k,v in turn.items() if k!='label_samples'}))
            for bin_name in ('<1s','1-<2s','>=2s'):
                selected=[t for t in track['turns'] if t['whole_clip_bin']==bin_name]
                short_rows.append(dict(case_id=cid,stream=stream,profile=name,population=result['population'],duration_bin=bin_name,
                                       source_turns=len(selected),turns_with_known_modal_label=sum(t['modal_label'] is not None for t in selected),
                                       mapped_turns=sum(t['mapping_available'] for t in selected),
                                       turns_with_any_known_support=sum((t['known_samples'] or 0)>0 for t in selected),
                                       sole_active_samples=sum(t['sole_active_samples'] or 0 for t in selected),
                                       unknown_samples=sum(t['unknown_samples'] or 0 for t in selected)))
        if len(rows)%240==0:print(json.dumps(dict(phase='REFERENCE_SCORING',rows=len(rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    write_csv(report/'REFERENCE_PROFILE_SCENE_RESULTS.csv',rows)
    write_csv(report/'REFERENCE_PROFILE_TURN_RESULTS.csv',turn_rows)
    write_csv(report/'REFERENCE_SHORT_TURN_RESULTS.csv',short_rows)
    summary=aggregate(rows);write_csv(report/'REFERENCE_PROFILE_RESULTS.csv',summary)
    parity=baseline_parity(report)
    totals=Counter(r['profile'] for r in rows)
    result=dict(schema='jp_s6a_reference_scoring_receipt_v1',status='COMPLETE' if len(rows)==3840 and parity['status']=='PASS' else 'PARTIAL',
                outputs=len(rows),six_reference_outputs=2880,diagnostic_control_outputs=960,counts_by_profile=dict(totals),
                reference_index=binding(folder/'REFERENCE_INDEX.json'),source_index=binding(report/'support/FROZEN_SUPPORT_INDEX.json'),
                tables=[binding(report/name) for name in ('REFERENCE_PROFILE_SCENE_RESULTS.csv','REFERENCE_PROFILE_TURN_RESULTS.csv',
                                                         'REFERENCE_SHORT_TURN_RESULTS.csv','REFERENCE_PROFILE_RESULTS.csv')],
                actual_vector_B0_parity=binding(report/'CUE_FEATURE_B0_PARITY.json'),policy=POLICY,
                elapsed_sec=time.perf_counter()-started,created_utc=now(),summary=summary)
    save(report/'REFERENCE_PROFILE_RECEIPT.json',result);return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    args=parser.parse_args();result=score(args.report)
    print(json.dumps({k:v for k,v in result.items() if k!='summary'},indent=2))
