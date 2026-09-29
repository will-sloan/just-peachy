"""Dispatch one fresh bounded native recipe job. See README_B01_DELAYED_METADATA2_V2.md."""
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
    p.add_argument('--run-id', required=True)
    p.add_argument('--census', type=Path, required=True)
    args = p.parse_args()
    assert args.run_id=='b01-delayed-metadata2-v2'
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
    paths = {name:HERE/name for name in ('b01_native_delayed_metadata2_v2.py','README_B01_DELAYED_METADATA2_V2.md')}
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
old=root/'b01-short-v9';prior=json.loads((old/'ADMISSION.json').read_text())
for row in prior['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
component=root/'d1-geometry-delayed-metadata2-v1'
review=json.loads((component/'REVIEW.json').read_text())
assert review['status']=='PASS_NATIVE_RECIPE_FUNCTIONAL_RESOURCE_ONLY' and review['independent_generic_max_abs']==0
assert review['result_sha256']==sha(component/'RESULT.json')
assert sha(component/'nemo-arm64/lib/libnemo_speech_asr.so')=='1639518a4de05caa1cf40feb3c9e4e2672cfe82fde87f79f707b115421cdb020'
parent=Path(prior['prototype']);source=root/'shared-app-delayed-metadata2-v2/prototype'
assert not source.parent.exists()
assert not any(x.is_symlink() for x in parent.rglob('*'))
shutil.copytree(parent,source,copy_function=os.link)
adapter=source/'vendor/edge_speech_pipeline/nemotron_diarization.py'
adapter.unlink();adapter.write_bytes(base64.b64decode(PAYLOAD['nemotron_diarization.py']))
assert sha(adapter)=='2537162df8ac8ccdd89c45c3f26fa12ef48519867a0474bf4be39e4667d75e37'
catalog=source/'config/backends.json';doc=json.loads(catalog.read_text())
selected=next(x for x in doc['backends'] if x['key']=='nemotron_hybrid')
assert selected['composition']['n2']['diarization']=='D1' and selected['composition']['n2']['embedding']=='E0'
selected['composition']['n2']['streaming_profile']='native_v3_delayed'
selected['composition']['native_d1_runtime']=dict(session_sha256='1639518a4de05caa1cf40feb3c9e4e2672cfe82fde87f79f707b115421cdb020',cpu_sha256='f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557',metadata_mib=2,graph_cache_entries=8)
selected['composition']['process_runtime_policy']={'ORT_DISABLE_TELEMETRY':'1'}
selected['manifest_id']='sha256:'+hashlib.sha256(json.dumps(selected['composition'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
selected['label']='Experimental CM5: Sherpa + delayed Nemotron + ReDimNet'
catalog.unlink();catalog.write_text(json.dumps(doc,indent=2))
dest=root/RUN_ID;dest.mkdir();(dest/'data').mkdir()
for name,blob in PAYLOAD.items():
 if name!='nemotron_diarization.py':(dest/name).write_bytes(base64.b64decode(blob))
os.link(old/'prefix12.wav',dest/'prefix12.wav')
runtime=json.loads((old/'data/n2_runtime.json').read_text())
runtime['nemotron_library']=str(component/'nemo-arm64/lib/libnemo_speech_asr_c.so.1')
runtime['streaming_profile']='native_v3_delayed'
runtime['native_runtime_files']=[dict(path=str(component/row['name']),sha256=row['sha256']) for row in json.loads((component/'INPUTS.json').read_text())['files'] if row['name'].startswith('nemo-arm64/lib/')]
(dest/'data/n2_runtime.json').write_text(json.dumps(runtime,indent=2))
files=[]
for row in prior['files']:
 path=Path(row['path'])
 if path.is_relative_to(old) or path.is_relative_to(parent) or '/nemo-arm64/' in str(path):continue
 files.append(row)
for path in sorted(source.rglob('*')):
 if path.is_file():files.append(dict(path=str(path),sha256=sha(path)))
for name in ['prefix12.wav','data/n2_runtime.json','b01_native_delayed_metadata2_v2.py','README_B01_DELAYED_METADATA2_V2.md']:
 files.append(dict(path=str(dest/name),sha256=sha(dest/name)))
files+=runtime['native_runtime_files']
now=datetime.now(timezone.utc);assert now+timedelta(minutes=8)<datetime.fromisoformat('2026-10-01T17:47:34+00:00')
admission=dict(prior);admission.update(schema='native-B01-delayed-metadata2.v1',prototype=str(source),admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=8)).isoformat(),files=files,closed_owners=owners,available_ram_bytes=available,disk_free_bytes=free,component_review_sha256=sha(component/'REVIEW.json'),backend_manifest_id=selected['manifest_id'],address_space_max_bytes=768*1024**2,profile='native_v3_delayed',changed_code=['same D1 metadata2 and delayed profile as prior V1','disable ORT telemetry before initialization; explicit composition binding'],runtime_seconds=180)
(dest/'ADMISSION.json').write_text(json.dumps(admission,indent=2))
(source.parent/'DERIVATIVE.json').write_text(json.dumps(dict(parent=str(parent),changed_files=['vendor/edge_speech_pipeline/nemotron_diarization.py','config/backends.json'],backend_manifest_id=selected['manifest_id'],source_files=[x for x in files if Path(x['path']).is_relative_to(source)]),indent=2))
print(json.dumps(dict(admission=admission,target_bytes=target_bytes,host_window_bytes=HOST_USED,units=units)))
'''
    prefix = '\n'.join(k+'='+repr(v) for k,v in dict(REMOTE=REMOTE, PAYLOAD=payload, HOST_USED=used,
                       RUN_ID=args.run_id, PROFILE=args.profile, KERNEL=args.kernel, REFERENCE=args.reference).items())
    preflight = remote(prefix+'\n'+code)
    (out/'PREFLIGHT.json').write_text(json.dumps(preflight,indent=2),encoding='utf-8')
    command = ('systemd-run --user --unit=jp-'+args.run_id+' --wait --pipe '
               '--setenv=ORT_DISABLE_TELEMETRY=1 --setenv=MALLOC_ARENA_MAX=1 --setenv=MALLOC_MMAP_THRESHOLD_=131072 --setenv=MALLOC_TRIM_THRESHOLD_=131072 -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 '
               'taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B '
               +REMOTE+'/'+args.run_id+'/b01_native_delayed_metadata2_v2.py')
    (out/'COMMAND.json').write_text(json.dumps(dict(command=command)),encoding='utf-8')
    with (out/'launch.log').open('x',encoding='utf-8') as log:
        process = subprocess.run(SSH+[command],stdout=log,stderr=subprocess.STDOUT,timeout=220)
    (out/'LAUNCH_RESULT.json').write_text(json.dumps(dict(exit_code=process.returncode,requires_independent_review=True)),encoding='utf-8')
    print(json.dumps(dict(run_id=args.run_id,exit_code=process.returncode,evidence=str(out))))


if __name__ == '__main__':
    main()
