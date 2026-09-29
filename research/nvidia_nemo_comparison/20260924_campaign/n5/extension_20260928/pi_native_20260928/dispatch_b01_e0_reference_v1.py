"""Dispatch one fresh bounded native recipe job. See README_B01_E0_REFERENCE_V1.md."""
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
    assert args.run_id=='b01-e0-reference-v1'
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
    paths = {name:HERE/name for name in ('b01_e0_reference_v1.py','b01_e0_reference_gate_v1.py','README_B01_E0_REFERENCE_V1.md')}
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
old=root/'b01-defer-scipy-full-v1';prior=json.loads((old/'ADMISSION.json').read_text())
for row in prior['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
review=json.loads((old/'REVIEW.json').read_text())
assert review['status']=='PASS_B01_SAVED_FILE_PASSAGE_DRAIN_E0_REFERENCE_PENDING'
assert review['D1_reference_max_abs']==0 and review['source_samples']==715127
source=Path(prior['prototype']);selected=next(x for x in json.loads((source/'config/backends.json').read_text())['backends'] if x['key']=='nemotron_hybrid')
dest=root/RUN_ID;dest.mkdir()
for name,blob in PAYLOAD.items():(dest/name).write_bytes(base64.b64decode(blob))
plan=dict(tolerance_max_abs=1e-5,sources=[],queries=[]);files=[]
for run_id in ['b01-defer-scipy-v1','b01-defer-scipy-full-v1']:
 run=root/run_id;rr=json.loads((run/'REVIEW.json').read_text());assert rr['application_archive_process_drained'] and rr['D1_reference_max_abs']==0
 for rel,digest in rr['bindings'].items():assert sha(run/rel)==digest
 src=run/('source.wav' if 'full' in run_id else 'prefix12.wav');plan['sources'].append(str(src));files.append(dict(path=str(src),sha256=sha(src)))
 sess=next((run/'data/sessions').iterdir());ep=sess/'events.jsonl';files.append(dict(path=str(ep),sha256=sha(ep)))
 for event in [json.loads(l) for l in ep.read_text().splitlines()]:
  if event['event_type']!='research_embedding':continue
  e=event['payload'];first,last=round(e['source_start_sec']*16000),round(e['source_end_sec']*16000)
  assert 8000<=last-first<=32000 and len(e['normalized_embedding'])==192 and e['left_padding_sec']==0
  plan['queries'].append(dict(run_id=run_id,event_id=e['event_id'],source=str(src),first_sample=first,last_sample=last,expected=e['normalized_embedding']))
model=Path('/home/peachyprototype/JustPeachy/install/models/5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609/redimnet2_b2_fp32.onnx')
assert sha(model)=='5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609'
files.append(dict(path=str(model),sha256=sha(model)))
(dest/'QUERY_PLAN.json').write_text(json.dumps(plan,indent=2))
for name in ['QUERY_PLAN.json','b01_e0_reference_v1.py','b01_e0_reference_gate_v1.py','README_B01_E0_REFERENCE_V1.md']:
 files.append(dict(path=str(dest/name),sha256=sha(dest/name)))
now=datetime.now(timezone.utc);assert now+timedelta(minutes=8)<datetime.fromisoformat('2026-10-01T17:47:34+00:00')
admission=dict(prior);admission.update(schema='native-B01-E0-reference.v1',ui_mode='B01_E0_reference',model=str(model),prototype=str(source),backend_manifest_id=selected['manifest_id'],startup_stack_limit_bytes=1048576,admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=8)).isoformat(),files=files,closed_owners=owners,available_ram_bytes=available,disk_free_bytes=free,address_space_max_bytes=768*1024**2,changed_code=['Independent standalone E0 CPU reference and repeat on every exact admitted application window; fixed1e-5 parity gate; no ASR/diarizer execution or accuracy scoring'],runtime_seconds=180,output_max_bytes=48*1024**2,full_passage_review_sha256=sha(old/'REVIEW.json'),expected_source_samples=715127,mode='open_with_names',empty_new_gallery=True)
(dest/'ADMISSION.json').write_text(json.dumps(admission,indent=2))
print(json.dumps(dict(admission=admission,target_bytes=target_bytes,host_window_bytes=HOST_USED,units=units)))
'''
    prefix = '\n'.join(k+'='+repr(v) for k,v in dict(REMOTE=REMOTE, PAYLOAD=payload, HOST_USED=used,
                       RUN_ID=args.run_id, PROFILE=args.profile, KERNEL=args.kernel, REFERENCE=args.reference).items())
    preflight = remote(prefix+'\n'+code)
    (out/'PREFLIGHT.json').write_text(json.dumps(preflight,indent=2),encoding='utf-8')
    command = 'python3 '+REMOTE+'/'+args.run_id+'/b01_e0_reference_gate_v1.py'
    (out/'COMMAND.json').write_text(json.dumps(dict(command=command)),encoding='utf-8')
    with (out/'launch.log').open('x',encoding='utf-8') as log:
        process = subprocess.run(SSH+[command],stdout=log,stderr=subprocess.STDOUT,timeout=220)
    (out/'LAUNCH_RESULT.json').write_text(json.dumps(dict(exit_code=process.returncode,requires_independent_review=True)),encoding='utf-8')
    print(json.dumps(dict(run_id=args.run_id,exit_code=process.returncode,evidence=str(out))))


if __name__ == '__main__':
    main()
