"""Exact original171 plus fresh5 input construction; README_S6D_NATIVE176_COMPOSITE_V2.md."""
from copy import deepcopy
from datetime import datetime
import argparse, hashlib, importlib.util, json, shutil, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT=HERE/'s6d_native176_scoring_inputs_v1.py'
assert hashlib.sha256(PARENT.read_bytes()).hexdigest()=='e379a78c98c937e32549494da52cf1da68278a40ec67294885c1d4fe19299957','Accepted builder parent differs'
_s=importlib.util.spec_from_file_location('s6d_original176_builder',PARENT);B=importlib.util.module_from_spec(_s);_s.loader.exec_module(B)
need=B.need;Cache=B.Cache;save=B.save
COMPOSITE=B.R/'runner/native176_recovery5_preparation_v1/COMPOSITE_MAP.json'
COMPOSITE_SHA='236839692934235d2e320e44d2e3f757aa572eb044d08d64af4dc6156b9ac07d'
RECOVERY_FREEZE=COMPOSITE.parent/'SOURCE_FREEZE.json'
SCORER=HERE/'s6d_native_correctness_composite_v2.py'
README=HERE/'README_S6D_NATIVE176_COMPOSITE_V2.md'
STOP_REASON='complete payload accounting is unavailable: last complete census is older than60 seconds; OFFLINE_CHILD_EXITED_AFTER_STOP'

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def scientific(job):return {k:v for k,v in job.items() if k!='output'}
def launch_identity(record):
    value=record.get('creation_time');text=record.get('creation_utc')
    parsed=None
    if isinstance(text,str):
        instant=datetime.fromisoformat(text.replace('Z','+00:00'));need(instant.tzinfo is not None,'Launch UTC must include timezone');parsed=instant.timestamp()
    need(value is not None or parsed is not None,'Bound launch creation time absent')
    if value is not None and parsed is not None:need(B.finite(value) and abs(value-parsed)<.001,'Conflicting launch creation forms')
    value=parsed if value is None else value
    need(type(record.get('pid')) is int and record['pid']>0 and B.finite(value) and value>0,'Invalid launch identity')
    return dict(pid=record['pid'],creation_time=value)

def approval_exact(queue,ref,approval):
    expected=[digest(j) for j in queue['jobs']]
    need(approval.get('schema')=='s6d_queue_approval_v1' and approval.get('run_id')==queue['run_id'] and approval.get('queue_sha256')==ref['sha256'] and approval.get('authorization_ref'),'Exact actually approved queue required')
    need(len(approval['approved_job_sha256'])==len(expected) and set(approval['approved_job_sha256'])==set(expected),'Exact approved job digests required')

def launch_exact(record,queue,approval,state):
    argv=record.get('argv',[])
    for flag,value in (('--queue',queue['path']),('--queue-sha256',queue['sha256']),('--approval',approval['path']),('--approval-sha256',approval['sha256']),('--state-dir',str(state))):
        need(argv.count(flag)==1 and argv[argv.index(flag)+1]==value,'Supervisor launch queue/approval/state differs')
    need('--keep-awake' in argv,'Owned keep-awake launch required')
    return launch_identity(record)

