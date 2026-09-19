"""Prepare then admit the exact B4 remainder; README_S6D_BANK_REMAINING_ADMIT_V7.md."""
import argparse
import copy
import datetime as dt
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import s6d_bank_admit_v1 as A

SIM=A.SIM;R=A.R;G=A.G;OUT=R/'runner/bank_queue_v7'
PROPOSAL=R/'runner/bank_b4_qa_scope_proposal_v1/FINAL_RECAPTURE_REMAINDER_PROPOSAL.json'
PROPOSAL_SHA='acffe3474cf00049a83183a73c10fb1ca52a6a85012dd53e9231109c0c2628d9'
DIAGNOSIS=R/'runner/bank_b4_timeout_proposal_v1/DIAGNOSIS.json'
DIAGNOSIS_SHA='9b092941cb4fff05eb74490cbab14734ff5fc886e9c6a68b299fea043a9e50f4'
OLD=R/'runner/bank_queue_v6'
OLD_REVIEW_SHA='54f991e5cb1918adf0e465b218073f8d5b9dee629ffdbc238c46b35c212c6f98'
RUNNER_SHA='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4'
OWNER_SHA='22c3480d354ebe3620bd6ffe0dfd27e7e4cfc38a1e073b583ce39431c6f5286b'
BRIDGE_SHA='e09ed591f2e08f2e705190aa4b9617c042e90382c4c42010317d958731338015'
CLOSURE_STATUS='ROOT_ACCEPTED_INTERRUPTED_BANK_V6_CLOSURE_WITH_PROVISIONAL_B4'
ROOT_STATUS='ROOT_ACCEPTED_EXACT_BANK_V7_REMAINDER_FOR_ADMISSION'
ROOT_CLOSURE_SHA='7715b01db5d12634ea9ccd5b5a7cdf439a4e800e3fc8ab3c069dad8cae5ad06b'
BASE_ADMIT_SHA='8016e915c47ea4f0ad49407053a99b804069e11cec826d8866df658af9fec08d'
CLOSED_IDS=['bank_v5_P_MAIN6_B3_pre_QA','bank_v5_P_MAIN6_B3','bank_v5_P_MAIN6_B3_post_QA','bank_v5_P_MAIN6_B4_pre_QA']
PARTIAL={f'P_MAIN6_S45_05_{n:02d}' for n in range(11,19)}
SCOPE_SUPPLEMENT_SHA='fba2065070351a2f70723f4558ae37c3bd843116e665de56cef8c1e04f85496e'

def need(ok,message):A.require(ok,message)
def encoded(doc):return (json.dumps(doc,indent=2,allow_nan=False)+'\n').encode()
def save(path,doc):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(encoded(doc))
def virtual(path,doc):
    raw=encoded(doc);return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def verify(ref):return A.read(A.verify(ref)['path'])
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def map_path(path,mapping):return str(Path(*(mapping.get(x,x) for x in Path(path).parts)))
def source_ref():return A.bind(__file__)
def readme_ref():return A.bind(Path(__file__).with_name('README_S6D_BANK_REMAINING_ADMIT_V7.md'))

def walk_bindings(value):
    if isinstance(value,dict):
        if set(('path','bytes','sha256'))<=set(value):
            A.verify({k:value[k] for k in ('path','bytes','sha256')})
        else:
            for item in value.values():walk_bindings(item)
    elif isinstance(value,list):
        for item in value:walk_bindings(item)

