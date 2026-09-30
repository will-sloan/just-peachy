"""Independent compact binding review; README_FIELD_ARCHIVE_BUDGET_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-archive-budget-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_NATIVE_SMALL_ARCHIVE_BUDGET_BOUNDARIES_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
selected=Path(a['installed_release']);assert {p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
derivation=read(r/'ARCHIVE_BUDGET_DERIVATION_V1.json')
assert sha(selected/'app/sessions.py')==derivation['source_sha256']
assert sha(r/'archive_budget_v1/app/sessions.py')==derivation['derivative_sha256']
budget=read(r/'ARCHIVE_BUDGET_V1.json')
assert budget==out['budget']==dict(schema='just-peachy.archive-budget.v1',metadata_input_bytes=16*1024**2,auxiliary_bytes=2*1024**2,control_file_bytes=65536,compact_index='none')
assert out['budget_sha256']==hashlib.sha256(json.dumps(budget,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert len(out['cases'])==14 and sum(bool(v.get('rejected')) for v in out['cases'])==11
for row in out['cases']:assert row==read(r/(row['case']+'.json'))
assert not list(r.glob('must-not-publish*')) and not list(r.rglob('*.sqlite')) and not list(r.rglob('.*.tmp'))
epochs=list((r/'data/conversations').glob('*/epochs/*'))
assert len(epochs)==1
for name,folder,error in [('compact-store-reopen',epochs[0],None),('auxiliary-failure',r/'auxiliary-archive','ARCHIVE_AUXILIARY_BYTE_LIMIT'),('metadata-failure',r/'metadata-archive','ARCHIVE_QUOTA_REACHED')]:
 case=read(r/(name+'.json'));m=read(folder/'epoch.json');b=m['archive_budget']
 # Repeat close updates timestamps. Retained case hash identifies that checkpoint, not final bytes after repeat.
 assert not m['worker_alive'] and m['closed'] and m['state']==('PARTIAL' if error else 'CLOSED')
 assert (error in str(m['archive_error'])) if error else m['archive_error'] is None
 assert m['queue_items']==m['queue_bytes']==0 and m['metadata_bytes']<=b['metadata_input_bytes']
 auxiliary=sum((folder/n).stat().st_size for n in ['windows.jsonl','resources.jsonl','transforms.jsonl'] if (folder/n).exists())
 assert auxiliary==m['auxiliary_bytes']<=b['auxiliary_bytes']
 assert (folder/'epoch.json').stat().st_size<=b['control_file_bytes']
 assert m['accepted_items']==case['accepted'] and m['completed_items']==case['completed']
 if error:assert m['accepted_items']==2 and m['completed_items']==0 and case['repeat_close_preserves_error']
 else:
  import wave
  assert m['source_samples']==m['recorded_samples']==160 and case['rows']==1
  assert (folder/'model_input.f32le').read_bytes()==bytes(160*4)
  with wave.open(str(folder/'model_input.wav')) as wav:
   assert wav.getnframes()==160 and wav.getframerate()==16000 and wav.readframes(160)==bytes(320)
assert out['physical_epoch_ceiling_bytes']==31485484
assert not any(out[k] for k in ['capture','models','GUI','full_maximum_files_exercised','installed_integration'])
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
    with (PRIVATE/'field-archive-budget-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