def stopped_closed(queue,ref,checkpoint,lock,closure,launch):
    """Historical blocked ownership closure is explicit; no synthetic FINISH is created."""
    ids=[j['job_id'] for j in queue['jobs']];completed=checkpoint.get('completed',{});active=checkpoint.get('active') or {}
    need(len(ids)==176 and checkpoint.get('run_id')==queue['run_id'] and checkpoint.get('queue_sha256')==ref['sha256'],'Original exact176 checkpoint required')
    need(checkpoint.get('status')=='REPORT_BLOCKED' and checkpoint.get('reason')==STOP_REASON and set(completed)==set(ids[:171]) and len(completed)==171 and active.get('job_id')==ids[171],'Exact historical171/stopped child required')
    need(lock.get('run_id')==queue['run_id'] and lock.get('queue_sha256')==ref['sha256'] and isinstance(lock.get('owner_nonce'),str) and len(lock['owner_nonce'])==32 and not lock.get('unresolved_hardware'),'Historical owner lock differs')
    li=launch_identity(launch);need(li=={k:lock[k] for k in ('pid','creation_time')},'Historical supervisor launch differs')
    result=closure.get('result') or {};awake=closure.get('keep_awake') or {};census=closure.get('payload_census_closure') or {};snapshot=census.get('snapshot') or {}
    need(closure.get('run_id')==queue['run_id'] and result.get('run_id')==queue['run_id'] and result.get('action')=='REPORT_BLOCKED' and result.get('reason')==STOP_REASON and result.get('done')==171 and result.get('total')==176 and result.get('job_id')==active['job_id'],'Historical failure disposition changed')
    need(closure.get('owner_lock')=='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' and closure.get('hardware_restoration_unresolved') is False,'Historical supervisor ownership unresolved')
    need(awake==dict(requested=True,owned=True,restored=True,status='RESTORED'),'Historical keep-awake closure absent')
    need(census.get('closed') is True and snapshot.get('running') is False and snapshot.get('has_complete') is True and snapshot.get('pending') is False and snapshot.get('error') is None and snapshot.get('violation_latched') is False and snapshot.get('stale') is True,'Historical census closure must retain its exact stale failure')
    identities=[dict(role='original_supervisor',**li)]
    for job_id in ids[:171]:
        saved=completed[job_id];identity=saved['identity']
        need(saved.get('status')=='DECLARED_ARTIFACTS_VERIFIED' and type(saved.get('exit_code')) is int and saved['exit_code']==0 and identity.get('run_id')==queue['run_id'] and identity.get('job_id')==job_id and isinstance(identity.get('child_run_id'),str) and identity['child_run_id'],'Original completed identity differs')
        identities.append(dict(role=job_id,pid=identity['pid'],creation_time=identity['creation_time']))
    need(active.get('run_id')==queue['run_id'] and isinstance(active.get('child_run_id'),str) and active['child_run_id'],'Stopped instance identity absent')
    identities.append(dict(role='stopped_uncredited_original',pid=active['pid'],creation_time=active['creation_time']))
    for item in identities:need(type(item['pid']) is int and item['pid']>0 and B.finite(item['creation_time']) and item['creation_time']>0,'Finite exact process identity required')
    return identities

def composite_rows(composite,old_queue,checkpoint,recovery_queue):
    rows=composite['rows'];old={j['job_id']:j for j in old_queue['jobs']};new={j['job_id']:j for j in recovery_queue['jobs']}
    ids=[r['scientific_job_id'] for r in rows]
    need(len(rows)==176 and len(set(ids))==176 and ids==list(old) and [r['ordinal'] for r in rows]==list(range(1,177)),'Exact original ordered176 mapping required')
    need(composite['expected']==dict(original_declared=176,original_completed=171,recovery_required=5,recovery_FINISH_done=5,recovery_FINISH_total=5) and composite['stopped_original_attempt_credited'] is False and composite['old176_FINISH_claimed'] is False and composite['science_declaration_changed'] is False,'Composite evidence classes differ')
    originals=[];recoveries=[]
    for row in rows:
        job_id=row['scientific_job_id'];need(row['original_queue_job_sha256']==digest(old[job_id]),'Original literal job differs')
        if row['origin']=='original_completed':
            need(row['original_execution_job_id']==job_id and row['original_completion_path']==old[job_id]['completion_path'] and row['saved_checkpoint_record']==checkpoint['completed'].get(job_id),'Original171 saved record differs');originals.append(job_id)
        else:
            need(row['origin']=='recovery_required' and job_id not in checkpoint['completed'] and row['execution_job_id']==job_id+'_recover1' and row['native_job_id']==job_id and row['accepted_recovery_result'] is False,'Unaccepted recovery mapping differs')
            execution=row['execution_job_id'];need(execution in new and digest(new[execution])==row['recovery_queue_job_sha256'] and new[execution]['completion_path']==row['recovery_completion_path'],'Recovery literal queue differs');recoveries.append(execution)
    need(len(originals)==171 and set(originals)==set(checkpoint['completed']) and len(recoveries)==5 and recoveries==list(new) and len(new)==len(recovery_queue['jobs']),'Exact171+5 partition required')
    return {r['scientific_job_id']:r for r in rows}

