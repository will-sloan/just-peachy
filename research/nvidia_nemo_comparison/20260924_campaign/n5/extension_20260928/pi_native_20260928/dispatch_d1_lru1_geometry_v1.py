"""Dispatch one fresh bounded native recipe job. See README_D1_LRU1_CHECKS_V1.md."""
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
    p.add_argument('--profile', choices=['native_v3_streaming','native_v3_delayed'], required=True)
    p.add_argument('--kernel', choices=['generic','a76'], required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--census', type=Path, required=True)
    p.add_argument('--reference', default='')
    args = p.parse_args()
    assert args.run_id=='d1-geometry-delayed-lru1-v1' and args.profile=='native_v3_delayed' and args.kernel=='a76'
    assert (args.kernel == 'a76') == bool(args.reference)
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
    paths = {name:HERE/name for name in ('d1_geometry_v1.py','README_GEOMETRY_V2.md','README_D1_LRU1_CHECKS_V1.md')}
    paths['nemotron_diarization.py'] = PRIVATE/'native-profiles-v2/nemotron_diarization.py'
    assert hashlib.sha256(paths['nemotron_diarization.py'].read_bytes()).hexdigest() == '2537162df8ac8ccdd89c45c3f26fa12ef48519867a0474bf4be39e4667d75e37'
    payload = {k:base64.b64encode(v.read_bytes()).decode() for k,v in paths.items()}
    code = '''
import base64,hashlib,json,os,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
os.sched_setaffinity(0,{3})
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
 row=json.loads(p.read_text());observed=start(row['pid'])
 assert not(row['boot_id']==boot and observed==row['start_ticks']),str(p)
 owners.append(dict(file=str(p),owner=row,observed_start_ticks=observed,exact_alive=False))
units=subprocess.run(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],capture_output=True,text=True,check=True).stdout
assert not units.strip(),units
assert start(1013)==569 and start(1130)==607
available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
free=shutil.disk_usage(root).free
assert available>=850*1024**2 and free>=5*1024**3
target_bytes=int(subprocess.check_output(['du','-sb',str(root)],text=True).split()[0])
assert target_bytes+HOST_USED+16*1024**2<1024**3
old=root/'d1-metadata-full-v12'
assert sha(old/'RESULT_V12.json')=='db84e3fea26f5326a40a0a4958737244c7ece8f4da8d1d910fd40eb5a547218c'
source=root/'scheduler-native-v1/inputs/source/src/asr'
assert sha(source/'c_api.cpp')=='d031ee096eefc0d5ed597bd8897fe05d0fe538fbe4f2119d2533a606400862fe'
assert sha(source/'diar/aosc_state.h')=='c14f4e0ee44d27951a2be5d7798d8606ab01a96fda91872776e0ff204b76da85'
lru=root/'d1-lru1-build-v1'
build_review=json.loads((lru/'BUILD_REVIEW.json').read_text())
assert sha(lru/'output/libnemo_speech_asr.so')==build_review['library_sha256']
assert sha(lru/'BUILD_RESULT.json')==build_review['result_sha256']
assert json.loads((lru/'BUILD_REVIEW.json').read_text())['status']=='PASS_D1_LRU1_BUILD_ONLY'
dest=root/RUN_ID;dest.mkdir()
for row in json.loads((old/'INPUTS_V12.json').read_text())['files']:
 name=row['name'];p=old/name
 assert sha(p)==row['sha256'],name
 if not(name in ('D1.gguf','source.wav') or name.startswith('nemo-arm64/')):continue
 if name=='nemo-arm64/lib/libnemo_speech_asr.so':p=lru/'output/libnemo_speech_asr.so'
 if KERNEL=='generic' and '/libggml-cpu.so' in name:
  p=root/'d1-smoke-v3'/name
  assert sha(p)=='cab8b22fbec1cd0204d9ca4b6997670f99290776ad34859ec0cd3c92ae77bd24'
 q=dest/name;q.parent.mkdir(parents=True,exist_ok=True);os.link(p,q)
for name,blob in PAYLOAD.items():(dest/name).write_bytes(base64.b64decode(blob))
stream=PROFILE=='native_v3_streaming'
geometry=dict(chunk_frames=13 if stream else 264,right_context_frames=1,left_context_frames=0 if stream else 1,fifo_frames=80 if stream else 0,spkcache_frames=264,update_period_frames=40 if stream else 188,preset='v3-streaming' if stream else 'v3-offline',gpu=-1)
config=dict(profile=PROFILE,kernel=KERNEL,c_abi_geometry=geometry,coarse_frame_seconds=.08,same_geometry_parity_tolerance=1e-5,all_audio_retained=True,compute_graph_lru_capacity=1,metadata_arena_mib=2,metadata_build_review_sha256=sha(lru/'BUILD_REVIEW.json'))
if REFERENCE:
 ref=root/REFERENCE;r=json.loads((ref/'RESULT.json').read_text())
 assert r['status']=='NATIVE_GEOMETRY_COLLECTED_REQUIRES_REVIEW' and r['config']['kernel']=='generic' and r['config']['profile']==PROFILE
 review=json.loads((ref/'REVIEW.json').read_text())
 assert review['status']=='PASS_NATIVE_RECIPE_FUNCTIONAL_RESOURCE_ONLY' and review['result_sha256']==sha(ref/'RESULT.json')
 os.link(ref/'saved_full.npy',dest/'same_geometry_generic.npy')
 config['reference_result_sha256']=sha(ref/'RESULT.json');config['reference_review_sha256']=sha(ref/'REVIEW.json')
(dest/'CONFIG.json').write_text(json.dumps(config,indent=2))
files=[dict(name=str(p.relative_to(dest)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(dest.rglob('*')) if p.is_file()]
(dest/'INPUTS.json').write_text(json.dumps(dict(schema='native-geometry-inputs.v1',files=files,ancestry_inputs_sha256=sha(old/'INPUTS_V12.json'),historical_bundle_manifests_preserved=True),indent=2))
now=datetime.now(timezone.utc);checkpoint=datetime.fromisoformat('2026-10-01T17:47:34+00:00')
assert now+timedelta(minutes=12)<checkpoint
admission=dict(schema='native-geometry-admission.v1',boot_id=boot,admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),checkpoint_utc=checkpoint.isoformat(),inputs_sha256=sha(dest/'INPUTS.json'),cpus=[2,3],native_threads=1,address_space_max_bytes=768*1024**2,runtime_seconds=600,maximum_tasks=64,output_max_bytes=16*1024**2,minimum_available_ram_bytes=850*1024**2,minimum_target_free_bytes=5*1024**3,available_ram_bytes=available,disk_free_bytes=free,gpu=False,downloads=False,capture=False,accuracy_scored=False,target_root=str(dest),original_app_unchanged=True,closed_owners=owners)
(dest/'ADMISSION.json').write_text(json.dumps(admission,indent=2))
print(json.dumps(dict(admission=admission,config=config,target_bytes=target_bytes,host_window_bytes=HOST_USED,units=units)))
'''
    prefix = '\n'.join(k+'='+repr(v) for k,v in dict(REMOTE=REMOTE, PAYLOAD=payload, HOST_USED=used,
                       RUN_ID=args.run_id, PROFILE=args.profile, KERNEL=args.kernel, REFERENCE=args.reference).items())
    preflight = remote(prefix+'\n'+code)
    (out/'PREFLIGHT.json').write_text(json.dumps(preflight,indent=2),encoding='utf-8')
    command = ('systemd-run --user --unit=jp-'+args.run_id+' --wait --pipe '
               '-p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 '
               'taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B '
               +REMOTE+'/'+args.run_id+'/d1_geometry_v1.py')
    (out/'COMMAND.json').write_text(json.dumps(dict(command=command)),encoding='utf-8')
    with (out/'launch.log').open('x',encoding='utf-8') as log:
        process = subprocess.run(SSH+[command],stdout=log,stderr=subprocess.STDOUT,timeout=630)
    (out/'LAUNCH_RESULT.json').write_text(json.dumps(dict(exit_code=process.returncode,requires_independent_review=True)),encoding='utf-8')
    print(json.dumps(dict(run_id=args.run_id,exit_code=process.returncode,evidence=str(out))))


if __name__ == '__main__':
    main()
