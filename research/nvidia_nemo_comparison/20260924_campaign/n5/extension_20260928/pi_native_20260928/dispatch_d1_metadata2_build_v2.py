"""Dispatch one fresh bounded native recipe job. See README_D1_METADATA2_V2.md."""
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
    p.add_argument('--run-id', required=True)
    p.add_argument('--census', type=Path, required=True)
    args = p.parse_args()
    assert args.run_id == 'd1-metadata2-build-v2'
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
    paths = {name:HERE/name for name in ('build_d1_metadata2_v2.py','README_D1_METADATA2_V2.md')}
    payload = {k:base64.b64encode(v.read_bytes()).decode() for k,v in paths.items()}
    code = "\nimport base64,hashlib,json,os,shutil,subprocess\nfrom pathlib import Path\nfrom datetime import datetime,timezone,timedelta\nos.sched_setaffinity(0,{3});root=Path(REMOTE)\nboot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()\nassert boot=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43' and os.getuid()!=0\nassert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()\ndef sha(p):\n with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()\ndef start(pid):\n try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])\n except FileNotFoundError:return None\nowners=[]\nfor p in root.rglob('*OWNER*.json'):\n row=json.loads(p.read_text());s=start(row['pid']);assert not(row['boot_id']==boot and s==row['start_ticks'])\n owners.append(dict(file=str(p.relative_to(root)),owner=row,observed_start_ticks=s,exact_alive=False))\nunits=subprocess.run(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],capture_output=True,text=True,check=True).stdout;assert not units.strip()\nassert start(1013)==569 and start(1130)==607\navailable=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'));free=shutil.disk_usage(root).free\nassert available>=850*1024**2 and free>=5*1024**3\nused=int(subprocess.check_output(['du','-sb',str(root)],text=True).split()[0]);assert used+HOST_USED+16*1024**2<1024**3\nassert sha(root/'metadata-native-v1/output/libnemo_speech_asr.so')=='5d219c3cd388703e830d4be6491b75ff023c4ba9c277bf2e082f19b542979377'\ndest=root/RUN_ID;dest.mkdir()\nfor name,blob in PAYLOAD.items():(dest/name).write_bytes(base64.b64decode(blob))\nfiles={n:sha(dest/n) for n in PAYLOAD}\nfiles['../metadata-native-v1/output/runtime.a']=sha(root/'metadata-native-v1/output/runtime.a')\nfiles['../metadata-native-v1/output/libnemo_speech_asr.so']=sha(root/'metadata-native-v1/output/libnemo_speech_asr.so')\nfiles['../scheduler-native-v1/bundle.tar.json']=sha(root/'scheduler-native-v1/bundle.tar.json')\nfiles['../metadata-native-v1/session.cpp']=sha(root/'metadata-native-v1/session.cpp')\nfiles['../metadata-native-v1/BUILD_RESULT.json']=sha(root/'metadata-native-v1/BUILD_RESULT.json')\nfiles['../d1-lru-build-v1/output/sortformer_model.cpp.o']=sha(root/'d1-lru-build-v1/output/sortformer_model.cpp.o')\nfiles['../d1-lru-build-v1/output/libnemo_speech_asr.so']=sha(root/'d1-lru-build-v1/output/libnemo_speech_asr.so')\nnow=datetime.now(timezone.utc);assert now+timedelta(minutes=12)<datetime.fromisoformat('2026-10-01T17:47:34+00:00')\nadmission=dict(schema='native-D1-lru-build.v1',boot_id=boot,cpus=[2,3],address_space_max_bytes=768*1024**2,admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),runtime_seconds=600,files=files,output_max_bytes=16*1024**2,available_ram_bytes=available,disk_free_bytes=free,closed_owners=owners,build_only=True,downloads=False,gpu=False,original_app_unchanged=True)\n(dest/'BUILD_ADMISSION.json').write_text(json.dumps(admission,indent=2))\nprint(json.dumps(dict(admission=admission,target_bytes=used,host_window_bytes=HOST_USED)))\n"
    prefix = '\n'.join(k+'='+repr(v) for k,v in dict(REMOTE=REMOTE, PAYLOAD=payload, HOST_USED=used,
                       RUN_ID=args.run_id).items())
    preflight = remote(prefix+'\n'+code)
    (out/'PREFLIGHT.json').write_text(json.dumps(preflight,indent=2),encoding='utf-8')
    command = ('systemd-run --user --unit=jp-'+args.run_id+' --wait --pipe '
               '-p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 '
               'taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B '
               +REMOTE+'/'+args.run_id+'/build_d1_metadata2_v2.py')
    (out/'COMMAND.json').write_text(json.dumps(dict(command=command)),encoding='utf-8')
    with (out/'launch.log').open('x',encoding='utf-8') as log:
        process = subprocess.run(SSH+[command],stdout=log,stderr=subprocess.STDOUT,timeout=630)
    (out/'LAUNCH_RESULT.json').write_text(json.dumps(dict(exit_code=process.returncode,requires_independent_review=True)),encoding='utf-8')
    print(json.dumps(dict(run_id=args.run_id,exit_code=process.returncode,evidence=str(out))))


if __name__ == '__main__':
    main()
