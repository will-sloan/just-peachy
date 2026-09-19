"""Mechanical admission for the existing Tk8 then HOST2 queues; see README."""
from pathlib import Path
import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
P=R/'runner/native_execution_queue_preparation_v1'
THREAD='01a0812d-3ff0-7ed0-a06c-4df61b62a459'
GROUPS={'tk8':('8c2a94ec8f2b1b244ed06c9c3d5676d1f1977282de0e619e822233284c07a971','1866e5b6bee4a3e73fc54a501b1bf976e60ebc07a03bcc0ca5440443034406a1',8),
        'host2':('366d5586d2c70c97f299c09d8b3d660d6db05b303440ec2d0effffb862493e75','6031c55b26df7a6f567a6c68fd71ccd294ad810e79ea7c6c37f54708d6ac2510',2)}
ALLOC=SIM/'scripts/s6d_C12_root_admit_v2.py'
ALLOC_SHA='6730ecf67f287dd972ac8c8b793b4899950800d892eadbb8f893b464438a9f14'
RUNNER=R/'runner/source_epoch_census_v4/s6d_runner_v1.py'
RUNNER_SHA='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4'
CREDITS=R/'application/native68_root_acceptance_v1/ROOT_RETENTION_AND_68_CREDITS.json'
CREDITS_SHA='7c3978631b0bb1f3d8c666e5b76dc0bfde0571e26c19f75ebea00276fca4bb60'
C12=R/'runner/beam_C_queue_proposed_v4/ROOT_ALL12_ACCEPTANCE.json'
C12_SHA='6d02b3fdd9c27bfe4b2372478176de17cd99c9f32c17885c26f1c2cc65119725'
BANK=R/'runner/bank_queue_v6/QUEUE.json'
BANK_SHA='351a8e529947aa9eca44f7fd90347d05e815e39e91b4ad1d39feaa90a384d75f'

def need(ok,message):
    if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'),parse_constant=lambda _:need(False,'Nonfinite JSON'))
def bound(p):
    p=Path(p).resolve();a=p.stat();raw=p.read_bytes();b=p.stat()
    need((a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns),'Changed metadata while reading')
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def verified(b):need(bound(b['path'])==b,'Changed bound metadata');return read(b['path'])
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def encoded(v):return (json.dumps(v,indent=2,allow_nan=False)+'\n').encode()
def save(p,v):
    with Path(p).open('xb') as f:f.write(encoded(v));f.flush();os.fsync(f.fileno())
    return bound(p)
def module(path,sha,name):
    need(bound(path)['sha256']==sha,'Changed reviewed dependency')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def context(group):
    need(group in GROUPS,'Only existing Tk8/HOST2 groups')
    qp,ap=P/group/'QUEUE.json',P/group/'APPROVAL_PROPOSAL.json';qb,ab=bound(qp),bound(ap)
    need((qb['sha256'],ab['sha256'])==GROUPS[group][:2],'Exact original queue/proposal required')
    q,a=read(qp),read(ap)
    need(q['owner_thread_id']==q['owner_session_id']==THREAD and q['fixture_only'] is False,'Original root-owned queue required')
    need(len(q['jobs'])==GROUPS[group][2] and len({j['job_id'] for j in q['jobs']})==GROUPS[group][2],'Exact group population required')
    need(a['approved_job_sha256']==[] and a['proposed_job_sha256']==[digest(j) for j in q['jobs']],'Original unapproved literals differ')
    need(q['runner_sha256']==RUNNER_SHA and q['payload_policy']['max_new_payload_bytes']==40*2**30,'Original V4/40 required')
    need(bound(RUNNER)['sha256']==RUNNER_SHA and bound(ALLOC)['sha256']==ALLOC_SHA,'Reviewed source dependency changed')
    need(bound(CREDITS)['sha256']==CREDITS_SHA,'Existing accepted176/68 authority changed')
    source_guards={}
    manifests={}
    for j in q['jobs']:
        for b in j['source_bindings']:
            need(b['bytes']<=16*2**20,'Only small source guards admitted here')
            need(b['path'] not in source_guards or source_guards[b['path']]==b,'Conflicting source guard')
            source_guards[b['path']]=b
        argv=j['argv'];mp=Path(argv[argv.index('--manifest')+1]);mb=bound(mp)
        need(mb['sha256']==argv[argv.index('--manifest-sha256')+1],'Manifest argv binding changed')
        m=read(mp);matches=[x for x in m['jobs'] if x['job_id']==argv[argv.index('--native-job-id')+1]]
        need(len(matches)==1 and matches[0]['job_id']==j['job_id'],'Literal native job binding differs')
        need(m['limits']['cpu_affinity']==[12,13,14,15] and m['limits']['cpu_threads_each']==1 and m['limits']['max_new_payload_gib']==40,'Original allocation differs')
        manifests[str(mp)]=(mb,m)
    for b in source_guards.values():need(bound(b['path'])==b,'Original per-job source guard changed')
    need(sum(b['bytes'] for b in source_guards.values())<=64*2**20,'Bounded source graph required')
    need(bound(C12)['sha256']==C12_SHA and bound(BANK)['sha256']==BANK_SHA,'Exact C12 closure/bank queue changed')
    return dict(group=group,queue=qb,approval_proposal=ab,q=q,a=a,manifests=manifests,runner=bound(RUNNER),allocation_source=bound(ALLOC),credits=bound(CREDITS),C12=bound(C12),physical_bank=bound(BANK),source=bound(__file__),readme=bound(Path(__file__).with_name('README_S6D_TK_HOST_ADMIT_V2.md')))

