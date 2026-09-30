"""Independent compact binding review; README_FIELD_CONTROLLER_STOP_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-controller-stop-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
assert out['status']=='PASS_INSTALLED_CONTROLLER_ARCHIVE_FAILURE_STOP_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
for path,digest in a['archive_binding_files'].items():assert sha(path)==digest
assert out['actual_controller'] and out['actual_command_workers_joined']
assert out['source_samples']==0 and not any(out[k] for k in ['actual_source','models','capture','GUI','full_live_composition'])
assert len(out['cases'])==2
for row in out['cases']:
 name=row['case'];d=r/name/'data'
 assert row==read(r/'binding_receipts'/(name+'-CASE.json'))
 assert row['command_worker_joined'] and row['application_lock_released'] and row['archive_worker_joined'] and row['engine_released']
 assert row['no_publisher_retry_on_close'] and row['state_after_close']=='CLOSED' and row['automatic_stop_processed']
 assert row['error'].startswith('ARCHIVE_REQUIRED:') and not row['source_started'] and row['models_loaded']==0
 assert len(row['stop_observations'])==1 and row['stop_observations'][0]['source_event_signaled'] is False
 assert not (d/'runtime.lock').exists()
 closure=read(r/'binding_receipts'/(name+'-last_application.json'))
 assert closure['terminal_error']==row['error'] and closure['microphone_open'] is False
 pending=list(d.rglob('*.pending'));assert len(pending)==1 and pending[0].read_bytes()==b'{\n '
 if name=='prepare-failure':
  assert len(row['publisher_calls'])==1 and pending[0].name=='.conversation.json.pending' and row['actual_engine_constructors']==1
  entry_failure=read(r/name/'outputs/failure/entry.json');assert entry_failure['stop_requested'] and entry_failure['raw_retained']
  assert not list(d.rglob('epoch.json'))
 else:
  assert name=='worker-failure' and pending[0].name=='.epoch.json.pending'
  archived=read(r/name/'outputs/closure/archive.json')
  assert archived['worker_joined'] and archived['closed'] and not archived['logical_success']
  assert archived['source_samples']==archived['recorded_samples']==archived['accepted_items']==archived['completed_items']==0
  assert archived['publication_failure']['replaced'] is False
  failure=read(r/name/'outputs/failure/archive.json')
  assert failure['stop_requested'] and failure['raw_retained'] and failure['receipt_retained']
  assert sum(Path(v['path']).name=='.epoch.json.pending' for v in row['publisher_calls'])==2
for group,limits in a['metadata_limits'].items():
 sizes=[p.stat().st_size for p in (r/group).iterdir() if p.name!='.budget.guard']
 assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(x<=limits['maximum_file_bytes'] for x in sizes)
assert not any((r/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
assert all((r/'control'/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert len(list(r.rglob('*.pending')))==2 and not list(r.rglob('*.wav')) and not list(r.rglob('*.f32le'))
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
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<8*1024**2
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in samples),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-controller-stop-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
