"""Independent native package review and private backup; README_FIELD_DEPENDENCIES_V2.md."""
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
    p=argparse.ArgumentParser();p.add_argument('--run',choices=['field-dependency-v2'],default='field-dependency-v2');args=p.parse_args()
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
passed=r['status']=='PASS_RETAINED_DEPENDENCY_GUARDED_CANDIDATE_ROLLBACK_AND_PREWRITE_QUOTA_ONLY'
if not passed:
 assert r['status']=='FAILED_PRESERVED' and dispatch['exit_code']==1
 summary=dict(status='REVIEWED_RETAINED_DEPENDENCY_FAILURE_ONLY',natural_exit=1,error=r['error'],probe_started=(root/'PROBE_OWNER.json').exists(),scope='Failure preserved; no dependency/deployment acceptance')
else:
 assert dispatch['exit_code']==0 and not r['capture_opened'] and not r['models_loaded'] and not r['GUI_opened']
 assert not r['assets_copied'] and not r['releases_copied'] and not r['baseline_activated'] and not r['relocation_qualified']
 lock=read(a['retained_lock']);assert sha(a['retained_lock'])==r['dependency_lock_sha256']
 assert lock['schema']=='just-peachy.retained-dependencies.v1'
 for tree,expected in lock['roots'].items():
  assert sorted(str(p) for p in Path(tree).rglob('*') if p.is_file() or p.is_symlink())==expected
 seen=set();unique={}
 for item in lock['entries']:
  p=Path(item['path']);assert item['path'] not in seen;seen.add(item['path'])
  assert str(p.resolve(strict=True))==item['resolved'] and (os.readlink(p) if p.is_symlink() else None)==item['link']
  if item['kind']=='directory_link':assert p.is_dir() and p.is_symlink() and item['bytes']==0 and item['sha256'] is None
  else:
   st=p.stat();assert p.is_file() and st.st_size==item['bytes'] and sha(p)==item['sha256'] and st.st_dev==item['device'] and st.st_ino==item['inode']
   unique[(st.st_dev,st.st_ino)]=st.st_size
 assert len(unique)==lock['unique_files'] and sum(unique.values())==lock['unique_logical_bytes']
 assert r['dependency_check']['entries']==len(seen) and r['elf_roots']==len(lock['elf'])
 for elf in lock['elf']:
  assert 'not found' not in elf['text'] and elf['root'] in {x['resolved'] for x in lock['entries']}
  assert all(p in seen for p in elf['resolved'])
 probe=read(a['retained_probe']);command=read(Path(a['retained_probe']).parent/'PROBE_COMMAND.json')
 assert not r['new_import_probe'] and not (root/'PROBE_OWNER.json').exists() and sha(a['retained_probe'])==a['retained_probe_sha256']
 assert command['exit_code']==0 and json.loads(command['stdout'])==probe and probe['capture_closed'] and not probe['models_loaded'] and not probe['Tk_root_created']
 assert set(probe['mapped_elf'])<={x['resolved'] for x in lock['entries']} and len(probe['mapped_elf'])==r['mapped_elf_count']
 assert probe['address_space']==[768*1024**2]*2 and probe['stack']==[1048576]*2
 seq=read(root/'POINTER_SEQUENCE.json');assert seq['first']==seq['rolled_back']==read(root/'deployment/current.json')
 assert seq['second']==read(root/'deployment/previous.json') and seq['first']['version']=='b01-offline-20260930-v5' and seq['second']['version']=='b01-offline-20260930-v7'
 for pointer in [seq['first'],seq['second']]:
  descriptor=Path(pointer['descriptor']);assert sha(descriptor)==pointer['descriptor_sha256']
  d=read(descriptor);assert d['candidate_root']==str(root/'deployment') and d['data_root']==str(root/'data')
  assert d['dependencies']==a['retained_lock'] and d['dependencies_sha256']==r['dependency_lock_sha256']
  release=Path(d['release']);assert sha(release/'RELEASE_MANIFEST.json')==d['manifest_sha256'] and sha(release/'config/field_contract.json')==d['contract_sha256']==lock['release_contract_sha256']
  manifest=read(release/'RELEASE_MANIFEST.json')
  for row in manifest['files']:assert sha(release/row['path'])==row['sha256']
 assert len(list((root/'deployment/history').glob('*.json')))==3
 rejected=read(root/'REJECTIONS.json');assert len(rejected)==r['rejections']==8 and all(x['pointer_unchanged'] for x in rejected)
 assert {x['case'] for x in rejected}=={'stale_current_pointer','wrong_descriptor_digest','wrong_previous_digest','wrong_dependency_hash','missing_dependency','wrong_resolved_target','busy_private_data','prewrite_output_bound'}
 assert not (root/'must-not-exist.json').exists()
 assert not (root/'data/runtime.lock').exists() and (root/'data/private-preservation-canary').read_bytes()==b'PRIVATE_SYNTHETIC_CANARY\n'
 assert sha(root/'data/live_config.json')==a['live_config_sha256'] and read(root/'data/DATA_SCHEMA.json')==dict(schema_version=1)
 assert not (root/'data/sessions').exists() and not (root/'data/source_receipts').exists()
 storage=read(root/'STORAGE.json');assert storage==r['storage'] and storage['incremental_asset_bytes']==storage['incremental_release_bytes']==0
 assert storage['remaining_after_private_quota_reservation']>5*1024**3 and storage['pinned_unique_bytes']==sum(unique.values())
 summary=dict(status='PASS_RETAINED_DEPENDENCY_GATES_PREWRITE_QUOTA_AND_CANDIDATE_ROLLBACK_ONLY',natural_exit=0,
  dependency_entries=len(seen),unique_files=len(unique),unique_logical_bytes=sum(unique.values()),ELF_roots=len(lock['elf']),mapped_ELFs=len(probe['mapped_elf']),
  dependency_lock_sha256=r['dependency_lock_sha256'],rejections=rejected,storage=storage,
  new_import_probe=False,retained_probe_only=True,baseline_activated=False,relocation_qualified=False,models_loaded=False,capture_opened=False,GUI_opened=False,protocol_seconds=r['elapsed_seconds'])
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