def plan(c):
    return dict(schema='s6d-tk-host-group-admission-plan.v1',status='PROPOSED_NOT_ADMITTED',group=c['group'],queue=c['queue'],approval_proposal=c['approval_proposal'],runner=c['runner'],allocation_source=c['allocation_source'],native176_68_acceptance=c['credits'],source=c['source'],readme=c['readme'],
        C12_acceptance=c['C12'],physical_bank_queue=c['physical_bank'],job_count=GROUPS[c['group']][2],state_dir=str(Path('G:/Just_Peachy_S6D/20260913T195357Z/runner/native_execution_queue_preparation_v1')/(c['group']+'_state')),
        source_manifests=[x[0] for x in c['manifests'].values()],sequence=['C12 runtime closure','physical bank whole54 FINISH and owner closure','tk8','Tk8 full-source/UI/owner closure','host2','HOST2 full-source/correctness/owner closure'],
        maximum_NN_stacks=1,physical_supervisor_overlap=False,affinity=[12,13,14,15],threads_each=1,payload_cap_bytes=40*2**30,
        no_80GiB_exception=True,root_proof_required='Exact root-reviewed completed C12 and whole54 physical bank FINISH/checkpoint/immutable-owner/census/keep-awake acceptance; HOST additionally exact root-reviewed Tk8 whole-source/UI/owner acceptance. No partial/stopped bank closure is sufficient.',
        actual_approval_created=False,models_or_device_calls=0)

def closed_instances(doc,expected=None):
    rows=doc.get('closed_instances');need(isinstance(rows,list) and rows,'Explicit closed process identities required')
    if expected is not None:need(len(rows)==expected,'Wrong closed identity population')
    keys=[]
    for row in rows:
        need(type(row.get('pid')) is int and row['pid']>0 and type(row.get('creation_time')) in (int,float) and math.isfinite(row['creation_time']) and row['creation_time']>0,'Invalid closed identity')
        keys.append((row['pid'],row['creation_time']))
    need(len(keys)==len(set(keys)),'Duplicate closed identity')
    return rows