def closure_shape(root,cp,cl,lock):
    need(root.get('status')==CLOSURE_STATUS and root.get('owner_thread_id')==A.THREAD and root.get('run_id')=='20260913T195357Z','Exact root interruption acceptance required')
    need(root.get('all_owners_closed') is True and root.get('whole_original_queue_complete') is False and root.get('provisional_cases')==8,'No whole V6 completion or retrospective partial credit')
    need(cp.get('status')=='REVIEW_FAILURE' and set(cp.get('completed',{}))==set(CLOSED_IDS) and cp.get('active',{}).get('job_id')=='bank_v5_P_MAIN6_B4','Exact interrupted4-stage checkpoint required')
    need(cl.get('result',{}).get('action')=='REVIEW_FAILURE' and cl['result'].get('done')==4 and cl['result'].get('total')==54 and cl['result'].get('job_id')=='bank_v5_P_MAIN6_B4','Exact failed supervisor result required')
    need(cl.get('hardware_restoration_unresolved') is False and cl.get('owner_lock')=='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT','Actual final hardware closure required')
    need(cl.get('keep_awake',{}).get('restored') is True and cl.get('payload_census_closure',{}).get('closed') is True and cl['payload_census_closure']['snapshot'].get('running') is False and cl['payload_census_closure']['snapshot'].get('error') is None and cl['payload_census_closure']['snapshot'].get('violation_latched') is False,'Closed keep-awake/census required')
    need(len(root.get('completed_stages',[]))==4 and {x['job_id'] for x in root['completed_stages']}==set(CLOSED_IDS),'Exact four retained stage reviews required')
    rows=root.get('closed_instances',[]);pairs=[]
    import math
    for row in rows:
        need(type(row.get('pid')) is int and row['pid']>0 and type(row.get('creation_time')) in (int,float) and math.isfinite(row['creation_time']) and row['creation_time']>0,'Finite closed process identity required')
        pairs.append((row['pid'],row['creation_time']))
    required=[cp['completed'][j]['identity'] for j in CLOSED_IDS]+[cp['active'],lock]
    required_pairs={(x['pid'],x['creation_time']) for x in required}
    need(len(pairs)==len(set(pairs)) and len(required_pairs)==6 and required_pairs<=set(pairs),'Four completed children, failed child and final supervisor must be closed')
    # V4 closed locks retain the historical launch intent; final closure is authoritative.
    intent=lock.get('unresolved_hardware',{})
    need(intent.get('job_id')==cp['active']['job_id'] and intent.get('child_run_id')==cp['active']['child_run_id'] and intent.get('run_id')==cp['active']['run_id'] and intent.get('launch_state')=='INTENT_PERSISTED','Retained immutable launch intent must match failed child')
    return rows

def context(closure_ref):
    need(A.bind(A.__file__)['sha256']==BASE_ADMIT_SHA,'Reviewed base metadata helper changed')
    need(closure_ref['sha256']==ROOT_CLOSURE_SHA and Path(closure_ref['path'])==R/'runner/bank_b4_root_closure_v1/ROOT_INTERRUPTED_EPOCH_ACCEPTANCE.json','Exact accepted root interrupted epoch required')
    need(A.bind(PROPOSAL)['sha256']==PROPOSAL_SHA and A.bind(DIAGNOSIS)['sha256']==DIAGNOSIS_SHA,'Exact reviewed remainder diagnosis required')
    proposal=A.read(PROPOSAL);diagnosis=A.read(DIAGNOSIS)
    need(proposal['status']=='PROPOSED_FINAL_26_RECAPTURE_SCOPE_NOT_ADMITTED' and proposal['scope_supplement']['sha256']==SCOPE_SUPPLEMENT_SHA,'Final26-recapture scope required')
    for key in ('original290_proposal','eight_only_proposal','scope_supplement','original18_source_plan'):A.verify(proposal[key])
    for ref in diagnosis['input_bindings']:A.verify(ref)
    oldref=A.bind(OLD/'ROOT_QUEUE_REVIEW.json');need(oldref['sha256']==OLD_REVIEW_SHA,'Exact original V6 admission required');old=verify(oldref)
    queue=verify(old['queue']);ledger_ref=A.bind(R/'physical_ledger.json');ledger=A.read(ledger_ref['path'])
    need(ledger_ref==next(x for x in diagnosis['input_bindings'] if Path(x['path'])==R/'physical_ledger.json'),'Exact145-row saved ledger required')
    need(len(ledger['passes'])==145 and sum(x['status']=='PASS' for x in ledger['passes'])==141 and sum(x['status']=='FAIL' for x in ledger['passes'])==4,'All145 charges/four failures retained')
    root=verify(closure_ref)
    need(root['queue']==old['queue'] and root['checkpoint']==proposal['preserve_original_checkpoint'],'Root must join exact old queue/checkpoint')
    cp=verify(root['checkpoint']);cl=verify(root['supervisor_closure']);lock=verify(root['closed_lock'])
    need(root['supervisor_closure']==diagnosis['supervisor']['closure'] and root['closed_lock']==diagnosis['supervisor']['immutable_lock'],'Exact final supervisor/lock required')
    closure_shape(root,cp,cl,lock)
    need(root['failure']==next(x for x in diagnosis['input_bindings'] if Path(x['path'])==R/'physical_supervisor/bank_v5_P_MAIN6_B4/CAPTURE_BRIDGE_FAILURE.json') and root['restoration']==next(x for x in diagnosis['input_bindings'] if Path(x['path'])==R/'physical_supervisor/bank_v5_P_MAIN6_B4/RESTORATION.json'),'Root failure/restoration joins differ')
    need(verify(root['restoration'])['verified'] is True,'Saved actual restoration required');verify(root['failure'])
    walk_bindings(root['completed_stages']);walk_bindings(root['current_process_snapshot']);walk_bindings(root['allocation_decision'])
    partial=[]
    for entry in root['retained_partial_cases']:
        case=verify(entry['case_result']);meta=verify(entry['capture_metadata'])
        ident=case['attempt']['attempt_id'];need(ident in PARTIAL and case['status']=='PASS' and case['metadata']==entry['capture_metadata'],'Exact provisional case/metadata joins required')
        need(entry['case_result']==next(x['result'] for x in diagnosis['completed_provisional_cases'] if x['attempt_id']==ident),'Different retained partial case')
        partial.append(ident)
    need(len(partial)==8 and set(partial)==PARTIAL,'Exact eight provisional cases required')
    for key,sha in [('runner',RUNNER_SHA),('owner',OWNER_SHA),('bridge',BRIDGE_SHA)]:need(A.verify(old[key])['sha256']==sha,'Unchanged runner/owner/bridge required')
    execution=old['owner_execution_dependencies'];need(len(execution)==28 and len({Path(x['path']).name.casefold() for x in execution})==28,'Original28 canonical execution dependencies required')
    for ref in execution:A.verify(ref)
    need(queue['payload_policy']['max_new_payload_bytes']==40*2**30,'Physical shared40GiB unchanged')
    return dict(proposal=proposal,diagnosis=diagnosis,old=old,oldref=oldref,queue=queue,ledger=ledger,ledger_ref=ledger_ref,closure=root,closure_ref=closure_ref,cp=cp,execution=execution)

