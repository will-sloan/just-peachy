"""Additive interpretation/matching repair; README_S6C_CUE_METRICS_V2.md."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import s6c_enrollment as E

SOURCE=E.REPORT/'cue_audit_v1/PHYSICAL_CUE_AUDIT.json'
OUT=E.REPORT/'cue_audit_v2'

def match(predictions,references,maximum_lag=1.):
    """Maximum-cardinality ordered causal interval matching; no predictor input."""
    ordered=sorted(enumerate(references),key=lambda x:(x[1]['time_sec'],x[0]))
    pending=list(ordered);pairs=[]
    for pi,p in sorted(enumerate(predictions),key=lambda x:(x[1]['time_sec'],x[0])):
        pending=[(ri,r) for ri,r in pending if r['time_sec']>=p['time_sec']-maximum_lag]
        eligible=[(ri,r) for ri,r in pending if r['time_sec']<=p['time_sec']]
        if eligible:
            ri,r=eligible[0];pending.remove((ri,r))
            pairs.append(dict(prediction=pi,reference=ri,lag_sec=p['time_sec']-r['time_sec']))
    return dict(predictions=len(predictions),references=len(references),matched=len(pairs),
        precision=len(pairs)/len(predictions) if predictions else None,
        recall=len(pairs)/len(references) if references else None,pairs=pairs,
        matching='Maximum-cardinality ordered one-to-one matching, causal lag0..1s; earliest eligible reference first')

def checks():
    refs=[dict(time_sec=0.),dict(time_sec=.5)]
    preds=[dict(time_sec=.6),dict(time_sec=1.1)]
    assert match(preds,refs)['matched']==2
    assert match([dict(time_sec=-.1)],refs)['matched']==0
    assert match([dict(time_sec=3.)],refs)['matched']==0
    assert match(list(reversed(preds)),list(reversed(refs)))['matched']==2
    assert match(preds,[])['recall'] is None
    assert match([],refs)['precision'] is None
    return dict(status='PASS',checks=6,new_models=0)

def run():
    target=OUT/'PHYSICAL_CUE_METRIC_CORRECTION_V2.json'
    if target.exists():raise ValueError('Additive correction already exists; never overwrite')
    receipt=E.read(SOURCE)
    if receipt['status']!='COMPLETE_PHYSICAL_DIAGNOSTICS_ONLY' or len(receipt['rows'])!=240:raise ValueError('Complete V1 required')
    rows=[];summary={}
    for row in receipt['rows']:
        E.verify(row['result']);case=E.read(row['result']['path'])
        rows.append(dict(case_id=row['case_id'],source=row['result'],person_transition_detection=match(case['sustained_selected_changes'],case['local_person_transitions']),
            position_transition_detection=match(case['sustained_selected_changes'],case['local_nominal_position_transitions'])))
    for key in ('person_transition_detection','position_transition_detection'):
        p=sum(r[key]['predictions'] for r in rows);r=sum(r[key]['references'] for r in rows);m=sum(r[key]['matched'] for r in rows)
        summary[key]=dict(predictions=p,references=r,matched=m,precision=m/p if p else None,recall=m/r if r else None)
    value=dict(schema='s6c-physical-cue-metric-correction.v2',status='COMPLETE_ADDITIVE_METRIC_CORRECTION',created_utc=E.utc(),
        source=E.bind(SOURCE),code=E.bind(__file__),readme=E.bind(Path(__file__).with_name('README_S6C_CUE_METRICS_V2.md')),
        checks=checks(),rows=rows,corrected_local_sustained_change_summary=summary,
        receipt_age_scope=dict(original_field='stream_populations[].host_receipt_age',
            actual_mean_definition='Duration-weighted interval-start receipt age; the age value is sampled at each state-interval left endpoint',
            actual_spread_definition='Spread of those interval-start age values, weighted by interval duration',
            limitations='Not analytic time-average age or whole-time peak age; age increases inside intervals. Original age numbers remain unchanged and are not used for freshness decisions.'),
        lineage='V1 source/helper/README/results remain unchanged. This correction replaces nearest-latest greedy reference matching only and narrows age interpretation.',
        no_raw_trace_rescan=True,new_model_calls=0,new_policy_runs=0,new_hardware_passes=0)
    E.save(target,value)
    (OUT/'PHYSICAL_CUE_METRIC_CORRECTION_V2.md').write_text(
        '# Physical cue audit: additive metric correction\n\n'
        'Use the V2 matching counts in the adjacent JSON. They maximize the number of causal one-to-one matches within the predeclared 0–1 s interval. The original V1 nearest-latest greedy counts are retained as history. No detector threshold or prediction event changed.\n\n'
        'The V1 `host_receipt_age` mean/spread are duration-weighted samples at interval starts. They are not analytic time averages or continuous-time maxima. Freshness decisions themselves used the exact existing receipt-expiry boundaries.\n\n'
        'This is an evaluator-only correction using all 240 already-bound case summaries; no raw telemetry, model, policy or hardware run was repeated.\n',encoding='utf-8')
    return E.bind(target)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('checks','run'));a=p.parse_args()
    print(json.dumps({'checks':checks,'run':run}[a.action](),indent=2))