def phase_closure(phase,expected_ids=None):
    cp=verified(phase['checkpoint']);cl=verified(phase['supervisor_closure']);queue=verified(phase['queue'])
    need(cp.get('run_id')==cl.get('run_id')=='20260913T195357Z','Foreign phase run')
    need(Path(phase['checkpoint']['path']).parent==Path(phase['state_dir']) and Path(phase['supervisor_closure']['path']).parent==Path(phase['state_dir']),'Foreign phase state')
    ids=[j['job_id'] for j in queue['jobs']]
    need(len(ids)==len(set(ids)) and cp.get('queue_sha256')==phase['queue']['sha256'],'Phase queue binding differs')
    if expected_ids is not None:need(ids==expected_ids,'Wrong predecessor queue/order')
    need(cp.get('status')=='FINISH' and cp.get('active') is None and set(cp.get('completed',{}))==set(ids),'Whole predecessor FINISH required')
    for jid,row in cp['completed'].items():
        need(row.get('exit_code')==0 and row.get('status')=='DECLARED_ARTIFACTS_VERIFIED' and row['identity']['job_id']==jid,'Unaccepted predecessor job')
    result=cl.get('result',{});census=cl.get('payload_census_closure',{})
    need(result.get('action')=='FINISH' and result.get('done')==result.get('total')==len(ids),'Closed FINISH population differs')
    need(cl.get('owner_lock')=='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' and cl.get('keep_awake',{}).get('restored') is True and cl.get('hardware_restoration_unresolved') is False,'Owner/keep-awake closure absent')
    need(census.get('closed') is True and census.get('snapshot',{}).get('running') is False and census['snapshot'].get('error') is None and census['snapshot'].get('violation_latched') is False,'Census closure absent')
    return cp

BANK_FINISH_STATUS='ROOT_ACCEPTED_PHYSICAL_BANK_V6_FULL54_AND_OWNER_CLOSURE'
BANK_STATE=Path('G:/Just_Peachy_S6D/20260913T195357Z/runner/bank_queue_v6/supervisor_state')

def physical_bank_closure(proof,c):
    """Require all54 exact bank jobs and their closed V4 phase, not a paused owner snapshot."""
    need(proof.get('expected_status')==BANK_FINISH_STATUS,'Explicit whole54 bank acceptance status required')
    bank=verified(proof['binding']);queue=verified(c['physical_bank'])
    need(bank.get('status')==BANK_FINISH_STATUS and bank.get('owner_thread_id')==THREAD and bank.get('run_id')=='20260913T195357Z','Actual whole54 root bank acceptance required')
    need(bank.get('queue')==c['physical_bank'] and bank.get('accepted')==bank.get('planned')==54 and bank.get('all_owners_closed') is True,'All54 bank stages and owners must be accepted')
    need(c['physical_bank']['sha256']==BANK_SHA and queue.get('schema')=='s6d_approved_job_queue_v1' and queue.get('run_id')=='20260913T195357Z' and queue.get('owner_thread_id')==queue.get('owner_session_id')==THREAD and queue.get('runner_sha256')==RUNNER_SHA,'Exact root-owned V4 physical bank queue required')
    ids=[j['job_id'] for j in queue['jobs']]
    need(len(ids)==len(set(ids))==54 and all(j.get('kind')=='hardware' for j in queue['jobs']),'Exact54 physical bank jobs required')
    phase=bank['phase_closure'];state=BANK_STATE
    need(phase.get('queue')==c['physical_bank'] and Path(phase.get('state_dir',''))==state and Path(phase['checkpoint']['path'])==state/'CHECKPOINT.json','Canonical complete bank phase required')
    cp=phase_closure(phase,ids)
    cl=verified(phase['supervisor_closure']);lock=verified(phase['closed_owner_lock'])
    nonce=lock.get('owner_nonce')
    need(isinstance(nonce,str) and len(nonce)==32 and all(ch in '0123456789abcdef' for ch in nonce),'Exact immutable owner nonce required')
    need(Path(phase['closed_owner_lock']['path'])==state/('CLOSED_LOCK_'+nonce+'.json') and Path(phase['supervisor_closure']['path'])==state/('SUPERVISOR_CLOSURE_'+nonce+'.json'),'Supervisor and immutable closed owner receipt differ')
    need(lock.get('run_id')=='20260913T195357Z' and lock.get('queue_sha256')==c['physical_bank']['sha256'] and not lock.get('unresolved_hardware'),'Closed bank owner belongs to another run/queue or is unresolved')
    owner=closed_instances({'closed_instances':[lock]},1)[0]
    need(cl.get('result',{}).get('run_id')=='20260913T195357Z' and cl['result'].get('checkpoint_path')==phase['checkpoint']['path'] and cl['result'].get('job_id') is None,'Final supervisor result does not bind the complete bank phase')
    awake=cl['keep_awake'];need(awake.get('requested') is True and awake.get('owned') is True and awake.get('restored') is True and awake.get('status')=='RESTORED','Bank keep-awake ownership must be fully restored')
    census=cl['payload_census_closure']['snapshot']
    need(census.get('has_complete') is True and census.get('stale') is False and census.get('pending') is False and census.get('logical_roots')==queue['payload_policy']['new_payload_roots'],'Complete closed bank census for all original roots required')
    need(queue['payload_policy']['max_new_payload_bytes']==40*2**30 and type(census.get('accounted_bytes')) is int and 0<=census['accounted_bytes']<=40*2**30,'Original physical shared40GiB cap required')
    children=[]
    for jid in ids:
        identity=cp['completed'][jid]['identity']
        need(identity.get('run_id')=='20260913T195357Z' and identity.get('job_id')==jid,'Foreign completed bank child identity')
        children.append(identity)
    closed_instances({'closed_instances':children},54)
    owners=closed_instances(bank)
    closed_keys={(x['pid'],x['creation_time']) for x in owners}
    required_keys={(x['pid'],x['creation_time']) for x in children+[owner]}
    need(len(required_keys)==55 and required_keys<=closed_keys,'Root closure omits a completed bank child or final supervisor')
    return owners

