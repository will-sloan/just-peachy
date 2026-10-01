"""Read-only user reconnect inspection; README_USER_RECONNECT_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys

NATIVE = r"""
import os,resource,signal,json,sys,hashlib,subprocess,shutil,fcntl,datetime
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,)*2)
signal.alarm(30)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
print(json.dumps(dict(utility_owner=owner)),file=sys.stderr,flush=True)
home=Path.home();r=home/'JustPeachy/research/nemotron-20260928'
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
assert os.uname().machine=='aarch64'
mem={k.rstrip(':'):int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines())}
assert 1500000000<mem['MemTotal']<2200000000 and mem['MemAvailable']>=192*1024**2
assert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320
assert shutil.disk_usage(r).free>=5*1024**3
def command(argv,env=None):
 q=subprocess.run(argv,capture_output=True,text=True,timeout=5,env=env)
 assert len(q.stdout.encode())+len(q.stderr.encode())<=32768
 return dict(returncode=q.returncode,stdout=q.stdout,stderr=q.stderr)
pins={'JustPeachy/install/current.json':'fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3','JustPeachy/data/live_config.json':'568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395','.config/kanshi/config':'c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b'}
files=[]
for rel,pin in pins.items():
 p=home/rel
 assert p.is_file() and p.stat().st_size<=65536
 raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 files.append(dict(path=str(p),bytes=len(raw),sha256=digest,pre_shutdown_pin_matches=digest==pin))
capture={}
for p in sorted(Path('/proc/asound').glob('card*/pcm*c/sub*/status')):
 raw=p.read_text();assert len(raw)<=4096;capture[str(p)]=raw.strip()
assert len(capture)<=32
leases=[]
for p in (r/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):
 with p.open('rb') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
 leases.append(str(p))
processes=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==owner['pid']:continue
 try:
  with (p/'cmdline').open('rb') as f:raw=f.read(8193)
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if b'JustPeachy' not in raw and b'just-peachy' not in raw:continue
 assert len(raw)<=8192 and len(processes)<64
 t=ticks(int(p.name))
 if t is not None:processes.append(dict(pid=int(p.name),start_ticks=t,boot_id=boot,cmdline=raw.replace(b'\0',b' ').decode(errors='replace')))
env=dict(os.environ,XDG_RUNTIME_DIR='/run/user/1000',WAYLAND_DISPLAY='wayland-0')
value=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),utility_owner=owner,boot_id=boot,
 previous_boot_changed=boot!='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43',
 files=files,capture=capture,free_leases=leases,current_project_processes=processes,
 research_units=command(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*']),
 display=command(['wlr-randr'],env),
 sound_cards=Path('/proc/asound/cards').read_text(),
 available_ram_bytes=mem['MemAvailable'],target_free_bytes=shutil.disk_usage(r).free,
 native_write=False,capture_started=False,physical_touch_proven=False,offline_proven=False)
print(json.dumps(value),flush=True)
"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    O=args.output
    p=psutil.Process()
    (O/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(
        pid=p.pid,create_time=p.create_time(),affinity=[14])))
    sys.dont_write_bytecode=True
    scope=json.loads((O/'HOST_SCOPE_V1.json').read_bytes())
    now=datetime.datetime.now(datetime.timezone.utc)
    assert now+datetime.timedelta(seconds=60)<datetime.datetime.fromisoformat(scope['expires_utc'])
    assert now+datetime.timedelta(seconds=60)<datetime.datetime(2026,10,1,17,42,44,tzinfo=datetime.timezone.utc)
    assert scope['user_reported_reconnection'] is True
    from field_operator_broker_host_v2 import ssh_phase,process_phase
    from dispatch_b01_stack_v2 import SSH
    result=ssh_phase(['python3','-u','-B','-'],payload=NATIVE.encode(),timeout=40,maximum=262144)
    out=result.pop('stdout');err=result.pop('stderr')
    (O/'INSPECT_STDOUT.bin').open('xb').write(out)
    (O/'INSPECT_STDERR.bin').open('xb').write(err)
    (O/'INSPECT_PHASE.json').open('x').write(json.dumps(result))
    lines=err.splitlines()
    if lines:
        owner=json.loads(lines[0])['utility_owner']
        (O/'NATIVE_OWNER.json').open('x').write(json.dumps(owner))
    assert result['returncode']==0 and result['fault'] is None and result['readers_joined'] and result['ssh_reaped']
    value=json.loads(out);assert value['utility_owner']==owner
    from field_local_manager_owners_v1 import identity
    identity(owner)
    # PID absence is conservative if the numeric PID was already reused.
    command='test ! -e /proc/'+str(owner['pid'])
    closed=process_phase(SSH+[command],timeout=10,maximum=16384)
    cout=closed.pop('stdout');cerr=closed.pop('stderr')
    (O/'CLOSURE_STDOUT.bin').open('xb').write(cout)
    (O/'CLOSURE_STDERR.bin').open('xb').write(cerr)
    (O/'CLOSURE_PHASE.json').open('x').write(json.dumps(closed))
    assert closed['returncode']==0 and closed['fault'] is None and closed['readers_joined'] and closed['ssh_reaped']
    value['utility_pid_absent_after_ssh']=True
    (O/'RESULT.json').open('x').write(json.dumps(value))
    print(json.dumps(value))


if __name__=='__main__':
    main()
