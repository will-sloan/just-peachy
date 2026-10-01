"""Outer gate for the concrete live entry. Read README_FIELD_SAVED_ACTIONS_V1.md."""
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import math
import subprocess
import sys
import time
from field_saved_actions_v1 import identity,ticks,sha,small,sink,available_ram,capture_closed
from field_live_layout_v3 import specification
from field_child_deadline_v1 import validate,remaining,supervise

MIB=1024**2


def footprint(root):
    total=0;files=dirs=0
    for base,names,members in os.walk(root,followlinks=False):
        dirs+=1;p=Path(base);s=p.stat()
        if p.is_symlink() or max(s.st_size,s.st_blocks*512)>65536:raise RuntimeError('Directory boundary')
        total+=65536
        for name in members:
            p=Path(base)/name;s=p.lstat()
            if p.is_symlink() or not p.is_file() or s.st_size>32*MIB:raise RuntimeError('Output member boundary')
            files+=1;total+=s.st_size
        if dirs>64 or files>256:raise RuntimeError('Full tree cardinality')
    return dict(bytes=total,files=files,directories=dirs)


def main(root):
    """Own research lease through exact worker and source-child closure."""
    os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*MIB,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(MIB,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(32*MIB,)*2)
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError("Existing gate alarm")
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(335)
    root=Path(root).resolve();a=small(root/'control/ADMISSION.json');layout=specification()
    policy_path=Path(a['resource_policy']['path'])
    if sha(policy_path)!=a['resource_policy']['sha256']:raise RuntimeError('Fresh resource policy hash')
    policy=small(policy_path)
    if policy['authority']!='AUTONOMOUS_QUIET_AUTHORIZATION_V1' or policy['old_policy_unchanged'] is not True:
        raise RuntimeError('Measured resource-policy authority missing')
    if policy['hard_deadline_utc']!='2026-10-01T17:42:44Z':raise RuntimeError('Wrong hard deadline')
    for key in ('target_maximum_bytes','host_maximum_bytes','combined_request_bytes'):
        if type(a[key]) is not int or a[key]!=layout[key]:raise RuntimeError('Full independent maxima not reserved')
    if a['capture'] is not False or a['scope']!='SAVED_COPY_VISIBLE_SAVE_OPEN':raise RuntimeError('Saved-only admission required')
    if identity()['boot_id']!=a['boot_id'] or not datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']):
        raise RuntimeError('Stale admission')
    if ticks(1013)!=569 or ticks(1130)!=607:raise RuntimeError('Baseline identities changed')
    home=Path.home()/'JustPeachy'
    if sha(home/'install/current.json')!=a['install_sha256'] or sha(home/'data/live_config.json')!=a['live_config_sha256']:
        raise RuntimeError('Baseline file identities changed')
    if available_ram()<850*MIB or shutil.disk_usage(root).free<5*1024**3+layout['target_maximum_bytes']:
        raise RuntimeError('Initial Pi RAM/disk floor')
    if not capture_closed():raise RuntimeError('Capture busy')
    for row in a['files']:
        if Path(row['path']).stat().st_size!=row['bytes'] or sha(row['path'])!=row['sha256']:
            raise RuntimeError('Changed admitted input')
    target_now=int(subprocess.check_output(['du','-sb',str(root.parent)],text=True).split()[0])
    if a['host_window_bytes']+target_now+layout['combined_request_bytes']>policy['combined_output_cap_bytes']:
        raise RuntimeError('Measured combined reservation does not fit fresh policy')
    if a['payload_before_bytes']+max(0,target_now-a['target_before_bytes'])+layout['combined_request_bytes']>policy['total_payload_cap_bytes']:
        raise RuntimeError('Measured full payload reservation does not fit fresh policy')
    active=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating',
        '--no-legend','--plain','jp-*'],text=True)
    if active.strip():raise RuntimeError('Active research unit; leave it untouched')
    with (root.parent/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (home/'data/xvf-hardware.lock').open('r+b') as hardware:
            fcntl.flock(hardware,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(hardware,fcntl.LOCK_UN)
        for owner in a['preflight_pi_owners']:
            if owner['boot_id']==a['boot_id'] and ticks(owner['pid'])==owner['start_ticks']:
                raise RuntimeError('Prior exact research owner alive')
        control=sink(root,'control');receipts=sink(root,'receipts');logs=sink(root,'logs');telemetry=sink(root,'telemetry')
        gate_owner=identity();control.json('DISPATCH_OWNER.json',gate_owner)
        cfg=small(root/'config/CONFIG.json');deadline=validate(cfg['deadline'],a)
        signal.alarm(max(1,min(335,math.ceil(remaining(deadline,hard=True)+35))))
        if remaining(deadline,hard=True)+60>(datetime.fromisoformat(a['expires_utc'])-datetime.now(timezone.utc)).total_seconds():
            raise RuntimeError('Cleanup does not fit admission')
        unit='jp-'+root.name
        if len(unit)>80 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in unit):
            raise RuntimeError('Exact bounded unit name')
        props=['CPUQuota=200%','TasksMax=64','LimitAS='+str(768*MIB),'LimitSTACK='+str(MIB),
               'RuntimeMaxSec=285','TimeoutStopSec=30','LimitCORE=0','Nice=10','LimitFSIZE='+str(32*MIB)]
        cmd=['systemd-run','--user','--unit='+unit,'--description=JustPeachy-admitted-live-entry','--wait','--pipe']
        for prop in props:cmd+=['-p',prop]
        env=dict(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
            MALLOC_ARENA_MAX='1',MALLOC_MMAP_THRESHOLD_='131072',MALLOC_TRIM_THRESHOLD_='131072',
            CUDA_VISIBLE_DEVICES='-1',ORT_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1',
            XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()),DISPLAY=':0',WAYLAND_DISPLAY='wayland-0',
            XAUTHORITY=str(Path.home()/'.Xauthority'),ALSA_CONFIG_PATH=cfg['alsa_config'])
        for k,v in env.items():cmd+=['--setenv='+k+'='+v]
        cmd+=['taskset','-c','2,3',a['python'],'-B',str(root/'code/field_saved_actions_v1.py'),'--root',str(root)]
        if remaining(deadline,hard=True)<285:
            raise RuntimeError('Worker runtime and Stop must fit the already-running common lifetime')
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
        os.set_blocking(proc.stdout.fileno(),False)
        owner=None;acked=False;failure=None;max_rss=0;min_ram=available_ram();samples=0;pending=b''
        def drain():
            nonlocal pending
            while True:
                raw=proc.stdout.read(16384)
                if not raw:return
                try:logs.write('service.log',raw,append=True)
                except BaseException:
                    pending=raw
                    raise
        try:
            next_sample=0.
            while proc.poll() is None:
                drain()
                if (root/'control/OWNER.json').exists() and not acked:
                    owner=small(root/'control/OWNER.json')
                    if owner['boot_id']!=a['boot_id'] or ticks(owner['pid'])!=owner['start_ticks']:
                        raise RuntimeError('Worker exact identity mismatch')
                    properties=subprocess.check_output(['systemctl','--user','show',unit,
                        '-p','MainPID','-p','ControlGroup','-p','CPUQuotaPerSecUSec','-p','TasksMax',
                        '-p','LimitAS','-p','LimitSTACK','-p','LimitFSIZE','-p','RuntimeMaxUSec','-p','TimeoutStopUSec'],text=True)
                    actual=dict(line.split('=',1) for line in properties.splitlines() if '=' in line)
                    if int(actual['MainPID'])!=owner['pid'] or int(actual['LimitAS'])!=768*MIB or int(actual['LimitSTACK'])!=MIB or int(actual['TasksMax'])!=64:
                        raise RuntimeError('Actual systemd properties mismatch')
                    if (actual['CPUQuotaPerSecUSec']!='2s' or int(actual['LimitFSIZE'])!=32*MIB or
                        actual['RuntimeMaxUSec'] not in ('4min 45s',) or actual['TimeoutStopUSec'] not in ('30s',)):
                        raise RuntimeError('Actual CPU/file/runtime/stop limits mismatch')
                    control.json('REQUEST.json',dict(properties=actual,raw_properties=properties,gate_owner=gate_owner,gate_envelope=dict(affinity=sorted(os.sched_getaffinity(0)),address_space=list(resource.getrlimit(resource.RLIMIT_AS)),stack=list(resource.getrlimit(resource.RLIMIT_STACK)),file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)),alarm_remaining_seconds=signal.getitimer(signal.ITIMER_REAL)[0])))
                    control.json('ACK.json',dict(owner=owner,admission_sha256=sha(root/'control/ADMISSION.json')))
                    acked=True
                now=time.monotonic()
                if now>=next_sample:
                    next_sample=now+.5;ram=available_ram();min_ram=min(ram,min_ram)
                    size=footprint(root)
                    row=dict(monotonic=now,available_ram_bytes=ram,tree=size)
                    if owner and ticks(owner['pid'])==owner['start_ticks']:
                        values={}
                        for line in Path('/proc',str(owner['pid']),'status').read_text().splitlines():
                            if line.startswith(('VmRSS:','VmSize:','Threads:')):
                                key,value=line.split(':',1);values[key]=int(value.split()[0])
                        row['worker']=values;max_rss=max(max_rss,values.get('VmRSS',0)*1024)
                    telemetry.write('gate.jsonl',encoded_line(row),append=True);samples+=1
                    if size['bytes']>layout['target_maximum_bytes'] or ram<192*MIB or shutil.disk_usage(root).free<5*1024**3:
                        raise RuntimeError('Sampled live resource/output stop')
                if remaining(deadline)<=0:raise TimeoutError('Shared work deadline')
                time.sleep(.02)
            drain()
        except BaseException as exc:
            failure=type(exc).__name__+': '+str(exc)[:1024]
            # Stop only this admitted service. Its cgroup includes the source child.
            subprocess.run(['systemctl','--user','stop','--no-block',unit],timeout=5,check=False)
            diagnostic=sink(root,'failure')
            if pending:diagnostic.write('gate.bin',pending)
            diagnostic.json('gate.json',dict(error=failure,rejected_log_bytes=len(pending),remaining_pipe_tail_retained=False))
        finally:
            try:proc.wait(timeout=min(60,max(1,remaining(deadline,hard=True))))
            except subprocess.TimeoutExpired:
                subprocess.run(['systemctl','--user','kill','--kill-whom=all','--signal=KILL',unit],timeout=5,check=False)
                proc.wait(timeout=5)
            try:
                if not pending:drain()
            finally:proc.stdout.close()
        exact_dead=owner is not None and ticks(owner['pid'])!=owner['start_ticks']
        source_dead=None
        source_owner_path=root/'source/CHILD_OWNER.json'
        if source_owner_path.exists():
            source_owner=small(source_owner_path)
            source_dead=ticks(source_owner['pid'])!=source_owner['start_ticks']
        value=dict(gate_owner=gate_owner,worker_owner=owner,worker_exact_dead=exact_dead,
            source_exact_dead=source_dead,owner_ack=acked,returncode=proc.returncode,
            pipe_closed=proc.stdout.closed,failure=failure,peak_sampled_worker_rss_bytes=max_rss,
            minimum_sampled_available_ram_bytes=min_ram,resource_samples=samples,capture_closed=capture_closed(),
            tree=footprint(root))
        value['logical_success']=not failure and proc.returncode==0 and exact_dead and source_dead is None and value['capture_closed']
        receipts.json('DISPATCH_RESULT.json',value)
        sink(root,'closure').json('gate.json',value)
        print(json.dumps(dict(logical_success=value['logical_success'],failure=failure,returncode=proc.returncode)))
        return int(not value['logical_success'])


def encoded_line(value):
    from field_live_layout_v3 import encoded
    return encoded(value)+b'\n'


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    raise SystemExit(main(parser.parse_args().root))
