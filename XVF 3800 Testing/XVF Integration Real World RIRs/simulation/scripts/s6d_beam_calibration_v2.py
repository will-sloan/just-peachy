"""Model-free C calibration candidate V2; see README_S6D_BEAM_CALIBRATION_V2.md."""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import s6d_beam_calibration_v1 as V1

N=V1.N
need,bind,verified,save,finite=N.need,N.bind,N.verified,N.save,V1.finite
need(bind(V1.__file__)['sha256']=='9165da50cb28e1385c3d6edf19581261171edab68f34c0b5cd67cd37b4ba6e74','Frozen V1 guards changed')
need(bind(N.__file__)['sha256']==V1.COLLECTION_HELPER_SHA,'Frozen collection utility changed')
BEAM_PATH=Path(r"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6D\20260913T195357Z\application\beam_native_interface_v3\source\edge_speech_pipeline\research_beams_s6d.py")
A15_SHA='8042fbec1cdd4632d90b9d2148c37114e3fcd1aa8cc39a442d22a575e4177018'
METRICS=V1.METRICS

def payload_digest(support):
    payload={k:v for k,v in support.items() if k!='root_acceptance'}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def require_support_authority(support,admission,partition_ref,base,gallery_ref):
    need(base.get('schema_version')=='edge-s6d-beam-calibration-partition.v1' and base.get('status')=='ROOT_ACCEPTED_CAPTURED_C_FOR_COLLECTION_ONLY','Root accepted captured C partition required')
    need(base.get('partition')=='C' and base.get('Q_used') is False and base.get('disjoint_from_E_Q_verified') is True and admission['original_case_result'] in base.get('accepted_case_results',[]),'Actual original C provenance required')
    need(support.get('schema')=='s6d-C-captured-support.v1' and support.get('status')=='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT','Accepted conservative support required')
    need(support.get('case_result')==admission['original_case_result'] and support.get('partition')==partition_ref and support.get('gallery')==gallery_ref,'Support case/partition/gallery differs')
    need(support.get('no_per_beam_alignment') is True and support.get('rir_origin_added_again') is False,'C clock convention differs')
    spans=support.get('spans')
    need(isinstance(spans,list) and all(s.get('role')=='C' and s.get('source_id') in set(base['C_source_ids']) for s in spans),'Non-C source in calibration support')
    root=verified(support['root_acceptance'])
    need(root.get('schema')=='s6d-C-support-root-acceptance.v1' and root.get('status')=='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT' and root.get('Q_used') is False and root.get('disjoint_from_E_Q_verified') is True,'Semantic root support acceptance required')
    target=dict(case_result=admission['original_case_result'],partition=partition_ref,gallery=gallery_ref,
                support_payload_sha256=payload_digest(support),C_source_ids=sorted({s['source_id'] for s in spans}))
    need(isinstance(root.get('acceptances'),list) and sum(row==target for row in root['acceptances'])==1,'Root receipt does not accept this exact support payload/case/partition/gallery/C scope')
    return target

def settings_context(settings):
    age=settings.get('maximum_evidence_age_sec',.75)
    need(finite(age) and age==.75,'Exact runtime evidence age0.75 required')
    streams=settings.get('identity_streams');selected=settings.get('selected_profile_ids')
    need(isinstance(streams,list) and streams and len(set(streams))==len(streams) and all(isinstance(x,str) and x for x in streams),'Exact identity streams required')
    need(isinstance(selected,list) and selected and len(set(selected))==len(selected),'Exact selected identities required')
    return dict(identity_streams=streams,selected_profile_ids=selected,maximum_evidence_age_sec=age)

def runtime_eligible(row,now,settings,admission):
    return (finite(now) and row.get('speech') is True and row.get('overlap') is False and
            all(finite(row.get(k)) for k in ('source_start_sec','source_end_sec','available_at_sec')) and
            0<=row['source_start_sec']<row['source_end_sec']<=row['available_at_sec']<=now and
            0<=now-row['available_at_sec']<=settings['maximum_evidence_age_sec'] and
            0<=now-row['source_end_sec']<=settings['maximum_evidence_age_sec'] and
            row.get('stream_id') in settings['identity_streams'] and
            all(isinstance(row.get(k),str) and row[k] for k in ('capture_source_id','route_id')) and
            (row.get('capture_source_id'),row.get('route_id'))==(admission['capture_source_id'],admission['route_id']))

