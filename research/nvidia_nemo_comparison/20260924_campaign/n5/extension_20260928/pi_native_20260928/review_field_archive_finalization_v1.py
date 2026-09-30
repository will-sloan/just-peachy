"""Independent compact binding review; README_FIELD_ARCHIVE_FINALIZATION_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-archive-finalization-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_NATIVE_RESERVED_ARCHIVE_FINALIZATION_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
selected=Path(a['installed_release']);assert {p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
derivation=read(r/'ARCHIVE_FINALIZATION_DERIVATION_V1.json')
assert sha(r.parent/'field-archive-budget-v1/archive_budget_v1/app/sessions.py')==derivation['base_source_sha256']
assert sha(r/'archive_finalization_v1/app/sessions.py')==derivation['derivative_sha256']
assert sha(r/'field_archive_budget_v2.py')==derivation['helper_sha256']
budget=read(r/'ARCHIVE_BUDGET_V2.json');assert budget==out['budget']
assert budget['initial_control_bytes']==32768 and budget['runtime_control_bytes']==24576 and budget['control_file_bytes']==65536
assert budget['detail_file_bytes']==262144 and budget['detail_reserve_bytes']==1048576 and budget['auxiliary_bytes']==2097152
assert out['budget_sha256']==hashlib.sha256(json.dumps(budget,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert len(out['cases'])==10 and sum(bool(v.get('rejected')) for v in out['cases'])==6
for row in out['cases']:assert row==read(r/(row['case']+'.json'))
assert not list(r.glob('must-not-publish*')) and not list(r.rglob('*.sqlite')) and not list(r.rglob('.*.tmp'))
for case in out['cases']:
 if 'epoch' not in case:continue
 folder=r/'epochs'/case['epoch'];m=read(folder/'epoch.json')
 assert sha(folder/'epoch.json')==case['meta_sha256'] and (folder/'epoch.json').stat().st_size==case['final_bytes']<=65536
 assert not m['worker_alive'] and m['closed'] and m['state']==case['state']
 assert m['queue_items']==m['queue_bytes']==0 and m['accepted_items']==m['completed_items']==1
 assert case['initial_bytes']<=32768
 sizes={q.name:q.stat().st_size for q in folder.iterdir() if q.is_file()};assert sizes==case['sizes']
 auxiliary=sum(sizes.get(n,0) for n in ['windows.jsonl','resources.jsonl','transforms.jsonl'])
 assert auxiliary==m['auxiliary_bytes']<=1048576 and auxiliary+sizes.get('failure.txt',0)+2*sizes.get('checkpoint-detail.json',0)<=2097152
 assert not list(folder.glob('*.wav')) and not list(folder.glob('*.f32le'))
 if case['case']=='near-full-late-failure':
  assert 32752<=case['initial_bytes']<=32768 and m['state']=='PARTIAL' and not m['diagnostic_retention_failed']
  assert (folder/'failure.txt').read_bytes()==(r/'INPUT_failure.txt').read_bytes()
  assert m['failure_detail']['sha256']==sha(folder/'failure.txt')==case['raw_failure_sha256'] and m['failure_detail']['retained']
  assert len(m['archive_error'].encode())<1200
 elif case['case']=='late-metadata-overflow':
  late=read(folder/'checkpoint-detail.json');assert late['late_detail']=='y'*50000
  assert m['control_metadata_overflow'] and m['archive_error']=='ARCHIVE_CONTROL_RUNTIME_LIMIT' and m['state']=='PARTIAL'
  assert m['late_metadata_detail']['sha256']==sha(folder/'checkpoint-detail.json')==case['detail_sha256'] and m['late_metadata_detail']['retained']
 elif case['case']=='diagnostic-retention-overflow':
  assert m['diagnostic_retention_failed'] and not m['failure_detail']['retained'] and case['full_fixture_retained']
  assert m['failure_detail']['bytes']==262145 and m['failure_detail']['sha256']==sha(r/'INPUT_oversized_failure.txt')
  assert (r/'INPUT_oversized_failure.txt').read_bytes()==b'z'*262145 and not (folder/'failure.txt').exists()
 else:assert case['case']=='normal-reserved-close' and m['state']=='CLOSED'
assert not any(out[k] for k in ['capture','models','GUI','audio_generated','full_maximum_files_exercised','installed_integration'])
assert read(r/'LEASE_CLOSED.json')['released'] and not (r/'data/runtime.lock').exists()
assert sha(r/'data/live_config.json')==a['live_config_sha256'] and sha(r/'data/n2_runtime.json')==a['n2_runtime_sha256']
with (r/'data/.runtime.guard').open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,budget_sha256=out['budget_sha256'],target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-archive-finalization-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
