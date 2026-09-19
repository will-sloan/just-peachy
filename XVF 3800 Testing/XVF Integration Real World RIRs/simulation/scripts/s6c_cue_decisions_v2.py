"""Bound actual R0 feature and v3 cue-action diagnostics; README_S6C_CUE_DECISIONS_V2.md."""
from __future__ import annotations
import argparse
import bisect
import collections
from copy import deepcopy
import gzip
import hashlib
import json
import math
from pathlib import Path
import time
import s6c_enrollment as E
import numpy as np

S6B=E.SIM/'reports/S6B/20260909T230840Z'
OUT=E.REPORT/'cue_decisions_v2'
FEATURE_AUTHORITY=E.REPORT/'cue_decisions_v1/R0_FEATURE_CUE_AUDIT.json'
SEALED_SHA='2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e'
POLICY=dict(reference_single_person_min_window_fraction=.5,reference_other_person_max_sec=0.,
    pair_disjoint_waveforms=True,ambiguity_cosine_low=.2,ambiguity_cosine_high=.65,
    angle_change_deg=35.,receipt_max_age_sec=.25,minimum_delivery_reliability=.2,
    production_fit=False,reference_inputs_to_predictor=False,
    pairing='All within-case disjoint qualifying observation pairs; repeated source clips are separately tagged; not independent statistical trials')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def verified(binding):
    E.verify(binding)
    return E.read(binding['path'])

def sealed():
    binding=E.bind(S6B/'LOCAL_ARTIFACT_INDEX.json')
    if binding['sha256']!=SEALED_SHA:raise ValueError('Sealed S6B index differs')
    return verified(binding)

def old_binding(index,name):
    wanted=(S6B/name).resolve()
    rows=[r for r in index['artifacts'] if Path(r['path']).resolve()==wanted]
    if len(rows)!=1:raise ValueError('Sealed authority must resolve once: '+str(wanted))
    return {k:rows[0][k] for k in ('path','sha256','bytes') if k in rows[0]}

def freeze():
    target=OUT/'CUE_DECISION_PLAN.json'
    if target.exists():
        value=E.read(target)
        for b in value['bindings']:E.verify(b)
        return value
    authority=sealed()
    paths=[Path(__file__),Path(__file__).with_name('README_S6C_CUE_DECISIONS_V2.md'),Path(E.__file__),
        E.REPORT/'EPOCH1_EXECUTION_MANIFEST.json',E.REPORT/'epoch1/CHALLENGE_N00_PREDICTION_INDEX.json',
        E.REPORT/'cue_audit_v1/PHYSICAL_CUE_AUDIT.json',FEATURE_AUTHORITY,
        E.REPORT/'cue_decisions_v1/N00_CUE_ACTION_AUDIT.json',Path(__file__).with_name('s6c_cue_decisions.py'),Path(__file__).with_name('README_S6C_CUE_DECISIONS.md')]
    bindings=[E.bind(p) for p in paths]
    bindings += [E.bind(S6B/'LOCAL_ARTIFACT_INDEX.json')]
    bindings += [old_binding(authority,n) for n in ('INPUT_INDEX.json','EPOCH2_EXECUTION_MANIFEST.json','epoch2/FULL_ALL_NEURAL_INDEX.json')]
    predictions=E.read(paths[4])
    if predictions['status']!='COMPLETE' or predictions['completed']!=7392 or len(predictions['rows'])!=7392:
        raise ValueError('Expected closed 66 x56 x2 N00 challenge')
    keys={(r['candidate_id'],r['case_id'],r['stream']) for r in predictions['rows']}
    if len(keys)!=7392 or len(predictions['profiles'])!=66 or len(predictions['case_ids'])!=56:
        raise ValueError('N00 output grid differs')
    if keys!={(p,c,t) for p in predictions['profiles'] for c in predictions['case_ids'] for t in ('O0','O1')}:
        raise ValueError('Missing exact profile/case/tap combination')
    value=dict(schema='s6c-cue-decision-plan.v1',status='FROZEN_BEFORE_NEW_FEATURE_AND_ACTION_SUMMARIES',
        created_utc=E.utc(),bindings=bindings,policy=POLICY,
        physical_trace_denominator=240,feature_output_denominator=480,decision_output_denominator=7392,
        decision_scope='66 real v3 N00 policies x56 challenge cases x2 taps; no enrollment names in this branch',
        scope='Evaluator-only joins to already computed vectors and actual policy outputs; no new model call or predictor clone')
    E.save(target,value)
    return value

