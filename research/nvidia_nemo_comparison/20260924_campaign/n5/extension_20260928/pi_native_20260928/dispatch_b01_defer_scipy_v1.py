"""Dispatch one fresh bounded native recipe job. See README_B01_DEFER_SCIPY_V1.md."""
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
    assert args.run_id=='b01-defer-scipy-v1'
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
    calculation = budget(census['calculation']['existing_bytes']+delta, used, 48*1024**2, free, 50)
    out = PRIVATE/(args.run_id+'-evidence'); out.mkdir()
    (out/'HOST_RECHECK.json').write_text(json.dumps(dict(calculation=calculation, free=free,
          census=str(args.census), census_sha256=hashlib.sha256(args.census.read_bytes()).hexdigest()), indent=2), encoding='utf-8')
    paths = {name:HERE/name for name in ('b01_defer_scipy_v1.py','b01_scipy_gate_v1.py','README_B01_DEFER_SCIPY_V1.md')}
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
assert target_bytes+HOST_USED+48*1024**2<1024**3
old=root/'b05-native-stack-v1';prior=json.loads((old/'ADMISSION.json').read_text())
for row in prior['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
review=json.loads((old/'REVIEW.json').read_text())
assert review['status']=='PASS_B05_NATIVE_STACK_STOP_RESTART_ONLY'
assert review['bindings']['RESULT.json']==sha(old/'RESULT.json')
assert review['sessions'][1]['reference_max_abs']==0 and review['sessions'][1]['samples']==715127
parent=Path(prior['prototype']);source=root/'shared-app-b01-defer-scipy-v1/prototype'
assert not source.parent.exists() and not any(p.is_symlink() for p in parent.rglob('*'))
shutil.copytree(parent,source,copy_function=os.link)
catalog=source/'config/backends.json';doc=json.loads(catalog.read_text());selected=next(x for x in doc['backends'] if x['key']=='nemotron_hybrid')
import ast
changed={}
for name,anchor in [('audio.py','        combined = np.concatenate((self._carry, values))'),('enrollment.py','        common = gcd(int(rate), 16_000)')]:
 p=source/'vendor/edge_speech_pipeline'/name
 text=p.read_text();assert text.count('from scipy.signal import resample_poly')==1
 text=text.replace('from scipy.signal import resample_poly','')
 assert text.count(anchor)==1
 text=text.replace(anchor,'        from scipy.signal import resample_poly\\n'+anchor)
 ast.parse(text)
 p.unlink();p.write_text(text);changed[name]=sha(p)
selected['composition']['process_runtime_policy']['RLIMIT_STACK_startup_bytes']=1048576
selected['composition']['process_runtime_policy']['resampler_import_policy']='load_scipy_only_when_sample_rate_conversion_requested_v1'
selected['composition']['process_runtime_policy']['deferred_import_sources']=changed
selected['label']='Experimental CM5 B01: retained ReDimNet; resampling dependencies loaded only on use'
selected['manifest_id']='sha256:'+hashlib.sha256(json.dumps(selected['composition'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
catalog.unlink();catalog.write_text(json.dumps(doc,indent=2))
assert sha(source/'app/n2_pipeline.py')=='6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491'
dest=root/RUN_ID;dest.mkdir();(dest/'data').mkdir()
for name,blob in PAYLOAD.items():(dest/name).write_bytes(base64.b64decode(blob))
short=root/'b05-anonymous-v1';short_admission=json.loads((short/'ADMISSION.json').read_text())
assert sha(short/'prefix12.wav')==next(r['sha256'] for r in short_admission['files'] if r['path']==str(short/'prefix12.wav'))
os.link(short/'prefix12.wav',dest/'prefix12.wav')
shutil.copyfile(old/'data/n2_runtime.json',dest/'data/n2_runtime.json')
files=[row for row in prior['files'] if not Path(row['path']).is_relative_to(old) and not Path(row['path']).is_relative_to(parent)]
files += [dict(path=str(p),sha256=sha(p)) for p in sorted(source.rglob('*')) if p.is_file()]
for name in ['prefix12.wav','data/n2_runtime.json','b01_defer_scipy_v1.py','b01_scipy_gate_v1.py','README_B01_DEFER_SCIPY_V1.md']:
 files.append(dict(path=str(dest/name),sha256=sha(dest/name)))
now=datetime.now(timezone.utc);assert now+timedelta(minutes=8)<datetime.fromisoformat('2026-10-01T17:47:34+00:00')
admission=dict(prior);admission.update(schema='native-B01-defer-scipy.v1',ui_mode='B01_defer_scipy',prototype=str(source),backend_manifest_id=selected['manifest_id'],startup_stack_limit_bytes=1048576,admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=8)).isoformat(),files=files,closed_owners=owners,available_ram_bytes=available,disk_free_bytes=free,address_space_max_bytes=768*1024**2,changed_code=['Only resample_poly imports moved into actual rate-conversion branches in audio.py and enrollment.py; original eager E0 constructor unchanged; original n2_pipeline unchanged; no live audio or enrollment invoked'],runtime_seconds=180,output_max_bytes=48*1024**2,full_passage_review_sha256=sha(old/'REVIEW.json'),expected_source_samples=192000,mode='open_with_names',empty_new_gallery=True)
(dest/'ADMISSION.json').write_text(json.dumps(admission,indent=2))
print(json.dumps(dict(admission=admission,target_bytes=target_bytes,host_window_bytes=HOST_USED,units=units)))
'''
    prefix = '\n'.join(k+'='+repr(v) for k,v in dict(REMOTE=REMOTE, PAYLOAD=payload, HOST_USED=used,
                       RUN_ID=args.run_id, PROFILE=args.profile, KERNEL=args.kernel, REFERENCE=args.reference).items())
    preflight = remote(prefix+'\n'+code)
    (out/'PREFLIGHT.json').write_text(json.dumps(preflight,indent=2),encoding='utf-8')
    command = 'python3 '+REMOTE+'/'+args.run_id+'/b01_scipy_gate_v1.py'
    (out/'COMMAND.json').write_text(json.dumps(dict(command=command)),encoding='utf-8')
    with (out/'launch.log').open('x',encoding='utf-8') as log:
        process = subprocess.run(SSH+[command],stdout=log,stderr=subprocess.STDOUT,timeout=220)
    (out/'LAUNCH_RESULT.json').write_text(json.dumps(dict(exit_code=process.returncode,requires_independent_review=True)),encoding='utf-8')
    print(json.dumps(dict(run_id=args.run_id,exit_code=process.returncode,evidence=str(out))))


if __name__ == '__main__':
    main()
