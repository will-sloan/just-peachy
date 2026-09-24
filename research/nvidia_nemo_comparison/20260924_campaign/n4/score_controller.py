"""Score immutable Controller results into a new directory. README_METRICS.md."""
import argparse
from collections import defaultdict
import json
import hashlib
from pathlib import Path
from common import load,sha,bind,freeze,audio_only
from metrics import score_cell,aggregate,require_versions


def convert(result):
    """Actual words only; no shadow-label outputs are promoted to widget evidence."""
    attempt=Path(result['attempt'])
    by_path={str(Path(r['path']).resolve()):r for r in result['evidence']}
    def evidence(path):
        bound=by_path.get(str(path.resolve()))
        if not bound or path.stat().st_size!=bound['bytes'] or sha(path)!=bound['sha256']:
            raise ValueError('Required execution evidence missing or changed: '+str(path))
        return load(path)
    snapshot=evidence(attempt/'FINAL_SNAPSHOT.json')
    events_path=attempt/'RUNTIME_EVENTS.jsonl'
    event_binding=by_path.get(str(events_path.resolve()))
    if not event_binding or bind(events_path)!=event_binding:
        raise ValueError('Runtime events are not bound to completed execution')
    groups={}
    for row in snapshot['rows']:
        groups.setdefault(row['utterance_id'],[]).append(row)
    segments=[];texts=[]
    for rows in groups.values():
        if all('raw_asr_text' in r for r in rows):
            rows=sorted(rows,key=lambda r:r.get('token_range',[0])[0])
            # Raw fragments preserve the original whitespace at token boundaries.
            texts.append(''.join(r['raw_asr_text'] for r in rows))
            segments.extend(dict(text=r['raw_asr_text'],track=r.get('track_id') or 'Unknown') for r in rows)
        elif len(rows)==1:
            r=rows[0];texts.append(r.get('text',''))
            segments.append(dict(text=r.get('text',''),track=r.get('track_id') or 'Unknown'))
        else:
            raise ValueError('Ambiguous repeated utterance without token-fragment support')
    duration=result['audio']['frames']/16000
    activity=[];native_frames=0;overhang=0.
    with events_path.open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['event_type']!='n2_diarization_frames':continue
            p=row['payload'];step=p['frame_step_sec']
            support=min(duration,p['audio_received_sec'])
            for offset,probabilities in enumerate(p['probabilities']):
                start=(p['frame_start']+offset)*step;end=start+step;native_frames+=1
                overhang+=max(0,end-max(start,support))
                # Score only the actual observed waveform's support; preserve
                # all original probabilities/timestamps and report excluded tail.
                if start>=support:continue
                for slot,probability in enumerate(probabilities):
                    if probability>=p.get('activity_threshold',.5):
                        activity.append(dict(start=start,end=min(end,support),label=p['track_ids'][slot]))
    return dict(job_id=result['job_id'],status='COMPLETE',raw_text=' '.join(texts),segments=segments,
        activity=activity if native_frames else None,
        activity_support=dict(native_frames=native_frames,overhang_seconds=overhang,
            rule='intersection with actual delivered waveform; no truth-fitted shift; raw events unchanged'),
        first_widget_visibility='UNAVAILABLE_CONTROLLER_ONLY',source_result_scope=result.get('resource_scope'))


def main(args):
    import os
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    import psutil
    process=psutil.Process();process.cpu_affinity([4])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    args.output.mkdir(parents=True,exist_ok=False)
    index=load(args.index);manifest=load(args.manifest)
    admission_path=args.index.parent/'ADMISSION.json'
    admission=load(admission_path)
    def n2_hash(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if n2_hash(admission['contract'])!=admission['contract_sha256'] or index['contract_sha256']!=admission['contract_sha256']:
        raise ValueError('Execution admission/index contract differs')
    if admission['contract']['manifest']!=bind(args.manifest):
        raise ValueError('Execution used a different audio manifest')
    truth={r['job_id']:r for r in load(args.truth)['cells']}
    complete=index['completed'];failed=index['failed'];jobs=manifest['jobs']
    ids={j['job_id'] for j in jobs}
    if len(ids)!=len(jobs) or not set(complete).isdisjoint(failed) or (set(complete)|set(failed))-ids:
        raise ValueError('Unknown, duplicate or contradictory result population')
    rows=[];bindings=[]
    for job in jobs:
        audio_only(job)
        jid=job['job_id']
        if jid not in truth or truth[jid]['frames']!=job['frames']:
            raise ValueError('Reference/audio population differs')
        if jid in complete or jid in failed:
            result_path=Path((complete if jid in complete else failed)[jid])
            result=load(result_path)
            checkpoint=load(result_path.parent.parent/'CHECKPOINT.json')
            if checkpoint['result']!=bind(result_path) or checkpoint['cache_key']!=result['cache_key']:
                raise ValueError('Execution checkpoint/result changed')
            if result['cache_key']!=n2_hash(dict(contract=admission['contract_sha256'],job=job)):
                raise ValueError('Result does not belong to this admission')
            if result['audio']!=job or result['job_id']!=jid:
                raise ValueError('Execution audio differs from required job')
            bindings.append(bind(result_path))
            expected='COMPLETE' if jid in complete else 'FAILED'
            if result['status']!=expected:
                raise ValueError('Result/index status disagreement')
            prediction=convert(result) if expected=='COMPLETE' else dict(job_id=jid,status='FAILED')
        else:
            prediction=dict(job_id=jid,status='NOT_TESTED')
        row=score_cell(truth[jid],prediction)
        if 'activity_support' in prediction:row['activity_support']=prediction['activity_support']
        rows.append(row)
    result=dict(schema='n4-established-controller-score-v1',
        status='ACTUALLY_SCORED_EXISTING_EXECUTION',scope=args.scope,
        completed_N4_inference_claimed=False,metrics=aggregate(rows),rows=rows,
        metric_versions=require_versions(),
        inputs=[bind(p) for p in (args.index,admission_path,args.manifest,args.truth,Path(__file__),Path(__file__).with_name('metrics.py'))],
        execution_results=bindings)
    freeze(args.output/'SCORES.json',result)
    print(json.dumps(dict(status=result['status'],scope=args.scope,metrics=result['metrics']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('index','manifest','truth','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--scope',required=True,help='e.g. N2 screen rescore; never relabel as N4 full bank')
    main(p.parse_args())
