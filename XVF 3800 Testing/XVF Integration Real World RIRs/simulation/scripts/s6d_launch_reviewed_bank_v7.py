"""Launch reviewed V7 only after fresh allocation; see README_S6D_LAUNCH_REVIEWED_BANK_V7.md."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import shutil
import subprocess
import sys
import json
import s6d_launch_reviewed_bank_v6 as L
import s6d_bank_remaining_admit_v7 as V7

Q=L.R/'runner/bank_queue_v7'
STATE=L.G/'runner/bank_queue_v7/supervisor_state'
BASE_LAUNCH_SHA='b593140c3df56801529dae26100153df5a698959ffa0f9bce31a14761f085895'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for option in ('bank-admission','independent-review','c12-acceptance'):
        p.add_argument('--'+option,type=Path,required=True);p.add_argument('--'+option+'-sha256',required=True)
    a=p.parse_args()
    L.need(L.bound(L.__file__)['sha256']==BASE_LAUNCH_SHA,'Reviewed V6 launcher helpers changed')
    rr=L.bound(a.bank_admission);independent=L.bound(a.independent_review);c12ref=L.bound(a.c12_acceptance)
    L.need(rr['sha256']==a.bank_admission_sha256 and Path(rr['path'])==Q/'ROOT_QUEUE_REVIEW.json','Exact actual V7 admission path/SHA required')
    L.need(independent['sha256']==a.independent_review_sha256 and c12ref['sha256']==a.c12_acceptance_sha256,'Exact independent/C12 review hashes required')
    review=L.verify(rr);check=L.verify(independent);c12=L.verify(c12ref)
    L.need(review['status']=='ROOT_ADMITTED_BANK_V7_REMAINDER_PENDING_LAUNCH' and review['root_owner_thread_id']==V7.A.THREAD and review['run_id']=='20260913T195357Z','Actual root V7 admission required')
    L.need(check['status']=='PASS_INDEPENDENT_LITERAL_BANK_REVIEW' and check['root_receipt']==rr and check['queue']==review['queue'] and check['approval']==review['approval'],'Independent literal joins differ')
    freeze=L.verify(review['source_freeze'])
    for source in (Path(__file__),Path(V7.__file__)):
        L.need(L.bound(source) in freeze['files'],'Root-reviewed source freeze omits actual launcher/helper')
    c=V7.context(review['original_epoch_closure'])
    L.need(c12ref==L.bound(L.R/'runner/beam_C_queue_proposed_v4/ROOT_ALL12_ACCEPTANCE.json') and c12ref['sha256']=='6d02b3fdd9c27bfe4b2372478176de17cd99c9f32c17885c26f1c2cc65119725','Exact actual C12 acceptance required')
    L.need(c12['status']=='ROOT_ACCEPTED_C12_ALL12_COLLECTION' and c12['accepted']==c12['planned']==12 and c12['owner_thread_id']==V7.A.THREAD and c12['old_failure_credit']==0 and c12['all_owners_closed'] is True,'Complete C12 source/owner acceptance required')
    for phase in c12['phase_closures']:
        closure=L.verify(phase['supervisor_closure'])
        L.need(closure['result']['action']=='FINISH' and closure['owner_lock']=='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' and closure['keep_awake']['restored'] is True and closure['payload_census_closure']['closed'] is True,'C12 supervisor not closed')
        L.need(not(Path(phase['state_dir'])/'SUPERVISOR_LOCK.json').exists(),'C12 live lock remains')
    L.need(not(L.G/'runner/bank_queue_v6/supervisor_state/SUPERVISOR_LOCK.json').exists(),'Old physical supervisor live lock remains')
    allocation_source=L.SIM/'scripts/s6d_C12_root_admit_v2.py'
    L.need(L.bound(allocation_source)['sha256']=='6730ecf67f287dd972ac8c8b793b4899950800d892eadbb8f893b464438a9f14','Allocation source changed')
    allocation_helpers=L.load(allocation_source,'bankV7_launch_allocation')
    snapshot,current=allocation_helpers.runtime_snapshot()
    known=c12['closed_instances']+c['closure']['closed_instances']
    allocation=allocation_helpers.allocation_decision(snapshot,current,known)
    L.need(datetime.now(timezone.utc)<datetime(2026,9,16,19,8,57,tzinfo=timezone.utc),'Original work deadline/reserve')
    free={d:shutil.disk_usage(d).free for d in ('C:/','G:/')}
    L.need(free['C:/']>=50*2**30 and free['G:/']>=75*2**30,'Original disk floors')
    queue=L.verify(review['queue']);approval=L.verify(review['approval'])
    L.need(len(queue['jobs'])==54 and review['current_charged_attempts']==145 and review['new_attempts_admitted']==318 and review['total_forecast_attempts']==463 and review['total_forecast_charged_seconds']==21187.3213125,'Exact reviewed remainder population/charge required')
    L.need(queue['payload_policy']['max_new_payload_bytes']==40*2**30,'Physical40GiB cap unchanged')
    guards={}
    for job in queue['jobs']:
        for ref in job['source_bindings']:
            key=str(Path(ref['path']).resolve());L.need(key not in guards or guards[key]==ref,'Conflicting source guard');guards[key]=ref
    for ref in guards.values():L.need(L.bound(ref['path'])==ref,'Admitted source changed')
    L.need(L.bound(review['runner']['path'])==review['runner'] and review['runner']['sha256']==V7.RUNNER_SHA,'Frozen V4 supervisor required')
    runner=L.load(review['runner']['path'],'bankV7_exact_runner');runner.validate_queue(queue,approval,review['queue']['sha256'])
    L.need(not STATE.exists() and not(Q/'ROOT_LAUNCH.json').exists(),'Fresh launch state required')
    preflight=L.save(Q/'ROOT_LAUNCH_PREFLIGHT.json',dict(status='ROOT_PHYSICAL_BANKV7_LAUNCH_PREFLIGHT_PASS',utc=datetime.now(timezone.utc).isoformat(),bank_admission=rr,independent_review=independent,c12_acceptance=c12ref,original_epoch_closure=review['original_epoch_closure'],process_snapshot=snapshot,allocation=allocation,free_bytes=free,source_guards_verified=len(guards),initial_allocation='Hardware only; no other NN/device owner. Separate root admission required for later overlap.',forecast_attempts=463,forecast_charged_seconds=21187.3213125,launcher=L.bound(__file__),readme=L.bound(Path(__file__).with_name('README_S6D_LAUNCH_REVIEWED_BANK_V7.md'))))
    argv=[sys.executable,'-B',review['runner']['path'],'--queue',review['queue']['path'],'--approval',review['approval']['path'],'--queue-sha256',review['queue']['sha256'],'--approval-sha256',review['approval']['sha256'],'--state-dir',str(STATE),'--keep-awake']
    with(Q/'SUPERVISOR.stdout.log').open('xb') as out,(Q/'SUPERVISOR.stderr.log').open('xb') as err:
        child=subprocess.Popen(argv,cwd=L.SIM,stdin=subprocess.DEVNULL,stdout=out,stderr=err,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
    import psutil
    launched=L.save(Q/'ROOT_LAUNCH.json',dict(status='SUPERVISOR_LAUNCHED',utc=datetime.now(timezone.utc).isoformat(),pid=child.pid,creation_time=psutil.Process(child.pid).create_time(),argv=argv,cwd=str(L.SIM),preflight=preflight,queue=review['queue'],approval=review['approval'],state_dir=str(STATE),stages=54,future_attempts=318,completed_new_stages=0))
    print(json.dumps(dict(launch=launched,pid=child.pid,stages=54,future_attempts=318)))

if __name__=='__main__':main()
