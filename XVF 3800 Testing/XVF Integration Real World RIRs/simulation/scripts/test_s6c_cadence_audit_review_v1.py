"""Independent compact cadence report review. README_S6C_CADENCE_AUDIT_REVIEW_V1.md."""
import argparse
from collections import Counter,defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

SIM=Path(__file__).resolve().parents[1];REPORT=SIM/'reports/S6C/20260910T123540Z'
def bind(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(binding):
    raw=Path(binding['path']).read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('Bound metadata changed')
    return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def equal(a,b):
    if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(equal(v,b[k]) for k,v in a.items())
    if isinstance(a,(list,tuple)):return isinstance(b,(list,tuple)) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if type(a) in (int,float) and type(b) in (int,float):return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
    return a==b
def main(output):
    if output.exists():raise ValueError('Preserve prior review')
    rb=bind(REPORT/'cadence_audit_v1/RESULT.json')
    assert rb['sha256']=='96f9b5d604001f740543dc98945e8ad6f31b30aa137687e973bb9aec77779e4d'
    result=read(rb);plan=read(result['plan']);cells=read(result['cells_binding'])['rows'];checks=3
    for b in (result['source'],result['readme'],plan['source'],plan['readme']):assert bind(b['path'])==b;checks+=1
    assert len(cells)==336 and len({(r['candidate_id'],r['case_id'],r['tap']) for r in cells})==336;checks+=1
    expected=set()
    for row in cells:
        a=row['data'];event=row['events'];assert event['streamed_bytes']==event['binding']['bytes'] and event['sha256']==event['binding']['sha256'];checks+=1
        assert sum(a['role_opportunities'].values())==2*a['source_dispatches'];checks+=1
        assert a['actual_embedding_calls']==a['event_counts'].get('research_embedding',0);checks+=1
        assert a['queue']['final_pending']==0 and a['queue']['peak_journal_lag_sec'] is None;checks+=1
        assert a['target_track_chosen_count'] is None and a['sole_cue_causal_admission_count'] is None;checks+=1
        expected.add((row['case_id'],row['tap']))
    assert len(expected)==112;checks+=1
    for summary in result['summary']:
        group=[r for r in cells if r['candidate_id']==summary['candidate_id'] and r['tap']==summary['tap']]
        assert len(group)==56;checks+=1
        for key,cellkey in (('source_duration_sec','duration_sec'),('worker_elapsed_sum_sec','worker_elapsed_sec'),('native_elapsed_sum_sec','native_elapsed_sec'),('process_cpu_sum_sec','process_cpu_sec')):
            assert equal(sum(r[cellkey] for r in group),summary[key]);checks+=1
        for key in ('source_dispatches','actual_embedding_calls'):
            assert sum(r['data'][key] for r in group)==summary[key];checks+=1
        for key in ('flags','reasons','event_counts'):
            value=Counter()
            for row in group:value.update(row['data'][key])
            assert dict(value)==summary[key];checks+=1
        for name,value in summary['numeric'].items():
            entries=[r['data']['numeric'][name] for r in group if name in r['data']['numeric']]
            observed=sum(e['observed'] for e in entries);total=sum(e['sum'] for e in entries)
            expected_value=dict(observed=observed,missing=sum(e['missing'] for e in entries),sum=total,
                min=min((e['min'] for e in entries if e['min'] is not None),default=None),max=max((e['max'] for e in entries if e['max'] is not None),default=None),mean=total/observed if observed else None)
            assert equal(expected_value,value);checks+=1
        costs=defaultdict(Counter)
        for row in group:
            for kind,values in row['data']['inclusive_costs_sec'].items():costs[kind].update(values)
        assert equal({k:dict(v) for k,v in costs.items()},summary['inclusive_costs_sec']);checks+=1
        assert summary['scheduler_peak_pending']==max((r['data']['queue']['observed_max_pending'] for r in group if r['data']['queue']['observed_max_pending'] is not None),default=None);checks+=1
    spec=importlib.util.spec_from_file_location('cadence_independent_review',result['source']['path']);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    fixtures=module.tests();assert fixtures['checks']==12 and fixtures['neural_calls']==0;checks+=1
    interpretation=bind(REPORT/'cadence_audit_v1/INTERPRETATION.md')
    review=dict(status='PASS_COMPACT_ARITHMETIC_AND_SOURCE_REVIEW',schema='s6c_cadence_independent_review.v1',checks=checks,original_pure_fixtures=fixtures,
        result=rb,plan=result['plan'],cells=result['cells_binding'],interpretation=interpretation,source=result['source'],readme=result['readme'],
        reviewer=bind(__file__),reviewer_readme=bind(Path(__file__).with_name('README_S6C_CADENCE_AUDIT_REVIEW_V1.md')),
        scope='Independent aggregation from exact336 compact cell buffers and read-only source semantics. No second native-event scan, model/audio/vector read or metric rerun. The bound original stream audit establishes each event-byte hash; this review does not independently rehash those large logs.',
        interpretation_checks=['Role counts distinct from shared dispatches; actual accepted embedding correspondence retained.','Acknowledged due entries are repeated ledger entries, not selected identities or debtor-specific voice delivery.','Context stamp is the newest released row snapshot, not every track age.','Scheduler maintained peak pending count is separate from final journal lag; missing peak journal lag remains null.','Model/API/full-dispatch costs are nested and cannot be summed as wall speedup.','Zero direct cue-event flags do not establish raw direction stability or isolate association-mediated scheduling effects.'])
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(review,f,indent=2,allow_nan=False)
    print(json.dumps(bind(output),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
