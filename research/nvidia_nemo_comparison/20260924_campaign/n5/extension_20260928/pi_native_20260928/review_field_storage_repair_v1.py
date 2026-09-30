"""Independent compact binding review; README_FIELD_STORAGE_REPAIR_V1.md."""
import hashlib
import json
from pathlib import Path
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    from dispatch_geometry_v2 import remote,PRIVATE
    result=remote(r'''
import os,sys,resource
sys.dont_write_bytecode=True;os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
import json,hashlib,fcntl,subprocess
from pathlib import Path
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-storage-repair-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
assert out['status']=='PASS_NATIVE_STORAGE_REPAIR_COMPONENTS_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
import base64
cases=read(r/'storage_receipts/STORAGE_CASES.json');assert len(cases)==11 and len({x['case'] for x in cases})==11
assert read(r/'storage_receipts/STORAGE_CLOSURE.json')['status']==out['status']
for row in cases:
 name=row['case'];d=r/'fixtures'/name
 if 'old_b64' in row:
  old=base64.b64decode(row['old_b64']);raw=base64.b64decode(row['expected_raw_b64'])
  committed=name in ['success','directory-fsync'];assert row['committed']==committed
  assert (d/'epoch.json').read_bytes()==(raw if committed else old)
  pending=d/'.epoch.json.pending'
  expected=raw[:3] if name=='short-write' else raw if name in ['file-fsync','replace'] else b'prior partial' if name=='existing-pending' else None
  assert (pending.read_bytes() if pending.exists() else None)==expected
  assert (base64.b64decode(row['pending_b64']) if row['pending_b64'] is not None else None)==expected
  if name in ['short-write','file-fsync','replace','directory-fsync']:
   assert row['error']=='PublicationFailure' and row['replaced']==committed
  elif name=='success':assert row['error'] is None
  else:assert row['error']=='ValueError' and not any(row['calls'].values())
 else:
  if name=='finite-bytes':
   assert row['publication']['admission_last'] and (d/'control/CONFIG.json').read_bytes()==base64.b64decode(row['input_b64'])
  else:assert row['error']=='Nonfinite decoded control number' and not d.exists()
assert out['cases']==11 and out['archive_cases']==7 and out['injected_io_failures']==4 and out['prewrite_slot_rejections']==2 and out['overflow_rejections']==3
assert out['exact_finite_staging'] and out['child_processes']==out['source_audio_samples']==0 and not any(out[k] for k in ['models','capture','GUI','whole_run_integrated'])
assert out['fixture_directories']==12 and out['fixture_files']<=24 and out['fixture_bytes']<=65536
for group,limits in a['metadata_limits'].items():
 sizes=[p.stat().st_size for p in (r/group).iterdir() if p.name!='.budget.guard']
 assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(x<=limits['maximum_file_bytes'] for x in sizes)
assert not any((r/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
assert all((r/'control'/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert {q.relative_to(r).as_posix() for q in r.rglob('*.pending')}=={'fixtures/'+n+'/.epoch.json.pending' for n in ['short-write','file-fsync','replace','existing-pending']} and not list(r.rglob('*.wav'))
samples=[json.loads(line) for line in (r/'outer/telemetry/resources.jsonl').read_bytes().splitlines()]
assert len(samples)==dispatch['resource_rows']>=1
for sample in samples:
 ids=[tuple(i) for i in sample['aggregate_unique_identities']];assert len(ids)==len(set(ids))
assert dispatch['process_reaped'] and dispatch['pipe_closed']
for role in ['gate','worker']:
 closure=read(r/'outer/closure_reserve'/(role+'-OUTPUT_CLOSURE.json'))
 assert closure['logical_success'] and closure['closure_retained'] and closure['work_complete'] and closure['failure'] is None
 assert closure['raw_retention_complete'] and closure['rejected_bytes']==0
 if role=='gate':assert closure['log_bytes']==(r/'outer/logs/service.log').stat().st_size and closure['resource_rows']==len(samples)
assert not (r/'RESULT.json').exists() and not (r/'DISPATCH_RESULT.json').exists() and not (r/'service.log').exists()
assert sha(r/'control/LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(r/'control/INSTALL_BACKUP.json')==a['install_sha256']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in samples),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-storage-repair-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
