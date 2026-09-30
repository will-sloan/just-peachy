"""Independent compact binding review; README_FIELD_OVERLAY_LAUNCHER_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-overlay-launcher-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_COMPACT_OVERLAY_TRANSACTION_AND_GUARDED_ENTRY_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
selected=Path(a['installed_release']);assert {p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
cases=read(r/'ADAPTER_CASES.json');assert len(cases['rejections'])==7 and len(cases['launches'])==5
for row in cases['rejections']:
 assert row['rejected'] and row['candidate_unchanged'] and row==read(r/(row['case']+'-REJECTION.json'))
for row in cases['launches']:
 assert row==read(r/(row['case']+'-COLLECTED.json')) and sha(r/(row['case']+'-RESULT.json'))==row['result_sha256']
 result=read(r/(row['case']+'-RESULT.json'))
 assert result['affinity']==[2,3] and result['address_space']==[768*1024**2]*2 and result['stack']==[1024**2]*2
 assert not result['models'] and not result['capture'] and not result['GUI']
 if row['expected_rejection']:
  assert row['exit_code']==1 and not result['entered'] and row['expected_rejection'] in result['error']
 else:
  assert row['exit_code']==0 and result['status']=='PASS_GUARDED_RETAINED_OVERLAY_ONLY'
  assert result['entered'] and result['borrowers']==result['borrowers_closed']==1
  assert result['lease_continuous'] and result['lease_released'] and result['threads_closed'] and result['controller_closed'] and result['worker_joined'] and result['pending_commands']==0
  assert result['dependency_check']['entries']==7890 and result['dependency_check']['unique_files']==7847 and result['dependency_check']['unique_logical_bytes']==791871486
  assert result['overlay']['source_sha256']==a['overlay_source_sha256'] and result['overlay']['descriptor_sha256']==a['overlay_descriptor_sha256']
  assert len(row['blocked_updates'])==3
  for blocked in row['blocked_updates']:
   phase=read(r/(row['case']+'-'+blocked['phase']+'.json'))
   assert blocked['candidate_unchanged'] and blocked['lease_token']==phase['lease_token']==result['lease_token'] and blocked['pid']==phase['owner']['pid']==result['lease_owner_pid']
# Independently resolve the three-record hash chain and final rollback projection.
root=r/'deployment';state=read(root/'state.json');assert sha(root/'state.json')==cases['final_state_sha256']==out['final_state_sha256']
assert state==cases['final'] and state['current']==cases['first']['current'] and state['previous']==cases['selected']['current']
assert read(state['current']['descriptor'])['overlay'] is None
records=list((root/'transactions').glob('*.json'));assert len(records)==3 and not list((root/'staged').iterdir())
seen=[];cursor=state
while cursor is not None:
 name=cursor['transaction'];record=read(root/'transactions'/name)
 assert sha(root/'transactions'/name)==cursor['transaction_sha256']
 assert record['current']==cursor['current'] and record['previous']==cursor['previous']
 assert record['dependency_check']['entries']==7890
 seen.append(name)
 previous=next((v for v in [cases['first'],cases['selected']] if v['transaction']==record['prior_transaction']),None)
 if previous is not None:
  raw=json.dumps(previous,indent=2,allow_nan=False).encode('utf-8')
  assert hashlib.sha256(raw).hexdigest()==record['expected_prior_sha256']
 else:assert record['prior_transaction'] is None and record['expected_prior_sha256'] is None
 cursor=previous
assert len(seen)==3 and len(set(seen))==3
for path in [r/'base.deployment.json',r/'overlay.deployment.json']:
 d=read(path);assert d['config_sha256']==cases['config_sha256']
 assert d['base_binding']==dict(path=a['compact_binding'],sha256=a['compact_binding_sha256'])
 assert d['candidate_root']==str(root) and d['data_root']==str(r/'data')
 for n,h in d['config_sha256'].items():assert sha(r/'data'/n)==h
assert not (r/'data/runtime.lock').exists() and not (r/'data/source_receipts').exists() and not (r/'data/sessions').exists()
assert not list(r.glob('*FORCED_CLOSE.json')) and not list((r/'data').rglob('epoch.json')) and not list((r/'data').rglob('*.wav'))
assert out['prepublication_rejections']==7 and out['launch_rejections']==4 and out['blocked_updates']==3 and out['new_controller_entries']==1
assert not any(out[k] for k in ['models','capture','GUI','audio','engine','epoch_created','baseline_activated','catalogue_copied','release_copied'])
assert out['base_unchanged'] and out['exact_configs'] and out['ownership_closed'] and out['entry_closed']
derivation=read(r/'OVERLAY_TRANSACTION_DERIVATION_V1.json')
original=r.parent/'field-transaction-v2/field_candidate_transaction_v1.py'
assert sha(original)==derivation['base_source_sha256'] and sha(r/'field_overlay_transaction_v1.py')==derivation['derivative_sha256']
s=original.read_text().replace('README_FIELD_TRANSACTION_V1.md','README_FIELD_OVERLAY_LAUNCHER_V1.md').replace('import field_dependencies_v2 as pins','import field_dependencies_v2 as pins\nimport field_overlay_deployment_v1 as adapter').replace('pins.check_descriptor(descriptor_path, descriptor_sha, release_tools)','adapter.check_descriptor(descriptor_path, descriptor_sha, release_tools)')
assert s==(r/'field_overlay_transaction_v1.py').read_text()
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
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-overlay-launcher-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