def metadata(cache):
    data=B.static_inputs(cache);cb=cache.binding(COMPOSITE,COMPOSITE_SHA);c=cache.load(COMPOSITE)
    need(c['schema']=='s6d-native176-composite-execution.v1' and c['status']=='PENDING_EXACT_FIVE_FINISH_AND_ROOT_COMPOSITE_ADMISSION','Exact composite schema required')
    rf=cache.binding(RECOVERY_FREEZE,'adae410e4a4d024e7a39f9bd9b90f528b72e19db2280a3e2d947174c3fe78d7d');freeze=cache.load(RECOVERY_FREEZE)
    need(freeze['composite']==cb and freeze['queue']==c['recovery_queue'],'Recovery freeze source graph differs');cache.graph(freeze['sources'])
    need(c['original']['queue']==data['queue_ref'],'Original queue differs');cache.graph(c['original']);cache.check(c['recovery_scope']);rq=cache.verified(c['recovery_queue']);cp=cache.verified(c['original']['checkpoint'])
    need(rq['runner_sha256']==B.PINS['runner'] and rq['protocol_wrapper']==data['queue']['protocol_wrapper'] and rq['payload_policy']==data['queue']['payload_policy'] and rq['disk_policy']==data['queue']['disk_policy'] and rq['campaign']==data['queue']['campaign'],'Recovery must retain V4/874d/40/floors/deadline')
    rows=composite_rows(c,data['queue'],cp,rq);contexts={};manifests={x['path']:x for x in data['prospective']['execution_manifests']};qold={j['job_id']:j for j in data['queue']['jobs']};qnew={j['job_id']:j for j in rq['jobs']}
    for sid,row in rows.items():
        original_ref,oldjob,oldmanifest=data['declared'][sid]
        if row['origin']=='original_completed':ref,job,manifest,qjob=original_ref,oldjob,oldmanifest,qold[sid]
        else:
            need(row['original_manifest']==original_ref and row['original_native_job_sha256']==digest(oldjob) and row['scientific_fields_sha256']==digest(scientific(oldjob)),'Original scientific source differs')
            ref=row['recovery_manifest'];manifest=cache.verified(ref);matches=[j for j in manifest['jobs'] if j['job_id']==sid];need(len(matches)==1,'Recovery native ID ambiguous');job=matches[0];qjob=qnew[row['execution_job_id']]
            need(scientific(job)==scientific(oldjob) and job['output']==row['output'],'Recovery science changed beyond output')
            permitted={'jobs','job_count','source_audio_total_sec','prior_recovery_manifest','created_utc','purpose','payload_root','status','recovery_original_authorities'}
            need({k:v for k,v in manifest.items() if k not in permitted}=={k:v for k,v in oldmanifest.items() if k not in permitted} and manifest['prior_recovery_manifest']==original_ref and manifest['recovery_original_authorities']==c['original'],'Recovery manifest changed scientific/runtime context')
            argv=qjob['argv'];need(argv[argv.index('--native-job-id')+1]==sid and argv[argv.index('--manifest')+1]==ref['path'] and argv[argv.index('--manifest-sha256')+1]==ref['sha256'],'Recovery CLI/native source differs')
            cache.graph(qjob['source_bindings']);manifests[ref['path']]=ref
        contexts[sid]=dict(origin=row['origin'],qjob=qjob,manifest_ref=ref,job=job,manifest=manifest)
    return dict(data=data,composite=c,composite_ref=cb,recovery_freeze=rf,original_checkpoint=cp,recovery_queue=rq,contexts=contexts,execution_manifests=list(manifests.values()),original_launch_ref=freeze['original_supervisor_launch'])

def selection_for(meta):
    return [dict(scientific_job_id=row['scientific_job_id'],execution_job_id=meta['contexts'][row['scientific_job_id']]['qjob']['job_id'],origin=row['origin'],manifest=meta['contexts'][row['scientific_job_id']]['manifest_ref']) for row in meta['composite']['rows']]

def state_paths(cache,refs,state):
    lock=cache.verified(refs['closed_lock']);nonce=lock.get('owner_nonce')
    for key,name in (('checkpoint','CHECKPOINT.json'),('closed_lock','CLOSED_LOCK_'+str(nonce)+'.json'),('supervisor_closure','SUPERVISOR_CLOSURE_'+str(nonce)+'.json')):need(Path(refs[key]['path']).resolve()==state/name,'Exact state/immutable closure path required')
    need(not (state/'SUPERVISOR_LOCK.json').exists(),'Supervisor lock active')
    return lock

