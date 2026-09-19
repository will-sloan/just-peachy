"""Fresh N6g C12 metadata preparation and separate root-reviewed admission; README adjacent."""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
THREAD='01a0812d-3ff0-7ed0-a06c-4df61b62a459'
Q=R/'runner/beam_C_queue_proposed_v3'
PROTOCOL=G/'runner/beam_C_queue_proposed_v3'
STATE=PROTOCOL/'supervisor_state'
OLD_PROTOCOL=G/'runner/beam_C_queue_proposed_v2'
PINS={
 'parent_proposal':(R/'runner/beam_C_admission_preparation_v1/ADMISSION_PROPOSAL.json','3c431161614a02ca95eb4c47cfe0096d047a42767dd64f777270b98ff3ec81b1'),
 'parent_adoption':(R/'runner/beam_C_admission_preparation_v1/ROOT_SOURCE_ADOPTION.json','906e3db0d09d7f0fc9f30ace1957262e3dc542bf4a0ea39d7270ec2be4edb410'),
 'source_adoption':(R/'application/beam_C_source_origin_root_acceptance_v1/ROOT_SOURCE_ACCEPTANCE.json','cb312b7c2230dfb1d1a840b3a229d173f68bb9c9bb38093351914cf2f5c0694d'),
 'source_freeze':(R/'application/beam_C_source_origin_proposal_v2/SOURCE_FREEZE.json','921c43168eb15f574ec5801834b34501b1ea617d7e1453e854528b6ab998d355'),
 'independent_review':(R/'application/C12_source_origin_independent_v1/INDEPENDENT_REVIEW.json','7937ecf055e68b83617f7018f65d7d252989182c65ea7bc089162e02ecbd62d2'),
 'failure_closure':(R/'runner/beam_C_queue_proposed_v2/ROOT_FAILED_RUNTIME_CLOSURE.json','ec5ab2b05ee123a2fb73250013e44408b0be2e526ab615b8b7e35e4c5e918a6f'),
}
RUNNER_SHA='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4'
MANIFEST_SHA='ede8ac94cd707a785986ac3ca9664141b472ceb0c8db5e7218b38b6bb399a3ea'
HELPER_SHA='6de4c1433c1f529e3e62e7d0bc5d0e9739a1ba951f530598abefad8b4ed0d7b2'
H2_SCRIPT=SIM.parents[2]/'Software Validation from Datasets/Evaluation Tool/scripts/maintain_h2_storage.py'
CONTROL_MARKERS=('s6d_capture_owner','s6d_capture_supervisor_bridge','s6d_telemetry','run-s6d-telemetry.ps1','s6dqueuedtelemetry','xvf_host.exe','measurement_app','s6d_closed_telemetry_restore','s6d_readonly_state_recovery')

def require(ok,message):
    if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'),parse_constant=lambda _:require(False,'Nonfinite JSON'))
