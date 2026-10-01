"""Native outer broker supervisor; README_FIELD_OPERATOR_BROKER_NATIVE_V1.md."""
from datetime import datetime,timezone
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time
sys.dont_write_bytecode=True
from field_operator_broker_common_v1 import bundle,physical,ready
from field_operator_session_plan_v3 import validate_policy,encoded
from field_operator_session_ledger_v4 import Ledger,read,file_pin,identity,ticks
from field_operator_broker_files_v2 import Files,inspect
from field_operator_entry_v7 import available_ram,capture_closed
from field_owner_binding_v1 import decode
MIB=1024**2

def recording_tree(root):
    total=0;files=dirs=0
    for base,names,members in os.walk(root,followlinks=False):
        dirs+=1;p=Path(base);s=p.stat()
        if p.is_symlink() or max(s.st_size,s.st_blocks*512)>65536:raise RuntimeError('Recording directory boundary')
        total+=65536
        for name in members:
            p=Path(base)/name;s=p.lstat()
            if p.is_symlink() or not p.is_file() or s.st_size>32*MIB:raise RuntimeError('Recording member boundary')
            files+=1;total+=s.st_size
        if dirs>64 or files>256:raise RuntimeError('Original recording cardinality')
    if total>146919980:raise RuntimeError('Original recording allocation')
    return dict(bytes=total,files=files,directories=dirs)

def tree(root,policy):
    inspect(root,lambda:validate_policy(policy));plan=policy['allocation'];total=files=dirs=0
    allowed={'broker','code','RELEASE.json','.lease','recordings',*plan['slot_names']}
    if set(p.name for p in root.iterdir())-allowed:raise ValueError('Unknown outer member')
    for base,names,members in os.walk(root,followlinks=False):
        p=Path(base)
        if p==root/'recordings':
            if set(names)-set(plan['slot_names']) or members:raise ValueError('Unknown recording reservation')
            for name in names:
                row=recording_tree(p/name);total+=row['bytes'];files+=row['files'];dirs+=row['directories']
            names[:]=[]
        dirs+=1
        if p.is_symlink() or max(p.stat().st_size,p.stat().st_blocks*512)>65536:raise ValueError('Outer directory quota')
        total+=65536
        for name in members:
            q=p/name;s=q.lstat()
            if q.is_symlink() or not q.is_file() or s.st_nlink not in (1,2):raise ValueError('Outer file type')
            if s.st_size>128*1024 and not (p==root/'broker' and name in ('service.log','telemetry.jsonl')):
                raise ValueError('Outer file maximum')
            if p==root and (name not in ('RELEASE.json','.lease') or (name=='.lease' and s.st_size)):
                raise ValueError('Outer root file')
            if p.name in plan['slot_names'] and p.parent==root:
                from field_operator_session_plan_v3 import RECORDS
                if name not in {k+'.json'+suffix for k in RECORDS for suffix in ('','.pending')} or s.st_size>16384:
                    raise ValueError('Ledger slot file')
            total+=s.st_size;files+=1
    if total>plan['target_maximum_bytes']:raise RuntimeError('Full broker output allocation')
    return dict(bytes=total,files=files,directories=dirs)