def build(c):
    old=c['old'];queue=copy.deepcopy(c['queue']);artifacts=[];replacements={};groups=[];future=[]
    def add(path,doc):
        ref=virtual(path,doc);artifacts.append(dict(binding=ref,document=doc));return ref
    inherited=None
    for group in c['proposal']['groups']:
        plan=verify(group['original_plan']);auth=verify(group['original_authorization'])
        if inherited is None:inherited=auth['reviewed_recoveries']
        need(auth['reviewed_recoveries']==inherited and auth['source_bindings']==c['execution'],'Original execution/recovery graph differs')
        rows=copy.deepcopy(group['attempts']);plan['attempts']=rows
        plan.update(admission_helper=source_ref(),admission_readme=readme_ref(),original_epoch_closure=c['closure_ref'],remainder_metadata_proposal=A.bind(PROPOSAL),declared_group_id=group['group_id'])
        if group['group_id'] in ('P_MAIN6_B4','P_MAIN6_B3_RECAP18'):plan.update(previous_partial_case_root_review=c['closure_ref'],previous_partial_cases_remain_provisional=True,recaptures_required_with_own_QA=True)
        directory=OUT/'groups'/group['group_id'];pb=add(directory/'CAPTURE_PLAN.json',plan)
        auth.update(plan_sha256=pb['sha256'],root_review_passed=True,attempt_ids=[x['attempt_id'] for x in rows],ledger_before_admission=c['ledger_ref'],charged_playback_seconds=float(A.charge(rows)),admission_helper=source_ref(),admission_readme=readme_ref(),original_epoch_closure=c['closure_ref'],scope='V7 exact remainder: retain145 charges/four failures;26 old partial records stay historical; fresh18-case B3 QA chain and full30-case B4 QA chain. No retrospective QA, duplicated unique-scene credits, source, timing, gain, guard, profile, timeout or control changes.')
        ab=add(directory/'CAPTURE_AUTHORIZATION.json',auth);replacements[group['original_plan']['path']]=pb;replacements[group['original_authorization']['path']]=ab
        groups.append(dict(group_id=group['group_id'],plan=pb,authorization=ab,attempts=len(rows)));future.extend(rows)
    for ref in inherited:A.verify(ref)
    need(len(future)==len({x['attempt_id'] for x in future})==318 and not({x['attempt_id'] for x in future}&{x['attempt_id'] for x in c['ledger']['passes']}),'Exact318 fresh IDs required')
    total=sum((Fraction(str(x['charged_playback_s'])) for x in c['ledger']['passes']),Fraction())+A.charge(future)
    need(total==Fraction('21187.3213125') and len(c['ledger']['passes'])+len(future)==463,'Exact463/21187.3213125 forecast required')
    previous=None;jobs=[];original_jobs={job['job_id']:job for job in queue['jobs']};rows_by_id={x['attempt_id']:x for x in future};renames=c['proposal']['renames'];reverse={v:k for k,v in renames.items()}
    for stage in c['proposal']['stages']:
        job=copy.deepcopy(original_jobs[stage['original_job_id']]);oldid=job['job_id']
        job['job_id']=stage['proposed_job_id'];job['bank_group_id']=stage['group'];job['predecessor_job_id']=previous;previous=job['job_id']
        need(stage['proposed_predecessor']==job['predecessor_job_id'],'Exact proposed predecessor chain required')
        argv=job['argv'];idx=argv.index('--attempt-ids')+1;ids=stage['attempt_ids'];argv[idx:]=ids
        for option in ('--plan','--authorization'):
            ref=replacements[argv[argv.index(option)+1]];argv[argv.index(option)+1]=ref['path'];argv[argv.index(option+'-sha256')+1]=ref['sha256']
        argv[argv.index('--batch')+1]=job['job_id'];mapping={**renames,oldid:job['job_id']}
        for key in ('heartbeat_path','completion_path','stop_request_path','restoration_path'):job[key]=map_path(job[key],mapping)
        # Keep exact protocol predicates and derive each case's exact existing
        # two-artifact predicate pair. The18 recaptures use the same45s MAIN
        # template with only case/attempt/source identity fields rebound.
        originals=job['expected_artifacts'];kept=[]
        for artifact in originals:
            if Path(artifact['path']).name not in ('COMPLETE.json','RESTORATION.json'):continue
            artifact=copy.deepcopy(artifact);artifact['path']=map_path(artifact['path'],mapping);fields=artifact['expected_fields']
            if 'plan.sha256' in fields:fields.update({'plan.sha256':argv[argv.index('--plan-sha256')+1],'authorization.sha256':argv[argv.index('--authorization-sha256')+1],'semantic_checks.attempt_count':len(ids)})
            kept.append(artifact)
        need(len(kept)==2,'Exact original completion/restoration pair required')
        for ident in ids:
            row=rows_by_id[ident];oldident=reverse.get(ident,ident)
            cases=[x for x in originals if x.get('expected_fields',{}).get('attempt.attempt_id')==oldident]
            if not cases:
                need(stage['group']=='P_MAIN6_B3_RECAP18' and stage['stage']=='body' and row['duration_sec']==45,'Only declared18 recapture rows may use shared45s template')
                cases=[x for x in originals if x.get('expected_fields',{}).get('attempt.profile')=='P_MAIN6'][:1]
            need(len(cases)==1,'Exact case predicate template required');case=copy.deepcopy(cases[0]);oldfolder=Path(case['path']).parent
            metas=[x for x in originals if Path(x['path'])==oldfolder/'capture_metadata.json'];need(len(metas)==1,'Exact metadata predicate template required');meta=copy.deepcopy(metas[0])
            fields=case['expected_fields'];need(fields['attempt.profile']==row['profile'] and fields['attempt.role']==row['role'] and fields['source_input.timing.source_frames']==round(row['duration_sec']*16000),'Same profile/role/duration predicate template required')
            folder=Path(next(x['document']['payload_root'] for x in artifacts if x['binding']['path']==argv[argv.index('--plan')+1]))/'beam_bank'/row['case_id']/row['profile']/ident
            case['path']=str(folder/'case_result.json');meta['path']=str(folder/'capture_metadata.json')
            fields.update({'attempt.attempt_id':ident,'attempt.case_id':row['case_id'],'attempt.source_audio.sha256':row['source_audio']['sha256'],'source_input.source.sha256':row['source_audio']['sha256']})
            kept.extend([case,meta])
        job['expected_artifacts']=kept
        sources=[replacements.get(x['path'],x) for x in job['source_bindings']]+[source_ref(),readme_ref(),A.bind(PROPOSAL),A.bind(DIAGNOSIS),c['closure_ref'],c['oldref']]
        job['source_bindings']=list({x['path']:x for x in sources}.values());jobs.append(job)
    queue['jobs']=jobs
    need(len(groups)==18 and len(jobs)==54 and [len(x['argv'][x['argv'].index('--attempt-ids')+1:]) for x in jobs[:6]]==[1,18,1,1,30,1],'Exact18groups/54stages/B3/B4 order required')
    need([x for j in jobs for x in j['argv'][j['argv'].index('--attempt-ids')+1:]]==[x['attempt_id'] for x in future],'Group/stage attempt order differs')
    qb=add(OUT/'QUEUE.json',queue);approval=verify(old['approval']);runner=load(old['runner']['path'],'v7_frozen_queue_validator')
    approval.update(queue_sha256=qb['sha256'],approved_job_sha256=[runner.digest(j) for j in jobs],authorization_ref=str(OUT/'ROOT_QUEUE_REVIEW.json'))
    # The frozen validator also stats actual plan files. Preparation deliberately
    # leaves them virtual; the unmodified validator runs after materialization,
    # before check-plan/root admission/final APPROVAL during explicit --admit.
    virtual_refs={item['binding']['path']:item['binding'] for item in artifacts}
    guards={ref['path']:ref for job in jobs for ref in job['source_bindings']}
    for ref in guards.values():
        if ref['path'] in virtual_refs:need(ref==virtual_refs[ref['path']],'Virtual source binding differs')
        else:A.verify(ref)
    for job in jobs:need(all(x['bytes']<=16*2**20 for x in job['source_bindings']) and sum(x['bytes'] for x in job['source_bindings'])<=64*2**20,'Original source size bounds')
    ab=virtual(OUT/'APPROVAL.json',approval)
    return dict(status='UNAPPROVED_REVIEW_BUNDLE_NOT_EXECUTABLE',source=source_ref(),readme=readme_ref(),original_epoch_closure=c['closure_ref'],original_bank_admission=c['oldref'],ledger_before_admission=c['ledger_ref'],remainder=A.bind(PROPOSAL),diagnosis=A.bind(DIAGNOSIS),artifacts=artifacts,approval_proposal=dict(binding=ab,document=approval),queue=qb,groups=groups,runner=old['runner'],owner=old['owner'],bridge=old['bridge'],qualification=old['qualification'],policy=old['policy'],source_review=old['source_review'],owner_execution_source_freeze=old['owner_execution_source_freeze'],owner_execution_dependencies=c['execution'],reviewed_recoveries=inherited,current_charged_attempts=145,new_attempts_admitted=318,total_forecast_attempts=463,total_forecast_charged_seconds=float(total),literal_runtime_validation='PENDING_ACTUAL_PATHS_BEFORE_FINAL_APPROVAL',actual_approval_created=False)