def bound(p):
    p=Path(p).resolve();before=p.stat();data=p.read_bytes();after=p.stat()
    require((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'Changed metadata during hash')
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def verify(b):
    require(bound(b['path'])==b,'Changed binding: '+b['path']);return read(b['path'])
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def encoded(v):return (json.dumps(v,indent=2,allow_nan=False)+'\n').encode('utf-8')
def save(p,v):
    with Path(p).open('xb') as f:f.write(encoded(v));f.flush();os.fsync(f.fileno())
    return bound(p)
def dedup(bindings):
    out={}
    for b in bindings:
        path=str(Path(b['path']).resolve())
        require(path not in out or out[path]==b,'Conflicting source binding')
        out[path]=b
    return list(out.values())

def transform(oldq,oldapproval,oldm,newm,newref,newhelper,source_pairs,extra_guards):
    """Pure twelve-cell remap. No filesystem, source, process or model actions."""
    require(oldq['fixture_only'] is False and oldq['owner_thread_id']==oldq['owner_session_id']==THREAD,'Root nonfixture queue required')
    require(oldq['stage']=='C_collection' and len(oldq['jobs'])==len(oldm['jobs'])==len(newm['jobs'])==12,'Exact C12 population')
    require(oldq['runner_sha256']==RUNNER_SHA and oldq['payload_policy']['max_new_payload_bytes']==40*2**30,'V4/40 source contract')
    require(not oldapproval['approved_job_sha256'] and oldapproval['proposed_job_sha256']==[digest(j) for j in oldq['jobs']],'Original unapproved literals differ')
    require(newm['support']==oldm['support'] and newm['limits']==oldm['limits'] and newm['assets']==oldm['assets'],'Science/support/limits changed')
    require(newm['support']['evidence']['sha256']=='bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2','Strict bb1b required')
    mapping={oldq['manifest']['path']:newref,oldm['runner_helper']['path']:newhelper}
    mapping.update({x['original']['path']:x['copy'] for x in source_pairs})
    q=copy.deepcopy(oldq);q['manifest']=newref;q['status']='PROPOSED_N6G_C12_NOT_APPROVED'
    q['source_adoption_guards']=extra_guards
    for index,(jq,jo,jn) in enumerate(zip(q['jobs'],oldm['jobs'],newm['jobs'])):
        require(jq['job_id']==jo['job_id']==jn['job_id'],'Literal case ordering changed')
        require({k:v for k,v in jo.items() if k!='output'}=={k:v for k,v in jn.items() if k!='output'},'Scientific job changed')
        require(jn['stage']=='C_collection' and jn['mode']=='calibration_collection','C-only selectors-disabled mode required')
        require(jq['argv'][1]==oldm['runner_helper']['path'] and jq['argv'][2:]==['--manifest',oldq['manifest']['path'],'--manifest-sha256',oldq['manifest']['sha256'],'--job-id',jq['job_id']],'Original exact argv differs')
        jq['argv']=[jq['argv'][0],newhelper['path'],'--manifest',newref['path'],'--manifest-sha256',newref['sha256'],'--job-id',jq['job_id']]
        jq['cwd']=newm['source_root']
        for key in ('heartbeat_path','completion_path','stop_request_path'):
            require(Path(jq[key]).is_relative_to(OLD_PROTOCOL),'Original protocol path outside expected root')
            jq[key]=str(PROTOCOL/Path(jq[key]).relative_to(OLD_PROTOCOL))
        def replace(value):
            if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
            if isinstance(value,list):return [replace(x) for x in value]
            if isinstance(value,str):
                if value==oldq['manifest']['sha256']:return newref['sha256']
                if value==oldm['runner_helper']['sha256']:return newhelper['sha256']
                if value==jo['output'] or value.startswith(jo['output']+'\\'):return jn['output']+value[len(jo['output']):]
                old=str(OLD_PROTOCOL)
                if value==old or value.startswith(old+'\\'):return str(PROTOCOL)+value[len(old):]
            return value
        jq['expected_artifacts']=replace(jq['expected_artifacts'])
        jq['source_bindings']=dedup([mapping.get(b['path'],b) for b in jq['source_bindings']]+extra_guards)
        bypath={b['path']:b for b in jq['source_bindings']}
        require(all(bypath.get(b['path'])==b for b in [newref,newhelper,*newm['source_files'],*extra_guards]),'Actual adopted source graph missing')
        require(all(bypath.get(mapping[b['path']]['path'])==mapping[b['path']] if b['path'] in mapping else bypath.get(b['path'])==b for b in oldq['jobs'][index]['source_bindings']),'Original required guard lost')
        require(all(b['bytes']<=16*2**20 for b in bypath.values()) and sum(b['bytes'] for b in bypath.values())<=64*2**20,'Small source guard bounds')
    ap=copy.deepcopy(oldapproval);ap['queue_sha256']=None;ap['authorization_ref']=str(Q/'ROOT_ADMISSION.json')
    ap['allowed_working_directories']=[newm['source_root']];ap['proposed_job_sha256']=[digest(j) for j in q['jobs']];ap['approved_job_sha256']=[]
    ap['status']='UNAPPROVED_N6G_C12_ROOT_QUEUE_REVIEW_REQUIRED'
    return q,ap

def input_context():
    refs={};values={}
    for key,(path,sha) in PINS.items():
        b=bound(path);require(b['sha256']==sha,'Exact pinned '+key+' required');refs[key]=b;values[key]=verify(b)
    parent=values['parent_proposal'];adopt=values['source_adoption'];freeze=values['source_freeze'];review=values['independent_review']
    require(adopt['status']=='ROOT_ACCEPTED_C12_SOURCE_ORIGIN_REPAIR_ONLY' and adopt['run_id']=='20260913T195357Z' and adopt['owner_thread_id']==THREAD,'Root source adoption required')
    require(adopt['source_freeze']==refs['source_freeze'] and adopt['independent_review']==refs['independent_review'] and adopt['old_failure_runtime_closure']==refs['failure_closure'],'Actual root adoption joins differ')
    require(review['status']=='PASS_SOURCE_AND_FOCUSED_FIXTURES_ONLY' and review['source_freeze']==refs['source_freeze'] and review['findings']==[],'Independent repaired-source closure required')
    require(freeze['manifest']['sha256']==MANIFEST_SHA and freeze['runner']['sha256']==HELPER_SHA,'Exact N6g/manifest required')
    require(len(parent['bindings'])==24 and parent['collection_scope']['selectors_enabled'] is False and parent['collection_scope']['source_frames']==10597650,'Original collection authority/scope differs')
    for b in parent['bindings'].values():require(bound(b['path'])==b,'Original authority changed: '+b['path'])
    for row in freeze['source_files']:
        for b in row.values():require(bound(b['path'])==b,'Frozen producer source changed')
    oldq=verify(parent['bindings']['queue']);oldap=verify(parent['bindings']['approval_proposal']);oldm=verify(parent['bindings']['manifest']);newm=verify(freeze['manifest'])
    require(bound(freeze['runner']['path'])==freeze['runner'],'Frozen N6g changed')
    extras=[*refs.values(),bound(__file__),bound(Path(__file__).with_name('README_S6D_C12_ROOT_ADMIT_V2.md'))]
    q,ap=transform(oldq,oldap,oldm,newm,freeze['manifest'],freeze['runner'],freeze['source_files'],extras)
    return dict(refs=refs,values=values,parent=parent,freeze=freeze,old_queue=oldq,queue=q,approval=ap,manifest=newm,runner=parent['bindings']['runner'])

def fresh_outputs(context):
    require(not PROTOCOL.exists(),'Fresh protocol/state root required')
    for job in context['manifest']['jobs']:require(not Path(job['output']).exists(),'Fresh native output required: '+job['output'])
    for job in context['queue']['jobs']:
        for k in ('heartbeat_path','completion_path','stop_request_path'):require(not Path(job[k]).exists(),'Occupied protocol artifact')
        for a in job['expected_artifacts']:require(not Path(a['path']).exists(),'Occupied expected artifact')

def closure_decision(record,checkpoint,closure,lock):
    require(record['status']=='ROOT_C12_FAILED_RUNTIME_CLOSED_ZERO_ACCEPTED' and record['accepted']==0 and record['planned']==12 and record['original_failure_preserved'] is True,'Prior failure closure must retain zero credit')
    require(checkpoint['status']=='REVIEW_FAILURE' and checkpoint['completed']=={} and checkpoint['queue_sha256']=='cc6b61e6b002a499587dd9c32513b2066c650b6ffaab561c8faa28d84da23317','Exact failed old queue required')
    require(closure['result']['action']=='REVIEW_FAILURE' and closure['result']['done']==0 and closure['result']['total']==12,'Old closure population differs')
    require(closure['owner_lock']=='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' and closure['keep_awake']['restored'] is True and closure['payload_census_closure']['closed'] is True and closure['hardware_restoration_unresolved'] is False,'Prior owner/keep-awake/census not closed')
    require(lock['pid']==634952 and lock['creation_time']==1789417586.000414 and checkpoint['active']['pid']==627564 and checkpoint['active']['creation_time']==1789417617.482576,'Exact historical instances required')
    return [dict(pid=lock['pid'],creation_time=lock['creation_time']),dict(pid=checkpoint['active']['pid'],creation_time=checkpoint['active']['creation_time'])]

def allocation_decision(snapshot,current,known):
    require(snapshot.get('complete') is True and snapshot.get('errors')==[],'Complete current inventory required')
    seen=set();retained=[]
    for row in snapshot['rows']:
        pid=row.get('pid');require(type(pid) is int and pid>=0 and pid not in seen,'Invalid/duplicate PID');seen.add(pid)
        name=str(row.get('name') or '').casefold();argv=row.get('argv');creation=row.get('creation_time')
        finite=type(creation) in (int,float) and math.isfinite(creation) and creation>0
        if pid==current['pid']:
            require(finite and abs(creation-current['creation_time'])<.02,'Current metadata PID reused');continue
        for old in known:
            if pid==old['pid']:require(finite and abs(creation-old['creation_time'])>=.02,'Original C12 instance still alive or unreadable')
        critical=name.removesuffix('.exe').startswith(('python','powershell','pwsh','cmd','dotnet','xvf_host'))
        if critical:require(isinstance(argv,list) and argv and all(isinstance(x,str) for x in argv) and finite,'Unreadable interpreter/control process')
        text=' '.join(argv).casefold() if isinstance(argv,list) and all(isinstance(x,str) for x in argv) else ''
        require(name!='xvf_host.exe' and not any(x in text for x in CONTROL_MARKERS),'Physical/control process overlap forbidden')
        if 'python' in name:
            script_args=[x for x in argv[1:] if not x.startswith('-')]
            require(script_args and str(Path(script_args[0]).resolve()).casefold()==str(H2_SCRIPT.resolve()).casefold(),'Other Python/NN/supervisor workload forbidden')
            retained.append(row)
    require(current['pid'] in seen,'Current process absent from complete inventory')
    return dict(status='ONE_C12_SLOT_NO_OTHER_NN_OR_PHYSICAL_CONTROL_PROCESS',known_instances_absent=True,retained_unrelated_H2=retained,physical_supervisor_overlap=False)

def runtime_snapshot():
    import psutil
    rows=[];errors=[]
    for p in psutil.process_iter():
        try:
            info=p.as_dict(attrs=['pid','name','cmdline','create_time'],ad_value=None)
            rows.append(dict(pid=info['pid'],name=info['name'],argv=info['cmdline'],creation_time=info['create_time']))
        except psutil.NoSuchProcess:continue
        except BaseException as e:errors.append(repr(e))
    current=dict(pid=os.getpid(),creation_time=psutil.Process().create_time())
    return dict(complete=not errors,errors=errors,rows=rows,utc=dt.datetime.now(dt.timezone.utc).isoformat()),current

def preparation_record(c,qb,ab):
    return dict(schema='s6d-C12-N6g-preparation.v1',status='PREPARED_NOT_ADMITTED',inputs=c['refs'],queue=qb,approval_proposal=ab,runner=c['runner'],
                manifest=c['freeze']['manifest'],native_helper=c['freeze']['runner'],state_dir=str(STATE),protocol_root=str(PROTOCOL),
                original24_authorities=c['parent']['bindings'],scope=c['parent']['collection_scope'],unchanged_limits=c['parent']['unchanged_limits'],
                completion_gates=c['parent']['collection_completion_gates'],literal_job_hashes=c['approval']['proposed_job_sha256'],
                source=bound(__file__),readme=bound(Path(__file__).with_name('README_S6D_C12_ROOT_ADMIT_V2.md')),
                old_failed_jobs_accepted=0,maximum_NN_stacks=1,physical_supervisor_overlap=False,actual_approval_created=False,models_or_process_device_queries=0)

def prepare():
    require(not Q.exists(),'Fresh preparation directory required')
    c=input_context();fresh_outputs(c);Q.mkdir(parents=True)
    qb=save(Q/'QUEUE.json',c['queue']);c['approval']['queue_sha256']=qb['sha256'];ab=save(Q/'APPROVAL_PROPOSAL.json',c['approval'])
    result=preparation_record(c,qb,ab)
    rb=save(Q/'PREPARATION.json',result);print(json.dumps(dict(status=result['status'],preparation=rb,queue=qb,approval_proposal=ab)))

def admit(review_path,review_sha):
    require(review_path and review_sha,'Exact separate root queue review required')
    c=input_context();fresh_outputs(c)
    require(not any((Q/x).exists() for x in ('APPROVAL.json','ROOT_ADMISSION.json','ADMISSION_PREFLIGHT.json')),'Fresh actual authority paths required')
    prepref=bound(Q/'PREPARATION.json');prep=verify(prepref);qb=bound(Q/'QUEUE.json');q=verify(qb);ap=verify(prep['approval_proposal'])
    require(prep==preparation_record(c,qb,prep['approval_proposal']) and q==c['queue'],'Prepared source/literals/scope/limits/gates changed')
    expected=copy.deepcopy(c['approval']);expected['queue_sha256']=qb['sha256'];require(ap==expected,'Prepared approval changed')
    rr=bound(review_path);require(rr['sha256']==review_sha,'Root exact queue-review hash required');review=verify(rr)
    require(review.get('status')=='ROOT_ACCEPTED_EXACT_N6G_C12_QUEUE_FOR_ADMISSION' and review.get('owner_thread_id')==THREAD and review.get('run_id')=='20260913T195357Z','Exact root queue authority required')
    require(review.get('preparation')==prepref and review.get('queue')==qb and review.get('source_adoption')==c['refs']['source_adoption'] and review.get('prior_runtime_closure')==c['refs']['failure_closure'],'Root queue/source/closure bindings differ')
    require(review.get('allow_admission') is True and review.get('physical_supervisor_overlap') is False,'No-overlap root admission required')
    record=c['values']['failure_closure'];known=closure_decision(record,verify(record['checkpoint']),verify(record['supervisor_closure']),verify(record['closed_lock']))
    require(not (OLD_PROTOCOL/'supervisor_state/SUPERVISOR_LOCK.json').exists(),'Old C12 lock remains')
    snapshot,current=runtime_snapshot();allocation=allocation_decision(snapshot,current,known)
    now=dt.datetime.now(dt.timezone.utc);require(now<dt.datetime(2026,9,16,19,8,57,tzinfo=dt.timezone.utc),'Original closeout deadline reached')
    disks={drive:shutil.disk_usage(drive).free for drive in ('C:/','G:/')};require(disks['C:/']>=50*2**30 and disks['G:/']>=75*2**30,'Original disk floors')
    for job in q['jobs']:
        for b in job['source_bindings']:require(bound(b['path'])==b,'Adopted per-job guard changed')
    actual=copy.deepcopy(ap);actual['approved_job_sha256']=[digest(j) for j in q['jobs']];actual['status']='ROOT_APPROVED_EXACT_N6G_C12_CALIBRATION_COLLECTION'
    spec=importlib.util.spec_from_file_location('C12_N6g_admission_runner',c['runner']['path']);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    runner.validate_queue(q,actual,qb['sha256'])
    # All semantic/closure/process/resource checks precede any effective approval write.
    audit=save(Q/'ADMISSION_PREFLIGHT.json',dict(status='ROOT_C12_ADMISSION_PREFLIGHT_PASSED',root_review=rr,snapshot=snapshot,current=current,allocation=allocation,free_bytes=disks,utc=now.isoformat()))
    approval_bytes=encoded(actual)
    approval_binding=dict(path=str((Q/'APPROVAL.json').resolve()),bytes=len(approval_bytes),sha256=hashlib.sha256(approval_bytes).hexdigest())
    admission=dict(schema='s6d-C12-root-admission.v2',status='ROOT_ADMITTED_N6G_C12_PENDING_SUPERVISOR_PREFLIGHT',run_id=q['run_id'],owner_thread_id=THREAD,utc=now.isoformat(),
                   root_review=rr,preparation=prepref,queue=qb,approval=approval_binding,source_adoption=c['refs']['source_adoption'],prior_failed_runtime_closure=c['refs']['failure_closure'],
                   runner=c['runner'],state_dir=str(STATE),scope=prep['scope'],limits=prep['unchanged_limits'],completion_gates=prep['completion_gates'],
                   admission_preflight=audit,allocation=allocation,maximum_NN_stacks=1,physical_supervisor_overlap=False,
                   runtime_limit='Current no-overlap is checked here. Root must withhold physical/other NN launches for the entire C12 allocation; no new cross-supervisor mutex or automatic termination is claimed. Unchanged V4 per-job source/census/resource/deadline gates remain mandatory.',
                   source=bound(__file__),actual_model_launches=0,hardware_actions=0)
    admitted=save(Q/'ROOT_ADMISSION.json',admission)
    approved=save(Q/'APPROVAL.json',actual)
    require(approved==approval_binding,'Final approval bytes differ')
    print(json.dumps(dict(status=admission['status'],admission=admitted,approval=approved,jobs=12)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',action='store_true');mode.add_argument('--admit',action='store_true')
    p.add_argument('--root-queue-review');p.add_argument('--root-queue-review-sha256');a=p.parse_args()
    if a.prepare:prepare()
    else:admit(a.root_queue_review,a.root_queue_review_sha256)
