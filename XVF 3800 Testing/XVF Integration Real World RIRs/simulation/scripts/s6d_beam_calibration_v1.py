"""Closed C-probe extraction and conservative threshold proposal; see README_S6D_BEAM_CALIBRATION_V1.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import math
from pathlib import Path
import s6d_beam_native_run_v1 as N

METRICS=('minimum_selected_score','minimum_selected_margin','minimum_beam_margin','minimum_auto_correlation','minimum_auto_margin')
COLLECTION_HELPER_SHA='6f7162900dbf19ff1876c5bbb09720a16081d1a330319ac8cc6e1f6ef61dfbb4'
need=N.need;bind=N.bind;verified=N.verified;save=N.save
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def require_closed_collection(manifest_ref,m,job,completed,audit,admission):
    need(m.get('schema')=='s6d-beam-execution.v1' and m['runner_helper']['sha256']==COLLECTION_HELPER_SHA and bind(m['runner_helper']['path'])==m['runner_helper'],'Reviewed collection source required')
    need(type(job.get('expected_frames')) is int and job['expected_frames']>0 and job.get('expected_identity_frames')==job['expected_frames'] and isinstance(job.get('audio_pcm_sha256'),str) and len(job['audio_pcm_sha256'])==64,'Full predeclared PCM/frame identity required')
    need(completed.get('helper')==m['runner_helper'] and completed.get('inner_native_loop')==m['support']['native_loop'] and completed.get('native_run_one_same_process') is True and completed.get('subprocess_spawned_by_wrapper') is False and completed.get('failure') is None,'Actual reviewed C wrapper completion required')
    need(completed.get('completion_audit',{}).get('path')==str(Path(job['output'])/'FULL_MULTISTREAM_AUDIT.json') and completed.get('result',{}).get('path')==str(Path(job['output'])/'RESULT.json'),'C result/audit output belongs to another job')
    result=verified(completed['result']);need(result.get('job')==job and result.get('manifest')==manifest_ref and result.get('status')=='COMPLETE' and result.get('failure') is None,'Literal native result differs')
    need(audit.get('job_id')==job['job_id'] and audit.get('physical_case_result')==admission['original_case_result'] and audit.get('source_proofs')==job['stream_proofs'] and audit.get('dispatch',{}).get('frames')==job['expected_frames'],'Full-source audit identity/count differs')
    need(set(audit.get('journals',{}))==set(job['stream_proofs']),'C focus journal omitted')
    for name,proof in job['stream_proofs'].items():
        j=audit['journals'][name];need(bind(j['path'])==j and j['bytes']==proof['bytes']==2*job['expected_frames'] and j['sha256']==proof['sha256'],'Changed/incomplete closed C journal')
    need(audit['consumer_events']['path']==str(Path(job['output'])/'consumer_events.jsonl'),'Foreign consumer event journal')

def require_candidate_join(candidate,seen,admission,settings,window_seconds,clean_fraction):
    key=(candidate.get('stream_id'),candidate.get('event_id'));need(key in seen,'Probe lacks a preceding actual native identity event')
    event=seen[key]
    for field in ('event_id','stream_id','capture_source_id','route_id','source_start_sec','source_end_sec','available_at_sec','speech','overlap','identity'):
        need(candidate.get(field)==event.get(field),'Probe/native identity join differs: '+field)
    need(event.get('evidence_kind')=='mature' and finite(event.get('clean_fraction')) and event['clean_fraction']>=clean_fraction and abs(event['source_end_sec']-event['source_start_sec']-window_seconds)<=1/16000,'Actual mature clean whole-window proof absent')
    need(candidate['stream_id'] in settings['identity_streams'] and (candidate['capture_source_id'],candidate['route_id'])==(admission['capture_source_id'],admission['route_id']),'Foreign capture/route/tap in C probe')
    return event

def conservative_label(start,end,spans):
    """Captured-clock support only; whole candidate must survive the supplied uncertainty envelope."""
    need(all(type(x) is int for x in (start,end)) and 0<=start<end,'Integer source window required')
    hits=[]
    for s in spans:
        bounds=[s[k] for k in ('start_min','start_max','stop_min','stop_max')]
        need(all(type(x) is int for x in bounds) and 0<=bounds[0]<=bounds[1]<bounds[2]<=bounds[3],'Invalid conservative C source support')
        if max(start,bounds[0])<min(end,bounds[3]):hits.append(s)
    if len(hits)!=1:return None,'mixed_or_uncovered_support'
    s=hits[0]
    if start<s['start_max'] or end>s['stop_min']:return None,'boundary_uncertainty'
    return s,'whole_window_exclusive_C_interior'

def summarize_thresholds(rows,min_sources=2):
    """Fixed no-Q rule: strictly above observed C-negative maximum; require retained positives."""
    need(type(min_sources) is int and min_sources>=2,'At least two distinct C sources per class required')
    summary={};thresholds={};issues=[]
    for key in METRICS:
        values=[r for r in rows if r.get('metric')==key]
        for r in values:need(r.get('label') in ('positive','negative') and finite(r.get('value')) and -1<=r['value']<=(2 if 'margin' in key else 1) and isinstance(r.get('source_id'),str),'Invalid labelled C feature')
        pos=[r for r in values if r['label']=='positive'];neg=[r for r in values if r['label']=='negative']
        ps={r['source_id'] for r in pos};ns={r['source_id'] for r in neg};threshold=None;retained=[]
        if len(ps)<min_sources or len(ns)<min_sources:issues.append(key+': insufficient distinct C sources in positive/negative classes')
        else:
            proposed=max(0.,max(r['value'] for r in neg)+1e-6)
            retained=[r for r in pos if r['value']>=proposed]
            if proposed>1 or len({r['source_id'] for r in retained})<min_sources:issues.append(key+': no supported conservative separation; do not force nominal threshold')
            else:threshold=proposed;thresholds[key]=threshold
        summary[key]=dict(positive_rows=len(pos),negative_rows=len(neg),positive_distinct_source_ids=sorted(ps),negative_distinct_source_ids=sorted(ns),threshold=threshold,retained_positive_rows=len(retained),scope='Correlated model windows are not independent observations or summed unique duration')
    return dict(thresholds=thresholds if not issues else None,metrics=summary,issues=issues)

def extract(manifest_ref,job_id,completion_ref,support_ref,output):
    m=verified(manifest_ref);job=next(j for j in m['jobs'] if j['job_id']==job_id)
    need(job['mode']=='calibration_collection','Only actual C collection outputs can calibrate')
    completed=verified(completion_ref)
    need(completed.get('status')=='COMPLETE' and completed.get('manifest')==manifest_ref and completed.get('native_job_id')==job_id and completed.get('full_multistream_evidence_validated') is True and completed.get('stop_requested') is False and completed.get('protocol_observer_closed') is True and completed.get('protocol_observer_errors')==[],'Closed accepted C protocol required')
    audit=verified(completed['completion_audit']);need(audit.get('status')=='PASS_FULL_MULTISTREAM_EVIDENCE' and audit.get('errors')==[] and audit.get('manifest')==manifest_ref,'C full-source audit absent')
    admission=verified(job['admission']);partition=verified(admission['calibration_partition']);base=verified(partition['original_partition'])
    require_closed_collection(manifest_ref,m,job,completed,audit,admission)
    need(base.get('partition')=='C' and base.get('Q_used') is False and base.get('disjoint_from_E_Q_verified') is True and admission['original_case_result'] in base.get('accepted_case_results',[]),'Actual original C provenance required')
    support=verified(support_ref)
    need(support.get('schema')=='s6d-C-captured-support.v1' and support.get('status')=='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT' and support.get('case_result')==admission['original_case_result'] and support.get('partition')==partition['original_partition'],'Exact evaluator-only captured C support required')
    need(support.get('gallery')==job['gallery'] and support.get('no_per_beam_alignment') is True and support.get('rir_origin_added_again') is False,'C identity/clock convention differs')
    need(isinstance(support.get('root_acceptance'),dict),'Separate root source-support acceptance required');verified(support['root_acceptance'])
    spans=support['spans'];allowed=set(base['C_source_ids'])
    need(all(s.get('source_id') in allowed and s.get('role')=='C' for s in spans),'Non-C source in calibration support')
    need(m['support']['evidence']['sha256']==N.PINS['evidence'],'Accepted evidence reader changed')
    B=N.module(m['support']['evidence'],'C_evidence_reader');event_bound=audit['consumer_events'];need(bind(event_bound['path'])==event_bound,'C event journal changed')
    settings=verified(job['beam_settings']);selected=set(settings['selected_profile_ids']);features=[];counts=Counter();probe_ids=set();seen={}
    profile=verified(job['profile_binding']);window=profile['embedding']['window_sec'];clean=profile['embedding']['minimum_clean_fraction']
    gallery=verified(job['gallery']);known_ids={r['profile_id'] for r in gallery['profiles']}
    need(selected<=known_ids and all(s.get('profile_id') is None or s['profile_id'] in known_ids for s in spans),'Foreign profile identity in support/selection')
    for event in B.stream(event_bound['path']):
        if event.get('event_type')=='s6d_beam_identity':
            identity_event=event['payload'];key=(identity_event.get('stream_id'),identity_event.get('event_id'));need(key not in seen,'Duplicate actual native identity event');seen[key]=identity_event
        if event.get('event_type')!='s6d_C_selector_probe':continue
        p=event['payload'];index=p['probe_index'];need(type(index) is int and index>0 and index not in probe_ids,'Duplicate/malformed actual probe');probe_ids.add(index)
        need(p.get('collection_only') is True and p.get('thresholds_applied') is False and p.get('actual_disabled_result',{}).get('calibrated') is False and p['actual_disabled_result'].get('status')=='NO_MATCH','Selector was enabled during collection')
        now=p['selector_now_sec'];need(finite(now),'Invalid actual probe clock');candidates=[]
        for r in p['candidates']:
            counts['candidate_opportunities']+=1
            require_candidate_join(r,seen,admission,settings,window,clean)
            a,b=r.get('source_start_sec'),r.get('source_end_sec');available=r.get('available_at_sec')
            if not all(finite(x) for x in (a,b,available)) or not 0<=a<b<=available<=now or now-b>.75 or now-available>.75 or r.get('speech') is not True or r.get('overlap') is not False:
                counts['runtime_ineligible_retained']+=1;continue
            truth,reason=conservative_label(round(a*16000),round(b*16000),spans)
            if truth is None:counts['unlabelled_'+reason]+=1;continue
            ident=r.get('identity') or {};known=ident.get('known_profile_id')
            if ident.get('naming_state')!='confirmed' or known is None:counts['no_confirmed_identity_retained']+=1;continue
            need(known in known_ids,'Foreign confirmed profile in actual C identity event')
            correct=truth.get('profile_id') is not None and truth['profile_id']==known
            common=dict(source_id=truth['source_id'],case_result=admission['original_case_result'],job_id=job_id,probe_index=index,event_id=r['event_id'],stream_id=r['stream_id'],source_start_sec=a,source_end_sec=b,label='positive' if correct else 'negative')
            if p['selector']=='selected':
                if known not in selected:counts['outside_selected_population_retained']+=1;continue
                score=ident.get('current_query_name_cosine');margin=ident.get('margin')
                if not finite(score) or not finite(margin):counts['missing_query_score_retained']+=1;continue
                features.extend([dict(common,metric='minimum_selected_score',value=score),dict(common,metric='minimum_selected_margin',value=margin)])
                candidates.append((score,common))
            elif p['selector']=='auto':
                if p.get('exclusive_auto_speech') is not True or r.get('same_auto_window') is not True or not finite(r.get('auto_waveform_correlation')):counts['auto_support_unavailable_retained']+=1;continue
                value=r['auto_waveform_correlation'];features.append(dict(common,metric='minimum_auto_correlation',value=value));candidates.append((value,common))
            else:raise ValueError('Unknown actual probe kind')
        candidates.sort(key=lambda x:x[0],reverse=True)
        # Same-person duplicate copies are not false alternatives or independent duration.
        if len(candidates)>=2 and candidates[0][1]['label']!=candidates[1][1]['label']:
            metric='minimum_beam_margin' if p['selector']=='selected' else 'minimum_auto_margin'
            features.append(dict(candidates[0][1],metric=metric,value=candidates[0][0]-candidates[1][0]))
        else:counts['no_identifiable_same_window_competition_retained']+=1
    need(probe_ids and bind(event_bound['path'])==event_bound,'Missing/changed actual C probe stream')
    result=dict(schema='s6d-C-beam-features.v1',status='EXTRACTED_C_ONLY_NOT_ACCEPTED_THRESHOLDS',source=bind(__file__),manifest=manifest_ref,job_id=job_id,completion=completion_ref,full_source_audit=completed['completion_audit'],support=support_ref,partition=partition['original_partition'],gallery=job['gallery'],profile_binding=job['profile_binding'],capture_profile=job['capture_profile'],identity_streams=settings['identity_streams'],selected_profile_ids=settings['selected_profile_ids'],Q_used=False,disjoint_from_E_Q_verified=True,counts=dict(counts),actual_probe_count=len(probe_ids),features=features,limitations=['Whole-span conservative possible source support only; ambiguous and unknown opportunities retained in counts','Source identity is original C input metadata, not proof every focus stream preserved that source. Eligible final named-association correctness is distinct from exact acoustic target localization.','No per-beam lag search, waveform switch, Q threshold tuning or model invocation','No simultaneous competition truth is manufactured from two copies of one person'])
    save(output,result);return bind(output)

def propose(feature_refs,output):
    groups=[verified(x) for x in feature_refs];need(groups,'C feature inputs required')
    need(len({(g['manifest']['sha256'],g['job_id']) for g in groups})==len(groups),'Duplicate C job feature populations')
    context=('gallery','profile_binding','capture_profile','identity_streams','selected_profile_ids')
    first=groups[0]
    for g in groups:
        need(g.get('schema')=='s6d-C-beam-features.v1' and g.get('Q_used') is False and g.get('disjoint_from_E_Q_verified') is True,'No Q features allowed')
        need(g.get('status')=='EXTRACTED_C_ONLY_NOT_ACCEPTED_THRESHOLDS' and g['source']['sha256']==bind(__file__)['sha256'] and bind(g['source']['path'])==g['source'],'Different extraction source/status')
        for key in ('manifest','completion','full_source_audit','support','partition','gallery','profile_binding'):verified(g[key])
        need(all(g[k]==first[k] for k in context),'Do not pool incompatible C capture/gallery/profile/tap opportunities')
    rows=[r for g in groups for r in g['features']];fit=summarize_thresholds(rows)
    result=dict(schema_version='edge-s6d-beam-calibration-proposal.v1',status='PROPOSED_C_ONLY_PENDING_INDEPENDENT_ROOT_REVIEW' if fit['thresholds'] else 'CALIBRATION_SUPPORT_INSUFFICIENT_SELECTORS_DISABLED',source=bind(__file__),features=feature_refs,context={k:first[k] for k in context},partition='C',Q_used=False,disjoint_from_E_Q_verified=True,fit=fit,duplicate_resolution_enabled=False,rule='Each gate strictly exceeds observed eligible C-negative maximum by1e-6; minimum2 distinct source IDs in each class and2 retained positive sources. All5 gates must qualify. No threshold grid or Q selection.',thresholds_accepted=False,required_before_enablement='Independent review must validate source/identity/probe joins, adequate C opportunity/competition support and exact canonical profile digest; only root may publish a separately bound edge-s6d-beam-calibration.v1 ACCEPTED_C_ONLY receipt.',models_started=0)
    save(output,result);return bind(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    e=sub.add_parser('extract');e.add_argument('--manifest',type=Path,required=True);e.add_argument('--manifest-sha256',required=True);e.add_argument('--job-id',required=True);e.add_argument('--completion',type=Path,required=True);e.add_argument('--support',type=Path,required=True);e.add_argument('--output',type=Path,required=True)
    f=sub.add_parser('propose');f.add_argument('--features',type=Path,nargs='+',required=True);f.add_argument('--output',type=Path,required=True);a=p.parse_args()
    need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G-only output required');a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.cmd=='extract':
        b=bind(a.manifest);need(b['sha256']==a.manifest_sha256,'Manifest differs');answer=extract(b,a.job_id,bind(a.completion),bind(a.support),a.output)
    else:answer=propose([bind(x) for x in a.features],a.output)
    import json
    print(json.dumps(answer))
