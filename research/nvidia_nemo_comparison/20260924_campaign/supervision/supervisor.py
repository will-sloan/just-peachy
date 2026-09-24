"""Cheap Windows/POSIX campaign supervisor; no LLM calls. See README.md."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import psutil

INTERVALS = {'setup': 10, 'inference': 15, 'replay': 30}
PYTHON = sys.executable


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


@contextmanager
def lock(path, wait=0):
    """OS-held one-byte lock: process death releases ownership, never timeout theft."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    acquired = False
    try:
        stream.seek(0, 2)
        if not stream.tell():stream.write(b'0');stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            deadline=time.monotonic()+wait
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic()>=deadline:raise BlockingIOError('Another campaign writer owns '+str(path)) from exc
                    time.sleep(.02)
        else:
            import fcntl
            deadline=time.monotonic()+wait
            while True:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.02)
        acquired = True
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def process_identity_state(pid, created):
    """Distinguish absence/PID reuse from an owner whose identity is uncertain."""
    if pid is None:return 'ABSENT'
    try:
        process = psutil.Process(pid)
        if not process.is_running():return 'ABSENT'
        if created is None:return 'UNVERIFIED'
        return 'ALIVE' if abs(process.create_time()-created) < .1 else 'PID_REUSED'
    except psutil.NoSuchProcess:return 'ABSENT'
    except (psutil.Error, TypeError, ValueError):return 'UNVERIFIED'


def same_process(record):
    return process_identity_state(record.get('pid'),record.get('create_time'))=='ALIVE'


def require_no_active_worker(record):
    # A terminal status is written before the host releases its lifetime lock.
    # A surviving child must also block restart after unexpected host death.
    for label,pid,created in (
            ('host',record.get('pid'),record.get('create_time')),
            ('child',record.get('child_pid'),record.get('child_create_time'))):
        identity=process_identity_state(pid,created)
        if identity=='ALIVE':
            raise RuntimeError('Worker '+label+' still active; refusing overlap')
        if identity=='UNVERIFIED':
            raise RuntimeError('Worker '+label+' identity unverified; manual recovery required before resume')
    if record.get('child_launch_pending'):
        raise RuntimeError('Worker child launch outcome unverified; manual recovery required before resume')


def disk_reserves(state):
    values={};low=[]
    for drive,minimum in state['resource_policy']['minimum_free_gib'].items():
        path=Path(drive+'/')
        if path.exists():
            values[drive]=psutil.disk_usage(str(path)).free/1024**3
            if values[drive]<minimum:low.append(drive)
    return values,low


def stop_owned_tree(record):
    """Stop only a verified supervisor host and its descendants on reserve breach."""
    if not same_process(record):return False
    owner=psutil.Process(record['pid']);children=owner.children(recursive=True)
    targets=list(reversed(children))+[owner]
    for process in targets:
        try:process.terminate()
        except psutil.Error:pass
    _,remaining=psutil.wait_procs(targets,timeout=5)
    for process in remaining:
        try:process.kill()
        except psutil.Error:pass
    return True


def init(root, thread_id, started):
    root.mkdir(parents=True, exist_ok=True)
    with lock(root/'writer.lock'):
        if (root/'campaign.json').exists():return read(root/'campaign.json')
        start = datetime.fromisoformat(started) if started else datetime.now(timezone.utc)
        state = dict(schema='just-peachy.n1.campaign.v1', campaign_id='20260924_campaign',
            started_utc=start.isoformat(), target_utc=(start+timedelta(hours=96)).isoformat(),
            packaging_reserve_hours=12, phase='setup', stage='N1', status='SETUP',
            session_id=thread_id, requested_model='gpt-6-astra', requested_reasoning='ultra', requested_speed='normal',
            llm_dispatch='MANUAL_REVIEW_ONLY_NO_VERIFIED_CROSS_TURN_IDLE_GUARD',
            llm_dispatch_reason='CLI accepts exact session resume, but no authenticated atomic idle/queue guard is verified. Never resume a competing live turn.',
            scheduler_intervals_minutes=INTERVALS, worker_spec=None,
            resource_policy=dict(max_parallel_workers=2,max_cpu_cores=2,gpu_owner=None,
                                 minimum_free_gib={'C:':50,'G:':75},new_payload_allowance_gib=50),
            downgrade_order=['retain baseline and Nemotron hybrid','compact ASR and enrollment','600M alternatives','optional multitalker and standalone punctuation'],
            user_constraints=['No desktop control or focus changes','Pi off throughout campaign','Saved processed audio only','No microphone enumeration'],
            current_codex_turn_active=True, created_utc=now())
        atomic(root/'campaign.json',state)
        return state


