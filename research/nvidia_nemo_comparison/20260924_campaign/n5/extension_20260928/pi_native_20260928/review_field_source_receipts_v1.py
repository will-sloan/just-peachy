"""Independent compact binding review; README_FIELD_SOURCE_RECEIPTS_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-source-receipts-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_SOURCE_STOP_RECEIPT_ADAPTER_FIXTURES_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
plan=read(r/'FIELD_WHOLE_RUN_ALLOCATION_V2.json');descriptor=read(r/'FIELD_SOURCE_RECEIPT_DESCRIPTOR_V1.json')
assert descriptor['plan_sha256']==sha(r/'FIELD_WHOLE_RUN_ALLOCATION_V2.json')
assert descriptor['scope']=='no-capture-qualification'
for name,h in descriptor['files'].items():assert sha(r/name)==h
cases=read(r/'SOURCE_RECEIPT_CASES.json');assert len(cases)==14 and len({c['case'] for c in cases})==14
assert sum(c['rejected'] for c in cases)==13
expected={'normal-stop':None,'post-route-quota':'LIVE_SOURCE_CLOSE_INCOMPLETE','route-stop-quota':'LIVE_SOURCE_CLOSE_INCOMPLETE','bridge-quota':'SOURCE_RECEIPT_NOT_PUBLISHED','accepted-tail':'UNCONSUMED_ACCEPTED_RAW_TAIL','route-mismatch':'SOURCE_RESTORATION_FAILED'}
for row in cases:
 assert row==read(r/(row['case']+'-CASE.json'))
 if row['case'] not in expected:
  assert row['rejected'] and row['unpublished']
  if row['case'].startswith('descriptor-'):assert not (r/'fixtures'/row['case']).exists()
  continue
 name=row['case'];d=r/'fixtures'/name
 assert row['calls']==['restore','stream.stop','stream.close','lease.close','endpoint_snapshot']
 assert row['error']==expected[name] and row['start_rejected'] and row['cached_stop_no_repeat']
 closure=read(d/'closure_reserve/SOURCE_CLOSURE.json');assert closure==row['closure']
 assert closure['closed'] and closure['stream_closed'] and closure['lease_released']
 assert closure['logical_success']==(expected[name] is None) and closure['failure_code']==expected[name]
 assert closure['bridge_model_samples']==closure['bridge_native_frames']==0
 assert closure['final_status']['pending_raw_blocks']==int(name=='accepted-tail')
 for group,snapshot in row['snapshot'].items():
  directory=d/group;sizes={x.name:x.stat().st_size for x in directory.iterdir() if x.name!='.budget.guard'}
  assert sizes==snapshot['sizes'] and sum(sizes.values())==snapshot['bytes']<=snapshot['budget']['maximum_bytes']
  assert len(sizes)==snapshot['files']<=snapshot['budget']['maximum_files']
  for n,size in sizes.items():assert size<=snapshot['budget']['maximum_file_bytes']
 for failure in row['diagnostics']:
  assert failure['raw_retained'] and failure['receipt_retained']
  raw=d/'failure'/failure['raw_path'];assert raw.stat().st_size==failure['bytes'] and sha(raw)==failure['sha256']
 assert row['layout']['directories']==4 and row['layout']['observed_directory_bytes']+65536<plan['filesystem_metadata_reserve_bytes']
 assert len(row['events'])==1 and row['events'][0]['kind']=='source_stopped'
 if name in ['post-route-quota','route-stop-quota']:assert row['events'][0]['errors']==['SOURCE_RECEIPT_NOT_PUBLISHED']
normal=r/'fixtures/normal-stop/source'
assert read(normal/'PRE_ROUTE_SNAPSHOT.json')==read(normal/'POST_ROUTE_SNAPSHOT.json')=={'route':'fixture','value':1}
assert not read(normal/'ROUTE_STOP.json')['errors']
assert len(next(c for c in cases if c['case']=='post-route-quota')['diagnostics'])==4
assert len(next(c for c in cases if c['case']=='route-stop-quota')['diagnostics'])==3
assert len(next(c for c in cases if c['case']=='bridge-quota')['diagnostics'])==2
large=next(c for c in cases if c['case']=='oversized-diagnostic')['receipt']
assert not large['raw_retained'] and not large['receipt_retained']
assert large['bytes']==(r/'OVERSIZED_SYNTHETIC_INPUT.json').stat().st_size and large['sha256']==sha(r/'OVERSIZED_SYNTHETIC_INPUT.json')
assert not list(r.rglob('*.pending')) and not list(r.rglob('*.wav')) and not list(r.rglob('epoch.json'))
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert out['cases']==14 and out['rejections']==13 and out['actual_installed_stop_derivative'] and out['fake_hardware']
assert not any(out[k] for k in ['source_started','models','capture','GUI','audio','controller','whole_run_integrated','policy_changed'])
assert sha(r/'LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(r/'INSTALL_BACKUP.json')==a['install_sha256']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-source-receipts-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