def same_auto_span(row,probe):
    support=probe.get('auto_support')
    return (isinstance(support,(list,tuple)) and len(support)==2 and all(finite(x) for x in support) and
            all(abs(row[k]-support[i])<=1/16000 for i,k in enumerate(('source_start_sec','source_end_sec'))))

def metric_pool(record,settings,admission):
    result=[]
    for row in record['candidates']:
        if not runtime_eligible(row,record['selector_now_sec'],settings,admission):continue
        if record['selector']=='selected':
            ident=row.get('identity') or {}
            if ident.get('naming_state')!='confirmed' or ident.get('known_profile_id') not in settings['selected_profile_ids']:continue
            score,margin=ident.get('current_query_name_cosine'),ident.get('margin')
            if not finite(score) or not finite(margin):continue
        else:
            if record.get('exclusive_auto_speech') is not True or not same_auto_span(row,record):continue
            score=row.get('auto_waveform_correlation')
            if not finite(score):continue
        result.append((score,row))
    return sorted(result,key=lambda pair:pair[0],reverse=True)

def feature_rows(record,settings,admission):
    rows=[];pool=metric_pool(record,settings,admission)
    def add(metric,value,row):
        rows.append(dict(metric=metric,value=value,label=row['calibration_truth']['label'],
                         source_id=row['calibration_truth']['source_id'],job_id=record['job_id'],
                         probe_index=record['probe_index'],event_id=row['event_id'],stream_id=row['stream_id']))
    for score,row in pool:
        if record['selector']=='selected':
            add('minimum_selected_score',score,row);add('minimum_selected_margin',row['identity']['margin'],row)
        else:add('minimum_auto_correlation',score,row)
    if len(pool)>=2:
        first,second=pool[0][1],pool[1][1]
        row=deepcopy(first)
        if {first['calibration_truth']['label'],second['calibration_truth']['label']}!={'positive','negative'}:
            row['calibration_truth']['label']='ambiguous'
        add('minimum_beam_margin' if record['selector']=='selected' else 'minimum_auto_margin',pool[0][0]-pool[1][0],row)
    return rows

def collect_probe(probe,seen,admission,settings,window,clean,spans,known_ids,job_id):
    need(probe.get('selector') in ('selected','auto'),'Unknown probe selector')
    need(probe.get('collection_only') is True and probe.get('thresholds_applied') is False and probe.get('actual_disabled_result',{}).get('calibrated') is False and probe['actual_disabled_result'].get('status')=='NO_MATCH','Selectors must be disabled during actual C collection')
    need(finite(probe.get('selector_now_sec')),'Invalid actual probe clock')
    record={k:deepcopy(probe.get(k)) for k in ('probe_index','selector','selector_now_sec','auto_support','exclusive_auto_speech')}
    record.update(job_id=job_id,candidates=[]);counts=Counter();keys=set()
    for row in probe['candidates']:
        V1.require_candidate_join(row,seen,admission,settings,window,clean)
        key=(row['stream_id'],row['event_id']);need(key not in keys,'Duplicate candidate opportunity in probe');keys.add(key)
        r=deepcopy(row);r.pop('waveform',None);r.pop('vector',None)
        a,b=r['source_start_sec'],r['source_end_sec'];need(all(finite(x) for x in (a,b)),'Finite native window required')
        start,end=round(a*16000),round(b*16000)
        need(abs(a*16000-start)<=1e-5 and abs(b*16000-end)<=1e-5,'Native source times must be exact16k frames')
        truth,reason=V1.conservative_label(start,end,spans)
        ident=r.get('identity') or {};known=ident.get('known_profile_id')
        need(known is None or known in known_ids,'Foreign actual gallery identity')
        label='ambiguous';source_id=truth['source_id'] if truth else None
        if truth and ident.get('naming_state')=='confirmed' and known is not None:
            label='positive' if truth.get('profile_id') is not None and truth['profile_id']==known else 'negative'
        r['calibration_truth']=dict(label=label,source_id=source_id,reason=reason if truth is None else ('confirmed_name_agreement' if label!='ambiguous' else 'unresolved_identity_not_acoustic_truth'))
        r['runtime_eligible']=runtime_eligible(r,record['selector_now_sec'],settings,admission)
        if record['selector']=='auto':
            need(r.get('same_auto_window') is same_auto_span(r,record),'Probe auto/source span flag differs')
            value=r.get('auto_waveform_correlation');need(value is None or finite(value) and -1<=value<=1,'Invalid actual auto correlation')
        counts['candidate_opportunities']+=1
        counts['runtime_eligible' if r['runtime_eligible'] else 'runtime_ineligible_retained']+=1
        counts[label+'_source_support_retained']+=1
        record['candidates'].append(r)
    return record,feature_rows(record,settings,admission),counts

