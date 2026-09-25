"""Accept exact application-lane ASR smoke evidence. README_REVIEW_ASR.md."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path

from common import audio_only,bind,freeze,fingerprint,load,verify
from asr_bank_components import component_key,verify_admission


def finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Finite numeric time required')
    return value


def scan_events(cell,read_samples):
    verify(cell['events']);job=cell['job'];variant=cell['variant'];duration=job['frames']/16000
    counts=Counter();dispatches=[];observations=[];punctuation=[];native_finals=[];drains=[]
    digest=hashlib.sha256();size=0;last_available=0.;closed=set();cursor=0
    with gzip.open(cell['events']['path'],'rb') as stream:
        for raw in stream:
            digest.update(raw);size+=len(raw);row=json.loads(raw);kind=row['event_type'];p=row['payload']
            end=finite(row['source_time_sec'])
            if not 0 <= end <= duration:raise ValueError('Event outside actual waveform')
            counts[kind]+=1
            if kind in ('research_asr_dispatch','research_asr_tail_dispatch'):
                start=finite(p['source_start_sec'])
                if p['source_end_sec']!=end or abs(start-cursor/16000)>1e-8:raise ValueError('Dispatch discontinuity')
                count=round((end-start)*16000)
                if count<=0 or count>read_samples or (kind=='research_asr_tail_dispatch' and variant!='A0'):
                    raise ValueError('Invalid actual dispatch length/type')
                cursor+=count;dispatches.append(count)
                if p.get('samples',count)!=count:raise ValueError('Dispatch sample count differs')
            elif kind=='research_asr_drain':
                if end!=duration or p['padding_is_observed_audio'] is not False:
                    raise ValueError('Flush cannot invent observed audio')
                if variant!='A0' and p['exact_input_samples']!=job['frames']:raise ValueError('Native source census differs')
                drains.append(p)
            elif kind=='research_asr_observation':
                available=finite(p['available_at_sec']);start=finite(p['source_start_sec'])
                if (not 0<=start<=end<=available or available<last_available or p['source_end_sec']!=end
                        or p['event_id']!=f'asr:{len(observations)+1:08d}' or p['kind']!='asr'
                        or type(p['final']) is not bool or not isinstance(p['text'],str)
                        or p['utterance_id'] in closed):
                    raise ValueError('Invalid causal raw observation or final history')
                if p['punctuation'] is not None:raise ValueError('Formatting has contaminated raw ASR observations')
                last_available=available;observations.append(p)
                if p['final']:closed.add(p['utterance_id'])
            elif kind=='component_final_punctuation':
                punctuation.append(p)
            elif kind=='n3_asr_result':
                if variant=='A0' or p['input_end_sec']!=end or p['input_samples']!=round(end*16000):
                    raise ValueError('Actual native result source differs')
                if p['final'] and p['raw_text']:native_finals.append(p['raw_text'])
            elif kind not in ('research_asr_reset','research_asr_full_dispatch_cost'):
                raise ValueError('Unexpected ASR component event type')
            if kind.startswith('research_asr_') and 'modeled_available_at_sec' in p:
                if finite(p['modeled_available_at_sec'])<end:raise ValueError('Modeled availability precedes support')
    if cell['events_expanded']!=dict(uncompressed_sha256=digest.hexdigest(),uncompressed_bytes=size):
        raise ValueError('Expanded event bytes differ')
    expected=[read_samples]*(job['frames']//read_samples)
    if job['frames']%read_samples:expected.append(job['frames']%read_samples)
    if dispatches!=expected or cursor!=job['frames'] or len(drains)!=1:
        raise ValueError('Missing or duplicate source dispatch/drain')
    finals=[r for r in observations if r['final']]
    if variant!='A0' and native_finals!=[r['text'] for r in finals]:
        raise ValueError('Native final text was lost or rewritten')
    if len(punctuation)!=len(finals):raise ValueError('Every raw final needs exactly one formatting result')
    previous=0.;statuses=Counter()
    for raw,p in zip(finals,punctuation):
        available=finite(p['modeled_available_at_sec'])
        if (p['raw_text']!=raw['text'] or p['input_event_id']!=raw['event_id']
                or p['utterance_id']!=raw['utterance_id']
                or p['modeled_asr_submission_at_sec']!=raw['available_at_sec']
                or available<max(previous,raw['available_at_sec'])):
            raise ValueError('Formatting input or modeled FIFO differs')
        if variant in ('A2','A3') and p['punctuation']['text']!=raw['text']:
            raise ValueError('Native punctuation was silently replaced')
        statuses[p['punctuation']['status']]+=1;previous=available
    summary=cell['summary']
    if (summary['input_samples']!=job['frames'] or summary['source_reads']!=len(expected)
            or summary['event_counts']!=dict(counts) or summary['predictor_observations']!=len(observations)
            or summary['final_utterances']!=[r['text'] for r in finals]
            or summary['raw_final_text']!=' '.join(r['text'].strip() for r in finals if r['text'].strip())
            or summary['punctuation_calls']!=len(finals) or summary['closed_watermark']['closed'] is not True
            or summary['closed_watermark']['source'] is not None
            or summary['observed_live_latency_qualified'] is not False or summary['integrated_N4_cells']!=0):
        raise ValueError('Cell summary differs from actual complete event evidence')
    return dict(dispatches=len(dispatches),source_samples=cursor,raw_observations=len(observations),
        final_utterances=len(finals),raw_final_words=sum(len(r['text'].split()) for r in finals),
        punctuation_statuses=dict(statuses),expanded_bytes=size)


def review(root,output):
    import psutil
    if output.exists():raise ValueError('Preserve previous review; choose fresh output')
    final_binding=bind(root/'RESULT.json');final=load(final_binding['path'])
    if final['status']!='SMOKE_COLLECTED_REQUIRES_REVIEW' or final['completed']!=8 or final['total']!=8:
        raise ValueError('Complete eight-cell smoke required before review')
    try:
        if psutil.Process(final['owner']['pid']).create_time()==final['owner']['create_time']:
            raise ValueError('Exact numerical coordinator is still active')
    except psutil.NoSuchProcess:pass
    contract=verify_admission(root/'ADMISSION.json');admission=bind(root/'ADMISSION.json')
    if (final['admission']!=admission or final.get('child') is not None or final['integrated_N4_cells']!=0
            or contract['total']!=8 or len(contract['jobs'])!=2 or contract['variants']!=['A0','A1','A2','A3']
            or len(final['variants'])!=4):raise ValueError('Smoke admission/census disagreement')
    cells=[];bindings=[]
    for variant,binding in zip(contract['variants'],final['variants']):
        verify(binding)
        if Path(binding['path']).resolve()!=(root/variant/'RESULT.json').resolve():raise ValueError('Wrong variant result path')
        index=load(binding['path']);progress=load(root/variant/'RESULT_INDEX.json')
        if (index['status']!='COMPLETE' or index['variant']!=variant or index['completed']!=2 or index['total']!=2
                or index['cpu_affinity']!=[4] or set(index['cells'])!={j['job_id'] for j in contract['jobs']}
                or progress['cells']!=index['cells'] or progress['completed']!=2 or progress['total']!=2):
            raise ValueError('Variant index is incomplete or changed')
        bindings.extend([binding,bind(root/variant/'RESULT_INDEX.json')])
        for job in contract['jobs']:
            audio_only(job);result_binding=index['cells'][job['job_id']];verify(result_binding)
            cell=load(result_binding['path']);profile=contract['profiles'][job['tap']]
            if (Path(result_binding['path']).resolve()!=(root/variant/job['job_id']/'RESULT.json').resolve()
                    or cell['schema']!='n4-asr-component-cell-v1' or cell['status']!='COMPLETE'
                    or cell['job']!=job or cell['variant']!=variant or cell['admission_sha256']!=admission['sha256']
                    or cell['profile_sha256']!=fingerprint(profile) or cell['cache_key']!=component_key(contract,job,variant,profile)
                    or cell['actual_neural_inference'] is not True or cell['cpu_affinity']!=[4] or cell['integrated_N4_cells']!=0):
                raise ValueError('Cell contract/cache differs')
            if Path(cell['events']['path']).resolve()!=(root/variant/job['job_id']/'ASR_EVENTS.jsonl.gz').resolve():
                raise ValueError('Wrong cell event path')
            if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Audio bytes changed')
            scan=scan_events(cell,round(profile['asr']['journal_read_ms']*16))
            cells.append(dict(variant=variant,result=result_binding,scan=scan));bindings.append(result_binding)
    for binding in [final_binding,admission,*bindings]:verify(binding)
    receipt=dict(schema='n4-asr-smoke-review-v1',status='PASS_ASR_COMPONENT_SMOKE',utc=datetime.now(timezone.utc).isoformat(),
        component_cells=8,per_variant=2,component_contract_sha256=fingerprint(contract['component_contract']),
        admission=admission,final_result=final_binding,cells=cells,integrated_N4_cells=0,
        full_bank_admitted=False,Controller_or_widget_parity_qualified=False,live_latency_qualified=False,
        notes='Native application ASR-loop evidence only. Actual text remains private; formatting quality needs separate metrics.',
        code=[bind(Path(__file__).with_name(n)) for n in ('review_asr_components.py','test_review_asr_components.py','README_REVIEW_ASR.md')])
    output.mkdir(parents=True,exist_ok=False);freeze(output/'REVIEW.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    import psutil
    process=psutil.Process();process.cpu_affinity([14])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    print(json.dumps(review(args.run,args.output),indent=2))