def spans_union(spans):
    result=[]
    for a,b in sorted(spans):
        if b<=a:continue
        if result and a<=result[-1][1]+1e-9:result[-1][1]=max(b,result[-1][1])
        else:result.append([a,b])
    return result

def reference_window(support,tap,start,end):
    offset=support['output_mappings'][tap]['source_with_rir_to_output_offset_samples']
    people=collections.defaultdict(list)
    sources=collections.defaultdict(set)
    for turn in support['turns']:
        clipped=[[max(start,(a+offset)/16000),min(end,(b+offset)/16000)] for a,b in turn['support_ranges']]
        clipped=[(a,b) for a,b in clipped if b>a]
        if clipped:
            people[turn['speaker_key']].extend(clipped)
            sources[turn['speaker_key']].add(turn['source_id'])
    seconds={p:sum(b-a for a,b in spans_union(r)) for p,r in people.items()}
    if len(seconds)==1:
        person=next(iter(seconds))
        fraction=seconds[person]/(end-start)
        if fraction+1e-9>=POLICY['reference_single_person_min_window_fraction']:
            return dict(status='QUALIFIED_SINGLE_REFERENCE_PERSON',person=person,
                reference_fraction=fraction,source_ids=sorted(sources[person]))
    return dict(status='MULTIPLE_REFERENCE_PEOPLE' if len(seconds)>1 else 'INSUFFICIENT_ESTIMATED_REFERENCE_ACTIVITY',
                person=None,reference_support_sec=seconds,source_ids=[])

def delivered_at(rows,times,now):
    i=bisect.bisect_right(times,now)-1
    if i<0:return dict(status='NOT_YET_DELIVERED',usable=False,row=None,receipt_age_sec=None)
    row=rows[i];age=now-row['available_at_sec'];angle=row.get('angle_deg')
    valid=row.get('valid') is True and angle is not None and math.isfinite(angle) and 0<=angle<=180
    usable=valid and age<=POLICY['receipt_max_age_sec'] and row.get('reliability',0)>=POLICY['minimum_delivery_reliability']
    return dict(status='DELIVERY_VALID' if usable else 'STALE_RECEIPT' if age>POLICY['receipt_max_age_sec'] else 'INVALID_OR_LOW_RELIABILITY',
        usable=usable,row=row,receipt_age_sec=age,
        DSP_source_age_sec=None,scope='Host-delivery prerequisite only, not full tracker cue qualification')

def summary_values(values):
    if not values:return dict(count=0,mean=None,median=None,p10=None,p90=None)
    a=np.asarray(values,float)
    return dict(count=len(values),mean=float(a.mean()),median=float(np.median(a)),
                p10=float(np.quantile(a,.1)),p90=float(np.quantile(a,.9)))

