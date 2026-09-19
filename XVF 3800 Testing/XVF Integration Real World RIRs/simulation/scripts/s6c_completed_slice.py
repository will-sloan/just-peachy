"""Publish whole predeclared candidate slices from durable native receipts. README_S6C_COMPLETED_SLICE.md."""
import argparse
import sys
from s6c_common import *

def publish(manifest_path,candidates,label):
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in label):raise ValueError('Simple label required')
    parent_binding=bind(manifest_path);parent=verified(parent_binding);spec=verified(parent['execution_manifest'])
    for b in spec['execution_files']+spec['assets']:bind(b['path'],b['sha256'])
    sys.path.insert(0,str(Path(spec['root'])/'scripts'))
    from s6c_execution import verify_job
    jobs=[j for j in parent['jobs'] if j['candidate_id'] in candidates]
    if {j['candidate_id'] for j in jobs}!=set(candidates):raise ValueError('Requested candidate is not in parent manifest')
    rows=[];missing=[]
    for job in jobs:
        row=verify_job(job)
        if not row:missing.append({k:job[k] for k in ('candidate_id','case_id','asr_tap','identity_tap')})
        else:rows.append(row)
    if missing:return dict(status='NOT_READY',requested=len(jobs),complete=len(rows),missing=len(missing),first_missing=missing[0])
    folder=REPORT/'completed_slices'/spec['epoch'];jobs_path=folder/(label+'_JOBS.json');result_path=folder/(label+'_RESULTS.json')
    sliced=dict(schema='jp_s6c_native_jobs.v1',status='REGISTERED_EXACT_JOBS',epoch=spec['epoch'],stage='COMPLETE_CANDIDATE_SLICE',
        requested=len(jobs),jobs=jobs,case_ids=sorted({j['case_id'] for j in jobs}),candidate_ids=sorted(candidates),
        profile_routes=[dict(candidate_id=c,stream=a,identity_tap=i) for c,a,i in sorted({(j['candidate_id'],j['asr_tap'],j['identity_tap']) for j in jobs})],
        execution_manifest=parent['execution_manifest'],parent_manifest=parent_binding,helper=bind(__file__),
        selection='Every predeclared job for requested candidates, both supported routes and all original panel cases; only completion timing, never prediction outcomes')
    save(jobs_path,sliced,immutable=True)
    result=dict(status='COMPLETE',requested=len(jobs),completed=len(rows),rows=rows,epoch=spec['epoch'],stage='COMPLETE_CANDIDATE_SLICE',
        jobs=bind(jobs_path),execution_manifest=parent['execution_manifest'],parent_manifest=parent_binding,helper=bind(__file__),
        reexecuted_native_jobs=0,scope='Durable worker receipts admitted independently of still-running parent coordinator; parent completion remains separately reported')
    if result_path.exists():
        old=read(result_path)
        if old!=result:raise ValueError('Existing slice differs; never overwrite completed subset evidence')
    else:save(result_path,result,immutable=True)
    return dict(status='COMPLETE',requested=len(jobs),results=bind(result_path))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--candidates',nargs='+',required=True);p.add_argument('--label',required=True)
    a=p.parse_args();print(json.dumps(publish(a.manifest,a.candidates,a.label),indent=2))