def review_gate(review,c):
    need(review.get('status')=='ROOT_ACCEPTED_EXACT_TK_HOST_GROUP_FOR_ADMISSION' and review.get('owner_thread_id')==THREAD and review.get('run_id')=='20260913T195357Z','Separate actual root queue review required')
    need(review.get('plan')==plan(c),'Root review does not bind exact prepared group/source/allocation')
    need(review.get('allow_admission') is True and review.get('maximum_NN_stacks')==1 and review.get('physical_supervisor_overlap') is False,'Explicit serial no-physical-overlap allocation required')
    proofs=review.get('prerequisite_acceptances',{})
    need(set(proofs)==({'C12','PhysicalBank'} if c['group']=='tk8' else {'C12','PhysicalBank','Tk8'}),'Exact predecessor acceptance set required')
    need(proofs['C12']==c['C12'],'Only exact actual C12 acceptance allowed')
    doc=verified(proofs['C12'])
    need(doc.get('status')=='ROOT_ACCEPTED_C12_ALL12_COLLECTION' and doc.get('owner_thread_id')==THREAD and doc.get('run_id')=='20260913T195357Z','Wrong C12 authority')
    need(doc.get('accepted')==doc.get('planned')==12 and doc.get('old_failure_credit')==0 and doc.get('all_owners_closed') is True,'Incomplete C12 acceptance')
    need(len(doc['phase_closures'])==2,'Both C12 phases required')
    for phase in doc['phase_closures']:phase_closure(phase)
    known=closed_instances(doc,14)
    known=known+physical_bank_closure(proofs['PhysicalBank'],c)
    if c['group']=='host2':
        tk=verified(proofs['Tk8']);tq=bound(P/'tk8/QUEUE.json')
        need(tk.get('status')=='ROOT_ACCEPTED_TK8_FULL_SOURCE_UI_AND_OWNER_CLOSURE' and tk.get('owner_thread_id')==THREAD and tk.get('run_id')=='20260913T195357Z','Actual root Tk8 acceptance required')
        need(tk.get('queue')==tq and tk.get('accepted')==tk.get('planned')==8 and tk.get('all_owners_closed') is True and tk.get('full_source_evidence_validated') is True and tk.get('all_declared_Tk_view_evidence_validated') is True,'Complete Tk8 source/UI/owner evidence required')
        need(tk['phase_closure']['queue']==tq,'Tk8 phase queue differs');phase_closure(tk['phase_closure'],[j['job_id'] for j in read(tq['path'])['jobs']])
        known=known+closed_instances(tk,9)
    return proofs,known

def fresh(c):
    root=P/c['group']
    need(not any((root/n).exists() for n in ['ROOT_ADMISSION.json','APPROVAL.json','ADMISSION_PREFLIGHT.json']),'Fresh authority paths required')
    need(not Path(plan(c)['state_dir']).exists(),'Fresh supervisor state required')
    for j in c['q']['jobs']:
        for k in ('heartbeat_path','completion_path','stop_request_path'):need(not Path(j[k]).exists(),'Existing protocol artifact')
        for a in j['expected_artifacts']:need(not Path(a['path']).exists(),'Existing native artifact')
    for _,m in c['manifests'].values():
        for j in m['jobs']:need(not Path(j['output']).exists(),'Fresh native output required')

