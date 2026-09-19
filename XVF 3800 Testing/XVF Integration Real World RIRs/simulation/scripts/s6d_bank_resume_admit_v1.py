"""Fresh bank admission after explicitly reviewed V5 restoration recovery; README."""
import argparse
import copy
import datetime as dt
from fractions import Fraction
import importlib.util
from pathlib import Path
import shutil
import subprocess
import json
import s6d_bank_admit_v1 as A

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-review',type=Path,required=True)
    ap.add_argument('--recovery',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=A.R/'runner/bank_queue_v3')
    args=ap.parse_args();out=args.output.resolve()
    A.require(not out.exists() and out.is_relative_to(A.R/'runner'),'fresh root runner output required')
    source_review=A.read(args.source_review);sr=A.bind(args.source_review)
    A.require(source_review['status']=='ROOT_ACCEPTED_DYNAMIC_GAIN_RESTORATION_SOURCES_V1','root accepted V5 source required')
    for b in source_review['source_bindings']:A.verify(b)
    owner=A.verify(source_review['owner']);bridge=A.verify(source_review['bridge']);policy=A.verify(source_review['policy'])
    A.require(Path(owner['path']).name=='s6d_capture_owner_v5.py' and Path(bridge['path']).name=='s6d_capture_supervisor_bridge_v2.py','exact new restoration source epoch required')
    recovery=A.read(args.recovery);rb=A.bind(args.recovery)
    A.require(recovery['schema_version']=='edge-s6d-restoration-recovery.v1' and recovery['status']=='PASS','actual fresh getter-only recovery required')
    for k in ('original_restoration','original_owner','reapply_origin','initial_state','recovery_measurement','source_review'):A.verify(recovery[k])
    A.require(recovery['source_review']==sr,'recovery source review differs')
    original_dir=A.R/'runner/bank_queue_v2';old_review=A.read(original_dir/'ROOT_QUEUE_REVIEW.json')
    A.require(A.bind(original_dir/'ROOT_QUEUE_REVIEW.json')['sha256']=='089df8daf0e2385c1800b932b9739c7a69fc5315791665e843ad5c9db03a130c','exact original admitted bank required')
    for k in ('queue','approval','runner','qualification','metadata_review'):A.verify(old_review[k])
    ledger_binding=A.bind(A.R/'physical_ledger.json');ledger=A.read(ledger_binding['path']);passes=ledger['passes']
    A.require(len(passes)==34 and all(x['status']=='PASS' for x in passes),'exact34 charged capture history required; old batch restoration FAIL remains separate')
    failed=ledger['batches']['bank_v1_P_MAIN6_B1_pre_QA']
    A.require(recovery['original_restoration']==failed['restoration'] and recovery['original_owner']==failed['owner'],'recovery does not resolve exact old owner')
    # The reviewed owner performs the same file-only closure gate used before
    # hardware ownership. A status string alone cannot authorize new outputs.
    spec=importlib.util.spec_from_file_location('s6d_resume_closure_owner',owner['path'])
    closure_owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(closure_owner)
    A.require(closure_owner.prior_closure(A.R,[rb])==ledger,'reviewed V5 closure differs from exact34 bound ledger')
    A.require(A.bind(A.R/'physical_ledger.json')==ledger_binding,'physical ledger changed during recovery admission')
    original=A.read(old_review['queue']['path']);queue=copy.deepcopy(original)
    all_rows=[];groups=[];replacements={};old_id='QA_P_MAIN6_B1_PRE';new_id=old_id+'_R2'
    for g in old_review['groups']:
        old_pb=A.verify(g['plan']);old_ab=A.verify(g['authorization'])
        plan=A.read(old_pb['path']);auth=A.read(old_ab['path']);gid=g['group_id']
        plan.update(owner=owner,supervisor_bridge=bridge,owner_restoration_source_review=sr,restoration_policy='exact_static_plus_verified_dynamic_agc.v1')
        plan.pop('owner_V4_source_review',None)
        if gid=='P_MAIN6_B1':
            A.require(plan['attempts'][0]['attempt_id']==old_id,'expected first preQA')
            plan['attempts'][0]['attempt_id']=new_id
            plan['attempts'][0]['retry_of_attempt_id']=old_id
            plan['attempts'][0]['retry_reason']='New restoration epoch physical QA; old capture PASS and old strict restoration FAIL both preserved'
        for a in plan['attempts']:
            A.require(a['attempt_id'] not in {p['attempt_id'] for p in passes},'already charged attempt')
            dest=Path(plan['payload_root'])/'beam_bank'/a['case_id']/a['profile']/a['attempt_id']
            A.require(not dest.exists(),'existing destination must not be reused')
        directory=out/'groups'/gid
        A.save(directory/'CAPTURE_PLAN.json',plan);pb=A.bind(directory/'CAPTURE_PLAN.json')
        active_sources=auth['source_bindings']+[b for b in source_review['source_bindings'] if Path(b['path']).name in ('s6d_capture_owner_v5.py','README_S6D_CAPTURE_V5.md','s6d_restoration_policy_v1.py','s6d_capture_supervisor_bridge_v2.py')]
        active_sources=list({b['path']:b for b in active_sources}.values())
        A.require(len({Path(b['path']).name for b in active_sources})==len(active_sources),'snapshot basenames must be unique')
        auth.update(plan_sha256=pb['sha256'],source_bindings=active_sources,reviewed_recoveries=[rb],restoration_source_review=sr,
            attempt_ids=[a['attempt_id'] for a in plan['attempts']],ledger_before_admission=ledger_binding,
            scope='Fresh V5/V2 bank continuation after exact getter-only recovery. FirstQA repeated once underR2; all remaining source/profile/guard/gain settings unchanged. Original strict restoration failure is retained.')
        A.save(directory/'CAPTURE_AUTHORIZATION.json',auth);ab=A.bind(directory/'CAPTURE_AUTHORIZATION.json')
        replacements[old_pb['path']]=pb;replacements[old_ab['path']]=ab
        groups.append(dict(group_id=gid,plan=pb,authorization=ab,attempts=len(plan['attempts'])))
        all_rows.extend(plan['attempts'])
    A.require(len(all_rows)==394 and len({a['attempt_id'] for a in all_rows})==394,'394 future unique attempts')
    total=sum((Fraction(str(p['charged_playback_s'])) for p in passes),Fraction())+A.charge(all_rows)
    A.require(total==Fraction('19682.375375') and len(passes)+len(all_rows)==428,'exact428/19682.375375 forecast')
    seen=[]
    for j in queue['jobs']:
        old_job_id=j['job_id'];A.require(old_job_id.startswith('bank_v1_'),'original bank job prefix')
        j['job_id']='bank_v2_'+old_job_id[len('bank_v1_'):]
        j['predecessor_job_id']=seen[-1] if seen else None;seen.append(j['job_id'])
        argv=j['argv'];argv[argv.index('--owner')+1]=owner['path'];argv[argv.index('--owner-sha256')+1]=owner['sha256'];argv[1]=bridge['path']
        for option,hash_option in (('--plan','--plan-sha256'),('--authorization','--authorization-sha256')):
            b=replacements[argv[argv.index(option)+1]];argv[argv.index(option)+1]=b['path'];argv[argv.index(hash_option)+1]=b['sha256']
        argv[argv.index('--batch')+1]=j['job_id']
        argv[:]=[new_id if x==old_id else x for x in argv]
        for key in ('heartbeat_path','completion_path','stop_request_path','restoration_path'):
            j[key]=j[key].replace(old_job_id,j['job_id'])
        for artifact in j['expected_artifacts']:
            artifact['path']=artifact['path'].replace(old_job_id,j['job_id']).replace('\\'+old_id+'\\','\\'+new_id+'\\')
            f=artifact.get('expected_fields',{})
            if 'plan.sha256' in f:
                f.update({'plan.sha256':argv[argv.index('--plan-sha256')+1],'authorization.sha256':argv[argv.index('--authorization-sha256')+1],
                    'owner.sha256':owner['sha256'],'wrapper.sha256':bridge['sha256'],
                    'semantic_checks.restoration.checks.restoration_policy_valid':True,
                    'semantic_checks.restoration.checks.exact_static_configuration_match':True,
                    'semantic_checks.restoration.checks.requested_gain_set_verified':True,
                    'semantic_checks.restoration.checks.packed_input_disabled':True,
                    'semantic_checks.restoration.restoration_policy':'exact_static_plus_verified_dynamic_agc.v1',
                    'semantic_checks.restoration.no_mutation_scope':False})
                f.pop('semantic_checks.restoration.checks.exact_configuration_match',None)
            if f.get('attempt.attempt_id')==old_id:f['attempt.attempt_id']=new_id
        source=[replacements.get(b['path'],b) for b in j['source_bindings']]
        source += [owner,bridge,policy,sr,rb,A.bind(__file__),A.bind(Path(__file__).with_name('README_S6D_BANK_RESUME_ADMIT_V1.md'))]
        j['source_bindings']=list({b['path']:b for b in source}.values())
        for b in j['source_bindings']:A.verify(b)
        A.require(not Path(j['completion_path']).parent.exists() and not(A.R/'hardware_batches'/j['job_id']).exists(),'fresh protocol and batch destinations required')
    A.require(A.bind(A.R/'physical_ledger.json')==ledger_binding,'physical ledger changed before queue approval')
    spec=importlib.util.spec_from_file_location('s6d_resume_runner',old_review['runner']['path']);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    A.save(out/'QUEUE.json',queue);qb=A.bind(out/'QUEUE.json')
    approval=A.read(old_review['approval']['path']);approval.update(queue_sha256=qb['sha256'],approved_job_sha256=[runner.digest(j) for j in queue['jobs']],authorization_ref=str(out/'ROOT_QUEUE_REVIEW.json'))
    A.require(runner.validate_queue(queue,approval,qb['sha256']) is True,'literal V4 runner queue validation')
    A.save(out/'APPROVAL.json',approval)
    A.require(dt.datetime.now(dt.timezone.utc)<dt.datetime(2026,9,16,19,8,57,tzinfo=dt.timezone.utc),'campaign closeout reserve reached')
    A.require(shutil.disk_usage('C:/').free>=50*2**30 and shutil.disk_usage('G:/').free>=75*2**30,'storage floors')
    checks=[]
    for g in groups:
        log=out/'validation'/(g['group_id']+'.log');log.parent.mkdir(parents=True,exist_ok=True)
        argv=[queue['jobs'][0]['argv'][0],'-B',owner['path'],'check-plan','--plan',g['plan']['path'],'--authorization',g['authorization']['path']]
        with log.open('x',encoding='utf-8') as f:
            p=subprocess.run(argv,cwd=A.SIM,stdout=f,stderr=subprocess.STDOUT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        A.require(p.returncode==0,'owner check-plan failed: '+str(log));checks.append(dict(group_id=g['group_id'],argv=argv,exit_code=p.returncode,log=A.bind(log)))
    receipt=dict(status='ROOT_ADMITTED_FRESH_BANK_AFTER_REVIEWED_RECOVERY_PENDING_LAUNCH',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        root_owner_thread_id=A.THREAD,queue=qb,approval=A.bind(out/'APPROVAL.json'),runner=old_review['runner'],owner=owner,bridge=bridge,policy=policy,
        source_review=sr,recovery=rb,qualification=old_review['qualification'],original_bank_admission=A.bind(original_dir/'ROOT_QUEUE_REVIEW.json'),
        groups=groups,owner_plan_checks=checks,helper=A.bind(__file__),dependency=A.bind(A.__file__),readme=A.bind(Path(__file__).with_name('README_S6D_BANK_RESUME_ADMIT_V1.md')),
        current_charged_attempts=34,new_attempts_admitted=394,total_forecast_attempts=428,total_forecast_charged_seconds=float(total),
        first_QA_retry=new_id,original_capture_and_strict_restoration_failure_preserved=True,playback_started=False,
        scope='Only restoration policy/provenance and firstQA retry change. Original waveform/gain/guards/profiles/source-role and limits preserved. Same-pass/beam efficacy remains separately evaluated.')
    A.save(out/'ROOT_QUEUE_REVIEW.json',receipt)
    print(json.dumps(dict(status=receipt['status'],receipt=A.bind(out/'ROOT_QUEUE_REVIEW.json'),attempts=394,stages=60)))

if __name__=='__main__':main()
