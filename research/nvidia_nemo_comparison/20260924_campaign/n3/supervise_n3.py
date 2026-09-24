"""Bound OS queue and sequential jobs; deliberately not named stdlib queue.py."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_n3_supervisor',HERE.parent/'supervision/supervisor.py')
supervisor=importlib.util.module_from_spec(spec);spec.loader.exec_module(supervisor)
load=lambda path: json.loads(Path(path).read_text(encoding='utf-8-sig'))
atomic=supervisor.atomic
now=supervisor.now


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(document):
    for row in document['bindings']:
        if sha(row['path'])!=row['sha256']:raise ValueError('Admission changed: '+row['path'])


def prerequisite(numerical,chain,expected):
    """No process launches from stale, partial, failed or different N2 evidence."""
    if numerical.get('contract_sha256')!=expected['numerical_contract'] or chain.get('contract_sha256')!=expected['chain_contract']:
        return 'BLOCKED_CONTRACT_CHANGED'
    if numerical.get('status') in ('FAILED','INCOMPLETE','INTERRUPTED','CANCELLED') or chain.get('status') in ('FAILED','FAILED_FINAL_CHECKS','INCOMPLETE','BLOCKED','INTERRUPTED'):
        return 'BLOCKED_N2_FAILURE'
    if numerical.get('status')=='COMPLETE' and numerical.get('completed')==422 and numerical.get('total')==422 and chain.get('status')=='READY_FOR_REVIEW':
        return 'READY'
    return 'WAITING_N2'


def before_cutoff(document):
    if datetime.now(timezone.utc)>=datetime.fromisoformat(document['packaging_cutoff_utc']):
        raise TimeoutError('Campaign packaging reserve reached')
    _,low=supervisor.disk_reserves(load(Path(document['state'])/'campaign.json'))
    if low:raise RuntimeError('Disk reserve breached: '+','.join(low))


def owner_gone(record):
    return supervisor.process_identity_state(record.get('pid'),record.get('create_time')) in ('ABSENT','PID_REUSED')


def wait_for_n2(args,document):
    import psutil
    output=Path(document['output']);output.mkdir(parents=True,exist_ok=True)
    with supervisor.lock(output/'queue-owner.lock'):
        process=psutil.Process();process.cpu_affinity([4]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        result=dict(status='STARTING',owner=dict(pid=process.pid,create_time=process.create_time()),
            started_utc=now(),plan_sha256=sha(args.plan),llm_invoked=False,stage_complete=False)
        verify(document)
        try:
            while True:
                before_cutoff(document)
                numerical=load(document['n2']['numerical_result']);chain=load(document['n2']['chain_result'])
                status=prerequisite(numerical,chain,document['n2'])
                result.update(status=status,updated_utc=now(),n2_completed=numerical.get('completed'))
                atomic(output/'QUEUE_RESULT.json',result)
                if status.startswith('BLOCKED'):return 2
                if status=='READY':
                    state=Path(document['state']);worker=load(state/'worker.json')
                    try:supervisor.require_no_active_worker(worker)
                    except RuntimeError:
                        time.sleep(15);continue
                    if not owner_gone(chain.get('owner',{})):
                        time.sleep(15);continue
                    # A terminal report precedes release of its owner's OS lock.
                    try:
                        with supervisor.lock(state/'worker-owner.lock'):
                            with supervisor.lock(Path(document['n2']['chain_result']).parent/'chain.owner.lock'):
                                verify(document)
                                final=chain['final_checks']
                                if sha(final['path'])!=final['sha256'] or load(final['path']).get('status')!='PASS':
                                    raise ValueError('N2 final acceptance checks changed or failed')
                                atomic(output/'N2_PREREQUISITE.json',dict(numerical=numerical,chain=chain,worker=worker))
                    except BlockingIOError:
                        time.sleep(15);continue
                    supervisor.phase(state,'inference','N3')
                    launch=supervisor.start(state,Path(document['worker_spec']))
                    result.update(status='DISPATCHED_N3',worker=launch,updated_utc=now())
                    atomic(output/'QUEUE_RESULT.json',result)
                    return 0
                time.sleep(30)
        except Exception as exc:
            result.update(status='BLOCKED_REVIEW_REQUIRED',error=repr(exc),updated_utc=now())
            atomic(output/'QUEUE_RESULT.json',result);return 2


def accepted(job,returncode):
    """Exit zero never replaces the declared result/cell census."""
    if returncode!=0:return False,'exit '+str(returncode)
    path=Path(job['result'])
    if not path.is_file():return False,'missing result'
    value=load(path)
    if value.get('status') not in job.get('accepted_status',['COMPLETE']):return False,'result status '+str(value.get('status'))
    if 'expected_cells' in job and (value.get('completed')!=job['expected_cells'] or value.get('total')!=job['expected_cells']):
        return False,'incomplete cell census'
    if value.get('successful') is False:return False,'failed tests'
    return True,None


def stop_child(process,created):
    import psutil
    if supervisor.process_identity_state(process.pid,created)!='ALIVE':return
    parent=psutil.Process(process.pid);children=parent.children(recursive=True)
    for child in reversed(children):
        try:child.terminate()
        except psutil.NoSuchProcess:pass
    parent.terminate();_,alive=psutil.wait_procs(children+[parent],timeout=5)
    for child in alive:
        try:child.kill()
        except psutil.NoSuchProcess:pass
    process.wait(timeout=5)


def execute(args,document):
    import psutil
    output=Path(document['output']);output.mkdir(parents=True,exist_ok=True)
    with supervisor.lock(output/'numerical-owner.lock'):
        if (output/'RESULT.json').exists():raise ValueError('Preserve prior coordinator evidence; make a new reviewed plan')
        verify(document);before_cutoff(document)
        own=psutil.Process();own.cpu_affinity([4]);own.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        worker=load(Path(document['state'])/'worker.json')
        if worker.get('child_pid')!=own.pid or abs(worker.get('child_create_time',0)-own.create_time())>=.1 or not supervisor.same_process(worker):
            raise RuntimeError('N3 must be the exact live supervisor-owned child; direct overlapping run is forbidden')
        prerequisite_receipt=load(output/'N2_PREREQUISITE.json')
        if prerequisite(prerequisite_receipt['numerical'],prerequisite_receipt['chain'],document['n2'])!='READY':
            raise RuntimeError('Missing validated N2 transition receipt')
        result=dict(status='RUNNING',started_utc=now(),plan_sha256=sha(args.plan),
            owner=dict(pid=own.pid,create_time=own.create_time()),jobs={},completed=0,total=len(document['jobs']),
            execution='sequential; one numerical child; CPU4 or CPU14; at most one GPU owner',stage_complete=False)
        def publish():
            atomic(output/'RESULT.json',result)
            atomic(Path(document['state'])/'panel_progress.json',dict(stage='N3',status=result['status'],
                completed=result['completed'],total=result['total'],unit='attempted_plan_jobs_not_audio_cells',
                active=result.get('active'),updated_utc=now(),stage_complete=False))
        def gpu_owner(value):
            state=Path(document['state'])
            with supervisor.lock(state/'writer.lock',wait=5):
                campaign=load(state/'campaign.json');campaign['resource_policy']['gpu_owner']=value
                campaign['n3_status']=result['status'];atomic(state/'campaign.json',campaign)
        child=None;created=None
        try:
            for job in document['jobs']:
                before_cutoff(document)
                dependencies=job.get('depends_on',[])
                if any(result['jobs'].get(name,{}).get('status')!='COMPLETE' for name in dependencies):
                    result['jobs'][job['id']]=dict(status='NOT_TESTED_DEPENDENCY_FAILED',dependencies=dependencies)
                    result['completed']+=1;publish();continue
                # Everything that may execute is immutable; do not rehash the
                # multi-gigabyte model payload for every job (adapters do that).
                for row in document['bindings']:
                    if row.get('bytes',0)<50*2**20 and sha(row['path'])!=row['sha256']:
                        raise ValueError('Executable/config admission changed: '+row['path'])
                row=dict(status='RUNNING',started_utc=now());result['jobs'][job['id']]=row
                result['active']=job['id'];publish()
                logpath=output/(job['id']+'.log')
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
                env['CUDA_VISIBLE_DEVICES']='0' if job.get('gpu') else ''
                started=time.monotonic()
                with logpath.open('xb') as log:
                    child=subprocess.Popen(job['argv'],cwd=document['cwd'],env=env,stdin=subprocess.DEVNULL,
                        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                    created=psutil.Process(child.pid).create_time()
                    row['owner']=dict(pid=child.pid,create_time=created)
                    gpu_owner(dict(stage='N3',job=job['id'],**row['owner']) if job.get('gpu') else None);publish()
                    while child.poll() is None:
                        before_cutoff(document)
                        if time.monotonic()-started>job['timeout_seconds']:
                            stop_child(child,created);row['timeout']=True;break
                        row['elapsed_seconds']=time.monotonic()-started;result['updated_utc']=now()
                        publish();time.sleep(5)
                    code=child.wait();child=None
                ok,reason=accepted(job,code)
                row.update(status='COMPLETE' if ok else 'FAILED',exit_code=code,reason=reason,
                    finished_utc=now(),elapsed_seconds=time.monotonic()-started,log_sha256=sha(logpath))
                if Path(job['result']).is_file():row['result']=dict(path=job['result'],sha256=sha(job['result']))
                result['completed']+=1;gpu_owner(None);publish()
            verify(document)
            result.update(status='READY_FOR_REVIEW',active=None,
                numerical_jobs_passed=all(r['status']=='COMPLETE' for r in result['jobs'].values()),
                stage_complete=False,manual_resume='Review N3 numerical evidence, fix failed/unavailable paths, qualify A1 portable streaming, inspect private GUI captures, assemble and back up the final N3 handoff. Do not rerun complete unchanged cells or start N4.')
            return 0 if result['numerical_jobs_passed'] else 2
        except BaseException as exc:
            result.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
            if child is not None and child.poll() is None and created is not None:stop_child(child,created)
            return 2
        finally:
            result['updated_utc']=now();gpu_owner(None);publish()
            atomic(output/'MANUAL_RESUME.json',dict(status=result['status'],thread_id=document['thread_id'],
                instruction=result.get('manual_resume','Inspect N3 failure evidence; preserve failed runs and all N2 outputs.'),
                llm_dispatch='MANUAL_ONLY_NO_VERIFIED_ATOMIC_IDLE_GUARD'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['wait','run','check'])
    p.add_argument('--plan',type=Path,required=True);args=p.parse_args();document=load(args.plan)
    if document['schema']!='just-peachy.n3.queue-plan.v1':raise ValueError('Unsupported queue plan')
    if args.command=='check':
        verify(document);print(json.dumps(dict(status='VERIFIED_NOT_STARTED',jobs=len(document['jobs']))));return 0
    return wait_for_n2(args,document) if args.command=='wait' else execute(args,document)


if __name__=='__main__':raise SystemExit(main())
