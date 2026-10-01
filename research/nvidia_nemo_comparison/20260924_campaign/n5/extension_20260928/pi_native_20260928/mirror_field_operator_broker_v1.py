"""CPU14 whole broker-tree receiver; README_FIELD_OPERATOR_BROKER_DISPATCH_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
import time
sys.dont_write_bytecode=True

MODULES=('field_host_budget_v1','field_owner_binding_v1','field_operator_session_plan_v1',
 'field_operator_broker_layout_v2','field_operator_session_plan_v3','field_live_layout_v2',
 'field_live_layout_v3','field_operator_broker_streamed_mirror_v1',
 'field_operator_broker_ssh_mirror_v1','field_operator_broker_export_v1')
BOOTSTRAP="""import os,resource,signal,sys,json,types
os.sched_setaffinity(0,{2,3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
signal.alarm(80)
n=int(sys.stdin.buffer.readline(16));assert 0<n<=262144
raw=sys.stdin.buffer.read(n);assert len(raw)==n
r=json.loads(raw);modules=r.pop('modules')
for name,source in modules.items():
 m=types.ModuleType(name);m.__file__='<admitted:'+name+'>';sys.modules[name]=m
 exec(compile(source,m.__file__,'exec'),m.__dict__)
sys.modules['field_operator_broker_export_v1'].run(r,modules)
"""

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--owner-receipt',type=Path,required=True)
    args=parser.parse_args()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    raw_owner=json.dumps(owner,separators=(',',':')).encode()
    if len(raw_owner)>512:raise ValueError('Early owner slot')
    with args.owner_receipt.open('xb') as f:
        f.write(raw_owner);f.flush()
    if args.owner_receipt.read_bytes()!=raw_owner:raise IOError('Early owner readback')
    # All project imports and admission/source reads follow registration.
    from dispatch_b01_stack_v2 import SSH,REMOTE
    from field_host_budget_v1 import HostStore,encoded,floors
    from field_operator_broker_host_v2 import checked_pins,digest,closed_owners
    from field_operator_broker_ssh_mirror_v1 import receive,receive_json,send_json,write_all
    from field_operator_broker_layout_v2 import allocation
    if args.admission.stat().st_size>131072:raise ValueError('Bounded export admission')
    a=json.loads(args.admission.read_bytes());now=datetime.now(timezone.utc)
    remaining=(datetime.fromisoformat(a['expires_utc'])-now).total_seconds()
    if not 150<=remaining<=600 or datetime.fromisoformat(a['expires_utc'])>datetime.fromisoformat('2026-10-01T17:42:44+00:00'):
        raise ValueError('Full export/closure reserve')
    full=allocation(a['session_count'])
    if a['maximum_host_output_bytes']!=full['target_maximum_bytes']+4*1024**2 or a['mirror_maximum_bytes']!=full['target_maximum_bytes']:
        raise ValueError('Full target mirror plus independent 4MiB host metadata')
    if a['pi_readonly_export'] is not True or a['capture'] is not False or a['target_payload_writes'] is not False or a['host_affinity']!=[14]:
        raise ValueError('Read-only export scope')
    if args.output.absolute()!=Path(a['output']).absolute():raise ValueError('Exact output')
    if not re.fullmatch(r'field-operator-sessions-v[1-9][0-9]*',a['source_relative']) or not re.fullmatch(r'jp-field-broker-export-v[1-9][0-9]*[.]service',a['export_unit']):
        raise ValueError('Dedicated source/export unit')
    pins=checked_pins(a['input_pins']);here=Path(__file__).absolute().parent
    required={str(here/(n+'.py')) for n in (*MODULES,'field_operator_broker_host_v2','mirror_field_operator_broker_v1','dispatch_b01_stack_v2','dispatch_geometry_v2')}
    if not required.issubset(pins) or digest(__file__)!=a['coordinator_sha256']:raise ValueError('All receiver/helper pins')
    manifest_path=Path(a['manifest'])
    if str(manifest_path) not in pins or manifest_path.stat().st_size>262144:raise ValueError('Independent closed-tree census pin')
    manifest=json.loads(manifest_path.read_bytes())
    if manifest['policy_sha256']!=a['policy_sha256'] or manifest['owners']!=a['live_owners']:
        raise ValueError('Closed tree binding')
    files={k:manifest['files'][k] for k in sorted(manifest['files'])}
    modules={n:(here/(n+'.py')).read_text(encoding='utf-8') for n in MODULES}
    if {n:hashlib.sha256(s.encode()).hexdigest() for n,s in modules.items()}!=a['module_sha256']:
        raise ValueError('Injected module pins')
    request=encoded(dict(admission=a,files=files,modules=modules))
    if len(request)>262144:raise ValueError('Original framed request limit')
    floors(a['maximum_host_output_bytes'])
    store=HostStore(args.output).create({'ADMISSION.json':encoded(a),'REGISTERED_OWNER.json':encoded(owner)})
    command=['systemd-run','--user','--unit='+a['export_unit'],'--description=JustPeachy-broker-closed-tree-export','--wait','--pipe','--quiet']
    for prop in ('CPUQuota=200%','TasksMax=64','LimitAS=134217728','LimitSTACK=1048576',
                 'RuntimeMaxSec=90','TimeoutStopSec=10','LimitCORE=0','LimitFSIZE=0','Nice=10'):
        command+=['-p',prop]
    command+=['--setenv=OPENBLAS_NUM_THREADS=1','--setenv=OMP_NUM_THREADS=1','--setenv=CUDA_VISIBLE_DEVICES=',
              'taskset','-c','2,3','python3','-u','-B','-c',BOOTSTRAP]
    threading.stack_size(1048576)
    began=time.monotonic();stderr=bytearray();overflow=threading.Event();expired=threading.Event()
    stop_lock=threading.Lock();stop_attempted=False;stop_error=[]
    proc=subprocess.Popen(SSH+['exec '+shlex.join(command)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    def stop_owned():
        nonlocal stop_attempted
        with stop_lock:
            if stop_attempted:return
            stop_attempted=True
        try:subprocess.run(SSH+['systemctl --user stop --no-block '+a['export_unit']],
            timeout=10,check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except BaseException as exc:stop_error.append(type(exc).__name__+': '+str(exc)[:256])
        if proc.poll() is None:proc.kill()
    def drain():
        while True:
            part=proc.stderr.read(4096)
            if not part:return
            room=65536-len(stderr);stderr.extend(part[:room])
            if len(part)>room:overflow.set();stop_owned();return
    def timeout():
        if proc.poll() is None:expired.set();stop_owned()
    reader=threading.Thread(target=drain,daemon=True);reader.start()
    timer=threading.Timer(110,timeout);timer.daemon=True;timer.start()
    remote_owner=None;result=dict(status='FAILED_PRESERVED')
    try:
        write_all(proc.stdin,str(len(request)).encode()+b'\n'+request);proc.stdin.flush()
        ready=receive_json(proc.stdout,began+105);remote_owner=ready['owner']
        if set(remote_owner)!={'pid','start_ticks','boot_id'} or remote_owner['boot_id']!=a['boot_id'] or ready['source']!=REMOTE+'/'+a['source_relative']:
            raise ValueError('Exact exporter identity/source')
        store.json('PREFLIGHT.json',ready)
        send_json(proc.stdin,dict(ack=remote_owner));proc.stdin.close()
        def closed():
            if proc.stdout.read(1)!=b'' or proc.wait(timeout=max(.1,began+105-time.monotonic()))!=0:
                raise RuntimeError('Unexpected stream terminal')
            reader.join(2)
            if reader.is_alive() or overflow.is_set() or expired.is_set():raise RuntimeError('Stream watchdog/readers')
            result['remote_closure']=closed_owners([remote_owner])
        data=receive(store,args.output.with_name(args.output.name+'-mirror'),proc.stdout,files,
            deadline=began+105,maximum_bytes=a['mirror_maximum_bytes'],
            verify_process_closed=closed,source_label=ready['source'])
        result.update(data,status='PASS_SSH_CLOSED_BROKER_TREE_MIRROR_ONLY')
    except BaseException as exc:
        stop_owned()
        result['error']=type(exc).__name__+': '+str(exc)[:2048]
    finally:
        if proc.poll() is None:stop_owned()
        proc.wait(timeout=5);timer.cancel();timer.join(2);reader.join(2)
        for pipe in (proc.stdin,proc.stdout,proc.stderr):
            if not pipe.closed:pipe.close()
        if remote_owner is not None and 'remote_closure' not in result:
            try:result['remote_closure']=closed_owners([remote_owner])
            except BaseException as exc:result['closure_error']=type(exc).__name__+': '+str(exc)[:512]
        store.write('worker.raw',bytes(stderr))
        result.update(elapsed_seconds=time.monotonic()-began,ssh_returncode=proc.returncode,
            stderr_overflow=overflow.is_set(),watchdog_expired=expired.is_set(),
            threads_joined=not reader.is_alive() and not timer.is_alive(),remote_owner=remote_owner,
            own_stop_attempted=stop_attempted,own_stop_error=stop_error)
        store.json('RESULT.json',result)
        store.json('coordinator-closure.json',dict(owner=owner,work_complete=True,
            ssh_reaped=True,pipes_closed=True,threads_joined=result['threads_joined'],
            logical_success=result['status']=='PASS_SSH_CLOSED_BROKER_TREE_MIRROR_ONLY'))
    print(json.dumps({k:result.get(k) for k in ('status','error','files','bytes','data_chunks','elapsed_seconds','ssh_returncode')}))
    return int(result['status']!='PASS_SSH_CLOSED_BROKER_TREE_MIRROR_ONLY')
if __name__=='__main__':raise SystemExit(main())