def admit(group,review_path,review_sha):
    c=context(group);rr=bound(review_path);need(rr['sha256']==review_sha,'Exact root-review SHA required')
    review=verified(rr);proofs,known=review_gate(review,c);fresh(c)
    alloc=module(ALLOC,ALLOC_SHA,'tk_host_reviewed_allocation');snapshot,current=alloc.runtime_snapshot()
    allocation=alloc.allocation_decision(snapshot,current,known)
    now=dt.datetime.now(dt.timezone.utc)
    need(now<dt.datetime(2026,9,16,19,8,57,tzinfo=dt.timezone.utc),'Original work deadline/reserve reached')
    disks={drive:shutil.disk_usage(drive).free for drive in ('C:/','G:/')}
    need(disks['C:/']>=50*2**30 and disks['G:/']>=75*2**30,'Original disk floors')
    a=copy.deepcopy(c['a']);a['approved_job_sha256']=[digest(j) for j in c['q']['jobs']];a['approval_state']='ROOT_APPROVED_EXACT_'+group.upper()
    runner=module(RUNNER,RUNNER_SHA,'tk_host_reviewed_runner');runner.validate_queue(c['q'],a,c['queue']['sha256'])
    root=P/group
    audit=save(root/'ADMISSION_PREFLIGHT.json',dict(status='ROOT_TK_HOST_ADMISSION_PREFLIGHT_PASSED',root_review=rr,allocation=allocation,snapshot=snapshot,current=current,free_bytes=disks,utc=now.isoformat(),payload_census='Fresh exact V4 supervisor preflight remains mandatory before first model.'))
    ab=dict(path=str((root/'APPROVAL.json').resolve()),bytes=len(encoded(a)),sha256=hashlib.sha256(encoded(a)).hexdigest())
    admission=dict(schema='s6d-tk-host-root-admission.v1',status='ROOT_ADMITTED_'+group.upper()+'_PENDING_SUPERVISOR_PREFLIGHT',group=group,run_id='20260913T195357Z',owner_thread_id=THREAD,root_review=rr,plan=plan(c),queue=c['queue'],approval=ab,runner=c['runner'],prerequisite_acceptances=proofs,admission_preflight=audit,state_dir=plan(c)['state_dir'],physical_supervisor_overlap=False,maximum_NN_stacks=1,
        allocation_obligation='Root must withhold physical and all other NN starts until this exact group full-source/UI where applicable and owner/census/keep-awake closure is accepted. No new shared mutex is claimed.')
    rb=save(root/'ROOT_ADMISSION.json',admission);need(save(root/'APPROVAL.json',a)==ab,'Final approval bytes differ')
    print(json.dumps(dict(status=admission['status'],admission=rb,approval=ab)))

def prepare(directory):
    need(not directory.exists(),'Fresh metadata-only proposal directory required')
    plans={g:plan(context(g)) for g in GROUPS}
    directory.mkdir(parents=True)
    for group,p in plans.items():
        save(directory/(group.upper()+'_PLAN.json'),p)
        proofs=dict(C12=p['C12_acceptance'],PhysicalBank=dict(binding=None,expected_status=BANK_FINISH_STATUS))
        if group=='host2':proofs['Tk8']=None
        save(directory/(group.upper()+'_ROOT_REVIEW_PROPOSAL.json'),dict(status='PROPOSED_NOT_ROOT_AUTHORITY',run_id='20260913T195357Z',owner_thread_id=THREAD,plan=p,allow_admission=False,maximum_NN_stacks=1,physical_supervisor_overlap=False,prerequisite_acceptances=proofs))
    print(json.dumps(dict(status='PROPOSALS_ONLY',directory=str(directory),groups=list(plans),actual_approvals=0)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True);m.add_argument('--prepare',type=Path);m.add_argument('--admit',choices=tuple(GROUPS));p.add_argument('--root-review',type=Path);p.add_argument('--root-review-sha256');a=p.parse_args()
    if a.prepare:prepare(a.prepare)
    else:
        need(a.root_review is not None and a.root_review_sha256,'Root review path/SHA required');admit(a.admit,a.root_review,a.root_review_sha256)