def prepare(output):
    need(output.resolve().is_relative_to(B.R) and not output.exists(),'Fresh compact R preparation required');cache=Cache();m=metadata(cache)
    proposal=dict(schema='s6d-native176-scoring-build-proposal.v2',status='PREPARED_ONLY_NOT_APPROVED',builder=cache.binding(__file__),readme=cache.binding(README),parent=cache.binding(PARENT),composite=m['composite_ref'],recovery_freeze=m['recovery_freeze'],prospective=m['data']['prospective_ref'],scorer=cache.binding(SCORER),analysis_executable=cache.binding(B.ANALYSIS),original_launch=m['original_launch_ref'],required_future_admission=dict(schema='s6d-native176-scoring-build-admission.v2',status='ROOT_ACCEPTED_NATIVE176_COMPOSITE_CLOSED_INPUT_BUILDER_V2',owner_thread_id=B.ROOT_ID,fields=['builder','readme','proposal','composite','recovery: approval,root_admission,supervisor_launch,checkpoint,closed_lock,supervisor_closure','output_root fresh G','score_output_root fresh nested G'],allow_closed_input_construction=True),original171_only_saved_declarations=True,fresh5_FINISH_required=True,actual_scoring=False,actual_PID_checks=False)
    cache.unchanged();output.mkdir(parents=True);save(output/'PROPOSAL.json',proposal);return cache.binding(output/'PROPOSAL.json')