def exact_selector():
    raw=BEAM_PATH.read_bytes()
    need(hashlib.sha256(raw).hexdigest()==N.PINS['beam'],'Frozen runtime selector source changed')
    tree=ast.parse(raw.decode('utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BeamSelector')
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='choose')
    # Correlations are the actual collection probe values. No waveform transform or search.
    scope={'finite':finite,'waveform_similarity':lambda auto,value:value}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(BEAM_PATH),'exec'),scope)
    return scope['choose']

def replay_probe(record,thresholds,settings,admission,choose=None):
    choose=choose or exact_selector()
    candidates=[]
    for row in record['candidates']:
        r=deepcopy(row);r['waveform']=r.get('auto_waveform_correlation') if record['selector']=='auto' else None
        candidates.append(r)
    actor=SimpleNamespace(calibration={**thresholds,'duplicate_resolution_enabled':False},
                          settings=SimpleNamespace(**settings),capture_identity=(admission['capture_source_id'],admission['route_id']))
    kw={} if record['selector']=='selected' else dict(auto_wave=True,auto_support=record.get('auto_support'),auto_speech=record.get('exclusive_auto_speech'))
    return choose(actor,candidates,record['selector_now_sec'],**kw)

def fit_thresholds(rows,min_sources=2):
    need(type(min_sources) is int and min_sources>=2,'At least2 distinct C sources required')
    thresholds={};metrics={};issues=[]
    for metric in METRICS:
        rs=[r for r in rows if r['metric']==metric]
        for r in rs:
            need(r['label'] in ('positive','negative','ambiguous') and finite(r['value']) and -1<=r['value']<=(2 if 'margin' in metric else 1),'Invalid actual C metric')
            need(r['source_id'] is None or isinstance(r['source_id'],str) and r['source_id'],'Invalid C source ID')
            if r['label']!='ambiguous':need(r['source_id'] is not None,'Labelled feature lacks unique original C source')
        pos=[r for r in rs if r['label']=='positive'];neg=[r for r in rs if r['label']=='negative'];amb=[r for r in rs if r['label']=='ambiguous']
        ps={r['source_id'] for r in pos};ns={r['source_id'] for r in neg};threshold=None;retained=set()
        if len(ps)<min_sources or len(ns)<min_sources:issues.append(metric+': insufficient distinct known C positive/negative sources')
        else:
            bound=max(r['value'] for r in neg+amb)
            proposed=max(0.,bound+1e-6);retained={r['source_id'] for r in pos if r['value']>=proposed}
            if proposed>1 or len(retained)<min_sources:issues.append(metric+': conservative negative/ambiguity bound has inadequate positive retention')
            else:threshold=proposed;thresholds[metric]=threshold
        metrics[metric]=dict(positive_rows=len(pos),negative_rows=len(neg),ambiguous_rows=len(amb),positive_source_ids=sorted(ps),negative_source_ids=sorted(ns),retained_positive_source_ids=sorted(retained),threshold=threshold,ambiguity_is_not_negative_truth=True)
    return dict(thresholds=thresholds if not issues else None,metrics=metrics,issues=issues)