def prepare(directory,closure_ref):
    need(directory.is_relative_to(R/'runner') and not directory.exists(),'Fresh runner preparation directory required')
    c=context(closure_ref);bundle=build(c)
    need(A.bind(R/'physical_ledger.json')==c['ledger_ref'],'Ledger changed during preparation')
    directory.mkdir();save(directory/'PREPARATION.json',bundle)
    save(directory/'ROOT_REVIEW_PROPOSAL.json',dict(status='PROPOSED_NOT_ROOT_AUTHORITY',owner_thread_id=A.THREAD,run_id='20260913T195357Z',allow_admission=False,preparation=A.bind(directory/'PREPARATION.json'),source_freeze=None,original_epoch_closure=closure_ref))
    print(json.dumps(dict(status='UNAPPROVED_METADATA_ONLY',preparation=A.bind(directory/'PREPARATION.json'),actual_approval_created=False)))

def admit(preparation,root_path,root_sha):
    pref=A.bind(preparation);bundle=A.read(preparation);rr=A.bind(root_path);need(rr['sha256']==root_sha,'Exact actual root review SHA required');root=verify(rr)
    need(root.get('status')==ROOT_STATUS and root.get('owner_thread_id')==A.THREAD and root.get('run_id')=='20260913T195357Z' and root.get('allow_admission') is True and root.get('preparation')==pref and root.get('original_epoch_closure')==bundle['original_epoch_closure'],'Root exact preparation/closure acceptance required')
    freeze=verify(root['source_freeze']);need(any(x.get('sha256')==source_ref()['sha256'] and x.get('path')==source_ref()['path'] for x in freeze['files']),'Root source freeze omits exact helper')
    c=context(bundle['original_epoch_closure']);need(build(c)==bundle,'Prepared literals/source changed')
    owner=load(c['old']['owner']['path'],'v7_actual_prior_closure');need(owner.prior_closure(R,bundle['reviewed_recoveries'])==c['ledger'],'Original all-owner restoration/recovery gate required')
    need(not OUT.exists() and not(G/'runner/bank_queue_v7/supervisor_state').exists(),'Fresh V7 queue/state required')
    for item in bundle['artifacts']:need(not Path(item['binding']['path']).exists(),'Fresh artifact destinations required')
    for item in bundle['artifacts']:
        doc=item['document']
        if doc.get('schema')=='s6d-capture-plan.v1':
            for row in doc['attempts']:need(not(Path(doc['payload_root'])/'beam_bank'/row['case_id']/row['profile']/row['attempt_id']).exists(),'Fresh whole capture folder required')
    for job in next(x['document'] for x in bundle['artifacts'] if x['binding']==bundle['queue'])['jobs']:
        need(not Path(job['completion_path']).parent.exists() and not(R/'hardware_batches'/job['job_id']).exists(),'Fresh protocol/batch required')
        for artifact in job['expected_artifacts']:need(not Path(artifact['path']).exists(),'Existing capture destination cannot be reused')
    need(dt.datetime.now(dt.timezone.utc)<dt.datetime(2026,9,16,19,8,57,tzinfo=dt.timezone.utc),'Original deadline/reserve')
    need(shutil.disk_usage('C:/').free>=50*2**30 and shutil.disk_usage('G:/').free>=75*2**30,'Original C50/G75 floors')
    need(A.bind(R/'physical_ledger.json')==c['ledger_ref'],'Ledger changed before actual writes')
    for item in bundle['artifacts']:
        save(Path(item['binding']['path']),item['document']);need(A.bind(item['binding']['path'])==item['binding'],'Materialized artifact bytes differ')
    runner=load(bundle['runner']['path'],'v7_actual_materialized_validator')
    need(runner.validate_queue(A.read(bundle['queue']['path']),bundle['approval_proposal']['document'],bundle['queue']['sha256']) is True,'Unmodified actual-path V4 validation required before final APPROVAL')
    checks=[]
    for group in bundle['groups']:
        log=OUT/'validation'/(group['group_id']+'.log');log.parent.mkdir(parents=True,exist_ok=True)
        argv=[sys.executable,'-B',bundle['owner']['path'],'check-plan','--plan',group['plan']['path'],'--authorization',group['authorization']['path']]
        with log.open('x',encoding='utf-8') as f:proc=subprocess.run(argv,cwd=SIM,stdout=f,stderr=subprocess.STDOUT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        need(proc.returncode==0,'Owner check-plan failed; no final APPROVAL: '+str(log));checks.append(dict(group_id=group['group_id'],argv=argv,exit_code=0,log=A.bind(log)))
    receipt={k:bundle[k] for k in ('queue','groups','runner','owner','bridge','qualification','policy','source_review','owner_execution_source_freeze','owner_execution_dependencies','reviewed_recoveries','current_charged_attempts','new_attempts_admitted','total_forecast_attempts','total_forecast_charged_seconds','original_epoch_closure','original_bank_admission')}
    receipt.update(status='ROOT_ADMITTED_BANK_V7_REMAINDER_PENDING_LAUNCH',root_owner_thread_id=A.THREAD,run_id='20260913T195357Z',root_preparation_review=rr,source_freeze=root['source_freeze'],preparation=pref,approval=bundle['approval_proposal']['binding'],owner_plan_checks=checks,retained_partial_cases_remain_provisional=True,original_failures_preserved=True,playback_started=False)
    save(OUT/'ROOT_QUEUE_REVIEW.json',receipt)
    save(OUT/'APPROVAL.json',bundle['approval_proposal']['document']);need(A.bind(OUT/'APPROVAL.json')==bundle['approval_proposal']['binding'],'Final approval bytes differ')
    print(json.dumps(dict(status=receipt['status'],receipt=A.bind(OUT/'ROOT_QUEUE_REVIEW.json'),approval=A.bind(OUT/'APPROVAL.json'),launch_performed=False)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',type=Path);mode.add_argument('--admit',type=Path,help='Exact PREPARATION.json path');p.add_argument('--closure-review',type=Path);p.add_argument('--closure-review-sha256');p.add_argument('--root-review',type=Path);p.add_argument('--root-review-sha256');a=p.parse_args()
    if a.prepare:
        need(a.closure_review and a.closure_review_sha256,'Exact root closure path/SHA required');ref=A.bind(a.closure_review);need(ref['sha256']==a.closure_review_sha256,'Exact root closure SHA');prepare(a.prepare.resolve(),ref)
    else:
        need(a.root_review and a.root_review_sha256,'Exact root preparation review required');admit(a.admit.resolve(),a.root_review,a.root_review_sha256)
