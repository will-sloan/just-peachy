"""Independent compact cadence arithmetic; README_S6C_CADENCE_COMPACT_REVIEW_V1.md."""
from __future__ import annotations
import argparse,hashlib,json,math
from collections import defaultdict
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
SHA='4b796e8dc5591fc4c61b425b2d504dfb13c414d631acb5021dd2f50f400e25e9'

def bind(path,raw=None):
    p=Path(path).resolve();b=p.read_bytes() if raw is None else raw;return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def read(binding):
    raw=Path(binding['path']).read_bytes();assert bind(binding['path'],raw)==binding
    return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def counts(rows):
    out={}
    for row in rows:
        for key,value in row.items():out[key]=out.get(key,0)+value
    return out
def reconstruct(rows,candidate,tap):
    cells=[r for r in rows if (r['candidate_id'],r['tap'])==(candidate,tap)];numeric=defaultdict(list);costs=defaultdict(list)
    for cell in cells:
        for key,value in cell['data']['numeric'].items():numeric[key].append(value)
        for key,value in cell['data']['inclusive_costs_sec'].items():costs[key].append(value)
    numbers={}
    for key,values in numeric.items():
        observed=sum(v['observed'] for v in values);total=sum(v['sum'] for v in values)
        numbers[key]=dict(observed=observed,missing=sum(v['missing'] for v in values),sum=total,
            min=min((v['min'] for v in values if v['min'] is not None),default=None),max=max((v['max'] for v in values if v['max'] is not None),default=None),mean=total/observed if observed else None)
    return dict(candidate_id=candidate,tap=tap,native_cells=len(cells),source_duration_sec=sum(r['duration_sec'] for r in cells),
        source_dispatches=sum(r['data']['source_dispatches'] for r in cells),actual_embedding_calls=sum(r['data']['actual_embedding_calls'] for r in cells),
        flags=counts([r['data']['flags'] for r in cells]),reasons=counts([r['data']['reasons'] for r in cells]),event_counts=counts([r['data']['event_counts'] for r in cells]),numeric=numbers,inclusive_costs_sec={key:counts(values) for key,values in costs.items()},
        scheduler_peak_pending=max((r['data']['queue']['observed_max_pending'] for r in cells if r['data']['queue']['observed_max_pending'] is not None),default=None),
        scheduler_peak_pending_missing_cells=sum(r['data']['queue']['observed_max_pending'] is None for r in cells),worker_elapsed_sum_sec=sum(r['worker_elapsed_sec'] for r in cells),native_elapsed_sum_sec=sum(r['native_elapsed_sec'] for r in cells),process_cpu_sum_sec=sum(r['process_cpu_sec'] for r in cells),peak_journal_lag_sec=None,target_track_chosen_count=None,sole_cue_causal_admission_count=None)
def run(output):
    assert not (REPORT/'PACED_QUIET_OWNER.json').exists()
    rb=bind(REPORT/'cadence_floor_audit_v3/RESULT.json');assert rb['sha256']==SHA;result=read(rb);data=read(result['cells_binding']);rows=data['rows']
    assert result['status']=='COMPLETE_448_NEW_BOUND_NATIVE_CELLS' and result['cells']==len(rows)==448
    keys={(r['candidate_id'],r['case_id'],r['tap']) for r in rows};cases={r['case_id'] for r in rows}
    assert len(cases)==56 and len(keys)==448 and keys=={(c,s,t) for c in ('C191','C192','C193','C194') for s in cases for t in ('O0','O1')}
    checked=0
    def compare(a,b):
        nonlocal checked
        if isinstance(a,dict):assert isinstance(b,dict) and set(a)==set(b);[compare(a[k],b[k]) for k in a]
        elif type(a) is float:assert type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9);checked+=1
        else:assert type(a)==type(b) and a==b;checked+=1
    assert len(result['summary'])==8 and len({(r['candidate_id'],r['tap']) for r in result['summary']})==8
    for aggregate in result['summary']:compare(reconstruct(rows,aggregate['candidate_id'],aggregate['tap']),aggregate)
    source=bind(__file__);readme=bind(HERE/'README_S6C_CADENCE_COMPACT_REVIEW_V1.md')
    report=dict(status='PASS_INDEPENDENT_COMPACT_ARITHMETIC',sources=[source,readme,rb,result['cells_binding']],complete_cells=448,unique_cases=56,aggregates=8,leaf_checks=checked,
        summary=[{k:r[k] for k in ('candidate_id','tap','native_cells','source_dispatches','actual_embedding_calls','worker_elapsed_sum_sec','process_cpu_sum_sec')} for r in result['summary']],
        scope='Independent eight-aggregate recomputation from exact parsed compact448 cell buffer. Counts/nulls/keys exact, finite float sums within1e-9 absolute/1e-12 relative. No raw event/source/model reads, no rescoring or inference; parent336 compact observations unchanged. Due opportunity and source-paced limitations remain inherited.',raw_native_event_reads=0,model_calls=0)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    return bind(output)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.output)))