def joint_replay(records,thresholds,settings,admission,min_sources=2,case_identities=None):
    need(set(thresholds)==set(METRICS),'All5 frozen gates required')
    need(all(finite(v) and 0<=v<=1 for v in thresholds.values()),'Valid frozen gate range required')
    choose=exact_selector();zero={k:0. for k in METRICS};summaries={};issues=[]
    for selector in ('selected','auto'):
        positives=set();negative_challenges=set();negative_rejected=set();competition_positive=set();counts=Counter()
        for record in records:
            if record['selector']!=selector:continue
            identity=case_identities[(record['job_id'],record['probe_index'])] if case_identities is not None else admission
            by_id={(r['stream_id'],r['event_id']):r for r in record['candidates']}
            before=replay_probe(record,zero,settings,identity,choose);after=replay_probe(record,thresholds,settings,identity,choose)
            def truth(result):
                return by_id[(result['selected_stream'],result['evidence_id'])]['calibration_truth'] if result.get('status')=='ASSOCIATED' else None
            bt,at=truth(before),truth(after);counts['actual_probe_opportunities']+=1
            if bt and bt['label']=='negative':
                negative_challenges.add(bt['source_id'])
                if at is None or at['label']=='positive':negative_rejected.add(bt['source_id'])
            if at is None:counts['abstained']+=1
            elif at['label']=='positive':
                positives.add(at['source_id']);counts['retained_positive']+=1
                pool=metric_pool(record,settings,identity)
                if {r['calibration_truth']['label'] for _,r in pool}>={'positive','negative'}:competition_positive.add(at['source_id'])
            else:
                counts['negative_or_ambiguous_winner']+=1
                issues.append(selector+': proposed gates select '+at['label']+' evidence; no enableable proposal')
        if len(positives)<min_sources:issues.append(selector+': fewer than2 distinct C sources survive joint gates')
        if len(negative_challenges)<min_sources or len(negative_rejected)<min_sources:issues.append(selector+': fewer than2 distinct C sources establish joint negative-challenge rejection')
        if len(competition_positive)<min_sources:issues.append(selector+': fewer than2 retained positive C sources have actual identifiable positive/negative competition')
        summaries[selector]=dict(counts=dict(counts),retained_positive_source_ids=sorted(positives),negative_challenge_source_ids=sorted(negative_challenges),rejected_negative_source_ids=sorted(negative_rejected),retained_competition_source_ids=sorted(competition_positive))
    return dict(status='JOINT_REPLAY_SUPPORTED' if not issues else 'JOINT_REPLAY_INSUFFICIENT',issues=issues,selectors=summaries,selector_source=bind(BEAM_PATH),duplicate_resolution_enabled=False,correlation_scope='Exact precomputed same-source-window collection correlations; no model/waveform calls')

