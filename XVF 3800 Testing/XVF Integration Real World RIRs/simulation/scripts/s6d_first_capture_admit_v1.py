"""Materialize the reviewed first-QA-only hardware queue; see accompanying README."""
import copy,datetime,hashlib,json,shutil
from pathlib import Path
SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
OUT=R/'runner/first_capture_queue_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p,sha=None):
    p=Path(p).resolve();b=p.read_bytes();out=dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    if sha and out['sha256']!=sha:raise ValueError('Binding changed: '+str(p))
    return out
def verify(b):
    actual=bind(b['path'],b['sha256'])
    if actual['bytes']!=b['bytes']:raise ValueError('Size changed')
    return actual
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main():
    if OUT.exists() or (R/'physical_ledger.json').exists():raise ValueError('First capture already admitted/attempted; preserve history')
    pre=read(R/'preflight_after_reset_v1/PREFLIGHT.json')
    if pre['status']!='READ_ONLY_PREFLIGHT_COMPLETE' or pre['errors'] or not pre['expected_build'] or not pre['hardware_lock_released']:raise ValueError('Full current preflight required')
    ack=read(R/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json')
    if ack.get('own_analog_outputs_disconnected_confirmed') is not True:raise ValueError('Fresh user confirmation required')
    freeze_binding=bind(R/'physical_preparation_review_v2/SOURCE_FREEZE.json','4b7f52df102917f09e18340b14cf8c78442fdb000d2498ae65df4a630d48e3c6')
    review_binding=bind(R/'physical_preparation_review_v2/ROOT_PHYSICAL_SOURCE_REVIEW_V4.json','fc771cee141aea736ce3d2315303f2131471d6ab70a0153fbc740de49c72a176')
    freeze=read(freeze_binding['path']);old=read(R/'capture_implementation/review_v3/SOURCE_FREEZE.json')
    sources={}
    for b in old['sources']+freeze['additive_sources']:
        actual=verify(b);sources[actual['path']]=actual
    sources=list(sources.values())
    if len({Path(b['path']).name.casefold() for b in sources})!=len(sources):raise ValueError('Owner snapshots require unique filenames')
    proposed=read(R/'physical_preparation_review_v2/CAPTURE_PLAN_PROPOSAL.json')
    qp=read(R/'physical_preparation_review_v2/SUPERVISOR_QUEUE_PROPOSAL.json')
    stage=copy.deepcopy(qp['proposed_stages'][0])
    if stage['attempt_ids']!=['QA_QUAL_MAIN_PRE'] or stage['charged_playback_seconds']!=12.3413125:raise ValueError('Only exact first sentinel allowed')
    attempts=[a for a in proposed['attempts'] if a['attempt_id'] in stage['attempt_ids']]
    if len(attempts)!=1 or attempts[0]['profile']!='P_INPUT_QA6' or attempts[0]['duration_sec']!=8:raise ValueError('Wrong first capture')
    verify(attempts[0]['source_audio'])
    for k in ('baseline','output_level_policy','initialization_policy','audio_acceptance_policy'):verify(proposed[k])
    inherited=read(R/'runner/width_queue_v1/QUEUE.json')
    if any(shutil.disk_usage(row['path']).free<row['minimum_free_bytes'] for row in inherited['disk_policy']):raise ValueError('Storage floor')
    OUT.mkdir()
    safety=dict(schema='s6d-xvf-own-output-safety.v1',xvf_own_analog_outputs_off_or_disconnected=True,
        user_confirmation_text=ack['user_reply'],original_confirmation=bind(R/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json'),
        scope='XVF own analog outputs only; PC peripherals may remain connected',recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(OUT/'XVF_ANALOG_SAFETY.json',safety)
    plan=copy.deepcopy(proposed)
    plan.update(schema='s6d-capture-plan.v1',status='ROOT_ADMITTED_FIRST_QA_ONLY',attempts=attempts,
        qualification_batches=[dict(batch_id=stage['fresh_owner_batch'],attempt_ids=stage['attempt_ids'],scope='FIRST_QA_ONLY_REVIEW_BEFORE_NEXT_STAGE')],
        safety=bind(OUT/'XVF_ANALOG_SAFETY.json'),owner_V4_source_review=review_binding,no_execution_authorization_created=False,
        prerequisites=['User outputs confirmed; fresh full preflight passes; inspect actual first-QA integrity/restoration before further admission'])
    save(OUT/'CAPTURE_PLAN.json',plan);pb=bind(OUT/'CAPTURE_PLAN.json')
    authority=dict(schema='s6d-root-first-QA-admission.v1',root_review_passed=True,plan_sha256=pb['sha256'],source_bindings=sources,
        scope='Only QA_QUAL_MAIN_PRE; no controls/C/bank authority',attempt_ids=stage['attempt_ids'],charged_playback_seconds=12.3413125,
        reviewed_source=review_binding,source_freeze=freeze_binding,current_preflight=bind(R/'preflight_after_reset_v1/PREFLIGHT.json'),
        device_reset_history=bind(R/'reset_recovery_after_confirmation_v1/RESULT.json'),safety=plan['safety'],
        prior_pre_reset_DSP_restoration_claim=False,owner_restores='Exact state recorded immediately before this capture batch',
        admitted_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_owner_thread_id=inherited['owner_thread_id'])
    save(OUT/'CAPTURE_AUTHORIZATION.json',authority);ab=bind(OUT/'CAPTURE_AUTHORIZATION.json')
    argv=stage['argv_ready_prefix']+['--plan',pb['path'],'--plan-sha256',pb['sha256'],'--authorization',ab['path'],'--authorization-sha256',ab['sha256']]+stage['argv_ready_suffix']
    job={k:stage[k] for k in ('job_id','kind','workload','allow_owned_termination','cwd','heartbeat_path','completion_path','stop_request_path','restoration_path','timeout_s','stall_after_s','heartbeat_stale_s','stop_grace_s','expected_artifacts')}
    job.update(argv=argv,environment={'PYTHONDONTWRITEBYTECODE':'1'},source_bindings=sources+[pb,ab,plan['safety'],attempts[0]['source_audio']],scientific_scope='One exact tagged-input transport QA, no beam efficacy')
    fields=job['expected_artifacts'][0]['expected_fields'];fields.update(failure=None,protocol_observer_errors=[],progress_count=1,shared_stop_event_hook=True,physical_qualification_complete=False)
    fields.update({'plan.sha256':pb['sha256'],'authorization.sha256':ab['sha256'],'owner.sha256':plan['owner']['sha256'],'wrapper.sha256':plan['supervisor_bridge']['sha256']})
    queue={k:inherited[k] for k in ('schema','run_id','owner_thread_id','owner_session_id','campaign','disk_policy','payload_policy','fixture_only')}
    queue['jobs']=[job];queue['runner_sha256']=qp['reviewed_runner']['sha256']
    save(OUT/'QUEUE.json',queue);qb=bind(OUT/'QUEUE.json')
    approval=dict(schema='s6d_queue_approval_v1',run_id=queue['run_id'],queue_sha256=qb['sha256'],authorization_ref=ab['path'],
        approved_job_sha256=[hashlib.sha256(json.dumps(job,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()],
        executable_bindings=[bind(argv[0])],allowed_working_directories=[str(SIM)],allowed_output_roots=queue['payload_policy']['new_payload_roots'],
        approval_state='ROOT_ACCEPTED_FIRST_QA_ONLY_HARDWARE_NEVER_TERMINATE')
    save(OUT/'APPROVAL.json',approval)
    receipt=dict(status='FIRST_QA_ADMITTED_PENDING_VALIDATION_AND_LAUNCH',queue=qb,approval=bind(OUT/'APPROVAL.json'),plan=pb,authorization=ab,
        source=binding if False else bind(__file__),source_count=len(sources),playback_started=False,overall_S6D_complete=False)
    save(OUT/'ROOT_QUEUE_REVIEW.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
