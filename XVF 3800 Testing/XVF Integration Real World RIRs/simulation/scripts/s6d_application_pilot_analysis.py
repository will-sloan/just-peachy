"""Analyze only admitted frozen pilot receipts. See README_S6D_APPLICATION_PILOT_ANALYSIS.md."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

V3_SHA='ec110adcbaf230c5f33b49629967e163f5d526b7a339123c05fb000a14d7138f'


def bind(path):
    path=Path(path).resolve();h=hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda:handle.read(1024*1024),b''):h.update(part)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def jsonl(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def tokens(text):return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?",text.lower())


def summary(values):
    xs=sorted(float(x) for x in values if isinstance(x,(int,float)) and math.isfinite(x))
    def percentile(q):
        at=(len(xs)-1)*q;lo=int(at);hi=math.ceil(at)
        return xs[lo]+(xs[hi]-xs[lo])*(at-lo)
    return {'count':len(xs),'p50':percentile(.5) if xs else None,'p95':percentile(.95) if xs else None,
        'p99':percentile(.99) if xs else None,'maximum':max(xs) if xs else None,'minimum':min(xs) if xs else None}


def semantic_errors(result,job,manifest_binding,manifest):
    errors=[]
    if result.get('job')!=job:errors.append('job_mismatch')
    if result.get('manifest')!=manifest_binding:errors.append('manifest_mismatch')
    if result.get('helper')!=manifest['helper']:errors.append('helper_mismatch')
    if result.get('status')!='COMPLETE' or result.get('failure') is not None or result.get('native_tested') is not True:
        errors.append('native_semantic_failure')
    if result.get('resource_observer_closed') is not True or result.get('event_consumer_drained') is not True or result.get('observer_errors') or result.get('completion_errors'):
        errors.append('observer_or_drain_failure')
    if result.get('telemetry',{}).get('state')!='COMPLETED':errors.append('engine_not_completed')
    return errors


def analyze_cell(job,manifest_binding,manifest):
    output=Path(job['output']);result_path=output/'RESULT.json'
    base={'job_id':job['job_id'],'candidate':job['candidate'],'scene_id':job['scene_id'],'variant':job['variant'],
        'source_duration_sec':job['audio_duration_sec']}
    if not result_path.exists():return {**base,'status':'UNAVAILABLE','reason':'No RESULT receipt; not imputed'},None
    result=read(result_path);errors=semantic_errors(result,job,manifest_binding,manifest)
    if errors:return {**base,'status':'FAILED_OR_UNADMITTED','errors':errors,'receipt':bind(result_path),'failure':result.get('failure')},None
    session=Path(result['session_dir']);paths={'consumer':output/'consumer_events.jsonl','journal':session/'events.jsonl',
        'resources':output/'resources.jsonl','latest':session/'latest_labelled_transcript.jsonl','finalization':session/'session_finalization_v3.json'}
    absent=[k for k,p in paths.items() if not p.exists()]
    if absent:return {**base,'status':'MISSING_EVIDENCE','missing':absent,'receipt':bind(result_path)},None
    finalization=read(paths['finalization'])
    if finalization.get('state')!='COMPLETED' or finalization.get('event_and_transcript_handles_closed') is not True or finalization.get('live_lanes_at_finalization') or finalization.get('finalization_error'):
        return {**base,'status':'INVALID_FINALIZATION','receipt':bind(result_path),'finalization':finalization},None
    events=jsonl(paths['consumer']);journal=jsonl(paths['journal']);resources=jsonl(paths['resources']);latest=jsonl(paths['latest'])
    event_type=lambda r:r.get('event_type')
    payload=lambda r:r.get('payload',r)
    origins=[payload(r)['pilot_publication_monotonic_sec'] for r in events if event_type(r)=='source_started']
    if len(origins)!=1:raise ValueError('Exactly one bound actual source_started required: '+job['job_id'])
    origin=origins[0];first={}
    kinds={'s6d_text_ready'} if job['settings'] and job['settings']['text_delivery'] else {'transcript_partial','transcript_final'}
    for event in events:
        p=payload(event);key=p.get('utterance_id')
        if event_type(event) not in kinds or not p.get('text','').strip() or key in first:continue
        publication=p.get('pilot_publication_monotonic_sec');consumed=event.get('actual_consumed_monotonic_sec')
        if not isinstance(publication,(int,float)) or not isinstance(consumed,(int,float)):raise ValueError('Actual monotonic clocks missing')
        first[key]={'utterance_id':key,'text':p['text'],'source_start_sec':p.get('source_start_sec'),
            'source_end_sec':p.get('source_end_sec'),'publication_from_source_start_sec':publication-origin,
            'consumer_from_source_start_sec':consumed-origin,'consumer_queue_delay_sec':consumed-publication,
            'publication_minus_source_end_sec':publication-origin-p['source_end_sec'] if p.get('source_end_sec') is not None else None}
    finals={r['utterance_id']:r for r in latest};missing=sorted(set(finals)-set(first))
    timing={key:summary(r[key] for r in first.values()) for key in ('publication_from_source_start_sec','consumer_from_source_start_sec','consumer_queue_delay_sec','publication_minus_source_end_sec')}
    startup={}
    for kind in ('session_created','research_models_ready','session_started'):
        rows=[payload(r) for r in events if event_type(r)==kind]
        startup[kind]=[{'publication_before_source_start_sec':origin-r['pilot_publication_monotonic_sec'],
            'model_load_elapsed_sec':r.get('model_load_elapsed_sec'),'session_elapsed_sec':r.get('session_elapsed_sec')} for r in rows]
    resource_summary={key:summary(r.get(key) for r in resources) for key in ('rss','uss','process_tree_rss','threads','cpu_percent','sampling_gap_sec')}
    queue_metrics={}
    for name in ('event_consumer','journal','punctuation','policy'):
        samples=[r.get('telemetry',{}).get('s6d',{}).get(name) for r in resources if r.get('telemetry',{}).get('s6d')]
        samples=[r for r in samples if isinstance(r,dict)]
        queue_metrics[name]={key:summary(r.get(key) for r in samples) for key in ('depth','oldest_age_sec','max_age_sec','max_handler_sec','max_depth')}
    labels=[{k:r.get(k) for k in ('utterance_id','source_start_sec','source_end_sec','text','first_display_label','first_display_time',
        'first_final_label','first_final_time','latest_label','latest_state','latest_known_profile_id','latest_known_name','latest_naming_state','revision_count')} for r in latest]
    revisions=[payload(r) for r in journal if event_type(r)=='transcript_label_revision']
    resultrow={**base,'status':'ANALYZED','receipt':bind(result_path),'evidence':{k:bind(p) for k,p in paths.items()},
        'source_start_monotonic_sec':origin,'startup':startup,'first_text':list(first.values()),'first_text_metrics':timing,
        'never_emitted_final_ids':missing,'never_emitted_final_count':len(missing),'identity_final_rows':labels,'identity_revisions':revisions,
        'naming_state_counts':dict(Counter(str(r.get('latest_naming_state')) for r in latest)),
        'latest_final_unknown_name_rows':sum(r.get('latest_known_profile_id') is None for r in latest),
        'latest_final_raw_word_count':sum(len(tokens(r['text'])) for r in latest),'resource_metrics':resource_summary,
        'queue_metrics':queue_metrics,'final_queues':result.get('telemetry',{}).get('s6d'),
        'source_cursor_sec':result.get('telemetry',{}).get('source_duration_sec'),'asr_cursor_sec':result.get('telemetry',{}).get('asr_cursor_sec'),
        'speaker_cursor_sec':result.get('telemetry',{}).get('speaker_cursor_sec'),'native_elapsed_sec':result.get('elapsed_sec'),
        'physical_tested':False,'gui_tested':False,'cm5_tested':False}
    return resultrow,{'first':first,'finals':finals}


def pair(left,right,data,scope):
    base={'left_job_id':left,'right_job_id':right,'comparison':scope}
    if left not in data or right not in data:return {**base,'status':'UNAVAILABLE','reason':'One or both cells absent or unadmitted'}
    a=data[left];b=data[right];ids=sorted(set(a['finals'])|set(b['finals']))
    words=[{'utterance_id':key,'left_text':a['finals'].get(key,{}).get('text'),'right_text':b['finals'].get(key,{}).get('text'),
        'exact_raw_equal':a['finals'].get(key,{}).get('text')==b['finals'].get(key,{}).get('text')} for key in ids]
    timings=[]
    for key in sorted(set(a['first'])|set(b['first'])):
        x=a['first'].get(key);y=b['first'].get(key)
        compatible=x is not None and y is not None and x['source_start_sec']==y['source_start_sec']
        timings.append({'utterance_id':key,'compatible_source_start':compatible,'left_never':x is None,'right_never':y is None,
            'first_hypothesis_equal':x['text']==y['text'] if x and y else None,
            'publication_right_minus_left_sec':y['publication_from_source_start_sec']-x['publication_from_source_start_sec'] if compatible else None,
            'consumer_right_minus_left_sec':y['consumer_from_source_start_sec']-x['consumer_from_source_start_sec'] if compatible else None})
    raw_equal=all(x['exact_raw_equal'] for x in words)
    publication=summary(x['publication_right_minus_left_sec'] for x in timings)
    consumer=summary(x['consumer_right_minus_left_sec'] for x in timings)
    return {**base,'status':'ANALYZED','raw_final_rows':words,'all_raw_final_rows_equal':raw_equal,
        'concatenated_normalized_words_equal':[t for r in a['finals'].values() for t in tokens(r['text'])]==[t for r in b['finals'].values() for t in tokens(r['text'])],
        'first_text_pairs':timings,'additional_publication_delay':publication,'additional_consumer_delay':consumer,
        'latency_goals_diagnostic_only':{'p50_le_0_10':publication['p50']<=.10 if publication['count'] else None,
            'p95_le_0_25':publication['p95']<=.25 if publication['count'] else None},
        'qualification':'Small pilot; not a full-bank timing qualification. Endpoint/word differences remain adverse.'}


def run(manifest_path,output):
    binding=bind(manifest_path)
    if binding['sha256']!=V3_SHA:raise ValueError('This analyzer is prebound to reviewed frozen v3 only')
    manifest=read(manifest_path);output.mkdir(parents=True,exist_ok=False)
    plan={'schema':'s6d-native-pilot-analysis-plan.v1','manifest':binding,'helper':bind(__file__),
        'timing_goals':manifest['timing_goals'],'selection':'All12 predeclared jobs, no result selection',
        'clock':'Actual pilot_publication_monotonic_sec and actual_consumed_monotonic_sec, each normalized by actual source_started publication in its own process.',
        'source_pacing':'WavSource appends a 0.1s block before sleeping its duration. source_started precedes first block; publication minus source_end may be about -0.1s without future audio. No exact block-arrival clock is inferred.',
        'startup':'Cold model initialization/hash cost reported separately; no unmeasured warmup deducted.',
        'pairing':'Stable utterance ID with identical source_start; unequal words/endpoints retained as adverse, not silently realigned.',
        'unknown':'No current known profile counted as unnamed; this includes correctly anonymous C065 and is not itself a naming error.',
        'missing':'Absent, failed, invalid-finalized cells stay unavailable. No zero latency/false successful result imputation.'}
    (output/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
    rows=[];data={}
    for job in manifest['jobs']:
        row,detail=analyze_cell(job,binding,manifest);rows.append(row)
        if detail is not None:data[job['job_id']]=detail
    pairs=[]
    for candidate in ('C065','C088','C105'):
        for scene in ('S45_01_06','S45_08_07'):
            for variant in ('delivery_only','delivery_repair'):
                left=f'{candidate}_{scene}_original';right=f'{candidate}_{scene}_{variant}'
                if any(j['job_id']==right for j in manifest['jobs']):pairs.append(pair(left,right,data,'Within candidate: original to '+variant))
    for scene in ('S45_01_06','S45_08_07'):
        for variant in ('original','delivery_repair'):
            for named in ('C088','C105'):
                left=f'C065_{scene}_{variant}';right=f'{named}_{scene}_{variant}'
                if any(j['job_id']==right for j in manifest['jobs']):pairs.append(pair(left,right,data,'Naming additional delay over same anonymous C065 parent'))
    result={'schema':'s6d-native-pilot-analysis.v1','status':'COMPLETE_ANALYSIS' if len(data)==12 else 'PARTIAL_MISSING_EVIDENCE',
        'plan':bind(output/'PLAN.json'),'analyzed_count':len(data),'declared_count':12,'cells':rows,'pairs':pairs,
        'default_promoted':False,'full_bank_tested':False,'paced_finalists_tested':False,'long_session_tested':False}
    (output/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'analyzed':len(data),'result':bind(output/'RESULT.json')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.manifest,args.output)