def extract_data(manifest_ref,job_id,completion_ref,support_ref):
    m=verified(manifest_ref);matches=[j for j in m['jobs'] if j['job_id']==job_id];need(len(matches)==1,'Exactly one literal C job required');job=matches[0]
    need(job['mode']=='calibration_collection','Only actual C collection outputs can calibrate')
    completed=verified(completion_ref)
    need(completed.get('status')=='COMPLETE' and completed.get('manifest')==manifest_ref and completed.get('native_job_id')==job_id and completed.get('full_multistream_evidence_validated') is True and completed.get('stop_requested') is False and completed.get('protocol_observer_closed') is True and completed.get('protocol_observer_errors')==[],'Closed accepted C protocol required')
    audit=verified(completed['completion_audit']);need(audit.get('status')=='PASS_FULL_MULTISTREAM_EVIDENCE' and audit.get('errors')==[] and audit.get('manifest')==manifest_ref,'C full-source audit absent')
    admission=verified(job['admission']);partition=verified(admission['calibration_partition']);base=verified(partition['original_partition'])
    V1.require_closed_collection(manifest_ref,m,job,completed,audit,admission)
    support=verified(support_ref)
    require_support_authority(support,admission,partition['original_partition'],base,job['gallery'])
    need(job['gallery']['sha256']==A15_SHA,'Exact original A15 gallery required')
    settings_ref=job['beam_settings'];settings=settings_context(verified(settings_ref));profile=verified(job['profile_binding']);gallery=verified(job['gallery'])
    known={row['profile_id'] for row in gallery['profiles']};need(len(known)==15 and set(settings['selected_profile_ids'])<=known,'Actual A15/selected profile population differs')
    spans=support['spans'];need(all(s.get('profile_id') is None or s['profile_id'] in known for s in spans),'Foreign profile identity in support')
    # Validate every interval even if no observed candidate reaches it.
    for span in spans:
        bounds=[span[k] for k in ('start_min','start_max','stop_min','stop_max')]
        need(all(type(x) is int for x in bounds) and 0<=bounds[0]<=bounds[1]<bounds[2]<=bounds[3]<=job['expected_frames'],'Invalid/out-of-capture conservative C support')
    need(m['support']['evidence']['sha256']==N.PINS['evidence'],'Accepted evidence reader changed')
    B=N.module(m['support']['evidence'],'C_v2_evidence_reader')
    event_bound=audit['consumer_events'];need(bind(event_bound['path'])==event_bound,'C event journal changed')
    seen={};ids=set();features=[];records=[];counts=Counter()
    for event in B.stream(event_bound['path']):
        if event.get('event_type')=='s6d_beam_identity':
            row=event['payload'];key=(row.get('stream_id'),row.get('event_id'));need(key not in seen,'Duplicate native identity event');seen[key]=row
        if event.get('event_type')!='s6d_C_selector_probe':continue
        p=event['payload'];index=p.get('probe_index');need(type(index) is int and index>0 and index not in ids,'Duplicate/malformed actual probe');ids.add(index)
        record,rows,cs=collect_probe(p,seen,admission,settings,profile['embedding']['window_sec'],profile['embedding']['minimum_clean_fraction'],spans,known,job_id)
        need(all(r['source_end_sec']*16000<=job['expected_frames']+1e-5 for r in record['candidates']),'Candidate outside full captured source')
        records.append(record);features.extend(rows);counts.update(cs)
    need(ids and bind(event_bound['path'])==event_bound,'Missing/changed actual C probes')
    return dict(schema='s6d-C-beam-features.v2',status='EXTRACTED_C_ONLY_NOT_ACCEPTED_THRESHOLDS',source=bind(__file__),frozen_V1_guards=bind(V1.__file__),manifest=manifest_ref,job_id=job_id,completion=completion_ref,full_source_audit=completed['completion_audit'],support=support_ref,partition=partition['original_partition'],gallery=job['gallery'],profile_binding=job['profile_binding'],beam_settings=settings_ref,capture_profile=job['capture_profile'],settings=settings,identity_streams=settings['identity_streams'],selected_profile_ids=settings['selected_profile_ids'],capture_identity=dict(capture_source_id=admission['capture_source_id'],route_id=admission['route_id']),Q_used=False,disjoint_from_E_Q_verified=True,counts=dict(counts),actual_probe_count=len(ids),features=features,probes=records,limitations=['Common input identity does not prove source survival or exact acoustic beam target','Unresolved identities and ambiguous source support remain actual competitors; never negative truth','Original C source IDs define distinct support, not correlated model windows','No per-beam alignment, waveform/model call or Q tuning; duplicate resolution remains disabled'])

def extract(manifest_ref,job_id,completion_ref,support_ref,output):
    save(output,extract_data(manifest_ref,job_id,completion_ref,support_ref));return bind(output)