def build(admission_path,sha):
    cache=Cache();ar=cache.binding(admission_path,sha);admission=cache.load(admission_path)
    need(admission.get('schema')=='s6d-native176-scoring-build-admission.v2' and admission.get('status')=='ROOT_ACCEPTED_NATIVE176_COMPOSITE_CLOSED_INPUT_BUILDER_V2' and admission.get('owner_thread_id')==B.ROOT_ID and admission.get('allow_closed_input_construction') is True,'Explicit root composite input construction required')
    need(admission['builder']==cache.binding(__file__) and admission['readme']==cache.binding(README),'Builder/README differs');proposal=cache.verified(admission['proposal']);m=metadata(cache);data=m['data'];c=m['composite'];old=c['original'];recovery=admission['recovery'];newstate=Path(c['future_state_dir']).resolve()
    need(proposal['status']=='PREPARED_ONLY_NOT_APPROVED' and proposal['builder']==admission['builder'] and proposal['composite']==admission['composite']==m['composite_ref'] and proposal['prospective']==data['prospective_ref'] and proposal['recovery_freeze']==m['recovery_freeze'] and proposal['scorer']==cache.binding(SCORER),'Prepared composite graph differs')
    oldlock=state_paths(cache,old,B.STATE);newlock=state_paths(cache,recovery,newstate)
    oldapproval=cache.verified(old['approval']);approval_exact(data['queue'],data['queue_ref'],oldapproval)
    oldlaunch=cache.verified(m['original_launch_ref']);launch_exact(oldlaunch,data['queue_ref'],old['approval'],B.STATE)
    identities=stopped_closed(data['queue'],data['queue_ref'],m['original_checkpoint'],oldlock,cache.verified(old['supervisor_closure']),oldlaunch)
    stopped=cache.verified(old['stopped_launch']);stop=cache.verified(old['stopped_STOP']);active=m['original_checkpoint']['active']
    need(all(stopped[k]==active[k] and stop[k]==active[k] for k in ('run_id','job_id','child_run_id','pid','creation_time')),'Stopped launch/STOP ownership differs')
    oldjob=data['declared'][active['job_id']][1];oldq=next(j for j in data['queue']['jobs'] if j['job_id']==active['job_id'])
    need(not Path(oldq['completion_path']).exists() and not (Path(oldjob['output'])/'FULL_SOURCE_AUDIT.json').exists(),'Stopped original disposition changed; re-review required')
    need(Path(recovery['approval']['path']).resolve()==Path(c['future_approval_path']).resolve() and Path(recovery['root_admission']['path']).resolve()==Path(c['future_root_admission_path']).resolve(),'Exact recovery root authority paths required')
    newapproval=cache.verified(recovery['approval']);approval_exact(m['recovery_queue'],c['recovery_queue'],newapproval);root=cache.verified(recovery['root_admission'])
    need(root.get('status')=='ROOT_ADMITTED_NATIVE176_RECOVERY5_PENDING_SUPERVISOR_PREFLIGHT' and root.get('owner_thread_id')==B.ROOT_ID and root.get('queue')==c['recovery_queue'] and root.get('composite_map')==m['composite_ref'] and root.get('approval')==recovery['approval'] and root.get('source_freeze')==m['recovery_freeze'] and root.get('original_authorities')==c['original'],'Recovery actual root admission differs')
    newlaunch=cache.verified(recovery['supervisor_launch']);li=launch_exact(newlaunch,c['recovery_queue'],recovery['approval'],newstate);newcp=cache.verified(recovery['checkpoint'])
    identities+=B.validate_closed(m['recovery_queue'],c['recovery_queue'],newcp,newlock,cache.verified(recovery['supervisor_closure']),li)
    import psutil
    absence=B.prove_absent(identities,psutil)
    need(shutil.disk_usage('C:/').free>=50*2**30 and shutil.disk_usage('G:/').free>=75*2**30,'C50/G75 floor unmet')
    out=Path(admission['output_root']).resolve();scoreout=Path(admission['score_output_root']).resolve();need(out.is_relative_to(B.G) and scoreout.is_relative_to(out) and out!=scoreout and not out.exists() and not scoreout.exists(),'Fresh bounded G input/scoring epoch required')
    prospective=data['prospective'];r,e,s=B.pure_apis(cache,prospective);gallery_map=cache.load(B.GALLERY);items=[];gallery_values={};validations=[]
    for row in prospective['rows']:
        sid=row['job_id'];context=m['contexts'][sid];qjob=context['qjob'];manifest_ref=context['manifest_ref'];job=context['job'];manifest=context['manifest'];checkpoint=m['original_checkpoint'] if context['origin']=='original_completed' else newcp;saved=checkpoint['completed'][qjob['job_id']]
        validation=r['validate_completion'](qjob,saved['identity']);need(validation==saved['validation'],'Saved actual completion artifacts changed')
        completion=cache.load(qjob['completion_path']);need(completion['native_job_id']==sid and completion['pid']==saved['identity']['pid'] and completion['creation_time']==saved['identity']['creation_time'] and completion['declared_model_assets']==manifest['assets'],'Actual protocol owner/native ID/assets differ')
        result_ref=cache.binding(Path(job['output'])/'RESULT.json');result=cache.verified(result_ref);audit_ref=cache.binding(Path(job['output'])/'FULL_SOURCE_AUDIT.json');audit=cache.verified(audit_ref)
        need(completion['manifest']==manifest_ref and completion['completion_audit']==audit_ref and completion['native_result']==result_ref and result['manifest']==manifest_ref and result['helper']==manifest['helper'] and result['job']==job,'Exact actual protocol/result/audit join differs')
        need(result['pid']==saved['identity']['pid'] and result['process_create_time']==saved['identity']['creation_time'],'Actual native PID+creation differs')
        need(audit['status']=='PASS_OFFLINE_EVIDENCE' and audit['errors']==[] and audit['manifest']==manifest_ref and audit['result']==result_ref and audit['job_id']==sid and audit['expected_frames_predeclared'] is True,'Accepted full-source audit differs')
        cache.check(job['audio']);need(cache.pcm[str(Path(job['audio']['path']).resolve())]==audit['journals']['source'],'Actual source PCM differs')
        for lane in ('asr','identity'):cache.check(audit['journals'][lane])
        finalization=cache.verified(audit['finalization']);consumer_closure=cache.verified(audit['consumer_closure']) if audit['consumer_closure'] else None
        s['admit_full_source'](job,audit);need(e['validate_completion'](result,job,finalization,audit['journals'],consumer_closure)==[],'Whole-source/native/finalizer/consumer guard failed')
        dispatch=cache.dispatch(audit['consumer_events']['path'],job['expected_frames'],e['validate_dispatch']);cache.check(audit['consumer_events']);need(dispatch==audit['dispatch'],'Actual full event dispatch differs')
        session=Path(result['session_dir']).resolve();need(session.is_relative_to(Path(job['output']).resolve()/'sessions'),'Foreign session output')
        need(Path(audit['finalization']['path']).resolve()==session/'session_finalization_v3.json' and Path(audit['consumer_events']['path']).resolve()==Path(job['output']).resolve()/'consumer_events.jsonl','Foreign finalizer/event path')
        latest=cache.binding(session/'latest_labelled_transcript.jsonl');reference=cache.verified(row['reference']);cache.graph(reference);need(reference['input_audio']==job['audio'] and reference['composition_frames']==job['expected_frames'],'Reference source/frames differ');s['validate_reference'](reference)
        gallery=B.gallery_row(job['gallery'],gallery_map['rows']);key='NONE' if job['gallery'] is None else job['gallery']['sha256'];gallery_values[key]=gallery
        if job['gallery'] is not None:
            actual=cache.verified(job['gallery']);need({(p['profile_id'],p['display_name']) for p in actual['profiles']}=={(p['profile_id'],p['display_name']) for p in gallery['profiles']},'Actual gallery identities differ')
            loaded=result['telemetry']['scheduler']['identity']['gallery'];need(loaded['manifest']==job['gallery'] and loaded['loaded_count']==len(gallery['profiles']),'Actual loaded gallery differs')
        items.append(dict(job_id=sid,manifest=manifest_ref,result=result_ref,completion_audit=audit_ref,consumer_events=audit['consumer_events'],latest=latest,reference=row['reference'],gallery_key=key))
        validations.append(dict(job_id=sid,execution_job_id=qjob['job_id'],identity=saved['identity'],validation=validation,dispatch=dispatch))
    need(len(items)==176 and not (B.STATE/'SUPERVISOR_LOCK.json').exists() and not (newstate/'SUPERVISOR_LOCK.json').exists(),'Incomplete or restarted execution');cache.unchanged()
    out.mkdir(parents=True,exist_ok=False);grefs={}
    for key,value in gallery_values.items():path=out/('GALLERY_'+key+'.json');save(path,value);grefs[key]=cache.binding(path)
    for item in items:item['gallery_row']=grefs[item.pop('gallery_key')]
    selection=selection_for(m);proof=dict(schema='s6d-native176-composite-closed-input-validation.v2',status='ALL176_COMPOSITE_CLOSED_INPUTS_VERIFIED',admission=ar,builder=admission['builder'],composite=m['composite_ref'],original_completed=171,recovery_completed=5,original_blocked_checkpoint=old['checkpoint'],recovery_FINISH_checkpoint=recovery['checkpoint'],owner_exit=absence,execution_selection=selection,completion_validations=validations,unique_hashed_paths=len(cache.entries),hash_reads=cache.hash_reads,models_started=0,actual_scoring=False)
    save(out/'VALIDATION.json',proof)
    spec=dict(schema='s6d-native-scoring-inputs.v1',status='APPROVED_CLOSED_NATIVE_INPUTS',owner_exit_verified=True,source_graph_verified=True,scorer=cache.binding(SCORER),dependencies=prospective['dependencies'],gallery_map=cache.binding(B.GALLERY),execution_manifests=m['execution_manifests'],execution_selection=selection,composite_execution=m['composite_ref'],jobs=items,unavailable_jobs=[],comparison_pairs=prospective['comparison_pairs'],output_root=str(scoreout),closed_input_validation=cache.binding(out/'VALIDATION.json'),builder=admission['builder'],root_build_admission=ar,source_scope='Original171 plus fresh5 exact actual source manifests. Historical stopped attempt preserved and uncredited. Headless consumer only; interruption/concurrency context retained, GUI/scanout unmeasured.')
    cache.unchanged();need(not (B.STATE/'SUPERVISOR_LOCK.json').exists() and not (newstate/'SUPERVISOR_LOCK.json').exists(),'Supervisor restarted before commit');save(out/'SCORING_INPUTS.json',spec);ref=cache.binding(out/'SCORING_INPUTS.json')
    save(out/'SCORER_COMMAND_PROPOSED.json',dict(status='PREPARED_NOT_LAUNCHED',argv=[str(B.ANALYSIS),'-B',str(SCORER),'--spec',ref['path'],'--sha256',ref['sha256']],analysis_executable=cache.check(proposal['analysis_executable']),required_meeteval_version='0.4.3',separate_root_execution_review_required=True,models_started=0));return ref

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True);a=sub.add_parser('prepare');a.add_argument('--output',type=Path,required=True);b=sub.add_parser('build');b.add_argument('--admission',type=Path,required=True);b.add_argument('--sha256',required=True);a=p.parse_args();print(json.dumps(prepare(a.output) if a.action=='prepare' else build(a.admission,a.sha256)))
