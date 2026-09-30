"""Independent native package review and private backup; README_FIELD_TRANSACTION_V1.md."""
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
    p=argparse.ArgumentParser();p.add_argument('--run',choices=['field-transaction-v1'],default='field-transaction-v1');args=p.parse_args()
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
passed=r['status']=='PASS_NATIVE_SINGLE_STATE_QUOTA_AND_INJECTED_COMMIT_BOUNDARIES_ONLY'
if not passed:
 assert r['status']=='FAILED_PRESERVED' and dispatch['exit_code']==1
 summary=dict(status='REVIEWED_CANDIDATE_TRANSACTION_FAILURE_ONLY',natural_exit=1,error=r['error'],scope='Failure preserved; transaction acceptance withheld')
else:
 assert dispatch['exit_code']==0 and not any(r[k] for k in ['capture_opened','models_loaded','GUI_opened','assets_copied','original_baseline_activated','automatic_retry','process_kill_test','power_loss_test'])
 lock=read(a['retained_lock']);assert sha(a['retained_lock'])==r['dependency_lock_sha256']==a['retained_lock_sha256']
 # Independent retained byte/membership check; never invoke the candidate helper.
 for tree,expected in lock['roots'].items():
  assert sorted(str(p) for p in Path(tree).rglob('*') if p.is_file() or p.is_symlink())==expected
 for item in lock['entries']:
  p=Path(item['path']);assert str(p.resolve(strict=True))==item['resolved'] and (os.readlink(p) if p.is_symlink() else None)==item['link']
  if item['kind']=='file':
   st=p.stat();assert st.st_size==item['bytes'] and st.st_dev==item['device'] and st.st_ino==item['inode'] and sha(p)==item['sha256']
  else:assert p.is_dir() and p.is_symlink()
 cases=read(root/'TRANSACTION_CASES.json');dep=root/'deployment'
 state=read(dep/'state.json');assert state==cases['final'] and sha(dep/'state.json')==cases['final_sha256']==r['final_state_sha256']
 assert not (dep/'current.json').exists() and not (dep/'previous.json').exists()
 records={p.name:read(p) for p in (dep/'transactions').glob('*.json')}
 assert len(records)==cases['immutable_records']==r['immutable_records']==6
 def projection(name):
  record=records[name]
  return dict(schema='just-peachy.candidate-state.v1',current=record['current'],previous=record['previous'],transaction=name,transaction_sha256=sha(dep/'transactions'/name))
 def state_hash(value):return hashlib.sha256(json.dumps(value,indent=2,allow_nan=False).encode('utf-8')).hexdigest()
 chain=[];name=state['transaction']
 while name is not None:
  assert name not in chain and name in records;chain.append(name)
  record=records[name];assert record['schema']=='just-peachy.candidate-transaction.v1'
  prior=record['prior_transaction']
  assert record['expected_prior_sha256']==(state_hash(projection(prior)) if prior else None)
  assert record['previous']==(records[prior]['current'] if prior else None)
  assert record['dependency_check']['entries']==len(lock['entries'])
  name=prior
 assert len(chain)==5 and projection(chain[0])==state
 assert [records[n]['current']['version'] for n in reversed(chain)]==['b01-offline-20260930-v5','b01-offline-20260930-v7','b01-offline-20260930-v5','b01-offline-20260930-v7','b01-offline-20260930-v5']
 for rec in records.values():
  ptr=rec['current'];d=read(ptr['descriptor']);assert sha(ptr['descriptor'])==ptr['descriptor_sha256']
  assert d['candidate_root']==str(dep) and d['data_root']==str(root/'data')
  assert d['dependencies']==a['retained_lock'] and d['dependencies_sha256']==a['retained_lock_sha256']
  release=Path(d['release']);assert sha(release/'RELEASE_MANIFEST.json')==ptr['manifest_sha256']==d['manifest_sha256']
  assert sha(release/'config/field_contract.json')==d['contract_sha256']==lock['release_contract_sha256']
  assert d['version']==ptr['version'] and not ptr['inference_started']
 rejected=cases['rejections'];assert len(rejected)==r['rejections']==3 and all(x['unchanged'] for x in rejected)
 assert {x['case'] for x in rejected}=={'activation_quota_before_any_candidate_write','rollback_quota_before_any_candidate_write','stale_authoritative_state'}
 for case in rejected[:2]:
  assert case['before']==case['after'] and 'quota rejected before publication' in case['error']
  assert all(name in {p.relative_to(dep).as_posix() for p in dep.rglob('*') if p.is_file()} for name in case['before'])
 interrupted=cases['interruptions'];assert [x['phase'] for x in interrupted]==['before_commit','after_commit'] and len(interrupted)==r['injected_interruptions']==2
 first,second=interrupted;orphan=set(records)-set(chain);assert orphan=={first['transaction']}
 staged=list((dep/'staged').glob('*.json'));assert len(staged)==1 and staged[0].name==first['transaction'] and read(staged[0])==projection(first['transaction'])
 assert first['prior_sha256']==first['observed_sha256']==cases['third_sha256'] and first['observed_state']==cases['third'] and not first['committed']
 assert records[first['transaction']]['expected_prior_sha256']==first['prior_sha256']
 assert second['transaction'] in chain and second['committed'] and second['prior_sha256']==cases['third_sha256']
 assert second['observed_state']==projection(second['transaction']) and second['observed_sha256']==state_hash(second['observed_state'])
 assert not (dep/'staged'/second['transaction']).exists() and not any(x['automatic_retry'] for x in interrupted)
 assert state['current']==cases['first']['current'] and state['previous']==cases['second']['current']
 assert not (root/'data/runtime.lock').exists() and (root/'data/private-preservation-canary').read_bytes()==b'PRIVATE_SYNTHETIC_CANARY\n'
 assert sha(root/'data/live_config.json')==a['live_config_sha256'] and read(root/'data/DATA_SCHEMA.json')==dict(schema_version=1)
 assert len(list((root/'data').iterdir()))==3 and not (root/'PROBE_OWNER.json').exists()
 summary=dict(status='PASS_INDEPENDENT_SINGLE_STATE_QUOTA_AND_INJECTED_COMMIT_BOUNDARIES_ONLY',natural_exit=0,
  dependency_entries=len(lock['entries']),dependency_lock_sha256=a['retained_lock_sha256'],rejections=3,injected_interruptions=2,
  immutable_records=6,committed_chain_records=5,retained_precommit_staged_files=1,final_state_sha256=sha(dep/'state.json'),
  candidate_version=state['current']['version'],previous_candidate_version=state['previous']['version'],data_unchanged=True,
  new_import_probe=False,models_loaded=False,capture_opened=False,GUI_opened=False,baseline_activated=False,
  power_loss_test=False,process_kill_test=False,automatic_retry=False,protocol_seconds=r['elapsed_seconds'])
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
