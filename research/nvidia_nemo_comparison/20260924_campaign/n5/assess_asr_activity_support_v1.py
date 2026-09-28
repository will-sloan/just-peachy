"""Offline empty-control diagnostic; README_ASR_ACTIVITY_SUPPORT_V1.md."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import pin


def records(binding):
    verify(binding)
    with gzip.open(binding['path'],'rt',encoding='utf-8') as stream:
        for line in stream:yield json.loads(line)


def union(intervals):
    out=[]
    for start,end in sorted(intervals):
        if end<=start:continue
        if out and start<=out[-1][1]:out[-1][1]=max(end,out[-1][1])
        else:out.append([start,end])
    return out


def assess(output):
    pin();local=HERE.parents[4]/'local'
    plan=load(local/'n4/integrated-main-plan-v3.json')
    # The accepted plan binds component reviews; derive no new inference.
    reviews=plan['context']['reviews']
    for key in ('ASR','D1'):verify(reviews[key])
    asr=load(reviews['ASR']['path']);d1=load(reviews['D1']['path'])
    catalog=HERE.parent/'data/CORPUS_CATALOGUE_240.csv'
    scenes=[r['case_id'] for r in csv.DictReader(catalog.open(encoding='utf-8-sig')) if r['reference_class']=='empty_control']
    assert len(scenes)==11
    jobs={f'N2_{case}_{tap}' for case in scenes for tap in ('O0','O1')}
    dmap={r['job_id']:r for r in d1['rows'] if r['encoder']=='E0' and r['job_id'] in jobs}
    amap={}
    for row in asr['cells']:
        if row['variant'] not in ('A0','A2'):continue
        job=Path(row['result']['path']).parent.name
        if job in jobs:amap[row['variant'],job]=row
    assert len(dmap)==22 and len(amap)==44
    results=[];inputs=[]
    for job in sorted(jobs):
        db=dmap[job]['result'];verify(db);d=load(db['path']);assert d['status']=='COMPLETE'
        duration=d['job']['frames']/16000;frames=[]
        for event in records(d['events']):
            if event['event_type']!='n2_diarization_frames':continue
            p=event['payload'];step=p['frame_step_sec']
            for i,probs in enumerate(p['probabilities']):
                start=(p['frame_start']+i)*step;end=min(start+step,p['audio_received_sec'],duration)
                if end>start:frames.append((start,end,sum(v>=.5 for v in probs)))
        inputs.extend([db,d['events']])
        raw=sum((e-s)*n for s,e,n in frames)
        for variant in ('A0','A2'):
            ab=amap[variant,job]['result'];verify(ab);a=load(ab['path']);assert a['status']=='COMPLETE'
            assert a['job']==d['job']
            finals={}
            for event in records(a['events']):
                if event['event_type']=='research_asr_observation':
                    p=event['payload']
                    if p['final']:finals[p['utterance_id']]=p
            intervals=[(p['source_start_sec'],p['source_end_sec']) for p in finals.values() if p['text'].strip()]
            inputs.extend([ab,a['events']])
            for pad in (0.0,0.25,0.5,1.0):
                support=union([(max(0,s-pad),min(duration,e+pad)) for s,e in intervals])
                retained=sum(n*sum(max(0,min(e,b)-max(s,a)) for a,b in support) for s,e,n in frames)
                assert -1e-9<=retained<=raw+1e-7
                results.append(dict(job_id=job,asr=variant,padding_seconds=pad,audio_seconds=duration,
                    nonempty_final_utterances=len(intervals),raw_false_speaker_seconds=raw,
                    supported_false_speaker_seconds=retained,removed_false_speaker_seconds=raw-retained))
    aggregates=[]
    for variant in ('A0','A2'):
        for pad in (0.0,0.25,0.5,1.0):
            selected=[r for r in results if r['asr']==variant and r['padding_seconds']==pad]
            raw=sum(r['raw_false_speaker_seconds'] for r in selected)
            retained=sum(r['supported_false_speaker_seconds'] for r in selected)
            aggregates.append(dict(asr=variant,padding_seconds=pad,files=len(selected),
                audio_seconds=sum(r['audio_seconds'] for r in selected),raw_false_speaker_seconds=raw,
                retained_false_speaker_seconds=retained,removed_percent=100*(raw-retained)/raw if raw else None,
                files_with_nonempty_asr=sum(r['nonempty_final_utterances']>0 for r in selected)))
    receipt=dict(status='OFFLINE_EMPTY_CONTROL_DIAGNOSTIC_ONLY',reviews=reviews,catalogue=bind(catalog),
        selected_inputs=inputs,aggregates=aggregates,rows=results,
        method='Intersect native >=0.5 activity with union of nonempty final ASR coarse utterance intervals plus fixed padding.',
        limitations=['Final ASR uses future information; not causal streaming validation.',
          'Empty controls measure false activity only; no speech recall, net DER or live latency claim.',
          'ASR intervals are coarse revision/utterance support, not exact word boundaries.',
          'Filtering runs after native inference and saves no diarizer computation.',
          'No threshold selected, deployed filter, model training or new inference.'],
        code=[bind(__file__),bind(HERE/'README_ASR_ACTIVITY_SUPPORT_V1.md')])
    freeze(output,receipt);print(aggregates)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    assess(p.parse_args().output)