def features():
    freeze();target=OUT/'R0_FEATURE_CUE_AUDIT.json'
    if target.exists():raise ValueError('Completed feature output retained; do not overwrite')
    index=sealed()
    inputs=verified(old_binding(index,'INPUT_INDEX.json'))['rows']
    old=verified(old_binding(index,'EPOCH2_EXECUTION_MANIFEST.json'))
    native=verified(old_binding(index,'epoch2/FULL_ALL_NEURAL_INDEX.json'))
    native_rows={(r['case_id'],r['stream']):r['receipt'] for r in native['rows'] if r['recipe_id']=='R0'}
    if len(inputs)!=480 or len(native_rows)!=480:raise ValueError('Full paired R0 bank required')
    rows=[];groups=collections.defaultdict(list);started=time.perf_counter()
    for item in inputs:
        cid,tap=item['case_id'],item['stream'];binding=native_rows[cid,tap]
        receipt=verified(binding)
        if receipt['status']!='COMPLETE' or receipt['identity']['execution_digest']!=old['execution_digest'] or receipt['identity']['recipe_id']!='R0':
            raise ValueError('Wrong native R0 execution')
        if receipt['job_key']!=digest(receipt['identity']) or receipt['identity']['audio']!=item['audio']:
            raise ValueError('Wrong native input binding')
        evidence=verified(receipt['evidence']);E.verify(receipt['vectors'])
        if evidence['vectors']!=receipt['vectors'] or evidence['job_key']!=receipt['job_key'] or evidence['identity']!=receipt['identity']:
            raise ValueError('Evidence/receipt identity mismatch')
        with np.load(evidence['vectors']['path'],allow_pickle=False) as z:vectors=z['vectors']
        if vectors.shape!=(len(evidence['features']),192) or not np.all(np.isfinite(vectors)):raise ValueError('Bad native vectors')
        support=verified(item['support'])['support'];E.verify(item['telemetry'])
        telemetry=[json.loads(line) for line in Path(item['telemetry']['path']).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        times=[r['available_at_sec'] for r in telemetry]
        if times!=sorted(times):raise ValueError('Delivered timeline out of order')
        window_rows=[];pair_rows=[]
        for i,f in enumerate(evidence['features']):
            start,end,ready=f['source_start_sec'],f['source_end_sec'],f['available_at_sec']
            if ready<end-1e-9:raise ValueError('Embedding arrived before complete window')
            cue=delivered_at(telemetry,times,ready)
            window_rows.append(dict(index=i,evidence_id=f.get('evidence_event_id',f'embedding:{i+1:08d}'),
                source_start_sec=start,source_end_sec=end,available_at_sec=ready,
                inference_to_source_end_sec=ready-end,reference=reference_window(support,tap,start,end),
                delivered_cue=cue,admission=f['admission']))
        norms=np.linalg.norm(vectors,axis=1)
        normalized=vectors/np.maximum(norms[:,None],1e-12)
        similarities=normalized@normalized.T
        for i,left in enumerate(window_rows):
            if left['reference']['person'] is None:continue
            for j in range(i+1,len(window_rows)):
                right=window_rows[j]
                if right['reference']['person'] is None or right['source_start_sec']<left['source_end_sec']-1e-9:continue
                cos=float(similarities[i,j]);same=left['reference']['person']==right['reference']['person']
                repeated=bool(set(left['reference']['source_ids'])&set(right['reference']['source_ids']))
                both=left['delivered_cue']['usable'] and right['delivered_cue']['usable']
                delta=abs(left['delivered_cue']['row']['angle_deg']-right['delivered_cue']['row']['angle_deg']) if both else None
                ambiguous=POLICY['ambiguity_cosine_low']<=cos<=POLICY['ambiguity_cosine_high']
                pair=dict(left=i,right=j,same_reference_person=same,shared_original_source_id=repeated,
                    waveform_windows_disjoint=True,cosine=cos,voice_ambiguous_band=ambiguous,
                    both_delivery_cues_usable=both,absolute_direction_difference_deg=delta)
                pair_rows.append(pair)
                groups[(tap,same,repeated,ambiguous)].append(pair)
        value=dict(case_id=cid,stream=tap,physical_trace_units_not_additive=1,
            bindings=[binding,receipt['evidence'],receipt['vectors'],item['support'],item['telemetry']],
            source_with_rir_mapping=support['output_mappings'][tap],features=window_rows,pairs=pair_rows)
        p=OUT/'features'/cid/(tap+'.json');E.save(p,value);rows.append(dict(case_id=cid,stream=tap,result=E.bind(p),features=len(window_rows),pairs=len(pair_rows)))
        if len(rows)%40==0:print(json.dumps(dict(phase='R0_FEATURE_CUES',completed=len(rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    stats=[]
    for (tap,same,repeated,ambiguous),pairs in sorted(groups.items()):
        angles=[p['absolute_direction_difference_deg'] for p in pairs if p['both_delivery_cues_usable']]
        stats.append(dict(stream=tap,same_reference_person=same,shared_original_source_id=repeated,voice_ambiguous_band=ambiguous,
            pair_count=len(pairs),angle_pair_count=len(angles),cue_coverage=len(angles)/len(pairs),
            cosine=summary_values([p['cosine'] for p in pairs]),absolute_angle_difference_deg=summary_values(angles),
            angle_difference_at_least35=sum(v>=35 for v in angles),angle_difference_below35=sum(v<35 for v in angles)))
    result=dict(status='COMPLETE_MODEL_FREE_R0_FEATURE_DIAGNOSTIC',schema='s6c-feature-cue-audit.v1',
        created_utc=E.utc(),plan=E.bind(OUT/'CUE_DECISION_PLAN.json'),rows=rows,output_tap_rows=480,physical_traces=240,
        feature_count=sum(r['features'] for r in rows),pair_count=sum(r['pairs'] for r in rows),pair_summaries=stats,
        new_model_calls=0,production_updates=0,
        limitations=['R0 .5s windows, actual embeddings; scoreband is a descriptive pairwise ambiguity stratum, not a tracker uncertainty posterior.',
            'No relative angle is invented when either delivered cue is invalid; missing pairs remain denominators.',
            'Shared original clip pairs are identified; disjoint windows and all-pair counts do not imply independent utterances or statistical replicates.',
            'Reference activity and existing tap offsets are estimated scoring support, not runtime gates or exact phonetic alignment.',
            'RIR50ms convention already present in source-with-RIR support; only saved output offset added once.',
            'A held host-recent cue has unknown DSP source age; this audit does not establish complete tracker eligibility.'])
    E.save(target,result);return E.bind(target)

def reduced(profile):
    p=deepcopy(profile);p.pop('profile_id',None);p['tracker']['cues_enabled']=False; p['xvf']['mode']='none'
    return p

def matched_cue_route(parent,candidate):
    return (parent['tracker']['cues_enabled'] is False and candidate['tracker']['cues_enabled'] is True and
            parent['xvf']['mode']=='none' and candidate['xvf']['mode']=='tracking_only' and
            reduced(parent)==reduced(candidate))

def relation(a,b):
    if a.get('tracker_id') is None or b.get('tracker_id') is None:return 'UNKNOWN'
    return 'SAME' if a['tracker_id']==b['tracker_id'] else 'DIFFERENT'

def action_counts(value):
    counts=collections.Counter();reasons=collections.Counter();events=collections.Counter()
    for d in value['decisions']:
        counts['decisions']+=1;counts['assigned']+=d.get('tracker_id') is not None
        cue=d.get('cue',{});reasons[cue.get('reason','audio_gate_or_no_cue_stage')]+=1
        counts['qualified_bearing']+=cue.get('qualified_bearing_deg') is not None
        contributions=cue.get('candidate_contributions',{})
        counts['logged_joint_candidate_comparisons']+=len(contributions)
        counts['decisions_with_logged_nonzero_spatial_contribution']+=any(abs(r.get('cue_score',0))>1e-12 for r in contributions.values())
        counts['borderline_existing_selected']+=str(d.get('joint_choice')) in contributions and contributions[str(d.get('joint_choice'))]['borderline']
        counts['borderline_selected_with_positive_cue']+=str(d.get('joint_choice')) in contributions and contributions[str(d.get('joint_choice'))]['borderline'] and contributions[str(d.get('joint_choice'))]['cue_score']>0
        for event in d['lineage']:events[event['event']]+=1
    return dict(counts=dict(counts),cue_reasons=dict(reasons),actual_lineage_events=dict(events),
        transcript_events=len(value['transcript_events']),identity_queries=sum(r.get('identity',{}).get('query_executed',False) for r in value['decisions']))

def trace(value,index,feature_rows):
    d=value['decisions'][index];eid=d['evidence_id'];events=[]
    for event in value['transcript_events']:
        if event.get('evidence_id')==eid or eid in event.get('evidence_ids',[]):events.append(event)
    rows=value['_audit_delivered_rows']
    delivered=(delivered_at(rows,[r['available_at_sec'] for r in rows],d['available_at_sec']) if rows is not None
               else dict(status='CUES_OFF',usable=False,row=None))
    return dict(actual_decision=d,actual_delivered_input=delivered,
        actual_embedding_support={k:feature_rows[index][k] for k in ('source_start_sec','source_end_sec','available_at_sec','admission')},
        linked_actual_display_events=events,display_link='Explicit matching evidence_id/evidence_ids only; no fabricated transcript attribution',
        named_branch='Identity none in N00; separate actual-C and native-gallery proofs cover naming')

def decisions():
    freeze();target=OUT/'N00_CUE_ACTION_AUDIT.json'
    if target.exists():raise ValueError('Completed action output retained; do not overwrite')
    feature_index=E.read(FEATURE_AUTHORITY)
    if feature_index['status']!='COMPLETE_MODEL_FREE_R0_FEATURE_DIAGNOSTIC':raise ValueError('Feature audit not complete')
    fmap={(r['case_id'],r['stream']):r['result'] for r in feature_index['rows']}
    idx=E.read(E.REPORT/'epoch1/CHALLENGE_N00_PREDICTION_INDEX.json')
    spec=E.read(E.REPORT/'EPOCH1_EXECUTION_MANIFEST.json')
    profiles={(r['candidate_id'],r['asr_tap']):r for r in spec['profiles'] if r['candidate_id'] in idx['profiles']}
    indexed={(r['candidate_id'],r['case_id'],r['stream']):r for r in idx['rows']}
    matched=[]
    for (pid,tap),p in profiles.items():
        if p['cue_condition']=='CUES_OFF':continue
        if p['profile']['xvf']['mode']!='tracking_only':continue
        parents=sorted(qid for (qid,qtap),q in profiles.items() if qtap==tap and q['cue_condition']=='CUES_OFF' and matched_cue_route(q['profile'],p['profile']))
        if parents:
            parent=profiles[parents[0],tap]['profile']
            if parent['tracker']['cues_enabled'] or parent['xvf']['mode']!='none' or not p['profile']['tracker']['cues_enabled']:
                raise ValueError('Matched route is not a strict none-to-tracking-only cue toggle')
            matched.append(dict(parent=parents[0],equivalent_parent_config_ids=parents,candidate=pid,stream=tap,cue_condition=p['cue_condition'],
                exact_permitted_differences=['profile_id','tracker.cues_enabled','xvf.mode'],extra_component_changes=False))
    if not matched:raise ValueError('No matched pairs; do not claim completed contrast analysis')
    rows=[];contrasts=[];counts_by_profile={};examples=collections.defaultdict(list);started=time.perf_counter()
    for cid in idx['case_ids']:
        for tap in ('O0','O1'):
            feature=verified(fmap[cid,tap]);windows=feature['features'];cache={}
            for pid in idx['profiles']:
                row=indexed[pid,cid,tap];E.verify(row['result'])
                value=json.loads(gzip.decompress(Path(row['result']['path']).read_bytes()))
                if value['status']!='COMPLETE' or value['identity']['execution_digest']!=spec['execution_digest'] or value['identity']['profile']!=profiles[pid,tap]['profile']:
                    raise ValueError('Prediction/epoch/profile mismatch')
                if (value['case_id'],value['stream'],value['candidate_id'])!=(cid,tap,pid) or value['prediction_key']!=digest(value['identity']):
                    raise ValueError('Prediction key/row identity mismatch')
                if value['identity']['source']!=feature['bindings'][0]:raise ValueError('Prediction source differs from exact audited R0 receipt')
                telemetry=value['identity']['telemetry']
                if telemetry is not None:
                    E.verify(telemetry)
                    value['_audit_delivered_rows']=[json.loads(line) for line in Path(telemetry['path']).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
                else:value['_audit_delivered_rows']=None
                if len(value['decisions'])!=len(windows):raise ValueError('N00 changed observation count')
                for d,w in zip(value['decisions'],windows):
                    if d['evidence_id']!=w['evidence_id'] or any(d[k]!=w[k] for k in ('source_start_sec','source_end_sec','available_at_sec')):
                        raise ValueError('N00 decision/actual feature support mismatch')
                cache[pid]=value;record=action_counts(value)
                rows.append(dict(candidate_id=pid,case_id=cid,stream=tap,prediction=row['result'],**record))
            for pair in matched:
                if pair['stream']!=tap:continue
                a,b=cache[pair['parent']],cache[pair['candidate']]
                if [(r['utterance_index'],r['text']) for r in a['final_transcripts_latest']]!=[(r['utterance_index'],r['text']) for r in b['final_transcripts_latest']]:
                    raise ValueError('Matched policy changed raw words')
                matrix=collections.Counter();shared=0
                for fp in feature['pairs']:
                    i,j=fp['left'],fp['right'];truth='SAME' if fp['same_reference_person'] else 'DIFFERENT'
                    left=relation(a['decisions'][i],a['decisions'][j]);right=relation(b['decisions'][i],b['decisions'][j])
                    ls='UNKNOWN' if left=='UNKNOWN' else 'CORRECT' if left==truth else 'WRONG'
                    rs='UNKNOWN' if right=='UNKNOWN' else 'CORRECT' if right==truth else 'WRONG'
                    matrix[ls+'->'+rs]+=1;shared+=fp['shared_original_source_id']
                    category=('harm' if ls=='CORRECT' and rs=='WRONG' else 'help' if ls=='WRONG' and rs=='CORRECT'
                        else 'resolved_correct' if ls=='UNKNOWN' and rs=='CORRECT' else 'lost_known_correct' if ls=='CORRECT' and rs=='UNKNOWN' else None)
                    ek=(pair['parent'],pair['candidate'],tap,category)
                    if category and len(examples[ek])<2:
                        examples[ek].append(dict(case_id=cid,stream=tap,parent=pair['parent'],candidate=pair['candidate'],category=category,
                            reference_pair=fp,reference_left=windows[i]['reference'],reference_right=windows[j]['reference'],
                            scorer_only_relation=truth,parent_relation=left,candidate_relation=right,
                            parent_prediction=indexed[pair['parent'],cid,tap]['result'],candidate_prediction=indexed[pair['candidate'],cid,tap]['result'],
                            prior_parent=trace(a,i,windows),prior_candidate=trace(b,i,windows),
                            current_parent=trace(a,j,windows),current_candidate=trace(b,j,windows),
                            interpretation='Paired retrospective association diagnostic; may include accumulated cue-state effects, not a one-step randomized causal effect'))
                contrasts.append(dict(**pair,case_id=cid,reference_qualified_disjoint_pairs=len(feature['pairs']),
                    shared_original_source_pairs=shared,transition_counts=dict(matrix),raw_word_parity=True))
            if len(rows)%1320==0:print(json.dumps(dict(phase='N00_CUE_ACTIONS',completed=len(rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    p=OUT/'N00_ACTION_ROWS.json';E.save(p,dict(rows=rows))
    c=OUT/'N00_MATCHED_RELATION_ROWS.json';E.save(c,dict(rows=contrasts))
    example_rows=[]
    for key,values in sorted(examples.items()):
        parent,candidate,tap,category=key
        for n,value in enumerate(values):
            path=OUT/'examples'/f'{parent}_{candidate}_{tap}_{category}_{n+1}.json';E.save(path,value)
            example_rows.append(dict(parent=parent,candidate=candidate,stream=tap,category=category,result=E.bind(path)))
    for pid in idx['profiles']:
        for tap in ('O0','O1'):
            subset=[r for r in rows if r['candidate_id']==pid and r['stream']==tap]
            counter=collections.Counter();reason=collections.Counter();events=collections.Counter()
            for r in subset:counter.update(r['counts']);reason.update(r['cue_reasons']);events.update(r['actual_lineage_events'])
            counts_by_profile[pid+'_'+tap]=dict(candidate_id=pid,stream=tap,outputs=len(subset),counts=dict(counter),cue_reasons=dict(reason),actual_lineage_events=dict(events))
    aggregates=[]
    for pair in matched:
        subset=[r for r in contrasts if all(r[k]==pair[k] for k in ('parent','candidate','stream'))]
        counter=collections.Counter()
        for r in subset:counter.update(r['transition_counts'])
        aggregates.append(dict(**pair,case_rows=len(subset),pair_count=sum(r['reference_qualified_disjoint_pairs'] for r in subset),transition_counts=dict(counter)))
    value=dict(status='COMPLETE_ACTUAL_N00_CHALLENGE_ACTION_DIAGNOSTIC',schema='s6c-cue-action-audit.v1',created_utc=E.utc(),
        plan=E.bind(OUT/'CUE_DECISION_PLAN.json'),feature_audit=E.bind(FEATURE_AUTHORITY),
        action_rows=E.bind(p),matched_relation_rows=E.bind(c),examples=example_rows,
        outputs=7392,candidates=66,cases=56,taps=['O0','O1'],profile_summaries=list(counts_by_profile.values()),matched_summaries=aggregates,
        new_model_calls=0,actual_policy_replays=0,predictor_changes=0,
        limitations=['Reads existing actual v3 outputs, not a new replay or native proof.',
            'Logged joint contribution counts exclude old_voice_gate, which logs eligibility/action but no numeric candidate breakdown; zero logged contribution is not proof of zero internal spatial ranking.',
            'Pair truth is evaluator-only; comparisons are anonymized co-assignment relations invariant to arbitrary track-number renaming.',
            'All-pair counts overlap in evidence and are not independent trials, speaker error rates, cpWER or named-identity accuracy.',
            'Wrong-to-correct and correct-to-wrong are reported separately from Unknown resolution/loss; missing reference support remains in full feature/output denominators.',
            'Diagnostic nominal and reassigned cues retain their explicit oracle/null labels; no production gain is inferred from them.',
            'Example delivery prerequisite is joined independently; actual logged cue/score/lineage is authoritative for pipeline action.',
            'N00 identity mode is none; named/display proof is separately source-bound in gallery_branch_proof_v1 and native gallery results.'])
    E.save(target,value);return E.bind(target)

def checks():
    support=dict(output_mappings={'O0':dict(source_with_rir_to_output_offset_samples=1600)},turns=[dict(speaker_key='A',source_id='a',support_ranges=[[0,8000]])])
    assert reference_window(support,'O0',.1,.6)['person']=='A'
    assert reference_window(support,'O0',.6,1.1)['person'] is None
    other=deepcopy(support);other['turns'].append(dict(speaker_key='B',source_id='b',support_ranges=[[4000,4800]]))
    assert reference_window(other,'O0',.1,.6)['status']=='MULTIPLE_REFERENCE_PEOPLE'
    rows=[dict(available_at_sec=1.,angle_deg=180.,valid=True,reliability=1.)]
    assert delivered_at(rows,[1.],.9)['row'] is None
    assert delivered_at(rows,[1.],1.2)['usable'] and not delivered_at(rows,[1.],1.3)['usable']
    assert relation(dict(tracker_id=1),dict(tracker_id=1))==relation(dict(tracker_id=99),dict(tracker_id=99))=='SAME'
    assert relation(dict(tracker_id=None),dict(tracker_id=None))=='UNKNOWN'
    assert spans_union([[0,.4],[.2,.5]])==[[0,.5]]
    parent=dict(profile_id='off',tracker=dict(cues_enabled=False,cosine_threshold=.35),xvf=dict(mode='none'),asr=dict(endpoint=1.2))
    candidate=deepcopy(parent);candidate['profile_id']='on';candidate['tracker']['cues_enabled']=True;candidate['xvf']['mode']='tracking_only'
    assert matched_cue_route(parent,candidate)
    other=deepcopy(candidate);other['xvf']['mode']='both';assert not matched_cue_route(parent,other)
    other=deepcopy(candidate);other['asr']['endpoint']=.5;assert not matched_cue_route(parent,other)
    other=deepcopy(candidate);other['tracker']['cosine_threshold']=.4;assert not matched_cue_route(parent,other)
    return dict(status='PASS',checks=12,new_model_calls=0)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('freeze','decisions','checks'));a=p.parse_args()
    print(json.dumps(dict(freeze=freeze,features=features,decisions=decisions,checks=checks)[a.action](),indent=2),flush=True)
