"""CPU14 whole-live coordinator. Read README_FIELD_TRANSFER_UI_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time

from dispatch_b01_stack_v2 import SSH,REMOTE
from dispatch_geometry_v2 import remote
from field_host_budget_v1 import HostStore,encoded,floors

HERE=Path(__file__).resolve().parent
RUN='field-transfer-ui-v2'
LIMITS=dict(metadata=(512*1024,256*1024,12),failure=(128*1024,65536,4),closure=(32768,16384,4))


def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--owner-receipt',type=Path,required=True)
    args=parser.parse_args()
    # Register before plan reads or host-store validation; exclusive caller-reserved slot.
    early_owner=dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time(),affinity=[14])
    raw_owner=encoded(early_owner)
    if len(raw_owner)>512:raise ValueError('Bounded early owner receipt')
    with args.owner_receipt.open('xb') as handle:
        handle.write(raw_owner);handle.flush()
    if args.owner_receipt.read_bytes()!=raw_owner:raise IOError('Early owner readback')
    if args.plan.stat().st_size>1024**2:raise ValueError('Bounded exact plan required')
    plan=json.loads(args.plan.read_bytes());a=plan['admission']
    now=datetime.now(timezone.utc)
    if not 590<=(datetime.fromisoformat(a['expires_utc'])-now).total_seconds()<=600:raise ValueError('Fresh full time admission')
    if a['combined_request_bytes']!=297706584 or a['host_maximum_bytes']!=150950444 or a['target_maximum_bytes']!=146756140:
        raise ValueError('Whole independent maxima required')
    if a['output_root']!=REMOTE+'/'+RUN:raise ValueError('Exact fresh target')
    required={str(HERE/n) for n in ('dispatch_field_transfer_v2.py','stage_field_transfer_v2.py','mirror_field_transfer_v2.py','field_transfer_export_v2.py','field_host_budget_v1.py','field_transfer_ssh_mirror_v1.py','field_transfer_streamed_mirror_v1.py')}
    if not required.issubset({str(Path(r['path'])) for r in plan['host_pins']}):raise ValueError('Required coordinator/helper pins omitted')
    for row in plan['host_pins']:
        q=Path(row['path'])
        if q.is_symlink() or q.stat().st_size!=row['bytes'] or digest(q)!=row['sha256']:raise ValueError('Host input pin mismatch')
    if digest(__file__)!=plan['coordinator_sha256']:raise ValueError('Coordinator bytes not admitted')
    if time.time()-Path(plan['census']).stat().st_mtime>900:raise ValueError('Stale host census')
    for owner in plan['prior_host_owners']:
        try:created=psutil.Process(owner['pid']).create_time()
        except psutil.NoSuchProcess:created=None
        if created is not None and abs(created-owner['create_time'])<.001:raise ValueError('Healthy prior host owner; leave it alone')
    floors(a['host_maximum_bytes'])
    output=Path(plan['output']).absolute()
    owner=dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time(),affinity=[14])
    store=HostStore(output,LIMITS).create({'ADMISSION.json':encoded(plan),'REGISTERED_OWNER.json':encoded(owner)})
    raw_attempted=set();success=False;stage=None;live=None;backup=None;failure=None;proc=None;buffers=[bytearray(),bytearray()];overflow=threading.Event();readers=[]
    try:
        stage_files={}
        for row in plan['stage_files']:
            raw=Path(row['local']).read_bytes()
            if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Staged input drift')
            stage_files[row['relative']]=dict(base64=base64.b64encode(raw).decode(),sha256=row['sha256'])
        stage_source=(HERE/'stage_field_transfer_v2.py').read_text(encoding='utf-8')
        request=encoded(dict(admission=a,stage_files=stage_files))
        if len(request)>3*1024**2:raise ValueError('Compact staging payload exceeded')
        stage=remote(stage_source+'\nREQUEST='+repr(json.loads(request))+'\nprint(json.dumps(stage(REQUEST)))')
        store.write('PREFLIGHT.json',encoded(stage))
        # Stage returned naturally; confirm exact identity before any live worker.
        observation=remote("O="+repr(stage['owner'])+"\n"+CLOSED_ONE)
        store.write('JOB_ENVELOPE.json',encoded(dict(stage_closure=observation,capture_authority=a['authority_sha256'])))
        root=a['output_root'];python=a['python']
        command='exec '+shlex.join(['taskset','-c','3',python,'-B',root+'/code/field_transfer_gate_v2.py','--root',root])
        store.write('LAUNCH.json',encoded(dict(target=root,unit='jp-'+RUN,gate='field_transfer_gate_v2.py',maximum_live_wait_seconds=345)))
        proc=subprocess.Popen(SSH+[command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        def read(index,pipe):
            while True:
                part=pipe.read(4096)
                if not part:return
                remaining=65536-len(buffers[index]);buffers[index].extend(part[:remaining])
                if len(part)>remaining:overflow.set();return
        for i,pipe in enumerate((proc.stdout,proc.stderr)):
            t=threading.Thread(target=read,args=(i,pipe),name='live-ssh-reader-'+str(i),daemon=True);t.start();readers.append(t)
        end=time.monotonic()+345
        while proc.poll() is None and time.monotonic()<end and not overflow.is_set():
            floors();time.sleep(.1)
        if proc.poll() is None:
            subprocess.run(SSH+['systemctl --user stop --no-block jp-'+RUN],timeout=10,check=False,capture_output=True)
            try:proc.wait(timeout=35)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)
                raise TimeoutError('Live SSH transport failed to close after owned-unit Stop')
            raise TimeoutError('Live work output or time boundary reached')
        for t in readers:t.join(3)
        if any(t.is_alive() for t in readers):raise RuntimeError('Live pipe readers remain')
        if overflow.is_set():raise RuntimeError('Bounded live SSH output overflow')
        raw_attempted.add('worker.raw');store.write('worker.raw',bytes(buffers[0]))
        raw_attempted.add('coordinator.raw');store.write('coordinator.raw',bytes(buffers[1]))
        # Exact ownership closure and independently hashed actual closed tree.
        live=remote("ROOT="+repr(root)+"\n"+CLOSED_TREE)
        store.write('CENSUS.json',encoded(live))
        manifest_path=output/'metadata/CENSUS.json'
        modules=('field_host_budget_v1','field_transfer_streamed_mirror_v1','field_transfer_ssh_mirror_v1','field_transfer_export_v2')
        mirror_a=dict(expires_utc=a['expires_utc'],pi_readonly_export=True,capture=False,
            host_affinity=[14],maximum_host_output_bytes=150950444,mirror_maximum_bytes=146756140,
            target_payload_writes=False,output=str(output.with_name(output.name+'-backup')),manifest=str(manifest_path),
            input_pins=[],module_sha256={n:hashlib.sha256((HERE/(n+'.py')).read_text(encoding='utf-8').encode()).hexdigest() for n in modules},
            coordinator_sha256=digest(HERE/'mirror_field_transfer_v2.py'),boot_id=a['boot_id'],
            source_relative=RUN,install_sha256=a['install_sha256'],live_config_sha256=a['live_config_sha256'],
            closed_owners=a['preflight_pi_owners'],live_owners=live['owners'],dispatch_result_sha256=live['dispatch_result_sha256'])
        # HostStore's bounded REVIEW slot holds the fresh closed-tree export admission.
        store.write('REVIEW.json',encoded(mirror_a))
        mirror=subprocess.run([sys.executable,'-B',str(HERE/'mirror_field_transfer_v2.py'),'--admission',
            str(output/'metadata/REVIEW.json'),'--output',mirror_a['output']],capture_output=True,text=True,timeout=120)
        backup=dict(returncode=mirror.returncode,stdout=mirror.stdout[-8192:],stderr=mirror.stderr[-8192:])
        success=proc.returncode==0 and live['dispatch']['logical_success'] and mirror.returncode==0
    except BaseException as exc:
        failure=type(exc).__name__+': '+str(exc)[:2048]
    finally:
        if proc is not None and proc.poll() is None:
            subprocess.run(SSH+['systemctl --user stop --no-block jp-'+RUN],timeout=10,check=False,capture_output=True)
            try:proc.wait(timeout=35)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        for t in readers:t.join(3)
        if proc:
            for pipe in (proc.stdout,proc.stderr):
                if not pipe.closed:pipe.close()
        for name,index in (('worker.raw',0),('coordinator.raw',1)):
            if name not in raw_attempted:
                raw_attempted.add(name);store.write(name,bytes(buffers[index]))
        result=dict(logical_success=success,failure=failure,stage=stage,live_returncode=None if proc is None else proc.returncode,
            mirror=backup,readers_joined=all(not t.is_alive() for t in readers))
        store.write('RESULT.json',encoded(result))
        store.write('coordinator-closure.json',encoded(dict(owner=owner,work_complete=True,logical_success=success,
            ssh_reaped=proc is None or proc.poll() is not None,pipes_closed=True,readers_joined=result['readers_joined'])))
    print(json.dumps(dict(logical_success=success,failure=failure,mirror=backup)))
    return int(not success)


CLOSED_ONE=r'''import os,json,resource,signal
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2);resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2);resource.setrlimit(resource.RLIMIT_FSIZE,(0,0));signal.alarm(10)
try:t=int(Path('/proc',str(O['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])
except FileNotFoundError:t=None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot!=O['boot_id'] or t!=O['start_ticks']
me=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot)
print(json.dumps(dict(owner=O,observed_start_ticks=t,exact_alive=False,utility_owner=me)))
'''

CLOSED_TREE=r'''import os,json,hashlib,fcntl,signal,resource
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2);resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2);resource.setrlimit(resource.RLIMIT_FSIZE,(0,0));signal.alarm(30)
root=Path(ROOT);boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
owners=[json.loads((root/'control/MANIFEST.json').read_bytes())['stage_owner']]
for rel in ('control/DISPATCH_OWNER.json','control/OWNER.json','control/REGISTERED_OWNER.json','source/CHILD_OWNER.json'):
 p=root/rel
 if p.exists():owners.append(json.loads(p.read_bytes()))
for o in owners:assert o['boot_id']!=boot or ticks(o['pid'])!=o['start_ticks']
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
with (root.parent/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
 fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 files={};dirs=[]
 for base,names,members in os.walk(root,followlinks=False):
  d=Path(base);assert not d.is_symlink()
  dirs.append('' if d==root else d.relative_to(root).as_posix())
  for name in members:
   p=d/name;assert p.is_file() and not p.is_symlink() and p.stat().st_size<=33554432
   files[p.relative_to(root).as_posix()]=dict(bytes=p.stat().st_size,sha256=sha(p))
  assert len(files)<=256 and len(dirs)<=64
 assert sum(v['bytes'] for v in files.values())+len(dirs)*65536<=146756140
 dispatch=json.loads((root/'receipts/DISPATCH_RESULT.json').read_bytes())
 print(json.dumps(dict(files=files,directories=dirs,owners=owners,dispatch=dispatch,
     dispatch_result_sha256=sha(root/'receipts/DISPATCH_RESULT.json'),utility_owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot))))
'''


if __name__=='__main__':
    raise SystemExit(main())
