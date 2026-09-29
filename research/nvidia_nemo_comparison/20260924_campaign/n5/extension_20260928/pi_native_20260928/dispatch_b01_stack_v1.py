"""Fresh native stack-reservation trial; see README_B01_STACK_V1.md."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import psutil

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OUT=LOCAL/'n5/research-extension-20260928/pi-native-20260928/b01-v4-evidence'
REMOTE='/home/peachyprototype/JustPeachy/research/nemotron-20260928'
SSH=['ssh.exe','-i','C:/Users/amiri/.ssh/just_peachy_cm5_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','HostKeyAlias=192.168.2.57','-o','ConnectTimeout=10','peachyprototype@raspberrypi.local']


def remote(code):
    encoded=base64.b64encode(code.encode()).decode()
    command="python3 -c \"import base64;exec(base64.b64decode('"+encoded+"'))\""
    r=subprocess.run(SSH+[command],capture_output=True,text=True,timeout=90,check=True)
    return json.loads(r.stdout)


def main():
    psutil.Process().cpu_affinity([14])
    sys.path.insert(0,str(HERE.parent))
    from window_guard import snapshot
    census=snapshot(LOCAL,16*1024**2)
    if OUT.exists(): raise RuntimeError('Evidence path already exists; no repeat dispatch')
    OUT.mkdir()
    (OUT/'HOST_CENSUS.json').write_text(json.dumps(census,indent=2))
    payload={name:base64.b64encode((HERE/name).read_bytes()).decode() for name in ('b01_native_short_v4.py','README_B01_STACK_V1.md')}
    code='''
import base64,hashlib,json,os,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
root=Path(REMOTE)
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43' and os.getuid()!=0
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def start(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None
owners=[]
for p in root.rglob('*OWNER*.json'):
    row=json.loads(p.read_text()); observed=start(row['pid'])
    assert not (row['boot_id']==boot and observed==row['start_ticks']),str(p)
    owners.append(dict(file=str(p),owner=row,observed_start_ticks=observed,exact_alive=False))
units=subprocess.run(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],capture_output=True,text=True,check=True).stdout
assert not units.strip(),units
assert start(1013)==569 and start(1130)==607,'Original app identity changed'
available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
free=shutil.disk_usage(root).free
assert available>=850*1024**2 and free>=5*1024**3
target_bytes=int(subprocess.check_output(['du','-sb',str(root)],text=True).split()[0])
assert target_bytes+HOST_USED+16*1024**2<1024**3
old=root/'b01-short-v3';admission=json.loads((old/'ADMISSION.json').read_text())
for row in admission['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert sha(root/'d1-a76-full-v10/RESULT.json')=='3b88191d3c075da6376526993f495db8d8c4274743db00cca14888a586356fb9'
dest=root/'b01-short-v4';dest.mkdir();(dest/'data').mkdir()
for name,blob in PAYLOAD.items():(dest/name).write_bytes(base64.b64decode(blob))
shutil.copyfile(old/'prefix12.wav',dest/'prefix12.wav')
shutil.copyfile(old/'data/n2_runtime.json',dest/'data/n2_runtime.json')
files=[]
for row in admission['files']:
    p=Path(row['path'])
    if p.is_relative_to(old):continue
    files.append(row)
for p in (dest/'prefix12.wav',dest/'data/n2_runtime.json',dest/'b01_native_short_v4.py',dest/'README_B01_STACK_V1.md'):
    files.append(dict(path=str(p),sha256=sha(p)))
now=datetime.now(timezone.utc)
admission.update(schema='native-B01-short-admission.v4',admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=8)).isoformat(),files=files,closed_owners=owners,available_ram_bytes=available,disk_free_bytes=free,python_thread_stack_bytes=1048576,prior_failure_sha256=sha(old/'RESULT.json'),changed_code=['harness process-local threading.stack_size only'])
(dest/'ADMISSION.json').write_text(json.dumps(admission,indent=2))
preflight=dict(utc=now.isoformat(),boot_id=boot,owners=owners,active_units=units,original_app_start_ticks=start(1130),available_ram_bytes=available,disk_free_bytes=free,target_bytes=target_bytes,host_window_bytes=HOST_USED,combined_with_reservation=target_bytes+HOST_USED+16*1024**2,admission=admission)
print(json.dumps(preflight))
'''
    code='REMOTE='+repr(REMOTE)+'\nPAYLOAD='+repr(payload)+'\nHOST_USED='+str(census['calculation']['window_used_bytes'])+'\n'+code
    preflight=remote(code)
    (OUT/'PREFLIGHT.json').write_text(json.dumps(preflight,indent=2))
    command='systemd-run --user --unit=jp-b01-short-v4 --wait --pipe --setenv=MALLOC_ARENA_MAX=2 -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B '+REMOTE+'/b01-short-v4/b01_native_short_v4.py'
    (OUT/'COMMAND.json').write_text(json.dumps(dict(command=command)))
    with (OUT/'launch.log').open('x') as log:
        proc=subprocess.run(SSH+[command],stdout=log,stderr=subprocess.STDOUT,timeout=220)
    (OUT/'LAUNCH_RESULT.json').write_text(json.dumps(dict(exit_code=proc.returncode,requires_independent_review=True)))
    print(json.dumps(dict(launch_exit=proc.returncode,evidence=str(OUT))),flush=True)


if __name__=='__main__':main()
