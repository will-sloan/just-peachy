"""Four held accuracy-worker partitions; see README_S6D_BEAM_PARALLEL_PREPARE_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import s6d_beam_native_run_v1 as N
import s6d_beam_execution_prepare_v1 as P

GLOBAL_SCOPE='At most4 total concurrent NN workers across all S6D accuracy queues, including full-bank confirmations and these beam queues. Root alone allocates slots. No overlap with admitted serial latency benchmarks. These concurrency timings are descriptive resource observations, not latency-benefit comparisons.'

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def partition(rows):
    N.need(rows and len({r['job_id'] for r in rows})==len(rows),'Unique nonempty exact original jobs required')
    groups=[rows[i::4] for i in range(4)]
    N.need(sorted(r['job_id'] for g in groups for r in g)==sorted(r['job_id'] for r in rows),'Partition changed jobs')
    return groups

def prepare(queue_path,queue_sha,plan_path,output):
    qb=N.bind(queue_path);N.need(qb['sha256']==queue_sha,'Exact held queue differs');q=N.verified(qb)
    parent_approval=N.verified(N.bind(Path(queue_path).with_name('APPROVAL_PROPOSAL.json')))
    N.need(q.get('status')=='PROPOSED_NOT_APPROVED' and parent_approval.get('approved_job_sha256')==[] and parent_approval['queue_sha256']==qb['sha256'],'Unapproved exact parent proposal required')
    N.need(q['stage'] in ('C_collection','stream_diagnostics','main_core'),'Only declared accuracy stages supported')
    plan_ref=N.bind(plan_path);plan=N.verified(plan_ref);manifest=N.verified(q['manifest'])
    N.need(manifest['declaration']==plan_ref and manifest['stage']==q['stage'],'Queue/manifest/declaration differ')
    expected=[r['job_id'] for r in plan['tasks'] if r['stage']==q['stage']]
    N.need([j['job_id'] for j in q['jobs']]==expected==[j['job_id'] for j in manifest['jobs']],'Exact full stage order required')
    N.need(manifest['limits']['cpu_affinity']==[12,13,14,15] and manifest['limits']['cpu_threads_each']==1,'Unchanged accepted affinity/thread contract required')
    if q['stage']=='main_core':
        for j in manifest['jobs']:
            if j['mode']=='mono_asr_beam_identity':N.need(N.verified(N.verified(j['beam_settings'])['calibration']).get('status')=='ACCEPTED_C_ONLY','Actual C-only calibration prerequisite absent')
    out=Path(output).resolve();N.need(out.parent==P.R/'runner' and not out.exists(),'Fresh report runner proposal directory required')
    for j in q['jobs']:
        N.need(not Path(j['heartbeat_path']).exists() and not Path(j['completion_path']).exists(),'Parent execution already has output')
    for j in manifest['jobs']:N.need(not Path(j['output']).exists(),'Native result already exists; no duplicate coverage execution')
    out.mkdir();receipts=[];workers=partition(q['jobs']);original_jobs={j['job_id']:j for j in q['jobs']}
    for number,group in enumerate(workers,1):
        folder=out/f'worker{number:02d}';folder.mkdir();copy=deepcopy(q);copy.update(status='PROPOSED_NOT_APPROVED',parallel_execution_scope=GLOBAL_SCOPE,parallel_worker_index=number,parallel_worker_count=4,latency_comparison_admissible=False,parent_serial_queue=qb,jobs=[])
        for job in group:
            current=deepcopy(job);old=Path(job['completion_path']).parent;new=P.G/'runner'/out.name/f'worker{number:02d}'/job['job_id']
            N.need(not new.exists(),'Fresh independent protocol output required')
            for key in ('heartbeat_path','completion_path','stop_request_path'):current[key]=str(new/Path(current[key]).name)
            for artifact in current['expected_artifacts']:
                p=Path(artifact['path'])
                if p.parent==old:artifact['path']=str(new/p.name)
            copy['jobs'].append(current)
        N.save(folder/'QUEUE.json',copy);b=N.bind(folder/'QUEUE.json')
        proposal=deepcopy(parent_approval);proposal.update(queue_sha256=b['sha256'],authorization_ref=str(folder/'ROOT_ADMISSION.json'),approved_job_sha256=[],proposed_job_sha256=[digest(j) for j in copy['jobs']],status='UNAPPROVED_GLOBAL_ROOT_ALLOCATION_REQUIRED')
        N.save(folder/'APPROVAL_PROPOSAL.json',proposal)
        receipts.append(dict(worker=number,queue=b,approval_proposal=N.bind(folder/'APPROVAL_PROPOSAL.json'),job_count=len(group),job_ids=[j['job_id'] for j in group],state_dir=str(P.G/'runner'/out.name/f'worker{number:02d}'/'supervisor_state')))
    # This metadata describes exact future diagnostic membership before physical bank binding.
    declared=partition([r for r in plan['tasks'] if r['stage']=='stream_diagnostics'])
    N.save(out/'DIAGNOSTIC_528_WORKER_MEMBERSHIP.json',dict(status='EXACT_MEMBERSHIP_ONLY_CAPTURE_BINDING_REQUIRED',declaration=plan_ref,workers=[dict(worker=i+1,job_count=len(g),tasks=g) for i,g in enumerate(declared)],original_count=528,latency_comparison_admissible=False,global_scope=GLOBAL_SCOPE))
    helper_dir=out/'helpers';helper_dir.mkdir();helpers=[]
    for path in (Path(__file__),Path(__file__).with_name('README_S6D_BEAM_PARALLEL_PREPARE_V1.md'),Path(__file__).with_name('s6d_beam_parallel_checks_v1.py'),Path(N.__file__),Path(P.__file__),Path(__file__).with_name('README_S6D_BEAM_EXECUTION_V1.md')):
        shutil.copyfile(path,helper_dir/path.name);helpers.append(N.bind(helper_dir/path.name))
    N.save(out/'PARALLEL_PROPOSAL_RECEIPT.json',dict(status='FOUR_UNAPPROVED_ACCURACY_WORKER_QUEUES',source=N.bind(__file__),helpers=helpers,parent_queue=qb,manifest=q['manifest'],declaration=plan_ref,workers=receipts,partition_rule='Original literal stage order, round-robin index modulo4; each job exactly once, original order retained inside each worker.',original_job_count=len(q['jobs']),global_concurrent_NN_cap=4,global_scope=GLOBAL_SCOPE,unchanged_affinity=[12,13,14,15],inner_model_threads=1,original_source_pacing=True,models_started=0,mutual_exclusion='Root must choose parallel queues or parent serial queue, never both. Native outputs remain exact original manifest paths and must be fresh.',pending_diagnostic_membership=N.bind(out/'DIAGNOSTIC_528_WORKER_MEMBERSHIP.json')))
    print(json.dumps(N.bind(out/'PARALLEL_PROPOSAL_RECEIPT.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--queue-sha256',required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.queue,a.queue_sha256,a.plan,a.output)
