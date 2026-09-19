"""Narrow independent native176 builder review; see README_S6D_NATIVE176_SCORING_INPUTS_REVIEW_V1.md."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
TARGET=R/'application/native176_scoring_preparation_v1/source_epoch/s6d_native176_scoring_inputs_v1.py'
TARGET_SHA='e379a78c98c937e32549494da52cf1da68278a40ec67294885c1d4fe19299957'

def bind(p):
    p=Path(p).resolve();data=p.read_bytes();return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def need(v,m):
    if not v:raise ValueError(m)

def rejected(call):
    try:call()
    except (ValueError,PermissionError):return True
    return False

def review(output):
    need(output.drive.upper()=='G:' and not output.exists(),'Fresh G-only review output required')
    source=bind(TARGET);need(source['sha256']==TARGET_SHA,'Reviewed frozen builder differs')
    spec=importlib.util.spec_from_file_location('s6d_native176_scoring_independent_target',TARGET)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    checks={};calls=[]
    class Missing(Exception):pass
    def process(pid):
        calls.append(pid);return SimpleNamespace(create_time=lambda:20.)
    provider=SimpleNamespace(Process=process,NoSuchProcess=Missing)
    mixed=[dict(role='historical_old',pid=100,creation_time=10.),dict(role='current_same_pid',pid=100,creation_time=20.)]
    checks['one_reused_PID_does_not_hide_later_live_instance']=rejected(lambda:m.prove_absent(mixed,provider)) and calls==[100,100]
    calls.clear();same=[dict(role='one',pid=100,creation_time=10.),dict(role='two',pid=100,creation_time=10.)]
    proof=m.prove_absent(same,provider)
    checks['exact_instance_dedup_preserves_both_roles']=calls==[100] and len(proof['rows'])==2 and proof['unique_instances']==1 and all(r['status']=='ORIGINAL_INSTANCE_ABSENT_PID_REUSED' for r in proof['rows'])
    cache=m.Cache();data=m.static_inputs(cache)
    prospective,queue=data['prospective'],data['queue'];scoring=[r['job_id'] for r in prospective['rows']];execution=[j['job_id'] for j in queue['jobs']]
    joined=m.matched_queue_rows(prospective['rows'],queue['jobs'])
    checks['actual_frozen176_distinct_orders_join_exactly']=len(scoring)==len(set(scoring))==176 and scoring!=execution and set(scoring)==set(execution) and all(r['job_id']==j['job_id'] for r,j in joined)
    _,e,_=m.pure_apis(cache,prospective)
    events=[dict(event_type='source_started',payload=dict(expected_samples=16,pipeline_sample_rate=16000)),
        dict(event_type='research_asr_tail_dispatch',payload=dict(source_start_sec=0.,source_end_sec=.001,samples=16)),
        dict(event_type='research_asr_drain',payload=dict(source_end_sec=.001,padding_is_observed_audio=False,synthetic_right_padding_sec=.66)),
        *[dict(event_type='research_scheduler_watermark',payload=dict(lane_closed=True,lane=lane)) for lane in ('asr','speaker')],
        dict(event_type='session_completed',payload={})]
    prefix=''.join(json.dumps(v)+'\n' for v in events)
    output.mkdir(parents=True)
    for name,suffix in [('malformed_trailing_row','{broken}\n'),('partial_trailing_row','{"event_type":"late"}')]:
        p=output/(name+'.jsonl');p.write_text(prefix+suffix,encoding='utf-8')
        c=m.Cache();checks[name+'_after_complete_rejected']=rejected(lambda:c.dispatch(p,16,e['validate_dispatch'])) and str(p.resolve()) not in c.entries
    cache.unchanged();need(bind(TARGET)==source,'Target changed during review')
    result=dict(status='PASS_NARROW_SOURCE_PROBES_NOT_CLOSED_INPUT_ADMISSION' if all(checks.values()) else 'CHANGES_REQUESTED',
        source=source,review_helper=bind(__file__),readme=bind(Path(__file__).with_name('README_S6D_NATIVE176_SCORING_INPUTS_REVIEW_V1.md')),
        checks=checks,passed=sum(checks.values()),total=len(checks),static_prospective=data['prospective_ref'],static_queue=data['queue_ref'],
        static_unique_bound_files=len(cache.entries),scoring_order_sha256=hashlib.sha256(json.dumps(scoring,separators=(',',':')).encode()).hexdigest(),
        execution_order_sha256=hashlib.sha256(json.dumps(execution,separators=(',',':')).encode()).hexdigest(),
        actual_live_state_read=False,actual_process_provider_called=False,actual_closed_results_read=False,
        actual_build_or_prepare_called=False,actual_scoring=False,actual_models=0,actual_hardware=0,actual_approvals_created=0,
        scope='Read-only static126-file graph and five targeted probes. No author24 rerun and no all176 output audit; full closure/input validation remains future root-admitted work.')
    with (output/'RECEIPT.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(dict(status=result['status'],passed=result['passed'],total=result['total'],receipt=bind(output/'RECEIPT.json'))))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();review(a.output)
