"""Admit the remaining bank after reviewed telemetry recovery; see README."""
import argparse,copy,datetime as dt,importlib.util,json,shutil,subprocess
from fractions import Fraction
from pathlib import Path
import s6d_bank_admit_v1 as A

DONE={f'P_MAIN6_S45_04_{i:02d}' for i in range(1,19)}
SKIP_GROUPS={'P_MAIN6_B1','P_MAIN6_B2'}
RENAMES={'QA_P_MAIN6_B3_PRE':'QA_P_MAIN6_B3_PRE_R2','P_MAIN6_S45_04_19':'P_MAIN6_S45_04_19_R2'}

def path_map(value,mapping):
    return str(Path(*(mapping.get(x,x) for x in Path(value).parts)))

def snapshot_sources(existing,reviewed):
    result={}
    for b in existing+reviewed:
        name=Path(b['path']).name.casefold()
        if name in result:
            A.require((b['bytes'],b['sha256'])==(result[name]['bytes'],result[name]['sha256']),'Conflicting snapshot basename: '+name)
        else:result[name]=b
    return list(result.values())

def execution_sources_from_freeze(review,freeze_binding,expected_sha256,required_members):
    A.require(len(expected_sha256)==64 and freeze_binding['sha256']==expected_sha256 and review.get('owner_execution_source_freeze')==freeze_binding,'Root must bind the exact supplied V10 execution source freeze/hash')
    A.require(Path(freeze_binding['path']).is_relative_to(A.R/'runner'),'Execution source freeze must be inside the campaign runner root')
    execution_freeze=A.read(A.verify(freeze_binding)['path'])
    dependencies=execution_freeze['owner_execution_dependency_bindings']
    sources=snapshot_sources([], [A.verify(b) for b in dependencies])
    A.require(len(sources)==len(dependencies)==26 and all(b in sources for b in required_members),'Exact26 collision-free canonical execution dependencies including owner/bridge/policy required')
    return sources

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-review',type=Path,required=True)
    ap.add_argument('--execution-freeze',type=Path,required=True)
    ap.add_argument('--execution-freeze-sha256',required=True)
    ap.add_argument('--recovery',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=A.R/'runner/bank_queue_v5')
    args=ap.parse_args();out=args.output.resolve()
    A.require(not out.exists() and out.is_relative_to(A.R/'runner'),'Fresh bounded output required')
    sr=A.bind(args.source_review);review=A.read(args.source_review)
    A.require(review['status']=='ROOT_ACCEPTED_RECORDED_TELEMETRY_RECOVERY_V5_SOURCES_V1','Root V10 source review required')
    for b in review['source_bindings']:A.verify(b)
    owner=A.verify(review['owner']);bridge=A.verify(review['bridge']);policy=A.verify(review['policy'])
    A.require(Path(owner['path']).name=='s6d_capture_owner_v10.py' and Path(bridge['path']).name=='s6d_capture_supervisor_bridge_v2.py','Exact V10/bridgeV2 epoch')
    ef=A.bind(args.execution_freeze)
    execution_sources=execution_sources_from_freeze(review,ef,args.execution_freeze_sha256,(owner,bridge,policy))
    helper_binding=A.bind(__file__);readme_binding=A.bind(Path(__file__).with_name('README_S6D_BANK_REMAINING_ADMIT_V5.md'))
    rb=A.bind(args.recovery);recovery=A.read(args.recovery)
    A.require(recovery['schema_version']=='edge-s6d-restoration-recovery.v2' and recovery['status']=='PASS','Actual fresh restoration required')
    olddir=A.R/'runner/bank_queue_v4';oldref=A.bind(olddir/'ROOT_QUEUE_REVIEW.json')
    A.require(oldref['sha256']=='6b953127a0dc2ec6ea643e5c9eb575ad4d67982b77b92d312e7ad2857d99af2e','Exact interrupted bank admission')
    old=A.read(oldref['path'])
    for k in ('queue','approval','runner','qualification','source_review','recovery'):A.verify(old[k])
    ledger_ref=A.bind(A.R/'physical_ledger.json');ledger=A.read(ledger_ref['path']);passes=ledger['passes']
    A.require(len(passes)==120 and sum(x['status']=='PASS' for x in passes)==118 and sum(x['status']=='FAIL' for x in passes)==2,'Exact120 history')
    A.require({x['attempt_id'] for x in passes if x['status']=='FAIL'}=={'P_MAIN6_S45_01_17','P_MAIN6_S45_04_19'},'Both original telemetry failures preserved')
    first_auth=A.read(A.verify(old['groups'][0]['authorization'])['path'])
    inherited=first_auth['reviewed_recoveries'];recoveries=inherited+[rb]
    for b in recoveries:A.verify(b)
    spec=importlib.util.spec_from_file_location('reviewed_v10_closure',owner['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    A.require(module.prior_closure(A.R,recoveries)==ledger,'All actual old/new recovery semantics and exact ledger')
    partial=A.bind(A.R/'partial_bank_review_v2/B3_FIRST18_TRANSPORT.json')
    A.require(partial['sha256']=='4322d76bdb6235936d2950cb159c1783558fd37fc76c173aa3cfdf2c4b6f7668','Exact18 transport review')
    partial_data=A.read(partial['path'])
    A.require({x['attempt_id'] for x in partial_data['attempts']}==DONE,'Exact18 reviewed PASS credits')
    queue=copy.deepcopy(A.read(old['queue']['path']))
    cp_ref=A.bind(olddir/'state/CHECKPOINT.json');cp=A.read(cp_ref['path'])
    A.require(cp['status']=='REVIEW_FAILURE' and cp['active']['job_id']=='bank_v3_P_MAIN6_B3','Exact interrupted B3 state')
    expected_closed={f'bank_v3_{g}{suffix}' for g in SKIP_GROUPS for suffix in ('_pre_QA','','_post_QA')}|{'bank_v3_P_MAIN6_B3_pre_QA'}
    A.require(set(cp['completed'])==expected_closed,'Exact seven closed previous stages')
    rspec=importlib.util.spec_from_file_location('prior_bank_completion_validation',old['runner']['path'])
    prior_runner=importlib.util.module_from_spec(rspec);rspec.loader.exec_module(prior_runner)
    previous_closed=[]
    for job in queue['jobs']:
        if job['job_id'] in expected_closed:
            completion=cp['completed'][job['job_id']]
            A.require(completion['status']=='DECLARED_ARTIFACTS_VERIFIED' and completion['exit_code']==0,'Prior stage must be fully closed')
            actual=prior_runner.validate_completion(job,completion['identity'])
            A.require(actual==completion['validation'],'Previous complete/restore/QA artifact bindings changed')
            previous_closed.append(dict(job_id=job['job_id'],validation=actual))
    queue['jobs']=[j for j in queue['jobs'] if not any(j['job_id'] in {f'bank_v3_{g}',f'bank_v3_{g}_pre_QA',f'bank_v3_{g}_post_QA'} for g in SKIP_GROUPS)]
    A.require(len(queue['jobs'])==54,'Exact54 remaining stages')
    groups=[];all_rows=[];replacements={};charged_ids={x['attempt_id'] for x in passes}
    for group in old['groups']:
        if group['group_id'] in SKIP_GROUPS:continue
        pb0=A.verify(group['plan']);ab0=A.verify(group['authorization'])
        plan=A.read(pb0['path']);auth=A.read(ab0['path'])
        A.require(auth['reviewed_recoveries']==inherited,'Original recovery context differs')
        plan.update(owner=owner,supervisor_bridge=bridge,owner_restoration_source_review=sr,owner_execution_source_freeze=ef,admission_helper=helper_binding,admission_readme=readme_binding,restoration_policy='exact_static_plus_verified_dynamic_agc.v1')
        rows=[]
        for original in plan['attempts']:
            ident=original['attempt_id']
            if ident in DONE:continue
            row=copy.deepcopy(original)
            if ident in RENAMES:
                row.update(attempt_id=RENAMES[ident],retry_of_attempt_id=ident,
                    retry_reason='Fresh qualified telemetry epoch pre-QA' if ident.startswith('QA_') else 'Preserved original telemetry-finalization FAIL; exact source repeated')
            A.require(row['attempt_id'] not in charged_ids,'Cannot repeat an existing charged ID')
            destination=Path(plan['payload_root'])/'beam_bank'/row['case_id']/row['profile']/row['attempt_id']
            A.require(not destination.exists(),'Existing payload cannot be reused')
            rows.append(row)
        plan['attempts']=rows
        if group['group_id']=='P_MAIN6_B3':
            plan['previous_pass_transport_review']=partial
            plan['excluded_previously_completed_attempt_ids']=sorted(DONE)
        directory=out/'groups'/group['group_id']
        A.save(directory/'CAPTURE_PLAN.json',plan);pb=A.bind(directory/'CAPTURE_PLAN.json')
        # Historical producer copies remain nested in the reviewed recovery proof.
        # Only the frozen canonical execution graph enters the owner's flat snapshot.
        sources=copy.deepcopy(execution_sources)
        auth.update(plan_sha256=pb['sha256'],source_bindings=sources,reviewed_recoveries=recoveries,
            restoration_source_review=sr,owner_execution_source_freeze=ef,admission_helper=helper_binding,admission_readme=readme_binding,attempt_ids=[x['attempt_id'] for x in rows],ledger_before_admission=ledger_ref,
            charged_playback_seconds=float(A.charge(rows)),
            partial_pass_transport_review=partial,scope='Retain60 earlier canonical MAIN plus18 B3 transport-verified PASS captures; fresh B3 pre-QA_R2, failed04_19_R2, every other pending row. Original failures/charges preserved. No new waveform/gain/guard/profile/timing policy.')
        A.save(directory/'CAPTURE_AUTHORIZATION.json',auth);ab=A.bind(directory/'CAPTURE_AUTHORIZATION.json')
        replacements[pb0['path']]=pb;replacements[ab0['path']]=ab
        groups.append(dict(group_id=group['group_id'],plan=pb,authorization=ab,attempts=len(rows)))
        all_rows.extend(rows)
    A.require(len(all_rows)==312 and len({x['attempt_id'] for x in all_rows})==312,'Exact312 unique future attempts')
    total=sum((Fraction(str(x['charged_playback_s'])) for x in passes),Fraction())+A.charge(all_rows)
    A.require(total==Fraction('19805.740625') and len(passes)+len(all_rows)==432,'Exact432/19805.740625 forecast')
    previous=None
    for job in queue['jobs']:
        oldid=job['job_id'];A.require(oldid.startswith('bank_v3_'),'Expected old job epoch')
        job['job_id']='bank_v4_'+oldid[len('bank_v3_'):]
        job['predecessor_job_id']=previous;previous=job['job_id']
        argv=job['argv'];index=argv.index('--attempt-ids')+1
        ids=[RENAMES.get(x,x) for x in argv[index:] if x not in DONE]
        A.require(ids,'Every stage retains actual attempts')
        argv[index:]=ids
        argv[1]=bridge['path'];argv[argv.index('--owner')+1]=owner['path'];argv[argv.index('--owner-sha256')+1]=owner['sha256']
        for option in ('--plan','--authorization'):
            b=replacements[argv[argv.index(option)+1]]
            argv[argv.index(option)+1]=b['path'];argv[argv.index(option+'-sha256')+1]=b['sha256']
        argv[argv.index('--batch')+1]=job['job_id']
        mapping=dict(RENAMES);mapping[oldid]=job['job_id']
        for key in ('heartbeat_path','completion_path','stop_request_path','restoration_path'):
            job[key]=path_map(job[key],mapping)
        artifacts=[]
        for art in job['expected_artifacts']:
            if DONE.intersection(Path(art['path']).parts):continue
            art['path']=path_map(art['path'],mapping);fields=art.get('expected_fields',{})
            if 'plan.sha256' in fields:
                fields.update({'plan.sha256':argv[argv.index('--plan-sha256')+1],
                    'authorization.sha256':argv[argv.index('--authorization-sha256')+1],
                    'owner.sha256':owner['sha256'],'wrapper.sha256':bridge['sha256'],
                    'semantic_checks.attempt_count':len(ids)})
            if fields.get('attempt.attempt_id') in RENAMES:fields['attempt.attempt_id']=RENAMES[fields['attempt.attempt_id']]
            artifacts.append(art)
        job['expected_artifacts']=artifacts
        sources=[replacements.get(b['path'],b) for b in job['source_bindings']]
        sources+=execution_sources+[sr,rb,ef,partial,cp_ref,helper_binding,readme_binding]
        job['source_bindings']=list({b['path']:b for b in sources}.values())
        for b in job['source_bindings']:A.verify(b)
        A.require(not Path(job['completion_path']).parent.exists() and not(A.R/'hardware_batches'/job['job_id']).exists(),'Fresh batch/protocol destinations')
    A.require(A.bind(A.R/'physical_ledger.json')==ledger_ref,'Ledger changed during admission')
    spec=importlib.util.spec_from_file_location('remaining_bank_runner',old['runner']['path'])
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    A.save(out/'QUEUE.json',queue);qb=A.bind(out/'QUEUE.json')
    approval=A.read(old['approval']['path']);approval.update(queue_sha256=qb['sha256'],
        approved_job_sha256=[runner.digest(x) for x in queue['jobs']],authorization_ref=str(out/'ROOT_QUEUE_REVIEW.json'))
    A.require(runner.validate_queue(queue,approval,qb['sha256']) is True,'Exact literal runner gate')
    A.save(out/'APPROVAL.json',approval)
    A.require(dt.datetime.now(dt.timezone.utc)<dt.datetime(2026,9,16,19,8,57,tzinfo=dt.timezone.utc),'Original closeout reserve')
    A.require(shutil.disk_usage('C:/').free>=50*2**30 and shutil.disk_usage('G:/').free>=75*2**30,'Storage floors')
    checks=[]
    for group in groups:
        log=out/'validation'/(group['group_id']+'.log');log.parent.mkdir(parents=True,exist_ok=True)
        argv=[queue['jobs'][0]['argv'][0],'-B',owner['path'],'check-plan','--plan',group['plan']['path'],'--authorization',group['authorization']['path']]
        with log.open('x',encoding='utf-8') as f:proc=subprocess.run(argv,cwd=A.SIM,stdout=f,stderr=subprocess.STDOUT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        A.require(proc.returncode==0,'Owner check-plan failed: '+str(log))
        checks.append(dict(group_id=group['group_id'],argv=argv,exit_code=proc.returncode,log=A.bind(log)))
    receipt=dict(status='ROOT_ADMITTED_REMAINING_BANK_AFTER_TELEMETRY_RECOVERY_PENDING_LAUNCH',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        root_owner_thread_id=A.THREAD,queue=qb,approval=A.bind(out/'APPROVAL.json'),runner=old['runner'],owner=owner,bridge=bridge,policy=policy,
        source_review=sr,owner_execution_source_freeze=ef,owner_execution_dependencies=execution_sources,recovery=rb,reviewed_recoveries=recoveries,qualification=old['qualification'],original_bank_admission=oldref,
        groups=groups,owner_plan_checks=checks,helper=helper_binding,dependency=A.bind(A.__file__),readme=readme_binding,
        retained_pass_transport_review=partial,retained_pass_attempt_ids=sorted(DONE),current_charged_attempts=120,new_attempts_admitted=312,previous_closed_stages=previous_closed,previous_checkpoint=cp_ref,excluded_completed_groups=sorted(SKIP_GROUPS),
        total_forecast_attempts=432,total_forecast_charged_seconds=float(total),original_failures_preserved=True,playback_started=False)
    A.save(out/'ROOT_QUEUE_REVIEW.json',receipt)
    print(json.dumps(dict(status=receipt['status'],receipt=A.bind(out/'ROOT_QUEUE_REVIEW.json'),attempts=312,stages=len(queue['jobs']))))

if __name__=='__main__':main()