def main(root,policy_sha256):
    os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*MIB,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(MIB,)*2);resource.setrlimit(resource.RLIMIT_FSIZE,(32*MIB,)*2)
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('Existing gate alarm')
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(565)
    root=Path(root).absolute()
    if file_pin(root/'RELEASE.json')['sha256']!=policy_sha256:raise ValueError('Gate policy pin')
    policy,config,manifest=bundle(root);check=lambda:validate_policy(policy)
    files=Files(root,check);owner=identity();files.json('GATE_OWNER.json',owner)
    physical(config)
    expiry=datetime.fromisoformat(policy['expires_utc'])
    if (expiry-datetime.now(timezone.utc)).total_seconds()<570:raise RuntimeError('Full gate/Stop/backup lifetime')
    if available_ram()<850*MIB or shutil.disk_usage(root).free<5*1024**3+policy['allocation']['target_maximum_bytes']:
        raise RuntimeError('Initial RAM/full output reserve')
    before=read(root/'broker/STAGE_OWNER.json')
    if before['boot_id']==owner['boot_id'] and ticks(before['pid'])==before['start_ticks']:raise RuntimeError('Outer initializer remains alive')
    for previous in decode(config['preflight_pi_owners']):
        if previous['boot_id']==owner['boot_id'] and ticks(previous['pid'])==previous['start_ticks']:
            raise RuntimeError('Prior exact research process is alive')
    root_target=root.parent
    target=int(subprocess.check_output(['du','-sb',str(root_target)],text=True,timeout=10).split()[0])
    own=int(subprocess.check_output(['du','-sb',str(root)],text=True,timeout=10).split()[0])
    outside=target-own;request=policy['allocation']['combined_request_bytes']
    if policy['host_window_bytes']+outside+request>policy['combined_output_cap_bytes'] or policy['payload_before_bytes']+max(0,outside-policy['target_before_bytes'])+request>policy['total_payload_cap_bytes']:
        raise RuntimeError('Fresh target-inclusive full broker reservation')
    active=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','--plain','jp-*'],text=True,timeout=10)
    if active.strip():raise RuntimeError('Healthy research unit remains; leave it untouched')
    home=Path.home()/'JustPeachy';unit='jp-'+root.name
    with (root_target/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (home/'data/xvf-hardware.lock').open('r+b') as hardware:
            fcntl.flock(hardware,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(hardware,fcntl.LOCK_UN)
        props=['CPUQuota=200%','TasksMax=64','LimitAS='+str(768*MIB),'LimitSTACK='+str(MIB),
               'RuntimeMaxSec=510','TimeoutStopSec=30','LimitCORE=0','Nice=10','LimitFSIZE='+str(32*MIB)]
        cmd=['systemd-run','--user','--unit='+unit,'--description=JustPeachy-admitted-session-broker','--wait','--pipe']
        for prop in props:cmd+=['-p',prop]
        env=dict(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
            MALLOC_ARENA_MAX='1',MALLOC_MMAP_THRESHOLD_='131072',MALLOC_TRIM_THRESHOLD_='131072',
            CUDA_VISIBLE_DEVICES='-1',ORT_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1',
            XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()),DISPLAY=':0',WAYLAND_DISPLAY='wayland-0',
            XAUTHORITY=str(Path.home()/'.Xauthority'),ALSA_CONFIG_PATH=config['alsa_config'])
        for k,v in env.items():cmd+=['--setenv='+k+'='+v]
        cmd+=['taskset','-c','2,3',config['python'],'-B',str(root/'code/field_operator_broker_entry_v1.py'),
              '--root',str(root),'--policy-sha256',policy_sha256]
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
        os.set_blocking(proc.stdout.fileno(),False)
        worker=None;acked=False;failure=None;pending=b'';samples=0;peak=0;minimum=available_ram()
        def drain():
            nonlocal pending
            while True:
                block=proc.stdout.read(16384)
                if not block:return
                try:files.write('service.log',block,append=True)
                except BaseException:pending=block;raise
        try:
            next_sample=0.;started=time.monotonic()
            while proc.poll() is None:
                check();drain()
                if not acked and (root/'broker/OWNER.json').exists():
                    worker=ready(root,'OWNER.json',check)
                    if worker['boot_id']!=owner['boot_id'] or ticks(worker['pid'])!=worker['start_ticks']:raise ValueError('Exact broker owner')
                    raw=subprocess.check_output(['systemctl','--user','show',unit,'-p','MainPID','-p','ControlGroup',
                        '-p','CPUQuotaPerSecUSec','-p','TasksMax','-p','LimitAS','-p','LimitSTACK','-p','LimitFSIZE',
                        '-p','RuntimeMaxUSec','-p','TimeoutStopUSec'],text=True,timeout=10)
                    actual=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
                    if int(actual['MainPID'])!=worker['pid'] or int(actual['LimitAS'])!=768*MIB or int(actual['LimitSTACK'])!=MIB or int(actual['TasksMax'])!=64 or actual['CPUQuotaPerSecUSec']!='2s' or int(actual['LimitFSIZE'])!=32*MIB or actual['RuntimeMaxUSec']!='8min 30s' or actual['TimeoutStopUSec']!='30s':
                        raise RuntimeError('Actual shared systemd envelope mismatch')
                    files.json('ENVELOPE.json',dict(gate_owner=owner,properties=actual,raw_properties=raw,
                        gate_affinity=sorted(os.sched_getaffinity(0)),gate_as=list(resource.getrlimit(resource.RLIMIT_AS)),
                        gate_stack=list(resource.getrlimit(resource.RLIMIT_STACK)),alarm_seconds=signal.getitimer(signal.ITIMER_REAL)[0]))
                    files.json('ACK.json',dict(owner=worker,policy_sha256=policy_sha256,gate_owner=owner));acked=True
                now=time.monotonic()
                if now>=next_sample:
                    next_sample=now+.5;ram=available_ram();minimum=min(minimum,ram);size=tree(root,policy);rss=0
                    if worker and ticks(worker['pid'])==worker['start_ticks']:
                        rss=next((int(line.split()[1])*1024 for line in Path('/proc',str(worker['pid']),'status').read_text().splitlines() if line.startswith('VmRSS:')),0)
                    peak=max(peak,rss)
                    line=encoded(dict(t=now,ram=ram,rss=rss,tree=size))+b'\n'
                    if len(line)>256:raise RuntimeError('Telemetry sample allocation')
                    files.write('telemetry.jsonl',line,append=True);samples+=1
                    if ram<192*MIB or shutil.disk_usage(root).free<5*1024**3:raise RuntimeError('Sampled RAM/disk stop')
                if (expiry-datetime.now(timezone.utc)).total_seconds()<60:raise TimeoutError('Cleanup/backup reserve')
                time.sleep(.02)
            drain()
        except BaseException as exc:
            failure=type(exc).__name__+': '+str(exc)[:1024]
            subprocess.run(['systemctl','--user','stop','--no-block',unit],timeout=5,check=False)
            try:files.json('FAILURE.json',dict(error=failure,rejected_log_bytes=len(pending),remaining_pipe_tail_retained=False))
            except Exception:pass
        finally:
            try:proc.wait(timeout=35)
            except subprocess.TimeoutExpired:
                subprocess.run(['systemctl','--user','kill','--kill-whom=all','--signal=KILL',unit],timeout=5,check=False)
                proc.wait(timeout=5)
            try:
                if not pending:drain()
            finally:proc.stdout.close()
        closed=[]
        for name in policy['allocation']['slot_names']:
            recording=root/'recordings'/name
            for relative in ('control/OWNER.json','parent_control/OWNER.json','source/CHILD_OWNER.json'):
                p=recording/relative
                if p.exists():
                    who=read(p);dead=who['boot_id']!=owner['boot_id'] or ticks(who['pid'])!=who['start_ticks']
                    closed.append(dict(slot=name,kind=relative,owner=who,exact_dead=dead))
        dead=worker is not None and ticks(worker['pid'])!=worker['start_ticks']
        result=dict(gate_owner=owner,worker_owner=worker,worker_exact_dead=dead,recording_owners=closed,
            returncode=proc.returncode,owner_ack=acked,pipe_closed=proc.stdout.closed,failure=failure,
            capture_closed=capture_closed(),samples=samples,peak_sampled_broker_rss_bytes=peak,
            minimum_sampled_available_ram_bytes=minimum,tree=tree(root,policy),aggregate_rss_qualified=False)
        result['logical_success']=not failure and proc.returncode==0 and dead and all(x['exact_dead'] for x in closed) and result['capture_closed']
        files.json('GATE_RESULT.json',result)
        print(json.dumps(dict(logical_success=result['logical_success'],returncode=proc.returncode,failure=failure)))
        return int(not result['logical_success'])
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--policy-sha256',required=True)
    a=p.parse_args();raise SystemExit(main(a.root,a.policy_sha256))