def phase(root, name, stage=None):
    with lock(root/'writer.lock'):
        state = read(root/'campaign.json')
        if name not in INTERVALS:raise ValueError('Unknown phase')
        state['phase']=name
        if stage:state['stage']=stage
        atomic(root/'campaign.json',state)
    return state


def probe(root, expected_phase=None):
    with lock(root/'writer.lock'):
        state = read(root/'campaign.json')
        if expected_phase and state['phase'] != expected_phase:
            result=dict(status='PHASE_NOT_DUE',utc=now(),expected_phase=expected_phase,actual_phase=state['phase'])
            atomic(root/f'probe-{expected_phase}.json',result)
            return result
        worker=read(root/'worker.json',{})
        progress=read(root/'panel_progress.json',{})
        health = worker.get('status','IDLE')
        if health in ('STARTING','RUNNING') and not same_process(worker):health='WORKER_LOST'
        age = (time.time()-worker.get('heartbeat_unix',time.time())) if worker else None
        if health in ('STARTING','RUNNING') and age is not None and age>120:health='WATCHDOG_HEARTBEAT_STALE'
        disk,low=disk_reserves(state)
        if low:
            health='DISK_RESERVE_LOW'
            if worker.get('status') in ('STARTING','RUNNING') and stop_owned_tree(worker):
                worker.update(status='FAILED_DISK_RESERVE',error='Reserve breached on '+','.join(low),ended_utc=now())
                atomic(root/'worker.json',worker)
        completed=progress.get('completed',0);total=progress.get('total',0)
        elapsed=progress.get('elapsed_seconds')
        prior=read(root/'status.json',{})
        reference=prior.get('throughput_reference',{})
        identity=[worker.get('run_id'),progress.get('pid')]
        if reference.get('identity')!=identity or completed<reference.get('completed',0) or (
                elapsed is not None and reference.get('elapsed_seconds') is not None and elapsed<reference['elapsed_seconds']):
            reference=dict(identity=identity,completed=completed,elapsed_seconds=elapsed)
        new_cells=completed-reference.get('completed',completed)
        span=elapsed-reference['elapsed_seconds'] if elapsed is not None and reference.get('elapsed_seconds') is not None else None
        eta=span/new_cells*(total-completed) if new_cells>0 and span is not None and span>=0 else None
        if total and completed>=total:eta=0
        meaningful=dict(stage=state['stage'],phase=state['phase'],worker_health=health,
                        worker_run=worker.get('run_id'),error=worker.get('error'),
                        progress_decile=int(10*completed/total) if total else None)
        digest=hashlib.sha256(json.dumps(meaningful,sort_keys=True).encode()).hexdigest()
        changed=prior.get('meaningful_hash')!=digest
        status=dict(schema='just-peachy.n1.status.v1',checked_utc=now(),meaningful=meaningful,
            meaningful_hash=digest,changed=changed,completed=completed,total=total,eta_seconds=eta,
            eta_basis='New cells since first observed current worker/PID; cached cells excluded; null until a throughput interval exists',
            throughput_reference=reference,throughput_new_cells=new_cells,throughput_window_seconds=span,
            target_utc=state['target_utc'],worker_heartbeat_age_sec=age,available_disk_gib=disk,
            llm_invoked=False,review_dispatch=state['llm_dispatch'],interval_minutes=INTERVALS[state['phase']])
        if changed:
            request=dict(schema='just-peachy.n1.review-request.v1',utc=now(),session_id=state['session_id'],
                model=state['requested_model'],reasoning=state['requested_reasoning'],speed=state['requested_speed'],
                delta=meaningful,prior=prior.get('meaningful'),dispatch='QUEUED_MANUAL_NO_LLM_STARTED',
                active_turn_protected=state['current_codex_turn_active'])
            atomic(root/'review_requests'/f'{time.time_ns()}-{digest[:12]}.json',request)
        atomic(root/'status.json',status)
        atomic(root/f"probe-{state['phase']}.json",status)
        return status


