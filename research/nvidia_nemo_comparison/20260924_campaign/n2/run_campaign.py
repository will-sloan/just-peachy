"""Two-lane code-only N2 numerical coordinator. See README.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'supervision'))
from supervisor import read,lock,disk_reserves,process_identity_state,stop_owned_tree
from io_utils import atomic,IO_VERSION


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def completion(job):
    """A zero exit alone cannot certify a partial or missing numerical panel."""
    path=Path(job['result']);result=read(path,{})
    if result.get('status')!='COMPLETE':raise ValueError('Numerical result is not COMPLETE: '+str(path))
    if job['result_kind']=='controller':
        count=len(result.get('completed',{}))
        if result.get('failed'):raise ValueError('Controller result contains failures')
    elif job['result_kind']=='gui':
        count=len(result.get('cells',[]))
        if any(row['status']!='COMPLETE' for row in result['cells']):raise ValueError('GUI cell failed')
    elif job['result_kind']=='native':
        count=result['completed'] if isinstance(result['completed'],int) else len(result['completed'])
        if result.get('failed'):raise ValueError('Native result contains failures')
    else:raise ValueError('Unknown result kind')
    if count!=job['cells']:raise ValueError('Numerical cell count is incomplete')
    return dict(path=str(path),sha256=digest(path),cells=count)


def admit(spec):
    if spec.get('schema')!='n2-numerical-coordinator-v1' or len(spec.get('lanes',[])) not in (1,2):
        raise ValueError('One or two explicit N2 lanes required')
    keys=[];cpus=[]
    for lane in spec['lanes']:
        cpus.append(lane['cpu'])
        if type(lane['cpu']) is not int or lane['cpu']<0 or not lane['jobs']:raise ValueError('CPU and jobs required')
        for job in lane['jobs']:
            keys.append(job['id'])
            if not isinstance(job['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]+',job['id']):raise ValueError('Unsafe job ID')
            if job.get('device') not in ('cpu','cuda'):raise ValueError('Explicit device required')
            if not isinstance(job['argv'],list) or not job['argv'] or not all(isinstance(x,str) for x in job['argv']):
                raise ValueError('Explicit argv list required')
            if not Path(job['argv'][0]).is_file() or not Path(job['cwd']).is_dir():raise ValueError('Missing executable or cwd')
            if type(job['cells']) is not int or job['cells']<=0:raise ValueError('Positive integer cell denominator required')
            timeout=job.get('timeout_seconds')
            if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 0<timeout<=86400:
                raise ValueError('Explicit job timeout in (0,86400] seconds required')
    if len(set(keys))!=len(keys) or len(set(cpus))!=len(cpus):raise ValueError('Duplicate job or CPU lane')
    if sum(any(job.get('device')=='cuda' for job in lane['jobs']) for lane in spec['lanes'])>1:
        raise ValueError('Only one lane may own CUDA')
    return keys,cpus


def run(args):
    import psutil
    spec=read(args.spec);keys,cpus=admit(spec)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    state_root=args.state.resolve();state=read(state_root/'campaign.json')
    deadline=datetime.fromisoformat(state['target_utc'])-timedelta(hours=state['packaging_reserve_hours'])
    p=psutil.Process();p.cpu_affinity(cpus)
    if os.name=='nt':p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    binding=dict(spec=spec,runner_sha256=digest(__file__),io_version=IO_VERSION,io_helper_sha256=digest(HERE/'io_utils.py'),
                 supervisor_sha256=digest(HERE.parent/'supervision/supervisor.py'))
    contract=canonical(binding);admission=output/'ADMISSION.json'
    with lock(output/'owner.lock'):
        if admission.exists() and read(admission)['contract_sha256']!=contract:raise ValueError('Coordinator contract changed')
        atomic(admission,dict(contract_sha256=contract,contract=binding))
        prior=read(output/'RESULT.json',{})
        if prior and (prior.get('contract_sha256')!=contract or set(prior.get('jobs',{}))!=set(keys)):
            raise ValueError('Prior coordinator result contract or job set differs')
        for item in prior.get('jobs',{}).values():
            if item.get('owner'):
                owner=item['owner'];identity=process_identity_state(owner['pid'],owner.get('create_time'))
                if identity in ('ALIVE','UNVERIFIED'):raise RuntimeError('Prior child remains active or unverified')
        jobs=prior.get('jobs',{});running={};logs={};started=time.monotonic();initial=0
        for lane in spec['lanes']:
            for job in lane['jobs']:
                old=jobs.get(job['id'],{})
                if old.get('status')=='COMPLETE':
                    actual=completion(job)
                    if actual!=old['result']:raise ValueError('Completed numerical evidence changed')
                    initial+=job['cells']
                else:jobs[job['id']]=dict(status='PENDING',cells=job['cells'])
        total=sum(job['cells'] for lane in spec['lanes'] for job in lane['jobs'])
        errors=[]

        def report(status):
            completed=sum(row['cells'] for row in jobs.values() if row['status']=='COMPLETE')
            active_progress=[]
            for key,(proc,job) in running.items():
                progress=read(Path(job['progress']),{})
                count=progress.get('completed',0)
                if isinstance(count,dict):count=len(count)
                if not isinstance(count,int):count=0
                completed+=min(job['cells'],max(0,count))
                active_progress.append(dict(job=key,completed=count,total=job['cells'],progress=job['progress']))
            value=dict(schema='n2-numerical-coordinator-result-v1',status=status,contract_sha256=contract,
                pid=os.getpid(),completed=completed,total=total,cached_at_start=initial,
                elapsed_seconds=time.monotonic()-started,active=active_progress,jobs=jobs,errors=errors,
                llm_invoked=False,packaging_cutoff_utc=deadline.isoformat())
            atomic(output/'RESULT.json',value)
            atomic(state_root/'panel_progress.json',value)

        try:
            while True:
                _,low=disk_reserves(read(state_root/'campaign.json'))
                if low:raise RuntimeError('Campaign disk reserve breached: '+','.join(low))
                if datetime.now(timezone.utc)>=deadline:raise RuntimeError('Campaign packaging reserve reached')
                for lane in spec['lanes']:
                    active=next((job for job in lane['jobs'] if job['id'] in running),None)
                    if active:continue
                    if any(jobs[job['id']]['status']=='FAILED' for job in lane['jobs']):continue
                    pending=next((job for job in lane['jobs'] if jobs[job['id']]['status']=='PENDING'),None)
                    if pending is None:continue
                    key=pending['id'];log=(output/(key+'.log')).open('ab');logs[key]=log
                    flags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0
                    proc=subprocess.Popen(pending['argv'],cwd=pending['cwd'],stdin=subprocess.DEVNULL,
                        stdout=log,stderr=log,creationflags=flags)
                    running[key]=(proc,pending)
                    jobs[key]=dict(status='RUNNING',cells=pending['cells'],owner=None,
                        started_utc=datetime.now(timezone.utc).isoformat(),started_monotonic=time.monotonic())
                    try:
                        owner=psutil.Process(proc.pid)
                        jobs[key]['owner']=dict(pid=proc.pid,create_time=owner.create_time())
                        owner.cpu_affinity([lane['cpu']])
                    except psutil.Error:
                        if proc.poll() is None:raise
                    report('RUNNING')
                for key,(proc,job) in list(running.items()):
                    if proc.poll() is None:
                        if time.monotonic()-jobs[key]['started_monotonic']<=job['timeout_seconds']:continue
                        if jobs[key]['owner']:stop_owned_tree(jobs[key]['owner'])
                        else:proc.terminate()
                        try:proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
                        jobs[key]['timeout_reached']=True
                    logs.pop(key).close();del running[key]
                    jobs[key].update(exit_code=proc.returncode,finished_utc=datetime.now(timezone.utc).isoformat())
                    try:
                        if jobs[key].get('timeout_reached'):raise TimeoutError('Numerical job exceeded declared wall-clock bound')
                        if proc.returncode:raise RuntimeError('Numerical job exit '+str(proc.returncode))
                        jobs[key].update(status='COMPLETE',result=completion(job))
                    except BaseException as exc:
                        jobs[key].update(status='FAILED',error=repr(exc));errors.append(dict(job=key,error=repr(exc)))
                report('RUNNING')
                if not running:
                    runnable=any(all(jobs[j['id']]['status']!='FAILED' for j in lane['jobs']) and
                        any(jobs[j['id']]['status']=='PENDING' for j in lane['jobs']) for lane in spec['lanes'])
                    if not runnable:break
                time.sleep(2)
        except BaseException as exc:
            errors.append(dict(coordinator=repr(exc)))
            for key,(proc,job) in running.items():
                if jobs[key]['owner']:stop_owned_tree(jobs[key]['owner'])
                elif proc.poll() is None:proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
                jobs[key].update(status='INTERRUPTED',error=repr(exc))
            raise
        finally:
            for log in logs.values():log.close()
            finished=all(row['status']=='COMPLETE' for row in jobs.values())
            report('COMPLETE' if finished else 'INCOMPLETE')
        return 0 if finished else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--state',type=Path,required=True)
    raise SystemExit(run(parser.parse_args()))
