"""Independent compact binding review; README_FIELD_CHILD_DEADLINE_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-child-deadline-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_ABSOLUTE_CHILD_DEADLINE_FIXTURES_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
selected=Path(a['installed_release']);assert {p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
cases=read(r/'DEADLINE_CASES.json');assert len(cases['rejections'])==7 and len(cases['cases'])==3
assert a['child_deadline_seconds']==60 and a['child_stop_grace_seconds']==2
for row in cases['rejections']:
 assert row['rejected'] and row==read(r/(row['case']+'-REJECTION.json')) and row['error']
 d=read(r/(row['case']+'-INPUT.json'));name=row['case']
 if name=='missing-field':assert 'grace_ns' not in d
 elif name=='wrong-boot':assert d['boot_id']!=a['boot_id']
 elif name=='future-issued':assert 'order' in row['error']
 elif name=='overlong':assert d['hard_ns']-d['issued_ns']>60*10**9
 elif name=='grace-overmax':assert d['grace_ns']>2*10**9
 elif name=='noninteger':assert type(d['issued_ns']) is bool
 else:assert name=='expired-before-spawn' and 'expired before work' in row['error']
def check(d):
 assert set(d)=={'schema','boot_id','issued_ns','soft_ns','hard_ns','grace_ns'}
 assert d['schema']=='just-peachy.absolute-child-deadline.v1' and d['boot_id']==a['boot_id']
 assert all(type(d[k]) is int for k in ['issued_ns','soft_ns','hard_ns','grace_ns'])
 assert 0<d['issued_ns']<d['soft_ns']<d['hard_ns']
 assert d['hard_ns']-d['soft_ns']==d['grace_ns']<=2*10**9 and d['hard_ns']-d['issued_ns']<=60*10**9
launch=read(r/'expired-launcher-COLLECTED.json');result=read(r/'expired-launcher-RESULT.json')
assert launch['result_sha256']==sha(r/'expired-launcher-RESULT.json')
assert read(r/'expired-launcher-SPEC.json')['deadline']==read(r/'expired-before-spawn-INPUT.json')
check(launch['supervision_deadline']);assert launch['outcome']['returncode']==1 and not launch['outcome']['terminate_sent']
assert not result['entered'] and result['borrowers']==result['borrowers_closed']==0 and 'expired before work' in result['error']
assert not any(result[k] for k in ['capture','GUI','models']) and result['affinity']==[2,3]
assert result['address_space']==[768*1024**2]*2 and result['stack']==[1024**2]*2
for row in cases['cases']:
 mode=row['mode'];d=row['deadline'];outcome=row['outcome'];check(d)
 assert d['hard_ns']-d['issued_ns']==1200000000 and d['grace_ns']==250000000
 assert row==read(r/(mode+'-COLLECTED.json')) and read(r/(mode+'-SPEC.json'))['deadline']==d
 ready=read(r/(mode+'-READY.json'));owner=read(r/(mode+'-OWNER.json'))
 assert ready['deadline']==d and ready['owner']==owner==row['owner'] and owner['pid']==outcome['pid']
 assert d['issued_ns']<=ready['armed_monotonic_ns']<d['soft_ns']
 assert ready['affinity']==[2,3] and ready['address_space']==[768*1024**2]*2 and ready['stack']==[1024**2]*2
 assert outcome['hard_ns']==d['hard_ns'] and outcome['soft_ns']==d['soft_ns'] and not outcome['abort']
 assert outcome['reaped_ns']<=d['hard_ns']+500000000
 assert not (r/(mode+'-data/runtime.lock')).exists()
 with (r/(mode+'-data/.runtime.guard')).open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if mode=='stubborn':
  assert outcome['returncode']==-9 and outcome['terminate_sent'] and outcome['kill_sent']
  assert d['soft_ns']<=outcome['terminate_ns']<d['hard_ns']
  assert d['hard_ns']<=outcome['kill_ns']<=d['hard_ns']+500000000
  assert not (r/(mode+'-RESULT.json')).exists()
  old=read(r/'STUBBORN_STALE_LOCK.json');recovery=row['recovery']
  assert old['pid']==owner['pid']==recovery['previous_pid'] and old['token']==ready['lease_token']==recovery['previous_token']
  assert recovery['new_pid']==read(r/'OWNER.json')['pid'] and recovery['new_token']!=old['token']
 else:
  finished=read(r/(mode+'-RESULT.json'));assert finished['lease_closed'] and finished['owner']==owner and finished['deadline']==d
  assert not finished['models'] and not finished['capture'] and finished['finished_ns']<=d['hard_ns']
  assert not outcome['kill_sent'] and outcome['returncode']==(0 if mode=='normal' else 124)
  if mode=='normal':assert not outcome['terminate_sent']
  else:assert finished['expired']
assert out['rejections']==7 and out['fixture_children']==3 and out['expired_launcher'] and out['ownership_closed']
assert out['normal_exit'] and out['cooperative_expiry'] and out['forced_sigkill'] and out['stale_lock_recovered_through_interface']
assert not any(out[k] for k in ['models','capture','GUI','controller','epoch','full_launcher_protocol_v2_executed'])
assert not list(r.rglob('*.wav')) and not list(r.rglob('epoch.json')) and not (r/'deployment').exists()
assert not (r/'data/runtime.lock').exists() and not (r/'data/source_receipts').exists() and not (r/'data/sessions').exists()
assert sha(r/'data/live_config.json')==a['live_config_sha256'] and sha(r/'data/n2_runtime.json')==a['n2_runtime_sha256']
derivation=read(r/'CHILD_DEADLINE_DERIVATION_V1.json')
for name,row in derivation['files'].items():
 assert sha(r/name)==row['derivative_sha256']
 assert sha(r.parent/'field-overlay-launcher-v1'/name.replace('_v2.py','_v1.py'))==row['base_sha256']
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
    with (PRIVATE/'field-child-deadline-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
