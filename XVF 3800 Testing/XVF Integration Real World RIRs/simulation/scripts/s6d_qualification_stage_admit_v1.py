"""Materialize one already reviewed qualification stage; see matching README."""
import argparse,copy,datetime,hashlib,json,shutil
from pathlib import Path
SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p,sha=None):
    p=Path(p).resolve();b=p.read_bytes();v=dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    if sha and v['sha256']!=sha:raise ValueError('Changed binding: '+str(p))
    return v
def verify(v):
    actual=bind(v['path'],v['sha256'])
    if actual['bytes']!=v['bytes']:raise ValueError('Changed size')
    return actual
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',type=int,choices=range(1,6),required=True)
    ap.add_argument('--admission-version',type=int,default=1)
    ap.add_argument('--runner-review',type=Path,required=True)
    ap.add_argument('--predecessor-review',type=Path,required=True)
    a=ap.parse_args()
    if a.admission_version<1:raise ValueError('Positive admission version')
    out=R/f'runner/qualification_stage_{a.stage}_queue_v{a.admission_version}'
    if out.exists():raise ValueError('Preserve existing admission and artifacts')
    rr=read(a.runner_review)
    if rr.get('status')!='ROOT_ACCEPTED_CENSUS_RUNNER_V4':raise ValueError('Root reviewed runner required')
    runner=verify(rr['runner']);pred=read(a.predecessor_review)
    if a.stage==1:
        bind(a.predecessor_review,'a70e8ac90418b168c9025ffce5d524213a486612988944f9c2a65d842daea87b')
        if pred['status']!='ACCEPTED_FIRST_QA_AND_RESTORATION_ONLY':raise ValueError('First QA review required')
    elif pred.get('status')!='ROOT_ACCEPTED_QUALIFICATION_STAGE' or pred.get('admitted_next_stage_index')!=a.stage:
        raise ValueError('Actual predecessor evidence must be reviewed before this stage')
    ack=read(R/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json')
    if ack.get('own_analog_outputs_disconnected_confirmed') is not True:raise ValueError('Recorded output confirmation required')
    freeze=read(R/'physical_preparation_review_v2/SOURCE_FREEZE.json')
    bind(R/'physical_preparation_review_v2/SOURCE_FREEZE.json','4b7f52df102917f09e18340b14cf8c78442fdb000d2498ae65df4a630d48e3c6')
    source_review=bind(R/'physical_preparation_review_v2/ROOT_PHYSICAL_SOURCE_REVIEW_V4.json','fc771cee141aea736ce3d2315303f2131471d6ab70a0153fbc740de49c72a176')
    old=read(R/'capture_implementation/review_v3/SOURCE_FREEZE.json')
    sources=list({v['path']:verify(v) for v in old['sources']+freeze['additive_sources']}.values())
    if len({Path(v['path']).name.casefold() for v in sources})!=len(sources):raise ValueError('Source snapshot basenames must be unique')
    proposed=read(R/'physical_preparation_review_v2/CAPTURE_PLAN_PROPOSAL.json')
    stage=copy.deepcopy(read(R/'physical_preparation_review_v2/SUPERVISOR_QUEUE_PROPOSAL.json')['proposed_stages'][a.stage])
    attempts=[x for x in proposed['attempts'] if x['attempt_id'] in stage['attempt_ids']]
    if [x['attempt_id'] for x in attempts]!=stage['attempt_ids']:raise ValueError('Exact declared attempt ordering required')
    for x in attempts:verify(x['source_audio'])
    for k in ('baseline','output_level_policy','initialization_policy','audio_acceptance_policy'):verify(proposed[k])
    ledger=read(R/'physical_ledger.json');prior_ids={x['attempt_id'] for x in ledger['passes']}
    if prior_ids.intersection(stage['attempt_ids']):raise ValueError('Never repeat a charged attempt ID')
    charged=sum(x['charged_playback_s'] for x in ledger['passes'])+stage['charged_playback_seconds']
    if len(ledger['passes'])+len(attempts)>480 or charged>21600:raise ValueError('Global physical budget exceeded')
    inherited=read(R/'runner/width_queue_v1/QUEUE.json')
    if any(shutil.disk_usage(x['path']).free<x['minimum_free_bytes'] for x in inherited['disk_policy']):raise ValueError('Storage floor')
    deadline=datetime.datetime.fromisoformat(inherited['campaign']['deadline_utc']).timestamp()-inherited['campaign']['closeout_reserve_s']
    if datetime.datetime.now().timestamp()+stage['timeout_s']+stage['stop_grace_s']>deadline:raise ValueError('Campaign deadline')
    out.mkdir()
    safety=dict(schema='s6d-xvf-own-output-safety.v1',xvf_own_analog_outputs_off_or_disconnected=True,user_confirmation_text=ack['user_reply'],original_confirmation=bind(R/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json'))
    save(out/'XVF_ANALOG_SAFETY.json',safety)
    plan=copy.deepcopy(proposed);plan.update(schema='s6d-capture-plan.v1',status='ROOT_ADMITTED_ONE_QUALIFICATION_STAGE',attempts=attempts,
        qualification_batches=[dict(batch_id=stage['fresh_owner_batch'],attempt_ids=stage['attempt_ids'])],
        safety=bind(out/'XVF_ANALOG_SAFETY.json'),owner_V4_source_review=source_review,no_execution_authorization_created=False,
        prerequisites=['Actual preceding stage and restoration reviewed; root must review this stage before advancing'])
    save(out/'CAPTURE_PLAN.json',plan);pb=bind(out/'CAPTURE_PLAN.json')
    authority=dict(schema='s6d-root-qualification-stage-admission.v1',root_review_passed=True,plan_sha256=pb['sha256'],source_bindings=sources,
        stage_index=a.stage,attempt_ids=stage['attempt_ids'],charged_playback_seconds=stage['charged_playback_seconds'],
        prospective_global_attempt_count=len(ledger['passes'])+len(attempts),prospective_global_charged_seconds=charged,
        predecessor_review=bind(a.predecessor_review),runner_review=bind(a.runner_review),source_review=source_review,
        safety=plan['safety'],ledger_before_admission=bind(R/'physical_ledger.json'),root_owner_thread_id=inherited['owner_thread_id'],
        scope='One literal qualification stage; no main bank admission; no heavy model inference during observer contrast',
        admitted_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(out/'CAPTURE_AUTHORIZATION.json',authority);ab=bind(out/'CAPTURE_AUTHORIZATION.json')
    argv=stage['argv_ready_prefix']+['--plan',pb['path'],'--plan-sha256',pb['sha256'],'--authorization',ab['path'],'--authorization-sha256',ab['sha256']]+stage['argv_ready_suffix']
    job={k:stage[k] for k in ('job_id','kind','workload','allow_owned_termination','cwd','heartbeat_path','completion_path','stop_request_path','restoration_path','timeout_s','stall_after_s','heartbeat_stale_s','stop_grace_s','expected_artifacts')}
    # Audio hashes stay in the plan and are verified by the owner. Periodic
    # small-source checks must not rehash long WAVs or exceed16MiB per file.
    bindings=sources+[runner,pb,ab,plan['safety']]
    job.update(argv=argv,environment={'PYTHONDONTWRITEBYTECODE':'1'},source_bindings=list({b['path']:b for b in bindings}.values()))
    fields=job['expected_artifacts'][0]['expected_fields']
    fields.update(failure=None,protocol_observer_errors=[],shared_stop_event_hook=True,physical_qualification_complete=False)
    fields.update({'plan.sha256':pb['sha256'],'authorization.sha256':ab['sha256'],'owner.sha256':plan['owner']['sha256'],'wrapper.sha256':plan['supervisor_bridge']['sha256']})
    if 'progress_count' in fields or fields['semantic_checks.attempt_count']!=len(attempts):raise ValueError('Only semantic attempt count is a capture count')
    queue={k:inherited[k] for k in ('schema','run_id','owner_thread_id','owner_session_id','campaign','disk_policy','payload_policy','fixture_only')}
    queue.update(jobs=[job],runner_sha256=runner['sha256']);save(out/'QUEUE.json',queue);qb=bind(out/'QUEUE.json')
    approval=dict(schema='s6d_queue_approval_v1',run_id=queue['run_id'],queue_sha256=qb['sha256'],authorization_ref=ab['path'],
        approved_job_sha256=[hashlib.sha256(json.dumps(job,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()],
        executable_bindings=[bind(argv[0])],allowed_working_directories=[str(SIM)],allowed_output_roots=queue['payload_policy']['new_payload_roots'],approval_state='ROOT_ACCEPTED_QUALIFICATION_HARDWARE_NEVER_TERMINATE')
    save(out/'APPROVAL.json',approval)
    receipt=dict(status='ONE_QUALIFICATION_STAGE_ADMITTED_PENDING_VALIDATE_ONLY_AND_LAUNCH',queue=qb,approval=bind(out/'APPROVAL.json'),plan=pb,authorization=ab,runner=runner,helper=bind(__file__),attempts=len(attempts),charged_playback_seconds=stage['charged_playback_seconds'],playback_started=False)
    save(out/'ROOT_QUEUE_REVIEW.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