def propose(feature_refs,output):
    groups=[verified(b) for b in feature_refs];need(groups,'C features required')
    need(len({(g['manifest']['sha256'],g['job_id']) for g in groups})==len(groups),'Duplicate C job populations')
    first=groups[0];context=('gallery','profile_binding','beam_settings','capture_profile','identity_streams','selected_profile_ids','settings')
    for g in groups:
        need(g.get('schema')=='s6d-C-beam-features.v2' and g.get('Q_used') is False and g.get('disjoint_from_E_Q_verified') is True and g.get('status')=='EXTRACTED_C_ONLY_NOT_ACCEPTED_THRESHOLDS','Exact V2 C feature population required')
        need(g['source']['sha256']==bind(__file__)['sha256'] and bind(g['source']['path'])==g['source'],'Different extraction source')
        again=extract_data(g['manifest'],g['job_id'],g['completion'],g['support'])
        need({k:v for k,v in again.items() if k!='source'}=={k:v for k,v in g.items() if k!='source'},'Feature/probe population differs from bound actual closed C extraction')
        need(all(g[k]==first[k] for k in context),'Incompatible gallery/profile/capture/stream/selected opportunities')
    fit=fit_thresholds([r for g in groups for r in g['features']]);joint=None
    if fit['thresholds']:
        # Capture identities differ by case; replay each record using its actual bound case.
        tagged=[]
        for g in groups:
            for p in g['probes']:tagged.append((p,g['capture_identity']))
        joint=joint_replay_by_case(tagged,fit['thresholds'],first['settings'])
    supported=fit['thresholds'] is not None and joint is not None and joint['status']=='JOINT_REPLAY_SUPPORTED'
    result=dict(schema_version='edge-s6d-beam-calibration-proposal.v2',status='PROPOSED_C_ONLY_JOINT_SUPPORTED_PENDING_ROOT_REVIEW' if supported else 'CALIBRATION_SUPPORT_INSUFFICIENT_SELECTORS_DISABLED',source=bind(__file__),features=feature_refs,context={k:first[k] for k in context},partition='C',Q_used=False,disjoint_from_E_Q_verified=True,fit=fit,joint_replay=joint,enablement_candidate=supported,selectors_enabled=False,thresholds_accepted=False,duplicate_resolution_enabled=False,rule='Fixed thresholds exceed observed known-negative and ambiguous metric maxima by1e-6; known positive/negative support and retained positives require2 distinct C sources per gate. Exact runtime joint replay additionally requires2 retained positive,2 rejected negative-challenge and2 retained competition sources per selector, with no negative/ambiguous winner.',required_before_enablement='Root independently reviews actual scoped C support and joint evidence; only a separately accepted exact-context edge-s6d-beam-calibration.v1 receipt can enable runtime selectors.',models_started=0)
    save(output,result);return bind(output)

def joint_replay_by_case(tagged,thresholds,settings):
    # Compile the exact selector once, retaining each actual case identity.
    identities={(p['job_id'],p['probe_index']):identity for p,identity in tagged}
    need(len(identities)==len(tagged),'Duplicate actual case/probe population')
    result=joint_replay([p for p,identity in tagged],thresholds,settings,None,case_identities=identities)
    result['all_actual_runtime_competitors_retained']=True
    need(result['selector_source']['sha256']==N.PINS['beam'],'Selector source changed during joint replay')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    e=sub.add_parser('extract');e.add_argument('--manifest',type=Path,required=True);e.add_argument('--manifest-sha256',required=True);e.add_argument('--job-id',required=True);e.add_argument('--completion',type=Path,required=True);e.add_argument('--support',type=Path,required=True);e.add_argument('--output',type=Path,required=True)
    f=sub.add_parser('propose');f.add_argument('--features',type=Path,nargs='+',required=True);f.add_argument('--output',type=Path,required=True);a=p.parse_args()
    need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G-only output required');a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.cmd=='extract':
        ref=bind(a.manifest);need(ref['sha256']==a.manifest_sha256,'Manifest differs');answer=extract(ref,a.job_id,bind(a.completion),bind(a.support),a.output)
    else:answer=propose([bind(p) for p in a.features],a.output)
    print(json.dumps(answer))
