"""Independent compact binding review; README_FIELD_ENTRY_CONFIG_BUDGET_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-entry-config-budget-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_SELECTED_ENTRY_CONFIG_PUBLICATION_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
cases=read(r/'ENTRY_CONFIG_CASES.json')
assert len(cases)==14 and len({x['case'] for x in cases})==14
for row in cases[:7]:assert row['error'] and not row['directory_created'] and not (r/'fixtures'/row['case']).exists()
for row in cases[7:]:
 name=row['case'];d=r/'fixtures'/name
 assert d.exists()==row['directory_created']
 if row['input_cfg'] is not None:
  raw=(r/(name+'-INPUT_CONFIG.bin')).read_bytes();assert json.loads(raw)==row['input_cfg']
 if name=='mapped-config':
  v=row['prepared'];assert v['status']=='CONFIGURATION_PREPARED_NOT_LAUNCHABLE' and not v['source_factory_integrated'] and not v['capture_started']
  assert read(d/'closure_reserve/CONFIG_CLOSURE.json')==v
  assert sha(d/'config/CONFIG.json')==v['sha256'] and (d/'config/CONFIG.json').stat().st_size==v['bytes']
  assert (d/'config/CONFIG.json').read_bytes()==raw and read(d/'config/CONFIG.json')['capture'] is True
  assert row['repeat_error']=='Entry publication already attempted'
  for stage in ['before','after']:assert v[stage]['directories']==5 and v[stage]['measured_directory_extent_bytes']<=v[stage]['reserved_directory_bytes']==327680
 elif name in ['bad-factory','boolean-capture','config-byte-cap','boolean-epoch']:
  assert row['error'] and not d.exists()
 elif name=='layout-drift':
  assert (d/'unexpected').is_dir() and not (d/'config/CONFIG.json').exists()
  assert not row['failure']['raw_retained'] and not row['failure']['receipt_retained'] and row['failure']['sha256']==hashlib.sha256(raw).hexdigest()
 elif name=='closure-quota':
  failure=row['failure'];assert failure['configuration_published'] and failure['raw_retained'] and failure['receipt_retained']
  assert (d/'config/CONFIG.json').read_bytes()==(d/'failure/CONFIG_REJECTED.bin').read_bytes()==raw
  assert read(d/'failure/CONFIG_FAILURE.json')['receipt_retained']
  assert not (d/'closure_reserve/CONFIG_CLOSURE.json').exists()
 if d.exists():
  cfg=read(r/(name+'-DESCRIPTOR.json'))
  for group,limits in cfg['groups'].items():
   sizes=[p.stat().st_size for p in (d/group).iterdir() if p.name!='.budget.guard']
   assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(n<=limits['maximum_file_bytes'] for n in sizes)
for pattern in ['.budget.guard','.layout.guard']:
 for guard in r.rglob(pattern):
  assert guard.stat().st_size==0
  with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert sha(r/'data/live_config.json')==a['data_config_sha256']
assert out['cases']==14 and out['descriptor_rejections']==out['configuration_cases']==7 and out['configuration_files']==2
assert out['launchable_objects_returned']==out['controller_constructors']==out['source_audio_samples']==0
assert not any(out[k] for k in ['models','capture','GUI','whole_run_integrated','policy_changed'])
assert not list(r.rglob('*.pending')) and not list(r.rglob('*.wav'))
for sample in dispatch['samples']:
 ids=[tuple(i) for i in sample.get('aggregate_unique_identities',[])]
 assert len(ids)==len(set(ids))
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
    with (PRIVATE/'field-entry-config-budget-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