def start(root, spec_path, resume=False):
    with lock(root/'writer.lock'):
        _,low=disk_reserves(read(root/'campaign.json'))
        if low:raise RuntimeError('Disk reserve breached; refusing new allocation on '+','.join(low))
        existing=read(root/'worker.json',{})
        require_no_active_worker(existing)
        spec=read(spec_path)
        if not isinstance(spec.get('argv'),list) or not spec['argv'] or not all(isinstance(x,str) for x in spec['argv']):
            raise ValueError('Worker spec needs an explicit argv list')
        if not Path(spec['argv'][0]).is_file() or not Path(spec['cwd']).is_dir():
            raise ValueError('Worker executable/cwd missing')
        active_spec=root/'worker_spec.json';atomic(active_spec,spec)
        flags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0
        with (root/'worker_host.log').open('ab') as log:
            process=subprocess.Popen([PYTHON,'-B',str(Path(__file__).resolve()),'host','--root',str(root)],
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=flags,
                start_new_session=os.name!='nt')
        p=psutil.Process(process.pid)
        threading.Thread(target=process.wait,daemon=True,name='n1-host-reaper').start()
        record=dict(status='STARTING',pid=process.pid,create_time=p.create_time(),run_id=uuid.uuid4().hex,
                    started_utc=now(),heartbeat_unix=time.time(),resumed=resume,argv_sha256=hashlib.sha256(json.dumps(spec['argv']).encode()).hexdigest())
        atomic(root/'worker.json',record)
        return record


def host(root):
    # Independent worker host lives after the initiating Codex turn. The OS lock
    # serializes host lifetimes, while writer.lock serializes status mutations.
    with lock(root/'worker-owner.lock'):
        spec=read(root/'worker_spec.json')
        process_self=psutil.Process()
        if os.name=='nt':process_self.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        cpus=process_self.cpu_affinity()
        if len(cpus)>2:process_self.cpu_affinity(cpus[-2:])
        with lock(root/'writer.lock',wait=5):
            record=read(root/'worker.json')
            if record.get('pid')!=os.getpid():raise RuntimeError('Host owner mismatch')
            record.update(status='RUNNING',heartbeat_unix=time.time(),child_launch_pending=True)
            atomic(root/'worker.json',record)
        flags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0
        try:
            with (root/'worker.log').open('ab') as log:
                child=subprocess.Popen(spec['argv'],cwd=spec['cwd'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=flags)
                try:
                    child_created=psutil.Process(child.pid).create_time()
                except psutil.Error:
                    # A tiny child may already have exited. Its Popen handle
                    # confirms that outcome, including Windows access denial
                    # after exit; never retain an unbound PID.
                    if child.poll() is None:raise
                    child_created=None
                with lock(root/'writer.lock',wait=5):
                    record.update(child_pid=child.pid if child_created is not None else None,
                                  child_create_time=child_created,child_launch_pending=False,
                                  heartbeat_unix=time.time())
                    atomic(root/'worker.json',record)
                while child.poll() is None:
                    with lock(root/'writer.lock',wait=5):
                        record.update(heartbeat_unix=time.time());atomic(root/'worker.json',record)
                    time.sleep(5)
            record.update(status='COMPLETED' if child.returncode==0 else 'FAILED',exit_code=child.returncode,
                          ended_utc=now(),heartbeat_unix=time.time(),error=None if child.returncode==0 else f'Worker exited {child.returncode}')
        except Exception as exc:
            if 'child' not in locals():record['child_launch_pending']=False
            if 'child' in locals() and child.poll() is None:
                try:
                    owned=psutil.Process(child.pid)
                    descendants=owned.children(recursive=True)
                    for process in reversed(descendants):
                        try:process.terminate()
                        except psutil.Error:pass
                    owned.terminate()
                    _,remaining=psutil.wait_procs(descendants+[owned],timeout=5)
                    for process in remaining:
                        try:process.kill()
                        except psutil.Error:pass
                    child.wait(timeout=5)
                except (psutil.Error,subprocess.TimeoutExpired):pass
            record.update(status='FAILED',ended_utc=now(),heartbeat_unix=time.time(),error=repr(exc))
        with lock(root/'writer.lock',wait=5):atomic(root/'worker.json',record)
        probe(root)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['init','probe','phase','start','host','status'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--thread-id');p.add_argument('--started-utc');p.add_argument('--phase',choices=INTERVALS)
    p.add_argument('--stage');p.add_argument('--expected-phase',choices=INTERVALS)
    p.add_argument('--spec',type=Path);p.add_argument('--resume',action='store_true')
    args=p.parse_args();root=args.root.resolve()
    if args.command=='init':result=init(root,args.thread_id,args.started_utc)
    elif args.command=='probe':result=probe(root,args.expected_phase)
    elif args.command=='phase':result=phase(root,args.phase,args.stage)
    elif args.command=='start':result=start(root,args.spec,args.resume)
    elif args.command=='host':host(root);return
    else:result=read(root/'status.json',{})
    if sys.stdout:print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except BlockingIOError:
        if sys.stdout:print('{"status":"OVERLAP_PREVENTED"}')
        raise SystemExit(0)
