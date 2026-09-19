"""Root admission of the frozen twelve calibration collection jobs; see README."""
import copy, datetime as dt, hashlib, importlib.util, json, shutil
from pathlib import Path
import psutil

SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
P = R / 'runner/beam_C_admission_preparation_v1'
Q = R / 'runner/beam_C_queue_proposed_v2'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def require(ok, message):
    if not ok: raise ValueError(message)
def bound(p, sha=None):
    p = Path(p); data = p.read_bytes(); digest = hashlib.sha256(data).hexdigest()
    require(sha is None or sha == digest, 'Changed binding: ' + str(p))
    return dict(path=str(p), bytes=len(data), sha256=digest)
def verify(b):
    got=bound(b['path'], b['sha256']); require(got['bytes']==b['bytes'], 'Size mismatch'); return got
def save(p, value):
    with Path(p).open('x', encoding='utf-8') as f: json.dump(value, f, indent=2, allow_nan=False); f.write('\n')

def main():
    proposal_binding=bound(P/'ADMISSION_PROPOSAL.json', '3c431161614a02ca95eb4c47cfe0096d047a42767dd64f777270b98ff3ec81b1')
    adoption=bound(P/'ROOT_SOURCE_ADOPTION.json', '906e3db0d09d7f0fc9f30ace1957262e3dc542bf4a0ea39d7270ec2be4edb410')
    proposal=read(proposal_binding['path']); bindings=proposal['bindings']
    require(len(bindings)==24, 'Exact source authority population')
    for b in bindings.values(): verify(b)
    queue=read(bindings['queue']['path']); approval=read(bindings['approval_proposal']['path'])
    require(queue['owner_thread_id']==queue['owner_session_id']=='01a0812d-3ff0-7ed0-a06c-4df61b62a459', 'Exact root owner')
    require(queue['fixture_only'] is False and len(queue['jobs'])==12, 'Actual twelve jobs')
    require(not approval['approved_job_sha256'], 'Proposal must remain unapproved')
    hashes=[hashlib.sha256(json.dumps(j, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() for j in queue['jobs']]
    require(hashes==approval['proposed_job_sha256']==proposal['future_authority']['proposed_job_sha256'], 'Exact twelve literal job digests')
    require(proposal['collection_scope']['selectors_enabled'] is False, 'Collection selectors disabled')
    require(proposal['collection_scope']['source_frames']==10597650, 'Exact source duration population')
    state=Path(proposal['future_authority']['supervisor_state_dir'])
    require(state==G/'runner/beam_C_queue_proposed_v2/supervisor_state' and not state.exists(), 'Fresh exact G state')
    for j in proposal['jobs']:
        for k in ('future_output','future_completion','future_feature_output'):
            require(not Path(j[k]).exists(), 'Previously occupied '+str(j[k]))
    for j in queue['jobs']:
        for k in ('heartbeat_path','completion_path','stop_request_path'):
            require(not Path(j[k]).exists(), 'Runtime path occupied')
        for a in j['expected_artifacts']: require(not Path(a['path']).exists(), 'Artifact path occupied')
    require(not any(Q.glob('ROOT_LAUNCH*.json')), 'Already launched')
    require(not (Q/'APPROVAL.json').exists() and not (Q/'ROOT_ADMISSION.json').exists(), 'Admission already exists')
    old_state=G/'runner/native_execution_queue_preparation_v1/native176_state'
    fresh_state=G/'runner/native176_recovery5_v1/supervisor_state'
    closure=bound(R/'runner/native176_recovery5_preparation_v1/ROOT_RUNTIME_CLOSURE_V1.json', '7547962d5a4e01c507cc65bed315d9fe9b802fba59e719f02771feeb60d36b6f')
    require(read(closure['path'])['status']=='ROOT_VERIFIED_RECOVERY5_RUNTIME_CLOSED_COMPOSITE_SCIENCE_PENDING', 'Fresh five runtime closure')
    old=read(old_state/'CHECKPOINT.json'); fresh=read(fresh_state/'CHECKPOINT.json')
    require(len(old['completed'])==171 and len(fresh['completed'])==5, 'Exact closed runtime populations')
    # Immutable closure receipts, not historical active checkpoint text, establish closure.
    for directory in (old_state,fresh_state):
        require(not (directory/'SUPERVISOR_LOCK.json').exists(), 'Runtime owner lock remains')
        require(len(list(directory.glob('SUPERVISOR_CLOSURE_*.json')))==1, 'Unique immutable closure required')
    now=dt.datetime.now(dt.timezone.utc)
    require(now < dt.datetime(2026,9,16,19,8,57,tzinfo=dt.timezone.utc), 'No new job after closeout boundary')
    processes=[]
    for p in psutil.process_iter(['pid','name','create_time']):
        if 'python' not in (p.info['name'] or '').lower(): continue
        try: command=p.cmdline()
        except psutil.NoSuchProcess: continue
        require(command, 'Unreadable Python command')
        text=' '.join(command)
        processes.append(dict(pid=p.pid,creation_time=p.info['create_time'],argv=command))
        # One current root metadata process and the known unrelated H2 maintenance service only.
        require(p.pid==psutil.Process().pid or 'maintain_h2_storage.py' in text, 'Other Python workload must be allocated before C12')
    disks={drive:shutil.disk_usage(drive).free for drive in ('C:/','G:/')}
    require(disks['C:/']>=50*1024**3 and disks['G:/']>=75*1024**3, 'Disk floors')
    approval=copy.deepcopy(approval); approval['approved_job_sha256']=list(hashes)
    approval['status']='ROOT_APPROVED_EXACT_C12_CALIBRATION_COLLECTION'
    spec=importlib.util.spec_from_file_location('s6d_C12_admit_runner',bindings['runner']['path']); runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    runner.validate_queue(queue,approval,bindings['queue']['sha256'])
    save(Q/'APPROVAL.json',approval)
    admission=dict(schema='s6d-C12-root-admission.v1',status='ROOT_ADMITTED_C12_COLLECTION_PENDING_SUPERVISOR_PREFLIGHT',utc=now.isoformat(),owner_thread_id=queue['owner_thread_id'],run_id=queue['run_id'],proposal=proposal_binding,source_adoption=adoption,bindings=bindings,queue=bindings['queue'],runner=bindings['runner'],approval=bound(Q/'APPROVAL.json'),state_dir=str(state),scope=proposal['collection_scope'],limits=proposal['unchanged_limits'],native176_runtime_closure=closure,scientific176_status='ALL176_COMPUTATIONS_AVAILABLE_COMPOSITE_VALIDATION_SCORING_PENDING',ownership_snapshot=processes,free_bytes=disks,allocation={'maximum_NN_stacks':1,'cpu_affinity':[12,13,14,15],'threads_each':1,'Tk_HOST_diagnostics_or_other_NN_overlap':False,'physical_bank_overlap':'Root may launch separately admitted bank_queue_v5 on its independent hardware owner; retain overlap condition in timing interpretation. No timing equivalence inferred.','non_NN_composite_validation_and_scoring':'Permitted; record concurrent file/cpu work.','fresh_payload_census':'Unchanged V4 supervisor must complete fresh census and resource checks before each child; last closed five census is supporting evidence only.'},completion_gates=proposal['collection_completion_gates'],source=bound(__file__))
    save(Q/'ROOT_ADMISSION.json',admission)
    print(json.dumps({'status':admission['status'],'admission':bound(Q/'ROOT_ADMISSION.json'),'approval':admission['approval'],'jobs':12}))

if __name__=='__main__': main()
