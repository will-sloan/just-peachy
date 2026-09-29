"""Dispatch one fresh bounded native recipe job. See README_XVF_RESTART_V1.md."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import psutil
from dispatch_b01_stack_v2 import SSH, REMOTE, LOCAL

HERE = Path(__file__).resolve().parent
PRIVATE = LOCAL/'n5/research-extension-20260928/pi-native-20260928'


def remote(code):
    response = subprocess.run(SSH+["python3 -"], input=code, capture_output=True, text=True, encoding="utf-8", timeout=90)
    if response.returncode: raise RuntimeError("Remote preflight failed: "+response.stderr[-4000:])
    return json.loads(response.stdout)

def main():
    p = argparse.ArgumentParser()
    p.set_defaults(profile='native_v3_delayed',kernel='a76',reference='')
    p.add_argument('--reset-once',action='store_true')
    p.add_argument('--census',type=Path,required=True)
    args=p.parse_args()
    if not args.reset_once:p.error('Explicit one-shot recovery intent required')
    args.mode='reset';args.run_id='xvf-restart-v1'
    bound_names=('xvf_restart_v1.py','xvf_restart_gate_v1.py','README_XVF_RESTART_V1.md','dispatch_xvf_restart_v1.py')
    if args.reference: assert re.fullmatch(r'd1-geometry-[a-z0-9-]+', args.reference)
    psutil.Process().cpu_affinity([14])
    sys.path.insert(0, str(HERE.parent))
    from window_guard import window, budget, payload_inventory
    window()
    assert time.time()-args.census.stat().st_mtime < 900, 'Need fresh comprehensive host census'
    census = json.loads(args.census.read_text(encoding='utf-8'))
    worker = json.loads((LOCAL/'supervision/worker.json').read_text())
    assert worker['status'] == 'COMPLETED' and worker['pid'] == 55636 and worker['create_time'] == 1790637870.806714
    for identity in (census['supervisor']['host'], census['supervisor']['launcher']):
        try:
            process = psutil.Process(identity['pid'])
            assert abs(process.create_time()-identity['create_time']) > .001, 'Exact host owner active'
        except psutil.NoSuchProcess:
            pass
    used = 0
    for relative in ('n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928'):
        inv = payload_inventory(LOCAL/relative)
        assert not inv['errors'] and not inv['reparse_not_traversed']
        used += inv['total_logical_bytes']
    delta = used-census['calculation']['window_used_bytes']
    assert delta >= 0
    free = {d:shutil.disk_usage(d+'/').free for d in ('C:','G:')}
    calculation = budget(census['calculation']['existing_bytes']+delta, used, 16*1024**2, free, 50)
    out = PRIVATE/(args.run_id+'-evidence'); out.mkdir()
    (out/'HOST_RECHECK.json').write_text(json.dumps(dict(calculation=calculation, free=free,
          census=str(args.census), census_sha256=hashlib.sha256(args.census.read_bytes()).hexdigest()), indent=2), encoding='utf-8')

    paths={name:HERE/name for name in bound_names}
    payload={name:base64.b64encode(path.read_bytes()).decode() for name,path in paths.items()}
    code = r"""
import os,json,hashlib,shutil,base64,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
os.sched_setaffinity(0,{3});r=Path(REMOTE)
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43' and os.getuid()!=0
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def start(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
owners=[]
for p in r.rglob('*OWNER*.json'):
 o=json.loads(p.read_text());t=start(o['pid']);assert not(o['boot_id']==boot and t==o['start_ticks'])
 owners.append(dict(file=str(p),owner=o,observed_start_ticks=t,exact_alive=False))
units=subprocess.run(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],capture_output=True,text=True,check=True).stdout
assert not units.strip() and start(1013)==569 and start(1130)==607
available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
free=shutil.disk_usage(r).free;assert available>=850*1024**2 and free>=5*1024**3
used=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]);assert HOST_USED+used+16*1024**2<1024**3
old=r/'b01-fir-integration-v1';prior=json.loads((old/'ADMISSION.json').read_text())
for row in prior['files']:assert sha(Path(row['path']))==row['sha256']
source=Path(prior['prototype'])
assert source==r/'shared-app-b01-fir-v1/prototype'
config=Path.home()/'JustPeachy/data/live_config.json'
assert sha(config)=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
tool=Path.home()/'JustPeachy/tools/native_xvf_usb/bin/xvf_host'
assert sha(tool)=='8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982'
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
d=r/RUN_ID;d.mkdir()
for name,blob in PAYLOAD.items():(d/name).write_bytes(base64.b64decode(blob))
files=list(prior['files'])
for f in [config,tool,*[d/name for name in PAYLOAD]]:files.append(dict(path=str(f),sha256=sha(f)))
if MODE=='reset':
 (d/'live_config.json').write_bytes(config.read_bytes())
 files.append(dict(path=str(d/'live_config.json'),sha256=sha(d/'live_config.json')))
now=datetime.now(timezone.utc);assert now+timedelta(minutes=8)<datetime.fromisoformat('2026-10-01T17:47:34+00:00')
a=dict(schema='native-xvf-restart.v1',ui_mode='xvf_restart',mode=MODE,physically_ready_attested=MODE=='user',capture_seconds=12 if MODE=='user' else 0,boot_id=boot,prototype=str(source),files=files,admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=8)).isoformat(),closed_owners=owners,available_ram_bytes=available,disk_free_bytes=free,address_space_max_bytes=768*1024**2,cpus=[2,3],cpu_quota_percent=200,native_threads=1,startup_stack_limit_bytes=1048576,runtime_seconds=180,stop_timeout_seconds=90,output_max_bytes=16*1024**2,capture=MODE=='user',playback=False,audio_saved=False,models_loaded=False)
(d/'ADMISSION.json').write_text(json.dumps(a,indent=2))
print(json.dumps(dict(admission=a,target_bytes=used,host_window_bytes=HOST_USED)))
"""
    prefix='\n'.join(k+'='+repr(v) for k,v in dict(REMOTE=REMOTE,RUN_ID=args.run_id,PAYLOAD=payload,HOST_USED=used,MODE=args.mode).items())
    x=remote(prefix+'\n'+code)
    (out/'PREFLIGHT.json').write_text(json.dumps(x,indent=2),encoding='utf-8')
    command='python3 '+REMOTE+'/'+args.run_id+'/xvf_restart_gate_v1.py'
    (out/'COMMAND.json').write_text(json.dumps(dict(command=command)),encoding='utf-8')
    with (out/'launch.log').open('x',encoding='utf-8') as f:run=subprocess.run(SSH+[command],stdout=f,stderr=subprocess.STDOUT,timeout=310)
    (out/'LAUNCH_RESULT.json').write_text(json.dumps(dict(exit_code=run.returncode,requires_independent_review=True)),encoding='utf-8')
    print(json.dumps(dict(run_id=args.run_id,exit_code=run.returncode,evidence=str(out))))


if __name__=='__main__':main()
