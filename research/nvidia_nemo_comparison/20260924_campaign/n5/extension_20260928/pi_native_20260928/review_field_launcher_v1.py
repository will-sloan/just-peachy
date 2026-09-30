"""Independent native package review and private backup; README_FIELD_LAUNCHER_V1.md."""
import argparse
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import subprocess
import tarfile
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    p=argparse.ArgumentParser();p.add_argument('--run',choices=['field-launcher-v1'],default='field-launcher-v1');args=p.parse_args()
    from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
    from dispatch_b01_stack_v2 import SSH
    x=remote('RUN='+repr(args.run)+'\n'+r'''
import os,json,hashlib,resource,subprocess,fcntl,zipfile,sys,base64
sys.dont_write_bytecode=True
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
root=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');dispatch=read(root/'DISPATCH_RESULT.json');env=read(root/'LIVE_ENVELOPE.json')
for row in a['files']:assert sha(row['path'])==row['sha256']
assert not a['capture'] and not a['models_loaded'] and not a['audio_saved']
assert env['affinity']==[2,3] and env['address_space']==[768*1024**2]*2 and env['stack']==[1048576]*2
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==8*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
owners=list(root.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for path in owners:
 o=read(path);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
installed=Path(a['installed_release']);source=Path(a['rollback_release'])
cache_additions={}
for folder,key in [(installed,'installed_files'),(source,'rollback_files')]:
 assert {p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}==a[key]
passed=r['status']=='PASS_GUARDED_INSTALLED_HEALTH_CONTROLLER_AND_ROLLBACK_ONLY'
if not passed:
 assert r['status']=='FAILED_PRESERVED' and dispatch['exit_code']==1
 summary=dict(status='REVIEWED_GUARDED_LAUNCHER_FAILURE_ONLY',natural_exit=1,error=r['error'],traceback=r.get('traceback'),scope='Failure preserved; launcher qualification withheld')
else:
 assert dispatch['exit_code']==0 and not any(r[k] for k in ['models_loaded','capture_opened','GUI_opened','baseline_activated','assets_copied','release_copied'])
 cases=read(root/'LAUNCHER_CASES.json');outcomes=cases['outcomes']
 assert len(outcomes)==r['cases']==7 and r['early_rejections']==4 and r['real_entry_calls']==3 and r['blocked_updates']==6
 assert not list(root.glob('*FORCED_CLOSE.json'))
 expected_cases=['missing-config','stale-state','changed-config','busy-data','v7-health','v7-controller','v5-rollback-health']
 assert [x['case'] for x in outcomes]==expected_cases
 observations=[];tokens={}
 for index,item in enumerate(outcomes):
  case=item['case'];result=read(root/(case+'-RESULT.json'));spec=read(root/(case+'-launch.json'));owner=read(root/(case+'-OWNER.json'))
  assert sha(root/(case+'-RESULT.json'))==item['result_sha256'] and read(root/(case+'-COLLECTED.json'))==item
  assert spec['run_admission_sha256']==sha(root/'ADMISSION.json') and spec['candidate_root']==str(root/'deployment') and spec['data_root']==str(root/'data')
  assert result['affinity']==[2,3] and result['address_space']==[768*1024**2]*2 and result['stack']==[1048576]*2
  assert not result['models_loaded'] and not result['capture_opened']
  if index<4:
   assert item['exit_code']==1 and result['status']=='FAILED_PRESERVED' and not result['entered'] and item['expected_rejection'] in result['error']
   assert not item['blocked_updates'] and not (root/(case+'-before-entry.json')).exists()
  else:
   assert item['exit_code']==0 and result['status']=='PASS_GUARDED_INSTALLED_ENTRY_ONLY' and result['entered'] and result['lease_continuous'] and result['lease_released'] and result['threads_closed']
   assert result['configuration_sha256']==cases['configuration_sha256'] and result['state_sha256']==item['state_sha256']==spec['state_sha256']
   assert result['lease_owner_pid']==owner['pid']
   expected_version='b01-offline-20260930-v5' if index==6 else 'b01-offline-20260930-v7'
   assert result['version']==expected_version
   output=result['entry_output']
   if item['command']=='controller-check':
    assert output['status']=='INSTALLED_CONTROLLER_IDLE_CHECK_PASS' and output['model_loads']==0 and not output['capture_opened']
    assert len(output['unavailable_rejections'])==3 and result['borrowers']==result['borrowers_closed']==1
   else:
    assert output['status']=='OFFLINE_CODE_AND_ASSETS_HEALTHY' and not output['models_loaded'] and not output['capture_opened']
    assert result['borrowers']==result['borrowers_closed']==0 and output['version']==expected_version
   assert len(item['blocked_updates'])==2
   for event in item['blocked_updates']:
    phase=event['phase'];barrier=read(root/(case+'-'+phase+'.json'));gate=read(root/(case+'-'+phase+'-continue.json'))
    assert barrier['owner']==owner and barrier['lease_token']==event['lease_token']==result['lease_token'] and event['pid']==owner['pid']
    assert barrier['state_sha256']==result['state_sha256'] and event['state_unchanged'] and 'owns' in event['error']
    assert gate==dict(continue_phase=phase,owner_pid=owner['pid'])
   tokens[case]=result['lease_token']
  observations.append(dict(case=case,exit_code=item['exit_code'],entered=result['entered'],seconds=result['elapsed_seconds'],current_status=result['current_status']))
 assert len(set(tokens.values()))==3
 dep=root/'deployment';state=read(dep/'state.json');assert state==cases['final'] and sha(dep/'state.json')==cases['final_state_sha256']==r['final_state_sha256']
 assert state['current']==cases['first']['current'] and state['previous']==cases['activated']['current']
 records={p.name:read(p) for p in (dep/'transactions').glob('*.json')};assert len(records)==3 and not list((dep/'staged').iterdir())
 def projection(name):
  rec=records[name];return dict(schema='just-peachy.candidate-state.v1',current=rec['current'],previous=rec['previous'],transaction=name,transaction_sha256=sha(dep/'transactions'/name))
 chain=[];name=state['transaction']
 while name is not None:
  assert name in records and name not in chain;chain.append(name);record=records[name];prior=record['prior_transaction']
  expected=hashlib.sha256(json.dumps(projection(prior),indent=2,allow_nan=False).encode()).hexdigest() if prior else None
  assert record['expected_prior_sha256']==expected and record['previous']==(records[prior]['current'] if prior else None)
  name=prior
 assert len(chain)==3 and projection(chain[0])==state
 for pointer in [cases['first']['current'],cases['activated']['current']]:
  d=read(pointer['descriptor']);assert sha(pointer['descriptor'])==pointer['descriptor_sha256']
  assert d['candidate_root']==str(dep) and d['data_root']==str(root/'data') and d['dependencies']==a['retained_lock'] and d['dependencies_sha256']==a['retained_lock_sha256']
  release=Path(d['release']);assert sha(release/'RELEASE_MANIFEST.json')==d['manifest_sha256']==pointer['manifest_sha256']
 assert sha(a['retained_lock'])==a['retained_lock_sha256'] and sha(a['source_state'])==a['source_state_sha256']
 assert sha(a['runtime_config_source'])==a['runtime_config_sha256']==sha(root/'N2_RUNTIME_BACKUP.json')
 for name,expected in cases['configuration_sha256'].items():assert sha(root/'data'/name)==expected
 assert cases['configuration_sha256']==r['configuration_sha256'] and (root/'data/private-preservation-canary').read_bytes()==b'PRIVATE_SYNTHETIC_CANARY\n'
 assert not (root/'data/runtime.lock').exists() and (root/'data/.runtime.guard').read_bytes()==b''
 with (root/'data/.runtime.guard').open('r+b') as guard:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not (root/'data/source_receipts').exists() and not list((root/'data').rglob('*.wav'))
 summary=dict(status='PASS_INDEPENDENT_GUARDED_INSTALLED_HEALTH_CONTROLLER_AND_ROLLBACK_ONLY',natural_exit=0,cases=7,early_rejections=4,real_entry_calls=3,blocked_updates=6,
  current_candidate=state['current']['version'],previous_candidate=state['previous']['version'],final_state_sha256=sha(dep/'state.json'),
  observations=observations,original_configs_unchanged=True,continuous_data_ownership=True,process_local_borrow_adapter=True,
  models_loaded=False,capture_opened=False,GUI_opened=False,baseline_activated=False,protocol_seconds=r['elapsed_seconds'])
links={}
assert not any(p.is_symlink() for p in root.rglob('*'))
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
size=sum(x['bytes'] for x in files.values());assert size<a['target_output_max_bytes']==4*1024**2
summary.update(owners_closed=len(owners),peak_rss_bytes=r['peak_rss_bytes'],sampled_aggregate_peak_bytes=max(x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),target_bytes=size,baseline_unchanged=True,capture_closed=True,leases_free=True,field_release_accepted=False,model_inference=False)
summary['reader_generated_cache_additions']={k:v['sha256'] for k,v in cache_additions.items()}
print(json.dumps(dict(summary=summary,files=files,links=links,cache_additions=cache_additions)))
''')
    out=PRIVATE/(args.run+'-evidence');backup=out/'target';backup.mkdir();seen=set();seen_links=set()
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/'+args.run+' -cf - .'],timeout=90)
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
        for member in archive:
            if member.isdir():continue
            assert member.name.startswith('./');name=member.name[2:];path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts
            if member.issym():
                assert name in x['links'] and name not in seen_links and member.linkname==x['links'][name];seen_links.add(name);continue
            assert member.isfile() and name in x['files'] and name not in seen
            raw=archive.extractfile(member).read();assert len(raw)==x['files'][name]['bytes'] and hashlib.sha256(raw).hexdigest()==x['files'][name]['sha256']
            target=backup.joinpath(*path.parts);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(raw)
            assert hashlib.sha256(target.read_bytes()).hexdigest()==x['files'][name]['sha256'];seen.add(name)
    assert seen==set(x['files']) and seen_links==set(x['links'])
    import base64
    for name,row in x['cache_additions'].items():
        raw=base64.b64decode(row['data']);assert hashlib.sha256(raw).hexdigest()==row['sha256']
        target=out/'reader-generated-caches'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(raw)
    combined=x['summary']['target_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert combined+1024**2<8*1024**2
    x['summary'].update(review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),private_backup_verified=True,backup_files=len(seen),backup_links=len(seen_links),combined_bytes=combined)
    for name,value in [('REVIEW.json',x['summary']),('BACKUP.json',dict(files=x['files'],links=x['links'])),('SYMLINKS.json',x['links'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in x['summary'].items() if k not in ['observations','negatives','actions']}))


if __name__=='__main__':main()
