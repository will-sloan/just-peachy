"""Admit reviewed aggregate-only recovery after actual topology proof; see README."""
import copy,datetime,hashlib,json,shutil
from pathlib import Path
SIM=Path(__file__).resolve().parents[1];R=SIM/'reports/S6D/20260913T195357Z'
P=R/'runner/width_score_recovery_preparation_v2';OUT=R/'runner/width_score_recovery_queue_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p):
    p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(b):
    v=bind(b['path'])
    if (v['bytes'],v['sha256'])!=(b['bytes'],b['sha256']):raise ValueError('Changed binding '+b['path'])
    return v
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main():
    if OUT.exists():raise ValueError('Preserve existing queue')
    plan=read(P/'RECOVERY_PLAN.json');auth=read(P/'ROOT_ADMISSION_TEMPLATE.json')
    if bind(P/'RECOVERY_PLAN.json')['sha256']!='a7cb5cc3cc43d8537c512e459f8d5c6778b82ca981d02e91ee909061ed43de1e':raise ValueError('Exact reviewed plan')
    if verify(auth['helper'])['sha256']!='30d2558fcf8396e315291a8ad934bd1f4f3195a8cd92f0cd88812151b5174e5a':raise ValueError('Exact reviewed finite source')
    checks=Path('G:/Just_Peachy_S6D/20260913T195357Z/review_fixtures/root_recovery_v2/RECEIPT.json')
    if read(checks)['status']!='PASS' or read(checks)['tests']!=7:raise ValueError('Root repeated independent review checks')
    probe=R/'runner/width_recovery_topology_probe_v1/queue_v1'
    result=read(probe/'PROBE_RESULT.json')
    if result['status']!='PASS_EXACT_PROCESS_TOPOLOGY' or not result['environment_versions_match'] or not result['separate_worker'] or result['recovery_helper']!=auth['helper']:raise ValueError('Actual topology required')
    closures=list((probe/'state').glob('SUPERVISOR_CLOSURE_*.json'))
    if len(closures)!=1:raise ValueError('Actual topology supervisor closure')
    closure=read(closures[0])
    if closure['result']['action']!='FINISH' or closure['owner_lock']!='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' or not closure['keep_awake']['restored'] or not closure['payload_census_closure']['closed']:raise ValueError('Topology ownership not closed')
    for b in plan['source_bindings']+[plan['reuse_validation'],plan['runner'],plan['runner_acceptance']]:verify(b)
    if any(shutil.disk_usage(x['path']).free<x['minimum_free_bytes'] for x in plan['disk_policy']):raise ValueError('Storage floor')
    OUT.mkdir();auth.update(status='ADMITTED_AGGREGATE_ONLY_RECOVERY',root_review_passed=True,old_attempt_reusable=True,
        actual_topology=bind(probe/'PROBE_RESULT.json'),actual_topology_closure=bind(closures[0]),root_source_checks=bind(checks),
        interpretation='Reuse all3840 committed scores and1920 exact controls; zero new score calls; old failed attempt remains adverse',
        admitted_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(OUT/'ROOT_RECOVERY_ADMISSION.json',auth);ab=bind(OUT/'ROOT_RECOVERY_ADMISSION.json')
    old=read(plan['original_queue']['path']);job=copy.deepcopy(old['jobs'][0]);job.update(job_id=plan['job_id'],argv=auth['argv'])
    protocol=OUT/'protocol'/plan['job_id']
    for key,name in [('heartbeat_path','HEARTBEAT.json'),('completion_path','COMPLETION.json'),('stop_request_path','STOP_REQUEST.json')]:job[key]=str(protocol/name)
    all_bindings=plan['source_bindings']+[plan['runner'],auth['recovery_plan'],auth['helper'],plan['reuse_validation'],ab]+plan['prediction_indices']
    job['source_bindings']=list({x['path']:x for x in all_bindings}.values())
    for key in ('timeout_s','stall_after_s','heartbeat_stale_s','stop_grace_s'):job[key]=plan['proposed_runtime_limits'][key]
    completion=dict(status='COMPLETE',failure=None,protocol_observer_closed=True,protocol_errors=[],stop_requested=False,
        scoring_complete=True,reused_new_score_cells=3840,new_score_calls=0,model_calls=0,hardware_calls=0,
        **{'semantic_checks.committed_new_scores':3840,'semantic_checks.exact_coverage_cells':5760,'semantic_checks.exact_scene_cells':5760,'semantic_checks.bound_aggregate_artifacts':15,
           'recovery_plan.sha256':auth['recovery_plan']['sha256'],'admission.sha256':ab['sha256']})
    receipt=copy.deepcopy(old['jobs'][0]['expected_artifacts'][1]);receipt['path']=str(Path(plan['new_analysis_report_root'])/'SCORING_RECEIPT.json')
    receipt['expected_fields'].update(reused_new_score_cells=3840,new_score_calls_this_recovery=0)
    job['expected_artifacts']=[dict(path=job['completion_path'],format='json',min_bytes=1,expected_fields=completion),receipt]
    job['scientific_scope']='Aggregate-only recovery from unchanged exact3840 scores plus1920 controls; no neural/hardware/new score execution or retention claim'
    queue={k:old[k] for k in ('schema','run_id','owner_thread_id','owner_session_id','fixture_only')}
    queue.update(campaign=plan['campaign'],disk_policy=plan['disk_policy'],payload_policy=plan['payload_policy'],runner_sha256=plan['runner']['sha256'],jobs=[job])
    save(OUT/'QUEUE.json',queue);qb=bind(OUT/'QUEUE.json')
    approval=read(R/'runner/width_score_queue_v1/APPROVAL.json')
    approval.update(queue_sha256=qb['sha256'],authorization_ref=ab['path'],approved_job_sha256=[hashlib.sha256(json.dumps(job,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()],approval_state='ROOT_ACCEPTED_AGGREGATE_ONLY_RECOVERY')
    save(OUT/'APPROVAL.json',approval)
    report=dict(status='ROOT_ADMITTED_AGGREGATE_RECOVERY_PENDING_VALIDATE_ONLY_AND_LAUNCH',queue=qb,approval=bind(OUT/'APPROVAL.json'),runner=plan['runner'],authorization=ab,helper=bind(__file__),actual_topology=auth['actual_topology'],old_scores_recomputed=False)
    save(OUT/'ROOT_QUEUE_REVIEW.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
